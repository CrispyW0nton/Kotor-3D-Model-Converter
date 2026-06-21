from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _placements():
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint

    return AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grdev01"))


def test_t2907_flat_terrain_heightfield_builds_mesh_and_walkable_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        analyse_terrain_slopes,
        compile_terrain_room_geometry,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grdev01_terr01",
        width=8.0,
        depth=6.0,
        heights=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        floor_surface_id="grass",
        material=PrimitiveMaterial(texture="LMA_grass01"),
    )

    report = analyse_terrain_slopes(terrain)
    geometry = compile_terrain_room_geometry(terrain)

    assert report.triangle_count == 8
    assert report.walkable_triangle_count == 8
    assert report.non_walk_triangle_count == 0
    assert geometry.metadata["primitive"] == "terrain_heightfield"
    assert geometry.room_mesh.name == "grdev01_terr01_terrain"
    assert geometry.room_mesh.texture == "LMA_grass01"
    assert len(geometry.room_mesh.vertices) == 9
    assert len(geometry.room_mesh.faces) == 8
    assert len(geometry.wok.verts) == 9
    assert len(geometry.wok.faces) == 8
    assert geometry.wok.walkable_face_count() == 8
    assert geometry.wok.non_walk_face_count() == 0
    assert len(geometry.wok.boundary_edges()) == 8


def test_t2907_steep_terrain_triangles_export_as_non_walk() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        analyse_terrain_slopes,
        compile_terrain_room_geometry,
        validate_terrain_heightfield_primitive,
    )

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grdev01_cliff",
        width=2.0,
        depth=2.0,
        heights=((0.0, 0.0), (3.0, 3.0)),
        max_walkable_slope_degrees=30.0,
    )

    validation = validate_terrain_heightfield_primitive(terrain)
    report = analyse_terrain_slopes(terrain)
    geometry = compile_terrain_room_geometry(terrain)

    assert validation.ok is True
    assert validation.warnings
    assert report.non_walk_triangle_count == 2
    assert geometry.metadata["non_walk_triangle_count"] == 2
    assert geometry.wok.walkable_face_count() == 0
    assert geometry.wok.non_walk_face_count() == 2
    assert {face.surface for face in geometry.wok.faces} == {7}


def test_t2907_terrain_project_compiles_through_authored_room_spec() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import (
        compile_authored_room_spec,
        create_terrain_room_project,
        validate_authored_module_project,
    )
    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive
    from src.core.modules.authored_walkmesh_boundaries import apply_authored_walkmesh_boundary_policy_to_geometry

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grdev01_terr01",
        width=6.0,
        depth=6.0,
        heights=((0.0, 0.0, 0.0), (0.0, 0.25, 0.0), (0.0, 0.0, 0.0)),
        max_walkable_slope_degrees=45.0,
    )
    project = create_terrain_room_project(
        module_root="grdev01",
        game="K1",
        display_name="GhostRigger Terrain Dev Room",
        terrain=terrain,
        placements=_placements(),
    )

    validation = validate_authored_module_project(project)
    geometry = compile_authored_room_spec(project.rooms[0])
    with_boundaries = apply_authored_walkmesh_boundary_policy_to_geometry(geometry, wall_height=3.0)

    assert validation.ok is True
    assert project.rooms[0].metadata["primitive"] == "terrain_heightfield"
    assert geometry.metadata["source"] == "src.core.modules.authored_terrain_builder"
    assert geometry.wok.walkable_face_count() == 8
    assert with_boundaries.wok.non_walk_face_count() == 16
    assert with_boundaries.metadata["walkmesh_boundary_wall_faces"] == 16


def test_t2908_terrain_heightfield_sample_edit_operations() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        flatten_terrain_heightfield,
        offset_terrain_heightfield_samples,
        set_terrain_heightfield_sample,
        smooth_terrain_heightfield,
        terrain_height_range,
    )

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grterr_room01",
        heights=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    )

    raised = set_terrain_heightfield_sample(terrain, row_index=1, column_index=1, height=1.0)
    brushed = offset_terrain_heightfield_samples(raised, row_index=1, column_index=1, delta=0.5, radius=1)
    smoothed = smooth_terrain_heightfield(brushed, iterations=1, strength=0.5)
    flattened = flatten_terrain_heightfield(smoothed, height=0.25)

    assert raised.heights[1][1] == 1.0
    assert brushed.heights[1][1] == 1.5
    assert brushed.metadata["last_changed_sample_count"] == 5
    assert smoothed.heights[0] == brushed.heights[0]
    assert smoothed.heights[1][1] < brushed.heights[1][1]
    assert flattened.heights == ((0.25, 0.25, 0.25), (0.25, 0.25, 0.25), (0.25, 0.25, 0.25))
    assert terrain_height_range(flattened) == (0.25, 0.25)


def test_t2603_terrain_erase_brush_resets_local_dirty_region() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, apply_terrain_brush_stroke

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grerase_room01",
        heights=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.0)),
    )

    erased = apply_terrain_brush_stroke(
        terrain,
        brush="erase",
        points=((1, 1, 1.0),),
        radius=0,
        height=0.0,
        strength=1.0,
    )

    assert erased.heights[1][1] == 0.0
    assert erased.heights[0][0] == 0.0
    assert erased.metadata["last_brush"] == "erase"
    assert erased.metadata["last_dirty_region"] == {
        "min_row": 1,
        "max_row": 1,
        "min_column": 1,
        "max_column": 1,
        "changed_sample_count": 1,
    }
    assert erased.metadata["dirty_region_only"] is True
    assert erased.metadata["defer_full_rebuild_until_stroke_end"] is True


def test_t2603_terrain_slope_brush_creates_controlled_local_grade() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, apply_terrain_brush_stroke

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grslope_room01",
        heights=tuple(tuple(0.0 for _column in range(5)) for _row in range(5)),
    )

    sloped = apply_terrain_brush_stroke(
        terrain,
        brush="slope",
        points=((0, 0, 1.0), (2, 2, 1.0), (4, 4, 1.0)),
        radius=0,
        height=1.0,
        strength=1.0,
    )

    assert sloped.heights[0][0] == 0.0
    assert round(sloped.heights[2][2], 6) == 0.5
    assert sloped.heights[4][4] == 1.0
    assert sloped.metadata["last_brush"] == "slope"
    assert sloped.metadata["last_dirty_region"] == {
        "min_row": 0,
        "max_row": 4,
        "min_column": 0,
        "max_column": 4,
        "changed_sample_count": 3,
    }
    assert sloped.metadata["last_brush_slope_report"]["walkable_triangle_count"] > 0
    assert sloped.metadata["dirty_region_only"] is True
    assert sloped.metadata["defer_full_rebuild_until_stroke_end"] is True


def test_t2603_terrain_brush_symmetry_mirrors_sample_edits() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, apply_terrain_brush_stroke

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grsym_room01",
        heights=tuple(tuple(0.0 for _column in range(5)) for _row in range(5)),
    )

    mirrored = apply_terrain_brush_stroke(
        terrain,
        brush="raise",
        points=((1, 0, 1.0),),
        radius=0,
        delta=0.25,
        strength=1.0,
        symmetry_axis="column",
    )

    assert mirrored.heights[1][0] == 0.25
    assert mirrored.heights[1][4] == 0.25
    assert mirrored.heights[1][2] == 0.0
    assert mirrored.metadata["last_brush_symmetry_axis"] == "column"
    assert mirrored.metadata["last_input_stroke_point_count"] == 1
    assert mirrored.metadata["last_stroke_point_count"] == 2
    assert mirrored.metadata["last_dirty_region"] == {
        "min_row": 1,
        "max_row": 1,
        "min_column": 0,
        "max_column": 4,
        "changed_sample_count": 2,
    }
    assert mirrored.metadata["last_brush_performance"]["sample_point_count"] == 2
    assert mirrored.metadata["dirty_region_only"] is True


def test_t2907_terrain_shape_presets_create_readable_heightfields() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        apply_terrain_shape_preset,
        available_terrain_shape_presets,
        compile_terrain_room_geometry,
    )

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grshape_room01",
        width=8.0,
        depth=8.0,
        heights=tuple(tuple(0.0 for _column in range(5)) for _row in range(5)),
        max_walkable_slope_degrees=45.0,
    )

    preset_ids = {preset.preset_id for preset in available_terrain_shape_presets()}
    mound = apply_terrain_shape_preset(terrain, preset_id="gentle_mound", height=0.8)
    ramp = apply_terrain_shape_preset(terrain, preset_id="ramp", height=0.6)
    terraces = apply_terrain_shape_preset(terrain, preset_id="terraces", height=0.9)
    geometry = compile_terrain_room_geometry(mound)

    assert {"flat", "gentle_mound", "shallow_bowl", "ridge", "ramp", "terraces"} <= preset_ids
    assert mound.heights[2][2] > mound.heights[0][0]
    assert mound.metadata["last_shape_preset_id"] == "gentle_mound"
    assert ramp.heights[0][0] < ramp.heights[-1][0]
    assert len({round(value, 3) for row in terraces.heights for value in row}) >= 3
    assert geometry.wok.walkable_face_count() > 0
