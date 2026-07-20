"""Renderer-neutral preview contract for Odyssey ``.gui`` resources.

The standalone GUI Editor and Map Studio PIE are deliberately separate
products.  This module is the inward-facing seam between them: an editor may
compile a mutable PyKotor GUI object into an immutable snapshot, while PIE (or
any renderer) consumes only the snapshot/payload and never imports Qt or the
editor window.

Coordinates remain in the retail GUI's top-left pixel space.  No claim is made
that parsing a layout reproduces Odyssey's controller code, visibility rules,
or event dispatch; those runtime behaviours need their own evidence-backed
adapters.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


PIE_HUD_PREVIEW_SCHEMA = "ghoststudio.pie_hud_preview.v1"


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _rgba(value: object) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    channels = []
    for name, default in (("r", 0.0), ("g", 0.0), ("b", 0.0), ("a", 1.0)):
        channel = getattr(value, name, default)
        channels.append(_number(default if channel is None else channel, default))
    return tuple(channels)  # type: ignore[return-value]


def _point(value: object) -> tuple[float, float]:
    return _number(getattr(value, "x", 0.0)), _number(getattr(value, "y", 0.0))


def _enum_parts(value: object) -> tuple[str, int]:
    name = _text(getattr(value, "name", ""))
    number = _integer(getattr(value, "value", value), -1)
    return (name or ("Invalid" if number < 0 else f"Control{number}"), number)


def _json_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return _text(value)


@dataclass(frozen=True, slots=True)
class KotorGuiBorderSnapshot:
    """Texture and draw policy retained from one GUI border-like structure."""

    corner: str = ""
    edge: str = ""
    fill: str = ""
    fill_style: int = 0
    dimension: int = 0
    inner_offset: int | None = None
    inner_offset_y: int | None = None
    pulsing: int | None = None
    color_rgba: tuple[float, float, float, float] | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "corner": self.corner,
            "edge": self.edge,
            "fill": self.fill,
            "fill_style": self.fill_style,
            "dimension": self.dimension,
            "inner_offset": self.inner_offset,
            "inner_offset_y": self.inner_offset_y,
            "pulsing": self.pulsing,
            "color_rgba": list(self.color_rgba) if self.color_rgba is not None else None,
        }


@dataclass(frozen=True, slots=True)
class KotorGuiTextSnapshot:
    """Retail text declaration without TLK resolution or runtime substitution."""

    value: str = ""
    strref: int = -1
    font: str = ""
    alignment: int = 0
    pulsing: int | None = None
    color_rgba: tuple[float, float, float, float] | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "value": self.value,
            "strref": self.strref,
            "font": self.font,
            "alignment": self.alignment,
            "pulsing": self.pulsing,
            "color_rgba": list(self.color_rgba) if self.color_rgba is not None else None,
        }


@dataclass(frozen=True, slots=True)
class KotorGuiControlSnapshot:
    """One immutable GUI control in retail top-left pixel coordinates."""

    key: str
    parent_key: str
    child_keys: tuple[str, ...]
    path: tuple[int, ...]
    tag: str
    control_id: int | None
    control_type: str
    control_type_id: int
    left: float
    top: float
    width: float
    height: float
    locked: bool | None
    color_rgba: tuple[float, float, float, float] | None
    border: KotorGuiBorderSnapshot | None
    highlight: KotorGuiBorderSnapshot | None
    selected: KotorGuiBorderSnapshot | None
    highlight_selected: KotorGuiBorderSnapshot | None
    progress: KotorGuiBorderSnapshot | None
    text: KotorGuiTextSnapshot | None
    navigation: tuple[tuple[str, int], ...]
    properties: tuple[tuple[str, object], ...]
    texture_resrefs: tuple[str, ...]

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    def scaled_extent(
        self,
        source_width: float,
        source_height: float,
        target_width: float,
        target_height: float,
    ) -> tuple[float, float, float, float]:
        """Return this extent scaled into a target top-left pixel space."""

        if source_width <= 0 or source_height <= 0:
            raise ValueError("GUI source dimensions must be positive")
        scale_x = float(target_width) / float(source_width)
        scale_y = float(target_height) / float(source_height)
        return (
            self.left * scale_x,
            self.top * scale_y,
            self.width * scale_x,
            self.height * scale_y,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "parent_key": self.parent_key,
            "child_keys": list(self.child_keys),
            "path": list(self.path),
            "tag": self.tag,
            "control_id": self.control_id,
            "control_type": self.control_type,
            "control_type_id": self.control_type_id,
            "extent": [self.left, self.top, self.width, self.height],
            "locked": self.locked,
            "color_rgba": list(self.color_rgba) if self.color_rgba is not None else None,
            "border": self.border.to_payload() if self.border is not None else None,
            "highlight": self.highlight.to_payload() if self.highlight is not None else None,
            "selected": self.selected.to_payload() if self.selected is not None else None,
            "highlight_selected": (
                self.highlight_selected.to_payload() if self.highlight_selected is not None else None
            ),
            "progress": self.progress.to_payload() if self.progress is not None else None,
            "text": self.text.to_payload() if self.text is not None else None,
            "navigation": {key: value for key, value in self.navigation},
            "properties": {key: _json_value(value) for key, value in self.properties},
            "texture_resrefs": list(self.texture_resrefs),
        }


@dataclass(frozen=True, slots=True)
class KotorGuiPreviewSnapshot:
    """Immutable GUI definition shared by authoring and runtime previews."""

    game: str
    resref: str
    source_kind: str
    source_width: int
    source_height: int
    root_keys: tuple[str, ...]
    controls: tuple[KotorGuiControlSnapshot, ...]
    schema: str = PIE_HUD_PREVIEW_SCHEMA

    def __post_init__(self) -> None:
        game = self.game.strip().upper()
        if game not in {"K1", "K2"}:
            raise ValueError(f"Unsupported KOTOR game tag: {self.game!r}")
        if not self.resref.strip():
            raise ValueError("GUI resref cannot be blank")
        if self.source_width <= 0 or self.source_height <= 0:
            raise ValueError("GUI source dimensions must be positive")
        keys = tuple(control.key for control in self.controls)
        if len(keys) != len(set(keys)):
            raise ValueError("GUI preview control keys must be unique")
        known = set(keys)
        if any(key not in known for key in self.root_keys):
            raise ValueError("GUI preview root key does not identify a control")
        object.__setattr__(self, "game", game)
        object.__setattr__(self, "resref", self.resref.strip().lower())
        object.__setattr__(self, "source_kind", self.source_kind.strip() or "editable_gui")

    def control(self, key: str) -> KotorGuiControlSnapshot | None:
        return next((control for control in self.controls if control.key == key), None)

    def absolute_extent(self, key: str) -> tuple[float, float, float, float]:
        """Return a control extent in root GUI pixel space.

        Odyssey child extents are parent-local.  The reference Electron editor
        expresses that by nesting absolutely positioned elements; the Qt and
        PIE consumers use this explicit equivalent.
        """

        control = self.control(key)
        if control is None:
            raise KeyError(key)
        left, top = control.left, control.top
        parent_key = control.parent_key
        visited = {control.key}
        while parent_key:
            if parent_key in visited:
                raise ValueError("GUI control hierarchy contains a cycle")
            visited.add(parent_key)
            parent = self.control(parent_key)
            if parent is None:
                raise ValueError(f"GUI control {control.key!r} has missing parent {parent_key!r}")
            left += parent.left
            top += parent.top
            parent_key = parent.parent_key
        return left, top, control.width, control.height

    def to_pie_payload(self) -> dict[str, object]:
        """Return a JSON-safe value that PIE can consume without editor imports."""

        payload: dict[str, object] = {
            "schema": self.schema,
            "source": {
                "kind": self.source_kind,
                "game": self.game,
                "resref": self.resref,
                "canvas": [self.source_width, self.source_height],
            },
            "root_keys": list(self.root_keys),
            "controls": [control.to_payload() for control in self.controls],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        payload["revision"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload


def _optional_int(value: object) -> int | None:
    return None if value is None else _integer(value)


def _border_snapshot(value: object) -> KotorGuiBorderSnapshot | None:
    if value is None or isinstance(value, (bool, int, float, str)):
        return None
    return KotorGuiBorderSnapshot(
        corner=_text(getattr(value, "corner", "")),
        edge=_text(getattr(value, "edge", "")),
        fill=_text(getattr(value, "fill", "")),
        fill_style=_integer(getattr(value, "fill_style", 0)),
        dimension=_integer(getattr(value, "dimension", 0)),
        inner_offset=_optional_int(getattr(value, "inner_offset", None)),
        inner_offset_y=_optional_int(getattr(value, "inner_offset_y", None)),
        pulsing=_optional_int(getattr(value, "pulsing", None)),
        color_rgba=_rgba(getattr(value, "color", None)),
    )


def _text_snapshot(value: object) -> KotorGuiTextSnapshot | None:
    if value is None:
        return None
    return KotorGuiTextSnapshot(
        value=_text(getattr(value, "text", "")),
        strref=_integer(getattr(value, "strref", -1), -1),
        font=_text(getattr(value, "font", "")),
        alignment=_integer(getattr(value, "alignment", 0)),
        pulsing=_optional_int(getattr(value, "pulsing", None)),
        color_rgba=_rgba(getattr(value, "color", None)),
    )


def _texture_resrefs(control: object, borders: Iterable[KotorGuiBorderSnapshot | None]) -> tuple[str, ...]:
    values: list[str] = []
    for border in borders:
        if border is None:
            continue
        values.extend((border.corner, border.edge, border.fill))
    for name in ("thumb", "gui_thumb", "gui_direction"):
        item = getattr(control, name, None)
        values.append(_text(getattr(item, "image", "")))
    scroll_bar = getattr(control, "scroll_bar", None)
    if scroll_bar is not None:
        for name in ("thumb", "gui_thumb", "gui_direction"):
            item = getattr(scroll_bar, name, None)
            values.append(_text(getattr(item, "image", "")))
    return tuple(dict.fromkeys(value.strip().lower() for value in values if value and value.strip()))


@dataclass(frozen=True, slots=True)
class DecodedKotorGuiTexture:
    """Top-down RGBA pixels ready for a GUI renderer."""

    width: int
    height: int
    rgba: bytes
    txi: str = ""


def decode_kotor_gui_texture(data: bytes, *, max_size: int = 512) -> DecodedKotorGuiTexture:
    """Decode TPC/TGA bytes without taking a Qt or GPU dependency.

    PyKotor yields DXT mipmaps in top-down order and uncompressed TPC data in
    bottom-up order.  GUI canvas consumers need top-down pixels, so only the
    latter path is flipped here.  A suitable authored mip is selected before
    conversion to keep retail UI loading responsive.
    """

    if not data:
        raise ValueError("Texture data is empty")
    # Loose Override resources may supply TGA instead of TPC.  Pillow handles
    # TGA origin bits and channel order, while the PyKotor path below retains
    # authored TPC mip selection and DXT handling.
    from io import BytesIO
    from PIL import Image

    try:
        loose_image = Image.open(BytesIO(data))
        if str(loose_image.format or "").upper() == "TGA":
            loose_image = loose_image.convert("RGBA")
            limit = max(1, int(max_size))
            if max(loose_image.size) > limit:
                resampling = getattr(Image, "Resampling", Image)
                loose_image.thumbnail((limit, limit), resampling.LANCZOS)
            return DecodedKotorGuiTexture(
                width=int(loose_image.width),
                height=int(loose_image.height),
                rgba=bytes(loose_image.tobytes("raw", "RGBA")),
            )
    except Exception:
        pass
    from pykotor.resource.formats.tpc import read_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat

    texture = read_tpc(bytes(data))
    original_format = texture.format()
    mipmaps = tuple(texture.layers[0].mipmaps) if texture.layers else ()
    if not mipmaps:
        raise ValueError("TPC texture has no mipmaps")
    limit = max(1, int(max_size))
    mip = mipmaps[-1]
    for candidate in mipmaps:
        if max(int(candidate.width), int(candidate.height)) <= limit:
            mip = candidate
            break
    working = mip.copy()
    working.convert(TPCTextureFormat.RGBA)
    image = working.to_pil_image()
    if image is None:
        raise ValueError("PyKotor could not decode the texture")
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    compressed = original_format in {
        TPCTextureFormat.DXT1,
        TPCTextureFormat.DXT3,
        TPCTextureFormat.DXT5,
    }
    if not compressed:
        transpose = getattr(Image, "Transpose", Image)
        image = image.transpose(transpose.FLIP_TOP_BOTTOM)
    return DecodedKotorGuiTexture(
        width=int(image.width),
        height=int(image.height),
        rgba=bytes(image.tobytes("raw", "RGBA")),
        txi=str(getattr(texture, "txi", "") or ""),
    )


def _runtime_properties(control: object) -> tuple[tuple[str, object], ...]:
    values: dict[str, object] = {}
    supplied = getattr(control, "properties", None)
    if isinstance(supplied, Mapping):
        values.update({str(key): _json_value(value) for key, value in supplied.items()})
    for name in (
        "current_value",
        "max_value",
        "visible_value",
        "start_from_left",
        "padding",
        "looping",
        "left_scrollbar",
        "draw_mode",
        "is_selected",
        "horizontal",
    ):
        value = getattr(control, name, None)
        if value is not None:
            values[name] = _json_value(value)
    return tuple(sorted(values.items()))


def _navigation(control: object) -> tuple[tuple[str, int], ...]:
    moveto = getattr(control, "moveto", None)
    if moveto is None:
        return ()
    return tuple((name, _integer(getattr(moveto, name, -1), -1)) for name in ("up", "down", "left", "right"))


def _roots(gui: object) -> tuple[object, ...]:
    root = getattr(gui, "root", None)
    if root is not None:
        return (root,)
    controls = getattr(gui, "controls", ())
    return tuple(controls or ())


def infer_kotor_gui_source_size(
    gui: object,
    *,
    fallback_width: int = 640,
    fallback_height: int = 480,
) -> tuple[int, int]:
    """Infer the retail canvas, preferring the root panel's clipping extent."""

    roots = _roots(gui)
    if len(roots) == 1:
        root_width, root_height = _point(getattr(roots[0], "size", None))
        if root_width > 0 and root_height > 0:
            # Retail layouts may park hidden or clipped controls outside the
            # root panel (for example K2 ``maininterface_p`` party slot 4 and
            # its 512px map backing).  Those must not enlarge the canvas.
            return int(math.ceil(root_width)), int(math.ceil(root_height))

    max_right = float(max(1, fallback_width))
    max_bottom = float(max(1, fallback_height))

    def visit(control: object) -> None:
        nonlocal max_right, max_bottom
        left, top = _point(getattr(control, "position", None))
        width, height = _point(getattr(control, "size", None))
        max_right = max(max_right, left + max(0.0, width))
        max_bottom = max(max_bottom, top + max(0.0, height))
        for child in tuple(getattr(control, "children", ()) or ()):
            visit(child)

    for root in roots:
        visit(root)
    return int(math.ceil(max_right)), int(math.ceil(max_bottom))


def compile_kotor_gui_preview(
    gui: object,
    *,
    game: str,
    resref: str,
    source_width: int | None = None,
    source_height: int | None = None,
    source_kind: str = "retail_gui",
) -> KotorGuiPreviewSnapshot:
    """Compile a PyKotor-compatible GUI object into the shared PIE contract."""

    if source_width is None or source_height is None:
        inferred_width, inferred_height = infer_kotor_gui_source_size(gui)
        source_width = inferred_width if source_width is None else source_width
        source_height = inferred_height if source_height is None else source_height

    compiled: list[KotorGuiControlSnapshot] = []

    def visit(control: object, path: tuple[int, ...], parent_key: str) -> str:
        key = "control:" + ".".join(str(index) for index in path)
        children = tuple(getattr(control, "children", ()) or ())
        child_keys = tuple(f"{key}.{index}" for index in range(len(children)))
        left, top = _point(getattr(control, "position", None))
        width, height = _point(getattr(control, "size", None))
        type_name, type_id = _enum_parts(getattr(control, "gui_type", -1))
        border = _border_snapshot(getattr(control, "border", None))
        highlight = _border_snapshot(getattr(control, "hilight", None))
        selected = _border_snapshot(getattr(control, "selected", None))
        highlight_selected = _border_snapshot(getattr(control, "hilight_selected", None))
        progress = _border_snapshot(getattr(control, "progress", None))
        control_id_raw = getattr(control, "id", None)
        locked_raw = getattr(control, "locked", None)
        row = KotorGuiControlSnapshot(
            key=key,
            parent_key=parent_key,
            child_keys=child_keys,
            path=path,
            tag=_text(getattr(control, "tag", "")),
            control_id=None if control_id_raw is None else _integer(control_id_raw),
            control_type=type_name,
            control_type_id=type_id,
            left=left,
            top=top,
            width=width,
            height=height,
            locked=None if locked_raw is None else bool(locked_raw),
            color_rgba=_rgba(getattr(control, "color", None)),
            border=border,
            highlight=highlight,
            selected=selected,
            highlight_selected=highlight_selected,
            progress=progress,
            text=_text_snapshot(getattr(control, "gui_text", None)),
            navigation=_navigation(control),
            properties=_runtime_properties(control),
            texture_resrefs=_texture_resrefs(
                control,
                (border, highlight, selected, highlight_selected, progress),
            ),
        )
        compiled.append(row)
        for index, child in enumerate(children):
            visit(child, path + (index,), key)
        return key

    root_keys = tuple(visit(root, (index,), "") for index, root in enumerate(_roots(gui)))
    return KotorGuiPreviewSnapshot(
        game=game,
        resref=resref,
        source_kind=source_kind,
        source_width=int(source_width),
        source_height=int(source_height),
        root_keys=root_keys,
        controls=tuple(compiled),
    )


__all__ = [
    "DecodedKotorGuiTexture",
    "PIE_HUD_PREVIEW_SCHEMA",
    "KotorGuiBorderSnapshot",
    "KotorGuiControlSnapshot",
    "KotorGuiPreviewSnapshot",
    "KotorGuiTextSnapshot",
    "compile_kotor_gui_preview",
    "decode_kotor_gui_texture",
    "infer_kotor_gui_source_size",
]
