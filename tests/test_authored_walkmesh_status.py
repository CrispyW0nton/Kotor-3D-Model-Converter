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
    assert "generated WOK intent" in status.summary
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
    assert "generated WOK intent" in status.summary
