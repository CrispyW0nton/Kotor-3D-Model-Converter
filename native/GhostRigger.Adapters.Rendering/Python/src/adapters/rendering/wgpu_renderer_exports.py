"""Lazy public export table for the WGPU viewport renderer adapter."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, str] = {
    "WgpuRenderer": "src.adapters.rendering.wgpu_core.renderer",
    "WgpuResourceCache": "src.adapters.rendering.wgpu_core.resources",
    "WgpuMeshResource": "src.core.rendering.wgpu_shared",
    "WgpuTextureResource": "src.core.rendering.wgpu_shared",
    "WgpuMaterialResource": "src.core.rendering.wgpu_shared",
    "WgpuSkeletonResource": "src.core.rendering.wgpu_shared",
    "WgpuSkinResource": "src.core.rendering.wgpu_shared",
    "WgpuPickResources": "src.core.rendering.wgpu_shared",
    "WgpuLightResource": "src.core.rendering.wgpu_shared",
    "_WgpuBackendSpec": "src.core.rendering.wgpu_shared",
    "_load_mesh_shader": "src.core.rendering.wgpu_shaders",
    "_load_skinned_mesh_shader": "src.core.rendering.wgpu_shaders",
    "_GRID_WGSL": "src.core.rendering.wgpu_shaders",
    "_LINE_WGSL": "src.core.rendering.wgpu_shaders",
    "_SKINNED_LINE_WGSL": "src.core.rendering.wgpu_shaders",
    "_PICK_WGSL": "src.core.rendering.wgpu_shaders",
    "_MESH_TEXTURED_WGSL": "src.core.rendering.wgpu_shaders",
    "_MESH_BASIC_WGSL": "src.core.rendering.wgpu_shaders",
    "_hex_to_rgb_float": "src.core.rendering.color_utils",
    "_srgb_to_linear": "src.core.rendering.wgpu_shared",
    "_format_is_srgb": "src.core.rendering.wgpu_shared",
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
