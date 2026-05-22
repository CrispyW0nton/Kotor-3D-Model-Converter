"""Library-backed asset browser for the standalone Module Editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, infer_model_category


class ModuleEditorAssetItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict[str, Any]) -> None:
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "?")
        category = str(row.get("category") or infer_model_category(resref, str(row.get("model_class", ""))))
        label = f"[{game}] {category}  {resref}"
        if row.get("area_label"):
            label = f"{label} - {row.get('area_label')}"
        super().__init__(label)
        self.row = dict(row)


class ModuleEditorAssetBrowser(QtWidgets.QWidget):
    """Compact asset browser for adding game-library rows into KMAP scenes."""

    importRequested = QtCore.Signal(dict)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)

        filter_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Filter assets")
        self.search_edit.textChanged.connect(self._apply_filter)
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItems(["All", "Module", "Creature", "Character", "Item/Armor/Weapons", "Other", "Template"])
        self.category_combo.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.category_combo)
        root.addLayout(filter_row)

        self.listbox = QtWidgets.QListWidget()
        self.listbox.itemDoubleClicked.connect(lambda _item: self.import_selected())
        self.listbox.itemSelectionChanged.connect(self._update_detail)
        root.addWidget(self.listbox, 1)

        self.detail_label = QtWidgets.QLabel("Scan the main Game Library, then import assets here.")
        self.detail_label.setWordWrap(True)
        root.addWidget(self.detail_label)

        self.import_button = QtWidgets.QPushButton("Import Selected to Level")
        self.import_button.setProperty("accent", True)
        self.import_button.clicked.connect(self.import_selected)
        root.addWidget(self.import_button)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows = enrich_library_rows([dict(row) for row in rows])
        self._apply_filter()

    def selected_row(self) -> dict[str, Any] | None:
        item = self.listbox.currentItem()
        row = getattr(item, "row", None)
        return dict(row) if isinstance(row, dict) else None

    def import_selected(self) -> None:
        row = self.selected_row()
        if row:
            self.importRequested.emit(row)

    def _apply_filter(self) -> None:
        if not hasattr(self, "listbox"):
            return
        needle = self.search_edit.text().strip().lower()
        category = self.category_combo.currentText()
        self.listbox.clear()
        count = 0
        for row in self._rows:
            resref = str(row.get("resref") or "")
            row_category = str(row.get("category") or infer_model_category(resref, str(row.get("model_class", ""))))
            haystack = " ".join(str(row.get(key, "")) for key in ("game", "resref", "category", "area_label", "source")).lower()
            if category != "All" and row_category != category:
                continue
            if needle and needle not in haystack:
                continue
            self.listbox.addItem(ModuleEditorAssetItem(row))
            count += 1
        if count == 0:
            self.listbox.addItem("No library assets available")
        self.detail_label.setText(f"{count} asset(s) shown")

    def _update_detail(self) -> None:
        row = self.selected_row()
        if not row:
            return
        source = Path(str(row.get("source", ""))).name if row.get("source") else ""
        parts = [str(row.get("resref", "")), str(row.get("game", "")), str(row.get("category", ""))]
        if row.get("area_label"):
            parts.append(str(row.get("area_label")))
        if source:
            parts.append(source)
        self.detail_label.setText("  ".join(part for part in parts if part))
