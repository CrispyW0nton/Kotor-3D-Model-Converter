"""Fill Floor Faces: patch imported WOKs from visible floor geometry.

Converted candidate modules ship rooms whose imported WOK covers only part
of the rendered floor (921srt's custom throne room: the corridor to the next
room renders floor but has no walkmesh, so PIE and the game stop the player
at an invisible cliff).  The fill op adds walkable faces for uncovered
near-horizontal render triangles, in the WOK's own coordinate frame.
"""

from __future__ import annotations

import os
import struct
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


def _primitive(*, wok_offset=(0.0, 0.0, 0.0)):
    """A 20x10 floor whose WOK covers only the west half (x 0..10).

    The render surface also carries a steep wall so the slope filter is
    exercised.  ``wok_offset`` shifts the WOK's coordinate frame to model a
    module-space WOK (render surfaces are always room-local).
    """

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.module_format import WOKData, WOKFace

    floor = ImportedMeshSurface(
        name="floor",
        texture="floor01",
        vertices=(
            # west half (already covered)
            (0.0, 0.0, 1.0), (10.0, 0.0, 1.0), (10.0, 10.0, 1.0), (0.0, 10.0, 1.0),
            # east half (uncovered, sharing the complete x=10 seam)
            (10.0, 0.0, 1.0), (20.0, 0.0, 1.0), (20.0, 10.0, 1.0), (10.0, 10.0, 1.0),
            # steep wall at the east edge
            (20.0, 0.0, 1.0), (20.0, 10.0, 1.0), (20.0, 10.0, 5.0), (20.0, 0.0, 5.0),
        ),
        faces=((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (8, 9, 10), (8, 10, 11)),
    )
    ox, oy, oz = wok_offset
    wok = WOKData(name="fillroom")
    wok.verts.extend([(0.0 + ox, 0.0 + oy, 1.0 + oz), (10.0 + ox, 0.0 + oy, 1.0 + oz),
                      (10.0 + ox, 10.0 + oy, 1.0 + oz), (0.0 + ox, 10.0 + oy, 1.0 + oz)])
    wok.faces.append(WOKFace(0, 1, 2, 4, -1, -1, -1))
    wok.faces.append(WOKFace(0, 2, 3, 4, -1, -1, -1))
    return ImportedMeshRoomPrimitive(
        room_resref="fillroom",
        surfaces=(floor,),
        source_model="fillroom",
        wok=wok,
        metadata={"wok_coordinate_space": "module"},
    )


def test_fill_adds_only_uncovered_floor_and_keeps_source_unmutated() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import fill_imported_wok_from_floor_surfaces
    from src.core.modules.authored_walkmesh_audit import audit_authored_wok

    primitive = _primitive()
    patched, report = fill_imported_wok_from_floor_surfaces(primitive)
    # The uncovered east half becomes walkable; the wall is skipped as steep.
    assert report["faces_added"] == 2
    assert report["faces_too_steep"] == 2
    assert len(patched.wok.faces) == len(primitive.wok.faces) + report["faces_added"]
    # Source primitive is untouched (shared with undo snapshots).
    assert len(primitive.wok.faces) == 2
    assert all(face.adj1 is not None for face in primitive.wok.faces)
    # Every patched face is walkable and inside the floor footprint.
    for face in patched.wok.faces[2:]:
        assert int(face.surface) == 4
        for index in (face.v1, face.v2, face.v3):
            x, y, z = patched.wok.verts[index]
            assert -0.01 <= x <= 20.01 and -0.01 <= y <= 10.01
            assert abs(z - 1.0) < 1e-6
    audit = audit_authored_wok("fillroom", patched.wok)
    assert audit.walkable_component_count == 1
    # One connected rectangular floor serializes as one closed perimeter.
    assert struct.unpack_from("<I", patched.wok.to_bytes(), 128)[0] == 1
    # Second run is a no-op: the floor is now fully covered.
    again, report2 = fill_imported_wok_from_floor_surfaces(patched)
    assert report2["faces_added"] == 0
    assert again is patched


def test_fill_rejects_positive_area_partial_overlap_instead_of_using_only_the_centroid() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import ImportedMeshSurface, fill_imported_wok_from_floor_surfaces

    primitive = _primitive()
    crossing = ImportedMeshSurface(
        name="crossing",
        texture="floor01",
        vertices=((0.0, 0.0, 1.0), (20.0, 0.0, 1.0), (20.0, 10.0, 1.0), (0.0, 10.0, 1.0)),
        faces=((0, 1, 2), (0, 2, 3)),
    )
    primitive = replace(primitive, surfaces=(crossing,))

    patched, report = fill_imported_wok_from_floor_surfaces(primitive)
    assert patched is primitive
    assert report["faces_added"] == 0
    assert report["faces_partial_overlap"] >= 1


def test_fill_drops_downward_ceiling_and_leaves_unstitched_island_unmodified() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import ImportedMeshSurface, fill_imported_wok_from_floor_surfaces

    primitive = _primitive()
    ceiling = ImportedMeshSurface(
        name="ceiling",
        texture="ceil",
        vertices=((10.0, 0.0, 4.0), (20.0, 10.0, 4.0), (20.0, 0.0, 4.0)),
        faces=((0, 1, 2),),
    )
    island = ImportedMeshSurface(
        name="island",
        texture="floor",
        vertices=((30.0, 0.0, 1.0), (40.0, 0.0, 1.0), (40.0, 10.0, 1.0), (30.0, 10.0, 1.0)),
        faces=((0, 1, 2), (0, 2, 3)),
    )
    primitive = replace(primitive, surfaces=primitive.surfaces + (ceiling, island))

    patched, report = fill_imported_wok_from_floor_surfaces(primitive)
    assert report["faces_downward"] == 1
    assert report["faces_unstitched"] == 2
    assert all(vertex[2] < 3.9 for vertex in patched.wok.verts)
    assert all(vertex[0] < 29.9 for vertex in patched.wok.verts)


def test_fill_respects_module_space_wok_frame() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_imported_mesh import fill_imported_wok_from_floor_surfaces

    offset = (100.0, -50.0, 0.0)
    primitive = _primitive(wok_offset=offset)
    # Without the frame mapping the whole floor looks uncovered (the koq/921srt
    # regression this test pins): the west half must be recognised as covered.
    patched, report = fill_imported_wok_from_floor_surfaces(primitive, render_to_wok_offset=offset)
    assert report["faces_already_covered"] >= 1
    for face in patched.wok.faces[2:]:
        for index in (face.v1, face.v2, face.v3):
            x, y, _z = patched.wok.verts[index]
            assert 100.0 - 0.01 <= x <= 120.01 and -60.01 <= y <= -39.99


def test_controller_fill_is_undoable_and_reports() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grfill", game="K2")
    primitive = _primitive()
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grfill", game="K2", display_name="grfill", tag="grfill"),
        rooms=(AuthoredRoomSpec(room_resref="fillroom", primitive=primitive, position=(0.0, 0.0, 0.0)),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grfill")),
        lights=(),
    )
    controller._store_authored_project(authored)
    ok, message = controller.fill_authored_room_wok_from_floors(room_resref="fillroom")
    assert ok, message
    assert "added" in message
    updated = controller._load_authored_project_or_raise()
    assert len(updated.rooms[0].primitive.wok.faces) > 2
    assert "wok_floor_fill" in dict(updated.rooms[0].primitive.metadata)
