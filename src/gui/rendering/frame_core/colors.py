"""Colour constants and textured/lightmap triangle paste helpers."""

from __future__ import annotations

from .dependencies import *  # noqa: F401,F403
from src.math.frame_math import _clamp, _edge_has_seam_global, _lerp, _uwrap_global, _vflip_nontiled, _vflip_tiled

# ─────────────────────────────────────────────────────────────────────
#  Colour constants
# ─────────────────────────────────────────────────────────────────────

_BG      = (23,  25, 28,  255)
_GRID    = (58,  64, 72,  255)
_WIRE    = (100,100,200, 255)
_BONE    = (255,170,  0, 255)
_SEL     = (0,  255,170, 255)
_AXIS_X  = (255, 80, 80, 255)
_AXIS_Y  = (80, 255, 80, 255)
_AXIS_Z  = (80, 140,255, 255)


def _hex_to_rgb_tuple(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return fallback


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

    # GL_REPEAT handles tiled finite UV coordinates at sampling time.
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
    # Lightmap UVs may also tile; wrapping is handled at sampling time.
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



__all__ = tuple(name for name in globals() if not name.startswith('__'))
