"""Mislabeled room-local WOKs must be auto-aligned to their room geometry.

Converted candidate modules can ship a custom room whose WOK is stored
room-local while stock import labels every room ``wok_coordinate_space:
"module"`` (921srt's 921srtb).  Trusting the label leaves that room's
collision floating at the label-implied coordinates: the combined walkmesh
has no floor under the player start, PIE blocks with "Player start is not on
a walkable WOK face", and an exported .wok detaches from the room in-game.
The alignment audit compares the WOK bounds with the room's rendered
surfaces and re-reads the WOK as room-local when that clearly fixes it.
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


def _square_room(*, resref: str, position: tuple[float, float, float], wok_verts_offset: tuple[float, float, float]):
    """One imported room: a 10x10 render square at room-local origin plus a
    WOK square whose vertices carry ``wok_verts_offset`` (module-space WOKs
    bake the room's world position in; room-local ones use (0, 0, 0))."""

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.module_format import WOKData, WOKFace

    corners = ((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0))
    surface = ImportedMeshSurface(
        name=f"{resref}_floor",
        texture="tex01",
        vertices=tuple((x, y, 0.0) for x, y in corners),
        faces=((0, 1, 2), (0, 2, 3)),
    )
    ox, oy, oz = wok_verts_offset
    wok = WOKData(name=resref)
    wok.verts.extend((x + ox, y + oy, oz) for x, y in corners)
    wok.faces.append(WOKFace(0, 1, 2, 1, -1, -1, -1))
    wok.faces.append(WOKFace(0, 2, 3, 1, -1, -1, -1))
    primitive = ImportedMeshRoomPrimitive(
        room_resref=resref,
        surfaces=(surface,),
        source_model=resref,
        wok=wok,
        metadata={"wok_coordinate_space": "module"},
    )
    return AuthoredRoomSpec(
        room_resref=resref,
        primitive=primitive,
        position=position,
        metadata={"source": "stock_room_conversion", "source_model": resref},
    )


def _project(rooms):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject

    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grwokfix", game="K2", display_name="grwokfix", tag="grwokfix"),
        rooms=tuple(rooms),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grwokfix")),
        lights=(),
    )


def test_aligned_module_space_wok_passes_through_unchanged() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_walkmesh import combine_authored_module_walkmesh, resolve_room_wok_module_offset

    position = (30.0, 40.0, 0.0)
    room = _square_room(resref="alignedrm", position=position, wok_verts_offset=position)
    offset, warning = resolve_room_wok_module_offset(room)
    assert offset == (0.0, 0.0, 0.0)
    assert warning is None
    combined = combine_authored_module_walkmesh(_project([room]))
    xs = sorted({round(v[0], 3) for v in combined.wok.verts})
    assert xs == [25.0, 35.0]
    assert not any("declared module-space" in w for w in combined.warnings)


def test_mislabeled_room_local_wok_is_rebased_with_warning() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_walkmesh import (
        combine_authored_module_walkmesh,
        resolve_room_wok_module_offset,
        snap_position_to_authored_walkmesh,
    )

    # WOK vertices at room-local origin, room placed 21 units south: the
    # module-space label would leave the floor at Y 0 while the room renders
    # at Y -21 (the 921srtb shape).
    room = _square_room(resref="mislabeled", position=(0.0, -21.0, 0.0), wok_verts_offset=(0.0, 0.0, 0.0))
    offset, warning = resolve_room_wok_module_offset(room)
    assert offset == (0.0, -21.0, 0.0)
    assert warning is not None and "mislabeled" in warning and "room-local" in warning
    project = _project([room])
    combined = combine_authored_module_walkmesh(project)
    ys = sorted({round(v[1], 3) for v in combined.wok.verts})
    assert ys == [-26.0, -16.0]
    assert any("declared module-space" in w for w in combined.warnings)
    # The room WOK object itself is untouched (compile passthrough is shared).
    assert sorted({round(v[1], 3) for v in room.primitive.wok.verts}) == [-5.0, 5.0]
    # The player-start position under the room now snaps onto a walkable face.
    snapped = snap_position_to_authored_walkmesh(project, (0.0, -21.0, 0.0))
    assert snapped is not None and snapped.inside_face


def test_alignment_ignores_non_render_and_background_surfaces() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import ImportedMeshSurface
    from src.core.modules.authored_module_walkmesh import resolve_room_wok_module_offset

    position = (100.0, 0.0, 0.0)
    room = _square_room(resref="filtered", position=position, wok_verts_offset=position)

    def distractor(name: str, **flags):
        return ImportedMeshSurface(
            name=name,
            texture="ignored",
            vertices=((195.0, -5.0, 0.0), (205.0, -5.0, 0.0), (205.0, 5.0, 0.0), (195.0, 5.0, 0.0)),
            faces=((0, 1, 2), (0, 2, 3)),
            **flags,
        )

    primitive = replace(
        room.primitive,
        surfaces=room.primitive.surfaces + (
            distractor("backdrop", backdrop=True),
            distractor("background", background_geometry=True),
            distractor("hidden", render=False),
        ),
    )
    room = replace(room, primitive=primitive)
    offset, warning = resolve_room_wok_module_offset(room)
    assert offset == (0.0, 0.0, 0.0)
    assert warning is None


def test_export_rebases_correctly_labeled_room_local_generated_wok() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import generate_room_walkmesh_from_geometry
    from src.core.modules.authored_module_export import build_authored_module

    position = (30.0, 40.0, 0.0)
    room = _square_room(resref="generated", position=position, wok_verts_offset=(0.0, 0.0, 0.0))
    generated, report = generate_room_walkmesh_from_geometry(
        room.primitive,
        source_wok_policy="replace",
    )
    assert report["floor_faces"] == 2
    assert generated.metadata["wok_coordinate_space"] == "room_local"
    room = replace(room, primitive=generated)

    build = build_authored_module(_project([room]))
    exported_wok = build.module.room_woks["generated"]
    assert sorted({round(vertex[0], 3) for vertex in exported_wok.verts}) == [25.0, 35.0]
    assert sorted({round(vertex[1], 3) for vertex in exported_wok.verts}) == [35.0, 45.0]
    # Export rebases a copy; the undo/project snapshot remains room-local.
    assert sorted({round(vertex[0], 3) for vertex in generated.wok.verts}) == [-5.0, 5.0]


def test_walkmesh_status_reports_the_alignment_repair() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_walkmesh_status import authored_walkmesh_status_for_project

    room = _square_room(resref="mislabeled", position=(0.0, -21.0, 0.0), wok_verts_offset=(0.0, 0.0, 0.0))
    status = authored_walkmesh_status_for_project(_project([room]))
    assert any("declared module-space" in warning for warning in status.warnings)


def test_offset_wok_data_copies_without_mutating_source() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_walkmesh import offset_wok_data
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(name="src")
    wok.verts.extend([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)])
    wok.faces.append(WOKFace(0, 1, 2, 1, -1, -1, -1))
    moved = offset_wok_data(wok, (10.0, -2.0, 0.5))
    assert moved is not wok
    assert moved.verts[0] == (10.0, -2.0, 0.5)
    assert wok.verts[0] == (0.0, 0.0, 0.0)
    assert offset_wok_data(wok, (0.0, 0.0, 0.0)) is wok
