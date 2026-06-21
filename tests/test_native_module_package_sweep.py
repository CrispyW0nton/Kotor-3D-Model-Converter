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


def test_native_module_manifest_uses_collapsed_package_boundaries() -> None:
    entries = _manifest_entries()
    names = {entry["name"] for entry in entries}
    sources = {entry["source_package"] for entry in entries}

    assert len(entries) == 19
    assert names == {
        "GhostRigger.Core.Automation",
        "GhostRigger.Core.GUI.Display",
        "GhostRigger.Core.GUI.Helpers",
        "GhostRigger.Core.IO",
        "GhostRigger.Core.Math",
        "GhostRigger.Core.Project",
        "GhostRigger.Core.Qt",
        "GhostRigger.Core.Rendering",
        "GhostRigger.Core.Resources",
        "GhostRigger.Core.Scene",
        "GhostRigger.Core.Tools",
        "GhostRigger.Core.Unreal",
        "GhostRigger.Core.Validation",
        "GhostRigger.Core.Workflow",
        "GhostRigger.Runtime.Core",
    }
    assert len(sources) == len(entries)
    for source in sources:
        assert source.startswith("src/"), source
        assert "\\" not in source, source


def test_native_module_projects_are_solution_projects_without_debug_apps() -> None:
    solution = SOLUTION.read_text(encoding="utf-8")

    for name in {entry["name"] for entry in _manifest_entries()}:
        assert f'"{name}"' in solution
        assert f'"{name}.DEBUG"' not in solution
        assert f"native\\{name}\\{name}.vcxproj" in solution
        assert f"native\\{name}.DEBUG\\{name}.DEBUG.vcxproj" not in solution
        assert not (ROOT / "native" / f"{name}.DEBUG").exists()


def test_native_module_project_files_keep_module_exports() -> None:
    for entry in _manifest_entries():
        name = entry["name"]
        project_dir = ROOT / "native" / name
        project = (project_dir / f"{name}.vcxproj").read_text(encoding="utf-8")
        header = _read_project_item_containing(
            project_dir,
            project,
            "ClInclude",
            f"gr_{entry['symbol_prefix']}_version",
        )

        assert f"<TargetName>{name}</TargetName>" in project
        assert f"<RootNamespace>{name}</RootNamespace>" in project
        assert f"gr_{entry['symbol_prefix']}_version" in header
        assert f"gr_{entry['symbol_prefix']}_capabilities_json" in header
        assert any(
            source_package.replace("/", "\\") in project
            for source_package in entry["source_package"].split(";")
        )


def test_native_module_packages_are_exposed_through_registry_specs() -> None:
    manifest_entries = _manifest_entries()
    specs = python_module_package_specs()

    assert tuple(spec.name for spec in specs) == tuple(
        entry["name"] for entry in manifest_entries
    )
    assert specs[0].name == "GhostRigger.Core.Scene"
    assert specs[0].dll_name == "GhostRigger.Core.Scene.dll"
    assert specs[0].version_export == "gr_scene_version"
    assert all(spec.dll_name == f"{spec.name}.dll" for spec in specs)
    assert all(spec.capabilities_export.endswith("_capabilities_json") for spec in specs)
