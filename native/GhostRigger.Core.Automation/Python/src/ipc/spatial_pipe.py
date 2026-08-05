"""Bounded Windows named-pipe transport for Ghost Studio spatial IPC.

The full-trust Ghost Studio process owns the server pipe.  The contained MCP
adapter connects as a client.  The pipe is session-local, rejects remote
clients, and carries one strictly framed request/response per connection.
HMAC authentication remains owned by :mod:`spatial_auth` and the IPC route
dispatcher; this module only preserves those signed bytes across the transport.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import threading
import time
from typing import Callable, Mapping


WINDOWS_SPATIAL_TRANSPORT = "windows-named-pipe-v1"
PIPE_REQUEST_SCHEMA = "ghoststudio-spatial-pipe-request/v1"
PIPE_RESPONSE_SCHEMA = "ghoststudio-spatial-pipe-response/v1"
PIPE_RESPONSE_AUTH_DOMAIN = "ghoststudio-spatial-pipe-response-hmac/v1"
MAX_REQUEST_BODY_BYTES = 1024 * 1024
MAX_RESPONSE_BODY_BYTES = 4 * 1024 * 1024
MAX_REQUEST_FRAME_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_FRAME_BYTES = 6 * 1024 * 1024
_PIPE_PREFIX = "\\\\.\\pipe\\LOCAL\\"
_PIPE_NAME_RE = re.compile(
    r"^\\\\\.\\pipe\\LOCAL\\GhostStudioSpatial-[A-Za-z0-9_-]{43}$"
)
_PACKAGE_SID_RE = re.compile(
    r"^S-1-15-2(?:-(?:0|[1-9]\d{0,9})){7}$"
)
_AUTH_HEADER_NAMES = frozenset(
    {
        "X-GhostStudio-Session",
        "X-GhostStudio-Timestamp",
        "X-GhostStudio-Nonce",
        "X-GhostStudio-Signature",
    }
)
_ROUTES = {
    "/api/mcpstudio/health": "GET",
    "/api/mcpstudio/spatial-snapshot": "POST",
    "/api/mcpstudio/capture": "POST",
    "/api/mcpstudio/evidence-gaps": "POST",
}
_LENGTH = struct.Struct(">I")
_RESPONSE_ACK = b"\x06"


class SpatialPipeError(RuntimeError):
    """Stable, non-secret transport failure."""

    _MESSAGES = {
        "invalid-pipe-name": "Ghost Studio spatial pipe name is invalid.",
        "invalid-request-frame": "Ghost Studio spatial pipe request is invalid.",
        "invalid-response-frame": "Ghost Studio spatial pipe response is invalid.",
        "pipe-unavailable": "Ghost Studio spatial pipe is unavailable.",
        "pipe-timeout": "Ghost Studio spatial pipe request timed out.",
        "pipe-security-failed": "Ghost Studio spatial pipe security failed.",
        "pipe-session-mismatch": "Ghost Studio spatial pipe session is invalid.",
        "unsupported-platform": "Ghost Studio spatial pipe requires Windows.",
    }

    def __init__(self, code: str):
        self.code = code
        super().__init__(self._MESSAGES.get(code, "Ghost Studio spatial pipe failed."))


class SpatialPipeFatalError(SpatialPipeError):
    """Unrecoverable server identity failure that must terminate the pipe thread."""


@dataclass(frozen=True)
class SpatialPipeRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class SpatialPipeResponse:
    status: int
    content_type: str
    body: bytes


def create_windows_spatial_pipe_name() -> str:
    """Return an unpredictable session-local pipe name."""

    token = secrets.token_urlsafe(32)
    name = f"{_PIPE_PREFIX}GhostStudioSpatial-{token}"
    return validate_windows_spatial_pipe_name(name)


def validate_windows_spatial_pipe_name(value: object) -> str:
    if not isinstance(value, str) or not _PIPE_NAME_RE.fullmatch(value):
        raise SpatialPipeError("invalid-pipe-name")
    return value


def _validate_windows_app_container_package_sid(value: object) -> str:
    if (
        not isinstance(value, str)
        or not _PACKAGE_SID_RE.fullmatch(value)
        or any(int(part, 10) > 0xFFFFFFFF for part in value.split("-")[4:])
    ):
        raise SpatialPipeError("pipe-security-failed")
    return value


def _windows_app_container_server_pipe_name(
    pipe_name: object,
    package_sid: object,
    *,
    session_id: object,
) -> str:
    """Translate a public LOCAL alias to its exact AppContainer server path."""

    alias = validate_windows_spatial_pipe_name(pipe_name)
    exact_package_sid = _validate_windows_app_container_package_sid(package_sid)
    if (
        not isinstance(session_id, int)
        or isinstance(session_id, bool)
        or not (0 <= session_id <= 0xFFFFFFFF)
    ):
        raise SpatialPipeError("pipe-security-failed")
    suffix = alias[len(_PIPE_PREFIX) :]
    return (
        rf"\\.\pipe\Sessions\{session_id}\AppContainerNamedObjects"
        rf"\{exact_package_sid}\{suffix}"
    )


def _strict_auth_headers(headers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(headers, Mapping) or set(headers) != _AUTH_HEADER_NAMES:
        raise SpatialPipeError("invalid-request-frame")
    normalized: dict[str, str] = {}
    for key in sorted(_AUTH_HEADER_NAMES):
        value = headers.get(key)
        if not isinstance(value, str) or not value or len(value) > 256:
            raise SpatialPipeError("invalid-request-frame")
        normalized[key] = value
    return normalized


def _encode_body(value: bytes, *, limit: int, error_code: str) -> str:
    if not isinstance(value, bytes) or len(value) > limit:
        raise SpatialPipeError(error_code)
    return base64.b64encode(value).decode("ascii")


def _decode_body(value: object, *, limit: int, error_code: str) -> bytes:
    if not isinstance(value, str) or len(value) > ((limit + 2) // 3) * 4:
        raise SpatialPipeError(error_code)
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise SpatialPipeError(error_code) from exc
    if len(decoded) > limit:
        raise SpatialPipeError(error_code)
    return decoded


def _serialize_frame(payload: dict[str, object], *, limit: int, error_code: str) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise SpatialPipeError(error_code) from exc
    if not encoded or len(encoded) > limit:
        raise SpatialPipeError(error_code)
    return encoded


def _parse_frame(value: bytes, *, limit: int, error_code: str) -> dict[str, object]:
    if not isinstance(value, bytes) or not value or len(value) > limit:
        raise SpatialPipeError(error_code)
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpatialPipeError(error_code) from exc
    if not isinstance(payload, dict):
        raise SpatialPipeError(error_code)
    return payload


def encode_spatial_pipe_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
) -> bytes:
    normalized_method = str(method or "").strip().upper()
    normalized_path = str(path or "").strip()
    if _ROUTES.get(normalized_path) != normalized_method:
        raise SpatialPipeError("invalid-request-frame")
    if normalized_method == "GET" and body != b"":
        raise SpatialPipeError("invalid-request-frame")
    payload = {
        "schema": PIPE_REQUEST_SCHEMA,
        "method": normalized_method,
        "path": normalized_path,
        "headers": _strict_auth_headers(headers),
        "bodyBase64": _encode_body(
            body,
            limit=MAX_REQUEST_BODY_BYTES,
            error_code="invalid-request-frame",
        ),
    }
    return _serialize_frame(
        payload,
        limit=MAX_REQUEST_FRAME_BYTES,
        error_code="invalid-request-frame",
    )


def decode_spatial_pipe_request(value: bytes) -> SpatialPipeRequest:
    payload = _parse_frame(
        value,
        limit=MAX_REQUEST_FRAME_BYTES,
        error_code="invalid-request-frame",
    )
    if set(payload) != {"schema", "method", "path", "headers", "bodyBase64"}:
        raise SpatialPipeError("invalid-request-frame")
    method = payload.get("method")
    path = payload.get("path")
    if (
        payload.get("schema") != PIPE_REQUEST_SCHEMA
        or not isinstance(method, str)
        or not isinstance(path, str)
        or _ROUTES.get(path) != method
    ):
        raise SpatialPipeError("invalid-request-frame")
    headers = payload.get("headers")
    if not isinstance(headers, dict):
        raise SpatialPipeError("invalid-request-frame")
    body = _decode_body(
        payload.get("bodyBase64"),
        limit=MAX_REQUEST_BODY_BYTES,
        error_code="invalid-request-frame",
    )
    if method == "GET" and body != b"":
        raise SpatialPipeError("invalid-request-frame")
    return SpatialPipeRequest(
        method=method,
        path=path,
        headers=_strict_auth_headers(headers),
        body=body,
    )


def _response_signature(
    *,
    secret: bytes,
    request: SpatialPipeRequest,
    response: SpatialPipeResponse,
) -> str:
    if not isinstance(secret, bytes) or len(secret) != 32:
        raise SpatialPipeError("invalid-response-frame")
    canonical = "\n".join(
        (
            PIPE_RESPONSE_AUTH_DOMAIN,
            request.method,
            request.path,
            request.headers["X-GhostStudio-Session"],
            request.headers["X-GhostStudio-Timestamp"],
            request.headers["X-GhostStudio-Nonce"],
            hashlib.sha256(request.body).hexdigest(),
            str(response.status),
            hashlib.sha256(response.body).hexdigest(),
        )
    ).encode("utf-8")
    return hmac.new(secret, canonical, hashlib.sha256).hexdigest()


def encode_spatial_pipe_response(
    response: SpatialPipeResponse,
    *,
    request: SpatialPipeRequest,
    secret: bytes,
) -> bytes:
    if (
        not isinstance(response, SpatialPipeResponse)
        or not isinstance(response.status, int)
        or isinstance(response.status, bool)
        or not (100 <= response.status <= 599)
        or response.content_type != "application/json"
    ):
        raise SpatialPipeError("invalid-response-frame")
    payload = {
        "schema": PIPE_RESPONSE_SCHEMA,
        "status": response.status,
        "contentType": response.content_type,
        "requestNonce": request.headers["X-GhostStudio-Nonce"],
        "bodyBase64": _encode_body(
            response.body,
            limit=MAX_RESPONSE_BODY_BYTES,
            error_code="invalid-response-frame",
        ),
        "signature": _response_signature(
            secret=secret,
            request=request,
            response=response,
        ),
    }
    return _serialize_frame(
        payload,
        limit=MAX_RESPONSE_FRAME_BYTES,
        error_code="invalid-response-frame",
    )


def decode_spatial_pipe_response(
    value: bytes,
    *,
    request: SpatialPipeRequest,
    secret: bytes,
) -> SpatialPipeResponse:
    payload = _parse_frame(
        value,
        limit=MAX_RESPONSE_FRAME_BYTES,
        error_code="invalid-response-frame",
    )
    if set(payload) != {
        "schema",
        "status",
        "contentType",
        "requestNonce",
        "bodyBase64",
        "signature",
    }:
        raise SpatialPipeError("invalid-response-frame")
    status = payload.get("status")
    content_type = payload.get("contentType")
    request_nonce = payload.get("requestNonce")
    signature = payload.get("signature")
    if (
        payload.get("schema") != PIPE_RESPONSE_SCHEMA
        or not isinstance(status, int)
        or isinstance(status, bool)
        or not (100 <= status <= 599)
        or content_type != "application/json"
        or request_nonce
        != request.headers["X-GhostStudio-Nonce"]
        or not isinstance(signature, str)
        or not re.fullmatch(r"[0-9a-f]{64}", signature)
    ):
        raise SpatialPipeError("invalid-response-frame")
    response = SpatialPipeResponse(
        status=status,
        content_type=content_type,
        body=_decode_body(
            payload.get("bodyBase64"),
            limit=MAX_RESPONSE_BODY_BYTES,
            error_code="invalid-response-frame",
        ),
    )
    expected = _response_signature(
        secret=secret,
        request=request,
        response=response,
    )
    if not hmac.compare_digest(signature, expected):
        raise SpatialPipeError("invalid-response-frame")
    return response


def pack_spatial_pipe_frame(value: bytes, *, limit: int) -> bytes:
    if (
        not isinstance(value, bytes)
        or not isinstance(limit, int)
        or limit <= 0
        or not value
        or len(value) > limit
    ):
        raise SpatialPipeError("invalid-request-frame")
    return _LENGTH.pack(len(value)) + value


def unpack_spatial_pipe_frame(value: bytes, *, limit: int) -> bytes:
    if (
        not isinstance(value, bytes)
        or not isinstance(limit, int)
        or limit <= 0
        or len(value) < _LENGTH.size
    ):
        raise SpatialPipeError("invalid-request-frame")
    length = _LENGTH.unpack(value[: _LENGTH.size])[0]
    payload = value[_LENGTH.size :]
    if length <= 0 or length > limit or len(payload) != length:
        raise SpatialPipeError("invalid-request-frame")
    return payload


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _ERROR_IO_PENDING = 997
    _ERROR_IO_INCOMPLETE = 996
    _ERROR_OPERATION_ABORTED = 995
    _ERROR_BROKEN_PIPE = 109
    _ERROR_NO_DATA = 232
    _ERROR_PIPE_NOT_CONNECTED = 233
    _ERROR_NOT_FOUND = 1168
    _ERROR_PIPE_CONNECTED = 535
    _ERROR_PIPE_BUSY = 231
    _ERROR_FILE_NOT_FOUND = 2
    _ERROR_SEM_TIMEOUT = 121
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 258
    _INFINITE = 0xFFFFFFFF
    _PIPE_ACCESS_DUPLEX = 0x00000003
    _FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
    _FILE_FLAG_OVERLAPPED = 0x40000000
    _PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
    _FILE_READ_DATA = 0x00000001
    _FILE_WRITE_DATA = 0x00000002
    _FILE_READ_ATTRIBUTES = 0x00000080
    _SYNCHRONIZE = 0x00100000
    _PIPE_CLIENT_ACCESS = (
        _FILE_READ_DATA
        | _FILE_WRITE_DATA
        | _FILE_READ_ATTRIBUTES
        | _SYNCHRONIZE
    )
    _OPEN_EXISTING = 3
    _TOKEN_QUERY = 0x0008
    _TOKEN_USER = 1
    _TOKEN_IS_APP_CONTAINER = 29
    _TOKEN_CAPABILITIES = 30
    _TOKEN_APP_CONTAINER_SID = 31
    _SDDL_REVISION_1 = 1
    _SECURITY_SQOS_PRESENT = 0x00100000
    _SECURITY_IDENTIFICATION = 0x00010000
    _SE_KERNEL_OBJECT = 6
    _DACL_SECURITY_INFORMATION = 0x00000004
    _LABEL_SECURITY_INFORMATION = 0x00000010
    _SE_DACL_PROTECTED = 0x1000
    _ACCESS_ALLOWED_ACE_TYPE = 0x00
    _SYSTEM_MANDATORY_LABEL_ACE_TYPE = 0x11
    _SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 0x1

    class _SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = (
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        )

    class _SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = (
            ("Sid", wintypes.LPVOID),
            ("Attributes", wintypes.DWORD),
        )

    class _TOKEN_USER_STRUCT(ctypes.Structure):
        _fields_ = (("User", _SID_AND_ATTRIBUTES),)

    class _TOKEN_APPCONTAINER_INFORMATION(ctypes.Structure):
        _fields_ = (("TokenAppContainer", wintypes.LPVOID),)

    class _ACL(ctypes.Structure):
        _fields_ = (
            ("AclRevision", ctypes.c_ubyte),
            ("Sbz1", ctypes.c_ubyte),
            ("AclSize", wintypes.WORD),
            ("AceCount", wintypes.WORD),
            ("Sbz2", wintypes.WORD),
        )

    class _ACE_HEADER(ctypes.Structure):
        _fields_ = (
            ("AceType", ctypes.c_ubyte),
            ("AceFlags", ctypes.c_ubyte),
            ("AceSize", wintypes.WORD),
        )

    class _ACCESS_ALLOWED_ACE(ctypes.Structure):
        _fields_ = (
            ("Header", _ACE_HEADER),
            ("Mask", wintypes.DWORD),
            ("SidStart", wintypes.DWORD),
        )

    class _OVERLAPPED(ctypes.Structure):
        _fields_ = (
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        )

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    _kernel32.GetCurrentThread.restype = wintypes.HANDLE
    _kernel32.GetCurrentProcessId.restype = wintypes.DWORD
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    _kernel32.LocalFree.restype = wintypes.HLOCAL
    _kernel32.CreateEventW.argtypes = (
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    )
    _kernel32.CreateEventW.restype = wintypes.HANDLE
    _kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.CancelIoEx.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_OVERLAPPED),
    )
    _kernel32.CancelIoEx.restype = wintypes.BOOL
    _kernel32.GetOverlappedResult.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_OVERLAPPED),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL,
    )
    _kernel32.GetOverlappedResult.restype = wintypes.BOOL
    _kernel32.CreateNamedPipeW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
    )
    _kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    _kernel32.ConnectNamedPipe.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_OVERLAPPED),
    )
    _kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    _kernel32.DisconnectNamedPipe.argtypes = (wintypes.HANDLE,)
    _kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    _kernel32.ReadFile.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(_OVERLAPPED),
    )
    _kernel32.ReadFile.restype = wintypes.BOOL
    _kernel32.WriteFile.argtypes = (
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(_OVERLAPPED),
    )
    _kernel32.WriteFile.restype = wintypes.BOOL
    _kernel32.WaitNamedPipeW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    _kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    _kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.GetNamedPipeClientSessionId.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.GetNamedPipeClientSessionId.restype = wintypes.BOOL
    _kernel32.GetNamedPipeServerProcessId.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    _kernel32.ProcessIdToSessionId.argtypes = (
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    _kernel32.ProcessIdToSessionId.restype = wintypes.BOOL

    _advapi32.OpenProcessToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    )
    _advapi32.OpenProcessToken.restype = wintypes.BOOL
    _advapi32.OpenThreadToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.BOOL,
        ctypes.POINTER(wintypes.HANDLE),
    )
    _advapi32.OpenThreadToken.restype = wintypes.BOOL
    _advapi32.ImpersonateNamedPipeClient.argtypes = (wintypes.HANDLE,)
    _advapi32.ImpersonateNamedPipeClient.restype = wintypes.BOOL
    _advapi32.RevertToSelf.argtypes = ()
    _advapi32.RevertToSelf.restype = wintypes.BOOL
    _advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    _advapi32.GetTokenInformation.restype = wintypes.BOOL
    _advapi32.ConvertSidToStringSidW.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    )
    _advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    )
    _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    _advapi32.GetSecurityInfo.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(ctypes.POINTER(_ACL)),
        ctypes.POINTER(ctypes.POINTER(_ACL)),
        ctypes.POINTER(wintypes.LPVOID),
    )
    _advapi32.GetSecurityInfo.restype = wintypes.DWORD
    _advapi32.GetSecurityDescriptorControl.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.WORD),
        ctypes.POINTER(wintypes.DWORD),
    )
    _advapi32.GetSecurityDescriptorControl.restype = wintypes.BOOL
    _advapi32.GetAce.argtypes = (
        ctypes.POINTER(_ACL),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
    )
    _advapi32.GetAce.restype = wintypes.BOOL


def _require_windows() -> None:
    if os.name != "nt":
        raise SpatialPipeError("unsupported-platform")


def _windows_error(code: str) -> SpatialPipeError:
    error = SpatialPipeError(code)
    if os.name == "nt":
        error.__cause__ = ctypes.WinError(ctypes.get_last_error())
    return error


def _current_windows_session_id() -> int:
    _require_windows()
    session_id = wintypes.DWORD()
    if not _kernel32.ProcessIdToSessionId(
        _kernel32.GetCurrentProcessId(),
        ctypes.byref(session_id),
    ):
        raise _windows_error("pipe-security-failed")
    return int(session_id.value)


def _current_user_sid_string() -> str:
    _require_windows()
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(
        _kernel32.GetCurrentProcess(),
        _TOKEN_QUERY,
        ctypes.byref(token),
    ):
        raise _windows_error("pipe-security-failed")
    sid_text = wintypes.LPWSTR()
    try:
        required = wintypes.DWORD()
        _advapi32.GetTokenInformation(
            token,
            _TOKEN_USER,
            None,
            0,
            ctypes.byref(required),
        )
        if required.value <= 0:
            raise _windows_error("pipe-security-failed")
        token_data = ctypes.create_string_buffer(required.value)
        if not _advapi32.GetTokenInformation(
            token,
            _TOKEN_USER,
            token_data,
            required,
            ctypes.byref(required),
        ):
            raise _windows_error("pipe-security-failed")
        token_user = ctypes.cast(
            token_data,
            ctypes.POINTER(_TOKEN_USER_STRUCT),
        ).contents
        if not _advapi32.ConvertSidToStringSidW(
            token_user.User.Sid,
            ctypes.byref(sid_text),
        ):
            raise _windows_error("pipe-security-failed")
        value = str(sid_text.value or "")
        if not value.startswith("S-1-"):
            raise SpatialPipeError("pipe-security-failed")
        return value
    finally:
        if sid_text:
            _kernel32.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))
        if token:
            _kernel32.CloseHandle(token)


def _sid_to_string(sid) -> str:
    sid_text = wintypes.LPWSTR()
    if not sid or not _advapi32.ConvertSidToStringSidW(
        sid,
        ctypes.byref(sid_text),
    ):
        raise _windows_error("pipe-security-failed")
    try:
        value = str(sid_text.value or "")
        if not value.startswith("S-1-"):
            raise SpatialPipeError("pipe-security-failed")
        return value
    finally:
        _kernel32.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))


def _acl_rows(acl) -> list[tuple[int, int, int, str]]:
    if not acl:
        raise SpatialPipeError("pipe-security-failed")
    rows: list[tuple[int, int, int, str]] = []
    for index in range(int(acl.contents.AceCount)):
        ace_pointer = wintypes.LPVOID()
        if not _advapi32.GetAce(
            acl,
            index,
            ctypes.byref(ace_pointer),
        ):
            raise _windows_error("pipe-security-failed")
        ace = ctypes.cast(
            ace_pointer,
            ctypes.POINTER(_ACCESS_ALLOWED_ACE),
        ).contents
        sid_address = int(ace_pointer.value) + _ACCESS_ALLOWED_ACE.SidStart.offset
        rows.append(
            (
                int(ace.Header.AceType),
                int(ace.Header.AceFlags),
                int(ace.Mask),
                _sid_to_string(wintypes.LPVOID(sid_address)),
            )
        )
    return rows


def _audit_pipe_security(
    handle,
    *,
    package_sid: str,
    user_sid: str,
) -> None:
    dacl = ctypes.POINTER(_ACL)()
    sacl = ctypes.POINTER(_ACL)()
    descriptor = wintypes.LPVOID()
    result = _advapi32.GetSecurityInfo(
        handle,
        _SE_KERNEL_OBJECT,
        _DACL_SECURITY_INFORMATION | _LABEL_SECURITY_INFORMATION,
        None,
        None,
        ctypes.byref(dacl),
        ctypes.byref(sacl),
        ctypes.byref(descriptor),
    )
    if result != 0 or not descriptor:
        raise SpatialPipeError("pipe-security-failed")
    try:
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not _advapi32.GetSecurityDescriptorControl(
            descriptor,
            ctypes.byref(control),
            ctypes.byref(revision),
        ) or not (control.value & _SE_DACL_PROTECTED):
            raise SpatialPipeError("pipe-security-failed")
        dacl_rows = _acl_rows(dacl)
        if len(dacl_rows) != 3 or any(
            ace_type != _ACCESS_ALLOWED_ACE_TYPE or flags != 0
            for ace_type, flags, _mask, _sid in dacl_rows
        ):
            raise SpatialPipeError("pipe-security-failed")
        dacl_by_sid = {
            sid: mask for _ace_type, _flags, mask, sid in dacl_rows
        }
        if set(dacl_by_sid) != {"S-1-5-18", user_sid, package_sid}:
            raise SpatialPipeError("pipe-security-failed")
        if dacl_by_sid[package_sid] != _PIPE_CLIENT_ACCESS:
            raise SpatialPipeError("pipe-security-failed")
        if any(
            dacl_by_sid[sid] not in {0x10000000, 0x001F01FF}
            for sid in ("S-1-5-18", user_sid)
        ):
            raise SpatialPipeError("pipe-security-failed")
        sacl_rows = _acl_rows(sacl)
        if sacl_rows != [
            (
                _SYSTEM_MANDATORY_LABEL_ACE_TYPE,
                0,
                _SYSTEM_MANDATORY_LABEL_NO_WRITE_UP,
                "S-1-16-4096",
            )
        ]:
            raise SpatialPipeError("pipe-security-failed")
    finally:
        _kernel32.LocalFree(descriptor)


def _token_information(token, information_class: int):
    required = wintypes.DWORD()
    _advapi32.GetTokenInformation(
        token,
        information_class,
        None,
        0,
        ctypes.byref(required),
    )
    if required.value <= 0:
        raise _windows_error("pipe-security-failed")
    buffer = ctypes.create_string_buffer(required.value)
    if not _advapi32.GetTokenInformation(
        token,
        information_class,
        buffer,
        required,
        ctypes.byref(required),
    ):
        raise _windows_error("pipe-security-failed")
    return buffer


def verify_windows_spatial_pipe_client(
    handle,
    *,
    package_sid: str,
    expected_user_sid: str,
) -> None:
    """Require the exact capability-free AppContainer client token."""

    if not _advapi32.ImpersonateNamedPipeClient(handle):
        raise _windows_error("pipe-security-failed")
    token = wintypes.HANDLE()
    try:
        if not _advapi32.OpenThreadToken(
            _kernel32.GetCurrentThread(),
            _TOKEN_QUERY,
            True,
            ctypes.byref(token),
        ):
            raise _windows_error("pipe-security-failed")
        app_container_flag = _token_information(
            token,
            _TOKEN_IS_APP_CONTAINER,
        )
        is_app_container = ctypes.cast(
            app_container_flag,
            ctypes.POINTER(wintypes.DWORD),
        ).contents.value
        if is_app_container != 1:
            raise SpatialPipeError("pipe-security-failed")
        user_buffer = _token_information(token, _TOKEN_USER)
        user = ctypes.cast(
            user_buffer,
            ctypes.POINTER(_TOKEN_USER_STRUCT),
        ).contents
        if _sid_to_string(user.User.Sid) != expected_user_sid:
            raise SpatialPipeError("pipe-security-failed")
        app_container_buffer = _token_information(
            token,
            _TOKEN_APP_CONTAINER_SID,
        )
        app_container = ctypes.cast(
            app_container_buffer,
            ctypes.POINTER(_TOKEN_APPCONTAINER_INFORMATION),
        ).contents
        if _sid_to_string(app_container.TokenAppContainer) != package_sid:
            raise SpatialPipeError("pipe-security-failed")
        capabilities = _token_information(token, _TOKEN_CAPABILITIES)
        if ctypes.cast(
            capabilities,
            ctypes.POINTER(wintypes.DWORD),
        ).contents.value != 0:
            raise SpatialPipeError("pipe-security-failed")
    finally:
        if token:
            _kernel32.CloseHandle(token)
        if not _advapi32.RevertToSelf():
            raise SpatialPipeFatalError("pipe-security-failed")


def _create_pipe_handle(pipe_name: str, package_sid: str):
    _require_windows()
    server_pipe_name = _windows_app_container_server_pipe_name(
        pipe_name,
        package_sid,
        session_id=_current_windows_session_id(),
    )
    user_sid = _current_user_sid_string()
    # The user ACE and package ACE deliberately satisfy the two-principal
    # AppContainer access check.  The low-integrity label permits the
    # contained client to write without granting any additional principal.
    sddl = (
        f"D:P(A;;GA;;;SY)(A;;GA;;;{user_sid})"
        f"(A;;0x{_PIPE_CLIENT_ACCESS:08x};;;{package_sid})"
        "S:(ML;;NW;;;LW)"
    )
    descriptor = wintypes.LPVOID()
    if not _advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl,
        _SDDL_REVISION_1,
        ctypes.byref(descriptor),
        None,
    ):
        raise _windows_error("pipe-security-failed")
    try:
        attributes = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES),
            descriptor,
            False,
        )
        handle = _kernel32.CreateNamedPipeW(
            server_pipe_name,
            _PIPE_ACCESS_DUPLEX
            | _FILE_FLAG_OVERLAPPED
            | _FILE_FLAG_FIRST_PIPE_INSTANCE,
            _PIPE_REJECT_REMOTE_CLIENTS,
            1,
            64 * 1024,
            64 * 1024,
            0,
            ctypes.byref(attributes),
        )
        if not handle or handle == _INVALID_HANDLE_VALUE:
            raise _windows_error("pipe-unavailable")
        try:
            _audit_pipe_security(
                handle,
                package_sid=package_sid,
                user_sid=user_sid,
            )
        except Exception:
            _kernel32.CloseHandle(handle)
            raise
        return handle
    finally:
        _kernel32.LocalFree(descriptor)


def _remaining_milliseconds(deadline: float) -> int:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SpatialPipeError("pipe-timeout")
    return max(1, min(0xFFFFFFFE, int(remaining * 1000)))


def _new_overlapped():
    event = _kernel32.CreateEventW(None, True, False, None)
    if not event:
        raise _windows_error("pipe-unavailable")
    return event, _OVERLAPPED(hEvent=event)


def _cancel_and_drain_overlapped(handle, overlapped) -> None:
    """Cancel one pending operation and keep its storage alive until completion."""

    cancelled = bool(_kernel32.CancelIoEx(handle, ctypes.byref(overlapped)))
    cancel_error = 0 if cancelled else ctypes.get_last_error()
    transferred = wintypes.DWORD()
    drained = bool(
        _kernel32.GetOverlappedResult(
            handle,
            ctypes.byref(overlapped),
            ctypes.byref(transferred),
            True,
        )
    )
    if drained:
        return
    drain_error = ctypes.get_last_error()
    if drain_error in {
        _ERROR_OPERATION_ABORTED,
        _ERROR_BROKEN_PIPE,
        _ERROR_NO_DATA,
        _ERROR_PIPE_NOT_CONNECTED,
    }:
        return
    if not cancelled and cancel_error not in {0, _ERROR_NOT_FOUND}:
        raise SpatialPipeError("pipe-unavailable")
    raise SpatialPipeError("pipe-unavailable")


def _finish_overlapped(
    handle,
    overlapped,
    *,
    pending: bool,
    deadline: float | None,
) -> int:
    if pending:
        if deadline is None:
            wait_milliseconds = _INFINITE
        else:
            try:
                wait_milliseconds = _remaining_milliseconds(deadline)
            except BaseException:
                _cancel_and_drain_overlapped(handle, overlapped)
                raise
        wait_result = _kernel32.WaitForSingleObject(
            overlapped.hEvent,
            wait_milliseconds,
        )
        if wait_result == _WAIT_TIMEOUT:
            _cancel_and_drain_overlapped(handle, overlapped)
            raise SpatialPipeError("pipe-timeout")
        if wait_result != _WAIT_OBJECT_0:
            _cancel_and_drain_overlapped(handle, overlapped)
            raise SpatialPipeError("pipe-unavailable")
    transferred = wintypes.DWORD()
    if not _kernel32.GetOverlappedResult(
        handle,
        ctypes.byref(overlapped),
        ctypes.byref(transferred),
        False,
    ):
        raise _windows_error("pipe-unavailable")
    return int(transferred.value)


def _connect_pipe(handle, *, deadline: float | None = None) -> bool:
    event, overlapped = _new_overlapped()
    try:
        connected = bool(_kernel32.ConnectNamedPipe(handle, ctypes.byref(overlapped)))
        if connected:
            _finish_overlapped(
                handle,
                overlapped,
                pending=False,
                deadline=deadline,
            )
            return True
        error = ctypes.get_last_error()
        if error == _ERROR_PIPE_CONNECTED:
            return True
        if error != _ERROR_IO_PENDING:
            raise _windows_error("pipe-unavailable")
        _finish_overlapped(
            handle,
            overlapped,
            pending=True,
            deadline=deadline,
        )
        return True
    finally:
        _kernel32.CloseHandle(event)


def _read_once(handle, size: int, *, deadline: float) -> bytes:
    buffer = ctypes.create_string_buffer(size)
    event, overlapped = _new_overlapped()
    try:
        completed = bool(
            _kernel32.ReadFile(
                handle,
                buffer,
                size,
                None,
                ctypes.byref(overlapped),
            )
        )
        if not completed and ctypes.get_last_error() != _ERROR_IO_PENDING:
            raise _windows_error("pipe-unavailable")
        transferred = _finish_overlapped(
            handle,
            overlapped,
            pending=not completed,
            deadline=deadline,
        )
        if transferred <= 0:
            raise SpatialPipeError("pipe-unavailable")
        return bytes(buffer.raw[:transferred])
    finally:
        _kernel32.CloseHandle(event)


def _read_exact(handle, size: int, *, deadline: float) -> bytes:
    if size < 0:
        raise SpatialPipeError("pipe-unavailable")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = _read_once(handle, min(remaining, 64 * 1024), deadline=deadline)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_once(handle, value: bytes, *, deadline: float) -> int:
    buffer = ctypes.create_string_buffer(value)
    event, overlapped = _new_overlapped()
    try:
        completed = bool(
            _kernel32.WriteFile(
                handle,
                buffer,
                len(value),
                None,
                ctypes.byref(overlapped),
            )
        )
        if not completed and ctypes.get_last_error() != _ERROR_IO_PENDING:
            raise _windows_error("pipe-unavailable")
        transferred = _finish_overlapped(
            handle,
            overlapped,
            pending=not completed,
            deadline=deadline,
        )
        if transferred <= 0:
            raise SpatialPipeError("pipe-unavailable")
        return transferred
    finally:
        _kernel32.CloseHandle(event)


def _write_exact(handle, value: bytes, *, deadline: float) -> None:
    offset = 0
    while offset < len(value):
        offset += _write_once(
            handle,
            value[offset : offset + (64 * 1024)],
            deadline=deadline,
        )


def _read_framed(handle, *, limit: int, deadline: float, error_code: str) -> bytes:
    length = _LENGTH.unpack(_read_exact(handle, _LENGTH.size, deadline=deadline))[0]
    if length <= 0 or length > limit:
        raise SpatialPipeError(error_code)
    return _read_exact(handle, length, deadline=deadline)


def _write_framed(handle, value: bytes, *, limit: int, deadline: float) -> None:
    _write_exact(
        handle,
        pack_spatial_pipe_frame(value, limit=limit),
        deadline=deadline,
    )


def _assert_same_windows_session(handle) -> None:
    client_session = wintypes.DWORD()
    server_session = wintypes.DWORD()
    if (
        not _kernel32.GetNamedPipeClientSessionId(
            handle,
            ctypes.byref(client_session),
        )
        or not _kernel32.ProcessIdToSessionId(
            _kernel32.GetCurrentProcessId(),
            ctypes.byref(server_session),
        )
        or client_session.value != server_session.value
    ):
        raise SpatialPipeError("pipe-session-mismatch")


class WindowsSpatialNamedPipeServer:
    """One-instance local named-pipe server owned by the full-trust GUI."""

    def __init__(
        self,
        *,
        package_sid: str,
        request_handler: Callable[[SpatialPipeRequest], SpatialPipeResponse],
        response_secret: bytes,
        client_identity_verifier: Callable[[object], None] | None = None,
        fatal_error_handler: Callable[[BaseException], None] | None = None,
        pipe_name: str | None = None,
        io_timeout_seconds: float = 10.0,
    ):
        _require_windows()
        if not callable(request_handler):
            raise TypeError("request_handler must be callable")
        if fatal_error_handler is not None and not callable(fatal_error_handler):
            raise TypeError("fatal_error_handler must be callable")
        if not isinstance(response_secret, bytes) or len(response_secret) != 32:
            raise ValueError("response_secret must contain exactly 32 bytes")
        if not isinstance(io_timeout_seconds, (int, float)) or not (
            0.1 <= float(io_timeout_seconds) <= 30.0
        ):
            raise ValueError("io_timeout_seconds must be between 0.1 and 30")
        self.pipe_name = validate_windows_spatial_pipe_name(
            pipe_name or create_windows_spatial_pipe_name()
        )
        self._package_sid = package_sid
        self._request_handler = request_handler
        self._response_secret = response_secret
        self._fatal_error_handler = fatal_error_handler
        expected_user_sid = _current_user_sid_string()
        self._client_identity_verifier = client_identity_verifier or (
            lambda handle: verify_windows_spatial_pipe_client(
                handle,
                package_sid=package_sid,
                expected_user_sid=expected_user_sid,
            )
        )
        self._io_timeout_seconds = float(io_timeout_seconds)
        self._stop_requested = threading.Event()
        self._client_active = threading.Event()
        self._thread: threading.Thread | None = None
        self._handle = None
        self._lock = threading.Lock()
        self._startup_error: BaseException | None = None
        self.security_contract = {
            "pipePrefix": _PIPE_PREFIX,
            "rejectRemoteClients": True,
            "daclPrincipals": ("current-user", "SYSTEM", package_sid),
            "sessionScoped": True,
        }

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._handle = _create_pipe_handle(
                self.pipe_name,
                self._package_sid,
            )
            self._stop_requested.clear()
            self._startup_error = None
            self._thread = threading.Thread(
                target=self._run,
                name="GhostStudio-Spatial-Named-Pipe",
                daemon=True,
            )
            self._thread.start()

    def stop(self, *, drain_active: bool = False) -> None:
        self._stop_requested.set()
        with self._lock:
            handle = self._handle
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            if drain_active and self._client_active.is_set():
                thread.join(timeout=max(2.0, self._io_timeout_seconds + 0.5))
            if thread.is_alive() and handle and handle != _INVALID_HANDLE_VALUE:
                _kernel32.CancelIoEx(handle, None)
            thread.join(timeout=2.0)
        elif handle and handle != _INVALID_HANDLE_VALUE:
            _kernel32.CancelIoEx(handle, None)
        with self._lock:
            if self._thread is thread and (
                thread is None or not thread.is_alive()
            ):
                self._thread = None

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return bool(thread is not None and thread.is_alive())

    def _run(self) -> None:
        with self._lock:
            handle = self._handle
        try:
            while not self._stop_requested.is_set():
                try:
                    _connect_pipe(handle)
                except SpatialPipeError as exc:
                    if self._stop_requested.is_set():
                        return
                    raise
                self._client_active.set()
                try:
                    if self._stop_requested.is_set():
                        return
                    deadline = time.monotonic() + self._io_timeout_seconds
                    request = decode_spatial_pipe_request(
                        _read_framed(
                            handle,
                            limit=MAX_REQUEST_FRAME_BYTES,
                            deadline=deadline,
                            error_code="invalid-request-frame",
                        )
                    )
                    _assert_same_windows_session(handle)
                    self._client_identity_verifier(handle)
                    try:
                        response = self._request_handler(request)
                    except Exception:
                        response = SpatialPipeResponse(
                            status=500,
                            content_type="application/json",
                            body=b'{"status":"error","code":"spatial-request-failed"}',
                        )
                    encoded = encode_spatial_pipe_response(
                        response,
                        request=request,
                        secret=self._response_secret,
                    )
                    _write_framed(
                        handle,
                        encoded,
                        limit=MAX_RESPONSE_FRAME_BYTES,
                        deadline=deadline,
                    )
                    if _read_exact(
                        handle,
                        len(_RESPONSE_ACK),
                        deadline=deadline,
                    ) != _RESPONSE_ACK:
                        raise SpatialPipeError("invalid-response-frame")
                except SpatialPipeFatalError:
                    raise
                except SpatialPipeError:
                    if self._stop_requested.is_set():
                        return
                finally:
                    _kernel32.DisconnectNamedPipe(handle)
                    self._client_active.clear()
        except BaseException as exc:
            self._startup_error = exc
        finally:
            self._client_active.clear()
            if handle and handle != _INVALID_HANDLE_VALUE:
                _kernel32.CloseHandle(handle)
            with self._lock:
                self._handle = None
        if (
            isinstance(self._startup_error, SpatialPipeFatalError)
            and self._fatal_error_handler is not None
        ):
            try:
                self._fatal_error_handler(self._startup_error)
            except BaseException:
                pass


def _open_pipe_client(pipe_name: str, *, deadline: float):
    _require_windows()
    pipe_name = validate_windows_spatial_pipe_name(pipe_name)
    while True:
        wait_ms = _remaining_milliseconds(deadline)
        if _kernel32.WaitNamedPipeW(pipe_name, wait_ms):
            handle = _kernel32.CreateFileW(
                pipe_name,
                _PIPE_CLIENT_ACCESS,
                0,
                None,
                _OPEN_EXISTING,
                _FILE_FLAG_OVERLAPPED
                | _SECURITY_SQOS_PRESENT
                | _SECURITY_IDENTIFICATION,
                None,
            )
            if handle and handle != _INVALID_HANDLE_VALUE:
                return handle
            error = ctypes.get_last_error()
            if error not in {_ERROR_PIPE_BUSY, _ERROR_FILE_NOT_FOUND}:
                raise _windows_error("pipe-unavailable")
        else:
            error = ctypes.get_last_error()
            if error not in {
                _ERROR_PIPE_BUSY,
                _ERROR_FILE_NOT_FOUND,
                _ERROR_SEM_TIMEOUT,
            }:
                raise _windows_error("pipe-unavailable")
        if time.monotonic() >= deadline:
            raise SpatialPipeError("pipe-timeout")
        time.sleep(min(0.025, max(0.001, deadline - time.monotonic())))


def call_windows_spatial_pipe(
    pipe_name: str,
    *,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout_seconds: float = 8.0,
    expected_server_pid: int,
    response_secret: bytes,
) -> SpatialPipeResponse:
    """Perform one bounded request over the exact descriptor pipe."""

    _require_windows()
    if not isinstance(timeout_seconds, (int, float)) or not (
        0.1 <= float(timeout_seconds) <= 30.0
    ):
        raise ValueError("timeout_seconds must be between 0.1 and 30")
    encoded = encode_spatial_pipe_request(
        method=method,
        path=path,
        headers=headers,
        body=body,
    )
    request = decode_spatial_pipe_request(encoded)
    deadline = time.monotonic() + float(timeout_seconds)
    handle = _open_pipe_client(pipe_name, deadline=deadline)
    try:
        server_pid = wintypes.DWORD()
        if (
            not isinstance(expected_server_pid, int)
            or isinstance(expected_server_pid, bool)
            or expected_server_pid <= 0
            or not _kernel32.GetNamedPipeServerProcessId(
                handle,
                ctypes.byref(server_pid),
            )
            or server_pid.value != expected_server_pid
        ):
            raise SpatialPipeError("pipe-security-failed")
        _write_framed(
            handle,
            encoded,
            limit=MAX_REQUEST_FRAME_BYTES,
            deadline=deadline,
        )
        response = _read_framed(
            handle,
            limit=MAX_RESPONSE_FRAME_BYTES,
            deadline=deadline,
            error_code="invalid-response-frame",
        )
        decoded = decode_spatial_pipe_response(
            response,
            request=request,
            secret=response_secret,
        )
        _write_exact(handle, _RESPONSE_ACK, deadline=deadline)
        return decoded
    finally:
        _kernel32.CloseHandle(handle)


__all__ = [
    "MAX_REQUEST_BODY_BYTES",
    "MAX_RESPONSE_BODY_BYTES",
    "PIPE_REQUEST_SCHEMA",
    "PIPE_RESPONSE_SCHEMA",
    "SpatialPipeError",
    "SpatialPipeRequest",
    "SpatialPipeResponse",
    "WINDOWS_SPATIAL_TRANSPORT",
    "WindowsSpatialNamedPipeServer",
    "call_windows_spatial_pipe",
    "create_windows_spatial_pipe_name",
    "decode_spatial_pipe_request",
    "decode_spatial_pipe_response",
    "encode_spatial_pipe_request",
    "encode_spatial_pipe_response",
    "pack_spatial_pipe_frame",
    "unpack_spatial_pipe_frame",
    "validate_windows_spatial_pipe_name",
]
