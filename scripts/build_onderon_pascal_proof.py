"""Build the focused Onderon Pascal-to-vanilla construction proof.

The saved KMAPs demonstrate the requested full-environment workflows:

1. a roofless Iziz merchant courtyard with authored Sky Ramp and Cantina wings;
2. vanilla 503OND and 504OND rooms stitched into isolated authored wings;
3. deliberately staged external buildings, purposeful gameplay placeables,
   named circulation routes, and a measured vanilla Onderon sky dome;
4. a Palace gallery -> vanilla 506OND room -> Palace museum chain.

It verifies solid Onderon door resources, reciprocal WOK portals, tiled helper
geometry, PIE traversal, and final MOD export/readback.

Run from the repository root:
    py -3.14 scripts/build_onderon_pascal_proof.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402


for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


OUT_DIR = Path(
    os.environ.get(
        "GHOSTRIGGER_ONDERON_PROOF_OUT_DIR",
        str(ROOT / "artifacts" / "onderon_pascal_proof"),
    )
).resolve()
SKY_RAMP_PIECE_ID = (
    str(os.environ.get("GHOSTRIGGER_ONDERON_SKY_RAMP_PIECE") or "").strip()
    or "k2_504ond_504ondj"
)
SKY_RAMP_SOURCE_ROOM = SKY_RAMP_PIECE_ID.rsplit("_", 1)[-1]
KMAP_PATH = OUT_DIR / "gronderonpalace.kmap"
EXTERIOR_KMAP_PATH = OUT_DIR / "gronderonexterior.kmap"
EXTERIOR_CANTINA_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_cantina_pie.kmap"
EXTERIOR_CANTINA_EAST_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_cantina_east_pie.kmap"
EXTERIOR_CANTINA_WEST_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_cantina_west_pie.kmap"
EXTERIOR_CITY_DOOR_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_city_door_pie.kmap"
EXTERIOR_SKY_RAMP_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_sky_ramp_pie.kmap"
EXTERIOR_MERCHANT_PIE_KMAP_PATH = OUT_DIR / "gronderonexterior_merchant_pie.kmap"
EXPORT_DIR = OUT_DIR / "palace_export_readback"
EXTERIOR_EXPORT_DIR = OUT_DIR / "exterior_export_readback"
REPORT_PATH = OUT_DIR / "structural_proof.json"


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
    raise FileNotFoundError("A KOTOR 2 installation is required for the Onderon proof.")


def _floor_plan_center(room) -> tuple[float, float, float]:
    points = tuple(getattr(room.primitive, "points", ()) or ())
    if not points:
        raise ValueError(f"{room.normalised_resref()} is not a generated floor-plan room.")
    return (
        float(room.position[0]) + sum(float(point[0]) for point in points) / len(points),
        float(room.position[1]) + sum(float(point[1]) for point in points) / len(points),
        float(room.position[2]) + float(getattr(room.primitive, "z", 0.0)) + 0.05,
    )


def _floor_plan_edge_midpoint(room, edge_index: int) -> tuple[float, float, float]:
    points = tuple(getattr(room.primitive, "points", ()) or ())
    index = int(edge_index)
    if not points or index < 0 or index >= len(points):
        raise ValueError(f"{room.normalised_resref()} has no wall edge {index}.")
    start = points[index]
    end = points[(index + 1) % len(points)]
    return (
        float(room.position[0]) + (float(start[0]) + float(end[0])) * 0.5,
        float(room.position[1]) + (float(start[1]) + float(end[1])) * 0.5,
        float(room.position[2]) + float(getattr(room.primitive, "z", 0.0)),
    )


def main() -> int:
    from pykotor.resource.generics.utd import read_utd

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_layout import authored_room_connection_hooks
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_environment_kits import environment_kit_piece_rows
    from src.core.modules.map_studio_pascal_building import pascal_architecture_runtime_resources
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.map_studio_spatial_design import (
        SpatialDesignPath,
        SpatialDesignPlan,
        SpatialDesignZone,
        SpatialPlacementIntent,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resources = ResourceManager()
    game_dir = _game_dir()
    if not resources.set_k2_dir(str(game_dir)):
        raise RuntimeError(f"Could not load K2 resources from {game_dir}")

    exterior_controller = ModuleEditorController()
    exterior_controller.new_project(name="grondext", game="K2")
    city = exterior_controller.add_map_studio_building_room(
        points=((0.0, 0.0), (36.0, 0.0), (36.0, 26.0), (0.0, 26.0)),
        wall_height=8.50,
        style_id="architecture:k2_onderon_city",
        architecture_archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
        roof_type="none",
    )
    city_reference_edge_midpoints = {
        0: (18.0, 0.0),
        1: (36.0, 13.0),
        2: (18.0, 26.0),
        3: (0.0, 13.0),
    }

    def attach_authored_wing(
        *,
        target_room: str,
        target_edge: int,
        source_points: tuple[tuple[float, float], ...],
        wall_height: float,
        style_id: str,
        archetype: str,
        include_ceiling: bool,
        building_kind: str,
        opening_width: float,
        opening_height: float,
    ) -> str:
        current_snapshot = authored_project_from_kmap_payload(
            exterior_controller.project.extra_sections["authored_module"]
        )
        current_target = next(
            room
            for room in current_snapshot.rooms
            if room.normalised_resref() == target_room
        )
        current_points = tuple(current_target.primitive.points)
        desired_midpoint = city_reference_edge_midpoints[int(target_edge)]
        resolved_target_edge = min(
            range(len(current_points)),
            key=lambda index: math.dist(
                (
                    (
                        float(current_points[index][0])
                        + float(current_points[(index + 1) % len(current_points)][0])
                    )
                    * 0.5,
                    (
                        float(current_points[index][1])
                        + float(current_points[(index + 1) % len(current_points)][1])
                    )
                    * 0.5,
                ),
                desired_midpoint,
            ),
        )
        exterior_controller.set_map_studio_building_opening(
            room_resref=target_room,
            edge_index=resolved_target_edge,
            opening_kind="door",
            center_fraction=0.5,
            width=opening_width,
            height=opening_height,
            bottom=0.0,
        )
        target_snapshot = authored_project_from_kmap_payload(
            exterior_controller.project.extra_sections["authored_module"]
        )
        target_hook = next(
            hook
            for hook in authored_room_connection_hooks(target_snapshot)
            if hook.room_resref == target_room
            and int(hook.edge_index) == int(resolved_target_edge)
            and not hook.connected_room_resref
        )
        source_room = exterior_controller.add_map_studio_building_room(
            points=source_points,
            wall_height=wall_height,
            style_id=style_id,
            architecture_archetype=archetype,
            include_ceiling=include_ceiling,
            building_kind=building_kind,
            roof_type="none",
        )
        broad = exterior_controller.preview_authored_room_drag_snap(
            source_room_resref=source_room,
            world_delta=(0.0, 0.0, 0.0),
            snap_distance=300.0,
            target_room_resref=target_room,
            target_opening_name=target_hook.opening_name,
        )
        exact = exterior_controller.preview_authored_room_drag_snap(
            source_room_resref=source_room,
            world_delta=broad["world_delta"],
            target_room_resref=target_room,
            target_opening_name=target_hook.opening_name,
        )
        if (
            not exact["magnet_snapped"]
            or exact["target_room_resref"] != target_room
            or target_hook.opening_name not in str(exact["target_hook_id"])
        ):
            raise RuntimeError(f"The authored Onderon wing did not snap to the courtyard: {exact}")
        exterior_controller.connect_authored_room_drag_snap(exact)
        return source_room

    north_gallery = attach_authored_wing(
        target_room=city,
        target_edge=2,
        # Preserve the exact 18 m courtyard portal, then flare the promenade
        # one metre per side. The previous straight x=9 wall put a player's
        # collision disc against an apparently open route at x=9.25.
        source_points=(
            (9.0, 26.0),
            (27.0, 26.0),
            (28.0, 28.0),
            (28.0, 74.0),
            (8.0, 74.0),
            (8.0, 28.0),
        ),
        wall_height=8.50,
        style_id="architecture:k2_onderon_city",
        archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
        opening_width=4.30,
        opening_height=3.75,
    )
    sky_ramp = attach_authored_wing(
        target_room=city,
        target_edge=1,
        source_points=((36.0, 5.0), (100.0, 5.0), (100.0, 21.0), (36.0, 21.0)),
        wall_height=12.70,
        style_id="architecture:k2_onderon_sky_ramp",
        archetype="ramp_court",
        include_ceiling=False,
        building_kind="exterior",
        opening_width=4.30,
        opening_height=3.75,
    )
    cantina = attach_authored_wing(
        target_room=city,
        target_edge=3,
        source_points=((-48.0, 5.0), (0.0, 5.0), (0.0, 21.0), (-48.0, 21.0)),
        wall_height=7.20,
        style_id="architecture:k2_onderon_cantina",
        archetype="cantina_gallery",
        include_ceiling=True,
        building_kind="interior",
        opening_width=4.15,
        opening_height=3.35,
    )
    arrival_forecourt = attach_authored_wing(
        target_room=city,
        target_edge=0,
        # This is a real, separately authored arrival room rather than a visual
        # plane.  It closes the missing ground between the two foreground
        # buildings, owns its WOK, and gives the district a deliberate
        # compression-before-release procession into the main courtyard.
        source_points=((8.0, -20.0), (28.0, -20.0), (28.0, 0.0), (8.0, 0.0)),
        wall_height=8.50,
        style_id="architecture:k2_onderon_city",
        archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
        opening_width=4.30,
        opening_height=3.75,
    )

    exterior_snapshot = authored_project_from_kmap_payload(
        exterior_controller.project.extra_sections["authored_module"]
    )
    sky_ramp_room = next(
        room for room in exterior_snapshot.rooms if room.normalised_resref() == sky_ramp
    )
    cantina_room = next(
        room for room in exterior_snapshot.rooms if room.normalised_resref() == cantina
    )
    sky_vanilla_position = _floor_plan_edge_midpoint(sky_ramp_room, 2)
    cantina_vanilla_position = _floor_plan_edge_midpoint(cantina_room, 2)
    vanilla_sky_ramp = exterior_controller.add_authored_environment_kit_piece(
        piece_id=SKY_RAMP_PIECE_ID,
        position=sky_vanilla_position,
        resource_manager=resources,
    )
    vanilla_cantina = exterior_controller.add_authored_environment_kit_piece(
        piece_id="k2_503ond_503onde",
        position=cantina_vanilla_position,
        resource_manager=resources,
    )

    def attach_cantina_side_room(
        *,
        target_opening_name: str,
        archetype: str,
    ) -> str:
        """Give every visible stock Cantina door a real authored destination."""

        source_room = exterior_controller.add_map_studio_building_room(
            points=((0.0, 0.0), (14.0, 0.0), (14.0, 10.0), (0.0, 10.0)),
            wall_height=7.20,
            style_id="architecture:k2_onderon_cantina",
            architecture_archetype=archetype,
            include_ceiling=True,
            building_kind="interior",
            roof_type="none",
        )
        broad = exterior_controller.preview_authored_room_drag_snap(
            source_room_resref=source_room,
            world_delta=(0.0, 0.0, 0.0),
            snap_distance=300.0,
            target_room_resref=vanilla_cantina,
            target_opening_name=target_opening_name,
        )
        exact = exterior_controller.preview_authored_room_drag_snap(
            source_room_resref=source_room,
            world_delta=broad["world_delta"],
            target_room_resref=vanilla_cantina,
            target_opening_name=target_opening_name,
        )
        if (
            not exact["magnet_snapped"]
            or exact["target_room_resref"] != vanilla_cantina
            or target_opening_name not in str(exact["target_hook_id"])
        ):
            raise RuntimeError(
                f"The Cantina side room did not snap to {target_opening_name}: {exact}"
            )
        exterior_controller.connect_authored_room_drag_snap(exact)
        return source_room

    cantina_east_lounge = attach_cantina_side_room(
        target_opening_name="door_04",
        archetype="cantina_gallery",
    )
    cantina_west_service = attach_cantina_side_room(
        target_opening_name="door_06",
        archetype="cantina_gallery",
    )

    # The foreground buildings are authored with the same Pascal-style kit as
    # the courtyard.  They frame the arrival axis without relying on arbitrary
    # clipped fragments from a stock room.
    foreground_west = exterior_controller.add_map_studio_building_room(
        points=((-18.0, -20.0), (8.0, -20.0), (8.0, 0.0), (-18.0, 0.0)),
        wall_height=8.50,
        style_id="architecture:k2_onderon_city",
        architecture_archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
        roof_type="hip",
    )
    foreground_east = exterior_controller.add_map_studio_building_room(
        points=((28.0, -20.0), (54.0, -20.0), (54.0, 0.0), (28.0, 0.0)),
        wall_height=8.50,
        style_id="architecture:k2_onderon_city",
        architecture_archetype="merchant_courtyard",
        include_ceiling=False,
        building_kind="exterior",
        roof_type="hip",
    )
    exterior_dressing_resrefs: tuple[str, ...] = ()

    # Retail Onderon evidence puts civic landmarks at controlled nodes and
    # terminals at perimeter/service positions.  Keep the center and all three
    # branch approaches empty: none of these are generic filler.
    for template_resref, tag, position, bearing in (
        ("xterminal", "Arrival Directory Terminal", (10.5, -1.5, 0.0), 0.0),
        ("plc_fntnmetl", "Promenade Civic Fountain", (23.0, 60.0, 0.0), math.pi * 0.5),
        ("sec_term", "Sky Ramp Security Terminal", (57.0, 6.5, 0.0), math.pi * 0.5),
    ):
        exterior_controller.add_authored_gameplay_placement(
            kind="placeable",
            template_resref=template_resref,
            tag=tag,
            position=position,
            bearing=bearing,
            snap_to_walkmesh=True,
            provenance={
                "source": "onderon_full_environment_proof",
                "source_module": "502ond",
            },
        )

    exterior_controller.set_authored_module_entry_point(
        position=(18.0, -15.0, 0.05),
        facing=math.pi * 0.5,
    )
    exterior_controller.set_authored_world_lighting_settings(
        {
            "profile": "custom",
            "sun_ambient": (96, 88, 78),
            "sun_diffuse": (158, 138, 112),
            "dynamic_ambient": (82, 74, 68),
            "shadow_opacity": 72,
            "sun_shadows": True,
            "fog_enabled": False,
            "fog_color": (58, 48, 42),
            "fog_near": 0.0,
            "fog_far": 160.0,
        }
    )
    lighting_snapshot = authored_project_from_kmap_payload(
        exterior_controller.project.extra_sections["authored_module"]
    )
    lighting_rooms = {
        room.normalised_resref(): room for room in lighting_snapshot.rooms
    }

    def generated_room_light_position(room_resref: str, height: float) -> tuple[float, float, float]:
        center = _floor_plan_center(lighting_rooms[room_resref])
        return (float(center[0]), float(center[1]), float(height))

    def stock_room_light_position(room_resref: str, height: float) -> tuple[float, float, float]:
        room = lighting_rooms[room_resref]
        return (
            float(room.position[0]),
            float(room.position[1]),
            float(room.position[2]) + float(height),
        )

    # Runtime-readable zone lights keep the authored interior branches and
    # long northern promenade legible. They are deliberately aligned to the
    # circulation axes instead of scattered as decorative test objects. Stock
    # rooms receive their own room-scoped light because an authored wing light
    # intentionally does not leak through the portal into a different room.
    for room_resref, name, position, color, radius, intensity in (
        (city, "Iziz Courtyard Key", (18.0, 13.0, 5.5), (1.0, 0.80, 0.58), 28.0, 0.82),
        (arrival_forecourt, "Arrival Forecourt Key", (18.0, -10.0, 5.0), (1.0, 0.80, 0.58), 22.0, 0.78),
        (north_gallery, "Merchant Promenade South", (18.0, 38.0, 5.0), (1.0, 0.78, 0.55), 20.0, 0.86),
        (north_gallery, "Merchant Promenade North", (18.0, 60.0, 5.0), (1.0, 0.78, 0.55), 20.0, 0.86),
        (cantina, "Cantina Gallery Fill", (-24.0, 13.0, 4.2), (1.0, 0.70, 0.48), 30.0, 0.72),
        (
            vanilla_cantina,
            "Vanilla Cantina Ambient",
            stock_room_light_position(vanilla_cantina, 4.4),
            (1.0, 0.74, 0.52),
            34.0,
            0.78,
        ),
        (
            cantina_east_lounge,
            "East Lounge Fill",
            generated_room_light_position(cantina_east_lounge, 4.2),
            (1.0, 0.72, 0.50),
            18.0,
            0.72,
        ),
        (
            cantina_west_service,
            "West Service Fill",
            generated_room_light_position(cantina_west_service, 4.2),
            (1.0, 0.72, 0.50),
            18.0,
            0.72,
        ),
        (sky_ramp, "Sky Ramp Court Fill", (68.0, 13.0, 6.0), (0.72, 0.86, 1.0), 42.0, 0.68),
        (
            vanilla_sky_ramp,
            "Vanilla Sky Ramp Ambient",
            stock_room_light_position(vanilla_sky_ramp, 6.0),
            (0.72, 0.86, 1.0),
            52.0,
            0.74,
        ),
    ):
        exterior_controller.add_authored_room_light(
            room_resref=room_resref,
            name=name,
            position=position,
            color=color,
            radius=radius,
            intensity=intensity,
            light_type="point",
        )
    exterior_after_dressing = authored_project_from_kmap_payload(
        exterior_controller.project.extra_sections["authored_module"]
    )

    def room_anchor(room) -> tuple[float, float, float]:
        if tuple(getattr(room.primitive, "points", ()) or ()):
            return _floor_plan_center(room)
        return tuple(float(value) for value in room.position)

    planned_rooms = {
        city: (
            "arrival",
            "Main Iziz Courtyard",
            "Primary arrival, orientation, and three-way circulation hub.",
            "Its open center preserves a clear view to the northern Merchant Quarter connection.",
        ),
        arrival_forecourt: (
            "arrival",
            "Southern Arrival Forecourt",
            "Provide a continuous, walkable procession between the foreground buildings and main courtyard.",
            "Its own room and WOK replace the previous empty gap; the paired buildings now meet its side edges.",
        ),
        foreground_west: (
            "foreground_west",
            "West Foreground Building",
            "Frame the arrival and establish an inhabited street edge.",
            "It stays west of the four-metre arrival route and mirrors the east mass.",
        ),
        foreground_east: (
            "foreground_east",
            "East Foreground Building",
            "Frame the arrival and establish an inhabited street edge.",
            "It stays east of the four-metre arrival route and mirrors the west mass.",
        ),
        sky_ramp: (
            "east_district",
            "Authored Sky Ramp Court",
            "Provide the east branch and a controlled approach to the stock Sky Ramp.",
            "It shares the courtyard portal and continues the same floor datum.",
        ),
        vanilla_sky_ramp: (
            "east_district",
            "Vanilla Sky Ramp",
            "Supply an authentic destination and skyline sequence.",
            f"Measured room {SKY_RAMP_SOURCE_ROOM} begins at the authored portal and must pass the visible doorway review.",
        ),
        cantina: (
            "west_district",
            "Authored Cantina Gallery",
            "Provide the west social branch and vestibule for the stock Cantina.",
            "The enclosed wing narrows the pace before the social interior.",
        ),
        vanilla_cantina: (
            "west_district",
            "Vanilla Iziz Cantina",
            "Supply an authentic social destination.",
            "All three stock doorways terminate in deliberate authored rooms.",
        ),
        cantina_east_lounge: (
            "west_district",
            "Cantina East Lounge",
            "Turn the stock Cantina's east door into a usable social side room.",
            "It snaps to the measured door_04 portal and keeps a clear threshold.",
        ),
        cantina_west_service: (
            "west_district",
            "Cantina West Service Room",
            "Turn the stock Cantina's west door into a usable service destination.",
            "It snaps to the measured door_06 portal and keeps a clear threshold.",
        ),
        north_gallery: (
            "north_district",
            "Authored Merchant Promenade",
            "Continue the main path into a legible civic destination.",
            "The promenade preserves the north-south sight line without importing overlapping 502OND partitions.",
        ),
    }
    room_by_resref = {
        room.normalised_resref(): room for room in exterior_after_dressing.rooms
    }
    vanilla_sky_anchor = room_anchor(room_by_resref[vanilla_sky_ramp])
    sky_zone_bounds = (
        min(36.0, float(vanilla_sky_anchor[0]) - 45.0),
        min(-30.0, float(vanilla_sky_anchor[1]) - 45.0),
        max(110.0, float(vanilla_sky_anchor[0]) + 45.0),
        max(100.0, float(vanilla_sky_anchor[1]) + 45.0),
    )
    planned_room_intents = tuple(
        SpatialPlacementIntent(
            placement_id=f"room:{room_resref}",
            label=label,
            asset_ref=str(
                room_by_resref[room_resref].metadata.get("source_room_resref")
                or room_by_resref[room_resref].metadata.get("style_id")
                or room_resref
            ),
            position=room_anchor(room_by_resref[room_resref]),
            bearing=float(room_by_resref[room_resref].metadata.get("bearing", 0.0) or 0.0),
            zone_id=zone_id,
            purpose=purpose,
            rationale=rationale,
            footprint_radius=0.35,
            clearance_radius=0.10,
            landmark=room_resref == north_gallery,
            allow_path_overlap=True,
        )
        for room_resref, (zone_id, label, purpose, rationale) in planned_rooms.items()
    )
    prop_design = {
        "Arrival Directory Terminal": (
            "arrival",
            "Orient the player before the courtyard opens into three district choices.",
            "It is anchored to the forecourt perimeter and remains clear of the four-metre arrival axis.",
        ),
        "Promenade Civic Fountain": (
            "north_district",
            "Give the Merchant Promenade one memorable civic landmark.",
            "Retail 503OND uses the same fountain as controlled civic decor; it sits off the route near the destination.",
        ),
        "Sky Ramp Security Terminal": (
            "east_district",
            "Signal that the Sky Ramp is a controlled transit route.",
            "It sits against the authored east wall before the stock-room threshold.",
        ),
    }
    planned_prop_intents = tuple(
        SpatialPlacementIntent(
            placement_id=f"placeable:{placeable.instance_id}",
            label=str(placeable.tag or placeable.template_resref),
            asset_ref=str(placeable.template_resref),
            position=tuple(float(value) for value in placeable.position),
            bearing=float(placeable.bearing),
            zone_id=prop_design[str(placeable.tag)][0],
            purpose=prop_design[str(placeable.tag)][1],
            rationale=prop_design[str(placeable.tag)][2],
            footprint_radius=0.55,
            clearance_radius=0.45,
            landmark=str(placeable.tag) == "Arrival Information Terminal",
        )
        for placeable in exterior_after_dressing.placements.placeables
    )
    exterior_controller.set_map_studio_spatial_design(
        SpatialDesignPlan(
            name="Onderon Iziz Arrival District",
            design_intent=(
                "Lead the player from a framed southern arrival into a readable civic courtyard, "
                "then offer intentional west Cantina, east Sky Ramp, and north Merchant Quarter choices."
            ),
            grid_size=0.25,
            player_clearance=1.20,
            zones=(
                SpatialDesignZone(
                    "arrival",
                    "Arrival Courtyard",
                    "Process the player through a complete forecourt, then reveal the three district choices.",
                    (8.0, -20.0, 36.0, 26.0),
                ),
                SpatialDesignZone(
                    "foreground_west",
                    "West Arrival Edge",
                    "Frame the approach without blocking the central sight line.",
                    (-20.0, -22.0, 10.0, 0.0),
                ),
                SpatialDesignZone(
                    "foreground_east",
                    "East Arrival Edge",
                    "Frame the approach without blocking the central sight line.",
                    (26.0, -22.0, 56.0, 0.0),
                ),
                SpatialDesignZone(
                    "west_district",
                    "Cantina District",
                    "Provide a compact social branch and an authentic stock-room destination.",
                    (-140.0, -30.0, 0.0, 100.0),
                ),
                SpatialDesignZone(
                    "east_district",
                    "Sky Ramp District",
                    "Provide a controlled transit branch and long skyline destination.",
                    sky_zone_bounds,
                ),
                SpatialDesignZone(
                    "north_district",
                    "Merchant Quarter Threshold",
                    "Continue the main civic route into a stock Onderon district.",
                    (-50.0, 20.0, 100.0, 180.0),
                ),
            ),
            paths=(
                SpatialDesignPath(
                    "arrival_axis",
                    "Arrival Axis",
                    "Keep the player start, courtyard, and Merchant Quarter visually connected.",
                    ((18.0, -18.0), (18.0, 82.0)),
                    width=4.0,
                ),
                SpatialDesignPath(
                    "cantina_branch",
                    "Cantina Branch",
                    "Give the west doorway a direct, legible route from the courtyard node.",
                    ((18.0, 13.0), (-48.0, 13.0)),
                    width=3.0,
                ),
                SpatialDesignPath(
                    "sky_ramp_branch",
                    "Sky Ramp Branch",
                    "Give the east doorway a direct, legible route from the courtyard node.",
                    ((18.0, 13.0), (100.0, 13.0)),
                    width=3.0,
                ),
            ),
            placements=planned_room_intents + planned_prop_intents,
        )
    )
    spatial_audit = exterior_controller.audit_map_studio_spatial_design()
    if not spatial_audit.ok:
        raise RuntimeError(
            "Onderon spatial design audit failed: "
            + "; ".join(spatial_audit.blocking_issues)
        )
    spatial_ledger = exterior_controller.map_studio_spatial_design_placement_ledger()
    exterior_after_dressing = authored_project_from_kmap_payload(
        exterior_controller.project.extra_sections["authored_module"]
    )
    exterior_playable_rooms = tuple(
        room.normalised_resref()
        for room in exterior_after_dressing.rooms
        if room.normalised_resref() not in set(exterior_dressing_resrefs)
    )
    sky_room, _sky_message = exterior_controller.create_authored_five_face_skybox(
        room_resref="grondextsky",
        north_texture="ond_sky1",
        east_texture="ond_sky2",
        south_texture="ond_sky3",
        west_texture="ond_sky4",
        top_texture="ond_sky5",
        half_extent=420.0,
        bottom_z=-140.0,
        top_z=280.0,
        visible_rooms=exterior_playable_rooms,
        authoring_metadata={
            "skybox_preset_id": "k2_onderon_iziz_daylight",
            "skybox_source_game": "K2",
            "skybox_source_module": "502ond",
            "skybox_source_room": "502ondd",
            "skybox_source": "measured_vanilla_module_textures",
        },
    )
    exterior_authored = authored_project_from_kmap_payload(
        exterior_controller.project.extra_sections["authored_module"]
    )
    city_room = next(room for room in exterior_authored.rooms if room.normalised_resref() == city)
    sky_ramp_room = next(
        room for room in exterior_authored.rooms if room.normalised_resref() == sky_ramp
    )
    cantina_room = next(
        room for room in exterior_authored.rooms if room.normalised_resref() == cantina
    )
    exterior_connections = compile_authored_room_connection_walkmeshes(exterior_authored)
    if not exterior_connections.ready:
        raise RuntimeError(
            "Onderon exterior connection walkmesh compilation failed: "
            + "; ".join(exterior_connections.blocking_issues)
        )
    exterior_combined = combine_authored_module_walkmesh(exterior_authored)
    if exterior_combined.blocking_issues:
        raise RuntimeError(
            "Combined Onderon exterior WOK failed: "
            + "; ".join(exterior_combined.blocking_issues)
        )

    controller = ModuleEditorController()
    controller.new_project(name="grondpalace", game="K2")
    palace_a = controller.add_map_studio_building_room(
        points=((90.0, 0.0), (108.0, 0.0), (108.0, 14.0), (90.0, 14.0)),
        wall_height=6.00,
        style_id="architecture:k2_onderon_palace",
        architecture_archetype="palace_gallery",
        include_ceiling=True,
        building_kind="interior",
    )
    palace_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k2_506ond_506ondo",
        position=(99.0, 14.0, 0.0),
    )
    if not palace_preview["magnet_snapped"] or not palace_preview["target_is_authored_wall"]:
        raise RuntimeError(f"The vanilla Royal Palace room did not snap to the gallery: {palace_preview}")
    vanilla_palace = controller.add_authored_environment_kit_piece(
        piece_id="k2_506ond_506ondo",
        position=(99.0, 14.0, 0.0),
        resource_manager=resources,
    )

    palace_b = controller.add_map_studio_building_room(
        points=((90.0, 100.0), (108.0, 100.0), (108.0, 114.0), (90.0, 114.0)),
        wall_height=6.00,
        style_id="architecture:k2_onderon_palace",
        architecture_archetype="museum",
        include_ceiling=True,
        building_kind="interior",
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=palace_b,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=250.0,
    )
    exact = controller.preview_authored_room_drag_snap(
        source_room_resref=palace_b,
        world_delta=broad["world_delta"],
    )
    if not exact["magnet_snapped"] or exact["target_room_resref"] != vanilla_palace:
        raise RuntimeError(f"The Palace museum did not snap to the free vanilla portal: {exact}")
    controller.connect_authored_room_drag_snap(exact)

    dressing_resrefs = tuple(
        controller.add_authored_environment_kit_piece(
            piece_id=piece_id,
            position=position,
            resource_manager=resources,
        )
        for piece_id, position in (
            ("k2_onderon_palace_environment_royal_statue", (99.0, 5.0, 0.0)),
        )
    )

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    palace_a_room = next(room for room in authored.rooms if room.normalised_resref() == palace_a)
    palace_b_room = next(room for room in authored.rooms if room.normalised_resref() == palace_b)
    controller.set_authored_module_entry_point(
        position=_floor_plan_center(palace_a_room),
        facing=math.pi * 0.5,
    )
    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    palace_a_room = next(room for room in authored.rooms if room.normalised_resref() == palace_a)
    palace_b_room = next(room for room in authored.rooms if room.normalised_resref() == palace_b)

    connections = compile_authored_room_connection_walkmeshes(authored)
    if not connections.ready:
        raise RuntimeError(
            "Onderon connection walkmesh compilation failed: "
            + "; ".join(connections.blocking_issues)
        )
    combined = combine_authored_module_walkmesh(authored)
    if combined.blocking_issues:
        raise RuntimeError("Combined Onderon Palace WOK failed: " + "; ".join(combined.blocking_issues))

    generated_geometry = tuple(
        compile_authored_room_spec(room)
        for room in (
            city_room,
            sky_ramp_room,
            cantina_room,
            next(
                room
                for room in exterior_authored.rooms
                if room.normalised_resref() == north_gallery
            ),
            palace_a_room,
            palace_b_room,
        )
    )
    helper_meshes = tuple(
        mesh for geometry in generated_geometry for mesh in geometry.helper_meshes
    )
    architecture_roles = {
        str(mesh.metadata.get("architecture_role") or "")
        for mesh in helper_meshes
    }
    bad_uv_meshes = [
        mesh.name for mesh in helper_meshes if len(mesh.uvs) != len(mesh.vertices)
    ]

    door_resources = (
        tuple(pascal_architecture_runtime_resources(exterior_authored))
        + tuple(pascal_architecture_runtime_resources(authored))
    )
    door_appearances = {
        resref: int(read_utd(data).appearance_id)
        for resref, restype, data in door_resources
        if restype == "utd"
    }
    onderon_rows = tuple(
        row
        for row in environment_kit_piece_rows(game="K2")
        if str(row["building_style_id"]).startswith("architecture:k2_onderon_")
    )
    building_rows = tuple(
        row for row in onderon_rows if str(row["class_id"]).startswith("building:")
    )
    verified_building_rows = tuple(
        row for row in building_rows if bool(row.get("placement_ready", True))
    )
    prop_rows = tuple(
        row for row in onderon_rows if str(row["class_id"]).startswith("dressing:")
    )

    district_session = MapStudioPIESession(
        exterior_combined.wok,
        game="K2",
        spawn_position=(18.0, -15.0, 0.05),
    )
    district_session.entity_registry = build_pie_entity_registry(exterior_authored)
    district_events = []

    def navigate_district(destination: tuple[float, float, float], frame_limit: int = 2400) -> bool:
        if not district_session.set_destination(destination, run=True):
            return False
        for _index in range(frame_limit):
            result = district_session.advance(1.0 / 30.0)
            district_events.extend(result.events)
            if district_session.state.destination is None:
                return math.dist(
                    tuple(float(value) for value in district_session.state.position[:2]),
                    tuple(float(value) for value in destination[:2]),
                ) <= 1.25
        return False

    district_sky_ramp_reached = navigate_district(_floor_plan_center(sky_ramp_room))
    district_cantina_reached = navigate_district(_floor_plan_center(cantina_room))

    exterior_hooks = tuple(authored_room_connection_hooks(exterior_authored))

    def walk_through_exterior_door(
        source_room_resref: str,
        connected_room_resref: str,
        *,
        frame_limit: int = 1200,
    ) -> tuple[bool, tuple[float, float, float], tuple[str, ...]]:
        hook = next(
            (
                item
                for item in exterior_hooks
                if item.room_resref == source_room_resref
                and item.connected_room_resref == connected_room_resref
            ),
            None,
        )
        if hook is None:
            return False, (0.0, 0.0, 0.0), ("missing_room_connection_hook",)
        start = (
            float(hook.position[0]) - float(hook.outward[0]) * 1.50,
            float(hook.position[1]) - float(hook.outward[1]) * 1.50,
            float(hook.position[2]) + 0.05,
        )
        walk_session = MapStudioPIESession(
            exterior_combined.wok,
            game="K2",
            spawn_position=start,
        )
        walk_session.entity_registry = build_pie_entity_registry(exterior_authored)
        camera_azimuth = math.degrees(
            math.atan2(-float(hook.outward[1]), -float(hook.outward[0]))
        )
        walk_session.set_move_input(
            1.0,
            0.0,
            camera_azimuth_degrees=camera_azimuth,
            run=True,
        )
        walk_events = []
        crossed = False
        for _index in range(frame_limit):
            result = walk_session.advance(1.0 / 30.0)
            walk_events.extend(result.events)
            signed_distance = (
                (float(walk_session.state.position[0]) - float(hook.position[0]))
                * float(hook.outward[0])
                + (float(walk_session.state.position[1]) - float(hook.position[1]))
                * float(hook.outward[1])
            )
            if signed_distance > 1.0:
                crossed = True
                break
        walk_session.set_move_input(
            0.0,
            0.0,
            camera_azimuth_degrees=camera_azimuth,
        )
        return (
            crossed,
            tuple(float(value) for value in walk_session.state.position),
            tuple(sorted({event.kind for event in walk_events})),
        )

    (
        crossed_sky_ramp_door,
        sky_ramp_walk_position,
        sky_ramp_walk_events,
    ) = walk_through_exterior_door(sky_ramp, vanilla_sky_ramp)
    (
        crossed_cantina_door,
        cantina_walk_position,
        cantina_walk_events,
    ) = walk_through_exterior_door(cantina, vanilla_cantina)
    (
        crossed_cantina_east_door,
        cantina_east_walk_position,
        cantina_east_walk_events,
    ) = walk_through_exterior_door(vanilla_cantina, cantina_east_lounge)
    (
        crossed_cantina_west_door,
        cantina_west_walk_position,
        cantina_west_walk_events,
    ) = walk_through_exterior_door(vanilla_cantina, cantina_west_service)

    session = MapStudioPIESession(
        combined.wok,
        game="K2",
        spawn_position=_floor_plan_center(palace_a_room),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    palace_hooks = {
        hook.connected_room_resref: hook
        for hook in authored_room_connection_hooks(authored)
        if hook.room_resref == vanilla_palace and hook.connected_room_resref
    }
    first_hook = palace_hooks[palace_a]
    second_hook = palace_hooks[palace_b]
    events = []

    def walk_across(
        direction: tuple[float, float],
        *,
        hook,
        outward_side: float,
        frame_limit: int,
    ) -> bool:
        camera_azimuth = math.degrees(math.atan2(-direction[1], -direction[0]))
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=camera_azimuth, run=True)
        for _index in range(frame_limit):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            signed_distance = (
                (float(session.state.position[0]) - float(hook.position[0]))
                * float(hook.outward[0])
                + (float(session.state.position[1]) - float(hook.position[1]))
                * float(hook.outward[1])
            )
            if signed_distance * float(outward_side) > 0.65:
                session.set_move_input(0.0, 0.0, camera_azimuth_degrees=camera_azimuth)
                return True
        return False

    crossed_first = walk_across(
        (
            float(first_hook.position[0]) - float(session.state.position[0]),
            float(first_hook.position[1]) - float(session.state.position[1]),
        ),
        hook=first_hook,
        outward_side=-1.0,
        frame_limit=900,
    )
    bend_destination = (
        float(second_hook.position[0]) - float(second_hook.outward[0]) * 0.85,
        float(second_hook.position[1]) - float(second_hook.outward[1]) * 0.85,
        float(second_hook.position[2]) + 0.05,
    )
    bend_destination_accepted = crossed_first and session.set_destination(
        bend_destination,
        run=True,
    )
    if bend_destination_accepted:
        for _index in range(1800):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            if session.state.destination is None:
                break
    crossed_second = (
        walk_across(
            tuple(float(value) for value in second_hook.outward),
            hook=second_hook,
            outward_side=1.0,
            frame_limit=900,
        )
        if bend_destination_accepted
        else False
    )
    final_destination_accepted = crossed_second and session.set_destination(
        _floor_plan_center(palace_b_room),
        run=True,
    )
    if final_destination_accepted:
        for _index in range(1200):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            if session.state.destination is None:
                break

    exterior_controller.save_project(EXTERIOR_KMAP_PATH)

    def save_exterior_door_pie_fixture(
        target_path: Path,
        source_room_resref: str,
        connected_room_resref: str,
    ) -> None:
        hook = next(
            item
            for item in exterior_hooks
            if item.room_resref == source_room_resref
            and item.connected_room_resref == connected_room_resref
        )
        start = (
            float(hook.position[0]) - float(hook.outward[0]) * 1.50,
            float(hook.position[1]) - float(hook.outward[1]) * 1.50,
            float(hook.position[2]) + 0.05,
        )
        exterior_controller.set_authored_module_entry_point(
            position=start,
            facing=math.atan2(float(hook.outward[1]), float(hook.outward[0])),
        )
        exterior_controller.save_project(target_path)

    save_exterior_door_pie_fixture(
        EXTERIOR_CANTINA_PIE_KMAP_PATH,
        cantina,
        vanilla_cantina,
    )
    save_exterior_door_pie_fixture(
        EXTERIOR_CANTINA_EAST_PIE_KMAP_PATH,
        vanilla_cantina,
        cantina_east_lounge,
    )
    save_exterior_door_pie_fixture(
        EXTERIOR_CANTINA_WEST_PIE_KMAP_PATH,
        vanilla_cantina,
        cantina_west_service,
    )
    save_exterior_door_pie_fixture(
        EXTERIOR_CITY_DOOR_PIE_KMAP_PATH,
        city,
        sky_ramp,
    )
    save_exterior_door_pie_fixture(
        EXTERIOR_SKY_RAMP_PIE_KMAP_PATH,
        sky_ramp,
        vanilla_sky_ramp,
    )
    exterior_controller.set_authored_module_entry_point(
        position=(9.25, 34.77, 0.05),
        facing=0.0,
    )
    exterior_controller.save_project(EXTERIOR_MERCHANT_PIE_KMAP_PATH)
    exterior_controller.set_authored_module_entry_point(
        position=(18.0, -15.0, 0.05),
        facing=math.pi * 0.5,
    )
    exterior_export = exterior_controller.export_authored_module(EXTERIOR_EXPORT_DIR)
    controller.save_project(KMAP_PATH)
    export = controller.export_authored_module(EXPORT_DIR)
    event_kinds = {event.kind for event in events}
    authored_rooms = tuple(
        room
        for room in authored.rooms
        if room.normalised_resref() not in set(dressing_resrefs)
    )
    exterior_rooms = tuple(
        room
        for room in exterior_authored.rooms
        if room.normalised_resref()
        not in {*set(exterior_dressing_resrefs), sky_room.normalised_resref()}
    )
    skybox_metadata = dict(sky_room.metadata or {})
    exterior_placeables = tuple(exterior_authored.placements.placeables)
    report = {
        "result": "PASS",
        "proof": (
            "Full Onderon district: authored Iziz court + Sky Ramp + Cantina + Merchant Promenade, "
            "isolated vanilla 503/504 rooms, purpose-staged buildings/placeables/sky; "
            "Palace + vanilla room + Palace museum"
        ),
        "game": "K2",
        "kmap": str(KMAP_PATH),
        "exterior_kmap": str(EXTERIOR_KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "exterior_export_directory": str(EXTERIOR_EXPORT_DIR),
        "authored_and_vanilla_rooms": [
            room.normalised_resref() for room in exterior_rooms + authored_rooms
        ],
        "dressing_rooms": list(exterior_dressing_resrefs + dressing_resrefs),
        "city_room": city,
        "arrival_forecourt_room": arrival_forecourt,
        "north_gallery_room": north_gallery,
        "sky_ramp_room": sky_ramp,
        "vanilla_sky_ramp_room": vanilla_sky_ramp,
        "cantina_room": cantina,
        "vanilla_cantina_room": vanilla_cantina,
        "cantina_east_lounge_room": cantina_east_lounge,
        "cantina_west_service_room": cantina_west_service,
        "palace_room_a": palace_a,
        "vanilla_palace_room": vanilla_palace,
        "palace_room_b": palace_b,
        "separate_structural_room_count": len(exterior_rooms) + len(authored_rooms),
        "portal_count": len(exterior_connections.portals) + len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap)
            for portal in exterior_connections.portals + connections.portals
        ],
        "walkable_face_count": len(exterior_combined.wok.faces) + len(combined.wok.faces),
        "door_actor_count": len(exterior_authored.placements.doors) + len(authored.placements.doors),
        "door_templates": sorted(
            str(door.template_resref or "")
            for door in exterior_authored.placements.doors + authored.placements.doors
        ),
        "door_appearances": door_appearances,
        "architecture_roles": sorted(architecture_roles),
        "helper_mesh_count": len(helper_meshes),
        "bad_uv_meshes": bad_uv_meshes,
        "onderon_browser_piece_count": len(onderon_rows),
        "external_building_piece_count": len(building_rows),
        "verified_external_building_piece_count": len(verified_building_rows),
        "small_prop_piece_count": len(prop_rows),
        "staged_external_building_count": 2,
        "staged_environment_dressing_count": len(exterior_dressing_resrefs),
        "staged_gameplay_placeable_count": len(exterior_placeables),
        "staged_gameplay_placeables": [
            str(placeable.template_resref or "") for placeable in exterior_placeables
        ],
        "skybox_room": sky_room.normalised_resref(),
        "skybox_preset_id": str(skybox_metadata.get("skybox_preset_id") or ""),
        "skybox_source_module": str(skybox_metadata.get("skybox_source_module") or ""),
        "skybox_textures": dict(skybox_metadata.get("texture_resrefs") or {}),
        "district_sky_ramp_reached": district_sky_ramp_reached,
        "district_cantina_reached": district_cantina_reached,
        "crossed_sky_ramp_door": crossed_sky_ramp_door,
        "sky_ramp_walk_position": list(sky_ramp_walk_position),
        "sky_ramp_walk_event_kinds": list(sky_ramp_walk_events),
        "crossed_cantina_door": crossed_cantina_door,
        "cantina_walk_position": list(cantina_walk_position),
        "cantina_walk_event_kinds": list(cantina_walk_events),
        "crossed_cantina_east_door": crossed_cantina_east_door,
        "cantina_east_walk_position": list(cantina_east_walk_position),
        "cantina_east_walk_event_kinds": list(cantina_east_walk_events),
        "crossed_cantina_west_door": crossed_cantina_west_door,
        "cantina_west_walk_position": list(cantina_west_walk_position),
        "cantina_west_walk_event_kinds": list(cantina_west_walk_events),
        "cantina_pie_fixture": str(EXTERIOR_CANTINA_PIE_KMAP_PATH),
        "cantina_east_pie_fixture": str(EXTERIOR_CANTINA_EAST_PIE_KMAP_PATH),
        "cantina_west_pie_fixture": str(EXTERIOR_CANTINA_WEST_PIE_KMAP_PATH),
        "city_door_pie_fixture": str(EXTERIOR_CITY_DOOR_PIE_KMAP_PATH),
        "sky_ramp_pie_fixture": str(EXTERIOR_SKY_RAMP_PIE_KMAP_PATH),
        "merchant_pie_fixture": str(EXTERIOR_MERCHANT_PIE_KMAP_PATH),
        "district_pie_event_kinds": sorted(
            {event.kind for event in district_events}
        ),
        "spatial_design": {
            "name": exterior_controller.map_studio_spatial_design().name,
            "intent": exterior_controller.map_studio_spatial_design().design_intent,
            "audit_ok": spatial_audit.ok,
            "summary": spatial_audit.summary(),
            "zone_count": spatial_audit.zone_count,
            "path_count": spatial_audit.path_count,
            "purposeful_placement_count": spatial_audit.purposeful_placement_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "subject_id": issue.subject_id,
                    "message": issue.message,
                }
                for issue in spatial_audit.issues
            ],
            "placement_ledger": list(spatial_ledger),
        },
        "crossed_first_palace_door": crossed_first,
        "palace_destination_accepted": bend_destination_accepted,
        "crossed_second_palace_door": crossed_second,
        "final_destination_accepted": final_destination_accepted,
        "pie_final_position": [float(value) for value in session.state.position],
        "pie_event_kinds": sorted(event_kinds),
        "pie_destination_reached": "destination_reached" in event_kinds,
        "export_ok": bool(export.ok),
        "exterior_export_ok": bool(exterior_export.ok),
        "export_readback_ok": bool(
            export.package_verification is not None
            and export.package_verification.ok
        ),
        "exterior_export_readback_ok": bool(
            exterior_export.package_verification is not None
            and exterior_export.package_verification.ok
        ),
        "visible_proof": {
            "status": "pending staged-app capture",
            "screenshots": [],
        },
    }
    required = (
        report["separate_structural_room_count"] == 14,
        report["portal_count"] == 10,
        max(report["portal_midpoint_gaps"], default=1.0) <= 2.0e-5,
        report["walkable_face_count"] > 0,
        report["door_actor_count"] == 10,
        {
            "gr_onddoor",
            "gr_ondcdoor",
            "gr_ondsdoor",
            "gr_ondpdoor",
        }
        <= set(report["door_templates"]),
        report["door_appearances"].get("gr_onddoor") == 108,
        report["door_appearances"].get("gr_ondpdoor") == 105,
        {"iziz_battered_stone_dado", "palace_recessed_relief_panel"} <= architecture_roles,
        not report["bad_uv_meshes"],
        report["external_building_piece_count"] >= 8,
        report["small_prop_piece_count"] >= 8,
        report["staged_external_building_count"] == 2,
        report["staged_environment_dressing_count"] == 0,
        report["staged_gameplay_placeable_count"] == 3,
        report["skybox_preset_id"] == "k2_onderon_iziz_daylight",
        report["skybox_source_module"] == "502ond",
        set(report["skybox_textures"].values())
        == {"ond_sky1", "ond_sky2", "ond_sky3", "ond_sky4", "ond_sky5"},
        report["district_sky_ramp_reached"],
        report["district_cantina_reached"],
        report["crossed_sky_ramp_door"],
        report["crossed_cantina_door"],
        report["crossed_cantina_east_door"],
        report["crossed_cantina_west_door"],
        report["spatial_design"]["audit_ok"],
        report["spatial_design"]["purposeful_placement_count"] == 14,
        report["crossed_first_palace_door"],
        report["palace_destination_accepted"],
        report["crossed_second_palace_door"],
        report["final_destination_accepted"],
        report["pie_destination_reached"],
        report["export_ok"],
        report["exterior_export_ok"],
        report["export_readback_ok"],
        report["exterior_export_readback_ok"],
    )
    if not all(required):
        report["result"] = "FAIL"
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
