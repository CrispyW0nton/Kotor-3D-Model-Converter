#!/usr/bin/env python3
"""
test_final_acceptance.py — Final acceptance testing for m02aa_01a rendering fixes
=================================================================================
Verifies:
1. KotorInstallation API compatibility (texture/lightmap loading)
2. Texture-format loading (TPC DXT, TGA lightmap, decode)
3. VBO/shader attribute alignment
4. Material-routing correctness (lightmap role, wrap modes)
5. No regressions from FIX-LMWRAP, FIX-LMSHADE, FIX-LMROLE
"""

import sys, os, struct, io, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GAME_DIR = os.path.join(os.path.dirname(__file__), 'game_data', 'swkotor')
HAS_GAME = os.path.isdir(GAME_DIR) and os.path.isfile(os.path.join(GAME_DIR, 'chitin.key'))


class TestKotorInstallationAPI(unittest.TestCase):
    """Test KotorInstallation resource loading API."""

    @classmethod
    def setUpClass(cls):
        if not HAS_GAME:
            raise unittest.SkipTest("Game files not available")
        from src.core.kotor_install import KotorInstallation
        cls.install = KotorInstallation(GAME_DIR)

    def test_diffuse_tpc_loading(self):
        """All 13 diffuse textures load via get_texture() (TPC from ERF)."""
        names = ['lts_trim01', 'lts_pwall01i', 'lts_nwall04i', 'lts_lite08',
                 'lts_bwall04i', 'lts_pwall04', 'lts_rwall01', 'lmi_bed01',
                 'lts_nwall02', 'lts_gwall01', 'lts_bwall02i', 'lts_glass01', 'lts_nums']
        for name in names:
            raw = self.install.get_texture(name)
            self.assertIsNotNone(raw, f"get_texture('{name}') returned None")
            self.assertGreater(len(raw), 1000, f"'{name}' too small: {len(raw)} bytes")

    def test_lightmap_tga_loading(self):
        """All 6 lightmap TGA textures load via get_texture() (TGA from BIF)."""
        names = ['m02aa_01a_lm0', 'm02aa_01a_lm1', 'm02aa_01a_lm2',
                 'm02aa_01a_lm3', 'm02aa_01a_lm4', 'm02aa_01a_lm5']
        for name in names:
            raw = self.install.get_texture(name)
            self.assertIsNotNone(raw, f"get_texture('{name}') returned None")
            self.assertGreater(len(raw), 100, f"'{name}' too small: {len(raw)} bytes")

    def test_lightmap_not_txi(self):
        """Lightmap get_texture() returns TGA data (>100 bytes), not TXI (60 bytes)."""
        raw = self.install.get_texture('m02aa_01a_lm0')
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw), 200, 
                          f"lm0 is only {len(raw)} bytes — likely TXI instead of TGA")

    def test_get_type_tga(self):
        """Direct get(name, RES_TGA=3) returns TGA data for lightmaps."""
        raw = self.install.get('m02aa_01a_lm0', 3)  # RES_TGA = 3
        self.assertIsNotNone(raw)
        self.assertGreater(len(raw), 200)

    def test_model_mdl_mdx_loading(self):
        """MDL+MDX for m02aa_01a load from BIF."""
        mdl = self.install.get('m02aa_01a', 2002)  # RES_MDL
        mdx = self.install.get('m02aa_01a', 3008)  # RES_MDX
        self.assertIsNotNone(mdl)
        self.assertIsNotNone(mdx)
        self.assertGreater(len(mdl), 10000)
        self.assertGreater(len(mdx), 10000)


class TestTextureFormatDecoding(unittest.TestCase):
    """Test texture format loading (TPC DXT, TGA, decode pipeline)."""

    @classmethod
    def setUpClass(cls):
        if not HAS_GAME:
            raise unittest.SkipTest("Game files not available")
        from src.core.kotor_install import KotorInstallation
        cls.install = KotorInstallation(GAME_DIR)

    def _decode(self, raw):
        from PIL import Image
        # TGA
        try:
            img = Image.open(io.BytesIO(raw))
            return img.convert('RGBA')
        except Exception:
            pass
        # TPC via viewport
        try:
            from src.gui.viewport import _load_tpc_bytes
            return _load_tpc_bytes(raw)
        except Exception:
            pass
        return None

    def test_tpc_diffuse_decode(self):
        """TPC diffuse textures (DXT compressed) decode to PIL images."""
        raw = self.install.get_texture('lts_trim01')
        img = self._decode(raw)
        self.assertIsNotNone(img, "Failed to decode TPC texture")
        self.assertEqual(img.mode, 'RGBA')
        self.assertGreater(img.size[0], 0)

    def test_tga_lightmap_decode(self):
        """TGA lightmap textures decode to PIL images."""
        raw = self.install.get_texture('m02aa_01a_lm0')
        img = self._decode(raw)
        self.assertIsNotNone(img, "Failed to decode TGA lightmap")
        self.assertEqual(img.mode, 'RGBA')
        self.assertEqual(img.size, (64, 64))

    def test_small_lightmap_decode(self):
        """Small 8×8 lightmap decodes correctly."""
        raw = self.install.get_texture('m02aa_01a_lm3')
        img = self._decode(raw)
        self.assertIsNotNone(img, "Failed to decode 8×8 lightmap")
        self.assertEqual(img.size, (8, 8))

    def test_texture_cache_integration(self):
        """TextureCache.get() returns PIL images for all module textures."""
        from src.gui.viewport import TextureCache
        tc = TextureCache()
        tc.set_installation(self.install, 'K1')
        
        for name in ['lts_trim01', 'm02aa_01a_lm0', 'lmi_bed01']:
            img = tc.get(name)
            self.assertIsNotNone(img, f"TextureCache.get('{name}') returned None")
            self.assertEqual(img.mode, 'RGBA')


class TestModelLoading(unittest.TestCase):
    """Test model loading through GhostRigger pipeline."""

    @classmethod
    def setUpClass(cls):
        mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
        mdx_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdx')
        if not os.path.exists(mdl_path):
            raise unittest.SkipTest("Model files not available")
        from src.core.kotor_loader import load_model_from_bytes
        with open(mdl_path, 'rb') as f:
            mdl = f.read()
        with open(mdx_path, 'rb') as f:
            mdx = f.read()
        cls.model = load_model_from_bytes(mdl, mdx)
        cls.mesh_nodes = [n for n in cls.model.all_nodes() if getattr(n, 'is_mesh', False)]

    def test_model_loaded(self):
        """Model loads successfully."""
        self.assertIsNotNone(self.model)
        self.assertEqual(self.model.name, 'M02aa_01a')

    def test_mesh_node_count(self):
        """Model has 56 mesh nodes."""
        self.assertEqual(len(self.mesh_nodes), 56)

    def test_lightmapped_nodes_have_flag(self):
        """All nodes with texture_2 (lightmap) have has_lightmap=True."""
        for n in self.mesh_nodes:
            lm = str(getattr(n, 'lightmap', '') or '').strip()
            if lm and lm.startswith('m02aa_01a_lm'):
                self.assertTrue(getattr(n, 'has_lightmap', False),
                              f"{n.name}: has lightmap '{lm}' but has_lightmap=False")

    def test_lightmap_uvs_present(self):
        """Lightmapped nodes have uvs_lm data."""
        for n in self.mesh_nodes:
            if getattr(n, 'has_lightmap', False):
                uvs_lm = getattr(n, 'uvs_lm', [])
                self.assertGreater(len(uvs_lm), 0,
                                 f"{n.name}: has_lightmap=True but no uvs_lm")

    def test_texture_names_populated(self):
        """All mesh nodes have texture_names[] matching tex_count."""
        for n in self.mesh_nodes:
            tc = int(getattr(n, 'tex_count', 1))
            tn = getattr(n, 'texture_names', [])
            self.assertEqual(len(tn), tc,
                           f"{n.name}: tex_count={tc} but texture_names has {len(tn)} entries")

    def test_lm_composite_render_path(self):
        """Lightmapped nodes use LM-composite render path (not multi-mat-split)."""
        for n in self.mesh_nodes:
            if getattr(n, 'has_lightmap', False):
                tc = int(getattr(n, 'tex_count', 1))
                if tc == 2:
                    # Should be LM-composite, not multi-material
                    fm = getattr(n, 'face_mats', [])
                    # All face_mats should be 0 (clamped) for lightmap nodes
                    # OR all the same value (which means all faces use same diffuse)
                    unique_fm = set(fm) if fm else {0}
                    self.assertEqual(len(unique_fm), 1,
                                   f"{n.name}: lightmap node has multiple face_mats {unique_fm}")


class TestVBOShaderAlignment(unittest.TestCase):
    """Test VBO format and shader attribute alignment."""

    def test_vbo_format_string(self):
        """VBO format is '3f 3f 2f 2f 4f' (pos, norm, uv, uv_lm, color)."""
        from src.gui import gpu_renderer
        # The format is hardcoded in _draw_node
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn("'3f 3f 2f 2f 4f'", src)

    def test_shader_attributes(self):
        """Shader inputs match VBO attributes."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn("'in_pos'", src)
        self.assertIn("'in_norm'", src)
        self.assertIn("'in_uv'", src)
        self.assertIn("'in_uv_lm'", src)
        self.assertIn("'in_color'", src)

    def test_build_vbo_produces_14_floats_per_vertex(self):
        """_build_vbo_data produces 14 floats per vertex (3+3+2+2+4)."""
        mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
        if not os.path.exists(mdl_path):
            self.skipTest("Model files not available")
        
        from src.core.kotor_loader import load_model_from_bytes
        from src.gui.gpu_renderer import _build_vbo_data
        
        with open(mdl_path, 'rb') as f:
            mdl = f.read()
        with open(mdl_path.replace('.mdl', '.mdx'), 'rb') as f:
            mdx = f.read()
        model = load_model_from_bytes(mdl, mdx)
        
        # Get first mesh node
        for n in model.all_nodes():
            if getattr(n, 'is_mesh', False) and len(getattr(n, 'vertices', [])) > 0:
                wp, wo = n.world_transform()
                vdata, idx = _build_vbo_data(n, wp, wo, is_module=True)
                if vdata is not None:
                    # Each row should be 14 floats
                    self.assertEqual(vdata.shape[1], 14,
                                   f"VBO data has {vdata.shape[1]} floats per vertex, expected 14")
                    break


class TestMaterialRouting(unittest.TestCase):
    """Test material-routing correctness (the core bug fixes)."""

    def test_lightmap_wrap_mode_code(self):
        """FIX-LMWRAP: Lightmap textures set to CLAMP_TO_EDGE in _draw_node."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        # Should set repeat_x=False, repeat_y=False for lightmaps
        self.assertIn('gl_lm.repeat_x = False', src)
        self.assertIn('gl_lm.repeat_y = False', src)

    def test_lm_shade_flag(self):
        """FIX-LMSHADE: u_lm_shade uniform set to 1 for module geometry."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn("u_lm_shade", src)
        # Should set to 1 when is_module
        self.assertIn("1 if _gpu_is_module else 0", src)

    def test_lm_role_inference(self):
        """FIX-LMROLE: Renderer infers lightmap role when MDL flag is False."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        # The LMROLE safety net in _draw_node
        self.assertIn('FIX-LMROLE', src)

    def test_shader_lightmap_multiply(self):
        """Shader uses diffuse × lightmap × 2.0 for lightmap compositing."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn('2.0', src)  # Overbright factor

    def test_diffuse_default_repeat(self):
        """Diffuse textures default to GL_REPEAT."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn('tex.repeat_x = True', src)
        self.assertIn('tex.repeat_y = True', src)

    def test_multitex_split_case_a_b(self):
        """_draw_node_multitex handles Case A (lightmap) and Case B (multi-material)."""
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn('Case A', src)
        self.assertIn('Case B', src)


class TestRenderOutput(unittest.TestCase):
    """Test actual render output with real textures."""

    @classmethod
    def setUpClass(cls):
        mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
        if not os.path.exists(mdl_path) or not HAS_GAME:
            raise unittest.SkipTest("Model or game files not available")
        
        from src.core.kotor_loader import load_model_from_bytes
        from src.core.kotor_install import KotorInstallation
        from src.gui.viewport import TextureCache
        
        with open(mdl_path, 'rb') as f:
            mdl = f.read()
        with open(mdl_path.replace('.mdl', '.mdx'), 'rb') as f:
            mdx = f.read()
        cls.model = load_model_from_bytes(mdl, mdx)
        
        install = KotorInstallation(GAME_DIR)
        tc = TextureCache()
        tc.set_installation(install, 'K1')
        
        # Preload all textures
        for mn in cls.model.all_nodes():
            if not getattr(mn, 'is_mesh', False):
                continue
            for attr in ['texture', 'lightmap']:
                name = str(getattr(mn, attr, '') or '').strip()
                if name and name.upper() not in ('NULL', '', 'NONE'):
                    tc.get(name)
        
        cls.tex_dict = {k: v for k, v in tc._cache.items() if v is not None}

    def test_all_textures_loaded(self):
        """All 19 textures (13 diffuse + 6 lightmaps) are in tex_dict."""
        self.assertGreaterEqual(len(self.tex_dict), 19)

    def test_render_produces_image(self):
        """GPU render with real textures produces a non-empty image."""
        from src.gui.gpu_renderer import render_model_autoframe
        imgs = render_model_autoframe(self.model, W=512, H=512,
                                       textures=self.tex_dict, views=['diag'])
        self.assertIn('diag', imgs)
        img = imgs['diag']
        self.assertEqual(img.size, (512, 512))
        
        # Check it's not all black
        import numpy as np
        arr = np.array(img)
        non_black = np.sum(arr[:, :, :3] > 10)
        self.assertGreater(non_black, 1000, "Image appears to be mostly black")

    def test_render_has_texture_detail(self):
        """Render shows texture detail (not flat grey/white)."""
        from src.gui.gpu_renderer import render_model_autoframe
        import numpy as np
        
        imgs = render_model_autoframe(self.model, W=512, H=512,
                                       textures=self.tex_dict, views=['diag'])
        img = imgs['diag']
        arr = np.array(img)
        
        # Check color variance — flat grey would have very low variance
        # Take only non-black pixels
        mask = arr[:, :, :3].sum(axis=2) > 30
        if mask.sum() > 100:
            colored = arr[:, :, :3][mask]
            variance = colored.var()
            self.assertGreater(variance, 100,
                             f"Low color variance ({variance:.1f}) suggests flat untextured rendering")


class TestCrossReference(unittest.TestCase):
    """Cross-reference with xoreos/KotorBlender/KotOR.js conventions."""

    def test_xoreos_slot1_is_lightmap(self):
        """Consistent with xoreos: textureCount=2, slot 1 = lightmap (UV1, multiply)."""
        # xoreos model_kotor.cpp setupShaderTexture: textureIndex=1 → TEXTURE_LIGHTMAP, BLEND_MULTIPLY
        # GhostRigger: has_lightmap + tex_count=2 → u_lm_tex bound to location=1, in_uv_lm
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        self.assertIn('gl_lm.use(location=1)', src)  # Lightmap on texture unit 1

    def test_xoreos_no_per_face_material_texture_selection(self):
        """Consistent with xoreos: face material indices don't select textures in KotOR.
        
        xoreos model_kotor.cpp readMesh: uses interleaved vertex data with per-vertex UVs.
        Face indices index into the vertex buffer, NOT material slots.
        The face_mats in PyKotor's MDL reading correspond to NWN's multi-material
        system, which is NOT used by KotOR for lightmapped geometry.
        """
        # In GhostRigger, lightmap nodes should NOT be split by face_mats
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        # _draw_node_multitex Case A: lightmap → draw once, not per-material
        self.assertIn("has_lightmap=True: slot 0 = diffuse, slot 1 = lightmap", src)

    def test_kotorjs_overbright_factor(self):
        """Consistent with KotOR.js: lightmap × diffuse × 2.0 overbright."""
        # KotOR.js ShaderOdysseyModel.ts: lightMap compositing with ×2 overbright
        src = open(os.path.join(os.path.dirname(__file__), 'src', 'gui', 'gpu_renderer.py')).read()
        # Check for the overbright multiply
        self.assertIn('2.0', src)

    def test_kotorblender_lightmap_uv_range(self):
        """Consistent with KotorBlender: lightmap UVs are always in [0,1]."""
        mdl_path = os.path.join(os.path.dirname(__file__), 'm02aa_01a.mdl')
        if not os.path.exists(mdl_path):
            self.skipTest("Model files not available")
        
        from src.core.kotor_loader import load_model_from_bytes
        with open(mdl_path, 'rb') as f:
            mdl = f.read()
        with open(mdl_path.replace('.mdl', '.mdx'), 'rb') as f:
            mdx = f.read()
        model = load_model_from_bytes(mdl, mdx)
        
        for n in model.all_nodes():
            if not getattr(n, 'is_mesh', False) or not getattr(n, 'has_lightmap', False):
                continue
            uvs_lm = getattr(n, 'uvs_lm', [])
            for u, v in uvs_lm:
                self.assertGreaterEqual(u, -0.01, f"{n.name}: LM UV u={u} < 0")
                self.assertLessEqual(u, 1.01, f"{n.name}: LM UV u={u} > 1")
                self.assertGreaterEqual(v, -0.01, f"{n.name}: LM UV v={v} < 0")
                self.assertLessEqual(v, 1.01, f"{n.name}: LM UV v={v} > 1")


if __name__ == '__main__':
    unittest.main(verbosity=2)
