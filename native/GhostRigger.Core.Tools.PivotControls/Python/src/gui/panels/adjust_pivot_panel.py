"""Dockable Adjust Pivot toolbox for scene-object pivot editing."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from src.gui.libtheme.collapsible_group import CollapsibleGroupBox


class AdjustPivotPanel(QtWidgets.QWidget):
    """Compact 3ds Max-inspired pivot editing toolbox."""

    pivotModeChanged = QtCore.Signal(str)
    pivotActionRequested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode_buttons: dict[str, QtWidgets.QToolButton] = {}
        self._action_buttons: dict[str, QtWidgets.QToolButton] = {}
        self._mode_group: QtWidgets.QButtonGroup | None = None
        self._selected_count = 0
        self._locked = False
        self._hierarchy_available = False
        self._build()
        self.set_selection_state(0, locked=False, hierarchy_available=False)

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        mode_box = CollapsibleGroupBox("Move/Rotate/Scale")
        mode_layout = QtWidgets.QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(8, 8, 8, 8)
        mode_layout.setSpacing(4)
        mode_specs = [
            ("affect_pivot_only", "Affect Pivot Only", "Move or rotate the selected object's pivot without moving the visible object."),
            ("affect_object_only", "Affect Object Only", "Move, rotate, or scale the object around its current pivot."),
            ("affect_hierarchy_only", "Affect Hierarchy Only", "Adjust hierarchy transform data where supported."),
        ]
        self._mode_group = QtWidgets.QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for key, text, tooltip in mode_specs:
            button = self._tool_button(text, tooltip, checkable=True)
            button.toggled.connect(lambda checked=False, mode=key: self._emit_pivot_mode_if_checked(mode, checked))
            self._mode_group.addButton(button)
            self._mode_buttons[key] = button
            mode_layout.addWidget(button)
        self._mode_buttons["affect_object_only"].setChecked(True)
        root.addWidget(mode_box)

        align_box = CollapsibleGroupBox("Alignment")
        align_grid = QtWidgets.QGridLayout(align_box)
        align_grid.setContentsMargins(8, 8, 8, 8)
        align_grid.setSpacing(4)
        align_specs = [
            ("center_to_object", "Center to Object", "Move the pivot to the selected object's bounding box centre."),
            ("align_to_object", "Align to Object", "Align the pivot orientation to the selected object."),
            ("align_to_world", "Align to World", "Align the pivot orientation to world axes."),
        ]
        for index, (key, text, tooltip) in enumerate(align_specs):
            button = self._tool_button(text, tooltip)
            button.clicked.connect(lambda _checked=False, action=key: self.pivotActionRequested.emit(action))
            self._action_buttons[key] = button
            align_grid.addWidget(button, index // 2, index % 2)
        root.addWidget(align_box)

        pivot_box = CollapsibleGroupBox("Pivot")
        pivot_layout = QtWidgets.QVBoxLayout(pivot_box)
        pivot_layout.setContentsMargins(8, 8, 8, 8)
        reset = self._tool_button("Reset Pivot", "Reset pivot position and orientation to the object default.")
        reset.clicked.connect(lambda _checked=False: self.pivotActionRequested.emit("reset_pivot"))
        self._action_buttons["reset_pivot"] = reset
        pivot_layout.addWidget(reset)
        root.addWidget(pivot_box)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addStretch(1)

    def _tool_button(self, text: str, tooltip: str, *, checkable: bool = False) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setProperty("_gr_full_text", text)
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        if checkable:
            button.setAutoRaise(False)
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _emit_pivot_mode_if_checked(self, mode: str, checked: bool) -> None:
        if checked:
            self.pivotModeChanged.emit(str(mode))

    def set_pivot_mode(self, mode: str) -> None:
        button = self._mode_buttons.get(str(mode))
        if button is not None:
            button.blockSignals(True)
            button.setChecked(True)
            button.blockSignals(False)

    def set_selection_state(self, selected_count: int, *, locked: bool = False, hierarchy_available: bool = False) -> None:
        self._selected_count = int(max(0, selected_count))
        self._locked = bool(locked)
        self._hierarchy_available = bool(hierarchy_available)
        has_selection = self._selected_count > 0
        enabled = has_selection and not self._locked
        for key, button in self._mode_buttons.items():
            button.setEnabled(enabled and (key != "affect_hierarchy_only" or self._hierarchy_available))
        for button in self._action_buttons.values():
            button.setEnabled(enabled)
        if not has_selection:
            self.status_label.setText("No object selected.")
        elif self._locked:
            self.status_label.setText("Selected object is locked.")
        elif not self._hierarchy_available:
            self.status_label.setText("Hierarchy mode is not available for this selection.")
        else:
            self.status_label.setText("")

    def apply_ghost_theme(self, theme) -> None:
        if theme is None:
            return
        self.status_label.setStyleSheet(f"color:{theme.color('text.secondary')};")

    def apply_ghost_layout(self, layout) -> None:
        margin = layout.spacing_value("margin", 4)
        spacing = layout.spacing_value("panelSpacing", 4)
        if self.layout() is not None:
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(spacing)
        button_height = max(22, layout.toolbar("viewport").height - 8)
        for button in [*self._mode_buttons.values(), *self._action_buttons.values()]:
            button.setMinimumHeight(button_height)
