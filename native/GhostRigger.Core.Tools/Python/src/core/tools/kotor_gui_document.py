"""Headless, lossless editing model for Odyssey ``.gui`` resources.

The document deliberately edits the original GFF tree instead of round-tripping
only through PyKotor's higher-level GUI classes.  That keeps fields unknown to
GhostRigger intact while still exposing the fields whose engine purpose is
known through typed schemas.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from pykotor.common.misc import ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, GFFStruct, bytes_gff, read_gff
from pykotor.resource.generics.gui import construct_gui
from utility.common.geometry import Vector3

from src.core.rendering.kotor_gui_preview import (
    KotorGuiBorderSnapshot,
    KotorGuiPreviewSnapshot,
    compile_kotor_gui_preview,
)


GUI_CONTROL_TYPES: tuple[tuple[int, str], ...] = (
    (2, "Panel"),
    (5, "Label"),
    (6, "Button"),
    (7, "Check Box"),
    (8, "Slider"),
    (9, "Scroll Bar"),
    (10, "Progress Bar"),
    (11, "List Box"),
)

_CONTROL_NAMES = {
    -1: "Invalid",
    0: "Control",
    2: "Panel",
    4: "Prototype Item",
    **dict(GUI_CONTROL_TYPES),
}
_TAG_PREFIXES = {2: "PNL", 5: "LBL", 6: "BTN", 7: "CHK", 8: "SLD", 9: "SCR", 10: "PRG", 11: "LST"}
_CONTAINER_TYPES = {0, 2}
_TEXT_TYPES = {4, 5, 6, 7, 11}
_BORDER_TYPES = {0, 2, 4, 6, 7, 8, 9, 10, 11}
_INTERACTIVE_TYPES = {6, 7, 8, 9, 11}
_RESREF_PATTERN = re.compile(r"^[A-Za-z0-9_]*$")

TEXT_ALIGNMENT_CHOICES: tuple[tuple[str, int], ...] = (
    ("Top left", 9),
    ("Top center", 10),
    ("Top right", 12),
    ("Middle left", 17),
    ("Middle center", 18),
    ("Middle right", 20),
    ("Bottom left", 33),
    ("Bottom center", 34),
    ("Bottom right", 36),
)
FILL_STYLE_CHOICES: tuple[tuple[str, int], ...] = (
    ("Engine default / none", 0),
    ("Solid color", 1),
    ("Texture", 2),
)


@dataclass(frozen=True, slots=True)
class GuiFieldSpec:
    """One typed inspector field and its exact GFF storage route."""

    key: str
    label: str
    group: str
    kind: str
    struct_path: tuple[str, ...]
    field_label: str
    storage: str
    default: object = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple[tuple[str, int], ...] = ()
    help_text: str = ""


@dataclass(frozen=True, slots=True)
class GuiValidationIssue:
    severity: str
    path: tuple[int, ...]
    field: str
    message: str


def _spec(
    key: str,
    label: str,
    group: str,
    kind: str,
    field_label: str,
    storage: str,
    *,
    struct_path: tuple[str, ...] = (),
    default: object = None,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
    choices: tuple[tuple[str, int], ...] = (),
    help_text: str = "",
) -> GuiFieldSpec:
    return GuiFieldSpec(
        key,
        label,
        group,
        kind,
        struct_path,
        field_label,
        storage,
        default,
        minimum,
        maximum,
        choices,
        help_text,
    )


_COMMON_FIELDS = (
    _spec("tag", "Tag", "Identity", "text", "TAG", "string", default="", help_text="Script-facing control tag."),
    _spec("id", "Control ID", "Identity", "int", "ID", "int32", default=-1, minimum=-1, maximum=2_147_483_647, help_text="Numeric ID used by navigation and engine code."),
    _spec("locked", "Locked", "Identity", "bool", "Obj_Locked", "uint8", default=False, help_text="Prevents accidental canvas movement and resizing."),
    _spec("left", "Left", "Extent", "int", "LEFT", "int32", struct_path=("EXTENT",), default=0, minimum=-32768, maximum=32767),
    _spec("top", "Top", "Extent", "int", "TOP", "int32", struct_path=("EXTENT",), default=0, minimum=-32768, maximum=32767),
    _spec("width", "Width", "Extent", "int", "WIDTH", "int32", struct_path=("EXTENT",), default=1, minimum=1, maximum=32767),
    _spec("height", "Height", "Extent", "int", "HEIGHT", "int32", struct_path=("EXTENT",), default=1, minimum=1, maximum=32767),
    _spec("color", "Control color", "Appearance", "color", "COLOR", "vector3", default=(1.0, 1.0, 1.0)),
)

_TEXT_FIELDS = (
    _spec("text.value", "Text override", "Text", "text", "TEXT", "string", struct_path=("TEXT",), default="", help_text="Literal text; leave blank when the game supplies text at runtime."),
    _spec("text.strref", "TLK string ref", "Text", "uint32_or_minus_one", "STRREF", "uint32_strref", struct_path=("TEXT",), default=-1, minimum=-1, maximum=4_294_967_294, help_text="-1 uses literal/runtime text; otherwise references dialog.tlk."),
    _spec("text.font", "Font texture", "Text", "texture", "FONT", "resref", struct_path=("TEXT",), default="", help_text="KOTOR font texture resref from the selected game install."),
    _spec("text.alignment", "Alignment", "Text", "choice", "ALIGNMENT", "int32", struct_path=("TEXT",), default=9, choices=TEXT_ALIGNMENT_CHOICES),
    _spec("text.pulsing", "Pulsing", "Text", "bool", "PULSING", "uint8", struct_path=("TEXT",), default=False),
    _spec("text.color", "Text color", "Text", "color", "COLOR", "vector3", struct_path=("TEXT",), default=(1.0, 1.0, 1.0)),
)


def _border_fields(prefix: str, group: str, struct_label: str) -> tuple[GuiFieldSpec, ...]:
    route = (struct_label,)
    return (
        _spec(f"{prefix}.fill", "Fill texture", group, "texture", "FILL", "resref", struct_path=route, default=""),
        _spec(f"{prefix}.edge", "Edge texture", group, "texture", "EDGE", "resref", struct_path=route, default=""),
        _spec(f"{prefix}.corner", "Corner texture", group, "texture", "CORNER", "resref", struct_path=route, default=""),
        _spec(f"{prefix}.fill_style", "Fill style", group, "choice", "FILLSTYLE", "int32", struct_path=route, default=2, choices=FILL_STYLE_CHOICES),
        _spec(f"{prefix}.dimension", "Border dimension", group, "int", "DIMENSION", "int32", struct_path=route, default=0, minimum=0, maximum=4096),
        _spec(f"{prefix}.inner_offset", "Inner X offset", group, "int", "INNEROFFSET", "int32", struct_path=route, default=0, minimum=-4096, maximum=4096),
        _spec(f"{prefix}.inner_offset_y", "Inner Y offset", group, "int", "INNEROFFSETY", "int32", struct_path=route, default=0, minimum=-4096, maximum=4096),
        _spec(f"{prefix}.pulsing", "Pulsing", group, "bool", "PULSING", "uint8", struct_path=route, default=False),
        _spec(f"{prefix}.color", "Color", group, "color", "COLOR", "vector3", struct_path=route, default=(1.0, 1.0, 1.0)),
    )


_NAVIGATION_FIELDS = tuple(
    _spec(
        f"navigation.{name.lower()}",
        name.title(),
        "Keyboard / controller navigation",
        "int",
        name,
        "int32",
        struct_path=("MOVETO",),
        default=-1,
        minimum=-1,
        maximum=2_147_483_647,
        help_text="Control ID selected when moving in this direction; -1 disables the link.",
    )
    for name in ("UP", "DOWN", "LEFT", "RIGHT")
)

_RUNTIME_FIELDS = {
    7: (
        _spec("checkbox.selected", "Initially selected", "Check box", "bool", "ISSELECTED", "uint8", default=False),
    ),
    8: (
        _spec("value.current", "Current value", "Slider", "int", "CURVALUE", "int32", default=0, minimum=0, maximum=2_147_483_647),
        _spec("value.maximum", "Maximum value", "Slider", "int", "MAXVALUE", "int32", default=100, minimum=1, maximum=2_147_483_647),
        _spec("thumb.image", "Thumb texture", "Slider", "texture", "IMAGE", "resref", struct_path=("THUMB",), default=""),
        _spec("thumb.alignment", "Thumb alignment", "Slider", "choice", "ALIGNMENT", "int32", struct_path=("THUMB",), default=18, choices=TEXT_ALIGNMENT_CHOICES),
    ),
    9: (
        _spec("scroll.current", "Current value", "Scroll bar", "int", "CURVALUE", "int32", default=0, minimum=0, maximum=2_147_483_647),
        _spec("scroll.maximum", "Maximum value", "Scroll bar", "int", "MAXVALUE", "int32", default=99, minimum=1, maximum=2_147_483_647),
        _spec("scroll.visible", "Visible value", "Scroll bar", "int", "VISIBLEVALUE", "int32", default=1, minimum=1, maximum=2_147_483_647),
        _spec("scroll.draw_mode", "Draw mode", "Scroll bar", "int", "DRAWMODE", "uint8", default=0, minimum=0, maximum=255),
        _spec("thumb.image", "Thumb texture", "Scroll bar", "texture", "IMAGE", "resref", struct_path=("THUMB",), default=""),
        _spec("direction.image", "Direction texture", "Scroll bar", "texture", "IMAGE", "resref", struct_path=("DIR",), default=""),
    ),
    10: (
        _spec("value.current", "Current value", "Progress", "int", "CURVALUE", "int32", default=0, minimum=0, maximum=2_147_483_647),
        _spec("value.maximum", "Maximum value", "Progress", "int", "MAXVALUE", "int32", default=100, minimum=1, maximum=2_147_483_647),
        _spec("progress.start_left", "Start from left", "Progress", "bool", "STARTFROMLEFT", "uint8", default=True),
        *_border_fields("progress", "Progress fill", "PROGRESS"),
    ),
    11: (
        _spec("list.padding", "Item padding", "List box", "int", "PADDING", "int32", default=5, minimum=0, maximum=4096),
        _spec("list.looping", "Loop navigation", "List box", "bool", "LOOPING", "uint8", default=True),
        _spec("list.left_scrollbar", "Scroll bar on left", "List box", "bool", "LEFTSCROLLBAR", "uint8", default=False),
        _spec("list.scroll.maximum", "Scroll maximum", "List box", "int", "MAXVALUE", "int32", struct_path=("SCROLLBAR",), default=99, minimum=1, maximum=2_147_483_647),
        _spec("list.scroll.visible", "Visible items", "List box", "int", "VISIBLEVALUE", "int32", struct_path=("SCROLLBAR",), default=1, minimum=1, maximum=2_147_483_647),
        _spec("list.scroll.current", "Current item", "List box", "int", "CURVALUE", "int32", struct_path=("SCROLLBAR",), default=0, minimum=0, maximum=2_147_483_647),
        _spec("list.thumb.image", "Scroll thumb texture", "List box", "texture", "IMAGE", "resref", struct_path=("SCROLLBAR", "THUMB"), default=""),
        _spec("list.direction.image", "Scroll direction texture", "List box", "texture", "IMAGE", "resref", struct_path=("SCROLLBAR", "DIR"), default=""),
    ),
}


def _direct_struct(parent: GFFStruct, label: str) -> GFFStruct | None:
    value = parent.acquire(label, None)
    return value if isinstance(value, GFFStruct) else None


def _direct_list(parent: GFFStruct, label: str) -> GFFList | None:
    value = parent.acquire(label, None)
    return value if isinstance(value, GFFList) else None


def _ensure_struct(parent: GFFStruct, label: str) -> GFFStruct:
    existing = parent.acquire(label, None)
    if existing is None:
        return parent.set_struct(label, GFFStruct(0))
    if not isinstance(existing, GFFStruct):
        raise ValueError(f"{label} exists but is not a GFF struct")
    return existing


def _ensure_list(parent: GFFStruct, label: str) -> GFFList:
    existing = parent.acquire(label, None)
    if existing is None:
        return parent.set_list(label, GFFList())
    if not isinstance(existing, GFFList):
        raise ValueError(f"{label} exists but is not a GFF list")
    return existing


def _blank_border(*, fill_style: int = 2) -> GFFStruct:
    border = GFFStruct(0)
    border.set_resref("CORNER", ResRef.from_blank())
    border.set_resref("EDGE", ResRef.from_blank())
    border.set_resref("FILL", ResRef.from_blank())
    border.set_int32("FILLSTYLE", fill_style)
    border.set_int32("DIMENSION", 0)
    border.set_int32("INNEROFFSET", 0)
    return border


def _blank_text() -> GFFStruct:
    text = GFFStruct(0)
    text.set_string("TEXT", "")
    text.set_uint32("STRREF", 0xFFFFFFFF)
    text.set_resref("FONT", ResRef.from_blank())
    text.set_int32("ALIGNMENT", 9)
    text.set_vector3("COLOR", Vector3(1.0, 1.0, 1.0))
    return text


def _blank_moveto() -> GFFStruct:
    moveto = GFFStruct(0)
    for label in ("UP", "DOWN", "LEFT", "RIGHT"):
        moveto.set_int32(label, -1)
    return moveto


def _blank_thumb() -> GFFStruct:
    thumb = GFFStruct(0)
    thumb.set_resref("IMAGE", ResRef.from_blank())
    thumb.set_int32("ALIGNMENT", 18)
    thumb.set_int32("FLIPSTYLE", 0)
    thumb.set_int32("DRAWSTYLE", 0)
    return thumb


def _gff_border_snapshot(control: GFFStruct, label: str) -> KotorGuiBorderSnapshot | None:
    border = _direct_struct(control, label)
    if border is None:
        return None
    color = border.acquire("COLOR", None)
    rgba = None if color is None else (float(color.x), float(color.y), float(color.z), 1.0)
    return KotorGuiBorderSnapshot(
        corner=str(border.get_resref("CORNER", ResRef.from_blank())),
        edge=str(border.get_resref("EDGE", ResRef.from_blank())),
        fill=str(border.get_resref("FILL", ResRef.from_blank())),
        fill_style=int(border.get_int32("FILLSTYLE", 0)),
        dimension=int(border.get_int32("DIMENSION", 0)),
        inner_offset=border.get_int32("INNEROFFSET", None),
        inner_offset_y=border.get_int32("INNEROFFSETY", None),
        pulsing=border.get_uint8("PULSING", None),
        color_rgba=rgba,
    )


class KotorGuiDocument:
    """Editable GFF-backed GUI document with bounded byte-level undo history."""

    history_limit = 100

    def __init__(
        self,
        gff: GFF,
        *,
        game: str,
        resref: str,
        source_kind: str = "retail_gui",
        source_path: str | Path | None = None,
    ) -> None:
        tag = str(game or "K2").strip().upper()
        if tag not in {"K1", "K2"}:
            raise ValueError(f"Unsupported KOTOR game tag: {game!r}")
        name = str(resref or "untitled").strip().lower()
        if not name:
            raise ValueError("GUI resref cannot be blank")
        self.game = tag
        self.resref = name
        self.source_kind = str(source_kind or "editable_gui")
        self.source_path = Path(source_path).resolve() if source_path else None
        self._gff = gff
        self._undo: list[bytes] = []
        self._redo: list[bytes] = []
        self._revision = 0
        # GFF writers may canonicalize otherwise equivalent input bytes.  The
        # document is clean immediately after parsing; dirty state begins with
        # the first authored mutation, not with PyKotor's serialization order.
        baseline = self.to_bytes()
        self._clean_digest = hashlib.sha256(baseline).digest()

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        game: str,
        resref: str,
        source_kind: str = "retail_gui",
        source_path: str | Path | None = None,
    ) -> "KotorGuiDocument":
        raw = bytes(data or b"")
        if not raw:
            raise ValueError("GUI data is empty")
        return cls(
            read_gff(raw),
            game=game,
            resref=resref,
            source_kind=source_kind,
            source_path=source_path,
        )

    @classmethod
    def new(cls, *, game: str = "K2", resref: str = "new_gui", width: int = 640, height: int = 480) -> "KotorGuiDocument":
        if width < 1 or height < 1:
            raise ValueError("GUI canvas dimensions must be positive")
        gff = GFF(GFFContent.GUI)
        root = GFFStruct(-1)
        root.set_int32("CONTROLTYPE", 2)
        root.set_int32("ID", 0)
        root.set_string("TAG", "ROOT")
        root.set_uint8("Obj_Locked", 1)
        extent = root.set_struct("EXTENT", GFFStruct(0))
        extent.set_int32("LEFT", 0)
        extent.set_int32("TOP", 0)
        extent.set_int32("WIDTH", int(width))
        extent.set_int32("HEIGHT", int(height))
        root.set_struct("BORDER", _blank_border())
        root.set_list("CONTROLS", GFFList())
        gff.root = root
        return cls(gff, game=game, resref=resref, source_kind="new_gui")

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def dirty(self) -> bool:
        return hashlib.sha256(self.to_bytes()).digest() != self._clean_digest

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @staticmethod
    def key_for_path(path: Iterable[int]) -> str:
        values = tuple(int(value) for value in path)
        if not values or values[0] != 0:
            raise ValueError("GUI paths start at the single root control (0)")
        return "control:" + ".".join(str(value) for value in values)

    @staticmethod
    def path_for_key(key: str) -> tuple[int, ...]:
        text = str(key or "")
        if not text.startswith("control:"):
            raise ValueError(f"Invalid GUI control key: {key!r}")
        try:
            path = tuple(int(part) for part in text.partition(":")[2].split("."))
        except ValueError as exc:
            raise ValueError(f"Invalid GUI control key: {key!r}") from exc
        if not path or path[0] != 0 or any(value < 0 for value in path):
            raise ValueError(f"Invalid GUI control key: {key!r}")
        return path

    def control_struct(self, path: Iterable[int]) -> GFFStruct:
        values = tuple(int(value) for value in path)
        if not values or values[0] != 0:
            raise KeyError(values)
        current = self._gff.root
        for index in values[1:]:
            controls = _direct_list(current, "CONTROLS")
            if controls is None or index < 0 or index >= len(controls):
                raise KeyError(values)
            current = controls[index]
        return current

    def control_type(self, path: Iterable[int]) -> int:
        return int(self.control_struct(path).get_int32("CONTROLTYPE", -1))

    def control_name(self, path: Iterable[int]) -> str:
        control = self.control_struct(path)
        control_type = int(control.get_int32("CONTROLTYPE", -1))
        return _CONTROL_NAMES.get(control_type, f"Control {control_type}")

    def iter_controls(self) -> Iterable[tuple[tuple[int, ...], GFFStruct]]:
        def visit(path: tuple[int, ...], struct: GFFStruct):
            yield path, struct
            controls = _direct_list(struct, "CONTROLS")
            if controls is not None:
                for index, child in enumerate(controls):
                    yield from visit(path + (index,), child)

        yield from visit((0,), self._gff.root)

    def insertion_parent(self, path: Iterable[int]) -> tuple[int, ...]:
        values = tuple(path)
        if self.control_type(values) in _CONTAINER_TYPES:
            return values
        return values[:-1] or (0,)

    def field_specs(self, path: Iterable[int]) -> tuple[GuiFieldSpec, ...]:
        control_type = self.control_type(path)
        fields: list[GuiFieldSpec] = list(_COMMON_FIELDS)
        if control_type in _TEXT_TYPES:
            fields.extend(_TEXT_FIELDS)
        if control_type in _BORDER_TYPES:
            fields.extend(_border_fields("border", "Border / background", "BORDER"))
        if control_type in _INTERACTIVE_TYPES:
            fields.extend(_border_fields("highlight", "Highlight", "HILIGHT"))
            fields.extend(_NAVIGATION_FIELDS)
        if control_type == 7:
            fields.extend(_border_fields("selected", "Selected state", "SELECTED"))
            fields.extend(_border_fields("highlight_selected", "Highlighted selected state", "HILIGHTSELECTED"))
        fields.extend(_RUNTIME_FIELDS.get(control_type, ()))
        return tuple(fields)

    def _field_spec(self, path: Iterable[int], key: str) -> GuiFieldSpec:
        for spec in self.field_specs(path):
            if spec.key == key:
                return spec
        raise KeyError(f"{self.key_for_path(path)} has no editable field {key!r}")

    def field_value(self, path: Iterable[int], key: str) -> object:
        spec = self._field_spec(path, key)
        struct = self.control_struct(path)
        for label in spec.struct_path:
            nested = _direct_struct(struct, label)
            if nested is None:
                return spec.default
            struct = nested
        value = struct.acquire(spec.field_label, None)
        if value is None:
            return spec.default
        if spec.storage == "resref":
            return str(value)
        if spec.storage == "vector3":
            return (float(value.x), float(value.y), float(value.z))
        if spec.storage == "uint32_strref":
            number = int(value)
            return -1 if number == 0xFFFFFFFF else number
        if spec.kind == "bool":
            return bool(value)
        return value

    def field_values(self, path: Iterable[int]) -> dict[str, object]:
        return {spec.key: self.field_value(path, spec.key) for spec in self.field_specs(path)}

    @staticmethod
    def _validated_value(spec: GuiFieldSpec, value: object) -> object:
        if spec.kind in {"int", "uint32_or_minus_one", "choice"}:
            try:
                result = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{spec.label} must be a whole number") from exc
            if spec.minimum is not None and result < spec.minimum:
                raise ValueError(f"{spec.label} must be at least {spec.minimum:g}")
            if spec.maximum is not None and result > spec.maximum:
                raise ValueError(f"{spec.label} must be at most {spec.maximum:g}")
            allowed = {choice_value for _choice_label, choice_value in spec.choices}
            if allowed and result not in allowed:
                raise ValueError(f"{spec.label} must use a known option")
            return result
        if spec.kind == "bool":
            return bool(value)
        if spec.kind in {"texture", "resref"}:
            result = str(value or "").strip().lower()
            if len(result) > 16:
                raise ValueError(f"{spec.label} is limited to 16 characters")
            if not _RESREF_PATTERN.fullmatch(result):
                raise ValueError(f"{spec.label} may contain only letters, numbers, and underscores")
            return result
        if spec.kind == "color":
            try:
                channels = tuple(float(channel) for channel in value)  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{spec.label} must be an RGB color") from exc
            if len(channels) != 3 or any(not math.isfinite(channel) or channel < 0.0 or channel > 1.0 for channel in channels):
                raise ValueError(f"{spec.label} channels must be between 0 and 1")
            return channels
        result = str(value or "")
        if "\x00" in result:
            raise ValueError(f"{spec.label} cannot contain a null character")
        return result

    def _checkpoint(self) -> None:
        self._undo.append(self.to_bytes())
        if len(self._undo) > self.history_limit:
            del self._undo[0]
        self._redo.clear()

    def _mutated(self) -> None:
        self._revision += 1

    def set_field(self, path: Iterable[int], key: str, value: object) -> None:
        values = tuple(path)
        spec = self._field_spec(values, key)
        new_value = self._validated_value(spec, value)
        if self.field_value(values, key) == new_value:
            return
        self._checkpoint()
        struct = self.control_struct(values)
        for label in spec.struct_path:
            struct = _ensure_struct(struct, label)
        if spec.storage == "string":
            struct.set_string(spec.field_label, str(new_value))
        elif spec.storage == "int32":
            struct.set_int32(spec.field_label, int(new_value))
        elif spec.storage == "uint8":
            struct.set_uint8(spec.field_label, int(bool(new_value)) if spec.kind == "bool" else int(new_value))
        elif spec.storage == "uint32_strref":
            number = int(new_value)
            struct.set_uint32(spec.field_label, 0xFFFFFFFF if number == -1 else number)
        elif spec.storage == "resref":
            struct.set_resref(spec.field_label, ResRef(str(new_value)))
        elif spec.storage == "vector3":
            red, green, blue = new_value  # type: ignore[misc]
            struct.set_vector3(spec.field_label, Vector3(red, green, blue))
        else:  # pragma: no cover - schema contract guard
            raise ValueError(f"Unsupported GUI field storage: {spec.storage}")
        self._mutated()

    def set_extent(self, path: Iterable[int], left: int, top: int, width: int, height: int) -> None:
        values = tuple(path)
        requested = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height),
        }
        if requested["width"] < 1 or requested["height"] < 1:
            raise ValueError("GUI control width and height must be positive")
        current = {name: int(self.field_value(values, name)) for name in requested}
        if current == requested:
            return
        self._checkpoint()
        extent = _ensure_struct(self.control_struct(values), "EXTENT")
        extent.set_int32("LEFT", requested["left"])
        extent.set_int32("TOP", requested["top"])
        extent.set_int32("WIDTH", requested["width"])
        extent.set_int32("HEIGHT", requested["height"])
        self._mutated()

    def _next_id(self) -> int:
        used = {int(struct.get_int32("ID", -1)) for _path, struct in self.iter_controls()}
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    def _next_tag(self, control_type: int) -> str:
        prefix = _TAG_PREFIXES.get(control_type, "CTRL")
        used = {str(struct.get_string("TAG", "")).casefold() for _path, struct in self.iter_controls()}
        index = 1
        while f"{prefix}_NEW_{index}".casefold() in used:
            index += 1
        return f"{prefix}_NEW_{index}"

    def _new_control(self, control_type: int, parent: GFFStruct) -> GFFStruct:
        if control_type not in dict(GUI_CONTROL_TYPES):
            raise ValueError(f"Unsupported addable GUI control type: {control_type}")
        control = GFFStruct(0)
        control.set_int32("CONTROLTYPE", control_type)
        control.set_int32("ID", self._next_id())
        control.set_string("TAG", self._next_tag(control_type))
        control.set_uint8("Obj_Locked", 0)
        parent_tag = parent.get_string("TAG", None)
        parent_id = parent.get_int32("ID", None)
        if parent_tag is not None:
            control.set_string("Obj_Parent", parent_tag)
        if parent_id is not None:
            control.set_int32("Obj_ParentID", int(parent_id))
        extent = control.set_struct("EXTENT", GFFStruct(0))
        extent.set_int32("LEFT", 16)
        extent.set_int32("TOP", 16)
        default_width, default_height = {
            2: (320, 240),
            5: (160, 28),
            6: (120, 36),
            7: (32, 32),
            8: (180, 24),
            9: (24, 160),
            10: (180, 20),
            11: (240, 180),
        }[control_type]
        extent.set_int32("WIDTH", default_width)
        extent.set_int32("HEIGHT", default_height)
        if control_type in _BORDER_TYPES:
            control.set_struct("BORDER", _blank_border())
        if control_type in _TEXT_TYPES:
            control.set_struct("TEXT", _blank_text())
        if control_type in _INTERACTIVE_TYPES:
            control.set_struct("HILIGHT", _blank_border())
            control.set_struct("MOVETO", _blank_moveto())
        if control_type in _CONTAINER_TYPES:
            control.set_list("CONTROLS", GFFList())
        if control_type == 7:
            control.set_struct("SELECTED", _blank_border())
            control.set_struct("HILIGHTSELECTED", _blank_border())
            control.set_uint8("ISSELECTED", 0)
        elif control_type == 8:
            control.set_int32("CURVALUE", 0)
            control.set_int32("MAXVALUE", 100)
            control.set_struct("THUMB", _blank_thumb())
        elif control_type == 9:
            control.set_int32("CURVALUE", 0)
            control.set_int32("MAXVALUE", 99)
            control.set_int32("VISIBLEVALUE", 1)
            control.set_uint8("DRAWMODE", 0)
            control.set_struct("THUMB", _blank_thumb())
            control.set_struct("DIR", _blank_thumb())
        elif control_type == 10:
            control.set_int32("CURVALUE", 0)
            control.set_int32("MAXVALUE", 100)
            control.set_uint8("STARTFROMLEFT", 1)
            control.set_struct("PROGRESS", _blank_border(fill_style=2))
        elif control_type == 11:
            control.set_int32("PADDING", 5)
            control.set_uint8("LOOPING", 1)
            control.set_uint8("LEFTSCROLLBAR", 0)
            proto = GFFStruct(0)
            proto.set_int32("CONTROLTYPE", 4)
            proto.set_string("TAG", "PROTOITEM")
            proto.set_struct("EXTENT", GFFStruct(0))
            proto_extent = _direct_struct(proto, "EXTENT")
            assert proto_extent is not None
            for label, number in (("LEFT", 0), ("TOP", 0), ("WIDTH", default_width - 24), ("HEIGHT", 24)):
                proto_extent.set_int32(label, number)
            proto.set_struct("TEXT", _blank_text())
            proto.set_struct("BORDER", _blank_border())
            proto.set_struct("HILIGHT", _blank_border())
            control.set_struct("PROTOITEM", proto)
            scrollbar = GFFStruct(0)
            scrollbar.set_int32("CONTROLTYPE", 9)
            scrollbar.set_string("TAG", "SCROLLBAR")
            scrollbar.set_int32("MAXVALUE", 99)
            scrollbar.set_int32("VISIBLEVALUE", 1)
            scrollbar.set_int32("CURVALUE", 0)
            scroll_extent = scrollbar.set_struct("EXTENT", GFFStruct(0))
            for label, number in (("LEFT", default_width - 24), ("TOP", 0), ("WIDTH", 24), ("HEIGHT", default_height)):
                scroll_extent.set_int32(label, number)
            scrollbar.set_struct("BORDER", _blank_border())
            scrollbar.set_struct("THUMB", _blank_thumb())
            scrollbar.set_struct("DIR", _blank_thumb())
            control.set_struct("SCROLLBAR", scrollbar)
        return control

    def add_control(self, parent_path: Iterable[int], control_type: int) -> tuple[int, ...]:
        parent_values = tuple(parent_path)
        parent = self.control_struct(parent_values)
        if self.control_type(parent_values) not in _CONTAINER_TYPES:
            raise ValueError("New controls must be added to a panel or generic container")
        self._checkpoint()
        controls = _ensure_list(parent, "CONTROLS")
        controls.append(self._new_control(int(control_type), parent))
        new_path = parent_values + (len(controls) - 1,)
        self._mutated()
        return new_path

    def delete_control(self, path: Iterable[int]) -> tuple[int, ...]:
        values = tuple(path)
        if len(values) <= 1:
            raise ValueError("The root panel cannot be deleted")
        parent_path = values[:-1]
        parent = self.control_struct(parent_path)
        controls = _direct_list(parent, "CONTROLS")
        if controls is None or values[-1] >= len(controls):
            raise KeyError(values)
        self._checkpoint()
        del controls[values[-1]]
        self._mutated()
        return parent_path

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.to_bytes())
        self._gff = read_gff(self._undo.pop())
        self._mutated()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.to_bytes())
        self._gff = read_gff(self._redo.pop())
        self._mutated()
        return True

    def to_bytes(self) -> bytes:
        return bytes_gff(self._gff)

    def preview_snapshot(self) -> KotorGuiPreviewSnapshot:
        snapshot = compile_kotor_gui_preview(
            construct_gui(self._gff),
            game=self.game,
            resref=self.resref,
            source_kind=self.source_kind,
        )
        structs = dict(self.iter_controls())
        enriched = []
        for row in snapshot.controls:
            struct = structs.get(row.path)
            if struct is None:
                enriched.append(row)
                continue
            control_type = int(struct.get_int32("CONTROLTYPE", -1))
            field_values = self.field_values(row.path)
            texture_refs = tuple(
                dict.fromkeys(
                    (
                        *row.texture_resrefs,
                        *(
                            str(field_values[spec.key]).strip().lower()
                            for spec in self.field_specs(row.path)
                            if spec.kind == "texture" and str(field_values[spec.key]).strip()
                        ),
                    )
                )
            )
            properties = dict(row.properties)
            property_fields = {
                7: {"is_selected": "checkbox.selected"},
                8: {"current_value": "value.current", "max_value": "value.maximum"},
                9: {
                    "current_value": "scroll.current",
                    "max_value": "scroll.maximum",
                    "visible_value": "scroll.visible",
                    "draw_mode": "scroll.draw_mode",
                },
                10: {
                    "current_value": "value.current",
                    "max_value": "value.maximum",
                    "start_from_left": "progress.start_left",
                },
                11: {
                    "padding": "list.padding",
                    "looping": "list.looping",
                    "left_scrollbar": "list.left_scrollbar",
                    "scroll_current": "list.scroll.current",
                    "scroll_maximum": "list.scroll.maximum",
                    "scroll_visible": "list.scroll.visible",
                },
            }.get(control_type, {})
            properties.update({name: field_values[field] for name, field in property_fields.items()})
            enriched.append(
                replace(
                    row,
                    progress=_gff_border_snapshot(struct, "PROGRESS") if control_type == 10 else row.progress,
                    properties=tuple(sorted(properties.items())),
                    texture_resrefs=texture_refs,
                )
            )
        return replace(snapshot, controls=tuple(enriched))

    def mark_saved(self, path: str | Path) -> None:
        self.source_path = Path(path).resolve()
        self.source_kind = "local_gui"
        self.resref = self.source_path.stem.lower()
        self._clean_digest = hashlib.sha256(self.to_bytes()).digest()

    def validation_issues(self) -> tuple[GuiValidationIssue, ...]:
        issues: list[GuiValidationIssue] = []
        ids: dict[int, tuple[int, ...]] = {}
        tags: dict[str, tuple[int, ...]] = {}
        known_types = set(_CONTROL_NAMES)
        for path, control in self.iter_controls():
            control_type = int(control.get_int32("CONTROLTYPE", -1))
            extent = _direct_struct(control, "EXTENT")
            if extent is None:
                issues.append(GuiValidationIssue("error", path, "EXTENT", "Control has no EXTENT structure."))
            else:
                width = int(extent.get_int32("WIDTH", 0))
                height = int(extent.get_int32("HEIGHT", 0))
                if width < 1 or height < 1:
                    issues.append(GuiValidationIssue("error", path, "EXTENT", "Width and height must be positive."))
            if control_type not in known_types:
                issues.append(GuiValidationIssue("warning", path, "CONTROLTYPE", f"Unknown control type {control_type} is preserved but not fully editable."))
            control_id = control.get_int32("ID", None)
            if control_id is not None and int(control_id) >= 0:
                number = int(control_id)
                if number in ids:
                    issues.append(GuiValidationIssue("warning", path, "ID", f"Control ID {number} is also used by {self.key_for_path(ids[number])}."))
                else:
                    ids[number] = path
            tag = str(control.get_string("TAG", "") or "").strip()
            if tag:
                folded = tag.casefold()
                if folded in tags:
                    issues.append(GuiValidationIssue("warning", path, "TAG", f"Tag {tag!r} is also used by {self.key_for_path(tags[folded])}."))
                else:
                    tags[folded] = path
            for spec in self.field_specs(path):
                if spec.kind not in {"texture", "resref"}:
                    continue
                value = str(self.field_value(path, spec.key) or "")
                if len(value) > 16 or not _RESREF_PATTERN.fullmatch(value):
                    issues.append(GuiValidationIssue("error", path, spec.key, f"{spec.label} is not a valid KOTOR resref."))
            if control_type in {8, 9, 10}:
                current = control.get_int32("CURVALUE", None)
                maximum = control.get_int32("MAXVALUE", None)
                if current is not None and maximum is not None and int(current) > int(maximum):
                    issues.append(GuiValidationIssue("warning", path, "CURVALUE", "Current value is greater than maximum value."))
        return tuple(issues)


__all__ = [
    "FILL_STYLE_CHOICES",
    "GUI_CONTROL_TYPES",
    "TEXT_ALIGNMENT_CHOICES",
    "GuiFieldSpec",
    "GuiValidationIssue",
    "KotorGuiDocument",
]
