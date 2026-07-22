"""Pascal-inspired direct building policy for Map Studio.

The viewport owns clicks and preview feedback; this headless module turns a
closed wall path into durable KMAP room intent. It deliberately compiles to
Ghost Studio's existing Odyssey floor-plan/MDL/WOK path rather than inventing a
runtime building format that KOTOR cannot consume.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, normalise_resref
from .authored_room_floorplan import (
    FloorPlanRoomPrimitive,
    polygon_signed_area,
    validate_floor_plan_room_primitive,
)
from .authored_room_operations import set_authored_floor_plan_wall_opening
from .authored_room_primitives import PrimitiveMaterial
from .authored_room_materials import normalize_authored_room_texture


@dataclass(frozen=True)
class PascalBuildingLevel:
    level_index: int
    name: str
    floor_z: float
    room_resrefs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PascalBuildingStyle:
    style_id: str
    label: str
    game: str
    floor_texture: str
    wall_texture: str
    ceiling_texture: str
    source_module: str = ""
    source_room: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PascalOpeningPreview:
    """Resolved hosted-opening candidate shared by viewport preview and commit."""

    room_resref: str
    edge_index: int
    opening_kind: str
    center_fraction: float
    width: float
    height: float
    bottom: float
    valid: bool
    reason: str = ""


_DEFAULT_STYLES = (
    PascalBuildingStyle(
        style_id="plcaa_graybox",
        label="PLCaa Neutral Blockout",
        game="BOTH",
        floor_texture="ruler01",
        wall_texture="ruler01",
        ceiling_texture="ruler01",
        source_module="plcaa",
        tags=("blockout", "neutral", "plcaa"),
    ),
)

_VANILLA_STYLE_SCHEMA = "ghostrigger.map-building-style-vanilla/v1"
_VANILLA_STYLE_RELATIVE = Path("assets/map_studio/environment_kits/vanilla_styles.json")


def _candidate_roots() -> tuple[Path, ...]:
    candidates = [Path.cwd(), Path(sys.executable).resolve().parent]
    try:
        candidates.extend(Path(__file__).resolve().parents)
    except (OSError, RuntimeError):
        pass
    result: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in result:
            result.append(resolved)
    return tuple(result)


def vanilla_pascal_style_catalog_path(*, writable: bool = False) -> Path:
    configured = str(os.environ.get("GHOSTRIGGER_BUILDING_STYLE_CATALOG", "") or "").strip()
    candidates = [Path(configured)] if configured else []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "GhostStudio" / "cache" / "vanilla_building_styles.json")
    candidates.extend(root / _VANILLA_STYLE_RELATIVE for root in _candidate_roots())
    if not writable:
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    if local:
        return Path(local) / "GhostStudio" / "cache" / "vanilla_building_styles.json"
    return Path.cwd() / _VANILLA_STYLE_RELATIVE


@lru_cache(maxsize=2)
def vanilla_pascal_building_styles(path_text: str = "") -> tuple[PascalBuildingStyle, ...]:
    path = Path(path_text) if path_text else vanilla_pascal_style_catalog_path()
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ()
    if str(payload.get("schema") or "") != _VANILLA_STYLE_SCHEMA:
        return ()
    result: list[PascalBuildingStyle] = []
    for raw in tuple(payload.get("styles") or ()):
        row = dict(raw or {})
        style_id = str(row.get("style_id") or "").strip().lower()
        game = str(row.get("game") or "").strip().upper()
        wall = str(row.get("wall_texture") or "").strip().lower()
        if not style_id or game not in {"K1", "K2"} or not wall:
            continue
        result.append(
            PascalBuildingStyle(
                style_id=style_id,
                label=str(row.get("label") or style_id),
                game=game,
                floor_texture=str(row.get("floor_texture") or wall).strip().lower(),
                wall_texture=wall,
                ceiling_texture=str(row.get("ceiling_texture") or wall).strip().lower(),
                source_module=str(row.get("source_module") or "").strip().lower(),
                source_room=str(row.get("source_room") or "").strip().lower(),
                tags=tuple(str(value) for value in tuple(row.get("tags") or ()) if str(value).strip()),
            )
        )
    return tuple(result)


def _surface_texture(surface: Any) -> str:
    texture = str(getattr(surface, "texture", "") or "").strip().lower()
    if texture:
        return texture
    return next(
        (
            str(value or "").strip().lower()
            for value in tuple(getattr(surface, "texture_names", ()) or ())
            if str(value or "").strip()
        ),
        "",
    )


def _building_surface_role(surface: Any) -> str:
    name = str(getattr(surface, "name", "") or "").strip().lower()
    texture = _surface_texture(surface)
    text = f"{name} {texture}"
    if any(word in text for word in ("ceil", "ceiling", "roof", "overhead", "upper")):
        return "ceiling"
    if any(word in text for word in ("floor", "ground", "grnd", "walk", "deck", "path", "road", "carpet")):
        return "floor"
    if any(word in text for word in ("wall", "panel", "corr", "bulkhead", "side", "column", "pillar", "trim")):
        return "wall"
    normals = tuple(getattr(surface, "normals", ()) or ())
    if normals:
        sample = normals[:: max(1, len(normals) // 128)]
        mean_z = sum(float(normal[2]) for normal in sample) / max(1, len(sample))
        if mean_z > 0.55:
            return "floor"
        if mean_z < -0.55:
            return "ceiling"
    return "wall"


def scan_vanilla_pascal_building_styles(
    resource_manager: Any,
    *,
    games: tuple[str, ...] = ("K1", "K2"),
    progress: Any = None,
) -> tuple[PascalBuildingStyle, ...]:
    """Learn reusable floor/wall/ceiling palettes from installed vanilla rooms."""

    from .map_studio_terrain_kit import _base_game_lyt_rooms

    tasks: list[tuple[str, str, str]] = []
    for game in tuple(dict.fromkeys(str(value or "").strip().upper() for value in games)):
        if game not in {"K1", "K2"}:
            continue
        for room_resref, module_resref in sorted(_base_game_lyt_rooms(resource_manager, game, outdoor_only=False).items()):
            tasks.append((game, module_resref, room_resref))
    candidates: list[PascalBuildingStyle] = []
    total = len(tasks)
    for ordinal, (game, module_resref, room_resref) in enumerate(tasks, 1):
        if callable(progress):
            progress(ordinal - 1, total, f"{game} {module_resref} / {room_resref}")
        loader = getattr(resource_manager, "load_model_strict", None)
        if not callable(loader):
            loader = getattr(resource_manager, "load_model", None)
        if not callable(loader):
            break
        try:
            model = loader(room_resref, game, prefer_base_archive=True)
        except TypeError:
            model = loader(room_resref, game)
        if model is None:
            continue
        roles: dict[str, Counter[str]] = {"floor": Counter(), "wall": Counter(), "ceiling": Counter()}
        stack = [getattr(model, "root_node", None)] if getattr(model, "root_node", None) is not None else []
        while stack:
            surface = stack.pop()
            stack.extend(tuple(getattr(surface, "children", ()) or ()))
            if not bool(getattr(surface, "render", True)) or not tuple(getattr(surface, "faces", ()) or ()):
                continue
            texture = _surface_texture(surface)
            if not texture or texture in {"null", "none", "default"}:
                continue
            weight = max(1, len(tuple(getattr(surface, "faces", ()) or ())))
            roles[_building_surface_role(surface)][texture] += weight
        wall = roles["wall"].most_common(1)
        floor = roles["floor"].most_common(1)
        ceiling = roles["ceiling"].most_common(1)
        if not wall and not floor:
            continue
        wall_texture = (wall or floor)[0][0]
        floor_texture = (floor or wall)[0][0]
        ceiling_texture = (ceiling or wall or floor)[0][0]
        candidates.append(
            PascalBuildingStyle(
                style_id=f"vanilla_{game.lower()}_{module_resref}_{room_resref}"[:96],
                label=f"{module_resref} / {room_resref}",
                game=game,
                floor_texture=floor_texture,
                wall_texture=wall_texture,
                ceiling_texture=ceiling_texture,
                source_module=module_resref,
                source_room=room_resref,
                tags=(game.lower(), module_resref, room_resref, "vanilla", "environment"),
            )
        )
    # Many room models repeat the same art palette. Keep one provenance record
    # per unique texture triplet so the authoring combo stays practical.
    unique: dict[tuple[str, str, str, str], PascalBuildingStyle] = {}
    for style in candidates:
        unique.setdefault((style.game, style.floor_texture, style.wall_texture, style.ceiling_texture), style)
    result = tuple(sorted(unique.values(), key=lambda style: (style.game, style.source_module, style.source_room)))
    if callable(progress):
        progress(total, total, f"Learned {len(result)} unique vanilla building palettes")
    return result


def write_vanilla_pascal_style_catalog(
    styles: tuple[PascalBuildingStyle, ...],
    path: str | Path = "",
) -> Path:
    target = Path(path) if path else vanilla_pascal_style_catalog_path(writable=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": _VANILLA_STYLE_SCHEMA,
        "style_count": len(styles),
        "games": sorted({style.game for style in styles}),
        "styles": [
            {
                "style_id": style.style_id,
                "label": style.label,
                "game": style.game,
                "floor_texture": style.floor_texture,
                "wall_texture": style.wall_texture,
                "ceiling_texture": style.ceiling_texture,
                "source_module": style.source_module,
                "source_room": style.source_room,
                "tags": list(style.tags),
            }
            for style in styles
        ],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    vanilla_pascal_building_styles.cache_clear()
    return target


def available_pascal_building_styles(game: str = "") -> tuple[PascalBuildingStyle, ...]:
    wanted = str(game or "").strip().upper()
    try:
        from .map_studio_environment_kits import vanilla_environment_kit_collections

        kit_styles = tuple(
            PascalBuildingStyle(
                style_id=f"kit:{collection.collection_id}",
                label=collection.label,
                game=collection.game,
                floor_texture=collection.floor_texture,
                wall_texture=collection.wall_texture,
                ceiling_texture=collection.ceiling_texture,
                source_module=collection.module_resref,
                source_room="",
                tags=tuple(collection.tags) + ("geometry-kit", collection.environment_kind),
            )
            for collection in vanilla_environment_kit_collections()
        )
    except Exception:
        kit_styles = ()
    return tuple(
        style
        for style in (_DEFAULT_STYLES + kit_styles + vanilla_pascal_building_styles())
        if style.game in {"BOTH", wanted} or not wanted
    )


def _clean_points(points: object) -> tuple[tuple[float, float], ...]:
    result: list[tuple[float, float]] = []
    for raw in tuple(points or ()):
        values = tuple(raw or ())
        if len(values) < 2:
            continue
        point = (float(values[0]), float(values[1]))
        if not all(math.isfinite(value) for value in point):
            raise ValueError("Building wall points must contain finite world coordinates.")
        if not result or math.hypot(point[0] - result[-1][0], point[1] - result[-1][1]) > 1.0e-6:
            result.append(point)
    if len(result) > 2 and math.hypot(result[0][0] - result[-1][0], result[0][1] - result[-1][1]) <= 1.0e-6:
        result.pop()
    if len(result) < 3:
        raise ValueError("Close at least three wall segments to create a room.")
    ordered = tuple(result)
    return ordered if polygon_signed_area(ordered) > 0.0 else tuple(reversed(ordered))


def _next_room_resref(project: AuthoredModuleProject) -> str:
    used = {normalise_resref(room.room_resref) for room in tuple(project.rooms or ())}
    root = normalise_resref(project.module_root) or "grbuild"
    for ordinal in range(1, 10_000):
        suffix = f"r{ordinal:03d}"
        candidate = f"{root[: max(1, 16 - len(suffix))]}{suffix}"[:16]
        if candidate not in used:
            return candidate
    raise ValueError("This map has exhausted its authored building-room identifiers.")


def add_pascal_building_room(
    project: AuthoredModuleProject,
    *,
    points: object,
    floor_z: float = 0.0,
    wall_height: float = 3.0,
    level_index: int = 0,
    level_name: str = "",
    floor_texture: str = "ruler01",
    wall_texture: str = "ruler01",
    ceiling_texture: str = "ruler01",
    include_ceiling: bool = True,
    floor_surface_id: int | str = 4,
    style_id: str = "plcaa_graybox",
    style_source_module: str = "plcaa",
    style_source_room: str = "",
    building_kind: str = "interior",
    roof_type: str = "none",
    roof_pitch_degrees: float = 30.0,
    roof_overhang: float = 0.25,
) -> tuple[AuthoredModuleProject, str]:
    """Append one closed wall loop as an exportable KOTOR room."""

    z = float(floor_z)
    height = float(wall_height)
    if not math.isfinite(z):
        raise ValueError("Building floor elevation must be finite.")
    if not math.isfinite(height) or height <= 0.05:
        raise ValueError("Building wall height must be greater than 0.05 m.")
    kind = str(building_kind or "interior").strip().lower()
    if kind not in {"interior", "exterior"}:
        kind = "interior"
    roof = str(roof_type or "none").strip().lower()
    if roof not in {"none", "flat", "hip", "gable"}:
        raise ValueError("Roof preset must be None, Flat, Pitched/Hip, or Gable.")
    pitch = float(roof_pitch_degrees)
    overhang = float(roof_overhang)
    if not math.isfinite(pitch) or pitch < 5.0 or pitch > 70.0:
        raise ValueError("Roof pitch must be between 5 and 70 degrees.")
    if not math.isfinite(overhang) or overhang < 0.0 or overhang > 5.0:
        raise ValueError("Roof overhang must be between 0 and 5 metres.")
    room_resref = _next_room_resref(project)
    source = {
        "source": "map_studio:pascal_building",
        "style_id": str(style_id or "custom"),
        "style_source_module": normalise_resref(style_source_module),
        "style_source_room": normalise_resref(style_source_room),
        "kit_collection_id": str(style_id or "")[4:] if str(style_id or "").startswith("kit:") else "",
        "kit_autobuild": str(style_id or "").startswith("kit:"),
    }
    primitive = FloorPlanRoomPrimitive(
        room_resref=room_resref,
        points=_clean_points(points),
        z=z,
        wall_height=height,
        floor_surface_id=floor_surface_id,
        material=PrimitiveMaterial(texture=normalize_authored_room_texture(floor_texture), metadata={**source, "surface_role": "floor"}),
        wall_material=PrimitiveMaterial(texture=normalize_authored_room_texture(wall_texture), metadata={**source, "surface_role": "wall"}),
        ceiling_material=PrimitiveMaterial(texture=normalize_authored_room_texture(ceiling_texture), metadata={**source, "surface_role": "ceiling"}),
        include_walls=True,
        include_ceiling=bool(include_ceiling),
        metadata={
            **source,
            "building_level_index": int(level_index),
            "building_level_name": str(level_name or f"Level {int(level_index) + 1}"),
            "building_kind": kind,
            "building_roof_type": roof,
            "building_roof_pitch_degrees": pitch,
            "building_roof_overhang": overhang,
            "closed_wall_loop": True,
            "pascal_graph_node": "room",
        },
    )
    validation = validate_floor_plan_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    room = AuthoredRoomSpec(
        room_resref=room_resref,
        primitive=primitive,
        position=(0.0, 0.0, 0.0),
        visible_rooms=(),
        metadata={
            "primitive": "floor_plan_extrusion",
            "source": "map_studio:pascal_building",
            "building_level_index": int(level_index),
            "building_level_name": str(level_name or f"Level {int(level_index) + 1}"),
            "building_kind": kind,
            "building_roof_type": roof,
            "style_id": str(style_id or "custom"),
        },
    )
    rooms = tuple(project.rooms or ()) + (room,)
    visible = tuple(normalise_resref(item.room_resref) for item in rooms)
    rooms = tuple(replace(item, visible_rooms=visible) for item in rooms)
    placements = project.placements
    if not project.rooms:
        center_x = sum(point[0] for point in primitive.points) / len(primitive.points)
        center_y = sum(point[1] for point in primitive.points) / len(primitive.points)
        placements = replace(
            placements,
            entry_point=replace(
                placements.entry_point,
                area_resref=normalise_resref(project.module_root),
                position=(center_x, center_y, z + 0.05),
            ),
        )
    return replace(project, rooms=rooms, placements=placements), room_resref


def set_pascal_building_opening(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    edge_index: int,
    opening_kind: str,
    center_fraction: float,
    width: float,
    height: float,
    bottom: float,
) -> AuthoredModuleProject:
    kind = str(opening_kind or "door").strip().lower()
    if kind not in {"door", "window"}:
        raise ValueError("Building openings must be doors or windows.")
    preview = preview_pascal_building_opening(
        project,
        room_resref=room_resref,
        edge_index=edge_index,
        opening_kind=kind,
        center_fraction=center_fraction,
        width=width,
        height=height,
        bottom=bottom,
    )
    if not preview.valid:
        raise ValueError(preview.reason or f"The {kind} does not fit on this wall.")
    target_room = next(
        room
        for room in project.rooms
        if normalise_resref(room.room_resref) == normalise_resref(room_resref)
    )
    primitive = target_room.primitive
    used_names = {
        str(opening.name or "").strip().lower()
        for opening in tuple(getattr(primitive, "openings", ()) or ())
    }
    opening_name = ""
    for ordinal in range(1, 10_000):
        candidate = f"{kind}_edge_{int(edge_index)}_{ordinal:03d}"
        if candidate.lower() not in used_names:
            opening_name = candidate
            break
    if not opening_name:
        raise ValueError(f"Wall {int(edge_index) + 1} has exhausted its opening identifiers.")
    updated = set_authored_floor_plan_wall_opening(
        project,
        room_resref=normalise_resref(room_resref),
        name=opening_name,
        edge_index=int(edge_index),
        center_fraction=preview.center_fraction,
        width=preview.width,
        height=preview.height,
        bottom=preview.bottom,
    )
    rooms = []
    for room in updated.rooms:
        if normalise_resref(room.room_resref) != normalise_resref(room_resref):
            rooms.append(room)
            continue
        primitive = room.primitive
        opening_rows = []
        for opening in tuple(getattr(primitive, "openings", ()) or ()):
            if str(opening.name or "").strip() == opening_name:
                opening = replace(
                    opening,
                    metadata={
                        **dict(opening.metadata),
                        "pascal_graph_node": kind,
                        "opening_kind": kind,
                    },
                )
            opening_rows.append(opening)
        rooms.append(replace(room, primitive=replace(primitive, openings=tuple(opening_rows))))
    return replace(updated, rooms=tuple(rooms))


def preview_pascal_building_opening(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    edge_index: int,
    opening_kind: str,
    center_fraction: float,
    width: float,
    height: float,
    bottom: float,
) -> PascalOpeningPreview:
    """Resolve one wall-hosted opening without mutating the authored project.

    Horizontal clamping happens here so the translucent viewport ghost and the
    committed cut use the exact same wall-local values. Existing openings on
    the edge participate in a 2D wall-plane overlap check.
    """

    kind = str(opening_kind or "door").strip().lower()
    clean_room = normalise_resref(room_resref)
    edge = int(edge_index)
    try:
        room = next(item for item in project.rooms if normalise_resref(item.room_resref) == clean_room)
    except StopIteration:
        return PascalOpeningPreview(clean_room, edge, kind, 0.5, 0.0, 0.0, 0.0, False, "The wall's room no longer exists.")
    primitive = getattr(room, "primitive", None)
    points = tuple(getattr(primitive, "points", ()) or ())
    if kind not in {"door", "window"}:
        return PascalOpeningPreview(clean_room, edge, kind, 0.5, 0.0, 0.0, 0.0, False, "Choose Door or Window first.")
    if edge < 0 or edge >= len(points):
        return PascalOpeningPreview(clean_room, edge, kind, 0.5, 0.0, 0.0, 0.0, False, "Move over a visible wall edge.")
    values = (float(center_fraction), float(width), float(height), float(bottom))
    if not all(math.isfinite(value) for value in values):
        return PascalOpeningPreview(clean_room, edge, kind, 0.5, 0.0, 0.0, 0.0, False, "Opening dimensions must be finite.")
    center, opening_width, opening_height, opening_bottom = values
    start = points[edge]
    end = points[(edge + 1) % len(points)]
    edge_length = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
    wall_height = float(getattr(primitive, "wall_height", 0.0) or 0.0)
    if opening_width <= 0.0 or opening_height <= 0.0:
        return PascalOpeningPreview(clean_room, edge, kind, center, opening_width, opening_height, opening_bottom, False, "Opening width and height must be greater than zero.")
    if edge_length <= opening_width + 0.02:
        return PascalOpeningPreview(clean_room, edge, kind, center, opening_width, opening_height, opening_bottom, False, f"This {kind} is wider than the wall.")
    half_fraction = (opening_width * 0.5) / edge_length
    margin_fraction = min(0.02 / edge_length, 0.02)
    center = max(half_fraction + margin_fraction, min(1.0 - half_fraction - margin_fraction, center))
    if opening_bottom < 0.0 or opening_bottom + opening_height >= wall_height - 0.01:
        return PascalOpeningPreview(
            clean_room,
            edge,
            kind,
            center,
            opening_width,
            opening_height,
            opening_bottom,
            False,
            f"The {kind} must fit below the {wall_height:.2f} m wall top.",
        )
    proposed_start = center - half_fraction
    proposed_end = center + half_fraction
    proposed_bottom = opening_bottom
    proposed_top = opening_bottom + opening_height
    for existing in tuple(getattr(primitive, "openings", ()) or ()):
        if int(getattr(existing, "edge_index", -1)) != edge:
            continue
        existing_half = (float(existing.width) * 0.5) / edge_length
        existing_start = float(existing.center_fraction) - existing_half
        existing_end = float(existing.center_fraction) + existing_half
        existing_bottom = float(existing.bottom)
        existing_top = existing_bottom + float(existing.height)
        horizontal_overlap = min(proposed_end, existing_end) - max(proposed_start, existing_start)
        vertical_overlap = min(proposed_top, existing_top) - max(proposed_bottom, existing_bottom)
        if horizontal_overlap > 1.0e-6 and vertical_overlap > 1.0e-6:
            return PascalOpeningPreview(
                clean_room,
                edge,
                kind,
                center,
                opening_width,
                opening_height,
                opening_bottom,
                False,
                f"Move the {kind}; it overlaps {str(existing.name or 'another opening').replace('_', ' ')}.",
            )
    return PascalOpeningPreview(
        clean_room,
        edge,
        kind,
        center,
        opening_width,
        opening_height,
        opening_bottom,
        True,
        f"Click to place {kind}.",
    )


def pascal_building_levels(project: AuthoredModuleProject) -> tuple[PascalBuildingLevel, ...]:
    grouped: dict[int, dict[str, Any]] = {}
    for room in tuple(project.rooms or ()):
        primitive = getattr(room, "primitive", None)
        metadata = dict(getattr(primitive, "metadata", {}) or {})
        if metadata.get("source") != "map_studio:pascal_building":
            continue
        index = int(metadata.get("building_level_index", 0) or 0)
        row = grouped.setdefault(
            index,
            {
                "name": str(metadata.get("building_level_name") or f"Level {index + 1}"),
                "floor_z": float(getattr(primitive, "z", 0.0) or 0.0),
                "rooms": [],
            },
        )
        row["rooms"].append(normalise_resref(room.room_resref))
    return tuple(
        PascalBuildingLevel(index, row["name"], row["floor_z"], tuple(row["rooms"]))
        for index, row in sorted(grouped.items())
    )


__all__ = [
    "PascalBuildingLevel",
    "PascalOpeningPreview",
    "PascalBuildingStyle",
    "add_pascal_building_room",
    "available_pascal_building_styles",
    "pascal_building_levels",
    "preview_pascal_building_opening",
    "set_pascal_building_opening",
    "scan_vanilla_pascal_building_styles",
    "vanilla_pascal_building_styles",
    "vanilla_pascal_style_catalog_path",
    "write_vanilla_pascal_style_catalog",
]
