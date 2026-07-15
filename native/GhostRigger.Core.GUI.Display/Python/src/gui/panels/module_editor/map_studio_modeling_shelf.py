"""Compact clean-room modeling shelf used only by Map Studio.

The interaction density follows the user's Maya shelf (35 x 34 icon-only
buttons, repeatable commands, double-click options).  All artwork is drawn by
Ghost Studio at runtime from semantic primitives; no Autodesk image resource
is bundled or loaded.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.modules.map_studio_modeling_shelf import map_studio_modeling_shelf_commands


_ORANGE = QtGui.QColor("#db8735")
_CYAN = QtGui.QColor("#38b9d6")
_GREEN = QtGui.QColor("#66b56c")
_RED = QtGui.QColor("#d85b55")


def _line(painter: QtGui.QPainter, color: QtGui.QColor, width: float = 1.7) -> None:
    pen = QtGui.QPen(color, width, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)


def _polygon(painter: QtGui.QPainter, points, *, fill: QtGui.QColor = _ORANGE, stroke: QtGui.QColor | None = None) -> None:
    painter.setBrush(fill)
    painter.setPen(QtGui.QPen(stroke or fill.darker(135), 1.1))
    painter.drawPolygon(QtGui.QPolygonF(tuple(QtCore.QPointF(*point) for point in points)))


def _cube(painter: QtGui.QPainter, x: float, y: float, size: float, *, fill: QtGui.QColor = _ORANGE) -> None:
    front = QtCore.QRectF(x, y + (size * 0.22), size * 0.72, size * 0.72)
    painter.setBrush(fill)
    painter.setPen(QtGui.QPen(fill.darker(145), 1.0))
    painter.drawRect(front)
    _polygon(
        painter,
        ((x, y + size * 0.22), (x + size * 0.28, y), (x + size, y), (x + size * 0.72, y + size * 0.22)),
        fill=fill.lighter(118),
    )
    _polygon(
        painter,
        ((x + size * 0.72, y + size * 0.22), (x + size, y), (x + size, y + size * 0.72), (x + size * 0.72, y + size * 0.94)),
        fill=fill.darker(118),
    )


def _arrow(painter: QtGui.QPainter, start: tuple[float, float], end: tuple[float, float], color: QtGui.QColor = _CYAN) -> None:
    _line(painter, color, 2.0)
    painter.drawLine(QtCore.QPointF(*start), QtCore.QPointF(*end))
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = end
    base = (end[0] - ux * 4.5, end[1] - uy * 4.5)
    _polygon(painter, (tip, (base[0] + px * 2.5, base[1] + py * 2.5), (base[0] - px * 2.5, base[1] - py * 2.5)), fill=color)


def _nodes(painter: QtGui.QPainter, points, color: QtGui.QColor = _ORANGE, radius: float = 2.1) -> None:
    painter.setPen(QtGui.QPen(color.darker(150), 0.8))
    painter.setBrush(color)
    for x, y in points:
        painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)


def _text_overlay(painter: QtGui.QPainter, text: str, color: QtGui.QColor) -> None:
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(8 if len(text) > 2 else 10)
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(QtCore.QRectF(1, 1, 26, 25), QtCore.Qt.AlignmentFlag.AlignCenter, text)


def map_studio_modeling_icon(icon_key: str, palette: QtGui.QPalette | None = None, size: int = 28) -> QtGui.QIcon:
    """Draw one original semantic shelf icon."""

    extent = max(20, int(size))
    pixmap = QtGui.QPixmap(extent, extent)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.scale(extent / 28.0, extent / 28.0)
    fg = (palette or QtWidgets.QApplication.palette()).color(QtGui.QPalette.ColorRole.WindowText)
    muted = QtGui.QColor(fg)
    muted.setAlpha(170)
    key = str(icon_key or "")

    if key in {"reset_transform", "center_pivot", "zero_pivot", "freeze_transform"}:
        _line(painter, muted, 1.4)
        painter.drawEllipse(QtCore.QPointF(14, 14), 8, 8)
        painter.drawLine(4, 14, 24, 14)
        painter.drawLine(14, 4, 14, 24)
        _text_overlay(painter, {"reset_transform": "RT", "center_pivot": "CP", "zero_pivot": "ZP", "freeze_transform": "FT"}[key], _ORANGE)
    elif key in {"separate", "combine", "duplicate_special"}:
        if key == "combine":
            _cube(painter, 5, 7, 11, fill=_ORANGE)
            _cube(painter, 12, 7, 11, fill=_CYAN)
            _arrow(painter, (5, 23), (22, 23), _GREEN)
        elif key == "separate":
            _cube(painter, 8, 7, 12, fill=_ORANGE)
            _arrow(painter, (14, 22), (4, 24), _CYAN)
            _arrow(painter, (14, 22), (24, 24), _CYAN)
        else:
            _cube(painter, 4, 8, 10, fill=_ORANGE)
            _cube(painter, 13, 5, 10, fill=_CYAN)
            _text_overlay(painter, "+", _GREEN)
    elif key in {"fill_hole", "make_hole", "boolean_difference"}:
        painter.setPen(QtGui.QPen(_ORANGE, 2.0))
        painter.setBrush(_ORANGE.lighter(150) if key == "fill_hole" else QtCore.Qt.BrushStyle.NoBrush)
        painter.drawRect(QtCore.QRectF(5, 6, 18, 16))
        painter.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.transparent))
        painter.setPen(QtGui.QPen(_RED if key != "fill_hole" else _GREEN, 2.0))
        painter.drawEllipse(QtCore.QPointF(14, 14), 4.5, 4.5)
        if key == "boolean_difference":
            _text_overlay(painter, "A-B", _RED)
    elif key == "mirror":
        _line(painter, _CYAN, 1.4)
        painter.drawLine(14, 3, 14, 25)
        _cube(painter, 2.5, 8, 9, fill=_ORANGE)
        _cube(painter, 16.5, 8, 9, fill=QtGui.QColor(_ORANGE.red(), _ORANGE.green(), _ORANGE.blue(), 120))
    elif key == "bevel":
        path = QtGui.QPainterPath()
        path.moveTo(5, 22); path.lineTo(5, 10); path.lineTo(11, 4); path.lineTo(23, 4); path.lineTo(23, 22); path.closeSubpath()
        painter.setBrush(_ORANGE); painter.setPen(QtGui.QPen(_ORANGE.darker(150), 1.2)); painter.drawPath(path)
        _line(painter, _CYAN, 2.2); painter.drawLine(5, 10, 11, 4)
    elif key == "bridge":
        _line(painter, _ORANGE, 2.0)
        painter.drawLine(4, 7, 4, 21); painter.drawLine(24, 7, 24, 21)
        painter.drawLine(4, 7, 24, 7); painter.drawLine(4, 21, 24, 21)
        _line(painter, _CYAN, 1.5)
        for y in (10.5, 14, 17.5): painter.drawLine(4, y, 24, y)
    elif key == "extrude":
        _polygon(painter, ((4, 18), (14, 22), (22, 17), (12, 13)), fill=_ORANGE)
        _arrow(painter, (13, 14), (13, 3), _CYAN)
        _line(painter, _ORANGE.darker(140), 1.2); painter.drawLine(4, 18, 4, 23); painter.drawLine(22, 17, 22, 22)
    elif key in {"merge", "target_weld", "connect"}:
        pts = ((5, 7), (5, 21), (23, 7), (23, 21))
        _nodes(painter, pts)
        _line(painter, _CYAN, 1.8)
        if key == "connect":
            painter.drawLine(5, 7, 23, 21); painter.drawLine(5, 21, 23, 7)
        else:
            _arrow(painter, (6, 7), (14, 14), _CYAN); _arrow(painter, (22, 21), (14, 14), _CYAN)
            _nodes(painter, ((14, 14),), _GREEN, 2.8)
    elif key in {"multi_cut", "edge_loop"}:
        _cube(painter, 5, 6, 16, fill=QtGui.QColor(_ORANGE.red(), _ORANGE.green(), _ORANGE.blue(), 150))
        _line(painter, _CYAN, 2.0)
        if key == "multi_cut":
            painter.drawLine(3, 22, 24, 5); _nodes(painter, ((7, 19), (14, 13), (21, 7)), _GREEN)
        else:
            painter.drawLine(5, 12, 21, 12); painter.drawLine(5, 17, 21, 17)
    elif key in {"lattice", "wrap", "shrink_wrap", "bend"}:
        if key == "lattice":
            _line(painter, _CYAN, 1.1)
            for value in (5, 14, 23):
                painter.drawLine(value, 5, value, 23); painter.drawLine(5, value, 23, value)
            _nodes(painter, tuple((x, y) for x in (5, 14, 23) for y in (5, 14, 23)), _ORANGE, 1.5)
        elif key == "bend":
            path = QtGui.QPainterPath(); path.moveTo(5, 22); path.cubicTo(7, 7, 18, 4, 24, 14)
            _line(painter, _ORANGE, 5.0); painter.drawPath(path); _line(painter, _CYAN, 1.2); painter.drawPath(path)
        else:
            _cube(painter, 7, 9, 13, fill=_ORANGE)
            path = QtGui.QPainterPath(); path.moveTo(3, 7); path.cubicTo(8, 1, 20, 1, 25, 7); path.cubicTo(20, 25, 8, 25, 3, 7)
            _line(painter, _CYAN, 1.8); painter.drawPath(path)
            if key == "shrink_wrap": _arrow(painter, (14, 2), (14, 10), _GREEN)
    elif key in {"reverse_normals", "soften_edges", "harden_edges"}:
        _polygon(painter, ((4, 20), (14, 5), (24, 20)), fill=QtGui.QColor(_ORANGE.red(), _ORANGE.green(), _ORANGE.blue(), 140))
        if key == "reverse_normals":
            _arrow(painter, (14, 15), (14, 4), _CYAN); _arrow(painter, (18, 7), (18, 18), _RED)
        elif key == "soften_edges":
            path = QtGui.QPainterPath(); path.moveTo(4, 20); path.quadTo(14, 10, 24, 20); _line(painter, _CYAN, 2.5); painter.drawPath(path)
        else:
            _line(painter, _CYAN, 2.5); painter.drawLine(4, 20, 14, 9); painter.drawLine(14, 9, 24, 20)
    elif key == "history":
        _line(painter, _ORANGE, 2.0)
        for index in range(3): painter.drawRect(QtCore.QRectF(5 + index * 3, 5 + index * 3, 14, 14))
        _line(painter, _RED, 2.6); painter.drawLine(5, 24, 24, 5)
    elif key in {"select_triangles", "select_quads", "contained_faces"}:
        if key == "select_triangles":
            _polygon(painter, ((4, 22), (14, 4), (24, 22)), fill=_ORANGE)
        elif key == "select_quads":
            _polygon(painter, ((5, 6), (23, 6), (23, 22), (5, 22)), fill=_ORANGE)
        else:
            _polygon(painter, ((3, 6), (25, 6), (23, 23), (5, 23)), fill=QtGui.QColor(_ORANGE.red(), _ORANGE.green(), _ORANGE.blue(), 100))
            _polygon(painter, ((9, 10), (19, 10), (19, 19), (9, 19)), fill=_GREEN)
    elif key == "make_live":
        _cube(painter, 7, 8, 14, fill=_ORANGE)
        _line(painter, _CYAN, 1.4); painter.drawEllipse(QtCore.QPointF(14, 14), 11, 11); painter.drawLine(14, 1, 14, 27); painter.drawLine(1, 14, 27, 14)
    elif key == "quad_draw":
        pts = ((5, 6), (23, 6), (23, 22), (5, 22))
        _line(painter, _CYAN, 2.0)
        for first, second in zip(pts, pts[1:] + pts[:1]): painter.drawLine(QtCore.QPointF(*first), QtCore.QPointF(*second))
        _nodes(painter, pts, _ORANGE, 2.5)
        _polygon(painter, ((10, 10), (18, 10), (18, 18), (10, 18)), fill=QtGui.QColor(_GREEN.red(), _GREEN.green(), _GREEN.blue(), 130))
    else:
        _cube(painter, 6, 6, 16, fill=_ORANGE)

    painter.end()
    return QtGui.QIcon(pixmap)


class MapStudioModelingShelfButton(QtWidgets.QToolButton):
    """One command-repeatable shelf button with Maya-style options access."""

    commandRequested = QtCore.Signal(str)
    optionsRequested = QtCore.Signal(str)

    def __init__(self, command, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.command = command
        self.setObjectName(f"mapStudioModelingShelfButton_{command.key}")
        self.setAccessibleName(command.label)
        self.setAccessibleDescription(command.description)
        self.setFixedSize(35, 34)
        self.setIconSize(QtCore.QSize(28, 28))
        self.setAutoRaise(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setIcon(map_studio_modeling_icon(command.icon_key, self.palette(), 28))
        shortcut = f" ({command.shortcut})" if command.shortcut else ""
        options = "\nDouble-click or right-click for Tool Options." if command.options_key else ""
        self.setToolTip(f"{command.label}{shortcut}\n{command.description}{options}")
        self.clicked.connect(lambda _checked=False: self.commandRequested.emit(command.action_key))

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.command.options_key:
            self.optionsRequested.emit(self.command.options_key)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:  # noqa: N802 - Qt API
        menu = QtWidgets.QMenu(self)
        run = menu.addAction(self.icon(), self.command.label)
        run.triggered.connect(lambda: self.commandRequested.emit(self.command.action_key))
        if self.command.options_key:
            options = menu.addAction("Tool Options...")
            options.triggered.connect(lambda: self.optionsRequested.emit(self.command.options_key))
        menu.exec(event.globalPos())

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802 - Qt API
        if event.type() in {QtCore.QEvent.Type.PaletteChange, QtCore.QEvent.Type.StyleChange}:
            self.setIcon(map_studio_modeling_icon(self.command.icon_key, self.palette(), 28))
        super().changeEvent(event)


class MapStudioModelingShelf(QtWidgets.QWidget):
    """The user's 32-command modeling shelf in its stable reference order."""

    commandRequested = QtCore.Signal(str)
    optionsRequested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioModelingShelf")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(1)
        self.buttons: dict[str, MapStudioModelingShelfButton] = {}
        for command in map_studio_modeling_shelf_commands():
            button = MapStudioModelingShelfButton(command, self)
            button.commandRequested.connect(self.commandRequested)
            button.optionsRequested.connect(self.optionsRequested)
            self.buttons[command.key] = button
            row.addWidget(button)
        row.addStretch(1)
        self.setFixedHeight(34)

    def button(self, key: str) -> MapStudioModelingShelfButton | None:
        return self.buttons.get(str(key or ""))


__all__ = [
    "MapStudioModelingShelf",
    "MapStudioModelingShelfButton",
    "map_studio_modeling_icon",
]
