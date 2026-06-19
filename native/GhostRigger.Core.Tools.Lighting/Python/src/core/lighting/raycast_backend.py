"""Raycast backend facade used by the lightmap baker."""

from __future__ import annotations

from .lightmap_shadow_solver import LightmapShadowSolver


class Open3DRaycastBackend(LightmapShadowSolver):
    """Open3D-backed shadow raycaster with the legacy CPU path as fallback."""


__all__ = ["Open3DRaycastBackend"]
