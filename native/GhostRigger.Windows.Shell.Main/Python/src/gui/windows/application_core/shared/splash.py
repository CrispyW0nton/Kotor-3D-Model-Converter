"""Startup splash widgets and theme helpers for the GhostRigger main window."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme import ThemeManager
from src.gui.libtheme.style_tokens import FALLBACK_STYLES, LEGACY_MATRIX_COLORS
from src.gui.qt_lib.windows.progress_toast import QtProgressPanel
from src.gui.windows.application_core.application_core_lib.functions.qt_helpers import _primary_screen_available_geometry
from src.gui.windows.application_core.application_core_lib.functions.splash_theme import (
    C,
    _SPLASH_SURFACE_STYLES,
    _darken_hex,
    _lighten_hex,
    _native_splash_palette_colors,
    _palette_hex,
    _surface_fill,
)

_GUI_DIR = Path(__file__).resolve().parents[3]

BRANDED_SPLASH_COLORS = {
    "splash.background": "#030706",
    "splash.panel": "#07110D",
    "splash.brandBackground": "#020504",
    "splash.progressBackground": "#091711",
    "splash.logBackground": "#010302",
    "splash.border": "#1EA85E",
    "splash.text": "#DDFCEB",
    "splash.secondaryText": "#7FDCA8",
    "splash.accent": "#4DFF92",
    "splash.progressTrack": "#020504",
    "splash.progressFill": "#21E46F",
    "panel.background": "#07110D",
    "panel.backgroundAlt": "#020504",
    "panel.altBackground": "#020504",
    "toolbar.border": "#1EA85E",
    "text.primary": "#DDFCEB",
    "text.secondary": "#7FDCA8",
    "accent.primary": "#4DFF92",
    "input.background": "#010302",
    "success": "#21E46F",
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
    STAGE_ROWS = (
        ("native", "Native runtime audit", ("native", "bootstrap", "runtime", "pre-python")),
        ("diagnostics", "Renderer and hardware scan", ("diagnostic", "renderer", "hardware")),
        ("resources", "Loading tools and resources", ("resource", "library", "indexing", "game libraries")),
        ("workspace", "Opening workspace", ("workspace", "main window")),
    )

    def __init__(self, app_root: Path, theme=None, *, theme_manager: Optional[ThemeManager] = None):
        super().__init__(None, QtCore.Qt.SplashScreen | QtCore.Qt.FramelessWindowHint)
        self.app_root = Path(app_root)
        self.theme_manager = theme_manager
        self._last_logged_status = ""
        self._stage_index = 0
        self._stage_labels: list[tuple[QtWidgets.QLabel, QtWidgets.QLabel]] = []
        self._stage_colors = {"active": C["accent"], "done": C["accent"], "pending": C["text2"]}
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

        self.brand_panel = QtWidgets.QFrame()
        self.brand_panel.setObjectName("StartupSplashBrand")
        brand_layout = QtWidgets.QVBoxLayout(self.brand_panel)
        brand_layout.setContentsMargins(18, 18, 18, 18)
        brand_layout.setSpacing(10)
        self.logo_label = QtWidgets.QLabel()
        self.logo_label.setObjectName("StartupSplashLogo")
        self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
        self.logo_label.setMinimumSize(220, 220)
        logo = self._load_logo_pixmap("")
        if not logo.isNull():
            self.logo_label.setPixmap(logo.scaled(220, 220, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.product_label = QtWidgets.QLabel("GhostRigger")
        self.product_label.setObjectName("StartupSplashProduct")
        self.product_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.product_label.setWordWrap(True)
        self.subtitle_label = QtWidgets.QLabel("Odyssey Engine Pipeline")
        self.subtitle_label.setObjectName("StartupSplashSubtitle")
        self.subtitle_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.subtitle_label.setWordWrap(True)
        brand_layout.addWidget(self.logo_label)
        root.addWidget(self.brand_panel, 0)

        content = QtWidgets.QFrame()
        content.setObjectName("StartupSplashContent")
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addStretch(1)
        content_layout.addWidget(self.product_label)
        content_layout.addWidget(self.subtitle_label)
        accent_line = QtWidgets.QFrame()
        accent_line.setObjectName("StartupSplashAccentLine")
        accent_line.setFixedHeight(2)
        content_layout.addWidget(accent_line)
        self.header_label = QtWidgets.QLabel("Preparing GhostRigger")
        self.header_label.setObjectName("StartupSplashHeader")
        self.header_label.setWordWrap(True)
        self.stage_list = QtWidgets.QWidget()
        self.stage_list.setObjectName("StartupSplashStages")
        stage_layout = QtWidgets.QVBoxLayout(self.stage_list)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(6)
        for index, (_stage_id, label_text, _keywords) in enumerate(self.STAGE_ROWS):
            stage_row = QtWidgets.QWidget()
            stage_row.setObjectName("StartupSplashStageRow")
            row_layout = QtWidgets.QHBoxLayout(stage_row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            marker = QtWidgets.QLabel(">")
            marker.setObjectName("StartupSplashStageMarker")
            marker.setFixedWidth(18)
            marker.setAlignment(QtCore.Qt.AlignCenter)
            label = QtWidgets.QLabel(label_text)
            label.setObjectName("StartupSplashStageLabel")
            label.setWordWrap(True)
            row_layout.addWidget(marker)
            row_layout.addWidget(label, 1)
            stage_layout.addWidget(stage_row)
            self._stage_labels.append((marker, label))
            self._set_stage_state(index, "active" if index == 0 else "pending")
        self.progress_panel = QtProgressPanel()
        self.progress_panel.setObjectName("StartupSplashProgressPanel")
        self.progress_percent_label = QtWidgets.QLabel("0%")
        self.progress_percent_label.setObjectName("StartupSplashProgressPercent")
        self.progress_percent_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        progress_row = QtWidgets.QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(10)
        progress_row.addWidget(self.progress_panel, 1)
        progress_row.addWidget(self.progress_percent_label, 0)
        self.launch_log_header = QtWidgets.QWidget()
        self.launch_log_header.setObjectName("StartupSplashLogHeader")
        launch_log_header_layout = QtWidgets.QHBoxLayout(self.launch_log_header)
        launch_log_header_layout.setContentsMargins(0, 0, 0, 0)
        launch_log_header_layout.setSpacing(8)
        self.launch_log_label = QtWidgets.QLabel("Launch Log")
        self.launch_log_label.setObjectName("StartupSplashLogTitle")
        self.clear_log_button = QtWidgets.QToolButton()
        self.clear_log_button.setObjectName("StartupSplashLogClear")
        self.clear_log_button.setText("Clear")
        self.clear_log_button.setAutoRaise(True)
        self.clear_log_button.clicked.connect(lambda: self.launch_log.clear())
        launch_log_header_layout.addWidget(self.launch_log_label)
        launch_log_header_layout.addStretch(1)
        launch_log_header_layout.addWidget(self.clear_log_button)
        self.launch_log = QtWidgets.QPlainTextEdit()
        self.launch_log.setObjectName("StartupSplashLog")
        self.launch_log.setReadOnly(True)
        self.launch_log.setUndoRedoEnabled(False)
        self.launch_log.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.launch_log.setMaximumBlockCount(1000)
        self.launch_log.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.copyright_label = QtWidgets.QLabel(self.COPYRIGHT_TEXT)
        self.copyright_label.setObjectName("StartupSplashCopyright")
        self.copyright_label.setWordWrap(True)
        self.copyright_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        brand_layout.addStretch(1)
        brand_layout.addWidget(self.copyright_label)
        content_layout.addWidget(self.header_label)
        content_layout.addWidget(self.stage_list)
        content_layout.addLayout(progress_row)
        content_layout.addWidget(self.launch_log_header)
        content_layout.addWidget(self.launch_log, 1)
        content_layout.addStretch(1)
        root.addWidget(content, 1)

    def apply_ghost_theme(self, theme) -> None:
        style_theme = theme
        use_native_palette = True
        use_branded_palette = True
        if theme is not None:
            use_native_palette = theme.style("splash.useNativePalette", "true").strip().lower() not in {"0", "false", "no", "off"}
            use_branded_palette = theme.style("splash.useBrandedPalette", "true").strip().lower() not in {"0", "false", "no", "off"}
        if theme is not None and theme.is_native() and use_native_palette:
            style_theme = _ThemeColorOverride(theme, _native_splash_palette_colors())
        if theme is not None and use_branded_palette:
            style_theme = _ThemeColorOverride(style_theme, BRANDED_SPLASH_COLORS)
        if theme is None:
            window = C["bg"]
            panel = C["panel"]
            panel_alt = C["panel2"]
            border = C["accent"]
            text = C["text"]
            subtext = C["text2"]
            accent = C["accent"]
            log_bg = C["bg"]
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
            log_bg = style_theme.color("splash.logBackground", style_theme.color("input.background", panel))
            surface_style = theme.style("splash.surfaceStyle", FALLBACK_STYLES["splash.surfaceStyle"]).strip().lower()
            if surface_style not in _SPLASH_SURFACE_STYLES:
                surface_style = "matte"
        window_fill = _surface_fill(window, surface_style)
        panel_fill = _surface_fill(panel, surface_style)
        panel_alt_fill = _surface_fill(panel_alt, surface_style)
        log_fill = _surface_fill(log_bg, "flat")
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
                border-radius: 8px;
            }}
            QFrame#StartupSplashContent {{
                background: {panel_fill};
                border: 0;
            }}
            QLabel#StartupSplashProduct {{
                color: {text};
                font-size: 34pt;
                font-weight: 800;
            }}
            QLabel#StartupSplashSubtitle {{
                color: {accent};
                font-size: 15pt;
                font-weight: 600;
            }}
            QLabel#StartupSplashCopyright {{
                color: {subtext};
            }}
            QFrame#StartupSplashAccentLine {{
                background: {accent};
                border: 0;
            }}
            QLabel#StartupSplashHeader {{
                color: {accent};
                font-size: 16pt;
                font-weight: 700;
            }}
            QLabel#StartupSplashStageMarker {{
                font-size: 13pt;
                font-weight: 800;
            }}
            QLabel#StartupSplashStageLabel {{
                font-size: 10pt;
                font-weight: 600;
            }}
            QLabel#StartupSplashProgressPercent {{
                color: {accent};
                font-size: 14pt;
                font-weight: 800;
                min-width: 46px;
            }}
            QLabel#StartupSplashLogTitle {{
                color: {accent};
                font-size: 9pt;
                font-weight: 700;
                text-transform: uppercase;
            }}
            QToolButton#StartupSplashLogClear {{
                color: {subtext};
                border: 0;
                padding: 2px 6px;
            }}
            QToolButton#StartupSplashLogClear:hover {{
                color: {accent};
            }}
            QPlainTextEdit#StartupSplashLog {{
                background: {log_fill};
                color: {text};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
                border-radius: 8px;
                padding: 7px;
                font-family: Consolas, "Cascadia Mono", "Courier New";
                font-size: 9pt;
                selection-background-color: {accent};
            }}
            """
        )
        self._stage_colors = {
            "active": accent,
            "done": accent,
            "pending": subtext,
        }
        self._update_stage_rows(self._stage_index)
        self.progress_panel.apply_ghost_theme(style_theme, color_prefix="splash", surface_style=surface_style)
        self._apply_splash_content(theme)

    def _apply_splash_content(self, theme) -> None:
        if theme is not None:
            width = theme.metric("splash.width", 860)
            height = theme.metric("splash.height", 440)
            logo_size = theme.metric("splash.logoSize", 250)
            product = theme.style("splash.productText", self.PRODUCT_TEXT).strip() or self.PRODUCT_TEXT
            subtitle = theme.style("splash.subtitleText", self.SUBTITLE_TEXT).strip() or self.SUBTITLE_TEXT
            copyright_text = theme.style("splash.copyrightText", self.COPYRIGHT_TEXT).strip() or self.COPYRIGHT_TEXT
            logo_path = theme.style("splash.logoPath", "").strip()
        else:
            width = 860
            height = 440
            logo_size = 250
            product = self.PRODUCT_TEXT
            subtitle = self.SUBTITLE_TEXT
            copyright_text = self.COPYRIGHT_TEXT
            logo_path = ""
        self.setFixedSize(max(420, int(width)), max(220, int(height)))
        self.brand_panel.setFixedWidth(max(260, min(360, int(width) // 2 - 60)))
        self.product_label.setText(product)
        self.subtitle_label.setText(subtitle)
        self.copyright_label.setText(copyright_text)
        self.logo_label.setMinimumSize(max(160, int(logo_size)), max(160, int(logo_size)))
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
        candidates: list[Path] = []
        if logo_path:
            path = Path(logo_path).expanduser()
            candidates.append(path if path.is_absolute() else self.app_root / path)
        native_repo_root = os.environ.get("GHOSTRIGGER_NATIVE_REPO_ROOT", "").strip()
        if native_repo_root:
            candidates.append(Path(native_repo_root) / "assets" / "icons" / "ghostrigger_1024x1024.png")
        candidates.extend(
            [
                self.app_root / "assets" / "icons" / "ghostrigger_1024x1024.png",
                _GUI_DIR.parents[2] / "assets" / "icons" / "ghostrigger_1024x1024.png",
                _GUI_DIR / "icons" / "logo_24.png",
            ]
        )
        for path in candidates:
            pixmap = QtGui.QPixmap(path.as_posix())
            if not pixmap.isNull():
                return pixmap
        return QtGui.QPixmap()

    def set_status(self, title: str, detail: str, *, value: int = 0, total: int = 0, finished: bool = False) -> None:
        self.header_label.setText(title)
        self._stage_index = self._stage_index_for_status(title, detail, finished)
        self._update_stage_rows(self._stage_index)
        self._set_progress_percent(self._stage_index, value=value, total=total, finished=finished)
        status_line = f"STATUS  {title}: {detail}" if detail else f"STATUS  {title}"
        if status_line != self._last_logged_status:
            self._last_logged_status = status_line
            self.append_log_line(status_line)
        if finished:
            self.progress_panel.set_finished(title, detail)
        elif total > 0:
            self.progress_panel.set_progress(title, detail, value, total)
        else:
            self.progress_panel.set_busy(title, detail)

    def _stage_index_for_status(self, title: str, detail: str, finished: bool) -> int:
        if finished:
            return len(self.STAGE_ROWS) - 1
        haystack = f"{title} {detail}".lower()
        for index, (_stage_id, _label, keywords) in enumerate(self.STAGE_ROWS):
            if any(keyword in haystack for keyword in keywords):
                return max(index, self._stage_index)
        return self._stage_index

    def _update_stage_rows(self, active_index: int) -> None:
        for index in range(len(self._stage_labels)):
            if index < active_index:
                self._set_stage_state(index, "done")
            elif index == active_index:
                self._set_stage_state(index, "active")
            else:
                self._set_stage_state(index, "pending")

    def _set_stage_state(self, index: int, state: str) -> None:
        if index >= len(self._stage_labels):
            return
        marker, label = self._stage_labels[index]
        color = self._stage_colors.get(state, self._stage_colors["pending"])
        marker.setText(">" if state == "active" else ("✓" if state == "done" else "o"))
        marker.setStyleSheet(f"color: {color};")
        label.setStyleSheet(f"color: {color};")

    def _set_progress_percent(self, stage_index: int, *, value: int, total: int, finished: bool) -> None:
        if finished:
            percent = 100
        elif total > 0:
            percent = round(max(0, min(value, total)) * 100 / total)
        else:
            stage_floor = (12, 38, 63, 82)
            percent = stage_floor[min(max(stage_index, 0), len(stage_floor) - 1)]
        self.progress_percent_label.setText(f"{percent}%")

    def append_log_line(self, text: str) -> None:
        line = str(text).rstrip()
        if not line:
            return
        self.launch_log.appendPlainText(line)
        scrollbar = self.launch_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_log_lines(self, text: str) -> None:
        for line in str(text).splitlines():
            self.append_log_line(line)

    def _center_on_screen(self) -> None:
        geometry = _primary_screen_available_geometry()
        if geometry is None:
            return
        self.move(geometry.center() - self.rect().center())
