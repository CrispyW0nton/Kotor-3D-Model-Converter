"""Build a deterministic Rhen Var landing-zone proof for Map Studio.

The proof is intentionally purpose-led rather than a random asset scatter:

* one exterior landing courtyard receives the retail K2 ``v_ehawk`` model,
* one enclosed temple vestibule and one temple hall remain separate rooms,
* two reciprocal Pascal doorway magnets produce two WOK portals,
* a four-metre circulation axis stays clear from the player start to the hall,
* authorized assets from the supplied Rhen Var Citadel, Colony, and Temple
  mods provide the skyline, snow dressing, monuments, and focal prop, while
  the Pascal-authored rooms retain collision authority for portals/interiors,
* the measured 261TEL sky orientation and cold polar atmosphere provide the
  exterior reference.

The repository-packaged mod-derived subset is used under author permission
confirmed by the user on 2026-07-25. Credits and source hashes live beside the
pack under ``mod_sources/imported``. The Ebon Hawk is resolved at run time from
the user's installed KOTOR II resources.

Run from the repository root:
    py -3.14 scripts/build_rhen_var_landing_zone_proof.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402


for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


OUT_DIR = ROOT / "artifacts" / "rhen_var_landing_zone_proof"
KMAP_PATH = OUT_DIR / "grrhenlz.kmap"
EXPORT_DIR = OUT_DIR / "export_readback"
REPORT_PATH = OUT_DIR / "structural_proof.json"
ASSET_PACK_ROOT = ROOT / "assets" / "map_studio" / "terrain_kits" / "rhen_var"
ASSET_MANIFEST_PATH = ASSET_PACK_ROOT / "manifest.json"

RHEN_VAR_STYLE_ID = "architecture:k2_rhen_var"
LANDING_ROUTE_WIDTH = 4.0
PLAYER_CLEARANCE = 1.2
PLAYER_START = (24.0, 34.0, 0.05)
PLAYER_FACING = math.pi * 0.5
ROUTE_POINTS = ((24.0, 34.0), (24.0, 96.0))
HALL_DESTINATION = (24.0, 96.0, 0.05)


@dataclass(frozen=True)
class RoomPlan:
    """One deterministic playable room in the landing-zone proof."""

    role: str
    points: tuple[tuple[float, float], ...]
    wall_height: float
    archetype: str
    include_ceiling: bool
    building_kind: str
    roof_type: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "points": [[float(value) for value in point] for point in self.points],
            "wall_height": float(self.wall_height),
            "style_id": RHEN_VAR_STYLE_ID,
            "archetype": self.archetype,
            "include_ceiling": bool(self.include_ceiling),
            "building_kind": self.building_kind,
            "roof_type": self.roof_type,
        }


@dataclass(frozen=True)
class PlacementPlan:
    """One explained visual placement used to dress the proof."""

    placement_id: str
    label: str
    asset_ref: str
    position: tuple[float, float, float]
    rotation_degrees_z: float
    scale: float
    zone_id: str
    purpose: str
    rationale: str
    footprint_radius: float
    clearance_radius: float
    landmark: bool = False
    allow_path_overlap: bool = False
    target_room_role: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "placement_id": self.placement_id,
            "label": self.label,
            "asset_ref": self.asset_ref,
            "position": [float(value) for value in self.position],
            "rotation_degrees_z": float(self.rotation_degrees_z),
            "scale": float(self.scale),
            "zone_id": self.zone_id,
            "purpose": self.purpose,
            "rationale": self.rationale,
            "footprint_radius": float(self.footprint_radius),
            "clearance_radius": float(self.clearance_radius),
            "landmark": bool(self.landmark),
            "allow_path_overlap": bool(self.allow_path_overlap),
            "target_room_role": self.target_room_role,
        }


@dataclass(frozen=True)
class LandingZoneLayout:
    """Serializable deterministic intent for the Rhen Var proof."""

    rooms: tuple[RoomPlan, ...]
    connections: tuple[tuple[str, str], ...]
    placements: tuple[PlacementPlan, ...]
    route_points: tuple[tuple[float, float], ...] = ROUTE_POINTS
    route_width: float = LANDING_ROUTE_WIDTH
    player_start: tuple[float, float, float] = PLAYER_START
    destination: tuple[float, float, float] = HALL_DESTINATION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.rhen-var-landing-zone-proof/v1",
            "style_id": RHEN_VAR_STYLE_ID,
            "rooms": [room.to_dict() for room in self.rooms],
            "connections": [list(pair) for pair in self.connections],
            "placements": [placement.to_dict() for placement in self.placements],
            "route": {
                "points": [[float(value) for value in point] for point in self.route_points],
                "width": float(self.route_width),
            },
            "player_start": [float(value) for value in self.player_start],
            "destination": [float(value) for value in self.destination],
        }


def landing_zone_layout() -> LandingZoneLayout:
    """Return the canonical, deterministic first Rhen Var environment."""

    return LandingZoneLayout(
        rooms=(
            RoomPlan(
                role="landing",
                points=((0.0, 0.0), (48.0, 0.0), (48.0, 64.0), (0.0, 64.0)),
                wall_height=8.0,
                archetype="landing_courtyard",
                include_ceiling=False,
                building_kind="exterior",
            ),
            RoomPlan(
                role="vestibule",
                points=((16.0, 64.0), (32.0, 64.0), (32.0, 80.0), (16.0, 80.0)),
                wall_height=8.0,
                archetype="temple_interior",
                include_ceiling=True,
                building_kind="interior",
            ),
            RoomPlan(
                role="hall",
                points=((12.0, 80.0), (36.0, 80.0), (36.0, 104.0), (12.0, 104.0)),
                wall_height=8.0,
                archetype="temple_interior",
                include_ceiling=True,
                building_kind="interior",
            ),
        ),
        connections=(("landing", "vestibule"), ("vestibule", "hall")),
        placements=(
            PlacementPlan(
                "retail_ebon_hawk",
                "Ebon Hawk",
                "retail:K2:v_ehawk",
                (24.0, 14.0, 0.0),
                90.0,
                0.58,
                "landing",
                "Arrival landmark and narrative origin.",
                "The ship anchors the south end of the approach while leaving its north ramp side and the temple sightline clear.",
                16.2,
                0.8,
                landmark=True,
                target_room_role="landing",
            ),
            PlacementPlan(
                "west_fortress",
                "Rhen Var Colony Fortress",
                "rv_mod_col_fortified_tower",
                (-39.0, 23.0, 0.0),
                270.0,
                1.0,
                "west_perimeter",
                "Establish the landing zone beside a real fortified settlement.",
                "The authorized full-scale Colony building faces east toward the pad but remains wholly beyond the playable landing WOK.",
                33.1,
                0.6,
                landmark=True,
            ),
            PlacementPlan(
                "east_lighthouse",
                "Rhen Var Colony Lighthouse",
                "rv_mod_col_lighthouse",
                (100.0, 60.0, 0.0),
                90.0,
                1.0,
                "east_perimeter",
                "Give the polar settlement a distant navigation landmark.",
                "The authorized full-scale lighthouse faces west across the landing court and never intrudes on the authored play space.",
                45.4,
                0.6,
                landmark=True,
            ),
            PlacementPlan(
                "left_snowbank",
                "West Landing Snowbank",
                "rv_mod_cit_snowdrift",
                (6.0, 51.0, -0.03),
                18.0,
                1.0,
                "landing",
                "Blend the authored pad into the snowy perimeter.",
                "The drift softens the west floor seam while remaining nineteen metres from the central route.",
                3.2,
                0.4,
                target_room_role="landing",
            ),
            PlacementPlan(
                "right_snowbank",
                "East Landing Snowbank",
                "rv_mod_cit_snowdrift",
                (42.0, 49.0, -0.03),
                198.0,
                1.0,
                "landing",
                "Blend the authored pad into the snowy perimeter.",
                "A mirrored but non-identical bearing frames the approach without forming a repetitive prop row.",
                3.2,
                0.4,
                target_room_role="landing",
            ),
            PlacementPlan(
                "west_threshold_statue",
                "West Rhen Var Temple Statue",
                "rv_mod_cit_statue",
                (18.0, 58.0, 0.0),
                195.0,
                0.45,
                "temple_threshold",
                "Signal the ruined ceremonial approach.",
                "The authorized monument toes inward toward the functional portal while remaining outside the four-metre route.",
                1.3,
                0.3,
                target_room_role="landing",
            ),
            PlacementPlan(
                "east_threshold_statue",
                "East Rhen Var Temple Statue",
                "rv_mod_cit_statue",
                (30.0, 58.0, 0.0),
                165.0,
                0.45,
                "temple_threshold",
                "Signal the ruined ceremonial approach.",
                "The paired authorized monument completes the doorway hierarchy without occupying the doorway or walkmesh.",
                1.3,
                0.3,
                target_room_role="landing",
            ),
            PlacementPlan(
                "hall_tomb_plinth",
                "Rhen Var Tomb Plinth",
                "rv_mod_cit_coffin",
                (24.0, 101.5, 0.02),
                0.0,
                0.52,
                "temple_interior",
                "Terminate the first-area route with a deliberate tomb focal point.",
                "The authorized Citadel plinth begins beyond the verified destination and reads as the narrative objective rather than corridor clutter.",
                2.5,
                0.3,
                landmark=True,
                target_room_role="hall",
            ),
        ),
    )


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-12:
        return math.dist(point, start)
    amount = max(
        0.0,
        min(
            1.0,
            (
                (float(point[0]) - float(start[0])) * dx
                + (float(point[1]) - float(start[1])) * dy
            )
            / length_sq,
        ),
    )
    closest = (float(start[0]) + dx * amount, float(start[1]) + dy * amount)
    return math.dist(point, closest)


def path_clearance_issues(layout: LandingZoneLayout | None = None) -> tuple[str, ...]:
    """Return explained placement IDs that obstruct the four-metre route."""

    plan = layout or landing_zone_layout()
    issues: list[str] = []
    segments = tuple(zip(plan.route_points, plan.route_points[1:]))
    for placement in plan.placements:
        if placement.allow_path_overlap:
            continue
        required = (
            float(plan.route_width) * 0.5
            + float(placement.footprint_radius)
            + float(placement.clearance_radius)
        )
        point = (float(placement.position[0]), float(placement.position[1]))
        distance = min(
            (_point_segment_distance(point, start, end) for start, end in segments),
            default=float("inf"),
        )
        if distance < required:
            issues.append(
                f"{placement.placement_id} leaves {distance:.3f} m; {required:.3f} m is required."
            )
    return tuple(issues)


def _connect_new_room(
    controller: Any,
    *,
    source_room_resref: str,
    target_room_resref: str,
) -> dict[str, object]:
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=source_room_resref,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=300.0,
        target_room_resref=target_room_resref,
    )
    if not bool(broad.get("magnet_snapped", False)):
        raise RuntimeError(
            f"{source_room_resref} did not find {target_room_resref}'s doorway: {broad}"
        )
    exact = controller.preview_authored_room_drag_snap(
        source_room_resref=source_room_resref,
        world_delta=broad["world_delta"],
        target_room_resref=target_room_resref,
    )
    if not bool(exact.get("magnet_snapped", False)):
        raise RuntimeError(
            f"{source_room_resref} did not commit an exact doorway magnet: {exact}"
        )
    controller.connect_authored_room_drag_snap(exact)
    return exact


def build_structural_rooms(
    controller: Any,
    layout: LandingZoneLayout | None = None,
) -> dict[str, str]:
    """Build the three separate rooms and their two reciprocal connections."""

    plan = layout or landing_zone_layout()
    room_by_role = {room.role: room for room in plan.rooms}
    result: dict[str, str] = {}

    landing = room_by_role["landing"]
    result["landing"] = controller.add_map_studio_building_room(
        points=landing.points,
        wall_height=landing.wall_height,
        style_id=RHEN_VAR_STYLE_ID,
        architecture_archetype=landing.archetype,
        include_ceiling=landing.include_ceiling,
        building_kind=landing.building_kind,
        roof_type=landing.roof_type,
    )
    controller.set_map_studio_building_opening(
        room_resref=result["landing"],
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=4.4,
        height=3.8,
        bottom=0.0,
    )

    vestibule = room_by_role["vestibule"]
    result["vestibule"] = controller.add_map_studio_building_room(
        points=vestibule.points,
        wall_height=vestibule.wall_height,
        style_id=RHEN_VAR_STYLE_ID,
        architecture_archetype=vestibule.archetype,
        include_ceiling=vestibule.include_ceiling,
        building_kind=vestibule.building_kind,
        roof_type=vestibule.roof_type,
    )
    first_preview = _connect_new_room(
        controller,
        source_room_resref=result["vestibule"],
        target_room_resref=result["landing"],
    )
    if not bool(first_preview.get("auto_cut_source", False)):
        raise RuntimeError("The landing-to-vestibule connection did not auto-cut the source wall.")
    controller.set_map_studio_building_opening(
        room_resref=result["vestibule"],
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=4.4,
        height=3.8,
        bottom=0.0,
    )

    hall = room_by_role["hall"]
    result["hall"] = controller.add_map_studio_building_room(
        points=hall.points,
        wall_height=hall.wall_height,
        style_id=RHEN_VAR_STYLE_ID,
        architecture_archetype=hall.archetype,
        include_ceiling=hall.include_ceiling,
        building_kind=hall.building_kind,
        roof_type=hall.roof_type,
    )
    second_preview = _connect_new_room(
        controller,
        source_room_resref=result["hall"],
        target_room_resref=result["vestibule"],
    )
    if not bool(second_preview.get("auto_cut_source", False)):
        raise RuntimeError("The vestibule-to-hall connection did not auto-cut the source wall.")
    return result


def _game_dir() -> Path:
    settings_path = ROOT / "settings.json"
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        configured = Path(str(settings.get("k2_dir") or ""))
        if (configured / "chitin.key").is_file():
            return configured
    configured = Path(os.environ.get("K2_PATH", ""))
    if (configured / "chitin.key").is_file():
        return configured
    fallback = Path(
        r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
    )
    if (fallback / "chitin.key").is_file():
        return fallback
    raise FileNotFoundError(
        "A KOTOR II installation is required to resolve retail v_ehawk and 261TEL textures."
    )


def _transform_retail_visual_primitive(
    primitive: Any,
    *,
    room_resref: str,
    rotation_degrees_z: float,
    scale: float,
) -> tuple[Any, dict[str, Any]]:
    """Centre, ground, rotate, and scale a retail visual without changing UVs."""

    from src.core.modules.module_format import WOKData

    surfaces = tuple(primitive.surfaces or ())
    vertices = tuple(vertex for surface in surfaces for vertex in surface.vertices)
    if not vertices:
        raise ValueError("Retail v_ehawk did not contain renderable surfaces.")
    minimum = tuple(min(float(vertex[index]) for vertex in vertices) for index in range(3))
    maximum = tuple(max(float(vertex[index]) for vertex in vertices) for index in range(3))
    center_x = (minimum[0] + maximum[0]) * 0.5
    center_y = (minimum[1] + maximum[1]) * 0.5
    angle = math.radians(float(rotation_degrees_z))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    factor = float(scale)

    def point(value: Any) -> tuple[float, float, float]:
        x = (float(value[0]) - center_x) * factor
        y = (float(value[1]) - center_y) * factor
        return (
            x * cosine - y * sine,
            x * sine + y * cosine,
            (float(value[2]) - minimum[2]) * factor,
        )

    def normal(value: Any) -> tuple[float, float, float]:
        x = float(value[0])
        y = float(value[1])
        z = float(value[2])
        rotated = (x * cosine - y * sine, x * sine + y * cosine, z)
        length = math.sqrt(sum(component * component for component in rotated))
        if length <= 1.0e-12:
            return (0.0, 0.0, 1.0)
        return tuple(component / length for component in rotated)

    transformed_surfaces = tuple(
        replace(
            surface,
            vertices=tuple(point(vertex) for vertex in surface.vertices),
            normals=tuple(normal(value) for value in surface.normals),
            mesh_average_point=point(surface.mesh_average_point),
        )
        for surface in surfaces
    )
    source_size = tuple(maximum[index] - minimum[index] for index in range(3))
    metadata = {
        **dict(primitive.metadata or {}),
        "source": "retail_game",
        "source_game": "K2",
        "source_model": "v_ehawk",
        "visual_only": True,
        "copied_third_party_asset_data": False,
        "proof_role": "arrival_landmark",
        "rotation_degrees_z": float(rotation_degrees_z),
        "scale": factor,
        "source_dimensions_m": [float(value) for value in source_size],
        "staged_dimensions_m": [float(value) * factor for value in source_size],
    }
    return (
        replace(
            primitive,
            room_resref=room_resref,
            surfaces=transformed_surfaces,
            source_model="v_ehawk",
            game="K2",
            wok=WOKData(name=room_resref),
            metadata=metadata,
        ),
        metadata,
    )


def _stage_retail_ebon_hawk(
    controller: Any,
    resources: Any,
    placement: PlacementPlan,
) -> tuple[str, dict[str, Any]]:
    from src.core.modules.authored_imported_mesh import (
        build_imported_mesh_primitive_from_stock_model,
    )
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
    )
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.map_studio_stock_content_preview import (
        load_stock_kotor_model,
    )

    model = load_stock_kotor_model(resources, "v_ehawk", "K2")
    if model is None:
        raise FileNotFoundError("The installed KOTOR II data did not resolve retail model v_ehawk.")
    room_resref = "grrvehawk"
    source = build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=room_resref,
        source_model="v_ehawk",
        game="K2",
    )
    primitive, provenance = _transform_retail_visual_primitive(
        source,
        room_resref=room_resref,
        rotation_degrees_z=placement.rotation_degrees_z,
        scale=placement.scale,
    )
    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    if any(room.normalised_resref() == room_resref for room in authored.rooms):
        raise ValueError(f"Visual room {room_resref} already exists.")
    all_rooms = tuple(room.normalised_resref() for room in authored.rooms) + (room_resref,)
    existing = tuple(
        replace(
            room,
            visible_rooms=tuple(
                dict.fromkeys(tuple(room.visible_rooms or ()) + (room_resref,))
            ),
        )
        for room in authored.rooms
    )
    visual_room = AuthoredRoomSpec(
        room_resref=room_resref,
        primitive=primitive,
        position=tuple(float(value) for value in placement.position),
        visible_rooms=all_rooms,
        metadata={
            "primitive": "imported_mesh",
            "source": "retail_game",
            "source_game": "K2",
            "source_model": "v_ehawk",
            "visual_only": True,
            "proof_placement_id": placement.placement_id,
            "purpose": placement.purpose,
            "rationale": placement.rationale,
            "copied_third_party_asset_data": False,
        },
    )
    controller._store_authored_project(  # noqa: SLF001 - proof orchestration boundary
        replace(authored, rooms=existing + (visual_room,))
    )
    return room_resref, provenance


def _spatial_plan(layout: LandingZoneLayout):
    from src.core.modules.map_studio_spatial_design import (
        SpatialDesignPath,
        SpatialDesignPlan,
        SpatialDesignZone,
        SpatialPlacementIntent,
    )

    return SpatialDesignPlan(
        name="Rhen Var Ebon Hawk Landing Zone",
        design_intent=(
            "Orient the player at the Ebon Hawk, preserve one four-metre temple approach, "
            "and use authorized Rhen Var settlement landmarks, snow, and monuments to "
            "frame—not obstruct—the route."
        ),
        grid_size=0.25,
        player_clearance=PLAYER_CLEARANCE,
        zones=(
            SpatialDesignZone(
                "landing",
                "Ebon Hawk Landing Court",
                "Provide arrival, orientation, and a clear first sightline to the temple.",
                (-5.0, -5.0, 53.0, 66.0),
            ),
            SpatialDesignZone(
                "temple_threshold",
                "Temple Threshold",
                "Concentrate ceremonial framing around the functional portal.",
                (10.0, 53.0, 38.0, 69.0),
            ),
            SpatialDesignZone(
                "temple_interior",
                "Temple Interior",
                "Transition from exposed snow into a warm, enclosed exploration space.",
                (8.0, 78.0, 40.0, 108.0),
            ),
            SpatialDesignZone(
                "west_perimeter",
                "Western Fortress Perimeter",
                "Place the full-scale Colony fortress beyond the playable WOK as a believable settlement edge.",
                (-80.0, -12.0, 10.0, 115.0),
            ),
            SpatialDesignZone(
                "east_perimeter",
                "Eastern Lighthouse Perimeter",
                "Use the full-scale Colony lighthouse as a distant navigation landmark beyond the playable WOK.",
                (40.0, -10.0, 150.0, 115.0),
            ),
        ),
        paths=(
            SpatialDesignPath(
                "landing_to_temple",
                "Landing-to-Temple Route",
                "Keep the arrival point, both doorway portals, and first hall destination continuously legible.",
                layout.route_points,
                width=layout.route_width,
                level_z=0.05,
            ),
        ),
        placements=tuple(
            SpatialPlacementIntent(
                placement_id=placement.placement_id,
                label=placement.label,
                asset_ref=placement.asset_ref,
                position=placement.position,
                bearing=math.radians(placement.rotation_degrees_z),
                zone_id=placement.zone_id,
                purpose=placement.purpose,
                rationale=placement.rationale,
                footprint_radius=placement.footprint_radius,
                clearance_radius=placement.clearance_radius,
                landmark=placement.landmark,
                allow_path_overlap=placement.allow_path_overlap,
            )
            for placement in layout.placements
        ),
    )


def _texture_resources() -> tuple[tuple[str, str, bytes], ...]:
    manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    resources: list[tuple[str, str, bytes]] = []
    for row in tuple(manifest.get("textures") or ()):
        filename = str(row.get("filename") or row.get("texture_file") or "").strip()
        if not filename:
            raise ValueError(f"Rhen Var texture row has no packaged file: {row!r}")
        path = ASSET_PACK_ROOT / filename
        resources.append(
            (
                str(row["texture_resref"]),
                "tga",
                path.read_bytes(),
            )
        )
    return tuple(resources)


def _floor_plan_center(room: Any) -> tuple[float, float, float]:
    points = tuple(getattr(room.primitive, "points", ()) or ())
    if not points:
        raise ValueError(f"{room.normalised_resref()} is not a generated room.")
    return (
        float(room.position[0]) + sum(float(point[0]) for point in points) / len(points),
        float(room.position[1]) + sum(float(point[1]) for point in points) / len(points),
        float(room.position[2]) + float(getattr(room.primitive, "z", 0.0)) + 0.05,
    )


def main() -> int:
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_export import (
        AuthoredModuleExportRequest,
        export_authored_module_project,
    )
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
    )
    from src.core.modules.authored_module_layout import (
        authored_room_connection_hooks,
    )
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    layout = landing_zone_layout()
    clearance_issues = path_clearance_issues(layout)
    if clearance_issues:
        raise RuntimeError("Landing route is obstructed: " + "; ".join(clearance_issues))

    game_dir = _game_dir()
    resources = ResourceManager()
    if not resources.set_k2_dir(str(game_dir)):
        raise RuntimeError(f"Could not load KOTOR II resources from {game_dir}")

    controller = ModuleEditorController()
    controller.new_project(name="grrhenlz", game="K2")
    room_resrefs = build_structural_rooms(controller, layout)
    controller.set_authored_module_entry_point(
        position=layout.player_start,
        facing=PLAYER_FACING,
    )

    dressing_rooms: dict[str, str] = {}
    for placement in layout.placements:
        dressing_rooms[placement.placement_id] = controller.add_authored_terrain_kit_asset(
            asset_id=placement.asset_ref,
            position=placement.position,
            rotation_degrees_z=placement.rotation_degrees_z,
            scale=placement.scale,
            target_room_resref=room_resrefs.get(placement.target_room_role, ""),
            resource_manager=resources,
        )
    ebon_room = dressing_rooms["retail_ebon_hawk"]
    ebon_provenance = {
        "source_game": "K2",
        "source_model": "v_ehawk",
        "source_reference": "retail:K2:v_ehawk",
        "retail_bytes_packaged": False,
        "placement_workflow": "Map Studio Terrain Kit / Vehicles & Landing Craft",
        "movable": True,
    }

    controller.set_authored_world_lighting_settings(
        {
            "profile": "standard",
            "sun_ambient": (0, 0, 0),
            "sun_diffuse": (0, 0, 0),
            "dynamic_ambient": (67, 81, 114),
            "shadow_opacity": 205,
            "sun_shadows": False,
            "fog_enabled": True,
            "fog_color": (91, 107, 128),
            "fog_near": 32.0,
            "fog_far": 220.0,
        }
    )
    for room_role, name, position, color, radius, intensity in (
        (
            "landing",
            "Polar Landing Fill",
            (24.0, 38.0, 9.0),
            (0.58, 0.72, 1.0),
            48.0,
            0.52,
        ),
        (
            "vestibule",
            "Temple Vestibule Firelight",
            (24.0, 72.0, 5.2),
            (1.0, 0.70, 0.44),
            12.0,
            0.82,
        ),
        (
            "hall",
            "Temple Hall Firelight",
            (24.0, 92.0, 5.4),
            (1.0, 0.66, 0.40),
            17.0,
            0.75,
        ),
    ):
        controller.add_authored_room_light(
            room_resref=room_resrefs[room_role],
            name=name,
            position=position,
            color=color,
            radius=radius,
            intensity=intensity,
        )

    spatial_audit = controller.set_map_studio_spatial_design(_spatial_plan(layout))
    if not spatial_audit.ok:
        raise RuntimeError(
            "Rhen Var spatial design failed: "
            + "; ".join(spatial_audit.blocking_issues)
        )

    sky_room, _message = controller.create_authored_five_face_skybox(
        room_resref="grrvsky",
        north_texture="gr_rvskyn",
        east_texture="gr_rvskye",
        south_texture="gr_rvskys",
        west_texture="gr_rvskyw",
        top_texture="gr_rvskyt",
        half_extent=520.0,
        bottom_z=-180.0,
        top_z=340.0,
        visible_rooms=tuple(room_resrefs.values()),
        authoring_metadata={
            "skybox_preset_id": "k2_rhen_var_polar_day",
            "skybox_source": "Poly Haven Lago d'Isola 4K HDRI",
            "skybox_source_author": "Andreas Mischok",
            "skybox_license": "CC0 1.0",
            "skybox_source_url": "https://polyhaven.com/a/lago_disola",
            "skybox_source_sha256": "49b02525462f1e518bc39907277300d38bc611bbbc4703979d7881a9193c882c",
            "skybox_projection": "KOTOR five-face cube, 1024px, ACES, -0.35 EV, +18 degree longitude",
            "lighting_reference": "K2 261TEL polar plateau",
        },
    )

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    connections = compile_authored_room_connection_walkmeshes(authored)
    combined = combine_authored_module_walkmesh(authored)
    if not connections.ready:
        raise RuntimeError(
            "Rhen Var portal compilation failed: "
            + "; ".join(connections.blocking_issues)
        )
    if combined.blocking_issues:
        raise RuntimeError(
            "Rhen Var combined WOK failed: " + "; ".join(combined.blocking_issues)
        )

    playable_rooms = tuple(
        next(
            room
            for room in authored.rooms
            if room.normalised_resref() == room_resrefs[role]
        )
        for role in ("landing", "vestibule", "hall")
    )
    playable_geometry = tuple(compile_authored_room_spec(room) for room in playable_rooms)
    connected_hooks = tuple(
        hook
        for hook in authored_room_connection_hooks(authored)
        if str(hook.connected_room_resref or "").strip()
    )

    session = MapStudioPIESession(
        combined.wok,
        game="K2",
        spawn_position=layout.player_start,
    )
    session.entity_registry = build_pie_entity_registry(authored)
    destination_accepted = session.set_destination(layout.destination, run=True)
    pie_events = []
    if destination_accepted:
        for _index in range(3600):
            result = session.advance(1.0 / 30.0)
            pie_events.extend(result.events)
            if session.state.destination is None:
                break
    pie_event_kinds = {event.kind for event in pie_events}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    controller.save_project(KMAP_PATH)
    export = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=authored,
            output_dir=str(EXPORT_DIR),
            game_root_dir=str(game_dir),
            include_reference_check=False,
            include_wok_check=True,
            include_game_template_check=False,
            strict=True,
            dry_run=False,
            create_backups=False,
            write_loose_resources=True,
            extra_resources=_texture_resources(),
        )
    )

    manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    authored_asset_rows = tuple(
        room
        for room in authored.rooms
        if str(room.metadata.get("source") or "") == "map_studio:terrain_kit"
    )
    report = {
        "result": "PASS",
        "proof": "Retail Ebon Hawk landing -> Pascal temple vestibule -> Pascal temple hall",
        "game": "K2",
        "layout": layout.to_dict(),
        "kmap": str(KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "playable_rooms": [room.normalised_resref() for room in playable_rooms],
        "playable_room_count": len(playable_rooms),
        "separate_room_wok_face_counts": [
            len(geometry.wok.faces) for geometry in playable_geometry
        ],
        "portal_count": len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap) for portal in connections.portals
        ],
        "reciprocal_connected_hook_count": len(connected_hooks),
        "door_actor_count": len(authored.placements.doors),
        "door_templates": sorted(
            str(door.template_resref or "") for door in authored.placements.doors
        ),
        "combined_walkable_face_count": len(combined.wok.faces),
        "path_width_m": layout.route_width,
        "path_clearance_issues": list(clearance_issues),
        "spatial_audit_ok": bool(spatial_audit.ok),
        "spatial_zone_count": int(spatial_audit.zone_count),
        "spatial_placement_count": int(spatial_audit.placement_count),
        "spatial_landmark_count": int(spatial_audit.landmark_count),
        "retail_ebon_hawk_room": ebon_room,
        "retail_ebon_hawk_provenance": ebon_provenance,
        "terrain_asset_pack_schema": manifest.get("schema"),
        "terrain_asset_pack_id": manifest.get("pack_id"),
        "terrain_asset_pack_provenance": manifest.get("provenance"),
        "terrain_visual_room_count": len(authored_asset_rows),
        "terrain_visual_rooms": {
            placement_id: room_resref
            for placement_id, room_resref in dressing_rooms.items()
        },
        "sky_room": sky_room.normalised_resref(),
        "sky_source": "Poly Haven Lago d'Isola 4K HDRI by Andreas Mischok (CC0 1.0)",
        "sky_textures": [
            "gr_rvskyn",
            "gr_rvskye",
            "gr_rvskys",
            "gr_rvskyw",
            "gr_rvskyt",
        ],
        "destination_accepted": bool(destination_accepted),
        "pie_destination_reached": "destination_reached" in pie_event_kinds,
        "pie_final_position": [float(value) for value in session.state.position],
        "pie_event_kinds": sorted(pie_event_kinds),
        "export_ok": bool(export.ok),
        "export_code": str(export.code or ""),
        "export_message": str(export.message or ""),
        "export_blocking_issues": list(export.blocking_issues or ()),
        "package_result_ok": bool(
            export.package_result is not None and export.package_result.ok
        ),
        "package_result_code": str(
            export.package_result.code if export.package_result is not None else ""
        ),
        "export_readback_ok": bool(
            export.package_verification is not None
            and export.package_verification.ok
        ),
        "export_readback_code": str(
            export.package_verification.code
            if export.package_verification is not None
            else ""
        ),
        "visible_proof": {
            "status": "pending staged-app capture",
            "screenshots": [],
        },
    }
    required = (
        report["playable_room_count"] == 3,
        all(count > 0 for count in report["separate_room_wok_face_counts"]),
        report["portal_count"] == 2,
        max(report["portal_midpoint_gaps"], default=1.0) <= 2.0e-5,
        report["reciprocal_connected_hook_count"] == 4,
        report["door_actor_count"] == 2,
        set(report["door_templates"]) == {"gr_rvdoor"},
        report["combined_walkable_face_count"] > 0,
        not report["path_clearance_issues"],
        report["spatial_audit_ok"],
        report["retail_ebon_hawk_provenance"]["source_model"] == "v_ehawk",
        report["terrain_asset_pack_schema"] == "ghostrigger.rhen-var-asset-pack/v1",
        report["destination_accepted"],
        report["pie_destination_reached"],
        report["export_ok"],
        report["export_readback_ok"],
    )
    if not all(required):
        report["result"] = "FAIL"
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
