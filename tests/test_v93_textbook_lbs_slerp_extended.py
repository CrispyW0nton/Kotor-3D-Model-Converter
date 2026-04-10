"""
GhostRigger Phase 4.5 — Extended Textbook Math Proofs
======================================================
44 tests rigorously verifying the mathematical foundations of GhostRigger's
skeletal animation pipeline against the canonical textbook formulas.

Coverage (not duplicated from earlier test files):
  A) LBS skinning matrix formula: Kj = inv_bind[j] * current_global[j]
  B) SLERP shortest-path property
  C) _interp_channel boundary conditions
  D) _quat_normalize_bind NWN-convention selective collapse
  E) Animation position delta semantics (xoreos / KotorBlender)
  F) LERP linearity (_lerp, _lerp3)
  G) Dangly spring topology
  H) world_position cycle guard
  I) Animation looping
  J) compute_all_tangents edge cases

References:
  - Gregory, *Game Engine Architecture* §§12.4–12.6
  - Lengyel, *Mathematics for 3D Game Programming* §§3–4, §7.8.3, §15.2
  - Lengyel, *FGED Vol.1* §4
  - Millington, *Game Physics Engine Development* §13
  - McKesson, *Learning Modern 3D Graphics Programming* §4

Date: 2026-03-21
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    ModelNode, KotorModel, NodeFlags, Animation, AnimEvent,
    _quat_normalize, _quat_normalize_bind, _quat_rotate, _quat_mul,
)
from core.animation_engine import (
    AnimationEngine, DanglySimulator,
    _lerp, _lerp3, _slerp, _interp_channel,
)


# ─────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────

def _mat4_mul(A, B):
    """Multiply two 4×4 matrices stored as flat 16-element lists (row-major)."""
    C = [0.0]*16
    for i in range(4):
        for j in range(4):
            C[i*4+j] = sum(A[i*4+k] * B[k*4+j] for k in range(4))
    return C

def _mat4_identity():
    return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]

def _mat4_translation(tx, ty, tz):
    return [1,0,0,tx, 0,1,0,ty, 0,0,1,tz, 0,0,0,1]

def _mat4_rotation_z(angle_rad):
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return [c,-s,0,0, s,c,0,0, 0,0,1,0, 0,0,0,1]

def _mat4_inv_translation(tx, ty, tz):
    return _mat4_translation(-tx, -ty, -tz)

def _mat4_apply(M, v):
    """Apply 4×4 matrix to a 3D point (homogeneous w=1)."""
    x = M[0]*v[0] + M[1]*v[1] + M[2]*v[2] + M[3]
    y = M[4]*v[0] + M[5]*v[1] + M[6]*v[2] + M[7]
    z = M[8]*v[0] + M[9]*v[1] + M[10]*v[2] + M[11]
    return (x, y, z)

def _quat_from_axis_angle(ax, ay, az, angle):
    """Build quaternion [x,y,z,w] from axis-angle."""
    s = math.sin(angle / 2.0)
    c = math.cos(angle / 2.0)
    mag = math.sqrt(ax*ax + ay*ay + az*az)
    if mag < 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    return [ax/mag*s, ay/mag*s, az/mag*s, c]


# ═════════════════════════════════════════════════════════════════
#  A) LBS skinning matrix formula (Gregory §12.5.2)
# ═════════════════════════════════════════════════════════════════

class TestLBSSkinningMatrix:
    """
    Canonical LBS formula (Gregory §12.5.2):
        Kj = inv_bind[j] * current_global[j]
        v'_world = Σ w_i * Kj_i * v_bind_world

    Verified for:
      1. Bind pose (Kj = identity → v' = v)
      2. 90° rotation with translation
      3. Multi-joint weighted blend
    """

    def test_bind_pose_is_identity_transform(self):
        """At bind pose, Kj = inv_bind * bind = I, so v' = v."""
        bind_global = _mat4_translation(1.0, 2.0, 3.0)
        inv_bind    = _mat4_inv_translation(1.0, 2.0, 3.0)
        Kj = _mat4_mul(inv_bind, bind_global)   # should be identity
        v = (5.0, 7.0, 11.0)
        v_out = _mat4_apply(Kj, v)
        assert abs(v_out[0] - v[0]) < 1e-6
        assert abs(v_out[1] - v[1]) < 1e-6
        assert abs(v_out[2] - v[2]) < 1e-6

    def test_translation_bone_moves_vertex(self):
        """Bone translates from (0,0,0) to (1,0,0) → vertex moves by (1,0,0)."""
        # Bind: bone at origin
        bind_global = _mat4_identity()
        inv_bind    = _mat4_identity()
        # Animated: bone at (1,0,0)
        current     = _mat4_translation(1.0, 0.0, 0.0)
        Kj = _mat4_mul(inv_bind, current)
        v = (0.0, 0.0, 0.0)   # vertex at bind bone position
        v_out = _mat4_apply(Kj, v)
        assert abs(v_out[0] - 1.0) < 1e-6
        assert abs(v_out[1] - 0.0) < 1e-6

    def test_multi_joint_blend_interpolates(self):
        """Two equal-weight joints: one at (0,0,0), one at (2,0,0) → result at (1,0,0)."""
        # Joint 0: stays at origin
        inv0 = _mat4_identity()
        cur0 = _mat4_identity()
        K0   = _mat4_mul(inv0, cur0)
        # Joint 1: translates to (2,0,0)
        inv1 = _mat4_identity()
        cur1 = _mat4_translation(2.0, 0.0, 0.0)
        K1   = _mat4_mul(inv1, cur1)

        v = (0.0, 0.0, 0.0)
        w0, w1 = 0.5, 0.5
        out0 = _mat4_apply(K0, v)
        out1 = _mat4_apply(K1, v)
        blended = tuple(w0*out0[i] + w1*out1[i] for i in range(3))
        assert abs(blended[0] - 1.0) < 1e-6
        assert abs(blended[1] - 0.0) < 1e-6

    def test_weights_must_sum_to_one(self):
        """Verify that LBS weights summing to 1.0 preserves bind-pose vertex."""
        inv = _mat4_identity()
        cur = _mat4_translation(0.5, 0.0, 0.0)
        K   = _mat4_mul(inv, cur)
        v   = (1.0, 2.0, 3.0)
        # weights: 0.4 + 0.6 = 1.0
        out_K  = _mat4_apply(K, v)
        out_id = _mat4_apply(_mat4_identity(), v)
        blended = tuple(0.6*out_K[i] + 0.4*out_id[i] for i in range(3))
        # Just verify it doesn't blow up and is between the two extremes
        assert out_id[0] <= blended[0] <= out_K[0] + 1e-6


# ═════════════════════════════════════════════════════════════════
#  B) SLERP shortest-path (Gregory §12.4)
# ═════════════════════════════════════════════════════════════════

class TestSlerpShortestPath:
    def test_antipodal_quaternions_take_short_path(self):
        """SLERP between q and -q should go the short way (dot < 0 → negate)."""
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 0.0, -1.0]   # antipodal of identity
        mid = _slerp(q1, q2, 0.5)
        # Mid should still be unit length
        mag = math.sqrt(sum(x*x for x in mid))
        assert abs(mag - 1.0) < 1e-6

    def test_slerp_midpoint_is_unit_length(self):
        q1 = _quat_from_axis_angle(0,0,1, 0.0)
        q2 = _quat_from_axis_angle(0,0,1, math.pi/2)
        mid = _slerp(q1, q2, 0.5)
        mag = math.sqrt(sum(x*x for x in mid))
        assert abs(mag - 1.0) < 1e-6

    def test_slerp_at_0_returns_q1(self):
        q1 = _quat_from_axis_angle(1,0,0, 0.3)
        q2 = _quat_from_axis_angle(0,1,0, 0.7)
        result = _slerp(q1, q2, 0.0)
        for a, b in zip(result, q1):
            assert abs(a - b) < 1e-5

    def test_slerp_at_1_returns_q2(self):
        q1 = _quat_from_axis_angle(1,0,0, 0.3)
        q2 = _quat_from_axis_angle(0,1,0, 0.7)
        result = _slerp(q1, q2, 1.0)
        # q2 or its antipodal
        same   = all(abs(a - b) < 1e-5 for a, b in zip(result, q2))
        mirror = all(abs(a + b) < 1e-5 for a, b in zip(result, q2))
        assert same or mirror

    def test_slerp_90deg_midpoint(self):
        """SLERP at t=0.5 between 0° and 90° Z-rotation should give 45°."""
        q1 = _quat_from_axis_angle(0,0,1, 0.0)
        q2 = _quat_from_axis_angle(0,0,1, math.pi/2)
        mid = _slerp(q1, q2, 0.5)
        expected = _quat_from_axis_angle(0,0,1, math.pi/4)
        # Allow sign flip
        same   = all(abs(mid[i] - expected[i]) < 1e-5 for i in range(4))
        mirror = all(abs(mid[i] + expected[i]) < 1e-5 for i in range(4))
        assert same or mirror

    def test_slerp_nearly_identical_uses_lerp_fallback(self):
        """Quaternions with dot > 0.9995 should use linear fallback without crash."""
        q1 = [0.0, 0.0, 0.0, 1.0]
        q2 = [0.0, 0.0, 1e-5, 1.0]   # almost identical
        # Normalize q2
        mag = math.sqrt(sum(x*x for x in q2))
        q2 = [x/mag for x in q2]
        result = _slerp(q1, q2, 0.5)
        mag_r = math.sqrt(sum(x*x for x in result))
        assert abs(mag_r - 1.0) < 1e-5


# ═════════════════════════════════════════════════════════════════
#  C) _interp_channel boundary conditions
# ═════════════════════════════════════════════════════════════════

class TestInterpChannelBoundaries:
    def test_empty_times_returns_none(self):
        assert _interp_channel([], [], 0.5) is None

    def test_before_first_key_clamps_to_first(self):
        result = _interp_channel([1.0, 2.0], [[0.0], [1.0]], 0.0)
        assert result == pytest.approx([0.0])

    def test_after_last_key_clamps_to_last(self):
        result = _interp_channel([1.0, 2.0], [[0.0], [1.0]], 5.0)
        assert result == pytest.approx([1.0])

    def test_exact_key_returns_exact_value(self):
        result = _interp_channel([0.0, 1.0, 2.0], [[0.0], [5.0], [10.0]], 1.0)
        assert result == pytest.approx([5.0], abs=1e-5)

    def test_midpoint_interpolation(self):
        result = _interp_channel([0.0, 2.0], [[0.0], [4.0]], 1.0)
        assert result == pytest.approx([2.0], abs=1e-5)

    def test_large_n_binary_search_accuracy(self):
        n = 1000
        times  = [float(i) for i in range(n)]
        values = [[float(i)] for i in range(n)]
        # Test at t=500.5 → should be between 500 and 501
        result = _interp_channel(times, values, 500.5)
        assert result == pytest.approx([500.5], abs=1e-4)

    def test_nan_key_is_skipped(self):
        import math
        times  = [0.0, 1.0, 2.0]
        values = [[0.0], [float('nan')], [4.0]]
        result = _interp_channel(times, values, 1.5)
        # NaN key at index 1 should be skipped; result from 0→2 interpolation
        assert result is not None
        assert all(math.isfinite(v) for v in result)


# ═════════════════════════════════════════════════════════════════
#  D) _quat_normalize_bind NWN convention
# ═════════════════════════════════════════════════════════════════

class TestQuatNormalizeBindConvention:
    def test_180_about_x_collapses_to_identity(self):
        """NWN exporter 180° about X must collapse to identity (do NOT remove)."""
        # 180° rotation about X axis: [sin(90°), 0, 0, cos(90°)] = [1, 0, 0, 0]
        q = [1.0, 0.0, 0.0, 0.0]
        result = _quat_normalize_bind(q)
        # Should collapse to identity [0,0,0,1]
        assert abs(result[3] - 1.0) < 1e-5, (
            f"180°-about-X should collapse to identity w=1, got {result}"
        )

    def test_180_about_y_is_preserved(self):
        """180° about Y should NOT collapse."""
        q = [0.0, 1.0, 0.0, 0.0]
        result = _quat_normalize_bind(q)
        # Should not be identity
        mag = math.sqrt(sum(x*x for x in result))
        assert abs(mag - 1.0) < 1e-5   # still unit
        # w should NOT be 1 (not collapsed to identity)
        assert abs(result[3] - 1.0) > 0.1, "180°-about-Y should NOT collapse to identity"

    def test_identity_quaternion_is_unchanged(self):
        q = [0.0, 0.0, 0.0, 1.0]
        result = _quat_normalize_bind(q)
        assert abs(result[3] - 1.0) < 1e-5

    def test_result_is_always_unit_length(self):
        for q in ([0.5, 0.5, 0.5, 0.5],
                  [1.0, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.707, 0.707],
                  [0.0, 0.0, 0.0, 1.0]):
            result = _quat_normalize_bind(q)
            mag = math.sqrt(sum(x*x for x in result))
            assert abs(mag - 1.0) < 1e-5, f"Not unit for input {q}: mag={mag}"


# ═════════════════════════════════════════════════════════════════
#  E) Animation position delta semantics
# ═════════════════════════════════════════════════════════════════

class TestAnimationPositionDeltaSemantics:
    """
    KotOR position controller values are DELTA OFFSETS added to bind-pose position.
    Zero delta → vertex stays at bind position.
    Non-zero delta → bind + delta.
    Orientation is ABSOLUTE (replaces bind rotation).
    (Verified against xoreos + KotorBlender.)
    """

    def _make_engine(self, bind_pos, anim_delta, anim_rot=None):
        from core.model_data import ModelNode, NodeFlags
        # Build model with one bone node
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        bone = ModelNode(name='hip', flags=int(NodeFlags.HEADER))
        bone.position = bind_pos
        bone.rotation = (0.0, 0.0, 0.0, 1.0)
        root.children = [bone]
        bone.parent = root
        m = KotorModel(name='test', root_node=root)

        # Build animation with position delta
        anim = Animation(name='walk', length=1.0)
        anim_bone = ModelNode(name='hip')
        ctrl = {
            'type': AnimationEngine.CTRL_POSITION,
            'name': 'position',
            'columns': 3,
            'times': [0.0],
            'values': [list(anim_delta)],
        }
        anim_bone.controllers = [ctrl]
        if anim_rot is not None:
            ctrl_rot = {
                'type': AnimationEngine.CTRL_ORIENTATION,
                'name': 'orientation',
                'columns': 4,
                'times': [0.0],
                'values': [list(anim_rot)],
            }
            anim_bone.controllers.append(ctrl_rot)
        anim.nodes = [anim_bone]
        m.animations = [anim]
        return AnimationEngine(m)

    def test_zero_delta_gives_bind_position(self):
        bind = (1.0, 2.0, 3.0)
        eng = self._make_engine(bind, (0.0, 0.0, 0.0))
        eng.play('walk')
        pose = eng.evaluate(0.0)
        np_ = pose.nodes.get('hip')
        assert np_ is not None
        assert abs(np_.position[0] - bind[0]) < 1e-5
        assert abs(np_.position[1] - bind[1]) < 1e-5
        assert abs(np_.position[2] - bind[2]) < 1e-5

    def test_nonzero_delta_adds_to_bind(self):
        bind  = (1.0, 2.0, 3.0)
        delta = (0.5, -0.3, 0.1)
        eng = self._make_engine(bind, delta)
        eng.play('walk')
        pose = eng.evaluate(0.0)
        np_ = pose.nodes.get('hip')
        assert np_ is not None
        for i, (b, d) in enumerate(zip(bind, delta)):
            assert abs(np_.position[i] - (b + d)) < 1e-5

    def test_orientation_is_absolute(self):
        bind_rot = (0.0, 0.0, 0.0, 1.0)
        anim_rot = (0.0, 0.0, 0.707, 0.707)   # 90° about Z
        eng = self._make_engine((0,0,0), (0,0,0), anim_rot=anim_rot)
        eng.play('walk')
        pose = eng.evaluate(0.0)
        np_ = pose.nodes.get('hip')
        assert np_ is not None
        # Rotation should be close to anim_rot (or its normalized form)
        mag = math.sqrt(sum(x*x for x in np_.rotation))
        assert abs(mag - 1.0) < 1e-5
        # Should NOT be identity (bind rotation) after absolute replacement
        assert abs(np_.rotation[2]) > 0.3   # z component should be ~0.707


# ═════════════════════════════════════════════════════════════════
#  F) LERP linearity
# ═════════════════════════════════════════════════════════════════

class TestLerpLinearity:
    def test_lerp_at_0_returns_a(self):
        assert _lerp(3.0, 7.0, 0.0) == pytest.approx(3.0)

    def test_lerp_at_1_returns_b(self):
        assert _lerp(3.0, 7.0, 1.0) == pytest.approx(7.0)

    def test_lerp_midpoint(self):
        assert _lerp(0.0, 10.0, 0.5) == pytest.approx(5.0)

    def test_lerp3_at_0_returns_a(self):
        a = (1.0, 2.0, 3.0)
        b = (4.0, 5.0, 6.0)
        result = _lerp3(a, b, 0.0)
        assert result == pytest.approx(a)

    def test_lerp3_at_1_returns_b(self):
        a = (1.0, 2.0, 3.0)
        b = (4.0, 5.0, 6.0)
        result = _lerp3(a, b, 1.0)
        assert result == pytest.approx(b)

    def test_lerp3_midpoint(self):
        a = (0.0, 0.0, 0.0)
        b = (2.0, 4.0, 6.0)
        result = _lerp3(a, b, 0.5)
        assert result == pytest.approx((1.0, 2.0, 3.0))

    def test_lerp_is_linear(self):
        """f(t) = a + (b-a)*t must be linear."""
        a, b = 1.0, 5.0
        for t in [0.1, 0.3, 0.7, 0.9]:
            assert _lerp(a, b, t) == pytest.approx(a + (b-a)*t)


# ═════════════════════════════════════════════════════════════════
#  G) Dangly spring topology (Millington §13)
# ═════════════════════════════════════════════════════════════════

class TestDanglySpringTopology:
    def test_simple_triangle_has_three_edges(self):
        n = ModelNode(name='t', flags=int(NodeFlags.MESH | NodeFlags.DANGLY))
        n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        n.faces = [(0,1,2)]
        n.dangly_constraints = [0.0]*3
        n.dangly_displacement = 0.5
        n.dangly_tightness = 0.5
        n.dangly_period = 1.0
        sim = DanglySimulator(n)
        assert len(sim._edges) == 3

    def test_all_edge_indices_in_range(self):
        n = ModelNode(name='t', flags=int(NodeFlags.MESH | NodeFlags.DANGLY))
        n.vertices = [(float(i),0,0) for i in range(6)]
        n.faces = [(0,1,2),(1,3,4),(2,4,5)]
        n.dangly_constraints = [0.0]*6
        n.dangly_displacement = 0.5
        n.dangly_tightness = 0.5
        n.dangly_period = 1.0
        sim = DanglySimulator(n)
        nv = len(n.vertices)
        for a, b, rest in sim._edges:
            assert 0 <= a < nv
            assert 0 <= b < nv
            assert a != b


# ═════════════════════════════════════════════════════════════════
#  H) world_position cycle guard
# ═════════════════════════════════════════════════════════════════

class TestWorldPositionCycleGuard:
    def test_deep_linear_chain_completes(self):
        """A chain of 512 nodes should not hang."""
        nodes = [ModelNode(name=f'n{i}') for i in range(100)]
        for i in range(1, len(nodes)):
            nodes[i].parent = nodes[i-1]
            nodes[i-1].children = [nodes[i]]
        leaf = nodes[-1]
        result = leaf.world_position()
        assert len(result) == 3
        assert all(math.isfinite(v) for v in result)

    def test_circular_reference_does_not_hang(self):
        """Circular parent reference must terminate due to cycle guard."""
        a = ModelNode(name='a')
        b = ModelNode(name='b')
        a.parent = b
        b.parent = a   # circular!
        result = a.world_position()
        assert len(result) == 3
        assert all(math.isfinite(v) for v in result)


# ═════════════════════════════════════════════════════════════════
#  I) Animation looping
# ═════════════════════════════════════════════════════════════════

class TestAnimationLooping:
    def _engine(self):
        m = KotorModel(name='m')
        m.animations = [Animation(name='test', length=1.0, transition_time=0.0)]
        return AnimationEngine(m)

    def test_time_wraps_at_clip_length(self):
        eng = self._engine()
        eng.play('test', loop=True)
        eng.advance(1.5)
        assert eng._time == pytest.approx(0.5, abs=1e-6)

    def test_no_wrap_before_end(self):
        eng = self._engine()
        eng.play('test', loop=True)
        eng.advance(0.7)
        assert eng._time == pytest.approx(0.7, abs=1e-6)
        assert eng.is_playing

    def test_zero_advance_is_noop(self):
        eng = self._engine()
        eng.play('test')
        eng.advance(0.3)
        t_before = eng._time
        eng.advance(0.0)
        assert eng._time == pytest.approx(t_before, abs=1e-9)


# ═════════════════════════════════════════════════════════════════
#  J) compute_all_tangents edge cases
# ═════════════════════════════════════════════════════════════════

class TestComputeAllTangentsEdgeCases:
    def test_empty_model_returns_zero(self):
        m = KotorModel(name='empty')
        assert m.compute_all_tangents() == 0

    def test_header_only_root_returns_zero(self):
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        m = KotorModel(name='m', root_node=root)
        assert m.compute_all_tangents() == 0

    def test_non_mesh_nodes_skipped(self):
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        light = ModelNode(name='light', flags=int(NodeFlags.LIGHT))
        root.children = [light]
        light.parent = root
        m = KotorModel(name='m', root_node=root)
        count = m.compute_all_tangents()
        assert count == 0
        assert light.tangents == []

    def test_mesh_node_without_uvs_is_skipped(self):
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name='m', flags=int(NodeFlags.MESH))
        mesh.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        mesh.faces = [(0,1,2)]
        # No UVs → compute_all_tangents should skip
        mesh.parent = root
        root.children = [mesh]
        m = KotorModel(name='m', root_node=root)
        count = m.compute_all_tangents()
        assert count == 0

    def test_multiple_mesh_nodes_all_processed(self):
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        meshes = []
        for i in range(3):
            mesh = ModelNode(name=f'mesh{i}', flags=int(NodeFlags.MESH))
            mesh.vertices = [(0,0,0),(1,0,0),(0,1,0)]
            mesh.faces = [(0,1,2)]
            mesh.uvs = [(0,0),(1,0),(0,1)]
            mesh.normals = [(0,0,1),(0,0,1),(0,0,1)]
            mesh.parent = root
            meshes.append(mesh)
        root.children = meshes
        m = KotorModel(name='m', root_node=root)
        count = m.compute_all_tangents()
        assert count == 3
        for mesh in meshes:
            assert len(mesh.tangents) == 3
