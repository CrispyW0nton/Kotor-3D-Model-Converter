from __future__ import annotations

from pathlib import Path
import sys


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


def test_t2641_export_panel_exposes_dev_test_stage_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "devTestModuleRequested" in panel_source
    assert "mapStudioStageDevTestModuleButton" in panel_source
    assert "Stage grdev01 Dev Test Module" in panel_source
    assert "self.export_panel.devTestModuleRequested.connect(self.stage_dev_test_module)" in window_source
