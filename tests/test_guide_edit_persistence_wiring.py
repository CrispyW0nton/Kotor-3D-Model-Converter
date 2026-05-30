"""M12/T1203 source-level guardrails for guide-edit persistence wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_VIEWPORT_SOURCE_FILES = (
    "src/gui/viewports/viewport_core/shared/dependencies.py",
    "src/gui/viewports/viewport_core/shared/icons.py",
    "src/gui/viewports/viewport_core/shared/joint_palette.py",
    "src/gui/viewports/viewport_core/shared/selection_modes.py",
    "src/gui/viewports/viewport_core/shared/weight_heatmap.py",
    "src/gui/viewports/viewport_core/widgets/mini_thumbnail.py",
    "src/gui/viewports/viewport_core/widgets/snap_view_bar.py",
    "src/gui/viewports/viewport_core/widgets/viewport_widget.py",
    "src/gui/viewports/viewport_core/widgets/state_helpers.py",
    "src/gui/viewports/viewport_core/widgets/construction.py",
    "src/gui/viewports/viewport_core/widgets/scene_models.py",
    "src/gui/viewports/viewport_core/widgets/display_controls.py",
    "src/gui/viewports/viewport_core/widgets/camera_workflow.py",
    "src/gui/viewports/viewport_core/widgets/measurement_controls.py",
    "src/gui/viewports/viewport_core/widgets/transform_camera.py",
    "src/gui/viewports/viewport_core/widgets/selection_mesh.py",
    "src/gui/viewports/viewport_core/widgets/history_animation.py",
    "src/gui/viewports/viewport_core/widgets/event_navigation.py",
    "src/gui/viewports/viewport_core/widgets/rendering_pipeline.py",
    "src/gui/viewports/viewport_core/widgets/overlay_layers.py",
    "src/gui/viewports/viewport_core/widgets/picking_hover.py",
    "src/gui/viewports/viewport_core/widgets/drag_interactions.py",
    "src/gui/viewports/viewport_core/widgets/resource_cache.py",
    "src/gui/viewports/viewport_core/widgets/variants.py",
)


def _read(relpath: str) -> str:
    if relpath == "src/gui/viewports/qt_viewport.py":
        return "\n".join((ROOT / path).read_text(encoding="utf-8") for path in _VIEWPORT_SOURCE_FILES)
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

