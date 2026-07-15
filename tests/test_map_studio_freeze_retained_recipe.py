from __future__ import annotations

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


def _project():
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_composition_room_project
    from src.core.modules.authored_room_composition import AuthoredRoomComposition
    from src.core.modules.authored_room_primitives import CubePrimitive, FloorPrimitive

    return create_composition_room_project(
        module_root="freeze",
        game="K2",
        display_name="Freeze Recipe",
        composition=AuthoredRoomComposition(
            room_resref="freeze_room",
            floor=FloorPrimitive(
                name="polyPlaneFreeze",
                width=7.0,
                depth=5.0,
                subdivisions_width=2,
                subdivisions_depth=3,
                construction_node_id="floor-construction-node",
            ),
            primitives=(
                CubePrimitive(
                    name="polyCubeFreeze",
                    size=(2.0, 3.0, 4.0),
                    center=(0.25, -0.5, 2.0),
                    subdivisions_x=2,
                    subdivisions_y=3,
                    subdivisions_z=4,
                    construction_node_id="cube-construction-node",
                ),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="freeze")),
    )


def _composition(project):
    return project.rooms[0].primitive


def _flat(points) -> tuple[float, ...]:
    return tuple(float(value) for point in points for value in point)


def test_freeze_preserves_rotated_nonuniform_cube_recipe_identity_and_world_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import PlacedRoomPrimitive, primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        freeze_authored_room_composition_primitive_transform,
        set_authored_room_composition_primitive_dimensions,
        set_authored_room_composition_primitive_transform,
    )
    from src.core.modules.authored_room_primitives import CubePrimitive

    source = set_authored_room_composition_primitive_transform(
        _project(),
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
        translation=(3.25, -2.5, 0.75),
        rotation_degrees_z=37.0,
        scale=(1.4, 0.65, 1.25),
        pivot=(0.3, -0.2, 0.1),
    )
    source_primitive = _composition(source).primitives[0]
    assert isinstance(source_primitive, PlacedRoomPrimitive)
    source_recipe = source_primitive.primitive
    before_vertices = _flat(primitive_to_mesh(source_primitive).vertices)

    frozen = freeze_authored_room_composition_primitive_transform(
        source,
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
    )
    result = _composition(frozen).primitives[0]
    assert isinstance(result, PlacedRoomPrimitive)
    assert isinstance(result.primitive, CubePrimitive)
    assert result.primitive is source_recipe
    assert result.primitive.construction_node_id == "cube-construction-node"
    assert result.primitive.size == (2.0, 3.0, 4.0)
    assert (result.primitive.subdivisions_x, result.primitive.subdivisions_y, result.primitive.subdivisions_z) == (2, 3, 4)
    assert len(result.evaluation_transforms) == 1
    assert result.evaluation_transforms[0] == source_primitive.transform
    assert result.transform.translation == (0.0, 0.0, 0.0)
    assert result.transform.rotation_degrees_z == 0.0
    assert result.transform.scale == (1.0, 1.0, 1.0)
    assert result.transform.pivot == (0.0, 0.0, 0.0)
    assert _flat(primitive_to_mesh(result).vertices) == pytest.approx(before_vertices)
    assert _composition(frozen).metadata["freeze_transform_space"] == "retained_construction_recipe_evaluation_stages"
    assert _composition(frozen).metadata["freeze_transform_preserved_construction_recipe"] is True

    # The source project and its retained recipe remain untouched.
    assert source_primitive.transform.translation == (3.25, -2.5, 0.75)
    assert source_primitive.evaluation_transforms == ()
    assert source_recipe.size == (2.0, 3.0, 4.0)

    edited = set_authored_room_composition_primitive_dimensions(
        frozen,
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
        dimensions={"size_x": 5.0, "subdivisions_x": 5},
    )
    edited_primitive = _composition(edited).primitives[0]
    assert isinstance(edited_primitive, PlacedRoomPrimitive)
    assert isinstance(edited_primitive.primitive, CubePrimitive)
    assert edited_primitive.primitive.size == (5.0, 3.0, 4.0)
    assert edited_primitive.primitive.subdivisions_x == 5
    assert edited_primitive.primitive.construction_node_id == "cube-construction-node"
    assert edited_primitive.evaluation_transforms == result.evaluation_transforms


def test_repeat_freeze_appends_stages_and_round_trips_kmap_without_recipe_loss() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_composition import PlacedRoomPrimitive, primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        freeze_authored_room_composition_primitive_transform,
        set_authored_room_composition_primitive_transform,
    )
    from src.core.modules.authored_room_primitives import CubePrimitive

    first_edit = set_authored_room_composition_primitive_transform(
        _project(),
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
        translation=(2.0, 3.0, 1.0),
        rotation_degrees_z=25.0,
        scale=(1.2, 0.8, 1.1),
        pivot=(0.1, 0.2, 0.3),
    )
    first_frozen = freeze_authored_room_composition_primitive_transform(
        first_edit,
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
    )
    second_edit = set_authored_room_composition_primitive_transform(
        first_frozen,
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
        translation=(-1.0, 0.5, 2.25),
        rotation_degrees_z=-18.0,
        scale=(0.75, 1.3, 0.9),
        pivot=(-0.4, 0.25, 0.0),
    )
    before_second_freeze = _flat(primitive_to_mesh(_composition(second_edit).primitives[0]).vertices)
    twice_frozen = freeze_authored_room_composition_primitive_transform(
        second_edit,
        room_resref="freeze_room",
        primitive_name="polyCubeFreeze",
    )
    twice = _composition(twice_frozen).primitives[0]
    assert isinstance(twice, PlacedRoomPrimitive)
    assert isinstance(twice.primitive, CubePrimitive)
    assert twice.primitive.construction_node_id == "cube-construction-node"
    assert len(twice.evaluation_transforms) == 2
    assert _flat(primitive_to_mesh(twice).vertices) == pytest.approx(before_second_freeze)
    assert _composition(twice_frozen).metadata["freeze_transform_stage_count"] == 2

    payload = authored_project_to_kmap_payload(twice_frozen)
    recipe_payload = payload["rooms"][0]["primitive"]["primitives"][0]
    assert len(recipe_payload["evaluation_transforms"]) == 2
    assert recipe_payload["construction_node_id"] == "cube-construction-node"
    restored = authored_project_from_kmap_payload(payload)
    restored_primitive = _composition(restored).primitives[0]
    assert isinstance(restored_primitive, PlacedRoomPrimitive)
    assert isinstance(restored_primitive.primitive, CubePrimitive)
    assert restored_primitive.primitive.construction_node_id == "cube-construction-node"
    assert restored_primitive.evaluation_transforms == twice.evaluation_transforms
    assert restored_primitive.transform == twice.transform
    assert _flat(primitive_to_mesh(restored_primitive).vertices) == pytest.approx(before_second_freeze)


def test_floor_freeze_preserves_render_and_wok_geometry_through_kmap_roundtrip() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_room_composition import (
        PlacedRoomPrimitive,
        build_composition_wok,
        primitive_to_mesh,
        primitive_to_wok,
    )
    from src.core.modules.authored_room_operations import (
        freeze_authored_room_composition_primitive_transform,
        set_authored_room_composition_primitive_transform,
    )
    from src.core.modules.authored_room_primitives import FloorPrimitive

    edited = set_authored_room_composition_primitive_transform(
        _project(),
        room_resref="freeze_room",
        primitive_name="polyPlaneFreeze",
        translation=(-4.0, 2.0, 0.5),
        rotation_degrees_z=33.0,
        scale=(1.5, 0.7, 1.0),
        pivot=(0.75, -0.5, 0.0),
    )
    before_floor = _composition(edited).floor
    before_render = _flat(primitive_to_mesh(before_floor).vertices)
    before_wok = primitive_to_wok(before_floor)
    assert before_wok is not None
    before_wok_vertices = _flat(before_wok.verts)
    before_composition_wok = _flat(build_composition_wok(_composition(edited)).verts)

    frozen = freeze_authored_room_composition_primitive_transform(
        edited,
        room_resref="freeze_room",
        primitive_name="polyPlaneFreeze",
    )
    frozen_floor = _composition(frozen).floor
    assert isinstance(frozen_floor, PlacedRoomPrimitive)
    assert isinstance(frozen_floor.primitive, FloorPrimitive)
    assert frozen_floor.primitive.construction_node_id == "floor-construction-node"
    assert len(frozen_floor.evaluation_transforms) == 1
    assert _flat(primitive_to_mesh(frozen_floor).vertices) == pytest.approx(before_render)
    frozen_wok = primitive_to_wok(frozen_floor)
    assert frozen_wok is not None
    assert _flat(frozen_wok.verts) == pytest.approx(before_wok_vertices)
    assert _flat(build_composition_wok(_composition(frozen)).verts) == pytest.approx(before_composition_wok)

    restored = authored_project_from_kmap_payload(authored_project_to_kmap_payload(frozen))
    restored_floor = _composition(restored).floor
    assert isinstance(restored_floor, PlacedRoomPrimitive)
    assert isinstance(restored_floor.primitive, FloorPrimitive)
    assert restored_floor.primitive.construction_node_id == "floor-construction-node"
    assert restored_floor.evaluation_transforms == frozen_floor.evaluation_transforms
    restored_wok = primitive_to_wok(restored_floor)
    assert restored_wok is not None
    assert _flat(restored_wok.verts) == pytest.approx(before_wok_vertices)
