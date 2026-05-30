"""Lazy-composed viewport frame renderer public implementation module.

The large historical renderer body is split across focused frame_core modules.
Import through ``src.gui.qt_lib.viewports.frame_renderer`` or
``src.gui.viewports.frame_renderer`` so this module remains an implementation
detail.
"""

from __future__ import annotations

from .diagnostics import _GR_VIEWPORT_PROBE, _GR_VIEWPORT_PROBE_SEEN, _gr_probe, log
from .math_helpers import (
    _add,
    _clamp,
    _clean_tex_name,
    _compute_screen_size_ratio,
    _cross,
    _dot,
    _edge_has_seam_global,
    _float_to_sort_key,
    _lerp,
    _normalize,
    _sub,
    _uwrap_global,
    _vflip_nontiled,
    _vflip_tiled,
)
from .tpc import (
    _decompress_dxt1_bytes,
    _decompress_dxt5_bytes,
    _ensure_bottom_up,
    _extract_txi_from_tpc,
    _extract_txi_from_tpc_legacy,
    _is_tpc_data,
    _is_tpc_file,
    _load_tpc_bytes,
    _load_tpc_bytes_legacy,
    _load_tpc_bytes_legacy_inner,
)
from .txi import (
    _apply_txi_to_node,
    _compute_flipbook_uv,
    _extract_alpha_test_from_tpc,
    _parse_txi_string,
)
from .camera import ArcBallCamera
from .texture_cache import TextureCache
from .rasterizer import _rasterize_triangle_textured
from .colors import (
    _AXIS_X,
    _AXIS_Y,
    _AXIS_Z,
    _BG,
    _BONE,
    _GRID,
    _SEL,
    _WIRE,
    _hex_to_rgb_tuple,
    _paste_lightmap_triangle,
    _paste_textured_triangle,
    _rgb_str_to_tuple,
)
from .renderer_setup import RendererSetupMixin
from .renderer_render_loop import RendererRenderLoopMixin
from .renderer_textures import RendererTextureMixin
from .renderer_geometry import RendererGeometryMixin
from .renderer_meshes import RendererMeshMixin
from .renderer_overlays import RendererOverlayMixin


class FrameRenderer(
    RendererSetupMixin,
    RendererRenderLoopMixin,
    RendererTextureMixin,
    RendererGeometryMixin,
    RendererMeshMixin,
    RendererOverlayMixin,
):
    """Tk-free frame renderer composed from focused mixin modules."""


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
