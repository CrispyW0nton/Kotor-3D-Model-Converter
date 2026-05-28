"""Library-backed asset browser for the standalone Module Editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.panels.qt_library_panel import (
    MODEL_SUBCATEGORY_ORDER,
    enrich_library_rows,
    infer_model_category,
)


class ModuleEditorAssetItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict[str, Any]) -> None:
        resref = str(row.get("resref") or "")
        game = str(row.get("game") or "?")
        category = str(row.get("category") or infer_model_category(resref, str(row.get("model_class", ""))))
        subcategory = str(row.get("subcategory") or "")
        category_label = f"{category} / {subcategory}" if subcategory else category
        label = f"[{game}] {category_label}  {resref}"
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
        self.category_combo.addItems([
            "All",
            "Player Characters",
            *[
                f"Player Characters / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Player Characters"]
            ],
            "Party Members",
            *[
                f"Party Members / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Party Members"]
            ],
            "Commoners",
            *[
                f"Commoners / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Commoners"]
            ],
            "NPCs",
            *[
                f"NPCs / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["NPCs"]
            ],
            "Droids",
            *[
                f"Droids / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Droids"]
            ],
            "Turrets",
            *[
                f"Turrets / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Turrets"]
            ],
            "Creatures",
            *[
                f"Creatures / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Creatures"]
            ],
            "Holograms",
            *[
                f"Holograms / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Holograms"]
            ],
            "Supermodels",
            *[
                f"Supermodels / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Supermodels"]
            ],
            "Modules",
            *[
                f"Modules / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Modules"]
            ],
            "Level Assets",
            *[
                f"Level Assets / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Level Assets"]
            ],
            "Environment",
            *[
                f"Environment / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Environment"]
            ],
            "Skyboxes",
            *[
                f"Skyboxes / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Skyboxes"]
            ],
            "Minigame",
            *[
                f"Minigame / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Minigame"]
            ],
            "Menus",
            *[
                f"Menus / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Menus"]
            ],
            "GUI",
            *[
                f"GUI / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["GUI"]
            ],
            "Placeables",
            "Placeables / Containers",
            "Placeables / Computers & Panels",
            "Placeables / Doors & Transitions",
            "Placeables / Furniture",
            "Placeables / Lights & VFX",
            "Placeables / Traps & Hazards",
            "Placeables / Environmental Props",
            "Placeables / Misc Placeables",
            "Doors",
            "Doors / Taris",
            "Doors / Dantooine",
            "Doors / Tatooine",
            "Doors / Kashyyyk",
            "Doors / Manaan",
            "Doors / Korriban",
            "Doors / Leviathan",
            "Doors / Star Forge",
            "Doors / Rakata",
            "Doors / Yavin",
            "Doors / Endar Spire",
            "Doors / Ebon Hawk",
            "Doors / Peragus",
            "Doors / Telos",
            "Doors / Harbinger",
            "Doors / Nar Shaddaa",
            "Doors / Dxun",
            "Doors / Onderon",
            "Doors / Malachor",
            "Doors / Ravager",
            "Doors / Droid Planet",
            "Doors / Force Fields",
            "Doors / Generic Doors",
            "Doors / Unknown Doors",
            "Engine Items",
            *[
                f"Engine Items / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Engine Items"]
            ],
            "Armor",
            "Armor / Clothing",
            "Armor / Jedi Robes",
            "Armor / Light Armor",
            "Armor / Medium Armor",
            "Armor / Heavy Armor",
            "Armor / Environmental Suits",
            "Armor / Disguises",
            "Armor / Misc Armor",
            "Inventory",
            "Inventory / Security Spikes",
            "Inventory / Computer Spikes",
            "Inventory / Parts",
            "Inventory / Mines",
            "Inventory / Spikes",
            "Inventory / Traps",
            "Inventory / Medkits",
            "Inventory / Masks",
            "Inventory / Implants",
            "Inventory / Gauntlets",
            "Inventory / Armbands",
            "Inventory / Droid Items",
            "Inventory / Belts",
            "Inventory / Stims",
            "Inventory / Adrenal Stims",
            "Inventory / Combat Shots",
            "Inventory / Credits",
            "Inventory / Upgrades",
            "Inventory / Datapads",
            "Inventory / Pazaak",
            "Inventory / Quest Items",
            "Inventory / Misc Items",
            "Weapons",
            "Weapons / Grenades",
            "Weapons / Lightsabers",
            "Weapons / Double-Bladed Lightsabers",
            "Weapons / Short Lightsabers",
            "Weapons / Lightsaber Crystals",
            "Weapons / Vibroblades",
            "Weapons / Double-Bladed Melee",
            "Weapons / Blasters",
            "Weapons / Heavy Blasters",
            "Weapons / Blaster Rifles",
            "Weapons / Heavy Weapons",
            "Weapons / Creature Weapons",
            "Weapons / Single-Handed Melee",
            "Weapons / Two-Handed Weapons",
            "Weapons / Misc Weapons",
            "Item/Armor/Weapons",
            "Visual FX",
            *[
                f"Visual FX / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Visual FX"]
            ],
            "Visuals",
            *[
                f"Visuals / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Visuals"]
            ],
            "Planets",
            *[
                f"Planets / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Planets"]
            ],
            "Misc Models",
            *[
                f"Misc Models / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Misc Models"]
            ],
            "Stunts",
            *[
                f"Stunts / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Stunts"]
            ],
            "Uncategorised",
            "Other",
            "Templates",
            *[
                f"Templates / {subcategory}"
                for subcategory in MODEL_SUBCATEGORY_ORDER["Templates"]
            ],
        ])
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
            row_subcategory = str(row.get("subcategory") or "")
            row_category_path = f"{row_category} / {row_subcategory}" if row_subcategory else row_category
            haystack = " ".join(
                str(row.get(key, ""))
                for key in ("game", "resref", "category", "subcategory", "area_label", "source")
            ).lower()
            if category != "All" and row_category not in {category, category.split(" / ", 1)[0]}:
                continue
            if " / " in category and row_category_path != category:
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
        category = str(row.get("category", ""))
        subcategory = str(row.get("subcategory", ""))
        category_label = f"{category} / {subcategory}" if subcategory else category
        parts = [str(row.get("resref", "")), str(row.get("game", "")), category_label]
        if row.get("area_label"):
            parts.append(str(row.get("area_label")))
        if source:
            parts.append(source)
        self.detail_label.setText("  ".join(part for part in parts if part))
