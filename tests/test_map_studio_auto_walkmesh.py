"""Auto Generate Walkmesh: derive a room walkmesh from its render geometry.

Grounded in the complete installed K1/K2 WOK census and the plcaa engine proof:
walkable faces are up-facing and near-horizontal, while render walls and
ceilings must not be copied into a generated WOK around the floor.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _surface(name, tris):
    from src.core.modules.authored_imported_mesh import ImportedMeshSurface

    verts = []
    faces = []
    for tri in tris:
        base = len(verts)
        verts.extend(tri)
        faces.append((base, base + 1, base + 2))
    return ImportedMeshSurface(name=name, texture="tex", vertices=tuple(verts), faces=tuple(faces))


def _room_primitive(surfaces):
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive

    return ImportedMeshRoomPrimitive(room_resref="genroom", surfaces=tuple(surfaces), source_model="genroom")


# A flat up-facing floor quad, a vertical wall quad, and a down-facing ceiling.
_FLOOR = [
    ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
    ((0.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)),
]
_WALL = [
    ((0.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 10.0, 3.0)),
    ((0.0, 0.0, 0.0), (0.0, 10.0, 3.0), (0.0, 0.0, 3.0)),
]
_CEILING = [
    ((0.0, 0.0, 3.0), (10.0, 10.0, 3.0), (10.0, 0.0, 3.0)),
    ((0.0, 0.0, 3.0), (0.0, 10.0, 3.0), (10.0, 10.0, 3.0)),
]


def test_generator_classifies_floor_wall_and_drops_ceiling() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WALKABLE_IDS

    primitive = _room_primitive([_surface("floor", _FLOOR), _surface("wall", _WALL), _surface("ceil", _CEILING)])
    updated, report = generate_room_walkmesh_from_geometry(primitive)
    assert report["floor_faces"] == 2
    assert report["wall_faces"] == 2
    assert report["dropped_ceiling_faces"] == 2
    materials = [int(f.surface) for f in updated.wok.faces]
    assert sum(1 for m in materials if m in WALKABLE_IDS) == 2
    assert len(materials) == 2
    assert report["dropped_wall_faces"] == 2
    assert report["structural_validation"] == "passed"
    assert report["serialized_perimeter_loop_count"] == 1
    assert report["serialized_aabb_count"] == 3
    # A fresh room-local WOK replaces the old one; provenance recorded.
    meta = dict(updated.primitive.metadata) if hasattr(updated, "primitive") else dict(updated.metadata)
    assert meta.get("wok_coordinate_space") == "room_local"
    assert "wok_auto_generated" in meta


def test_imported_room_without_source_wok_requires_explicit_floor_intent() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import (
        generate_room_walkmesh_from_geometry,
        prepare_imported_mesh_walkmesh_generation_intent,
    )

    primitive = _room_primitive(
        [_surface("floor", _FLOOR), _surface("table_top", [((2.0, 2.0, 1.0), (3.0, 2.0, 1.0), (2.0, 3.0, 1.0))])]
    )
    primitive = replace(primitive, metadata={"imported_from": "legacy_room.mdl"})

    unchanged, blocked = generate_room_walkmesh_from_geometry(primitive)
    reviewed = prepare_imported_mesh_walkmesh_generation_intent(
        primitive,
        surface_faces={0: None},
        reason="Surface 0 is the authored floor; surface 1 is furniture.",
    )
    generated, report = generate_room_walkmesh_from_geometry(reviewed)

    assert unchanged is primitive
    assert blocked["structural_validation"] == "blocked"
    assert "roofs, tables" in blocked["blocked_reason"]
    assert generated.wok is not None
    assert len(generated.wok.faces) == 2
    assert report["reviewed_surface_names"] == ["floor"]
    assert report["reviewed_face_intent_count"] == 2


def test_imported_floor_intent_can_select_individual_faces_and_reject_stale_rows() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    import pytest

    from src.core.modules.authored_imported_mesh import (
        generate_room_walkmesh_from_geometry,
        prepare_imported_mesh_walkmesh_generation_intent,
    )

    mixed = _surface(
        "mixed_floor_and_ledge",
        _FLOOR + [((2.0, 2.0, 1.0), (3.0, 2.0, 1.0), (2.0, 3.0, 1.0))],
    )
    primitive = replace(
        _room_primitive([mixed]),
        metadata={"imported_from": "legacy_room.mdl"},
    )
    reviewed = prepare_imported_mesh_walkmesh_generation_intent(
        primitive,
        surface_faces={0: (0, 1)},
        reason="Only the first two triangles form the player floor.",
    )

    generated, report = generate_room_walkmesh_from_geometry(reviewed)

    assert generated.wok is not None
    assert len(generated.wok.faces) == 2
    assert report["reviewed_face_intent_count"] == 2
    with pytest.raises(ValueError, match="outside surface 0"):
        prepare_imported_mesh_walkmesh_generation_intent(
            primitive,
            surface_faces={0: (99,)},
            reason="stale",
        )


def test_generator_respects_slope_threshold() -> None:
    _configure_native_python_roots()
    import math

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WALKABLE_IDS

    # A 30-degree ramp (walkable) and a 60-degree ramp (wall) at 45 threshold.
    def ramp(angle_deg, y0):
        rise = 10.0 * math.tan(math.radians(angle_deg))
        return [
            ((0.0, y0, 0.0), (10.0, y0, 0.0), (10.0, y0 + 10.0, rise)),
            ((0.0, y0, 0.0), (10.0, y0 + 10.0, rise), (0.0, y0 + 10.0, rise)),
        ]

    primitive = _room_primitive([_surface("r30", ramp(30.0, 0.0)), _surface("r60", ramp(60.0, 40.0))])
    updated, report = generate_room_walkmesh_from_geometry(primitive, slope_max_degrees=45.0)
    assert report["floor_faces"] == 2  # the 30-degree ramp is walkable
    assert report["wall_faces"] == 2   # the 60-degree ramp is omitted
    assert len(updated.wok.faces) == 2
    assert all(int(face.surface) in WALKABLE_IDS for face in updated.wok.faces)


def test_generator_leaves_room_untouched_without_a_floor() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry

    primitive = _room_primitive([_surface("wall", _WALL)])  # only a wall, no floor
    updated, report = generate_room_walkmesh_from_geometry(primitive)
    assert report["floor_faces"] == 0
    assert updated is primitive  # unchanged


def test_generator_projects_existing_wok_materials_onto_covered_floor() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WOKData, WOKFace

    primitive = _room_primitive([_surface("floor", _FLOOR)])
    source = WOKData(
        name="genroom",
        verts=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        faces=[
            WOKFace(0, 1, 2, 10, -1, -1, -1),
            WOKFace(0, 2, 3, 10, -1, -1, -1),
        ],
    )
    source.rebuild_adjacencies()
    primitive = replace(primitive, wok=source)

    updated, report = generate_room_walkmesh_from_geometry(primitive, source_wok_policy="replace")
    assert report["projected_material_faces"] == 2
    assert [int(face.surface) for face in updated.wok.faces] == [10, 10]


def test_generator_preserves_imported_hole_unless_replacement_is_explicit() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WOKData, WOKFace

    primitive = _room_primitive([_surface("full_render_floor", _FLOOR)])
    source = WOKData(
        name="genroom",
        verts=[
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (10.0, 10.0, 0.0),
            (0.0, 10.0, 0.0),
            (3.0, 3.0, 0.0),
            (7.0, 3.0, 0.0),
            (7.0, 7.0, 0.0),
            (3.0, 7.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 5, 4),
            WOKFace(0, 5, 4, 4),
            WOKFace(1, 2, 6, 4),
            WOKFace(1, 6, 5, 4),
            WOKFace(2, 3, 7, 4),
            WOKFace(2, 7, 6, 4),
            WOKFace(3, 0, 4, 4),
            WOKFace(3, 4, 7, 4),
        ],
    )
    source.rebuild_adjacencies()
    primitive = replace(primitive, wok=source)

    preserved, safe_report = generate_room_walkmesh_from_geometry(primitive)
    replaced, destructive_report = generate_room_walkmesh_from_geometry(
        primitive,
        source_wok_policy="replace",
    )

    assert preserved is primitive
    assert safe_report["source_wok_preserved"] is True
    assert safe_report["serialized_perimeter_loop_count"] == 2
    assert safe_report["interior_boundary_loop_count"] == 1
    assert replaced is not primitive
    assert destructive_report["source_wok_preserved"] is False
    assert destructive_report["serialized_perimeter_loop_count"] == 1
    assert len(replaced.wok.faces) == 2


def test_generator_preserves_exactly_mappable_source_perimeter_transition() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WOKData, WOKFace

    primitive = _room_primitive([_surface("floor", _FLOOR)])
    source = WOKData(
        name="genroom",
        verts=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        faces=[
            WOKFace(0, 1, 2, 4, -1, -1, -1, 3, -1, -1),
            WOKFace(0, 2, 3, 4, -1, -1, -1),
        ],
    )
    source.rebuild_adjacencies()
    primitive = replace(primitive, wok=source)

    updated, report = generate_room_walkmesh_from_geometry(primitive, source_wok_policy="replace")
    assert updated is not primitive
    assert report["source_transition_edges"] == 1
    assert report["mapped_transition_edges"] == 1
    assert report["unmapped_transition_edges"] == 0
    assert [value for face in updated.wok.faces for value in (face.trans1, face.trans2, face.trans3) if value >= 0] == [3]


def test_generator_refuses_room_when_source_transition_cannot_be_mapped_safely() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import WOKData, WOKFace

    primitive = _room_primitive([_surface("floor", _FLOOR)])
    source = WOKData(
        name="genroom",
        verts=[(100.0, 0.0, 0.0), (110.0, 0.0, 0.0), (110.0, 10.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 4, -1, -1, -1, 7, -1, -1)],
    )
    primitive = replace(primitive, wok=source)

    updated, report = generate_room_walkmesh_from_geometry(primitive, source_wok_policy="replace")
    assert updated is primitive
    assert report["unmapped_transition_edges"] == 1
    assert "refused" in report["blocked_reason"]


def test_generator_reports_render_resolution_density_without_decimating() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import (
        EMPIRICAL_STOCK_WOK_FACE_MAX,
        generate_room_walkmesh_from_geometry,
    )
    from src.core.modules.authored_walkmesh_audit import audit_authored_wok

    triangles = [
        ((float(index) * 2.0, 0.0, 0.0), (float(index) * 2.0 + 1.0, 0.0, 0.0), (float(index) * 2.0, 1.0, 0.0))
        for index in range(EMPIRICAL_STOCK_WOK_FACE_MAX + 1)
    ]
    primitive = _room_primitive([_surface("dense", triangles)])
    updated, report = generate_room_walkmesh_from_geometry(
        primitive,
        disconnected_island_policy="preserve",
    )

    assert len(updated.wok.faces) == EMPIRICAL_STOCK_WOK_FACE_MAX + 1
    assert report["density_warning_threshold"] == EMPIRICAL_STOCK_WOK_FACE_MAX
    assert "no decimation" in report["density_warning"]
    assert any("empirical stock-room maximum" in warning for warning in audit_authored_wok("dense", updated.wok).warnings)


def test_generator_serializes_connected_floor_hole_as_outer_and_inner_perimeters() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry

    ring = [
        ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (3.0, 1.0, 0.0)),
        ((0.0, 0.0, 0.0), (3.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
        ((4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (3.0, 3.0, 0.0)),
        ((4.0, 0.0, 0.0), (3.0, 3.0, 0.0), (3.0, 1.0, 0.0)),
        ((4.0, 4.0, 0.0), (0.0, 4.0, 0.0), (1.0, 3.0, 0.0)),
        ((4.0, 4.0, 0.0), (1.0, 3.0, 0.0), (3.0, 3.0, 0.0)),
        ((0.0, 4.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
        ((0.0, 4.0, 0.0), (1.0, 1.0, 0.0), (1.0, 3.0, 0.0)),
    ]
    primitive = _room_primitive([_surface("ring", ring)])

    updated, report = generate_room_walkmesh_from_geometry(primitive)

    assert updated is not primitive
    assert report["walkable_component_count"] == 1
    assert report["serialized_perimeter_loop_count"] == 2
    assert report["interior_boundary_loop_count"] == 1
    assert report["structural_validation"] == "passed"


def test_generator_rejects_unreviewed_disconnected_walkable_islands() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry

    second_floor = [
        ((20.0, 0.0, 0.0), (30.0, 0.0, 0.0), (30.0, 10.0, 0.0)),
        ((20.0, 0.0, 0.0), (30.0, 10.0, 0.0), (20.0, 10.0, 0.0)),
    ]
    primitive = _room_primitive([_surface("islands", _FLOOR + second_floor)])

    unchanged, rejected = generate_room_walkmesh_from_geometry(primitive)
    preserved, accepted = generate_room_walkmesh_from_geometry(
        primitive,
        disconnected_island_policy="preserve",
    )

    assert unchanged is primitive
    assert rejected["walkable_component_count"] == 2
    assert "explicit review" in rejected["blocked_reason"]
    assert preserved is not primitive
    assert accepted["walkable_component_count"] == 2
    assert accepted["serialized_perimeter_loop_count"] == 2
    assert accepted["interior_boundary_loop_count"] == 0
    assert accepted["structural_validation"] == "passed"


def test_controller_auto_generate_all_rooms_is_undoable() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_editor_controller import ModuleEditorController

    room = AuthoredRoomSpec(
        room_resref="genroom",
        primitive=_room_primitive([_surface("floor", _FLOOR), _surface("wall", _WALL), _surface("ceil", _CEILING)]),
        position=(0.0, 0.0, 0.0),
        metadata={"source": "stock_room_conversion"},
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grauto", game="K2", display_name="grauto", tag="grauto"),
        rooms=(room,),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grauto")),
        lights=(),
    )
    controller = ModuleEditorController()
    controller.new_project(name="grauto", game="K2")
    controller._store_authored_project(project)

    ok, message = controller.auto_generate_map_studio_walkmesh()
    assert ok, message
    assert "walkable floor" in message
    authored = controller._load_authored_project_or_raise()
    wok = authored.rooms[0].primitive.wok
    assert wok is not None and len(wok.faces) == 2  # floor only; wall and ceiling omitted
    assert controller.can_undo_map_studio_command()


def test_controller_reports_imported_room_with_no_floor_truthfully() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_editor_controller import ModuleEditorController

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grnofloor", game="K2", display_name="grnofloor", tag="grnofloor"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="wallonly",
                primitive=_room_primitive([_surface("wall", _WALL)]),
                position=(0.0, 0.0, 0.0),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grnofloor")),
        lights=(),
    )
    controller = ModuleEditorController()
    controller.new_project(name="grnofloor", game="K2")
    controller._store_authored_project(project)

    ok, message = controller.auto_generate_map_studio_walkmesh()
    assert ok is False
    assert "1 imported room(s) had no derivable walkable floor" in message
    assert "not editable imported meshes" not in message
