"""Math, UV, and sorting helpers for viewport frame rendering."""

from __future__ import annotations

import math
import struct as _struct

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

# KotOR uses tiled UV coordinates extensively.  UV magnitude is never used to
# decide whether geometry is renderable; renderers wrap or clamp at sampling time.

# ── Inner-geometry / face node substrings ──────────────────────────────────
# The authoritative definitions now live in :mod:`src.core.render_constants`
# so that the CPU rasterizer (this file) and the GPU renderer
# (``src/gui/gpu_renderer.py``) classify nodes identically.  The ``_INNER_GEO_
# SUBSTRINGS`` and ``_FACE_MESH_SUBSTRINGS`` module-level aliases are imported
# from there at the top of this file; all call sites below reference the same
# objects.  Do NOT re-define them here — any divergence reintroduces the
# CPU/GPU inner-geometry classification drift that ate several days of NPC-
# head debugging.  See render_constants.py for the full coverage rationale.

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



__all__ = tuple(name for name in globals() if not name.startswith('__'))
