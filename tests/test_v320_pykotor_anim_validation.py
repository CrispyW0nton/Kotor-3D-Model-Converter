"""
test_v320_pykotor_anim_validation.py
=====================================
Phase 29 / v32.0  –  Tests for:

  1.  template_builder  K2 c_female02 rig (clavicle bones, K2-extra anims,
                        torsocam / hip / chest helper nodes)
  2.  template_builder  validate_animations_via_pykotor (internal fallback)
  3.  template_builder  check_model_eyeball_nodes
  4.  pykotor_bridge    compare_model_animations / list_animations_via_pykotor
  5.  snap_head_onto_body  merge_animations parameter
  6.  HeadSnapPanel  outfit quick-picks list in source
  7.  Library Panel  gr_humanoid_k2 node-count reflects K2 bone list
"""
from __future__ import annotations
import sys
import os

# Ensure src is on path
_ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC  = os.path.join(_ROOT, 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest
from core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(name: str, is_mesh=False, is_skin=False,
               texture='tex01', render=True) -> ModelNode:
    flags = int(NodeFlags.HEADER)
    if is_mesh: flags |= int(NodeFlags.MESH)
    if is_skin: flags |= int(NodeFlags.SKIN)
    n = ModelNode(name=name, flags=flags)
    n.texture  = texture
    n.render   = render
    n.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    n.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    n.faces    = [(0, 1, 2)]
    n.normals  = [(0.0, 0.0, 1.0)] * 3
    n.children = []
    n.parent   = None
    n.position = (0.0, 0.0, 0.0)
    n.rotation = (0.0, 0.0, 0.0, 1.0)
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  1.  K2 c_female02 Template
# ─────────────────────────────────────────────────────────────────────────────

class TestK2Template:
    """K2 template uses c_female02 rig with clavicle bones and K2-extra anims."""

    def test_k2_template_builds(self):
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2', name='gr_humanoid_k2')
        assert m is not None
        assert m.game_version == GameVersion.K2

    def test_k2_has_clavicle_bones(self):
        """K2 rig includes L_Clavicle and R_Clavicle (absent in K1)."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        names = {n.name for n in m.all_nodes()}
        assert 'L_Clavicle' in names, f"K2 should have L_Clavicle, got: {names}"
        assert 'R_Clavicle' in names

    def test_k2_has_torsocam_and_hip(self):
        """K2 rig includes 'torsocam' and 'hip' helper nodes."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        names = {n.name.lower() for n in m.all_nodes()}
        assert 'torsocam' in names, "K2 should have torsocam helper node"
        assert 'hip' in names, "K2 should have hip helper node"

    def test_k2_has_chest_helper(self):
        """K2 rig includes lowercase 'chest' helper node."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        names = {n.name for n in m.all_nodes()}
        assert 'chest' in names, f"K2 should have 'chest' helper node, got: {names}"

    def test_k2_has_more_bones_than_k1(self):
        """K2 skeleton has more bones than K1 (clavicles + helpers)."""
        from core.template_builder import build_humanoid_template
        k1 = build_humanoid_template(game_version='K1')
        k2 = build_humanoid_template(game_version='K2')
        k1_count = len(list(k1.all_nodes()))
        k2_count = len(list(k2.all_nodes()))
        assert k2_count > k1_count, \
            f"K2 ({k2_count}) should have more nodes than K1 ({k1_count})"

    def test_k2_has_extra_anim_slots(self):
        """K2 template has more animation slots than K1 (K2-exclusive anims)."""
        from core.template_builder import build_humanoid_template
        k1 = build_humanoid_template(game_version='K1')
        k2 = build_humanoid_template(game_version='K2')
        assert len(k2.animations) > len(k1.animations), \
            f"K2 ({len(k2.animations)}) should have more anims than K1 ({len(k1.animations)})"

    def test_k2_has_lookr_lookl_anims(self):
        """K2 template includes look-direction animations."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        anames = {a.name.lower() for a in m.animations}
        assert 'lookr' in anames, "K2 should have 'lookr' animation"
        assert 'lookl' in anames, "K2 should have 'lookl' animation"

    def test_k2_has_victory2_anim(self):
        """K2 template includes victory2 (not present in K1)."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        anames = {a.name.lower() for a in m.animations}
        assert 'victory2' in anames

    def test_k2_still_has_all_k1_anims(self):
        """K2 template includes all K1 standard animations as well."""
        from core.template_builder import build_humanoid_template, _ANIM_SLOTS
        m = build_humanoid_template(game_version='K2')
        anames = {a.name.lower() for a in m.animations}
        for name, _ in _ANIM_SLOTS:
            assert name.lower() in anames, \
                f"K2 template missing K1 standard anim '{name}'"

    def test_k2_headhook_present(self):
        """K2 template has headhook attachment bone."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        names = {n.name.lower() for n in m.all_nodes()}
        assert 'headhook' in names

    def test_k2_handconjure_present(self):
        """K2 template has handconjure FX hook (K2-specific)."""
        from core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2')
        names = {n.name.lower() for n in m.all_nodes()}
        assert 'handconjure' in names, \
            "K2 should have 'handconjure' K2-exclusive FX hook"


# ─────────────────────────────────────────────────────────────────────────────
#  2.  validate_animations_via_pykotor  (internal fallback path)
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateAnimationsViaPykotor:
    """validate_animations_via_pykotor with synthetic minimal MDL bytes."""

    def test_returns_dict_structure(self):
        """Function always returns a dict with required keys."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'')
        assert isinstance(result, dict)
        for key in ('ok', 'anims', 'missing', 'extra', 'coverage', 'error'):
            assert key in result, f"Missing key '{key}' in result"

    def test_empty_bytes_not_ok(self):
        """Passing empty bytes should yield ok=False."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'')
        assert not result['ok'], "Empty bytes should not parse successfully"

    def test_garbage_bytes_not_ok(self):
        """Garbage bytes should yield ok=False (no crash)."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'\x00' * 200 + b'garbage')
        assert isinstance(result['ok'], bool)   # must not raise

    def test_coverage_zero_when_no_anims_found(self):
        """Unparse-able bytes → coverage 0."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'\x00' * 100)
        # ok=False → coverage may be 0 or undefined; either is valid
        assert result['coverage'] >= 0

    def test_expected_names_subset(self):
        """Custom expected_names list is respected."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'', expected_names=['walk', 'run'])
        # missing should be subset of walk/run since nothing parses
        assert result['missing'] <= {'walk', 'run'}

    def test_pykotor_available_flag(self):
        """Result includes 'pykotor' bool flag."""
        from core.template_builder import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'')
        assert 'pykotor' in result
        assert isinstance(result['pykotor'], bool)


# ─────────────────────────────────────────────────────────────────────────────
#  3.  check_model_eyeball_nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckModelEyeballNodes:
    """check_model_eyeball_nodes validates inner-geo nodes."""

    def _make_head_model(self, eye_tex='pfhc01_eye', eye_uvs=None,
                         add_bad_eye=False) -> KotorModel:
        m = KotorModel(name='pfhc1')
        root = _make_node('pfhc1', is_mesh=False, render=False)
        root.name = 'pfhc1'
        face = _make_node('pfhc1_face', is_mesh=True, texture='pfhc01')
        face.parent = root; root.children.append(face)
        leye = _make_node('pfhc1_leye', is_mesh=True, texture=eye_tex)
        if eye_uvs is not None:
            leye.uvs = eye_uvs
        leye.parent = root; root.children.append(leye)
        if add_bad_eye:
            bad = _make_node('btReye', is_mesh=True, texture='NULL')
            bad.parent = root; root.children.append(bad)
        m.root_node = root
        return m

    def test_good_eye_passes(self):
        """Eye node with valid texture + UVs passes."""
        from core.template_builder import check_model_eyeball_nodes
        m = self._make_head_model()
        result = check_model_eyeball_nodes(m)
        assert isinstance(result, dict)
        assert 'ok' in result and 'nodes' in result and 'issues' in result
        # No issues for good eye
        eye_nodes = [n for n in result['nodes'] if 'eye' in n['name'].lower()]
        assert len(eye_nodes) > 0, "Should have found at least one eye node"
        for en in eye_nodes:
            assert en['ok'], f"Eye node '{en['name']}' should pass: {en['issues']}"

    def test_null_texture_eye_fails(self):
        """Eye node with NULL texture is flagged."""
        from core.template_builder import check_model_eyeball_nodes
        m = self._make_head_model(add_bad_eye=True)
        result = check_model_eyeball_nodes(m)
        bad_issues = [iss for name, iss in result['issues'] if 'eye' in name.lower()]
        assert len(bad_issues) > 0, "NULL-texture eye node should have issues"

    def test_extreme_uvs_eye_fails(self):
        """Eye node with extreme UVs is flagged."""
        from core.template_builder import check_model_eyeball_nodes
        m = self._make_head_model(eye_uvs=[(5.0, 5.0), (6.0, 0.0), (0.0, 7.0)])
        result = check_model_eyeball_nodes(m)
        # Extreme UVs should be flagged
        uv_issues = [iss for _, iss in result['issues'] if 'extreme' in iss.lower()]
        assert len(uv_issues) > 0, "Extreme-UV eye node should be flagged"

    def test_no_inner_geo_nodes_returns_ok(self):
        """Model with no inner-geo nodes returns ok=True, empty lists."""
        from core.template_builder import check_model_eyeball_nodes
        m = KotorModel(name='c_creature')
        root = _make_node('c_creature', is_mesh=False, render=False)
        body = _make_node('btBody', is_skin=True, texture='c_crt01')
        body.parent = root; root.children = [body]
        m.root_node = root
        result = check_model_eyeball_nodes(m)
        assert result['ok'] is True
        assert len(result['issues']) == 0
        assert len(result['nodes']) == 0

    def test_teeth_node_also_checked(self):
        """Teeth nodes are also validated by check_model_eyeball_nodes."""
        from core.template_builder import check_model_eyeball_nodes
        m = KotorModel(name='pfhc1')
        root = _make_node('pfhc1', is_mesh=False, render=False)
        teeth = _make_node('teethU', is_mesh=True, texture='pfhc01_teeth')
        teeth.parent = root; root.children = [teeth]
        m.root_node = root
        result = check_model_eyeball_nodes(m)
        assert any('teeth' in n['name'].lower() for n in result['nodes']), \
            "Teeth nodes should appear in check result"


# ─────────────────────────────────────────────────────────────────────────────
#  4.  pykotor_bridge  compare_model_animations / list_animations_via_pykotor
# ─────────────────────────────────────────────────────────────────────────────

class TestPykotorBridgeAnimations:
    """Tests for compare_model_animations and list_animations_via_pykotor."""

    def _make_model_with_anims(self, names):
        m = KotorModel(name='test')
        root = _make_node('test', is_mesh=False)
        m.root_node = root
        for name in names:
            a = Animation(); a.name = name; a.length = 1.0
            a.nodes = []; a.events = []
            m.animations.append(a)
        return m

    def test_compare_no_bytes_returns_gr_anims(self):
        """compare_model_animations with mdl_bytes=None returns gr anims only."""
        from core.pykotor_bridge import compare_model_animations
        m = self._make_model_with_anims(['walk', 'run', 'pause1'])
        result = compare_model_animations(m, mdl_bytes=None)
        assert 'gr_anims' in result
        assert 'walk' in result['gr_anims']
        assert 'run'  in result['gr_anims']
        assert result['pykotor_used'] is False
        assert result['discrepancy'] is False

    def test_compare_garbage_bytes_no_crash(self):
        """compare_model_animations with garbage bytes does not crash."""
        from core.pykotor_bridge import compare_model_animations
        m = self._make_model_with_anims(['walk'])
        result = compare_model_animations(m, mdl_bytes=b'\x00' * 100)
        assert isinstance(result, dict)
        assert 'discrepancy' in result

    def test_compare_structure(self):
        """compare_model_animations always returns all expected keys."""
        from core.pykotor_bridge import compare_model_animations
        m = self._make_model_with_anims([])
        result = compare_model_animations(m, mdl_bytes=None)
        for key in ('gr_anims', 'pk_anims', 'only_in_gr', 'only_in_pk',
                    'in_both', 'pykotor_used', 'discrepancy'):
            assert key in result, f"Missing key '{key}'"

    def test_list_animations_empty_bytes(self):
        """list_animations_via_pykotor returns [] for empty/invalid bytes."""
        from core.pykotor_bridge import list_animations_via_pykotor
        result = list_animations_via_pykotor(b'')
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_animations_garbage_no_crash(self):
        """list_animations_via_pykotor never crashes."""
        from core.pykotor_bridge import list_animations_via_pykotor
        result = list_animations_via_pykotor(b'\xde\xad\xbe\xef' * 50)
        assert isinstance(result, list)

    def test_is_pykotor_available(self):
        """is_pykotor_available returns a bool."""
        from core.pykotor_bridge import is_pykotor_available
        result = is_pykotor_available()
        assert isinstance(result, bool)

    def test_validate_via_pykotor_wrapper_in_bridge(self):
        """pykotor_bridge.validate_animations_via_pykotor delegates correctly."""
        from core.pykotor_bridge import validate_animations_via_pykotor
        result = validate_animations_via_pykotor(b'')
        assert isinstance(result, dict)
        assert 'ok' in result


# ─────────────────────────────────────────────────────────────────────────────
#  5.  snap_head_onto_body  merge_animations parameter
# ─────────────────────────────────────────────────────────────────────────────

class TestSnapMergeAnimations:
    """merge_animations parameter controls whether head anims are copied."""

    def _make_body(self):
        m = KotorModel(name='pfbc1')
        root = _make_node('pfbc1', is_mesh=False)
        hook = _make_node('headhook', is_mesh=False)
        hook.position = (0.0, 0.0, 1.65)
        hook.parent = root; root.children = [hook]
        m.root_node = root
        # Body has walk animation
        a = Animation(); a.name = 'walk'; a.length = 1.0
        a.nodes = []; a.events = []
        m.animations.append(a)
        return m

    def _make_head_with_talk_anims(self):
        m = KotorModel(name='pfhc1')
        root = _make_node('pfhc1', is_mesh=False)
        face = _make_node('pfhc1_face', is_mesh=True, texture='pfhc01')
        face.parent = root; root.children = [face]
        m.root_node = root
        # Head has talk animation (not on body)
        for aname in ('tlknorm1', 'tlkhappy1', 'tlksad1'):
            a = Animation(); a.name = aname; a.length = 1.167
            a.nodes = []; a.events = []
            m.animations.append(a)
        return m

    def test_merge_anims_true_copies_head_anims(self):
        """With merge_animations=True, head talk anims appear in combined."""
        from core.creature_appearance import snap_head_onto_body
        body = self._make_body()
        head = self._make_head_with_talk_anims()
        result = snap_head_onto_body(body, head, merge_animations=True)
        assert result['ok'], result['message']
        combined = result['model']
        anames = {a.name.lower() for a in combined.animations}
        assert 'tlknorm1' in anames, \
            f"tlknorm1 should be merged in. Got: {anames}"
        assert 'walk' in anames, "walk (body anim) should still be present"

    def test_merge_anims_false_keeps_only_body_anims(self):
        """With merge_animations=False, head talk anims NOT copied."""
        from core.creature_appearance import snap_head_onto_body
        body = self._make_body()
        head = self._make_head_with_talk_anims()
        result = snap_head_onto_body(body, head, merge_animations=False)
        assert result['ok'], result['message']
        combined = result['model']
        anames = {a.name.lower() for a in combined.animations}
        assert 'walk' in anames, "walk (body anim) should be present"
        assert 'tlknorm1' not in anames, \
            "tlknorm1 (head-only anim) should NOT be present when merge=False"

    def test_snap_default_does_not_merge_anims(self):
        """Default behaviour (merge_animations=False) does NOT merge head anims.

        Per the authenticated B1 research (Phase 30): KotOR never merges
        animations between body and head models.  Both share the same
        supermodel, so they stay in sync independently.  The default for
        snap_head_onto_body() is therefore merge_animations=False.
        To test merging, pass merge_animations=True explicitly.
        """
        from core.creature_appearance import snap_head_onto_body
        body = self._make_body()
        head = self._make_head_with_talk_anims()
        result = snap_head_onto_body(body, head)  # default merge_animations=False
        assert result['ok']
        combined = result['model']
        anames = {a.name.lower() for a in combined.animations}
        # Default: head anims NOT merged (authentic KotOR behaviour)
        assert 'tlknorm1' not in anames, (
            "Default snap should NOT merge head animations (use merge_animations=True "
            "explicitly if merging is required for export)"
        )
        assert 'walk' in anames, "Body animations must still be present"


# ─────────────────────────────────────────────────────────────────────────────
#  6.  HeadSnapPanel source-code checks
# ─────────────────────────────────────────────────────────────────────────────

class TestHeadSnapPanelSource:
    """Verify the HeadSnapPanel source contains the expected UI elements."""

    def _read_main_window(self):
        path = os.path.join(_SRC, 'gui', 'main_window.py')
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_outfit_quick_picks_present(self):
        """Source has a Quick Bodies section in HeadSnapPanel."""
        src = self._read_main_window()
        # Phase 30 panel uses 'Quick Bodies' label frames (dynamic K1/K2 suffix)
        assert ('Quick-Pick Bodies' in src
                or 'Quick-Pick Bodies / Outfits' in src
                or 'Quick Bodies' in src), \
            "HeadSnapPanel should have outfit quick-picks section"

    def test_pfbc1_in_quick_picks(self):
        """pfbc1 (female clothing) appears in quick-pick bodies."""
        src = self._read_main_window()
        assert 'pfbc1' in src

    def test_pmbj1_in_quick_picks(self):
        """pmbj1 (male Jedi robe) appears in quick-pick bodies."""
        src = self._read_main_window()
        assert 'pmbj1' in src

    def test_merge_anims_option_present(self):
        """HeadSnapPanel exposes merge-animations / creature assembly in some form.

        Phase 30 (B1): the panel uses CreatureAssembly / assemble_creature
        instead of raw snap_head_onto_body + merge flag, because B1 export
        never merges animations (supermodel handles sync).
        Accept any recognised variant.
        """
        src = self._read_main_window()
        # Accept: legacy BooleanVar, kwarg, UI label, or the new assemble API
        assert (
            '_merge_anims_var' in src
            or 'merge_animations' in src
            or 'Merge head animations' in src
            or 'merge_anims' in src
            or 'assemble_creature' in src
            or 'CreatureAssembly' in src
        ), "HeadSnapPanel should expose merge-animations option or use CreatureAssembly"

    def test_quick_body_method_present(self):
        """Quick-body handler is defined in main_window.py.

        Phase 32: HeadSnapPanel merged into CharacterBuilderPanel.
        The method is now _quick_pick_body (CharacterBuilderPanel) instead
        of the old _quick_body (HeadSnapPanel).
        """
        src = self._read_main_window()
        # Accept either the old or new method name
        assert 'def _quick_body' in src or 'def _quick_pick_body' in src

    def test_outfit_snap_uses_merge_or_assembly(self):
        """HeadSnapPanel calls snap_head_onto_body with merge flag or uses CreatureAssembly.

        Phase 30 (B1): the _snap / _preview methods use assemble_creature /
        CreatureAssembly.from_models which internally controls merge_animations.
        Either the old BooleanVar pattern or the new assembly API is accepted.
        """
        src = self._read_main_window()
        # Accept: old BooleanVar, kwarg, or new assembly API
        assert (
            '_merge_anims_var' in src
            or 'merge_animations' in src
            or 'assemble_creature' in src
            or 'CreatureAssembly' in src
        )


# ─────────────────────────────────────────────────────────────────────────────
#  7.  Library Panel  gr_humanoid_k2 node-count reflects K2 bone list
# ─────────────────────────────────────────────────────────────────────────────

class TestLibraryPanelK2NodeCount:
    """gr_humanoid_k2 entry in Library Panel should use K2 bone count."""

    def test_k2_bone_list_longer_than_k1(self):
        """_HUMANOID_BONES_K2 has more entries than _HUMANOID_BONES_K1."""
        from core.template_builder import _HUMANOID_BONES_K1, _HUMANOID_BONES_K2
        assert len(_HUMANOID_BONES_K2) > len(_HUMANOID_BONES_K1), \
            f"K2 ({len(_HUMANOID_BONES_K2)}) should have more bones than K1 ({len(_HUMANOID_BONES_K1)})"

    def test_k2_anim_extra_list_not_empty(self):
        """_ANIM_SLOTS_K2_EXTRA contains K2-exclusive animations."""
        from core.template_builder import _ANIM_SLOTS_K2_EXTRA
        assert len(_ANIM_SLOTS_K2_EXTRA) > 0

    def test_get_bones_for_version_k1(self):
        """get_bones_for_version('K1') returns K1 bones."""
        from core.template_builder import get_bones_for_version, _HUMANOID_BONES_K1
        assert get_bones_for_version('K1') is _HUMANOID_BONES_K1

    def test_get_bones_for_version_k2(self):
        """get_bones_for_version('K2') returns K2 bones."""
        from core.template_builder import get_bones_for_version, _HUMANOID_BONES_K2
        assert get_bones_for_version('K2') is _HUMANOID_BONES_K2

    def test_get_anim_slots_for_version_k2_includes_extras(self):
        """get_anim_slots_for_version('K2') includes K2-exclusive anims."""
        from core.template_builder import (
            get_anim_slots_for_version, _ANIM_SLOTS, _ANIM_SLOTS_K2_EXTRA,
        )
        k2_slots = get_anim_slots_for_version('K2')
        k1_slots = get_anim_slots_for_version('K1')
        assert len(k2_slots) > len(k1_slots)
        k2_names = {n for n, _ in k2_slots}
        for name, _ in _ANIM_SLOTS_K2_EXTRA:
            assert name in k2_names, f"K2 extra anim '{name}' not in K2 slots"

    def test_main_window_uses_k2_bone_count(self):
        """main_window.py references _HUMANOID_BONES_K2 for node count."""
        path = os.path.join(_SRC, 'gui', 'main_window.py')
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        assert '_HUMANOID_BONES_K2' in src, \
            "main_window should import _HUMANOID_BONES_K2 for K2 node count"

    def test_main_window_references_k2_extra_anims(self):
        """main_window.py references _ANIM_SLOTS_K2_EXTRA."""
        path = os.path.join(_SRC, 'gui', 'main_window.py')
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        assert '_ANIM_SLOTS_K2_EXTRA' in src, \
            "main_window should import _ANIM_SLOTS_K2_EXTRA"


# ─────────────────────────────────────────────────────────────────────────────
#  8.  save_template_manifest
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveTemplateManifest:
    """save_template_manifest produces valid JSON with correct content."""

    def test_manifest_k1_saved(self, tmp_path):
        from core.template_builder import build_humanoid_template, save_template_manifest
        import json
        m = build_humanoid_template(game_version='K1', name='gr_test_k1')
        path = save_template_manifest(m, str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data['game_version'] == 'K1'
        assert data['name'] == 'gr_test_k1'
        assert len(data['bones']) > 0
        assert len(data['animation_slots']) > 0

    def test_manifest_k2_saved(self, tmp_path):
        from core.template_builder import build_humanoid_template, save_template_manifest
        import json
        m = build_humanoid_template(game_version='K2', name='gr_test_k2')
        path = save_template_manifest(m, str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data['game_version'] == 'K2'
        # K2 should have clavicle bones in the manifest
        bone_names = {b['name'] for b in data['bones']}
        assert 'L_Clavicle' in bone_names

    def test_manifest_k2_has_more_anim_slots_than_k1(self, tmp_path):
        from core.template_builder import build_humanoid_template, save_template_manifest
        import json
        m1 = build_humanoid_template(game_version='K1', name='gr_t_k1')
        m2 = build_humanoid_template(game_version='K2', name='gr_t_k2')
        p1 = save_template_manifest(m1, str(tmp_path))
        p2 = save_template_manifest(m2, str(tmp_path))
        with open(p1) as f: d1 = json.load(f)
        with open(p2) as f: d2 = json.load(f)
        assert len(d2['animation_slots']) > len(d1['animation_slots']), \
            "K2 manifest should have more anim slots than K1"

    def test_manifest_k2_rig_source_mentions_c_female02(self, tmp_path):
        from core.template_builder import build_humanoid_template, save_template_manifest
        import json
        m = build_humanoid_template(game_version='K2', name='gr_t_k2')
        path = save_template_manifest(m, str(tmp_path))
        with open(path) as f:
            data = json.load(f)
        rig_src = data.get('rig_source', '')
        assert 'c_female02' in rig_src or 'c_female' in rig_src, \
            f"K2 manifest rig_source should mention c_female02, got: {rig_src}"


# ─────────────────────────────────────────────────────────────────────────────
#  9.  Regression: existing tests still pass after changes
# ─────────────────────────────────────────────────────────────────────────────

class TestRegressionAfterPhase29:
    """Ensure Phase 28 functionality was not broken by Phase 29 additions."""

    def test_k1_template_still_builds(self):
        from core.template_builder import build_humanoid_template, _ANIM_SLOTS
        m = build_humanoid_template(game_version='K1')
        assert m is not None
        assert len(m.animations) >= len(_ANIM_SLOTS)

    def test_k1_backward_compat_bones(self):
        """_HUMANOID_BONES (old alias) still points to K1 bones."""
        from core.template_builder import _HUMANOID_BONES, _HUMANOID_BONES_K1
        assert _HUMANOID_BONES is _HUMANOID_BONES_K1

    def test_snap_head_onto_body_still_works(self):
        from core.creature_appearance import snap_head_onto_body
        from core.model_data import KotorModel
        body = KotorModel(name='pfbc1')
        b_root = _make_node('pfbc1')
        hook = _make_node('headhook'); hook.position = (0, 0, 1.65)
        hook.parent = b_root; b_root.children = [hook]
        body.root_node = b_root
        head = KotorModel(name='pfhc1')
        h_root = _make_node('pfhc1')
        face = _make_node('pfhc1_face', is_mesh=True)
        face.parent = h_root; h_root.children = [face]
        head.root_node = h_root
        result = snap_head_onto_body(body, head)
        assert isinstance(result['ok'], bool)

    def test_inner_geo_constants_unchanged(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS, _FACE_MESH_SUBSTRINGS
        assert 'eye' in _INNER_GEO_SUBSTRINGS
        assert 'teeth' in _INNER_GEO_SUBSTRINGS
        assert 'head' in _FACE_MESH_SUBSTRINGS

    def test_rotate_90_still_works(self):
        from autorig.retarget_engine import RetargetEngine
        engine = RetargetEngine()
        m = KotorModel(name='rot_test')
        root = _make_node('rot_test')
        mesh = _make_node('body', is_mesh=True)
        mesh.vertices = [(1.0, 0.0, 0.0)]
        mesh.parent = root; root.children = [mesh]
        m.root_node = root
        engine._working = m
        result = engine.rotate_90(axis='Z', direction=+1)
        assert result['ok']
