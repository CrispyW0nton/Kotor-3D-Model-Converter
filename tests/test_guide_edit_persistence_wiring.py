"""M12/T1203 source-level guardrails for guide-edit persistence wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_workflow_exposes_guide_edit_adapter() -> None:
    src = _read("src/core/characters/headless_body_workflow.py")

    assert "class BodyGuideEditResult" in src
    assert "class BodyGuideEditHistory" in src
    assert "def update_body_guide(" in src
    assert "def update_body_guide_from_node(" in src
    assert "def undo_body_guide_edit(" in src
    assert "def redo_body_guide_edit(" in src
    assert "def record_body_guide_edit(" in src
    assert "acurig.move_guide(name, pos, auto_mirror=auto_mirror)" in src
    assert '"update_body_guide"' in src
    assert '"update_body_guide_from_node"' in src
    assert '"undo_body_guide_edit"' in src
    assert '"redo_body_guide_edit"' in src


def test_builder_connects_viewport_moves_to_acurig_guides() -> None:
    src = _read("src/gui/panels/qt_character_builder_panel.py")

    assert "self._body_guides" in src
    assert "self._body_guide_history" in src
    assert "self.viewport.nodeMoved.connect(self._on_viewport_node_moved)" in src
    assert "def _on_viewport_node_moved" in src
    assert "update_body_guide_from_node" in src
    assert "record_body_guide_edit" in src
    assert "self._push_body_guides_to_viewport()" in src
    assert "result.message" in src


def test_builder_exposes_toolbar_undo_redo_for_guides() -> None:
    src = _read("src/gui/panels/qt_character_builder_panel.py")

    assert "self._undo_guide_action" in src
    assert "self._redo_guide_action" in src
    assert "def _on_undo_body_guide_requested" in src
    assert "def _on_redo_body_guide_requested" in src
    assert "undo_body_guide_edit" in src
    assert "redo_body_guide_edit" in src


def test_viewport_exposes_acurig_guide_overlay_methods() -> None:
    src = _read("src/gui/viewports/qt_viewport.py")

    assert "def set_acurig_guides" in src
    assert "self._renderer.set_acurig_guides(guides or {})" in src
    assert "def clear_acurig_guides" in src

