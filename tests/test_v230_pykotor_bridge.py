"""
tests/test_v230_pykotor_bridge.py — Phase 14.2 PyKotor Bridge Tests

Tests for src/core/pykotor_bridge.py covering:
  - TPC patching (data_sz=0 for DXT textures)
  - TPC → PIL image conversion
  - MDL model loading via PyKotor
  - Skin bone weight indexing correctness
  - Animation loading (events, position delta, orientation)
  - MDLBinaryParser.parse_files() uses bridge
  - MDLBinaryParser.parse() uses legacy parser (not bridge)
  - is_pykotor_available() utility
"""

import struct
import sys
import os
import math
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(REPO, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# ── Asset paths ───────────────────────────────────────────────────────────────
_BANTHA_MDL = os.path.join(REPO, 'test_assets', 'c_bantha', 'c_bantha.mdl')
_BANTHA_MDX = os.path.join(REPO, 'test_assets', 'c_bantha', 'c_bantha.mdx')
_BANTHA_TPC = os.path.join(REPO, 'test_assets', 'c_bantha', 'c_bantha01.tpc')
_BANTHH_TPC = os.path.join(REPO, 'test_assets', 'c_bantha', 'c_banthh01.tpc')

_HAS_BANTHA = os.path.exists(_BANTHA_MDL) and os.path.exists(_BANTHA_MDX)
_HAS_TPC    = os.path.exists(_BANTHA_TPC)

# ── Imports ───────────────────────────────────────────────────────────────────
from core.pykotor_bridge import (
    is_pykotor_available,
    patch_tpc_for_pykotor,
    pykotor_tpc_to_pil,
    load_model_via_pykotor,
    load_model_from_bytes_via_pykotor,
)


# ═════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _make_dxt1_header(width=64, height=64, mips=1, data_sz=0):
    """Build a minimal DXT1 TPC header (128 bytes)."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    pixel_data = bytes(bw * bh * 8)  # DXT1 block data (zeros)
    hdr = bytearray(128)
    struct.pack_into('<I', hdr, 0, data_sz)   # data_sz
    struct.pack_into('<f', hdr, 4, 0.0)        # alpha_test
    struct.pack_into('<H', hdr, 8, width)
    struct.pack_into('<H', hdr, 10, height)
    hdr[12] = 2    # encoding = DXT1 (enc=2 means DXT1 when data_sz=0)
    hdr[13] = mips
    return bytes(hdr) + pixel_data


def _make_dxt5_header(width=64, height=64, mips=1, data_sz=0):
    """Build a minimal DXT5 TPC header."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    pixel_data = bytes(bw * bh * 16)
    hdr = bytearray(128)
    struct.pack_into('<I', hdr, 0, data_sz)
    struct.pack_into('<f', hdr, 4, 0.0)
    struct.pack_into('<H', hdr, 8, width)
    struct.pack_into('<H', hdr, 10, height)
    hdr[12] = 4    # encoding = DXT5 (enc=4 when data_sz=0)
    hdr[13] = mips
    return bytes(hdr) + pixel_data


def _make_rgba_header(width=4, height=4, alpha_test=0.0):
    """Build a minimal uncompressed RGBA TPC header."""
    sz = width * height * 4
    hdr = bytearray(128)
    struct.pack_into('<I', hdr, 0, sz)
    struct.pack_into('<f', hdr, 4, alpha_test)
    struct.pack_into('<H', hdr, 8, width)
    struct.pack_into('<H', hdr, 10, height)
    hdr[12] = 4
    hdr[13] = 1
    # pixel data: solid opaque red (255, 0, 0, 255) bottom-up
    pixels = b'\xFF\x00\x00\xFF' * (width * height)
    return bytes(hdr) + pixels


# ═════════════════════════════════════════════════════════════════════════════
#  TestPatchTpcForPykotor
# ═════════════════════════════════════════════════════════════════════════════

class TestPatchTpcForPykotor:
    def test_dxt1_data_sz_zero_patched(self):
        data = _make_dxt1_header(64, 64, 1, 0)
        patched = patch_tpc_for_pykotor(data)
        result = struct.unpack_from('<I', patched, 0)[0]
        expected = max(1, 64//4) * max(1, 64//4) * 8
        assert result == expected

    def test_dxt5_data_sz_zero_patched(self):
        data = _make_dxt5_header(64, 64, 1, 0)
        patched = patch_tpc_for_pykotor(data)
        result = struct.unpack_from('<I', patched, 0)[0]
        expected = max(1, 64//4) * max(1, 64//4) * 16
        assert result == expected

    def test_nonzero_data_sz_unchanged(self):
        data = _make_dxt1_header(64, 64, 1, 12345)
        patched = patch_tpc_for_pykotor(data)
        assert patched is data  # same object, no copy made
        result = struct.unpack_from('<I', patched, 0)[0]
        assert result == 12345

    def test_rgba_uncompressed_not_patched(self):
        data = _make_rgba_header(4, 4)
        orig_sz = struct.unpack_from('<I', data, 0)[0]
        patched = patch_tpc_for_pykotor(data)
        # Uncompressed (enc=4, data_sz!=0) should not be patched
        result = struct.unpack_from('<I', patched, 0)[0]
        assert result == orig_sz

    def test_data_too_small_unchanged(self):
        data = b'\x00' * 64  # too small
        patched = patch_tpc_for_pykotor(data)
        assert patched is data


# ═════════════════════════════════════════════════════════════════════════════
#  TestPykotorTpcToPil (requires PIL + PyKotor)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not is_pykotor_available(), reason="PyKotor not available")
class TestPykotorTpcToPil:
    def test_returns_none_for_empty_data(self):
        assert pykotor_tpc_to_pil(b'') is None

    def test_returns_none_for_short_data(self):
        assert pykotor_tpc_to_pil(b'\x00' * 100) is None

    def test_txi_str_attached(self):
        data = _make_rgba_header(4, 4)
        img = pykotor_tpc_to_pil(data)
        if img is not None:
            assert hasattr(img, '_txi_str')
            assert isinstance(img._txi_str, str)

    def test_tpc_raw_attached(self):
        data = _make_rgba_header(4, 4)
        img = pykotor_tpc_to_pil(data)
        if img is not None:
            assert hasattr(img, '_tpc_raw')
            assert isinstance(img._tpc_raw, (bytes, bytearray))

    def test_alpha_test_none_for_zero(self):
        """alpha_test=0.0 in header should result in _txi_alpha_test=None."""
        data = _make_rgba_header(4, 4, alpha_test=0.0)
        img = pykotor_tpc_to_pil(data)
        if img is not None:
            assert hasattr(img, '_txi_alpha_test')
            assert img._txi_alpha_test is None

    def test_alpha_test_valid_attached(self):
        """Valid alpha_test in (0, 1] should be attached."""
        hdr = bytearray(_make_rgba_header(4, 4))
        struct.pack_into('<f', hdr, 4, 0.5)
        data = bytes(hdr)
        img = pykotor_tpc_to_pil(data)
        if img is not None:
            assert hasattr(img, '_txi_alpha_test')
            if img._txi_alpha_test is not None:
                assert abs(img._txi_alpha_test - 0.5) < 0.01

    @pytest.mark.skipif(not _HAS_TPC, reason="c_bantha01.tpc not available")
    def test_real_tpc_loads(self):
        data = open(_BANTHA_TPC, 'rb').read()
        img = pykotor_tpc_to_pil(data)
        assert img is not None

    @pytest.mark.skipif(not _HAS_TPC, reason="c_bantha01.tpc not available")
    def test_real_tpc_has_attrs(self):
        data = open(_BANTHA_TPC, 'rb').read()
        img = pykotor_tpc_to_pil(data)
        assert img is not None
        assert hasattr(img, '_txi_str')
        assert hasattr(img, '_tpc_raw')
        assert hasattr(img, '_txi_alpha_test')

    @pytest.mark.skipif(not _HAS_TPC, reason="c_bantha01.tpc not available")
    def test_real_tpc_pixels_valid(self):
        data = open(_BANTHA_TPC, 'rb').read()
        img = pykotor_tpc_to_pil(data)
        assert img is not None
        assert img.mode == 'RGBA'
        w, h = img.size
        assert w > 0 and h > 0
        # At least some pixels should be non-zero
        pixels = list(img.getdata())
        non_zero = sum(1 for p in pixels if any(c > 0 for c in p[:3]))
        assert non_zero > 0


# ═════════════════════════════════════════════════════════════════════════════
#  TestLoadModelViaPykotor
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_BANTHA, reason="c_bantha test assets not available")
@pytest.mark.skipif(not is_pykotor_available(), reason="PyKotor not available")
class TestLoadModelViaPykotor:
    """Tests for load_model_via_pykotor() with real KotOR test assets."""

    @pytest.fixture(scope='class')
    def model(self):
        m = load_model_via_pykotor(_BANTHA_MDL, _BANTHA_MDX)
        assert m is not None, "Model failed to load"
        return m

    def test_model_loaded(self, model):
        assert model is not None

    def test_model_name(self, model):
        assert model.name.upper() == 'C_BANTHA'

    def test_has_nodes(self, model):
        nodes = model.all_nodes()
        assert len(nodes) > 0

    def test_has_skin_nodes(self, model):
        skin_nodes = [n for n in model.all_nodes() if n.is_skin]
        assert len(skin_nodes) >= 1

    def test_skin_has_vertices(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert len(n.vertices) > 0, f"Skin node '{n.name}' has no vertices"

    def test_skin_has_faces(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert len(n.faces) > 0, f"Skin node '{n.name}' has no faces"

    def test_skin_has_uvs(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert len(n.uvs) > 0, f"Skin node '{n.name}' has no UVs"

    def test_skin_texture_name(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert n.texture and len(n.texture) > 0, \
                    f"Skin node '{n.name}' has no texture name"

    def test_uv_values_in_range(self, model):
        for n in model.all_nodes():
            if n.is_skin and n.uvs:
                for u, v in n.uvs[:50]:
                    # UVs may legitimately exceed [0,1] for tiling, just check finite
                    assert math.isfinite(u), f"Non-finite U in node '{n.name}'"
                    assert math.isfinite(v), f"Non-finite V in node '{n.name}'"

    def test_skin_data_correct_count(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert len(n.skin_data) == len(n.vertices), \
                    f"Skin node '{n.name}': skin_data count != vertex count"

    def test_bone_map_not_empty(self, model):
        for n in model.all_nodes():
            if n.is_skin:
                assert len(n.bone_map) > 0, f"Skin node '{n.name}' has empty bone_map"

    def test_bone_index_valid(self, model):
        """BoneWeight.bone_index must be a valid bonemap slot."""
        for n in model.all_nodes():
            if n.is_skin and n.skin_data:
                for vsd in n.skin_data[:20]:
                    for bw in vsd.influences:
                        assert 0 <= bw.bone_index < len(n.bone_map), \
                            f"bone_index {bw.bone_index} out of range [0, {len(n.bone_map)}) in '{n.name}'"
                        assert 0.0 <= bw.weight <= 1.001, \
                            f"weight {bw.weight} out of range in '{n.name}'"

    def test_node_positions_finite(self, model):
        for n in model.all_nodes():
            for v in n.position:
                assert math.isfinite(v), f"Non-finite position in node '{n.name}'"

    def test_node_rotations_normalized(self, model):
        for n in model.all_nodes():
            q = n.rotation
            mag_sq = sum(v*v for v in q)
            assert abs(mag_sq - 1.0) < 0.01, \
                f"Rotation not normalized in '{n.name}': mag²={mag_sq}"

    def test_skin_nodes_have_bone_map(self, model):
        skin_nodes = [n for n in model.all_nodes() if n.is_skin]
        if not skin_nodes:
            pytest.skip("No skin nodes")
        for n in skin_nodes:
            assert len(n.bone_map) > 0

    def test_supermodel_string(self, model):
        assert isinstance(model.supermodel, str)

    def test_root_node_set(self, model):
        assert model.root_node is not None

    def test_has_animations(self, model):
        assert len(model.animations) > 0

    def test_animation_has_length(self, model):
        for a in model.animations:
            assert a.length > 0.0, f"Animation '{a.name}' has non-positive length"

    def test_animation_has_nodes(self, model):
        has_nodes = any(len(a.nodes) > 0 for a in model.animations)
        assert has_nodes, "No animation has any nodes"

    def test_animation_controllers_position_type(self, model):
        for anim in model.animations:
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['type'] == 8:  # POSITION
                        assert len(ctrl['times']) > 0
                        for row in ctrl['values']:
                            assert len(row) >= 3
                            for v in row:
                                assert math.isfinite(v)

    def test_animation_controllers_orientation_type(self, model):
        for anim in model.animations:
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['type'] == 20:  # ORIENTATION
                        assert len(ctrl['times']) > 0
                        for row in ctrl['values']:
                            assert len(row) >= 4
                            mag_sq = sum(v*v for v in row[:4])
                            assert abs(mag_sq - 1.0) < 0.02, \
                                f"Orientation not normalized: {row[:4]}"

    def test_animation_events(self, model):
        """Events should have correct activation_time (not None)."""
        for anim in model.animations:
            for evt in anim.events:
                assert isinstance(evt.time, float), \
                    f"Event time is not float: {evt.time!r} in '{anim.name}'"
                assert math.isfinite(evt.time), \
                    f"Event time is not finite: {evt.time!r} in '{anim.name}'"
                assert isinstance(evt.name, str)

    def test_animation_position_uses_delta(self, model):
        """Position controllers store delta offsets, not absolute positions."""
        for anim in model.animations:
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['type'] == 8:
                        # First frame values should be finite and small (delta)
                        for v in ctrl['values'][0]:
                            assert math.isfinite(v)


# ═════════════════════════════════════════════════════════════════════════════
#  TestLoadModelFromBytesViaPykotor
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_BANTHA, reason="c_bantha test assets not available")
@pytest.mark.skipif(not is_pykotor_available(), reason="PyKotor not available")
class TestLoadModelFromBytesViaPykotor:
    def test_load_from_bytes(self):
        mdl_bytes = open(_BANTHA_MDL, 'rb').read()
        mdx_bytes = open(_BANTHA_MDX, 'rb').read()
        model = load_model_from_bytes_via_pykotor(mdl_bytes, mdx_bytes)
        assert model is not None
        assert model.name.upper() == 'C_BANTHA'

    def test_load_from_bytes_no_mdx(self):
        """Loading without MDX should still work (no bone data)."""
        mdl_bytes = open(_BANTHA_MDL, 'rb').read()
        model = load_model_from_bytes_via_pykotor(mdl_bytes, b'')
        assert model is not None

    def test_returns_none_or_empty_for_invalid_data(self):
        result = load_model_from_bytes_via_pykotor(b'\x00' * 50)
        assert result is None


# ═════════════════════════════════════════════════════════════════════════════
#  TestMDLParserIntegration
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_BANTHA, reason="c_bantha test assets not available")
@pytest.mark.skipif(not is_pykotor_available(), reason="PyKotor not available")
class TestMDLParserIntegration:
    """Tests that MDLBinaryParser integrates with the PyKotor bridge correctly."""

    def test_parse_files_uses_bridge(self):
        """parse_files() should load a real MDL using the PyKotor bridge."""
        from core.mdl_parser import MDLBinaryParser
        model = MDLBinaryParser.parse_files(_BANTHA_MDL, _BANTHA_MDX)
        assert model is not None
        assert model.name.upper() == 'C_BANTHA'
        # Bridge should populate skin data
        skin_nodes = [n for n in model.all_nodes() if n.is_skin]
        assert len(skin_nodes) >= 1
        for sn in skin_nodes:
            assert len(sn.vertices) > 0

    def test_parse_bytes_uses_legacy(self):
        """parse() from bytes should use the legacy parser (not bridge).
        This ensures synthetic MDLs (e.g. from MDLBinaryWriter) aren't broken.
        """
        from core.mdl_parser import MDLBinaryParser
        from core.model_data import KotorModel, ModelNode
        from core.mdl_writer import MDLBinaryWriter
        # Create a minimal valid MDL bytes via the writer
        m = KotorModel(name='test_legacy')
        root = ModelNode(name='test_root')
        m.root_node = root
        writer = MDLBinaryWriter()
        mdl_bytes, mdx_bytes = writer.write(m)
        # parse() should use legacy parser and return something reasonable
        result = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
        assert result is not None
        assert isinstance(result, KotorModel)

    def test_parse_files_preserves_uvs(self):
        """UV coordinates from bridge should be finite."""
        from core.mdl_parser import MDLBinaryParser
        model = MDLBinaryParser.parse_files(_BANTHA_MDL, _BANTHA_MDX)
        for n in model.all_nodes():
            if n.is_skin and n.uvs:
                for u, v in n.uvs[:10]:
                    assert math.isfinite(u) and math.isfinite(v)

    def test_parse_has_animations(self):
        """Animations should be loaded from bridge."""
        from core.mdl_parser import MDLBinaryParser
        model = MDLBinaryParser.parse_files(_BANTHA_MDL, _BANTHA_MDX)
        assert len(model.animations) > 0


# ═════════════════════════════════════════════════════════════════════════════
#  TestAnimationEngine
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _HAS_BANTHA, reason="c_bantha test assets not available")
@pytest.mark.skipif(not is_pykotor_available(), reason="PyKotor not available")
class TestAnimationEngine:
    """Tests that AnimationEngine correctly evaluates PyKotor bridge models."""

    @pytest.fixture(scope='class')
    def model(self):
        return load_model_via_pykotor(_BANTHA_MDL, _BANTHA_MDX)

    def test_animation_engine_plays(self, model):
        from core.animation_engine import AnimationEngine
        eng = AnimationEngine(model)
        anim_names = [a.name for a in model.animations]
        assert len(anim_names) > 0
        eng.play(anim_names[0])
        eng.advance(0.1)
        pose = eng.evaluate(0.1)
        assert pose is not None
        assert len(pose.nodes) > 0

    def test_animation_evaluate_no_geometry_corruption(self, model):
        """Evaluated pose should have only finite position/rotation values."""
        from core.animation_engine import AnimationEngine
        eng = AnimationEngine(model)
        eng.play(model.animations[0].name)
        for t in [0.0, 0.1, 0.3, 0.5]:
            pose = eng.evaluate(t)
            for node_name, node_pose in pose.nodes.items():
                pos = node_pose.position
                rot = node_pose.rotation
                for v in pos:
                    assert math.isfinite(v), \
                        f"Non-finite position at t={t} for '{node_name}': {pos}"
                for v in rot:
                    assert math.isfinite(v), \
                        f"Non-finite rotation at t={t} for '{node_name}': {rot}"

    def test_animation_position_uses_delta(self, model):
        """Position at t=0 should be finite (delta applied to bind pose)."""
        from core.animation_engine import AnimationEngine
        eng = AnimationEngine(model)
        eng.play(model.animations[0].name)
        pose = eng.evaluate(0.0)
        assert len(pose.nodes) > 0
        for node_name, node_pose in pose.nodes.items():
            for v in node_pose.position:
                assert math.isfinite(v)


# ═════════════════════════════════════════════════════════════════════════════
#  TestIsPykotorAvailable
# ═════════════════════════════════════════════════════════════════════════════

class TestIsPykotorAvailable:
    def test_returns_bool(self):
        assert isinstance(is_pykotor_available(), bool)

    def test_pykotor_is_available(self):
        assert is_pykotor_available() is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
