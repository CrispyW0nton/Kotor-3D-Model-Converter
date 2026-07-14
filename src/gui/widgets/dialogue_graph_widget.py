"""Theme-aware visual editor surface for KOTOR dialogue graphs.

The widget presents immutable records from ``core.scripting.dialogue_contract``
and emits stable node/link identifiers.  It owns selection, layout, pan, zoom,
and fit interactions only; graph mutation and DLG serialization stay in the
controller and core scripting layers.
"""

from __future__ import annotations

from collections import defaultdict
from math import cos, radians, sin
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.scripting.dialogue_contract import (
    DialogueGraphLink,
    DialogueGraphNode,
    DialogueGraphSnapshot,
)


def _blend(first: QtGui.QColor, second: QtGui.QColor, amount: float) -> QtGui.QColor:
    ratio = max(0.0, min(1.0, float(amount)))
    return QtGui.QColor(
        round(first.red() * (1.0 - ratio) + second.red() * ratio),
        round(first.green() * (1.0 - ratio) + second.green() * ratio),
        round(first.blue() * (1.0 - ratio) + second.blue() * ratio),
        round(first.alpha() * (1.0 - ratio) + second.alpha() * ratio),
    )


class _DialogueNodeItem(QtWidgets.QGraphicsObject):
    """A movable dialogue node whose geometry follows the active font."""

    def __init__(self, row: DialogueGraphNode, palette: QtGui.QPalette):
        super().__init__()
        self.row = row
        metrics = QtGui.QFontMetrics(QtWidgets.QApplication.font())
        self._width = max(metrics.horizontalAdvance("M" * 24), metrics.height() * 14)
        self._height = metrics.height() * 5.5
        self._palette = QtGui.QPalette(palette)
        self._edges: list[_DialogueEdgeItem] = []
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsSelectable
            | QtWidgets.QGraphicsItem.ItemIsMovable
            | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setToolTip(self._tooltip())

    def _tooltip(self) -> str:
        details = [self.row.title, self.row.preview]
        if self.row.listener:
            details.append(f"Listener: {self.row.listener}")
        return "\n".join(part for part in details if part)

    def add_edge(self, edge: "_DialogueEdgeItem") -> None:
        self._edges.append(edge)

    def set_palette(self, palette: QtGui.QPalette) -> None:
        self._palette = QtGui.QPalette(palette)
        self.update()

    def boundingRect(self) -> QtCore.QRectF:  # noqa: N802 - Qt API
        return QtCore.QRectF(0.0, 0.0, self._width, self._height)

    def connection_point(self, *, outgoing: bool) -> QtCore.QPointF:
        rect = self.sceneBoundingRect()
        return QtCore.QPointF(rect.right() if outgoing else rect.left(), rect.center().y())

    def itemChange(self, change: QtWidgets.QGraphicsItem.GraphicsItemChange, value: object) -> object:  # noqa: N802
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            for edge in self._edges:
                edge.update_path()
        return super().itemChange(change, value)

    def paint(
        self,
        painter: QtGui.QPainter,
        _option: QtWidgets.QStyleOptionGraphicsItem,
        _widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        palette = self._palette
        base = palette.color(QtGui.QPalette.Base)
        accent_role = QtGui.QPalette.Highlight if self.row.kind == "entry" else QtGui.QPalette.Link
        accent = palette.color(accent_role)
        fill = _blend(base, accent, 0.18)
        border = palette.color(QtGui.QPalette.Highlight) if self.isSelected() else accent
        text = palette.color(QtGui.QPalette.Text)
        highlighted_text = palette.color(QtGui.QPalette.HighlightedText)
        rect = self.boundingRect()
        radius = max(2.0, QtGui.QFontMetrics(painter.font()).height() * 0.28)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(border, 2.5 if self.isSelected() else 1.5))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)

        header_height = QtGui.QFontMetrics(painter.font()).height() * 1.7
        header = QtCore.QRectF(rect.left(), rect.top(), rect.width(), header_height)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(header, radius, radius)
        painter.drawRect(QtCore.QRectF(header.left(), header.bottom() - radius, header.width(), radius))

        margin = QtGui.QFontMetrics(painter.font()).height() * 0.55
        title_font = QtGui.QFont(painter.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(highlighted_text)
        painter.drawText(header.adjusted(margin, 0.0, -margin, 0.0), QtCore.Qt.AlignVCenter, self.row.title)

        body_font = QtGui.QFont(painter.font())
        body_font.setBold(False)
        painter.setFont(body_font)
        painter.setPen(text)
        body = rect.adjusted(margin, header_height + margin * 0.45, -margin, -margin)
        metrics = QtGui.QFontMetrics(body_font)
        preview = metrics.elidedText(self.row.preview.replace("\n", " "), QtCore.Qt.ElideRight, round(body.width()))
        kind = "NPC entry" if self.row.kind == "entry" else "Player reply"
        painter.drawText(body, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, f"{kind}\n{preview}")


class _StartItem(_DialogueNodeItem):
    def __init__(self, palette: QtGui.QPalette):
        super().__init__(DialogueGraphNode("__start__", "start", "START", "Conversation entry points", "", "", -1, -1), palette)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, False)

    def paint(
        self,
        painter: QtGui.QPainter,
        _option: QtWidgets.QStyleOptionGraphicsItem,
        _widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        palette = self._palette
        rect = self.boundingRect()
        mid = palette.color(QtGui.QPalette.Mid)
        base = palette.color(QtGui.QPalette.Base)
        text = palette.color(QtGui.QPalette.Text)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(mid, 1.5))
        painter.setBrush(_blend(base, mid, 0.16))
        radius = max(2.0, QtGui.QFontMetrics(painter.font()).height() * 0.28)
        painter.drawRoundedRect(rect, radius, radius)
        font = QtGui.QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(rect, QtCore.Qt.AlignCenter, "START")


class _DialogueEdgeItem(QtWidgets.QGraphicsPathItem):
    def __init__(
        self,
        row: DialogueGraphLink,
        source: _DialogueNodeItem,
        target: _DialogueNodeItem | None,
        palette: QtGui.QPalette,
    ):
        super().__init__()
        self.row = row
        self.source = source
        self.target = target
        self._palette = QtGui.QPalette(palette)
        self.label = QtWidgets.QGraphicsSimpleTextItem(self)
        self.label.setAcceptedMouseButtons(QtCore.Qt.NoButton)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(-1.0)
        self.source.add_edge(self)
        if self.target is not None:
            self.target.add_edge(self)
        self.setToolTip("\n".join(value for value in (row.condition, row.comment) if value))
        self.update_path()
        self.set_palette(palette)

    def set_palette(self, palette: QtGui.QPalette) -> None:
        self._palette = QtGui.QPalette(palette)
        self.label.setBrush(palette.color(QtGui.QPalette.Text))
        label_text = self.row.condition or self.row.comment
        self.label.setText(label_text)
        self.setPen(QtGui.QPen(palette.color(QtGui.QPalette.Mid), 1.5))
        self.update()

    def update_path(self) -> None:
        start = self.source.connection_point(outgoing=True)
        if self.target is None:
            metrics = QtGui.QFontMetrics(QtWidgets.QApplication.font())
            end = start + QtCore.QPointF(metrics.horizontalAdvance("M" * 8), metrics.height() * 2)
        else:
            end = self.target.connection_point(outgoing=False)
        distance = max(abs(end.x() - start.x()) * 0.45, QtGui.QFontMetrics(QtWidgets.QApplication.font()).height() * 2.5)
        path = QtGui.QPainterPath(start)
        path.cubicTo(start + QtCore.QPointF(distance, 0.0), end - QtCore.QPointF(distance, 0.0), end)
        self.setPath(path)
        midpoint = path.pointAtPercent(0.5)
        bounds = self.label.boundingRect()
        self.label.setPos(midpoint.x() - bounds.width() * 0.5, midpoint.y() - bounds.height() - 2.0)

    def paint(
        self,
        painter: QtGui.QPainter,
        _option: QtWidgets.QStyleOptionGraphicsItem,
        _widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        color = self._palette.color(QtGui.QPalette.Highlight if self.isSelected() else QtGui.QPalette.Mid)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.QPen(color, 2.5 if self.isSelected() else 1.5))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawPath(self.path())

        if not self.path().isEmpty():
            end = self.path().pointAtPercent(1.0)
            before = self.path().pointAtPercent(0.96)
            direction = QtCore.QLineF(before, end)
            if direction.length() > 0.0:
                angle = direction.angle()
                size = max(5.0, QtGui.QFontMetrics(painter.font()).height() * 0.42)
                left = end + QtCore.QPointF(
                    -size * cos(radians(angle - 28.0)),
                    size * sin(radians(angle - 28.0)),
                )
                right = end + QtCore.QPointF(
                    -size * cos(radians(angle + 28.0)),
                    size * sin(radians(angle + 28.0)),
                )
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(color)
                painter.drawPolygon(QtGui.QPolygonF((end, left, right)))


class _DialogueGraphView(QtWidgets.QGraphicsView):
    zoomChanged = QtCore.Signal(float)

    def __init__(self, scene: QtWidgets.QGraphicsScene, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(scene, parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.BoundingRectViewportUpdate)
        self._panning = False
        self._pan_origin = QtCore.QPoint()
        self._minimum_zoom = 0.14
        self._maximum_zoom = 4.0

    def zoom_factor(self) -> float:
        return float(self.transform().m11())

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.zoomChanged.emit(self.zoom_factor())

    def fit_all(self) -> None:
        bounds = self.scene().itemsBoundingRect()
        if bounds.isEmpty():
            return
        margin = QtGui.QFontMetrics(self.font()).height() * 2.0
        self.fitInView(bounds.adjusted(-margin, -margin, margin, margin), QtCore.Qt.KeepAspectRatio)
        self.zoomChanged.emit(self.zoom_factor())

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:  # noqa: N802
        direction = 1.18 if event.angleDelta().y() > 0 else 1.0 / 1.18
        target = self.zoom_factor() * direction
        if self._minimum_zoom <= target <= self._maximum_zoom:
            self.scale(direction, direction)
            self.zoomChanged.emit(self.zoom_factor())
        event.accept()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._pan_origin = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DialogueGraphWidget(QtWidgets.QWidget):
    """Reusable DLG graph surface with stable-ID selection signals."""

    nodeSelected = QtCore.Signal(str)
    linkSelected = QtCore.Signal(str)
    selectionCleared = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("dialogueGraphWidget")
        self._scene = QtWidgets.QGraphicsScene(self)
        self.view = _DialogueGraphView(self._scene, self)
        self._nodes: dict[str, _DialogueNodeItem] = {}
        self._links: dict[str, _DialogueEdgeItem] = {}
        self._positions: dict[str, QtCore.QPointF] = {}
        self._snapshot = DialogueGraphSnapshot((), ())
        self._auto_fit_pending = False

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        fit_button = QtWidgets.QToolButton(self)
        fit_button.setText("Fit Graph")
        fit_button.setToolTip("Frame every dialogue node")
        fit_button.clicked.connect(self.fit_all)
        reset_button = QtWidgets.QToolButton(self)
        reset_button.setText("100%")
        reset_button.setToolTip("Reset graph zoom")
        reset_button.clicked.connect(self.view.reset_zoom)
        self.zoom_label = QtWidgets.QLabel("100%", self)
        toolbar.addWidget(fit_button)
        toolbar.addWidget(reset_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, 1)
        self._scene.selectionChanged.connect(self._selection_changed)
        self.view.zoomChanged.connect(lambda value: self.zoom_label.setText(f"{round(value * 100)}%"))
        self.apply_palette(self.palette())

    @property
    def snapshot(self) -> DialogueGraphSnapshot:
        return self._snapshot

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(self._nodes)

    @property
    def link_ids(self) -> tuple[str, ...]:
        return tuple(self._links)

    def set_graph(self, snapshot: DialogueGraphSnapshot) -> None:
        for node_id, item in self._nodes.items():
            self._positions[node_id] = QtCore.QPointF(item.pos())
        self._scene.clear()
        self._nodes.clear()
        self._links.clear()
        self._snapshot = snapshot
        palette = self.palette()
        metrics = QtGui.QFontMetrics(self.font())
        horizontal_gap = metrics.horizontalAdvance("M" * 8)
        vertical_gap = metrics.height() * 2.5

        starter_links = tuple(link for link in snapshot.links if link.starter)
        start_item: _StartItem | None = None
        if starter_links:
            start_item = _StartItem(palette)
            start_item.setPos(0.0, 0.0)
            self._scene.addItem(start_item)

        rows_by_depth: dict[int, list[DialogueGraphNode]] = defaultdict(list)
        for row in snapshot.nodes:
            rows_by_depth[row.depth].append(row)
        for depth in sorted(rows_by_depth):
            for row_index, row in enumerate(rows_by_depth[depth]):
                item = _DialogueNodeItem(row, palette)
                self._scene.addItem(item)
                self._nodes[row.node_id] = item
                prior_position = self._positions.get(row.node_id)
                if prior_position is not None:
                    item.setPos(prior_position)
                    continue
                x_offset = start_item.boundingRect().width() + horizontal_gap if start_item is not None else 0.0
                item.setPos(
                    x_offset + depth * (item.boundingRect().width() + horizontal_gap),
                    row_index * (item.boundingRect().height() + vertical_gap),
                )

        for row in snapshot.links:
            source = start_item if row.source_node_id is None else self._nodes.get(row.source_node_id)
            if source is None:
                continue
            edge = _DialogueEdgeItem(row, source, self._nodes.get(row.target_node_id or ""), palette)
            self._scene.addItem(edge)
            self._links[row.link_id] = edge
        self._update_scene_rect()
        self._auto_fit_pending = True
        QtCore.QTimer.singleShot(0, self._finish_auto_fit)

    def _update_scene_rect(self) -> None:
        bounds = self._scene.itemsBoundingRect()
        margin = QtGui.QFontMetrics(self.font()).height() * 4.0
        self._scene.setSceneRect(bounds.adjusted(-margin, -margin, margin, margin))

    def fit_all(self) -> None:
        self._auto_fit_pending = False
        self._update_scene_rect()
        self.view.fit_all()

    def _finish_auto_fit(self) -> None:
        if not self._auto_fit_pending or not self.isVisible():
            return
        self._auto_fit_pending = False
        self._update_scene_rect()
        self.view.fit_all()

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._auto_fit_pending:
            QtCore.QTimer.singleShot(0, self._finish_auto_fit)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._auto_fit_pending:
            QtCore.QTimer.singleShot(0, self._finish_auto_fit)

    def select_node(self, node_id: str) -> bool:
        item = self._nodes.get(str(node_id))
        if item is None:
            return False
        self._scene.clearSelection()
        item.setSelected(True)
        self.view.centerOn(item)
        return True

    def select_link(self, link_id: str) -> bool:
        item = self._links.get(str(link_id))
        if item is None:
            return False
        self._scene.clearSelection()
        item.setSelected(True)
        self.view.centerOn(item)
        return True

    def clear_selection(self) -> None:
        """Clear the graph selection when another view hides its current row."""

        self._scene.clearSelection()

    def _selection_changed(self) -> None:
        selected = self._scene.selectedItems()
        if not selected:
            self.selectionCleared.emit()
            return
        item = selected[0]
        if isinstance(item, _DialogueNodeItem) and not isinstance(item, _StartItem):
            self.nodeSelected.emit(item.row.node_id)
        elif isinstance(item, _DialogueEdgeItem):
            self.linkSelected.emit(item.row.link_id)

    def apply_palette(self, palette: QtGui.QPalette) -> None:
        self._scene.setBackgroundBrush(palette.color(QtGui.QPalette.Base))
        for item in self._nodes.values():
            item.set_palette(palette)
        for item in self._links.values():
            item.set_palette(palette)
        self.view.viewport().update()

    def apply_ghost_theme(self, _theme: object) -> None:
        """ThemeManager hook; the application palette remains authoritative."""

        self.apply_palette(self.palette())

    def changeEvent(self, event: QtCore.QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange, QtCore.QEvent.FontChange}:
            self.apply_palette(self.palette())


__all__ = ["DialogueGraphWidget"]
