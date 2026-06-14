from __future__ import annotations

import json
import re
from pathlib import Path

from src.adapters.native_core import python_module_package_specs


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "native" / "GhostRigger.NativeModulePackages.json"
SOLUTION = ROOT / "GhostRigger.sln"


def _manifest_entries() -> list[dict[str, str]]:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(entries, list)
    return entries


def _project_items(project_text: str, item_name: str) -> list[str]:
    return re.findall(rf'<{item_name} Include="([^"]+)"', project_text)


def _read_project_item_containing(
    project_dir: Path,
    project_text: str,
    item_name: str,
    needle: str,
) -> str:
    for relative in _project_items(project_text, item_name):
        item_path = project_dir / relative
        if item_path.suffix not in {".cpp", ".h", ".hpp"}:
            continue
        item_text = item_path.read_text(encoding="utf-8")
        if needle in item_text:
            return item_text
    raise AssertionError(f"{project_dir.name} has no {item_name} item containing {needle!r}")


def test_native_module_manifest_covers_python_package_boundaries() -> None:
    entries = _manifest_entries()
    names = {entry["name"] for entry in entries}
    sources = {entry["source_package"] for entry in entries}

    assert len(entries) == 60
    assert "GhostRigger.Domain.Core.Modules" in names
    assert "GhostRigger.Domain.Core.Level" in names
    assert "GhostRigger.Domain.Core.Scene" in names
    assert "GhostRigger.GUI.Boundary.Viewports" in names
    assert "GhostRigger.Systems.Feature.BAS" in names

    for source in sources:
        source_path = ROOT / source
        assert source_path.exists(), source
        assert any(source_path.rglob("*.py")), source


def test_native_module_projects_are_in_solution_without_debug_app_projects() -> None:
    entries = _manifest_entries()
    solution = SOLUTION.read_text(encoding="utf-8")

    for entry in entries:
        name = entry["name"]
        project_guid = entry["project_guid"]
        assert f'"{name}"' in solution
        assert f'"{name}.DEBUG"' not in solution
        assert f"native\\{name}\\{name}.vcxproj" in solution
        assert f"native\\{name}.DEBUG\\{name}.DEBUG.vcxproj" not in solution
        assert f"{project_guid}.Release|x64.Build.0" in solution
        assert not (ROOT / "native" / f"{name}.DEBUG").exists()


def test_native_module_project_files_keep_phase_one_diagnostic_contract() -> None:
    for entry in _manifest_entries():
        name = entry["name"]
        project_dir = ROOT / "native" / name

        project = (project_dir / f"{name}.vcxproj").read_text(encoding="utf-8")
        source = _read_project_item_containing(project_dir, project, "ClCompile", f'"name":"{name}"')
        header = _read_project_item_containing(
            project_dir,
            project,
            "ClInclude",
            f"gr_{entry['symbol_prefix']}_version",
        )

        assert f"<TargetName>{name}</TargetName>" in project
        assert f"<RootNamespace>{name}</RootNamespace>" in project
        assert f'"name":"{name}"' in source
        assert f'"source_package":"{entry["source_package"]}"' in source
        assert '"module_package":true' in source
        assert '"python_owner_active":' in source
        assert '"native_implementation_enabled":' in source
        assert f"gr_{entry['symbol_prefix']}_version" in header


def test_native_module_packages_are_exposed_through_registry_specs() -> None:
    manifest_names = tuple(entry["name"] for entry in _manifest_entries())
    specs = python_module_package_specs()

    assert tuple(spec.name for spec in specs) == manifest_names
    assert specs[0].name == "GhostRigger.Domain.Core.Modules"
    assert specs[0].dll_name == "GhostRigger.Domain.Core.Modules.dll"
    assert specs[0].version_export == "gr_modules_version"
    assert all(spec.capabilities_export.endswith("_capabilities_json") for spec in specs)
