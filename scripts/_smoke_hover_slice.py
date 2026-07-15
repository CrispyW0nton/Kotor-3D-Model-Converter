"""Headless smoke: import Map Studio window + panel and exercise hover slice APIs."""
from __future__ import annotations

import os
import sys
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

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from src.gui.windows.module_editor_window import ModuleEditorWindow

window = ModuleEditorWindow()
panel = window.viewport_panel

# Hover probe API round-trip.
panel.set_map_studio_hover_probe(True, "face")
assert panel._hover_probe_enabled is True
assert panel._hover_component_mode == "face"
assert panel.current_map_studio_hover_context() is None
candidates = panel._map_studio_hover_candidates()
print("candidates (empty scene):", len(candidates))
panel.set_map_studio_hover_probe(False)
assert panel._hover_probe_enabled is False

# Edit-mode change drives the probe.
window._handle_map_studio_edit_mode_changed("Face")
assert panel._hover_probe_enabled is True and panel._hover_component_mode == "face"
window._handle_map_studio_edit_mode_changed("Walkmesh")
assert panel._hover_component_mode == "walkmesh"
# Object mode keeps the probe on (face-only picking) so the GModeler panel
# opens over stock module geometry too.
window._handle_map_studio_edit_mode_changed("Object")
assert panel._hover_probe_enabled is True and panel._hover_component_mode == "object"
window._handle_map_studio_edit_mode_changed("Placement")
assert panel._hover_probe_enabled is False

# GModeler menu path: no hover context -> flat fallback path returns False.
assert window._open_map_studio_gmodeler_marking_menu(QtCore.QPoint(200, 200)) is False

# With a fake hover context the GModeler popup opens and closes cleanly.
from src.core.modules.map_studio_hover_context import MapStudioHoverContext

panel._hover_context = MapStudioHoverContext(component_type="face", room_resref="grtest01", face_index=2)
assert window._open_map_studio_gmodeler_marking_menu(QtCore.QPoint(300, 300)) is True
app.processEvents()
for w in QtWidgets.QApplication.topLevelWidgets():
    if w.objectName() == "mapStudioGModelerMarkingMenu":
        assert w.action_keys(), "GModeler panel lost its registry actions"
        kinds = {cell.kind for cell in w.cells()}
        assert {"action", "target", "do_nothing"} <= kinds, kinds
        assert w.current_action_key() in w.action_keys()
        w.close()
app.processEvents()

# Unwired actions still report read-only through the status bar.
window._handle_map_studio_gmodeler_action("face_bevel", "Face Corners")
message = window.statusBar().currentMessage()
assert "face_bevel" in message or "not wired to geometry" in message, message
print("status:", message[:110])

# Wired actions on a non-editable hover fall through to the tool belt, which
# reports the authored-module guidance without mutating anything.
window._handle_map_studio_gmodeler_action("face_delete", "Single Face")
message = window.statusBar().currentMessage()
assert message, "wired action must surface a status message"
print("status:", message[:110])

# Delete key routes through the hovered component first (falls back to the
# selection paths without crashing when the hover isn't editable geometry).
panel._hover_context = MapStudioHoverContext(component_type="face", room_resref="grtest01", face_index=1)
window.delete_map_studio_current_selection()
panel._hover_context = MapStudioHoverContext(component_type="vertex", room_resref="grtest01", face_index=1, vertex_index=0)
window.delete_map_studio_current_selection()
panel._hover_context = None
window.delete_map_studio_current_selection()

# Click-select a stock room row, Delete removes it, Ctrl+Z restores it.
from src.core.level.kmap_model import RoomInstance

window.controller.project.rooms.append(RoomInstance(name="m01aa_01a", model_resref="m01aa_01a"))
window._handle_map_studio_room_clicked("m01aa_01a", False)
window.delete_map_studio_current_selection()
assert all(
    str(getattr(row, "model_resref", "") or "").lower() != "m01aa_01a"
    for row in window.controller.project.rooms
), "selected stock room must delete"
assert window.controller.can_undo_map_studio_command(), "room delete must record undo"
window.undo_map_studio_command()
assert any(
    str(getattr(row, "model_resref", "") or "").lower() == "m01aa_01a"
    for row in window.controller.project.rooms
), "undo must restore the deleted room"
print("select/delete/undo loop OK")

window.controller.project.dirty = False
window.close()
app.processEvents()
print("HEADLESS SMOKE OK")
