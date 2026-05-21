"""Small theme-friendly collapsible group boxes for tool panels."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class CollapsibleGroupBox(QtWidgets.QGroupBox):
    """QGroupBox with a top-right +/- expander."""

    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._collapsed = False
        self._toggle = QtWidgets.QToolButton(self)
        self._toggle.setText("-")
        self._toggle.setToolTip("Collapse section")
        self._toggle.setAutoRaise(True)
        self._toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self._toggle.clicked.connect(self.toggle_collapsed)
        self._toggle.setFixedSize(18, 18)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._toggle.move(max(0, self.width() - self._toggle.width() - 6), 2)

    def setCollapsed(self, collapsed: bool) -> None:  # noqa: N802
        self._collapsed = bool(collapsed)
        layout = self.layout()
        if layout is not None:
            for index in range(layout.count()):
                item = layout.itemAt(index)
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(not self._collapsed)
                child_layout = item.layout()
                if child_layout is not None:
                    self._set_layout_visible(child_layout, not self._collapsed)
        self._toggle.setText("+" if self._collapsed else "-")
        self._toggle.setToolTip("Expand section" if self._collapsed else "Collapse section")
        self.setMaximumHeight(30 if self._collapsed else 16777215)
        self.updateGeometry()

    def toggle_collapsed(self) -> None:
        self.setCollapsed(not self._collapsed)

    @staticmethod
    def _set_layout_visible(layout: QtWidgets.QLayout, visible: bool) -> None:
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(visible)
            child_layout = item.layout()
            if child_layout is not None:
                CollapsibleGroupBox._set_layout_visible(child_layout, visible)
