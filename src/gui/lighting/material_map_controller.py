"""Viewport material map preview state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialMapController:
    diffuse: bool = True
    normal: bool = True
    environment: bool = True
    specular: bool = True
    lightmap: bool = True

    def set_enabled(self, map_name: str, enabled: bool) -> None:
        key = str(map_name or "").lower()
        if key == "env":
            key = "environment"
        if hasattr(self, key):
            setattr(self, key, bool(enabled))

    def to_renderer_attrs(self) -> dict[str, bool]:
        return {
            "show_diffuse_map": self.diffuse,
            "show_normal_map": self.normal,
            "show_environment_map": self.environment,
            "show_specular_map": self.specular,
            "show_lightmap_map": self.lightmap,
        }
