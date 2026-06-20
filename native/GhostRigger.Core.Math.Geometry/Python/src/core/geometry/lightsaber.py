"""Lightsaber render helpers.

KotOR lightsaber MDLs often use ordinary trimesh blade planes with textures
named like ``w_lsabreblue01`` or ``w_lsabresilv01`` rather than NODE_SABER
flags.  These helpers keep that material policy centralized so renderers do
not need to duplicate brittle texture-name checks.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable


_BLADE_TEXTURE_MARKERS = (
    "w_lsabre",
    "lsabre",
    "sabreglow",
    "sabreblade",
    "saberblade",
)

_BLADE_COLOR_OVERRIDE_ATTR = "_gr_lightsaber_blade_color_override"


@dataclass(frozen=True)
class LightsaberBladeColor:
    """A preview colour from the KOTOR lightsaber crystal palette."""

    id: str
    label: str
    aliases: tuple[str, ...]
    emissive_rgb: tuple[float, float, float]


LIGHTSABER_BLADE_COLORS: tuple[LightsaberBladeColor, ...] = (
    LightsaberBladeColor("blue", "Blue", ("blue",), (0.18, 0.55, 1.90)),
    LightsaberBladeColor("green", "Green", ("green", "gren"), (0.22, 1.75, 0.35)),
    LightsaberBladeColor("red", "Red", ("red", "sith"), (1.85, 0.18, 0.10)),
    LightsaberBladeColor("yellow", "Yellow", ("yelo", "yellow"), (1.85, 1.45, 0.22)),
    LightsaberBladeColor("violet", "Violet", ("purple", "violet", "purp", "prpl", "viol"), (1.35, 0.40, 1.90)),
    LightsaberBladeColor("viridian", "Viridian", ("viridian", "vird", "vrid", "dgrn"), (0.36, 1.80, 0.92)),
    LightsaberBladeColor("cyan", "Cyan", ("cyan", "aqua", "turq"), (0.35, 1.55, 1.95)),
    LightsaberBladeColor("orange", "Orange", ("orange", "org", "gold"), (1.90, 0.75, 0.16)),
    LightsaberBladeColor("bronze", "Bronze", ("bronze", "brnz"), (1.80, 1.05, 0.28)),
    LightsaberBladeColor("silver", "Silver", ("silv", "silver", "white"), (1.45, 1.65, 1.95)),
)

_BLADE_COLOR_BY_ID = {color.id: color for color in LIGHTSABER_BLADE_COLORS}

_BLADE_COLOR_HINTS: tuple[tuple[tuple[str, ...], tuple[float, float, float]], ...] = tuple(
    sorted(
        (
            (color.aliases, color.emissive_rgb)
            for color in LIGHTSABER_BLADE_COLORS
            if color.id != "silver"
        ),
        key=lambda item: max(len(alias) for alias in item[0]),
        reverse=True,
    )
)

_BLADE_NEUTRAL_COLOR_HINTS: tuple[tuple[tuple[str, ...], tuple[float, float, float]], ...] = (
    (_BLADE_COLOR_BY_ID["silver"].aliases, _BLADE_COLOR_BY_ID["silver"].emissive_rgb),
)

_BLADE_MODEL_COLOR_HINTS: tuple[tuple[tuple[str, ...], tuple[float, float, float]], ...] = (
    # K2 short saber 009 uses a neutral/silver blade mask texture name but is
    # the yellow blade variant in-game.  Prefer the model/hilt suffix over the
    # neutral mask so missing-texture previews still match the actual item.
    (("w_shortsbr_009", "lghtsbr09", "shortsbr09"), (1.85, 1.45, 0.22)),
)


def _clean(value: Any) -> str:
    return str(value or "").replace("\x00", "").strip().lower()


def _finite_vertex3(value: Any) -> tuple[float, float, float] | None:
    try:
        vertex = (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None
    if not all(math.isfinite(coord) for coord in vertex):
        return None
    return vertex


def _context_text(node: Any) -> str:
    parts: list[str] = []
    current = node
    for _ in range(8):
        if current is None:
            break
        parts.append(_clean(getattr(current, "name", "")))
        parts.append(_clean(getattr(current, "texture", "")))
        for texture_name in list(getattr(current, "texture_names", []) or []):
            parts.append(_clean(texture_name))
        current = getattr(current, "parent", None)
    return " ".join(part for part in parts if part)


def lightsaber_blade_color_choices() -> tuple[LightsaberBladeColor, ...]:
    """Return game-palette blade colours supported by the preview renderer."""

    return LIGHTSABER_BLADE_COLORS


def _normalize_color_id(color_id: str | None) -> str | None:
    if color_id is None:
        return None
    clean = _clean(color_id).replace(" ", "_")
    if clean in {"", "auto", "default", "model"}:
        return None
    if clean == "purple":
        clean = "violet"
    if clean not in _BLADE_COLOR_BY_ID:
        valid = ", ".join(color.id for color in LIGHTSABER_BLADE_COLORS)
        raise ValueError(f"Unsupported lightsaber blade color '{color_id}'. Valid colors: {valid}.")
    return clean


def _iter_model_nodes(model: Any) -> Iterable[Any]:
    if model is None:
        return ()
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        try:
            return tuple(all_nodes())
        except Exception:
            return ()
    root = getattr(model, "root_node", None)
    if root is None:
        return ()
    result: list[Any] = []
    stack = [root]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        result.append(current)
        stack.extend(reversed(list(getattr(current, "children", []) or [])))
    return tuple(result)


def is_lightsaber_model(model: Any) -> bool:
    """Return True when a model contains KOTOR lightsaber blade geometry."""

    if model is None:
        return False
    classification = _clean(getattr(model, "classification", ""))
    if classification == "lightsaber":
        return True
    return any(is_lightsaber_blade_node(node) for node in _iter_model_nodes(model))


def lightsaber_blade_color_override(node: Any) -> str | None:
    """Return the preview colour override inherited by a blade node, if any."""

    current = node
    for _ in range(12):
        if current is None:
            break
        value = getattr(current, _BLADE_COLOR_OVERRIDE_ATTR, None)
        if value:
            try:
                return _normalize_color_id(value)
            except ValueError:
                return None
        current = getattr(current, "parent", None)
    return None


def set_lightsaber_blade_color_override(model: Any, color_id: str | None) -> str | None:
    """Set a non-destructive preview blade colour override on a lightsaber model.

    The override is stored on runtime nodes only. It does not rename textures or
    mutate MDL/MDX source data, and clearing it returns the renderer to
    model/texture-derived colour detection.
    """

    normalized = _normalize_color_id(color_id)
    for node in _iter_model_nodes(model):
        try:
            if normalized is None:
                if hasattr(node, _BLADE_COLOR_OVERRIDE_ATTR):
                    delattr(node, _BLADE_COLOR_OVERRIDE_ATTR)
            else:
                setattr(node, _BLADE_COLOR_OVERRIDE_ATTR, normalized)
            if is_lightsaber_blade_node(node):
                setattr(node, "_gr_revision", int(getattr(node, "_gr_revision", 0) or 0) + 1)
        except Exception:
            continue
    return normalized


def is_lightsaber_blade_node(node: Any) -> bool:
    """Return True for visible blade/glow mesh nodes.

    The hilt mesh on ``w_shortsbr_009`` is named ``LghtSbr09`` but uses a hilt
    texture, so this intentionally keys primarily off the blade texture family.
    """
    if bool(getattr(node, "is_saber", False)):
        return True
    texture_names = list(getattr(node, "texture_names", []) or [])
    texture_names.append(getattr(node, "texture", ""))
    for texture_name in texture_names:
        clean = _clean(texture_name)
        if clean and any(marker in clean for marker in _BLADE_TEXTURE_MARKERS):
            return True
    return False


def lightsaber_blade_emissive_rgb(node: Any) -> tuple[float, float, float]:
    """Return a bright RGB self-illumination hint for a saber blade node."""
    override = lightsaber_blade_color_override(node)
    if override is not None:
        return _BLADE_COLOR_BY_ID[override].emissive_rgb
    joined = _context_text(node)
    for needles, rgb in _BLADE_COLOR_HINTS:
        if any(needle in joined for needle in needles):
            return rgb
    for needles, rgb in _BLADE_MODEL_COLOR_HINTS:
        if any(needle in joined for needle in needles):
            return rgb
    for needles, rgb in _BLADE_NEUTRAL_COLOR_HINTS:
        if any(needle in joined for needle in needles):
            return rgb
    return (0.60, 1.15, 1.80)


def lightsaber_blade_diffuse_rgb(node: Any) -> tuple[float, float, float]:
    """Return a sane diffuse tint for missing-texture blade fallbacks."""
    r, g, b = lightsaber_blade_emissive_rgb(node)
    peak = max(r, g, b, 1.0)
    return (min(1.0, r / peak), min(1.0, g / peak), min(1.0, b / peak))


def lightsaber_blade_texture_cache_key(node: Any) -> str:
    """Return a stable cache key for a generated blade texture."""
    r, g, b = lightsaber_blade_emissive_rgb(node)
    override = lightsaber_blade_color_override(node) or "model"
    return f"__lightsaber_blade__:{override}:{r:.3f}:{g:.3f}:{b:.3f}"


def should_use_procedural_lightsaber_blade_texture(node: Any, *, texture_missing: bool) -> bool:
    """Return True when the renderer should synthesize the blade mask.

    Stock KotOR lightsaber blade textures are opaque RGB glow masks with no TXI
    metadata.  Rendering them literally makes the result highly dependent on the
    current diffuse/alpha path and can leave some models looking unpowered.  The
    preview renderer instead synthesizes one additive blade mask for every
    detected blade plane, using the authored texture/model name only as the
    game-colour hint.  Missing textures and preview colour overrides therefore
    behave the same as normal game-library saber variants.
    """

    return is_lightsaber_blade_node(node)


def lightsaber_blade_procedural_rgba8(
    node: Any,
    *,
    width: int = 64,
    height: int = 256,
) -> tuple[int, int, bytes]:
    """Generate an additive lightsaber blade mask.

    Real KOTOR saber blades rely on a transparent/glow texture.  Some installs
    or partial resource paths do not resolve that texture, and a white 1x1
    fallback turns the four blade planes into opaque rectangles.  This generated
    texture gives missing blade masks a narrow bright core with a colored falloff
    whose RGB fades to black at the edges, so additive blending contributes glow
    instead of a solid panel.
    """

    try:
        width_value = int(width)
    except Exception:
        width_value = 64
    try:
        height_value = int(height)
    except Exception:
        height_value = 256
    width = max(8, min(512, width_value))
    height = max(16, min(2048, height_value))
    er, eg, eb = lightsaber_blade_emissive_rgb(node)
    peak = max(er, eg, eb, 1.0)
    glow = (er / peak, eg / peak, eb / peak)
    pixels = bytearray(width * height * 4)

    def smoothstep(edge0: float, edge1: float, value: float) -> float:
        if edge0 == edge1:
            return 1.0 if value >= edge1 else 0.0
        t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
        return t * t * (3.0 - 2.0 * t)

    for y in range(height):
        v = (y + 0.5) / float(height)
        tip_fade = smoothstep(0.00, 0.06, v) * (1.0 - smoothstep(0.94, 1.0, v))
        for x in range(width):
            u = (x + 0.5) / float(width)
            dist = abs(u - 0.5) * 2.0
            core = max(0.0, 1.0 - dist / 0.115) ** 1.35
            aura = max(0.0, 1.0 - dist) ** 2.15
            alpha = max(0.0, min(1.0, (core * 0.96 + aura * 0.46) * tip_fade))

            r = (glow[0] * aura * 0.95 + core * 1.18) * tip_fade
            g = (glow[1] * aura * 0.95 + core * 1.10) * tip_fade
            b = (glow[2] * aura * 0.95 + core * 0.82) * tip_fade
            if alpha < 0.01:
                r = g = b = alpha = 0.0

            idx = (y * width + x) * 4
            pixels[idx + 0] = int(max(0.0, min(1.0, r)) * 255)
            pixels[idx + 1] = int(max(0.0, min(1.0, g)) * 255)
            pixels[idx + 2] = int(max(0.0, min(1.0, b)) * 255)
            pixels[idx + 3] = int(max(0.0, min(1.0, alpha)) * 255)

    return width, height, bytes(pixels)


def synthetic_lightsaber_blade_uvs(
    vertices: Iterable[Any],
    *,
    edge_inset: float = 0.0,
) -> list[tuple[float, float]]:
    """Create UVs for blade planes that omit texture vertices.

    K2 ``w_shortsbr_009`` has two glow planes with no UV array.  Sampling the
    center of the blade texture for every vertex makes those planes solid.  Map
    the widest local axis to U and the longest local axis to V so the procedural
    blade texture can fade across the blade width and taper along its length.
    """

    verts: list[tuple[float, float, float]] = []
    for vertex in vertices or []:
        finite_vertex = _finite_vertex3(vertex)
        if finite_vertex is not None:
            verts.append(finite_vertex)
    if not verts:
        return []

    mins = [min(v[i] for v in verts) for i in range(3)]
    maxs = [max(v[i] for v in verts) for i in range(3)]
    spans = [maxs[i] - mins[i] for i in range(3)]
    length_axis = max(range(3), key=lambda idx: spans[idx])
    width_candidates = [idx for idx in range(3) if idx != length_axis]
    width_axis = max(width_candidates, key=lambda idx: spans[idx])
    length_span = spans[length_axis] if spans[length_axis] > 1e-8 else 1.0
    width_span = spans[width_axis] if spans[width_axis] > 1e-8 else 1.0

    inset = max(0.0, min(0.45, float(edge_inset or 0.0)))
    u_scale = 1.0 - inset * 2.0
    result: list[tuple[float, float]] = []
    for vertex in verts:
        u = max(0.0, min(1.0, (vertex[width_axis] - mins[width_axis]) / width_span))
        v = max(0.0, min(1.0, (vertex[length_axis] - mins[length_axis]) / length_span))
        if inset > 0.0:
            u = inset + u * u_scale
        result.append((u, v))
    return result


def lightsaber_blade_preview_quad(
    vertices: Iterable[Any],
    *,
    edge_inset: float = 0.32,
) -> tuple[
    list[tuple[float, float, float]],
    list[tuple[float, float]],
    list[tuple[int, int, int]],
    tuple[float, float, float],
] | None:
    """Build a smooth preview quad from a stock lightsaber blade node.

    Several K1/K2 saber variants store blade planes as sparse segmented strips
    and omit UV arrays. Rendering those triangles literally makes the viewport
    show a dotted or invisible blade. For preview only, derive a single filled
    plane from the authored local bounds; the MDL node and export data remain
    untouched.
    """

    verts: list[tuple[float, float, float]] = []
    for vertex in vertices or []:
        finite_vertex = _finite_vertex3(vertex)
        if finite_vertex is not None:
            verts.append(finite_vertex)
    if len(verts) < 3:
        return None

    mins = [min(v[i] for v in verts) for i in range(3)]
    maxs = [max(v[i] for v in verts) for i in range(3)]
    spans = [maxs[i] - mins[i] for i in range(3)]
    length_axis = max(range(3), key=lambda idx: spans[idx])
    width_candidates = [idx for idx in range(3) if idx != length_axis]
    width_axis = max(width_candidates, key=lambda idx: spans[idx])
    depth_axis = next(idx for idx in range(3) if idx not in {length_axis, width_axis})
    if spans[length_axis] <= 1e-8 or spans[width_axis] <= 1e-8:
        return None

    center_depth = (mins[depth_axis] + maxs[depth_axis]) * 0.5
    width_mid = (mins[width_axis] + maxs[width_axis]) * 0.5
    half_width = spans[width_axis] * 0.5
    # Slightly overdraw the authored plane so the preview reads like KOTOR's
    # glow rather than a mathematically thin card.
    half_width *= 1.18
    width_min = width_mid - half_width
    width_max = width_mid + half_width

    def point(width_value: float, length_value: float) -> tuple[float, float, float]:
        coords = [0.0, 0.0, 0.0]
        coords[width_axis] = width_value
        coords[length_axis] = length_value
        coords[depth_axis] = center_depth
        return (coords[0], coords[1], coords[2])

    inset = max(0.0, min(0.45, float(edge_inset or 0.0)))
    vertices_out = [
        point(width_min, mins[length_axis]),
        point(width_max, mins[length_axis]),
        point(width_min, maxs[length_axis]),
        point(width_max, maxs[length_axis]),
    ]
    uvs_out = [
        (inset, 0.0),
        (1.0 - inset, 0.0),
        (inset, 1.0),
        (1.0 - inset, 1.0),
    ]
    normal = [0.0, 0.0, 0.0]
    normal[depth_axis] = 1.0
    return vertices_out, uvs_out, [(0, 1, 2), (1, 3, 2)], (normal[0], normal[1], normal[2])
