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
    assert "browseSkeletonTemplateRequested" in src
    assert "applySkeletonTemplateRequested" in src
    assert 'QtWidgets.QGroupBox("KOTOR Base Skeleton")' in src
    assert 'QtWidgets.QPushButton("Build KOTOR Skeleton")' in src
    assert "setEditable(True)" in src
    assert "MatchContains" in src
    assert "Browse MDL..." in src
    assert "set_skeleton_template_options" in src
    assert "selected_skeleton_template_key" in src
    assert "set_selected_skeleton_template_key" in src
    assert "set_skeleton_template_status" in src


def test_inspector_search_text_can_override_current_combo_selection() -> None:
    src = _read("src/gui/qt_inspector_panel.py")

    assert "typed = combo.currentText().strip().lower()" in src
    assert "current_label = (" in src
    assert "typed in label or typed in data" in src
    assert 'return f"typed:{typed}"' in src
    assert "current = str(combo.currentData() or \"\")" in src


def test_builder_wires_template_selection_to_preview_and_apply() -> None:
    src = _read("src/gui/qt_character_builder_panel.py")

    assert "skeletonTemplateSelected.connect" in src
    assert "_on_skeleton_template_selected" in src
    assert "_typed_skeleton_template_option" in src
    assert "browseSkeletonTemplateRequested.connect" in src
    assert "_on_browse_skeleton_template_requested" in src
    assert '"Choose KOTOR base skeleton MDL"' in src
    assert "applySkeletonTemplateRequested.connect" in src
    assert "_on_apply_skeleton_template_requested" in src
    assert "skeleton_template_picker" in src
    assert "_installed_skeleton_template_rows(game)" in src
    assert "game_models=game_models" in src
    assert "max_results=8000" in src
    assert "_load_skeleton_template_model" in src
    assert "load_game_skeleton_source" in src
    assert "apply_template_rig(" in src
    assert 'scale_mode="manual"' in src
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
    assert "_fit_pos_x_spin" in inspector
    assert "translation_delta" in builder
    assert "set_fit_adjustment" in inspector
    assert "_on_fit_adjustment_changed" in builder
    assert "apply_external_model_fit_adjustment" in builder
    assert "refresh_model_geometry" in viewport
    assert "viewport.frame_all()" in builder
    assert "def apply_external_model_fit_adjustment" in workflow
    assert "translation_delta" in workflow


def test_open_scene_rehydrates_saved_source_models_for_viewport() -> None:
    builder = _read("src/gui/qt_character_builder_panel.py")

    assert "def _load_scene_from_path" in builder
    assert "SceneIO.load(path, load_models=False)" in builder
    assert "def _rehydrate_scene_models_from_sources" in builder
    assert "_body_wf.load_body(" in builder
    assert "_head_wf.load_head(" in builder
    assert "def _load_primary_scene_model_in_viewport" in builder
    assert "_load_model_in_viewport_with_textures(" in builder
    assert "prompt=False" in builder
    assert "SCENE_LOADED" in builder


def test_scene_save_persists_manual_fit_metadata_for_reload() -> None:
    builder = _read("src/gui/qt_character_builder_panel.py")

    assert "def _capture_scene_session_metadata" in builder
    assert 'metadata["manual_fit_adjustment"]' in builder
    assert "def _restore_manual_fit_from_metadata" in builder
    assert "apply_external_model_fit_adjustment(" in builder
    assert "rotation_delta_degrees=rotation" in builder
    assert "scale_delta=scale" in builder
    assert "translation_delta=translation" in builder
    assert "self._capture_scene_session_metadata()" in builder


def test_gpu_viewport_draws_external_reference_skeleton_overlay() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert 'getattr(self._renderer, "_ext_skeleton", None)' in viewport
    assert "self._renderer._draw_ext_skeleton(draw, w, h)" in viewport


def test_gpu_skinning_guards_external_parent_cycles() -> None:
    skinning = _read("src/core/gpu_skinning.py")

    assert "parent cycle detected" in skinning
    assert "ignoring self-parent cycle" in skinning


def test_shift_snaps_viewport_rotation_gimbal_to_ten_degrees() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "QtCore.Qt.ShiftModifier" in viewport
    assert "round(math.degrees(angle) / 10.0) * 10.0" in viewport
    assert "self._gimbal_node_start_rot" in viewport


def test_import_root_gimbal_transforms_whole_mesh_and_supports_scale() -> None:
    viewport = _read("src/gui/qt_viewport.py")
    core = _read("src/gui/viewport_core.py")

    assert "self.set_gimbal_mode(1 if current >= 3 else current + 1)" in viewport
    assert "3: \"Scale\"" in viewport
    assert "def _apply_model_gimbal_drag" in viewport
    assert "apply_external_model_fit_adjustment" in viewport
    assert "translation_delta=translation_delta" in viewport
    assert "scale_delta=scale_delta" in viewport
    assert "def _hit_test_model_bounds" in viewport
    assert "def _draw_selected_model_outline" in viewport
    assert "gimbal_mode: 0=none, 1=translate, 2=rotate, 3=scale" in core
    assert "elif self.gimbal_mode == 3" in core


def test_rotation_gimbal_rings_are_hit_testable() -> None:
    core = _read("src/gui/viewport_core.py")

    assert "_gimbal_handle_lines" in core
    assert "self._gimbal_handle_lines.append" in core
    assert "for x0, y0, x1, y1, axis in getattr(self, \"_gimbal_handle_lines\"" in core


def test_viewport_supports_multi_joint_marquee_and_group_drag() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "_selected_joint_nodes" in viewport
    assert "_joint_marquee_selecting" in viewport
    assert "def _joint_nodes_in_rect" in viewport
    assert "def _set_selected_joint_nodes" in viewport
    assert "Gimbal Multi-Joint Translate" in viewport


def test_external_template_skeleton_is_selectable_and_symmetry_aware() -> None:
    viewport = _read("src/gui/qt_viewport.py")
    core = _read("src/gui/viewport_core.py")
    builder = _read("src/gui/qt_character_builder_panel.py")
    inspector = _read("src/gui/qt_inspector_panel.py")

    assert "_ext_bone_screen_positions" in core
    assert "self._ext_bone_screen_positions.append" in core
    assert "def _joint_hit_positions" in viewport
    assert "ext_positions + bone_positions" in viewport
    assert "def _is_external_skeleton_node" in viewport
    assert "_external_world_delta_to_local" in viewport
    assert "lcollar_dum/rcollar_dum" in viewport
    assert "self._symmetry_action.toggled.connect(self._on_joint_symmetry_toggled)" in builder
    assert "symmetry_cb.setChecked(True)" in inspector
    assert "def set_joint_symmetry" in viewport


def test_selected_imported_mesh_outline_uses_projected_mesh_hull_not_bbox() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    outline_start = viewport.index("def _draw_selected_model_outline")
    outline_end = viewport.index("def _evict_transform_cache", outline_start)
    outline_src = viewport[outline_start:outline_end]

    assert "mesh_nodes()" in outline_src
    assert "hull = lower[:-1] + upper[:-1]" in outline_src
    assert "_get_render_bounds()" not in outline_src


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


def test_gpu_renderer_clamps_single_tile_character_atlases_like_cpu_renderer() -> None:
    viewport = _read("src/gui/viewport_core.py")
    gpu = _read("src/gui/gpu_renderer.py")

    assert "FIX-EDGEBLEED (CPU)" in viewport
    assert "FIX-EDGEBLEED (GPU)" in viewport
    assert "_has_no_repeat_features" in viewport
    assert "_accel_clamp_s = True" in viewport
    assert "_accel_clamp_t = True" in viewport
    assert "0.0 <= u <= 1.0 and 0.0 <= v <= 1.0" in viewport
    assert "def _node_uses_single_tile_atlas" in gpu
    assert "_node_uses_single_tile_atlas(node)" in gpu
    assert "gl_diff.repeat_x = not _node_clamp_s" in gpu
    assert "_gr_gpu_uv_v_flip" in gpu
    assert "img._gr_gpu_uv_v_flip = False" in viewport


def test_manual_v_key_bone_snap_is_wired_without_auto_snap() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "_UE_AUTO_SNAP_MAP" not in viewport
    assert "def auto_snap_external_skeleton_to_imported_unreal" not in viewport
    assert "self.auto_snap_external_skeleton_to_imported_unreal()" not in viewport
    assert "def _nearest_imported_bone_at" in viewport
    assert "def _snap_selected_external_bones_to_imported_at_cursor" in viewport
    assert "self._snap_key_down = True" in viewport
    assert "self._snap_key_down = False" in viewport
    assert "_snap_selected_external_bones_to_imported_at_cursor(x, y)" in viewport


def test_gimbal_translation_uses_projected_visible_axis_direction() -> None:
    viewport = _read("src/gui/qt_viewport.py")

    assert "def _projected_axis_delta" in viewport
    assert "start_sp = self._renderer._proj" in viewport
    assert "end_sp = self._renderer._proj" in viewport
    assert "pixels_along = (float(dx_screen) * sx + float(dy_screen) * sy) / length" in viewport
    assert "return self._projected_axis_delta(" in viewport
    assert "origin_world" in viewport

