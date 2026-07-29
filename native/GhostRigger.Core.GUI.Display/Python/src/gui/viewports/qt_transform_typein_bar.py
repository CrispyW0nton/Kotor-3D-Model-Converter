"""Compact 3ds Max-style transform type-in strip for the Qt viewport."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


def transform_bar_stylesheet(theme=None) -> str:
    if theme is None:
        c = {
            "bar_bg": "#25272b",
            "bar_border": "#3b3f46",
            "pill_bg": "#303238",
            "pill_text": "#f0d58a",
            "pill_border": "#555b65",
            "label": "#c4c9d1",
            "input_bg": "#181a1e",
            "input_text": "#e6ebf2",
            "input_border": "#484d56",
            "input_focus": "#69717e",
            "disabled_bg": "#202226",
            "disabled_text": "#666d78",
            "button_bg": "#303238",
            "button_text": "#d9dee6",
            "button_hover": "#3a3d44",
            "button_checked": "#4d3b18",
            "button_checked_text": "#ffe39a",
            "selection": "#315b88",
            "popup_bg": "#24272c",
        }
    else:
        c = {
            "bar_bg": theme.color("transformBar.background"),
            "bar_border": theme.color("transformBar.border"),
            "pill_bg": theme.color("button.checked"),
            "pill_text": theme.color("button.checkedText", theme.color("button.accentText")),
            "pill_border": theme.color("accent.primary"),
            "label": theme.color("text.secondary"),
            "input_bg": theme.color("input.background"),
            "input_text": theme.color("input.text"),
            "input_border": theme.color("input.border"),
            "input_focus": theme.color("input.focusBorder"),
            "disabled_bg": theme.color("button.disabledBackground"),
            "disabled_text": theme.color("button.disabledText", theme.color("text.disabled")),
            "button_bg": theme.color("button.background"),
            "button_text": theme.color("button.text"),
            "button_hover": theme.color("button.hover"),
            "button_checked": theme.color("button.checked"),
            "button_checked_text": theme.color("button.checkedText", theme.color("button.accentText")),
            "selection": theme.color("selection.background"),
            "popup_bg": theme.color("panel.backgroundAlt", theme.color("panel.altBackground")),
        }
    return f"""
    QFrame#TransformTypeInBar {{
        background:{c['bar_bg']};
        border-top:1px solid {c['bar_border']};
        border-bottom:1px solid {c['bar_border']};
    }}
    QLabel#TransformModePill {{
        color:{c['pill_text']};
        background:{c['pill_bg']};
        border:1px solid {c['pill_border']};
        border-radius:3px;
        padding:1px 7px;
        font-size:9pt;
        font-weight:600;
    }}
    QLabel#TransformMiniLabel {{
        color:{c['label']};
        font-size:8pt;
    }}
    QLineEdit {{
        background:{c['input_bg']};
        color:{c['input_text']};
        border:1px solid {c['input_border']};
        border-radius:2px;
        padding:1px 4px;
        selection-background-color:{c['selection']};
        font-size:9pt;
    }}
    QLineEdit:disabled {{
        background:{c['disabled_bg']};
        color:{c['disabled_text']};
        border-color:{c['bar_border']};
    }}
    QLineEdit:hover {{
        border-color:{c['input_focus']};
    }}
    QToolButton {{
        background:{c['button_bg']};
        color:{c['button_text']};
        border:1px solid {c['input_border']};
        border-radius:2px;
        padding:0;
        font-size:9pt;
        font-weight:600;
    }}
    QToolButton:hover {{
        background:{c['button_hover']};
        border-color:{c['input_focus']};
    }}
    QToolButton:checked {{
        background:{c['button_checked']};
        color:{c['button_checked_text']};
        border-color:{c['pill_border']};
    }}
    QToolButton:disabled {{
        background:{c['disabled_bg']};
        color:{c['disabled_text']};
        border-color:{c['bar_border']};
    }}
    QComboBox {{
        background:{c['input_bg']};
        color:{c['input_text']};
        border:1px solid {c['input_border']};
        border-radius:2px;
        padding:1px 17px 1px 5px;
        font-size:9pt;
    }}
    QComboBox:hover {{
        border-color:{c['input_focus']};
    }}
    QComboBox::drop-down {{
        border:0;
        width:15px;
    }}
    QComboBox QAbstractItemView {{
        background:{c['popup_bg']};
        color:{c['input_text']};
        selection-background-color:{c['selection']};
    }}
    """


class QtTransformTypeInBar(QtWidgets.QFrame):
    """Small status/tool strip for transform values and snap controls."""

    transformValueEdited = QtCore.Signal(str, str)
    gridEdited = QtCore.Signal(str)
    snapToggled = QtCore.Signal(bool)
    angleSnapToggled = QtCore.Signal(bool)
    angleIncrementChanged = QtCore.Signal(str)
    percentSnapToggled = QtCore.Signal(bool)
    percentIncrementChanged = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._suppress = False
        self.setObjectName("TransformTypeInBar")
        self.setFixedHeight(38)
        self.setAccessibleName("Transform and snapping controls")
        self.setAccessibleDescription(
            "Edit object transforms and grid spacing, or configure position, angle, and percent snapping."
        )
        self.setStyleSheet(transform_bar_stylesheet())
        self._build()

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(transform_bar_stylesheet(theme))

    def apply_ghost_layout(self, layout) -> None:
        height = layout.spacing_value("transformBarHeight", layout.spacing_value("inputHeight", 24) + 8)
        self.setFixedHeight(max(38, height))
        spacing = layout.spacing_value("toolbarSpacing", 4)
        if self.layout() is not None:
            self.layout().setContentsMargins(spacing + 1, 3, spacing + 1, 3)
            self.layout().setSpacing(max(1, spacing))
        control_h = max(32, layout.spacing_value("inputHeight", 24))
        for button in self.findChildren(QtWidgets.QToolButton):
            button.setFixedSize(control_h, control_h)
        for combo in self.findChildren(QtWidgets.QComboBox):
            combo.setFixedHeight(control_h)
        for edit in self.findChildren(QtWidgets.QLineEdit):
            edit.setFixedHeight(control_h)

    def _build(self) -> None:
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(5, 3, 5, 3)
        row.setSpacing(4)

        self.mode_label = QtWidgets.QLabel("MOVE")
        self.mode_label.setObjectName("TransformModePill")
        self.mode_label.setFixedWidth(56)
        self.mode_label.setAlignment(QtCore.Qt.AlignCenter)
        self.mode_label.setToolTip("Current transform mode")
        row.addWidget(self.mode_label)

        self.axis_edits: dict[str, QtWidgets.QLineEdit] = {}
        for axis in ("X", "Y", "Z"):
            label = QtWidgets.QLabel(f"{axis}:")
            label.setObjectName("TransformMiniLabel")
            row.addWidget(label)
            edit = QtWidgets.QLineEdit()
            edit.setFixedWidth(72)
            edit.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            edit.setToolTip(f"{axis} transform type-in")
            edit.setAccessibleName(f"{axis} transform value")
            edit.setAccessibleDescription(
                f"Enter the {axis} component of the active transform in the current reference coordinate system."
            )
            edit.editingFinished.connect(lambda axis_name=axis, field=edit: self._emit_axis(axis_name, field))
            self.axis_edits[axis] = edit
            row.addWidget(edit)

        grid_label = QtWidgets.QLabel("Grid:")
        grid_label.setObjectName("TransformMiniLabel")
        row.addWidget(grid_label)
        self.grid_edit = QtWidgets.QLineEdit()
        self.grid_edit.setFixedWidth(84)
        self.grid_edit.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.grid_edit.setToolTip("Grid spacing. Accepts values like 10 cm, 1 m, 2 ft.")
        self.grid_edit.setAccessibleName("Grid spacing")
        self.grid_edit.setAccessibleDescription(
            "Enter viewport grid spacing with an optional unit, such as 10 cm, 1 m, or 2 ft."
        )
        self.grid_edit.editingFinished.connect(self._emit_grid)
        row.addWidget(self.grid_edit)

        row.addSpacing(3)
        self.snap_button = self._tool_button("S", "Snap Toggle")
        self.snap_button.toggled.connect(lambda checked: self.snapToggled.emit(bool(checked)) if not self._suppress else None)
        row.addWidget(self.snap_button)

        self.angle_button = self._tool_button("A°", "Angle Snap Toggle")
        self.angle_button.toggled.connect(lambda checked: self.angleSnapToggled.emit(bool(checked)) if not self._suppress else None)
        row.addWidget(self.angle_button)
        self.angle_combo = self._combo(["1°", "2.5°", "5°", "10°", "15°", "30°", "45°", "90°"], "Angle snap increment")
        self.angle_combo.currentTextChanged.connect(lambda text: self.angleIncrementChanged.emit(text) if not self._suppress else None)
        row.addWidget(self.angle_combo)

        self.percent_button = self._tool_button("%", "Percent Snap Toggle")
        self.percent_button.toggled.connect(lambda checked: self.percentSnapToggled.emit(bool(checked)) if not self._suppress else None)
        row.addWidget(self.percent_button)
        self.percent_combo = self._combo(["1%", "2.5%", "5%", "10%", "25%", "50%", "100%"], "Percent snap increment")
        self.percent_combo.currentTextChanged.connect(lambda text: self.percentIncrementChanged.emit(text) if not self._suppress else None)
        row.addWidget(self.percent_combo)
        row.addStretch(1)

    def _tool_button(self, text: str, tooltip: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.setFixedSize(32, 32)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setAccessibleDescription(tooltip)
        button.setProperty("ghostFrequentAction", True)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _combo(self, values: list[str], tooltip: str) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setEditable(True)
        combo.addItems(values)
        combo.setFixedSize(68, 32)
        combo.setToolTip(tooltip)
        combo.setAccessibleName(tooltip)
        combo.setAccessibleDescription(f"Choose or type the {tooltip.lower()}.")
        combo.setProperty("ghostFrequentAction", True)
        return combo

    def set_transform_enabled(self, enabled: bool) -> None:
        for edit in self.axis_edits.values():
            edit.setEnabled(bool(enabled))

    def set_mode_label(self, text: str) -> None:
        self.mode_label.setText(str(text or "").upper()[:8])

    def set_transform_values(self, values: tuple[str, str, str]) -> None:
        self._suppress = True
        try:
            for axis, value in zip(("X", "Y", "Z"), values):
                self.axis_edits[axis].setText(str(value))
        finally:
            self._suppress = False

    def set_grid_text(self, text: str) -> None:
        self._suppress = True
        try:
            self.grid_edit.setText(str(text))
        finally:
            self._suppress = False

    def set_snap_state(self, *, snap: bool, angle: bool, percent: bool) -> None:
        self._suppress = True
        try:
            self.snap_button.setChecked(bool(snap))
            self.angle_button.setChecked(bool(angle))
            self.percent_button.setChecked(bool(percent))
        finally:
            self._suppress = False

    def set_increment_texts(self, *, angle: str, percent: str) -> None:
        self._suppress = True
        try:
            self.angle_combo.setCurrentText(str(angle))
            self.percent_combo.setCurrentText(str(percent))
        finally:
            self._suppress = False

    def _emit_axis(self, axis: str, field: QtWidgets.QLineEdit) -> None:
        if not self._suppress:
            self.transformValueEdited.emit(axis, field.text().strip())

    def _emit_grid(self) -> None:
        if not self._suppress:
            self.gridEdited.emit(self.grid_edit.text().strip())
