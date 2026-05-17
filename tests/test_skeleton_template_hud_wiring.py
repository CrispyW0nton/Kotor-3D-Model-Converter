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
    assert 'QtWidgets.QGroupBox("KOTOR Base Skeleton")' in src
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
    assert "_load_skeleton_template_model" in src
    assert "load_game_skeleton_source" in src
    assert "apply_template_rig(mesh_model, template_model, game=game)" in src
    assert "scene.assign" in src


def test_template_selection_previews_external_skeleton_overlay() -> None:
    builder = _read("src/gui/qt_character_builder_panel.py")
    viewport = _read("src/gui/qt_viewport.py")

    assert "viewport.set_external_skeleton(template_model)" in builder
    assert "fit_reference_model=self._selected_skeleton_template_model" in builder
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


def test_manual_import_fit_controls_are_wired() -> None:
    inspector = _read("src/gui/qt_inspector_panel.py")
    builder = _read("src/gui/qt_character_builder_panel.py")
    viewport = _read("src/gui/qt_viewport.py")
    workflow = _read("src/core/headless_body_workflow.py")

    assert "fitAdjustmentChanged" in inspector
    assert 'QtWidgets.QGroupBox("Import Fit")' in inspector
    assert "set_fit_adjustment" in inspector
    assert "_on_fit_adjustment_changed" in builder
    assert "apply_external_model_fit_adjustment" in builder
    assert "refresh_model_geometry" in viewport
    assert "def apply_external_model_fit_adjustment" in workflow


def test_shift_snaps_viewport_rotation_gimbal_to_ten_degrees() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "QtCore.Qt.ShiftModifier" in viewport
    assert "round(math.degrees(angle) / 10.0) * 10.0" in viewport
    assert "self._gimbal_node_start_rot" in viewport


def test_viewport_preloads_textures_for_skin_nodes() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "def _preload_gpu_textures" in viewport
    assert "def _prewarm_textures" in viewport
    assert 'getattr(node, "is_skin", False)' in viewport
    assert "model.all_nodes()" in viewport


def test_external_dcc_imports_disable_kotor_uv_seam_repair() -> None:
    workflow = _read("src/core/headless_body_workflow.py")
    viewport = _read("src/gui/viewport_core.py")

    assert "def _mark_external_import" in workflow
    assert 'setattr(node, "_external_imported", True)' in workflow
    assert 'getattr(node, "_external_imported", False)' in viewport
    assert "_face_has_u_seam = False" in viewport
    assert "_face_has_v_seam = False" in viewport

