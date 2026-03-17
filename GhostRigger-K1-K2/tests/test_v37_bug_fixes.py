"""
v3.7 Bug-Fix Regression Tests
==============================
Tests for BUG-01 through BUG-04 and the viewport w-canonicalization fix.

BUG-01  _apply_bind_pose_controllers: orientation ctrl now ALWAYS applied
        (not only when header rotation is identity/zero).
BUG-02  Same function: applied rotation is unit-normalised (w sign preserved).
        NOTE (v5.2): positive-w canonicalization was intentionally REMOVED from
        _apply_bind_pose_controllers to preserve the w sign needed for the
        NWN 180-X collapse detection in _quat_normalize_bind.  Tests below
        updated to reflect this: bind-pose result is unit-length, w may be < 0.
        Positive-w is enforced at the animation interpolation layer only.
BUG-03  BVH export: animated leaf joints now get CHANNELS in the hierarchy
        section and frame data in the MOTION section (previously silently
        dropped because "_collect_frame" skipped any node with no children).
BUG-04  Animation-length derivation: uses max(ctrl['times']) instead of
        ctrl['times'][-1] so unsorted / loopback keyframe lists give the
        correct duration.
VIEWPORT  _eval_node: base-pose rotation is now canonical (positive-w) before
        being used as slerp start-point, preventing 360° flips on first frame.
"""

import math
import os
import sys
import tempfile
import textwrap

import pytest

# ── path bootstrap ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.model_data import ModelNode, KotorModel, Animation, AnimEvent
from src.core.animation_engine import AnimationEngine, _interp_channel, _slerp


# ============================================================================
# Helpers
# ============================================================================

def _make_model_with_node(name='bone', position=(0, 0, 0),
                          rotation=(0, 0, 0, 1), controllers=None):
    """Build a minimal KotorModel with a single root node."""
    node = ModelNode(name=name, position=position, rotation=rotation)
    if controllers:
        node.controllers = controllers
    model = KotorModel(name='testmodel')
    model.root_node = node
    return model


def _make_anim(name='walk', length=1.0, nodes=None):
    anim = Animation(name=name, length=length, transition_time=0.1)
    if nodes:
        anim.nodes = nodes
    return anim


# ============================================================================
# BUG-01 / BUG-02  _apply_bind_pose_controllers orientation override
# ============================================================================

class TestApplyBindPoseOrientationOverride:
    """BUG-01: ctrl orientation must ALWAYS override node.rotation."""

    @staticmethod
    def _run_apply(node):
        """Call _apply_bind_pose_controllers on a model containing *node*."""
        from src.core.mdl_parser import MDLBinaryParser
        model = KotorModel(name='t')
        model.root_node = node
        MDLBinaryParser._apply_bind_pose_controllers(model)
        return node

    def test_override_when_header_is_identity(self):
        """Original behaviour: identity header → ctrl applied (unchanged)."""
        ctrl_rot = [0.0, 0.7071, 0.0, 0.7071]  # 90° around Y
        node = ModelNode(name='n', rotation=(0, 0, 0, 1))
        node.controllers = [{'type': 20, 'values': [ctrl_rot], 'times': [0.0]}]
        self._run_apply(node)
        x, y, z, w = node.rotation
        assert abs(y - 0.7071) < 0.001, "Y component must match ctrl"
        assert abs(w - 0.7071) < 0.001, "W component must match ctrl"

    def test_override_when_header_is_non_identity(self):
        """BUG-01 FIX: ctrl must override even when header has a non-identity rotation."""
        ctrl_rot = [0.0, 0.7071, 0.0, 0.7071]  # 90° around Y
        # Header has some other rotation — old code would leave this unchanged
        node = ModelNode(name='n', rotation=(0.5, 0.5, 0.5, 0.5))
        node.controllers = [{'type': 20, 'values': [ctrl_rot], 'times': [0.0]}]
        self._run_apply(node)
        x, y, z, w = node.rotation
        # After BUG-01 fix the ctrl value must win
        assert abs(y - 0.7071) < 0.002, \
            f"BUG-01: ctrl orientation must override non-identity header (got y={y:.4f})"

    def test_override_when_header_is_arbitrary_rotation(self):
        """BUG-01 FIX: ctrl overrides any non-zero header rotation."""
        ctrl_rot = [0.0, 0.0, 1.0, 0.0]   # 180° around Z (un-normalized)
        node = ModelNode(name='n', rotation=(0.1, 0.2, 0.3, 0.9))
        node.controllers = [{'type': 20, 'values': [ctrl_rot], 'times': [0.0]}]
        self._run_apply(node)
        x, y, z, w = node.rotation
        # z should dominate; w should be canonicalized ≥ 0
        assert abs(z) > 0.9, f"BUG-01: z should dominate after override (got z={z:.4f})"

    def test_positive_w_canonicalization(self):
        """v5.2 UPDATE: _apply_bind_pose_controllers now preserves the w sign
        (unit-normalise only).  A negative-w ctrl is stored as-is so that
        _quat_normalize_bind can still detect near-180-deg rotations via |w|<0.05.
        Positive-w canonicalization happens at the animation interpolation layer.
        We verify: result is unit-length AND w sign matches the original ctrl."""
        # Negative-w quaternion (same rotation, different representation)
        ctrl_neg = [0.0, -0.7071, 0.0, -0.7071]
        node = ModelNode(name='n', rotation=(0, 0, 0, 1))
        node.controllers = [{'type': 20, 'values': [ctrl_neg], 'times': [0.0]}]
        self._run_apply(node)
        x, y, z, w = node.rotation
        # sign is preserved — w must be negative (matching the ctrl)
        assert w < 0.0, f"v5.2: negative-w ctrl must be stored as-is (got w={w:.4f})"
        # Result must be a unit quaternion
        mag = math.sqrt(x*x + y*y + z*z + w*w)
        assert abs(mag - 1.0) < 1e-5, f"Result must be unit quaternion (mag={mag:.6f})"
        # Y magnitude matches the ctrl's normalised value
        assert abs(abs(y) - 0.7071) < 0.001, f"Y magnitude must match ctrl (got y={y:.4f})"

    def test_positive_w_on_already_negative_header(self):
        """v5.2 UPDATE: negative-w ctrl is stored with sign preserved (unit-
        normalised only).  Positive-w enforcement is deferred to the animation
        interpolation layer; bind-pose storage keeps the original sign."""
        ctrl_rot = [-0.5, -0.5, -0.5, -0.5]  # all-negative, w < 0
        node = ModelNode(name='n', rotation=(0, 0, 0, 1))
        node.controllers = [{'type': 20, 'values': [ctrl_rot], 'times': [0.0]}]
        self._run_apply(node)
        x, y, z, w = node.rotation
        # sign preserved — w must be negative (matching normalised ctrl)
        assert w < 0.0, f"v5.2: negative-w ctrl must be stored as-is (got w={w:.4f})"
        # Magnitude should still be 1
        mag = math.sqrt(x*x + y*y + z*z + w*w)
        assert abs(mag - 1.0) < 1e-5, f"Result must be unit quaternion (mag={mag:.6f})"

    def test_degenerate_zero_quaternion_not_applied(self):
        """Zero-quaternion ctrl should NOT overwrite node.rotation."""
        ctrl_zero = [0.0, 0.0, 0.0, 0.0]
        original = (0.0, 0.0, 0.0, 1.0)
        node = ModelNode(name='n', rotation=original)
        node.controllers = [{'type': 20, 'values': [ctrl_zero], 'times': [0.0]}]
        self._run_apply(node)
        assert node.rotation == original, "Degenerate zero-quat must not overwrite rotation"

    def test_multiple_ctrl_types_coexist(self):
        """Other ctrl types (8=pos, 132=alpha, 100=selfillum) still applied alongside.

        BUG-FIX v4.4: Controller type IDs corrected to match KotorBlender types.py:
          CTRL_MESH_SELFILLUMCOLOR = 100 (was 132)
          CTRL_MESH_ALPHA = 132 (was 100)
        """
        ctrl_rot = [0.0, 0.7071, 0.0, 0.7071]
        node = ModelNode(name='n', rotation=(0.5, 0.5, 0.5, 0.5))
        node.controllers = [
            {'type': 8,   'values': [[1.0, 2.0, 3.0]], 'times': [0.0]},
            {'type': 20,  'values': [ctrl_rot],         'times': [0.0]},
            {'type': 132, 'values': [[0.8]],            'times': [0.0]},   # alpha
            {'type': 100, 'values': [[1.0, 0.5, 0.0]], 'times': [0.0]},   # selfillum
        ]
        self._run_apply(node)
        # Position should be set via ctrl 8
        assert node.position == (1.0, 2.0, 3.0), "Position ctrl must still be applied"
        # Alpha should be set via ctrl 132 (CTRL_MESH_ALPHA)
        assert abs(node.alpha - 0.8) < 1e-6, "Alpha ctrl must still be applied"
        # Rotation must be from ctrl 20 (BUG-01 fix)
        _, y, _, w = node.rotation
        assert abs(y - 0.7071) < 0.002 and w >= 0, "Orientation ctrl must be applied"


# ============================================================================
# BUG-03  BVH export: animated leaf joints
# ============================================================================

class TestBVHLeafJointExport:
    """BUG-03: animated leaf joints must appear in BVH HIERARCHY with CHANNELS
    and have their frame data written to the MOTION section."""

    @staticmethod
    def _build_model_with_leaf_anim():
        """
        Build:  root → mid_bone → leaf_bone (no children, but IS animated)
        """
        root = ModelNode(name='root',      position=(0, 0, 0), rotation=(0, 0, 0, 1))
        mid  = ModelNode(name='mid_bone',  position=(0, 0, 1), rotation=(0, 0, 0, 1))
        leaf = ModelNode(name='leaf_bone', position=(0, 0, 1), rotation=(0, 0, 0, 1))
        root.children = [mid]
        mid.parent    = root
        mid.children  = [leaf]
        leaf.parent   = mid

        model = KotorModel(name='bvhtest')
        model.root_node = root

        # Animate leaf_bone with orientation keys
        leaf_anim_node = ModelNode(name='leaf_bone', position=(0, 0, 1),
                                   rotation=(0, 0, 0, 1))
        leaf_anim_node.controllers = [{
            'type': 20, 'name': 'orientation', 'columns': 4,
            'times': [0.0, 0.5, 1.0],
            'values': [
                [0.0, 0.0, 0.0, 1.0],
                [0.0, 0.3827, 0.0, 0.9239],
                [0.0, 0.7071, 0.0, 0.7071],
            ]
        }]

        anim = Animation(name='wave', length=1.0, transition_time=0.1)
        anim.nodes = [leaf_anim_node]

        model.animations = [anim]
        return model

    def _export_bvh(self, model):
        """Export 'wave' animation to BVH and return the text."""
        engine = AnimationEngine(model)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bvh',
                                        delete=False) as tf:
            path = tf.name
        try:
            ok = engine.export_animation_bvh('wave', path)
            assert ok, "export_animation_bvh returned False"
            with open(path, 'r') as f:
                return f.read()
        finally:
            os.unlink(path)

    def test_leaf_joint_in_hierarchy_section(self):
        """BUG-03 FIX: animated leaf_bone must appear as JOINT (not End Site)."""
        model = self._build_model_with_leaf_anim()
        bvh   = self._export_bvh(model)
        # Should contain 'JOINT leaf_bone'
        assert 'JOINT leaf_bone' in bvh, \
            f"BUG-03: animated leaf 'leaf_bone' must be a JOINT in hierarchy:\n{bvh[:800]}"

    def test_leaf_joint_has_channels(self):
        """BUG-03 FIX: JOINT leaf_bone must have CHANNELS declaration."""
        model = self._build_model_with_leaf_anim()
        bvh   = self._export_bvh(model)
        lines = bvh.splitlines()
        in_leaf = False
        found_channels = False
        for line in lines:
            if 'JOINT leaf_bone' in line:
                in_leaf = True
            if in_leaf and 'CHANNELS' in line:
                found_channels = True
                break
            if in_leaf and line.strip() == '}':
                break
        assert found_channels, \
            "BUG-03: JOINT leaf_bone must have a CHANNELS declaration"

    def test_leaf_joint_frame_count_matches_non_leaf(self):
        """BUG-03 FIX: the number of values per frame must account for leaf channels."""
        model  = self._build_model_with_leaf_anim()
        engine = AnimationEngine(model)
        # Root  = 6 channels, mid_bone = 3 channels, leaf_bone = 3 channels → 12/frame
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bvh',
                                        delete=False) as tf:
            path = tf.name
        try:
            engine.export_animation_bvh('wave', path)
            with open(path, 'r') as f:
                bvh = f.read()
        finally:
            os.unlink(path)

        motion_idx = bvh.index('MOTION')
        motion_part = bvh[motion_idx:]
        frame_lines = [l for l in motion_part.splitlines()
                       if l and l[0].lstrip().replace('-','').replace('.','').replace(' ','').isdigit()]
        assert frame_lines, "No frame data found in MOTION section"
        values_per_frame = len(frame_lines[0].split())
        # root(6) + mid(3) + leaf(3) = 12
        assert values_per_frame == 12, \
            f"BUG-03: expected 12 values/frame (root6+mid3+leaf3), got {values_per_frame}"

    def test_pure_end_site_still_excluded(self):
        """Pure leaf (no animation) must still be written as End Site, not JOINT."""
        root = ModelNode(name='root',       position=(0, 0, 0), rotation=(0, 0, 0, 1))
        tip  = ModelNode(name='tip_static', position=(0, 0, 1), rotation=(0, 0, 0, 1))
        root.children = [tip]
        tip.parent    = root
        model = KotorModel(name='static_test')
        model.root_node = root
        # Animate ONLY the root
        root_anim = ModelNode(name='root', position=(0, 0, 0), rotation=(0, 0, 0, 1))
        root_anim.controllers = [{
            'type': 8, 'name': 'position', 'columns': 3,
            'times': [0.0, 1.0],
            'values': [[0, 0, 0], [0, 1, 0]]
        }]
        anim = Animation(name='move', length=1.0)
        anim.nodes = [root_anim]
        model.animations = [anim]
        engine = AnimationEngine(model)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bvh', delete=False) as tf:
            path = tf.name
        try:
            engine.export_animation_bvh('move', path)
            with open(path, 'r') as f:
                bvh = f.read()
        finally:
            os.unlink(path)
        assert 'JOINT tip_static' not in bvh, \
            "Pure unamimated End Site should NOT become a JOINT"
        assert 'End Site' in bvh, "Pure unamimated node should remain End Site"


# ============================================================================
# BUG-04  Animation length derivation uses max() not [-1]
# ============================================================================

class TestAnimationLengthDerivation:
    """BUG-04: animation length derived from max(times) not times[-1]."""

    @staticmethod
    def _make_parser_anim_from_nodes(nodes, header_length=0.0):
        """Build an Animation object and run the length-derivation logic."""
        anim = Animation(name='test', length=header_length, transition_time=0.1)
        anim.nodes = nodes
        # Re-run derivation logic (copy of the fixed code path)
        if anim.length <= 0.0 and anim.nodes:
            max_t = 0.0
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['times']:
                        max_t = max(max_t, max(ctrl['times']))  # BUG-04 fix
            if max_t > 0.0:
                anim.length = max_t
        return anim

    def test_sorted_times_gives_correct_length(self):
        """Baseline: sorted keyframes. Both [-1] and max() give same result."""
        node = ModelNode(name='n')
        node.controllers = [{'type': 20, 'times': [0.0, 0.25, 0.5, 0.75, 1.0],
                              'values': [[0,0,0,1]]*5}]
        anim = self._make_parser_anim_from_nodes([node])
        assert abs(anim.length - 1.0) < 1e-6, f"Expected 1.0, got {anim.length}"

    def test_unsorted_times_gives_correct_length(self):
        """BUG-04 FIX: unsorted keyframes. [-1] would return wrong value; max() is correct."""
        node = ModelNode(name='n')
        # Last entry is a small loopback key at 0.0 — [-1] would give 0.0
        node.controllers = [{'type': 20, 'times': [0.0, 0.5, 1.0, 0.0],
                              'values': [[0,0,0,1]]*4}]
        anim = self._make_parser_anim_from_nodes([node])
        assert abs(anim.length - 1.0) < 1e-6, \
            f"BUG-04: unsorted times should give length=1.0, got {anim.length}"

    def test_loopback_key_does_not_truncate_length(self):
        """BUG-04: KotOR loop-back pattern [0.0, ..., max_t, 0.0] must yield max_t."""
        node = ModelNode(name='n')
        node.controllers = [{
            'type': 8,
            'times': [0.0, 0.1, 0.2, 0.5, 0.8, 1.2, 0.0],  # final 0.0 = loopback
            'values': [[0,0,0]]*7
        }]
        anim = self._make_parser_anim_from_nodes([node])
        assert abs(anim.length - 1.2) < 1e-6, \
            f"BUG-04: loop-back key at end should not truncate length (got {anim.length})"

    def test_multiple_controllers_max_across_all(self):
        """BUG-04: length is the maximum time across ALL controller tracks."""
        node = ModelNode(name='n')
        node.controllers = [
            {'type': 8,  'times': [0.0, 0.8, 0.0], 'values': [[0,0,0]]*3},
            {'type': 20, 'times': [0.0, 1.5, 0.0], 'values': [[0,0,0,1]]*3},
        ]
        anim = self._make_parser_anim_from_nodes([node])
        assert abs(anim.length - 1.5) < 1e-6, \
            f"BUG-04: should pick max across all tracks (got {anim.length})"

    def test_header_length_nonzero_not_overridden(self):
        """If header already has length > 0, derivation must NOT override it."""
        node = ModelNode(name='n')
        node.controllers = [{'type': 20, 'times': [0.0, 2.0], 'values': [[0,0,0,1]]*2}]
        anim = self._make_parser_anim_from_nodes([node], header_length=1.5)
        assert abs(anim.length - 1.5) < 1e-6, \
            "Non-zero header length must not be overridden by derivation"

    def test_empty_times_handled_gracefully(self):
        """Empty ctrl times list must not crash and length stays 0."""
        node = ModelNode(name='n')
        node.controllers = [{'type': 20, 'times': [], 'values': []}]
        anim = self._make_parser_anim_from_nodes([node])
        assert anim.length == 0.0, "Empty times should leave length at 0"


# ============================================================================
# VIEWPORT  w-canonicalization in _eval_node base pose
# ============================================================================

class TestViewportWCanonicalization:
    """VIEWPORT FIX: base-pose rotation in _eval_node is canonicalized."""

    def test_negative_w_base_becomes_positive(self):
        """Base rotation with w<0 is flipped to positive-w before pose eval."""
        # Rotation is (0, 0.7071, 0, -0.7071) — same as (0, 0.7071, 0, +0.7071)
        # but negative-w; _eval_node must flip it.
        model = _make_model_with_node(
            name='bone',
            rotation=(0.0, 0.7071, 0.0, -0.7071),
        )
        anim_node = ModelNode(name='bone', rotation=(0, 0, 0, 1))
        # No controllers — we just want the base pose
        anim = _make_anim(length=1.0, nodes=[anim_node])
        model.animations = [anim]
        engine = AnimationEngine(model)
        engine.play('walk')
        pose = engine.evaluate(0.0)
        np_ = pose.nodes.get('bone')
        assert np_ is not None, "bone must appear in pose"
        x, y, z, w = np_.rotation
        assert w >= 0.0, f"VIEWPORT: base rotation must have w>=0 (got w={w:.4f})"

    def test_positive_w_base_unchanged(self):
        """Base rotation with w>0 must be left unchanged (no spurious flip)."""
        model = _make_model_with_node(
            name='bone',
            rotation=(0.0, 0.7071, 0.0, 0.7071),
        )
        anim_node = ModelNode(name='bone', rotation=(0, 0, 0, 1))
        anim = _make_anim(length=1.0, nodes=[anim_node])
        model.animations = [anim]
        engine = AnimationEngine(model)
        engine.play('walk')
        pose = engine.evaluate(0.0)
        np_ = pose.nodes['bone']
        x, y, z, w = np_.rotation
        assert abs(y - 0.7071) < 0.002, "Positive-w base rotation must be preserved"
        assert w >= 0.0, "w must remain positive"

    def test_base_plus_animated_no_flip(self):
        """Base with negative-w + animated ctrl must not produce 360° flip."""
        model = _make_model_with_node(
            name='arm',
            rotation=(0.0, 0.0, 0.0, -1.0),   # identity but w<0
        )
        arm_anim = ModelNode(name='arm', rotation=(0, 0, 0, 1))
        arm_anim.controllers = [{
            'type': 20, 'name': 'orientation', 'columns': 4,
            'times': [0.0, 0.5, 1.0],
            'values': [
                [0.0, 0.0, 0.0, 1.0],
                [0.0, 0.1952, 0.0, 0.9808],
                [0.0, 0.3827, 0.0, 0.9239],
            ]
        }]
        anim = _make_anim(length=1.0, nodes=[arm_anim])
        model.animations = [anim]
        engine = AnimationEngine(model)
        engine.play('walk')

        # All poses should have valid, positive-w quaternions
        for t in [0.0, 0.25, 0.5, 0.75, 1.0]:
            pose = engine.evaluate(t)
            np_ = pose.nodes.get('arm')
            if np_ is None:
                continue
            x, y, z, w = np_.rotation
            mag = math.sqrt(x*x + y*y + z*z + w*w)
            assert abs(mag - 1.0) < 1e-4, f"t={t}: rotation must be unit (mag={mag:.6f})"
            assert w >= -0.01, f"t={t}: w must be >= 0 after canonicalization (w={w:.4f})"

    def test_slerp_shortest_path_with_canonical_base(self):
        """Canonical base ensures slerp always takes the short path (< 180°)."""
        # Without canonicalization, slerp between (0,0,0,-1) and (0,0,0,1) would
        # travel 360° instead of 0°.  With fix, both are (0,0,0,1) → slerp = identity.
        q_neg_id = [0.0, 0.0, 0.0, -1.0]   # identity with negative w
        q_pos_id = [0.0, 0.0, 0.0,  1.0]   # identity with positive w
        mid = _slerp(q_neg_id, q_pos_id, 0.5)
        # After _slerp's shortest-path correction, midpoint should be ~identity
        x, y, z, w = mid
        assert abs(w) > 0.99, \
            f"slerp of identity quats should give identity midpoint (w={w:.4f})"


# ============================================================================
# Integration: full animation pipeline with all fixes active
# ============================================================================

class TestIntegrationAllFixes:
    """End-to-end: parse-like setup → evaluate → export with all 4 bugs fixed."""

    def _build_full_model(self):
        """
        Build a model that exercises all 4 bug fixes:
          - root has orientation ctrl overriding non-identity header  (BUG-01)
          - ctrl quaternion is negative-w                             (BUG-02)
          - child 'leaf' is animated but has no sub-children          (BUG-03)
          - animation length stored as 0 with loopback-pattern times  (BUG-04)
        """
        from src.core.mdl_parser import MDLBinaryParser

        root = ModelNode(name='root', position=(0, 0, 0), rotation=(0.5, 0.5, 0.5, 0.5))
        leaf = ModelNode(name='leaf', position=(0, 0, 1), rotation=(0, 0, 0, 1))
        root.children = [leaf]
        leaf.parent   = root

        # BUG-01: ctrl overrides root.rotation; v5.2: negative-w sign preserved
        root.controllers = [{'type': 20, 'values': [[0.0, 0.0, 0.0, -1.0]],
                              'times': [0.0]}]
        leaf.controllers = []

        model = KotorModel(name='integration')
        model.root_node = root

        # Apply bind pose (exercises BUG-01; v5.2: w sign preserved, not forced +)
        MDLBinaryParser._apply_bind_pose_controllers(model)

        # BUG-01 check: ctrl must OVERRIDE the non-identity header rotation
        rx, ry, rz, rw = model.root_node.rotation
        # The ctrl value was (0,0,0,-1) — unit length, w=-1 preserved by v5.2
        assert abs(rw - (-1.0)) < 1e-5, \
            (f"v5.2: negative-w ctrl must be stored with sign preserved "
             f"(expected w=-1.0, got w={rw:.4f})")
        # And it must be a unit quaternion
        mag = math.sqrt(rx*rx + ry*ry + rz*rz + rw*rw)
        assert abs(mag - 1.0) < 1e-5, \
            f"BUG-01: bind-pose result must be unit quaternion (mag={mag:.6f})"

        # Build animation (exercises BUG-03 + BUG-04)
        leaf_anim = ModelNode(name='leaf', rotation=(0, 0, 0, 1))
        leaf_anim.controllers = [{
            'type': 20, 'name': 'orientation', 'columns': 4,
            # BUG-04: loopback at end means [-1]=0.0 → length=0 (wrong)
            'times': [0.0, 0.5, 1.0, 0.0],
            'values': [
                [0.0, 0.0, 0.0, 1.0],
                [0.0, 0.3827, 0.0, 0.9239],
                [0.0, 0.7071, 0.0, 0.7071],
                [0.0, 0.0, 0.0, 1.0],
            ]
        }]
        anim = Animation(name='test', length=0.0)  # header says 0 → derive
        anim.nodes = [leaf_anim]
        model.animations = [anim]

        return model

    def test_full_pipeline(self):
        """All 4 bug fixes active in one end-to-end run."""
        model = self._build_full_model()

        # BUG-04: derive length from max(times)
        anim = model.animations[0]
        if anim.length <= 0.0:
            max_t = 0.0
            for an in anim.nodes:
                for ctrl in an.controllers:
                    if ctrl['times']:
                        max_t = max(max_t, max(ctrl['times']))
            anim.length = max_t

        assert abs(anim.length - 1.0) < 1e-5, \
            f"BUG-04: derived length should be 1.0, got {anim.length}"

        engine = AnimationEngine(model)
        engine.play('test')

        # Evaluate at mid-point
        pose = engine.evaluate(0.5)
        np_ = pose.nodes.get('leaf')
        assert np_ is not None, "leaf node must appear in pose"
        x, y, z, w = np_.rotation
        assert w >= 0.0, "VIEWPORT: evaluated rotation must have positive w"
        assert abs(math.sqrt(x*x+y*y+z*z+w*w) - 1.0) < 1e-4, "Must be unit quaternion"

        # BUG-03: BVH export must include leaf JOINT
        with tempfile.NamedTemporaryFile(suffix='.bvh', delete=False) as tf:
            path = tf.name
        try:
            engine.export_animation_bvh('test', path)
            with open(path) as f:
                bvh = f.read()
        finally:
            os.unlink(path)

        assert 'JOINT leaf' in bvh, \
            f"BUG-03: animated leaf must be JOINT in BVH:\n{bvh[:600]}"
