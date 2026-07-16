"""Auto Generate Walkmesh: derive a room walkmesh from its render geometry.

Grounded in a study of 1121 stock K2 room WOKs: walkable faces are up-facing
and near-horizontal (99% within 45 deg of flat), walls are kept as NON_WALK
(94% of rooms carry them), and ceilings are dropped (a down-facing face over
the floor collapses the perimeter loop and freezes the player).
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
    from src.core.modules.module_format import NON_WALK_ID, WALKABLE_IDS

    primitive = _room_primitive([_surface("floor", _FLOOR), _surface("wall", _WALL), _surface("ceil", _CEILING)])
    updated, report = generate_room_walkmesh_from_geometry(primitive)
    assert report["floor_faces"] == 2
    assert report["wall_faces"] == 2
    assert report["dropped_ceiling_faces"] == 2
    materials = [int(f.surface) for f in updated.wok.faces]
    assert sum(1 for m in materials if m in WALKABLE_IDS) == 2
    assert sum(1 for m in materials if m == NON_WALK_ID) == 2
    # A fresh room-local WOK replaces the old one; provenance recorded.
    meta = dict(updated.primitive.metadata) if hasattr(updated, "primitive") else dict(updated.metadata)
    assert meta.get("wok_coordinate_space") == "room_local"
    assert "wok_auto_generated" in meta


def test_generator_respects_slope_threshold() -> None:
    _configure_native_python_roots()
    import math

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.module_format import NON_WALK_ID, WALKABLE_IDS

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
    assert report["wall_faces"] == 2   # the 60-degree ramp is NON_WALK


def test_generator_leaves_room_untouched_without_a_floor() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry

    primitive = _room_primitive([_surface("wall", _WALL)])  # only a wall, no floor
    updated, report = generate_room_walkmesh_from_geometry(primitive)
    assert report["floor_faces"] == 0
    assert updated is primitive  # unchanged


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
    assert wok is not None and len(wok.faces) == 4  # 2 floor + 2 wall, ceiling dropped
    assert controller.can_undo_map_studio_command()
