from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_prelaunch_library_payload_scans_before_main_window(tmp_path, monkeypatch) -> None:
    import src.gui.windows.qt_main_window as qt_main_window

    app_root = tmp_path
    (app_root / "settings.json").write_text(
        '{"k1_dir": "C:/Games/KOTOR", "k2_dir": "C:/Games/KOTOR2", "autoscan": true}',
        encoding="utf-8",
    )
    calls = []

    resource_manager = object()

    def fake_scan(k1_dir, k2_dir):
        calls.append((k1_dir, k2_dir))
        return resource_manager, [{"game": "K1", "resref": "pmbam", "source": k1_dir}]

    monkeypatch.setattr(qt_main_window, "_index_game_libraries_sync", fake_scan)
    statuses = []
    payload = qt_main_window._build_prelaunch_library_input(
        app_root,
        {"foo": "bar"},
        lambda title, detail: statuses.append((title, detail)),
    )

    assert payload["foo"] == "bar"
    assert calls == [("C:/Games/KOTOR", "C:/Games/KOTOR2")]
    assert payload["preloaded_library"]["detection_attempted"] is True
    assert payload["preloaded_library"]["_resource_manager"] is resource_manager
    assert payload["preloaded_library"]["rows"][0]["resref"] == "pmbam"
    assert any(title == "Indexing game libraries" for title, _detail in statuses)


def test_preloaded_library_skips_post_show_auto_detect_timer() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    init_source = inspect.getsource(QtGhostRiggerMainWindow.__init__)
    assert "self._preloaded_library" in init_source
    assert 'if not self._preloaded_library.get("detection_attempted")' in init_source
    assert "QtCore.QTimer.singleShot(250, self._auto_detect_dirs_on_startup)" in init_source
    assert 'preloaded.get("_resource_manager")' in inspect.getsource(
        QtGhostRiggerMainWindow._apply_preloaded_library
    )
    assert "manager = self._get_resource_manager()" in inspect.getsource(
        QtGhostRiggerMainWindow._populate_resource_panel
    )
    assert "self._suppress_theme_progress_toast = True" in init_source
    assert "QtCore.QTimer.singleShot(1200, self._enable_theme_progress_toasts)" in init_source
    assert "self._suppress_theme_progress_toast = False" in inspect.getsource(
        QtGhostRiggerMainWindow._enable_theme_progress_toasts
    )


def test_main_window_exposes_visual_profile_dropdown() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_bar_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    assert "self.visual_profile_combo = QtWidgets.QComboBox()" in command_bar_source
    assert "_populate_visual_profile_combo" in command_bar_source
    assert "_on_visual_profile_selected" in inspect.getsource(QtGhostRiggerMainWindow)


def test_startup_splash_uses_themed_embedded_progress() -> None:
    _qapp()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtProgressPanel, QtProgressToast, QtStartupSplash

    splash = QtStartupSplash(_REPO_ROOT)
    splash.set_status("Library ready", "6071 model resources indexed.", finished=True)

    assert isinstance(splash.progress_panel, QtProgressPanel)
    assert splash.logo_label.pixmap() is not None
    assert "GhostRigger (C) 2026 Shaolin (CrispyWonton)" in splash.copyright_label.text()
    assert "LordVaderCW" in splash.copyright_label.text()

    class Parent(QtWidgets.QWidget):
        theme_manager = None

    toast = QtProgressToast(Parent())
    assert isinstance(toast.progress_panel, QtProgressPanel)


def test_startup_splash_registers_with_theme_manager() -> None:
    _qapp()

    from PySide6 import QtWidgets
    from src.gui.libtheme import ThemeManager
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    manager = ThemeManager(
        _REPO_ROOT,
        {"theme_layout": {"theme_mode": "manual", "selected_theme": "matrix"}},
    )
    splash = QtStartupSplash(_REPO_ROOT, theme_manager=manager)
    matrix_style = splash.styleSheet()

    manager.themeChanged.emit(manager.get_theme("light"))
    for _ in range(8):
        QtWidgets.QApplication.processEvents()
    light_style = splash.styleSheet()

    assert splash.theme_manager is manager
    assert splash in manager.applier._aware_widgets
    assert "#00FF7A" in matrix_style
    assert "#1F6FEB" in light_style
    assert matrix_style != light_style


def test_startup_splash_reads_theme_customization_styles() -> None:
    _qapp()

    from src.gui.libtheme.theme_model import Theme
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    theme = Theme(
        id="custom",
        name="Custom",
        version="1",
        colors={
            "window.background": "#101010",
            "panel.background": "#202020",
            "panel.backgroundAlt": "#303030",
            "panel.altBackground": "#303030",
            "toolbar.border": "#445566",
            "accent.primary": "#00AAFF",
            "text.primary": "#FFFFFF",
            "text.secondary": "#CCCCCC",
            "input.background": "#050505",
            "success": "#44AA66",
            "splash.background": "#111122",
            "splash.panel": "#222233",
            "splash.brandBackground": "#333344",
            "splash.progressBackground": "#444455",
            "splash.border": "#556677",
            "splash.text": "#EEEEFF",
            "splash.secondaryText": "#AAAACC",
            "splash.accent": "#8899FF",
            "splash.progressTrack": "#050515",
            "splash.progressFill": "#22CC88",
        },
        metrics={"splash.width": 640, "splash.height": 260, "splash.logoSize": 48},
        styles={
            "splash.productText": "GhostRigger Premium",
            "splash.subtitleText": "Theme linked startup",
            "splash.copyrightText": "Custom copyright",
            "splash.surfaceStyle": "glossy",
        },
    )
    splash = QtStartupSplash(_REPO_ROOT, theme=theme)

    assert splash.product_label.text() == "GhostRigger Premium"
    assert splash.subtitle_label.text() == "Theme linked startup"
    assert splash.copyright_label.text() == "Custom copyright"
    assert splash.width() == 640
    assert splash.height() == 260
    assert "#111122" in splash.styleSheet()
    assert "#8899FF" in splash.styleSheet()
    assert "#22CC88" in splash.progress_panel.styleSheet()
    assert "qlineargradient" in splash.styleSheet()


def test_startup_splash_native_theme_uses_live_app_palette() -> None:
    app = _qapp()
    QtGui = pytest.importorskip("PySide6.QtGui")

    from src.gui.libtheme.theme_model import Theme
    from src.gui.qt_lib.windows.qt_main_window import QtStartupSplash

    old_palette = QtGui.QPalette(app.palette())
    native_palette = QtGui.QPalette(old_palette)
    native_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#1E1E1E"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#2D2D2D"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#3C3C3C"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Mid, QtGui.QColor("#282828"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#E81123"))
    native_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#FFFFFF"))
    native_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#FFFFFF"))
    app.setPalette(native_palette)
    theme = Theme(
        id="native",
        name="Native",
        version="1",
        colors={
            "splash.background": "#F3F3F3",
            "splash.panel": "#FFFFFF",
            "splash.accent": "#1F6FEB",
        },
        styles={"application.native": "true", "splash.surfaceStyle": "glossy"},
    )
    splash = None
    try:
        splash = QtStartupSplash(_REPO_ROOT, theme=theme)
        assert "#1E1E1E" in splash.styleSheet()
        assert "#3C3C3C" in splash.styleSheet()
        assert "#E81123" in splash.styleSheet()
        assert "#F3F3F3" not in splash.styleSheet()
        assert "qlineargradient" in splash.styleSheet()
        assert "#E81123" in splash.progress_panel.styleSheet()
    finally:
        if splash is not None:
            splash.deleteLater()
        app.setPalette(old_palette)


def test_progress_toast_reapplies_active_theme_on_show() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow, QtProgressToast

    show_source = inspect.getsource(QtGhostRiggerMainWindow._show_progress_toast)
    update_source = inspect.getsource(QtGhostRiggerMainWindow._update_progress_toast)
    finish_source = inspect.getsource(QtGhostRiggerMainWindow._finish_progress_toast)
    changed_source = inspect.getsource(QtGhostRiggerMainWindow._on_theme_changed)
    apply_source = inspect.getsource(QtGhostRiggerMainWindow._apply_progress_toast_theme)

    assert "_apply_progress_toast_theme()" in show_source
    assert "_apply_progress_toast_theme()" in update_source
    assert "_apply_progress_toast_theme()" in finish_source
    assert "self._apply_progress_toast_theme()" in changed_source
    assert "current_theme" in apply_source
    assert "get_theme()" in apply_source
    assert hasattr(QtProgressToast, "apply_native_theme")


def test_progress_panel_stylesheet_tracks_theme_tokens() -> None:
    _qapp()

    from src.gui.qt_lib.windows.qt_main_window import QtProgressPanel

    class Theme:
        def __init__(self, colors):
            self.colors = colors

        def color(self, token, default=None):
            return self.colors.get(token, default or "#000000")

    panel = QtProgressPanel()
    panel.apply_ghost_theme(
        Theme(
            {
                "panel.backgroundAlt": "#101010",
                "panel.altBackground": "#101010",
                "accent.primary": "#112233",
                "text.primary": "#eeeeee",
                "text.secondary": "#aaaaaa",
                "input.background": "#050505",
                "success": "#44aa66",
            }
        )
    )
    dark_style = panel.styleSheet()
    panel.apply_ghost_theme(
        Theme(
            {
                "panel.backgroundAlt": "#f0f0f0",
                "panel.altBackground": "#f0f0f0",
                "accent.primary": "#1F6FEB",
                "text.primary": "#1D2733",
                "text.secondary": "#4A5568",
                "input.background": "#ffffff",
                "success": "#1B8F45",
            }
        )
    )
    light_style = panel.styleSheet()

    assert "#112233" in dark_style
    assert "#1F6FEB" in light_style
    assert dark_style != light_style
