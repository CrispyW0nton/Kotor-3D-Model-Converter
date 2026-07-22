"""Retail-derived environment-kit collections for Map Studio.

Kotor.NET's Area Designer supplies the data idea: a kit is a collection of
typed geometry templates with local magnet sockets and compatibility classes.
Ghost Studio derives that metadata from installed K1/K2 LYTs and the existing
retail terrain-surface census. No game bytes are copied into the catalog.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


ENVIRONMENT_KIT_SCHEMA = "ghostrigger.environment-kits/v1"
ENVIRONMENT_KIT_MIME_TYPE = "application/x-ghostrigger-map-environment-kit+json"
ENVIRONMENT_KIT_PAYLOAD_SCHEMA = "ghostrigger.map-environment-kit/v1"
_CATALOG_RELATIVE = Path("assets/map_studio/environment_kits/vanilla_kits.json")


@dataclass(frozen=True)
class EnvironmentKitMagnet:
    magnet_id: str
    kind: str
    magnet_class: str
    local_position: tuple[float, float, float]
    local_orientation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    target_piece_id: str = ""
    source: str = "inferred"

    @property
    def yaw_radians(self) -> float:
        x, y, z, w = self.local_orientation
        return math.atan2(2.0 * ((w * z) + (x * y)), 1.0 - 2.0 * ((y * y) + (z * z)))


@dataclass(frozen=True)
class EnvironmentKitPiece:
    piece_id: str
    collection_id: str
    label: str
    game: str
    module_resref: str
    room_resref: str
    role: str
    class_id: str
    model_resref: str
    terrain_asset_id: str = ""
    surface_index: int = -1
    texture_resref: str = ""
    lightmap_resref: str = ""
    dimensions_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    triangle_count: int = 0
    magnets: tuple[EnvironmentKitMagnet, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvironmentKitCollection:
    collection_id: str
    label: str
    game: str
    module_resref: str
    environment_kind: str
    floor_texture: str = "ruler01"
    wall_texture: str = "ruler01"
    ceiling_texture: str = "ruler01"
    pieces: tuple[EnvironmentKitPiece, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def terrain_piece_count(self) -> int:
        return sum(piece.role == "terrain" for piece in self.pieces)

    @property
    def room_piece_count(self) -> int:
        return sum(piece.role in {"room_tile", "exterior_tile"} for piece in self.pieces)


@dataclass(frozen=True)
class EnvironmentKitSnapResult:
    position: tuple[float, float, float]
    yaw_radians: float
    source_magnet_id: str
    target_magnet_id: str
    target_piece_id: str
    target_room_resref: str = ""
    cursor_distance: float = 0.0


def _candidate_roots() -> tuple[Path, ...]:
    roots = [Path.cwd(), Path(sys.executable).resolve().parent]
    try:
        roots.extend(Path(__file__).resolve().parents)
    except (OSError, RuntimeError):
        pass
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def environment_kit_catalog_path(*, writable: bool = False) -> Path:
    configured = str(os.environ.get("GHOSTRIGGER_ENVIRONMENT_KIT_CATALOG", "") or "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(root / _CATALOG_RELATIVE for root in _candidate_roots())
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "GhostStudio" / "cache" / "vanilla_environment_kits.json")
    if not writable:
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    if local:
        return Path(local) / "GhostStudio" / "cache" / "vanilla_environment_kits.json"
    return Path.cwd() / _CATALOG_RELATIVE


def _magnet_from_payload(raw: object) -> EnvironmentKitMagnet:
    row = dict(raw or {})
    return EnvironmentKitMagnet(
        magnet_id=str(row.get("magnet_id") or "magnet"),
        kind=str(row.get("kind") or "edge"),
        magnet_class=str(row.get("magnet_class") or "generic"),
        local_position=tuple(float(value) for value in tuple(row.get("local_position") or (0, 0, 0))[:3]),
        local_orientation=tuple(float(value) for value in tuple(row.get("local_orientation") or (0, 0, 0, 1))[:4]),
        target_piece_id=str(row.get("target_piece_id") or ""),
        source=str(row.get("source") or "inferred"),
    )


def _piece_from_payload(raw: object) -> EnvironmentKitPiece:
    row = dict(raw or {})
    dimensions = tuple(float(value) for value in tuple(row.get("dimensions_m") or (0, 0, 0))[:3])
    magnet_rows = tuple(row.get("magnets") or ())
    magnets = tuple(_magnet_from_payload(value) for value in magnet_rows)
    if not magnets and str(row.get("magnet_profile") or "") == "bounds_4":
        magnets = _terrain_edge_magnets(dimensions)
    return EnvironmentKitPiece(
        piece_id=str(row.get("piece_id") or ""),
        collection_id=str(row.get("collection_id") or ""),
        label=str(row.get("label") or row.get("piece_id") or "Kit piece"),
        game=str(row.get("game") or "").upper(),
        module_resref=str(row.get("module_resref") or "").lower(),
        room_resref=str(row.get("room_resref") or "").lower(),
        role=str(row.get("role") or "generic"),
        class_id=str(row.get("class_id") or "generic"),
        model_resref=str(row.get("model_resref") or "").lower(),
        terrain_asset_id=str(row.get("terrain_asset_id") or ""),
        surface_index=int(row.get("surface_index", -1)),
        texture_resref=str(row.get("texture_resref") or "").lower(),
        lightmap_resref=str(row.get("lightmap_resref") or "").lower(),
        dimensions_m=dimensions,
        triangle_count=int(row.get("triangle_count") or 0),
        magnets=magnets,
        tags=tuple(str(value) for value in tuple(row.get("tags") or ())),
    )


@lru_cache(maxsize=2)
def vanilla_environment_kit_collections(path_text: str = "") -> tuple[EnvironmentKitCollection, ...]:
    path = Path(path_text) if path_text else environment_kit_catalog_path()
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ()
    if str(payload.get("schema") or "") != ENVIRONMENT_KIT_SCHEMA:
        return ()
    rows: list[EnvironmentKitCollection] = []
    for raw in tuple(payload.get("collections") or ()):
        row = dict(raw or {})
        collection_id = str(row.get("collection_id") or "")
        game = str(row.get("game") or "").upper()
        if not collection_id or game not in {"K1", "K2"}:
            continue
        rows.append(
            EnvironmentKitCollection(
                collection_id=collection_id,
                label=str(row.get("label") or collection_id),
                game=game,
                module_resref=str(row.get("module_resref") or "").lower(),
                environment_kind=str(row.get("environment_kind") or "interior"),
                floor_texture=str(row.get("floor_texture") or "ruler01").lower(),
                wall_texture=str(row.get("wall_texture") or "ruler01").lower(),
                ceiling_texture=str(row.get("ceiling_texture") or "ruler01").lower(),
                pieces=tuple(_piece_from_payload(value) for value in tuple(row.get("pieces") or ())),
                tags=tuple(str(value) for value in tuple(row.get("tags") or ())),
            )
        )
    return tuple(rows)


def _yaw_quaternion(yaw: float) -> tuple[float, float, float, float]:
    return (0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5))


def _terrain_edge_magnets(dimensions: tuple[float, float, float]) -> tuple[EnvironmentKitMagnet, ...]:
    width = max(0.01, float(dimensions[0]))
    depth = max(0.01, float(dimensions[1]))
    return tuple(
        EnvironmentKitMagnet(
            magnet_id=name,
            kind="terrain_edge",
            magnet_class="terrain_edge",
            local_position=position,
            local_orientation=_yaw_quaternion(yaw),
            source="bounds_inference",
        )
        for name, position, yaw in (
            ("east", (width * 0.5, 0.0, 0.0), 0.0),
            ("north", (0.0, depth * 0.5, 0.0), math.pi * 0.5),
            ("west", (-width * 0.5, 0.0, 0.0), math.pi),
            ("south", (0.0, -depth * 0.5, 0.0), -math.pi * 0.5),
        )
    )


def _doorway_archetype(magnets: tuple[EnvironmentKitMagnet, ...]) -> str:
    """Classify a retail room tile by its LYT doorway topology.

    Kotor.NET-style kits need semantic piece types, not only an arbitrary room
    name and connection count.  LYT door hooks are the strongest retail signal
    available without redistributing model bytes: they state exactly where a
    room is intended to connect and which way the connection faces.
    """

    count = len(magnets)
    if count <= 0:
        return "chamber"
    if count == 1:
        return "dead_end"
    angles = sorted(magnet.yaw_radians for magnet in magnets)
    if count == 2:
        delta = abs(math.atan2(math.sin(angles[1] - angles[0]), math.cos(angles[1] - angles[0])))
        degrees = math.degrees(delta)
        if degrees >= 145.0:
            return "straight"
        if 55.0 <= degrees <= 125.0:
            return "corner"
        return "bend"
    if count == 3:
        return "t_junction"
    if count == 4:
        gaps = [
            (angles[(index + 1) % count] - angles[index]) % (2.0 * math.pi)
            for index in range(count)
        ]
        if all(math.radians(55.0) <= gap <= math.radians(125.0) for gap in gaps):
            return "cross"
        return "four_way_hub"
    return "hub"


def _read_base_game_layouts(resource_manager: Any, game: str) -> tuple[tuple[str, Any], ...]:
    try:
        from src.core.assets.resource_manager import RES_LYT
        from pykotor.resource.formats.lyt import read_lyt
        from .map_studio_room_catalog import _parse_ascii_lyt
    except Exception:
        return ()
    tag = str(game or "K1").upper()
    getter = getattr(resource_manager, "get_k2" if tag == "K2" else "get_k1", None)
    installation = getter() if callable(getter) else None
    if installation is None:
        return ()
    key_map = dict(getattr(installation, "_key_map", {}) or {})
    modules = sorted(key.rsplit(":", 1)[0] for key in key_map if key.endswith(f":{int(RES_LYT)}"))
    result: list[tuple[str, Any]] = []
    for module_resref in modules:
        try:
            raw = installation.get_bif(module_resref, RES_LYT)
            if not raw:
                continue
            try:
                layout = read_lyt(bytes(raw))
            except Exception:
                layout = _parse_ascii_lyt(bytes(raw))
            if layout is not None:
                result.append((module_resref, layout))
        except Exception:
            continue
    return tuple(result)


def scan_vanilla_environment_kits(
    resource_manager: Any,
    *,
    games: tuple[str, ...] = ("K1", "K2"),
    progress: Any = None,
) -> tuple[EnvironmentKitCollection, ...]:
    """Build lightweight kit metadata from retail layouts and terrain census."""

    from .map_studio_room_catalog import _door_hooks_by_room
    from .map_studio_terrain_kit import vanilla_terrain_kit_assets
    from .map_studio_pascal_building import vanilla_pascal_building_styles

    terrain_assets = tuple(vanilla_terrain_kit_assets())
    terrain_by_module: dict[tuple[str, str], list[Any]] = {}
    for asset in terrain_assets:
        terrain_by_module.setdefault((asset.game, asset.module_resref), []).append(asset)
    palettes = {(style.game, style.source_module): style for style in vanilla_pascal_building_styles()}
    layouts: list[tuple[str, str, Any]] = []
    for game in tuple(dict.fromkeys(str(value or "").upper() for value in games)):
        if game in {"K1", "K2"}:
            layouts.extend((game, module, layout) for module, layout in _read_base_game_layouts(resource_manager, game))
    result: list[EnvironmentKitCollection] = []
    total = len(layouts)
    for ordinal, (game, module_resref, layout) in enumerate(layouts, 1):
        if callable(progress):
            progress(ordinal - 1, total, f"{game} {module_resref}")
        collection_id = f"{game.lower()}_{module_resref}"
        terrain = terrain_by_module.get((game, module_resref), [])
        hooks_by_room = _door_hooks_by_room(layout)
        pieces: list[EnvironmentKitPiece] = []
        terrain_rooms = {asset.room_resref for asset in terrain}
        for room in tuple(getattr(layout, "rooms", ()) or ()):
            room_resref = str(getattr(room, "model", getattr(room, "name", "")) or "").strip().lower()
            if not room_resref:
                continue
            magnets = tuple(
                EnvironmentKitMagnet(
                    magnet_id=str(hook.door or f"door_{index + 1}"),
                    kind="doorway",
                    magnet_class="doorway",
                    local_position=tuple(float(value) for value in hook.local_position),
                    local_orientation=tuple(float(value) for value in hook.orientation),
                    source="lyt_doorhook",
                )
                for index, hook in enumerate(hooks_by_room.get(room_resref, ()))
            )
            role = "exterior_tile" if room_resref in terrain_rooms else "room_tile"
            archetype = _doorway_archetype(magnets)
            pieces.append(
                EnvironmentKitPiece(
                    piece_id=f"{collection_id}_{room_resref}",
                    collection_id=collection_id,
                    label=f"{room_resref} · {module_resref}",
                    game=game,
                    module_resref=module_resref,
                    room_resref=room_resref,
                    role=role,
                    class_id=f"{role}:{archetype}",
                    model_resref=room_resref,
                    magnets=magnets,
                    tags=(game.lower(), module_resref, room_resref, role, archetype, "vanilla"),
                )
            )
        textures: Counter[str] = Counter()
        for asset in terrain:
            textures[str(asset.texture_resref or "ruler01").lower()] += max(1, int(asset.triangle_count))
            pieces.append(
                EnvironmentKitPiece(
                    piece_id=asset.asset_id,
                    collection_id=collection_id,
                    label=asset.label,
                    game=game,
                    module_resref=module_resref,
                    room_resref=asset.room_resref,
                    role="terrain",
                    class_id=f"terrain:{str(asset.category).lower()}",
                    model_resref=asset.room_resref,
                    terrain_asset_id=asset.asset_id,
                    surface_index=int(asset.surface_index),
                    texture_resref=str(asset.texture_resref or "").lower(),
                    lightmap_resref=str(asset.lightmap_resref or "").lower(),
                    dimensions_m=tuple(float(value) for value in asset.dimensions_m),
                    triangle_count=int(asset.triangle_count),
                    magnets=_terrain_edge_magnets(tuple(float(value) for value in asset.dimensions_m)),
                    tags=tuple(asset.tags) + ("magnetized",),
                )
            )
        palette = palettes.get((game, module_resref))
        common_texture = textures.most_common(1)[0][0] if textures else "ruler01"
        exterior = bool(terrain)
        result.append(
            EnvironmentKitCollection(
                collection_id=collection_id,
                label=f"{game} · {module_resref} · {'Exterior' if exterior else 'Interior'}",
                game=game,
                module_resref=module_resref,
                environment_kind="exterior" if exterior else "interior",
                floor_texture=str(getattr(palette, "floor_texture", common_texture) or common_texture),
                wall_texture=str(getattr(palette, "wall_texture", common_texture) or common_texture),
                ceiling_texture=str(getattr(palette, "ceiling_texture", common_texture) or common_texture),
                pieces=tuple(pieces),
                tags=(game.lower(), module_resref, "vanilla", "environment-kit", "exterior" if exterior else "interior"),
            )
        )
    if callable(progress):
        progress(total, total, f"Learned {len(result)} retail environment collections")
    return tuple(result)


def write_vanilla_environment_kit_catalog(
    collections: tuple[EnvironmentKitCollection, ...],
    path: str | Path = "",
) -> Path:
    target = Path(path) if path else environment_kit_catalog_path(writable=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    collection_rows = [asdict(collection) for collection in collections]
    for collection in collection_rows:
        for piece in collection["pieces"]:
            if piece.get("role") == "terrain":
                # The four axis-aligned bounds magnets are deterministic from
                # dimensions, so store one profile token instead of repeating
                # ~26k identical socket records in the generated catalog.
                piece["magnets"] = []
                piece["magnet_profile"] = "bounds_4"
    payload = {
        "schema": ENVIRONMENT_KIT_SCHEMA,
        "collection_count": len(collections),
        "piece_count": sum(len(collection.pieces) for collection in collections),
        "collections": collection_rows,
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    # Generated metadata can contain thousands of pieces and magnets; keep it
    # compact without storing any retail geometry or texture bytes.
    temporary.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    vanilla_environment_kit_collections.cache_clear()
    environment_kit_piece_index.cache_clear()
    return target


def environment_kit_collection_rows(*, game: str = "", kind: str = "") -> tuple[dict[str, Any], ...]:
    wanted_game = str(game or "").upper()
    wanted_kind = str(kind or "").lower()
    return tuple(
        {
            "collection_id": collection.collection_id,
            "label": collection.label,
            "game": collection.game,
            "module_resref": collection.module_resref,
            "environment_kind": collection.environment_kind,
            "floor_texture": collection.floor_texture,
            "wall_texture": collection.wall_texture,
            "ceiling_texture": collection.ceiling_texture,
            "piece_count": len(collection.pieces),
            "room_piece_count": collection.room_piece_count,
            "terrain_piece_count": collection.terrain_piece_count,
            "tags": collection.tags,
        }
        for collection in vanilla_environment_kit_collections()
        if (not wanted_game or collection.game == wanted_game)
        and (not wanted_kind or collection.environment_kind == wanted_kind)
    )


def environment_kit_piece_rows(
    *,
    game: str = "",
    kind: str = "",
    collection_id: str = "",
    roles: tuple[str, ...] = ("room_tile", "exterior_tile"),
) -> tuple[dict[str, Any], ...]:
    """Return lightweight content-browser rows without retail geometry bytes."""

    wanted_game = str(game or "").upper()
    wanted_kind = str(kind or "").strip().lower()
    wanted_collection = str(collection_id or "").strip().lower()
    wanted_roles = {str(value or "").strip().lower() for value in tuple(roles or ())}
    rows: list[dict[str, Any]] = []
    for collection in vanilla_environment_kit_collections():
        if wanted_game and collection.game != wanted_game:
            continue
        if wanted_kind and collection.environment_kind != wanted_kind:
            continue
        if wanted_collection and collection.collection_id.lower() != wanted_collection:
            continue
        for piece in collection.pieces:
            if wanted_roles and piece.role.lower() not in wanted_roles:
                continue
            rows.append(
                {
                    "piece_id": piece.piece_id,
                    "asset_id": piece.piece_id,
                    "collection_id": collection.collection_id,
                    "collection_label": collection.label,
                    "label": piece.label,
                    "game": piece.game,
                    "module_resref": piece.module_resref,
                    "room_resref": piece.room_resref,
                    "role": piece.role,
                    "class_id": piece.class_id,
                    "model_resref": piece.model_resref,
                    "environment_kind": collection.environment_kind,
                    "magnet_count": len(piece.magnets),
                    "floor_texture": collection.floor_texture,
                    "wall_texture": collection.wall_texture,
                    "ceiling_texture": collection.ceiling_texture,
                    "tags": piece.tags,
                }
            )
    return tuple(rows)


def environment_kit_drag_payload(
    piece: EnvironmentKitPiece | str,
    *,
    rotation_degrees_z: float = 0.0,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Build the typed payload consumed by Map Studio's viewport drop target."""

    entry = environment_kit_piece(piece) if isinstance(piece, str) else piece
    if entry is None:
        raise ValueError(f"Unknown environment-kit piece {piece!r}.")
    return {
        "schema": ENVIRONMENT_KIT_PAYLOAD_SCHEMA,
        "piece_id": entry.piece_id,
        "asset_id": entry.piece_id,
        "collection_id": entry.collection_id,
        "label": entry.label,
        "game": entry.game,
        "module_resref": entry.module_resref,
        "room_resref": entry.room_resref,
        "role": entry.role,
        "class_id": entry.class_id,
        "rotation_degrees_z": float(rotation_degrees_z),
        "scale": float(scale),
        "snap_to_surface": True,
        "snap_to_magnets": True,
    }


@lru_cache(maxsize=1)
def environment_kit_piece_index() -> dict[str, EnvironmentKitPiece]:
    result: dict[str, EnvironmentKitPiece] = {}
    for collection in vanilla_environment_kit_collections():
        for piece in collection.pieces:
            result[piece.piece_id.lower()] = piece
            if piece.terrain_asset_id:
                result[piece.terrain_asset_id.lower()] = piece
    return result


def environment_kit_piece(piece_id: str) -> EnvironmentKitPiece | None:
    return environment_kit_piece_index().get(str(piece_id or "").strip().lower())


def magnet_snap_transform(
    source: EnvironmentKitMagnet,
    target: EnvironmentKitMagnet,
    *,
    target_world_position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    target_world_yaw: float = 0.0,
    source_scale: float = 1.0,
    target_scale: float = 1.0,
) -> tuple[tuple[float, float, float], float]:
    """Align a source magnet to face a target magnet, Kotor.NET-style."""

    yaw = target_world_yaw + target.yaw_radians - source.yaw_radians + math.pi
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    sx, sy, sz = (float(value) * float(source_scale) for value in source.local_position)
    rotated_source = ((sx * cosine) - (sy * sine), (sx * sine) + (sy * cosine), sz)
    target_yaw = target_world_yaw
    target_cos = math.cos(target_yaw)
    target_sin = math.sin(target_yaw)
    tx, ty, tz = (float(value) * float(target_scale) for value in target.local_position)
    rotated_target = ((tx * target_cos) - (ty * target_sin), (tx * target_sin) + (ty * target_cos), tz)
    world_target = tuple(float(target_world_position[index]) + rotated_target[index] for index in range(3))
    position = tuple(world_target[index] - rotated_source[index] for index in range(3))
    return position, yaw


def nearest_environment_kit_snap(
    source_piece: EnvironmentKitPiece,
    *,
    proposed_position: tuple[float, float, float],
    proposed_yaw: float,
    source_scale: float,
    targets: tuple[tuple[EnvironmentKitPiece, tuple[float, float, float], float, float, str], ...],
    max_distance: float = 1.5,
) -> EnvironmentKitSnapResult | None:
    """Find and align the nearest compatible Kotor.NET-style magnet pair."""

    best: EnvironmentKitSnapResult | None = None
    source_cos = math.cos(float(proposed_yaw))
    source_sin = math.sin(float(proposed_yaw))
    for source_magnet in source_piece.magnets:
        sx = float(source_magnet.local_position[0]) * float(source_scale)
        sy = float(source_magnet.local_position[1]) * float(source_scale)
        sz = float(source_magnet.local_position[2]) * float(source_scale)
        source_world = (
            float(proposed_position[0]) + (sx * source_cos) - (sy * source_sin),
            float(proposed_position[1]) + (sx * source_sin) + (sy * source_cos),
            float(proposed_position[2]) + sz,
        )
        for target_piece, target_position, target_yaw, target_scale, target_room in targets:
            target_cos = math.cos(float(target_yaw))
            target_sin = math.sin(float(target_yaw))
            for target_magnet in target_piece.magnets:
                if source_magnet.kind != target_magnet.kind:
                    continue
                if source_magnet.magnet_class != target_magnet.magnet_class:
                    continue
                tx = float(target_magnet.local_position[0]) * float(target_scale)
                ty = float(target_magnet.local_position[1]) * float(target_scale)
                tz = float(target_magnet.local_position[2]) * float(target_scale)
                target_world = (
                    float(target_position[0]) + (tx * target_cos) - (ty * target_sin),
                    float(target_position[1]) + (tx * target_sin) + (ty * target_cos),
                    float(target_position[2]) + tz,
                )
                distance = math.dist(source_world, target_world)
                if distance > float(max_distance) or (best is not None and distance >= best.cursor_distance):
                    continue
                snapped_position, snapped_yaw = magnet_snap_transform(
                    source_magnet,
                    target_magnet,
                    target_world_position=target_position,
                    target_world_yaw=float(target_yaw),
                    source_scale=float(source_scale),
                    target_scale=float(target_scale),
                )
                best = EnvironmentKitSnapResult(
                    position=snapped_position,
                    yaw_radians=snapped_yaw,
                    source_magnet_id=source_magnet.magnet_id,
                    target_magnet_id=target_magnet.magnet_id,
                    target_piece_id=target_piece.piece_id,
                    target_room_resref=str(target_room or ""),
                    cursor_distance=distance,
                )
    return best


__all__ = [
    "ENVIRONMENT_KIT_SCHEMA",
    "ENVIRONMENT_KIT_MIME_TYPE",
    "ENVIRONMENT_KIT_PAYLOAD_SCHEMA",
    "EnvironmentKitCollection",
    "EnvironmentKitMagnet",
    "EnvironmentKitPiece",
    "EnvironmentKitSnapResult",
    "environment_kit_catalog_path",
    "environment_kit_collection_rows",
    "environment_kit_drag_payload",
    "environment_kit_piece",
    "environment_kit_piece_index",
    "environment_kit_piece_rows",
    "magnet_snap_transform",
    "nearest_environment_kit_snap",
    "scan_vanilla_environment_kits",
    "vanilla_environment_kit_collections",
    "write_vanilla_environment_kit_catalog",
]
