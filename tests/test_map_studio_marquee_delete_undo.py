"""Focused proof: marquee multi-delete is one undo, and undo reverts views.

LordVaderCW's manual test found two defects: Ctrl+Z did not visually put a
moved desk back (the preview-key cache skipped reloading a rebuilt model that
hashed back to the pre-move key while the in-place-promoted node stayed
moved), and plain click-drag-release could not box-select objects for a
Del-key delete (the marquee required Ctrl and batch deletes burned one undo
step per object).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


PANEL_PATHS = (
    "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
    "native/GhostRigger.Core.Tools/Python/src/gui/panels/module_editor/module_editor_viewport_panel.py",
)
WINDOW_PATH = "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"


def test_in_place_promotion_invalidates_preview_key_for_undo() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    placement_id = "authored:placeable:i_desk"
    node = SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), children=[])
    setattr(node, "_gr_map_studio_placement_id", placement_id)
    panel._room_preview_model = SimpleNamespace(root_node=SimpleNamespace(children=[node]))
    panel._placement_markers = {placement_id: SimpleNamespace(bearing=0.0, position=(0.0, 0.0, 0.0), shape="box")}
    panel._room_preview_model_key = "clean-key-from-load"

    assert panel.update_authored_placement_preview_transform(placement_id, position=(5.0, 2.0, 0.0), bearing=0.4)
    # The loaded model was mutated in place, so its cache key must no longer
    # match ANY rebuilt key — including an undo that hashes back to the
    # pre-move key.  Otherwise _sync_room_preview_model skips the reload and
    # the desk visually stays where it was dragged.
    assert panel._room_preview_model_key == "__promoted_in_place__"
    assert panel._room_preview_model_key != "clean-key-from-load"

    # An unknown placement performs no mutation and must not dirty the key.
    panel._room_preview_model_key = "clean-key-from-load"
    assert not panel.update_authored_placement_preview_transform("authored:placeable:i_missing", bearing=1.0)
    assert panel._room_preview_model_key == "clean-key-from-load"


def test_marquee_batch_delete_is_one_undoable_command() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grmarq", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grmarq")
    for index in range(3):
        controller.add_authored_gameplay_placement(
            kind="placeable",
            template_resref=f"plc_bench{index}",
            tag=f"desk_{index}",
            position=(float(index), 1.0, 0.0),
        )
    ids = [
        row.placement_id
        for row in controller.authored_gameplay_placements()
        if str(getattr(row, "tag", "")).startswith("desk_")
    ]
    assert len(ids) == 3
    controller.command_history.clear()

    removed = controller.remove_authored_gameplay_placements(ids)
    assert set(removed) == set(ids)
    remaining = [
        row for row in controller.authored_gameplay_placements()
        if str(getattr(row, "tag", "")).startswith("desk_")
    ]
    assert remaining == []
    assert controller.command_history.undo_label == "Remove 3 placements"

    # ONE undo restores all three desks; nothing is left to undo after it.
    assert controller.undo_map_studio_command() is not None
    restored = [
        row for row in controller.authored_gameplay_placements()
        if str(getattr(row, "tag", "")).startswith("desk_")
    ]
    assert len(restored) == 3
    assert not controller.can_undo_map_studio_command()

    # Empty/invalid input is a no-op that records nothing.
    assert controller.remove_authored_gameplay_placements(()) == ()


def test_undo_of_placement_move_is_targeted_not_full_map_reload() -> None:
    """Undoing one placement move must not rebuild/reload the whole map."""

    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.level import LevelTransform
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grundotgt", game="K1")
        window.controller.create_authored_room_preset_module(
            preset_id="rectangular_dev_room", module_root="grundotgt"
        )
        window.controller.add_authored_gameplay_placement(
            kind="placeable",
            template_resref="plc_bench",
            tag="undo_target",
            position=(1.0, 1.0, 0.0),
        )
        window._refresh_all()
        placement_id = next(
            row.placement_id
            for row in window.controller.authored_gameplay_placements()
            if row.tag == "undo_target"
        )
        window.placement_tab.snap_wok_box.setChecked(False)
        window._set_transform(
            placement_id,
            LevelTransform(position=(6.0, 4.0, 0.0), rotation=(0.0, 0.0, 0.5), scale=(1.0, 1.0, 1.0)),
        )

        def _fail_broad_refresh(_message: str = "") -> None:
            raise AssertionError("undo of a placement move must not use the broad _refresh_all path")

        def _fail_preview_rebuild(*_args, **_kwargs):
            raise AssertionError("undo of a placement move must not rebuild the combined preview model")

        window._refresh_all = _fail_broad_refresh
        window.controller.map_studio_viewport_preview_model = _fail_preview_rebuild

        window.undo_map_studio_command()

        reverted = next(
            row
            for row in window.controller.authored_gameplay_placements()
            if row.placement_id == placement_id
        )
        assert tuple(round(float(v), 3) for v in reverted.position[:2]) == (1.0, 1.0)
        table_row = window.viewport_panel._row_ids.index(placement_id)
        assert window.viewport_panel.scene_table.item(table_row, 2).text() == "1.000"
        assert window.viewport_panel.scene_table.item(table_row, 3).text() == "1.000"

        # Membership commands still use the broad fallback: deleting the
        # placement and undoing THAT must call _refresh_all.
        broad_calls: list[str] = []
        window._refresh_all = lambda message="": broad_calls.append(message)
        window.controller.remove_authored_gameplay_placements([placement_id])
        window.undo_map_studio_command()
        assert broad_calls, "undo of a remove must fall back to the broad refresh"
    finally:
        window.deleteLater()


def test_plain_drag_marquee_and_delete_priority_source_contracts() -> None:
    _configure_native_python_roots()
    for path in PANEL_PATHS:
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "Plain LMB drag over the canvas becomes a rubber-band" in source
        assert "_mark_room_preview_model_promoted" in source
        assert '"__promoted_in_place__"' in source
    window = (ROOT / WINDOW_PATH).read_text(encoding="utf-8")
    assert "remove_authored_gameplay_placements(matched)" in window
    # Marquee/multi selection must be deleted before the hovered object.
    marquee_index = window.index("if self._delete_selected_map_studio_rooms():")
    hovered_index = window.index("hovered_id and self._delete_map_studio_placement_ids([hovered_id])")
    assert marquee_index < hovered_index
