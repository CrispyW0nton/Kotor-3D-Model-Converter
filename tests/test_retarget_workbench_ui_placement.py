"""Retarget Workbench UI placement regression tests."""

from __future__ import annotations

import inspect
import os

from PySide6 import QtWidgets


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_retarget_workbench_controls_live_in_retarget_window() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        assert window.findChild(QtWidgets.QComboBox, "retargetModeComboBox") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchStatusLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchInputsLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchOutputLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchRuntimeLabel") is not None
        assert window.findChild(QtWidgets.QComboBox, "kotorOutputNameModeComboBox") is not None
        assert window.findChild(QtWidgets.QComboBox, "targetKotorAnimationSlotComboBox") is not None
        assert window.findChild(QtWidgets.QLineEdit, "customKotorAnimationNameLineEdit") is not None
        assert window.findChild(QtWidgets.QLineEdit, "outputUnrealClipNameLineEdit") is not None
    finally:
        window.close()


def test_retarget_workbench_source_target_boxes_have_search_and_external_import() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    rows = [
        {"game": "K1", "resref": "pmbam", "category": "Character", "module_code": ""},
        {"game": "K2", "resref": "p_kreia", "category": "Character", "module_code": ""},
    ]
    window = QtAnimationRetargetWindow()
    try:
        window.set_library_rows(rows)
        panel = window.panel
        assert panel.source_library_combo.isEditable()
        assert panel.target_library_combo.isEditable()
        assert panel.source_library_combo.findText("K1 : pmbam : Character") >= 0
        assert panel.target_library_combo.findText("K2 : p_kreia : Character") >= 0

        emitted: list[tuple[str, str]] = []
        window.sourceGameLibraryRequested.connect(lambda row: emitted.append(("source", row["resref"])))
        window.targetGameLibraryRequested.connect(lambda row: emitted.append(("target", row["resref"])))
        panel.source_library_combo.setCurrentIndex(panel.source_library_combo.findText("K1 : pmbam : Character"))
        panel.target_library_combo.setCurrentIndex(panel.target_library_combo.findText("K2 : p_kreia : Character"))

        panel._emit_or_request_library_row("source")
        panel._emit_or_request_library_row("target")

        assert emitted == [("source", "pmbam"), ("target", "p_kreia")]
        assert any(button.text() == "Import External File..." for button in window.findChildren(QtWidgets.QPushButton))
    finally:
        window.close()


def test_main_viewport_header_does_not_construct_retarget_workbench_controls() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    header_source = inspect.getsource(QtGhostRiggerMainWindow._make_header)
    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)

    assert "retargetModeComboBox" not in header_source
    assert "retargetWorkbenchStatusLabel" not in header_source
    assert "retargetWorkbenchInputsLabel" not in header_source
    assert "retargetWorkbenchOutputLabel" not in header_source
    assert "retargetWorkbenchRuntimeLabel" not in header_source
    assert "kotorOutputNameModeComboBox" not in command_source
    assert "targetKotorAnimationSlotComboBox" not in command_source
    assert "customKotorAnimationNameLineEdit" not in command_source
    assert "outputUnrealClipNameLineEdit" not in command_source
    assert "retargetOutputDisplayLabelLineEdit" not in command_source
    assert "Preview Retarget" not in command_source
    assert "Export Preview" not in command_source


def test_main_window_routes_retarget_window_preview_to_workbench_controller() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout) + inspect.getsource(QtGhostRiggerMainWindow._retarget_workbench_preview_from_window)

    assert "previewRequested.connect(self._retarget_workbench_preview_from_window)" in source
    assert "controller.set_source_kotor_animation_slot(anim_name)" in source
    assert "self._preview_retarget_animation()" in source
