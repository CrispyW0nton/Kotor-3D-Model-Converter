"""Build the focused K1 Korriban connection proof used by visible Map Studio QA.

The generated KMAP contains four separate rooms:

1. a Pascal-built Korriban tomb,
2. a deterministic concave Shyrack cave with formations, and
3. the measured vanilla ``m38aa_02`` tomb room, and
4. a second Pascal-built Shyrack cave parcel.

Every cave/tomb join uses an open cave-arch module transition with reciprocal
WOK portals; cave archways must not spawn KOTOR door actors.

Run from the repository root:
    py -3.14 scripts/build_shyrack_tomb_chain_proof.py
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402


for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


OUT_DIR = ROOT / "artifacts" / "korriban_proof" / "shyrack_tomb_chain"
KMAP_PATH = OUT_DIR / "grshyrchain.kmap"
EXPORT_DIR = OUT_DIR / "export_readback"
REPORT_PATH = OUT_DIR / "structural_proof.json"


def _game_dir() -> Path:
    settings_path = ROOT / "settings.json"
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        configured = Path(str(settings.get("k1_dir") or ""))
        if (configured / "chitin.key").is_file():
            return configured
    configured = Path(os.environ.get("K1_PATH", ""))
    if (configured / "chitin.key").is_file():
        return configured
    fallback = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if (fallback / "chitin.key").is_file():
        return fallback
    raise FileNotFoundError("A KOTOR 1 installation is required for the proof.")


def _median_band_depths(cave, geometry) -> list[float]:
    edge_start = cave.primitive.points[1]
    edge_end = cave.primitive.points[2]
    dx = float(edge_end[0]) - float(edge_start[0])
    dy = float(edge_end[1]) - float(edge_start[1])
    edge_length = math.hypot(dx, dy)
    band_depths: dict[int, list[float]] = {}
    for mesh in geometry.helper_meshes:
        if mesh.metadata.get("surface_role") != "cave_wall":
            continue
        if int(mesh.metadata.get("edge_index", -1)) != 1:
            continue
        band = int(mesh.metadata["contour_band"])
        top_z = max(float(vertex[2]) for vertex in mesh.vertices)
        for vertex in mesh.vertices:
            if math.isclose(float(vertex[2]), top_z, abs_tol=1.0e-7):
                inward = (
                    dx * (float(vertex[1]) - float(edge_start[1]))
                    - dy * (float(vertex[0]) - float(edge_start[0]))
                ) / edge_length
                band_depths.setdefault(band, []).append(inward)
    return [
        statistics.median(band_depths[index])
        for index in sorted(band_depths)
    ]


def main() -> int:
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_layout import authored_room_connection_hooks
    from src.core.modules.authored_module_project import compile_authored_room_spec
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        compile_authored_room_connection_walkmeshes,
    )
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resources = ResourceManager()
    game_dir = _game_dir()
    if not resources.set_k1_dir(str(game_dir)):
        raise RuntimeError(f"Could not load K1 resources from {game_dir}")

    controller = ModuleEditorController()
    controller.new_project(name="grshyrchain", game="K1")

    tomb_room = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (18.0, 0.0), (18.0, 14.0), (0.0, 14.0)),
        wall_height=3.9,
        style_id="architecture:k1_korriban_tombs",
    )
    controller.set_map_studio_building_opening(
        room_resref=tomb_room,
        edge_index=2,
        opening_kind="door",
        center_fraction=0.5,
        width=5.25,
        height=3.75,
        bottom=0.0,
    )

    cave_room = controller.add_map_studio_building_room(
        points=((-3.0, 16.0), (21.0, 16.0), (21.0, 34.0), (-3.0, 34.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_caves",
        include_ceiling=True,
    )
    controller.set_map_studio_building_opening(
        room_resref=cave_room,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=5.25,
        height=3.75,
        bottom=0.0,
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=cave_room,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=100.0,
    )
    cave_snap = controller.preview_authored_room_drag_snap(
        source_room_resref=cave_room,
        world_delta=broad["world_delta"],
    )
    if not cave_snap["magnet_snapped"]:
        raise RuntimeError(f"The generated cave did not snap to the tomb: {cave_snap}")
    controller.connect_authored_room_drag_snap(cave_snap)

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    cave_before_stock = next(
        room for room in authored.rooms if room.normalised_resref() == cave_room
    )
    cave_points = tuple(cave_before_stock.primitive.points)
    cave_origin = tuple(float(value) for value in cave_before_stock.position)
    north_start = cave_points[2]
    north_end = cave_points[3]
    north_midpoint = (
        cave_origin[0] + (float(north_start[0]) + float(north_end[0])) * 0.5,
        cave_origin[1] + (float(north_start[1]) + float(north_end[1])) * 0.5,
        cave_origin[2],
    )
    stock_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m38aa_m38aa_02",
        position=north_midpoint,
    )
    if not stock_preview["magnet_snapped"]:
        raise RuntimeError(
            f"The vanilla tomb did not snap to the Shyrack cave: {stock_preview}"
        )
    stock_tomb = controller.add_authored_environment_kit_piece(
        piece_id="k1_m38aa_m38aa_02",
        position=north_midpoint,
        resource_manager=resources,
    )

    second_cave = controller.add_map_studio_building_room(
        points=((0.0, 64.0), (24.0, 64.0), (24.0, 82.0), (0.0, 82.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_caves",
        include_ceiling=True,
    )
    controller.set_map_studio_building_opening(
        room_resref=second_cave,
        edge_index=0,
        opening_kind="door",
        center_fraction=0.5,
        width=5.25,
        height=4.15,
        bottom=0.0,
    )
    broad_second = controller.preview_authored_room_drag_snap(
        source_room_resref=second_cave,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=160.0,
    )
    second_preview = controller.preview_authored_room_drag_snap(
        source_room_resref=second_cave,
        world_delta=broad_second["world_delta"],
    )
    if not second_preview["magnet_snapped"] or second_preview["target_room_resref"] != stock_tomb:
        raise RuntimeError(
            f"The second parcel-built Shyrack cave did not snap to the vanilla tomb: {second_preview}"
        )
    controller.connect_authored_room_drag_snap(second_preview)

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    connections = compile_authored_room_connection_walkmeshes(authored)
    if not connections.ready:
        raise RuntimeError(
            "Connection walkmesh compilation failed: "
            + "; ".join(connections.blocking_issues)
        )
    cave = next(room for room in authored.rooms if room.normalised_resref() == cave_room)
    tomb = next(room for room in authored.rooms if room.normalised_resref() == tomb_room)
    second_cave_room = next(room for room in authored.rooms if room.normalised_resref() == second_cave)
    tomb_geometry = compile_authored_room_spec(tomb)
    geometry = compile_authored_room_spec(cave)
    second_geometry = compile_authored_room_spec(second_cave_room)
    helper_meshes = (
        tuple(tomb_geometry.helper_meshes)
        + tuple(geometry.helper_meshes)
        + tuple(second_geometry.helper_meshes)
    )
    roles = [
        str(mesh.metadata.get("architecture_role") or "")
        for mesh in helper_meshes
    ]
    transition_assets = [
        str(dict(opening.metadata or {}).get("module_transition_asset_id") or "")
        for room in authored.rooms
        if hasattr(room.primitive, "openings")
        for opening in room.primitive.openings
        if dict(opening.metadata or {}).get("module_transition_asset_id")
    ]
    transition_shells = [
        mesh
        for mesh in helper_meshes
        if mesh.metadata.get("module_transition_asset_id") == "shyrack_cave_entrance"
    ]
    korriban_transition_shells = [
        mesh
        for mesh in helper_meshes
        if mesh.metadata.get("module_transition_asset_id") == "korriban_cave_entrance"
    ]
    ceiling = tuple(
        mesh
        for mesh in helper_meshes
        if mesh.metadata.get("architecture_role") == "faceted_cave_ceiling"
    )
    band_depths = _median_band_depths(cave, geometry)
    reentrant_reversals = sum(
        following < previous - 0.05
        for previous, following in zip(band_depths, band_depths[1:])
    )

    combined = combine_authored_module_walkmesh(authored)
    if combined.blocking_issues:
        raise RuntimeError(
            "Combined WOK failed: " + "; ".join(combined.blocking_issues)
        )
    session = MapStudioPIESession(
        combined.wok,
        game="K1",
        spawn_position=(9.0, 12.0, 0.05),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    events = []
    hooks = authored_room_connection_hooks(authored)

    def connected_hook(room_resref: str, target_resref: str):
        return next(
            hook
            for hook in hooks
            if hook.room_resref == room_resref
            and hook.connected_room_resref == target_resref
        )

    def walk_across_hook(hook, outward_side: float, frame_limit: int = 900) -> bool:
        direction = (
            float(hook.outward[0]) * float(outward_side),
            float(hook.outward[1]) * float(outward_side),
        )
        camera_azimuth = math.degrees(math.atan2(-direction[1], -direction[0]))
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=camera_azimuth, run=True)
        for _index in range(frame_limit):
            events.extend(session.advance(1.0 / 30.0).events)
            signed_distance = (
                (float(session.state.position[0]) - float(hook.position[0]))
                * float(hook.outward[0])
                + (float(session.state.position[1]) - float(hook.position[1]))
                * float(hook.outward[1])
            )
            if signed_distance * float(outward_side) > 0.65:
                session.set_move_input(0.0, 0.0, camera_azimuth_degrees=camera_azimuth)
                return True
        session.set_move_input(0.0, 0.0, camera_azimuth_degrees=camera_azimuth)
        return False

    def walk_to(point: tuple[float, float, float], frame_limit: int = 1500) -> bool:
        if not session.set_destination(point, run=True):
            return False
        for _index in range(frame_limit):
            events.extend(session.advance(1.0 / 30.0).events)
            if session.state.destination is None:
                return True
        return False

    first_cave_to_stock = connected_hook(cave_room, stock_tomb)
    stock_to_second = connected_hook(stock_tomb, second_cave)
    final_center = (
        float(second_cave_room.position[0])
        + sum(float(point[0]) for point in second_cave_room.primitive.points) / len(second_cave_room.primitive.points),
        float(second_cave_room.position[1])
        + sum(float(point[1]) for point in second_cave_room.primitive.points) / len(second_cave_room.primitive.points),
        float(second_cave_room.position[2]) + 0.05,
    )
    first_portal_reached = walk_to(
        (
            float(first_cave_to_stock.position[0]) - float(first_cave_to_stock.outward[0]) * 0.55,
            float(first_cave_to_stock.position[1]) - float(first_cave_to_stock.outward[1]) * 0.55,
            float(first_cave_to_stock.position[2]) + 0.05,
        )
    )
    crossed_to_stock = first_portal_reached and walk_across_hook(first_cave_to_stock, 1.0)
    second_portal_reached = crossed_to_stock and walk_to(
        (
            float(stock_to_second.position[0]) - float(stock_to_second.outward[0]) * 0.55,
            float(stock_to_second.position[1]) - float(stock_to_second.outward[1]) * 0.55,
            float(stock_to_second.position[2]) + 0.05,
        )
    )
    crossed_to_second_cave = second_portal_reached and walk_across_hook(stock_to_second, 1.0)
    destination_accepted = crossed_to_second_cave and session.set_destination(final_center, run=True)
    if destination_accepted:
        for _index in range(1200):
            events.extend(session.advance(1.0 / 30.0).events)
            if session.state.destination is None:
                break

    controller.save_project(KMAP_PATH)
    export = controller.export_authored_module(EXPORT_DIR)
    visible_screenshots = tuple(
        path
        for path in (
            OUT_DIR / "pie_single_korriban_transition.png",
            OUT_DIR / "pie_inside_shyrack_room.png",
            OUT_DIR / "pie_at_shyrack_transition.png",
            OUT_DIR / "pie_crossed_shyrack_to_vanilla.png",
            OUT_DIR / "pie_second_portal_approach.png",
        )
        if path.is_file()
    )
    report = {
        "result": "PASS",
        "proof": "Pascal-built tomb -> parcel Shyrack cave -> vanilla tomb -> parcel Shyrack cave",
        "game": "K1",
        "kmap": str(KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "rooms": [room.normalised_resref() for room in authored.rooms],
        "generated_tomb_room": tomb_room,
        "generated_shyrack_room": cave_room,
        "vanilla_tomb_room": stock_tomb,
        "second_generated_shyrack_room": second_cave,
        "vanilla_source": "m38aa/m38aa_02",
        "room_count": len(authored.rooms),
        "separate_room_count": len(authored.rooms),
        "portal_count": len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap) for portal in connections.portals
        ],
        "door_actor_count": len(authored.placements.doors),
        "door_models": sorted(
            {
                str(dict(opening.metadata or {}).get("door_model_resref") or "")
                for room in authored.rooms
                if hasattr(room.primitive, "openings")
                for opening in room.primitive.openings
                if dict(opening.metadata or {}).get("door_model_resref")
            }
        ),
        "transition_assets": transition_assets,
        "open_transition_count": sum(
            1
            for room in authored.rooms
            if hasattr(room.primitive, "openings")
            for opening in room.primitive.openings
            if dict(opening.metadata or {}).get("open_module_transition")
        ),
        "cave_archway_transition_count": sum(
            1
            for room in authored.rooms
            if hasattr(room.primitive, "openings")
            for opening in room.primitive.openings
            if dict(opening.metadata or {}).get("cave_archway_transition")
        ),
        "shyrack_transition_shell_face_count": sum(
            len(mesh.faces) for mesh in transition_shells
        ),
        "shyrack_transition_shell_textures": sorted(
            {str(mesh.texture or "") for mesh in transition_shells}
        ),
        "korriban_transition_shell_face_count": sum(
            len(mesh.faces) for mesh in korriban_transition_shells
        ),
        "korriban_transition_shell_textures": sorted(
            {str(mesh.texture or "") for mesh in korriban_transition_shells}
        ),
        "stalactite_count": roles.count("shyrack_stalactite"),
        "stalagmite_count": roles.count("shyrack_stalagmite"),
        "ceiling_facet_count": len(ceiling),
        "ceiling_regions": sorted(
            {
                str(mesh.metadata.get("ceiling_region") or "")
                for mesh in ceiling
            }
        ),
        "wall_profile_depths": band_depths,
        "reentrant_profile_reversals": reentrant_reversals,
        "pie_final_position": [float(value) for value in session.state.position],
        "pie_first_portal_reached": bool(first_portal_reached),
        "pie_crossed_to_stock_tomb": bool(crossed_to_stock),
        "pie_second_portal_reached": bool(second_portal_reached),
        "pie_crossed_to_second_cave": bool(crossed_to_second_cave),
        "pie_destination_accepted": bool(destination_accepted),
        "pie_destination_reached": "destination_reached" in {event.kind for event in events},
        "pie_door_opened": "door_opened" in {event.kind for event in events},
        "export_ok": bool(export.ok),
        "export_readback_ok": bool(
            export.package_verification is not None
            and export.package_verification.ok
        ),
        "exported_woks": (
            list(export.package_verification.parsed_wok)
            if export.package_verification is not None
            else []
        ),
        "visible_proof": {
            "status": (
                "captured in the staged Debug Map Studio PIE workflow"
                if visible_screenshots
                else "pending staged-app capture"
            ),
            "screenshots": [str(path) for path in visible_screenshots],
        },
    }
    required = (
        report["room_count"] == 4,
        report["portal_count"] == 3,
        max(report["portal_midpoint_gaps"], default=1.0) <= 1.0e-5,
        report["door_actor_count"] == 0,
        not report["door_models"],
        report["transition_assets"].count("shyrack_cave_entrance") == 2,
        report["transition_assets"].count("korriban_cave_entrance") == 1,
        report["open_transition_count"] == 4,
        report["cave_archway_transition_count"] == 4,
        report["shyrack_transition_shell_face_count"] == 6273 * 2,
        report["shyrack_transition_shell_textures"] == ["gr_shyrentr"],
        report["korriban_transition_shell_face_count"] == 6624,
        report["korriban_transition_shell_textures"] == ["gr_korrentr"],
        report["stalactite_count"] >= 4,
        report["stalagmite_count"] >= 4,
        report["ceiling_facet_count"] >= 32,
        report["reentrant_profile_reversals"] >= 2,
        not report["pie_door_opened"],
        report["pie_first_portal_reached"],
        report["pie_crossed_to_stock_tomb"],
        report["pie_second_portal_reached"],
        report["pie_crossed_to_second_cave"],
        report["pie_destination_accepted"],
        report["pie_destination_reached"],
        math.dist(tuple(report["pie_final_position"]), final_center) <= 1.0,
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
