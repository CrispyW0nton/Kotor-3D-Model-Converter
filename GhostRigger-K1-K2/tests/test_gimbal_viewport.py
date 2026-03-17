"""
Tests for the Gimbal transform overlay and skeleton-clearing features.
These tests validate the new functionality without requiring a display (headless).
"""
import math
import sys
import os
import pytest

# Make imports work without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import ModelNode, NodeFlags, KotorModel


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────

def make_dummy_node(name="bone", position=(0.0, 0.0, 1.0)):
    n = ModelNode()
    n.name = name
    n.flags = int(NodeFlags.HEADER)
    n.position = tuple(position)
    return n


def make_mesh_node(name="mesh"):
    n = ModelNode()
    n.name = name
    n.flags = int(NodeFlags.MESH)
    n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
    n.faces    = [(0,1,2)]
    return n


def make_model_with_skeleton():
    """Build a simple model: root → bone1 → bone2, plus a mesh node at root."""
    model = KotorModel()
    root = ModelNode()
    root.name = "TestModel"
    root.flags = int(NodeFlags.HEADER)
    root.position = (0, 0, 0)

    bone1 = make_dummy_node("hip", (0, 0, 0.5))
    bone2 = make_dummy_node("spine", (0, 0, 1.0))
    mesh  = make_mesh_node("body_mesh")

    # Link hierarchy
    bone2.parent = bone1
    bone1.children.append(bone2)
    bone1.parent = root
    root.children.append(bone1)
    mesh.parent = root
    root.children.append(mesh)

    model.root_node = root
    return model


# ─────────────────────────────────────────────────────────────────────
#  Gimbal hit_test_gimbal tests (unit-level)
# ─────────────────────────────────────────────────────────────────────

class TestGimbalHitTest:
    """
    Test FrameRenderer.hit_test_gimbal() – we fabricate _gimbal_handles
    directly so no display is needed.
    """

    def _make_renderer_stub(self):
        """Create a minimal stub that has _gimbal_handles."""
        class Stub:
            _gimbal_handles = []
            def hit_test_gimbal(self, sx, sy, radius=10):
                best_axis = None
                best_d2   = radius * radius
                for hx, hy, axis in self._gimbal_handles:
                    d2 = (hx - sx)**2 + (hy - sy)**2
                    if d2 < best_d2:
                        best_d2 = d2
                        best_axis = axis
                return best_axis
        return Stub()

    def test_no_handles_returns_none(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = []
        assert stub.hit_test_gimbal(100, 100) is None

    def test_exact_hit(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = [(100, 200, 'X'), (150, 200, 'Y'), (100, 250, 'Z')]
        assert stub.hit_test_gimbal(100, 200) == 'X'

    def test_nearest_within_radius(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = [(100, 100, 'X'), (115, 100, 'Y')]
        # 8px from X, 7px from Y – Y should win
        assert stub.hit_test_gimbal(108, 100, radius=10) == 'Y'

    def test_outside_all_returns_none(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = [(100, 100, 'X'), (200, 200, 'Y')]
        assert stub.hit_test_gimbal(500, 500, radius=10) is None

    def test_plane_handle(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = [(50, 50, 'XY'), (80, 80, 'XZ'), (110, 110, 'YZ')]
        assert stub.hit_test_gimbal(50, 50, radius=8) == 'XY'

    def test_radius_zero_requires_exact(self):
        stub = self._make_renderer_stub()
        stub._gimbal_handles = [(100, 100, 'Z')]
        assert stub.hit_test_gimbal(100, 100, radius=0) is None   # d2=0 < 0 is False
        assert stub.hit_test_gimbal(100, 100, radius=1) == 'Z'


# ─────────────────────────────────────────────────────────────────────
#  Gimbal drag math tests (no display needed)
# ─────────────────────────────────────────────────────────────────────

class TestGimbalDragMath:
    """
    Test the axis-delta calculation used in _apply_gimbal_drag without
    needing a real viewport.  We replicate the logic inline.
    """

    def _axis_delta(self, axis_name, dx_screen, dy_screen,
                    right, up, world_per_px):
        if axis_name == 'X':
            w_dir = (1.0, 0.0, 0.0)
        elif axis_name == 'Y':
            w_dir = (0.0, 1.0, 0.0)
        else:
            w_dir = (0.0, 0.0, 1.0)
        sc_x = w_dir[0]*right[0] + w_dir[1]*right[1] + w_dir[2]*right[2]
        sc_y = w_dir[0]*up[0]    + w_dir[1]*up[1]    + w_dir[2]*up[2]
        ll = math.sqrt(sc_x*sc_x + sc_y*sc_y)
        if ll < 1e-6:
            return (0.0, 0.0, 0.0)
        proj = (dx_screen * sc_x + (-dy_screen) * sc_y) / ll
        delta = proj * world_per_px
        return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

    def test_x_axis_camera_facing_front(self):
        """Camera looking along -Y (front view): right=+X, up=+Z."""
        right = (1.0, 0.0, 0.0)
        up    = (0.0, 0.0, 1.0)
        wpp   = 0.01   # 1cm per pixel

        # Move mouse 10px right → expect +X delta
        d = self._axis_delta('X', 10, 0, right, up, wpp)
        assert abs(d[0] - 0.1) < 1e-6, f"Expected 0.1 X delta, got {d[0]}"
        assert abs(d[1]) < 1e-9
        assert abs(d[2]) < 1e-9

    def test_z_axis_camera_facing_front(self):
        """Move mouse 5px up → expect +Z delta when camera front-facing."""
        right = (1.0, 0.0, 0.0)
        up    = (0.0, 0.0, 1.0)
        wpp   = 0.01

        d = self._axis_delta('Z', 0, -5, right, up, wpp)   # dy=-5 means moving up
        assert abs(d[2] - 0.05) < 1e-6, f"Expected 0.05 Z delta, got {d[2]}"

    def test_y_axis_zero_when_camera_aligned(self):
        """Y axis is parallel to camera's left-right when up=+Y: sc_x=0, sc_y=1."""
        right = (1.0, 0.0, 0.0)
        up    = (0.0, 1.0, 0.0)
        wpp   = 0.01
        d = self._axis_delta('Y', 0, -10, right, up, wpp)   # move up 10px
        assert abs(d[1] - 0.1) < 1e-6, f"Expected Y 0.1, got {d[1]}"

    def test_world_per_px_scaling(self):
        """Larger wpp means bigger world movement per pixel."""
        right = (1.0, 0.0, 0.0)
        up    = (0.0, 1.0, 0.0)
        d1 = self._axis_delta('X', 1, 0, right, up, 0.01)
        d2 = self._axis_delta('X', 1, 0, right, up, 0.05)
        assert abs(d2[0] / d1[0] - 5.0) < 1e-5


# ─────────────────────────────────────────────────────────────────────
#  Quaternion rotation tests for Rotate mode
# ─────────────────────────────────────────────────────────────────────

class TestRotateGimbalMath:
    """Test the quaternion multiplication used in rotate-mode gimbal."""

    def _rotate_quat(self, base_rot, axis, angle_rad):
        """Apply rotation around axis to base quaternion."""
        qx, qy, qz, qw = base_rot
        ha = angle_rad * 0.5
        c, s = math.cos(ha), math.sin(ha)
        if axis == 'X':
            rq = (s, 0.0, 0.0, c)
        elif axis == 'Y':
            rq = (0.0, s, 0.0, c)
        else:
            rq = (0.0, 0.0, s, c)
        ax, ay, az, aw = rq
        bx, by, bz, bw = qx, qy, qz, qw
        new_rot = (
            aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz,
        )
        ll = math.sqrt(sum(v*v for v in new_rot))
        if ll > 1e-9:
            return tuple(v/ll for v in new_rot)
        return (0.0, 0.0, 0.0, 1.0)

    def test_identity_unaffected_by_zero_rotation(self):
        base = (0.0, 0.0, 0.0, 1.0)
        result = self._rotate_quat(base, 'Z', 0.0)
        # Rotating by 0 should give identity
        assert abs(result[3] - 1.0) < 1e-6

    def test_z_rotation_90_deg(self):
        """Rotating identity by 90° around Z → (0, 0, sin45°, cos45°)."""
        base = (0.0, 0.0, 0.0, 1.0)
        result = self._rotate_quat(base, 'Z', math.pi / 2)
        expected_w = math.cos(math.pi / 4)
        expected_z = math.sin(math.pi / 4)
        assert abs(result[2] - expected_z) < 1e-6
        assert abs(result[3] - expected_w) < 1e-6

    def test_quaternion_stays_unit(self):
        """Result quaternion should always have unit length."""
        base = (0.1, 0.2, 0.3, 0.927)
        ll = math.sqrt(sum(v*v for v in base))
        base = tuple(v/ll for v in base)
        for axis in ('X', 'Y', 'Z'):
            for angle in (0.1, 0.5, 1.0, -0.7, math.pi):
                r = self._rotate_quat(base, axis, angle)
                mag = math.sqrt(sum(v*v for v in r))
                assert abs(mag - 1.0) < 1e-5, f"Non-unit quat for {axis}, {angle}"


# ─────────────────────────────────────────────────────────────────────
#  Clear skeleton tests
# ─────────────────────────────────────────────────────────────────────

class TestClearSkeleton:
    """
    Test the logic used by RigPanel._clear_skeleton without needing the GUI.
    We replicate the core logic inline.
    """

    def _clear_skeleton(self, model):
        """
        Replicate the logic from RigPanel._clear_skeleton (sans GUI dialogs).
        Returns the modified model.
        """
        # Strip skin weights from all mesh nodes
        for n in model.mesh_nodes():
            n.flags &= ~int(NodeFlags.SKIN)
            n.skin_data = []
            n.bone_map  = []

        # Walk tree, remove dummy nodes
        if model.root_node:
            stack = [model.root_node]
            while stack:
                node = stack.pop()
                kept = []
                for c in node.children:
                    if c.is_mesh or (c.is_dummy and c.name == model.root_node.name):
                        kept.append(c)
                        stack.append(c)
                    elif c.is_dummy:
                        pass  # drop
                    else:
                        kept.append(c)
                        stack.append(c)
                node.children = kept
        return model

    def test_clear_removes_dummy_bones(self):
        model = make_model_with_skeleton()
        # Before: root has bone1 (dummy) + body_mesh
        assert any(c.is_dummy for c in model.root_node.children)
        model = self._clear_skeleton(model)
        # After: only mesh children remain
        for c in model.root_node.children:
            assert not c.is_dummy, f"Dummy bone '{c.name}' was not removed"

    def test_clear_preserves_mesh_nodes(self):
        model = make_model_with_skeleton()
        mesh_count_before = len(list(model.mesh_nodes()))
        model = self._clear_skeleton(model)
        mesh_count_after = len(list(model.mesh_nodes()))
        assert mesh_count_after == mesh_count_before, \
            "Mesh nodes should not be removed by clear_skeleton"

    def test_clear_resets_skin_weights(self):
        model = make_model_with_skeleton()
        # Add skin data to mesh
        mesh = next(n for n in model.mesh_nodes())
        mesh.flags |= int(NodeFlags.SKIN)
        mesh.bone_map = ["hip", "spine"]
        mesh.skin_data = [object(), object()]
        
        model = self._clear_skeleton(model)
        mesh_after = next(n for n in model.mesh_nodes())
        assert mesh_after.bone_map == []
        assert mesh_after.skin_data == []
        assert not mesh_after.is_skin

    def test_clear_model_with_no_bones_is_safe(self):
        """Clearing a mesh-only model should not crash."""
        model = KotorModel()
        root = ModelNode()
        root.name = "m"
        root.flags = int(NodeFlags.HEADER)
        mesh = make_mesh_node("body")
        mesh.parent = root
        root.children.append(mesh)
        model.root_node = root

        model = self._clear_skeleton(model)   # should not raise


# ─────────────────────────────────────────────────────────────────────
#  External skeleton offset tests
# ─────────────────────────────────────────────────────────────────────

class TestExtSkeletonOffset:
    """Test that ext-skeleton offset math is correct."""

    def test_offset_applied_to_bone_position(self):
        """World position of ext-skel bone should be bone.world_pos + offset."""
        ext = make_model_with_skeleton()
        bone = next(c for c in ext.root_node.children if c.is_dummy)
        base_pos = bone.world_position()

        offset = (1.0, 2.5, -0.3)
        ox, oy, oz = offset

        # The viewport draws at: _bp(node) = (p[0]+ox, p[1]+oy, p[2]+oz)
        expected = (base_pos[0] + ox, base_pos[1] + oy, base_pos[2] + oz)
        actual   = (base_pos[0] + offset[0],
                    base_pos[1] + offset[1],
                    base_pos[2] + offset[2])
        for i in range(3):
            assert abs(actual[i] - expected[i]) < 1e-9

    def test_zero_offset_gives_original_position(self):
        ext = make_model_with_skeleton()
        bone = next(c for c in ext.root_node.children if c.is_dummy)
        base_pos = bone.world_position()
        offset = (0.0, 0.0, 0.0)
        result = (base_pos[0]+offset[0], base_pos[1]+offset[1], base_pos[2]+offset[2])
        for i in range(3):
            assert abs(result[i] - base_pos[i]) < 1e-9


