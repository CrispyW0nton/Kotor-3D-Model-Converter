from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGING_SCRIPT = ROOT / "scripts" / "stage_native_payload_dlls.ps1"
HOST_PROJECT = (
    ROOT
    / "native"
    / "GhostRigger.Native.Core.Host"
    / "GhostRigger.Native.Core.Host.vcxproj"
)


def _write_manifest(repo_root: Path, projects: list[str]) -> None:
    manifest_path = repo_root / "native" / "GhostRigger.PythonPayloadManifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps([{"project": project, "files": []} for project in projects]),
        encoding="utf-8",
    )


def _run_staging(repo_root: Path, host_out_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(STAGING_SCRIPT),
            "-RepoRoot",
            str(repo_root),
            "-Platform",
            "x64",
            "-Configuration",
            "Debug",
            "-HostOutDir",
            str(host_out_dir),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_staging_uses_exact_manifest_build_outputs_and_preserves_unowned_dlls(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    host_out_dir = tmp_path / "host-output"
    projects = ["GhostRigger.Core.One", "GhostRigger.Runtime.Two"]
    _write_manifest(repo_root, projects)

    source_dir = repo_root / "build" / "vs" / "x64" / "Debug"
    source_dir.mkdir(parents=True)
    source_bytes = {
        "GhostRigger.Core.One.dll": b"exact-core-one-build",
        "GhostRigger.Runtime.Two.dll": b"exact-runtime-two-build",
    }
    for dll_name, payload in source_bytes.items():
        (source_dir / dll_name).write_bytes(payload)
        (repo_root / dll_name).write_bytes(b"stale-root")

    host_out_dir.mkdir(parents=True)
    for dll_name in source_bytes:
        (host_out_dir / dll_name).write_bytes(b"stale-host")

    root_unowned = repo_root / "ThirdPartyKeep.dll"
    host_unowned = host_out_dir / "ThirdPartyKeep.dll"
    root_unowned.write_bytes(b"keep-root")
    host_unowned.write_bytes(b"keep-host")

    rogue_source = (
        repo_root
        / "native"
        / "rogue"
        / "build"
        / "vs"
        / "x64"
        / "Debug"
        / "GhostRigger.Core.One.dll"
    )
    rogue_source.parent.mkdir(parents=True)
    rogue_source.write_bytes(b"wrong-recursive-match")

    result = _run_staging(repo_root, host_out_dir)

    assert result.returncode == 0, result.stderr
    for dll_name, payload in source_bytes.items():
        assert (repo_root / dll_name).read_bytes() == payload
        assert (host_out_dir / dll_name).read_bytes() == payload
    assert root_unowned.read_bytes() == b"keep-root"
    assert host_unowned.read_bytes() == b"keep-host"


def test_staging_fails_before_pruning_when_any_manifest_dll_is_missing(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    host_out_dir = tmp_path / "host-output"
    projects = ["GhostRigger.Core.Present", "GhostRigger.Core.Missing"]
    _write_manifest(repo_root, projects)

    source_dir = repo_root / "build" / "vs" / "x64" / "Debug"
    source_dir.mkdir(parents=True)
    (source_dir / "GhostRigger.Core.Present.dll").write_bytes(b"present-source")
    host_out_dir.mkdir(parents=True)

    expected_stale: dict[Path, bytes] = {}
    for destination in (repo_root, host_out_dir):
        for project in projects:
            path = destination / f"{project}.dll"
            payload = f"stale:{destination.name}:{project}".encode()
            path.write_bytes(payload)
            expected_stale[path] = payload

    result = _run_staging(repo_root, host_out_dir)

    assert result.returncode != 0
    assert "GhostRigger.Core.Missing.dll" in result.stderr
    for path, payload in expected_stale.items():
        assert path.read_bytes() == payload


def test_staging_handles_host_out_dir_being_the_exact_source_directory(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    project = "GhostRigger.Core.SharedOutput"
    _write_manifest(repo_root, [project])

    source_dir = repo_root / "build" / "vs" / "x64" / "Debug"
    source_dir.mkdir(parents=True)
    source_dll = source_dir / f"{project}.dll"
    source_dll.write_bytes(b"shared-source-and-host-output")
    source_unowned = source_dir / "ThirdPartyKeep.dll"
    source_unowned.write_bytes(b"keep-shared-output")
    (repo_root / f"{project}.dll").write_bytes(b"stale-root")

    result = _run_staging(repo_root, source_dir)

    assert result.returncode == 0, result.stderr
    assert source_dll.read_bytes() == b"shared-source-and-host-output"
    assert (repo_root / f"{project}.dll").read_bytes() == b"shared-source-and-host-output"
    assert source_unowned.read_bytes() == b"keep-shared-output"


def test_host_postbuild_ends_with_fail_fast_manifest_staging() -> None:
    tree = ET.parse(HOST_PROJECT)
    namespace = {"msbuild": "http://schemas.microsoft.com/developer/msbuild/2003"}
    commands = [
        node.text or ""
        for node in tree.findall(".//msbuild:PostBuildEvent/msbuild:Command", namespace)
    ]

    assert len(commands) == 2
    for command in commands:
        lines = [line.strip() for line in command.splitlines() if line.strip()]
        final_line = lines[-1]
        assert "stage_native_payload_dlls.ps1" in final_line
        assert "-RepoRoot" in final_line
        assert "-HostOutDir" in final_line
        assert "-Platform" in final_line
        assert "-Configuration" in final_line
        assert "Get-ChildItem -LiteralPath '$(GhostRiggerRepoRoot)native' -Recurse" not in command
        assert "-Filter 'GhostRigger*.dll'" not in command
