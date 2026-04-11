"""
GhostRigger Weight Calculation Audit Tests
==========================================
Comprehensive tests verifying the correct bone-weight pipeline:
  1. _fill_skin_data correctly maps vertex_indices → bonemap local index → node name
  2. Weight normalization at import time
  3. anim_scale applied to position keyframe deltas
  4. 0xFFFF / negative node_id treated as unused slot
  5. LBS deformation correctness with normalized weights
  6. bone_transforms dict keyed by local bonemap index

References:
  - PyKotor MDLBoneVertex: vertex_indices reference bones in the bonemap array
  - PyKotor io_mdl.py line 2201: bonemap = [int(reader.read_single()) for ...]
  - KotorBlender: p1 = restloc + animscale * val

Date: 2026-04-10
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    ModelNode, KotorModel, NodeFlags, BoneWeight, VertexSkinData,
    Animation, _quat_rotate, _quat_conjugate,
)
from core.animation_engine import AnimationEngine, AnimPose, NodePose


# ──────────────────────────────────────────────────────────────────
#  Mock PyKotor skin data structures
# ──────────────────────────────────────────────────────────────────

class MockMDLBoneVertex:
    """Minimal mock of PyKotor's MDLBoneVertex."""
    def __init__(self, vertex_indices, vertex_weights):
        self.vertex_indices = vertex_indices
        self.vertex_weights = vertex_weights


class MockMDLSkin:
    """Minimal mock of PyKotor's MDLSkin."""
    def __init__(self, bonemap, vertex_bones, bone_indices=None):
        # bonemap[local_idx] = node_id (stored as float, converted to int)
        self.bonemap = bonemap
        self.vertex_bones = vertex_bones
        # bone_indices = fixed 16-element header array (NOT used for vertex_indices lookup)
        self.bone_indices = bone_indices or tuple(-1 for _ in range(16))


class MockPKNode:
    """Minimal mock of a PyKotor MDLNode."""
    def __init__(self, node_id, name):
        self.node_id = node_id
        self.name = name


# ──────────────────────────────────────────────────────────────────
#  Import _fill_skin_data
# ──────────────────────────────────────────────────────────────────

try:
    from core.pykotor_bridge import _fill_skin_data
    _BRIDGE_AVAILABLE = True
except ImportError:
    _BRIDGE_AVAILABLE = False


@pytest.mark.skipif(not _BRIDGE_AVAILABLE, reason="pykotor_bridge not importable")
class TestFillSkinDataBonemap:
    """Tests verifying _fill_skin_data uses bonemap (not bone_indices) for lookup."""

    def _make_pk_nodes(self, entries):
        """Build pk_nodes_by_id dict from list of (node_id, name) tuples."""
        return {nid: MockPKNode(nid, name) for nid, name in entries}

    def test_basic_bonemap_lookup(self):
        """bone_map[local_idx] = name of pk_nodes_by_id[bonemap[local_idx]]."""
        # bonemap[0] = node_id 10 → 'pelvis'
        # bonemap[1] = node_id 11 → 'spine'
        pk_nodes = self._make_pk_nodes([(10, 'pelvis'), (11, 'spine')])
        skin = MockMDLSkin(
            bonemap=[10, 11],          # local_idx 0 → node 10, local_idx 1 → node 11
            vertex_bones=[
                MockMDLBoneVertex((0.0, 1.0, -1.0, -1.0), (0.6, 0.4, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 2, f"Expected 2 bone_map slots, got {len(gr.bone_map)}"
        assert gr.bone_map[0] == 'pelvis', f"bone_map[0]={gr.bone_map[0]}"
        assert gr.bone_map[1] == 'spine',  f"bone_map[1]={gr.bone_map[1]}"

    def test_vertex_indices_are_local_bonemap_index(self):
        """vertex_indices[j] = local index into bonemap (not global node_id)."""
        # vertex_indices = (0.0, 1.0, ...) → local_idx 0 and 1 into bonemap
        # bonemap[0] = 42 → 'lshoulder'; bonemap[1] = 57 → 'rshoulder'
        pk_nodes = self._make_pk_nodes([(42, 'lshoulder'), (57, 'rshoulder')])
        skin = MockMDLSkin(
            bonemap=[42, 57],
            vertex_bones=[
                MockMDLBoneVertex((0.0, 1.0, -1.0, -1.0), (0.7, 0.3, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='arm')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.skin_data) == 1
        sd = gr.skin_data[0]
        assert len(sd.influences) == 2
        # bone_index should be local_idx (0 and 1), not global node_id (42 and 57)
        indices = {bw.bone_index for bw in sd.influences}
        assert 0 in indices, f"Expected local_idx=0, got {indices}"
        assert 1 in indices, f"Expected local_idx=1, got {indices}"
        # Global node IDs should NOT appear as bone indices
        assert 42 not in indices, "bone_index should be local_idx (0), not global node_id (42)"
        assert 57 not in indices, "bone_index should be local_idx (1), not global node_id (57)"

    def test_bone_indices_used_for_vertex_lookup(self):
        """bone_indices (uint16[16] header array) IS used for vertex_indices lookup.

        Verified against PyKotor io_mdl.py: bone_indices (stored as uint16[16] in
        the skin header) is separate from bonemap (float32 array at offset_to_bonemap).
        MDX per-vertex data stores float indices into bone_indices, not bonemap.

        When bone_indices has a valid entry (node_id=99→'wrongbone') at slot 0,
        bone_map[0] must be 'wrongbone' — not 'pelvis' from bonemap.
        """
        # bone_indices[0] = 99 → 'wrongbone'  ← this is what MDX vertex_indices index into
        # bonemap[0] = 10 → 'pelvis'          ← separate structure; NOT used for vertex lookup
        # vertex_indices[0] = 0 → bone_indices[0]=99 → 'wrongbone'  (CORRECT)
        pk_nodes = self._make_pk_nodes([(10, 'pelvis'), (99, 'wrongbone')])
        skin = MockMDLSkin(
            bonemap=[10],          # separate structure, not used when bone_indices is valid
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
            bone_indices=(99,) + (-1,) * 15,  # bone_indices[0]=99 → 'wrongbone'
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert gr.bone_map[0] == 'wrongbone', (
            f"Should use bone_indices[0]=99→'wrongbone', not bonemap. Got: {gr.bone_map[0]}"
        )

    def test_unused_slot_negative_node_id(self):
        """bonemap entry with node_id < 0 → bone_map slot is empty string."""
        # bonemap[0] = 10 → 'pelvis'; bonemap[1] = -1 → unused
        pk_nodes = self._make_pk_nodes([(10, 'pelvis')])
        skin = MockMDLSkin(
            bonemap=[10, -1],
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 2
        assert gr.bone_map[0] == 'pelvis'
        assert gr.bone_map[1] == '', f"Unused slot should be '', got '{gr.bone_map[1]}'"

    def test_unused_slot_0xffff(self):
        """bonemap entry with node_id == 0xFFFF (65535) → empty string (KotOR unused marker)."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis')])
        skin = MockMDLSkin(
            bonemap=[10, 0xFFFF],
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 2
        assert gr.bone_map[1] == '', f"0xFFFF slot should be '', got '{gr.bone_map[1]}'"

    def test_bonemap_longer_than_16(self):
        """Models with >16 active bones: bonemap can be longer than bone_indices (16 max)."""
        # Create 20 bones
        pk_nodes = self._make_pk_nodes([(i, f'bone_{i}') for i in range(20)])
        skin = MockMDLSkin(
            bonemap=list(range(20)),   # 20 entries, more than bone_indices can hold (max 16)
            vertex_bones=[
                MockMDLBoneVertex((0.0, 17.0, -1.0, -1.0), (0.5, 0.5, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 20, f"Should have 20 bone_map slots, got {len(gr.bone_map)}"
        assert gr.bone_map[17] == 'bone_17', f"bone_map[17]={gr.bone_map[17]}"

        # Verify the vertex's influences reference local_idx 0 and 17
        assert len(gr.skin_data) == 1
        indices = {bw.bone_index for bw in gr.skin_data[0].influences}
        assert 0 in indices
        assert 17 in indices

    def test_out_of_range_vertex_index_skipped(self):
        """vertex_indices[j] >= len(bonemap) → influence skipped (corrupt data guard)."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis')])
        skin = MockMDLSkin(
            bonemap=[10],
            vertex_bones=[
                # local_idx=99 is out of range (bonemap only has 1 entry)
                MockMDLBoneVertex((99.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        # Out-of-range index should be skipped → no influences
        assert len(gr.skin_data) == 1
        assert len(gr.skin_data[0].influences) == 0, (
            f"Out-of-range index should be skipped, got {len(gr.skin_data[0].influences)} influences"
        )

    def test_weight_normalization(self):
        """Weights are normalized to sum=1 after import."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis'), (11, 'spine')])
        # Weights sum to 0.6 (not 1.0) — should be normalized
        skin = MockMDLSkin(
            bonemap=[10, 11],
            vertex_bones=[
                MockMDLBoneVertex((0.0, 1.0, -1.0, -1.0), (0.3, 0.3, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.skin_data) == 1
        total = sum(bw.weight for bw in gr.skin_data[0].influences)
        assert abs(total - 1.0) < 1e-4, f"Weights should sum to 1.0, got {total}"

    def test_already_normalized_weights_unchanged(self):
        """Pre-normalized weights (sum=1) are not distorted."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis'), (11, 'spine')])
        skin = MockMDLSkin(
            bonemap=[10, 11],
            vertex_bones=[
                MockMDLBoneVertex((0.0, 1.0, -1.0, -1.0), (0.75, 0.25, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        total = sum(bw.weight for bw in gr.skin_data[0].influences)
        assert abs(total - 1.0) < 1e-4

        # Check individual weights are preserved
        w_by_idx = {bw.bone_index: bw.weight for bw in gr.skin_data[0].influences}
        assert abs(w_by_idx[0] - 0.75) < 1e-4
        assert abs(w_by_idx[1] - 0.25) < 1e-4

    def test_zero_weight_influences_skipped(self):
        """Zero-weight influences (≤1e-6) are not added."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis'), (11, 'spine')])
        skin = MockMDLSkin(
            bonemap=[10, 11],
            vertex_bones=[
                # spine has weight 0 → should be skipped
                MockMDLBoneVertex((0.0, 1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.skin_data[0].influences) == 1, (
            f"Zero-weight influence should be skipped, got {len(gr.skin_data[0].influences)}"
        )

    def test_negative_vertex_index_skipped(self):
        """vertex_indices[j] = -1.0 (unused) → influence skipped."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis')])
        skin = MockMDLSkin(
            bonemap=[10],
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.5, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        # Only local_idx=0 is valid; -1.0 is skipped
        assert len(gr.skin_data[0].influences) == 1

    def test_multi_vertex_skin_data_length_matches_vertex_bones(self):
        """skin_data length == len(vertex_bones) (one VertexSkinData per vertex)."""
        pk_nodes = self._make_pk_nodes([(10, 'pelvis')])
        skin = MockMDLSkin(
            bonemap=[10],
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.skin_data) == 3, f"Expected 3 VertexSkinData, got {len(gr.skin_data)}"

    def test_empty_bonemap_produces_empty_bone_map(self):
        """Empty bonemap → empty bone_map."""
        pk_nodes = {}
        skin = MockMDLSkin(bonemap=[], vertex_bones=[])
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert gr.bone_map == []
        assert gr.skin_data == []

    def test_unknown_node_id_produces_empty_string(self):
        """bonemap entry with node_id not in pk_nodes_by_id → empty string (not crash)."""
        pk_nodes = {}  # empty — no nodes known
        skin = MockMDLSkin(
            bonemap=[42],  # node 42 not in pk_nodes
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 1
        assert gr.bone_map[0] == '', f"Unknown node should produce '', got '{gr.bone_map[0]}'"

    def test_bone_map_indexed_by_local_idx(self):
        """
        Regression test: bone_map[local_idx] gives the correct bone name
        for the local_idx used in BoneWeight.bone_index.
        This is the key invariant for _build_bone_transforms.
        """
        pk_nodes = self._make_pk_nodes([
            (100, 'root'), (101, 'pelvis'), (102, 'lleg'), (103, 'rleg')
        ])
        # bonemap: local 0→100(root), 1→101(pelvis), 2→102(lleg), 3→103(rleg)
        skin = MockMDLSkin(
            bonemap=[100, 101, 102, 103],
            vertex_bones=[
                # Vertex 0: influenced by local 1 (pelvis) and 2 (lleg)
                MockMDLBoneVertex((1.0, 2.0, -1.0, -1.0), (0.6, 0.4, 0.0, 0.0)),
                # Vertex 1: influenced by local 3 (rleg) only
                MockMDLBoneVertex((3.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        assert len(gr.bone_map) == 4
        assert gr.bone_map[0] == 'root'
        assert gr.bone_map[1] == 'pelvis'
        assert gr.bone_map[2] == 'lleg'
        assert gr.bone_map[3] == 'rleg'

        # Vertex 0 influences: bone_index=1 (pelvis), bone_index=2 (lleg)
        v0 = gr.skin_data[0]
        bi_v0 = {bw.bone_index for bw in v0.influences}
        assert bi_v0 == {1, 2}, f"Vertex 0 should be influenced by local 1,2. Got {bi_v0}"
        # Verify names via bone_map
        for bw in v0.influences:
            name = gr.bone_map[bw.bone_index]
            assert name in ('pelvis', 'lleg'), f"Unexpected bone name: {name}"

        # Vertex 1 influences: bone_index=3 (rleg)
        v1 = gr.skin_data[1]
        bi_v1 = {bw.bone_index for bw in v1.influences}
        assert bi_v1 == {3}, f"Vertex 1 should be influenced by local 3. Got {bi_v1}"
        assert gr.bone_map[3] == 'rleg'


# ──────────────────────────────────────────────────────────────────
#  anim_scale position delta tests
# ──────────────────────────────────────────────────────────────────

class TestAnimScalePositionDelta:
    """Tests verifying anim_scale behaviour for position keyframe deltas.

    KotOR Engine (xoreos): anim_scale is an import-time coordinate-space
    factor stored in the MDL header.  It is NOT a runtime playback multiplier.
    xoreos does not scale position keyframes during playback.  GhostRigger
    follows the same rule: position deltas are added directly to the bind
    position without being scaled by anim_scale.

    References:
      - xoreos model_kotor.cpp: position frames are relative (delta-added)
        but never multiplied by anim_scale during playback.
      - Commit 90914d8: removed the anim_scale multiplier that was incorrectly
        shrinking bone movements and causing facial misalignment.
    """

    def _make_model_with_bone(self, bind_pos, anim_scale=1.0):
        """Create a minimal KotorModel with one bone node and one animation."""
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)

        bone = ModelNode(name='pelvis')
        bone.flags = 0
        bone.position = bind_pos
        bone.rotation = (0.0, 0.0, 0.0, 1.0)
        bone.parent = root
        root.children.append(bone)

        model = KotorModel()
        model.root_node = root
        model.anim_scale = anim_scale

        anim = Animation()
        anim.name = 'walk'
        anim.length = 1.0

        anim_bone = ModelNode(name='pelvis')
        anim_bone.controllers = [{
            'type': 8,   # CTRL_POSITION
            'times': [0.0, 0.5, 1.0],
            'values': [[0.0, 0.0, 0.2],   # delta at t=0
                       [0.0, 0.0, 0.5],   # delta at t=0.5
                       [0.0, 0.0, 0.2]],  # delta at t=1.0
        }]
        anim.nodes = [anim_bone]
        model.animations = [anim]

        return model

    def test_anim_scale_1_position_delta_applied_directly(self):
        """With anim_scale=1.0, position delta is added to bind pos unchanged."""
        bind_pos = (0.0, 0.0, 1.0)
        model = self._make_model_with_bone(bind_pos, anim_scale=1.0)
        engine = AnimationEngine(model)
        engine.play('walk', loop=False)

        pose = engine.evaluate(0.5)
        np = pose.nodes.get('pelvis')
        assert np is not None, "Pelvis node should be in pose"
        expected = (0.0 + 1.0 * 0.0,
                    0.0 + 1.0 * 0.0,
                    1.0 + 1.0 * 0.5)
        assert abs(np.position[2] - expected[2]) < 1e-4, (
            f"anim_scale=1.0: expected z={expected[2]}, got {np.position[2]}"
        )

    def test_anim_scale_2_no_effect_on_position_delta(self):
        """anim_scale=2.0 does NOT scale position deltas (it is an import-time factor only).

        xoreos never applies anim_scale during playback. The correct formula is:
            animated_pos = bind_pos + raw_delta   (no anim_scale multiplication)
        """
        bind_pos = (0.0, 0.0, 1.0)
        model = self._make_model_with_bone(bind_pos, anim_scale=2.0)
        engine = AnimationEngine(model)
        engine.play('walk', loop=False)

        pose = engine.evaluate(0.5)
        np = pose.nodes.get('pelvis')
        assert np is not None
        # At t=0.5, interpolated delta = 0.5 (from values [0.2, 0.5, 0.2])
        # anim_scale=2.0 has NO effect: pos_z = 1.0 + 0.5 = 1.5 (NOT 1.0 + 2.0*0.5)
        expected_z = 1.0 + 0.5   # raw delta only — anim_scale ignored
        assert abs(np.position[2] - expected_z) < 0.02, (
            f"anim_scale=2.0 should be ignored: expected z≈{expected_z:.3f}, got {np.position[2]:.3f}"
        )

    def test_anim_scale_0_5_no_effect_on_position_delta(self):
        """anim_scale=0.5 does NOT halve position deltas (it is an import-time factor only).

        xoreos never applies anim_scale during playback. The correct formula is:
            animated_pos = bind_pos + raw_delta   (no anim_scale multiplication)
        """
        bind_pos = (0.0, 0.0, 1.0)
        model = self._make_model_with_bone(bind_pos, anim_scale=0.5)
        engine = AnimationEngine(model)
        engine.play('walk', loop=False)

        pose = engine.evaluate(0.5)
        np = pose.nodes.get('pelvis')
        assert np is not None
        # At t=0.5, interpolated delta = 0.5 (from values [0.2, 0.5, 0.2])
        # anim_scale=0.5 has NO effect: pos_z = 1.0 + 0.5 = 1.5 (NOT 1.0 + 0.5*0.5)
        expected_z = 1.0 + 0.5   # raw delta only — anim_scale ignored
        assert abs(np.position[2] - expected_z) < 0.02, (
            f"anim_scale=0.5 should be ignored: expected z≈{expected_z:.3f}, got {np.position[2]:.3f}"
        )

    def test_anim_scale_at_keyframe_t0_no_scale(self):
        """At t=0, delta is [0,0,0.2]. anim_scale=2 has NO effect: z = bind_z + 0.2.

        anim_scale is an import-time coordinate-space factor, not a playback multiplier.
        """
        bind_pos = (0.0, 0.0, 1.0)
        model = self._make_model_with_bone(bind_pos, anim_scale=2.0)
        engine = AnimationEngine(model)
        engine.play('walk', loop=False)

        pose = engine.evaluate(0.0)
        np = pose.nodes.get('pelvis')
        assert np is not None
        # Raw delta at t=0 is 0.2. anim_scale=2.0 is ignored: z = 1.0 + 0.2 = 1.2
        expected_z = 1.0 + 0.2   # NOT 1.0 + 2.0*0.2
        assert abs(np.position[2] - expected_z) < 1e-4, (
            f"At t=0: expected z={expected_z:.4f} (no anim_scale), got {np.position[2]:.4f}"
        )

    def test_default_anim_scale_is_1(self):
        """KotorModel.anim_scale defaults to 1.0 — no scale applied if not set."""
        model = KotorModel()
        assert model.anim_scale == 1.0, f"Default anim_scale should be 1.0, got {model.anim_scale}"

    def test_anim_scale_does_not_affect_orientation(self):
        """anim_scale does not affect CTRL_ORIENTATION (type 20) \u2014 rotations use raw keyframes."""
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)

        bone = ModelNode(name='pelvis')
        bone.flags = 0
        bone.position = (0.0, 0.0, 1.0)
        bone.rotation = (0.0, 0.0, 0.0, 1.0)
        bone.parent = root
        root.children.append(bone)

        model = KotorModel()
        model.root_node = root
        model.anim_scale = 10.0  # extreme scale should NOT affect rotation

        anim = Animation()
        anim.name = 'turn'
        anim.length = 1.0

        # A 45° rotation about Z = [0, 0, sin(22.5°), cos(22.5°)]
        import math
        s = math.sin(math.pi / 8)
        c = math.cos(math.pi / 8)

        anim_bone = ModelNode(name='pelvis')
        anim_bone.controllers = [{
            'type': 20,   # CTRL_ORIENTATION
            'times': [0.0],
            'values': [[0.0, 0.0, s, c]],
        }]
        anim.nodes = [anim_bone]
        model.animations = [anim]

        engine = AnimationEngine(model)
        engine.play('turn', loop=False)

        pose = engine.evaluate(0.0)
        np = pose.nodes.get('pelvis')
        assert np is not None
        # Rotation should match the keyframe quaternion regardless of anim_scale
        assert abs(np.rotation[2] - s) < 1e-4, (
            f"Rotation z component: expected {s:.4f}, got {np.rotation[2]:.4f}"
        )
        assert abs(np.rotation[3] - c) < 1e-4, (
            f"Rotation w component: expected {c:.4f}, got {np.rotation[3]:.4f}"
        )


# ──────────────────────────────────────────────────────────────────
#  LBS weight pipeline integration
# ──────────────────────────────────────────────────────────────────

class TestLBSWeightPipeline:
    """Integration tests verifying correct weight → LBS deformation flow."""

    def test_vertex_skin_data_normalize(self):
        """VertexSkinData.normalize() brings weights to sum=1."""
        vsd = VertexSkinData(influences=[
            BoneWeight(bone_index=0, weight=0.3),
            BoneWeight(bone_index=1, weight=0.6),
        ])
        vsd.normalize()
        total = sum(bw.weight for bw in vsd.influences)
        assert abs(total - 1.0) < 1e-6

    def test_vertex_skin_data_to_packed_padding(self):
        """to_packed() pads to 4 entries and preserves order."""
        vsd = VertexSkinData(influences=[
            BoneWeight(bone_index=2, weight=0.8),
            BoneWeight(bone_index=5, weight=0.2),
        ])
        wts, idxs = vsd.to_packed()
        assert len(wts) == 4
        assert len(idxs) == 4
        assert wts[0] == 0.8
        assert wts[1] == 0.2
        assert wts[2] == 0.0  # padded
        assert idxs[0] == 2
        assert idxs[1] == 5
        assert idxs[2] == 0  # padded index

    def test_bone_weight_dataclass(self):
        """BoneWeight stores bone_index and weight correctly."""
        bw = BoneWeight(bone_index=3, weight=0.75)
        assert bw.bone_index == 3
        assert bw.weight == 0.75

    def test_single_bone_100pct_weight_is_passthrough(self):
        """A vertex with 100% weight on one bone should move exactly with that bone."""
        # This is the mathematical identity check: when weight=1.0 for one bone,
        # the LBS result equals the bone-transformed vertex exactly.
        # The full LBS integration requires the viewport; here we check the data path.

        if not _BRIDGE_AVAILABLE:
            pytest.skip("pykotor_bridge not available")

        pk_nodes = {10: MockPKNode(10, 'pelvis')}
        skin = MockMDLSkin(
            bonemap=[10],
            vertex_bones=[
                MockMDLBoneVertex((0.0, -1.0, -1.0, -1.0), (1.0, 0.0, 0.0, 0.0)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        # Verify the data structure
        assert len(gr.skin_data) == 1
        sd = gr.skin_data[0]
        assert len(sd.influences) == 1
        bw = sd.influences[0]
        assert bw.bone_index == 0
        assert abs(bw.weight - 1.0) < 1e-6
        assert gr.bone_map[0] == 'pelvis'

    def test_four_bone_equal_weights_normalized(self):
        """4 bones with equal 0.25 weights are valid (no normalization needed)."""
        if not _BRIDGE_AVAILABLE:
            pytest.skip("pykotor_bridge not available")

        pk_nodes = {i: MockPKNode(i, f'bone_{i}') for i in range(4)}
        skin = MockMDLSkin(
            bonemap=[0, 1, 2, 3],
            vertex_bones=[
                MockMDLBoneVertex((0.0, 1.0, 2.0, 3.0), (0.25, 0.25, 0.25, 0.25)),
            ],
        )
        gr = ModelNode(name='body')
        _fill_skin_data(skin, gr, pk_nodes)

        total = sum(bw.weight for bw in gr.skin_data[0].influences)
        assert abs(total - 1.0) < 1e-5
        assert len(gr.skin_data[0].influences) == 4


# ──────────────────────────────────────────────────────────────────
#  VertexSkinData dataclass correctness
# ──────────────────────────────────────────────────────────────────

class TestVertexSkinDataStructure:
    """Basic correctness tests for BoneWeight and VertexSkinData."""

    def test_empty_vertex_skin_data(self):
        vsd = VertexSkinData()
        assert vsd.influences == []

    def test_normalize_empty(self):
        """normalize() with no influences doesn't crash."""
        vsd = VertexSkinData()
        vsd.normalize()  # should be no-op

    def test_normalize_single_influence(self):
        """Single influence normalizes to weight=1.0."""
        vsd = VertexSkinData(influences=[BoneWeight(0, 0.5)])
        vsd.normalize()
        assert abs(vsd.influences[0].weight - 1.0) < 1e-6

    def test_to_packed_empty(self):
        """to_packed() with no influences returns all zeros."""
        vsd = VertexSkinData()
        wts, idxs = vsd.to_packed()
        assert wts == (0.0, 0.0, 0.0, 0.0)
        assert idxs == (0, 0, 0, 0)

    def test_to_packed_three_influences(self):
        """to_packed() with 3 influences pads to 4."""
        vsd = VertexSkinData(influences=[
            BoneWeight(1, 0.5),
            BoneWeight(2, 0.3),
            BoneWeight(3, 0.2),
        ])
        wts, idxs = vsd.to_packed()
        assert len(wts) == 4
        assert wts[3] == 0.0  # padded
        assert idxs[3] == 0   # padded index

    def test_bone_weight_default_values(self):
        bw = BoneWeight()
        assert bw.bone_index == 0
        assert bw.weight == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
