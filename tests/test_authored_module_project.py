from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
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


def _placements():
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint

    return AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grdev01"))


def test_t2612_floor_plan_room_project_compiles_through_room_spec() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import (
        compile_authored_room_spec,
        create_floor_plan_room_project,
        validate_authored_module_project,
    )
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    floor_plan = FloorPlanRoomPrimitive(
        room_resref="grdev01_room01",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        material=PrimitiveMaterial(texture="CM_Baremetal"),
    )
    project = create_floor_plan_room_project(
        module_root="grdev01",
        game="K1",
        display_name="GhostRigger Dev Test",
        floor_plan=floor_plan,
        placements=_placements(),
    )

    validation = validate_authored_module_project(project)
    geometry = compile_authored_room_spec(project.rooms[0])

    assert validation.ok
    assert project.rooms[0].metadata["primitive"] == "floor_plan_extrusion"
    assert geometry.metadata["primitive"] == "floor_plan_extrusion"
    assert geometry.room_mesh.name == "grdev01_room01_floor"
    assert geometry.room_mesh.texture == "CM_Baremetal"
    assert len(geometry.helper_meshes) == 4
    assert geometry.wok.walkable_face_count() == 2


def test_t2612_project_validation_blocks_invalid_floor_plan_room() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec, validate_authored_module_project
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grdev01_room01",
                primitive=FloorPlanRoomPrimitive(
                    room_resref="grdev01_room01",
                    points=((0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)),
                ),
            ),
        ),
        placements=_placements(),
    )

    validation = validate_authored_module_project(project)

    assert not validation.ok
    assert any("convex footprints only" in issue for issue in validation.blocking_issues)


def test_t2612_rectangular_room_spec_still_compiles_for_smoke_path() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import AuthoredRoomSpec, compile_authored_room_spec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    room = AuthoredRoomSpec(
        room_resref="grdev01_room01",
        primitive=RectangularRoomPrimitive(room_resref="grdev01_room01", width=10.0, depth=8.0),
    )

    geometry = compile_authored_room_spec(room)

    assert geometry.room_resref == "grdev01_room01"
    assert geometry.metadata["primitive"] == "rectangular_room"
    assert geometry.wok.walkable_face_count() == 2


def test_t2633_project_validation_blocks_unsafe_resrefs_before_truncation() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec, validate_authored_module_project
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="this_module_name_is_far_too_long"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="bad room",
                primitive=RectangularRoomPrimitive(room_resref="bad room"),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="entry/area")),
    )

    validation = validate_authored_module_project(project)

    assert validation.ok is False
    assert any("this_module_name_is_far_too_long" in issue and "16 characters or fewer" in issue for issue in validation.blocking_issues)
    assert any("bad room" in issue and "letters, numbers, and underscores" in issue for issue in validation.blocking_issues)
    assert any("entry/area" in issue and "letters, numbers, and underscores" in issue for issue in validation.blocking_issues)


def test_t2667_composition_room_project_compiles_walkable_primitives() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import (
        compile_authored_room_spec,
        create_composition_room_project,
        validate_authored_module_project,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, AuthoredPlaceableInstance, ModuleEntryPoint
    from src.core.modules.authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive, PrimitiveTransform
    from src.core.modules.authored_room_primitives import ArchPrimitive, FloorPrimitive, RampPrimitive, StairsPrimitive

    composition = AuthoredRoomComposition(
        room_resref="grdev01_room01",
        floor=FloorPrimitive(name="grdev01_floor", width=10.0, depth=10.0, surface_id="stone"),
        primitives=(
            PlacedRoomPrimitive(
                primitive=RampPrimitive(name="grdev01_ramp", width=2.0, length=3.0, height=1.0, surface_id="metal"),
                transform=PrimitiveTransform(translation=(2.0, 0.0, 0.0), rotation_degrees_z=90.0),
            ),
            StairsPrimitive(name="grdev01_steps", width=2.0, depth=3.0, height=1.0, steps=4, surface_id="stone"),
            ArchPrimitive(name="grdev01_arch", width=2.25, height=3.0, frame_thickness=0.25),
        ),
    )
    project = create_composition_room_project(
        module_root="grdev01",
        game="K1",
        display_name="GhostRigger Composition Dev Room",
        composition=composition,
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdev01", position=(0.0, -3.0, 0.0)),
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="plc_bench",
                    tag="grdev01_test_placeable",
                    position=(1.0, 1.0, 0.0),
                ),
            ),
        ),
    )

    validation = validate_authored_module_project(project)
    geometry = compile_authored_room_spec(project.rooms[0])

    assert validation.ok is True
    assert project.rooms[0].metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive"] == "authored_room_composition"
    assert geometry.metadata["primitive_count"] == 3
    assert geometry.metadata["walkmesh_primitive_count"] == 2
    assert geometry.metadata["transformed_primitive_count"] == 1
    assert geometry.wok.walkable_face_count() == 6
    assert [face.surface for face in geometry.wok.faces] == [4, 4, 10, 10, 4, 4]
    assert {mesh.name for mesh in geometry.helper_meshes} == {"grdev01_ramp", "grdev01_steps", "grdev01_arch"}
