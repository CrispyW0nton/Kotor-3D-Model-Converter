"""Lazy compatibility facade for the ModernGL viewport renderer.

The implementation lives in :mod:`src.gui.rendering.gpu_core` so the renderer
can be maintained by subsystem without keeping every shader, diagnostic helper,
resource cache, and public render helper in one very large module.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES: tuple[str, ...] = (
    "src.gui.rendering.gpu_core.diagnostics",
    "src.core.rendering.color_utils",
    "src.core.rendering.gpu_debug_tables",
    "src.core.rendering.gpu_diagnostics_config",
    "src.core.rendering.gpu_diagnostics_records",
    "src.core.rendering.gpu_scene_helpers",
    "src.core.rendering.gpu_shaders",
    "src.core.rendering.gpu_vbo_layout",
    "src.math.gpu_math",
    "src.adapters.gpu.viewport_probe",
    "src.adapters.rendering.moderngl_benchmark",
    "src.adapters.rendering.moderngl_cli",
    "src.adapters.rendering.moderngl_scene_helpers",
    "src.gui.rendering.gpu_core.resources",
    "src.gui.rendering.gpu_core.renderer",
)

_EXPORTS: dict[str, str] = {
    "GpuRenderer": "src.gui.rendering.gpu_core.renderer",
    "ModuleDrawItem": "src.core.rendering.gpu_debug_tables",
    "debug_draw_table": "src.core.rendering.gpu_debug_tables",
    "debug_uv_channel_table": "src.core.rendering.gpu_debug_tables",
    "debug_texture_cache_table": "src.core.rendering.gpu_debug_tables",
    "debug_material_role_table": "src.core.rendering.gpu_debug_tables",
    "clear_prebuilt_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "clear_prebuilt_static_gpu_model_data": "src.gui.rendering.gpu_core.resources",
    "prebuild_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "render_model_autoframe": "src.adapters.rendering.moderngl_scene_helpers",
    "_benchmark": "src.adapters.rendering.moderngl_benchmark",
    "_main": "src.adapters.rendering.moderngl_cli",
    "_VERT_SRC": "src.core.rendering.gpu_shaders",
    "_FRAG_SRC": "src.core.rendering.gpu_shaders",
    "_GRID_VERT_SRC": "src.core.rendering.gpu_shaders",
    "_GRID_FRAG_SRC": "src.core.rendering.gpu_shaders",
    "_GlTexCache": "src.gui.rendering.gpu_core.resources",
    "_GpuMesh": "src.gui.rendering.gpu_core.resources",
    "_PREBUILT_STATIC_MESH_ATTR": "src.gui.rendering.gpu_core.resources",
    "_prebuilt_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "_build_vbo_data": "src.gui.rendering.gpu_core.resources",
    "_split_vbo_attributes_for_gpu": "src.core.rendering.gpu_vbo_layout",
    "_VBO_MAIN_FORMAT": "src.core.rendering.gpu_vbo_layout",
    "_VBO_MAIN_ATTRS": "src.core.rendering.gpu_vbo_layout",
    "_VBO_BONE_IDS_FORMAT": "src.core.rendering.gpu_vbo_layout",
    "_VBO_BONE_IDS_ATTRS": "src.core.rendering.gpu_vbo_layout",
    "_compute_model_bounds": "src.core.rendering.gpu_scene_helpers",
    "_apply_txi_from_textures_to_model": "src.core.rendering.gpu_scene_helpers",
    "_CompositeModel": "src.core.rendering.gpu_scene_helpers",
    "_scene_gpu_root_for_node": "src.math.gpu_math",
    "_scene_gpu_model_matrix": "src.math.gpu_math",
    "_scene_authored_world_transform": "src.math.gpu_math",
    "_hex_to_rgb_float": "src.core.rendering.color_utils",
    "_should_auto_clamp_diffuse": "src.core.rendering.gpu_diagnostics_records",
    "_gr_gpu_probe": "src.adapters.gpu.viewport_probe",
    "_create_moderngl_standalone_context": "src.adapters.gpu.moderngl_context",
    "_gl_context_backend_candidates": "src.adapters.gpu.moderngl_context",
    "_gl_state_trace_path": "src.core.rendering.gpu_diagnostics_config",
    "_lm_data_dump_path": "src.core.rendering.gpu_diagnostics_config",
    "_skin_dump_path": "src.core.rendering.gpu_diagnostics_config",
    "_debug_visualize_mode": "src.core.rendering.gpu_diagnostics_config",
    "_lm_composite_mode": "src.core.rendering.gpu_diagnostics_config",
    "_build_gl_state_trace_record": "src.core.rendering.gpu_diagnostics_records",
    "_build_lm_data_dump_record": "src.core.rendering.gpu_diagnostics_records",
    "_matrix4_json": "src.core.rendering.gpu_diagnostics_records",
    "_matrix4_inverse_json": "src.core.rendering.gpu_diagnostics_records",
    "_matrix4_mul_json": "src.core.rendering.gpu_diagnostics_records",
    "_matrix4_det_value": "src.core.rendering.gpu_diagnostics_records",
    "_uploaded_palette_array_from_uploader": "src.core.rendering.gpu_diagnostics_records",
    "_homogeneous_position_json": "src.core.rendering.gpu_diagnostics_records",
    "_first_divergence_stage": "src.core.rendering.gpu_diagnostics_records",
    "_matrix_max_abs_delta": "src.core.rendering.gpu_diagnostics_records",
    "_matrix_translation_norm": "src.core.rendering.gpu_diagnostics_records",
    "_matrix_rotation_only": "src.core.rendering.gpu_diagnostics_records",
    "_qbone_inverse_bind_json": "src.core.rendering.gpu_diagnostics_records",
    "_qbone_direct_bind_json": "src.core.rendering.gpu_diagnostics_records",
    "_qbone_matrix_np": "src.core.rendering.gpu_diagnostics_records",
    "_node_world_matrix_for_pose_np": "src.core.rendering.gpu_diagnostics_records",
    "_node_pose_chain_records": "src.core.rendering.gpu_diagnostics_records",
    "_quat_xyzw_to_mat4_np": "src.core.rendering.gpu_diagnostics_records",
    "_xoreos_first_frame_orientation_matrix": "src.core.rendering.gpu_diagnostics_records",
    "_SKIN_3G_FORMULAS": "src.core.rendering.gpu_diagnostics_records",
    "_skin_3g_matrix_for_formula": "src.core.rendering.gpu_diagnostics_records",
    "_skin_3g_role_for_bone": "src.core.rendering.gpu_diagnostics_records",
    "_skin_3g_role_priority": "src.core.rendering.gpu_diagnostics_records",
    "_select_skin_3g_probe_vertices": "src.core.rendering.gpu_diagnostics_records",
    "_skin_3g_candidate_records": "src.core.rendering.gpu_diagnostics_records",
    "_skin_live_slot_records": "src.core.rendering.gpu_diagnostics_records",
    "_skin_bind_equivalence_record": "src.core.rendering.gpu_diagnostics_records",
    "_pose_node_transform": "src.core.rendering.gpu_diagnostics_records",
    "_select_skin_probe_vertex": "src.core.rendering.gpu_diagnostics_records",
    "_node_parent_chain_names": "src.core.rendering.gpu_diagnostics_records",
    "_build_skin_dump_record": "src.core.rendering.gpu_diagnostics_records",
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        for candidate in _EXPORT_MODULES:
            module = import_module(candidate)
            if hasattr(module, name):
                value = getattr(module, name)
                globals()[name] = value
                return value
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


if __name__ == "__main__":
    raise SystemExit(__getattr__("_main")())
