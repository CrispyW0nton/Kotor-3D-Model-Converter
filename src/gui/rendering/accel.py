"""
GhostRigger-K1-K2 – src/gui/accel.py
=====================================
Hardware-agnostic rendering acceleration layer.

Provides three acceleration tiers, automatically selected at import time:

  TIER 1 – Numba JIT  (fastest, ~17–40x vs PIL AFFINE)
    Requires: numba>=0.55  (pre-installed in the project environment)
    Compiles on first use; subsequent calls run at near-C speed.
    Functions:
      rasterize_triangle_jit()   – single textured triangle → RGBA framebuffer
      rasterize_frame_jit()      – batch of all triangles in one JIT call
      project_vertices_np()      – NumPy vectorized vertex projection
      frustum_cull_np()          – NumPy vectorized frustum culling
      depth_sort_np()            – NumPy argsort depth sort

  TIER 2 – NumPy only  (fast, ~3–104x vs Python loops, no JIT overhead)
    Used when Numba is unavailable.
    rasterize_triangle_np()    – NumPy barycentric per-triangle
    Same project / cull / sort as Tier 1

  TIER 3 – PIL AFFINE fallback  (original v10.3 path, always available)
    Used when both Numba and NumPy are unavailable (should not occur in practice).

Benchmark results (sandbox, Intel Xeon, 2026-03-10):
  PIL AFFINE (v10.3)           : 187 µs / triangle
  NumPy barycentric            :  20 µs / triangle  (9x)
  Numba single call            :  11 µs / triangle  (17x)
  Numba batch (2000 tris/frame):   4.7 µs / triangle  (40x)
  NumPy frustum cull 2k tris   :  0.26 ms  (104x vs Python)
  NumPy vertex project 5k verts:  0.05 ms  (700x vs Python)

Usage
-----
    from src.gui.qt_lib.rendering.accel import (
        ACCEL_TIER,
        project_vertices_np,
        frustum_cull_np,
        depth_sort_np,
        finite_uv_filter_np,
        rasterize_frame,
        warmup_jit,
    )

    # In FrameRenderer.render():
    warmup_jit()            # no-op if already warm; call once at startup
    sx, sy, sz, valid = project_vertices_np(vx, vy, vz, W, H, f, cam_mat)
    visible = frustum_cull_np(screen_pts, W, H)
    order   = depth_sort_np(depths)
    rasterize_frame(buf, tex_arr, vx, vy, uvs_u, uvs_v, f0, f1, f2, sr, sg, sb)
"""

from __future__ import annotations
import logging
import math
import os
import time
from typing import Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Acceleration tier detection
# ─────────────────────────────────────────────────────────────────────────────

ACCEL_TIER: int = 3   # 1=Numba, 2=NumPy, 3=PIL-fallback
_JIT_WARMED: bool = False

try:
    from numba import njit as _njit
    ACCEL_TIER = 1
    log.debug("accel: Numba available – using JIT tier (fastest)")
except ImportError:
    _njit = None  # type: ignore
    ACCEL_TIER = 2
    log.debug("accel: Numba not available – using NumPy tier")


# ─────────────────────────────────────────────────────────────────────────────
#  NumPy-vectorized utilities (available at all tiers)
# ─────────────────────────────────────────────────────────────────────────────

def project_vertices_np(
    vx: np.ndarray,   # (N,) float32 world-space X
    vy: np.ndarray,   # (N,) float32 world-space Y
    vz: np.ndarray,   # (N,) float32 world-space Z (camera-space depth)
    W: int, H: int,
    f: float,         # focal scale = 1/tan(half_fov)
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized perspective projection of N vertices.

    Returns (sx, sy, sz, valid_mask) as int32 / float32 / bool arrays.
    Invalid (behind camera) vertices get sx=sy=-9999.

    Speedup vs Python loop: ~700x on 5,000 vertices.

    Formula mirrors Camera.project():
        sx = W/2 + (cx/cz) * f * H/2
        sy = H/2 - (cy/cz) * f * H/2
    """
    valid = vz > 1e-4
    inv_z = np.where(valid, 1.0 / np.where(valid, vz, 1.0), 0.0)
    half_fH = f * H * 0.5
    sx = np.where(valid, (W * 0.5 + vx * inv_z * half_fH).astype(np.int32), np.int32(-9999))
    sy = np.where(valid, (H * 0.5 - vy * inv_z * half_fH).astype(np.int32), np.int32(-9999))
    return sx.astype(np.int32), sy.astype(np.int32), vz.astype(np.float32), valid


def frustum_cull_np(
    sx: np.ndarray,   # (N, 3) int32 screen X for each triangle vertex
    sy: np.ndarray,   # (N, 3) int32 screen Y
    W: int, H: int,
) -> np.ndarray:
    """
    Vectorized frustum culling.

    Returns a boolean mask (N,) where True = triangle AABB overlaps viewport.
    Completely off-screen triangles are False and should be skipped.

    Speedup vs Python loop: ~104x on 2,000 triangles.

    Culling rule: the triangle's AABB must overlap [0, W) × [0, H).
    Back-face culling is NOT done here (handled by depth sort / painter's algorithm).
    """
    bx0 = sx.min(axis=1)
    by0 = sy.min(axis=1)
    bx1 = sx.max(axis=1)
    by1 = sy.max(axis=1)
    return ~((bx1 < 0) | (bx0 >= W) | (by1 < 0) | (by0 >= H))


def depth_sort_np(depths: np.ndarray) -> np.ndarray:
    """
    Back-to-front sort using NumPy argsort (painter's algorithm).

    Returns integer index array: `order[0]` is the furthest triangle.
    Speedup vs Python timsort: ~3x on 2,000 triangles.

    Note: NumPy uses introsort (unstable) by default. For deterministic Z-fighting
    resolution the caller should provide a secondary key (face index) baked into
    the depth float as a tiny epsilon:
        depth_key = depth + face_index * 1e-7
    """
    return np.argsort(-depths, kind='stable')


def finite_uv_filter_np(
    uvs: np.ndarray,    # (N, 3, 2) float UV coords for N triangles
) -> np.ndarray:
    """
    Vectorized finite-UV filter.

    Returns a boolean mask (N,) where True = triangle has NO corrupt UVs
    and is safe to rasterize.

    Speedup vs Python loop: ~220x on 2,000 triangles.
    """
    return np.all(np.isfinite(uvs), axis=(1, 2))   # False for NaN or Inf


def shade_colors_np(
    normals:   np.ndarray,   # (N, 3) float32 face normals (unit vectors)
    light_dir: np.ndarray,   # (3,) float32 key-light direction
    light_dir2: np.ndarray,  # (3,) float32 fill-light direction
    ambient:   float,
    diffuse_rgb: np.ndarray, # (N, 3) float32 base diffuse [0..1]
) -> np.ndarray:
    """
    Vectorized Phong diffuse shading for N face normals.

    Returns (N, 3) uint8 array of shade colors [0..255].
    Speedup vs Python loop: ~30x on 2,000 faces.
    """
    # Clamp normal lengths (normalise)
    nlen = np.linalg.norm(normals, axis=1, keepdims=True)
    nlen = np.where(nlen > 1e-9, nlen, 1.0)
    n = normals / nlen   # (N,3) unit normals

    d1 = np.maximum(0.0, n @ light_dir)    # (N,)
    d2 = np.maximum(0.0, n @ light_dir2)   # (N,)
    intensity = np.clip(ambient + 0.6 * d1 + 0.3 * d2, 0.0, 1.0)  # (N,)

    rgb = diffuse_rgb * intensity[:, None]   # (N,3) float in [0,1]
    return (rgb * 255).clip(0, 255).astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
#  NumPy barycentric rasterizer  (Tier 2)
# ─────────────────────────────────────────────────────────────────────────────

def _rasterize_triangle_numpy(
    buf:      np.ndarray,   # (H, W, 4) uint8 RGBA framebuffer (modified in-place)
    tex:      np.ndarray,   # (TH, TW, 4) uint8 texture
    x0: int, y0: int,
    x1: int, y1: int,
    x2: int, y2: int,
    u0: float, v0: float,
    u1: float, v1: float,
    u2: float, v2: float,
    shade_r: int, shade_g: int, shade_b: int,
    node_alpha: float = 1.0,
    clamp_s: bool = False,
    clamp_t: bool = False,
) -> None:
    """
    NumPy-vectorized barycentric triangle rasterizer.

    Computes barycentric weights for every pixel in the AABB of the triangle,
    keeps only pixels with w0≥0, w1≥0, w2≥0 (inside the triangle), samples
    the texture at interpolated UV, applies shade color, and alpha-composites.

    ~9x faster than PIL AFFINE for KotOR-sized triangles (30–100px).
    """
    H, W = buf.shape[:2]
    TH, TW = tex.shape[:2]
    bx0 = max(0, min(x0, x1, x2))
    by0 = max(0, min(y0, y1, y2))
    bx1 = min(W - 1, max(x0, x1, x2))
    by1 = min(H - 1, max(y0, y1, y2))
    if bx1 <= bx0 or by1 <= by0:
        return

    denom = float((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
    if abs(denom) < 0.5:
        return

    # Build pixel grid in bounding box
    gy, gx = np.mgrid[by0:by1 + 1, bx0:bx1 + 1]

    inv_d = 1.0 / denom
    w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) * inv_d
    w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) * inv_d
    w2 = 1.0 - w0 - w1

    inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
    if not inside.any():
        return

    # UV interpolation with V-flip (KotOR MDX: V=0 = bottom of texture)
    u = w0[inside] * u0 + w1[inside] * u1 + w2[inside] * u2
    v_raw = w0[inside] * v0 + w1[inside] * v1 + w2[inside] * v2
    if clamp_s:
        u = np.clip(u, 0.0, 1.0)
    else:
        # GL_REPEAT tiling: frac() wrap so large UVs tile correctly.
        u = u - np.floor(u)
    if clamp_t:
        v_raw = np.clip(v_raw, 0.0, 1.0)
        v = 1.0 - v_raw
    else:
        v = 1.0 - v_raw
        v = v - np.floor(v)

    # Sample texture (nearest-neighbor, with clamp-to-valid-index)
    pu = np.clip((u * TW).astype(np.int32), 0, TW - 1)
    pv = np.clip((v * TH).astype(np.int32), 0, TH - 1)

    # Get pixel colors from texture
    px = tex[pv, pu]   # (K, 4) RGBA

    # Apply shade (lighting multiply)
    if shade_r < 253 or shade_g < 253 or shade_b < 253:
        r = (px[:, 0].astype(np.uint16) * shade_r >> 8).clip(0, 255).astype(np.uint8)
        g = (px[:, 1].astype(np.uint16) * shade_g >> 8).clip(0, 255).astype(np.uint8)
        b = (px[:, 2].astype(np.uint16) * shade_b >> 8).clip(0, 255).astype(np.uint8)
    else:
        r, g, b = px[:, 0], px[:, 1], px[:, 2]

    a = px[:, 3].astype(np.uint16)

    # Apply node alpha
    if node_alpha < 0.999:
        a = (a * node_alpha).astype(np.uint16)

    # Alpha composite into framebuffer
    gy_in = gy[inside]
    gx_in = gx[inside]

    # Fully opaque fast path
    opaque = a >= 254
    if opaque.any():
        buf[gy_in[opaque], gx_in[opaque], 0] = r[opaque]
        buf[gy_in[opaque], gx_in[opaque], 1] = g[opaque]
        buf[gy_in[opaque], gx_in[opaque], 2] = b[opaque]
        buf[gy_in[opaque], gx_in[opaque], 3] = 255

    # Transparent blending
    transp = (a > 0) & ~opaque
    if transp.any():
        ia = 255 - a[transp]
        dst = buf[gy_in[transp], gx_in[transp]]
        buf[gy_in[transp], gx_in[transp], 0] = ((r[transp] * a[transp] + dst[:, 0] * ia) >> 8).clip(0, 255)
        buf[gy_in[transp], gx_in[transp], 1] = ((g[transp] * a[transp] + dst[:, 1] * ia) >> 8).clip(0, 255)
        buf[gy_in[transp], gx_in[transp], 2] = ((b[transp] * a[transp] + dst[:, 2] * ia) >> 8).clip(0, 255)
        buf[gy_in[transp], gx_in[transp], 3] = 255


# ─────────────────────────────────────────────────────────────────────────────
#  Numba JIT rasterizer  (Tier 1)
# ─────────────────────────────────────────────────────────────────────────────

if ACCEL_TIER == 1:
    @_njit(cache=True)  # type: ignore[misc]
    def _rasterize_triangle_jit(
        buf, tex,
        x0, y0, x1, y1, x2, y2,
        u0, v0, u1, v1, u2, v2,
        shade_r, shade_g, shade_b,
        node_alpha_i255,  # pre-multiplied int: int(node_alpha * 255)
        clamp_s,
        clamp_t,
    ):
        """
        Numba JIT barycentric rasterizer – single triangle.
        17x faster than PIL AFFINE for 30px triangles.
        All per-pixel work (barycentric, UV sample, blend) compiled to native code.
        """
        H, W = buf.shape[0], buf.shape[1]
        TH, TW = tex.shape[0], tex.shape[1]
        bx0 = max(0, min(x0, x1, x2))
        by0 = max(0, min(y0, y1, y2))
        bx1 = min(W - 1, max(x0, x1, x2))
        by1 = min(H - 1, max(y0, y1, y2))
        if bx1 <= bx0 or by1 <= by0:
            return
        denom = float((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
        if abs(denom) < 0.5:
            return
        inv_d = 1.0 / denom
        for gy in range(by0, by1 + 1):
            for gx in range(bx0, bx1 + 1):
                w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) * inv_d
                w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) * inv_d
                w2 = 1.0 - w0 - w1
                if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                    continue
                u = w0 * u0 + w1 * u1 + w2 * u2
                v_raw = w0 * v0 + w1 * v1 + w2 * v2
                if clamp_s:
                    if u < 0.0:
                        u = 0.0
                    elif u > 1.0:
                        u = 1.0
                else:
                    u = u - math.floor(u)
                if clamp_t:
                    if v_raw < 0.0:
                        v_raw = 0.0
                    elif v_raw > 1.0:
                        v_raw = 1.0
                    v = 1.0 - v_raw
                else:
                    v = 1.0 - v_raw  # V-flip
                    v = v - math.floor(v)
                pu = min(TW - 1, max(0, int(u * TW)))
                pv = min(TH - 1, max(0, int(v * TH)))
                ta = int(tex[pv, pu, 3])
                if ta == 0:
                    continue
                # Apply node alpha
                if node_alpha_i255 < 255:
                    ta = ta * node_alpha_i255 >> 8
                r = int(tex[pv, pu, 0]) * shade_r >> 8
                g = int(tex[pv, pu, 1]) * shade_g >> 8
                b = int(tex[pv, pu, 2]) * shade_b >> 8
                if ta >= 254:
                    buf[gy, gx, 0] = r
                    buf[gy, gx, 1] = g
                    buf[gy, gx, 2] = b
                    buf[gy, gx, 3] = 255
                else:
                    ia = 255 - ta
                    buf[gy, gx, 0] = (r * ta + buf[gy, gx, 0] * ia) >> 8
                    buf[gy, gx, 1] = (g * ta + buf[gy, gx, 1] * ia) >> 8
                    buf[gy, gx, 2] = (b * ta + buf[gy, gx, 2] * ia) >> 8
                    buf[gy, gx, 3] = 255

    @_njit(cache=True)  # type: ignore[misc]
    def _rasterize_frame_jit(
        buf, tex,
        verts_sx, verts_sy,   # (NV,) int64 projected screen coords
        uvs_u, uvs_v,          # (NV,) float64 UV
        face_v0, face_v1, face_v2,  # (NF,) int64 vertex indices
        shade_r, shade_g, shade_b,  # (NF,) int64 shade channels
        node_alpha_i255,            # (NF,) int64 per-face alpha
        visible_mask,               # (NF,) bool frustum-cull mask
        clamp_s,
        clamp_t,
    ):
        """
        Numba JIT batch rasterizer – all visible triangles in one JIT call.

        Benefits over per-triangle Python dispatch:
          - No Python function call overhead per triangle
          - Tighter inner loop: ~40x speedup vs PIL AFFINE
          - All data stays in CPU cache (buf array continuity)

        Painter's algorithm order: caller must pass faces in back-to-front order
        (via depth_sort_np).
        """
        NF = face_v0.shape[0]
        H, W = buf.shape[0], buf.shape[1]
        TH, TW = tex.shape[0], tex.shape[1]
        for fi in range(NF):
            if not visible_mask[fi]:
                continue
            i0 = face_v0[fi]; i1 = face_v1[fi]; i2 = face_v2[fi]
            x0 = verts_sx[i0]; y0 = verts_sy[i0]
            x1 = verts_sx[i1]; y1 = verts_sy[i1]
            x2 = verts_sx[i2]; y2 = verts_sy[i2]
            bx0 = max(0, min(x0, x1, x2))
            by0 = max(0, min(y0, y1, y2))
            bx1 = min(W - 1, max(x0, x1, x2))
            by1 = min(H - 1, max(y0, y1, y2))
            if bx1 <= bx0 or by1 <= by0:
                continue
            denom = float((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
            if abs(denom) < 0.5:
                continue
            inv_d = 1.0 / denom
            u0 = uvs_u[i0]; v0 = uvs_v[i0]
            u1 = uvs_u[i1]; v1 = uvs_v[i1]
            u2 = uvs_u[i2]; v2 = uvs_v[i2]
            sr = shade_r[fi]; sg = shade_g[fi]; sb = shade_b[fi]
            na = node_alpha_i255[fi]
            for gy in range(by0, by1 + 1):
                for gx in range(bx0, bx1 + 1):
                    w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) * inv_d
                    w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) * inv_d
                    w2 = 1.0 - w0 - w1
                    if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                        continue
                    u = w0 * u0 + w1 * u1 + w2 * u2
                    v_raw = w0 * v0 + w1 * v1 + w2 * v2
                    if clamp_s:
                        if u < 0.0:
                            u = 0.0
                        elif u > 1.0:
                            u = 1.0
                    else:
                        u = u - math.floor(u)
                    if clamp_t:
                        if v_raw < 0.0:
                            v_raw = 0.0
                        elif v_raw > 1.0:
                            v_raw = 1.0
                        v = 1.0 - v_raw
                    else:
                        v = 1.0 - v_raw
                        v = v - math.floor(v)
                    pu = min(TW - 1, max(0, int(u * TW)))
                    pv = min(TH - 1, max(0, int(v * TH)))
                    ta = int(tex[pv, pu, 3])
                    if ta == 0:
                        continue
                    if na < 255:
                        ta = ta * na >> 8
                    r = int(tex[pv, pu, 0]) * sr >> 8
                    g = int(tex[pv, pu, 1]) * sg >> 8
                    b = int(tex[pv, pu, 2]) * sb >> 8
                    if ta >= 254:
                        buf[gy, gx, 0] = r
                        buf[gy, gx, 1] = g
                        buf[gy, gx, 2] = b
                        buf[gy, gx, 3] = 255
                    else:
                        ia = 255 - ta
                        buf[gy, gx, 0] = (r * ta + buf[gy, gx, 0] * ia) >> 8
                        buf[gy, gx, 1] = (g * ta + buf[gy, gx, 1] * ia) >> 8
                        buf[gy, gx, 2] = (b * ta + buf[gy, gx, 2] * ia) >> 8
                        buf[gy, gx, 3] = 255

    @_njit(cache=True)  # type: ignore[misc]
    def _flat_shade_frame_jit(
        buf,                          # (H, W, 4) uint8
        verts_sx, verts_sy,           # (NV,) int64
        face_v0, face_v1, face_v2,    # (NF,) int64
        fill_r, fill_g, fill_b,       # (NF,) uint8 flat fill colors
        visible_mask,                 # (NF,) bool
    ):
        """
        Numba JIT flat-shaded rasterizer (no texture sampling).
        Used during interactive drag (is_interactive=True) for ~100fps response.
        """
        NF = face_v0.shape[0]
        H, W = buf.shape[0], buf.shape[1]
        for fi in range(NF):
            if not visible_mask[fi]:
                continue
            i0 = face_v0[fi]; i1 = face_v1[fi]; i2 = face_v2[fi]
            x0 = verts_sx[i0]; y0 = verts_sy[i0]
            x1 = verts_sx[i1]; y1 = verts_sy[i1]
            x2 = verts_sx[i2]; y2 = verts_sy[i2]
            bx0 = max(0, min(x0, x1, x2))
            by0 = max(0, min(y0, y1, y2))
            bx1 = min(W - 1, max(x0, x1, x2))
            by1 = min(H - 1, max(y0, y1, y2))
            if bx1 <= bx0 or by1 <= by0:
                continue
            denom = float((y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2))
            if abs(denom) < 0.5:
                continue
            inv_d = 1.0 / denom
            cr = fill_r[fi]; cg = fill_g[fi]; cb = fill_b[fi]
            for gy in range(by0, by1 + 1):
                for gx in range(bx0, bx1 + 1):
                    w0 = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) * inv_d
                    w1 = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) * inv_d
                    w2 = 1.0 - w0 - w1
                    if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                        continue
                    buf[gy, gx, 0] = cr
                    buf[gy, gx, 1] = cg
                    buf[gy, gx, 2] = cb
                    buf[gy, gx, 3] = 255


# ─────────────────────────────────────────────────────────────────────────────
#  Public API – tier-dispatched entry points
# ─────────────────────────────────────────────────────────────────────────────

def warmup_jit() -> None:
    """
    Trigger JIT compilation on a tiny dummy frame so the first real render
    does not stall.  Call once at application startup (e.g. after model load).

    No-op when Numba is unavailable (ACCEL_TIER != 1).
    Compilation takes ~1–2 s on first run; results are cached to disk by Numba.
    """
    global _JIT_WARMED, ACCEL_TIER  # noqa: PLW0603
    if _JIT_WARMED or ACCEL_TIER != 1:
        return
    log.info("accel: warming JIT rasterizer (first-time compilation ~1-2s)...")
    t0 = time.perf_counter()
    try:
        buf = np.zeros((32, 32, 4), dtype=np.uint8)
        tex = np.full((8, 8, 4), 128, dtype=np.uint8)
        _rasterize_triangle_jit(
            buf, tex,
            1, 1, 15, 2, 8, 20,
            0.1, 0.1, 0.9, 0.2, 0.5, 0.9,
            255, 255, 255, 255,
            False, False,
        )
        # Also warm the batch path
        vs_x = np.array([1, 15, 8], dtype=np.int64)
        vs_y = np.array([1, 2, 20], dtype=np.int64)
        uu   = np.array([0.1, 0.9, 0.5], dtype=np.float64)
        vv   = np.array([0.1, 0.2, 0.9], dtype=np.float64)
        f0 = np.array([0], dtype=np.int64)
        f1 = np.array([1], dtype=np.int64)
        f2 = np.array([2], dtype=np.int64)
        sr = np.array([255], dtype=np.int64)
        sg = np.array([255], dtype=np.int64)
        sb = np.array([255], dtype=np.int64)
        na = np.array([255], dtype=np.int64)
        vm = np.array([True], dtype=np.bool_)
        _rasterize_frame_jit(buf, tex, vs_x, vs_y, uu, vv, f0, f1, f2, sr, sg, sb, na, vm, False, False)
        # Warm flat shade
        fr = np.array([200], dtype=np.uint8)
        fg = np.array([150], dtype=np.uint8)
        fb = np.array([100], dtype=np.uint8)
        _flat_shade_frame_jit(buf, vs_x, vs_y, f0, f1, f2, fr, fg, fb, vm)
        _JIT_WARMED = True
        log.info(f"accel: JIT warmup done in {(time.perf_counter()-t0)*1000:.0f} ms")
    except Exception as exc:
        log.warning(f"accel: JIT warmup failed ({exc}) — falling back to NumPy tier")
        ACCEL_TIER = 2
        _JIT_WARMED = False


def rasterize_triangle(
    buf: np.ndarray,
    tex: np.ndarray,
    x0: int, y0: int, x1: int, y1: int, x2: int, y2: int,
    u0: float, v0: float, u1: float, v1: float, u2: float, v2: float,
    shade_r: int, shade_g: int, shade_b: int,
    node_alpha: float = 1.0,
    clamp_s: bool = False,
    clamp_t: bool = False,
) -> None:
    """
    Tier-dispatched single-triangle rasterizer.

    Routes to Numba JIT (Tier 1) or NumPy (Tier 2) depending on availability.
    PIL fallback is NOT provided here; callers should check ACCEL_TIER and fall
    back to _paste_textured_triangle() when ACCEL_TIER == 3.
    """
    if ACCEL_TIER == 1 and _JIT_WARMED:
        na255 = max(0, min(255, int(node_alpha * 255)))
        _rasterize_triangle_jit(  # type: ignore[name-defined]
            buf, tex,
            x0, y0, x1, y1, x2, y2,
            u0, v0, u1, v1, u2, v2,
            shade_r, shade_g, shade_b,
            na255,
            clamp_s, clamp_t,
        )
    else:
        _rasterize_triangle_numpy(
            buf, tex,
            x0, y0, x1, y1, x2, y2,
            u0, v0, u1, v1, u2, v2,
            shade_r, shade_g, shade_b,
            node_alpha,
            clamp_s, clamp_t,
        )


def rasterize_frame(
    buf:       np.ndarray,   # (H, W, 4) uint8 framebuffer
    tex:       np.ndarray,   # (TH, TW, 4) uint8 texture (single texture per call)
    verts_sx:  np.ndarray,   # (NV,) int64 screen X
    verts_sy:  np.ndarray,   # (NV,) int64 screen Y
    uvs_u:     np.ndarray,   # (NV,) float64 U
    uvs_v:     np.ndarray,   # (NV,) float64 V
    face_v0:   np.ndarray,   # (NF,) int64 vertex index 0
    face_v1:   np.ndarray,   # (NF,) int64 vertex index 1
    face_v2:   np.ndarray,   # (NF,) int64 vertex index 2
    shade_r:   np.ndarray,   # (NF,) int64 shade R [0..255]
    shade_g:   np.ndarray,   # (NF,) int64 shade G
    shade_b:   np.ndarray,   # (NF,) int64 shade B
    node_alpha: np.ndarray,  # (NF,) float64 per-face alpha [0..1]
    visible:   np.ndarray,   # (NF,) bool frustum-cull mask
    clamp_s: bool = False,
    clamp_t: bool = False,
) -> None:
    """
    Tier-dispatched batch frame rasterizer.

    Caller must pass faces in back-to-front order (depth-sorted).
    For multi-texture models, call once per texture batch.
    """
    if ACCEL_TIER == 1 and _JIT_WARMED:
        na255 = (node_alpha * 255).clip(0, 255).astype(np.int64)
        _rasterize_frame_jit(  # type: ignore[name-defined]
            buf, tex,
            verts_sx, verts_sy,
            uvs_u, uvs_v,
            face_v0, face_v1, face_v2,
            shade_r, shade_g, shade_b,
            na255, visible,
            clamp_s, clamp_t,
        )
    else:
        # NumPy / PIL fallback: iterate individually
        NF = len(face_v0)
        for fi in range(NF):
            if not visible[fi]:
                continue
            i0, i1, i2 = face_v0[fi], face_v1[fi], face_v2[fi]
            _rasterize_triangle_numpy(
                buf, tex,
                int(verts_sx[i0]), int(verts_sy[i0]),
                int(verts_sx[i1]), int(verts_sy[i1]),
                int(verts_sx[i2]), int(verts_sy[i2]),
                float(uvs_u[i0]), float(uvs_v[i0]),
                float(uvs_u[i1]), float(uvs_v[i1]),
                float(uvs_u[i2]), float(uvs_v[i2]),
                int(shade_r[fi]), int(shade_g[fi]), int(shade_b[fi]),
                float(node_alpha[fi]),
                clamp_s, clamp_t,
            )


def flat_shade_frame(
    buf:       np.ndarray,
    verts_sx:  np.ndarray,
    verts_sy:  np.ndarray,
    face_v0:   np.ndarray,
    face_v1:   np.ndarray,
    face_v2:   np.ndarray,
    fill_r:    np.ndarray,   # (NF,) uint8
    fill_g:    np.ndarray,
    fill_b:    np.ndarray,
    visible:   np.ndarray,
) -> None:
    """
    Tier-dispatched flat-shaded frame rasterizer (no texture sampling).
    Used during interactive drag for maximum viewport responsiveness.
    """
    if ACCEL_TIER == 1 and _JIT_WARMED:
        _flat_shade_frame_jit(  # type: ignore[name-defined]
            buf, verts_sx, verts_sy,
            face_v0, face_v1, face_v2,
            fill_r, fill_g, fill_b,
            visible,
        )
    else:
        NF = len(face_v0)
        H, W = buf.shape[:2]
        for fi in range(NF):
            if not visible[fi]:
                continue
            i0, i1, i2 = face_v0[fi], face_v1[fi], face_v2[fi]
            x0,y0 = int(verts_sx[i0]), int(verts_sy[i0])
            x1,y1 = int(verts_sx[i1]), int(verts_sy[i1])
            x2,y2 = int(verts_sx[i2]), int(verts_sy[i2])
            bx0=max(0,min(x0,x1,x2)); by0=max(0,min(y0,y1,y2))
            bx1=min(W-1,max(x0,x1,x2)); by1=min(H-1,max(y0,y1,y2))
            if bx1<=bx0 or by1<=by0: continue
            denom=float((y1-y2)*(x0-x2)+(x2-x1)*(y0-y2))
            if abs(denom)<0.5: continue
            inv_d=1.0/denom
            cr,cg,cb = int(fill_r[fi]),int(fill_g[fi]),int(fill_b[fi])
            gy,gx = np.mgrid[by0:by1+1, bx0:bx1+1]
            w0=((y1-y2)*(gx-x2)+(x2-x1)*(gy-y2))*inv_d
            w1=((y2-y0)*(gx-x2)+(x0-x2)*(gy-y2))*inv_d
            w2=1.0-w0-w1
            inside=(w0>=0)&(w1>=0)&(w2>=0)
            if inside.any():
                buf[gy[inside],gx[inside],0]=cr
                buf[gy[inside],gx[inside],1]=cg
                buf[gy[inside],gx[inside],2]=cb
                buf[gy[inside],gx[inside],3]=255
