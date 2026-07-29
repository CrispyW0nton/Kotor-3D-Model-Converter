from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_command_launcher_is_searchable_categorized_and_keyboard_actionable() -> None:
    app = _qt_app()

    from PySide6 import QtCore, QtGui, QtTest, QtWidgets
    from src.gui.windows.application_core.shared.window_chrome import _CommandLauncherDialog

    parent = QtWidgets.QMainWindow()
    map_action = QtGui.QAction("Open Map Studio", parent)
    texture_action = QtGui.QAction("Texture Tool", parent)
    triggered: list[str] = []
    map_action.triggered.connect(lambda: triggered.append("map"))
    dialog = _CommandLauncherDialog(
        [
            ("Studios", [map_action]),
            ("Asset Tools", [texture_action]),
        ],
        parent,
    )
    try:
        assert dialog.objectName() == "CommandLauncherDialog"
        assert dialog.accessibleName() == "Open a Studio or Tool"
        assert dialog.accessibleDescription()
        assert dialog.search_edit.accessibleName() == "Search studios and tools"
        assert dialog.search_edit.accessibleDescription()
        assert dialog.command_tree.accessibleDescription()
        assert dialog.close_button.accessibleDescription()
        assert (
            dialog.command_tree.header().sectionResizeMode(0)
            == QtWidgets.QHeaderView.Stretch
        )
        assert (
            dialog.command_tree.header().sectionResizeMode(1)
            == QtWidgets.QHeaderView.ResizeToContents
        )
        assert [dialog.command_tree.topLevelItem(index).text(0) for index in range(2)] == [
            "Studios",
            "Asset Tools",
        ]

        dialog.search_edit.setText("map")
        app.processEvents()

        assert not dialog.command_tree.topLevelItem(0).isHidden()
        assert dialog.command_tree.topLevelItem(1).isHidden()
        current = dialog.command_tree.currentItem()
        assert current is not None
        assert current.text(0) == "Open Map Studio"

        dialog.show()
        dialog.search_edit.setFocus(QtCore.Qt.TabFocusReason)
        app.processEvents()
        QtTest.QTest.keyClick(dialog.search_edit, QtCore.Qt.Key_Tab)
        app.processEvents()
        assert app.focusWidget() in {
            dialog.command_tree,
            dialog.command_tree.viewport(),
        }

        dialog._activate_item(current)
        assert triggered == ["map"]
    finally:
        dialog.close()
        parent.close()


def test_main_command_bar_prioritizes_primary_actions_and_groups_the_rest() -> None:
    app = _qt_app()

    from PySide6 import QtGui, QtWidgets
    from src.gui.libtheme.layout_manager import LayoutManager
    from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin

    class Host(QtWidgets.QMainWindow, WindowChromeMixin):
        def __init__(self) -> None:
            super().__init__()
            self.settings_data = {}
            self.layout_manager = LayoutManager(
                ROOT,
                {"theme_layout": {"selected_layout": "default"}},
            )

        def _icon(self, *_args, **_kwargs):
            pixmap = QtGui.QPixmap(8, 8)
            pixmap.fill()
            return QtGui.QIcon(pixmap)

        def _configure_dock_toggle_action(self, *_args, **_kwargs) -> None:
            return None

        def _log(self, *_args, **_kwargs) -> None:
            return None

        def apply_workspace(self, *_args, **_kwargs) -> None:
            return None

        def __getattr__(self, name: str):
            if name.startswith("_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    host = Host()
    try:
        host._build_actions()
        command_bar = host._make_command_bar()
        command_bar.show()
        app.processEvents()

        primary = [
            button
            for button in command_bar.findChildren(QtWidgets.QToolButton)
            if button.property("_gr_full_text")
            and button.objectName() != "CommandStripMenuButton"
        ]
        grouped = command_bar.findChildren(QtWidgets.QToolButton, "CommandStripMenuButton")
        assert len(primary) <= 7
        assert {
            str(button.property("_gr_full_text"))
            for button in primary
        } >= {"New Scene", "Open Scene", "Save", "Studios and Tools", "Settings"}
        assert {
            str(button.property("_gr_full_text"))
            for button in grouped
        } == {"Import", "Export", "Create", "Panels"}

        launcher = command_bar.findChild(QtWidgets.QToolButton, "CommandLauncherButton")
        assert launcher is not None
        assert launcher.text() == "Studios and Tools"
        assert launcher.accessibleName() == "Open Studios and Tools"

        for button in (*primary, *grouped):
            assert button.accessibleName()
            assert button.toolTip()

        full_width = command_bar.sizeHint().width()
        command_bar.resize(max(1, full_width - 1), command_bar.sizeHint().height())
        host._update_command_bar_responsiveness()
        assert all(not button.text() for button in host._responsive_command_buttons)
        assert all(
            button.property("_gr_ignore_layout_button_mode") is True
            for button in host._responsive_command_buttons
        )

        command_bar.resize(full_width + 100, command_bar.sizeHint().height())
        host._update_command_bar_responsiveness()
        assert [button.text() for button in host._responsive_command_buttons[:3]] == [
            "New Scene",
            "Open Scene",
            "Save",
        ]

        launcher_groups = dict(host._command_launcher_groups())
        assert host.modules_action in launcher_groups["World Building"]
        assert host.retarget_workbench_action in launcher_groups["Character & Animation"]
        assert host.resources_panel_action in launcher_groups["Browsers & Panels"]
    finally:
        host.close()


def test_startup_defaults_preserve_saved_navigation_layout_and_overrides() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    state = SimpleNamespace(
        settings_data={
            "viewport_navigation_profile": "maya",
            "theme_layout": {
                "selected_layout": "compact",
                "layout_overrides": {"compact": {"main_width": 1234}},
            },
            "show_adjust_pivot_toolbox": True,
        }
    )

    QtGhostRiggerMainWindow._apply_startup_ui_defaults(state)

    assert state.settings_data["viewport_navigation_profile"] == "maya"
    assert state.settings_data["theme_layout"]["selected_layout"] == "compact"
    assert state.settings_data["theme_layout"]["layout_overrides"] == {
        "compact": {"main_width": 1234}
    }
    assert state.settings_data["show_adjust_pivot_toolbox"] is True


def test_settings_exposes_developer_mode_and_preserves_navigation_choice() -> None:
    _qt_app()

    from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog

    dialog = QtSettingsDialog(
        {
            "developer_mode": True,
            "viewport_navigation_profile": "maya",
        }
    )
    try:
        assert dialog.developer_mode_check.isChecked()
        assert "IPC" in dialog.developer_mode_check.toolTip()
        values = dialog.values()
        assert values["developer_mode"] is True
        assert values["viewport_navigation_profile"] == "maya"
    finally:
        dialog.close()


def test_main_shell_shortcuts_are_unique() -> None:
    _qt_app()

    from PySide6 import QtWidgets
    from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin

    class Host(QtWidgets.QMainWindow, WindowChromeMixin):
        def _icon(self, *_args, **_kwargs):
            from PySide6 import QtGui

            return QtGui.QIcon()

        def _configure_dock_toggle_action(self, *_args, **_kwargs) -> None:
            return None

        def __getattr__(self, name: str):
            if name.startswith("_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    host = Host()
    try:
        host._build_actions()
        assert host.command_launcher_action.shortcut().toString() == "Ctrl+K"
        assert host.anims_action.shortcut() != host.retarget_workbench_action.shortcut()
    finally:
        host.close()


def test_developer_menu_appears_only_after_explicit_opt_in() -> None:
    _qt_app()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin

    class Host(QtWidgets.QMainWindow, WindowChromeMixin):
        def __init__(self) -> None:
            super().__init__()
            self.settings_data = {"developer_mode": False}

        def _icon(self, *_args, **_kwargs):
            return QtGui.QIcon()

        def _configure_dock_toggle_action(self, *_args, **_kwargs) -> None:
            return None

        def _rebuild_recent_scenes_menu(self) -> None:
            return None

        def __getattr__(self, name: str):
            if name.startswith("_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    host = Host()
    try:
        host._build_actions()
        host._build_menu()
        assert not host.developer_menu_action.isVisible()

        host.settings_data["developer_mode"] = True
        host._sync_developer_actions_visibility()
        assert host.developer_menu_action.isVisible()
    finally:
        host.close()
