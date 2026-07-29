from __future__ import annotations

import copy
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


def _terrain_stroke_project(resolution: int = 9, *, patterned: bool = False):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import create_terrain_room_project
    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive

    heights = tuple(
        tuple(
            float(((row * 7) + (column * 3)) % 11) * 0.05 if patterned else 0.0
            for column in range(resolution)
        )
        for row in range(resolution)
    )
    room_resref = "grstroke_room01"
    terrain = TerrainHeightfieldPrimitive(
        room_resref=room_resref,
        heights=heights,
        width=float(resolution - 1),
        depth=float(resolution - 1),
    )
    placements = AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref=room_resref))
    return create_terrain_room_project(
        module_root="grstroke",
        game="K2",
        display_name="Terrain Stroke Fixture",
        terrain=terrain,
        placements=placements,
    )


def test_t2907_terrain_room_drag_snaps_matching_edges_and_builds_reciprocal_wok_portal() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_layout import (
        connect_authored_room_drag_snap,
        preview_authored_room_drag_snap,
    )
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredRoomSpec, create_terrain_room_project
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive

    target = TerrainHeightfieldPrimitive(
        room_resref="grterr_target",
        width=8.0,
        depth=8.0,
        heights=(
            (0.0, 0.0, 0.0),
            (0.2, 0.2, 0.2),
            (0.4, 0.4, 0.4),
        ),
    )
    source = TerrainHeightfieldPrimitive(
        room_resref="grterr_source",
        width=8.0,
        depth=8.0,
        heights=(
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
            (1.0, 1.0, 1.0),
        ),
    )
    project = create_terrain_room_project(
        module_root="grterr",
        game="K1",
        display_name="Terrain seam fixture",
        terrain=target,
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grterr")),
    )
    project = replace(
        project,
        rooms=project.rooms
        + (
            AuthoredRoomSpec(
                room_resref=source.room_resref,
                primitive=source,
                position=(9.0, 0.0, 0.0),
                visible_rooms=(source.room_resref,),
                metadata={"primitive": "terrain_heightfield"},
            ),
        ),
    )

    preview = preview_authored_room_drag_snap(
        project,
        source_room_resref=source.room_resref,
        world_delta=(-0.6, 0.0, 0.0),
        snap_distance=1.0,
    )
    assert preview.magnet_snapped is True
    assert preview.snap_kind == "terrain_seam"
    assert preview.source_opening_name == "terrain_left"
    assert preview.target_label == "grterr_target — right terrain edge"
    assert preview.position == (8.0, 0.0, 0.0)

    update = connect_authored_room_drag_snap(project, preview)
    connected_source = next(
        room for room in update.project.rooms if room.normalised_resref() == source.room_resref
    )
    assert connected_source.position == (8.0, 0.0, 0.0)
    # Source left edge is welded to the target right edge in world Z.
    assert tuple(row[0] for row in connected_source.primitive.heights) == (0.0, 0.2, 0.4)
    assert update.project.extra["last_walkmesh_build"]["auto_generated"] is True
    assert update.project.extra["last_walkmesh_build"]["operation"] == "connect_terrain_edges"

    walkmesh = compile_authored_room_connection_walkmeshes(update.project)
    assert walkmesh.ready is True
    assert len(walkmesh.portals) == 1
    assert walkmesh.portals[0].midpoint_gap <= 1.0e-7


def test_t2907_map_studio_adapts_to_portable_integrated_graphics() -> None:
    _install_native_payload_paths()

    from src.core.modules.map_studio_modeling_tools import (
        map_studio_viewport_performance_policy,
    )

    portable = map_studio_viewport_performance_policy(
        logical_threads=8,
        gpu_adapter="Intel Iris Xe Graphics",
    )
    assert portable.profile_key == "portable"
    assert portable.target_fps == 30
    assert portable.interactive_render_scale == 0.72
    assert portable.idle_render_scale == 1.0
    assert portable.hover_interval_ms == 33
    assert portable.texture_memory_budget_mb == 256

    quality = map_studio_viewport_performance_policy(
        "quality",
        logical_threads=32,
        gpu_adapter="Discrete GPU",
    )
    assert quality.profile_key == "quality"
    assert quality.target_fps == 60
    assert quality.interactive_render_scale == 1.0


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


def test_t2907_carved_terrain_hole_serializes_inner_perimeter_and_complete_aabb() -> None:
    _install_native_payload_paths()
    import struct

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        build_terrain_mesh,
        build_terrain_wok,
        carve_terrain_hole,
    )
    from src.core.modules.module_format import WOKData
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grdev01_hole",
        width=8.0,
        depth=8.0,
        heights=tuple(tuple(0.0 for _column in range(5)) for _row in range(5)),
    )
    carved = carve_terrain_hole(terrain, row_index=1, column_index=1)
    mesh = build_terrain_mesh(carved)
    wok = build_terrain_wok(carved)
    raw = wok.to_bytes()
    fingerprint, report = inspect_raw_wok_structure(carved.room_resref, raw)

    assert len(mesh.faces) == 30
    assert len(wok.faces) == 30
    assert struct.unpack_from("<I", raw, 128)[0] == 2
    assert fingerprint.perimeter_count == 2
    assert fingerprint.closed_perimeter_count == 2
    assert fingerprint.aabb_count == 59
    assert fingerprint.aabb_leaf_count == 30
    assert fingerprint.aabb_covered_face_count == 30
    assert fingerprint.aabb_missing_face_count == 0
    assert not report.has_errors
    assert len(WOKData.from_bytes(raw).faces) == 30

    boundary_notch = carve_terrain_hole(terrain, row_index=0, column_index=1)
    assert struct.unpack_from("<I", build_terrain_wok(boundary_notch).to_bytes(), 128)[0] == 1


def test_t2907_terrain_holes_reject_malformed_and_out_of_range_cells() -> None:
    _install_native_payload_paths()
    import pytest

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        build_terrain_wok,
        carve_terrain_hole,
        normalised_terrain_holes,
        validate_terrain_heightfield_primitive,
    )

    heights = tuple(tuple(0.0 for _column in range(4)) for _row in range(4))
    malformed = TerrainHeightfieldPrimitive(
        room_resref="grdev01_bad_hole",
        heights=heights,
        holes=((1, 1), ("2", 1), (0, 1, 2), (-1, 0)),
    )
    validation = validate_terrain_heightfield_primitive(malformed)

    assert validation.ok is False
    assert any("must use integer" in issue for issue in validation.blocking_issues)
    assert any("two-integer" in issue for issue in validation.blocking_issues)
    assert any("outside the valid cell range" in issue for issue in validation.blocking_issues)
    with pytest.raises(ValueError, match="outside the valid cell range"):
        build_terrain_wok(malformed)
    with pytest.raises(ValueError, match="must use integer"):
        normalised_terrain_holes(((1.5, 1),), row_count=4, column_count=4)
    with pytest.raises(ValueError, match="outside the valid cell range"):
        carve_terrain_hole(
            TerrainHeightfieldPrimitive(room_resref="grdev01_edge", heights=heights),
            row_index=3,
            column_index=0,
        )
    with pytest.raises(ValueError, match="must be integers"):
        carve_terrain_hole(
            TerrainHeightfieldPrimitive(room_resref="grdev01_fraction", heights=heights),
            row_index=1.25,
            column_index=1,
        )


def test_t2907_contiguous_diagonal_and_notched_holes_keep_one_walkable_component() -> None:
    _install_native_payload_paths()
    import struct

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        build_terrain_wok,
        validate_terrain_heightfield_primitive,
    )

    heights = tuple(tuple(0.0 for _column in range(6)) for _row in range(6))
    patterns = {
        "contiguous": ((2, 2), (2, 3)),
        "diagonal": ((1, 1), (2, 2)),
        "notched": ((0, 1), (0, 2)),
    }
    perimeter_counts: dict[str, int] = {}
    for label, holes in patterns.items():
        terrain = TerrainHeightfieldPrimitive(
            room_resref=f"grdev01_{label}",
            heights=heights,
            holes=holes,
        )
        validation = validate_terrain_heightfield_primitive(terrain)
        wok = build_terrain_wok(terrain)
        raw = wok.to_bytes()

        assert validation.ok is True
        assert validation.walkable_component_count == 1
        assert wok.walkable_face_count() == (25 - len(holes)) * 2
        perimeter_counts[label] = struct.unpack_from("<I", raw, 128)[0]

    assert perimeter_counts["contiguous"] == 2
    # Diagonal holes meet at one vertex.  The perimeter writer may serialize
    # that point-touching interior boundary as one closed loop or two; it must
    # never be rejected as a disconnected walkable floor.
    assert perimeter_counts["diagonal"] >= 2
    assert perimeter_counts["notched"] == 1


def test_t2907_terrain_carve_rejects_disconnected_islands_without_explicit_review() -> None:
    _install_native_payload_paths()
    import pytest

    from src.core.modules.authored_terrain_builder import (
        TerrainHeightfieldPrimitive,
        build_terrain_wok,
        carve_terrain_hole,
        compile_terrain_room_geometry,
        validate_terrain_heightfield_primitive,
    )

    heights = tuple(tuple(0.0 for _column in range(5)) for _row in range(5))
    nearly_split = TerrainHeightfieldPrimitive(
        room_resref="grdev01_split",
        heights=heights,
        holes=((0, 1), (1, 1), (2, 1)),
    )
    with pytest.raises(ValueError, match="2 disconnected walkable WOK islands"):
        carve_terrain_hole(nearly_split, row_index=3, column_index=1)

    reviewed = carve_terrain_hole(
        nearly_split,
        row_index=3,
        column_index=1,
        allow_disconnected_walkmesh_islands=True,
    )
    validation = validate_terrain_heightfield_primitive(reviewed)
    geometry = compile_terrain_room_geometry(reviewed)

    assert reviewed.metadata["allow_disconnected_walkmesh_islands"] is True
    assert validation.ok is True
    assert validation.walkable_component_count == 2
    assert any("explicitly reviewed" in warning for warning in validation.warnings)
    assert geometry.metadata["walkable_component_count"] == 2
    assert geometry.metadata["allow_disconnected_walkmesh_islands"] is True
    assert len(build_terrain_wok(reviewed).faces) == 24


def test_t2907_terrain_adjacency_rejects_third_owner_nonmanifold_edge() -> None:
    _install_native_payload_paths()
    import pytest

    from src.core.modules.authored_terrain_builder import _assign_wok_adjacency
    from src.core.modules.module_format import WOKFace

    faces = [
        WOKFace(0, 1, 2, surface=4),
        WOKFace(1, 0, 3, surface=4),
        WOKFace(0, 1, 4, surface=4),
    ]

    with pytest.raises(ValueError, match="non-manifold"):
        _assign_wok_adjacency(faces)


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
    assert with_boundaries.wok is geometry.wok
    assert with_boundaries.wok.walkable_face_count() == 8
    assert with_boundaries.wok.non_walk_face_count() == 0
    assert with_boundaries.metadata["walkmesh_boundary_wall_faces"] == 16
    assert with_boundaries.metadata["walkmesh_boundary_helper_faces"] == 16
    assert with_boundaries.metadata["walkmesh_game_wok_face_policy"] == "floor_only"


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


def test_t2907_terrain_brush_hardness_controls_smooth_falloff() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, apply_terrain_brush_stroke

    terrain = TerrainHeightfieldPrimitive(
        room_resref="grfalloff_room01",
        heights=tuple(tuple(0.0 for _column in range(7)) for _row in range(7)),
    )
    soft = apply_terrain_brush_stroke(
        terrain,
        brush="raise",
        points=((3, 3, 1.0),),
        radius=2,
        delta=1.0,
        falloff_hardness=0.0,
    )
    hard = apply_terrain_brush_stroke(
        terrain,
        brush="raise",
        points=((3, 3, 1.0),),
        radius=2,
        delta=1.0,
        falloff_hardness=1.0,
    )

    assert soft.heights[3][3] == 1.0
    assert 0.0 < soft.heights[3][5] < hard.heights[3][5]
    assert hard.heights[3][5] == 1.0
    assert soft.metadata["last_brush_falloff_hardness"] == 0.0
    assert hard.metadata["last_brush_falloff_hardness"] == 1.0


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


def test_t2907_terrain_stroke_session_decodes_once_and_serializes_once_at_commit() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.map_studio_terrain_sculpt_session import begin_terrain_sculpt_stroke

    payload = authored_project_to_kmap_payload(_terrain_stroke_project(65))
    source_payload = copy.deepcopy(payload)
    session = begin_terrain_sculpt_stroke(payload, room_resref="grstroke_room01")
    assert session.decode_count == 1

    for column in (28, 30, 32, 34, 36):
        frame = session.apply_frame(
            brush="raise",
            points=((32, column, 1.0),),
            delta=0.2,
            radius=2,
            falloff_hardness=0.65,
        )
        assert frame.applied is True
        assert frame.project_serialized is False
    assert session.frame_count == 5
    assert session.serialization_count == 0
    assert payload == source_payload

    committed = session.commit()
    assert committed.decode_count == 1
    assert committed.serialization_count == 1
    decoded = authored_project_from_kmap_payload(committed.payload)
    assert decoded.rooms[0].primitive.heights[32][32] > 0.0
    assert decoded.rooms[0].primitive.metadata["terrain_stroke_committed"] is True
    assert session.commit() is committed
    assert session.serialization_count == 1


def test_t2907_terrain_stroke_session_tracks_dirty_rectangle_and_dependency_halo() -> None:
    _install_native_payload_paths()
    from src.core.modules.map_studio_terrain_sculpt_session import MapStudioTerrainSculptStrokeSession

    session = MapStudioTerrainSculptStrokeSession.from_project(
        _terrain_stroke_project(9),
        room_resref="grstroke_room01",
    )
    result = session.apply_frame(
        brush="raise",
        points=((4, 4, 1.0),),
        delta=0.5,
        radius=1,
        falloff_hardness=1.0,
    )
    assert result.dirty_region.to_metadata() == {
        "min_row": 3,
        "max_row": 5,
        "min_column": 3,
        "max_column": 5,
        "changed_sample_count": 5,
        "covered_sample_count": 9,
        "empty": False,
    }
    assert result.dirty_region_with_halo.to_metadata() == {
        "min_row": 2,
        "max_row": 6,
        "min_column": 2,
        "max_column": 6,
        "changed_sample_count": 5,
        "covered_sample_count": 25,
        "empty": False,
    }
    patch = session.dirty_height_patch(result.dirty_region_with_halo)
    assert len(patch) == 5
    assert all(len(row) == 5 for row in patch)


def test_t2907_terrain_stroke_session_matches_brush_math_and_stays_resolution_local() -> None:
    _install_native_payload_paths()
    from src.core.modules.authored_terrain_builder import apply_terrain_brush_stroke
    from src.core.modules.map_studio_terrain_sculpt_session import MapStudioTerrainSculptStrokeSession

    for brush, kwargs in (
        ("raise", {"delta": 0.2, "radius": 2, "strength": 0.7}),
        ("smooth", {"delta": 0.1, "radius": 2, "strength": 0.65, "iterations": 2}),
        ("erode", {"delta": 0.04, "radius": 2, "strength": 0.8, "iterations": 2}),
    ):
        project = _terrain_stroke_project(13, patterned=True)
        expected = apply_terrain_brush_stroke(
            project.rooms[0].primitive,
            brush=brush,
            points=((6, 6, 1.0), (6, 7, 0.8)),
            falloff_hardness=0.55,
            **kwargs,
        )
        session = MapStudioTerrainSculptStrokeSession.from_project(
            project,
            room_resref="grstroke_room01",
        )
        session.apply_frame(
            brush=brush,
            points=((6, 6, 1.0), (6, 7, 0.8)),
            falloff_hardness=0.55,
            **kwargs,
        )
        assert session.commit().primitive.heights == expected.heights

    timings: dict[int, float] = {}
    changed_counts: dict[int, int] = {}
    for resolution in (17, 65, 129):
        session = MapStudioTerrainSculptStrokeSession.from_project(
            _terrain_stroke_project(resolution),
            room_resref="grstroke_room01",
        )
        center = resolution // 2
        session.apply_frame(brush="raise", points=((center, center),), delta=0.1, radius=2, force=True)
        result = session.apply_frame(
            brush="raise",
            points=((center, center + 1),),
            delta=0.1,
            radius=2,
            force=True,
        )
        timings[resolution] = result.elapsed_ms
        changed_counts[resolution] = len(result.changed_flat_indices)
        assert session.serialization_count == 0

    assert changed_counts == {17: 13, 65: 13, 129: 13}
    # The live brush contract is a 4 ms dirty-buffer budget.  Resolution must
    # not push a fixed-radius local stroke back onto the old whole-grid path.
    assert max(timings.values()) < 4.0
