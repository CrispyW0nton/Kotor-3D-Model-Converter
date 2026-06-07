"""Compatibility bridge for the current ModernGL renderer implementation.

The concrete ModernGL renderer and resource helpers live in the rendering
adapter package. Keep this module as a stable import route for existing callers
while they migrate to the more focused adapter modules.
"""

from __future__ import annotations

from src.adapters.rendering import moderngl_renderer_impl as _gpu_renderer_impl
from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
from src.adapters.rendering.moderngl_resources import (
    _GlTexCache,
    _GpuMesh,
    _PREBUILT_STATIC_MESH_ATTR,
    _build_vbo_data,
    _prebuilt_static_gpu_mesh_data,
    clear_prebuilt_static_gpu_mesh_data,
    clear_prebuilt_static_gpu_model_data,
    prebuild_static_gpu_mesh_data,
)


def moderngl_runtime_available() -> bool:
    return bool(getattr(_gpu_renderer_impl, "_MODERNGL", False) and getattr(_gpu_renderer_impl, "_NUMPY", False))


__all__ = (
    "GpuRenderer",
    "_GlTexCache",
    "_GpuMesh",
    "_PREBUILT_STATIC_MESH_ATTR",
    "_prebuilt_static_gpu_mesh_data",
    "_build_vbo_data",
    "clear_prebuilt_static_gpu_mesh_data",
    "clear_prebuilt_static_gpu_model_data",
    "prebuild_static_gpu_mesh_data",
    "moderngl_runtime_available",
)
