"""Retarget Workbench UI placement regression tests."""

from __future__ import annotations

import inspect
import os

from PySide6 import QtWidgets


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _sample_source_clip():
    from src.core.retargeting.source_animation import (
        SourcePose,
        SourceSkeletonClip,
        SourceSkeletonNode,
        Transform,
    )

    root_local = Transform()
    child_local = Transform(position=(0.0, 1.0, 0.0))
    root_global = Transform()
    child_global = Transform(position=(0.0, 1.0, 0.0))
    nodes = [
        SourceSkeletonNode("Root", None, 0, root_local, root_global),
        SourceSkeletonNode("RHand", "Root", 1, child_local, child_global),
    ]
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="demo.fbx",
        clip_name="Demo UE Idle",
        duration_seconds=0.5,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose, pose],
    )


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


def test_retarget_workbench_uses_internal_docks_and_quiet_viewports() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        docks = getattr(window, "_retarget_docks", {})
        assert set(docks) == {"animations", "mapping", "information", "transfer", "overrides"}
        assert docks["animations"].widget() is window.panel.animation_section
        assert docks["mapping"].widget() is window.panel.mapping_section
        assert docks["information"].widget() is window.panel.info_section
        assert docks["transfer"].widget() is window.panel.transfer_section
        assert window.findChild(QtWidgets.QDockWidget, "RetargetOverridesDock") is docks["overrides"]

        for viewport in (window.source_viewport, window.target_viewport):
            assert viewport.viewport_role == "retarget"
            toolbar = viewport.findChild(QtWidgets.QFrame, "ViewportToolbar")
            assert toolbar is not None
            assert viewport.viewport_toolbar_scroll.isVisible() is False
            assert toolbar.isVisible() is False
            assert viewport.transform_typein_bar.isVisible() is False
            assert viewport._viewcube_widget.isVisible() is False
    finally:
        window.close()


def test_retarget_workbench_view_menu_toggles_viewport_chrome() -> None:
    app = _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.show()
        app.processEvents()

        assert window.viewport_toolbar_action.isCheckable()
        assert window.viewcube_action.isCheckable()
        assert window.transform_typein_action.isCheckable()
        assert window.viewport_toolbar_action.isChecked() is False
        assert window.viewcube_action.isChecked() is False
        assert window.transform_typein_action.isChecked() is False

        window.viewport_toolbar_action.trigger()
        window.viewcube_action.trigger()
        window.transform_typein_action.trigger()
        for viewport in (window.source_viewport, window.target_viewport):
            toolbar = viewport.findChild(QtWidgets.QFrame, "ViewportToolbar")
            assert viewport.viewport_toolbar_chrome_visible is True
            assert viewport.viewcube_chrome_visible is True
            assert viewport.transform_typein_chrome_visible is True
            assert toolbar.isVisible() is True
            assert viewport.viewport_toolbar_scroll.isVisible() is True
            assert viewport.transform_typein_bar.isVisible() is True
        assert window.viewport_toolbar_action.isChecked() is True
        assert window.viewcube_action.isChecked() is True
        assert window.transform_typein_action.isChecked() is True
    finally:
        window.close()


def test_retarget_window_source_clip_preview_populates_source_viewport() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_clip_preview(_sample_source_clip())

        assert window.source_viewport.model is not None
        assert window.source_viewport.model.node_count() == 3
        assert getattr(window.source_viewport.model, "_gr_source_clip_preview") is True
        assert "Demo UE Idle" in window.panel.source_label.text()
        assert "2 nodes" in window.panel.source_label.text()
        assert window.source_viewport.bones_button.isChecked() is True
        assert window.source_viewport._renderer.show_bones is True
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
