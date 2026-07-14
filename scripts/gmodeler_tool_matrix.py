"""Headless GModeler tool matrix: run EVERY wired tool against a cube.

Empirical pass/fail data for each Map Studio modeling tool, exercised the
same way the window calls the controller. Two subjects:
  A. an imported-mesh cube room (the converted-stock-room path GModeler owns)
  B. an authored composition cube primitive (Create menu path)
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.core.modules.authored_imported_mesh import (
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
)
from src.core.modules.authored_module_kmap_bridge import (
    authored_project_from_kmap_payload,
    authored_project_to_kmap_payload,
)
from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
from src.core.modules.authored_module_project import (
    AuthoredModuleMetadata,
    AuthoredModuleProject,
    AuthoredRoomSpec,
)
from src.core.modules.module_editor_controller import ModuleEditorController

RESULTS: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, "PASS" if ok else "FAIL", detail[:110]))


def run(name: str, fn) -> None:
    try:
        ok, detail = fn()
        record(name, ok, detail)
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {exc}")


def _cube_surfaces() -> tuple[ImportedMeshSurface, ...]:
    v = (
        (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0),
        (0.0, 0.0, 3.0), (4.0, 0.0, 3.0), (4.0, 4.0, 3.0), (0.0, 4.0, 3.0),
    )
    faces = (
        (0, 1, 2), (0, 2, 3),          # floor
        (4, 6, 5), (4, 7, 6),          # ceiling
        (0, 4, 5), (0, 5, 1),          # walls
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    )
    uvs = tuple((p[0] / 4.0, p[1] / 4.0) for p in v)
    return (
        ImportedMeshSurface(
            name="cube",
            texture="lda_wall01",
            vertices=v,
            faces=faces,
            uvs=uvs,
            normals=((0.0, 0.0, 1.0),) * len(v),
        ),
    )


def fresh_controller() -> ModuleEditorController:
    c = ModuleEditorController()
    c.new_project(name="grcube01", game="K1")
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grcube01", game="K1", display_name="cube lab", tag="grcube01"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grcube01_room",
                primitive=ImportedMeshRoomPrimitive(room_resref="grcube01_room", surfaces=_cube_surfaces(), game="K1"),
            ),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grcube01")),
    )
    c.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    return c


def face_count(c: ModuleEditorController) -> int:
    authored = authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grcube01", fallback_game="K1"
    )
    room = authored.rooms[0]
    return sum(len(s.faces) for s in room.primitive.surfaces)


ROOM = "grcube01_room"
ROLE = "render"

# ---------------- A. imported-mesh cube: every wired GModeler op ----------------

def t_face_delete_single():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.delete_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[0])
    return ok and face_count(c) == before - 1, msg

def t_face_delete_multi():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.delete_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[0, 3, 5])
    return ok and face_count(c) == before - 3, msg

def t_face_extrude():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.extrude_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[2], distance=1.5)
    return ok and face_count(c) > before, msg

def t_face_inset():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.inset_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[2], inset=0.4)
    return ok and face_count(c) == before + 6, msg

def t_face_move():
    c = fresh_controller()
    ok, msg = c.move_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[2], delta=(0.0, 0.0, 0.5))
    return ok, msg

def t_face_flat():
    c = fresh_controller()
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="face_flat", mesh_role=ROLE, face_index=0, face_indices=(0, 1))
    return ok, msg

def t_face_flip():
    c = fresh_controller()
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="face_flip", mesh_role=ROLE, face_index=0, face_indices=(0,))
    return ok, msg

def t_face_split():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="face_split", mesh_role=ROLE, face_index=0)
    return ok and face_count(c) == before + 2, msg

def t_face_set_texture():
    c = fresh_controller()
    ok, msg = c.set_imported_mesh_room_face_texture(room_resref=ROOM, mesh_role=ROLE, face_indices=[0], texture="lda_grate01")
    return ok, msg

def t_edge_move():
    c = fresh_controller()
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="edge_move", mesh_role=ROLE, face_index=0, edge_corners=(0, 1), delta=(0.0, 0.0, 0.4))
    return ok, msg

def t_edge_bevel():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(
        room_resref=ROOM,
        op="edge_bevel",
        mesh_role=ROLE,
        face_index=0,
        edge_corners=(0, 1),
        amount=0.25,
    )
    authored = authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grcube01", fallback_game="K1"
    )
    surface = authored.rooms[0].primitive.surfaces[0]
    areas = []
    for face in surface.faces:
        a, b, d = (surface.vertices[index] for index in face)
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ad = (d[0] - a[0], d[1] - a[1], d[2] - a[2])
        cross = (
            ab[1] * ad[2] - ab[2] * ad[1],
            ab[2] * ad[0] - ab[0] * ad[2],
            ab[0] * ad[1] - ab[1] * ad[0],
        )
        areas.append(sum(value * value for value in cross) ** 0.5 * 0.5)
    return ok and len(surface.faces) > before and min(areas, default=0.0) > 1.0e-7, (
        f"{msg}; faces={len(surface.faces)}; min_area={min(areas, default=0.0):.6f}"
    )

def t_edge_split():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="edge_split", mesh_role=ROLE, face_index=0, edge_corners=(0, 2))
    return ok and face_count(c) > before, msg

def t_edge_collapse():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="edge_collapse", mesh_role=ROLE, face_index=0, edge_corners=(0, 1))
    return ok and face_count(c) < before, msg

def t_edge_delete():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="edge_delete", mesh_role=ROLE, face_index=0, edge_corners=(0, 2))
    return ok and face_count(c) < before, msg

def t_vertex_move():
    c = fresh_controller()
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="vertex_move", mesh_role=ROLE, face_index=0, vertex_corner=0, delta=(0.2, 0.0, 0.0))
    return ok, msg

def t_vertex_weld():
    c = fresh_controller()
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="vertex_weld", mesh_role=ROLE, face_index=0, vertex_corner=0, max_distance=5.0)
    return ok, msg

def t_vertex_delete():
    c = fresh_controller(); before = face_count(c)
    ok, msg = c.apply_imported_mesh_room_component_op(room_resref=ROOM, op="vertex_delete", mesh_role=ROLE, face_index=0, vertex_corner=0)
    return ok and face_count(c) < before, msg

def t_undo_after_edit():
    c = fresh_controller(); before = face_count(c)
    c.delete_imported_mesh_room_faces(room_resref=ROOM, mesh_role=ROLE, face_indices=[0])
    if not c.can_undo_map_studio_command():
        return False, "no undo checkpoint"
    c.undo_map_studio_command()
    return face_count(c) == before, f"faces {face_count(c)}/{before}"

def t_delete_whole_room():
    c = fresh_controller()
    ok, msg = c.delete_map_studio_rooms([ROOM])
    return ok, msg

def t_export_cube_module(tmp=Path(os.environ.get("TEMP", "/tmp")) / "grcube_export"):
    import shutil
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    c = fresh_controller()
    authored = authored_project_from_kmap_payload(c.project.extra_sections["authored_module"], fallback_name="grcube01", fallback_game="K1")
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True, exist_ok=True)
    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp)))
    kinds = {entry.restype for entry in result.resources}
    return (not result.blocking_issues) and {"mdl", "wok", "lyt", "are", "git", "ifo"} <= kinds, f"kinds={sorted(kinds)} blocking={result.blocking_issues[:1]}"

# ---------------- B. composition cube primitive (Create menu path) ----------------

def t_primitive_create_cube():
    c = ModuleEditorController(); c.new_project(name="grprim01", game="K1")
    c.add_authored_room_primitive(primitive_kind="cube", primitive_name="box1")
    rows = c.authored_room_primitive_transforms()
    return any(str(getattr(r, "primitive_name", "")) == "box1" for r in rows), f"{len(rows)} primitives"

def _prim_controller():
    c = ModuleEditorController(); c.new_project(name="grprim01", game="K1")
    c.add_authored_room_primitive(primitive_kind="cube", primitive_name="box1")
    rows = c.authored_room_primitive_transforms()
    room = str(getattr(rows[0], "room_resref", ""))
    return c, room

def t_primitive_gmodeler_face_delete():
    c, room = _prim_controller()
    ok, msg = c.delete_imported_mesh_room_faces(room_resref=room, mesh_role="helper_1", face_indices=[0])
    return ok, msg  # expected FAIL today: primitives are not imported meshes

def t_primitive_delete_object():
    c, room = _prim_controller()
    result = c.remove_authored_room_primitive(room_resref=room, primitive_name="box1")
    rows = c.authored_room_primitive_transforms()
    return not any(str(getattr(r, "primitive_name", "")) == "box1" for r in rows), f"{len(rows)} primitives left"

def t_primitive_center_pivot():
    c, room = _prim_controller()
    result = c.center_authored_room_primitive_pivot(room_resref=room, primitive_name="box1") if hasattr(c, "center_authored_room_primitive_pivot") else None
    return result is not None, "controller method exists" if result is not None else "NO controller method"

def t_primitive_freeze_transform():
    c, room = _prim_controller()
    result = c.freeze_authored_room_primitive_transform(room_resref=room, primitive_name="box1") if hasattr(c, "freeze_authored_room_primitive_transform") else None
    return result is not None, "controller method exists" if result is not None else "NO controller method"

def t_primitive_multi_select_combine():
    c, room = _prim_controller()
    names = [
        str(getattr(row, "primitive_name", "") or "")
        for row in c.authored_room_primitive_transforms()
        if str(getattr(row, "room_resref", "") or "") == room
        and str(getattr(row, "primitive_type", "") or "") != "plane"
    ][-2:]
    ids = [f"authored_primitive:{room}:{name}" for name in names]
    c.model.select_many(ids)
    c.combine_authored_room_primitives(room_resref=room, primitive_names=names)
    authored = authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grprim01", fallback_game="K1"
    )
    target = next(value for value in authored.rooms if value.room_resref == room)
    combined = [primitive for primitive in target.primitive.primitives if type(primitive).__name__ == "CombinedRoomPrimitive"]
    return (
        len(c.model.selected_ids) == 2 and len(combined) == 1,
        f"selected={len(c.model.selected_ids)} combined_meshes={len(combined)}",
    )

def t_primitive_separate_object():
    c, room = _prim_controller()
    names = [
        str(getattr(row, "primitive_name", "") or "")
        for row in c.authored_room_primitive_transforms()
        if str(getattr(row, "room_resref", "") or "") == room
        and str(getattr(row, "primitive_type", "") or "") != "plane"
    ][-2:]
    c.combine_authored_room_primitives(room_resref=room, primitive_names=names, group_name="combined_for_shells")
    before_rooms = len(authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grprim01", fallback_game="K1"
    ).rooms)
    c.separate_authored_room_primitive_shells(
        room_resref=room, primitive_name="combined_for_shells", name_prefix="shell"
    )
    rows = [
        row for row in c.authored_room_primitive_transforms()
        if str(getattr(row, "room_resref", "") or "") == room
        and str(getattr(row, "primitive_name", "") or "").startswith("shell_")
    ]
    after_rooms = len(authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grprim01", fallback_game="K1"
    ).rooms)
    return len(rows) >= 2 and after_rooms == before_rooms, f"shells={len(rows)} rooms={before_rooms}->{after_rooms}"


TESTS = [
    ("A01 face_delete single", t_face_delete_single),
    ("A02 face_delete multi (Shift-select batch)", t_face_delete_multi),
    ("A03 face_extrude", t_face_extrude),
    ("A04 face_inset", t_face_inset),
    ("A05 face_move", t_face_move),
    ("A06 face_flat", t_face_flat),
    ("A07 face_flip", t_face_flip),
    ("A08 face_split", t_face_split),
    ("A09 face_set_texture", t_face_set_texture),
    ("A10 edge_move", t_edge_move),
    ("A10b edge_bevel (Maya hard-edge chamfer)", t_edge_bevel),
    ("A11 edge_split", t_edge_split),
    ("A12 edge_collapse", t_edge_collapse),
    ("A13 edge_delete", t_edge_delete),
    ("A14 vertex_move", t_vertex_move),
    ("A15 vertex_weld", t_vertex_weld),
    ("A16 vertex_delete", t_vertex_delete),
    ("A17 undo after edit", t_undo_after_edit),
    ("A18 delete whole room (object mode)", t_delete_whole_room),
    ("A19 export cube as module", t_export_cube_module),
    ("B01 create cube primitive", t_primitive_create_cube),
    ("B02 GModeler face op on primitive", t_primitive_gmodeler_face_delete),
    ("B03 delete primitive object", t_primitive_delete_object),
    ("B04 center pivot (primitive)", t_primitive_center_pivot),
    ("B05 freeze transform (primitive)", t_primitive_freeze_transform),
    ("B06 select together + true mesh combine", t_primitive_multi_select_combine),
    ("B07 separate disconnected polygon shells", t_primitive_separate_object),
]

def main() -> int:
    for name, fn in TESTS:
        run(name, fn)

    print()
    print(f"{'TOOL':44} {'RESULT':6} DETAIL")
    print("-" * 100)
    fails = 0
    for name, status, detail in RESULTS:
        if status == "FAIL":
            fails += 1
        print(f"{name:44} {status:6} {detail}")
    print("-" * 100)
    print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")
    return fails


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
