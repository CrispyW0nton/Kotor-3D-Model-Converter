"""Startup splash widgets and theme helpers for the GhostRigger main window."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme import ThemeManager
from src.gui.libtheme.style_tokens import FALLBACK_STYLES, LEGACY_MATRIX_COLORS
from src.gui.qt_lib.windows.progress_toast import QtProgressPanel
from src.gui.windows.application_core.shared.qt_helpers import _primary_screen_available_geometry

C = dict(LEGACY_MATRIX_COLORS)
_SPLASH_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}
_GUI_DIR = Path(__file__).resolve().parents[3]

def _lighten_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.lighter(int(factor * 100)).name().upper()

def _darken_hex(value: str, factor: float = 1.18) -> str:
    color = QtGui.QColor(value)
    if not color.isValid():
        return value
    return color.darker(int(factor * 100)).name().upper()

def _surface_fill(value: str, style: str) -> str:
    style = style if style in _SPLASH_SURFACE_STYLES else "matte"
    if style == "flat":
        return value
    if style == "bevelled":
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_lighten_hex(value, 1.18)}, stop:1 {_darken_hex(value, 1.05)})"
    if style == "glossy":
        return (
            "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {_lighten_hex(value, 1.35)}, stop:0.48 {_lighten_hex(value, 1.10)}, "
            f"stop:0.50 {value}, stop:1 {_darken_hex(value, 1.18)})"
        )
    return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {value}, stop:1 {_darken_hex(value, 1.06)})"

def _palette_hex(palette: QtGui.QPalette, role: QtGui.QPalette.ColorRole, group: QtGui.QPalette.ColorGroup | None = None) -> str:
    color = palette.color(group, role) if group is not None else palette.color(role)
    return color.name().upper()

def _native_splash_palette_colors() -> dict[str, str]:
    app = QtWidgets.QApplication.instance()
    palette = app.palette() if app is not None else QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    return {
        "splash.background": _palette_hex(palette, role.Window),
        "splash.panel": _palette_hex(palette, role.Button),
        "splash.brandBackground": _palette_hex(palette, role.Base),
        "splash.progressBackground": _palette_hex(palette, role.Base),
        "splash.border": _palette_hex(palette, role.Mid),
        "splash.text": _palette_hex(palette, role.WindowText),
        "splash.secondaryText": _palette_hex(palette, role.Text),
        "splash.accent": _palette_hex(palette, role.Highlight),
        "splash.progressTrack": _palette_hex(palette, role.Base),
        "splash.progressFill": _palette_hex(palette, role.Highlight),
        "window.background": _palette_hex(palette, role.Window),
        "panel.background": _palette_hex(palette, role.Button),
        "panel.backgroundAlt": _palette_hex(palette, role.Base),
        "panel.altBackground": _palette_hex(palette, role.Base),
        "toolbar.border": _palette_hex(palette, role.Mid),
        "viewportToolbar.background": _palette_hex(palette, role.Window),
        "viewportToolbar.border": _palette_hex(palette, role.Mid),
        "text.primary": _palette_hex(palette, role.WindowText),
        "text.secondary": _palette_hex(palette, role.Text),
        "accent.primary": _palette_hex(palette, role.Highlight),
        "input.background": _palette_hex(palette, role.Base),
        "success": _palette_hex(palette, role.Highlight),
    }

class _ThemeColorOverride:
    def __init__(self, theme, colors: dict[str, str]) -> None:
        self._theme = theme
        self._colors = colors

    def color(self, token: str, default: str | None = None) -> str:
        return self._colors.get(token, self._theme.color(token, default))

    def metric(self, token: str, default: int | None = None) -> int:
        return self._theme.metric(token, default)

    def style(self, token: str, default: str | None = None) -> str:
        return self._theme.style(token, default)

    def is_native(self) -> bool:
        return self._theme.is_native()

class QtStartupSplash(QtWidgets.QWidget):
    """Theme-aware startup splash with embedded progress panel."""

    COPYRIGHT_TEXT = "GhostRigger (C) 2026 Shaolin (CrispyWonton). Co-developed by LordVaderCW."
    PRODUCT_TEXT = "GhostRigger"
    SUBTITLE_TEXT = "Odyssey Engine Pipeline"

    def __init__(self, app_root: Path, theme=None, *, theme_manager: Optional[ThemeManager] = None):
        super().__init__(None, QtCore.Qt.SplashScreen | QtCore.Qt.FramelessWindowHint)
        self.app_root = Path(app_root)
        self.theme_manager = theme_manager
        self.setObjectName("StartupSplash")
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self._build()
        if self.theme_manager is not None:
            self.theme_manager.register_theme_aware_widget(self)
            self.theme_manager.themeChanged.connect(self.apply_ghost_theme)
            theme = getattr(self.theme_manager, "current_theme", None) or self.theme_manager.get_theme()
        self.apply_ghost_theme(theme)
        self._center_on_screen()

    def _build(self) -> None:
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        brand_panel = QtWidgets.QFrame()
        brand_panel.setObjectName("StartupSplashBrand")
        brand_layout = QtWidgets.QVBoxLayout(brand_panel)
        brand_layout.setContentsMargins(18, 18, 18, 18)
        brand_layout.setSpacing(10)
        self.logo_label = QtWidgets.QLabel()
        self.logo_label.setObjectName("StartupSplashLogo")
        self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
        logo = QtGui.QPixmap((_GUI_DIR / "icons" / "logo_24.png").as_posix())
        if not logo.isNull():
            self.logo_label.setPixmap(logo.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.product_label = QtWidgets.QLabel("GhostRigger")
        self.product_label.setObjectName("StartupSplashProduct")
        self.product_label.setAlignment(QtCore.Qt.AlignCenter)
        self.product_label.setWordWrap(True)
        self.subtitle_label = QtWidgets.QLabel("Odyssey Engine Pipeline")
        self.subtitle_label.setObjectName("StartupSplashSubtitle")
        self.subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        brand_layout.addStretch(1)
        brand_layout.addWidget(self.logo_label)
        brand_layout.addWidget(self.product_label)
        brand_layout.addWidget(self.subtitle_label)
        brand_layout.addStretch(1)
        root.addWidget(brand_panel, 0)

        content = QtWidgets.QFrame()
        content.setObjectName("StartupSplashContent")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        self.header_label = QtWidgets.QLabel("Preparing GhostRigger")
        self.header_label.setObjectName("StartupSplashHeader")
        self.progress_panel = QtProgressPanel()
        self.progress_panel.setObjectName("StartupSplashProgressPanel")
        self.copyright_label = QtWidgets.QLabel(self.COPYRIGHT_TEXT)
        self.copyright_label.setObjectName("StartupSplashCopyright")
        self.copyright_label.setWordWrap(True)
        content_layout.addWidget(self.header_label)
        content_layout.addWidget(self.progress_panel, 1)
        content_layout.addWidget(self.copyright_label)
        root.addWidget(content, 1)

    def apply_ghost_theme(self, theme) -> None:
        style_theme = theme
        if theme is not None and theme.is_native():
            style_theme = _ThemeColorOverride(theme, _native_splash_palette_colors())
        if theme is None:
            window = C["bg"]
            panel = C["panel"]
            panel_alt = C["panel2"]
            border = C["accent"]
            text = C["text"]
            subtext = C["text2"]
            accent = C["accent"]
            surface_style = "matte"
        else:
            window = style_theme.color("splash.background", style_theme.color("window.background"))
            panel = style_theme.color("splash.panel", style_theme.color("panel.background"))
            panel_alt = style_theme.color(
                "splash.brandBackground",
                style_theme.color("panel.backgroundAlt", style_theme.color("panel.altBackground")),
            )
            border = style_theme.color("splash.border", style_theme.color("toolbar.border", style_theme.color("accent.primary")))
            text = style_theme.color("splash.text", style_theme.color("text.primary"))
            subtext = style_theme.color("splash.secondaryText", style_theme.color("text.secondary"))
            accent = style_theme.color("splash.accent", style_theme.color("accent.primary"))
            surface_style = theme.style("splash.surfaceStyle", FALLBACK_STYLES["splash.surfaceStyle"]).strip().lower()
            if surface_style not in _SPLASH_SURFACE_STYLES:
                surface_style = "matte"
        window_fill = _surface_fill(window, surface_style)
        panel_fill = _surface_fill(panel, surface_style)
        panel_alt_fill = _surface_fill(panel_alt, surface_style)
        border_top = _lighten_hex(border, 1.16)
        border_bottom = _darken_hex(border, 1.18)
        self.setStyleSheet(
            f"""
            QWidget#StartupSplash {{
                background: {window_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QFrame#StartupSplashBrand {{
                background: {panel_alt_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QFrame#StartupSplashContent {{
                background: {panel_fill};
                border: 0;
            }}
            QLabel#StartupSplashProduct {{
                color: {text};
                font-size: 15pt;
                font-weight: 800;
            }}
            QLabel#StartupSplashSubtitle,
            QLabel#StartupSplashCopyright {{
                color: {subtext};
            }}
            QLabel#StartupSplashHeader {{
                color: {accent};
                font-size: 12pt;
                font-weight: 700;
            }}
            """
        )
        self.progress_panel.apply_ghost_theme(style_theme, color_prefix="splash", surface_style=surface_style)
        self._apply_splash_content(theme)

    def _apply_splash_content(self, theme) -> None:
        if theme is not None:
            width = theme.metric("splash.width", 720)
            height = theme.metric("splash.height", 300)
            logo_size = theme.metric("splash.logoSize", 72)
            product = theme.style("splash.productText", self.PRODUCT_TEXT).strip() or self.PRODUCT_TEXT
            subtitle = theme.style("splash.subtitleText", self.SUBTITLE_TEXT).strip() or self.SUBTITLE_TEXT
            copyright_text = theme.style("splash.copyrightText", self.COPYRIGHT_TEXT).strip() or self.COPYRIGHT_TEXT
            logo_path = theme.style("splash.logoPath", "").strip()
        else:
            width = 720
            height = 300
            logo_size = 72
            product = self.PRODUCT_TEXT
            subtitle = self.SUBTITLE_TEXT
            copyright_text = self.COPYRIGHT_TEXT
            logo_path = ""
        self.setFixedSize(max(420, int(width)), max(220, int(height)))
        self.product_label.setText(product)
        self.subtitle_label.setText(subtitle)
        self.copyright_label.setText(copyright_text)
        font_metrics = QtGui.QFontMetrics(self.product_label.font())
        self.product_label.setMinimumWidth(min(max(140, font_metrics.horizontalAdvance(product) + 18), max(160, int(width) // 2)))
        pixmap = self._load_logo_pixmap(logo_path)
        if not pixmap.isNull():
            self.logo_label.setPixmap(
                pixmap.scaled(
                    max(16, int(logo_size)),
                    max(16, int(logo_size)),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
        else:
            self.logo_label.clear()

    def _load_logo_pixmap(self, logo_path: str) -> QtGui.QPixmap:
        path = Path(logo_path).expanduser() if logo_path else (_GUI_DIR / "icons" / "logo_24.png")
        if logo_path and not path.is_absolute():
            path = self.app_root / path
        return QtGui.QPixmap(path.as_posix())

    def set_status(self, title: str, detail: str, *, value: int = 0, total: int = 0, finished: bool = False) -> None:
        self.header_label.setText(title)
        if finished:
            self.progress_panel.set_finished(title, detail)
        elif total > 0:
            self.progress_panel.set_progress(title, detail, value, total)
        else:
            self.progress_panel.set_busy(title, detail)

    def _center_on_screen(self) -> None:
        geometry = _primary_screen_available_geometry()
        if geometry is None:
            return
        self.move(geometry.center() - self.rect().center())
