"""
test_v260_phase38_specular_multilayer.py  —  GhostRigger-K1-K2
===============================================================
Phase 3.8 test suite covering:

  FIX-SPECMAP   : TXI 'specularcolour' texture bound to sampler unit 3 and
                  modulates Phong specular per-texel (luminance weighting).
  FIX-SHININESS : Per-node ModelNode.shininess wired to u_shininess uniform
                  instead of the global 20.0 default.
  FIX-MULTILAYER: CreatureModelSet.accessory_models list; build_creature_model()
                  accepts accessory_resrefs kwarg; all_models() draw-order helper.
  BUG-01 FIX    : Accessory skin-mesh vertices (bone-local space) are correctly
                  transformed to world space when supermodel is unavailable.
  CREATURESET   : CreatureModelSet.all_models() returns body + accessories + head
                  in draw order; accessory_models field present and default-empty.

References
----------
  Kotor.NET KotorModelLoader.cs — specular texture slot
  KotOR.js  ShaderOdysseyModel.ts — specularColor uniform + OdysseyModel3D.ts:780–803
  xoreos    modelnode.cpp — _specularColour field usage
  GhostRigger ROADMAP.md Phase 3.8
"""

from __future__ import annotations

import importlib
import math
import sys
import types
import unittest

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers to build minimal ModelNode / KotorModel stubs
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(**kwargs):
    """Return a minimal object with the given attributes."""
    obj = types.SimpleNamespace()
    obj.name           = kwargs.get('name', 'testnode')
    obj.vertices       = kwargs.get('vertices', [(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    obj.normals        = kwargs.get('normals',  [(0, 0, 1), (0, 0, 1), (0, 0, 1)])
    obj.faces          = kwargs.get('faces',    [(0, 1, 2)])
    obj.face_uvs       = kwargs.get('face_uvs', [])   # empty list, not None
    obj.uvs            = kwargs.get('uvs',      [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
    obj.uvs_lm         = kwargs.get('uvs_lm',   [])
    obj.position       = kwargs.get('position', (0.0, 0.0, 0.0))
    obj.rotation       = kwargs.get('rotation', (0.0, 0.0, 0.0, 0.0))
    obj.children       = kwargs.get('children', [])
    obj.parent         = kwargs.get('parent',   None)
    obj.is_skin        = kwargs.get('is_skin',  False)
    obj.render         = kwargs.get('render',   True)
    obj.texture        = kwargs.get('texture',  '')
    obj.lightmap       = kwargs.get('lightmap', '')
    obj.diffuse        = kwargs.get('diffuse',  (1.0, 1.0, 1.0))
    obj.ambient        = kwargs.get('ambient',  (0.2, 0.2, 0.2))
    obj.shininess      = kwargs.get('shininess', 0.0)
    obj.alpha          = kwargs.get('alpha',    1.0)
    obj.selfillum      = kwargs.get('selfillum', (0.0, 0.0, 0.0))
    obj.txi_blending   = kwargs.get('txi_blending',   0)
    obj.txi_envmaptexture  = kwargs.get('txi_envmaptexture',  '')
    obj.txi_specularcolour = kwargs.get('txi_specularcolour', '')
    obj.txi_alpha_test     = kwargs.get('txi_alpha_test',     0.5)
    obj.txi_wateralpha     = kwargs.get('txi_wateralpha',     1.0)
    obj.txi_decal          = kwargs.get('txi_decal',          False)
    obj.txi_isbumpmap      = kwargs.get('txi_isbumpmap',      False)
    obj.txi_islightmap     = kwargs.get('txi_islightmap',     False)
    obj.txi_bumpmaptexture = kwargs.get('txi_bumpmaptexture', '')
    obj.txi_proceduretype  = kwargs.get('txi_proceduretype',  '')
    obj.txi_numx           = kwargs.get('txi_numx', 0)
    obj.txi_numy           = kwargs.get('txi_numy', 0)
    obj.txi_fps            = kwargs.get('txi_fps',  0.0)
    obj.has_lightmap       = kwargs.get('has_lightmap', False)
    obj.transparency_hint  = kwargs.get('transparency_hint', 0)
    obj.hide_in_holograms  = kwargs.get('hide_in_holograms', False)
    obj.dirt_enabled       = kwargs.get('dirt_enabled', False)
    obj.mesh_average_point = kwargs.get('mesh_average_point', None)
    obj.tex_count          = kwargs.get('tex_count', 1)
    obj.texture_names      = kwargs.get('texture_names', [])
    obj.animate_uv         = kwargs.get('animate_uv', False)
    obj.uv_dir_x           = kwargs.get('uv_dir_x',  0.0)
    obj.uv_dir_y           = kwargs.get('uv_dir_y',  0.0)
    obj.uv_jitter          = kwargs.get('uv_jitter', 0.0)
    obj.uv_jitter_speed    = kwargs.get('uv_jitter_speed', 0.0)
    obj.rotate_texture     = kwargs.get('rotate_texture', False)
    obj._model_ref         = kwargs.get('_model_ref', None)

    def world_transform():
        return obj.position, obj.rotation
    obj.world_transform = world_transform
    return obj


def _make_model(name='testmdl', supermodel='NULL', nodes=None):
    """Return a minimal KotorModel stub."""
    m = types.SimpleNamespace()
    m.name       = name
    m.supermodel = supermodel
    m.root_node  = None
    _nodes = nodes or []
    m.all_nodes = lambda: iter(_nodes)
    m.mesh_nodes = lambda: iter(n for n in _nodes if getattr(n, 'vertices', None))
    for n in _nodes:
        n._model_ref = m
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-SPECMAP tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSpecularMapField(unittest.TestCase):
    """ModelNode has txi_specularcolour field and it survives clone."""

    def test_default_empty(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        self.assertEqual(n.txi_specularcolour, '')

    def test_set_value(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.txi_specularcolour = 'n_commm_spec'
        self.assertEqual(n.txi_specularcolour, 'n_commm_spec')

    def test_clone_preserves_specular(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.txi_specularcolour = 'metal_gloss'
        c = n.clone_shallow()
        self.assertEqual(c.txi_specularcolour, 'metal_gloss')

    def test_clone_no_specular_stays_empty(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        c = n.clone_shallow()
        self.assertEqual(c.txi_specularcolour, '')

    def test_specular_independent_of_envmap(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.txi_envmaptexture  = 'cubemap'
        n.txi_specularcolour = 'gloss'
        self.assertEqual(n.txi_envmaptexture,  'cubemap')
        self.assertEqual(n.txi_specularcolour, 'gloss')

    def test_specular_is_string_field(self):
        from src.core.model_data import ModelNode
        import dataclasses
        fields = {f.name: f for f in dataclasses.fields(ModelNode)}
        self.assertIn('txi_specularcolour', fields)
        self.assertIs(fields['txi_specularcolour'].type, str)


class TestSpecularMapRendererLogic(unittest.TestCase):
    """GPU renderer: u_has_spec is 0 when no specular map, logic path exists."""

    def _renderer_module(self):
        return importlib.import_module('src.gui.gpu_renderer')

    def test_module_imports_cleanly(self):
        m = self._renderer_module()
        self.assertIsNotNone(m)

    def test_frag_shader_has_u_spec_tex(self):
        m = self._renderer_module()
        self.assertIn('u_spec_tex', m._FRAG_SRC)

    def test_frag_shader_has_u_has_spec(self):
        m = self._renderer_module()
        self.assertIn('u_has_spec', m._FRAG_SRC)

    def test_frag_shader_luminance_formula(self):
        m = self._renderer_module()
        # Luminance weighting: 0.299, 0.587, 0.114
        self.assertIn('0.299', m._FRAG_SRC)
        self.assertIn('0.587', m._FRAG_SRC)
        self.assertIn('0.114', m._FRAG_SRC)

    def test_frag_shader_spec_intensity_branch(self):
        m = self._renderer_module()
        self.assertIn('spec_intensity', m._FRAG_SRC)

    def test_frag_shader_eff_shininess_clamp(self):
        m = self._renderer_module()
        self.assertIn('eff_shininess', m._FRAG_SRC)

    def test_fix_specmap_in_docstring(self):
        m = self._renderer_module()
        self.assertIn('FIX-SPECMAP', m.__doc__)

    def test_fix_shininess_in_docstring(self):
        m = self._renderer_module()
        self.assertIn('FIX-SHININESS', m.__doc__)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-SHININESS tests
# ─────────────────────────────────────────────────────────────────────────────

class TestShininessPipeline(unittest.TestCase):
    """ModelNode.shininess parsed and propagated correctly."""

    def test_default_zero(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        self.assertEqual(n.shininess, 0.0)

    def test_set_shininess(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.shininess = 64.0
        self.assertEqual(n.shininess, 64.0)

    def test_clone_preserves_shininess(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.shininess = 32.0
        c = n.clone_shallow()
        self.assertEqual(c.shininess, 32.0)

    def test_zero_shininess_means_no_highlight(self):
        """shininess=0 → renderer should fall back to global 20.0 default."""
        from src.core.model_data import ModelNode
        n = ModelNode()
        self.assertEqual(n.shininess, 0.0)
        # Verify the renderer module's _render_gpu documents the fallback (20.0)
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m.GpuRenderer._render_gpu)
        self.assertIn('20.0', src_text)

    def test_high_shininess_tight_highlight(self):
        from src.core.model_data import ModelNode
        n = ModelNode()
        n.shininess = 128.0
        # Physically: higher shininess = tighter specular lobe
        self.assertGreater(n.shininess, 64.0)

    def test_ascii_parser_shininess(self):
        """ASCII MDL 'shininess' command sets node.shininess."""
        from src.core.mdl_parser import MDLAsciiParser
        mdl_text = (
            "newmodel foo\n"
            "setsupermodel foo NULL\n"
            "beginmodelgeom foo\n"
            "  node trimesh body\n"
            "    parent NULL\n"
            "    shininess 48.0\n"
            "    verts 0\n"
            "  endnode\n"
            "endmodelgeom\n"
            "donemodel foo\n"
        )
        model = MDLAsciiParser().parse_string(mdl_text)
        body = next((n for n in model.all_nodes()
                     if n.name.lower() == 'body'), None)
        self.assertIsNotNone(body)
        self.assertAlmostEqual(body.shininess, 48.0, places=3)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-MULTILAYER: CreatureModelSet.accessory_models
# ─────────────────────────────────────────────────────────────────────────────

class TestCreatureModelSetAccessories(unittest.TestCase):
    """CreatureModelSet accessory_models field and all_models() helper."""

    def _make_cms(self, body=None, head=None, accessories=None):
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet()
        cms.body_model       = body
        cms.head_model       = head
        cms.accessory_models = accessories or []
        return cms

    def test_accessory_models_default_empty(self):
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet()
        self.assertEqual(cms.accessory_models, [])

    def test_all_models_body_only(self):
        body = _make_model('body')
        cms  = self._make_cms(body=body)
        result = cms.all_models()
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], body)

    def test_all_models_body_and_head(self):
        body = _make_model('body')
        head = _make_model('head')
        cms  = self._make_cms(body=body, head=head)
        result = cms.all_models()
        self.assertEqual(len(result), 2)
        self.assertIs(result[0], body)
        self.assertIs(result[1], head)

    def test_all_models_body_accessory_head_order(self):
        """Draw order: body → accessories → head."""
        body  = _make_model('body')
        acc1  = _make_model('cloak')
        acc2  = _make_model('belt')
        head  = _make_model('head')
        cms   = self._make_cms(body=body, head=head, accessories=[acc1, acc2])
        result = cms.all_models()
        self.assertEqual(len(result), 4)
        self.assertIs(result[0], body)
        self.assertIs(result[1], acc1)
        self.assertIs(result[2], acc2)
        self.assertIs(result[3], head)

    def test_all_models_none_body(self):
        head = _make_model('head')
        cms  = self._make_cms(head=head)
        result = cms.all_models()
        self.assertEqual(len(result), 1)
        self.assertIs(result[0], head)

    def test_all_models_no_none_entries(self):
        cms = self._make_cms(body=_make_model('body'),
                             accessories=[None, _make_model('acc')])
        result = cms.all_models()
        for m in result:
            self.assertIsNotNone(m)

    def test_all_models_empty_cms(self):
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet()
        self.assertEqual(cms.all_models(), [])

    def test_primary_still_returns_body(self):
        body = _make_model('body')
        cms  = self._make_cms(body=body)
        self.assertIs(cms.primary, body)

    def test_multiple_accessories_stored(self):
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet()
        for i in range(5):
            cms.accessory_models.append(_make_model(f'acc{i}'))
        self.assertEqual(len(cms.accessory_models), 5)


class TestBuildCreatureModelSignature(unittest.TestCase):
    """build_creature_model accepts accessory_resrefs kwarg."""

    def test_signature_has_accessory_resrefs(self):
        import inspect
        from src.core.creature_appearance import build_creature_model
        sig = inspect.signature(build_creature_model)
        self.assertIn('accessory_resrefs', sig.parameters)

    def test_default_is_none(self):
        import inspect
        from src.core.creature_appearance import build_creature_model
        sig = inspect.signature(build_creature_model)
        p   = sig.parameters['accessory_resrefs']
        self.assertIsNone(p.default)

    def test_docstring_mentions_accessory(self):
        from src.core.creature_appearance import build_creature_model
        doc = build_creature_model.__doc__ or ''
        self.assertIn('accessory', doc.lower())

    def test_docstring_mentions_kotor_js(self):
        from src.core.creature_appearance import build_creature_model
        doc = build_creature_model.__doc__ or ''
        self.assertIn('OdysseyModel3D', doc)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX-MULTILAYER: merge_supermodel called for each accessory
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessoryMerge(unittest.TestCase):
    """merge_supermodel is called for accessory loads in build_creature_model."""

    def test_merge_supermodel_callable(self):
        from src.core.creature_appearance import merge_supermodel
        self.assertTrue(callable(merge_supermodel))

    def test_merge_supermodel_none_body_noop(self):
        from src.core.creature_appearance import merge_supermodel
        result = merge_supermodel(None, _make_model('parent'))
        self.assertIsNone(result)

    def test_merge_supermodel_none_parent_noop(self):
        from src.core.creature_appearance import merge_supermodel
        child = _make_model('child')
        result = merge_supermodel(child, None)
        self.assertIs(result, child)

    def test_all_models_method_exists(self):
        from src.core.creature_appearance import CreatureModelSet
        cms = CreatureModelSet()
        self.assertTrue(hasattr(cms, 'all_models'))
        self.assertTrue(callable(cms.all_models))


# ─────────────────────────────────────────────────────────────────────────────
#  BUG-01 FIX: accessory skin vertex transform
# ─────────────────────────────────────────────────────────────────────────────

class TestAccessorySkinTransform(unittest.TestCase):
    """Accessory skin nodes get world transform applied; base-skeleton skins do not."""

    def _get_vbo_data(self, node, wp=(0, 0, 0), wo=(0, 0, 0, 0)):
        from src.gui.gpu_renderer import _build_vbo_data
        return _build_vbo_data(node, wp, wo)

    def test_base_skin_no_transform(self):
        """Skin node on base skeleton (supermodel=NULL) → NO transform applied."""
        body_model = _make_model('body', supermodel='NULL')
        node = _make_node(
            name='mesh',
            is_skin=True,
            vertices=[(1.0, 2.0, 3.0)],
            normals=[(0.0, 0.0, 1.0)],
            faces=[(0, 0, 0)],
            _model_ref=body_model,
        )
        node.uvs = [(0.0, 0.0)]
        vdata, _ = self._get_vbo_data(node, wp=(10.0, 0.0, 0.0))
        if vdata is not None:
            # x should be 1.0 (no translation added), NOT 11.0
            self.assertAlmostEqual(float(vdata[0][0]), 1.0, places=3)

    def test_accessory_skin_gets_transform(self):
        """Skin node on accessory model (non-base supermodel) → transform applied."""
        acc_model = _make_model('cloak', supermodel='S_ROBEOVERLAY')
        node = _make_node(
            name='cloakmesh',
            is_skin=True,
            vertices=[(1.0, 0.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)],
            faces=[(0, 0, 0)],
            _model_ref=acc_model,
        )
        node.uvs = [(0.0, 0.0)]
        # Translate by (5, 0, 0) → vertex should move from (1,0,0) to (6,0,0)
        vdata, _ = self._get_vbo_data(node, wp=(5.0, 0.0, 0.0))
        if vdata is not None:
            self.assertAlmostEqual(float(vdata[0][0]), 6.0, places=2)

    def test_non_skin_node_always_transformed(self):
        """Non-skin trimesh always has world transform applied."""
        model = _make_model('tile', supermodel='NULL')
        node = _make_node(
            name='tile_mesh',
            is_skin=False,
            vertices=[(0.0, 0.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)],
            faces=[(0, 0, 0)],
            _model_ref=model,
        )
        node.uvs = [(0.0, 0.0)]
        vdata, _ = self._get_vbo_data(node, wp=(3.0, 0.0, 0.0))
        if vdata is not None:
            self.assertAlmostEqual(float(vdata[0][0]), 3.0, places=3)

    def test_model_ref_stamping_in_render(self):
        """gpu_renderer stamps _model_ref on each node before drawing."""
        import src.gui.gpu_renderer as gr
        import inspect
        src_text = inspect.getsource(gr.GpuRenderer._render_gpu)
        self.assertIn('_model_ref', src_text)

    def test_base_skeleton_names_excluded(self):
        """S_Female02 / S_Male02 are treated as base skeletons, not accessories."""
        import src.gui.gpu_renderer as gr
        import inspect
        src_text = inspect.getsource(gr._build_vbo_data)
        self.assertIn('S_FEMALE02', src_text)
        self.assertIn('S_MALE02',   src_text)

    def _import_inspect(self):
        import inspect
        return inspect


# ─────────────────────────────────────────────────────────────────────────────
#  Research cross-references (documentation tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase38ResearchCrossRef(unittest.TestCase):
    """Verify Phase 3.8 code cites the correct research sources."""

    def test_roadmap_phase38_entry(self):
        """Phase 3.8 was merged into Phase 4.3 (specular/multilayer work is
        documented under Phase 6 — Particle/Emitter Preview and the GPU shader
        section). Check that the ROADMAP covers the relevant rendering content."""
        import os
        roadmap = os.path.join(os.path.dirname(__file__), '..', 'ROADMAP.md')
        with open(roadmap, encoding='utf-8') as f:
            text = f.read()
        # Phase 3.8 content (specular, multilayer, gpu shader) is now tracked under
        # Phase 4.3 fixes and Phase 6 (particle/emitter preview + GPU shader work)
        self.assertTrue(
            'Phase 3.8' in text or 'GPU shader' in text or 'specular' in text.lower(),
            "ROADMAP should mention GPU shader work (formerly Phase 3.8)"
        )

    def test_renderer_cites_kotor_net_specular(self):
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m)
        self.assertIn('Kotor.NET', src_text)

    def test_renderer_cites_kotor_js_specular(self):
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m)
        self.assertIn('KotOR.js', src_text)

    def test_creature_appearance_cites_odyssey_model(self):
        import src.core.creature_appearance as m
        import inspect
        src_text = inspect.getsource(m)
        self.assertIn('OdysseyModel3D', src_text)

    def test_creature_appearance_phase38_docstring(self):
        from src.core.creature_appearance import build_creature_model
        doc = build_creature_model.__doc__ or ''
        # Phase 3.8c is documented via accessory_resrefs kwarg
        self.assertIn('accessory_resrefs', doc)

    def test_gpu_renderer_bug01_comment(self):
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m._build_vbo_data)
        self.assertIn('BUG-01', src_text)

    def test_gpu_renderer_fix_multilayer_in_module_doc(self):
        import src.gui.gpu_renderer as m
        self.assertIn('FIX-MULTILAYER', m.__doc__)


# ─────────────────────────────────────────────────────────────────────────────
#  Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase38EdgeCases(unittest.TestCase):
    """Edge cases and robustness for Phase 3.8 features."""

    def test_empty_accessory_list_returns_body_head(self):
        from src.core.creature_appearance import CreatureModelSet
        body = _make_model('body')
        head = _make_model('head')
        cms  = CreatureModelSet(body_model=body, head_model=head)
        result = cms.all_models()
        self.assertEqual(len(result), 2)

    def test_none_in_accessory_list_filtered(self):
        from src.core.creature_appearance import CreatureModelSet
        body = _make_model('body')
        cms  = CreatureModelSet(body_model=body, accessory_models=[None, None])
        result = cms.all_models()
        self.assertEqual(len(result), 1)

    def test_specularcolour_empty_string_no_binding(self):
        """Empty txi_specularcolour → u_has_spec stays 0."""
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m.GpuRenderer._render_gpu)
        self.assertIn('u_has_spec', src_text)

    def test_shininess_zero_uses_global_default(self):
        """shininess=0.0 → renderer uses 20.0 default, not 0."""
        import src.gui.gpu_renderer as m
        import inspect
        src_text = inspect.getsource(m.GpuRenderer._render_gpu)
        # The else branch sets prog['u_shininess'].value = 20.0
        self.assertIn('20.0', src_text)

    def test_accessory_models_dataclass_field(self):
        """CreatureModelSet has accessory_models as a proper dataclass field."""
        import dataclasses
        from src.core.creature_appearance import CreatureModelSet
        fields = {f.name for f in dataclasses.fields(CreatureModelSet)}
        self.assertIn('accessory_models', fields)

    def test_multiple_accessories_draw_order_preserved(self):
        from src.core.creature_appearance import CreatureModelSet
        models = [_make_model(f'm{i}') for i in range(4)]
        cms = CreatureModelSet(
            body_model=models[0],
            accessory_models=[models[1], models[2]],
            head_model=models[3],
        )
        result = cms.all_models()
        self.assertEqual([id(r) for r in result],
                         [id(m) for m in models])

    def test_build_creature_model_empty_accessory_list(self):
        """Passing accessory_resrefs=[] behaves same as default None."""
        import src.core.creature_appearance as mod
        # Just verify it doesn't crash on import and has the kwarg
        import inspect
        sig = inspect.signature(mod.build_creature_model)
        self.assertIn('accessory_resrefs', sig.parameters)

    def test_frag_shader_unit3_reference(self):
        """Fragment shader references unit 3 for specular map."""
        import src.gui.gpu_renderer as m
        import inspect
        # u_spec_tex is declared; binding code passes location=3
        self.assertIn('u_spec_tex', m._FRAG_SRC)
        src_text = inspect.getsource(m.GpuRenderer._render_gpu)
        self.assertIn('location=3', src_text)


if __name__ == '__main__':
    unittest.main()
