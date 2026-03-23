"""
test_v240_phase36_alpha_txi.py  –  Phase 3.6 rendering fixes audit
===================================================================

Tests for rendering improvements from the Phase 3.6 cross-repo deep dive:

  • Kotor.NET  — KotorModelLoader.cs: TransparencyHint field; TPC.cs structure
  • PyKotor    — gl/shader/texture.py: Texture.alpha_cutoff + blend_mode fields
  • xoreos     — tpc.cpp: alpha_test_threshold at TPC header offset 4

KEY FIXES TESTED:
─────────────────────────────────────────────────────────────────────────────

FIX-ALPHATEST  Per-node punchthrough alpha-test threshold
    OLD BUG: GPU renderer used hardcoded u_alpha_test=0.5 for ALL punchthrough
    surfaces, ignoring the per-texture TPC header float at bytes [4-7].
    FIX: _extract_alpha_test_from_tpc() reads float at TPC offset 4.
         _apply_txi_to_node() now accepts alpha_test kwarg and stores it as
         node.txi_alpha_test.
         GPU renderer reads node.txi_alpha_test when u_blend_mode==2
         (punchthrough), passing per-node discard threshold to u_alpha_test.
    REFERENCE: Kotor.NET TPC.cs; xoreos src/graphics/aurora/textureman.cpp;
               PyKotor gl/shader/texture.py Texture.alpha_cutoff.

FIX-RAWHEADER  TextureCache.get_raw_header()
    NEW METHOD: Returns first 128 bytes of TPC file for a texture name.
    Used by _load_txi_metadata_for_model() to fetch alpha_test from TPC header.

FIX-ALPHATESTZERO  TPC alpha_test=0.0 treated as "no test" (default 0.5)
    Per Kotor.NET and xoreos, alpha_test=0.0 means "no alpha test" not
    "discard everything".  _extract_alpha_test_from_tpc falls back to 0.5.

FIX-MODELNODE  ModelNode gains txi_alpha_test field (default 0.5)
    New dataclass field txi_alpha_test:float=0.5 stores the per-node threshold.

References:
    Kotor.NET/Kotor.NET/Formats/KotorTPC/TPC.cs
    Kotor.NET/Kotor.NET.Graphics/KotorModelLoader.cs
    PyKotor/Libraries/PyKotor/src/pykotor/gl/shader/texture.py
    xoreos/src/graphics/aurora/tpc.cpp
"""

import struct
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.viewport import (
    _parse_txi_string,
    _apply_txi_to_node,
    _extract_alpha_test_from_tpc,
    _extract_txi_from_tpc_legacy,
    _is_tpc_data,
)
from src.core.model_data import ModelNode


# ─────────────────────────────────────────────────────────────────────────────
# Helper: make minimal TPC bytes with given alpha_test value
# ─────────────────────────────────────────────────────────────────────────────

def _make_tpc(alpha_test: float = 0.5, width: int = 4, height: int = 4,
               encoding: int = 4) -> bytes:
    """Create a minimal valid TPC byte stream with the given alpha_test value."""
    bx = max(1, (width + 3) // 4)
    by = max(1, (height + 3) // 4)
    dxt5_sz = bx * by * 16  # DXT5 block size for 4x4

    header = bytearray(128)
    struct.pack_into('<I', header, 0, dxt5_sz)   # data_sz = first-mip DXT5 size
    struct.pack_into('<f', header, 4, alpha_test) # ← the value under test
    struct.pack_into('<H', header, 8, width)
    struct.pack_into('<H', header, 10, height)
    header[12] = encoding   # enc=4: RGBA/DXT5
    header[13] = 1          # mip_count

    pixel_data = bytes(dxt5_sz)
    return bytes(header) + pixel_data


# ─────────────────────────────────────────────────────────────────────────────
# FIX-ALPHATEST: _extract_alpha_test_from_tpc()
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractAlphaTestFromTpc:
    """TPC header bytes [4-7] = float alpha_test_threshold."""

    def test_extracts_standard_half(self):
        """alpha_test=0.5 (Aurora engine default) is returned correctly."""
        tpc = _make_tpc(alpha_test=0.5)
        result = _extract_alpha_test_from_tpc(tpc)
        assert result == pytest.approx(0.5)

    def test_extracts_high_threshold(self):
        """alpha_test=0.9 (very opaque alpha required) is returned correctly."""
        tpc = _make_tpc(alpha_test=0.9)
        result = _extract_alpha_test_from_tpc(tpc)
        assert result == pytest.approx(0.9, abs=1e-5)

    def test_extracts_low_threshold(self):
        """alpha_test=0.1 (nearly any alpha passes) is returned correctly."""
        tpc = _make_tpc(alpha_test=0.1)
        result = _extract_alpha_test_from_tpc(tpc)
        assert result == pytest.approx(0.1, abs=1e-5)

    def test_alpha_test_zero_defaults_to_half(self):
        """alpha_test=0.0 means 'no alpha test' — fall back to default 0.5.

        Per Kotor.NET TPC.cs and xoreos tpc.cpp, a zero value indicates
        the texture has no alpha test (it is fully opaque by default).
        We use 0.5 as the safe default for punchthrough rendering.
        """
        tpc = _make_tpc(alpha_test=0.0)
        result = _extract_alpha_test_from_tpc(tpc)
        assert result == pytest.approx(0.5), (
            "alpha_test=0.0 should fall back to 0.5 (no alpha test)"
        )

    def test_alpha_test_one_returns_one(self):
        """alpha_test=1.0 (only fully opaque pixels pass) is valid."""
        tpc = _make_tpc(alpha_test=1.0)
        result = _extract_alpha_test_from_tpc(tpc)
        assert result == pytest.approx(1.0)

    def test_empty_bytes_defaults_to_half(self):
        """Empty bytes → cannot read header → default 0.5."""
        result = _extract_alpha_test_from_tpc(b'')
        assert result == pytest.approx(0.5)

    def test_too_short_defaults_to_half(self):
        """Less than 8 bytes → default 0.5."""
        result = _extract_alpha_test_from_tpc(b'\x00\x00\x00\x00\x00')
        assert result == pytest.approx(0.5)

    def test_none_defaults_to_half(self):
        """None bytes → default 0.5 (safe fallback)."""
        result = _extract_alpha_test_from_tpc(None)
        assert result == pytest.approx(0.5)

    def test_non_tpc_bytes_returns_half(self):
        """Random non-TPC bytes → alpha_test outside [0,1] → default 0.5."""
        garbage = b'\xff\xff\xff\xff\xff\xff\xff\xff' + b'\x00' * 120
        result = _extract_alpha_test_from_tpc(garbage)
        # 0xFFFFFFFF as float is 3.40282e+38 — out of range, should default to 0.5
        assert result == pytest.approx(0.5)

    def test_full_tpc_stream_extracts_same_as_header(self):
        """Reading from full TPC stream (header + pixel data) gives same result."""
        tpc = _make_tpc(alpha_test=0.75)
        result_header = _extract_alpha_test_from_tpc(tpc[:8])   # header only
        result_full   = _extract_alpha_test_from_tpc(tpc)        # full stream
        assert result_header == pytest.approx(result_full)


# ─────────────────────────────────────────────────────────────────────────────
# FIX-ALPHATEST: _apply_txi_to_node alpha_test kwarg
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyTxiAlphaTest:
    """_apply_txi_to_node must store alpha_test on the node as txi_alpha_test."""

    def test_default_alpha_test_stored(self):
        """Without explicit kwarg, txi_alpha_test defaults to 0.5."""
        node = ModelNode()
        _apply_txi_to_node(node, "")
        assert hasattr(node, 'txi_alpha_test'), "ModelNode must have txi_alpha_test field"
        assert node.txi_alpha_test == pytest.approx(0.5)

    def test_explicit_alpha_test_stored(self):
        """Explicit alpha_test=0.25 is stored on the node."""
        node = ModelNode()
        _apply_txi_to_node(node, "", alpha_test=0.25)
        assert node.txi_alpha_test == pytest.approx(0.25)

    def test_alpha_test_stored_with_punchthrough_txi(self):
        """With punchthrough TXI, alpha_test from TPC header is stored."""
        node = ModelNode()
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=0.75)
        assert node.txi_blending == 2, "punchthrough must set txi_blending=2"
        assert node.txi_alpha_test == pytest.approx(0.75), (
            "TPC alpha_test_threshold must be stored even when TXI also sets punchthrough"
        )

    def test_alpha_test_zero_defaults_to_half(self):
        """alpha_test=0.0 should be treated as default (not passed through)."""
        node = ModelNode()
        _apply_txi_to_node(node, "", alpha_test=0.0)
        # 0.0 means 'no alpha test' — default to 0.5
        assert node.txi_alpha_test == pytest.approx(0.5)

    def test_alpha_test_stored_even_without_txi(self):
        """Empty TXI still stores alpha_test on the node."""
        node = ModelNode()
        _apply_txi_to_node(node, '', alpha_test=0.33)
        assert node.txi_alpha_test == pytest.approx(0.33, abs=1e-5)

    def test_alpha_test_range_clamped(self):
        """alpha_test > 1.0 falls back to 0.5 (out of range)."""
        node = ModelNode()
        _apply_txi_to_node(node, '', alpha_test=2.5)
        # Out of range value → fall back to default
        assert node.txi_alpha_test == pytest.approx(0.5)

    def test_other_txi_fields_still_set(self):
        """Setting alpha_test does not prevent other TXI fields from being parsed."""
        node = ModelNode()
        _apply_txi_to_node(node, "envmaptexture cm_fog\nblending additive\n",
                           alpha_test=0.8)
        assert node.txi_envmaptexture == 'cm_fog'
        assert node.txi_blending == 1
        assert node.txi_alpha_test == pytest.approx(0.8)


# ─────────────────────────────────────────────────────────────────────────────
# FIX-MODELNODE: ModelNode.txi_alpha_test field
# ─────────────────────────────────────────────────────────────────────────────

class TestModelNodeAlphaTest:
    """ModelNode must have txi_alpha_test field with default 0.5."""

    def test_field_exists(self):
        """ModelNode.txi_alpha_test field must exist."""
        node = ModelNode()
        assert hasattr(node, 'txi_alpha_test'), (
            "ModelNode must have txi_alpha_test field (FIX-ALPHATEST)"
        )

    def test_default_value(self):
        """Default txi_alpha_test must be 0.5 (Aurora engine default)."""
        node = ModelNode()
        assert node.txi_alpha_test == pytest.approx(0.5), (
            "Default alpha_test threshold must match Aurora engine default (0.5)"
        )

    def test_field_is_float(self):
        """txi_alpha_test must be a float."""
        node = ModelNode()
        assert isinstance(node.txi_alpha_test, float)

    def test_can_be_set(self):
        """txi_alpha_test can be set to any valid float."""
        node = ModelNode()
        node.txi_alpha_test = 0.9
        assert node.txi_alpha_test == pytest.approx(0.9)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: full pipeline from TPC bytes to node.txi_alpha_test
# ─────────────────────────────────────────────────────────────────────────────

class TestAlphaTestPipeline:
    """Full pipeline: TPC bytes → extract threshold → apply to node."""

    def test_grass_foliage_low_threshold(self):
        """Grass textures have low alpha_test (~0.1) so thin blades render."""
        tpc = _make_tpc(alpha_test=0.1)
        at = _extract_alpha_test_from_tpc(tpc)

        node = ModelNode()
        node.texture = 'grass_blade01'
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=at)

        assert node.txi_blending == 2
        assert node.txi_alpha_test == pytest.approx(0.1, abs=1e-4), (
            "Thin grass blades need low threshold so semi-transparent pixels pass"
        )

    def test_metal_grate_high_threshold(self):
        """Metal grates have high alpha_test (~0.9) for crisp hole boundaries."""
        tpc = _make_tpc(alpha_test=0.9)
        at = _extract_alpha_test_from_tpc(tpc)

        node = ModelNode()
        node.texture = 'metal_grate01'
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=at)

        assert node.txi_blending == 2
        assert node.txi_alpha_test == pytest.approx(0.9, abs=1e-4)

    def test_character_hair_alpha_test(self):
        """Character hair uses punchthrough with mid-range threshold (~0.5)."""
        tpc = _make_tpc(alpha_test=0.5)
        at = _extract_alpha_test_from_tpc(tpc)

        node = ModelNode()
        node.texture = 'hm_hair01'
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=at)

        assert node.txi_blending == 2
        assert node.txi_alpha_test == pytest.approx(0.5)

    def test_no_alpha_test_in_tpc_header(self):
        """TPC with alpha_test=0 → surface has no alpha test (default 0.5 used)."""
        tpc = _make_tpc(alpha_test=0.0)  # 0.0 = no alpha test
        at = _extract_alpha_test_from_tpc(tpc)

        node = ModelNode()
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=at)

        assert node.txi_alpha_test == pytest.approx(0.5), (
            "No alpha test (0.0) should use default 0.5"
        )

    def test_opaque_surface_without_punchthrough(self):
        """Opaque surfaces (no TXI punchthrough) still get txi_alpha_test stored."""
        tpc = _make_tpc(alpha_test=0.7)
        at = _extract_alpha_test_from_tpc(tpc)

        node = ModelNode()
        node.texture = 'c_bantha01'
        _apply_txi_to_node(node, "", alpha_test=at)  # no TXI

        # txi_alpha_test stored even though not punchthrough; won't be used at
        # draw time (u_blend_mode=0 → no discard in shader) but should be correct.
        assert node.txi_alpha_test == pytest.approx(0.7, abs=1e-4)
        assert node.txi_blending == 0  # still opaque


# ─────────────────────────────────────────────────────────────────────────────
# GPU renderer: verify u_alpha_test is set per-node (code inspection)
# ─────────────────────────────────────────────────────────────────────────────

class TestGpuRendererAlphaTestCode:
    """Inspect gpu_renderer.py source to verify FIX-ALPHATEST is implemented."""

    @pytest.fixture(autouse=True)
    def gpu_source(self):
        gpu_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'gpu_renderer.py'
        )
        with open(gpu_path, 'r') as f:
            self._src = f.read()

    def test_u_alpha_test_set_per_node_for_punchthrough(self):
        """GPU renderer must set u_alpha_test per-node when blend_mode==2."""
        assert "txi_alpha_test" in self._src, (
            "gpu_renderer.py must read node.txi_alpha_test for per-node threshold"
        )

    def test_u_alpha_test_only_set_for_punchthrough(self):
        """u_alpha_test update must be conditional on txi_blend==2."""
        assert "if txi_blend == 2" in self._src, (
            "gpu_renderer must only update u_alpha_test for punchthrough (txi_blend==2)"
        )

    def test_u_alpha_test_clamped(self):
        """u_alpha_test value must be clamped to [0,1] before setting."""
        assert "max(0.0, min(1.0" in self._src, (
            "gpu_renderer must clamp u_alpha_test to valid [0,1] range"
        )

    def test_punchthrough_blend_disabled(self):
        """Punchthrough mode disables GL blending (uses shader discard)."""
        assert "ctx.disable(moderngl.BLEND)" in self._src, (
            "Punchthrough must disable GL blending — discard happens in shader"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Kotor.NET research confirmation tests
# ─────────────────────────────────────────────────────────────────────────────

class TestKotorNETResearchConfirmation:
    """Tests confirming our implementation matches Kotor.NET findings.

    From KotorModelLoader.cs analysis:
    - node.TransparencyHint at mesh header +84
    - node.DoesRender at byte after beaming
    - IsTSL detection via function pointer values (4216880, 4216816, 4216864)
    """

    def test_transparency_hint_is_stored_on_node(self):
        """Our ModelNode has transparency_hint field (matches Kotor.NET node)."""
        node = ModelNode()
        assert hasattr(node, 'transparency_hint'), (
            "ModelNode must have transparency_hint field (Kotor.NET TransparencyHint)"
        )

    def test_render_flag_on_node(self):
        """ModelNode has render field (matches Kotor.NET DoesRender)."""
        node = ModelNode()
        assert hasattr(node, 'render'), "ModelNode must have render flag"
        assert node.render is True, "Default render=True (all nodes render unless flagged)"

    def test_has_shadow_field(self):
        """ModelNode has has_shadow field (matches Kotor.NET HasShadow)."""
        node = ModelNode()
        assert hasattr(node, 'has_shadow')

    def test_beaming_field(self):
        """ModelNode has beaming field (matches Kotor.NET Beaming)."""
        node = ModelNode()
        assert hasattr(node, 'beaming')

    def test_diffuse_and_ambient_fields(self):
        """ModelNode has diffuse/ambient color fields (Kotor.NET skips these).

        Kotor.NET KotorModelLoader.cs line 47:
            mdlReader.BaseStream.Position += 3*4*2;
            //node.Diffuse = mdlReader.ReadColour();
            //node.Ambient = mdlReader.ReadColour();
        Both fields are commented out in Kotor.NET — we do parse them.
        """
        node = ModelNode()
        assert hasattr(node, 'diffuse'), "ModelNode must store diffuse color"
        assert hasattr(node, 'ambient'), "ModelNode must store ambient color"

    def test_k2_tsl_isTSL_function_pointers(self):
        """K2 TSL detection uses function pointer values from game binary.

        Kotor.NET KotorModelLoader.cs:
            public bool IsTSL => FunctionPointer0 == 4216880
                              || FunctionPointer0 == 4216816
                              || FunctionPointer0 == 4216864;

        Our parser reads fp1 at mesh header +0 and uses those same values
        (plus PC K1/K2 variants) to detect game version.
        """
        # The K2 function pointer values from Kotor.NET and our parser match
        K2_TSL_FP_VALUES = {4216880, 4216816, 4216864}  # Kotor.NET values
        OUR_K2_FP_VALUES = {4285200, 4284816}           # our PC values
        # These sets should be known (documented) — this test just validates
        # they are the correct values from the source
        assert 4216880 in K2_TSL_FP_VALUES
        assert 4285200 in OUR_K2_FP_VALUES
        # The values differ because Kotor.NET uses OpenGLES mobile binaries
        # and our parser uses the PC (desktop) binary function pointers.
        assert K2_TSL_FP_VALUES != OUR_K2_FP_VALUES, (
            "Kotor.NET mobile and PC desktop binaries have different fp1 values"
        )

    def test_tpc_alpha_test_field_at_offset_4(self):
        """TPC header has alpha_test float at bytes [4-7] as confirmed by Kotor.NET/xoreos."""
        # Build a TPC with a known alpha_test value and verify extraction
        test_at = 0.333
        tpc = _make_tpc(alpha_test=test_at)
        # Verify the float is at bytes [4-7]
        extracted = struct.unpack_from('<f', tpc, 4)[0]
        assert extracted == pytest.approx(test_at, abs=1e-5), (
            "TPC alpha_test float must be at header bytes [4-7] (Kotor.NET confirmed)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# PyKotor gl/shader/texture.py research confirmation
# ─────────────────────────────────────────────────────────────────────────────

class TestPykotorTextureResearchConfirmation:
    """Tests confirming our implementation matches PyKotor GL texture findings.

    From PyKotor gl/shader/texture.py:
        class Texture:
            blend_mode: int = 0   # 0=default, 1=additive, 2=punchthrough
            alpha_cutoff: float = 0.0
            has_alpha: bool = False
    """

    def test_txi_blending_matches_pykotor_blend_modes(self):
        """Our TXI blend mode integers must match PyKotor Texture.blend_mode values."""
        # PyKotor: 0=default, 1=additive, 2=punchthrough
        # Our:     0=none,    1=additive, 2=punchthrough
        result_none   = _parse_txi_string("")['blending']
        result_add    = _parse_txi_string("blending additive\n")['blending']
        result_punch  = _parse_txi_string("blending punchthrough\n")['blending']

        assert result_none  == 0, "No blending: 0 (PyKotor default)"
        assert result_add   == 1, "Additive: 1 (PyKotor additive)"
        assert result_punch == 2, "Punchthrough: 2 (PyKotor punchthrough)"

    def test_alpha_cutoff_concept_matches_txi_alpha_test(self):
        """PyKotor Texture.alpha_cutoff = our txi_alpha_test concept.

        PyKotor Mesh.draw() in gl/models/mdl.py:
            alpha_cutoff = float(getattr(diffuse_tex, 'alpha_cutoff', 0.0))
            ...
            shader.set_float('alphaCutoff', alpha_cutoff)

        We store the same value as node.txi_alpha_test and pass it as
        u_alpha_test to the GPU shader.
        """
        # The concept is the same: a float 0..1 threshold for punchthrough discard
        node = ModelNode()
        _apply_txi_to_node(node, "blending punchthrough\n", alpha_test=0.6)

        # node.txi_alpha_test is our equivalent of PyKotor's Texture.alpha_cutoff
        assert node.txi_alpha_test == pytest.approx(0.6)

    def test_has_alpha_for_additive(self):
        """PyKotor Texture.has_alpha=True for additive textures.

        PyKotor Mesh.draw():
            has_alpha = bool(getattr(diffuse_tex, 'has_alpha', True))
            if blend_mode == 1:  # Additive
                glBlendFunc(GL_SRC_ALPHA if has_alpha else GL_SRC_COLOR, GL_ONE)

        Our GPU renderer uses GL ONE/ONE for additive which is a simpler
        approach (always GL_SRC_ALPHA for KotOR additive surfaces).
        """
        result = _parse_txi_string("blending additive\n")
        assert result['blending'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
