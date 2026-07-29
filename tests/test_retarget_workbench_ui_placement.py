"""Retarget Workbench UI placement regression tests."""

from __future__ import annotations

import inspect
import os

from PySide6 import QtCore, QtWidgets


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


def _sample_kotor_animation_model():
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode

    root = ModelNode(name="root")
    return KotorModel(
        name="N_Test",
        root_node=root,
        animations=[
            Animation(name="pause1", length=1.0),
            Animation(name="walk", length=1.5),
        ],
    )


def test_retarget_workbench_controls_live_in_retarget_window() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        assert window.windowTitle() == "GhostStudio — Animation Retargeting Workbench"
        assert not window.preview_action.icon().isNull()
        assert not window.apply_action.icon().isNull()
        assert window.preview_action.text() == "Preview Selected Animation"
        assert window.apply_action.text() == "Apply Selected to Target"
        assert window.findChild(QtWidgets.QComboBox, "retargetModeComboBox") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchStatusLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchInputsLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchOutputLabel") is not None
        assert window.findChild(QtWidgets.QLabel, "retargetWorkbenchRuntimeLabel") is not None
        assert window.findChild(QtWidgets.QComboBox, "kotorOutputNameModeComboBox") is not None
        assert window.findChild(QtWidgets.QComboBox, "targetKotorAnimationSlotComboBox") is not None
        assert window.findChild(QtWidgets.QLineEdit, "customKotorAnimationNameLineEdit") is not None
        assert window.findChild(QtWidgets.QLineEdit, "outputUnrealClipNameLineEdit") is not None
        assert window.findChild(QtWidgets.QCheckBox, "retargetBonesToggle") is not None
        assert window.findChild(QtWidgets.QCheckBox, "retargetGizmoToggle") is not None
        assert window.findChild(QtWidgets.QCheckBox, "retargetRootMotionToggle") is not None
        guidance = window.findChild(QtWidgets.QLabel, "retargetWorkflowGuidance")
        assert guidance is not None
        assert "1 Load an animated source" in guidance.text()
        assert "readiness checks pass" in guidance.text()
        assert window.statusBar().currentMessage() == "Choose a source and target to begin."
        output_controls = window.findChild(QtWidgets.QFrame, "retargetOutputGlobalControls")
        assert output_controls.isHidden() is False
        output_labels = [
            label.text()
            for label in output_controls.findChildren(QtWidgets.QLabel)
        ]
        assert output_labels == ["Output policy", "KOTOR slot", "Custom name", "Unreal clip", "Notes"]
        window.show()
        QtWidgets.QApplication.processEvents()
        assert output_controls.isVisible() is True
        assert not any(
            box.title() == "Source Bone / Target Bone"
            for box in window.findChildren(QtWidgets.QGroupBox)
        )
        assert window.findChild(QtWidgets.QPushButton, "playSelectedRetargetAnimationButton") is not None
        assert window.findChild(QtWidgets.QPushButton, "pauseRetargetAnimationButton") is not None
        assert window.findChild(QtWidgets.QPushButton, "stopRetargetAnimationButton") is not None
        assert window.findChild(QtWidgets.QPushButton, "exportAssignedRetargetAnimationsButton") is not None
        assert window.findChild(QtWidgets.QPushButton, "playSelectedRetargetAnimationButton").isEnabled() is False
        assert window.findChild(QtWidgets.QPushButton, "retargetSelectedAnimationButton").isEnabled() is False
        export_button = window.findChild(QtWidgets.QPushButton, "exportAssignedRetargetAnimationsButton")
        assert export_button.isEnabled() is False
        assert "Load a source and target" in export_button.toolTip()

        window.panel.set_source_model(_sample_kotor_animation_model())
        window.panel.set_target_model(_sample_kotor_animation_model())
        window.panel.anim_list.setCurrentRow(0)
        assert window.findChild(QtWidgets.QPushButton, "playSelectedRetargetAnimationButton").isEnabled() is True
        assert window.findChild(QtWidgets.QPushButton, "retargetSelectedAnimationButton").isEnabled() is True
        assert export_button.isEnabled() is True
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


def test_retarget_workbench_keeps_assignment_ui_and_quiet_viewports() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        assert getattr(window, "_retarget_docks", {}) == {}
        assert window.panel.animation_section is not None
        assert window.panel.assignment_section is not None
        assert window.panel.info_section is not None
        assert window.panel.transfer_section is not None
        assert not any(
            box.title() == "Source Bone / Target Bone"
            for box in window.findChildren(QtWidgets.QGroupBox)
        )

        for viewport in (window.source_viewport, window.target_viewport):
            assert viewport.viewport_role == "retarget"
            assert viewport.map_studio_authoring_chrome_enabled is False
            assert viewport.viewport_map_studio_modeling_tabs is None
            assert viewport.findChild(
                QtWidgets.QTabWidget,
                "ViewportToolbarMapStudioModelingTabs",
            ) is None
            toolbar = viewport.findChild(QtWidgets.QFrame, "ViewportToolbar")
            assert toolbar is not None
            assert viewport.viewport_toolbar_scroll.isVisible() is False
            assert toolbar.isVisible() is False
            assert viewport.transform_typein_bar.isVisible() is False
            assert viewport._viewcube_widget.isVisible() is False
    finally:
        window.close()


def test_retarget_workbench_viewports_keep_independent_renderer_surfaces() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        assert not hasattr(window, "_shared_gpu_renderer")
        assert window.source_viewport._owns_gpu_renderer is True
        assert window.target_viewport._owns_gpu_renderer is True
        assert window.source_viewport.canvas is not window.target_viewport.canvas
    finally:
        window.close()


def test_retarget_workbench_animation_dock_exposes_playback_controls() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_model(_sample_kotor_animation_model())

        play = window.findChild(QtWidgets.QPushButton, "previewSourceAnimationButton")
        pause = window.findChild(QtWidgets.QPushButton, "pauseSourceAnimationButton")
        stop = window.findChild(QtWidgets.QPushButton, "stopSourceAnimationButton")
        loop = window.findChild(QtWidgets.QCheckBox, "loopSourceAnimationCheckBox")

        assert play is not None
        assert pause is not None
        assert stop is not None
        assert loop is not None
        assert loop.isChecked() is True

        emitted: list[tuple[str, bool]] = []
        window.panel.animationPreviewRequested.connect(lambda name, should_loop: emitted.append((name, should_loop)))
        window.panel.select_animation("walk")
        assert play.isEnabled() is True
        assert pause.isEnabled() is True
        assert stop.isEnabled() is True
        loop.setChecked(False)
        play.click()

        assert emitted == [("walk", False)]
        window.preview_source_animation("walk", loop=False)
        assert window._source_preview_engine is not None
        assert window._source_preview_engine.current_animation.name == "walk"
        assert window._source_preview_timer.isActive()
        window.stop_source_animation_preview(clear_pose=True)
        assert window._source_preview_engine is None
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


def test_retarget_window_overlay_toggles_scope_source_clip_preview() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_retarget_bones_visible(False)
        window.set_retarget_gizmo_visible(False)
        window.set_source_clip_preview(_sample_source_clip())

        for viewport in (window.source_viewport, window.target_viewport):
            assert viewport.bones_button.isChecked() is False
            assert viewport._renderer.show_bones is False
            assert viewport.joint_dot_enabled is False
            assert viewport.gimbal_button.isChecked() is False
            assert viewport._renderer.show_gimbal is False
            assert viewport._transform_gizmo.visible is False

        window.set_retarget_bones_visible(True)
        window.set_retarget_gizmo_visible(True)
        assert window.source_viewport._renderer.show_bones is True
        assert window.target_viewport._renderer.show_bones is True
        assert window.source_viewport._renderer.show_gimbal is True
        assert window.target_viewport._renderer.show_gimbal is True
    finally:
        window.close()


def test_retarget_window_animation_rows_have_assignable_output_names() -> None:
    _qapp()
    from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_clip_preview(_sample_source_clip())

        item = window.panel.anim_list.currentItem()
        assert item is not None
        assert item.checkState() == QtCore.Qt.Checked
        assert window.panel.selected_animation() == "Demo UE Idle"
        assignment = window.current_animation_assignment()
        assert assignment["source_animation"] == "Demo UE Idle"
        assert assignment["output_name"] == "Demo_UE_Idle"
        assert assignment["output_mode"] == KotorOutputAnimationNameMode.CUSTOM_PATCH.value

        window.set_animation_assignment(
            "Demo UE Idle",
            output_name="ca_idle_01",
            output_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        )

        assignment = window.current_animation_assignment()
        assert assignment["output_name"] == "ca_idle_01"
        assert "ca_idle_01" in item.text()

        window.set_source_clip_preview(_sample_source_clip())
        assignment = window.current_animation_assignment()
        assert assignment["output_name"] == "ca_idle_01"
    finally:
        window.close()


def test_double_clicking_source_animation_notifies_retarget_controller_path() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        played: list[str] = []
        window.sourceAnimationPlayRequested.connect(played.append)
        window.set_source_clip_preview(_sample_source_clip())

        item = window.panel.anim_list.currentItem()
        assert item is not None
        window.panel.anim_list.itemDoubleClicked.emit(item)

        assert played == ["Demo UE Idle"]
        assert window.source_viewport._renderer._anim_pose is not None
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

    source = inspect.getsource(QtGhostRiggerMainWindow._ensure_animation_retarget_window) + inspect.getsource(QtGhostRiggerMainWindow._retarget_workbench_preview_from_window)

    assert "previewRequested.connect(self._retarget_workbench_preview_from_window)" in source
    assert "controller.set_source_kotor_animation_slot(anim_name)" in source
    assert "self._preview_retarget_animation()" in source


def test_workbench_source_playback_auto_retargets_to_workbench_target_viewport() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_workbench_play_source_animation_from_window)
    adapter_source = inspect.getsource(QtGhostRiggerMainWindow._ensure_retarget_workbench_target_viewport_adapter)

    assert "window.play_source_clip_animation(anim_name)" in source
    assert "self._apply_retarget_workbench_animation_assignment(anim_name)" in source
    assert "self._ensure_retarget_workbench_target_viewport_adapter()" in source
    assert "controller.preview(auto_play=False, show_node_overlay=show_nodes)" in source
    assert "_retarget_workbench_sync_target_time_from_source" in inspect.getsource(
        QtGhostRiggerMainWindow._ensure_animation_retarget_window
    )
    assert "adapter.set_time(float(time_seconds))" in inspect.getsource(
        QtGhostRiggerMainWindow._retarget_workbench_sync_target_time_from_source
    )
    assert "window.target_viewport" in adapter_source
    assert "preview_controller.viewport = adapter" in adapter_source
    assert "workbench_controller.viewport = adapter" in adapter_source


def test_workbench_status_syncs_auto_profile_mapping_table() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    status_source = inspect.getsource(QtGhostRiggerMainWindow._apply_retarget_workbench_mode_status)
    mapping_source = inspect.getsource(QtGhostRiggerMainWindow._sync_retarget_workbench_profile_mapping)

    assert "self._sync_retarget_workbench_profile_mapping()" in status_source
    assert "window.set_mapping_report" in mapping_source
    assert "matched_count=len(mapping)" in mapping_source


def test_workbench_assignment_helper_pushes_row_output_naming_to_controller() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._apply_retarget_workbench_animation_assignment)

    assert "window.current_animation_assignment()" in source
    assert "controller.set_custom_kotor_animation_name(output_name)" in source
    assert "controller.set_target_kotor_animation_slot(output_name)" in source


def test_workbench_apply_button_routes_to_verified_export_path() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    build_layout_source = inspect.getsource(QtGhostRiggerMainWindow._ensure_animation_retarget_window)
    apply_source = inspect.getsource(QtGhostRiggerMainWindow._retarget_workbench_apply_from_window)

    assert "applyRequested.connect(self._retarget_workbench_apply_from_window)" in build_layout_source
    assert "self._retarget_workbench_preview_from_window(anim_name)" in apply_source
    assert "self._export_retarget_preview()" in apply_source


def test_target_slot_refresh_syncs_vanilla_output_without_overwriting_custom_mode() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._refresh_target_kotor_animation_slots)

    assert "controller.set_target_kotor_animation_slot(selected)" in source
    assert "KotorOutputAnimationNameMode.CUSTOM_PATCH" in source
    assert "not is_custom_output" in source


def test_workbench_stop_pauses_target_preview_adapter() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_stop)

    assert "_retarget_target_viewport_adapter" in source
    assert "adapter.pause()" in source
    assert "clear_poses()" in source
