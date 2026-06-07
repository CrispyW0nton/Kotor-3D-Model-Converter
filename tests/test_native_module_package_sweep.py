from __future__ import annotations

import json
from pathlib import Path

from src.adapters.native_core import python_module_package_specs


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "native" / "GhostRigger.NativeModulePackages.json"
SOLUTION = ROOT / "GhostRigger.sln"


def _manifest_entries() -> list[dict[str, str]]:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    return entries


def _pascal_name(project_name: str) -> str:
    return "".join(part for part in project_name.replace(".", " ").split() if part)


def test_native_module_manifest_covers_python_package_boundaries() -> None:
    entries = _manifest_entries()
    names = {entry["name"] for entry in entries}
    sources = {entry["source_package"] for entry in entries}

    assert len(entries) == 60
    assert "GhostRigger.Modules" in names
    assert "GhostRigger.Level" in names
    assert "GhostRigger.Scene" in names
    assert "GhostRigger.GUI.Viewports" in names
    assert "GhostRigger.Systems.BAS" in names

    for source in sources:
        source_path = ROOT / source
        assert source_path.exists(), source
        assert any(source_path.rglob("*.py")), source


def test_native_module_projects_are_in_solution_with_debug_validators() -> None:
    entries = _manifest_entries()
    solution = SOLUTION.read_text(encoding="utf-8")

    for entry in entries:
        name = entry["name"]
        project_guid = entry["project_guid"]
        debug_guid = entry["debug_project_guid"]
        assert f'"{name}"' in solution
        assert f'"{name}.DEBUG"' in solution
        assert f"native\\{name}\\{name}.vcxproj" in solution
        assert f"native\\{name}.DEBUG\\{name}.DEBUG.vcxproj" in solution
        assert f"{project_guid}.Release|x64.Build.0" in solution
        assert f"{debug_guid}.Debug|x64.Build.0" in solution
        assert f"{debug_guid}.Release|x64.Build.0" not in solution


def test_native_module_project_files_keep_phase_one_diagnostic_contract() -> None:
    for entry in _manifest_entries():
        name = entry["name"]
        pascal = _pascal_name(name)
        project_dir = ROOT / "native" / name
        debug_dir = ROOT / "native" / f"{name}.DEBUG"

        project = (project_dir / f"{name}.vcxproj").read_text(encoding="utf-8")
        source = (project_dir / f"{pascal}.cpp").read_text(encoding="utf-8")
        header = (project_dir / f"{pascal}.h").read_text(encoding="utf-8")
        debug_source = (debug_dir / f"{pascal}DEBUG.cpp").read_text(encoding="utf-8")

        assert f"<TargetName>{name}</TargetName>" in project
        assert f'"name":"{name}"' in source
        assert f'"source_package":"{entry["source_package"]}"' in source
        assert '"module_package":true' in source
        assert '"native_implementation_enabled":false' in source
        assert '"python_owner_active":true' in source
        assert f"gr_{entry['symbol_prefix']}_version" in header
        assert f"{name}.DEBUG OK" in debug_source


def test_native_module_packages_are_exposed_through_registry_specs() -> None:
    manifest_names = tuple(entry["name"] for entry in _manifest_entries())
    specs = python_module_package_specs()

    assert tuple(spec.name for spec in specs) == manifest_names
    assert specs[0].name == "GhostRigger.Modules"
    assert specs[0].dll_name == "GhostRigger.Modules.dll"
    assert specs[0].version_export == "gr_modules_version"
    assert all(spec.capabilities_export.endswith("_capabilities_json") for spec in specs)
