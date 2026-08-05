"""Windows AppContainer ACL contracts for Ghost Studio spatial sessions."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUTH_MODULE = (
    ROOT
    / "native"
    / "GhostRigger.Core.Automation"
    / "Python"
    / "src"
    / "ipc"
    / "spatial_auth.py"
)
PACKAGE_SID = (
    "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)
OTHER_PACKAGE_SID = (
    "S-1-15-2-1229027099-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)


def _auth_module():
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_auth_appcontainer_test_module",
        AUTH_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _powershell() -> Path:
    system_root = Path(
        os.environ.get("SystemRoot") or os.environ.get("WINDIR") or ""
    )
    return (
        system_root
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )


def _acl_snapshot(path: Path) -> dict[str, object]:
    script = "\n".join(
        (
            "$ErrorActionPreference='Stop'",
            "$acl=Get-Acl -LiteralPath $env:GHOSTSTUDIO_TEST_ACL_PATH",
            "$access=@($acl.Access | ForEach-Object {",
            "  $identity=$_.IdentityReference",
            "  if($identity -is [Security.Principal.SecurityIdentifier]){",
            "    $sid=$identity.Value",
            "  }else{",
            "    $sid=$identity.Translate([Security.Principal.SecurityIdentifier]).Value",
            "  }",
            "  [pscustomobject]@{",
            "    sid=$sid",
            "    rights=[int64]$_.FileSystemRights",
            "    inheritance=[int]$_.InheritanceFlags",
            "    propagation=[int]$_.PropagationFlags",
            "    inherited=[bool]$_.IsInherited",
            "    type=[string]$_.AccessControlType",
            "  }",
            "})",
            "$owner=([Security.Principal.NTAccount]$acl.Owner).Translate([Security.Principal.SecurityIdentifier]).Value",
            "[pscustomobject]@{owner=$owner;protected=[bool]$acl.AreAccessRulesProtected;access=$access} | ConvertTo-Json -Depth 5 -Compress",
        )
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    completed = subprocess.run(
        [
            str(_powershell()),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            "SystemRoot": os.environ.get("SystemRoot", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "PATH": os.environ.get("PATH", ""),
            "GHOSTSTUDIO_TEST_ACL_PATH": str(path),
        },
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "s-1-15-2-0-0-0-0-0-0-0",
        "S-1-15-2-0-0-0-0-0-0",
        "S-1-15-2-0-0-0-0-0-0-0-0",
        "S-1-15-2-00-0-0-0-0-0-0",
        "S-1-15-2-4294967296-0-0-0-0-0-0",
        "S-1-15-3-0-0-0-0-0-0-0",
        f" {PACKAGE_SID}",
        f"{PACKAGE_SID} ",
    ],
)
def test_spatial_appcontainer_sid_rejects_noncanonical_values(
    value: str,
) -> None:
    module = _auth_module()

    with pytest.raises(module.SpatialAuthenticationError) as error:
        module.spatial_app_container_package_sid(
            {module.SPATIAL_APP_CONTAINER_SID_ENV: value}
        )

    assert error.value.code == "invalid-app-container-sid"


def test_spatial_appcontainer_sid_requires_explicit_environment_binding() -> None:
    module = _auth_module()

    assert module.spatial_app_container_package_sid({}) is None
    assert (
        module.spatial_app_container_package_sid(
            {module.SPATIAL_APP_CONTAINER_SID_ENV: PACKAGE_SID}
        )
        == PACKAGE_SID
    )


def test_default_session_path_uses_the_approval_bound_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _auth_module()
    profile_root = tmp_path / "app-container-profile"
    profile_root.mkdir()
    monkeypatch.setattr(
        module,
        "_windows_app_container_profile_root",
        lambda _environ=None: profile_root,
    )

    assert module.default_spatial_session_path(
        {module.SPATIAL_APP_CONTAINER_SID_ENV: PACKAGE_SID}
    ) == (
        profile_root
        / "MCPStudioState"
        / "GhostStudioSpatial"
        / "ghoststudio-session.json"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows AppContainer path contract")
def test_link_audit_reanchors_at_the_appcontainer_profile_after_access_denial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _auth_module()
    profile_root = tmp_path / "app-container-profile"
    target = (
        profile_root
        / "MCPStudioState"
        / "GhostStudioSpatial"
        / "ghoststudio-session.json"
    )
    target.parent.mkdir(parents=True)
    target.write_text("{}\n", encoding="utf-8")
    denied_ancestor = Path(target.anchor) / target.parts[1]
    original_lstat = Path.lstat

    def guarded_lstat(candidate: Path):
        if candidate == denied_ancestor:
            raise PermissionError("AppContainer ancestor is not enumerable")
        return original_lstat(candidate)

    monkeypatch.setattr(
        module,
        "_windows_app_container_profile_root",
        lambda _environ=None: profile_root,
    )
    monkeypatch.setattr(Path, "lstat", guarded_lstat)

    module._assert_no_link_components(
        target,
        allow_missing=False,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL contract")
def test_spatial_descriptor_read_audit_does_not_spawn_a_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _auth_module()
    monkeypatch.setenv(module.SPATIAL_APP_CONTAINER_SID_ENV, PACKAGE_SID)
    artifact = tmp_path / "session" / "ghoststudio-session.json"
    module.publish_spatial_session_descriptor(
        artifact,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=3_600,
    )

    def _reject_subprocess(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("read-only ACL audit spawned a helper process")

    def _reject_resolve(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "read-only ACL audit resolved inaccessible ancestors"
        )

    monkeypatch.setattr(module.subprocess, "run", _reject_subprocess)
    monkeypatch.setattr(Path, "resolve", _reject_resolve)
    descriptor = module.load_spatial_session_descriptor(
        artifact,
        now=lambda: 1_001,
    )

    assert descriptor.port == 7017


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL contract")
def test_spatial_acl_grants_only_exact_package_read_and_traverse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _auth_module()
    monkeypatch.setenv(module.SPATIAL_APP_CONTAINER_SID_ENV, PACKAGE_SID)
    directory = tmp_path / "session"
    artifact = directory / "ghoststudio-session.json"

    module.write_private_spatial_artifact(artifact, b"{}\n")

    directory_acl = _acl_snapshot(directory)
    artifact_acl = _acl_snapshot(artifact)
    assert directory_acl["protected"] is True
    assert artifact_acl["protected"] is True
    owner_sid = directory_acl["owner"]
    assert artifact_acl["owner"] == owner_sid

    directory_rules = {
        rule["sid"]: rule for rule in directory_acl["access"]
    }
    artifact_rules = {
        rule["sid"]: rule for rule in artifact_acl["access"]
    }
    assert set(directory_rules) == {
        owner_sid,
        "S-1-5-18",
        PACKAGE_SID,
    }
    assert set(artifact_rules) == {
        owner_sid,
        "S-1-5-18",
        PACKAGE_SID,
    }
    for full_control_sid in (owner_sid, "S-1-5-18"):
        assert directory_rules[full_control_sid] == {
            "sid": full_control_sid,
            "rights": 0x1F01FF,
            "inheritance": 3,
            "propagation": 0,
            "inherited": False,
            "type": "Allow",
        }
        assert artifact_rules[full_control_sid] == {
            "sid": full_control_sid,
            "rights": 0x1F01FF,
            "inheritance": 0,
            "propagation": 0,
            "inherited": False,
            "type": "Allow",
        }
    assert directory_rules[PACKAGE_SID] == {
        "sid": PACKAGE_SID,
        "rights": 0x1200A9,
        "inheritance": 3,
        "propagation": 0,
        "inherited": False,
        "type": "Allow",
    }
    assert artifact_rules[PACKAGE_SID] == {
        "sid": PACKAGE_SID,
        "rights": 0x120089,
        "inheritance": 0,
        "propagation": 0,
        "inherited": False,
        "type": "Allow",
    }
    write_rights = 0x2 | 0x4 | 0x10 | 0x100 | 0x10000 | 0x40000 | 0x80000
    assert directory_rules[PACKAGE_SID]["rights"] & write_rights == 0
    assert artifact_rules[PACKAGE_SID]["rights"] & write_rights == 0

    monkeypatch.setenv(
        module.SPATIAL_APP_CONTAINER_SID_ENV,
        OTHER_PACKAGE_SID,
    )
    with pytest.raises(module.SpatialAuthenticationError) as mismatch:
        module._private_security(artifact, False, apply=False)
    assert mismatch.value.code == "private-session-required"

    monkeypatch.setenv(
        module.SPATIAL_APP_CONTAINER_SID_ENV,
        PACKAGE_SID,
    )
    system_root = Path(
        os.environ.get("SystemRoot") or os.environ.get("WINDIR") or ""
    )
    drift = subprocess.run(
        [
            str(system_root / "System32" / "icacls.exe"),
            str(artifact),
            "/grant",
            "*S-1-5-32-545:R",
            "/Q",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert drift.returncode == 0, drift.stderr
    with pytest.raises(module.SpatialAuthenticationError) as unexpected:
        module._private_security(artifact, False, apply=False)
    assert unexpected.value.code == "private-session-required"


@pytest.mark.skipif(os.name != "nt", reason="Windows DACL contract")
def test_spatial_acl_uses_explicit_package_sid_not_ambient_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _auth_module()
    monkeypatch.delenv(module.SPATIAL_APP_CONTAINER_SID_ENV, raising=False)
    artifact = tmp_path / "explicit-session" / "ghoststudio-session.json"

    module.write_private_spatial_artifact(
        artifact,
        b"{}\n",
        package_sid=PACKAGE_SID,
    )
    artifact_acl = _acl_snapshot(artifact)
    artifact_rules = {
        rule["sid"]: rule for rule in artifact_acl["access"]
    }
    assert set(artifact_rules) == {
        artifact_acl["owner"],
        "S-1-5-18",
        PACKAGE_SID,
    }

    monkeypatch.setenv(
        module.SPATIAL_APP_CONTAINER_SID_ENV,
        OTHER_PACKAGE_SID,
    )
    module._private_security(
        artifact,
        False,
        apply=False,
        package_sid=PACKAGE_SID,
    )
