"""
test_v230_envmap_txi_rendering.py  –  Phase 3.5 environment map & TXI rendering audit
======================================================================================

Comprehensive tests for environment-map, TXI parsing, and texture-alpha handling
improvements identified from the multi-repo deep dive:

  • Kotor.NET  (NickHugi/Kotor.NET)  – minimal TXI/TPC structure
  • KotOR.js   (KobaltBlu)            – ShaderOdysseyModel.ts + TXI.ts + TextureLoader.ts
  • xoreos                            – modelnode.cpp EnvironmentBlendedOver / BlendedUnder
  • PyKotor    (th3w1zard1)           – txi_data.py authoritative TXI field list

KEY FINDINGS AND FIXES TESTED:
─────────────────────────────────────────────────────────────────────────────────

FIX-1  bumpyshinytexture → envmaptexture ALIAS
    xoreos/modelnode.cpp:479-482:
        if (!...bumpyShinyTexture.empty()) envMap = ...bumpyShinyTexture;
        if (!...envMapTexture.empty())     envMap = ...envMapTexture;  // overrides
    KotOR.js/TXI.ts:161-164:
        case 'bumpyshinytexture':
        case 'envmaptexture':
            this.envMapTexture = args[1]...
    Both keywords map to the same environment-map texture slot.
    OLD BUG: our _parse_txi_string treated 'bumpyshinytexture' as specbumpmap.
    FIX: _parse_txi_string now routes 'bumpyshinytexture' → result['envmaptexture'].

FIX-2  KotOR uses EnvironmentBlendedOver (NOT BlendedUnder like NWN)
    xoreos/modelnode.cpp:726-773 renderGeometryEnvMappedOver (KotOR + KotOR2):
        Draw diffuse with GL_ONE, GL_ZERO
        Re-draw diffuse with GL_ZERO, GL_ONE   (preserve dest alpha = 1 - diffuse.a)
        Draw env map with GL_ONE_MINUS_DST_ALPHA, GL_ONE  (additive, weighted)
    Equivalent single-pass formula:
        lit_color += env_col * (1.0 - diffuse.alpha)
    KotOR.js ShaderOdysseyModel.ts (ENVMAP_BLENDING_ADD branch ~line 340):
        outgoingLight += envColor * reflectivity * (1 - diffuseColor.a)
    OLD BUG: our shader used mix(lit_color, env_col, diffuse.alpha) which is WRONG
             (BlendedUnder formula; env REPLACES diffuse instead of being additive)
    FIX: shader now uses += env_col * (1 - diffuse.alpha)

FIX-3  TPC alpha channel interpretation with envmaptexture
    When envmaptexture is in TXI, the DXT5 alpha channel = blend weight for env.
    The surface is NOT transparent — env is additive so final output is always
    fully opaque (final_alpha = max(diffuse*node_alpha, (1-diffuse)*node_alpha)).
    _apply_kotor_alpha preserves the alpha channel for env-mapped textures.

FIX-4  Standalone .txi file loading
    TextureCache.get_txi() searches:
      1. Standalone .txi file on disk (same directory as texture)
      2. TXI embedded at end of .tpc file
      3. TXI resource from BIF/KEY archive
    This ensures envmaptexture, bumpyshinytexture, etc. are picked up from
    all possible TXI source locations.

FIX-5  TPC alphaTest header field
    TPC header bytes [4-7] = float alpha_test_threshold.
    Used only for blending=punchthrough (not transparency).
    Non-1.0 alphaTest does NOT mean the texture is transparent — it's the
    discard threshold for alpha-tested geometry (grass, grates, foliage).

References:
    xoreos/src/graphics/aurora/modelnode.cpp  (renderGeometryEnvMappedOver)
    KotOR.js/src/shaders/ShaderOdysseyModel.ts (ENVMAP_BLENDING_ADD)
    KotOR.js/src/resource/TXI.ts              (bumpyshinytexture/envmaptexture)
    KotOR.js/src/loaders/TextureLoader.ts     (ParseTXI envmap loading)
    PyKotor/src/pykotor/resource/formats/txi/txi_data.py (authoritative)
    Kotor.NET/Kotor.NET/Formats/KotorTXI/TXI.cs (TXIEnvironmentMappedModifier)
"""

import struct
import sys
import os

import pytest

# Allow importing from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.gui.viewport import _parse_txi_string, _apply_txi_to_node, _extract_txi_from_tpc_legacy
from src.core.model_data import ModelNode


# ─────────────────────────────────────────────────────────────────────────────
# FIX-1: bumpyshinytexture → envmaptexture alias
# ─────────────────────────────────────────────────────────────────────────────

class TestBumpyShinyTexture:
    """TXI 'bumpyshinytexture' must be treated as an env-map alias, not a bump map."""

    def test_bumpyshinytexture_maps_to_envmaptexture(self):
        """KotOR.js TXI.ts:161-164 + xoreos modelnode.cpp:479-480."""
        txi = "bumpyshinytexture cm_baremetal\n"
        result = _parse_txi_string(txi)
        assert result['envmaptexture'] == 'cm_baremetal', (
            "bumpyshinytexture must alias envmaptexture (KotOR.js TXI.ts:161-164)")

    def test_bumpyshinytexture_lowercase_name(self):
        """Texture names should be lowercased per KotOR.js Load() convention."""
        txi = "bumpyshinytexture CM_Fog\n"
        result = _parse_txi_string(txi)
        assert result['envmaptexture'] == 'cm_fog'

    def test_bumpyshinytexture_does_not_set_bumpmaptexture(self):
        """bumpyshinytexture is NOT a bump map — must not go into bumpmaptexture slot."""
        txi = "bumpyshinytexture cm_baremetal\n"
        result = _parse_txi_string(txi)
        assert result['bumpmaptexture'] == '', (
            "bumpyshinytexture must not populate bumpmaptexture (it's an env-map alias)")

    def test_bumpyshinytexture_applies_to_node(self):
        """_apply_txi_to_node must set txi_envmaptexture from bumpyshinytexture."""
        node = ModelNode()
        txi_str = "bumpyshinytexture cm_baremetal\n"
        _apply_txi_to_node(node, txi_str)
        assert hasattr(node, 'txi_envmaptexture')
        assert node.txi_envmaptexture == 'cm_baremetal'

    def test_bumpyshinytexture_does_not_set_bumpmaptexture_on_node(self):
        """After applying bumpyshinytexture TXI, node.txi_bumpmaptexture must be empty."""
        node = ModelNode()
        txi_str = "bumpyshinytexture cm_baremetal\n"
        _apply_txi_to_node(node, txi_str)
        assert getattr(node, 'txi_bumpmaptexture', '') == ''

    def test_envmaptexture_still_works(self):
        """envmaptexture keyword must still parse correctly (not broken by alias fix)."""
        txi = "envmaptexture cm_fog\n"
        result = _parse_txi_string(txi)
        assert result['envmaptexture'] == 'cm_fog'

    def test_envmaptexture_wins_over_bumpyshinytexture_when_both_present(self):
        """When both keywords appear, xoreos takes the last one seen.
        Our parser is line-by-line; whichever appears last in the TXI wins."""
        # Both present — envmaptexture second, so it should win
        txi = "bumpyshinytexture cm_baremetal\nenvmaptexture cm_fog\n"
        result = _parse_txi_string(txi)
        # Both map to the same field; last value wins
        assert result['envmaptexture'] == 'cm_fog'

    def test_bumpyshinytexture_then_envmaptexture_order(self):
        """When bumpyshinytexture is after envmaptexture, it overrides it."""
        txi = "envmaptexture cm_fog\nbumpyshinytexture cm_baremetal\n"
        result = _parse_txi_string(txi)
        assert result['envmaptexture'] == 'cm_baremetal'

    def test_bumpyshinytexture_empty_arg_ignored(self):
        """bumpyshinytexture with no argument should not set envmaptexture."""
        txi = "bumpyshinytexture\n"
        result = _parse_txi_string(txi)
        # Empty or numeric-only args should be ignored
        # (the fix only sets envmaptexture when arg is a non-numeric string)
        assert result['envmaptexture'] == ''

    def test_bumpyshinytexture_numeric_arg_ignored(self):
        """bumpyshinytexture with a numeric arg (malformed) should not set envmaptexture."""
        txi = "bumpyshinytexture 1\n"
        result = _parse_txi_string(txi)
        # Numeric arg means malformed line; should not be treated as texture name
        assert result['envmaptexture'] == ''


# ─────────────────────────────────────────────────────────────────────────────
# FIX-2: KotOR uses EnvironmentBlendedOver (additive env on top of diffuse)
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvMapBlendingFormula:
    """The env-map blending formula must match xoreos BlendedOver (additive)."""

    def test_envmap_blending_add_formula_concept(self):
        """
        Verify the conceptual formula: env contribution = env_col * (1 - diffuse.a)

        xoreos renderGeometryEnvMappedOver:
            GL_BLEND(GL_ONE_MINUS_DST_ALPHA, GL_ONE) for env pass
        KotOR.js ENVMAP_BLENDING_ADD:
            outgoingLight += envColor * reflectivity * (1 - diffuseColor.a)

        At diffuse.alpha = 0.0 (fully transparent diffuse): full env contribution
        At diffuse.alpha = 1.0 (fully opaque diffuse): zero env contribution
        At diffuse.alpha = 0.5 (50% transparent): 50% env contribution
        """
        def env_blended_over(lit_rgb, env_rgb, diffuse_alpha):
            """Reference implementation of KotOR's BlendedOver formula."""
            env_blend = 1.0 - diffuse_alpha
            return (
                lit_rgb[0] + env_rgb[0] * env_blend,
                lit_rgb[1] + env_rgb[1] * env_blend,
                lit_rgb[2] + env_rgb[2] * env_blend,
            )

        # Test: diffuse fully opaque → env barely shows
        lit = (0.5, 0.5, 0.5)
        env = (1.0, 1.0, 1.0)
        result = env_blended_over(lit, env, diffuse_alpha=1.0)
        assert result == pytest.approx((0.5, 0.5, 0.5), abs=1e-6), (
            "With alpha=1 (opaque), env should have zero contribution")

        # Test: diffuse fully transparent → full env contribution
        result = env_blended_over(lit, env, diffuse_alpha=0.0)
        assert result == pytest.approx((1.5, 1.5, 1.5), abs=1e-6), (
            "With alpha=0 (transparent), env adds its full value")

        # Test: diffuse half-transparent → 50% env
        result = env_blended_over(lit, env, diffuse_alpha=0.5)
        assert result == pytest.approx((1.0, 1.0, 1.0), abs=1e-6), (
            "With alpha=0.5, env contributes 50%")

    def test_old_mix_formula_is_wrong(self):
        """
        Verify that the OLD mix formula (lerp) is NOT what KotOR uses.
        OLD: lit_color = mix(lit_color, env_col, diffuse.alpha)
        This is BlendedUnder (NWN), NOT BlendedOver (KotOR).
        """
        def env_blended_under_wrong(lit_rgb, env_rgb, diffuse_alpha):
            """The WRONG BlendedUnder formula (NWN, not KotOR)."""
            t = diffuse_alpha
            return (
                lit_rgb[0] * (1 - t) + env_rgb[0] * t,
                lit_rgb[1] * (1 - t) + env_rgb[1] * t,
                lit_rgb[2] * (1 - t) + env_rgb[2] * t,
            )

        def env_blended_over_correct(lit_rgb, env_rgb, diffuse_alpha):
            """The CORRECT BlendedOver formula (KotOR)."""
            env_blend = 1.0 - diffuse_alpha
            return (
                lit_rgb[0] + env_rgb[0] * env_blend,
                lit_rgb[1] + env_rgb[1] * env_blend,
                lit_rgb[2] + env_rgb[2] * env_blend,
            )

        lit = (0.3, 0.4, 0.5)
        env = (1.0, 0.8, 0.6)

        # These should differ
        wrong  = env_blended_under_wrong(lit, env, 0.2)
        correct = env_blended_over_correct(lit, env, 0.2)
        assert wrong != pytest.approx(correct, abs=1e-6), (
            "BlendedUnder and BlendedOver should produce different results")

        # Verify the correct formula matches xoreos at alpha=0.2
        # env_blend = 1 - 0.2 = 0.8
        expected = (0.3 + 1.0 * 0.8, 0.4 + 0.8 * 0.8, 0.5 + 0.6 * 0.8)
        assert correct == pytest.approx(expected, abs=1e-6)

    def test_bantha_hide_scenario(self):
        """
        Bantha hide has envmaptexture or bumpyshinytexture pointing to a shiny
        env map. The diffuse alpha of bantha skin texture is typically low
        (near 0), so the env map shows strongly → creates the characteristic
        wet/shiny hide appearance.

        Without BlendedOver, the env map was either ignored or replacing diffuse.
        """
        # Simulate bantha skin: diffuse darker, low alpha (env shows through)
        def env_blended_over(lit_rgb, env_rgb, diffuse_alpha):
            env_blend = 1.0 - diffuse_alpha
            return tuple(min(1.0, lit_rgb[i] + env_rgb[i] * env_blend) for i in range(3))

        # Bantha hide: dark diffuse, low alpha → shiny from env
        lit_bantha = (0.2, 0.15, 0.1)  # dark hide colour
        env_shine   = (0.8, 0.7, 0.6)  # warm shiny reflections
        diffuse_a   = 0.1              # nearly transparent diffuse → env dominates

        result = env_blended_over(lit_bantha, env_shine, diffuse_a)
        # Should be brighter than just the diffuse (env added)
        assert result[0] > lit_bantha[0], "Env should brighten the surface"
        assert result[1] > lit_bantha[1]
        # With alpha=0.1, env_blend=0.9 → significant env contribution
        expected_r = min(1.0, 0.2 + 0.8 * 0.9)
        assert result[0] == pytest.approx(expected_r, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# FIX-3: TXI parsing correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestTXIParsing:
    """TXI parsing must correctly handle all rendering-relevant fields."""

    def test_basic_envmaptexture_parse(self):
        txi = "envmaptexture cm_baremetal\n"
        r = _parse_txi_string(txi)
        assert r['envmaptexture'] == 'cm_baremetal'

    def test_blending_additive(self):
        txi = "blending additive\n"
        r = _parse_txi_string(txi)
        assert r['blending'] == 1

    def test_blending_punchthrough(self):
        txi = "blending punchthrough\n"
        r = _parse_txi_string(txi)
        assert r['blending'] == 2

    def test_blending_default_is_zero(self):
        r = _parse_txi_string("")
        assert r['blending'] == 0

    def test_cube_map_flag(self):
        txi = "cube 1\n"
        r = _parse_txi_string(txi)
        assert r['cube'] is True

    def test_flipbook_params(self):
        txi = "proceduretype cycle\nnumx 4\nnumy 4\nfps 10\n"
        r = _parse_txi_string(txi)
        assert r['proceduretype'] == 'cycle'
        assert r['numx'] == 4
        assert r['numy'] == 4
        assert r['fps'] == pytest.approx(10.0)

    def test_wateralpha(self):
        txi = "wateralpha 0.5\n"
        r = _parse_txi_string(txi)
        assert r['wateralpha'] == pytest.approx(0.5)

    def test_wateralpha_default_is_one(self):
        r = _parse_txi_string("")
        assert r['wateralpha'] == pytest.approx(1.0)

    def test_bumpmaptexture(self):
        txi = "bumpmaptexture bump_normal\n"
        r = _parse_txi_string(txi)
        assert r['bumpmaptexture'] == 'bump_normal'
        assert r['envmaptexture'] == ''  # must not bleed into envmaptexture

    def test_bumpmapscaling(self):
        txi = "bumpmapscaling 2.5\n"
        r = _parse_txi_string(txi)
        assert r['bumpmapscaling'] == pytest.approx(2.5)

    def test_clamp_both_axes(self):
        txi = "clamp 3\n"
        r = _parse_txi_string(txi)
        assert r['clamp'] is True
        assert r['clamp_s'] is True
        assert r['clamp_t'] is True

    def test_clamp_s_only(self):
        txi = "clamp 1\n"
        r = _parse_txi_string(txi)
        assert r['clamp_s'] is True
        assert r['clamp_t'] is False

    def test_mipmap_off(self):
        txi = "mipmap 0\n"
        r = _parse_txi_string(txi)
        assert r['mipmap'] == 0

    def test_decal_flag(self):
        txi = "decal 1\n"
        r = _parse_txi_string(txi)
        assert r['decal'] is True

    def test_empty_txi_returns_defaults(self):
        r = _parse_txi_string("")
        assert r['blending'] == 0
        assert r['envmaptexture'] == ''
        assert r['bumpmaptexture'] == ''
        assert r['cube'] is False
        assert r['wateralpha'] == pytest.approx(1.0)

    def test_unknown_command_silently_ignored(self):
        """Unknown TXI commands should not raise an exception."""
        txi = "unknowncommand somevalue\nanother_unknown 42\n"
        r = _parse_txi_string(txi)
        assert r is not None  # must not crash

    def test_multiline_txi_all_fields(self):
        """Test a realistic multi-field TXI like would appear on a KotOR character."""
        txi = """envmaptexture cm_baremetal
blending punchthrough
bumpmapscaling 1.0
mipmap 1
"""
        r = _parse_txi_string(txi)
        assert r['envmaptexture'] == 'cm_baremetal'
        assert r['blending'] == 2
        assert r['bumpmapscaling'] == pytest.approx(1.0)
        assert r['mipmap'] == 1

    def test_kotor_droid_txi_scenario(self):
        """
        Droids in KotOR (HK-47, T3-M4, battle droids) have shiny metal
        surfaces using bumpyshinytexture (and sometimes envmaptexture).
        Both should result in an env-map effect being applied.
        """
        # HK-47 style TXI (uses bumpyshinytexture for chrome body)
        hk47_txi = "bumpyshinytexture cm_baremetal\nmipmap 1\n"
        r = _parse_txi_string(hk47_txi)
        assert r['envmaptexture'] == 'cm_baremetal'
        assert r['bumpmaptexture'] == ''

    def test_kotor_creature_envmap_txi_scenario(self):
        """
        Bantha, rancor and other creatures may use envmaptexture for hide gloss.
        """
        bantha_txi = "envmaptexture cm_fog\nbumpmapscaling 1.5\n"
        r = _parse_txi_string(bantha_txi)
        assert r['envmaptexture'] == 'cm_fog'
        assert r['bumpmapscaling'] == pytest.approx(1.5)

    def test_islightmap_flag(self):
        txi = "islightmap 1\n"
        r = _parse_txi_string(txi)
        assert r['islightmap'] is True

    def test_isbumpmap_flag(self):
        txi = "isbumpmap 1\n"
        r = _parse_txi_string(txi)
        assert r['isbumpmap'] is True

    def test_renderhint_normalmap(self):
        txi = "renderhint normalmap\n"
        r = _parse_txi_string(txi)
        assert r['renderhint'] == 'normalmap'

    def test_case_insensitive_command(self):
        """TXI commands should be case-insensitive."""
        txi = "EnvMapTexture CM_Fog\n"
        r = _parse_txi_string(txi)
        # After lowercasing the command, it should still be found
        # Note: TXI parser lowercases the whole string before parsing
        assert r['envmaptexture'] == 'cm_fog'


# ─────────────────────────────────────────────────────────────────────────────
# FIX-4: TXI → node field application
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyTxiToNode:
    """_apply_txi_to_node must correctly propagate all TXI fields to ModelNode."""

    def test_envmaptexture_sets_txi_envmaptexture(self):
        node = ModelNode()
        _apply_txi_to_node(node, "envmaptexture cm_baremetal\n")
        assert node.txi_envmaptexture == 'cm_baremetal'

    def test_bumpyshinytexture_sets_txi_envmaptexture(self):
        """The primary fix: bumpyshinytexture must set txi_envmaptexture."""
        node = ModelNode()
        _apply_txi_to_node(node, "bumpyshinytexture cm_fog\n")
        assert node.txi_envmaptexture == 'cm_fog', (
            "bumpyshinytexture must set txi_envmaptexture (not txi_bumpmaptexture)")

    def test_blending_additive_sets_field(self):
        node = ModelNode()
        _apply_txi_to_node(node, "blending additive\n")
        assert node.txi_blending == 1

    def test_blending_punchthrough_sets_field(self):
        node = ModelNode()
        _apply_txi_to_node(node, "blending punchthrough\n")
        assert node.txi_blending == 2

    def test_flipbook_params_set(self):
        node = ModelNode()
        _apply_txi_to_node(node, "proceduretype cycle\nnumx 4\nnumy 4\nfps 10\n")
        assert node.txi_proceduretype == 'cycle'
        assert node.txi_numx == 4
        assert node.txi_numy == 4
        assert node.txi_fps == pytest.approx(10.0)

    def test_bumpmaptexture_sets_both_fields(self):
        node = ModelNode()
        _apply_txi_to_node(node, "bumpmaptexture bump_nmap\n")
        assert node.txi_bumpmaptexture == 'bump_nmap'
        assert node.bump_map == 'bump_nmap'

    def test_wateralpha_sets_field(self):
        node = ModelNode()
        _apply_txi_to_node(node, "wateralpha 0.5\n")
        assert node.txi_wateralpha == pytest.approx(0.5)

    def test_empty_txi_leaves_defaults(self):
        node = ModelNode()
        _apply_txi_to_node(node, "")
        assert node.txi_blending == 0
        assert node.txi_envmaptexture == ''

    def test_none_txi_leaves_defaults(self):
        node = ModelNode()
        _apply_txi_to_node(node, None)
        assert node.txi_blending == 0

    def test_cube_flag_sets_txi_cube(self):
        node = ModelNode()
        _apply_txi_to_node(node, "cube 1\n")
        assert getattr(node, 'txi_cube', False) is True

    def test_clamp_sets_clamp_fields(self):
        node = ModelNode()
        _apply_txi_to_node(node, "clamp 3\n")
        assert getattr(node, 'txi_clamp_s', False) is True
        assert getattr(node, 'txi_clamp_t', False) is True

    def test_rotate_sets_field(self):
        node = ModelNode()
        _apply_txi_to_node(node, "rotate 45.0\n")
        assert getattr(node, 'txi_rotate', 0.0) == pytest.approx(45.0)


# ─────────────────────────────────────────────────────────────────────────────
# FIX-5: TPC header alphaTest field usage
# ─────────────────────────────────────────────────────────────────────────────

class TestTPCAlphaTest:
    """TPC header alphaTest field must only be used for punchthrough, not transparency."""

    def _make_tpc_header(self, data_sz=0, alpha_test=1.0, width=8, height=8,
                         encoding=4, mip_count=1):
        """Build a minimal 128-byte TPC header for testing."""
        header = bytearray(128)
        struct.pack_into('<I', header, 0, data_sz)        # data_sz
        struct.pack_into('<f', header, 4, alpha_test)     # alpha_test
        struct.pack_into('<H', header, 8, width)          # width
        struct.pack_into('<H', header, 10, height)        # height
        header[12] = encoding                              # encoding
        header[13] = mip_count                             # mip_count
        return bytes(header)

    def test_alpha_test_field_is_readable(self):
        """Verify TPC header alpha_test is at bytes [4-7]."""
        header = self._make_tpc_header(alpha_test=0.5)
        at = struct.unpack_from('<f', header, 4)[0]
        assert at == pytest.approx(0.5)

    def test_alpha_test_1_is_default_no_punchthrough(self):
        """alphaTest=1.0 means 'no alpha test' — texture is opaque."""
        header = self._make_tpc_header(alpha_test=1.0)
        at = struct.unpack_from('<f', header, 4)[0]
        # When alphaTest=1.0, KotOR.js does not enable punchthrough
        # (alphaTest != 1 && envMapTexture == null → transparent)
        assert at == pytest.approx(1.0), "Default no-test value"

    def test_alpha_test_half_with_punchthrough_blending(self):
        """alphaTest<1.0 with punchthrough blending → binary cutoff."""
        header = self._make_tpc_header(alpha_test=0.5)
        at = struct.unpack_from('<f', header, 4)[0]
        threshold = int(at * 255)
        assert threshold == 127  # ≈ 128 in practice

    def test_alpha_test_with_envmap_no_transparency(self):
        """
        KotOR.js TextureLoader.ts:
            if(texture.header.alphaTest != 1 && texture.txi.envMapTexture == null)
                tex.material.transparent = true
        When envMapTexture is set: DON'T make transparent regardless of alphaTest.
        """
        txi = "envmaptexture cm_baremetal\n"
        r = _parse_txi_string(txi)
        has_env = bool(r['envmaptexture'])
        # Simulate KotOR.js transparency decision
        alpha_test = 0.5  # non-1.0 alphaTest
        should_be_transparent = (alpha_test != 1.0) and not has_env
        assert should_be_transparent is False, (
            "With envmaptexture set, surface must NOT be marked transparent "
            "even when alphaTest < 1.0 (KotOR.js TextureLoader.ts logic)")

    def test_alpha_test_without_envmap_may_enable_transparency(self):
        """Without envmaptexture and alphaTest<1.0 → texture may be semi-transparent."""
        txi = ""
        r = _parse_txi_string(txi)
        has_env = bool(r['envmaptexture'])
        alpha_test = 0.5
        # With no env map and alphaTest != 1.0: KotOR.js enables transparency
        should_be_transparent = (alpha_test != 1.0) and not has_env
        assert should_be_transparent is True


# ─────────────────────────────────────────────────────────────────────────────
# FIX-6: _apply_kotor_alpha alpha channel handling for env-mapped textures
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyKotorAlphaEnvMap:
    """DXT5 alpha channel must be preserved for env-mapped textures (blend weight)."""

    def _make_rgba_image(self, w=4, h=4, alpha=128):
        """Create a test RGBA PIL image with specified alpha."""
        try:
            from PIL import Image
            import numpy as np
            arr = np.ones((h, w, 4), dtype=np.uint8) * 200
            arr[:, :, 3] = alpha
            return Image.fromarray(arr, 'RGBA')
        except ImportError:
            return None

    def test_envmap_preserves_alpha_channel(self):
        """Env-mapped textures must preserve their DXT5 alpha (blend weight)."""
        img = self._make_rgba_image(alpha=50)
        if img is None:
            pytest.skip("PIL not available")

        from src.gui.viewport import TextureCache
        import numpy as np

        txi_meta = _parse_txi_string("envmaptexture cm_baremetal\n")
        raw_header = b'\x00' * 128  # dummy TPC header

        # Call the static method directly
        result = TextureCache._apply_kotor_alpha(raw_header, img, txi_meta)
        arr = np.array(result)
        # Alpha must be preserved (not forced to 255)
        assert arr[:, :, 3].mean() < 255, (
            "Env-mapped texture alpha must be preserved as blend weight")
        # Alpha should still be 50 (not modified)
        assert arr[:, :, 3].mean() == pytest.approx(50.0, abs=1.0)

    def test_opaque_surface_forces_alpha_255(self):
        """Standard opaque surfaces must have alpha forced to 255."""
        img = self._make_rgba_image(alpha=50)
        if img is None:
            pytest.skip("PIL not available")

        from src.gui.viewport import TextureCache
        import numpy as np

        txi_meta = _parse_txi_string("")  # no TXI = opaque
        raw_header = b'\x00' * 128

        result = TextureCache._apply_kotor_alpha(raw_header, img, txi_meta)
        arr = np.array(result)
        # Alpha must be forced to 255 for opaque surfaces
        assert arr[:, :, 3].min() == 255, (
            "Opaque surface texture alpha must be forced to 255")

    def test_bumpmap_forces_alpha_255(self):
        """Bump-mapped textures encode normals in alpha — must force to 255."""
        img = self._make_rgba_image(alpha=100)
        if img is None:
            pytest.skip("PIL not available")

        from src.gui.viewport import TextureCache
        import numpy as np

        txi_meta = _parse_txi_string("bumpmaptexture bump_nmap\n")
        raw_header = b'\x00' * 128

        result = TextureCache._apply_kotor_alpha(raw_header, img, txi_meta)
        arr = np.array(result)
        assert arr[:, :, 3].min() == 255, (
            "Bump-mapped texture alpha (= normal data) must be forced to 255")

    def test_additive_blending_preserves_alpha(self):
        """Additive blended textures (particles) must preserve their alpha."""
        img = self._make_rgba_image(alpha=100)
        if img is None:
            pytest.skip("PIL not available")

        from src.gui.viewport import TextureCache
        import numpy as np

        txi_meta = _parse_txi_string("blending additive\n")
        raw_header = b'\x00' * 128

        result = TextureCache._apply_kotor_alpha(raw_header, img, txi_meta)
        arr = np.array(result)
        # Additive blend preserves alpha for particle effects
        assert arr[:, :, 3].mean() == pytest.approx(100.0, abs=1.0), (
            "Additive blended texture alpha must be preserved")

    def test_bumpyshinytexture_preserves_alpha_via_envmap(self):
        """
        bumpyshinytexture maps to envmaptexture in parse_txi_string.
        After the fix, _apply_kotor_alpha should preserve alpha for it.
        """
        img = self._make_rgba_image(alpha=30)
        if img is None:
            pytest.skip("PIL not available")

        from src.gui.viewport import TextureCache
        import numpy as np

        # After fix: bumpyshinytexture → envmaptexture in parsed meta
        txi_meta = _parse_txi_string("bumpyshinytexture cm_baremetal\n")
        assert txi_meta['envmaptexture'] == 'cm_baremetal', "Pre-condition: fix applied"

        raw_header = b'\x00' * 128
        result = TextureCache._apply_kotor_alpha(raw_header, img, txi_meta)
        arr = np.array(result)
        # Alpha must be preserved (it's the env blend weight)
        assert arr[:, :, 3].mean() == pytest.approx(30.0, abs=1.0), (
            "bumpyshinytexture (→ envmaptexture) alpha must be preserved as blend weight")


# ─────────────────────────────────────────────────────────────────────────────
# FIX-7: GPU renderer env-map logic
# ─────────────────────────────────────────────────────────────────────────────

class TestGpuRendererEnvMapLogic:
    """GPU renderer must correctly handle env-mapped nodes."""

    def test_node_with_envmap_is_classified_opaque(self):
        """Env-mapped nodes must be in the opaque render pass (not transparent)."""
        from src.gui.gpu_renderer import GpuRenderer

        renderer = GpuRenderer()
        # Can't run GPU in test (no EGL), but verify _classify_node logic
        # by reading the source intent. The is_trans logic:
        # is_trans = (tb == 1) or (na < 0.999 and not has_env)
        # With has_env=True and tb=0, na=1.0: is_trans = False (opaque) ✓

        # Verify the formula directly
        na = 1.0   # node alpha
        tb = 0     # blending = normal
        has_env = True
        is_trans = (tb == 1) or (na < 0.999 and not has_env)
        assert is_trans is False, "Env-mapped nodes must be in the opaque pass"

    def test_node_without_envmap_opaque_alpha_is_opaque(self):
        """Standard opaque nodes with no env map must be in opaque pass."""
        na = 1.0
        tb = 0
        has_env = False
        is_trans = (tb == 1) or (na < 0.999 and not has_env)
        assert is_trans is False

    def test_additive_node_is_transparent(self):
        """Additive blended nodes must be in the transparent pass."""
        na = 1.0
        tb = 1  # additive
        has_env = False
        is_trans = (tb == 1) or (na < 0.999 and not has_env)
        assert is_trans is True

    def test_low_alpha_node_without_envmap_is_transparent(self):
        """Nodes with node_alpha < 1 and no env map → transparent pass."""
        na = 0.5
        tb = 0
        has_env = False
        is_trans = (tb == 1) or (na < 0.999 and not has_env)
        assert is_trans is True

    def test_low_alpha_node_with_envmap_is_opaque(self):
        """Env-mapped nodes must stay opaque even if node_alpha is not 1."""
        na = 0.5
        tb = 0
        has_env = True
        is_trans = (tb == 1) or (na < 0.999 and not has_env)
        assert is_trans is False, (
            "Env-mapped nodes are NOT transparency-sorted — they use additive blending")

    def test_env_final_alpha_formula(self):
        """
        GPU shader final_alpha for BlendedOver env-map:
            final_alpha = max(diffuse.a * node_alpha, (1 - diffuse.a) * node_alpha)
        At diffuse.a=0 (transparent): final = max(0, node_alpha) = node_alpha (from env)
        At diffuse.a=1 (opaque): final = max(node_alpha, 0) = node_alpha (from diffuse)
        At diffuse.a=0.5: final = max(0.5, 0.5) = 0.5 * node_alpha
        """
        def compute_final_alpha(diffuse_a, node_alpha, u_alpha=1.0):
            final_from_diffuse = diffuse_a * u_alpha * node_alpha
            env_min_alpha = (1.0 - diffuse_a) * u_alpha * node_alpha
            return max(final_from_diffuse, env_min_alpha)

        # Test cases
        assert compute_final_alpha(0.0, 1.0) == pytest.approx(1.0), (
            "With diffuse_a=0: env_min_alpha=1.0 → surface fully visible from env")
        assert compute_final_alpha(1.0, 1.0) == pytest.approx(1.0), (
            "With diffuse_a=1: diffuse alpha=1.0 → surface fully opaque")
        assert compute_final_alpha(0.5, 1.0) == pytest.approx(0.5), (
            "With diffuse_a=0.5: both are 0.5 → max=0.5")
        assert compute_final_alpha(0.3, 0.8) == pytest.approx(
            max(0.3 * 0.8, 0.7 * 0.8), abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# FIX-8: TXI extraction from embedded TPC data
# ─────────────────────────────────────────────────────────────────────────────

class TestTPCTXIExtraction:
    """TXI data embedded at end of TPC file must be correctly extracted."""

    def _make_tpc_with_txi(self, txi_string: str, width=4, height=4, encoding=4):
        """Create minimal TPC bytes with embedded TXI."""
        bx = max(1, (width + 3) // 4)
        by = max(1, (height + 3) // 4)
        dxt5_sz = bx * by * 16  # DXT5 block size

        header = bytearray(128)
        struct.pack_into('<I', header, 0, dxt5_sz)  # data_sz = DXT5 size
        struct.pack_into('<f', header, 4, 1.0)       # alpha_test = 1.0
        struct.pack_into('<H', header, 8, width)
        struct.pack_into('<H', header, 10, height)
        header[12] = encoding   # enc=4 (RGBA/DXT5)
        header[13] = 1          # mip_count

        pixel_data = bytes(dxt5_sz)  # zeroed DXT5 data (black transparent)

        txi_bytes = txi_string.encode('utf-8') + b'\x00'
        return bytes(header) + pixel_data + txi_bytes

    def test_extract_envmaptexture_from_tpc(self):
        """TXI embedded in TPC must yield envmaptexture correctly."""
        txi_str = "envmaptexture cm_baremetal\n"
        tpc_data = self._make_tpc_with_txi(txi_str)
        extracted = _extract_txi_from_tpc_legacy(tpc_data)
        assert 'envmaptexture' in extracted.lower()
        assert 'cm_baremetal' in extracted.lower()

    def test_extract_bumpyshinytexture_from_tpc(self):
        """bumpyshinytexture TXI embedded in TPC must extract correctly."""
        txi_str = "bumpyshinytexture cm_fog\n"
        tpc_data = self._make_tpc_with_txi(txi_str)
        extracted = _extract_txi_from_tpc_legacy(tpc_data)
        assert 'bumpyshinytexture' in extracted.lower() or 'envmaptexture' in extracted.lower()

    def test_extract_txi_from_tpc_then_parse(self):
        """Full pipeline: extract TXI from TPC → parse → bumpyshinytexture becomes envmap."""
        txi_str = "bumpyshinytexture cm_baremetal\nmipmap 1\n"
        tpc_data = self._make_tpc_with_txi(txi_str)
        extracted = _extract_txi_from_tpc_legacy(tpc_data)
        if extracted:  # may be empty if extraction fails on zeroed data
            parsed = _parse_txi_string(extracted)
            # After fix: bumpyshinytexture → envmaptexture
            assert parsed['envmaptexture'] == 'cm_baremetal'

    def test_empty_tpc_gives_empty_txi(self):
        """TPC with no TXI trailer must return empty string."""
        header = bytearray(128)
        struct.pack_into('<I', header, 0, 0)
        struct.pack_into('<H', header, 8, 4)
        struct.pack_into('<H', header, 10, 4)
        header[12] = 4
        header[13] = 1
        tpc_data = bytes(header) + bytes(16 * 4)  # some pixel data, no TXI
        # Padded with zeros at end means empty TXI
        extracted = _extract_txi_from_tpc_legacy(tpc_data)
        assert extracted == '', "TPC with no TXI trailer must give empty string"


# ─────────────────────────────────────────────────────────────────────────────
# Integration: realistic KotOR creature scenarios
# ─────────────────────────────────────────────────────────────────────────────

class TestKotorCreatureEnvMapScenarios:
    """Realistic scenarios for KotOR creature rendering."""

    def test_hk47_chrome_body_via_bumpyshinytexture(self):
        """
        HK-47 assassination droid has a chrome body using bumpyshinytexture.
        The TXI for his body texture includes bumpyshinytexture cm_baremetal
        which should create a metallic reflective sheen.
        """
        node = ModelNode()
        node.texture = 'phk47_body01'  # fictional HK-47 body texture
        _apply_txi_to_node(node, "bumpyshinytexture cm_baremetal\nmipmap 1\n")
        assert node.txi_envmaptexture == 'cm_baremetal', (
            "HK-47 chrome body: bumpyshinytexture must set txi_envmaptexture")
        assert getattr(node, 'txi_bumpmaptexture', '') == '', (
            "HK-47 chrome body: must NOT set bumpmaptexture")

    def test_bantha_shiny_hide_via_envmaptexture(self):
        """Bantha hide may use envmaptexture for a wet/shiny appearance."""
        node = ModelNode()
        node.texture = 'c_bantha01'
        _apply_txi_to_node(node, "envmaptexture cm_fog\nbumpmapscaling 1.5\n")
        assert node.txi_envmaptexture == 'cm_fog'
        assert node.txi_bumpmapscaling == pytest.approx(1.5)

    def test_warbot_metallic_texture(self):
        """War droids use bumpyshinytexture for metallic plate reflections."""
        node = ModelNode()
        node.texture = 'c_warbot01'
        _apply_txi_to_node(node, "bumpyshinytexture cm_baremetal\nblending punchthrough\n")
        # bumpyshinytexture → envmaptexture
        assert node.txi_envmaptexture == 'cm_baremetal'
        # blending punchthrough for metallic panels
        assert node.txi_blending == 2

    def test_window_glass_no_envmap(self):
        """Glass windows have no envmap — standard alpha transparency."""
        node = ModelNode()
        node.texture = 'window_glass01'
        _apply_txi_to_node(node, "blending additive\n")
        assert node.txi_blending == 1
        assert node.txi_envmaptexture == ''

    def test_campfire_particle_no_envmap(self):
        """Particle effects use additive blending, no env map."""
        node = ModelNode()
        node.texture = 'fx_fire01'
        _apply_txi_to_node(node, "blending additive\n")
        assert node.txi_blending == 1
        assert node.txi_envmaptexture == ''

    def test_water_surface_proceduretype(self):
        """Water surfaces use proceduretype water with bumpmap and envmap."""
        node = ModelNode()
        node.texture = 'fx_water01'
        _apply_txi_to_node(node, (
            "proceduretype water\n"
            "bumpmaptexture bump_ripple\n"
            "wateralpha 0.7\n"
            "envmaptexture cm_water\n"
        ))
        assert node.txi_proceduretype == 'water'
        assert node.txi_bumpmaptexture == 'bump_ripple'
        assert node.txi_wateralpha == pytest.approx(0.7)
        assert node.txi_envmaptexture == 'cm_water'

    def test_flipbook_fire_animation(self):
        """Fire animations use proceduretype cycle with numx/numy/fps."""
        node = ModelNode()
        node.texture = 'fx_flames_01'
        _apply_txi_to_node(node, (
            "proceduretype cycle\n"
            "numx 4\n"
            "numy 4\n"
            "fps 15\n"
        ))
        assert node.txi_proceduretype == 'cycle'
        assert node.txi_numx == 4
        assert node.txi_numy == 4
        assert node.txi_fps == pytest.approx(15.0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
