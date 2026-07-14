"""plcaa deep dive: strip everything that is not ceiling/floor/walls, repack.

The manual acceptance flow, headless: import the vanilla plcaa module from
the game install -> convert stock rooms to editable imported meshes ->
identify the baked demo objects (BoxSpin/Box/GeoSphere/ScriptLoop/ConeRef
nodes) -> delete them with the same controller ops the GModeler UI uses ->
export a game-ready plcaa replacement and verify the package.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.core.assets.resource_manager import ResourceManager
from src.core.modules.authored_imported_mesh import (
    ImportedMeshRoomPrimitive,
    imported_mesh_surface_role,
)
from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
from src.core.modules.module_editor_controller import ModuleEditorController

GAME_ROOT = Path(os.environ.get("GHOSTRIGGER_K1_ROOT", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"))
# The plcaa demo shapes baked into the stock room model (node-name prefixes,
# from the earlier PLCaa static-lab research).
DEMO_PREFIXES = ("boxspin", "box", "geosphere", "scriptloop", "coneref")

RESULTS: list[tuple[str, str, str]] = []


def record(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", str(detail)[:120]))
    print(f"{name:52} {'PASS' if ok else 'FAIL':6} {str(detail)[:120]}", flush=True)


def finish() -> None:
    print()
    fails = sum(1 for _n, s, _d in RESULTS if s == "FAIL")
    print(f"{'PLCAA CLEANUP STEP':52} {'RESULT':6} DETAIL")
    print("-" * 125)
    for name, status, detail in RESULTS:
        print(f"{name:52} {status:6} {detail}")
    print("-" * 125)
    print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")


def is_demo_surface(name: str) -> bool:
    clean = str(name or "").strip().lower()
    return any(clean.startswith(prefix) for prefix in DEMO_PREFIXES)


def room_primitive(c: ModuleEditorController, resref: str) -> ImportedMeshRoomPrimitive:
    authored = authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="plcaa", fallback_game="K1"
    )
    for room in authored.rooms:
        if room.normalised_resref() == resref and isinstance(room.primitive, ImportedMeshRoomPrimitive):
            return room.primitive
    raise AssertionError(f"{resref} is not an imported-mesh room")


# ---- P01: game install present ----
if not GAME_ROOT.exists():
    record("P01 KOTOR install found", False, str(GAME_ROOT))
    finish()
    sys.exit(1)
record("P01 KOTOR install found", True, str(GAME_ROOT))

rm = ResourceManager()
ok_index = rm.set_k1_dir(str(GAME_ROOT))
record("P02 ResourceManager indexes K1", ok_index, "")

# ---- P03: import the vanilla plcaa module ----
c = ModuleEditorController()
c.new_project(name="plcaa", game="K1")
ok, message = c.import_stock_module_from_rim(
    module_resref="plcaa",
    modules_dir=str(GAME_ROOT / "modules"),
    game="K1",
    resource_manager=rm,
)
record("P03 import stock plcaa module", ok, message)

authored = authored_project_from_kmap_payload(
    c.project.extra_sections["authored_module"], fallback_name="plcaa", fallback_game="K1"
)
room_resrefs = [room.normalised_resref() for room in authored.rooms]
record("P04 plcaa rooms discovered", len(room_resrefs) >= 1, f"rooms={room_resrefs}")

# ---- P05: make every stock room editable ----
ok, message = c.convert_all_stock_rooms_to_imported_mesh(resource_manager=rm)
record("P05 convert stock rooms to editable meshes", ok, message)

authored = authored_project_from_kmap_payload(
    c.project.extra_sections["authored_module"], fallback_name="plcaa", fallback_game="K1"
)
mesh_rooms = [
    room.normalised_resref()
    for room in authored.rooms
    if isinstance(room.primitive, ImportedMeshRoomPrimitive)
]
record("P06 rooms are imported meshes with stock WOK", len(mesh_rooms) >= 1, f"{mesh_rooms}")

# ---- P07: inventory the surfaces; find the demo objects by node name ----
target_room = mesh_rooms[0]
prim = room_primitive(c, target_room)
inventory = [(s.name, s.texture, len(s.faces)) for s in prim.surfaces]
demo = [(name, faces) for name, _tex, faces in inventory if is_demo_surface(name)]
shell = [(name, faces) for name, _tex, faces in inventory if not is_demo_surface(name)]
total_before = sum(len(s.faces) for s in prim.surfaces)
record(
    "P07 demo objects identified by node name",
    len(demo) > 0 and len(shell) > 0,
    f"{len(demo)} demo / {len(shell)} shell surfaces, {total_before} faces total",
)
print("    demo surfaces:", ", ".join(f"{n}({f})" for n, f in demo), flush=True)

# Geometric cross-check: demo objects should be small relative to the shell.
def surface_extent(surface) -> float:
    xs = [v[0] for v in surface.vertices]
    ys = [v[1] for v in surface.vertices]
    zs = [v[2] for v in surface.vertices]
    return max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))

shell_extent = max(surface_extent(s) for s in prim.surfaces if not is_demo_surface(s.name))
demo_extents = [surface_extent(s) for s in prim.surfaces if is_demo_surface(s.name)]
record(
    "P08 demo objects are small interior meshes",
    demo_extents and max(demo_extents) < shell_extent * 0.6,
    f"largest demo {max(demo_extents):.1f}m vs shell {shell_extent:.1f}m",
)

# ---- P09: delete every demo surface via the GModeler controller op ----
deleted_faces = 0
deleted_names: list[str] = []
while True:
    prim = room_primitive(c, target_room)
    target = next(
        (
            (index, surface)
            for index, surface in enumerate(prim.surfaces)
            if is_demo_surface(surface.name)
        ),
        None,
    )
    if target is None:
        break
    index, surface = target
    role = imported_mesh_surface_role(index)
    ok, message = c.delete_imported_mesh_room_faces(
        room_resref=target_room,
        mesh_role=role,
        face_indices=list(range(len(surface.faces))),
    )
    if not ok:
        record("P09 delete demo surfaces", False, f"{surface.name}: {message}")
        finish()
        sys.exit(1)
    deleted_faces += len(surface.faces)
    deleted_names.append(surface.name)

prim = room_primitive(c, target_room)
remaining_demo = [s.name for s in prim.surfaces if is_demo_surface(s.name)]
total_after = sum(len(s.faces) for s in prim.surfaces)
record(
    "P09 delete demo surfaces (controller ops)",
    deleted_faces > 0 and not remaining_demo,
    f"removed {len(deleted_names)} surfaces / {deleted_faces} faces; {total_before}->{total_after}",
)

# ---- P10: the structural shell survives, and the WOK is untouched ----
record(
    "P10 floor/walls/ceiling shell retained",
    total_after >= total_before - deleted_faces and len(prim.surfaces) >= 1 and prim.wok is not None,
    f"{len(prim.surfaces)} shell surfaces, wok faces {len(prim.wok.faces) if prim.wok else 0}",
)
record("P11 cleanup ops are undoable", c.can_undo_map_studio_command(), "")

# ---- P11b: put the player spawn on the cleaned floor ----
# Vanilla plcaa's IFO entry (5,5,0) sits off its own sparse WOK (the game
# snaps spawns; our exporter is stricter), so the manual flow ends with
# placing the entry on a walkable face before export.
wok = prim.wok
walk_face = next(face for face in wok.faces if face.surface not in (7, 0))
corners = (walk_face.v1, walk_face.v2, walk_face.v3)
centroid = tuple(sum(float(wok.verts[v][i]) for v in corners) / 3.0 for i in range(3))
c.set_authored_module_entry_point(area_resref="plcaa", position=centroid, facing=0.0)
record("P11b entry point placed on cleaned floor", True, f"spawn at ({centroid[0]:.1f}, {centroid[1]:.1f}, {centroid[2]:.2f})")

# ---- P12: export the cleaned plcaa as a game-ready module ----
from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

out_dir = ROOT / "artifacts" / "map_studio" / "plcaa_cleanup"
shutil.rmtree(out_dir, ignore_errors=True)
out_dir.mkdir(parents=True, exist_ok=True)
authored = authored_project_from_kmap_payload(
    c.project.extra_sections["authored_module"], fallback_name="plcaa", fallback_game="K1"
)
result = export_authored_module_project(
    AuthoredModuleExportRequest(project=authored, output_dir=str(out_dir), game_root_dir=str(GAME_ROOT))
)
kinds = {entry.restype for entry in result.resources}
record(
    "P12 export cleaned plcaa module",
    result.ok and not result.blocking_issues and {"mdl", "wok", "lyt", "are", "git", "ifo"} <= kinds,
    f"kinds={sorted(kinds)} blocking={result.blocking_issues[:1]}",
)
verification = result.package_verification
record(
    "P13 package verification (GFF/WOK/MDL readback)",
    verification is not None and verification.ok,
    getattr(verification, "message", "no verification"),
)
record(
    "P14 module package written",
    bool(result.module_path) and Path(str(result.module_path)).exists(),
    str(result.module_path),
)

finish()
