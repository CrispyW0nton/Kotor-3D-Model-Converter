"""M12/T1202 source-level guardrails for the skeleton-template HUD flow.

These tests intentionally avoid importing PySide6 so they can run in the
lightweight CI slice. Widget behavior is covered by the source contract here:
the inspector exposes the picker surface, the builder wires it to the
template rig transfer, and the viewport exposes the renderer overlay.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_inspector_exposes_skeleton_template_picker_controls() -> None:
    src = _read("src/gui/qt_inspector_panel.py")

    assert "skeletonTemplateSelected" in src
    assert "applySkeletonTemplateRequested" in src
    assert 'QtWidgets.QGroupBox("KOTOR Skeleton")' in src
    assert "set_skeleton_template_options" in src
    assert "selected_skeleton_template_key" in src
    assert "set_skeleton_template_status" in src


def test_builder_wires_template_selection_to_preview_and_apply() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "skeletonTemplateSelected.connect" in src
    assert "_on_skeleton_template_selected" in src
    assert "applySkeletonTemplateRequested.connect" in src
    assert "_on_apply_skeleton_template_requested" in src
    assert "skeleton_template_picker" in src
    assert "list_skeleton_templates(game=game, part=\"body\")" in src
    assert "load_template(game=game, part=part)" in src
    assert "apply_template_rig(mesh_model, template_model, game=game)" in src
    assert "scene.assign" in src


def test_template_selection_previews_external_skeleton_overlay() -> None:
    builder = _read("src/gui/qt_character_builder_panel.py")
    viewport = _read("src/gui/qt_viewport.py")

    assert "viewport.set_external_skeleton(template_model)" in builder
    assert "clear_external_skeleton" in builder
    assert "def set_external_skeleton" in viewport
    assert "self._renderer._ext_skeleton = model" in viewport
    assert "_fit_external_skeleton_overlay" in viewport
    assert "self._renderer._ext_skel_scale = scale" in viewport
    assert "def clear_external_skeleton" in viewport


def test_complete_character_load_and_texture_folder_prompt_are_wired() -> None:
    builder = _read("src/gui/qt_character_builder_panel.py")

    assert '"Complete character?"' in builder
    assert "supermodel_complete_character_load" in builder
    assert "CharacterMode.HEADLESS_BODY" in builder
    assert '"Locate texture folder"' in builder
    assert "_load_model_in_viewport_with_textures" in builder
    assert "texture_resolution_report(model, dirs)" in builder


def test_viewport_preloads_textures_for_skin_nodes() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "def _preload_gpu_textures" in viewport
    assert "def _prewarm_textures" in viewport
    assert 'getattr(node, "is_skin", False)' in viewport
    assert "model.all_nodes()" in viewport

