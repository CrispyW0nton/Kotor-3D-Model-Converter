"""Compatibility facade for application-core geometry helpers."""

from __future__ import annotations

from src.gui.windows.application_core.application_core_lib.functions.geometry import (
    _bounds_center,
    _bounds_from_points,
    _bounds_overlap_xy,
    _prebuild_gpu_mesh_data_for_model,
    _walkmesh_overlay_node_from_wok,
    _walkmesh_overlay_offset_for_model,
    _walkmesh_reference_bounds,
)

__all__ = [
    "_bounds_center",
    "_bounds_from_points",
    "_bounds_overlap_xy",
    "_prebuild_gpu_mesh_data_for_model",
    "_walkmesh_overlay_node_from_wok",
    "_walkmesh_overlay_offset_for_model",
    "_walkmesh_reference_bounds",
]
