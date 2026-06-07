"""Small theme-friendly collapsible group boxes for tool panels."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class CollapsibleGroupBox(QtWidgets.QGroupBox):
    """QGroupBox with a top-right +/- expander."""

    TOGGLE_SIZE = 16

    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._collapsed = False
        self._expanded_min_height = 0
        self._expanded_max_height = 16777215
        self._toggle = QtWidgets.QToolButton(self)
        self._toggle.setObjectName("CollapsibleGroupToggle")
        self._toggle.setProperty("_gr_ignore_layout_button_mode", True)
        self._toggle.setProperty("collapsibleToggle", True)
        self._toggle.setText("-")
        self._toggle.setToolTip("Collapse section")
        self._toggle.setAutoRaise(True)
        self._toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self._toggle.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self._toggle.clicked.connect(self.toggle_collapsed)
        self._enforce_toggle_size()
        self._toggle.setStyleSheet(
            "QToolButton#CollapsibleGroupToggle {"
            "min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px;"
            "width: 16px; height: 16px;"
            "padding: 0px; margin: 0px;"
            "}"
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        layout = self.layout()
        if layout is not None:
            self._reserve_header_space(layout)
        self._enforce_toggle_size()
        self._toggle.move(max(0, self.width() - self._toggle.width() - 8), 3)

    def setLayout(self, layout: QtWidgets.QLayout) -> None:  # noqa: N802
        super().setLayout(layout)
        layout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self._reserve_header_space(layout)

    def _reserve_header_space(self, layout: QtWidgets.QLayout) -> None:
        left, top, right, bottom = layout.getContentsMargins()
        layout.setContentsMargins(left, max(top, 18), right, bottom)

    def setCollapsed(self, collapsed: bool) -> None:  # noqa: N802
        if not self._collapsed:
            self._expanded_min_height = self.minimumHeight()
            self._expanded_max_height = self.maximumHeight()
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
        header_height = self.collapsed_height()
        self.setMinimumHeight(header_height if self._collapsed else self._expanded_min_height)
        self.setMaximumHeight(header_height if self._collapsed else self._expanded_max_height)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed if self._collapsed else QtWidgets.QSizePolicy.Preferred)
        self.updateGeometry()

    def toggle_collapsed(self) -> None:
        self.setCollapsed(not self._collapsed)

    def collapsed_height(self) -> int:
        return 24

    def _enforce_toggle_size(self) -> None:
        size = self.TOGGLE_SIZE
        self._toggle.setFixedSize(size, size)
        self._toggle.setMinimumSize(size, size)
        self._toggle.setMaximumSize(size, size)

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
