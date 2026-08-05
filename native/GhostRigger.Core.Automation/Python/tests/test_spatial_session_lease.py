"""Windows handle-lease contracts for the Ghost Studio spatial session."""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

import pytest

AUTH_MODULE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "ipc"
    / "spatial_auth.py"
)
PACKAGE_SID = (
    "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)
OWNER_NAME = ".ghoststudio-session.owner"


def _auth_module():
    name = "ghoststudio_spatial_session_lease_test_module"
    spec = importlib.util.spec_from_file_location(name, AUTH_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _prepared_session(auth, tmp_path: Path) -> tuple[Path, Path]:
    app_container_root = tmp_path.resolve()
    session_path = (
        app_container_root
        / "MCPStudioState"
        / "GhostStudioSpatial"
        / "ghoststudio-session.json"
    )
    auth.prepare_private_spatial_directory(
        session_path.parent,
        package_sid=PACKAGE_SID,
        app_container_root=app_container_root,
    )
    return session_path, app_container_root


def _acquire(auth, session_path: Path, app_container_root: Path):
    return auth.acquire_windows_spatial_session_lease(
        session_path,
        package_sid=PACKAGE_SID,
        app_container_root=app_container_root,
    )


def test_spatial_session_lease_rejects_non_windows_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _auth_module()
    monkeypatch.setattr(auth.os, "name", "posix")

    with pytest.raises(auth.SpatialAuthenticationError) as failure:
        auth.acquire_windows_spatial_session_lease(
            tmp_path / "ghoststudio-session.json",
            package_sid=PACKAGE_SID,
            app_container_root=tmp_path,
        )

    assert failure.value.code == "private-session-required"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_is_exclusive_persistent_and_idempotent(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME

    lease = _acquire(auth, session_path, app_container_root)
    assert isinstance(lease, auth.WindowsSpatialSessionLease)
    assert not lease.closed
    assert owner_path.is_file()
    assert owner_path.read_bytes() == b""
    assert _acquire(auth, session_path, app_container_root) is None

    lease.close()
    lease.close()
    assert lease.closed
    assert owner_path.is_file()

    with _acquire(auth, session_path, app_container_root) as replacement:
        assert replacement is not None
        assert not replacement.closed
    assert replacement.closed
    assert owner_path.is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_denies_delete_replace_and_inheritance(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME
    replacement = session_path.parent / "replacement.owner"
    replacement.write_bytes(b"replacement")

    lease = _acquire(auth, session_path, app_container_root)
    assert lease is not None
    try:
        flags = wintypes.DWORD()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetHandleInformation.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.GetHandleInformation.restype = wintypes.BOOL
        assert kernel32.GetHandleInformation(
            lease._handle,
            ctypes.byref(flags),
        )
        assert flags.value & 0x00000001 == 0

        with pytest.raises(PermissionError) as delete_failure:
            owner_path.unlink()
        assert getattr(delete_failure.value, "winerror", None) in {5, 32}

        with pytest.raises(PermissionError) as replace_failure:
            os.replace(replacement, owner_path)
        assert getattr(replace_failure.value, "winerror", None) in {5, 32}
    finally:
        lease.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_is_released_after_owner_process_crash(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    child_source = "\n".join(
        (
            "import importlib.util",
            "import os",
            "from pathlib import Path",
            "import sys",
            f"module_path=Path({json.dumps(str(AUTH_MODULE))})",
            "name='ghoststudio_spatial_session_lease_crash_child'",
            "spec=importlib.util.spec_from_file_location(name,module_path)",
            "module=importlib.util.module_from_spec(spec)",
            "sys.modules[name]=module",
            "spec.loader.exec_module(module)",
            (
                "lease=module.acquire_windows_spatial_session_lease("
                f"Path({json.dumps(str(session_path))}),"
                f"package_sid={json.dumps(PACKAGE_SID)},"
                f"app_container_root=Path({json.dumps(str(app_container_root))}))"
            ),
            "assert lease is not None",
            "print('held',flush=True)",
            "sys.stdin.buffer.read(1)",
            "os._exit(17)",
        )
    )
    child = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", child_source],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == b"held"
        assert _acquire(auth, session_path, app_container_root) is None
        assert child.stdin is not None
        child.stdin.write(b"x")
        child.stdin.flush()
        child.stdin.close()
        assert child.wait(timeout=10) == 17
        child.stdin = None

        replacement = _acquire(auth, session_path, app_container_root)
        assert replacement is not None
        replacement.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        if child.stdin is not None:
            child.stdin.close()
        if child.stdout is not None:
            child.stdout.close()
        if child.stderr is not None:
            child.stderr.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_creation_acl_survives_pre_audit_crash(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME
    child_source = "\n".join(
        (
            "import importlib.util",
            "import os",
            "from pathlib import Path",
            "import sys",
            f"module_path=Path({json.dumps(str(AUTH_MODULE))})",
            "name='ghoststudio_spatial_session_lease_acl_crash_child'",
            "spec=importlib.util.spec_from_file_location(name,module_path)",
            "module=importlib.util.module_from_spec(spec)",
            "sys.modules[name]=module",
            "spec.loader.exec_module(module)",
            (
                "def observe_then_crash("
                "_handle,expected_path,*,kernel32):"
            ),
            "  try:",
            (
                "    module._audit_windows_private_security("
                "expected_path,False,package_sid=None)"
            ),
            "  except module.SpatialAuthenticationError:",
            "    os._exit(91)",
            "  try:",
            (
                "    module._audit_windows_private_security("
                f"expected_path,False,package_sid={json.dumps(PACKAGE_SID)})"
            ),
            "  except module.SpatialAuthenticationError:",
            "    pass",
            "  else:",
            "    os._exit(92)",
            "  os._exit(17)",
            (
                "module._audit_windows_spatial_session_lease_handle="
                "observe_then_crash"
            ),
            (
                "module.acquire_windows_spatial_session_lease("
                f"Path({json.dumps(str(session_path))}),"
                f"package_sid={json.dumps(PACKAGE_SID)},"
                f"app_container_root=Path({json.dumps(str(app_container_root))}))"
            ),
            "os._exit(93)",
        )
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", child_source],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        check=False,
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    assert completed.returncode == 17, completed.stderr.decode(
        "utf-8",
        errors="replace",
    )
    auth._audit_windows_private_security(
        owner_path,
        False,
        package_sid=None,
    )
    with pytest.raises(auth.SpatialAuthenticationError):
        auth._audit_windows_private_security(
            owner_path,
            False,
            package_sid=PACKAGE_SID,
        )
    replacement = _acquire(auth, session_path, app_container_root)
    assert replacement is not None
    replacement.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_rejects_hard_link_shape(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME
    peer_path = session_path.parent / "peer.owner"

    lease = _acquire(auth, session_path, app_container_root)
    assert lease is not None
    lease.close()
    owner_path.replace(peer_path)
    os.link(peer_path, owner_path)

    with pytest.raises(auth.SpatialAuthenticationError) as failure:
        _acquire(auth, session_path, app_container_root)

    assert failure.value.code == "private-session-required"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_rejects_reparse_or_wrong_shape(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME
    owner_path.mkdir()

    with pytest.raises(auth.SpatialAuthenticationError) as directory_failure:
        _acquire(auth, session_path, app_container_root)
    assert directory_failure.value.code == "private-session-required"

    owner_path.rmdir()
    target = session_path.parent / "target.owner"
    target.write_bytes(b"")
    try:
        owner_path.symlink_to(target)
    except OSError:
        pytest.skip("Creating a Windows file symlink is not permitted")

    with pytest.raises(auth.SpatialAuthenticationError) as reparse_failure:
        _acquire(auth, session_path, app_container_root)
    assert reparse_failure.value.code == "private-session-required"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle lease contract")
def test_spatial_session_lease_rejects_existing_security_drift(
    tmp_path: Path,
) -> None:
    auth = _auth_module()
    session_path, app_container_root = _prepared_session(auth, tmp_path)
    owner_path = session_path.parent / OWNER_NAME

    lease = _acquire(auth, session_path, app_container_root)
    assert lease is not None
    lease.close()
    auth._windows_private_security(
        owner_path,
        False,
        apply=True,
        package_sid=PACKAGE_SID,
    )

    with pytest.raises(auth.SpatialAuthenticationError) as failure:
        _acquire(auth, session_path, app_container_root)

    assert failure.value.code == "private-session-required"
