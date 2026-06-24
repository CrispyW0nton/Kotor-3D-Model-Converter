from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_t2600_module_editor_icon_opens_map_studio_level_editor() -> None:
    """The existing main-screen Module Editor action is the Map Studio entry point."""

    chrome_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/window_chrome.py"
    )
    viewport_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/construction.py"
    )
    resource_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/resource_panels.py"
    )
    integration_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/"
        "integration/tool_integration_registry.py"
    )

    assert 'QtGui.QAction(self._icon("modular"), "Open Map Studio Level Editor", self)' in chrome_source
    assert "self.modules_action.triggered.connect(self._open_map_studio_modeling_workspace)" in chrome_source
    assert '"CommandStripMapStudioButton"' in chrome_source
    assert "ViewportToolbarMapStudioModelingButton" in chrome_source
    assert "modeling_button.clicked.connect(self._open_map_studio_modeling_workspace)" in chrome_source
    assert "ViewportToolbarMapStudioModelingTabs" in chrome_source
    assert "ViewportToolbarMapStudioModelingScrollArea" in chrome_source
    assert "ViewportToolbarMapStudioBlockoutScrollArea" in chrome_source
    assert 'tabs.addTab(tab, "Modeling")' in chrome_source
    assert "ViewportToolbarMapStudioModeButton_{mode.lower()}" in chrome_source
    assert "ViewportToolbarMapStudioToolButton_{key}" in chrome_source
    assert "ViewportToolbarMapStudioBlockoutTab" in chrome_source
    assert 'tabs.addTab(blockout_tab, "Blockout")' in chrome_source
    assert "ViewportToolbarMapStudioBlockoutButton_{key}" in chrome_source
    assert "take_viewport_modeling_tabs" in chrome_source
    assert "def _make_map_studio_modeling_tabs" in viewport_source
    assert "self.viewport_map_studio_modeling_tabs" in viewport_source
    assert "ViewportToolbarMapStudioModelingTabs" in viewport_source
    assert "ViewportToolbarMapStudioModelingScrollArea" in viewport_source
    assert "ViewportToolbarMapStudioBlockoutScrollArea" in viewport_source
    assert 'tabs.addTab(modeling_tab, "Modeling")' in viewport_source
    assert "ViewportToolbarMapStudioBlockoutTab" in viewport_source
    assert 'tabs.addTab(blockout_tab, "Blockout")' in viewport_source
    assert "def take_viewport_modeling_tabs" in viewport_source
    assert "def _open_map_studio_mode_from_toolbar" in viewport_source
    assert "def _run_map_studio_command_from_toolbar" in viewport_source
    for mode_label in ("Object", "Vertex", "Edge", "Face", "Terrain", "Walkmesh"):
        assert f'"{mode_label}"' in chrome_source
    for action_key in (
        "duplicate_selected",
        "delete_selected",
        "extrude",
        "bevel",
        "triangulate",
        "paint_material",
        "paint_wok",
    ):
        assert f'"{action_key}"' in chrome_source
        assert f'"{action_key}"' in viewport_source
    for tool_label in ("Material", "WOK"):
        assert f'"{tool_label}"' in chrome_source
        assert f'"{tool_label}"' in viewport_source
    for blockout_key in (
        "blockout_room",
        "floor",
        "wall",
        "cube",
        "ramp",
        "stairs",
        "door_frame",
        "arch",
        "terrain_patch",
    ):
        assert f'"{blockout_key}"' in chrome_source
    for blockout_label in ("Room", "Floor", "Wall", "Cube", "Ramp", "Stairs", "Doorway", "Arch", "Terrain"):
        assert f'"{blockout_label}"' in chrome_source
    assert "def _open_map_studio_mode_from_viewport" in chrome_source
    assert "def _run_map_studio_viewport_modeling_command" in chrome_source
    assert 'getattr(window, "select_map_studio_authored_context", None)' in chrome_source
    assert 'getattr(window, "_execute_map_studio_tool_belt_command", None)' in chrome_source
    assert 'getattr(window, "move_map_studio_authored_primitive_selection", None)' in chrome_source
    assert 'execute("duplicate_selected")' in chrome_source
    assert 'execute("delete_selected")' in chrome_source
    assert "The Module Editor icon opens this unified Map Studio workspace" in resource_source
    assert "def _open_map_studio_modeling_workspace" in resource_source
    assert "focus_map_studio_modeling_workspace" in resource_source
    assert "Map Studio could not open" in resource_source
    assert "Module Editor icon opens the existing Level Editor as Map Studio" in integration_source


def test_t2600_level_editor_window_is_branded_as_map_studio_without_new_surface() -> None:
    """Map Studio remains the existing Level Editor window and KMAP workflow."""

    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    assert "class ModuleEditorWindow(QtWidgets.QMainWindow)" in window_source
    assert 'self.setWindowTitle("GhostRigger Map Studio - Level Editor")' in window_source
    assert "GhostRigger Map Studio - Level Editor - {self.project.name}" in window_source
    assert "Map Studio is GhostRigger's Level Editor opened from the Module Editor icon" in window_source
    assert "mapStudioLevelEditorScopeLabel" in window_source
    assert "KMAP terrain, rooms, walkmesh, placements, validation, staged export, install handoff, and game proof" in window_source
    assert "Map Studio Level Editor ready." in window_source
    assert "self.controller = ModuleEditorController()" in window_source
    assert "def focus_map_studio_modeling_workspace" in window_source
    assert "def select_map_studio_authored_context" in window_source
    assert "self.controller.set_map_studio_active_selection" in window_source
    assert "def move_map_studio_authored_primitive_selection" in window_source
    assert "self.controller.move_authored_room_primitive" in window_source
    assert "edit Move X/Y/Z, then click Move again" in window_source
    assert "def delete_map_studio_authored_primitive_selection" in window_source
    assert "self.controller.remove_authored_room_primitive" in window_source
    assert "direct_command_actions" in window_source
    for action_key in (
        "select",
        "move",
        "duplicate_selected",
        "delete_selected",
        "object_grid_snap",
        "object_vertex_snap",
        "center_pivot",
        "freeze_transform",
        "paint_material",
        "paint_wok",
    ):
        assert f'"{action_key}"' in window_source


def test_t2600_main_screen_map_studio_action_opens_window_and_tool_belt_runtime() -> None:
    """The visible Module/Map Studio action opens the real window with usable modeling tools."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.application_core.shared.resource_panels import ResourcePanelsMixin
    from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class Host(QtWidgets.QMainWindow, WindowChromeMixin, ResourcePanelsMixin):
        def __init__(self) -> None:
            super().__init__()
            self.settings_data = {}
            self._library_rows = []
            self._resource_manager = None
            self.theme_manager = None
            self.layout_manager = None
            self.module_editor_window = None

        def _icon(self, *_args):
            return QtGui.QIcon()

        def _configure_dock_toggle_action(self, *_args, **_kwargs) -> None:
            return None

        def _get_resource_manager(self):
            return None

        def _log(self, *_args, **_kwargs) -> None:
            return None

        def __getattr__(self, name: str):
            if name.startswith("_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    host = Host()
    try:
        host._build_actions()
        host.modules_action.trigger()
        app.processEvents()

        window = host.module_editor_window
        assert window is not None
        assert window.isVisible()
        assert "Map Studio" in window.windowTitle()
        assert window.minimumWidth() <= 1400
        assert window.minimumHeight() <= 800
        assert window.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioTopToolbarScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioToolBeltScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioCustomToolBeltScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioWorkflowTabsScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioViewportPanelScrollArea") is None
        embedded_viewport = window.findChild(QtWidgets.QWidget, "MapStudioViewportWidget")
        assert embedded_viewport is not None
        assert embedded_viewport.property("_gr_suppress_renderer_diagnostics") is True
        assert embedded_viewport.property("_gr_map_studio_clean_viewport") is True
        presentation = getattr(embedded_viewport, "_map_studio_viewport_presentation", {})
        assert presentation.get("clean_display") is True
        assert presentation.get("subtle_room_outlines") is True
        assert presentation.get("show_room_guides") is False
        assert presentation.get("show_transform_dimensions") is False
        assert embedded_viewport.minimumHeight() >= 320
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioRightTabsScrollArea") is not None
        assert window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget") is not None
        for action_key in ("floor", "wall", "cube", "ramp", "stairs", "door_frame", "arch", "terrain_patch"):
            assert window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
        for action_key in ("select", "move", "duplicate_selected", "delete_selected", "paint_material", "paint_wok"):
            assert window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
    finally:
        window = getattr(host, "module_editor_window", None)
        if window is not None:
            window.close()
        host.close()


def test_t2600_real_main_window_exposes_modeling_tabs_and_opens_map_studio_runtime() -> None:
    """The actual Qt main window exposes the Map Studio belt and opens the Level Editor."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        icon_only_controls = [
            button
            for button in (
                *window.findChildren(QtWidgets.QToolButton),
                *window.findChildren(QtWidgets.QPushButton),
            )
            if button.property("_gr_ignore_layout_button_mode") is True
            and not str(button.text() or "").strip()
            and button.iconSize().width() > 0
        ]
        assert icon_only_controls
        blank_controls = [
            button.objectName() or str(button.toolTip() or button.property("_gr_full_text") or "<unnamed>")
            for button in icon_only_controls
            if button.icon().isNull()
        ]
        assert blank_controls == []

        command_icon = window.findChild(QtWidgets.QToolButton, "CommandStripMapStudioButton")
        assert command_icon is not None
        assert command_icon.toolTip() == "Open Map Studio Level Editor"
        assert window.findChild(QtWidgets.QToolButton, "ViewportToolbarMapStudioModelingButton") is not None
        top_toolbar = window.findChild(QtWidgets.QToolBar, "ReservedTopToolbar")
        assert top_toolbar is not None
        modeling_tabs = window.findChild(QtWidgets.QTabWidget, "ViewportToolbarMapStudioModelingTabs")
        assert modeling_tabs is not None
        assert modeling_tabs.isVisible()
        assert modeling_tabs.minimumHeight() > 0
        default_row = window.findChild(QtWidgets.QWidget, "ViewportToolbarDefaultRow")
        assert default_row is not None
        toolbar_band = window.findChild(QtWidgets.QFrame, "ViewportToolbarBand")
        assert toolbar_band is not None
        assert toolbar_band.height() >= default_row.minimumHeight() + modeling_tabs.minimumHeight()
        assert top_toolbar.minimumHeight() >= toolbar_band.height()
        assert top_toolbar.maximumHeight() >= toolbar_band.height()
        modeling_scroll = window.findChild(QtWidgets.QScrollArea, "ViewportToolbarMapStudioModelingScrollArea")
        assert modeling_scroll is not None
        assert modeling_scroll.horizontalScrollBar().maximum() > 0
        for mode_key in ("object", "vertex", "edge", "face", "terrain", "walkmesh"):
            assert window.findChild(QtWidgets.QToolButton, f"ViewportToolbarMapStudioModeButton_{mode_key}") is not None
        for action_key in ("blockout_room", "floor", "wall", "cube", "ramp", "stairs", "door_frame", "arch", "terrain_patch"):
            assert window.findChild(QtWidgets.QToolButton, f"ViewportToolbarMapStudioBlockoutButton_{action_key}") is not None
        modeling_tabs.setCurrentIndex(1)
        app.processEvents()
        blockout_scroll = window.findChild(QtWidgets.QScrollArea, "ViewportToolbarMapStudioBlockoutScrollArea")
        assert blockout_scroll is not None

        command_icon.click()
        app.processEvents()

        module_window = getattr(window, "module_editor_window", None)
        assert module_window is not None
        assert module_window.isVisible()
        assert module_window.minimumWidth() <= 1400
        assert module_window.minimumHeight() <= 800
        assert module_window.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioTopToolbarScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioToolBeltScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioCustomToolBeltScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioWorkflowTabsScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioViewportPanelScrollArea") is None
        embedded_viewport = module_window.findChild(QtWidgets.QWidget, "MapStudioViewportWidget")
        assert embedded_viewport is not None
        assert embedded_viewport.property("_gr_suppress_renderer_diagnostics") is True
        assert embedded_viewport.property("_gr_map_studio_clean_viewport") is True
        presentation = getattr(embedded_viewport, "_map_studio_viewport_presentation", {})
        assert presentation.get("clean_display") is True
        assert presentation.get("subtle_room_outlines") is True
        assert presentation.get("show_room_guides") is False
        assert presentation.get("show_transform_dimensions") is False
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioRightTabsScrollArea") is not None
        for action_key in (
            "object",
            "vertex",
            "edge",
            "face",
            "select",
            "move",
            "duplicate_selected",
            "delete_selected",
            "object_grid_snap",
            "object_vertex_snap",
            "vertex_snap",
            "grid_snap",
            "weld",
            "cut",
            "bridge",
            "extrude",
            "bevel",
            "inset",
            "flatten",
            "cleanup",
            "triangulate",
            "center_pivot",
            "freeze_transform",
            "terrain_patch",
            "paint_material",
            "paint_wok",
            "validate",
        ):
            assert module_window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_icon_reopens_after_close_or_deleted_reference_runtime() -> None:
    """The main toolbar/menu action keeps opening Map Studio across real window lifetimes."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        window.modules_action.trigger()
        app.processEvents()
        first = getattr(window, "module_editor_window", None)
        assert first is not None
        assert first.isVisible()
        assert first.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None

        first.controller.project.dirty = False
        first.close()
        app.processEvents()
        assert not first.isVisible()

        window.modules_action.trigger()
        app.processEvents()
        reopened = getattr(window, "module_editor_window", None)
        assert reopened is first
        assert reopened.isVisible()
        assert reopened.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None

        reopened.controller.project.dirty = False
        reopened.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()

        window.modules_action.trigger()
        app.processEvents()
        recreated = getattr(window, "module_editor_window", None)
        assert recreated is not None
        assert recreated is not reopened
        assert recreated.isVisible()
        assert recreated.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            try:
                module_window.controller.project.dirty = False
                module_window.close()
            except RuntimeError:
                pass
        window.close()


def test_t2600_map_studio_load_lyt_uses_indexed_resource_picker_runtime(monkeypatch) -> None:
    """Load LYT uses an in-app indexed game-resource chooser instead of raw Explorer browsing."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.core.assets.resource_manager import RES_LYT
    from src.gui.windows.module_editor_window import ModuleEditorWindow, _MapStudioLytResourceDialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    lyt_text = "\n".join(
        [
            "#MAXLAYOUT ASCII",
            "filedependancy layout.max",
            "beginlayout",
            "roomcount 2",
            "  m12aa_01  0.0  0.0  0.0",
            "  m12aa_02  10.0  0.0  0.0",
            "doorhookcount 1",
            "  m12aa_door  5.0  0.0  0.0",
            "donelayout",
        ]
    ).encode("latin-1")

    class FakeInstall:
        def __init__(self, game_dir: str, resrefs: tuple[str, ...]) -> None:
            self.game_dir = game_dir
            self._resrefs = resrefs

        def list_resrefs(self, restype: int):
            assert restype == RES_LYT
            return self._resrefs

    class FakeResourceManager:
        def __init__(self) -> None:
            self._installs = {
                "K1": FakeInstall("C:/Games/KOTOR", ("m12aa",)),
                "K2": FakeInstall("C:/Games/KOTOR2", ("003ebo",)),
            }

        def get_k1(self):
            return self._installs["K1"]

        def get_k2(self):
            return self._installs["K2"]

        def get(self, resref: str, restype: int, game: str = "K1"):
            assert restype == RES_LYT
            return lyt_text

    def fail_file_dialog(*_args, **_kwargs):
        raise AssertionError("Load LYT should use the indexed in-app picker, not QFileDialog.")

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", fail_file_dialog)
    window = ModuleEditorWindow()
    window.resource_manager = FakeResourceManager()
    try:
        rows = window._indexed_lyt_resource_rows()
        assert [row["resref"] for row in rows] == ["m12aa", "003ebo"]
        assert rows[0]["room_count"] == 2
        assert rows[0]["doorhook_count"] == 1

        dialog = _MapStudioLytResourceDialog(window, rows=rows)
        try:
            assert dialog.findChild(QtWidgets.QLineEdit, "mapStudioLytResourceSearchLineEdit") is not None
            assert dialog.findChild(QtWidgets.QComboBox, "mapStudioLytResourceGameComboBox") is not None
            assert dialog.findChild(QtWidgets.QListWidget, "mapStudioLytResourceListWidget").count() == 2
        finally:
            dialog.close()

        window._choose_indexed_lyt_resource = lambda indexed_rows: indexed_rows[0]
        window._handle_tab_action("Load LYT")
        app.processEvents()

        assert [room.model_resref for room in window.project.rooms] == ["m12aa_01", "m12aa_02"]
        assert "K1:m12aa.lyt" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_main_viewport_mode_buttons_route_map_studio_workspaces_runtime() -> None:
    """Main viewport Map Studio mode buttons open the editor and focus the matching workflow."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})

    expected = {
        "object": ("blockout", "geometry", "object", "primitive_room", "builder_tab"),
        "vertex": ("component", "geometry", "vertex", "weld_vertices", "builder_tab"),
        "edge": ("component", "geometry", "edge", "bridge", "builder_tab"),
        "face": ("component", "geometry", "face", "fill_face", "builder_tab"),
        "terrain": ("terrain", "terrain", "terrain", "terrain_sculpt", "builder_tab"),
        "walkmesh": ("component", "walkmesh", "walkmesh", "paint_wok", "walkmesh_tab"),
    }

    try:
        window.show()
        app.processEvents()

        for mode_key, (preset_key, workspace_key, component_key, tool_key, tab_name) in expected.items():
            button = window.findChild(QtWidgets.QToolButton, f"ViewportToolbarMapStudioModeButton_{mode_key}")
            assert button is not None
            assert button.isEnabled()
            button.click()
            app.processEvents()

            module_window = getattr(window, "module_editor_window", None)
            assert module_window is not None
            assert module_window.isVisible()
            assert module_window.map_studio_tool_belt_preset_combo.currentData() == preset_key
            assert module_window.map_studio_workspace_combo.currentData() == workspace_key
            assert module_window.builder_tab.componentModeComboBox.currentData()["key"] == component_key
            assert module_window.builder_tab.modelingToolComboBox.currentData()["key"] == tool_key
            expected_tab = module_window.walkmesh_tab if tab_name == "walkmesh_tab" else module_window.builder_tab
            assert module_window.workflow_tabs.currentWidget() is expected_tab
            assert f"{component_key.capitalize()} mode" in module_window.statusBar().currentMessage()
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_marking_menus_route_modes_and_tools_runtime() -> None:
    """Viewport marking menus expose Maya-like mode and tool choices through Map Studio actions."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def collect_actions(menu: QtWidgets.QMenu) -> list[QtGui.QAction]:
        actions: list[QtGui.QAction] = []
        for action in menu.actions():
            actions.append(action)
            child_menu = action.menu()
            if child_menu is not None:
                actions.extend(collect_actions(child_menu))
        return actions

    try:
        mode_menu = window._build_map_studio_mode_marking_menu(window)
        assert mode_menu.objectName() == "mapStudioModeMarkingMenu"
        for key in ("object", "vertex", "edge", "face", "select"):
            assert mode_menu.findChild(QtWidgets.QToolButton, f"mapStudioModeMarkingButton_{key}") is not None
            assert mode_menu.findChild(QtGui.QAction, f"mapStudioModeMarkingAction_{key}") is not None

        vertex_action = mode_menu.findChild(QtGui.QAction, "mapStudioModeMarkingAction_vertex")
        assert vertex_action is not None
        vertex_action.trigger()
        app.processEvents()
        assert window.builder_tab.componentModeComboBox.currentData()["key"] == "vertex"
        assert window.toolbar.selection_mode.currentText() == "Vertex"
        assert window.controller.map_studio_active_selection()["component_mode"] == "vertex"
        assert window.controller.map_studio_active_selection()["tool_key"] == "select"

        tool_menu = window._build_map_studio_tool_marking_menu(window)
        assert tool_menu.objectName() == "mapStudioToolMarkingMenu"
        for key in ("extrude", "bridge", "cut", "weld", "fill_hole", "bevel"):
            button = tool_menu.findChild(QtWidgets.QToolButton, f"mapStudioToolMarkingQuickButton_{key}")
            assert button is not None
            assert button.defaultAction() is not None
        names = {action.objectName(): action for action in collect_actions(tool_menu)}
        for key in (
            "insert_edge_loop",
            "cut_slice_insert_edges",
            "triangulate",
            "cleanup",
            "soften_edges",
            "harden_edges",
            "reverse_normals",
            "mirror",
            "separate",
            "combine",
            "paint_material",
            "paint_wok",
            "validate",
            "sculpt_raise",
            "sculpt_smooth",
            "sculpt_flatten",
        ):
            assert f"mapStudioToolMarkingAction_{key}" in names
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingTerrainBrushesMenu") is not None
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingUvMappingMenu") is not None
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingPlannedMenu") is not None
        assert names["mapStudioToolMarkingPlannedAction_offset_edge_loop"].isEnabled() is False
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_viewport_right_click_marking_menu_requests_split_by_shift_runtime() -> None:
    """Plain RMB requests the mode marking menu; Shift+RMB requests the tool marking menu."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    mode_positions: list[QtCore.QPoint] = []
    tool_positions: list[QtCore.QPoint] = []
    panel.modeMarkingMenuRequested.connect(mode_positions.append)
    panel.toolMarkingMenuRequested.connect(tool_positions.append)

    def mouse_event(modifiers=QtCore.Qt.NoModifier):
        return QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            QtCore.QPointF(42, 42),
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            modifiers,
        )

    try:
        canvas = panel.viewport.canvas
        assert panel.eventFilter(canvas, mouse_event()) is True
        assert len(mode_positions) == 1
        assert len(tool_positions) == 0

        assert panel.eventFilter(canvas, mouse_event(QtCore.Qt.ShiftModifier)) is True
        assert len(mode_positions) == 1
        assert len(tool_positions) == 1

        panel.viewport.canvas.install_input_bridge(panel.viewport)
        panel.viewport._show_mesh_context_menu = lambda _event: (_ for _ in ()).throw(
            AssertionError("Map Studio RMB should not fall through to the generic mesh context menu.")
        )
        surface = panel.viewport.canvas.current_surface() or canvas
        assert panel.viewport.eventFilter(surface, mouse_event()) is True
        assert len(mode_positions) == 2
        assert len(tool_positions) == 1

        assert panel.viewport.eventFilter(surface, mouse_event(QtCore.Qt.ShiftModifier)) is True
        assert len(mode_positions) == 2
        assert len(tool_positions) == 2
    finally:
        panel.close()


def test_t2600_map_studio_gimbal_modes_and_undo_redo_shortcuts_runtime() -> None:
    """Selected primitives show a manipulator, W/E/R changes modes, and Ctrl+Z/Ctrl+R route to KMAP undo/redo."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def key_event(key, modifiers=QtCore.Qt.NoModifier):
        return QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers)

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        primitive_name = str(selected["primitive_name"])
        overlay = getattr(window.viewport_panel.viewport, "_map_studio_universal_transform_overlay", None)
        assert overlay is not None
        assert getattr(overlay, "primitive_name", "") == primitive_name

        translate_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportTranslateGizmoButton")
        rotate_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportRotateGizmoButton")
        scale_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportScaleGizmoButton")
        assert translate_button is not None and translate_button.isChecked()
        assert rotate_button is not None
        assert scale_button is not None

        surface = window.viewport_panel.viewport.canvas.current_surface() or window.viewport_panel.viewport.canvas
        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_E)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "rotate"
        assert getattr(window.viewport_panel.viewport, "_map_studio_transform_gizmo_mode") == "rotate"
        assert rotate_button.isChecked()

        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_R)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "scale"
        assert scale_button.isChecked()

        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_W)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "translate"
        assert translate_button.isChecked()

        assert primitive_name in primitive_names()
        assert window.viewport_panel.viewport.eventFilter(
            surface,
            key_event(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier),
        ) is True
        app.processEvents()
        assert primitive_name not in primitive_names()

        assert window.viewport_panel.viewport.eventFilter(
            surface,
            key_event(QtCore.Qt.Key_R, QtCore.Qt.ControlModifier),
        ) is True
        app.processEvents()
        assert primitive_name in primitive_names()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_delete_key_removes_selected_authored_primitive_runtime() -> None:
    """The viewport Delete key removes the selected authored primitive through KMAP history."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        primitive_name = str(selected["primitive_name"])
        assert primitive_name in primitive_names()

        surface = window.viewport_panel.viewport.canvas.current_surface() or window.viewport_panel.viewport.canvas
        delete_event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier)
        assert window.viewport_panel.viewport.eventFilter(surface, delete_event) is True
        app.processEvents()

        assert primitive_name not in primitive_names()
        assert window.controller.command_history.undo_label == f"Remove primitive {primitive_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        window.undo_map_studio_command()
        app.processEvents()
        assert primitive_name in primitive_names()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_outliner_selects_renames_and_deletes_primitives_runtime() -> None:
    """Map Studio outliner rows behave like Maya scene objects for authored primitives."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def outliner_item(item_id: str):
        for item in window.outliner.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
            if str(item.data(0, QtCore.Qt.UserRole) or "") == item_id:
                return item
        raise AssertionError(f"Missing outliner item {item_id!r}")

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        room_resref = str(selected["room_resref"])
        primitive_name = str(selected["primitive_name"])
        item_id = f"authored_primitive:{room_resref}:{primitive_name}"
        item = outliner_item(item_id)
        assert item.text(0) == primitive_name
        assert item.text(1) == "cube"

        window.outliner.setCurrentItem(item)
        app.processEvents()
        selected_after_click = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected_after_click, dict)
        assert selected_after_click.get("primitive_name") == primitive_name
        overlay = getattr(window.viewport_panel.viewport, "_map_studio_universal_transform_overlay", None)
        assert overlay is not None
        assert getattr(overlay, "primitive_name", "") == primitive_name

        renamed = "renamed_outliner_cube"
        item.setText(0, renamed)
        app.processEvents()
        assert renamed in primitive_rows()
        assert primitive_name not in primitive_rows()
        assert window.controller.command_history.undo_label == f"Rename primitive {primitive_name}"

        renamed_id = f"authored_primitive:{room_resref}:{renamed}"
        renamed_item = outliner_item(renamed_id)
        window._outliner_action("delete", renamed_id)
        app.processEvents()
        assert renamed not in primitive_rows()
        assert window.controller.command_history.undo_label == f"Remove primitive {renamed}"

        window.undo_map_studio_command()
        app.processEvents()
        assert renamed in primitive_rows()
        assert outliner_item(renamed_id).text(0) == renamed
        assert renamed_item is not None
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_gimbal_rotate_and_scale_commit_authored_kmap_runtime() -> None:
    """Rotate and scale gimbal modes commit through authored KMAP transform commands."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_row(name: str):
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows[name]

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        room_resref = str(selected["room_resref"])
        primitive_name = str(selected["primitive_name"])

        window.viewport_panel.set_transform_gizmo_mode("rotate")
        window._rotate_authored_room_primitive(room_resref, primitive_name, 22.5)
        app.processEvents()
        assert round(float(getattr(primitive_row(primitive_name), "rotation_degrees_z")), 1) == 22.5
        assert window.controller.command_history.undo_label == f"Transform primitive {primitive_name}"

        window.viewport_panel.set_transform_gizmo_mode("scale")
        window._scale_authored_room_primitive(room_resref, primitive_name, (1.5, 1.5, 1.5))
        app.processEvents()
        assert tuple(round(float(value), 3) for value in getattr(primitive_row(primitive_name), "scale")) == (
            1.5,
            1.5,
            1.5,
        )
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_file_actions_save_open_kmap_and_keep_tool_belt_usable_runtime(tmp_path: Path, monkeypatch) -> None:
    """Visible File actions save/open authored KMAP state and leave modeling tools usable."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_file_actions.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    def click_tool(window: ModuleEditorWindow, action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    writer = ModuleEditorWindow()
    try:
        writer.show()
        app.processEvents()

        click_tool(writer, "floor")
        click_tool(writer, "paint_wok")
        click_tool(writer, "select")
        selection = writer.controller.map_studio_active_selection()
        assert selection["room_resref"] == "new_level_room01"
        assert selection["primitive_name"] == "new_level_room01_floor"
        assert selection["tool_key"] == "select"
        assert writer.controller.command_history.undo_label == "Select new_level_room01_floor"
        assert writer.controller.command_history.undo_stack[-1].stale_outputs == ()
        writer.save_as_action.trigger()
        app.processEvents()

        assert kmap_path.is_file()
        assert Path(writer.project.path) == kmap_path
        assert writer.project.dirty is False

        click_tool(writer, "cube")
        assert writer.project.dirty is True
        writer.save_action.trigger()
        app.processEvents()
        assert writer.project.dirty is False
    finally:
        writer.controller.project.dirty = False
        writer.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in reader.controller.authored_room_primitive_transforms()
        }
        assert "new_level_room01_floor" in rows
        assert rows["new_level_room01_floor"].primitive_type == "plane"
        assert str(getattr(rows["new_level_room01_floor"], "surface_id")) == "4"
        assert any(row.primitive_type == "cube" for row in rows.values())
        reopened_selection = reader.controller.map_studio_active_selection()
        assert reopened_selection["room_resref"] == "new_level_room01"
        assert reopened_selection["primitive_name"] == "new_level_room01_floor"
        assert reopened_selection["tool_key"] == "select"
        assert Path(reader.project.path) == kmap_path
        assert reader.project.dirty is False

        click_tool(reader, "validate")
        assert reader.statusBar().currentMessage().startswith("Validation complete:")
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_floor") is not None
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_paint_wok") is not None
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_visible_walkmesh_tab_assigns_room_wok_surface_and_persists_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    """Visible Walkmesh controls assign WOK surface intent into durable KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_walkmesh_surface.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def choose_surface(combo: QtWidgets.QComboBox, surface_id: str) -> None:
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == surface_id:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible Walkmesh surface {surface_id}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("validate")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        select_preset("export")
        click_tool("stage_module")
        assert window.controller.authored_module_readiness().readiness.capability_stage == "export_candidate"

        open_walkmesh = window.findChild(QtWidgets.QPushButton, "mapStudioWorkflowWalkmeshToolsButton")
        assert open_walkmesh is not None
        assert open_walkmesh.isEnabled()
        open_walkmesh.click()
        app.processEvents()
        assert window.workflow_tabs.currentWidget() is window.walkmesh_tab

        room_combo = window.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshRoomComboBox")
        surface_combo = window.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshSurfaceComboBox")
        apply_button = window.findChild(QtWidgets.QPushButton, "mapStudioWalkmeshApplySurfaceButton")
        status_label = window.findChild(QtWidgets.QLabel, "mapStudioWalkmeshStatusLabel")
        assert room_combo is not None and room_combo.isEnabled()
        assert surface_combo is not None and surface_combo.isEnabled()
        assert apply_button is not None and apply_button.isEnabled()
        assert status_label is not None
        assert "new_level_room01" in room_combo.currentText()

        choose_surface(surface_combo, "6")
        apply_button.click()
        app.processEvents()

        choices = window.controller.authored_walkmesh_room_surface_choices()
        assert len(choices) == 1
        assert choices[0].room_resref == "new_level_room01"
        assert choices[0].floor_surface_id == 6
        assert choices[0].floor_surface_name == "WATER"
        assert choices[0].walkable is False
        assert window.controller.command_history.undo_label == "Style new_level_room01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        payload = window.controller.project.extra_sections["authored_module"]
        invalidation = payload["export_proof_invalidation"]
        assert invalidation["latest_summary"] == "Style new_level_room01"
        assert invalidation["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
        assert "Regenerate the authored module package" in invalidation["next_action"]
        assert "Applied WOK surface 6 to room new_level_room01" in window.statusBar().currentMessage()

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened_choices = reader.controller.authored_walkmesh_room_surface_choices()
        assert len(reopened_choices) == 1
        assert reopened_choices[0].room_resref == "new_level_room01"
        assert reopened_choices[0].floor_surface_id == 6
        assert reopened_choices[0].floor_surface_name == "WATER"
        assert reopened_choices[0].walkable is False
        reopened_payload = reader.controller.project.extra_sections["authored_module"]
        assert reopened_payload["export_proof_invalidation"]["latest_summary"] == "Style new_level_room01"

        open_walkmesh = reader.findChild(QtWidgets.QPushButton, "mapStudioWorkflowWalkmeshToolsButton")
        assert open_walkmesh is not None
        open_walkmesh.click()
        app.processEvents()
        reopened_surface_combo = reader.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshSurfaceComboBox")
        assert reopened_surface_combo is not None
        current_data = reopened_surface_combo.currentData()
        assert isinstance(current_data, dict)
        assert str(current_data.get("surface_id") or "") == "6"
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_main_viewport_floor_blockout_button_creates_authored_kmap_state_runtime() -> None:
    """Clicking Floor from the main viewport creates durable KMAP room/floor state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        floor_button = window.findChild(QtWidgets.QToolButton, "ViewportToolbarMapStudioBlockoutButton_floor")
        assert floor_button is not None
        assert floor_button.text() == "Floor"

        floor_button.click()
        app.processEvents()

        module_window = getattr(window, "module_editor_window", None)
        assert module_window is not None
        assert module_window.isVisible()
        rows = module_window.controller.authored_room_primitive_transforms()
        floor_rows = [row for row in rows if row.primitive_type == "plane" and row.supports_walkmesh_surface]
        assert floor_rows
        assert module_window.controller.project.dirty is True
        assert module_window.controller.command_history.undo_label == "Add floor primitive"
        assert module_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_visible_tool_belt_buttons_mutate_kmap_state_runtime() -> None:
    """Visible Map Studio modeling buttons create, style, duplicate, and delete KMAP primitives."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        rows = primitive_rows()
        floor = rows["new_level_room01_floor"]
        assert getattr(floor, "primitive_type") == "plane"
        assert getattr(floor, "supports_walkmesh_surface") is True
        assert window.controller.project.dirty is True
        assert window.controller.command_history.undo_label == "Add floor primitive"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        click_tool("paint_material")
        assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
        assert getattr(primitive_rows()["new_level_room01_floor"], "texture") == "CM_Baremetal"

        click_tool("paint_wok")
        assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
        styled_floor = primitive_rows()["new_level_room01_floor"]
        assert str(getattr(styled_floor, "surface_id")) == "4"
        assert str(getattr(styled_floor, "surface_name")).upper() == "STONE"

        window.builder_tab.primitiveTranslateXSpinBox.setValue(0.13)
        window.builder_tab.primitiveTranslateYSpinBox.setValue(0.27)
        window.builder_tab.primitiveTranslateZSpinBox.setValue(0.0)
        click_tool("move")
        moved_floor = primitive_rows()["new_level_room01_floor"]
        assert tuple(round(float(value), 2) for value in getattr(moved_floor, "translation")) == (0.13, 0.27, 0.0)
        assert window.controller.command_history.undo_label == "Move primitive new_level_room01_floor"
        moved_payload = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert moved_payload["floor"]["transform"]["translation"] == [0.13, 0.27, 0.0]

        click_tool("object_grid_snap")
        snapped_floor = primitive_rows()["new_level_room01_floor"]
        assert tuple(round(float(value), 2) for value in getattr(snapped_floor, "translation")) == (0.1, 0.3, 0.0)
        assert window.controller.command_history.undo_label == "Object grid snap new_level_room01_floor"
        snapped_payload = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert [round(float(value), 2) for value in snapped_payload["floor"]["transform"]["translation"]] == [
            0.1,
            0.3,
            0.0,
        ]

        click_tool("duplicate_selected")
        rows = primitive_rows()
        duplicate_names = [name for name in rows if name.startswith("new_level_room01_floor_dup")]
        assert duplicate_names
        duplicate_name = duplicate_names[-1]
        assert window.controller.command_history.undo_label == "Duplicate primitive new_level_room01_floor"
        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        assert selected.get("primitive_name") == duplicate_name

        click_tool("delete_selected")
        assert duplicate_name not in primitive_rows()
        assert "new_level_room01_floor" in primitive_rows()
        assert window.controller.command_history.undo_label == f"Remove primitive {duplicate_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_undo_redo_actions_restore_authored_kmap_state_runtime() -> None:
    """Visible Undo/Redo actions restore authored Map Studio KMAP mutations."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()

        assert window.undo_action.isEnabled() is False
        assert window.redo_action.isEnabled() is False

        click_tool("floor")

        assert "new_level_room01_floor" in primitive_names()
        assert window.undo_action.isEnabled() is True
        assert window.undo_action.text() == "Undo Add floor primitive"
        assert window.redo_action.isEnabled() is False

        window.undo_action.trigger()
        app.processEvents()

        assert "new_level_room01_floor" not in primitive_names()
        assert window.undo_action.isEnabled() is False
        assert window.redo_action.isEnabled() is True
        assert window.redo_action.text() == "Redo Add floor primitive"
        assert "Undid Add floor primitive" in window.statusBar().currentMessage()

        window.redo_action.trigger()
        app.processEvents()

        assert "new_level_room01_floor" in primitive_names()
        assert window.undo_action.isEnabled() is True
        assert window.redo_action.isEnabled() is False
        assert "Redid Add floor primitive" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_component_modeling_buttons_mutate_floor_plan_kmap_state_runtime() -> None:
    """Visible component modeling buttons commit KMAP edits instead of only focusing panels."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def reset_room() -> None:
        click_tool("create_room")
        assert window.controller.command_history.undo_label == "Create authored module grdev01"

    try:
        window.show()
        app.processEvents()

        reset_room()
        click_tool("flatten")
        flattened = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert flattened["metadata"]["last_operation"] == "flatten_floor_plan_vertices"
        assert flattened["metadata"]["flattened_vertices"] == [0, 2]
        assert flattened["metadata"]["flatten_axis"] == "x"
        assert window.controller.command_history.undo_label == "Flatten grdev01_room01 vertices on x"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        reset_room()
        click_tool("cleanup")
        cleaned = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert cleaned["metadata"]["last_operation"] == "cleanup_floor_plan_vertices"
        assert window.controller.command_history.undo_label == "Clean grdev01_room01 floor-plan vertices"

        reset_room()
        click_tool("triangulate")
        triangulated = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert triangulated["metadata"]["last_operation"] == "triangulate_floor_plan_face"
        assert triangulated["metadata"]["triangulated_faces"] == [[0, 1, 2], [0, 2, 3]]
        assert window.controller.command_history.undo_label == "Triangulate grdev01_room01 floor-plan face"

        reset_room()
        click_tool("extrude")
        extruded = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert len(extruded["points"]) == 6
        assert extruded["metadata"]["operation"] == "edge_extrude"
        assert window.controller.command_history.undo_label == "Extrude edge 0 on grdev01_room01"

        reset_room()
        click_tool("bevel")
        beveled = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert len(beveled["points"]) == 8
        assert beveled["metadata"]["operation"] == "bevel"
        assert window.controller.command_history.undo_label == "Bevel grdev01_room01"

        reset_room()
        click_tool("split")
        explicit_split_payload = window.controller.project.extra_sections["authored_module"]
        assert len(explicit_split_payload["rooms"]) == 2
        assert {room["room_resref"] for room in explicit_split_payload["rooms"]} == {
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        }
        assert window.controller.command_history.undo_label == "Axis split grdev01_room01 on x"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        reset_room()
        click_tool("cut")
        split_payload = window.controller.project.extra_sections["authored_module"]
        assert len(split_payload["rooms"]) == 2
        assert {room["room_resref"] for room in split_payload["rooms"]} == {
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        }
        assert window.controller.command_history.undo_label == "Axis split grdev01_room01 on x"
        assert int(window.builder_tab.floorPlanBridgeFirstEdgeSpinBox.value()) == 0
        assert int(window.builder_tab.floorPlanBridgeSecondEdgeSpinBox.value()) == 1

        click_tool("bridge")
        bridged_payload = window.controller.project.extra_sections["authored_module"]
        assert len(bridged_payload["rooms"]) == 3
        bridge_room = bridged_payload["rooms"][-1]
        bridge_metadata = bridge_room["primitive"]["metadata"]
        assert bridge_metadata["operation"] == "bridge_edges"
        assert bridge_metadata["first_room_resref"] == "grdev01_room0_l1"
        assert bridge_metadata["first_edge_index"] == 0
        assert bridge_metadata["second_room_resref"] == "grdev01_room0_r2"
        assert bridge_metadata["second_edge_index"] == 1
        assert bridge_metadata["last_component_edit_audit"]["walkmesh_review_required"] is True
        assert window.controller.command_history.undo_label == "Bridge grdev01_room0_l1:0 to grdev01_room0_r2:1"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_snap_and_weld_buttons_persist_floor_plan_kmap_state_runtime(tmp_path: Path) -> None:
    """Visible snap and weld controls author durable KMAP floor-plan edits."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def room_payload(room_resref: str) -> dict:
        payload = window.controller.project.extra_sections["authored_module"]
        for room in payload["rooms"]:
            if room["room_resref"] == room_resref:
                return room
        raise AssertionError(f"Missing authored room {room_resref!r}")

    def select_room_combo(combo_name: str, room_resref: str) -> None:
        combo = getattr(window.builder_tab, combo_name)
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("room_resref") == room_resref:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing room {room_resref!r} in {combo_name}")

    def save_and_reload(path: Path, room_resref: str) -> dict:
        window.controller.save_project(path)
        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(path)
            payload = reloaded.controller.project.extra_sections["authored_module"]
            for room in payload["rooms"]:
                if room["room_resref"] == room_resref:
                    return dict(room)
            raise AssertionError(f"Missing reloaded room {room_resref!r}")
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()

    def assert_stale_walkmesh_edit(metadata: dict, *, topology_changed: bool) -> None:
        audit = metadata["last_component_edit_audit"]
        assert audit["walkmesh_review_required"] is True
        assert audit["export_candidate_stale"] is True
        assert audit["game_proof_stale"] is True
        assert audit["topology_changed"] is topology_changed
        assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        click_tool("cut")
        source_room = "grdev01_room0_l1"
        target_room = "grdev01_room0_r2"
        select_room_combo("floorPlanVertexRoomComboBox", source_room)
        select_room_combo("floorPlanVertexTargetRoomComboBox", target_room)
        window.builder_tab.floorPlanSourcePointSpinBox.setValue(1)
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()

        click_tool("vertex_snap")

        snapped = room_payload(source_room)
        snapped_metadata = snapped["primitive"]["metadata"]
        assert snapped_metadata["last_operation"] == "snap_floor_plan_vertex"
        assert snapped_metadata["last_vertex_edit"] == 1
        assert snapped_metadata["snap_target_room"] == target_room
        assert snapped_metadata["snap_target_index"] == 0
        assert snapped["primitive"]["points"][1] == room_payload(target_room)["primitive"]["points"][0]
        assert window.controller.command_history.undo_label == f"Snap {source_room} point 1"
        assert_stale_walkmesh_edit(snapped_metadata, topology_changed=False)
        reloaded_snap = save_and_reload(tmp_path / "vertex_snap.kmap", source_room)
        assert reloaded_snap["primitive"]["metadata"]["last_operation"] == "snap_floor_plan_vertex"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        app.processEvents()
        click_tool("grid_snap")

        gridded = room_payload("grdev01_room01")
        grid_metadata = gridded["primitive"]["metadata"]
        assert grid_metadata["last_operation"] == "grid_snap_floor_plan_vertices"
        assert grid_metadata["grid_snap_vertices"] == [0, 2]
        assert grid_metadata["grid_snap_size"] == 0.1
        assert grid_metadata["grid_snap_axes"] == ["x", "y"]
        assert window.controller.command_history.undo_label == "Grid snap grdev01_room01 vertices"
        assert_stale_walkmesh_edit(grid_metadata, topology_changed=False)
        reloaded_grid = save_and_reload(tmp_path / "grid_snap.kmap", "grdev01_room01")
        assert reloaded_grid["primitive"]["metadata"]["last_operation"] == "grid_snap_floor_plan_vertices"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("1,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(1)
        app.processEvents()
        click_tool("transform_snap_level")

        level_snapped = room_payload("grdev01_room01")
        level_metadata = level_snapped["primitive"]["metadata"]
        assert level_metadata["last_operation"] == "transform_snap_floor_plan_vertices"
        assert level_metadata["transform_snap_vertices"] == [1, 2]
        assert level_metadata["transform_snap_axis"] == "x"
        assert level_metadata["transform_snap_policy"] == "target"
        assert level_metadata["transform_snap_target_index"] == 1
        assert level_metadata["source"] == "map_studio:floor_plan_transform_level_snap"
        assert window.controller.command_history.undo_label == "Transform snap grdev01_room01 vertices on x"
        assert_stale_walkmesh_edit(level_metadata, topology_changed=False)
        reloaded_level = save_and_reload(tmp_path / "transform_snap_level.kmap", "grdev01_room01")
        assert reloaded_level["primitive"]["metadata"]["last_operation"] == "transform_snap_floor_plan_vertices"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()
        click_tool("weld")

        welded = room_payload("grdev01_room01")
        weld_metadata = welded["primitive"]["metadata"]
        assert weld_metadata["last_operation"] == "weld_floor_plan_vertices"
        assert weld_metadata["welded_vertices"] == [0, 2]
        assert weld_metadata["weld_policy"] == "target"
        assert len(welded["primitive"]["points"]) == 3
        assert window.controller.command_history.undo_label == "Weld grdev01_room01 vertices"
        assert_stale_walkmesh_edit(weld_metadata, topology_changed=True)
        reloaded_weld = save_and_reload(tmp_path / "weld.kmap", "grdev01_room01")
        assert reloaded_weld["primitive"]["metadata"]["last_operation"] == "weld_floor_plan_vertices"
        assert len(reloaded_weld["primitive"]["points"]) == 3

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()
        click_tool("merge_components")

        merged = room_payload("grdev01_room01")
        merge_metadata = merged["primitive"]["metadata"]
        assert merge_metadata["last_operation"] == "weld_floor_plan_vertices"
        assert merge_metadata["welded_vertices"] == [0, 2]
        assert len(merged["primitive"]["points"]) == 3
        assert window.controller.command_history.undo_label == "Weld grdev01_room01 vertices"
        assert_stale_walkmesh_edit(merge_metadata, topology_changed=True)
        reloaded_merge = save_and_reload(tmp_path / "merge_components.kmap", "grdev01_room01")
        assert reloaded_merge["primitive"]["metadata"]["last_operation"] == "weld_floor_plan_vertices"
        assert len(reloaded_merge["primitive"]["points"]) == 3
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_object_vertex_snap_moves_primitive_and_persists_kmap_runtime(tmp_path: Path) -> None:
    """Visible Object Vertex Snap moves a primitive pivot to another primitive vertex in KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def select_primitive(name: str) -> None:
        combo = window.builder_tab.roomPrimitiveTransformComboBox
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_name") == name:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible primitive row {name!r}")

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        click_tool("cube")
        cubes = [
            row
            for row in primitive_rows().values()
            if str(getattr(row, "primitive_type", "") or "") == "cube"
        ]
        assert len(cubes) >= 2
        source = cubes[0]
        target = cubes[1]

        select_primitive(str(getattr(target, "primitive_name")))
        window.builder_tab.primitiveTranslateXSpinBox.setValue(1.0)
        window.builder_tab.primitiveTranslateYSpinBox.setValue(0.0)
        window.builder_tab.primitiveTranslateZSpinBox.setValue(0.0)
        window.builder_tab.applyPrimitiveTransformButton.click()
        app.processEvents()

        select_primitive(str(getattr(source, "primitive_name")))
        click_tool("object_vertex_snap")

        source_name = str(getattr(source, "primitive_name"))
        target_name = str(getattr(target, "primitive_name"))
        snapped = primitive_rows()[source_name]
        assert tuple(round(float(value), 6) for value in getattr(snapped, "translation")) == (0.5, -0.5, 0.0)
        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "object_vertex_snap_primitive"
        assert metadata["last_vertex_snapped_primitive"] == source_name
        assert metadata["object_vertex_snap_coordinate_space"] == "authored_room_composition_mesh_space"
        assert metadata["target_primitive"] == target_name
        assert metadata["target_vertex_index"] == 0
        assert metadata["target_vertex"] == [0.5, -0.5, 0.0]
        assert metadata["old_translation"] == [0.0, 0.0, 0.0]
        assert metadata["new_translation"] == [0.5, -0.5, 0.0]
        assert window.controller.command_history.undo_label == f"Object vertex snap {source_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        path = tmp_path / "object_vertex_snap.kmap"
        window.controller.save_project(path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            assert tuple(round(float(value), 6) for value in getattr(reloaded_rows[source_name], "translation")) == (
                0.5,
                -0.5,
                0.0,
            )
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_metadata = reloaded_payload["rooms"][0]["primitive"]["metadata"]
            assert reloaded_metadata["last_operation"] == "object_vertex_snap_primitive"
            assert reloaded_metadata["target_primitive"] == target_name
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_combine_and_separate_buttons_persist_kmap_boundaries_runtime(tmp_path: Path) -> None:
    """Visible Combine and Separate controls author durable KMAP room/object boundaries."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def click_tool(window: ModuleEditorWindow, action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_room_combo(window: ModuleEditorWindow, combo_name: str, room_resref: str) -> None:
        combo = getattr(window.builder_tab, combo_name)
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("room_resref") == room_resref:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing room {room_resref!r} in {combo_name}")

    def select_first_non_floor_primitive(window: ModuleEditorWindow) -> dict:
        combo = window.builder_tab.roomPrimitiveTransformComboBox
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_type") != "plane":
                combo.setCurrentIndex(index)
                app.processEvents()
                return dict(data)
        raise AssertionError("Missing a non-floor primitive row for visible Separate.")

    def reload_payload(path: Path) -> dict:
        reader = ModuleEditorWindow()
        try:
            reader.controller.open_project(path)
            return dict(reader.controller.project.extra_sections["authored_module"])
        finally:
            reader.controller.project.dirty = False
            reader.close()

    combine_window = ModuleEditorWindow()
    try:
        combine_window.show()
        app.processEvents()

        click_tool(combine_window, "create_room")
        click_tool(combine_window, "cut")
        select_room_combo(combine_window, "floorPlanUnionFirstRoomComboBox", "grdev01_room0_l1")
        select_room_combo(combine_window, "floorPlanUnionSecondRoomComboBox", "grdev01_room0_r2")
        combine_window.builder_tab.floorPlanUnionResultRoomLineEdit.setText("grvisible_union")
        app.processEvents()
        click_tool(combine_window, "combine")

        combined_payload = combine_window.controller.project.extra_sections["authored_module"]
        assert [room["room_resref"] for room in combined_payload["rooms"]] == ["grvisible_union"]
        combined_room = combined_payload["rooms"][0]
        assert combined_room["primitive"]["metadata"]["operation"] == "rectangular_union"
        assert combined_room["primitive"]["metadata"]["source_room_resrefs"] == [
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        ]
        assert combine_window.controller.command_history.undo_label == "Merge grdev01_room0_l1 and grdev01_room0_r2"
        assert combine_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        combine_path = tmp_path / "visible_combine.kmap"
        combine_window.controller.save_project(combine_path)
        reloaded_combine = reload_payload(combine_path)
        assert [room["room_resref"] for room in reloaded_combine["rooms"]] == ["grvisible_union"]
        assert reloaded_combine["rooms"][0]["primitive"]["metadata"]["operation"] == "rectangular_union"
    finally:
        combine_window.controller.project.dirty = False
        combine_window.close()

    separate_window = ModuleEditorWindow()
    try:
        separate_window.show()
        app.processEvents()

        click_tool(separate_window, "blockout_room")
        selected = select_first_non_floor_primitive(separate_window)
        separate_window.builder_tab.roomPrimitiveSeparateResultLineEdit.setText("grvisible_sep")
        app.processEvents()
        click_tool(separate_window, "separate")

        separated_payload = separate_window.controller.project.extra_sections["authored_module"]
        assert [room["room_resref"] for room in separated_payload["rooms"]] == [
            "grdev01_room01",
            "grvisible_sep",
        ]
        assert separated_payload["rooms"][0]["metadata"]["last_operation"] == "separate_composition_primitive"
        assert separated_payload["rooms"][0]["metadata"]["last_separated_primitive"] == selected["primitive_name"]
        separated_room = separated_payload["rooms"][1]
        assert separated_room["metadata"]["last_operation"] == "separate_composition_primitive"
        assert separated_room["metadata"]["separated_from_room"] == selected["room_resref"]
        assert separated_room["metadata"]["separated_primitive"] == selected["primitive_name"]
        assert separate_window.controller.command_history.undo_label == f"Separate primitive {selected['primitive_name']}"
        assert separate_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in separate_window.controller.authored_room_primitive_transforms()
        }
        assert selected["primitive_name"] in rows
        assert getattr(rows[selected["primitive_name"]], "room_resref") == "grvisible_sep"

        separate_path = tmp_path / "visible_separate.kmap"
        separate_window.controller.save_project(separate_path)
        reloaded_separate = reload_payload(separate_path)
        assert [room["room_resref"] for room in reloaded_separate["rooms"]] == [
            "grdev01_room01",
            "grvisible_sep",
        ]
        assert reloaded_separate["rooms"][1]["metadata"]["separated_primitive"] == selected["primitive_name"]
    finally:
        separate_window.controller.project.dirty = False
        separate_window.close()


def test_t2600_visible_opening_and_transition_marker_persist_kmap_and_validate_runtime(tmp_path: Path) -> None:
    """Visible doorway controls persist KMAP opening/transition intent and validation blockers."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        window.builder_tab.floorPlanOpeningNameLineEdit.setText("south_door")
        window.builder_tab.floorPlanOpeningEdgeSpinBox.setValue(0)
        window.builder_tab.floorPlanOpeningCenterSpinBox.setValue(0.5)
        window.builder_tab.floorPlanOpeningWidthSpinBox.setValue(1.5)
        window.builder_tab.floorPlanOpeningHeightSpinBox.setValue(2.0)
        window.builder_tab.floorPlanOpeningBottomSpinBox.setValue(0.0)
        app.processEvents()

        click_tool("opening")

        payload = window.controller.project.extra_sections["authored_module"]
        primitive = payload["rooms"][0]["primitive"]
        opening = primitive["openings"][-1]
        assert opening == {
            "name": "south_door",
            "edge_index": 0,
            "center_fraction": 0.5,
            "width": 1.5,
            "height": 2.0,
            "bottom": 0.0,
            "metadata": {"source": "map_studio:wall_opening", "operation": "set_wall_opening"},
        }
        assert primitive["metadata"]["last_operation"] == "set_wall_opening"
        assert primitive["metadata"]["last_opening_name"] == "south_door"
        assert window.controller.command_history.undo_label == "Set wall opening south_door"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        trigger_index = window.builder_tab.floorPlanOpeningMarkerKindComboBox.findData("trigger")
        assert trigger_index >= 0
        window.builder_tab.floorPlanOpeningMarkerKindComboBox.setCurrentIndex(trigger_index)
        window.builder_tab.floorPlanOpeningMarkerTemplateLineEdit.setText("trg_exit")
        window.builder_tab.floorPlanOpeningMarkerTagLineEdit.setText("south_exit_trigger")
        window.builder_tab.floorPlanOpeningMarkerLinkedToLineEdit.setText("wp_dest")
        window.builder_tab.floorPlanOpeningMarkerLinkedModuleLineEdit.setText("grnext01")
        window.builder_tab.floorPlanOpeningMarkerTransitionDestSpinBox.setValue(2)
        app.processEvents()

        click_tool("opening_marker")

        marker_payload = window.controller.project.extra_sections["authored_module"]
        trigger = marker_payload["placements"]["triggers"][-1]
        marker_metadata = marker_payload["extra"]["last_opening_transition_marker"]
        assert trigger["template_resref"] == "trg_exit"
        assert trigger["tag"] == "south_exit_trigger"
        assert trigger["linked_to"] == "wp_dest"
        assert trigger["linked_to_module"] == "grnext01"
        assert trigger["transition_destination"] == 2
        assert marker_metadata["room_resref"] == "grdev01_room01"
        assert marker_metadata["opening_name"] == "south_door"
        assert marker_metadata["marker_kind"] == "trigger"
        assert marker_metadata["transition_destination"] == 2
        assert window.controller.command_history.undo_label == "Add opening marker south_exit_trigger"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        issues = window.controller.validate()
        assert any(
            getattr(issue, "code", "") == "MAP_STUDIO_TRANSITION_WOK_SURFACE_BLOCKER"
            and "no WOK DOOR/transition surface" in getattr(issue, "message", "")
            for issue in issues
        )

        kmap_path = tmp_path / "opening_transition_marker.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_opening = reloaded_payload["rooms"][0]["primitive"]["openings"][-1]
            reloaded_trigger = reloaded_payload["placements"]["triggers"][-1]
            assert reloaded_opening["name"] == "south_door"
            assert reloaded_trigger["tag"] == "south_exit_trigger"
            assert reloaded_trigger["linked_to_module"] == "grnext01"
            assert reloaded_payload["extra"]["last_opening_transition_marker"]["opening_name"] == "south_door"
            reloaded_issues = reloaded.controller.validate()
            assert any(
                getattr(issue, "code", "") == "MAP_STUDIO_TRANSITION_WOK_SURFACE_BLOCKER"
                for issue in reloaded_issues
            )
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_unwalkable_player_start_runtime(tmp_path: Path) -> None:
    """Visible entry point and Validate controls report a player start off generated WOK."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def player_start_validation_rows() -> list[int]:
        rows: list[int] = []
        for row in range(window.validation_panel.rowCount()):
            item_id = window.validation_panel.item(row, 2)
            message = window.validation_panel.item(row, 1)
            if item_id is None or message is None:
                continue
            if item_id.text().startswith("authored_entry_point:walkable:") or "player start" in message.text().lower():
                rows.append(row)
        return rows

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        select_preset("gameplay")
        window.builder_tab.entryPointAreaLineEdit.setText("grdev01")
        window.builder_tab.entryPointPosXSpinBox.setValue(99.0)
        window.builder_tab.entryPointPosYSpinBox.setValue(99.0)
        window.builder_tab.entryPointPosZSpinBox.setValue(0.0)
        window.builder_tab.entryPointFacingSpinBox.setValue(180.0)
        app.processEvents()

        click_tool("entry_point")

        payload = window.controller.project.extra_sections["authored_module"]
        assert payload["placements"]["entry_point"] == {
            "area_resref": "grdev01",
            "position": [99.0, 99.0, 0.0],
            "facing": 180.0,
        }
        assert window.controller.command_history.undo_label == "Set entry point grdev01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        select_preset("export")
        click_tool("validate")

        assert window.statusBar().currentMessage().startswith("Validation complete:")
        issues = window.controller.validate()
        assert any(getattr(issue, "code", "") == "MAP_STUDIO_PLAYER_START_NOT_WALKABLE" for issue in issues)
        rows = player_start_validation_rows()
        assert rows
        row = rows[0]
        assert window.validation_panel.item(row, 0).text() == "Error"
        assert "player start" in window.validation_panel.item(row, 1).text().lower()
        assert "move the player start" in window.validation_panel.item(row, 3).text().lower()

        kmap_path = tmp_path / "player_start_not_walkable.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            assert reloaded_payload["placements"]["entry_point"]["position"] == [99.0, 99.0, 0.0]
            reloaded_issues = reloaded.controller.validate()
            assert any(getattr(issue, "code", "") == "MAP_STUDIO_PLAYER_START_NOT_WALKABLE" for issue in reloaded_issues)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_normals_tools_report_and_repair_bad_winding_runtime(tmp_path: Path) -> None:
    """Visible normal cleanup tools persist winding intent and validation feedback."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_metadata() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]["metadata"]

    def room_metadata() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["metadata"]

    def issue_codes() -> set[str]:
        return {str(getattr(issue, "code", "") or "") for issue in window.controller.validate()}

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        click_tool("reverse_normals")

        reversed_metadata = primitive_metadata()
        assert reversed_metadata["last_operation"] == "cleanup_floor_plan_normals"
        assert reversed_metadata["normal_cleanup_positive_z"] is False
        assert reversed_metadata["normal_cleanup_flipped_faces"] == 1
        assert room_metadata()["normal_cleanup_positive_z"] is False
        assert window.controller.command_history.undo_label == "Clean grdev01_room01 floor-plan normals"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        audit = reversed_metadata["last_component_edit_audit"]
        assert audit["walkmesh_review_required"] is True
        assert audit["export_candidate_stale"] is True
        assert audit["game_proof_stale"] is True
        assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" in issue_codes()

        click_tool("normals")

        repaired_metadata = primitive_metadata()
        assert repaired_metadata["last_operation"] == "cleanup_floor_plan_normals"
        assert repaired_metadata["normal_cleanup_positive_z"] is True
        assert repaired_metadata["normal_cleanup_flipped_faces"] == 1
        assert room_metadata()["normal_cleanup_positive_z"] is True
        assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" not in issue_codes()

        kmap_path = tmp_path / "normal_cleanup.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_metadata = reloaded_payload["rooms"][0]["primitive"]["metadata"]
            assert reloaded_metadata["last_operation"] == "cleanup_floor_plan_normals"
            assert reloaded_metadata["normal_cleanup_positive_z"] is True
            reloaded_codes = {str(getattr(issue, "code", "") or "") for issue in reloaded.controller.validate()}
            assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" not in reloaded_codes
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_map_studio_controls_stage_export_candidate_runtime(tmp_path: Path, monkeypatch) -> None:
    """Visible Floor/Validate/Stage controls write durable package evidence back into KMAP."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    kmap_path = tmp_path / "visible_stage_export_candidate.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        resource_table = dialog.findChild(QtWidgets.QTableWidget, "mapStudioPackageWizardResourceReviewTable")
        proof_table = dialog.findChild(QtWidgets.QTableWidget, "mapStudioPackageWizardProofGateTable")
        assert resource_table is not None and resource_table.rowCount() > 0
        assert proof_table is not None and proof_table.rowCount() > 0
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        click_tool("validate")
        assert window.statusBar().currentMessage().startswith("Validation complete:")
        assert not [
            issue
            for issue in window.controller.validate()
            if str(getattr(issue, "severity", "")).lower() == "error"
        ]

        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        payload = window.controller.project.extra_sections["authored_module"]
        assert Path(payload["pack_manifest_path"]).is_file()
        assert Path(payload["proof_manifest_path"]).is_file()
        inventory = payload["package_resource_inventory"]
        assert inventory["readback_ok"] is True
        assert inventory["all_required_runtime_resources_present"] is True
        assert {"new_level.lyt", "new_level.vis", "new_level.pth", "new_level_room01.wok"} <= set(
            payload["runtime_resources"]
        )
        readiness = window.controller.authored_module_readiness().readiness
        assert readiness.capability_stage == "export_candidate"
        assert readiness.can_export_candidate is True
        manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
        authored_manifest = manifest["map_studio_authored_module"]
        material_uv = authored_manifest["material_uv"]
        assert material_uv[0]["room_resref"] == "new_level_room01"
        assert material_uv[0]["texture"] == "CM_Baremetal"
        assert material_uv[0]["floor_surface_id"] == 4
        assert material_uv[0]["floor_surface_name"] == "STONE"
        assert material_uv[0]["all_mesh_uvs_complete"] is True
        assert material_uv[0]["meshes"][0]["role"] == "room_mesh"
        assert material_uv[0]["meshes"][0]["uv_coordinate_space"] == "mesh_uv0"
        assert material_uv[0]["meshes"][0]["uv_count"] == material_uv[0]["meshes"][0]["vertex_count"]
        assert material_uv[0]["meshes"][0]["face_count"] > 0
        assert window.controller.command_history.undo_label == "Stage authored module new_level"
        assert "Authored module staged" in window.statusBar().currentMessage()

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
        assert window.project.dirty is False
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened_payload = reader.controller.project.extra_sections["authored_module"]
        assert Path(reopened_payload["pack_manifest_path"]).is_file()
        assert Path(reopened_payload["proof_manifest_path"]).is_file()
        assert reopened_payload["package_resource_inventory"]["readback_ok"] is True
        assert reopened_payload["package_resource_inventory"]["all_required_runtime_resources_present"] is True
        assert {"new_level.lyt", "new_level.vis", "new_level.pth", "new_level_room01.wok"} <= set(
            reopened_payload["runtime_resources"]
        )
        reopened_readiness = reader.controller.authored_module_readiness().readiness
        assert reopened_readiness.capability_stage == "export_candidate"
        assert reopened_readiness.can_export_candidate is True
        reopened_manifest = json.loads(Path(reopened_payload["pack_manifest_path"]).read_text(encoding="utf-8"))
        reopened_material_uv = reopened_manifest["map_studio_authored_module"]["material_uv"]
        assert reopened_material_uv[0]["texture"] == "CM_Baremetal"
        assert reopened_material_uv[0]["all_mesh_uvs_complete"] is True
        assert reopened_material_uv[0]["meshes"][0]["uv_coordinate_space"] == "mesh_uv0"
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_stage_module") is not None
        assert reader.project.dirty is False
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_visible_record_proof_dialog_updates_kmap_game_test_state_runtime(tmp_path: Path) -> None:
    """Visible Stage and Record Proof controls write game-test proof metadata into KMAP."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    evidence_path = tmp_path / "new_level_warp_proof.png"
    evidence_path.write_bytes(b"visible proof screenshot bytes")

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    def accept_proof_dialog(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioGameProofDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_proof_dialog(attempt + 1))
            return
        manifest_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofManifestLineEdit")
        evidence_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofEvidenceLineEdit")
        tester_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofTesterLineEdit")
        summary_label = dialog.findChild(QtWidgets.QLabel, "mapStudioProofPackageResourceSummaryLabel")
        assert manifest_edit is not None and Path(manifest_edit.text()).is_file()
        assert evidence_edit is not None
        assert tester_edit is not None
        assert summary_label is not None and "0 missing" in summary_label.text()
        evidence_edit.setText(str(evidence_path))
        tester_edit.setText("visible-runtime")
        for object_name in (
            "mapStudioProofModuleLoadsCheckBox",
            "mapStudioProofModuleIdentityCheckBox",
            "mapStudioProofPlayerFloorCheckBox",
            "mapStudioProofPlaceableVisibleCheckBox",
            "mapStudioProofWalkableFloorCheckBox",
            "mapStudioProofTransitionPathingCheckBox",
            "mapStudioProofNoInheritedContentCheckBox",
        ):
            checkbox = dialog.findChild(QtWidgets.QCheckBox, object_name)
            assert checkbox is not None
            checkbox.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioProofButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        click_tool("validate")

        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        payload = window.controller.project.extra_sections["authored_module"]
        assert Path(payload["proof_manifest_path"]).is_file()
        assert window.workflow_panel.proof_button.isEnabled()

        QtCore.QTimer.singleShot(20, accept_proof_dialog)
        window.workflow_panel.proof_button.click()
        app.processEvents()

        payload = window.controller.project.extra_sections["authored_module"]
        readiness = window.controller.authored_module_readiness().readiness
        proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
        assert payload["game_tested"] is True
        assert payload["in_game_proof_evidence_path"] == str(evidence_path)
        assert payload["in_game_proof"]["tester"] == "visible-runtime"
        assert payload["in_game_proof"]["accepted_checks"] == proof["acceptance_checks"]
        assert readiness is not None
        assert readiness.capability_stage == "game_tested"
        assert readiness.game_tested is True
        assert proof["game_tested"] is True
        assert proof["game_test"]["tester"] == "visible-runtime"
        assert "Map Studio game proof updated" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_terrain_patch_and_sculpt_buttons_mutate_kmap_state_runtime() -> None:
    """Visible terrain patch and sculpt buttons commit heightfield KMAP edits."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")

        terrain_payload = window.controller.project.extra_sections["authored_module"]
        terrain_primitive = terrain_payload["rooms"][0]["primitive"]
        assert terrain_primitive["type"] == "terrain_heightfield"
        assert terrain_primitive["floor_surface_id"] == "grass"
        assert terrain_primitive["metadata"]["supports_terrain_authoring"] is True
        assert terrain_primitive["metadata"]["supports_slope_walkability"] is True
        before_height = float(terrain_primitive["heights"][0][0])
        assert window.controller.command_history.undo_label == "Create authored module grdev01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        context = window.builder_tab.current_terrain_brush_context()
        assert context["enabled"] is True
        assert context["room_resref"] == "grdev01_room01"
        assert context["brush"] == "raise"

        click_tool("sculpt_raise")

        sculpted_payload = window.controller.project.extra_sections["authored_module"]
        sculpted = sculpted_payload["rooms"][0]["primitive"]
        metadata = sculpted["metadata"]
        assert float(sculpted["heights"][0][0]) == before_height + 0.1
        assert metadata["last_operation"] == "terrain_brush_stroke"
        assert metadata["last_brush"] == "raise"
        assert metadata["last_dirty_region"] == {
            "min_row": 0,
            "max_row": 0,
            "min_column": 0,
            "max_column": 0,
            "changed_sample_count": 1,
        }
        assert metadata["last_brush_slope_report"]["walkable_triangle_count"] == 32
        assert metadata["last_brush_slope_report"]["non_walk_triangle_count"] == 0
        assert metadata["last_brush_performance"]["within_budget"] is True
        assert window.controller.command_history.undo_label == "Apply terrain brush raise"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        status = window.controller.authored_terrain_status()
        assert status["ready"] is True
        assert status["terrain_room_count"] == 1
        assert status["walkable_triangle_count"] == 32
        assert status["non_walk_triangle_count"] == 0
        assert "max slope" in status["summary"]
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_viewport_terrain_brush_drag_paints_instead_of_marquee_runtime() -> None:
    """Left-drag in active Terrain Brush mode paints dirty terrain samples, not a selection box."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})

    def click_tool(module_window, action_key: str) -> None:
        belt = module_window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(module_window, preset_key: str) -> None:
        combo = module_window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def mouse_event(kind, x: float, y: float, button, buttons, modifiers=QtCore.Qt.NoModifier):
        return QtGui.QMouseEvent(kind, QtCore.QPointF(x, y), button, buttons, modifiers)

    try:
        window.show()
        app.processEvents()
        window.modules_action.trigger()
        app.processEvents()
        module_window = window.module_editor_window
        assert module_window is not None

        select_preset(module_window, "terrain")
        click_tool(module_window, "terrain_patch")
        module_window._sync_map_studio_terrain_brush_context(force_enabled=True)

        panel = module_window.viewport_panel
        canvas = panel.viewport.canvas
        samples = [(1, 1, 1.0), (1, 2, 1.0), (2, 2, 1.0)]
        panel._terrain_sample_at_event = lambda _event: samples.pop(0) if samples else (2, 2, 1.0)

        press = mouse_event(QtCore.QEvent.MouseButtonPress, 80, 80, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        move = mouse_event(QtCore.QEvent.MouseMove, 120, 96, QtCore.Qt.NoButton, QtCore.Qt.LeftButton)
        release = mouse_event(QtCore.QEvent.MouseButtonRelease, 120, 96, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)

        assert panel.eventFilter(canvas, press) is True
        assert not panel.viewport._selection_rubber_band.isVisible()
        assert panel.eventFilter(canvas, move) is True
        assert not panel.viewport._selection_rubber_band.isVisible()
        assert panel.eventFilter(canvas, release) is True
        assert not panel.viewport._selection_rubber_band.isVisible()

        payload = module_window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "terrain_brush_stroke"
        assert metadata["last_brush"] == "raise"
        assert metadata["dirty_region_only"] is True
        assert module_window.controller.command_history.undo_label == "Sculpt terrain raise on grdev01_room01"
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_viewport_terrain_brush_alt_right_drag_changes_size_and_hardness_runtime() -> None:
    """Alt+right-drag edits Photoshop-style terrain brush size and hardness controls."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def mouse_event(kind, x: float, y: float, button, buttons, modifiers=QtCore.Qt.NoModifier):
        return QtGui.QMouseEvent(kind, QtCore.QPointF(x, y), button, buttons, modifiers)

    try:
        window.show()
        app.processEvents()
        window.create_map_studio_starter_terrain()
        window.builder_tab.terrainRadiusSpinBox.setValue(1)
        window.builder_tab.terrainSmoothStrengthSpinBox.setValue(0.5)
        window._sync_map_studio_terrain_brush_context(force_enabled=True)

        panel = window.viewport_panel
        canvas = panel.viewport.canvas
        press = mouse_event(
            QtCore.QEvent.MouseButtonPress,
            100,
            100,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.AltModifier,
        )
        move = mouse_event(
            QtCore.QEvent.MouseMove,
            148,
            64,
            QtCore.Qt.NoButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.AltModifier,
        )
        release = mouse_event(
            QtCore.QEvent.MouseButtonRelease,
            148,
            64,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoButton,
            QtCore.Qt.AltModifier,
        )

        assert panel.eventFilter(canvas, press) is True
        assert panel.eventFilter(canvas, move) is True
        assert panel.eventFilter(canvas, release) is True

        assert window.builder_tab.terrainRadiusSpinBox.value() == 4
        assert round(float(window.builder_tab.terrainSmoothStrengthSpinBox.value()), 2) == 0.70
        context = window.builder_tab.current_terrain_brush_context()
        assert context["radius"] == 4
        assert round(float(context["hardness"]), 2) == 0.70
        assert panel._terrain_brush_context["radius"] == 4
        assert round(float(panel._terrain_brush_context["hardness"]), 2) == 0.70
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_terrain_brush_shelf_persists_kmap_metadata_runtime(tmp_path: Path) -> None:
    """Visible terrain shelf brushes all record durable dirty-region KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def terrain_primitive() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]

    brush_actions = (
        ("sculpt_noise", "noise"),
        ("sculpt_terrace", "terrace"),
        ("sculpt_plateau", "plateau"),
        ("sculpt_flatten", "flatten"),
        ("sculpt_lower", "lower"),
        ("sculpt_smooth", "smooth"),
        ("sculpt_erode", "erode"),
        ("sculpt_ramp", "ramp"),
        ("sculpt_slope", "slope"),
        ("sculpt_pinch", "pinch"),
        ("sculpt_erase", "erase"),
    )

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")
        window.builder_tab.terrainRowSpinBox.setValue(2)
        window.builder_tab.terrainColumnSpinBox.setValue(2)
        window.builder_tab.terrainRadiusSpinBox.setValue(1)
        window.builder_tab.terrainDeltaSpinBox.setValue(0.25)
        window.builder_tab.terrainHeightSpinBox.setValue(0.35)
        window.builder_tab.terrainSmoothIterationsSpinBox.setValue(2)
        window.builder_tab.terrainSmoothStrengthSpinBox.setValue(0.75)
        app.processEvents()

        first_heights = [list(row) for row in terrain_primitive()["heights"]]
        seen_brushes: list[str] = []
        for action_key, brush in brush_actions:
            click_tool(action_key)

            primitive = terrain_primitive()
            metadata = primitive["metadata"]
            seen_brushes.append(brush)
            assert metadata["last_operation"] == "terrain_brush_stroke"
            assert metadata["last_brush"] == brush
            assert metadata["source"] == "map_studio:terrain_brush_stroke"
            assert metadata["dirty_region_only"] is True
            assert metadata["last_dirty_region"]["changed_sample_count"] >= 0
            assert metadata["last_brush_radius"] == 1
            assert metadata["last_brush_delta"] == 0.25
            assert metadata["last_brush_height"] == 0.35
            assert metadata["last_brush_performance"]["within_budget"] is True
            assert "last_brush_slope_report" in metadata
            assert window.controller.command_history.undo_label == f"Apply terrain brush {brush}"
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )
            assert window.statusBar().currentMessage().startswith(f"Applied terrain brush {brush};")

        final_primitive = terrain_primitive()
        assert final_primitive["heights"] != first_heights
        assert seen_brushes == [brush for _action, brush in brush_actions]

        boundary = window.controller.map_studio_export_object_boundaries()[0]
        boundary_metadata = boundary.to_metadata()
        assert boundary.terrain_authoring_status == "dirty_region_sculpted"
        assert boundary.terrain_last_operation == "terrain_brush_stroke"
        assert boundary.terrain_last_brush == "erase"
        assert boundary_metadata["terrain_last_brush"] == "erase"
        readiness_boundary = window.controller.authored_module_readiness().readiness.metadata["export_object_boundaries"][0]
        assert readiness_boundary["terrain_last_brush"] == "erase"

        kmap_path = tmp_path / "visible_terrain_brush_shelf.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_primitive = reloaded_payload["rooms"][0]["primitive"]
            reloaded_metadata = reloaded_primitive["metadata"]
            assert reloaded_primitive["heights"] == final_primitive["heights"]
            assert reloaded_metadata["last_operation"] == "terrain_brush_stroke"
            assert reloaded_metadata["last_brush"] == "erase"
            assert reloaded_metadata["last_brush_performance"]["within_budget"] is True
            assert reloaded_metadata["last_brush_slope_report"]["walkable_triangle_count"] >= 0
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_steep_terrain_slope_warning_runtime(tmp_path: Path) -> None:
    """Visible terrain sculpting reports steep slope readiness warnings before export."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def slope_warning_rows() -> list[int]:
        rows: list[int] = []
        for row in range(window.validation_panel.rowCount()):
            message = window.validation_panel.item(row, 1)
            if message is not None and "steeper than" in message.text() and "non-walk" in message.text():
                rows.append(row)
        return rows

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")
        window.builder_tab.terrainDeltaSpinBox.setValue(5.0)
        app.processEvents()
        click_tool("sculpt_raise")

        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        slope_report = metadata["last_brush_slope_report"]
        assert slope_report["max_slope_degrees"] > 35.0
        assert slope_report["non_walk_triangle_count"] == 2
        assert "steeper than 35.0 degrees" in slope_report["warnings"][0]
        assert window.controller.command_history.undo_label == "Apply terrain brush raise"

        select_preset("export")
        click_tool("validate")

        assert window.statusBar().currentMessage().startswith("Validation complete:")
        rows = slope_warning_rows()
        assert rows
        row = rows[0]
        assert window.validation_panel.item(row, 0).text() == "Warning"
        assert "steeper than 35.0 degrees" in window.validation_panel.item(row, 1).text()
        assert "non-walk" in window.validation_panel.item(row, 1).text()

        kmap_path = tmp_path / "steep_terrain_slope.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_report = reloaded_payload["rooms"][0]["primitive"]["metadata"]["last_brush_slope_report"]
            assert reloaded_report["non_walk_triangle_count"] == 2
            reloaded_issues = reloaded.controller.validate()
            assert any("steeper than 35.0 degrees" in getattr(issue, "message", "") for issue in reloaded_issues)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_table_reports_wok_topology_blockers_runtime(monkeypatch) -> None:
    """Visible Validate table displays invalid, degenerate, non-manifold, and open WOK topology rows."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from types import SimpleNamespace

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def row_for_item_prefix(prefix: str) -> int:
        for row in range(window.validation_panel.rowCount()):
            item = window.validation_panel.item(row, 2)
            if item is not None and item.text().startswith(prefix):
                return row
        raise AssertionError(f"Missing validation-table row for {prefix!r}")

    readiness = SimpleNamespace(
        metadata={
            "invalid_wok_face_count": 1,
            "degenerate_wok_face_count": 2,
            "non_manifold_wok_edge_count": 3,
            "open_wok_edge_count": 4,
        },
        inputs=(),
        blocking_messages=(
            "Room grbad generated WOK has 1 face(s) with invalid vertex indices.",
            "Room grbad generated WOK has 2 degenerate face(s).",
            "Room grbad generated WOK has 3 non-manifold walkable edge(s).",
        ),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=("Room grbad generated WOK has 4 open/boundary walkable edge(s).",),
        can_preview=False,
        ready_for_game_test=False,
        game_tested=False,
    )
    readiness_result = SimpleNamespace(readiness=readiness, warnings=(), blocking_messages=())

    try:
        window.show()
        app.processEvents()
        monkeypatch.setattr(window.controller, "authored_module_readiness", lambda: readiness_result)

        select_preset("export")
        click_tool("validate")

        issues = window.controller.validate()
        assert {
            "MAP_STUDIO_WOK_INVALID_TRIANGLE",
            "MAP_STUDIO_WOK_DEGENERATE_TRIANGLE",
            "MAP_STUDIO_WOK_NON_MANIFOLD_EDGE",
            "MAP_STUDIO_WOK_OPEN_EDGE_WARNING",
        } <= {
            str(getattr(issue, "code", "") or "") for issue in issues
        }

        invalid_row = row_for_item_prefix("authored_wok_invalid_triangle:blocker")
        assert window.validation_panel.item(invalid_row, 0).text() == "Error"
        assert "invalid vertex indices" in window.validation_panel.item(invalid_row, 1).text()
        assert "valid vertices" in window.validation_panel.item(invalid_row, 3).text()

        degenerate_row = row_for_item_prefix("authored_wok_degenerate_triangle:blocker")
        assert window.validation_panel.item(degenerate_row, 0).text() == "Error"
        assert "degenerate" in window.validation_panel.item(degenerate_row, 1).text()
        assert "zero-area WOK triangles" in window.validation_panel.item(degenerate_row, 3).text()

        non_manifold_row = row_for_item_prefix("authored_wok_non_manifold_edge:blocker")
        assert window.validation_panel.item(non_manifold_row, 0).text() == "Error"
        assert "non-manifold walkable edge" in window.validation_panel.item(non_manifold_row, 1).text()
        assert "valid ownership" in window.validation_panel.item(non_manifold_row, 3).text()

        open_edge_row = row_for_item_prefix("authored_wok_open_edge:warning")
        assert window.validation_panel.item(open_edge_row, 0).text() == "Warning"
        assert "open/boundary walkable edge" in window.validation_panel.item(open_edge_row, 1).text()
        assert "intentional room perimeter" in window.validation_panel.item(open_edge_row, 3).text()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_stale_package_after_modeling_edit_runtime(tmp_path: Path) -> None:
    """Visible Validate reports stale package/proof state after staged output is edited."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        staged_payload = window.controller.project.extra_sections["authored_module"]
        assert Path(staged_payload["pack_manifest_path"]).is_file()
        assert Path(staged_payload["proof_manifest_path"]).is_file()

        select_preset("component")
        window.builder_tab.primitiveTranslateXSpinBox.setValue(0.25)
        click_tool("move")

        edited_payload = window.controller.project.extra_sections["authored_module"]
        invalidation = edited_payload["export_proof_invalidation"]
        assert edited_payload["proof_manifest_path"] == staged_payload["proof_manifest_path"]
        assert invalidation["invalidates_previous_export"] is True
        assert invalidation["invalidates_game_proof"] is True
        assert invalidation["latest_summary"] == "Move primitive new_level_room01_floor"
        assert invalidation["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]

        click_tool("validate")

        stale_rows = []
        for row in range(window.validation_panel.rowCount()):
            item_id = window.validation_panel.item(row, 2)
            if item_id is not None and item_id.text() == "authored_module:export_proof_stale":
                stale_rows.append(row)
        assert stale_rows
        row = stale_rows[0]
        assert window.validation_panel.item(row, 0).text() == "Warning"
        assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in window.validation_panel.item(row, 1).text()
        assert "record fresh in-game proof" in window.validation_panel.item(row, 3).text()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_required_blockout_buttons_create_distinct_kmap_primitives_runtime(tmp_path: Path) -> None:
    """Visible blockout buttons create the required KOTOR-authored primitive types."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    expected_blockout = {
        "wall": ("wall", False),
        "cube": ("cube", False),
        "ramp": ("ramp", True),
        "stairs": ("stairs", True),
        "door_frame": ("door_frame", False),
        "arch": ("arch", False),
    }

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        rows = primitive_rows()
        floor = rows["new_level_room01_floor"]
        assert getattr(floor, "primitive_type") == "plane"
        assert getattr(floor, "supports_walkmesh_surface") is True
        assert window.controller.command_history.undo_label == "Add floor primitive"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        created_names: dict[str, str] = {}
        for action_key, (primitive_type, supports_wok) in expected_blockout.items():
            before_names = set(primitive_rows())
            click_tool(action_key)
            after_rows = primitive_rows()
            new_names = sorted(set(after_rows) - before_names)
            assert len(new_names) == 1
            created = after_rows[new_names[0]]
            created_names[action_key] = new_names[0]
            assert getattr(created, "primitive_type") == primitive_type
            assert getattr(created, "supports_walkmesh_surface") is supports_wok
            assert window.controller.command_history.undo_label == f"Add {action_key} primitive"
            assert window.controller.command_history.undo_stack[-1].metadata["primitive_kind"] == action_key
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )

        payload = window.controller.project.extra_sections["authored_module"]
        composition = payload["rooms"][0]["primitive"]
        authored_types = {
            str(item.get("name") or ""): str(item.get("type") or "")
            for item in composition.get("primitives", ())
        }
        for action_key, (primitive_type, _supports_wok) in expected_blockout.items():
            assert authored_types[created_names[action_key]] == primitive_type
        assert composition["metadata"]["last_added_primitive_kind"] == "arch"

        kmap_path = tmp_path / "blockout_primitives.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            assert reloaded_rows["new_level_room01_floor"].primitive_type == "plane"
            for action_key, (primitive_type, supports_wok) in expected_blockout.items():
                row = reloaded_rows[created_names[action_key]]
                assert row.primitive_type == primitive_type
                assert row.supports_walkmesh_surface is supports_wok
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_center_pivot_and_freeze_update_kmap_without_moving_bounds_runtime(tmp_path: Path) -> None:
    """Visible Pivot and Freeze commands update authored KMAP transforms without moving geometry."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def current_primitive() -> dict:
        data = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(data, dict)
        return dict(data)

    def set_visible_transform(
        *,
        translation: tuple[float, float, float],
        scale: tuple[float, float, float],
        pivot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        window.builder_tab.primitiveTranslateXSpinBox.setValue(translation[0])
        window.builder_tab.primitiveTranslateYSpinBox.setValue(translation[1])
        window.builder_tab.primitiveTranslateZSpinBox.setValue(translation[2])
        window.builder_tab.primitiveRotateZSpinBox.setValue(0.0)
        window.builder_tab.primitiveScaleXSpinBox.setValue(scale[0])
        window.builder_tab.primitiveScaleYSpinBox.setValue(scale[1])
        window.builder_tab.primitiveScaleZSpinBox.setValue(scale[2])
        window.builder_tab.primitivePivotXSpinBox.setValue(pivot[0])
        window.builder_tab.primitivePivotYSpinBox.setValue(pivot[1])
        window.builder_tab.primitivePivotZSpinBox.setValue(pivot[2])
        window.builder_tab.applyPrimitiveTransformButton.click()
        app.processEvents()

    def overlay_for(selection: dict):
        return window.controller.map_studio_universal_transform_overlay(
            room_resref=str(selection["room_resref"]),
            primitive_name=str(selection["primitive_name"]),
        )

    def rounded_triplet(values: object) -> tuple[float, float, float]:
        return tuple(round(float(value), 6) for value in tuple(values))  # type: ignore[arg-type]

    def primitive_row(name: str) -> object:
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows[name]

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        pivot_selection = current_primitive()
        assert pivot_selection["primitive_type"] == "cube"
        set_visible_transform(translation=(1.0, 2.0, 0.0), scale=(2.0, 1.0, 2.0))
        pivot_selection = current_primitive()
        pivot_before = overlay_for(pivot_selection)

        click_tool("center_pivot")

        pivot_after = overlay_for(pivot_selection)
        assert rounded_triplet(pivot_after.bounds_min) == rounded_triplet(pivot_before.bounds_min)
        assert rounded_triplet(pivot_after.bounds_max) == rounded_triplet(pivot_before.bounds_max)
        assert rounded_triplet(pivot_after.center) == rounded_triplet(pivot_before.center)
        centered = primitive_row(str(pivot_selection["primitive_name"]))
        assert tuple(round(float(value), 6) for value in getattr(centered, "pivot")) == (0.0, 0.0, 0.5)
        assert tuple(round(float(value), 6) for value in getattr(centered, "translation")) == (1.0, 2.0, 0.5)
        assert window.controller.command_history.undo_label == f"Center pivot {pivot_selection['primitive_name']}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        click_tool("cube")
        freeze_selection = current_primitive()
        assert freeze_selection["primitive_type"] == "cube"
        assert freeze_selection["primitive_name"] != pivot_selection["primitive_name"]
        set_visible_transform(translation=(1.0, 2.0, 3.0), scale=(2.0, 3.0, 4.0))
        freeze_selection = current_primitive()
        freeze_before = overlay_for(freeze_selection)

        click_tool("freeze_transform")

        freeze_after = overlay_for(freeze_selection)
        assert rounded_triplet(freeze_after.bounds_min) == rounded_triplet(freeze_before.bounds_min)
        assert rounded_triplet(freeze_after.bounds_max) == rounded_triplet(freeze_before.bounds_max)
        assert rounded_triplet(freeze_after.center) == rounded_triplet(freeze_before.center)
        frozen = primitive_row(str(freeze_selection["primitive_name"]))
        assert tuple(round(float(value), 6) for value in getattr(frozen, "translation")) == (0.0, 0.0, 0.0)
        assert tuple(round(float(value), 6) for value in getattr(frozen, "scale")) == (1.0, 1.0, 1.0)
        assert window.controller.command_history.undo_label == f"Freeze transform {freeze_selection['primitive_name']}"

        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "freeze_primitive_transform"
        assert metadata["center_pivot_space"] == "primitive_local_preserve_world_geometry"
        assert metadata["freeze_transform_space"] == "primitive_local_parametric_unrotated"
        frozen_payload = next(
            item
            for item in payload["rooms"][0]["primitive"]["primitives"]
            if item.get("instance_name") == freeze_selection["primitive_name"]
        )
        assert frozen_payload["size"] == [2.0, 3.0, 4.0]
        assert frozen_payload["center"] == [1.0, 2.0, 5.0]
        assert frozen_payload["transform"] == {
            "translation": [0.0, 0.0, 0.0],
            "rotation_degrees_z": 0.0,
            "scale": [1.0, 1.0, 1.0],
            "pivot": [0.0, 0.0, 0.0],
        }

        kmap_path = tmp_path / "pivot_freeze.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            reloaded_centered = reloaded_rows[str(pivot_selection["primitive_name"])]
            assert tuple(round(float(value), 6) for value in getattr(reloaded_centered, "pivot")) == (0.0, 0.0, 0.5)
            reloaded_frozen = reloaded_rows[str(freeze_selection["primitive_name"])]
            assert tuple(round(float(value), 6) for value in getattr(reloaded_frozen, "translation")) == (0.0, 0.0, 0.0)
            assert tuple(round(float(value), 6) for value in getattr(reloaded_frozen, "scale")) == (1.0, 1.0, 1.0)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_duplicate_special_and_edge_normals_persist_kmap_metadata_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    """Visible Duplicate Special and edge normal tools write durable KMAP metadata."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_duplicate_special_normals.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def select_primitive(primitive_name: str) -> None:
        combo = window.findChild(QtWidgets.QComboBox, "mapStudioRoomPrimitiveTransformComboBox")
        assert combo is not None
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_name") == primitive_name:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible primitive selection row {primitive_name!r}")

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        cube = next(row for row in primitive_rows().values() if getattr(row, "primitive_type", "") == "cube")
        select_primitive(cube.primitive_name)

        count_spin = window.findChild(QtWidgets.QSpinBox, "mapStudioDuplicateSpecialCountSpinBox")
        offset_x = window.findChild(QtWidgets.QDoubleSpinBox, "mapStudioDuplicateSpecialOffsetXSpinBox")
        assert count_spin is not None
        assert offset_x is not None
        count_spin.setValue(2)
        offset_x.setValue(0.5)
        app.processEvents()

        count_before = len(primitive_rows())
        click_tool("duplicate_special")

        duplicated = primitive_rows()
        first_duplicate = f"{cube.primitive_name}_dup_01"[:32]
        second_duplicate = f"{cube.primitive_name}_dup_02"[:32]
        assert len(duplicated) == count_before + 2
        assert first_duplicate in duplicated
        assert second_duplicate in duplicated
        assert duplicated[first_duplicate].translation[0] == cube.translation[0] + 0.5
        assert duplicated[second_duplicate].translation[0] == cube.translation[0] + 1.0
        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        duplicate_batch = metadata["duplicate_special_batches"][0]
        assert metadata["last_operation"] == "duplicate_special"
        assert metadata["last_duplicated_primitive"] == cube.primitive_name
        assert metadata["last_duplicate_special_names"] == [first_duplicate, second_duplicate]
        assert duplicate_batch["source_primitive"] == cube.primitive_name
        assert duplicate_batch["generated_primitive_names"] == [first_duplicate, second_duplicate]
        assert duplicate_batch["translation_offset"] == [0.5, 0.0, 0.0]
        assert window.controller.command_history.undo_label == f"Duplicate primitive {cube.primitive_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        select_primitive(cube.primitive_name)
        click_tool("soften_edges")
        payload = window.controller.project.extra_sections["authored_module"]
        edge_policy = payload["rooms"][0]["primitive"]["metadata"]["edge_normal_policy_by_target"][cube.primitive_name]
        assert edge_policy["edge_normal_policy"] == "soft"
        assert edge_policy["edge_normal_policy_operation"] == "soften_edges"
        assert edge_policy["edge_normal_policy_coordinate_space"] == "authored_room_composition_primitive_edges"
        assert window.controller.command_history.undo_label == "Soften edges"
        boundary = window.controller.map_studio_export_object_boundaries()[0]
        assert boundary.normal_policy_status == "authored_visual_normal_policy"
        assert cube.primitive_name in boundary.normal_policy_summary

        click_tool("harden_edges")
        payload = window.controller.project.extra_sections["authored_module"]
        hard_policy = payload["rooms"][0]["primitive"]["metadata"]["edge_normal_policy_by_target"][cube.primitive_name]
        assert hard_policy["edge_normal_policy"] == "hard"
        assert hard_policy["edge_normal_policy_operation"] == "harden_edges"
        assert window.controller.command_history.undo_label == "Harden edges"

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened = reader.controller.project.extra_sections["authored_module"]
        reopened_metadata = reopened["rooms"][0]["primitive"]["metadata"]
        assert reopened_metadata["last_operation"] == "harden_edges"
        assert reopened_metadata["last_duplicate_special_names"] == [first_duplicate, second_duplicate]
        assert reopened_metadata["duplicate_special_batches"][0]["generated_primitive_names"] == [
            first_duplicate,
            second_duplicate,
        ]
        assert reopened_metadata["edge_normal_policy_by_target"][cube.primitive_name]["edge_normal_policy"] == "hard"
        reopened_rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in reader.controller.authored_room_primitive_transforms()
        }
        assert first_duplicate in reopened_rows
        assert second_duplicate in reopened_rows
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2911_visible_wok_surface_combo_paints_required_kotor_intent_runtime(tmp_path: Path) -> None:
    """Visible WOK surface choices round-trip required KOTOR intent into saved KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    required_surfaces = {
        "walkable": ("4", "STONE", True),
        "non_walk": ("7", "NON_WALK", False),
        "door_transition": ("18", "DOOR", True),
        "water": ("6", "WATER", False),
        "grass": ("3", "GRASS", True),
        "metal": ("10", "METAL", True),
        "visual_only": ("8", "TRANSPARENT", False),
    }

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_surface(surface_id: str) -> dict:
        combo = window.builder_tab.primitiveSurfaceComboBox
        assert combo.isEnabled()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == surface_id:
                combo.setCurrentIndex(index)
                app.processEvents()
                return dict(data)
        raise AssertionError(f"Missing visible WOK surface choice {surface_id}")

    def floor_row() -> object:
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows["new_level_room01_floor"]

    try:
        window.show()
        app.processEvents()

        click_tool("floor")

        for semantic, (surface_id, surface_name, walkable) in required_surfaces.items():
            combo_data = select_surface(surface_id)
            assert str(combo_data.get("name") or "").upper() == surface_name
            assert bool(combo_data.get("walkable")) is walkable

            click_tool("paint_wok")

            styled_floor = floor_row()
            assert str(getattr(styled_floor, "surface_id")) == surface_id
            assert str(getattr(styled_floor, "surface_name")).upper() == surface_name
            assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )

            primitive = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
            floor_payload = primitive["floor"]
            metadata = floor_payload["material"]["metadata"]
            assert str(floor_payload["surface_id"]) == surface_id
            assert str(metadata["surface_id"]) == surface_id
            assert str(metadata["surface_name"]).upper() == surface_name
            assert primitive["metadata"]["last_style_edit"] == "new_level_room01_floor"

        kmap_path = tmp_path / "surface_intent.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_floor = reloaded_payload["rooms"][0]["primitive"]["floor"]
            assert str(reloaded_floor["surface_id"]) == required_surfaces["visual_only"][0]
            assert str(reloaded_floor["material"]["metadata"]["surface_name"]).upper() == required_surfaces["visual_only"][1]
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_inset_button_edits_floor_plan_kmap_state_runtime() -> None:
    """The visible Inset component tool routes through the authored KMAP command path."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        before = window.controller.project.extra_sections["authored_module"]

        click_tool("inset")

        after = window.controller.project.extra_sections["authored_module"]
        assert before != after
        assert window.controller.command_history.undo_label == "Inset grdev01_room01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        assert "Inset the selected authored floor plan" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()
