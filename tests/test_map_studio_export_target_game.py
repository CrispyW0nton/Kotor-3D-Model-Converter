"""Focused K1/K2 export-target contracts for Map Studio."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_map_studio_export_target_retarget_is_undoable_and_updates_authored_binary_game() -> None:
    _install_native_payload_paths()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grtarget", game="K1")
    controller.create_dev_test_authored_module(module_root="grtarget")

    report = controller.record_port("K1", "K2")

    assert report.ok is True, report.message
    assert report.code == "authored_project_retargeted"
    assert controller.project.game == "K2"
    assert controller.project.source_game == "K1"
    assert controller.project.target_game == "K2"
    assert controller.project.extra_sections["authored_module"]["game"] == "K2"
    assert controller.command_history.undo_label == "Retarget K1 to K2"

    undo = controller.undo_map_studio_command()
    assert undo is not None
    assert controller.project.game == "K1"
    assert controller.project.target_game == "K1"
    assert controller.project.extra_sections["authored_module"]["game"] == "K1"

    redo = controller.redo_map_studio_command()
    assert redo is not None
    assert controller.project.game == "K2"
    assert controller.project.target_game == "K2"
    assert controller.project.extra_sections["authored_module"]["game"] == "K2"


def test_map_studio_export_panel_exposes_explicit_k1_k2_target_without_recursive_signal() -> None:
    _install_native_payload_paths()
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.export_panel import ModuleExportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleExportPanel()
    requested: list[str] = []
    panel.targetGameRequested.connect(requested.append)
    try:
        panel.set_target_game("K2", source_game="K1")
        assert panel.target_game_combo.currentData() == "K2"
        assert requested == []
        assert "Source K1 -> target K2" in panel.target_game_hint_label.text()

        panel.target_game_combo.setCurrentIndex(panel.target_game_combo.findData("K1"))
        panel._emit_target_game(panel.target_game_combo.currentIndex())
        assert requested == ["K1"]
    finally:
        panel.close()
        app.processEvents()

    display = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/export_panel.py"
    tools = ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/export_panel.py"
    assert display.read_bytes() == tools.read_bytes()
    window_source = (
        ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")
    assert "self.export_panel.targetGameRequested.connect(self._retarget_map_studio_export_game)" in window_source
    assert "def _retarget_map_studio_export_game" in window_source
    assert "report = self.controller.record_port(source, target)" in window_source
    assert "self.export_panel.set_target_game(" in window_source
