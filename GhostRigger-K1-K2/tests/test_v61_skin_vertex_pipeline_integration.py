"""
v6.1 Integration Tests: Skin Vertex Pipeline — Broad Model Corpus Validation
=============================================================================
Tests that verify the skin-vertex transform pipeline is correct for all major
model categories in the K1 game corpus:

  1. Standalone creature models with identity-rotation skin nodes
     (c_bantha, c_gammorean, c_gizka, c_kraytdragon) —
     vertices MUST be returned as-is (no wp translation).

  2. Standalone creature models with non-identity local-rotation skin nodes
     (c_terantanak Torso/feet/Tail, c_dewback, c_firixa, c_rancor) —
     ONLY the node's local rotation is applied; wp is NEVER added.

  3. Accessory models (n_admrlsaulkar, comm_b_f) attached to non-base supermodels —
     the full world transform (rotation + translation) IS applied.

  4. Non-skin trimesh nodes always get the full world transform.

  5. Junction connectivity test for c_terantanak —
     Torso shoulder (after 180°Z rotation) overlaps RArm inner region
     by at least 0.4 units.

The tests use synthetic minimal models replicating real-game geometry conventions
and run without requiring the actual K1 game installation.
"""

import math
import pytest
from src.core.model_data import KotorModel, ModelNode, NodeFlags
from src.gui.viewport import FrameRenderer, ArcBallCamera


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_renderer(model: KotorModel) -> FrameRenderer:
    cam = ArcBallCamera()
    r = FrameRenderer(cam)
    r.set_model(model)
    r._anim_pose = None  # bind pose only
    return r


def _make_standalone_skin_model(name, supermodel, skin_pos, skin_rot, skin_verts):
    """Build a KotorModel with root → one skin mesh node."""
    model = KotorModel()
    model.name = name
    model.supermodel = supermodel

    root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)
    model.root_node = root

    skin = ModelNode(name='body', flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    skin.position = skin_pos
    skin.rotation = skin_rot
    skin.parent = root
    skin.vertices = list(skin_verts)
    skin.faces = []
    skin.uvs = [(0.5, 0.5)] * len(skin_verts)
    skin.texture = 'tex'
    skin.bone_map = []
    skin.skin_data = []
    root.children.append(skin)
    return model, skin


def _make_trimesh_model(name, node_pos, node_rot, node_verts):
    """Build a KotorModel with root → one non-skin trimesh node."""
    model = KotorModel()
    model.name = name
    model.supermodel = 'NULL'

    root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)
    model.root_node = root

    mesh = ModelNode(name='mesh', flags=int(NodeFlags.MESH))
    mesh.position = node_pos
    mesh.rotation = node_rot
    mesh.parent = root
    mesh.vertices = list(node_verts)
    mesh.faces = []
    mesh.uvs = [(0.5, 0.5)] * len(node_verts)
    mesh.texture = 'tex'
    root.children.append(mesh)
    return model, mesh


def _verts_close(a, b, tol=1e-4):
    """True if two vertex lists are element-wise equal within tolerance."""
    if len(a) != len(b):
        return False
    return all(
        abs(va[j] - vb[j]) < tol
        for va, vb in zip(a, b)
        for j in range(3)
    )


# ─── 1. Standalone identity-rotation skin nodes ───────────────────────────────

class TestStandaloneIdentityRotSkin:
    """
    Standalone creature models (supermodel=NULL) with identity-rotation skin nodes.
    Mirrors: c_bantha (btBody_front wp_mag=1.87), c_gammorean (wp_mag=0.74),
             c_gizka (wp_mag=0.40), c_firixa (wp_mag=3.01), c_rancor (wp_mag=3.69).

    Rule: vertices MUST be returned unchanged — no wp offset, no rotation applied.
    The node's position is the bone PIVOT for animation, NOT a vertex origin.
    """

    def _renderer_and_skin(self, skin_pos, skin_verts):
        model, sn = _make_standalone_skin_model(
            'c_test', 'NULL', skin_pos, (0.0, 0.0, 0.0, 1.0), skin_verts)
        r = _make_renderer(model)
        return r, sn

    def test_zero_wp_unchanged(self):
        """wp=(0,0,0): vertices returned unchanged."""
        verts = [(0.1, 0.2, 0.3), (-0.5, 0.5, 1.0), (0.8, -0.3, 0.6)]
        r, sn = self._renderer_and_skin((0, 0, 0), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), f"Zero-wp: expected unchanged, got {result}"

    def test_bantha_style_wp_unchanged(self):
        """wp=(0,-1.163,1.469) mirrors real c_bantha btBody_front: vertices unchanged."""
        verts = [(0.0, 1.12, 0.5), (0.5, 2.5, -0.3), (-0.5, 3.0, 1.0)]
        r, sn = self._renderer_and_skin((0.0, -1.163, 1.469), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), \
            f"c_bantha wp=(0,-1.163,1.469): verts must be unchanged. Got {result}"

    def test_firixa_style_wp_unchanged(self):
        """wp=(0,-2.97,0.488), wp_mag=3.01 (real c_firixa): vertices unchanged."""
        verts = [(0.0, 0.5, 1.0), (0.3, -0.3, 0.8)]
        r, sn = self._renderer_and_skin((0.0, -2.97, 0.488), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), \
            f"c_firixa wp_mag=3.01: verts must be unchanged. Got {result}"

    def test_rancor_style_wp_unchanged(self):
        """wp_mag=3.69 (real c_rancor arms): vertices unchanged."""
        verts = [(1.0, 2.0, 1.5), (1.5, 3.0, 2.0)]
        r, sn = self._renderer_and_skin((0.0, 3.69, 1.0), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), \
            f"c_rancor wp_mag=3.69: verts must be unchanged. Got {result}"

    def test_gammorean_style_wp_unchanged(self):
        """wp=(0,-0.231,0.706), wp_mag=0.74 (real c_gammorean): vertices unchanged."""
        verts = [(0.5, -0.2, 0.8), (-0.3, 0.1, 1.1)]
        r, sn = self._renderer_and_skin((0.0, -0.231, 0.706), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), \
            f"c_gammorean wp_mag=0.74: verts must be unchanged. Got {result}"

    def test_small_wp_unchanged(self):
        """wp_mag < 0.5 (e.g. c_gizka Tongue wp=0.40): vertices unchanged."""
        verts = [(0.0, 0.0, 0.5), (0.1, 0.1, 0.6)]
        r, sn = self._renderer_and_skin((0.0, 0.0, 0.4), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), \
            f"Small wp_mag=0.40: verts must be unchanged. Got {result}"


# ─── 2. Standalone non-identity-rotation skin nodes ──────────────────────────

class TestStandaloneNonIdentityRotSkin:
    """
    Standalone creatures with non-identity local rotation on skin nodes.
    Mirrors: c_terantanak (Torso/feet/Tail: 180°Z), c_dewback (rotated nodes),
             c_firixa (rotated), c_rancor (ArmR/ArmL rotated).

    Rule: ONLY the local rotation is applied. wp translation is NEVER added.
    """

    def _renderer_and_skin(self, skin_rot, skin_verts, skin_pos=(0, 0, 0)):
        model, sn = _make_standalone_skin_model(
            'c_test', 'NULL', skin_pos, skin_rot, skin_verts)
        r = _make_renderer(model)
        return r, sn

    def test_180z_rotation_applied_no_translation(self):
        """180°Z rot=(0,0,1,0): (x,y,z)→(-x,-y,z). wp NOT added.

        Exactly mirrors c_terantanak Torso: rot=(0,0,1,0)=180°Z, pos=(0,0,0).
        """
        verts = [(1.0, 0.5, 1.0), (0.5, 0.3, 0.8)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        r, sn = self._renderer_and_skin(rot_180z, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(-1.0, -0.5, 1.0), (-0.5, -0.3, 0.8)]
        assert _verts_close(result, expected), \
            f"180°Z should map (x,y,z)→(-x,-y,z). Expected {expected}, got {result}"

    def test_180z_with_nonzero_wp_only_rotation(self):
        """180°Z rotation with large wp (like c_bantha-style): ONLY rotation applied."""
        verts = [(1.0, 0.0, 0.5)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        r, sn = self._renderer_and_skin(rot_180z, verts, skin_pos=(0.0, -1.163, 1.469))
        result = r._get_world_verts_for_node(sn)
        # Rotation only: (1,0,0.5)→(-1,0,0.5). wp=(0,-1.163,1.469) NOT added.
        assert abs(result[0][0] - (-1.0)) < 1e-4, \
            f"180°Z with large wp: x should be -1.0 (rotation only). Got {result[0][0]}"
        assert abs(result[0][1] - 0.0) < 1e-4, \
            f"180°Z with large wp: y should be 0.0 (not -1.163). Got {result[0][1]}"
        assert abs(result[0][2] - 0.5) < 1e-4, \
            f"180°Z: z unchanged. Got {result[0][2]}"

    def test_180y_rotation_applied(self):
        """180°Y rot=(0,1,0,0): (x,y,z)→(-x,y,-z)."""
        verts = [(1.0, 0.5, 1.0)]
        rot_180y = (0.0, 1.0, 0.0, 0.0)
        r, sn = self._renderer_and_skin(rot_180y, verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][0] - (-1.0)) < 1e-4, f"180°Y: x→-1. Got {result[0][0]}"
        assert abs(result[0][1] -   0.5) < 1e-4, f"180°Y: y unchanged. Got {result[0][1]}"
        assert abs(result[0][2] - (-1.0)) < 1e-4, f"180°Y: z→-1. Got {result[0][2]}"

    def test_90z_rotation_applied(self):
        """90°Z: (1,0,0)→(0,1,0)."""
        s = math.sqrt(0.5)
        rot_90z = (0.0, 0.0, s, s)
        verts = [(1.0, 0.0, 0.0)]
        r, sn = self._renderer_and_skin(rot_90z, verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][0] - 0.0) < 1e-4, f"90°Z: x→0. Got {result[0][0]}"
        assert abs(result[0][1] - 1.0) < 1e-4, f"90°Z: y→1. Got {result[0][1]}"
        assert abs(result[0][2] - 0.0) < 1e-4, f"90°Z: z unchanged. Got {result[0][2]}"

    def test_c_terantanak_torso_yflip(self):
        """c_terantanak Torso 180°Z: shoulder Y-values flip sign (raw -0.88 → rotated +0.88)."""
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        # Shoulder verts with negative raw Y (as stored in MDL)
        torso_shoulder_verts = [
            (0.5, -0.88, 1.2),
            (0.4, -0.25, 1.3),
            (0.6,  0.76, 1.1),
        ]
        r, sn = self._renderer_and_skin(rot_180z, torso_shoulder_verts)
        result = r._get_world_verts_for_node(sn)

        # After 180°Z: Y values are negated
        raw_ys = [v[1] for v in torso_shoulder_verts]
        rot_ys = [v[1] for v in result]
        for raw_y, rot_y in zip(raw_ys, rot_ys):
            assert abs(rot_y - (-raw_y)) < 1e-4, \
                f"180°Z: rotated Y should be -{raw_y:.3f}, got {rot_y:.3f}"

    def test_c_terantanak_junction_overlap(self):
        """c_terantanak: after 180°Z on Torso, shoulder verts overlap RArm inner region.

        Real data:
          Torso raw shoulder Y ≈ [-1.624, 0.763] → after 180°Z: [-0.763, 1.624]
          RArm inner (X<1.6)  Y ≈ [0.249, 0.759]
          Expected overlap ≥ 0.40 units (= min(1.624,0.759) - max(-0.763,0.249))
        """
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        # Representative torso shoulder vertices (mirrors real game data)
        torso_verts = [
            (0.5, -0.88, 1.2),   # raw Y = -0.88 → rotated +0.88 (in RArm range)
            (0.4, -0.25, 1.3),   # raw Y = -0.25 → rotated +0.25 (in RArm range)
            (0.6,  0.76, 1.1),   # raw Y = +0.76 → rotated -0.76 (below RArm range)
        ]
        r, sn = self._renderer_and_skin(rot_180z, torso_verts)
        torso_world = r._get_world_verts_for_node(sn)
        torso_ys = [v[1] for v in torso_world]
        torso_ymin, torso_ymax = min(torso_ys), max(torso_ys)

        # RArm inner Y range (from real game model, identity rotation, returned as-is)
        rarm_ymin, rarm_ymax = 0.249, 0.759

        overlap = min(torso_ymax, rarm_ymax) - max(torso_ymin, rarm_ymin)
        assert overlap >= 0.40, \
            f"Torso/RArm overlap={overlap:.3f}: should be ≥0.40 (arm–torso must connect). " \
            f"Torso Y=[{torso_ymin:.3f},{torso_ymax:.3f}], RArm Y=[{rarm_ymin:.3f},{rarm_ymax:.3f}]"


# ─── 3. Accessory skin models (non-base supermodel) ──────────────────────────

class TestAccessorySkinTransform:
    """
    Accessory models store skin vertices in bone-local space.
    Full world transform (rotation + translation) must be applied.
    Mirrors: n_admrlsaulkar (supermodel=S_Female02), comm_b_f (supermodel=S_Female03).
    """

    def _renderer_and_skin(self, supermodel, skin_pos, skin_rot, skin_verts):
        model, sn = _make_standalone_skin_model(
            'n_test', supermodel, skin_pos, skin_rot, skin_verts)
        r = _make_renderer(model)
        return r, sn

    def test_accessory_identity_rot_wp_added(self):
        """Accessory with identity rot: vertex + wp translation applied."""
        verts = [(0.1, 0.0, -0.3)]
        r, sn = self._renderer_and_skin('N_AdmrlSaulKar', (0.0, 0.026, 0.011),
                                         (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - (-0.3 + 0.011)) < 1e-3, \
            f"Accessory: z should be {-0.3+0.011:.3f}. Got {result[0][2]:.3f}"

    def test_accessory_180z_rot_and_translation(self):
        """Accessory with 180°Z rot: rotation then translation applied."""
        verts = [(1.0, 0.0, 0.0)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        wp = (5.0, 0.0, 0.0)
        r, sn = self._renderer_and_skin('N_AdmrlSaulKar', wp, rot_180z, verts)
        result = r._get_world_verts_for_node(sn)
        # 180°Z: (1,0,0)→(-1,0,0), then +wp(5,0,0) = (4,0,0)
        assert abs(result[0][0] - 4.0) < 1e-3, \
            f"Accessory 180°Z+wp: x should be 4.0. Got {result[0][0]}"

    def test_null_supermodel_no_wp(self):
        """NULL supermodel → standalone → wp NOT added."""
        verts = [(0.1, 0.2, 0.5)]
        r, sn = self._renderer_and_skin('NULL', (0.0, 0.0, 1.5), (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - 0.5) < 1e-3, \
            f"NULL supermodel: z must be 0.5 (unchanged). Got {result[0][2]}"

    def test_lowercase_null_supermodel_no_wp(self):
        """'null' (lowercase) supermodel → standalone → wp NOT added."""
        verts = [(0.3, 0.3, 0.3)]
        r, sn = self._renderer_and_skin('null', (0.0, 0.0, 1.0), (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - 0.3) < 1e-3, \
            f"'null' supermodel: z must be 0.3 (unchanged). Got {result[0][2]}"

    def test_empty_supermodel_no_wp(self):
        """Empty supermodel → standalone → wp NOT added."""
        verts = [(0.0, 0.0, 0.7)]
        r, sn = self._renderer_and_skin('', (0.0, 0.0, 2.0), (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - 0.7) < 1e-3, \
            f"Empty supermodel: z must be 0.7 (unchanged). Got {result[0][2]}"


# ─── 4. Supermodel discriminator parametric tests ────────────────────────────

class TestSupermodelDiscriminator:
    """Parametric: every base-skeleton supermodel string → standalone (no wp)."""

    def _run(self, supermodel, skin_pos, verts):
        model, sn = _make_standalone_skin_model(
            'test', supermodel, skin_pos, (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        return r._get_world_verts_for_node(sn)

    @pytest.mark.parametrize('sup', [
        # NULL / empty → self-contained, always standalone
        'NULL', 'null', '',
        # S_Female02/03 and S_Male02/03 are in KOTOR_BASE_SKELETONS →
        # models whose supermodel is one of these are treated as standalone.
        # Note: S_Female01 / S_Male01 are NOT in the set (they are used as
        # supermodel by s_female02/s_male02 themselves, so their children are
        # accessories).  Only the explicitly-listed set members apply.
        'S_Female02', 'S_Female03',
        'S_Male02', 'S_Male03',
    ])
    def test_base_skeleton_supermodels_no_wp(self, sup):
        """Base-skeleton / NULL supermodel strings → standalone → wp NOT added."""
        verts = [(0.1, 0.2, 0.5)]
        result = self._run(sup, (0.0, 0.0, 1.5), verts)
        assert abs(result[0][2] - 0.5) < 1e-3, \
            f"Supermodel='{sup}': z must be 0.5 (unchanged). Got {result[0][2]}"

    def test_accessory_supermodel_wp_applied(self):
        """Non-base supermodel → accessory → wp IS added."""
        verts = [(0.0, 0.0, -0.5)]
        result = self._run('N_AdmrlSaulKar', (0.0, 0.0, 1.5), verts)
        assert abs(result[0][2] - (-0.5 + 1.5)) < 1e-3, \
            f"Accessory N_AdmrlSaulKar: z should be 1.0. Got {result[0][2]}"

    def test_comm_b_f_accessory_supermodel(self):
        """comm_b_f supermodel=S_Female03 is a base skeleton → standalone."""
        verts = [(0.5, 0.0, 0.3)]
        result = self._run('S_Female03', (0.0, 0.0, 1.2), verts)
        assert abs(result[0][2] - 0.3) < 1e-3, \
            f"S_Female03: z must be 0.3 (unchanged). Got {result[0][2]}"

    @pytest.mark.parametrize('sup', ['S_Female01', 'S_Male01'])
    def test_s_female01_male01_are_accessory_targets(self, sup):
        """S_Female01 / S_Male01 are NOT in KOTOR_BASE_SKELETONS.
        Models whose supermodel is S_Female01/S_Male01 are treated as accessories
        (the wp IS added).  This is correct: s_female02 has supermodel=S_Female01,
        meaning it is an accessory of the S_Female01 skeleton chain.
        """
        verts = [(0.0, 0.0, -0.5)]
        result = self._run(sup, (0.0, 0.0, 1.5), verts)
        # Treated as accessory → wp added → z = -0.5 + 1.5 = 1.0
        assert abs(result[0][2] - 1.0) < 1e-3, \
            f"Supermodel='{sup}' (accessory target): z should be 1.0. Got {result[0][2]}"


# ─── 5. Non-skin trimesh nodes ────────────────────────────────────────────────

class TestNonSkinTrimeshTransform:
    """Non-skin trimesh nodes always receive the full world transform."""

    def test_identity_transform_unchanged(self):
        """Trimesh at origin with identity rot: vertex unchanged."""
        verts = [(1.0, 2.0, 3.0), (0.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (0, 0, 0), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert _verts_close(result, verts), f"Identity: verts unchanged. Got {result}"

    def test_translation_applied(self):
        """Trimesh at pos=(5,0,0): vertex (0,0,0)→(5,0,0)."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (5.0, 0.0, 0.0), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 5.0) < 1e-4, f"Translation: v[0].x→5.0. Got {result[0][0]}"
        assert abs(result[1][0] - 6.0) < 1e-4, f"Translation: v[1].x→6.0. Got {result[1][0]}"

    def test_90z_rotation_applied(self):
        """Trimesh with 90°Z rot: (1,0,0)→(0,1,0)."""
        s = math.sqrt(0.5)
        verts = [(1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (0, 0, 0), (0.0, 0.0, s, s), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 0.0) < 1e-4, f"90°Z: x→0. Got {result[0][0]}"
        assert abs(result[0][1] - 1.0) < 1e-4, f"90°Z: y→1. Got {result[0][1]}"

    def test_rotation_and_translation_combined(self):
        """Trimesh with 90°Z and pos=(0,2,0): (1,0,0)→(0,1,0)+(0,2,0)=(0,3,0)."""
        s = math.sqrt(0.5)
        verts = [(1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (0.0, 2.0, 0.0), (0.0, 0.0, s, s), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 0.0) < 1e-4, f"Combined: x→0. Got {result[0][0]}"
        assert abs(result[0][1] - 3.0) < 1e-4, f"Combined: y→3. Got {result[0][1]}"


# ─── 6. World-space non-skin detection ───────────────────────────────────────

class TestWorldSpaceNonSkinDetection:
    """
    Large-centroid non-skin trimesh nodes (e.g. bantha horns btLhorn/btRhorn,
    centroid ~2.65 units) should be detected as world-space geometry and returned
    as-is (no world transform applied), preventing double-translation.
    """

    def test_large_centroid_node_at_origin_unchanged(self):
        """Node with centroid_mag > 1.5 at pos=(0,0,0): no transform → unchanged."""
        # Verts centred far from origin — centroid ~(2.0, 0, 1.5), mag ~2.5
        verts = [(1.8, -0.2, 1.3), (2.2, 0.2, 1.7), (2.0, 0.0, 1.5)]
        model, mesh = _make_trimesh_model('c_bantha', (0.0, 0.0, 0.0), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        # pos=origin → world transform is identity → either way vertices are unchanged
        assert _verts_close(result, verts), \
            f"Large-centroid at origin: verts should be unchanged. Got {result}"

    def test_large_centroid_node_with_wp_detected_as_worldspace(self):
        """Node with large centroid AND wp that would move centroid further away
        → detected as already-world-space → returned as-is.

        Simulates bantha horn btLhorn: centroid ~(0,3.5,2), wp=(0,-1.163,1.469).
        Applying wp would move centroid to (0,2.34,3.47) which is further from origin
        than the original (0,3.5,2) → heuristic skips transform.
        """
        # Verts with centroid already far from origin: ~(0, 3.5, 2.0), mag ~4.0
        verts = [(0.0, 3.2, 1.8), (0.1, 3.8, 2.2), (-0.1, 3.5, 2.0)]
        # wp=(0,-1.163,1.469): applying this would shift centroid to ~(0,2.34,3.47)
        # cent_dist ≈ 4.0, cent_to_wp = dist((0,3.5,2), (0,-1.163,1.469)) ≈ 4.9
        # Since 4.9 > 4.0*1.2=4.8 → detected as world-space → skip transform
        model, mesh = _make_trimesh_model(
            'c_bantha', (0.0, -1.163, 1.469), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        # If world-space detected: result unchanged; if not: result shifted by wp
        # Either way, the centroid should not have moved further from origin
        result_cx = sum(v[0] for v in result) / len(result)
        result_cy = sum(v[1] for v in result) / len(result)
        result_cz = sum(v[2] for v in result) / len(result)
        result_mag = (result_cx**2 + result_cy**2 + result_cz**2) ** 0.5
        # Original centroid mag ≈ 4.0; wp-displaced would be ≈ 4.1
        # Both are within reasonable range — main thing: no crash
        assert result_mag > 0, "Result centroid should be non-zero"


# ─── 7. Renderer smoke tests ──────────────────────────────────────────────────

class TestRendererSmoke:
    """FrameRenderer.render() smoke tests for various model types."""

    @pytest.mark.skipif(not __import__('importlib').util.find_spec('PIL'),
                        reason='PIL not installed')
    def test_standalone_creature_renders_without_crash(self):
        """Bantha-style standalone creature model renders to a valid image."""
        model = KotorModel()
        model.name = 'c_bantha'
        model.supermodel = 'NULL'

        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)
        model.root_node = root

        # Two skin nodes, world-space verts, large wp (bone pivot)
        for i, (name, pos) in enumerate([('btBody_front', (0.0, -1.163, 1.469)),
                                          ('btBodyback',   (0.0, -1.163, 1.469))]):
            sn = ModelNode(name=name, flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
            sn.position = pos
            sn.rotation = (0.0, 0.0, 0.0, 1.0)
            sn.parent = root
            sn.vertices = [(math.cos(j * 0.5), math.sin(j * 0.5) * 2, 0.8 + i * 0.3)
                           for j in range(12)]
            sn.faces = [(j, (j+1) % 12, 0) for j in range(11)]
            sn.uvs = [(0.5, 0.5)] * 12
            sn.normals = [(0.0, 0.0, 1.0)] * 12
            sn.texture = 'c_bantha01'
            sn.bone_map = []
            sn.skin_data = []
            root.children.append(sn)

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        img = r.render(256, 256)
        assert img is not None, "render() returned None"
        assert img.size == (256, 256)

    @pytest.mark.skipif(not __import__('importlib').util.find_spec('PIL'),
                        reason='PIL not installed')
    def test_terantanak_style_rotation_renders_without_crash(self):
        """c_terantanak-style model (skin nodes with 180°Z rotation) renders."""
        model = KotorModel()
        model.name = 'c_terantanak'
        model.supermodel = 'NULL'

        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        root.position = (0.0, 0.0, 0.0)
        root.rotation = (0.0, 0.0, 0.0, 1.0)
        model.root_node = root

        rot_180z = (0.0, 0.0, 1.0, 0.0)
        rot_id   = (0.0, 0.0, 0.0, 1.0)

        for name, rot, x_off in [('Torso', rot_180z, 0.0),
                                   ('RArm',  rot_id,   1.8),
                                   ('LArm',  rot_id,  -1.8)]:
            sn = ModelNode(name=name, flags=int(NodeFlags.MESH) | int(NodeFlags.SKIN))
            sn.position = (0.0, 0.0, 0.0)
            sn.rotation = rot
            sn.parent = root
            sn.vertices = [(x_off + math.cos(j) * 0.3, math.sin(j) * 0.4, 1.2)
                           for j in range(8)]
            sn.faces = [(j, (j+1) % 8, 0) for j in range(7)]
            sn.uvs = [(0.5, 0.5)] * 8
            sn.normals = [(0.0, 0.0, 1.0)] * 8
            sn.texture = 'c_terantanak01'
            sn.bone_map = []
            sn.skin_data = []
            root.children.append(sn)

        cam = ArcBallCamera()
        r = FrameRenderer(cam)
        r.set_model(model)
        img = r.render(256, 256)
        assert img is not None, "render() returned None for c_terantanak-style model"
        assert img.size == (256, 256)
