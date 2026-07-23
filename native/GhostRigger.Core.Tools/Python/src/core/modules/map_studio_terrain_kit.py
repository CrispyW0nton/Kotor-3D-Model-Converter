"""Catalog and static-room bridge for Map Studio terrain kit assets.

Terrain dressing meshes are authored room geometry, not GIT placeables.  This
module keeps that distinction explicit while giving the GUI a small, stable
asset record it can search, thumbnail, drag, and surface-place.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.io.obj_room_document import load_obj_room_document

from .authored_imported_mesh import (
    ImportedMeshRoomPrimitive,
    build_imported_mesh_primitive_from_stock_model,
)
from .authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
from .authored_module_preview_model import build_authored_module_preview_model
from .authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
from .authored_obj_room_import import ObjRoomAuthoringOptions, build_obj_room_primitive
from .module_format import WOKData


TERRAIN_KIT_MIME_TYPE = "application/x-ghostrigger-map-terrain-kit+json"
TERRAIN_KIT_PAYLOAD_SCHEMA = "ghostrigger.map-terrain-kit/v1"
_ASSET_ROOT = Path("assets/map_studio/terrain_kits/dantooine")


@dataclass(frozen=True)
class TerrainKitAsset:
    """One portable, KOTOR-safe terrain dressing source."""

    asset_id: str
    label: str
    category: str
    obj_name: str
    texture_resref: str = "lda_rock06"
    source_units: str = "centimeters"
    source_up_axis: str = "y"
    asset_path: str = ""
    triangle_count: int = 0
    dimensions_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class VanillaTerrainKitAsset:
    """One locally indexed mesh surface from a retail KOTOR room model.

    Only provenance and lightweight geometry statistics are stored in the
    catalog.  The copyrighted MDL/MDX and texture bytes remain in the user's
    configured game installation and are resolved lazily for preview/placing.
    """

    asset_id: str
    label: str
    category: str
    game: str
    module_resref: str
    room_resref: str
    surface_index: int
    node_name: str
    texture_resref: str = ""
    lightmap_resref: str = ""
    triangle_count: int = 0
    dimensions_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    confidence: float = 0.0
    tags: tuple[str, ...] = ()


_DANTOOINE_ASSETS = (
    TerrainKitAsset("dantooine_distant_hill", "Distant Hill Mass", "Vistas & Horizons", "SM_Dantooine_Distant_HillMass_A.obj", triangle_count=1320, dimensions_m=(43.55, 42.87, 8.95), tags=("hill", "vista", "background")),
    TerrainKitAsset("dantooine_drainage_cut", "Drainage Cut", "Rock Formations", "SM_Dantooine_Drainage_Cut_A.obj", triangle_count=1556, dimensions_m=(21.33, 19.50, 3.30), tags=("canyon", "ravine", "wall")),
    TerrainKitAsset("dantooine_far_bluff", "Far Bluff (Soft)", "Rock Formations", "SM_Dantooine_Far_Bluff_Soft_A.obj", triangle_count=1486, dimensions_m=(22.65, 26.65, 7.03), tags=("cliff", "bluff", "vista")),
    TerrainKitAsset("dantooine_hill_ridge", "Hill Ridge", "Rock Formations", "SM_Dantooine_Hill_Ridge_A.obj", triangle_count=1369, dimensions_m=(15.11, 47.38, 6.03), tags=("ridge", "wall", "terrain")),
    TerrainKitAsset("dantooine_hillock_cluster", "Hillock Cluster", "Terrain Forms", "SM_Dantooine_Hillock_Cluster_A.obj", triangle_count=1368, dimensions_m=(22.99, 23.91, 6.95), tags=("hill", "cluster", "mound")),
    TerrainKitAsset("dantooine_horizon_shelf", "Horizon Shelf", "Vistas & Horizons", "SM_Dantooine_Horizon_Shelf_A.obj", triangle_count=1270, dimensions_m=(14.19, 52.93, 6.73), tags=("shelf", "ridge", "background")),
    TerrainKitAsset("dantooine_tree_twisted", "Twisted Tree", "Foliage", "SM_Dantooine_Tree_Twisted_A.obj", texture_resref="lda_bark04", triangle_count=1614, dimensions_m=(2.11, 2.59, 3.79), tags=("tree", "foliage", "trunk")),
    TerrainKitAsset("dantooine_tree_wide", "Wide Tree", "Foliage", "SM_Dantooine_Tree_Wide_A.obj", texture_resref="lda_bark04", triangle_count=1558, dimensions_m=(8.60, 9.61, 5.78), tags=("tree", "foliage", "silhouette")),
    TerrainKitAsset("dantooine_window_vista", "Window Vista Bluff", "Rock Formations", "SM_Dantooine_WindowVista_Bluff_A.obj", triangle_count=1473, dimensions_m=(20.64, 24.71, 9.37), tags=("cliff", "vista", "wall")),
)

_DATHOMIR_ROOT_FALLBACK = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\ModdersResourceFiles\FallenOrder\Dathomir\Converted\Models\Models"
)


def _dathomir_asset_root() -> Path:
    configured = str(os.environ.get("GHOSTRIGGER_DATHOMIR_KIT_ROOT", "") or "").strip()
    return Path(configured) if configured else _DATHOMIR_ROOT_FALLBACK


def _dathomir_assets() -> tuple[TerrainKitAsset, ...]:
    """Return optional Fallen Order Dathomir dressing pieces when present.

    These remain external references to the user's modder-resource extraction;
    Ghost Studio does not copy the extracted meshes or textures into KMAP.
    """

    root = _dathomir_asset_root()
    candidates = (
        TerrainKitAsset(
            "dathomir_scarlet_plant",
            "Dathomir Scarlet Plant",
            "Foliage",
            "scarlet_plant_1a2.obj",
            texture_resref="lka_grass",
            source_units="meters",
            source_up_axis="z",
            asset_path=str(root / "Foliage" / "Terrarium" / "DathomirPlant01" / "scarlet_plant_1a2" / "scarlet_plant_1a2.obj"),
            triangle_count=1268,
            dimensions_m=(1.43, 1.62, 1.49),
            tags=("dathomir", "fallen-order", "plant", "foliage", "terrarium"),
        ),
        TerrainKitAsset(
            "dathomir_terrarium_flower",
            "Dathomir Terrarium Flower",
            "Foliage",
            "flower_1.obj",
            texture_resref="lka_grass",
            source_units="meters",
            source_up_axis="z",
            asset_path=str(root / "Foliage" / "Terrarium" / "DathomirPlant02" / "Old" / "flower_1" / "flower_1.obj"),
            triangle_count=23142,
            dimensions_m=(3.00, 2.92, 2.59),
            tags=("dathomir", "fallen-order", "flower", "foliage", "terrarium"),
        ),
        TerrainKitAsset(
            "dathomir_planet_skybox",
            "Dathomir Planet Skybox",
            "Vistas & Horizons",
            "FIG_Planet01.obj",
            texture_resref="lka_mud02",
            source_units="meters",
            source_up_axis="z",
            asset_path=str(root / "FightClub" / "Skyboxes" / "Planet" / "FIG_Planet01" / "FIG_Planet01.obj"),
            triangle_count=1560,
            dimensions_m=(19.94, 19.94, 4.92),
            tags=("dathomir", "fallen-order", "skybox", "planet", "vista", "horizon"),
        ),
    )
    return tuple(asset for asset in candidates if Path(asset.asset_path).is_file())

_VANILLA_CATALOG_SCHEMA = "ghostrigger.map-terrain-kit-vanilla/v1"
_VANILLA_CATALOG_RELATIVE = Path("assets/map_studio/terrain_kits/vanilla_catalog.json")
_TERRAIN_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Ruins & Structures", "ruins", ("ruin", "rubble", "wreck", "brokenpillar", "bridge", "temple", "tomb", "archway", "column", "rampart")),
    # Root and trunk pieces are structural organic forms in places such as
    # Kashyyyk, not ordinary foliage cards.  Match them before the bark token
    # reaches the general foliage rule so the browser exposes a useful shelf.
    ("Debris & Natural Props", "debris", ("ancient_root", "root", "trunk", "stump", "bone", "log", "bark")),
    ("Foliage", "foliage", ("tree", "bark", "branch", "leaf", "leaves", "plant", "shrub", "bush", "vine", "fern", "grass")),
    ("Rock Formations", "rock", ("canyon", "ravine", "gorge", "trench", "drainage", "cut_", "cliff", "rock", "stone", "crag", "bluff", "boulder", "outcrop", "shelf", "ridge")),
    ("Water & Shorelines", "shore", ("water", "shore", "coast", "river", "stream", "lake", "ocean", "pool", "falls")),
    ("Vistas & Horizons", "horizon", ("horizon", "vista", "backdrop", "background", "sky", "distant", "far_")),
    ("Terrain Forms", "terrain", ("hill", "mound", "slope", "mount", "dune", "terrain", "ground", "earth", "soil", "dirt", "sand", "mud", "snow", "ice", "lava", "floorout")),
)

_LEGACY_TERRAIN_CATEGORIES = {
    "horizon": "Vistas & Horizons",
    "vista & horizon": "Vistas & Horizons",
    "trees & foliage": "Foliage",
    "nature": "Foliage",
    "canyons": "Rock Formations",
    "cliffs": "Rock Formations",
    "cliffs & rocks": "Rock Formations",
    "ridges": "Rock Formations",
    "hills": "Terrain Forms",
    "hills & ridges": "Terrain Forms",
    "water & shores": "Water & Shorelines",
    "ground & slopes": "Terrain Forms",
    "natural debris": "Debris & Natural Props",
}


def _normalized_terrain_category(category: str, search_text: str = "") -> str:
    """Migrate old catalogs into the stable, user-facing browser taxonomy."""

    text = str(search_text or "").lower()
    for candidate, _tag, keywords in _TERRAIN_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return candidate
    value = str(category or "").strip()
    return _LEGACY_TERRAIN_CATEGORIES.get(value.lower(), value or "Terrain Forms")


def _shadowlands_staging_metadata(asset: VanillaTerrainKitAsset) -> dict[str, Any]:
    """Describe a retail Shadowlands surface as a usable staged prop.

    The terrain index intentionally keeps the user's retail meshes in place,
    but raw node names such as ``ancient_Root_152`` are not a useful authoring
    vocabulary.  This lightweight presentation layer turns them into a small
    staging shelf while preserving exact source-room provenance for export.
    """

    if asset.game != "K1" or asset.module_resref not in {"m24aa", "m25aa"}:
        return {}
    name = str(asset.node_name or "").strip().lower()
    largest = max((abs(float(value)) for value in asset.dimensions_m), default=0.0)
    if largest >= 140.0:
        suggested_scale = 0.12
    elif largest >= 85.0:
        suggested_scale = 0.20
    elif largest >= 45.0:
        suggested_scale = 0.45
    else:
        suggested_scale = 1.0
    if any(token in name for token in ("ancient_root", "root", "trunk", "stump")):
        return {
            "category": "Roots & Tree Trunks",
            "staging_role": "Native root / tree-trunk staging",
            "suggested_scale": suggested_scale,
            "staging_hint": "Drag onto the clearing to stage a real Shadowlands root or trunk; it surface-snaps and relights in the destination map.",
        }
    if any(token in name for token in ("shell", "nucli", "plant", "vine")):
        return {
            "category": "Canopy & Foliage",
            "staging_role": "Native canopy / foliage staging",
            "suggested_scale": suggested_scale,
            "staging_hint": "Drag onto terrain to stage native Shadowlands foliage; it stays visual-only so the authored terrain owns collision.",
        }
    return {
        "staging_role": "Native Shadowlands terrain staging",
        "suggested_scale": suggested_scale,
        "staging_hint": "Drag onto terrain to stage this retail Shadowlands surface at a practical working scale.",
    }


def _vanilla_catalog_candidates() -> tuple[Path, ...]:
    configured = str(os.environ.get("GHOSTRIGGER_TERRAIN_CATALOG", "") or "").strip()
    candidates: list[Path] = [Path(configured)] if configured else []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "GhostStudio" / "cache" / "vanilla_terrain_catalog.json")
    for root in _candidate_roots():
        candidates.append(root / _VANILLA_CATALOG_RELATIVE)
    result: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved not in result:
            result.append(resolved)
    return tuple(result)


def vanilla_terrain_catalog_path(*, writable: bool = False) -> Path:
    """Return the bundled/current catalog, or the per-user refresh target."""

    candidates = _vanilla_catalog_candidates()
    if not writable:
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "GhostStudio" / "cache" / "vanilla_terrain_catalog.json"
    return Path.cwd() / _VANILLA_CATALOG_RELATIVE


def _vanilla_asset_payload(asset: VanillaTerrainKitAsset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "label": asset.label,
        "category": asset.category,
        "game": asset.game,
        "module_resref": asset.module_resref,
        "room_resref": asset.room_resref,
        "surface_index": int(asset.surface_index),
        "node_name": asset.node_name,
        "texture_resref": asset.texture_resref,
        "lightmap_resref": asset.lightmap_resref,
        "triangle_count": int(asset.triangle_count),
        "dimensions_m": list(asset.dimensions_m),
        "confidence": float(asset.confidence),
        "tags": list(asset.tags),
    }


def _vanilla_asset_from_payload(payload: dict[str, Any]) -> VanillaTerrainKitAsset | None:
    try:
        asset_id = str(payload.get("asset_id") or "").strip().lower()
        game = str(payload.get("game") or "").strip().upper()
        room_resref = str(payload.get("room_resref") or "").strip().lower()
        tags = tuple(str(value) for value in tuple(payload.get("tags") or ()) if str(value).strip())
        module_resref = str(payload.get("module_resref") or "").strip().lower()
        node_name = str(payload.get("node_name") or "terrain_mesh")
        category = _normalized_terrain_category(
            str(payload.get("category") or "Vanilla Terrain"),
            " ".join(
                (
                    str(payload.get("label") or ""),
                    node_name,
                    str(payload.get("texture_resref") or ""),
                    " ".join(tags),
                )
            ),
        )
        dimensions = tuple(float(value) for value in tuple(payload.get("dimensions_m") or ())[:3])
        if not asset_id or game not in {"K1", "K2"} or not room_resref or len(dimensions) != 3:
            return None
        asset = VanillaTerrainKitAsset(
            asset_id=asset_id,
            label=str(payload.get("label") or payload.get("node_name") or room_resref),
            category=category,
            game=game,
            module_resref=module_resref,
            room_resref=room_resref,
            surface_index=max(0, int(payload.get("surface_index", 0) or 0)),
            node_name=node_name,
            texture_resref=str(payload.get("texture_resref") or "").strip().lower(),
            lightmap_resref=str(payload.get("lightmap_resref") or "").strip().lower(),
            triangle_count=max(0, int(payload.get("triangle_count", 0) or 0)),
            dimensions_m=(dimensions[0], dimensions[1], dimensions[2]),
            confidence=max(0.0, min(1.0, float(payload.get("confidence", 0.0) or 0.0))),
            tags=tags,
        )
        presentation = _shadowlands_staging_metadata(asset)
        if presentation.get("category") and presentation["category"] != asset.category:
            asset = replace(asset, category=str(presentation["category"]))
        return asset
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=2)
def vanilla_terrain_kit_assets(path_text: str = "") -> tuple[VanillaTerrainKitAsset, ...]:
    path = Path(path_text) if path_text else vanilla_terrain_catalog_path()
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()
    if str(payload.get("schema") or "") != _VANILLA_CATALOG_SCHEMA:
        return ()
    assets = [_vanilla_asset_from_payload(dict(row)) for row in tuple(payload.get("assets") or ())]
    return tuple(asset for asset in assets if asset is not None)


def _terrain_surface_classification(surface: Any) -> tuple[str, float, tuple[str, ...]] | None:
    name = str(getattr(surface, "name", "") or "").lower()
    texture = str(getattr(surface, "texture", "") or "").lower()
    text = f"{name} {texture}"
    for category, tag, keywords in _TERRAIN_KEYWORDS:
        matches = tuple(keyword for keyword in keywords if keyword in text)
        if matches:
            confidence = min(0.98, 0.72 + (0.08 * len(matches)))
            return category, confidence, tuple(dict.fromkeys((tag, *matches)))
    if bool(getattr(surface, "background_geometry", False)) or bool(getattr(surface, "backdrop", False)):
        return "Vista & Horizon", 0.78, ("horizon", "background")
    return None


_OUTDOOR_MODULE_PREFIXES = {
    "K1": (
        "m13", "m14", "m15", "m16",  # Dantooine
        "m17", "m18",                 # Tatooine
        "m22", "m23", "m24", "m25", # Kashyyyk / Manaan exteriors
        "m26",                          # Unknown World
        "m27", "m28",                 # Korriban
        "m33", "m34", "m35", "m36", "m37", "m38", "m39",
    ),
    "K2": (
        "104per",                       # Peragus exterior
        "231tel", "232tel", "233tel", # Telos surface
        "400dxn", "401dxn", "402dxn", "403dxn", "410dxn", "411dxn", "421dxn",
        "501ond", "502ond", "503ond", "504ond", "505ond", "506ond",
        "601dan", "602dan", "604dan", "605dan", "610dan", "650dan",
        "701kor", "702kor", "710kor", "711kor",
        "901mal", "902mal", "903mal", "904mal", "905mal", "906mal",
    ),
}


def _base_game_lyt_rooms(resource_manager: Any, game: str, *, outdoor_only: bool) -> dict[str, str]:
    """Map each vanilla room model to one source LYT without indexing mods."""

    try:
        from src.core.assets.resource_manager import RES_LYT
        from pykotor.resource.formats.lyt import read_lyt
    except Exception:
        return {}
    tag = str(game or "K1").upper()
    installation_getter = getattr(resource_manager, "get_k2" if tag == "K2" else "get_k1", None)
    installation = installation_getter() if callable(installation_getter) else None
    if installation is None:
        return {}
    key_map = dict(getattr(installation, "_key_map", {}) or {})
    module_resrefs = sorted(
        key.rsplit(":", 1)[0]
        for key in key_map
        if key.endswith(f":{int(RES_LYT)}")
    )
    if outdoor_only:
        prefixes = _OUTDOOR_MODULE_PREFIXES.get(tag, ())
        module_resrefs = [value for value in module_resrefs if value.startswith(prefixes)]
    result: dict[str, str] = {}
    for module_resref in module_resrefs:
        try:
            raw = installation.get_bif(module_resref, RES_LYT)
            if not raw:
                continue
            try:
                layout = read_lyt(bytes(raw))
            except Exception:
                from .map_studio_room_catalog import _parse_ascii_lyt

                layout = _parse_ascii_lyt(bytes(raw))
            for room in tuple(getattr(layout, "rooms", ()) or ()):
                room_resref = str(getattr(room, "model", getattr(room, "name", "")) or "").strip().lower()
                if room_resref:
                    result.setdefault(room_resref, module_resref)
        except Exception:
            continue
    return result


def scan_vanilla_terrain_kit_assets(
    resource_manager: Any,
    *,
    games: tuple[str, ...] = ("K1", "K2"),
    outdoor_only: bool = True,
    max_rooms_per_module: int = 8,
    progress: Any = None,
) -> tuple[VanillaTerrainKitAsset, ...]:
    """Study retail outdoor room surfaces and build a lightweight local index.

    This is intentionally a metadata scan. Geometry and texture bytes never
    enter the cache; previews and placements load the named retail room lazily.
    """

    assets: list[VanillaTerrainKitAsset] = []
    tasks: list[tuple[str, str, str]] = []
    for game in tuple(dict.fromkeys(str(value or "").upper() for value in games)):
        if game not in {"K1", "K2"}:
            continue
        room_sources = _base_game_lyt_rooms(
            resource_manager,
            game,
            outdoor_only=bool(outdoor_only),
        )
        grouped: dict[str, list[str]] = {}
        for room_resref, module_resref in room_sources.items():
            grouped.setdefault(module_resref, []).append(room_resref)
        for module_resref, room_resrefs in sorted(grouped.items()):
            ordered = sorted(room_resrefs)
            limit = max(0, int(max_rooms_per_module))
            if limit and len(ordered) > limit:
                # Sample the whole module rather than only its alphabetic first
                # rooms; outdoor terrain/backdrop variants often live at the end.
                indices = {
                    min(len(ordered) - 1, int(round(index * (len(ordered) - 1) / max(1, limit - 1))))
                    for index in range(limit)
                }
                ordered = [ordered[index] for index in sorted(indices)]
            for room_resref in ordered:
                tasks.append((game, module_resref, room_resref))
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
        try:
            from src.core.geometry.model_data import NodeFlags

            aabb_flag = int(NodeFlags.AABB)
        except Exception:
            aabb_flag = 0x0200
        surface_index = 0
        stack = [getattr(model, "root_node", None)] if getattr(model, "root_node", None) is not None else []
        while stack:
            surface = stack.pop()
            stack.extend(tuple(getattr(surface, "children", ()) or ()))
            vertices = getattr(surface, "vertices", ()) or ()
            faces = getattr(surface, "faces", ()) or ()
            if (
                len(vertices) == 0
                or len(faces) == 0
                or not bool(getattr(surface, "render", True))
                or bool(int(getattr(surface, "flags", 0) or 0) & aabb_flag)
            ):
                continue
            current_surface_index = surface_index
            surface_index += 1
            classification = _terrain_surface_classification(surface)
            if classification is None or len(faces) < 4:
                continue
            category, confidence, tags = classification
            sample_step = max(1, len(vertices) // 512)
            sampled_vertices = vertices[::sample_step]
            mins = tuple(min(float(vertex[axis]) for vertex in sampled_vertices) for axis in range(3))
            maxs = tuple(max(float(vertex[axis]) for vertex in sampled_vertices) for axis in range(3))
            dimensions = tuple(maxs[axis] - mins[axis] for axis in range(3))
            if max(dimensions) < 0.35:
                continue
            node_name = str(getattr(surface, "name", "") or f"surface_{current_surface_index}").strip()
            texture_names = tuple(
                str(value or "").strip()
                for value in tuple(getattr(surface, "texture_names", ()) or ())
                if str(value or "").strip()
            )
            texture = str(getattr(surface, "texture", "") or "").strip()
            if not texture and texture_names:
                texture = texture_names[0]
            label_name = node_name.replace("_", " ").strip().title()
            assets.append(
                VanillaTerrainKitAsset(
                    asset_id=f"vanilla_{game.lower()}_{room_resref}_{current_surface_index:03d}",
                    label=f"{label_name} · {module_resref}",
                    category=category,
                    game=game,
                    module_resref=module_resref,
                    room_resref=room_resref,
                    surface_index=current_surface_index,
                    node_name=node_name,
                    texture_resref=texture.lower(),
                    lightmap_resref=str(getattr(surface, "lightmap", "") or "").strip().lower(),
                    triangle_count=len(faces),
                    dimensions_m=(float(dimensions[0]), float(dimensions[1]), float(dimensions[2])),
                    confidence=confidence,
                    tags=tuple(dict.fromkeys((*tags, game.lower(), module_resref, room_resref))),
                )
            )
    if callable(progress):
        progress(total, total, f"Indexed {len(assets)} vanilla terrain surfaces")
    return tuple(
        sorted(
            assets,
            key=lambda item: (item.game, item.category, item.module_resref, item.room_resref, item.surface_index),
        )
    )


def write_vanilla_terrain_kit_catalog(
    assets: tuple[VanillaTerrainKitAsset, ...],
    path: str | Path = "",
) -> Path:
    target = Path(path) if path else vanilla_terrain_catalog_path(writable=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": _VANILLA_CATALOG_SCHEMA,
        "asset_count": len(assets),
        "games": sorted({asset.game for asset in assets}),
        "assets": [_vanilla_asset_payload(asset) for asset in assets],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    vanilla_terrain_kit_assets.cache_clear()
    terrain_kit_asset_root.cache_clear()
    return target


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


@lru_cache(maxsize=1)
def terrain_kit_asset_root() -> Path:
    """Resolve the shipped terrain-kit root beside the staged application."""

    for root in _candidate_roots():
        candidate = root / _ASSET_ROOT
        if candidate.is_dir():
            return candidate
    return Path.cwd() / _ASSET_ROOT


def terrain_kit_assets(*, game: str = "") -> tuple[TerrainKitAsset | VanillaTerrainKitAsset, ...]:
    wanted_game = str(game or "").strip().upper()
    vanilla = tuple(
        asset
        for asset in vanilla_terrain_kit_assets()
        if not wanted_game or asset.game == wanted_game
    )
    return _DANTOOINE_ASSETS + _dathomir_assets() + vanilla


def terrain_kit_asset(asset_id: str) -> TerrainKitAsset | VanillaTerrainKitAsset:
    wanted = str(asset_id or "").strip().lower()
    for asset in terrain_kit_assets():
        if asset.asset_id == wanted:
            return asset
    raise ValueError(f"Unknown Map Studio terrain kit asset: {asset_id!r}.")


def terrain_kit_asset_path(asset: TerrainKitAsset | str) -> Path:
    entry = terrain_kit_asset(asset) if isinstance(asset, str) else asset
    if not isinstance(entry, TerrainKitAsset):
        raise ValueError("Vanilla Terrain Kit assets resolve from the configured game library, not a loose OBJ.")
    path = Path(entry.asset_path) if str(entry.asset_path or "").strip() else terrain_kit_asset_root() / entry.obj_name
    if not path.is_file():
        raise FileNotFoundError(f"Terrain kit source is missing: {path}")
    return path


def _terrain_asset_is_browser_ready(asset: TerrainKitAsset | VanillaTerrainKitAsset) -> bool:
    """Keep malformed micro-surfaces off the author-facing staging shelf."""

    if (
        isinstance(asset, VanillaTerrainKitAsset)
        and asset.game == "K1"
        and asset.module_resref in {"m24aa", "m25aa"}
        and asset.category == "Roots & Tree Trunks"
        and int(asset.triangle_count) < 24
    ):
        # Source-room AABBs can include tiny connector fragments such as the
        # eight-face ``stump02`` sheet.  In isolation they become a distracting
        # white shard, not a usable staged tree form.
        return False
    return True


def terrain_kit_asset_rows(*, game: str = "") -> tuple[dict[str, Any], ...]:
    """Return presentation-neutral records for the Terrain content browser."""

    root = terrain_kit_asset_root()
    supplied_assets = _DANTOOINE_ASSETS + _dathomir_assets()
    supplied = tuple(
        {
            "asset_id": asset.asset_id,
            "label": asset.label,
            "category": asset.category,
            "source": "Fallen Order / Dathomir" if "dathomir" in asset.tags else "Ghost Studio Terrain Kit / Dantooine",
            "asset_path": str(Path(asset.asset_path) if str(asset.asset_path or "").strip() else root / asset.obj_name),
            "texture_resref": asset.texture_resref,
            "triangle_count": int(asset.triangle_count),
            "dimensions_m": tuple(asset.dimensions_m),
            "tags": tuple(asset.tags),
            "suggested_scale": 0.35 if "skybox" in asset.tags else 1.0,
            "staging_role": "Dathomir environment staging" if "dathomir" in asset.tags else "Terrain kit staging",
            "staging_hint": (
                "Drag into a Dathomir map as visual world dressing; surface-snap foliage to terrain and place the planet as a distant vista."
                if "dathomir" in asset.tags
                else "Drag onto terrain or another visible level surface."
            ),
            "building_style_id": "environment:dathomir" if "dathomir" in asset.tags else "",
            "building_style_label": "Dathomir — Fallen Order Extraction" if "dathomir" in asset.tags else "",
        }
        for asset in supplied_assets
    )
    wanted_game = str(game or "").strip().upper()
    vanilla = tuple(
        {
            **_vanilla_asset_payload(asset),
            **_shadowlands_staging_metadata(asset),
            "source": f"{asset.game} vanilla · {asset.module_resref} / {asset.room_resref}",
            "source_kind": "vanilla_game",
            "asset_path": "",
            "requires_game": asset.game,
            "building_style_id": terrain_kit_builder_style_id(asset.game, asset.module_resref),
            "building_style_label": terrain_kit_builder_style_label(
                terrain_kit_builder_style_id(asset.game, asset.module_resref)
            ),
        }
        for asset in vanilla_terrain_kit_assets()
        if (not wanted_game or asset.game == wanted_game) and _terrain_asset_is_browser_ready(asset)
    )
    return supplied + vanilla


def terrain_kit_builder_style_id(game: str, module_resref: str) -> str:
    """Group compatible terrain modules under one Pascal building style."""

    tag = str(game or "").strip().upper()
    module = str(module_resref or "").strip().lower()
    if tag == "K1" and module in {"m24aa", "m25aa"}:
        return "architecture:k1_shadowlands"
    return ""


def terrain_kit_builder_style_label(style_id: str) -> str:
    return {
        "architecture:k1_shadowlands": "Kashyyyk Shadowlands — Earthen Clearings, Roots & Foliage",
    }.get(str(style_id or "").strip().lower(), "")


def terrain_kit_drag_payload(
    asset: TerrainKitAsset | VanillaTerrainKitAsset | str,
    *,
    rotation_degrees_z: float = 0.0,
    scale: float = 1.0,
) -> dict[str, Any]:
    entry = terrain_kit_asset(asset) if isinstance(asset, str) else asset
    return {
        "schema": TERRAIN_KIT_PAYLOAD_SCHEMA,
        "asset_id": entry.asset_id,
        "label": entry.label,
        "category": entry.category,
        "game": str(getattr(entry, "game", "") or ""),
        "source_kind": "vanilla_game" if isinstance(entry, VanillaTerrainKitAsset) else "supplied_obj",
        "rotation_degrees_z": float(rotation_degrees_z),
        "scale": float(scale),
        "snap_to_surface": True,
    }


def transform_terrain_kit_primitive(
    primitive: ImportedMeshRoomPrimitive,
    *,
    rotation_degrees_z: float,
    scale: float,
) -> ImportedMeshRoomPrimitive:
    uniform_scale = float(scale)
    if not math.isfinite(uniform_scale) or uniform_scale <= 0.0:
        raise ValueError("Terrain kit scale must be a finite positive value.")
    angle = math.radians(float(rotation_degrees_z))
    cosine = math.cos(angle)
    sine = math.sin(angle)

    def point(value: tuple[float, float, float]) -> tuple[float, float, float]:
        x = float(value[0]) * uniform_scale
        y = float(value[1]) * uniform_scale
        return (x * cosine - y * sine, x * sine + y * cosine, float(value[2]) * uniform_scale)

    def normal(value: tuple[float, float, float]) -> tuple[float, float, float]:
        x = float(value[0]) * cosine - float(value[1]) * sine
        y = float(value[0]) * sine + float(value[1]) * cosine
        z = float(value[2])
        length = math.sqrt((x * x) + (y * y) + (z * z)) or 1.0
        return (x / length, y / length, z / length)

    surfaces = tuple(
        replace(
            surface,
            vertices=tuple(point(value) for value in surface.vertices),
            normals=tuple(normal(value) for value in surface.normals),
        )
        for surface in primitive.surfaces
    )
    wok = primitive.wok
    if wok is not None:
        # Render geometry and WOK must stay in one room-local space. Leaving
        # stock collision unrotated made a visually placed terrain form walk
        # and snap against its old orientation in the exported module.
        wok = replace(
            wok,
            verts=[point(tuple(value)) for value in tuple(wok.verts or ())],
            raw=None,
            relative_hook1=point(tuple(wok.relative_hook1)),
            relative_hook2=point(tuple(wok.relative_hook2)),
            absolute_hook1=point(tuple(wok.absolute_hook1)),
            absolute_hook2=point(tuple(wok.absolute_hook2)),
            position=point(tuple(wok.position)),
        )
    metadata = dict(getattr(primitive, "metadata", {}) or {})
    transformed_portals: list[dict[str, Any]] = []
    for raw in tuple(metadata.get("walkmesh_portals") or ()):
        row = dict(raw or {})
        for key in ("start", "end", "midpoint", "hook_position", "hook_to_portal_offset"):
            values = tuple(row.get(key) or ())
            if len(values) >= 3:
                row[key] = list(point(tuple(float(value) for value in values[:3])))
        if tuple(row.get("start") or ()) and tuple(row.get("end") or ()):
            row["width_m"] = math.dist(tuple(row["start"]), tuple(row["end"]))
        transformed_portals.append(row)
    if transformed_portals:
        metadata["walkmesh_portals"] = transformed_portals
    return replace(primitive, surfaces=surfaces, wok=wok, metadata=metadata)


@lru_cache(maxsize=32)
def _build_supplied_terrain_kit_primitive(
    asset_id: str,
    room_resref: str,
    game: str = "K1",
    rotation_degrees_z: float = 0.0,
    scale: float = 1.0,
) -> ImportedMeshRoomPrimitive:
    """Decode one terrain asset as explicit visual-only KOTOR room geometry."""

    asset = terrain_kit_asset(asset_id)
    if not isinstance(asset, TerrainKitAsset):
        raise ValueError(f"Terrain Kit asset {asset_id!r} is not a supplied OBJ asset.")
    document = load_obj_room_document(terrain_kit_asset_path(asset))
    primitive, report = build_obj_room_primitive(
        document,
        ObjRoomAuthoringOptions(
            room_resref=str(room_resref or "grterrain")[:16],
            game=str(game or "K1").upper(),
            source_units=asset.source_units,
            source_up_axis=asset.source_up_axis,
            center_xy=True,
            ground_to_zero=True,
        ),
        material_texture_resrefs={surface.material_name: asset.texture_resref for surface in document.surfaces},
    )
    primitive = transform_terrain_kit_primitive(
        primitive,
        rotation_degrees_z=float(rotation_degrees_z),
        scale=float(scale),
    )
    return replace(
        primitive,
        # A present zero-face WOK is Odyssey's valid visual-only room form.
        # The sculpted terrain below retains collision ownership.
        wok=WOKData(name=str(room_resref or "grterrain")[:16]),
        metadata={
            **dict(primitive.metadata),
            "source": "map_studio:terrain_kit",
            "terrain_kit_asset_id": asset.asset_id,
            "terrain_kit_category": asset.category,
            "terrain_kit_texture_resref": asset.texture_resref,
            "terrain_kit_rotation_degrees_z": float(rotation_degrees_z),
            "terrain_kit_scale": float(scale),
            "terrain_kit_visual_only": True,
            "render_triangle_count": int(report.triangle_count),
        },
    )


def _build_vanilla_terrain_kit_primitive(
    asset: VanillaTerrainKitAsset,
    room_resref: str,
    *,
    resource_manager: Any,
    rotation_degrees_z: float,
    scale: float,
) -> ImportedMeshRoomPrimitive:
    if resource_manager is None:
        raise ValueError(f"Connect the {asset.game} game installation to use {asset.label}.")
    loader = getattr(resource_manager, "load_model_strict", None)
    if not callable(loader):
        loader = getattr(resource_manager, "load_model", None)
    if not callable(loader):
        raise ValueError("The active game resource library cannot load vanilla room models.")
    try:
        model = loader(asset.room_resref, asset.game, prefer_base_archive=True)
    except TypeError:
        model = loader(asset.room_resref, asset.game)
    if model is None:
        raise ValueError(
            f"Vanilla room model {asset.room_resref} was not found in the configured {asset.game} installation."
        )
    whole_room = build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=str(room_resref or "grterrain")[:16],
        source_model=asset.room_resref,
        game=asset.game,
    )
    if asset.surface_index >= len(whole_room.surfaces):
        raise ValueError(
            f"{asset.label} no longer matches {asset.room_resref}; refresh the Vanilla Terrain catalog."
        )
    source = whole_room.surfaces[asset.surface_index]
    if not source.vertices or not source.faces:
        raise ValueError(f"{asset.label} has no renderable terrain geometry.")
    mins = tuple(min(float(vertex[axis]) for vertex in source.vertices) for axis in range(3))
    maxs = tuple(max(float(vertex[axis]) for vertex in source.vertices) for axis in range(3))
    center_x = (mins[0] + maxs[0]) * 0.5
    center_y = (mins[1] + maxs[1]) * 0.5
    grounded = tuple(
        (float(vertex[0]) - center_x, float(vertex[1]) - center_y, float(vertex[2]) - mins[2])
        for vertex in source.vertices
    )
    # Retail lightmaps are tied to the source room and cannot follow a moved
    # cliff. Preserve its diffuse texture/material but let the destination map
    # bake new lighting for the relocated piece.
    surface = replace(
        source,
        name=f"{asset.room_resref}_{asset.node_name}"[:32],
        vertices=grounded,
        lightmap="",
        uvs_lm=(),
        texture_names=((source.texture,) if source.texture else ()),
        tex_count=1,
        backdrop=False,
        background_geometry=False,
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref=str(room_resref or "grterrain")[:16],
        surfaces=(surface,),
        source_model=asset.room_resref,
        game=asset.game,
        wok=WOKData(name=str(room_resref or "grterrain")[:16]),
        metadata={
            "source": "map_studio:terrain_kit:vanilla",
            "terrain_kit_asset_id": asset.asset_id,
            "terrain_kit_category": asset.category,
            "terrain_kit_texture_resref": source.texture,
            "terrain_kit_source_game": asset.game,
            "terrain_kit_source_module": asset.module_resref,
            "terrain_kit_source_room": asset.room_resref,
            "terrain_kit_source_surface_index": int(asset.surface_index),
            "terrain_kit_source_node": asset.node_name,
            "terrain_kit_visual_only": True,
            "source_lightmap_removed_for_relighting": bool(source.lightmap),
            "render_triangle_count": len(surface.faces),
        },
    )
    return transform_terrain_kit_primitive(
        primitive,
        rotation_degrees_z=float(rotation_degrees_z),
        scale=float(scale),
    )


def build_terrain_kit_primitive(
    asset_id: str,
    room_resref: str,
    game: str = "K1",
    rotation_degrees_z: float = 0.0,
    scale: float = 1.0,
    *,
    resource_manager: Any = None,
) -> ImportedMeshRoomPrimitive:
    """Decode a supplied or locally indexed terrain asset as a visual room."""

    asset = terrain_kit_asset(asset_id)
    if isinstance(asset, VanillaTerrainKitAsset):
        requested_game = str(game or asset.game).upper()
        if requested_game != asset.game:
            raise ValueError(f"{asset.label} is a {asset.game} asset and cannot be exported into {requested_game}.")
        return _build_vanilla_terrain_kit_primitive(
            asset,
            room_resref,
            resource_manager=resource_manager,
            rotation_degrees_z=float(rotation_degrees_z),
            scale=float(scale),
        )
    return _build_supplied_terrain_kit_primitive(
        asset.asset_id,
        room_resref,
        str(game or "K1").upper(),
        float(rotation_degrees_z),
        float(scale),
    )


def build_terrain_kit_preview_model(
    asset_id: str,
    *,
    game: str = "K1",
    resource_manager: Any = None,
) -> object | None:
    """Build one renderer-native thumbnail model without touching a KMAP."""

    primitive = build_terrain_kit_primitive(
        asset_id,
        "grtkpreview",
        game,
        resource_manager=resource_manager,
    )
    room = AuthoredRoomSpec(
        room_resref="grtkpreview",
        primitive=primitive,
        visible_rooms=("grtkpreview",),
        metadata={"source": "map_studio:terrain_kit_thumbnail"},
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grtkpreview", game=str(game or "K1").upper()),
        rooms=(room,),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grtkpreview")),
    )
    return build_authored_module_preview_model(project, include_backdrops=True).model


__all__ = [
    "TERRAIN_KIT_MIME_TYPE",
    "TERRAIN_KIT_PAYLOAD_SCHEMA",
    "TerrainKitAsset",
    "VanillaTerrainKitAsset",
    "build_terrain_kit_preview_model",
    "build_terrain_kit_primitive",
    "scan_vanilla_terrain_kit_assets",
    "terrain_kit_asset",
    "terrain_kit_asset_path",
    "terrain_kit_asset_root",
    "terrain_kit_asset_rows",
    "terrain_kit_assets",
    "terrain_kit_builder_style_id",
    "terrain_kit_builder_style_label",
    "terrain_kit_drag_payload",
    "transform_terrain_kit_primitive",
    "vanilla_terrain_catalog_path",
    "vanilla_terrain_kit_assets",
    "write_vanilla_terrain_kit_catalog",
]
