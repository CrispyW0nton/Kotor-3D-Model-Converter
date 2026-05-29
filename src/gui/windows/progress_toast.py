"""Theme-aware progress panels and viewport toast notifications."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS

C = dict(LEGACY_MATRIX_COLORS)
_SURFACE_STYLES = {"matte", "bevelled", "glossy", "flat"}


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
    style = style if style in _SURFACE_STYLES else "matte"
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


class QtProgressPanel(QtWidgets.QFrame):
    """Reusable themed progress block used by startup splash and toast."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, compact: bool = False):
        super().__init__(parent)
        self._compact = compact
        self.setObjectName("ProgressPanel")
        layout = QtWidgets.QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(3)
        else:
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(6)
        self.title_label = QtWidgets.QLabel()
        self.title_label.setObjectName("ProgressPanelTitle")
        self.detail_label = QtWidgets.QLabel()
        self.detail_label.setObjectName("ProgressPanelDetail")
        self.detail_label.setWordWrap(True)
        if compact:
            self.detail_label.setMaximumHeight(32)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        if compact:
            self.progress.setFixedHeight(5)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.progress)
        self.apply_ghost_theme(None)

    def apply_ghost_theme(self, theme, *, color_prefix: str = "", surface_style: str = "flat") -> None:
        if theme is None:
            panel = C["panel"]
            border = C["accent"]
            text = C["text"]
            subtext = C["text2"]
            bg = C["bg"]
            progress = C["accent"]
        else:
            if color_prefix:
                panel = theme.color(f"{color_prefix}.progressBackground", theme.color("panel.backgroundAlt", theme.color("panel.altBackground")))
                border = theme.color(f"{color_prefix}.border", theme.color("accent.primary"))
                text = theme.color(f"{color_prefix}.text", theme.color("text.primary"))
                subtext = theme.color(f"{color_prefix}.secondaryText", theme.color("text.secondary"))
                bg = theme.color(f"{color_prefix}.progressTrack", theme.color("input.background"))
                progress = theme.color(f"{color_prefix}.progressFill", theme.color("success", theme.color("accent.primary")))
            else:
                panel = theme.color("panel.backgroundAlt", theme.color("panel.altBackground"))
                border = theme.color("accent.primary")
                text = theme.color("text.primary")
                subtext = theme.color("text.secondary")
                bg = theme.color("input.background")
                progress = theme.color("success", theme.color("accent.primary"))
        panel_fill = _surface_fill(panel, surface_style)
        bg_fill = _surface_fill(bg, surface_style)
        border_top = _lighten_hex(border, 1.16)
        border_bottom = _darken_hex(border, 1.18)
        title_font_rule = "font-size: 11px;" if self._compact else ""
        detail_font_rule = "font-size: 10px;" if self._compact else ""
        progress_height = 5 if self._compact else 8
        self.setStyleSheet(
            f"""
            QFrame#ProgressPanel,
            QFrame#StartupSplashProgressPanel {{
                background: {panel_fill};
                border-top: 1px solid {border_top};
                border-left: 1px solid {border_top};
                border-right: 1px solid {border_bottom};
                border-bottom: 1px solid {border_bottom};
            }}
            QLabel#ProgressPanelTitle {{
                color: {text};
                font-weight: 700;
                {title_font_rule}
            }}
            QLabel#ProgressPanelDetail {{
                color: {subtext};
                {detail_font_rule}
            }}
            QProgressBar {{
                background: {bg_fill};
                border: 1px solid {border};
                height: {progress_height}px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {progress};
            }}
            """
        )

    def set_busy(self, title: str, detail: str) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.title_label.setToolTip(title)
        self.detail_label.setToolTip(detail)
        self.progress.setRange(0, 0)

    def set_progress(self, title: str, detail: str, value: int, total: int) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.title_label.setToolTip(title)
        self.detail_label.setToolTip(detail)
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(max(0, min(value, total)))
        else:
            self.progress.setRange(0, 0)

    def set_finished(self, title: str, detail: str) -> None:
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.title_label.setToolTip(title)
        self.detail_label.setToolTip(detail)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)


class QtProgressToast(QtWidgets.QFrame):
    """Small non-modal progress toast anchored to the viewport canvas."""

    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("ProgressToast")
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(280)
        self._close_timer = QtCore.QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.hide)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.progress_panel = QtProgressPanel(self, compact=True)
        layout.addWidget(self.progress_panel)
        parent_theme = getattr(getattr(parent, "theme_manager", None), "current_theme", None)
        if parent_theme is not None:
            self.apply_ghost_theme(parent_theme)

    def apply_ghost_theme(self, theme) -> None:
        self.progress_panel.apply_ghost_theme(theme)

    def apply_native_theme(self) -> None:
        theme = None
        parent = self.parentWidget()
        if parent is not None:
            theme = getattr(getattr(parent, "theme_manager", None), "current_theme", None)
            if theme is None:
                manager = getattr(parent, "theme_manager", None)
                if manager is not None:
                    theme = manager.get_theme()
        self.progress_panel.apply_ghost_theme(theme)

    def show_busy(self, title: str, detail: str):
        self._close_timer.stop()
        self.progress_panel.set_busy(title, detail)
        self._reposition()
        self.show()
        self.raise_()

    def update_progress(self, title: str, detail: str, value: int, total: int):
        self._close_timer.stop()
        self.progress_panel.set_progress(title, detail, value, total)
        self._reposition()
        self.show()
        self.raise_()

    def finish(self, title: str, detail: str, delay_ms: int = 2200):
        self.progress_panel.set_finished(title, detail)
        self._reposition()
        self.show()
        self.raise_()
        self._close_timer.start(delay_ms)

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        margin = 12
        viewport = getattr(parent, "viewport", None)
        canvas = getattr(viewport, "canvas", None)
        target = canvas if canvas is not None and canvas.isVisible() else viewport
        if target is not None and target.isVisible():
            rect = target.rect()
            x = rect.left() + margin
            y = max(rect.top() + margin, rect.bottom() - self.height() - margin + 1)
            point = target.mapToGlobal(QtCore.QPoint(x, y))
        else:
            x = margin
            y = max(margin, parent.height() - self.height() - margin)
            point = parent.mapToGlobal(QtCore.QPoint(x, y))
        self.move(point)
