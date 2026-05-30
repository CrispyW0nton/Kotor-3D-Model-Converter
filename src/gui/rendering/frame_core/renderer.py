"""Lazy-composed viewport frame renderer public implementation module.

The large historical renderer body is split across focused frame_core modules.
Import this backend directly when code needs the software ``FrameRenderer``.
"""

from __future__ import annotations

from .diagnostics import _GR_VIEWPORT_PROBE, _GR_VIEWPORT_PROBE_SEEN, _gr_probe, log
from src.math.frame_math import (
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
from src.gui.textures.tpc import (
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
from src.gui.textures.txi import (
    _apply_txi_to_node,
    _compute_flipbook_uv,
    _extract_alpha_test_from_tpc,
    _parse_txi_string,
)
from src.gui.camera.arcball_camera import ArcBallCamera
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

    MAX_TRIS = 80_000
    MAX_TRIS_TEXTURED = 5_000
    MAX_TRIS_TEXTURED_ACCEL = 10_000
    MAX_TRIS_TEXTURED_STILL = 50_000
    MAX_TRIS_INTERACTIVE = 10_000
    _DEPTH_EPSILON = 0.0001
    _DANGLY_PIN_THRESHOLD: float = 0.999
    _KEY_JOINT_NAMES = frozenset({
        "root", "rootdummy", "pelvis", "pelvis_g", "hip", "hips",
        "spine", "spine_01", "spine_02", "spine_03", "spine_04", "spine_05",
        "torso_g", "torsoupr_g", "neck", "neck_g", "necklwr_g",
        "neck_01", "neck_02", "head", "head_g",
        "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r",
        "lowerarm_l", "lowerarm_r", "hand_l", "hand_r", "lhand", "rhand",
        "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g", "lhand_g", "rhand_g",
        "thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r",
        "ball_l", "ball_r", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g",
        "lfoot_g", "rfoot_g", "lfoott_g", "rfoott_g",
    })


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
