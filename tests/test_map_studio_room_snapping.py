"""Modular maps Phase 3: snap rooms together at their doorways.

Rooms added from the catalog carry their LYT door hooks (room-local position
+ orientation). Snapping translates one room so a chosen hook coincides
exactly with a chosen hook on another room, so the entrances meet. KOTOR
rooms cannot rotate, so the result flags hooks that do not face each other.
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


def _room(resref, position, hooks):
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_project import AuthoredRoomSpec

    surface = ImportedMeshSurface(
        name=f"{resref}_floor", texture="tex",
        vertices=((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0)), faces=((0, 1, 2),),
    )
    primitive = ImportedMeshRoomPrimitive(room_resref=resref, surfaces=(surface,), source_model=resref)
    return AuthoredRoomSpec(
        room_resref=resref, primitive=primitive, position=position,
        metadata={"source": "stock_room_conversion", "connection_points": hooks},
    )


def _project(rooms):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject

    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grsnap", game="K2", display_name="grsnap", tag="grsnap"),
        rooms=tuple(rooms),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grsnap")),
        lights=(),
    )


# A door facing +X (quaternion identity) and one facing -X (180deg about Z).
_FACE_POS_X = [0.0, 0.0, 0.0, 1.0]
_FACE_NEG_X = [0.0, 0.0, 1.0, 0.0]


def test_authored_room_door_hooks_are_world_space() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_snapping import authored_room_door_hooks

    room = _room("rooma", (10.0, 5.0, 0.0), [{"door": "d1", "local_position": [2.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    hooks = authored_room_door_hooks(room)
    assert len(hooks) == 1
    assert hooks[0].door == "d1"
    assert hooks[0].world_position == (12.0, 5.0, 0.0)  # room position + local


def test_snap_translates_source_so_hooks_coincide() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_snapping import authored_room_door_hooks, snap_authored_room_to_room

    # target room at origin, its door at world (2, 0, 0) facing +X.
    target = _room("target", (0.0, 0.0, 0.0), [{"door": "east", "local_position": [2.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    # source room dropped far east; its door faces -X (so they oppose).
    source = _room("source", (50.0, 0.0, 0.0), [{"door": "west", "local_position": [-2.0, 0.0, 0.0], "orientation": _FACE_NEG_X}])
    result = snap_authored_room_to_room(
        _project([target, source]),
        source_room_resref="source", source_door="west",
        target_room_resref="target", target_door="east",
    )
    moved = next(r for r in result.project.rooms if r.normalised_resref() == "source")
    # The source door now sits exactly on the target door.
    src_hook = authored_room_door_hooks(moved)[0]
    assert abs(src_hook.world_position[0] - 2.0) < 1e-6
    assert abs(src_hook.world_position[1]) < 1e-6
    assert result.opposed is True
    assert not result.warnings


def test_snap_warns_when_hooks_do_not_oppose() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_snapping import snap_authored_room_to_room

    target = _room("target", (0.0, 0.0, 0.0), [{"door": "east", "local_position": [2.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    source = _room("source", (50.0, 0.0, 0.0), [{"door": "also_east", "local_position": [-2.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    result = snap_authored_room_to_room(
        _project([target, source]),
        source_room_resref="source", source_door="also_east",
        target_room_resref="target", target_door="east",
    )
    assert result.opposed is False
    assert result.warnings and "face" in result.warnings[0]


def test_snap_rejects_same_room_and_missing_hooks() -> None:
    _configure_native_python_roots()
    import pytest

    from src.core.modules.map_studio_room_snapping import snap_authored_room_to_room

    room = _room("rooma", (0.0, 0.0, 0.0), [{"door": "d", "local_position": [1.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    bare = _room("roomb", (5.0, 0.0, 0.0), [])
    project = _project([room, bare])
    with pytest.raises(ValueError):
        snap_authored_room_to_room(project, source_room_resref="rooma", source_door="d", target_room_resref="rooma", target_door="d")
    with pytest.raises(ValueError):
        snap_authored_room_to_room(project, source_room_resref="roomb", source_door="", target_room_resref="rooma", target_door="d")


def test_controller_snap_is_undoable() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    target = _room("target", (0.0, 0.0, 0.0), [{"door": "east", "local_position": [2.0, 0.0, 0.0], "orientation": _FACE_POS_X}])
    source = _room("source", (50.0, 0.0, 0.0), [{"door": "west", "local_position": [-2.0, 0.0, 0.0], "orientation": _FACE_NEG_X}])
    controller = ModuleEditorController()
    controller.new_project(name="grsnap", game="K2")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(_project([target, source]))
    controller._invalidate_map_studio_authored_state("test setup")

    choices = {row["room_resref"]: row for row in controller.authored_room_doorway_choices()}
    assert choices["source"]["hook_count"] == 1

    ok, message = controller.snap_authored_rooms_at_doorway(
        source_room_resref="source", source_door="west", target_room_resref="target", target_door="east",
    )
    assert ok, message
    from src.core.modules.map_studio_room_snapping import authored_room_door_hooks

    authored = controller._load_authored_project_or_raise()
    moved = next(r for r in authored.rooms if r.normalised_resref() == "source")
    # The room origin translated (50 -> 4) so its west door (local -2) now sits
    # exactly on the target's east door at world x=2.
    assert abs(float(moved.position[0]) - 4.0) < 1e-6
    assert abs(authored_room_door_hooks(moved)[0].world_position[0] - 2.0) < 1e-6
    # The snap recorded an undoable command.
    assert controller.can_undo_map_studio_command()
