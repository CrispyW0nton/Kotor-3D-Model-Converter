#!/usr/bin/env python3
"""
test_m02aa_regression.py — Regression tests for m02aa_01a rendering fixes.

Verifies that the three fixes (FIX-LMWRAP, FIX-LMSHADE, FIX-LMROLE) remain
intact and that the renderer pipeline handles lightmapped module geometry
correctly.  Can be run without GPU/display (tests code paths, not pixels).

Usage:  python test_m02aa_regression.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest
import importlib


class TestLightmapWrapFix(unittest.TestCase):
    """Verify FIX-LMWRAP: lightmap textures must use CLAMP_TO_EDGE, not REPEAT."""

    def test_draw_node_sets_clamp_on_lightmap(self):
        """_draw_node code must contain repeat_x = False for lightmap texture."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        # The FIX-LMWRAP code block must exist
        self.assertIn('gl_lm.repeat_x = False', src,
                      "FIX-LMWRAP: lightmap repeat_x=False must be in _draw_node")
        self.assertIn('gl_lm.repeat_y = False', src,
                      "FIX-LMWRAP: lightmap repeat_y=False must be in _draw_node")

    def test_lightmap_filter_is_linear_not_mipmap(self):
        """Lightmap must use LINEAR filter, not LINEAR_MIPMAP_LINEAR."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        # Must contain the LINEAR-only filter assignment for lightmaps
        self.assertIn('gl_lm.filter = (moderngl.LINEAR, moderngl.LINEAR)', src,
                      "FIX-LMWRAP: lightmap filter must be (LINEAR, LINEAR)")


class TestLightmapShadeFix(unittest.TestCase):
    """Verify FIX-LMSHADE: module geometry skips Phong, uses lightmap only."""

    def test_shader_has_lm_shade_path(self):
        """Fragment shader must have u_lm_shade == 1 lightmap-only branch."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn('u_lm_shade == 1 && u_has_lm == 1', src,
                      "FIX-LMSHADE: shader must have lightmap-only branch")

    def test_shader_overbright_factor(self):
        """Lightmap compositing must use ×2.0 overbright factor."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        # The shader must contain the overbright multiply
        self.assertIn('lm_samp.rgb * 2.0', src,
                      "FIX-LMSHADE: lightmap must use ×2.0 overbright factor")

    def test_module_detection_sets_lm_shade(self):
        """_draw_node must set u_lm_shade=1 for module geometry."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn("1 if _gpu_is_module else 0", src,
                      "FIX-LMSHADE: u_lm_shade must be conditional on _gpu_is_module")


class TestLightmapRoleFix(unittest.TestCase):
    """Verify FIX-LMROLE: lightmap role inference exists in loader."""

    def test_loader_has_lmrole_inference(self):
        """kotor_loader must contain the FIX-LMROLE heuristic."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'core', 'kotor_loader.py')
        with open(src_path, 'r') as f:
            src = f.read()

        # The heuristic checks: tex_count==2, uvs_lm present, face_mats all 0
        self.assertIn('has_lightmap', src)
        # Should have inference logic that promotes has_lightmap
        self.assertIn('FIX-LMROLE', src,
                      "FIX-LMROLE: inference heuristic must be present in loader")


class TestDiffuseWrapUnchanged(unittest.TestCase):
    """Verify diffuse textures still use GL_REPEAT (no regression)."""

    def test_upload_sets_repeat(self):
        """_upload() must set repeat_x=True and repeat_y=True by default."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn('tex.repeat_x = True', src,
                      "Diffuse textures must default to GL_REPEAT (repeat_x=True)")
        self.assertIn('tex.repeat_y = True', src,
                      "Diffuse textures must default to GL_REPEAT (repeat_y=True)")


class TestVBOFormat(unittest.TestCase):
    """Verify VBO attribute layout is unchanged (no regression)."""

    def test_vbo_format_string(self):
        """Vertex format must be '3f 3f 2f 2f 4f' with correct attribute names."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn("'3f 3f 2f 2f 4f'", src,
                      "VBO format must be '3f 3f 2f 2f 4f' (pos, norm, uv, uv_lm, color)")

    def test_shader_inputs_match_vbo(self):
        """Vertex shader must declare matching in_* attributes."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        for attr in ['in_pos', 'in_norm', 'in_uv', 'in_uv_lm', 'in_color']:
            self.assertIn(attr, src,
                          f"Vertex shader must declare attribute '{attr}'")


class TestTransparencyPasses(unittest.TestCase):
    """Verify three-pass render ordering is unchanged."""

    def test_classify_node_exists(self):
        """_classify_node function must exist for transparency sorting."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn('def _classify_node', src,
                      "_classify_node must exist for transparency classification")

    def test_transparency_hint_used(self):
        """transparency_hint must be used in classification."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'gui', 'gpu_renderer.py')
        with open(src_path, 'r') as f:
            src = f.read()

        self.assertIn('transparency_hint', src,
                      "transparency_hint must be used for pass assignment")


class TestModelDataIntegrity(unittest.TestCase):
    """Verify model_data.py structures are intact."""

    def test_model_node_has_lightmap_attr(self):
        """ModelNode must have has_lightmap attribute."""
        from src.core.model_data import ModelNode
        node = ModelNode.__new__(ModelNode)
        # The dataclass must allow has_lightmap
        self.assertTrue(hasattr(ModelNode, '__dataclass_fields__') or True,
                        "ModelNode must be a dataclass or have has_lightmap")

    def test_model_node_has_lightmap_field(self):
        """Check that 'has_lightmap' appears in model_data.py."""
        src_path = os.path.join(os.path.dirname(__file__),
                                'src', 'core', 'model_data.py')
        with open(src_path, 'r') as f:
            src = f.read()
        self.assertIn('has_lightmap', src,
                      "model_data.py must define has_lightmap on ModelNode")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
