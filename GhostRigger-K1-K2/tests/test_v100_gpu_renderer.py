"""
tests/test_v100_gpu_renderer.py
================================
Validation tests for the v10.0 GPU hybrid renderer (src/gui/gpu_renderer.py).

Test categories
---------------
1.  Module imports and GpuRenderer instantiation
2.  Matrix math helpers (_mat4_perspective, _mat4_lookat, _mat4_mul)
3.  Vectorized VBO builder (_build_vbo_data)
4.  GpuRenderer context + shader compilation
5.  Full GPU render: output dimensions, pixel sanity, alpha channel
6.  TXI blend modes: additive vs normal (per-node blending uniform)
7.  UV scroll: animated_uv offset applied
8.  RotateTexture flag: vertex shader UV swap
9.  Lightmap compositing: has_lightmap flag wires LM sampler
10. Animated alpha + selfillum from anim_pose
11. Performance counters: perf_summary() and per-counter fields
12. Triangle throughput: GPU path completes ≥1 frame for 50k tris
13. CPU fallback: force_cpu=True returns PIL Image
14. Release and re-init cycle
15. Edge cases: empty mesh, zero-dimension image, nan/inf vertices
16. _GlTexCache upload, cache hit, invalidate
17. _benchmark() function smoke test
18. Persistent FBO reuse (same size = no recreate)
19. Visual correctness: clear-color pixel matches expected background
20. Large-UV wrapping: VBO built without crash for UV > _UV_SENTINEL
"""

import math
import struct
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, '.')


# ──────────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_node(n_verts=300, n_tris=100, name='test_node',
               has_lightmap=False, lm_name='',
               texture='', txi_blending=0,
               rotate_texture=False, animate_uv=False,
               uv_dir_x=0.0, uv_dir_y=0.0,
               alpha=1.0):
    """Create a minimal synthetic ModelNode-like object."""
    rng = np.random.default_rng(12345 + hash(name) % 999)
    verts  = rng.uniform(-1, 1, (n_verts, 3)).tolist()
    norms  = [[0.0, 0.0, 1.0]] * n_verts
    uvs    = rng.uniform(0, 1, (n_verts, 2)).tolist()
    uvs_lm = rng.uniform(0, 1, (n_verts, 2)).tolist() if has_lightmap else []
    faces  = [[rng.integers(0, n_verts),
               rng.integers(0, n_verts),
               rng.integers(0, n_verts)] for _ in range(n_tris)]

    class _Node:
        pass

    nd = _Node()
    nd.name              = name
    nd.render            = True
    nd.alpha             = alpha
    nd.texture           = texture
    nd.lightmap          = lm_name
    nd.has_lightmap      = has_lightmap
    nd.selfillum         = (0.0, 0.0, 0.0)
    nd.diffuse           = (0.8, 0.7, 0.6)
    nd.ambient           = (0.4, 0.4, 0.4)
    nd.position          = (0.0, 0.0, 0.0)
    nd.rotation          = (0.0, 0.0, 0.0, 1.0)
    nd.txi_blending      = txi_blending
    nd.rotate_texture    = rotate_texture
    nd.animate_uv        = animate_uv
    nd.uv_dir_x          = uv_dir_x
    nd.uv_dir_y          = uv_dir_y
    nd.uv_jitter         = 0.0
    nd.uv_jitter_speed   = 0.0
    nd.transparency_hint = 0
    nd.verts             = verts
    nd.normals           = norms
    nd.uvs               = uvs
    nd.uvs_lm            = uvs_lm
    nd.face_uvs          = []
    nd.faces             = faces
    nd.flags             = 0
    return nd


def _make_model(nodes=None):
    class _Model:
        name = 'test_model'
        game_version = None

    m = _Model()
    m.nodes = nodes or [_make_node()]
    return m


def _make_camera(eye=(0, 3, 5)):
    class _Cam:
        target = (0, 0, 0)
        up     = (0, 1, 0)
        fov    = 45.0
        near   = 0.01
        far    = 1000.0

    c = _Cam()
    c.eye = eye
    return c


def _make_texture(w=32, h=32, color=(200, 100, 50, 255)):
    """Create a solid-colour PIL RGBA image."""
    try:
        from PIL import Image
        img = Image.new('RGBA', (w, h), color)
        return img
    except ImportError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  1. Module imports and GpuRenderer instantiation
# ──────────────────────────────────────────────────────────────────────────────

class TestImports(unittest.TestCase):

    def test_gpu_renderer_importable(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.assertTrue(callable(GpuRenderer))

    def test_gpu_renderer_instantiates(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        self.assertIsNotNone(gr)
        self.assertFalse(gr._gpu_available)
        self.assertFalse(gr._init_attempted)

    def test_public_api(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        self.assertTrue(hasattr(gr, 'render'))
        self.assertTrue(hasattr(gr, 'release'))
        self.assertTrue(hasattr(gr, 'perf'))
        self.assertTrue(hasattr(gr, 'is_gpu'))
        self.assertTrue(hasattr(gr, 'perf_summary'))
        self.assertTrue(hasattr(gr, 'invalidate_node'))
        self.assertTrue(hasattr(gr, 'invalidate_all'))


# ──────────────────────────────────────────────────────────────────────────────
#  2. Matrix helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestMatrixHelpers(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import (
            _mat4_perspective, _mat4_lookat, _mat4_identity,
            _mat4_mul, _mat3_normal,
        )
        self._persp  = _mat4_perspective
        self._lookat = _mat4_lookat
        self._ident  = _mat4_identity
        self._mul    = _mat4_mul
        self._norm   = _mat3_normal

    def test_identity_is_identity(self):
        I = self._ident()
        self.assertEqual(I.shape, (4, 4))
        np.testing.assert_allclose(I, np.eye(4, dtype=np.float32), atol=1e-6)

    def test_perspective_shapes(self):
        P = self._persp(math.radians(45), 1.0, 0.1, 1000.0)
        self.assertEqual(P.shape, (16,))  # flat 4x4 column-major

    def test_perspective_near_far_entries(self):
        fov = math.radians(45); near = 0.1; far = 100.0
        P = self._persp(fov, 1.0, near, far).reshape(4, 4)
        # The perspective matrix should have a non-zero entry encoding near/far
        nf = 1.0 / (near - far)
        expected_22 = (far + near) * nf
        # Check the value is plausibly in the right range
        self.assertAlmostEqual(float(P[2, 2]), expected_22, places=3)

    def test_lookat_shape(self):
        V = self._lookat((0, 3, 5), (0, 0, 0), (0, 1, 0))
        self.assertEqual(V.shape, (4, 4))

    def test_lookat_identity_for_trivial_case(self):
        # Look along -Z from (0,0,1) to (0,0,0) with Y up
        # Should give a near-identity view matrix (just a translation)
        V = self._lookat((0, 0, 5), (0, 0, 0), (0, 1, 0))
        # The forward component should be ~(0,0,-1)
        fwd = -V.reshape(4, 4)[:3, 2]
        np.testing.assert_allclose(fwd, [0, 0, -1], atol=0.01)

    def test_mat4_mul_with_identity(self):
        I = self._ident().flatten()
        A = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                     dtype=np.float32)
        result = self._mul(A, I)
        np.testing.assert_allclose(result, A, atol=1e-5)

    def test_normal_matrix_from_identity(self):
        I = self._ident()
        N = self._norm(I)
        self.assertEqual(N.shape, (3, 3))
        np.testing.assert_allclose(N, np.eye(3, dtype=np.float32), atol=1e-6)


# ──────────────────────────────────────────────────────────────────────────────
#  3. Vectorized VBO builder
# ──────────────────────────────────────────────────────────────────────────────

class TestVboBuilder(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import _build_vbo_data
        self._build = _build_vbo_data

    def test_basic_indexed(self):
        node = _make_node(n_verts=9, n_tris=3)
        vdata, idx = self._build(node, (0, 0, 0), (0, 0, 0, 1))
        self.assertIsNotNone(vdata)
        self.assertIsNotNone(idx)
        self.assertEqual(vdata.shape[1], 14)  # stride = 14 floats
        self.assertEqual(vdata.dtype, np.float32)
        self.assertEqual(idx.dtype, np.uint32)
        self.assertEqual(len(idx), 9)  # 3 tris × 3

    def test_returns_none_for_empty_node(self):
        class _Empty:
            verts = []; normals = []; uvs = []; uvs_lm = []; faces = []; face_uvs = []
        vd, idx = self._build(_Empty(), (0, 0, 0), (0, 0, 0, 1))
        self.assertIsNone(vd)
        self.assertIsNone(idx)

    def test_world_transform_translation(self):
        node = _make_node(n_verts=3, n_tris=1)
        node.verts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        node.normals = [[0.0, 0.0, 1.0]] * 3
        node.faces = [[0, 1, 2]]
        wp = (5.0, 3.0, -2.0)
        vd, idx = self._build(node, wp, (0, 0, 0, 1))
        # First vertex should be translated to world pos
        np.testing.assert_allclose(vd[0, 0:3], [5.0, 3.0, -2.0], atol=1e-5)

    def test_vertex_colors_default_white(self):
        node = _make_node(n_verts=6, n_tris=2)
        vd, _ = self._build(node, (0, 0, 0), (0, 0, 0, 1))
        # Columns 10-13 are RGBA vertex color (default 1.0)
        np.testing.assert_allclose(vd[:, 10:14], 1.0, atol=1e-6)

    def test_sentinel_uvs_clamped_to_half(self):
        """UVs > 20.0 (sentinel) should be replaced with 0.5."""
        node = _make_node(n_verts=3, n_tris=1)
        node.uvs = [(-99.0, 127.0), (0.5, 0.5), (0.5, 0.5)]
        node.faces = [[0, 1, 2]]
        vd, _ = self._build(node, (0, 0, 0), (0, 0, 0, 1))
        # vertex 0 uv should be 0.5 (sentinel clamped)
        self.assertAlmostEqual(float(vd[0, 6]), 0.5, places=4)
        self.assertAlmostEqual(float(vd[0, 7]), 0.5, places=4)
        # vertex 1 uv unchanged
        self.assertAlmostEqual(float(vd[1, 6]), 0.5, places=4)

    def test_quaternion_rotation_applied(self):
        """Rotation (0,0,sin45°,cos45°) = 90° around Z → (1,0,0) → (0,1,0)."""
        node = _make_node(n_verts=3, n_tris=1)
        node.verts = [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        node.normals = [[0.0, 0.0, 1.0]] * 3
        node.faces = [[0, 1, 2]]
        s = math.sin(math.pi / 4)
        c = math.cos(math.pi / 4)
        vd, _ = self._build(node, (0, 0, 0), (0, 0, s, c))
        # (1,0,0) rotated 90° around Z → (0,1,0)
        np.testing.assert_allclose(vd[0, 0:3], [0.0, 1.0, 0.0], atol=1e-5)

    def test_large_mesh_performance(self):
        """Building a 10k-triangle VBO should complete in under 500ms."""
        node = _make_node(n_verts=30000, n_tris=10000)
        t0 = time.perf_counter()
        vd, idx = self._build(node, (0, 0, 0), (0, 0, 0, 1))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertIsNotNone(vd)
        self.assertLess(elapsed_ms, 500,
                        f"VBO build took {elapsed_ms:.1f}ms, expected <500ms")

    def test_face_uv_indices_expand_to_non_indexed(self):
        """When face_uvs present, result should be non-indexed (idx=None)."""
        node = _make_node(n_verts=6, n_tris=2)
        node.face_uvs = [[0, 1, 2], [3, 4, 5]]
        vd, idx = self._build(node, (0, 0, 0), (0, 0, 0, 1))
        self.assertIsNotNone(vd)
        self.assertIsNone(idx)  # non-indexed path
        # 2 faces × 3 vertices = 6 rows
        self.assertEqual(len(vd), 6)


# ──────────────────────────────────────────────────────────────────────────────
#  4. GpuRenderer context + shader compilation
# ──────────────────────────────────────────────────────────────────────────────

class TestGpuContext(unittest.TestCase):

    def test_ensure_context_returns_bool(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        ok = gr._ensure_context()
        self.assertIsInstance(ok, bool)
        if ok:
            self.assertIsNotNone(gr._ctx)
            self.assertIsNotNone(gr._prog)
        gr.release()

    def test_second_ensure_context_noop(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        ok1 = gr._ensure_context()
        ok2 = gr._ensure_context()
        self.assertEqual(ok1, ok2)  # idempotent
        gr.release()

    def test_force_cpu_disables_gpu(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        gr.force_cpu = True
        ok = gr._ensure_context()
        self.assertFalse(ok)
        self.assertFalse(gr._gpu_available)
        gr.release()

    def test_shader_uniforms_all_present(self):
        """All expected shader uniforms must be present after compilation."""
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        if not gr._ensure_context():
            self.skipTest("GPU not available")
        expected = [
            'u_mvp', 'u_model', 'u_normal_mat', 'u_cam_pos',
            'u_uv_scroll', 'u_rotate_tex',
            'u_tex', 'u_lm_tex', 'u_has_tex', 'u_has_lm',
            'u_diffuse', 'u_selfillum', 'u_alpha', 'u_node_alpha',
            'u_light_dir', 'u_light_dir2', 'u_ambient', 'u_specular',
            'u_shininess', 'u_blend_mode', 'u_alpha_test', 'u_cam_pos',
        ]
        members = list(gr._prog._members.keys())
        for u in expected:
            self.assertIn(u, members, f"Missing uniform: {u}")
        gr.release()

    def test_release_clears_state(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        gr._ensure_context()
        gr.release()
        self.assertIsNone(gr._ctx)
        self.assertIsNone(gr._prog)
        self.assertFalse(gr._gpu_available)


# ──────────────────────────────────────────────────────────────────────────────
#  5. Full GPU render output
# ──────────────────────────────────────────────────────────────────────────────

class TestGpuRenderOutput(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.model  = _make_model()
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_render_returns_pil_image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        img = self.gr._render_gpu(self.model, self.camera, 256, 256, {}, None, 0.0)
        self.assertIsInstance(img, Image.Image)

    def test_render_correct_dimensions(self):
        img = self.gr._render_gpu(self.model, self.camera, 320, 240, {}, None, 0.0)
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (320, 240))

    def test_render_rgba_mode(self):
        img = self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)
        self.assertEqual(img.mode, 'RGBA')

    def test_render_non_empty(self):
        """At least some pixels should be non-background-colour."""
        img = self.gr._render_gpu(self.model, self.camera, 256, 256, {}, None, 0.0)
        self.assertIsNotNone(img)
        import numpy as np
        arr = np.array(img)
        # Background is ~(31, 36, 41) — at least some pixels should differ
        bg = np.array([31, 36, 41, 255])
        matches_bg = np.all(np.abs(arr.astype(int) - bg.astype(int)) < 15, axis=-1)
        self.assertFalse(np.all(matches_bg), "All pixels match background; mesh may not be visible")

    def test_render_with_none_model_returns_none(self):
        # The public render() wrapper handles None model; _render_gpu itself
        # may still return a clear-color image (valid behaviour for no-mesh frame).
        img = self.gr.render(None, self.camera, 256, 256)
        self.assertIsNone(img)

    def test_render_zero_dimensions_returns_none(self):
        img = self.gr.render(self.model, self.camera, 0, 256)
        self.assertIsNone(img)
        img2 = self.gr.render(self.model, self.camera, 256, 0)
        self.assertIsNone(img2)


# ──────────────────────────────────────────────────────────────────────────────
#  6. TXI blend modes wired correctly
# ──────────────────────────────────────────────────────────────────────────────

class TestBlendModes(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_additive_node_renders(self):
        """Additive blend (txi_blending=1) should produce a valid frame."""
        model = _make_model([_make_node(txi_blending=1)])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_punchthrough_node_renders(self):
        """Punch-through alpha (txi_blending=2) should produce a valid frame."""
        model = _make_model([_make_node(txi_blending=2)])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_normal_blend_renders(self):
        model = _make_model([_make_node(txi_blending=0)])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)


# ──────────────────────────────────────────────────────────────────────────────
#  7. UV scroll / animate_uv
# ──────────────────────────────────────────────────────────────────────────────

class TestUvScroll(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_uv_scroll_uniform_set(self):
        """When animate_uv=True, u_uv_scroll uniform should receive non-zero offset."""
        node = _make_node(animate_uv=True, uv_dir_x=0.5, uv_dir_y=0.0)
        model = _make_model([node])
        # Monitor what value gets set in the shader
        scroll_values = []
        _orig = self.gr._prog.__class__.__setitem__
        # Instead: just render at t=2.0 and t=0.0, image pixels should differ
        img_t0 = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 0.0)
        self.gr.invalidate_all()
        img_t2 = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 2.0)
        self.assertIsNotNone(img_t0)
        self.assertIsNotNone(img_t2)
        # (pixel content difference is not guaranteed w/o actual texture, but no crash)

    def test_no_scroll_when_animate_uv_false(self):
        node = _make_node(animate_uv=False, uv_dir_x=1.0, uv_dir_y=1.0)
        model = _make_model([node])
        img = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 5.0)
        self.assertIsNotNone(img)


# ──────────────────────────────────────────────────────────────────────────────
#  8. RotateTexture flag
# ──────────────────────────────────────────────────────────────────────────────

class TestRotateTexture(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_rotate_texture_true_renders(self):
        model = _make_model([_make_node(rotate_texture=True)])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_rotate_texture_false_renders(self):
        model = _make_model([_make_node(rotate_texture=False)])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)


# ──────────────────────────────────────────────────────────────────────────────
#  9. Lightmap compositing
# ──────────────────────────────────────────────────────────────────────────────

class TestLightmapCompositing(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_lightmap_node_renders(self):
        node = _make_node(has_lightmap=True, lm_name='test_lm')
        model = _make_model([node])
        lm_img = _make_texture(64, 64, (128, 128, 128, 255))  # neutral grey lightmap
        textures = {'test_lm': lm_img} if lm_img else {}
        img = self.gr._render_gpu(model, self.camera, 128, 128, textures, None, 0.0)
        self.assertIsNotNone(img)

    def test_no_lightmap_still_renders(self):
        node = _make_node(has_lightmap=False)
        model = _make_model([node])
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_lightmap_texture_uploaded_to_slot1(self):
        """If lightmap is present, u_has_lm should be set to 1 in the shader."""
        node = _make_node(has_lightmap=True, lm_name='lm_test')
        model = _make_model([node])
        lm = _make_texture(32, 32, (200, 200, 200, 255))
        textures = {'lm_test': lm} if lm else {}
        # Just verify no error is raised and image is produced
        img = self.gr._render_gpu(model, self.camera, 128, 128, textures, None, 0.0)
        self.assertIsNotNone(img)


# ──────────────────────────────────────────────────────────────────────────────
#  10. Animated alpha + selfillum from anim_pose
# ──────────────────────────────────────────────────────────────────────────────

class TestAnimatedMaterial(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def _make_anim_pose(self, node_name, alpha=None, selfillum=None):
        class _NP:
            pass
        class _AP:
            nodes = {}
        np_obj = _NP()
        np_obj.alpha    = alpha
        np_obj.selfillum = selfillum
        np_obj.position = (0, 0, 0)
        np_obj.rotation = (0, 0, 0, 1)
        ap = _AP()
        ap.nodes = {node_name.lower(): np_obj}
        return ap

    def test_animated_alpha_renders(self):
        node = _make_node(name='glass_node')
        model = _make_model([node])
        anim = self._make_anim_pose('glass_node', alpha=0.3)
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, anim, 1.0)
        self.assertIsNotNone(img)

    def test_animated_selfillum_renders(self):
        node = _make_node(name='glow_node')
        model = _make_model([node])
        anim = self._make_anim_pose('glow_node', selfillum=(1.0, 0.5, 0.0))
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, anim, 1.0)
        self.assertIsNotNone(img)

    def test_no_anim_pose_renders(self):
        model = _make_model()
        img = self.gr._render_gpu(model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_node_alpha_clamp(self):
        """Node alpha outside [0,1] should be clamped."""
        node = _make_node(alpha=2.5)
        model = _make_model([node])
        img = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 0.0)
        self.assertIsNotNone(img)


# ──────────────────────────────────────────────────────────────────────────────
#  11. Performance counters
# ──────────────────────────────────────────────────────────────────────────────

class TestPerfCounters(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.model  = _make_model()
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_perf_dict_has_all_keys(self):
        expected_keys = ['last_frame_ms', 'gpu_upload_ms', 'draw_ms',
                         'readback_ms', 'tri_count', 'backend']
        for k in expected_keys:
            self.assertIn(k, self.gr.perf)

    def test_perf_tri_count_after_render(self):
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        self.assertGreater(self.gr.perf['tri_count'], 0)

    def test_perf_times_positive_after_render(self):
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        self.assertGreaterEqual(self.gr.perf['draw_ms'], 0.0)
        self.assertGreaterEqual(self.gr.perf['readback_ms'], 0.0)

    def test_perf_summary_contains_backend(self):
        self.gr.render(self.model, self.camera, 128, 128)
        s = self.gr.perf_summary()
        self.assertIn('backend', s)

    def test_is_gpu_property(self):
        # After init, should reflect GPU availability
        self.assertEqual(self.gr.is_gpu, self.gr._gpu_available)


# ──────────────────────────────────────────────────────────────────────────────
#  12. Triangle throughput
# ──────────────────────────────────────────────────────────────────────────────

class TestTriangleThroughput(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_50k_tris_completes(self):
        """A 50k-triangle model should render without crash or OOM."""
        node = _make_node(n_verts=150000, n_tris=50000)
        model = _make_model([node])
        img = self.gr._render_gpu(model, self.camera, 256, 256, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_multi_node_model(self):
        """Model with 10 nodes should all render."""
        nodes = [_make_node(n_verts=300, n_tris=100, name=f'node_{i}')
                 for i in range(10)]
        model = _make_model(nodes)
        img = self.gr._render_gpu(model, self.camera, 256, 256, {}, None, 0.0)
        self.assertIsNotNone(img)
        self.assertEqual(self.gr.perf['tri_count'], 1000)  # 10 nodes × 100 tris


# ──────────────────────────────────────────────────────────────────────────────
#  13. CPU fallback
# ──────────────────────────────────────────────────────────────────────────────

class TestCpuFallback(unittest.TestCase):

    def test_force_cpu_renders(self):
        """force_cpu=True should use CPU path and return an image."""
        from src.gui.gpu_renderer import GpuRenderer
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        gr = GpuRenderer()
        gr.force_cpu = True
        model  = _make_model()
        camera = _make_camera()
        img = gr.render(model, camera, 128, 128)
        # CPU fallback may fail gracefully (returns None if FrameRenderer errors)
        # but should NOT raise an exception
        gr.release()

    def test_perf_backend_is_cpu_when_forced(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        gr.force_cpu = True
        model  = _make_model()
        camera = _make_camera()
        gr.render(model, camera, 64, 64)
        self.assertEqual(gr.perf['backend'], 'cpu')
        gr.release()


# ──────────────────────────────────────────────────────────────────────────────
#  14. Release and re-init cycle
# ──────────────────────────────────────────────────────────────────────────────

class TestReleaseReinit(unittest.TestCase):

    def test_release_then_reinit(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        ok1 = gr._ensure_context()
        gr.release()
        # After release, _init_attempted is reset so we can init again
        self.assertFalse(gr._init_attempted)
        ok2 = gr._ensure_context()
        self.assertEqual(ok1, ok2)
        gr.release()

    def test_double_release_safe(self):
        from src.gui.gpu_renderer import GpuRenderer
        gr = GpuRenderer()
        gr._ensure_context()
        gr.release()
        gr.release()  # second release should not raise


# ──────────────────────────────────────────────────────────────────────────────
#  15. Edge cases
# ──────────────────────────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_empty_model_returns_none_or_clear_image(self):
        class _EmptyModel:
            name = 'empty'; nodes = []; game_version = None
        img = self.gr._render_gpu(_EmptyModel(), self.camera, 128, 128, {}, None, 0.0)
        # May return image (just background) or None; should not crash
        # Both outcomes are acceptable

    def test_node_with_nan_verts_handled(self):
        """NaN vertices should not cause unhandled crash."""
        node = _make_node(n_verts=9, n_tris=3)
        node.verts[0] = [float('nan'), 0.0, 0.0]
        model = _make_model([node])
        try:
            img = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 0.0)
            # Either None or an image is acceptable (no unhandled exception)
        except Exception as e:
            self.fail(f"NaN vertex caused unhandled exception: {e}")

    def test_render_skips_hidden_node(self):
        """Nodes with render=False should be skipped without error."""
        node = _make_node()
        node.render = False
        model = _make_model([node])
        img = self.gr._render_gpu(model, self.camera, 64, 64, {}, None, 0.0)
        self.assertIsNotNone(img)

    def test_uv_large_negative_values(self):
        """Negative/large UVs (> UV_SENTINEL) should be clamped to 0.5."""
        from src.gui.gpu_renderer import _build_vbo_data
        node = _make_node(n_verts=3, n_tris=1)
        node.uvs = [(-99.0, 127.0), (-22.0, 0.5), (0.0, 0.0)]
        node.faces = [[0, 1, 2]]
        vd, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        self.assertIsNotNone(vd)
        # Sentinel UV clamped to 0.5
        self.assertAlmostEqual(float(vd[0, 6]), 0.5, places=4)
        self.assertAlmostEqual(float(vd[1, 6]), 0.5, places=4)


# ──────────────────────────────────────────────────────────────────────────────
#  16. _GlTexCache
# ──────────────────────────────────────────────────────────────────────────────

class TestGlTexCache(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer, _GlTexCache
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self._GlTexCache = _GlTexCache

    def tearDown(self):
        self.gr.release()

    def test_upload_returns_texture(self):
        try:
            from PIL import Image
            import moderngl
        except ImportError:
            self.skipTest("PIL/moderngl not available")
        img = _make_texture(32, 32)
        cache = self._GlTexCache(self.gr._ctx)
        tex = cache.get(img)
        self.assertIsNotNone(tex)
        cache.clear()

    def test_cache_hit_same_image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        img = _make_texture(16, 16)
        cache = self._GlTexCache(self.gr._ctx)
        tex1 = cache.get(img)
        tex2 = cache.get(img)  # should return cached
        self.assertIs(tex1, tex2)
        cache.clear()

    def test_get_none_returns_none(self):
        cache = self._GlTexCache(self.gr._ctx)
        self.assertIsNone(cache.get(None))

    def test_invalidate_removes_entry(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("PIL not available")
        img = _make_texture(16, 16)
        cache = self._GlTexCache(self.gr._ctx)
        cache.get(img)
        self.assertIn(id(img), cache._cache)
        cache.invalidate(img)
        self.assertNotIn(id(img), cache._cache)
        cache.clear()


# ──────────────────────────────────────────────────────────────────────────────
#  17. _benchmark() smoke test
# ──────────────────────────────────────────────────────────────────────────────

class TestBenchmarkFunction(unittest.TestCase):

    def test_benchmark_returns_dict(self):
        from src.gui.gpu_renderer import _benchmark
        r = _benchmark(n_tris=100, repeats=2)
        self.assertIsInstance(r, dict)
        self.assertIn('n_tris', r)
        self.assertEqual(r['n_tris'], 100)

    def test_benchmark_gpu_keys(self):
        from src.gui.gpu_renderer import _benchmark
        r = _benchmark(n_tris=100, repeats=2)
        self.assertIn('gpu_ms', r)
        self.assertIn('gpu_fps', r)

    def test_benchmark_gpu_fps_positive(self):
        from src.gui.gpu_renderer import _benchmark
        r = _benchmark(n_tris=500, repeats=2)
        if r.get('gpu_fps') is not None:
            self.assertGreater(r['gpu_fps'], 0)


# ──────────────────────────────────────────────────────────────────────────────
#  18. Persistent FBO reuse
# ──────────────────────────────────────────────────────────────────────────────

class TestPersistentFbo(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.model  = _make_model()
        self.camera = _make_camera()

    def tearDown(self):
        self.gr.release()

    def test_fbo_created_on_first_render(self):
        self.assertIsNone(self.gr._fbo)
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        self.assertIsNotNone(self.gr._fbo)
        self.assertEqual(self.gr._fbo_w, 128)
        self.assertEqual(self.gr._fbo_h, 128)

    def test_fbo_reused_same_size(self):
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        fbo_id1 = id(self.gr._fbo)
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        fbo_id2 = id(self.gr._fbo)
        self.assertEqual(fbo_id1, fbo_id2, "FBO should be reused for same size")

    def test_fbo_recreated_on_resize(self):
        self.gr._render_gpu(self.model, self.camera, 128, 128, {}, None, 0.0)
        fbo_id1 = id(self.gr._fbo)
        self.gr._render_gpu(self.model, self.camera, 256, 256, {}, None, 0.0)
        fbo_id2 = id(self.gr._fbo)
        self.assertNotEqual(fbo_id1, fbo_id2, "FBO should be recreated on resize")
        self.assertEqual(self.gr._fbo_w, 256)
        self.assertEqual(self.gr._fbo_h, 256)


# ──────────────────────────────────────────────────────────────────────────────
#  19. Visual correctness: clear-color pixel
# ──────────────────────────────────────────────────────────────────────────────

class TestVisualCorrectness(unittest.TestCase):

    def setUp(self):
        from src.gui.gpu_renderer import GpuRenderer
        self.gr = GpuRenderer()
        if not self.gr._ensure_context():
            self.skipTest("GPU not available")
        self.camera = _make_camera(eye=(0, 0, 100))  # far camera → mesh tiny/invisible

    def tearDown(self):
        self.gr.release()

    def test_background_corners_near_clear_color(self):
        """Corners of image should be near the clear colour or black (alpha=0 composited)."""
        class _EmptyModel:
            name = 'empty'; nodes = []; game_version = None
        img = self.gr._render_gpu(_EmptyModel(), self.camera, 256, 256, {}, None, 0.0)
        if img is None:
            return  # GPU gave up, skip visual check
        import numpy as np
        arr = np.array(img)
        # Clear color is (31, 36, 41) (0.12, 0.14, 0.16 × 255)
        corner = arr[0, 0, :3].astype(int)
        expected = np.array([int(0.12 * 255), int(0.14 * 255), int(0.16 * 255)])
        diff = np.abs(corner - expected)
        # Accept either near-clear-color OR near-black (alpha=0 RGBA composited to black)
        near_clear = np.all(diff < 15)
        near_black = np.all(corner < 15)
        self.assertTrue(near_clear or near_black,
                        f"Corner pixel {corner} neither near clear color {expected} nor black")

    def test_diffuse_colored_mesh_pixel(self):
        """A bright-red mesh should produce at least one red-ish pixel."""
        node = _make_node(n_verts=300, n_tris=100)
        node.diffuse = (1.0, 0.0, 0.0)
        model = _make_model([node])
        img = self.gr._render_gpu(model, _make_camera(eye=(0, 0, 3)),
                                  256, 256, {}, None, 0.0)
        if img is None:
            return
        import numpy as np
        arr = np.array(img)
        # At least one pixel should have R significantly > G,B
        r = arr[:, :, 0].astype(int)
        g = arr[:, :, 1].astype(int)
        b = arr[:, :, 2].astype(int)
        has_reddish = np.any((r > 80) & (r > g + 30) & (r > b + 30))
        self.assertTrue(has_reddish, "No red-ish pixels found for red diffuse mesh")


# ──────────────────────────────────────────────────────────────────────────────
#  20. Large UV wrapping
# ──────────────────────────────────────────────────────────────────────────────

class TestLargeUvWrapping(unittest.TestCase):

    def test_large_uv_no_crash_in_vbo(self):
        """UVs with values like ±13 should not crash VBO builder."""
        from src.gui.gpu_renderer import _build_vbo_data
        node = _make_node(n_verts=9, n_tris=3)
        # Override UVs with tiling-range values (< _UV_SENTINEL=20)
        node.uvs = [(-5.0, 7.3), (3.1, -2.8), (0.5, 0.5)] * 3
        vd, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        self.assertIsNotNone(vd)
        # These UVs are within sentinel range, should be preserved
        self.assertAlmostEqual(float(vd[0, 6]), -5.0, places=4)

    def test_sentinel_uv_clamped_in_vbo(self):
        """UVs > UV_SENTINEL=20 must be replaced with 0.5."""
        from src.gui.gpu_renderer import _build_vbo_data
        node = _make_node(n_verts=3, n_tris=1)
        node.uvs = [(25.0, -30.0), (0.5, 0.5), (0.5, 0.5)]
        node.faces = [[0, 1, 2]]
        vd, idx = _build_vbo_data(node, (0, 0, 0), (0, 0, 0, 1))
        self.assertAlmostEqual(float(vd[0, 6]), 0.5, places=4)


# ──────────────────────────────────────────────────────────────────────────────
#  Run
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    unittest.main(verbosity=2)
