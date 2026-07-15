from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

import pytest


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _cube_payload(controller, name: str) -> dict:
    payload = controller.project.extra_sections["authored_module"]
    return next(
        row
        for row in payload["rooms"][0]["primitive"]["primitives"]
        if row["name"] == name
    )


def test_primitive_recipe_preview_is_scoped_non_mutating_and_commits_once() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="elevation_test_room",
        module_root="grrecipe",
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        primitive_name="polyCube1",
    )

    payload = controller.project.extra_sections["authored_module"]
    payload_before = deepcopy(payload)
    payload_identity = id(payload)
    undo_count = len(controller.command_history.undo_stack)

    preview = controller.preview_authored_room_primitive_dimensions(
        room_resref="grrecipe_room01",
        primitive_name="polyCube1",
        dimensions={
            "size_x": 2.0,
            "size_y": 3.0,
            "size_z": 4.0,
            "subdivisions_x": 2,
            "subdivisions_y": 3,
            "subdivisions_z": 4,
        },
    )

    assert len(preview) == 1
    assert preview[0]["primitive_name"] == "polyCube1"
    assert len(preview[0]["faces"]) == 104
    assert id(controller.project.extra_sections["authored_module"]) == payload_identity
    assert controller.project.extra_sections["authored_module"] == payload_before
    assert len(controller.command_history.undo_stack) == undo_count
    assert controller.last_map_studio_primitive_preview_elapsed_ms < 20.0
    overlay = controller.last_map_studio_primitive_preview_overlay
    assert overlay is not None
    assert overlay.primitive_name == "polyCube1"
    assert overlay.coordinate_space == "kmap_world_preview"
    assert overlay.dimensions == pytest.approx((2.0, 3.0, 4.0))
    assert (overlay.vertex_count, overlay.metadata["logical_edge_count"], overlay.face_count) == (54, 104, 52)
    assert overlay.metadata["topology_count_source"] == "retained_construction_cage"

    controller.set_authored_room_primitive_dimensions(
        room_resref="grrecipe_room01",
        primitive_name="polyCube1",
        dimensions={
            "size_x": 2.0,
            "size_y": 3.0,
            "size_z": 4.0,
            "subdivisions_x": 2,
            "subdivisions_y": 3,
            "subdivisions_z": 4,
        },
    )

    committed = _cube_payload(controller, "polyCube1")
    assert committed["size"] == [2.0, 3.0, 4.0]
    assert committed["subdivisions_x"] == 2
    assert committed["subdivisions_y"] == 3
    assert committed["subdivisions_z"] == 4
    assert len(controller.command_history.undo_stack) == undo_count + 1


def test_invalid_primitive_recipe_preview_does_not_touch_kmap_or_history() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(
        preset_id="elevation_test_room",
        module_root="grrecipe",
    )
    controller.add_authored_room_primitive(
        primitive_kind="cube",
        primitive_name="polyCube1",
    )
    payload_before = deepcopy(controller.project.extra_sections["authored_module"])
    undo_count = len(controller.command_history.undo_stack)

    with pytest.raises(ValueError, match="at least"):
        controller.preview_authored_room_primitive_dimensions(
            room_resref="grrecipe_room01",
            primitive_name="polyCube1",
            dimensions={"subdivisions_x": 0},
        )

    assert controller.project.extra_sections["authored_module"] == payload_before
    assert len(controller.command_history.undo_stack) == undo_count
