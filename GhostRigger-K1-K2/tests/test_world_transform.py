"""
test_world_transform.py — Tests for the world-transform pipeline fixes.

Covers:
  - 180°-rotation fix for non-skin trimesh nodes (Wardroid / c_brith bug)
  - Bone world position accuracy (bone_world_position vs world_position)
  - Normal transform correctness for rotated mesh nodes
  - Selfillum controller application
  - Nested hierarchy correctness after fixes
"""
import math
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    ModelNode, NodeFlags, KotorModel,
    _quat_rotate, _quat_normalize_bind, _quat_normalize, _quat_mul,
)


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────

def _node(name, flags, pos=(0,0,0), rot=(0,0,0,1)):
    n = ModelNode(name=name, flags=flags, position=pos, rotation=rot)
    return n

def _attach(parent, child):
    child.parent = parent
    parent.children.append(child)
    return child

def _approx(a, b, tol=1e-4):
    return all(abs(x-y) < tol for x, y in zip(a, b))


# ─────────────────────────────────────────────────────────────────────
#  Test _quat_normalize (no-collapse version)
# ─────────────────────────────────────────────────────────────────────

class TestQuatNormalize:
    def test_identity_preserved(self):
        result = _quat_normalize((0, 0, 0, 1))
        assert _approx(result, [0, 0, 0, 1])

    def test_180_about_x_preserved(self):
        """_quat_normalize must NOT collapse 180° rotations."""
        result = _quat_normalize((1, 0, 0, 0))
        assert _approx(result, [1, 0, 0, 0])

    def test_180_about_z_preserved(self):
        result = _quat_normalize((0, 0, 1, 0))
        assert _approx(result, [0, 0, 1, 0])

    def test_180_about_y_preserved(self):
        result = _quat_normalize((0, 1, 0, 0))
        assert _approx(result, [0, 1, 0, 0])

    def test_normalizes_unnormalized(self):
        result = _quat_normalize((2, 0, 0, 0))
        assert _approx(result, [1, 0, 0, 0])

    def test_zero_quaternion_returns_identity(self):
        result = _quat_normalize((0, 0, 0, 0))
        assert _approx(result, [0, 0, 0, 1])


# ─────────────────────────────────────────────────────────────────────
#  Test _quat_normalize_bind (collapse-180 version)
# ─────────────────────────────────────────────────────────────────────

class TestQuatNormalizeBind:
    def test_180_about_x_collapsed(self):
        """Only pure X-axis 180° (NWN coord-flip) should be collapsed to identity."""
        result = _quat_normalize_bind((1, 0, 0, 0))
        assert _approx(result, [0, 0, 0, 1])

    def test_180_about_x_neg_collapsed(self):
        """Negative X-axis 180° (NWN coord-flip) should also be collapsed."""
        result = _quat_normalize_bind((-1, 0, 0, 0))
        assert _approx(result, [0, 0, 0, 1])

    def test_180_about_z_PRESERVED(self):
        """
        Z-axis 180° must NOT be collapsed — it is a real limb-mirror rotation
        used in droid/creature models (c_drdassassin, c_warbot, c_brith).
        Previously this was incorrectly collapsed to identity, causing one leg
        to appear rotated 180° in the wrong direction.
        """
        result = _quat_normalize_bind((0, 0, 1, 0))
        # Must NOT be identity — this is a real rotation that must be preserved
        assert not _approx(result, [0, 0, 0, 1]), \
            "Z-axis 180° must be preserved (real limb-mirror rotation, not NWN coord-flip)"
        assert _approx(result, [0, 0, 1, 0], tol=0.01)

    def test_180_about_y_PRESERVED(self):
        """Y-axis 180° must NOT be collapsed — real limb orientation transform."""
        result = _quat_normalize_bind((0, 1, 0, 0))
        assert not _approx(result, [0, 0, 0, 1]), \
            "Y-axis 180° must be preserved (real limb orientation)"
        assert _approx(result, [0, 1, 0, 0], tol=0.01)

    def test_180_diagonal_PRESERVED(self):
        """Diagonal 180° must NOT be collapsed — real geometry transform."""
        import math
        s = math.sqrt(0.5)
        result = _quat_normalize_bind((s, 0, s, 0))
        assert not _approx(result, [0, 0, 0, 1]), \
            "Diagonal 180° must be preserved (real geometry rotation)"

    def test_90_about_x_preserved(self):
        q = (0.707, 0, 0, 0.707)
        result = _quat_normalize_bind(q)
        assert not _approx(result, [0, 0, 0, 1])
        assert _approx(result[:3], [0.707, 0, 0], tol=0.01)

    def test_identity_unchanged(self):
        result = _quat_normalize_bind((0, 0, 0, 1))
        assert _approx(result, [0, 0, 0, 1])


# ─────────────────────────────────────────────────────────────────────
#  Test world_transform — core fix for Wardroid / c_brith
# ─────────────────────────────────────────────────────────────────────

class TestWorldTransformFix:
    """Verify that 180°-rotated non-skin mesh nodes get correct orientation."""

    def test_trimesh_180z_rotation_preserved(self):
        """
        A trimesh node with 180°-about-Z rotation must have that rotation
        reflected in its world_transform() orientation so vertices get flipped.
        Previously _quat_normalize_bind collapsed this to identity.
        """
        panel = _node('panel', NodeFlags.MESH, pos=(0, 0, 0.8),
                       rot=(0, 0, 1, 0))   # 180° about Z
        wp, wo = panel.world_transform()

        # Position should be (0, 0, 0.8)
        assert _approx(wp, (0, 0, 0.8))

        # Orientation should be 180° about Z, NOT identity
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot > 0.9, "180° rotation must NOT be collapsed to identity"

        # Vertex (1, 0, 0) should map to approximately (-1, 0, 0.8) after 180°Z
        v = (1.0, 0.0, 0.0)
        rx, ry, rz = _quat_rotate(wo, v)
        wx, wy, wz = rx + wp[0], ry + wp[1], rz + wp[2]
        assert abs(wx - (-1.0)) < 0.01, f"Expected wx≈-1.0, got {wx}"
        assert abs(wy) < 0.01
        assert abs(wz - 0.8) < 0.01

    def test_trimesh_180y_rotation_preserved(self):
        """180°-about-Y rotation on a trimesh node must be preserved."""
        panel = _node('panel_y', NodeFlags.MESH, pos=(0, 0, 1.0),
                       rot=(0, 1, 0, 0))   # 180° about Y
        wp, wo = panel.world_transform()

        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot > 0.9, "180° Y rotation must NOT be collapsed"

    def test_trimesh_identity_rotation_is_identity(self):
        """A node with identity rotation should produce identity world orient."""
        mesh = _node('mesh', NodeFlags.MESH, pos=(0, 0, 1.5), rot=(0, 0, 0, 1))
        wp, wo = mesh.world_transform()

        assert _approx(wp, (0, 0, 1.5))
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot < 0.001, "Identity rotation should remain identity"

    def test_nwn_root_flip_child_position_unaffected(self):
        """
        The NWN root-node 180°-about-X flip must NOT corrupt child positions.
        This is the original reason for _quat_normalize_bind.
        """
        root = _node('root', NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
        body = _node('body', NodeFlags.MESH, pos=(0,0,0.9), rot=(0,0,0,1))
        _attach(root, body)

        wp, wo = body.world_transform()
        # Body should be at (0, 0, 0.9) — NOT (0, 0, -0.9) which was the bug
        assert _approx(wp, (0, 0, 0.9)), f"Expected (0,0,0.9) got {wp}"

    def test_deep_hierarchy_positions_correct(self):
        """Three-level hierarchy: root→spine→head_mesh, all positions correct."""
        root  = _node('root',  NodeFlags.HEADER, pos=(0,0,0),   rot=(1,0,0,0))
        spine = _node('spine', NodeFlags.HEADER, pos=(0,0,1.0), rot=(0,0,0,1))
        head  = _node('head',  NodeFlags.MESH,   pos=(0,0,0.3), rot=(0,0,0,1))
        _attach(root, spine)
        _attach(spine, head)

        wp, wo = head.world_transform()
        assert _approx(wp, (0, 0, 1.3), tol=0.001)

    def test_world_position_equals_world_transform_position(self):
        """world_position() and world_transform()[0] must agree."""
        root  = _node('root',  NodeFlags.HEADER, pos=(0,0,0),   rot=(1,0,0,0))
        body  = _node('body',  NodeFlags.MESH,   pos=(0.1, 0.2, 0.5), rot=(0,0,1,0))
        _attach(root, body)

        wp1 = body.world_position()
        wp2, _ = body.world_transform()
        assert _approx(wp1, wp2, tol=1e-5)

    def test_skin_node_position_unchanged(self):
        """Skin nodes should produce the same world position as before (no regression)."""
        root = _node('root', NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
        skin = _node('skin', NodeFlags.MESH | NodeFlags.SKIN,
                     pos=(0.0, 0.0, 0.0), rot=(0,0,0,1))
        _attach(root, skin)

        wp, wo = skin.world_transform()
        assert _approx(wp, (0, 0, 0))
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot < 0.001   # skin at root should have identity orientation


# ─────────────────────────────────────────────────────────────────────
#  Test bone_world_position
# ─────────────────────────────────────────────────────────────────────

class TestBoneWorldPosition:
    """Verify bone_world_position uses fully-collapsed chain for pivot placement."""

    def test_simple_chain(self):
        root  = _node('root',  NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
        bone  = _node('bone',  NodeFlags.HEADER, pos=(0,0,1.5), rot=(0,0,1,0))
        _attach(root, bone)

        bwp = bone.bone_world_position()
        assert _approx(bwp, (0, 0, 1.5), tol=0.001)

    def test_bone_world_position_uses_collapse_on_leaf(self):
        """
        bone_world_position() should collapse 180°-rotations even on the leaf,
        giving the same result as if the rotation were identity.
        """
        root = _node('root', NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
        bone = _node('bone', NodeFlags.HEADER, pos=(0,0,1.0), rot=(0,0,1,0))
        _attach(root, bone)

        bwp = bone.bone_world_position()
        # Position should be unaffected by bone's own 180°-Z rotation
        assert _approx(bwp, (0, 0, 1.0), tol=0.001)

    def test_world_position_and_bone_position_agree_for_identity(self):
        """For identity rotations, both methods should agree."""
        root  = _node('root', NodeFlags.HEADER, pos=(0,0,0), rot=(0,0,0,1))
        bone  = _node('bone', NodeFlags.HEADER, pos=(0.5, 0, 1.0), rot=(0,0,0,1))
        _attach(root, bone)

        assert _approx(bone.world_position(), bone.bone_world_position(), tol=1e-5)


# ─────────────────────────────────────────────────────────────────────
#  Test _quat_rotate for vertex transform
# ─────────────────────────────────────────────────────────────────────

class TestQuatRotate:
    def test_180_z_flips_x_and_y(self):
        q = (0, 0, 1, 0)   # 180° about Z
        vx, vy, vz = _quat_rotate(q, (1.0, 0.5, 2.0))
        assert abs(vx - (-1.0)) < 0.01
        assert abs(vy - (-0.5)) < 0.01
        assert abs(vz - 2.0)    < 0.01

    def test_180_y_flips_x_and_z(self):
        q = (0, 1, 0, 0)   # 180° about Y
        vx, vy, vz = _quat_rotate(q, (1.0, 0.5, 2.0))
        assert abs(vx - (-1.0)) < 0.01
        assert abs(vy - 0.5)    < 0.01
        assert abs(vz - (-2.0)) < 0.01

    def test_90_z_rotates_correctly(self):
        s = math.sqrt(0.5)
        q = (0, 0, s, s)   # 90° about Z
        vx, vy, vz = _quat_rotate(q, (1.0, 0.0, 0.0))
        assert abs(vx) < 0.01
        assert abs(vy - 1.0) < 0.01
        assert abs(vz) < 0.01

    def test_identity_quat_unchanged(self):
        q = (0, 0, 0, 1)
        v = (1.5, 2.5, 3.5)
        result = _quat_rotate(q, v)
        assert _approx(result, v)


# ─────────────────────────────────────────────────────────────────────
#  Test _apply_bind_pose_controllers (selfillum)
# ─────────────────────────────────────────────────────────────────────

class TestBindPoseControllers:
    """Verify the MDL parser applies controllers to node fields correctly."""

    def _make_node_with_ctrl(self, ctrl_type, values):
        """Make a mesh node with a controller entry."""
        from core.mdl_parser import MDLBinaryParser
        node = ModelNode(name='test_mesh', flags=int(NodeFlags.MESH))
        node.controllers = [{'type': ctrl_type, 'values': values}]

        model = KotorModel()
        root  = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.children = [node]
        node.parent = root
        model.root_node = root

        MDLBinaryParser._apply_bind_pose_controllers(model)
        return node

    def test_selfillum_applied(self):
        """Controller type 100 should set node.selfillum (CTRL_MESH_SELFILLUMCOLOR=100).

        BUG-FIX v4.4: Corrected from type 132→100 to match KotorBlender types.py
        (CTRL_MESH_SELFILLUMCOLOR = 100, CTRL_MESH_ALPHA = 132).
        """
        node = self._make_node_with_ctrl(100, [[0.8, 0.4, 0.2]])
        assert hasattr(node, 'selfillum')
        assert abs(node.selfillum[0] - 0.8) < 0.001
        assert abs(node.selfillum[1] - 0.4) < 0.001
        assert abs(node.selfillum[2] - 0.2) < 0.001

    def test_alpha_applied(self):
        """Controller type 132 should set node.alpha (CTRL_MESH_ALPHA=132).

        BUG-FIX v4.4: Corrected from type 100→132 to match KotorBlender types.py.
        """
        node = self._make_node_with_ctrl(132, [[0.5]])
        assert hasattr(node, 'alpha')
        assert abs(node.alpha - 0.5) < 0.001

    def test_no_controller_leaves_default(self):
        """Nodes without controllers keep their default selfillum."""
        node = ModelNode(name='bare', flags=int(NodeFlags.MESH))
        model = KotorModel()
        root  = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.children = [node]; node.parent = root
        model.root_node = root
        from core.mdl_parser import MDLBinaryParser
        MDLBinaryParser._apply_bind_pose_controllers(model)
        assert node.selfillum == (0.0, 0.0, 0.0)


# ─────────────────────────────────────────────────────────────────────
#  Wardroid / c_brith simulation
# ─────────────────────────────────────────────────────────────────────

class TestDroidModelSimulation:
    """
    Simulate Wardroid / c_brith model hierarchy and verify correct rendering.

    KotOR droid models (wardroid, c_warbot, c_brith, etc.) have:
      - Root dummy with 180°-about-X NWN coordinate flip
      - Body trimesh nodes at origin with 180°-about-Z (mirrored side panels)
      - Arm trimesh nodes with 180°-about-Y (reversed arm geometry)
      - Leg mesh nodes with various non-identity rotations
    """

    def _build_droid(self):
        root     = _node('Wardroid', NodeFlags.HEADER, pos=(0,0,0), rot=(1,0,0,0))
        body     = _node('body',     NodeFlags.MESH | NodeFlags.SKIN,
                          pos=(0,0,0), rot=(0,0,0,1))
        panel_l  = _node('panel_l',  NodeFlags.MESH,
                          pos=(-0.4,0,0.8), rot=(0,0,1,0))   # 180°Z mirror
        panel_r  = _node('panel_r',  NodeFlags.MESH,
                          pos=( 0.4,0,0.8), rot=(0,0,0,1))   # identity
        arm_l    = _node('arm_l',    NodeFlags.HEADER,
                          pos=(-0.6,0,1.0), rot=(0,0,0,1))
        arm_mesh = _node('arm_mesh', NodeFlags.MESH,
                          pos=(0,0,-0.3),   rot=(0,1,0,0))   # 180°Y
        head     = _node('head',     NodeFlags.HEADER,
                          pos=(0,0,1.5),    rot=(0,0,0,1))
        eye      = _node('eye_mesh', NodeFlags.MESH,
                          pos=(0,0.1,0.1),  rot=(0,0,0,1))
        _attach(root, body); _attach(root, panel_l); _attach(root, panel_r)
        _attach(root, arm_l); _attach(arm_l, arm_mesh)
        _attach(root, head); _attach(head, eye)
        return root, {
            'root': root, 'body': body, 'panel_l': panel_l,
            'panel_r': panel_r, 'arm_l': arm_l, 'arm_mesh': arm_mesh,
            'head': head, 'eye': eye
        }

    def test_body_at_origin(self):
        _, nodes = self._build_droid()
        wp, _ = nodes['body'].world_transform()
        assert _approx(wp, (0, 0, 0), tol=0.001)

    def test_panel_l_position(self):
        _, nodes = self._build_droid()
        wp, wo = nodes['panel_l'].world_transform()
        assert _approx(wp, (-0.4, 0, 0.8), tol=0.001)
        # Must have 180° rotation preserved
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot > 0.9, "panel_l 180°Z rotation must be preserved"

    def test_panel_r_no_rotation(self):
        _, nodes = self._build_droid()
        wp, wo = nodes['panel_r'].world_transform()
        assert _approx(wp, (0.4, 0, 0.8), tol=0.001)
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot < 0.001, "panel_r identity rotation must stay identity"

    def test_arm_mesh_position(self):
        _, nodes = self._build_droid()
        wp, wo = nodes['arm_mesh'].world_transform()
        assert _approx(wp, (-0.6, 0, 0.7), tol=0.001)
        # 180°Y rotation must be preserved on arm_mesh
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot > 0.9, "arm_mesh 180°Y rotation must be preserved"

    def test_eye_position_deep_hierarchy(self):
        _, nodes = self._build_droid()
        wp, _ = nodes['eye'].world_transform()
        assert _approx(wp, (0, 0.1, 1.6), tol=0.001)

    def test_bone_world_position_correct(self):
        _, nodes = self._build_droid()
        # Bone pivot positions should match expected coordinates
        assert _approx(nodes['arm_l'].bone_world_position(), (-0.6, 0, 1.0), tol=0.001)
        assert _approx(nodes['head'].bone_world_position(),  (0, 0, 1.5), tol=0.001)

    def test_panel_l_vertex_flipped(self):
        """Left panel with 180°Z: vertex at (0.1, 0, 0) should map to (-0.1, 0, 0.8)."""
        _, nodes = self._build_droid()
        wp, wo = nodes['panel_l'].world_transform()
        v = (0.1, 0.0, 0.0)
        wo_rot = math.sqrt(sum(x*x for x in wo[:3]))
        if wo_rot > 0.001:
            rx, ry, rz = _quat_rotate(wo, v)
            wv = (rx + wp[0], ry + wp[1], rz + wp[2])
        else:
            wv = (v[0]+wp[0], v[1]+wp[1], v[2]+wp[2])
        assert abs(wv[0] - (-0.4 + (-0.1))) < 0.01, f"Expected x≈-0.5, got {wv[0]}"
        assert abs(wv[2] - 0.8) < 0.01


# ─────────────────────────────────────────────────────────────────────
#  c_drdassassin specific tests (leg mirroring fix)
# ─────────────────────────────────────────────────────────────────────

class TestDrdAssassinLegMirror:
    """
    Tests for the c_drdassassin 'one leg forward, one leg 180° rotated' fix.

    Root cause: _quat_normalize_bind was collapsing ALL 180° rotations including
    Y and Z axis ones, which are REAL geometry transforms used for droid leg mirroring.
    The right thigh joint (rthigh) uses a Z-axis 180° rotation to mirror the left leg
    geometry.  When this was collapsed to identity, child node positions were computed
    without the mirror rotation, causing the leg to appear in the wrong orientation.
    
    Fix: Only collapse pure X-axis 180° (NWN coord-flip).
    """

    def _build_assassin_legs(self):
        """Build a simplified c_drdassassin-style leg hierarchy."""
        # root: NWN X-axis coord flip
        root  = _node('root',   NodeFlags.HEADER, pos=(0,0,0),       rot=(1,0,0,0))
        hip   = _node('hip',    NodeFlags.HEADER, pos=(0,0,0.5),     rot=(0,0,0,1))

        # Left leg: no mirroring (identity rotation on thigh joint)
        lthigh = _node('lthigh', NodeFlags.HEADER, pos=(-0.15,0,0.6), rot=(0,0,0,1))
        lcalf  = _node('lcalf',  NodeFlags.MESH,   pos=(0,0,-0.45),   rot=(0,0,0,1))
        lfoot  = _node('lfoot',  NodeFlags.MESH,   pos=(0.05,0,-0.4), rot=(0,0,0,1))

        # Right leg: 180°Z mirror on thigh joint (to reuse same geometry as left leg)
        rthigh = _node('rthigh', NodeFlags.HEADER, pos=(0.15,0,0.6),  rot=(0,0,1,0))  # 180°Z!
        rcalf  = _node('rcalf',  NodeFlags.MESH,   pos=(0,0,-0.45),   rot=(0,0,0,1))
        rfoot  = _node('rfoot',  NodeFlags.MESH,   pos=(0.05,0,-0.4), rot=(0,0,0,1))

        _attach(root, hip)
        _attach(hip, lthigh); _attach(lthigh, lcalf); _attach(lcalf, lfoot)
        _attach(hip, rthigh); _attach(rthigh, rcalf); _attach(rthigh, rfoot)
        return {
            'root': root, 'hip': hip,
            'lthigh': lthigh, 'lcalf': lcalf, 'lfoot': lfoot,
            'rthigh': rthigh, 'rcalf': rcalf, 'rfoot': rfoot,
        }

    def test_lthigh_position(self):
        """Left thigh should be at (-0.15, 0, 1.1) — hip.z + lthigh.z."""
        nodes = self._build_assassin_legs()
        wp, _ = nodes['lthigh'].world_transform()
        assert _approx(wp, (-0.15, 0, 1.1), tol=0.001), \
            f"lthigh expected (-0.15,0,1.1), got {wp}"

    def test_rthigh_position(self):
        """Right thigh should be at (0.15, 0, 1.1) — symmetric with left."""
        nodes = self._build_assassin_legs()
        wp, _ = nodes['rthigh'].world_transform()
        assert _approx(wp, (0.15, 0, 1.1), tol=0.001), \
            f"rthigh expected (0.15,0,1.1), got {wp}"

    def test_lcalf_position(self):
        """Left calf should be directly below lthigh."""
        nodes = self._build_assassin_legs()
        wp, _ = nodes['lcalf'].world_transform()
        assert _approx(wp, (-0.15, 0, 0.65), tol=0.001), \
            f"lcalf expected (-0.15,0,0.65), got {wp}"

    def test_rcalf_position_with_mirror(self):
        """
        Right calf: rthigh has 180°Z rotation.  rcalf local pos (0,0,-0.45) has
        only a Z component, so 180°Z doesn't change its relative position.
        rcalf world pos should be (0.15, 0, 0.65) — symmetric with lcalf.
        """
        nodes = self._build_assassin_legs()
        wp, _ = nodes['rcalf'].world_transform()
        assert _approx(wp, (0.15, 0, 0.65), tol=0.001), \
            f"rcalf expected (0.15,0,0.65), got {wp}"

    def test_rfoot_x_offset_mirrored_correctly(self):
        """
        Right foot: rfoot local pos is (0.05, 0, -0.4) relative to rthigh.
        With rthigh's 180°Z rotation, the +0.05 X offset should become -0.05
        in the rthigh's coordinate frame.
        So rfoot world X = rthigh.x + (-0.05) = 0.15 + (-0.05) = 0.10
        
        Old (broken) behavior: rthigh 180°Z was collapsed → rfoot X = 0.15+0.05 = 0.20
        Fixed behavior: 180°Z preserved → rfoot X = 0.15+(-0.05) = 0.10
        """
        nodes = self._build_assassin_legs()
        wp, _ = nodes['rfoot'].world_transform()
        # rfoot world X should be 0.10 (mirrored), NOT 0.20 (un-mirrored)
        assert abs(wp[0] - 0.10) < 0.01, \
            f"rfoot X expected 0.10 (mirrored), got {wp[0]:.4f}. " \
            f"Old broken value was 0.20. This is the c_drdassassin leg flip fix."

    def test_lfoot_x_offset_not_mirrored(self):
        """Left foot has no mirroring — X stays positive as expected."""
        nodes = self._build_assassin_legs()
        wp, _ = nodes['lfoot'].world_transform()
        # lfoot world X = lthigh.x + 0.05 = -0.15 + 0.05 = -0.10
        assert abs(wp[0] - (-0.10)) < 0.01, \
            f"lfoot X expected -0.10, got {wp[0]:.4f}"

    def test_legs_symmetric_about_z_axis(self):
        """
        Left and right leg should be symmetric (mirrored about YZ plane).
        With the fix, lfoot.x ≈ -rfoot.x and lcalf.x ≈ -rcalf.x.
        Note: lfoot and rfoot have different Z heights because lfoot is under lcalf,
        but rfoot is directly under rthigh (different hierarchy depth in test model).
        We just check X symmetry and Y equality here.
        """
        nodes = self._build_assassin_legs()
        lf_wp, _ = nodes['lfoot'].world_transform()
        rf_wp, _ = nodes['rfoot'].world_transform()
        lc_wp, _ = nodes['lcalf'].world_transform()
        rc_wp, _ = nodes['rcalf'].world_transform()
        # Symmetric X (mirror): lfoot.x ≈ -rfoot.x
        assert abs(lf_wp[0] + rf_wp[0]) < 0.01, \
            f"Legs not symmetric: lfoot.x={lf_wp[0]:.3f}, rfoot.x={rf_wp[0]:.3f}"
        # Symmetric Y
        assert abs(lf_wp[1] - rf_wp[1]) < 0.01
        # lcalf and rcalf should be symmetric too
        assert abs(lc_wp[0] + rc_wp[0]) < 0.01, \
            f"Calves not symmetric: lcalf.x={lc_wp[0]:.3f}, rcalf.x={rc_wp[0]:.3f}"

    def test_rthigh_rotation_preserved_for_vertex_transform(self):
        """
        rthigh's 180°Z rotation must be preserved as the leaf's world orientation
        so vertex positions are correctly mirrored when rendering rthigh's mesh.
        """
        nodes = self._build_assassin_legs()
        _, wo = nodes['rthigh'].world_transform()
        wo_rot = math.sqrt(sum(v*v for v in wo[:3]))
        assert wo_rot > 0.9, \
            f"rthigh 180°Z rotation must be preserved for vertex transform, wo={wo}"
