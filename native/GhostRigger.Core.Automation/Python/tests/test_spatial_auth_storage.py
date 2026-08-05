"""Focused private-storage contracts for Ghost Studio spatial sessions."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import pytest


AUTH_MODULE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "ipc"
    / "spatial_auth.py"
)


def _auth_module():
    name = "ghoststudio_spatial_auth_storage_test_module"
    spec = importlib.util.spec_from_file_location(name, AUTH_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _no_security(_path: Path, _is_directory: bool) -> None:
    return None


def test_private_artifact_is_exclusive_flushed_and_secured(tmp_path: Path) -> None:
    auth = _auth_module()
    target = tmp_path / "private" / "capture.png"
    secured: list[tuple[Path, bool]] = []

    result = auth.write_private_spatial_artifact(
        target,
        b"\x89PNG\r\n\x1a\npayload",
        security_hook=lambda path, is_directory: secured.append(
            (Path(path), is_directory)
        ),
    )

    assert result == target
    assert target.read_bytes() == b"\x89PNG\r\n\x1a\npayload"
    assert secured == [(target.parent, True), (target, False)]

    with pytest.raises(FileExistsError):
        auth.write_private_spatial_artifact(
            target,
            b"replacement",
            security_hook=lambda _path, _is_directory: None,
        )
    assert target.read_bytes() == b"\x89PNG\r\n\x1a\npayload"


def test_private_artifact_is_removed_when_privacy_application_fails(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    target = tmp_path / "private" / "capture.png"

    def security(_path: Path, is_directory: bool) -> None:
        if not is_directory:
            raise auth.SpatialAuthenticationError("private-session-required")

    with pytest.raises(auth.SpatialAuthenticationError) as error:
        auth.write_private_spatial_artifact(
            target,
            b"private",
            security_hook=security,
        )

    assert error.value.code == "private-session-required"
    assert not target.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("port", "7017"),
        ("port", True),
        ("createdAt", "1000"),
        ("expiresAt", False),
        ("pid", "1234"),
    ],
)
def test_session_descriptor_rejects_coerced_scalar_types(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    auth = _auth_module()
    target = tmp_path / "private" / "ghoststudio-session.json"
    no_security = lambda _path, _is_directory: None
    auth.publish_spatial_session_descriptor(
        target,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=3_600,
        security_hook=no_security,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload[field] = value
    target.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(auth.SpatialAuthenticationError) as error:
        auth.load_spatial_session_descriptor(
            target,
            now=lambda: 1_001,
            security_audit=no_security,
        )

    assert error.value.code == "invalid-session-descriptor"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows sharing contract")
def test_session_descriptor_retries_a_transient_open_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _auth_module()
    target = tmp_path / "private" / "ghoststudio-session.json"
    first = auth.publish_spatial_session_descriptor(
        target,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=3_600,
        security_hook=_no_security,
    )
    reader = target.open("rb")
    assert reader.read(1)

    original_replace = auth.os.replace
    sharing_failure_observed = threading.Event()

    def _observe_replace(source, destination) -> None:
        try:
            original_replace(source, destination)
        except OSError as exc:
            if getattr(exc, "winerror", None) in {5, 32}:
                sharing_failure_observed.set()
            raise

    monkeypatch.setattr(auth.os, "replace", _observe_replace)

    def _release_reader_after_first_failure() -> None:
        if sharing_failure_observed.wait(timeout=2.0):
            reader.close()

    release = threading.Thread(
        target=_release_reader_after_first_failure,
        name="release-spatial-descriptor-reader",
        daemon=True,
    )
    release.start()
    try:
        replacement = auth.publish_spatial_session_descriptor(
            target,
            port=7017,
            now=lambda: 1_001,
            ttl_seconds=3_600,
            security_hook=_no_security,
        )
    finally:
        reader.close()
        release.join(timeout=2.0)

    assert sharing_failure_observed.is_set()
    assert replacement.credentials.session_id != first.credentials.session_id
    assert (
        auth.load_spatial_session_descriptor(
            target,
            now=lambda: 1_002,
            security_audit=_no_security,
        )
        == replacement
    )
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows sharing contract")
def test_session_descriptor_replacement_failure_is_bounded_and_atomic(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    target = tmp_path / "private" / "ghoststudio-session.json"
    first = auth.publish_spatial_session_descriptor(
        target,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=3_600,
        security_hook=_no_security,
    )

    started = time.monotonic()
    with target.open("rb") as reader:
        assert reader.read(1)
        with pytest.raises(PermissionError) as failure:
            auth.publish_spatial_session_descriptor(
                target,
                port=7017,
                now=lambda: 1_001,
                ttl_seconds=3_600,
                security_hook=_no_security,
            )
    elapsed = time.monotonic() - started

    assert getattr(failure.value, "winerror", None) in {5, 32}
    assert elapsed >= auth._WINDOWS_REPLACE_RETRY_SECONDS
    assert elapsed < 2.0
    assert (
        auth.load_spatial_session_descriptor(
            target,
            now=lambda: 1_002,
            security_audit=_no_security,
        )
        == first
    )
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))
