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
    "src.gui.rendering.gpu_core.debug_tables",
    "src.gui.rendering.gpu_core.shaders",
    "src.math.gpu_math",
    "src.gui.rendering.gpu_core.resources",
    "src.gui.rendering.gpu_core.renderer",
    "src.gui.rendering.gpu_core.scene_helpers",
    "src.gui.rendering.gpu_core.benchmark",
    "src.gui.rendering.gpu_core.cli",
)

_EXPORTS: dict[str, str] = {
    "GpuRenderer": "src.gui.rendering.gpu_core.renderer",
    "ModuleDrawItem": "src.gui.rendering.gpu_core.debug_tables",
    "debug_draw_table": "src.gui.rendering.gpu_core.debug_tables",
    "debug_uv_channel_table": "src.gui.rendering.gpu_core.debug_tables",
    "debug_texture_cache_table": "src.gui.rendering.gpu_core.debug_tables",
    "debug_material_role_table": "src.gui.rendering.gpu_core.debug_tables",
    "clear_prebuilt_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "clear_prebuilt_static_gpu_model_data": "src.gui.rendering.gpu_core.resources",
    "prebuild_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "render_model_autoframe": "src.gui.rendering.gpu_core.scene_helpers",
    "_benchmark": "src.gui.rendering.gpu_core.benchmark",
    "_main": "src.gui.rendering.gpu_core.cli",
    "_VERT_SRC": "src.gui.rendering.gpu_core.shaders",
    "_FRAG_SRC": "src.gui.rendering.gpu_core.shaders",
    "_GRID_VERT_SRC": "src.gui.rendering.gpu_core.shaders",
    "_GRID_FRAG_SRC": "src.gui.rendering.gpu_core.shaders",
    "_GlTexCache": "src.gui.rendering.gpu_core.resources",
    "_GpuMesh": "src.gui.rendering.gpu_core.resources",
    "_PREBUILT_STATIC_MESH_ATTR": "src.gui.rendering.gpu_core.resources",
    "_prebuilt_static_gpu_mesh_data": "src.gui.rendering.gpu_core.resources",
    "_build_vbo_data": "src.gui.rendering.gpu_core.resources",
    "_split_vbo_attributes_for_gpu": "src.gui.rendering.gpu_core.resources",
    "_compute_model_bounds": "src.gui.rendering.gpu_core.scene_helpers",
    "_apply_txi_from_textures_to_model": "src.gui.rendering.gpu_core.scene_helpers",
    "_CompositeModel": "src.gui.rendering.gpu_core.scene_helpers",
    "_scene_gpu_root_for_node": "src.math.gpu_math",
    "_scene_gpu_model_matrix": "src.math.gpu_math",
    "_scene_authored_world_transform": "src.math.gpu_math",
    "_should_auto_clamp_diffuse": "src.gui.rendering.gpu_core.diagnostics",
    "_create_moderngl_standalone_context": "src.gui.rendering.gpu_core.diagnostics",
    "_gl_context_backend_candidates": "src.gui.rendering.gpu_core.diagnostics",
    "_gl_state_trace_path": "src.gui.rendering.gpu_core.diagnostics",
    "_lm_data_dump_path": "src.gui.rendering.gpu_core.diagnostics",
    "_skin_dump_path": "src.gui.rendering.gpu_core.diagnostics",
    "_debug_visualize_mode": "src.gui.rendering.gpu_core.diagnostics",
    "_lm_composite_mode": "src.gui.rendering.gpu_core.diagnostics",
    "_build_gl_state_trace_record": "src.gui.rendering.gpu_core.diagnostics",
    "_build_lm_data_dump_record": "src.gui.rendering.gpu_core.diagnostics",
    "_build_skin_dump_record": "src.gui.rendering.gpu_core.diagnostics",
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
