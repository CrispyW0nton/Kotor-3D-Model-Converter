"""Bridge lighting UI state into viewport renderer attributes."""

from __future__ import annotations

from src.core.lighting.lightmap_controller import LightmapController
from src.core.lighting.material_map_controller import MaterialMapController


class LightingViewportController:
    def __init__(self) -> None:
        self.maps = MaterialMapController()
        self.lightmap = LightmapController()
        self.show_helpers = True
        self.show_volumes = False
        self.shader_complexity_mode = "off"

    def apply_to_renderer(self, renderer: object) -> None:
        for attr, value in self.maps.to_renderer_attrs().items():
            setattr(renderer, attr, value)
        setattr(renderer, "lightmap_intensity", self.lightmap.intensity)
        setattr(renderer, "lightmap_mode", self.lightmap.mode)
        setattr(renderer, "show_light_gizmos", self.show_helpers)
        setattr(renderer, "show_light_radius_volumes", self.show_volumes)
        setattr(renderer, "shader_complexity_mode", self.shader_complexity_mode)
