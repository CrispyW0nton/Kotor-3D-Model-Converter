"""Build the focused Telos Citadel Station Pascal-to-vanilla proof.

The saved KMAP contains three separate, walkable rooms:

1. a Pascal-built 203/204TEL residential gallery,
2. the vanilla K2 ``203telv`` bend, snapped through its first stock portal, and
3. a Pascal-built 202/222TEL civic passage, snapped to the remaining portal.

The proof also verifies the stock DOR_TEL14 resources, repeated UV projection,
the complete Telos content shelf, reciprocal WOK portals, PIE traversal, and
MOD export/readback.

Run from the repository root:
    py -3.14 scripts/build_telos_citadel_connection_proof.py
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


OUT_DIR = ROOT / "artifacts" / "telos_citadel_proof"
KMAP_PATH = OUT_DIR / "grteloskit.kmap"
EXPORT_DIR = OUT_DIR / "export_readback"
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
    raise FileNotFoundError("A KOTOR 2 installation is required for the Telos proof.")


def _floor_plan_center(room) -> tuple[float, float, float]:
    points = tuple(getattr(room.primitive, "points", ()) or ())
    if not points:
        raise ValueError(f"{room.normalised_resref()} is not a generated floor-plan room.")
    return (
        float(room.position[0]) + sum(float(point[0]) for point in points) / len(points),
        float(room.position[1]) + sum(float(point[1]) for point in points) / len(points),
        float(room.position[2]) + float(getattr(room.primitive, "z", 0.0)) + 0.05,
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
    from src.core.modules.map_studio_environment_kits import (
        environment_kit_collection_rows,
        environment_kit_piece_rows,
    )
    from src.core.modules.map_studio_pascal_building import pascal_architecture_runtime_resources
    from src.core.modules.map_studio_pie import MapStudioPIESession
    from src.core.modules.map_studio_pie_entities import build_pie_entity_registry
    from src.core.modules.module_editor_controller import ModuleEditorController

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resources = ResourceManager()
    game_dir = _game_dir()
    if not resources.set_k2_dir(str(game_dir)):
        raise RuntimeError(f"Could not load K2 resources from {game_dir}")

    controller = ModuleEditorController()
    controller.new_project(name="grteloskit", game="K2")
    residential = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (12.0, 0.0), (12.0, 8.0), (0.0, 8.0)),
        wall_height=3.985,
        style_id="architecture:k2_telos_citadel",
        architecture_archetype="residential",
    )
    stock_preview = controller.preview_authored_terrain_kit_placement(
        asset_id="k2_203tel_203telv",
        position=(6.0, 8.0, 0.0),
    )
    if not stock_preview["magnet_snapped"] or not stock_preview["target_is_authored_wall"]:
        raise RuntimeError(f"The vanilla Telos bend did not snap to the residential wall: {stock_preview}")
    vanilla_bend = controller.add_authored_environment_kit_piece(
        piece_id="k2_203tel_203telv",
        position=(6.0, 8.0, 0.0),
        resource_manager=resources,
    )

    civic = controller.add_map_studio_building_room(
        points=((0.0, 60.0), (14.0, 60.0), (14.0, 70.0), (0.0, 70.0)),
        wall_height=5.995,
        style_id="architecture:k2_telos_citadel",
        architecture_archetype="civic",
    )
    broad = controller.preview_authored_room_drag_snap(
        source_room_resref=civic,
        world_delta=(0.0, 0.0, 0.0),
        snap_distance=200.0,
    )
    exact = controller.preview_authored_room_drag_snap(
        source_room_resref=civic,
        world_delta=broad["world_delta"],
    )
    if not exact["magnet_snapped"] or exact["target_room_resref"] != vanilla_bend:
        raise RuntimeError(f"The civic passage did not snap to the free vanilla Telos portal: {exact}")
    controller.connect_authored_room_drag_snap(exact)

    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    first_room = next(room for room in authored.rooms if room.normalised_resref() == residential)
    second_room = next(room for room in authored.rooms if room.normalised_resref() == civic)
    controller.set_authored_module_entry_point(
        position=_floor_plan_center(first_room),
        facing=math.pi * 0.5,
    )
    authored = authored_project_from_kmap_payload(
        controller.project.extra_sections["authored_module"]
    )
    first_room = next(room for room in authored.rooms if room.normalised_resref() == residential)
    second_room = next(room for room in authored.rooms if room.normalised_resref() == civic)

    connections = compile_authored_room_connection_walkmeshes(authored)
    if not connections.ready:
        raise RuntimeError(
            "Telos connection walkmesh compilation failed: "
            + "; ".join(connections.blocking_issues)
        )
    combined = combine_authored_module_walkmesh(authored)
    if combined.blocking_issues:
        raise RuntimeError("Combined Telos WOK failed: " + "; ".join(combined.blocking_issues))

    generated_geometry = (
        compile_authored_room_spec(first_room),
        compile_authored_room_spec(second_room),
    )
    helper_meshes = tuple(
        mesh for geometry in generated_geometry for mesh in geometry.helper_meshes
    )
    architecture_roles = {
        str(mesh.metadata.get("architecture_role") or "")
        for mesh in helper_meshes
    }
    bad_uv_meshes = [
        mesh.name
        for mesh in helper_meshes
        if len(mesh.uvs) != len(mesh.vertices)
    ]

    door_resources = pascal_architecture_runtime_resources(authored)
    telos_door_bytes = next(
        data
        for resref, restype, data in door_resources
        if (resref, restype) == ("gr_teldoor", "utd")
    )
    telos_door = read_utd(telos_door_bytes)

    telos_rows = tuple(
        row
        for row in environment_kit_piece_rows(game="K2")
        if row["building_style_id"] == "architecture:k2_telos_citadel"
    )
    telos_collections = tuple(
        row
        for row in environment_kit_collection_rows(game="K2")
        if row["building_style_id"] == "architecture:k2_telos_citadel"
    )
    dressing_rows = tuple(
        row
        for row in telos_rows
        if row["collection_id"] == "k2_telos_citadel_dressing"
    )
    vanilla_rows = tuple(
        row for row in telos_rows if row["role"] in {"room_tile", "exterior_tile"}
    )

    session = MapStudioPIESession(
        combined.wok,
        game="K2",
        spawn_position=_floor_plan_center(first_room),
    )
    session.entity_registry = build_pie_entity_registry(authored)
    bend_hooks = {
        hook.connected_room_resref: hook
        for hook in authored_room_connection_hooks(authored)
        if hook.room_resref == vanilla_bend and hook.connected_room_resref
    }
    first_hook = bend_hooks[residential]
    second_hook = bend_hooks[civic]
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

    first_direction = (
        float(first_hook.position[0]) - float(session.state.position[0]),
        float(first_hook.position[1]) - float(session.state.position[1]),
    )
    crossed_first = walk_across(
        first_direction,
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
        _floor_plan_center(second_room),
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
        "proof": "Pascal Telos residential -> vanilla 203telv -> Pascal Telos civic",
        "game": "K2",
        "kmap": str(KMAP_PATH),
        "export_directory": str(EXPORT_DIR),
        "rooms": [room.normalised_resref() for room in authored.rooms],
        "residential_room": residential,
        "vanilla_room": vanilla_bend,
        "vanilla_source": "203tel/203telv",
        "civic_room": civic,
        "separate_room_count": len(authored.rooms),
        "portal_count": len(connections.portals),
        "portal_midpoint_gaps": [
            float(portal.midpoint_gap) for portal in connections.portals
        ],
        "walkable_face_count": len(combined.wok.faces),
        "door_actor_count": len(authored.placements.doors),
        "door_templates": sorted(
            str(door.template_resref or "") for door in authored.placements.doors
        ),
        "telos_door_appearance_id": int(telos_door.appearance_id),
        "architecture_roles": sorted(architecture_roles),
        "helper_mesh_count": len(helper_meshes),
        "bad_uv_meshes": bad_uv_meshes,
        "telos_collection_count": len(telos_collections),
        "vanilla_room_browser_count": len(vanilla_rows),
        "separate_dressing_piece_count": len(dressing_rows),
        "dressing_piece_ids": [row["piece_id"] for row in dressing_rows],
        "crossed_first_door": crossed_first,
        "bend_destination_accepted": bend_destination_accepted,
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
        report["separate_room_count"] == 3,
        report["portal_count"] == 2,
        max(report["portal_midpoint_gaps"], default=1.0) <= 2.0e-5,
        report["walkable_face_count"] > 0,
        report["door_actor_count"] == 2,
        set(report["door_templates"]) == {"gr_teldoor"},
        report["telos_door_appearance_id"] == 117,
        not report["bad_uv_meshes"],
        report["vanilla_room_browser_count"] >= 90,
        report["separate_dressing_piece_count"] == 9,
        report["crossed_first_door"],
        report["bend_destination_accepted"],
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
