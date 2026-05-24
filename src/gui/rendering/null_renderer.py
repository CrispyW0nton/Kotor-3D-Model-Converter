"""Null diagnostic viewport renderer."""

from __future__ import annotations

import time

from src.gui.rendering.renderer_backend import RendererBackend
from src.gui.rendering.renderer_capabilities import RendererCapabilities
from src.gui.rendering.renderer_interface import IViewportRenderer


class NullDiagnosticRenderer(IViewportRenderer):
    name = "Null Diagnostic"
    backend_id = RendererBackend.NULL_DIAGNOSTIC.value

    def __init__(self):
        self.interactive = False
        self.show_solid = True
        self.show_texture = True
        self.show_diffuse_map = True
        self.show_lightmap_map = True
        self.show_environment_map = True
        self.show_specular_map = True
        self.show_normal_map = True
        self.lighting_mode = "scene"
        self.scene_ambient = 0.06
        self.lightmap_intensity = 0.55
        self.lightmap_mode = "baked"
        self.show_light_gizmos = True
        self.show_wireframe = False
        self.render_mode = "realistic"
        self.selected_node = None
        self.selected_nodes = []
        self.show_grid = True
        self.cull_faces = False
        self.deferred_mesh_uploads = False
        self._mesh_cache = {}
        self.viewport_background = (23 / 255.0, 25 / 255.0, 28 / 255.0)
        self.perf = {"last_frame_ms": 0.0, "backend": self.backend_id, "tri_count": 0}
        self._diagnostics: dict[str, object] = {}

    def is_available(self) -> bool:
        return True

    def get_capabilities(self) -> RendererCapabilities:
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=True,
            api="None",
            supports_scene_meshes=False,
            supports_textures=False,
            supports_grid=False,
            supports_overlays=True,
            supports_hot_switch=True,
            diagnostic_only=True,
        )

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if W <= 0 or H <= 0:
            return None
        t0 = time.perf_counter()
        try:
            from PIL import Image, ImageDraw
        except Exception:
            return None
        rgb = tuple(max(0, min(255, int(round(v * 255.0)))) for v in self.viewport_background[:3])
        img = Image.new("RGBA", (int(W), int(H)), (*rgb, 255))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.text((12, 12), "Null Diagnostic Renderer", fill=(220, 225, 230, 220))
        self.perf["last_frame_ms"] = (time.perf_counter() - t0) * 1000.0
        return img

    def set_theme_colors(self, theme) -> None:
        raw = str(theme.color("viewport.background") or "").strip().lstrip("#")
        if len(raw) == 6:
            try:
                self.viewport_background = tuple(int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
            except ValueError:
                pass

    def set_native_palette_colors(self, *, base, text, highlight) -> None:
        self.viewport_background = tuple(max(0.0, min(1.0, float(v) / 255.0)) for v in base[:3])

    def clear_caches(self) -> None:
        self._mesh_cache.clear()

    def reset_framebuffers(self) -> None:
        return None

    def invalidate_node(self, node) -> None:
        return None

    def invalidate_node_cache(self) -> None:
        return None

    def invalidate_all(self) -> None:
        self.clear_caches()

    def get_diagnostics(self) -> dict:
        return {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": True,
            "api": "None",
            "backend": "diagnostic",
            **self._diagnostics,
        }

