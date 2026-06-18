from __future__ import annotations

import json
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2643_exports_kmap_authored_module_package(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

    kmap = new_kmap_project(name="grdev01", game="K1")
    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    kmap.extra_sections["authored_module"] = payload
    authored = authored_project_from_kmap_payload(payload, fallback_name=kmap.name, fallback_game=kmap.game)

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "export_candidate"
    assert Path(result.module_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert result.package_verification is not None
    assert result.package_verification.ok is True
    assert ("grdev01_room01", "mdl") in {(item.resref, item.restype) for item in result.package_verification.resources}
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {summary.restype for summary in result.resources}

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    authored_manifest = manifest["map_studio_authored_module"]
    assert authored_manifest["module_root"] == "grdev01"
    assert authored_manifest["capability_stage"] == "export_candidate"
    assert authored_manifest["game_tested"] is False
    assert authored_manifest["warp_command"] == "warp grdev01"


def test_t2643_controller_exports_current_kmap_authored_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=False)

    assert result.ok is True
    assert Path(result.module_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert "grdev01.are" in payload["runtime_resources"]
    assert "grdev01_room01.mdl" in payload["runtime_resources"]


def test_t2643_dry_run_does_not_mark_runtime_resources(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=True)

    assert result.ok is True
    assert result.code == "dry_run_passed"
    assert result.module_path == ""
    assert controller.project.extra_sections["authored_module"].get("runtime_resources", []) == []


def test_t2643_export_panel_exposes_authored_module_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    boundary_panel_source = Path(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authoredModuleRequested" in panel_source
    assert "mapStudioExportAuthoredModuleButton" in panel_source
    assert "Export Authored KMAP Module" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleRequested.connect(self.export_authored_module)" in window_source
    assert "self.controller.export_authored_module(path, dry_run=dry_run)" in window_source
