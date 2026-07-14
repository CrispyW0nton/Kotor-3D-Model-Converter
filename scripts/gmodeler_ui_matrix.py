"""GModeler UI matrix: drive every tool the way a MANUAL USER does, headlessly.

Pipeline per tool: hover context -> RMB opens the GModeler panel -> panel
shows the right tree -> activating the action routes through the window
handler (dialogs mocked) -> geometry actually changes -> undo works.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from PySide6 import QtCore, QtWidgets

# This machine segfaults on real GL draws in offscreen mode (known, pre-existing).
# The projection/camera math we need for hover picking runs before the draw calls,
# so no-op the actual VAO submission only.
import moderngl

moderngl.VertexArray.render = lambda self, *args, **kwargs: None

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

# Manual-flow tuning: dialogs are mocked the same way defaults will apply.
_dialog_calls: list[str] = []
_real_get_double = QtWidgets.QInputDialog.getDouble

def _mock_get_double(*args, **kwargs):
    _dialog_calls.append(str(args[1]) if len(args) > 1 else "?")
    return (args[3] if len(args) > 3 else 1.0), True

QtWidgets.QInputDialog.getDouble = staticmethod(_mock_get_double)

from scripts.gmodeler_tool_matrix import _cube_surfaces  # reuse cube fixture
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
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
from src.core.modules.map_studio_hover_context import MapStudioHoverContext
from src.gui.windows.module_editor_window import ModuleEditorWindow

RESULTS: list[tuple[str, str, str]] = []
ROOM = "grcube01_room"


def record(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", str(detail)[:100]))
    print(f"{name:44} {'PASS' if ok else 'FAIL':6} {str(detail)[:100]}", flush=True)


def make_window() -> ModuleEditorWindow:
    window = ModuleEditorWindow()
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grcube01", game="K1", display_name="cube", tag="grcube01"),
        rooms=(AuthoredRoomSpec(room_resref=ROOM, primitive=ImportedMeshRoomPrimitive(room_resref=ROOM, surfaces=_cube_surfaces(), game="K1")),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grcube01")),
    )
    window.controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    window._refresh_all("ui matrix")
    app.processEvents()
    # The manual user switches to Edit (GModeler) mode first.
    window._run_map_studio_mode_marking_action("edit")
    app.processEvents()
    return window


def face_count(window) -> int:
    authored = authored_project_from_kmap_payload(
        window.controller.project.extra_sections["authored_module"], fallback_name="grcube01", fallback_game="K1"
    )
    return sum(len(s.faces) for s in authored.rooms[0].primitive.surfaces)


def preview_mesh_node(window, room=ROOM, role="render"):
    for _room_node, node in window.viewport_panel._iter_room_preview_mesh_nodes(room):
        if str(getattr(node, "_gr_map_studio_mesh_role", "") or "") == role:
            return node
    return None


def hover(window, component="face", face=0, vertex=-1, edge=(-1, -1)):
    ctx = MapStudioHoverContext(
        component_type=component,
        room_resref=ROOM,
        mesh_role="render",
        face_index=face,
        vertex_index=vertex,
        edge_indices=tuple(edge),
        face_normal=(0.0, 0.0, 1.0),
    )
    window.viewport_panel._hover_context = ctx
    return ctx


def find_panel():
    return next(
        (
            w
            for w in QtWidgets.QApplication.topLevelWidgets()
            if w.objectName() == "mapStudioGModelerMarkingMenu" and w.isVisible()
        ),
        None,
    )


def close_panels():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == "mapStudioGModelerMarkingMenu":
            w.close()
            w.deleteLater()
    app.processEvents()


# ---- H0: does the offscreen renderer even produce hover candidates? ----
window = make_window()
panel = window.viewport_panel
candidates = panel._map_studio_hover_candidates()
record("H00 preview hover candidates (offscreen)", len(candidates) > 0, f"{len(candidates)} candidates")
if candidates:
    from src.core.modules.map_studio_hover_context import pick_map_studio_hover_context
    sx, sy = candidates[0].screen_points[0]
    picked = pick_map_studio_hover_context(candidates, sx, sy)
    record("H01 pick from real projection", picked.is_hit, f"{picked.component_type} face {picked.face_index}")

# ---- H1: RMB opens the GModeler panel per component ----
for comp, face, vert, edge in (("face", 0, -1, (-1, -1)), ("edge", 0, -1, (0, 1)), ("vertex", 0, 0, (-1, -1))):
    hover(window, comp, face, vert, edge)
    opened = window._open_map_studio_gmodeler_marking_menu(QtCore.QPoint(200, 200))
    app.processEvents()
    panel_widget = find_panel()
    ok = opened and panel_widget is not None and comp.upper() in panel_widget._header_text()
    record(f"H1{comp[0]} RMB opens {comp} panel", ok, panel_widget._header_text() if panel_widget else "no panel")
    close_panels()
window.controller.project.dirty = False
window.close(); app.processEvents()

# ---- H2: every action end-to-end through the window handler ----
FACE_ACTIONS = [
    ("face_extrude", "Single Face", True),
    ("face_inset", "Each Face", True),
    ("face_move", "Single Face", False),
    ("face_flat", "Single Face", False),
    ("face_flip", "Single Face", False),
    ("face_split", "Single Face", True),
    ("face_delete", "Single Face", True),
]
for key, target, changes_count in FACE_ACTIONS:
    window = make_window()
    hover(window, "face", 2)
    before = face_count(window)
    window._handle_map_studio_gmodeler_action(key, target)
    app.processEvents()
    after = face_count(window)
    ok = (after != before) if changes_count else True
    # verify the action actually landed by checking undo exists
    ok = ok and window.controller.can_undo_map_studio_command()
    record(f"H2 {key}", ok, f"faces {before}->{after}")
    window.controller.project.dirty = False
    window.close(); app.processEvents()

EDGE_ACTIONS = [
    ("edge_move", "Single Edge", (0, 2)),
    ("edge_bevel", "Single Edge", (0, 1)),
    ("edge_split", "Single Edge", (0, 2)),
    ("edge_collapse", "Single Edge", (0, 2)),
    ("edge_delete", "Single Edge", (0, 2)),
]
for key, target, edge in EDGE_ACTIONS:
    window = make_window()
    hover(window, "edge", 0, -1, edge)
    window._handle_map_studio_gmodeler_action(key, target)
    app.processEvents()
    if key == "edge_bevel" and window.viewport_panel._component_bevel_armed is not None:
        window.viewport_panel.bevel_segments_spin.setValue(3)
        window.viewport_panel.bevel_profile_spin.setValue(0.65)
        window.viewport_panel._apply_component_bevel_from_options()
        app.processEvents()
    record(f"H2 {key}", window.controller.can_undo_map_studio_command(), "")
    window.controller.project.dirty = False
    window.close(); app.processEvents()

VERTEX_ACTIONS = [("vertex_move", "Single Vertex"), ("vertex_weld", "To Nearest"), ("vertex_delete", "Single Vertex")]
for key, target in VERTEX_ACTIONS:
    window = make_window()
    hover(window, "vertex", 0, 0)
    window._handle_map_studio_gmodeler_action(key, target)
    app.processEvents()
    record(f"H2 {key}", window.controller.can_undo_map_studio_command(), "")
    window.controller.project.dirty = False
    window.close(); app.processEvents()

# ---- H3: Maya selection workflow (Shift multi-select faces -> Delete) ----
window = make_window()
panel = window.viewport_panel
before = face_count(window)
panel._hover_probe_enabled = True
panel._hover_component_mode = ""
for face in (0, 3, 5):
    ctx = hover(window, "face", face)
    panel._toggle_map_studio_component_selection(ctx, additive=True)
record("H3a shift-select 3 faces", len(panel.map_studio_component_selection()) == 3, f"{len(panel.map_studio_component_selection())} selected")
window.delete_map_studio_current_selection()
app.processEvents()
after = face_count(window)
record("H3b Delete removes all selected", after == before - 3, f"faces {before}->{after}")
record("H3c selection cleared after delete", len(panel.map_studio_component_selection()) == 0, "")

# ---- H4: object mode whole-room delete ----
window2_state = None
window._run_map_studio_mode_marking_action("object")
app.processEvents()
hover(window, "face", 0)
window._handle_map_studio_room_clicked(ROOM, False)
window.delete_map_studio_current_selection()
app.processEvents()
authored = authored_project_from_kmap_payload(window.controller.project.extra_sections["authored_module"], fallback_name="x", fallback_game="K1")
record("H4 object mode deletes whole room", len(authored.rooms) == 0, f"{len(authored.rooms)} rooms left")
window.controller.project.dirty = False
window.close(); app.processEvents()

# ---- H6: Maya-style interactive extrude (Ctrl+E arm -> drag -> commit) ----
class FakeMouse:
    def __init__(self, x, y):
        self._point = QtCore.QPointF(float(x), float(y))

    def position(self):
        return self._point


window = make_window()
panel = window.viewport_panel
candidates = panel._map_studio_hover_candidates()
panel._hover_candidate_cache = candidates
cand = candidates[0]
ctx = MapStudioHoverContext(
    component_type="face",
    room_resref=cand.room_resref,
    mesh_role=cand.mesh_role,
    face_index=cand.face_index,
    vertex_index=-1,
    edge_indices=(-1, -1),
    world_point=cand.world_points[0],
    face_normal=cand.normal,
)
panel._hover_context = ctx
before = face_count(window)
payload_before_live_pull = json.dumps(
    window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":")
)
armed = panel.arm_component_extrude()
record(
    "H6a Ctrl+E arms from hovered face",
    armed and (panel._component_extrude_armed or {}).get("kind") == "face",
    str((panel._component_extrude_armed or {}).get("face_indices")),
)
record("H6b LMB begins gizmo drag", panel._begin_component_extrude_drag(FakeMouse(400, 300)), "")
drag = panel._component_extrude_drag or {}
ax, ay = drag.get("axis_screen", (0.0, -1.0))
end_event = FakeMouse(400 + ax * 2.0, 300 + ay * 2.0)
panel._update_component_extrude_drag(end_event)
pending = float((panel._component_extrude_drag or {}).get("pending_distance", 0.0))
record("H6c drag maps pixels to meters", abs(pending - 2.0) < 0.05, f"pending {pending:+.3f}m (expect +2)")
live_node = preview_mesh_node(window, cand.room_resref, cand.mesh_role)
payload_during_live_pull = json.dumps(
    window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":")
)
record(
    "H6c2 extrude mesh previews before release",
    live_node is not None and len(tuple(getattr(live_node, "faces", ()) or ())) == before + 6,
    f"preview faces={len(tuple(getattr(live_node, 'faces', ()) or ())) if live_node else 0}",
)
record(
    "H6c3 extrude preview leaves KMAP untouched",
    payload_during_live_pull == payload_before_live_pull,
    "serialized only on release",
)
panel._finish_component_extrude_drag(end_event)
app.processEvents()
after = face_count(window)
record("H6d release commits extrude (1 face -> +6)", after == before + 6, f"faces {before}->{after}")
sel = panel.map_studio_component_selection()
record(
    "H6e new cap auto-selected with world points",
    len(sel) == 1 and sel[0]["component_type"] == "face" and len(tuple(sel[0]["face_world_points"])) >= 3,
    f"{len(sel)} selected, face {sel[0]['face_index'] if sel else '-'}",
)
record("H6f single undo entry for the pull", window.controller.can_undo_map_studio_command(), "")

before = face_count(window)
window._commit_map_studio_component_extrude(
    {
        "kind": "edge",
        "room_resref": ROOM,
        "mesh_role": "render",
        "face_index": 0,
        "edge_corners": (0, 1),
        "axis": (1.0, 0.0, 0.0),
        "distance": 1.5,
    }
)
app.processEvents()
after = face_count(window)
record("H6g edge extrude appends outward quad (+2)", after == before + 2, f"faces {before}->{after}")

panel._hover_context = ctx
panel._hover_candidate_cache = panel._map_studio_hover_candidates()
if panel.arm_component_extrude():
    panel._disarm_component_extrude("test")
record("H6h Esc disarms without geometry change", panel._component_extrude_armed is None and face_count(window) == after, "")

# H6j/H6k: Maya axis-orientation badge (normal <-> world toggle)
panel._hover_context = ctx
panel._hover_candidate_cache = panel._map_studio_hover_candidates()
if panel.arm_component_extrude():
    armed = panel._component_extrude_armed
    armed["axis"] = (0.6, 0.0, 0.8)  # pretend a slanted face normal
    armed["axis_normal"] = (0.6, 0.0, 0.8)
    toggle_pos = panel.component_extrude_toggle_screen_pos()
    clicked = toggle_pos is not None and panel._begin_component_extrude_drag(
        FakeMouse(toggle_pos[0] + 3.0, toggle_pos[1] - 3.0)
    )
    world_ok = (
        clicked
        and panel._component_extrude_drag is None  # badge click must NOT start a drag
        and armed.get("axis_mode") == "world"
        and tuple(armed.get("axis")) == (0.0, 0.0, 1.0)
    )
    record("H6j badge click snaps axis to world", world_ok, f"axis {armed.get('axis')} mode {armed.get('axis_mode')}")
    panel.toggle_component_extrude_axis_mode()
    record(
        "H6k second toggle restores component normal",
        armed.get("axis_mode") == "normal" and tuple(armed.get("axis")) == (0.6, 0.0, 0.8),
        f"axis {armed.get('axis')}",
    )
    panel._disarm_component_extrude()
else:
    record("H6j badge click snaps axis to world", False, "arming failed")

# H6l: world-mode face extrude pulls along the world axis end-to-end
before = face_count(window)
window._commit_map_studio_component_extrude(
    {
        "kind": "face",
        "room_resref": ROOM,
        "mesh_role": "render",
        "face_indices": (2,),
        "axis": (0.0, 0.0, 1.0),
        "axis_mode": "world",
        "distance": 1.0,
    }
)
app.processEvents()
record("H6l world-mode extrude commits", face_count(window) == before + 6, f"faces {before}->{face_count(window)}")

# H6i: RMB menu Extrude arms the same interactive flow (no dialog)
panel._hover_candidate_cache = panel._map_studio_hover_candidates()
fresh = panel._hover_candidate_cache[0]
panel._hover_context = MapStudioHoverContext(
    component_type="face",
    room_resref=fresh.room_resref,
    mesh_role=fresh.mesh_role,
    face_index=fresh.face_index,
    world_point=fresh.world_points[0],
    face_normal=fresh.normal,
)
window._handle_map_studio_gmodeler_action("face_extrude", "Single Face")
record("H6i menu Extrude arms interactive pull", panel._component_extrude_armed is not None, "")
panel._disarm_component_extrude()

# H6m-H6p: edge bevel is a live, persistent operator rather than an
# immediate single-number command.
window.controller.project.dirty = False
window.close(); app.processEvents()
window = make_window()
panel = window.viewport_panel
bevel_source_node = preview_mesh_node(window)
bevel_face = tuple(bevel_source_node.faces[0])
bevel_room_node = bevel_source_node.parent
bevel_offset = tuple(getattr(bevel_room_node, "position", (0.0, 0.0, 0.0)))
bevel_world_points = tuple(
    (
        float(bevel_source_node.vertices[index][0]) + float(bevel_offset[0]),
        float(bevel_source_node.vertices[index][1]) + float(bevel_offset[1]),
        float(bevel_source_node.vertices[index][2]) + float(bevel_offset[2]),
    )
    for index in bevel_face
)
panel._map_studio_component_selection = [
    {
        "component_type": "edge",
        "room_resref": ROOM,
        "mesh_role": "render",
        "face_index": 0,
        "edge_indices": (0, 1),
        "face_world_points": bevel_world_points,
        "world_point": bevel_world_points[0],
    }
]
panel._push_map_studio_component_selection()
panel._hover_context = MapStudioHoverContext(
    component_type="edge",
    room_resref=ROOM,
    mesh_role="render",
    face_index=0,
    edge_indices=(0, 1),
    world_point=bevel_world_points[0],
    face_normal=(0.0, 0.0, 1.0),
)
payload_before_bevel = json.dumps(
    window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":")
)
window._handle_map_studio_gmodeler_action("edge_bevel", "Single Edge")
panel.bevel_segments_spin.setValue(4)
panel.bevel_profile_spin.setValue(0.75)
panel.bevel_miter_combo.setCurrentIndex(panel.bevel_miter_combo.findData("patch"))
panel.bevel_smoothing_spin.setValue(60.0)
panel.bevel_uv_combo.setCurrentIndex(panel.bevel_uv_combo.findData("tiled"))
app.processEvents()
bevel_preview_node = preview_mesh_node(window, ROOM, "render")
record(
    "H6m Bevel opens persistent full controls",
    panel._component_bevel_armed is not None
    and not panel.bevel_options_frame.isHidden()
    and panel.bevel_segments_spin.value() == 4
    and abs(panel.bevel_profile_spin.value() - 0.75) < 1.0e-6
    and panel.bevel_miter_combo.currentData() == "patch"
    and panel.bevel_uv_combo.currentData() == "tiled",
    "segments/profile/miter/smoothing/UV/clamp",
)
record(
    "H6n Bevel topology previews before Apply",
    bevel_preview_node is not None and len(tuple(getattr(bevel_preview_node, "faces", ()) or ())) > face_count(window),
    f"preview faces={len(tuple(getattr(bevel_preview_node, 'faces', ()) or ())) if bevel_preview_node else 0}",
)
record(
    "H6o Bevel preview leaves KMAP untouched",
    json.dumps(window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":"))
    == payload_before_bevel,
    "immutable operator baseline",
)
panel._apply_component_bevel_from_options()
app.processEvents()
beveled = authored_project_from_kmap_payload(
    window.controller.project.extra_sections["authored_module"], fallback_name="grcube01", fallback_game="K1"
).rooms[0].primitive
bevel_edit = dict(beveled.metadata).get("last_topology_edit") or {}
record(
    "H6p Bevel Apply commits full operator state",
    bevel_edit.get("segments") == 4
    and abs(float(bevel_edit.get("profile", 0.0)) - 0.75) < 1.0e-6
    and bevel_edit.get("miter") == "patch"
    and bevel_edit.get("uv_mode") == "tiled",
    str(bevel_edit),
)
window.controller.project.dirty = False
window.close(); app.processEvents()

# ---- H7: Terrain workspace Plane -> sculpt -> generated WOK ----
from types import SimpleNamespace
from src.core.modules.authored_terrain_builder import TerrainHeightfieldPrimitive, build_terrain_wok

window = ModuleEditorWindow()
window.controller.new_project(name="grterrainui", game="K1")
window._refresh_all("terrain plane acceptance")
window._set_map_studio_workspace_combo_key("terrain")
window._handle_map_studio_tool_belt_action(SimpleNamespace(key="plane", workspace_key="terrain", tool_key=""))
app.processEvents()
authored = authored_project_from_kmap_payload(
    window.controller.project.extra_sections["authored_module"], fallback_name="grterrainui", fallback_game="K1"
)
terrain_room = next((room for room in authored.rooms if isinstance(room.primitive, TerrainHeightfieldPrimitive)), None)
record("H7a Terrain Plane creates sculptable grid", terrain_room is not None, terrain_room.room_resref if terrain_room else "none")
if terrain_room is not None:
    room_resref = terrain_room.room_resref
    window.builder_tab.terrainDeltaSpinBox.setValue(0.4)
    window.builder_tab.terrainRadiusSpinBox.setValue(2)
    window.builder_tab.terrainSmoothStrengthSpinBox.setValue(0.8)
    terrain_node = preview_mesh_node(window, room_resref, "render")
    terrain_payload_before = json.dumps(
        window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":")
    )
    z_before = tuple(float(vertex[2]) for vertex in tuple(getattr(terrain_node, "vertices", ()) or ()))
    window.apply_map_studio_viewport_terrain_brush_frame("raise", room_resref, ((8, 8, 1.0),))
    app.processEvents()
    z_live = tuple(float(vertex[2]) for vertex in tuple(getattr(terrain_node, "vertices", ()) or ()))
    record(
        "H7b terrain mesh sculpts during drag",
        max(z_live) > max(z_before)
        and json.dumps(window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":"))
        == terrain_payload_before,
        f"live peak={max(z_live):.2f}m; KMAP unchanged",
    )
    window.commit_map_studio_viewport_terrain_brush_stroke("raise", room_resref)
    app.processEvents()
    authored = authored_project_from_kmap_payload(
        window.controller.project.extra_sections["authored_module"], fallback_name="grterrainui", fallback_game="K1"
    )
    sculpted = next(room.primitive for room in authored.rooms if room.room_resref == room_resref)
    wok = build_terrain_wok(sculpted)
    raised = max(float(value) for row in sculpted.heights for value in row)
    record(
        "H7c release serializes and generates wrapping WOK",
        raised > 0.0 and len(wok.verts) == len(sculpted.heights) * len(sculpted.heights[0]),
        f"peak={raised:.2f}m wok={len(wok.verts)} verts/{len(wok.faces)} faces",
    )
window.controller.project.dirty = False
window.close(); app.processEvents()

# ---- H8: object selection individually/together -> combine -> separate ----
window = ModuleEditorWindow()
window.controller.new_project(name="grobjectui", game="K1")
window.controller.add_authored_room_primitive(primitive_kind="cube", primitive_name="box1")
window._refresh_all("object selection acceptance")
rows = list(window.controller.authored_room_primitive_transforms())
room_resref = str(getattr(rows[0], "room_resref", "") or "")
entries = [
    (room_resref, str(getattr(row, "primitive_name", "") or ""))
    for row in rows
    if str(getattr(row, "room_resref", "") or "") == room_resref
    and str(getattr(row, "primitive_type", "") or "") != "plane"
][-2:]
window._select_authored_room_primitives(entries)
app.processEvents()
record(
    "H8a select objects individually or together",
    len(window.controller.model.selected_ids) == 2
    and len(window.viewport_panel.selected_room_primitives()) == 2
    and len(window.outliner.selectedItems()) == 2,
    f"model={len(window.controller.model.selected_ids)} viewport={len(window.viewport_panel.selected_room_primitives())} outliner={len(window.outliner.selectedItems())}",
)
panel = window.viewport_panel
panel.set_transform_gizmo_mode("translate", announce=False)
selected_nodes_before = {
    str(getattr(node, "_gr_map_studio_primitive_name", "") or ""): tuple(getattr(node, "vertices", ()) or ())
    for _room_node, node in panel._iter_room_preview_mesh_nodes(room_resref)
    if str(getattr(node, "_gr_map_studio_primitive_name", "") or "") in {name for _room, name in entries}
}
kmap_before_group_drag = json.dumps(
    window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":")
)
started = panel._begin_room_primitive_drag((entries[0][0], entries[0][1], (0.0, 0.0, 0.0)), FakeMouse(300, 250))
drag = panel._room_primitive_drag or {}
drag["active"] = True
drag["pending_delta"] = (1.25, -0.5, 0.0)
panel._apply_room_primitive_drag_preview(drag)
selected_nodes_live = {
    str(getattr(node, "_gr_map_studio_primitive_name", "") or ""): tuple(getattr(node, "vertices", ()) or ())
    for _room_node, node in panel._iter_room_preview_mesh_nodes(room_resref)
    if str(getattr(node, "_gr_map_studio_primitive_name", "") or "") in {name for _room, name in entries}
}
record(
    "H8b multi-object geometry moves during drag",
    started
    and len(panel.selected_room_primitives()) == 2
    and len(selected_nodes_live) == 2
    and all(selected_nodes_live[name] != selected_nodes_before[name] for name in selected_nodes_before),
    f"selection={len(panel.selected_room_primitives())} changed={sum(selected_nodes_live.get(name) != value for name, value in selected_nodes_before.items())}",
)
record(
    "H8c transform preview leaves KMAP untouched",
    json.dumps(window.controller.project.extra_sections["authored_module"], sort_keys=True, separators=(",", ":"))
    == kmap_before_group_drag,
    "one transaction on release",
)
panel._finish_room_primitive_drag()
app.processEvents()
rows_after_drag = {
    row.primitive_name: tuple(row.pivot)
    for row in window.controller.authored_room_primitive_transforms()
    if row.primitive_name in {name for _room, name in entries}
}
record(
    "H8d release commits one batch transform",
    len(rows_after_drag) == 2
    and window.controller.command_history.undo_label == "Move 2 primitives"
    and len(panel.selected_room_primitives()) == 2,
    f"undo={window.controller.command_history.undo_label!r} selection={len(panel.selected_room_primitives())}",
)
broad_refresh_calls = []
original_refresh_all = window._refresh_all
def _tracked_refresh_all(*args, **kwargs):
    broad_refresh_calls.append((args, kwargs))
    return original_refresh_all(*args, **kwargs)
window._refresh_all = _tracked_refresh_all
combined = window._combine_selected_authored_room_primitives()
authored = authored_project_from_kmap_payload(
    window.controller.project.extra_sections["authored_module"], fallback_name="grobjectui", fallback_game="K1"
)
combined_room = next(room for room in authored.rooms if room.room_resref == room_resref)
combined_primitives = [
    primitive
    for primitive in combined_room.primitive.primitives
    if type(primitive).__name__ == "CombinedRoomPrimitive"
]
combined_name = combined_primitives[0].name if combined_primitives else ""
record(
    "H8e Combine creates one real polygon mesh",
    combined and len(combined_primitives) == 1 and len(combined_primitives[0].sources) == 2,
    f"combined={combined_name} sources={len(combined_primitives[0].sources) if combined_primitives else 0}",
)
window._select_authored_room_primitives(((room_resref, combined_name),))
before_rooms = len(authored.rooms)
separated = window._separate_selected_authored_room_primitive()
authored = authored_project_from_kmap_payload(
    window.controller.project.extra_sections["authored_module"], fallback_name="grobjectui", fallback_game="K1"
)
separated_room = next(room for room in authored.rooms if room.room_resref == room_resref)
shell_names = set(separated_room.metadata.get("last_separated_shell_names") or ())
shell_rows = [
    row
    for row in window.controller.authored_room_primitive_transforms()
    if str(getattr(row, "room_resref", "") or "") == room_resref
    and str(getattr(row, "primitive_name", "") or "") in shell_names
]
record(
    "H8f Separate makes selectable polygon shells",
    separated and len(shell_rows) >= 2 and len(authored.rooms) == before_rooms,
    f"shells={len(shell_rows)} rooms={before_rooms}->{len(authored.rooms)}",
)
scoped_refresh_ms = float(getattr(window, "_last_map_studio_geometry_refresh_ms", 9999.0) or 9999.0)
record(
    "H8g modeling edits avoid broad panel refresh",
    not broad_refresh_calls and scoped_refresh_ms < 25.0,
    f"broad={len(broad_refresh_calls)} scoped={scoped_refresh_ms:.2f}ms",
)
window.controller.project.dirty = False
window.close(); app.processEvents()

# ---- H5: no modal dialogs in normal flow (ZModeler-style immediate apply) ----
record(
    "H5 zero modal dialogs without Ctrl",
    len(_dialog_calls) == 0,
    f"{len(_dialog_calls)} dialog prompts: {sorted(set(_dialog_calls))[:4]}",
)

print()
print(f"{'UI WORKFLOW STEP':44} {'RESULT':6} DETAIL")
print("-" * 105)
fails = 0
for name, status, detail in RESULTS:
    if status == "FAIL":
        fails += 1
    print(f"{name:44} {status:6} {detail}")
print("-" * 105)
print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")
