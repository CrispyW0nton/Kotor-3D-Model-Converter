"""Focused UI-routing contracts for the Custom KOTOR Head Builder."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from src.core.geometry.model_data import CharacterMode
from src.gui.qt_lib.panels.qt_character_builder_panel import (
    QtCharacterBuilderWindow,
)
from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel
from src.gui.qt_lib.panels.qt_workflow_rail import QtWorkflowRail
from src.gui.qt_lib.panels.qt_head_builder_workspace import (
    HEAD_BUILDER_STEPS,
    QtHeadBuilderProperties,
)
from src.gui.qt_lib.dialogs.qt_getting_started_window import TUTORIAL_PAGES
from src.gui.windows.application_core.shared.window_lifecycle import (
    WindowLifecycleMixin,
)
from src.gui.windows.qt_character_builder_mode_selector import (
    CHARACTER_BUILDER_MODES,
    QtCharacterBuilderModeSelector,
)


ROOT = Path(__file__).resolve().parents[1]
DISPLAY_GUI = (
    ROOT
    / "native"
    / "GhostRigger.Core.GUI.Display"
    / "Python"
    / "src"
    / "gui"
)


def test_selector_renders_a_stable_custom_head_builder_card() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    selector = QtCharacterBuilderModeSelector()
    try:
        assert tuple(CHARACTER_BUILDER_MODES) == (
            "native_kotor_character",
            "native_kotor_head",
            "custom_rigged_character",
        )
        object_names = {
            card.objectName()
            for card in selector.findChildren(QtWidgets.QGroupBox)
        }
        assert "characterBuilderModeCard_native_kotor_head" in object_names
        assert app is not None
    finally:
        selector.close()


def test_head_mode_has_a_distinct_truthful_eleven_stage_surface() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    rail = QtWorkflowRail()
    workspace = QtHeadBuilderProperties()
    try:
        rail.set_mode(CharacterMode.HEAD)
        assert rail.steps() == [
            (number, label)
            for number, label in HEAD_BUILDER_STEPS
        ]
        for number, label in HEAD_BUILDER_STEPS:
            assert workspace.set_step(number)
            assert workspace.title.text() == f"{number}. {label}"
        physics_page = workspace.findChild(
            QtWidgets.QWidget,
            "HeadBuilderStepPhysics",
        )
        assert physics_page is not None
        assert "excluded from this release" in " ".join(
            label.text() for label in physics_page.findChildren(QtWidgets.QLabel)
        )
        assert workspace.retail_summary.text() == "Retail observed: not tested"
        assert "personally observed" in workspace.user_confirmed.text().casefold()
        assert app is not None
    finally:
        workspace.close()
        rail.close()


def test_head_properties_accept_current_donor_snapshot_fields() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    workspace = QtHeadBuilderProperties()
    snapshot = SimpleNamespace(
        geometry_root_name="PFHA04",
        attachment_target_name="neck_g",
        supermodel="S_Female02",
        local_node_count=10,
        inherited_node_declaration=564,
        local_animation_names=("talk", "tlknorm"),
        skins=(SimpleNamespace(bone_palette=("head_g", "neck_g")),),
        retail_bb_min=(-5.0, -5.0, -1.0),
        retail_bb_max=(5.0, 5.0, 5.0),
        retail_radius=7.5,
        preview_bb_min=(-0.1, 0.0, 0.0),
        preview_bb_max=(0.1, 0.0, 0.2),
        game="K2",
        resref="PFHA04",
        resource_view="stock",
    )
    try:
        workspace.set_step(10)
        workspace.set_message("verifying project complete")
        workspace.set_donor_selection(SimpleNamespace(snapshot=snapshot))
        part = SimpleNamespace(
            name="head",
            part_id="part-head",
            material_name="P_GHSTH1",
            vertices=((0.0, 0.0, 0.0),),
            faces=((0, 0, 0),),
            topology=SimpleNamespace(
                border_edge_count=4,
                degenerate_face_count=0,
            ),
        )
        workspace.set_art_document(
            SimpleNamespace(
                source_path="custom_head.obj",
                source_format="OBJ",
                vertex_count=1,
                face_count=1,
                parts=(part,),
            ),
            SimpleNamespace(errors=(), warnings=()),
        )
        text = workspace.donor_contract.toPlainText()
        assert "Inherited node declaration: 564" in text
        assert "Retail model envelope: (-5.0, -5.0, -1.0)" in text
        assert workspace.part_tree.topLevelItem(0).text(4) == (
            "4 boundary; 0 degenerate"
        )
        assert workspace.status.wordWrap()
        assert isinstance(workspace.title.parent().layout(), QtWidgets.QVBoxLayout)
        assert app is not None
    finally:
        workspace.close()


def test_head_properties_expose_direct_vanilla_component_recipe() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    workspace = QtHeadBuilderProperties()
    actions: list[tuple[str, object]] = []
    workspace.actionRequested.connect(
        lambda action, payload: actions.append((action, payload))
    )
    snapshot = SimpleNamespace(
        geometry_root_name="PFHA04",
        attachment_target_name="neck_g",
        supermodel="S_Female03",
        local_node_count=38,
        inherited_node_declaration=564,
        local_animation_names=(),
        skins=(SimpleNamespace(bone_palette=("head_g", "neck_g")),),
        retail_bb_min=(-5.0, -5.0, -1.0),
        retail_bb_max=(5.0, 5.0, 5.0),
        retail_radius=7.5,
        preview_bb_min=(-0.1, 0.0, 0.0),
        preview_bb_max=(0.1, 0.0, 0.2),
        game="K2",
        resref="PFHA04",
        resource_view="stock_only",
    )
    try:
        workspace.set_step(3)
        workspace.set_donor_selection(SimpleNamespace(snapshot=snapshot))
        assert {
            field.text()
            for field in workspace.component_source_fields.values()
        } == {"PFHA04"}
        workspace.component_source_fields["face"].setText("PFHA01")
        workspace.component_source_fields["eyes"].setText("PFHA02")
        workspace.component_source_fields["eyelashes"].setText("PFHA03")
        workspace.component_source_fields["hair"].setText("PFHA04")
        button = workspace.findChild(
            QtWidgets.QPushButton,
            "HeadBuilderBuildComponentsButton",
        )
        assert button is not None
        button.click()
        assert actions[-1][0] == "build_component_recipe"
        assert actions[-1][1]["face_resref"] == "PFHA01"
        assert actions[-1][1]["eyes_resref"] == "PFHA02"
        workspace.set_component_result(
            SimpleNamespace(
                report=SimpleNamespace(
                    source_resrefs={
                        "face": "PFHA01",
                        "mouth": "PFHA01",
                        "eyes": "PFHA02",
                        "eyelashes": "PFHA03",
                        "hair": "PFHA04",
                    },
                    target_node_ordinals=(25, 27, 28, 29, 30),
                    blocking_difference_paths=(),
                )
            )
        )
        assert "Accepted vanilla combination" in (
            workspace.component_summary.text()
        )
        donor_page = workspace.findChild(
            QtWidgets.QWidget,
            "HeadBuilderStepNativeDonor",
        )
        copy = " ".join(
            label.text() for label in donor_page.findChildren(QtWidgets.QLabel)
        ).casefold()
        assert "ithorians are intentionally unsupported" in copy
        assert "full-body rodian" in copy
        assert app is not None
    finally:
        workspace.close()


def test_character_studio_head_mode_mounts_production_workspace() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtCharacterBuilderWindow()
    try:
        window.open_mode(CharacterMode.HEAD)
        assert window._right_stack.currentWidget() is window.head_builder_properties
        assert window._bottom_stack.currentWidget() is window.head_builder_evidence
        assert window.head_builder_assets.isVisibleTo(window)
        assert window.head_builder_controller.service.project.current_step == 1
        assert len(window.rail.steps()) == 11
        assert all(action.isVisible() for action in window._head_toolbar_actions)
        assert app is not None
    finally:
        window.deleteLater()
        app.processEvents()


def test_leaving_head_mode_restores_body_controls_and_copy() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    inspector = QtInspectorPanel()
    try:
        inspector.set_active_mode(CharacterMode.HEAD)
        inspector.set_active_mode(CharacterMode.HEADLESS_BODY)
        inspector.set_step(1)
        assert inspector._title_label.text() == "1. Choose Base + Load Mesh"
        assert inspector._load_button.text() == "Load Custom Mesh…"
        assert not inspector._skeleton_template_group.isHidden()
        assert not inspector._import_fit_group.isHidden()
        assert inspector._head_donor_stage_group.isHidden()
        assert not inspector._build_skeleton_group.isHidden()
        assert inspector._check_model_button.text() == "Check Model"
        assert not inspector._body_motion_content.isHidden()
        assert inspector._head_transfer_stage_group.isHidden()
        assert not inspector._preview_attachment_group.isHidden()
        assert not inspector._body_attachment_group.isHidden()
        assert not inspector._body_preview_content.isHidden()
        assert inspector._head_face_palette.isHidden()
        assert app is not None
    finally:
        inspector.close()


def test_public_head_entry_selects_head_without_replacing_scene() -> None:
    calls: list[tuple[object, bool, str]] = []

    class WindowDouble:
        def _apply_mode(self, mode: object, *, locked: bool, source: str) -> None:
            calls.append((mode, locked, source))

    target = QtCharacterBuilderWindow.open_mode(
        WindowDouble(),
        "native_kotor_head",
    )

    assert getattr(target, "name", "") == "HEAD"
    assert calls == [(target, True, "public_entry")]
    source = inspect.getsource(QtCharacterBuilderWindow.open_mode)
    assert "_new_scene" not in source
    assert "scene.clear" not in source


def test_head_entry_aliases_reuse_the_existing_native_window() -> None:
    class WindowDouble:
        def __init__(self) -> None:
            self.opened: list[object] = []
            self.shown = 0

        def open_mode(self, mode: object) -> None:
            self.opened.append(mode)

        def set_renderer_settings(self, _settings: object) -> None:
            pass

        def show(self) -> None:
            self.shown += 1

        def raise_(self) -> None:
            pass

        def activateWindow(self) -> None:
            pass

    class HostDouble:
        def __init__(self) -> None:
            self._character_builder_window = WindowDouble()
            self.settings_data = {}
            self.opened: list[object] = []

        def _show_native_character_builder(self, mode: object = "") -> None:
            self.opened.append(mode)

        def _show_custom_rigged_character_builder(self) -> None:
            raise AssertionError("Custom-rig route should not be selected")

    host = HostDouble()
    for alias in (
        "native_kotor_head",
        "head_builder",
        "custom_head",
        "modular_head",
    ):
        WindowLifecycleMixin._open_qt_character_builder_window(host, alias)
    assert host.opened == ["head", "head", "head", "head"]

    reused = host._character_builder_window
    WindowLifecycleMixin._show_native_character_builder(host, "head")
    assert host._character_builder_window is reused
    assert reused.opened == ["head"]
    assert reused.shown == 1


def test_active_workflow_and_generic_handlers_are_mode_correct() -> None:
    class WorkflowDouble:
        def __init__(self, head: bool) -> None:
            self.head = head

        def _is_scene_mode(self, value: str) -> bool:
            return self.head and value == "head"

        @staticmethod
        def _head_workflow_module() -> str:
            return "head-workflow"

        @staticmethod
        def _body_workflow_module() -> str:
            return "body-workflow"

    assert (
        QtCharacterBuilderWindow._workflow_module(WorkflowDouble(True))
        == "head-workflow"
    )
    assert (
        QtCharacterBuilderWindow._workflow_module(WorkflowDouble(False))
        == "body-workflow"
    )

    source = (
        DISPLAY_GUI / "panels" / "qt_character_builder_panel.py"
    ).read_text(encoding="utf-8")
    assert '"Load Custom Head Art" if is_head_mode else "Load Body Model"' in source
    assert "result = _wf.load_head(" in source
    assert 'getattr(_wf, "check_head", None)' in source
    assert 'getattr(_wf, "validate_for_export_head", None)' in source
    assert "result = _wf.export_head_scene(" in source
    assert '"HEAD_BINARY_PENDING"' in source


def test_main_shell_tutorial_and_external_aliases_have_direct_head_routes() -> None:
    chrome_source = (
        DISPLAY_GUI / "windows" / "application_core" / "shared" / "window_chrome.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        DISPLAY_GUI / "windows" / "application_core" / "shared" / "window_lifecycle.py"
    ).read_text(encoding="utf-8")
    main_source = (
        DISPLAY_GUI / "windows" / "qt_main_window.py"
    ).read_text(encoding="utf-8")

    assert "self.head_builder_action = QtGui.QAction(" in chrome_source
    assert '"Custom KOTOR Head Builder..."' in chrome_source
    assert '"Ctrl+Shift+H"' in chrome_source
    assert "tools_menu.addAction(self.head_builder_action)" in chrome_source
    assert '"CommandStripHeadBuilderButton"' in chrome_source
    assert (
        'self._open_qt_character_builder_window("native_kotor_head")'
        in lifecycle_source
    )
    for alias in (
        '"native_kotor_head": lambda:',
        '"head_builder": lambda:',
        '"custom_head": lambda:',
        '"modular_head": lambda:',
    ):
        assert alias in main_source

    pages = {page.key: page for page in TUTORIAL_PAGES}
    assert pages["head_builder"].route == "head_builder"
    assert pages["head_builder"].route_label == "Open Custom Head Builder"
    assert "user-confirmed retail test" in " ".join(
        pages["head_builder"].steps
    )
