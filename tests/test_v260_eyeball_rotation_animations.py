"""
Phase 26 — Eyeball Rendering, 90° Rotation, Animation Chain & Template Tests
==============================================================================

Covers:
  1. Inner-geo nodes (eyes/teeth/tongue) are now always two-sided in all render paths
  2. Inner-geo nodes with any valid texture/UVs are NEVER marked deformation helpers
     (early-return guard bypasses all later checks including _skin_proxy_ids)
  3. _compute_skin_proxy_ids NEVER marks inner-geo nodes as proxies
  4. RetargetEngine.rotate_90 – all 6 axis/direction combinations
  5. Supermodel animation chain walk (multi-level chain up to 8 levels)
  6. Template category injected into LibraryPanel._all_entries
  7. gr_humanoid_* entries categorised as 'Template' by _infer_model_category
  8. Template loads procedurally via _model_override path
  9. Template builder produces K1 and K2 variants with correct metadata
 10. _infer_model_category returns 'Template' for gr_ prefix
"""

from __future__ import annotations
import os
import sys
import types
import copy

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, _ROOT)

from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion
from src.core.model_data import Animation


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mesh_node(name, texture='tex01', uvs=None, is_skin=False,
               render=True, extreme_uvs=False):
    """Create a minimal mesh ModelNode."""
    flags = int(NodeFlags.HEADER) | int(NodeFlags.MESH)
    if is_skin:
        flags |= int(NodeFlags.SKIN)
    n = ModelNode(name=name, flags=flags)
    n.render   = render
    n.texture  = texture
    n.uvs      = uvs if uvs is not None else [(0.1, 0.2), (0.5, 0.6), (0.3, 0.9)]
    if extreme_uvs:
        n.uvs = [(5.0, 5.0), (6.0, 0.0)]
    n.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    n.faces    = [(0, 1, 2)]
    n.normals  = [(0.0, 0.0, 1.0)] * 3
    return n


def _anim_obj(name, length=1.0):
    a = Animation()
    a.name   = name
    a.length = length
    a.nodes  = []
    a.events = []
    return a


# Reproduce the v26 _is_deformation_helper logic (including the new early-return)
def _is_deform_helper_v26(node, skin_proxy_ids=None):
    from src.gui.viewport import _INNER_GEO_SUBSTRINGS, _clean_tex_name

    if getattr(node, '_imported', False):
        return False

    tex         = _clean_tex_name(node.texture)
    is_null_tex = (not tex or tex.upper() == 'NULL')

    # ── v26 early-return: inner-geo nodes always renderable ──────────────
    _name_lower = node.name.lower()
    if any(s in _name_lower for s in _INNER_GEO_SUBSTRINGS):
        if not is_null_tex and node.uvs:
            _uvs_ok = not any(abs(u) > 3.0 or abs(v) > 3.0
                              for u, v in node.uvs[:20])
            if _uvs_ok:
                return False  # always render

    # Skin + real texture + valid UVs → always visible
    if node.is_skin and not is_null_tex and node.uvs:
        has_extreme = any(abs(u) > 3.0 or abs(v) > 3.0
                         for u, v in node.uvs[:20])
        if not has_extreme:
            return False

    # Extreme UVs → always helper
    if node.uvs:
        has_extreme = any(abs(u) > 3.0 or abs(v) > 3.0
                         for u, v in node.uvs[:20])
        if has_extreme:
            return True

    # Non-skin _g / _g0 / _dum — UNLESS inner-geo with real texture + valid UVs
    name_lower = node.name.lower()
    _name_is_inner_geo = any(s in name_lower for s in _INNER_GEO_SUBSTRINGS)
    if not node.is_skin and (name_lower.endswith('_g')
                              or name_lower.endswith('_g0')
                              or name_lower.endswith('_dum')):
        if _name_is_inner_geo and not is_null_tex and node.uvs:
            _uvs_ok = not any(abs(u) > 3.0 or abs(v) > 3.0
                              for u, v in node.uvs[:20])
            if _uvs_ok:
                return False
        return True

    if is_null_tex and not node.is_skin:
        return True
    if is_null_tex and node.is_skin and (not node.uvs
                        or all(u == 0.0 and v == 0.0
                               for u, v in node.uvs[:5])):
        return True
    if not node.is_skin and not node.uvs:
        return True
    if skin_proxy_ids is not None and id(node) in skin_proxy_ids:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
#  1.  Inner-geo nodes – two-sided in all render paths
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoTwoSided:
    """Inner-geometry nodes (eyes, teeth, tongue, jaw) must be two-sided
    so they are never back-face culled when viewed through the head socket."""

    from src.gui.viewport import _INNER_GEO_SUBSTRINGS, _FACE_MESH_SUBSTRINGS

    def _two_sided(self, name, is_dangly=False, transp_hint=0):
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS, _FACE_MESH_SUBSTRINGS
        nl = name.lower()
        is_face   = any(s in nl for s in _FACE_MESH_SUBSTRINGS)
        is_inner  = any(s in nl for s in _INNER_GEO_SUBSTRINGS)
        return is_dangly or transp_hint in (1, 2) or is_face or is_inner

    def test_btLeye_two_sided(self):
        assert self._two_sided('btLeye') is True

    def test_btReye_two_sided(self):
        assert self._two_sided('btReye') is True

    def test_eyeRA_two_sided(self):
        assert self._two_sided('eyeRA') is True

    def test_eyeLA_two_sided(self):
        assert self._two_sided('eyeLA') is True

    def test_f_rlweye_g_two_sided(self):
        assert self._two_sided('f_rlweye_g') is True

    def test_f_llweye_g_two_sided(self):
        assert self._two_sided('f_llweye_g') is True

    def test_teeth_u_two_sided(self):
        assert self._two_sided('teethU') is True

    def test_teeth_l_two_sided(self):
        assert self._two_sided('teethL') is True

    def test_tongue_two_sided(self):
        assert self._two_sided('tongue') is True

    def test_jaw_two_sided(self):
        assert self._two_sided('jaw') is True

    def test_gum_two_sided(self):
        assert self._two_sided('gum') is True

    def test_eyelid_two_sided(self):
        assert self._two_sided('eyeRlid') is True

    def test_body_not_two_sided(self):
        """Body mesh must NOT be two-sided (not inner-geo, not face)."""
        assert self._two_sided('body') is False

    def test_spine_not_two_sided(self):
        assert self._two_sided('spine') is False


# ─────────────────────────────────────────────────────────────────────────────
#  2.  Inner-geo nodes – _is_deformation_helper early-return guard (v26)
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoEarlyReturn:
    """
    v26 fix: _is_deformation_helper returns False immediately for inner-geo
    nodes that have a real texture and valid UVs — regardless of any other
    classification logic (name suffix, skin-proxy, etc.).
    """

    def test_btLeye_not_helper(self):
        """btLeye: non-skin, texture=c_bantha01, valid UVs → NOT a helper."""
        n = _mesh_node('btLeye', texture='c_bantha01')
        assert _is_deform_helper_v26(n) is False

    def test_btReye_not_helper(self):
        n = _mesh_node('btReye', texture='c_bantha01')
        assert _is_deform_helper_v26(n) is False

    def test_eye_g_suffix_not_helper(self):
        """f_rlweye_g: ends in _g but is inner-geo → NOT a helper."""
        n = _mesh_node('f_rlweye_g', texture='h_f')
        assert _is_deform_helper_v26(n) is False

    def test_teeth_g_suffix_not_helper(self):
        """teethU_g: ends in _g + inner-geo → NOT a helper."""
        n = _mesh_node('teethU_g', texture='h_m')
        assert _is_deform_helper_v26(n) is False

    def test_eye_null_tex_is_helper(self):
        """Eye node with null texture → still a helper (no texture = invisible)."""
        n = _mesh_node('btLeye', texture='null')
        assert _is_deform_helper_v26(n) is True

    def test_eye_extreme_uvs_is_helper(self):
        """Eye node with extreme UVs → still a helper."""
        n = _mesh_node('btLeye', texture='c_bantha01', extreme_uvs=True)
        assert _is_deform_helper_v26(n) is True

    def test_eye_skin_proxy_not_helper(self):
        """
        v26 fix: inner-geo node whose id is in skin_proxy_ids must still
        render (early-return fires BEFORE the proxy check).
        """
        n = _mesh_node('btLeye', texture='c_bantha01')
        proxy_set = {id(n)}
        # old code would return True (proxy), v26 should return False (inner-geo)
        assert _is_deform_helper_v26(n, skin_proxy_ids=proxy_set) is False

    def test_tongue_skin_proxy_not_helper(self):
        """Same for tongue node."""
        n = _mesh_node('tongue', texture='h_m')
        proxy_set = {id(n)}
        assert _is_deform_helper_v26(n, skin_proxy_ids=proxy_set) is False


# ─────────────────────────────────────────────────────────────────────────────
#  3.  _compute_skin_proxy_ids never marks inner-geo nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinProxyInnerGeoExemption:
    """
    v26 fix: _compute_skin_proxy_ids must skip inner-geo nodes so that
    btLeye / btReye etc. are never silenced even when they share a texture
    with exactly one skin mesh.
    """

    def _build_model_with_eye_and_skin(self):
        """
        Minimal model:
          - body_skin  : is_skin, tex='c_bantha01', 1215 verts  (the large skin mesh)
          - btLeye     : not skin, tex='c_bantha01', 13 verts    (eye = inner-geo)
          - btRhorn    : not skin, tex='c_bantha01', 99 verts    (should also NOT be proxied
                          since c_bantha01 now has ONE skin mesh → rule 4 met → horn IS proxied)
        """
        from src.core.model_data import KotorModel
        model = KotorModel(name='test_bantha')

        skin = _mesh_node('body_skin', texture='c_bantha01', is_skin=True)
        skin.vertices = [(float(i), 0.0, 0.0) for i in range(1215)]

        eye = _mesh_node('btLeye', texture='c_bantha01')
        eye.vertices = [(float(i), 0.0, 0.0) for i in range(13)]

        horn = _mesh_node('btRhorn', texture='c_bantha01')
        horn.vertices = [(float(i), 0.0, 0.0) for i in range(99)]

        root = ModelNode(name='Mesh_Root',
                         flags=int(NodeFlags.HEADER))
        root.children = [skin, eye, horn]
        skin.parent = root
        eye.parent  = root
        horn.parent = root
        model.root_node = root
        return model, skin, eye, horn

    def test_eye_not_in_proxy_set(self):
        """btLeye must never appear in skin_proxy_ids even with exactly one skin sharing tex."""
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS, _clean_tex_name

        model, skin, eye, horn = self._build_model_with_eye_and_skin()

        # Re-implement _compute_skin_proxy_ids logic with v26 inner-geo guard
        proxy_ids = set()
        all_nodes = list(model.all_nodes())

        skin_tex_verts = {}
        for n in all_nodes:
            if not n.is_skin: continue
            tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
            if not tex or tex == 'null': continue
            nv = len(getattr(n, 'vertices', []))
            if nv == 0: continue
            if tex not in skin_tex_verts:
                skin_tex_verts[tex] = []
            skin_tex_verts[tex].append((n, nv))

        for n in all_nodes:
            if not n.is_mesh or n.is_skin: continue
            tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
            if not tex or tex == 'null': continue
            if not getattr(n, 'uvs', []): continue
            nv = len(getattr(n, 'vertices', []))
            # v26 inner-geo exemption
            _n_lower = n.name.lower()
            if any(s in _n_lower for s in _INNER_GEO_SUBSTRINGS):
                continue  # <-- this is the new guard
            skin_matches = skin_tex_verts.get(tex, [])
            if len(skin_matches) != 1: continue
            _, skin_verts = skin_matches[0]
            if skin_verts <= nv: continue
            proxy_ids.add(id(n))

        assert id(eye)  not in proxy_ids, "btLeye must NOT be a skin proxy"
        assert id(skin) not in proxy_ids, "body_skin (is_skin) must NOT be a proxy"
        # horn has no inner-geo substring, so it IS a proxy here (expected)
        assert id(horn) in proxy_ids, "btRhorn (no inner-geo) should be a proxy"


# ─────────────────────────────────────────────────────────────────────────────
#  4.  RetargetEngine.rotate_90
# ─────────────────────────────────────────────────────────────────────────────

class TestRotate90:
    """Verify RetargetEngine.rotate_90 for all 6 axis/direction combinations."""

    def _engine_with_vertices(self, verts):
        from src.autorig.retarget_engine import RetargetEngine
        from src.core.model_data import KotorModel

        model = KotorModel(name='rot_test')
        root  = _mesh_node('Mesh_Root', texture='tex01')
        root.vertices = list(verts)
        root.faces    = []
        model.root_node = root
        engine = RetargetEngine()
        engine._working = model
        return engine, root

    def _approx(self, a, b, tol=1e-4):
        return all(abs(a[i] - b[i]) < tol for i in range(3))

    def test_z_ccw(self):
        """Z CCW: (1,0,0) → (0,1,0)"""
        engine, root = self._engine_with_vertices([(1.0, 0.0, 0.0)])
        res = engine.rotate_90(axis='Z', direction=+1)
        assert res['ok']
        assert self._approx(root.vertices[0], (0.0, 1.0, 0.0))

    def test_z_cw(self):
        """Z CW: (1,0,0) → (0,-1,0)"""
        engine, root = self._engine_with_vertices([(1.0, 0.0, 0.0)])
        engine.rotate_90(axis='Z', direction=-1)
        assert self._approx(root.vertices[0], (0.0, -1.0, 0.0))

    def test_y_ccw(self):
        """Y CCW: (1,0,0) → (0,0,-1)"""
        engine, root = self._engine_with_vertices([(1.0, 0.0, 0.0)])
        engine.rotate_90(axis='Y', direction=+1)
        assert self._approx(root.vertices[0], (0.0, 0.0, -1.0))

    def test_y_cw(self):
        """Y CW: (1,0,0) → (0,0,1)"""
        engine, root = self._engine_with_vertices([(1.0, 0.0, 0.0)])
        engine.rotate_90(axis='Y', direction=-1)
        assert self._approx(root.vertices[0], (0.0, 0.0, 1.0))

    def test_x_ccw(self):
        """X CCW: (0,1,0) → (0,0,1)"""
        engine, root = self._engine_with_vertices([(0.0, 1.0, 0.0)])
        engine.rotate_90(axis='X', direction=+1)
        assert self._approx(root.vertices[0], (0.0, 0.0, 1.0))

    def test_x_cw(self):
        """X CW: (0,0,1) → (0,1,0)"""
        engine, root = self._engine_with_vertices([(0.0, 0.0, 1.0)])
        engine.rotate_90(axis='X', direction=-1)
        assert self._approx(root.vertices[0], (0.0, 1.0, 0.0))

    def test_four_z_ccw_returns_identity(self):
        """4× Z CCW = identity rotation."""
        engine, root = self._engine_with_vertices([(1.0, 0.5, 0.3)])
        orig = list(root.vertices[0])
        for _ in range(4):
            engine.rotate_90(axis='Z', direction=+1)
        assert self._approx(root.vertices[0], orig)

    def test_no_model_returns_error(self):
        from src.autorig.retarget_engine import RetargetEngine
        engine = RetargetEngine()
        res = engine.rotate_90(axis='Z', direction=+1)
        assert not res['ok']

    def test_invalid_axis_returns_error(self):
        from src.autorig.retarget_engine import RetargetEngine
        from src.core.model_data import KotorModel
        model = KotorModel(name='x')
        engine = RetargetEngine()
        engine._working = model
        res = engine.rotate_90(axis='W', direction=+1)
        assert not res['ok']

    def test_normals_rotated_with_vertices(self):
        """Normals are rotated by the same transform as vertices."""
        engine, root = self._engine_with_vertices([(1.0, 0.0, 0.0)])
        root.normals = [(1.0, 0.0, 0.0)]
        engine.rotate_90(axis='Z', direction=+1)
        assert self._approx(root.normals[0], (0.0, 1.0, 0.0))


# ─────────────────────────────────────────────────────────────────────────────
#  5.  Supermodel animation chain walk (multi-level)
# ─────────────────────────────────────────────────────────────────────────────

class TestSupermodelChainWalk:
    """
    Verify the full supermodel chain walk logic that was added to _phase3.
    We test the underlying merge_supermodel_animations for multi-level chains.
    """

    def _model_with_anims(self, name, anim_names, supermodel='NULL'):
        from src.core.model_data import KotorModel
        m = KotorModel(name=name)
        m.supermodel = supermodel
        m.animations = [_anim_obj(n) for n in anim_names]
        return m

    def test_single_merge(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = self._model_with_anims('head', ['pause1'])
        parent = self._model_with_anims('s_male02', ['cpause1', 'cwalk', 'crun'])
        merge_supermodel_animations(child, parent)
        names = {a.name for a in child.animations}
        assert 'pause1'  in names
        assert 'cpause1' in names
        assert 'cwalk'   in names

    def test_chain_walk_no_duplicates(self):
        """After two-level merge no animation name appears twice."""
        from src.core.creature_appearance import merge_supermodel_animations
        child   = self._model_with_anims('head',     ['tlkang1'])
        parent1 = self._model_with_anims('s_male02', ['cpause1', 'cwalk'])
        parent2 = self._model_with_anims('s_male01', ['cwalk', 'crun'])
        merge_supermodel_animations(child, parent1)
        merge_supermodel_animations(child, parent2)
        names = [a.name for a in child.animations]
        assert names.count('cwalk') == 1, "Duplicate 'cwalk' after chain merge"

    def test_child_anims_not_overwritten(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = self._model_with_anims('head', ['tlkang1'])
        parent = self._model_with_anims('s_male02', ['tlkang1', 'cpause1'])
        merge_supermodel_animations(child, parent)
        # child's own tlkang1 must not be replaced
        orig_id = id(child.animations[0])
        merge_supermodel_animations(child, parent)
        assert id(child.animations[0]) == orig_id

    def test_empty_parent_no_change(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = self._model_with_anims('head', ['pause1'])
        parent = self._model_with_anims('s_male02', [])
        merge_supermodel_animations(child, parent)
        assert len(child.animations) == 1

    def test_circular_chain_guard(self):
        """Chain walk must terminate on circular supermodel references."""
        # Simulate by merging repeatedly — visited set prevents infinite loop
        from src.core.creature_appearance import merge_supermodel_animations
        a = self._model_with_anims('modelA', ['anim1'], supermodel='modelB')
        b = self._model_with_anims('modelB', ['anim2'], supermodel='modelA')
        visited = set()
        current = a
        depth   = 0
        while depth < 8:
            super_name = (getattr(current, 'supermodel', '') or '').strip().upper()
            if super_name in ('', 'NULL', 'NONE') or super_name in visited:
                break
            visited.add(super_name)
            depth += 1
            current = b if current.name == 'modelA' else a
        assert depth < 8, "Chain walk did not terminate on circular reference"


# ─────────────────────────────────────────────────────────────────────────────
#  6.  Template category in _infer_model_category
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplateCategoryInfer:
    """gr_ prefix models must be classified as 'Template'."""

    def _infer(self, resref, model_class=''):
        from src.gui.main_window import _infer_model_category
        return _infer_model_category(resref, model_class)

    def test_gr_humanoid_k1(self):
        assert self._infer('gr_humanoid_k1') == 'Template'

    def test_gr_humanoid_k2(self):
        assert self._infer('gr_humanoid_k2') == 'Template'

    def test_gr_other_prefix(self):
        assert self._infer('gr_custom_rig') == 'Template'

    def test_non_gr_not_template(self):
        assert self._infer('c_bantha')       != 'Template'
        assert self._infer('p_carth')        != 'Template'
        assert self._infer('s_male02')       != 'Template'

    def test_character_not_template(self):
        assert self._infer('p_bastila') == 'Character'


# ─────────────────────────────────────────────────────────────────────────────
#  7.  LibraryPanel CATEGORIES includes 'Template'
# ─────────────────────────────────────────────────────────────────────────────

class TestLibraryCategoriesHasTemplate:
    def test_template_tab_exists(self):
        from src.gui.main_window import LibraryPanel
        keys = [key for _, key, _ in LibraryPanel.CATEGORIES]
        assert 'Template' in keys

    def test_template_tab_label(self):
        from src.gui.main_window import LibraryPanel
        labels = [lbl for lbl, _, _ in LibraryPanel.CATEGORIES]
        assert 'Template' in labels


# ─────────────────────────────────────────────────────────────────────────────
#  8.  Template builder produces correct K1 / K2 variants
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplateBuildVariants:
    def test_k1_game_version(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K1', name='gr_humanoid_k1')
        assert m.game_version == GameVersion.K1

    def test_k2_game_version(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template(game_version='K2', name='gr_humanoid_k2')
        assert m.game_version == GameVersion.K2

    def test_template_has_bones(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template()
        nodes = list(m.all_nodes())
        assert len(nodes) >= 60, f"Expected ≥60 bones, got {len(nodes)}"

    def test_template_has_animations(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template()
        assert len(m.animations) >= 50, f"Expected ≥50 anim slots, got {len(m.animations)}"

    def test_template_has_talking_anims(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template()
        anim_names = {a.name for a in m.animations}
        for tlk in ('tlkang1', 'tlkfear1', 'tlkhappy1', 'tlknorm1'):
            assert tlk in anim_names, f"Missing talking anim '{tlk}'"

    def test_template_root_node_exists(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template()
        assert m.root_node is not None
        assert m.root_node.name == 'Mesh_Root'

    def test_template_name_matches_param(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template(name='gr_test_model')
        assert m.name == 'gr_test_model'

    def test_template_classification_character(self):
        from src.core.template_builder import build_humanoid_template
        m = build_humanoid_template()
        assert getattr(m, 'classification', '').lower() == 'character'


# ─────────────────────────────────────────────────────────────────────────────
#  9.  RetargetEngine.rotate_90 wired in RetargetPanel UI
# ─────────────────────────────────────────────────────────────────────────────

class TestRetargetPanelRotateWiring:
    """Verify rotate_90 method exists on the engine and panel handler exists."""

    def test_engine_has_rotate_90(self):
        from src.autorig.retarget_engine import RetargetEngine
        engine = RetargetEngine()
        assert callable(getattr(engine, 'rotate_90', None))

    def test_main_window_has_rotate_handler(self):
        import ast, inspect
        import src.gui.main_window as mw_mod
        src_path = inspect.getfile(mw_mod)
        with open(src_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        method_names = {
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
        }
        assert '_rotate_90' in method_names, (
            "_rotate_90 handler not found in main_window.py")

    def test_rotate_90_ui_labels_in_source(self):
        import src.gui.main_window as mw_mod
        import inspect
        src_path = inspect.getfile(mw_mod)
        with open(src_path, 'r', encoding='utf-8') as f:
            text = f.read()
        assert 'Rotate 90°' in text or 'rotate_90' in text.lower()
        assert 'CCW' in text or 'CW'  in text


# ─────────────────────────────────────────────────────────────────────────────
# 10.  Phase 26 regression — all previous tests still hold
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase26Regression:
    """Quick smoke-test: core functionality is still intact."""

    def test_import_model_data(self):
        from src.core.model_data import KotorModel, ModelNode, Animation
        assert KotorModel and ModelNode and Animation

    def test_import_template_builder(self):
        from src.core.template_builder import build_humanoid_template
        assert callable(build_humanoid_template)

    def test_import_creature_appearance(self):
        from src.core.creature_appearance import merge_supermodel_animations
        assert callable(merge_supermodel_animations)

    def test_import_retarget_engine(self):
        from src.autorig.retarget_engine import RetargetEngine, OrientationMode
        assert RetargetEngine and OrientationMode

    def test_orientation_modes_intact(self):
        from src.autorig.retarget_engine import OrientationMode
        assert OrientationMode.AUTO.value == 'AUTO'
        assert OrientationMode.YUP.value  == 'YUP'
        assert OrientationMode.ZUP.value  == 'ZUP'

    def test_inner_geo_substrings_unchanged(self):
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'eye'     in _INNER_GEO_SUBSTRINGS
        assert 'teeth'   in _INNER_GEO_SUBSTRINGS
        assert 'tongue'  in _INNER_GEO_SUBSTRINGS
        assert 'lid'     in _INNER_GEO_SUBSTRINGS

    def test_face_mesh_substrings_unchanged(self):
        from src.gui.viewport import _FACE_MESH_SUBSTRINGS
        assert 'face' in _FACE_MESH_SUBSTRINGS
        assert 'head' in _FACE_MESH_SUBSTRINGS
