"""Compatibility exports for ModernGL diagnostics helpers.

This adapter-owned table keeps old diagnostic import paths working while the
actual helpers live in core rendering modules or concrete GPU adapters.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from src.adapters.gpu.moderngl_context import (
    _create_moderngl_standalone_context,
    _gl_context_backend_candidates,
)
from src.core.geometry.model_data import KOTOR_BASE_SKELETONS as _KOTOR_BASE_SKELETONS
from src.core.lighting.light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_COLORS,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SELECTED_BOOST,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)
from src.core.rendering.gpu_debug_tables import ModuleDrawItem
from src.core.special.render_constants import (
    FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
)

_MODULE_EXPORTS: dict[str, str] = {
    "Image": "src.adapters.gpu.moderngl_runtime",
    "MatrixPaletteUploader": "src.adapters.gpu.moderngl_runtime",
    "_GPU_SKINNING": "src.adapters.gpu.moderngl_runtime",
    "_MODERNGL": "src.adapters.gpu.moderngl_runtime",
    "_NUMPY": "src.adapters.gpu.moderngl_runtime",
    "_PIL": "src.adapters.gpu.moderngl_runtime",
    "_SKIN_MAX_BONES": "src.adapters.gpu.moderngl_runtime",
    "moderngl": "src.adapters.gpu.moderngl_runtime",
    "np": "src.adapters.gpu.moderngl_runtime",
    "_GR_GPU_PROBE": "src.adapters.gpu.viewport_probe",
    "_GR_GPU_PROBE_SEEN": "src.adapters.gpu.viewport_probe",
    "_gr_gpu_probe": "src.adapters.gpu.viewport_probe",
    "annotations": "src.core.rendering.color_utils",
    "_hex_to_rgb_float": "src.core.rendering.color_utils",
    "os": "src.core.rendering.gpu_diagnostics_config",
    "_GL_STATE_TRACE_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_GL_DEBUG_ERRORS_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_GL_STATE_TRACE_TRUE": "src.core.rendering.gpu_diagnostics_config",
    "_GL_STATE_TRACE_FALSE": "src.core.rendering.gpu_diagnostics_config",
    "_GL_BACKEND_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_DEBUG_VIZ_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_LM_DATA_DUMP_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_LM_COMPOSITE_MODE_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_SKIN_DUMP_ENV": "src.core.rendering.gpu_diagnostics_config",
    "_gl_state_trace_path": "src.core.rendering.gpu_diagnostics_config",
    "_lm_data_dump_path": "src.core.rendering.gpu_diagnostics_config",
    "_skin_dump_path": "src.core.rendering.gpu_diagnostics_config",
    "_debug_visualize_mode": "src.core.rendering.gpu_diagnostics_config",
    "_lm_composite_mode": "src.core.rendering.gpu_diagnostics_config",
    "json": "src.core.rendering.gpu_diagnostics_records",
    "hashlib": "src.core.rendering.gpu_diagnostics_records",
    "logging": "src.core.rendering.gpu_diagnostics_records",
    "time": "src.core.rendering.gpu_diagnostics_records",
    "Dict": "src.core.rendering.gpu_diagnostics_records",
    "List": "src.core.rendering.gpu_diagnostics_records",
    "Optional": "src.core.rendering.gpu_diagnostics_records",
    "Tuple": "src.core.rendering.gpu_diagnostics_records",
    "log": "src.core.rendering.gpu_diagnostics_records",
    "_matrix_from_pos_quat_np": "src.core.rendering.gpu_diagnostics_records",
    "_VBO_BONE_IDS_FORMAT": "src.core.rendering.gpu_diagnostics_records",
    "_VBO_MAIN_FORMAT": "src.core.rendering.gpu_diagnostics_records",
    "_jsonable_gl_value": "src.core.rendering.gpu_diagnostics_records",
    "_safe_gl_attr": "src.core.rendering.gpu_diagnostics_records",
    "_uniform_trace_value": "src.core.rendering.gpu_diagnostics_records",
    "_build_gl_state_trace_record": "src.core.rendering.gpu_diagnostics_records",
    "_append_gl_state_trace": "src.core.rendering.gpu_diagnostics_records",
    "_first_uv_pairs": "src.core.rendering.gpu_diagnostics_records",
    "_first_vbo_uv_pairs": "src.core.rendering.gpu_diagnostics_records",
    "_texture_content_stats": "src.core.rendering.gpu_diagnostics_records",
    "_lightmap_role_info": "src.core.rendering.gpu_diagnostics_records",
    "_build_lm_data_dump_record": "src.core.rendering.gpu_diagnostics_records",
    "_append_jsonl_record": "src.core.rendering.gpu_diagnostics_records",
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
    "_skin_bind_equivalence_record": "src.core.rendering.gpu_diagnostics_records",
    "_skin_3g_candidate_records": "src.core.rendering.gpu_diagnostics_records",
    "_skin_live_slot_records": "src.core.rendering.gpu_diagnostics_records",
    "_build_skin_dump_record": "src.core.rendering.gpu_diagnostics_records",
    "_pose_node_transform": "src.core.rendering.gpu_diagnostics_records",
    "_select_skin_probe_vertex": "src.core.rendering.gpu_diagnostics_records",
    "_node_parent_chain_names": "src.core.rendering.gpu_diagnostics_records",
    "_node_uses_single_tile_atlas": "src.core.rendering.gpu_diagnostics_records",
    "_should_auto_clamp_diffuse": "src.core.rendering.gpu_diagnostics_records",
}

_DIRECT_EXPORTS = (
    "_create_moderngl_standalone_context",
    "_gl_context_backend_candidates",
    "_KOTOR_BASE_SKELETONS",
    "LIGHT_HELPER_AREA_SIZE",
    "LIGHT_HELPER_COLORS",
    "LIGHT_HELPER_DIRECTION_LENGTH",
    "LIGHT_HELPER_MARKER_RADIUS",
    "LIGHT_HELPER_POINT_RADIUS",
    "LIGHT_HELPER_SELECTED_BOOST",
    "LIGHT_HELPER_SPOT_CAP_MAX_RADIUS",
    "LIGHT_HELPER_SPOT_LENGTH",
    "ModuleDrawItem",
    "_FACE_MESH_SUBSTRINGS",
    "_INNER_GEO_SUBSTRINGS",
)

__all__ = tuple(sorted(set(_DIRECT_EXPORTS) | set(_MODULE_EXPORTS)))


def __getattr__(name: str) -> Any:
    module_name = _MODULE_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
