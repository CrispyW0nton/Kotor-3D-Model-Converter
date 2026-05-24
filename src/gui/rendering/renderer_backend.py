"""Renderer backend identifiers for the Qt viewport."""

from __future__ import annotations

from enum import Enum


class RendererBackend(str, Enum):
    AUTOMATIC = "automatic"
    MODERNGL_GL330 = "modern_gl"
    WGPU_AUTO = "wgpu_auto"
    WGPU_D3D12 = "wgpu_d3d12"
    WGPU_VULKAN = "wgpu_vulkan"
    WGPU_OPENGL = "wgpu_opengl"
    DIRECT3D_HARDWARE = "direct3d_hardware"
    DIRECT3D_WARP = "direct3d_warp"
    NULL_DIAGNOSTIC = "null_diagnostic"


_ALIASES = {
    "auto": RendererBackend.AUTOMATIC,
    "automatic": RendererBackend.AUTOMATIC,
    "modern_gl": RendererBackend.MODERNGL_GL330,
    "moderngl": RendererBackend.MODERNGL_GL330,
    "opengl": RendererBackend.MODERNGL_GL330,
    "gl330": RendererBackend.MODERNGL_GL330,
    "moderngl_gl330": RendererBackend.MODERNGL_GL330,
    "wgpu": RendererBackend.WGPU_AUTO,
    "wgpu_auto": RendererBackend.WGPU_AUTO,
    "wgpu_d3d12": RendererBackend.WGPU_D3D12,
    "d3d12": RendererBackend.WGPU_D3D12,
    "wgpu_vulkan": RendererBackend.WGPU_VULKAN,
    "vulkan": RendererBackend.WGPU_VULKAN,
    "wgpu_opengl": RendererBackend.WGPU_OPENGL,
    "direct3d": RendererBackend.DIRECT3D_HARDWARE,
    "direct3d_hardware": RendererBackend.DIRECT3D_HARDWARE,
    "d3d_hardware": RendererBackend.DIRECT3D_HARDWARE,
    "direct3d_warp": RendererBackend.DIRECT3D_WARP,
    "d3d_warp": RendererBackend.DIRECT3D_WARP,
    "null": RendererBackend.NULL_DIAGNOSTIC,
    "null_diagnostic": RendererBackend.NULL_DIAGNOSTIC,
}


def normalize_renderer_backend(value: object) -> RendererBackend:
    key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIASES.get(key, RendererBackend.AUTOMATIC)


def renderer_backend_label(backend: RendererBackend) -> str:
    return {
        RendererBackend.AUTOMATIC: "Automatic",
        RendererBackend.MODERNGL_GL330: "ModernGL / OpenGL 3.3",
        RendererBackend.WGPU_AUTO: "WGPU Auto",
        RendererBackend.WGPU_D3D12: "WGPU Direct3D 12",
        RendererBackend.WGPU_VULKAN: "WGPU Vulkan",
        RendererBackend.WGPU_OPENGL: "WGPU OpenGL",
        RendererBackend.DIRECT3D_HARDWARE: "Direct3D Hardware Experimental",
        RendererBackend.DIRECT3D_WARP: "Direct3D WARP Experimental",
        RendererBackend.NULL_DIAGNOSTIC: "Null Diagnostic",
    }[backend]
