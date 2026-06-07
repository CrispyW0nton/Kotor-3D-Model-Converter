"""Geometry-to-UV preview for diagnosing lightmap atlas suitability."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.lighting.lightmap_uv_validator import LightmapUVValidator


class UVGeometryPreviewWindow(QtWidgets.QDialog):
    def __init__(self, mesh: object, parent: QtWidgets.QWidget | None = None, *, channel: int = 1) -> None:
        super().__init__(parent)
        self.mesh = mesh
        self.channel = int(channel)
        self.validator = LightmapUVValidator()
        self.show_indices = False
        self.setWindowTitle("Geometry in UVs")
        self.resize(760, 620)
        root = QtWidgets.QVBoxLayout(self)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(str(getattr(mesh, "name", "mesh") or "mesh")))
        self.face_index_check = QtWidgets.QCheckBox("Face indices")
        self.face_index_check.toggled.connect(self._toggle_indices)
        row.addWidget(self.face_index_check)
        row.addStretch(1)
        root.addLayout(row)
        self.warning = QtWidgets.QLabel()
        root.addWidget(self.warning)
        self.canvas = QtWidgets.QLabel()
        self.canvas.setMinimumSize(420, 420)
        self.canvas.setStyleSheet("background:#101018; border:1px solid #343446;")
        self.canvas.installEventFilter(self)
        root.addWidget(self.canvas, 1)
        self.render()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.canvas and event.type() == QtCore.QEvent.Resize:
            self.render()
        return super().eventFilter(obj, event)

    def _toggle_indices(self, checked: bool) -> None:
        self.show_indices = bool(checked)
        self.render()

    def render(self) -> None:
        w = max(32, self.canvas.width())
        h = max(32, self.canvas.height())
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor("#101018"))
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(36, 24, min(w - 72, h - 72), min(w - 72, h - 72))
        painter.setPen(QtGui.QPen(QtGui.QColor("#707088"), 2))
        painter.drawRect(rect)
        validation = self.validator.validate_mesh_uvs(self.mesh, self.channel)
        overlap_faces = {idx for pair in validation.overlaps for idx in pair}
        palette = [QtGui.QColor("#54d6a3"), QtGui.QColor("#6fa8ff"), QtGui.QColor("#d8b45e"), QtGui.QColor("#d76f8c")]
        for face_index, tri in enumerate(self.validator._face_uv_triangles(self.mesh, self.channel)):
            if tri is None:
                continue
            material_id = 0
            face_mats = getattr(self.mesh, "face_mats", []) or []
            if face_index < len(face_mats):
                material_id = int(face_mats[face_index])
            color = QtGui.QColor("#ff9466") if face_index in overlap_faces else palette[material_id % len(palette)]
            painter.setPen(QtGui.QPen(color, 1))
            pts = [self._to_screen(rect, u, v) for u, v in tri]
            painter.drawPolygon(QtGui.QPolygonF(pts))
            if self.show_indices:
                center = QtCore.QPointF(sum(p.x() for p in pts) / 3.0, sum(p.y() for p in pts) / 3.0)
                painter.drawText(center, str(face_index))
        painter.end()
        self.canvas.setPixmap(pix)
        warnings = validation.warnings or ["UV geometry layout is ready for baking."]
        self.warning.setText(" ".join(warnings[:3]))

    def _to_screen(self, rect: QtCore.QRectF, u: float, v: float) -> QtCore.QPointF:
        return QtCore.QPointF(rect.left() + float(u) * rect.width(), rect.top() + (1.0 - float(v)) * rect.height())
