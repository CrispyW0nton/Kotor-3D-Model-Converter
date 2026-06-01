"""UV atlas preview window for the lightmap baker."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.lighting.lightmap_uv_validator import LightmapUVValidator


class UVPreviewWindow(QtWidgets.QDialog):
    def __init__(self, mesh: object, parent: QtWidgets.QWidget | None = None, *, channel: int = 0) -> None:
        super().__init__(parent)
        self.mesh = mesh
        self.validator = LightmapUVValidator()
        self.channel = int(channel)
        self.setWindowTitle("UV Preview")
        self.resize(760, 620)
        root = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.channel_combo = QtWidgets.QComboBox()
        for info in self.validator.inspect_mesh_uv_channels(mesh, 3):
            label = f"{info.display_name} ({'present' if info.has_uvs else 'missing'})"
            self.channel_combo.addItem(label, info.channel_index)
        self.channel_combo.currentIndexChanged.connect(self._channel_changed)
        top.addWidget(QtWidgets.QLabel("UV Channel"))
        top.addWidget(self.channel_combo, 1)
        root.addLayout(top)
        self.stats = QtWidgets.QLabel()
        root.addWidget(self.stats)
        self.canvas = QtWidgets.QLabel()
        self.canvas.setMinimumSize(420, 420)
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setStyleSheet("background:#0d0d16; border:1px solid #303044;")
        self.canvas.installEventFilter(self)
        root.addWidget(self.canvas, 1)
        self._select_channel(channel)
        self.render()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.canvas and event.type() == QtCore.QEvent.Resize:
            self.render()
        return super().eventFilter(obj, event)

    def _channel_changed(self) -> None:
        self.channel = int(self.channel_combo.currentData())
        self.render()

    def _select_channel(self, channel: int) -> None:
        idx = self.channel_combo.findData(int(channel))
        if idx >= 0:
            self.channel_combo.setCurrentIndex(idx)

    def render(self) -> None:
        w = max(32, self.canvas.width())
        h = max(32, self.canvas.height())
        pix = QtGui.QPixmap(w, h)
        pix.fill(QtGui.QColor("#0d0d16"))
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = QtCore.QRectF(36, 24, min(w - 72, h - 72), min(w - 72, h - 72))
        painter.setPen(QtGui.QPen(QtGui.QColor("#5e6385"), 2))
        painter.drawRect(rect)
        validation = self.validator.validate_mesh_uvs(self.mesh, self.channel)
        overlap_faces = {idx for pair in validation.overlaps for idx in pair}
        uvs = self.validator._uvs(self.mesh, self.channel)
        if not uvs:
            painter.setPen(QtGui.QColor("#d89090"))
            painter.drawText(self.canvas.rect(), QtCore.Qt.AlignCenter, "No UV data for this channel")
        else:
            for face_index, tri in enumerate(self.validator._face_uv_triangles(self.mesh, self.channel)):
                if tri is None:
                    continue
                color = "#ffcc66" if face_index in overlap_faces else "#55e08a"
                painter.setPen(QtGui.QPen(QtGui.QColor(color), 1))
                pts = [self._to_screen(rect, u, v) for u, v in tri]
                painter.drawPolygon(QtGui.QPolygonF(pts))
        painter.end()
        self.canvas.setPixmap(pix)
        info = self.validator.inspect_mesh_uv_channels(self.mesh, max_channels=self.channel + 1)[self.channel]
        status = "recommended" if info.recommended_for_lightmap else "check warnings"
        self.stats.setText(
            f"{getattr(self.mesh, 'name', 'mesh')} - {info.display_name}: "
            f"{info.uv_count} UVs, {info.face_count} faces, coverage {info.coverage_ratio:.1%}, {status}"
        )

    def _to_screen(self, rect: QtCore.QRectF, u: float, v: float) -> QtCore.QPointF:
        return QtCore.QPointF(rect.left() + float(u) * rect.width(), rect.top() + (1.0 - float(v)) * rect.height())
