"""Mini neutral-pose thumbnail widget for the Qt viewport."""

from __future__ import annotations

from ..shared.dependencies import Optional, QtCore, QtGui, QtWidgets

# ── T403: Mini-thumbnail inset widget ──────────────────────────────────────
# A floating QGraphicsView-backed inset pinned to the top-right corner of
# the main viewport canvas.  Renders the same scene at neutral pose with
# no joint overlay, and emits ``clicked`` when the user taps it so the
# host can reset the main camera.
#
# Sized per the M4 roadmap: 220×280 px, with an 8 px margin from the
# canvas edges and a subtle border so it reads as an inset over the
# main render.
THUMBNAIL_WIDTH_PX  = 220
THUMBNAIL_HEIGHT_PX = 280
THUMBNAIL_MARGIN_PX = 8


class _MiniThumbnailWidget(QtWidgets.QGraphicsView):
    """Top-right inset that previews the scene at neutral pose.

    Implemented as a ``QGraphicsView`` per the M4/T403 spec.  The host
    widget pushes a pre-rendered ``QPixmap`` via :meth:`set_thumbnail`;
    a click anywhere on the widget emits :attr:`clicked` so the host
    can reset the main camera.
    """

    clicked = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(THUMBNAIL_WIDTH_PX, THUMBNAIL_HEIGHT_PX)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        self.setStyleSheet(
            "QGraphicsView {"
            "  background:#101216;"
            "  border:1px solid #3a3f47;"
            "  border-radius:4px;"
            "}"
        )
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Click to reset camera (frame all)")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        # The graphics scene holds a single QPixmap item — the thumbnail
        # render.  Updates replace that item's pixmap rather than the
        # scene contents so geometry stays stable.

        self._scene = QtWidgets.QGraphicsScene(self)
        self._scene.setBackgroundBrush(QtGui.QColor("#101216"))
        self.setScene(self._scene)
        self._pixmap_item = QtWidgets.QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self._scene.addItem(self._pixmap_item)
        # Placeholder text shown until a render arrives.
        self._placeholder = self._scene.addText(
            "Neutral pose",
            QtGui.QFont("Sans", 8),
        )
        self._placeholder.setDefaultTextColor(QtGui.QColor("#8f9aaa"))
        self._placeholder.setPos(8.0, 8.0)

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(
            "QGraphicsView {"
            f"  background:{theme.color('viewport.background')};"
            f"  border:1px solid {theme.color('viewport.border')};"
            "  border-radius:4px;"
            "}"
        )
        self._scene.setBackgroundBrush(QtGui.QColor(theme.color("viewport.background")))
        self._placeholder.setDefaultTextColor(QtGui.QColor(theme.color("viewport.text")))

    def set_thumbnail(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        """Replace the inset's pixmap with *pixmap* (or clear if None)."""
        if pixmap is None or pixmap.isNull():
            self._pixmap_item.setPixmap(QtGui.QPixmap())
            self._placeholder.setVisible(True)
            return
        # Scale into the widget while preserving aspect ratio so a
        # square-ish character still reads correctly inside the
        # 220×280 frame.
        scaled = pixmap.scaled(
            THUMBNAIL_WIDTH_PX - 4,
            THUMBNAIL_HEIGHT_PX - 4,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self._pixmap_item.setPixmap(scaled)
        # Centre the pixmap in the scene.
        px = (THUMBNAIL_WIDTH_PX - scaled.width()) * 0.5
        py = (THUMBNAIL_HEIGHT_PX - scaled.height()) * 0.5
        self._pixmap_item.setPos(px, py)
        self._placeholder.setVisible(False)
        self._scene.setSceneRect(
            0.0, 0.0, float(THUMBNAIL_WIDTH_PX), float(THUMBNAIL_HEIGHT_PX)
        )

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # noqa: N802
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

__all__ = tuple(name for name in globals() if not name.startswith("__"))
