"""Lazy facade for the viewport frame-rendering backend.

The implementation lives in :mod:`src.core.rendering.frame_core.renderer`.
This keeps renderer, camera, and texture helpers in their owning backend
packages while preserving the historic viewport ``frame_renderer`` import
surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULE = "src.core.rendering.frame_core.renderer"

__all__ = (
    "_GR_VIEWPORT_PROBE",
    "_GR_VIEWPORT_PROBE_SEEN",
    "_gr_probe",
    "log",
    "_normalize",
    "_clean_tex_name",
    "_cross",
    "_dot",
    "_sub",
    "_add",
    "_clamp",
    "_lerp",
    "_uwrap_global",
    "_edge_has_seam_global",
    "_vflip_nontiled",
    "_vflip_tiled",
    "_float_to_sort_key",
    "_compute_screen_size_ratio",
    "_is_tpc_data",
    "_is_tpc_file",
    "_decompress_dxt1_bytes",
    "_decompress_dxt5_bytes",
    "_ensure_bottom_up",
    "_load_tpc_bytes",
    "_extract_txi_from_tpc",
    "_load_tpc_bytes_legacy",
    "_load_tpc_bytes_legacy_inner",
    "_extract_txi_from_tpc_legacy",
    "_parse_txi_string",
    "_extract_alpha_test_from_tpc",
    "_apply_txi_to_node",
    "_compute_flipbook_uv",
    "ArcBallCamera",
    "TextureCache",
    "_rasterize_triangle_textured",
    "_BG",
    "_GRID",
    "_WIRE",
    "_BONE",
    "_SEL",
    "_AXIS_X",
    "_AXIS_Y",
    "_AXIS_Z",
    "_hex_to_rgb_tuple",
    "_rgb_str_to_tuple",
    "_paste_textured_triangle",
    "_paste_lightmap_triangle",
    "FrameRenderer",
)


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORT_MODULE)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
