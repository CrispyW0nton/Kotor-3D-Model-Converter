from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2600_walkmesh_status_summarizes_flat_room_wok_intent() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_walkmesh_status import authored_walkmesh_status_for_project

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grwalk01",
        game="K1",
    )

    status = authored_walkmesh_status_for_project(project)

    assert status.ready is True
    assert status.room_count == 1
    assert status.terrain_room_count == 0
    assert "walkable triangle" in status.summary
    assert status.walkable_component_count == 1
    assert "Validate the module" in status.next_action


def test_t2600_walkmesh_status_reports_terrain_walkability_counts() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_operations import apply_authored_terrain_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_walkmesh_status import authored_walkmesh_status_for_project

    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grwalk02",
        game="K1",
    )
    project = apply_authored_terrain_operation(
        project,
        "set_height",
        row_index=1,
        column_index=1,
        height=5.0,
    )

    status = authored_walkmesh_status_for_project(project)

    assert status.ready is True
    assert status.room_count == 1
    assert status.terrain_room_count == 1
    assert status.walkable_triangle_count > 0
    assert status.non_walk_triangle_count > 0
    assert status.max_slope_degrees > 35.0
    assert "terrain room" in status.summary
    assert "Inspect green/orange terrain overlay" in status.next_action


def test_t2600_controller_exposes_walkmesh_status_for_map_studio() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    empty = controller.authored_walkmesh_status()

    assert empty.ready is False
    assert "no authored Map Studio module" in empty.summary

    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grwalk03")
    status = controller.authored_walkmesh_status()

    assert status.ready is True
    assert status.room_count == 1
    assert "walkable triangle" in status.summary


def test_t2604_wok_audit_blocks_disconnected_walkable_islands() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_walkmesh_audit import audit_authored_wok
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 1.0, 0.0),
            (3.0, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=4, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=4, adj1=0, adj2=-1, adj3=-1),
            WOKFace(4, 5, 6, surface=4, adj1=-1, adj2=-1, adj3=3),
            WOKFace(4, 6, 7, surface=4, adj1=2, adj2=-1, adj3=-1),
        ],
    )

    audit = audit_authored_wok("grsplit", wok)

    assert audit.ready is False
    assert audit.walkable_face_count == 4
    assert audit.walkable_component_count == 2
    assert audit.disconnected_component_count == 1
    assert any("disconnected walkable island" in message for message in audit.blocking_messages)


def test_t2604_walkmesh_status_and_readiness_block_disconnected_composition_room() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
    from src.core.modules.authored_room_primitives import FloorPrimitive
    from src.core.modules.authored_walkmesh_status import authored_walkmesh_status_for_project

    composition = AuthoredRoomComposition(
        room_resref="grsplit",
        floor=FloorPrimitive(name="main_floor", width=4.0, depth=4.0, surface_id=4),
        primitives=(
            PlacedRoomPrimitive(
                primitive=FloorPrimitive(name="isolated_floor", width=2.0, depth=2.0, surface_id=4),
                transform=PrimitiveTransform(translation=(8.0, 0.0, 0.0)),
                name="isolated_floor",
            ),
        ),
    )
    project = create_composition_room_project(
        module_root="grsplit",
        game="K1",
        display_name="Split WOK Test",
        composition=composition,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grsplit")),
    )

    status = authored_walkmesh_status_for_project(project)
    readiness = build_authored_module_readiness(project)

    assert status.ready is False
    assert status.walkable_component_count == 2
    assert status.disconnected_walkmesh_room_count == 1
    assert any("disconnected walkable island" in message for message in status.blocking_messages)
    assert readiness.can_preview is False
    assert any("disconnected walkable island" in message for message in readiness.blocking_messages)
