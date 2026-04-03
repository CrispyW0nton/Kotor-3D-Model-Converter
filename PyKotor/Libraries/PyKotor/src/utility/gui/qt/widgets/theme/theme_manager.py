"""Theme manager: apply themes/styles, no persistence. Host app owns settings."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import qtpy
from qtpy.QtCore import QDir, QDirIterator, QFile, QTextStream, Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QStyle, QStyleFactory

from utility.gui.qt.widgets.theme.theme_apply import (
    apply_style as _apply_style,
    apply_tooltip_style_to_app,
    get_original_style as _get_original_style,
)
from utility.gui.qt.widgets.theme.theme_catalog import build_builtin_theme_configs
from utility.gui.qt.widgets.theme.theme_types import ThemeSources

if TYPE_CHECKING:
    from qtpy.QtCore import QObject, QPoint
    from qtpy.QtGui import QFont, QMouseEvent
    from qtpy.QtWidgets import QLayout, QWidget


class ThemeManager:
    """Applies theme/style/palette to QApplication. No persistence; host app owns settings."""

    def __init__(
        self,
        original_style: str | None = None,
        theme_sources: ThemeSources | None = None,
        on_theme_error: Callable[[str, str], None] | None = None,
    ):
        self.original_style: str = original_style or _get_original_style()
        self._theme_sources: ThemeSources = theme_sources or ThemeSources()
        self._on_theme_error: Callable[[str, str], None] | None = on_theme_error
        self._builtin_configs: dict[str, dict[str, Any]] | None = None

    def _build_builtin_theme_configs(self) -> dict[str, dict[str, Any]]:
        if self._builtin_configs is None:
            self._builtin_configs = build_builtin_theme_configs(self)
        return self._builtin_configs

    def get_available_themes(self) -> tuple[str, ...]:
        """List all available themes (QRC QSS, extra-themes JSON, built-ins)."""
        themes: list[str] = []
        for prefix in self._theme_sources.qrc_prefixes:
            it = QDirIterator(QDir(prefix), QDirIterator.IteratorFlag.Subdirectories)
            while True:
                file = it.next()
                if not file or not file.strip():
                    break
                name = os.path.splitext(os.path.basename(file))[0].lower()
                if name and name not in themes:
                    themes.append(name)
        for dir_str in self._theme_sources.extra_theme_dirs:
            base = Path(dir_str)
            if not base.exists() or not base.is_dir():
                continue
            try:
                for json_file in base.glob("*.json"):
                    stem = json_file.stem.lower()
                    if "config" in stem or "settings" in stem or stem == "template":
                        continue
                    if stem and stem not in themes:
                        themes.append(stem)
            except OSError:
                continue
        for key in self._build_builtin_theme_configs():
            if key and key.lower() not in [t.lower() for t in themes]:
                themes.append(key)
        return tuple(sorted(themes))

    @staticmethod
    def get_default_styles() -> tuple[str, ...]:
        """Available Qt style names (original case)."""
        styles = [k for k in QStyleFactory.keys() if k and k.strip()]
        return tuple(sorted(styles))

    @classmethod
    def get_original_style(cls) -> str:
        """Current application style name (lowercase)."""
        return _get_original_style()

    @staticmethod
    def _parse_hex_color(color_str: str) -> QColor:
        if not color_str or not isinstance(color_str, str):
            return QColor()
        color_str = color_str.strip()
        if len(color_str) == 9 and color_str.startswith("#"):
            color_str = color_str[:7]
        if len(color_str) == 4 and color_str.startswith("#"):
            r, g, b = color_str[1], color_str[2], color_str[3]
            color_str = f"#{r}{r}{g}{g}{b}{b}"
        try:
            return QColor(color_str)
        except Exception:
            return QColor()

    def _create_palette_from_vscode_colors(self, colors: dict[str, str]) -> QPalette:
        def get_color(key: str, fallback: str | None = None) -> QColor:
            s = colors.get(key) or (fallback or "")
            if not s:
                return QColor()
            c = self._parse_hex_color(s)
            return c if c.isValid() else QColor()

        primary_bg = get_color("input.background") or get_color("dropdown.background") or get_color("button.background") or get_color("editor.background", "#2D2D2D")
        if not primary_bg.isValid():
            primary_bg = QColor(45, 45, 45)
        secondary_bg = get_color("sideBar.background") or get_color("activityBar.background") or get_color("editor.background", "#1E1E1E")
        if not secondary_bg.isValid():
            secondary_bg = QColor(30, 30, 30)
        text_color = get_color("foreground") or get_color("editor.foreground") or get_color("input.foreground", "#FFFFFF")
        if not text_color.isValid():
            text_color = QColor(255, 255, 255)
        tooltip_base = get_color("editorHoverWidget.background") or get_color("editorWidget.background") or get_color("dropdown.background")
        if not tooltip_base.isValid() or tooltip_base.alpha() < 200:
            tooltip_base = QColor(secondary_bg)
        highlight = get_color("editor.selectionBackground") or get_color("list.activeSelectionBackground") or get_color("focusBorder") or get_color("button.background", "#0078D4")
        if not highlight.isValid():
            highlight = QColor(0, 120, 212)
        if self._get_luminance(highlight) < 0.3:
            highlight = self.adjust_color(highlight, lightness=180)
        bright_text = get_color("foreground", "#FFFFFF")
        if not bright_text.isValid():
            bright_text = QColor(255, 255, 255)
        if self._get_luminance(bright_text) < 0.8:
            bright_text = QColor(255, 255, 255)
        text_color = self._ensure_contrast(text_color, secondary_bg, min_ratio=4.5)
        return self.create_palette(primary_bg, secondary_bg, text_color, tooltip_base, highlight, bright_text)

    def _load_vscode_theme(self, theme_filename: str) -> dict[str, Any] | None:
        theme_path: Path | None = None
        for dir_str in self._theme_sources.extra_theme_dirs:
            base = Path(dir_str)
            if not base.exists() or not base.is_dir():
                continue
            candidate = base / theme_filename
            if candidate.exists() and candidate.is_file():
                theme_path = candidate
                break
        if not theme_path:
            name_lower = theme_filename.lower()
            for dir_str in self._theme_sources.extra_theme_dirs:
                base = Path(dir_str)
                if not base.exists() or not base.is_dir():
                    continue
                for j in base.glob("*.json"):
                    if "config" in j.stem.lower() or "settings" in j.stem.lower():
                        continue
                    if j.name.lower() == name_lower:
                        theme_path = j
                        break
                if theme_path:
                    break
        if not theme_path or not theme_path.exists():
            return None
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                theme_data = json.load(f)
        except Exception:
            return None
        if not theme_data or "colors" not in theme_data:
            return None
        colors = theme_data.get("colors", {})
        if not colors:
            return None
        palette = self._create_palette_from_vscode_colors(colors)
        return {"style": "Fusion", "palette": lambda p=palette: p, "sheet": ""}

    def _get_theme_config(self, theme_name: str) -> dict[str, Any]:
        vscode = self._load_vscode_theme(f"{theme_name}.json")
        if vscode:
            return vscode
        for alt in (f"{theme_name}-color-theme.json", f"{theme_name}-dark.json", f"{theme_name}-light.json"):
            vscode = self._load_vscode_theme(alt)
            if vscode:
                return vscode
        configs = self._build_builtin_theme_configs()
        theme_lower = theme_name.lower()
        for key in configs:
            if key.lower() == theme_lower:
                return configs[key]
        return configs.get(theme_name, configs["sourcegraph-dark"])

    def apply_theme_and_style(
        self,
        theme_name: str | None = None,
        style_name: str | None = None,
        *,
        fallback_theme: str = "sourcegraph-dark",
        fallback_style: str = "Fusion",
    ) -> None:
        """Apply theme and style to QApplication. Caller is responsible for persisting choices."""
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            return
        theme_name = theme_name or fallback_theme
        style_name = style_name if style_name is not None else fallback_style

        if theme_name == "QDarkStyle":
            if not importlib.util.find_spec("qdarkstyle"):  # pyright: ignore[reportAttributeAccessIssue]
                if self._on_theme_error:
                    self._on_theme_error("Theme not found", "QDarkStyle is not installed in this environment.")
                return
            import qdarkstyle  # pyright: ignore[reportMissingImports]
            effective = self.original_style if style_name == "" else (style_name or self.original_style)
            if effective:
                obj = QStyleFactory.create(effective)
                if obj:
                    app.setStyle(obj)
            app_style = app.style()
            if app_style:
                app.setPalette(app_style.standardPalette())
            app.setStyleSheet(qdarkstyle.load_stylesheet())
            apply_tooltip_style_to_app(app)
            return

        theme_name = theme_name or fallback_theme
        config = self._get_theme_config(theme_name)
        sheet_val = config.get("sheet", "")
        sheet = str(sheet_val(app) if callable(sheet_val) else sheet_val)
        palette_val = config.get("palette", None)
        palette = palette_val() if callable(palette_val) else (palette_val if isinstance(palette_val, QPalette) else None)
        if palette is None:
            app_style = app.style()
            palette = app_style.standardPalette() if app_style else app.palette()

        if style_name == "":
            effective_style = "Fusion" if theme_name.lower() in ("fusion (light)", "sourcegraph-dark") else self.original_style
        elif style_name:
            effective_style = style_name
        else:
            effective_style = config.get("style", self.original_style)

        _apply_style(app, sheet=sheet, style=effective_style, palette=palette)
        apply_tooltip_style_to_app(app)

    def _get_file_stylesheet(self, qt_path: str, app: QApplication) -> str:
        f = QFile(qt_path)
        if not f.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            return ""
        try:
            return QTextStream(f).readAll()
        finally:
            f.close()

    @staticmethod
    def _get_luminance(color: QColor) -> float:
        r, g, b = color.redF(), color.greenF(), color.blueF()
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    @staticmethod
    def _get_contrast_ratio(c1: QColor, c2: QColor) -> float:
        l1 = ThemeManager._get_luminance(c1)
        l2 = ThemeManager._get_luminance(c2)
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

    def _ensure_contrast(self, text_color: QColor, bg_color: QColor, min_ratio: float = 4.5) -> QColor:
        if self._get_contrast_ratio(text_color, bg_color) >= min_ratio:
            return text_color
        bg_lum = self._get_luminance(bg_color)
        text_lum = self._get_luminance(text_color)
        if bg_lum < 0.5:
            target_lum = max((min_ratio * (bg_lum + 0.05)) - 0.05, bg_lum + 0.3)
        else:
            target_lum = min(((bg_lum + 0.05) / min_ratio) - 0.05, bg_lum - 0.3)
        target_lum = max(0.05, min(0.95, target_lum))
        result = QColor(text_color)
        h, s, v, a = result.getHsv()
        if h is not None and s is not None and v is not None:
            current_lum = self._get_luminance(result)
            if current_lum > 0 and abs(target_lum - current_lum) > 0.01:
                v_adjustment = int(255 * (target_lum - current_lum) * 2)
                new_v = max(10, min(245, v + v_adjustment))
                result.setHsv(h, s, new_v, a)
        return result

    def adjust_color(
        self,
        color: Any,
        lightness: int = 100,
        saturation: int = 100,
        hue_shift: int = 0,
    ) -> QColor:
        qcolor = QColor(color) if isinstance(color, QColor) else QColor(color)
        h, s, v, _ = qcolor.getHsv()
        if h is None or s is None or v is None:
            return qcolor
        s = max(0, min(255, s * saturation // 100))
        v = max(0, min(255, v * lightness // 100))
        h = (h + hue_shift) % 360
        qcolor.setHsv(h, s, v)
        return qcolor

    def create_palette(
        self,
        primary: QColor | Qt.GlobalColor | str | int,
        secondary: QColor | Qt.GlobalColor | str | int,
        text: QColor | Qt.GlobalColor | str | int,
        tooltip_base: QColor | Qt.GlobalColor | str | int,
        highlight: QColor | Qt.GlobalColor | str | int,
        bright_text: QColor | Qt.GlobalColor | str | int,
    ) -> QPalette:
        if not isinstance(primary, QColor):
            primary = QColor(primary)
        if not isinstance(secondary, QColor):
            secondary = QColor(secondary)
        if not isinstance(text, QColor):
            text = QColor(text)
        if not isinstance(tooltip_base, QColor):
            tooltip_base = QColor(tooltip_base)
        if not isinstance(highlight, QColor):
            highlight = QColor(highlight)
        if not isinstance(bright_text, QColor):
            bright_text = QColor(bright_text)

        palette = QPalette()
        hl_lum = self._get_luminance(highlight)
        highlighted_text = bright_text if hl_lum < 0.5 else self.adjust_color(secondary, lightness=20)
        role_colors: dict[QPalette.ColorRole, QColor] = {
            QPalette.ColorRole.Window: secondary,
            QPalette.ColorRole.Dark: self.adjust_color(primary, lightness=80),
            QPalette.ColorRole.Button: primary,
            QPalette.ColorRole.WindowText: text,
            QPalette.ColorRole.Base: primary,
            QPalette.ColorRole.AlternateBase: self.adjust_color(secondary, lightness=115),
            QPalette.ColorRole.ToolTipBase: tooltip_base,
            QPalette.ColorRole.ToolTipText: self._ensure_contrast(text, tooltip_base, min_ratio=4.5),
            QPalette.ColorRole.Text: self._ensure_contrast(text, primary, min_ratio=4.5),
            QPalette.ColorRole.ButtonText: self._ensure_contrast(text, primary, min_ratio=4.5),
            QPalette.ColorRole.BrightText: bright_text,
            QPalette.ColorRole.Link: highlight,
            QPalette.ColorRole.LinkVisited: self.adjust_color(highlight, hue_shift=15, saturation=90),
            QPalette.ColorRole.Highlight: highlight,
            QPalette.ColorRole.HighlightedText: highlighted_text,
            QPalette.ColorRole.Light: self.adjust_color(primary, lightness=150),
            QPalette.ColorRole.Midlight: self.adjust_color(primary, lightness=130),
            QPalette.ColorRole.Mid: self.adjust_color(primary, lightness=100),
            QPalette.ColorRole.Shadow: self.adjust_color(primary, lightness=50),
            QPalette.ColorRole.PlaceholderText: self.adjust_color(text, lightness=65, saturation=80),
        }
        if qtpy.QT5:
            extra = {
                getattr(QPalette.ColorRole, "Background", None): self.adjust_color(primary, lightness=110),
                getattr(QPalette.ColorRole, "Foreground", None): self.adjust_color(text, lightness=95),
            }
            extra = {k: v for k, v in extra.items() if k is not None}
        else:
            extra = {
                QPalette.ColorRole.Window: self.adjust_color(secondary, lightness=110),
                QPalette.ColorRole.WindowText: self.adjust_color(text, lightness=95),
            }
        role_colors.update(extra)
        for role, color in role_colors.items():
            palette.setColor(QPalette.ColorGroup.Normal, role, color)
        for state_key, sat_fac, light_fac in [(QPalette.ColorGroup.Disabled, 80, 60), (QPalette.ColorGroup.Inactive, 90, 80)]:
            for role, base_color in role_colors.items():
                palette.setColor(state_key, role, self.adjust_color(base_color, saturation=sat_fac, lightness=light_fac))
        return palette

    @staticmethod
    def setup_custom_title_bar(
        main_window: QWidget,
        title: str = "",
        icon_filename: str = "",
        font: QFont | None = None,
        hint: list[str] | None = None,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
        *,
        bottom_separator: bool = False,
    ) -> QWidget:
        from qtpy.QtCore import QPoint
        from qtpy.QtGui import QIcon
        from qtpy.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

        class TitleBar(QWidget):
            def __init__(self, parent: QWidget):
                super().__init__(parent)
                layout: QLayout = QHBoxLayout(self)
                self.setLayout(layout)
                layout.setContentsMargins(0, 0, 0, 0)
                self.setAutoFillBackground(True)
                if icon_filename:
                    self._icon = QLabel(self)
                    self._icon.setPixmap(QIcon(icon_filename).pixmap(16, 16))
                elif not parent.windowIcon().isNull():
                    self._icon = QLabel(self)
                    self._icon.setPixmap(parent.windowIcon().pixmap(16, 16))
                else:
                    self._icon = None
                if getattr(self, "_icon", None):
                    layout.addWidget(self._icon)
                self._title = QLabel(title, self)
                self._title.setAlignment(align)
                self._title.setFont(font or QFont("Arial", 12))
                layout.addWidget(self._title)
                app = QApplication.instance()
                palette = app.palette() if app else QPalette()
                hover_color = palette.color(QPalette.ColorRole.Highlight)
                hover_color.setAlpha(30)
                hover_rgba = f"rgba({hover_color.red()}, {hover_color.green()}, {hover_color.blue()}, {hover_color.alpha() / 255.0:.2f})"
                btn_style = f"QPushButton {{ background-color: transparent; border: none; width: 30px; height: 30px; }} QPushButton:hover {{ background-color: {hover_rgba}; }}"
                if "min" in (hint or []):
                    self.min_button = QPushButton("🗕", self)
                    self.min_button.setStyleSheet(btn_style)
                    self.min_button.clicked.connect(parent.showMinimized)
                    layout.addWidget(self.min_button)
                if "max" in (hint or []):
                    self.max_button = QPushButton("🗖", self)
                    self.max_button.setStyleSheet(btn_style)
                    self.max_button.clicked.connect(self.toggle_maximize)
                    layout.addWidget(self.max_button)
                if "close" in (hint or []):
                    self.close_button = QPushButton("✕", self)
                    self.close_button.setStyleSheet(btn_style)
                    self.close_button.clicked.connect(lambda *_: parent.close())
                    layout.addWidget(self.close_button)
                self.start = QPoint(0, 0)
                self.pressing = False

            def mousePressEvent(self, event: QMouseEvent):
                self.start = self.mapToGlobal(event.pos())
                self.pressing = True

            def mouseMoveEvent(self, event: QMouseEvent):
                if self.pressing:
                    end = self.mapToGlobal(event.pos())
                    parent = self.parent()
                    if isinstance(parent, QWidget):
                        parent.setGeometry(parent.x() + (end.x() - self.start.x()), parent.y() + (end.y() - self.start.y()), parent.width(), parent.height())
                    self.start = end

            def mouseReleaseEvent(self, event: QMouseEvent):
                self.pressing = False

            def toggle_maximize(self):
                parent = self.parent()
                if isinstance(parent, QWidget):
                    if parent.isMaximized():
                        parent.showNormal()
                        if hasattr(self, "max_button"):
                            self.max_button.setText("🗖")
                    else:
                        parent.showMaximized()
                        if hasattr(self, "max_button"):
                            self.max_button.setText("🗗")

        main_window.setWindowFlags(main_window.windowFlags() & ~Qt.WindowType.FramelessWindowHint)
        main_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title_bar = TitleBar(main_window)
        layout = QHBoxLayout(main_window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title_bar)
        if bottom_separator:
            sep = QWidget(main_window)
            sep.setFixedHeight(1)
            app = QApplication.instance()
            pal = app.palette() if app and isinstance(app, QApplication) else QPalette()
            sep.setStyleSheet(f"background-color: {pal.color(QPalette.ColorRole.Mid).name()};")
            layout.addWidget(sep)
        return title_bar
