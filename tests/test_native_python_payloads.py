from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_MANIFEST = ROOT / "native" / "GhostRigger.PythonPayloadManifest.json"


def _payload_entries() -> list[dict[str, object]]:
    entries = json.loads(PAYLOAD_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    return entries


def test_python_payload_manifest_covers_every_python_source_and_dll_project() -> None:
    entries = _payload_entries()
    payload_files = [
        Path(file)
        for entry in entries
        for file in entry["files"]
    ]
    source_files = sorted(Path("src") / path.relative_to(ROOT / "src") for path in (ROOT / "src").rglob("*.py"))
    payload_projects = {str(entry["project"]) for entry in entries}
    dll_projects = {
        project.stem
        for project in (ROOT / "native").glob("GhostRigger*/GhostRigger*.vcxproj")
        if ".DEBUG" not in project.stem
        and "<ConfigurationType>DynamicLibrary</ConfigurationType>" in project.read_text(encoding="utf-8")
    }

    assert len(entries) == 93
    assert len(payload_files) == 1270
    assert set(source_files).issubset(set(payload_files))
    assert payload_projects == dll_projects


def test_python_payload_copies_are_byte_identical_and_manifested() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        project_manifest = project_dir / "GhostRiggerPythonPayload.json"
        rc_file = project_dir / "GhostRiggerPythonPayload.rc"

        payload = json.loads(project_manifest.read_text(encoding="utf-8"))
        rc_text = rc_file.read_text(encoding="utf-8")

        assert payload["schema"] == "ghostrigger_python_payload.v1"
        assert payload["project"] == project
        assert payload["file_count"] == entry["python_file_count"]
        assert "PYTHON_PAYLOAD_MANIFEST RCDATA" in rc_text

        payload_rows = payload["files"]
        assert len(payload_rows) == entry["python_file_count"]
        for row in payload_rows:
            source = ROOT / row["source_path"]
            packaged = project_dir / row["packaged_path"]
            assert packaged.exists(), packaged
            assert packaged.read_bytes() == source.read_bytes()
            assert hashlib.sha256(packaged.read_bytes()).hexdigest() == row["sha256"]
            assert f'{row["resource_name"]} RCDATA' in rc_text


def test_python_payloads_are_included_in_visual_studio_projects() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        vcxproj = (project_dir / f"{project}.vcxproj").read_text(encoding="utf-8")

        assert '<ItemGroup Label="PythonPayload">' in vcxproj
        assert '<ResourceCompile Include="GhostRiggerPythonPayload.rc" />' in vcxproj
        assert '<None Include="GhostRiggerPythonPayload.json" />' in vcxproj
        for source in entry["files"]:
            include_path = f"python_payload\\{source}"
            assert f'<None Include="{include_path}" />' in vcxproj
