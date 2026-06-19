"""Shared imports and optional backend bindings for the viewport frame renderer."""

from __future__ import annotations


import math, os, logging, struct, threading, time as _time_mod
# (Tk import removed in T001 split; viewport_tk.py itself was deleted in M3/T302.)

from src.measurement.grid_measurement import GridMeasurement
from src.measurement.unit_system import UnitSystem

from typing import Optional, Dict, List, Tuple, Iterable
try:
    from src.core.geometry.model_data import (KotorModel, ModelNode, NodeFlags, _quat_rotate, _quat_conjugate,
                                   KOTOR_BASE_SKELETONS, is_animation_supermodel)
    from src.core.animation.animation_engine import DanglySimulator
    from src.core.walkmesh.walkmesh_renderer import WalkmeshOverlay, WalkmeshLoader, build_draw_list
    from src.core.special.render_constants import (
        INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
        FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    )
except ImportError:
    from core.geometry.model_data import (  # type: ignore[no-redef]  # tests add src/ to sys.path
        KotorModel, ModelNode, NodeFlags, _quat_rotate, _quat_conjugate,
        KOTOR_BASE_SKELETONS, is_animation_supermodel
    )
    from core.animation.animation_engine import DanglySimulator  # type: ignore[no-redef]
    from core.special.render_constants import (  # type: ignore[no-redef]
        INNER_GEO_SUBSTRINGS as _INNER_GEO_SUBSTRINGS,
        FACE_MESH_SUBSTRINGS as _FACE_MESH_SUBSTRINGS,
    )
    try:
        from core.walkmesh.walkmesh_renderer import WalkmeshOverlay, WalkmeshLoader, build_draw_list
    except ImportError:
        WalkmeshOverlay = None  # type: ignore
        WalkmeshLoader  = None  # type: ignore
        build_draw_list = None  # type: ignore

log = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False
    log.warning("Pillow not found – viewport unavailable")

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False

try:
    from src.core.animation.gpu_skinning import (
        MatrixPaletteUploader as _MatrixPaletteUploader,
        MAX_BONES as _SKIN_MAX_BONES,
    )
except ImportError:
    try:
        from core.animation.gpu_skinning import (  # type: ignore[no-redef]
            MatrixPaletteUploader as _MatrixPaletteUploader,
            MAX_BONES as _SKIN_MAX_BONES,
        )
    except ImportError:
        _MatrixPaletteUploader = None  # type: ignore[assignment]
        _SKIN_MAX_BONES = 128

# ── Acceleration layer (accel.py + tex_atlas.py) ─────────────────────────────
# Provides Numba JIT / NumPy barycentric rasterizers that are 17–40× faster
# than the PIL AFFINE path and vectorised projection / frustum-cull utilities.
# The import is optional – if missing the PIL path is used unchanged.
try:
    from src.core.rendering.accel import (
        ACCEL_TIER as _ACCEL_TIER,
        warmup_jit as _warmup_jit,
        project_vertices_np as _accel_proj_verts,
        frustum_cull_np as _accel_frustum_cull,
        depth_sort_np as _accel_depth_sort,
        rasterize_frame as _accel_rasterize_frame,
        flat_shade_frame as _accel_flat_shade_frame,
        shade_colors_np as _accel_shade_colors,
    )
    from src.core.graphics.tex_atlas import TexArrayCache as _TexArrayCache
    _ACCEL_AVAILABLE = (_ACCEL_TIER in (1, 2))
    log.info(f"viewport: accel tier {_ACCEL_TIER} loaded "
             f"({'Numba JIT' if _ACCEL_TIER == 1 else 'NumPy'} rasterizer)")
except Exception as _accel_err:
    _ACCEL_AVAILABLE = False
    _ACCEL_TIER = 3
    log.debug(f"viewport: accel not available ({_accel_err}) — using PIL AFFINE path")
    # Stubs so the rest of the file can reference these names safely
    def _warmup_jit(): pass
    def _accel_proj_verts(*a, **kw): return None
    def _accel_frustum_cull(*a, **kw): return None
    def _accel_depth_sort(*a, **kw): return None
    def _accel_rasterize_frame(*a, **kw): pass
    def _accel_flat_shade_frame(*a, **kw): pass
    def _accel_shade_colors(*a, **kw): return None
    class _TexArrayCache:  # type: ignore[no-redef]
        def __init__(self, **kw): pass
        def get(self, img): return None
        def clear(self): pass



__all__ = tuple(name for name in globals() if not name.startswith('__'))
