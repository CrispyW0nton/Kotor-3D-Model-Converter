"""Compact 3ds Max-style transform type-in strip for the Qt viewport."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


def transform_bar_stylesheet() -> str:
    return """
    QFrame#TransformTypeInBar {
        background:#25272b;
        border-top:1px solid #3b3f46;
        border-bottom:1px solid #15171a;
    }
    QLabel#TransformModePill {
        color:#f0d58a;
        background:#303238;
        border:1px solid #555b65;
        border-radius:3px;
        padding:1px 7px;
        font-size:9pt;
        font-weight:600;
    }
    QLabel#TransformMiniLabel {
        color:#c4c9d1;
        font-size:8pt;
    }
    QLineEdit {
        background:#181a1e;
        color:#e6ebf2;
        border:1px solid #484d56;
        border-radius:2px;
        padding:1px 4px;
        selection-background-color:#315b88;
        font-size:9pt;
    }
    QLineEdit:disabled {
        background:#202226;
        color:#666d78;
        border-color:#333740;
    }
    QLineEdit:hover {
        border-color:#69717e;
    }
    QToolButton {
        background:#303238;
        color:#d9dee6;
        border:1px solid #555b65;
        border-radius:2px;
        padding:0;
        font-size:9pt;
        font-weight:600;
    }
    QToolButton:hover {
        background:#3a3d44;
        border-color:#767f8e;
    }
    QToolButton:checked {
        background:#4d3b18;
        color:#ffe39a;
        border-color:#c9952f;
    }
    QToolButton:disabled {
        background:#24262b;
        color:#686f7a;
        border-color:#383d45;
    }
    QComboBox {
        background:#181a1e;
        color:#e6ebf2;
        border:1px solid #484d56;
        border-radius:2px;
        padding:1px 17px 1px 5px;
        font-size:9pt;
    }
    QComboBox:hover {
        border-color:#69717e;
    }
    QComboBox::drop-down {
        border:0;
        width:15px;
    }
    QComboBox QAbstractItemView {
        background:#24272c;
        color:#d7dde6;
        selection-background-color:#4d3b18;
    }
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
        self.setFixedHeight(32)
        self.setStyleSheet(transform_bar_stylesheet())
        self._build()

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
        button.setFixedSize(24, 24)
        button.setToolTip(tooltip)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        return button

    def _combo(self, values: list[str], tooltip: str) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox()
        combo.setEditable(True)
        combo.addItems(values)
        combo.setFixedSize(58, 24)
        combo.setToolTip(tooltip)
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
