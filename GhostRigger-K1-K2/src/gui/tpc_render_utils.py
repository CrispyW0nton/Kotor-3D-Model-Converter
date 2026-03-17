"""
tpc_render_utils.py — Pure-Python TPC/DXT texture and triangle rendering utilities.

This module contains ONLY headless-safe, GUI-free utility functions extracted
from viewport.py.  It has zero tkinter dependency and can be imported anywhere.

Functions exported:
  _is_tpc_data(data)             → bool
  _load_tpc_bytes(data)          → PIL RGBA Image or None
  _clean_tex_name(name)          → str
  _decompress_dxt1_bytes(data, w, h) → bytearray
  _decompress_dxt5_bytes(data, w, h) → bytearray
  _paste_textured_triangle(img, tex, sp0, sp1, sp2, uv0, uv1, uv2, W, H, shade)
  _uwrap_global(base, other)     → float
  _edge_has_seam_global(a, b)    → bool
  _vflip_nontiled(v, th)         → float
  _vflip_tiled(v, tile_v, src_h) → float
  _UV_SENTINEL                   = 20.0

Used by:
  - src/gui/viewport.py  (imported at top, avoids code duplication)
  - tools/headless_render_test.py  (standalone texture render tests)
"""
import math, struct
from typing import Optional

_PIL = False
try:
    from PIL import Image, ImageDraw
    _PIL = True
except ImportError:
    pass

_UV_SENTINEL = 20.0

# ── Math helpers ─────────────────────────────────────────────────────────────
def _normalize(v):
    l = math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2])
    return (v[0]/l,v[1]/l,v[2]/l) if l>1e-9 else (0.0,1.0,0.0)

def _clean_tex_name(name: str) -> str:
    """Sanitize a texture name from a binary fixed-width field."""
    if not name: return ''
    out = []
    for ch in name:
        if 32 <= ord(ch) <= 126: out.append(ch)
        else: break
    return ''.join(out).strip()

def _lerp(a, b, t): return a + (b-a)*t

# ── Module-level UV seam helpers ─────────────────────────────────────────────
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


# ── TPC detection ─────────────────────────────────────────────────────────────
def _is_tpc_data(data: bytes) -> bool:
    """
    Detect KotOR TPC format from raw bytes.

    KotOR TPC header layout (128 bytes, BioWare Aurora engine):
      [0-3]   uint32  data_sz    – byte size of first mip level pixel data (0=mip chain)
      [4-7]   float   alpha_test_threshold
      [8-9]   uint16  width
      [10-11] uint16  height
      [12]    uint8   encoding   – 0=auto, 1=grey, 2=RGB/DXT1, 4=RGBA/DXT5,
                                   10=DXT1, 12=DXT1, 13=DXT3, 14=DXT5
      [13]    uint8   mip_count
      [14-127] reserved zeros

    NOTE: The real Aurora TPC format has ENCODING at byte[12] and mip_count at
    byte[13].  Bytes[14-127] are always zero in genuine TPC files.
    The "layers" field described in some tools is actually the encoding field.
    """
    if len(data) < 128:
        return False
    data_sz = struct.unpack_from('<I', data, 0)[0]
    w       = struct.unpack_from('<H', data, 8)[0]
    h       = struct.unpack_from('<H', data, 10)[0]
    enc     = data[12]   # ENCODING at offset 12 (Aurora engine format)
    mips    = data[13]

    # PyKotor-compatible zero-byte test (primary fast-path):
    # bytes[15..100] are ALL zero in genuine TPC files.
    pykotor_tpc = all(b == 0 for b in data[15:100])
    if pykotor_tpc:
        if 0 < w <= 8192 and 0 < h <= 8192 * 6:
            return True
        if w > 0 and h > 0:
            return True

    # Encoding-based detection
    TPC_ENCS = (0, 1, 2, 4, 10, 12, 13, 14)
    if w == 0 or h == 0 or w > 4096:
        return False
    _cubemap_h = (h == 6 * w)
    if not _cubemap_h and h > 4096:
        return False
    if enc not in TPC_ENCS:
        return False
    bx = max(1, (w+3)//4); by = max(1, (h+3)//4)
    valid = {bx*by*8, bx*by*16, w*h, w*h*3, w*h*4}
    if data_sz in valid:
        return True
    if data_sz == 0 and enc in TPC_ENCS and mips > 0:
        min_pixel = 1 if enc == 1 else (3 if enc == 2 else 4)
        if len(data) >= 128 + min_pixel:
            return True
    if data_sz > 0 and 128 + data_sz <= len(data) + 1024:
        if enc in TPC_ENCS and len(data) > 256:
            return True
    return False


def _is_tpc_file(path: str) -> bool:
    """Returns True if path is a TPC file by reading its header."""
    try:
        with open(path, 'rb') as f:
            return _is_tpc_data(f.read(256))
    except Exception:
        return False


# ── DXT decompressors ─────────────────────────────────────────────────────────
def _decompress_dxt1_bytes(data: bytes, w: int, h: int) -> bytearray:
    """Software DXT1 block decompressor → RGBA bytearray."""
    result = bytearray(w * h * 4)
    bw = max(1, (w+3)//4); bh = max(1, (h+3)//4)
    for by in range(bh):
        for bx in range(bw):
            pos = (by * bw + bx) * 8
            if pos + 8 > len(data): continue
            c0r = struct.unpack_from('<H', data, pos)[0]
            c1r = struct.unpack_from('<H', data, pos+2)[0]
            lk  = struct.unpack_from('<I', data, pos+4)[0]
            def e(c): return (((c>>11)&31)*255//31, ((c>>5)&63)*255//63, (c&31)*255//31)
            c0, c1 = e(c0r), e(c1r)
            punchthrough = (c0r <= c1r)
            if not punchthrough:
                cols  = [c0, c1,
                         tuple((2*c0[i]+c1[i])//3 for i in range(3)),
                         tuple((c0[i]+2*c1[i])//3 for i in range(3))]
                alphas = [255, 255, 255, 255]
            else:
                cols  = [c0, c1,
                         tuple((c0[i]+c1[i])//2 for i in range(3)),
                         (0,0,0)]
                alphas = [255, 255, 255, 0]
            for py2 in range(4):
                for px2 in range(4):
                    idx = (lk >> (2*(py2*4+px2))) & 3
                    col = cols[idx]
                    gx, gy = bx*4+px2, by*4+py2
                    if gx < w and gy < h:
                        o = (gy*w+gx)*4
                        result[o]=col[0]; result[o+1]=col[1]
                        result[o+2]=col[2]; result[o+3]=alphas[idx]
    return result


def _decompress_dxt5_bytes(data: bytes, w: int, h: int) -> bytearray:
    """Software DXT5 block decompressor → RGBA bytearray."""
    result = bytearray(w * h * 4)
    bw = max(1, (w+3)//4); bh = max(1, (h+3)//4)
    for by in range(bh):
        for bx in range(bw):
            pos = (by * bw + bx) * 16
            if pos + 16 > len(data): continue
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
                        result[o]=col[0]; result[o+1]=col[1]
                        result[o+2]=col[2]; result[o+3]=alpha
    return result


# ── TPC image loader ─────────────────────────────────────────────────────────
def _load_tpc_bytes(data: bytes) -> Optional['Image.Image']:
    """
    Load a KotOR TPC image from raw bytes.  Returns PIL RGBA Image or None.

    KotOR TPC header layout (BioWare / Aurora engine format):
      [0-3]   uint32  data_sz   – first-mip pixel data size (0 = use mip chain)
      [4-7]   float   alpha_test
      [8-9]   uint16  width
      [10-11] uint16  height
      [12]    uint8   encoding  – 0=auto(data_sz), 1=grey, 2=RGB or DXT1,
                                  4=RGBA or DXT5, 10=DXT1, 12=DXT1, 13=DXT3, 14=DXT5
      [13]    uint8   mip_count
      [14-127] reserved zeros

    IMPORTANT: The Aurora engine stores the ENCODING at byte[12], not byte[14].
    The commonly-cited "layers" field (byte[12]=1..4 channels) is actually the
    encoding value for all stock KotOR textures:
      enc=2  → RGB uncompressed (data_sz==w*h*3) OR DXT1 (data_sz==dxt1_sz)
      enc=4  → RGBA uncompressed (data_sz==w*h*4) OR DXT5 (data_sz==dxt5_sz)
    Stock BIF-extracted textures always have enc=2 or enc=4.

    BOTTOM-UP vs TOP-DOWN:
    - Uncompressed TPC (enc=1,2 raw RGB, enc=4 raw RGBA) are BOTTOM-UP (OpenGL).
      We flip vertically after load so the image is top-down (PIL-standard).
    - DXT-compressed textures (enc=0 resolved, enc=10,12,13,14) are TOP-DOWN.
    - When enc=2/4 resolves to DXT, no flip needed.
    - When enc=2/4 resolves to raw, flip vertically.
    """
    if not _PIL or len(data) < 128:
        return None

    data_sz  = struct.unpack_from('<I', data, 0)[0]
    width    = struct.unpack_from('<H', data, 8)[0]
    height   = struct.unpack_from('<H', data, 10)[0]
    encoding = data[12]   # CORRECT: encoding at offset 12 (Aurora engine format)
    mip_cnt  = data[13]

    if width == 0 or height == 0:
        return None

    # Cubemap detection: 6 square faces stacked → height = 6 * width
    _is_cubemap = (height > 0 and width > 0 and height // width == 6
                   and height % width == 0)
    if _is_cubemap:
        height = width  # render only first face

    pixel_data = data[128:]
    bx = max(1, (width+3)//4); by = max(1, (height+3)//4)
    dxt1_sz = bx * by * 8
    dxt5_sz = bx * by * 16

    # ── enc=0 (auto-encoding): infer from data_sz + encoding ─────────────
    # Stock KotOR BIF textures use enc=0; the real encoding is detected by
    # matching data_sz to the DXT1 or DXT5 block sizes for this resolution.
    if encoding == 0:
        if data_sz == dxt1_sz or (data_sz == 0 and len(pixel_data) >= dxt1_sz and encoding <= 2):
            encoding = 10
        elif data_sz == dxt5_sz or (data_sz == 0 and len(pixel_data) >= dxt5_sz):
            encoding = 14
        elif len(pixel_data) >= dxt5_sz:
            encoding = 14
        elif len(pixel_data) >= dxt1_sz:
            encoding = 10

    def _flip(img):
        try: return img.transpose(Image.FLIP_TOP_BOTTOM)
        except: return img

    try:
        sz3 = width * height * 3
        sz4 = width * height * 4

        # enc=1: greyscale, bottom-up
        if encoding == 1:
            sz = width * height
            if len(pixel_data) >= sz:
                return _flip(Image.frombytes('L', (width, height),
                                             pixel_data[:sz]).convert('RGBA'))

        # enc=2: RGB (bottom-up) OR DXT1 (top-down)
        # Priority: if data_sz matches DXT1 → DXT1; if matches sz3 → raw RGB
        if encoding == 2:
            if data_sz == sz3 and len(pixel_data) >= sz3:
                return _flip(Image.frombytes('RGB', (width, height),
                                             pixel_data[:sz3]).convert('RGBA'))
            if (data_sz == dxt1_sz or data_sz == 0) and len(pixel_data) >= dxt1_sz:
                raw = _decompress_dxt1_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if len(pixel_data) >= dxt1_sz:
                raw = _decompress_dxt1_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if len(pixel_data) >= sz3:
                return _flip(Image.frombytes('RGB', (width, height),
                                             pixel_data[:sz3]).convert('RGBA'))

        # enc=4: RGBA (bottom-up) OR DXT5 (top-down)
        if encoding == 4:
            if data_sz == sz4 and len(pixel_data) >= sz4:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             pixel_data[:sz4]))
            if (data_sz == dxt5_sz or data_sz == 0) and len(pixel_data) >= dxt5_sz:
                raw = _decompress_dxt5_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if len(pixel_data) >= dxt5_sz:
                raw = _decompress_dxt5_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if len(pixel_data) >= sz4:
                return _flip(Image.frombytes('RGBA', (width, height),
                                             pixel_data[:sz4]))

        # enc=10,12: DXT1
        if encoding in (10, 12) and len(pixel_data) >= dxt1_sz:
            raw = _decompress_dxt1_bytes(pixel_data, width, height)
            return Image.frombytes('RGBA', (width, height), bytes(raw))

        # enc=13,14: DXT5
        if encoding in (13, 14) and len(pixel_data) >= dxt5_sz:
            raw = _decompress_dxt5_bytes(pixel_data, width, height)
            return Image.frombytes('RGBA', (width, height), bytes(raw))

        # Universal fallback from data_sz
        if data_sz > 0 and len(pixel_data) >= data_sz:
            if data_sz == dxt5_sz:
                raw = _decompress_dxt5_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if data_sz == dxt1_sz:
                raw = _decompress_dxt1_bytes(pixel_data, width, height)
                return Image.frombytes('RGBA', (width, height), bytes(raw))
            if data_sz == sz4:
                return _flip(Image.frombytes('RGBA', (width, height), pixel_data[:sz4]))
            if data_sz == sz3:
                return _flip(Image.frombytes('RGB', (width, height),
                                             pixel_data[:sz3]).convert('RGBA'))
        # Last resort: try both DXT sizes
        if len(pixel_data) >= dxt5_sz:
            raw = _decompress_dxt5_bytes(pixel_data, width, height)
            return Image.frombytes('RGBA', (width, height), bytes(raw))
        if len(pixel_data) >= dxt1_sz:
            raw = _decompress_dxt1_bytes(pixel_data, width, height)
            return Image.frombytes('RGBA', (width, height), bytes(raw))
        return None
    except Exception:
        return None


# ── Triangle rasterizer (UV-mapped) ─────────────────────────────────────────
def _paste_textured_triangle(
        img,          # PIL RGB Image (modified in-place)
        tex_img,      # PIL RGBA texture Image
        sp0, sp1, sp2,  # screen pixel coords (sx, sy)
        uv0, uv1, uv2,  # (u, v) in [0,1]
        W: int, H: int,
        shade_color: tuple,
        sel_brightness: int = 0,
        node_alpha: float = 1.0,
        is_additive: bool = False,
        skip_seam_fix: bool = False,  # legacy combined flag
        skip_seam_u: bool = False,    # True → bypass U-axis seam fix
        skip_seam_v: bool = False):   # True → bypass V-axis seam fix
    """
    Paste a UV-mapped texture triangle onto `img` using PIL's fast AFFINE
    (projective) transform.

    KotOR UV convention: V=0 is the BOTTOM of the texture (OpenGL-style).
    PIL images are top-down: row 0 is TOP.
    Therefore we flip V: tex_row = (1 - v) * height.

    Seam-crossing fix (v10.3): when two UV coordinates straddle a tile
    boundary (e.g. u0=0.95, u1=0.02), the affine interpolation travels the
    long way around.  We pull u1/u2 within +/-0.5 of u0 to fix this.
    Uses strict exclusive in-bounds guard (-0.1 < u_try < 1.1) to avoid
    sampling the transparent AFFINE fillcolor fringe at texture edges.

    Tiling (v10.3): for UV spans > 1.5, we pre-tile the texture image.
    Centroid integer shift preserves seam-corrected UVs that are slightly
    outside [0,1] without triggering tiling.

    Aligned with viewport.py _paste_textured_triangle v10.3 logic.
    """
    if not _PIL or tex_img is None:
        return

    # UV sentinel guard
    if (abs(uv0[0]) > _UV_SENTINEL or abs(uv0[1]) > _UV_SENTINEL or
            abs(uv1[0]) > _UV_SENTINEL or abs(uv1[1]) > _UV_SENTINEL or
            abs(uv2[0]) > _UV_SENTINEL or abs(uv2[1]) > _UV_SENTINEL):
        return

    sx0,sy0=int(sp0[0]),int(sp0[1])
    sx1,sy1=int(sp1[0]),int(sp1[1])
    sx2,sy2=int(sp2[0]),int(sp2[1])

    bx0=max(0,min(sx0,sx1,sx2)); by0=max(0,min(sy0,sy1,sy2))
    bx1=min(W-1,max(sx0,sx1,sx2)); by1=min(H-1,max(sy0,sy1,sy2))
    bw=bx1-bx0+1; bh=by1-by0+1
    if bw<=0 or bh<=0: return

    rx0,ry0=sx0-bx0,sy0-by0
    rx1,ry1=sx1-bx0,sy1-by0
    rx2,ry2=sx2-bx0,sy2-by0

    tw,th=tex_img.size

    # ── UV coordinate preparation (v10.3 sync with viewport.py) ─────────────
    # Use separate raw vs working variable names to avoid clobbering seam-
    # corrected values.  v0r/v1r/v2r are the working V variables (preserved
    # for the V-flip and affine-solve sections below).
    u0       = float(uv0[0]);  v0r      = float(uv0[1])
    u1_raw   = float(uv1[0]);  v1r_in   = float(uv1[1])
    u2_raw   = float(uv2[0]);  v2r_in   = float(uv2[1])

    # V-flip scale factors (set after tiling section)
    _vflip_tiles = None
    _vflip_src_h = None

    # Raw UV span (before any seam fix)
    _u_span_raw = max(u0, u1_raw, u2_raw) - min(u0, u1_raw, u2_raw)
    _v_span_raw = max(v0r, v1r_in, v2r_in) - min(v0r, v1r_in, v2r_in)

    # ── Seam-crossing fix (v10.4b) ────────────────────────────────────────────────────
    # FAST PATH: if all UVs lie strictly within [0.05, 0.95] no tile boundary
    # can be crossed - skip seam detection entirely (>80% of KotOR triangles).
    #
    # Per-axis skip flags allow independent control of U and V seam fixes.
    # skip_seam_u=True: bypass U-axis seam fix (caller confirmed no U-seam vertices)
    # skip_seam_v=True: bypass V-axis seam fix (caller confirmed no V-seam vertices)
    # skip_seam_fix is legacy combined flag (both axes).
    #
    # Strict exclusive in-bounds guard for wrapped vertices:
    #   -0.1 < u_try < 1.1  (exclusive)
    # The old span*0.70-only guard accepted u_try=1.1 which samples the
    # transparent AFFINE fillcolor fringe, causing a dark edge artifact.
    # Genuine KotOR seam vertices sit very close to 0 or 1 so their wrapped
    # value is at most ~1.03 - safely within (-0.1, 1.1).
    #
    # When span >= 1.0 skip the seam fix (the triangle spans multiple tiles
    # and will be handled by the tiling section below).
    _skip_u = skip_seam_fix or skip_seam_u
    _skip_v = skip_seam_fix or skip_seam_v
    _U_SEAM_SAFE = _skip_u or (0.05 <= u0 <= 0.95 and
                    0.05 <= u1_raw <= 0.95 and
                    0.05 <= u2_raw <= 0.95)
    _V_SEAM_SAFE = _skip_v or (0.05 <= v0r <= 0.95 and
                    0.05 <= v1r_in <= 0.95 and
                    0.05 <= v2r_in <= 0.95)

    if _U_SEAM_SAFE:
        u1, u2 = u1_raw, u2_raw
    elif _u_span_raw < 1.0:
        u_has_seam = (_edge_has_seam_global(u0, u1_raw) or
                      _edge_has_seam_global(u0, u2_raw) or
                      _edge_has_seam_global(u1_raw, u2_raw))
        if u_has_seam:
            u1_try = _uwrap_global(u0, u1_raw)
            u2_try = _uwrap_global(u0, u2_raw)
            new_span = max(u0, u1_try, u2_try) - min(u0, u1_try, u2_try)
            # Strict exclusive bounds guard with significant span reduction
            if new_span < _u_span_raw * 0.70 and -0.1 < u1_try < 1.1 and -0.1 < u2_try < 1.1:
                u1, u2 = u1_try, u2_try
            else:
                u1, u2 = u1_raw, u2_raw
        else:
            u1, u2 = u1_raw, u2_raw
    else:
        u1, u2 = u1_raw, u2_raw

    # V seam fix (same logic as U, using v1r/v2r as working variables)
    if _V_SEAM_SAFE:
        v1r, v2r = v1r_in, v2r_in
    elif _v_span_raw < 1.0:
        v_has_seam = (_edge_has_seam_global(v0r, v1r_in) or
                      _edge_has_seam_global(v0r, v2r_in) or
                      _edge_has_seam_global(v1r_in, v2r_in))
        if v_has_seam:
            v1_try = _uwrap_global(v0r, v1r_in)
            v2_try = _uwrap_global(v0r, v2r_in)
            new_vspan = max(v0r, v1_try, v2_try) - min(v0r, v1_try, v2_try)
            # Strict exclusive bounds guard
            if new_vspan < _v_span_raw * 0.70 and -0.1 < v1_try < 1.1 and -0.1 < v2_try < 1.1:
                v1r, v2r = v1_try, v2_try
            else:
                v1r, v2r = v1r_in, v2r_in
        else:
            v1r, v2r = v1r_in, v2r_in
    else:
        v1r, v2r = v1r_in, v2r_in

    u_min = min(u0, u1, u2);    u_max = max(u0, u1, u2)
    v_min = min(v0r, v1r, v2r); v_max = max(v0r, v1r, v2r)

    # ── Tiling ────────────────────────────────────────────────────
    # Span-based tiling check, not position-based.
    # Threshold 1.0 prevents KotOR back-seam triangles
    # (e.g. torso u=[0.003,1.366,0.003], span=1.363) tile correctly instead
    # of falling through to centroid-shift with u_max still OOB.
    MAX_TILE_SRC_PX  = 128
    MAX_TILED_PIXELS = 512*512
    MAX_TILE_COUNT   = 8

    u_span_curr = u_max - u_min
    v_span_curr = v_max - v_min
    needs_tiling = (u_span_curr > 1.0 or v_span_curr > 1.0)

    # Centroid-integer-shift for out-of-range single-tile faces
    if not needs_tiling and (u_min < -0.001 or u_max > 1.001 or
                              v_min < -0.001 or v_max > 1.001):
        u_cen = (u0 + u1 + u2) / 3.0
        v_cen = (v0r + v1r + v2r) / 3.0
        u_int_shift = int(math.floor(u_cen))
        v_int_shift = int(math.floor(v_cen))
        if u_int_shift != 0:
            u0 -= u_int_shift;  u1 -= u_int_shift;  u2 -= u_int_shift
        if v_int_shift != 0:
            v0r -= v_int_shift;  v1r -= v_int_shift;  v2r -= v_int_shift
        # Recompute min/max after centroid shift (v10.3 fix: was missing previously)
        u_min = min(u0, u1, u2);    u_max = max(u0, u1, u2)
        v_min = min(v0r, v1r, v2r); v_max = max(v0r, v1r, v2r)
        # Stage-A: integer floor shift for multi-tile OOB (guarded).
        # Guard: only apply when (v_max - floor) ≤ 1.001 so we don't wrap
        # a face with v_max=0.17 up by +1 tile to v_max=1.17.
        if u_min < -0.001:
            _uf2 = int(math.floor(u_min))
            if _uf2 != 0 and (u_max - _uf2) <= 1.001:
                u0-=_uf2; u1-=_uf2; u2-=_uf2
                u_min=min(u0,u1,u2); u_max=max(u0,u1,u2)
        if v_min < -0.001:
            _vf2 = int(math.floor(v_min))
            if _vf2 != 0 and (v_max - _vf2) <= 1.001:
                v0r-=_vf2; v1r-=_vf2; v2r-=_vf2
                v_min=min(v0r,v1r,v2r); v_max=max(v0r,v1r,v2r)
        if u_max > 1.001:
            _uc2 = int(math.floor(u_max))
            if _uc2 > 0 and (u_max - u_min) < 0.5:
                u0-=_uc2; u1-=_uc2; u2-=_uc2
                u_min=min(u0,u1,u2); u_max=max(u0,u1,u2)
        if v_max > 1.001:
            _vc2 = int(math.floor(v_max))
            if _vc2 > 0 and (v_max - v_min) < 0.5:
                v0r-=_vc2; v1r-=_vc2; v2r-=_vc2
                v_min=min(v0r,v1r,v2r); v_max=max(v0r,v1r,v2r)
        # Stage-B: fringe clamp for tiny sub-pixel OOB (|delta| < 0.05).
        # e.g. v=-0.006 after centroid pass: floor=-1, but Stage-A guard blocked
        # the +1 shift (v_max=0.17 would become 1.17). Apply a fractional shift
        # of exactly v_min to bring the minimum to 0, preserving relative UVs.
        if u_min < -0.001 and u_min > -0.05 and (u_max - u_min) <= 1.001:
            _ufr = u_min
            u0-=_ufr; u1-=_ufr; u2-=_ufr
            u_min=min(u0,u1,u2); u_max=max(u0,u1,u2)
        if v_min < -0.001 and v_min > -0.05 and (v_max - v_min) <= 1.001:
            _vfr = v_min
            v0r-=_vfr; v1r-=_vfr; v2r-=_vfr
            v_min=min(v0r,v1r,v2r); v_max=max(v0r,v1r,v2r)

    if needs_tiling:
        u_floor = int(math.floor(u_min));  v_floor = int(math.floor(v_min))
        tile_u  = int(math.floor(u_max)) - u_floor + 1
        tile_v  = int(math.floor(v_max)) - v_floor + 1

        if tile_u <= MAX_TILE_COUNT and tile_v <= MAX_TILE_COUNT:
            try:
                src_w = max(1, min(tw, MAX_TILE_SRC_PX))
                src_h = max(1, min(th, MAX_TILE_SRC_PX))
                tw_t = src_w * tile_u;  th_t = src_h * tile_v
                if tw_t * th_t > MAX_TILED_PIXELS:
                    sc = (MAX_TILED_PIXELS / (tw_t * th_t)) ** 0.5
                    src_w = max(1, int(src_w * sc));  src_h = max(1, int(src_h * sc))
                    tw_t = src_w * tile_u;  th_t = src_h * tile_v
                src_rgba = tex_img.convert('RGBA')
                thumb = src_rgba.resize((src_w, src_h),
                    Image.BOX if hasattr(Image, 'BOX') else Image.NEAREST)
                tiled = Image.new('RGBA', (tw_t, th_t))
                for ti in range(tile_u):
                    for tj in range(tile_v):
                        tiled.paste(thumb, (ti * src_w, tj * src_h))
                tex_img = tiled;  tw, th = tw_t, th_t
                u0 -= u_floor;  u1 -= u_floor;  u2 -= u_floor
                v0r -= v_floor;  v1r -= v_floor;  v2r -= v_floor
                _vflip_tiles = tile_v;  _vflip_src_h = src_h
            except MemoryError:
                needs_tiling = False
            except Exception:
                needs_tiling = False
        else:
            # UV range too large to tile: centroid-shift to bring centroid into [0,1]
            u_cen = (u0 + u1 + u2) / 3.0
            v_cen = (v0r + v1r + v2r) / 3.0
            u_shift = int(math.floor(u_cen));  v_shift = int(math.floor(v_cen))
            u0 -= u_shift;  u1 -= u_shift;  u2 -= u_shift
            v0r -= v_shift;  v1r -= v_shift;  v2r -= v_shift
            needs_tiling = False

    if _vflip_tiles is not None:
        tv0=_vflip_tiled(v0r,_vflip_tiles,_vflip_src_h)
        tv1=_vflip_tiled(v1r,_vflip_tiles,_vflip_src_h)
        tv2=_vflip_tiled(v2r,_vflip_tiles,_vflip_src_h)
    else:
        tv0=_vflip_nontiled(v0r,th)
        tv1=_vflip_nontiled(v1r,th)
        tv2=_vflip_nontiled(v2r,th)

    tu0=u0*tw; tu1=u1*tw; tu2=u2*tw

    # ── Solve affine transform ─────────────────────────────────────────────
    denom=rx0*(ry1-ry2)+rx1*(ry2-ry0)+rx2*(ry0-ry1)
    if abs(denom)<0.5: return
    inv=1.0/denom
    a=(tu0*(ry1-ry2)+tu1*(ry2-ry0)+tu2*(ry0-ry1))*inv
    b=(tu0*(rx2-rx1)+tu1*(rx0-rx2)+tu2*(rx1-rx0))*inv
    c=(tu0*(rx1*ry2-rx2*ry1)+tu1*(rx2*ry0-rx0*ry2)+tu2*(rx0*ry1-rx1*ry0))*inv
    d=(tv0*(ry1-ry2)+tv1*(ry2-ry0)+tv2*(ry0-ry1))*inv
    e=(tv0*(rx2-rx1)+tv1*(rx0-rx2)+tv2*(rx1-rx0))*inv
    f=(tv0*(rx1*ry2-rx2*ry1)+tv1*(rx2*ry0-rx0*ry2)+tv2*(rx0*ry1-rx1*ry0))*inv

    # ── Warp and composite ────────────────────────────────────────────────
    try:
        src=tex_img if tex_img.mode=='RGBA' else tex_img.convert('RGBA')
        patch=src.transform((bw,bh),Image.AFFINE,(a,b,c,d,e,f),
                             resample=Image.BILINEAR,fillcolor=(0,0,0,0))
        # Apply shade (lighting)
        sr,sg,sb=shade_color[0],shade_color[1],shade_color[2]
        sr=min(255,sr+sel_brightness); sg=min(255,sg+sel_brightness); sb=min(255,sb+sel_brightness)
        if not (sr>=253 and sg>=253 and sb>=253):
            try:
                import numpy as _np
                arr=_np.array(patch,dtype=_np.uint16)
                arr[:,:,0]=(arr[:,:,0]*sr//255).clip(0,255)
                arr[:,:,1]=(arr[:,:,1]*sg//255).clip(0,255)
                arr[:,:,2]=(arr[:,:,2]*sb//255).clip(0,255)
                patch=Image.fromarray(arr.astype(_np.uint8),'RGBA')
            except Exception:
                pass

        # Handle node alpha
        alpha=patch.split()[3]
        if node_alpha < 1.0:
            try:
                import numpy as _np
                a_arr=_np.array(alpha,dtype=_np.uint16)
                a_arr=(a_arr*max(0,min(1,node_alpha))).clip(0,255).astype(_np.uint8)
                alpha=Image.fromarray(a_arr,'L')
            except Exception:
                pass

        # Composite onto destination
        if img.mode=='RGB':
            region=img.crop((bx0,by0,bx0+bw,by0+bh)).convert('RGBA')
            region.paste(patch,(0,0),alpha)
            img.paste(region.convert('RGB'),(bx0,by0))
        else:
            img.paste(patch,(bx0,by0),alpha)
    except Exception:
        pass
