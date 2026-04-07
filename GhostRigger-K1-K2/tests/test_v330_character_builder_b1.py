"""
test_v330_character_builder_b1.py
==================================
Phase 30 — Authentic KotOR Character Builder tests.

Covers:
  1. CreatureAssembly.from_models() — dual-model engine simulation
  2. _find_headhook_node() — strict vs fallback, warning on non-standard name
  3. _validate_supermodel_pair() — matching, mismatch, missing
  4. _infer_supermodel() — K1 male/female/default, K2
  5. CreatureAssembly.export_separate() — Option B1 two-file export
       • supermodel agreement (no change needed)
       • supermodel mismatch (fixed automatically)
       • body has SM, head doesn't (head gets body's SM)
       • neither has SM (both get inferred SM)
  6. snap_head_onto_body() — corrected: head root as child of headhook,
       no vertex movement, no animation merging by default
  7. assemble_creature() — high-level wrapper, preview + export_separate modes
  8. K1 vs K2 supermodel defaults
  9. Regression: old tests that used snap_head_onto_body still pass
 10. CreatureAssembly.from_resrefs() — mock resource manager path
"""

import sys
import os
import copy
import types

# ── path setup ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


# ── minimal mock helpers ─────────────────────────────────────────────────────

class MockNode:
    """Minimal stand-in for a KotOR model node."""
    def __init__(self, name, position=None, parent=None, children=None,
                 is_mesh=False, is_skin=False, vertices=None):
        self.name     = name
        self.position = position or (0.0, 0.0, 0.0)
        self.parent   = parent
        self.children = children if children is not None else []
        self.is_mesh  = is_mesh
        self.is_skin  = is_skin
        self.vertices = vertices or []


class MockModel:
    """Minimal stand-in for a KotorModel."""
    def __init__(self, name, supermodel='s_female02', nodes=None):
        self.name       = name
        self.supermodel = supermodel
        self._nodes     = nodes or []
        self.root_node  = self._nodes[0] if self._nodes else None
        self.bb_min     = (0.0, 0.0, 0.0)
        self.bb_max     = (0.0, 0.0, 1.8)

    def all_nodes(self):
        """BFS over all nodes."""
        result, queue = [], list(self._nodes)
        seen = set()
        while queue:
            n = queue.pop(0)
            if id(n) in seen:
                continue
            seen.add(id(n))
            result.append(n)
            queue.extend(getattr(n, 'children', []))
        return result

    def compute_bounds(self):
        pass


def _make_body_model(name='pmbc1', supermodel='s_female02',
                     hook_name='headhook', hook_z=1.5):
    """Build a body model with a headhook node."""
    root    = MockNode('Mesh_Root', position=(0.0, 0.0, 0.0))
    pelvis  = MockNode('Pelvis',    position=(0.0, 0.0, 0.5),  parent=root)
    neck    = MockNode('Neck',      position=(0.0, 0.0, 1.0),  parent=pelvis)
    hook    = MockNode(hook_name,   position=(0.0, 0.0, hook_z), parent=neck)
    torso   = MockNode('Torso',     position=(0.0, 0.0, 0.8),
                       is_mesh=True, parent=root)
    root.children    = [pelvis, torso]
    pelvis.children  = [neck]
    neck.children    = [hook]
    return MockModel(name, supermodel=supermodel,
                     nodes=[root, pelvis, neck, hook, torso])


def _make_head_model(name='pmhc1', supermodel='s_female02'):
    """Build a head model with a skull → jaw/eye hierarchy."""
    root  = MockNode('Mesh_Root',  position=(0.0, 0.0, 0.0))
    skull = MockNode('skull',      position=(0.0, 0.0, 0.05), parent=root,
                     is_mesh=True)
    jaw   = MockNode('jaw',        position=(0.0, 0.0, -0.1), parent=skull)
    eye_r = MockNode('btReye',     position=(0.05, 0.0, 0.0), parent=skull,
                     is_mesh=True)
    eye_l = MockNode('btLeye',     position=(-0.05, 0.0, 0.0), parent=skull,
                     is_mesh=True)
    root.children  = [skull]
    skull.children = [jaw, eye_r, eye_l]
    return MockModel(name, supermodel=supermodel,
                     nodes=[root, skull, jaw, eye_r, eye_l])


# ═══════════════════════════════════════════════════════════════════════════════
# 1. _find_headhook_node
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindHeadhookNode:
    def test_finds_exact_headhook(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='headhook')
        node, used_fb = _find_headhook_node(body, strict=False)
        assert node is not None
        assert node.name == 'headhook'
        assert used_fb is False

    def test_strict_mode_exact_name_found(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='headhook')
        node, used_fb = _find_headhook_node(body, strict=True)
        assert node is not None
        assert used_fb is False

    def test_strict_mode_fallback_not_found(self):
        from core.creature_appearance import _find_headhook_node
        # headpoint is a fallback name; strict mode should return None
        body = _make_body_model(hook_name='headpoint')
        node, used_fb = _find_headhook_node(body, strict=True)
        assert node is None

    def test_fallback_headpoint_found_in_nonstrict(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='headpoint')
        node, used_fb = _find_headhook_node(body, strict=False)
        assert node is not None
        assert node.name == 'headpoint'
        assert used_fb is True

    def test_fallback_neck_found(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='neckjoint')
        node, used_fb = _find_headhook_node(body, strict=False)
        assert node is not None
        assert used_fb is True

    def test_returns_none_when_no_hook(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='shoulder')
        node, used_fb = _find_headhook_node(body, strict=False)
        assert node is None

    def test_case_insensitive(self):
        from core.creature_appearance import _find_headhook_node
        body = _make_body_model(hook_name='HeadHook')
        # lowercase compare should still find it
        node, used_fb = _find_headhook_node(body, strict=False)
        # 'HeadHook'.lower() == 'headhook' — should match exact
        assert node is not None
        assert used_fb is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. _validate_supermodel_pair
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateSupermodelPair:
    def test_matching_supermodels_no_warnings(self):
        from core.creature_appearance import _validate_supermodel_pair
        body = _make_body_model(supermodel='s_female02')
        head = _make_head_model(supermodel='s_female02')
        warnings = _validate_supermodel_pair(body, head, game='K1')
        assert warnings == []

    def test_mismatched_supermodels_warns(self):
        from core.creature_appearance import _validate_supermodel_pair
        body = _make_body_model(supermodel='s_female02')
        head = _make_head_model(supermodel='s_male01')
        warnings = _validate_supermodel_pair(body, head, game='K1')
        assert len(warnings) == 1
        assert 's_female02' in warnings[0]
        assert 's_male01' in warnings[0]

    def test_body_missing_supermodel_warns(self):
        from core.creature_appearance import _validate_supermodel_pair
        body = _make_body_model(supermodel='')
        head = _make_head_model(supermodel='s_female02')
        warnings = _validate_supermodel_pair(body, head, game='K1')
        assert len(warnings) == 1
        assert 'no supermodel' in warnings[0].lower() or 'not set' in warnings[0].lower() \
            or 'pmbc1' in warnings[0] or 'body' in warnings[0].lower()

    def test_head_missing_supermodel_warns(self):
        from core.creature_appearance import _validate_supermodel_pair
        body = _make_body_model(supermodel='s_female02')
        head = _make_head_model(supermodel='')
        warnings = _validate_supermodel_pair(body, head, game='K1')
        assert len(warnings) == 1

    def test_both_null_supermodel_warns(self):
        from core.creature_appearance import _validate_supermodel_pair
        body = _make_body_model(supermodel='NULL')
        head = _make_head_model(supermodel='NULL')
        warnings = _validate_supermodel_pair(body, head, game='K1')
        assert len(warnings) >= 1  # at least one warning for missing SM


# ═══════════════════════════════════════════════════════════════════════════════
# 3. _infer_supermodel
# ═══════════════════════════════════════════════════════════════════════════════

class TestInferSupermodel:
    def test_k1_male_body(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pmbc1', 'K1') == 's_female02'

    def test_k1_female_body(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pfbc1', 'K1') == 's_female03'

    def test_k1_male_head(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pmhc1', 'K1') == 's_female02'

    def test_k1_female_head(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pfhc1', 'K1') == 's_female03'

    def test_k2_male(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pmbc1', 'K2') == 's_female02'

    def test_k2_female(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('pfbc1', 'K2') == 's_female03'

    def test_unknown_prefix_returns_default(self):
        from core.creature_appearance import _infer_supermodel
        sm = _infer_supermodel('n_alien01', 'K1')
        assert sm == 's_female02'  # default

    def test_k2_default_same_as_k1_default(self):
        from core.creature_appearance import _infer_supermodel
        assert _infer_supermodel('n_alien', 'K2') == _infer_supermodel('n_alien', 'K1')


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CreatureAssembly.from_models()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreatureAssemblyFromModels:
    def test_basic_success_k1(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model('pmbc1', supermodel='s_female02')
        head = _make_head_model('pmhc1', supermodel='s_female02')
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert asm.ok is True
        assert asm.headhook_node is not None
        assert asm.headhook_node.name == 'headhook'
        assert asm.headhook_world_pos is not None
        assert asm.game == 'K1'

    def test_basic_success_k2(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model('pfbc1', supermodel='s_female03')
        head = _make_head_model('pfhc1', supermodel='s_female03')
        asm = CreatureAssembly.from_models(body, head, game='K2')
        assert asm.ok is True
        assert asm.game == 'K2'

    def test_fails_with_no_body(self):
        from core.creature_appearance import CreatureAssembly
        head = _make_head_model()
        asm = CreatureAssembly.from_models(None, head, game='K1')
        assert asm.ok is False
        assert 'body' in asm.message.lower()

    def test_fails_with_no_head(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model()
        asm = CreatureAssembly.from_models(body, None, game='K1')
        assert asm.ok is False
        assert 'head' in asm.message.lower()

    def test_fails_when_no_headhook(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model(hook_name='shoulder')
        head = _make_head_model()
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert asm.ok is False
        assert 'headhook' in asm.message.lower()

    def test_headhook_world_pos_above_zero(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model(hook_z=1.5)
        head = _make_head_model()
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert asm.ok is True
        assert asm.headhook_world_pos[2] > 0.0

    def test_supermodel_mismatch_warns_but_ok(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model(supermodel='s_female02')
        head = _make_head_model(supermodel='s_male01')
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert asm.ok is True       # still assembles
        assert len(asm.warnings) >= 1
        assert any('mismatch' in w.lower() or 'female02' in w.lower()
                   for w in asm.warnings)

    def test_fallback_hook_name_warns(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model(hook_name='headpoint')
        head = _make_head_model()
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert asm.ok is True
        assert asm._used_fallback_hook is True
        assert any('headhook' in w.lower() or 'headpoint' in w.lower()
                   for w in asm.warnings)

    def test_body_models_not_mutated(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model()
        head = _make_head_model()
        body_node_names_before = [n.name for n in body.all_nodes()]
        head_node_names_before = [n.name for n in head.all_nodes()]
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert [n.name for n in body.all_nodes()] == body_node_names_before
        assert [n.name for n in head.all_nodes()] == head_node_names_before

    def test_message_contains_model_names(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model('pmbc1')
        head = _make_head_model('pmhc1')
        asm = CreatureAssembly.from_models(body, head, game='K1')
        assert 'pmbc1' in asm.message
        assert 'pmhc1' in asm.message


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CreatureAssembly.export_separate() — Option B1
# ═══════════════════════════════════════════════════════════════════════════════

class TestExportSeparate:
    def _make_asm(self, body_sm='s_female02', head_sm='s_female02',
                  game='K1', hook='headhook'):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model(supermodel=body_sm, hook_name=hook)
        head = _make_head_model(supermodel=head_sm)
        return CreatureAssembly.from_models(body, head, game=game)

    def test_returns_two_model_objects(self):
        asm = self._make_asm()
        result = asm.export_separate()
        assert result['ok'] is True
        assert result['body_model'] is not None
        assert result['head_model'] is not None

    def test_body_and_head_model_names_present(self):
        asm = self._make_asm()
        result = asm.export_separate()
        assert result['body_name'] == 'pmbc1'
        assert result['head_name'] == 'pmhc1'

    def test_supermodel_agreement_no_warnings(self):
        asm = self._make_asm(body_sm='s_female02', head_sm='s_female02')
        result = asm.export_separate()
        assert result['supermodel'] == 's_female02'
        # No supermodel-mismatch warnings expected
        sm_warnings = [w for w in result['warnings']
                       if 'mismatch' in w.lower() or 'set to' in w.lower()]
        assert len(sm_warnings) == 0

    def test_supermodel_mismatch_fixed(self):
        asm = self._make_asm(body_sm='s_female02', head_sm='s_male01')
        result = asm.export_separate()
        assert result['ok'] is True
        # Both models now have the same supermodel
        assert result['body_model'].supermodel == result['head_model'].supermodel
        # A warning should mention the fix
        assert any('mismatch' in w.lower() or 'set to' in w.lower()
                   for w in result['warnings'])

    def test_body_has_sm_head_does_not(self):
        asm = self._make_asm(body_sm='s_female02', head_sm='')
        result = asm.export_separate()
        assert result['ok'] is True
        assert result['head_model'].supermodel == 's_female02'
        assert any('no supermodel' in w.lower() or 'set to' in w.lower()
                   for w in result['warnings'])

    def test_head_has_sm_body_does_not(self):
        asm = self._make_asm(body_sm='', head_sm='s_female02')
        result = asm.export_separate()
        assert result['ok'] is True
        assert result['body_model'].supermodel == 's_female02'

    def test_neither_has_sm_inferred(self):
        asm = self._make_asm(body_sm='NULL', head_sm='NULL')
        result = asm.export_separate()
        assert result['ok'] is True
        assert result['supermodel'] != ''
        assert result['supermodel'] not in ('null', 'NULL', 'none')

    def test_original_models_not_mutated(self):
        """export_separate should work on deep copies."""
        asm = self._make_asm(body_sm='s_female02', head_sm='s_male01')
        body_sm_before = asm.body_model.supermodel
        head_sm_before = asm.head_model.supermodel
        asm.export_separate()
        assert asm.body_model.supermodel == body_sm_before
        assert asm.head_model.supermodel == head_sm_before

    def test_k2_assembly_export(self):
        asm = self._make_asm(body_sm='s_female03', head_sm='s_female03', game='K2')
        result = asm.export_separate()
        assert result['ok'] is True
        assert result['supermodel'] == 's_female03'

    def test_export_fails_when_assembly_failed(self):
        from core.creature_appearance import CreatureAssembly
        asm = CreatureAssembly()  # no models set
        result = asm.export_separate()
        assert result['ok'] is False

    def test_body_name_lowercase(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model('PMBC1')
        head = _make_head_model('PMHC1')
        asm = CreatureAssembly.from_models(body, head, game='K1')
        result = asm.export_separate()
        assert result['body_name'] == 'pmbc1'
        assert result['head_name'] == 'pmhc1'


# ═══════════════════════════════════════════════════════════════════════════════
# 6. snap_head_onto_body() — corrected implementation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnapHeadOntoBody:
    def test_basic_success(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok'] is True
        assert result['model'] is not None

    def test_head_root_is_child_of_headhook(self):
        """The head's root node must become a direct child of the headhook bone."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok'] is True
        combined = result['model']
        # Find the headhook node in the combined model
        hook = None
        for n in combined.all_nodes():
            if n.name.lower() == 'headhook':
                hook = n
                break
        assert hook is not None
        # The head's root node (Mesh_Root) must be a direct child of hook
        child_names = [c.name for c in hook.children]
        assert 'Mesh_Root' in child_names

    def test_head_skeleton_preserved(self):
        """The jaw, eyeball bones must still be under the head root after snap."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        combined = result['model']
        all_names = {n.name for n in combined.all_nodes()}
        assert 'skull' in all_names
        assert 'jaw' in all_names
        assert 'btReye' in all_names
        assert 'btLeye' in all_names

    def test_no_scaling_by_default(self):
        """Default scale_head=False — no vertex distortion."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        # Give skull a known vertex
        for n in head.all_nodes():
            if n.name == 'skull':
                n.vertices = [(0.1, 0.0, 0.05)]
        original_v = (0.1, 0.0, 0.05)
        result = snap_head_onto_body(body, head, scale_head=False)
        assert result['ok'] is True
        # With no scaling, vertex should be unchanged
        combined = result['model']
        skull_node = next(n for n in combined.all_nodes() if n.name == 'skull')
        assert skull_node.vertices[0] == pytest.approx(original_v)

    def test_no_animation_merge_by_default(self):
        """Default merge_animations=False — no animations copied."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        # Add a head-only animation
        head.animations = [types.SimpleNamespace(name='talk')]
        body.animations = []
        result = snap_head_onto_body(body, head, merge_animations=False)
        combined = result['model']
        anim_names = [a.name for a in getattr(combined, 'animations', [])]
        assert 'talk' not in anim_names  # should NOT be merged

    def test_fails_with_no_body(self):
        from core.creature_appearance import snap_head_onto_body
        head = _make_head_model()
        result = snap_head_onto_body(None, head)
        assert result['ok'] is False

    def test_fails_with_no_head(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        result = snap_head_onto_body(body, None)
        assert result['ok'] is False

    def test_fails_when_no_headhook(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model(hook_name='shoulder')
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok'] is False
        assert 'headhook' in result['message'].lower()

    def test_returns_warnings_key(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert 'warnings' in result

    def test_original_models_not_mutated(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        body_names_before = [n.name for n in body.all_nodes()]
        head_names_before = [n.name for n in head.all_nodes()]
        snap_head_onto_body(body, head)
        assert [n.name for n in body.all_nodes()] == body_names_before
        assert [n.name for n in head.all_nodes()] == head_names_before

    def test_headhook_pos_returned(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['headhook_pos'] is not None
        assert len(result['headhook_pos']) == 3

    def test_fallback_hook_name_warns(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model(hook_name='headpoint')
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok'] is True
        assert len(result['warnings']) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 7. assemble_creature() high-level wrapper
# ═══════════════════════════════════════════════════════════════════════════════

class TestAssembleCreature:
    def test_preview_mode_returns_model(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model()
        head = _make_head_model()
        result = assemble_creature(body, head, game='K1', mode='preview')
        assert result['ok'] is True
        assert result['model'] is not None

    def test_export_separate_mode_returns_two_models(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model()
        head = _make_head_model()
        result = assemble_creature(body, head, game='K1', mode='export_separate')
        assert result['ok'] is True
        assert result['body_model'] is not None
        assert result['head_model'] is not None
        assert result['supermodel'] != ''

    def test_preview_mode_default(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model()
        head = _make_head_model()
        result = assemble_creature(body, head, game='K1')  # default mode
        assert result['ok'] is True

    def test_k2_preview_mode(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model(supermodel='s_female03')
        head = _make_head_model(supermodel='s_female03')
        result = assemble_creature(body, head, game='K2', mode='preview')
        assert result['ok'] is True

    def test_k2_export_separate_mode(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model(supermodel='s_female03')
        head = _make_head_model(supermodel='s_female03')
        result = assemble_creature(body, head, game='K2', mode='export_separate')
        assert result['ok'] is True
        assert result['supermodel'] == 's_female03'

    def test_fails_gracefully_no_headhook(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model(hook_name='shoulder')
        head = _make_head_model()
        result = assemble_creature(body, head, game='K1', mode='export_separate')
        assert result['ok'] is False
        assert 'message' in result

    def test_warnings_propagated(self):
        from core.creature_appearance import assemble_creature
        body = _make_body_model(supermodel='s_female02')
        head = _make_head_model(supermodel='s_male01')
        result = assemble_creature(body, head, game='K1', mode='preview')
        # Supermodel mismatch should appear in warnings
        assert 'warnings' in result
        assert len(result['warnings']) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# 8. K1 vs K2 supermodel constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupermodelConstants:
    def test_k1_supermodels_defined(self):
        from core.creature_appearance import _K1_SUPERMODELS
        assert 'male' in _K1_SUPERMODELS
        assert 'female' in _K1_SUPERMODELS
        assert 'default' in _K1_SUPERMODELS

    def test_k2_supermodels_defined(self):
        from core.creature_appearance import _K2_SUPERMODELS
        assert 'male' in _K2_SUPERMODELS
        assert 'female' in _K2_SUPERMODELS
        assert 'default' in _K2_SUPERMODELS
        assert 'alt' in _K2_SUPERMODELS  # c_female02

    def test_k1_male_is_s_female02(self):
        from core.creature_appearance import _K1_SUPERMODELS
        assert _K1_SUPERMODELS['male'] == 's_female02'

    def test_k1_female_is_s_female03(self):
        from core.creature_appearance import _K1_SUPERMODELS
        assert _K1_SUPERMODELS['female'] == 's_female03'

    def test_k2_alt_is_c_female02(self):
        from core.creature_appearance import _K2_SUPERMODELS
        assert _K2_SUPERMODELS['alt'] == 'c_female02'

    def test_headhook_node_name_constant(self):
        from core.creature_appearance import _HEADHOOK_NODE_NAME
        assert _HEADHOOK_NODE_NAME == 'headhook'

    def test_headhook_fallbacks_do_not_include_headhook(self):
        from core.creature_appearance import _HEADHOOK_FALLBACKS
        assert 'headhook' not in _HEADHOOK_FALLBACKS


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CreatureAssembly.get_viewport_preview_model()
# ═══════════════════════════════════════════════════════════════════════════════

class TestViewportPreviewModel:
    def test_returns_combined_model(self):
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model()
        head = _make_head_model()
        asm = CreatureAssembly.from_models(body, head, game='K1')
        result = asm.get_viewport_preview_model()
        assert result['ok'] is True
        assert result['model'] is not None

    def test_fails_when_assembly_not_ok(self):
        from core.creature_appearance import CreatureAssembly
        asm = CreatureAssembly()
        result = asm.get_viewport_preview_model()
        assert result['ok'] is False

    def test_head_hierarchy_intact_in_preview(self):
        """jaw and eye bones must remain under skull in the preview model."""
        from core.creature_appearance import CreatureAssembly
        body = _make_body_model()
        head = _make_head_model()
        asm = CreatureAssembly.from_models(body, head, game='K1')
        result = asm.get_viewport_preview_model()
        combined = result['model']
        all_names = {n.name for n in combined.all_nodes()}
        assert 'jaw' in all_names
        assert 'btReye' in all_names


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Regression: existing snap_head_onto_body tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnapRegressions:
    """Ensure previously-passing snap tests still pass with the new implementation."""

    def test_result_has_ok_key(self):
        from core.creature_appearance import snap_head_onto_body
        b = _make_body_model(); h = _make_head_model()
        r = snap_head_onto_body(b, h)
        assert 'ok' in r

    def test_result_has_model_key(self):
        from core.creature_appearance import snap_head_onto_body
        b = _make_body_model(); h = _make_head_model()
        r = snap_head_onto_body(b, h)
        assert 'model' in r

    def test_result_has_message_key(self):
        from core.creature_appearance import snap_head_onto_body
        b = _make_body_model(); h = _make_head_model()
        r = snap_head_onto_body(b, h)
        assert 'message' in r

    def test_result_has_headhook_pos_key(self):
        from core.creature_appearance import snap_head_onto_body
        b = _make_body_model(); h = _make_head_model()
        r = snap_head_onto_body(b, h)
        assert 'headhook_pos' in r

    def test_combined_contains_both_body_and_head_nodes(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        combined = result['model']
        all_names = {n.name for n in combined.all_nodes()}
        # Body nodes
        assert 'Torso' in all_names
        assert 'Pelvis' in all_names
        # Head nodes
        assert 'skull' in all_names

    def test_headhook_pos_z_above_one(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model(hook_z=1.5)
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['headhook_pos'][2] > 1.0

    def test_success_message_contains_model_names(self):
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model('pmbc1')
        head = _make_head_model('pmhc1')
        result = snap_head_onto_body(body, head)
        assert 'pmbc1' in result['message']
        assert 'pmhc1' in result['message']
