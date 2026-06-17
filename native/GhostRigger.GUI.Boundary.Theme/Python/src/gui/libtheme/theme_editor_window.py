"""Theme and layout editor for GhostRigger."""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

from PySide6 import QtCore, QtGui, QtWidgets

from .layout_applier import button_mode_to_toolbutton_style
from .layout_manager import LayoutManager
from .layout_model import LayoutDefinition
from .qt_stylesheet_builder import QtStylesheetBuilder
from .style_tokens import (
    FALLBACK_COLORS,
    FALLBACK_FONTS,
    FALLBACK_METRICS,
    FALLBACK_STYLES,
    VALID_BUTTON_MODES,
    VALID_TAB_STYLE_MODES,
)
from .theme_manager import ThemeManager
from .theme_model import Theme, ThemeFont
from .theme_validator import ThemeValidator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_MATRIX_FONT_DIR = Path(__file__).resolve().parents[1] / "fonts" / "AurebeshAF"
_REGISTERED_MATRIX_FONT = False
_PIXEL_TOKEN_HINTS = (
    "width",
    "height",
    "margin",
    "padding",
    "spacing",
    "radius",
    "border",
    "size",
    "row",
    "handle",
)
_MATRIX_BAR_STYLE_VALUES = {"matrix", "png", "gif", "disabled"}
_SPLASH_STYLE_KEYS = (
    "splash.logoPath",
    "splash.productText",
    "splash.subtitleText",
    "splash.copyrightText",
    "splash.surfaceStyle",
)
_SPLASH_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}
_SPLASH_COLOR_KEYS = (
    "splash.background",
    "splash.panel",
    "splash.brandBackground",
    "splash.progressBackground",
    "splash.border",
    "splash.text",
    "splash.secondaryText",
    "splash.accent",
    "splash.progressTrack",
    "splash.progressFill",
)


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


def _live_native_palette_colors() -> dict[str, str]:
    app = QtWidgets.QApplication.instance()
    palette = app.palette() if app is not None else QtGui.QPalette()
    disabled = QtGui.QPalette.ColorGroup.Disabled
    role = QtGui.QPalette.ColorRole
    window = _palette_hex(palette, role.Window)
    base = _palette_hex(palette, role.Base)
    alternate = _palette_hex(palette, role.AlternateBase)
    button = _palette_hex(palette, role.Button)
    text = _palette_hex(palette, role.Text)
    window_text = _palette_hex(palette, role.WindowText)
    button_text = _palette_hex(palette, role.ButtonText)
    mid = _palette_hex(palette, role.Mid)
    dark = _palette_hex(palette, role.Dark)
    light = _palette_hex(palette, role.Light)
    highlight = _palette_hex(palette, role.Highlight)
    highlighted_text = _palette_hex(palette, role.HighlightedText)
    link = _palette_hex(palette, role.Link)
    disabled_button = _palette_hex(palette, role.Button, disabled)
    disabled_text = _palette_hex(palette, role.Text, disabled)
    warning = "#D8A326" if QtGui.QColor(window).lightness() < 128 else "#B88700"
    error = "#F05252" if QtGui.QColor(window).lightness() < 128 else "#C93434"
    success = "#22C55E" if QtGui.QColor(window).lightness() < 128 else "#1B8F45"
    return {
        "window.background": window,
        "window.text": window_text,
        "panel.background": button,
        "panel.backgroundAlt": base,
        "panel.altBackground": base,
        "panel.border": mid,
        "panel.headerBackground": button,
        "panel.headerText": button_text,
        "groupbox.border": mid,
        "groupbox.title": highlight,
        "viewport.background": base,
        "viewport.border": mid,
        "viewport.text": text,
        "viewport.gridMajor": mid,
        "viewport.gridMinor": dark,
        "toolbar.background": window,
        "toolbar.border": mid,
        "viewportToolbar.background": window,
        "viewportToolbar.border": mid,
        "button.background": button,
        "button.hover": light,
        "button.pressed": dark,
        "button.checked": highlight,
        "button.checkedText": highlighted_text,
        "button.text": button_text,
        "button.accentText": highlighted_text,
        "button.disabledBackground": disabled_button,
        "button.disabledText": disabled_text,
        "input.background": base,
        "input.text": text,
        "input.border": mid,
        "input.focusBorder": highlight,
        "spinbox.background": base,
        "spinbox.text": text,
        "spinbox.border": mid,
        "tab.background": window,
        "tab.selectedBackground": base,
        "tab.inactiveBackground": button,
        "tab.text": text,
        "tab.selectedText": highlight,
        "table.background": base,
        "table.text": text,
        "table.headerBackground": button,
        "table.headerText": button_text,
        "table.grid": mid,
        "tree.background": base,
        "tree.text": text,
        "scrollbar.background": window,
        "scrollbar.handle": mid,
        "selection.background": highlight,
        "selection.text": highlighted_text,
        "text.primary": window_text,
        "text.secondary": text,
        "text.disabled": disabled_text,
        "text.gold": warning,
        "accent.primary": highlight,
        "accent.secondary": link,
        "transformBar.background": window,
        "transformBar.border": mid,
        "splash.background": window,
        "splash.panel": button,
        "splash.brandBackground": base,
        "splash.progressBackground": base,
        "splash.border": mid,
        "splash.text": window_text,
        "splash.secondaryText": text,
        "splash.accent": highlight,
        "splash.progressTrack": base,
        "splash.progressFill": highlight,
        "matrixBar.background": window,
        "matrixBar.glyph": highlight,
        "matrixBar.text": highlight,
        "matrixBar.subtext": text,
        "matrixBar.metaText": text,
        "matrixBar.ipcText": link,
        "info": link,
        "warning": warning,
        "error": error,
        "success": success,
    }


def _register_bundled_matrix_font() -> None:
    """Register the packaged Aurebesh font without importing Matrix widgets."""
    global _REGISTERED_MATRIX_FONT
    if _REGISTERED_MATRIX_FONT:
        return
    for filename in (
        "AurebeshAF-CanonTech.otf",
        "AurebeshAF-LegendsTech.otf",
        "AurebeshAF-Canon.otf",
        "AurebeshAF-Legends.otf",
    ):
        path = _MATRIX_FONT_DIR / filename
        if path.exists():
            QtGui.QFontDatabase.addApplicationFont(str(path))
    _REGISTERED_MATRIX_FONT = True


def _metric_unit(token: str) -> str:
    lower = token.lower()
    if lower.endswith(".size") or "fontsize" in lower:
        return "pt" if "font" in lower else "px"
    if any(hint in lower for hint in _PIXEL_TOKEN_HINTS):
        return "px"
    return "px"


class MatrixBarImagePreview(QtWidgets.QLabel):
    cropChanged = QtCore.Signal(float, float, float, float)
    PREVIEW_SIZE = QtCore.QSize(640, 240)

    def __init__(self, text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._source = QtGui.QPixmap()
        self._crop = (0.0, 0.0, 100.0, 100.0)
        self._image_rect = QtCore.QRectF()
        self._drag_start: QtCore.QPointF | None = None
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.setMinimumSize(260, self.PREVIEW_SIZE.height())
        self.setMaximumHeight(self.PREVIEW_SIZE.height())

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(self.PREVIEW_SIZE)

    def minimumSizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(260, self.PREVIEW_SIZE.height())

    def set_source_pixmap(self, pixmap: QtGui.QPixmap) -> None:
        self._source = pixmap
        self.update()

    def set_crop(self, crop: tuple[float, float, float, float]) -> None:
        self._crop = self._normalize_crop(crop)
        self.update()

    def source_pixmap(self) -> QtGui.QPixmap:
        return self._source

    @staticmethod
    def _normalize_crop(crop: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        try:
            x, y, w, h = (float(value) for value in crop)
        except Exception:
            return (0.0, 0.0, 100.0, 100.0)
        x = max(0.0, min(99.0, x))
        y = max(0.0, min(99.0, y))
        w = max(1.0, min(100.0 - x, w))
        h = max(1.0, min(100.0 - y, h))
        return (x, y, w, h)

    def _point_to_percent(self, point: QtCore.QPointF) -> tuple[float, float]:
        if self._image_rect.isNull() or not self._image_rect.isValid():
            return (0.0, 0.0)
        x = (point.x() - self._image_rect.left()) / max(1.0, self._image_rect.width()) * 100.0
        y = (point.y() - self._image_rect.top()) / max(1.0, self._image_rect.height()) * 100.0
        return (max(0.0, min(100.0, x)), max(0.0, min(100.0, y)))

    def _crop_rect(self) -> QtCore.QRectF:
        x, y, w, h = self._crop
        return QtCore.QRectF(
            self._image_rect.left() + self._image_rect.width() * x / 100.0,
            self._image_rect.top() + self._image_rect.height() * y / 100.0,
            self._image_rect.width() * w / 100.0,
            self._image_rect.height() * h / 100.0,
        )

    def _source_crop_rect(self) -> QtCore.QRectF:
        if self._source.isNull():
            return QtCore.QRectF()
        x, y, w, h = self._crop
        width = max(1, self._source.width())
        height = max(1, self._source.height())
        return QtCore.QRectF(
            width * x / 100.0,
            height * y / 100.0,
            max(1.0, width * w / 100.0),
            max(1.0, height * h / 100.0),
        ).intersected(QtCore.QRectF(0, 0, width, height))

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        if self._source.isNull():
            self._image_rect = QtCore.QRectF()
            super().paintEvent(event)
            return
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        scaled = self._source.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        left = (self.width() - scaled.width()) / 2.0
        top = (self.height() - scaled.height()) / 2.0
        self._image_rect = QtCore.QRectF(left, top, scaled.width(), scaled.height())
        painter.drawPixmap(QtCore.QPointF(left, top), scaled)
        selection = self._crop_rect()
        pen = QtGui.QPen(QtGui.QColor(0, 255, 122), 2)
        painter.setPen(pen)
        painter.drawRect(selection)
        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton and not self._source.isNull():
            self._drag_start = QtCore.QPointF(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._drag_start is not None:
            self._update_drag_crop(QtCore.QPointF(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._drag_start is not None:
            self._update_drag_crop(QtCore.QPointF(event.position()))
            self._drag_start = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_drag_crop(self, end: QtCore.QPointF) -> None:
        if self._drag_start is None:
            return
        x1, y1 = self._point_to_percent(self._drag_start)
        x2, y2 = self._point_to_percent(end)
        x = min(x1, x2)
        y = min(y1, y2)
        w = max(1.0, abs(x2 - x1))
        h = max(1.0, abs(y2 - y1))
        self._crop = self._normalize_crop((x, y, w, h))
        self.cropChanged.emit(*self._crop)
        self.update()


class SplashPreviewWidget(QtWidgets.QFrame):
    """Compact preview for the startup splash theme styles."""

    def __init__(self, app_root: Path, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_root = Path(app_root)
        self.setObjectName("SplashPreview")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        self.brand_panel = QtWidgets.QFrame()
        self.brand_panel.setObjectName("SplashPreviewBrand")
        brand_layout = QtWidgets.QVBoxLayout(self.brand_panel)
        brand_layout.setContentsMargins(18, 18, 18, 18)
        brand_layout.setSpacing(10)
        self.logo_label = QtWidgets.QLabel()
        self.logo_label.setObjectName("SplashPreviewLogo")
        self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
        self.product_label = QtWidgets.QLabel()
        self.product_label.setObjectName("SplashPreviewProduct")
        self.product_label.setAlignment(QtCore.Qt.AlignCenter)
        self.product_label.setWordWrap(True)
        self.subtitle_label = QtWidgets.QLabel()
        self.subtitle_label.setObjectName("SplashPreviewSubtitle")
        self.subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        brand_layout.addStretch(1)
        brand_layout.addWidget(self.logo_label)
        brand_layout.addWidget(self.product_label)
        brand_layout.addWidget(self.subtitle_label)
        brand_layout.addStretch(1)
        root.addWidget(self.brand_panel, 0)

        self.content_panel = QtWidgets.QFrame()
        self.content_panel.setObjectName("SplashPreviewContent")
        content_layout = QtWidgets.QVBoxLayout(self.content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        self.header_label = QtWidgets.QLabel("Preparing GhostRigger")
        self.header_label.setObjectName("SplashPreviewHeader")
        self.progress_block = QtWidgets.QFrame()
        self.progress_block.setObjectName("SplashPreviewProgress")
        progress_layout = QtWidgets.QVBoxLayout(self.progress_block)
        progress_layout.setContentsMargins(12, 10, 12, 10)
        progress_layout.setSpacing(6)
        self.progress_title = QtWidgets.QLabel("Theme editor preview")
        self.progress_title.setObjectName("SplashPreviewProgressTitle")
        self.progress_detail = QtWidgets.QLabel("Library scan and theme feedback appear inside the splash.")
        self.progress_detail.setObjectName("SplashPreviewProgressDetail")
        self.progress_detail.setWordWrap(True)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(72)
        self.progress.setTextVisible(False)
        progress_layout.addWidget(self.progress_title)
        progress_layout.addWidget(self.progress_detail)
        progress_layout.addWidget(self.progress)
        self.copyright_label = QtWidgets.QLabel()
        self.copyright_label.setObjectName("SplashPreviewCopyright")
        self.copyright_label.setWordWrap(True)
        content_layout.addWidget(self.header_label)
        content_layout.addWidget(self.progress_block, 1)
        content_layout.addWidget(self.copyright_label)
        root.addWidget(self.content_panel, 1)

    def apply_theme(self, theme: Theme) -> None:
        width = theme.metric("splash.width", FALLBACK_METRICS["splash.width"])
        height = theme.metric("splash.height", FALLBACK_METRICS["splash.height"])
        logo_size = theme.metric("splash.logoSize", FALLBACK_METRICS["splash.logoSize"])
        surface_style = theme.style("splash.surfaceStyle", FALLBACK_STYLES["splash.surfaceStyle"]).strip().lower()
        if surface_style not in _SPLASH_SURFACE_STYLES:
            surface_style = FALLBACK_STYLES["splash.surfaceStyle"]
        self.setMinimumHeight(max(220, min(420, int(height))))
        self.setMaximumHeight(max(240, min(480, int(height))))
        product = theme.style("splash.productText", FALLBACK_STYLES["splash.productText"])
        self.product_label.setText(product)
        self.subtitle_label.setText(theme.style("splash.subtitleText", FALLBACK_STYLES["splash.subtitleText"]))
        self.copyright_label.setText(theme.style("splash.copyrightText", FALLBACK_STYLES["splash.copyrightText"]))
        font_metrics = QtGui.QFontMetrics(self.product_label.font())
        self.brand_panel.setMinimumWidth(min(max(220, font_metrics.horizontalAdvance(product) + 42), max(260, int(width) // 2)))
        pixmap = self._load_logo_pixmap(theme.style("splash.logoPath", ""))
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
        window = theme.color("splash.background", theme.color("window.background"))
        panel = theme.color("splash.panel", theme.color("panel.background"))
        panel_alt = theme.color("splash.brandBackground", theme.color("panel.backgroundAlt", theme.color("panel.altBackground")))
        border = theme.color("splash.border", theme.color("toolbar.border", theme.color("accent.primary")))
        text = theme.color("splash.text", theme.color("text.primary"))
        subtext = theme.color("splash.secondaryText", theme.color("text.secondary"))
        accent = theme.color("splash.accent", theme.color("accent.primary"))
        progress_bg = theme.color("splash.progressTrack", theme.color("input.background"))
        success = theme.color("splash.progressFill", theme.color("success", accent))
        window_fill = _surface_fill(window, surface_style)
        panel_fill = _surface_fill(panel, surface_style)
        panel_alt_fill = _surface_fill(panel_alt, surface_style)
        progress_fill = _surface_fill(progress_bg, surface_style)
        border_top = _lighten_hex(border, 1.28) if surface_style in {"bevelled", "glossy"} else border
        border_bottom = _darken_hex(border, 1.28) if surface_style in {"bevelled", "glossy"} else border
        self.setStyleSheet(
            f"""
            QFrame#SplashPreview {{
                background: {window_fill};
                border: 1px solid {border};
            }}
            QFrame#SplashPreviewBrand {{
                background: {panel_alt_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QFrame#SplashPreviewContent {{
                background: {panel_fill};
                border: 0;
            }}
            QLabel#SplashPreviewProduct {{
                color: {text};
                font-size: 15pt;
                font-weight: 800;
            }}
            QLabel#SplashPreviewSubtitle,
            QLabel#SplashPreviewCopyright,
            QLabel#SplashPreviewProgressDetail {{
                color: {subtext};
            }}
            QLabel#SplashPreviewHeader {{
                color: {accent};
                font-size: 12pt;
                font-weight: 700;
            }}
            QFrame#SplashPreviewProgress {{
                background: {panel_alt_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QLabel#SplashPreviewProgressTitle {{
                color: {text};
                font-weight: 700;
            }}
            QProgressBar {{
                background: {progress_fill};
                border: 1px solid {border};
                height: 12px;
            }}
            QProgressBar::chunk {{
                background: {success};
            }}
            """
        )
        self.setToolTip(f"Splash preview target size: {width} x {height}")

    def _load_logo_pixmap(self, logo_path: str) -> QtGui.QPixmap:
        path = Path(logo_path).expanduser() if logo_path else Path(__file__).resolve().parents[1] / "icons" / "logo_24.png"
        if logo_path and not path.is_absolute():
            path = self.app_root / path
        return QtGui.QPixmap(path.as_posix())


class ThemeEditorWindow(QtWidgets.QMainWindow):
    """Editor with local preview and explicit full-application apply actions."""

    themeApplied = QtCore.Signal(str)

    def __init__(
        self,
        theme_manager: ThemeManager,
        layout_manager: LayoutManager,
        parent: QtWidgets.QWidget | None = None,
        *,
        matrix_bar_settings: dict | None = None,
        matrix_background_enabled: bool = True,
    ) -> None:
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.layout_manager = layout_manager
        self._matrix_bar_fallback = dict(matrix_bar_settings or {})
        self._matrix_background_enabled = bool(matrix_background_enabled)
        self._theme = copy.deepcopy(theme_manager.current_theme or theme_manager.get_theme())
        self._layout = copy.deepcopy(layout_manager.current_layout or layout_manager.get_layout())
        self._dirty = False
        _register_bundled_matrix_font()
        self.setObjectName("ThemeEditorWindow")
        self.setWindowTitle("Theme Editor")
        self.resize(1180, 760)
        self._build()
        self._load_theme(self._theme.id)
        self._load_layout(self._layout.id)
        self._refresh_preview()

    def _build(self) -> None:
        toolbar = QtWidgets.QToolBar("Theme Editor Actions", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, slot in (
            ("Apply Theme", self._apply_theme_to_app),
            ("Apply Layout", self._apply_layout_to_app),
            ("Save", self._save),
            ("Reset Changes", self._reset_changes),
            ("Open Theme XML", self._open_theme_xml),
            ("Open Themes Folder", lambda: self._open_folder(self.theme_manager.user_theme_dir)),
            ("Validate All Themes", self._validate_themes),
            ("Validate All Layouts", self._validate_layouts),
        ):
            action = QtGui.QAction(text, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        self.setCentralWidget(splitter)
        editor_tabs = QtWidgets.QTabWidget()
        splitter.addWidget(editor_tabs)
        splitter.addWidget(self._build_preview_area())
        splitter.setSizes([520, 660])

        editor_tabs.addTab(self._build_theme_page(), "Theme")
        editor_tabs.addTab(self._build_matrix_bar_page(), "Matrix Bar")
        editor_tabs.addTab(self._build_splash_page(), "Splash")
        editor_tabs.addTab(self._build_color_page(), "Colours")
        editor_tabs.addTab(self._build_font_page(), "Fonts")
        editor_tabs.addTab(self._build_metric_page(), "Metrics")
        editor_tabs.addTab(self._build_layout_page(), "Layout")

    def _build_theme_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.theme_combo = QtWidgets.QComboBox()
        for theme in self.theme_manager.available_themes():
            self.theme_combo.addItem(theme.name, theme.id)
        self.theme_combo.currentIndexChanged.connect(lambda _=0: self._load_theme(str(self.theme_combo.currentData() or "default")))
        self.theme_name = QtWidgets.QLineEdit()
        self.theme_id = QtWidgets.QLineEdit()
        self.theme_version = QtWidgets.QLineEdit()
        self.theme_description = QtWidgets.QPlainTextEdit()
        self.theme_description.setMaximumHeight(70)
        for widget in (self.theme_name, self.theme_id, self.theme_version, self.theme_description):
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(self._mark_dirty)
        form.addRow("Select theme", self.theme_combo)
        form.addRow("Theme id", self.theme_id)
        form.addRow("Name", self.theme_name)
        form.addRow("Version", self.theme_version)
        form.addRow("Description", self.theme_description)
        root.addLayout(form)
        buttons = QtWidgets.QHBoxLayout()
        for text, slot in (
            ("Duplicate Theme", self._duplicate_theme),
            ("Create New Theme", self._new_theme),
            ("Rename Theme", self._rename_theme),
            ("Save Theme As", self._save_theme_as),
            ("Reload Theme", self._reload_theme),
            ("Validate Theme", self._validate_theme),
        ):
            button = QtWidgets.QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        root.addLayout(buttons)
        root.addStretch(1)
        return page

    def _build_matrix_bar_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.matrix_bar_enabled = QtWidgets.QCheckBox("Enable Matrix bar")
        self.matrix_bar_enabled.toggled.connect(self._set_matrix_bar_enabled)
        self.matrix_bar_style = QtWidgets.QComboBox()
        for label, value in (
            ("Theme matrix", "matrix"),
            ("PNG image", "png"),
            ("Animated GIF", "gif"),
            ("Disabled", "disabled"),
        ):
            self.matrix_bar_style.addItem(label, value)
        self.matrix_bar_style.currentIndexChanged.connect(
            lambda _=0: self._set_matrix_bar_style(str(self.matrix_bar_style.currentData() or "matrix"))
        )
        self.matrix_bar_glyphs = QtWidgets.QLineEdit()
        self.matrix_bar_glyphs.setPlaceholderText("Optional custom glyph alphabet")
        self.matrix_bar_glyphs.textEdited.connect(lambda value: self._set_matrix_bar_text_style("matrixBar.glyphs", value))
        self.matrix_bar_font = QtWidgets.QLineEdit()
        self.matrix_bar_font.setPlaceholderText("Blank uses the theme's matrix font role")
        self.matrix_bar_font.textEdited.connect(lambda value: self._set_matrix_bar_text_style("matrixBar.fontFamily", value))
        self.matrix_bar_image = QtWidgets.QLineEdit()
        self.matrix_bar_image.textEdited.connect(lambda value: self._set_matrix_bar_text_style("matrixBar.imagePath", value))
        image_row = QtWidgets.QHBoxLayout()
        image_row.addWidget(self.matrix_bar_image, 1)
        image_browse = QtWidgets.QPushButton("Browse")
        image_browse.clicked.connect(self._browse_matrix_bar_image)
        image_row.addWidget(image_browse)
        crop_row = QtWidgets.QHBoxLayout()
        self.matrix_bar_crop_spins: dict[str, QtWidgets.QDoubleSpinBox] = {}
        for label, key in (("X", "matrixBar.cropX"), ("Y", "matrixBar.cropY"), ("W", "matrixBar.cropW"), ("H", "matrixBar.cropH")):
            crop_row.addWidget(QtWidgets.QLabel(label))
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(1)
            spin.setSuffix("%")
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value, style_key=key: self._set_matrix_bar_text_style(style_key, f"{float(value):.1f}"))
            self.matrix_bar_crop_spins[key] = spin
            crop_row.addWidget(spin)
        form.addRow("", self.matrix_bar_enabled)
        form.addRow("Matrix Bar Style", self.matrix_bar_style)
        form.addRow("Matrix Glyphs", self.matrix_bar_glyphs)
        form.addRow("Matrix Font", self.matrix_bar_font)
        form.addRow("Matrix Image/GIF", image_row)
        form.addRow("Image Crop", crop_row)
        root.addLayout(form)
        self.matrix_bar_preview = MatrixBarImagePreview("GHOSTRIGGER // Odyssey Engine Pipeline")
        self.matrix_bar_preview.setObjectName("MatrixBarPreview")
        self.matrix_bar_preview.setAlignment(QtCore.Qt.AlignCenter)
        self._matrix_bar_preview_movie: QtGui.QMovie | None = None
        self.matrix_bar_preview.cropChanged.connect(self._set_matrix_bar_crop_from_preview)
        root.addWidget(self.matrix_bar_preview)
        root.addStretch(1)
        return page

    def _build_splash_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        self.splash_product = QtWidgets.QLineEdit()
        self.splash_product.textEdited.connect(lambda value: self._set_splash_style("splash.productText", value))
        self.splash_subtitle = QtWidgets.QLineEdit()
        self.splash_subtitle.textEdited.connect(lambda value: self._set_splash_style("splash.subtitleText", value))
        self.splash_copyright = QtWidgets.QPlainTextEdit()
        self.splash_copyright.setMaximumHeight(70)
        self.splash_copyright.textChanged.connect(
            lambda: self._set_splash_style("splash.copyrightText", self.splash_copyright.toPlainText())
        )
        self.splash_logo = QtWidgets.QLineEdit()
        self.splash_logo.textEdited.connect(lambda value: self._set_splash_style("splash.logoPath", value))
        logo_row = QtWidgets.QHBoxLayout()
        logo_row.addWidget(self.splash_logo, 1)
        logo_browse = QtWidgets.QPushButton("Browse")
        logo_browse.clicked.connect(self._browse_splash_logo)
        logo_row.addWidget(logo_browse)
        logo_reset = QtWidgets.QPushButton("Use Packaged")
        logo_reset.clicked.connect(self._reset_splash_logo)
        logo_row.addWidget(logo_reset)
        self.splash_surface_style = QtWidgets.QComboBox()
        for label, value in (("Matte", "matte"), ("Bevelled", "bevelled"), ("Glossy", "glossy"), ("Flat", "flat")):
            self.splash_surface_style.addItem(label, value)
        self.splash_surface_style.currentIndexChanged.connect(
            lambda _=0: self._set_splash_style("splash.surfaceStyle", str(self.splash_surface_style.currentData() or "matte"))
        )
        self.splash_metric_spins: dict[str, QtWidgets.QSpinBox] = {}
        size_row = QtWidgets.QHBoxLayout()
        for label, key, minimum, maximum in (
            ("W", "splash.width", 420, 1800),
            ("H", "splash.height", 220, 900),
            ("Logo", "splash.logoSize", 16, 360),
        ):
            size_row.addWidget(QtWidgets.QLabel(label))
            spin = QtWidgets.QSpinBox()
            spin.setRange(minimum, maximum)
            spin.setSuffix(" px")
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value, metric_key=key: self._set_splash_metric(metric_key, int(value)))
            self.splash_metric_spins[key] = spin
            size_row.addWidget(spin)
        form.addRow("Product", self.splash_product)
        form.addRow("Subtitle", self.splash_subtitle)
        form.addRow("Copyright", self.splash_copyright)
        form.addRow("Logo image", logo_row)
        form.addRow("Surface style", self.splash_surface_style)
        form.addRow("Splash size", size_row)
        root.addLayout(form)
        colour_group = QtWidgets.QGroupBox("Splash Colours")
        colour_grid = QtWidgets.QGridLayout(colour_group)
        colour_grid.setColumnStretch(1, 1)
        self.splash_color_edits: dict[str, QtWidgets.QLineEdit] = {}
        for row, token in enumerate(_SPLASH_COLOR_KEYS):
            colour_grid.addWidget(QtWidgets.QLabel(token), row, 0)
            edit = QtWidgets.QLineEdit()
            edit.setMaxLength(9)
            edit.textEdited.connect(lambda value, colour_token=token: self._set_splash_color(colour_token, value))
            self.splash_color_edits[token] = edit
            colour_grid.addWidget(edit, row, 1)
            picker = QtWidgets.QPushButton("Pick")
            picker.clicked.connect(lambda _checked=False, colour_token=token: self._pick_splash_color(colour_token))
            colour_grid.addWidget(picker, row, 2)
            reset = QtWidgets.QPushButton("Reset")
            reset.clicked.connect(lambda _checked=False, colour_token=token: self._reset_splash_color(colour_token))
            colour_grid.addWidget(reset, row, 3)
        root.addWidget(colour_group)
        self.splash_preview = SplashPreviewWidget(self.theme_manager.app_root)
        root.addWidget(self.splash_preview)
        root.addStretch(1)
        return page

    def _build_color_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        self.color_filter = QtWidgets.QLineEdit()
        self.color_filter.setPlaceholderText("Search colour tokens")
        self.color_filter.textChanged.connect(self._populate_color_tokens)
        root.addWidget(self.color_filter)
        self.color_list = QtWidgets.QTreeWidget()
        self.color_list.setHeaderLabels(["Token", "Colour", "Value"])
        self.color_list.setRootIsDecorated(False)
        self.color_list.setUniformRowHeights(True)
        self.color_list.header().setStretchLastSection(False)
        self.color_list.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.color_list.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.color_list.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.color_list.itemSelectionChanged.connect(self._select_color_token)
        root.addWidget(self.color_list, 1)
        form = QtWidgets.QFormLayout()
        self.color_token_name = QtWidgets.QLineEdit()
        self.color_token_name.setReadOnly(True)
        self.color_value = QtWidgets.QLineEdit()
        self.color_value.textEdited.connect(self._set_color_from_text)
        picker = QtWidgets.QPushButton("Colour Picker")
        picker.clicked.connect(self._pick_color)
        reset = QtWidgets.QPushButton("Reset Token")
        reset.clicked.connect(self._reset_color)
        form.addRow("Token name", self.color_token_name)
        form.addRow("Hex colour", self.color_value)
        form.addRow("", picker)
        form.addRow("", reset)
        root.addLayout(form)
        return page

    def _build_font_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.font_role = QtWidgets.QComboBox()
        self.font_role.currentTextChanged.connect(self._select_font_role)
        self.font_family = QtWidgets.QFontComboBox()
        self.font_family.currentFontChanged.connect(lambda font: self._set_font_field("family", font.family()))
        self.font_size = QtWidgets.QSpinBox()
        self.font_size.setRange(6, 36)
        self.font_size.valueChanged.connect(lambda value: self._set_font_field("size", int(value)))
        self.font_weight = QtWidgets.QComboBox()
        self.font_weight.addItems(["normal", "bold"])
        self.font_weight.currentTextChanged.connect(lambda value: self._set_font_field("weight", value))
        self.font_preview = QtWidgets.QLabel("Aa GhostRigger 0123456789")
        form.addRow("Font role", self.font_role)
        form.addRow("Family", self.font_family)
        form.addRow("Size", self.font_size)
        form.addRow("Weight", self.font_weight)
        form.addRow("Preview", self.font_preview)
        return page

    def _build_metric_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        self.metric_filter = QtWidgets.QLineEdit()
        self.metric_filter.setPlaceholderText("Search metric tokens")
        self.metric_filter.textChanged.connect(self._populate_metric_tokens)
        root.addWidget(self.metric_filter)
        style_row = QtWidgets.QFormLayout()
        self.tab_style_mode_combo = QtWidgets.QComboBox()
        for mode in ("standard", "flat", "beveled"):
            if mode in VALID_TAB_STYLE_MODES:
                self.tab_style_mode_combo.addItem(mode.title(), mode)
        self.tab_style_mode_combo.currentIndexChanged.connect(
            lambda _=0: self._set_tab_style_mode(str(self.tab_style_mode_combo.currentData() or "standard"))
        )
        style_row.addRow("Tab style mode", self.tab_style_mode_combo)
        root.addLayout(style_row)
        self.metric_table = QtWidgets.QTableWidget(0, 2)
        self.metric_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._configure_metric_table(self.metric_table, first_column_width=270)
        root.addWidget(self.metric_table)
        return page

    def _build_layout_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self.layout_combo = QtWidgets.QComboBox()
        for layout in self.layout_manager.available_layouts():
            self.layout_combo.addItem(layout.name, layout.id)
        self.layout_combo.currentIndexChanged.connect(lambda _=0: self._load_layout(str(self.layout_combo.currentData() or "default")))
        self.button_mode = QtWidgets.QComboBox()
        for mode in sorted(VALID_BUTTON_MODES):
            self.button_mode.addItem(mode, mode)
        self.button_mode.currentTextChanged.connect(self._set_layout_button_mode)
        form.addRow("Select layout", self.layout_combo)
        form.addRow("Button mode preview", self.button_mode)
        root.addLayout(form)
        self.layout_metric_table = QtWidgets.QTableWidget(0, 2)
        self.layout_metric_table.setHorizontalHeaderLabels(["Layout metric", "Value"])
        self._configure_metric_table(self.layout_metric_table, first_column_width=285)
        root.addWidget(self.layout_metric_table, 1)
        buttons = QtWidgets.QHBoxLayout()
        validate = QtWidgets.QPushButton("Validate Layout")
        validate.clicked.connect(self._validate_layout)
        save_as = QtWidgets.QPushButton("Save Layout As")
        save_as.clicked.connect(self._save_layout_as)
        buttons.addWidget(validate)
        buttons.addWidget(save_as)
        buttons.addStretch(1)
        root.addLayout(buttons)
        return page

    def _configure_metric_table(self, table: QtWidgets.QTableWidget, *, first_column_width: int) -> None:
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setShowGrid(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setMinimumSectionSize(120)
        table.setColumnWidth(0, first_column_width)

    def _metric_name_cell(self, token: str) -> QtWidgets.QWidget:
        label = QtWidgets.QLabel(token)
        label.setObjectName("MetricTokenLabel")
        label.setToolTip(token)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        label.setContentsMargins(8, 0, 8, 0)
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label, 1)
        return wrapper

    def _metric_value_cell(
        self,
        token: str,
        value: int,
        *,
        changed,
        minimum: int = 0,
        maximum: int = 5000,
    ) -> QtWidgets.QWidget:
        spin = QtWidgets.QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(int(value))
        spin.setAccelerated(True)
        spin.setKeyboardTracking(False)
        spin.setSuffix(f" {_metric_unit(token)}")
        spin.setProperty("metricToken", token)
        spin.valueChanged.connect(lambda number, key=token: changed(key, int(number)))
        wrapper = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(wrapper)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(spin, 0)
        layout.addStretch(1)
        return wrapper

    def _build_preview_area(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("ThemeEditorPreview")
        root = QtWidgets.QVBoxLayout(panel)
        self.preview_toolbar = QtWidgets.QToolBar("Preview Toolbar")
        for text in ("Open", "Save", "Build", "Export"):
            action = QtGui.QAction(text, self.preview_toolbar)
            self.preview_toolbar.addAction(action)
        root.addWidget(self.preview_toolbar)
        row = QtWidgets.QHBoxLayout()
        sample = QtWidgets.QPushButton("Sample Button")
        checked = QtWidgets.QPushButton("Checked")
        checked.setCheckable(True)
        checked.setChecked(True)
        disabled = QtWidgets.QPushButton("Disabled")
        disabled.setEnabled(False)
        for button in (sample, checked, disabled):
            row.addWidget(button)
        root.addLayout(row)
        self.preview_line = QtWidgets.QLineEdit("Sample line edit")
        self.preview_combo = QtWidgets.QComboBox()
        self.preview_combo.addItems(["Default", "Compact", "Wide"])
        self.preview_spin = QtWidgets.QSpinBox()
        self.preview_check = QtWidgets.QCheckBox("Sample checkbox")
        form = QtWidgets.QFormLayout()
        form.addRow("Line edit", self.preview_line)
        form.addRow("Combo box", self.preview_combo)
        form.addRow("Spin box", self.preview_spin)
        form.addRow("", self.preview_check)
        group = QtWidgets.QGroupBox("Sample Group")
        group.setLayout(form)
        root.addWidget(group)
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(QtWidgets.QLabel("Selected tab content"), "Selected")
        tabs.addTab(QtWidgets.QLabel("Inactive tab content"), "Inactive")
        root.addWidget(tabs)
        self.preview_table = QtWidgets.QTableWidget(3, 3)
        self.preview_table.setHorizontalHeaderLabels(["Token", "State", "Value"])
        self.preview_table.setItem(0, 0, QtWidgets.QTableWidgetItem("button.background"))
        self.preview_table.setItem(1, 0, QtWidgets.QTableWidgetItem("input.text"))
        self.preview_table.setItem(2, 0, QtWidgets.QTableWidgetItem("selection.background"))
        root.addWidget(self.preview_table)
        self.preview_tree = QtWidgets.QTreeWidget()
        self.preview_tree.setHeaderLabels(["Tree", "Status"])
        QtWidgets.QTreeWidgetItem(self.preview_tree, ["Panel", "Ready"])
        root.addWidget(self.preview_tree)
        status_row = QtWidgets.QHBoxLayout()
        for text, token in (("Info", "info"), ("Warning", "warning"), ("Error", "error"), ("Success", "success")):
            label = QtWidgets.QLabel(text)
            label.setProperty("_preview_token", token)
            status_row.addWidget(label)
        root.addLayout(status_row)
        self.viewport_swatch = QtWidgets.QLabel("Viewport / transform bar preview")
        self.viewport_swatch.setAlignment(QtCore.Qt.AlignCenter)
        self.viewport_swatch.setMinimumHeight(72)
        root.addWidget(self.viewport_swatch)
        return panel

    def _load_theme(self, theme_id: str) -> None:
        theme = self.theme_manager.get_theme(theme_id)
        self._theme = copy.deepcopy(theme)
        self._apply_live_native_palette()
        self.theme_id.setText(self._theme.id)
        self.theme_name.setText(self._theme.name)
        self.theme_version.setText(self._theme.version)
        self.theme_description.setPlainText(self._theme.description)
        self._populate_color_tokens()
        self._populate_fonts()
        self._populate_metric_tokens()
        self._populate_matrix_bar_controls()
        self._populate_splash_controls()
        self._populate_style_controls()
        self._dirty = False
        self._refresh_preview()

    def _load_layout(self, layout_id: str) -> None:
        self._layout = copy.deepcopy(self.layout_manager.get_layout(layout_id))
        self.button_mode.setCurrentText(self._layout.toolbar("main").button_mode)
        self._populate_layout_metrics()
        self._refresh_preview()

    def _populate_color_tokens(self) -> None:
        text = self.color_filter.text().strip().lower() if hasattr(self, "color_filter") else ""
        self.color_list.clear()
        for token, value in sorted(self._theme.colors.items()):
            if text and text not in token.lower():
                continue
            item = QtWidgets.QTreeWidgetItem(self.color_list, [token, "", value])
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            item.setBackground(1, QtGui.QColor(value))
            item.setToolTip(1, value)

    def _select_color_token(self) -> None:
        item = self.color_list.currentItem()
        if item is None:
            return
        self.color_token_name.setText(item.text(0))
        self.color_value.setText(item.text(2))

    def _set_color_from_text(self, value: str) -> None:
        token = self.color_token_name.text().strip()
        value = value.strip()
        if not token or not _HEX_RE.match(value):
            return
        self._theme.colors[token] = value.upper()
        item = self.color_list.currentItem()
        if item is not None:
            item.setText(2, value.upper())
            item.setBackground(1, QtGui.QColor(value.upper()))
            item.setToolTip(1, value.upper())
        self._mark_dirty()
        self._refresh_preview()

    def _pick_color(self) -> None:
        current = QtGui.QColor(self.color_value.text())
        picked = QtWidgets.QColorDialog.getColor(current, self, "Select colour")
        if picked.isValid():
            self.color_value.setText(picked.name().upper())
            self._set_color_from_text(picked.name().upper())

    def _reset_color(self) -> None:
        token = self.color_token_name.text().strip()
        if token in FALLBACK_COLORS:
            self.color_value.setText(FALLBACK_COLORS[token])
            self._set_color_from_text(FALLBACK_COLORS[token])

    def _populate_fonts(self) -> None:
        self.font_role.blockSignals(True)
        self.font_role.clear()
        for role in sorted(set(FALLBACK_FONTS) | set(self._theme.fonts)):
            self.font_role.addItem(role)
        self.font_role.blockSignals(False)
        self._select_font_role(self.font_role.currentText())

    def _select_font_role(self, role: str) -> None:
        if not role:
            return
        font = self._theme.font(role)
        self.font_family.blockSignals(True)
        self.font_size.blockSignals(True)
        self.font_weight.blockSignals(True)
        self.font_family.setCurrentFont(QtGui.QFont(font.family))
        self.font_size.setValue(font.size)
        self.font_weight.setCurrentText(font.weight)
        self.font_family.blockSignals(False)
        self.font_size.blockSignals(False)
        self.font_weight.blockSignals(False)
        self.font_preview.setFont(QtGui.QFont(font.family, font.size, 700 if font.weight == "bold" else 400))

    def _set_font_field(self, field: str, value: object) -> None:
        role = self.font_role.currentText()
        if not role:
            return
        font = copy.deepcopy(self._theme.font(role))
        if field == "size":
            font.size = int(value)
        elif field == "family":
            font.family = str(value)
        elif field == "weight":
            font.weight = str(value)
        self._theme.fonts[role] = ThemeFont(role=role, family=font.family, size=font.size, weight=font.weight)
        self._select_font_role(role)
        self._mark_dirty()
        self._refresh_preview()

    def _populate_metric_tokens(self) -> None:
        text = self.metric_filter.text().strip().lower() if hasattr(self, "metric_filter") else ""
        rows = [(k, v) for k, v in sorted(self._theme.metrics.items()) if not text or text in k.lower()]
        self.metric_table.setUpdatesEnabled(False)
        self.metric_table.setRowCount(len(rows))
        for row, (token, value) in enumerate(rows):
            self.metric_table.setCellWidget(row, 0, self._metric_name_cell(token))
            self.metric_table.setCellWidget(
                row,
                1,
                self._metric_value_cell(token, int(value), changed=self._metric_spin_changed),
            )
        self.metric_table.setUpdatesEnabled(True)

    def _populate_style_controls(self) -> None:
        if not hasattr(self, "tab_style_mode_combo"):
            return
        self.tab_style_mode_combo.blockSignals(True)
        mode = self._theme.styles.get("tab.mode", FALLBACK_STYLES["tab.mode"])
        index = self.tab_style_mode_combo.findData(mode)
        self.tab_style_mode_combo.setCurrentIndex(max(index, 0))
        self.tab_style_mode_combo.blockSignals(False)

    def _matrix_bar_style_value(self, key: str, default: str = "") -> str:
        value = self._theme.styles.get(key)
        if value is not None:
            return str(value)
        fallback_key = {
            "matrixBar.style": "style",
            "matrixBar.glyphs": "glyphs",
            "matrixBar.fontFamily": "font_family",
            "matrixBar.imagePath": "image_path",
        }.get(key, key)
        fallback = self._matrix_bar_fallback.get(fallback_key)
        if key == "matrixBar.style" and not fallback and not self._matrix_background_enabled:
            return "disabled"
        return str(fallback if fallback is not None else FALLBACK_STYLES.get(key, default))

    def _populate_matrix_bar_controls(self) -> None:
        if not hasattr(self, "matrix_bar_style"):
            return
        style = self._matrix_bar_style_value("matrixBar.style", "matrix").strip().lower()
        if style not in _MATRIX_BAR_STYLE_VALUES:
            style = "matrix"
        self.matrix_bar_enabled.blockSignals(True)
        self.matrix_bar_style.blockSignals(True)
        self.matrix_bar_glyphs.blockSignals(True)
        self.matrix_bar_font.blockSignals(True)
        self.matrix_bar_image.blockSignals(True)
        self.matrix_bar_enabled.setChecked(style != "disabled")
        index = self.matrix_bar_style.findData(style)
        self.matrix_bar_style.setCurrentIndex(max(index, 0))
        self.matrix_bar_glyphs.setText(self._matrix_bar_style_value("matrixBar.glyphs"))
        self.matrix_bar_font.setText(self._matrix_bar_style_value("matrixBar.fontFamily"))
        self.matrix_bar_image.setText(self._matrix_bar_style_value("matrixBar.imagePath"))
        for key, default in (
            ("matrixBar.cropX", 0.0),
            ("matrixBar.cropY", 0.0),
            ("matrixBar.cropW", 100.0),
            ("matrixBar.cropH", 100.0),
        ):
            spin = self.matrix_bar_crop_spins.get(key)
            if spin is not None:
                spin.blockSignals(True)
                try:
                    spin.setValue(float(self._matrix_bar_style_value(key, str(default))))
                except ValueError:
                    spin.setValue(default)
                spin.blockSignals(False)
        self.matrix_bar_enabled.blockSignals(False)
        self.matrix_bar_style.blockSignals(False)
        self.matrix_bar_glyphs.blockSignals(False)
        self.matrix_bar_font.blockSignals(False)
        self.matrix_bar_image.blockSignals(False)

    def _set_matrix_bar_enabled(self, enabled: bool) -> None:
        if enabled:
            style = str(self.matrix_bar_style.currentData() or "matrix")
            if style == "disabled":
                style = "matrix"
                index = self.matrix_bar_style.findData(style)
                self.matrix_bar_style.blockSignals(True)
                self.matrix_bar_style.setCurrentIndex(max(index, 0))
                self.matrix_bar_style.blockSignals(False)
        else:
            style = "disabled"
            index = self.matrix_bar_style.findData(style)
            self.matrix_bar_style.blockSignals(True)
            self.matrix_bar_style.setCurrentIndex(max(index, 0))
            self.matrix_bar_style.blockSignals(False)
        self._theme.styles["matrixBar.style"] = style
        self._mark_dirty()
        self._refresh_preview()

    def _set_matrix_bar_style(self, style: str) -> None:
        style = style if style in _MATRIX_BAR_STYLE_VALUES else "matrix"
        self._theme.styles["matrixBar.style"] = style
        self.matrix_bar_enabled.blockSignals(True)
        self.matrix_bar_enabled.setChecked(style != "disabled")
        self.matrix_bar_enabled.blockSignals(False)
        self._mark_dirty()
        self._refresh_preview()

    def _set_matrix_bar_text_style(self, key: str, value: str) -> None:
        self._theme.styles[key] = value.strip()
        self._mark_dirty()
        self._refresh_preview()

    def _matrix_bar_crop(self) -> tuple[float, float, float, float]:
        values = []
        for key, default in (
            ("matrixBar.cropX", 0.0),
            ("matrixBar.cropY", 0.0),
            ("matrixBar.cropW", 100.0),
            ("matrixBar.cropH", 100.0),
        ):
            try:
                values.append(float(self._matrix_bar_style_value(key, str(default))))
            except ValueError:
                values.append(default)
        return MatrixBarImagePreview._normalize_crop(tuple(values))  # type: ignore[arg-type]

    def _set_matrix_bar_crop_from_preview(self, x: float, y: float, w: float, h: float) -> None:
        crop = MatrixBarImagePreview._normalize_crop((x, y, w, h))
        for key, value in (
            ("matrixBar.cropX", crop[0]),
            ("matrixBar.cropY", crop[1]),
            ("matrixBar.cropW", crop[2]),
            ("matrixBar.cropH", crop[3]),
        ):
            self._theme.styles[key] = f"{value:.1f}"
            spin = self.matrix_bar_crop_spins.get(key)
            if spin is not None:
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        if hasattr(self, "matrix_bar_preview"):
            self.matrix_bar_preview.set_crop(crop)
        self._mark_dirty()

    def _browse_matrix_bar_image(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Matrix Bar Image",
            self.matrix_bar_image.text().strip(),
            "Images (*.png *.jpg *.jpeg *.gif);;All files (*.*)",
        )
        if path:
            self.matrix_bar_image.setText(path)
            self._set_matrix_bar_text_style("matrixBar.imagePath", path)

    def _splash_style_value(self, key: str) -> str:
        return str(self._theme.styles.get(key, FALLBACK_STYLES.get(key, "")))

    def _populate_splash_controls(self) -> None:
        if not hasattr(self, "splash_product"):
            return
        self.splash_product.blockSignals(True)
        self.splash_subtitle.blockSignals(True)
        self.splash_copyright.blockSignals(True)
        self.splash_logo.blockSignals(True)
        self.splash_surface_style.blockSignals(True)
        self.splash_product.setText(self._splash_style_value("splash.productText"))
        self.splash_subtitle.setText(self._splash_style_value("splash.subtitleText"))
        self.splash_copyright.setPlainText(self._splash_style_value("splash.copyrightText"))
        self.splash_logo.setText(self._splash_style_value("splash.logoPath"))
        surface_style = self._splash_style_value("splash.surfaceStyle").strip().lower() or "matte"
        index = self.splash_surface_style.findData(surface_style if surface_style in _SPLASH_SURFACE_STYLES else "matte")
        self.splash_surface_style.setCurrentIndex(max(index, 0))
        self.splash_product.blockSignals(False)
        self.splash_subtitle.blockSignals(False)
        self.splash_copyright.blockSignals(False)
        self.splash_logo.blockSignals(False)
        self.splash_surface_style.blockSignals(False)
        for key, spin in getattr(self, "splash_metric_spins", {}).items():
            spin.blockSignals(True)
            spin.setValue(self._theme.metric(key, FALLBACK_METRICS[key]))
            spin.blockSignals(False)
        for key, edit in getattr(self, "splash_color_edits", {}).items():
            value = self._theme.color(key)
            edit.blockSignals(True)
            edit.setText(value)
            edit.setStyleSheet(f"background:{value}; color:{self._contrast_text(value)};")
            edit.blockSignals(False)

    def _set_splash_style(self, key: str, value: str) -> None:
        if key not in _SPLASH_STYLE_KEYS:
            return
        cleaned = value.strip() if key == "splash.logoPath" else value.strip()
        if key == "splash.surfaceStyle":
            cleaned = cleaned.lower()
            if cleaned not in _SPLASH_SURFACE_STYLES:
                cleaned = "matte"
        if cleaned:
            self._theme.styles[key] = cleaned
        else:
            self._theme.styles.pop(key, None)
        self._mark_dirty()
        self._refresh_preview()

    def _set_splash_metric(self, key: str, value: int) -> None:
        if key not in {"splash.width", "splash.height", "splash.logoSize"}:
            return
        self._theme.metrics[key] = max(0, min(5000, int(value)))
        spin = getattr(self, "splash_metric_spins", {}).get(key)
        if spin is not None and spin.value() != self._theme.metrics[key]:
            spin.blockSignals(True)
            spin.setValue(self._theme.metrics[key])
            spin.blockSignals(False)
        self._mark_dirty()
        self._refresh_preview()

    def _set_splash_color(self, key: str, value: str) -> None:
        value = value.strip().upper()
        if key not in _SPLASH_COLOR_KEYS or not _HEX_RE.match(value):
            return
        self._theme.colors[key] = value
        edit = getattr(self, "splash_color_edits", {}).get(key)
        if edit is not None:
            if edit.text() != value:
                edit.blockSignals(True)
                edit.setText(value)
                edit.blockSignals(False)
            edit.setStyleSheet(f"background:{value}; color:{self._contrast_text(value)};")
        self._mark_dirty()
        self._refresh_preview()

    def _pick_splash_color(self, key: str) -> None:
        current = QtGui.QColor(self._theme.color(key))
        picked = QtWidgets.QColorDialog.getColor(current, self, f"Select {key}")
        if picked.isValid():
            value = picked.name().upper()
            edit = self.splash_color_edits.get(key)
            if edit is not None:
                edit.setText(value)
            self._set_splash_color(key, value)

    def _reset_splash_color(self, key: str) -> None:
        if key not in _SPLASH_COLOR_KEYS:
            return
        value = self._derived_splash_color(key).upper()
        self._theme.colors[key] = value
        edit = self.splash_color_edits.get(key)
        if edit is not None:
            edit.setText(value)
            edit.setStyleSheet(f"background:{value}; color:{self._contrast_text(value)};")
        self._mark_dirty()
        self._refresh_preview()

    def _derived_splash_color(self, key: str) -> str:
        if self._theme.is_native():
            palette = QtWidgets.QApplication.palette()
            native = {
                "splash.background": palette.color(QtGui.QPalette.Window).name(),
                "splash.panel": palette.color(QtGui.QPalette.Base).name(),
                "splash.brandBackground": palette.color(QtGui.QPalette.AlternateBase).name(),
                "splash.progressBackground": palette.color(QtGui.QPalette.AlternateBase).name(),
                "splash.border": palette.color(QtGui.QPalette.Mid).name(),
                "splash.text": palette.color(QtGui.QPalette.WindowText).name(),
                "splash.secondaryText": palette.color(QtGui.QPalette.Text).name(),
                "splash.accent": palette.color(QtGui.QPalette.Highlight).name(),
                "splash.progressTrack": palette.color(QtGui.QPalette.Base).name(),
                "splash.progressFill": palette.color(QtGui.QPalette.Highlight).name(),
            }
            return native.get(key, self._theme.color(key))
        derived = {
            "splash.background": self._theme.color("window.background"),
            "splash.panel": self._theme.color("panel.background"),
            "splash.brandBackground": self._theme.color("panel.backgroundAlt", self._theme.color("panel.altBackground")),
            "splash.progressBackground": self._theme.color("panel.backgroundAlt", self._theme.color("panel.altBackground")),
            "splash.border": self._theme.color("toolbar.border", self._theme.color("panel.border")),
            "splash.text": self._theme.color("text.primary"),
            "splash.secondaryText": self._theme.color("text.secondary"),
            "splash.accent": self._theme.color("accent.primary"),
            "splash.progressTrack": self._theme.color("input.background"),
            "splash.progressFill": self._theme.color("success", self._theme.color("accent.primary")),
        }
        return derived.get(key, self._theme.color(key))

    @staticmethod
    def _contrast_text(value: str) -> str:
        color = QtGui.QColor(value)
        if not color.isValid():
            return "#FFFFFF"
        luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255.0
        return "#000000" if luminance > 0.58 else "#FFFFFF"

    def _browse_splash_logo(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Splash Logo",
            self.splash_logo.text().strip(),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)",
        )
        if path:
            self.splash_logo.setText(path)
            self._set_splash_style("splash.logoPath", path)

    def _reset_splash_logo(self) -> None:
        self.splash_logo.clear()
        self._theme.styles.pop("splash.logoPath", None)
        self._mark_dirty()
        self._refresh_preview()

    def _clear_matrix_bar_preview_media(self) -> None:
        movie = getattr(self, "_matrix_bar_preview_movie", None)
        if movie is not None:
            movie.stop()
            self._matrix_bar_preview_movie = None
        self.matrix_bar_preview.clear()
        self.matrix_bar_preview.setMovie(None)

    def _refresh_matrix_bar_preview(self) -> None:
        if not hasattr(self, "matrix_bar_preview"):
            return
        style = self._matrix_bar_style_value("matrixBar.style", "matrix").strip().lower()
        image_path = self._matrix_bar_style_value("matrixBar.imagePath")
        self._clear_matrix_bar_preview_media()
        self.matrix_bar_preview.set_source_pixmap(QtGui.QPixmap())
        self.matrix_bar_preview.set_crop(self._matrix_bar_crop())
        self.matrix_bar_preview.setText("GHOSTRIGGER // Odyssey Engine Pipeline")
        matrix_font = self._matrix_bar_style_value("matrixBar.fontFamily") or self._theme.font("matrix").family
        self.matrix_bar_preview.setStyleSheet(
            f"background:{self._theme.color('matrixBar.background')}; "
            f"color:{self._theme.color('matrixBar.text')}; "
            f"border:1px solid {self._theme.color('toolbar.border')}; "
            f"font-family:{matrix_font};"
        )
        if style in {"png", "image"} and image_path:
            pixmap = QtGui.QPixmap(image_path)
            if not pixmap.isNull():
                self.matrix_bar_preview.set_source_pixmap(pixmap)
                return
        if style == "gif" and image_path:
            movie = QtGui.QMovie(image_path)
            if movie.isValid():
                height = max(1, self.matrix_bar_preview.height())
                width = max(1, self.matrix_bar_preview.width())
                movie.setScaledSize(QtCore.QSize(width, height))
                self.matrix_bar_preview.setMovie(movie)
                self._matrix_bar_preview_movie = movie
                movie.start()
                return
        if style == "disabled":
            self.matrix_bar_preview.setText("Matrix bar disabled")

    def _set_tab_style_mode(self, mode: str) -> None:
        if mode not in VALID_TAB_STYLE_MODES:
            mode = FALLBACK_STYLES["tab.mode"]
        self._theme.styles["tab.mode"] = mode
        self._mark_dirty()
        self._refresh_preview()

    def _metric_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        key_item = self.metric_table.item(item.row(), 0)
        if key_item is None:
            return
        try:
            value = max(0, min(5000, int(item.text())))
        except ValueError:
            return
        self._theme.metrics[key_item.text()] = value
        self._mark_dirty()
        self._refresh_preview()

    def _metric_spin_changed(self, token: str, value: int) -> None:
        self._theme.metrics[token] = max(0, min(5000, int(value)))
        self._mark_dirty()
        self._refresh_preview()

    def _populate_layout_metrics(self) -> None:
        rows = [
            ("window.defaultWidth", self._layout.main_width),
            ("window.defaultHeight", self._layout.main_height),
            ("toolbar.height", self._layout.toolbar("main").height),
            ("toolbar.iconSize", self._layout.toolbar("main").icon_size),
            ("leftPanel.preferredWidth", self._layout.panel("library").preferred_width),
            ("rightPanel.preferredWidth", self._layout.panel("properties").preferred_width),
            ("farRightPanel.preferredWidth", self._layout.panel("meshTools").preferred_width),
            ("bottomPanel.preferredHeight", self._layout.panel("outputLog").preferred_height),
            ("panel.margin", self._layout.spacing_value("margin", FALLBACK_METRICS["panel.margin"])),
            ("panel.spacing", self._layout.spacing_value("panelSpacing", FALLBACK_METRICS["panel.spacing"])),
            ("input.height", self._layout.spacing_value("inputHeight", FALLBACK_METRICS["input.height"])),
            ("tab.height", self._layout.spacing_value("tabHeight", FALLBACK_METRICS["tab.height"])),
            ("tab.width", self._layout.spacing_value("tabWidth", FALLBACK_METRICS["tab.width"])),
            ("tab.padding", self._layout.spacing_value("tabPadding", FALLBACK_METRICS["tab.padding"])),
            ("tab.paddingX", self._layout.spacing_value("tabPaddingX", FALLBACK_METRICS["tab.paddingX"])),
            ("tab.paddingY", self._layout.spacing_value("tabPaddingY", FALLBACK_METRICS["tab.paddingY"])),
            ("tab.margin", self._layout.spacing_value("tabMargin", FALLBACK_METRICS["tab.margin"])),
            ("tab.marginX", self._layout.spacing_value("tabMarginX", FALLBACK_METRICS["tab.marginX"])),
            ("tab.marginY", self._layout.spacing_value("tabMarginY", FALLBACK_METRICS["tab.marginY"])),
            ("table.rowHeight", self._layout.spacing_value("tableRowHeight", FALLBACK_METRICS["table.rowHeight"])),
            ("tree.rowHeight", self._layout.spacing_value("treeRowHeight", FALLBACK_METRICS["tree.rowHeight"])),
            ("splitter.handleWidth", self._layout.spacing_value("splitterHandleWidth", FALLBACK_METRICS["splitter.handleWidth"])),
        ]
        self.layout_metric_table.setUpdatesEnabled(False)
        self.layout_metric_table.setRowCount(len(rows))
        for row, (key, value) in enumerate(rows):
            self.layout_metric_table.setCellWidget(row, 0, self._metric_name_cell(key))
            self.layout_metric_table.setCellWidget(
                row,
                1,
                self._metric_value_cell(key, int(value), changed=self._layout_metric_spin_changed, minimum=0),
            )
        self.layout_metric_table.setUpdatesEnabled(True)

    def _layout_metric_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        key = self.layout_metric_table.item(item.row(), 0).text()
        try:
            value = max(12, min(5000, int(item.text())))
        except ValueError:
            return
        self._set_layout_metric(key, value)
        self._mark_dirty()
        self._refresh_preview()

    def _layout_metric_spin_changed(self, key: str, value: int) -> None:
        self._set_layout_metric(key, max(0, min(5000, int(value))))
        self._mark_dirty()
        self._refresh_preview()

    def _set_layout_metric(self, key: str, value: int) -> None:
        if key == "window.defaultWidth":
            self._layout.main_width = value
        elif key == "window.defaultHeight":
            self._layout.main_height = value
        elif key == "toolbar.height":
            self._layout.toolbar("main").height = value
        elif key == "toolbar.iconSize":
            self._layout.toolbar("main").icon_size = value
        elif key == "leftPanel.preferredWidth":
            self._layout.panel("library").preferred_width = value
        elif key == "rightPanel.preferredWidth":
            self._layout.panel("properties").preferred_width = value
        elif key == "farRightPanel.preferredWidth":
            self._layout.panel("meshTools").preferred_width = value
        elif key == "bottomPanel.preferredHeight":
            self._layout.panel("outputLog").preferred_height = value
        else:
            xml_name = {
                "panel.margin": "margin",
                "panel.spacing": "panelSpacing",
                "input.height": "inputHeight",
                "tab.height": "tabHeight",
                "tab.width": "tabWidth",
                "tab.padding": "tabPadding",
                "tab.paddingX": "tabPaddingX",
                "tab.paddingY": "tabPaddingY",
                "tab.margin": "tabMargin",
                "tab.marginX": "tabMarginX",
                "tab.marginY": "tabMarginY",
                "table.rowHeight": "tableRowHeight",
                "tree.rowHeight": "treeRowHeight",
                "splitter.handleWidth": "splitterHandleWidth",
            }.get(key, key)
            self._layout.spacing[xml_name] = value

    def _set_layout_button_mode(self, mode: str) -> None:
        if mode in VALID_BUTTON_MODES:
            self._layout.toolbar("main").button_mode = mode
            self._mark_dirty()
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        if not hasattr(self, "preview_toolbar"):
            return
        self._theme.id = self.theme_id.text().strip() or self._theme.id
        self._theme.name = self.theme_name.text().strip() or self._theme.name
        self._theme.version = self.theme_version.text().strip() or self._theme.version
        self._theme.description = self.theme_description.toPlainText().strip()
        preview_theme = copy.deepcopy(self._theme)
        if hasattr(self, "tab_style_mode_combo"):
            preview_theme.styles["tab.mode"] = str(self.tab_style_mode_combo.currentData() or FALLBACK_STYLES["tab.mode"])
        for layout_token, metric_token in {
            "tabHeight": "tab.height",
            "tabWidth": "tab.width",
            "tabPadding": "tab.padding",
            "tabPaddingX": "tab.paddingX",
            "tabPaddingY": "tab.paddingY",
            "tabMargin": "tab.margin",
            "tabMarginX": "tab.marginX",
            "tabMarginY": "tab.marginY",
        }.items():
            if layout_token in self._layout.spacing:
                preview_theme.metrics[metric_token] = int(self._layout.spacing[layout_token])
        self.centralWidget().setStyleSheet(QtStylesheetBuilder().build(preview_theme))
        icon_size = self._layout.toolbar("main").icon_size
        self.preview_toolbar.setIconSize(QtCore.QSize(icon_size, icon_size))
        self.preview_toolbar.setToolButtonStyle(button_mode_to_toolbutton_style(self._layout.toolbar("main").button_mode))
        self.preview_toolbar.setMinimumHeight(self._layout.toolbar("main").height)
        self.preview_toolbar.setMaximumHeight(self._layout.toolbar("main").height + 8)
        spacing = self._layout.spacing_value("panelSpacing", 4)
        margin = self._layout.spacing_value("margin", 4)
        for layout in self.centralWidget().findChildren(QtWidgets.QLayout):
            layout.setSpacing(spacing)
            layout.setContentsMargins(margin, margin, margin, margin)
        self.preview_table.verticalHeader().setDefaultSectionSize(self._layout.spacing_value("tableRowHeight", 22))
        for label in self.findChildren(QtWidgets.QLabel):
            token = label.property("_preview_token")
            if token:
                label.setStyleSheet(f"color:{self._theme.color(str(token))}; font-weight:bold;")
        self.viewport_swatch.setStyleSheet(
            f"background:{self._theme.color('viewport.background')}; "
            f"color:{self._theme.color('viewport.text')}; "
            f"border:1px solid {self._theme.color('transformBar.border')};"
        )
        if hasattr(self, "splash_preview"):
            self.splash_preview.apply_theme(preview_theme)
        self._refresh_matrix_bar_preview()

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True

    def _apply_theme_to_app(self) -> None:
        self.theme_manager.themes[self._theme.id] = copy.deepcopy(self._theme)
        self.theme_manager.settings.selected_theme = self._theme.id
        self.theme_manager.settings.theme_mode = "manual"
        self.theme_manager.current_theme = copy.deepcopy(self._theme)
        self.theme_manager.applier.apply_theme(self._theme, self.parentWidget())
        self.themeApplied.emit(self._theme.id)

    def _apply_layout_to_app(self) -> None:
        parent = self.parentWidget()
        self.layout_manager.layouts[self._layout.id] = copy.deepcopy(self._layout)
        self.layout_manager.settings.selected_layout = self._layout.id
        if isinstance(parent, QtWidgets.QMainWindow):
            self.layout_manager.current_layout = copy.deepcopy(self._layout)
            self.layout_manager.applier.apply_layout(self._layout, parent)

    def _duplicate_theme(self) -> None:
        new_id = f"{self._theme.id}_copy"
        self._theme.id = new_id
        self._theme.name = f"{self._theme.name} Copy"
        self.theme_id.setText(new_id)
        self.theme_name.setText(self._theme.name)
        self._mark_dirty()

    def _new_theme(self) -> None:
        self._theme = Theme(
            id="new_theme",
            name="New Theme",
            version="1",
            colors=dict(FALLBACK_COLORS),
            metrics=dict(FALLBACK_METRICS),
            styles=dict(FALLBACK_STYLES),
        )
        self._load_theme_fields()

    def _apply_live_native_palette(self) -> None:
        if self._theme.is_native():
            self._theme.colors.update(_live_native_palette_colors())

    def _rename_theme(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "Rename Theme", "Theme name", text=self.theme_name.text())
        if ok and text.strip():
            self.theme_name.setText(text.strip())
            self._mark_dirty()

    def _load_theme_fields(self) -> None:
        self._apply_live_native_palette()
        self.theme_id.setText(self._theme.id)
        self.theme_name.setText(self._theme.name)
        self.theme_version.setText(self._theme.version)
        self.theme_description.setPlainText(self._theme.description)
        self._populate_color_tokens()
        self._populate_fonts()
        self._populate_metric_tokens()
        self._populate_matrix_bar_controls()
        self._populate_splash_controls()
        self._populate_style_controls()
        self._refresh_preview()

    def _reload_theme(self) -> None:
        self.theme_manager.reload()
        self._load_theme(str(self.theme_combo.currentData() or self._theme.id))

    def _save(self) -> None:
        self._save_theme_to_path(self.theme_manager.user_theme_dir / f"{self._theme.id}.xml")
        self._save_layout_to_path(self.layout_manager.user_layout_dir / f"{self._layout.id}.xml")

    def _save_theme_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Theme As", str(self.theme_manager.user_theme_dir / f"{self._theme.id}.xml"), "Theme XML (*.xml)")
        if path:
            self._save_theme_to_path(Path(path))

    def _save_layout_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Layout As", str(self.layout_manager.user_layout_dir / f"{self._layout.id}.xml"), "Layout XML (*.xml)")
        if path:
            self._save_layout_to_path(Path(path))

    def _save_theme_to_path(self, path: Path) -> None:
        warnings = ThemeValidator().validate_theme(self._theme)
        invalid = [w for w in warnings if "invalid value" in w]
        if invalid:
            QtWidgets.QMessageBox.warning(self, "Theme Validation", "\n".join(invalid[:12]))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        self._theme_xml().write(path, encoding="utf-8", xml_declaration=True)
        self.theme_manager.reload()
        self._dirty = False

    def _save_layout_to_path(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        self._layout_xml().write(path, encoding="utf-8", xml_declaration=True)
        self.layout_manager.reload()
        self._dirty = False

    def _theme_xml(self) -> ET.ElementTree:
        root = ET.Element("theme", {"id": self._theme.id, "name": self._theme.name, "version": self._theme.version})
        metadata = ET.SubElement(root, "metadata")
        ET.SubElement(metadata, "author").text = self._theme.author
        ET.SubElement(metadata, "description").text = self._theme.description
        ET.SubElement(metadata, "mode").text = self._theme.mode
        colors = ET.SubElement(root, "colors")
        for name, value in sorted(self._theme.colors.items()):
            ET.SubElement(colors, "color", {"name": name, "value": value})
        fonts = ET.SubElement(root, "fonts")
        for font in sorted(self._theme.fonts.values(), key=lambda f: f.role):
            ET.SubElement(fonts, "font", {"role": font.role, "family": font.family, "size": str(font.size), "weight": font.weight})
        icons = ET.SubElement(root, "icons")
        ET.SubElement(icons, "provider").text = self._theme.icons.provider
        ET.SubElement(icons, "defaultMode").text = self._theme.icons.default_mode
        for role, size in sorted(self._theme.icons.sizes.items()):
            ET.SubElement(icons, "size", {"role": role, "value": str(size)})
        metrics = ET.SubElement(root, "metrics")
        for name, value in sorted(self._theme.metrics.items()):
            ET.SubElement(metrics, "metric", {"name": name, "value": str(max(0, min(5000, int(value))))})
        styles = ET.SubElement(root, "styles")
        for name, value in sorted({**FALLBACK_STYLES, **self._theme.styles}.items()):
            ET.SubElement(styles, "style", {"name": name, "value": value})
        ET.indent(root)
        return ET.ElementTree(root)

    def _layout_xml(self) -> ET.ElementTree:
        root = ET.Element("layout", {"id": self._layout.id, "name": self._layout.name, "version": self._layout.version})
        ET.SubElement(root, "mainWindow", {"width": str(self._layout.main_width), "height": str(self._layout.main_height), "maximized": str(self._layout.maximized).lower()})
        toolbars = ET.SubElement(root, "toolbars")
        for toolbar in self._layout.toolbars.values():
            ET.SubElement(toolbars, "toolbar", {"id": toolbar.id, "visible": str(toolbar.visible).lower(), "buttonMode": toolbar.button_mode, "iconSize": str(toolbar.icon_size), "height": str(toolbar.height)})
        panels = ET.SubElement(root, "panels")
        for panel in self._layout.panels.values():
            ET.SubElement(panels, "panel", {"id": panel.id, "region": panel.region, "visible": str(panel.visible).lower(), "minWidth": str(panel.min_width), "preferredWidth": str(panel.preferred_width), "minHeight": str(panel.min_height), "preferredHeight": str(panel.preferred_height)})
        viewport = ET.SubElement(root, "viewport")
        ET.SubElement(viewport, "region", {"id": "mainViewport", "minWidth": str(self._layout.viewport.min_width), "preferredWidth": str(self._layout.viewport.preferred_width)})
        ET.SubElement(viewport, "toolbar", {"visible": str(self._layout.viewport.toolbar_visible).lower(), "buttonMode": self._layout.viewport.toolbar_button_mode, "compact": str(self._layout.viewport.toolbar_compact).lower()})
        spacing = ET.SubElement(root, "spacing")
        for name, value in sorted(self._layout.spacing.items()):
            ET.SubElement(spacing, name, {"value": str(max(0, min(5000, int(value))))})
        ET.indent(root)
        return ET.ElementTree(root)

    def _open_theme_xml(self) -> None:
        path = Path(self._theme.source_path) if self._theme.source_path else self.theme_manager.user_theme_dir / f"{self._theme.id}.xml"
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def _validate_theme(self) -> None:
        lines = ThemeValidator().validate_theme(self._theme) or ["Theme is valid."]
        QtWidgets.QMessageBox.information(self, "Theme Validation", "\n".join(lines[:80]))

    def _validate_layout(self) -> None:
        lines = list(self._layout.warnings) or ["Layout is valid."]
        QtWidgets.QMessageBox.information(self, "Layout Validation", "\n".join(lines[:80]))

    def _validate_themes(self) -> None:
        self.theme_manager.reload()
        QtWidgets.QMessageBox.information(self, "Theme Validation", "\n".join((self.theme_manager.diagnostics or ["All themes are valid."])[:80]))

    def _validate_layouts(self) -> None:
        self.layout_manager.reload()
        QtWidgets.QMessageBox.information(self, "Layout Validation", "\n".join((self.layout_manager.diagnostics or ["All layouts are valid."])[:80]))

    def _reset_changes(self) -> None:
        self._load_theme(str(self.theme_combo.currentData() or self.theme_manager.get_theme().id))
        self._load_layout(str(self.layout_combo.currentData() or self.layout_manager.get_layout().id))

    def close_without_prompt(self) -> None:
        self.setProperty("_skipUnsavedPrompt", True)
        self.close()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        skip_prompt = bool(self.property("_skipUnsavedPrompt"))
        spontaneous = True
        try:
            spontaneous = bool(event.spontaneous())
        except Exception:
            spontaneous = True
        if self._dirty and not skip_prompt and spontaneous:
            result = QtWidgets.QMessageBox.question(self, "Theme Editor", "Discard unsaved theme/layout changes?")
            if result != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        super().closeEvent(event)
