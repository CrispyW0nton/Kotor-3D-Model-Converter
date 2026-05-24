"""ModernGL/OpenGL 3.3 renderer adapter."""

from __future__ import annotations

from src.gui.rendering.gpu_renderer import GpuRenderer
from src.gui.rendering.renderer_backend import RendererBackend
from src.gui.rendering.renderer_capabilities import RendererCapabilities


class ModernGLRenderer(GpuRenderer):
    """Adapter that keeps the existing ModernGL renderer behavior intact."""

    name = "ModernGL / OpenGL 3.3"
    backend_id = RendererBackend.MODERNGL_GL330.value

    def is_available(self) -> bool:
        try:
            from src.gui.rendering import gpu_renderer

            return bool(getattr(gpu_renderer, "_MODERNGL", False) and getattr(gpu_renderer, "_NUMPY", False))
        except Exception:
            return False

    def get_capabilities(self) -> RendererCapabilities:
        available = self.is_available()
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=available,
            reason="" if available else "moderngl or numpy is not installed",
            api="OpenGL 3.3",
            supports_scene_meshes=True,
            supports_textures=True,
            supports_grid=True,
            supports_overlays=True,
            supports_hot_switch=True,
        )

    def shutdown(self) -> None:
        self.release()

    def get_diagnostics(self) -> dict:
        ctx = getattr(self, "_ctx", None)
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": bool(getattr(self, "_gpu_available", False)),
            "api": "OpenGL",
            "backend": "ModernGL",
            "version_code": getattr(ctx, "version_code", None),
            "gpu": getattr(ctx, "info", {}).get("GL_RENDERER") if ctx is not None else None,
            "vendor": getattr(ctx, "info", {}).get("GL_VENDOR") if ctx is not None else None,
        }

