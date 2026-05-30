"""TPC detection, DXT decompression, and image loading helpers."""

from __future__ import annotations

from .dependencies import *  # noqa: F401,F403

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


def _ensure_bottom_up(img: 'Image.Image', data: bytes = b'') -> 'Image.Image':
    """Normalise a TGA-derived image to bottom-up (OpenGL) row order.

    This is a **defensive utility** for the niche case where a caller bypasses
    Pillow (e.g. a hand-rolled TGA reader) and therefore needs explicit
    origin-bit inspection.  The default TGA loading path in this module goes
    through ``PIL.Image.open()``, which internally normalises every TGA
    variant to top-down regardless of the origin bit — see the
    ``FIX-TGA-ORIENT`` commentary in ``TextureCache._load_bytes`` — and then
    flips unconditionally to bottom-up.  For those callers this helper is a
    no-op.

    TGA origin bits (byte 17, bits 4–5, "image descriptor"):

      bit 5 (``0x20``) : screen origin     1 = top,    0 = bottom
      bit 4 (``0x10``) : horizontal origin 1 = right,  0 = left   (ignored here)

    Rule applied:

      * ``origin`` bit 5 set → row 0 is at the **top** of the image →
        image is already top-down as Pillow would produce it, so we flip it
        to bottom-up to match the renderer's ``tv = (1-v)*h`` convention.
      * ``origin`` bit 5 clear → row 0 is at the **bottom** → bottom-up
        already; no flip.

    Parameters
    ----------
    img : PIL.Image.Image
        The RGBA image to (possibly) flip.
    data : bytes
        Raw TGA bytes for header inspection.  Must be at least 18 bytes to
        include the image descriptor field.  If ``data`` is shorter than 18
        bytes or empty, the image is returned unchanged (safe fall-through).

    Returns
    -------
    PIL.Image.Image
        The input image, optionally flipped to bottom-up.

    Notes
    -----
    The helper is **not** wired into the Pillow code path on purpose — doing
    so would double-flip files with a top origin bit (Pillow already
    normalised them).  Callers that produce images from raw TGA bytes
    without Pillow can opt in here explicitly.
    """
    if not data or len(data) < 18:
        return img
    image_descriptor = data[17]
    top_origin = bool(image_descriptor & 0x20)
    if top_origin:
        try:
            return img.transpose(Image.FLIP_TOP_BOTTOM)
        except Exception:
            return img
    return img


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
        img._gr_gpu_uv_v_flip = True  # type: ignore[attr-defined]
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
    if img is not None:
        img._gr_gpu_uv_v_flip = True  # type: ignore[attr-defined]
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



__all__ = tuple(name for name in globals() if not name.startswith('__'))
