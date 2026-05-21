"""Shared Qt theme constants and helpers for the GhostRigger migration."""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from src.gui.libtheme.qt_stylesheet_builder import QtStylesheetBuilder
from src.gui.libtheme.style_tokens import LEGACY_MATRIX_COLORS
from src.gui.libtheme.theme_model import Theme


C = dict(LEGACY_MATRIX_COLORS)

_GUI_DIR = Path(__file__).resolve().parents[1]
_QT_ICON_DIR = (_GUI_DIR / "icons").as_posix()


class QtOverflowScrollArea(QtWidgets.QScrollArea):
    """Scroll area that lets dense tool strips keep their natural width."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        lock_content_width: bool = False,
    ) -> None:
        super().__init__(parent)
        self._lock_content_width = bool(lock_content_width)

    def setWidget(self, widget: QtWidgets.QWidget | None) -> None:  # noqa: N802 - Qt API
        super().setWidget(widget)
        self._sync_content_width()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._sync_content_width()

    def _sync_content_width(self) -> None:
        if not self._lock_content_width:
            return
        widget = self.widget()
        if widget is None:
            return
        locked_width = widget.property("_gr_overflow_min_width") or 0
        widget.adjustSize()
        widget.setMinimumWidth(max(int(locked_width), widget.sizeHint().width(), self.viewport().width()))


def icon(name: str, size: int = 16) -> QtGui.QIcon:
    icons_dir = _GUI_DIR / "icons"
    path = icons_dir / f"{name}_{size}.png"
    if path.exists():
        return QtGui.QIcon(str(path))
    fallback = icons_dir / f"{name}_24.png"
    return QtGui.QIcon(str(fallback)) if fallback.exists() else QtGui.QIcon()


def make_scrollable_panel(
    widget: QtWidgets.QWidget,
    object_name: str,
    parent: QtWidgets.QWidget | None = None,
) -> QtOverflowScrollArea:
    scroll = QtOverflowScrollArea(parent)
    scroll.setObjectName(object_name)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    scroll.setMinimumSize(0, 0)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")
    scroll.setWidget(widget)
    return scroll


def make_horizontal_overflow_area(
    widget: QtWidgets.QWidget,
    object_name: str,
    *,
    height: int | None = None,
    parent: QtWidgets.QWidget | None = None,
) -> QtOverflowScrollArea:
    scroll = QtOverflowScrollArea(parent, lock_content_width=True)
    scroll.setObjectName(object_name)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setWidgetResizable(False)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    scroll.setMinimumWidth(0)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")
    if height is not None:
        scroll.setFixedHeight(height)
    widget.setProperty("_gr_overflow_min_width", max(widget.minimumWidth(), widget.sizeHint().width()))
    widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    widget.adjustSize()
    scroll.setWidget(widget)
    return scroll


def update_legacy_palette(theme: Theme) -> None:
    """Refresh the compatibility palette used by already-migrated panels."""

    C.clear()
    C.update(theme.legacy_colors())


def apply_theme(widget: QtWidgets.QWidget, theme: Theme | None = None) -> None:
    if theme is not None:
        update_legacy_palette(theme)
        widget.setStyleSheet(QtStylesheetBuilder().build(theme))
        return
    widget.setStyleSheet(
        QtStylesheetBuilder().build(
            Theme(id="matrix", name="Matrix", version="1", colors={}, source_path="")
        )
    )


def heading(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setProperty("heading", True)
    return label
