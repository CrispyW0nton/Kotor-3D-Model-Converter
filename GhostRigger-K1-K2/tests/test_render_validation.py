"""
Validation render tests for key models using actual game data.
Verifies that skin vertex transforms produce correct results (connected geometry).
"""
import os
import sys
import pytest

GAME_MODELS_DIR = '/tmp/game_models'
RENDER_OUT_DIR = '/tmp/final_renders'

# Skip if game models not available
MODELS_AVAILABLE = os.path.isdir(GAME_MODELS_DIR) and os.path.exists(
    os.path.join(GAME_MODELS_DIR, 'c_terantanak.mdl'))


@pytest.mark.skipif(not MODELS_AVAILABLE, reason='Game models not extracted')
class TestSkinVertexJunctionConnectivity:
    """Test that skin node vertices form connected junctions after transform."""

    def _load_model(self, name):
        from src.core.mdl_parser import MDLBinaryParser
        mdl = os.path.join(GAME_MODELS_DIR, f'{name}.mdl')
        mdx = os.path.join(GAME_MODELS_DIR, f'{name}.mdx')
        with open(mdl, 'rb') as f: mdl_data = f.read()
        with open(mdx, 'rb') as f: mdx_data = f.read()
        return MDLBinaryParser(mdl_data, mdx_data).parse()

    def _quat_rotate(self, q, v):
        qx, qy, qz, qw = q
        vx, vy, vz = v
        tx = 2*(qy*vz - qz*vy)
        ty = 2*(qz*vx - qx*vz)
        tz = 2*(qx*vy - qy*vx)
        return (vx + qw*tx + qy*tz - qz*ty,
                vy + qw*ty + qz*tx - qx*tz,
                vz + qw*tz + qx*ty - qy*tx)

    def test_c_terantanak_rarm_torso_junction_connected(self):
        """RArm Y-range and rotated Torso shoulder Y-range must overlap."""
        from src.core.mdl_parser import MDLBinaryParser
        model = self._load_model('c_terantanak')

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        assert 'RArm' in skin, 'RArm skin node missing'
        assert 'Torso' in skin, 'Torso skin node missing'

        rarm = skin['RArm']
        torso = skin['Torso']

        # RArm inner verts (X < 1.6 = near torso junction)
        rarm_inner_y = [v[1] for v in rarm.vertices if v[0] < 1.6]
        assert len(rarm_inner_y) >= 3, 'Too few RArm inner verts'

        # Torso rotation (should be ~180° Z)
        lr = torso.rotation
        lr_len = sum(x**2 for x in lr) ** 0.5
        if lr_len > 1e-9:
            lr = tuple(x/lr_len for x in lr)

        # Apply rotation to torso verts, then find shoulder region
        rotated = [self._quat_rotate(lr, v) for v in torso.vertices]
        shoulder_y = [v[1] for v in rotated if abs(v[0]) > 0.3]
        assert len(shoulder_y) >= 3, 'Too few Torso shoulder verts after rotation'

        # Check Y overlap
        overlap = min(max(rarm_inner_y), max(shoulder_y)) - max(min(rarm_inner_y), min(shoulder_y))
        assert overlap > 0.1, (
            f'Arm-torso junction disconnected: '
            f'RArm Y=[{min(rarm_inner_y):.3f},{max(rarm_inner_y):.3f}], '
            f'Torso Y=[{min(shoulder_y):.3f},{max(shoulder_y):.3f}], '
            f'overlap={overlap:.3f}'
        )

    def test_c_terantanak_larm_torso_junction_connected(self):
        """LArm Y-range and rotated Torso left-shoulder Y-range must overlap."""
        from src.core.mdl_parser import MDLBinaryParser
        model = self._load_model('c_terantanak')

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        larm = skin['LArm']
        torso = skin['Torso']

        # LArm inner verts (X > -1.6 = near torso junction, left side)
        larm_inner_y = [v[1] for v in larm.vertices if v[0] > -1.6]
        assert len(larm_inner_y) >= 3

        lr = torso.rotation
        lr_len = sum(x**2 for x in lr) ** 0.5
        if lr_len > 1e-9:
            lr = tuple(x/lr_len for x in lr)
        rotated = [self._quat_rotate(lr, v) for v in torso.vertices]
        shoulder_y = [v[1] for v in rotated if abs(v[0]) > 0.3]

        overlap = min(max(larm_inner_y), max(shoulder_y)) - max(min(larm_inner_y), min(shoulder_y))
        assert overlap > 0.1, (
            f'Left arm-torso junction disconnected: '
            f'LArm Y=[{min(larm_inner_y):.3f},{max(larm_inner_y):.3f}], '
            f'Torso Y=[{min(shoulder_y):.3f},{max(shoulder_y):.3f}], '
            f'overlap={overlap:.3f}'
        )

    def test_c_bantha_body_junction_connected(self):
        """c_bantha btBody_front and btBodyback Y-ranges must overlap near Y≈1.2."""
        from src.core.mdl_parser import MDLBinaryParser
        model = self._load_model('c_bantha')

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        assert 'btBody_front' in skin, 'btBody_front missing'
        assert 'btBodyback' in skin, 'btBodyback missing'

        front = skin['btBody_front']
        back = skin['btBodyback']

        # Both have identity rotation (no corrective rotation needed)
        # Verify rotation is identity
        for sn in [front, back]:
            rot = sn.rotation
            lr_len = sum(x**2 for x in rot) ** 0.5
            if lr_len > 1e-9:
                rot = tuple(x/lr_len for x in rot)
            assert abs(rot[3]) > 0.99, f'{sn.name} should have near-identity rotation'

        # Vertices are returned as-is (world-space) — check natural junction
        front_ys = [v[1] for v in front.vertices]
        back_ys = [v[1] for v in back.vertices]

        overlap = min(max(front_ys), max(back_ys)) - max(min(front_ys), min(back_ys))
        assert overlap > 0, (
            f'Bantha body junction disconnected: '
            f'front Y=[{min(front_ys):.3f},{max(front_ys):.3f}], '
            f'back Y=[{min(back_ys):.3f},{max(back_ys):.3f}]'
        )

    def test_skin_standalone_identity_verts_unchanged(self):
        """For standalone model with identity rotation, vertices must be returned as-is."""
        from src.core.mdl_parser import MDLBinaryParser
        from src.gui.viewport import FrameRenderer, ArcBallCamera

        model = self._load_model('c_bantha')
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.model = model

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        front_node = skin.get('btBody_front')
        if front_node is None:
            pytest.skip('btBody_front not found')

        world_verts = renderer._get_world_verts_for_node(front_node)
        orig_verts = list(front_node.vertices)

        assert len(world_verts) == len(orig_verts), 'Vert count mismatch'
        # Check a sample of vertices are unchanged
        import math
        for i in range(min(10, len(world_verts))):
            for j in range(3):
                assert abs(world_verts[i][j] - orig_verts[i][j]) < 1e-4, (
                    f'Vert {i} coord {j} changed: {orig_verts[i]} → {world_verts[i]}'
                )

    def test_skin_standalone_with_rotation_applied(self):
        """For standalone skin node with non-identity rotation, only rotation applied (no translation)."""
        from src.core.mdl_parser import MDLBinaryParser
        from src.gui.viewport import FrameRenderer, ArcBallCamera

        model = self._load_model('c_terantanak')
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.model = model

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        torso = skin.get('Torso')
        if torso is None:
            pytest.skip('Torso not found')

        world_verts = renderer._get_world_verts_for_node(torso)
        orig_verts = list(torso.vertices)

        assert len(world_verts) == len(orig_verts), 'Vert count mismatch'

        # Vertices should be CHANGED (rotation applied) but not translated by position
        # Torso has (0,0,0) position so verifying that world_verts != orig_verts
        # (rotation changed them) but centroid should stay near origin
        import numpy as np
        orig_arr = np.array(orig_verts)
        world_arr = np.array(world_verts)

        # Check vertices changed (rotation applied)
        max_diff = float(np.max(np.abs(orig_arr - world_arr)))
        assert max_diff > 0.1, f'Vertices unchanged despite non-identity rotation (max_diff={max_diff})'

        # Check position NOT added (Torso position is 0,0,0 anyway, but verify concept)
        orig_centroid = orig_arr.mean(axis=0)
        world_centroid = world_arr.mean(axis=0)
        pos = torso.position  # should be (0,0,0)
        # centroid should not be displaced by node position
        pos_mag = sum(x**2 for x in pos) ** 0.5
        if pos_mag > 0.01:
            # If there's a non-zero position, verify it wasn't added to centroid
            centroid_shift = float(np.linalg.norm(world_centroid - orig_centroid - np.array(pos)))
            assert centroid_shift < 0.5, 'Node position incorrectly added to skin vertices'


@pytest.mark.skipif(not MODELS_AVAILABLE, reason='Game models not extracted')
class TestRenderOutput:
    """Test that renders produce visible output for key models."""

    def _render_model(self, name, tex_name=None):
        from src.core.mdl_parser import MDLBinaryParser
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        from src.gui.tpc_render_utils import _load_tpc_bytes
        import numpy as np

        mdl = os.path.join(GAME_MODELS_DIR, f'{name}.mdl')
        mdx = os.path.join(GAME_MODELS_DIR, f'{name}.mdx')
        with open(mdl, 'rb') as f: mdl_data = f.read()
        with open(mdx, 'rb') as f: mdx_data = f.read()
        model = MDLBinaryParser(mdl_data, mdx_data).parse()

        textures = {}
        if tex_name:
            for ext in ['.tpc', '.tga']:
                tp = os.path.join(GAME_MODELS_DIR, tex_name + ext)
                if os.path.exists(tp):
                    with open(tp, 'rb') as f: td = f.read()
                    img = _load_tpc_bytes(td)
                    if img: textures[tex_name] = img; break

        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.model = model
        renderer.textures = textures
        renderer.show_texture = bool(textures)
        renderer.show_solid = True
        return renderer.render_still(512, 512, az_deg=0, el_deg=10)

    def _count_model_pixels(self, img):
        import numpy as np
        arr = np.array(img)
        bg = arr[0, 0]
        diff = np.abs(arr.astype(int) - bg.astype(int)).sum(axis=2)
        return int((diff > 20).sum())

    def test_c_terantanak_renders_with_pixels(self):
        img = self._render_model('c_terantanak', 'c_terantanak01')
        assert img is not None, 'Render returned None'
        npix = self._count_model_pixels(img)
        assert npix > 5000, f'Too few model pixels: {npix}'

    def test_c_bantha_renders_with_pixels(self):
        img = self._render_model('c_bantha', 'c_bantha01')
        assert img is not None, 'Render returned None'
        npix = self._count_model_pixels(img)
        assert npix > 20000, f'Too few model pixels: {npix}'

    def test_comm_b_f_renders_with_pixels(self):
        img = self._render_model('comm_b_f', 'comm_b_f01')
        assert img is not None, 'Render returned None'
        npix = self._count_model_pixels(img)
        assert npix > 2000, f'Too few model pixels: {npix}'
