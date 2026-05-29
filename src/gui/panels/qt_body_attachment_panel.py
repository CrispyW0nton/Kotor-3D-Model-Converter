"""Body Attachment System toolbox."""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.assets.qt_theme import heading


BAS_SLOT_LABELS: dict[str, str] = {
    "head": "HEAD",
    "body": "BODY",
    "left_hand": "L. HAND",
    "right_hand": "R. HAND",
    "left_weapon": "L. Weapon",
    "right_weapon": "R. Wep",
}

BAS_SLOT_POSITIONS: dict[str, tuple[int, int]] = {
    "head": (1, 1),
    "left_hand": (2, 0),
    "body": (2, 1),
    "right_hand": (2, 2),
    "left_weapon": (3, 0),
    "right_weapon": (3, 2),
}

BAS_PRESET_MODELS: dict[str, tuple[tuple[str, str], ...]] = {
    "head": (
        ("Player Male Head A 01", "pmha01"),
        ("Player Male Head C 01", "pmhc01"),
        ("Player Female Head A 01", "pfha01"),
        ("Player Female Head C 01", "pfhc01"),
    ),
    "left_weapon": (
        ("Vibroblade", "w_vbroswrd_001"),
        ("Short Sword", "w_vbroshort_001"),
        ("Lightsaber", "w_lghtsbr_001"),
    ),
    "right_weapon": (
        ("Blaster Pistol", "w_blstrpstl_001"),
        ("Blaster Rifle", "w_blstrrfl_001"),
        ("Lightsaber", "w_lghtsbr_001"),
    ),
}


class QtBodyAttachmentPanel(QtWidgets.QWidget):
    """Attach heads, hands, and weapons to the active body preview."""

    attachRequested = QtCore.Signal(str, str)
    clearRequested = QtCore.Signal(str)
    saveBuildRequested = QtCore.Signal()
    slotSelected = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._slot_buttons: dict[str, QtWidgets.QToolButton] = {}
        self._slot_models: dict[str, str] = {}
        self._selected_slot = "head"
        self._syncing_layer_selection = False
        self._build()
        self.set_selected_slot("head")

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Body Attachment System"))

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for row in range(5):
            for col in range(3):
                slot = next((key for key, pos in BAS_SLOT_POSITIONS.items() if pos == (row, col)), "")
                if slot:
                    button = QtWidgets.QToolButton()
                    button.setText(BAS_SLOT_LABELS[slot])
                    button.setCheckable(True)
                    button.setMinimumSize(88, 34)
                    button.clicked.connect(lambda _checked=False, key=slot: self.set_selected_slot(key))
                    self._slot_buttons[slot] = button
                    grid.addWidget(button, row, col)
                else:
                    filler = QtWidgets.QLabel("")
                    filler.setMinimumSize(88, 34)
                    grid.addWidget(filler, row, col)
        root.addLayout(grid)

        form = QtWidgets.QFormLayout()
        self.slot_label = QtWidgets.QLabel("")
        form.addRow("Slot", self.slot_label)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setEditable(True)
        form.addRow("Model", self.model_combo)
        root.addLayout(form)

        controls = QtWidgets.QHBoxLayout()
        self.attach_button = QtWidgets.QPushButton("Attach")
        self.attach_button.clicked.connect(self._emit_attach)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(lambda: self.clearRequested.emit(self._selected_slot))
        controls.addWidget(self.attach_button)
        controls.addWidget(self.clear_button)
        root.addLayout(controls)

        self.save_build_button = QtWidgets.QPushButton("Save Build")
        self.save_build_button.clicked.connect(self.saveBuildRequested.emit)
        root.addWidget(self.save_build_button)

        self.layer_tree = QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderLabels(["Layer", "Model", "State"])
        self.layer_tree.setRootIsDecorated(False)
        self.layer_tree.setAlternatingRowColors(True)
        self.layer_tree.setMaximumHeight(150)
        self.layer_tree.itemSelectionChanged.connect(self._handle_layer_selection_changed)
        root.addWidget(self.layer_tree)

        self.status = QtWidgets.QPlainTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(72)
        root.addWidget(self.status)
        root.addStretch(1)
        self._refresh_layers()

    def selected_slot(self) -> str:
        return self._selected_slot

    def selected_model_resref(self) -> str:
        text = str(self.model_combo.currentText() or "").strip()
        if text and text != str(self.model_combo.itemText(self.model_combo.currentIndex()) or "").strip():
            return text
        return str(self.model_combo.currentData() or text or "").strip()

    def set_selected_slot(self, slot: str) -> None:
        slot = slot if slot in BAS_SLOT_LABELS else "head"
        self._selected_slot = slot
        for key, button in self._slot_buttons.items():
            button.setChecked(key == slot)
        self.slot_label.setText(BAS_SLOT_LABELS[slot])
        self._populate_model_combo(slot)
        attachable = slot not in {"body", "left_hand", "right_hand"}
        self.model_combo.setEnabled(attachable)
        self.attach_button.setEnabled(attachable)
        self.clear_button.setEnabled(slot != "body" and attachable)
        self._sync_selected_layer()
        self.slotSelected.emit(slot)

    def set_body_model(self, model: Any) -> None:
        name = str(getattr(model, "name", "") or "BODY") if model is not None else "BODY"
        self._slot_models["body"] = name
        self._set_slot_text("body", name)

    def set_slot_model(self, slot: str, model: Any = None, *, resref: str = "") -> None:
        label = str(resref or getattr(model, "name", "") or BAS_SLOT_LABELS.get(slot, slot))
        self._slot_models[slot] = label
        self._set_slot_text(slot, label)

    def clear_slot_model(self, slot: str) -> None:
        self._slot_models.pop(slot, None)
        self._set_slot_text(slot, BAS_SLOT_LABELS.get(slot, slot))

    def set_status(self, message: str) -> None:
        self.status.setPlainText(str(message or ""))

    def _populate_model_combo(self, slot: str) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for label, value in BAS_PRESET_MODELS.get(slot, ()):
            self.model_combo.addItem(f"{label} - {value}", value)
        if self.model_combo.count() == 0:
            self.model_combo.addItem("", "")
        self.model_combo.blockSignals(False)

    def _emit_attach(self) -> None:
        if self._selected_slot in {"body", "left_hand", "right_hand"}:
            return
        self.attachRequested.emit(self._selected_slot, self.selected_model_resref())

    def _set_slot_text(self, slot: str, text: str) -> None:
        button = self._slot_buttons.get(slot)
        if button is None:
            return
        base = BAS_SLOT_LABELS.get(slot, slot)
        value = str(text or "").strip()
        button.setText(base if not value or value == base else f"{base}\n{value}")
        self._refresh_layers()

    def _refresh_layers(self) -> None:
        tree = getattr(self, "layer_tree", None)
        if tree is None:
            return
        order = ("body", "head", "left_hand", "right_hand", "left_weapon", "right_weapon")
        tree.blockSignals(True)
        tree.clear()
        for slot in order:
            model = str(self._slot_models.get(slot, "") or "").strip()
            if slot == "body":
                model = model or "BODY"
                state = "Base"
            elif slot in {"left_hand", "right_hand"}:
                state = "Socket"
            else:
                state = "Attached" if model else "Empty"
            item = QtWidgets.QTreeWidgetItem([BAS_SLOT_LABELS.get(slot, slot), model or "", state])
            item.setData(0, QtCore.Qt.UserRole, slot)
            if slot == "body":
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            tree.addTopLevelItem(item)
        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)
        tree.blockSignals(False)
        self._sync_selected_layer()

    def _sync_selected_layer(self) -> None:
        tree = getattr(self, "layer_tree", None)
        if tree is None:
            return
        self._syncing_layer_selection = True
        try:
            for index in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(index)
                if str(item.data(0, QtCore.Qt.UserRole) or "") == self._selected_slot:
                    tree.setCurrentItem(item)
                    break
        finally:
            self._syncing_layer_selection = False

    def _handle_layer_selection_changed(self) -> None:
        if self._syncing_layer_selection:
            return
        item = self.layer_tree.currentItem()
        slot = str(item.data(0, QtCore.Qt.UserRole) or "") if item is not None else ""
        if slot:
            self.set_selected_slot(slot)

    def layer_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        for index in range(self.layer_tree.topLevelItemCount()):
            item = self.layer_tree.topLevelItem(index)
            rows.append((item.text(0), item.text(1), item.text(2)))
        return rows
