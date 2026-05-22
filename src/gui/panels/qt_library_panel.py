"""Qt game library panel for the GhostRigger migration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from src.core.qt_core.modules.module_categories import get_module_info
from src.gui.qt_lib.assets.qt_theme import icon, heading


_ITEM_PREFIXES = (
    "w_", "iw_", "ia_", "g_w_", "g_i_", "g_a_", "g1_", "g2_", "g3_",
    "i_", "a_", "uti_", "plc_", "lbl_", "lbn_",
)


def infer_model_category(resref: str, model_class: str = "") -> str:
    """Return the library tab category for a model row."""
    r = (resref or "").lower()
    cls = (model_class or "").lower()
    if r.startswith("gr_"):
        return "Template"
    if cls == "tile":
        return "Module"
    if cls == "character":
        return "Creature" if r.startswith("c_") else "Character"
    if cls in {"item"}:
        return "Item/Armor/Weapons"
    if cls in {"door", "effect", "effects", "misc"}:
        return "Other"
    if r.startswith("c_"):
        return "Creature"
    if r.startswith(
        (
            "p_", "n_", "k_p_", "k_m_", "pmh", "pmb", "pmf", "pmc", "po_",
            "pfh", "pfb", "pff", "pfc", "s_male", "s_female", "s_human",
            "darkjedi", "malak", "bastila", "trask", "canderous", "revan",
            "jolee", "juhani", "carth", "mission", "zaalbar", "hk47", "g0t0",
            "t3m4", "kreia", "atton", "mical", "bao", "visas", "hanharr",
            "mandra", "darth",
        )
    ):
        return "Character"
    if _module_info_for_row(resref, "") is not None:
        return "Module"
    if any(r.startswith(prefix) for prefix in _ITEM_PREFIXES):
        return "Item/Armor/Weapons"
    if r.startswith(
        (
            "ad_", "ai_", "jo_", "bi_", "br_", "bo_", "do_", "dr_", "du_",
            "fr_", "ga_", "gi_", "go_", "gr_", "gu_", "ha_", "he_", "ho_",
            "hu_", "ja_", "je_", "ki_", "la_", "le_", "li_", "lo_", "ma_",
            "me_", "mi_", "mo_", "mu_", "ni_", "nu_", "or_", "pa_", "pi_",
            "qu_", "ra_", "ri_", "ro_", "sa_", "se_", "si_", "sk_", "sl_",
            "sm_", "so_", "sp_", "st_", "su_", "sw_", "ta_", "te_", "ti_",
            "tr_", "tu_", "ul_", "un_", "ur_", "va_", "vi_", "wa_", "wi_",
            "wo_", "ya_", "yo_", "za_", "ze_", "zo_", "zu_",
        )
    ):
        return "Character"
    return "Other"


def _module_info_for_row(resref: str, game: str = ""):
    games = [game] if str(game or "").upper() in {"K1", "K2"} else ["K1", "K2"]
    for game_key in games:
        info = get_module_info(resref, game_key)
        if info is not None:
            return info
    return None


def enrich_library_rows(rows: list[dict]) -> list[dict]:
    """Copy rows, add category/area fields, and append built-in templates."""
    enriched: list[dict] = []
    seen = set()
    for row in rows:
        item = dict(row)
        resref = str(item.get("resref", ""))
        game = str(item.get("game", ""))
        module_info = _module_info_for_row(resref, game)
        item.setdefault("category", "Module" if module_info is not None else infer_model_category(resref, str(item.get("model_class", ""))))
        if module_info is not None:
            item.setdefault("module_code", module_info.module_code)
            item.setdefault("location", module_info.location)
            item.setdefault("area_name", module_info.area_name)
            item.setdefault("area", module_info.location)
            item.setdefault("area_label", module_info.label)
            item.setdefault("location_type", module_info.location_type)
        enriched.append(item)
        seen.add((resref.lower(), game.upper()))

    for game in ("K1", "K2"):
        resref = f"gr_humanoid_{game.lower()}"
        if (resref, game) in seen:
            continue
        enriched.append(
            {
                "game": game,
                "resref": resref,
                "source": "[GhostRigger Built-in]",
                "category": "Template",
                "template": True,
            }
        )
    enriched.sort(key=lambda item: (str(item.get("game", "")), str(item.get("category", "")), str(item.get("resref", ""))))
    return enriched


class QtModelListItem(QtWidgets.QListWidgetItem):
    def __init__(self, row: dict):
        label = f"[{row.get('game', '?')}] {row.get('resref', '')}"
        if row.get("area_label"):
            label = f"{label} - {row.get('area_label')}"
        super().__init__(label)
        self.row = row


class QtLibraryPanel(QtWidgets.QWidget):
    loadRequested = QtCore.Signal(str, str)
    extractRequested = QtCore.Signal(dict)
    retargetSourceRequested = QtCore.Signal(dict)
    retargetTargetRequested = QtCore.Signal(dict)
    levelEditorImportRequested = QtCore.Signal(dict)
    batchRequested = QtCore.Signal(str, list)
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
        self.listbox.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.listbox.customContextMenuRequested.connect(self._show_context_menu)
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
        self.level_button = QtWidgets.QPushButton("Add to Level")
        self.load_button.clicked.connect(self.load_selected)
        self.extract_button.clicked.connect(self.extract_selected)
        self.level_button.clicked.connect(self.import_selected_to_level)
        action_row.addWidget(self.load_button, 1)
        action_row.addWidget(self.extract_button)
        action_row.addWidget(self.level_button)
        root.addLayout(action_row)

        batch_row = QtWidgets.QHBoxLayout()
        for label, fmt in (("Batch OBJ", "obj"), ("Batch ASCII", "ascii"), ("Batch TGA", "tga")):
            button = QtWidgets.QPushButton(label)
            button.setProperty("compact", True)
            button.clicked.connect(lambda _checked=False, f=fmt: self.batchRequested.emit(f, self.visible_rows()))
            batch_row.addWidget(button)
        batch_row.addStretch(1)
        root.addLayout(batch_row)

        scan_row = QtWidgets.QHBoxLayout()
        self.deep_button = QtWidgets.QPushButton("Deep Scan")
        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.setProperty("accent", True)
        self.deep_button.clicked.connect(self.deepScanRequested.emit)
        self.scan_button.clicked.connect(self.scanRequested.emit)
        scan_row.addStretch(1)
        for button in (self.deep_button, self.scan_button):
            button.setProperty("compact", True)
            scan_row.addWidget(button)
        root.addLayout(scan_row)

    def set_rows(self, rows: list[dict]) -> None:
        self._rows = enrich_library_rows(rows)
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

    def import_selected_to_level(self) -> None:
        row = self.selected_row()
        if row:
            self.levelEditorImportRequested.emit(row)

    def _load_item(self, item: QtWidgets.QListWidgetItem) -> None:
        row = getattr(item, "row", None)
        if row:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))

    def _show_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.listbox.itemAt(pos)
        if item is not None:
            self.listbox.setCurrentItem(item)
        row = self.selected_row()
        if not row:
            return
        menu = QtWidgets.QMenu(self)
        load_action = menu.addAction("Load Model")
        add_to_level_action = menu.addAction("Add to Level Editor")
        extract_action = menu.addAction("Extract")
        menu.addSeparator()
        source_action = menu.addAction("Send to Retarget Workbench (Source)")
        target_action = menu.addAction("Send to Retarget Workbench (Target)")
        chosen = menu.exec(self.listbox.mapToGlobal(pos))
        if chosen is load_action:
            self.loadRequested.emit(row.get("resref", ""), row.get("game", ""))
        elif chosen is add_to_level_action:
            self.levelEditorImportRequested.emit(row)
        elif chosen is extract_action:
            self.extractRequested.emit(row)
        elif chosen is source_action:
            self.retargetSourceRequested.emit(row)
        elif chosen is target_action:
            self.retargetTargetRequested.emit(row)

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
        area_filter = self.module_area_combo.currentText() if category == "Module" else "All Areas"

        self.listbox.clear()
        count = 0
        counts: dict[str, int] = {}
        for row in self._rows:
            row_cat = row.get("category") or infer_model_category(str(row.get("resref", "")))
            counts[row_cat] = counts.get(row_cat, 0) + 1

        for row in self._rows:
            text = " ".join(
                str(row.get(key, ""))
                for key in ("game", "resref", "module_code", "location", "area_name", "area_label")
            )
            if game_filter != "All" and row.get("game") != game_filter:
                continue
            row_cat = row.get("category") or infer_model_category(str(row.get("resref", "")))
            if category != "All" and row_cat != category:
                continue
            if category == "Module" and area_filter not in ("", "All Areas") and row.get("area_label") != area_filter:
                continue
            if needle and needle not in text.lower():
                continue
            self.listbox.addItem(QtModelListItem(row))
            count += 1
        if count == 0:
            self.listbox.addItem("No matching models")
        self.filter_count_label.setText(f"{count} shown")
        parts = [f"All: {len(self._rows)}"]
        for label, key, _icon_name in self.CATEGORIES[1:]:
            value = counts.get(key, 0)
            if value:
                parts.append(f"{label}: {value}")
        self.category_count_label.setText("  ".join(parts))

    def _rebuild_module_areas(self) -> None:
        current = self.module_area_combo.currentText()
        self.module_area_combo.clear()
        self.module_area_combo.addItem("All Areas")
        areas = sorted({str(row.get("area_label", "")) for row in self._rows if row.get("area_label")})
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
        parts = [str(row.get("resref", "")), str(row.get("game", ""))]
        if row.get("area_label"):
            parts.append(str(row.get("area_label")))
        if source:
            parts.append(source)
        self.thumb_label.setText("  ".join(part for part in parts if part))
