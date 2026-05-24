"""3ds Max-style ViewCube overlay for the Qt viewport."""

from __future__ import annotations

import math
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from .viewcube_math import (
    CUBE_VERTICES,
    FACE_DIRECTIONS,
    FACE_LABELS,
    FACE_VERTEX_KEYS,
    ViewAction,
    ViewCubeRegion,
    camera_basis_from_angles,
    target_for_region,
)


VIEWCUBE_SIZE = 104
VIEWCUBE_MARGIN = 10
VIEWCUBE_CONTROL_H = 22
VIEWCUBE_MIN_CANVAS_W = 150
VIEWCUBE_MIN_CANVAS_H = 118
VIEWCUBE_DRAG_THRESHOLD = 4


class ViewCubeWidget(QtWidgets.QWidget):
    """Interactive viewport navigation overlay.

    The widget owns only drawing and hit-testing.  It emits requests back to
    the host viewport, which keeps the existing ArcBallCamera as the single
    source of truth for orientation, projection, orbit, and framing.
    """

    viewActionRequested = QtCore.Signal(object)
    orientationRequested = QtCore.Signal(float, float)
    dragOrbitRequested = QtCore.Signal(float, float)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        camera_state: Callable[[], tuple[float, float, bool]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_state = camera_state
        self._hover_region: ViewCubeRegion | str | None = None
        self._press_region: ViewCubeRegion | str | None = None
        self._press_pos = QtCore.QPoint()
        self._last_pos = QtCore.QPoint()
        self._dragging = False
        self._projected_vertices: dict[tuple[int, int, int], QtCore.QPointF] = {}
        self._visible_faces: list[tuple[ViewAction, QtGui.QPolygonF, float]] = []
        self._visible_edges: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
        self._visible_corners: list[tuple[int, int, int]] = []
        self._persp_rect = QtCore.QRectF()
        self._home_rect = QtCore.QRectF()
        self._colors = {
            "panel": QtGui.QColor(22, 24, 29, 166),
            "border": QtGui.QColor(84, 92, 104, 194),
            "face": QtGui.QColor(72, 78, 88, 188),
            "face_alt": QtGui.QColor(58, 64, 74, 178),
            "line": QtGui.QColor(165, 174, 188, 210),
            "text": QtGui.QColor(232, 237, 244),
            "muted": QtGui.QColor(170, 180, 194),
            "accent": QtGui.QColor(255, 190, 82),
            "accent_fill": QtGui.QColor(255, 190, 82, 76),
        }
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.setToolTip("ViewCube")
        self.setFixedSize(self.sizeHint())

    def sizeHint(self) -> QtCore.QSize:  # noqa: N802
        return QtCore.QSize(VIEWCUBE_SIZE + 2 * VIEWCUBE_MARGIN, VIEWCUBE_SIZE + VIEWCUBE_CONTROL_H + 3 * VIEWCUBE_MARGIN)

    def apply_ghost_theme(self, theme) -> None:
        self._colors.update(
            {
                "panel": QtGui.QColor(theme.color("viewportToolbar.background", theme.color("panel.backgroundAlt"))),
                "border": QtGui.QColor(theme.color("viewportToolbar.border", theme.color("panel.border"))),
                "face": QtGui.QColor(theme.color("button.background")),
                "face_alt": QtGui.QColor(theme.color("panel.altBackground", theme.color("panel.backgroundAlt"))),
                "line": QtGui.QColor(theme.color("text.secondary", theme.color("text.primary"))),
                "text": QtGui.QColor(theme.color("text.primary")),
                "muted": QtGui.QColor(theme.color("text.secondary", theme.color("text.primary"))),
                "accent": QtGui.QColor(theme.color("accent.primary")),
                "accent_fill": QtGui.QColor(theme.color("accent.primary")),
            }
        )
        self._colors["panel"].setAlpha(166)
        self._colors["border"].setAlpha(194)
        self._colors["face"].setAlpha(188)
        self._colors["face_alt"].setAlpha(178)
        self._colors["line"].setAlpha(210)
        self._colors["accent_fill"].setAlpha(76)
        self.update()

    def camera_state(self) -> tuple[float, float, bool]:
        if self._camera_state is None:
            return (90.0, 20.0, False)
        try:
            azimuth, elevation, ortho = self._camera_state()
            return (float(azimuth), float(elevation), bool(ortho))
        except Exception:
            return (90.0, 20.0, False)

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        self._draw(painter)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._press_region is not None and event.buttons() & QtCore.Qt.LeftButton:
            if not self._dragging:
                delta = pos - self._press_pos
                if abs(delta.x()) > VIEWCUBE_DRAG_THRESHOLD or abs(delta.y()) > VIEWCUBE_DRAG_THRESHOLD:
                    self._dragging = True
                    self.setCursor(QtCore.Qt.ClosedHandCursor)
            if self._dragging:
                delta = pos - self._last_pos
                self._last_pos = pos
                self.dragOrbitRequested.emit(float(delta.x()) * 0.45, float(-delta.y()) * 0.45)
                self.update()
            return
        before = self._hover_region
        self._hover_region = self._hit_test(pos)
        if self._hover_region != before:
            self.setCursor(QtCore.Qt.PointingHandCursor if self._hover_region is not None else QtCore.Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() != QtCore.Qt.LeftButton:
            return
        self._press_pos = event.position().toPoint()
        self._last_pos = self._press_pos
        self._press_region = self._hit_test(self._press_pos)
        self._dragging = False
        if self._press_region is not None:
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() != QtCore.Qt.LeftButton:
            return
        released_region = self._hit_test(event.position().toPoint())
        press_region = self._press_region
        was_dragging = self._dragging
        self._press_region = None
        self._dragging = False
        self._hover_region = released_region
        self.setCursor(QtCore.Qt.PointingHandCursor if released_region is not None else QtCore.Qt.ArrowCursor)
        if was_dragging:
            self.update()
            event.accept()
            return
        if press_region is not None and self._same_region(press_region, released_region):
            self._activate_region(press_region)
            event.accept()
        self.update()

    def leaveEvent(self, _event: QtCore.QEvent) -> None:  # noqa: N802
        if self._hover_region is not None:
            self._hover_region = None
            self.setCursor(QtCore.Qt.ArrowCursor)
            self.update()

    def _draw(self, painter: QtGui.QPainter) -> None:
        azimuth, elevation, ortho = self.camera_state()
        cube_rect = QtCore.QRectF(VIEWCUBE_MARGIN, VIEWCUBE_MARGIN, VIEWCUBE_SIZE, VIEWCUBE_SIZE)
        panel_rect = QtCore.QRectF(1, 1, self.width() - 2, self.height() - 2)
        painter.setPen(QtGui.QPen(self._colors["border"], 1.0))
        painter.setBrush(self._colors["panel"])
        painter.drawRoundedRect(panel_rect, 7, 7)

        self._build_geometry(azimuth, elevation, cube_rect)
        self._draw_faces(painter)
        self._draw_edges_and_corners(painter)
        self._draw_controls(painter, ortho)

    def _build_geometry(self, azimuth: float, elevation: float, rect: QtCore.QRectF) -> None:
        right, up, fwd = camera_basis_from_angles(azimuth, elevation)
        scale = rect.width() * 0.34
        center = rect.center()
        self._projected_vertices = {}
        depths: dict[tuple[int, int, int], float] = {}
        for key, vertex in CUBE_VERTICES.items():
            sx = center.x() + (vertex[0] * right[0] + vertex[1] * right[1] + vertex[2] * right[2]) * scale
            sy = center.y() - (vertex[0] * up[0] + vertex[1] * up[1] + vertex[2] * up[2]) * scale
            depth = vertex[0] * fwd[0] + vertex[1] * fwd[1] + vertex[2] * fwd[2]
            self._projected_vertices[key] = QtCore.QPointF(sx, sy)
            depths[key] = depth

        visible_faces: list[tuple[ViewAction, QtGui.QPolygonF, float]] = []
        for action, keys in FACE_VERTEX_KEYS.items():
            normal = FACE_DIRECTIONS[action]
            if normal[0] * fwd[0] + normal[1] * fwd[1] + normal[2] * fwd[2] >= -0.001:
                continue
            polygon = QtGui.QPolygonF([self._projected_vertices[key] for key in keys])
            avg_depth = sum(depths[key] for key in keys) / len(keys)
            visible_faces.append((action, polygon, avg_depth))
        self._visible_faces = sorted(visible_faces, key=lambda item: item[2], reverse=True)
        visible_vertex_keys = {key for action, _poly, _depth in self._visible_faces for key in FACE_VERTEX_KEYS[action]}
        self._visible_corners = sorted(visible_vertex_keys)
        self._visible_edges = self._visible_edge_keys(visible_vertex_keys)

    def _visible_edge_keys(
        self,
        visible_vertex_keys: set[tuple[int, int, int]],
    ) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
        edges: set[tuple[tuple[int, int, int], tuple[int, int, int]]] = set()
        for keys in FACE_VERTEX_KEYS.values():
            for i, a in enumerate(keys):
                b = keys[(i + 1) % len(keys)]
                if a in visible_vertex_keys and b in visible_vertex_keys:
                    edges.add(tuple(sorted((a, b))))  # type: ignore[arg-type]
        return sorted(edges)

    def _draw_faces(self, painter: QtGui.QPainter) -> None:
        font = painter.font()
        font.setPointSize(max(7, font.pointSize()))
        font.setBold(True)
        painter.setFont(font)
        for index, (action, polygon, _depth) in enumerate(self._visible_faces):
            highlighted = self._is_hovered("face", action.value)
            color = QtGui.QColor(self._colors["face" if index % 2 == 0 else "face_alt"])
            if highlighted:
                color = QtGui.QColor(self._colors["accent"])
                color.setAlpha(118)
            painter.setPen(QtGui.QPen(self._colors["border"], 1.0))
            painter.setBrush(color)
            painter.drawPolygon(polygon)
            center = self._polygon_center(polygon)
            painter.setPen(self._colors["text"])
            painter.drawText(
                QtCore.QRectF(center.x() - 26, center.y() - 8, 52, 16),
                QtCore.Qt.AlignCenter,
                FACE_LABELS[action],
            )

    def _draw_edges_and_corners(self, painter: QtGui.QPainter) -> None:
        edge_pen = QtGui.QPen(self._colors["line"], 1.25)
        painter.setPen(edge_pen)
        for a, b in self._visible_edges:
            painter.drawLine(self._projected_vertices[a], self._projected_vertices[b])
        hover = self._hover_region
        if isinstance(hover, ViewCubeRegion) and hover.kind == "edge":
            keys = self._edge_keys_from_region(hover)
            if keys is not None:
                painter.setPen(QtGui.QPen(self._colors["accent"], 4.0, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
                painter.drawLine(self._projected_vertices[keys[0]], self._projected_vertices[keys[1]])
        if isinstance(hover, ViewCubeRegion) and hover.kind == "corner":
            key = tuple(int(round(v)) for v in hover.direction)
            point = self._projected_vertices.get(key)  # type: ignore[arg-type]
            if point is not None:
                painter.setPen(QtGui.QPen(self._colors["accent"], 2.0))
                painter.setBrush(self._colors["accent_fill"])
                painter.drawEllipse(point, 7.0, 7.0)

    def _draw_controls(self, painter: QtGui.QPainter, ortho: bool) -> None:
        y = VIEWCUBE_MARGIN + VIEWCUBE_SIZE + 6
        self._home_rect = QtCore.QRectF(VIEWCUBE_MARGIN, y, VIEWCUBE_CONTROL_H, VIEWCUBE_CONTROL_H)
        self._persp_rect = QtCore.QRectF(
            VIEWCUBE_MARGIN + VIEWCUBE_CONTROL_H + 6,
            y,
            VIEWCUBE_SIZE - VIEWCUBE_CONTROL_H - 6,
            VIEWCUBE_CONTROL_H,
        )
        self._draw_button_rect(painter, self._home_rect, self._hover_region == "home")
        painter.setPen(QtGui.QPen(self._colors["text"], 1.5))
        cx = self._home_rect.center().x()
        cy = self._home_rect.center().y()
        roof = QtGui.QPolygonF(
            [
                QtCore.QPointF(cx - 6, cy - 1),
                QtCore.QPointF(cx, cy - 7),
                QtCore.QPointF(cx + 6, cy - 1),
            ]
        )
        painter.drawPolyline(roof)
        painter.drawRect(QtCore.QRectF(cx - 4, cy - 1, 8, 7))

        self._draw_button_rect(painter, self._persp_rect, self._hover_region == "perspective")
        painter.setPen(self._colors["text"])
        painter.drawText(
            self._persp_rect,
            QtCore.Qt.AlignCenter,
            "Ortho" if ortho else "Persp",
        )

    def _draw_button_rect(self, painter: QtGui.QPainter, rect: QtCore.QRectF, highlighted: bool) -> None:
        fill = QtGui.QColor(self._colors["accent_fill"] if highlighted else self._colors["face_alt"])
        painter.setPen(QtGui.QPen(self._colors["accent"] if highlighted else self._colors["border"], 1.0))
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, 4, 4)

    def _hit_test(self, pos: QtCore.QPoint) -> ViewCubeRegion | str | None:
        p = QtCore.QPointF(pos)
        if self._home_rect.contains(p):
            return "home"
        if self._persp_rect.contains(p):
            return "perspective"

        for key in self._visible_corners:
            point = self._projected_vertices.get(key)
            if point is None:
                continue
            if math.hypot(point.x() - p.x(), point.y() - p.y()) <= 8.0:
                return ViewCubeRegion("corner", f"corner:{key}", key, label="Corner view")

        best_edge = None
        best_dist = 1e9
        for a, b in self._visible_edges:
            pa = self._projected_vertices[a]
            pb = self._projected_vertices[b]
            dist = self._distance_to_segment(p, pa, pb)
            if dist < best_dist:
                best_dist = dist
                best_edge = (a, b)
        if best_edge is not None and best_dist <= 6.0:
            direction = tuple((best_edge[0][i] + best_edge[1][i]) * 0.5 for i in range(3))
            return ViewCubeRegion("edge", f"edge:{best_edge}", direction, label="Edge view")

        for action, polygon, _depth in reversed(self._visible_faces):
            if polygon.containsPoint(p, QtCore.Qt.OddEvenFill):
                return ViewCubeRegion("face", action.value, FACE_DIRECTIONS[action], action, FACE_LABELS[action])
        return None

    def _activate_region(self, region: ViewCubeRegion | str) -> None:
        if region == "home":
            self.viewActionRequested.emit(ViewAction.HOME)
            return
        if region == "perspective":
            self.viewActionRequested.emit(ViewAction.PERSPECTIVE)
            return
        if isinstance(region, ViewCubeRegion):
            target = target_for_region(region)
            if target is None:
                return
            self.orientationRequested.emit(float(target[0]), float(target[1]))

    def _is_hovered(self, kind: str, key: str) -> bool:
        return isinstance(self._hover_region, ViewCubeRegion) and self._hover_region.kind == kind and self._hover_region.key == key

    def _same_region(self, a: ViewCubeRegion | str | None, b: ViewCubeRegion | str | None) -> bool:
        if isinstance(a, ViewCubeRegion) and isinstance(b, ViewCubeRegion):
            return a.kind == b.kind and a.key == b.key
        return a == b

    def _edge_keys_from_region(
        self,
        region: ViewCubeRegion,
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
        for a, b in self._visible_edges:
            direction = tuple((a[i] + b[i]) * 0.5 for i in range(3))
            if direction == region.direction:
                return a, b
        return None

    def _polygon_center(self, polygon: QtGui.QPolygonF) -> QtCore.QPointF:
        if polygon.isEmpty():
            return QtCore.QPointF(0.0, 0.0)
        count = max(1, len(polygon))
        x = sum(p.x() for p in polygon) / count
        y = sum(p.y() for p in polygon) / count
        return QtCore.QPointF(x, y)

    def _distance_to_segment(
        self,
        p: QtCore.QPointF,
        a: QtCore.QPointF,
        b: QtCore.QPointF,
    ) -> float:
        abx = b.x() - a.x()
        aby = b.y() - a.y()
        apx = p.x() - a.x()
        apy = p.y() - a.y()
        denom = abx * abx + aby * aby
        if denom <= 1e-9:
            return math.hypot(apx, apy)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
        cx = a.x() + abx * t
        cy = a.y() + aby * t
        return math.hypot(p.x() - cx, p.y() - cy)
