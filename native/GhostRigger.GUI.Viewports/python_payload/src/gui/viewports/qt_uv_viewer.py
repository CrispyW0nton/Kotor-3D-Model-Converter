"""Qt UV viewer window for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.math.frame_math import _clean_tex_name


class QtUVViewerWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._model = None
        self._mesh_nodes = []
        self._selected_node = None
        self._tex_cache = None
        self._show_grid = True
        self._show_texture = True
        self._zoom = 1.0
        self._pan_x = 32.0
        self._pan_y = 32.0
        self.setWindowTitle("UV Viewer")
        self.resize(900, 700)
        self._build()

    def _build(self) -> None:
        central = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        toolbar = QtWidgets.QFrame()
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(4, 4, 4, 4)
        self.node_combo = QtWidgets.QComboBox()
        self.node_combo.currentTextChanged.connect(self._select_node_name)
        row.addWidget(QtWidgets.QLabel("Node:"))
        row.addWidget(self.node_combo, 1)
        fit_button = QtWidgets.QPushButton("Fit")
        fit_button.clicked.connect(self.fit_view)
        row.addWidget(fit_button)
        self.grid_button = QtWidgets.QPushButton("Grid")
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_button.clicked.connect(self._toggle_grid)
        row.addWidget(self.grid_button)
        self.texture_button = QtWidgets.QPushButton("Texture")
        self.texture_button.setCheckable(True)
        self.texture_button.setChecked(True)
        self.texture_button.clicked.connect(self._toggle_texture)
        row.addWidget(self.texture_button)
        row.addStretch(1)
        self.canvas = QtWidgets.QLabel("UV viewport migration host")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(420, 320)
        self.canvas.setStyleSheet("background:#080812; color:#ccccff; border:1px solid #252550;")
        self.canvas.installEventFilter(self)
        root.addWidget(toolbar)
        root.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

    def set_model(self, model) -> None:
        self._model = model
        self._mesh_nodes = list(self._iter_mesh_nodes(model)) if model else []
        self.node_combo.blockSignals(True)
        self.node_combo.clear()
        self.node_combo.addItems([node.name for node in self._mesh_nodes] or ["(no mesh nodes)"])
        self.node_combo.blockSignals(False)
        if self._mesh_nodes:
            self._selected_node = self._mesh_nodes[0]
        else:
            self._selected_node = None
        self.fit_view()

    def set_selected_node(self, node) -> None:
        if node in self._mesh_nodes:
            self._selected_node = node
            idx = self._mesh_nodes.index(node)
            self.node_combo.blockSignals(True)
            self.node_combo.setCurrentIndex(idx)
            self.node_combo.blockSignals(False)
            self.fit_view()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self.canvas and event.type() == QtCore.QEvent.Resize:
            self.render_uv()
        return super().eventFilter(obj, event)

    def fit_view(self) -> None:
        w = max(32, self.canvas.width())
        h = max(32, self.canvas.height())
        node = self._selected_node
        margin = 34
        if node and getattr(node, "uvs", None):
            us = [uv[0] for uv in node.uvs]
            vs = [uv[1] for uv in node.uvs]
            u_min, u_max = min(min(us), 0.0), max(max(us), 1.0)
            v_min, v_max = min(min(vs), 0.0), max(max(vs), 1.0)
            u_pad = (u_max - u_min) * 0.1 + 0.05
            v_pad = (v_max - v_min) * 0.1 + 0.05
            u_min -= u_pad; u_max += u_pad
            v_min -= v_pad; v_max += v_pad
            uv_w = max(0.001, u_max - u_min)
            uv_h = max(0.001, v_max - v_min)
            self._zoom = min((w - margin * 2) / uv_w, (h - margin * 2) / uv_h)
            self._pan_x = margin + ((w - margin * 2) - uv_w * self._zoom) * 0.5 - u_min * self._zoom
            self._pan_y = margin + ((h - margin * 2) - uv_h * self._zoom) * 0.5 + (1.0 + v_min) * self._zoom - self._zoom
        else:
            size = max(32, min(w, h) - margin * 2)
            self._zoom = float(size)
            self._pan_x = (w - size) * 0.5
            self._pan_y = (h - size) * 0.5
        self.render_uv()

    def render_uv(self) -> None:
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor("#0d0d1a"))
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if self._show_grid:
            self._draw_checker(painter, w, h)
        self._draw_texture(painter)
        self._draw_uv_border(painter)
        self._draw_uv_wire(painter)
        painter.end()
        self.canvas.setPixmap(pix)

    def _iter_mesh_nodes(self, model):
        if not model or not getattr(model, "root_node", None):
            return
        stack = [model.root_node]
        visited = set()
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            if getattr(node, "is_mesh", False) and (getattr(node, "uvs", None) or getattr(node, "vertices", None)):
                yield node
            stack.extend(getattr(node, "children", []) or [])

    def _select_node_name(self, name: str) -> None:
        for node in self._mesh_nodes:
            if node.name == name:
                self._selected_node = node
                self.fit_view()
                return

    def _toggle_grid(self, checked: bool) -> None:
        self._show_grid = checked
        self.render_uv()

    def _toggle_texture(self, checked: bool) -> None:
        self._show_texture = checked
        self.render_uv()

    def _uv_to_screen(self, u: float, v: float) -> QtCore.QPointF:
        return QtCore.QPointF(self._pan_x + u * self._zoom, self._pan_y + (1.0 - v) * self._zoom)

    def _draw_checker(self, painter: QtGui.QPainter, w: int, h: int) -> None:
        size = 32
        a = QtGui.QColor(40, 40, 55)
        b = QtGui.QColor(25, 25, 40)
        for y in range(0, h, size):
            for x in range(0, w, size):
                painter.fillRect(x, y, size, size, a if ((x // size + y // size) % 2 == 0) else b)

    def _draw_texture(self, painter: QtGui.QPainter) -> None:
        node = self._selected_node
        if not (self._show_texture and node and self._tex_cache):
            return
        tex_name = _clean_tex_name(getattr(node, "texture", "") or "")
        if not tex_name:
            return
        try:
            img = self._tex_cache.get(tex_name)
            if img is None:
                return
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            qimg = QtGui.QImage(
                img.tobytes("raw", "RGBA"),
                img.width,
                img.height,
                img.width * 4,
                QtGui.QImage.Format_RGBA8888,
            ).copy()
            tl = self._uv_to_screen(0.0, 1.0)
            br = self._uv_to_screen(1.0, 0.0)
            painter.setOpacity(0.78)
            painter.drawImage(QtCore.QRectF(tl, br), qimg)
            painter.setOpacity(1.0)
        except Exception:
            return

    def _draw_uv_border(self, painter: QtGui.QPainter) -> None:
        painter.setPen(QtGui.QPen(QtGui.QColor(80, 80, 160), 2))
        tl = self._uv_to_screen(0.0, 1.0)
        br = self._uv_to_screen(1.0, 0.0)
        painter.drawRect(QtCore.QRectF(tl, br))

    def _draw_uv_wire(self, painter: QtGui.QPainter) -> None:
        node = self._selected_node
        if not (node and getattr(node, "uvs", None) and getattr(node, "faces", None)):
            painter.setPen(QtGui.QColor(160, 90, 110))
            painter.drawText(self.canvas.rect(), QtCore.Qt.AlignCenter, "No UV data for this node")
            return
        painter.setPen(QtGui.QPen(QtGui.QColor(68, 255, 136), 1))
        uvs = node.uvs
        for face in node.faces:
            try:
                pts = [self._uv_to_screen(uvs[i][0], uvs[i][1]) for i in face[:3] if i < len(uvs)]
            except Exception:
                continue
            if len(pts) == 3:
                painter.drawPolygon(QtGui.QPolygonF(pts))
