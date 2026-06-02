"""Qt host for renderer-owned viewport surface widgets."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class RendererSurfaceHost(QtWidgets.QWidget):
    """Owns the visible renderer surface plus a transparent overlay image layer."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("RendererSurfaceHost")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)

        self._surface_widget: Optional[QtWidgets.QWidget] = None
        self._input_bridge: Optional[QtCore.QObject] = None
        self._surface_backend_id = ""
        self._surface_live = False
        self._bridge_installed = False

        self._layout = QtWidgets.QStackedLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)

        self._overlay_label = QtWidgets.QLabel(self)
        self._overlay_label.setObjectName("ViewportOverlayLayer")
        self._overlay_label.setAlignment(QtCore.Qt.AlignCenter)
        self._overlay_label.setScaledContents(False)
        self._overlay_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._overlay_label.setStyleSheet("background: transparent;")
        self._overlay_label.hide()
        self._layout.addWidget(self._overlay_label)

        self._diagnostics_label = QtWidgets.QLabel(self)
        self._diagnostics_label.setObjectName("ViewportDiagnosticsOverlay")
        self._diagnostics_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self._diagnostics_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self._diagnostics_label.setStyleSheet(
            "QLabel#ViewportDiagnosticsOverlay {"
            "background: rgba(5, 12, 18, 168);"
            "color: #bde8ff;"
            "border: 1px solid rgba(70, 150, 190, 150);"
            "padding: 5px 7px;"
            "font-family: Consolas, monospace;"
            "font-size: 10px;"
            "}"
        )
        self._diagnostics_label.hide()

    def set_renderer_surface(
        self,
        surface_widget: QtWidgets.QWidget,
        *,
        backend_id: str = "",
        live_surface: bool = False,
    ) -> None:
        if surface_widget is self._surface_widget:
            self._surface_backend_id = str(backend_id or "")
            self._surface_live = bool(live_surface)
            self.install_input_bridge(self._input_bridge)
            self._raise_overlay()
            return

        old = self._surface_widget
        if old is not None:
            try:
                if self._input_bridge is not None:
                    old.removeEventFilter(self._input_bridge)
            except Exception:
                pass
            self._layout.removeWidget(old)
            old.setParent(None)
            old.deleteLater()

        self._surface_widget = surface_widget
        self._surface_backend_id = str(backend_id or "")
        self._surface_live = bool(live_surface)
        self._bridge_installed = False
        surface_widget.setParent(self)
        surface_widget.setMouseTracking(True)
        surface_widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        surface_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._layout.insertWidget(0, surface_widget)
        self._layout.setCurrentWidget(surface_widget)
        surface_widget.show()
        surface_widget.raise_()
        self.clear_overlay()
        self._raise_overlay()
        self.install_input_bridge(self._input_bridge)

    def clear_renderer_surface(self) -> None:
        if self._surface_widget is None:
            return
        old = self._surface_widget
        try:
            if self._input_bridge is not None:
                old.removeEventFilter(self._input_bridge)
        except Exception:
            pass
        self._layout.removeWidget(old)
        old.setParent(None)
        old.deleteLater()
        self._surface_widget = None
        self._surface_backend_id = ""
        self._surface_live = False
        self._bridge_installed = False
        self.clear_overlay()

    def set_diagnostics_text(self, text: str) -> None:
        text = str(text or "").strip()
        if not text:
            self.clear_diagnostics_text()
            return
        self._diagnostics_label.setText(text)
        self._diagnostics_label.adjustSize()
        self._diagnostics_label.show()
        self._position_diagnostics_label()
        self._diagnostics_label.raise_()

    def clear_diagnostics_text(self) -> None:
        self._diagnostics_label.clear()
        self._diagnostics_label.hide()

    def current_surface(self) -> Optional[QtWidgets.QWidget]:
        return self._surface_widget

    def install_input_bridge(self, viewport_controller: Optional[QtCore.QObject]) -> None:
        self._input_bridge = viewport_controller
        self._bridge_installed = False
        surface = self._surface_widget
        if surface is None or viewport_controller is None:
            return
        try:
            surface.removeEventFilter(viewport_controller)
        except Exception:
            pass
        surface.installEventFilter(viewport_controller)
        self._bridge_installed = True

    def set_overlay_pixmap(self, pixmap: Optional[QtGui.QPixmap]) -> None:
        if pixmap is None or pixmap.isNull():
            self.clear_overlay()
            return
        self._overlay_label.setPixmap(pixmap)
        self._overlay_label.setText("")
        self._overlay_label.show()
        self._raise_overlay()

    def clear_overlay(self) -> None:
        self._overlay_label.clear()
        self._overlay_label.hide()

    def setPixmap(self, pixmap: QtGui.QPixmap) -> None:  # noqa: N802 - QLabel compatibility
        label = self._surface_label()
        if label is not None:
            label.setPixmap(pixmap)
            label.setText("")
            label.show()
        self.clear_overlay()

    def setText(self, text: str) -> None:  # noqa: N802 - QLabel compatibility
        label = self._surface_label()
        if label is not None:
            label.setText(text)
            label.setPixmap(QtGui.QPixmap())
            label.show()
        else:
            self._overlay_label.setText(text)
            self._overlay_label.show()

    def setAlignment(self, alignment: QtCore.Qt.AlignmentFlag) -> None:  # noqa: N802
        label = self._surface_label()
        if label is not None:
            label.setAlignment(alignment)
        self._overlay_label.setAlignment(alignment)

    def setScaledContents(self, enabled: bool) -> None:  # noqa: N802
        label = self._surface_label()
        if label is not None:
            label.setScaledContents(bool(enabled))
        self._overlay_label.setScaledContents(bool(enabled))

    def pixmap(self) -> Optional[QtGui.QPixmap]:
        label = self._surface_label()
        return label.pixmap() if label is not None else self._overlay_label.pixmap()

    def is_live_surface(self) -> bool:
        return self._surface_live

    def surface_backend_id(self) -> str:
        return self._surface_backend_id

    def overlay_layer_active(self) -> bool:
        return self._overlay_label.isVisible()

    def input_bridge_installed(self) -> bool:
        return self._bridge_installed

    def diagnostics(self) -> dict[str, object]:
        surface = self._surface_widget
        return {
            "current_surface_widget_class": type(surface).__name__ if surface is not None else "",
            "surface_size": (int(self.width()), int(self.height())),
            "device_pixel_ratio": float(self.devicePixelRatioF()),
            "input_bridge_installed": self._bridge_installed,
            "overlay_layer_active": self.overlay_layer_active(),
            "diagnostics_overlay_active": self._diagnostics_label.isVisible(),
            "live_surface": self._surface_live,
            "backend_id": self._surface_backend_id,
        }

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._raise_overlay()
        self._position_diagnostics_label()

    def _surface_label(self) -> Optional[QtWidgets.QLabel]:
        surface = self._surface_widget
        return surface if isinstance(surface, QtWidgets.QLabel) else None

    def _raise_overlay(self) -> None:
        if not self._overlay_has_content():
            self._overlay_label.hide()
        self._overlay_label.raise_()
        for child in self.findChildren(QtWidgets.QWidget, options=QtCore.Qt.FindDirectChildrenOnly):
            if child is not self._surface_widget and child is not self._overlay_label and child is not self._diagnostics_label:
                child.raise_()
        if self._diagnostics_label.isVisible():
            self._diagnostics_label.raise_()

    def _overlay_has_content(self) -> bool:
        pixmap = self._overlay_label.pixmap()
        return bool((pixmap is not None and not pixmap.isNull()) or self._overlay_label.text())

    def _position_diagnostics_label(self) -> None:
        if not self._diagnostics_label.isVisible():
            return
        margin = 10
        size = self._diagnostics_label.sizeHint()
        width = min(max(180, size.width()), max(180, min(460, self.width() - margin * 2)))
        height = min(max(22, size.height()), max(22, self.height() - margin * 2))
        self._diagnostics_label.setFixedSize(width, height)
        y = 64 if self._surface_live and self._overlay_label.isVisible() else margin
        self._diagnostics_label.move(margin, min(y, max(margin, self.height() - height - margin)))
