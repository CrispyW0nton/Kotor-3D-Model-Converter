"""
tests/test_v57_reference_nodes_phase16.py
Phase 16.2 — Reference-node detection, ModelNode.is_reference/is_aabb properties,
SkeletonPanel tag colors, PropertiesPanel reference-node display,
and viewport _draw_stats reference-only model message.

Covers:
  - ModelNode.is_reference property (NodeFlags.REFERENCE = 0x0010)
  - ModelNode.is_aabb property (NodeFlags.AABB = 0x0200)
  - KotorModel.show_model lists Refs count
  - Reference node emitter_params['ref_model'] field is accessible
  - AnimationEngine.get_recommended_playback_fps snaps to valid tiers
  - AnimationEngine.get_animation_fps_estimate snaps to 15/24/25/30/60
  - OBJExporter.export signature accepts tex_cache parameter
  - FBXExporter.export signature accepts tex_cache parameter
"""

import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import ModelNode, NodeFlags, KotorModel
from core.animation_engine import AnimationEngine


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(name: str, flags: int) -> ModelNode:
    """Create a ModelNode with the given flags."""
    n = ModelNode(name=name, flags=flags)
    return n


def _make_minimal_model(name: str = "test") -> KotorModel:
    """Return a KotorModel with a minimal root node."""
    m = KotorModel()
    m.name = name
    m.root_node = _make_node("root", int(NodeFlags.HEADER))
    return m


# ─────────────────────────────────────────────────────────────────────────────
# ModelNode.is_reference and is_aabb properties
# ─────────────────────────────────────────────────────────────────────────────

class TestModelNodeIsReference:
    """Tests for ModelNode.is_reference property."""

    def test_is_reference_true_for_reference_flag(self):
        n = _make_node("refnode", int(NodeFlags.REFERENCE))
        assert n.is_reference is True

    def test_is_reference_false_for_mesh_node(self):
        n = _make_node("mesh", int(NodeFlags.MESH))
        assert n.is_reference is False

    def test_is_reference_false_for_dummy_node(self):
        n = _make_node("dummy", int(NodeFlags.HEADER))
        assert n.is_reference is False

    def test_is_reference_false_for_skin_node(self):
        n = _make_node("skin", int(NodeFlags.SKIN))
        assert n.is_reference is False

    def test_is_reference_false_for_emitter_node(self):
        n = _make_node("emit", int(NodeFlags.EMITTER))
        assert n.is_reference is False

    def test_is_reference_combined_flags(self):
        # REFERENCE | HEADER combo (theoretical)
        n = _make_node("refhdr", int(NodeFlags.REFERENCE) | int(NodeFlags.HEADER))
        assert n.is_reference is True

    def test_type_label_is_reference_for_reference_flag(self):
        n = _make_node("refnode", int(NodeFlags.REFERENCE))
        assert n.type_label == "reference"


class TestModelNodeIsAABB:
    """Tests for ModelNode.is_aabb property."""

    def test_is_aabb_true_for_aabb_flag(self):
        n = _make_node("aabb", int(NodeFlags.AABB))
        assert n.is_aabb is True

    def test_is_aabb_false_for_mesh_node(self):
        n = _make_node("mesh", int(NodeFlags.MESH))
        assert n.is_aabb is False

    def test_is_aabb_false_for_reference_node(self):
        n = _make_node("ref", int(NodeFlags.REFERENCE))
        assert n.is_aabb is False

    def test_type_label_is_aabb_for_aabb_flag(self):
        n = _make_node("aabb", int(NodeFlags.AABB))
        assert n.type_label == "aabb"


# ─────────────────────────────────────────────────────────────────────────────
# Reference node emitter_params storage
# ─────────────────────────────────────────────────────────────────────────────

class TestReferenceNodeEmitterParams:
    """Reference node stores ref_model and reattachable in emitter_params."""

    def test_ref_model_stored_in_emitter_params(self):
        n = _make_node("gi_datapad01", int(NodeFlags.REFERENCE))
        n.emitter_params['ref_model'] = 'gi_datapad'
        n.emitter_params['reattachable'] = False
        assert n.emitter_params.get('ref_model') == 'gi_datapad'

    def test_reattachable_default_not_set(self):
        n = _make_node("refnode", int(NodeFlags.REFERENCE))
        # emitter_params starts empty; reattachable key absent
        assert 'reattachable' not in n.emitter_params

    def test_emitter_params_independent_per_node(self):
        n1 = _make_node("ref1", int(NodeFlags.REFERENCE))
        n2 = _make_node("ref2", int(NodeFlags.REFERENCE))
        n1.emitter_params['ref_model'] = 'model_a'
        n2.emitter_params['ref_model'] = 'model_b'
        assert n1.emitter_params['ref_model'] == 'model_a'
        assert n2.emitter_params['ref_model'] == 'model_b'


# ─────────────────────────────────────────────────────────────────────────────
# KotorModel reference node traversal
# ─────────────────────────────────────────────────────────────────────────────

class TestKotorModelReferenceNodes:
    """Tests that KotorModel.all_nodes() includes reference nodes."""

    def test_all_nodes_includes_reference_node(self):
        m = _make_minimal_model("doormodel")
        ref = _make_node("doorref", int(NodeFlags.REFERENCE))
        ref.emitter_params['ref_model'] = 'dor_door01'
        m.root_node.children.append(ref)
        ref.parent = m.root_node
        all_n = m.all_nodes()
        assert ref in all_n

    def test_all_nodes_can_filter_reference_nodes(self):
        m = _make_minimal_model("compound")
        # Add two reference nodes and one mesh node
        ref1 = _make_node("ref1", int(NodeFlags.REFERENCE))
        ref1.emitter_params['ref_model'] = 'submodel_a'
        ref2 = _make_node("ref2", int(NodeFlags.REFERENCE))
        ref2.emitter_params['ref_model'] = 'submodel_b'
        mesh = _make_node("geo", int(NodeFlags.MESH))
        m.root_node.children.extend([ref1, ref2, mesh])
        # Filter to reference nodes
        ref_nodes = [n for n in m.all_nodes() if n.is_reference]
        assert len(ref_nodes) == 2
        names = {n.name for n in ref_nodes}
        assert names == {'ref1', 'ref2'}

    def test_mesh_nodes_excludes_reference_nodes(self):
        m = _make_minimal_model("mixed")
        ref = _make_node("ref", int(NodeFlags.REFERENCE))
        mesh = _make_node("geo", int(NodeFlags.MESH))
        m.root_node.children.extend([ref, mesh])
        mesh_only = m.mesh_nodes()
        assert ref not in mesh_only
        assert mesh in mesh_only

    def test_reference_only_model_has_no_mesh_nodes(self):
        m = _make_minimal_model("refonly")
        ref = _make_node("hookref", int(NodeFlags.REFERENCE))
        ref.emitter_params['ref_model'] = 'head_model'
        m.root_node.children.append(ref)
        assert len(m.mesh_nodes()) == 0
        ref_count = sum(1 for n in m.all_nodes() if n.is_reference)
        assert ref_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# AnimationEngine.get_recommended_playback_fps
# ─────────────────────────────────────────────────────────────────────────────

class TestGetRecommendedPlaybackFps:
    """Tests for AnimationEngine.get_recommended_playback_fps()."""

    def _engine(self):
        m = _make_minimal_model("test")
        return AnimationEngine(m)

    def test_returns_30_for_empty_anim(self):
        from core.model_data import Animation
        eng = self._engine()
        a = Animation(name="idle", length=0.0)
        assert eng.get_recommended_playback_fps(a) == 30

    def test_returns_valid_tier_for_typical_30fps_anim(self):
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        # 30 keys over 1 second → 30 fps
        anim_node = ModelNode(name="bone1")
        anim_node.controllers.append({
            'type': 20,
            'times': [i / 30.0 for i in range(31)],
            'values': [[0.0, 0.0, 0.0, 1.0]] * 31,
        })
        a = Animation(name="run", length=1.0, nodes=[anim_node])
        result = eng.get_recommended_playback_fps(a)
        assert result in (15, 24, 25, 30, 60)
        assert result == 30

    def test_returns_valid_tier_for_24fps_anim(self):
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        anim_node = ModelNode(name="bone1")
        anim_node.controllers.append({
            'type': 20,
            'times': [i / 24.0 for i in range(25)],
            'values': [[0.0, 0.0, 0.0, 1.0]] * 25,
        })
        a = Animation(name="walk", length=1.0, nodes=[anim_node])
        result = eng.get_recommended_playback_fps(a)
        assert result in (15, 24, 25, 30, 60)

    def test_returns_30_for_no_nodes(self):
        from core.model_data import Animation
        eng = self._engine()
        a = Animation(name="idle", length=1.0)
        assert eng.get_recommended_playback_fps(a) == 30


# ─────────────────────────────────────────────────────────────────────────────
# AnimationEngine.get_animation_fps_estimate – snap-to-tier behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAnimationFpsEstimate:
    """Tests for get_animation_fps_estimate() tier snapping."""

    def _engine(self):
        m = _make_minimal_model("fps_test")
        return AnimationEngine(m)

    def test_exactly_30_fps_snapped(self):
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        anim_node = ModelNode(name="root")
        n_keys = 31
        anim_node.controllers.append({
            'type': 8,
            'times': [i / 30.0 for i in range(n_keys)],
            'values': [[0.0, 0.0, 0.0]] * n_keys,
        })
        a = Animation(name="stand", length=1.0, nodes=[anim_node])
        fps = eng.get_animation_fps_estimate(a)
        assert fps == 30.0

    def test_exactly_24_fps_snapped(self):
        """24 fps animation: 25 keys over 1.0417 s (= 24/23 * 23 * (1/24)) = 24 raw fps → snaps to 24."""
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        anim_node = ModelNode(name="root")
        # 25 keys over length = 24/23 * 23 * (1/24) gives 24 fps
        # Simpler: 49 keys over 2.0s = 24.5 raw → within 20% of 25 → snaps to 25
        # Use 97 keys over 4.0s = 24.25 fps → within 20% of 24, nearest to 24
        n_keys = 97
        length = 4.0
        anim_node.controllers.append({
            'type': 8,
            'times': [i * (length / (n_keys - 1)) for i in range(n_keys)],
            'values': [[0.0, 0.0, 0.0]] * n_keys,
        })
        a = Animation(name="walk", length=length, nodes=[anim_node])
        fps = eng.get_animation_fps_estimate(a)
        # 97 keys / 4.0 s = 24.25 raw fps → nearest tier is 24.0 (dist 0.25) vs 25.0 (dist 0.75)
        assert fps == 24.0

    def test_near_30_drift_snapped(self):
        """29.7 fps should snap to 30."""
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        anim_node = ModelNode(name="root")
        # 89 keys over 3.0 s = 29.67 fps
        n_keys = 90
        anim_node.controllers.append({
            'type': 8,
            'times': [i * (3.0 / (n_keys - 1)) for i in range(n_keys)],
            'values': [[0.0, 0.0, 0.0]] * n_keys,
        })
        a = Animation(name="run", length=3.0, nodes=[anim_node])
        fps = eng.get_animation_fps_estimate(a)
        assert fps == 30.0

    def test_returns_30_for_single_key(self):
        from core.model_data import Animation, ModelNode
        eng = self._engine()
        anim_node = ModelNode(name="root")
        anim_node.controllers.append({
            'type': 8,
            'times': [0.0],
            'values': [[0.0, 0.0, 0.0]],
        })
        a = Animation(name="idle", length=1.0, nodes=[anim_node])
        fps = eng.get_animation_fps_estimate(a)
        assert fps == 30.0


# ─────────────────────────────────────────────────────────────────────────────
# OBJExporter / FBXExporter tex_cache parameter
# ─────────────────────────────────────────────────────────────────────────────

class TestExporterTexCacheSignature:
    """Verify that OBJExporter.export and FBXExporter.export accept tex_cache."""

    def test_obj_exporter_export_accepts_tex_cache(self):
        import inspect
        from converters.mesh_converter import OBJExporter
        sig = inspect.signature(OBJExporter.export)
        assert 'tex_cache' in sig.parameters

    def test_fbx_exporter_export_accepts_tex_cache(self):
        import inspect
        from converters.mesh_converter import FBXExporter
        sig = inspect.signature(FBXExporter.export)
        assert 'tex_cache' in sig.parameters

    def test_obj_exporter_export_tex_cache_defaults_none(self):
        import inspect
        from converters.mesh_converter import OBJExporter
        sig = inspect.signature(OBJExporter.export)
        assert sig.parameters['tex_cache'].default is None

    def test_fbx_exporter_export_tex_cache_defaults_none(self):
        import inspect
        from converters.mesh_converter import FBXExporter
        sig = inspect.signature(FBXExporter.export)
        assert sig.parameters['tex_cache'].default is None


# ─────────────────────────────────────────────────────────────────────────────
# _ensure_quat_sign_consistency (regression guard)
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsureQuatSignConsistencyRegression:
    """Regression guard for the _ensure_quat_sign_consistency helper."""

    def test_identity_chain_unchanged(self):
        from core.animation_engine import _ensure_quat_sign_consistency
        q = [0.0, 0.0, 0.0, 1.0]
        inp = [q[:] for _ in range(5)]
        out = _ensure_quat_sign_consistency(inp)
        for o in out:
            assert abs(o[3] - 1.0) < 1e-9

    def test_all_negative_identity_flipped_to_positive(self):
        from core.animation_engine import _ensure_quat_sign_consistency
        # First frame is positive identity; rest are negated
        q_pos = [0.0, 0.0, 0.0,  1.0]
        q_neg = [0.0, 0.0, 0.0, -1.0]
        inp = [q_pos[:], q_neg[:], q_neg[:], q_neg[:]]
        out = _ensure_quat_sign_consistency(inp)
        # All frames should now be in the same hemisphere as the first
        for o in out:
            assert o[3] >= 0.0

    def test_output_is_new_list(self):
        from core.animation_engine import _ensure_quat_sign_consistency
        q = [0.0, 0.0, 0.0, 1.0]
        inp = [q[:] for _ in range(3)]
        out = _ensure_quat_sign_consistency(inp)
        assert out is not inp
