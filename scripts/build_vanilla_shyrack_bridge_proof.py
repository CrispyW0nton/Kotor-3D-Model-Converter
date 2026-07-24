"""Build the focused vanilla-Shyrack module-transition proof.

The generated KMAP contains three separate rooms:

1. a Pascal-built Korriban tomb,
2. the vanilla K1 ``m34aa_01a`` Shyrack cave room, and
3. a second Pascal-built Korriban tomb dragged onto the cave's free WOK portal.

Both ends use the supplied mirrored Korriban transition shell, authentic
``DOR_LKO04`` door actors, and reciprocal WOK transition edges.
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


OUT_DIR = ROOT / "artifacts" / "korriban_proof" / "vanilla_shyrack_bridge"
KMAP_PATH = OUT_DIR / "grshyrbridge.kmap"
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
    points = tuple(getattr(room.primitive, "points", ()) or ())
    if not points:
        raise ValueError(f"{room.normalised_resref()} is not a floor-plan room.")
    return (
        float(room.position[0]) + sum(float(point[0]) for point in points) / len(points),
        float(room.position[1]) + sum(float(point[1]) for point in points) / len(points),
        float(room.position[2]) + float(getattr(room.primitive, "z", 0.0)) + 0.05,
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
    controller.new_project(name="grshyrbridge", game="K1")
    first_tomb = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (20.0, 0.0), (20.0, 14.0), (0.0, 14.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_tombs",
    )
    first_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k1_m34aa_m34aa_01a",
        position=(10.0, 14.0, 0.0),
    )
    if not first_preview["magnet_snapped"] or not first_preview["target_is_authored_wall"]:
        raise RuntimeError(f"The vanilla cave did not snap to the first tomb: {first_preview}")
    vanilla_cave = controller.add_authored_environment_kit_piece(
        piece_id="k1_m34aa_m34aa_01a",
        position=(10.0, 14.0, 0.0),
        resource_manager=resources,
    )

    second_tomb = controller.add_map_studio_building_room(
        points=((0.0, 60.0), (20.0, 60.0), (20.0, 74.0), (0.0, 74.0)),
        wall_height=6.25,
        style_id="architecture:k1_korriban_tombs",
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=second_tomb,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=200.0,
    )
    exact = controller.preview_authored_room_drag_snap(
        source_room_resref=second_tomb,
        world_delta=broad["world_delta"],
    )
    if not exact["magnet_snapped"] or exact["target_room_resref"] != vanilla_cave:
        raise RuntimeError(f"The second tomb did not snap to the free vanilla cave portal: {exact}")
    controller.connect_authored_room_drag_snap(exact)
    controller.set_authored_module_entry_point(
        position=(10.0, 8.5, 0.0),
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

    first_room = next(room for room in authored.rooms if room.normalised_resref() == first_tomb)
    second_room = next(room for room in authored.rooms if room.normalised_resref() == second_tomb)
    generated_rooms = (first_room, second_room)
    transition_ids = [
        str(dict(opening.metadata or {}).get("module_transition_asset_id") or "")
        for room in generated_rooms
        for opening in tuple(room.primitive.openings or ())
    ]
    shell_faces = 0
    shell_textures: set[str] = set()
    for room in generated_rooms:
        geometry = compile_authored_room_spec(room)
        for mesh in geometry.helper_meshes:
            if mesh.metadata.get("module_transition_asset_id") != "korriban_cave_entrance":
                continue
            shell_faces += len(mesh.faces)
            shell_textures.add(str(mesh.texture or ""))

    session = MapStudioPIESession(
        combined.wok,
        game="K1",
        spawn_position=_room_center(first_room),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    destination = _room_center(second_room)
    events = []
    cave_hooks = {
        hook.connected_room_resref: hook
        for hook in authored_room_connection_hooks(authored)
        if hook.room_resref == vanilla_cave and hook.connected_room_resref
    }
    first_hook = cave_hooks[first_tomb]
    second_hook = cave_hooks[second_tomb]

    def walk_direction_across_portal(
        direction: tuple[float, float],
        *,
        hook,
        outward_side: float,
        frame_limit: int,
    ) -> bool:
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

    first_direction = (
        float(first_hook.position[0]) - float(session.state.position[0]),
        float(first_hook.position[1]) - float(session.state.position[1]),
    )
    crossed_first = walk_direction_across_portal(
        first_direction,
        hook=first_hook,
        outward_side=-1.0,
        frame_limit=900,
    )
    cave_destination = (
        float(second_hook.position[0]) - float(second_hook.outward[0]) * 0.85,
        float(second_hook.position[1]) - float(second_hook.outward[1]) * 0.85,
        float(second_hook.position[2]) + 0.05,
    )
    cave_destination_accepted = crossed_first and session.set_destination(
        cave_destination,
        run=True,
    )
    if cave_destination_accepted:
        for _index in range(1800):
            result = session.advance(1.0 / 30.0)
            events.extend(result.events)
            if session.state.destination is None:
                break
    crossed_second = walk_direction_across_portal(
        tuple(float(value) for value in second_hook.outward),
        hook=second_hook,
        outward_side=1.0,
        frame_limit=900,
    ) if cave_destination_accepted else False
    final_destination_accepted = crossed_second and session.set_destination(
        destination,
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
        "proof": "Pascal tomb -> vanilla m34aa Shyrack cave -> Pascal tomb",
        "game": "K1",
        "kmap": str(KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "rooms": [room.normalised_resref() for room in authored.rooms],
        "first_generated_tomb": first_tomb,
        "vanilla_shyrack_room": vanilla_cave,
        "vanilla_source": "m34aa/m34aa_01a",
        "second_generated_tomb": second_tomb,
        "room_count": len(authored.rooms),
        "separate_room_count": len(authored.rooms),
        "portal_count": len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap) for portal in connections.portals
        ],
        "transition_assets": transition_ids,
        "transition_shell_face_count": shell_faces,
        "transition_shell_textures": sorted(shell_textures),
        "door_actor_count": len(authored.placements.doors),
        "door_templates": sorted(
            str(door.template_resref or "") for door in authored.placements.doors
        ),
        "crossed_first_door": crossed_first,
        "cave_destination_accepted": cave_destination_accepted,
        "crossed_second_door": crossed_second,
        "final_destination_accepted": final_destination_accepted,
        "pie_final_position": [float(value) for value in session.state.position],
        "pie_event_kinds": sorted(event_kinds),
        "pie_destination_reached": "destination_reached" in event_kinds,
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
        report["transition_assets"].count("korriban_cave_entrance") == 2,
        report["transition_shell_face_count"] == 7438 * 2,
        report["transition_shell_textures"] == ["gr_korrentr"],
        report["door_actor_count"] == 2,
        set(report["door_templates"]) == {"gr_korrdoor"},
        report["crossed_first_door"],
        report["cave_destination_accepted"],
        report["crossed_second_door"],
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
