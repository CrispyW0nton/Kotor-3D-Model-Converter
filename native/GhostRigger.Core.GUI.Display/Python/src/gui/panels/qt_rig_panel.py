"""Qt rigging panel for GhostRigger."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import C, heading


class QtRigPanel(QtWidgets.QWidget):
    rigActionRequested = QtCore.Signal(str)
    SUPPORTED_ACTIONS = frozenset({
        "Auto-Rig Model",
        "Weight Stats",
        "Remove Rigging",
        "Clear Skeleton",
    })

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._model_available = False
        self._action_buttons: dict[str, list[QtWidgets.QPushButton]] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)
        root.addWidget(heading("Rigging"))

        guidance = QtWidgets.QLabel(
            "Rig the model currently loaded in the main viewport. Start with Auto-Rig, "
            "review Weight Stats, then save or export a copy. Remove Rigging and Clear "
            "Skeleton change the loaded model and ask for confirmation."
        )
        guidance.setObjectName("riggingWorkflowGuidance")
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        self.model_context_label = QtWidgets.QLabel("No model loaded — open or select a model in the main viewport.")
        self.model_context_label.setObjectName("riggingModelContextLabel")
        self.model_context_label.setWordWrap(True)
        root.addWidget(self.model_context_label)

        self.tabs = QtWidgets.QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_auto_tab()
        self._build_library_tab()
        self._build_grig_tab()
        self._build_manual_tab()
        self._build_accurig_tab()
        for index in range(1, self.tabs.count()):
            self.tabs.setTabText(index, f"{self.tabs.tabText(index)} (unavailable)")
            self.tabs.setTabEnabled(index, False)
            self.tabs.setTabToolTip(index, "This workflow is not available in the current build.")

        self.status_label = QtWidgets.QLabel("Load a model to enable the available rigging actions.")
        self.status_label.setStyleSheet(f"color:{C['text2']}; font-family:Consolas;")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self._refresh_action_states()

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
            action_id = "".join(
                char
                for char in "".join(part.title() for part in label.split())
                if char.isalnum()
            )
            button.setObjectName(f"rigAction{action_id}")
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            if label not in self.SUPPORTED_ACTIONS:
                button.setText(f"{label} (unavailable)")
            self._action_buttons.setdefault(label, []).append(button)
            layout.addWidget(button)

    def set_model_context(self, available: bool, name: str = "") -> None:
        """Expose which main-viewport model the panel will modify."""
        self._model_available = bool(available)
        if self._model_available:
            display_name = name.strip() or "Current viewport model"
            self.model_context_label.setText(f"Editing: {display_name}")
            self.status_label.setText("Choose Auto-Rig or inspect the current rig with Weight Stats.")
        else:
            self.model_context_label.setText("No model loaded — open or select a model in the main viewport.")
            self.status_label.setText("Load a model to enable the available rigging actions.")
        self._refresh_action_states()

    def _refresh_action_states(self) -> None:
        for action, buttons in self._action_buttons.items():
            supported = action in self.SUPPORTED_ACTIONS
            for button in buttons:
                button.setEnabled(supported and self._model_available)
                if supported:
                    button.setToolTip(
                        "Operates on the model currently loaded in the main viewport."
                        if self._model_available
                        else "Load a model in the main viewport first."
                    )
                else:
                    button.setToolTip("This action is not available in the current build.")

    def _emit_action(self, action: str) -> None:
        if action not in self.SUPPORTED_ACTIONS or not self._model_available:
            return
        self.status_label.setText(f"{action} requested.")
        self.rigActionRequested.emit(action)


class QtRigWindow(QtWidgets.QMainWindow):
    """Standalone host for the main-viewport rigging workflow."""

    rigActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Ghost-Studio Rigging")
        self.setWindowFlag(QtCore.Qt.Window, True)
        self.resize(640, 720)
        self.panel = QtRigPanel(self)
        self.panel.rigActionRequested.connect(self.rigActionRequested.emit)
        self.setCentralWidget(self.panel)

    @property
    def status_label(self) -> QtWidgets.QLabel:
        return self.panel.status_label


__all__ = ["QtRigPanel", "QtRigWindow"]
