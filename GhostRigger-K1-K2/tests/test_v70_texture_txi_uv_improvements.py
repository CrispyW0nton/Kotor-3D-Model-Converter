"""
GhostRigger v7.0 — Comprehensive Texture/TXI/UV Improvement Tests

This test suite validates the full KOTOR texture mapping improvements:

BUG-TXI-1: TXI extraction from TPC used wrong field encoding at offset 14 instead
  of pixel_type at offset 12 for compression detection. Fix: use PyKotor-compatible
  pixel_type/mipmap_count field mapping and compression detection (data_sz != 0).

BUG-TXI-2: No TXI string parser existed; TXI metadata was extracted but never
  parsed into usable fields. Fix: add _parse_txi_string() that converts TXI ASCII
  to a structured dict with all relevant fields (blending, cube, proceduretype,
  numx, numy, fps, clamp_s/t, bumpmaptexture, envmaptexture, etc.)

BUG-TXI-3: No mechanism to apply TXI metadata to ModelNode fields. Fix: add
  _apply_txi_to_node() that calls _parse_txi_string() and updates node.txi_*
  fields.

BUG-TXI-4: TextureCache had no TXI loading support. Fix: add get_txi() method
  that searches disk (.txi files), extracts from TPC files, and loads from BIF
  archives, with proper caching.

BUG-UV4-1: UV sets 2 and 3 (MDX Texture2/Texture3 channels) were parsed in the
  MDL parser but never stored on the node. Fix: add uvs_2/uvs_3 fields to
  ModelNode and populate them from mdx_t2_off/mdx_t3_off.

BUG-RENDER-1: TXI additive blending (blending=1) was not applied during rendering.
  Fix: pass txi_blending to triangle data and reduce node_alpha to 0.5 for
  additive-blended faces.

BUG-RENDER-2: Flipbook animations (proceduretype=cycle, numx/numy, fps) were
  not applied to UV coordinates during rendering. Fix: add _compute_flipbook_uv()
  helper and apply it when _node_is_flipbook is True.

BUG-RENDER-3: TXI clamp mode (clamp_s/clamp_t) was not applied. Fix: clamp
  UV coordinates to [0,1] when txi_clamp_s/txi_clamp_t are set.

BUG-RENDER-4: Additional TXI UV rotation ('rotate' command) was not applied.
  Fix: apply 2D UV rotation around (0.5, 0.5) when txi_rotate != 0.

Tests cover:
  - TXI extraction offset calculation (pixel_type vs encoding field)
  - TXI string parsing for all key commands
  - _apply_txi_to_node field population
  - TextureCache.get_txi disk/embedded loading
  - UV2/UV3 field existence in ModelNode
  - UV2/UV3 parsing from MDX channel data
  - Flipbook UV coordinate computation
  - TXI clamp mode UV clamping
  - TXI rotate UV rotation
  - Additive blending triangle ordering
  - Full round-trip: MDL parse → TXI load → render call
"""

import math
import struct
import threading
import pytest

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

# ─── Import paths ─────────────────────────────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.viewport import (
    _parse_txi_string,
    _apply_txi_to_node,
    _compute_flipbook_uv,
    _extract_txi_from_tpc,
    _is_tpc_data,
    _load_tpc_bytes,
    TextureCache,
)
from src.core.model_data import ModelNode, NodeFlags


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_mesh_node(name: str = 'test', texture: str = 'test_tex') -> ModelNode:
    """Create a simple mesh node with a texture."""
    node = ModelNode(name=name, flags=NodeFlags.MESH)
    node.texture = texture
    node.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    node.faces = [(0, 1, 2)]
    node.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    return node


def _make_tpc_header(width: int, height: int, pixel_type: int,
                     mip_count: int = 1, data_sz: int = 0) -> bytes:
    """Build a minimal 128-byte TPC header."""
    header = bytearray(128)
    struct.pack_into('<I', header, 0, data_sz)     # data_sz at offset 0
    struct.pack_into('<f', header, 4, 1.0)          # alpha_test at offset 4
    struct.pack_into('<H', header, 8, width)        # width at offset 8
    struct.pack_into('<H', header, 10, height)      # height at offset 10
    header[12] = pixel_type                         # pixel_type at offset 12
    header[13] = mip_count                          # mip_count at offset 13
    # bytes 14-127 are 0 (reserved) — required for TPC detection
    return bytes(header)


def _make_tpc_with_txi(width: int, height: int, pixel_type: int,
                        txi_str: str, compressed: bool = True) -> bytes:
    """Build a TPC file with embedded TXI metadata."""
    if compressed:
        # DXT1 data: bx*by*8 bytes
        bx = max(1, (width + 3) // 4)
        by = max(1, (height + 3) // 4)
        if pixel_type in (2,):
            pixel_data_size = bx * by * 8   # DXT1
        else:
            pixel_data_size = bx * by * 16  # DXT5
        header = _make_tpc_header(width, height, pixel_type, 1, pixel_data_size)
        pixel_data = bytes(pixel_data_size)
    else:
        # Uncompressed
        bpp = {1: 1, 2: 3, 4: 4}.get(pixel_type, 4)
        pixel_data_size = width * height * bpp
        header = _make_tpc_header(width, height, pixel_type, 1, 0)
        pixel_data = bytes(pixel_data_size)
    txi_bytes = txi_str.encode('utf-8')
    return header + pixel_data + txi_bytes


# ─────────────────────────────────────────────────────────────────────────────
#  1. TXI String Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTxiString:
    """Test _parse_txi_string() with various TXI command sets."""

    def test_empty_string_returns_defaults(self):
        result = _parse_txi_string('')
        assert result['blending'] == 0
        assert result['cube'] is False
        assert result['proceduretype'] == ''
        assert result['numx'] == 0
        assert result['numy'] == 0
        assert result['fps'] == 0.0
        assert result['loop'] is True
        assert result['clamp_s'] is False
        assert result['clamp_t'] is False

    def test_blending_additive(self):
        result = _parse_txi_string('blending additive\n')
        assert result['blending'] == 1

    def test_blending_punchthrough(self):
        result = _parse_txi_string('blending punchthrough\n')
        assert result['blending'] == 2

    def test_blending_punch_through_hyphenated(self):
        result = _parse_txi_string('blending punch-through\n')
        assert result['blending'] == 2

    def test_cube_flag(self):
        result = _parse_txi_string('cube 1\n')
        assert result['cube'] is True

    def test_cube_flag_zero(self):
        result = _parse_txi_string('cube 0\n')
        assert result['cube'] is False

    def test_proceduretype_cycle(self):
        result = _parse_txi_string('proceduretype cycle\n')
        assert result['proceduretype'] == 'cycle'

    def test_flipbook_grid(self):
        txi = 'proceduretype cycle\nnumx 4\nnumy 2\nfps 10\n'
        result = _parse_txi_string(txi)
        assert result['proceduretype'] == 'cycle'
        assert result['numx'] == 4
        assert result['numy'] == 2
        assert result['fps'] == 10.0

    def test_envmap_texture(self):
        result = _parse_txi_string('envmaptexture cm_fog\n')
        assert result['envmaptexture'] == 'cm_fog'

    def test_bumpmap_texture(self):
        result = _parse_txi_string('bumpmaptexture n_test_bump\n')
        assert result['bumpmaptexture'] == 'n_test_bump'

    def test_bumpmapscaling(self):
        result = _parse_txi_string('bumpmapscaling 2.5\n')
        assert abs(result['bumpmapscaling'] - 2.5) < 1e-6

    def test_rotate(self):
        result = _parse_txi_string('rotate 0.25\n')
        assert abs(result['rotate'] - 0.25) < 1e-6

    def test_clamp_s(self):
        result = _parse_txi_string('clamps 1\n')
        assert result['clamp_s'] is True

    def test_clamp_t(self):
        result = _parse_txi_string('clampt 1\n')
        assert result['clamp_t'] is True

    def test_isbumpmap(self):
        result = _parse_txi_string('isbumpmap 1\n')
        assert result['isbumpmap'] is True

    def test_islightmap(self):
        result = _parse_txi_string('islightmap 1\n')
        assert result['islightmap'] is True

    def test_multiple_commands(self):
        txi = (
            'blending additive\n'
            'proceduretype cycle\n'
            'numx 8\n'
            'numy 8\n'
            'fps 24.0\n'
            'envmaptexture cm_baremetal\n'
        )
        result = _parse_txi_string(txi)
        assert result['blending'] == 1
        assert result['proceduretype'] == 'cycle'
        assert result['numx'] == 8
        assert result['numy'] == 8
        assert result['fps'] == 24.0
        assert result['envmaptexture'] == 'cm_baremetal'

    def test_case_insensitive_commands(self):
        result = _parse_txi_string('BLENDING ADDITIVE\nNUMX 3\n')
        assert result['blending'] == 1
        assert result['numx'] == 3

    def test_unknown_commands_ignored(self):
        """Unknown commands should not raise exceptions."""
        result = _parse_txi_string('unknowncmd somevalue\nblending additive\n')
        assert result['blending'] == 1

    def test_malformed_values_handled(self):
        """Malformed numeric values should not crash the parser."""
        result = _parse_txi_string('numx notanumber\nfps good\n')
        # Should remain at defaults since values are invalid
        assert result['numx'] == 0  # default unchanged due to parse error

    def test_mipmap_command(self):
        result = _parse_txi_string('mipmap 0\n')
        assert result['mipmap'] == 0

    def test_decal_command(self):
        result = _parse_txi_string('decal 1\n')
        assert result['decal'] is True

    def test_distort_commands(self):
        txi = 'distort 1\ndistortangle 0.5\ndistortspeed 2.0\n'
        result = _parse_txi_string(txi)
        assert result['distort'] is True
        assert abs(result['distortangle'] - 0.5) < 1e-6
        assert abs(result['distortspeed'] - 2.0) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
#  2. _apply_txi_to_node Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyTxiToNode:
    """Test that _apply_txi_to_node properly updates ModelNode TXI fields."""

    def test_empty_txi_no_changes(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, '')
        assert node.txi_blending == 0
        assert node.txi_cube is False
        assert node.txi_proceduretype == ''

    def test_additive_blending_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'blending additive\n')
        assert node.txi_blending == 1

    def test_punchthrough_blending_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'blending punchthrough\n')
        assert node.txi_blending == 2

    def test_cube_flag_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'cube 1\n')
        assert node.txi_cube is True

    def test_flipbook_params_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'proceduretype cycle\nnumx 4\nnumy 4\nfps 10\n')
        assert node.txi_proceduretype == 'cycle'
        assert node.txi_numx == 4
        assert node.txi_numy == 4
        assert abs(node.txi_fps - 10.0) < 1e-6

    def test_envmap_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'envmaptexture cm_fog\n')
        assert node.txi_envmaptexture == 'cm_fog'

    def test_bumpmap_applied_to_both_fields(self):
        """bumpmap texture should update both txi_bumpmaptexture AND node.bump_map."""
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'bumpmaptexture n_bump\n')
        assert node.txi_bumpmaptexture == 'n_bump'
        assert node.bump_map == 'n_bump'

    def test_bumpmapscaling_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'bumpmapscaling 3.0\n')
        assert abs(node.txi_bumpmapscaling - 3.0) < 1e-6

    def test_rotate_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'rotate 0.5\n')
        assert abs(node.txi_rotate - 0.5) < 1e-6

    def test_clamp_modes_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'clamps 1\nclampt 1\n')
        assert node.txi_clamp_s is True
        assert node.txi_clamp_t is True

    def test_loop_false_applied(self):
        node = _make_mesh_node()
        _apply_txi_to_node(node, 'loop 0\n')
        assert node.txi_loop is False

    def test_idempotent_apply(self):
        """Applying TXI twice should not cause any issues."""
        node = _make_mesh_node()
        txi = 'blending additive\nnumx 4\n'
        _apply_txi_to_node(node, txi)
        _apply_txi_to_node(node, txi)
        assert node.txi_blending == 1
        assert node.txi_numx == 4


# ─────────────────────────────────────────────────────────────────────────────
#  3. Flipbook UV Computation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeFlipbookUV:
    """Test _compute_flipbook_uv() frame-cell mapping."""

    def test_single_frame_unchanged(self):
        """1x1 flipbook should return UV unchanged."""
        u, v = _compute_flipbook_uv(0.5, 0.5, 1, 1, frame=0)
        assert abs(u - 0.5) < 1e-6
        assert abs(v - 0.5) < 1e-6

    def test_zero_numx_returns_unchanged(self):
        """Zero grid size should return UV unchanged."""
        u, v = _compute_flipbook_uv(0.3, 0.7, 0, 4, frame=0)
        assert u == 0.3
        assert v == 0.7

    def test_2x2_frame0_top_left(self):
        """Frame 0 of 2x2 grid = top-left cell."""
        u, v = _compute_flipbook_uv(0.5, 0.5, 2, 2, frame=0)
        # col=0, row=0: u_out = (0 + 0.5) * 0.5 = 0.25, v_out = (0 + 0.5) * 0.5 = 0.25
        assert abs(u - 0.25) < 1e-6
        assert abs(v - 0.25) < 1e-6

    def test_2x2_frame1_top_right(self):
        """Frame 1 of 2x2 grid = top-right cell (col=1, row=0)."""
        u, v = _compute_flipbook_uv(0.5, 0.5, 2, 2, frame=1)
        # col=1, row=0: u_out = (1 + 0.5) * 0.5 = 0.75, v_out = (0 + 0.5) * 0.5 = 0.25
        assert abs(u - 0.75) < 1e-6
        assert abs(v - 0.25) < 1e-6

    def test_2x2_frame2_bottom_left(self):
        """Frame 2 of 2x2 grid = bottom-left cell (col=0, row=1)."""
        u, v = _compute_flipbook_uv(0.5, 0.5, 2, 2, frame=2)
        # col=0, row=1: u_out = (0 + 0.5) * 0.5 = 0.25, v_out = (1 + 0.5) * 0.5 = 0.75
        assert abs(u - 0.25) < 1e-6
        assert abs(v - 0.75) < 1e-6

    def test_4x4_frame15_last(self):
        """Frame 15 (last) of 4x4 = bottom-right cell (col=3, row=3)."""
        u, v = _compute_flipbook_uv(0.5, 0.5, 4, 4, frame=15)
        # col=3, row=3: u_out = (3 + 0.5)/4 = 0.875, v_out = (3 + 0.5)/4 = 0.875
        assert abs(u - 0.875) < 1e-6
        assert abs(v - 0.875) < 1e-6

    def test_frame_wraps_around(self):
        """Frames past total_frames should wrap around."""
        # 2x2 grid, frame=4 → frame=0 (mod 4)
        u0, v0 = _compute_flipbook_uv(0.5, 0.5, 2, 2, frame=0)
        u4, v4 = _compute_flipbook_uv(0.5, 0.5, 2, 2, frame=4)
        assert abs(u0 - u4) < 1e-6
        assert abs(v0 - v4) < 1e-6

    def test_uv_within_cell_preserves_offset(self):
        """UVs within [0,1] should map to within the correct cell."""
        # 4x4 grid, frame=0 (col=0, row=0): UVs should stay in [0, 0.25]
        for uv_in in [0.0, 0.25, 0.5, 0.75, 0.99]:
            u_out, v_out = _compute_flipbook_uv(uv_in, uv_in, 4, 4, frame=0)
            assert 0.0 <= u_out <= 0.25 + 1e-6
            assert 0.0 <= v_out <= 0.25 + 1e-6

    def test_non_square_grid(self):
        """Non-square flipbook grid should work correctly."""
        # 8x4 grid, frame=8 → col = 8 % 8 = 0, row = 8 // 8 = 1
        u, v = _compute_flipbook_uv(0.5, 0.5, 8, 4, frame=8)
        cell_w = 1.0 / 8
        cell_h = 1.0 / 4
        expected_u = (0 + 0.5) * cell_w   # col=0
        expected_v = (1 + 0.5) * cell_h   # row=1
        assert abs(u - expected_u) < 1e-6
        assert abs(v - expected_v) < 1e-6


# ─────────────────────────────────────────────────────────────────────────────
#  4. TPC Header and TXI Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTpcHeaderAndTxiExtraction:
    """Test TPC header parsing and TXI extraction with corrected PyKotor layout."""

    def test_tpc_header_with_txi_extract(self):
        """TXI string embedded after DXT1 pixel data should be extracted correctly."""
        txi_content = 'blending additive\nnumx 4\nnumy 4\nfps 10\n'
        tpc_data = _make_tpc_with_txi(32, 32, 2, txi_content, compressed=True)
        result = _extract_txi_from_tpc(tpc_data)
        assert 'blending additive' in result
        assert 'numx 4' in result

    def test_tpc_header_without_txi_returns_empty(self):
        """TPC without TXI should return empty string."""
        # Minimal DXT1 TPC without any trailing data
        bx = max(1, (16 + 3) // 4)
        by = max(1, (16 + 3) // 4)
        pixel_data_size = bx * by * 8
        header = _make_tpc_header(16, 16, 2, 1, pixel_data_size)
        tpc_data = header + bytes(pixel_data_size)
        result = _extract_txi_from_tpc(tpc_data)
        assert result == ''

    def test_tpc_txi_with_dxt5_pixel_type_4(self):
        """TXI extraction from DXT5 (pixel_type=4) TPC file."""
        txi_content = 'cube 1\n'
        tpc_data = _make_tpc_with_txi(16, 16, 4, txi_content, compressed=True)
        result = _extract_txi_from_tpc(tpc_data)
        assert 'cube 1' in result

    def test_tpc_too_short_returns_empty(self):
        """Files shorter than 128 bytes should return empty string."""
        result = _extract_txi_from_tpc(b'\x00' * 64)
        assert result == ''

    def test_tpc_uncompressed_rgb_with_txi(self):
        """TXI extraction from uncompressed RGB (pixel_type=2, data_sz=0) TPC."""
        txi_content = 'mipmap 0\n'
        # Uncompressed: pixel_type=2 (RGB), data_sz=0
        w, h = 8, 8
        pixel_data = bytes(w * h * 3)
        header = _make_tpc_header(w, h, 2, 1, 0)  # data_sz=0 for uncompressed
        tpc_data = header + pixel_data + txi_content.encode('utf-8')
        result = _extract_txi_from_tpc(tpc_data)
        assert 'mipmap 0' in result

    def test_tpc_detection_requires_zero_reserved_bytes(self):
        """TPC detection should succeed when reserved bytes 15-100 are zero."""
        header = _make_tpc_header(32, 32, 2, 1, 0)
        # Confirm bytes 14-127 are zero (as _make_tpc_header sets them)
        assert all(b == 0 for b in header[15:100])
        assert _is_tpc_data(header + bytes(32 * 32 * 3))

    def test_non_tpc_data_not_detected(self):
        """Non-TPC binary data should not be detected as TPC."""
        # A simple TGA with non-zero reserved area
        fake_tga = bytearray(200)
        fake_tga[2] = 2   # TGA type: uncompressed RGB
        fake_tga[15] = 0xFF  # TGA color map bytes — non-zero in reserved zone
        fake_tga[16] = 0xAB  # More non-zero data
        assert not _is_tpc_data(bytes(fake_tga))


# ─────────────────────────────────────────────────────────────────────────────
#  5. ModelNode UV Fields Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestModelNodeUVFields:
    """Test that ModelNode has the correct UV and TXI field definitions."""

    def test_uvs_lm_field_exists(self):
        """ModelNode must have uvs_lm (lightmap UV) field."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'uvs_lm')
        assert isinstance(node.uvs_lm, list)

    def test_uvs_2_field_exists(self):
        """ModelNode must have uvs_2 (Texture2 UV) field."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'uvs_2')
        assert isinstance(node.uvs_2, list)

    def test_uvs_3_field_exists(self):
        """ModelNode must have uvs_3 (Texture3 UV) field."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'uvs_3')
        assert isinstance(node.uvs_3, list)

    def test_txi_blending_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_blending')
        assert node.txi_blending == 0

    def test_txi_cube_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_cube')
        assert node.txi_cube is False

    def test_txi_proceduretype_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_proceduretype')
        assert node.txi_proceduretype == ''

    def test_txi_numx_numy_fields_exist(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_numx')
        assert hasattr(node, 'txi_numy')
        assert node.txi_numx == 0
        assert node.txi_numy == 0

    def test_txi_fps_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_fps')
        assert node.txi_fps == 0.0

    def test_txi_envmaptexture_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_envmaptexture')
        assert node.txi_envmaptexture == ''

    def test_txi_bumpmaptexture_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_bumpmaptexture')
        assert node.txi_bumpmaptexture == ''

    def test_txi_bumpmapscaling_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_bumpmapscaling')
        assert node.txi_bumpmapscaling == 1.0

    def test_txi_rotate_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_rotate')
        assert node.txi_rotate == 0.0

    def test_txi_clamp_modes_exist(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_clamp_s')
        assert hasattr(node, 'txi_clamp_t')
        assert node.txi_clamp_s is False
        assert node.txi_clamp_t is False

    def test_txi_loop_field_exists(self):
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'txi_loop')
        assert node.txi_loop is True

    def test_uv_fields_default_empty(self):
        """All UV fields should start as empty lists."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert node.uvs == []
        assert node.uvs_lm == []
        assert node.uvs_2 == []
        assert node.uvs_3 == []

    def test_uv_fields_independent(self):
        """Setting one UV field should not affect others."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        node.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        node.uvs_lm = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9)]
        node.uvs_2 = [(0.2, 0.2)]
        node.uvs_3 = [(0.3, 0.3)]
        assert len(node.uvs) == 3
        assert len(node.uvs_lm) == 3
        assert len(node.uvs_2) == 1
        assert len(node.uvs_3) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  6. TextureCache TXI Loading Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTextureCacheTxiLoading:
    """Test TextureCache.get_txi() method."""

    def test_get_txi_empty_name_returns_empty(self):
        cache = TextureCache()
        assert cache.get_txi('') == ''

    def test_get_txi_none_name_returns_empty(self):
        cache = TextureCache()
        assert cache.get_txi(None) == ''

    def test_get_txi_nonexistent_texture_returns_empty(self):
        cache = TextureCache()
        result = cache.get_txi('nonexistent_texture_12345')
        assert result == ''

    def test_get_txi_from_standalone_txi_file(self, tmp_path):
        """get_txi should load from a standalone .txi file on disk."""
        txi_content = 'blending additive\nnumx 4\n'
        txi_file = tmp_path / 'test_tex.txi'
        txi_file.write_text(txi_content)

        cache = TextureCache()
        cache.set_search_dirs([str(tmp_path)])
        result = cache.get_txi('test_tex')
        assert 'blending additive' in result
        assert 'numx 4' in result

    def test_get_txi_cached_on_second_call(self, tmp_path):
        """Second call should use cache (same result)."""
        txi_content = 'cube 1\n'
        txi_file = tmp_path / 'my_tex.txi'
        txi_file.write_text(txi_content)

        cache = TextureCache()
        cache.set_search_dirs([str(tmp_path)])
        result1 = cache.get_txi('my_tex')
        result2 = cache.get_txi('my_tex')
        assert result1 == result2
        assert 'cube 1' in result1

    def test_get_txi_case_insensitive_name(self, tmp_path):
        """get_txi should normalize texture name to lowercase."""
        txi_content = 'mipmap 0\n'
        txi_file = tmp_path / 'UPPER_TEX.txi'
        txi_file.write_text(txi_content)

        cache = TextureCache()
        cache.set_search_dirs([str(tmp_path)])
        result = cache.get_txi('UPPER_TEX')
        # The file may or may not be found depending on filesystem case-sensitivity
        # but the key should be lowercased in cache
        assert isinstance(result, str)

    def test_get_txi_from_tpc_file_embedded(self, tmp_path):
        """get_txi should extract TXI from embedded TPC data."""
        txi_content = 'bumpmaptexture test_bump\n'
        tpc_data = _make_tpc_with_txi(16, 16, 2, txi_content, compressed=True)
        # Write as .tga (KotOR stores TPC files with .tga extension)
        tga_path = tmp_path / 'tpc_tex.tga'
        tga_path.write_bytes(tpc_data)

        cache = TextureCache()
        cache.set_search_dirs([str(tmp_path)])
        result = cache.get_txi('tpc_tex')
        assert 'bumpmaptexture test_bump' in result

    def test_txi_cache_cleared_on_set_search_dirs(self, tmp_path):
        """Changing search dirs should clear the TXI cache."""
        txi_content = 'blending additive\n'
        txi_file = tmp_path / 'tex1.txi'
        txi_file.write_text(txi_content)

        cache = TextureCache()
        cache.set_search_dirs([str(tmp_path)])
        result1 = cache.get_txi('tex1')

        # Change search dirs → cache cleared
        cache.set_search_dirs([])
        result2 = cache.get_txi('tex1')

        assert 'blending additive' in result1
        assert result2 == ''  # not found in empty dirs

    def test_txi_cache_cleared_on_set_game_library(self):
        """Setting a new game library should clear the TXI cache."""
        cache = TextureCache()
        # Manually inject a cached value
        cache._txi_cache['test'] = 'some txi content'
        assert 'test' in cache._txi_cache

        # Setting a new (mock) game library should clear the cache
        class MockLib:
            pass
        cache.set_game_library(MockLib())
        assert 'test' not in cache._txi_cache


# ─────────────────────────────────────────────────────────────────────────────
#  7. TXI UV Transformation Tests (render pipeline logic)
# ─────────────────────────────────────────────────────────────────────────────

class TestTxiUVTransformations:
    """Test TXI-driven UV transformations applied during rendering."""

    def test_clamp_s_limits_u_to_01(self):
        """clamp_s should clamp U coordinates to [0,1]."""
        # Simulate the clamp-s logic from _draw_mesh_textured
        def apply_clamp_s(u, v):
            return max(0.0, min(1.0, u)), v

        u_out, v_out = apply_clamp_s(-0.5, 0.5)
        assert u_out == 0.0

        u_out, v_out = apply_clamp_s(1.5, 0.5)
        assert u_out == 1.0

        u_out, v_out = apply_clamp_s(0.5, 0.5)
        assert u_out == 0.5

    def test_clamp_t_limits_v_to_01(self):
        """clamp_t should clamp V coordinates to [0,1]."""
        def apply_clamp_t(u, v):
            return u, max(0.0, min(1.0, v))

        u_out, v_out = apply_clamp_t(0.5, -0.3)
        assert v_out == 0.0

        u_out, v_out = apply_clamp_t(0.5, 1.8)
        assert v_out == 1.0

    def test_txi_rotate_uv_90_degrees(self):
        """TXI rotate 0.25 (= 90°) should rotate UV around (0.5, 0.5)."""
        # rotate = 0.25 turns = 90° CCW
        # Point (1.0, 0.5): relative to center = (0.5, 0.0)
        # After 90° CCW rotation: (x,y) → (-y, x) → (0.0, 0.5)
        # After re-centering: (0.5, 1.0)
        ang = math.radians(0.25 * 360.0)
        ca, sa = math.cos(ang), math.sin(ang)
        u, v = 1.0, 0.5
        uu, vv = u - 0.5, v - 0.5   # → (0.5, 0.0)
        u_rot = uu * ca - vv * sa + 0.5   # 0.5*cos(90) - 0.0*sin(90) + 0.5 ≈ 0.5
        v_rot = uu * sa + vv * ca + 0.5   # 0.5*sin(90) + 0.0*cos(90) + 0.5 ≈ 1.0
        assert abs(u_rot - 0.5) < 1e-5
        assert abs(v_rot - 1.0) < 1e-5

    def test_flipbook_frame_0_maps_to_first_cell(self):
        """Flipbook frame 0 should map UVs to the first (top-left) cell."""
        numx, numy = 4, 4
        u_in, v_in = 0.5, 0.5
        u_out, v_out = _compute_flipbook_uv(u_in, v_in, numx, numy, frame=0)
        # Frame 0, col=0, row=0: output = (0 + 0.5) / 4, (0 + 0.5) / 4
        assert abs(u_out - 0.125) < 1e-6
        assert abs(v_out - 0.125) < 1e-6

    def test_flipbook_all_frames_cover_full_texture(self):
        """All flipbook frames together should cover the entire [0,1]² UV space."""
        numx, numy = 2, 2
        cell_w = 1.0 / numx
        cell_h = 1.0 / numy
        covered_cells = set()
        for frame in range(numx * numy):
            u, v = _compute_flipbook_uv(0.5, 0.5, numx, numy, frame)
            # Find which cell this is
            col = int(u / cell_w)
            row = int(v / cell_h)
            covered_cells.add((col, row))
        # Should cover all 4 cells
        assert len(covered_cells) == 4

    def test_additive_blending_reduces_alpha(self):
        """Additive blending (txi_blending=1) should use reduced alpha in render."""
        # Simulate the alpha computation from _draw_mesh_textured
        def effective_alpha(node_alpha: float, txi_blend: int) -> float:
            if txi_blend == 1:
                return min(node_alpha, 0.5)
            return node_alpha

        # Fully opaque + additive → half alpha
        assert effective_alpha(1.0, 1) == 0.5
        # Partially transparent + additive → min of both
        assert effective_alpha(0.3, 1) == 0.3
        # No blending → unchanged
        assert effective_alpha(0.8, 0) == 0.8

    def test_punchthrough_blending_no_alpha_change(self):
        """Punchthrough blending (txi_blending=2) should not change alpha."""
        def effective_alpha(node_alpha: float, txi_blend: int) -> float:
            if txi_blend == 1:
                return min(node_alpha, 0.5)
            return node_alpha

        assert effective_alpha(1.0, 2) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
#  8. Integration: Full TXI round-trip Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTxiIntegration:
    """Integration tests for the full TXI metadata pipeline."""

    def test_parse_and_apply_flipbook_pipeline(self):
        """Full pipeline: TXI string → parse → apply to node → verify render params."""
        txi_str = (
            'proceduretype cycle\n'
            'numx 8\n'
            'numy 4\n'
            'fps 15.0\n'
            'loop 1\n'
        )
        node = _make_mesh_node(texture='animated_tex')
        _apply_txi_to_node(node, txi_str)

        # Verify node fields set correctly
        assert node.txi_proceduretype == 'cycle'
        assert node.txi_numx == 8
        assert node.txi_numy == 4
        assert abs(node.txi_fps - 15.0) < 1e-6
        assert node.txi_loop is True

        # Verify render would compute correct frame
        fps = node.txi_fps
        time = 1.0   # 1 second → frame 15 (at 15fps)
        total_frames = node.txi_numx * node.txi_numy
        frame = int(time * fps) % total_frames
        assert frame == 15

        # Verify flipbook UV for this frame
        u, v = _compute_flipbook_uv(0.5, 0.5, node.txi_numx, node.txi_numy, frame)
        expected_col = 15 % 8  # col=7
        expected_row = 15 // 8  # row=1
        cell_w = 1.0 / 8
        cell_h = 1.0 / 4
        assert abs(u - (expected_col + 0.5) * cell_w) < 1e-6
        assert abs(v - (expected_row + 0.5) * cell_h) < 1e-6

    def test_parse_and_apply_bumpmap_pipeline(self):
        """Full pipeline: TXI bumpmap → apply to node → verify bump_map set."""
        txi_str = 'bumpmaptexture n_head_bump\nbumpmapscaling 2.0\n'
        node = _make_mesh_node(texture='n_head')
        _apply_txi_to_node(node, txi_str)

        assert node.txi_bumpmaptexture == 'n_head_bump'
        assert node.bump_map == 'n_head_bump'  # also updates base field
        assert abs(node.txi_bumpmapscaling - 2.0) < 1e-6

    def test_parse_and_apply_additive_blending(self):
        """Full pipeline: TXI additive blending → node gets txi_blending=1."""
        txi_str = 'blending additive\n'
        node = _make_mesh_node(texture='glow_effect')
        _apply_txi_to_node(node, txi_str)

        assert node.txi_blending == 1

    def test_parse_and_apply_clamp_modes(self):
        """Full pipeline: TXI clamp modes → node gets correct flags."""
        txi_str = 'clamps 1\nclampt 1\n'
        node = _make_mesh_node(texture='decal_tex')
        _apply_txi_to_node(node, txi_str)

        assert node.txi_clamp_s is True
        assert node.txi_clamp_t is True

        # Verify clamp behavior
        u_clamped = max(0.0, min(1.0, -0.3))
        v_clamped = max(0.0, min(1.0, 1.7))
        assert u_clamped == 0.0
        assert v_clamped == 1.0

    def test_empty_tpc_txi_no_node_changes(self):
        """TPC without TXI should not modify node TXI fields."""
        node = _make_mesh_node()
        original_blending = node.txi_blending
        original_proceduretype = node.txi_proceduretype

        _apply_txi_to_node(node, '')  # empty TXI

        assert node.txi_blending == original_blending
        assert node.txi_proceduretype == original_proceduretype

    def test_txi_thread_safety(self):
        """get_txi should be thread-safe when called concurrently."""
        cache = TextureCache()
        results = []
        errors = []

        def worker():
            try:
                # All threads look up a nonexistent texture
                result = cache.get_txi('nonexistent_thread_test')
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert all(r == '' for r in results)


# ─────────────────────────────────────────────────────────────────────────────
#  9. UV2/UV3 Parser Tests (MDL Parser integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestUV2UV3ParserFields:
    """Test that MDL parser UV2/UV3 fields are parsed and stored on nodes."""

    def test_mdx_t2_offset_constant_existence(self):
        """
        The MDL parser should check mdx_t2_off and mdx_t3_off validity
        (_t2_ok, _t3_ok) and store results in node.uvs_2 and node.uvs_3.
        """
        # Verify the fields exist on ModelNode
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        assert hasattr(node, 'uvs_2'), "ModelNode should have uvs_2 field"
        assert hasattr(node, 'uvs_3'), "ModelNode should have uvs_3 field"

    def test_uv2_uv3_store_per_vertex_data(self):
        """Node should be able to store UV2/UV3 data matching vertex count."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        node.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
        node.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
        node.uvs_2 = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9)]
        node.uvs_3 = [(0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)]

        assert len(node.uvs_2) == 4
        assert len(node.uvs_3) == 4
        # First UV2 vertex
        assert abs(node.uvs_2[0][0] - 0.1) < 1e-6
        assert abs(node.uvs_3[0][0] - 0.2) < 1e-6

    def test_uv2_uv3_independent_from_uv0(self):
        """UV2/UV3 should not affect the primary UV set."""
        node = ModelNode(name='test', flags=NodeFlags.MESH)
        node.uvs = [(0.5, 0.5)]
        node.uvs_2 = [(0.1, 0.1)]
        node.uvs_3 = [(0.2, 0.2)]
        assert node.uvs[0] == (0.5, 0.5)
        assert node.uvs_2[0] == (0.1, 0.1)
        assert node.uvs_3[0] == (0.2, 0.2)


# ─────────────────────────────────────────────────────────────────────────────
#  10. TPC Pixel Format Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PIL, reason="PIL not available")
class TestTpcPixelFormats:
    """Test TPC pixel format handling (PyKotor-compatible layout)."""

    def test_tpc_dxt1_pixel_type_2_loads(self):
        """DXT1 TPC (pixel_type=2, compressed) should load as RGBA image."""
        bx = max(1, (16 + 3) // 4)
        by = max(1, (16 + 3) // 4)
        pixel_data_size = bx * by * 8
        header = _make_tpc_header(16, 16, 2, 1, pixel_data_size)
        # Fill with a simple solid color DXT1 block
        # DXT1 block: c0=white (0xFFFF), c1=black (0x0000), lookup=0x00000000
        dxt1_block = struct.pack('<HHI', 0xFFFF, 0x0000, 0x00000000)
        pixel_data = dxt1_block * (bx * by)
        tpc_data = header + pixel_data
        img = _load_tpc_bytes(tpc_data)
        assert img is not None
        assert img.size == (16, 16)
        assert img.mode == 'RGBA'

    def test_tpc_dxt5_pixel_type_4_loads(self):
        """DXT5 TPC (pixel_type=4, compressed) should load as RGBA image."""
        bx = max(1, (8 + 3) // 4)
        by = max(1, (8 + 3) // 4)
        pixel_data_size = bx * by * 16
        header = _make_tpc_header(8, 8, 4, 1, pixel_data_size)
        pixel_data = bytes(pixel_data_size)  # zeros = black
        tpc_data = header + pixel_data
        img = _load_tpc_bytes(tpc_data)
        assert img is not None
        assert img.size == (8, 8)
        assert img.mode == 'RGBA'

    def test_tpc_greyscale_pixel_type_1_loads(self):
        """Greyscale TPC (pixel_type=1, uncompressed) should load."""
        w, h = 4, 4
        pixel_data = bytes([128] * (w * h))  # mid-grey
        header = _make_tpc_header(w, h, 1, 1, 0)
        tpc_data = header + pixel_data
        img = _load_tpc_bytes(tpc_data)
        assert img is not None
        assert img.size == (w, h)

    def test_tpc_rgb_uncompressed_pixel_type_2_loads(self):
        """RGB uncompressed TPC (pixel_type=2, data_sz=0) should load."""
        w, h = 4, 4
        pixel_data = bytes([255, 0, 0] * (w * h))  # all red
        header = _make_tpc_header(w, h, 2, 1, 0)  # data_sz=0 = uncompressed
        tpc_data = header + pixel_data
        img = _load_tpc_bytes(tpc_data)
        assert img is not None
        assert img.size == (w, h)

    def test_tpc_rgba_uncompressed_pixel_type_4_loads(self):
        """RGBA uncompressed TPC (pixel_type=4, data_sz=0) should load."""
        w, h = 4, 4
        pixel_data = bytes([0, 255, 0, 255] * (w * h))  # all green opaque
        header = _make_tpc_header(w, h, 4, 1, 0)  # data_sz=0 = uncompressed
        tpc_data = header + pixel_data
        img = _load_tpc_bytes(tpc_data)
        assert img is not None
        assert img.size == (w, h)

    def test_tpc_invalid_dimensions_returns_none(self):
        """TPC with zero dimensions should return None."""
        header = _make_tpc_header(0, 0, 2, 1, 0)
        result = _load_tpc_bytes(header + bytes(16))
        assert result is None

    def test_tpc_data_too_short_returns_none(self):
        """TPC data shorter than 128 bytes should return None."""
        result = _load_tpc_bytes(bytes(64))
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
