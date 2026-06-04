from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from src.gui.libtheme.layout_loader import LayoutLoader
from src.gui.libtheme.collapsible_group import CollapsibleGroupBox
from src.gui.libtheme.layout_applier import LayoutApplier, button_mode_to_toolbutton_style
from src.gui.libtheme.layout_model import ToolbarLayout
from src.gui.libtheme.qt_stylesheet_builder import QtStylesheetBuilder
from src.gui.libtheme.style_tokens import FALLBACK_COLORS, FALLBACK_METRICS, FALLBACK_STYLES, VALID_BUTTON_MODES
from src.gui.libtheme.theme_applier import ThemeApplier
from src.gui.libtheme.theme_editor_window import ThemeEditorWindow
from src.gui.libtheme.theme_loader import ThemeLoader
from src.gui.libtheme.theme_manager import ThemeManager
from src.gui.libtheme.layout_manager import LayoutManager
from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog
from src.core.camera.arcball_camera import ArcBallCamera
from src.core.rendering.frame_core.renderer import FrameRenderer
from src.gui.qt_lib.viewports.qt_transform_typein_bar import transform_bar_stylesheet


ROOT = Path(__file__).resolve().parents[1]


def _rgb_float(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _srgb_to_linear(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def test_packaged_themes_load_and_validate() -> None:
    loader = ThemeLoader()
    themes = loader.load_dir(ROOT / "config" / "themes" / "themes")

    assert {
        "default",
        "default_matrix",
        "default_droid",
        "default_dark",
        "default_light",
        "default_classic",
    } == set(themes)
    assert themes["default"].name == "Default"
    assert themes["default"].is_native()
    assert themes["default"].color("splash.accent") != "#00FF7A"
    assert themes["default"].color("splash.background") != themes["default_matrix"].color("splash.background")
    default_core = {
        themes["default"].color("window.background").upper(),
        themes["default"].color("panel.background").upper(),
        themes["default"].color("viewport.background").upper(),
        themes["default"].color("accent.primary").upper(),
    }
    matrix_core = {
        themes["default_matrix"].color("window.background").upper(),
        themes["default_matrix"].color("panel.background").upper(),
        themes["default_matrix"].color("viewport.background").upper(),
        themes["default_matrix"].color("accent.primary").upper(),
    }
    assert not (default_core & matrix_core)
    assert themes["default_matrix"].is_palette_only()
    assert not themes["default_matrix"].is_native()
    assert themes["default_matrix"].color("accent.primary") == "#00FF7A"
    assert themes["default_matrix"].metric("toolbar.height") == themes["default"].metric("toolbar.height")
    assert themes["default_droid"].color("button.background") == "#4A4A4A"
    assert themes["default_droid"].font("matrix").family == "Aurebesh AF"
    assert themes["default_droid"].font("default").family == themes["default"].font("default").family


def test_default_ui_theme_variants_are_palette_only_without_qss() -> None:
    loader = ThemeLoader()
    themes = loader.load_dir(ROOT / "config" / "themes" / "themes")

    for theme_id in ("default_matrix", "default_droid", "default_dark", "default_light", "default_classic"):
        theme = themes[theme_id]
        assert theme.is_palette_only()
        assert QtStylesheetBuilder().build(theme) == ""
        assert ThemeApplier().build_stylesheet(theme) == ""
        assert theme.metric("button.height") == themes["default"].metric("button.height")
        assert theme.metric("splitter.handleWidth") == themes["default"].metric("splitter.handleWidth")


def test_theme_defaults_prefer_default_ui_variants() -> None:
    settings = ThemeManager(ROOT, {}).settings

    assert settings.selected_theme == "default"
    assert settings.os_light_theme == "default_light"
    assert settings.os_dark_theme == "default_dark"

    manager = ThemeManager(ROOT, {})
    assert manager.get_theme().id == "default"
    assert manager.get_theme("missing").id == "default"
    assert manager.select_theme("missing", apply=False).id == "default"


def test_about_dialog_reports_runtime_details_and_copies_summary() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.dialogs.qt_dialogs import QtAboutDialog

    class FakeViewport:
        def render_state_status_text(self) -> str:
            return "Renderer: Direct3D (WGPU) | Display: Textured"

    class FakeThemeManager:
        def __init__(self):
            self._theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_matrix.xml")

        def get_theme(self):
            return self._theme

    class FakeParent(QtWidgets.QWidget):
        APP_TITLE = "GhostRigger-K1-K2  //  Odyssey Engine Pipeline v6.1"
        APP_VERSION = "6.1.0"

        def __init__(self):
            super().__init__()
            self.app_root = ROOT
            self.viewport = FakeViewport()
            self.theme_manager = FakeThemeManager()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    parent = FakeParent()
    dialog = QtAboutDialog(parent)
    try:
        dialog.apply_ghost_theme(parent.theme_manager.get_theme())

        version = dialog.findChild(QtWidgets.QLabel, "AboutVersionValue")
        renderer = dialog.findChild(QtWidgets.QLabel, "AboutRendererValue")
        theme = dialog.findChild(QtWidgets.QLabel, "AboutThemeValue")
        bioware = dialog.findChild(QtWidgets.QPushButton, "AboutCompanyBioWareButton")
        obsidian = dialog.findChild(QtWidgets.QPushButton, "AboutCompanyObsidianButton")
        lucasarts = dialog.findChild(QtWidgets.QPushButton, "AboutCompanyLucasArtsButton")

        assert dialog.minimumWidth() >= 900
        assert dialog.minimumHeight() >= 650
        assert version is not None and "6.1.0" in version.text()
        assert renderer is not None and "Direct3D (WGPU)" in renderer.text()
        assert theme is not None and "default_matrix" in theme.text()
        assert "#00FF7A" in dialog.styleSheet()
        assert bioware is not None and bioware.property("creditUrl") == "https://www.bioware.com/"
        assert obsidian is not None and obsidian.property("creditUrl") == "https://www.obsidian.net/"
        assert lucasarts is not None and lucasarts.property("creditUrl") == "https://www.lucasfilm.com/what-we-do/games/"
        assert "LordVaderCW" in dialog._details_text
        assert "CrispyW0nton / ShaolinGhost" in dialog._details_text
        assert "PyKotor / OpenKotOR" in dialog._details_text
        assert "PySide6 / Qt" in dialog._details_text

        dialog.copy_details()
        assert "GhostRigger-K1-K2" in app.clipboard().text()
        assert "Renderer: Direct3D (WGPU)" in app.clipboard().text()
    finally:
        dialog.deleteLater()
        parent.deleteLater()
        app.processEvents()


def test_packaged_layouts_load_and_affect_metrics() -> None:
    loader = LayoutLoader()
    layouts = loader.load_dir(ROOT / "config" / "themes" / "layouts")

    assert {
        "default",
        "compact",
        "wide",
        "cinematic",
        "profile_animation",
        "profile_mesh_editing",
        "profile_lighting",
        "profile_cinegraphics",
        "profile_clean",
    }.issubset(layouts)
    assert layouts["compact"].toolbar("main").button_mode == "iconOnly"
    assert layouts["wide"].viewport.preferred_width > layouts["compact"].viewport.preferred_width
    assert layouts["default"].dock_groups
    assert layouts["profile_lighting"].dock_groups[1].docks == ["lighting", "cameras", "properties"]
    assert layouts["profile_animation"].name == "Animation"
    assert layouts["profile_mesh_editing"].name == "Mesh Editing"
    assert layouts["profile_lighting"].name == "Lighting"
    assert layouts["profile_cinegraphics"].name == "Cinegraphics"
    assert layouts["profile_clean"].name == "Default"
    assert all("Visual Profile" not in layouts[layout_id].name for layout_id in (
        "profile_animation",
        "profile_mesh_editing",
        "profile_lighting",
        "profile_cinegraphics",
        "profile_clean",
    ))
    assert layouts["profile_clean"].panel("contentBrowser").visible is False
    assert layouts["profile_clean"].panel("outputLog").visible is True
    assert layouts["profile_clean"].panel("pythonTerminal").visible is True
    assert layouts["profile_clean"].panel("outputLog").preferred_height < layouts["default"].panel("outputLog").preferred_height
    assert layouts["profile_mesh_editing"].panel("nodes").visible is False
    assert layouts["default"].panel("spriteMaterials").visible is False
    assert layouts["profile_mesh_editing"].panel("spriteMaterials").visible is True
    assert layouts["profile_cinegraphics"].panel("spriteMaterials").visible is True


def test_visual_profile_dock_groups_stay_workflow_scoped() -> None:
    loader = LayoutLoader()
    layouts = loader.load_dir(ROOT / "config" / "themes" / "layouts")

    expected = {
        "profile_animation": [
            ["scene", "content_browser"],
            ["animations", "properties", "nodes"],
        ],
        "profile_mesh_editing": [
            ["scene", "content_browser"],
            ["module_meshes", "mesh_tools", "adjust_pivot", "properties"],
        ],
        "profile_lighting": [
            ["scene"],
            ["lighting", "cameras", "properties"],
        ],
        "profile_cinegraphics": [
            ["scene"],
            ["cameras", "lighting", "properties"],
        ],
        "profile_clean": [],
    }

    for profile_id, groups in expected.items():
        layout = layouts[profile_id]
        assert [group.docks for group in layout.dock_groups] == groups
        assert all(group.visible for group in layout.dock_groups)


def test_visual_profile_apply_hides_detachable_docks_outside_profile() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    layout = LayoutLoader().load_file(ROOT / "config" / "themes" / "layouts" / "profile_lighting.xml")
    assert layout is not None

    window = QtWidgets.QMainWindow()
    window._detachable_panels = {}  # type: ignore[attr-defined]
    for key in (
        "animations",
        "nodes",
        "lighting",
        "cameras",
        "module_meshes",
        "mesh_tools",
        "adjust_pivot",
        "2das",
        "resources",
    ):
        dock = QtWidgets.QDockWidget(key, window)
        dock.setWidget(QtWidgets.QLabel(key))
        dock.show()
        window._detachable_panels[key] = dock  # type: ignore[attr-defined]

    LayoutApplier()._apply_panels(layout, window)

    assert not window._detachable_panels["lighting"].isHidden()  # type: ignore[attr-defined]
    assert not window._detachable_panels["cameras"].isHidden()  # type: ignore[attr-defined]
    assert window._detachable_panels["animations"].isHidden()  # type: ignore[attr-defined]
    assert window._detachable_panels["nodes"].isHidden()  # type: ignore[attr-defined]
    assert window._detachable_panels["module_meshes"].isHidden()  # type: ignore[attr-defined]
    assert window._detachable_panels["adjust_pivot"].isHidden()  # type: ignore[attr-defined]
    window.deleteLater()
    app.processEvents()


def test_layout_apply_hides_optional_detachable_docks_not_declared_by_layout() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    for layout_name in ("compact.xml", "cinematic.xml"):
        layout = LayoutLoader().load_file(ROOT / "config" / "themes" / "layouts" / layout_name)
        assert layout is not None

        window = QtWidgets.QMainWindow()
        window._detachable_panels = {}  # type: ignore[attr-defined]
        for key in ("nodes", "2das", "resources"):
            dock = QtWidgets.QDockWidget(key, window)
            dock.setWidget(QtWidgets.QLabel(key))
            dock.show()
            window._detachable_panels[key] = dock  # type: ignore[attr-defined]

        LayoutApplier()._apply_panels(layout, window)

        assert window._detachable_panels["nodes"].isHidden()  # type: ignore[attr-defined]
        assert window._detachable_panels["2das"].isHidden()  # type: ignore[attr-defined]
        assert window._detachable_panels["resources"].isHidden()  # type: ignore[attr-defined]
        window.deleteLater()
    app.processEvents()


def test_layout_apply_leaves_content_browser_width_user_resizable() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    layout = LayoutLoader().load_file(ROOT / "config" / "themes" / "layouts" / "default.xml")
    assert layout is not None

    window = QtWidgets.QMainWindow()
    window.content_browser_dock = QtWidgets.QDockWidget("Content Browser", window)  # type: ignore[attr-defined]
    window.content_browser_dock.setMinimumWidth(500)  # type: ignore[attr-defined]
    window.content_browser_dock.setMaximumWidth(510)  # type: ignore[attr-defined]
    window.scene_dock = QtWidgets.QDockWidget("Scene", window)  # type: ignore[attr-defined]
    window.properties_dock = QtWidgets.QDockWidget("Properties", window)  # type: ignore[attr-defined]
    window.properties_dock.setMaximumWidth(510)  # type: ignore[attr-defined]
    window.log_panel = QtWidgets.QWidget(window)  # type: ignore[attr-defined]

    LayoutApplier()._apply_panels(layout, window)

    assert window.content_browser_dock.minimumWidth() == 0  # type: ignore[attr-defined]
    assert window.content_browser_dock.maximumWidth() >= 1000000  # type: ignore[attr-defined]
    assert window.properties_dock.minimumWidth() == layout.panel("properties").min_width  # type: ignore[attr-defined]
    assert window.properties_dock.maximumWidth() >= 1000000  # type: ignore[attr-defined]
    window.deleteLater()


def test_layout_manager_merges_user_dock_profile_overrides() -> None:
    manager = LayoutManager(
        ROOT,
        {
            "theme_layout": {
                "selected_layout": "profile_clean",
                "layout_overrides": {
                    "profile_clean": {
                        "panels": {
                            "nodes": {
                                "visible": True,
                                "region": "left",
                                "min_width": 260,
                                "preferred_width": 420,
                                "min_height": 160,
                                "preferred_height": 520,
                            }
                        },
                        "dock_groups": [
                            {
                                "id": "user_left_1",
                                "area": "left",
                                "mode": "tabbed",
                                "visible": True,
                                "active": "nodes",
                                "docks": ["nodes", "2das"],
                            }
                        ],
                    }
                },
            }
        },
    )

    layout = manager.get_layout("profile_clean")

    assert layout.panel("contentBrowser").visible is False
    assert layout.panel("nodes").visible is True
    assert layout.panel("nodes").preferred_width == 420
    assert [group.docks for group in layout.dock_groups] == [["nodes", "2das"]]


def test_default_matrix_theme_is_palette_only_without_qss() -> None:
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_matrix.xml")
    assert theme is not None

    stylesheet = QtStylesheetBuilder().build(theme)

    assert theme.is_palette_only()
    assert stylesheet == ""
    assert theme.color("accent.primary") == "#00FF7A"


def test_default_theme_uses_native_qt_styling() -> None:
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default.xml")
    assert theme is not None
    assert theme.is_native()
    assert QtStylesheetBuilder().build(theme) == ""


def test_packaged_custom_themes_define_spinbox_stepper_tokens() -> None:
    themes = ThemeLoader().load_dir(ROOT / "config" / "themes" / "themes")
    required = {
        "spinbox.buttonBackground",
        "spinbox.buttonHover",
        "spinbox.buttonPressed",
        "spinbox.buttonBorder",
        "spinbox.arrow",
    }

    for theme_id, theme in themes.items():
        if theme.is_native() or theme.is_palette_only():
            continue
        assert required.issubset(theme.colors), theme_id
        stylesheet = QtStylesheetBuilder().build(theme)
        assert "QDoubleSpinBox::up-button" in stylesheet
        assert "QTreeWidget::item:selected" in stylesheet
        assert "QTreeWidget::item:selected:!active" in stylesheet
        assert theme.color("spinbox.buttonBorder") in stylesheet
        expected_arrow = "spin_up_light.svg" if theme.mode == "dark" else "spin_up_dark.svg"
        assert expected_arrow in stylesheet


def test_required_theme_tokens_resolve_for_all_packaged_themes() -> None:
    themes = ThemeLoader().load_dir(ROOT / "config" / "themes" / "themes")

    for theme in themes.values():
        for token in FALLBACK_COLORS:
            assert theme.color(token).startswith("#"), (theme.id, token)
        stylesheet = QtStylesheetBuilder().build(theme)
        if theme.is_native() or theme.is_palette_only():
            assert stylesheet == ""
        else:
            assert "QPushButton:disabled" in stylesheet
            assert "viewportToolbar.background" not in stylesheet
            assert theme.color("viewportToolbar.border") in stylesheet


def test_native_theme_normalizes_stale_matrix_splash_fallbacks(tmp_path: Path) -> None:
    theme_path = tmp_path / "default.xml"
    theme_path.write_text(
        """<theme id="default" name="Default" version="1">
  <metadata><mode>native</mode></metadata>
  <styles><style name="application.native" value="true"/></styles>
  <colors>
    <color name="splash.background" value="#0B0F0D"/>
    <color name="splash.accent" value="#00FF7A"/>
    <color name="splash.progressFill" value="#00FF7A"/>
  </colors>
</theme>
""",
        encoding="utf-8",
    )

    theme = ThemeLoader().load_file(theme_path)

    assert theme is not None
    assert theme.is_native()
    assert theme.color("splash.background") == "#F3F3F3"
    assert theme.color("splash.accent") == "#1F6FEB"
    assert theme.color("splash.progressFill") == "#1B8F45"


def test_native_theme_normalizes_stale_matrix_palette_fallbacks(tmp_path: Path) -> None:
    theme_path = tmp_path / "default.xml"
    theme_path.write_text(
        """<theme id="default" name="Default" version="1">
  <metadata><mode>native</mode></metadata>
  <styles><style name="application.native" value="true"/></styles>
  <colors>
    <color name="window.background" value="#0B0F0D"/>
    <color name="panel.background" value="#111916"/>
    <color name="button.checked" value="#00FF7A"/>
    <color name="button.pressed" value="#1B2A22"/>
    <color name="accent.primary" value="#00FF7A"/>
    <color name="viewport.gridMajor" value="#1B2A22"/>
    <color name="matrixBar.text" value="#00FF7A"/>
    <color name="success" value="#00FF7A"/>
  </colors>
</theme>
""",
        encoding="utf-8",
    )

    theme = ThemeLoader().load_file(theme_path)

    assert theme is not None
    assert theme.is_native()
    assert theme.color("window.background") == "#F3F3F3"
    assert theme.color("panel.background") == "#FFFFFF"
    assert theme.color("button.checked") == "#1F6FEB"
    assert theme.color("button.pressed") == "#D9E2EC"
    assert theme.color("accent.primary") == "#1F6FEB"
    assert theme.color("viewport.gridMajor") == "#D5DAE1"
    assert theme.color("matrixBar.text") == "#1F4F8F"
    assert theme.color("success") == "#1B8F45"


def test_required_layout_metrics_resolve_for_all_packaged_layouts() -> None:
    layouts = LayoutLoader().load_dir(ROOT / "config" / "themes" / "layouts")
    required_spacing = {"margin", "panelSpacing", "toolbarSpacing", "splitterHandleWidth", "inputHeight", "tabHeight", "tableRowHeight", "treeRowHeight"}

    for layout in layouts.values():
        assert required_spacing.issubset(layout.spacing), layout.id
        assert layout.toolbar("main").button_mode in VALID_BUTTON_MODES
        assert layout.spacing_value("inputHeight") > 0
        assert layout.toolbar("main").height > 0
        assert layout.panel("library").preferred_width >= layout.panel("library").min_width


def test_button_mode_parser_has_safe_fallback() -> None:
    assert button_mode_to_toolbutton_style("iconOnly") != button_mode_to_toolbutton_style("textOnly")
    assert button_mode_to_toolbutton_style("unknown") == button_mode_to_toolbutton_style("textBesideIcon")


def test_invalid_theme_and_layout_do_not_crash(tmp_path: Path) -> None:
    bad_theme = tmp_path / "bad_theme.xml"
    bad_layout = tmp_path / "bad_layout.xml"
    bad_theme.write_text("<theme><broken>", encoding="utf-8")
    bad_layout.write_text("<layout><broken>", encoding="utf-8")

    theme = ThemeLoader().load_file(bad_theme)
    layout = LayoutLoader().load_file(bad_layout)

    assert theme is not None
    assert layout is not None
    assert theme.warnings
    assert layout.warnings


def test_managers_load_packaged_defaults() -> None:
    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default_matrix"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})

    assert theme_manager.get_theme().id == "default_matrix"
    assert layout_manager.get_layout().id == "default"
    assert "iconOnly" in VALID_BUTTON_MODES


def test_theme_applier_precache_warms_later_instances() -> None:
    previous_cache = dict(ThemeApplier._global_stylesheet_cache)
    ThemeApplier._global_stylesheet_cache.clear()
    try:
        themes = ThemeLoader().load_dir(ROOT / "config" / "themes" / "themes")

        result = ThemeApplier.precache_stylesheets(themes.values())

        assert result["failed"] == 0
        assert result["built"] == len(themes)
        classic = themes["default_classic"]
        key = ThemeApplier._theme_cache_key(classic)
        assert key in ThemeApplier._global_stylesheet_cache

        applier = ThemeApplier()
        stylesheet = applier.build_stylesheet(classic)

        assert stylesheet == ThemeApplier._global_stylesheet_cache[key]
        assert stylesheet == ""
        assert key not in applier._stylesheet_cache
    finally:
        ThemeApplier._global_stylesheet_cache.clear()
        ThemeApplier._global_stylesheet_cache.update(previous_cache)


def test_collapsible_group_toggle_stays_small_under_theme_and_layout() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    old_stylesheet = app.styleSheet()
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_matrix.xml")
    assert theme is not None
    container = QtWidgets.QWidget()
    outer = QtWidgets.QVBoxLayout(container)
    group = CollapsibleGroupBox("Selection Mode")
    inner = QtWidgets.QVBoxLayout(group)
    inner.addWidget(QtWidgets.QPushButton("Object"))
    outer.addWidget(group)
    try:
        app.setStyleSheet(QtStylesheetBuilder().build(theme))
        LayoutApplier().apply_toolbar_button_mode(
            container,
            ToolbarLayout(id="main", button_mode="textOnly", icon_size=22, height=48),
        )
        container.resize(320, 140)
        container.show()
        app.processEvents()

        toggle = group._toggle
        assert toggle.property("_gr_ignore_layout_button_mode") is True
        assert toggle.width() == CollapsibleGroupBox.TOGGLE_SIZE
        assert toggle.height() == CollapsibleGroupBox.TOGGLE_SIZE
        assert toggle.maximumWidth() == CollapsibleGroupBox.TOGGLE_SIZE
        assert toggle.maximumHeight() == CollapsibleGroupBox.TOGGLE_SIZE
    finally:
        container.deleteLater()
        app.setStyleSheet(old_stylesheet)


def test_matrix_bar_controls_live_in_theme_editor_not_settings(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default_matrix"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})
    settings_dialog = QtSettingsDialog(
        {"matrix_background": False, "matrix_bar": {"style": "gif", "glyphs": "ABC"}},
        theme_manager=theme_manager,
        layout_manager=layout_manager,
    )
    editor = ThemeEditorWindow(
        theme_manager,
        layout_manager,
        matrix_bar_settings={"style": "gif", "glyphs": "ABC", "font_family": "Consolas"},
        matrix_background_enabled=False,
    )
    try:
        settings_tabs = settings_dialog.findChild(QtWidgets.QTabWidget, "SettingsSectionsTabs")
        assert settings_tabs is not None
        assert "Matrix Bar" not in [settings_tabs.tabText(index) for index in range(settings_tabs.count())]

        editor_tabs = next(
            tabs
            for tabs in editor.centralWidget().findChildren(QtWidgets.QTabWidget)
            if "Colours" in [tabs.tabText(index) for index in range(tabs.count())]
        )
        assert "Matrix Bar" in [editor_tabs.tabText(index) for index in range(editor_tabs.count())]
        assert "Splash" in [editor_tabs.tabText(index) for index in range(editor_tabs.count())]
        assert editor.matrix_bar_style.currentData() == "gif"
        assert editor.matrix_bar_glyphs.text() == "ABC"

        image_path = tmp_path / "matrix_bar.png"
        image = QtGui.QImage(24, 12, QtGui.QImage.Format_RGB32)
        image.fill(QtGui.QColor("#FF0044"))
        assert image.save(str(image_path))

        editor.matrix_bar_style.setCurrentIndex(editor.matrix_bar_style.findData("png"))
        editor.matrix_bar_image.setText(str(image_path))
        editor._set_matrix_bar_text_style("matrixBar.imagePath", str(image_path))

        assert editor._theme.styles["matrixBar.style"] == "png"
        assert editor._theme.styles["matrixBar.imagePath"] == str(image_path)
        assert not editor.matrix_bar_preview.source_pixmap().isNull()
        editor._set_matrix_bar_crop_from_preview(10.0, 20.0, 30.0, 40.0)
        assert editor._theme.styles["matrixBar.cropX"] == "10.0"
        assert editor._theme.styles["matrixBar.cropH"] == "40.0"
        assert editor.matrix_bar_preview.maximumHeight() == 240
        editor.matrix_bar_preview.resize(620, 240)
        rendered = QtGui.QPixmap(editor.matrix_bar_preview.size())
        rendered.fill(QtGui.QColor("#000000"))
        editor.matrix_bar_preview.render(rendered)
        assert rendered.toImage().pixelColor(310, 120) == QtGui.QColor("#FF0044")
        assert editor.matrix_bar_preview._crop_rect().width() < editor.matrix_bar_preview._image_rect.width()
    finally:
        editor.deleteLater()
        settings_dialog.deleteLater()


def test_theme_editor_splash_customization_updates_preview_and_theme() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default_matrix"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})
    editor = ThemeEditorWindow(theme_manager, layout_manager)
    try:
        assert editor.splash_product.text() == FALLBACK_STYLES["splash.productText"]
        editor.splash_product.setText("GhostRigger Premium")
        editor._set_splash_style("splash.productText", "GhostRigger Premium")
        editor.splash_subtitle.setText("Theme linked startup")
        editor._set_splash_style("splash.subtitleText", "Theme linked startup")
        editor.splash_copyright.setPlainText("Custom copyright")
        editor._set_splash_style("splash.copyrightText", "Custom copyright")
        editor._set_splash_metric("splash.logoSize", 96)
        editor._set_splash_color("splash.accent", "#8844CC")
        editor._set_splash_color("splash.progressFill", "#228833")
        editor._set_splash_style("splash.surfaceStyle", "glossy")

        assert editor._theme.styles["splash.productText"] == "GhostRigger Premium"
        assert editor._theme.styles["splash.subtitleText"] == "Theme linked startup"
        assert editor._theme.styles["splash.copyrightText"] == "Custom copyright"
        assert editor._theme.styles["splash.surfaceStyle"] == "glossy"
        assert editor._theme.metrics["splash.logoSize"] == 96
        assert editor._theme.colors["splash.accent"] == "#8844CC"
        assert editor._theme.colors["splash.progressFill"] == "#228833"
        assert editor.splash_color_edits["splash.accent"].text() == "#8844CC"
        assert editor.splash_preview.product_label.text() == "GhostRigger Premium"
        assert editor.splash_preview.subtitle_label.text() == "Theme linked startup"
        assert "Custom copyright" in editor.splash_preview.copyright_label.text()
        assert "#8844CC" in editor.splash_preview.styleSheet()
        assert "#228833" in editor.splash_preview.styleSheet()
        assert "qlineargradient" in editor.splash_preview.styleSheet()
    finally:
        editor.deleteLater()
        app.processEvents()


def test_theme_editor_native_splash_uses_live_app_palette() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
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

    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})
    editor = ThemeEditorWindow(theme_manager, layout_manager)
    try:
        assert editor._theme.is_native()
        assert editor._theme.color("window.background") == "#1E1E1E"
        assert editor._theme.color("splash.background") == "#1E1E1E"
        assert editor._theme.color("splash.panel") == "#3C3C3C"
        assert editor._theme.color("splash.accent") == "#E81123"
        assert editor.splash_color_edits["splash.background"].text() == "#1E1E1E"
        assert "#1E1E1E" in editor.splash_preview.styleSheet()
    finally:
        editor.deleteLater()
        app.setPalette(old_palette)
        app.processEvents()


def test_theme_editor_programmatic_close_skips_dirty_prompt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default_matrix"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})
    editor = ThemeEditorWindow(theme_manager, layout_manager)
    try:
        editor._mark_dirty()
        editor.show()
        app.processEvents()
        editor.close()
        app.processEvents()
        assert not editor.isVisible()
    finally:
        editor.deleteLater()
        app.processEvents()


def test_matrix_bar_media_is_header_only_and_crop_aware() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    apply_source = inspect.getsource(QtGhostRiggerMainWindow._apply_matrix_theme)
    native_source = inspect.getsource(QtGhostRiggerMainWindow.apply_native_theme)

    assert "QtMatrixPanel" not in command_source
    assert "command_bar" not in apply_source
    assert "command_bar" not in native_source
    assert "matrixBar.cropX" in inspect.getsource(QtGhostRiggerMainWindow._matrix_bar_settings)


def test_main_window_native_theme_keeps_dock_separator_grip() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    native_source = inspect.getsource(QtGhostRiggerMainWindow.apply_native_theme)

    assert "QMainWindow::separator" in native_source
    assert "panel.border" in native_source
    assert "width: 4px" in native_source
    assert "height: 4px" in native_source


def test_main_window_reserves_fixed_command_bar_height() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    reserved_source = inspect.getsource(QtGhostRiggerMainWindow._sync_reserved_top_rows)
    apply_source = inspect.getsource(LayoutApplier.apply_layout)

    assert "command_bar_scroll" not in reserved_source
    assert "PM_ScrollBarExtent" not in reserved_source
    assert "host_height = max(36, height, host.sizeHint().height())" in reserved_source
    assert "_sync_reserved_top_rows" in apply_source


def test_viewport_chrome_and_renderer_use_theme_tokens() -> None:
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_classic.xml")
    assert theme is not None

    stylesheet = transform_bar_stylesheet(theme)
    assert theme.color("transformBar.background") in stylesheet
    assert theme.color("input.background") in stylesheet
    assert theme.color("button.checked") in stylesheet
    app_stylesheet = QtStylesheetBuilder().build(theme)
    assert app_stylesheet == ""

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_theme_colors(theme)

    expected_background = tuple(int(theme.color("viewport.background").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    expected_grid = tuple(int(theme.color("viewport.gridMinor").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    expected_axis = tuple(int(theme.color("error").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    assert renderer.viewport_background == expected_background
    assert renderer.grid_minor_color == expected_grid
    assert renderer.grid_x_axis_color == expected_axis


def test_wgpu_renderer_uses_theme_tokens_for_viewport_overlays() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.renderer_backend import RendererBackend

    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_classic.xml")
    assert theme is not None
    renderer = WgpuRenderer(RendererBackend.WGPU_D3D12)

    renderer.set_theme_colors(theme)

    assert renderer.viewport_background == pytest.approx(_rgb_float(theme.color("viewport.background")))
    assert renderer.grid_minor_color == pytest.approx(_rgb_float(theme.color("viewport.gridMinor")))
    assert renderer.grid_major_color == pytest.approx(_rgb_float(theme.color("viewport.gridMajor")))
    assert renderer.wire_color == pytest.approx(_rgb_float(theme.color("accent.primary")))
    assert renderer.hovered_edge_color == pytest.approx(_rgb_float(theme.color("viewport.helper.meshHover")))
    assert renderer.selected_edge_color == pytest.approx(_rgb_float(theme.color("viewport.selection")))
    assert renderer.hidden_line_color == pytest.approx(_rgb_float(theme.color("viewport.border")))
    assert renderer.missing_texture_color_b == pytest.approx(_rgb_float(theme.color("viewport.background")))
    assert renderer.get_diagnostics()["viewport_theme_colors"]["wire"] == pytest.approx(renderer.wire_color)


def test_wgpu_renderer_uses_native_palette_for_viewport_overlays() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.renderer_backend import RendererBackend

    renderer = WgpuRenderer(RendererBackend.WGPU_D3D12)

    renderer.set_native_palette_colors(
        base=(235, 238, 242),
        text=(30, 34, 40),
        highlight=(0, 120, 215),
    )

    assert renderer.viewport_background == pytest.approx((235 / 255.0, 238 / 255.0, 242 / 255.0))
    assert renderer.grid_minor_color == pytest.approx((198 / 255.0, 201 / 255.0, 206 / 255.0))
    assert renderer.grid_major_color == pytest.approx((174 / 255.0, 177 / 255.0, 181 / 255.0))
    assert renderer.wire_color == pytest.approx((0.0, 120 / 255.0, 215 / 255.0))
    assert renderer.hovered_edge_color == pytest.approx((0.0, 215 / 255.0, 181 / 255.0))
    assert renderer.selected_edge_color == pytest.approx((1.0, 210 / 255.0, 63 / 255.0))
    assert renderer.missing_texture_color_a == pytest.approx(renderer.wire_color)
    assert renderer.missing_texture_color_b == pytest.approx(renderer.viewport_background)


def test_wgpu_renderer_linearizes_viewport_colours_for_srgb_surfaces() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.renderer_backend import RendererBackend

    renderer = WgpuRenderer(RendererBackend.WGPU_D3D12)
    renderer.format = "bgra8unorm-srgb"
    background = (23 / 255.0, 25 / 255.0, 28 / 255.0)

    assert renderer._target_rgb(background) == pytest.approx(tuple(_srgb_to_linear(channel) for channel in background))
    assert renderer._target_rgba((*background, 1.0))[:3] == pytest.approx(renderer._target_rgb(background))

    mvp = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    color = (1 / 255.0, 0.0, 0.0, 1.0)
    pick_uniform = renderer._line_uniform_bytes(mvp, color, target_color=False)
    assert struct.unpack("4f", pick_uniform[64:80]) == pytest.approx(color)

    renderer.format = "bgra8unorm"
    assert renderer._target_rgb(background) == pytest.approx(background)


def test_moderngl_renderer_diagnostics_include_renderer_stats() -> None:
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer

    renderer = ModernGLRenderer()
    renderer.perf.update(
        {
            "last_frame_ms": 12.25,
            "gpu_upload_ms": 1.5,
            "draw_ms": 4.75,
            "readback_ms": 2.0,
            "tri_count": 3456,
        }
    )

    diagnostics = renderer.get_diagnostics()

    assert diagnostics["performance"]["frame_time_ms"] == pytest.approx(12.25)
    assert diagnostics["performance"]["upload_ms"] == pytest.approx(1.5)
    assert diagnostics["performance"]["draw_ms"] == pytest.approx(4.75)
    assert diagnostics["performance"]["readback_ms"] == pytest.approx(2.0)
    assert diagnostics["triangle_count"] == 3456


def test_viewport_renderer_statistics_lines_include_active_renderer() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    class FakeRenderer:
        name = "ModernGL"
        perf = {"tri_count": 1}

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    try:
        lines = viewport._renderer_statistics_lines(
            FakeRenderer(),
            {
                "name": "ModernGL",
                "backend": "ModernGL",
                "gpu": "NVIDIA Test GPU",
                "triangle_count": 1234,
                "mesh_cache_size": 12,
                "texture_cache_size": 5,
                "performance": {
                    "frame_time_ms": 16.25,
                    "draw_ms": 3.5,
                    "upload_ms": 1.25,
                    "readback_ms": 0.75,
                },
            },
        )

        assert lines[0] == "ModernGL"
        assert "Frame 16.2 ms" in lines[1]
        assert "Draw 3.5" in lines[1]
        assert "Tris 1,234" in lines[1]
        assert "NVIDIA Test GPU" in lines[2]
        assert "Meshes 12" in lines[2]
        assert "Textures 5" in lines[2]
    finally:
        viewport.deleteLater()
        app.processEvents()


def test_live_surface_diagnostics_sit_below_overlay_hud() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    from src.gui.qt_lib.viewports.viewport_host import RendererSurfaceHost

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host = RendererSurfaceHost()
    surface = QtWidgets.QLabel("surface")
    try:
        host.resize(640, 360)
        host.show()
        host.set_renderer_surface(surface, backend_id="pygfx_wgpu", live_surface=True)
        host.set_overlay_pixmap(QtGui.QPixmap(64, 64))
        host.set_diagnostics_text("Renderer\nFrame 16.0 ms\nTris 1")
        app.processEvents()

        label = host.findChild(QtWidgets.QLabel, "ViewportDiagnosticsOverlay")
        assert label is not None
        assert label.y() >= 90
    finally:
        host.deleteLater()
        app.processEvents()


def test_viewport_emits_persistent_render_state_status() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    seen: list[str] = []
    viewport.renderStateChanged.connect(seen.append)
    try:
        initial = viewport.render_state_status_text()
        assert "Renderer:" in initial
        assert "Display:" in initial

        viewport.set_shade_mode("wire")

        assert seen
        assert "Renderer:" in seen[-1]
        assert "Display: Wireframe" in seen[-1]

        viewport.set_renderer_settings(RendererSettings(backend=RendererBackend.WGPU_D3D12))
        assert "Renderer: Direct3D (WGPU)" in viewport.render_state_status_text()
    finally:
        viewport.deleteLater()
        app.processEvents()


def test_viewport_renderer_settings_noop_does_not_recreate_wgpu_surface() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    class FakeRenderer:
        backend_id = "wgpu_d3d12"

        def __init__(self) -> None:
            self.canvas = None
            self.set_settings_calls = 0
            self.created_surfaces = 0

        @property
        def active_renderer(self):
            return self

        def get_diagnostics(self):
            return {"backend_id": self.backend_id, "name": "Direct3D (WGPU)"}

        def create_surface_widget(self, parent=None):
            self.created_surfaces += 1
            self.canvas = QtWidgets.QLabel("surface", parent)
            return self.canvas

        def set_settings(self, settings):
            self.set_settings_calls += 1

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    renderer = FakeRenderer()
    try:
        surface = QtWidgets.QLabel("existing", viewport.canvas)
        renderer.canvas = surface
        viewport._gpu_renderer = renderer
        viewport._owns_gpu_renderer = True
        viewport.canvas.set_renderer_surface(surface, backend_id="wgpu_d3d12", live_surface=True)

        viewport.set_renderer_settings(RendererSettings())
        viewport._sync_renderer_surface(force=True)

        assert renderer.set_settings_calls == 0
        assert renderer.created_surfaces == 0
        assert viewport.canvas.current_surface() is surface
    finally:
        viewport.deleteLater()
        app.processEvents()


def test_renderer_has_native_theme_overlay_defaults_without_theme_apply() -> None:
    renderer = FrameRenderer(ArcBallCamera())

    assert renderer._ambient > 0.0
    assert renderer._anim_pose is None
    assert renderer.show_gimbal is True
    assert renderer.show_walkmesh is False
    assert renderer._walkmesh_overlay is None


def test_native_viewport_theme_keeps_overlay_render_path_available() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import pytest
    from PySide6 import QtGui, QtWidgets

    pytest.importorskip("PIL")

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    old_palette = QtGui.QPalette(app.palette())
    native_palette = QtGui.QPalette(old_palette)
    native_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(235, 238, 242))
    native_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(30, 34, 40))
    native_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(224, 226, 230))
    native_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(25, 28, 34))
    native_palette.setColor(QtGui.QPalette.ColorRole.Mid, QtGui.QColor(126, 132, 142))
    native_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(0, 120, 215))
    native_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(native_palette)
    viewport = QtViewportWidget()
    try:
        themed = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "default_classic.xml")
        assert themed is not None
        viewport.apply_ghost_theme(themed)
        assert viewport._renderer.hud_fill != (30, 34, 40)
        viewport.apply_native_theme()
        assert viewport._renderer.viewport_background == (235, 238, 242)
        assert viewport._renderer.hud_fill == (224, 226, 230)
        assert viewport._renderer.hud_success_fill == (0, 120, 215)

        root = ModelNode(name="root")
        mesh = ModelNode(
            name="tri",
            vertices=[(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
            faces=[(0, 1, 2)],
        )
        root.children.append(mesh)
        mesh.parent = root
        viewport._use_gpu = False
        viewport.load_model(KotorModel(name="NativeOverlaySmoke", root_node=root))

        image = viewport._render_frame(320, 240)

        assert image is not None
        assert viewport._transform_gizmo.renderer.handles
    finally:
        viewport.deleteLater()
        app.setPalette(old_palette)
