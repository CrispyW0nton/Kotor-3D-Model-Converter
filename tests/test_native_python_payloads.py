from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
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


def test_payload_dlls_export_common_python_payload_abi() -> None:
    for entry in _payload_entries():
        project = str(entry["project"])
        project_dir = ROOT / "native" / project
        cpp_text = "\n".join(path.read_text(encoding="utf-8") for path in project_dir.glob("*.cpp"))

        assert "GhostRiggerPythonPayloadResource.h" in cpp_text
        assert "gr_python_payload_manifest_json" in cpp_text
        assert "gr_python_payload_file_count" in cpp_text
        assert "manifest_json_from_module_symbol" in cpp_text


def test_native_host_depends_on_every_payload_dll_project_without_linking_libs() -> None:
    entries = _payload_entries()
    host_project = ROOT / "native" / "GhostRigger.Native" / "GhostRigger.Native.vcxproj"
    tree = ET.parse(host_project)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}

    refs = {
        Path(node.attrib["Include"]).stem: node
        for node in tree.findall(".//msb:ItemGroup[@Label='NativePayloadDependencies']/msb:ProjectReference", ns)
    }

    assert set(refs) == {str(entry["project"]) for entry in entries}
    for node in refs.values():
        link_node = node.find("msb:LinkLibraryDependencies", ns)
        assert link_node is not None
        assert link_node.text == "false"


def test_native_host_dependency_table_covers_every_payload_project() -> None:
    entries = _payload_entries()
    dependency_header = (
        ROOT / "native" / "GhostRigger.Native" / "GhostRiggerNativeDependencies.h"
    ).read_text(encoding="utf-8")

    dependency_names = set(re.findall(r'\{L"(GhostRigger[^"]+)", L"GhostRigger[^"]+\.dll"', dependency_header))

    assert dependency_names == {str(entry["project"]) for entry in entries}
    assert "kNativeDependencySpecs" in dependency_header
    assert "kNativeDependencySpecCount" in dependency_header


def test_main_py_logs_native_dependency_audit_from_host_environment() -> None:
    main_source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert "GHOSTRIGGER_NATIVE_DEPENDENCY_AUDIT_JSON" in main_source
    assert "Native DLL dependency audit:" in main_source
    assert "Native DLL dependency %0*d/%0*d" in main_source
    assert "_log_native_dependency_audit(log)" in main_source
