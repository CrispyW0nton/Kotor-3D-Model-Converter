"""Focused private-storage contracts for Ghost Studio spatial sessions."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

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
