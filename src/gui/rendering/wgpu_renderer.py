"""Lazy compatibility facade for the WGPU viewport renderer.

The implementation lives in :mod:`src.gui.rendering.wgpu_core` so the WGPU
backend can be maintained by subsystem without keeping resource caches, renderer
logic, shader text, and probe helpers in one large module.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES: tuple[str, ...] = (
    "src.gui.rendering.wgpu_core.shared",
    "src.gui.rendering.wgpu_core.shaders",
    "src.gui.rendering.wgpu_core.resources",
    "src.gui.rendering.wgpu_core.renderer",
)

_EXPORTS: dict[str, str] = {
    "WgpuRenderer": "src.gui.rendering.wgpu_core.renderer",
    "WgpuResourceCache": "src.gui.rendering.wgpu_core.resources",
    "WgpuMeshResource": "src.gui.rendering.wgpu_core.shared",
    "WgpuTextureResource": "src.gui.rendering.wgpu_core.shared",
    "WgpuMaterialResource": "src.gui.rendering.wgpu_core.shared",
    "WgpuSkeletonResource": "src.gui.rendering.wgpu_core.shared",
    "WgpuSkinResource": "src.gui.rendering.wgpu_core.shared",
    "WgpuPickResources": "src.gui.rendering.wgpu_core.shared",
    "WgpuLightResource": "src.gui.rendering.wgpu_core.shared",
    "_WgpuBackendSpec": "src.gui.rendering.wgpu_core.shared",
    "_load_mesh_shader": "src.gui.rendering.wgpu_core.shaders",
    "_load_skinned_mesh_shader": "src.gui.rendering.wgpu_core.shaders",
    "_GRID_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_LINE_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_SKINNED_LINE_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_PICK_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_MESH_TEXTURED_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_MESH_BASIC_WGSL": "src.gui.rendering.wgpu_core.shaders",
    "_srgb_to_linear": "src.gui.rendering.wgpu_core.shared",
    "_format_is_srgb": "src.gui.rendering.wgpu_core.shared",
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
