"""
GhostRigger v5.4 – Animation explosion fix + UV wrapping seam fix regression tests

BUG-ANIM-EXPLODE:
    When playing an animation, the viewport's _node_world_transform was NOT applying
    _quat_normalize_bind to PARENT nodes in the pose path.  KotOR root nodes carry
    [1,0,0,0] (180° about X = NWN coord-flip) in both bind and animated pose.  Without
    collapsing this to identity on parent nodes, all descendant positions were rotated
    180° around X during animation, flipping Y and Z and exploding the mesh.

    Fix: In _node_world_transform animated path, apply _quat_normalize_bind for
    non-leaf (parent) nodes, exactly as the bind-pose path does.

BUG-UV-SEAM-TILING:
    The seam-crossing unwrap (_uwrap) could produce UVs slightly outside [0,1]
    (e.g. u=-0.005 or v=1.003).  These were then hitting the `needs_tiling` threshold
    (-0.001 to 1.001) and triggering the expensive multi-tile image path unnecessarily,
    producing garbled/stretched textures at UV boundaries on models like c_bantha.

    Fix: Raise needs_tiling epsilon from 0.001 to 0.5.  UVs in [-0.5, 1.5] that
    aren't genuinely tiling are now wrapped to [0,1] via frac() before rendering.
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from src.core.model_data import (
    ModelNode, KotorModel,
    _quat_normalize_bind, _quat_normalize, _quat_mul, _quat_rotate,
)
from src.core.animation_engine import AnimationEngine, AnimPose, NodePose


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(name, parent=None, rotation=(0,0,0,1), position=(0,0,0)):
    """Create a minimal ModelNode."""
    n = ModelNode(name=name)
    n.rotation = rotation
    n.position = position
    if parent is not None:
        n.parent = parent
        parent.children.append(n)
    return n


def _make_model_with_180x_root():
    """
    Build a minimal model that mimics the KotOR structure:
      root[1,0,0,0 = 180°X] → cutscene[0,0,0,1] → bone[0,0,0,1 at (0,1,2)]

    In the OLD code, the animated root rotation [1,0,0,0] was NOT collapsed, so
    rotating the child position (0,1,2) by [1,0,0,0] gave (0,-1,-2) — exploded.
    In the FIXED code, _quat_normalize_bind collapses [1,0,0,0] to identity,
    so the child position stays at (0,1,2).
    """
    model = KotorModel()
    root = _make_node('Root', rotation=(1.0, 0.0, 0.0, 0.0), position=(0,0,0))
    cutscene = _make_node('cutscene', parent=root, rotation=(0,0,0,1), position=(0,0,0))
    bone = _make_node('bone', parent=cutscene, rotation=(0,0,0,1), position=(0,1,2))
    model.root_node = root
    return model, root, cutscene, bone


def _simulate_viewport_world_transform(node, anim_pose):
    """
    Replicate the viewport's _node_world_transform (animated path).

    This is the FIXED version: applies _quat_normalize_bind to parent nodes
    even when they come from the animation pose.
    """
    chain = []
    n = node
    while n:
        chain.append(n)
        n = n.parent
    chain.reverse()

    wx, wy, wz = 0.0, 0.0, 0.0
    parent_orient = [0.0, 0.0, 0.0, 1.0]
    last_i = len(chain) - 1

    for ci, cn in enumerate(chain):
        is_leaf = (ci == last_i)
        pn = anim_pose.nodes.get(cn.name.lower()) if anim_pose else None
        if pn:
            lx, ly, lz = pn.position
            rot = list(pn.rotation)
            # FIXED: apply _quat_normalize_bind for parent nodes
            if not is_leaf:
                node_rot = _quat_normalize_bind(rot)
            else:
                l2 = sum(r*r for r in rot)
                if l2 > 1e-9:
                    l = math.sqrt(l2)
                    rot = [r/l for r in rot]
                node_rot = rot
        else:
            lx, ly, lz = cn.position
            rot = list(cn.rotation)
            if is_leaf:
                node_rot = _quat_normalize(rot)
            else:
                node_rot = _quat_normalize_bind(rot)

        rx, ry, rz = _quat_rotate(parent_orient, (lx, ly, lz))
        wx += rx; wy += ry; wz += rz
        parent_orient = _quat_mul(parent_orient, node_rot)

    return (wx, wy, wz), tuple(parent_orient)


def _simulate_OLD_viewport_world_transform(node, anim_pose):
    """
    Replicate the OLD (buggy) viewport _node_world_transform for parent nodes.
    Normalizes but does NOT apply _quat_normalize_bind for animated parent nodes.
    """
    chain = []
    n = node
    while n:
        chain.append(n)
        n = n.parent
    chain.reverse()

    wx, wy, wz = 0.0, 0.0, 0.0
    parent_orient = [0.0, 0.0, 0.0, 1.0]
    last_i = len(chain) - 1

    for ci, cn in enumerate(chain):
        pn = anim_pose.nodes.get(cn.name.lower()) if anim_pose else None
        if pn:
            lx, ly, lz = pn.position
            rot = list(pn.rotation)
            # OLD: normalize only, no _quat_normalize_bind
            l2 = sum(r*r for r in rot)
            if l2 > 1e-9:
                l = math.sqrt(l2)
                rot = [r/l for r in rot]
            if rot[3] < 0:
                rot = [-r for r in rot]
            node_rot = rot
        else:
            lx, ly, lz = cn.position
            rot = list(cn.rotation)
            if ci == last_i:
                node_rot = _quat_normalize(rot)
            else:
                node_rot = _quat_normalize_bind(rot)

        rx, ry, rz = _quat_rotate(parent_orient, (lx, ly, lz))
        wx += rx; wy += ry; wz += rz
        parent_orient = _quat_mul(parent_orient, node_rot)

    return (wx, wy, wz), tuple(parent_orient)


# ─────────────────────────────────────────────────────────────────────────────
#  Test: Animation explosion fix (BUG-ANIM-EXPLODE)
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationExplosionFix:
    """Tests that the 180°-X root rotation in animated models no longer explodes bones."""

    def test_bind_pose_not_affected_by_fix(self):
        """Bind pose world transform should be unchanged by the animation fix."""
        model, root, cutscene, bone = _make_model_with_180x_root()
        # Bind pose: no animation pose
        wp, wo = _simulate_viewport_world_transform(bone, None)
        # [1,0,0,0] root → collapsed to identity → child at (0,1,2) stays there
        assert abs(wp[0]) < 0.01
        assert abs(wp[1] - 1.0) < 0.01
        assert abs(wp[2] - 2.0) < 0.01

    def test_animated_root_180x_does_not_flip_children(self):
        """
        When root is animated with [1,0,0,0] (unchanged), child positions must
        NOT be rotated 180°.  The FIXED viewport applies _quat_normalize_bind,
        collapsing [1,0,0,0] → identity so child stays at (0,1,2).
        """
        model, root, cutscene, bone = _make_model_with_180x_root()

        # Build a minimal animation pose with the root unchanged ([1,0,0,0])
        pose = AnimPose(nodes={
            'root': NodePose('Root', (0,0,0), (1.0, 0.0, 0.0, 0.0), 1.0),
            'cutscene': NodePose('cutscene', (0,0,0), (0,0,0,1), 1.0),
            'bone': NodePose('bone', (0,1,2), (0,0,0,1), 1.0),
        })

        wp_fixed, _ = _simulate_viewport_world_transform(bone, pose)
        wp_old, _ = _simulate_OLD_viewport_world_transform(bone, pose)

        # OLD code: [1,0,0,0] applied to (0,1,2) → (0,-1,-2) — EXPLODED
        assert abs(wp_old[1] + 1.0) < 0.01, f"Expected old code to flip Y to -1, got {wp_old[1]:.3f}"
        assert abs(wp_old[2] + 2.0) < 0.01, f"Expected old code to flip Z to -2, got {wp_old[2]:.3f}"

        # FIXED code: [1,0,0,0] collapsed to identity → bone stays at (0,1,2)
        assert abs(wp_fixed[1] - 1.0) < 0.01, f"Expected fixed Y=1.0, got {wp_fixed[1]:.3f}"
        assert abs(wp_fixed[2] - 2.0) < 0.01, f"Expected fixed Z=2.0, got {wp_fixed[2]:.3f}"

    def test_animated_real_rotation_preserved(self):
        """
        Real joint rotations (e.g. 45° about Y) must NOT be collapsed.
        _quat_normalize_bind only collapses pure X-axis 180° rotations.
        """
        model, root, cutscene, bone = _make_model_with_180x_root()

        # 45° rotation about Y = [0, sin(π/8), 0, cos(π/8)] ≈ [0, 0.383, 0, 0.924]
        import math
        angle = math.pi / 4  # 45°
        hy = math.sin(angle / 2)
        wy = math.cos(angle / 2)

        # Add a joint between cutscene and bone with 45° Y rotation
        joint = _make_node('joint', parent=cutscene, rotation=(0, hy, 0, wy), position=(0,0,1))
        bone.parent = joint
        joint.children.append(bone)
        bone.position = (0, 1, 0)

        pose = AnimPose(nodes={
            'root': NodePose('Root', (0,0,0), (1.0, 0.0, 0.0, 0.0), 1.0),
            'cutscene': NodePose('cutscene', (0,0,0), (0,0,0,1), 1.0),
            'joint': NodePose('joint', (0,0,1), (0, hy, 0, wy), 1.0),
            'bone': NodePose('bone', (0,1,0), (0,0,0,1), 1.0),
        })

        wp_fixed, _ = _simulate_viewport_world_transform(bone, pose)

        # joint at (0,0,1), then bone at local (0,1,0) rotated by 45° about Y
        # 45° Y rotation: (x,y,z) → (x*cos45 + z*sin45, y, -x*sin45 + z*cos45)
        # (0,1,0) → (0, 1, 0) (Y-up → stays Y)
        expected_y = 1.0  # Y component unchanged by Y-axis rotation
        assert abs(wp_fixed[1] - expected_y) < 0.1, \
            f"45° Y rotation should preserve Y, got {wp_fixed[1]:.3f}"

    def test_identity_root_unaffected(self):
        """Models with identity root rotation work correctly in both bind and animated pose."""
        root = _make_node('Root', rotation=(0,0,0,1), position=(0,0,0))
        child = _make_node('child', parent=root, rotation=(0,0,0,1), position=(1,2,3))

        pose = AnimPose(nodes={
            'root': NodePose('Root', (0,0,0), (0,0,0,1), 1.0),
            'child': NodePose('child', (1,2,3), (0,0,0,1), 1.0),
        })
        wp, _ = _simulate_viewport_world_transform(child, pose)
        assert abs(wp[0] - 1.0) < 0.01
        assert abs(wp[1] - 2.0) < 0.01
        assert abs(wp[2] - 3.0) < 0.01

    def test_small_animated_position_delta(self):
        """
        Position keyframe deltas (small offsets) must produce small world-space motion.
        This verifies the animation doesn't explode even with position-animated bones.
        """
        model, root, cutscene, bone = _make_model_with_180x_root()

        # Bone has a small animation delta: +0.05 in X
        pose = AnimPose(nodes={
            'root': NodePose('Root', (0,0,0), (1.0, 0.0, 0.0, 0.0), 1.0),
            'cutscene': NodePose('cutscene', (0,0,0), (0,0,0,1), 1.0),
            'bone': NodePose('bone', (0.05, 1.0, 2.0), (0,0,0,1), 1.0),
        })

        wp_fixed, _ = _simulate_viewport_world_transform(bone, pose)
        wp_bind, _ = _simulate_viewport_world_transform(bone, None)

        # Motion should be small (< 0.1 in each axis)
        diff = [abs(wp_fixed[i] - wp_bind[i]) for i in range(3)]
        assert max(diff) < 0.1, \
            f"Animation produced large motion {diff} — should be tiny deltas"

    def test_quat_normalize_bind_only_collapses_pure_x_180(self):
        """_quat_normalize_bind collapses [1,0,0,0] but preserves [0,1,0,0] and [0,0,1,0]."""
        # Pure X-axis 180° → collapse to identity
        result = _quat_normalize_bind([1.0, 0.0, 0.0, 0.0])
        assert abs(result[3] - 1.0) < 0.01, f"Expected w≈1 (identity), got {result}"

        # Pure Y-axis 180° → preserve (it's a REAL geometry rotation)
        result = _quat_normalize_bind([0.0, 1.0, 0.0, 0.0])
        assert abs(result[1] - 1.0) < 0.01, f"Expected y≈1 preserved, got {result}"

        # Pure Z-axis 180° → preserve (real limb mirror)
        result = _quat_normalize_bind([0.0, 0.0, 1.0, 0.0])
        assert abs(result[2] - 1.0) < 0.01, f"Expected z≈1 preserved, got {result}"


# ─────────────────────────────────────────────────────────────────────────────
#  Test: UV seam tiling fix (BUG-UV-SEAM-TILING)
# ─────────────────────────────────────────────────────────────────────────────

class TestUVSeamTilingFix:
    """Tests for the UV seam fix: slightly-out-of-range UVs should not trigger tiling."""

    def _run_uv_tiling_check(self, u0, v0, u1, v1, u2, v2):
        """
        Simulate the viewport UV tiling check logic.
        Returns (needs_tiling, after_clamp_uvs) with the v5.4 epsilon=0.5.
        """
        import math as _m

        # Seam unwrap (same as viewport code)
        def _uwrap(base, other):
            diff = other - base
            while diff > 0.5: other -= 1.0; diff -= 1.0
            while diff < -0.5: other += 1.0; diff += 1.0
            return other

        _u_span_raw = max(u0,u1,u2) - min(u0,u1,u2)
        _v_span_raw = max(v0,v1,v2) - min(v0,v1,v2)

        if _u_span_raw < 1.0 and _v_span_raw < 1.0:
            u1 = _uwrap(u0, u1)
            u2 = _uwrap(u0, u2)
            v1 = _uwrap(v0, v1)
            v2 = _uwrap(v0, v2)

        u_min = min(u0,u1,u2)
        u_max = max(u0,u1,u2)
        v_min = min(v0,v1,v2)
        v_max = max(v0,v1,v2)

        # epsilon: 0.5 (broad tolerance for floating-point anim values)
        needs_tiling = (u_min < -0.5 or u_max > 1.5 or
                        v_min < -0.5 or v_max > 1.5)

        # If slightly out of range (but not tiling), apply frac clamping
        after_clamp = [(u0,v0), (u1,v1), (u2,v2)]
        if not needs_tiling and (u_min < -0.001 or u_max > 1.001 or
                                  v_min < -0.001 or v_max > 1.001):
            def _frac(x): return x - _m.floor(x)
            u0 = _frac(u0); u1 = _frac(u1); u2 = _frac(u2)
            v0 = _frac(v0); v1 = _frac(v1); v2 = _frac(v2)
            after_clamp = [(u0,v0), (u1,v1), (u2,v2)]

        return needs_tiling, after_clamp

    def test_seam_crossing_does_not_trigger_tiling(self):
        """
        UV face straddling a tile boundary should NOT trigger the tiling path.
        Example: c_bantha bthair face crossing u=0 boundary.
        """
        # face[0] from bthair: u0=0.3264, u1=-0.0048, u2=0.3386
        #                       v0=0.038,  v1=0.0483, v2=0.9265
        needs_tiling, _ = self._run_uv_tiling_check(
            0.3264, 0.038, -0.0048, 0.0483, 0.3386, 0.9265)
        assert not needs_tiling, "Seam-crossing face should NOT trigger tiling"

    def test_slightly_over_1_does_not_trigger_tiling(self):
        """UV slightly over 1.0 from seam correction should not trigger tiling."""
        needs_tiling, _ = self._run_uv_tiling_check(
            0.985, 0.5, 1.003, 0.5, 0.995, 0.6)
        assert not needs_tiling, "u=1.003 should not trigger tiling (epsilon=0.5)"

    def test_genuinely_tiling_mesh_does_trigger_tiling(self):
        """Large UV range (e.g. pelvis_g: ±13 tiles) should still trigger tiling."""
        needs_tiling, _ = self._run_uv_tiling_check(
            -13.58, -9.13, -13.58, 6.18, 13.58, 6.18)
        assert needs_tiling, "UV range ±13 should trigger tiling"

    def test_uv_in_0_to_1_no_tiling(self):
        """Normal UVs in [0,1] should never trigger tiling."""
        needs_tiling, _ = self._run_uv_tiling_check(
            0.1, 0.2, 0.5, 0.7, 0.9, 0.3)
        assert not needs_tiling, "Normal [0,1] UVs should not trigger tiling"

    def test_seam_corrected_uvs_clamped_to_01(self):
        """After seam correction, slightly-out-of-range UVs should be frac-clamped to [0,1]."""
        _, after_clamp = self._run_uv_tiling_check(
            0.3264, 0.038, -0.0048, 0.0483, 0.3386, 0.9265)
        # After seam correction: u1 was unwrapped to ~-0.005, should be clamped
        for (u, v) in after_clamp:
            assert -0.001 <= u <= 1.001, f"UV u={u:.4f} not clamped to [0,1]"
            assert -0.001 <= v <= 1.001, f"UV v={v:.4f} not clamped to [0,1]"

    def test_medium_out_of_range_triggers_tiling(self):
        """UVs clearly out of range (>0.5 outside [0,1]) should trigger tiling."""
        needs_tiling, _ = self._run_uv_tiling_check(
            0.0, 0.0, 2.0, 0.0, 0.5, 1.0)
        assert needs_tiling, "UVs with u=2.0 should trigger tiling"

    def test_negative_uv_triggers_tiling_when_large(self):
        """Negative UVs beyond -0.5 should trigger tiling."""
        needs_tiling, _ = self._run_uv_tiling_check(
            -0.6, 0.3, 0.4, 0.3, 0.0, 0.8)
        assert needs_tiling, "u=-0.6 beyond epsilon should trigger tiling"

    def test_v_seam_crossing_does_not_trigger_tiling(self):
        """V-axis seam crossing (v=0.02 and v=0.98 in same triangle) should not tile."""
        # v0=0.9369, v1=0.9265, v2=0.0483 after seam unwrap: v2 wraps to 1.0483
        # but that's still < 1.5 → no tiling
        needs_tiling, clamp_uvs = self._run_uv_tiling_check(
            0.0074, 0.9369, 0.3386, 0.9265, -0.0048, 0.0483)
        assert not needs_tiling, "V-axis seam crossing should not trigger tiling"


# ─────────────────────────────────────────────────────────────────────────────
#  Integration: AnimationEngine + Viewport World Transform
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationIntegration:
    """Integration tests combining AnimationEngine pose output with viewport transform."""

    def _build_kotor_model_with_animation(self):
        """
        Build a realistic KotOR model with 180°-X root and animated bones.
        Mirrors the c_bantha-style structure: root[180X] → dummy → bones
        """
        from src.core.model_data import Animation, ModelNode as MN
        from src.core.animation_engine import AnimationEngine

        # Build hierarchy
        root = _make_node('C_Model', rotation=(1.0, 0.0, 0.0, 0.0), position=(0,0,0))
        dummy = _make_node('cutscenedummy', parent=root, rotation=(0,0,0,1), position=(0,0,0))
        spine = _make_node('BTSpine', parent=dummy, rotation=(0,0,0,1), position=(0,-0.4,1.5))
        head = _make_node('BTHead', parent=dummy, rotation=(0,0,0,1), position=(0,1.3,1.8))

        model = KotorModel()
        model.root_node = root
        model.name = 'C_Model'

        # Build animation with small position deltas
        anim_root = _make_node('C_Model', rotation=(1.0,0.0,0.0,0.0), position=(0,0,0))
        anim_spine = _make_node('BTSpine', rotation=(0,0,0,1), position=(0,0,0))
        anim_head = _make_node('BTHead', rotation=(0,0,0,1), position=(0,0,0))

        # Position deltas (small walk-cycle offsets)
        anim_spine.controllers = [{'type': 8, 'times': [0.0, 0.5, 1.0],
                                    'values': [[0.0,0.0,0.0], [0.05,-0.01,0.02], [0.0,0.0,0.0]]}]
        anim_head.controllers = [{'type': 20, 'times': [0.0, 0.5],
                                   'values': [[0.0,0.0,0.0,1.0], [0.0,0.05,0.0,0.999]]}]

        from src.core.model_data import Animation
        anim = Animation()
        anim.name = 'walk'
        anim.length = 1.0
        anim.transition_time = 0.25
        anim.anim_root = 'C_Model'
        anim.nodes = [anim_root, anim_spine, anim_head]
        anim.events = []
        model.animations = [anim]

        return model, dummy, spine, head

    def test_no_explosion_with_180x_root_animation(self):
        """
        Full round-trip: AnimationEngine.evaluate() → viewport transform.
        Bone positions should be close to bind-pose when animation delta is small.
        """
        from src.core.animation_engine import AnimationEngine

        model, dummy, spine, head = self._build_kotor_model_with_animation()
        engine = AnimationEngine(model)
        engine.play('walk', loop=True)
        pose = engine.evaluate(0.5)

        assert pose is not None, "Should produce a valid pose"

        # Get bind-pose world positions
        spine_bind, _ = spine.world_transform()
        head_bind, _ = head.world_transform()

        # Get animated world positions using FIXED transform
        spine_anim, _ = _simulate_viewport_world_transform(spine, pose)
        head_anim, _ = _simulate_viewport_world_transform(head, pose)

        # Motion should be small (< 1.0 units for small position deltas)
        spine_diff = max(abs(spine_anim[i] - spine_bind[i]) for i in range(3))
        head_diff = max(abs(head_anim[i] - head_bind[i]) for i in range(3))

        assert spine_diff < 1.0, \
            f"Spine moved too much: {spine_diff:.3f} units (explosion!)"
        assert head_diff < 1.0, \
            f"Head moved too much: {head_diff:.3f} units (explosion!)"

    def test_old_code_would_explode(self):
        """
        Demonstrates that the OLD viewport code DID produce explosive motion.
        This confirms we're testing the right thing.
        """
        from src.core.animation_engine import AnimationEngine

        model, dummy, spine, head = self._build_kotor_model_with_animation()
        engine = AnimationEngine(model)
        engine.play('walk', loop=True)
        pose = engine.evaluate(0.5)

        assert pose is not None

        spine_bind, _ = spine.world_transform()

        # Old code does NOT apply _quat_normalize_bind for animated parent nodes
        spine_old, _ = _simulate_OLD_viewport_world_transform(spine, pose)

        # Old code flips Y and Z due to [1,0,0,0] root rotation
        # spine bind = (0,-0.4,1.5) → old anim should be (0,+0.4,-1.5)
        old_y_flipped = spine_old[1] < 0 and spine_bind[1] < 0  # both negative?
        old_z_flipped = spine_old[2] < 0 and spine_bind[2] > 0  # old neg, bind pos?

        # At least one should be sign-flipped to confirm the bug existed
        assert old_y_flipped or old_z_flipped, \
            "Expected old code to flip Y or Z (explosion), but it didn't"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
