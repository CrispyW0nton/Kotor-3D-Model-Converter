"""Terrain deep dive: paint a heightfield headlessly, prove the WOK wraps it.

Pipeline: create terrain patch -> paint brush strokes (the manual user's
Terrain-mode brushes) -> verify the generated walkmesh follows the sculpted
surface exactly (verts, slope classification, adjacency) -> export a module
and read the WOK back with PyKotor -> live sculpt-session frames + undo.
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

from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
from src.core.modules.authored_terrain_builder import (
    TerrainHeightfieldPrimitive,
    analyse_terrain_slopes,
    build_terrain_mesh,
    build_terrain_wok,
)
from src.core.modules.module_editor_controller import ModuleEditorController

RESULTS: list[tuple[str, str, str]] = []


def record(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", str(detail)[:110]))
    print(f"{name:52} {'PASS' if ok else 'FAIL':6} {str(detail)[:110]}", flush=True)


def terrain_primitive(c: ModuleEditorController) -> TerrainHeightfieldPrimitive:
    authored = authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="grterr01", fallback_game="K1"
    )
    for room in authored.rooms:
        if isinstance(room.primitive, TerrainHeightfieldPrimitive):
            return room.primitive
    raise AssertionError("no terrain room")


def max_height(primitive) -> float:
    return max(max(float(v) for v in row) for row in primitive.heights)


# ---- T01: create a paintable terrain patch (auto-creates authored module) ----
c = ModuleEditorController()
c.new_project(name="grterr01", game="K1")
resref = c.create_terrain_patch(room_resref="grterr01_terrain", resolution=17, width=20.0, depth=20.0)
prim = terrain_primitive(c)
record("T01 create 17x17 terrain patch", resref == "grterr01_terrain" and len(prim.heights) == 17, resref)
record(
    "T01b new terrain starts as a flat sculptable plane",
    all(abs(float(height)) <= 1.0e-9 for row in prim.heights for height in row),
    f"{len(prim.heights)}x{len(prim.heights[0])} editable height samples",
)

# ---- T02: paint raise strokes like a user dragging the brush ----
# Hill painted OFF-CENTER: the module entry point spawns at the patch
# center, and export correctly refuses an entry on a too-steep face.
stroke = tuple((12 + drow, 12 + dcol, 1.0) for drow in (-1, 0, 1) for dcol in (-1, 0, 1))
c.apply_authored_terrain_brush_stroke(brush="raise", room_resref=resref, points=stroke, delta=0.15, radius=2, strength=0.8)
prim = terrain_primitive(c)
record("T02 raise brush lifts the surface", 0.3 < max_height(prim) < 3.0, f"max height {max_height(prim):.2f}m")

# ---- T03: smooth pass keeps the hill but relaxes it ----
peak_before = max_height(prim)
c.apply_authored_terrain_brush_stroke(brush="smooth", room_resref=resref, points=((12, 12, 1.0),), radius=3, strength=0.6, iterations=2)
prim = terrain_primitive(c)
record("T03 smooth brush relaxes the peak", 0.0 < max_height(prim) < peak_before, f"peak {peak_before:.2f} -> {max_height(prim):.2f}m")

# ---- T04: the WOK wraps the sculpted surface exactly ----
mesh = build_terrain_mesh(prim)
wok = build_terrain_wok(prim)
verts_match = len(wok.verts) == len(mesh.vertices) and all(
    abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) < 1.0e-9 for a, b in zip(wok.verts, mesh.vertices)
)
faces_match = len(wok.faces) == len(mesh.faces)
record("T04 WOK verts == sculpted render verts", verts_match and faces_match, f"{len(wok.verts)} verts, {len(wok.faces)} faces")

# ---- T05: gentle hill stays walkable ----
report = analyse_terrain_slopes(prim)
record(
    "T05 gentle hill fully walkable",
    report.non_walk_triangle_count == 0 and report.walkable_triangle_count == len(wok.faces),
    f"max slope {report.max_slope_degrees:.1f} deg, walkable {report.walkable_triangle_count}/{len(wok.faces)}",
)

# ---- T06: steep cliff auto-classifies as non-walk ----
c.apply_authored_terrain_brush_stroke(brush="raise", room_resref=resref, points=((3, 3, 1.0),), delta=8.0, radius=0)
prim = terrain_primitive(c)
wok = build_terrain_wok(prim)
walk_ids = {f.surface for f in wok.faces}
report = analyse_terrain_slopes(prim)
record(
    "T06 steep spike exports as non-walk faces",
    report.non_walk_triangle_count > 0 and len(walk_ids) >= 2,
    f"{report.non_walk_triangle_count} non-walk tris, surfaces {sorted(walk_ids)}",
)

# ---- T07: WOK adjacency is mutually consistent (creature pathing sanity) ----
def adjacency_consistent(wok) -> tuple[bool, str]:
    for index, face in enumerate(wok.faces):
        for adj in (face.adj1, face.adj2, face.adj3):
            if adj < 0:
                continue
            other = wok.faces[adj]
            if index not in (other.adj1, other.adj2, other.adj3):
                return False, f"face {index} -> {adj} not mutual"
    return True, f"{len(wok.faces)} faces checked"

ok_adj, detail = adjacency_consistent(wok)
record("T07 WOK adjacency mutual", ok_adj, detail)

# ---- T08: walkability overlay tracks the sculpt (viewport hover data) ----
overlay = c.authored_terrain_walkability_overlay()
triangles = tuple(getattr(overlay, "triangles", ()) or ())
non_walk_overlay = sum(1 for t in triangles if not bool(getattr(t, "walkable", True)))
record(
    "T08 walkability overlay tracks sculpt",
    len(triangles) == len(wok.faces) and non_walk_overlay == report.non_walk_triangle_count,
    f"{len(triangles)} tris, {non_walk_overlay} non-walk",
)

# ---- T09: undo removes the cliff (stroke = one undo entry) ----
peak_with_cliff = max_height(prim)
ok_undo = c.undo_map_studio_command()
prim = terrain_primitive(c)
record("T09 undo removes the cliff stroke", ok_undo and max_height(prim) < peak_with_cliff, f"peak {peak_with_cliff:.2f} -> {max_height(prim):.2f}m")

# ---- T10: live sculpt session (what the viewport brush drag calls) ----
# Gentle ridge: steeper than 35 degrees would (correctly) export non-walk.
frame_result = c.apply_map_studio_terrain_sculpt_frame(
    room_resref=resref, brush="raise", points=((12, 4, 1.0), (12, 5, 1.0)), delta=0.3, radius=2, force=True
)
c.commit_map_studio_terrain_sculpt_stroke(brush="raise", room_resref=resref)
prim = terrain_primitive(c)
row12 = max(float(v) for v in prim.heights[12])
record("T10 live sculpt frame + stroke commit", frame_result.applied and row12 > 0.3, f"row 12 peak {row12:.2f}m")
record("T10b sculpt stroke is undoable", c.can_undo_map_studio_command(), "")

# ---- T11: stage placements onto the sculpt, then export a game module ----
from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

c.shrink_wrap_authored_placements_to_terrain(room_resref=resref)
tmp = Path(os.environ.get("TEMP", "/tmp")) / "grterr_export"
shutil.rmtree(tmp, ignore_errors=True)
tmp.mkdir(parents=True, exist_ok=True)
authored = authored_project_from_kmap_payload(c.project.extra_sections["authored_module"], fallback_name="grterr01", fallback_game="K1")
result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp)))
kinds = {entry.restype for entry in result.resources}
record(
    "T11 export painted terrain (mdl/wok/lyt/are/git/ifo)",
    (not result.blocking_issues) and {"mdl", "wok", "lyt", "are", "git", "ifo"} <= kinds,
    f"kinds={sorted(kinds)} blocking={result.blocking_issues[:1]}",
)

# The engine-facing WOK is floor-only.  Its serialized BWM perimeter records,
# not synthetic vertical NON_WALK walls, define the walkable region.
wok_files = sorted(tmp.rglob("*.wok"))
if wok_files:
    from pykotor.resource.formats.bwm import read_bwm
    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    bwm = read_bwm(wok_files[0])
    walk_faces = bwm.walkable_faces()
    walk_max_z = max(float(v.z) for face in walk_faces for v in (face.v1, face.v2, face.v3))
    prim = terrain_primitive(c)
    record(
        "T12 exported walkable faces wrap the sculpt",
        abs(walk_max_z - max_height(prim)) < 1.0e-4 and len(walk_faces) > 0,
        f"walkable max z {walk_max_z:.2f}m vs painted {max_height(prim):.2f}m ({len(walk_faces)} walkable faces)",
    )
    wok_fingerprint, wok_report = inspect_raw_wok_structure(resref, wok_files[0].read_bytes())
    record(
        "T13 raw WOK perimeter is serialized and closed",
        not wok_report.has_errors
        and wok_fingerprint.perimeter_count >= 1
        and wok_fingerprint.closed_perimeter_count == wok_fingerprint.perimeter_count,
        f"{wok_fingerprint.closed_perimeter_count}/{wok_fingerprint.perimeter_count} closed loop(s)",
    )
else:
    record("T12 exported walkable faces wrap the sculpt", False, "no .wok file written")

# ---- T14: sculpted mesh normals follow the slope (lighting quality) ----
prim = terrain_primitive(c)
mesh = build_terrain_mesh(prim)
tilted = sum(1 for n in mesh.normals if abs(1.0 - float(n[2])) > 1.0e-3)
record("T14 mesh normals follow the sculpted slope", tilted > 0, f"{tilted}/{len(mesh.normals)} normals tilted")

# ---- T15: ramp brush golden — monotonic walkable grade along the stroke ----
c.apply_authored_terrain_brush_stroke(
    brush="ramp",
    room_resref=resref,
    points=((2, 2, 1.0), (2, 6, 1.0), (2, 10, 1.0)),
    delta=0.25,
    radius=1,
)
prim = terrain_primitive(c)
grade = [float(prim.heights[2][column]) for column in (2, 6, 10)]
monotonic = grade[0] <= grade[1] <= grade[2] or grade[0] >= grade[1] >= grade[2]
ramp_report = analyse_terrain_slopes(prim)
record(
    "T15 ramp brush grades monotonically and stays walkable",
    monotonic and grade[0] != grade[2] and ramp_report.walkable_triangle_count > 0,
    f"grade {grade[0]:.2f} -> {grade[1]:.2f} -> {grade[2]:.2f}m, max slope {ramp_report.max_slope_degrees:.1f} deg",
)

# ---- T16/T17: carve a hole; the raw exported WOK gains an interior loop ----
faces_before_hole = len(build_terrain_wok(terrain_primitive(c)).faces)
# Carve away from the shrink-wrapped entry point/placements: the export gate
# correctly blocks modules whose entry point sits over a hole.
c.apply_authored_terrain_operation(operation="carve_hole", room_resref=resref, row_index=4, column_index=12, radius=1)
prim = terrain_primitive(c)
faces_after_hole = len(build_terrain_wok(prim).faces)
record(
    "T16 carve_hole removes floor cells from mesh and WOK",
    len(prim.holes) == 9 and faces_after_hole == faces_before_hole - 18,
    f"{faces_before_hole} -> {faces_after_hole} faces, {len(prim.holes)} holed cell(s)",
)
tmp_hole = Path(os.environ.get("TEMP", "/tmp")) / "grterr_export_hole"
shutil.rmtree(tmp_hole, ignore_errors=True)
tmp_hole.mkdir(parents=True, exist_ok=True)
authored = authored_project_from_kmap_payload(c.project.extra_sections["authored_module"], fallback_name="grterr01", fallback_game="K1")
hole_result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_hole)))
hole_wok_files = sorted(tmp_hole.rglob("*.wok"))
if not hole_result.blocking_issues and hole_wok_files:
    hole_fingerprint, hole_report = inspect_raw_wok_structure(resref, hole_wok_files[0].read_bytes())
    record(
        "T17 holed WOK serializes 2 closed perimeter loops",
        not hole_report.has_errors
        and hole_fingerprint.perimeter_count == 2
        and hole_fingerprint.closed_perimeter_count == 2,
        f"{hole_fingerprint.closed_perimeter_count}/{hole_fingerprint.perimeter_count} closed loop(s)",
    )
else:
    record(
        "T17 holed WOK serializes 2 closed perimeter loops",
        False,
        f"blocking={hole_result.blocking_issues[:1]} wok_files={len(hole_wok_files)}",
    )

# ---- T18: hole round-trips KMAP payload and fill_hole restores the floor ----
holes_persisted = tuple(terrain_primitive(c).holes)
c.apply_authored_terrain_operation(operation="fill_hole", room_resref=resref, row_index=4, column_index=12, radius=1)
prim = terrain_primitive(c)
record(
    "T18 KMAP persists holes and fill_hole restores floor",
    len(holes_persisted) == 9 and prim.holes == () and len(build_terrain_wok(prim).faces) == faces_before_hole,
    f"persisted {len(holes_persisted)} cell(s); after fill {len(prim.holes)} remain",
)

print()
print(f"{'TERRAIN PIPELINE STEP':52} {'RESULT':6} DETAIL")
print("-" * 118)
fails = sum(1 for _n, status, _d in RESULTS if status == "FAIL")
for name, status, detail in RESULTS:
    print(f"{name:52} {status:6} {detail}")
print("-" * 118)
print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")
raise SystemExit(1 if fails else 0)
