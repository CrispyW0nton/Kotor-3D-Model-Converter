"""
GFF V3.2 data types for GhostRigger.

Spec: BioWare Aurora GFF format (used by all KotOR .utc/.utp/.utd/.dlg etc.)

Header layout:
    FileType[4] + Version[4] ("V3.2") + 6 × (offset, count) pairs = 56 bytes
    Sections: Header(0), StructArray(1), FieldArray(2), LabelArray(3),
              FieldDataBlock(4), FieldIndicesArray(5), ListIndicesArray(6)

Field types (from BioWare GFF spec):
    0  BYTE         uint8
    1  CHAR         int8
    2  UINT16       uint16
    3  INT16        int16
    4  UINT32       uint32
    5  INT32        int32
    6  UINT64       uint64
    7  INT64        int64
    8  FLOAT        float32
    9  DOUBLE       float64
    10 CExoString   length-prefixed UTF-8 string
    11 ResRef       1-byte length + up to 16 ASCII chars
    12 CExoLocString  int32 strref + list of language strings
    13 Binary       4-byte size + raw bytes
    14 Struct       embedded struct (field_index = struct array index)
    15 List         list of struct indices
    16 Position     3 × float32 (x, y, z)
    17 Rotation     4 × float32 (quaternion x, y, z, w)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Union


# ─── Field Type Enum ─────────────────────────────────────────────────────────

class GffFieldType(IntEnum):
    BYTE            = 0
    CHAR            = 1
    UINT16          = 2
    INT16           = 3
    UINT32          = 4
    INT32           = 5
    UINT64          = 6
    INT64           = 7
    FLOAT           = 8
    DOUBLE          = 9
    CEXOSTRING      = 10
    RESREF          = 11
    CEXOLOCSTRING   = 12
    BINARY          = 13
    STRUCT          = 14
    LIST            = 15
    POSITION        = 16
    ROTATION        = 17


# ─── Compound value types ─────────────────────────────────────────────────────

@dataclass
class ResRef:
    """KotOR ResRef: max 16 ASCII chars, case-insensitive."""
    value: str = ""

    def __post_init__(self):
        # Normalize: strip null bytes, lowercase, max 16 chars
        self.value = self.value.replace('\x00', '').lower()[:16]

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ResRef({self.value!r})"

    def __eq__(self, other) -> bool:
        if isinstance(other, ResRef):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other.replace('\x00', '').lower()[:16]
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass
class LocString:
    """
    CExoLocString: a string reference (StrRef) into dialog.tlk plus
    optional per-language override strings.
    strref = -1 means no TLK reference, use the embedded strings.
    """
    strref: int = -1
    strings: Dict[int, str] = field(default_factory=dict)  # lang_id → text

    # Standard KotOR language IDs
    LANG_ENGLISH = 0
    LANG_FRENCH  = 2
    LANG_GERMAN  = 4
    LANG_ITALIAN = 6
    LANG_SPANISH = 8
    LANG_POLISH  = 10

    def get_text(self, lang_id: int = 0) -> str:
        """Return the text for the given language, or empty string."""
        return self.strings.get(lang_id, "")

    def set_text(self, text: str, lang_id: int = 0):
        self.strings[lang_id] = text

    @property
    def english(self) -> str:
        return self.get_text(self.LANG_ENGLISH)

    @english.setter
    def english(self, value: str):
        self.set_text(value, self.LANG_ENGLISH)

    def __repr__(self) -> str:
        if self.strref >= 0:
            return f"LocString(strref={self.strref})"
        texts = list(self.strings.values())
        first = texts[0] if texts else ""
        return f"LocString({first!r})"


# ─── Core GFF data structures ─────────────────────────────────────────────────

@dataclass
class GffField:
    """
    A single GFF field (one entry in the Field Array).
    label: up to 16-char ASCII label string
    type:  GffFieldType
    value: Python-native value depending on type
    """
    label: str
    type: GffFieldType
    value: Any = None

    def __repr__(self) -> str:
        return f"GffField({self.label!r}, {self.type.name}, {self.value!r})"


@dataclass
class GffStruct:
    """
    A GFF Struct (one entry in the Struct Array).
    type_id: struct type identifier (0xFFFFFFFF for top-level)
    fields:  ordered dict of label → GffField
    """
    type_id: int = 0xFFFFFFFF
    fields: Dict[str, GffField] = field(default_factory=dict)

    def get(self, label: str, default=None):
        f = self.fields.get(label)
        return f.value if f is not None else default

    def set(self, label: str, ftype: GffFieldType, value):
        self.fields[label] = GffField(label, ftype, value)

    def __getitem__(self, label: str):
        return self.fields[label].value

    def __setitem__(self, label: str, value):
        if label in self.fields:
            self.fields[label].value = value
        else:
            raise KeyError(f"Field {label!r} not found in struct")

    def __contains__(self, label: str) -> bool:
        return label in self.fields

    def __repr__(self) -> str:
        return f"GffStruct(type_id=0x{self.type_id:08x}, fields={list(self.fields)})"


@dataclass
class GffFile:
    """
    Top-level GFF file container.
    file_type:    4-char string e.g. "UTC ", "UTP ", "UTD "
    file_version: "V3.2"
    root:         top-level GffStruct (struct index 0, type_id 0xFFFFFFFF)
    """
    file_type: str = "    "
    file_version: str = "V3.2"
    root: GffStruct = field(default_factory=GffStruct)

    def get(self, label: str, default=None):
        return self.root.get(label, default)

    def set(self, label: str, ftype: GffFieldType, value):
        self.root.set(label, ftype, value)

    def __repr__(self) -> str:
        return f"GffFile({self.file_type.strip()!r} {self.file_version}, {len(self.root.fields)} top-level fields)"


# ─── UTC field helpers (human-readable field catalogue) ──────────────────────

UTC_FIELDS = {
    # GFF label              → (human name,   field_type,   default)
    "Tag":              ("Tag",                  GffFieldType.CEXOSTRING,   ""),
    "TemplateResRef":   ("ResRef",               GffFieldType.RESREF,       ""),
    "FirstName":        ("Name",                 GffFieldType.CEXOLOCSTRING, None),
    "LastName":         ("Last Name",            GffFieldType.CEXOLOCSTRING, None),
    "Appearance_Type":  ("Appearance (2DA row)", GffFieldType.UINT16,        0),
    "Gender":           ("Gender",               GffFieldType.BYTE,          0),
    "Race":             ("Race",                 GffFieldType.BYTE,          6),
    "SubraceIndex":     ("Subrace",              GffFieldType.BYTE,          0),
    "Class1":           ("Class 1",              GffFieldType.BYTE,          0),
    "Level":            ("Level 1",              GffFieldType.BYTE,          1),
    "Class2":           ("Class 2",              GffFieldType.BYTE,         255),
    "Level2":           ("Level 2",              GffFieldType.BYTE,          0),
    "Class3":           ("Class 3",              GffFieldType.BYTE,         255),
    "Level3":           ("Level 3",              GffFieldType.BYTE,          0),
    "MaxHitPoints":     ("Max HP",               GffFieldType.INT16,         8),
    "CurrentHitPoints": ("Current HP",           GffFieldType.INT16,         8),
    "MaxFP":            ("Max Force Points",     GffFieldType.INT16,         0),
    "CurrentFP":        ("Current FP",           GffFieldType.INT16,         0),
    "fortbonus":        ("Fortitude Save",       GffFieldType.CHAR,          0),
    "refbonus":         ("Reflex Save",          GffFieldType.CHAR,          0),
    "willbonus":        ("Will Save",            GffFieldType.CHAR,          0),
    "Str":              ("Strength",             GffFieldType.BYTE,         10),
    "Dex":              ("Dexterity",            GffFieldType.BYTE,         10),
    "Con":              ("Constitution",         GffFieldType.BYTE,         10),
    "Int":              ("Intelligence",         GffFieldType.BYTE,         10),
    "Wis":              ("Wisdom",               GffFieldType.BYTE,         10),
    "Cha":              ("Charisma",             GffFieldType.BYTE,         10),
    "ComputerUsed":     ("Computer Use",         GffFieldType.BYTE,          0),
    "Demolitions":      ("Demolitions",          GffFieldType.BYTE,          0),
    "Stealth":          ("Stealth",              GffFieldType.BYTE,          0),
    "Awareness":        ("Awareness",            GffFieldType.BYTE,          0),
    "Persuade":         ("Persuade",             GffFieldType.BYTE,          0),
    "Repair":           ("Repair",               GffFieldType.BYTE,          0),
    "SecuritySkill":    ("Security",             GffFieldType.BYTE,          0),
    "TreatInjury":      ("Treat Injury",         GffFieldType.BYTE,          0),
    "FactionID":        ("Faction",              GffFieldType.UINT32,        1),
    "SoundSetFile":     ("Sound Set (2DA)",      GffFieldType.UINT16,        0),
    "Conversation":     ("Conversation ResRef",  GffFieldType.RESREF,       ""),
    "OnSpawn":          ("On Spawn Script",      GffFieldType.RESREF,       ""),
    "OnDeath":          ("On Death Script",      GffFieldType.RESREF,       ""),
    "OnDamaged":        ("On Damaged Script",    GffFieldType.RESREF,       ""),
    "OnAttacked":       ("On Attacked Script",   GffFieldType.RESREF,       ""),
    "OnHeartbeat":      ("On Heartbeat Script",  GffFieldType.RESREF,       ""),
    "OnBlocked":        ("On Blocked Script",    GffFieldType.RESREF,       ""),
    "OnConversation":   ("On Conversation Script", GffFieldType.RESREF,     ""),
    "OnDisturbance":    ("On Disturbance Script",GffFieldType.RESREF,       ""),
    "OnEndConversation":("On End Conversation",  GffFieldType.RESREF,       ""),
    "OnUserDefined":    ("On User Defined",      GffFieldType.RESREF,       ""),
    "WillNotRender":    ("Will Not Render",      GffFieldType.BYTE,          0),
    "NoPermDeath":      ("No Perm Death",        GffFieldType.BYTE,          0),
    "IsPC":             ("Is PC",                GffFieldType.BYTE,          0),
    "Disarmable":       ("Disarmable",           GffFieldType.BYTE,          0),
    "BodyBag":          ("Body Bag",             GffFieldType.BYTE,          0),
    "NotReorienting":   ("Not Reorienting",      GffFieldType.BYTE,          0),
    "BlindSpot":        ("Blind Spot",           GffFieldType.FLOAT,         0.0),
    "MultiplierSet":    ("Multiplier Set",       GffFieldType.BYTE,          0),
}

# UTP (Placeable) fields
UTP_FIELDS = {
    "Tag":              ("Tag",                  GffFieldType.CEXOSTRING,   ""),
    "TemplateResRef":   ("ResRef",               GffFieldType.RESREF,       ""),
    "LocalizedName":    ("Name",                 GffFieldType.CEXOLOCSTRING, None),
    "Appearance":       ("Appearance (2DA row)", GffFieldType.UINT32,        0),
    "MaxHP":            ("Max HP",               GffFieldType.INT16,         0),
    "CurrentHP":        ("Current HP",           GffFieldType.INT16,         0),
    "Faction":          ("Faction",              GffFieldType.UINT32,        1),
    "Static":           ("Static",               GffFieldType.BYTE,          0),
    "Useable":          ("Useable",              GffFieldType.BYTE,          1),
    "HasInventory":     ("Has Inventory",        GffFieldType.BYTE,          0),
    "OnUsed":           ("On Used Script",       GffFieldType.RESREF,       ""),
    "OnOpen":           ("On Open Script",       GffFieldType.RESREF,       ""),
    "OnClosed":         ("On Closed Script",     GffFieldType.RESREF,       ""),
    "OnDamaged":        ("On Damaged Script",    GffFieldType.RESREF,       ""),
    "OnDeath":          ("On Death Script",      GffFieldType.RESREF,       ""),
    "OnHeartbeat":      ("On Heartbeat Script",  GffFieldType.RESREF,       ""),
    "OnMeleeAttacked":  ("On Melee Attacked",    GffFieldType.RESREF,       ""),
    "OnLock":           ("On Lock Script",       GffFieldType.RESREF,       ""),
    "OnUnlock":         ("On Unlock Script",     GffFieldType.RESREF,       ""),
    "OnUserDefined":    ("On User Defined",      GffFieldType.RESREF,       ""),
    "Locked":           ("Locked",               GffFieldType.BYTE,          0),
    "LockDC":           ("Lock Difficulty",      GffFieldType.BYTE,          0),
    "TrapDetected":     ("Trap Detected",        GffFieldType.BYTE,          0),
    "TrapType":         ("Trap Type",            GffFieldType.BYTE,          0),
    "TrapFlag":         ("Has Trap",             GffFieldType.BYTE,          0),
    "TrapDisarmable":   ("Trap Disarmable",      GffFieldType.BYTE,          0),
    "TrapDetectable":   ("Trap Detectable",      GffFieldType.BYTE,          0),
    "TrapOneShot":      ("Trap One-Shot",        GffFieldType.BYTE,          0),
    "Description":      ("Description",          GffFieldType.CEXOLOCSTRING, None),
    "Plot":             ("Plot Item",            GffFieldType.BYTE,          0),
    "BodyBag":          ("Body Bag Type",        GffFieldType.BYTE,          0),
    "Min1HP":           ("Min 1 HP",             GffFieldType.BYTE,          0),
    "NotBlastable":     ("Not Blastable",        GffFieldType.BYTE,          0),
    "PaletteID":        ("Palette ID",           GffFieldType.BYTE,          0),
    "Comment":          ("Comment",              GffFieldType.CEXOSTRING,   ""),
}

# UTD (Door) fields
UTD_FIELDS = {
    "Tag":              ("Tag",                  GffFieldType.CEXOSTRING,   ""),
    "TemplateResRef":   ("ResRef",               GffFieldType.RESREF,       ""),
    "LocalizedName":    ("Name",                 GffFieldType.CEXOLOCSTRING, None),
    "GenericType":      ("Generic Type (2DA)",   GffFieldType.BYTE,          0),
    "LinkedTo":         ("Linked To (tag)",      GffFieldType.CEXOSTRING,   ""),
    "LinkedToFlags":    ("Linked To Flags",      GffFieldType.BYTE,          0),
    "MaxHP":            ("Max HP",               GffFieldType.INT16,         30),
    "CurrentHP":        ("Current HP",           GffFieldType.INT16,         30),
    "Locked":           ("Locked",               GffFieldType.BYTE,          0),
    "LockDC":           ("Lock Difficulty",      GffFieldType.BYTE,          0),
    "KeyRequired":      ("Key Required",         GffFieldType.BYTE,          0),
    "KeyName":          ("Key Tag",              GffFieldType.CEXOSTRING,   ""),
    "AutoRemoveKey":    ("Auto Remove Key",      GffFieldType.BYTE,          0),
    "Faction":          ("Faction",              GffFieldType.UINT32,        1),
    "Static":           ("Static",               GffFieldType.BYTE,          0),
    "OnOpen":           ("On Open Script",       GffFieldType.RESREF,       ""),
    "OnClosed":         ("On Closed Script",     GffFieldType.RESREF,       ""),
    "OnFailToOpen":     ("On Fail To Open",      GffFieldType.RESREF,       ""),
    "OnDamaged":        ("On Damaged Script",    GffFieldType.RESREF,       ""),
    "OnDeath":          ("On Death Script",      GffFieldType.RESREF,       ""),
    "OnMeleeAttacked":  ("On Melee Attacked",    GffFieldType.RESREF,       ""),
    "OnLock":           ("On Lock Script",       GffFieldType.RESREF,       ""),
    "OnOpen2":          ("On Open 2 Script",     GffFieldType.RESREF,       ""),
    "OnUnlock":         ("On Unlock Script",     GffFieldType.RESREF,       ""),
    "OnUserDefined":    ("On User Defined",      GffFieldType.RESREF,       ""),
    "Interruptable":    ("Interruptable",        GffFieldType.BYTE,          1),
    "Comment":          ("Comment",              GffFieldType.CEXOSTRING,   ""),
}

BLUEPRINT_FIELDS = {
    "UTC": UTC_FIELDS,
    "UTP": UTP_FIELDS,
    "UTD": UTD_FIELDS,
}
