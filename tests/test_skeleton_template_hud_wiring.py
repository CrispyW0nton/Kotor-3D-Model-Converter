"""M12/T1202 source-level guardrails for the skeleton-template HUD flow.

These tests intentionally avoid importing PySide6 so they can run in the
lightweight CI slice. Widget behavior is covered by the source contract here:
the inspector exposes the picker surface, the builder wires it to the
template rig transfer, and the viewport exposes the renderer overlay.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_NATIVE_SOURCE_ROOTS = (
    ROOT / "native" / "GhostRigger.Core.GUI.Display" / "Python",
    ROOT / "native" / "GhostRigger.Core.GUI.Display" / "Python",
    ROOT / "native" / "GhostRigger.Core.GUI.Display" / "Python",
    ROOT / "native" / "GhostRigger.GUI.Rendering.Frame" / "Python",
    ROOT / "native" / "GhostRigger.Core.Unreal" / "Python",
    ROOT / "native" / "GhostRigger.Core.Rendering" / "Python",
    ROOT / "native" / "GhostRigger.Core.Workflow" / "Python",
    ROOT / "native" / "GhostRigger.Core.Workflow" / "Python",
)

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

_SPLIT_SOURCE_MAP = {
    "src/gui/rendering/frame_core/renderer_meshes.py": "src/core/rendering/frame_core/renderer_meshes.py",
    "src/gui/rendering/frame_core/renderer_overlays.py": "src/core/rendering/frame_core/renderer_overlays.py",
    "src/gui/rendering/frame_core/texture_cache.py": "src/core/rendering/frame_core/texture_cache.py",
    "src/gui/rendering/gpu_core/diagnostics.py": "src/core/rendering/gpu_diagnostics_records.py",
    "src/gui/rendering/gpu_core/resources.py": "src/adapters/rendering/moderngl_resources.py",
    "src/gui/rendering/gpu_core/renderer.py": "src/adapters/rendering/moderngl_renderer_impl.py",
}


def _read(relpath: str) -> str:
    if relpath == "src/gui/viewports/qt_viewport.py":
        return "\n".join(_read(path) for path in _VIEWPORT_SOURCE_FILES)
    relpath = _SPLIT_SOURCE_MAP.get(relpath, relpath)
    path = ROOT / relpath
    if path.exists():
        return path.read_text(encoding="utf-8")
    for source_root in _NATIVE_SOURCE_ROOTS:
        native_path = source_root / relpath
        if native_path.exists():
            return native_path.read_text(encoding="utf-8")
    raise FileNotFoundError(relpath)


def test_inspector_exposes_skeleton_template_picker_controls() -> None:
    src = _read("src/gui/panels/qt_inspector_panel.py")

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
    src = _read("src/gui/panels/qt_inspector_panel.py")

    assert "typed = combo.currentText().strip().lower()" in src
    assert "current_label = (" in src
    assert "typed in label or typed in data" in src
    assert 'return f"typed:{typed}"' in src
    assert "current = str(combo.currentData() or \"\")" in src


def test_builder_wires_template_selection_to_preview_and_apply() -> None:
    src = _read("src/gui/panels/qt_character_builder_panel.py")

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


def test_template_apply_replaces_scene_and_viewport_with_rigged_model() -> None:
    src = _read("src/gui/panels/qt_character_builder_panel.py")
    start = src.index("def _on_apply_skeleton_template_requested")
    end = src.index("\n    @QtCore.Slot()\n    def _on_validate_requested", start)
    block = src[start:end]

    assert 'rigged_model = result.get("model")' in block
    assert "_md.PartSlot.HEADLESS_BODY" in block
    assert "self.scene.assign(\n            _md.PartSlot.HEADLESS_BODY,\n            rigged_model," in block
    assert "_load_model_in_viewport_with_textures(\n                    rigged_model," in block
    assert "self._push_import_fit_report_to_inspector(rigged_model)" in block
    assert 'self._schedule_live_validation("skeleton_template_applied")' in block


def test_humanoid_mode_uses_five_step_character_builder_rail() -> None:
    rail = _read("src/gui/panels/qt_workflow_rail.py")
    humanoid_start = rail.index("_STEPS_HUMANOID")
    humanoid_end = rail.index("_STEPS_CREATURE", humanoid_start)
    humanoid_block = rail[humanoid_start:humanoid_end]

    assert "*_STEPS_UNIFIED_CHARACTER_BUILDER" in humanoid_block
    assert "Validate + Export" not in rail
    assert "Load Humanoid" not in rail
    assert "Add Motions" not in rail


def test_template_selection_previews_external_skeleton_overlay() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "viewport.set_external_skeleton(template_model, fit_to_model=False)" in builder
    assert "fit_reference_model=self._selected_skeleton_template_model" in builder
    assert "clear_external_skeleton" in builder
    assert "def set_external_skeleton" in viewport
    assert "fit_to_model: bool = True" in viewport
    assert "self._renderer._ext_skeleton = model" in viewport
    assert "_fit_external_skeleton_overlay" in viewport
    assert "self._renderer._ext_skel_scale = scale" in viewport
    assert "def clear_external_skeleton" in viewport


def test_shared_viewport_exposes_pivot_and_freeze_toolbar_actions() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "ViewportCenterPivotButton" in viewport
    assert "ViewportFreezeTransformsButton" in viewport
    assert "def center_pivot_to_selection" in viewport
    assert "def freeze_selected_transform" in viewport
    assert "def _freeze_world_vertices_for_node" in viewport
    assert "def _mark_node_vertices_as_world_space" in viewport
    assert "_gr_vertices_in_kotor_world = True" in viewport


def test_complete_character_load_and_texture_folder_prompt_are_wired() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")

    assert '"Complete character?"' in builder
    assert "supermodel_complete_character_load" in builder
    assert "CharacterMode.HEADLESS_BODY" in builder
    assert '"Locate texture folder"' in builder
    assert "_load_model_in_viewport_with_textures" in builder
    assert "texture_resolution_report(model, dirs)" in builder


def test_manual_import_fit_controls_are_wired() -> None:
    inspector = _read("src/gui/panels/qt_inspector_panel.py")
    builder = _read("src/gui/panels/qt_character_builder_panel.py")
    viewport = _read("src/gui/viewports/qt_viewport.py")
    workflow = _read("src/core/characters/headless_body_workflow.py")

    assert "fitAdjustmentChanged" in inspector
    assert "refitToSelectedBaseRequested" in inspector
    assert 'QtWidgets.QGroupBox("Import Fit")' in inspector
    assert 'QtWidgets.QPushButton("Re-fit to Selected Base")' in inspector
    assert "Source Forward" in inspector
    assert "Source Up" in inspector
    assert "Bounds Bottom" in inspector
    assert "selected_fit_override" in inspector
    assert "_fit_pos_x_spin" in inspector
    assert "translation_delta" in builder
    assert "set_fit_adjustment" in inspector
    assert "_on_fit_adjustment_changed" in builder
    assert "_on_refit_to_selected_base_requested" in builder
    assert "_external_import_source_path" in builder
    assert "selected_fit_override()" in builder
    assert "fit_reference_model=self._selected_skeleton_template_model" in builder
    assert "fit_override=fit_override" in builder
    assert "apply_external_model_fit_adjustment" in builder
    assert "refresh_model_geometry" in viewport
    assert "viewport.frame_all()" in builder
    assert "def apply_external_model_fit_adjustment" in workflow
    assert "translation_delta" in workflow


def test_motion_library_loader_syncs_inspector_supermodel_before_listing() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")

    assert "def _sync_motion_controls_to_scene" in builder
    assert "selected_motion_source" in builder
    assert "selected_motion_supermodel" in builder
    assert "_sync_motion_controls_to_scene(_wf)" in builder
    assert "available_animation_library(self.scene)" in builder
    assert "SuperModelResolver.clear_cache()" in builder


def test_open_scene_rehydrates_saved_source_models_for_viewport() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")

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
    builder = _read("src/gui/panels/qt_character_builder_panel.py")

    assert "def _capture_scene_session_metadata" in builder
    assert 'metadata["manual_fit_adjustment"]' in builder
    assert "def _restore_manual_fit_from_metadata" in builder
    assert "apply_external_model_fit_adjustment(" in builder
    assert "rotation_delta_degrees=rotation" in builder
    assert "scale_delta=scale" in builder
    assert "translation_delta=translation" in builder
    assert "self._capture_scene_session_metadata()" in builder


def test_gpu_viewport_draws_external_reference_skeleton_overlay() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert 'getattr(self._renderer, "_ext_skeleton", None)' in viewport
    assert "self._renderer._draw_ext_skeleton(draw, w, h)" in viewport


def test_character_builder_pushes_auto_fit_overlay_to_viewport() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")
    viewport = _read("src/gui/viewports/qt_viewport.py")
    renderer = _read("src/gui/rendering/frame_core/renderer_overlays.py")
    setup = _read("src/core/rendering/frame_core/renderer_setup.py")

    assert "report.get(\"fitted_visual_overlay\")" in builder
    assert "report.get(\"visual_overlay\")" in builder
    assert "viewport.set_character_fit_overlay(overlay)" in builder
    assert "viewport.clear_character_fit_overlay()" in builder
    assert "def set_character_fit_overlay" in viewport
    assert "def clear_character_fit_overlay" in viewport
    assert "self._renderer.set_character_fit_overlay(overlay)" in viewport
    assert "_character_fit_overlay" in setup
    assert "def set_character_fit_overlay" in renderer
    assert "def _draw_character_fit_overlay" in renderer


def test_gpu_and_software_paths_draw_character_fit_overlay() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")
    render_loop = _read("src/core/rendering/frame_core/renderer_render_loop.py")

    assert 'getattr(self._renderer, "_character_fit_overlay", None)' in viewport
    assert "self._renderer._draw_character_fit_overlay(draw, w, h)" in viewport
    assert 'getattr(self, "_character_fit_overlay", None)' in render_loop
    assert "self._draw_character_fit_overlay(draw, W, H)" in render_loop


def test_gpu_skinning_guards_external_parent_cycles() -> None:
    skinning = _read("src/core/animation/gpu_skinning.py")

    assert "parent cycle detected" in skinning
    assert "ignoring self-parent cycle" in skinning


def test_shift_snaps_viewport_rotation_gimbal_to_ten_degrees() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "QtCore.Qt.ShiftModifier" in viewport
    assert "round(math.degrees(angle) / 10.0) * 10.0" in viewport
    assert "self._gimbal_node_start_rot" in viewport


def test_import_root_gimbal_transforms_whole_mesh_and_supports_scale() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")
    core = _read("src/gui/rendering/frame_core/renderer_overlays.py")

    assert "self._transform_gizmo.cycle_mode()" in viewport
    assert "def set_gimbal_mode" in viewport
    assert "GizmoMode.SCALE" in viewport
    assert "return \"[S]\" if self._compact_controls else \"[Scale]\"" in viewport
    assert "def _apply_model_gimbal_drag" in viewport
    assert "def _promoted_model_root_for_mesh_transform" in viewport
    assert "self._mesh_transform_promotes_to_model_root = True" in viewport
    assert "apply_external_model_fit_adjustment" in viewport
    assert "translation_delta=translation_delta" in viewport
    assert "scale_delta=scale_delta" in viewport
    assert "pivot_override=getattr" in viewport
    assert "def _hit_test_model_bounds" in viewport
    assert "def _draw_selected_model_outline" in viewport
    assert "Scale mode (gimbal_mode==3)" in core
    assert "elif self.gimbal_mode == 3" in core


def test_character_builder_bind_marks_clean_payload_vertices_as_world_space() -> None:
    builder = _read("src/core/characters/character_builder.py")
    workflow = _read("src/core/characters/headless_body_workflow.py")

    assert "cleaned.vertex_space = 1" in builder
    assert 'setattr(cleaned, "_imported", True)' in builder
    assert 'setattr(cleaned, "_gr_vertices_in_kotor_world", True)' in builder
    assert "pivot_override" in workflow


def test_rotation_gimbal_rings_are_hit_testable() -> None:
    core = _read("src/gui/rendering/frame_core/renderer_overlays.py")

    assert "_gimbal_handle_lines" in core
    assert "self._gimbal_handle_lines.append" in core
    assert "for x0, y0, x1, y1, axis in getattr(self, \"_gimbal_handle_lines\"" in core


def test_viewport_supports_multi_joint_marquee_and_group_drag() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "_selected_joint_nodes" in viewport
    assert "_joint_marquee_selecting" in viewport
    assert "def _joint_nodes_in_rect" in viewport
    assert "def _set_selected_joint_nodes" in viewport
    assert "Gimbal Multi-Joint Translate" in viewport


def test_external_template_skeleton_is_selectable_and_symmetry_aware() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")
    core = _read("src/gui/rendering/frame_core/renderer_overlays.py")
    builder = _read("src/gui/panels/qt_character_builder_panel.py")
    inspector = _read("src/gui/panels/qt_inspector_panel.py")

    assert "_ext_bone_screen_positions" in core
    assert "self._ext_bone_screen_positions.append" in core
    assert "def _joint_hit_positions" in viewport
    assert "ext_positions + bone_positions" in viewport
    assert "def _is_external_skeleton_node" in viewport
    assert "_external_world_delta_to_local" in viewport
    assert "lcollar_dum/rcollar_dum" in viewport
    assert "_prepare_transform_gizmo_symmetry" in viewport
    assert "_apply_transform_gizmo_symmetry" in viewport
    assert "_commit_transform_gizmo_symmetry" in viewport
    assert "self._symmetry_action.toggled.connect(self._on_joint_symmetry_toggled)" in builder
    assert "action.setChecked(enabled)" in builder
    assert "inspector.set_symmetry_enabled(enabled)" in builder
    assert "symmetry_cb.setChecked(True)" in inspector
    assert "self._symmetry_checkboxes.append(symmetry_cb)" in inspector
    assert "def set_symmetry_enabled" in inspector
    assert "def symmetry_enabled" in inspector
    assert "def set_joint_symmetry" in viewport


def test_character_builder_has_rig_tool_belt_and_marking_menus() -> None:
    builder = _read("src/gui/panels/qt_character_builder_panel.py")
    viewport_variants = _read("src/gui/viewports/viewport_core/widgets/variants.py")

    assert 'QtWidgets.QLabel(" Rig: ")' in builder
    assert '("select", "Select"' in builder
    assert '("translate", "Move"' in builder
    assert '("rotate", "Rotate"' in builder
    assert '("transform", "Transform"' in builder
    assert "CharacterBuilderRigToolAction_{key}" in builder
    assert "characterBuilderTransformMarkingMenu" in builder
    assert "characterBuilderRigMarkingMenu" in builder
    assert "characterBuilderRigMarkingQuickButton_{key}" in builder
    assert '("weights", "Weights"' in builder
    assert '("center_pivot", "Center Pivot"' in builder
    assert '("freeze_transforms", "Freeze"' in builder
    assert "def _center_pivot_from_marking_menu" in builder
    assert "def _freeze_transform_from_marking_menu" in builder
    assert "characterBuilderRigMarkingAction_{key}" in builder
    assert '("rom", "Range of Motion Test"' in builder
    assert "def _viewport_external_skeleton_model" in builder
    assert "def _option_from_loaded_skeleton_template" in builder
    assert "or self._viewport_external_skeleton_model()" in builder
    assert "rigTransformMarkingMenuRequested" in viewport_variants
    assert "rigToolsMarkingMenuRequested" in viewport_variants
    assert "DEFAULT_VIEWPORT_TOOLBAR_VISIBLE = False" in viewport_variants
    assert "DEFAULT_MAP_STUDIO_AUTHORING_CHROME = True" in viewport_variants
    assert "tabs.hide()" not in viewport_variants


def test_selected_imported_mesh_outline_uses_projected_mesh_hover_path_not_bbox() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    helper_start = viewport.index("def _draw_hovered_mesh_outline")
    helper_end = viewport.index("def _draw_selected_model_outline", helper_start)
    outline_src = viewport[helper_start:helper_end]
    selected_start = viewport.index("def _draw_selected_model_outline")
    selected_end = viewport.index("def _draw_mesh_subobject_selection", selected_start)
    selected_src = viewport[selected_start:selected_end]

    assert "self._draw_hovered_mesh_outline(draw, w, h)" in selected_src
    assert "_projected_mesh_bounds(node, w, h)" in outline_src
    assert "edge_faces" in outline_src
    assert "_get_render_bounds()" not in outline_src


def test_viewport_preloads_textures_for_skin_nodes() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "def _preload_gpu_textures" in viewport
    assert "def _prewarm_textures" in viewport
    assert 'getattr(node, "is_skin", False)' in viewport
    assert "model.all_nodes()" in viewport


def test_external_dcc_imports_disable_kotor_uv_seam_repair() -> None:
    workflow = _read("src/core/characters/headless_body_workflow.py")
    viewport = _read("src/gui/rendering/frame_core/renderer_meshes.py")

    assert "def _mark_external_import" in workflow
    assert 'setattr(node, "_external_imported", True)' in workflow
    assert 'getattr(node, "_external_imported", False)' in viewport
    assert "_face_has_u_seam = False" in viewport
    assert "_face_has_v_seam = False" in viewport


def test_gpu_renderer_clamps_single_tile_character_atlases_like_cpu_renderer() -> None:
    viewport = (
        _read("src/gui/rendering/frame_core/renderer_meshes.py")
        + _read("src/gui/rendering/frame_core/texture_cache.py")
    )
    gpu = (
        _read("src/gui/rendering/gpu_core/diagnostics.py")
        + _read("src/gui/rendering/gpu_core/resources.py")
        + _read("src/gui/rendering/gpu_core/renderer.py")
    )

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
    assert "img._gr_gpu_uv_v_flip = True" in viewport


def test_manual_v_key_bone_snap_is_wired_without_auto_snap() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "_UE_AUTO_SNAP_MAP" not in viewport
    assert "def auto_snap_external_skeleton_to_imported_unreal" not in viewport
    assert "self.auto_snap_external_skeleton_to_imported_unreal()" not in viewport
    assert "def _nearest_imported_bone_at" in viewport
    assert "def _snap_selected_external_bones_to_imported_at_cursor" in viewport
    assert "def _nearest_visible_bone_dot_at" in viewport
    assert "def _snap_joint_drag_to_visible_bone_at_cursor" in viewport
    assert "self._snap_key_down = True" in viewport
    assert "self._snap_key_down = False" in viewport
    assert "_snap_selected_external_bones_to_imported_at_cursor(x, y)" in viewport
    assert "_snap_joint_drag_to_visible_bone_at_cursor(x, y)" in viewport


def test_gimbal_translation_uses_projected_visible_axis_direction() -> None:
    viewport = _read("src/gui/viewports/qt_viewport.py")

    assert "def _projected_axis_delta" in viewport
    assert "start_sp = self._renderer._proj" in viewport
    assert "end_sp = self._renderer._proj" in viewport
    assert "pixels_along = (float(dx_screen) * sx + float(dy_screen) * sy) / length" in viewport
    assert "return self._projected_axis_delta(" in viewport
    assert "origin_world" in viewport
