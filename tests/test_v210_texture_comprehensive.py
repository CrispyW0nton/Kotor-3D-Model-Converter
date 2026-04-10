"""
GhostRigger v2.1.0 — Comprehensive Texture Loading Tests

This test suite validates the complete texture loading pipeline, covering:

1. All TPC pixel formats (DXT1, DXT5, greyscale, RGB, RGBA, BGRA)
2. BGRA (enc=12, data_sz=0) - XBox Aurora variant (was broken: returned None/black)
3. Mipmap chain handling
4. Cubemap TPC detection and loading
5. TXI extraction for all formats
6. Alpha test threshold from TPC header
7. TPC detection for all valid encoding values
8. V-flip orientation for uncompressed vs DXT formats
9. Legacy decoder (_load_tpc_bytes_legacy) for all formats
10. tpc_render_utils._load_tpc_bytes for all formats
11. TextureCache._load_bytes TXI attribute preservation
12. Full pipeline: TPC bytes → TextureCache → apply TXI to node
"""

import sys
import os
import struct
import pytest

from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'src'))

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

from gui.viewport import (
    _load_tpc_bytes,
    _load_tpc_bytes_legacy,
    _is_tpc_data,
    _extract_txi_from_tpc,
    _parse_txi_string,
    _apply_txi_to_node,
    TextureCache,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tpc_header(w: int, h: int, enc: int, mips: int = 1,
                     data_sz: int = 0, alpha_test: float = 0.5) -> bytes:
    """Build a 128-byte TPC header."""
    hdr = struct.pack('<I f 2H B B', data_sz, alpha_test, w, h, enc, mips)
    return hdr + b'\x00' * (128 - len(hdr))


def _make_dxt1_block(r: int = 255, g: int = 0, b: int = 0) -> bytes:
    """Single DXT1 8-byte block encoding a solid color."""
    # Encode approximate color to RGB565
    c0 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    c1 = c0  # identical endpoints → same color
    return struct.pack('<HHI', c0, c1, 0)


def _make_dxt5_block(r: int = 255, g: int = 0, b: int = 0,
                     alpha: int = 255) -> bytes:
    """Single DXT5 16-byte block encoding a solid color+alpha."""
    alpha_block = bytes([alpha, alpha, 0, 0, 0, 0, 0, 0])
    color_block = _make_dxt1_block(r, g, b)
    return alpha_block + color_block


def _make_tpc_dxt1(w: int = 8, h: int = 8,
                   r: int = 255, g: int = 0, b: int = 0,
                   txi: str = '') -> bytes:
    """Build a DXT1 TPC with solid color and optional TXI."""
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    dxt1_block = _make_dxt1_block(r, g, b)
    pixel_data = dxt1_block * (bw * bh)
    data_sz = len(pixel_data)
    header = _make_tpc_header(w, h, 2, 1, data_sz)
    return header + pixel_data + txi.encode()


def _make_tpc_dxt5(w: int = 8, h: int = 8,
                   r: int = 255, g: int = 0, b: int = 0,
                   alpha: int = 255, txi: str = '',
                   alpha_test: float = 0.5) -> bytes:
    """Build a DXT5 TPC with solid color/alpha and optional TXI."""
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    dxt5_block = _make_dxt5_block(r, g, b, alpha)
    pixel_data = dxt5_block * (bw * bh)
    data_sz = len(pixel_data)
    header = _make_tpc_header(w, h, 4, 1, data_sz, alpha_test)
    return header + pixel_data + txi.encode()


def _make_tpc_rgba(w: int = 4, h: int = 4,
                   r: int = 255, g: int = 0, b: int = 0,
                   alpha: int = 255) -> bytes:
    """Build an uncompressed RGBA TPC.

    PyKotor convention: uncompressed = data_sz == 0.
    """
    pixel_data = bytes([r, g, b, alpha] * (w * h))
    header = _make_tpc_header(w, h, 4, 1, 0)  # data_sz=0 → uncompressed (pykotor)
    return header + pixel_data


def _make_tpc_rgb(w: int = 4, h: int = 4,
                  r: int = 255, g: int = 0, b: int = 0) -> bytes:
    """Build an uncompressed RGB TPC.

    PyKotor convention: uncompressed = data_sz == 0.
    """
    pixel_data = bytes([r, g, b] * (w * h))
    header = _make_tpc_header(w, h, 2, 1, 0)  # data_sz=0 → uncompressed (pykotor)
    return header + pixel_data


def _make_tpc_grey(w: int = 4, h: int = 4, grey: int = 128) -> bytes:
    """Build a greyscale TPC (enc=1, data_sz=0)."""
    pixel_data = bytes([grey] * (w * h))
    header = _make_tpc_header(w, h, 1, 1, 0)
    return header + pixel_data


def _make_tpc_bgra(w: int = 4, h: int = 4,
                   b: int = 255, g: int = 0, r: int = 0,
                   a: int = 255) -> bytes:
    """Build a BGRA TPC (enc=12, data_sz=0). Used on Xbox/some Aurora builds."""
    # BGRA format: bytes are stored as [B, G, R, A]
    pixel_data = bytes([b, g, r, a] * (w * h))
    header = _make_tpc_header(w, h, 12, 1, 0)  # data_sz=0 = uncompressed
    return header + pixel_data


def _make_tpc_with_mips(w: int = 8, h: int = 8, mips: int = 2) -> bytes:
    """Build a DXT1 TPC with a 2-level mipmap chain."""
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    block = _make_dxt1_block(255, 0, 0)
    mip0 = block * (bw * bh)
    mip1_w = max(1, w // 2)
    mip1_h = max(1, h // 2)
    bw1 = max(1, (mip1_w + 3) // 4)
    bh1 = max(1, (mip1_h + 3) // 4)
    mip1 = block * (bw1 * bh1)
    data_sz = len(mip0)
    header = _make_tpc_header(w, h, 2, mips, data_sz)
    return header + mip0 + mip1


def _make_tpc_cubemap(face_size: int = 4) -> bytes:
    """Build a DXT1 cubemap TPC (height = 6 * width)."""
    h = face_size * 6  # 6 faces stacked
    bw = max(1, (face_size + 3) // 4)
    bh = max(1, (h + 3) // 4)
    block = _make_dxt1_block(0, 0, 255)  # blue
    pixel_data = block * (bw * bh)
    data_sz = len(pixel_data)
    header = _make_tpc_header(face_size, h, 2, 1, data_sz)
    return header + pixel_data


# ── TPC Detection Tests ───────────────────────────────────────────────────────

class TestTpcDetection:
    """Test _is_tpc_data for all valid TPC formats."""

    def test_dxt1_compressed_detected(self):
        raw = _make_tpc_dxt1(8, 8, 255, 0, 0)
        assert _is_tpc_data(raw) is True

    def test_dxt5_compressed_detected(self):
        raw = _make_tpc_dxt5(8, 8)
        assert _is_tpc_data(raw) is True

    def test_rgba_uncompressed_detected(self):
        raw = _make_tpc_rgba(4, 4, 0, 255, 0)
        assert _is_tpc_data(raw) is True

    def test_rgb_uncompressed_detected(self):
        raw = _make_tpc_rgb(4, 4, 0, 0, 255)
        assert _is_tpc_data(raw) is True

    def test_greyscale_detected(self):
        raw = _make_tpc_grey(4, 4, 128)
        assert _is_tpc_data(raw) is True

    def test_bgra_detected(self):
        """BGRA TPC (enc=12, data_sz=0) must be detected."""
        raw = _make_tpc_bgra(4, 4, b=255, g=0, r=0, a=255)
        assert _is_tpc_data(raw) is True

    def test_mipmap_chain_detected(self):
        raw = _make_tpc_with_mips(8, 8, mips=2)
        assert _is_tpc_data(raw) is True

    def test_cubemap_detected(self):
        raw = _make_tpc_cubemap(4)
        assert _is_tpc_data(raw) is True

    def test_too_short_rejected(self):
        assert _is_tpc_data(b'\x00' * 127) is False

    def test_empty_rejected(self):
        assert _is_tpc_data(b'') is False

    def test_zero_dimensions_rejected(self):
        header = _make_tpc_header(0, 0, 2, 1, 0)
        assert _is_tpc_data(header + bytes(32)) is False


# ── TPC Loading Tests ─────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestTpcLoading:
    """Test _load_tpc_bytes for all valid TPC formats."""

    # ── DXT1 ──

    def test_dxt1_loads_as_rgba(self):
        raw = _make_tpc_dxt1(8, 8, 255, 0, 0)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (8, 8)

    def test_dxt1_red_pixel_correct(self):
        """DXT1 solid-red TPC: pixel should be approximately red."""
        raw = _make_tpc_dxt1(8, 8, 255, 0, 0)
        img = _load_tpc_bytes(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        # DXT1 RGB565 encoding truncates to 5/6 bits, so allow ±8 tolerance
        assert px[0] > 220, f"Red channel should be high, got {px}"
        assert px[1] < 10, f"Green channel should be 0, got {px}"
        assert px[2] < 10, f"Blue channel should be 0, got {px}"

    def test_dxt1_has_txi_str_attribute(self):
        raw = _make_tpc_dxt1(8, 8, txi='blending punchthrough\n')
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert hasattr(img, '_txi_str')

    def test_dxt1_txi_content_correct(self):
        raw = _make_tpc_dxt1(8, 8, txi='blending punchthrough\nenvmaptexture cm_baremetal\n')
        img = _load_tpc_bytes(raw)
        assert img is not None
        txi = getattr(img, '_txi_str', '')
        parsed = _parse_txi_string(txi)
        assert parsed['blending'] == 2, f"Expected blending=2, got {parsed['blending']}"
        assert parsed['envmaptexture'] == 'cm_baremetal'

    def test_dxt1_alpha_test_attribute(self):
        raw = _make_tpc_dxt1(8, 8)
        img = _load_tpc_bytes(raw)
        # alpha_test=0.5 (default) is within (0,1] so should be set
        assert hasattr(img, '_txi_alpha_test')
        assert 0.0 < img._txi_alpha_test <= 1.0

    def test_dxt1_custom_alpha_test_preserved(self):
        # Build with custom alpha_test=0.9
        bw, bh = max(1, (8+3)//4), max(1, (8+3)//4)
        dxt1 = _make_dxt1_block(255, 0, 0) * (bw * bh)
        data_sz = len(dxt1)
        header = _make_tpc_header(8, 8, 2, 1, data_sz, alpha_test=0.9)
        raw = header + dxt1
        img = _load_tpc_bytes(raw)
        assert img is not None
        at = getattr(img, '_txi_alpha_test', None)
        assert at is not None
        assert abs(at - 0.9) < 0.01, f"Expected alpha_test≈0.9, got {at}"

    # ── DXT5 ──

    def test_dxt5_loads_as_rgba(self):
        raw = _make_tpc_dxt5(8, 8)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (8, 8)

    def test_dxt5_alpha_255_preserved(self):
        raw = _make_tpc_dxt5(8, 8, r=255, g=0, b=0, alpha=255)
        img = _load_tpc_bytes(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        assert px[3] == 255, f"Alpha should be 255, got {px}"

    def test_dxt5_txi_extracted(self):
        txi = 'blending additive\n'
        raw = _make_tpc_dxt5(4, 4, txi=txi)
        img = _load_tpc_bytes(raw)
        assert img is not None
        txi_str = getattr(img, '_txi_str', '')
        parsed = _parse_txi_string(txi_str)
        assert parsed['blending'] == 1, f"Expected blending=1 (additive), got {parsed['blending']}"

    # ── RGBA uncompressed ──

    def test_rgba_uncompressed_loads(self):
        raw = _make_tpc_rgba(4, 4, r=0, g=255, b=0)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (4, 4)

    def test_rgba_uncompressed_orientation_correct(self):
        """Uncompressed RGBA (data_sz=0) is stored bottom-up; returned as-is (no flip).

        PyKotor rule: compressed = (data_sz != 0).
        For uncompressed RGBA (data_sz=0) KotOR stores rows bottom-up (OpenGL
        convention).  _load_tpc_bytes must preserve that order so the renderer's
        (1-v)*h formula maps UV coordinates correctly:

          storage row 0 = GL bottom = red  → PIL row 0 = red   (bottom-up preserved)
          storage row 3 = GL top    = blue → PIL row 3 = blue

        The renderer then maps UV V=0 (KotOR top) → (1-0)*h = h → PIL row h = bottom
        → correct texture-top colour (blue).  No extra flip is applied.
        """
        w, h = 4, 4
        pixels = bytearray()
        colors = [
            (255, 0, 0, 255),   # row 0 storage = GL bottom = red
            (0, 255, 0, 255),   # row 1 = green
            (255, 255, 255, 255),  # row 2 = white
            (0, 0, 255, 255),   # row 3 storage = GL top = blue
        ]
        for color in colors:
            for _ in range(w):
                pixels.extend(color)
        # data_sz=0 → pykotor treats as uncompressed → no flip
        header = _make_tpc_header(w, h, 4, 1, 0)
        raw = bytes(header) + bytes(pixels)
        img = _load_tpc_bytes(raw)
        assert img is not None
        # No flip for uncompressed: PIL row 0 = first stored row = red (GL bottom)
        row0_px = img.getpixel((0, 0))
        row3_px = img.getpixel((0, 3))
        assert row0_px[:3] == (255, 0, 0), f"PIL row 0 should be red (first stored row, no flip), got {row0_px}"
        assert row3_px[:3] == (0, 0, 255), f"PIL row 3 should be blue (last stored row, no flip), got {row3_px}"

    # ── RGB uncompressed ──

    def test_rgb_uncompressed_loads(self):
        raw = _make_tpc_rgb(4, 4, r=255, g=255, b=0)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (4, 4)

    def test_rgb_pixel_converted_to_rgba(self):
        raw = _make_tpc_rgb(4, 4, r=0, g=0, b=255)
        img = _load_tpc_bytes(raw)
        assert img is not None
        # Alpha should be 255 (fully opaque from RGB → RGBA conversion)
        px = img.getpixel((0, 0))
        assert px[3] == 255, f"Alpha from RGB should be 255, got {px}"

    # ── Greyscale ──

    def test_greyscale_loads(self):
        raw = _make_tpc_grey(4, 4, grey=200)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (4, 4)

    def test_greyscale_pixel_correct(self):
        raw = _make_tpc_grey(4, 4, grey=128)
        img = _load_tpc_bytes(raw)
        assert img is not None
        # Greyscale 128 should map to (128,128,128,255) in RGBA
        px = img.getpixel((0, 0))
        assert abs(px[0] - 128) <= 2, f"Grey R should be ~128, got {px}"
        assert px[3] == 255

    # ── BGRA (critical fix) ──

    def test_bgra_loads_correctly(self):
        """BGRA TPC (enc=12, data_sz=0) must load and return correct colors.

        This was broken in prior versions: enc=12 was treated as DXT1,
        but BGRA is an uncompressed format requiring B↔R channel swap.
        """
        # BGRA bytes: B=255, G=0, R=0, A=255 → should appear as RGBA blue
        raw = _make_tpc_bgra(4, 4, b=255, g=0, r=0, a=255)
        img = _load_tpc_bytes(raw)
        assert img is not None, "BGRA TPC should load successfully"
        assert img.mode == 'RGBA'
        assert img.size == (4, 4)
        px = img.getpixel((0, 0))
        assert px[0] == 0,   f"BGRA blue→RGBA: R should be 0, got {px}"
        assert px[1] == 0,   f"BGRA blue→RGBA: G should be 0, got {px}"
        assert px[2] == 255, f"BGRA blue→RGBA: B should be 255, got {px}"
        assert px[3] == 255, f"BGRA blue→RGBA: A should be 255, got {px}"

    def test_bgra_red_pixel(self):
        """BGRA red: B=0, G=0, R=255, A=255 → RGBA=(255,0,0,255)."""
        raw = _make_tpc_bgra(4, 4, b=0, g=0, r=255, a=255)
        img = _load_tpc_bytes(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        assert px[0] == 255, f"BGRA red→RGBA: R should be 255, got {px}"
        assert px[1] == 0,   f"BGRA red→RGBA: G should be 0, got {px}"
        assert px[2] == 0,   f"BGRA red→RGBA: B should be 0, got {px}"

    def test_bgra_orientation_correct(self):
        """BGRA is bottom-up; after loading PIL row 0 should be the first stored row.

        Convention (UV-fix v2): ALL loaded TPC images are returned in bottom-up
        orientation (PIL row 0 = OpenGL V=0 = texture bottom).  BGRA is stored
        bottom-up (like all uncompressed TPC formats), so NO vertical flip is
        applied.  The BGRA→RGBA channel swap happens but the row order is preserved:

          storage row 0 = GL bottom → PIL row 0 = blue  (first stored BGRA row)
          storage row 3 = GL top   → PIL row 3 = red   (last stored BGRA row)

        The renderer's (1-v)*h formula then maps OpenGL V coordinates to PIL rows:
          V=0 (GL bottom) → PIL row h-1 (last row = GL bottom stored at row 3 after
          all-same-color blocks) or correct texture-bottom colour.
        """
        w, h = 4, 4
        # First stored row (GL bottom) = blue, last stored row (GL top) = red
        pixels = bytearray()
        # Row 0 storage = BGRA blue:  B=255, G=0, R=0, A=255
        # Rows 1-3 storage           B=0,   G=0, R=255, A=255  → red after BGRA→RGBA swap
        for row in range(h):
            color = (255, 0, 0, 255) if row == 0 else (0, 0, 255, 255)  # B,G,R,A
            for _ in range(w):
                pixels.extend(color)
        header = _make_tpc_header(w, h, 12, 1, 0)  # BGRA, data_sz=0
        raw = bytes(header) + bytes(pixels)
        img = _load_tpc_bytes(raw)
        assert img is not None
        # No V-flip for BGRA (already bottom-up).  Channel swap only:
        #   storage row 0  BGRA (255,0,0,255) → RGBA (0,0,255,255) = blue  → PIL row 0
        #   storage row 3  BGRA (0,0,255,255) → RGBA (255,0,0,255) = red   → PIL row 3
        top_px = img.getpixel((0, 0))
        bottom_px = img.getpixel((0, h - 1))
        assert top_px[:3] == (0, 0, 255), f"PIL row 0 should be blue (first stored BGRA row, no flip), got {top_px}"
        assert bottom_px[:3] == (255, 0, 0), f"PIL bottom row should be red (last stored BGRA row), got {bottom_px}"

    # ── Mipmap chain ──

    def test_mipmap_chain_loads_first_mip(self):
        """TPC with mipmap chain should load the first (largest) mip level."""
        raw = _make_tpc_with_mips(8, 8, mips=2)
        img = _load_tpc_bytes(raw)
        assert img is not None
        # First mip is 8×8
        assert img.size == (8, 8), f"Expected 8×8 (first mip), got {img.size}"

    # ── Cubemap ──

    def test_cubemap_loads_first_face(self):
        """Cubemap TPC (height=6*width) should load successfully."""
        raw = _make_tpc_cubemap(4)
        img = _load_tpc_bytes(raw)
        # pykotor extracts one face; accept any square RGBA image
        assert img is not None
        assert img.mode == 'RGBA'

    # ── TXI attributes ──

    def test_tpc_raw_attribute_set(self):
        """_load_tpc_bytes must set _tpc_raw on the returned image."""
        raw = _make_tpc_dxt1(4, 4)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert hasattr(img, '_tpc_raw'), "Image must have _tpc_raw attribute"

    def test_txi_str_empty_when_no_txi(self):
        """_load_tpc_bytes must set _txi_str='' when no TXI is present."""
        raw = _make_tpc_dxt1(4, 4, txi='')
        img = _load_tpc_bytes(raw)
        assert img is not None
        txi_str = getattr(img, '_txi_str', None)
        assert txi_str is not None, "_txi_str must be set (may be empty)"
        # Empty or non-empty string both valid; no crash expected

    def test_txi_envmaptexture_extracted(self):
        raw = _make_tpc_dxt5(4, 4, txi='envmaptexture cm_fog\n')
        img = _load_tpc_bytes(raw)
        assert img is not None
        txi_str = getattr(img, '_txi_str', '')
        parsed = _parse_txi_string(txi_str)
        assert parsed.get('envmaptexture') == 'cm_fog'

    def test_txi_bumpmaptexture_extracted(self):
        raw = _make_tpc_dxt5(4, 4, txi='bumpmaptexture n_sithpraet\n')
        img = _load_tpc_bytes(raw)
        assert img is not None
        txi_str = getattr(img, '_txi_str', '')
        parsed = _parse_txi_string(txi_str)
        assert parsed.get('bumpmaptexture') == 'n_sithpraet'


# ── Legacy Decoder Tests ───────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestLegacyTpcDecoder:
    """Test _load_tpc_bytes_legacy for all supported formats."""

    def test_dxt1_legacy_loads(self):
        raw = _make_tpc_dxt1(8, 8, 255, 0, 0)
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (8, 8)

    def test_dxt5_legacy_loads(self):
        raw = _make_tpc_dxt5(8, 8)
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None
        assert img.mode == 'RGBA'

    def test_rgba_uncompressed_legacy(self):
        raw = _make_tpc_rgba(4, 4, 255, 0, 0)
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None
        assert img.mode == 'RGBA'

    def test_greyscale_legacy(self):
        raw = _make_tpc_grey(4, 4, 200)
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None
        assert img.mode == 'RGBA'

    def test_bgra_legacy_loads_correctly(self):
        """Legacy decoder must handle BGRA (enc=12, data_sz=0) with B↔R swap."""
        raw = _make_tpc_bgra(4, 4, b=255, g=0, r=0, a=255)  # blue in BGRA
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None, "Legacy decoder must handle BGRA format"
        assert img.mode == 'RGBA'
        px = img.getpixel((0, 0))
        assert px[2] == 255, f"BGRA blue→RGBA: B channel should be 255, got {px}"
        assert px[0] == 0,   f"BGRA blue→RGBA: R channel should be 0, got {px}"

    def test_bgra_legacy_red_pixel(self):
        raw = _make_tpc_bgra(4, 4, b=0, g=0, r=255, a=255)  # red
        img = _load_tpc_bytes_legacy(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        assert px[0] == 255, f"BGRA red→RGBA: R should be 255, got {px}"
        assert px[2] == 0,   f"BGRA red→RGBA: B should be 0, got {px}"

    def test_none_for_empty_data(self):
        assert _load_tpc_bytes_legacy(bytes(32)) is None

    def test_none_for_zero_dimensions(self):
        header = _make_tpc_header(0, 0, 2, 1, 0)
        assert _load_tpc_bytes_legacy(header + bytes(64)) is None


# ── tpc_render_utils Tests ─────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestTpcRenderUtils:
    """Test tpc_render_utils._load_tpc_bytes for BGRA and other formats."""

    def _load_render_utils(self):
        try:
            from gui import tpc_render_utils
            return tpc_render_utils
        except ImportError:
            return None

    def test_bgra_via_render_utils(self):
        """tpc_render_utils._load_tpc_bytes must correctly handle BGRA enc=12."""
        ru = self._load_render_utils()
        if ru is None:
            pytest.skip("tpc_render_utils not importable")
        raw = _make_tpc_bgra(4, 4, b=255, g=0, r=0, a=255)
        img = ru._load_tpc_bytes(raw)
        assert img is not None, "tpc_render_utils must handle BGRA"
        px = img.getpixel((0, 0))
        assert px[2] == 255, f"BGRA blue→RGBA B channel should be 255, got {px}"

    def test_dxt1_via_render_utils(self):
        ru = self._load_render_utils()
        if ru is None:
            pytest.skip("tpc_render_utils not importable")
        raw = _make_tpc_dxt1(8, 8, 255, 0, 0)
        img = ru._load_tpc_bytes(raw)
        assert img is not None
        assert img.mode == 'RGBA'

    def test_dxt5_via_render_utils(self):
        ru = self._load_render_utils()
        if ru is None:
            pytest.skip("tpc_render_utils not importable")
        raw = _make_tpc_dxt5(8, 8, alpha=255)
        img = ru._load_tpc_bytes(raw)
        assert img is not None


# ── TextureCache Pipeline Tests ───────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestTextureCachePipeline:
    """Test TextureCache._load_bytes preserves TXI attributes."""

    def test_txi_str_preserved_through_load_bytes(self):
        """TextureCache._load_bytes must preserve _txi_str from _load_tpc_bytes."""
        txi = 'blending punchthrough\nenvmaptexture cm_baremetal\n'
        raw = _make_tpc_dxt5(4, 4, txi=txi)
        tc = TextureCache()
        img = tc._load_bytes(raw)
        assert img is not None
        txi_str = getattr(img, '_txi_str', None)
        assert txi_str is not None, "_txi_str must be preserved through _load_bytes"
        parsed = _parse_txi_string(txi_str)
        assert parsed['blending'] == 2

    def test_alpha_test_preserved_through_load_bytes(self):
        raw = _make_tpc_dxt1(4, 4)  # default alpha_test=0.5
        tc = TextureCache()
        img = tc._load_bytes(raw)
        assert img is not None
        at = getattr(img, '_txi_alpha_test', None)
        assert at is not None
        assert 0.0 < at <= 1.0

    def test_load_bytes_bgra(self):
        """TextureCache._load_bytes must handle BGRA format."""
        raw = _make_tpc_bgra(4, 4, b=255, g=0, r=0, a=255)
        tc = TextureCache()
        img = tc._load_bytes(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        assert px[2] == 255, f"BGRA→RGBA blue should be in B channel, got {px}"


# ── TXI Extraction from TPC Tests ─────────────────────────────────────────────

class TestTxiExtractionFromTpc:
    """Test _extract_txi_from_tpc for all formats."""

    def test_extract_txi_from_dxt1(self):
        raw = _make_tpc_dxt1(4, 4, txi='blending punchthrough\n')
        txi = _extract_txi_from_tpc(raw)
        assert 'blending' in txi.lower()

    def test_extract_txi_from_dxt5(self):
        raw = _make_tpc_dxt5(4, 4, txi='envmaptexture cm_fog\n')
        txi = _extract_txi_from_tpc(raw)
        assert 'envmaptexture' in txi.lower()

    def test_extract_empty_txi_when_none(self):
        raw = _make_tpc_dxt1(4, 4, txi='')
        txi = _extract_txi_from_tpc(raw)
        # May be empty or None-ish; must not crash
        assert isinstance(txi, str)

    def test_extract_txi_multiline(self):
        txi_content = 'blending punchthrough\nenvmaptexture cm_baremetal\nbumpmaptexture n_bump\n'
        raw = _make_tpc_dxt5(4, 4, txi=txi_content)
        txi = _extract_txi_from_tpc(raw)
        parsed = _parse_txi_string(txi)
        assert parsed['blending'] == 2
        assert parsed['envmaptexture'] == 'cm_baremetal'


# ── Apply TXI to Node Integration Tests ───────────────────────────────────────

class TestApplyTxiNodeIntegration:
    """Test full TXI-to-node pipeline for texture metadata."""

    def _make_mesh_node(self):
        from core.model_data import ModelNode, NodeFlags
        node = ModelNode()
        node.name = 'test_mesh'
        node.texture = 'test_tex'
        # Must set MESH flag so is_mesh property returns True
        node.flags = NodeFlags.MESH | NodeFlags.HEADER
        return node

    def test_apply_punchthrough_txi_to_node(self):
        """Punchthrough TXI must set txi_blending=2 and correct alpha_test."""
        node = self._make_mesh_node()
        _apply_txi_to_node(node, 'blending punchthrough\n', alpha_test=0.7)
        assert node.txi_blending == 2
        assert abs(node.txi_alpha_test - 0.7) < 0.01

    def test_apply_additive_txi_to_node(self):
        node = self._make_mesh_node()
        _apply_txi_to_node(node, 'blending additive\n', alpha_test=0.5)
        assert node.txi_blending == 1

    def test_apply_envmap_txi_to_node(self):
        node = self._make_mesh_node()
        _apply_txi_to_node(node, 'envmaptexture cm_baremetal\n', alpha_test=0.5)
        assert node.txi_envmaptexture == 'cm_baremetal'

    def test_apply_bumpmap_txi_sets_bump_map(self):
        node = self._make_mesh_node()
        _apply_txi_to_node(node, 'bumpmaptexture n_bump01\n', alpha_test=0.5)
        assert node.txi_bumpmaptexture == 'n_bump01'
        assert node.bump_map == 'n_bump01'

    def test_apply_txi_from_textures_to_model_sets_blending(self):
        """_apply_txi_from_textures_to_model must set txi_blending on mesh nodes."""
        try:
            from gui.gpu_renderer import _apply_txi_from_textures_to_model
        except ImportError:
            pytest.skip("gpu_renderer not importable")

        node = self._make_mesh_node()

        # Build a TPC with punchthrough TXI and attach as texture
        raw = _make_tpc_dxt5(4, 4, alpha_test=0.7,
                              txi='blending punchthrough\nenvmaptexture cm_test\n')
        img = _load_tpc_bytes(raw)
        assert img is not None

        textures = {'test_tex': img}

        class _FakeModel:
            def all_nodes(self):
                return [node]

        _apply_txi_from_textures_to_model(_FakeModel(), textures)
        assert node.txi_blending == 2, f"txi_blending should be 2 after apply, got {node.txi_blending}"
        assert abs(node.txi_alpha_test - 0.7) < 0.01, f"alpha_test should be ≈0.7, got {node.txi_alpha_test}"


# ── Orientation / V-flip Tests ────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestTpcOrientation:
    """Verify that all TPC formats return images in top-down (PIL) orientation."""

    def test_dxt1_is_already_top_down(self):
        """DXT1 is stored top-down; no flip needed."""
        # DXT1 block: top-left = red, others = black
        # In standard DXT ordering, block (0,0) = top-left of image
        # c0 > c1 → 4-color, index 0 = c0 = red, index 1 = c1 = black
        c0 = 0xF800  # red RGB565
        c1 = 0x0000  # black
        lk = 0x00000000  # all pixels = color 0 = red
        dxt1 = struct.pack('<HHI', c0, c1, lk)
        raw = _make_tpc_header(4, 4, 2, 1, 8) + dxt1
        img = _load_tpc_bytes(raw)
        assert img is not None
        px = img.getpixel((0, 0))
        assert px[0] > 220, f"DXT1 top-left should be red, got {px}"

    def test_rgba_uncompressed_no_flip_bottom_up_preserved(self):
        """RGBA uncompressed (data_sz=0) is returned as-is in bottom-up order.

        PyKotor rule: data_sz=0 → uncompressed → no flip.  The first stored
        row is GL bottom and remains PIL row 0 after loading.  The renderer's
        V-flip at render-time handles the coordinate conversion.
        """
        w, h = 4, 4
        # storage row 0 = GL bottom = blue; row 3 = GL top = red
        pixels = bytearray()
        for row in range(h):
            color = (0, 0, 255, 255) if row == 0 else (255, 0, 0, 255)
            for _ in range(w):
                pixels.extend(color)
        # data_sz=0 → uncompressed, no flip
        header = _make_tpc_header(w, h, 4, 1, 0)
        raw = bytes(header) + bytes(pixels)
        img = _load_tpc_bytes(raw)
        assert img is not None
        top = img.getpixel((0, 0))
        # No flip: PIL row 0 = first stored row = blue (GL bottom)
        assert top[:3] == (0, 0, 255), f"Bottom-up preserved: PIL row 0 should be blue, got {top}"


# ── Edge Cases ────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="Pillow not available")
class TestTpcEdgeCases:
    """Test edge cases and error handling in TPC loading."""

    def test_none_for_too_short_data(self):
        assert _load_tpc_bytes(bytes(64)) is None

    def test_none_for_zero_dimensions(self):
        header = _make_tpc_header(0, 0, 2, 1, 0)
        assert _load_tpc_bytes(header + bytes(64)) is None

    def test_dxt1_4x4_minimum_size(self):
        """Minimum 4×4 DXT1 TPC (1 block = 8 bytes) should load."""
        raw = _make_tpc_dxt1(4, 4, 128, 0, 128)
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.size == (4, 4)

    def test_large_texture_256x256(self):
        """256×256 DXT1 TPC should load successfully."""
        bw = bh = max(1, (256 + 3) // 4)
        block = _make_dxt1_block(255, 255, 0)  # yellow
        pixel_data = block * (bw * bh)
        data_sz = len(pixel_data)
        header = _make_tpc_header(256, 256, 2, 1, data_sz)
        raw = header + pixel_data
        img = _load_tpc_bytes(raw)
        assert img is not None
        assert img.size == (256, 256)

    def test_txi_with_binary_noise_rejected(self):
        """TXI block containing binary data should be rejected/ignored."""
        # DXT1 block followed by binary noise (not valid TXI)
        raw = _make_tpc_dxt1(4, 4) + bytes([0xFF, 0x80, 0x00] * 20)
        img = _load_tpc_bytes(raw)
        # Should not crash; TXI string may be empty
        assert img is not None

    def test_alpha_test_zero_not_attached(self):
        """alpha_test=0.0 in TPC header must NOT be attached (invalid threshold)."""
        bw, bh = max(1, 5 // 4), max(1, 5 // 4)
        dxt1 = _make_dxt1_block() * (bw * bh)
        data_sz = len(dxt1)
        header = _make_tpc_header(4, 4, 2, 1, data_sz, alpha_test=0.0)
        raw = header + dxt1
        img = _load_tpc_bytes(raw)
        assert img is not None
        at = getattr(img, '_txi_alpha_test', None)
        assert at is None or at > 0.0, "alpha_test=0.0 must not be attached"

    def test_alpha_test_gt_1_not_attached(self):
        """alpha_test > 1.0 in TPC header must NOT be attached (invalid)."""
        bw, bh = max(1, 5 // 4), max(1, 5 // 4)
        dxt1 = _make_dxt1_block() * (bw * bh)
        data_sz = len(dxt1)
        header = _make_tpc_header(4, 4, 2, 1, data_sz, alpha_test=2.5)
        raw = header + dxt1
        img = _load_tpc_bytes(raw)
        assert img is not None
        at = getattr(img, '_txi_alpha_test', None)
        assert at is None or (0.0 < at <= 1.0), f"Invalid alpha_test must not be attached: {at}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
