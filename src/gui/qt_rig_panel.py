"""Qt rigging panel for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import C, heading


class QtRigPanel(QtWidgets.QWidget):
    rigActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("Rigging"))

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_auto_tab()
        self._build_library_tab()
        self._build_grig_tab()
        self._build_manual_tab()
        self._build_accurig_tab()

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        root.addWidget(self.status_label)

    def _build_auto_tab(self) -> None:
        page = self._page()
        page.layout().addWidget(self._radio_group("Skeleton Template", ["Humanoid", "Creature", "Prop"]))
        page.layout().addWidget(self._slider_group("Height Override (0 = auto)", 0, 60, 0))
        page.layout().addWidget(self._slider_group("Heat Falloff", 10, 100, 40))
        self._add_action_buttons(page.layout(), [
            "Auto-Rig Model",
            "Map FBX Bones",
            "Weight Preview",
            "Weight Stats",
            "Remove Rigging",
            "Clear Skeleton",
        ])
        self.supermodel_combo = QtWidgets.QComboBox()
        self.supermodel_combo.addItems(["NULL", "k_sup_males", "k_sup_females", "k_sup_creatures", "s_female02", "s_male02"])
        page.layout().addWidget(QtWidgets.QLabel("Supermodel:"))
        page.layout().addWidget(self.supermodel_combo)
        page.layout().addStretch(1)
        self.tabs.addTab(page, "Auto")

    def _build_library_tab(self) -> None:
        page = self._page()
        page.layout().addWidget(QtWidgets.QLabel("Copy a bone hierarchy and skin-weight structure from a library model."))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Template model:"))
        self.template_edit = QtWidgets.QLineEdit("c_bantha")
        row.addWidget(self.template_edit, 1)
        page.layout().addLayout(row)
        quick = QtWidgets.QListWidget()
        quick.addItems(["c_bantha", "c_gammorean", "c_dewback", "c_ithorian", "c_rancor", "c_jawa", "c_drdastro"])
        quick.itemClicked.connect(lambda item: self.template_edit.setText(item.text()))
        page.layout().addWidget(quick, 1)
        self._add_action_buttons(page.layout(), ["Load Template", "Apply to Current Model"])
        self.scale_check = QtWidgets.QCheckBox("Scale bones to target model height")
        self.scale_check.setChecked(True)
        page.layout().addWidget(self.scale_check)
        self.template_info = QtWidgets.QPlainTextEdit("(No template loaded)")
        self.template_info.setReadOnly(True)
        page.layout().addWidget(self.template_info, 1)
        self.tabs.addTab(page, "Library")

    def _build_grig_tab(self) -> None:
        page = self._page()
        for title, buttons in (
            ("Profile Detection", ["Detect Profile", "Auto Place Pins"]),
            ("Bone Pins", ["Add Pin", "Lock Selected", "Delete Selected"]),
            ("Chain Builder", ["Build Arm Chain", "Build Leg Chain", "Mirror Chain"]),
            ("Weight Painting", ["Heat", "Sphere", "Flood", "Smooth", "Relax", "Erase"]),
            ("Template I/O", ["Save Template", "Load Template"]),
        ):
            page.layout().addWidget(self._button_group(title, buttons))
        page.layout().addStretch(1)
        self.tabs.addTab(page, "GRig")

    def _build_manual_tab(self) -> None:
        page = self._page()
        page.layout().addWidget(self._button_group("Manual Skeleton Editing", [
            "Add Bone",
            "Delete Bone",
            "Rename Bone",
            "Parent Bone",
            "Bake Bind Pose",
        ]))
        page.layout().addStretch(1)
        self.tabs.addTab(page, "Manual")

    def _build_accurig_tab(self) -> None:
        page = self._page()
        page.layout().addWidget(self._button_group("Guide-Based Rigging", [
            "Auto Place Guides",
            "Mirror Guides",
            "Build Skeleton",
            "Apply Weights",
            "Confirm Rig",
        ]))
        page.layout().addStretch(1)
        self.tabs.addTab(page, "AcuRig")

    def _page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        return page

    def _radio_group(self, title: str, labels: list[str]) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        row = QtWidgets.QHBoxLayout(group)
        self.template_group = QtWidgets.QButtonGroup(group)
        for i, label in enumerate(labels):
            rb = QtWidgets.QRadioButton(label)
            rb.setChecked(i == 0)
            self.template_group.addButton(rb)
            row.addWidget(rb)
        return group

    def _slider_group(self, title: str, minimum: int, maximum: int, value: int) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        layout = QtWidgets.QVBoxLayout(group)
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        layout.addWidget(slider)
        return group

    def _button_group(self, title: str, labels: list[str]) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox(title)
        group.setStyleSheet(f"QGroupBox {{ color:{C['gold']}; }}")
        layout = QtWidgets.QVBoxLayout(group)
        self._add_action_buttons(layout, labels)
        return group

    def _add_action_buttons(self, layout: QtWidgets.QBoxLayout, labels: list[str]) -> None:
        for label in labels:
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            layout.addWidget(button)

    def _emit_action(self, action: str) -> None:
        self.status_label.setText(f"{action} requested.")
        self.rigActionRequested.emit(action)

