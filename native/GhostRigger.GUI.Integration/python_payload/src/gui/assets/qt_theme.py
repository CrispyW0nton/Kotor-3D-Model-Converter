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


class QtFlowLayout(QtWidgets.QLayout):
    """Simple left-to-right wrapping layout for dense tool rows."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        margin: int = 0,
        hspacing: int = 4,
        vspacing: int = 3,
        horizontal_alignment: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignLeft,
    ) -> None:
        super().__init__(parent)
        self._items: list[QtWidgets.QLayoutItem] = []
        self._hspacing = int(hspacing)
        self._vspacing = int(vspacing)
        self._horizontal_alignment = horizontal_alignment
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:  # noqa: N802 - Qt API
        self._items.append(item)

    def setSpacing(self, spacing: int) -> None:  # noqa: N802 - Qt API
        self._hspacing = int(spacing)
        self._vspacing = max(2, int(spacing) // 2)
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802 - Qt API
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem | None:  # noqa: N802 - Qt API
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> QtCore.Qt.Orientations:  # noqa: N802 - Qt API
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        return self._do_layout(QtCore.QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QtCore.QRect) -> None:  # noqa: N802 - Qt API
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802 - Qt API
        return self.minimumSize()

    def minimumSize(self) -> QtCore.QSize:  # noqa: N802 - Qt API
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QtCore.QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect: QtCore.QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        rows: list[tuple[list[tuple[QtWidgets.QLayoutItem, QtCore.QSize]], int, int]] = []
        row: list[tuple[QtWidgets.QLayoutItem, QtCore.QSize]] = []
        row_width = 0
        line_height = 0
        max_width = max(1, effective.width())
        for item in self._items:
            widget = item.widget()
            if widget is not None and not widget.isVisible():
                continue
            hint = item.sizeHint()
            next_width = hint.width() if not row else row_width + self._hspacing + hint.width()
            if row and next_width > max_width:
                rows.append((row, row_width, line_height))
                row = []
                row_width = 0
                line_height = 0
                next_width = hint.width()
            row.append((item, hint))
            row_width = next_width
            line_height = max(line_height, hint.height())
        if row:
            rows.append((row, row_width, line_height))

        y = effective.y()
        for row_items, current_width, current_height in rows:
            x = effective.x()
            if self._horizontal_alignment & QtCore.Qt.AlignHCenter:
                x += max(0, (max_width - current_width) // 2)
            if not test_only:
                for item, hint in row_items:
                    item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
                    x += hint.width() + self._hspacing
            y += current_height + self._vspacing
        if rows:
            y -= self._vspacing
        return y + bottom - rect.y()


def icon(name: str, size: int = 16) -> QtGui.QIcon:
    icons_dir = _GUI_DIR / "icons"
    path = icons_dir / f"{name}.svg"
    if path.exists():
        return QtGui.QIcon(str(path))
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
