from __future__ import annotations

import os

import pytest


def _qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_content_browser_merges_models_modules_templates_and_animations() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "pmbam", "category": "Character", "source": "k1"},
        {"game": "K1", "resref": "m02aa_01a", "model_class": "tile", "source": "k1"},
    ])
    panel.set_animation_entries([
        {"model": "pmbam", "animation": "walk", "frames": 30, "source": "Current model"},
    ])

    asset_types = {asset.asset_type for asset in panel.visible_assets()}
    assert {"Model", "Module", "Blueprint", "Animation"}.issubset(asset_types)

    panel.select_asset_type("Animation")
    assert [asset.name for asset in panel.visible_assets()] == ["walk"]
    item = panel.asset_view.topLevelItem(0)
    panel.asset_view.setCurrentItem(item)
    assert panel.selected_entry()["animation"] == "walk"
    assert panel.selected_row() is None


def test_content_browser_search_and_game_filter_keep_library_rows_visible() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_rows([
        {"game": "K1", "resref": "n_darthmalak", "category": "Character", "source": "k1"},
        {"game": "K2", "resref": "c_boma", "category": "Creature", "source": "k2"},
    ])

    panel.search_edit.setText("boma")
    panel.game_filter.setCurrentText("K2")

    assets = panel.visible_assets()
    assert len(assets) == 1
    assert assets[0].name == "c_boma"
    item = panel.asset_view.topLevelItem(0)
    panel.asset_view.setCurrentItem(item)
    assert panel.selected_row()["resref"] == "c_boma"


def test_content_browser_splitter_keeps_user_adjusted_pane_sizes() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    class Layout:
        def panel(self, _name):
            return type("Panel", (), {"min_width": 220, "preferred_width": 420})()

        def spacing_value(self, _name, default=0):
            return default

    panel = QtContentBrowserPanel()
    panel.resize(760, 420)
    panel._apply_initial_splitter_sizes()
    initial = panel.splitter.sizes()

    panel.splitter.setSizes([180, 360, 220])
    panel._on_splitter_moved(180, 1)
    moved = panel.splitter.sizes()
    panel.apply_ghost_layout(Layout())

    assert moved != initial
    assert panel.splitter.sizes() == moved


def test_content_browser_keeps_scanned_animations_when_scene_selection_changes() -> None:
    _qapp()

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel

    panel = QtContentBrowserPanel()
    panel.set_scanned_animation_entries([
        {
            "game": "K1",
            "model": "S_Female02",
            "resref": "s_female02",
            "animation": "walk",
            "source": "Game Library (K1:s_female02)",
        },
    ])
    panel.set_scene_animation_entries([
        {
            "game": "K1",
            "model": "N_Bith",
            "object_name": "Cantina Bith",
            "animation": "pause1",
            "source": "Scene: Cantina Bith",
        },
    ])
    panel.select_asset_type("Animation")

    names = {asset.name for asset in panel.visible_assets()}
    assert {"walk", "pause1"} <= names

    panel.set_scene_animation_entries([
        {
            "game": "K1",
            "model": "N_DarthMalak",
            "object_name": "Malak",
            "animation": "talk",
            "source": "Scene: Malak",
        },
    ])

    names = {asset.name for asset in panel.visible_assets()}
    assert {"walk", "talk"} <= names
    assert "pause1" not in names


def test_floating_content_browser_host_resizes_single_dock() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    dock.setWidget(QtWidgets.QLabel("browser"))
    owner._detachable_panels["content_browser"] = dock

    assert host.tabPosition(QtCore.Qt.LeftDockWidgetArea) == QtWidgets.QTabWidget.North

    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    host.resize(980, 560)
    host.show()
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert host.centralWidget() is dock
    assert dock.width() >= 900

    host.resize(1180, 560)
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert dock.width() >= 1080


def test_floating_dock_host_can_combine_detached_panels() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _remove_dock_key_from_floating_hosts(self, key, *, keep_host=None):
            for host in list(dict.fromkeys(self._floating_dock_hosts.values())):
                if host is keep_host:
                    continue
                if key in host.dock_keys:
                    host.dock_keys.remove(key)
                    host._refresh_title()
                if not host.dock_keys:
                    host.hide()
            if keep_host is None:
                self._floating_dock_hosts.pop(key, None)

        def _floating_dock_host_label(self, host):
            titles = [
                self._detachable_panels[key].windowTitle()
                for key in host.dock_keys
                if key in self._detachable_panels
            ]
            if not titles:
                return "Floating Window"
            return f"Workspace: {' / '.join(titles)}" if len(titles) > 1 else f"Window: {titles[0]}"

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    content_host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    properties_host = QtFloatingDockHost(owner, "Properties", "properties")
    content_dock = QtWidgets.QDockWidget("Content Browser", content_host)
    properties_dock = QtWidgets.QDockWidget("Properties", properties_host)
    content_dock.setWidget(QtWidgets.QLabel("content"))
    properties_dock.setWidget(QtWidgets.QLabel("properties"))
    owner._detachable_panels = {
        "content_browser": content_dock,
        "properties": properties_dock,
    }

    content_host.add_detachable_dock("content_browser", content_dock, QtCore.Qt.LeftDockWidgetArea)
    assert content_host.centralWidget() is content_dock
    properties_host.add_detachable_dock("properties", properties_dock, QtCore.Qt.RightDockWidgetArea)
    content_host.add_detachable_dock("properties", properties_dock, QtCore.Qt.RightDockWidgetArea)

    assert content_host.centralWidget() is None
    assert content_host.dock_keys == ["content_browser", "properties"]
    assert properties_host.dock_keys == []
    assert owner._floating_dock_hosts["properties"] is content_host
    assert content_host.windowTitle() == "Workspace: Content Browser / Properties"


def test_floating_dock_host_ignores_deleted_dock_wrapper() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    import shiboken6

    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost, _qt_object_alive

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    shiboken6.delete(dock)

    assert not _qt_object_alive(dock)
    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    assert host.dock_keys == []


def test_content_browser_new_window_ignores_narrow_docked_saved_width() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    shell = SimpleNamespace(
        settings_data={
            "theme_layout": {
                "panel_sizes": {
                    "content_browser": {
                        "width": 180,
                        "height": 360,
                        "floating": False,
                    }
                }
            }
        },
        _detachable_panel_sizes={"content_browser": (760, 520)},
    )

    assert QtGhostRiggerMainWindow._detachable_panel_window_size(shell, "content_browser") == (760, 520)

    shell.settings_data["theme_layout"]["panel_sizes"]["content_browser"] = {
        "width": 420,
        "height": 480,
        "floating": True,
    }

    assert QtGhostRiggerMainWindow._detachable_panel_window_size(shell, "content_browser") == (760, 520)


def test_floating_host_clears_stale_dock_maximum_width() -> None:
    _qapp()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtFloatingDockHost

    class Owner(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self._dock_rehosting = False
            self._floating_dock_hosts = {}
            self._detachable_panels = {}

        def _close_floating_dock_host(self, _host):
            pass

    owner = Owner()
    host = QtFloatingDockHost(owner, "Content Browser", "content_browser")
    dock = QtWidgets.QDockWidget("Content Browser", host)
    dock.setWidget(QtWidgets.QLabel("browser"))
    dock.setMaximumWidth(500)
    owner._detachable_panels["content_browser"] = dock

    host.add_detachable_dock("content_browser", dock, QtCore.Qt.LeftDockWidgetArea)
    host.resize(900, 560)
    host.show()
    for _ in range(8):
        QtWidgets.QApplication.processEvents()

    assert dock.maximumWidth() >= 900
    assert dock.width() >= 860
