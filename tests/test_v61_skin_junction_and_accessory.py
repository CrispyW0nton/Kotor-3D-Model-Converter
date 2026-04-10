"""
v6.1 Skin Junction & Accessory Model Tests
==========================================
Phase 17 UPDATE: All KotOR MDL vertices (skin AND non-skin) are stored in
NODE-LOCAL space and require the full world transform to be applied.

Previous incorrect assumption:
  "Standalone skin nodes: vertices in world space → return as-is"

Correct behavior (Phase 17, verified by KotorBlender + PyKotor + binary analysis):
  ALL nodes → apply full world transform (translate by wp + rotate by wo).
  No special-casing for standalone vs. accessory or skin vs. non-skin.

  Key evidence (c_bantha):
    btBody_front local verts Y=[1.117,3.391], world pivot Y=-1.163
    Correct world Y = [-0.046, 2.228] (body covers torso/back, anatomy correct)
    Old "as-is" gave Y=[1.117,3.391] (body floating in front of head)

  KotorBlender (base.py): obj.location = self.position (LOCAL), verts uploaded raw,
    Blender scene graph applies parent-chain transform automatically.
  PyKotor: vertex_positions read raw, no world-space pre-baking.
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
    return node


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 17: Skin node rotation + translation both applied
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinNodeRotFix:
    """All skin nodes: full world transform (rotation + translation) always applied."""

    def _renderer_with_skin(self, rotation, position=(0, 0, 0)):
        model, root = _make_standalone('NULL')
        verts = [(1.0, 0.5, 1.5), (1.2, 0.3, 1.2), (0.9, 0.8, 1.8)]
        node = _add_skin_node(root, model, 'Torso', verts,
                              rotation=rotation, position=position)
        model.compute_bounds()
        return _make_renderer_for(model), node, verts

    # ── 180° Z rotation (c_terantanak Torso/feet/Tail case) ──────────────────

    def test_180z_rotation_applied_to_verts(self):
        """180° Z rotation flips X and Y signs: (1,0.5,z) → (-1,-0.5,z).
        
        Phase 17: node at position=(0,0,0) so no additional translation.
        """
        rot = _quat_from_axis_angle(0, 0, 1, 180)   # ~(0,0,1,0) normalised
        r, node, orig = self._renderer_with_skin(rot)
        world = r._get_world_verts_for_node(node)
        assert len(world) == len(orig)
        # After 180° Z: x→-x, y→-y, z stays (plus no translation since pos=(0,0,0))
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - (-ov[0])) < 1e-4, f"X: expected {-ov[0]:.3f}, got {wv[0]:.3f}"
            assert abs(wv[1] - (-ov[1])) < 1e-4, f"Y: expected {-ov[1]:.3f}, got {wv[1]:.3f}"
            assert abs(wv[2] - ov[2]) < 1e-4, f"Z: expected {ov[2]:.3f}, got {wv[2]:.3f}"

    def test_180z_rotation_with_position_full_transform(self):
        """Phase 17: 180°Z + position=(0,0,100.0) → rotation applied AND z+100 added.

        Vertex z should be ov[2] + 100.0 (not just ov[2]).
        """
        rot = _quat_from_axis_angle(0, 0, 1, 180)
        r, node, orig = self._renderer_with_skin(rot, position=(0, 0, 100.0))
        world = r._get_world_verts_for_node(node)
        # Full transform: rotate (x,y,z)→(-x,-y,z), then add wp=(0,0,100)
        for wv, ov in zip(world, orig):
            assert abs(wv[2] - (ov[2] + 100.0)) < 1e-4, \
                f"Z: expected {ov[2]+100.0:.3f} (rot+translate), got {wv[2]:.3f}"

    # ── Identity rotation (RArm / LArm case, most creature nodes) ────────────

    def test_identity_rotation_zero_position_unchanged(self):
        """Identity rotation + position=(0,0,0): world = identity → verts unchanged."""
        r, node, orig = self._renderer_with_skin((0, 0, 0, 1))
        world = r._get_world_verts_for_node(node)
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - ov[0]) < 1e-6
            assert abs(wv[1] - ov[1]) < 1e-6
            assert abs(wv[2] - ov[2]) < 1e-6

    def test_identity_rotation_large_position_applied(self):
        """Phase 17: identity-rotation skin node with large position → position IS added.

        c_bantha style: btBody_front pos=(0,-1.163,1.469).
        local vert (1.0, 0.5, 1.5) → world (1.0, 0.5-1.163, 1.5+1.469) = (1.0, -0.663, 2.969)
        """
        r, node, orig = self._renderer_with_skin((0, 0, 0, 1), position=(0, -1.163, 1.469))
        world = r._get_world_verts_for_node(node)
        wp = (0.0, -1.163, 1.469)
        for wv, ov in zip(world, orig):
            assert abs(wv[0] - (ov[0] + wp[0])) < 1e-6
            assert abs(wv[1] - (ov[1] + wp[1])) < 1e-6, \
                f"Y: expected {ov[1]+wp[1]:.3f} (wp applied), got {wv[1]:.3f}"
            assert abs(wv[2] - (ov[2] + wp[2])) < 1e-6

    # ── 90° Y rotation ────────────────────────────────────────────────────────

    def test_90y_rotation_applied(self):
        """90° Y rotation: (1,0,0) → (0,0,-1), (0,0,1) → (1,0,0).
        
        Phase 17: pos=(0,0,0) so no translation, rotation-only result.
        """
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
#  Phase 17: c_bantha body: world transform correctly positions body mesh
# ─────────────────────────────────────────────────────────────────────────────

class TestBanthaBodyJunction:
    """Phase 17: c_bantha skin nodes — world transform places body in correct position.

    btBody_front: local verts Y=[1.117,3.391], world pivot Y=-1.163
    Correct world Y = [-0.046, 2.228] (body covers torso, matches game anatomy)

    Both front and back body share the same pivot Y=-1.163.
    After applying the transform, front Y min ≈ -0.046 and back Y max ≈ 0.033,
    so they meet/overlap near Y≈0 (correct anatomical junction).
    """

    def _bantha_body_front_renderer(self):
        """Simulate btBody_front: position=(0,-1.163,1.469), identity rotation."""
        model, root = _make_standalone('NULL')
        # Representative verts in the junction region (Y ≈ 1.12 to 3.39 local)
        verts = [(0.0, 1.12, 0.0), (0.0, 2.28, 0.5), (0.0, 3.39, 1.0)]
        node = _add_skin_node(root, model, 'btBody_front', verts,
                              rotation=(0, 0, 0, 1),
                              position=(0.0, -1.163, 1.469))
        model.compute_bounds()
        return _make_renderer_for(model), node, verts

    def test_front_body_verts_translated(self):
        """Phase 17: btBody_front verts should be shifted by wp (Y-1.163)."""
        r, node, orig = self._bantha_body_front_renderer()
        world = r._get_world_verts_for_node(node)
        wp_y = -1.163
        for wv, ov in zip(world, orig):
            assert abs(wv[1] - (ov[1] + wp_y)) < 1e-5, \
                f"Y: expected {ov[1]+wp_y:.4f} (wp applied), got {wv[1]:.4f}"

    def test_front_back_junction_preserved(self):
        """Phase 17: Front body Y_min(≈-0.046) and back body Y_max(≈0.033) overlap."""
        model, root = _make_standalone('NULL')
        # Front body: local Y=[1.12, 3.39]; after wp_y=-1.163: world Y=[-0.043, 2.227]
        front_verts = [(0.0, 1.12, 0.0), (0.0, 2.28, 0.5), (0.0, 3.39, 1.0)]
        # Back body: local Y=[-2.85, 1.20]; after wp_y=-1.163: world Y=[-4.013, 0.037]
        back_verts  = [(0.0, -2.85, 0.0), (0.0, 0.06, 0.3), (0.0, 1.20, 0.5)]
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

        # After applying wp: front_ymin ≈ -0.043, back_ymax ≈ 0.037
        # Junction: back body Y_max ≥ front body Y_min means they meet/overlap
        gap = front_ymin - back_ymax
        assert gap <= 0.15, \
            f"Front/back body junction gap = {gap:.3f}; expected ≤ 0.15 (bodies connected)"

    def test_bantha_wp_applied_correctness(self):
        """Phase 17: wp=(0,-1.163,1.469) IS applied to bantha-style skin vert."""
        model, root = _make_standalone('NULL')
        verts = [(0.0, 0.0, 0.5)]
        node = _add_skin_node(root, model, 'body', verts,
                              rotation=(0,0,0,1),
                              position=(0.0, -1.163, 1.469))  # wp_mag≈1.87
        model.compute_bounds()
        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(node)
        # Phase 17: wp applied → y = 0.0 - 1.163 = -1.163, z = 0.5 + 1.469 = 1.969
        assert abs(world[0][1] - (-1.163)) < 1e-5, \
            f"Y must be -1.163 (wp applied), got {world[0][1]:.4f}"
        assert abs(world[0][2] - (0.5 + 1.469)) < 1e-5, \
            f"Z must be 1.969 (wp applied), got {world[0][2]:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
#  Accessory models — same transform path as standalone (Phase 17)
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessorySkinTransform:
    """Phase 17: Accessory and standalone models use the same transform path.
    Both apply the full world transform (rotation + translation).
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

    def test_accessory_vs_standalone_same_result(self):
        """Phase 17: Both 'accessory' and 'standalone' supermodel strings → same result."""
        verts = [(0.5, 0.0, 0.0)]
        wp = (0, 0, 1.5)

        # Standalone (NULL)
        model_s, root_s = _make_standalone('NULL')
        node_s = _add_skin_node(root_s, model_s, 'head', verts,
                                rotation=(0,0,0,1), position=wp)
        model_s.compute_bounds()
        r_s = _make_renderer_for(model_s)
        world_s = r_s._get_world_verts_for_node(node_s)

        # Accessory
        model_a, root_a = _make_standalone('N_AdmrlSaulKar')
        node_a = _add_skin_node(root_a, model_a, 'head', verts,
                                rotation=(0,0,0,1), position=wp)
        model_a.compute_bounds()
        r_a = _make_renderer_for(model_a)
        world_a = r_a._get_world_verts_for_node(node_a)

        # Phase 17: both should produce the same result (z = 0.0 + 1.5 = 1.5)
        assert abs(world_s[0][2] - 1.5) < 1e-4, \
            f"Standalone skin Phase 17: z must be 1.5 (wp applied), got {world_s[0][2]:.3f}"
        assert abs(world_a[0][2] - 1.5) < 1e-4, \
            f"Accessory skin z must be 1.5 (wp applied), got {world_a[0][2]:.3f}"

    def test_base_skeleton_supermodel_wp_applied(self):
        """Phase 17: Supermodel = 'S_Female02' → world transform IS applied.

        Phase 17 unified path: no special-casing based on supermodel name.
        """
        model, root = _make_standalone('S_Female02')
        verts = [(0.0, 0.0, 0.5)]
        node = _add_skin_node(root, model, 'body', verts,
                              rotation=(0,0,0,1), position=(0,0,1.5))
        model.compute_bounds()
        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(node)
        # Phase 17: wp always applied → z = 0.5 + 1.5 = 2.0
        assert abs(world[0][2] - 2.0) < 1e-4, \
            f"Phase 17 (S_Female02): z must be 2.0 (wp applied); z={world[0][2]:.3f}"


# ─────────────────────────────────────────────────────────────────────────────
#  C_terantanak arm-torso junction (geometric proof, Phase 17)
# ─────────────────────────────────────────────────────────────────────────────

class TestTerantanakJunction:
    """Verify that applying 180° Z rotation to Torso connects it to RArm.

    Phase 17: Torso pos=(0,0,0), so no translation offset.
    The 180°Z rotation flips Y: raw negative Y becomes positive, matching RArm.

    Real data from the binary model:
      RArm inner (X<1.6):  Y=[0.249, 0.759]
      Torso raw shoulder:  Y=[-0.882, -0.249]  (negative without rotation)
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
        torso_raw_y = [-0.882, -0.600, -0.400, -0.249]
        rarm_y      = [0.249, 0.400, 0.600, 0.759]

        # RAW (no rotation applied): torso Y stays negative
        torso_ymax_raw = max(torso_raw_y)   # -0.249
        rarm_ymin_raw  = min(rarm_y)        # +0.249
        gap_without_fix = rarm_ymin_raw - torso_ymax_raw  # 0.498
        assert gap_without_fix > 0.4, \
            f"Without fix, gap should be large (≈0.498); got {gap_without_fix:.3f}"


# ─────────────────────────────────────────────────────────────────────────────
#  Non-skin (trimesh) nodes must always get their world transform
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

    def test_skin_node_also_gets_transform(self):
        """Phase 17: Skin node at position (5,0,0): vertex (0,0,0) → world (5,0,0).

        Same as non-skin trimesh — all nodes apply the full world transform.
        """
        model, root = _make_standalone('NULL')
        mesh = ModelNode(name='panel', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
        mesh.parent = root
        mesh.position = (5.0, 0.0, 0.0)
        mesh.rotation = (0, 0, 0, 1)
        mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        mesh.uvs = [(0.5, 0.5)] * 2
        mesh.bone_map = []
        mesh.skin_data = []
        root.children.append(mesh)
        model.compute_bounds()

        r = _make_renderer_for(model)
        world = r._get_world_verts_for_node(mesh)
        # Phase 17: SKIN nodes also get the world transform applied
        assert abs(world[0][0] - 5.0) < 1e-5, \
            f"Phase 17 SKIN vertex at pos (5,0,0): world x should be 5.0, got {world[0][0]}"
        assert abs(world[1][0] - 6.0) < 1e-5
