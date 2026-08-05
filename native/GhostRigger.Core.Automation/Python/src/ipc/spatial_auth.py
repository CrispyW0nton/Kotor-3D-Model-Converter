"""HMAC authentication for the narrow Ghost Studio spatial IPC surface.

The legacy Ghostworks IPC routes predate MCP Studio and remain outside this
security boundary.  This module is intentionally framework-free so the GUI
bridge and the private stdio adapter share exactly one signing contract.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import importlib.util
import json
import os
import re
import secrets
import stat
import subprocess
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

AUTH_DOMAIN = "ghoststudio-spatial-hmac/v1"
HEADER_SESSION = "X-GhostStudio-Session"
HEADER_TIMESTAMP = "X-GhostStudio-Timestamp"
HEADER_NONCE = "X-GhostStudio-Nonce"
HEADER_SIGNATURE = "X-GhostStudio-Signature"
MAX_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 30
DEFAULT_REPLAY_CAPACITY = 4096
_WINDOWS_REPLACE_RETRY_SECONDS = 0.5
_WINDOWS_REPLACE_RETRY_INITIAL_DELAY_SECONDS = 0.01
_WINDOWS_REPLACE_RETRY_MAX_DELAY_SECONDS = 0.05
_WINDOWS_TRANSIENT_REPLACE_WINERRORS = frozenset({5, 32})
_WINDOWS_SESSION_OWNER_NAME = ".ghoststudio-session.owner"
_WINDOWS_SESSION_LEASE_BUSY_ERRORS = frozenset({32, 33})
SPATIAL_APP_CONTAINER_SID_ENV = (
    "GHOSTSTUDIO_SPATIAL_APP_CONTAINER_SID"
)
SPATIAL_TRANSPORT_ENV = "GHOSTSTUDIO_SPATIAL_TRANSPORT"
SPATIAL_SESSION_PATH_ENV = "GHOSTSTUDIO_SPATIAL_SESSION_PATH"
WINDOWS_SPATIAL_TRANSPORT = "windows-named-pipe-v1"
LOOPBACK_SPATIAL_TRANSPORT = "loopback-http"
SPATIAL_PROFILE_ANCHOR_SCHEMA = "ghoststudio-spatial-profile-anchor/v1"
SPATIAL_PROFILE_ADAPTER_ID = "ghoststudio"
SPATIAL_PROFILE_IDENTITY_DERIVATION = (
    "approval-sha256-base64url-userenv-v1"
)
_UNAPPROVED_PROFILE_ID = "0" * 64
_PROFILE_ANCHOR_EXPORTS = frozenset(
    {
        "SCHEMA",
        "ADAPTER_ID",
        "APPROVAL_ID",
        "TRANSPORT",
        "IDENTITY_DERIVATION",
    }
)
_LEGACY_SPATIAL_NETWORK_ENV_KEYS = frozenset(
    {
        "ghoststudio_spatial_base_url",
        "ghoststudio_spatial_host",
        "ghoststudio_spatial_port",
        "ghoststudio_spatial_session_url",
        "ghoststudio_spatial_url",
    }
)

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SIGNATURE_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_APP_CONTAINER_PACKAGE_SID_RE = re.compile(
    r"^S-1-15-2(?:-(?:0|[1-9]\d{0,9})){7}$"
)
_WINDOWS_PIPE_NAME_RE = re.compile(
    r"^\\\\\.\\pipe\\LOCAL\\GhostStudioSpatial-[A-Za-z0-9_-]{43}$"
)
_APPROVAL_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_APP_CONTAINER_MONIKER_RE = re.compile(
    r"^GhostMCPStudio\.[A-Za-z0-9_-]{43}$"
)


class SpatialAuthenticationError(ValueError):
    """A stable, non-secret authentication failure."""

    _MESSAGES = {
        "body-too-large": "Spatial request body exceeds the allowed size.",
        "expired-request": "Spatial request timestamp is outside the allowed window.",
        "expired-session": "Spatial authentication session has expired.",
        "invalid-nonce": "Spatial request nonce is invalid.",
        "invalid-app-container-sid": (
            "Spatial AppContainer identity is invalid."
        ),
        "invalid-session": "Spatial authentication session is invalid.",
        "invalid-session-descriptor": "Spatial session descriptor is invalid.",
        "invalid-signature": "Spatial request signature is invalid.",
        "invalid-spatial-transport": "Spatial IPC transport is invalid.",
        "invalid-spatial-profile-anchor": (
            "Spatial profile approval anchor is invalid."
        ),
        "invalid-spatial-profile-root": (
            "Spatial AppContainer profile root is invalid."
        ),
        "conflicting-spatial-environment": (
            "Reserved spatial environment is conflicting."
        ),
        "unapproved-spatial-profile": (
            "Spatial profile approval has not been embedded."
        ),
        "invalid-timestamp": "Spatial request timestamp is invalid.",
        "missing-credentials": "Spatial authentication credentials are missing.",
        "private-session-required": "Spatial session storage is not private.",
        "replay-capacity-exhausted": (
            "Spatial request replay protection is at capacity."
        ),
        "replayed-request": "Spatial request nonce has already been used.",
        "session-descriptor-unavailable": "Spatial session descriptor is unavailable.",
    }

    def __init__(self, code: str):
        self.code = code
        super().__init__(self._MESSAGES.get(code, "Spatial authentication failed."))


@dataclass(frozen=True)
class SpatialSessionCredentials:
    """One bounded GUI/adapter session secret.

    ``secret`` is excluded from repr so diagnostic output cannot disclose it.
    """

    session_id: str
    secret: bytes = field(repr=False)
    expires_at: int

    def __post_init__(self) -> None:
        if not _SESSION_RE.fullmatch(self.session_id):
            raise ValueError("session_id must be a 16-128 character safe token")
        if not isinstance(self.secret, bytes) or len(self.secret) != 32:
            raise ValueError("secret must contain exactly 32 bytes")
        if not isinstance(self.expires_at, int) or self.expires_at <= 0:
            raise ValueError("expires_at must be a positive Unix timestamp")

    @classmethod
    def create(
        cls,
        *,
        now: Callable[[], float] = time.time,
        ttl_seconds: int = 8 * 60 * 60,
    ) -> "SpatialSessionCredentials":
        if not isinstance(ttl_seconds, int) or ttl_seconds < 60:
            raise ValueError("ttl_seconds must be an integer of at least 60")
        issued_at = int(now())
        return cls(
            session_id=f"gst_{secrets.token_urlsafe(24)}",
            secret=secrets.token_bytes(32),
            expires_at=issued_at + ttl_seconds,
        )


@dataclass(frozen=True)
class SpatialProfileAnchor:
    schema: str
    adapter_id: str
    approval_id: str
    transport: str
    identity_derivation: str

    def __post_init__(self) -> None:
        if (
            self.schema != SPATIAL_PROFILE_ANCHOR_SCHEMA
            or self.adapter_id != SPATIAL_PROFILE_ADAPTER_ID
            or not _APPROVAL_ID_RE.fullmatch(self.approval_id)
            or self.transport != WINDOWS_SPATIAL_TRANSPORT
            or self.identity_derivation
            != SPATIAL_PROFILE_IDENTITY_DERIVATION
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-anchor"
            )


@dataclass(frozen=True)
class WindowsSpatialProfileIdentity:
    moniker: str
    package_sid: str
    profile_root: Path

    def __post_init__(self) -> None:
        if not _APP_CONTAINER_MONIKER_RE.fullmatch(self.moniker):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )
        validate_spatial_app_container_package_sid(self.package_sid)
        root = Path(self.profile_root)
        if not root.is_absolute() or root != _absolute_lexical_path(root):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )


@dataclass(frozen=True)
class SpatialServerBootstrap:
    anchor: SpatialProfileAnchor
    identity: WindowsSpatialProfileIdentity
    session_path: Path

    def __post_init__(self) -> None:
        expected_moniker = derive_windows_spatial_profile_moniker(
            self.anchor.approval_id
        )
        expected_session = spatial_session_path_for_profile(
            self.identity.profile_root
        )
        if (
            self.anchor.approval_id == _UNAPPROVED_PROFILE_ID
            or self.identity.moniker != expected_moniker
            or Path(self.session_path) != expected_session
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )

    @property
    def package_sid(self) -> str:
        return self.identity.package_sid

    @property
    def profile_root(self) -> Path:
        return self.identity.profile_root

    @property
    def transport(self) -> str:
        return self.anchor.transport


@dataclass(frozen=True)
class SpatialSessionDescriptor:
    credentials: SpatialSessionCredentials
    port: int | None
    created_at: int
    pid: int
    transport: str = LOOPBACK_SPATIAL_TRANSPORT
    pipe_name: str | None = None
    schema: str = "ghoststudio-spatial-session/v1"


@dataclass(frozen=True)
class VerifiedSpatialRequest:
    session_id: str
    timestamp: int
    nonce: str
    body_sha256: str


class WindowsSpatialSessionLease:
    """One process-lifetime ownership lease backed only by a Windows handle."""

    __slots__ = ("_close_handle", "_handle", "_lock")

    def __init__(
        self,
        handle: object,
        close_handle: Callable[[object], bool],
    ) -> None:
        self._handle = handle
        self._close_handle = close_handle
        self._lock = threading.Lock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._handle is None

    def close(self) -> None:
        with self._lock:
            handle = self._handle
            if handle is None:
                return
            if not self._close_handle(handle):
                raise SpatialAuthenticationError(
                    "private-session-required"
                )
            self._handle = None

    def __enter__(self) -> "WindowsSpatialSessionLease":
        if self.closed:
            raise RuntimeError("spatial session lease is closed")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> bool:
        self.close()
        return False

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def sha256_hex(body: bytes) -> str:
    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")
    return hashlib.sha256(body).hexdigest()


def validate_spatial_app_container_package_sid(value: object) -> str:
    if (
        not isinstance(value, str)
        or not _APP_CONTAINER_PACKAGE_SID_RE.fullmatch(value)
        or any(
            int(component, 10) > 0xFFFFFFFF
            for component in value.split("-")[4:]
        )
    ):
        raise SpatialAuthenticationError("invalid-app-container-sid")
    return value


def derive_windows_spatial_profile_moniker(approval_id: str) -> str:
    if not isinstance(approval_id, str) or not _APPROVAL_ID_RE.fullmatch(
        approval_id
    ):
        raise SpatialAuthenticationError("invalid-spatial-profile-anchor")
    encoded = base64.urlsafe_b64encode(
        bytes.fromhex(approval_id)
    ).decode("ascii").rstrip("=")
    moniker = f"GhostMCPStudio.{encoded}"
    if not _APP_CONTAINER_MONIKER_RE.fullmatch(moniker):
        raise SpatialAuthenticationError("invalid-spatial-profile-anchor")
    return moniker


def spatial_session_path_for_profile(profile_root: Path) -> Path:
    root = Path(profile_root)
    if not root.is_absolute():
        raise SpatialAuthenticationError("invalid-spatial-profile-root")
    root = _absolute_lexical_path(root)
    return (
        root
        / "MCPStudioState"
        / "GhostStudioSpatial"
        / "ghoststudio-session.json"
    )


def load_embedded_spatial_profile_anchor() -> SpatialProfileAnchor:
    module = None
    if __package__:
        try:
            module = importlib.import_module(
                f"{__package__}.spatial_profile_anchor"
            )
        except (ImportError, AttributeError):
            module = None
        except Exception as exc:
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-anchor"
            ) from exc
    if module is None:
        anchor_path = Path(__file__).with_name("spatial_profile_anchor.py")
        try:
            spec = importlib.util.spec_from_file_location(
                "_ghoststudio_embedded_spatial_profile_anchor",
                anchor_path,
            )
            if spec is None or spec.loader is None:
                raise SpatialAuthenticationError(
                    "invalid-spatial-profile-anchor"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except SpatialAuthenticationError:
            raise
        except Exception as exc:
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-anchor"
            ) from exc
    exported = {
        name: value
        for name, value in vars(module).items()
        if name.isupper()
    }
    if set(exported) != _PROFILE_ANCHOR_EXPORTS:
        raise SpatialAuthenticationError("invalid-spatial-profile-anchor")
    return SpatialProfileAnchor(
        schema=exported["SCHEMA"],
        adapter_id=exported["ADAPTER_ID"],
        approval_id=exported["APPROVAL_ID"],
        transport=exported["TRANSPORT"],
        identity_derivation=exported["IDENTITY_DERIVATION"],
    )


def _native_windows_spatial_profile(
    moniker: str,
) -> tuple[str, Path]:
    if os.name != "nt" or not _APP_CONTAINER_MONIKER_RE.fullmatch(moniker):
        raise SpatialAuthenticationError("invalid-spatial-profile-root")
    import ctypes
    from ctypes import wintypes

    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = (
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.LPVOID),
    )
    userenv.DeriveAppContainerSidFromAppContainerName.restype = wintypes.LONG
    userenv.GetAppContainerFolderPath.argtypes = (
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.LPVOID),
    )
    userenv.GetAppContainerFolderPath.restype = wintypes.LONG
    advapi32.ConvertSidToStringSidW.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    )
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.FreeSid.argtypes = (wintypes.LPVOID,)
    advapi32.FreeSid.restype = wintypes.LPVOID
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL
    ole32.CoTaskMemFree.argtypes = (wintypes.LPVOID,)
    ole32.CoTaskMemFree.restype = None

    sid_pointer = wintypes.LPVOID()
    sid_text_pointer = wintypes.LPWSTR()
    folder_pointer = wintypes.LPVOID()
    try:
        if (
            userenv.DeriveAppContainerSidFromAppContainerName(
                moniker,
                ctypes.byref(sid_pointer),
            )
            != 0
            or not sid_pointer.value
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )
        if not advapi32.ConvertSidToStringSidW(
            sid_pointer,
            ctypes.byref(sid_text_pointer),
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )
        package_sid = validate_spatial_app_container_package_sid(
            str(sid_text_pointer.value or "")
        )
        if (
            userenv.GetAppContainerFolderPath(
                package_sid,
                ctypes.byref(folder_pointer),
            )
            != 0
            or not folder_pointer.value
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )
        profile_root = _absolute_lexical_path(
            Path(ctypes.wstring_at(folder_pointer.value))
        )
        return package_sid, profile_root
    except (AttributeError, OSError, ValueError) as exc:
        raise SpatialAuthenticationError(
            "invalid-spatial-profile-root"
        ) from exc
    finally:
        if folder_pointer.value:
            ole32.CoTaskMemFree(folder_pointer)
        if sid_text_pointer:
            kernel32.LocalFree(
                ctypes.cast(sid_text_pointer, wintypes.HLOCAL)
            )
        if sid_pointer.value:
            advapi32.FreeSid(sid_pointer)


def _audit_windows_low_integrity_profile(path: Path) -> None:
    if os.name != "nt":
        raise SpatialAuthenticationError("invalid-spatial-profile-root")
    import ctypes
    from ctypes import wintypes

    class _AclSizeInformation(ctypes.Structure):
        _fields_ = (
            ("ace_count", wintypes.DWORD),
            ("acl_bytes_in_use", wintypes.DWORD),
            ("acl_bytes_free", wintypes.DWORD),
        )

    class _AceHeader(ctypes.Structure):
        _fields_ = (
            ("ace_type", wintypes.BYTE),
            ("ace_flags", wintypes.BYTE),
            ("ace_size", wintypes.WORD),
        )

    class _MandatoryLabelAce(ctypes.Structure):
        _fields_ = (
            ("header", _AceHeader),
            ("mask", wintypes.DWORD),
            ("sid_start", wintypes.DWORD),
        )

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32.GetNamedSecurityInfoW.argtypes = (
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.GetAclInformation.argtypes = (
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    advapi32.GetAclInformation.restype = wintypes.BOOL
    advapi32.GetAce.argtypes = (
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.GetAce.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    )
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL

    sacl = wintypes.LPVOID()
    descriptor = wintypes.LPVOID()

    def _reject() -> None:
        raise SpatialAuthenticationError("invalid-spatial-profile-root")

    result = advapi32.GetNamedSecurityInfoW(
        str(path),
        1,
        0x00000010,
        None,
        None,
        None,
        ctypes.byref(sacl),
        ctypes.byref(descriptor),
    )
    if result != 0 or not descriptor.value or not sacl.value:
        _reject()
    try:
        details = _AclSizeInformation()
        if not advapi32.GetAclInformation(
            sacl,
            ctypes.byref(details),
            ctypes.sizeof(details),
            2,
        ) or details.ace_count != 1:
            _reject()
        ace_pointer = wintypes.LPVOID()
        if not advapi32.GetAce(
            sacl,
            0,
            ctypes.byref(ace_pointer),
        ):
            _reject()
        ace = ctypes.cast(
            ace_pointer,
            ctypes.POINTER(_MandatoryLabelAce),
        ).contents
        sid_pointer = wintypes.LPVOID(
            int(ace_pointer.value) + _MandatoryLabelAce.sid_start.offset
        )
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(
            sid_pointer,
            ctypes.byref(sid_text),
        ):
            _reject()
        try:
            label_sid = str(sid_text.value or "")
        finally:
            kernel32.LocalFree(
                ctypes.cast(sid_text, wintypes.HLOCAL)
            )
        if (
            ace.header.ace_type != 0x11
            or ace.header.ace_flags != 0x03
            or ace.mask != 0x1
            or label_sid != "S-1-16-4096"
        ):
            _reject()
    finally:
        kernel32.LocalFree(descriptor)


def _same_windows_path(left: Path, right: Path) -> bool:
    return os.path.normcase(
        os.fspath(_absolute_lexical_path(left))
    ) == os.path.normcase(os.fspath(_absolute_lexical_path(right)))


def assert_spatial_bootstrap_environment(
    bootstrap: SpatialServerBootstrap,
    environ: Mapping[str, str] | None = None,
) -> None:
    values = os.environ if environ is None else environ
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = str(raw_key).casefold()
        if key in normalized and normalized[key] != raw_value:
            raise SpatialAuthenticationError(
                "conflicting-spatial-environment"
            )
        normalized[key] = raw_value
    if any(key in normalized for key in _LEGACY_SPATIAL_NETWORK_ENV_KEYS):
        raise SpatialAuthenticationError(
            "conflicting-spatial-environment"
        )
    expected = {
        SPATIAL_TRANSPORT_ENV.casefold(): bootstrap.transport,
        SPATIAL_APP_CONTAINER_SID_ENV.casefold(): bootstrap.package_sid,
    }
    for key, wanted in expected.items():
        if key in normalized and normalized[key] != wanted:
            raise SpatialAuthenticationError(
                "conflicting-spatial-environment"
            )
    session_key = SPATIAL_SESSION_PATH_ENV.casefold()
    if session_key in normalized:
        candidate = normalized[session_key]
        if not isinstance(candidate, str) or not Path(candidate).is_absolute():
            raise SpatialAuthenticationError(
                "conflicting-spatial-environment"
            )
        if not _same_windows_path(
            Path(candidate),
            bootstrap.session_path,
        ):
            raise SpatialAuthenticationError(
                "conflicting-spatial-environment"
            )


def resolve_windows_spatial_server_bootstrap(
    anchor: SpatialProfileAnchor,
    *,
    environ: Mapping[str, str] | None = None,
    native_profile_resolver: Callable[
        [str], tuple[str, Path]
    ] = _native_windows_spatial_profile,
    low_integrity_audit: Callable[
        [Path], None
    ] = _audit_windows_low_integrity_profile,
) -> SpatialServerBootstrap:
    if anchor.approval_id == _UNAPPROVED_PROFILE_ID:
        raise SpatialAuthenticationError("unapproved-spatial-profile")
    values = os.environ if environ is None else environ
    local_app_data_text = str(values.get("LOCALAPPDATA") or "").strip()
    if (
        not local_app_data_text
        or not Path(local_app_data_text).is_absolute()
    ):
        raise SpatialAuthenticationError("invalid-spatial-profile-root")
    local_app_data = _absolute_lexical_path(Path(local_app_data_text))
    moniker = derive_windows_spatial_profile_moniker(anchor.approval_id)
    package_sid, observed_root = native_profile_resolver(moniker)
    package_sid = validate_spatial_app_container_package_sid(package_sid)
    observed_root = _absolute_lexical_path(Path(observed_root))
    packages_root = _absolute_lexical_path(
        local_app_data / "Packages"
    )
    app_container_root = _absolute_lexical_path(packages_root / moniker)
    expected_root = _absolute_lexical_path(app_container_root / "AC")
    if not _same_windows_path(observed_root, expected_root):
        raise SpatialAuthenticationError("invalid-spatial-profile-root")
    for candidate in (packages_root, app_container_root, observed_root):
        try:
            details = candidate.lstat()
        except OSError as exc:
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            ) from exc
        if _is_link_or_reparse(details) or not stat.S_ISDIR(
            details.st_mode
        ):
            raise SpatialAuthenticationError(
                "invalid-spatial-profile-root"
            )
    low_integrity_audit(observed_root)
    identity = WindowsSpatialProfileIdentity(
        moniker=moniker,
        package_sid=package_sid,
        profile_root=observed_root,
    )
    bootstrap = SpatialServerBootstrap(
        anchor=anchor,
        identity=identity,
        session_path=spatial_session_path_for_profile(observed_root),
    )
    assert_spatial_bootstrap_environment(bootstrap, values)
    return bootstrap


def resolve_embedded_spatial_server_bootstrap(
    environ: Mapping[str, str] | None = None,
) -> SpatialServerBootstrap:
    return resolve_windows_spatial_server_bootstrap(
        load_embedded_spatial_profile_anchor(),
        environ=environ,
    )


def default_spatial_session_path(
    environ: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    app_container_root = _windows_app_container_profile_root(values)
    if app_container_root is not None:
        return spatial_session_path_for_profile(app_container_root)
    local_app_data = str(values.get("LOCALAPPDATA") or "").strip()
    root = (
        Path(local_app_data)
        if local_app_data and Path(local_app_data).is_absolute()
        else Path.home() / "AppData" / "Local"
    )
    return (
        root
        / "GhostMCPStudio"
        / "sessions"
        / "ghoststudio-session.json"
    )


def spatial_app_container_package_sid(
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return one explicitly supplied canonical AppContainer package SID."""

    values = os.environ if environ is None else environ
    if SPATIAL_APP_CONTAINER_SID_ENV not in values:
        return None
    candidate = values.get(SPATIAL_APP_CONTAINER_SID_ENV)
    return validate_spatial_app_container_package_sid(candidate)


def spatial_transport_marker(
    environ: Mapping[str, str] | None = None,
    *,
    required: bool = False,
) -> str | None:
    """Return the exact sealed Windows spatial transport marker."""

    values = os.environ if environ is None else environ
    if SPATIAL_TRANSPORT_ENV not in values:
        if required:
            raise SpatialAuthenticationError("invalid-spatial-transport")
        return None
    candidate = values.get(SPATIAL_TRANSPORT_ENV)
    if candidate != WINDOWS_SPATIAL_TRANSPORT:
        raise SpatialAuthenticationError("invalid-spatial-transport")
    return candidate


def _windows_app_container_profile_root(
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    package_sid = spatial_app_container_package_sid(environ)
    if package_sid is None or os.name != "nt":
        return None

    import ctypes
    from ctypes import wintypes

    folder = wintypes.LPVOID()
    try:
        userenv = ctypes.WinDLL("userenv", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        userenv.GetAppContainerFolderPath.argtypes = (
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPVOID),
        )
        userenv.GetAppContainerFolderPath.restype = wintypes.LONG
        ole32.CoTaskMemFree.argtypes = (wintypes.LPVOID,)
        ole32.CoTaskMemFree.restype = None
        result = userenv.GetAppContainerFolderPath(
            package_sid,
            ctypes.byref(folder),
        )
        if result != 0 or not folder.value:
            raise SpatialAuthenticationError(
                "private-session-required"
            )
        root = _absolute_lexical_path(
            Path(ctypes.wstring_at(folder.value))
        )
    except (AttributeError, OSError, ValueError) as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc
    finally:
        if folder.value:
            try:
                ole32.CoTaskMemFree(folder)
            except (NameError, OSError):
                pass

    try:
        details = root.lstat()
    except OSError as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc
    if _is_link_or_reparse(details) or not stat.S_ISDIR(details.st_mode):
        raise SpatialAuthenticationError("private-session-required")
    return root


def _absolute_lexical_path(path: Path) -> Path:
    """Return an absolute path without following links or reparse points."""

    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_reparse(details: os.stat_result) -> bool:
    if stat.S_ISLNK(details.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = int(getattr(details, "st_file_attributes", 0))
    return bool(reparse_flag and attributes & reparse_flag)


def _assert_no_link_components(
    path: Path,
    *,
    allow_missing: bool,
    error_code: str = "private-session-required",
    app_container_root: Path | None = None,
) -> None:
    """Reject linked ancestors before any caller resolves or creates a path."""

    candidate = _absolute_lexical_path(path)
    anchor = Path(candidate.anchor)
    current = anchor
    for component in candidate.parts[1:]:
        current /= component
        try:
            details = current.lstat()
        except PermissionError:
            reanchor_root = (
                _absolute_lexical_path(app_container_root)
                if app_container_root is not None
                else _windows_app_container_profile_root()
            )
            if reanchor_root is None:
                raise SpatialAuthenticationError(error_code) from None
            normalized_root = os.path.normcase(
                os.fspath(reanchor_root)
            )
            normalized_candidate = os.path.normcase(
                os.fspath(candidate)
            )
            try:
                common = os.path.commonpath(
                    (normalized_root, normalized_candidate)
                )
            except ValueError:
                raise SpatialAuthenticationError(error_code) from None
            if common != normalized_root:
                raise SpatialAuthenticationError(error_code) from None
            current = reanchor_root
            relative = Path(
                os.path.relpath(candidate, reanchor_root)
            )
            for relative_component in relative.parts:
                current /= relative_component
                try:
                    details = current.lstat()
                except FileNotFoundError:
                    if allow_missing:
                        continue
                    raise SpatialAuthenticationError(
                        error_code
                    ) from None
                except OSError:
                    raise SpatialAuthenticationError(
                        error_code
                    ) from None
                if _is_link_or_reparse(details):
                    raise SpatialAuthenticationError(error_code)
            return
        except FileNotFoundError:
            if allow_missing:
                continue
            raise SpatialAuthenticationError(error_code) from None
        if _is_link_or_reparse(details):
            raise SpatialAuthenticationError(error_code)


def _assert_regular_unlinked_path(path: Path) -> None:
    try:
        details = path.lstat()
    except FileNotFoundError as exc:
        raise SpatialAuthenticationError(
            "session-descriptor-unavailable"
        ) from exc
    if _is_link_or_reparse(details) or not stat.S_ISREG(details.st_mode):
        raise SpatialAuthenticationError("invalid-session-descriptor")


def _windows_final_path_key(value: str | os.PathLike[str]) -> str:
    text = os.fspath(value)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[8:]
    elif text.startswith("\\\\?\\"):
        text = text[4:]
    return os.path.normcase(os.path.normpath(os.path.abspath(text)))


def _assert_windows_spatial_session_owner_path(path: Path) -> None:
    try:
        details = path.lstat()
    except OSError as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc
    if (
        _is_link_or_reparse(details)
        or not stat.S_ISREG(details.st_mode)
        or int(getattr(details, "st_nlink", 0)) != 1
        or details.st_size != 0
    ):
        raise SpatialAuthenticationError("private-session-required")


def _audit_windows_spatial_session_lease_handle(
    handle: object,
    expected_path: Path,
    *,
    kernel32,
) -> None:
    import ctypes
    from ctypes import wintypes

    class _FileTime(ctypes.Structure):
        _fields_ = (
            ("low", wintypes.DWORD),
            ("high", wintypes.DWORD),
        )

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("attributes", wintypes.DWORD),
            ("creation_time", _FileTime),
            ("last_access_time", _FileTime),
            ("last_write_time", _FileTime),
            ("volume_serial_number", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        )

    kernel32.GetFileType.argtypes = (wintypes.HANDLE,)
    kernel32.GetFileType.restype = wintypes.DWORD
    kernel32.GetFileInformationByHandle.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    )
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFinalPathNameByHandleW.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.GetHandleInformation.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.GetHandleInformation.restype = wintypes.BOOL

    information = _ByHandleFileInformation()
    handle_flags = wintypes.DWORD()
    if (
        kernel32.GetFileType(handle) != 0x0001
        or not kernel32.GetFileInformationByHandle(
            handle,
            ctypes.byref(information),
        )
        or not kernel32.GetHandleInformation(
            handle,
            ctypes.byref(handle_flags),
        )
    ):
        raise SpatialAuthenticationError("private-session-required")
    size = (
        int(information.file_size_high) << 32
    ) | int(information.file_size_low)
    if (
        int(information.attributes) & (0x0010 | 0x0400)
        or information.number_of_links != 1
        or size != 0
        or handle_flags.value & 0x00000001
    ):
        raise SpatialAuthenticationError("private-session-required")

    required = int(
        kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
    )
    if required <= 0:
        raise SpatialAuthenticationError("private-session-required")
    buffer = ctypes.create_unicode_buffer(required + 1)
    length = int(
        kernel32.GetFinalPathNameByHandleW(
            handle,
            buffer,
            len(buffer),
            0,
        )
    )
    if (
        length <= 0
        or length >= len(buffer)
        or _windows_final_path_key(buffer.value)
        != _windows_final_path_key(expected_path)
    ):
        raise SpatialAuthenticationError("private-session-required")
    _assert_windows_spatial_session_owner_path(expected_path)


def _windows_current_user_sid() -> str:
    """Return the current process token's canonical Windows user SID."""

    import ctypes
    from ctypes import wintypes

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = (
            ("sid", wintypes.LPVOID),
            ("attributes", wintypes.DWORD),
        )

    class _TokenUser(ctypes.Structure):
        _fields_ = (("user", _SidAndAttributes),)

    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc

    advapi32.OpenProcessToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    )
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.IsValidSid.argtypes = (wintypes.LPVOID,)
    advapi32.IsValidSid.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL

    def _reject(error: int | None = None) -> None:
        failure = SpatialAuthenticationError(
            "private-session-required"
        )
        if error:
            failure.__cause__ = ctypes.WinError(error)
        raise failure

    token = wintypes.HANDLE()
    ctypes.set_last_error(0)
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        0x0008,
        ctypes.byref(token),
    ):
        _reject(ctypes.get_last_error())
    try:
        token_size = wintypes.DWORD()
        ctypes.set_last_error(0)
        if advapi32.GetTokenInformation(
            token,
            1,
            None,
            0,
            ctypes.byref(token_size),
        ) or ctypes.get_last_error() != 122:
            _reject(ctypes.get_last_error())
        if token_size.value <= 0:
            _reject()
        token_buffer = ctypes.create_string_buffer(token_size.value)
        ctypes.set_last_error(0)
        if not advapi32.GetTokenInformation(
            token,
            1,
            token_buffer,
            token_size,
            ctypes.byref(token_size),
        ):
            _reject(ctypes.get_last_error())
        token_user = ctypes.cast(
            token_buffer,
            ctypes.POINTER(_TokenUser),
        ).contents
        if not advapi32.IsValidSid(token_user.user.sid):
            _reject()
        sid_text_pointer = wintypes.LPVOID()
        ctypes.set_last_error(0)
        if not advapi32.ConvertSidToStringSidW(
            token_user.user.sid,
            ctypes.byref(sid_text_pointer),
        ):
            _reject(ctypes.get_last_error())
        try:
            sid_text = ctypes.wstring_at(sid_text_pointer.value)
            if not sid_text.startswith("S-1-"):
                _reject()
            return sid_text
        finally:
            kernel32.LocalFree(sid_text_pointer)
    finally:
        kernel32.CloseHandle(token)


def _audit_windows_private_security(
    path: Path,
    is_directory: bool,
    *,
    package_sid: str | None,
) -> None:
    """Audit the protected session ACL without creating a child process."""

    import ctypes
    from ctypes import wintypes

    class _AclSizeInformation(ctypes.Structure):
        _fields_ = (
            ("ace_count", wintypes.DWORD),
            ("acl_bytes_in_use", wintypes.DWORD),
            ("acl_bytes_free", wintypes.DWORD),
        )

    class _AceHeader(ctypes.Structure):
        _fields_ = (
            ("ace_type", wintypes.BYTE),
            ("ace_flags", wintypes.BYTE),
            ("ace_size", wintypes.WORD),
        )

    class _AccessAllowedAce(ctypes.Structure):
        _fields_ = (
            ("header", _AceHeader),
            ("mask", wintypes.DWORD),
            ("sid_start", wintypes.DWORD),
        )

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = (
            ("sid", wintypes.LPVOID),
            ("attributes", wintypes.DWORD),
        )

    class _TokenUser(ctypes.Structure):
        _fields_ = (("user", _SidAndAttributes),)

    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc

    advapi32.GetNamedSecurityInfoW.argtypes = (
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi32.GetSecurityDescriptorControl.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.WORD),
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi32.GetAclInformation.argtypes = (
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    advapi32.GetAclInformation.restype = wintypes.BOOL
    advapi32.GetAce.argtypes = (
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.GetAce.restype = wintypes.BOOL
    advapi32.IsValidSid.argtypes = (wintypes.LPVOID,)
    advapi32.IsValidSid.restype = wintypes.BOOL
    advapi32.GetLengthSid.argtypes = (wintypes.LPVOID,)
    advapi32.GetLengthSid.restype = wintypes.DWORD
    advapi32.ConvertSidToStringSidW.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPVOID),
    )
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    )
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL

    def _reject() -> None:
        raise SpatialAuthenticationError("private-session-required")

    def _sid_text(sid: int | None) -> str:
        if not sid or not advapi32.IsValidSid(sid):
            _reject()
        text_pointer = wintypes.LPVOID()
        if not advapi32.ConvertSidToStringSidW(
            sid,
            ctypes.byref(text_pointer),
        ):
            _reject()
        try:
            return ctypes.wstring_at(text_pointer.value)
        finally:
            kernel32.LocalFree(text_pointer)

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        0x0008,
        ctypes.byref(token),
    ):
        _reject()
    try:
        token_size = wintypes.DWORD()
        advapi32.GetTokenInformation(
            token,
            1,
            None,
            0,
            ctypes.byref(token_size),
        )
        if token_size.value <= 0:
            _reject()
        token_buffer = ctypes.create_string_buffer(token_size.value)
        if not advapi32.GetTokenInformation(
            token,
            1,
            token_buffer,
            token_size,
            ctypes.byref(token_size),
        ):
            _reject()
        token_user = ctypes.cast(
            token_buffer,
            ctypes.POINTER(_TokenUser),
        ).contents
        current_user_sid = _sid_text(token_user.user.sid)
    finally:
        kernel32.CloseHandle(token)

    owner = wintypes.LPVOID()
    dacl = wintypes.LPVOID()
    descriptor = wintypes.LPVOID()
    result = advapi32.GetNamedSecurityInfoW(
        str(path),
        1,
        0x00000001 | 0x00000004,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if result != 0 or not descriptor.value:
        _reject()
    try:
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not advapi32.GetSecurityDescriptorControl(
            descriptor,
            ctypes.byref(control),
            ctypes.byref(revision),
        ):
            _reject()
        if (
            not control.value & 0x0004
            or not control.value & 0x1000
            or not dacl.value
            or _sid_text(owner.value) != current_user_sid
        ):
            _reject()

        expected_flags = 0x03 if is_directory else 0x00
        expected = {
            current_user_sid: (0x001F01FF, expected_flags),
            "S-1-5-18": (0x001F01FF, expected_flags),
        }
        if package_sid is not None:
            expected[package_sid] = (
                0x001200A9 if is_directory else 0x00120089,
                expected_flags,
            )

        acl_details = _AclSizeInformation()
        if not advapi32.GetAclInformation(
            dacl,
            ctypes.byref(acl_details),
            ctypes.sizeof(acl_details),
            2,
        ):
            _reject()
        if acl_details.ace_count != len(expected):
            _reject()

        seen: set[str] = set()
        sid_offset = _AccessAllowedAce.sid_start.offset
        for index in range(acl_details.ace_count):
            ace_pointer = wintypes.LPVOID()
            if not advapi32.GetAce(
                dacl,
                index,
                ctypes.byref(ace_pointer),
            ):
                _reject()
            header = ctypes.cast(
                ace_pointer,
                ctypes.POINTER(_AceHeader),
            ).contents
            if header.ace_type != 0 or header.ace_flags != expected_flags:
                _reject()
            rule = ctypes.cast(
                ace_pointer,
                ctypes.POINTER(_AccessAllowedAce),
            ).contents
            sid_pointer = ace_pointer.value + sid_offset
            if (
                not advapi32.IsValidSid(sid_pointer)
                or sid_offset + advapi32.GetLengthSid(sid_pointer)
                > header.ace_size
            ):
                _reject()
            sid = _sid_text(sid_pointer)
            wanted = expected.get(sid)
            if (
                wanted is None
                or sid in seen
                or rule.mask != wanted[0]
            ):
                _reject()
            seen.add(sid)
        if seen != set(expected):
            _reject()
    finally:
        kernel32.LocalFree(descriptor)


def _windows_private_security(
    path: Path,
    is_directory: bool,
    *,
    apply: bool,
    package_sid: str | None = None,
) -> None:
    if package_sid is None:
        package_sid = spatial_app_container_package_sid()
    else:
        package_sid = validate_spatial_app_container_package_sid(
            package_sid
        )
    if not apply:
        _audit_windows_private_security(
            path,
            is_directory,
            package_sid=package_sid,
        )
        return
    system_root = str(
        os.environ.get("SystemRoot") or os.environ.get("WINDIR") or ""
    ).strip()
    powershell = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not system_root or not powershell.is_file():
        raise SpatialAuthenticationError("private-session-required")
    encoded_path = base64.b64encode(str(path).encode("utf-8")).decode("ascii")
    script = "\n".join(
        (
            "$ErrorActionPreference='Stop'",
            f"$path=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_path}'))",
            "$current=[Security.Principal.WindowsIdentity]::GetCurrent().User",
            "$system=New-Object Security.Principal.SecurityIdentifier('S-1-5-18')",
            f"$packageText=$env:{SPATIAL_APP_CONTAINER_SID_ENV}",
            "$package=$null",
            "if($packageText){",
            "  $package=New-Object Security.Principal.SecurityIdentifier($packageText)",
            "}",
            f"$isDirectory=${str(bool(is_directory)).lower()}",
            f"$apply=${str(bool(apply)).lower()}",
            "if($apply){",
            "  if($isDirectory){",
            "    $acl=New-Object Security.AccessControl.DirectorySecurity",
            "    $packageAce=if($package){'(A;OICI;0x1200A9;;;'+$package.Value+')'}else{''}",
            "    $sddl='O:'+$current.Value+'D:P(A;OICI;FA;;;'+$current.Value+')(A;OICI;FA;;;SY)'+$packageAce",
            "  }else{",
            "    $acl=New-Object Security.AccessControl.FileSecurity",
            "    $packageAce=if($package){'(A;;0x120089;;;'+$package.Value+')'}else{''}",
            "    $sddl='O:'+$current.Value+'D:P(A;;FA;;;'+$current.Value+')(A;;FA;;;SY)'+$packageAce",
            "  }",
            "  $sections=[Security.AccessControl.AccessControlSections]::Owner -bor [Security.AccessControl.AccessControlSections]::Access",
            "  $acl.SetSecurityDescriptorSddlForm($sddl,$sections)",
            "  if($isDirectory){",
            "    $target=New-Object IO.DirectoryInfo($path)",
            "  }else{",
            "    $target=New-Object IO.FileInfo($path)",
            "  }",
            "  $target.SetAccessControl($acl)",
            "}",
            "$observed=Get-Acl -LiteralPath $path",
            "$owner=([Security.Principal.NTAccount]$observed.Owner).Translate([Security.Principal.SecurityIdentifier]).Value",
            "if($owner -ne $current.Value){exit 31}",
            "if(-not $observed.AreAccessRulesProtected){exit 32}",
            "$inheritance=if($isDirectory){3}else{0}",
            "$expected=@{}",
            "$expected[$current.Value]=[pscustomobject]@{rights=[int64]0x1F01FF;inheritance=$inheritance}",
            "$expected[$system.Value]=[pscustomobject]@{rights=[int64]0x1F01FF;inheritance=$inheritance}",
            "if($package){",
            "  $packageRights=if($isDirectory){[int64]0x1200A9}else{[int64]0x120089}",
            "  $expected[$package.Value]=[pscustomobject]@{rights=$packageRights;inheritance=$inheritance}",
            "}",
            "$rules=@($observed.Access)",
            "if($rules.Count -ne $expected.Count){exit 33}",
            "$seen=@{}",
            "foreach($rule in $observed.Access){",
            "  if($rule.IdentityReference -is [Security.Principal.SecurityIdentifier]){",
            "    $sid=$rule.IdentityReference.Value",
            "  }else{",
            "    $sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value",
            "  }",
            "  if(-not $expected.ContainsKey($sid) -or $seen.ContainsKey($sid)){exit 33}",
            "  $seen[$sid]=$true",
            "  if($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow){exit 34}",
            "  $wanted=$expected[$sid]",
            "  if([int64]$rule.FileSystemRights -ne $wanted.rights){exit 35}",
            "  if([int]$rule.InheritanceFlags -ne $wanted.inheritance){exit 36}",
            "  if([int]$rule.PropagationFlags -ne 0 -or $rule.IsInherited){exit 37}",
            "}",
            "if($seen.Count -ne $expected.Count){exit 38}",
        )
    )
    encoded_script = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    windows_module_root = (
        Path(system_root)
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "Modules"
    )
    helper_environment = {
        "SystemRoot": system_root,
        "WINDIR": system_root,
        "PATH": f"{Path(system_root) / 'System32'};{system_root}",
        "PSModulePath": str(windows_module_root),
    }
    for name in ("TEMP", "TMP"):
        value = str(os.environ.get(name) or "").strip()
        if value and Path(value).is_absolute():
            helper_environment[name] = value
    if package_sid is not None:
        helper_environment[SPATIAL_APP_CONTAINER_SID_ENV] = (
            package_sid
        )
    try:
        completed = subprocess.run(
            [
                str(powershell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded_script,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=helper_environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SpatialAuthenticationError("private-session-required") from exc
    if completed.returncode != 0:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from RuntimeError(
            "private ACL helper failed with exit code "
            f"{completed.returncode}"
        )
    _audit_windows_private_security(
        path,
        is_directory,
        package_sid=package_sid,
    )


def _private_security(
    path: Path,
    is_directory: bool,
    *,
    apply: bool,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> None:
    _assert_no_link_components(
        path.parent,
        allow_missing=False,
        app_container_root=app_container_root,
    )
    details = path.lstat()
    expected = stat.S_ISDIR(details.st_mode) if is_directory else stat.S_ISREG(details.st_mode)
    if _is_link_or_reparse(details) or not expected:
        raise SpatialAuthenticationError("private-session-required")
    if os.name == "nt":
        resolved = _absolute_lexical_path(path)
        _windows_private_security(
            resolved,
            is_directory,
            apply=apply,
            package_sid=package_sid,
        )
        return
    resolved = path.resolve(strict=True)
    if apply:
        resolved.chmod(0o700 if is_directory else 0o600)
        details = resolved.stat()
    if details.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SpatialAuthenticationError("private-session-required")
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise SpatialAuthenticationError("private-session-required")


def prepare_private_spatial_directory(
    path: str | os.PathLike[str],
    *,
    security_hook: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> Path:
    """Create and verify a private directory without following path links."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("private spatial directory path must be absolute")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(
        target,
        allow_missing=True,
        app_container_root=app_container_root,
    )
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    _assert_no_link_components(
        target,
        allow_missing=False,
        app_container_root=app_container_root,
    )
    details = target.lstat()
    if _is_link_or_reparse(details) or not stat.S_ISDIR(details.st_mode):
        raise SpatialAuthenticationError("private-session-required")
    security = security_hook or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=True,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    )
    security(target, True)
    return target


def secure_private_spatial_artifact(
    path: str | os.PathLike[str],
    *,
    security_hook: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> Path:
    """Apply and verify private access on one existing regular artifact."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("private spatial artifact path must be absolute")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(
        target.parent,
        allow_missing=False,
        app_container_root=app_container_root,
    )
    _assert_regular_unlinked_path(target)
    security = security_hook or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=True,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    )
    security(target, False)
    return target


def acquire_windows_spatial_session_lease(
    session_path: str | os.PathLike[str],
    *,
    package_sid: str,
    app_container_root: Path,
) -> WindowsSpatialSessionLease | None:
    """Acquire the sole Windows owner handle for one spatial session path."""

    if os.name != "nt":
        raise SpatialAuthenticationError("private-session-required")

    import ctypes
    from ctypes import wintypes

    resolved_package_sid = validate_spatial_app_container_package_sid(
        package_sid
    )
    target = Path(session_path).expanduser()
    root = Path(app_container_root).expanduser()
    if not target.is_absolute() or not root.is_absolute():
        raise SpatialAuthenticationError("private-session-required")
    target = _absolute_lexical_path(target)
    root = _absolute_lexical_path(root)
    parent = target.parent
    try:
        normalized_root = os.path.normcase(os.fspath(root))
        normalized_parent = os.path.normcase(os.fspath(parent))
        if os.path.commonpath(
            (normalized_root, normalized_parent)
        ) != normalized_root:
            raise SpatialAuthenticationError(
                "private-session-required"
            )
        _assert_no_link_components(
            root,
            allow_missing=False,
            app_container_root=root,
        )
        root_details = root.lstat()
        if _is_link_or_reparse(root_details) or not stat.S_ISDIR(
            root_details.st_mode
        ):
            raise SpatialAuthenticationError(
                "private-session-required"
            )
        _assert_no_link_components(
            parent,
            allow_missing=False,
            app_container_root=root,
        )
        parent_details = parent.lstat()
        if _is_link_or_reparse(parent_details) or not stat.S_ISDIR(
            parent_details.st_mode
        ):
            raise SpatialAuthenticationError(
                "private-session-required"
            )
        _private_security(
            parent,
            True,
            apply=False,
            package_sid=resolved_package_sid,
            app_container_root=root,
        )
    except SpatialAuthenticationError:
        raise
    except (OSError, ValueError) as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc

    owner_path = parent / _WINDOWS_SESSION_OWNER_NAME
    try:
        _assert_windows_spatial_session_owner_path(owner_path)
    except SpatialAuthenticationError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
    else:
        _audit_windows_private_security(
            owner_path,
            False,
            package_sid=None,
        )

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = (
            ("length", wintypes.DWORD),
            ("security_descriptor", wintypes.LPVOID),
            ("inherit_handle", wintypes.BOOL),
        )

    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise SpatialAuthenticationError(
            "private-session-required"
        ) from exc
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        wintypes.BOOL
    )
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_SecurityAttributes),
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
    kernel32.LocalFree.restype = wintypes.HLOCAL

    current_user_sid = _windows_current_user_sid()
    security_descriptor = wintypes.LPVOID()
    security_descriptor_size = wintypes.DWORD()
    owner_sddl = (
        f"O:{current_user_sid}"
        f"D:P(A;;FA;;;{current_user_sid})(A;;FA;;;SY)"
    )
    ctypes.set_last_error(0)
    if (
        not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            owner_sddl,
            1,
            ctypes.byref(security_descriptor),
            ctypes.byref(security_descriptor_size),
        )
        or not security_descriptor.value
    ):
        conversion_error = ctypes.get_last_error()
        if security_descriptor.value:
            kernel32.LocalFree(security_descriptor)
        failure = SpatialAuthenticationError(
            "private-session-required"
        )
        if conversion_error:
            failure.__cause__ = ctypes.WinError(conversion_error)
        raise failure
    attributes = _SecurityAttributes(
        ctypes.sizeof(_SecurityAttributes),
        security_descriptor.value,
        False,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    handle = None
    try:
        ctypes.set_last_error(0)
        handle = kernel32.CreateFileW(
            str(owner_path),
            0x80000000 | 0x40000000,
            0x00000001,
            ctypes.byref(attributes),
            4,
            0x00000080 | 0x00200000,
            None,
        )
        open_error = ctypes.get_last_error()
    finally:
        free_result = kernel32.LocalFree(security_descriptor)
    if free_result:
        if handle and handle != invalid_handle:
            kernel32.CloseHandle(handle)
        raise SpatialAuthenticationError(
            "private-session-required"
        )
    if not handle or handle == invalid_handle:
        if open_error in _WINDOWS_SESSION_LEASE_BUSY_ERRORS:
            return None
        failure = SpatialAuthenticationError(
            "private-session-required"
        )
        failure.__cause__ = ctypes.WinError(open_error)
        raise failure

    def _close_handle(value: object) -> bool:
        return bool(kernel32.CloseHandle(value))

    lease = WindowsSpatialSessionLease(handle, _close_handle)
    try:
        if not kernel32.SetHandleInformation(
            handle,
            0x00000001,
            0,
        ):
            raise SpatialAuthenticationError(
                "private-session-required"
            )
        _audit_windows_spatial_session_lease_handle(
            handle,
            owner_path,
            kernel32=kernel32,
        )
        _audit_windows_private_security(
            owner_path,
            False,
            package_sid=None,
        )
        _audit_windows_spatial_session_lease_handle(
            handle,
            owner_path,
            kernel32=kernel32,
        )
        return lease
    except BaseException:
        lease.close()
        raise


def write_private_spatial_artifact(
    path: str | os.PathLike[str],
    content: bytes,
    *,
    security_hook: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> Path:
    """Exclusively create, flush, and secure one private spatial artifact."""

    if not isinstance(content, bytes):
        raise TypeError("private spatial artifact content must be bytes")
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("private spatial artifact path must be absolute")
    target = _absolute_lexical_path(target)
    parent = prepare_private_spatial_directory(
        target.parent,
        security_hook=security_hook,
        package_sid=package_sid,
        app_container_root=app_container_root,
    )
    if target.parent != parent:
        raise SpatialAuthenticationError("private-session-required")

    descriptor_fd = -1
    created = False
    try:
        descriptor_fd = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        created = True
        with os.fdopen(descriptor_fd, "wb", closefd=True) as stream:
            descriptor_fd = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        secure_private_spatial_artifact(
            target,
            security_hook=security_hook,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    except Exception:
        if descriptor_fd >= 0:
            os.close(descriptor_fd)
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return target


def _replace_private_spatial_artifact(
    temporary: Path,
    target: Path,
    *,
    app_container_root: Path | None,
) -> None:
    """Atomically replace one artifact across short Windows reader leases."""

    deadline = time.monotonic() + _WINDOWS_REPLACE_RETRY_SECONDS
    delay = _WINDOWS_REPLACE_RETRY_INITIAL_DELAY_SECONDS
    while True:
        try:
            os.replace(temporary, target)
            return
        except OSError as exc:
            if (
                os.name != "nt"
                or getattr(exc, "winerror", None)
                not in _WINDOWS_TRANSIENT_REPLACE_WINERRORS
                or time.monotonic() >= deadline
            ):
                raise
            _assert_no_link_components(
                target.parent,
                allow_missing=False,
                app_container_root=app_container_root,
            )
            parent_details = target.parent.lstat()
            if _is_link_or_reparse(parent_details) or not stat.S_ISDIR(
                parent_details.st_mode
            ):
                raise SpatialAuthenticationError(
                    "private-session-required"
                ) from exc
            _assert_regular_unlinked_path(target)
            _assert_regular_unlinked_path(temporary)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(delay, remaining))
            delay = min(
                delay * 2,
                _WINDOWS_REPLACE_RETRY_MAX_DELAY_SECONDS,
            )


def publish_spatial_session_descriptor(
    path: str | os.PathLike[str],
    *,
    port: int | None = None,
    pipe_name: str | None = None,
    transport: str | None = None,
    credentials: SpatialSessionCredentials | None = None,
    now: Callable[[], float] = time.time,
    ttl_seconds: int = 8 * 60 * 60,
    security_hook: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> SpatialSessionDescriptor:
    """Atomically publish one private spatial session descriptor."""

    resolved_transport = (
        str(transport)
        if transport is not None
        else (
            WINDOWS_SPATIAL_TRANSPORT
            if pipe_name is not None
            else LOOPBACK_SPATIAL_TRANSPORT
        )
    )
    if resolved_transport == WINDOWS_SPATIAL_TRANSPORT:
        if package_sid is None:
            spatial_transport_marker(required=True)
            package_sid = spatial_app_container_package_sid()
        if package_sid is None:
            raise SpatialAuthenticationError("invalid-app-container-sid")
        package_sid = validate_spatial_app_container_package_sid(
            package_sid
        )
        if (
            port is not None
            or not isinstance(pipe_name, str)
            or not _WINDOWS_PIPE_NAME_RE.fullmatch(pipe_name)
        ):
            raise ValueError("pipe_name must be one strict local spatial pipe")
        schema = "ghoststudio-spatial-session/v2"
    elif resolved_transport == LOOPBACK_SPATIAL_TRANSPORT:
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not (1 <= port <= 65535)
            or pipe_name is not None
        ):
            raise ValueError("port must be between 1 and 65535")
        schema = "ghoststudio-spatial-session/v1"
    else:
        raise SpatialAuthenticationError("invalid-spatial-transport")
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("spatial session path must be absolute")
    target = _absolute_lexical_path(target)
    parent = target.parent
    _assert_no_link_components(
        parent,
        allow_missing=True,
        app_container_root=app_container_root,
    )
    try:
        _assert_regular_unlinked_path(target)
    except SpatialAuthenticationError as exc:
        if exc.code != "session-descriptor-unavailable":
            raise
    parent = prepare_private_spatial_directory(
        parent,
        security_hook=security_hook,
        package_sid=package_sid,
        app_container_root=app_container_root,
    )

    created_at = int(now())
    session_credentials = credentials or SpatialSessionCredentials.create(
        now=lambda: created_at, ttl_seconds=ttl_seconds
    )
    if session_credentials.expires_at <= created_at:
        raise SpatialAuthenticationError("expired-session")
    descriptor = SpatialSessionDescriptor(
        credentials=session_credentials,
        port=port,
        created_at=created_at,
        pid=os.getpid(),
        transport=resolved_transport,
        pipe_name=pipe_name,
        schema=schema,
    )
    encoded_secret = base64.urlsafe_b64encode(session_credentials.secret).decode(
        "ascii"
    ).rstrip("=")
    payload: dict[str, object] = {
        "schema": descriptor.schema,
        "sessionId": session_credentials.session_id,
        "secret": encoded_secret,
        "createdAt": created_at,
        "expiresAt": session_credentials.expires_at,
        "pid": descriptor.pid,
    }
    if resolved_transport == WINDOWS_SPATIAL_TRANSPORT:
        payload["transport"] = resolved_transport
        payload["pipeName"] = pipe_name
    else:
        payload["port"] = port
    serialized = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(serialized) >= 4096:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    temporary = parent / (
        f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    descriptor_fd = -1
    try:
        descriptor_fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor_fd, "wb", closefd=True) as stream:
            descriptor_fd = -1
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        secure_private_spatial_artifact(
            temporary,
            security_hook=security_hook,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
        _replace_private_spatial_artifact(
            temporary,
            target,
            app_container_root=app_container_root,
        )
        _assert_regular_unlinked_path(target)
        secure_private_spatial_artifact(
            target,
            security_hook=security_hook,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    except Exception:
        if descriptor_fd >= 0:
            os.close(descriptor_fd)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return descriptor


def remove_spatial_session_descriptor(
    path: str | os.PathLike[str],
    *,
    session_id: str,
    security_audit: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> bool:
    """Remove a descriptor only when the current file belongs to the caller."""

    if not _SESSION_RE.fullmatch(str(session_id or "")):
        raise ValueError("session_id must be a 16-128 character safe token")
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise SpatialAuthenticationError("invalid-session-descriptor")
    target = _absolute_lexical_path(target)
    parent = target.parent
    _assert_no_link_components(
        parent,
        allow_missing=True,
        app_container_root=app_container_root,
    )
    try:
        parent_details = parent.lstat()
    except FileNotFoundError:
        return False
    if _is_link_or_reparse(parent_details) or not stat.S_ISDIR(parent_details.st_mode):
        raise SpatialAuthenticationError("private-session-required")
    _assert_no_link_components(
        parent,
        allow_missing=False,
        app_container_root=app_container_root,
    )
    try:
        _assert_regular_unlinked_path(target)
    except SpatialAuthenticationError as exc:
        if exc.code == "session-descriptor-unavailable":
            return False
        raise

    audit = security_audit or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=False,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    )
    audit(parent, True)
    audit(target, False)
    before = target.lstat()
    raw = target.read_bytes()
    after = target.lstat()
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or not raw or len(raw) >= 4096:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpatialAuthenticationError("invalid-session-descriptor") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema")
        not in {
            "ghoststudio-spatial-session/v1",
            "ghoststudio-spatial-session/v2",
        }
        or not hmac.compare_digest(
            str(payload.get("sessionId") or ""),
            session_id,
        )
    ):
        return False

    current = target.lstat()
    current_identity = (
        current.st_dev,
        current.st_ino,
        current.st_size,
        current.st_mtime_ns,
    )
    if current_identity != identity_before:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    target.unlink()
    return True


def load_spatial_session_descriptor(
    path: str | os.PathLike[str],
    *,
    now: Callable[[], float] = time.time,
    security_audit: Callable[[Path, bool], None] | None = None,
    package_sid: str | None = None,
    app_container_root: Path | None = None,
) -> SpatialSessionDescriptor:
    """Load a strict private descriptor for the stdio adapter."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise SpatialAuthenticationError("invalid-session-descriptor")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(
        target.parent,
        allow_missing=False,
        app_container_root=app_container_root,
    )
    _assert_regular_unlinked_path(target)
    audit = security_audit or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=False,
            package_sid=package_sid,
            app_container_root=app_container_root,
        )
    )
    audit(target.parent, True)
    audit(target, False)
    before = target.lstat()
    raw = target.read_bytes()
    after = target.lstat()
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if not raw or len(raw) >= 4096:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpatialAuthenticationError(
            "invalid-session-descriptor"
        ) from exc
    if not isinstance(payload, dict):
        raise SpatialAuthenticationError("invalid-session-descriptor")
    schema = payload.get("schema")
    common_keys = {
        "schema",
        "sessionId",
        "secret",
        "createdAt",
        "expiresAt",
        "pid",
    }
    if schema == "ghoststudio-spatial-session/v1":
        expected_keys = common_keys | {"port"}
        transport = LOOPBACK_SPATIAL_TRANSPORT
        pipe_name = None
    elif schema == "ghoststudio-spatial-session/v2":
        expected_keys = common_keys | {"transport", "pipeName"}
        transport = payload.get("transport")
        pipe_name = payload.get("pipeName")
        if (
            transport != WINDOWS_SPATIAL_TRANSPORT
            or not isinstance(pipe_name, str)
            or not _WINDOWS_PIPE_NAME_RE.fullmatch(pipe_name)
        ):
            raise SpatialAuthenticationError("invalid-session-descriptor")
    else:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if set(payload) != expected_keys:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if (
        not isinstance(payload["sessionId"], str)
        or not isinstance(payload["secret"], str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", payload["secret"])
        or not isinstance(payload["createdAt"], int)
        or isinstance(payload["createdAt"], bool)
        or not isinstance(payload["expiresAt"], int)
        or isinstance(payload["expiresAt"], bool)
        or not isinstance(payload["pid"], int)
        or isinstance(payload["pid"], bool)
    ):
        raise SpatialAuthenticationError("invalid-session-descriptor")
    try:
        secret_text = payload["secret"]
        secret = base64.b64decode(
            secret_text + ("=" * (-len(secret_text) % 4)),
            altchars=b"-_",
            validate=True,
        )
        port = payload.get("port")
        created_at = payload["createdAt"]
        expires_at = payload["expiresAt"]
        pid = payload["pid"]
        credentials = SpatialSessionCredentials(
            session_id=payload["sessionId"],
            secret=secret,
            expires_at=expires_at,
        )
    except (TypeError, ValueError) as exc:
        raise SpatialAuthenticationError(
            "invalid-session-descriptor"
        ) from exc
    if (
        (
            schema == "ghoststudio-spatial-session/v1"
            and (
                not isinstance(port, int)
                or isinstance(port, bool)
                or not (1 <= port <= 65535)
            )
        )
        or created_at <= 0
        or expires_at <= created_at
        or pid <= 0
    ):
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if int(now()) > expires_at:
        raise SpatialAuthenticationError("expired-session")
    return SpatialSessionDescriptor(
        credentials=credentials,
        port=port,
        created_at=created_at,
        pid=pid,
        transport=transport,
        pipe_name=pipe_name,
        schema=str(schema),
    )


def canonical_request_bytes(
    *,
    method: str,
    path: str,
    timestamp: int,
    nonce: str,
    body: bytes,
) -> bytes:
    normalized_method = str(method or "").strip().upper()
    normalized_path = str(path or "").strip()
    if (
        not normalized_method
        or "\n" in normalized_method
        or not normalized_path.startswith("/")
        or "\n" in normalized_path
        or "\n" in nonce
    ):
        raise ValueError("method, path, or nonce is invalid")
    components = (
        AUTH_DOMAIN,
        normalized_method,
        normalized_path,
        str(int(timestamp)),
        nonce,
        sha256_hex(body),
    )
    return "\n".join(components).encode("utf-8")


class SpatialRequestSigner:
    """Create request headers without exposing the secret to call sites."""

    def __init__(self, credentials: SpatialSessionCredentials):
        self._credentials = credentials

    def sign(
        self,
        *,
        method: str,
        path: str,
        body: bytes,
        timestamp: int | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        issued_at = int(time.time()) if timestamp is None else int(timestamp)
        request_nonce = nonce or secrets.token_urlsafe(24)
        if not _NONCE_RE.fullmatch(request_nonce):
            raise ValueError("nonce must be a 16-128 character safe token")
        canonical = canonical_request_bytes(
            method=method,
            path=path,
            timestamp=issued_at,
            nonce=request_nonce,
            body=body,
        )
        signature = hmac.new(
            self._credentials.secret,
            canonical,
            hashlib.sha256,
        ).hexdigest()
        return {
            HEADER_SESSION: self._credentials.session_id,
            HEADER_TIMESTAMP: str(issued_at),
            HEADER_NONCE: request_nonce,
            HEADER_SIGNATURE: signature,
        }


class SpatialRequestAuthenticator:
    """Verify freshness, HMAC integrity, and per-session nonce uniqueness."""

    def __init__(
        self,
        credentials: SpatialSessionCredentials,
        *,
        max_clock_skew_seconds: int = DEFAULT_MAX_CLOCK_SKEW_SECONDS,
        replay_capacity: int = DEFAULT_REPLAY_CAPACITY,
        now: Callable[[], float] = time.time,
    ):
        if not isinstance(max_clock_skew_seconds, int) or not (
            1 <= max_clock_skew_seconds <= 300
        ):
            raise ValueError("max_clock_skew_seconds must be between 1 and 300")
        if not isinstance(replay_capacity, int) or not (1 <= replay_capacity <= 65536):
            raise ValueError("replay_capacity must be between 1 and 65536")
        self._credentials = credentials
        self._max_clock_skew_seconds = max_clock_skew_seconds
        self._replay_capacity = replay_capacity
        self._now = now
        self._seen_nonces: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        wanted = name.casefold()
        for key, value in headers.items():
            if str(key).casefold() == wanted:
                return str(value or "").strip()
        return ""

    def verify(
        self,
        *,
        headers: Mapping[str, str],
        method: str,
        path: str,
        body: bytes,
    ) -> VerifiedSpatialRequest:
        if not isinstance(body, bytes):
            raise TypeError("body must be bytes")
        if len(body) > MAX_BODY_BYTES:
            raise SpatialAuthenticationError("body-too-large")

        session_id = self._header(headers, HEADER_SESSION)
        timestamp_text = self._header(headers, HEADER_TIMESTAMP)
        nonce = self._header(headers, HEADER_NONCE)
        signature = self._header(headers, HEADER_SIGNATURE)
        if not all((session_id, timestamp_text, nonce, signature)):
            raise SpatialAuthenticationError("missing-credentials")
        if not hmac.compare_digest(session_id, self._credentials.session_id):
            raise SpatialAuthenticationError("invalid-session")
        try:
            timestamp = int(timestamp_text, 10)
        except (TypeError, ValueError):
            raise SpatialAuthenticationError("invalid-timestamp") from None
        if not _NONCE_RE.fullmatch(nonce):
            raise SpatialAuthenticationError("invalid-nonce")
        if not _SIGNATURE_RE.fullmatch(signature):
            raise SpatialAuthenticationError("invalid-signature")

        now = int(self._now())
        if now > self._credentials.expires_at:
            raise SpatialAuthenticationError("expired-session")
        if abs(now - timestamp) > self._max_clock_skew_seconds:
            raise SpatialAuthenticationError("expired-request")

        canonical = canonical_request_bytes(
            method=method,
            path=path,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
        )
        expected_signature = hmac.new(
            self._credentials.secret,
            canonical,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature.casefold(), expected_signature):
            raise SpatialAuthenticationError("invalid-signature")

        with self._lock:
            oldest_allowed = now - self._max_clock_skew_seconds
            expired_nonces = [
                seen_nonce
                for seen_nonce, signed_at in self._seen_nonces.items()
                if signed_at < oldest_allowed
            ]
            for seen_nonce in expired_nonces:
                del self._seen_nonces[seen_nonce]
            if nonce in self._seen_nonces:
                raise SpatialAuthenticationError("replayed-request")
            if len(self._seen_nonces) >= self._replay_capacity:
                raise SpatialAuthenticationError(
                    "replay-capacity-exhausted"
                )
            self._seen_nonces[nonce] = timestamp

        return VerifiedSpatialRequest(
            session_id=session_id,
            timestamp=timestamp,
            nonce=nonce,
            body_sha256=sha256_hex(body),
        )
