"""GPU-default adapter for the backend lightmap baking pipeline."""

from __future__ import annotations

from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver
from src.core.lighting.lightmap_baker import LightmapBaker as _CoreLightmapBaker
from src.core.lighting.lightmap_lighting_solver import LightmapLightingSolver


class LightmapBaker(_CoreLightmapBaker):
    """Backend lightmap baker with the GPU solver adapter as the default solver."""

    def __init__(self, *args, lighting_solver=None, **kwargs) -> None:
        super().__init__(
            *args,
            lighting_solver=lighting_solver or LightmapGpuSolver(LightmapLightingSolver()),
            **kwargs,
        )


__all__ = ("LightmapBaker",)
