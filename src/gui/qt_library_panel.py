"""Qt game library panel for the GhostRigger migration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from .qt_theme import icon, heading


class QtModelListItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict):
        super().__init__(f"[{row.get('game', '?')}] {row.get('resref', '')}")
        self.row = row


class QtLibraryPanel(QtWidgets.QWidget):
    loadRequested = QtCore.Signal(str, str)
    extractRequested = QtCore.Signal(dict)
    batchRequested = QtCore.Signal(str, list)
    autoDetectRequested = QtCore.Signal()
    dirsChanged = QtCore.Signal(str, str)
    scanRequested = QtCore.Signal()
    deepScanRequested = QtCore.Signal()

    CATEGORIES = [
        ("All", "All", "library"),
        ("Creature", "Creature", "cat_creature"),
        ("Character", "Character", "cat_character"),
        ("Item/Armor", "Item/Armor/Weapons", "cat_item"),
        ("Module", "Module", "cat_module"),
        ("Other", "Other", "cat_other"),
        ("Template", "Template", "skeleton"),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)
        root.addWidget(heading("Game Library"))

        dir_row = QtWidgets.QHBoxLayout()
        self.k1_button = QtWidgets.QPushButton("Set K1 Dir")
        self.k2_button = QtWidgets.QPushButton("Set K2 Dir")
        self.auto_button = QtWidgets.QPushButton("Auto-detect")
        self.deep_button = QtWidgets.QPushButton("Deep Scan")
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.setProperty("accent", True)
        self.k1_button.clicked.connect(lambda: self._choose_dir("K1"))
        self.k2_button.clicked.connect(lambda: self._choose_dir("K2"))
        self.auto_button.clicked.connect(self.autoDetectRequested.emit)
        self.deep_button.clicked.connect(self.deepScanRequested.emit)
        self.scan_button.clicked.connect(self.scanRequested.emit)
        for button in (self.k1_button, self.k2_button, self.auto_button):
            button.setProperty("compact", True)
            dir_row.addWidget(button)
        dir_row.addStretch(1)
        for button in (self.deep_button, self.scan_button):
            button.setProperty("compact", True)
            dir_row.addWidget(button)
        root.addLayout(dir_row)

        filter_row = QtWidgets.QHBoxLayout()
        self.game_filter = QtWidgets.QButtonGroup(self)
        for label in ("All", "K1", "K2"):
            rb = QtWidgets.QRadioButton(label)
            rb.setChecked(label == "All")
            rb.toggled.connect(self._apply_filter)
            self.game_filter.addButton(rb)
            filter_row.addWidget(rb)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        self.category_tabs = QtWidgets.QTabWidget()
        self.category_tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self.category_tabs.setUsesScrollButtons(True)
        self.category_tabs.setElideMode(QtCore.Qt.ElideRight)
        self.category_tabs.tabBar().setExpanding(False)
        for label, _key, icon_name in self.CATEGORIES:
            self.category_tabs.addTab(QtWidgets.QWidget(), icon(icon_name, 16), label)
        self.category_tabs.currentChanged.connect(self._apply_filter)
        root.addWidget(self.category_tabs, 0)

        self.module_area_combo = QtWidgets.QComboBox()
        self.module_area_combo.addItem("All Areas")
        self.module_area_combo.currentTextChanged.connect(self._apply_filter)
        root.addWidget(self.module_area_combo)
        self.module_area_combo.hide()

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter models")
        self.search_edit.textChanged.connect(self._apply_filter)
        clear = QtWidgets.QPushButton("x")
        clear.setProperty("compact", True)
        clear.clicked.connect(self.search_edit.clear)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(clear)
        root.addLayout(search_row)

        self.listbox = QtWidgets.QListWidget()
        self.listbox.itemDoubleClicked.connect(self._load_item)
        self.listbox.itemSelectionChanged.connect(self._update_selection_text)
        root.addWidget(self.listbox, 1)

        self.thumb_label = QtWidgets.QLabel("")
        self.thumb_label.setMinimumHeight(34)
        self.thumb_label.setWordWrap(True)
        root.addWidget(self.thumb_label)

        count_row = QtWidgets.QHBoxLayout()
        self.category_count_label = QtWidgets.QLabel("")
        self.filter_count_label = QtWidgets.QLabel("")
        count_row.addWidget(self.category_count_label)
        count_row.addStretch(1)
        count_row.addWidget(self.filter_count_label)
        root.addLayout(count_row)

        self.status_label = QtWidgets.QLabel("No game directory set")
        root.addWidget(self.status_label)

        action_row = QtWidgets.QHBoxLayout()
        self.load_button = QtWidgets.QPushButton("Load Model")
        self.load_button.setProperty("accent", True)
        self.extract_button = QtWidgets.QPushButton("Extract")
        self.load_button.clicked.connect(self.load_selected)
        self.extract_button.clicked.connect(self.extract_selected)
        action_row.addWidget(self.load_button, 1)
        action_row.addWidget(self.extract_button)
        root.addLayout(action_row)

        batch_row = QtWidgets.QHBoxLayout()
        for label, fmt in (("Batch OBJ", "obj"), ("Batch ASCII", "ascii"), ("Batch TGA", "tga")):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, f=fmt: self.batchRequested.emit(f, self.visible_rows()))
            batch_row.addWidget(button)
        batch_row.addStretch(1)
        root.addLayout(batch_row)

    def set_rows(self, rows: list[dict]) -> None:
        self._rows = rows
        self._rebuild_module_areas()
        self._apply_filter()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def selected_row(self) -> Optional[dict]:
        item = self.listbox.currentItem()
        return getattr(item, "row", None) if item else None

    def visible_rows(self) -> list[dict]:
        rows = []
        for index in range(self.listbox.count()):
            row = getattr(self.listbox.item(index), "row", None)
            if row:
                rows.append(row)
        return rows

    def load_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))

    def extract_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.extractRequested.emit(row)

    def _load_item(self, item: QtWidgets.QListWidgetItem) -> None:
        row = getattr(item, "row", None)
        if row:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))

    def _choose_dir(self, game: str) -> None:
        title = "Select KotOR 1 Game Directory" if game == "K1" else "Select KotOR 2 TSL Game Directory"
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title)
        if not path:
            return
        if game == "K1":
            self._k1_dir = path
            self._k2_dir = getattr(self, "_k2_dir", "")
        else:
            self._k1_dir = getattr(self, "_k1_dir", "")
            self._k2_dir = path
        self.dirsChanged.emit(getattr(self, "_k1_dir", ""), getattr(self, "_k2_dir", ""))

    def _current_game_filter(self) -> str:
        checked = self.game_filter.checkedButton()
        return checked.text() if checked else "All"

    def _current_category(self) -> str:
        idx = self.category_tabs.currentIndex()
        if 0 <= idx < len(self.CATEGORIES):
            return self.CATEGORIES[idx][1]
        return "All"

    def _apply_filter(self) -> None:
        if not hasattr(self, "listbox"):
            return
        category = self._current_category()
        self.module_area_combo.setVisible(category == "Module")
        game_filter = self._current_game_filter()
        needle = self.search_edit.text().lower().strip()

        self.listbox.clear()
        count = 0
        for row in self._rows:
            text = f"[{row.get('game', '?')}] {row.get('resref', '')}"
            if game_filter != "All" and row.get("game") != game_filter:
                continue
            row_cat = row.get("category", "All")
            if category != "All" and row_cat != category:
                continue
            if needle and needle not in text.lower():
                continue
            self.listbox.addItem(QtModelListItem(row))
            count += 1
        if count == 0:
            self.listbox.addItem("No matching models")
        self.filter_count_label.setText(f"{count} shown")
        self.category_count_label.setText(f"All: {len(self._rows)}")

    def _rebuild_module_areas(self) -> None:
        current = self.module_area_combo.currentText()
        self.module_area_combo.clear()
        self.module_area_combo.addItem("All Areas")
        areas = sorted({str(row.get("area", "")) for row in self._rows if row.get("area")})
        self.module_area_combo.addItems(areas)
        idx = self.module_area_combo.findText(current)
        if idx >= 0:
            self.module_area_combo.setCurrentIndex(idx)

    def _update_selection_text(self) -> None:
        row = self.selected_row()
        if not row:
            self.thumb_label.setText("")
            return
        source = Path(str(row.get("source", ""))).name if row.get("source") else ""
        self.thumb_label.setText(f"{row.get('resref', '')}  {row.get('game', '')}  {source}")
