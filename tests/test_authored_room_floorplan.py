from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Resources.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene.Walkmesh/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2611_compiles_rectangle_floor_plan_to_room_geometry() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    primitive = FloorPlanRoomPrimitive(
        room_resref="grdev_poly",
        points=((-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)),
        wall_height=2.5,
        floor_surface_id="metal",
        material=PrimitiveMaterial(texture="CM_Baremetal"),
    )

    geometry = compile_floor_plan_room_geometry(primitive)

    assert geometry.room_resref == "grdev_poly"
    assert geometry.room_mesh.name == "grdev_poly_floor"
    assert geometry.room_mesh.texture == "CM_Baremetal"
    assert geometry.room_mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert geometry.room_mesh.metadata["surface_id"] == 10
    assert geometry.wok.walkable_face_count() == 2
    assert [face.surface for face in geometry.wok.faces] == [10, 10]
    assert len(geometry.helper_meshes) == 4
    assert geometry.helper_meshes[0].metadata["primitive"] == "floor_plan_wall"
    assert geometry.metadata["primitive"] == "floor_plan_extrusion"
    assert geometry.metadata["wall_count"] == 4
    assert geometry.metadata["polygon_area"] == 8.0


def test_t2611_clockwise_floor_plan_is_normalized_for_wok_and_mesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, compile_floor_plan_room_geometry, polygon_signed_area

    primitive = FloorPlanRoomPrimitive(
        room_resref="clockwise",
        points=((-1.0, -1.0), (-1.0, 1.0), (1.0, 1.0), (1.0, -1.0)),
    )

    geometry = compile_floor_plan_room_geometry(primitive)

    assert polygon_signed_area(primitive.points) < 0.0
    assert polygon_signed_area(tuple((x, y) for x, y, _ in geometry.room_mesh.vertices)) > 0.0
    assert geometry.room_mesh.faces == ((0, 1, 2), (0, 2, 3))
    assert geometry.wok.faces[0].adj3 == 1
    assert geometry.wok.faces[1].adj1 == 0


def test_t2611_invalid_floor_plan_blocks_before_geometry_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, validate_floor_plan_room_primitive

    too_few = validate_floor_plan_room_primitive(FloorPlanRoomPrimitive(room_resref="bad", points=((0.0, 0.0), (1.0, 0.0))))
    duplicate = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(room_resref="bad", points=((0.0, 0.0), (1.0, 0.0), (1.0, 0.0), (0.0, 1.0)))
    )
    concave = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad",
            points=((0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)),
        )
    )

    assert not too_few.ok
    assert any("at least three" in issue for issue in too_few.blocking_issues)
    assert not duplicate.ok
    assert any("duplicate" in issue for issue in duplicate.blocking_issues)
    assert not concave.ok
    assert any("convex" in issue for issue in concave.blocking_issues)


def test_t2613_floor_plan_doorway_opening_splits_wall_panels() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening, compile_floor_plan_room_geometry

    primitive = FloorPlanRoomPrimitive(
        room_resref="door_room",
        points=((-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)),
        wall_height=3.0,
        openings=(FloorPlanWallOpening(name="door_a", edge_index=0, center_fraction=0.5, width=1.0, height=2.0),),
    )

    geometry = compile_floor_plan_room_geometry(primitive)
    wall_names = [mesh.name for mesh in geometry.helper_meshes]
    opening_panels = [mesh for mesh in geometry.helper_meshes if mesh.metadata.get("opening_name") == "door_a"]

    assert geometry.metadata["opening_count"] == 1
    assert geometry.metadata["wall_count"] == 6
    assert wall_names[:3] == ["door_room_wall_01_left", "door_room_wall_01_lintel", "door_room_wall_01_right"]
    assert len(opening_panels) == 3
    assert {mesh.metadata["wall_panel"] for mesh in opening_panels} == {"opening_left", "opening_lintel", "opening_right"}
    lintel = next(mesh for mesh in opening_panels if mesh.metadata["wall_panel"] == "opening_lintel")
    assert min(vertex[2] for vertex in lintel.vertices) == 2.0
    assert max(vertex[2] for vertex in lintel.vertices) == 3.0
    assert geometry.wok.walkable_face_count() == 2


def test_t2613_invalid_floor_plan_opening_blocks_before_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening, validate_floor_plan_room_primitive

    oversized = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad_opening",
            points=((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),
            openings=(FloorPlanWallOpening(name="too_wide", edge_index=0, width=4.0, height=1.0),),
        )
    )
    too_tall = validate_floor_plan_room_primitive(
        FloorPlanRoomPrimitive(
            room_resref="bad_opening",
            points=((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),
            openings=(FloorPlanWallOpening(name="too_tall", edge_index=0, width=1.0, height=3.0),),
        )
    )

    assert not oversized.ok
    assert any("does not fit within wall edge" in issue for issue in oversized.blocking_issues)
    assert not too_tall.ok
    assert any("must leave wall geometry above it" in issue for issue in too_tall.blocking_issues)


def test_t2623_insets_convex_floor_plan_points() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import inset_floor_plan_points, polygon_signed_area

    inset = inset_floor_plan_points(((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)), 0.5)

    assert inset == ((-2.5, -1.5), (2.5, -1.5), (2.5, 1.5), (-2.5, 1.5))
    assert polygon_signed_area(inset) == 15.0


def test_t2623_apply_inset_compiles_smaller_floor_plan_room() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanInsetOperation, FloorPlanRoomPrimitive, FloorPlanWallOpening, apply_floor_plan_inset, compile_floor_plan_room_geometry

    primitive = FloorPlanRoomPrimitive(
        room_resref="outer_room",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        openings=(FloorPlanWallOpening(name="door", edge_index=0),),
        metadata={"author_note": "blockout"},
    )

    inset = apply_floor_plan_inset(
        primitive,
        FloorPlanInsetOperation(distance=0.25, room_resref="inner_room", metadata={"operation_id": "inset_a"}),
    )
    geometry = compile_floor_plan_room_geometry(inset)

    assert inset.room_resref == "inner_room"
    assert inset.points == ((-2.75, -1.75), (2.75, -1.75), (2.75, 1.75), (-2.75, 1.75))
    assert inset.openings == ()
    assert inset.metadata["operation"] == "inset"
    assert inset.metadata["author_note"] == "blockout"
    assert inset.metadata["operation_id"] == "inset_a"
    assert geometry.room_resref == "inner_room"
    assert geometry.metadata["polygon_area"] == 19.25


def test_t2623_inset_rejects_invalid_operation_inputs() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_floorplan import inset_floor_plan_points

    with pytest.raises(ValueError, match="distance must be positive"):
        inset_floor_plan_points(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), 0.0)
    with pytest.raises(ValueError, match="convex footprints only"):
        inset_floor_plan_points(((0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)), 0.1)


def test_t2625_bevels_convex_floor_plan_points() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import bevel_floor_plan_points, polygon_signed_area

    bevelled = bevel_floor_plan_points(((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)), 0.5)

    assert bevelled == (
        (-3.0, -1.5),
        (-2.5, -2.0),
        (2.5, -2.0),
        (3.0, -1.5),
        (3.0, 1.5),
        (2.5, 2.0),
        (-2.5, 2.0),
        (-3.0, 1.5),
    )
    assert polygon_signed_area(bevelled) == 23.5


def test_t2625_apply_bevel_compiles_chamfered_floor_plan_room() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanBevelOperation, FloorPlanRoomPrimitive, FloorPlanWallOpening, apply_floor_plan_bevel, compile_floor_plan_room_geometry

    primitive = FloorPlanRoomPrimitive(
        room_resref="box_room",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        openings=(FloorPlanWallOpening(name="door", edge_index=0),),
        metadata={"author_note": "blockout"},
    )

    bevelled = apply_floor_plan_bevel(
        primitive,
        FloorPlanBevelOperation(distance=0.25, room_resref="bevel_room", metadata={"operation_id": "bevel_a"}),
    )
    geometry = compile_floor_plan_room_geometry(bevelled)

    assert bevelled.room_resref == "bevel_room"
    assert len(bevelled.points) == 8
    assert bevelled.openings == ()
    assert bevelled.metadata["operation"] == "bevel"
    assert bevelled.metadata["author_note"] == "blockout"
    assert bevelled.metadata["operation_id"] == "bevel_a"
    assert geometry.room_resref == "bevel_room"
    assert geometry.room_mesh.name == "bevel_room_floor"
    assert len(geometry.room_mesh.faces) == 6
    assert geometry.wok.walkable_face_count() == 6
    assert geometry.metadata["wall_count"] == 8
    assert geometry.metadata["polygon_area"] == 23.875


def test_t2625_bevel_rejects_invalid_operation_inputs() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_floorplan import bevel_floor_plan_points

    with pytest.raises(ValueError, match="distance must be positive"):
        bevel_floor_plan_points(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), 0.0)
    with pytest.raises(ValueError, match="overlaps edge"):
        bevel_floor_plan_points(((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)), 1.0)
    with pytest.raises(ValueError, match="convex footprints only"):
        bevel_floor_plan_points(((0.0, 0.0), (2.0, 0.0), (1.0, 0.5), (2.0, 2.0), (0.0, 2.0)), 0.1)


def test_t2627_rectangular_cut_decomposes_floor_plan_into_convex_pieces() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRectangularCutOperation,
        FloorPlanRoomPrimitive,
        apply_floor_plan_rectangular_cut,
        compile_floor_plan_room_geometry,
        polygon_signed_area,
    )

    primitive = FloorPlanRoomPrimitive(
        room_resref="cut_room",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        metadata={"author_note": "boolean blockout"},
    )

    pieces = apply_floor_plan_rectangular_cut(
        primitive,
        FloorPlanRectangularCutOperation(center=(0.0, 0.0), size=(2.0, 1.0), room_resref_prefix="cutpiece"),
    )
    geometries = [compile_floor_plan_room_geometry(piece) for piece in pieces]

    assert [piece.room_resref for piece in pieces] == ["cutpiece_l1", "cutpiece_r2", "cutpiece_b3", "cutpiece_t4"]
    assert [piece.metadata["piece_role"] for piece in pieces] == ["left", "right", "bottom", "top"]
    assert all(piece.openings == () for piece in pieces)
    assert all(piece.metadata["operation"] == "rectangular_cut_difference" for piece in pieces)
    assert all(piece.metadata["author_note"] == "boolean blockout" for piece in pieces)
    assert sum(abs(polygon_signed_area(piece.points)) for piece in pieces) == 22.0
    assert sum(geometry.wok.walkable_face_count() for geometry in geometries) == 8


def test_t2627_rectangular_edge_cut_creates_exportable_notch_pieces() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRectangularCutOperation, FloorPlanRoomPrimitive, apply_floor_plan_rectangular_cut, polygon_signed_area

    primitive = FloorPlanRoomPrimitive(
        room_resref="notch_room",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
    )

    pieces = apply_floor_plan_rectangular_cut(
        primitive,
        FloorPlanRectangularCutOperation(center=(0.0, 1.25), size=(2.0, 1.5)),
    )

    assert [piece.metadata["piece_role"] for piece in pieces] == ["left", "right", "bottom"]
    assert sum(abs(polygon_signed_area(piece.points)) for piece in pieces) == 21.0
    assert pieces[0].points == ((-3.0, -2.0), (-1.0, -2.0), (-1.0, 2.0), (-3.0, 2.0))
    assert pieces[2].points == ((-1.0, -2.0), (1.0, -2.0), (1.0, 0.5), (-1.0, 0.5))


def test_t2627_rectangular_cut_rejects_unsafe_inputs() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_floorplan import FloorPlanRectangularCutOperation, FloorPlanRoomPrimitive, apply_floor_plan_rectangular_cut

    primitive = FloorPlanRoomPrimitive(
        room_resref="cut_room",
        points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
    )
    non_rect = FloorPlanRoomPrimitive(
        room_resref="bad",
        points=((0.0, 0.0), (2.0, 0.0), (3.0, 1.0), (2.0, 2.0), (0.0, 2.0)),
    )

    with pytest.raises(ValueError, match="size must be positive"):
        apply_floor_plan_rectangular_cut(primitive, FloorPlanRectangularCutOperation(center=(0.0, 0.0), size=(0.0, 1.0)))
    with pytest.raises(ValueError, match="does not overlap"):
        apply_floor_plan_rectangular_cut(primitive, FloorPlanRectangularCutOperation(center=(9.0, 0.0), size=(1.0, 1.0)))
    with pytest.raises(ValueError, match="remove the entire"):
        apply_floor_plan_rectangular_cut(primitive, FloorPlanRectangularCutOperation(center=(0.0, 0.0), size=(8.0, 6.0)))
    with pytest.raises(ValueError, match="rectangular source"):
        apply_floor_plan_rectangular_cut(non_rect, FloorPlanRectangularCutOperation(center=(1.0, 1.0), size=(1.0, 1.0)))


def test_t2628_rectangular_union_merges_adjacent_floor_plans() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import (
        FloorPlanRectangularUnionOperation,
        FloorPlanRoomPrimitive,
        FloorPlanWallOpening,
        apply_floor_plan_rectangular_union,
        compile_floor_plan_room_geometry,
        polygon_signed_area,
    )
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    left = FloorPlanRoomPrimitive(
        room_resref="left_room",
        points=((-4.0, -2.0), (0.0, -2.0), (0.0, 2.0), (-4.0, 2.0)),
        floor_surface_id="metal",
        material=PrimitiveMaterial(texture="CM_Baremetal"),
        openings=(FloorPlanWallOpening(name="old_door", edge_index=1),),
        metadata={"author_note": "blockout"},
    )
    right = FloorPlanRoomPrimitive(
        room_resref="right_room",
        points=((0.0, -2.0), (4.0, -2.0), (4.0, 2.0), (0.0, 2.0)),
        floor_surface_id="metal",
        material=PrimitiveMaterial(texture="CM_Baremetal"),
    )

    merged = apply_floor_plan_rectangular_union(
        left,
        right,
        FloorPlanRectangularUnionOperation(room_resref="merged_room", metadata={"operation_id": "union_a"}),
    )
    geometry = compile_floor_plan_room_geometry(merged)

    assert merged.room_resref == "merged_room"
    assert merged.points == ((-4.0, -2.0), (4.0, -2.0), (4.0, 2.0), (-4.0, 2.0))
    assert merged.openings == ()
    assert merged.metadata["operation"] == "rectangular_union"
    assert merged.metadata["operation_id"] == "union_a"
    assert merged.metadata["author_note"] == "blockout"
    assert merged.metadata["source_room_resrefs"] == ["left_room", "right_room"]
    assert polygon_signed_area(merged.points) == 32.0
    assert geometry.room_resref == "merged_room"
    assert geometry.wok.walkable_face_count() == 2
    assert geometry.metadata["polygon_area"] == 32.0


def test_t2628_rectangular_union_allows_overlapping_rectangles_that_fill_bounds() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, apply_floor_plan_rectangular_union

    lower = FloorPlanRoomPrimitive(
        room_resref="lower",
        points=((-2.0, -2.0), (2.0, -2.0), (2.0, 1.0), (-2.0, 1.0)),
    )
    upper = FloorPlanRoomPrimitive(
        room_resref="upper",
        points=((-2.0, -1.0), (2.0, -1.0), (2.0, 2.0), (-2.0, 2.0)),
    )

    merged = apply_floor_plan_rectangular_union(lower, upper)

    assert merged.room_resref == "lower"
    assert merged.points == ((-2.0, -2.0), (2.0, -2.0), (2.0, 2.0), (-2.0, 2.0))
    assert merged.metadata["combined_bounds"] == [-2.0, -2.0, 2.0, 2.0]


def test_t2628_rectangular_union_rejects_non_rectangular_results() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, apply_floor_plan_rectangular_union
    from src.core.modules.authored_room_primitives import PrimitiveMaterial

    base = FloorPlanRoomPrimitive(
        room_resref="base",
        points=((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
    )
    l_shape = FloorPlanRoomPrimitive(
        room_resref="branch",
        points=((2.0, 1.0), (4.0, 1.0), (4.0, 3.0), (2.0, 3.0)),
    )
    disjoint = FloorPlanRoomPrimitive(
        room_resref="far",
        points=((5.0, 0.0), (6.0, 0.0), (6.0, 1.0), (5.0, 1.0)),
    )
    mismatched_material = FloorPlanRoomPrimitive(
        room_resref="mat",
        points=((2.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0)),
        material=PrimitiveMaterial(texture="different"),
    )
    non_rect = FloorPlanRoomPrimitive(
        room_resref="poly",
        points=((0.0, 0.0), (2.0, 0.0), (3.0, 1.0), (2.0, 2.0), (0.0, 2.0)),
    )

    with pytest.raises(ValueError, match="non-rectangular or disconnected"):
        apply_floor_plan_rectangular_union(base, l_shape)
    with pytest.raises(ValueError, match="non-rectangular or disconnected"):
        apply_floor_plan_rectangular_union(base, disjoint)
    with pytest.raises(ValueError, match="matching room materials"):
        apply_floor_plan_rectangular_union(base, mismatched_material)
    with pytest.raises(ValueError, match="rectangular footprints"):
        apply_floor_plan_rectangular_union(base, non_rect)
