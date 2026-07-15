"""Base interface for viewport renderer backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.core.rendering.renderer_capabilities import RendererCapabilities


class IViewportRenderer(ABC):
    name: str = "Viewport Renderer"
    backend_id: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> RendererCapabilities:
        raise NotImplementedError

    def initialize(self, viewport_widget=None, scene_context=None) -> None:
        return None

    def create_surface_widget(self, parent=None):
        return None

    def resize(self, width: int, height: int, device_pixel_ratio: float = 1.0) -> None:
        return None

    @abstractmethod
    def render(self, scene, camera, *args, **kwargs):
        raise NotImplementedError

    def render_overlay(self, overlay_context) -> None:
        return None

    def pick(self, request, scene=None, camera=None):
        return None

    def shutdown(self) -> None:
        release = getattr(self, "release", None)
        if callable(release):
            release()

    def get_diagnostics(self) -> dict:
        caps = self.get_capabilities()
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": caps.available,
            "reason": caps.reason,
            "api": caps.api,
        }

    def upload_mesh(self, mesh):
        return None

    def upload_texture(self, texture):
        return None

    def update_texture_regions(self, texture_name: str, image, regions, *, finalize: bool = True) -> bool:
        """Patch dirty cached-image rectangles when the backend supports it.

        ``finalize=False`` permits a backend to defer expensive derived data,
        such as mip-chain generation, until the final call for a stroke.
        """
        return False

    def invalidate_texture(self, texture_name: str, image=None) -> bool:
        """Evict only one named texture as a partial-update fallback."""
        return False

    def release_resource(self, resource_id) -> None:
        return None

    def invalidate_all(self) -> None:
        return None
