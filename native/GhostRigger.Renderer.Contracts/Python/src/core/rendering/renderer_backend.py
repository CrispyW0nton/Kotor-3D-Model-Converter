"""Renderer backend identifiers for viewport renderer adapters."""

from __future__ import annotations

from enum import Enum


class RendererBackend(str, Enum):
    AUTOMATIC = "automatic"
    MODERNGL_GL330 = "modern_gl"
    WGPU_AUTO = "wgpu_auto"
    WGPU_D3D12 = "wgpu_d3d12"
    WGPU_VULKAN = "wgpu_vulkan"
    WGPU_OPENGL = "wgpu_opengl"
    PYGFX_WGPU = "pygfx_wgpu"
    NATIVE_D3D12 = "native_d3d12"
    DIRECT3D_HARDWARE = "direct3d_hardware"
    DIRECT3D_WARP = "direct3d_warp"
    NULL_DIAGNOSTIC = "null_diagnostic"


SUPPORTED_RENDERER_BACKENDS = (
    RendererBackend.MODERNGL_GL330,
    RendererBackend.WGPU_D3D12,
    RendererBackend.PYGFX_WGPU,
)


_ALIASES = {
    "auto": RendererBackend.MODERNGL_GL330,
    "automatic": RendererBackend.MODERNGL_GL330,
    "modern_gl": RendererBackend.MODERNGL_GL330,
    "moderngl": RendererBackend.MODERNGL_GL330,
    "opengl": RendererBackend.MODERNGL_GL330,
    "gl330": RendererBackend.MODERNGL_GL330,
    "moderngl_gl330": RendererBackend.MODERNGL_GL330,
    "wgpu": RendererBackend.WGPU_D3D12,
    "wgpu_auto": RendererBackend.WGPU_D3D12,
    "wgpu_d3d12": RendererBackend.WGPU_D3D12,
    "d3d12": RendererBackend.WGPU_D3D12,
    "direct3d_wgpu": RendererBackend.WGPU_D3D12,
    "direct3d_(wgpu)": RendererBackend.WGPU_D3D12,
    "direct3d/wgpu": RendererBackend.WGPU_D3D12,
    "direct3d": RendererBackend.WGPU_D3D12,
    "wgpu_vulkan": RendererBackend.WGPU_D3D12,
    "vulkan": RendererBackend.WGPU_D3D12,
    "wgpu_opengl": RendererBackend.WGPU_D3D12,
    "pygfx": RendererBackend.PYGFX_WGPU,
    "pygfx_wgpu": RendererBackend.PYGFX_WGPU,
    "pygfx_(wgpu)": RendererBackend.PYGFX_WGPU,
    "pygfx/wgpu": RendererBackend.PYGFX_WGPU,
    "native": RendererBackend.WGPU_D3D12,
    "native_d3d12": RendererBackend.WGPU_D3D12,
    "native/d3d12": RendererBackend.WGPU_D3D12,
    "ghostrigger_native": RendererBackend.WGPU_D3D12,
    "gr_native": RendererBackend.WGPU_D3D12,
    "direct3d_hardware": RendererBackend.WGPU_D3D12,
    "d3d_hardware": RendererBackend.WGPU_D3D12,
    "direct3d_warp": RendererBackend.WGPU_D3D12,
    "d3d_warp": RendererBackend.WGPU_D3D12,
    "null": RendererBackend.NULL_DIAGNOSTIC,
    "null_diagnostic": RendererBackend.NULL_DIAGNOSTIC,
}


def normalize_renderer_backend(value: object) -> RendererBackend:
    if isinstance(value, RendererBackend):
        value = value.value
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(key, RendererBackend.MODERNGL_GL330)


def supported_renderer_backend(value: object) -> RendererBackend:
    backend = normalize_renderer_backend(value)
    if backend in SUPPORTED_RENDERER_BACKENDS or backend == RendererBackend.NULL_DIAGNOSTIC:
        return backend
    return RendererBackend.WGPU_D3D12 if backend.value.startswith("wgpu") else RendererBackend.MODERNGL_GL330


def renderer_backend_label(backend: RendererBackend) -> str:
    backend = supported_renderer_backend(backend)
    return {
        RendererBackend.MODERNGL_GL330: "ModernGL",
        RendererBackend.WGPU_D3D12: "Direct3D (WGPU)",
        RendererBackend.PYGFX_WGPU: "pygfx (WGPU)",
        RendererBackend.NULL_DIAGNOSTIC: "Null Diagnostic",
    }[backend]
