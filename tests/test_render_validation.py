"""
Validation render tests for key models using test assets.

Verifies that:
  - Skin vertex transforms produce correct results (connected geometry)
  - Renders produce visible output for c_bantha and N_sithpraet
  - The render pipeline handles textures correctly

Uses test_assets/c_bantha/ (c_bantha model + c_bantha01.tpc texture) and
test_assets/N_sithpraet.mdl / n_sithpraet01.tga.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Test asset paths ─────────────────────────────────────────────────────────
ASSETS_DIR      = os.path.join(os.path.dirname(__file__), '..', 'test_assets')
BANTHA_MDL      = os.path.join(ASSETS_DIR, 'c_bantha', 'c_bantha.mdl')
BANTHA_MDX      = os.path.join(ASSETS_DIR, 'c_bantha', 'c_bantha.mdx')
BANTHA_TPC      = os.path.join(ASSETS_DIR, 'c_bantha', 'c_bantha01.tpc')
SITHPRAET_MDL   = os.path.join(ASSETS_DIR, 'N_sithpraet.mdl')
SITHPRAET_MDX   = os.path.join(ASSETS_DIR, 'N_sithpraet.mdx')
SITHPRAET_TGA   = os.path.join(ASSETS_DIR, 'n_sithpraet01.tga')

BANTHA_AVAILABLE    = os.path.exists(BANTHA_MDL)
SITHPRAET_AVAILABLE = os.path.exists(SITHPRAET_MDL)


def _load_model(mdl_path, mdx_path):
    from src.core.mdl_parser import MDLBinaryParser
    mdl = open(mdl_path, 'rb').read()
    mdx = open(mdx_path, 'rb').read() if os.path.exists(mdx_path) else b''
    return MDLBinaryParser(mdl, mdx).parse()


def _quat_rotate(q, v):
    qx, qy, qz, qw = q
    vx, vy, vz = v
    tx = 2*(qy*vz - qz*vy)
    ty = 2*(qz*vx - qx*vz)
    tz = 2*(qx*vy - qy*vx)
    return (vx + qw*tx + qy*tz - qz*ty,
            vy + qw*ty + qz*tx - qx*tz,
            vz + qw*tz + qx*ty - qy*tx)


# ── Skin vertex connectivity tests ───────────────────────────────────────────

class TestSkinVertexJunctionConnectivity:
    """Test that skin node vertices form connected junctions after transform."""

    def test_c_bantha_body_junction_connected(self):
        """c_bantha btBody_front and btBodyback Y-ranges must overlap near Y≈1.2."""
        if not BANTHA_AVAILABLE:
            pytest.skip('c_bantha model not available')
        model = _load_model(BANTHA_MDL, BANTHA_MDX)

        skin = {n.name: n for n in model.nodes if getattr(n, 'is_skin', False)}
        if 'btBody_front' not in skin or 'btBodyback' not in skin:
            pytest.skip('btBody_front/btBodyback skin nodes missing from c_bantha')

        front = skin['btBody_front']
        back  = skin['btBodyback']

        # Both have near-identity rotation (no corrective rotation needed)
        for sn in [front, back]:
            rot = sn.rotation
            lr_len = sum(x**2 for x in rot) ** 0.5
            if lr_len > 1e-9:
                rot = tuple(x/lr_len for x in rot)
            assert abs(rot[3]) > 0.99, f'{sn.name} should have near-identity rotation'

        front_ys = [v[1] for v in front.vertices]
        back_ys  = [v[1] for v in back.vertices]

        overlap = (min(max(front_ys), max(back_ys))
                   - max(min(front_ys), min(back_ys)))
        assert overlap > 0, (
            f'Bantha body junction disconnected: '
            f'front Y=[{min(front_ys):.3f},{max(front_ys):.3f}], '
            f'back Y=[{min(back_ys):.3f},{max(back_ys):.3f}]'
        )

    def test_skin_standalone_world_verts_correctly_transformed(self):
        """For standalone skin nodes, world verts = local verts + world pivot translation.

        KotOR MDL rule (Phase 16, verified against PyKotor GL renderer and KotorBlender):
          ALL MDL vertices — including skin nodes — are stored in NODE-LOCAL space.
          The full parent-chain world transform must be applied to produce world coords.

        btBody_front (c_bantha):
          - Local verts Y ∈ [1.117, 3.391]
          - Node world pivot Y ≈ -1.163
          - Expected world verts Y ∈ [-0.046, 2.228]
          - NOT local verts as-is (that would give wrong Y ∈ [1.117, 3.391])
        """
        if not BANTHA_AVAILABLE:
            pytest.skip('c_bantha model not available')
        from src.gui.viewport import FrameRenderer, ArcBallCamera

        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)

        skin = {n.name: n for n in model.all_nodes() if getattr(n, 'is_skin', False)}
        front_node = skin.get('btBody_front')
        if front_node is None:
            pytest.skip('btBody_front not found in c_bantha')

        world_verts = renderer._get_world_verts_for_node(front_node)
        orig_verts  = list(front_node.vertices)

        assert len(world_verts) == len(orig_verts), 'Vert count mismatch'

        # World verts must NOT be identical to local verts (node pivot ≠ origin)
        changed = sum(
            1 for i in range(min(20, len(world_verts)))
            if any(abs(world_verts[i][j] - orig_verts[i][j]) > 0.01 for j in range(3))
        )
        assert changed > 0, (
            'btBody_front world verts equal local verts — world transform not applied. '
            f'Node world pivot: {front_node.world_position()}'
        )

        # World Y range should match PyKotor expected: [-0.1, 2.3] (tolerance ±0.2)
        world_ys = [v[1] for v in world_verts]
        world_zs = [v[2] for v in world_verts]
        assert min(world_ys) < 0.2, (
            f'btBody_front world Y min {min(world_ys):.3f} too high (expected < 0.2)'
        )
        assert max(world_ys) > 1.5, (
            f'btBody_front world Y max {max(world_ys):.3f} too low (expected > 1.5)'
        )
        assert min(world_zs) > -0.1, (
            f'btBody_front world Z min {min(world_zs):.3f} too low (expected > -0.1)'
        )
        assert max(world_zs) > 2.0, (
            f'btBody_front world Z max {max(world_zs):.3f} too low (expected > 2.0)'
        )

    def test_n_sithpraet_skin_nodes_have_vertices(self):
        """N_sithpraet skin nodes must each have non-empty vertex lists."""
        if not SITHPRAET_AVAILABLE:
            pytest.skip('N_sithpraet model not available')
        model = _load_model(SITHPRAET_MDL, SITHPRAET_MDX)
        skin_nodes = [n for n in model.all_nodes() if getattr(n, 'is_skin', False)]
        if not skin_nodes:
            pytest.skip('N_sithpraet has no skin nodes')
        for node in skin_nodes:
            assert node.vertices is not None, f'{node.name}: vertices is None'
            assert len(node.vertices) > 0, f'{node.name}: empty vertex list'

    def test_n_sithpraet_mesh_bounding_box_finite(self):
        """N_sithpraet mesh nodes must have finite bounding boxes."""
        if not SITHPRAET_AVAILABLE:
            pytest.skip('N_sithpraet model not available')
        import math
        model = _load_model(SITHPRAET_MDL, SITHPRAET_MDX)
        for node in model.mesh_nodes():
            for v in node.vertices[:5]:  # spot-check first 5
                for coord in v:
                    assert math.isfinite(coord), \
                        f'{node.name}: non-finite vertex coord {coord}'


# ── Render output tests ──────────────────────────────────────────────────────

class TestRenderOutput:
    """Render visible output for available test models."""

    def _render_model(self, mdl_path, mdx_path, tex_path=None):
        from src.gui.viewport import FrameRenderer, ArcBallCamera, _load_tpc_bytes
        model = _load_model(mdl_path, mdx_path)
        textures = {}
        if tex_path and os.path.exists(tex_path):
            tex_data = open(tex_path, 'rb').read()
            img = _load_tpc_bytes(tex_data)
            if img:
                tex_name = os.path.splitext(os.path.basename(tex_path))[0]
                textures[tex_name] = img
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)
        if textures:
            renderer.textures = textures
            renderer.show_texture = True
        renderer.show_solid = True
        return renderer.render(512, 512)

    def _count_model_pixels(self, img):
        import numpy as np
        arr = np.array(img)
        bg  = arr[0, 0]
        diff = np.abs(arr.astype(int) - bg.astype(int)).sum(axis=2)
        return int((diff > 20).sum())

    def test_c_bantha_renders_with_pixels(self):
        """c_bantha rendered headlessly must produce >5000 non-background pixels."""
        if not BANTHA_AVAILABLE:
            pytest.skip('c_bantha model not available')
        img = self._render_model(BANTHA_MDL, BANTHA_MDX, BANTHA_TPC)
        assert img is not None, 'Render returned None'
        npix = self._count_model_pixels(img)
        assert npix > 5000, f'Too few model pixels: {npix}'

    def test_n_sithpraet_renders_with_pixels(self):
        """N_sithpraet rendered headlessly must produce >2000 non-background pixels."""
        if not SITHPRAET_AVAILABLE:
            pytest.skip('N_sithpraet model not available')
        img = self._render_model(SITHPRAET_MDL, SITHPRAET_MDX, SITHPRAET_TGA)
        assert img is not None, 'Render returned None'
        npix = self._count_model_pixels(img)
        assert npix > 2000, f'Too few model pixels: {npix}'

    def test_render_returns_correct_size(self):
        """Render must return an image with the requested dimensions."""
        if not BANTHA_AVAILABLE:
            pytest.skip('c_bantha model not available')
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        model = _load_model(BANTHA_MDL, BANTHA_MDX)
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(model)
        img = renderer.render(200, 150)
        assert img is not None
        assert img.size == (200, 150), f'Expected (200,150), got {img.size}'

    def test_render_none_model_does_not_crash(self):
        """Rendering with no model set must not raise an exception."""
        from src.gui.viewport import FrameRenderer, ArcBallCamera
        cam = ArcBallCamera()
        renderer = FrameRenderer(cam)
        renderer.set_model(None)
        # Must not raise; result may be None or a blank grid image
        try:
            renderer.render(100, 100)
        except Exception as e:
            pytest.fail(f'render(None model) raised: {e}')
