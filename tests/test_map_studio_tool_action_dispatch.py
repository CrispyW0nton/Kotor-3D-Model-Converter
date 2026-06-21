from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    for rel in reversed(
        (
            "native/GhostRigger.Core.Scene/Python",
            "native/GhostRigger.Core.Rendering/Python",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Game/Python",
            "native/GhostRigger.Core.Resources/Python",
            ".",
        )
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_t2606_tool_action_dispatch_resolves_command_and_disabled_context() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        resolve_map_studio_tool_belt_action,
    )

    cube = resolve_map_studio_tool_belt_action("cube")

    assert cube.enabled is True
    assert cube.command_method == "add_authored_room_primitive"
    assert cube.command_kwargs["primitive_kind"] == "cube"
    assert cube.mutates_kmap is True
    assert cube.stale_outputs == ("MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod")
    assert "game proof" in cube.readiness_impact

    snap = resolve_map_studio_tool_belt_action("vertex_snap")

    assert snap.enabled is False
    assert "source point and a target point" in snap.disabled_reason
    assert snap.command_method == ""

    ready_snap = resolve_map_studio_tool_belt_action(
        "vertex_snap",
        MapStudioToolActionContext(
            room_resref="room_a",
            point_index=0,
            target_point_index=1,
            target_room_resref="room_b",
        ),
    )

    assert ready_snap.enabled is True
    assert ready_snap.command_method == "snap_authored_floor_plan_vertex"
    assert ready_snap.command_kwargs["target_room_resref"] == "room_b"

    extrude = resolve_map_studio_tool_belt_action(
        "extrude",
        MapStudioToolActionContext(room_resref="room_a", operation_distance=0.75, operation_edge_index=2),
    )

    assert extrude.enabled is True
    assert extrude.command_method == "apply_authored_room_operation"
    assert extrude.command_kwargs == {
        "operation": "edge_extrude",
        "room_resref": "room_a",
        "distance": 0.75,
        "edge_index": 2,
    }

    boolean = resolve_map_studio_tool_belt_action(
        "boolean",
        MapStudioToolActionContext(room_resref="room_a", cut_center=(1.0, 2.0), cut_size=(3.0, 4.0)),
    )

    assert boolean.enabled is True
    assert boolean.command_method == "apply_authored_room_operation"
    assert boolean.command_kwargs["operation"] == "rectangular_cut"
    assert boolean.command_kwargs["center"] == (1.0, 2.0)
    assert boolean.command_kwargs["size"] == (3.0, 4.0)


def test_t2606_tool_action_dispatch_executes_headless_command_and_records_undo() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_tool_action_dispatch import (
        MapStudioToolActionContext,
        execute_map_studio_tool_belt_action,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grbelt01", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grbelt01")

    before_count = len(controller.authored_room_primitive_transforms())

    execute_map_studio_tool_belt_action(controller, "cube")

    after = controller.authored_room_primitive_transforms()
    assert len(after) == before_count + 1
    assert after[-1].primitive_type == "cube"
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Add cube primitive"

    undo = controller.undo_map_studio_command()

    assert undo is not None
    assert len(controller.authored_room_primitive_transforms()) == before_count

    controller.create_authored_room_preset_module(preset_id="octagonal_room", module_root="grbevel01")
    room_before = controller.authored_floor_plan_room_choices()[0]
    execute_map_studio_tool_belt_action(
        controller,
        "bevel",
        MapStudioToolActionContext(room_resref=room_before.room_resref, operation_distance=0.1),
    )
    room_after = controller.authored_floor_plan_room_choices()[0]

    assert room_after.point_count > room_before.point_count
    assert controller.can_undo_map_studio_command() is True
    assert controller.command_history.undo_label == "Apply room operation bevel"


def test_t2606_level_editor_routes_tool_belt_actions_through_core_dispatcher() -> None:
    window_source = _read("native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py")
    scene_dispatcher = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    tools_dispatcher = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_tool_action_dispatch.py")
    scene_catalog = _read("native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_modeling_tools.py")
    tools_catalog = _read("native/GhostRigger.Core.Tools/Python/src/core/modules/map_studio_modeling_tools.py")

    assert "from src.core.modules.map_studio_tool_action_dispatch import" in window_source
    assert "resolve_map_studio_tool_belt_action(key, route_context)" in window_source
    assert "execute_map_studio_tool_belt_action(self.controller, action_key, context)" in window_source
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in scene_catalog
    assert 'MapStudioToolBeltAction(\n        "triangulate",' in tools_catalog

    for source in (scene_dispatcher, tools_dispatcher):
        assert "class MapStudioToolActionContext" in source
        assert "class MapStudioToolActionRoute" in source
        assert "def resolve_map_studio_tool_belt_action" in source
        assert "def execute_map_studio_tool_belt_action" in source
        assert 'command_method="add_authored_room_primitive"' in source
        assert 'command_method="snap_authored_floor_plan_vertex"' in source
        assert 'command_method="apply_authored_room_operation"' in source
