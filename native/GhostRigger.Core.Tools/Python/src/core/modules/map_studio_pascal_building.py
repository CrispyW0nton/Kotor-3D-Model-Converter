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
from .map_studio_pascal_graph import planarize_pascal_building_rooms, refresh_pascal_wall_graph


@dataclass(frozen=True)
class PascalBuildingLevel:
    level_index: int
    name: str
    floor_z: float
    floor_to_floor_height: float = 3.0
    room_resrefs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PascalBuildingArchetype:
    """One measured room contour within a broader module art style."""

    archetype_id: str
    label: str
    shell_profile: str
    recommended_wall_height_m: float
    recommended_floor_to_floor_m: float
    description: str = ""
    evidence_rooms: tuple[str, ...] = ()


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
    architecture_profile: str = ""
    architecture_shell_profile: str = ""
    architecture_archetypes: tuple[PascalBuildingArchetype, ...] = ()
    recommended_wall_height_m: float = 3.0
    recommended_floor_to_floor_m: float = 3.0
    recommended_door_width_m: float = 1.25
    recommended_door_height_m: float = 2.2
    accent_textures: tuple[str, ...] = ()
    evidence_rooms: tuple[str, ...] = ()
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


# These are geometry recipes, not texture palettes.  Their dimensions and
# material families are taken from the listed retail room models; the room
# compiler uses the profile token to add bays, ribs, coves, trims, and light
# strips to the user's own footprint.  Keeping the source rooms here makes the
# provenance inspectable and lets the training-corpus scanner reproduce the
# measurements from an installed game without redistributing BioWare assets.
_ARCHITECTURE_STYLES = (
    PascalBuildingStyle(
        style_id="architecture:k1_endar_spire",
        label="Endar Spire — Architecture Kit",
        game="K1",
        floor_texture="lhr_flr01",
        wall_texture="lhr_wall01",
        ceiling_texture="lhr_tech01",
        source_module="m01aa",
        source_room="m01aa_08a",
        architecture_profile="endar_spire",
        architecture_shell_profile="endar_corridor",
        recommended_wall_height_m=3.655,
        recommended_floor_to_floor_m=3.87,
        recommended_door_width_m=6.16,
        recommended_door_height_m=3.01,
        accent_textures=("lhr_red02", "lhr_trim01", "lhr_lit01", "lhr_wall06"),
        evidence_rooms=(
            "m01aa_01a",
            "m01aa_06a",
            "m01aa_08a",
            "m01ab_09a",
            "k2:151har02",
            "k2:152har36",
        ),
        tags=(
            "k1",
            "endar spire",
            "republic warship",
            "harbinger geometry reference",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k2_harbinger",
        label="Harbinger — Republic Warship Architecture Kit",
        game="K2",
        floor_texture="har_fl01",
        wall_texture="har_wl07",
        ceiling_texture="har_tc01",
        source_module="151har",
        source_room="151har02",
        architecture_profile="harbinger",
        architecture_shell_profile="harbinger_corridor",
        recommended_wall_height_m=3.655,
        recommended_floor_to_floor_m=3.87,
        recommended_door_width_m=6.16,
        recommended_door_height_m=3.01,
        accent_textures=("har_wl01", "har_tr02", "har_lt01", "har_wl09"),
        evidence_rooms=("151har02", "151har16", "152har36", "153harff"),
        tags=(
            "k2",
            "harbinger",
            "republic warship",
            "endar geometry lineage",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k2_telos_citadel",
        label="Telos Citadel Station — Architecture Kit",
        game="K2",
        floor_texture="tel_fl05",
        wall_texture="tel_wl06",
        ceiling_texture="tel_fl01",
        source_module="203tel",
        source_room="203telv",
        architecture_profile="telos_citadel",
        architecture_shell_profile="telos_citadel_residential",
        architecture_archetypes=(
            PascalBuildingArchetype(
                archetype_id="residential",
                label="Residential gallery",
                shell_profile="telos_citadel_residential",
                recommended_wall_height_m=3.985,
                recommended_floor_to_floor_m=5.095,
                description=(
                    "Measured 203TEL/204TEL residential contour with a recessed ceiling tray, "
                    "broad canted wall shoulders, luminous utility belt, and framed apartment bays."
                ),
                evidence_rooms=("203telf", "203telv", "204tela", "204telf"),
            ),
            PascalBuildingArchetype(
                archetype_id="civic",
                label="Civic passage",
                shell_profile="telos_citadel_civic",
                recommended_wall_height_m=5.995,
                recommended_floor_to_floor_m=6.739,
                description=(
                    "Measured Entertainment Module passage with deep portal returns, white-grey "
                    "station panels, structural crowns, and inset turquoise light bands."
                ),
                evidence_rooms=("202tel02", "202tel04", "202tel08", "222tel02", "222tel04"),
            ),
            PascalBuildingArchetype(
                archetype_id="concourse",
                label="Citadel concourse",
                shell_profile="telos_citadel_concourse",
                recommended_wall_height_m=6.739,
                recommended_floor_to_floor_m=10.197,
                description=(
                    "Large public-station shell derived from the docking, entertainment, and "
                    "residential hub rooms, with a deeper ceiling coffer and wider structural cadence."
                ),
                evidence_rooms=("201tel05", "201tel06", "203tell", "204telc", "204tele"),
            ),
        ),
        recommended_wall_height_m=3.985,
        recommended_floor_to_floor_m=5.095,
        recommended_door_width_m=3.48,
        recommended_door_height_m=3.029,
        accent_textures=("tel_wl03", "tel_tr04", "tel_lt02", "tel_hcl1"),
        evidence_rooms=(
            "201tel04",
            "201tel05",
            "201tel06",
            "202tel02",
            "202tel04",
            "202tel08",
            "203telf",
            "203telv",
            "203tell",
            "204tela",
            "204telc",
            "204tele",
            "204telf",
            "207tel_1",
        ),
        tags=(
            "k2",
            "telos",
            "citadel station",
            "residential module",
            "entertainment module",
            "docking module",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k1_taris_apartments",
        label="Taris Apartments — Architecture Kit",
        game="K1",
        floor_texture="lts_floor01",
        wall_texture="lts_pwall01i",
        ceiling_texture="lts_nwall04i",
        source_module="m02aa",
        source_room="m02aa_06a",
        architecture_profile="taris_apartments",
        architecture_shell_profile="taris_apartment",
        recommended_wall_height_m=2.55,
        recommended_floor_to_floor_m=3.075,
        recommended_door_width_m=3.0,
        recommended_door_height_m=2.396,
        accent_textures=("lts_pwall04", "lts_trim01", "lts_lite08", "lts_gwall01"),
        evidence_rooms=("m02aa_01a", "m02aa_03a", "m02aa_06a", "m02ad_01a", "m02ad_06a"),
        tags=("k1", "taris", "apartments", "interior", "architecture-kit", "vanilla-derived", "priority"),
    ),
    PascalBuildingStyle(
        style_id="architecture:k1_shadowlands",
        label="Kashyyyk Shadowlands — Earthen Clearing Kit",
        game="K1",
        floor_texture="lka_mud02",
        wall_texture="lka_mud02",
        ceiling_texture="lka_plant03",
        source_module="m24aa",
        source_room="m24aa_02a",
        architecture_profile="shadowlands",
        architecture_shell_profile="shadowlands_root_wall",
        # The stock walkable tiles vary by 10-17 m.  The 6 m parameter drives
        # a broad, irregular dirt berm; full-size ancient roots and trunks
        # remain explicit, draggable retail staging pieces.
        recommended_wall_height_m=6.0,
        recommended_floor_to_floor_m=8.0,
        recommended_door_width_m=4.0,
        recommended_door_height_m=3.25,
        accent_textures=("lka_bark06", "lka_plant02", "lka_plant03", "lka_mud02"),
        evidence_rooms=(
            "m24aa_02a",
            "m24aa_09a",
            "m24aa_13a",
            "m24aa_16a",
            "m25aa_01a",
            "m25aa_04a",
            "m25aa_11a",
            "m25aa_12a",
        ),
        tags=(
            "k1",
            "kashyyyk",
            "shadowlands",
            "upper shadowlands",
            "lower shadowlands",
            "exterior",
            "organic",
            "terrain-wall",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k1_korriban_tombs",
        label="K1 Korriban Tombs — Sith Reliquary Architecture Kit",
        game="K1",
        floor_texture="lko_flr01",
        wall_texture="lko_wal07",
        ceiling_texture="lko_wal07",
        source_module="m37aa",
        source_room="m37aa_02",
        architecture_profile="korriban_tombs",
        architecture_shell_profile="korriban_tomb",
        architecture_archetypes=(
            PascalBuildingArchetype(
                archetype_id="corridor",
                label="Carved tomb corridor",
                shell_profile="korriban_tomb",
                recommended_wall_height_m=3.90,
                recommended_floor_to_floor_m=4.50,
                description=(
                    "Measured 5.4 m × 3.9 m passage contour with 1.5 m carved-section cadence "
                    "from the Ajunta Pall, Marka Ragnos, Tulak Hord, and Naga Sadow corridor families."
                ),
                evidence_rooms=(
                    "m37aa_02",
                    "m37aa_03",
                    "m37aa_11",
                    "m38aa_07",
                    "m38ab_01",
                    "m38ab_07",
                    "m39aa_02",
                    "m39aa_18",
                ),
            ),
            PascalBuildingArchetype(
                archetype_id="chamber",
                label="Reliquary chamber",
                shell_profile="korriban_tomb_chamber",
                recommended_wall_height_m=10.35,
                recommended_floor_to_floor_m=11.10,
                description=(
                    "Measured tall tomb chamber with 3 m relief cadence, corbelled vault shoulders, "
                    "and massive corner supports from m37aa_12, m38aa_08/m38aa_11, and m39aa_07."
                ),
                evidence_rooms=("m37aa_12", "m37aa_16", "m38aa_08", "m38aa_11", "m39aa_07"),
            ),
            PascalBuildingArchetype(
                archetype_id="junction",
                label="Cross-vault junction",
                shell_profile="korriban_tomb_junction",
                recommended_wall_height_m=10.24,
                recommended_floor_to_floor_m=11.10,
                description=(
                    "Measured three- and four-way tomb junction with 4.5 m structural stations, "
                    "cross-vault shoulders, and reinforced corner piers from m38aa_06, m38aa_08, "
                    "and m39aa_16."
                ),
                evidence_rooms=("m38aa_06", "m38aa_08", "m39aa_16"),
            ),
            PascalBuildingArchetype(
                archetype_id="burial",
                label="Burial alcove",
                shell_profile="korriban_tomb_burial",
                recommended_wall_height_m=10.28,
                recommended_floor_to_floor_m=11.10,
                description=(
                    "Measured dead-end burial room with recessed wall niches, stone lintels, "
                    "sarcophagus plinths, and a compact corbelled vault from m37aa_12, "
                    "m38aa_11, and m39aa_13."
                ),
                evidence_rooms=("m37aa_12", "m38aa_11", "m39aa_13"),
            ),
            PascalBuildingArchetype(
                archetype_id="monumental",
                label="Monumental tomb hall",
                shell_profile="korriban_tomb_monumental",
                recommended_wall_height_m=22.08,
                recommended_floor_to_floor_m=23.00,
                description=(
                    "Measured double-height tomb hall with 10.5 m wall modules, giant pylons, "
                    "deep corbelled capitals, and a 22.08 m floor-to-vault rise from the "
                    "9,231-triangle m39aa_07 hall."
                ),
                evidence_rooms=("m39aa_07",),
            ),
        ),
        # Object1806/Object1753 in m37aa_02 establish the reusable corridor
        # aperture: 5.400 m wide, 3.900 m high, with lower relief stations at
        # 0.675 and 1.1625 m.  The 10.35 m model bound is buried exterior shell,
        # not playable headroom.
        recommended_wall_height_m=3.90,
        recommended_floor_to_floor_m=4.50,
        recommended_door_width_m=5.25,
        recommended_door_height_m=3.75,
        accent_textures=("lko_wal08", "lko_tirm01", "lko_rocks", "lko_flr03"),
        evidence_rooms=(
            "m37aa_02",
            "m37aa_03",
            "m37aa_11",
            "m37aa_12",
            "m37aa_16",
            "m38aa_01",
            "m38aa_06",
            "m38aa_07",
            "m38aa_08",
            "m38aa_09",
            "m38aa_11",
            "m38ab_01",
            "m38ab_03",
            "m38ab_04",
            "m38ab_07",
            "m38ab_08",
            "m39aa_02",
            "m39aa_07",
            "m39aa_10",
            "m39aa_13",
            "m39aa_16",
            "m39aa_17",
            "m39aa_18",
        ),
        tags=(
            "k1",
            "korriban",
            "sith tombs",
            "ajunta pall",
            "marka ragnos",
            "tulak hord",
            "naga sadow",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k1_korriban_caves",
        label="K1 Shyrack Caves — Organic Passage Architecture Kit",
        game="K1",
        floor_texture="lrk_flr03",
        wall_texture="lko_cliff01",
        ceiling_texture="lko_cliff01",
        source_module="m34aa",
        source_room="m34aa_01a",
        architecture_profile="korriban_caves_k1",
        architecture_shell_profile="korriban_cave",
        # The reusable authored passage is intentionally smaller than the
        # 40–100 m stock cavern set; full retail caverns remain draggable tiles.
        recommended_wall_height_m=6.25,
        recommended_floor_to_floor_m=7.0,
        recommended_door_width_m=5.0,
        recommended_door_height_m=4.15,
        accent_textures=("lko_rock5", "lko_web", "lka_lightbeams", "lko_water01"),
        evidence_rooms=(
            "m34aa_01a",
            "m34aa_01b",
            "m34aa_02a",
            "m34aa_03a",
            "m34aa_04a",
            "m34aa_05a",
            "m34aa_05b",
            "m34aa_06a",
            "m34aa_07a",
            "m34aa_07b",
            "m34aa_07c",
            "m34aa_08a",
        ),
        tags=(
            "k1",
            "korriban",
            "shyrack caves",
            "sith academy cave",
            "organic",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k2_korriban_tombs",
        label="K2 Secret Tomb — Ruined Sith Architecture Kit",
        game="K2",
        floor_texture="kor_flr01",
        wall_texture="kor_wal07a",
        ceiling_texture="kor_wal07a",
        source_module="711kor",
        source_room="711kora",
        architecture_profile="korriban_tombs_k2",
        architecture_shell_profile="korriban_tomb_ruined",
        recommended_wall_height_m=6.25,
        recommended_floor_to_floor_m=7.00,
        recommended_door_width_m=5.25,
        recommended_door_height_m=3.75,
        accent_textures=("kor_wal06", "kor_tr01", "kor_rocks", "kor_wal08"),
        evidence_rooms=(
            "711kora",
            "711korb",
            "711korc",
            "711kord",
            "711kore",
            "711korf",
            "711korg",
            "711korh",
            "711kori",
            "711korj",
            "711kork",
            "711korl",
            "711korm",
            "711korn",
            "711koro",
            "711korp",
            "711korq",
            "711korr",
            "711kors",
            "711kort",
            "711koru",
        ),
        tags=(
            "k2",
            "korriban",
            "secret tomb",
            "ruined sith architecture",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
    PascalBuildingStyle(
        style_id="architecture:k2_korriban_caves",
        label="K2 Shyrack Caves — Organic Passage Architecture Kit",
        game="K2",
        floor_texture="lrk_flr03",
        wall_texture="kor_cliff01",
        ceiling_texture="kor_cliff01",
        source_module="710kor",
        source_room="710korb",
        architecture_profile="korriban_caves_k2",
        architecture_shell_profile="korriban_cave",
        recommended_wall_height_m=6.25,
        recommended_floor_to_floor_m=7.0,
        recommended_door_width_m=5.0,
        recommended_door_height_m=4.15,
        accent_textures=("kor_rock5", "kor_web", "kor_lightbeams", "kor_water01"),
        evidence_rooms=(
            "710korb",
            "710korc",
            "710kord",
            "710kore",
            "710korf",
            "710korg",
            "710kori",
            "710korj",
            "710kork",
            "710korl",
            "710korm",
            "710korn",
        ),
        tags=(
            "k2",
            "korriban",
            "shyrack caves",
            "organic",
            "interior",
            "architecture-kit",
            "vanilla-derived",
            "priority",
        ),
    ),
)

_VANILLA_STYLE_SCHEMA = "ghostrigger.map-building-style-vanilla/v1"
_VANILLA_STYLE_RELATIVE = Path("assets/map_studio/environment_kits/vanilla_styles.json")
_PASCAL_LEVELS_KEY = "pascal_building_levels"

# Retail K1 genericdoors.2da row 48 resolves to DOR_LHR01.  The model's
# transition/collision mesh measures 6.160 m wide by 3.010 m high, so the
# authored wall opening and the runtime door share one measured contract.
_ARCHITECTURE_DOOR_SPECS: dict[tuple[str, str], dict[str, Any]] = {
    ("K1", "endar_spire"): {
        "template_resref": "gr_enddoor",
        "sealed_template_resref": "gr_endseal",
        "model_resref": "dor_lhr01",
        "appearance_id": 48,
        "label": "Endar Spire Door",
        "opening_width_m": 6.16,
        "opening_height_m": 3.01,
    },
    # tar_m02aa/_s.rim uses appearance 20 (DOR_LTS02) for its apartment
    # entrances.  The m02aa_01a WOK transition threshold measures 4.500 m;
    # the 2.396 m clear height comes from the measured Taris apartment kit
    # profile and fits beneath its 2.55 m wall/ceiling contour.
    ("K1", "taris_apartments"): {
        "template_resref": "gr_tardoor",
        "sealed_template_resref": "gr_tarseal",
        "model_resref": "dor_lts02",
        "appearance_id": 20,
        "label": "Taris Apartment Door",
        "opening_width_m": 4.5,
        "opening_height_m": 2.396,
    },
    # Citadel residential modules use K2 genericdoors.2da row 117
    # (DOR_TEL14). Its measured model envelope is 3.480 m × 3.029 m and the
    # generated wall reveal is built to that same contract.
    ("K2", "telos_citadel"): {
        "template_resref": "gr_teldoor",
        "sealed_template_resref": "gr_telseal",
        "model_resref": "dor_tel14",
        "appearance_id": 117,
        "label": "Telos Citadel Door",
        "opening_width_m": 3.48,
        "opening_height_m": 3.029,
        "frame_width_m": 3.92,
        "frame_height_m": 3.31,
    },
    # Korriban Tombs use the DOR_LKO04 family for their standard stone
    # threshold (K1 genericdoors.2da appearance 40; corroborated by the
    # Korriban tomb module UTDs).  Its 6.802 m outer frame surrounds the
    # measured 5.25 m × 3.75 m playable aperture, so the generated wall cuts
    # the actual passage rather than the decorative frame silhouette.
    ("K1", "korriban_tombs"): {
        "template_resref": "gr_korrdoor",
        "sealed_template_resref": "gr_korrseal",
        "model_resref": "dor_lko04",
        "appearance_id": 40,
        "label": "Korriban Tomb Door",
        "opening_width_m": 5.25,
        "opening_height_m": 3.75,
        "frame_width_m": 6.802,
        "frame_height_m": 3.9,
    },
    ("K2", "korriban_tombs_k2"): {
        "template_resref": "gr_k2kordoor",
        "sealed_template_resref": "gr_k2korseal",
        "model_resref": "dor_lko04",
        "appearance_id": 40,
        "label": "K2 Secret Tomb Door",
        "opening_width_m": 5.25,
        "opening_height_m": 3.75,
        "frame_width_m": 6.802,
        "frame_height_m": 3.9,
    },
}


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
                architecture_profile=str(row.get("architecture_profile") or "").strip().lower(),
                architecture_shell_profile=str(row.get("architecture_shell_profile") or "").strip().lower(),
                architecture_archetypes=tuple(
                    PascalBuildingArchetype(
                        archetype_id=str(dict(value or {}).get("archetype_id") or "").strip().lower(),
                        label=str(dict(value or {}).get("label") or dict(value or {}).get("archetype_id") or ""),
                        shell_profile=str(dict(value or {}).get("shell_profile") or "").strip().lower(),
                        recommended_wall_height_m=float(
                            dict(value or {}).get("recommended_wall_height_m") or 3.0
                        ),
                        recommended_floor_to_floor_m=float(
                            dict(value or {}).get("recommended_floor_to_floor_m") or 3.0
                        ),
                        description=str(dict(value or {}).get("description") or ""),
                        evidence_rooms=tuple(
                            str(room).strip().lower()
                            for room in tuple(dict(value or {}).get("evidence_rooms") or ())
                            if str(room).strip()
                        ),
                    )
                    for value in tuple(row.get("architecture_archetypes") or ())
                    if str(dict(value or {}).get("archetype_id") or "").strip()
                ),
                recommended_wall_height_m=float(row.get("recommended_wall_height_m") or 3.0),
                recommended_floor_to_floor_m=float(row.get("recommended_floor_to_floor_m") or 3.0),
                recommended_door_width_m=float(row.get("recommended_door_width_m") or 1.25),
                recommended_door_height_m=float(row.get("recommended_door_height_m") or 2.2),
                accent_textures=tuple(
                    str(value).strip().lower()
                    for value in tuple(row.get("accent_textures") or ())
                    if str(value).strip()
                ),
                evidence_rooms=tuple(
                    str(value).strip().lower()
                    for value in tuple(row.get("evidence_rooms") or ())
                    if str(value).strip()
                ),
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
                "architecture_profile": style.architecture_profile,
                "architecture_shell_profile": style.architecture_shell_profile,
                "architecture_archetypes": [
                    {
                        "archetype_id": archetype.archetype_id,
                        "label": archetype.label,
                        "shell_profile": archetype.shell_profile,
                        "recommended_wall_height_m": float(archetype.recommended_wall_height_m),
                        "recommended_floor_to_floor_m": float(archetype.recommended_floor_to_floor_m),
                        "description": archetype.description,
                        "evidence_rooms": list(archetype.evidence_rooms),
                    }
                    for archetype in style.architecture_archetypes
                ],
                "recommended_wall_height_m": float(style.recommended_wall_height_m),
                "recommended_floor_to_floor_m": float(style.recommended_floor_to_floor_m),
                "recommended_door_width_m": float(style.recommended_door_width_m),
                "recommended_door_height_m": float(style.recommended_door_height_m),
                "accent_textures": list(style.accent_textures),
                "evidence_rooms": list(style.evidence_rooms),
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
        from .map_studio_environment_kits import (
            environment_kit_collection_display_label,
            vanilla_environment_kit_collections,
        )

        kit_styles = tuple(
            PascalBuildingStyle(
                style_id=f"kit:{collection.collection_id}",
                label=environment_kit_collection_display_label(collection),
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
        for style in (_DEFAULT_STYLES + _ARCHITECTURE_STYLES + kit_styles + vanilla_pascal_building_styles())
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
    architecture_profile: str = "",
    architecture_shell_profile: str = "",
    architecture_archetype: str = "",
    architecture_accent_textures: tuple[str, ...] = (),
    architecture_evidence_rooms: tuple[str, ...] = (),
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
    profile_token = str(architecture_profile or "").strip().lower()
    archetype_token = str(architecture_archetype or "").strip().lower()
    cleaned_points = _clean_points(points)
    korriban_minimums = {
        "chamber": (9.0, 81.0, 9.75, "reliquary chamber"),
        "junction": (10.0, 100.0, 9.75, "cross-vault junction"),
        "burial": (8.0, 64.0, 9.75, "burial alcove"),
        "monumental": (18.0, 324.0, 20.0, "monumental tomb hall"),
    }
    if profile_token == "korriban_tombs" and archetype_token in korriban_minimums:
        minimum_span, minimum_area, minimum_height, label = korriban_minimums[archetype_token]
        span_x = max(point[0] for point in cleaned_points) - min(point[0] for point in cleaned_points)
        span_y = max(point[1] for point in cleaned_points) - min(point[1] for point in cleaned_points)
        if min(span_x, span_y) < minimum_span or abs(polygon_signed_area(cleaned_points)) < minimum_area:
            raise ValueError(
                f"The Korriban {label} needs a footprint at least {minimum_span:g} m wide "
                f"and {minimum_area:g} m²; choose Carved tomb corridor for narrower plans."
            )
        if height < minimum_height:
            raise ValueError(f"The Korriban {label} needs at least {minimum_height:g} m of wall height.")
    if profile_token == "shadowlands":
        # A Shadowlands footprint describes an open-air walkable clearing or
        # path bounded by roots and earth, not a conventional roofed building.
        # Keep this invariant in the headless owner so project files, scripts,
        # and the GUI all compile the same outdoor result.
        kind = "exterior"
        roof = "none"
        include_ceiling = False
    project = set_pascal_building_level(
        project,
        level_index=int(level_index),
        name=str(level_name or f"Level {int(level_index) + 1}"),
        floor_z=z,
        floor_to_floor_height=height,
        include_default_when_empty=False,
        overwrite=False,
    )
    room_resref = _next_room_resref(project)
    source = {
        "source": "map_studio:pascal_building",
        "style_id": str(style_id or "custom"),
        "style_source_module": normalise_resref(style_source_module),
        "style_source_room": normalise_resref(style_source_room),
        "kit_collection_id": str(style_id or "")[4:] if str(style_id or "").startswith("kit:") else "",
        "kit_autobuild": str(style_id or "").startswith("kit:"),
        "architecture_profile": profile_token,
        "architecture_shell_profile": str(architecture_shell_profile or "").strip().lower(),
        "architecture_archetype": archetype_token,
        "architecture_accent_textures": [
            normalize_authored_room_texture(value)
            for value in tuple(architecture_accent_textures or ())
            if str(value or "").strip()
        ],
        "architecture_evidence_rooms": [
            normalise_resref(value)
            for value in tuple(architecture_evidence_rooms or ())
            if normalise_resref(value)
        ],
    }
    primitive = FloorPlanRoomPrimitive(
        room_resref=room_resref,
        points=cleaned_points,
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
            "architecture_archetype": archetype_token,
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
    updated_project = replace(project, rooms=rooms, placements=placements)
    return planarize_pascal_building_rooms(updated_project), room_resref


def pascal_architecture_door_spec(game: str, architecture_profile: str) -> dict[str, Any] | None:
    """Return the measured runtime-door contract for one architecture kit."""

    key = (
        str(game or "K1").strip().upper(),
        str(architecture_profile or "").strip().lower(),
    )
    row = _ARCHITECTURE_DOOR_SPECS.get(key)
    return None if row is None else dict(row)


def pascal_architecture_sealed_door_spec(
    game: str,
    architecture_profile: str,
) -> dict[str, Any] | None:
    """Return the locked, non-transition variant of an authentic style door."""

    row = pascal_architecture_door_spec(game, architecture_profile)
    if row is None:
        return None
    sealed_template = normalise_resref(row.get("sealed_template_resref"))
    if not sealed_template:
        return None
    row["template_resref"] = sealed_template
    row["label"] = f"{str(row.get('label') or 'Area Door')} — Sealed"
    row["sealed"] = True
    return row


def pascal_architecture_profile_for_room(
    project: AuthoredModuleProject,
    room_resref: str,
) -> str:
    """Resolve the measured architecture profile owning one authored/stock room."""

    target = normalise_resref(room_resref)
    room = next(
        (candidate for candidate in project.rooms if candidate.normalised_resref() == target),
        None,
    )
    if room is None:
        return ""
    primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
    profile = str(primitive_metadata.get("architecture_profile") or "").strip().lower()
    if profile:
        return profile

    room_metadata = dict(getattr(room, "metadata", {}) or {})
    style_id = str(room_metadata.get("style_id") or "").strip().lower()
    if not style_id:
        collection_id = str(room_metadata.get("environment_kit_collection_id") or "").strip()
        source_module = str(room_metadata.get("environment_kit_source_module") or "").strip()
        if collection_id or source_module:
            from .map_studio_environment_kits import environment_kit_builder_style_id

            style_id = environment_kit_builder_style_id(
                str(room_metadata.get("environment_kit_source_game") or project.game),
                source_module,
                collection_id,
            ).strip().lower()
    for style in available_pascal_building_styles(str(project.game or "")):
        if style.style_id.strip().lower() == style_id:
            return str(style.architecture_profile or "").strip().lower()
    return ""


@lru_cache(maxsize=8)
def _pascal_architecture_door_bytes(
    game: str,
    architecture_profile: str,
    sealed: bool = False,
) -> bytes:
    """Build a clean, script-free UTD for a style's authentic stock door."""

    spec = (
        pascal_architecture_sealed_door_spec(game, architecture_profile)
        if sealed
        else pascal_architecture_door_spec(game, architecture_profile)
    )
    if spec is None:
        return b""
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.utd import UTD, bytes_utd

    door = UTD()
    door.resref = ResRef(str(spec["template_resref"]))
    door.tag = str(spec["template_resref"])
    door.name = LocalizedString.from_english(str(spec["label"]))
    door.appearance_id = int(spec["appearance_id"])
    door.static = False
    door.lockable = bool(sealed)
    door.locked = bool(sealed)
    door.key_required = bool(sealed)
    door.key_name = "gr_no_key" if sealed else ""
    door.lock_dc = 100 if sealed else 0
    door.unlock_dc = 100 if sealed else 0
    door.not_blastable = True
    door.current_hp = 30
    door.maximum_hp = 30
    door.open_state = 0
    return bytes(bytes_utd(door))


def pascal_architecture_runtime_resources(
    project: AuthoredModuleProject,
) -> tuple[tuple[str, str, bytes], ...]:
    """Return deterministic UTD resources required by generated kit doors.

    KMAP keeps door intent and never embeds opaque binary resources.  Rebuilding
    this small UTD from the style contract keeps cold-open preview and MOD
    export deterministic while still using the retail generic-door model.
    """

    game = str(project.game or "K1").strip().upper()
    required: dict[str, tuple[str, str, bool]] = {}
    for door in tuple(getattr(project.placements, "doors", ()) or ()):
        template = normalise_resref(getattr(door, "template_resref", ""))
        for (spec_game, profile), spec in _ARCHITECTURE_DOOR_SPECS.items():
            if spec_game == game and template == normalise_resref(spec["template_resref"]):
                required[template] = (spec_game, profile, False)
                break
            if spec_game == game and template == normalise_resref(spec.get("sealed_template_resref")):
                required[template] = (spec_game, profile, True)
                break
    return tuple(
        (template, "utd", _pascal_architecture_door_bytes(spec_game, profile, sealed))
        for template, (spec_game, profile, sealed) in sorted(required.items())
    )


def add_pascal_sealed_door(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    opening_name: str,
    position: tuple[float, float, float],
    bearing: float,
):
    """Place one locked style-authentic door across an intentionally sealed hook."""

    profile = pascal_architecture_profile_for_room(project, room_resref)
    spec = pascal_architecture_sealed_door_spec(project.game, profile)
    if spec is None:
        raise ValueError(
            f"Room {normalise_resref(room_resref) or room_resref} has no measured area-door contract; "
            "leave the opening available or mark it as an external module exit."
        )
    from .authored_module_placements import add_authored_gameplay_placement

    room_key = normalise_resref(room_resref)
    opening_key = normalise_resref(opening_name)
    return add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref=str(spec["template_resref"]),
        tag=f"seal_{room_key[-4:]}_{opening_key[-5:]}"[:16],
        position=position,
        bearing=float(bearing),
    )


def _pascal_opening_world_pose(
    room: AuthoredRoomSpec,
    *,
    edge_index: int,
    center_fraction: float,
    bottom: float,
) -> tuple[tuple[float, float, float], float]:
    primitive = room.primitive
    points = tuple(getattr(primitive, "points", ()) or ())
    start = points[int(edge_index)]
    end = points[(int(edge_index) + 1) % len(points)]
    origin = tuple(float(value) for value in tuple(room.position or (0.0, 0.0, 0.0))[:3])
    center = max(0.0, min(1.0, float(center_fraction)))
    world = (
        origin[0] + float(start[0]) + (float(end[0]) - float(start[0])) * center,
        origin[1] + float(start[1]) + (float(end[1]) - float(start[1])) * center,
        origin[2] + float(getattr(primitive, "z", 0.0) or 0.0) + float(bottom),
    )
    bearing = math.atan2(float(end[1]) - float(start[1]), float(end[0]) - float(start[0]))
    return world, bearing


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
    connection_metadata: dict[str, Any] | None = None,
) -> AuthoredModuleProject:
    kind = str(opening_kind or "door").strip().lower()
    if kind not in {"door", "window"}:
        raise ValueError("Building openings must be doors or windows.")
    suppress_door_actor = bool(
        (connection_metadata or {}).get("suppress_door_actor")
        or (connection_metadata or {}).get("open_module_transition")
        or (connection_metadata or {}).get("cave_archway_transition")
    )
    preview = preview_pascal_building_opening(
        project,
        room_resref=room_resref,
        edge_index=edge_index,
        opening_kind=kind,
        center_fraction=center_fraction,
        width=width,
        height=height,
        bottom=bottom,
        suppress_style_door_contract=suppress_door_actor,
    )
    if not preview.valid:
        raise ValueError(preview.reason or f"The {kind} does not fit on this wall.")
    target_room = next(
        room
        for room in project.rooms
        if normalise_resref(room.room_resref) == normalise_resref(room_resref)
    )
    primitive = target_room.primitive
    architecture_profile = str(
        dict(getattr(primitive, "metadata", {}) or {}).get("architecture_profile") or ""
    ).strip().lower()
    door_spec = (
        pascal_architecture_door_spec(project.game, architecture_profile)
        if kind == "door"
        else None
    )
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
                metadata = {
                    **dict(opening.metadata),
                    "pascal_graph_node": kind,
                    "opening_kind": kind,
                    **dict(connection_metadata or {}),
                }
                if door_spec is not None and not suppress_door_actor:
                    metadata.update(
                        {
                            "door_template_resref": str(door_spec["template_resref"]),
                            "door_model_resref": str(door_spec["model_resref"]),
                            "door_appearance_id": int(door_spec["appearance_id"]),
                            "door_aperture_width_m": float(door_spec["opening_width_m"]),
                            "door_aperture_height_m": float(door_spec["opening_height_m"]),
                            "door_outer_width_m": float(
                                door_spec.get("frame_width_m", door_spec["opening_width_m"])
                            ),
                            "door_outer_height_m": float(
                                door_spec.get("frame_height_m", door_spec["opening_height_m"])
                            ),
                            "architecture_role": f"{architecture_profile}_doorway",
                        }
                    )
                opening = replace(
                    opening,
                    metadata=metadata,
                )
            opening_rows.append(opening)
        rooms.append(replace(room, primitive=replace(primitive, openings=tuple(opening_rows))))
    updated = replace(updated, rooms=tuple(rooms))
    if door_spec is not None and not suppress_door_actor:
        from .authored_module_placements import add_authored_gameplay_placement

        position, bearing = _pascal_opening_world_pose(
            target_room,
            edge_index=int(edge_index),
            center_fraction=preview.center_fraction,
            bottom=preview.bottom,
        )
        placement = add_authored_gameplay_placement(
            updated,
            kind="door",
            template_resref=str(door_spec["template_resref"]),
            tag=f"{normalise_resref(room_resref)}_{opening_name}"[:32],
            position=position,
            bearing=bearing,
        )
        updated = placement.project
        rooms = []
        for room in updated.rooms:
            if normalise_resref(room.room_resref) != normalise_resref(room_resref):
                rooms.append(room)
                continue
            opening_rows = tuple(
                replace(
                    opening,
                    metadata={
                        **dict(opening.metadata),
                        "door_placement_id": placement.placement_id,
                    },
                )
                if str(opening.name or "").strip() == opening_name
                else opening
                for opening in tuple(getattr(room.primitive, "openings", ()) or ())
            )
            rooms.append(replace(room, primitive=replace(room.primitive, openings=opening_rows)))
        updated = replace(updated, rooms=tuple(rooms))
    return refresh_pascal_wall_graph(updated)


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
    suppress_style_door_contract: bool = False,
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
    architecture_profile = str(
        dict(getattr(primitive, "metadata", {}) or {}).get("architecture_profile") or ""
    ).strip().lower()
    door_spec = (
        pascal_architecture_door_spec(project.game, architecture_profile)
        if kind == "door" and not bool(suppress_style_door_contract)
        else None
    )
    if door_spec is not None:
        width = float(door_spec["opening_width_m"])
        height = float(door_spec["opening_height_m"])
        bottom = 0.0
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


def _pascal_building_level_rows(project: AuthoredModuleProject) -> dict[int, dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for raw in tuple(dict(getattr(project, "extra", {}) or {}).get(_PASCAL_LEVELS_KEY) or ()):
        row = dict(raw or {})
        try:
            index = int(row.get("level_index", 0))
            floor_z = float(row.get("floor_z", 0.0))
            height = max(0.25, float(row.get("floor_to_floor_height", 3.0) or 3.0))
        except (TypeError, ValueError):
            continue
        if index < 0 or not all(math.isfinite(value) for value in (floor_z, height)):
            continue
        grouped[index] = {
            "name": str(row.get("name") or f"Level {index + 1}"),
            "floor_z": floor_z,
            "floor_to_floor_height": height,
            "rooms": [],
        }
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
                "floor_to_floor_height": max(0.25, float(getattr(primitive, "wall_height", 3.0) or 3.0)),
                "rooms": [],
            },
        )
        row["rooms"].append(normalise_resref(room.room_resref))
    return grouped


def set_pascal_building_level(
    project: AuthoredModuleProject,
    *,
    level_index: int,
    name: str = "",
    floor_z: float = 0.0,
    floor_to_floor_height: float = 3.0,
    include_default_when_empty: bool = True,
    overwrite: bool = True,
) -> AuthoredModuleProject:
    """Persist one semantic level without changing authored room coordinates."""

    index = int(level_index)
    elevation = float(floor_z)
    height = max(0.25, float(floor_to_floor_height))
    if index < 0:
        raise ValueError("Building level index must be zero or greater.")
    if not all(math.isfinite(value) for value in (elevation, height)):
        raise ValueError("Building level elevation and height must be finite.")
    grouped = _pascal_building_level_rows(project)
    if not grouped and include_default_when_empty and index != 0:
        grouped[0] = {
            "name": "Level 1",
            "floor_z": 0.0,
            "floor_to_floor_height": height,
            "rooms": [],
        }
    if overwrite or index not in grouped:
        rooms = list(grouped.get(index, {}).get("rooms", ()))
        grouped[index] = {
            "name": str(name or f"Level {index + 1}"),
            "floor_z": elevation,
            "floor_to_floor_height": height,
            "rooms": rooms,
        }
    extra = dict(getattr(project, "extra", {}) or {})
    extra[_PASCAL_LEVELS_KEY] = [
        {
            "level_index": level,
            "name": str(row["name"]),
            "floor_z": float(row["floor_z"]),
            "floor_to_floor_height": float(row["floor_to_floor_height"]),
        }
        for level, row in sorted(grouped.items())
    ]
    return replace(project, extra=extra)


def pascal_building_levels(project: AuthoredModuleProject) -> tuple[PascalBuildingLevel, ...]:
    grouped = _pascal_building_level_rows(project)
    if not grouped:
        grouped[0] = {
            "name": "Level 1",
            "floor_z": 0.0,
            "floor_to_floor_height": 3.0,
            "rooms": [],
        }
    return tuple(
        PascalBuildingLevel(
            level_index=index,
            name=row["name"],
            floor_z=row["floor_z"],
            floor_to_floor_height=row["floor_to_floor_height"],
            room_resrefs=tuple(row["rooms"]),
        )
        for index, row in sorted(grouped.items())
    )


_ARCHITECTURE_TRAINING_ROOMS: dict[str, tuple[tuple[str, str], ...]] = {
    "endar_spire": (
        ("m01aa", "m01aa_01a"),
        ("m01aa", "m01aa_06a"),
        ("m01aa", "m01aa_08a"),
        ("m01ab", "m01ab_09a"),
    ),
    "taris_apartments": (
        ("m02aa", "m02aa_01a"),
        ("m02aa", "m02aa_03a"),
        ("m02aa", "m02aa_06a"),
        ("m02ad", "m02ad_01a"),
        ("m02ad", "m02ad_06a"),
    ),
    "harbinger": (
        ("151har", "151har02"),
        ("151har", "151har16"),
        ("152har", "152har36"),
        ("153har", "153harff"),
    ),
    "telos_citadel": (
        ("201tel", "201tel04"),
        ("201tel", "201tel05"),
        ("201tel", "201tel06"),
        ("202tel", "202tel02"),
        ("202tel", "202tel04"),
        ("202tel", "202tel08"),
        ("203tel", "203telf"),
        ("203tel", "203telv"),
        ("203tel", "203tell"),
        ("204tel", "204tela"),
        ("204tel", "204telc"),
        ("204tel", "204tele"),
        ("204tel", "204telf"),
        ("207tel", "207tel_1"),
    ),
    "shadowlands": (
        ("m24aa", "m24aa_02a"),
        ("m24aa", "m24aa_09a"),
        ("m24aa", "m24aa_13a"),
        ("m24aa", "m24aa_16a"),
        ("m25aa", "m25aa_01a"),
        ("m25aa", "m25aa_04a"),
        ("m25aa", "m25aa_11a"),
        ("m25aa", "m25aa_12a"),
    ),
    "korriban_tombs": (
        ("m37aa", "m37aa_02"),
        ("m37aa", "m37aa_03"),
        ("m37aa", "m37aa_11"),
        ("m37aa", "m37aa_12"),
        ("m37aa", "m37aa_16"),
        ("m38aa", "m38aa_01"),
        ("m38aa", "m38aa_06"),
        ("m38aa", "m38aa_07"),
        ("m38aa", "m38aa_08"),
        ("m38aa", "m38aa_09"),
        ("m38aa", "m38aa_11"),
        ("m38ab", "m38ab_01"),
        ("m38ab", "m38ab_03"),
        ("m38ab", "m38ab_04"),
        ("m38ab", "m38ab_07"),
        ("m38ab", "m38ab_08"),
        ("m39aa", "m39aa_02"),
        ("m39aa", "m39aa_07"),
        ("m39aa", "m39aa_10"),
        ("m39aa", "m39aa_13"),
        ("m39aa", "m39aa_16"),
        ("m39aa", "m39aa_17"),
        ("m39aa", "m39aa_18"),
    ),
    "korriban_caves_k1": (
        ("m34aa", "m34aa_01a"),
        ("m34aa", "m34aa_02a"),
        ("m34aa", "m34aa_03a"),
        ("m34aa", "m34aa_04a"),
        ("m34aa", "m34aa_05a"),
        ("m34aa", "m34aa_05b"),
        ("m34aa", "m34aa_06a"),
        ("m34aa", "m34aa_07a"),
        ("m34aa", "m34aa_07b"),
        ("m34aa", "m34aa_07c"),
        ("m34aa", "m34aa_08a"),
        ("m34aa", "m34aa_01b"),
        ("m34aa", "m34aa_09"),
    ),
    "korriban_tombs_k2": (
        ("711kor", "711kora"),
        ("711kor", "711korb"),
        ("711kor", "711korc"),
        ("711kor", "711kord"),
        ("711kor", "711kore"),
        ("711kor", "711korf"),
        ("711kor", "711korg"),
        ("711kor", "711korh"),
        ("711kor", "711kori"),
        ("711kor", "711korj"),
        ("711kor", "711kork"),
        ("711kor", "711korl"),
        ("711kor", "711korm"),
        ("711kor", "711korn"),
        ("711kor", "711koro"),
        ("711kor", "711korp"),
        ("711kor", "711korq"),
        ("711kor", "711korr"),
        ("711kor", "711kors"),
        ("711kor", "711kort"),
        ("711kor", "711koru"),
    ),
    "korriban_caves_k2": (
        ("710kor", "710korb"),
        ("710kor", "710korc"),
        ("710kor", "710kord"),
        ("710kor", "710kore"),
        ("710kor", "710korf"),
        ("710kor", "710korg"),
        ("710kor", "710kori"),
        ("710kor", "710korj"),
        ("710kor", "710kork"),
        ("710kor", "710korl"),
        ("710kor", "710korm"),
        ("710kor", "710korn"),
    ),
}

_ARCHITECTURE_TRAINING_GAMES = {
    "endar_spire": "K1",
    "taris_apartments": "K1",
    "harbinger": "K2",
    "telos_citadel": "K2",
    "shadowlands": "K1",
    "korriban_tombs": "K1",
    "korriban_caves_k1": "K1",
    "korriban_tombs_k2": "K2",
    "korriban_caves_k2": "K2",
}


def architecture_training_room_specs(profile: str) -> tuple[tuple[str, str], ...]:
    """Return the retail module/room evidence set for one build profile."""

    return _ARCHITECTURE_TRAINING_ROOMS.get(str(profile or "").strip().lower(), ())


def architecture_training_game(profile: str) -> str:
    """Return the installed game that owns one architecture evidence set."""

    return _ARCHITECTURE_TRAINING_GAMES.get(str(profile or "").strip().lower(), "K1")


def classify_architecture_surface(surface: Any) -> dict[str, Any]:
    """Classify one baked stock surface for architecture-corpus training.

    The record intentionally carries confidence and evidence.  The automated
    split handles high-confidence floor, ceiling, wall, trim, and light cases;
    ambiguous props/details remain reviewable instead of being silently used
    as construction pieces.
    """

    vertices = tuple(getattr(surface, "vertices", ()) or ())
    faces = tuple(getattr(surface, "faces", ()) or ())
    texture = str(getattr(surface, "texture", "") or "").strip().lower()
    name = str(getattr(surface, "name", "") or "").strip().lower()
    evidence = f"{name} {texture}"
    bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if vertices:
        bounds = (
            min(float(value[0]) for value in vertices),
            min(float(value[1]) for value in vertices),
            min(float(value[2]) for value in vertices),
            max(float(value[0]) for value in vertices),
            max(float(value[1]) for value in vertices),
            max(float(value[2]) for value in vertices),
        )
    total_area = 0.0
    signed_normal_z = 0.0
    absolute_normal_z = 0.0
    for raw_face in faces:
        try:
            a, b, c = (vertices[int(index)] for index in tuple(raw_face)[:3])
        except (IndexError, TypeError, ValueError):
            continue
        ab = (float(b[0]) - float(a[0]), float(b[1]) - float(a[1]), float(b[2]) - float(a[2]))
        ac = (float(c[0]) - float(a[0]), float(c[1]) - float(a[1]), float(c[2]) - float(a[2]))
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        twice_area = math.sqrt(sum(value * value for value in cross))
        if twice_area <= 1.0e-10:
            continue
        area = twice_area * 0.5
        normal_z = cross[2] / twice_area
        total_area += area
        signed_normal_z += normal_z * area
        absolute_normal_z += abs(normal_z) * area
    signed_z = signed_normal_z / total_area if total_area > 1.0e-10 else 0.0
    horizontal = absolute_normal_z / total_area if total_area > 1.0e-10 else 0.0
    dimensions = (bounds[3] - bounds[0], bounds[4] - bounds[1], bounds[5] - bounds[2])
    role = "detail"
    confidence = 0.55
    reason = "mixed orientation or unrecognized material"
    if any(token in evidence for token in ("_lit", "lite", "light", "lamp", "glow")):
        role, confidence, reason = "light", 0.96, "light material/name token"
    elif any(token in evidence for token in ("trim", "pipe", "column", "pillar", "rib")):
        role, confidence, reason = "trim", 0.92, "trim/structure material token"
    elif any(token in evidence for token in ("flr", "floor", "ground", "deck")):
        role, confidence, reason = "floor", 0.95, "floor material/name token"
    elif any(token in evidence for token in ("ceil", "roof", "overhead")):
        role, confidence, reason = "ceiling", 0.95, "ceiling material/name token"
    elif horizontal >= 0.78 and dimensions[2] <= max(0.35, min(dimensions[0], dimensions[1]) * 0.15):
        role = "floor" if signed_z >= 0.0 else "ceiling"
        confidence = min(0.94, 0.70 + horizontal * 0.24)
        reason = "area-weighted horizontal face orientation"
    elif horizontal <= 0.32 and dimensions[2] >= 0.35:
        role, confidence, reason = "wall", min(0.93, 0.72 + (1.0 - horizontal) * 0.21), "area-weighted vertical face orientation"
    elif any(token in evidence for token in ("wall", "panel", "bulk", "hll", "gwall", "pwall", "nwall")):
        role, confidence, reason = "wall", 0.82, "wall material/name token"
    return {
        "role": role,
        "confidence": round(float(confidence), 4),
        "reason": reason,
        "bounds": tuple(round(float(value), 6) for value in bounds),
        "dimensions_m": tuple(round(float(value), 6) for value in dimensions),
        "area_m2": round(float(total_area), 6),
        "mean_signed_normal_z": round(float(signed_z), 6),
        "mean_absolute_normal_z": round(float(horizontal), 6),
        "requires_review": bool(confidence < 0.75 or role == "detail"),
    }


def serialize_architecture_model_text(
    model: Any,
    *,
    game: str,
    module_resref: str,
    room_resref: str,
    profile: str,
) -> tuple[str, dict[str, Any]]:
    """Serialize a stock Odyssey room as an OBJ-like labeled text sequence.

    This follows the useful part of LLaMA-Mesh's representation: ordinary
    vertex/UV/normal/face statements stay directly readable by a language
    model.  Ghost Studio adds source provenance and semantic labels needed for
    architecture extraction.  It does not fine-tune or ship game geometry;
    callers generate the text locally from their installed game.
    """

    from .authored_imported_mesh import build_imported_mesh_primitive_from_stock_model

    primitive = build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=room_resref,
        source_model=room_resref,
        game=game,
    )
    lines = [
        "# ghostrigger-kotor-architecture-sequence/v1",
        f"# game {str(game or '').strip().upper()}",
        f"# module {normalise_resref(module_resref)}",
        f"# room {normalise_resref(room_resref)}",
        f"# profile {str(profile or '').strip().lower()}",
        "# units metres",
    ]
    vertex_offset = 0
    role_counts: Counter[str] = Counter()
    texture_counts: Counter[str] = Counter()
    review_surfaces: list[str] = []
    triangle_count = 0
    for surface_index, surface in enumerate(primitive.surfaces):
        analysis = classify_architecture_surface(surface)
        role = str(analysis["role"])
        role_counts[role] += 1
        texture = str(getattr(surface, "texture", "") or "null").strip().lower()
        texture_counts[texture] += len(tuple(getattr(surface, "faces", ()) or ()))
        if analysis["requires_review"]:
            review_surfaces.append(str(getattr(surface, "name", "") or f"surface_{surface_index}"))
        lines.extend(
            (
                f"o {str(getattr(surface, 'name', '') or f'surface_{surface_index}')}",
                f"# semantic_role {role}",
                f"# semantic_confidence {analysis['confidence']:.4f}",
                f"# semantic_reason {analysis['reason']}",
                "# bounds " + " ".join(f"{float(value):.6f}" for value in analysis["bounds"]),
                f"usemtl {texture}",
            )
        )
        vertices = tuple(getattr(surface, "vertices", ()) or ())
        uvs = tuple(getattr(surface, "uvs", ()) or ())
        normals = tuple(getattr(surface, "normals", ()) or ())
        for vertex in vertices:
            lines.append("v " + " ".join(f"{float(value):.6f}" for value in tuple(vertex)[:3]))
        if len(uvs) == len(vertices):
            for uv in uvs:
                lines.append("vt " + " ".join(f"{float(value):.6f}" for value in tuple(uv)[:2]))
        if len(normals) == len(vertices):
            for normal in normals:
                lines.append("vn " + " ".join(f"{float(value):.6f}" for value in tuple(normal)[:3]))
        has_uvs = len(uvs) == len(vertices)
        has_normals = len(normals) == len(vertices)
        for raw_face in tuple(getattr(surface, "faces", ()) or ()):
            indices = tuple(int(value) + vertex_offset + 1 for value in tuple(raw_face)[:3])
            triangle_count += 1
            if has_uvs and has_normals:
                lines.append("f " + " ".join(f"{index}/{index}/{index}" for index in indices))
            elif has_uvs:
                lines.append("f " + " ".join(f"{index}/{index}" for index in indices))
            else:
                lines.append("f " + " ".join(str(index) for index in indices))
        vertex_offset += len(vertices)
    summary = {
        "schema": "ghostrigger.kotor-architecture-summary/v1",
        "profile": str(profile or "").strip().lower(),
        "game": str(game or "").strip().upper(),
        "module_resref": normalise_resref(module_resref),
        "room_resref": normalise_resref(room_resref),
        "surface_count": len(primitive.surfaces),
        "vertex_count": vertex_offset,
        "triangle_count": triangle_count,
        "role_counts": dict(sorted(role_counts.items())),
        "texture_triangle_counts": dict(texture_counts.most_common()),
        "review_surfaces": review_surfaces,
    }
    return "\n".join(lines) + "\n", summary


__all__ = [
    "PascalBuildingLevel",
    "PascalOpeningPreview",
    "PascalBuildingStyle",
    "architecture_training_room_specs",
    "architecture_training_game",
    "classify_architecture_surface",
    "add_pascal_building_room",
    "add_pascal_sealed_door",
    "available_pascal_building_styles",
    "pascal_architecture_door_spec",
    "pascal_architecture_profile_for_room",
    "pascal_architecture_runtime_resources",
    "pascal_architecture_sealed_door_spec",
    "pascal_building_levels",
    "preview_pascal_building_opening",
    "set_pascal_building_level",
    "set_pascal_building_opening",
    "scan_vanilla_pascal_building_styles",
    "serialize_architecture_model_text",
    "vanilla_pascal_building_styles",
    "vanilla_pascal_style_catalog_path",
    "write_vanilla_pascal_style_catalog",
]
