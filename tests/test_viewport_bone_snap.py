from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWPORT_PAYLOAD = ROOT / "native" / "GhostRigger.Core.GUI.Viewports" / "Python"


def _read_viewport(relpath: str) -> str:
    return (VIEWPORT_PAYLOAD / relpath).read_text(encoding="utf-8")


def test_hold_v_joint_drag_snap_is_wired_to_visible_bone_dots() -> None:
    selection = _read_viewport("src/gui/viewports/viewport_core/widgets/selection_mesh.py")
    drag = _read_viewport("src/gui/viewports/viewport_core/widgets/drag_interactions.py")

    assert "def _nearest_visible_bone_dot_at" in selection
    assert "exclude_nodes=tuple(drag_nodes + mirror_nodes)" in selection
    assert "def _move_node_by_overlay_world_delta" in selection
    assert "def _snap_joint_drag_to_visible_bone_at_cursor" in selection
    assert "mirrored_delta = (-delta_world[0], delta_world[1], delta_world[2])" in selection
    assert "self._snap_key_down" in drag
    assert "self._snap_joint_drag_to_visible_bone_at_cursor(x, y)" in drag


def test_hold_v_joint_drag_snap_keeps_legacy_external_gimbal_snap() -> None:
    selection = _read_viewport("src/gui/viewports/viewport_core/widgets/selection_mesh.py")
    drag = _read_viewport("src/gui/viewports/viewport_core/widgets/drag_interactions.py")

    assert "def _nearest_imported_bone_at" in selection
    assert "def _snap_selected_external_bones_to_imported_at_cursor" in selection
    assert "_snap_selected_external_bones_to_imported_at_cursor(x, y)" in drag
