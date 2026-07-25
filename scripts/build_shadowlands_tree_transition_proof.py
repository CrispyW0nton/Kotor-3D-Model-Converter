"""Build the focused Shadowlands tree-tunnel module-transition proof.

The KMAP joins two separate Pascal-built Shadowlands clearings through the
vanilla ``m25aa_11a`` bend.  Each authored opening owns one supplied tree/root
transition shell, a sealed visual floor, forest panorama cards, and an exact
reciprocal WOK portal.
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


OUT_DIR = ROOT / "artifacts" / "shadowlands_proof" / "tree_transition"
KMAP_PATH = OUT_DIR / "grshadowtree.kmap"
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


def _room_center(room) -> tuple[float, float, float]:
    points = tuple(room.primitive.points or ())
    return (
        float(room.position[0]) + sum(float(point[0]) for point in points) / len(points),
        float(room.position[1]) + sum(float(point[1]) for point in points) / len(points),
        float(room.position[2]) + float(room.primitive.z) + 0.05,
    )


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
    controller.new_project(name="grshadowtree", game="K1")
    first_clearing = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (24.0, 0.0), (24.0, 20.0), (0.0, 20.0)),
        wall_height=6.0,
        style_id="architecture:k1_shadowlands",
    )
    stock_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m25aa_m25aa_11a",
        position=(12.0, 20.0, 0.0),
    )
    if not stock_preview["magnet_snapped"] or not stock_preview["target_is_authored_wall"]:
        raise RuntimeError(f"The vanilla bend did not snap to the first clearing: {stock_preview}")
    vanilla_bend = controller.add_authored_environment_kit_piece(
        piece_id="k1_m25aa_m25aa_11a",
        position=(12.0, 20.0, 0.0),
        resource_manager=resources,
    )

    second_clearing = controller.add_map_studio_building_room(
        points=((0.0, 80.0), (24.0, 80.0), (24.0, 100.0), (0.0, 100.0)),
        wall_height=6.0,
        style_id="architecture:k1_shadowlands",
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=second_clearing,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=300.0,
    )
    exact = controller.preview_authored_room_drag_snap(
        source_room_resref=second_clearing,
        world_delta=broad["world_delta"],
    )
    if not exact["magnet_snapped"] or exact["target_room_resref"] != vanilla_bend:
        raise RuntimeError(f"The second clearing did not snap to the free vanilla portal: {exact}")
    controller.connect_authored_room_drag_snap(exact)
    # Put the visible PIE proof on-axis with the first supplied tree tunnel
    # instead of leaving the default player start aimed across the clearing.
    controller.set_authored_module_entry_point(
        position=(12.0, 14.5, 0.0),
        facing=math.pi * 0.5,
    )

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    connections = compile_authored_room_connection_walkmeshes(authored)
    if not connections.ready:
        raise RuntimeError(
            "Connection walkmesh compilation failed: "
            + "; ".join(connections.blocking_issues)
        )
    combined = combine_authored_module_walkmesh(authored)
    if combined.blocking_issues:
        raise RuntimeError("Combined WOK failed: " + "; ".join(combined.blocking_issues))

    first_room = next(
        room for room in authored.rooms if room.normalised_resref() == first_clearing
    )
    second_room = next(
        room for room in authored.rooms if room.normalised_resref() == second_clearing
    )
    transition_assets: list[str] = []
    shell_face_count = 0
    shell_trim_policies: set[str] = set()
    shell_clearance_widths: list[float] = []
    shell_clearance_heights: list[float] = []
    panorama_count = 0
    threshold_count = 0
    for room in (first_room, second_room):
        transition_assets.extend(
            str(dict(opening.metadata or {}).get("module_transition_asset_id") or "")
            for opening in room.primitive.openings
        )
        geometry = compile_authored_room_spec(room)
        shell_meshes = tuple(
            mesh
            for mesh in geometry.helper_meshes
            if mesh.metadata.get("module_transition_asset_id")
            == "shadowlands_module_transition"
        )
        shell_face_count += sum(len(mesh.faces) for mesh in shell_meshes)
        shell_trim_policies.update(
            str(mesh.metadata.get("geometry_trim_policy") or "")
            for mesh in shell_meshes
        )
        shell_clearance_widths.extend(
            float(mesh.metadata.get("player_clearance_half_width_m", 0.0)) * 2.0
            for mesh in shell_meshes
        )
        shell_clearance_heights.extend(
            float(mesh.metadata.get("player_clearance_height_m", 0.0))
            for mesh in shell_meshes
        )
        panorama_count += sum(
            mesh.metadata.get("architecture_role")
            == "shadowlands_jungle_panorama_card"
            for mesh in geometry.helper_meshes
        )
        threshold_count += sum(
            mesh.metadata.get("architecture_role")
            == "shadowlands_transition_floor"
            for mesh in geometry.helper_meshes
        )

    session = MapStudioPIESession(
        combined.wok,
        game="K1",
        spawn_position=_room_center(first_room),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    events = []
    stock_hooks = {
        hook.connected_room_resref: hook
        for hook in authored_room_connection_hooks(authored)
        if hook.room_resref == vanilla_bend and hook.connected_room_resref
    }
    first_hook = stock_hooks[first_clearing]
    second_hook = stock_hooks[second_clearing]

    def cross_portal(direction, hook, outward_side, frame_limit) -> bool:
        camera_azimuth = math.degrees(math.atan2(-direction[1], -direction[0]))
        session.set_move_input(
            1.0,
            0.0,
            camera_azimuth_degrees=camera_azimuth,
            run=True,
        )
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
                session.set_move_input(
                    0.0,
                    0.0,
                    camera_azimuth_degrees=camera_azimuth,
                )
                return True
        return False

    crossed_first = cross_portal(
        (
            float(first_hook.position[0]) - float(session.state.position[0]),
            float(first_hook.position[1]) - float(session.state.position[1]),
        ),
        first_hook,
        -1.0,
        900,
    )
    inside_second = (
        float(second_hook.position[0]) - float(second_hook.outward[0]) * 0.85,
        float(second_hook.position[1]) - float(second_hook.outward[1]) * 0.85,
        float(second_hook.position[2]) + 0.05,
    )
    inside_destination_accepted = crossed_first and session.set_destination(
        inside_second,
        run=True,
    )
    if inside_destination_accepted:
        for _index in range(1800):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            if session.state.destination is None:
                break
    crossed_second = (
        cross_portal(second_hook.outward, second_hook, 1.0, 900)
        if inside_destination_accepted
        else False
    )
    final_destination_accepted = crossed_second and session.set_destination(
        _room_center(second_room),
        run=True,
    )
    if final_destination_accepted:
        for _index in range(1200):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            if session.state.destination is None:
                break

    controller.save_project(KMAP_PATH)
    export = controller.export_authored_module(EXPORT_DIR)
    event_kinds = {event.kind for event in events}
    report = {
        "result": "PASS",
        "proof": "Pascal Shadowlands clearing -> vanilla m25aa bend -> Pascal clearing",
        "game": "K1",
        "kmap": str(KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "rooms": [room.normalised_resref() for room in authored.rooms],
        "first_generated_clearing": first_clearing,
        "vanilla_shadowlands_room": vanilla_bend,
        "vanilla_source": "m25aa/m25aa_11a",
        "second_generated_clearing": second_clearing,
        "room_count": len(authored.rooms),
        "separate_room_count": len(authored.rooms),
        "portal_count": len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap) for portal in connections.portals
        ],
        "transition_assets": transition_assets,
        "tree_tunnel_shell_face_count": shell_face_count,
        "tree_tunnel_trim_policies": sorted(shell_trim_policies),
        "tree_tunnel_min_clearance_width_m": min(shell_clearance_widths, default=0.0),
        "tree_tunnel_min_clearance_height_m": min(shell_clearance_heights, default=0.0),
        "panorama_card_count": panorama_count,
        "visual_threshold_count": threshold_count,
        "crossed_first_transition": crossed_first,
        "inside_destination_accepted": inside_destination_accepted,
        "crossed_second_transition": crossed_second,
        "final_destination_accepted": final_destination_accepted,
        "pie_event_kinds": sorted(event_kinds),
        "pie_destination_reached": "destination_reached" in event_kinds,
        "pie_final_position": [float(value) for value in session.state.position],
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
            "status": "pending staged-app capture",
            "screenshots": [],
        },
    }
    required = (
        report["room_count"] == 3,
        report["portal_count"] == 2,
        max(report["portal_midpoint_gaps"], default=1.0) <= 2.0e-5,
        report["transition_assets"].count("shadowlands_module_transition") == 2,
        report["tree_tunnel_shell_face_count"] > 0,
        report["tree_tunnel_trim_policies"] == [
            "portal_envelope_minus_player_clearance"
        ],
        report["tree_tunnel_min_clearance_width_m"] >= 2.0,
        report["tree_tunnel_min_clearance_height_m"] >= 2.1,
        report["panorama_card_count"] == 8,
        report["visual_threshold_count"] == 2,
        report["crossed_first_transition"],
        report["inside_destination_accepted"],
        report["crossed_second_transition"],
        report["final_destination_accepted"],
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
