from __future__ import annotations

from pathlib import Path
import sys


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Scene.Level/Python",
        "native/GhostRigger.Core.Resources.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene.Walkmesh/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2641_controller_stages_grdev01_smoke_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")

    result = controller.stage_dev_test_module(tmp_path)

    assert result.ok is True
    assert result.code == "staged_for_manual_install"
    assert result.export_result is not None
    assert result.export_result.code == "export_candidate"
    assert Path(result.export_result.module_path).is_file()
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    assert Path(result.proof_recording_script_path).is_file()
    assert result.launch_helper_command == ""
    assert result.elevated_launch_script_path == ""


def test_t2641_export_panel_exposes_dev_test_stage_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Core.Tools.ModuleMeshes/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Core.Tools.ModuleEditor/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "devTestModuleRequested" in panel_source
    assert "mapStudioStageDevTestModuleButton" in panel_source
    assert "Stage grdev01 Dev Test Module" in panel_source
    assert "self.export_panel.devTestModuleRequested.connect(self.stage_dev_test_module)" in window_source
    assert "Proof recorder:" in window_source


def test_t2642_builder_tab_exposes_authored_dev_room_action() -> None:
    builder_source = Path(
        "native/GhostRigger.Core.Tools.ModuleMeshes/Python/src/gui/panels/module_editor/builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Core.Tools.ModuleEditor/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "Create grdev01 Dev Room" in builder_source
    assert "self.controller.create_dev_test_authored_module()" in window_source
