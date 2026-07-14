"""KOTOR 2 round-trip smoke: does the plcaa pipeline work for TSL?

Same flow as plcaa_cleanup_matrix but against the K2 install: import a
stock K2 module -> convert rooms to editable meshes -> run a GModeler op ->
export a game-ready module with K2 MDL headers -> verify the package.
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
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
from src.core.modules.module_editor_controller import ModuleEditorController

K2_ROOT = Path(os.environ.get("GHOSTRIGGER_K2_ROOT", r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"))
MODULE = os.environ.get("GHOSTRIGGER_K2_SMOKE_MODULE", "001ebo")

RESULTS: list[tuple[str, str, str]] = []


def record(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", str(detail)[:120]))
    print(f"{name:52} {'PASS' if ok else 'FAIL':6} {str(detail)[:120]}", flush=True)


def authored_of(c):
    return authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name=MODULE, fallback_game="K2"
    )


if not K2_ROOT.exists():
    record("K01 KOTOR 2 install found", False, str(K2_ROOT))
    sys.exit(1)
record("K01 KOTOR 2 install found", True, str(K2_ROOT))

rm = ResourceManager()
record("K02 ResourceManager indexes K2", rm.set_k2_dir(str(K2_ROOT)), "")

c = ModuleEditorController()
c.new_project(name=MODULE, game="K2")
ok, message = c.import_stock_module_from_rim(
    module_resref=MODULE,
    modules_dir=str(K2_ROOT / "Modules"),
    game="K2",
    resource_manager=rm,
)
record(f"K03 import stock {MODULE} module", ok, message)
if not ok:
    sys.exit(1)

# Stock fidelity is measured against the real BIF-backed LYT/VIS, not against
# the placeholder rows produced by our importer.
from pykotor.extract.installation import Installation
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.formats.vis import read_vis
from pykotor.resource.type import ResourceType as RT

installation = Installation(K2_ROOT)
vanilla_lyt_resource = installation.resource(MODULE, RT.LYT)
vanilla_vis_resource = installation.resource(MODULE, RT.VIS)
imported = authored_of(c)
candidate_positions = {
    room.normalised_resref(): tuple(float(value) for value in room.position)
    for room in imported.rooms
}
candidate_visibility = {
    room.normalised_resref(): {_normal.lower() for _normal in room.visible_rooms}
    for room in imported.rooms
}
vanilla_positions = {}
vanilla_visibility = {}
if vanilla_lyt_resource is not None:
    vanilla_lyt = read_lyt(vanilla_lyt_resource.data)
    vanilla_positions = {
        str(room.model).lower(): (
            float(room.position.x),
            float(room.position.y),
            float(room.position.z),
        )
        for room in vanilla_lyt.rooms
    }
if vanilla_vis_resource is not None:
    vanilla_vis = read_vis(vanilla_vis_resource.data)
    vanilla_visibility = {
        str(room).lower(): {str(target).lower() for target in targets}
        for room, targets in vanilla_vis._visibility.items()
    }
record(
    "K03b stock LYT positions preserved from vanilla",
    candidate_positions == vanilla_positions,
    f"candidate={len(set(candidate_positions.values()))} unique, vanilla={len(set(vanilla_positions.values()))} unique",
)
record(
    "K03c stock VIS adjacency preserved from vanilla",
    candidate_visibility == vanilla_visibility,
    f"candidate={sum(map(len, candidate_visibility.values()))} links, vanilla={sum(map(len, vanilla_visibility.values()))} links",
)

ok, message = c.convert_all_stock_rooms_to_imported_mesh(resource_manager=rm)
record("K04 convert stock rooms to editable meshes", ok, message)

authored = authored_of(c)
mesh_rooms = [
    room.normalised_resref()
    for room in authored.rooms
    if isinstance(room.primitive, ImportedMeshRoomPrimitive)
]
total_faces = sum(
    len(surface.faces)
    for room in authored.rooms
    if isinstance(room.primitive, ImportedMeshRoomPrimitive)
    for surface in room.primitive.surfaces
)
woks = sum(
    1
    for room in authored.rooms
    if isinstance(room.primitive, ImportedMeshRoomPrimitive) and room.primitive.wok is not None
)
record(
    "K05 rooms editable with stock WOKs",
    len(mesh_rooms) >= 1,
    f"{len(mesh_rooms)} rooms, {total_faces} faces, {woks} stock WOKs",
)

# Dummy rooms with no render geometry stay placeholders; a user deletes them
# rather than shipping a placeholder slab.
placeholders = [
    room.normalised_resref()
    for room in authored.rooms
    if not isinstance(room.primitive, ImportedMeshRoomPrimitive)
]
if placeholders:
    ok, message = c.delete_map_studio_rooms(placeholders)
    record("K05b delete placeholder dummy rooms", ok, f"{placeholders} -> {message}")

# One real GModeler edit, exactly like the plcaa cleanup path.
target = mesh_rooms[0]
before = sum(len(s.faces) for s in authored.rooms[0].primitive.surfaces) if authored.rooms else 0
ok, message = c.delete_imported_mesh_room_faces(room_resref=target, mesh_role="render", face_indices=[0])
record("K06 GModeler face delete on K2 room", ok, message)

# Spawn on a walkable face of the entry room, then export.
prim = next(room.primitive for room in authored_of(c).rooms if room.normalised_resref() == target)
if prim.wok is not None:
    walk_face = next((f for f in prim.wok.faces if f.surface not in (7, 0)), None)
    if walk_face is not None:
        corners = (walk_face.v1, walk_face.v2, walk_face.v3)
        centroid = tuple(sum(float(prim.wok.verts[v][i]) for v in corners) / 3.0 for i in range(3))
        c.set_authored_module_entry_point(area_resref=MODULE, position=centroid, facing=0.0)

from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

out_dir = ROOT / "artifacts" / "map_studio" / "k2_roundtrip_smoke"
shutil.rmtree(out_dir, ignore_errors=True)
out_dir.mkdir(parents=True, exist_ok=True)
result = export_authored_module_project(
    AuthoredModuleExportRequest(project=authored_of(c), output_dir=str(out_dir), game_root_dir=str(K2_ROOT))
)
kinds = {entry.restype for entry in result.resources}
record(
    "K07 export K2 module",
    result.ok and not result.blocking_issues and {"mdl", "wok", "lyt", "are", "git", "ifo"} <= kinds,
    f"kinds={sorted(kinds)} blocking={result.blocking_issues[:1]}",
)
verification = result.package_verification
record(
    "K08 package verification (GFF/WOK/MDL readback)",
    verification is not None and verification.ok,
    getattr(verification, "message", "no verification"),
)
record(
    "K09 module package written",
    bool(result.module_path) and Path(str(result.module_path)).exists(),
    str(result.module_path),
)

# K2 MDL fingerprint: the emitted model must carry K2 PC function pointers.
fp1 = -1
if result.module_path and Path(str(result.module_path)).exists():
    import struct

    from pykotor.extract.capsule import LazyCapsule

    for item in LazyCapsule(Path(str(result.module_path))):
        if item.restype().extension.lower() == "mdl":
            data = bytes(item.data() or b"")
            fp1 = struct.unpack_from("<I", data, 12)[0]
            break
record("K10 emitted MDL uses K2 function pointers", fp1 == 4285200, f"fp1={fp1} (K2 PC = 4285200)")

print()
fails = sum(1 for _n, s, _d in RESULTS if s == "FAIL")
print(f"{'K2 ROUND-TRIP STEP':52} {'RESULT':6} DETAIL")
print("-" * 125)
for name, status, detail in RESULTS:
    print(f"{name:52} {status:6} {detail}")
print("-" * 125)
print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")
raise SystemExit(1 if fails else 0)
