"""Qt normal-map / ZBrush pipeline panel for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading


class QtNormalMapPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("ZBrush to KotOR Pipeline"))

        self.low_label = QtWidgets.QLabel("Low-poly mesh: current model")
        root.addWidget(self.low_label)

        high_group = QtWidgets.QGroupBox("High-poly Source")
        high_group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        high_layout = QtWidgets.QHBoxLayout(high_group)
        self.high_path = QtWidgets.QLineEdit()
        self.high_path.setPlaceholderText("High-poly OBJ path")
        browse = QtWidgets.QPushButton("Browse")
        browse.clicked.connect(self._browse_high)
        high_layout.addWidget(self.high_path, 1)
        high_layout.addWidget(browse)
        root.addWidget(high_group)

        bake_group = QtWidgets.QGroupBox("Bake Settings")
        bake_group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        form = QtWidgets.QFormLayout(bake_group)
        self.res_combo = QtWidgets.QComboBox()
        self.res_combo.addItems(["512", "1024", "2048", "4096"])
        self.res_combo.setCurrentText("1024")
        self.bump_spin = QtWidgets.QDoubleSpinBox()
        self.bump_spin.setRange(0.0, 10.0)
        self.bump_spin.setSingleStep(0.1)
        self.bump_spin.setValue(1.0)
        self.output_path = QtWidgets.QLineEdit()
        self.output_path.setPlaceholderText("Output TGA/TPC path")
        form.addRow("Resolution:", self.res_combo)
        form.addRow("Bump Strength:", self.bump_spin)
        form.addRow("Output:", self.output_path)
        root.addWidget(bake_group)

        actions = QtWidgets.QHBoxLayout()
        for label in ("Bake Normal Map", "Convert TGA to TPC", "Open Output"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.set_status(f"{text} is pending Qt behavior wiring."))
            actions.addWidget(button)
        root.addLayout(actions)
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        root.addWidget(self.status_label)
        root.addStretch(1)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _browse_high(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select high-poly OBJ", "", "OBJ files (*.obj);;All files (*.*)")
        if path:
            self.high_path.setText(path)

