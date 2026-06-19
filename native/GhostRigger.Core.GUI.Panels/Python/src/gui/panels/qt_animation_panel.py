"""Qt animation panels for GhostRigger."""

from __future__ import annotations

import re
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

try:  # QtSvg is optional in a few headless/test installs.
    from PySide6 import QtSvg
except Exception:  # pragma: no cover - fallback only
    QtSvg = None  # type: ignore[assignment]

from src.core.retargeting.retarget_output_naming import KotorOutputAnimationNameMode
from src.gui.qt_lib.assets.qt_theme import C, heading


ANIMATION_NAME_ROLE = QtCore.Qt.UserRole
ANIMATION_SOURCE_ROLE = QtCore.Qt.UserRole + 1


_ANIMATION_SOURCE_OPTIONS = (
    ("B1", "body", "Body source"),
    ("F1", "head", "Face source"),
    ("I1", "attachment", "Item / weapon source"),
)

_SUPERMODEL_OPTIONS = (
    ("Auto - selected model chain", ""),
    ("K1 Female PC body - S_Female02", "S_Female02"),
    ("K1 Female PC extended - S_Female03", "S_Female03"),
    ("K1 Male PC body - S_Male02", "S_Male02"),
    ("K1 Male PC extended - S_Male03", "S_Male03"),
    ("Base Female Core - S_Female01", "S_Female01"),
    ("Base Male Core - S_Male01", "S_Male01"),
    ("Creature Bantha - C_BANTHA", "C_BANTHA"),
    ("Creature Rancor - C_RANCOR", "C_RANCOR"),
    ("Droid Wardroid - N_WARDROID", "N_WARDROID"),
)


_ANIMATION_EXACT_LABELS = {
    "active": "Active Idle",
    "default": "Default Pose",
    "pause": "Idle",
    "pause1": "Idle 1",
    "pause2": "Idle 2",
    "walk": "Walk",
    "walkinj": "Injured Walk",
    "walkback": "Walk Backward",
    "run": "Run",
    "runinj": "Injured Run",
    "ready": "Ready",
    "talk": "Talk",
    "listen": "Listen",
    "usecomp": "Use Computer",
    "unlock": "Unlock",
    "open": "Open",
    "close": "Close",
    "die": "Die",
    "dead": "Dead",
    "deadloop": "Dead Loop",
    "damage": "Damage Reaction",
    "dodge": "Dodge",
    "parry": "Parry",
    "taunt": "Taunt",
    "throw": "Throw",
    "cast": "Cast Force Power",
}

_ANIMATION_PREFIX_LABELS = (
    ("talk", "Talk"),
    ("listen", "Listen"),
    ("gesture", "Gesture"),
    ("walk", "Walk"),
    ("run", "Run"),
    ("dance", "Dance"),
    ("dead", "Dead"),
    ("die", "Die"),
    ("dodge", "Dodge"),
    ("parry", "Parry"),
    ("damage", "Damage Reaction"),
    ("throwgrenade", "Throw Grenade"),
    ("throw", "Throw"),
    ("cast", "Cast Force Power"),
)

_ANIMATION_FAMILY_LABELS = {
    "b": "Blaster",
    "c": "Combat",
    "f": "Fists",
    "g": "General Weapon",
    "m": "Melee",
}

_ANIMATION_ACTION_LABELS = {
    "a": "Attack",
    "c": "Critical Strike",
    "d": "Defend",
    "f": "Flurry",
    "g": "Get Hit",
    "n": "Block",
    "p": "Power Attack",
    "r": "Idle",
    "w": "Activate Weapon",
    "x": "Fall Through Air",
    "y": "Air-To-Ground Fall",
    "z": "Get Back Up",
}

_ANIMATION_SET_LABELS = {
    ("g", 1): "Single Hand Melee: Shortsword",
    ("g", 2): "Single Hand Melee: Lightsaber, Melee",
    ("g", 5): "Blaster Pistol",
    ("g", 6): "Dual Blasters",
    ("g", 7): "Blaster Rifles",
    ("g", 8): "Hand to Hand Combat",
    ("g", 9): "Assault Cannons",
    ("m", 2): "Vibroswords, Shortswords",
    ("c", 2): "Single Hand Melee: Vibrosword, Short Sword",
    ("b", 5): "Single Hand Blasters",
    ("b", 6): "Dual Blasters: L + R",
    ("b", 7): "Blaster Rifles: Both Hands",
    ("b", 8): "Assault Cannons: Both Hands",
    ("b", 9): "Assault Cannons: Both Hands",
}

_ANIMATION_GAME_SET_LABELS = {
    ("b", 8, "K2"): "",
    ("b", 9, "K1"): "",
}

_ANIMATION_CONTEXT_ACTION_LABELS = {
    ("g", 2, "r"): "Idle (On Guard Pose)",
    ("g", 2, "w"): "Activate Lightsaber",
}


def animation_display_name(anim_name: str, *, inherited: bool = False, source: str = "", game: str = "") -> str:
    """Return a readable label while preserving the raw KOTOR slot elsewhere."""
    raw = str(anim_name or "").strip()
    if not raw:
        return ""
    key = raw.lower()
    label = _animation_base_display_name(key, raw, game=game)
    if inherited:
        source = str(source or "").strip()
        label = f"{label} (Inherited" + (f" from {source}" if source else "") + ")"
    return label


def animation_row_label(anim_name: str, *, inherited: bool = False, source: str = "", game: str = "") -> str:
    raw = str(anim_name or "").strip()
    game_label = _animation_game_label(game)
    display = animation_display_name(raw, inherited=inherited, source=source, game=game_label)
    if raw:
        display = f"{display} [{raw}]"
    if game_label:
        display = f"{display} [{game_label}]"
    return display


def _animation_base_display_name(key: str, raw: str, *, game: str = "") -> str:
    if key in _ANIMATION_EXACT_LABELS:
        return _ANIMATION_EXACT_LABELS[key]
    match = re.fullmatch(r"pause(\d+)", key)
    if match:
        return f"Idle {int(match.group(1))}"
    match = re.fullmatch(r"animloop(\d+)", key)
    if match:
        return f"Ambient Loop {int(match.group(1)):02d}"
    match = re.fullmatch(r"([bcfgm])(\d+)([a-z])(\d*)([a-z]?)", key)
    if match:
        family_code, set_number, action_code, variant, form_code = match.groups()
        set_int = int(set_number)
        family = _ANIMATION_FAMILY_LABELS.get(family_code, f"Move Family {family_code.upper()}")
        set_label = _animation_set_context(family_code, set_int, game)
        action = _animation_action_label(family_code, set_int, action_code)
        suffix = f" {int(variant)}" if variant else ""
        form = f" Form {form_code.upper()}" if form_code else ""
        context = f" ({set_label})" if set_label else ""
        return f"{family} Set {set_int}{context} {action}{suffix}{form}"
    match = re.fullmatch(r"([a-z]+)(\d+)", key)
    if match:
        prefix, variant = match.groups()
        for token, label in _ANIMATION_PREFIX_LABELS:
            if prefix.startswith(token):
                return f"{label} {int(variant)}"
    return _humanize_animation_slot(raw)


def _animation_set_context(family_code: str, set_number: int, game: str = "") -> str:
    game_label = _animation_game_label(game)
    game_specific = _ANIMATION_GAME_SET_LABELS.get((family_code, set_number, game_label))
    if game_specific is not None:
        return game_specific
    return _ANIMATION_SET_LABELS.get((family_code, set_number), "")


def _animation_action_label(family_code: str, set_number: int, action_code: str) -> str:
    return _ANIMATION_CONTEXT_ACTION_LABELS.get(
        (family_code, set_number, action_code),
        _ANIMATION_ACTION_LABELS.get(action_code, f"Action {action_code.upper()}"),
    )


def _humanize_animation_slot(raw: str) -> str:
    text = raw.replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", text)
    text = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", text)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    words = [word for word in text.split() if word]
    return " ".join(word[:1].upper() + word[1:] for word in words) or raw


def _animation_game_label(game: str) -> str:
    text = str(game or "").strip().upper()
    if text in {"K1", "K2"}:
        return text
    if "KOTOR2" in text or "KOTOR 2" in text or "KOTOR II" in text:
        return "K2"
    if "KOTOR1" in text or "KOTOR 1" in text or "KOTOR" in text:
        return "K1"
    return ""


def _game_from_model(model) -> str:
    for attr in ("_gr_source_game", "game", "game_tag", "game_version"):
        value = getattr(model, attr, "")
        if hasattr(value, "value"):
            value = value.value
        label = _animation_game_label(str(value or ""))
        if label:
            return label
    return ""


class QtAnimationsPanel(QtWidgets.QWidget):
    animationSelected = QtCore.Signal(str)
    animationActionRequested = QtCore.Signal(str, str)
    animationSourceChanged = QtCore.Signal(str)
    inheritanceGameChanged = QtCore.Signal(str)
    inheritanceSupermodelChanged = QtCore.Signal(str)
    seekRequested = QtCore.Signal(int)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._source_buttons: dict[str, QtWidgets.QToolButton] = {}
        self._supermodel_buttons: dict[str, QtWidgets.QToolButton] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animation Browser"))
        source_row = QtWidgets.QHBoxLayout()
        source_row.addWidget(QtWidgets.QLabel("Source"))
        self.animation_source_combo = QtWidgets.QComboBox()
        self.animation_source_combo.setObjectName("AnimationBrowserSourceComboLegacy")
        self.animation_source_combo.hide()
        self.source_button_group = QtWidgets.QButtonGroup(self)
        self.source_button_group.setExclusive(True)
        for label, value, tooltip in _ANIMATION_SOURCE_OPTIONS:
            self.animation_source_combo.addItem(label, value)
            button = self._source_mode_button(label, value, tooltip)
            self.source_button_group.addButton(button)
            self._source_buttons[value] = button
            source_row.addWidget(button)
        self.source_button_group.buttonClicked.connect(lambda _button: self._sync_source_combo_from_buttons())
        self._source_buttons["body"].setChecked(True)
        self.animation_source_combo.setCurrentIndex(0)
        source_row.addStretch(1)
        root.addLayout(source_row)
        inheritance_row = QtWidgets.QHBoxLayout()
        inheritance_row.addWidget(QtWidgets.QLabel("Game"))
        self.inheritance_game_label = QtWidgets.QLabel("Auto")
        self.inheritance_game_label.setObjectName("AnimationBrowserGameLabel")
        self.inheritance_game_label.setToolTip("Animation inheritance game is detected from the selected model.")
        inheritance_row.addWidget(self.inheritance_game_label, 1)
        root.addLayout(inheritance_row)
        supermodel_row = QtWidgets.QHBoxLayout()
        supermodel_row.addWidget(QtWidgets.QLabel("Supermodel"))
        self.inheritance_supermodel_combo = QtWidgets.QComboBox()
        self.inheritance_supermodel_combo.setObjectName("AnimationBrowserSupermodelCombo")
        self.inheritance_supermodel_combo.setEditable(True)
        self.inheritance_supermodel_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        for label, value in _SUPERMODEL_OPTIONS:
            self.inheritance_supermodel_combo.addItem(label, value)
        self.inheritance_supermodel_combo.setToolTip(
            "Choose or type the exact root supermodel used for inherited animation lookup."
        )
        self.inheritance_supermodel_combo.currentTextChanged.connect(
            lambda _text: self.inheritanceSupermodelChanged.emit(self.selected_inheritance_supermodel())
        )
        supermodel_row.addWidget(self.inheritance_supermodel_combo, 1)
        root.addLayout(supermodel_row)
        supermodel_button_row = QtWidgets.QHBoxLayout()
        supermodel_button_row.addWidget(QtWidgets.QLabel("Sets"))
        self.supermodel_button_group = QtWidgets.QButtonGroup(self)
        self.supermodel_button_group.setExclusive(True)
        for label, value, tooltip in (
            ("Auto", "", "Use the selected model's authored supermodel chain"),
            ("B1", "S_Male01", "Body animation set 1"),
            ("B2", "S_Male02", "Body animation set 2"),
            ("B3", "S_Male03", "Body animation set 3"),
            ("F1", "S_Female01", "Face animation set 1"),
            ("F2", "S_Female02", "Face animation set 2"),
            ("F3", "S_Female03", "Face animation set 3"),
        ):
            button = self._source_mode_button(label, value or "auto", tooltip)
            self.supermodel_button_group.addButton(button)
            self._supermodel_buttons[value.lower()] = button
            supermodel_button_row.addWidget(button)
        self.supermodel_button_group.buttonClicked.connect(lambda _button: self._sync_supermodel_combo_from_buttons())
        self._sync_supermodel_buttons("")
        supermodel_button_row.addStretch(1)
        root.addLayout(supermodel_button_row)
        self.listbox = QtWidgets.QListWidget()
        self.listbox.currentItemChanged.connect(lambda item, _prev: self.animationSelected.emit(self._name_for_item(item)))
        self.listbox.itemDoubleClicked.connect(lambda _item: self._emit_action("Play"))
        root.addWidget(self.listbox, 1)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMaximumHeight(90)
        root.addWidget(self.info)
        self.seek = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.seek.setRange(0, 100)
        self.seek.valueChanged.connect(self.seekRequested.emit)
        root.addWidget(self.seek)
        controls = QtWidgets.QHBoxLayout()
        for label in ("Play", "Stop", "Loop", "Export"):
            button = self._action_button(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            controls.addWidget(button)
        root.addLayout(controls)
        output_controls = QtWidgets.QHBoxLayout()
        for label in ("Bake Animation", "Export Binary MDL"):
            button = self._action_button(label)
            button.clicked.connect(lambda _checked=False, text=label: self._emit_action(text))
            output_controls.addWidget(button)
        root.addLayout(output_controls)

    def load_model(self, model, select_name: str = "", game: str = "") -> None:
        self.listbox.clear()
        animations = getattr(model, "animations", []) or [] if model else []
        game = game or _game_from_model(model)
        self.set_inheritance_game(game, emit=False)
        for anim in animations:
            self._add_animation_item(getattr(anim, "name", str(anim)), anim=anim, game=game)
        if select_name:
            self.select_animation(select_name)
        self.info.setPlainText(f"{len(animations)} animation(s)" if model else "No animation source loaded.")

    def selected_animation(self) -> str:
        return self._name_for_item(self.listbox.currentItem())

    def selected_animation_source(self) -> str:
        if not hasattr(self, "animation_source_combo"):
            return "body"
        value = self.animation_source_combo.currentData()
        return str(value or "body")

    def set_animation_source(self, source: str) -> None:
        target = str(source or "body").strip().lower()
        previous = self.selected_animation_source()
        if target in self._source_buttons:
            self._source_buttons[target].setChecked(True)
        for index in range(self.animation_source_combo.count()):
            if str(self.animation_source_combo.itemData(index) or "").lower() == target:
                self.animation_source_combo.setCurrentIndex(index)
                if previous != target:
                    self.animationSourceChanged.emit(target)
                return
        self.animation_source_combo.setCurrentIndex(0)
        if "body" in self._source_buttons:
            self._source_buttons["body"].setChecked(True)
        if previous != "body":
            self.animationSourceChanged.emit("body")

    def selected_inheritance_game(self) -> str:
        if not hasattr(self, "inheritance_game_label"):
            return ""
        value = self.inheritance_game_label.text().strip().upper()
        return value if value in {"K1", "K2"} else ""

    def selected_inheritance_supermodel(self) -> str:
        if not hasattr(self, "inheritance_supermodel_combo"):
            return ""
        text = self.inheritance_supermodel_combo.currentText().strip()
        if text.lower().startswith("auto"):
            return ""
        text_key = text.lower()
        for index in range(self.inheritance_supermodel_combo.count()):
            label = self.inheritance_supermodel_combo.itemText(index).strip().lower()
            value = str(self.inheritance_supermodel_combo.itemData(index) or "").strip()
            if text_key == label and value:
                return value
            if text_key == value.lower():
                return value
        return text

    def set_inheritance_game(self, game: str, *, emit: bool = True) -> None:
        value = str(game or "").strip().upper()
        text = value if value in {"K1", "K2"} else "Auto"
        if hasattr(self, "inheritance_game_label") and self.inheritance_game_label.text() != text:
            self.inheritance_game_label.setText(text)
            if emit:
                self.inheritanceGameChanged.emit("" if text == "Auto" else text)

    def set_inheritance_supermodel(self, supermodel: str) -> None:
        value = str(supermodel or "").strip()
        target = value.lower()
        for index in range(self.inheritance_supermodel_combo.count()):
            item_value = str(self.inheritance_supermodel_combo.itemData(index) or "").lower()
            if item_value == target:
                self.inheritance_supermodel_combo.setCurrentIndex(index)
                self._sync_supermodel_buttons(value)
                return
        if value:
            self.inheritance_supermodel_combo.setEditText(value)
        else:
            self.inheritance_supermodel_combo.setCurrentIndex(0)
        self._sync_supermodel_buttons(value)

    def select_animation(self, anim_name: str) -> bool:
        if not anim_name:
            return False
        needle = str(anim_name)
        for index in range(self.listbox.count()):
            item = self.listbox.item(index)
            if self._name_for_item(item).lower() == needle.lower():
                self.listbox.setCurrentItem(item)
                self.listbox.scrollToItem(item)
                return True
        return False

    def add_effective_animation(self, entry: dict) -> bool:
        name = str(entry.get("name") or "")
        if not name:
            return False
        inherited = bool(entry.get("inherited"))
        source = str(entry.get("source") or "")
        game = str(entry.get("game") or "")
        self._add_animation_item(name, entry=entry, inherited=inherited, source=source, game=game)
        return True

    def _emit_action(self, action: str) -> None:
        self.animationActionRequested.emit(action, self.selected_animation())

    def _sync_source_combo_from_buttons(self) -> None:
        for value, button in self._source_buttons.items():
            if button.isChecked():
                for index in range(self.animation_source_combo.count()):
                    if str(self.animation_source_combo.itemData(index) or "") == value:
                        self.animation_source_combo.setCurrentIndex(index)
                        break
                self.animationSourceChanged.emit(value)
                return

    def _sync_supermodel_combo_from_buttons(self) -> None:
        for value, button in self._supermodel_buttons.items():
            if button.isChecked():
                self.set_inheritance_supermodel(value)
                self.inheritanceSupermodelChanged.emit(self.selected_inheritance_supermodel())
                return

    def _sync_supermodel_buttons(self, supermodel: str) -> None:
        target = str(supermodel or "").strip().lower()
        for value, button in self._supermodel_buttons.items():
            button.setChecked(value == target)

    def _source_mode_button(self, label: str, value: str, tooltip: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setObjectName(f"AnimationSource{value.title()}Button")
        button.setCheckable(True)
        button.setToolTip(tooltip)
        button.setIcon(_animation_source_svg_icon(label, 24))
        button.setIconSize(QtCore.QSize(24, 24))
        button.setAutoRaise(True)
        button.setFixedSize(34, 30)
        return button

    def _action_button(self, label: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setText(label)
        button.setToolTip(label)
        button.setIcon(_animation_source_svg_icon(_animation_action_icon_text(label), 22))
        button.setIconSize(QtCore.QSize(22, 22))
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        if label == "Loop":
            button.setCheckable(True)
        return button

    def _add_animation_item(
        self,
        anim_name: str,
        *,
        anim=None,
        entry: dict | None = None,
        inherited: bool = False,
        source: str = "",
        game: str = "",
    ) -> QtWidgets.QListWidgetItem:
        name = str(anim_name or "")
        item = QtWidgets.QListWidgetItem(animation_row_label(name, inherited=inherited, source=source, game=game))
        item.setIcon(_animation_source_svg_icon(_animation_slot_icon_text(name), 20))
        item.setData(ANIMATION_NAME_ROLE, name)
        item.setData(ANIMATION_SOURCE_ROLE, dict(entry or {}))
        if anim is not None:
            item.setData(ANIMATION_SOURCE_ROLE, {"animation": anim})
        tooltip = f"Animation slot: {name}"
        if inherited:
            tooltip += f"\nInherited from: {source or 'supermodel'}"
        item.setToolTip(tooltip)
        self.listbox.addItem(item)
        return item

    def _name_for_item(self, item: QtWidgets.QListWidgetItem | None) -> str:
        if item is None:
            return ""
        return str(item.data(ANIMATION_NAME_ROLE) or item.text() or "")


def _animation_source_svg_icon(label: str, size: int = 24) -> QtGui.QIcon:
    accent = str(C.get("accent", "#00ff99"))
    panel = str(C.get("panel2", "#101820"))
    text = str(C.get("text", "#ffffff"))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24">
<rect x="2" y="3" width="20" height="18" rx="4" fill="{panel}" stroke="{accent}" stroke-width="1.6"/>
<path d="M7 7h10M7 17h10" stroke="{accent}" stroke-width="1.2" stroke-linecap="round" opacity="0.65"/>
<text x="12" y="15" fill="{text}" font-family="Arial, sans-serif" font-size="8" font-weight="700" text-anchor="middle">{label}</text>
</svg>"""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    if QtSvg is not None:
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg.encode("utf-8")))
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter)
        painter.end()
    else:  # pragma: no cover - only used when QtSvg is unavailable
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QColor(accent))
        painter.drawRoundedRect(2, 3, 20, 18, 4, 4)
        painter.setPen(QtGui.QColor(text))
        painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, label)
        painter.end()
    return QtGui.QIcon(pixmap)


def _animation_action_icon_text(label: str) -> str:
    return {
        "Play": ">",
        "Stop": "[]",
        "Loop": "L",
        "Export": "EX",
        "Bake Animation": "BK",
        "Export Binary MDL": "MDL",
    }.get(label, label[:2].upper())


def _animation_slot_icon_text(anim_name: str) -> str:
    key = str(anim_name or "").strip().lower()
    if key.startswith(("cast", "force")):
        return "FP"
    match = re.fullmatch(r"([bcfgm])(\d+)([a-z])(\d*)([a-z]?)", key)
    if match:
        _family, set_number, action_code, _variant, _form = match.groups()
        action_icons = {
            "a": "AT",
            "c": "CS",
            "d": "DF",
            "f": "FL",
            "g": "HT",
            "n": "BL",
            "p": "PA",
            "r": "ID",
            "w": "ON",
        }
        return action_icons.get(action_code, f"S{set_number}")
    if key.startswith(("walk", "run")):
        return "MV"
    if key.startswith(("talk", "tlk", "listen")):
        return "VO"
    return "AN"


class QtAnimationLibraryPanel(QtWidgets.QWidget):
    libraryActionRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(heading("Animation Library"))
        scan = QtWidgets.QHBoxLayout()
        for label in ("Scan Animations", "Refresh"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            scan.addWidget(button)
        root.addLayout(scan)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("Filter animations")
        root.addWidget(self.filter_edit)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Model", "Animation", "Frames", "Source"])
        root.addWidget(self.tree, 1)
        actions = QtWidgets.QHBoxLayout()
        for label in ("Load", "Preview", "Export"):
            button = QtWidgets.QPushButton(label)
            button.clicked.connect(lambda _checked=False, text=label: self.libraryActionRequested.emit(text))
            actions.addWidget(button)
        root.addLayout(actions)

    def set_entries(self, entries: list[dict]) -> None:
        self.tree.clear()
        for entry in entries:
            item = QtWidgets.QTreeWidgetItem([
                str(entry.get("model", "")),
                self._animation_tree_label(entry),
                str(entry.get("frames", "")),
                str(entry.get("source", "")),
            ])
            item.setData(0, QtCore.Qt.UserRole, entry)
            self.tree.addTopLevelItem(item)

    def selected_entry(self) -> Optional[dict]:
        item = self.tree.currentItem()
        return item.data(0, QtCore.Qt.UserRole) if item else None

    def _animation_tree_label(self, entry: dict) -> str:
        name = str(entry.get("animation", ""))
        return animation_row_label(
            name,
            inherited=bool(entry.get("inherited")),
            source=str(entry.get("source", "")),
            game=str(entry.get("game", "")),
        )


class QtAnimationLibraryCombinedPanel(QtWidgets.QWidget):
    """Combined right-pane host for current-model animations and the library."""

    def __init__(
        self,
        animations_panel: QtAnimationsPanel,
        library_panel: QtAnimationLibraryPanel,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.animations_panel = animations_panel
        self.library_panel = library_panel
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.animations_panel, "Current")
        self.tabs.addTab(self.library_panel, "Library")
        root.addWidget(self.tabs, 1)

    def show_current_model_tab(self) -> None:
        self.tabs.setCurrentWidget(self.animations_panel)

    def show_library_tab(self) -> None:
        self.tabs.setCurrentWidget(self.library_panel)


class QtAnimationRetargetPanel(QtWidgets.QWidget):
    sourceCurrentRequested = QtCore.Signal()
    targetCurrentRequested = QtCore.Signal()
    sourceLibraryRequested = QtCore.Signal()
    targetLibraryRequested = QtCore.Signal()
    sourceGameLibraryRequested = QtCore.Signal(dict)
    targetGameLibraryRequested = QtCore.Signal(dict)
    sourceExternalImportRequested = QtCore.Signal()
    targetExternalImportRequested = QtCore.Signal()
    previewRequested = QtCore.Signal(str)
    applyRequested = QtCore.Signal(str)
    pauseRequested = QtCore.Signal()
    stopRequested = QtCore.Signal()
    animationSelected = QtCore.Signal(str)
    animationPreviewRequested = QtCore.Signal(str, bool)
    animationPauseRequested = QtCore.Signal()
    animationStopPreviewRequested = QtCore.Signal()
    sourceAnimationPlayRequested = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._source_model = None
        self._target_model = None
        self._library_rows: list[dict] = []
        self._animation_assignments: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.source_box = self._make_model_box("Source")
        self.target_box = self._make_model_box("Target")
        self.animation_section = self._make_animation_column()
        self.info_section = self._make_information_section()
        self.transfer_section = self._make_transfer_section()
        self.assignment_section = self._make_assignment_column()

        content = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.addWidget(self.animation_section)
        content.addWidget(self.assignment_section)
        content.setSizes([320, 520])
        root.addWidget(content, 1)

        self.controls_widget = self._make_controls_widget()
        root.addWidget(self.controls_widget)

    def _make_controls_widget(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)
        for label, slot in (
            ("Play", self._play_source_animation),
            ("Pause", self.pauseRequested.emit),
            ("Stop", self.stopRequested.emit),
            ("Retarget", self._preview),
            ("Export MDL and Assign Retargeted Animations", self._apply),
        ):
            button = QtWidgets.QPushButton(label)
            if label == "Retarget":
                button.setObjectName("retargetSelectedAnimationButton")
            elif label == "Play":
                button.setObjectName("playSelectedRetargetAnimationButton")
            elif label == "Pause":
                button.setObjectName("pauseRetargetAnimationButton")
            elif label == "Stop":
                button.setObjectName("stopRetargetAnimationButton")
            elif label.startswith("Export MDL"):
                button.setObjectName("exportAssignedRetargetAnimationsButton")
            button.clicked.connect(slot)
            controls.addWidget(button, 1)
        widget.setLayout(controls)
        return widget

    def _make_animation_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(heading("Animations"))
        self.anim_list = QtWidgets.QListWidget()
        self.anim_list.currentItemChanged.connect(
            lambda item, _old=None: self._on_animation_selected(self._source_name_for_item(item))
        )
        self.anim_list.itemDoubleClicked.connect(lambda _item: self._play_source_animation())
        self.anim_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_animation_context_menu)
        layout.addWidget(self.anim_list, 1)

        playback = QtWidgets.QWidget(column)
        playback.setObjectName("RetargetAnimationPlaybackControls")
        playback_layout = QtWidgets.QHBoxLayout(playback)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(4)
        self.animation_preview_button = QtWidgets.QPushButton("Play", playback)
        self.animation_preview_button.setObjectName("previewSourceAnimationButton")
        self.animation_pause_button = QtWidgets.QPushButton("Pause", playback)
        self.animation_pause_button.setObjectName("pauseSourceAnimationButton")
        self.animation_stop_button = QtWidgets.QPushButton("Stop", playback)
        self.animation_stop_button.setObjectName("stopSourceAnimationButton")
        self.animation_loop_checkbox = QtWidgets.QCheckBox("Loop", playback)
        self.animation_loop_checkbox.setObjectName("loopSourceAnimationCheckBox")
        self.animation_loop_checkbox.setChecked(True)
        self.animation_preview_button.clicked.connect(self._preview_source_animation)
        self.animation_pause_button.clicked.connect(self.animationPauseRequested.emit)
        self.animation_stop_button.clicked.connect(self.animationStopPreviewRequested.emit)
        playback_layout.addWidget(self.animation_preview_button, 1)
        playback_layout.addWidget(self.animation_pause_button, 1)
        playback_layout.addWidget(self.animation_stop_button, 1)
        playback_layout.addWidget(self.animation_loop_checkbox, 0)
        layout.addWidget(playback, 0)
        self._update_animation_playback_controls()
        return column

    def _make_assignment_column(self) -> QtWidgets.QWidget:
        column = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.info_section, 1)
        layout.addWidget(self.transfer_section, 0)
        return column

    def _make_information_section(self) -> QtWidgets.QWidget:
        info_box = QtWidgets.QGroupBox("Information")
        info_layout = QtWidgets.QVBoxLayout(info_box)
        info_layout.setContentsMargins(6, 6, 6, 6)
        self.info = QtWidgets.QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumHeight(82)
        info_layout.addWidget(self.info)
        return info_box

    def _make_transfer_section(self) -> QtWidgets.QWidget:
        options = QtWidgets.QGroupBox("Transfer")
        opt_layout = QtWidgets.QVBoxLayout(options)
        opt_layout.setContentsMargins(6, 6, 6, 6)
        self.preserve_scale = QtWidgets.QCheckBox("Preserve target size")
        self.preserve_scale.setChecked(True)
        self.ignore_scale = QtWidgets.QCheckBox("Ignore scale keys")
        self.ignore_scale.setChecked(True)
        self.material_keys = QtWidgets.QCheckBox("Copy material animation")
        self.material_keys.setChecked(True)
        for box in (self.preserve_scale, self.ignore_scale, self.material_keys):
            opt_layout.addWidget(box)
        opt_layout.addStretch(1)
        return options

    def _make_model_box(self, title: str) -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        label = QtWidgets.QLabel("None")
        label.setWordWrap(True)
        library_combo = QtWidgets.QComboBox()
        library_combo.setEditable(True)
        library_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        library_combo.setMinimumWidth(240)
        library_combo.setPlaceholderText(f"Search {title.lower()} game-library model")
        library_combo.lineEdit().setPlaceholderText(f"Search {title.lower()} game-library model")
        completer = QtWidgets.QCompleter(library_combo.model(), library_combo)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        library_combo.setCompleter(completer)
        button_row = QtWidgets.QHBoxLayout()
        current_button = QtWidgets.QPushButton("Use Current")
        library_button = QtWidgets.QPushButton("Load from Game Library")
        external_button = QtWidgets.QPushButton("Import External File...")
        if title == "Source":
            self.source_label = label
            self.source_library_combo = library_combo
            current_button.clicked.connect(self.sourceCurrentRequested.emit)
            library_button.clicked.connect(lambda _checked=False: self._emit_or_request_library_row("source"))
            external_button.clicked.connect(self.sourceExternalImportRequested.emit)
            library_combo.activated.connect(lambda _index=0: self._emit_library_row("source"))
        else:
            self.target_label = label
            self.target_library_combo = library_combo
            current_button.clicked.connect(self.targetCurrentRequested.emit)
            library_button.clicked.connect(lambda _checked=False: self._emit_or_request_library_row("target"))
            external_button.clicked.connect(self.targetExternalImportRequested.emit)
            library_combo.activated.connect(lambda _index=0: self._emit_library_row("target"))
        button_row.addWidget(current_button, 1)
        button_row.addWidget(library_button, 1)
        button_row.addWidget(external_button, 1)
        layout.addWidget(label)
        layout.addWidget(library_combo)
        layout.addLayout(button_row)
        return box

    def set_library_rows(self, rows: list[dict]) -> None:
        self._library_rows = [dict(row) for row in rows or []]
        for combo in (getattr(self, "source_library_combo", None), getattr(self, "target_library_combo", None)):
            if combo is not None:
                self._populate_library_combo(combo)

    def selected_library_row(self, role: str) -> Optional[dict]:
        combo = self.source_library_combo if role == "source" else self.target_library_combo
        row = combo.currentData()
        if isinstance(row, dict):
            return dict(row)
        text = combo.currentText().strip().lower()
        if not text:
            return None
        for candidate in self._library_rows:
            if text in self._library_row_label(candidate).lower():
                return dict(candidate)
        return None

    def _populate_library_combo(self, combo: QtWidgets.QComboBox) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem("Search game library...", None)
            for row in self._library_rows:
                combo.addItem(self._library_row_label(row), dict(row))
            if current:
                combo.setCurrentText(current)
        finally:
            combo.blockSignals(False)

    def _emit_library_row(self, role: str) -> None:
        row = self.selected_library_row(role)
        if not row:
            return
        if role == "source":
            self.sourceGameLibraryRequested.emit(row)
        else:
            self.targetGameLibraryRequested.emit(row)

    def _emit_or_request_library_row(self, role: str) -> None:
        row = self.selected_library_row(role)
        if row:
            if role == "source":
                self.sourceGameLibraryRequested.emit(row)
            else:
                self.targetGameLibraryRequested.emit(row)
            return
        if role == "source":
            self.sourceLibraryRequested.emit()
        else:
            self.targetLibraryRequested.emit()

    def _library_row_label(self, row: dict) -> str:
        game = str(row.get("game") or "").strip()
        resref = str(row.get("resref") or row.get("name") or "").strip()
        category = str(row.get("category") or "").strip()
        module = str(row.get("module_code") or row.get("area_label") or "").strip()
        pieces = [piece for piece in (game, resref, category, module) if piece]
        return " : ".join(pieces) if pieces else "(unnamed model)"

    def set_source_model(self, model) -> None:
        self._source_model = model
        self.source_label.setText(self._model_label(model))
        previous_assignments = {str(key): dict(value) for key, value in self._animation_assignments.items()}
        self.anim_list.clear()
        self._animation_assignments.clear()
        for anim in getattr(model, "animations", []) or [] if model else []:
            source_name = str(getattr(anim, "name", anim))
            item = QtWidgets.QListWidgetItem()
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            length = float(getattr(anim, "length", 0.0) or 0.0)
            item.setData(QtCore.Qt.UserRole, anim)
            item.setData(QtCore.Qt.UserRole + 2, source_name)
            assignment = previous_assignments.get(source_name) or self._default_assignment_for(source_name)
            item.setData(QtCore.Qt.UserRole + 1, assignment)
            self._animation_assignments[source_name] = dict(assignment)
            self._render_animation_item(item, length=length)
            self.anim_list.addItem(item)
        if self.anim_list.count() == 1:
            self.anim_list.setCurrentRow(0)
        self._update_animation_playback_controls()
        self._update_info()

    def set_target_model(self, model) -> None:
        self._target_model = model
        self.target_label.setText(self._model_label(model))
        self._update_info()

    def set_mapping_report(self, report) -> None:
        self.info.setPlainText(
            f"Mapped bones: {getattr(report, 'matched_count', 0)}\n"
            f"Exact: {getattr(report, 'exact_matches', 0)}  Alias: {getattr(report, 'alias_matches', 0)}  "
            f"Manual: {getattr(report, 'manual_matches', 0)}\n"
            f"Unmapped source: {len(getattr(report, 'missing_source', []) or [])}\n"
            f"Unmapped target: {len(getattr(report, 'missing_target', []) or [])}"
        )

    def selected_animation(self) -> str:
        item = self.anim_list.currentItem()
        return self._source_name_for_item(item)

    def _on_animation_selected(self, anim_name: str) -> None:
        self.animationSelected.emit(anim_name)
        self._update_animation_playback_controls()

    def _preview_source_animation(self) -> None:
        anim_name = self.selected_animation()
        if not anim_name:
            return
        self.animationPreviewRequested.emit(anim_name, self.animation_loop_checkbox.isChecked())

    def _update_animation_playback_controls(self) -> None:
        has_animation = bool(self.selected_animation())
        for button in (
            getattr(self, "animation_preview_button", None),
            getattr(self, "animation_pause_button", None),
            getattr(self, "animation_stop_button", None),
        ):
            if button is not None:
                button.setEnabled(has_animation)

    def select_animation(self, anim_name: str) -> bool:
        if not anim_name:
            return False
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if self._source_name_for_item(item) == str(anim_name):
                self.anim_list.setCurrentItem(item)
                self.anim_list.scrollToItem(item)
                return True
        return False

    def config_kwargs(self) -> dict:
        return {
            "preserve_model_scale": self.preserve_scale.isChecked(),
            "ignore_scale_keys": self.ignore_scale.isChecked(),
            "copy_material_animation": self.material_keys.isChecked(),
        }

    def manual_bone_mapping(self) -> dict[str, str]:
        return {}

    def assignment_for_animation(self, anim_name: str | None = None) -> dict:
        item = self._item_for_animation(anim_name or self.selected_animation())
        if item is None:
            return {}
        source_name = self._source_name_for_item(item)
        assignment = item.data(QtCore.Qt.UserRole + 1)
        if not isinstance(assignment, dict):
            assignment = self._default_assignment_for(source_name)
            item.setData(QtCore.Qt.UserRole + 1, assignment)
        result = dict(assignment)
        result.setdefault("source_animation", source_name)
        result["checked"] = item.checkState() == QtCore.Qt.Checked
        return result

    def checked_animation_assignments(self) -> list[dict]:
        assignments: list[dict] = []
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                assignments.append(self.assignment_for_animation(self._source_name_for_item(item)))
        return assignments

    def set_animation_assignment(
        self,
        anim_name: str,
        *,
        output_name: str | None = None,
        output_mode: KotorOutputAnimationNameMode | str | None = None,
        checked: bool | None = None,
    ) -> None:
        item = self._item_for_animation(anim_name)
        if item is None:
            return
        source_name = self._source_name_for_item(item)
        assignment = self.assignment_for_animation(source_name) or self._default_assignment_for(source_name)
        if output_name is not None:
            assignment["output_name"] = str(output_name or "").strip()
        if output_mode is not None:
            assignment["output_mode"] = self._coerce_output_mode(output_mode).value
        if checked is not None:
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        item.setData(QtCore.Qt.UserRole + 1, dict(assignment))
        self._animation_assignments[source_name] = dict(assignment)
        self._render_animation_item(item)

    def _bone_names(self, model) -> list[str]:
        if model is None or not hasattr(model, "all_nodes"):
            return []
        names = []
        for node in model.all_nodes():
            name = str(getattr(node, "name", "") or "").strip().lower()
            if name:
                names.append(name)
        return sorted(set(names))

    def _preview(self) -> None:
        self.previewRequested.emit(self.selected_animation())

    def _play_source_animation(self) -> None:
        self.sourceAnimationPlayRequested.emit(self.selected_animation())

    def _apply(self) -> None:
        self.applyRequested.emit(self.selected_animation())

    def _item_for_animation(self, anim_name: str | None) -> QtWidgets.QListWidgetItem | None:
        needle = str(anim_name or "")
        if not needle:
            return self.anim_list.currentItem()
        for index in range(self.anim_list.count()):
            item = self.anim_list.item(index)
            if self._source_name_for_item(item) == needle:
                return item
        return None

    def _source_name_for_item(self, item: QtWidgets.QListWidgetItem | None) -> str:
        if item is None:
            return ""
        source_name = item.data(QtCore.Qt.UserRole + 2)
        return str(source_name or item.text() or "")

    def _default_assignment_for(self, source_name: str) -> dict:
        return {
            "source_animation": source_name,
            "output_name": self._safe_custom_output_name(source_name),
            "output_mode": KotorOutputAnimationNameMode.CUSTOM_PATCH.value,
            "checked": True,
        }

    def _render_animation_item(self, item: QtWidgets.QListWidgetItem, *, length: float | None = None) -> None:
        source_name = self._source_name_for_item(item)
        assignment = item.data(QtCore.Qt.UserRole + 1)
        if not isinstance(assignment, dict):
            assignment = self._default_assignment_for(source_name)
        mode = self._coerce_output_mode(assignment.get("output_mode"))
        output_name = str(assignment.get("output_name") or "").strip() or self._safe_custom_output_name(source_name)
        mode_label = "custom patch" if mode == KotorOutputAnimationNameMode.CUSTOM_PATCH else "vanilla slot"
        source_label = animation_row_label(source_name)
        item.setText(f"{source_label}  ->  {output_name} ({mode_label})")
        tooltip = (
            f"Source animation: {source_label}\n"
            f"Target output animation: {output_name}\n"
            f"Output type: {mode_label}"
        )
        if length is not None and length > 0.0:
            tooltip += f"\nLength: {length:.3f}s"
        item.setToolTip(tooltip)

    def _show_animation_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.anim_list.itemAt(pos)
        if item is None:
            return
        self.anim_list.setCurrentItem(item)
        menu = QtWidgets.QMenu(self)
        rename_action = menu.addAction("Rename target output animation...")
        custom_action = menu.addAction("Set output type: Custom animation patch")
        vanilla_action = menu.addAction("Set output type: Vanilla slot override")
        toggle_action = menu.addAction("Assign/export this animation")
        toggle_action.setCheckable(True)
        toggle_action.setChecked(item.checkState() == QtCore.Qt.Checked)
        chosen = menu.exec(self.anim_list.mapToGlobal(pos))
        if chosen is None:
            return
        source_name = self._source_name_for_item(item)
        if chosen is rename_action:
            current = str(self.assignment_for_animation(source_name).get("output_name") or "")
            text, accepted = QtWidgets.QInputDialog.getText(
                self,
                "Rename Retarget Output",
                "Target output animation name:",
                QtWidgets.QLineEdit.Normal,
                current,
            )
            if accepted:
                self.set_animation_assignment(source_name, output_name=text)
        elif chosen is custom_action:
            self.set_animation_assignment(source_name, output_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH)
        elif chosen is vanilla_action:
            self.set_animation_assignment(source_name, output_mode=KotorOutputAnimationNameMode.VANILLA_SLOT)
        elif chosen is toggle_action:
            self.set_animation_assignment(source_name, checked=toggle_action.isChecked())

    def _coerce_output_mode(self, value) -> KotorOutputAnimationNameMode:
        if isinstance(value, KotorOutputAnimationNameMode):
            return value
        raw = str(value or "").strip().lower()
        if raw in {KotorOutputAnimationNameMode.VANILLA_SLOT.value, "vanilla", "slot"}:
            return KotorOutputAnimationNameMode.VANILLA_SLOT
        return KotorOutputAnimationNameMode.CUSTOM_PATCH

    def _safe_custom_output_name(self, source_name: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(source_name or "").strip())
        text = re.sub(r"_+", "_", text).strip("_-")
        if not text:
            text = "retargeted_animation"
        return text[:64]

    def _model_label(self, model) -> str:
        if model is None:
            return "None"
        return (
            f"{getattr(model, 'name', '?')}\n"
            f"{len(getattr(model, 'animations', []) or [])} anims  "
            f"{len(list(model.all_nodes())) if hasattr(model, 'all_nodes') else 0} nodes"
        )

    def _update_info(self) -> None:
        if self._source_model is None or self._target_model is None:
            self.info.setPlainText("Set a source model with animations and a target model.")
