"""
v6.1 Skin Junction & Accessory Model Tests
==========================================
Covers the two key fixes in _get_world_verts_for_node:

  FIX-SKIN-NODEROT:  Standalone skin nodes with a non-identity LOCAL rotation
      have that rotation applied to their vertices.  The node's POSITION is
      never added (it is the animation bone pivot, not a mesh origin).
      Evidence: c_terantanak Torso/feet/Tail carry a ~180° Z rotation; without
      it the shoulder seam has a Y-sign flip (junction gap = 0), after the fix
      the Y ranges overlap by ~0.51 units (fully connected).

  FIX-ACCESSORY-SKIN:  Accessory models (non-base-supermodel) have skin
      vertices in bone-local space; the full world transform is applied.

  FIX-BANTHA-NOWP:  Standalone models with identity skin-node rotation AND a
      non-zero node position must NOT add that position to the vertices.
      The position is the bone's world pivot for LBS, not a mesh offset.
      Evidence: c_bantha btBody_front pos=(0,-1.163,1.469); adding it would
      shift the already-world-space body verts by -1.163 in Y, breaking
      front/back junction.
"""
import math
import pytest
from src.core.model_data import KotorModel, ModelNode, NodeFlags
from src.gui.viewport import FrameRenderer, ArcBallCamera


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _quat_from_axis_angle(ax, ay, az, deg):
    """Build a quaternion (x,y,z,w) for an axis-angle rotation."""
    rad = math.radians(deg) / 2
    s = math.sin(rad)
    l = math.sqrt(ax*ax + ay*ay + az*az) or 1.0
    return (ax/l*s, ay/l*s, az/l*s, math.cos(rad))


def _make_renderer_for(model: KotorModel) -> FrameRenderer:
    cam = ArcBallCamera()
    r = FrameRenderer(cam)
    r.set_model(model)
    r._anim_pose = None  # bind pose
    return r


def _make_standalone(supermodel='NULL'):
    """Build a minimal standalone model with one skin node."""
    root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
    root.position = (0, 0, 0)
    root.rotation = (0, 0, 0, 1)
    model = KotorModel(name='test', root_node=root)
    model.supermodel = supermodel
    # NOTE: model.nodes is a property (read-only) derived from root_node tree.
    # Nodes are attached by setting parent.children.append(node) in _add_skin_node.
    model.compute_bounds()
    return model, root


def _add_skin_node(parent, model, name, verts, rotation=(0, 0, 0, 1),
                   position=(0, 0, 0)):
    node = ModelNode(name=name,
                     flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    node.position = position
    node.rotation = rotation
    node.parent = parent
    node.vertices = list(verts)
    node.uvs = [(0.5, 0.5)] * len(verts)
    node.texture = 'dummy'
    parent.children.append(node)
    # NOTE: model.nodes is a computed property; attaching to parent tree is enough.
    return node


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-SKIN-NODEROT: 180° Z rotation applied to standalone skin nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinNodeRotFix:
    """Standalone skin nodes carry only the node's LOCAL rotation — no position."""

    def _renderer_with_skin(self, rotation, position=(0, 0, 0)):
        model, root = _make_standalone('NULL')
        verts = [(1.0, 0.5, 1.5), (1.2, 0.3, 1.2), (0.9, 0.8, 1.8)]
        node = _add_skin_node(root, model, 'Torso', verts,
                              rotation=rotation, position=position)
        model.compute_bounds()
        return _make_renderer_for(model), node, verts

    # ── 180° Z rotation (c_terantanak Torso/feet/Tail case) ──────────────────

    def test_180z_rotation_applied_to_verts(self):
        """180° Z rotation flips X and Y signs: (1,0.5,z) → (-1,-0.5,z)."""
        rot = _quat_from_axis_angle(0, 0, 1, 180)   # ~(0,0,1,0) normalised
        r, node, orig = self._renderer_with_skin(rot)
        world = r._get_world_verts_for_node(node)
        assert len(world) == len(orig)
        # After 180° Z: x→-x, y→-y, z stays
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - (-ov[0])) < 1e-4, f"X: expected {-ov[0]:.3f}, got {wv[0]:.3f}"
            assert abs(wv[1] - (-ov[1])) < 1e-4, f"Y: expected {-ov[1]:.3f}, got {wv[1]:.3f}"
            assert abs(wv[2] - ov[2]) < 1e-4, f"Z: expected {ov[2]:.3f}, got {wv[2]:.3f}"

    def test_180z_rotation_position_NOT_added(self):
        """Node position is NEVER added to standalone skin verts (bone pivot only)."""
        rot = _quat_from_axis_angle(0, 0, 1, 180)
        # Give the node a large position that would visibly displace verts if added
        r, node, orig = self._renderer_with_skin(rot, position=(0, 0, 100.0))
        world = r._get_world_verts_for_node(node)
        # Z must be unaffected by position (100.0 NOT added)
        for wv, ov in zip(world, orig):
            assert abs(wv[2] - ov[2]) < 1e-4, \
                f"Z: rotation-only expected {ov[2]:.3f}, got {wv[2]:.3f} (position was illegally added)"

    # ── Identity rotation (RArm / LArm case, most creature nodes) ────────────

    def test_identity_rotation_verts_unchanged(self):
        """Identity rotation → vertices returned exactly as stored."""
        r, node, orig = self._renderer_with_skin((0, 0, 0, 1))
        world = r._get_world_verts_for_node(node)
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - ov[0]) < 1e-6
            assert abs(wv[1] - ov[1]) < 1e-6
            assert abs(wv[2] - ov[2]) < 1e-6

    def test_identity_rotation_large_position_NOT_added(self):
        """Large bone pivot on identity-rotation skin node must NOT shift verts."""
        r, node, orig = self._renderer_with_skin((0, 0, 0, 1), position=(0, -1.163, 1.469))
        world = r._get_world_verts_for_node(node)
        # c_bantha style: verts stay at their stored positions
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - ov[0]) < 1e-6
            assert abs(wv[1] - ov[1]) < 1e-6, \
                f"Y: expected {ov[1]:.3f} unchanged, got {wv[1]:.3f} (position was illegally added)"
            assert abs(wv[2] - ov[2]) < 1e-6

    # ── 90° Y rotation ────────────────────────────────────────────────────────

    def test_90y_rotation_applied(self):
        """90° Y rotation: (1,0,0) → (0,0,-1), (0,0,1) → (1,0,0)."""
        rot = _quat_from_axis_angle(0, 1, 0, 90)
        model, root = _make_standalone('NULL')
        verts = [(1.0, 0.0, 0.0)]
        node = _add_skin_node(root, model, 'arm', verts, rotation=rot)
        model.compute_bounds()
        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(node)
        # 90° Y: (1,0,0) → (0,0,-1)
        assert abs(world[0][0] - 0.0) < 1e-4
        assert abs(world[0][1] - 0.0) < 1e-4
        assert abs(world[0][2] - (-1.0)) < 1e-4


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-BANTHA-NOWP: Standalone model with large non-zero bone position
# ─────────────────────────────────────────────────────────────────────────────

class TestBanthaBodyJunction:
    """c_bantha skin nodes have large wp_mag (≈1.87) but identity rotation.
    Vertices are in model/world space — the position must NOT be added.

    Bantha geometry: front body Y=[1.12, 3.39], back body Y=[-2.85, 1.20].
    They share junction at Y≈1.12.  If wp_Y=-1.163 were added to front body
    the new Y_max would be ≈2.23 and junction would shift, breaking the model.
    """

    def _bantha_body_front_renderer(self):
        """Simulate btBody_front: position=(0,-1.163,1.469), identity rotation."""
        model, root = _make_standalone('NULL')
        # Representative verts in the junction region (Y ≈ 1.12 to 3.39)
        verts = [(0.0, 1.12, 0.0), (0.0, 2.28, 0.5), (0.0, 3.39, 1.0)]
        node = _add_skin_node(root, model, 'btBody_front', verts,
                              rotation=(0, 0, 0, 1),
                              position=(0.0, -1.163, 1.469))
        model.compute_bounds()
        return _make_renderer_for(model), node, verts

    def test_front_body_verts_unchanged(self):
        """btBody_front verts must remain at stored Y positions (no wp offset)."""
        r, node, orig = self._bantha_body_front_renderer()
        world = r._get_world_verts_for_node(node)
        for wv, ov in zip(world, orig):
            assert abs(wv[1] - ov[1]) < 1e-6, \
                f"Y: expected {ov[1]:.3f}, got {wv[1]:.3f} (wp_Y=-1.163 was illegally added)"

    def test_front_back_junction_preserved(self):
        """Front body Y_min(1.12) and back body Y_max(1.20) must overlap."""
        model, root = _make_standalone('NULL')
        front_verts = [(0.0, 1.12, 0.0), (0.0, 2.28, 0.5), (0.0, 3.39, 1.0)]
        back_verts  = [(0.0, -2.85, 0.0), (0.0, 0.06, 0.3), (0.0, 1.20, 0.5)]
        # Both have the same bone position as real bantha
        bp = (0.0, -1.163, 1.469)
        front = _add_skin_node(root, model, 'btBody_front', front_verts,
                               rotation=(0,0,0,1), position=bp)
        back  = _add_skin_node(root, model, 'btBodyback',  back_verts,
                               rotation=(0,0,0,1), position=bp)
        model.compute_bounds()
        r = _make_renderer_for(model)

        wf = r._get_world_verts_for_node(front)
        wb = r._get_world_verts_for_node(back)

        front_ymin = min(v[1] for v in wf)
        back_ymax  = max(v[1] for v in wb)

        # Junction: back body Y_max ≥ front body Y_min means they meet/overlap
        gap = front_ymin - back_ymax
        assert gap <= 0.15, \
            f"Front/back body junction gap = {gap:.3f}; expected ≤ 0.15 (bodies connected)"

    def test_large_wp_mag_standalone_not_applied(self):
        """wp_mag = 1.87 on a NULL-supermodel skin must not be added to verts."""
        model, root = _make_standalone('NULL')
        verts = [(0.0, 0.0, 0.5)]
        node = _add_skin_node(root, model, 'body', verts,
                              rotation=(0,0,0,1),
                              position=(0.0, -1.163, 1.469))  # wp_mag≈1.87
        model.compute_bounds()
        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(node)
        assert abs(world[0][1] - 0.0) < 1e-6, \
            f"Y must be 0.0 (unchanged), got {world[0][1]:.3f} (wp added illegally)"
        assert abs(world[0][2] - 0.5) < 1e-6, \
            f"Z must be 0.5 (unchanged), got {world[0][2]:.3f} (wp added illegally)"


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-ACCESSORY-SKIN: Accessory models apply full world transform
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessorySkinTransform:
    """n_admrlsaulkar / comm_b_f style: supermodel is a known NPC base skeleton.
    Skin vertices are in bone-local space → full world transform is applied.
    """

    _ACCESSORY_SUPERMODELS = ['N_AdmrlSaulKar', 'S_Female02', 'S_Male02',
                               'comm_b_f', 'S_Female03']

    def _make_accessory(self, supermodel):
        model, root = _make_standalone(supermodel)
        verts = [(0.5, 0.0, 0.0)]
        node = _add_skin_node(root, model, 'head', verts,
                              rotation=(0, 0, 0, 1),
                              position=(0.0, 0.0, 1.5))
        model.compute_bounds()
        return _make_renderer_for(model), node

    def test_accessory_skin_wp_applied(self):
        """Accessory skin with position z=1.5: world vert z = vert_z + 1.5."""
        r, node = self._make_accessory('N_AdmrlSaulKar')
        world = r._get_world_verts_for_node(node)
        # Vertex (0.5, 0.0, 0.0) + wp (0.0, 0.0, 1.5) = (0.5, 0.0, 1.5)
        assert abs(world[0][2] - 1.5) < 1e-4, \
            f"Accessory skin z: expected 1.5, got {world[0][2]:.3f}"

    def test_accessory_vs_standalone_different(self):
        """Accessory and standalone models handle the same wp differently."""
        # Standalone: verts unchanged
        model_s, root_s = _make_standalone('NULL')
        verts = [(0.5, 0.0, 0.0)]
        node_s = _add_skin_node(root_s, model_s, 'head', verts,
                                rotation=(0,0,0,1), position=(0,0,1.5))
        model_s.compute_bounds()
        r_s = _make_renderer_for(model_s)
        world_s = r_s._get_world_verts_for_node(node_s)

        # Accessory: wp IS added
        model_a, root_a = _make_standalone('N_AdmrlSaulKar')
        node_a = _add_skin_node(root_a, model_a, 'head', verts,
                                rotation=(0,0,0,1), position=(0,0,1.5))
        model_a.compute_bounds()
        r_a = _make_renderer_for(model_a)
        world_a = r_a._get_world_verts_for_node(node_a)

        # Standalone: z=0.0 (unchanged); Accessory: z=1.5 (wp added)
        assert abs(world_s[0][2] - 0.0) < 1e-4, \
            f"Standalone skin z must be 0.0 (unchanged), got {world_s[0][2]:.3f}"
        assert abs(world_a[0][2] - 1.5) < 1e-4, \
            f"Accessory skin z must be 1.5 (wp added), got {world_a[0][2]:.3f}"

    def test_base_skeleton_supermodel_treated_as_standalone(self):
        """Supermodel = 'S_Female02' is a base skeleton → standalone treatment.

        'S_Female02' and 'S_Male02' are base skeletons (in KOTOR_BASE_SKELETONS);
        these are the PC/NPC body skeletons that themselves carry skin geometry.
        A model reporting S_Female02 as its supermodel is e.g. s_female03 (body),
        which has standalone skin verts, not accessory bone-local verts.
        'S_Female01' is NOT in the list (it is the supermodel OF S_Female02).
        """
        model, root = _make_standalone('S_Female02')  # IS in KOTOR_BASE_SKELETONS
        verts = [(0.0, 0.0, 0.5)]
        node = _add_skin_node(root, model, 'body', verts,
                              rotation=(0,0,0,1), position=(0,0,1.5))
        model.compute_bounds()
        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(node)
        # S_Female02 is a base skeleton → standalone → z unchanged
        assert abs(world[0][2] - 0.5) < 1e-4, \
            f"Base skeleton (S_Female02) must use standalone treatment; z={world[0][2]:.3f}"


# ─────────────────────────────────────────────────────────────────────────────
#  C_terantanak arm-torso junction (geometric proof)
# ─────────────────────────────────────────────────────────────────────────────

class TestTerantanakJunction:
    """Verify that applying 180° Z rotation to Torso connects it to RArm.

    Real data from the binary model (see earlier vertex-range analysis):
      RArm inner (X<1.6):  Y=[0.249, 0.759]
      Torso raw shoulder:  Y=[-0.882, -0.249]  (Y sign-flipped without fix)
      Torso after 180° Z:  Y=[+0.249, +0.882]  (connected to RArm)
    """

    def _make_terantanak_style(self):
        """Simplified c_terantanak: Torso with 180°Z + RArm with identity rot."""
        model, root = _make_standalone('NULL')
        rot_180z = _quat_from_axis_angle(0, 0, 1, 180)

        # Torso shoulder verts: Y is negative WITHOUT fix (Y-flip from 180°Z)
        torso_raw_y = [-0.882, -0.600, -0.400, -0.249]
        torso_verts = [(1.5, y, 1.5) for y in torso_raw_y]  # shoulder region
        torso = _add_skin_node(root, model, 'Torso', torso_verts,
                               rotation=rot_180z, position=(0,0,0))

        # RArm inner verts: Y positive, connecting to torso after rotation
        rarm_y = [0.249, 0.400, 0.600, 0.759]
        rarm_verts = [(1.5, y, 1.5) for y in rarm_y]
        rarm = _add_skin_node(root, model, 'RArm', rarm_verts,
                              rotation=(0,0,0,1), position=(0,0,0))

        model.compute_bounds()
        return _make_renderer_for(model), torso, rarm

    def test_torso_y_before_fix_is_negative(self):
        """Without rotation, Torso shoulder Y is negative (disconnected from RArm)."""
        _, torso, _ = self._make_terantanak_style()
        raw_y = [v[1] for v in torso.vertices]
        assert max(raw_y) < 0, \
            f"Raw torso Y must be negative before rotation fix; max={max(raw_y):.3f}"

    def test_torso_y_after_fix_is_positive(self):
        """After 180°Z rotation, Torso shoulder Y becomes positive → connects to RArm."""
        r, torso, rarm = self._make_terantanak_style()
        torso_world = r._get_world_verts_for_node(torso)
        torso_y = [v[1] for v in torso_world]
        assert min(torso_y) > 0, \
            f"After 180°Z fix, Torso shoulder Y must be positive; min={min(torso_y):.3f}"

    def test_arm_torso_junction_overlaps_after_fix(self):
        """After fix, Torso Y range and RArm Y range overlap (junction connected)."""
        r, torso, rarm = self._make_terantanak_style()
        torso_world = r._get_world_verts_for_node(torso)
        rarm_world  = r._get_world_verts_for_node(rarm)

        torso_ymin = min(v[1] for v in torso_world)
        torso_ymax = max(v[1] for v in torso_world)
        rarm_ymin  = min(v[1] for v in rarm_world)
        rarm_ymax  = max(v[1] for v in rarm_world)

        overlap = min(torso_ymax, rarm_ymax) - max(torso_ymin, rarm_ymin)
        assert overlap > 0, \
            f"Junction gap={-overlap:.3f}: Torso Y=[{torso_ymin:.3f},{torso_ymax:.3f}], " \
            f"RArm Y=[{rarm_ymin:.3f},{rarm_ymax:.3f}] — arms NOT connected after fix"

    def test_arm_torso_junction_gap_without_fix_is_negative(self):
        """Verify that WITHOUT the rotation fix the junction would be disconnected."""
        model, root = _make_standalone('NULL')
        rot_180z = _quat_from_axis_angle(0, 0, 1, 180)

        torso_raw_y = [-0.882, -0.600, -0.400, -0.249]
        rarm_y      = [0.249, 0.400, 0.600, 0.759]

        # RAW (no rotation applied): torso Y stays negative
        torso_ymax_raw = max(torso_raw_y)   # -0.249
        rarm_ymin_raw  = min(rarm_y)        # +0.249
        gap_without_fix = rarm_ymin_raw - torso_ymax_raw  # 0.498
        assert gap_without_fix > 0.4, \
            f"Without fix, gap should be large (≈0.498); got {gap_without_fix:.3f}"


# ─────────────────────────────────────────────────────────────────────────────
#  Non-skin (trimesh) nodes must still get their world transform
# ─────────────────────────────────────────────────────────────────────────────

class TestNonSkinWorldTransformPreserved:
    """Non-skin trimesh nodes are stored in node-local space and must
    always receive the full parent-chain world transform."""

    def test_trimesh_child_offset_is_applied(self):
        """Trimesh at position (5,0,0): vertex (0,0,0) → world (5,0,0)."""
        model, root = _make_standalone('NULL')
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH))
        mesh.parent = root
        mesh.position = (5.0, 0.0, 0.0)
        mesh.rotation = (0, 0, 0, 1)
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        mesh.uvs = [(0.5, 0.5)] * 2
        root.children.append(mesh)
        model.compute_bounds()

        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(mesh)
        assert abs(world[0][0] - 5.0) < 1e-5, \
            f"Non-skin vertex (0,0,0) at pos (5,0,0) → world x should be 5.0, got {world[0][0]}"
        assert abs(world[1][0] - 6.0) < 1e-5

    def test_skin_flag_removes_transform_for_standalone(self):
        """Same geometry as above but with SKIN flag: vertex NOT translated."""
        model, root = _make_standalone('NULL')
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        mesh.parent = root
        mesh.position = (5.0, 0.0, 0.0)
        mesh.rotation = (0, 0, 0, 1)
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        mesh.uvs = [(0.5, 0.5)] * 2
        root.children.append(mesh)
        model.compute_bounds()

        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(mesh)
        # SKIN + standalone: verts returned as-is
        assert abs(world[0][0] - 0.0) < 1e-5, \
            f"Standalone SKIN vertex should be unchanged (0.0), got {world[0][0]}"
        assert abs(world[1][0] - 1.0) < 1e-5
