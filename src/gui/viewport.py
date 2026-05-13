"""
3D Viewport Widget – GhostRigger-K1-K2
=======================================
Fast software rasterizer using a PIL ImageDraw buffer.
Each frame is drawn into a single PIL Image and displayed with
one Canvas.create_image() call – no per-triangle Canvas items.

v9.0 Improvements
-----------------
- Z-fighting fix: depth sort uses weighted centroid + deterministic face-index
  tiebreak (1e-7 epsilon) so coplanar faces on bantha/quad models no longer flicker
- Interactive LOD fallback: textured mode automatically drops to fast flat-shading
  during orbit/pan drag for smooth 60 fps response on any model
- Fast render tick: _RENDER_MS_INTERACTIVE=16ms during drag (vs 33ms idle)
- _render_fast flag propagated from drag handlers through schedule loop
- Reduced interactive tri cap: 20k (was 25k) for better drag responsiveness
- Bone placement: fully uses _node_world_transform cache – bones stay aligned
  with mesh during both bind pose and animation playback
- _release_pan now correctly resets is_interactive=False on MMB/RMB release

Features
--------
- Full UV-mapped textured rendering (proper per-pixel UV interpolation)
- KotOR-accurate Phong lighting with per-vertex normals (diffuse + specular + ambient)
- Self-illumination color support (glowing parts)
- Alpha/transparency channel support
- Specular map (cm_specmap) support
- DXT1/DXT5 decompressor for TPC textures
- Auto-detects KotOR TPC data embedded in .tga files
- Flat-shaded filled triangles with painter-sort depth (fallback)
- Wireframe overlay toggle
- Bone / skeleton overlay
- Grid floor
- Arc-ball camera (Maya-style: LMB=orbit, MMB/RMB=pan, Scroll=zoom)
- "Frame All" button + auto-frame on model load
- Axes gizmo in corner
- UV Viewer popup window (separate minimizable window)
- High-resolution texture sampling (full-res or 512x512 cache)
"""

import math, os, logging, struct, threading, time as _time_mod
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Tuple
try:
    from ..core.model_data import (KotorModel, ModelNode, NodeFlags, _quat_rotate, _quat_conjugate,
                                   KOTOR_BASE_SKELETONS)
    from ..core.animation_engine import DanglySimulator
    from ..core.walkmesh_renderer import WalkmeshOverlay, WalkmeshLoader, build_draw_list
except ImportError:
    from core.model_data import (  # type: ignore[no-redef]  # tests add src/ to sys.path
        KotorModel, ModelNode, NodeFlags, _quat_rotate, _quat_conjugate,
        KOTOR_BASE_SKELETONS
    )
    from core.animation_engine import DanglySimulator  # type: ignore[no-redef]
    try:
        from core.walkmesh_renderer import WalkmeshOverlay, WalkmeshLoader, build_draw_list
    except ImportError:
        WalkmeshOverlay = None  # type: ignore
        WalkmeshLoader  = None  # type: ignore
        build_draw_list = None  # type: ignore

log = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    _PIL = True
except ImportError:
    _PIL = False
    log.warning("Pillow not found – viewport unavailable")

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False

# ── Acceleration layer (accel.py + tex_atlas.py) ─────────────────────────────
# Provides Numba JIT / NumPy barycentric rasterizers that are 17–40× faster
# than the PIL AFFINE path and vectorised projection / frustum-cull utilities.
# The import is optional – if missing the PIL path is used unchanged.
try:
    from .accel import (
        ACCEL_TIER as _ACCEL_TIER,
        warmup_jit as _warmup_jit,
        project_vertices_np as _accel_proj_verts,
        frustum_cull_np as _accel_frustum_cull,
        depth_sort_np as _accel_depth_sort,
        sentinel_filter_np as _accel_sentinel_filter,
        rasterize_frame as _accel_rasterize_frame,
        flat_shade_frame as _accel_flat_shade_frame,
        shade_colors_np as _accel_shade_colors,
    )
    from .tex_atlas import TexArrayCache as _TexArrayCache
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
    def _accel_sentinel_filter(*a, **kw): return None
    def _accel_rasterize_frame(*a, **kw): pass
    def _accel_flat_shade_frame(*a, **kw): pass
    def _accel_shade_colors(*a, **kw): return None
    class _TexArrayCache:  # type: ignore[no-redef]
        def __init__(self, **kw): pass
        def get(self, img): return None
        def clear(self): pass


# ─────────────────────────────────────────────────────────────────────
#  Math helpers
# ─────────────────────────────────────────────────────────────────────

def _normalize(v):
    l = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])
    return (v[0]/l, v[1]/l, v[2]/l) if l > 1e-9 else (0.0, 1.0, 0.0)


def _clean_tex_name(name: str) -> str:
    """
    Sanitize a texture name that may have come from a fixed-width binary field.
    Stops at the first non-printable / non-ASCII character and strips whitespace.
    """
    if not name:
        return ''
    out = []
    for ch in name:
        if 32 <= ord(ch) <= 126:
            out.append(ch)
        else:
            break
    return ''.join(out).strip()

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ── UV sentinel threshold ────────────────────────────────────────────────────
# KotOR skin meshes embed seam-split duplicate vertices whose UV coords are
# intentionally set to a large placeholder (e.g. (-22, 127) in n_darthrevan's
# torso).  Any triangle that references one of these vertices cannot be textured
# v6.0 FIX: UV sentinel removed.  KotOR module textures intentionally use
# tiled UVs well beyond the 0-1 range (walls, floors, terrain).  The software
# rasterizer already uses frac() (u % 1.0) for GL_REPEAT wrapping, which
# handles any UV magnitude correctly.  Filtering by magnitude was the root
# cause of missing/stretched module textures.
#
# Previously _UV_SENTINEL = 100.0 caused triangles with |UV| > 100 to be
# silently skipped, and a fragile workaround raised the limit to 1e6 for
# module models.  Both are now removed.
#
# Only NaN/Inf values (genuinely corrupt MDX data) are filtered.  The
# threshold is set to a value that no legitimate UV will ever exceed,
# while still catching corrupt floats.
# Cross-ref: KotOR.js TextureLoader.ts -- default is RepeatWrapping, no UV
# filtering.  KotorBlender scene/material.py -- GL_REPEAT default.
_UV_SENTINEL = 1e18  # effectively disabled; only catches NaN/Inf

# ── Inner-geometry node name substrings ─────────────────────────────────────
# KotOR head models contain eye, eyelid, teeth, tongue, gum, and jaw meshes
# that sit geometrically INSIDE the face mesh.  With a painter's-algorithm
# (centroid-depth) sort these would sometimes be drawn before the opaque face
# mesh and then overwritten by it.  We promote them to render tier 1 (drawn
# after all tier-0 opaque geometry) so that the face mesh's eye-socket and
# mouth-gap openings correctly expose the underlying inner geometry.
#
# Criteria for promotion:
#   • Non-skin node (skin nodes are primary visible geometry — never promoted)
#   • Node name contains any of the substrings below (case-insensitive)
#   • transparency_hint == 0  (already-transparent nodes are already tier 1)
#
# Covers standard K1/K2 PC head naming (eyeRA, eyeLA, eyeRlid, eyeLlid,
# teethU, teethL, teethUa, teethLa, tongue) and NPC face-node naming
# (f_rlweye_g, f_llweye_g: NPC eyeball nodes that end in _g but are REAL
# renderable geometry — they must NOT be excluded by _is_deformation_helper).
# Also includes darthband_h / general NPC head model substrings for eyeball,
# gumskin, tonguemesh, eyelid_mesh, jawskin which appear in KotOR NPC heads.
_INNER_GEO_SUBSTRINGS: tuple = (
    'eye', 'lid', 'teeth', 'tooth', 'gum', 'jaw',
    'tongue', 'teethu', 'teethl',
    'eyeball', 'cornea', 'iris', 'pupil',   # explicit eyeball naming
    'gumskin', 'tonguemesh', 'jawskin',      # NPC sub-mesh names
    'eyelid', 'teetha', 'teethb',            # additional NPC variant names
)

# Head/face node substrings — these nodes render the outer face surface and
# must be treated as two-sided so that inner geometry (eyes, teeth visible
# through the mouth gap / eye socket) does not show reversed winding.
_FACE_MESH_SUBSTRINGS: tuple = (
    'face', 'head', 'skull', 'fhead', 'fchead',
)

def _lerp(a, b, t):
    return a + (b - a) * t


# ── Module-level UV seam-fix helpers ────────────────────────────────────────
# Defined here (module scope) so _paste_textured_triangle does NOT re-create
# these closure objects on EVERY triangle call.  Moving them to module level
# saves ~2–3 µs per triangle (Python closure allocation + MAKE_FUNCTION opcode)
# which adds up to ~16 ms per 8000-triangle textured frame.
def _uwrap_global(base: float, other: float) -> float:
    """Pull 'other' to within ±0.5 of 'base' (seam-crossing unwrap)."""
    diff = other - base
    while diff >  0.5: other -= 1.0; diff -= 1.0
    while diff < -0.5: other += 1.0; diff += 1.0
    return other

def _edge_has_seam_global(a: float, b: float) -> bool:
    """True if _uwrap shortens the a→b distance by > 0.01."""
    raw_dist  = abs(b - a)
    b_wrapped = _uwrap_global(a, b)
    wrap_dist = abs(b_wrapped - a)
    return wrap_dist < raw_dist - 0.01

def _vflip_nontiled(v: float, th: float) -> float:
    """Standard non-tiled V-flip: (1.0 - v) * th."""
    return (1.0 - v) * th

def _vflip_tiled(v: float, tile_v: float, src_h: float) -> float:
    """Tiled V-flip: (tile_v - v) * src_h."""
    return (tile_v - v) * src_h


# ─────────────────────────────────────────────────────────────────────
#  UE-inspired: Sortable float depth key
#  Derived from Unreal Engine 5 MeshDrawCommands.cpp
#  `BitInvertIfNegativeFloat(uint32 f)`:
#    mask = -int32(f >> 31) | 0x80000000
#    return f ^ mask
#  This produces an unsigned integer that sorts in the same order as the
#  original float, including negative values, with a single XOR. Sorting
#  these uint32 keys with standard integer comparison gives back-to-front
#  order for depth values when sorted ascending (farther = larger key).
# ─────────────────────────────────────────────────────────────────────
import struct as _struct

def _float_to_sort_key(f: float) -> int:
    """
    Convert a float depth value to a sortable unsigned integer key.
    Implements UE5's BitInvertIfNegativeFloat trick so that:
      - Positive floats map to [0x80000000, 0xFFFFFFFF] (larger = farther)
      - Negative floats map to [0x00000000, 0x7FFFFFFF] (smaller = closer)
    Sorting keys DESCENDING gives back-to-front draw order (painter's algorithm).

    This avoids floating-point comparison instability between very close depths
    and is numerically more robust than raw float comparison for depth-sorted
    transparent geometry.
    """
    bits = _struct.unpack('<I', _struct.pack('<f', float(f)))[0]
    # If sign bit set (negative float): invert all bits.
    # If sign bit clear (positive float): invert only sign bit.
    # Result: sortable unsigned integer, ascending = front-to-back.
    mask = (-(bits >> 31) & 0xFFFFFFFF) | 0x80000000
    return bits ^ mask


def _compute_screen_size_ratio(
    bounds_min: tuple,
    bounds_max: tuple,
    view_origin: tuple,
    fov_vertical_rad: float,
    viewport_height: int,
) -> float:
    """
    Compute a screen-size fraction for the given world-space bounding box.
    Inspired by UE5's ComputeBoundsScreenSize (SceneView.cpp).

    Returns the fraction of the viewport height covered by the bounding
    sphere of the object.  Used for screen-size driven LOD decisions:
      < 0.02  → very small on screen (could skip or use low-detail)
      > 0.30  → large (full detail worth rendering)

    Formula:
      screen_radius = sphere_radius / (distance * tan(HalfVFOV))
      ratio = screen_radius * viewport_height
    """
    if viewport_height <= 0 or fov_vertical_rad <= 0:
        return 1.0
    cx = (bounds_min[0] + bounds_max[0]) * 0.5
    cy = (bounds_min[1] + bounds_max[1]) * 0.5
    cz = (bounds_min[2] + bounds_max[2]) * 0.5
    rx = bounds_max[0] - cx
    ry = bounds_max[1] - cy
    rz = bounds_max[2] - cz
    sphere_r = math.sqrt(rx*rx + ry*ry + rz*rz)
    dx = cx - view_origin[0]
    dy = cy - view_origin[1]
    dz = cz - view_origin[2]
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    if dist < 1e-6:
        return 1.0
    tan_half_fov = math.tan(fov_vertical_rad * 0.5)
    if tan_half_fov < 1e-9:
        return 1.0
    # projected sphere radius in normalized device coordinates
    screen_radius_ndc = sphere_r / (dist * tan_half_fov)
    return screen_radius_ndc  # multiply by viewport_height for pixel radius


# ─────────────────────────────────────────────────────────────────────
#  TPC detection & loading helpers
# ─────────────────────────────────────────────────────────────────────

def _is_tpc_data(data: bytes) -> bool:
    """
    Detect KotOR TPC format from raw bytes.
    Returns True if the data looks like a TPC file (regardless of extension).

    KotOR TPC header layout (128 bytes, BioWare format):
      [0-3]   uint32  data_sz    – byte size of the first mip level's pixel data
                                   NOTE: some TPC files have data_sz=0 (mip chain)
      [4-7]   float   alpha_test_threshold  (0.0..1.0 range)
      [8-9]   uint16  width
      [10-11] uint16  height
      [12]    uint8   encoding   – 0=auto/infer, 1=grey, 2=RGB or DXT1,
                                   4=RGBA or DXT5, 10=DXT1, 12=DXT1, 13=DXT3, 14=DXT5
      [13]    uint8   mip_count
      [14-127] reserved (all zeros in authentic TPC files)

    NOTE: The Aurora engine encoding field is at offset 12, NOT offset 14.
    This is confirmed by xoreos, KotOR Modding Wiki, and tpc_render_utils.py.
    Previous versions incorrectly placed encoding at offset 14 (treating offset 12
    as a 'layers' field like some other formats).  Fixed to match xoreos/KotorBlender.

    CUBEMAP NOTE: Cubemap TPC files store 6 square faces stacked vertically
    so height = 6 * width.  A 1024×6144 cubemap must be accepted even though
    6144 > 4096.  Detection mirrors KotorBlender: cubemap = (h // w == 6).
    """
    if len(data) < 128:
        return False
    data_sz = struct.unpack_from('<I', data, 0)[0]
    w       = struct.unpack_from('<H', data, 8)[0]
    h       = struct.unpack_from('<H', data, 10)[0]
    enc     = data[12]   # Encoding at offset 12 (Aurora engine, confirmed xoreos/KotorBlender)
    mips    = data[13]   # mip_count at offset 13

    # ── PyKotor-compatible zero-byte test (primary fast-path) ────────────
    # PyKotor detect_tpc() checks that bytes[15..100] are ALL zero.
    # TPC header has a 128-byte reserved section; TGA files have non-zero
    # data at those positions (image descriptor, color map spec, etc.).
    # This test catches TPC files even with unusual encoding values (0, 3).
    pykotor_tpc = all(b == 0 for b in data[15:100])
    if pykotor_tpc:
        # Confirmed TPC by PyKotor method; validate dimensions
        if 0 < w <= 8192 and 0 < h <= 8192 * 6:
            return True
        # Tiny files (thumbnails) may have non-power-of-2 small dims — accept
        if w > 0 and h > 0:
            return True
    # ── Primary encoding-based detection (our method) ───────────────────
    # KotOR encoding values: 0=auto(layers), 1=grey, 2=RGB, 4=RGBA, 10=DXT1,
    # 12=DXT1_alpha, 13=DXT3, 14=DXT5
    TPC_ENCS = (0, 1, 2, 4, 10, 12, 13, 14)
    if w == 0 or h == 0 or w > 4096:
        return False
    # Allow cubemap TPC files: height = 6 * width (6 square faces stacked).
    _cubemap_h = (h == 6 * w)
    if not _cubemap_h and h > 4096:
        return False
    if enc not in TPC_ENCS:
        return False
    bx = max(1, (w + 3) // 4)
    by = max(1, (h + 3) // 4)
    # Expected data size for first mip level
    valid = {
        bx * by * 8,          # DXT1 / enc=10
        bx * by * 16,         # DXT3 / DXT5
        w * h,                # greyscale (enc=1)
        w * h * 3,            # RGB (enc=2)
        w * h * 4,            # RGBA (enc=4)
    }
    if data_sz in valid:
        return True
    # data_sz=0 is valid for TPC files stored with full mip chain sizes (not first-mip)
    if data_sz == 0 and enc in TPC_ENCS and mips > 0:
        min_pixel = 1 if enc == 1 else (3 if enc == 2 else 4)
        if len(data) >= 128 + min_pixel:
            return True
    # Loose match: data_sz fits within file after 128-byte header
    if data_sz > 0 and 128 + data_sz <= len(data) + 1024:
        if enc in TPC_ENCS and len(data) > 256:
            return True
    return False


def _is_tpc_file(path: str) -> bool:
    """Check if file on disk is TPC by reading its header (128 bytes for full validation)."""
    try:
        with open(path, 'rb') as f:
            header = f.read(128)   # read full TPC header (was 16 – too short for loose check)
        return _is_tpc_data(header)
    except Exception:
        return False


def _decompress_dxt1_bytes(data: bytes, w: int, h: int) -> bytearray:
    """Software DXT1 block decompressor → RGBA bytearray.

    DXT1 has two modes based on the relative ordering of the two endpoint colors:
      c0r > c1r  →  4-color opaque mode  (index 0-3 all opaque, index 3 = interpolated)
      c0r <= c1r →  3-color + transparent mode  (index 3 → transparent black, alpha=0)

    Reference: S3TC / DXT1 specification, Microsoft DirectX documentation.
    """
    result = bytearray(w * h * 4)
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    for by in range(bh):
        for bx in range(bw):
            pos = (by * bw + bx) * 8
            if pos + 8 > len(data):
                continue
            c0r = struct.unpack_from('<H', data, pos)[0]
            c1r = struct.unpack_from('<H', data, pos + 2)[0]
            lk  = struct.unpack_from('<I', data, pos + 4)[0]
            def e(c): return (((c>>11)&31)*255//31, ((c>>5)&63)*255//63, (c&31)*255//31)
            c0, c1 = e(c0r), e(c1r)
            # punchthrough_mode: when c0r <= c1r, index=3 is transparent
            punchthrough = (c0r <= c1r)
            if not punchthrough:
                cols  = [c0, c1,
                         tuple((2*c0[i]+c1[i])//3 for i in range(3)),
                         tuple((c0[i]+2*c1[i])//3 for i in range(3))]
                alphas = [255, 255, 255, 255]
            else:
                cols  = [c0, c1,
                         tuple((c0[i]+c1[i])//2 for i in range(3)),
                         (0, 0, 0)]
                alphas = [255, 255, 255, 0]   # index 3 → transparent
            for py2 in range(4):
                for px2 in range(4):
                    idx = (lk >> (2*(py2*4+px2))) & 3
                    col = cols[idx]
                    gx, gy = bx*4+px2, by*4+py2
                    if gx < w and gy < h:
                        o = (gy*w+gx)*4
                        result[o] = col[0]; result[o+1] = col[1]
                        result[o+2] = col[2]; result[o+3] = alphas[idx]
    return result


def _decompress_dxt5_bytes(data: bytes, w: int, h: int) -> bytearray:
    """Software DXT5 block decompressor → RGBA bytearray."""
    result = bytearray(w * h * 4)
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    for by in range(bh):
        for bx in range(bw):
            pos = (by * bw + bx) * 16
            if pos + 16 > len(data):
                continue
            a0, a1 = data[pos], data[pos+1]
            abits = struct.unpack_from('<Q', data, pos+1)[0] >> 8
            c0r = struct.unpack_from('<H', data, pos+8)[0]
            c1r = struct.unpack_from('<H', data, pos+10)[0]
            lk  = struct.unpack_from('<I', data, pos+12)[0]
            def e(c): return (((c>>11)&31)*255//31, ((c>>5)&63)*255//63, (c&31)*255//31)
            c0, c1 = e(c0r), e(c1r)
            cols = [c0, c1,
                    tuple((2*c0[i]+c1[i])//3 for i in range(3)),
                    tuple((c0[i]+2*c1[i])//3 for i in range(3))]
            if a0 > a1:
                als = [a0, a1,
                       (6*a0+a1)//7, (5*a0+2*a1)//7, (4*a0+3*a1)//7,
                       (3*a0+4*a1)//7, (2*a0+5*a1)//7, (a0+6*a1)//7]
            else:
                als = [a0, a1,
                       (4*a0+a1)//5, (3*a0+2*a1)//5, (2*a0+3*a1)//5,
                       (a0+4*a1)//5, 0, 255]
            for py2 in range(4):
                for px2 in range(4):
                    col   = cols[(lk >> (2*(py2*4+px2))) & 3]
                    alpha = als[(abits >> (3*(py2*4+px2))) & 7]
                    gx, gy = bx*4+px2, by*4+py2
                    if gx < w and gy < h:
                        o = (gy*w+gx)*4
                        result[o] = col[0]; result[o+1] = col[1]
                        result[o+2] = col[2]; result[o+3] = alpha
    return result


def _load_tpc_bytes(data: bytes) -> Optional['Image.Image']:
    """Load a KotOR TPC image from raw bytes using pykotor's battle-tested reader.

    pykotor.read_tpc handles DXT1/DXT3/DXT5 decompression, greyscale, RGB/RGBA,
    cubemap slicing, and TXI extraction correctly across K1 and K2 content.
    Falls back to the legacy software decompressor if pykotor is unavailable.

    Returns a PIL RGBA Image (bottom-up orientation, ready for the renderer's
    V-flip formula) or None on failure.

    FIX-TXI-ATTR: The returned image always has '_txi_str' set (may be empty
    string if no TXI is present).  This allows _apply_txi_from_textures_to_model()
    in gpu_renderer.py to extract punchthrough/blending/envmap metadata from TPC
    files and apply it to model nodes at render time.  Without this attribute the
    TXI cache in that function stays empty and blending modes are never updated
    (causing bantha hair/fur to render as solid blocks instead of cut-out geometry).
    """
    if not _PIL or not data or len(data) < 128:
        return None
    try:
        from pykotor.resource.formats.tpc.tpc_auto import read_tpc as _pk_read_tpc
        from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
        tpc = _pk_read_tpc(data)   # pykotor accepts raw bytes directly
        # FIX-TXI-ATTR: Extract TXI string before converting (tpc.txi is set after load)
        _txi = ''
        try:
            _txi = (tpc.txi or '').strip() if isinstance(getattr(tpc, 'txi', None), str) else ''
        except Exception:
            pass
        # Record the original format BEFORE conversion (used for orientation detection below)
        _orig_format = tpc.format()
        _is_compressed = _orig_format in (
            TPCTextureFormat.DXT1, TPCTextureFormat.DXT3, TPCTextureFormat.DXT5
        ) if hasattr(TPCTextureFormat, 'DXT1') else (data[:4] != b'\x00\x00\x00\x00' and data[12] in (2, 4) and struct.unpack_from('<I', data, 0)[0] != 0)
        tpc.convert(TPCTextureFormat.RGBA)
        mip = tpc.get(0, 0)          # first layer, first (largest) mipmap
        img = mip.to_pil_image()
        if img is None:
            raise ValueError("pykotor returned None image")
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        # FIX-VFLIP v2 (UV-convention fix):
        # KotOR MDL UV coordinates use V=0=TOP convention (same as Direct3D / PNG),
        # NOT the OpenGL V=0=BOTTOM convention that our CPU rasterizer assumes.
        # The CPU rasterizer applies V-flip (1-v)*h at render time, which converts
        # from OpenGL-space (V=0=bottom) to PIL row space (row 0=top).
        # For this render-time flip to produce correct results, the stored image
        # must be in BOTTOM-UP (OpenGL) orientation so that:
        #   V=0 (near-top in KotOR MDL) -> render flip -> PIL row near bottom -> correct texture bottom.
        #
        # PyKotor returns:
        #   - Uncompressed (RGBA/RGB/Grey): BOTTOM-UP (OpenGL convention). No extra flip needed.
        #   - DXT1/DXT3/DXT5: TOP-DOWN (DirectX DXT block order).
        #     Must flip to bottom-up so the renderer's (1-v) formula works correctly.
        #
        # Without this fix: DXT tail tip (V=0.015) -> (1-0.015)*H=504 -> pink mouth area (WRONG)
        # With this fix:    DXT flip -> V=0.015 -> (1-0.015)*H=504 -> original row H-504 -> dark brown (CORRECT)
        if _is_compressed:
            # DXT textures are top-down: flip to bottom-up for the renderer's V-flip
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            # Uncompressed textures are already bottom-up: no extra flip needed
            pass
        # FIX-TXI-ATTR: Attach TXI string so GPU renderer can apply blending modes
        img._txi_str = _txi  # type: ignore[attr-defined]
        # Also store raw data so legacy _extract_txi path works as fallback
        img._tpc_raw = data   # type: ignore[attr-defined]
        # FIX-ALPHATEST: Attach alpha_test from TPC header for punchthrough threshold
        try:
            _at = struct.unpack_from('<f', data, 4)[0]
            if 0.0 < _at <= 1.0:
                img._txi_alpha_test = _at  # type: ignore[attr-defined]
        except Exception:
            pass
        return img
    except ImportError:
        pass  # pykotor not installed — fall through to legacy decoder
    except Exception as e:
        log.debug(f"pykotor TPC load failed ({e}), trying legacy decoder")
    # ── Legacy software decoder (fallback when pykotor is unavailable) ────────
    # _load_tpc_bytes_legacy already attaches _txi_str, _tpc_raw, _txi_alpha_test.
    img = _load_tpc_bytes_legacy(data)
    return img


def _extract_txi_from_tpc(data: bytes) -> str:
    """Extract TXI metadata string from TPC binary data.

    Uses pykotor.read_tpc() which correctly parses the TXI trailer embedded
    after all mipmap pixel data.  Falls back to manual extraction if pykotor
    is unavailable.

    Returns the TXI string (may be empty if none present).
    """
    if not data or len(data) < 128:
        return ''
    try:
        from pykotor.resource.formats.tpc.tpc_auto import read_tpc as _pk_read_tpc
        tpc = _pk_read_tpc(data)   # pykotor accepts raw bytes directly
        txi = tpc.txi or ''
        return txi.strip() if isinstance(txi, str) else ''
    except ImportError:
        pass
    except Exception as e:
        log.debug(f"pykotor TXI extraction error: {e}")
    # Fallback: manual TXI extraction (legacy method)
    return _extract_txi_from_tpc_legacy(data)


def _load_tpc_bytes_legacy(data: bytes) -> Optional['Image.Image']:
    """Load KotOR TPC from raw bytes (legacy pure-Python decoder).

    Wraps _load_tpc_bytes_legacy_inner and attaches TXI metadata attributes
    (_txi_str, _tpc_raw, _txi_alpha_test) to the returned PIL Image so that
    callers can access blending/alpha-mode without re-fetching the raw bytes.
    Returns None if decoding fails.
    """
    img = _load_tpc_bytes_legacy_inner(data)
    if img is not None:
        # Attach _tpc_raw (raw bytes for fallback TXI / header reading)
        img._tpc_raw = data  # type: ignore[attr-defined]
        # Attach _txi_str — extracted from embedded TPC TXI trailer
        # NOTE: _extract_txi_from_tpc_legacy is defined after this function;
        # Python resolves it at call-time so forward reference is fine.
        try:
            img._txi_str = _extract_txi_from_tpc_legacy(data)  # type: ignore[attr-defined]
        except Exception:
            img._txi_str = ''  # type: ignore[attr-defined]
        # Attach _txi_alpha_test from TPC header bytes [4-7]
        try:
            at = struct.unpack_from('<f', data, 4)[0]
            if 0.0 < at <= 1.0:
                img._txi_alpha_test = at  # type: ignore[attr-defined]
        except Exception:
            pass
    return img


def _load_tpc_bytes_legacy_inner(data: bytes) -> Optional['Image.Image']:
    # Legacy software TPC decoder — used as fallback when pykotor unavailable.
    """
    Load a KotOR TPC image from raw bytes. Returns PIL RGBA Image or None.
    (Called exclusively by _load_tpc_bytes_legacy which attaches TXI attrs.)

    Rewritten to exactly mirror PyKotor's TPCBinaryReader logic so the two
    paths always produce identical output regardless of which is invoked.

    KotOR TPC header layout (BioWare / Aurora engine format):
      [0-3]   uint32  data_sz   – first-mip pixel data size
                                  0 = uncompressed  (PyKotor: compressed = data_sz != 0)
      [4-7]   float   alpha_test
      [8-9]   uint16  width
      [10-11] uint16  height
      [12]    uint8   pixel_type – 1=Grey, 2=RGB/DXT1, 4=RGBA/DXT5, 12=BGRA
      [13]    uint8   mip_count
      [14-127] reserved zeros

    FORMAT MAP (mirrors PyKotor TPCBinaryReader + stock KotOR BIF handling):
      data_sz != 0 → always compressed (PyKotor convention)
      data_sz == 0, pixel_type=2: compressed if pixel_data < sz3 (DXT1), else uncompressed RGB
      data_sz == 0, pixel_type=4: compressed if pixel_data < sz4 (DXT5), else uncompressed RGBA
      data_sz == 0, pixel_type=1  → Greyscale  → as-is (already bottom-up, OpenGL)
      data_sz == 0, pixel_type=12 → BGRA       → swap B/R → as-is

      (compressed=True,  pixel_type=2)  → DXT1   → decompress → flip (top-down→bottom-up)
      (compressed=True,  pixel_type=4)  → DXT5   → decompress → flip
      (compressed=False, pixel_type=1)  → Grey   → as-is
      (compressed=False, pixel_type=2)  → RGB    → as-is
      (compressed=False, pixel_type=4)  → RGBA   → as-is
      (compressed=False, pixel_type=12) → BGRA   → swap B/R → as-is

    Explicit DXT encodings (10=DXT1, 13=DXT3, 14=DXT5) are always compressed
    (top-down) and are always flipped to bottom-up.

    ORIENTATION RULE (matches _load_tpc_bytes / PyKotor pipeline):
    - DXT-compressed output is TOP-DOWN (DirectX convention).  Must flip to
      BOTTOM-UP so the renderer's V-flip formula (tv = (1-v)*h) is correct.
    - Uncompressed output is already BOTTOM-UP (OpenGL convention).  No flip.

    STOCK KotOR BIF NOTE:
    - KotOR BIF archives store DXT-compressed textures with data_sz=0.
    - PyKotor's read_tpc() raises OSError on these files (seeks past EOF).
    - This legacy decoder handles them by comparing pixel_data length against
      uncompressed size: if too small → DXT-compressed.

    CUBEMAP SUPPORT:
    - height == 6 * width → cubemap; return first face only.
    """
    if not _PIL or len(data) < 128:
        return None
    data_sz    = struct.unpack_from('<I', data, 0)[0]
    width      = struct.unpack_from('<H', data, 8)[0]
    height     = struct.unpack_from('<H', data, 10)[0]
    pixel_type = data[12]
    if width == 0 or height == 0:
        return None

    # ── Cubemap detection ─────────────────────────────────────────────────────
    if height > 0 and width > 0 and height // width == 6 and height % width == 0:
        log.debug(f"TPC: cubemap detected {width}x{height} → rendering face 0 only")
        height = width

    pixel_data = data[128:]
    bx = max(1, (width  + 3) // 4)
    by = max(1, (height + 3) // 4)
    dxt1_sz = bx * by * 8
    dxt5_sz = bx * by * 16
    sz1 = width * height
    sz3 = width * height * 3
    sz4 = width * height * 4

    # ── Compression detection ─────────────────────────────────────────────────
    # PyKotor's rule (compressed = data_sz != 0) only covers files written by
    # PyKotor.  Stock KotOR BIF textures store DXT-compressed data with data_sz=0
    # and rely on pixel_type (2=DXT1, 4=DXT5) to signal compression.
    #
    # Strategy:
    #   data_sz != 0 → always compressed (PyKotor convention)
    #   data_sz == 0 + pixel_type in (2, 4):
    #       Use actual pixel_data length to discriminate:
    #       - if len(pixel_data) < sz3 (for enc=2) or < sz4 (for enc=4), the
    #         data is too small for uncompressed → must be DXT-compressed.
    #       - if len(pixel_data) >= uncompressed size → uncompressed.
    #   data_sz == 0 + pixel_type in (1, 12) → always uncompressed.
    if data_sz != 0:
        compressed = True
    elif pixel_type == 2:
        # enc=2: DXT1 block data is smaller than uncompressed RGB (sz3)
        compressed = (len(pixel_data) < sz3)
    elif pixel_type == 4:
        # enc=4: DXT5 block data is smaller than uncompressed RGBA (sz4)
        compressed = (len(pixel_data) < sz4)
    else:
        # enc=1 (Grey), enc=12 (BGRA), enc=10/13/14 handled below → uncompressed
        compressed = False

    def _flip(img):
        """Flip vertically: DXT top-down → bottom-up for the renderer's (1-v)*h."""
        try:
            return img.transpose(Image.FLIP_TOP_BOTTOM)
        except Exception:
            return img

    try:
        # ── Explicit DXT encodings (always compressed, always top-down → flip) ──
        # enc=10: explicit DXT1
        # enc=12 with data_sz≠0: Aurora DXT1 variant
        # enc=13: DXT3 (uses DXT5-sized blocks)
        # enc=14: DXT5
        if pixel_type == 10 or (pixel_type == 12 and data_sz != 0):
            if len(pixel_data) >= dxt1_sz:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             bytes(_decompress_dxt1_bytes(pixel_data, width, height))))
        if pixel_type == 13:
            if len(pixel_data) >= dxt5_sz:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             bytes(_decompress_dxt5_bytes(pixel_data, width, height))))
        if pixel_type == 14:
            if len(pixel_data) >= dxt5_sz:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             bytes(_decompress_dxt5_bytes(pixel_data, width, height))))

        # ── Main format dispatch: (compressed, pixel_type) ───────────────────
        if compressed:
            # DXT format (top-down storage → flip to bottom-up for renderer)
            if pixel_type == 2:
                # DXT1
                if len(pixel_data) >= dxt1_sz:
                    return _flip(Image.frombytes('RGBA', (width, height),
                                                 bytes(_decompress_dxt1_bytes(pixel_data, width, height))))
            elif pixel_type == 4:
                # DXT5
                if len(pixel_data) >= dxt5_sz:
                    return _flip(Image.frombytes('RGBA', (width, height),
                                                 bytes(_decompress_dxt5_bytes(pixel_data, width, height))))
            # Fallback: try DXT5 first (larger → more likely), then DXT1
            if len(pixel_data) >= dxt5_sz:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             bytes(_decompress_dxt5_bytes(pixel_data, width, height))))
            if len(pixel_data) >= dxt1_sz:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             bytes(_decompress_dxt1_bytes(pixel_data, width, height))))
        else:
            # Uncompressed (already bottom-up, OpenGL convention — NO flip)
            if pixel_type == 1:
                # Greyscale
                if len(pixel_data) >= sz1:
                    return Image.frombytes('L', (width, height),
                                           pixel_data[:sz1]).convert('RGBA')
            elif pixel_type == 2:
                # RGB (uncompressed, data_sz=0, pixel_data >= sz3)
                if len(pixel_data) >= sz3:
                    return Image.frombytes('RGB', (width, height),
                                           pixel_data[:sz3]).convert('RGBA')
            elif pixel_type == 4:
                # RGBA (uncompressed, data_sz=0, pixel_data >= sz4)
                if len(pixel_data) >= sz4:
                    return Image.frombytes('RGBA', (width, height), pixel_data[:sz4])
            elif pixel_type == 12:
                # BGRA → swap B and R channels, no flip
                if len(pixel_data) >= sz4:
                    try:
                        bgra_img = Image.frombytes('RGBA', (width, height), pixel_data[:sz4])
                        r, g, b, a = bgra_img.split()
                        return Image.merge('RGBA', (b, g, r, a))
                    except Exception as e:
                        log.debug(f"TPC BGRA swap error: {e}")
            # Uncompressed fallback: try RGBA, then RGB, then Grey
            if len(pixel_data) >= sz4:
                return Image.frombytes('RGBA', (width, height), pixel_data[:sz4])
            if len(pixel_data) >= sz3:
                return Image.frombytes('RGB', (width, height),
                                       pixel_data[:sz3]).convert('RGBA')
            if len(pixel_data) >= sz1:
                return Image.frombytes('L', (width, height),
                                       pixel_data[:sz1]).convert('RGBA')

        log.debug(f"TPC legacy: unhandled format pixel_type={pixel_type} "
                  f"compressed={compressed} {width}x{height} pixdata={len(pixel_data)}")
        return None
    except Exception as e:
        log.debug(f"TPC legacy decode error pixel_type={pixel_type} {width}x{height}: {e}")
        return None


def _extract_txi_from_tpc_legacy(data: bytes) -> str:
    # Legacy manual TXI extraction — fallback when pykotor unavailable.
    """
    Extract TXI metadata string from TPC binary data (PyKotor/KotorBlender-compatible).

    TPC files optionally embed TXI (texture instructions) as ASCII/UTF-8 text
    immediately after the last mipmap's pixel data, up to the end of the file.
    TXI controls procedural texture effects: envmaptexture, bumpmap, cube maps, etc.

    PyKotor reads: tpc.txi = reader.read_string(file_size - reader.position())
    KotorBlender reads: image.txi_lines = remaining_bytes.decode('utf-8').splitlines()

    Returns the TXI string (may be empty string if none present).

    FIX-TXI-OFFSET: Stock KotOR BIF textures use data_sz=0 with enc=2 (DXT1) or enc=4
    (DXT5).  The original code used `_is_compressed = (data_sz != 0)` which is the
    PyKotor rule — but PyKotor's read_tpc *fails* on these files (it reads enc=2/data_sz=0
    as uncompressed RGB, computing the wrong data size).  For TXI extraction we must
    independently infer whether the pixel data is DXT-compressed by comparing the pixel
    data length against the uncompressed size: if the total file is too small to hold
    uncompressed data, the texture must be DXT-compressed.
    """
    if len(data) < 128:
        return ''
    try:
        data_sz     = struct.unpack_from('<I', data, 0)[0]
        width       = struct.unpack_from('<H', data, 8)[0]
        height      = struct.unpack_from('<H', data, 10)[0]
        pixel_type  = data[12]   # PyKotor: pixel_type at 0x0C; 1=grey,2=RGB,4=RGBA,12=BGRA
        mip_cnt     = max(1, data[13])  # mipmap count at 0x0D

        if width == 0 or height == 0:
            return ''

        # Cubemap: height = 6 * width
        if height > 0 and width > 0 and height // width == 6 and height % width == 0:
            height = width  # use first face only for size computation

        # Compute size of all mipmaps to find TXI start offset.
        bx = max(1, (width  + 3) // 4)
        by = max(1, (height + 3) // 4)
        dxt1_sz0 = bx * by * 8
        dxt5_sz0 = bx * by * 16
        sz1_0    = width * height          # greyscale
        sz3_0    = width * height * 3      # RGB
        sz4_0    = width * height * 4      # RGBA / BGRA

        pixel_data_len = len(data) - 128

        # FIX-TXI-OFFSET: Determine if this is a DXT-compressed texture.
        # PyKotor rule (data_sz != 0) is WRONG for stock KotOR BIF textures which
        # have enc=2 or enc=4 with data_sz=0 but DXT1/DXT5 pixel data.
        # Correct rule: if data_sz != 0 AND matches DXT size → definitely compressed;
        # if data_sz == 0 AND pixel_data_len < uncompressed size → must be compressed.
        if data_sz != 0:
            # Non-zero data_sz: use PyKotor's rule for the compressed flag
            _is_compressed = True
        else:
            # data_sz == 0: infer from actual pixel data size
            # If pixel_data_len is too small to hold uncompressed pixels,
            # it must be DXT-compressed (stock KotOR BIF format).
            _uncompressed_min = {1: sz1_0, 2: sz3_0, 4: sz4_0, 12: sz4_0}.get(pixel_type, sz4_0)
            _is_compressed = (pixel_data_len < _uncompressed_min)

        # Determine per-block or per-pixel size for mip chain calculation
        if _is_compressed:
            if data_sz != 0:
                # Use explicit data_sz if it matches a known DXT block size
                if data_sz == dxt1_sz0:
                    _bytes_per_block = 8
                elif data_sz == dxt5_sz0:
                    _bytes_per_block = 16
                else:
                    # Guess from pixel_type: enc=2 → DXT1 (8 bytes/block), enc=4 → DXT5 (16)
                    _bytes_per_block = 8 if pixel_type in (2,) else 16
                    # Fall back to data_sz as mip0 size
                    if 0 < data_sz <= pixel_data_len:
                        mip0_sz = data_sz
                        def mip_sz_fn(w, h):  # type: ignore[misc]
                            _bx = max(1, (w+3)//4); _by = max(1, (h+3)//4)
                            return max(_bytes_per_block, _bx * _by * _bytes_per_block)
                        total_pix = mip0_sz
                        mw, mh = max(1, width >> 1), max(1, height >> 1)
                        for _ in range(mip_cnt - 1):
                            total_pix += mip_sz_fn(mw, mh)
                            mw = max(1, mw >> 1); mh = max(1, mh >> 1)
                        txi_start = 128 + total_pix
                        if txi_start < len(data):
                            raw = data[txi_start:]
                            txi = raw.rstrip(b'\x00').decode('utf-8', errors='replace').strip()
                            if txi:
                                first_line = txi.split('\n')[0].strip()
                                first_word = first_line.split()[0] if first_line.split() else ''
                                all_printable = all(32 <= ord(c) <= 126 or c in '\r\n\t' for c in txi[:256])
                                if first_word.isascii() and first_word.isalpha() and all_printable:
                                    return txi
                        return ''
            else:
                # data_sz == 0, compressed: infer DXT block size from pixel_type
                # enc=2 → DXT1 (8 bytes/block), enc=4 → DXT5 (16 bytes/block)
                # Also check pixel data fits dxt5 vs dxt1
                if pixel_type in (2,) or pixel_data_len < dxt5_sz0:
                    _bytes_per_block = 8
                else:
                    _bytes_per_block = 16
            mip0_sz = bx * by * _bytes_per_block
            def mip_sz_fn(w, h):  # type: ignore[misc]
                return max(_bytes_per_block,
                           max(1, (w+3)//4) * max(1, (h+3)//4) * _bytes_per_block)
        else:
            bpp = {1: 1, 2: 3, 4: 4, 12: 4}.get(pixel_type, 4)
            mip0_sz = width * height * bpp
            def mip_sz_fn(w, h):  # type: ignore[misc]
                return max(1, w) * max(1, h) * bpp

        total_pix = mip0_sz
        mw, mh = max(1, width >> 1), max(1, height >> 1)
        for _ in range(mip_cnt - 1):
            total_pix += mip_sz_fn(mw, mh)
            mw = max(1, mw >> 1); mh = max(1, mh >> 1)

        txi_start = 128 + total_pix
        if txi_start < len(data):
            raw = data[txi_start:]
            # Strip null bytes and decode
            txi = raw.rstrip(b'\x00').decode('utf-8', errors='replace').strip()
            if txi:
                # Validate: TXI must start with a printable ASCII word (command name).
                # If the first char is non-printable or the first word contains
                # high-byte chars (binary pixel data leaking in), discard.
                first_line = txi.split('\n')[0].strip()
                first_word = first_line.split()[0] if first_line.split() else ''
                all_printable = all(
                    32 <= ord(c) <= 126 or c in '\r\n\t'
                    for c in txi[:256]
                )
                if first_word.isascii() and first_word.isalpha() and all_printable:
                    log.debug(f"TPC TXI ({len(txi)} chars): {txi[:80]!r}")
                    return txi
                else:
                    log.debug(f"TPC TXI rejected (binary/invalid): first_word={first_word!r}")
    except Exception as e:
        log.debug(f"TPC TXI extraction error: {e}")
    return ''


# ─────────────────────────────────────────────────────────────────────
#  TXI Metadata Parser
#  Parses KotOR TXI ASCII command-value pairs into a structured dict.
#  Reference: PyKotor txi_data.py, KotOR.js TXI.ts, NWN wiki TXI docs.
# ─────────────────────────────────────────────────────────────────────

def _parse_txi_string(txi: str) -> dict:
    """
    Parse a TXI metadata string into a dictionary of properties.

    TXI files are ASCII text files with command-value pairs:
        proceduretype cycle
        numx 4
        numy 4
        fps 10
        cube 1
        bumpmap some_texture
        bumpmapscaling 1.5
        blending additive
        envmaptexture cm_fog

    Returns a dict with these keys (with sensible defaults if absent):
        blending      : int   (0=none, 1=additive, 2=punchthrough)
        cube          : bool
        proceduretype : str   ('cycle', 'water', 'arturo', '')
        numx          : int   (flipbook columns)
        numy          : int   (flipbook rows)
        fps           : float (flipbook animation fps)
        envmaptexture : str
        bumpmaptexture: str
        bumpmapscaling: float
        rotate        : float (degrees)
        loop          : bool
        clamp_s       : bool  (True = GL_CLAMP_TO_EDGE in S/U axis)
        clamp_t       : bool  (True = GL_CLAMP_TO_EDGE in T/V axis)
        clamp         : bool  (True = clamp both S and T axes)
        decal         : bool
        mipmap        : int   (0=off, 1=on)
        filter        : bool
        downsamplemax : int
        downsamplemin : int
        xbox_downsample: int  (Xbox-specific downsampling override)
        compresstexture: bool (request driver-level texture compression)
        isbumpmap     : bool
        islightmap    : bool
        diffusebumpmap: str
        specbumpmap   : str
        distort       : bool
        distortangle  : float
        distortspeed  : float
        renderhint    : str   ('animatedmodel', 'normalmap', 'specularmap', '')
        priority      : int   (render priority, 0=default)
        texture_op    : str   (texture blending operation, '')
    """
    result = {
        'blending': 0,
        'cube': False,
        'proceduretype': '',
        'numx': 0,
        'numy': 0,
        'fps': 0.0,
        'envmaptexture': '',
        'bumpmaptexture': '',
        'bumpmapscaling': 1.0,
        'rotate': 0.0,
        'loop': True,
        'clamp_s': False,
        'clamp_t': False,
        'decal': False,
        'mipmap': 1,
        'filter': True,
        'downsamplemax': 0,
        'downsamplemin': 0,
        'isbumpmap': False,
        'islightmap': False,
        'diffusebumpmap': '',
        'specbumpmap': '',
        'distort': False,
        'distortangle': 0.0,
        'distortspeed': 0.0,
        'clamp': False,
        'xbox_downsample': 0,
        'compresstexture': False,
        'renderhint': '',
        'priority': 0,
        'texture_op': '',
        # Additional KotOR TXI commands
        'wateralpha': 1.0,       # Water/transparency alpha multiplier (0.0-1.0)
        'specularcolour': '',    # Specular highlight color texture name
        'fontwidth': 0,          # GUI font glyph width
        'fontheight': 0,         # GUI font glyph height
        'spacingr': 0.0,         # GUI font right-spacing
        'spacingb': 0.0,         # GUI font bottom-spacing
        'numchars': 0,           # GUI font character count
        'basetexture': '',       # Base texture reference
        'defaultwidth': 0,       # Default width for procedural textures
        'defaultheight': 0,      # Default height for procedural textures
        'channelscale': (1.0, 1.0, 1.0, 1.0),  # RGBA channel scale (per-channel)
        'channeltranslate': (0.0, 0.0, 0.0, 0.0),  # RGBA channel translation
    }
    if not txi:
        return result

    # Multi-line coordinate commands (upperleftcoords / lowerrightcoords)
    # These consume the next N lines after the command.
    _coord_mode = None
    _coord_rem = 0

    for raw_line in txi.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Handle multi-line coordinate blocks
        if _coord_mode is not None:
            _coord_rem -= 1
            if _coord_rem <= 0:
                _coord_mode = None
            continue

        # Split into command and optional argument
        parts = line.split(None, 1)
        if not parts:
            continue
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ''

        try:
            if cmd == 'blending':
                s = arg.lower()
                if s == 'additive':
                    result['blending'] = 1
                elif s in ('punchthrough', 'punch-through'):
                    result['blending'] = 2
                else:
                    result['blending'] = int(arg) if arg.isdigit() else 0
            elif cmd == 'cube':
                result['cube'] = bool(int(arg)) if arg else True
            elif cmd == 'proceduretype':
                result['proceduretype'] = arg.lower()
            elif cmd == 'numx':
                result['numx'] = int(arg)
            elif cmd == 'numy':
                result['numy'] = int(arg)
            elif cmd == 'fps':
                result['fps'] = float(arg)
            elif cmd in ('envmaptexture', 'env_map_texture'):
                # FIX-ENVMAP: envmaptexture and bumpyshinytexture both specify the
                # reflection/environment-map companion texture for the diffuse layer.
                # Reference: KotOR.js TXI.ts:161-164, xoreos modelnode.cpp:479-482.
                result['envmaptexture'] = arg.lower()
            elif cmd in ('bumpmaptexture', 'bumpmap'):
                result['bumpmaptexture'] = arg.lower()
            elif cmd == 'bumpmapscaling':
                result['bumpmapscaling'] = float(arg)
            elif cmd == 'rotate':
                result['rotate'] = float(arg)
            elif cmd == 'loop':
                result['loop'] = bool(int(arg)) if arg else True
            elif cmd in ('clamps', 'clamp_s'):
                result['clamp_s'] = bool(int(arg)) if arg else True
            elif cmd in ('clampt', 'clamp_t'):
                result['clamp_t'] = bool(int(arg)) if arg else True
            elif cmd == 'clamp':
                # KotOR 'clamp' is a bitmask per xoreos textures/txi.cpp and PyKotor:
                #   bit 0 (value & 1) = clamp S axis (U)
                #   bit 1 (value & 2) = clamp T axis (V)
                # So: clamp 1 → S only, clamp 2 → T only, clamp 3 → both axes
                # The only value seen in real K1/K2 data is 3 (both axes clamped).
                # clamp 0 → no clamping (same as omitting the command).
                try:
                    val_int = int(arg) if arg else 3  # default 3 when no arg
                except (ValueError, TypeError):
                    val_int = 3
                clamp_s_bit = bool(val_int & 1)
                clamp_t_bit = bool(val_int & 2)
                result['clamp'] = bool(val_int)
                result['clamp_s'] = clamp_s_bit
                result['clamp_t'] = clamp_t_bit
            elif cmd == 'decal':
                result['decal'] = bool(int(arg)) if arg else True
            elif cmd == 'mipmap':
                result['mipmap'] = int(arg) if arg else 1
            elif cmd == 'filter':
                result['filter'] = bool(int(arg)) if arg else True
            elif cmd == 'downsamplemax':
                result['downsamplemax'] = int(arg)
            elif cmd == 'downsamplemin':
                result['downsamplemin'] = int(arg)
            elif cmd == 'xbox_downsample':
                # Xbox-specific downsampling override (reduces texture res on Xbox)
                result['xbox_downsample'] = int(arg) if arg else 1
            elif cmd in ('compresstexture', 'compress'):
                # Request driver-level texture compression (DXTn hint)
                result['compresstexture'] = bool(int(arg)) if arg else True
            elif cmd == 'renderhint':
                # Rendering hint ('animatedmodel', 'normalmap', 'specularmap')
                result['renderhint'] = arg.lower()
            elif cmd == 'priority':
                # Render priority (0=default, higher = render later)
                result['priority'] = int(float(arg)) if arg else 0
            elif cmd in ('texop', 'texture_op', 'textureop'):
                # Texture blending op ('modulate', 'add', 'decal', etc.)
                result['texture_op'] = arg.lower()
            elif cmd == 'isbumpmap':
                result['isbumpmap'] = bool(int(arg)) if arg else True
            elif cmd == 'islightmap':
                result['islightmap'] = bool(int(arg)) if arg else True
            elif cmd in ('isdiffusebumpmap', 'diffusebumpmap'):
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['diffusebumpmap'] = arg.lower()
                else:
                    result['isbumpmap'] = True
            elif cmd == 'bumpyshinytexture':
                # KotOR/xoreos: bumpyshinytexture is an ALIAS for envmaptexture.
                # Both KotOR.js (TXI.ts:161-164) and xoreos (modelnode.cpp:479-482)
                # treat this as the environment-map companion texture.
                # Do NOT treat it as a bump map — it is a reflection/env map.
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['envmaptexture'] = arg.lower()
                # else: malformed line, skip
            elif cmd in ('isspecularbumpmap', 'specularbumpmap'):
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['specbumpmap'] = arg.lower()
                else:
                    result['isbumpmap'] = True
            elif cmd == 'distort':
                result['distort'] = bool(int(arg)) if arg else True
            elif cmd == 'distortangle':
                result['distortangle'] = float(arg)
            elif cmd == 'distortspeed':
                result['distortspeed'] = float(arg)
            elif cmd in ('upperleftcoords', 'lowerrightcoords'):
                # These commands are followed by N coordinate lines
                try:
                    _coord_rem = int(arg)
                    _coord_mode = cmd
                except (ValueError, TypeError):
                    pass
            elif cmd == 'wateralpha':
                result['wateralpha'] = float(arg) if arg else 1.0
            elif cmd in ('specularcolour', 'specularcolor'):
                result['specularcolour'] = arg.lower() if arg else ''
            elif cmd == 'fontwidth':
                result['fontwidth'] = int(arg) if arg else 0
            elif cmd == 'fontheight':
                result['fontheight'] = int(arg) if arg else 0
            elif cmd == 'spacingr':
                result['spacingr'] = float(arg) if arg else 0.0
            elif cmd == 'spacingb':
                result['spacingb'] = float(arg) if arg else 0.0
            elif cmd == 'numchars':
                result['numchars'] = int(arg) if arg else 0
            elif cmd == 'basetexture':
                result['basetexture'] = arg.lower() if arg else ''
            elif cmd == 'defaultwidth':
                result['defaultwidth'] = int(arg) if arg else 0
            elif cmd == 'defaultheight':
                result['defaultheight'] = int(arg) if arg else 0
            elif cmd == 'channelscale':
                # channelscale has 4 float values on the next line as a block
                # For now just mark it as encountered; the coordinate block parser handles it
                pass
            elif cmd == 'channeltranslate':
                pass
            # Silently ignore unknown commands (many TXI commands are display hints)
        except (ValueError, TypeError, IndexError):
            pass

    return result


def _extract_alpha_test_from_tpc(raw_bytes: bytes) -> float:
    """Extract the alpha_test_threshold float from TPC header bytes [4-7].

    KotOR TPC header layout (Aurora engine):
      [0-3]  uint32  data_sz
      [4-7]  float   alpha_test_threshold  (0.0 = ignore, >0 = discard threshold)
      [8-9]  uint16  width
      [10-11]uint16  height
      [12]   uint8   encoding
      ...

    Used only for blending=punchthrough surfaces (TXI 'blending punchthrough').
    The engine's GL_ALPHA_TEST reference value; values above this pass the test.

    References:
        Kotor.NET KotorModelLoader.cs — reads TransparencyHint at +84 (mesh),
        alpha_test float from TPC header [4-7].
        xoreos tpc.cpp — alpha_test_threshold at offset 4.
        PyKotor io_tpc.py — alpha_test field in TPCHeader struct.

    Returns:
        float alpha_test_threshold (0.0..1.0). Default 0.5 if not present.
    """
    if not raw_bytes or len(raw_bytes) < 8:
        return 0.5
    try:
        at = struct.unpack_from('<f', raw_bytes, 4)[0]
        if 0.0 < at <= 1.0:
            return at
    except Exception:
        pass
    return 0.5


def _apply_txi_to_node(node, txi_str: str, alpha_test: float = 0.5) -> None:
    """
    Parse a TXI string and apply the metadata fields to a ModelNode.

    Called after loading a texture so that TXI data from TPC embedded
    metadata (or a standalone .txi file) updates the node's rendering
    properties.  Only fields that have explicit TXI entries are updated;
    other node fields remain at their ModelNode defaults.

    Args:
        node      : ModelNode instance to update
        txi_str   : Raw TXI ASCII string (may be empty)
        alpha_test: Per-node punchthrough threshold from TPC header [4-7].
                    FIX-ALPHATEST: Stored on node.txi_alpha_test so the GPU
                    renderer can pass it as u_alpha_test per draw-call instead
                    of using the hardcoded 0.5 global default.
                    Default: 0.5 (matches Aurora engine default).
    """
    # Always store alpha_test on node (even if txi_str is empty —
    # punchthrough threshold comes from TPC header, not TXI content).
    if hasattr(node, 'txi_alpha_test'):
        node.txi_alpha_test = float(alpha_test) if 0.0 < alpha_test <= 1.0 else 0.5

    if not txi_str:
        return
    meta = _parse_txi_string(txi_str)

    # Blending / transparency
    if meta['blending']:
        node.txi_blending = meta['blending']

    # Cubemap flag
    if meta['cube']:
        node.txi_cube = True

    # Flipbook animation
    if meta['proceduretype']:
        node.txi_proceduretype = meta['proceduretype']
    if meta['numx'] > 0:
        node.txi_numx = meta['numx']
    if meta['numy'] > 0:
        node.txi_numy = meta['numy']
    if meta['fps'] > 0.0:
        node.txi_fps = meta['fps']

    # Companion textures
    # FIX-ENVMAP: envmaptexture and bumpyshinytexture both name the env-map companion.
    # _parse_txi_string already maps bumpyshinytexture → result['envmaptexture'],
    # so both keywords are handled via the same field here.
    if meta['envmaptexture']:
        node.txi_envmaptexture = meta['envmaptexture']
    if meta['bumpmaptexture']:
        node.txi_bumpmaptexture = meta['bumpmaptexture']
        node.bump_map = meta['bumpmaptexture']  # also update the bump_map field
    if meta['bumpmapscaling'] != 1.0:
        node.txi_bumpmapscaling = meta['bumpmapscaling']

    # UV rotation from TXI (additional to rotate_texture flag)
    if meta['rotate'] != 0.0:
        node.txi_rotate = meta['rotate']

    # Loop
    node.txi_loop = meta['loop']

    # Clamp modes (clamp sets both axes; individual overrides respected too)
    if meta['clamp']:
        node.txi_clamp_s = True
        node.txi_clamp_t = True
    if meta['clamp_s']:
        node.txi_clamp_s = True
    if meta['clamp_t']:
        node.txi_clamp_t = True

    # Water alpha (modulates texture transparency for water/lava surfaces)
    if meta.get('wateralpha', 1.0) != 1.0:
        node.txi_wateralpha = meta['wateralpha']

    # Specular colour map (bumpyshinytexture / specularcolour)
    if meta.get('specularcolour'):
        node.txi_specularcolour = meta['specularcolour']

    # Decal: TXI decal flag — surface is a decal (alpha as blend weight over bg)
    if meta.get('decal'):
        node.txi_decal = True

    # Bump/normal-map flag — this texture slot IS a bump/normal map
    if meta.get('isbumpmap'):
        node.txi_isbumpmap = True

    # Lightmap flag — this texture slot IS a lightmap
    if meta.get('islightmap'):
        node.txi_islightmap = True


def _compute_flipbook_uv(u: float, v: float, numx: int, numy: int,
                          frame: int) -> tuple:
    """
    Compute UV coordinates within a flipbook (sprite-sheet) texture frame.

    Flipbook textures tile the sprite sheet into numx × numy cells.
    Frame 0 is top-left, frame (numx-1) is top-right, frame (numx*(numy-1))
    is bottom-left (matching KotOR.js TXI.ts cell ordering convention).

    Args:
        u, v  : Original UV coords (0..1 within the full sprite sheet)
        numx  : Number of columns
        numy  : Number of rows
        frame : Current animation frame index (0-based)

    Returns:
        (u_out, v_out): UV within the specific cell for this frame
    """
    if numx <= 0 or numy <= 0:
        return u, v
    # Clamp frame to valid range
    total_frames = numx * numy
    frame = frame % total_frames

    col = frame % numx
    row = frame // numx

    cell_w = 1.0 / numx
    cell_h = 1.0 / numy

    # u, v within [0,1] map to the sub-cell
    u_out = (col + (u % 1.0)) * cell_w
    v_out = (row + (v % 1.0)) * cell_h
    return u_out, v_out


# ─────────────────────────────────────────────────────────────────────
#  Arc-ball Camera (Maya style)
# ─────────────────────────────────────────────────────────────────────

class ArcBallCamera:
    """
    Orbital camera.
      • LMB drag   → orbit  (azimuth / elevation)
      • MMB / RMB  → pan    (shift target)
      • Scroll     → zoom
    """
    def __init__(self):
        self.azimuth   = 30.0     # degrees
        self.elevation = 20.0     # degrees  (clamped –89..89)
        self.distance  = 5.0
        self.target    = [0.0, 1.0, 0.0]
        self.fov       = 45.0
        self._near     = 0.01
        self._far      = 1000.0

    # ── eye position ──────────────────────────────────────────────────

    def eye(self):
        """Camera eye position. KotOR is Z-up, so elevation rotates in XZ plane."""
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        ce = math.cos(el)
        x  = self.distance * ce * math.cos(az)
        y  = self.distance * ce * math.sin(az)
        z  = self.distance * math.sin(el)
        return (self.target[0]+x, self.target[1]+y, self.target[2]+z)

    # ── controls ──────────────────────────────────────────────────────

    def orbit(self, daz: float, del_: float):
        self.azimuth   = (self.azimuth + daz) % 360.0
        self.elevation = _clamp(self.elevation + del_, -85.0, 85.0)

    def zoom(self, steps: float):
        self.distance = max(0.05, self.distance * (0.9 ** steps))

    def pan(self, dx_px: float, dy_px: float, viewport_h: int):
        right, up, fwd, eye = self._view_matrix()
        scale = self.distance / max(viewport_h, 1) * 1.8
        self.target[0] -= right[0] * dx_px * scale
        self.target[1] -= right[1] * dx_px * scale
        self.target[2] -= right[2] * dx_px * scale
        self.target[0] += up[0] * dy_px * scale
        self.target[1] += up[1] * dy_px * scale
        self.target[2] += up[2] * dy_px * scale

    def frame_bounds(self, bb_min, bb_max):
        """Fit camera to bounding box using screen-space projection (Z-up world).

        Instead of using the raw 3-D diagonal (which over-distances wide/flat
        models like quadrupeds or banthas), we iterate over the 8 BB corners,
        project them onto the camera's right/up plane, and derive the minimum
        distance required so that all projected corners fit inside the FOV.
        """
        cx = (bb_min[0] + bb_max[0]) * 0.5
        cy = (bb_min[1] + bb_max[1]) * 0.5
        cz = (bb_min[2] + bb_max[2]) * 0.5
        self.target    = [cx, cy, cz]
        self.elevation = 25.0
        self.azimuth   = -45.0

        # Compute a safe initial distance (3-D diagonal) just to get camera vectors
        dx = bb_max[0] - bb_min[0]
        dy = bb_max[1] - bb_min[1]
        dz = bb_max[2] - bb_min[2]
        diag = math.sqrt(dx*dx + dy*dy + dz*dz)
        self.distance = max(0.5, diag * 1.1)

        # Compute camera right/up vectors at current orientation
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        fwd_v  = (-math.cos(el)*math.cos(az),
                  -math.cos(el)*math.sin(az),
                  -math.sin(el))
        world_up = (0.0, 0.0, 1.0)
        right_v = _normalize(_cross(fwd_v, world_up))
        if _dot(right_v, right_v) < 1e-6:
            right_v = _normalize(_cross(fwd_v, (0.0, 1.0, 0.0)))
        up_v = _normalize(_cross(right_v, fwd_v))

        # 8 corners of the bounding box relative to centre
        corners = [
            (bb_min[0]-cx, bb_min[1]-cy, bb_min[2]-cz),
            (bb_max[0]-cx, bb_min[1]-cy, bb_min[2]-cz),
            (bb_min[0]-cx, bb_max[1]-cy, bb_min[2]-cz),
            (bb_max[0]-cx, bb_max[1]-cy, bb_min[2]-cz),
            (bb_min[0]-cx, bb_min[1]-cy, bb_max[2]-cz),
            (bb_max[0]-cx, bb_min[1]-cy, bb_max[2]-cz),
            (bb_min[0]-cx, bb_max[1]-cy, bb_max[2]-cz),
            (bb_max[0]-cx, bb_max[1]-cy, bb_max[2]-cz),
        ]

        # Project each corner onto right/up plane; find max screen extent
        max_right = max_up = 0.0
        for c in corners:
            pr = abs(_dot(c, right_v))
            pu = abs(_dot(c, up_v))
            if pr > max_right: max_right = pr
            if pu > max_up:    max_up    = pu

        # Determine required distance so the extent fits inside the FOV
        # At distance d: half_screen_world = d * tan(fov/2)
        # We need half_screen_world >= max(max_right, max_up) * 1.15 (5% margin)
        half_fov_tan = math.tan(math.radians(self.fov) * 0.5)
        screen_extent = max(max_right, max_up, 0.01)
        fitted_dist   = (screen_extent * 1.18) / half_fov_tan

        # Also keep at least the depth-extent / 2 to avoid near-plane clipping
        depth_extent = abs(_dot((dx, dy, dz), fwd_v))
        min_dist     = max(0.3, depth_extent * 0.6)

        self.distance = max(fitted_dist, min_dist)

    # ── projection helpers ────────────────────────────────────────────

    def _view_matrix(self):
        """Returns (right, up, fwd) unit vectors + eye position."""
        eye = self.eye()
        fwd = _normalize(_sub(self.target, eye))
        world_up = (0.0, 0.0, 1.0)
        right = _normalize(_cross(fwd, world_up))
        if _dot(right, right) < 1e-6:
            world_up = (0.0, 1.0, 0.0)
            right = _normalize(_cross(fwd, world_up))
        up = _cross(right, fwd)
        return right, up, fwd, eye

    def project(self, x, y, z, W, H):
        """Project world point to screen pixel (sx, sy, depth). Returns None if behind camera."""
        right, up, fwd, eye = self._view_matrix()
        dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
        cx =  _dot((dx,dy,dz), right)
        cy =  _dot((dx,dy,dz), up)
        cz =  _dot((dx,dy,dz), fwd)
        if cz < self._near:
            return None
        f   = 1.0 / math.tan(math.radians(self.fov) * 0.5)
        sx  = int(W * 0.5 + (cx / cz) * f * H * 0.5)
        sy  = int(H * 0.5 - (cy / cz) * f * H * 0.5)
        return sx, sy, cz


# ─────────────────────────────────────────────────────────────────────
#  Texture loader
# ─────────────────────────────────────────────────────────────────────

class TextureCache:
    """
    Loads and caches textures from disk.
    - Auto-detects KotOR TPC data in .tga files (KotOR stores TPC with .tga extension)
    - Supports DXT1 (enc=2), DXT5 (enc=4), uncompressed Grey/RGB/RGBA
    - Supports plain TGA, PNG via Pillow
    - Loads and caches TXI metadata (from embedded TPC TXI or standalone .txi files)
    Returns PIL.Image in RGBA mode at full resolution (capped at MAX_SIZE).
    """

    MAX_SIZE = 512   # max viewport texture resolution per axis
    # Raised from 256→512: KotOR textures are typically 128×128 or 256×256.
    # At 512px cap we load textures at their native resolution (no downscale for
    # typical sizes), eliminating the main source of blurry/blocky texture rendering.
    # Cost: 512×512 RGBA = 1MB per texture vs 256KB at 256px — acceptable for modern hardware.

    def __init__(self):
        self._cache: Dict[str, Optional['Image.Image']] = {}
        self._txi_cache: Dict[str, str] = {}   # name → TXI string ('' if absent)
        self._search_dirs: List[str] = []
        self._game_library = None   # Optional GameLibrary for BIF-backed loading
        self._game_tag: str = "K1"
        self._installation = None  # Optional KotorInstallation (fast path, legacy)
        self._resource_manager = None  # Optional ResourceManager (new unified path)
        self._lock = threading.Lock()  # thread-safe access (render + prewarm threads)
        # Per-name load lock dict: prevents two threads loading the SAME texture simultaneously
        # while not blocking threads loading DIFFERENT textures (vs. a single global lock).
        self._load_locks: Dict[str, threading.Lock] = {}
        self._load_locks_lock = threading.Lock()  # protects _load_locks dict itself
        # Mip-bias cache: per-INSTANCE so clear_mip_cache() only affects this cache.
        # (Was previously a class-level dict which caused id() reuse bugs across instances.)
        self._mip_bias_cache: Dict[int, Optional['Image.Image']] = {}

    def set_search_dirs(self, dirs: List[str]):
        new_dirs = [d for d in dirs if d and os.path.isdir(d)]
        # Only clear cache if the search directories actually changed
        with self._lock:
            if new_dirs != self._search_dirs:
                self._search_dirs = new_dirs
                self._cache.clear()
                self._txi_cache.clear()
                # Clear per-key load locks too (keys may no longer be relevant)
                with self._load_locks_lock:
                    self._load_locks.clear()
                log.debug(f"TextureCache search dirs updated: {self._search_dirs}")

    def set_game_library(self, library, game_tag: str = "K1"):
        """
        Attach a GameLibrary instance so textures can be loaded directly from
        BIF/ERF archives when not found on disk.  Clears the cache when the
        library reference changes.
        """
        with self._lock:
            if library is not self._game_library:
                self._game_library = library
                self._game_tag = game_tag
                self._cache.clear()
                self._txi_cache.clear()
                with self._load_locks_lock:
                    self._load_locks.clear()
                log.debug(f"TextureCache: game library set ({game_tag})")
            elif game_tag != self._game_tag:
                # Same library, but switching between K1 and K2 model –
                # update the tag and clear the cache so textures are re-resolved
                # from the correct game's archives.
                self._game_tag = game_tag
                self._cache.clear()
                self._txi_cache.clear()
                with self._load_locks_lock:
                    self._load_locks.clear()
                log.debug(f"TextureCache: game tag updated to {game_tag} (cache cleared)")

    def set_installation(self, installation, game_tag: str = "K1"):
        """
        Attach a KotorInstallation (fast lazy BIF/ERF reader) for texture loading.
        This supersedes the slower GameLibrary path for texture lookups.
        Clears the cache when the installation reference changes.
        """
        with self._lock:
            if installation is not self._installation:
                self._installation = installation
                self._game_tag = game_tag
                self._cache.clear()
                self._txi_cache.clear()
                with self._load_locks_lock:
                    self._load_locks.clear()
                log.info(f"TextureCache: KotorInstallation set ({game_tag})")

    def set_resource_manager(self, manager, game_tag: str = "K1"):
        """
        Attach the new unified ResourceManager as the primary texture backend.

        This is the preferred method — it supersedes both set_installation() and
        set_game_library() by routing all archive lookups through the single
        ResourceManager which handles KEY/BIF, TexturePacks ERFs, module ERFs,
        and Override/ in the correct priority order.

        Clears all caches when the manager reference or game tag changes.
        """
        with self._lock:
            changed = (manager is not self._resource_manager or
                       game_tag != self._game_tag)
            if changed:
                self._resource_manager = manager
                self._game_tag = game_tag
                # Also keep _installation in sync for legacy code paths
                if manager is not None:
                    inst = manager.get_k1() if game_tag == "K1" else manager.get_k2()
                    # _installation is used by legacy get_txi() / get_raw_header()
                    # We don't set it here to avoid the old path running — the new
                    # _resource_manager path takes priority in _load().
                self._cache.clear()
                self._txi_cache.clear()
                with self._load_locks_lock:
                    self._load_locks.clear()
                log.info(f"TextureCache: ResourceManager set ({game_tag})")

    def get_txi(self, name: str) -> str:
        """
        Get the TXI metadata string for a texture by name.

        Checks (in order):
          1. _txi_cache (fast path)
          2. Standalone .txi file on disk next to the texture
          3. TXI embedded in TPC file (via _extract_txi_from_tpc)
          4. TXI from BIF/ERF archive via GameLibrary

        Returns the raw TXI string (may be empty string if no TXI exists).
        """
        if not name:
            return ''
        clean = _clean_tex_name(name)
        if not clean:
            return ''
        key = clean.lower()
        # Fast path
        if key in self._txi_cache:
            return self._txi_cache[key]

        txi_str = ''
        try:
            with self._lock:
                search_dirs = list(self._search_dirs)
                game_library = self._game_library
                game_tag = self._game_tag

            # 1. Look for standalone .txi file on disk
            for search_dir in search_dirs:
                txi_path = os.path.join(search_dir, clean + '.txi')
                if os.path.exists(txi_path):
                    try:
                        with open(txi_path, 'r', encoding='utf-8', errors='replace') as f:
                            txi_str = f.read().strip()
                        if txi_str:
                            log.debug(f"TXI '{clean}' loaded from {txi_path}")
                            break
                    except Exception as e:
                        log.debug(f"TXI file read error {txi_path}: {e}")

            # 2. Extract TXI from embedded TPC data
            if not txi_str:
                for search_dir in search_dirs:
                    for ext in ('.tga', '.TGA', '.tpc', '.TPC'):
                        tex_path = os.path.join(search_dir, clean + ext)
                        if not os.path.exists(tex_path):
                            continue
                        try:
                            with open(tex_path, 'rb') as f:
                                raw = f.read()
                            if _is_tpc_data(raw):
                                txi_str = _extract_txi_from_tpc(raw)
                                if txi_str:
                                    log.debug(f"TXI '{clean}' extracted from {ext} TPC file")
                                    break
                        except Exception as e:
                            log.debug(f"TXI TPC extract error {tex_path}: {e}")
                    if txi_str:
                        break

            # 3. Load from BIF/ERF archive via GameLibrary
            if not txi_str and game_library is not None:
                try:
                    # TXI resource type ID = 1448 (RES_TXI from game_library.py)
                    _RES_TXI = 1448
                    raw = game_library.get_resource_data(clean, _RES_TXI, game_tag)
                    if raw:
                        txi_str = raw.decode('utf-8', errors='replace').strip()
                        if txi_str:
                            log.debug(f"TXI '{clean}' loaded from BIF/ERF archive")
                    # If no standalone TXI, try to get TXI from embedded TPC
                    if not txi_str:
                        raw = game_library.get_texture_data(clean, game_tag)
                        if raw and _is_tpc_data(raw):
                            txi_str = _extract_txi_from_tpc(raw)
                            if txi_str:
                                log.debug(f"TXI '{clean}' extracted from BIF TPC")
                except Exception as e:
                    log.debug(f"TXI BIF load error '{clean}': {e}")

        except Exception as e:
            log.debug(f"TXI load error for '{name}': {e}")

        with self._lock:
            self._txi_cache[key] = txi_str
        return txi_str

    def get_raw_header(self, name: str) -> Optional[bytes]:
        """Return the first 128 bytes of the TPC/TGA file for a texture.

        Used by _load_txi_metadata_for_model() to extract the alpha_test_threshold
        float from TPC header bytes [4-7] (FIX-ALPHATEST).

        Returns 128-byte header bytes if the texture is a TPC file, else None.
        The caller uses _extract_alpha_test_from_tpc() to read the float value.

        References:
            Kotor.NET TPC.cs — TPC header layout (width/height/encoding/alpha_test)
            xoreos tpc.cpp — alpha_test_threshold at header offset 4
            PyKotor io_tpc.py — TPCHeader.alpha_test_threshold field
        """
        if not name:
            return None
        clean = _clean_tex_name(name)
        if not clean:
            return None
        try:
            with self._lock:
                search_dirs = list(self._search_dirs)
                game_library = self._game_library
                game_tag = self._game_tag
            # 1. Search on-disk directories
            for search_dir in search_dirs:
                for ext in ('.tga', '.TGA', '.tpc', '.TPC'):
                    path = os.path.join(search_dir, clean + ext)
                    if not os.path.exists(path):
                        continue
                    try:
                        with open(path, 'rb') as f:
                            header = f.read(128)
                        if _is_tpc_data(header):
                            return header
                    except Exception:
                        pass
            # 2. BIF/ERF archive
            if game_library is not None:
                try:
                    raw = game_library.get_texture_data(clean, game_tag)
                    if raw and len(raw) >= 128 and _is_tpc_data(raw[:128]):
                        return raw[:128]
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def get(self, name: str) -> Optional['Image.Image']:
        if not _PIL or not name:
            return None
        clean = _clean_tex_name(name)
        if not clean:
            return None
        key = clean.lower()
        # Fast path: CPython GIL makes simple dict lookups atomic.
        # If the key is already in the cache (even None = "not found"), return immediately.
        try:
            return self._cache[key]
        except KeyError:
            pass
        # Slow path: use a per-key lock so two threads loading DIFFERENT textures
        # don't block each other, but two threads loading the SAME texture share one lock.
        # This avoids the old pattern where the global lock was held during disk I/O,
        # blocking the render thread for the entire duration of a BIF archive read.
        with self._load_locks_lock:
            if key not in self._load_locks:
                self._load_locks[key] = threading.Lock()
            key_lock = self._load_locks[key]
        with key_lock:
            # Double-check: another thread may have loaded it while we waited
            try:
                return self._cache[key]
            except KeyError:
                pass
            try:
                img = self._load(key)
            except MemoryError:
                log.warning(f"TextureCache: out of memory loading '{name}' — skipping")
                img = None
            except Exception as e:
                log.debug(f"TextureCache: error loading '{name}': {e}")
                img = None
            # Store result (even None) so future calls hit the fast path
            with self._lock:
                self._cache[key] = img
        return img

    def _load(self, name: str) -> Optional['Image.Image']:
        """Load texture by name: disk search dirs first, then BIF archives.
        Called under per-key lock — safe for concurrent access.

        v12.7 ALPHA FIX: KotOR DXT5 alpha channel has three distinct meanings
        depending on TXI metadata.  After loading, we check the TXI for:
          1. 'bumpmaptexture' → alpha is bump/specular data, NOT transparency.
             Force alpha channel = 255 (fully opaque surface rendering).
             Affects: c_rancor01, c_hutt01, c_drdassassin01, etc.
          2. 'blending punchthrough' → apply TPC alpha_test_threshold as binary cutoff.
             Uses the float at TPC header bytes [4-7] as the GL_ALPHA_TEST value.
          3. Standard → alpha as-is (glass, hair, transparent effects).

        FIX-TXI-PREFER: _load_tpc_bytes / _load_tpc_bytes_legacy attach _txi_str
        directly to the returned PIL Image when they successfully extract TXI from
        the embedded TPC trailer.  We now prefer that attached TXI string over the
        result of get_txi() so that stock KotOR BIF textures (enc=2/4, data_sz=0)
        with embedded TXI get their blending/alpha modes applied correctly.
        The external get_txi() call is kept as a fallback for sidecar .txi files
        and archive TXI resources not embedded in the TPC itself.
        """
        # Snapshot search dirs under lock to avoid TOCTOU with set_search_dirs()
        with self._lock:
            search_dirs = list(self._search_dirs)
            game_library = self._game_library
            game_tag = self._game_tag
            installation = self._installation
            resource_manager = self._resource_manager

        # ── 1. Search on-disk directories first (override folder wins) ──────
        for search_dir in search_dirs:
            # Priority: .tga first (may be TPC), then .tpc, then .png/.dds
            for ext in ('.tga', '.TGA', '.tpc', '.TPC', '.png', '.PNG', '.dds', '.DDS'):
                path = os.path.join(search_dir, name + ext)
                if not os.path.exists(path):
                    continue
                try:
                    img = self._load_file(path)
                    if img is not None:
                        img = self._resize_if_needed(img, name)
                        # Apply TXI-aware alpha processing for on-disk textures.
                        # FIX-TXI-PREFER: use _txi_str already attached to img
                        # (by _load_tpc_bytes/legacy) if available, then fall back
                        # to get_txi() for sidecar files / archive TXI resources.
                        try:
                            with open(path, 'rb') as fraw:
                                raw_bytes = fraw.read(512)  # header only for alpha_test
                            txi_s = getattr(img, '_txi_str', None)
                            if txi_s is None:
                                txi_s = self.get_txi(name)
                            txi_m = _parse_txi_string(txi_s) if txi_s else _parse_txi_string('')
                            img = self._apply_kotor_alpha(raw_bytes, img, txi_m)
                        except Exception:
                            pass
                        log.debug(f"Texture '{name}' loaded from {os.path.basename(path)}")
                        return img
                except MemoryError:
                    log.warning(f"Texture '{name}': out of memory — skipping")
                    return None
                except Exception as e:
                    log.debug(f"Texture load error {path}: {e}")
        # ── 2. ResourceManager (unified BIF/ERF/Override, <2ms) ─────────────
        # New primary archive backend — replaces the split installation/game_library path.
        # Checks: Override > module ERFs > TexturePacks ERFs > BIF in correct priority.
        if resource_manager is not None:
            try:
                raw = resource_manager.get_texture(name, game_tag)
                if raw:
                    img = self._load_bytes(raw)
                    if img is not None:
                        img = self._resize_if_needed(img, name)
                        try:
                            txi_s = getattr(img, '_txi_str', None)
                            if not txi_s:
                                txi_s = resource_manager.get_txi(name, game_tag)
                            txi_m = _parse_txi_string(txi_s) if txi_s else _parse_txi_string('')
                            img = self._apply_kotor_alpha(raw, img, txi_m)
                        except Exception:
                            pass
                        log.debug(f"Texture '{name}' loaded from ResourceManager ({game_tag})")
                        return img
            except MemoryError:
                log.warning(f"Texture '{name}': out of memory from ResourceManager — skipping")
                return None
            except Exception as e:
                log.debug(f"Texture ResourceManager error '{name}': {e}")
        # ── 3. Legacy: KotorInstallation (lazy BIF/ERF seek, <5ms) ──────────
        if installation is not None:
            try:
                raw = installation.get_texture(name)
                if raw:
                    img = self._load_bytes(raw)
                    if img is not None:
                        img = self._resize_if_needed(img, name)
                        try:
                            txi_s = getattr(img, '_txi_str', None)
                            if not txi_s:
                                txi_s = installation.get_txi(name)
                            txi_m = _parse_txi_string(txi_s) if txi_s else _parse_txi_string('')
                            img = self._apply_kotor_alpha(raw, img, txi_m)
                        except Exception:
                            pass
                        log.debug(f"Texture '{name}' loaded from KotorInstallation")
                        return img
            except MemoryError:
                log.warning(f"Texture '{name}': out of memory from installation — skipping")
                return None
            except Exception as e:
                log.debug(f"Texture installation load error '{name}': {e}")
        # ── 4. Fallback: load from BIF/KEY/ERF archives via GameLibrary ──────
        if game_library is not None:
            try:
                raw = game_library.get_texture_data(name, game_tag)
                if raw:
                    img = self._load_bytes(raw)
                    if img is not None:
                        img = self._resize_if_needed(img, name)
                        # Apply TXI-aware alpha processing for BIF textures.
                        # FIX-TXI-PREFER: _load_bytes → _load_tpc_bytes attaches
                        # _txi_str to img if it successfully parsed embedded TXI.
                        # Use that first; fall back to get_txi() which re-fetches
                        # from the archive (slower but works for sidecar .txi).
                        try:
                            txi_s = getattr(img, '_txi_str', None)
                            if not txi_s:
                                txi_s = self.get_txi(name)
                            txi_m = _parse_txi_string(txi_s) if txi_s else _parse_txi_string('')
                            img = self._apply_kotor_alpha(raw, img, txi_m)
                        except Exception:
                            pass
                        log.debug(f"Texture '{name}' loaded from BIF archive")
                        return img
            except MemoryError:
                log.warning(f"Texture '{name}': out of memory from BIF — skipping")
                return None
            except Exception as e:
                log.debug(f"Texture BIF load error '{name}': {e}")

        log.debug(f"Texture '{name}' not found in search dirs or BIF archives")
        return None

    @staticmethod
    def _apply_kotor_alpha(raw_bytes: bytes, img: 'Image.Image',
                           txi_meta: dict) -> 'Image.Image':
        """
        Apply correct KotOR alpha processing to a loaded RGBA texture.

        KotOR uses DXT5 alpha for different purposes:
          1. bumpmaptexture in TXI → alpha = normal/bump map data, NOT transparency.
             Force alpha = 255 (solid opaque surface).
          2. envmaptexture / bumpyshinytexture in TXI → alpha = env-map blend weight.
             KotOR uses "EnvironmentBlendedOver" (xoreos/modelnode.cpp:726-773):
             The env map is drawn ADDITIVELY on top of the diffuse, weighted by
             (1 - diffuse.alpha).  Where alpha=0, env shows at full strength.
             Where alpha=1, env barely contributes.  We PRESERVE the alpha channel
             here so the GPU fragment shader can use it for BlendedOver blending.
             IMPORTANT: 'bumpyshinytexture' is an alias for 'envmaptexture' in
             both KotOR.js (TXI.ts:161-164) and xoreos (modelnode.cpp:479-482).
          3. blending punchthrough in TXI → binary alpha cutoff at TPC threshold.
             Read alpha_test_threshold from TPC header bytes [4-7].
          4. blending additive (1) → keep alpha as-is for additive particle effects.
          5. Standard (blending=0, no bump, no envmap) → FORCE alpha=255.
             KotOR DXT5 textures store bump/specular data in the alpha
             channel by default — treating it as transparency makes models
             look see-through.  The engine itself ignores alpha on opaque
             surfaces; we must do the same.

        Returns modified image (or original if no processing needed).
        """
        if img is None or not _NUMPY:
            return img
        try:
            blending = txi_meta.get('blending', 0)
            has_bump = bool(txi_meta.get('bumpmaptexture', ''))
            has_env  = bool(txi_meta.get('envmaptexture', ''))
            if has_bump:
                # Case 1: bump map — alpha is normal/bump data, NOT transparency.
                # Force fully opaque so the model renders solid.
                arr = np.array(img)
                if arr[:, :, 3].min() < 255:
                    arr[:, :, 3] = 255
                    return Image.fromarray(arr, 'RGBA')
            elif has_env:
                # Case 2: env map — alpha = blend weight between surface and env map.
                # PRESERVE the alpha channel (do NOT force to 255).
                # The GPU shader reads alpha as env_weight; the surface is opaque
                # (final_alpha=1 is forced in the shader when u_has_env=1).
                # The CPU path must also not override this channel.
                pass  # keep original alpha for env map blending
            elif blending == 2:
                # Case 3: punchthrough alpha — apply TPC threshold as hard cutoff
                threshold = 128  # default if TPC header not available
                if raw_bytes and len(raw_bytes) >= 8:
                    import struct as _s
                    try:
                        at = _s.unpack_from('<f', raw_bytes, 4)[0]
                        at = max(0.0, min(1.0, at))
                        threshold = int(at * 255)
                    except Exception:
                        pass
                if threshold > 0:
                    arr = np.array(img)
                    alpha = arr[:, :, 3]
                    if not (np.all(alpha >= threshold) or np.all(alpha < threshold)):
                        arr[:, :, 3] = np.where(alpha >= threshold, 255, 0).astype(np.uint8)
                        return Image.fromarray(arr, 'RGBA')
            elif blending == 1:
                # Case 4: additive blend — keep alpha for additive particle effects
                pass
            else:
                # Case 5: standard opaque surface (blending=0, no bump, no envmap) —
                # ALWAYS force alpha=255.  KotOR DXT5 encodes bump/specular in
                # alpha; using it as transparency makes character skin see-through.
                arr = np.array(img)
                if arr[:, :, 3].min() < 255:
                    arr[:, :, 3] = 255
                    return Image.fromarray(arr, 'RGBA')
        except Exception as e:
            log.debug(f"_apply_kotor_alpha error: {e}")
        return img


    def _resize_if_needed(self, img: 'Image.Image', name: str = '') -> 'Image.Image':
        """Downscale image to MAX_SIZE if too large. Handles MemoryError gracefully."""
        try:
            w, h = img.size
            if w > self.MAX_SIZE or h > self.MAX_SIZE:
                # Maintain aspect ratio
                scale = self.MAX_SIZE / max(w, h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                img = img.resize((nw, nh), Image.LANCZOS)
                log.debug(f"Texture '{name}' downscaled {w}x{h} → {nw}x{nh}")
        except MemoryError:
            log.warning(f"Texture '{name}': MemoryError during resize — using original")
        except Exception as e:
            log.debug(f"Texture resize error '{name}': {e}")
        return img

    def _load_bytes(self, raw: bytes) -> Optional['Image.Image']:
        """Load a texture from raw bytes (TPC or TGA/PNG).

        All returned images are in BOTTOM-UP orientation so that the renderer's
        V-flip formula (tv = (1-v)*h) produces correct UV mapping.
        KotOR MDL UV V=0 means TOP of texture (Direct3D/top-down convention).
        The render-time flip converts from KotOR UV-space to PIL row-space.
        - TPC files: _load_tpc_bytes() returns bottom-up (flips DXT and uncompressed).
        - Standard TGA files (bottom-up origin): PIL loads bottom-up correctly.
        - PNG/other: PIL loads top-down, must flip to bottom-up.
        """
        if not _PIL:
            return None
        if _is_tpc_data(raw):
            return _load_tpc_bytes(raw)
        try:
            import io
            img = Image.open(io.BytesIO(raw)).convert('RGBA')
            # FIX-TGA-ORIENT: PIL always returns top-down images (row 0 = top)
            # regardless of TGA origin bit.  PIL internally flips bottom-origin
            # TGA data to top-down during Image.open().  ALL images from PIL are
            # therefore top-down.  We must flip ALL of them to bottom-up so the
            # renderer's V-flip formula (tv = (1-v)*h) maps KotOR D3D UVs
            # (V=0=top) correctly:
            #   V=0 (top) → (1-0)*h = h → last row → top of bottom-up image ✓
            #   V=1 (bottom) → (1-1)*h = 0 → row 0 → bottom of bottom-up image ✓
            #
            # Previously, bottom-origin TGA files were NOT flipped (assumed PIL
            # preserved the bottom-up layout), causing them to remain top-down
            # and render upside-down.
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            return img
        except Exception:
            return None

    def _load_file(self, path: str) -> Optional['Image.Image']:
        """
        Load a texture file. Auto-detects TPC format even for .tga extensions.
        KotOR stores TPC data in files named .tga – we detect this by checking
        the data_sz / width / height fields in the first 128 bytes.

        All returned images are in bottom-up orientation so that the render-time
        V-flip (tv = (1-v)*h) produces correct UV mapping.
        KotOR MDL UV V=0 = top of texture (Direct3D convention).
        - TPC files: bottom-up from _load_tpc_bytes() (flips DXT and uncompressed).
        - All PIL-opened images (TGA, PNG, DDS): PIL always returns top-down
          → flip to bottom-up for consistency.
        """
        try:
            with open(path, 'rb') as f:
                raw = f.read()
        except OSError as e:
            log.debug(f"Cannot read {path}: {e}")
            return None

        if _is_tpc_data(raw):
            return _load_tpc_bytes(raw)

        # Fall back to Pillow for real TGA / PNG / DDS
        if _PIL:
            try:
                import io
                img = Image.open(io.BytesIO(raw)).convert('RGBA')
                # FIX-TGA-ORIENT: PIL always returns top-down images (row 0 = top)
                # regardless of TGA origin bit.  PIL internally normalises all
                # TGA variants to top-down during Image.open().  Flip ALL images
                # to bottom-up so the renderer's V-flip formula works correctly.
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                return img
            except Exception:
                pass
        return None

    # ── UE-inspired texture mip-bias for interactive mode ────────────────
    # In UE, the streaming manager can supply lower-resolution mip levels
    # for LOD objects (StreamingManagerTexture.cpp: StreamWantedMips).
    # We replicate this by keeping a half-resolution cache ("mip1") that is
    # used during interactive orbit/drag.  This halves the number of
    # getpixel() calls in _paste_textured_triangle by reducing the texture's
    # lookup area, cutting per-frame cost roughly 4× for large textures.

    def get_mip1(self, img: 'Image.Image') -> Optional['Image.Image']:
        """
        Return a half-resolution (mip-level-1) version of *img*.

        The result is cached by image identity (id(img)).  The cache is
        intentionally per-instance so it can be cleared when textures reload.
        UE's equivalent is the mip-bias applied during interactive camera
        movement to prevent bandwidth-heavy full-resolution sampling.

        Thread-safety (v10.4): reads and writes are protected by a local
        reference snapshot so a concurrent clear_mip_cache() call from the
        main thread cannot corrupt a partial dict access mid-read.
        """
        if img is None or not _PIL:
            return img
        key = id(img)
        # FIX (v10.4): snapshot the cache dict reference so that a concurrent
        # clear_mip_cache() (which reassigns self._mip_bias_cache) doesn't
        # cause a KeyError or corrupt iteration in the render thread.
        cache = self._mip_bias_cache
        cached = cache.get(key)
        if cached is not None:
            return cached
        try:
            w, h = img.size
            nw = max(1, w // 2)
            nh = max(1, h // 2)
            mip = img.resize((nw, nh), Image.BOX if hasattr(Image, 'BOX') else Image.NEAREST)
            cache[key] = mip
            return mip
        except Exception:
            cache[key] = img
            return img

    def clear_mip_cache(self):
        """Clear mip-bias cache (call when textures reload).

        FIX (v10.4): Replace the dict object rather than clearing in-place.
        This ensures that any render-thread snapshot of the old dict is still
        valid (it will just miss new entries), avoiding a race between the
        main-thread clear and a render-thread read.
        """
        self._mip_bias_cache = {}

    def sample(self, img: 'Image.Image', u: float, v: float,
               clamp_s: bool = False, clamp_t: bool = False) -> Tuple[int,int,int]:
        """Sample texture at UV (tiled/wrapped). Returns (r, g, b).

        KotOR MDX UVs follow Direct3D convention: V=0 = texture TOP.
        Our PIL Images are bottom-up (row 0 = bottom of texture).
        Flip: tex_row = (1-v_tiled)*h → V=0 maps to last row (top), V=1 to row 0 (bottom).

        Tiling: values outside [0, 1] are wrapped via % 1.0.  Values *inside*
        [0, 1] – including the boundary v=1.0 – are kept as-is so that
        v=1.0 (OpenGL top edge) correctly maps to PIL row 0.
        Bug-fix: the old code applied % unconditionally, which collapsed v=1.0
        to 0.0 (same as v=0.0, the bottom edge) and returned the wrong row.

        clamp_s / clamp_t: when True, implement GL_CLAMP_TO_EDGE on the
        corresponding axis (i.e. clamp UV to [0,1] instead of wrapping).
        Used for TXI 'clamp' textures (e.g. all KotOR head/face textures).
        """
        if img is None:
            return (128, 128, 128)
        w, h = img.size
        # U axis: GL_REPEAT (wrap) or GL_CLAMP_TO_EDGE
        if clamp_s:
            u_frac = max(0.0, min(1.0, u))
            px = min(w - 1, int(u_frac * w))
        else:
            u_frac = u % 1.0
            px = int(u_frac * w) % w
        # V axis: GL_REPEAT (wrap) or GL_CLAMP_TO_EDGE
        if clamp_t:
            v_tiled = max(0.0, min(1.0, v))
        elif v < 0.0 or v > 1.0:
            # Tile V only when outside [0, 1] to preserve the v=1.0 → row-0 mapping.
            v_tiled = v % 1.0
        else:
            v_tiled = v
        # V-flip: OpenGL V=0 → PIL row h-1; V=1 → PIL row 0.
        py = max(0, min(h - 1, int((1.0 - v_tiled) * h)))
        try:
            pixel = img.getpixel((px, py))
            if len(pixel) >= 3:
                return (pixel[0], pixel[1], pixel[2])
            return (pixel[0], pixel[0], pixel[0])
        except Exception:
            return (128, 128, 128)

    def sample_bilinear(self, img: 'Image.Image', u: float, v: float,
                         clamp_s: bool = False, clamp_t: bool = False) -> Tuple[int,int,int,int]:
        """
        Bilinear-filtered texture sample. Returns (r, g, b, a) for correct alpha blending.

        Uses the same V-flip as sample(): v=0 (D3D top) → row h-1 (top of
        bottom-up image); v=1 (D3D bottom) → row 0 (bottom of bottom-up image).
        V tiling only applied outside [0,1] so that v=1.0 stays at row 0
        rather than collapsing to v=0.0.

        clamp_s / clamp_t: GL_CLAMP_TO_EDGE on U/V axis respectively.
        When set, the UV is clamped to [0,1] before sampling instead of
        wrapping.  Neighbour pixels (x1/y1) are also clamped to prevent
        bilinear from reading across the edge boundary.
        """
        if img is None:
            return (128, 128, 128, 255)
        w, h = img.size
        # U axis: GL_REPEAT or GL_CLAMP_TO_EDGE
        if clamp_s:
            u_clamped = max(0.0, min(1.0, u))
            u_f = u_clamped * w
        else:
            u_f = (u % 1.0) * w
        # V axis: GL_REPEAT or GL_CLAMP_TO_EDGE
        if clamp_t:
            v_tiled = max(0.0, min(1.0, v))
        elif v < 0.0 or v > 1.0:
            # Tile V only when outside [0, 1] (preserve v=1.0 → top-row boundary).
            v_tiled = v % 1.0
        else:
            v_tiled = v
        # V-flip: V=0 (OpenGL bottom) → row h-1; V=1 → row 0.
        v_f = (1.0 - v_tiled) * h
        x0 = int(u_f) % w
        y0 = max(0, min(h - 1, int(v_f)))
        # Neighbour pixels: clamp to edge instead of wrapping for clamped axes
        if clamp_s:
            x1 = min(w - 1, x0 + 1)
        else:
            x1 = (x0 + 1) % w
        if clamp_t:
            y1 = min(h - 1, y0)  # don't step past edge
        else:
            y1 = min(h - 1, y0 + 1)
        fx = u_f - int(u_f)
        fy = v_f - int(v_f)
        try:
            c00 = img.getpixel((x0, y0))
            c10 = img.getpixel((x1, y0))
            c01 = img.getpixel((x0, y1))
            c11 = img.getpixel((x1, y1))
            # Ensure all pixels have 4 components
            def _rgba(p):
                if len(p) == 4: return p
                if len(p) == 3: return (p[0], p[1], p[2], 255)
                return (p[0], p[0], p[0], 255)
            c00, c10, c01, c11 = _rgba(c00), _rgba(c10), _rgba(c01), _rgba(c11)
            r = int(_lerp(_lerp(c00[0], c10[0], fx), _lerp(c01[0], c11[0], fx), fy))
            g = int(_lerp(_lerp(c00[1], c10[1], fx), _lerp(c01[1], c11[1], fx), fy))
            b = int(_lerp(_lerp(c00[2], c10[2], fx), _lerp(c01[2], c11[2], fx), fy))
            a = int(_lerp(_lerp(c00[3], c10[3], fx), _lerp(c01[3], c11[3], fx), fy))
            return (_clamp(r,0,255), _clamp(g,0,255), _clamp(b,0,255), _clamp(a,0,255))
        except Exception:
            return self.sample(img, u, v) + (255,)


# ─────────────────────────────────────────────────────────────────────
#  Triangle rasterizer helper  (KotOR shader-accurate)
# ─────────────────────────────────────────────────────────────────────

def _rasterize_triangle_textured(pixels, W, H, z_buf,
                                  p0, p1, p2,
                                  uv0, uv1, uv2,
                                  n0, n1, n2,
                                  tex_img, tex_cache,
                                  light_dir, eye_dir,
                                  diffuse_color, ambient_color,
                                  specular_col, shininess,
                                  selfillum,
                                  alpha,
                                  shade_mode):
    """
    Software rasterizes a single triangle with KotOR-accurate shading:
    - Affine UV interpolation
    - Per-vertex normal Gouraud shading
    - Phong specular (approximated)
    - Self-illumination color (additive)
    - Alpha transparency (written to pixels directly – no true blending in SW rasterizer)
    - Depth buffer test

    p0,p1,p2 = (sx, sy, depth)  screen pixels + depth
    uv0,uv1,uv2 = (u, v) texture coords
    n0,n1,n2 = (nx, ny, nz) vertex normals in world space
    selfillum = (r,g,b) 0..1 self-illumination color
    alpha     = float 0..1 opacity
    """
    x0, y0, d0 = p0
    x1, y1, d1 = p1
    x2, y2, d2 = p2

    min_x = max(0, min(x0, x1, x2))
    max_x = min(W-1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(H-1, max(y0, y1, y2))

    if min_x > max_x or min_y > max_y:
        return

    denom = (y1 - y2)*(x0 - x2) + (x2 - x1)*(y0 - y2)
    if abs(denom) < 0.5:
        return

    inv_denom = 1.0 / denom
    si_r, si_g, si_b = selfillum

    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            w0 = ((y1 - y2)*(px - x2) + (x2 - x1)*(py - y2)) * inv_denom
            w1 = ((y2 - y0)*(px - x2) + (x0 - x2)*(py - y2)) * inv_denom
            w2 = 1.0 - w0 - w1

            if w0 < 0 or w1 < 0 or w2 < 0:
                continue

            depth = w0*d0 + w1*d1 + w2*d2
            buf_idx = py * W + px
            if depth >= z_buf[buf_idx]:
                continue
            z_buf[buf_idx] = depth

            u = w0*uv0[0] + w1*uv1[0] + w2*uv2[0]
            v = w0*uv0[1] + w1*uv1[1] + w2*uv2[1]

            nx = w0*n0[0] + w1*n1[0] + w2*n2[0]
            ny = w0*n0[1] + w1*n1[1] + w2*n2[1]
            nz = w0*n0[2] + w1*n1[2] + w2*n2[2]
            nl = math.sqrt(nx*nx + ny*ny + nz*nz)
            if nl > 1e-9:
                nx /= nl; ny /= nl; nz /= nl

            # KotOR lighting: ambient + diffuse (two-sided)
            ndotl = nx*light_dir[0] + ny*light_dir[1] + nz*light_dir[2]
            ndotl_pos = max(0.0, ndotl)
            ndotl_neg = max(0.0, -ndotl) * 0.35   # back-face fill (KotOR uses ~35%)
            ndotl_f   = ndotl_pos + ndotl_neg

            # Blinn-Phong specular
            spec = 0.0
            if shininess > 0.5 and ndotl_pos > 0:
                hx = light_dir[0] + eye_dir[0]
                hy = light_dir[1] + eye_dir[1]
                hz = light_dir[2] + eye_dir[2]
                hl = math.sqrt(hx*hx + hy*hy + hz*hz)
                if hl > 1e-9:
                    hx /= hl; hy /= hl; hz /= hl
                ndoth = max(0.0, nx*hx + ny*hy + nz*hz)
                spec = ndoth ** min(shininess * 2.0, 128.0)

            shade = ambient_color + (1.0 - ambient_color) * ndotl_f

            if tex_img is not None:
                tr, tg, tb, ta = tex_cache.sample_bilinear(tex_img, u, v)
                # Skip fully transparent pixels
                if ta < 8:
                    continue
                # Modulate: texture × lighting
                r = int(_clamp(tr * shade + specular_col * spec * 255
                               + si_r * 255, 0, 255))
                g = int(_clamp(tg * shade + specular_col * spec * 255
                               + si_g * 255, 0, 255))
                b = int(_clamp(tb * shade + specular_col * spec * 255
                               + si_b * 255, 0, 255))
            else:
                r = int(_clamp(diffuse_color[0] * shade * 255
                               + specular_col * spec * 255 + si_r * 255, 0, 255))
                g = int(_clamp(diffuse_color[1] * shade * 255
                               + specular_col * spec * 255 + si_g * 255, 0, 255))
                b = int(_clamp(diffuse_color[2] * shade * 255
                               + specular_col * spec * 255 + si_b * 255, 0, 255))

            pixels[px, py] = (r, g, b)


# ─────────────────────────────────────────────────────────────────────
#  Colour constants
# ─────────────────────────────────────────────────────────────────────

_BG      = (18,  18, 40,  255)
_GRID    = (45,  45, 90,  255)
_WIRE    = (100,100,200, 255)
_BONE    = (255,170,  0, 255)
_SEL     = (0,  255,170, 255)
_AXIS_X  = (255, 80, 80, 255)
_AXIS_Y  = (80, 255, 80, 255)
_AXIS_Z  = (80, 140,255, 255)


def _rgb_str_to_tuple(s: str):
    s = s.lstrip('#')
    return int(s[0:2],16), int(s[2:4],16), int(s[4:6],16)


def _paste_textured_triangle(
        img: 'Image.Image',
        tex_img: 'Image.Image',
        sp0, sp1, sp2,          # screen pixel coords (int sx, int sy)
        uv0, uv1, uv2,          # (u, v) 0..1
        W: int, H: int,
        shade_color: tuple,
        sel_brightness: int = 0,  # extra brightness for selected triangles (0=none, 50=normal sel)
        node_alpha: float = 1.0,  # per-node alpha (0=fully transparent, 1=opaque)
        is_additive: bool = False,  # TXI blending=1 → additive screen-space blend
        skip_seam_fix: bool = False,  # legacy combined flag (deprecated, use per-axis below)
        skip_seam_u: bool = False,   # True → bypass U-axis seam fix
        skip_seam_v: bool = False,   # True → bypass V-axis seam fix
        clamp_s: bool = False,       # True → GL_CLAMP_TO_EDGE on U axis (TXI clamp S bit)
        clamp_t: bool = False,       # True → GL_CLAMP_TO_EDGE on V axis (TXI clamp T bit)
        is_punchthrough: bool = False):  # TXI blending=2 → use texture alpha as binary cutout mask
    """
    Paste a UV-mapped texture triangle onto `img` using PIL's fast PERSPECTIVE
    (projective) transform.

    Steps:
      1. Compute the bounding box of the screen triangle → crop `img` target region
      2. Compute the PERSPECTIVE transform coefficients that map from the bounding-
         box coordinate space to the texture's UV space
      3. Create a mask (1-bit polygon) so only pixels inside the triangle are written
      4. Paste the warped texture patch onto `img` at the correct position

    The shade_color is applied as a per-pixel multiply to simulate lighting.
    """
    if not _PIL or tex_img is None:
        return

    # v6.0 FIX: UV sentinel guard removed.  GL_REPEAT (frac) handles all UV
    # magnitudes.  Only skip if UV contains NaN/Inf (corrupt data).
    try:
        _uv_check = (uv0[0] + uv0[1] + uv1[0] + uv1[1] + uv2[0] + uv2[1])
        if _uv_check != _uv_check:  # NaN check
            return
        if not math.isfinite(_uv_check):  # Inf check
            return
    except (TypeError, IndexError):
        return

    sx0, sy0 = int(sp0[0]), int(sp0[1])
    sx1, sy1 = int(sp1[0]), int(sp1[1])
    sx2, sy2 = int(sp2[0]), int(sp2[1])

    # Bounding box (clipped to viewport)
    bx0 = max(0, min(sx0, sx1, sx2))
    by0 = max(0, min(sy0, sy1, sy2))
    bx1 = min(W - 1, max(sx0, sx1, sx2))
    by1 = min(H - 1, max(sy0, sy1, sy2))
    bw  = bx1 - bx0 + 1
    bh  = by1 - by0 + 1
    if bw <= 0 or bh <= 0:
        return

    # Relative screen corners (in the bounding-box space)
    rx0, ry0 = sx0 - bx0, sy0 - by0
    rx1, ry1 = sx1 - bx0, sy1 - by0
    rx2, ry2 = sx2 - bx0, sy2 - by0

    # ── Compute affine/perspective transform coefficients ──────────────
    # We need to map bounding-box pixel (x, y) → texture pixel (tx, ty)
    # using the 3-point correspondence:
    #   screen (rx0,ry0) → tex (uv0[0]*tw, (1-uv0[1])*th)  [flip V for KotOR]
    #   screen (rx1,ry1) → tex (uv1[0]*tw, (1-uv1[1])*th)
    #   screen (rx2,ry2) → tex (uv2[0]*tw, (1-uv2[1])*th)
    # For PIL Image.transform(AFFINE), the 6 coefficients a,b,c,d,e,f map:
    #   source_x = a*dest_x + b*dest_y + c
    #   source_y = d*dest_x + e*dest_y + f
    # We solve the affine system from the 3-point correspondence.
    tw, th = tex_img.size

    # ── UV coordinate preparation (KotOR-accurate wrapping) ──────────────
    #
    # KotOR MDX stores UVs in Direct3D convention: V=0 is the TOP of the texture.
    # PIL images are bottom-up (row 0 = bottom of texture).  All loaded textures
    # (TPC, TGA, PNG) are flipped to bottom-up orientation by TextureCache.
    # To sample correctly we flip V:
    #   tex_row = (1.0 - v_mdx) * height
    # This maps V=0 (top) → last row (top of bottom-up image)
    #       and V=1 (bottom) → row 0 (bottom of bottom-up image).
    # This flip is applied below as: tv = (1.0 - v_raw) * th
    #
    # Seam crossing fix (applies ONLY when the tri's own UV span ≤ 1 tile):
    # When two UVs in the same triangle straddle a tile boundary (e.g. u0=0.95
    # and u1=0.05) the affine interpolation travels the long way around (0.95→1.5)
    # instead of the short way (0.95→0.05).  Fix: shift u1/u2 to be within ±0.5
    # of u0.  IMPORTANT: only do this when the raw UV span across the triangle is
    # ≤ 0.5 (i.e. the triangle itself does NOT span more than half a tile).  If the
    # triangle intentionally spans multiple tiles (e.g. pelvis_g UV=[-13, +13]) the
    # seam fix must NOT be applied — it would collapse 26 tiles to a 0-span triangle.
    #
    # Tiling fix (applies when any UV is outside [0, 1]):
    # PIL Image.transform(AFFINE) samples the source image using absolute pixel coords
    # and does NOT wrap.  For tiling textures we must either:
    #   (a) Pre-tile the source image to cover the UV range  — expensive for large UVs
    #   (b) Reduce the texture to a thumbnail first, then tile a small image  — fast
    # We choose (b): downscale the source to MAX_TILE_SRC_PX × MAX_TILE_SRC_PX before
    # tiling, cap tiles at MAX_TILE_COUNT×MAX_TILE_COUNT, keep total tiled image under
    # MAX_TILED_PX total pixels.  For very large UV ranges (3dgui pelvis: ±13 tiles)
    # where capping would still mismatch, we fall back to modulo-sampling: reduce all
    # UVs to [0,1] via frac() before computing the affine transform.  This gives the
    # correct tiled appearance (each tile is identical) without memory explosion.

    import math as _tmath

    u0, v0_raw = uv0[0], uv0[1]
    u1_raw, v1_raw_in = uv1[0], uv1[1]
    u2_raw, v2_raw_in = uv2[0], uv2[1]

    # ── TXI Clamp mode (v12.3): GL_CLAMP_TO_EDGE ─────────────────────────────
    # When clamp_s or clamp_t is set (TXI 'clamp' command, e.g. clamp 3 for head
    # textures), we:
    #   1. Force-skip BOTH axes of the seam-crossing fix (clamped textures have no
    #      tiling seam to unwrap — the seam fix would produce incorrect results).
    #   2. Force-skip the tiling path (clamped textures must NOT tile).
    #   3. Clamp UV coordinates to [0, 1] on the relevant axes so that the affine
    #      transform maps to the correct edge texel instead of wrapping.
    # This matches GL_CLAMP_TO_EDGE: sampling beyond [0,1] returns the edge texel.
    if clamp_s or clamp_t:
        skip_seam_fix = True  # disable seam-fix for both axes on clamped textures
        if clamp_s:
            u0      = max(0.0, min(1.0, u0))
            u1_raw  = max(0.0, min(1.0, u1_raw))
            u2_raw  = max(0.0, min(1.0, u2_raw))
        if clamp_t:
            v0_raw    = max(0.0, min(1.0, v0_raw))
            v1_raw_in = max(0.0, min(1.0, v1_raw_in))
            v2_raw_in = max(0.0, min(1.0, v2_raw_in))

    # ── Degenerate-UV skip for clamped textures (v12.5) ─────────────────
    # When clamp_s or clamp_t collapses all 3 UV coordinates on one axis to the
    # SAME value (e.g. all three U vertices clamped to 1.0), the 3×3 affine
    # system is rank-deficient and the transform fills the bounding box with a
    # single texel column/row, producing bright edge-colour stripes.
    # Detection: after clamping, if the UV span on a clamped axis is < 1e-5,
    # the triangle is a hair-thin sliver in UV space → skip it.
    if clamp_s:
        _us_after = (max(0.0, min(1.0, uv0[0])),
                     max(0.0, min(1.0, uv1[0])),
                     max(0.0, min(1.0, uv2[0])))
        if max(_us_after) - min(_us_after) < 1e-5:
            return  # degenerate after U-clamp → skip to avoid stripe artefact
    if clamp_t:
        _vs_after = (max(0.0, min(1.0, uv0[1])),
                     max(0.0, min(1.0, uv1[1])),
                     max(0.0, min(1.0, uv2[1])))
        if max(_vs_after) - min(_vs_after) < 1e-5:
            return  # degenerate after V-clamp → skip to avoid stripe artefact

    # After clamping, v1_raw/v2_raw are the current working copies
    # (they will be overwritten by the seam-fix section or passed through)

    # V-flip scale factors: for non-tiled path these are 1 and th (set after tiling section)
    # For tiled path: _vflip_tiles = tile_v_needed, _vflip_src_h = src_h per tile
    # V-flip formula: tv = (_vflip_tiles - v_shifted) * _vflip_src_h
    # For non-tiled: tv = (1 - v) * th  (same as current formula)
    _vflip_tiles  = None   # set after tiling section
    _vflip_src_h  = None   # set after tiling section
    _tile_src_w   = None   # one-tile pixel width for tiled tu conversion

    # Raw UV span for this triangle (before any seam fix)
    _u_span_raw = max(u0, u1_raw, u2_raw) - min(u0, u1_raw, u2_raw)
    _v_span_raw = max(v0_raw, v1_raw_in, v2_raw_in) - min(v0_raw, v1_raw_in, v2_raw_in)

    # Seam-crossing fix: pull u1/u2 close to u0 so the affine transform goes the
    # SHORT way around the tile boundary rather than the long way.
    #
    # CRITICAL FIX (v5.2): The previous code gated the seam fix on raw_span ≤ 0.6.
    # That is WRONG for the common seam-crossing case (u0=0.95, u1=0.02): the raw
    # span is 0.93 which exceeds 0.6, so the fix was SKIPPED, causing an affine
    # stretch across the full tile width instead of a tiny 0.07-unit triangle.
    #
    # Correct algorithm: apply the fix whenever the triangle fits within ONE tile
    # (raw_span < 1.0) — _uwrap is already smart and only shifts when needed.
    # For intentional tiling meshes (raw_span ≥ 1.0) the fix is skipped because
    # the triangle genuinely spans multiple tiles and we handle those in the
    # tiling section below.  This correctly handles ALL cases:
    #   • Normal [0.2..0.5]: span=0.3 < 1 → _uwrap called, no shift needed
    #   • Seam [0.95, 0.02]: span=0.93 < 1 → _uwrap called, SHIFTS u1 to 1.02 ✓
    #   • Tiling pelvis [-5..+5]: span=10 ≥ 1 → skip, handled by tiling section ✓
    #
    # PERF-FIX (v10.2): _uwrap and _edge_has_seam are now module-level functions
    # (_uwrap_global, _edge_has_seam_global) to avoid re-creating closure objects
    # on every triangle call (~2-3 µs saved per call = ~16-24 ms per 8k-tri frame).

    # ── Seam-crossing fix (v10.4) ────────────────────────────────────────────
    # Uses module-level _uwrap_global / _edge_has_seam_global (defined near top
    # of module) instead of inner closures.  Logic is identical to v10.1.
    #
    # Per-axis seam skip flags.
    # skip_seam_u=True → bypass U-axis seam fix (set when no U-seam vertices exist)
    # skip_seam_v=True → bypass V-axis seam fix (set when no V-seam vertices exist)
    # skip_seam_fix is the legacy combined flag (both axes, kept for backwards compat)
    # These flags are computed per-face using positional duplicate analysis:
    # faces at hair/fin attachment points have U-axis seam verts but no V-seam verts,
    # so only the V fix is skipped, preventing black tip artifacts on hair strands.
    #
    # FAST PATH: If ALL three UV components (u and v) lie strictly within the
    # "safe zone" [0.05, 0.95], no tile boundary can be crossed → skip the entire
    # seam-detection block.  This is true for >80% of KotOR triangles and saves
    # ~1.5 µs per triangle on the common path.
    _skip_u = skip_seam_fix or skip_seam_u
    _skip_v = skip_seam_fix or skip_seam_v
    _U_SEAM_SAFE = _skip_u or (0.05 <= u0 <= 0.95 and
                    0.05 <= u1_raw <= 0.95 and
                    0.05 <= u2_raw <= 0.95)
    _V_SEAM_SAFE = _skip_v or (0.05 <= v0_raw <= 0.95 and
                    0.05 <= v1_raw_in <= 0.95 and
                    0.05 <= v2_raw_in <= 0.95)

    if _U_SEAM_SAFE:
        u1, u2 = u1_raw, u2_raw
    elif _u_span_raw < 1.0:
        u_has_seam = (_edge_has_seam_global(u0, u1_raw) or
                      _edge_has_seam_global(u0, u2_raw) or
                      _edge_has_seam_global(u1_raw, u2_raw))
        if u_has_seam:
            u1_try = _uwrap_global(u0, u1_raw)
            u2_try = _uwrap_global(u0, u2_raw)
            # Wide-triangle guard: accept fix only if it significantly reduces span
            # AND the wrapped UVs stay within (-0.1, 1.1) so PIL AFFINE sampling
            # doesn't hit the transparent fillcolor region more than a tiny fringe.
            # Replaced the old raw_span*0.70-only guard.
            # The old guard incorrectly accepted u=[0.9, 0.1, 0.8] → [0.9, 1.1, 0.8]:
            # new_span=0.30 < 0.80*0.70=0.56 → ACCEPTED → but u1_try=1.1 samples
            # outside the texture (PIL AFFINE → transparent fillcolor at that corner).
            # Strictly requiring u1_try < 1.1 (exclusive) rejects that case because
            # 1.1 is not < 1.1.  All real KotOR seam faces have u_seam_vert < 0.1
            # (i.e. very close to 0) so their wrapped value is > 0.9 + tiny, which
            # is ≤ ~1.03 — well within the (-0.1, 1.1) safe sampling window.
            new_span = max(u0, u1_try, u2_try) - min(u0, u1_try, u2_try)
            _u1_ok = -0.1 < u1_try < 1.1
            _u2_ok = -0.1 < u2_try < 1.1
            if new_span < _u_span_raw * 0.70 and _u1_ok and _u2_ok:
                u1, u2 = u1_try, u2_try
            else:
                u1, u2 = u1_raw, u2_raw
        else:
            u1, u2 = u1_raw, u2_raw
    else:
        u1, u2 = u1_raw, u2_raw

    if _V_SEAM_SAFE:
        v1_raw, v2_raw = v1_raw_in, v2_raw_in
    elif _v_span_raw < 1.0:
        v_has_seam = (_edge_has_seam_global(v0_raw, v1_raw_in) or
                      _edge_has_seam_global(v0_raw, v2_raw_in) or
                      _edge_has_seam_global(v1_raw_in, v2_raw_in))
        if v_has_seam:
            v1_try = _uwrap_global(v0_raw, v1_raw_in)
            v2_try = _uwrap_global(v0_raw, v2_raw_in)
            new_vspan = max(v0_raw, v1_try, v2_try) - min(v0_raw, v1_try, v2_try)
            # Same in-bounds guard as U axis (see U seam fix above)
            _v1_ok = -0.1 < v1_try < 1.1
            _v2_ok = -0.1 < v2_try < 1.1
            if new_vspan < _v_span_raw * 0.70 and _v1_ok and _v2_ok:
                v1_raw, v2_raw = v1_try, v2_try
            else:
                v1_raw, v2_raw = v1_raw_in, v2_raw_in
        else:
            v1_raw, v2_raw = v1_raw_in, v2_raw_in
    else:
        v1_raw, v2_raw = v1_raw_in, v2_raw_in

    u_min = min(u0, u1, u2)
    u_max = max(u0, u1, u2)
    v_min = min(v0_raw, v1_raw, v2_raw)
    v_max = max(v0_raw, v1_raw, v2_raw)

    # ── Tiling for large UV coordinates ──────────────────────────────────
    # IMPORTANT: The seam-unwrap above (_uwrap) may produce UVs outside [0,1]
    # (e.g. u=-0.468 or v=1.851) for triangles that straddle a tile boundary.
    # These are NOT tiling meshes; they are single-tile faces whose UVs have
    # been shifted by the seam fix.
    #
    # The previous position-based tiling check
    #   (u_min < -0.5 or u_max > 1.5 or v_min < -0.5 or v_max > 1.5)
    # incorrectly triggered tiling for seam-corrected faces that have v=1.85
    # (high position, but SMALL span ≈ 0.36).  The tiling path then shifted UVs
    # by the floor of u_min (u_floor = -1), which UNDID the seam fix and caused
    # visible seam-stretch artifacts on n_darthrevan, p_bastilabb, etc.
    #
    # CORRECT ALGORITHM: trigger tiling only when the UV SPAN of the triangle
    # exceeds 1.0 tiles (v12.13: lowered from 1.5 to fix KotOR back-seam triangles
    # with span ≈ 1.36 that were incorrectly falling through to centroid-shift).
    # A triangle with u=[-0.468, 0.030] has span=0.498 < 1.0 → NOT a tiling face.
    # A face with u=[-5, +5] has span=10 > 1.0 → IS a tiling face.
    #
    # For small-span faces that are "shifted" outside [0,1] (v=1.85, u=-0.47),
    # we use a CENTROID INTEGER SHIFT to normalise coordinates while preserving
    # relative UV differences.  This is critical — per-UV frac() was collapsing
    # the seam fix (e.g., u=-0.468 → frac → 0.532 = original value).
    #
    # Strategy:
    #  1. If UV span > 1.0 tiles: activate tiling, down-sample, tile, shift by floor.
    #  2. If UV span ≤ 1.0 tiles but coordinates shifted outside [0,1]:
    #     apply centroid integer shift to bring the centroid into [0,1] while
    #     keeping relative UV differences intact.  This preserves the seam fix.
    #  3. If all UVs already in [0,1]: use texture as-is.

    MAX_TILE_SRC_PX  = 128   # thumbnail side for tiling source; raised 64→128 for better BILINEAR quality
    MAX_TILED_PIXELS = 512 * 512  # 262144 pixels — raised budget for crisp tiled textures
    MAX_TILE_COUNT   = 8     # maximum tiles per axis

    # Use SPAN-based tiling check, not POSITION-based.
    # A face genuinely spans multiple tiles only when max−min > 1.5.
    # The old position-based check (u_min < -0.5 or u_max > 1.5) was triggering
    # tiling for seam-corrected faces (small span, but shifted position), causing
    # the tiling floor-shift to undo the seam correction.
    # Clamped textures must NEVER tile (GL_CLAMP_TO_EDGE → no tiling).
    # Lower tiling threshold from 1.5 → 1.0 (fixes back-seam triangles).
    #   KotOR back-seam triangles (e.g. torso u=[0.003,1.366,0.003], span=1.363)
    #   need 2 tiles to render correctly; with threshold 1.5 they fell through to
    #   the centroid-shift which leaves u_max=1.366 OOB (PIL samples outside the
    #   texture, returning transparent black → dark seam artifact).
    #   Threshold 1.0 means any span > 1 full tile triggers proper tiling. Seam-
    #   corrected faces always have span << 1.0 so this does not affect them.
    u_span_curr = u_max - u_min
    v_span_curr = v_max - v_min
    needs_tiling = (u_span_curr > 1.0 or v_span_curr > 1.0) and not (clamp_s and clamp_t)

    # ── Centroid-integer-shift for seam-corrected and slightly out-of-range faces ──
    # When UVs are outside [0,1] but the span is small (≤ 1.5), the face is a
    # single-tile face whose position has been shifted by seam correction or by
    # the original MDL UV layout.  Apply a whole-tile shift to move the centroid
    # into [0,1], preserving relative UV differences (unlike per-UV frac() which
    # collapses all integer multiples to 0 and destroys the seam fix).
    if not needs_tiling and (u_min < -0.001 or u_max > 1.001 or
                              v_min < -0.001 or v_max > 1.001):
        # Replaced frac_clamp with centroid integer shift.
        # frac() was collapsing seam-corrected UVs (e.g., u=-0.468 → 0.532 = WRONG).
        # Centroid integer shift: shift all UVs by the same integer amount so
        # the centroid falls in [0,1]; relative UV differences preserved.
        u_cen = (u0 + u1 + u2) / 3.0
        v_cen = (v0_raw + v1_raw + v2_raw) / 3.0
        u_int_shift = int(_tmath.floor(u_cen))
        v_int_shift = int(_tmath.floor(v_cen))
        if u_int_shift != 0:
            u0     -= u_int_shift
            u1     -= u_int_shift
            u2     -= u_int_shift
        if v_int_shift != 0:
            v0_raw -= v_int_shift
            v1_raw -= v_int_shift
            v2_raw -= v_int_shift
        # Recompute min/max after centroid shift
        u_min = min(u0, u1, u2)
        u_max = max(u0, u1, u2)
        v_min = min(v0_raw, v1_raw, v2_raw)
        v_max = max(v0_raw, v1_raw, v2_raw)
        # Two-stage secondary correction after centroid shift.
        #
        # Stage A – Integer floor shift (for faces displaced by multiple whole tiles):
        #   floor(-0.006) = -1; subtracting (-1) shifts by +1 tile which is WRONG if
        #   v_max is only 0.17 (result would be 1.17, outside [0,1]).  Guard: only apply
        #   when the shifted max would stay ≤ 1.001.  Handles u_min < -1.0 and v_min < -1.0.
        if u_min < -0.001:
            _u_floor2 = int(_tmath.floor(u_min))
            if _u_floor2 != 0 and (u_max - _u_floor2) <= 1.001:
                u0 -= _u_floor2; u1 -= _u_floor2; u2 -= _u_floor2
                u_min = min(u0, u1, u2); u_max = max(u0, u1, u2)
        if v_min < -0.001:
            _v_floor2 = int(_tmath.floor(v_min))
            if _v_floor2 != 0 and (v_max - _v_floor2) <= 1.001:
                v0_raw -= _v_floor2; v1_raw -= _v_floor2; v2_raw -= _v_floor2
                v_min = min(v0_raw, v1_raw, v2_raw); v_max = max(v0_raw, v1_raw, v2_raw)
        if u_max > 1.001:
            _u_ceil2 = int(_tmath.floor(u_max))
            # Guard: only shift if centroid >= 1 AND span is small.
            # A seam-corrected face (u_cen ≈ 0.987, u_max = 1.01) must NOT be
            # shifted — its centroid is already in [0,1], and shifting would undo
            # the seam fix (u0=0.96 → -0.04, u1=1.01 → 0.01 → WRONG texture area).
            # Only shift when u_cen is itself >= 1 (face is genuinely displaced by
            # more than one full tile, e.g. u_cen = 1.5 needs -1 shift).
            _u_cen_curr = (u0 + u1 + u2) / 3.0
            if _u_ceil2 > 0 and (u_max - u_min) < 0.5 and _u_cen_curr >= 1.0:
                u0 -= _u_ceil2; u1 -= _u_ceil2; u2 -= _u_ceil2
                u_min = min(u0, u1, u2); u_max = max(u0, u1, u2)
        if v_max > 1.001:
            _v_ceil2 = int(_tmath.floor(v_max))
            _v_cen_curr = (v0_raw + v1_raw + v2_raw) / 3.0
            if _v_ceil2 > 0 and (v_max - v_min) < 0.5 and _v_cen_curr >= 1.0:
                v0_raw -= _v_ceil2; v1_raw -= _v_ceil2; v2_raw -= _v_ceil2
                v_min = min(v0_raw, v1_raw, v2_raw); v_max = max(v0_raw, v1_raw, v2_raw)
        # Stage B – Fringe clamp for tiny sub-pixel OOB values (|delta| < 0.05).
        #   After Stage A, a face may still have e.g. v_min = -0.006 because floor(-0.006)=-1
        #   but the guard blocked the +1 shift (v_max would have become 1.17).
        #   These are genuinely near-zero UV values that should be clamped to 0.
        #   Apply a fractional shift of exactly -v_min to bring the minimum to 0,
        #   but only when the fringe is tiny (< 0.05) AND the span stays ≤ 1.001.
        if u_min < -0.001 and u_min > -0.05 and (u_max - u_min) <= 1.001:
            _u_fringe = u_min          # negative, e.g. -0.006
            u0 -= _u_fringe; u1 -= _u_fringe; u2 -= _u_fringe
            u_min = min(u0, u1, u2); u_max = max(u0, u1, u2)
        if v_min < -0.001 and v_min > -0.05 and (v_max - v_min) <= 1.001:
            _v_fringe = v_min          # negative, e.g. -0.006
            v0_raw -= _v_fringe; v1_raw -= _v_fringe; v2_raw -= _v_fringe
            v_min = min(v0_raw, v1_raw, v2_raw); v_max = max(v0_raw, v1_raw, v2_raw)

    if needs_tiling:
        u_floor = int(_tmath.floor(u_min))
        v_floor = int(_tmath.floor(v_min))
        tile_u_needed = int(_tmath.floor(u_max)) - u_floor + 1
        tile_v_needed = int(_tmath.floor(v_max)) - v_floor + 1

        if tile_u_needed <= MAX_TILE_COUNT and tile_v_needed <= MAX_TILE_COUNT:
            # Down-sample source so tiled image fits within budget
            src_w = max(1, min(tw, MAX_TILE_SRC_PX))
            src_h = max(1, min(th, MAX_TILE_SRC_PX))
            tiled_w = src_w * tile_u_needed
            tiled_h = src_h * tile_v_needed
            if tiled_w * tiled_h > MAX_TILED_PIXELS:
                # Further shrink proportionally
                scale = (MAX_TILED_PIXELS / (tiled_w * tiled_h)) ** 0.5
                src_w = max(1, int(src_w * scale))
                src_h = max(1, int(src_h * scale))
                tiled_w = src_w * tile_u_needed
                tiled_h = src_h * tile_v_needed

            try:
                src_rgba = tex_img.convert('RGBA')
                thumb = src_rgba.resize((src_w, src_h),
                                        Image.BOX if hasattr(Image, 'BOX') else Image.NEAREST)
                tiled = Image.new('RGBA', (tiled_w, tiled_h))
                for ti in range(tile_u_needed):
                    for tj in range(tile_v_needed):
                        tiled.paste(thumb, (ti * src_w, tj * src_h))
                tex_img = tiled
                tw, th = tiled_w, tiled_h
                # Shift UVs so u_floor maps to 0
                u0     -= u_floor;  u1     -= u_floor;  u2     -= u_floor
                v0_raw -= v_floor;  v1_raw -= v_floor;  v2_raw -= v_floor
                # Recalculate after shift (u_floor/v_floor now 0)
                u_floor = v_floor = 0
                # V-flip for tiled path: tv = (tile_v_needed - v_shifted) * src_h
                # (linear monotone flip over the full tiled V range; works because
                # all tiles are identical so global flip == per-tile flip visually)
                _vflip_tiles = tile_v_needed
                _vflip_src_h = src_h
                _tile_src_w  = src_w   # needed for correct tu conversion below
            except MemoryError:
                # Fall through to centroid-shift path
                needs_tiling = False
            except Exception:
                needs_tiling = False
        else:
            # UV range too large to tile with pre-tiled image (> MAX_TILE_COUNT tiles).
            # Strategy: apply per-vertex frac() (modulo 1.0) to bring each UV into
            # [0, 1].  This gives correct tiling for all vertices; the only artefact
            # is a potential seam at tile boundaries where the affine interpolates
            # across the frac() discontinuity.  This is far preferable to the previous
            # centroid-shift which only showed the central tile, leaving the rest of
            # the surface solid-colored (edge-stretch on GPU, center-only on CPU).
            # Seams at tile edges are typically much less visible than solid stretching.
            u0     = u0     - _tmath.floor(u0)
            u1     = u1     - _tmath.floor(u1)
            u2     = u2     - _tmath.floor(u2)
            v0_raw = v0_raw - _tmath.floor(v0_raw)
            v1_raw = v1_raw - _tmath.floor(v1_raw)
            v2_raw = v2_raw - _tmath.floor(v2_raw)
            needs_tiling = False

    # ── Flip V for KotOR (MDX stores V=0=top; PIL images are bottom-up) ────
    # All texture images in our system are bottom-up (row 0 = bottom of texture).
    # MDX UVs follow D3D convention: V=0 = texture top.
    # Non-tiled: tex_row = (1 - v) * h  → v=0 maps to row h-1 (top), v=1 to row 0 (bottom).
    # Tiled:     tex_row = (tile_v_needed - v_shifted) * src_h
    #            — a linear global flip over the full tiled V range.  Since all tiles
    #              are identical this produces the same visual result as per-tile flip.
    #            Reduces to (1-v)*h for the single-tile case (tile_v_needed=1, src_h=th).
    # PERF-FIX (v10.2): Use module-level _vflip_nontiled / _vflip_tiled instead of
    # per-call closure definitions (saves ~1 µs / triangle on the closure creation).
    if _vflip_tiles is not None:
        # Tiled path: use tile-aware V-flip
        tv0 = _vflip_tiled(v0_raw, _vflip_tiles, _vflip_src_h)
        tv1 = _vflip_tiled(v1_raw, _vflip_tiles, _vflip_src_h)
        tv2 = _vflip_tiled(v2_raw, _vflip_tiles, _vflip_src_h)
    else:
        # Non-tiled path: standard formula
        tv0 = _vflip_nontiled(v0_raw, th)
        tv1 = _vflip_nontiled(v1_raw, th)
        tv2 = _vflip_nontiled(v2_raw, th)
    # BUG-FIX (Phase 16): after tiling, u is in [0, tile_u] range, NOT [0, 1].
    # Multiplying by tw (=tiled_width = src_w * tile_u) gives values tile_u times
    # too large.  The correct pixel coord is u * src_w (single tile pixel width).
    # Non-tiled path: u is in [0, 1], tw is the original texture width → correct.
    if _tile_src_w is not None:
        tu0 = u0 * _tile_src_w
        tu1 = u1 * _tile_src_w
        tu2 = u2 * _tile_src_w
    else:
        tu0 = u0 * tw
        tu1 = u1 * tw
        tu2 = u2 * tw

    # Solve:  [rx0 ry0 1; rx1 ry1 1; rx2 ry2 1] * [a b c]^T = [tu0 tu1 tu2]
    #   and   [rx0 ry0 1; rx1 ry1 1; rx2 ry2 1] * [d e f]^T = [tv0 tv1 tv2]
    denom = (rx0 * (ry1 - ry2) + rx1 * (ry2 - ry0) + rx2 * (ry0 - ry1))
    if abs(denom) < 0.5:
        return   # degenerate triangle

    inv_d = 1.0 / denom
    a = ((tu0 * (ry1 - ry2) + tu1 * (ry2 - ry0) + tu2 * (ry0 - ry1)) * inv_d)
    b = ((tu0 * (rx2 - rx1) + tu1 * (rx0 - rx2) + tu2 * (rx1 - rx0)) * inv_d)
    c = ((tu0 * (rx1*ry2 - rx2*ry1)
          + tu1 * (rx2*ry0 - rx0*ry2)
          + tu2 * (rx0*ry1 - rx1*ry0)) * inv_d)

    d = ((tv0 * (ry1 - ry2) + tv1 * (ry2 - ry0) + tv2 * (ry0 - ry1)) * inv_d)
    e = ((tv0 * (rx2 - rx1) + tv1 * (rx0 - rx2) + tv2 * (rx1 - rx0)) * inv_d)
    f = ((tv0 * (rx1*ry2 - rx2*ry1)
          + tv1 * (rx2*ry0 - rx0*ry2)
          + tv2 * (rx0*ry1 - rx1*ry0)) * inv_d)

    # ── Warp the texture patch ─────────────────────────────────────────
    try:
        # Skip convert('RGBA') if already RGBA (pre-converted by _get_tex / FrameRenderer._get_tex)
        src_img = tex_img if tex_img.mode == 'RGBA' else tex_img.convert('RGBA')
        patch = src_img.transform(
            (bw, bh),
            Image.AFFINE,
            (a, b, c, d, e, f),
            resample=Image.BILINEAR,  # BILINEAR gives smooth interpolation; eliminates blocky pixels
            fillcolor=(0, 0, 0, 0)   # Transparent black fill: prevents dark fringing at UV seams
        )
    except Exception:
        return

    # Apply lighting modulation (multiply by shade_color) + optional selection brightness
    # PERF-FIX (v10.1): Skip numpy shade modulate when shade is white (255,255,255).
    # For fully-lit faces this saves ~0.07ms/tri (16% of total per-tri cost).
    # Only modulate when shade differs from pure white by > 2 per channel.
    sr = min(255, shade_color[0] + sel_brightness)
    sg = min(255, shade_color[1] + sel_brightness)
    sb = min(255, shade_color[2] + sel_brightness)
    _shade_is_white = (sr >= 253 and sg >= 253 and sb >= 253)
    if not _shade_is_white:
        try:
            import numpy as _np
            arr = _np.array(patch, dtype=_np.uint16)
            arr[:, :, 0] = (arr[:, :, 0] * sr // 255).clip(0, 255)
            arr[:, :, 1] = (arr[:, :, 1] * sg // 255).clip(0, 255)
            arr[:, :, 2] = (arr[:, :, 2] * sb // 255).clip(0, 255)
            patch = Image.fromarray(arr.astype(_np.uint8), 'RGBA')
        except Exception:
            # No numpy: apply color tint via point transform
            def _tint(px, channel):
                sc_ch = [sr, sg, sb][channel]
                return max(0, min(255, px * sc_ch // 255))
            r_lut = [_tint(i, 0) for i in range(256)]
            g_lut = [_tint(i, 1) for i in range(256)]
            b_lut = [_tint(i, 2) for i in range(256)]
            a_lut = list(range(256))
            patch = patch.point(r_lut + g_lut + b_lut + a_lut)

    # ── Triangle mask + alpha composite ──────────────────────────────
    # For fully-opaque node alpha (no transparency) we MUST use a polygon mask
    # rather than the patch's alpha channel.  KotOR DXT5 textures store
    # bump/specular data in the alpha channel — using it as transparency makes
    # character skin appear see-through.  _apply_kotor_alpha already forces
    # alpha=255 for standard textures, but as a belt-and-suspenders fix we also
    # ignore the texture alpha entirely when the node is fully opaque.
    #
    # EXCEPTION: Punchthrough (blending=2) nodes use the texture alpha channel
    # as a binary cutout mask.  _apply_kotor_alpha has already processed the
    # texture so that alpha < threshold → 0 and alpha >= threshold → 255.
    # For these nodes we MUST use the texture alpha (not polygon mask) to
    # achieve correct hair/fur/eye cutout rendering.
    #
    # Only for genuinely transparent nodes (node_alpha < 1) or punch-through
    # (punchthrough blending) do we honour the texture alpha channel.
    #
    # We fall back to the polygon-mask path for additive blending too (which
    # uses a separate mask_arr in numpy) to keep the additive path simple.
    _need_poly_mask = is_additive or (node_alpha >= 0.999 and not is_punchthrough)
    if _need_poly_mask:
        mask = Image.new('L', (bw, bh), 0)
        ImageDraw.Draw(mask).polygon([(rx0, ry0), (rx1, ry1), (rx2, ry2)], fill=255)
        if node_alpha < 0.999:
            alpha_val = int(_clamp(node_alpha * 255, 0, 255))
            try:
                import numpy as _np2
                ma = _np2.array(mask, dtype=_np2.uint16)
                mask = Image.fromarray((ma * alpha_val // 255).astype(_np2.uint8), 'L')
            except Exception:
                mask = mask.point(lambda p: p * alpha_val // 255)
    else:
        # Transparent node: use patch alpha (may contain punchthrough cutout data)
        # patch.split()[3] returns the A channel as an 'L' image.
        # fillcolor=(0,0,0,0) ensures pixels outside the UV triangle have alpha=0.
        mask = patch.split()[3]
        if node_alpha < 0.999:
            alpha_val = int(_clamp(node_alpha * 255, 0, 255))
            try:
                import numpy as _np2
                ma = _np2.array(mask, dtype=_np2.uint16)
                mask = Image.fromarray((ma * alpha_val // 255).clip(0, 255).astype(_np2.uint8), 'L')
            except Exception:
                mask = mask.point(lambda p: p * alpha_val // 255)

    # Composite the patch onto the output image.
    # PERF-FIX (v10.1): Use RGBA-canvas fast path when img is RGBA.
    # img.paste(patch, (x,y), mask) uses PIL's built-in alpha composite which
    # avoids the crop()+convert(RGBA)+composite()+convert(RGB) chain that called
    # convert() 4 times per triangle (~0.04ms/tri saved = 8% speedup).
    if is_additive:
        # Additive blending: dst = clamp(dst + src * mask_alpha/255)
        # Simulates OpenGL GL_ONE + GL_ONE blending used for fire/glow/FX in KotOR.
        # Unlike alpha blending (which darkens with low alpha), additive blending
        # brightens the background — correct for particle effects and energy weapons.
        try:
            import numpy as _np
            bg_crop  = img.crop((bx0, by0, bx1 + 1, by1 + 1))
            bg_arr   = _np.array(bg_crop.convert('RGBA'), dtype=_np.uint16)
            src_arr  = _np.array(patch,    dtype=_np.uint16)
            mask_arr = _np.array(mask,     dtype=_np.uint16)
            weight = mask_arr[:, :, _np.newaxis]           # (H,W,1)
            added = bg_arr[:,:,:3] + (src_arr[:,:,:3] * weight // 255)
            added = added.clip(0, 255).astype(_np.uint8)
            if img.mode == 'RGBA':
                out_arr = _np.array(bg_crop.convert('RGBA'), dtype=_np.uint8)
                out_arr[:,:,:3] = added
                img.paste(Image.fromarray(out_arr, 'RGBA'), (bx0, by0))
            else:
                img.paste(Image.fromarray(added, 'RGB'), (bx0, by0))
        except Exception:
            # Numpy unavailable: fall back to normal alpha composite
            bg_crop = img.crop((bx0, by0, bx1 + 1, by1 + 1)).convert('RGBA')
            composited = Image.composite(patch, bg_crop, mask)
            img.paste(composited.convert('RGB'), (bx0, by0))
    elif img.mode == 'RGBA':
        # Fast path: RGBA canvas — direct paste with mask (no crop/composite needed)
        img.paste(patch, (bx0, by0), mask)
    else:
        # RGB canvas fallback: crop → composite → paste
        bg_crop = img.crop((bx0, by0, bx1 + 1, by1 + 1)).convert('RGBA')
        composited = Image.composite(patch, bg_crop, mask)
        img.paste(composited.convert('RGB'), (bx0, by0))


def _paste_lightmap_triangle(
        img: 'Image.Image',
        lm_img: 'Image.Image',
        sp0, sp1, sp2,
        lm_uv0, lm_uv1, lm_uv2,
        W: int, H: int) -> None:
    """
    Multiply-blend a lightmap texture triangle onto `img`.

    KotOR uses a classic two-texture lightmap bake:
      final_rgb = diffuse_rgb * lightmap_rgb * 2.0  (clamped to 255)

    The factor 2.0 matches KotOR's "overbright" lightmaps: a neutral
    mid-grey 0x7F7F7F lightmap leaves the surface unchanged; bright
    patches boost it; dark patches dim it.

    Steps:
      1. Warp the lightmap using the same affine method as
         _paste_textured_triangle, but with V-flip (KotOR LM UVs are
         OpenGL-convention V=0=bottom, same as diffuse UVs).
      2. Build a triangle mask.
      3. Read diffuse pixels from `img`, multiply by lightmap, paste back.
    """
    if not _PIL or lm_img is None:
        return
    # v6.0 FIX: Lightmap UV sentinel removed. frac() handles all magnitudes.
    try:
        _lm_check = (lm_uv0[0] + lm_uv0[1] + lm_uv1[0] + lm_uv1[1] + lm_uv2[0] + lm_uv2[1])
        if _lm_check != _lm_check:  # NaN check
            return
        if not math.isfinite(_lm_check):  # Inf check
            return
    except (TypeError, IndexError):
        return

    sx0, sy0 = int(sp0[0]), int(sp0[1])
    sx1, sy1 = int(sp1[0]), int(sp1[1])
    sx2, sy2 = int(sp2[0]), int(sp2[1])

    bx0 = max(0, min(sx0, sx1, sx2))
    by0 = max(0, min(sy0, sy1, sy2))
    bx1 = min(W - 1, max(sx0, sx1, sx2))
    by1 = min(H - 1, max(sy0, sy1, sy2))
    bw = bx1 - bx0 + 1
    bh = by1 - by0 + 1
    if bw <= 0 or bh <= 0:
        return

    rx0, ry0 = sx0 - bx0, sy0 - by0
    rx1, ry1 = sx1 - bx0, sy1 - by0
    rx2, ry2 = sx2 - bx0, sy2 - by0

    tw, th = lm_img.size
    # Lightmap UVs: same OpenGL convention as diffuse — V=0=bottom. Apply V-flip.
    tu0 = lm_uv0[0] * tw;  tv0 = (1.0 - lm_uv0[1]) * th
    tu1 = lm_uv1[0] * tw;  tv1 = (1.0 - lm_uv1[1]) * th
    tu2 = lm_uv2[0] * tw;  tv2 = (1.0 - lm_uv2[1]) * th

    denom = (rx0*(ry1-ry2) + rx1*(ry2-ry0) + rx2*(ry0-ry1))
    if abs(denom) < 0.5:
        return

    inv_d = 1.0 / denom
    a = ((tu0*(ry1-ry2) + tu1*(ry2-ry0) + tu2*(ry0-ry1)) * inv_d)
    b = ((tu0*(rx2-rx1) + tu1*(rx0-rx2) + tu2*(rx1-rx0)) * inv_d)
    c = ((tu0*(rx1*ry2-rx2*ry1) + tu1*(rx2*ry0-rx0*ry2) + tu2*(rx0*ry1-rx1*ry0)) * inv_d)
    d_c = ((tv0*(ry1-ry2) + tv1*(ry2-ry0) + tv2*(ry0-ry1)) * inv_d)
    e = ((tv0*(rx2-rx1) + tv1*(rx0-rx2) + tv2*(rx1-rx0)) * inv_d)
    f = ((tv0*(rx1*ry2-rx2*ry1) + tv1*(rx2*ry0-rx0*ry2) + tv2*(rx0*ry1-rx1*ry0)) * inv_d)

    try:
        lm_src = lm_img.convert('RGB')
        lm_patch = lm_src.transform(
            (bw, bh), Image.AFFINE, (a, b, c, d_c, e, f),
            resample=Image.BILINEAR, fillcolor=(127, 127, 127)
        )
    except Exception:
        return

    mask = Image.new('L', (bw, bh), 0)
    ImageDraw.Draw(mask).polygon(
        [(rx0, ry0), (rx1, ry1), (rx2, ry2)], fill=255
    )

    # Overbright multiply: final = clamp(diffuse * lightmap * 2 / 255)
    try:
        import numpy as _np
        bg_arr  = _np.array(img.crop((bx0, by0, bx1+1, by1+1)).convert('RGB'),
                            dtype=_np.uint32)
        lm_arr  = _np.array(lm_patch, dtype=_np.uint32)
        msk_arr = _np.array(mask,     dtype=_np.float32) / 255.0

        blended = ((bg_arr * lm_arr * 2) // 255).clip(0, 255)
        result  = (blended.astype(_np.float32) * msk_arr[:,:,_np.newaxis]
                   + bg_arr.astype(_np.float32) * (1.0 - msk_arr[:,:,_np.newaxis])
                   ).clip(0, 255).astype(_np.uint8)
        img.paste(Image.fromarray(result, 'RGB'), (bx0, by0))
    except Exception:
        pass  # lightmap failure is non-fatal; diffuse already rendered


class FrameRenderer:

    MAX_TRIS = 80_000           # Performance cap for painter's sort mode (flat/solid)
    MAX_TRIS_TEXTURED = 5_000   # Textured mode cap — PIL AFFINE per triangle is slow.
                                 # Benchmarks on typical KotOR-sized triangles (~30-40px):
                                 #   146µs/tri → 5000-tri frame ≈ 730ms (~1.4 fps)
                                 #   Raised 2000→5000: better coverage for character models
                                 #   (sith praetorian has 2845 renderable tris — was clipping).
                                 # When accel.py is available (NumPy/Numba), this is
                                 # raised at runtime to MAX_TRIS_TEXTURED_ACCEL.
                                 # _do_render auto-reduces further on MemoryError.
    MAX_TRIS_TEXTURED_ACCEL = 10_000  # Cap when Numba/NumPy accel available (~17-40x speedup)
    MAX_TRIS_TEXTURED_STILL = 50_000  # No-cap for still/offline renders (render_still())
    MAX_TRIS_INTERACTIVE = 10_000  # Reduced cap during mouse drag for fast response
    # Z-epsilon: faces whose back-to-front depths differ by less than this amount
    # are coplanar-candidates; we nudge the sort key by face-index to break ties
    # deterministically and eliminate Z-fighting flicker between coplanar surfaces.
    _DEPTH_EPSILON = 0.0001
    # UE FIXED_VERTEX_INDEX pattern: dangly constraint threshold above which a
    # vertex is considered "pinned" (fully attached, not subject to cloth sim).
    # KotOR stores constraint as a float 0.0 (free) to 1.0 (pinned).
    # Mirrored from UE5 SkeletalRenderCPUSkin.cpp FIXED_VERTEX_INDEX = 0xFFFF.
    _DANGLY_PIN_THRESHOLD: float = 0.999

    def __init__(self, camera: ArcBallCamera):
        self.cam            = camera
        self.model: Optional[KotorModel] = None
        self.show_bones     = True
        self.show_wireframe = False
        self.show_solid     = True
        self.show_grid      = True
        self.show_texture   = False   # Toggle textured rendering
        self.is_interactive = False   # True while mouse dragged (enable LOD)
        # FIX (v10.4): Explicitly declare _lq_tex_mode in __init__ so that
        # getattr(self, '_lq_tex_mode', False) is never needed; the attribute
        # is always present and won't be left stale across model reloads.
        self._lq_tex_mode: bool = False
        self.selected_node: Optional[ModelNode] = None
        self.textures: Dict[str, 'Image.Image'] = {} if _PIL else {}
        self.tex_cache = TextureCache()
        self._wt_cache: Dict[int, tuple] = {}   # node id → (wp, wo, is_id)
        # Bone screen positions for click/hover selection
        self._bone_screen_positions: List[Tuple] = []  # [(sx,sy,depth,node), ...]
        self._hovered_bone: Optional[ModelNode] = None
        # ── Rig-edit mode (Phase 22) ─────────────────────────────────────────
        # When True the renderer draws an orange "Rig Edit Mode" banner and
        # colours adjustable bone joints orange so the user knows they're live.
        self.rig_edit_mode: bool = False
        # Callback invoked after a bone joint is dragged in rig-edit mode:
        #   on_bone_moved(node_name: str, new_pos: tuple)
        self.on_bone_moved = None
        self._outlier_skin_nodes: set = set()   # node ids to skip (accessory model proxies)
        self._outlier_model_id: int = -1            # id() of model for which outliers were computed

        # ── Acceleration layer caches (v10.5) ────────────────────────────────
        # TexArrayCache converts PIL → NumPy RGBA arrays for the accel rasterizer,
        # with LRU eviction to bound memory.  When accel is unavailable this is a
        # no-op stub, so all downstream code can call .get() unconditionally.
        self._tex_arr_cache = _TexArrayCache(max_entries=256)
        # Raise the textured triangle cap when fast rasterizer is available.
        # PIL AFFINE: 187 µs/tri → 2 k cap.  NumPy/Numba: 5–11 µs/tri → 10 k cap.
        if _ACCEL_AVAILABLE:
            self.__class__.MAX_TRIS_TEXTURED = self.__class__.MAX_TRIS_TEXTURED_ACCEL

        # ── Render-bounds cache ───────────────────────────────────────────────
        # render_bounds() is O(N*verts) — cache it per model, only recompute when
        # the model identity changes.  Called every frame from _draw_stats() so
        # without caching this adds 8–20 ms overhead per frame on large models.
        self._render_bounds_cache: Optional[tuple] = None   # ((min), (max)) or None
        self._render_bounds_model_id: int = -1

        # ── LOD hysteresis ───────────────────────────────────────────────────
        # UE-inspired: prevent rapid triangle-budget oscillation when the model
        # sits right at the boundary between two LOD tiers.  We only update the
        # current LOD cap when the newly computed cap differs from the previous
        # one by more than _LOD_HYSTERESIS_FRAC of MAX_TRIS.  This eliminates
        # the flickering "LOD pop" artefact where the budget oscillates between
        # e.g. 40 k and 50 k triangles every other frame.
        # Reference: UE ComputeLODForMeshes / USkinnedMeshComponent::UpdateLODStatus
        self._lod_prev_cap: int = self.MAX_TRIS   # last committed triangle cap
        self._LOD_HYSTERESIS_FRAC: float = 0.10   # 10% dead-band

        # KotOR-accurate lighting (two-light rig matching Odyssey engine)
        # Key light from upper-right, fill from left
        self._light_dir  = _normalize((0.55, 0.40, 0.90))  # main key light (upper right)
        self._light_dir2 = _normalize((-0.35, -0.20, 0.60)) # fill light (left)
        self._ambient    = 0.38   # raised v12.14: brighter ambient for low-RGB creature textures
        self._specular   = 0.10
        self._shininess  = 20.0

        # Animation pose (set by AnimationsPanel)
        self._anim_pose = None   # Optional[AnimPose]
        self._anim_name: str = ""   # current animation name for HUD display
        self._anim_time: float = 0.0   # current animation time for HUD display
        self._anim_length: float = 0.0  # current animation length for HUD display
        # FIX-SKIN-ANIM-D3: Base pose (t=0) for GPU skinning bind reference.
        # When a new animation starts, the caller should set this via
        # set_anim_base_pose().  The GPU renderer uses it as:
        #   M_skin = world_anim(t) * inv(world_anim(t=0))
        self._anim_base_pose = None  # Optional[AnimPose]
        # Per-pose bone-transform cache: reused across all skin nodes in one frame
        self._bone_transforms_cache: Optional[Dict] = None
        self._bone_transforms_pose_id: int = -1
        # ── Dangly mesh Verlet cloth simulators (Phase 4.6) ────────────────
        # Maps node id() → DanglySimulator.  Created lazily on first animation tick.
        self._dangly_sims: Dict[int, 'DanglySimulator'] = {}
        self._dangly_last_time: float = 0.0   # wall-clock time of last sim step

        # ── Gimbal / transform overlay ────────────────────────────────
        # gimbal_mode: 0=none, 1=translate, 2=rotate
        self.gimbal_mode: int = 1
        self.show_gimbal: bool = True
        self.gimbal_active_axis = None          # axis being dragged ('X','Y','Z',etc.) or None
        self._gimbal_handles: List[Tuple] = []  # [(sx,sy,axis), ...] from last draw
        # External skeleton overlay (ghost from another model)
        self._ext_skeleton = None               # KotorModel or None
        self._ext_skel_offset: List[float] = [0.0, 0.0, 0.0]
        # ── Walkmesh overlay (Phase 9 / Phase 16.1) ───────────────────────────
        # Loaded separately via load_walkmesh() (co-load with MDL when WOK found).
        # show_walkmesh toggles visibility; show_walkmesh_nonwalk shows blockers.
        self.show_walkmesh:       bool = False
        self.show_walkmesh_walk:  bool = True   # show walkable surfaces
        self.show_walkmesh_block: bool = True   # show non-walkable blockers
        self._walkmesh_overlay: Optional['WalkmeshOverlay'] = None

    def set_anim_base_pose(self, base_pose):
        """Set the animation's first-frame (t=0) pose for GPU skinning.

        FIX-SKIN-ANIM-D3: The GPU skinning palette needs the animation's
        t=0 pose as the bind reference (xoreos approach).  Call this once
        when a new animation starts, before the first set_animation_pose().
        """
        self._anim_base_pose = base_pose

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0):
        """Set the animation pose for rendering. Pass None to clear (bind pose).

        When an animated pose is supplied, advances all DanglySimulators by the
        wall-clock time since the previous call so cloth/chain nodes oscillate
        live during animation playback.  (Phase 4.6 — Dangly Verlet wiring.)
        """
        import time as _time_mod
        now = _time_mod.perf_counter()

        # Advance dangly simulators when we have an active pose and a model
        if pose is not None and self.model is not None and DanglySimulator is not None:
            if self._dangly_last_time <= 0.0:
                # First tick — initialise so we don’t get a huge dt on the second
                self._dangly_last_time = now
                dt = 0.0
            else:
                dt = now - self._dangly_last_time
            self._dangly_last_time = now

            if dt > 0.0:
                for n in self.model.all_nodes():
                    if not n.is_dangly or not n.vertices:
                        continue
                    nid = id(n)
                    if nid not in self._dangly_sims:
                        try:
                            self._dangly_sims[nid] = DanglySimulator(n)
                        except Exception:
                            continue
                    try:
                        self._dangly_sims[nid].step(dt)
                    except Exception:
                        pass
        elif pose is None:
            # Pose cleared — reset simulators to bind pose
            for sim in self._dangly_sims.values():
                try:
                    sim.reset()
                except Exception:
                    pass
            self._dangly_last_time = 0.0

        self._anim_pose = pose
        self._anim_name = name
        self._anim_time = time
        self._anim_length = length
        # FIX-SKIN-ANIM-D3: Clear base pose when animation is cleared.
        if pose is None:
            self._anim_base_pose = None
        self._wt_cache.clear()  # force re-evaluation with new pose
        # Invalidate per-pose bone-transforms cache
        self._bone_transforms_cache = None
        self._bone_transforms_pose_id = -1
        # Ensure next frame renders at full quality (not LOD/interactive mode)
        self.is_interactive = False
        # Request a redraw so every animation frame is actually rendered.
        # Without this the viewport only redraws on the next idle 33 ms tick,
        # causing animation to appear frozen or heavily frame-dropped.
        # Use getattr for safe call — FrameRenderer may be instantiated standalone
        # (e.g. in unit tests) without the ModelViewport parent widget that owns
        # _request_render().  In that case silently skip the redraw request.
        _req = getattr(self, '_request_render', None)
        if _req is not None:
            try:
                _req(fast=True)
            except Exception:
                pass

    # ── Base skeleton names (supermodels that ARE the main skeleton) ──────
    # Use the shared KOTOR_BASE_SKELETONS constant from model_data to ensure
    # consistent behaviour across viewport rendering, compute_bounds, and render_bounds.
    _BASE_SKELETONS = KOTOR_BASE_SKELETONS

    def set_model(self, m: Optional[KotorModel]):
        self.model = m
        self._wt_cache: Dict[int, tuple] = {}   # node id → (wp, wo, is_id)
        self._cached_model_id = id(m) if m else -1  # track for cache invalidation
        self._anim_pose = None   # clear animation pose when model changes
        self._bone_transforms_cache = None   # invalidate bone-transform cache
        self._bone_transforms_pose_id = -1
        self._outlier_skin_nodes: set = set()   # node ids to skip for accessory models
        # Clear dangly simulators: new model may have different nodes
        self._dangly_sims = {}
        self._dangly_last_time = 0.0
        # Invalidate render-bounds cache
        self._render_bounds_cache = None
        self._render_bounds_model_id = id(m) if m else -1
        # Reset LOD hysteresis so the new model gets a fresh cap evaluation
        self._lod_prev_cap = self.MAX_TRIS
        # FIX (v10.4): Reset _lq_tex_mode on model change so a stale LQ flag
        # from a previous drag cannot survive into the new model's first render.
        self._lq_tex_mode = False
        # v20: Reset model-scale bounding diagonal (used by LBS explosion guard).
        # Must be cleared on model change so the new model's size is recomputed.
        self._lbs_model_diag = None
        # Compute skin-proxy node id set for deformation-helper detection.
        # Non-skin nodes whose texture has an exclusive skin-mesh counterpart
        # (exactly 1 skin mesh uses that texture in the whole model) are deformation
        # reference proxies — they should not render separately.
        self._skin_proxy_ids: set = set()
        if m is not None:
            self._skin_proxy_ids = self._compute_skin_proxy_ids(m)
        # Clear per-model texture dict so stale PIL images from the previous
        # model don't linger (stale RGBA-converted refs waste memory and can
        # shadow newly loaded textures after a tex_cache clear).
        self.textures.clear()
        # Clear mip-bias cache (old texture images may be replaced)
        self.tex_cache.clear_mip_cache()
        # Clear TexArrayCache so stale PIL→NumPy conversions are evicted (v10.5)
        self._tex_arr_cache.clear()
        if m:
            # Use render_bounds (visible nodes only) for camera framing so that
            # deformation-helper skeleton meshes don't push the camera too far back.
            rbb_min, rbb_max = m.render_bounds()
            # Cache the result immediately so _draw_stats() doesn't recompute it
            self._render_bounds_cache = (rbb_min, rbb_max)
            self.cam.frame_bounds(rbb_min, rbb_max)
            # Pre-compute outlier skin nodes for accessory models (e.g. ad_saul)
            self._compute_outlier_skin_nodes(m)
            # Load and apply TXI metadata for all mesh nodes
            # This populates txi_blending, txi_cube, txi_proceduretype, etc.
            # so that the renderer can apply flipbook / additive blending / clamp modes.
            self._load_txi_metadata_for_model(m)
            # Trigger Numba JIT warmup in background so the first drag frame is fast
            # (v10.5): warmup_jit() is a no-op if already warmed or if Numba is absent.
            import threading as _t
            _t.Thread(target=_warmup_jit, daemon=True,
                      name="accel-jit-warmup").start()

    @staticmethod
    def _compute_skin_proxy_ids(model: 'KotorModel') -> set:
        """
        v12.14: Build the set of node ids that are SkinMesh deformation proxies.

        In KotOR, some non-skin trimesh nodes (e.g. 'head_Hair' on the bantha)
        serve as simplified reference geometry that drives SkinMesh deformation.
        They share a texture with a skin mesh and should NOT be rendered separately
        because the skin mesh (bthair / btBody_front) already provides the visible
        geometry in the correct world-space position.

        Rule: A non-skin node N is a proxy if and only if:
          1. N is NOT a skin node.
          2. N has a real (non-null) texture.
          3. N has UV coordinates.
          4. The texture is used by EXACTLY ONE skin mesh in the whole model.
          5. That skin mesh has MORE vertices than N.

        This correctly identifies 'head_Hair' (61 verts, c_banthh01) as a proxy
        of 'bthair' (320 verts, c_banthh01), while NOT marking 'btRhorn' as a
        proxy because c_bantha01 is shared by TWO skin meshes (btBody_front,
        btBodyback), so condition 4 is not met.

        Returns a set of Python id()s for proxy nodes.
        """
        proxy_ids: set = set()
        try:
            all_nodes = model.all_nodes()

            # Build tex → [(skin_node, vert_count)] mapping for skin meshes
            skin_tex_verts: dict = {}
            for n in all_nodes:
                # KotOR skin nodes have both is_skin=True and is_mesh=True (flags 0x61).
                # Accept any node that is a skin (is_skin=True) regardless of is_mesh.
                if not n.is_skin:
                    continue
                tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
                if not tex or tex == 'null':
                    continue
                nv = len(getattr(n, 'vertices', []))
                if nv == 0:
                    continue
                if tex not in skin_tex_verts:
                    skin_tex_verts[tex] = []
                skin_tex_verts[tex].append((n, nv))

            # Check each non-skin, non-null, UV-having node
            for n in all_nodes:
                if not n.is_mesh or n.is_skin:
                    continue
                tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
                if not tex or tex == 'null':
                    continue
                if not getattr(n, 'uvs', []):
                    continue  # already handled by no-UVs check
                nv = len(getattr(n, 'vertices', []))

                # BUG FIX v26: NEVER mark inner-geometry nodes (eyes, eyelids,
                # teeth, tongue, jaw, gum) as skin proxies.  These are real
                # renderable meshes; even when they share a texture with a skin
                # mesh they must be drawn independently so the eyeball / teeth
                # appear inside the head socket.  Without this exemption, models
                # like n_brejikh whose eye nodes share c_bantha01 (or equivalent)
                # with exactly one skin mesh would have their eyes silenced.
                _n_lower = n.name.lower()
                if any(s in _n_lower for s in _INNER_GEO_SUBSTRINGS):
                    continue

                skin_matches = skin_tex_verts.get(tex, [])
                # Condition 4: exactly ONE skin mesh uses this texture
                if len(skin_matches) != 1:
                    continue
                skin_node, skin_verts = skin_matches[0]
                # Condition 5: skin mesh has more vertices than this node
                if skin_verts <= nv:
                    continue

                proxy_ids.add(id(n))
                log.debug(
                    f"Skin proxy: '{n.name}' (non-skin, {nv}v, tex='{tex}') "
                    f"→ covered by '{skin_node.name}' (skin, {skin_verts}v)"
                )
        except Exception as e:
            log.debug(f"_compute_skin_proxy_ids error: {e}")
        return proxy_ids

    def _load_txi_metadata_for_model(self, m: 'KotorModel') -> None:
        """
        Load TXI metadata for all mesh nodes in the model and apply to node fields.

        Iterates over all mesh nodes, looks up TXI data for each node's primary
        texture (and secondary textures), then updates the TXI fields on each node
        (txi_blending, txi_cube, txi_proceduretype, etc.) via _apply_txi_to_node().

        FIX-ALPHATEST: Also extracts the per-texture alpha_test_threshold from the
        TPC header bytes [4-7] and stores it as node.txi_alpha_test so the GPU
        renderer can use the per-node discard threshold instead of a global 0.5.
        References: Kotor.NET TPC.cs, xoreos tpc.cpp, PyKotor io_tpc.py.

        This is called once when a model is loaded (set_model) and only affects
        nodes whose primary texture has TXI data in the cache or on disk.
        """
        if m is None:
            return
        try:
            for node in m.all_nodes():
                if not node.is_mesh:
                    continue
                tex_name = _clean_tex_name(node.texture)
                if not tex_name or tex_name.upper() in ('NULL', ''):
                    continue
                txi_str = self.tex_cache.get_txi(tex_name)
                # FIX-ALPHATEST: extract alpha_test_threshold from raw TPC header
                alpha_test = 0.5  # Aurora engine default
                try:
                    raw = self.tex_cache.get_raw_header(tex_name)
                    if raw:
                        alpha_test = _extract_alpha_test_from_tpc(raw)
                except Exception:
                    pass
                # Always call _apply_txi_to_node to set txi_alpha_test even
                # when there is no TXI string (punchthrough threshold comes from TPC).
                _apply_txi_to_node(node, txi_str or '', alpha_test)
        except Exception as e:
            log.debug(f"_load_txi_metadata_for_model error: {e}")

    def _get_render_bounds(self):
        """Return cached render bounds for the current model.
        Recomputes only when the model identity changes (O(N*verts) avoided per frame)."""
        if self.model is None:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        model_id = id(self.model)
        if self._render_bounds_cache is not None and self._render_bounds_model_id == model_id:
            return self._render_bounds_cache
        # Recompute (model was replaced without calling set_model, e.g. node was modified)
        try:
            rbb_min, rbb_max = self.model.render_bounds()
        except Exception:
            rbb_min, rbb_max = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
        self._render_bounds_cache = (rbb_min, rbb_max)
        self._render_bounds_model_id = model_id
        return rbb_min, rbb_max

    def _compute_outlier_skin_nodes(self, m: 'KotorModel'):
        """
        For accessory models (non-standard supermodel), identify skin proxy meshes
        that should not be rendered — they belong to the parent skeleton, not the
        accessory itself.

        Two detection strategies are tried:

        Strategy A – Z-distance (works when skin proxy verts are raw/unshifted):
          Anchor = Z centroid of non-skin visible nodes.
          Outlier if skin node centroid is > 1.5 units away from anchor.

        Strategy B – Vertex count ratio (works for ad_saul-style face overlays):
          In face/head overlay accessories, the non-skin "anchor" pieces are
          tiny (< 50 verts each). Any skin node with > 5× the max non-skin
          vertex count is a body proxy that should be hidden.

        Guard: only triggers for non-standard supermodels; skip if > 50% outliers.
        """
        self._outlier_skin_nodes = set()
        super_upper = m.supermodel.strip().upper()
        if super_upper in self._BASE_SKELETONS:
            return   # base character model – no outlier filtering needed
        # Also skip for creature/droid models (self-contained, no accessory proxy meshes)
        # Model names starting with C_ (creature), N_ (creature NPC), or the model's
        # own supermodel matching its own name prefix means it IS the base skeleton.
        model_upper = (m.name or '').strip().upper()
        # Expanded creature/NPC prefixes to prevent outlier-check crashes on all creature models
        creature_prefixes = ('C_', 'N_WARD', 'WARDROID', 'N_', 'P_', 'G_')
        if any(model_upper.startswith(p) for p in creature_prefixes):
            return
        if any(super_upper.startswith(p) for p in creature_prefixes):
            return
        # If supermodel is 'NULL' or empty, model is self-contained → skip outlier check
        if not super_upper or super_upper in ('NULL', 'NONE', '0'):
            return

        # Collect visible non-skin nodes (the "anchor geometry")
        # PERFORMANCE: Sample at most 100 vertices per node for Z-centroid
        # (full iteration is O(total_verts) and too slow for high-poly models)
        _MAX_SAMPLE = 100
        ns_zs = []
        ns_visible = []
        for n in m.mesh_nodes():
            if n.is_skin or not n.vertices:
                continue
            if self._is_deformation_helper(n):
                continue
            wp = n.world_position()
            verts = n.vertices
            step = max(1, len(verts) // _MAX_SAMPLE)
            for v in verts[::step]:
                ns_zs.append(v[2] + wp[2])
            ns_visible.append(n)

        # Require at least 3 non-skin visible nodes for a reliable anchor
        if len(ns_visible) < 3:
            return

        anchor_z = sum(ns_zs) / len(ns_zs)

        # Collect skin nodes
        skin_nodes = []
        for n in m.mesh_nodes():
            if not n.is_skin or not n.vertices:
                continue
            if self._is_deformation_helper(n):
                continue
            # Determine if this model is an accessory (non-base supermodel).
            # For accessory models, skin vertices are in bone-local space and
            # need the node's world-position Z added to get world Z.
            # For standalone models (NULL supermodel / base skeleton), skin
            # vertices are already in world/model space.
            verts = n.vertices
            step = max(1, len(verts) // _MAX_SAMPLE)
            raw_zs = [v[2] for v in verts[::step]]

            # All skin nodes store vertices in node-local space.
            # Always add the node's world Z to get world Z for outlier detection.
            wp_s = n.world_position()
            zs = [v + wp_s[2] for v in raw_zs]
            node_cz = sum(zs) / len(zs) if zs else 0.0
            skin_nodes.append((n, node_cz, abs(node_cz - anchor_z)))

        if not skin_nodes:
            return

        # ── Strategy A: Z-distance outlier ──────────────────────────────────
        candidates_a = [item for item in skin_nodes if item[2] > 1.5]

        # ── Strategy B: vertex-count ratio (face-overlay proxy detection) ───
        # If non-skin pieces are all tiny (≤50 verts), a skin node with
        # > 5× the max non-skin vertex count is a body proxy.
        # EXCEPTION: skin nodes with a real texture AND valid UVs are never
        # body proxies; they are the primary visible geometry (e.g. ad_saul body).
        max_ns_verts = max(len(n.vertices) for n in ns_visible)
        candidates_b = []
        if max_ns_verts <= 50:
            vcount_threshold = max(max_ns_verts * 5, 100)
            for n, cz, dist in skin_nodes:
                if len(n.vertices) < vcount_threshold:
                    continue
                # Skip if the node has a real texture with valid UVs (it's renderable geometry)
                tex = _clean_tex_name(n.texture)
                if tex and tex.upper() not in ('NULL', ''):
                    if n.uvs and not any(abs(u) > 3.0 or abs(v) > 3.0 for u, v in n.uvs[:20]):
                        continue  # real textured skin node – keep it
                candidates_b.append((n, cz, dist))

        # Merge candidates (union of both strategies)
        candidate_ids = {id(n) for n, _, _ in candidates_a}
        candidate_ids |= {id(n) for n, _, _ in candidates_b}
        candidates = [(n, cz, d) for n, cz, d in skin_nodes if id(n) in candidate_ids]

        # Guard: don't filter if more than half of skin nodes would be hidden
        if len(candidates) > len(skin_nodes) * 0.5:
            return

        for n, cz, dist in candidates:
            self._outlier_skin_nodes.add(id(n))

    def _is_outlier_skin(self, node: 'ModelNode') -> bool:
        """Return True if this node is a far-outlier skin proxy in an accessory model."""
        return id(node) in self._outlier_skin_nodes

    def _cam_view_matrix(self):
        """Return (right, up, fwd, eye) from the camera, supporting both
        ArcBallCamera objects (which have _view_matrix()) and duck-typed
        camera objects (which only have eye, target, up attributes).

        FIX-HEADLESS-CAM: render_model_autoframe / _render_cpu pass a plain
        namespace camera with no _view_matrix() method.  This shim computes
        the view matrix from the raw eye/target/up attributes so that
        FrameRenderer works in headless/batch mode without an ArcBallCamera.
        """
        if callable(getattr(self.cam, '_view_matrix', None)):
            return self.cam._view_matrix()
        # Duck-typed camera: compute view matrix from eye/target/up
        _eye = self.cam.eye
        if callable(_eye):
            _eye = _eye()
        target = getattr(self.cam, 'target', (0.0, 0.0, 0.0))
        world_up_hint = getattr(self.cam, 'up', (0.0, 0.0, 1.0))
        fwd = _normalize(_sub(target, _eye))
        right = _normalize(_cross(fwd, world_up_hint))
        if _dot(right, right) < 1e-6:
            # up is parallel to fwd — use fallback world-up
            _fb = (0.0, 1.0, 0.0) if abs(world_up_hint[2]) > 0.9 else (0.0, 0.0, 1.0)
            right = _normalize(_cross(fwd, _fb))
        up = _cross(right, fwd)
        return right, up, fwd, _eye

    def render(self, W: int, H: int) -> Optional['Image.Image']:
        if not _PIL:
            return None
        # Wrap the entire render in a MemoryError guard so any PIL allocation
        # failure returns None rather than propagating up to crash the app.
        try:
            return self._render_inner(W, H)
        except MemoryError:
            log.warning(f"FrameRenderer.render: MemoryError at {W}x{H} — returning None")
            return None
        except Exception as exc:
            log.warning(f"FrameRenderer.render: unhandled error: {exc}", exc_info=True)
            return None

    def render_still(self, W: int, H: int,
                     az_deg: float = -45.0, el_deg: float = 20.0,
                     fov: float = 45.0) -> Optional['Image.Image']:
        """
        High-quality offline/still render — bypasses the interactive triangle cap.

        Uses MAX_TRIS_TEXTURED_STILL (50k tris) so that every visible face is
        rendered regardless of model complexity.  Temporarily overrides the camera
        angle and restores it afterwards so the viewport state is unchanged.

        Usage:
            img = renderer.render_still(1024, 1024, az_deg=-60, el_deg=25)
            img.save("my_model.png")

        Args:
            W, H       : output image dimensions in pixels
            az_deg     : camera azimuth angle in degrees (default -45°)
            el_deg     : camera elevation angle in degrees (default 20°)
            fov        : camera field-of-view in degrees (default 45°)

        Returns:
            PIL Image in RGB mode, or None on failure.
        """
        if not _PIL:
            return None
        # Save current camera state
        _saved_az  = getattr(self.cam, 'az',  -45.0)
        _saved_el  = getattr(self.cam, 'el',   20.0)
        _saved_fov = getattr(self.cam, 'fov',  45.0)
        # Temporarily raise triangle cap to still-render budget
        _saved_cap = self.__class__.MAX_TRIS_TEXTURED
        try:
            self.__class__.MAX_TRIS_TEXTURED = self.__class__.MAX_TRIS_TEXTURED_STILL
            # Override camera angles if accessible
            if hasattr(self.cam, 'az'):
                self.cam.az = az_deg
            if hasattr(self.cam, 'el'):
                self.cam.el = el_deg
            if hasattr(self.cam, 'fov'):
                self.cam.fov = fov
            return self.render(W, H)
        except Exception as exc:
            log.warning(f"FrameRenderer.render_still: {exc}", exc_info=True)
            return None
        finally:
            # Always restore original state
            self.__class__.MAX_TRIS_TEXTURED = _saved_cap
            if hasattr(self.cam, 'az'):  self.cam.az  = _saved_az
            if hasattr(self.cam, 'el'):  self.cam.el  = _saved_el
            if hasattr(self.cam, 'fov'): self.cam.fov = _saved_fov

    def _render_inner(self, W: int, H: int) -> Optional['Image.Image']:
        if not _PIL:
            return None
        # Track last rendered dimensions for hit-testing (AcuRig guide drag etc.)
        self._last_W = W
        self._last_H = H
        # Only clear the world-transform cache when the model or animation
        # pose actually changes — NOT every frame.  Clearing every frame forced
        # a full O(n_bones²) parent-chain walk on every render tick, making the
        # bantha (~40 bones × ~6000 verts) extremely laggy.
        # The cache is already invalidated by set_model() and set_animation_pose().
        # Here we only clear it if the model identity has changed (safety net).
        if self.model and id(self.model) != getattr(self, '_cached_model_id', -1):
            self._wt_cache.clear()
            self._cached_model_id = id(self.model)

        # Auto-compute outlier skin nodes if not yet done for this model
        # (ensures headless/batch renders also benefit from outlier filtering)
        if self.model and id(self.model) != self._outlier_model_id:
            self._compute_outlier_skin_nodes(self.model)
            self._outlier_model_id = id(self.model)

        # Cache view matrix for this frame so _proj() doesn't recompute it
        # per-triangle (saves significant CPU for high-poly models like bantha)
        # FIX-HEADLESS-CAM: use _cam_view_matrix() shim so duck-typed cameras
        # (e.g. _AutoCam from render_model_autoframe) work without _view_matrix()
        self._frame_view = self._cam_view_matrix()  # (right, up, fwd, eye)

        # PERF-FIX (v10.2): Per-frame world-vertex and world-normal caches.
        # _get_world_verts_for_node and _get_world_normals_for_node are called
        # twice per frame when both _draw_mesh_textured and _draw_mesh_flat run
        # (not possible) OR when the same node appears in multiple passes.
        # More importantly: for static (bind-pose) models the transform is
        # identity for most nodes — caching within the frame avoids redundant
        # vertex list comprehensions.  Cache is keyed by node id and cleared
        # at the start of every frame (so stale data is never used).
        self._frame_verts_cache: dict = {}
        self._frame_norms_cache: dict = {}

        # PERF-FIX (v10.1): Use RGBA canvas so _paste_textured_triangle can use
        # the fast img.paste(patch, pos, mask) path without crop+composite overhead.
        # The RGBA alpha channel is ignored at display time (converted to RGB by
        # ImageTk.PhotoImage when drawn to the canvas).
        img  = Image.new('RGBA', (W, H), _BG[:3] + (255,))
        draw = ImageDraw.Draw(img)

        if self.show_grid:
            self._draw_grid(draw, W, H)

        if self.model:
            if self.show_texture:
                # ── Render path selection (v10.5) ─────────────────────────
                # Priority order:
                #   1. Accel (Numba/NumPy) – 17–40× speedup, handles both flat
                #      and textured modes, used for interactive AND idle.
                #   2. PIL flat (interactive drag, no accel) – original fast path.
                #   3. PIL textured (idle, no accel) – original PIL AFFINE path.
                if self.is_interactive:
                    # Interactive drag: use fast flat-shade accel if available,
                    # otherwise fall back to PIL flat.
                    if _ACCEL_AVAILABLE:
                        _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=True)
                    else:
                        _accel_ok = False
                    if not _accel_ok:
                        self._draw_mesh_flat(draw, img, W, H)
                    draw = ImageDraw.Draw(img)
                else:
                    # Idle / release: use textured accel if available.
                    if _ACCEL_AVAILABLE:
                        _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=False)
                    else:
                        _accel_ok = False
                    if not _accel_ok:
                        # Fall back to PIL AFFINE path
                        self._draw_mesh_textured(draw, img, W, H)
                    # Recreate draw after any texture rendering since paste()
                    # may invalidate the draw context
                    draw = ImageDraw.Draw(img)
            else:
                # Solid / flat mode: use accel flat-shade if available
                if _ACCEL_AVAILABLE:
                    _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=True)
                else:
                    _accel_ok = False
                if not _accel_ok:
                    self._draw_mesh_flat(draw, img, W, H)
                draw = ImageDraw.Draw(img)

            # Bones drawn after all mesh/paste calls with a fresh draw context
            if self.show_bones:
                self._draw_bones(draw, W, H)

            # External skeleton overlay (ghost purple bones from other model)
            if self._ext_skeleton:
                self._draw_ext_skeleton(draw, W, H)

            # Gimbal transform overlay for selected node
            if self.show_gimbal and self.selected_node and not self.is_interactive:
                self._draw_gimbal(draw, W, H)

            # Walkmesh overlay (Phase 16.1 — drawn after model geometry)
            if self.show_walkmesh and self._walkmesh_overlay is not None:
                self._draw_walkmesh_overlay(draw, W, H)

            # AcuRig guide overlay — drawn last so it's always visible
            if getattr(self, '_acurig_guides_overlay', None):
                self._draw_acurig_guides(draw, W, H)

        self._draw_axes(draw, W, H)
        self._draw_stats(draw, W, H)
        # ── Rig-edit mode banner (Phase 22) ──────────────────────────────────
        if self.rig_edit_mode:
            self._draw_rig_edit_banner(draw, W, H)
        return img

    # ── projection ────────────────────────────────────────────────────

    def _proj(self, x, y, z, W, H):
        """Project world-space point to screen. Uses cached view matrix for speed."""
        fv = getattr(self, '_frame_view', None)
        if fv is None:
            return self.cam.project(x, y, z, W, H)
        right, up, fwd, eye = fv
        dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
        cx = dx*right[0] + dy*right[1] + dz*right[2]
        cy = dx*up[0]    + dy*up[1]    + dz*up[2]
        cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
        if cz < getattr(self.cam, '_near', getattr(self.cam, 'near', 0.01)):
            return None
        import math as _m
        f  = 1.0 / _m.tan(_m.radians(self.cam.fov) * 0.5)
        sx = int(W * 0.5 + (cx / cz) * f * H * 0.5)
        sy = int(H * 0.5 - (cy / cz) * f * H * 0.5)
        return sx, sy, cz

    def _proj_batch(self, world_verts, W: int, H: int):
        """
        Project a list of world-space (x,y,z) tuples to screen coords in bulk.
        Returns a list of (sx, sy, cz) or None for each vertex (None = behind camera).
        Uses numpy vectorisation when available for ~10x speedup on large meshes.

        v10.5: Eliminated the post-NumPy Python result-list loop using np.ndarray
        fancy indexing, reducing per-call overhead by ~30% on 1k-vertex meshes.
        """
        fv = getattr(self, '_frame_view', None) or self._cam_view_matrix()
        right, up, fwd, eye = fv
        near = getattr(self.cam, '_near', getattr(self.cam, 'near', 0.01))
        import math as _m
        f = 1.0 / _m.tan(_m.radians(self.cam.fov) * 0.5)
        ex, ey, ez = eye

        if _NUMPY and len(world_verts) > 8:
            arr = np.array(world_verts, dtype=np.float32)
            dx = arr[:, 0] - ex
            dy = arr[:, 1] - ey
            dz = arr[:, 2] - ez
            cx = dx*right[0] + dy*right[1] + dz*right[2]
            cy = dx*up[0]    + dy*up[1]    + dz*up[2]
            cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
            valid = cz >= near
            hw = W * 0.5
            hh = H * 0.5
            fhh = f * hh
            safe_cz = np.where(valid, cz, 1.0)
            sx = np.where(valid, (hw + (cx / safe_cz) * fhh).astype(np.int32), np.int32(-1))
            sy = np.where(valid, (hh - (cy / safe_cz) * fhh).astype(np.int32), np.int32(-1))
            # Build result list without per-element Python branching.
            # Pre-allocate None list; overwrite valid indices in bulk using numpy.
            NV = len(world_verts)
            result: list = [None] * NV
            valid_idx = np.nonzero(valid)[0]
            sx_v = sx[valid_idx].tolist()
            sy_v = sy[valid_idx].tolist()
            cz_v = cz[valid_idx].tolist()
            for k, i in enumerate(valid_idx.tolist()):
                result[i] = (sx_v[k], sy_v[k], cz_v[k])
            return result

        # Fallback: scalar loop
        result = []
        fhh = f * H * 0.5
        hw  = W * 0.5
        hh  = H * 0.5
        for vx, vy, vz in world_verts:
            dx = vx - ex; dy = vy - ey; dz = vz - ez
            cx = dx*right[0] + dy*right[1] + dz*right[2]
            cy = dx*up[0]    + dy*up[1]    + dz*up[2]
            cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
            if cz < near:
                result.append(None)
            else:
                result.append((int(hw + (cx/cz)*fhh), int(hh - (cy/cz)*fhh), cz))
        return result

    # ── Grid ──────────────────────────────────────────────────────────

    def _draw_grid(self, draw: 'ImageDraw.Draw', W: int, H: int):
        n    = 8
        step = max(0.1, self.cam.distance * 0.15)
        for s in (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0):
            if step <= s:
                step = s; break
        gr = _GRID[:3]
        for i in range(-n, n+1):
            p1 = self._proj(-n*step, i*step, 0, W, H)
            p2 = self._proj( n*step, i*step, 0, W, H)
            if p1 and p2:
                draw.line([p1[0],p1[1],p2[0],p2[1]], fill=gr, width=1)
            p1 = self._proj(i*step, -n*step, 0, W, H)
            p2 = self._proj(i*step,  n*step, 0, W, H)
            if p1 and p2:
                draw.line([p1[0],p1[1],p2[0],p2[1]], fill=gr, width=1)

    # ── Texture loading helper ─────────────────────────────────────────

    def _get_tex(self, node: ModelNode) -> Optional['Image.Image']:
        """Resolve texture image for a node. Returns PIL.Image (RGBA) or None.

        Pre-converts textures to RGBA mode on first access and caches the result
        so _paste_textured_triangle doesn't need to call convert('RGBA') per triangle.
        """
        raw_name = node.texture
        if not raw_name:
            return None
        tex_name = _clean_tex_name(raw_name)
        if not tex_name or tex_name.upper() in ('NULL', ''):
            return None
        key = tex_name.lower()
        img = self.textures.get(key)
        if img is None:
            img = self.tex_cache.get(tex_name)
            if img:
                # Pre-convert to RGBA so _paste_textured_triangle skips convert()
                if img.mode != 'RGBA':
                    try:
                        img = img.convert('RGBA')
                    except Exception:
                        pass
                self.textures[key] = img
        return img

    def _get_tex_by_name(self, raw_name: str) -> Optional['Image.Image']:
        """Resolve and cache a texture image by raw texture name string.

        Used by multi-texture rendering to look up secondary material slots
        (face_mats > 0) without a node reference.
        """
        if not raw_name:
            return None
        tex_name = _clean_tex_name(raw_name)
        if not tex_name or tex_name.upper() in ('NULL', ''):
            return None
        key = tex_name.lower()
        img = self.textures.get(key)
        if img is None:
            img = self.tex_cache.get(tex_name)
            if img:
                if img.mode != 'RGBA':
                    try:
                        img = img.convert('RGBA')
                    except Exception:
                        pass
                self.textures[key] = img
        return img

    def _get_tex_for_face(self, node: ModelNode, face_idx: int) -> Optional['Image.Image']:
        """Return the correct texture image for a specific face index.

        When tex_count == 1 (normal case) this is identical to _get_tex(node).
        When tex_count > 1 (multi-material mesh, e.g. c_bantha body+head zones),
        face_mats[face_idx] carries the 0-based texture-slot index; we look up
        texture_names[slot] so each face gets its own correct texture.

        This fixes the 'mouth texture rendering on the tail' bug: without this,
        all faces of a multi-material node got slot-0's texture regardless of
        which material zone they belonged to.

        FIX-LMROUTE: When has_lightmap=True, always return the primary diffuse
        texture (slot 0).  Lightmap nodes use slot 1 for the lightmap texture
        (composited via a separate multiply pass), NOT as a per-face material.
        face_mats[i]==1 on these nodes is a KotOR binary artifact, not a
        material-selection indicator.
        """
        tex_count    = getattr(node, 'tex_count', 1)
        face_mats    = getattr(node, 'face_mats', [])
        tex_names    = getattr(node, 'texture_names', [])

        if tex_count <= 1 or not face_mats or not tex_names:
            # Single-texture node — fast path
            return self._get_tex(node)

        # FIX-LMROUTE: Lightmapped nodes should always use the primary diffuse
        # texture, not route faces to the lightmap via face_mats.
        if bool(getattr(node, 'has_lightmap', False)):
            return self._get_tex(node)

        slot = face_mats[face_idx] if face_idx < len(face_mats) else 0
        # Clamp to valid range; corrupt data sometimes has out-of-range values
        slot = max(0, min(slot, len(tex_names) - 1))
        raw  = tex_names[slot] if slot < len(tex_names) else node.texture

        if not raw:
            # Fallback to primary texture if the slot is empty
            return self._get_tex(node)
        return self._get_tex_by_name(raw)

    # ── Compute face normal from vertices ─────────────────────────────

    @staticmethod
    def _face_normal(v0, v1, v2):
        e1 = _sub(v1, v0)
        e2 = _sub(v2, v0)
        return _normalize(_cross(e1, e2))

    @staticmethod
    def _compute_area_weighted_normals(
        faces: list, world_verts: list
    ) -> list:
        """
        Compute per-vertex normals via area-weighted face-normal accumulation.

        Inspired by UE5's SkeletalMesh normal recomputation:  each face
        contributes to its three vertices with a weight equal to the triangle's
        area (‖e1 × e2‖ / 2).  Larger triangles therefore dominate the vertex
        normal, which produces smoother lighting gradients on curved surfaces
        compared to plain averaging.

        Returns a list of (nx, ny, nz) tuples, one per world-space vertex.
        Falls back to (0, 1, 0) for degenerate vertices with zero accumulated
        weight.  Only uses faces whose vertex indices are within bounds.

        UE reference: SkeletalRenderCPUSkin.cpp – SkinVertices, tangent
        accumulation loops (lines ~750-880 in the analysed source).
        """
        nv = len(world_verts)
        if nv == 0 or not faces:
            return []

        accum = [[0.0, 0.0, 0.0] for _ in range(nv)]

        for face in faces:
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= nv or i1 >= nv or i2 >= nv:
                continue
            # Skip degenerate faces with repeated vertex indices
            if i0 == i1 or i1 == i2 or i0 == i2:
                continue
            v0 = world_verts[i0]
            v1 = world_verts[i1]
            v2 = world_verts[i2]
            # Unweighted cross product — its magnitude equals twice the
            # triangle area, so this IS the area-weighted normal.
            e1x = v1[0]-v0[0]; e1y = v1[1]-v0[1]; e1z = v1[2]-v0[2]
            e2x = v2[0]-v0[0]; e2y = v2[1]-v0[1]; e2z = v2[2]-v0[2]
            cx = e1y*e2z - e1z*e2y
            cy = e1z*e2x - e1x*e2z
            cz = e1x*e2y - e1y*e2x
            accum[i0][0] += cx; accum[i0][1] += cy; accum[i0][2] += cz
            accum[i1][0] += cx; accum[i1][1] += cy; accum[i1][2] += cz
            accum[i2][0] += cx; accum[i2][1] += cy; accum[i2][2] += cz

        result = []
        for a in accum:
            ax, ay, az = a
            length = math.sqrt(ax*ax + ay*ay + az*az)
            if length > 1e-9:
                result.append((ax/length, ay/length, az/length))
            else:
                result.append((0.0, 1.0, 0.0))
        return result

    def _node_world_transform(self, node: 'ModelNode'):
        """
        Return (wp, wo, is_identity_rot) with per-frame caching.

        When an animation pose is active, always walk the full parent chain
        and substitute animated position/rotation for nodes that have pose data.
        Nodes NOT in the pose retain their bind-pose local transform.

        This is critical: even if a leaf bone has no keyframes, its world
        transform must be recomputed because its *parent* may have moved.
        """
        nid = id(node)
        cached = self._wt_cache.get(nid)
        if cached is not None:
            return cached
        import math as _math
        try:
            from ..core.model_data import (_quat_rotate as _qr, _quat_normalize_bind,
                                           _quat_normalize, _quat_mul)
        except ImportError:
            from core.model_data import (_quat_rotate as _qr, _quat_normalize_bind,  # type: ignore
                                         _quat_normalize, _quat_mul)

        if self._anim_pose is not None:
            # Always walk the full ancestor chain when a pose is active.
            # Substitute animated values for nodes that have pose entries;
            # use bind-pose local transform for nodes that don't.
            chain = []
            n = node
            _visited_chain: set = set()
            while n is not None:
                nid_c = id(n)
                if nid_c in _visited_chain or len(chain) > 512:
                    break  # cycle guard for corrupted MDL data
                _visited_chain.add(nid_c)
                chain.append(n)
                n = n.parent
            chain.reverse()

            wx, wy, wz = 0.0, 0.0, 0.0
            parent_orientation = [0.0, 0.0, 0.0, 1.0]
            last_i = len(chain) - 1

            for ci, chain_node in enumerate(chain):
                is_leaf = (ci == last_i)
                pn = self._anim_pose.nodes.get(chain_node.name.lower())
                if pn:
                    lx, ly, lz = pn.position
                    # NaN guard: fall back to bind-pose position if animated value is non-finite
                    if not (_math.isfinite(lx) and _math.isfinite(ly) and _math.isfinite(lz)):
                        lx, ly, lz = chain_node.position
                    rot = list(pn.rotation)
                    # NaN guard on rotation
                    if not all(_math.isfinite(v) for v in rot):
                        rot = list(chain_node.rotation)
                    # Parent nodes in the chain (non-leaf): apply _quat_normalize_bind
                    # to collapse the NWN X-axis 180° coord-flip rotation to identity,
                    # exactly as the bind-pose path does.  This is critical: the root
                    # node often carries [1,0,0,0] (180° about X) in both its bind pose
                    # AND in the animation pose (since there's no keyframe that changes
                    # it).  Without collapsing it here, all descendant positions are
                    # rotated 180° around X during animation, causing the mesh to
                    # invert/explode.  _quat_normalize_bind only collapses PURE X-axis
                    # 180° rotations — actual animation keyframes produce rotations that
                    # won't match this pattern, so they are preserved unchanged.
                    #
                    # Leaf node: preserve the actual rotation for vertex transform
                    # (used to orient the mesh node in world space).
                    if not is_leaf:
                        node_rot = _quat_normalize_bind(rot)
                    else:
                        l2 = rot[0]*rot[0]+rot[1]*rot[1]+rot[2]*rot[2]+rot[3]*rot[3]
                        if l2 > 1e-9:
                            l = _math.sqrt(l2)
                            rot = [rot[0]/l, rot[1]/l, rot[2]/l, rot[3]/l]
                        node_rot = rot
                else:
                    lx, ly, lz = chain_node.position
                    rot = list(chain_node.rotation)
                    # Bind-pose parent nodes: collapse 180°-about-axis NWN convention
                    # Leaf node: preserve actual rotation for vertex transform
                    if is_leaf:
                        node_rot = _quat_normalize(rot)
                    else:
                        node_rot = _quat_normalize_bind(rot)

                rx, ry, rz = _qr(parent_orientation, (lx, ly, lz))
                wx += rx; wy += ry; wz += rz
                parent_orientation = _quat_mul(parent_orientation, node_rot)

            # Explosion guard: if accumulated world position is non-finite or
            # unreasonably large, fall back to the bind-pose transform.  This
            # catches bad animation keyframes that produce runaway positions.
            if not (_math.isfinite(wx) and _math.isfinite(wy) and _math.isfinite(wz)):
                wp_b, wo_b = node.world_transform()
                wo_rot_b = _math.sqrt(wo_b[0]*wo_b[0] + wo_b[1]*wo_b[1] + wo_b[2]*wo_b[2])
                result = (wp_b, wo_b, wo_rot_b < 0.001)
                self._wt_cache[nid] = result
                return result

            wp = (wx, wy, wz)
            wo = tuple(parent_orientation)
            # Ensure orientation quaternion is unit-length (guards against
            # accumulated float error across long parent chains)
            wo_len2 = wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2] + wo[3]*wo[3]
            if wo_len2 > 1e-9 and abs(wo_len2 - 1.0) > 1e-4:
                _s = 1.0 / _math.sqrt(wo_len2)
                wo = (wo[0]*_s, wo[1]*_s, wo[2]*_s, wo[3]*_s)
            wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_id  = (wo_rot < 0.001)
            result = (wp, wo, is_id)
            self._wt_cache[nid] = result
            return result

        # Default: bind pose (no animation active)
        wp, wo = node.world_transform()
        wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
        is_id  = (wo_rot < 0.001)
        result = (wp, wo, is_id)
        self._wt_cache[nid] = result
        return result

    @staticmethod
    def _apply_vertex_transform(node: 'ModelNode', v, wp, wo, is_identity_rot: bool):
        """
        Transform vertex v from node-local/bind-pose to world space.

        KotOR MDL vertex storage rules (verified empirically against full K1+K2 model set):
          - Skin nodes: vertices are stored in SKIN-NODE-LOCAL space.
            For models with identity skin-node rotation (most common), only add wp.
            For models with a non-identity rotation on the skin mesh node itself
            (e.g. p_bastilabb / p_bastilaba which carry a 180° X or Y rotation
            inherited from the NWN co-ordinate-flip exporter), the rotation MUST be
            applied before the translation so that vertices end up correctly oriented
            in world space.  Applying the rotation to identity-rotation nodes is
            a no-op (wo = (0,0,0,1) → _quat_rotate returns v unchanged), so the
            same branch is safe for both cases.
          - Non-skin (trimesh/dangly) + identity orientation → translate by wp only.
          - Non-skin + non-identity orientation → full world transform (rotate + translate).
        """
        if is_identity_rot:
            return (v[0] + wp[0], v[1] + wp[1], v[2] + wp[2])
        rx, ry, rz = _quat_rotate(wo, v)
        return (rx + wp[0], ry + wp[1], rz + wp[2])

    def _get_vertex_world(self, node: 'ModelNode', vi: int):
        """Get a vertex in world space using cached world transform."""
        v = node.vertices[vi]
        wp, wo, is_id = self._node_world_transform(node)
        return self._apply_vertex_transform(node, v, wp, wo, is_id)

    # ── Linear Blend Skinning (animated mesh deformation) ─────────────

    def _build_bone_transforms(self, node: 'ModelNode') -> Optional[Dict]:
        """
        Build a dict mapping compact bone index → (bind_world_pos, bind_world_quat,
        anim_world_pos, anim_world_quat) for all bones in this skin node's bone_map.

        Also stores the skin node's own bind-pose world position under the special
        key -1 so _lbs_vertex can convert skin-local vertices to world space.

        PERFORMANCE: A shared per-pose name-keyed cache (_bone_transforms_by_name) holds
        the transform for every unique bone name in the model.  Each call for a skin node
        builds its compact-index dict by looking up names in that shared cache, so the
        expensive bind-pose/anim-pose passes run only ONCE per animation frame across all
        skin nodes, instead of once per skin node.

        Returns None if the node has no bone_map or no valid bones.
        """
        if not node.is_skin or not node.bone_map or not node.skin_data:
            return None

        model = self.model
        if model is None:
            return None

        # ── Per-pose shared cache keyed by bone NAME ─────────────────────
        # id() of the pose object changes on every animation tick (new AnimPose),
        # which correctly invalidates the cache each frame.
        pose_key = id(self._anim_pose) if self._anim_pose is not None else 0

        if (self._bone_transforms_cache is None or
                self._bone_transforms_pose_id != pose_key):
            # First call this frame: build the full name-keyed cache.
            self._bone_transforms_cache = {}   # name_lower → (bind_wp, bind_wo, anim_wp, anim_wo)
            self._bone_transforms_pose_id = pose_key

            # Build name → node map, preferring non-skin (bone/joint) nodes over
            # skin-mesh nodes when duplicate names exist.  KotOR models frequently
            # use the same name for a bone joint (non-skin, small vertex count or
            # no vertices) AND the deformable skin mesh it drives (e.g. "torso" is
            # both the joint and the 907-vertex skin mesh in N_sithpraet).  For LBS
            # we must reference the JOINT's world transform, not the skin mesh's.
            node_by_name: Dict[str, 'ModelNode'] = {}
            for n in model.all_nodes():
                key = n.name.lower()
                existing = node_by_name.get(key)
                if existing is None:
                    node_by_name[key] = n
                elif existing.is_skin and not n.is_skin:
                    # Replace skin mesh with the non-skin bone/joint node
                    node_by_name[key] = n
                # else: keep existing (first non-skin wins, or first if both skin)

            # Collect unique bone names across all skin nodes
            all_bone_names: set = set()
            for mn in model.all_nodes():
                if mn.is_skin and mn.bone_map:
                    for bname in mn.bone_map:
                        if bname:
                            all_bone_names.add(bname.lower())

            saved_pose = self._anim_pose

            # ── Pass 1: compute all bind-pose transforms ────────────────────
            # THREAD-SAFETY: Don't modify self._anim_pose or self._wt_cache here
            # because the main thread may call set_animation_pose() concurrently.
            # Instead, compute bind-pose transforms by calling _node_world_transform
            # with a temporarily overridden pose variable using a local approach.
            # We create a fresh local wt_cache for the bind pass so we don't
            # corrupt the per-frame cache used by the current animation pass.
            saved_anim_cache = dict(self._wt_cache)
            self._anim_pose = None   # switch to bind pose for Pass 1
            self._wt_cache = {}      # isolated cache for bind-pose pass

            bind_by_name: Dict[str, tuple] = {}
            for bname_lower in all_bone_names:
                bone_node = node_by_name.get(bname_lower)
                if bone_node is None:
                    continue
                wp, wo, _ = self._node_world_transform(bone_node)
                bind_by_name[bname_lower] = (wp, wo)

            # Restore animation pose and wt_cache for animated pass
            self._anim_pose = saved_pose
            self._wt_cache = saved_anim_cache

            # ── Pass 2: compute all animated transforms ─────────────────────
            for bname_lower, (bind_wp, bind_wo) in bind_by_name.items():
                bone_node = node_by_name.get(bname_lower)
                if bone_node is None:
                    continue
                anim_wp, anim_wo, _ = self._node_world_transform(bone_node)
                self._bone_transforms_cache[bname_lower] = (bind_wp, bind_wo, anim_wp, anim_wo)

        # ── Build this node's compact-index → transforms dict ──────────
        # Note: key -1 (skin node bind-pose world position) is no longer stored
        # here as a separate entry; _lbs_vertex reads skin_wp directly via
        # _node_world_transform(node) and adds it to v_local before LBS.
        bone_transforms: Dict = {}

        for bi, bone_name in enumerate(node.bone_map):
            if not bone_name:
                continue
            key = bone_name.lower()
            bt = self._bone_transforms_cache.get(key)
            if bt is not None:
                bone_transforms[bi] = bt

        return bone_transforms if bone_transforms else None

    def _lbs_vertex(self, node: 'ModelNode', vi: int,
                    bone_transforms: Dict) -> Tuple[float, float, float]:
        """
        Apply Linear Blend Skinning to vertex vi of the given skin node.

        KotOR stores skin vertices in NODE-LOCAL space (relative to the skin
        node's pivot in the bind pose), the same as non-skin trimesh nodes.
        The vertex must first be transformed to world space using the skin
        node's world transform before LBS deformation is applied.

        Standard LBS formula:
            v_world_anim = sum_i( w_i * (R_anim_i * R_bind_i^-1 * (v_bind_world - T_bind_i) + T_anim_i) )

        Where:
          v_bind_world = vertex in world space at bind pose
                         = skin_node_world_transform(v_local)
          T_bind_i     = bone i world position at bind pose
          R_bind_i     = bone i world rotation at bind pose
          T_anim_i     = bone i world position at animated pose
          R_anim_i     = bone i world rotation at animated pose

        If no valid bone influences found, falls back to the bind-pose world
        position (skin node world transform applied to the local vertex).
        """
        try:
            from ..core.model_data import _quat_rotate as _qr, _quat_conjugate
        except ImportError:
            from core.model_data import _quat_rotate as _qr, _quat_conjugate  # type: ignore

        v = node.vertices[vi]

        # Convert vertex from node-local space to world space using the skin
        # node's own world transform.  This is the bind-pose world position.
        wp_s, wo_s, is_id_s = self._node_world_transform(node)
        v_world = self._apply_vertex_transform(node, v, wp_s, wo_s, is_id_s)
        vbx, vby, vbz = v_world[0], v_world[1], v_world[2]

        def _bind_fallback():
            """Return bind-pose world position."""
            return (vbx, vby, vbz)

        if vi >= len(node.skin_data):
            # No skin data: return bind-pose world position
            return _bind_fallback()

        sd = node.skin_data[vi]
        influences = sd.influences

        if not influences:
            # No influences: return bind-pose world position
            return _bind_fallback()

        import math as _math_lbs
        rx_total = ry_total = rz_total = 0.0
        total_weight = 0.0
        # Explosion guard: if animated position is more than _MAX_BONE_DIST units away
        # from the bind position, the bone transform is degenerate (NaN propagation from
        # bad animation keyframes, or un-collapsed 180°-axis root rotations in the chain).
        # Skip that influence and fall back to bind-pose contribution instead.
        #
        # v20.0 FIX: Threshold scaled by model bounding-box size to handle large creatures.
        # Previous hard-coded 8.0 unit limit was too small for creatures like c_brith
        # (Drexl) whose wings span ~30 units and travel 15+ units during flight animations,
        # causing clipped/missing wing geometry during animation playback.
        #
        # Strategy: scale by max(model_bbox_diagonal * 0.6, 8.0) to:
        #   - Keep the 8-unit floor for human-scale characters (prevents usecomp distortions)
        #   - Allow large creature wings/limbs to deform correctly (c_brith, c_bosdrexl, etc.)
        # The 0.6 factor means a bone can travel up to 60% of the model's bounding diagonal
        # before being treated as degenerate.  For c_brith (~55-unit diagonal): 33 units.
        # For S_Female02 human scale (~4.0-unit diagonal): floor 8.0 applies.
        _model_diag = getattr(self, '_lbs_model_diag', None)
        if _model_diag is None:
            # Compute bounding diagonal once per model and cache it
            m = self.model
            if m is not None:
                try:
                    bmin, bmax = m.bounding_box()
                    dx = bmax[0]-bmin[0]; dy = bmax[1]-bmin[1]; dz = bmax[2]-bmin[2]
                    _model_diag = _math_lbs.sqrt(dx*dx + dy*dy + dz*dz)
                except Exception:
                    _model_diag = 10.0
            else:
                _model_diag = 10.0
            self._lbs_model_diag = _model_diag
        _MAX_BONE_DIST = max(8.0, _model_diag * 0.6)

        for bw in influences:
            if bw.weight <= 0.0:
                continue
            bt = bone_transforms.get(bw.bone_index)
            if bt is None:
                continue
            bind_wp, bind_wo, anim_wp, anim_wo = bt
            w = bw.weight

            # Sanity-check anim_wp: skip bones with non-finite or extreme positions
            # (explosion guard — catches bad keyframes and un-collapsed root rotations)
            awx, awy, awz = anim_wp
            if not (_math_lbs.isfinite(awx) and _math_lbs.isfinite(awy) and _math_lbs.isfinite(awz)):
                # Non-finite: fall back to bind-pose contribution for this influence
                rx_total += w * vbx; ry_total += w * vby; rz_total += w * vbz
                total_weight += w
                continue
            bwx, bwy, bwz = bind_wp
            bone_travel = _math_lbs.sqrt((awx-bwx)**2 + (awy-bwy)**2 + (awz-bwz)**2)
            if bone_travel > _MAX_BONE_DIST:
                # Bone moved impossibly far: treat as bind-pose for this influence
                rx_total += w * vbx; ry_total += w * vby; rz_total += w * vbz
                total_weight += w
                continue

            # Step 1: transform vertex from bind-pose world space to bone-local space
            # v_bone_local = R_bind^-1 * (v_bind_world - T_bind_bone)
            vx = vbx - bwx
            vy = vby - bwy
            vz = vbz - bwz
            # Inverse of bind rotation quaternion = conjugate (since unit quaternion)
            bind_inv = _quat_conjugate(bind_wo)
            lx, ly, lz = _qr(bind_inv, (vx, vy, vz))

            # Step 2: transform from bone-local space to animated world space
            # v_anim_world = R_anim * v_bone_local + T_anim_bone
            ax, ay, az = _qr(anim_wo, (lx, ly, lz))
            rx_total += w * (ax + awx)
            ry_total += w * (ay + awy)
            rz_total += w * (az + awz)
            total_weight += w

        if total_weight < 0.001:
            # No valid bones – fall back to bind-pose world position
            return _bind_fallback()

        # Normalize by total weight (handles partial weight sums)
        inv_w = 1.0 / total_weight
        rx, ry, rz = rx_total * inv_w, ry_total * inv_w, rz_total * inv_w

        # Final explosion guard: if LBS result is more than _MAX_BONE_DIST*2 away
        # from the bind-pose vertex, the deformation is too extreme — return bind pose.
        # Multiplied by 2 here (vs per-bone check) because compound deformations from
        # multiple valid bones can legitimately sum to larger displacements than any
        # single bone travel (e.g. c_brith wingtip = root travel + wing-fold travel).
        if (_math_lbs.sqrt((rx-vbx)**2 + (ry-vby)**2 + (rz-vbz)**2) > _MAX_BONE_DIST * 2.0):
            return _bind_fallback()
        return (rx, ry, rz)

    def _get_world_verts_for_node(self, node: 'ModelNode') -> List[Tuple]:
        """
        Get all world-space vertices for a node, using LBS when an animation
        pose is active and the node has skin_data, or bind pose otherwise.

        KotOR MDL vertex space convention — Phase 17 (verified against KotorBlender,
        PyKotor, and direct binary analysis of c_bantha, c_terantanak, p_bastilabb,
        N_sithpraet and 50+ other models):

        ALL nodes (skin AND non-skin trimesh/dangly) — BIND POSE:
          Vertices are stored in NODE-LOCAL space (relative to the node's own
          pivot point in the hierarchy).  The full parent-chain world transform
          (translation + rotation accumulated root→leaf) must always be applied.

          KotorBlender (base.py): set_object_data() sets obj.location = self.position
          (LOCAL, not world); vertices uploaded raw without any pre-transform.
          Blender scene graph applies parent-chain transforms automatically.

          PyKotor: vertex_positions read raw from binary MDL, no world-space pre-baking.

          c_bantha direct binary analysis:
            btBody_front local verts Y=[1.117, 3.391], node world pivot Y=-1.163
            → correct world Y = [-0.046, 2.228] (body covers torso, anatomy correct)
            "as-is" gave Y=[1.117, 3.391] (body floating forward in front of skeleton)

          btRhorn: local verts Y=[1.851,2.955], pivot (Y=-0.890,Z=1.469)
            World verts Y=[0.961,2.065] — curved upward/forward above the head. ✓

        SKIN nodes — ANIMATED POSE:
          Use Linear Blend Skinning (LBS) with bone_transforms.
          LBS pre-transforms the local vertex to world space (via skin node's own
          world transform) before applying bone deformation.
        """
        verts = node.vertices
        if not verts:
            return []

        # ── SKIN nodes: LBS path (animated pose) ──────────────────────────────
        if (self._anim_pose is not None and node.is_skin and
                node.bone_map and node.skin_data):
            bone_transforms = self._build_bone_transforms(node)
            if bone_transforms:
                return [self._lbs_vertex(node, i, bone_transforms)
                        for i in range(len(verts))]
            # LBS unavailable: fall through to bind-pose path

        # ── All nodes (skin bind-pose + non-skin trimesh/dangly): apply full world transform ──
        # Phase 17: This unified path handles ALL node types in bind pose.
        # See docstring above for full rationale + references.
        wp, wo, is_id = self._node_world_transform(node)
        xfm = self._apply_vertex_transform

        # ── DanglySimulator path ──────────────────────────────────────────────
        if node.is_dangly and node.dangly_constraints:
            constraints = node.dangly_constraints
            sim = self._dangly_sims.get(id(node)) if self._anim_pose is not None else None
            result = []
            for i, v in enumerate(verts):
                c = constraints[i] if i < len(constraints) else 0.0
                is_pinned = (c >= (DanglySimulator.PIN_THRESHOLD
                                   if DanglySimulator is not None else 0.95))
                if sim is not None and not is_pinned and i < len(sim.positions):
                    result.append(sim.positions[i])
                else:
                    result.append(xfm(node, v, wp, wo, is_id))
            return result

        return [xfm(node, v, wp, wo, is_id) for v in verts]

    def _get_world_normals_for_node(self, node: 'ModelNode') -> List[Optional[Tuple]]:
        """
        Return world-space normals for a node.

        All nodes (skin and non-skin) with identity world orientation: normals are
          already oriented correctly in world space — return as-is (no rotation needed).
        Any node with non-identity world orientation: rotate each normal by the
          node's world orientation quaternion.  This correctly orients normals for:
          - Non-skin trimesh nodes with non-identity bind-pose rotation
          - Skin nodes that carry a non-identity orientation (e.g. 180° X/Y on
            p_bastilabb/p_bastilaba from the NWN coord-flip exporter)

        Returns a list parallel to node.normals.  Empty list if no normals.
        """
        norms = node.normals
        if not norms:
            return []

        # Check if rotation is identity — skip transform when not needed
        wp, wo, is_id = self._node_world_transform(node)
        if is_id:
            return list(norms)

        # Rotate normals by world orientation (rotation-only, no translation).
        # This handles both non-skin trimesh nodes AND skin nodes that carry a
        # non-identity rotation (NWN coord-flip exporter artefact on mesh nodes).
        result = []
        for n in norms:
            rn = _quat_rotate(wo, n)
            # Re-normalise
            nl = math.sqrt(rn[0]*rn[0] + rn[1]*rn[1] + rn[2]*rn[2])
            if nl > 1e-9:
                result.append((rn[0]/nl, rn[1]/nl, rn[2]/nl))
            else:
                result.append(n)
        return result

    def _screen_size_lod_cap(self, W: int, H: int) -> int:
        """
        UE-inspired screen-size driven triangle cap with LOD hysteresis.

        Computes what fraction of the viewport the model occupies (like UE's
        ComputeBoundsScreenSize / USkeletalMeshComponent::UpdateLODStatus) and
        scales the triangle budget accordingly.  A hysteresis dead-band of
        _LOD_HYSTERESIS_FRAC × MAX_TRIS prevents rapid oscillation when the
        camera sits right at a LOD boundary (eliminates "LOD-pop" flicker).

        Returns a triangle count cap in the range:
          [MAX_TRIS_INTERACTIVE (10k) .. MAX_TRIS (80k)]
        """
        if self.model is None:
            cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
            self._lod_prev_cap = cap
            return cap

        try:
            bmin, bmax = self._get_render_bounds()
        except Exception:
            cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
            self._lod_prev_cap = cap
            return cap

        # FIX-CAMEYE: safely handle both callable (ArcBallCamera) and
        # tuple/list (duck-typed camera) for the eye attribute.
        _eye = self.cam.eye
        eye_pos = _eye() if callable(_eye) else _eye
        fov_rad = math.radians(self.cam.fov)

        # Compute screen-size ratio using UE's formula
        ratio = _compute_screen_size_ratio(bmin, bmax, eye_pos, fov_rad, H)

        # Scale triangle cap proportionally to screen coverage:
        # - ratio ≥ 0.5 → full detail
        # - ratio ≤ 0.05 → minimum detail (interactive cap)
        ratio_clamped = _clamp(ratio, 0.05, 0.5)
        t = (ratio_clamped - 0.05) / (0.5 - 0.05)  # 0..1

        base_cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
        min_cap  = self.MAX_TRIS_INTERACTIVE
        new_cap  = int(min_cap + t * (base_cap - min_cap))

        # ── LOD hysteresis dead-band ────────────────────────────────────────
        # Only commit a new cap when it differs from the last committed value
        # by more than the hysteresis threshold.  This prevents per-frame
        # oscillation of the triangle budget when the camera distance hovers
        # near a tier boundary.  Mirrors UE's LOD hysteresis in UpdateLODStatus.
        hysteresis_band = int(self._LOD_HYSTERESIS_FRAC * self.MAX_TRIS)
        if abs(new_cap - self._lod_prev_cap) > hysteresis_band:
            self._lod_prev_cap = new_cap
        return self._lod_prev_cap


    def _draw_mesh_flat(self, draw: 'ImageDraw.Draw',
                        img: 'Image.Image', W: int, H: int):
        cam      = self.cam
        # Use pre-cached view matrix from render() to avoid recomputing per call
        right, up, fwd, eye = getattr(self, '_frame_view', None) or cam._view_matrix()

        # UE-inspired: screen-size driven triangle cap.
        # Scales budget between MAX_TRIS_INTERACTIVE and MAX_TRIS based on how
        # large the model appears on screen (like UE's ComputeBoundsScreenSize).
        tri_cap = self._screen_size_lod_cap(W, H)

        tris = []  # (sort_key, screen_pts, fill_rgb, is_selected)

        for node in self._iter_mesh_nodes():
            if not node.vertices or not node.faces:
                continue
            is_sel = (node is self.selected_node)

            # Skip nodes explicitly marked non-renderable (render=False).
            # Respect the KotOR MDL render flag; only bypass for selected node.
            # EXCEPTION: inner-geometry nodes (eyes, eyelids, teeth, tongue, jaw,
            # gum) are ALWAYS rendered even if render=0.  Some KotOR NPC head MDLs
            # incorrectly store render=0 on these nodes; skipping them causes the
            # character to appear eyeless / toothless in the viewport.
            _nl_flat = node.name.lower()
            _is_inner_geo_flat = any(s in _nl_flat for s in _INNER_GEO_SUBSTRINGS)
            if not getattr(node, 'render', True) and not is_sel and not _is_inner_geo_flat:
                continue

            # Skip deformation-helper nodes entirely in flat mode (unless selected).
            # These are internal skinning proxy meshes that only clutter the display.
            is_helper = self._is_deformation_helper(node)
            if is_helper and not is_sel:
                continue
            # Also skip outlier skin proxies (far-body meshes in accessory models)
            if self._is_outlier_skin(node) and not is_sel:
                continue

            verts = node.vertices
            nv    = len(verts)

            # Pre-transform ALL vertices for this node once.
            # Uses LBS (linear blend skinning) when animation pose is active,
            # otherwise falls back to bind-pose transform.
            # PERF-FIX (v10.2): Use per-frame vertex/normal cache.
            _node_id_flat = id(node)
            _fvc_flat = getattr(self, '_frame_verts_cache', None)
            _fnc_flat = getattr(self, '_frame_norms_cache', None)
            if _fvc_flat is not None and _node_id_flat in _fvc_flat:
                world_verts = _fvc_flat[_node_id_flat]
            else:
                world_verts = self._get_world_verts_for_node(node)
                if _fvc_flat is not None:
                    _fvc_flat[_node_id_flat] = world_verts

            # Pre-transform normals to world space for correct lighting on
            # rotated non-skin nodes (e.g. Wardroid / c_brith body panels).
            if _fnc_flat is not None and _node_id_flat in _fnc_flat:
                world_norms = _fnc_flat[_node_id_flat]
            else:
                world_norms = self._get_world_normals_for_node(node)
                if _fnc_flat is not None:
                    _fnc_flat[_node_id_flat] = world_norms
            n_norms = len(world_norms)

            # ── UE-inspired area-weighted vertex normals ──────────────────────
            # If the node has no stored normals (many KotOR placeable/prop nodes
            # omit per-vertex normals in their MDX data), compute them from the
            # face geometry using area-weighted accumulation.  This gives much
            # smoother shading on curved surfaces than per-face flat-normals.
            # Reference: UE5 SkeletalRenderCPUSkin.cpp tangent accumulation loops.
            if n_norms == 0 and world_verts and node.faces:
                world_norms = self._compute_area_weighted_normals(node.faces, world_verts)
                n_norms = len(world_norms)

            # Batch-project all world vertices to screen coords once per node
            # (avoids per-face view-matrix reconstruction — significant speedup)
            screen_verts = self._proj_batch(world_verts, W, H)


            # Base colour: use texture diffuse or grey for untextured
            clean_tex = _clean_tex_name(node.texture)
            if not clean_tex or clean_tex.upper() in ('NULL',''):
                r, g, b = 130, 130, 160
            else:
                r  = int(_clamp(node.diffuse[0] * 220, 30, 240))
                g  = int(_clamp(node.diffuse[1] * 220, 30, 240))
                b  = int(_clamp(node.diffuse[2] * 220, 30, 240))

            if node.is_skin:
                b = min(b + 25, 255)   # slight blue tint for skin nodes

            # ── Bumpmap/envmap visual indicator (flat mode) ──────────────────
            # Since we can't do real normal-mapping in the flat rasteriser, give
            # bumpmap nodes a subtle warm-gold tint and envmap nodes a cyan tint
            # so modders know these surfaces have special material effects.
            _has_bump = bool(getattr(node, 'txi_bumpmaptexture', ''))
            _has_env  = bool(getattr(node, 'txi_envmaptexture', ''))
            if _has_bump:
                r = min(255, int(r * 1.10 + 10))   # warm gold tint
                g = min(255, int(g * 1.05))
            if _has_env:
                g = min(255, g + 15)               # cyan tint
                b = min(255, b + 20)

            # Per-node alpha — transparent nodes (glass, droid eyes) get blended
            node_alpha = float(getattr(node, 'alpha', 1.0))
            node_alpha = _clamp(node_alpha, 0.0, 1.0)
            # transparency_hint is a render-mode flag, NOT an alpha value:
            #   0 = opaque (default), 1 = additive, 2 = subtractive/special.
            # Do NOT force partial alpha from transparency_hint alone —
            # only honour explicit alpha < 1.0 set by CTRL_MESH_ALPHA or node.alpha.

            # Apply animated alpha from pose (CTRL_MESH_ALPHA=132)
            if self._anim_pose is not None:
                _pn_flat = self._anim_pose.nodes.get(node.name.lower())
                if _pn_flat is not None and _pn_flat.alpha is not None:
                    node_alpha = _clamp(_pn_flat.alpha, 0.0, 1.0)

            # ── Cloth/dangly mesh: teal tint to visually distinguish cloth ──
            # Dangly (cloth) nodes get a distinctive teal colour overlay so
            # modders can immediately see which geometry has cloth simulation.
            is_cloth = node.is_dangly
            # Two-sided: cloth/dangly + transparent materials skip backface cull.
            # Also make face/head mesh nodes two-sided: KotOR head models have
            # inner-geometry (eyes, teeth, tongue) sitting INSIDE the face mesh.
            # Backface culling on the face can make interior geometry visible
            # from directions where the face mesh winding appears reversed (e.g.
            # looking upward through the mouth gap, or in some model orientations).
            # Rendering the face as two-sided prevents the "see-through" effect
            # without changing the depth-sort ordering.
            _nl_flat2 = node.name.lower()
            _is_face_mesh_flat = any(s in _nl_flat2 for s in _FACE_MESH_SUBSTRINGS)
            # BUG FIX v26: inner-geometry nodes (eyes, eyelids, teeth, tongue) sit
            # INSIDE the face mesh.  Without two-sided rendering their triangles are
            # back-face culled when viewed from outside the head (the eye normals
            # typically point inward/outward inconsistently).  Force two-sided so
            # they always contribute pixels after the tier-1 promotion draws them
            # over the opaque head mesh.
            _is_inner_geo_flat2 = any(s in _nl_flat2 for s in _INNER_GEO_SUBSTRINGS)
            is_two_sided_flat = (is_cloth
                                 or getattr(node, "transparency_hint", 0) in (1, 2)
                                 or _is_face_mesh_flat
                                 or _is_inner_geo_flat2)
            if is_cloth:
                # Teal shift: boost green+blue, reduce red
                r = max(20, r - 40)
                g = min(255, g + 60)
                b = min(255, b + 80)

            # ── Inner-geometry tier bump (eyes, teeth, eyelids, tongue) ─────
            # In KotOR heads, eye/teeth/eyelid nodes sit geometrically INSIDE the
            # head mesh (behind the eye-socket opening / mouth gap).  They have
            # transparency_hint=0 (opaque) just like the face mesh, so the standard
            # two-pass tier (0=opaque first, 1=transparent last) would lump them
            # together and rely purely on centroid depth to decide draw order.
            # Centroid depth alone fails here: the eyeball centroid may be computed
            # as FURTHER from the camera than the whole-head centroid, causing the
            # head mesh to be drawn LAST and paint over the eyeball.
            # Fix: promote these inner-geometry nodes to tier 1 so they are ALWAYS
            # drawn AFTER the opaque head/body mesh regardless of depth order.
            # The head mesh's geometric eye-socket opening then correctly exposes the
            # eyeball geometry underneath.
            _nl_flat = node.name.lower()
            # Inner-geometry tier bump: promote eye/teeth/tongue nodes to draw tier 1
            # (after opaque face mesh) so they show through socket/mouth openings.
            # BUG FIX v20: removed 'not node.is_skin' gate — in some K2 head models
            # (child_f, comm_a_m, p_carth, etc.) eyeball nodes ARE declared as skin
            # meshes (MESH|SKIN flags) rather than trimesh.  The old check prevented
            # these skin-type eyeballs from being promoted, causing them to be painter-
            # sorted behind the opaque face mesh and become invisible.  Now we check
            # ALL nodes (skin or not) for inner-geo naming, as long as they have a
            # non-null texture (deformation helpers with null textures won't match).
            _clean_tex_flat = _clean_tex_name(getattr(node, 'texture', '') or '')
            _has_tex_flat = bool(_clean_tex_flat and _clean_tex_flat.upper() not in ('NULL', ''))
            _is_inner_geo_flat = (
                _has_tex_flat
                and any(s in _nl_flat for s in _INNER_GEO_SUBSTRINGS)
                and int(getattr(node, 'transparency_hint', 0)) == 0
            )

            for fi, face in enumerate(node.faces):
                if len(face) < 3: continue
                v0, v1, v2 = face[0], face[1], face[2]
                if v0 >= nv or v1 >= nv or v2 >= nv:
                    continue
                # Skip degenerate (collapsed) faces with repeated vertex indices
                if v0 == v1 or v1 == v2 or v0 == v2:
                    continue

                wv0 = world_verts[v0]
                wv1 = world_verts[v1]
                wv2 = world_verts[v2]
                p0 = screen_verts[v0]
                p1 = screen_verts[v1]
                p2 = screen_verts[v2]
                if p0 is None or p1 is None or p2 is None:
                    continue

                # ── Backface culling (screen-space winding order) ────────
                # In screen space (Y-axis pointing DOWN), the cross product
                # sign convention is: winding < 0 → CCW (front-facing in
                # right-handed KotOR coordinates).  winding > 0 → CW = back.
                # We skip BACK-facing (winding > 0) when in solid/non-wireframe
                # mode.  Allow degenerate tris (winding ≈ 0) through to avoid
                # holes along silhouette edges.
                ex1 = p1[0] - p0[0]; ey1 = p1[1] - p0[1]
                ex2 = p2[0] - p0[0]; ey2 = p2[1] - p0[1]
                winding = ex1 * ey2 - ex2 * ey1
                # Skip back-facing (CW in screen-Y-down space)
                if winding > 0 and not self.show_wireframe and self.show_solid and not is_two_sided_flat:
                    continue

                # Use weighted-centroid depth: average is more stable than
                # min() for coplanar/nearly-coplanar faces (fixes bantha Z-fighting).
                # Small face-index jitter breaks ties deterministically.
                depth = (p0[2] + p1[2] + p2[2]) * 0.3333 + fi * 1e-7

                # Normal — use world-space normals for correct lighting
                if n_norms > max(v0, v1, v2):
                    nx = (world_norms[v0][0]+world_norms[v1][0]+world_norms[v2][0]) / 3.0
                    ny = (world_norms[v0][1]+world_norms[v1][1]+world_norms[v2][1]) / 3.0
                    nz = (world_norms[v0][2]+world_norms[v1][2]+world_norms[v2][2]) / 3.0
                    nl_len = math.sqrt(nx*nx+ny*ny+nz*nz)
                    if nl_len > 1e-9:
                        nx /= nl_len; ny /= nl_len; nz /= nl_len
                    norm = (nx, ny, nz)
                else:
                    norm = self._face_normal(wv0, wv1, wv2)

                lx, ly, lz = self._light_dir
                ndotl = _clamp(_dot(norm, (lx, ly, lz)), 0.0, 1.0)
                ndotl = max(ndotl, _clamp(-_dot(norm, (lx, ly, lz)), 0.0, 1.0) * (0.55 if is_two_sided_flat else 0.35))
                shade = self._ambient + (1.0 - self._ambient) * ndotl
                fill  = (int(r*shade), int(g*shade), int(b*shade))

                # Depth bias for transparent tris to sort after opaque at same depth
                sort_depth = depth - (1e-3 if node_alpha < 0.999 else 0.0)
                # UE-inspired: convert to sortable uint key for stable integer comparison
                sort_key = _float_to_sort_key(sort_depth)
                # Two-pass tier: opaque=0, transparent/additive=1.
                # Tier is the PRIMARY sort dimension — all opaque tris are drawn
                # before any transparent tri regardless of depth.  This prevents
                # transparent inner geometry (eyes, teeth) from rendering on top
                # of the opaque face mesh purely because of centroid-depth ordering.
                _th_flat = int(getattr(node, 'transparency_hint', 0))
                # Inner-geometry (eyes, eyelids, teeth) are promoted to tier 1
                # even when transparency_hint==0 so they draw AFTER the opaque
                # face/head mesh.  This exposes them through the eye-socket and
                # mouth-gap openings in the face geometry.
                _is_trans_flat = (_th_flat > 0 or node_alpha < 0.999 or _is_inner_geo_flat)
                _tier_flat = 1 if _is_trans_flat else 0
                tris.append((sort_key, ((p0[0],p0[1]), (p1[0],p1[1]), (p2[0],p2[1])), fill, is_sel, fi, node_alpha, _tier_flat))
                if len(tris) >= tri_cap:
                    break
            if len(tris) >= tri_cap:
                break

        # Two-pass sort: tier 0 (opaque) before tier 1 (transparent);
        # within each tier, back-to-front by depth; ties broken by face index.
        # This prevents transparent inner geometry (eyes, hair, teeth, gums)
        # from rendering on top of opaque face/body meshes when centroid depth
        # ordering alone would place them in front.
        tris.sort(key=lambda t: (t[6], -t[0], t[4]))

        for depth, pts, fill, is_sel, _fi, t_alpha, _tier in tris:
            flat = [pts[0][0],pts[0][1], pts[1][0],pts[1][1], pts[2][0],pts[2][1]]
            if self.show_solid:
                sel_fill = (min(fill[0]+30,255), min(fill[1]+50,255), fill[2]) if is_sel else fill
                if t_alpha < 0.999:
                    # Blend with background colour for transparent flat-shaded faces
                    bg = (18, 18, 40)
                    a = t_alpha
                    sel_fill = (int(sel_fill[0]*a + bg[0]*(1-a)),
                                int(sel_fill[1]*a + bg[1]*(1-a)),
                                int(sel_fill[2]*a + bg[2]*(1-a)))
                draw.polygon(flat, fill=sel_fill)
            if self.show_wireframe or is_sel:
                wire_col = _SEL[:3] if is_sel else _WIRE[:3]
                draw.polygon(flat, outline=wire_col)

        # NOTE: _draw_bones is called by render() with a fresh draw context.

    # ── Accelerated rasterizer (v10.5) ────────────────────────────────
    # Uses accel.py (Numba JIT tier 1 or NumPy tier 2) for 17–40× speedup
    # over the PIL AFFINE path.  Falls back to PIL if accel is unavailable.

    def _draw_mesh_accel(self, draw: 'ImageDraw.Draw',
                         img: 'Image.Image', W: int, H: int,
                         flat_only: bool = False) -> bool:
        """
        Batch rasterizer using the accel.py acceleration layer.

        When flat_only=True (interactive drag), uses flat_shade_frame_jit for
        maximum speed (~100 fps on high-poly models).
        When flat_only=False (textured idle), uses rasterize_frame_jit with
        per-triangle UV sampling.

        Returns True if the accel path ran, False if it should fall back to PIL.

        Architecture (v10.5):
        1. Collect world verts + UVs per node (same as _draw_mesh_textured).
        2. _proj_batch → NumPy vectorized screen projection.
        3. frustum_cull_np → vectorized AABB cull.
        4. sentinel_filter_np → vectorized UV sentinel filter (220× speedup).
        5. depth_sort_np → NumPy argsort (3× faster than Python sort).
        6. _accel_rasterize_frame / _accel_flat_shade_frame → batch rasterize.
        7. Convert NumPy framebuffer back to PIL for compositing.
        """
        if not _ACCEL_AVAILABLE or not _NUMPY:
            return False
        if not _PIL:
            return False

        cam       = self.cam
        light_dir = self._light_dir
        ambient   = self._ambient

        # Use accel cap (10k) for textured; interactive is also 10k (same limit)
        tri_cap = min(self._screen_size_lod_cap(W, H),
                      self.MAX_TRIS_TEXTURED_ACCEL if not flat_only
                      else self.MAX_TRIS_INTERACTIVE)

        # ── 1. Allocate NumPy framebuffer ─────────────────────────────────
        # We maintain a separate NumPy (H, W, 4) RGBA buffer so the JIT
        # rasterizer can write pixels directly without PIL overhead.
        # Pre-fill with the viewport background colour.
        bg_r, bg_g, bg_b = _BG[:3]
        buf = np.empty((H, W, 4), dtype=np.uint8)
        buf[:, :, 0] = bg_r
        buf[:, :, 1] = bg_g
        buf[:, :, 2] = bg_b
        buf[:, :, 3] = 255

        # Copy existing img pixels (e.g. grid) into buf so grid is preserved
        try:
            existing = np.array(img, dtype=np.uint8)
            if existing.shape == (H, W, 4):
                buf[:] = existing
            elif existing.shape == (H, W, 3):
                buf[:, :, :3] = existing
                buf[:, :, 3] = 255
        except Exception:
            pass  # If img copy fails, use plain bg (grid will be redrawn after)

        # ── 2. Collect all visible triangles ─────────────────────────────
        # Per-node arrays are built then concatenated at the end for the batch call.
        # For multi-texture models we make one rasterize_frame call per texture batch.
        # For simplicity in v10.5 we store: [(tex_arr, verts_sx, verts_sy, uvs_u,
        #   uvs_v, fv0, fv1, fv2, depths, shade_r, shade_g, shade_b, alphas), ...]
        # One entry per (node, texture) pair.
        batches = []   # list of dicts, one per unique (node, texture)

        total_tris = 0
        wire_tris  = []  # [(flat_pts, wire_col), ...]

        # v6.0 FIX: Module UV sentinel workaround removed.  _UV_SENTINEL is now
        # set to 1e18 (effectively disabled), so there is no need for a separate
        # module-specific threshold.  All UV magnitudes are valid; the software
        # rasterizer uses frac() (GL_REPEAT) to wrap UVs correctly.
        # Cross-ref: KotOR.js TextureLoader.ts -- default is RepeatWrapping.
        _accel_model_cls = (str(getattr(self.model, 'classification', 'character') or 'character')).lower() if self.model else 'character'
        _accel_mtype_raw = getattr(self.model, 'model_type', None) if self.model else None
        _accel_mtype = int(_accel_mtype_raw) if _accel_mtype_raw is not None else 4
        _accel_is_module = (_accel_model_cls in ('effect', 'tile', 'other') or _accel_mtype in (0, 2))
        _accel_uv_sentinel = _UV_SENTINEL

        for node in self._iter_visible_mesh_nodes():
            if not node.vertices or not node.faces:
                continue
            if total_tris >= tri_cap:
                break

            verts   = node.vertices
            nv      = len(verts)
            uvs     = node.uvs if not flat_only else []
            n_uvs   = len(uvs)
            face_uvs_list = getattr(node, 'face_uvs', [])
            _has_face_uvs = bool(face_uvs_list) and len(face_uvs_list) == len(node.faces)
            has_uvs = (n_uvs > 0) and not flat_only
            is_sel  = (node is self.selected_node)

            # ── World transform + projection ──────────────────────────────
            _node_id = id(node)
            _fvc = getattr(self, '_frame_verts_cache', None)
            _fnc = getattr(self, '_frame_norms_cache', None)
            if _fvc is not None and _node_id in _fvc:
                world_verts = _fvc[_node_id]
            else:
                world_verts = self._get_world_verts_for_node(node)
                if _fvc is not None:
                    _fvc[_node_id] = world_verts

            if _fnc is not None and _node_id in _fnc:
                world_norms = _fnc[_node_id]
            else:
                world_norms = self._get_world_normals_for_node(node)
                if _fnc is not None:
                    _fnc[_node_id] = world_norms
            n_norms = len(world_norms)

            if n_norms == 0 and world_verts and node.faces:
                world_norms = self._compute_area_weighted_normals(node.faces, world_verts)
                n_norms = len(world_norms)

            # ── Batch project all vertices via NumPy ─────────────────────
            screen_verts_t = self._proj_batch(world_verts, W, H)
            # Build sx/sy/valid arrays
            sv_sx = np.full(nv, -9999, dtype=np.int32)
            sv_sy = np.full(nv, -9999, dtype=np.int32)
            sv_cz = np.zeros(nv, dtype=np.float32)
            sv_ok = np.zeros(nv, dtype=np.bool_)
            for i, p in enumerate(screen_verts_t):
                if p is not None:
                    sv_sx[i], sv_sy[i], sv_cz[i] = p
                    sv_ok[i] = True

            # ── Per-node texture & diffuse colour ─────────────────────────
            _use_lq = self._lq_tex_mode
            # FIX-LMROUTE: When has_lightmap=True, tex_count==2 means
            # slot 0 = diffuse and slot 1 = lightmap.  The lightmap is
            # composited as a separate multiply pass (not per-face material).
            # Treating lightmapped nodes as multi-texture causes face_mats[i]=1
            # to route ALL faces to the lightmap image as their diffuse texture,
            # which is the "texture-to-face routing" bug (D5).  xoreos and
            # KotOR.js both handle textureIndex==1 as lightmap, not per-face
            # material selection.
            _node_has_lightmap_accel = bool(getattr(node, 'has_lightmap', False))
            _node_is_multitex = (getattr(node, 'tex_count', 1) > 1
                                 and bool(getattr(node, 'face_mats', []))
                                 and bool(getattr(node, 'texture_names', []))
                                 and not _node_has_lightmap_accel)
            node_alpha = float(_clamp(getattr(node, 'alpha', 1.0), 0.0, 1.0))
            # transparency_hint is a render-mode flag, not an alpha override.
            # Only explicit node.alpha < 1 or CTRL_MESH_ALPHA animation sets transparency.

            # Animation overrides
            if self._anim_pose is not None:
                _pn = self._anim_pose.nodes.get(node.name.lower())
                if _pn is not None and _pn.alpha is not None:
                    node_alpha = _clamp(_pn.alpha, 0.0, 1.0)

            clean_tex = _clean_tex_name(node.texture)
            if not clean_tex or clean_tex.upper() in ('NULL', ''):
                diff = (0.55, 0.55, 0.65)
            else:
                diff = (
                    _clamp(node.diffuse[0], 0.0, 1.0),
                    _clamp(node.diffuse[1], 0.0, 1.0),
                    _clamp(node.diffuse[2], 0.0, 1.0),
                )

            selfillum = getattr(node, 'selfillum', (0.0, 0.0, 0.0))
            if self._anim_pose is not None:
                _pn_si = self._anim_pose.nodes.get(node.name.lower())
                if _pn_si is not None and _pn_si.selfillum is not None:
                    selfillum = _pn_si.selfillum
            si_boost = max(selfillum)

            # Get single-tex image + array once per node
            if not flat_only and not _node_is_multitex and has_uvs:
                _raw_tex = self._get_tex(node)
                _pil_tex = self.tex_cache.get_mip1(_raw_tex) if (_use_lq and _raw_tex) else _raw_tex
                _tex_arr = self._tex_arr_cache.get(_pil_tex) if _pil_tex else None
            else:
                _pil_tex = None
                _tex_arr = None

            transp_hint = getattr(node, 'transparency_hint', 0)
            _nl_accel = node.name.lower()
            _is_face_accel = any(s in _nl_accel for s in _FACE_MESH_SUBSTRINGS)
            # BUG FIX v26: inner-geo nodes two-sided in accel path too
            _is_inner_geo_accel = any(s in _nl_accel for s in _INNER_GEO_SUBSTRINGS)
            is_two_sided = (node.is_dangly
                            or transp_hint in (1, 2)
                            or _is_face_accel
                            or _is_inner_geo_accel)

            # ── Per-node TXI features (Phase 18-C) ────────────────────────
            # TXI clamp_s/clamp_t: apply GL_CLAMP_TO_EDGE on the relevant axis.
            # This makes the accel path match the PIL path for clamped textures.
            _accel_clamp_s = bool(getattr(node, 'txi_clamp_s', False))
            _accel_clamp_t = bool(getattr(node, 'txi_clamp_t', False))
            # UV animation (animate_uv): add time-based scroll offset.
            _accel_animate_uv = bool(getattr(node, 'animate_uv', False))
            _accel_uv_scroll_u = 0.0
            _accel_uv_scroll_v = 0.0
            if _accel_animate_uv:
                _accel_uv_dir_x = float(getattr(node, 'uv_dir_x', 0.0) or 0.0)
                _accel_uv_dir_y = float(getattr(node, 'uv_dir_y', 0.0) or 0.0)
                _accel_uv_jitter = float(getattr(node, 'uv_jitter', 0.0) or 0.0)
                _accel_uv_jitter_spd = float(getattr(node, 'uv_jitter_speed', 0.0) or 0.0)
                _t_anim = getattr(self, '_anim_time', 0.0)
                if _accel_uv_dir_x != 0.0 or _accel_uv_dir_y != 0.0:
                    _accel_uv_scroll_u = _accel_uv_dir_x * _t_anim
                    _accel_uv_scroll_v = _accel_uv_dir_y * _t_anim
                if _accel_uv_jitter != 0.0 and _accel_uv_jitter_spd > 0.0:
                    import random as _random
                    _jitter = _random.uniform(-_accel_uv_jitter, _accel_uv_jitter)
                    _accel_uv_scroll_u += _jitter
                    _accel_uv_scroll_v += _jitter
            # rotatetexture: rotate UV 90° CCW = (u, v) → (v, 1-u)
            _accel_rotate_tex = bool(getattr(node, 'rotatetexture', False)
                                     or getattr(node, 'rotate_texture', False))

            # ── Per-face loop ─────────────────────────────────────────────
            # Build per-face arrays for this node's triangles
            face_x0 = []; face_y0 = []; face_x1 = []; face_y1 = []
            face_x2 = []; face_y2 = []
            face_u0 = []; face_v0_l = []; face_u1 = []; face_v1_l = []
            face_u2 = []; face_v2_l = []
            face_sr = []; face_sg = []; face_sb = []
            face_alpha = []
            face_depths = []
            face_is_sel = []
            face_tex_arr = []   # per-face tex array (for multi-tex)
            fi_insert = []      # insertion order for Z-tie breaking

            for _fi, face in enumerate(node.faces):
                if len(face) < 3:
                    continue
                vi0, vi1, vi2 = face[0], face[1], face[2]
                if vi0 == vi1 or vi1 == vi2 or vi0 == vi2:
                    continue
                if vi0 >= nv or vi1 >= nv or vi2 >= nv:
                    continue
                if not (sv_ok[vi0] and sv_ok[vi1] and sv_ok[vi2]):
                    continue

                p0 = (sv_sx[vi0], sv_sy[vi0], sv_cz[vi0])
                p1 = (sv_sx[vi1], sv_sy[vi1], sv_cz[vi1])
                p2 = (sv_sx[vi2], sv_sy[vi2], sv_cz[vi2])

                # Backface cull
                ex1 = p1[0]-p0[0]; ey1 = p1[1]-p0[1]
                ex2 = p2[0]-p0[0]; ey2 = p2[1]-p0[1]
                winding = ex1*ey2 - ex2*ey1
                if winding > 0 and not self.show_wireframe and self.show_solid and not is_two_sided:
                    continue

                fi_local = len(face_depths)
                depth = (p0[2] + p1[2] + p2[2]) * 0.3333 + fi_local * 1e-7

                # ── UV resolve ────────────────────────────────────────────
                if has_uvs and not flat_only:
                    if _has_face_uvs:
                        fuv = face_uvs_list[_fi]
                        ti0, ti1, ti2 = fuv[0], fuv[1], fuv[2]
                    else:
                        ti0, ti1, ti2 = vi0, vi1, vi2
                    uv0 = uvs[ti0] if ti0 < n_uvs else (0.5, 0.5)
                    uv1 = uvs[ti1] if ti1 < n_uvs else (0.5, 0.5)
                    uv2 = uvs[ti2] if ti2 < n_uvs else (0.5, 0.5)

                    # v6.0 FIX: UV sentinel guard effectively disabled.
                    # Only NaN/Inf is filtered.  All legitimate UV magnitudes
                    # are handled by the frac()-based GL_REPEAT wrapping.
                    _uv_sum = (uv0[0] + uv0[1] + uv1[0] + uv1[1] + uv2[0] + uv2[1])
                    if _uv_sum != _uv_sum:  # NaN check (NaN != NaN)
                        continue

                    u0r, u1r, u2r = uv0[0], uv1[0], uv2[0]
                    v0r, v1r, v2r = uv0[1], uv1[1], uv2[1]

                    # ── Phase 18-C: TXI clamp (GL_CLAMP_TO_EDGE) ─────────────
                    # Clamp UVs to [0, 1-eps] on axes that have TXI clamp set.
                    # The upper bound is 1-eps (not 1.0) because the accel rasterizer
                    # applies frac() per pixel: frac(1.0)=0.0 would sample the wrong
                    # edge. GL_CLAMP_TO_EDGE should sample the LAST texel, so we
                    # clamp to TW-1/TW ≈ 0.9990... Using a small epsilon is correct.
                    # This prevents tiling on head textures, decals, etc.
                    # Also skip the seam fix on clamped axes (no tiling = no seam).
                    _CLAMP_MAX = 0.9999  # just below 1.0 so frac() stays near edge
                    if _accel_clamp_s:
                        u0r = max(0.0, min(_CLAMP_MAX, u0r))
                        u1r = max(0.0, min(_CLAMP_MAX, u1r))
                        u2r = max(0.0, min(_CLAMP_MAX, u2r))
                    if _accel_clamp_t:
                        v0r = max(0.0, min(_CLAMP_MAX, v0r))
                        v1r = max(0.0, min(_CLAMP_MAX, v1r))
                        v2r = max(0.0, min(_CLAMP_MAX, v2r))

                    # ── Phase 18-D: rotatetexture (90° CCW UV rotation) ───────
                    # KotOR rotatetexture: (u, v) → (v, 1-u)
                    if _accel_rotate_tex:
                        u0r, v0r = v0r, 1.0 - u0r
                        u1r, v1r = v1r, 1.0 - u1r
                        u2r, v2r = v2r, 1.0 - u2r

                    # ── Phase 18-D: UV animation (animate_uv scroll) ──────────
                    # Add time-based scroll offset. The accel rasterizer's frac()
                    # handles modulo wrap automatically, so no clamping needed here.
                    if _accel_uv_scroll_u != 0.0:
                        u0r += _accel_uv_scroll_u
                        u1r += _accel_uv_scroll_u
                        u2r += _accel_uv_scroll_u
                    if _accel_uv_scroll_v != 0.0:
                        v0r += _accel_uv_scroll_v
                        v1r += _accel_uv_scroll_v
                        v2r += _accel_uv_scroll_v

                    # Seam fix (reuse existing helpers)
                    # Only apply when span < 1.0 — multi-tile faces (span >= 1.0)
                    # are handled by the accel rasterizer's frac() UV wrapping and
                    # must NOT be seam-fixed (would collapse tile range to zero span).
                    # Also skip on clamped axes (clamp + seam fix would interfere).
                    raw_span_u = max(u0r, u1r, u2r) - min(u0r, u1r, u2r)
                    raw_span_v = max(v0r, v1r, v2r) - min(v0r, v1r, v2r)
                    if raw_span_u < 1.0 and not _accel_clamp_s:
                        u_has_seam = (_edge_has_seam_global(u0r, u1r) or
                                      _edge_has_seam_global(u0r, u2r) or
                                      _edge_has_seam_global(u1r, u2r))
                        if u_has_seam:
                            u1r = _uwrap_global(u0r, u1r)
                            u2r = _uwrap_global(u0r, u2r)
                    if raw_span_v < 1.0 and not _accel_clamp_t:
                        v_has_seam = (_edge_has_seam_global(v0r, v1r) or
                                      _edge_has_seam_global(v0r, v2r) or
                                      _edge_has_seam_global(v1r, v2r))
                        if v_has_seam:
                            v1r = _uwrap_global(v0r, v1r)
                            v2r = _uwrap_global(v0r, v2r)
                    uv0 = (u0r, v0r); uv1 = (u1r, v1r); uv2 = (u2r, v2r)

                    # Multi-tex face texture
                    if _node_is_multitex:
                        _raw_ft = self._get_tex_for_face(node, _fi)
                        _pil_ft = self.tex_cache.get_mip1(_raw_ft) if (_use_lq and _raw_ft) else _raw_ft
                        _ta = self._tex_arr_cache.get(_pil_ft) if _pil_ft else None
                    else:
                        _ta = _tex_arr
                    face_tex_arr.append(_ta)
                else:
                    uv0 = uv1 = uv2 = (0.5, 0.5)
                    face_tex_arr.append(None)

                # ── Per-face lighting ─────────────────────────────────────
                if n_norms > max(vi0, vi1, vi2):
                    nx = (world_norms[vi0][0] + world_norms[vi1][0] + world_norms[vi2][0]) / 3.0
                    ny = (world_norms[vi0][1] + world_norms[vi1][1] + world_norms[vi2][1]) / 3.0
                    nz = (world_norms[vi0][2] + world_norms[vi1][2] + world_norms[vi2][2]) / 3.0
                    nl = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if nl > 1e-9:
                        nx /= nl; ny /= nl; nz /= nl
                else:
                    wv0 = world_verts[vi0]; wv1 = world_verts[vi1]; wv2 = world_verts[vi2]
                    fnorm = self._face_normal(wv0, wv1, wv2)
                    nx, ny, nz = fnorm

                ndotl = nx*light_dir[0] + ny*light_dir[1] + nz*light_dir[2]
                ndotl_f = max(0.0, ndotl) + max(0.0, -ndotl) * (0.55 if is_two_sided else 0.35)
                shade = ambient + (1.0 - ambient) * ndotl_f
                shade = max(shade, si_boost)

                dr, dg, db = diff
                shade_r = int(_clamp(shade * (0.5 + dr*0.5) * 255, 0, 255))
                shade_g = int(_clamp(shade * (0.5 + dg*0.5) * 255, 0, 255))
                shade_b = int(_clamp(shade * (0.5 + db*0.5) * 255, 0, 255))

                face_x0.append(int(p0[0])); face_y0.append(int(p0[1]))
                face_x1.append(int(p1[0])); face_y1.append(int(p1[1]))
                face_x2.append(int(p2[0])); face_y2.append(int(p2[1]))
                face_u0.append(uv0[0]); face_v0_l.append(uv0[1])
                face_u1.append(uv1[0]); face_v1_l.append(uv1[1])
                face_u2.append(uv2[0]); face_v2_l.append(uv2[1])
                face_sr.append(shade_r); face_sg.append(shade_g); face_sb.append(shade_b)
                face_alpha.append(node_alpha)
                face_depths.append(depth)
                face_is_sel.append(is_sel)
                fi_insert.append(fi_local)

                total_tris += 1
                if total_tris >= tri_cap:
                    break
            if not face_depths:
                if total_tris >= tri_cap:
                    break
                continue

            # ── Sort and rasterize this node's batch ──────────────────────
            NF = len(face_depths)
            depths_arr = np.array(face_depths, dtype=np.float32)
            order = _accel_depth_sort(depths_arr)  # back-to-front indices

            # Build sorted arrays
            sx0 = np.array(face_x0, dtype=np.int64)[order]
            sy0 = np.array(face_y0, dtype=np.int64)[order]
            sx1 = np.array(face_x1, dtype=np.int64)[order]
            sy1 = np.array(face_y1, dtype=np.int64)[order]
            sx2 = np.array(face_x2, dtype=np.int64)[order]
            sy2 = np.array(face_y2, dtype=np.int64)[order]

            # Frustum cull
            sc_x = np.stack([sx0, sx1, sx2], axis=1)
            sc_y = np.stack([sy0, sy1, sy2], axis=1)
            visible = _accel_frustum_cull(sc_x, sc_y, W, H)

            sr_arr = np.array(face_sr, dtype=np.int64)[order]
            sg_arr = np.array(face_sg, dtype=np.int64)[order]
            sb_arr = np.array(face_sb, dtype=np.int64)[order]
            alpha_arr = np.array(face_alpha, dtype=np.float64)[order]

            # Determine whether to use textured or flat pass.
            # Use textured pass when:
            #   1. NOT in flat_only (interactive drag) mode, AND
            #   2. Either the node-level _tex_arr is set (single-tex fast path),
            #      OR at least one face in face_tex_arr has a texture (multi-tex
            #      OR case where the cache was just populated during prewarm).
            # Previously this condition was `flat_only or _tex_arr is None` which
            # meant multi-texture nodes ALWAYS rendered flat because _tex_arr is
            # intentionally None for those nodes (line ~5088).  It also meant
            # single-tex nodes fell to flat if the texture array hadn't been
            # converted to NumPy yet (TexArrayCache miss on first frame).
            _any_tex_arr = (_tex_arr is not None or
                            any(t is not None for t in face_tex_arr))
            if flat_only or not _any_tex_arr:
                # ── Flat shade pass ────────────────────────────────────────
                # Build synthetic per-vertex arrays for single flat triangle
                # rasterization: vertex 0 = p0, vertex 1 = p1, vertex 2 = p2,
                # face references vertex indices 0,1,2 directly.
                # We abuse the flat_shade_frame API which expects global vertex arrays.
                # Build (3*NF,) vertex arrays with one triangle per 3 vertices.
                _nx = NF
                all_sx = np.empty(_nx * 3, dtype=np.int64)
                all_sy = np.empty(_nx * 3, dtype=np.int64)
                all_sx[0::3] = sx0; all_sy[0::3] = sy0
                all_sx[1::3] = sx1; all_sy[1::3] = sy1
                all_sx[2::3] = sx2; all_sy[2::3] = sy2
                fv0 = np.arange(0, _nx*3, 3, dtype=np.int64)
                fv1 = fv0 + 1
                fv2 = fv0 + 2
                fr_arr = np.clip(sr_arr, 0, 255).astype(np.uint8)
                fg_arr = np.clip(sg_arr, 0, 255).astype(np.uint8)
                fb_arr = np.clip(sb_arr, 0, 255).astype(np.uint8)
                _accel_flat_shade_frame(buf, all_sx, all_sy, fv0, fv1, fv2,
                                        fr_arr, fg_arr, fb_arr, visible)
            else:
                # ── Textured pass ──────────────────────────────────────────
                # Group sorted faces by their texture array.
                # In the common single-texture case this is one group.
                # Faces with None texture fall back to flat-shade within
                # this same pass (avoids a separate flat-shade call for models
                # that have a mix of textured and untextured faces).
                ordered_tex = [face_tex_arr[i] for i in order]
                u0a = np.array(face_u0, dtype=np.float64)[order]
                v0a = np.array(face_v0_l, dtype=np.float64)[order]
                u1a = np.array(face_u1, dtype=np.float64)[order]
                v1a = np.array(face_v1_l, dtype=np.float64)[order]
                u2a = np.array(face_u2, dtype=np.float64)[order]
                v2a = np.array(face_v2_l, dtype=np.float64)[order]

                # Build 3*NF vertex arrays for the batch call
                _nx = NF
                all_sx = np.empty(_nx * 3, dtype=np.int64)
                all_sy = np.empty(_nx * 3, dtype=np.int64)
                all_sx[0::3] = sx0; all_sy[0::3] = sy0
                all_sx[1::3] = sx1; all_sy[1::3] = sy1
                all_sx[2::3] = sx2; all_sy[2::3] = sy2
                # Per-vertex UV (one per triangle-vertex)
                all_uu = np.empty(_nx * 3, dtype=np.float64)
                all_vv = np.empty(_nx * 3, dtype=np.float64)
                all_uu[0::3] = u0a; all_uu[1::3] = u1a; all_uu[2::3] = u2a
                all_vv[0::3] = v0a; all_vv[1::3] = v1a; all_vv[2::3] = v2a
                fv0 = np.arange(0, _nx*3, 3, dtype=np.int64)
                fv1 = fv0 + 1
                fv2 = fv0 + 2

                # Group by texture for batch calls.
                # Most nodes are single-texture → one call.
                # Faces with None texture get a flat-shade call instead.
                prev_tex = None
                group_start = 0
                _flat_vis_list = []   # indices of visible None-tex faces for flat fallback
                for gi in range(NF + 1):
                    cur_tex = ordered_tex[gi] if gi < NF else None
                    if cur_tex is not prev_tex or gi == NF:
                        # Flush previous group
                        if gi > group_start:
                            g_sl = slice(group_start, gi)
                            g_fv0 = fv0[g_sl]; g_fv1 = fv1[g_sl]; g_fv2 = fv2[g_sl]
                            if prev_tex is not None:
                                _accel_rasterize_frame(
                                    buf, prev_tex,
                                    all_sx, all_sy,
                                    all_uu, all_vv,
                                    g_fv0, g_fv1, g_fv2,
                                    sr_arr[g_sl], sg_arr[g_sl], sb_arr[g_sl],
                                    alpha_arr[g_sl],
                                    visible[g_sl],
                                )
                            else:
                                # No texture for this group — render as flat-shade
                                fr_g = np.clip(sr_arr[g_sl], 0, 255).astype(np.uint8)
                                fg_g = np.clip(sg_arr[g_sl], 0, 255).astype(np.uint8)
                                fb_g = np.clip(sb_arr[g_sl], 0, 255).astype(np.uint8)
                                _accel_flat_shade_frame(
                                    buf, all_sx, all_sy,
                                    g_fv0, g_fv1, g_fv2,
                                    fr_g, fg_g, fb_g,
                                    visible[g_sl],
                                )
                        prev_tex   = cur_tex
                        group_start = gi

            # Collect wireframe data
            if self.show_wireframe or is_sel:
                for idx_sorted in range(NF):
                    if not visible[idx_sorted]:
                        continue
                    flat = [int(sx0[idx_sorted]), int(sy0[idx_sorted]),
                            int(sx1[idx_sorted]), int(sy1[idx_sorted]),
                            int(sx2[idx_sorted]), int(sy2[idx_sorted])]
                    orig_is_sel = face_is_sel[order[idx_sorted]]
                    wire_col = _SEL[:3] if orig_is_sel else _WIRE[:3]
                    wire_tris.append((flat, wire_col))

            if total_tris >= tri_cap:
                break

        # ── 3. Convert NumPy buffer back to PIL ───────────────────────────
        try:
            result_img = Image.fromarray(buf, 'RGBA')
            # Blit result into img in-place
            img.paste(result_img, (0, 0))
        except Exception as exc:
            log.debug(f"_draw_mesh_accel: PIL conversion failed ({exc})")
            return False

        # ── 4. Wireframe pass ─────────────────────────────────────────────
        if wire_tris:
            draw2 = ImageDraw.Draw(img)
            for flat, wire_col in wire_tris:
                draw2.polygon(flat, outline=wire_col)

        return True  # accel path ran successfully

    # ── Full UV-mapped textured renderer (fast PIL-based) ──────────────

    def _draw_mesh_textured(self, draw: 'ImageDraw.Draw',
                             img: 'Image.Image', W: int, H: int):
        """
        UV-mapped textured rendering using PIL AFFINE transform per triangle.

        Strategy:
        1. Collect ALL triangles from visible nodes with world-space vertices,
           UVs, normals and depth → sort back-to-front (painter's algorithm)
        2. For each triangle with a loaded texture:
           a. Compute per-face lighting (center normal dot light)
           b. Use _paste_textured_triangle() with PIL AFFINE transform for
              proper per-pixel UV interpolation (no pixelation from centroid sampling)
           c. Modulate with per-face lighting shade color
        3. For triangles WITHOUT a loaded texture: flat-fill with diffuse color

        The AFFINE warp correctly maps the texture onto each triangle using bilinear
        sampling, eliminating the pixelation caused by the old centroid-only approach.
        """
        cam = self.cam
        light_dir = self._light_dir
        ambient   = self._ambient

        # Use reduced tri cap during interactive drag for fast viewport response
        # For textured mode use a smaller cap (PIL affine per-tri is slow)
        tri_cap = min(self._screen_size_lod_cap(W, H), self.MAX_TRIS_TEXTURED)

        # ── Collect all triangles ────────────────────────────────────────
        # Entry: (depth, screen_pts, fill_rgb, tex_img, uv0, uv1, uv2, is_sel)
        tris = []

        for node in self._iter_visible_mesh_nodes():
            if not node.vertices or not node.faces:
                continue

            verts   = node.vertices
            nv      = len(verts)
            uvs     = node.uvs
            n_uvs   = len(uvs)
            # face_uvs: per-face tvert index triples (ASCII MDL only).
            # When present, uvs[face_uvs[fi][k]] gives the UV for face fi, vertex k.
            # When absent (binary MDL), use vertex indices directly.
            face_uvs_list = getattr(node, 'face_uvs', [])
            _has_face_uvs = bool(face_uvs_list) and len(face_uvs_list) == len(node.faces)
            n_norms = 0        # will be set after world_norms computed
            has_uvs = (n_uvs > 0)
            is_sel  = (node is self.selected_node)

            # Multi-texture support: does this node use per-face texture selection?
            # tex_count > 1 means face_mats[i] indexes into texture_names[slot].
            # Single-texture fast-path: pre-resolve once per node.
            _node_tex_count = getattr(node, 'tex_count', 1)
            # FIX-LMROUTE-V2: Determine lightmap status BEFORE multitex check.
            # _node_has_lm must be computed here (not later at lightmap-setup)
            # because _node_is_multitex depends on it.  The original code defined
            # _node_has_lm 17 lines AFTER its first use, causing a NameError on
            # the first loop iteration and stale-value bugs on subsequent nodes.
            # This was the root cause of the D5 texture-to-face routing bug in
            # the PIL AFFINE fallback path (_draw_mesh_textured).
            _node_has_lm = bool(getattr(node, 'has_lightmap', False))
            # FIX-LMROUTE: Lightmapped nodes (has_lightmap=True) must NOT
            # be treated as multi-texture even when tex_count==2.  In KotOR,
            # slot 1 is the lightmap (composited via UV1 multiply pass), not a
            # per-face material variant.  face_mats[i]==1 on lightmapped nodes
            # means "this face has a lightmap", NOT "use texture_names[1] as
            # diffuse".  Without this guard, _get_tex_for_face routes all faces
            # to the lightmap image as their primary diffuse texture, producing
            # the D5 "texture-to-face routing" bug.
            # Reference: xoreos setupShaderTexture (textureIndex==1 → LIGHTMAP,
            #            not per-face material); KotOR.js textureMap2 = lightmap.
            _node_is_multitex = (_node_tex_count > 1
                                 and bool(getattr(node, 'face_mats', []))
                                 and bool(getattr(node, 'texture_names', []))
                                 and not _node_has_lm)
            # For single-texture nodes resolve once; multi-tex resolves per face.
            # PERF-FIX (v10.2): When _lq_tex_mode is active (first frame after drag
            # release), use mip1 (half-res) textures to halve the PIL AFFINE warp
            # cost.  TextureCache.get_mip1() is O(1) after the first access.
            _use_lq = self._lq_tex_mode  # FIX (v10.4): now always a real attr
            if not _node_is_multitex and has_uvs:
                _raw_tex = self._get_tex(node)
                tex_img = self.tex_cache.get_mip1(_raw_tex) if (_use_lq and _raw_tex is not None) else _raw_tex
            else:
                tex_img = None

            # ── Lightmap setup ─────────────────────────────────────────────
            # KotOR lightmaps: has_lightmap=True means node.lightmap holds the
            # lightmap texture name; node.uvs_lm holds per-vertex lightmap UVs.
            # We load the lightmap image once per node and composite it as a
            # multiply pass (overbright ×2) after the diffuse pass.
            # NOTE: _node_has_lm was already computed above (FIX-LMROUTE-V2)
            # for the multitex check.  No need to re-compute here.
            _lm_tex_name   = str(getattr(node, 'lightmap', ''))
            _uvs_lm        = getattr(node, 'uvs_lm', [])
            _n_uvs_lm      = len(_uvs_lm)
            _has_lm_uvs    = (_n_uvs_lm > 0)
            lm_img = None
            if _node_has_lm and _lm_tex_name and _has_lm_uvs:
                lm_img = self._get_tex_by_name(_lm_tex_name)

            # ── Environment map setup (TXI envmaptexture) ──────────────────
            # When TXI defines 'envmaptexture <name>', the diffuse texture alpha
            # channel is the blend weight between the surface colour and the env map.
            # We load the env-map texture here for use in _apply_envmap_to_patch()
            # called per-triangle after the diffuse paste.
            # Note: _apply_kotor_alpha now PRESERVES the alpha channel for env-map
            # textures so the blend weight survives into the rasteriser.
            _node_env_tex_name = str(getattr(node, 'txi_envmaptexture', '')).strip().lower()
            _env_img = self._get_tex_by_name(_node_env_tex_name) if _node_env_tex_name else None


            node_alpha = float(getattr(node, 'alpha', 1.0))
            node_alpha = _clamp(node_alpha, 0.0, 1.0)
            # Full transparency hint pipeline (sourced from xoreos modelnode.cpp):
            #   transparency_hint == 0  → render OPAQUE even if texture has alpha
            #                            (KotOR convention: 0 = opaque/punch-through)
            #   transparency_hint == 1  → TRANSPARENT (alpha-blend, src_alpha blending)
            #   transparency_hint >= 2  → engine-side glass/additive; treat as semi-transparent
            #   beaming == True         → additive glow (handled above via _node_txi_blending=1)
            # The hint only affects default alpha — explicit CTRL_MESH_ALPHA (132) controller
            # values always override it.
            _transp_hint = int(getattr(node, 'transparency_hint', 0))
            # transparency_hint is a render-mode flag ONLY — do NOT force partial
            # alpha from it.  Real glass/additive uses explicit CTRL_MESH_ALPHA (132)
            # or txi_blending flags.  Many KotOR skin meshes have hint=1 but are
            # fully opaque (bump/specular data in DXT5 alpha channel, not transparency).
            # transparency_hint >= 2 is an engine render-mode flag only — do NOT
            # force partial alpha from it.  Real glass/additive uses explicit
            # CTRL_MESH_ALPHA or txi_blending flags.

            # ── Animation overrides: alpha and selfillum from pose ──────────
            # CTRL_MESH_ALPHA (132) and CTRL_MESH_SELFILLUMCOLOR (100) are material
            # controllers that animate per-node opacity and glow independently of
            # skeletal motion.  KotOR uses these heavily for droid eye blinks,
            # glass flickering, and fire/energy FX self-illumination pulses.
            if self._anim_pose is not None:
                _pn_mat = self._anim_pose.nodes.get(node.name.lower())
                if _pn_mat is not None:
                    if _pn_mat.alpha is not None:
                        node_alpha = _clamp(_pn_mat.alpha, 0.0, 1.0)
                    # selfillum will be applied below after 'selfillum' is assigned

            # Base diffuse color fallback
            clean_tex = _clean_tex_name(node.texture)
            if not clean_tex or clean_tex.upper() in ('NULL', ''):
                diff = (0.55, 0.55, 0.65)
            else:
                diff = (
                    _clamp(node.diffuse[0], 0.0, 1.0),
                    _clamp(node.diffuse[1], 0.0, 1.0),
                    _clamp(node.diffuse[2], 0.0, 1.0),
                )

            selfillum = getattr(node, 'selfillum', (0.0, 0.0, 0.0))

            # Apply animated selfillum from pose (CTRL_MESH_SELFILLUMCOLOR=100)
            if self._anim_pose is not None:
                _pn_si = self._anim_pose.nodes.get(node.name.lower())
                if _pn_si is not None and _pn_si.selfillum is not None:
                    selfillum = _pn_si.selfillum

            # ── UV scroll (animate_uv) ─────────────────────────────────────
            # When animate_uv is True, texture scrolls at (uv_dir_x, uv_dir_y)
            # units/sec.  We offset all UVs by current_time * direction each frame.
            # uv_jitter adds a sinusoidal perturbation for water/lava shimmer.
            # Reference: KotorBlender io_scene_kotor/mdl_data.py TrimeshNode fields.
            _node_animate_uv   = bool(getattr(node, 'animate_uv', False))
            _node_uv_dir_x     = float(getattr(node, 'uv_dir_x', 0.0))
            _node_uv_dir_y     = float(getattr(node, 'uv_dir_y', 0.0))
            _node_uv_jitter    = float(getattr(node, 'uv_jitter', 0.0))
            _node_uv_jitter_spd= float(getattr(node, 'uv_jitter_speed', 0.0))
            _node_uv_scroll_u  = 0.0
            _node_uv_scroll_v  = 0.0
            if _node_animate_uv and (_node_uv_dir_x != 0.0 or _node_uv_dir_y != 0.0
                                      or _node_uv_jitter != 0.0):
                _t_anim = getattr(self, '_anim_time', 0.0)
                _node_uv_scroll_u = (_node_uv_dir_x * _t_anim)
                _node_uv_scroll_v = (_node_uv_dir_y * _t_anim)
                if _node_uv_jitter != 0.0 and _node_uv_jitter_spd > 0.0:
                    import math as _muv
                    _jitter = _node_uv_jitter * _muv.sin(_t_anim * _node_uv_jitter_spd * 2.0 * _muv.pi)
                    _node_uv_scroll_u += _jitter
                    _node_uv_scroll_v += _jitter
            # 90° counter-clockwise on the surface.  Implementation: swap U and V
            # and negate the new V: (u, v) → (v, 1.0 - u).
            # Reference: KotorBlender io_scene_kotor reader.py rotatetexture field;
            # xoreos engine source MeshNode::render() UV rotation.
            _node_rotate_tex = bool(getattr(node, 'rotate_texture', False))

            # ── TXI metadata: load and apply texture-specific rendering properties ──
            # TXI (Texture eXtra Info) files provide additional rendering params:
            #   blending=1    → additive blending (glow/fire effects)
            #   blending=2    → punchthrough alpha (hard cutoff)
            #   proceduretype → flipbook animation ('cycle') or water effects
            #   numx/numy/fps → flipbook grid dimensions and speed
            #   clamp_s/t     → UV clamp mode (prevent repeat wrapping)
            _node_txi_blending    = int(getattr(node, 'txi_blending', 0))
            _node_txi_clamp_s     = bool(getattr(node, 'txi_clamp_s', False))
            _node_txi_clamp_t     = bool(getattr(node, 'txi_clamp_t', False))
            # FIX-EDGEBLEED (CPU): Match GPU renderer behaviour — if the node has no
            # explicit TXI repeat/tile setting and all UVs stay within [0,1] (i.e. a
            # UV-atlased character/creature mesh), default to clamp-to-edge on both
            # axes.  This prevents bright corner pixels (e.g. yellow at V≈1.0 of the
            # bantha texture) from bleeding into near-boundary UVs through bilinear
            # interpolation.  Tiling nodes (UVs outside [0,1]) keep GL_REPEAT.
            if not _node_txi_clamp_s or not _node_txi_clamp_t:
                _has_explicit_repeat = bool(getattr(node, 'txi_blending', 0) == 0 and
                                            getattr(node, 'txi_proceduretype', '') == '' and
                                            not getattr(node, 'animate_uv', False))
                if _has_explicit_repeat and node.uvs:
                    _sample = node.uvs[:min(30, len(node.uvs))]
                    _uv_in_range = all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0
                                       for u, v in _sample)
                    if _uv_in_range:
                        _node_txi_clamp_s = True
                        _node_txi_clamp_t = True
            # Beaming nodes use additive blending (glow/lightshaft effect).
            # background_geometry nodes (skybox/floor tiles) need no special depth bias —
            # they are sorted naturally by depth, just like opaque geometry.
            # NOTE: beaming overrides txi_blending to additive so the glow composites
            # correctly over the scene regardless of the texture's own TXI settings.
            _node_beaming = bool(getattr(node, 'beaming', False))
            if _node_beaming:
                _node_txi_blending = 1  # treat beaming as additive glow
            _node_txi_procedure   = str(getattr(node, 'txi_proceduretype', ''))
            _node_txi_numx        = int(getattr(node, 'txi_numx', 0))
            _node_txi_numy        = int(getattr(node, 'txi_numy', 0))
            _node_txi_fps         = float(getattr(node, 'txi_fps', 0.0))
            _node_txi_rotate_deg  = float(getattr(node, 'txi_rotate', 0.0))
            # PERF-FIX (v10.2): Pre-compute TXI rotation cos/sin once per node
            # instead of computing them per-face inside the triangle loop.
            if _node_txi_rotate_deg != 0.0:
                _txi_ang = math.radians(_node_txi_rotate_deg * 360.0)
                _txi_ca  = math.cos(_txi_ang)
                _txi_sa  = math.sin(_txi_ang)
            else:
                _txi_ca = _txi_sa = 0.0
            # Is this a flipbook animation?
            _node_is_flipbook = (_node_txi_procedure == 'cycle'
                                 and _node_txi_numx > 0 and _node_txi_numy > 0)
            # Current flipbook frame (based on animation time if available)
            if _node_is_flipbook and _node_txi_fps > 0.0:
                _anim_t = getattr(self, '_anim_time', 0.0)
                _total_frames = _node_txi_numx * _node_txi_numy
                _flip_frame = int(_anim_t * _node_txi_fps) % max(1, _total_frames)
            else:
                _flip_frame = 0

            # Two-sided flag: dangly/cloth nodes and transparency_hint in (1,2) render
            # both faces. KotOR uses this for robes, capes, glass panels, cloth.
            # Also make face/head mesh nodes two-sided to prevent see-through
            # artifacts caused by inner-geometry (eyes, teeth) winding issues.
            transp_hint = getattr(node, 'transparency_hint', 0)
            _nl_tex2 = node.name.lower()
            _is_face_mesh_tex = any(s in _nl_tex2 for s in _FACE_MESH_SUBSTRINGS)
            # BUG FIX v26: same as flat path – inner-geo (eyes, eyelids, teeth)
            # must be two-sided so they aren't back-face culled from outside the head.
            _is_inner_geo_tex2 = any(s in _nl_tex2 for s in _INNER_GEO_SUBSTRINGS)
            is_two_sided = (node.is_dangly
                            or transp_hint in (1, 2)
                            or _is_face_mesh_tex
                            or _is_inner_geo_tex2)

            # ── Inner-geometry tier bump (textured path) ────────────────────
            # Same logic as flat-shade path: eye, eyelid, teeth, and tongue
            # nodes are promoted to tier 1 (drawn after the head/body mesh)
            # so they are revealed through the eye-socket/mouth-gap openings.
            _nl_tex = node.name.lower()
            # BUG FIX v20: same as flat path — removed 'not node.is_skin' gate.
            # Eyeball nodes in K2 head models can be skin nodes; must still promote
            # them to draw tier 1 so they render after the opaque face mesh.
            _clean_tex_ign = _clean_tex_name(getattr(node, 'texture', '') or '')
            _has_tex_ign = bool(_clean_tex_ign and _clean_tex_ign.upper() not in ('NULL', ''))
            _is_inner_geo_tex = (
                _has_tex_ign
                and any(s in _nl_tex for s in _INNER_GEO_SUBSTRINGS)
                and int(transp_hint) == 0
            )

            # Pre-transform ALL vertices to world space (LBS when animated)
            # PERF-FIX (v10.2): Use per-frame vertex/normal cache to avoid
            # redundant transforms across multiple draw passes.
            _node_id = id(node)
            _fvc = getattr(self, '_frame_verts_cache', None)
            _fnc = getattr(self, '_frame_norms_cache', None)
            if _fvc is not None and _node_id in _fvc:
                world_verts = _fvc[_node_id]
            else:
                world_verts = self._get_world_verts_for_node(node)
                if _fvc is not None:
                    _fvc[_node_id] = world_verts

            # Pre-transform normals to world space for correct lighting on rotated nodes
            if _fnc is not None and _node_id in _fnc:
                world_norms = _fnc[_node_id]
            else:
                world_norms = self._get_world_normals_for_node(node)
                if _fnc is not None:
                    _fnc[_node_id] = world_norms
            n_norms = len(world_norms)

            # ── UE-inspired area-weighted vertex normals ──────────────────────
            # Compute smooth per-vertex normals when none are stored in the MDX.
            # Area-weighted accumulation (UE5 SkeletalRenderCPUSkin reference).
            if n_norms == 0 and world_verts and node.faces:
                world_norms = self._compute_area_weighted_normals(node.faces, world_verts)
                n_norms = len(world_norms)

            # Batch-project all world vertices once per node for speed
            screen_verts_t = self._proj_batch(world_verts, W, H)

            # v6.0 FIX: Vectorized UV sentinel pre-filter simplified.
            # _UV_SENTINEL is now 1e18 (effectively disabled) — only catches
            # NaN/Inf from corrupt MDX data.  No module-specific workaround needed.
            # The frac() wrapping in the software rasterizer handles all UV magnitudes.
            _model_cls_str = getattr(self.model, 'classification', 'character') if self.model else 'character'
            _model_type_raw_vp = (getattr(self.model, 'model_type', None) if self.model else None)
            _model_type_int = int(_model_type_raw_vp) if _model_type_raw_vp is not None else 4
            _vp_is_module = (_model_cls_str in ('effect', 'tile', 'other') or
                             _model_type_int in (0, 2))
            _node_uv_sentinel = _UV_SENTINEL  # 1e18 — effectively NaN/Inf only
            _sentinel_mask: Optional[np.ndarray] = None
            if _NUMPY and has_uvs and n_uvs > 0 and node.faces and not _node_is_multitex:
                try:
                    # Build (NF, 3, 2) UV array for all faces
                    NF_all = len(node.faces)
                    _uvs_arr = np.empty((NF_all, 3, 2), dtype=np.float32)
                    for _mfi, _mface in enumerate(node.faces):
                        if len(_mface) < 3:
                            _uvs_arr[_mfi] = 0.0
                            continue
                        if _has_face_uvs:
                            _fuv = face_uvs_list[_mfi]
                            _ti = [_fuv[0], _fuv[1], _fuv[2]]
                        else:
                            _ti = [_mface[0], _mface[1], _mface[2]]
                        for _k, _idx in enumerate(_ti):
                            _uvs_arr[_mfi, _k] = uvs[_idx] if _idx < n_uvs else (0.5, 0.5)
                    _sentinel_mask = _accel_sentinel_filter(_uvs_arr, _node_uv_sentinel)
                except Exception:
                    _sentinel_mask = None  # fall back to per-face check

            # ── Per-node seam-split vertex detection (v10.4 fix) ─────────────
            # Build PER-AXIS sets of vertex indices that are genuine UV-seam-split
            # duplicates: vertices sharing the same 3D position with UV near the
            # OPPOSITE boundary (one near 0, one near 1) on the same axis.
            #
            # WHY PER-AXIS (v10.4b):
            # Using a single combined set incorrectly includes hair-mesh attachment
            # points where several strands start at the same 3D position.  Those
            # positions can have U values of e.g. [0.067, 0.331, 0.912] — near-0
            # and near-1 exist on the U axis — but there is NO V-axis seam at those
            # positions.  If the combined set were used to gate the V-seam fix, it
            # would allow the (erroneous) V-seam fix to run on hair-strand faces,
            # wrapping the V tip vertex outside the texture and producing a black
            # artifact at the tip.
            #
            # SOLUTION: Maintain separate _node_u_seam_verts and _node_v_seam_verts.
            # A face's per-axis skip flag is:
            #   skip_seam_u = not (any vi in _node_u_seam_verts)
            #   skip_seam_v = not (any vi in _node_v_seam_verts)
            # so the V-seam fix is only applied when a genuine V-seam vertex exists.
            #
            # PERF: O(N) positional hash per node, O(1) per-face set lookup.
            # Sets typically contain ≤ 100 vertices for a 1k-vertex mesh.
            _node_u_seam_verts: set = set()
            _node_v_seam_verts: set = set()
            if has_uvs and n_uvs > 0 and node.vertices:
                try:
                    _nv_verts = node.vertices
                    _pos_to_uv_groups: dict = {}
                    # Round to 4 decimal places to handle floating-point imprecision
                    for _vi, (_vpos, _vuv) in enumerate(zip(_nv_verts, uvs)):
                        _pkey = (round(_vpos[0], 4), round(_vpos[1], 4),
                                 round(_vpos[2], 4))
                        if _pkey not in _pos_to_uv_groups:
                            _pos_to_uv_groups[_pkey] = []
                        _pos_to_uv_groups[_pkey].append((_vi, _vuv))
                    # For each position with multiple verts, check axes separately:
                    _SEAM_NEAR = 0.15  # seam vertices within 0.15 of the boundary
                    for _grp in _pos_to_uv_groups.values():
                        if len(_grp) < 2:
                            continue
                        _u_vals = [_uv[0] for _, _uv in _grp]
                        _v_vals = [_uv[1] for _, _uv in _grp]
                        _u_near0 = any(u < _SEAM_NEAR for u in _u_vals)
                        _u_near1 = any(u > 1.0 - _SEAM_NEAR for u in _u_vals)
                        _v_near0 = any(v < _SEAM_NEAR for v in _v_vals)
                        _v_near1 = any(v > 1.0 - _SEAM_NEAR for v in _v_vals)
                        if _u_near0 and _u_near1:
                            for _vi, _ in _grp:
                                _node_u_seam_verts.add(_vi)
                        if _v_near0 and _v_near1:
                            for _vi, _ in _grp:
                                _node_v_seam_verts.add(_vi)
                except Exception:
                    # fallback: treat all verts as non-seam on both axes
                    _node_u_seam_verts = set()
                    _node_v_seam_verts = set()

            for _fi, face in enumerate(node.faces):
                if len(face) < 3:
                    continue
                vi0, vi1, vi2 = face[0], face[1], face[2]
                # Skip degenerate (collapsed) faces with repeated vertex indices
                if vi0 == vi1 or vi1 == vi2 or vi0 == vi2:
                    continue

                # ── Per-face texture (multi-texture mesh support) ──────────
                # For single-texture nodes tex_img is already resolved above.
                # For multi-material nodes (c_bantha body+head, etc.) resolve
                # the correct texture slot for THIS face from face_mats[_fi].
                if _node_is_multitex and has_uvs:
                    _raw_face_tex = self._get_tex_for_face(node, _fi)
                    face_tex = self.tex_cache.get_mip1(_raw_face_tex) if (_use_lq and _raw_face_tex is not None) else _raw_face_tex
                else:
                    face_tex = tex_img
                if vi0 >= nv or vi1 >= nv or vi2 >= nv:
                    continue

                wv0 = world_verts[vi0]
                wv1 = world_verts[vi1]
                wv2 = world_verts[vi2]

                p0 = screen_verts_t[vi0]
                p1 = screen_verts_t[vi1]
                p2 = screen_verts_t[vi2]
                if p0 is None or p1 is None or p2 is None:
                    continue

                # ── Backface culling (screen-space winding order) ────────
                # Screen Y is DOWN; CCW in world (front-facing) = CW in screen
                # → winding cross product is NEGATIVE for front faces.
                # Skip back-facing (winding > 0) in solid mode.
                ex1 = p1[0] - p0[0]; ey1 = p1[1] - p0[1]
                ex2 = p2[0] - p0[0]; ey2 = p2[1] - p0[1]
                winding = ex1 * ey2 - ex2 * ey1
                if winding > 0 and not self.show_wireframe and self.show_solid and not is_two_sided:
                    continue

                # Weighted-centroid depth (average is more stable than min for
                # coplanar/overlapping faces; small face-index bias breaks Z-tie)
                fi_local = len(tris)  # unique per-triangle ID for Z-fight tiebreak
                depth = (p0[2] + p1[2] + p2[2]) * 0.3333 + fi_local * 1e-7

                # ── UVs ─────────────────────────────────────────────────
                if has_uvs:
                    # When face_uvs is populated (ASCII MDL), use tvert indices;
                    # otherwise (binary MDL) use vertex indices directly.
                    if _has_face_uvs:
                        fuv = face_uvs_list[_fi]
                        ti0, ti1, ti2 = fuv[0], fuv[1], fuv[2]
                    else:
                        ti0, ti1, ti2 = vi0, vi1, vi2
                    # Use (0.5, 0.5) fallback for out-of-range tvert indices
                    uv0 = uvs[ti0] if ti0 < n_uvs else (0.5, 0.5)
                    uv1 = uvs[ti1] if ti1 < n_uvs else (0.5, 0.5)
                    uv2 = uvs[ti2] if ti2 < n_uvs else (0.5, 0.5)
                    # ── Lightmap UVs (UV channel 1 / uvs_lm) ────────────────
                    # Binary MDL: lightmap UVs are indexed by vertex index.
                    # Use (0.5,0.5) fallback when lm UVs are absent.
                    if _has_lm_uvs:
                        lm_uv0 = _uvs_lm[vi0] if vi0 < _n_uvs_lm else (0.5, 0.5)
                        lm_uv1 = _uvs_lm[vi1] if vi1 < _n_uvs_lm else (0.5, 0.5)
                        lm_uv2 = _uvs_lm[vi2] if vi2 < _n_uvs_lm else (0.5, 0.5)
                    else:
                        lm_uv0 = lm_uv1 = lm_uv2 = (0.5, 0.5)
                    # v6.0 FIX: UV sentinel guard simplified to NaN/Inf only.
                    # All legitimate UV magnitudes are handled by frac() wrapping.
                    # The vectorized pre-filter (_sentinel_mask) still runs but with
                    # _UV_SENTINEL=1e18 it only catches corrupt NaN/Inf data.
                    if _sentinel_mask is not None:
                        if not _sentinel_mask[_fi]:
                            continue
                    else:
                        _uv_sum_vp = (uv0[0] + uv0[1] + uv1[0] + uv1[1] + uv2[0] + uv2[1])
                        if _uv_sum_vp != _uv_sum_vp or not math.isfinite(_uv_sum_vp):
                            continue  # NaN or Inf check
                    # rotate_texture: (u,v) → (v, 1-u)  [90° CCW rotation]
                    # Used by KotOR for certain prop nodes (floor decals, lightmapped tiles).
                    if _node_rotate_tex:
                        uv0 = (uv0[1], 1.0 - uv0[0])
                        uv1 = (uv1[1], 1.0 - uv1[0])
                        uv2 = (uv2[1], 1.0 - uv2[0])
                    # ── TXI rotate: additional UV rotation from TXI metadata ──
                    # Some textures have a 'rotate' command in TXI that specifies
                    # an additional rotation angle in turns (0.0–1.0 = 0°–360°).
                    # Apply as a 2D UV rotation around the center (0.5, 0.5).
                    # PERF-FIX (v10.2): _txi_ca/_txi_sa are pre-computed per-node
                    # (not per-face) so no math.cos/sin or closure per triangle.
                    if _node_txi_rotate_deg != 0.0:
                        uu0 = uv0[0]-0.5; vv0 = uv0[1]-0.5
                        uu1 = uv1[0]-0.5; vv1 = uv1[1]-0.5
                        uu2 = uv2[0]-0.5; vv2 = uv2[1]-0.5
                        uv0 = (uu0 * _txi_ca - vv0 * _txi_sa + 0.5,
                               uu0 * _txi_sa + vv0 * _txi_ca + 0.5)
                        uv1 = (uu1 * _txi_ca - vv1 * _txi_sa + 0.5,
                               uu1 * _txi_sa + vv1 * _txi_ca + 0.5)
                        uv2 = (uu2 * _txi_ca - vv2 * _txi_sa + 0.5,
                               uu2 * _txi_sa + vv2 * _txi_ca + 0.5)
                    # ── TXI clamp mode: GL_CLAMP_TO_EDGE when clamp_s/t set ──
                    # Default KotOR wrapping is GL_REPEAT. When the TXI 'clamps'
                    # or 'clampt' command is present, clamp UVs to [0,1] to prevent
                    # texture wrapping artifacts on decals and alpha-blended surfaces.
                    if _node_txi_clamp_s:
                        uv0 = (_clamp(uv0[0], 0.0, 1.0), uv0[1])
                        uv1 = (_clamp(uv1[0], 0.0, 1.0), uv1[1])
                        uv2 = (_clamp(uv2[0], 0.0, 1.0), uv2[1])
                    if _node_txi_clamp_t:
                        uv0 = (uv0[0], _clamp(uv0[1], 0.0, 1.0))
                        uv1 = (uv1[0], _clamp(uv1[1], 0.0, 1.0))
                        uv2 = (uv2[0], _clamp(uv2[1], 0.0, 1.0))
                    # ── TXI flipbook: remap UVs to the current frame cell ─────
                    # KotOR flipbook textures use proceduretype=cycle with numx/numy
                    # to divide the texture into a grid of animation frames.
                    # We remap the face UVs to point within the current frame's cell.
                    if _node_is_flipbook and _node_txi_numx > 0 and _node_txi_numy > 0:
                        uv0 = _compute_flipbook_uv(uv0[0], uv0[1],
                                                    _node_txi_numx, _node_txi_numy, _flip_frame)
                        uv1 = _compute_flipbook_uv(uv1[0], uv1[1],
                                                    _node_txi_numx, _node_txi_numy, _flip_frame)
                        uv2 = _compute_flipbook_uv(uv2[0], uv2[1],
                                                    _node_txi_numx, _node_txi_numy, _flip_frame)
                    # ── UV scroll (animate_uv) ────────────────────────────────────
                    # Add time-based offset to all diffuse UVs.  UVs wrap naturally
                    # (the texture rasteriser uses modulo-1 tiling), so no clamping here.
                    # This replicates the KotOR engine's real-time UV scroll for water,
                    # lava, energy shields, etc.
                    if _node_animate_uv and (_node_uv_scroll_u != 0.0 or _node_uv_scroll_v != 0.0):
                        uv0 = (uv0[0] + _node_uv_scroll_u, uv0[1] + _node_uv_scroll_v)
                        uv1 = (uv1[0] + _node_uv_scroll_u, uv1[1] + _node_uv_scroll_v)
                        uv2 = (uv2[0] + _node_uv_scroll_u, uv2[1] + _node_uv_scroll_v)
                else:
                    uv0 = uv1 = uv2 = (0.5, 0.5)
                    lm_uv0 = lm_uv1 = lm_uv2 = (0.5, 0.5)

                # ── Per-face lighting ────────────────────────────────────
                if n_norms > max(vi0, vi1, vi2):
                    nx = (world_norms[vi0][0] + world_norms[vi1][0] + world_norms[vi2][0]) / 3.0
                    ny = (world_norms[vi0][1] + world_norms[vi1][1] + world_norms[vi2][1]) / 3.0
                    nz = (world_norms[vi0][2] + world_norms[vi1][2] + world_norms[vi2][2]) / 3.0
                    nl = math.sqrt(nx*nx + ny*ny + nz*nz)
                    if nl > 1e-9:
                        nx /= nl; ny /= nl; nz /= nl
                    norm = (nx, ny, nz)
                else:
                    norm = self._face_normal(wv0, wv1, wv2)

                ndotl = _dot(norm, light_dir)
                # Two-sided materials get stronger back-face lighting (cloth/glass)
                ndotl_f = max(0.0, ndotl) + max(0.0, -ndotl) * (0.55 if is_two_sided else 0.35)
                si_r, si_g, si_b = selfillum
                # Self-illumination raises the minimum shade (emissive surfaces stay bright)
                si_boost = max(si_r, si_g, si_b)
                shade = ambient + (1.0 - ambient) * ndotl_f
                shade = max(shade, si_boost)

                # Flat fill color for untextured or fallback
                # face_tex = per-face correct texture (multi-tex) or node tex (single)
                if face_tex is not None:
                    # Shade color for texture modulation (centre sample for fill approx).
                    # UE-inspired mip-bias: use a half-resolution version of the
                    # texture for the centroid colour approximation.  The mip1
                    # image is cached per texture in TextureCache.get_mip1().
                    # This mirrors UE's StreamingManagerTexture mip-level bias:
                    # lower-resolution mips used when per-pixel detail is not required.
                    sample_tex = self.tex_cache.get_mip1(face_tex)
                    uc = (uv0[0] + uv1[0] + uv2[0]) / 3.0
                    vc = (uv0[1] + uv1[1] + uv2[1]) / 3.0
                    tr, tg, tb = self.tex_cache.sample(sample_tex, uc, vc,
                                                        clamp_s=_node_txi_clamp_s,
                                                        clamp_t=_node_txi_clamp_t)
                    # Per-channel: texture * lighting * diffuse tint + SI
                    dr, dg, db = diff
                    r = int(_clamp(tr * shade * (0.5 + dr*0.5) + si_r * 255, 0, 255))
                    g = int(_clamp(tg * shade * (0.5 + dg*0.5) + si_g * 255, 0, 255))
                    b = int(_clamp(tb * shade * (0.5 + db*0.5) + si_b * 255, 0, 255))
                    fill = (r, g, b)
                else:
                    r = int(_clamp(diff[0] * shade * 255 + si_r * 255, 0, 255))
                    g = int(_clamp(diff[1] * shade * 255 + si_g * 255, 0, 255))
                    b = int(_clamp(diff[2] * shade * 255 + si_b * 255, 0, 255))
                    fill = (r, g, b)

                # shade_color for texture modulation (applied inside _paste_textured_triangle)
                # Per-channel shade colour: diffuse tint preserves model colour
                # while lighting darkens/brightens. Pure grey washes out colour.
                dr, dg, db = diff
                shade_r = int(_clamp(shade * (0.5 + dr*0.5) * 255, 0, 255))
                shade_g = int(_clamp(shade * (0.5 + dg*0.5) * 255, 0, 255))
                shade_b = int(_clamp(shade * (0.5 + db*0.5) * 255, 0, 255))
                shade_col = (shade_r, shade_g, shade_b)

                # Transparent tris (alpha < 1) are appended after opaque so they
                # sort behind opaque geometry at the same depth — correct for glass.
                is_transparent = (node_alpha < 0.999)
                # TXI additive blend (glow/fire) OR beaming nodes: also sorts like transparent
                is_additive = (_node_txi_blending == 1)
                # background_geometry (skybox, floor tiles) should render BEFORE
                # opaque foreground geometry to prevent z-fighting.  We give these a depth
                # BONUS (push them farther away in sort order) so they appear at the bottom
                # of the painter-sort stack (drawn first, overwritten by foreground).
                _node_bg_geom = bool(getattr(node, 'background_geometry', False))
                _bg_bias = 1e-2 if _node_bg_geom else 0.0
                # Use a depth bias so transparent/additive faces sort AFTER opaque at same depth
                sort_depth = depth - (1e-3 if (is_transparent or is_additive) else 0.0) + _bg_bias
                # UE-inspired: convert to sortable uint key for stable integer comparison
                sort_key = _float_to_sort_key(sort_depth)

                # Per-axis seam fix flags.
                #
                # CORE TEXTURE-WRAPPING FIX (v14.1):
                # Previously, a face got skip_seam_u=False (fix applied) ONLY when it
                # contained a vertex in _node_u_seam_verts (a positional duplicate).
                # This was TOO RESTRICTIVE: meshes without positional UV-seam duplicates
                # (non-skin trimeshes, area geometry, creature accessories) would have
                # _node_u_seam_verts = {} → _face_has_u_seam = False → skip_seam_u=True
                # → seam fix NEVER applied → texture stretched across full tile on ALL
                # seam-crossing faces.
                #
                # RULE (v14.1):
                # Let _node_u_seam_verts_found and _node_v_seam_verts_found track
                # whether the analysis ran at all (i.e., whether the mesh had any
                # positional duplicates in either axis).
                #
                #   _node_u_seam_verts is non-empty → u-seam analysis found duplicates;
                #     only fix faces touching a seam vertex (interior faces skipped).
                #   _node_v_seam_verts is non-empty → same for v axis.
                #   BOTH empty AND analysis ran → no duplicates in either axis; let
                #     _paste_textured_triangle's own detection handle both axes.
                #   BOTH empty AND analysis did NOT run (no UVs/verts) → allow both.
                #
                # Hair-strand fix (v10.4b) is preserved:
                #   bthair: _node_u_seam_verts non-empty, _node_v_seam_verts empty.
                #   Because _node_u_seam_verts is non-empty, we know the seam analysis
                #   DID run.  _node_v_seam_verts being empty means there are NO v-seam
                #   duplicates → the V-seam fix stays disabled for all bthair faces.
                #   This prevents the erroneous V-wrap that caused black hair-tip artefacts.
                #
                # For meshes with no duplicates at all (trimesh, area geometry):
                #   Both sets are empty.  The SAFE fast-path inside _paste_textured_triangle
                #   (all UVs in [0.05, 0.95]) covers >80% of faces cheaply.
                #   Only the <20% with seam-crossing UVs are checked by _edge_has_seam.
                _any_u_found = bool(_node_u_seam_verts)
                _any_v_found = bool(_node_v_seam_verts)
                # Was the analysis actually meaningful? (ran on a mesh with uvs+verts)
                # We use the presence of either set as evidence that analysis ran and
                # found at least one axis' worth of duplicates.
                _analysis_ran = bool(_any_u_found or _any_v_found)

                if _any_u_found:
                    # Seam analysis found u-duplicates: gate to faces touching a seam vert
                    _face_has_u_seam = (vi0 in _node_u_seam_verts or
                                        vi1 in _node_u_seam_verts or
                                        vi2 in _node_u_seam_verts)
                else:
                    # Either no u-duplicates found, or analysis found only v-duplicates.
                    # If analysis ran (v-seam found), there are genuinely no u-seam
                    # duplicates → we still need to allow _paste_textured_triangle's
                    # own seam detection for meshes that have seam faces without
                    # positional-duplicate verts (e.g. non-skin area meshes).
                    # Allow seam detection to run (True = don't skip).
                    _face_has_u_seam = True

                if _any_v_found:
                    # Seam analysis found v-duplicates: gate to faces touching a seam vert
                    _face_has_v_seam = (vi0 in _node_v_seam_verts or
                                        vi1 in _node_v_seam_verts or
                                        vi2 in _node_v_seam_verts)
                elif _analysis_ran:
                    # Analysis ran (u-seam found) but no v-seam duplicates exist.
                    # This means the mesh genuinely has no V-axis seam faces
                    # (e.g. bthair: u-seam at attachment points but continuous V).
                    # DISABLE v-seam fix to preserve hair-strand black-tip fix (v10.4b).
                    _face_has_v_seam = False
                else:
                    # Analysis found nothing in either axis: allow both axes to run.
                    _face_has_v_seam = True

                # Two-pass tier: opaque=0, transparent/additive/semi=1.
                # Tier is the PRIMARY sort dimension — all opaque tris are drawn
                # before any transparent tri regardless of depth.  This prevents
                # transparent inner geometry (eyes, droid lenses, glow FX)
                # from rendering on top of opaque face/body meshes when centroid
                # depth ordering alone would place them in front.
                _th_tex = int(getattr(node, 'transparency_hint', 0))
                # Inner-geometry nodes (eyes, eyelids, teeth) are promoted to
                # tier 1 even when transparency_hint==0 so they render AFTER
                # the opaque head/body mesh and are visible through the eye-socket
                # / mouth-gap geometric openings in the face mesh.
                _is_trans_tex = (_th_tex > 0 or is_transparent or is_additive or _is_inner_geo_tex)
                _tier_tex = 1 if _is_trans_tex else 0
                tris.append((sort_key,
                             ((p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1])),
                             fill, shade_col, face_tex, uv0, uv1, uv2, is_sel,
                             fi_local, node_alpha, _node_txi_blending,
                             lm_img, lm_uv0, lm_uv1, lm_uv2,
                             _face_has_u_seam, _face_has_v_seam,
                             _node_txi_clamp_s, _node_txi_clamp_t,
                             _tier_tex))

                if len(tris) >= tri_cap:
                    break
            if len(tris) >= tri_cap:
                break

        # ── Sort: two-pass (tier) then back-to-front (painter's algorithm) ──
        # PRIMARY key: tier (0=opaque, 1=transparent/additive).
        # All opaque triangles render before any transparent triangle
        # regardless of depth.  This prevents transparent inner geometry
        # (eyes, glass, droid lenses) from occluding opaque face/body meshes
        # when centroid-depth ordering alone would place them in front.
        # SECONDARY key: depth (descending = back-to-front within each tier).
        # TERTIARY key: face-insertion index (breaks Z-fighting ties).
        tris.sort(key=lambda t: (t[20], -t[0], t[9]))

        # ── Draw triangles (two-pass: solid first, then wireframe/outlines) ──
        # Pass 1: all solid/texture fills (paste operations modify img in-place)
        wire_tris = []  # collect wireframe data for pass 2
        _mem_error_count = 0  # track consecutive MemoryErrors to abort early
        for entry in tris:
            (depth, pts, fill, shade_col, tex_img, uv0, uv1, uv2, is_sel,
             _fi2, t_alpha, txi_blend, tri_lm_img, lm_uv0, lm_uv1, lm_uv2,
             _tri_face_has_u_seam, _tri_face_has_v_seam,
             _tri_clamp_s, _tri_clamp_t, _tier_draw) = entry
            sp0, sp1, sp2 = pts
            flat = [sp0[0], sp0[1], sp1[0], sp1[1], sp2[0], sp2[1]]

            if self.show_solid:
                if tex_img is not None:
                    # Proper UV-mapped rendering via PIL AFFINE warp.
                    # sel_brightness brightens selected triangles for visual feedback.
                    # node_alpha drives transparency for glass/droid-eye surfaces.
                    # TXI additive blending=1: screen-space additive composite (src+dst).
                    _is_add = (txi_blend == 1)
                    _is_punch = (txi_blend == 2)
                    try:
                        _paste_textured_triangle(
                            img, tex_img,
                            sp0, sp1, sp2,
                            uv0, uv1, uv2,
                            W, H, shade_col,
                            sel_brightness=(50 if is_sel else 0),
                            node_alpha=t_alpha,
                            is_additive=_is_add,
                            skip_seam_u=(not _tri_face_has_u_seam),
                            skip_seam_v=(not _tri_face_has_v_seam),
                            clamp_s=_tri_clamp_s,
                            clamp_t=_tri_clamp_t,
                            is_punchthrough=_is_punch
                        )
                        _mem_error_count = 0  # reset on success
                        # ── Lightmap pass: multiply-blend lightmap over diffuse ──
                        # Only applied to non-additive, non-transparent faces
                        # (additive FX nodes don't have lightmaps in KotOR)
                        if tri_lm_img is not None and not _is_add and t_alpha >= 0.999:
                            _paste_lightmap_triangle(
                                img, tri_lm_img,
                                sp0, sp1, sp2,
                                lm_uv0, lm_uv1, lm_uv2,
                                W, H
                            )
                    except MemoryError:
                        _mem_error_count += 1
                        log.debug(f"_draw_mesh_textured: MemoryError on triangle {_fi2}")
                        if _mem_error_count >= 3:
                            # Too many OOMs in a row — stop textured rendering, fall back
                            log.warning("_draw_mesh_textured: too many MemoryErrors, aborting textured pass")
                            break
                    except Exception:
                        pass  # single-triangle errors are non-fatal
                else:
                    # No texture: flat fill — apply alpha via color blend with background
                    sel_fill = (min(fill[0]+40, 255), min(fill[1]+60, 255), fill[2]) if is_sel else fill
                    if t_alpha < 0.999:
                        # Blend with a mid-grey background for untextured transparent faces
                        bg = (30, 30, 50)
                        a = t_alpha
                        blended = (int(sel_fill[0]*a + bg[0]*(1-a)),
                                   int(sel_fill[1]*a + bg[1]*(1-a)),
                                   int(sel_fill[2]*a + bg[2]*(1-a)))
                        draw.polygon(flat, fill=blended)
                    else:
                        draw.polygon(flat, fill=sel_fill)

            if self.show_wireframe or is_sel:
                wire_col = _SEL[:3] if is_sel else _WIRE[:3]
                wire_tris.append((flat, wire_col))

        # Pass 2: wireframe / selection outlines (with fresh draw context after paste)
        if wire_tris:
            draw = ImageDraw.Draw(img)
            for flat, wire_col in wire_tris:
                draw.polygon(flat, outline=wire_col)

        # NOTE: _draw_bones is called by render() with a fresh draw context.

    def _is_deformation_helper(self, node: 'ModelNode') -> bool:
        """
        Detect KotOR deformation-helper mesh nodes that should NOT be rendered
        as visible geometry.

        OBJ / FBX imported nodes are tagged with node._imported = True by
        OBJImporter and FBXImporter.  These are never deformation helpers —
        they are real geometry the user explicitly loaded.

        In KotOR's Odyssey engine, character models contain hidden deformation
        helper trimeshes (usually ending in _g, _G, or matching bone names like
        lbicep_g, rthigh_g, pelvis_g, head_g, jaw2, etc.).  These are used by
        the engine's SkinMesh deformation pipeline and are never rendered directly.
        They have:
          - No texture (tex=null/empty) OR extreme UV coordinates (|u|>3 or |v|>3)
          - Often named with a _g / _G suffix (geometry deformation)
          - Sometimes carry a visible texture name but with completely invalid UVs
            or NO UVs at all
          - Non-skin nodes with _g/_G suffix are always helpers even if textured

        IMPORTANT: Skin nodes with a real (non-null) texture AND valid UVs are
        ALWAYS renderable geometry, even if their name ends in _g.  Some KotOR
        models (e.g. n_darthrevanm, n_darthrevanf, p_bastilabb02) use _g-named
        skin meshes as their primary visible geometry.

        NON-skin _g nodes: always helpers regardless of texture (they are deform
        proxies used for SkinMesh influence even when textured, e.g. rthigh_g in
        n_admrlsaulkar carries texture 'n_saulh' but has no UVs / extreme UVs).

        v12.14: Also treats skin-proxy nodes (identified by _compute_skin_proxy_ids)
        as deformation helpers.  A non-skin node is a proxy when it shares an
        exclusive texture with exactly one skin mesh that has more vertices
        (e.g. 'head_Hair' on c_bantha is a 61-vert proxy for 'bthair' with 320 verts).
        """
        # ── OBJ / FBX imported nodes: always renderable ───────────────────────
        # Nodes tagged with _imported=True were explicitly loaded by the user from
        # an OBJ or FBX file.  They are never KotOR deformation helpers — skip all
        # KotOR-specific heuristics and render them unconditionally.
        if getattr(node, '_imported', False):
            return False

        tex = _clean_tex_name(node.texture)
        is_null_tex = (not tex or tex.upper() == 'NULL')

        # ── BUG FIX v26: Inner-geometry nodes (eyes, eyelids, teeth, tongue, ─
        # jaw, gum) are ALWAYS renderable when they have a real texture and
        # valid UVs — regardless of is_skin status, name suffix, or proxy rules.
        # These nodes sit inside the face mesh and form the visible eye/mouth
        # content.  Treating them as deformation helpers (for any reason) causes
        # them to be silently dropped from the render list and the character
        # appears eyeless.  This explicit early-return short-circuits ALL later
        # helper checks, including the _skin_proxy_ids check.
        _name_lower_check = node.name.lower()
        if any(s in _name_lower_check for s in _INNER_GEO_SUBSTRINGS):
            if not is_null_tex and node.uvs:
                _uvs_ok = not any(abs(u) > 3.0 or abs(v) > 3.0
                                  for u, v in node.uvs[:20])
                if _uvs_ok:
                    return False  # always render inner-geo nodes

        # ── Skin node with a real texture and valid UVs → always visible ──────
        # Never treat it as a deformation helper regardless of name.
        # (Some KotOR models use _g-named skin meshes as primary geometry.)
        if node.is_skin and not is_null_tex and node.uvs:
            has_extreme_uvs = any(abs(u) > 3.0 or abs(v) > 3.0
                                  for u, v in node.uvs[:20])
            if not has_extreme_uvs:
                return False

        # ── Extreme UV coordinates → always a deform helper ───────────────────
        # EXCEPTION: Module/area/tile models (classification 'effect'=0 or
        # 'tile'=2) legitimately use UV coordinates far outside [−3, +3] for
        # tiled wall/floor textures (e.g. U=−8.75 for LTS_logwal02, or
        # V=−9.71 for wall geometry in Dantooine/Taris modules).  These are
        # real renderable geometry, not deformation helpers.  Skip the extreme-UV
        # helper check for module classifications.
        # Reference: KotOR MDL mesh header — area/tile models tile textures
        # over large surfaces using UV coordinates that match the surface scale
        # in game units (e.g. a 9-unit wall maps to U≈9.0 with a 1-unit texture).
        if node.uvs:
            _model_cls_str = getattr(self.model, 'classification', 'character') if self.model else 'character'
            # FIX-MODEL-TYPE-ZERO: don't treat model_type=0 as falsy
            _model_type_raw2 = (getattr(self.model, 'model_type', None) if self.model else None)
            _model_type_int = int(_model_type_raw2) if _model_type_raw2 is not None else 4
            _is_module_model = (_model_cls_str in ('effect', 'tile', 'other') or
                                _model_type_int in (0, 2))
            if not _is_module_model:
                has_extreme_uvs = any(abs(u) > 3.0 or abs(v) > 3.0
                                      for u, v in node.uvs[:20])
                if has_extreme_uvs:
                    return True

        # ── Non-skin _g / _G or _dum nodes are deform helpers — UNLESS they ───
        # are inner-geometry (eye, eyelid, teeth, tongue) nodes with a real
        # texture.  NPC head models use naming like f_rlweye_g / f_llweye_g for
        # actual eyeball trimesh nodes that end in _g but ARE visible geometry.
        # Without this exception those eyeballs are incorrectly hidden.
        name_lower = node.name.lower()
        _name_is_inner_geo = any(s in name_lower for s in _INNER_GEO_SUBSTRINGS)
        if not node.is_skin and (name_lower.endswith('_g')
                                  or name_lower.endswith('_g0')
                                  or name_lower.endswith('_dum')):
            # EXCEPTION: inner-geometry nodes with a real texture and valid
            # (non-extreme) UVs are ALWAYS renderable — they are real eyeball /
            # teeth / tongue meshes, not deformation proxies.
            if _name_is_inner_geo and not is_null_tex and node.uvs:
                _uvs_ok = not any(abs(u) > 3.0 or abs(v) > 3.0
                                  for u, v in node.uvs[:20])
                if _uvs_ok:
                    return False  # render this inner-geo node
            return True

        # ── Null-texture, non-skin nodes → always deform helpers ─────────────
        if is_null_tex and not node.is_skin:
            return True

        # ── Null-texture skin nodes with no UVs or only zero UVs → helpers ───
        if is_null_tex and node.is_skin and (not node.uvs
                            or all(u == 0.0 and v == 0.0
                                   for u, v in node.uvs[:5])):
            return True

        # ── Non-skin nodes with NO UVs → deform helpers UNLESS module/area model ──
        # KotOR creature/character models contain skeleton-bone helper nodes
        # (e.g. BTHips, BTSpine1, BTHead, BTShoulders on the bantha; or similar
        # bone-proxy trimeshes on other creatures) that:
        #   - Carry a real texture name (e.g. 'c_bantha01') but NO UV coords
        #   - Are NOT skin nodes (is_skin=False)
        #   - Are NOT named _g / _dum (so the suffix check above doesn't catch them)
        # These are the raw bone geometry that the engine uses internally for
        # collision/deformation but never renders directly.  Without UVs they
        # cannot be textured, and rendering them as flat-shaded produces ugly
        # opaque bone-shaped blobs that obscure the real skin mesh.
        #
        # EXCEPTION: Module/area models (classification 'effect'=0 or 'tile'=2)
        # store ALL vertex data (including UVs) in the companion .mdx file.
        # When the MDX is not available or not yet loaded, UV arrays are empty but
        # the geometry IS real renderable geometry.  We must NOT discard it.
        # For these models, render even without UVs (flat-shaded fallback).
        # Also: AABB nodes in room models are always real geometry (walkmesh).
        if not node.is_skin and not node.uvs:
            model_cls = getattr(self.model, 'classification', 'character') if self.model else 'character'
            model_type = getattr(self.model, 'model_type', 4) if self.model else 4
            # Module/area/effect models: render all non-_g trimeshes even without UVs
            if model_cls in ('effect', 'tile', 'other') or model_type in (0, 2):
                # Still skip obvious _g deformation proxies
                if not (name_lower.endswith('_g') or name_lower.endswith('_g0') or name_lower.endswith('_dum')):
                    return False  # render as flat-shaded geometry
            return True

        # ── v12.14: Skin-proxy detection (non-skin node with exclusive-texture ──
        # skin-mesh counterpart).  E.g. 'head_Hair' on c_bantha (61 verts, c_banthh01)
        # is a deformation proxy for 'bthair' (320 verts, c_banthh01).
        _proxy_ids = getattr(self, '_skin_proxy_ids', None)
        if _proxy_ids is not None and id(node) in _proxy_ids:
            return True

        return False

    def _iter_visible_mesh_nodes(self):
        """Yield mesh nodes that have visible geometry (not deform helpers or outlier proxies).

        Dangly (cloth) nodes are ALWAYS rendered — they represent visible cloth
        geometry even if they share properties with deformation helpers.

        BUG-C FIX: Respect the KotOR MDL 'render' flag.  Nodes with render=False
        are explicitly marked as invisible by the model author and must never be
        drawn.  Previously these nodes were rendered despite the flag, causing
        invisible geometry bleed (e.g. collision proxy meshes appearing as solid
        black patches over the visible model).

        v12.15 FIXES (from deep research):
        - Skip SABER nodes (NODE_SABER=0x0800): lightsaber blade geometry is
          runtime-generated by the engine; the saber mesh node only provides anchor
          positions.  Rendering it produces garbage quad geometry.
        - Skip attachment/hook dummy nodes by well-known naming conventions:
          camerahook, headhook, handhook_*, rhand, lhand, handconjure*, etc.
          These are empty DUMMY nodes used as VFX/camera attachment points.
        """
        # Attachment/hook name prefixes — these are always non-renderable dummy nodes
        # used as VFX, camera, and weapon attachment points in KotOR character models.
        _HOOK_PREFIXES = (
            'camerahook', 'headhook', 'handhook', 'rhand', 'lhand',
            'handconjure', 'chestconjure', 'footstep', 'impact_', 'ap_',
        )
        for n in self._iter_mesh_nodes():
            # Skip nodes explicitly marked non-renderable by the MDL author.
            # The render flag is set to False for collision boxes, occluders, and
            # internal engine helpers.  Always respect it regardless of other flags.
            # Exception: selected node is always shown for editing purposes.
            # EXCEPTION: inner-geometry nodes (eyes, eyelids, teeth, tongue) are
            # always rendered even if render=0 — some KotOR NPC head MDLs store
            # render=0 on eyeball/teeth nodes which would make the face appear empty.
            _nl_tex = n.name.lower()
            _is_inner_geo_tex = any(s in _nl_tex for s in _INNER_GEO_SUBSTRINGS)
            if not getattr(n, 'render', True) and n is not self.selected_node and not _is_inner_geo_tex:
                continue
            # Skip SABER nodes — lightsaber blade is procedurally generated
            # at runtime.  The node only provides anchor/extent information; rendering
            # it as geometry produces degenerate quads.
            if getattr(n, 'is_saber', False):
                continue
            # Skip attachment/hook dummy nodes by name convention.
            # These are DUMMY nodes that carry no vertices but may have been classified
            # as mesh nodes due to partial flag parsing.
            _nl = n.name.lower()
            if any(_nl.startswith(pfx) or _nl == pfx for pfx in _HOOK_PREFIXES):
                continue
            # Dangly/cloth nodes are never deformation helpers — always render them
            if n.is_dangly:
                yield n
                continue
            if not self._is_deformation_helper(n) and not self._is_outlier_skin(n):
                yield n

    def hit_test_bone(self, sx: int, sy: int, radius: int = 8) -> Optional['ModelNode']:
        """Return the nearest bone within `radius` pixels of screen coord (sx, sy)."""
        best_node = None
        best_dist2 = radius * radius
        for bsx, bsy, depth, node in self._bone_screen_positions:
            d2 = (bsx - sx)**2 + (bsy - sy)**2
            if d2 <= best_dist2:
                best_dist2 = d2
                best_node = node
        return best_node

    def _iter_mesh_nodes(self):
        """Yield all mesh and skin nodes in the model (depth-first).

        Added visited-set cycle guard.  Cyclic or corrupt MDL
        node hierarchies (e.g. shared-child sub-graphs) could cause an infinite
        loop here before this fix, stalling the render thread indefinitely.

        Phase 16 FIX: Yield nodes with is_mesh OR is_skin.  KotOR MDL skin
        nodes (flag 0x0040) have is_mesh=False but contain renderable geometry
        (UV-mapped, textured body meshes).  Previously, skin nodes like
        btBody_front / btBodyback / bthair were silently excluded from the
        render loop, causing the creature body to be completely invisible
        (only the bone-proxy helper geometry was rendered, which the
        deformation-helper filter then removed, leaving an empty frame).
        """
        if not self.model or not self.model.root_node:
            return
        stack = [self.model.root_node]
        visited: set = set()
        while stack:
            n = stack.pop()
            if n is None:
                continue
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            if n.is_mesh or n.is_skin:
                yield n
            stack.extend(c for c in reversed(n.children) if c is not None)

    # ── Bones ─────────────────────────────────────────────────────────

    def _draw_bones(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw bone/skeleton overlay.

        In KotOR models, the skeleton consists of BOTH true dummy nodes (0x0001)
        AND deformation-helper trimesh nodes (0x0021, _g suffix).  Both types
        carry position/orientation data and are referenced by skin node bone_maps.
        We show all of them as joints.

        Bone categories:
          • Root / body joints      – large gold dots (r=4), connected
          • Deform-helper trimesh   – small green dots (r=3), connected
          • Leaf joints             – small amber dots (r=2)
          • Effect attachment nodes – tiny dim-blue dots (r=2), no lines
            (hook, conjure, camerahook – these are VFX attachment points)
          • Selected joint          – teal (r=7) + name label
          • Hovered joint           – bright yellow (r=5) + name label
        """
        if not self.model or not self.model.root_node:
            return

        # In rig-edit mode all adjustable joints are orange so the user can
        # immediately see which bones they can drag with the gizmo.
        _rig_edit = getattr(self, 'rig_edit_mode', False)
        _BONE_COL   = (255, 140,  20) if _rig_edit else _BONE[:3]  # orange or gold
        _BONE_DEFORM= (255, 100,  10) if _rig_edit else (60, 200, 80)
        _BONE_LEAF  = (200,  80,   0) if _rig_edit else (180, 100, 0)
        _BONE_LINE  = (220, 120,  20) if _rig_edit else (200, 140, 20)
        _DEFORM_LINE= (200,  90,  10) if _rig_edit else (50, 160, 70)
        _SEL_COL    = _SEL[:3]            # teal  (0,255,170)
        _EFF_COL    = ( 50, 120, 180)      # dim blue for effect nodes

        # Clear bone screen positions for this frame (hit-test tracking)
        self._bone_screen_positions = []

        def _is_bone_node(node) -> bool:
            """Return True if this node is a skeleton joint (dummy OR deform-helper)."""
            if node.is_dummy:
                return True
            # Root node is always treated as a bone (skeleton root)
            if node.parent is None:
                return True
            # Deform-helper trimesh nodes (_g, _dum suffixes) ARE skeleton joints
            # in KotOR's Odyssey engine – they carry bone transforms
            if node.is_mesh and not node.is_skin:
                nl = node.name.lower()
                if (nl.endswith('_g') or nl.endswith('_g0') or
                        nl.endswith('_dum') or nl.endswith('dummy')):
                    return True
            return False

        def _nearest_bone_ancestor(node):
            """Walk parent chain and return the first bone ancestor, or None."""
            p = node.parent
            _visited = set()
            while p is not None:
                pid = id(p)
                if pid in _visited:
                    break   # cycle guard
                _visited.add(pid)
                if _is_bone_node(p):
                    return p
                p = p.parent
            return None

        def _bone_world_pos(node):
            # Use the renderer's cached world-transform for animated poses so
            # joint dots track the animation correctly.  For bind pose use
            # bone_world_position() which applies full 180°-collapse on ALL
            # nodes including the leaf — this gives the correct pivot point for
            # joint dots (independent of mesh vertex orientation).
            if self._anim_pose is not None:
                wp, _, _ = self._node_world_transform(node)
                return wp
            return node.bone_world_position()

        def _process_bone_node(node):
            """Draw one bone joint + its connection line to the nearest bone ancestor."""
            is_bone = _is_bone_node(node)
            if not is_bone:
                return

            # ── Classify this joint ────────────────────────────────
            name_lw = node.name.lower()
            is_effect_attach = any(s in name_lw for s in
                ('hook', 'conjure', 'camerahook'))
            is_deform_helper = (node.is_mesh and not node.is_dummy)

            # ── World position → screen position ──────────────────
            wp  = _bone_world_pos(node)
            pp  = self._proj(*wp, W, H)

            # Count bone children (for leaf detection)
            bone_children = [c for c in node.children if _is_bone_node(c)]
            has_joint_children = bool(bone_children)
            is_sel     = (node is self.selected_node)
            is_hovered = (node is self._hovered_bone and not is_sel)

            if pp:
                # Record for click hit-testing
                self._bone_screen_positions.append((pp[0], pp[1], pp[2], node))

                # Dot appearance
                if is_sel:
                    dot_color    = _SEL_COL
                    outline_col  = (255, 255, 100)
                    r = 7
                elif is_hovered:
                    dot_color    = (255, 220, 80)
                    outline_col  = (255, 255, 180)
                    r = 5
                elif is_effect_attach:
                    dot_color    = _EFF_COL
                    outline_col  = None
                    r = 2
                elif is_deform_helper:
                    dot_color    = _BONE_DEFORM
                    outline_col  = None
                    r = 3 if has_joint_children else 2
                else:
                    dot_color    = _BONE_COL if has_joint_children else _BONE_LEAF
                    outline_col  = None
                    r = 4 if has_joint_children else 2

                draw.ellipse([pp[0]-r, pp[1]-r, pp[0]+r, pp[1]+r],
                             fill=dot_color, outline=outline_col)

                # Bone name label for selected or hovered nodes
                if is_sel or is_hovered:
                    try:
                        lx = pp[0] + r + 3
                        ly = pp[1] - 7
                        label_col = (0, 255, 200) if is_sel else (255, 240, 120)
                        draw.text((lx+1, ly+1), node.name, fill=(0, 0, 0))
                        draw.text((lx,   ly),   node.name, fill=label_col)
                    except Exception:
                        pass

            # ── Bone connection line ───────────────────────────────
            # Effect attachment nodes never draw lines – VFX points only
            if not is_effect_attach:
                par_bone = _nearest_bone_ancestor(node)
                if par_bone is not None:
                    par_wp = _bone_world_pos(par_bone)
                    pp2    = self._proj(*par_wp, W, H)
                    if pp and pp2:
                        dx = pp[0] - pp2[0]; dy = pp[1] - pp2[1]
                        line_len = math.sqrt(dx*dx + dy*dy)
                        if line_len < max(W, H) * 0.5:
                            if is_sel:
                                line_col = _SEL_COL
                            elif is_deform_helper:
                                line_col = _DEFORM_LINE
                            else:
                                line_col = _BONE_LINE
                            lw = 2 if has_joint_children else 1
                            draw.line([pp[0], pp[1], pp2[0], pp2[1]],
                                      fill=line_col, width=lw)

        # Iterative BFS traversal — avoids Python recursion limit on deep models
        # such as c_brith (601 nodes) and other RARE_CHAR type-64 models.
        _stack = [self.model.root_node]
        _visited_ids: set = set()
        while _stack:
            node = _stack.pop()
            nid = id(node)
            if nid in _visited_ids:
                continue
            _visited_ids.add(nid)
            _process_bone_node(node)
            # Push children in reverse order so left-most child is processed first
            for c in reversed(node.children):
                if id(c) not in _visited_ids:
                    _stack.append(c)

        # ── Post-pass: skin influence lines for selected node ──────────────
        # When a skin mesh node is selected, draw dashed lines from the skin
        # node's world position to each of its referenced bone joints.
        # This makes the bone/mesh relationship visible for debugging rigging.
        sel = self.selected_node
        if sel is not None and sel.is_skin and sel.bone_map:
            sel_wp = _bone_world_pos(sel)
            sel_sp = self._proj(*sel_wp, W, H)
            INFL_LINE = (100, 200, 255)   # light blue — influence connection
            for bone_name in sel.bone_map[:16]:   # limit to 16 for performance
                bone_node = self.model.find_node(bone_name) if self.model else None
                if bone_node is None:
                    continue
                b_wp = _bone_world_pos(bone_node)
                b_sp = self._proj(*b_wp, W, H)
                if sel_sp and b_sp:
                    # Dashed influence line
                    x0, y0 = sel_sp[0], sel_sp[1]
                    x1, y1 = b_sp[0],  b_sp[1]
                    dx, dy = x1-x0, y1-y0
                    length = math.sqrt(dx*dx+dy*dy)
                    if 5 < length < max(W, H) * 0.7:
                        steps = max(2, int(length / 8))
                        for s in range(steps):
                            if s % 2 == 0:
                                tx = int(x0 + dx * s / steps)
                                ty = int(y0 + dy * s / steps)
                                tx2= int(x0 + dx * (s+1) / steps)
                                ty2= int(y0 + dy * (s+1) / steps)
                                draw.line([tx, ty, tx2, ty2],
                                          fill=INFL_LINE, width=1)




    # ── AcuRig guide overlay ─────────────────────────────────────────────────

    def set_acurig_guides(self, guides: dict):
        """Register an AcuRig guide dict for viewport overlay rendering.

        Parameters
        ----------
        guides : dict
            Mapping of guide_name → RigGuide (or any object with .position tuple).
            Pass None or {} to clear the overlay.
        """
        self._acurig_guides_overlay = guides or {}
        self._acurig_selected_guide: str = ''
        self.redraw()

    def _draw_acurig_guides(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """Draw AcuRig guide handles as coloured circles with name labels.

        Guides are rendered as:
          • Normal guides     – teal circle (r=7) with white name label
          • Selected guide    – bright yellow circle (r=9) with bold label
          • Left-side (l_*)   – left-colour (cornflower blue)
          • Right-side (r_*)  – right-colour (hot pink)
          • Centre (c_*/mid)  – green

        The overlay is drawn on top of the bone skeleton so modders can
        clearly see guide positions relative to the rig.
        """
        guides = getattr(self, '_acurig_guides_overlay', None)
        if not guides:
            return

        selected = getattr(self, '_acurig_selected_guide', '')

        _TEAL   = (0, 220, 180)
        _YELLOW = (255, 220, 0)
        _BLUE   = (100, 160, 255)
        _PINK   = (255, 80, 160)
        _GREEN  = (80, 220, 80)

        for name, guide in guides.items():
            pos = getattr(guide, 'position', None)
            if pos is None:
                continue
            if len(pos) < 3:
                continue

            sp = self._proj(pos[0], pos[1], pos[2], W, H)
            if sp is None:
                continue
            sx, sy, _ = sp

            nl = name.lower()
            if nl.startswith('l_') or nl.endswith('_l'):
                col = _BLUE
            elif nl.startswith('r_') or nl.endswith('_r'):
                col = _PINK
            elif nl.startswith('c_') or 'mid' in nl or 'center' in nl or 'centre' in nl:
                col = _GREEN
            else:
                col = _TEAL

            is_sel = (name == selected)
            r = 9 if is_sel else 7
            outline = _YELLOW if is_sel else col
            fill    = tuple(max(0, c - 80) for c in col)

            draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=fill, outline=outline, width=2)

            # Diamond crosshair for selected guide
            if is_sel:
                d = 14
                draw.line([sx-d, sy, sx+d, sy], fill=_YELLOW, width=1)
                draw.line([sx, sy-d, sx, sy+d], fill=_YELLOW, width=1)

            # Name label
            try:
                label_col = _YELLOW if is_sel else (200, 230, 255)
                draw.text((sx + r + 3, sy - 6), name, fill=label_col)
            except Exception:
                pass

    def hit_test_acurig_guide(self, mx: int, my: int, radius: int = 14) -> str:
        """
        Return the name of the AcuRig guide whose projected screen circle
        contains the pixel (mx, my), or '' if none.

        We store projected positions during _draw_acurig_guides in a lightweight
        parallel list so this test runs in O(n) without re-projecting.
        """
        guides = getattr(self, '_acurig_guides_overlay', None)
        if not guides:
            return ''
        W = self._last_W if hasattr(self, '_last_W') else 800
        H = self._last_H if hasattr(self, '_last_H') else 600
        best_name = ''
        best_dist2 = radius * radius + 1
        for name, guide in guides.items():
            pos = getattr(guide, 'position', None)
            if pos is None or len(pos) < 3:
                continue
            sp = self._proj(pos[0], pos[1], pos[2], W, H)
            if sp is None:
                continue
            sx, sy, _ = sp
            d2 = (mx - sx) ** 2 + (my - sy) ** 2
            if d2 < best_dist2:
                best_dist2 = d2
                best_name = name
        return best_name

    def _draw_gimbal(self, draw, W: int, H: int):
        """
        Draw a 3-axis translate/rotate gimbal centred on the selected node.

        Translate mode (gimbal_mode==1):
          - Red/Green/Blue axis arrows with arrowheads (X/Y/Z)
          - Yellow/Cyan/Magenta square plane handles (XY, XZ, YZ)
        Rotate mode (gimbal_mode==2):
          - Colour-coded arc rings around each axis

        Handle screen positions are stored in self._gimbal_handles for
        ViewportWidget hit-testing.
        """
        import math as _gm
        node = self.selected_node
        if not node:
            return
        wp, _, _ = self._node_world_transform(node)
        cp = self._proj(*wp, W, H)
        if cp is None:
            return
        cx, cy, cz = cp
        self._gimbal_handles = []

        # Gimbal arm in world units (constant screen size regardless of distance)
        HANDLE_PX = 80
        dist = max(0.5, cz)
        fov_rad = _gm.radians(self.cam.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)
        arm = HANDLE_PX * world_per_px

        axis_colors = {
            'X': (220,  60,  60),
            'Y': ( 60, 220,  60),
            'Z': ( 60, 120, 220),
        }
        active = self.gimbal_active_axis

        if self.gimbal_mode == 1:   # ── Translate ──────────────────
            for name, col in axis_colors.items():
                dx = arm if name == 'X' else 0.0
                dy = arm if name == 'Y' else 0.0
                dz = arm if name == 'Z' else 0.0
                sp = self._proj(wp[0]+dx, wp[1]+dy, wp[2]+dz, W, H)
                if sp is None:
                    continue
                sx, sy, _ = sp
                draw_col = (255, 255, 80) if active == name else col
                lw = 3 if active == name else 2
                draw.line([cx, cy, sx, sy], fill=draw_col, width=lw)
                # Arrowhead
                ddx, ddy = sx - cx, sy - cy
                ll = _gm.sqrt(ddx*ddx + ddy*ddy)
                if ll > 1:
                    ndx, ndy = ddx/ll, ddy/ll
                    px2, py2 = -ndy * 5, ndx * 5
                    draw.polygon([
                        (sx, sy),
                        (int(sx - ndx*10 + px2), int(sy - ndy*10 + py2)),
                        (int(sx - ndx*10 - px2), int(sy - ndy*10 - py2)),
                    ], fill=draw_col)
                self._gimbal_handles.append((sx, sy, name))

            # Plane handles (small squares)
            plane_cfg = {
                'XY': (arm*0.45, arm*0.45, 0.0,      (220, 220,  60)),
                'XZ': (arm*0.45, 0.0,      arm*0.45,  ( 60, 220, 220)),
                'YZ': (0.0,      arm*0.45, arm*0.45,  (220,  60, 220)),
            }
            for pname, (pdx, pdy, pdz, pcol) in plane_cfg.items():
                sp = self._proj(wp[0]+pdx, wp[1]+pdy, wp[2]+pdz, W, H)
                if sp is None:
                    continue
                px2, py2, _ = sp
                c = (255, 255, 80) if active == pname else pcol
                draw.rectangle([px2-6, py2-6, px2+6, py2+6],
                                fill=c, outline=(255, 255, 255))
                self._gimbal_handles.append((px2, py2, pname))

        elif self.gimbal_mode == 2:   # ── Rotate ─────────────────────
            N = 24
            for name, col in axis_colors.items():
                pts = []
                for i in range(N + 1):
                    angle = 2 * _gm.pi * i / N
                    c, s = _gm.cos(angle), _gm.sin(angle)
                    if name == 'X':
                        rp = (wp[0], wp[1]+arm*c, wp[2]+arm*s)
                    elif name == 'Y':
                        rp = (wp[0]+arm*c, wp[1], wp[2]+arm*s)
                    else:
                        rp = (wp[0]+arm*c, wp[1]+arm*s, wp[2])
                    sp = self._proj(*rp, W, H)
                    pts.append((sp[0], sp[1]) if sp else None)
                ring_col = (255, 255, 80) if active == name else col
                lw = 3 if active == name else 2
                for i in range(len(pts) - 1):
                    if pts[i] and pts[i+1]:
                        draw.line([pts[i][0], pts[i][1],
                                   pts[i+1][0], pts[i+1][1]],
                                  fill=ring_col, width=lw)
                # Handle dot at 90 deg for click detection
                c90, s90 = _gm.cos(_gm.pi / 2), _gm.sin(_gm.pi / 2)
                if name == 'X':
                    tip = (wp[0], wp[1]+arm*c90, wp[2]+arm*s90)
                elif name == 'Y':
                    tip = (wp[0]+arm*c90, wp[1], wp[2]+arm*s90)
                else:
                    tip = (wp[0]+arm*c90, wp[1]+arm*s90, wp[2])
                sp = self._proj(*tip, W, H)
                if sp:
                    self._gimbal_handles.append((sp[0], sp[1], name))

        # Centre dot
        draw.ellipse([cx-4, cy-4, cx+4, cy+4],
                      fill=(255, 255, 255), outline=(150, 150, 150))
        mode_lbl = "Translate" if self.gimbal_mode == 1 else "Rotate"
        try:
            draw.text((cx+6, cy-14), f"[{mode_lbl}] {node.name}",
                       fill=(200, 200, 200))
        except Exception:
            pass

    def hit_test_gimbal(self, sx: int, sy: int, radius: int = 10):
        """Return axis/plane name if (sx,sy) is within radius of a gimbal handle, else None."""
        best_axis = None
        best_d2   = radius * radius
        for hx, hy, axis in self._gimbal_handles:
            d2 = (hx - sx)**2 + (hy - sy)**2
            if d2 < best_d2:
                best_d2 = d2
                best_axis = axis
        return best_axis

    # ── External skeleton overlay ─────────────────────────────────────

    def _draw_ext_skeleton(self, draw, W: int, H: int):
        """
        Render an external skeleton (loaded from a separate MDL file) as
        a ghost overlay in purple, offset by _ext_skel_offset.
        Used for the 'Load External Skeleton' rigging workflow.
        """
        if not self._ext_skeleton or not self._ext_skeleton.root_node:
            return
        ox, oy, oz = self._ext_skel_offset
        EXT_DOT  = (180,  80, 255)
        EXT_LINE = (130,  50, 200)
        EXT_SEL  = (255, 200,  80)
        ext_selected = getattr(self, '_ext_skel_selected_node', None)

        def _bp(node):
            p = node.bone_world_position()
            return (p[0]+ox, p[1]+oy, p[2]+oz)

        def _draw_ext_bone(node):
            """Draw one ext-skeleton bone node."""
            wp2 = _bp(node)
            sp  = self._proj(*wp2, W, H)
            is_sel = (node is ext_selected)
            col = EXT_SEL if is_sel else EXT_DOT
            if sp:
                r = 5 if is_sel else 3
                draw.ellipse([sp[0]-r, sp[1]-r, sp[0]+r, sp[1]+r],
                              fill=col, outline=None)
                try:
                    draw.text((sp[0]+4, sp[1]-6), node.name,
                               fill=(160, 100, 220))
                except Exception:
                    pass
            if node.parent:
                pp2 = _bp(node.parent)
                spp = self._proj(*pp2, W, H)
                if sp and spp:
                    draw.line([sp[0], sp[1], spp[0], spp[1]],
                               fill=EXT_LINE, width=1)

        # Iterative BFS — avoid recursion limit on deep ext-skeleton hierarchies
        _ext_stack = [self._ext_skeleton.root_node]
        _ext_visited: set = set()
        while _ext_stack:
            _n = _ext_stack.pop()
            _nid = id(_n)
            if _nid in _ext_visited:
                continue
            _ext_visited.add(_nid)
            _draw_ext_bone(_n)
            for c in reversed(_n.children):
                if id(c) not in _ext_visited:
                    _ext_stack.append(c)

    # ── Walkmesh overlay (Phase 16.1) ─────────────────────────────────

    def _draw_walkmesh_overlay(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw the loaded walkmesh overlay as semi-transparent colored triangles.
        Surface types are color-coded (green=walkable, red=blocked, blue=water, etc.).
        Called after mesh/bone rendering so it appears on top.
        """
        overlay = self._walkmesh_overlay
        if overlay is None or not WalkmeshOverlay:
            return
        try:
            faces = overlay.faces_for_render(
                show_walkable=self.show_walkmesh_walk,
                show_non_walkable=self.show_walkmesh_block)
        except Exception:
            return
        if not faces:
            return

        _BG_R, _BG_G, _BG_B = _BG[0], _BG[1], _BG[2]

        for face in faces:
            try:
                p0 = self._proj(face.v0[0], face.v0[1], face.v0[2], W, H)
                p1 = self._proj(face.v1[0], face.v1[1], face.v1[2], W, H)
                p2 = self._proj(face.v2[0], face.v2[1], face.v2[2], W, H)
            except Exception:
                continue
            if not (p0 and p1 and p2):
                continue

            # face.color is (R,G,B,A) with components in [0.0, 1.0]
            # Blend fill color with background for semi-transparency
            cr, cg, cb, ca = face.color
            # ca is already 0.0-1.0; scale RGB channels to 0-255 for blending
            cr8 = int(cr * 255); cg8 = int(cg * 255); cb8 = int(cb * 255)
            alpha = ca  # 0.0-1.0
            fr = int(cr8 * alpha + _BG_R * (1.0 - alpha))
            fg = int(cg8 * alpha + _BG_G * (1.0 - alpha))
            fb = int(cb8 * alpha + _BG_B * (1.0 - alpha))
            pts = [p0[0], p0[1], p1[0], p1[1], p2[0], p2[1]]
            try:
                draw.polygon(pts, fill=(fr, fg, fb), outline=(cr8, cg8, cb8))
            except Exception:
                pass

    def load_walkmesh(self, wok_data_or_path, world_offset=(0.0, 0.0, 0.0)):
        """
        Load a walkmesh overlay from a WOKData object or file path.
        Stores it in self._walkmesh_overlay; toggled with show_walkmesh.

        Parameters
        ----------
        wok_data_or_path : WOKData instance, file path string, or None to clear.
        world_offset     : (x, y, z) offset to apply to all vertices.
        """
        if not WalkmeshOverlay or not WalkmeshLoader:
            log.debug("walkmesh_renderer not available – walkmesh overlay skipped")
            self._walkmesh_overlay = None
            return
        if wok_data_or_path is None:
            self._walkmesh_overlay = None
            return
        try:
            if isinstance(wok_data_or_path, str):
                loader = WalkmeshLoader()
                overlay = loader.from_file(wok_data_or_path, world_offset)
            else:
                loader = WalkmeshLoader()
                overlay = loader.from_wok_data(wok_data_or_path, world_offset)
            self._walkmesh_overlay = overlay
            log.info(f"Walkmesh loaded: {overlay.summary() if overlay else 'none'}")
        except Exception as e:
            log.warning(f"Walkmesh load failed: {e}")
            self._walkmesh_overlay = None

    def clear_walkmesh(self):
        """Remove the walkmesh overlay."""
        self._walkmesh_overlay = None

    def toggle_walkmesh(self):
        """Toggle walkmesh overlay visibility."""
        self.show_walkmesh = not self.show_walkmesh
        self._request_render()

    # ── Rig-edit mode banner (Phase 22) ──────────────────────────────

    def _draw_rig_edit_banner(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw a prominent orange banner at the top of the viewport when in
        rig-edit mode, reminding the user to drag bones and confirm.
        """
        try:
            bh = 26
            # Semi-transparent orange strip
            draw.rectangle([0, 0, W, bh], fill=(180, 80, 0))
            msg = (
                "  ✦ RIG EDIT MODE  –  Drag bone joints to adjust  ·  "
                "Click 'Confirm Rig' in the Retarget panel when done"
            )
            draw.text((6, 5), msg, fill=(255, 230, 140))
        except Exception:
            pass

    # ── Axes gizmo ────────────────────────────────────────────────────

    def _draw_axes(self, draw: 'ImageDraw.Draw', W: int, H: int):
        ox, oy = 45, H - 45
        L      = 28
        right, up, fwd, _ = self._cam_view_matrix()

        def axis_end(ax):
            dx = _dot(ax, right)
            dy = _dot(ax, up)
            return int(ox + dx*L), int(oy - dy*L)

        x_end = axis_end((1,0,0))
        y_end = axis_end((0,1,0))
        z_end = axis_end((0,0,1))

        draw.line([ox,oy, x_end[0],x_end[1]], fill=_AXIS_X[:3], width=2)
        draw.line([ox,oy, y_end[0],y_end[1]], fill=_AXIS_Y[:3], width=2)
        draw.line([ox,oy, z_end[0],z_end[1]], fill=_AXIS_Z[:3], width=2)

        try:
            draw.text((x_end[0]+3, x_end[1]-6), "X", fill=_AXIS_X[:3])
            draw.text((y_end[0]+3, y_end[1]-6), "Y", fill=_AXIS_Y[:3])
            draw.text((z_end[0]+3, z_end[1]-6), "Z↑", fill=_AXIS_Z[:3])
        except Exception:
            pass

    # ── Stats HUD ─────────────────────────────────────────────────────

    def _draw_stats(self, draw: 'ImageDraw.Draw', W: int, H: int):
        if not self.model:
            draw.text((8, 8), "No model loaded", fill=(150,150,200))
            return
        vc = bc = fc = tex_ok = tex_total = uv_ok = 0
        # Cache visible mesh nodes list for this stats call (avoid 3× iteration)
        visible_nodes = list(self._iter_visible_mesh_nodes())
        # Use _iter_visible_mesh_nodes so outlier skin proxies are excluded from V/F counts
        for n in visible_nodes:
            vc += len(n.vertices)
            fc += len(n.faces)
            if n.texture and _clean_tex_name(n.texture).upper() not in ('NULL',''):
                tex_total += 1
                if self._get_tex(n):
                    tex_ok += 1
            if len(n.uvs) == len(n.vertices) and n.vertices:
                uv_ok += 1
        stack = [self.model.root_node]
        _bc_visited: set = set()
        while stack:
            n = stack.pop()
            if n is None:
                continue
            nid = id(n)
            if nid in _bc_visited:
                continue
            _bc_visited.add(nid)
            if not n.is_mesh:
                bc += 1
            stack.extend(c for c in n.children if c is not None)
        skin_nodes = sum(1 for n in visible_nodes if n.is_skin)
        mode_str = " [TEX+PHONG]" if (self.show_texture and not self.is_interactive) else \
                   " [FLAT(drag)]" if (self.show_texture and self.is_interactive) else \
                   " [FLAT]"
        uv_mesh  = sum(1 for n in visible_nodes if n.vertices)
        # Game version string
        try:
            from ..core.model_data import GameVersion
        except ImportError:
            from core.model_data import GameVersion  # type: ignore
        gv_str = "K1" if self.model.game_version == GameVersion.K1 else "K2"
        txt = (f"{self.model.name}  [{gv_str}]  |  V:{vc:,}  F:{fc:,}  "
               f"Bones:{bc}  Skin:{skin_nodes}  "
               f"UV:{uv_ok}/{uv_mesh}  Tex:{tex_ok}/{tex_total}{mode_str}")
        draw.text((8, 8), txt, fill=(160,160,220))
        # Show render bounds info — use CACHED value (not recomputed every frame)
        rbb_min, rbb_max = self._get_render_bounds()
        dx = rbb_max[0]-rbb_min[0]; dy = rbb_max[1]-rbb_min[1]; dz = rbb_max[2]-rbb_min[2]
        bounds_txt = f"Bounds: {dx:.2f}×{dy:.2f}×{dz:.2f}m"
        draw.text((8, H - 18), bounds_txt, fill=(100, 100, 160))
        if vc == 0:
            # Context-aware "no geometry" message:
            # Check if ALL mesh nodes have render=False (intentional invisible model)
            # vs. model truly has no geometry at all
            #
            # FIX Phase 16.2: Detect reference-only models (NodeFlags.REFERENCE = 0x0010).
            # These are compound models that delegate geometry to external MDL files.
            # Show an informative "⊕ References external model(s):" message instead of
            # the generic "No renderable geometry" warning.
            try:
                _ref_names = [
                    n.emitter_params.get('ref_model', n.name)
                    for n in self.model.all_nodes()
                    if getattr(n, 'is_reference', False)
                ]
            except Exception:
                _ref_names = []
            if _ref_names:
                ref_list = ', '.join(_ref_names[:3])
                if len(_ref_names) > 3:
                    ref_list += f' (+{len(_ref_names)-3} more)'
                draw.text((W//2 - 200, H//2 - 16),
                          "⊕ Reference model – geometry loaded at runtime",
                          fill=(120, 200, 255))
                draw.text((W//2 - 200, H//2),
                          f"  References: {ref_list}",
                          fill=(100, 170, 220))
                return
            all_mesh = list(self._iter_mesh_nodes())
            has_any_verts = any(getattr(n,'vertices',None) for n in all_mesh)
            all_render_false = has_any_verts and all(
                not getattr(n,'render',True) for n in all_mesh
                if getattr(n,'vertices',None)
            )
            name_lower = self.model.name.lower() if self.model and self.model.name else ''
            # Broad non-visual classification — covers VFX, cameras, lights, mini-game
            # helpers, stunt-room scaffolding, level-only environment helpers, and
            # special purpose models that intentionally contain zero renderable geometry.
            # Patterns observed in K1/K2 game data (748 models total):
            #   v_*, fx_*, fx* → VFX / weapon beam / muzzle flash
            #   *cam, *camera → camera placeholder
            #   *_light, *_intlight, *_sun, *light → light dummy
            #   *_mgm*, *_mgt*, *_mgo*, *_mgv*, *mg_* → mini-game sequence models
            #   stuntroom* → cutscene stunt-room scaffolding
            #   mgb_null, mgg_null, *_null → null/placeholder entries
            #   empty, galaxy → engine special placeholders
            #   Numbered area models (e.g. 102perz2, 302narli, 601dand, 421dxn*)
            #     → area-specific environment / camera helpers with no visible mesh
            #   plc_* (smoke/spark/steam/mist/emitter placeables) → all-emitter, no mesh
            #   c_lightsaber → lightsaber blade is pure VFX emitter
            #   w_lfire_* → laser fire beam VFX
            #   w_null_* → weapon null placeholder
            #   m##_set, m##_hd, m##light, m##_camera, m##_char* → level sub-models
            import re as _re
            is_nonvisual = (
                name_lower.startswith('fx_')
                or name_lower.startswith('fx')   # fxmuzzle, fxsmoke, etc.
                or name_lower.startswith('v_')
                or name_lower.startswith('w_laser')
                or name_lower.startswith('w_lfire')  # w_lfire_pb_b1 etc.
                or name_lower.startswith('w_null')
                or name_lower == 'c_lightsaber'  # pure VFX emitter
                or name_lower.endswith('cam')
                or name_lower.endswith('_cam')
                or name_lower.endswith('camera')
                or name_lower.endswith('_light')
                or name_lower.endswith('_intlight')
                or name_lower.endswith('_sun')
                or name_lower.endswith('light')   # m14light etc.
                or '_mgt' in name_lower
                or '_mgo' in name_lower
                or '_mgm' in name_lower
                or '_mgv' in name_lower
                or '_mg_' in name_lower            # m03mg_01b, m26mg_01c
                or name_lower.endswith('_null')
                or name_lower in ('empty', 'galaxy', 'mgb_null', 'mgg_null',
                                  'mg_distort', 'lmg_distort')
                or name_lower.startswith('stuntroom')
                # plc_ models that are pure emitter/VFX (smoke, sparks, steam, mist)
                # — all confirmed to have 0 mesh nodes in audit
                or name_lower.startswith('plc_')
                # Numbered area helpers: 3+ digit prefix then letter code (e.g. 102perz2)
                or bool(_re.match(r'^\d{3}[a-z]', name_lower))
                # Level sub-models: *_set, *_hd, m##_char*, m##mg* (mini-game level)
                or bool(_re.match(r'^m\d+[a-z]*_(set|hd|char)', name_lower))
                or bool(_re.match(r'^m\d+mg', name_lower))   # m03mg_01b, m26mg_01c
                or name_lower.endswith('_set')                # m05aa_set, m28ac_set
                or name_lower.endswith('_hd')                 # m26ad_hd
                # Module area instance models:
                #   m##xx_##x  (e.g. m13aa_01f, m14ab_02d, m22aa_06a)
                #   m##xx_##   (e.g. m34aa_09, m37aa_17, m38aa_12)
                #   m##xx_c##_char##  (e.g. m13aa_c01_char04)
                # These are environment/sound/event scaffolding with no mesh
                or bool(_re.match(r'^m\d{2}[a-z]{2,4}_\d{2}[a-z]?$', name_lower))
                or bool(_re.match(r'^m\d{2}[a-z]{2}_c\d+_char\d+$', name_lower))
                # NPC dummy markers
                or name_lower == 'n_admoff'
                # Weapon LOD placeholder slots (e.g. w_blstrcrbn_006, w_ionrfl_004)
                or bool(_re.match(r'^w_.+_0{1,2}[346]$', name_lower))
            )
            if is_nonvisual or (len(all_mesh) == 0):
                warn = "ℹ Non-visual model (VFX / camera / helper – no display geometry)"
                warn_col = (100, 150, 220)
            elif all_render_false:
                warn = "ℹ All geometry has render=False (engine-internal LOD / collision proxy)"
                warn_col = (150, 180, 100)
            else:
                warn = "⚠ No renderable geometry – check MDL/MDX paths"
                warn_col = (255, 120, 80)
            draw.text((W//2 - 220, H//2 - 8), warn, fill=warn_col)
        elif self.show_texture and tex_ok == 0 and tex_total > 0:
            warn = f"⚠ {tex_total} texture(s) referenced but none loaded – set texture directory"
            draw.text((8, 24), warn, fill=(255,180,80))

        # Show animation state in bottom-right corner
        if self._anim_pose is not None and self._anim_name:
            anim_txt = f"\u25b6 {self._anim_name}"
            if self._anim_length > 0:
                pct = int(100 * self._anim_time / self._anim_length)
                anim_txt += f"  {self._anim_time:.3f}/{self._anim_length:.3f}s  [{pct}%]"
            # Estimate text width (~6px per char at 8pt font) and right-align
            txt_w = len(anim_txt) * 6
            draw.text((max(8, W - txt_w - 8), H - 24), anim_txt, fill=(100, 220, 100))
            # Draw a progress bar at the very bottom of the frame
            bar_h = 4
            bar_y = H - bar_h
            draw.rectangle([0, bar_y, W, H], fill=(20, 30, 40))
            if self._anim_length > 0:
                bar_w = int(W * min(1.0, self._anim_time / self._anim_length))
                draw.rectangle([0, bar_y, bar_w, H], fill=(60, 200, 100))
        elif not self._anim_pose:
            # Show "Bind Pose" indicator when in rest position
            draw.text((W - 72, H - 18), "Bind Pose", fill=(80, 80, 120))


# ─────────────────────────────────────────────────────────────────────
#  UV Viewer Window
# ─────────────────────────────────────────────────────────────────────

class UVViewerWindow(tk.Toplevel):
    """
    Separate minimizable popup showing UV layout for any selected mesh node.

    Features:
      - Node selector dropdown (all mesh nodes)
      - UV channel selector (UV0 / UV1 lightmap)
      - Checkerboard background + texture overlay option
      - Triangle edges (green), seam edges (red)
      - Optional vertex dots
      - Zoom & pan with mouse
      - Fit button to reset view
    """

    _BG_DARK    = "#0d0d1a"
    _BG_PANEL   = "#13132b"
    _UV_EDGE    = "#44ff88"
    _UV_SEAM    = "#ff4444"
    _UV_VERT    = "#ffcc44"
    _UV_FILL    = (30, 80, 60, 80)
    _CHECKER_A  = (40, 40, 55)
    _CHECKER_B  = (25, 25, 40)
    _CHECKER_SZ = 32

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.title("UV Viewer  —  GhostRigger-K1-K2")
        self.geometry("640x640")
        self.configure(bg=self._BG_DARK)
        self.minsize(320, 320)

        self._model: Optional[KotorModel] = None
        self._mesh_nodes: List[ModelNode] = []
        self._selected_node: Optional[ModelNode] = None
        self._photo: Optional['ImageTk.PhotoImage'] = None
        self._tex_cache: Optional['TextureCache'] = None  # set by ViewportWidget.open_uv_viewer

        self._zoom   = 1.0
        self._pan_x  = 0.0
        self._pan_y  = 0.0
        self._mx = self._my = 0
        self._render_pending = False

        self._build_ui()
        self._schedule_render()

    def _build_ui(self):
        tb = tk.Frame(self, bg=self._BG_PANEL, height=34)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        btn_style = dict(bg="#1e1e3a", fg="#ccccff", relief='flat',
                         activebackground="#3333aa", activeforeground="white",
                         padx=5, pady=2, font=("Segoe UI", 8), cursor="hand2",
                         bd=0, highlightthickness=0)

        tk.Label(tb, text="Node:", bg=self._BG_PANEL, fg="#aaaacc",
                 font=("Segoe UI", 8)).pack(side='left', padx=(6, 2))

        self._node_var = tk.StringVar(value="(no model)")
        self._node_combo = ttk.Combobox(tb, textvariable=self._node_var,
                                         state='readonly', width=22,
                                         font=("Segoe UI", 8))
        self._node_combo.pack(side='left', padx=2)
        self._node_combo.bind('<<ComboboxSelected>>', self._on_node_selected)

        tk.Label(tb, text="  UV:", bg=self._BG_PANEL, fg="#aaaacc",
                 font=("Segoe UI", 8)).pack(side='left', padx=(8, 2))
        self._uv_chan_var = tk.StringVar(value="UV0")
        for ch in ("UV0", "UV1 (LM)"):
            tk.Radiobutton(tb, text=ch, variable=self._uv_chan_var, value=ch,
                           bg=self._BG_PANEL, fg="#aaaacc",
                           selectcolor="#222244", activebackground=self._BG_PANEL,
                           font=("Segoe UI", 8),
                           command=self._request_render).pack(side='left', padx=2)

        self._show_verts_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Verts", variable=self._show_verts_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=4)

        self._show_seams_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Seams", variable=self._show_seams_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=2)

        # Texture overlay — show actual texture behind UV wireframe
        self._show_tex_var = tk.BooleanVar(value=True)
        tk.Checkbutton(tb, text="Texture", variable=self._show_tex_var,
                       bg=self._BG_PANEL, fg="#aaaacc",
                       selectcolor="#222244", activebackground=self._BG_PANEL,
                       font=("Segoe UI", 8),
                       command=self._request_render).pack(side='left', padx=4)

        tk.Button(tb, text="⊞ Fit", command=self._fit_view,
                  **btn_style).pack(side='right', padx=4)

        self._canvas = tk.Canvas(self, bg=self._BG_DARK,
                                 highlightthickness=0,
                                 cursor="fleur")
        self._canvas.pack(fill='both', expand=True)

        self._canvas.bind("<ButtonPress-1>",  self._press)
        self._canvas.bind("<B1-Motion>",      self._drag)
        self._canvas.bind("<MouseWheel>",     self._on_scroll)
        self._canvas.bind("<Button-4>",       lambda e: self._zoom_step(1.15))
        self._canvas.bind("<Button-5>",       lambda e: self._zoom_step(0.87))
        self._canvas.bind("<Configure>",      lambda e: self._request_render())

        self._status_var = tk.StringVar(value="No model loaded")
        tk.Label(self, textvariable=self._status_var,
                 bg=self._BG_PANEL, fg="#6060aa",
                 font=("Segoe UI", 8), anchor='w').pack(
                 fill='x', side='bottom', padx=4)

    def set_model(self, model: Optional[KotorModel]):
        self._model = model
        self._mesh_nodes = list(self._iter_mesh_nodes(model)) if model else []

        names = [n.name for n in self._mesh_nodes]
        self._node_combo['values'] = names if names else ["(no mesh nodes)"]

        if self._mesh_nodes:
            if self._selected_node and self._selected_node in self._mesh_nodes:
                idx = self._mesh_nodes.index(self._selected_node)
            else:
                idx = 0
                self._selected_node = self._mesh_nodes[0]
            self._node_var.set(names[idx])
        else:
            self._selected_node = None
            self._node_var.set("(no mesh nodes)")

        self._fit_view()
        self._request_render()

    def set_selected_node(self, node: Optional[ModelNode]):
        if node and node in self._mesh_nodes:
            self._selected_node = node
            self._node_var.set(node.name)
            self._request_render()

    def _iter_mesh_nodes(self, model):
        """Yield mesh nodes with UV/vertex data (depth-first, cycle-safe)."""
        if not model or not model.root_node:
            return
        stack = [model.root_node]
        visited: set = set()
        while stack:
            n = stack.pop()
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            # Include mesh nodes that have UVs OR vertices (show at least something)
            if n.is_mesh and (n.uvs or n.vertices):
                yield n
            stack.extend(n.children)

    def _on_node_selected(self, event=None):
        name = self._node_var.get()
        for n in self._mesh_nodes:
            if n.name == name:
                self._selected_node = n
                break
        self._request_render()

    def _fit_view(self):
        """Fit UV view to show all UVs including tiling outside 0-1 range."""
        W = self._canvas.winfo_width() or 640
        H = self._canvas.winfo_height() or 640
        margin = 32

        # Calculate UV extent including tiles outside 0-1 for selected node
        node = self._selected_node
        if node and node.uvs:
            us = [uv[0] for uv in node.uvs]
            vs = [uv[1] for uv in node.uvs]
            u_min, u_max = min(us), max(us)
            v_min, v_max = min(vs), max(vs)
            # Expand to at least 0-1 range
            u_min = min(u_min, 0.0); u_max = max(u_max, 1.0)
            v_min = min(v_min, 0.0); v_max = max(v_max, 1.0)
            # Add some padding
            u_pad = (u_max - u_min) * 0.1 + 0.05
            v_pad = (v_max - v_min) * 0.1 + 0.05
            u_min -= u_pad; u_max += u_pad
            v_min -= v_pad; v_max += v_pad
            uv_w = u_max - u_min
            uv_h = v_max - v_min
            # Fit to canvas preserving aspect ratio
            avail_w = W - margin * 2
            avail_h = H - margin * 2
            scale = min(avail_w / max(uv_w, 0.001), avail_h / max(uv_h, 0.001))
            self._zoom = scale
            # Center the UV range
            disp_w = uv_w * scale
            disp_h = uv_h * scale
            self._pan_x = margin + (avail_w - disp_w) * 0.5 - u_min * scale
            self._pan_y = margin + (avail_h - disp_h) * 0.5 + (1.0 + v_min) * scale - scale
        else:
            size = min(W, H) - margin * 2
            self._zoom  = float(size)
            self._pan_x = margin + (W - size) * 0.5
            self._pan_y = margin + (H - size) * 0.5
        self._request_render()

    def _uv_to_screen(self, u: float, v: float) -> Tuple[int, int]:
        sx = int(self._pan_x + u * self._zoom)
        sy = int(self._pan_y + (1.0 - v) * self._zoom)
        return sx, sy

    def _press(self, e):
        self._mx, self._my = e.x, e.y

    def _drag(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self._pan_x += dx
        self._pan_y += dy
        self._request_render()

    def _on_scroll(self, e):
        steps = -(e.delta / 120.0) if e.delta else -1
        factor = 0.9 ** steps
        self._zoom_step(factor, cx=e.x, cy=e.y)

    def _zoom_step(self, factor: float, cx: int = None, cy: int = None):
        W = self._canvas.winfo_width() or 640
        H = self._canvas.winfo_height() or 640
        cx = cx if cx is not None else W // 2
        cy = cy if cy is not None else H // 2
        old_zoom = self._zoom
        new_zoom = _clamp(self._zoom * factor, 32.0, 8192.0)
        ratio = new_zoom / old_zoom
        self._pan_x = cx - (cx - self._pan_x) * ratio
        self._pan_y = cy - (cy - self._pan_y) * ratio
        self._zoom  = new_zoom
        self._request_render()

    def _request_render(self):
        self._render_pending = True

    def _schedule_render(self):
        if not self.winfo_exists():
            return
        if self._render_pending:
            self._render_pending = False
            self._do_render()
        self.after(33, self._schedule_render)

    def _do_render(self):
        if not _PIL:
            return
        W = self._canvas.winfo_width()
        H = self._canvas.winfo_height()
        if W < 4 or H < 4:
            return

        img_rgb = Image.new('RGB', (W, H), (13, 13, 26))
        draw = ImageDraw.Draw(img_rgb)

        self._draw_checker(draw, W, H)

        # ── v12.9: Texture overlay ────────────────────────────────────────────
        # When "Texture" checkbox is on and the selected node has a texture,
        # draw the actual texture image inside the UV 0-1 square so users can
        # verify that UV wireframe edges align with texture seams.
        # The texture is displayed semi-transparently so the wireframe remains
        # readable on top.
        node = self._selected_node
        if node and getattr(self, '_show_tex_var', None) and self._show_tex_var.get():
            tex_name = _clean_tex_name(getattr(node, 'texture', '') or '')
            if tex_name and self._tex_cache is not None:
                try:
                    tex_img = self._tex_cache.get(tex_name)
                    if tex_img is not None:
                        # Compute screen rect for UV [0,1]×[0,1] square
                        tl = self._uv_to_screen(0.0, 1.0)
                        br = self._uv_to_screen(1.0, 0.0)
                        x0, y0 = int(tl[0]), int(tl[1])
                        x1, y1 = int(br[0]), int(br[1])
                        sw = max(1, x1 - x0)
                        sh = max(1, y1 - y0)
                        # Resize texture to fit the UV square
                        tex_rgba = tex_img.convert('RGBA').resize((sw, sh), Image.BILINEAR)
                        # Create a dimmed copy so wireframe stays visible
                        import numpy as _np
                        ta = _np.array(tex_rgba, dtype=_np.uint16)
                        ta[:, :, :3] = (ta[:, :, :3] * 180 // 255).clip(0, 255)
                        ta[:, :, 3] = 220  # semi-transparent overlay
                        tex_overlay = Image.fromarray(ta.astype(_np.uint8), 'RGBA')
                        img_rgba = img_rgb.convert('RGBA')
                        img_rgba.paste(tex_overlay, (x0, y0), tex_overlay.split()[3])
                        img_rgb = img_rgba.convert('RGB')
                        draw = ImageDraw.Draw(img_rgb)
                except Exception:
                    pass  # silently skip on error; checkerboard fallback is fine

        self._draw_uv_border(draw, W, H)

        if node and node.uvs and node.faces:
            self._draw_uvs(draw, img_rgb, node, W, H)
            uv_count = len(node.uvs)
            face_count = len(node.faces)
            self._status_var.set(
                f"{node.name}  |  UVs: {uv_count}  Faces: {face_count}  "
                f"Verts: {len(node.vertices)}  Tex: {node.texture or '(none)'}  "
                f"Zoom: {self._zoom:.0f}px/unit")
        else:
            draw.text((W//2 - 80, H//2 - 8),
                      "No UV data for this node",
                      fill=(150, 100, 100))
            self._status_var.set("No UV data")

        try:
            photo = ImageTk.PhotoImage(img_rgb)
            self._photo = photo
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor='nw', image=photo)
        except Exception as e:
            log.debug(f"UV viewer render error: {e}")

    def _draw_checker(self, draw, W, H):
        sz = self._CHECKER_SZ
        for iy in range(0, H, sz):
            for ix in range(0, W, sz):
                parity = ((ix // sz) + (iy // sz)) % 2
                col = self._CHECKER_A if parity == 0 else self._CHECKER_B
                draw.rectangle([ix, iy, ix+sz-1, iy+sz-1], fill=col)

    def _draw_uv_border(self, draw, W, H):
        """Draw UV 0-1 border and tiling grid lines for UVs outside 0-1 range."""
        tl = self._uv_to_screen(0.0, 1.0)
        br = self._uv_to_screen(1.0, 0.0)
        border_col  = (80, 80, 160)
        tile_col    = (50, 50, 90)

        # Draw main 0-1 UV border (highlighted)
        draw.rectangle([tl[0], tl[1], br[0], br[1]], outline=border_col, width=2)
        try:
            draw.text((tl[0], tl[1] - 14), "V=1", fill=(80, 80, 140))
            draw.text((tl[0] - 22, br[1] + 2), "V=0", fill=(80, 80, 140))
            draw.text((tl[0], br[1] + 4), "U=0", fill=(80, 80, 140))
            draw.text((br[0] - 20, br[1] + 4), "U=1", fill=(80, 80, 140))
        except Exception:
            pass

        # Draw tiling grid for tiles outside 0-1 range (lighter lines)
        node = self._selected_node
        if node and node.uvs:
            us = [uv[0] for uv in node.uvs]
            vs = [uv[1] for uv in node.uvs]
            u_min = int(min(us)) - 1
            u_max = int(max(us)) + 2
            v_min = int(min(vs)) - 1
            v_max = int(max(vs)) + 2
            if u_min < 0 or u_max > 1 or v_min < 0 or v_max > 1:
                for ui in range(u_min, u_max + 1):
                    if ui == 0 or ui == 1:
                        continue
                    p1 = self._uv_to_screen(float(ui), float(v_min))
                    p2 = self._uv_to_screen(float(ui), float(v_max))
                    if p1 and p2:
                        draw.line([p1[0], p1[1], p2[0], p2[1]],
                                  fill=tile_col, width=1)
                for vi in range(v_min, v_max + 1):
                    if vi == 0 or vi == 1:
                        continue
                    p1 = self._uv_to_screen(float(u_min), float(vi))
                    p2 = self._uv_to_screen(float(u_max), float(vi))
                    if p1 and p2:
                        draw.line([p1[0], p1[1], p2[0], p2[1]],
                                  fill=tile_col, width=1)

    # ── UV island palette (per-island coloring) ───────────────────────────
    # Each disconnected UV island gets a distinct color for easy visual
    # identification.  Colors are chosen to be visible on both dark checker-
    # board and semi-transparent texture backgrounds.
    _UV_ISLAND_COLORS = [
        (0x44, 0xff, 0x88),   # green  (default)
        (0x44, 0xcc, 0xff),   # cyan
        (0xff, 0xcc, 0x44),   # yellow
        (0xff, 0x66, 0xcc),   # pink
        (0x88, 0x88, 0xff),   # lavender
        (0xff, 0x88, 0x44),   # orange
        (0x44, 0xff, 0xcc),   # mint
        (0xff, 0x44, 0x44),   # red
    ]

    @staticmethod
    def _compute_uv_islands(valid_faces: list, n_uvs: int) -> dict:
        """
        Find connected UV islands using union-find on UV vertex adjacency.
        Returns a dict mapping face-index → island-id (0-based).
        Two faces are in the same island if they share a UV vertex.
        """
        parent = list(range(n_uvs))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            a, b = find(a), find(b)
            if a != b:
                parent[a] = b

        for ui0, ui1, ui2 in valid_faces:
            union(ui0, ui1)
            union(ui1, ui2)

        # Build island id remapping (canonical root → 0-based island id)
        root_to_id: Dict[int, int] = {}
        face_island: Dict[int, int] = {}
        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            root = find(ui0)
            if root not in root_to_id:
                root_to_id[root] = len(root_to_id)
            face_island[fi] = root_to_id[root]

        return face_island

    @staticmethod
    @staticmethod
    def _compute_adaptive_edge_threshold(uvs: list, faces: list) -> float:
        """
        Compute an adaptive long-edge filter threshold based on the mesh's
        actual UV edge length distribution.

        For normal meshes (body, horns, eyes): no filtering (threshold=1.0)
        For full-span fin meshes (bthair, spans full V=0..1): tight filter 0.05
        For other fin meshes (head_Hair, partial span): use boundary-only mode
          by returning a very large value — handled via 'fin mesh' flag in caller

        Returns:
          (threshold_sq, is_fin_mesh)
        """
        n_uvs = len(uvs)
        lengths_sq = []
        for face in faces:
            if len(face) < 3:
                continue
            v0, v1, v2 = face
            if max(v0, v1, v2) >= n_uvs:
                continue
            for i, j in ((v0, v1), (v1, v2), (v2, v0)):
                du = uvs[i][0] - uvs[j][0]
                dv = uvs[i][1] - uvs[j][1]
                lengths_sq.append(du * du + dv * dv)

        if len(lengths_sq) < 4:
            return 0.40  # default fallback

        lengths_sq.sort()
        p75_sq = lengths_sq[int(0.75 * len(lengths_sq))]
        p95_sq = lengths_sq[int(0.95 * len(lengths_sq))]

        if p75_sq > 0.50:
            # Full-span fin mesh (bthair): very long edges at 75th percentile.
            # These fins span nearly the full UV height (V=0..1).
            # Use tight threshold to show only the narrow base/top edges.
            return 0.05
        elif p75_sq > 0.10:
            # Partial-span fin mesh (head_Hair): edges at 75th percentile are
            # medium length.  Show only boundary (seam) edges to avoid clutter.
            # Return a very small threshold so essentially no interior edges pass;
            # the caller will still show seam edges (boundary) as those are
            # detected separately via edge_count == 1.
            return 0.04
        elif p95_sq > 0.10:
            # Mostly-normal mesh with a small tail of longer edges.
            return 0.20
        else:
            # Normal mesh (body, horns, eyes): all edges are short.
            return 1.0  # no filter

    def _draw_uvs(self, draw, img, node, W, H):
        uvs   = node.uvs
        faces = node.faces
        n_uvs = len(uvs)
        # face_uvs: per-face tvert index triples (ASCII MDL only)
        face_uvs_list = getattr(node, 'face_uvs', [])
        _has_face_uvs = bool(face_uvs_list) and len(face_uvs_list) == len(faces)

        if n_uvs == 0:
            draw.text((W//2 - 80, H//2 - 8),
                      f"{node.name}: No UV data",
                      fill=(150, 100, 100))
            return

        show_seams = self._show_seams_var.get()
        show_verts = self._show_verts_var.get()

        # When UV count doesn't exactly match vertex count, clamp indices
        n_verts = len(node.vertices) if node.vertices else n_uvs
        use_clamped = (n_uvs != n_verts)

        edge_count: Dict[Tuple[int,int], int] = {}
        valid_faces = []
        for _fi, face in enumerate(faces):
            if len(face) < 3:
                continue
            vi0, vi1, vi2 = face[0], face[1], face[2]
            # Resolve tvert indices
            if _has_face_uvs:
                fuv = face_uvs_list[_fi]
                ui0, ui1, ui2 = fuv[0], fuv[1], fuv[2]
            else:
                ui0, ui1, ui2 = vi0, vi1, vi2
            # Clamp UV indices to valid range
            ui0 = min(ui0, n_uvs - 1)
            ui1 = min(ui1, n_uvs - 1)
            ui2 = min(ui2, n_uvs - 1)
            if ui0 < 0 or ui1 < 0 or ui2 < 0:
                continue
            valid_faces.append((ui0, ui1, ui2))
            for e in ((min(ui0,ui1), max(ui0,ui1)),
                      (min(ui1,ui2), max(ui1,ui2)),
                      (min(ui2,ui0), max(ui2,ui0))):
                edge_count[e] = edge_count.get(e, 0) + 1

        # ── Adaptive edge-length threshold ────────────────────────────────────
        # Replaces the hard-coded 0.40 sq threshold with a mesh-aware value:
        #  - Normal meshes (body, horns, eyes): threshold = 1.0 (no filtering)
        #  - Full-span fin/hair meshes (bthair): threshold = 0.05 (tight)
        #  - Partial-span fin meshes (head_Hair): threshold = 0.04 (boundary only)
        # For all fin meshes, seam (boundary) edges are ALWAYS shown regardless
        # of length — this ensures the perimeter of each UV island is visible.
        _long_edge_sq_thresh = self._compute_adaptive_edge_threshold(uvs, faces)
        # Fin mesh flag: for partial-span fins, draw seams even for long edges
        _is_fin = _long_edge_sq_thresh <= 0.05

        # ── UV island detection for per-island fill coloring ──────────────────
        face_island = self._compute_uv_islands(valid_faces, n_uvs)
        n_islands = max(face_island.values(), default=-1) + 1
        island_colors = self._UV_ISLAND_COLORS

        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)

        # When texture overlay is active, use a thinner semi-transparent fill
        # so the texture remains visible under the UV wireframe.
        tex_overlay_active = (getattr(self, '_show_tex_var', None) is not None
                              and self._show_tex_var.get()
                              and self._tex_cache is not None
                              and _clean_tex_name(getattr(node, 'texture', '') or ''))
        _fill_alpha = 25 if tex_overlay_active else 60

        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            p0 = self._uv_to_screen(*uvs[ui0])
            p1 = self._uv_to_screen(*uvs[ui1])
            p2 = self._uv_to_screen(*uvs[ui2])
            if all(p[0] < -W or p[0] > W*2 or p[1] < -H or p[1] > H*2
                   for p in (p0, p1, p2)):
                continue
            # Use per-island color for the fill
            iid = face_island.get(fi, 0)
            ir, ig, ib = island_colors[iid % len(island_colors)]
            ov_draw.polygon([p0[0],p0[1], p1[0],p1[1], p2[0],p2[1]],
                             fill=(ir, ig, ib, _fill_alpha))

        img_rgba = img.convert('RGBA')
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        img.paste(img_rgba.convert('RGB'))

        for fi, (ui0, ui1, ui2) in enumerate(valid_faces):
            p0 = self._uv_to_screen(*uvs[ui0])
            p1 = self._uv_to_screen(*uvs[ui1])
            p2 = self._uv_to_screen(*uvs[ui2])
            iid = face_island.get(fi, 0)
            island_rgb = island_colors[iid % len(island_colors)]
            island_hex = '#{:02x}{:02x}{:02x}'.format(*island_rgb)

            edges_of_face = [
                ((min(ui0,ui1), max(ui0,ui1)), p0, p1, uvs[ui0], uvs[ui1]),
                ((min(ui1,ui2), max(ui1,ui2)), p1, p2, uvs[ui1], uvs[ui2]),
                ((min(ui2,ui0), max(ui2,ui0)), p2, p0, uvs[ui2], uvs[ui0]),
            ]
            for edge_key, pa, pb, uva, uvb in edges_of_face:
                # Adaptive long-edge filter: skip diagonal edges that span
                # more UV space than the mesh-appropriate threshold.
                # For fin/hair meshes this removes the "X-pattern" grid noise;
                # for normal body/horn meshes all edges pass through.
                du = uva[0] - uvb[0]
                dv = uva[1] - uvb[1]
                uv_len_sq = du*du + dv*dv
                is_long = uv_len_sq > _long_edge_sq_thresh
                is_seam = edge_count.get(edge_key, 0) == 1
                if is_long:
                    # For fin meshes, still draw long boundary/seam edges
                    # so the island perimeter is visible even when internal
                    # diagonal edges are suppressed.
                    if not (show_seams and is_seam and _is_fin):
                        continue
                if show_seams and is_seam:
                    # Seam edge (boundary): draw in seam color at width=2
                    draw.line([pa[0],pa[1], pb[0],pb[1]], fill=self._UV_SEAM, width=2)
                else:
                    # Interior/shared edge: draw in per-island color
                    draw.line([pa[0],pa[1], pb[0],pb[1]], fill=island_hex, width=1)

        if show_verts:
            drawn_verts = set()
            for ui0, ui1, ui2 in valid_faces:
                for ui in (ui0, ui1, ui2):
                    if ui in drawn_verts:
                        continue
                    drawn_verts.add(ui)
                    px, py = self._uv_to_screen(*uvs[ui])
                    if -4 <= px <= W+4 and -4 <= py <= H+4:
                        r = 2
                        draw.ellipse([px-r, py-r, px+r, py+r],
                                     fill=self._UV_VERT, outline=None)

        # ── Island count status hint ──────────────────────────────────────────
        # Append island count to help users understand UV layout complexity.
        if n_islands > 1 and hasattr(self, '_status_var'):
            try:
                current = self._status_var.get()
                if 'Islands:' not in current:
                    self._status_var.set(current + f'  Islands: {n_islands}')
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────
#  ViewportWidget  (Tkinter Frame)
# ─────────────────────────────────────────────────────────────────────

class ViewportWidget(tk.Frame):
    """
    Embeds a Tkinter Canvas and drives FrameRenderer at ~30 fps.
    """

    _RENDER_MS = 33          # ~30 fps idle render tick
    _RENDER_MS_INTERACTIVE = 16  # ~60 fps during active drag (feels snappier)

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.configure(bg="#0d0d1a")

        self.camera  = ArcBallCamera()
        self.model:  Optional[KotorModel] = None
        self._renderer = FrameRenderer(self.camera)

        self._mx = self._my = 0
        self._drag_mode = 'orbit'
        self._render_pending = False
        self._render_fast    = False          # True → use _RENDER_MS_INTERACTIVE tick
        self._render_in_progress = False   # guard: only one render thread at a time
        self._render_started_at: float = 0.0  # perf_counter when render thread launched
        self._last_render_ms: float = 0.0     # last frame render time in ms
        self._render_frame_count: int = 0     # total frames rendered
        # FIX (v10.4): FPS counter uses wall-clock time between displayed frames
        # (not render_ms sum) so the reading is accurate when the render thread
        # is idle between frames.  _fps_last_wall is updated when a frame arrives.
        self._fps_accum: float = 0.0          # accumulated wall-clock time for FPS
        self._fps_frames: int = 0             # frames received in current FPS window
        self._fps_display: float = 0.0        # last computed FPS value
        self._fps_last_wall: float = _time_mod.perf_counter()  # wall-clock at last frame
        self._photo: Optional['ImageTk.PhotoImage'] = None
        self._drag_threshold = 4  # pixels moved before treating click as drag
        self._press_x = self._press_y = 0
        self._is_dragging = False

        # ── Two-pass progressive render state ────────────────────────────────
        # After a drag ends (is_interactive goes False), the first textured frame
        # uses mip1 (half-res) for fast visual feedback, then immediately queues
        # a second full-quality frame.  _lq_pending_hq = True means: after the
        # current LQ render completes, queue one more HQ render automatically.
        self._lq_pending_hq: bool = False

        # Callback: called with (node) when user clicks a bone, or None for deselect
        self.on_bone_selected = None
        # Callback: called with (node) when user clicks a mesh node
        self.on_node_selected = None
        # Callback: called when a node's position is modified via gimbal drag
        self.on_node_moved = None

        self._uv_viewer: Optional[UVViewerWindow] = None

        # ── Gimbal drag state ─────────────────────────────────────────
        self._gimbal_dragging: bool = False
        self._gimbal_axis: str = ''
        self._gimbal_drag_start: tuple = (0, 0)
        self._gimbal_node_start_pos: tuple = (0.0, 0.0, 0.0)

        # ── AcuRig guide drag state ────────────────────────────────────
        self._acurig_guide_dragging: bool = False
        self._acurig_drag_guide_name: str = ''
        self._acurig_drag_start: tuple = (0, 0)
        # Callback: (guide_name, new_world_pos) when a guide is moved
        self.on_acurig_guide_moved = None

        # Thread-safe render result queue: render thread posts (img, render_ms)
        # here; _schedule_render drains it on the main thread.  This avoids
        # calling self.after() from a background thread, which raises
        # RuntimeError("main thread is not in main loop") on Linux/macOS.
        import queue as _queue
        self._render_result_queue: '_queue.Queue' = _queue.Queue(maxsize=2)

        self._build_toolbar()
        self._build_canvas()

    def _build_toolbar(self):
        tb = tk.Frame(self, bg="#0e0e20", height=30)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)

        # Base button style
        btn = dict(bg="#1a1a3a", fg="#ccccff", relief='flat',
                   activebackground="#3333aa", activeforeground="white",
                   padx=6, pady=2, font=("Segoe UI", 8), cursor="hand2",
                   bd=0, highlightthickness=0)

        def _vp_sep():
            """Thin separator for viewport toolbar."""
            return tk.Frame(tb, bg="#252550", width=1)

        def _vp_tip(widget, text):
            """Attach tooltip to a viewport toolbar widget."""
            tip_win = None
            def show(e):
                nonlocal tip_win
                if tip_win: return
                x = widget.winfo_rootx() + 4
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                tip_win = tk.Toplevel(widget)
                tip_win.wm_overrideredirect(True)
                tip_win.wm_geometry(f"+{x}+{y}")
                tk.Label(tip_win, text=text, bg="#1a1a4a", fg="#ccccff",
                         font=("Segoe UI", 7), relief='flat',
                         padx=5, pady=2).pack()
            def hide(e):
                nonlocal tip_win
                if tip_win:
                    try: tip_win.destroy()
                    except Exception: pass
                    tip_win = None
            widget.bind("<Enter>", show, add='+')
            widget.bind("<Leave>", hide, add='+')
            widget.bind("<ButtonPress>", hide, add='+')

        # ── Display group ────────────────────────────────────────────────
        self._btn_wire = tk.Button(
            tb, text="⬚ Wire  W", command=self._toggle_wireframe, **btn)
        self._btn_wire.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_wire, "Toggle wireframe overlay  (W)")

        self._btn_bones = tk.Button(
            tb, text="🦴 Bones  B", command=self._toggle_bones, **btn)
        self._btn_bones.configure(bg="#333322")   # on by default
        self._btn_bones.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_bones, "Toggle skeleton/bone overlay  (B)")

        self._btn_tex = tk.Button(
            tb, text="🖼 Texture  T", command=self._toggle_texture, **btn)
        self._btn_tex.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_tex, "Toggle texture rendering  (T)")

        # Shade radio group (compact, no label)
        self._shade_var = tk.StringVar(value="Solid")
        shade_frame = tk.Frame(tb, bg="#0e0e20")
        shade_frame.pack(side='left', padx=2)
        for shade in ("Solid", "Wire", "Both"):
            display = shade if shade != "Wire" else "Wires"
            val     = shade if shade != "Wire" else "Wireframe"
            tk.Radiobutton(
                shade_frame, text=shade, variable=self._shade_var, value=val,
                bg="#0e0e20", fg="#9999cc", selectcolor="#1e2244",
                activebackground="#0e0e20", font=("Segoe UI", 8),
                command=self._on_shade_change
            ).pack(side='left', padx=1)

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Navigation group ─────────────────────────────────────────────
        b_frame_all = tk.Button(tb, text="⊞ Frame  F",
                                command=self.frame_all, **btn)
        b_frame_all.pack(side='left', padx=2, pady=2)
        _vp_tip(b_frame_all, "Frame all geometry in view  (F)")

        self._btn_wok = tk.Button(
            tb, text="🗺 WalkMesh", command=self._toggle_walkmesh_btn, **btn)
        self._btn_wok.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_wok, "Toggle walkmesh overlay")

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Transform/Gimbal group ──────────────────────────────────────
        self._btn_gimbal = tk.Button(
            tb, text="✛ Gimbal  G", command=self._toggle_gimbal, **btn)
        self._btn_gimbal.configure(bg="#334422")   # on by default
        self._btn_gimbal.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gimbal, "Toggle gimbal (node transform handle)  (G)")

        self._btn_gimbal_mode = tk.Button(
            tb, text="[Translate]", command=self._cycle_gimbal_mode, **btn)
        self._btn_gimbal_mode.configure(bg="#223344")
        self._btn_gimbal_mode.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gimbal_mode, "Cycle gimbal mode: Translate → Rotate  (Tab)")

        # ── Rig-Edit toggle (Phase 22) ──────────────────────────────────
        self._btn_rig_edit = tk.Button(
            tb, text="✦ Rig Edit", command=self._toggle_rig_edit_mode, **btn)
        self._btn_rig_edit.configure(bg="#1e1e3a")   # inactive = dark
        self._btn_rig_edit.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_rig_edit,
                "Toggle Rig-Edit Mode: drag bone joints to adjust positions.\n"
                "Click again or press 'Confirm Rig' in the Retarget panel "
                "to bake and finish.")

        _vp_sep().pack(side='left', fill='y', padx=4, pady=4)

        # ── Utility group ─────────────────────────────────────────────
        self._btn_uv = tk.Button(
            tb, text="UV View", command=self._open_uv_viewer, **btn)
        self._btn_uv.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_uv, "Open UV editor window")

        # Fast-drag toggle (for low-power machines)
        self._fast_drag_enabled: bool = False  # default: fast drag OFF
        self._btn_fast_drag = tk.Button(
            tb, text="⚡ Fast", command=self._toggle_fast_drag, **btn)
        self._btn_fast_drag.configure(bg="#1a1a3a")  # dark = inactive
        self._btn_fast_drag.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_fast_drag,
                "Fast-drag mode: drops to flat-shading during orbit\n"
                "(faster on slow machines, textures hidden during drag)")

        # ── Renderer toggle (CPU ↔ GPU) ─────────────────────────────
        # v6.0: UI toggle to switch between CPU PIL rasterizer and GPU
        # ModernGL renderer at runtime.  GPU provides z-buffer depth testing,
        # back-face culling, and 60fps for ≤100k triangles.  CPU fallback
        # remains available for systems without GPU/EGL support.
        # Cross-ref: Deliverable 3 (T308); Hayes (2025) §6.3.
        self._use_gpu: bool = False  # default: CPU renderer (safe fallback)
        self._gpu_renderer = None    # lazy-init GpuRenderer on first toggle
        self._btn_gpu = tk.Button(
            tb, text="CPU", command=self._toggle_gpu_renderer, **btn)
        self._btn_gpu.configure(bg="#1a1a3a")  # dark = CPU mode
        self._btn_gpu.pack(side='left', padx=2, pady=2)
        _vp_tip(self._btn_gpu,
                "Toggle CPU ↔ GPU renderer  (Ctrl+G)\n"
                "GPU: z-buffer depth, back-face culling, 60fps\n"
                "CPU: software rasterizer fallback")

        # Reset camera (far right)
        b_reset = tk.Button(tb, text="↺ Camera",
                            command=self.reset_camera, **btn)
        b_reset.pack(side='right', padx=4, pady=2)
        _vp_tip(b_reset, "Reset camera to default view")

        # Canvas keyboard bindings (added after canvas is built)
        self._vp_toolbar_built = True

    def _build_canvas(self):
        self.canvas = tk.Canvas(self, bg="#111128",
                                cursor="fleur",
                                highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._press_lmb)
        self.canvas.bind("<B1-Motion>",      self._drag_lmb)
        self.canvas.bind("<ButtonRelease-1>", self._release_lmb)
        self.canvas.bind("<ButtonPress-2>",  self._press_pan)
        self.canvas.bind("<B2-Motion>",      self._drag_pan)
        self.canvas.bind("<ButtonRelease-2>", self._release_pan)
        self.canvas.bind("<ButtonPress-3>",  self._press_pan)
        self.canvas.bind("<B3-Motion>",      self._drag_pan)
        self.canvas.bind("<ButtonRelease-3>", self._release_pan)
        self.canvas.bind("<MouseWheel>",     self._on_scroll)
        self.canvas.bind("<Button-4>",       lambda e: self._zoom_in())
        self.canvas.bind("<Button-5>",       lambda e: self._zoom_out())
        self.canvas.bind("<Configure>",      self._on_resize)
        # Keyboard shortcuts for viewport (canvas must have focus)
        self.canvas.bind("<f>",              lambda e: self.frame_all())
        self.canvas.bind("<F>",              lambda e: self.frame_all())
        self.canvas.bind("<w>",              lambda e: self._toggle_wireframe())
        self.canvas.bind("<b>",              lambda e: self._toggle_bones())
        self.canvas.bind("<t>",              lambda e: self._toggle_texture())
        self.canvas.bind("<g>",              lambda e: self._toggle_gimbal())
        self.canvas.bind("<Tab>",            lambda e: self._cycle_gimbal_mode())
        self.canvas.bind("<r>",              lambda e: self.reset_camera())
        self.canvas.bind("<Control-g>",      lambda e: self._toggle_gpu_renderer())
        self.canvas.bind("<Control-G>",      lambda e: self._toggle_gpu_renderer())
        self.canvas.bind("<plus>",           lambda e: self._zoom_in())
        self.canvas.bind("<minus>",          lambda e: self._zoom_out())
        self.canvas.bind("<equal>",          lambda e: self._zoom_in())
        self.canvas.bind("<ButtonPress-1>",  lambda e: self.canvas.focus_set(), add='+')

        self._schedule_render()

    # ── Public API ────────────────────────────────────────────────────

    def load_model(self, model: KotorModel,
                   texture_dir: str = "",
                   extra_texture_dirs: List[str] = None,
                   texture_cache: Dict[str, bytes] = None):
        self.model = model
        self._renderer.set_model(model)

        # Build search dirs list: texture_dir + extra_dirs
        search_dirs = []
        if texture_dir and os.path.isdir(texture_dir):
            search_dirs.append(texture_dir)
        if extra_texture_dirs:
            for d in extra_texture_dirs:
                if d and os.path.isdir(d) and d not in search_dirs:
                    search_dirs.append(d)
        # Only update search dirs if provided (set_search_dirs is smart about clearing)
        if search_dirs:
            self._renderer.tex_cache.set_search_dirs(search_dirs)

        if model:
            self._compute_bb(model)
            # Use render_bounds (visible nodes only) for camera framing.
            # FrameRenderer.set_model() already computed and cached render_bounds,
            # so _get_render_bounds() returns the cached result instantly.
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max)
            # Pre-warm texture cache in background thread to eliminate toggle lag
            self._prewarm_textures(model)

        self._update_uv_viewer_model()
        self._request_render()

    def set_game_library(self, library, game_tag: str = "K1"):
        """
        Wire a GameLibrary instance into the texture cache so that textures
        can be loaded from BIF/ERF archives (not just disk directories).
        Call this once after the library scan completes.
        """
        self._renderer.tex_cache.set_game_library(library, game_tag)
        log.debug(f"ViewportWidget: game library set ({game_tag})")

    def set_installation(self, installation, game_tag: str = "K1"):
        """
        Wire a KotorInstallation (fast lazy BIF/ERF reader) into the texture
        cache.  This is the preferred fast path — supersedes GameLibrary for
        texture resolution.  Call this once after KotorInstallation is created.
        """
        self._renderer.tex_cache.set_installation(installation, game_tag)
        log.info(f"ViewportWidget: KotorInstallation set ({game_tag})")

    def set_resource_manager(self, manager, game_tag: str = "K1"):
        """
        Wire the unified ResourceManager into the texture cache.
        This is the new preferred method — supersedes both set_installation()
        and set_game_library() with a single unified resource backend.
        """
        self._renderer.tex_cache.set_resource_manager(manager, game_tag)
        log.info(f"ViewportWidget: ResourceManager set ({game_tag})")

    def _prewarm_textures(self, model: KotorModel):
        """Pre-load all model textures in a background thread to eliminate
        lag when the user first toggles textured rendering.
        Uses a snapshot of texture names captured on the main thread to avoid
        racing with model structure changes on the render thread."""
        if not model:
            return
        # Snapshot texture names on the CALLING (main) thread before background thread starts.
        # This prevents a data race where the background thread walks model.mesh_nodes()
        # while the main thread may be replacing the model.
        try:
            tex_names = list({n.texture_clean for n in model.mesh_nodes()
                              if n.texture_clean and n.texture_clean.upper() not in ('NULL', '')})
        except Exception:
            return
        if not tex_names:
            return
        renderer = self._renderer
        import threading
        _viewport_ref = self  # keep a weak ref pattern via closure
        def _load():
            any_loaded = False
            for name in tex_names:
                try:
                    img = renderer.tex_cache.get(name)
                    if img is not None:
                        any_loaded = True
                except MemoryError:
                    log.warning(f"Prewarm: out of memory loading '{name}' — stopping prewarm")
                    break  # stop prewarm to avoid cascading OOM
                except Exception:
                    pass
            # After prewarm finishes, request a re-render on the main thread
            # so the newly loaded textures are displayed.  Without this the
            # first render may be flat grey because it ran before textures loaded.
            if any_loaded:
                try:
                    _viewport_ref.after(0, _viewport_ref._request_render)
                except Exception:
                    pass
        threading.Thread(target=_load, daemon=True, name="tex_prewarm").start()

    def _compute_bb(self, model: KotorModel):
        """Compute model bounding box using world-space vertex positions.

        Applies the same vertex transform rules as FrameRenderer._apply_vertex_transform:
          - Skin nodes (ANY orientation): translate by world position only — no rotation.
            The bind-pose rotation is baked into vertex positions by the NWN/KotOR exporter.
          - Non-skin (trimesh/dangly) + identity orientation → translate by wp only.
          - Non-skin + non-identity orientation → full world transform (rotate + translate).

        This rule is verified against the full K1 model set.

        Added visited-set guard to prevent infinite loop on cyclic
        or corrupt MDL data (models with nodes that reference each other as children).
        Previously `stack.extend(n.children)` without a visited check could loop
        forever on bantha/c_brith/wardroid models with shared child references.

        PERF-FIX (v4.4): Use _node_world_transform cache (fills on first call then
        returns cached result) instead of n.world_transform() which walks the full
        ancestor chain from scratch every time — O(depth) per node.  For skin-heavy
        models (c_bantha has 4 meshes × 1500 verts each) this avoids 6000 redundant
        ancestor chain traversals.
        """
        import math as _math
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        visited: set = set()
        # Temporarily seed the world-transform cache so _node_world_transform
        # can be reused by the renderer on the first render without re-walking chains.
        stack = [model.root_node]
        while stack:
            n = stack.pop()
            nid = id(n)
            if nid in visited:
                continue   # Cycle / shared-child guard
            visited.add(nid)
            stack.extend(n.children)
            if not n.vertices:
                continue
            try:
                # Use the cached world-transform (fills cache on first call)
                wp, wo, is_id = self._renderer._node_world_transform(n)
            except Exception:
                # Fallback: call world_transform() directly if renderer not ready
                wp, wo = n.world_transform()
                is_id = (abs(wo[0]) < 0.001 and abs(wo[1]) < 0.001 and abs(wo[2]) < 0.001)
            wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_identity_rot = (wo_rot < 0.001)

            for v in n.vertices:
                if n.is_skin:
                    # Skin verts: translate by world position, no rotation
                    x, y, z = v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]
                elif is_identity_rot:
                    # Trimesh with identity rotation – only translate
                    x, y, z = v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]
                else:
                    # Non-skin, non-identity rotation – rotate then translate
                    rx, ry, rz = _quat_rotate(wo, v)
                    x, y, z = rx + wp[0], ry + wp[1], rz + wp[2]

                if x < mins[0]: mins[0] = x
                if y < mins[1]: mins[1] = y
                if z < mins[2]: mins[2] = z
                if x > maxs[0]: maxs[0] = x
                if y > maxs[1]: maxs[1] = y
                if z > maxs[2]: maxs[2] = z
                has_data = True
        if has_data:
            model.bb_min = tuple(mins)
            model.bb_max = tuple(maxs)

    def set_selected_node(self, node: Optional[ModelNode]):
        self._renderer.selected_node = node
        if self._uv_viewer and self._uv_viewer.winfo_exists():
            self._uv_viewer.set_selected_node(node)
        self._request_render()

    def frame_all(self):
        if self.model:
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max)
        self._request_render()

    def reset_camera(self):
        self.camera.__init__()
        if self.model:
            rbb_min, rbb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(rbb_min, rbb_max)
        self._request_render()

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0):
        """
        Apply an AnimPose to the viewport renderer for animated display.
        The pose overrides node transforms during rendering.

        Called by AnimationsPanel._tick() on every animation frame.
        Uses fast=True so the render loop uses the 16ms interactive tick
        interval during animation playback for smooth frame delivery.
        """
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        self._request_render(fast=True)

    def clear_animation_pose(self):
        """Clear the animation pose and return to bind pose."""
        self._renderer.set_animation_pose(None)
        self._request_render()

    def toggle_wireframe(self):
        self._toggle_wireframe()

    def toggle_bones(self):
        self._toggle_bones()

    def toggle_texture(self):
        self._toggle_texture()

    def open_uv_viewer(self):
        self._open_uv_viewer()

    def _toggle_walkmesh_btn(self):
        """Toggle walkmesh overlay from toolbar button.

        If no walkmesh has been co-loaded alongside the current model, attempt
        an on-demand discovery search (game directory, Override/, modules/ archives)
        via the main window's _try_coload_walkmesh().  If that also finds nothing,
        flash the button red and show an informational log message.
        """
        if self._renderer._walkmesh_overlay is None:
            # Attempt on-demand walkmesh discovery via the main window
            parent = self.winfo_toplevel()
            _coload = getattr(parent, '_try_coload_walkmesh', None)
            if _coload is not None:
                # Build a Path for the current model (if any)
                model_path_str = getattr(parent, '_model_path', '') or ''
                if model_path_str:
                    from pathlib import Path as _Path
                    try:
                        _coload(_Path(model_path_str))
                    except Exception:
                        pass
            # Check again after the discovery attempt
            if self._renderer._walkmesh_overlay is None:
                # Still nothing — inform the user
                self._btn_wok.configure(bg="#552222")   # brief red flash
                self.after(400, lambda: self._btn_wok.configure(bg="#1e1e3a"))
                _log_fn = getattr(parent, 'log', None) or getattr(self, '_log', None)
                if _log_fn:
                    _log_fn("No walkmesh found — place a .wok/.pwk/.dwk file "
                            "alongside the MDL, or set the game directory so the "
                            "module archive can be searched automatically.", 'warn')
                return
            # Discovery succeeded — button is already set green by _do_coload_walkmesh
            return
        self._renderer.show_walkmesh = not self._renderer.show_walkmesh
        on = self._renderer.show_walkmesh
        self._btn_wok.configure(bg="#225533" if on else "#1e1e3a")
        self._request_render()

    # ── Mouse handlers ────────────────────────────────────────────────

    def _press_lmb(self, e):
        """LMB press: check AcuRig guide → gimbal → bone, else orbit."""
        self._mx, self._my = e.x, e.y
        self._press_x, self._press_y = e.x, e.y
        self._is_dragging = False
        self._gimbal_dragging = False
        self._acurig_guide_dragging = False

        # AcuRig guide drag — highest priority when guides are visible
        if getattr(self._renderer, '_acurig_guides_overlay', None):
            guide_name = self._renderer.hit_test_acurig_guide(e.x, e.y)
            if guide_name:
                self._acurig_guide_dragging = True
                self._acurig_drag_guide_name = guide_name
                self._acurig_drag_start = (e.x, e.y)
                self._renderer._acurig_selected_guide = guide_name
                self._request_render()
                return  # consumed

        # Gimbal handle hit-test has priority over everything else
        if (self._renderer.show_gimbal and self._renderer.selected_node
                and self._renderer._gimbal_handles):
            axis = self._renderer.hit_test_gimbal(e.x, e.y)
            if axis:
                self._gimbal_dragging = True
                self._gimbal_axis = axis
                self._gimbal_drag_start = (e.x, e.y)
                node = self._renderer.selected_node
                self._gimbal_node_start_pos = tuple(node.position)
                self._renderer.gimbal_active_axis = axis
                self._request_render()
                return  # consumed; don't start orbit/bone check

        # Check for bone hit at press point (for immediate visual feedback)
        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(e.x, e.y)
            if node:
                self._renderer._hovered_bone = node
                self._request_render()

    def _drag_lmb(self, e):
        """LMB drag: AcuRig guide → gimbal → orbit camera."""
        # AcuRig guide drag
        if self._acurig_guide_dragging and self._acurig_drag_guide_name:
            self._apply_acurig_guide_drag(e.x, e.y)
            self._request_render(fast=True)
            return

        # Gimbal drag takes priority
        if self._gimbal_dragging and self._renderer.selected_node:
            self._apply_gimbal_drag(e.x, e.y)
            self._request_render(fast=True)
            return

        dx_total = abs(e.x - self._press_x)
        dy_total = abs(e.y - self._press_y)
        if not self._is_dragging and (dx_total > self._drag_threshold or
                                       dy_total > self._drag_threshold):
            self._is_dragging = True
            self._renderer._hovered_bone = None
            # Cancel any pending progressive HQ render (new drag started)
            self._lq_pending_hq = False
            self._renderer._lq_tex_mode = False
        if self._is_dragging:
            dx, dy = e.x - self._mx, e.y - self._my
            self._mx, self._my = e.x, e.y
            self.camera.orbit(dx * 0.4, -dy * 0.4)
            # Only enable LOD flat-shading during drag when fast-drag mode is ON
            # FIX (v10.4): use self._fast_drag_enabled directly (always defined).
            if self._fast_drag_enabled:
                self._renderer.is_interactive = True
            # PERF-GPU-INTERACTIVE: Tell GPU renderer we are in interactive drag
            # so it can skip MSAA resolve (~59ms saved) and alpha composite (~19ms).
            _gpu_r = getattr(self, '_gpu_renderer', None)
            if _gpu_r is not None:
                _gpu_r.interactive = True
            self._request_render(fast=True)

    def _release_lmb(self, e):
        """LMB release: finish AcuRig guide / gimbal drag or check bone/node click."""
        # Finish AcuRig guide drag
        if self._acurig_guide_dragging:
            self._acurig_guide_dragging = False
            guide_name = self._acurig_drag_guide_name
            self._acurig_drag_guide_name = ''
            if self.on_acurig_guide_moved and guide_name:
                guides = getattr(self._renderer, '_acurig_guides_overlay', {})
                guide = guides.get(guide_name)
                if guide and hasattr(guide, 'position'):
                    try:
                        self.on_acurig_guide_moved(guide_name, tuple(guide.position))
                    except Exception:
                        pass
            self._request_render()
            return

        # Finish gimbal drag
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()  # re-propagate moved bone to children
            node = self._renderer.selected_node
            if node:
                # Generic node-moved callback
                if self.on_node_moved:
                    self.on_node_moved(node)
                # Rig-edit mode: forward bone move to the RetargetEngine
                if self._renderer.rig_edit_mode and self._renderer.on_bone_moved:
                    try:
                        self._renderer.on_bone_moved(node.name, node.position)
                    except Exception:
                        pass
            self._request_render()
            return

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False  # restore full quality after drag
        # PERF-GPU-INTERACTIVE: Clear GPU renderer interactive mode on release
        # so the next still frame uses full MSAA + alpha composite quality.
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = False
        # ── Progressive two-pass render after drag ────────────────────────────
        # When texture mode is active and the user was dragging, trigger a fast
        # LQ (mip1 half-res) first frame for immediate feedback, then auto-queue
        # a second full-quality render.  This makes the viewport feel responsive
        # even on high-poly models: the first frame appears in ~100ms (LQ), and
        # the full-quality frame follows ~500ms later.
        if self._renderer.show_texture and self._is_dragging:
            self._renderer._lq_tex_mode = True     # first frame: use mip1 textures
            self._lq_pending_hq = True             # after LQ frame: queue HQ
        self._request_render()  # trigger one full-quality frame (or LQ if above)
        if self._is_dragging:
            self._is_dragging = False
            return
        # Click (no drag): try bone hit-test first
        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(e.x, e.y)
            if node:
                self._renderer.selected_node = node
                if self._uv_viewer and self._uv_viewer.winfo_exists():
                    self._uv_viewer.set_selected_node(node)
                # Notify main window via callback
                if self.on_bone_selected:
                    self.on_bone_selected(node)
                self._request_render()
                return
        # No bone clicked – deselect
        self._renderer.selected_node = None
        if self.on_bone_selected:
            self.on_bone_selected(None)
        self._request_render()

    # ── AcuRig guide drag helpers ─────────────────────────────────────

    def _apply_acurig_guide_drag(self, mx: int, my: int):
        """
        Move the currently-dragged AcuRig guide by mapping mouse delta to
        world-space XY displacement (guides live in the model's bind plane).

        The drag maps screen pixels to world units using the same
        world_per_px estimate as the gimbal translate helper, projecting only
        in the camera's right/up plane (ignoring depth).
        """
        import math as _gm
        guide_name = self._acurig_drag_guide_name
        guides = getattr(self._renderer, '_acurig_guides_overlay', {})
        guide = guides.get(guide_name)
        if guide is None or not hasattr(guide, 'position'):
            return

        sx0, sy0 = self._acurig_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0

        W = self.canvas.winfo_width()  or 800
        H = self.canvas.winfo_height() or 600

        # Approximate world_per_pixel from camera distance to guide position
        pos = guide.position
        sp = self._renderer._proj(pos[0], pos[1], pos[2], W, H)
        dist = sp[2] if sp else 5.0
        dist = max(0.5, dist)
        fov_rad = _gm.radians(self.camera.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)

        right, up, _fwd, _eye = self.camera._view_matrix()

        # Δ world = screen_dx × right_dir + (-screen_dy) × up_dir
        dx_world = (dx_screen * right[0] + (-dy_screen) * up[0]) * world_per_px
        dy_world = (dx_screen * right[1] + (-dy_screen) * up[1]) * world_per_px
        dz_world = (dx_screen * right[2] + (-dy_screen) * up[2]) * world_per_px

        old_pos = list(pos)
        new_pos = [old_pos[0] + dx_world,
                   old_pos[1] + dy_world,
                   old_pos[2] + dz_world]
        guide.position = new_pos

        # Update drag start so deltas are relative each frame
        self._acurig_drag_start = (mx, my)

    # ── Gimbal helpers ────────────────────────────────────────────────

    def _apply_gimbal_drag(self, mx: int, my: int):
        """
        Move (translate) or rotate the selected node by mapping the mouse
        delta from drag-start to world-space motion along the active axis.

        Translate (gimbal_mode==1):
          - Single axis: project screen-delta onto world axis via camera matrix.
          - Plane: sum of two axis deltas.
        Rotate (gimbal_mode==2):
          - Horizontal screen delta → rotation angle around axis.
        """
        import math as _gm
        node = self._renderer.selected_node
        if not node:
            return

        sx0, sy0 = self._gimbal_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0

        W = self.canvas.winfo_width()  or 800
        H = self.canvas.winfo_height() or 600
        wp, _, _ = self._renderer._node_world_transform(node)
        proj_result = self._renderer._proj(*wp, W, H)
        cz = proj_result[2] if proj_result else 1.0
        dist = max(0.5, cz)
        fov_rad = _gm.radians(self.camera.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)

        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos

        if self._renderer.gimbal_mode == 1:   # Translate
            right, up, fwd, eye = self.camera._view_matrix()

            def _axis_delta(axis_name):
                """Screen-space projection → world delta along one axis."""
                if axis_name == 'X':
                    w_dir = (1.0, 0.0, 0.0)
                elif axis_name == 'Y':
                    w_dir = (0.0, 1.0, 0.0)
                else:
                    w_dir = (0.0, 0.0, 1.0)
                sc_x = w_dir[0]*right[0] + w_dir[1]*right[1] + w_dir[2]*right[2]
                sc_y = w_dir[0]*up[0]    + w_dir[1]*up[1]    + w_dir[2]*up[2]
                ll = _gm.sqrt(sc_x*sc_x + sc_y*sc_y)
                if ll < 1e-6:
                    return (0.0, 0.0, 0.0)
                proj = (dx_screen * sc_x + (-dy_screen) * sc_y) / ll
                delta = proj * world_per_px
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

            if len(axis) == 1:
                d = _axis_delta(axis)
                nx, ny, nz = start[0]+d[0], start[1]+d[1], start[2]+d[2]
            else:
                d1 = _axis_delta(axis[0])
                d2 = _axis_delta(axis[1])
                nx = start[0] + d1[0] + d2[0]
                ny = start[1] + d1[1] + d2[1]
                nz = start[2] + d1[2] + d2[2]
            node.position = (nx, ny, nz)

        elif self._renderer.gimbal_mode == 2:   # Rotate
            angle = dx_screen * 0.01
            qx, qy, qz, qw = node.rotation
            ha = angle * 0.5
            c, s = _gm.cos(ha), _gm.sin(ha)
            if axis == 'X':
                rq = (s, 0.0, 0.0, c)
            elif axis == 'Y':
                rq = (0.0, s, 0.0, c)
            else:
                rq = (0.0, 0.0, s, c)
            ax, ay, az, aw = rq
            bx, by, bz, bw = qx, qy, qz, qw
            new_rot = (
                aw*bx + ax*bw + ay*bz - az*by,
                aw*by - ax*bz + ay*bw + az*bx,
                aw*bz + ax*by - ay*bx + az*bw,
                aw*bw - ax*bx - ay*by - az*bz,
            )
            ll = _gm.sqrt(sum(v*v for v in new_rot))
            if ll > 1e-9:
                node.rotation = tuple(v/ll for v in new_rot)

        # Evict this node and all descendants from wt_cache so they re-evaluate
        nid = id(node)
        self._renderer._wt_cache.pop(nid, None)
        stack = list(node.children)
        _evict_visited: set = set()
        while stack:
            c = stack.pop()
            cid = id(c)
            if cid in _evict_visited:
                continue
            _evict_visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            stack.extend(c.children)

    def _toggle_gimbal(self):
        """Toggle gimbal overlay on/off."""
        self._renderer.show_gimbal = not self._renderer.show_gimbal
        self._btn_gimbal.configure(
            bg="#334422" if self._renderer.show_gimbal else "#1e1e3a")
        self._request_render()

    def _cycle_gimbal_mode(self):
        """Toggle between Translate [T] and Rotate [R] gimbal modes."""
        current = self._renderer.gimbal_mode
        self._renderer.gimbal_mode = 2 if current == 1 else 1
        mode_lbl = "Translate" if self._renderer.gimbal_mode == 1 else "Rotate"
        self._btn_gimbal_mode.configure(
            text=f"[{mode_lbl}]",
            bg="#223344" if self._renderer.gimbal_mode == 1 else "#332244")
        self._request_render()

    def set_gimbal_mode(self, mode: int):
        """Set gimbal mode externally: 1=Translate, 2=Rotate."""
        self._renderer.gimbal_mode = mode
        mode_lbl = "Translate" if mode == 1 else "Rotate"
        if hasattr(self, '_btn_gimbal_mode'):
            self._btn_gimbal_mode.configure(
                text=f"[{mode_lbl}]",
                bg="#223344" if mode == 1 else "#332244")

    # ── Rig-Edit mode public API (Phase 22) ──────────────────────────────

    def enter_rig_edit_mode(self, on_bone_moved=None):
        """
        Enter Rig Edit Mode.

        In this mode:
        • Bone joints are drawn in orange instead of gold to signal edit mode.
        • An orange banner is drawn at the top of the viewport.
        • Every time the user drags a bone joint via the gimbal, the optional
          *on_bone_moved(name, new_pos)* callback is invoked.
        • Bones are automatically shown and gimbal is enabled.

        Call exit_rig_edit_mode() or confirm_rig_edit() to leave.
        """
        self._renderer.rig_edit_mode = True
        self._renderer.on_bone_moved  = on_bone_moved
        # Ensure bones and gimbal are visible
        self._renderer.show_bones  = True
        self._renderer.show_gimbal = True
        if hasattr(self, '_btn_bones'):
            self._btn_bones.configure(bg="#cc5500")   # orange tint
        if hasattr(self, '_btn_rig_edit'):
            self._btn_rig_edit.configure(bg="#cc5500", text="✦ Rig Edit ON")
        self._request_render()

    def exit_rig_edit_mode(self):
        """
        Leave Rig Edit Mode without baking.  Bone positions stay where the
        user left them but the auto-skin weights are NOT recalculated.
        """
        self._renderer.rig_edit_mode = False
        self._renderer.on_bone_moved  = None
        if hasattr(self, '_btn_bones'):
            self._btn_bones.configure(bg="#333322")   # restore normal colour
        if hasattr(self, '_btn_rig_edit'):
            self._btn_rig_edit.configure(bg="#1e1e3a", text="✦ Rig Edit")
        self._request_render()

    def confirm_rig_edit(self, retarget_engine=None):
        """
        Confirm Rig Edit: exit rig-edit mode and (optionally) bake the
        adjusted bone positions into fresh skin weights.

        If *retarget_engine* is a RetargetEngine instance, bake_rig_edit()
        is called on the current model to re-skin all mesh nodes from the
        updated bone positions.

        Returns the number of re-skinned mesh nodes (0 if no engine given).
        """
        self.exit_rig_edit_mode()
        count = 0
        if retarget_engine is not None and self.model is not None:
            try:
                count = retarget_engine.bake_rig_edit(self.model)
            except Exception as _e:
                import logging as _log
                _log.getLogger(__name__).warning(
                    f"confirm_rig_edit bake failed: {_e}")
        # Invalidate world-transform cache so the re-skinned model renders fresh
        self._renderer._wt_cache.clear()
        self._renderer._lbs_model_diag = None
        self._request_render()
        return count

    def is_rig_edit_active(self) -> bool:
        """Return True if rig-edit mode is currently active."""
        return self._renderer.rig_edit_mode

    def load_ext_skeleton(self, model, offset=(0.0, 0.0, 0.0)):
        """
        Load an external skeleton (KotorModel) as a purple ghost overlay.
        Pass model=None to clear it.
        The overlay offset can be changed with set_ext_skeleton_offset().
        """
        self._renderer._ext_skeleton = model
        self._renderer._ext_skel_offset = list(offset)
        self._request_render()

    def set_ext_skeleton_offset(self, x: float, y: float, z: float):
        """Reposition the external skeleton overlay in world space."""
        self._renderer._ext_skel_offset = [x, y, z]
        self._renderer._wt_cache.clear()
        self._request_render()

    def _toggle_rig_edit_mode(self):
        """Toggle Rig-Edit Mode on/off from the toolbar button."""
        if self._renderer.rig_edit_mode:
            self.exit_rig_edit_mode()
        else:
            self.enter_rig_edit_mode()

    def _press_orbit(self, e):
        self._mx, self._my = e.x, e.y

    def _drag_orbit(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        self.camera.orbit(dx * 0.4, -dy * 0.4)
        self._request_render()

    def _press_pan(self, e):
        self._mx, self._my = e.x, e.y

    def _drag_pan(self, e):
        dx, dy = e.x - self._mx, e.y - self._my
        self._mx, self._my = e.x, e.y
        H = self.canvas.winfo_height() or 600
        self.camera.pan(dx, dy, H)
        # FIX (v10.4): use self._fast_drag_enabled directly (always defined in
        # __init__), eliminating the getattr(..., True) default mismatch.
        if self._fast_drag_enabled:
            self._renderer.is_interactive = True
        # PERF-GPU-INTERACTIVE: Tell GPU renderer we are in interactive drag
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = True
        self._request_render(fast=True)

    def _release_pan(self, e):
        """MMB/RMB release: restore full-quality render after pan drag."""
        self._renderer.is_interactive = False
        # PERF-GPU-INTERACTIVE: Clear GPU renderer interactive mode on release
        _gpu_r = getattr(self, '_gpu_renderer', None)
        if _gpu_r is not None:
            _gpu_r.interactive = False
        # Progressive two-pass render: LQ first, then HQ
        if self._renderer.show_texture:
            self._renderer._lq_tex_mode = True
            self._lq_pending_hq = True
        self._request_render()

    def _on_scroll(self, e):
        steps = -(e.delta / 120.0) if e.delta else -1
        self.camera.zoom(steps)
        self._renderer.is_interactive = False  # zoom = one-shot, no LOD needed
        self._request_render()

    def _zoom_in(self):
        self.camera.zoom(-1)
        self._request_render()

    def _zoom_out(self):
        self.camera.zoom(1)
        self._request_render()

    def _on_resize(self, e):
        self._request_render()

    # ── Toolbar callbacks ─────────────────────────────────────────────

    def _toggle_wireframe(self):
        self._renderer.show_wireframe = not self._renderer.show_wireframe
        self._btn_wire.configure(
            bg="#3333aa" if self._renderer.show_wireframe else "#1e1e3a")
        self._request_render()

    def _toggle_bones(self):
        self._renderer.show_bones = not self._renderer.show_bones
        self._btn_bones.configure(
            bg="#333322" if self._renderer.show_bones else "#1e1e3a")
        self._request_render()

    def _toggle_texture(self):
        self._renderer.show_texture = not self._renderer.show_texture
        active = self._renderer.show_texture
        self._btn_tex.configure(
            bg="#224422" if active else "#1e1e3a")
        # When enabling Texture mode, ensure the solid fill pass
        # is active.  If the user had selected the 'Wireframe' shade radio
        # (show_solid=False, show_wireframe=True), texture mode is meaningless
        # because no polygon fill is ever drawn.  Switch to 'Both' (solid +
        # wireframe) so textured faces become visible immediately.
        if active and not self._renderer.show_solid:
            self._renderer.show_solid = True
            # Keep wireframe on if it was already on; update radio button
            new_mode = "Both" if self._renderer.show_wireframe else "Solid"
            self._shade_var.set(new_mode)
        self._request_render()

    def _toggle_fast_drag(self):
        """Toggle whether mouse drag falls back to flat-shading for speed.

        Fast drag ON  : during orbit/pan the renderer drops to flat-shading so
                        the viewport stays responsive on high-poly models.
                        Textures temporarily disappear during drag, reappear on
                        release.  Useful for very high-poly models.
        Fast drag OFF (default): textured quality is kept throughout the drag.
                        No texture pop.  Slightly slower on large models.
        """
        self._fast_drag_enabled = not self._fast_drag_enabled
        self._btn_fast_drag.configure(
            bg="#332211" if self._fast_drag_enabled else "#1e1e3a")
        status = "ON" if self._fast_drag_enabled else "OFF"
        # Update renderer flag immediately
        if not self._fast_drag_enabled:
            # Turning off fast drag: force full quality even if currently dragging
            self._renderer.is_interactive = False
        self._request_render()

    def _open_uv_viewer(self):
        if self._uv_viewer is not None:
            try:
                if self._uv_viewer.winfo_exists():
                    self._uv_viewer.deiconify()
                    self._uv_viewer.lift()
                    self._uv_viewer.focus_force()
                    return
            except tk.TclError:
                pass

        parent = self.winfo_toplevel()
        self._uv_viewer = UVViewerWindow(parent)
        self._uv_viewer.protocol("WM_DELETE_WINDOW", self._on_uv_viewer_close)
        # Pass texture cache so the UV viewer can show texture overlays
        self._uv_viewer._tex_cache = self.tex_cache
        self._update_uv_viewer_model()
        if self._renderer.selected_node:
            self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self._btn_uv.configure(bg="#334433")

    def _on_uv_viewer_close(self):
        if self._uv_viewer:
            self._uv_viewer.destroy()
            self._uv_viewer = None
        self._btn_uv.configure(bg="#1e1e3a")

    def _update_uv_viewer_model(self):
        if self._uv_viewer:
            try:
                if self._uv_viewer.winfo_exists():
                    self._uv_viewer.set_model(self.model)
            except tk.TclError:
                self._uv_viewer = None

    def _on_shade_change(self):
        mode = self._shade_var.get()
        self._renderer.show_solid     = mode in ("Solid", "Both")
        self._renderer.show_wireframe = mode in ("Wireframe", "Both")
        # If Texture mode is ON and user switches to Wireframe-only,
        # auto-upgrade to 'Both' so textured faces remain visible.
        # Pure wireframe with texture mode active is always user-error;
        # they almost certainly want Both (solid fill + wire overlay).
        if (self._renderer.show_texture and not self._renderer.show_solid
                and self._renderer.show_wireframe):
            self._renderer.show_solid = True
            self._shade_var.set("Both")
        self._request_render()

    # ── Render loop ───────────────────────────────────────────────────

    def _request_render(self, fast: bool = False):
        """Mark a render as needed.  fast=True uses the interactive tick interval."""
        self._render_pending = True
        if fast:
            self._render_fast = True

    def _schedule_render(self):
        if not self.winfo_exists():
            return   # window closed – stop the render loop

        # ── Drain render-result queue (main-thread safe) ──────────────────────
        # The render thread posts (img, render_ms, W, H) here instead of calling
        # self.after() directly; we drain and apply it now on the main thread.
        try:
            while True:
                img, render_ms, W, H = self._render_result_queue.get_nowait()
                self._last_render_ms = render_ms
                self._render_frame_count += 1
                # FPS rolling window — wall-clock based (v10.4 fix)
                # Using actual wall-clock delta prevents FPS over-counting when
                # the render thread is fast but Tkinter drains the queue slowly.
                _now_wall = _time_mod.perf_counter()
                self._fps_accum  += _now_wall - self._fps_last_wall
                self._fps_last_wall = _now_wall
                self._fps_frames += 1
                if self._fps_accum >= 0.5:
                    self._fps_display = self._fps_frames / self._fps_accum
                    self._fps_accum  = 0.0
                    self._fps_frames = 0
                if img is not None:
                    try:
                        # Kill any residual alpha layer before display.
                        # ImageTk.PhotoImage with RGBA mode shows transparent pixels
                        # as see-through on the Tkinter canvas; flatten to RGB first.
                        if getattr(img, 'mode', 'RGB') == 'RGBA':
                            _bg_flat = Image.new('RGB', img.size, _BG[:3])
                            _bg_flat.paste(img, mask=img.split()[3])
                            img = _bg_flat
                        photo = ImageTk.PhotoImage(img)
                        self._photo = photo   # keep reference – must be kept alive
                        self.canvas.delete("all")
                        self.canvas.create_image(0, 0, anchor='nw', image=photo)
                        # ── HUD overlay ──────────────────────────────────────
                        # Top-right: FPS + render time
                        fps_txt = f"{self._fps_display:.0f} fps  {render_ms:.0f}ms"
                        self.canvas.create_text(
                            W - 4, 4, text=fps_txt,
                            anchor='ne', fill="#445566", font=("Consolas", 7))
                        # Bottom-left: model name + triangle hint (when model loaded)
                        _mdl = getattr(self, 'model', None)
                        if _mdl:
                            _nm = getattr(_mdl, 'name', '') or ''
                            _gv = getattr(_mdl, 'game_version', None)
                            _gv_str = ''
                            try:
                                from src.core.model_data import GameVersion as _GVH
                                _gv_str = 'K1' if _gv == _GVH.K1 else 'K2'
                            except Exception:
                                pass
                            _n_mesh = len(_mdl.mesh_nodes()) if hasattr(_mdl, 'mesh_nodes') else 0
                            _hud_line = f"[{_gv_str}] {_nm}  ·  {_n_mesh} mesh"
                            self.canvas.create_text(
                                6, H - 6, text=_hud_line,
                                anchor='sw', fill="#445566", font=("Consolas", 7))
                            # Shade mode badge (top-left)
                            _shade = self._shade_var.get() if hasattr(self, '_shade_var') else ''
                            if _shade and _shade != 'Solid':
                                self.canvas.create_text(
                                    6, 4, text=_shade.upper(),
                                    anchor='nw', fill="#886644", font=("Consolas", 7))
                    except Exception as _e:
                        log.debug(f"Viewport canvas update error: {_e}")
                # ── Progressive two-pass: after LQ frame, queue HQ frame ──────
                # If _lq_pending_hq is set, this render was the fast mip1 frame.
                # Now clear _lq_tex_mode and queue a full-quality follow-up render.
                if getattr(self, '_lq_pending_hq', False):
                    self._lq_pending_hq = False
                    self._renderer._lq_tex_mode = False   # full-res for HQ frame
                    self._render_pending = True           # queue the HQ render
        except Exception:
            pass   # queue.Empty → nothing to drain

        # Watchdog: if render thread has been running > 8 s it is stuck/crashed;
        # reset the flag so new renders can proceed.
        # Increased from 3→8 s: complex models with LBS can legitimately take 4-6 s
        # on the first frame when bone transforms are computed for all vertices.
        # FIX (v10.4): use module-level _time_mod (imported at top) instead of
        # a local `import time` on every single schedule tick (saves ~1 µs/tick).
        if self._render_in_progress:
            elapsed = _time_mod.perf_counter() - self._render_started_at
            if elapsed > 8.0:
                log.warning(f"Viewport render watchdog: {elapsed:.1f}s — resetting stuck render")
                self._render_in_progress = False
        fast = getattr(self, '_render_fast', False)
        if self._render_pending and not self._render_in_progress:
            self._render_pending = False
            self._render_fast    = False
            self._do_render()
        # Use faster tick during interactive drag for smoother orbit/pan feel
        next_ms = self._RENDER_MS_INTERACTIVE if fast else self._RENDER_MS
        self.after(next_ms, self._schedule_render)

    def _toggle_gpu_renderer(self):
        """Toggle between CPU PIL rasterizer and GPU ModernGL renderer.

        v6.0 Deliverable 3 (T308): runtime CPU ↔ GPU switch.
        GPU renderer provides proper z-buffer depth testing (no painter's
        algorithm), back-face culling, and 60fps for ≤100k triangles.
        CPU fallback is always available for systems without GPU/EGL.
        """
        self._use_gpu = not self._use_gpu
        if self._use_gpu:
            # Lazy-init GPU renderer
            if self._gpu_renderer is None:
                try:
                    try:
                        from src.gui.gpu_renderer import GpuRenderer
                    except ImportError:
                        from gui.gpu_renderer import GpuRenderer  # type: ignore
                    self._gpu_renderer = GpuRenderer()
                except Exception as exc:
                    log.warning(f"GPU renderer not available — staying on CPU: {exc}")
                    self._use_gpu = False
            self._btn_gpu.configure(text="GPU", bg="#224422")  # green = active
        else:
            self._btn_gpu.configure(text="CPU", bg="#1a1a3a")  # dark = inactive
        # Force a re-render with the new renderer
        self._request_render(fast=True)

    def _do_render(self):
        """Kick off rendering in a background thread so Tkinter stays responsive."""
        if not _PIL:
            return
        W = self.canvas.winfo_width()
        H = self.canvas.winfo_height()
        if W < 4 or H < 4:
            return

        self._render_in_progress = True
        self._render_started_at  = _time_mod.perf_counter()
        renderer  = self._renderer
        canvas    = self.canvas

        # v6.0: GPU rendering path — uses GpuRenderer instead of CPU FrameRenderer
        _use_gpu_local = getattr(self, '_use_gpu', False)
        _gpu_r = getattr(self, '_gpu_renderer', None) if _use_gpu_local else None

        def _render_thread():
            t0 = _time_mod.perf_counter()
            img = None
            try:
                if _gpu_r is not None and self.model is not None:
                    # GPU path: use GpuRenderer.render() for z-buffered rendering
                    # Build {name: PIL.Image} dict from TextureCache for GpuRenderer.
                    # TextureCache stores loaded PIL images in ._cache (dict);
                    # GpuRenderer.render() expects textures={str: PIL.Image}.
                    #
                    # FIX-GPU-TEXPRELOAD: Ensure all model textures are loaded
                    # before passing to the GPU renderer.  TextureCache lazily
                    # loads textures on first .get() call; when switching to GPU
                    # mode without a prior CPU render, _cache is empty and the
                    # GPU renderer gets no textures (white/untextured geometry).
                    # Walk all mesh nodes and trigger a .get() for each texture
                    # name so the cache is populated before we read _cache.items().
                    _tc = getattr(renderer, 'tex_cache', None)
                    # PERF-TEXPRELOAD: Only walk all nodes for texture preloading
                    # once per model.  Track the model id; if unchanged, skip the
                    # expensive node walk + _tc.get() calls entirely.
                    # This saves ~2-5ms/frame on 56-mesh-node module models.
                    _cur_model_id_vp = id(self.model)
                    _last_preload_id = getattr(self, '_gpu_tex_preload_model_id', 0)
                    if _tc is not None and _cur_model_id_vp != _last_preload_id:
                        try:
                            _all_fn = getattr(self.model, 'all_nodes', None)
                            _mnodes = list(_all_fn()) if _all_fn else []
                            for _mn in _mnodes:
                                if not getattr(_mn, 'is_mesh', False):
                                    continue
                                _mtex = str(getattr(_mn, 'texture', '') or '').strip()
                                if _mtex and _mtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_mtex)  # triggers lazy load
                                _lmtex = str(getattr(_mn, 'lightmap', '') or '').strip()
                                if _lmtex and _lmtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_lmtex)
                                _envtex = str(getattr(_mn, 'txi_envmaptexture', '') or '').strip()
                                if _envtex and _envtex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_envtex)
                                for _tn in getattr(_mn, 'texture_names', []):
                                    _tn_clean = str(_tn or '').strip()
                                    if (_tn_clean
                                            and _tn_clean.upper() not in ('NULL', '', 'NONE')
                                            and _tn_clean != _mtex
                                            and _tn_clean != _lmtex):
                                        _tc.get(_tn_clean)
                                _spectex = str(getattr(_mn, 'txi_specularcolour', '') or '').strip()
                                if _spectex and _spectex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_spectex)
                                _bumptex = str(getattr(_mn, 'txi_bumpmaptexture', '') or '').strip()
                                if _bumptex and _bumptex.upper() not in ('NULL', '', 'NONE'):
                                    _tc.get(_bumptex)
                            self._gpu_tex_preload_model_id = _cur_model_id_vp
                        except Exception:
                            pass
                    if _tc is not None and hasattr(_tc, '_cache'):
                        _tex_dict = {k: v for k, v in _tc._cache.items()
                                     if v is not None}
                    else:
                        _tex_dict = {}
                    # FIX-GPU-ANIM: Pass animation pose and time to GPU renderer.
                    # Previously these were omitted, causing:
                    #   1. Animations not playing in GPU mode (anim_pose=None)
                    #   2. UV scroll/flipbook animations frozen (anim_time=0.0)
                    #   3. Material animations (alpha, selfillum) not applied
                    # The FrameRenderer stores the current animation state in
                    # _anim_pose (AnimPose object) and _anim_time (float seconds).
                    _gpu_anim_pose = getattr(renderer, '_anim_pose', None)
                    _gpu_anim_time = float(getattr(renderer, '_anim_time', 0.0))
                    # FIX-SKIN-ANIM-D3: Pass the animation's first-frame (t=0)
                    # pose as the bind reference for GPU skinning.
                    _gpu_base_pose = getattr(renderer, '_anim_base_pose', None)
                    img = _gpu_r.render(self.model, self.camera, W, H,
                                        textures=_tex_dict,
                                        anim_pose=_gpu_anim_pose,
                                        anim_time=_gpu_anim_time,
                                        anim_base_pose=_gpu_base_pose)
                else:
                    img = renderer.render(W, H)
            except MemoryError:
                log.warning("Viewport render: MemoryError — reducing triangle cap")
                # Auto-reduce tri cap to avoid repeat crash
                try:
                    renderer.MAX_TRIS = max(5000, renderer.MAX_TRIS // 2)
                    renderer.MAX_TRIS_TEXTURED = max(5000, renderer.MAX_TRIS_TEXTURED // 2)
                    log.warning(f"Tri cap reduced to {renderer.MAX_TRIS}")
                except Exception:
                    pass
            except Exception as exc:
                log.warning(f"Viewport render error: {exc}", exc_info=True)
            render_ms = (_time_mod.perf_counter() - t0) * 1000.0
            # ── Thread-safe result posting ────────────────────────────────────
            # Instead of calling self.after() from this background thread (which
            # raises RuntimeError on Linux when the main event loop hasn't started
            # or is not currently executing), we push (img, render_ms) into a
            # thread-safe queue.  _schedule_render() drains the queue on the main
            # thread every tick (33 ms) and applies the result to the canvas.
            try:
                # Non-blocking put: if the queue is full (2 items), discard the
                # oldest result – the most recent render is always the freshest.
                if self._render_result_queue.full():
                    try:
                        self._render_result_queue.get_nowait()
                    except Exception:
                        pass
                self._render_result_queue.put_nowait((img, render_ms, W, H))
            except Exception:
                pass
            finally:
                # Always clear the in-progress flag so future renders can start.
                # This is safe here because _render_in_progress is only written
                # by the main thread (set True before thread launch) and by THIS
                # thread (set False when done).  The queue pattern means the
                # flag is cleared here, not in _apply, which is correct.
                self._render_in_progress = False

        threading.Thread(target=_render_thread, daemon=True,
                         name="viewport_render").start()
