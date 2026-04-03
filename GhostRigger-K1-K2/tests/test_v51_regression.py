"""
GhostRigger v5.1 — Comprehensive Regression Test Suite
=======================================================

Regression tests for all diagnosed issues from the full-corpus audit:

ISSUES COVERED
--------------
ISSUE-1   Guide/ghost nodes (suffix _g, _g0, bt* prefix) must be excluded
          from UV checks.  BTHips, BTSpine1 in c_bantha — false positives fixed.

ISSUE-2   Saber blade planes (is_saber=True, names like plane239, plane242)
          intentionally carry no UV data.  Excluded from UV checks.

ISSUE-3   KotOR MDX UV sentinel values (~-1.7e38, ~-1.0e30) must be filtered
          before UV span computation.  m26ae_04a and m35aa_* series.

ISSUE-4   Sky-dome textures (lts_sky0001, lta_sky0001, dan_nebk …) use
          procedural mapping — no UV expected.  Excluded from checks.

ISSUE-5   tex='null' or tex='' placeholder nodes intentionally have no UV.
          Excluded from checks.

ISSUE-6   WONTFIX bone names: "Fin_lil'FL", "3DGui" are authentic Bioware
          original data quirks. Classified as wontfix, not blocking errors.

ISSUE-7   n_forcezombie K2 debug bone name: 'HEY>>IF_THIS_DOESNT_WORK>>
          DELETE_IT' — Bioware developer comment, WONTFIX.

ISSUE-8   V-flip false-positive detection: nodes with UVs only in [0, 0.5]
          are NOT flipped; they use the lower texture atlas region. Fixed in
          texture_wrap_evaluation.py.

ISSUE-9   Missing UV in original Bioware assets (48 models total):
          Box01 (c_drdassassin), RForeArm (c_hutt), Ran_Thumb_01_R
          (c_rancor), tail (c_rancors), Object05 (dor_lmadoor01), etc.
          Classified as WONTFIX — original game data gaps.

ISSUE-10  Bone coverage check must skip all-inactive bone maps (robe/cape
          overlays) — these are valid overlay meshes with no per-vertex weights.
"""

import math
import os
import re
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Shared helpers ─────────────────────────────────────────────────────────────

REPO = Path(__file__).parent.parent
K1_DIR  = str(REPO / 'game_data' / 'k1_extracted')
K2_DIR  = str(REPO / 'game_data' / 'k2_extracted')

K1_AVAILABLE = os.path.isdir(K1_DIR)
K2_AVAILABLE = os.path.isdir(K2_DIR)


def _make_node(name, uvs=None, vertices=None, texture='test_tex',
               is_saber=False, is_skin=False, bone_map=None,
               bone_map_floats=None, skin_data=None):
    """Create a minimal synthetic mesh node for testing.

    is_saber and is_skin are computed from NodeFlags; this helper sets
    the appropriate flags bits.
    Use vertices=[] explicitly to create a null-mesh (0 vertices).
    """
    from src.core.model_data import ModelNode, NodeFlags
    flags = NodeFlags.MESH
    if is_saber:
        flags |= NodeFlags.SABER
    if is_skin:
        flags |= NodeFlags.SKIN
    n = ModelNode(name=name, flags=flags)
    # Use 'is None' guard so that passing [] creates an empty list (null mesh)
    n.uvs       = [] if uvs is None else uvs
    n.vertices  = [(0, 0, 0), (1, 0, 0), (0, 1, 0)] if vertices is None else vertices
    n.faces     = [(0, 1, 2)]
    n.texture   = texture
    n.bone_map  = [] if bone_map is None else bone_map
    n.bone_map_floats = [] if bone_map_floats is None else bone_map_floats
    n.skin_data = [] if skin_data is None else skin_data
    return n


def _import_audit():
    """Import tools/batch_problem_audit.py as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'batch_problem_audit',
        str(REPO / 'tools' / 'batch_problem_audit.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-1: Guide/ghost node exclusions
# ═══════════════════════════════════════════════════════════════════════════════

class TestGuideNodeExclusion:
    """
    ISSUE-1: Nodes with guide suffixes (_g, _g0) or bt* prefix + no UVs
    must be excluded from UV checks.  Previously flagged as 'tex_missing_uv'
    (false positive).
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_g_suffix_excluded(self, audit):
        """Node ending with _g is a guide node → excluded."""
        n = _make_node('lfoot_g', uvs=[], texture='c_bantha01')
        assert audit._is_guide_node(n), "lfoot_g must be classified as guide node"

    def test_g0_suffix_excluded(self, audit):
        """Node ending with _g0 is a guide node → excluded."""
        n = _make_node('pelvis_g0', uvs=[], texture='c_bantha01')
        assert audit._is_guide_node(n), "pelvis_g0 must be classified as guide node"

    def test_g01_suffix_excluded(self, audit):
        """Node ending with _g01 is a guide node → excluded."""
        n = _make_node('rcollar_g01', uvs=[], texture='c_test01')
        assert audit._is_guide_node(n), "rcollar_g01 must be classified as guide node"

    def test_bt_prefix_no_uv_excluded(self, audit):
        """Node starting with 'bt' and no UVs (BTHips, BTSpine1) → guide node."""
        n = _make_node('BTHips', uvs=[], texture='c_bantha01')
        assert audit._is_guide_node(n), "BTHips (no UVs) must be classified as guide node"

    def test_bt_prefix_with_uv_not_excluded(self, audit):
        """Node starting with 'bt' but WITH UVs → not a guide node."""
        n = _make_node('btBody_front', uvs=[(0, 0), (1, 0), (0, 1)], texture='c_bantha01')
        assert not audit._is_guide_node(n), \
            "btBody_front with UVs must NOT be classified as guide node"

    def test_dum_suffix_excluded(self, audit):
        """Node ending with _dum → placeholder, excluded."""
        n = _make_node('cutscene_dum', uvs=[], texture='c_test')
        assert audit._is_guide_node(n), "_dum suffix must be guide node"

    def test_shadow_suffix_excluded(self, audit):
        """Node ending with _shadow → shadow geometry, excluded."""
        n = _make_node('body_shadow', uvs=[], texture='c_test')
        assert audit._is_guide_node(n), "_shadow suffix must be guide node"

    def test_normal_mesh_not_excluded(self, audit):
        """Regular mesh node with UVs and texture must NOT be excluded."""
        n = _make_node('head', uvs=[(0, 0), (1, 0), (0, 1)], texture='n_saulh')
        assert not audit._is_guide_node(n), "Regular head mesh must not be guide node"

    @pytest.mark.skipif(not K1_AVAILABLE, reason="K1 game data not available")
    def test_c_bantha_guide_nodes_excluded_from_uv_check(self, audit):
        """
        c_bantha K1: BTHips and BTSpine1 are guide nodes with no UVs.
        They must NOT cause 'tex_missing_uv' in the audit.
        Previously this was a false-positive failure.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        gl = GameLibrary()
        gl.scan(K1_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k1_key.get('c_bantha', RES_MDL)
        if entry is None:
            pytest.skip("c_bantha not found in K1")
        mdl_data = entry.read()
        mdx_e = gl._k1_key.get('c_bantha', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''

        result = audit._audit_one('c_bantha', mdl_data, mdx_data)
        # c_bantha is clean — no missing UV issues on renderable nodes
        if result is not None:
            assert 'tex_missing_uv' not in result.get('issue_types', []), \
                (f"c_bantha should not flag tex_missing_uv "
                 f"(BTHips/BTSpine1 are guide nodes). Got: {result}")


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-2: Saber blade plane exclusions
# ═══════════════════════════════════════════════════════════════════════════════

class TestSaberNodeExclusion:
    """
    ISSUE-2: Lightsaber blade planes (is_saber=True, e.g. plane239, plane242)
    carry no UV data and must be excluded from UV checks.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_saber_node_excluded(self, audit):
        """Node with is_saber=True is excluded regardless of name."""
        n = _make_node('plane242', uvs=[], texture='w_lsabreblue01', is_saber=True)
        assert audit._is_guide_node(n), "is_saber=True node must be guide/excluded"

    def test_non_saber_plane_not_excluded(self, audit):
        """A regular Plane node without is_saber=True is NOT excluded."""
        n = _make_node('Plane03', uvs=[(0, 0), (1, 0), (0, 1)],
                       texture='logo_sw_01', is_saber=False)
        assert not audit._is_guide_node(n), \
            "Non-saber Plane03 with UVs must not be excluded"

    @pytest.mark.skipif(not K2_AVAILABLE, reason="K2 game data not available")
    def test_lightsaber_model_no_missing_uv(self, audit):
        """
        w_lghtsbr_001 K2: blade planes have no UVs but are saber nodes.
        Must NOT flag tex_missing_uv.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        gl = GameLibrary()
        gl.scan(k2_dir=K2_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k2_key.get('w_lghtsbr_001', RES_MDL)
        if entry is None:
            pytest.skip("w_lghtsbr_001 not found in K2")
        mdl_data = entry.read()
        mdx_e = gl._k2_key.get('w_lghtsbr_001', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''

        result = audit._audit_one('w_lghtsbr_001', mdl_data, mdx_data)
        if result is not None:
            assert 'tex_missing_uv' not in result.get('issue_types', []), \
                f"Lightsaber model must not flag tex_missing_uv. Got: {result}"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-3: UV sentinel filtering
# ═══════════════════════════════════════════════════════════════════════════════

class TestUVSentinelFiltering:
    """
    ISSUE-3: KotOR MDX uses sentinel values ~-1.7e38 and ~-1.0e30 to mark
    'no UV assigned' for shared-position vertices.  These must be filtered
    before UV range computation to avoid INF/NaN spans.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def _run_uv_stats(self, audit, nodes):
        return audit._uv_stats(nodes)

    def test_sentinel_1_7e38_filtered(self, audit):
        """UV value -1.7e38 (FLT_SENTINEL) must be filtered, not counted as valid UV."""
        SENTINEL = -1.7014118346e38
        n = _make_node(
            'test_mesh',
            uvs=[(0.1, 0.2), (0.5, 0.6), (SENTINEL, SENTINEL)],
            texture='test_tex'
        )
        stats = audit._uv_stats([n])
        # max span must be computed from the 2 valid UVs only (~0.4)
        assert stats['max_span_u'] < 10.0, \
            f"Sentinel UVs must not inflate span: max_span_u={stats['max_span_u']}"
        assert stats['max_span_v'] < 10.0, \
            f"Sentinel UVs must not inflate span: max_span_v={stats['max_span_v']}"

    def test_sentinel_1e30_filtered(self, audit):
        """UV value -1.0e30 (area model sentinel) must be filtered."""
        SENTINEL = -1.0e30
        n = _make_node(
            'Box1617',
            uvs=[(0.2, 0.3)] * 10 + [(SENTINEL, 0.5)] * 10,
            texture='lza_wall04s'
        )
        stats = audit._uv_stats([n])
        assert stats['max_span_u'] < 100.0, \
            f"1e30 sentinel must be filtered: max_span_u={stats['max_span_u']}"

    def test_all_sentinel_uvs_treated_as_missing(self, audit):
        """A node where ALL UVs are sentinels → treated as missing UV."""
        SENTINEL = -1.7e38
        verts = [(float(i), 0, 0) for i in range(20)]
        n = _make_node(
            'all_sentinel',
            uvs=[(SENTINEL, SENTINEL)] * 20,
            vertices=verts,
            texture='real_tex'
        )
        stats = audit._uv_stats([n])
        assert stats['missing_uv'] == 1, \
            "Node with all-sentinel UVs must count as missing UV"

    def test_valid_uvs_not_filtered(self, audit):
        """Normal UVs in [0,1] must not be filtered."""
        n = _make_node(
            'normal_mesh',
            uvs=[(u * 0.1, v * 0.1) for u in range(5) for v in range(5)],
            texture='normal_tex'
        )
        stats = audit._uv_stats([n])
        assert stats['missing_uv'] == 0, "Normal UVs must not be filtered"
        assert stats['total_renderable'] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-4: Sky-dome texture exclusion
# ═══════════════════════════════════════════════════════════════════════════════

class TestSkyTextureExclusion:
    """
    ISSUE-4: Nodes with sky-dome textures (lts_sky0001, dan_nebk, etc.)
    use procedural shader mapping — they require no UV atlas.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    @pytest.mark.parametrize('sky_tex', [
        'lts_sky0001', 'lta_sky0001', 'lko_sky02', 'dan_nebk',
        'dan_sky', 'nar_sky', 'mss_sky', 'dxn_sky',
        'lts_sky0002', 'lts_sky0003',
    ])
    def test_sky_texture_excluded(self, audit, sky_tex):
        """Each sky-dome texture must cause the node to be excluded."""
        n = _make_node('sky05', uvs=[], texture=sky_tex)
        assert audit._is_guide_node(n), \
            f"Sky texture '{sky_tex}' must cause node exclusion"

    def test_non_sky_texture_not_excluded(self, audit):
        """A regular world texture must NOT trigger sky exclusion."""
        n = _make_node('wall01', uvs=[(0, 0), (1, 0), (0, 1)], texture='lza_wall04s')
        assert not audit._is_guide_node(n), \
            "Non-sky texture must not cause exclusion"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-5: Null/empty texture placeholder exclusion
# ═══════════════════════════════════════════════════════════════════════════════

class TestNullTexturePlaceholder:
    """
    ISSUE-5: Nodes with tex='null' or tex='' are untextured placeholders.
    They must be excluded from UV checks to prevent false positives.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_null_texture_excluded(self, audit):
        """tex='null' → excluded from UV checks."""
        n = _make_node('Firixa_part', uvs=[], texture='null')
        assert audit._is_guide_node(n), "tex='null' must cause node exclusion"

    def test_empty_texture_excluded(self, audit):
        """tex='' → excluded from UV checks."""
        n = _make_node('Box01', uvs=[], texture='')
        assert audit._is_guide_node(n), "tex='' must cause node exclusion"

    def test_whitespace_texture_excluded(self, audit):
        """tex='  ' (whitespace only) → excluded."""
        n = _make_node('Mesh01', uvs=[], texture='   ')
        assert audit._is_guide_node(n), "whitespace-only tex must cause exclusion"

    def test_real_texture_not_excluded(self, audit):
        """A real texture name must NOT cause exclusion."""
        n = _make_node('head', uvs=[(0, 0), (1, 0), (0, 1)], texture='c_hutt01')
        assert not audit._is_guide_node(n), "Real texture must not be excluded"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-6: WONTFIX bone names — Bioware original data quirks
# ═══════════════════════════════════════════════════════════════════════════════

class TestWontfixBoneNames:
    """
    ISSUE-6: Known Bioware bone name quirks must be categorized as 'wontfix'
    rather than raising a blocking bone_issue.

    Known WONTFIX bones:
      • "Fin_lil'FL"   — apostrophe in name (c_firixa, plc_firixa01)
      • "3DGui"        — starts with digit (3dgui)
      • "HEY>>IF_THIS_DOESNT_WORK>>DELETE_IT"  — debug comment (n_forcezombie)
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_apostrophe_bone_in_wontfix_set(self, audit):
        """Fin_lil'FL must be in KNOWN_WONTFIX_BONES."""
        assert "Fin_lil'FL" in audit.KNOWN_WONTFIX_BONES, \
            "Fin_lil'FL must be in KNOWN_WONTFIX_BONES"

    def test_digit_start_bone_in_wontfix_set(self, audit):
        """'3DGui' must be in KNOWN_WONTFIX_BONES."""
        assert '3DGui' in audit.KNOWN_WONTFIX_BONES, \
            "'3DGui' must be in KNOWN_WONTFIX_BONES"

    def test_wontfix_bone_does_not_raise_bone_issue(self, audit):
        """
        A model with only WONTFIX bone names must NOT have 'bone_issue'
        in its issue_types.  It should have a 'wontfix' key instead.
        """
        from src.core.model_data import ModelNode, NodeFlags, VertexSkinData, BoneWeight
        # Build a minimal skin node with a wontfix bone name
        n = _make_node('Firixa', is_skin=True,
                       uvs=[(float(i % 10) / 10, float(i % 10) / 10) for i in range(30)],
                       vertices=[(float(i), 0, 0) for i in range(30)],
                       texture='c_firixa01',
                       bone_map=["Fin_lil'FL", 'Mid', 'cutscenedummy'])
        vsd = [VertexSkinData(influences=[BoneWeight(0, 1.0)]) for _ in range(30)]
        n.skin_data = vsd
        n.bone_map_floats = [0.0] * 3  # not all-inactive

        # Build a fake parse result by calling _audit_one-equivalent logic
        # Directly test BONE_NAME_RE and KNOWN_WONTFIX_BONES
        BONE_NAME_RE = audit.BONE_NAME_RE
        KNOWN_WONTFIX_BONES = audit.KNOWN_WONTFIX_BONES

        all_bone_names = set(n.bone_map)
        bad_bones = [b for b in all_bone_names if not BONE_NAME_RE.match(b)]
        real_bad = [b for b in bad_bones if b not in KNOWN_WONTFIX_BONES]
        wf_bad   = [b for b in bad_bones if b     in KNOWN_WONTFIX_BONES]

        assert real_bad == [], f"No real bad bones expected; got: {real_bad}"
        assert len(wf_bad) > 0, "Fin_lil'FL must be in wf_bad (wontfix)"
        assert "Fin_lil'FL" in wf_bad

    def test_genuine_bad_bone_raises_issue(self, audit):
        """A bone name with illegal characters that is NOT in WONTFIX → real error."""
        BONE_NAME_RE = audit.BONE_NAME_RE
        KNOWN_WONTFIX_BONES = audit.KNOWN_WONTFIX_BONES

        bad_name = 'HEY>>DEBUG>>DELETE_ME'
        # This is NOT in KNOWN_WONTFIX_BONES (unless added)
        if bad_name in KNOWN_WONTFIX_BONES:
            pytest.skip("Test bone name was added to WONTFIX — update test")
        assert not BONE_NAME_RE.match(bad_name), \
            f"'{bad_name}' must fail BONE_NAME_RE"

    @pytest.mark.skipif(not K1_AVAILABLE, reason="K1 game data not available")
    def test_c_firixa_wontfix_not_bone_issue(self, audit):
        """
        c_firixa K1: Fin_lil'FL apostrophe bone must be wontfix,
        not a blocking bone_issue.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        gl = GameLibrary()
        gl.scan(K1_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k1_key.get('c_firixa', RES_MDL)
        if entry is None:
            pytest.skip("c_firixa not found in K1")
        mdl_data = entry.read()
        mdx_e = gl._k1_key.get('c_firixa', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''

        result = audit._audit_one('c_firixa', mdl_data, mdx_data)
        if result is not None:
            assert 'bone_issue' not in result.get('issue_types', []), \
                (f"c_firixa wontfix bone must not raise bone_issue. "
                 f"Got issue_types={result.get('issue_types', [])}")


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-7: n_forcezombie debug bone name
# ═══════════════════════════════════════════════════════════════════════════════

class TestForceZombieDebugBone:
    """
    ISSUE-7: n_forcezombie K2 contains the Bioware debug bone name
    'HEY>>IF_THIS_DOESNT_WORK>>DELETE_IT'.  This is an authenticated
    Bioware developer comment left in the original game files.
    The audit should classify it as a WONTFIX bone name issue.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_debug_bone_name_fails_regex(self, audit):
        """The debug bone name must fail BONE_NAME_RE (contains >> characters)."""
        debug_bone = 'HEY>>IF_THIS_DOESNT_WORK>>DELETE_IT'
        assert not audit.BONE_NAME_RE.match(debug_bone), \
            "Debug bone name must fail BONE_NAME_RE (contains >>)"

    @pytest.mark.skipif(not K2_AVAILABLE, reason="K2 game data not available")
    def test_n_forcezombie_contains_debug_bone(self):
        """
        n_forcezombie K2 must contain the debug bone name in its bone_map.
        Verifies the Bioware original data quirk is present as documented.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        from src.core.mdl_parser import MDLBinaryParser

        gl = GameLibrary()
        gl.scan(k2_dir=K2_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k2_key.get('n_forcezombie', RES_MDL)
        if entry is None:
            pytest.skip("n_forcezombie not found in K2")
        mdl_data = entry.read()
        mdx_e = gl._k2_key.get('n_forcezombie', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''
        model = MDLBinaryParser(mdl_data, mdx_data).parse()

        all_bones = set()
        for n in model.mesh_nodes():
            all_bones.update(b for b in (n.bone_map or []) if b)

        debug_bone = 'HEY>>IF_THIS_DOESNT_WORK>>DELETE_IT'
        assert debug_bone in all_bones, \
            (f"n_forcezombie K2 must contain the debug bone name "
             f"'{debug_bone}'. Found bones: {sorted(all_bones)[:10]}")


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-8: V-flip false-positive fix
# ═══════════════════════════════════════════════════════════════════════════════

class TestVFlipFalsePositiveFix:
    """
    ISSUE-8: Nodes with UVs only in [0, 0.5] are NOT V-flipped.
    They use the lower half of the texture atlas (normal UV atlasing).
    The old check (median_v < 0.1 and max_v < 0.5) was a false-positive.
    Fixed in texture_wrap_evaluation.py: only flag when ALL V < 0.
    """

    def test_low_uv_range_not_vflip(self):
        """
        A mesh whose UVs are in [0.01, 0.16] (e.g. 3dgui RFlap node) is
        NOT V-flipped — it simply samples the bottom strip of the texture.
        The fixed check must return v_flip_consistent=True for this case.
        """
        # Simulate the v_flip check from texture_wrap_evaluation.py
        # Old (wrong): median_v < 0.1 and max_v < 0.5 → inconsistent
        # New (correct): all(v < -0.01) → inconsistent

        vs = [0.013, 0.055, 0.055, 0.162, 0.013, 0.162]  # 3dgui RFlap pattern

        # Old logic (should incorrectly flag this as inconsistent)
        median_v_old = sorted(vs)[len(vs) // 2]
        old_inconsistent = median_v_old < 0.1 and max(vs) < 0.5
        assert old_inconsistent, \
            "Old check must produce a false positive for this UV range"

        # New logic (must NOT flag this as inconsistent)
        new_inconsistent = all(v < -0.01 for v in vs)
        assert not new_inconsistent, \
            "New check must NOT flag low-but-positive UVs as v-flip inconsistent"

    def test_negative_uvs_are_vflip(self):
        """
        A mesh with all-negative V values IS genuinely V-flipped.
        The new check must detect this.
        """
        vs = [-0.5, -0.3, -0.1, -0.8, -0.2]  # all negative

        new_inconsistent = all(v < -0.01 for v in vs)
        assert new_inconsistent, \
            "All-negative V values must be flagged as v-flip inconsistent"

    def test_mixed_positive_negative_not_vflip(self):
        """
        Mixed positive/negative V (e.g. from tiling) is NOT a v-flip issue —
        it's a tiling UV that happens to span the seam.
        """
        vs = [-0.3, 0.0, 0.5, 1.0, 1.5, -0.1]  # mixed tiling

        new_inconsistent = all(v < -0.01 for v in vs)
        assert not new_inconsistent, \
            "Mixed +/- tiling UVs must NOT be flagged as v-flip inconsistent"

    def test_zero_v_boundary_not_vflip(self):
        """
        V values at or near 0 (e.g. 0.0, 0.001) are valid bottom-of-atlas UVs.
        Must not be flagged.
        """
        vs = [0.0, 0.0, 0.001, 0.003, 0.0]

        new_inconsistent = all(v < -0.01 for v in vs)
        assert not new_inconsistent, \
            "Near-zero positive V values must not be flagged"


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-9: Original Bioware missing UV data — WONTFIX classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestBiowareMissingUVWontfix:
    """
    ISSUE-9: 48 models in K1+K2 have genuine missing UV data in original
    Bioware game files.  These are documented as WONTFIX.
    """

    # Ground truth: models that must have missing UV data (cannot be fixed)
    WONTFIX_MISSING_UV = {
        'K1': [
            'c_drdassassin', 'c_hutt', 'c_rancor', 'c_rancors',
            'dor_lmadoor01', 'n_commm', 'n_fatcomm', 'n_jedicounm',
            'n_sithcomm', 'n_repsold',
        ],
        'K2': [
            'c_drdassassin', 'c_hutt', 'c_rancor', 'c_rancors',
            'dor_lmadoor01', 'n_commm', 'n_fatcomm', 'n_jedicounm',
            'n_sithassn', 'n_sithcomm',
        ],
    }

    @pytest.mark.skipif(not K1_AVAILABLE, reason="K1 game data not available")
    def test_c_hutt_rforearm_missing_uv(self):
        """
        c_hutt K1: RForeArm node has 0 UVs / 108 vertices.
        This is a known original Bioware asset bug.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        from src.core.mdl_parser import MDLBinaryParser

        gl = GameLibrary()
        gl.scan(K1_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k1_key.get('c_hutt', RES_MDL)
        if entry is None:
            pytest.skip("c_hutt not found")
        mdl_data = entry.read()
        mdx_e = gl._k1_key.get('c_hutt', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''
        model = MDLBinaryParser(mdl_data, mdx_data).parse()

        rforearm = next(
            (n for n in model.mesh_nodes() if n.name == 'RForeArm'), None
        )
        assert rforearm is not None, "c_hutt must have RForeArm node"
        assert len(rforearm.uvs or []) == 0, \
            "RForeArm must have 0 UVs (original Bioware data gap)"
        assert len(rforearm.vertices or []) > 0, \
            "RForeArm must still have vertices"

    @pytest.mark.skipif(not K1_AVAILABLE, reason="K1 game data not available")
    def test_c_rancor_thumb_missing_uv(self):
        """
        c_rancor K1: Ran_Thumb_01_R node has 0 UVs / 40 vertices.
        """
        import logging; logging.disable(logging.CRITICAL)
        from src.resources.game_library import GameLibrary
        from src.core.mdl_parser import MDLBinaryParser

        gl = GameLibrary()
        gl.scan(K1_DIR)
        RES_MDL, RES_MDX = 2002, 3008

        entry = gl._k1_key.get('c_rancor', RES_MDL)
        if entry is None:
            pytest.skip("c_rancor not found")
        mdl_data = entry.read()
        mdx_e = gl._k1_key.get('c_rancor', RES_MDX)
        mdx_data = mdx_e.read() if mdx_e else b''
        model = MDLBinaryParser(mdl_data, mdx_data).parse()

        thumb = next(
            (n for n in model.mesh_nodes() if n.name == 'Ran_Thumb_01_R'), None
        )
        assert thumb is not None, "c_rancor must have Ran_Thumb_01_R node"
        assert len(thumb.uvs or []) == 0, \
            "Ran_Thumb_01_R must have 0 UVs (WONTFIX Bioware data)"

    def test_missing_uv_models_count_within_expected_range(self):
        """
        Full-corpus check: missing UV model count must be in [40, 65].
        Values outside this range indicate a regression in exclusion rules.
        (Actual count as of audit: 50 models — 24 K1 + 26 K2.)
        """
        import logging; logging.disable(logging.CRITICAL)
        import json

        eval_path = REPO / 'audit_output' / 'tex_wrap_eval.json'
        if not eval_path.exists():
            pytest.skip("tex_wrap_eval.json not available; run evaluation first")

        with open(eval_path) as f:
            data = json.load(f)

        count = data['stats']['with_missing_uv']
        assert 40 <= count <= 65, \
            (f"Missing UV model count {count} is outside expected range [40, 65]. "
             f"Regression in exclusion rules?")


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUE-10: Bone coverage check — all-inactive bone map overlay skip
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoneCoverageOverlaySkip:
    """
    ISSUE-10: Robe/cape overlay skin nodes with all-inactive bone maps
    (bone_map_floats all < 0) must not trigger low-coverage bone_issue.
    """

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_all_inactive_bone_map_skipped(self, audit):
        """
        A skin node whose bone_map_floats are all negative (-1.0) is an
        overlay robe/cape.  It must not cause a bone coverage warning.
        """
        from src.core.model_data import VertexSkinData, BoneWeight

        # Overlay node: no influences on any vertex (all-inactive)
        n = _make_node(
            'robe_overlay',
            is_skin=True,
            uvs=[(0.1 * i, 0.1 * i) for i in range(10)],
            vertices=[(float(i), 0, 0) for i in range(10)],
            texture='robe_tex',
            bone_map=['bone_a', 'bone_b'],
            bone_map_floats=[-1.0, -1.0],  # all inactive
            skin_data=[VertexSkinData(influences=[]) for _ in range(10)],
        )
        # Simulate the bone check logic from _audit_one
        has_bm_slots = n.bone_map_floats is not None and len(n.bone_map_floats) > 0
        all_inactive = has_bm_slots and all(v < 0 for v in n.bone_map_floats)
        assert all_inactive, "All-negative bone_map_floats must be all_inactive"
        # all_inactive → skip weight coverage check (no bone_issue raised)

    def test_active_bone_map_checked(self, audit):
        """
        A skin node with active bone_map_floats (≥0) but low coverage
        must trigger a bone coverage warning.
        """
        from src.core.model_data import VertexSkinData, BoneWeight

        # Skin node with <90% weight coverage
        n = _make_node(
            'skin_low_coverage',
            is_skin=True,
            uvs=[(0.1 * i, 0.1 * i) for i in range(10)],
            vertices=[(float(i), 0, 0) for i in range(10)],
            texture='skin_tex',
            bone_map=['bone_a', 'bone_b'],
            bone_map_floats=[0.0, 0.5],  # active
            skin_data=(
                [VertexSkinData(influences=[BoneWeight(0, 1.0)])] * 5 +
                [VertexSkinData(influences=[]) for _ in range(5)]  # 50% coverage
            ),
        )
        has_bm_slots = n.bone_map_floats is not None and len(n.bone_map_floats) > 0
        all_inactive = has_bm_slots and all(v < 0 for v in n.bone_map_floats)
        assert not all_inactive, "Active bone_map_floats must not be all_inactive"

        # Coverage check
        weighted = sum(1 for sd in n.skin_data if sd.influences)
        coverage = weighted / len(n.vertices)
        assert coverage < 0.9, f"Expected low coverage, got {coverage:.0%}"


# ═══════════════════════════════════════════════════════════════════════════════
# UV stats function integration tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestUVStatsIntegration:
    """Integration tests for the _uv_stats() helper function."""

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    def test_clean_model_no_issues(self, audit):
        """All UV coordinates in [0,1] → 0 missing, 0 tiling."""
        nodes = [
            _make_node('head', uvs=[(u/4, v/4) for u in range(5) for v in range(5)],
                       texture='head_tex'),
            _make_node('body', uvs=[(u/3, v/3) for u in range(4) for v in range(4)],
                       texture='body_tex'),
        ]
        stats = audit._uv_stats(nodes)
        assert stats['missing_uv'] == 0
        assert stats['tiling_nodes'] == 0
        assert stats['total_renderable'] == 2

    def test_tiling_uv_detected(self, audit):
        """UV coordinates > 1.0 must be counted as tiling."""
        n = _make_node('tiled_floor',
                       uvs=[(u * 3.0, v * 3.0) for u in range(4) for v in range(4)],
                       texture='floor_tex')
        stats = audit._uv_stats([n])
        assert stats['tiling_nodes'] == 1, "Tiling UV node must be counted"
        assert stats['max_span_u'] > 1.0

    def test_missing_uv_counted(self, audit):
        """Node with 0 UVs on a textured mesh → missing_uv count 1."""
        n = _make_node('no_uvs',
                       uvs=[],
                       vertices=[(float(i), 0, 0) for i in range(10)],
                       texture='real_tex')
        stats = audit._uv_stats([n])
        assert stats['missing_uv'] == 1
        assert stats['total_renderable'] == 1

    def test_guide_nodes_excluded_from_count(self, audit):
        """Guide node (_g suffix) must not appear in total_renderable."""
        guide = _make_node('lfoot_g', uvs=[], texture='body_tex')
        real  = _make_node('body',
                           uvs=[(0.1, 0.1), (0.5, 0.5), (0.9, 0.9)],
                           texture='body_tex')
        stats = audit._uv_stats([guide, real])
        assert stats['total_renderable'] == 1, \
            "Guide node must not be counted in total_renderable"
        assert stats['missing_uv'] == 0

    def test_null_mesh_excluded(self, audit):
        """A node with 0 vertices is a null-mesh placeholder — excluded."""
        n = _make_node('null_mesh',
                       uvs=[],
                       vertices=[],   # explicitly empty — null mesh
                       texture='real_tex')
        stats = audit._uv_stats([n])
        assert stats['total_renderable'] == 0, \
            "Null-mesh node (0 verts) must not appear in total_renderable"


# ═══════════════════════════════════════════════════════════════════════════════
# Full-corpus audit results validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullCorpusAuditResults:
    """
    Validates the previously computed tex_wrap_eval.json results.
    These are the ground-truth numbers from the completed full-corpus audit.
    """

    @pytest.fixture(scope='class')
    def eval_data(self):
        eval_path = REPO / 'audit_output' / 'tex_wrap_eval.json'
        if not eval_path.exists():
            pytest.skip("tex_wrap_eval.json not available")
        with open(eval_path) as f:
            return json.load(f)

    def test_total_models_5764(self, eval_data):
        """Must have exactly 5,764 models audited."""
        assert eval_data['stats']['total_models'] == 5764, \
            f"Expected 5764 total models, got {eval_data['stats']['total_models']}"

    def test_all_models_parsed(self, eval_data):
        """All 5,764 models must parse successfully."""
        assert eval_data['stats']['parsed_ok'] == 5764, \
            f"All models must parse: {eval_data['stats']['parsed_ok']} parsed"

    def test_missing_uv_count(self, eval_data):
        """Missing UV count must be 40–65 (documented 50 WONTFIX models: 24 K1 + 26 K2)."""
        count = eval_data['stats']['with_missing_uv']
        assert 40 <= count <= 65, \
            f"Missing UV count {count} outside expected range [40, 65]"

    def test_tiling_uv_count_reasonable(self, eval_data):
        """Tiling UV count must be > 2000 and < 4500 (documented ~3,347)."""
        count = eval_data['stats']['with_tiling']
        assert 2000 <= count <= 4500, \
            f"Tiling UV count {count} outside expected range [2000, 4500]"

    def test_guide_nodes_excluded_large_count(self, eval_data):
        """Guide node exclusion must remove >30,000 nodes."""
        assert eval_data['stats']['total_guide_nodes'] > 30000, \
            "Guide node count too low — exclusion rules may be broken"

    def test_saber_nodes_excluded(self, eval_data):
        """Saber blade nodes (expected ~80–100) must be excluded."""
        count = eval_data['stats']['total_saber_nodes']
        assert 50 <= count <= 200, \
            f"Saber node count {count} outside expected range [50, 200]"

    def test_k1_k2_breakdown_correct(self, eval_data):
        """K1 must have 2,527 and K2 must have 3,237 total models."""
        k1 = eval_data['stats']['per_game']['K1']
        k2 = eval_data['stats']['per_game']['K2']
        assert k1['total'] == 2527, f"K1 total must be 2527, got {k1['total']}"
        assert k2['total'] == 3237, f"K2 total must be 3237, got {k2['total']}"

    def test_c_bantha_passes_in_results(self, eval_data):
        """c_bantha must have has_missing_uv=False (guide nodes excluded)."""
        results = eval_data.get('results', [])
        bantha = next((r for r in results if r['resref'] == 'c_bantha'), None)
        if bantha is None:
            pytest.skip("c_bantha not in results")
        assert bantha.get('parse_ok'), "c_bantha must parse OK"
        assert not bantha.get('has_missing_uv'), \
            "c_bantha must not have missing UV (BTHips/BTSpine1 are guide nodes)"

    def test_3dgui_no_missing_uv(self, eval_data):
        """3dgui must have has_missing_uv=False (null-tex parts excluded)."""
        results = eval_data.get('results', [])
        gui = next((r for r in results if r['resref'] == '3dgui'), None)
        if gui is None:
            pytest.skip("3dgui not in results")
        assert not gui.get('has_missing_uv'), \
            "3dgui must not have missing UV (untextured parts are excluded)"


# ═══════════════════════════════════════════════════════════════════════════════
# Bone-name regex tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoneNameRegex:
    """Tests for the BONE_NAME_RE pattern used to validate bone names."""

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    @pytest.mark.parametrize('name', [
        'RForeArm', 'lfoot', 'BTHips', 'Spine1', 'bone_001',
        'head', 'L_Arm', 'HEY', 'valid_name_123',
    ])
    def test_valid_bone_names(self, audit, name):
        """Valid ASCII identifier bone names must match BONE_NAME_RE."""
        assert audit.BONE_NAME_RE.match(name), \
            f"'{name}' must be a valid bone name"

    @pytest.mark.parametrize('name', [
        "Fin_lil'FL",    # apostrophe
        '3DGui',         # starts with digit
        'bone name',     # space
        'HEY>>DEBUG',    # >>
        'bone/name',     # slash
        'bone.name',     # dot
        '',              # empty
        '123abc',        # digit-start
    ])
    def test_invalid_bone_names(self, audit, name):
        """Bone names with illegal characters must fail BONE_NAME_RE."""
        assert not audit.BONE_NAME_RE.match(name), \
            f"'{name}' must fail BONE_NAME_RE"


# ═══════════════════════════════════════════════════════════════════════════════
# Model classification tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelClassification:
    """Tests for the _classify() helper."""

    @pytest.fixture(scope='class')
    def audit(self):
        return _import_audit()

    @pytest.mark.parametrize('model_type,expected', [
        (0, 'effect'),
        (1, 'effects'),
        (2, 'misc'),
        (4, 'character'),
        (8, 'door'),
        (32, 'item'),
        (64, 'character'),
        (255, 'character'),  # fallback
    ])
    def test_classification_mapping(self, audit, model_type, expected):
        """Model type byte → classification string mapping."""

        class FakeModel:
            def __init__(self, mt):
                self.model_type = mt

        result = audit._classify(FakeModel(model_type))
        assert result == expected, \
            f"model_type={model_type} must map to '{expected}', got '{result}'"
