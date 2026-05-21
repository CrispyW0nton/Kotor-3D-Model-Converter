from __future__ import annotations

from pathlib import Path

from src.gui.libtheme.layout_loader import LayoutLoader
from src.gui.libtheme.layout_applier import button_mode_to_toolbutton_style
from src.gui.libtheme.qt_stylesheet_builder import QtStylesheetBuilder
from src.gui.libtheme.style_tokens import FALLBACK_COLORS, FALLBACK_METRICS, VALID_BUTTON_MODES
from src.gui.libtheme.theme_loader import ThemeLoader
from src.gui.libtheme.theme_manager import ThemeManager
from src.gui.libtheme.layout_manager import LayoutManager
from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer
from src.gui.qt_lib.viewports.qt_transform_typein_bar import transform_bar_stylesheet


ROOT = Path(__file__).resolve().parents[1]


def test_packaged_themes_load_and_validate() -> None:
    loader = ThemeLoader()
    themes = loader.load_dir(ROOT / "config" / "themes" / "themes")

    assert {"matrix", "dark", "light", "classic"}.issubset(themes)
    assert themes["matrix"].name == "Matrix"
    assert themes["matrix"].color("accent.primary") == "#00FF7A"
    assert themes["matrix"].legacy_colors()["accent"] == "#00FF7A"


def test_packaged_layouts_load_and_affect_metrics() -> None:
    loader = LayoutLoader()
    layouts = loader.load_dir(ROOT / "config" / "themes" / "layouts")

    assert {"default", "compact", "wide", "cinematic"}.issubset(layouts)
    assert layouts["compact"].toolbar("main").button_mode == "iconOnly"
    assert layouts["wide"].viewport.preferred_width > layouts["compact"].viewport.preferred_width


def test_stylesheet_builds_from_matrix_theme() -> None:
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "matrix.xml")
    assert theme is not None

    stylesheet = QtStylesheetBuilder().build(theme)

    assert "QMainWindow" in stylesheet
    assert "#00FF7A" in stylesheet
    assert "QSplitter::handle" in stylesheet


def test_required_theme_tokens_resolve_for_all_packaged_themes() -> None:
    themes = ThemeLoader().load_dir(ROOT / "config" / "themes" / "themes")

    for theme in themes.values():
        for token in FALLBACK_COLORS:
            assert theme.color(token).startswith("#"), (theme.id, token)
        assert "QPushButton:disabled" in QtStylesheetBuilder().build(theme)


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
    theme_manager = ThemeManager(ROOT, {"theme_layout": {"selected_theme": "matrix"}})
    layout_manager = LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}})

    assert theme_manager.get_theme().id == "matrix"
    assert layout_manager.get_layout().id == "default"
    assert "iconOnly" in VALID_BUTTON_MODES


def test_viewport_chrome_and_renderer_use_theme_tokens() -> None:
    theme = ThemeLoader().load_file(ROOT / "config" / "themes" / "themes" / "classic.xml")
    assert theme is not None

    stylesheet = transform_bar_stylesheet(theme)
    assert theme.color("transformBar.background") in stylesheet
    assert theme.color("input.background") in stylesheet
    assert theme.color("button.checked") in stylesheet

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_theme_colors(theme)

    expected_background = tuple(int(theme.color("viewport.background").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    expected_grid = tuple(int(theme.color("viewport.gridMinor").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    expected_axis = tuple(int(theme.color("error").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    assert renderer.viewport_background == expected_background
    assert renderer.grid_minor_color == expected_grid
    assert renderer.grid_x_axis_color == expected_axis
