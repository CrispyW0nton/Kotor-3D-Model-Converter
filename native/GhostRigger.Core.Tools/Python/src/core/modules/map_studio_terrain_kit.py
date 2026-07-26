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
from .authored_room_geometry import PrimitiveMesh
from .module_format import WOKData, WOKFace


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
    material_textures: tuple[tuple[str, str, str], ...] = ()
    collision_intent: str = ""
    collision_mode: str = ""
    provenance: str = ""
    source_author: str = ""
    source_mod_id: str = ""
    source_units: str = "centimeters"
    source_up_axis: str = "y"
    asset_path: str = ""
    triangle_count: int = 0
    dimensions_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleTransitionFitContract:
    """Shared visual-fit contract for a supplied module transition.

    The walkmesh portal width remains engine truth.  ``host_opening_*`` is the
    larger visual recess required to expose the supplied facade without
    driving its roots/rocks through the authored wall.
    """

    asset_id: str
    uniform_scale: float
    source_yaw_degrees: float
    source_width_m: float
    source_depth_m: float
    source_height_m: float
    host_opening_width_m: float
    host_opening_height_m: float
    actor_clearance_width_m: float
    actor_clearance_height_m: float
    ground_embed_m: float


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


@dataclass(frozen=True)
class RetailModelTerrainKitAsset:
    """A complete retail model exposed as movable environment dressing.

    The catalog stores only the resref and presentation metadata. Model and
    texture bytes continue to resolve from the user's configured game install.
    """

    asset_id: str
    label: str
    category: str
    game: str
    model_resref: str
    suggested_scale: float = 1.0
    source_yaw_degrees: float = 0.0
    tags: tuple[str, ...] = ()


_RETAIL_MODEL_ASSETS = (
    RetailModelTerrainKitAsset(
        asset_id="retail:k2:v_ehawk",
        label="Landed Ebon Hawk",
        category="Vehicles & Landing Craft",
        game="K2",
        model_resref="v_ehawk",
        suggested_scale=0.58,
        source_yaw_degrees=90.0,
        tags=("rhen var", "vehicle", "spacecraft", "landing landmark"),
    ),
)


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

_CAVE_PORTAL_ASSET_ROOT = Path("assets/map_studio/terrain_kits/cave_portals")
_CAVE_PORTAL_ASSETS = (
    TerrainKitAsset(
        "korriban_cave_entrance",
        "Korriban Carved Cave Entrance",
        "Module Transitions",
        "KorribanCaveEntranceMirrored.obj",
        texture_resref="gr_korrentr",
        source_units="centimeters",
        source_up_axis="y",
        asset_path=str(_CAVE_PORTAL_ASSET_ROOT / "KorribanCaveEntranceMirrored.obj"),
        triangle_count=6470,
        dimensions_m=(0.7764, 0.8450, 0.4509),
        tags=("korriban", "tomb", "cave", "entrance", "portal", "carved", "two-way"),
    ),
    TerrainKitAsset(
        "shyrack_cave_entrance",
        "Shyrack Cave Entrance",
        "Module Transitions",
        "ShyrackCaveEntranceMirrored.obj",
        texture_resref="gr_shyrentr",
        source_units="meters",
        source_up_axis="y",
        asset_path=str(_CAVE_PORTAL_ASSET_ROOT / "ShyrackCaveEntranceMirrored.obj"),
        triangle_count=6273,
        dimensions_m=(1.0000, 0.7586, 0.4487),
        tags=("korriban", "shyrack", "cave", "entrance", "portal", "rock", "two-way"),
    ),
    TerrainKitAsset(
        "shadowlands_module_transition",
        "Shadowlands Tree Tunnel Transition",
        "Module Transitions",
        "ShadowlandsModuleTransition.obj",
        texture_resref="gr_shadwarm",
        source_units="meters",
        source_up_axis="y",
        asset_path=str(_CAVE_PORTAL_ASSET_ROOT / "ShadowlandsModuleTransition.obj"),
        triangle_count=4795,
        dimensions_m=(0.6634, 1.0000, 0.6282),
        tags=("shadowlands", "jungle", "trees", "forest", "tunnel", "module", "transition", "two-way"),
    ),
)
_MODULE_TRANSITION_ASSET_IDS = frozenset(asset.asset_id for asset in _CAVE_PORTAL_ASSETS)
_RHEN_VAR_ASSET_ROOT = Path("assets/map_studio/terrain_kits/rhen_var")
_RHEN_VAR_MANIFEST_SCHEMA = "ghostrigger.rhen-var-asset-pack/v1"


def _manifest_material_textures(value: Any) -> tuple[tuple[str, str, str], ...]:
    """Normalize exact OBJ-material texture rows from an asset manifest.

    The legacy ``texture_resref`` remains the fallback for single-material
    assets. New imported packs may map each exact ``usemtl`` name to its own
    KOTOR-safe resref and packaged TGA path.
    """

    rows: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        entries = tuple(value.items())
    else:
        entries = tuple(
            (
                str(dict(row or {}).get("material_name") or dict(row or {}).get("material") or ""),
                row,
            )
            for row in tuple(value or ())
            if isinstance(row, dict)
        )
    for material_name, raw in entries:
        material = str(material_name or "").strip()
        details = dict(raw or {}) if isinstance(raw, dict) else {"texture_resref": raw}
        resref = str(details.get("texture_resref") or "").strip().lower()
        if (
            not material
            or not resref
            or len(resref) > 16
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in resref)
        ):
            continue
        texture_file = str(details.get("texture_file") or f"{resref}.tga").strip()
        if not texture_file:
            texture_file = f"{resref}.tga"
        rows.append((material, resref, texture_file))
    return tuple(dict.fromkeys(rows))


@lru_cache(maxsize=1)
def _rhen_var_assets() -> tuple[TerrainKitAsset, ...]:
    """Load the optional, provenance-tracked Rhen Var pack manifest."""

    manifest = next(
        (
            root / _RHEN_VAR_ASSET_ROOT / "manifest.json"
            for root in _candidate_roots()
            if (root / _RHEN_VAR_ASSET_ROOT / "manifest.json").is_file()
        ),
        Path.cwd() / _RHEN_VAR_ASSET_ROOT / "manifest.json",
    )
    if not manifest.is_file():
        return ()
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ()
    if str(payload.get("schema") or "") != _RHEN_VAR_MANIFEST_SCHEMA:
        return ()
    assets: list[TerrainKitAsset] = []
    for raw in tuple(payload.get("assets") or ()):
        row = dict(raw or {})
        asset_id = str(row.get("asset_id") or "").strip().lower()
        obj_name = str(row.get("obj_name") or "").strip()
        dimensions = tuple(float(value) for value in tuple(row.get("dimensions_m") or ())[:3])
        if not asset_id or not obj_name or len(dimensions) != 3:
            continue
        provenance = str(row.get("provenance") or "").strip()
        source_author = str(row.get("source_author") or "").strip()
        source_mod_id = str(row.get("source_mod_id") or "").strip()
        assets.append(
            TerrainKitAsset(
                asset_id=asset_id,
                label=str(row.get("label") or asset_id),
                category=str(row.get("category") or "Rhen Var"),
                obj_name=obj_name,
                texture_resref=str(row.get("texture_resref") or "gr_rvstone").strip().lower(),
                material_textures=_manifest_material_textures(row.get("material_textures")),
                collision_intent=str(row.get("collision_intent") or "").strip(),
                collision_mode=str(row.get("collision_mode") or "").strip().lower(),
                provenance=provenance,
                source_author=source_author,
                source_mod_id=source_mod_id,
                source_units=str(row.get("source_units") or "meters"),
                source_up_axis=str(row.get("source_up_axis") or "z"),
                asset_path=str(_RHEN_VAR_ASSET_ROOT / obj_name),
                triangle_count=max(0, int(row.get("triangle_count") or 0)),
                dimensions_m=dimensions,
                tags=tuple(
                    dict.fromkeys(
                        (
                            "rhen var",
                            "snow",
                            *((provenance,) if provenance else ()),
                            *((source_author,) if source_author else ()),
                            *((source_mod_id,) if source_mod_id else ()),
                            *(str(value) for value in tuple(row.get("tags") or ())),
                        )
                    )
                ),
            )
        )
    return tuple(assets)

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
        "261tel",                       # Telos polar plateau / Rhen Var reference
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


def terrain_kit_assets(
    *,
    game: str = "",
) -> tuple[TerrainKitAsset | VanillaTerrainKitAsset | RetailModelTerrainKitAsset, ...]:
    wanted_game = str(game or "").strip().upper()
    vanilla = tuple(
        asset
        for asset in vanilla_terrain_kit_assets()
        if not wanted_game or asset.game == wanted_game
    )
    retail_models = tuple(
        asset
        for asset in _RETAIL_MODEL_ASSETS
        if not wanted_game or asset.game == wanted_game
    )
    return (
        _DANTOOINE_ASSETS
        + _CAVE_PORTAL_ASSETS
        + _rhen_var_assets()
        + _dathomir_assets()
        + retail_models
        + vanilla
    )


def terrain_kit_asset(
    asset_id: str,
) -> TerrainKitAsset | VanillaTerrainKitAsset | RetailModelTerrainKitAsset:
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
    if not path.is_absolute():
        path = next(
            (root / path for root in _candidate_roots() if (root / path).is_file()),
            Path.cwd() / path,
        )
    if not path.is_file():
        raise FileNotFoundError(f"Terrain kit source is missing: {path}")
    return path


def _terrain_kit_texture_rows(asset: TerrainKitAsset) -> tuple[tuple[str, str, str], ...]:
    """Return exact material/resref/file rows with a legacy fallback."""

    rows = tuple(asset.material_textures or ())
    if rows:
        return rows
    resref = str(asset.texture_resref or "").strip().lower()
    return (("", resref, f"{resref}.tga"),) if resref else ()


def _terrain_kit_texture_path(asset: TerrainKitAsset, texture_file: str, texture_resref: str) -> Path:
    """Resolve one packaged TGA without assuming it sits beside the OBJ."""

    raw_path = Path(str(texture_file or "").strip())
    obj_path = terrain_kit_asset_path(asset)
    candidates: list[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend(
            root / _RHEN_VAR_ASSET_ROOT / raw_path
            for root in _candidate_roots()
        )
        candidates.extend(
            (
                obj_path.parent / raw_path,
                obj_path.parent / raw_path.name,
                obj_path.with_name(f"{texture_resref}.tga"),
            )
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Packaged terrain texture {texture_file or f'{texture_resref}.tga'} "
        f"for {asset.obj_name} could not be resolved."
    )


def terrain_kit_runtime_resources(project: Any) -> tuple[tuple[str, str, bytes], ...]:
    """Return custom KOTOR TGA resources used by placed loose-OBJ kit pieces.

    The KMAP stores lightweight asset provenance and the compiled room mesh.
    Texture pixels stay in the shipped kit directory and are resolved into the
    final MOD only when an authored room actually references that kit asset.
    """

    packaged_assets = {
        asset.asset_id: asset
        for asset in _CAVE_PORTAL_ASSETS + _rhen_var_assets()
    }
    required: set[str] = set()
    for room in tuple(getattr(project, "rooms", ()) or ()):
        metadata = dict(getattr(room, "metadata", {}) or {})
        primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
        asset_id = str(
            metadata.get("terrain_kit_asset_id")
            or primitive_metadata.get("terrain_kit_asset_id")
            or ""
        ).strip().lower()
        if asset_id in packaged_assets:
            required.add(asset_id)
        for opening in tuple(getattr(getattr(room, "primitive", None), "openings", ()) or ()):
            transition_asset = str(
                dict(getattr(opening, "metadata", {}) or {}).get("module_transition_asset_id")
                or ""
            ).strip().lower()
            if transition_asset in packaged_assets:
                required.add(transition_asset)
    resources: list[tuple[str, str, bytes]] = []
    emitted_resrefs: set[str] = set()
    for asset_id in sorted(required):
        asset = packaged_assets[asset_id]
        for _material_name, texture_resref, texture_file in _terrain_kit_texture_rows(asset):
            if texture_resref in emitted_resrefs:
                continue
            texture_path = _terrain_kit_texture_path(asset, texture_file, texture_resref)
            resources.append((texture_resref, "tga", texture_path.read_bytes()))
            emitted_resrefs.add(texture_resref)
    return tuple(resources)


def module_transition_asset_for_profiles(owner_profile: str, target_profile: str) -> str:
    """Choose the one visual shell owned by a connected floor-plan opening."""

    owner = str(owner_profile or "").strip().lower()
    target = str(target_profile or "").strip().lower()
    if "shadowlands" in {owner, target}:
        return "shadowlands_module_transition"
    cave_profiles = {"korriban_caves_k1", "korriban_caves_k2"}
    tomb_profiles = {"korriban_tombs", "korriban_tombs_k2"}
    if owner in tomb_profiles and target in cave_profiles:
        return "korriban_cave_entrance"
    if owner in cave_profiles and target in tomb_profiles:
        return "shyrack_cave_entrance"
    return ""


@lru_cache(maxsize=48)
def _module_transition_source_primitive(
    asset_id: str,
    room_resref: str,
    game: str,
    scale: float,
) -> ImportedMeshRoomPrimitive:
    return _build_supplied_terrain_kit_primitive(
        asset_id,
        room_resref,
        game,
        0.0,
        float(scale),
    )


@lru_cache(maxsize=96)
def module_transition_fit_contract(
    asset_id: str,
    opening_width: float,
    opening_height: float = 2.60,
    game: str = "K1",
) -> ModuleTransitionFitContract:
    """Measure one supplied transition and define its shared host-wall fit.

    Shadowlands uses a stable authored scale.  Scaling that tree facade from
    the much narrower retail WOK portal made every attachment a different
    size and guaranteed that the decorative walls protruded through the host
    berm.  Other transition families retain their established proportional
    fit until their own visual contracts are revised.
    """

    clean_asset = str(asset_id or "").strip().lower()
    if clean_asset not in _MODULE_TRANSITION_ASSET_IDS:
        raise ValueError(f"Unknown module transition asset: {asset_id!r}")
    nominal_scale = {
        "korriban_cave_entrance": 9.50,
        "shyrack_cave_entrance": 8.25,
        "shadowlands_module_transition": 8.00,
    }[clean_asset]
    source_yaw_degrees = {
        "korriban_cave_entrance": 180.0,
        "shyrack_cave_entrance": 90.0,
        "shadowlands_module_transition": 90.0,
    }[clean_asset]
    if clean_asset == "shadowlands_module_transition":
        # The supplied root tunnel was authored at a deliberately neutral unit
        # scale.  At 5.60 m wide its trees read smaller than the surrounding
        # retail Shadowlands trunks.  The 6.30 m fit keeps the passage human
        # scale while restoring the heavy forest silhouette.
        uniform_scale = 6.30
    else:
        uniform_scale = nominal_scale * max(
            0.65,
            min(1.65, float(opening_width) / 5.25),
        )
    source = _module_transition_source_primitive(
        clean_asset,
        "grtransitionfit",
        str(game or "K1").upper(),
        round(uniform_scale, 6),
    )
    yaw = math.radians(source_yaw_degrees)
    yaw_cos = math.cos(yaw)
    yaw_sin = math.sin(yaw)
    points = tuple(
        (
            yaw_cos * float(vertex[0]) - yaw_sin * float(vertex[1]),
            yaw_sin * float(vertex[0]) + yaw_cos * float(vertex[1]),
            float(vertex[2]),
        )
        for surface in source.surfaces
        for vertex in tuple(surface.vertices or ())
    )
    if not points:
        raise ValueError(f"Module transition asset {clean_asset!r} has no geometry.")
    width = max(point[0] for point in points) - min(point[0] for point in points)
    depth = max(point[1] for point in points) - min(point[1] for point in points)
    height = max(point[2] for point in points) - min(point[2] for point in points)
    if clean_asset == "shadowlands_module_transition":
        # Preserve the full tree silhouette in a deliberately wider host
        # recess.  The root plinth is embedded into the terrain so it reads as
        # grown from the berm instead of resting on top of it.
        ground_embed = 0.46
        host_width = width + 0.18
        host_height = max(float(opening_height), height - ground_embed + 0.12)
        clearance_width = max(3.40, min(width - 1.10, float(opening_width) + 0.20))
        clearance_height = max(2.75, min(2.90, float(opening_height) - 0.12))
    else:
        ground_embed = 0.0
        host_width = max(float(opening_width), width) + 0.10
        host_height = max(float(opening_height), height) + 0.08
        clearance_width = max(
            2.00,
            min(float(opening_width) * 0.60, max(2.00, float(opening_width) - 0.70)),
        )
        clearance_height = max(2.15, min(2.75, float(opening_height) - 0.18))
    return ModuleTransitionFitContract(
        asset_id=clean_asset,
        uniform_scale=float(uniform_scale),
        source_yaw_degrees=float(source_yaw_degrees),
        source_width_m=float(width),
        source_depth_m=float(depth),
        source_height_m=float(height),
        host_opening_width_m=float(host_width),
        host_opening_height_m=float(host_height),
        actor_clearance_width_m=float(clearance_width),
        actor_clearance_height_m=float(clearance_height),
        ground_embed_m=float(ground_embed),
    )


def build_module_transition_shell_meshes(
    asset_id: str,
    *,
    room_resref: str,
    edge_index: int,
    opening_name: str,
    center: tuple[float, float, float],
    tangent: tuple[float, float],
    inward_normal: tuple[float, float],
    opening_width: float,
    connected_room_resref: str,
    opening_height: float = 2.60,
    transition_length_m: float = 0.0,
    game: str = "K1",
) -> tuple[PrimitiveMesh, ...]:
    """Fit one supplied two-way transition shell onto a shared room portal.

    OBJ UV0 and normals are preserved.  Scaling is uniform, and the source
    X/Y/Z axes become portal tangent/depth/up in room-local coordinates.  The
    shell is visual-only; the authored reciprocal WOK portal and generated
    floor/throat remain the collision owners.  The source mesh is clipped to a
    portal-sized envelope and a central actor-clear volume before placement.
    This keeps decorative roots/rocks from spearing through room walls or the
    walkable tunnel while interpolating UV0 and normals at every cut edge.
    """

    clean_asset = str(asset_id or "").strip().lower()
    if clean_asset not in _MODULE_TRANSITION_ASSET_IDS:
        return ()
    fit = module_transition_fit_contract(
        clean_asset,
        float(opening_width),
        float(opening_height),
        str(game or "K1").upper(),
    )
    source_yaw_degrees = float(fit.source_yaw_degrees)
    uniform_scale = float(fit.uniform_scale)
    source = _module_transition_source_primitive(
        clean_asset,
        str(room_resref or "grtransition")[:16],
        str(game or "K1").upper(),
        round(uniform_scale, 6),
    )
    tx, ty = (float(tangent[0]), float(tangent[1]))
    nx, ny = (float(inward_normal[0]), float(inward_normal[1]))
    yaw = math.radians(source_yaw_degrees)
    yaw_cos = math.cos(yaw)
    yaw_sin = math.sin(yaw)
    cx, cy, cz = (float(value) for value in center)
    ground_embed = float(fit.ground_embed_m)

    def portal_point(value: tuple[float, float, float]) -> tuple[float, float, float]:
        source_x = yaw_cos * float(value[0]) - yaw_sin * float(value[1])
        source_y = yaw_sin * float(value[0]) + yaw_cos * float(value[1])
        return (source_x, source_y, float(value[2]))

    def world_point(value: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            cx + tx * float(value[0]) + nx * float(value[1]),
            cy + ty * float(value[0]) + ny * float(value[1]),
            cz + float(value[2]) - ground_embed,
        )

    def portal_normal(value: tuple[float, float, float]) -> tuple[float, float, float]:
        source_x = yaw_cos * float(value[0]) - yaw_sin * float(value[1])
        source_y = yaw_sin * float(value[0]) + yaw_cos * float(value[1])
        return (source_x, source_y, float(value[2]))

    def world_normal(value: tuple[float, float, float]) -> tuple[float, float, float]:
        transformed = (tx * value[0] + nx * value[1], ty * value[0] + ny * value[1], value[2])
        length = math.sqrt(sum(component * component for component in transformed)) or 1.0
        return tuple(component / length for component in transformed)

    source_points = tuple(
        portal_point(vertex)
        for surface in source.surfaces
        for vertex in tuple(surface.vertices or ())
    )
    if not source_points:
        return ()
    source_depth_min = min(point[1] for point in source_points)
    source_depth_max = max(point[1] for point in source_points)
    source_depth_span = max(0.25, source_depth_max - source_depth_min)
    requested_length = max(source_depth_span, float(transition_length_m or 0.0))
    tile_step = max(0.25, source_depth_span - min(0.45, source_depth_span * 0.10))
    tile_count = max(1, int(math.ceil(max(0.0, requested_length - source_depth_span) / tile_step)) + 1)
    tiled_depth_span = source_depth_span + float(tile_count - 1) * tile_step
    tile_offsets = tuple(
        (float(index) - float(tile_count - 1) * 0.5) * tile_step
        for index in range(tile_count)
    )
    depth_limit_min = -max(requested_length, tiled_depth_span) * 0.5
    depth_limit_max = max(requested_length, tiled_depth_span) * 0.5
    shell_half_width = float(fit.host_opening_width_m) * 0.5
    clearance_half_width = float(fit.actor_clearance_width_m) * 0.5
    clearance_height = float(fit.actor_clearance_height_m)
    preserve_source_opening = clean_asset == "shadowlands_module_transition"
    tolerance = 1.0e-6

    def normalise(value: tuple[float, ...]) -> tuple[float, float, float]:
        x, y, z = (float(value[index]) if index < len(value) else 0.0 for index in range(3))
        length = math.sqrt((x * x) + (y * y) + (z * z))
        return (x / length, y / length, z / length) if length > 1.0e-8 else (0.0, 0.0, 1.0)

    def lerp(first: tuple[float, ...], second: tuple[float, ...], fraction: float) -> tuple[float, ...]:
        return tuple(float(a) + ((float(b) - float(a)) * fraction) for a, b in zip(first, second))

    def clip_half_space(
        polygon: list[dict[str, tuple[float, ...]]],
        signed_distance: Any,
        *,
        keep_inside: bool,
    ) -> list[dict[str, tuple[float, ...]]]:
        if not polygon:
            return []
        result: list[dict[str, tuple[float, ...]]] = []
        previous = polygon[-1]
        previous_distance = float(signed_distance(previous["position"]))
        previous_kept = (
            previous_distance >= -tolerance
            if keep_inside
            else previous_distance <= tolerance
        )
        for current in polygon:
            current_distance = float(signed_distance(current["position"]))
            current_kept = (
                current_distance >= -tolerance
                if keep_inside
                else current_distance <= tolerance
            )
            if current_kept != previous_kept:
                denominator = previous_distance - current_distance
                fraction = 0.0 if abs(denominator) <= 1.0e-12 else previous_distance / denominator
                fraction = max(0.0, min(1.0, fraction))
                intersection = {
                    key: lerp(value, current.get(key, value), fraction)
                    for key, value in previous.items()
                }
                intersection["normal"] = normalise(intersection.get("normal", (0.0, 0.0, 1.0)))
                result.append(intersection)
            if current_kept:
                result.append(current)
            previous = current
            previous_distance = current_distance
            previous_kept = current_kept
        return result

    envelope_planes = (
        lambda point: float(point[0]) + shell_half_width,
        lambda point: shell_half_width - float(point[0]),
        lambda point: float(point[1]) - depth_limit_min,
        lambda point: depth_limit_max - float(point[1]),
    )
    clearance_planes = (
        lambda point: float(point[0]) + clearance_half_width,
        lambda point: clearance_half_width - float(point[0]),
        lambda point: float(point[1]) - (depth_limit_min - 0.02),
        lambda point: (depth_limit_max + 0.02) - float(point[1]),
        lambda point: float(point[2]) + 0.08,
        lambda point: clearance_height - float(point[2]),
    )

    def clip_to_envelope(
        polygon: list[dict[str, tuple[float, ...]]],
    ) -> list[dict[str, tuple[float, ...]]]:
        result = polygon
        for plane in envelope_planes:
            result = clip_half_space(result, plane, keep_inside=True)
            if len(result) < 3:
                return []
        return result

    def subtract_clearance(
        polygon: list[dict[str, tuple[float, ...]]],
    ) -> list[list[dict[str, tuple[float, ...]]]]:
        candidates = [polygon]
        outside: list[list[dict[str, tuple[float, ...]]]] = []
        for plane in clearance_planes:
            next_candidates: list[list[dict[str, tuple[float, ...]]]] = []
            for candidate in candidates:
                inside = clip_half_space(candidate, plane, keep_inside=True)
                escaped = clip_half_space(candidate, plane, keep_inside=False)
                if len(escaped) >= 3:
                    outside.append(escaped)
                if len(inside) >= 3:
                    next_candidates.append(inside)
            candidates = next_candidates
            if not candidates:
                break
        return outside

    meshes: list[PrimitiveMesh] = []
    for surface_index, surface in enumerate(source.surfaces):
        source_vertices = tuple(surface.vertices or ())
        source_normals = tuple(surface.normals or ())
        source_uvs = tuple(surface.uvs or ())
        has_normals = len(source_normals) == len(source_vertices)
        has_uvs = len(source_uvs) == len(source_vertices)
        for tile_index, tile_offset in enumerate(tile_offsets):
            vertices: list[tuple[float, float, float]] = []
            normals: list[tuple[float, float, float]] = []
            uvs: list[tuple[float, float]] = []
            faces: list[tuple[int, int, int]] = []
            source_face_count = 0
            for face in tuple(surface.faces or ()):
                try:
                    indices = tuple(int(index) for index in tuple(face)[:3])
                    polygon = [
                        {
                            "position": (
                                portal_point(source_vertices[index])[0],
                                portal_point(source_vertices[index])[1] + float(tile_offset),
                                portal_point(source_vertices[index])[2],
                            ),
                            "normal": (
                                portal_normal(source_normals[index])
                                if has_normals
                                else (0.0, 0.0, 1.0)
                            ),
                            "uv": (
                                tuple(float(value) for value in source_uvs[index][:2])
                                if has_uvs
                                else (0.0, 0.0)
                            ),
                        }
                        for index in indices
                    ]
                except (IndexError, TypeError, ValueError):
                    continue
                source_face_count += 1
                bounded = clip_to_envelope(polygon)
                if len(bounded) < 3:
                    continue
                fragments = [bounded] if preserve_source_opening else subtract_clearance(bounded)
                for fragment in fragments:
                    for fragment_index in range(1, len(fragment) - 1):
                        triangle = (fragment[0], fragment[fragment_index], fragment[fragment_index + 1])
                        first_index = len(vertices)
                        vertices.extend(world_point(tuple(vertex["position"][:3])) for vertex in triangle)
                        normals.extend(
                            world_normal(normalise(tuple(vertex["normal"][:3])))
                            for vertex in triangle
                        )
                        if has_uvs:
                            uvs.extend(tuple(float(value) for value in vertex["uv"][:2]) for vertex in triangle)
                        faces.append((first_index, first_index + 1, first_index + 2))
            if not faces:
                continue
            meshes.append(
                PrimitiveMesh(
                    name=(
                        f"{str(room_resref or 'room')[:16]}_transition_e{int(edge_index) + 1:02d}_"
                        f"{clean_asset[:12]}_{surface_index + 1:02d}_t{tile_index + 1:02d}"
                    ),
                    vertices=tuple(vertices),
                    faces=tuple(faces),
                    normals=tuple(normals),
                    uvs=tuple(uvs) if has_uvs else (),
                    texture=str(surface.texture or ""),
                    diffuse=tuple(float(value) for value in surface.diffuse),
                    ambient=tuple(float(value) for value in surface.ambient),
                    metadata={
                        "source": "map_studio:module_transition_asset",
                        "module_transition_asset_id": clean_asset,
                        "module_transition_shell": True,
                        "mirrored_two_way_transition": True,
                        "visual_only": True,
                        "walkmesh_role": "visual_shell",
                        "transition_floor_owner": "generated_reciprocal_wok_portal",
                        "room_resref": str(room_resref or "")[:16],
                        "edge_index": int(edge_index),
                        "opening_name": str(opening_name or ""),
                        "connected_room_resref": str(connected_room_resref or "")[:16],
                        "uniform_scale": float(uniform_scale),
                        "source_yaw_degrees": float(source_yaw_degrees),
                        "uv0_preserved": bool(has_uvs),
                        "source_surface": str(surface.name or ""),
                        "source_face_count": int(source_face_count),
                        "trimmed_face_count": len(faces),
                        "portal_envelope_half_width_m": float(shell_half_width),
                        "host_opening_width_m": float(fit.host_opening_width_m),
                        "host_opening_height_m": float(fit.host_opening_height_m),
                        "source_detail_width_m": float(fit.source_width_m),
                        "source_detail_depth_m": float(fit.source_depth_m),
                        "source_detail_height_m": float(fit.source_height_m),
                        "ground_embed_m": float(ground_embed),
                        "player_clearance_half_width_m": float(clearance_half_width),
                        "player_clearance_height_m": float(clearance_height),
                        "transition_length_m": float(max(requested_length, tiled_depth_span)),
                        "transition_tile_index": int(tile_index),
                        "transition_tile_count": int(tile_count),
                        "transition_tile_offset_m": float(tile_offset),
                        "geometry_trim_policy": (
                            "measured_host_recess_preserve_source_opening"
                            if preserve_source_opening
                            else "detail_preserving_host_recess_minus_actor_clearance"
                        ),
                        "host_surface_overlap_trimmed": True,
                        "host_wall_recess_required": True,
                        "source_opening_preserved": bool(preserve_source_opening),
                    },
                )
            )
    return tuple(meshes)


def _terrain_asset_is_browser_ready(
    asset: TerrainKitAsset | VanillaTerrainKitAsset | RetailModelTerrainKitAsset,
) -> bool:
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


def _terrain_asset_collision_mode(asset: TerrainKitAsset) -> str:
    explicit = str(asset.collision_mode or "").strip().lower()
    if explicit in {
        "walkable_floor_quad",
        "walkable_stair_ramp",
        "visual_only",
        "host_wok_required",
    }:
        return explicit
    intent = str(asset.collision_intent or "").casefold().replace("_", " ")
    if "walkable top plane" in intent:
        return "walkable_floor_quad"
    if "walkable simplified stair ramp" in intent or ("walkable" in intent and "stair" in intent):
        return "walkable_stair_ramp"
    if not intent or "nonblocking" in intent or "visual only" in intent or "visual-only" in intent:
        return "visual_only"
    return "host_wok_required"


def _terrain_asset_collision_status(asset: TerrainKitAsset) -> str:
    mode = _terrain_asset_collision_mode(asset)
    if mode in {"walkable_floor_quad", "walkable_stair_ramp"}:
        return "generated_walkmesh"
    if mode == "visual_only":
        return "visual_only"
    return "authoring_required"


def terrain_kit_asset_rows(*, game: str = "") -> tuple[dict[str, Any], ...]:
    """Return presentation-neutral records for the Terrain content browser."""

    root = terrain_kit_asset_root()
    supplied_assets = _DANTOOINE_ASSETS + _CAVE_PORTAL_ASSETS + _rhen_var_assets() + _dathomir_assets()
    transition_styles = {
        "korriban_cave_entrance": (
            "architecture:k1_korriban_tombs",
            "Korriban Tombs — Carved Stone and Cave Connections",
            9.50,
        ),
        "shyrack_cave_entrance": (
            "architecture:k1_korriban_caves",
            "Korriban Shyrack Caves — Organic Rock Tunnels",
            8.25,
        ),
        "shadowlands_module_transition": (
            "architecture:k1_shadowlands",
            "Kashyyyk Shadowlands — Earthen Clearings, Roots & Foliage",
            6.30,
        ),
    }
    supplied = tuple(
        {
            "asset_id": asset.asset_id,
            "label": asset.label,
            "category": asset.category,
            "source": (
                "Ghost Studio / Module Transitions"
                if asset.asset_id in _MODULE_TRANSITION_ASSET_IDS
                else (
                    f"Rhen Var Asset Pack / {asset.source_author}"
                    if str(asset.source_author or "").strip()
                    else "Rhen Var Asset Pack"
                )
                if "rhen var" in asset.tags
                else "Fallen Order / Dathomir"
                if "dathomir" in asset.tags
                else "Ghost Studio Terrain Kit / Dantooine"
            ),
            "asset_path": str(Path(asset.asset_path) if str(asset.asset_path or "").strip() else root / asset.obj_name),
            "texture_resref": asset.texture_resref,
            "texture_resrefs": tuple(
                dict.fromkeys(
                    texture_resref
                    for _material_name, texture_resref, _texture_file in _terrain_kit_texture_rows(asset)
                )
            ),
            "material_textures": {
                material_name: {
                    "texture_resref": texture_resref,
                    "texture_file": texture_file,
                }
                for material_name, texture_resref, texture_file in tuple(asset.material_textures or ())
            },
            "collision_intent": str(asset.collision_intent or ""),
            "collision_mode": _terrain_asset_collision_mode(asset),
            "provenance": str(asset.provenance or ""),
            "source_author": str(asset.source_author or ""),
            "source_mod_id": str(asset.source_mod_id or ""),
            "collision_status": _terrain_asset_collision_status(asset),
            "collision_ready": _terrain_asset_collision_status(asset) != "authoring_required",
            "triangle_count": int(asset.triangle_count),
            "dimensions_m": tuple(asset.dimensions_m),
            "tags": tuple(asset.tags),
            "suggested_scale": (
                transition_styles[asset.asset_id][2]
                if asset.asset_id in transition_styles
                else 0.35
                if "skybox" in asset.tags
                else 1.0
            ),
            "staging_role": (
                "Two-way module transition"
                if asset.asset_id in _MODULE_TRANSITION_ASSET_IDS
                else "Rhen Var environment staging"
                if "rhen var" in asset.tags
                else "Dathomir environment staging"
                if "dathomir" in asset.tags
                else "Terrain kit staging"
            ),
            "staging_hint": (
                "Drag onto a room doorway to stage the visual shell; the snapped rooms retain walkmesh ownership."
                if asset.asset_id in _MODULE_TRANSITION_ASSET_IDS
                else
                (
                    "Drag onto the snowy landscape; keep buildings and ruins on the 8 m grid and keep the central traversal path clear. "
                    "This solid piece still requires host-walkmesh collision authoring before game export."
                    if _terrain_asset_collision_status(asset) == "authoring_required"
                    else
                    "Drag onto the snowy landscape; keep buildings and ruins on the 8 m grid and keep the central traversal path clear."
                )
                if "rhen var" in asset.tags
                else
                "Drag into a Dathomir map as visual world dressing; surface-snap foliage to terrain and place the planet as a distant vista."
                if "dathomir" in asset.tags
                else "Drag onto terrain or another visible level surface."
            ),
            "building_style_id": (
                transition_styles[asset.asset_id][0]
                if asset.asset_id in transition_styles
                else "architecture:k2_rhen_var"
                if "rhen var" in asset.tags
                else "environment:dathomir"
                if "dathomir" in asset.tags
                else ""
            ),
            "building_style_label": (
                transition_styles[asset.asset_id][1]
                if asset.asset_id in transition_styles
                else "Rhen Var — Authorized Citadel, Colony & Temple Collection"
                if "rhen var" in asset.tags
                else "Dathomir — Fallen Order Extraction"
                if "dathomir" in asset.tags
                else ""
            ),
        }
        for asset in supplied_assets
    )
    wanted_game = str(game or "").strip().upper()
    retail_models = tuple(
        {
            "asset_id": asset.asset_id,
            "label": asset.label,
            "category": asset.category,
            "source": f"{asset.game} retail model · {asset.model_resref}",
            "source_kind": "retail_model",
            "asset_path": "",
            "requires_game": asset.game,
            "texture_resref": "",
            "texture_resrefs": (),
            "material_textures": {},
            "collision_intent": "Visual-only landmark; surrounding authored WOK owns traversal.",
            "collision_mode": "visual_only",
            "collision_status": "visual_only",
            "collision_ready": True,
            "triangle_count": 0,
            "dimensions_m": (0.0, 0.0, 0.0),
            "tags": asset.tags,
            "suggested_scale": float(asset.suggested_scale),
            "suggested_rotation_degrees_z": float(asset.source_yaw_degrees),
            "staging_role": "Movable arrival landmark",
            "staging_hint": (
                "Drag the landed ship onto a clear exterior pad. Keep the ramp "
                "side and the primary route unobstructed."
            ),
            "building_style_id": "architecture:k2_rhen_var",
            "building_style_label": "Rhen Var — Authorized Citadel, Colony & Temple Collection",
            "provenance": "Resolved from the user's KOTOR II installation; no retail bytes are packaged.",
            "source_author": "BioWare / LucasArts",
            "source_mod_id": "",
        }
        for asset in _RETAIL_MODEL_ASSETS
        if (not wanted_game or asset.game == wanted_game)
    )
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
    return supplied + retail_models + vanilla


def terrain_kit_builder_style_id(game: str, module_resref: str) -> str:
    """Group compatible terrain modules under one Pascal building style."""

    tag = str(game or "").strip().upper()
    module = str(module_resref or "").strip().lower()
    if tag == "K1" and module in {"m24aa", "m25aa"}:
        return "architecture:k1_shadowlands"
    if tag == "K2" and module == "261tel":
        return "architecture:k2_rhen_var"
    return ""


def terrain_kit_builder_style_label(style_id: str) -> str:
    return {
        "architecture:k1_shadowlands": "Kashyyyk Shadowlands — Earthen Clearings, Roots & Foliage",
        "architecture:k2_rhen_var": "Rhen Var — Authorized Citadel, Colony & Temple Collection",
    }.get(str(style_id or "").strip().lower(), "")


def terrain_kit_drag_payload(
    asset: TerrainKitAsset | VanillaTerrainKitAsset | RetailModelTerrainKitAsset | str,
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
        "source_kind": (
            "vanilla_game"
            if isinstance(entry, VanillaTerrainKitAsset)
            else "retail_model"
            if isinstance(entry, RetailModelTerrainKitAsset)
            else "supplied_obj"
        ),
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


def _supplied_terrain_bounds(
    primitive: ImportedMeshRoomPrimitive,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points = tuple(
        vertex
        for surface in tuple(primitive.surfaces or ())
        for vertex in tuple(surface.vertices or ())
    )
    if not points:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    return (
        tuple(min(float(point[axis]) for point in points) for axis in range(3)),
        tuple(max(float(point[axis]) for point in points) for axis in range(3)),
    )


def _walkable_quad_wok(
    room_resref: str,
    vertices: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
    *,
    provenance: str,
) -> WOKData:
    wok = WOKData(
        name=str(room_resref or "grterrain")[:16],
        verts=list(vertices),
        faces=[
            WOKFace(0, 1, 2, surface=4, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=4, adj1=0, adj2=-1, adj3=-1),
        ],
    )
    wok.provenance = provenance
    wok.readiness_blocking = False
    return wok


def _supplied_terrain_collision_contract(
    asset: TerrainKitAsset,
    primitive: ImportedMeshRoomPrimitive,
) -> tuple[WOKData | None, str, bool, str]:
    """Return an honest KOTOR WOK contract for one supplied OBJ.

    KOTOR room collision is a floor walkmesh, not arbitrary render-mesh
    collision. Traversal tiles therefore receive small authored floor/ramp
    WOKs. Solid props stay authorable but explicitly block export until Map
    Studio can subtract their footprint from the owning room WOK; pretending
    they were visual-only would silently let the player walk through them.
    """

    intent = str(asset.collision_intent or "").strip()
    collision_mode = _terrain_asset_collision_mode(asset)
    if collision_mode == "walkable_floor_quad":
        minimum, maximum = _supplied_terrain_bounds(primitive)
        floor_z = min(float(maximum[2]), float(minimum[2]) + 0.30)
        return (
            _walkable_quad_wok(
                primitive.room_resref,
                (
                    (minimum[0], minimum[1], floor_z),
                    (maximum[0], minimum[1], floor_z),
                    (maximum[0], maximum[1], floor_z),
                    (minimum[0], maximum[1], floor_z),
                ),
                provenance="rhen_var_manifest_walkable_floor",
            ),
            "generated_walkmesh",
            False,
            "",
        )
    if collision_mode == "walkable_stair_ramp":
        minimum, maximum = _supplied_terrain_bounds(primitive)
        clear_half_width = max(0.25, min(abs(minimum[0]), abs(maximum[0]), 3.85))
        lower_y = max(float(minimum[1]), -4.0)
        upper_y = min(float(maximum[1]), 4.0)
        lower_z = max(float(minimum[2]), 0.0)
        upper_z = min(float(maximum[2]), 3.20)
        return (
            _walkable_quad_wok(
                primitive.room_resref,
                (
                    (-clear_half_width, lower_y, lower_z),
                    (clear_half_width, lower_y, lower_z),
                    (clear_half_width, upper_y, upper_z),
                    (-clear_half_width, upper_y, upper_z),
                ),
                provenance="rhen_var_manifest_walkable_stair_ramp",
            ),
            "generated_walkmesh",
            False,
            "",
        )
    if collision_mode == "visual_only":
        return (
            WOKData(name=str(primitive.room_resref or "grterrain")[:16]),
            "visual_only",
            True,
            "",
        )
    reason = (
        f"{asset.label} declares collision intent '{intent}', but arbitrary solid OBJ collision cannot be "
        "represented safely by an independent room WOK without cutting its footprint from the owning room. "
        "Generate/trim the host walkmesh collision before game export."
    )
    return (None, "authoring_required", False, reason)


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
    exact_materials = {
        material_name: texture_resref
        for material_name, texture_resref, _texture_file in tuple(asset.material_textures or ())
    }
    folded_materials = {
        material_name.casefold(): texture_resref
        for material_name, texture_resref in exact_materials.items()
    }
    material_texture_resrefs = {
        surface.material_name: (
            exact_materials.get(surface.material_name)
            or folded_materials.get(str(surface.material_name or "").casefold())
            or asset.texture_resref
        )
        for surface in document.surfaces
    }
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
        material_texture_resrefs=material_texture_resrefs,
    )
    collision_wok, collision_status, visual_only, collision_reason = _supplied_terrain_collision_contract(
        asset,
        primitive,
    )
    primitive = replace(primitive, wok=collision_wok)
    primitive = transform_terrain_kit_primitive(
        primitive,
        rotation_degrees_z=float(rotation_degrees_z),
        scale=float(scale),
    )
    return replace(
        primitive,
        metadata={
            **dict(primitive.metadata),
            "source": "map_studio:terrain_kit",
            "terrain_kit_asset_id": asset.asset_id,
            "terrain_kit_category": asset.category,
            "terrain_kit_texture_resref": asset.texture_resref,
            "terrain_kit_texture_resrefs": tuple(
                dict.fromkeys(material_texture_resrefs.values())
            ),
            "terrain_kit_material_textures": tuple(
                {
                    "material_name": material_name,
                    "texture_resref": texture_resref,
                    "texture_file": texture_file,
                }
                for material_name, texture_resref, texture_file in tuple(asset.material_textures or ())
            ),
            "terrain_kit_rotation_degrees_z": float(rotation_degrees_z),
            "terrain_kit_scale": float(scale),
            "terrain_kit_collision_intent": str(asset.collision_intent or ""),
            "terrain_kit_collision_mode": _terrain_asset_collision_mode(asset),
            "terrain_kit_collision_status": collision_status,
            "terrain_kit_collision_ready": collision_status in {"generated_walkmesh", "visual_only"},
            "terrain_kit_collision_blocking_reason": collision_reason,
            "terrain_kit_visual_only": visual_only,
            "module_transition_asset": asset.asset_id in _MODULE_TRANSITION_ASSET_IDS,
            "module_transition_floor_required": asset.asset_id in _MODULE_TRANSITION_ASSET_IDS,
            "mirrored_two_way_transition": asset.asset_id in _MODULE_TRANSITION_ASSET_IDS,
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


def _build_retail_model_terrain_kit_primitive(
    asset: RetailModelTerrainKitAsset,
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
        raise ValueError("The active game resource library cannot load retail models.")
    try:
        model = loader(asset.model_resref, asset.game, prefer_base_archive=True)
    except TypeError:
        model = loader(asset.model_resref, asset.game)
    if model is None:
        raise ValueError(
            f"Retail model {asset.model_resref} was not found in the configured {asset.game} installation."
        )
    primitive = build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=str(room_resref or "grterrain")[:16],
        source_model=asset.model_resref,
        game=asset.game,
    )
    vertices = tuple(
        vertex
        for surface in primitive.surfaces
        for vertex in tuple(surface.vertices or ())
    )
    if not vertices:
        raise ValueError(f"{asset.label} has no renderable geometry.")
    min_x = min(float(vertex[0]) for vertex in vertices)
    max_x = max(float(vertex[0]) for vertex in vertices)
    min_y = min(float(vertex[1]) for vertex in vertices)
    max_y = max(float(vertex[1]) for vertex in vertices)
    min_z = min(float(vertex[2]) for vertex in vertices)
    center_x = (min_x + max_x) * 0.5
    center_y = (min_y + max_y) * 0.5
    grounded_surfaces = tuple(
        replace(
            surface,
            vertices=tuple(
                (
                    float(vertex[0]) - center_x,
                    float(vertex[1]) - center_y,
                    float(vertex[2]) - min_z,
                )
                for vertex in tuple(surface.vertices or ())
            ),
            lightmap="",
            uvs_lm=(),
            backdrop=False,
            background_geometry=False,
        )
        for surface in primitive.surfaces
    )
    grounded = replace(
        primitive,
        surfaces=grounded_surfaces,
        wok=WOKData(name=str(room_resref or "grterrain")[:16]),
        metadata={
            **dict(primitive.metadata or {}),
            "source": "map_studio:terrain_kit:retail_model",
            "terrain_kit_asset_id": asset.asset_id,
            "terrain_kit_category": asset.category,
            "terrain_kit_source_game": asset.game,
            "terrain_kit_source_model": asset.model_resref,
            "terrain_kit_collision_mode": "visual_only",
            "terrain_kit_collision_status": "visual_only",
            "terrain_kit_collision_ready": True,
            "terrain_kit_visual_only": True,
            "retail_bytes_packaged": False,
        },
    )
    return transform_terrain_kit_primitive(
        grounded,
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
    if isinstance(asset, RetailModelTerrainKitAsset):
        requested_game = str(game or asset.game).upper()
        if requested_game != asset.game:
            raise ValueError(
                f"{asset.label} is a {asset.game} asset and cannot be exported into {requested_game}."
            )
        return _build_retail_model_terrain_kit_primitive(
            asset,
            room_resref,
            resource_manager=resource_manager,
            rotation_degrees_z=float(rotation_degrees_z),
            scale=float(scale),
        )
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
    "RetailModelTerrainKitAsset",
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
    "terrain_kit_runtime_resources",
    "module_transition_asset_for_profiles",
    "build_module_transition_shell_meshes",
    "transform_terrain_kit_primitive",
    "vanilla_terrain_catalog_path",
    "vanilla_terrain_kit_assets",
    "write_vanilla_terrain_kit_catalog",
]
