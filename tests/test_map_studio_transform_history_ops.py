from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    for rel in reversed(
        (
            "native/GhostRigger.Core.Scene/Python",
            "native/GhostRigger.Core.Resources/Python",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Rendering/Python",
            ".",
        )
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _named_primitive(project, name: str):
    composition = project.rooms[0].primitive
    def primitive_name(item) -> str:
        return str(getattr(item, "name", "") or getattr(getattr(item, "primitive", None), "name", "") or "")

    if primitive_name(composition.floor) == name:
        return composition.floor
    return next(item for item in composition.primitives if primitive_name(item) == name)


def _assert_vec3_rows_equal(left, right) -> None:
    assert len(left) == len(right)
    for left_row, right_row in zip(left, right):
        assert tuple(left_row) == pytest.approx(tuple(right_row), abs=1.0e-7)


def test_reset_transformations_restores_identity_but_keeps_pivot_and_intentionally_moves_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        reset_authored_room_composition_primitive_transform,
        set_authored_room_composition_primitive_transform,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grreset",
        game="K2",
    )
    name = "grreset_room01_ramp"
    transformed = set_authored_room_composition_primitive_transform(
        project,
        room_resref="grreset_room01",
        primitive_name=name,
        translation=(4.0, -2.0, 1.0),
        rotation_degrees_z=35.0,
        scale=(1.5, 0.75, 2.0),
        pivot=(0.25, -0.5, 0.125),
    )
    before_vertices = primitive_to_mesh(_named_primitive(transformed, name)).vertices

    reset = reset_authored_room_composition_primitive_transform(
        transformed,
        room_resref="grreset_room01",
        primitive_name=name,
    )
    result = _named_primitive(reset, name)
    after_vertices = primitive_to_mesh(result).vertices

    assert result.transform.translation == (0.0, 0.0, 0.0)
    assert result.transform.rotation_degrees_z == 0.0
    assert result.transform.scale == (1.0, 1.0, 1.0)
    assert result.transform.pivot == (0.25, -0.5, 0.125)
    assert before_vertices != after_vertices
    assert reset.rooms[0].primitive.metadata["reset_transform_space"] == (
        "primitive_local_intentionally_moves_geometry"
    )


def test_zero_pivot_compensates_translation_and_preserves_world_geometry_under_rotation_and_scale() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        set_authored_room_composition_primitive_transform,
        zero_authored_room_composition_primitive_pivot,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grzero",
        game="K1",
    )
    name = "grzero_room01_ramp"
    transformed = set_authored_room_composition_primitive_transform(
        project,
        room_resref="grzero_room01",
        primitive_name=name,
        translation=(2.5, -1.25, 0.75),
        rotation_degrees_z=47.0,
        scale=(1.75, 0.65, 1.2),
        pivot=(0.4, -0.3, 0.2),
    )
    before = _named_primitive(transformed, name)
    before_vertices = primitive_to_mesh(before).vertices

    zeroed = zero_authored_room_composition_primitive_pivot(
        transformed,
        room_resref="grzero_room01",
        primitive_name=name,
    )
    after = _named_primitive(zeroed, name)
    after_vertices = primitive_to_mesh(after).vertices

    assert after.transform.pivot == (0.0, 0.0, 0.0)
    assert after.transform.rotation_degrees_z == before.transform.rotation_degrees_z
    assert after.transform.scale == before.transform.scale
    assert after.transform.translation != before.transform.translation
    _assert_vec3_rows_equal(before_vertices, after_vertices)
    assert zeroed.rooms[0].primitive.metadata["zero_pivot_space"] == (
        "primitive_local_preserve_world_geometry"
    )


def test_freeze_transform_retains_rotated_primitive_recipe_and_preserves_visible_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_composition import primitive_to_mesh
    from src.core.modules.authored_room_operations import (
        freeze_authored_room_composition_primitive_transform,
        set_authored_room_composition_primitive_transform,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grfreeze",
        game="K2",
    )
    name = "grfreeze_room01_ramp"
    transformed = set_authored_room_composition_primitive_transform(
        project,
        room_resref="grfreeze_room01",
        primitive_name=name,
        translation=(3.0, -2.0, 0.75),
        rotation_degrees_z=37.0,
        scale=(1.4, 0.65, 1.25),
        pivot=(0.3, -0.2, 0.1),
    )
    before_vertices = primitive_to_mesh(_named_primitive(transformed, name)).vertices

    frozen = freeze_authored_room_composition_primitive_transform(
        transformed,
        room_resref="grfreeze_room01",
        primitive_name=name,
    )
    result = _named_primitive(frozen, name)
    after_vertices = primitive_to_mesh(result).vertices

    assert result.transform.translation == (0.0, 0.0, 0.0)
    assert result.transform.rotation_degrees_z == 0.0
    assert result.transform.scale == (1.0, 1.0, 1.0)
    assert result.transform.pivot == (0.0, 0.0, 0.0)
    assert type(result.primitive) is type(_named_primitive(transformed, name).primitive)
    assert len(result.evaluation_transforms) == 1
    _assert_vec3_rows_equal(before_vertices, after_vertices)
    assert frozen.rooms[0].primitive.metadata["freeze_transform_space"] == (
        "retained_construction_recipe_evaluation_stages"
    )
    assert frozen.rooms[0].primitive.metadata["freeze_transform_preserved_construction_recipe"] is True


def test_delete_history_on_imported_mesh_preserves_geometry_wok_and_export_provenance_through_kmap() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_room_operations import delete_authored_room_composition_primitive_history
    from src.core.modules.module_format import WOKData, WOKFace

    surface = ImportedMeshSurface(
        name="render",
        texture="LTS_wall01",
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),
        faces=((0, 1, 2),),
        uvs=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 3,
    )
    wok = WOKData(
        name="histroom",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4)],
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="histroom",
        surfaces=(surface,),
        source_model="histroom",
        game="K2",
        wok=wok,
        metadata={
            "source": "stock_module_import",
            "source_runtime_graph": {"animation_count": 2, "light_count": 3},
            "topology_policy": "preserve_imported_channels",
            "custom_export_token": "keep-me",
            "last_topology_edit": {"operation": "edge_bevel", "segments": 3},
            "construction_history": [{"operation": "import"}],
            "live_operator_width": 0.25,
            "preview_state_mesh": "discard-me",
        },
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="histmod", game="K2", tag="histmod"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="histroom",
                primitive=primitive,
                visible_rooms=("histroom",),
                metadata={"source": "stock_module_import"},
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="histmod")),
    )

    updated = delete_authored_room_composition_primitive_history(
        project,
        room_resref="histroom",
        primitive_name="histroom",
    )
    round_tripped = authored_project_from_kmap_payload(authored_project_to_kmap_payload(updated))
    result = round_tripped.rooms[0].primitive

    assert result.surfaces == primitive.surfaces
    assert result.wok is not None
    assert result.wok.verts == primitive.wok.verts
    assert [(face.v1, face.v2, face.v3, face.surface) for face in result.wok.faces] == [
        (0, 1, 2, 4)
    ]
    assert result.source_model == "histroom"
    assert result.game == "K2"
    assert result.metadata["source"] == "stock_module_import"
    assert result.metadata["source_runtime_graph"] == {"animation_count": 2, "light_count": 3}
    assert result.metadata["topology_policy"] == "preserve_imported_channels"
    assert result.metadata["custom_export_token"] == "keep-me"
    assert "last_topology_edit" not in result.metadata
    assert "construction_history" not in result.metadata
    assert "live_operator_width" not in result.metadata
    assert "preview_state_mesh" not in result.metadata
    assert set(updated.rooms[0].metadata["delete_history_removed_keys"]) == {
        "construction_history",
        "last_topology_edit",
        "live_operator_width",
        "preview_state_mesh",
    }


def test_controller_transform_history_commands_each_create_one_undo_record() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grundo")
    name = "grundo_room01_ramp"
    controller.set_authored_room_primitive_transform(
        room_resref="grundo_room01",
        primitive_name=name,
        translation=(2.0, 1.0, 0.5),
        rotation_degrees_z=20.0,
        scale=(1.2, 0.8, 1.5),
        pivot=(0.25, 0.1, 0.0),
    )

    commands = (
        (controller.reset_authored_room_primitive_transform, "Reset transformations"),
        (controller.zero_authored_room_primitive_pivot, "Zero pivot"),
        (controller.delete_authored_room_primitive_history, "Delete history"),
    )
    for command, label in commands:
        controller.command_history.clear()
        command(room_resref="grundo_room01", primitive_name=name)
        assert len(controller.command_history.undo_stack) == 1
        assert controller.command_history.undo_label == f"{label} {name}"
