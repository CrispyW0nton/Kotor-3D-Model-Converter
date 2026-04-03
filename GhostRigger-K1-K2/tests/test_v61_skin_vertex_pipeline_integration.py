"""
v6.1 Integration Tests: Skin Vertex Pipeline — Phase 17 Unified Transform
==========================================================================
Phase 17: All KotOR MDL vertices (skin AND non-skin) are stored in NODE-LOCAL
space and require the full world transform to produce correct world-space coords.

VERIFIED SOURCES (Phase 17):
  - KotorBlender (io_scene_kotor/scene/modelnode/base.py):
    set_object_data() sets obj.location = self.position (LOCAL, not world),
    and uploads bl_mesh.vertices from self.verts without any pre-transform.
    Blender applies the parent-chain transforms automatically via scene graph.
  - PyKotor: reads vertex_positions raw from binary MDL with no world-space pre-baking.
  - Direct binary analysis of c_bantha:
    btBody_front local verts Y=[1.117,3.391], world pivot Y=-1.163
    Correct world Y = [-0.046, 2.228] (body covers torso/back, anatomy correct)
    Old "as-is" gave wrong Y = [1.117, 3.391] (body floating in front of skeleton)

Test categories:
  1. Standalone identity-rotation skin nodes → full world transform (translate by wp)
  2. Standalone non-identity-rotation skin nodes → full world transform (rotate + translate)
  3. Accessory skin models (non-base supermodel) → full world transform (same path)
  4. Supermodel discriminator tests — all apply wp (Phase 17 unified)
  5. Non-skin trimesh nodes → full world transform
  6. Phase 16+17 non-skin large-centroid correctness (heuristic removed)
  7. Renderer smoke tests
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
    """Build a KotorModel with root -> one skin mesh node."""
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
    """Build a KotorModel with root -> one non-skin trimesh node."""
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
    Phase 17: All skin nodes use full world transform.

    For identity-rotation nodes, the world transform is: translate by node world pos.
    At root level (pos=(0,0,0)) this is identity -> verts unchanged.
    With non-zero pivot (e.g. btBody_front pos=(0,-1.163,1.469)), verts are shifted.

    Verified by: c_bantha btBody_front local Y=[1.117,3.391], pivot Y=-1.163
    -> correct world Y=[-0.046,2.228] (anatomy correct, matches PyKotor analysis).
    """

    def _renderer_and_skin(self, skin_pos, skin_verts):
        model, sn = _make_standalone_skin_model(
            'c_test', 'NULL', skin_pos, (0.0, 0.0, 0.0, 1.0), skin_verts)
        r = _make_renderer(model)
        return r, sn

    def test_zero_wp_unchanged(self):
        """wp=(0,0,0): world transform is identity -> vertices unchanged."""
        verts = [(0.1, 0.2, 0.3), (-0.5, 0.5, 1.0), (0.8, -0.3, 0.6)]
        r, sn = self._renderer_and_skin((0, 0, 0), verts)
        result = r._get_world_verts_for_node(sn)
        assert _verts_close(result, verts), f"Zero-wp: expected unchanged, got {result}"

    def test_bantha_style_wp_applied(self):
        """wp=(0,-1.163,1.469) mirrors c_bantha btBody_front: wp IS applied (Phase 17)."""
        verts = [(0.0, 1.12, 0.5), (0.5, 2.5, -0.3), (-0.5, 3.0, 1.0)]
        wp = (0.0, -1.163, 1.469)
        r, sn = self._renderer_and_skin(wp, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"c_bantha wp=(0,-1.163,1.469): world transform must be applied.\n" \
            f"Expected {expected}, got {result}"

    def test_firixa_style_wp_applied(self):
        """wp=(0,-2.97,0.488), wp_mag=3.01 (real c_firixa): wp IS applied."""
        verts = [(0.0, 0.5, 1.0), (0.3, -0.3, 0.8)]
        wp = (0.0, -2.97, 0.488)
        r, sn = self._renderer_and_skin(wp, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"c_firixa wp_mag=3.01: world transform must be applied. Got {result}"

    def test_rancor_style_wp_applied(self):
        """wp_mag=3.69 (real c_rancor arms): wp IS applied."""
        verts = [(1.0, 2.0, 1.5), (1.5, 3.0, 2.0)]
        wp = (0.0, 3.69, 1.0)
        r, sn = self._renderer_and_skin(wp, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"c_rancor wp_mag=3.69: world transform must be applied. Got {result}"

    def test_gammorean_style_wp_applied(self):
        """wp=(0,-0.231,0.706), wp_mag=0.74 (real c_gammorean): wp IS applied."""
        verts = [(0.5, -0.2, 0.8), (-0.3, 0.1, 1.1)]
        wp = (0.0, -0.231, 0.706)
        r, sn = self._renderer_and_skin(wp, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"c_gammorean wp_mag=0.74: world transform must be applied. Got {result}"

    def test_small_wp_applied(self):
        """wp_mag=0.40: small world position IS still applied (no threshold)."""
        verts = [(0.0, 0.0, 0.5), (0.1, 0.1, 0.6)]
        wp = (0.0, 0.0, 0.4)
        r, sn = self._renderer_and_skin(wp, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"Small wp_mag=0.40: world transform must be applied. Got {result}"


# ─── 2. Standalone non-identity-rotation skin nodes ──────────────────────────

class TestStandaloneNonIdentityRotSkin:
    """
    Standalone creatures with non-identity local rotation on skin nodes.
    Phase 17: full world transform (rotate + translate) is always applied.
    """

    def _renderer_and_skin(self, skin_rot, skin_verts, skin_pos=(0, 0, 0)):
        model, sn = _make_standalone_skin_model(
            'c_test', 'NULL', skin_pos, skin_rot, skin_verts)
        r = _make_renderer(model)
        return r, sn

    def test_180z_rotation_applied_no_translation_at_origin(self):
        """180 degree Z rot=(0,0,1,0): (x,y,z)->(-x,-y,z). pos=(0,0,0), no additional translation."""
        verts = [(1.0, 0.5, 1.0), (0.5, 0.3, 0.8)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        r, sn = self._renderer_and_skin(rot_180z, verts)
        result = r._get_world_verts_for_node(sn)
        expected = [(-1.0, -0.5, 1.0), (-0.5, -0.3, 0.8)]
        assert _verts_close(result, expected), \
            f"180 degree Z should map (x,y,z)->(-x,-y,z). Expected {expected}, got {result}"

    def test_180z_with_nonzero_wp_rotation_and_translation(self):
        """180 degree Z rotation with large wp: BOTH rotation AND translation applied (Phase 17)."""
        verts = [(1.0, 0.0, 0.5)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        wp = (0.0, -1.163, 1.469)
        r, sn = self._renderer_and_skin(rot_180z, verts, skin_pos=wp)
        result = r._get_world_verts_for_node(sn)
        # 180 degree Z: (1,0,0.5)->(-1,0,0.5), then add wp=(0,-1.163,1.469)
        assert abs(result[0][0] - (-1.0)) < 1e-4, \
            f"180 degree Z + wp: x should be -1.0 (rotated). Got {result[0][0]}"
        assert abs(result[0][1] - (-1.163)) < 1e-4, \
            f"180 degree Z + wp: y should be -1.163 (wp added). Got {result[0][1]}"
        assert abs(result[0][2] - (0.5 + 1.469)) < 1e-4, \
            f"180 degree Z + wp: z should be 1.969 (rot + wp). Got {result[0][2]}"

    def test_180y_rotation_applied(self):
        """180 degree Y rot=(0,1,0,0): (x,y,z)->(-x,y,-z)."""
        verts = [(1.0, 0.5, 1.0)]
        rot_180y = (0.0, 1.0, 0.0, 0.0)
        r, sn = self._renderer_and_skin(rot_180y, verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][0] - (-1.0)) < 1e-4, f"180 degree Y: x->-1. Got {result[0][0]}"
        assert abs(result[0][1] -   0.5) < 1e-4, f"180 degree Y: y unchanged. Got {result[0][1]}"
        assert abs(result[0][2] - (-1.0)) < 1e-4, f"180 degree Y: z->-1. Got {result[0][2]}"

    def test_90z_rotation_applied(self):
        """90 degree Z: (1,0,0)->(0,1,0)."""
        s = math.sqrt(0.5)
        rot_90z = (0.0, 0.0, s, s)
        verts = [(1.0, 0.0, 0.0)]
        r, sn = self._renderer_and_skin(rot_90z, verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][0] - 0.0) < 1e-4, f"90 degree Z: x->0. Got {result[0][0]}"
        assert abs(result[0][1] - 1.0) < 1e-4, f"90 degree Z: y->1. Got {result[0][1]}"
        assert abs(result[0][2] - 0.0) < 1e-4, f"90 degree Z: z unchanged. Got {result[0][2]}"

    def test_c_terantanak_torso_yflip(self):
        """c_terantanak Torso 180 degree Z: shoulder Y-values flip sign (raw -0.88 -> rotated +0.88).

        Phase 17: node is at pos=(0,0,0) so no translation, only rotation.
        """
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        torso_shoulder_verts = [
            (0.5, -0.88, 1.2),
            (0.4, -0.25, 1.3),
            (0.6,  0.76, 1.1),
        ]
        r, sn = self._renderer_and_skin(rot_180z, torso_shoulder_verts)
        result = r._get_world_verts_for_node(sn)
        raw_ys = [v[1] for v in torso_shoulder_verts]
        rot_ys = [v[1] for v in result]
        for raw_y, rot_y in zip(raw_ys, rot_ys):
            assert abs(rot_y - (-raw_y)) < 1e-4, \
                f"180 degree Z: rotated Y should be -{raw_y:.3f}, got {rot_y:.3f}"

    def test_c_terantanak_junction_overlap(self):
        """c_terantanak: after 180 degree Z on Torso, shoulder verts overlap RArm inner region."""
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        torso_verts = [
            (0.5, -0.88, 1.2),
            (0.4, -0.25, 1.3),
            (0.6,  0.76, 1.1),
        ]
        r, sn = self._renderer_and_skin(rot_180z, torso_verts)
        torso_world = r._get_world_verts_for_node(sn)
        torso_ys = [v[1] for v in torso_world]
        torso_ymin, torso_ymax = min(torso_ys), max(torso_ys)
        rarm_ymin, rarm_ymax = 0.249, 0.759
        overlap = min(torso_ymax, rarm_ymax) - max(torso_ymin, rarm_ymin)
        assert overlap >= 0.40, \
            f"Torso/RArm overlap={overlap:.3f}: should be >=0.40"


# ─── 3. Accessory skin models ─────────────────────────────────────────────────

class TestAccessorySkinTransform:
    """
    Phase 17: All skin nodes apply full world transform regardless of supermodel.
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
        """Accessory with 180 degree Z rot: rotation then translation applied."""
        verts = [(1.0, 0.0, 0.0)]
        rot_180z = (0.0, 0.0, 1.0, 0.0)
        wp = (5.0, 0.0, 0.0)
        r, sn = self._renderer_and_skin('N_AdmrlSaulKar', wp, rot_180z, verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][0] - 4.0) < 1e-3, \
            f"Accessory 180 degree Z+wp: x should be 4.0. Got {result[0][0]}"

    def test_null_supermodel_wp_applied(self):
        """NULL supermodel: world transform IS applied (Phase 17)."""
        verts = [(0.1, 0.2, 0.5)]
        wp = (0.0, 0.0, 1.5)
        r, sn = self._renderer_and_skin('NULL', wp, (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - (0.5 + 1.5)) < 1e-3, \
            f"NULL supermodel Phase 17: z must be {0.5+1.5} (wp applied). Got {result[0][2]}"

    def test_lowercase_null_supermodel_wp_applied(self):
        """'null' (lowercase) supermodel: world transform IS applied (Phase 17)."""
        verts = [(0.3, 0.3, 0.3)]
        wp = (0.0, 0.0, 1.0)
        r, sn = self._renderer_and_skin('null', wp, (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - (0.3 + 1.0)) < 1e-3, \
            f"'null' supermodel Phase 17: z must be 1.3 (wp applied). Got {result[0][2]}"

    def test_empty_supermodel_wp_applied(self):
        """Empty supermodel: world transform IS applied (Phase 17)."""
        verts = [(0.0, 0.0, 0.7)]
        wp = (0.0, 0.0, 2.0)
        r, sn = self._renderer_and_skin('', wp, (0, 0, 0, 1), verts)
        result = r._get_world_verts_for_node(sn)
        assert abs(result[0][2] - (0.7 + 2.0)) < 1e-3, \
            f"Empty supermodel Phase 17: z must be {0.7+2.0} (wp applied). Got {result[0][2]}"


# ─── 4. Supermodel discriminator — unified transform (Phase 17) ───────────────

class TestSupermodelDiscriminator:
    """Phase 17: All supermodel strings -> same transform path (always apply wp)."""

    def _run(self, supermodel, skin_pos, verts):
        model, sn = _make_standalone_skin_model(
            'test', supermodel, skin_pos, (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        return r._get_world_verts_for_node(sn)

    @pytest.mark.parametrize('sup', [
        'NULL', 'null', '',
        'S_Female02', 'S_Female03',
        'S_Male02', 'S_Male03',
    ])
    def test_base_skeleton_supermodels_wp_applied(self, sup):
        """Phase 17: All supermodel strings -> world transform IS applied (wp added)."""
        verts = [(0.1, 0.2, 0.5)]
        wp = (0.0, 0.0, 1.5)
        result = self._run(sup, wp, verts)
        assert abs(result[0][2] - (0.5 + 1.5)) < 1e-3, \
            f"Supermodel='{sup}' Phase 17: z must be {0.5+1.5} (wp applied). Got {result[0][2]}"

    def test_accessory_supermodel_wp_applied(self):
        """Non-base supermodel -> wp IS added."""
        verts = [(0.0, 0.0, -0.5)]
        result = self._run('N_AdmrlSaulKar', (0.0, 0.0, 1.5), verts)
        assert abs(result[0][2] - (-0.5 + 1.5)) < 1e-3, \
            f"Accessory N_AdmrlSaulKar: z should be 1.0. Got {result[0][2]}"

    def test_comm_b_f_supermodel_wp_applied(self):
        """S_Female03 supermodel -> world transform applied (Phase 17)."""
        verts = [(0.5, 0.0, 0.3)]
        wp = (0.0, 0.0, 1.2)
        result = self._run('S_Female03', wp, verts)
        assert abs(result[0][2] - (0.3 + 1.2)) < 1e-3, \
            f"S_Female03 Phase 17: z must be {0.3+1.2} (wp applied). Got {result[0][2]}"

    @pytest.mark.parametrize('sup', ['S_Female01', 'S_Male01'])
    def test_s_female01_male01_wp_applied(self, sup):
        """S_Female01 / S_Male01 -> world transform applied (Phase 17 unified path)."""
        verts = [(0.0, 0.0, -0.5)]
        result = self._run(sup, (0.0, 0.0, 1.5), verts)
        assert abs(result[0][2] - 1.0) < 1e-3, \
            f"Supermodel='{sup}' Phase 17: z should be 1.0. Got {result[0][2]}"


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
        """Trimesh at pos=(5,0,0): vertex (0,0,0)->(5,0,0)."""
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (5.0, 0.0, 0.0), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 5.0) < 1e-4, f"Translation: v[0].x->5.0. Got {result[0][0]}"
        assert abs(result[1][0] - 6.0) < 1e-4, f"Translation: v[1].x->6.0. Got {result[1][0]}"

    def test_90z_rotation_applied(self):
        """Trimesh with 90 degree Z rot: (1,0,0)->(0,1,0)."""
        s = math.sqrt(0.5)
        verts = [(1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (0, 0, 0), (0.0, 0.0, s, s), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 0.0) < 1e-4, f"90 degree Z: x->0. Got {result[0][0]}"
        assert abs(result[0][1] - 1.0) < 1e-4, f"90 degree Z: y->1. Got {result[0][1]}"

    def test_rotation_and_translation_combined(self):
        """Trimesh with 90 degree Z and pos=(0,2,0): (1,0,0)->(0,1,0)+(0,2,0)=(0,3,0)."""
        s = math.sqrt(0.5)
        verts = [(1.0, 0.0, 0.0)]
        model, mesh = _make_trimesh_model('test', (0.0, 2.0, 0.0), (0.0, 0.0, s, s), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert abs(result[0][0] - 0.0) < 1e-4, f"Combined: x->0. Got {result[0][0]}"
        assert abs(result[0][1] - 3.0) < 1e-4, f"Combined: y->3. Got {result[0][1]}"


# ─── 6. Non-skin trimesh world transform (Phase 16+17 confirmed) ──────────────

class TestWorldSpaceNonSkinDetection:
    """
    Phase 16+17: The old world-space heuristic for non-skin trimesh nodes has been
    removed. ALL mesh nodes (skin + non-skin) store vertices in NODE-LOCAL space
    and always need the full parent-chain world transform applied.
    """

    def test_large_centroid_node_at_origin_unchanged(self):
        """Node with centroid_mag > 1.5 at pos=(0,0,0): transform is identity -> unchanged."""
        verts = [(1.8, -0.2, 1.3), (2.2, 0.2, 1.7), (2.0, 0.0, 1.5)]
        model, mesh = _make_trimesh_model('c_bantha', (0.0, 0.0, 0.0), (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        assert _verts_close(result, verts), \
            f"Large-centroid at origin: world transform is identity, verts unchanged. Got {result}"

    def test_large_centroid_node_with_wp_gets_transform_applied(self):
        """Non-skin node with large centroid AND non-origin pivot: world transform must be applied."""
        verts = [(0.0, 2.4, 0.9), (0.1, 2.5, 1.0), (-0.1, 2.3, 0.8)]
        wp = (0.0, -0.890, 1.469)
        model, mesh = _make_trimesh_model('c_bantha', wp, (0, 0, 0, 1), verts)
        r = _make_renderer(model)
        result = r._get_world_verts_for_node(mesh)
        expected = [(v[0] + wp[0], v[1] + wp[1], v[2] + wp[2]) for v in verts]
        assert _verts_close(result, expected), \
            f"Non-skin node with displaced pivot: world transform must be applied.\n" \
            f"  Expected centroid Y~={sum(e[1] for e in expected)/len(expected):.3f}, " \
            f"got Y~={sum(r_v[1] for r_v in result)/len(result):.3f}"


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
        """c_terantanak-style model (skin nodes with 180 degree Z rotation) renders."""
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
