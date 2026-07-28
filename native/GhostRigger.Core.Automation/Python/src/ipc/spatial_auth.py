"""HMAC authentication for the narrow Ghost Studio spatial IPC surface.

The legacy Ghostworks IPC routes predate MCP Studio and remain outside this
security boundary.  This module is intentionally framework-free so the GUI
bridge and the private stdio adapter share exactly one signing contract.
"""

from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import threading
import time
from typing import Callable, Mapping


AUTH_DOMAIN = "ghoststudio-spatial-hmac/v1"
HEADER_SESSION = "X-GhostStudio-Session"
HEADER_TIMESTAMP = "X-GhostStudio-Timestamp"
HEADER_NONCE = "X-GhostStudio-Nonce"
HEADER_SIGNATURE = "X-GhostStudio-Signature"
MAX_BODY_BYTES = 1024 * 1024
DEFAULT_MAX_CLOCK_SKEW_SECONDS = 30
DEFAULT_REPLAY_CAPACITY = 4096

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_SIGNATURE_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class SpatialAuthenticationError(ValueError):
    """A stable, non-secret authentication failure."""

    _MESSAGES = {
        "body-too-large": "Spatial request body exceeds the allowed size.",
        "expired-request": "Spatial request timestamp is outside the allowed window.",
        "expired-session": "Spatial authentication session has expired.",
        "invalid-nonce": "Spatial request nonce is invalid.",
        "invalid-session": "Spatial authentication session is invalid.",
        "invalid-session-descriptor": "Spatial session descriptor is invalid.",
        "invalid-signature": "Spatial request signature is invalid.",
        "invalid-timestamp": "Spatial request timestamp is invalid.",
        "missing-credentials": "Spatial authentication credentials are missing.",
        "private-session-required": "Spatial session storage is not private.",
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
class SpatialSessionDescriptor:
    credentials: SpatialSessionCredentials
    port: int
    created_at: int
    pid: int
    schema: str = "ghoststudio-spatial-session/v1"


@dataclass(frozen=True)
class VerifiedSpatialRequest:
    session_id: str
    timestamp: int
    nonce: str
    body_sha256: str


def sha256_hex(body: bytes) -> str:
    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")
    return hashlib.sha256(body).hexdigest()


def default_spatial_session_path(
    environ: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environ is None else environ
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
) -> None:
    """Reject linked ancestors before any caller resolves or creates a path."""

    candidate = _absolute_lexical_path(path)
    anchor = Path(candidate.anchor)
    current = anchor
    for component in candidate.parts[1:]:
        current /= component
        try:
            details = current.lstat()
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


def _windows_private_security(
    path: Path,
    is_directory: bool,
    *,
    apply: bool,
) -> None:
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
            f"$isDirectory=${str(bool(is_directory)).lower()}",
            f"$apply=${str(bool(apply)).lower()}",
            "if($apply){",
            "  if($isDirectory){",
            "    $acl=New-Object Security.AccessControl.DirectorySecurity",
            "    $sddl='O:'+$current.Value+'D:P(A;OICI;FA;;;'+$current.Value+')(A;OICI;FA;;;SY)'",
            "  }else{",
            "    $acl=New-Object Security.AccessControl.FileSecurity",
            "    $sddl='O:'+$current.Value+'D:P(A;;FA;;;'+$current.Value+')(A;;FA;;;SY)'",
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
            "$allowed=@($current.Value,$system.Value)",
            "$currentFull=$false",
            "$systemFull=$false",
            "foreach($rule in $observed.Access){",
            "  $sid=([Security.Principal.NTAccount]$rule.IdentityReference).Translate([Security.Principal.SecurityIdentifier]).Value",
            "  if($allowed -notcontains $sid){exit 33}",
            "  if($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow){exit 34}",
            "  $full=(($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)",
            "  if($sid -eq $current.Value -and $full){$currentFull=$true}",
            "  if($sid -eq $system.Value -and $full){$systemFull=$true}",
            "}",
            "if(-not $currentFull -or -not $systemFull){exit 35}",
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


def _private_security(path: Path, is_directory: bool, *, apply: bool) -> None:
    _assert_no_link_components(
        path.parent,
        allow_missing=False,
    )
    details = path.lstat()
    expected = stat.S_ISDIR(details.st_mode) if is_directory else stat.S_ISREG(details.st_mode)
    if _is_link_or_reparse(details) or not expected:
        raise SpatialAuthenticationError("private-session-required")
    resolved = path.resolve(strict=True)
    if os.name == "nt":
        _windows_private_security(resolved, is_directory, apply=apply)
        return
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
) -> Path:
    """Create and verify a private directory without following path links."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("private spatial directory path must be absolute")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(target, allow_missing=True)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    _assert_no_link_components(target, allow_missing=False)
    details = target.lstat()
    if _is_link_or_reparse(details) or not stat.S_ISDIR(details.st_mode):
        raise SpatialAuthenticationError("private-session-required")
    security = security_hook or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=True,
        )
    )
    security(target, True)
    return target


def secure_private_spatial_artifact(
    path: str | os.PathLike[str],
    *,
    security_hook: Callable[[Path, bool], None] | None = None,
) -> Path:
    """Apply and verify private access on one existing regular artifact."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("private spatial artifact path must be absolute")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(target.parent, allow_missing=False)
    _assert_regular_unlinked_path(target)
    security = security_hook or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=True,
        )
    )
    security(target, False)
    return target


def write_private_spatial_artifact(
    path: str | os.PathLike[str],
    content: bytes,
    *,
    security_hook: Callable[[Path, bool], None] | None = None,
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


def publish_spatial_session_descriptor(
    path: str | os.PathLike[str],
    *,
    port: int,
    credentials: SpatialSessionCredentials | None = None,
    now: Callable[[], float] = time.time,
    ttl_seconds: int = 8 * 60 * 60,
    security_hook: Callable[[Path, bool], None] | None = None,
) -> SpatialSessionDescriptor:
    """Atomically publish one private loopback session descriptor."""

    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError("port must be between 1 and 65535")
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise ValueError("spatial session path must be absolute")
    target = _absolute_lexical_path(target)
    parent = target.parent
    _assert_no_link_components(parent, allow_missing=True)
    try:
        _assert_regular_unlinked_path(target)
    except SpatialAuthenticationError as exc:
        if exc.code != "session-descriptor-unavailable":
            raise
    parent = prepare_private_spatial_directory(
        parent,
        security_hook=security_hook,
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
    )
    encoded_secret = base64.urlsafe_b64encode(session_credentials.secret).decode(
        "ascii"
    ).rstrip("=")
    payload = {
        "schema": descriptor.schema,
        "sessionId": session_credentials.session_id,
        "secret": encoded_secret,
        "port": port,
        "createdAt": created_at,
        "expiresAt": session_credentials.expires_at,
        "pid": descriptor.pid,
    }
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
        )
        os.replace(temporary, target)
        _assert_regular_unlinked_path(target)
        secure_private_spatial_artifact(
            target,
            security_hook=security_hook,
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
) -> bool:
    """Remove a descriptor only when the current file belongs to the caller."""

    if not _SESSION_RE.fullmatch(str(session_id or "")):
        raise ValueError("session_id must be a 16-128 character safe token")
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise SpatialAuthenticationError("invalid-session-descriptor")
    target = _absolute_lexical_path(target)
    parent = target.parent
    _assert_no_link_components(parent, allow_missing=True)
    try:
        parent_details = parent.lstat()
    except FileNotFoundError:
        return False
    if _is_link_or_reparse(parent_details) or not stat.S_ISDIR(parent_details.st_mode):
        raise SpatialAuthenticationError("private-session-required")
    _assert_no_link_components(parent, allow_missing=False)
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
        or payload.get("schema") != "ghoststudio-spatial-session/v1"
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
) -> SpatialSessionDescriptor:
    """Load a strict private descriptor for the stdio adapter."""

    target = Path(path).expanduser()
    if not target.is_absolute():
        raise SpatialAuthenticationError("invalid-session-descriptor")
    target = _absolute_lexical_path(target)
    _assert_no_link_components(target.parent, allow_missing=False)
    _assert_regular_unlinked_path(target)
    audit = security_audit or (
        lambda candidate, is_directory: _private_security(
            candidate,
            is_directory,
            apply=False,
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
    expected_keys = {
        "schema",
        "sessionId",
        "secret",
        "port",
        "createdAt",
        "expiresAt",
        "pid",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if payload.get("schema") != "ghoststudio-spatial-session/v1":
        raise SpatialAuthenticationError("invalid-session-descriptor")
    if (
        not isinstance(payload["sessionId"], str)
        or not isinstance(payload["secret"], str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", payload["secret"])
        or not isinstance(payload["port"], int)
        or isinstance(payload["port"], bool)
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
        port = payload["port"]
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
        not (1 <= port <= 65535)
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
            while self._seen_nonces:
                _, seen_at = next(iter(self._seen_nonces.items()))
                if seen_at >= oldest_allowed:
                    break
                self._seen_nonces.popitem(last=False)
            if nonce in self._seen_nonces:
                raise SpatialAuthenticationError("replayed-request")
            self._seen_nonces[nonce] = timestamp
            while len(self._seen_nonces) > self._replay_capacity:
                self._seen_nonces.popitem(last=False)

        return VerifiedSpatialRequest(
            session_id=session_id,
            timestamp=timestamp,
            nonce=nonce,
            body_sha256=sha256_hex(body),
        )
