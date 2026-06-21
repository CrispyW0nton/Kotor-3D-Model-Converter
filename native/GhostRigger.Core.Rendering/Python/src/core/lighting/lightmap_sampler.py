"""Texel sampling helpers for UV-aware lightmap bakes."""

from __future__ import annotations

from .lightmap_rasterizer import LightmapRasterizer, LightmapTexelBuffer


class LightmapSampler:
    def __init__(self, rasterizer: LightmapRasterizer | None = None) -> None:
        self.rasterizer = rasterizer or LightmapRasterizer()

    def sample_mesh(self, mesh: object, uv_channel: int, resolution: int) -> LightmapTexelBuffer:
        return self.rasterizer.rasterize_mesh(mesh, uv_channel, resolution)


__all__ = ["LightmapSampler"]
