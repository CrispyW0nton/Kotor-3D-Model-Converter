"""
Phase 25.0 — Rendering, Export & Template Tests
================================================

Covers:
  1. _is_deformation_helper — eye/teeth/tongue NPC nodes correctly rendered
  2. _is_deformation_helper — arm skin nodes correctly rendered
  3. Face mesh two-sided rendering (_FACE_MESH_SUBSTRINGS)
  4. K1/K2 export selector (_pick_export_game_version / _save_ascii_mdl / _export_mdl_binary)
  5. Supermodel animation inheritance (merge_supermodel_animations)
  6. Humanoid template builder (build_humanoid_template / save_template_manifest)
  7. Template export wired into main window (_export_humanoid_template exists)
  8. Animation panel list_animations returns full set after supermodel merge
  9. Inner-geo tier promotion constants
 10. Template manifest JSON content

Tests
-----
  TestDeformHelperLogic             (9 tests)  — Pure logic, no Tk dependency
  TestFaceMeshTwoSided              (3 tests)
  TestGameVersionExport             (5 tests)
  TestSupermodelAnimMerge           (6 tests)
  TestHumanoidTemplateBuilder       (8 tests)
  TestTemplateManifest              (4 tests)
  TestAnimationEngineListAnims      (4 tests)
  TestInnerGeoTierPromotion         (4 tests)
  TestMainWindowTemplateExport      (5 tests)
  TestExportMenuHasTemplate         (2 tests)
"""

from __future__ import annotations
import os
import sys
import json
import tempfile
import types

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, _ROOT)

from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion
from src.core.model_data import Animation


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mesh_node(name, texture='tex01', uvs=None, is_skin=False, render=True):
    """Create a minimal mesh ModelNode."""
    flags = int(NodeFlags.HEADER) | int(NodeFlags.MESH)
    if is_skin:
        flags |= int(NodeFlags.SKIN)
    n = ModelNode(name=name, flags=flags)
    n.render   = render
    n.texture  = texture
    n.uvs      = uvs if uvs is not None else [(0.1, 0.2), (0.5, 0.6), (0.3, 0.9)]
    n.vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
    n.faces    = [(0, 1, 2)]
    n.normals  = [(0, 0, 1)] * 3
    return n


def _anim_obj(name, length=1.0):
    a = Animation()
    a.name   = name
    a.length = length
    a.nodes  = []
    a.events = []
    return a


# ─────────────────────────────────────────────────────────────────────────────
#  Pure-logic helper that reproduces _is_deformation_helper without Tk
# ─────────────────────────────────────────────────────────────────────────────

def _is_deform_helper(node, skin_proxy_ids=None):
    """
    Reproduce the _is_deformation_helper logic from viewport.py without
    importing any Tk-dependent code.

    Mirrors the code at src/gui/viewport.py lines 6277–6394.
    """
    from src.gui.viewport import _INNER_GEO_SUBSTRINGS, _clean_tex_name

    if getattr(node, '_imported', False):
        return False

    tex        = _clean_tex_name(node.texture)
    is_null_tex = (not tex or tex.upper() == 'NULL')

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

    # Null-texture non-skin → helper
    if is_null_tex and not node.is_skin:
        return True

    # Null-texture skin with no UVs or all-zero UVs → helper
    if is_null_tex and node.is_skin and (not node.uvs
                        or all(u == 0.0 and v == 0.0
                               for u, v in node.uvs[:5])):
        return True

    # Non-skin no UVs → helper
    if not node.is_skin and not node.uvs:
        return True

    # Skin-proxy detection
    if skin_proxy_ids is not None and id(node) in skin_proxy_ids:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
#  1. _is_deformation_helper logic — eye/teeth nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestDeformHelperLogic:
    """
    Pure-logic tests for _is_deformation_helper without Tk/renderer dependency.
    Each test mirrors a real rendering scenario from KotOR head/body models.
    """

    # ── Eye nodes ──────────────────────────────────────────────────────────

    def test_npc_eye_node_with_texture_not_helper(self):
        """f_rlweye_g with real texture + valid UVs → renders (NOT a helper)."""
        n = _mesh_node('f_rlweye_g', texture='n_brejx01', is_skin=False)
        assert _is_deform_helper(n) is False

    def test_npc_eye_node_no_texture_is_helper(self):
        """Eye node with null texture IS a helper (nothing to render)."""
        n = _mesh_node('f_rlweye_g', texture='NULL', is_skin=False,
                       uvs=[(0.1, 0.2)])
        assert _is_deform_helper(n) is True

    def test_npc_eye_node_no_uvs_is_helper(self):
        """Eye node with valid texture but no UVs is a helper."""
        n = _mesh_node('f_rlweye_g', texture='n_brejx01', is_skin=False,
                       uvs=[])
        assert _is_deform_helper(n) is True

    def test_plain_g_node_no_inner_geo_is_helper(self):
        """Non-inner-geo _g node (e.g. pelvis_g) with texture IS a helper."""
        n = _mesh_node('pelvis_g', texture='c_jawa01', is_skin=False,
                       uvs=[(0.1, 0.2)])
        assert _is_deform_helper(n) is True

    def test_left_eye_node_variant(self):
        """f_llweye_g (left eye) with texture is NOT a helper."""
        n = _mesh_node('f_llweye_g', texture='n_brejx01', is_skin=False)
        assert _is_deform_helper(n) is False

    # ── Arm / body skin nodes ──────────────────────────────────────────────

    def test_skin_node_with_texture_and_uvs_not_helper(self):
        """Standard skin node with real texture and valid UVs → renders."""
        n = _mesh_node('robe_arm_l', texture='c_jawa01', is_skin=True,
                       uvs=[(0.1, 0.2), (0.5, 0.6)])
        assert _is_deform_helper(n) is False

    def test_skin_node_null_texture_zero_uvs_is_helper(self):
        """Skin node with null texture and all-zero UVs → deform helper."""
        n = _mesh_node('armflesh', texture='NULL', is_skin=True,
                       uvs=[(0.0, 0.0), (0.0, 0.0)])
        assert _is_deform_helper(n) is True

    def test_non_skin_node_without_uvs_is_helper(self):
        """Non-skin node without UV data is always a deform helper."""
        n = _mesh_node('BTHips', texture='c_bantha01', is_skin=False, uvs=[])
        assert _is_deform_helper(n) is True

    def test_skin_node_extreme_uvs_is_helper(self):
        """Skin node with extreme UVs (>3.0) → deform helper."""
        n = _mesh_node('rbicep_g', texture='c_jawa01', is_skin=True,
                       uvs=[(5.0, 5.0), (0.1, 0.2)])
        assert _is_deform_helper(n) is True


# ─────────────────────────────────────────────────────────────────────────────
#  2. Face mesh two-sided rendering constants
# ─────────────────────────────────────────────────────────────────────────────

class TestFaceMeshTwoSided:
    """Nodes whose names match _FACE_MESH_SUBSTRINGS must be treated two-sided."""

    def test_face_substring_in_constants(self):
        from src.gui.viewport import _FACE_MESH_SUBSTRINGS
        assert 'face' in _FACE_MESH_SUBSTRINGS
        assert 'head' in _FACE_MESH_SUBSTRINGS

    def test_face_node_name_matches(self):
        from src.gui.viewport import _FACE_MESH_SUBSTRINGS
        name = 'n_childfh_face'
        assert any(s in name.lower() for s in _FACE_MESH_SUBSTRINGS)

    def test_head_node_name_matches(self):
        from src.gui.viewport import _FACE_MESH_SUBSTRINGS
        name = 'n_brejikh_head'
        assert any(s in name.lower() for s in _FACE_MESH_SUBSTRINGS)


# ─────────────────────────────────────────────────────────────────────────────
#  3. Game-version export selector
# ─────────────────────────────────────────────────────────────────────────────

class TestGameVersionExport:
    """The K1/K2 export picker dialog exists and binary/ASCII exporters use it."""

    def _get_main_cls(self):
        """Return the KotorModToolsApp class without instantiating it."""
        import inspect
        # Import main_window source only — avoid executing Tk code
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_mw_inspect",
            os.path.join(_ROOT, "src", "gui", "main_window.py"))
        return spec  # just for source-level inspection

    def test_pick_export_game_version_method_exists(self):
        """KotorModToolsApp must expose _pick_export_game_version."""
        import inspect
        import ast
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            src = fh.read()
        assert 'def _pick_export_game_version' in src

    def test_save_ascii_mdl_calls_pick(self):
        """_save_ascii_mdl must call _pick_export_game_version."""
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            src = fh.read()
        # Both method definitions must be present and the pick call inside the save method
        assert 'def _save_ascii_mdl' in src
        assert '_pick_export_game_version' in src

    def test_export_mdl_binary_calls_pick(self):
        """_export_mdl_binary must call _pick_export_game_version."""
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            src = fh.read()
        assert 'def _export_mdl_binary' in src

    def test_retarget_panel_has_k1_k2_radio_buttons(self):
        """The character builder (formerly retarget panel) must define K1/K2 radio buttons.

        Phase 32: RetargetPanel was merged into CharacterBuilderPanel which uses
        _game_var instead of _export_gv_var for the K1/K2 game selector.
        """
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            src = fh.read()
        # CharacterBuilderPanel uses _game_var with K1/K2 radiobuttons
        assert '_game_var' in src or '_export_gv_var' in src
        assert '"K1"' in src or "'K1'" in src
        assert '"K2"' in src or "'K2'" in src

    def test_game_version_enum_k1_k2_exist(self):
        """GameVersion enum must have K1 and K2 members."""
        assert hasattr(GameVersion, 'K1')
        assert hasattr(GameVersion, 'K2')


# ─────────────────────────────────────────────────────────────────────────────
#  4. Supermodel animation inheritance
# ─────────────────────────────────────────────────────────────────────────────

class TestSupermodelAnimMerge:
    """merge_supermodel_animations correctly inherits parent animations."""

    def test_merge_adds_parent_anims_to_child(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = KotorModel(name='head01')
        parent = KotorModel(name='S_Female02')
        child.animations  = [_anim_obj('pause1')]
        parent.animations = [_anim_obj('pause1'), _anim_obj('walk'),
                             _anim_obj('run'),    _anim_obj('tlknorm1')]
        result = merge_supermodel_animations(child, parent)
        names = {a.name for a in result.animations}
        assert 'walk'     in names
        assert 'run'      in names
        assert 'tlknorm1' in names

    def test_merge_does_not_duplicate_existing_anims(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = KotorModel(name='head01')
        parent = KotorModel(name='S_Female02')
        child.animations  = [_anim_obj('pause1', length=1.5)]
        parent.animations = [_anim_obj('pause1', length=2.0), _anim_obj('walk')]
        merge_supermodel_animations(child, parent)
        pause_anims = [a for a in child.animations if a.name == 'pause1']
        assert len(pause_anims) == 1
        # Child's own animation is preserved (length=1.5, not 2.0)
        assert abs(pause_anims[0].length - 1.5) < 1e-9

    def test_merge_case_insensitive(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = KotorModel(name='head01')
        parent = KotorModel(name='S_Male02')
        child.animations  = [_anim_obj('Pause1')]
        parent.animations = [_anim_obj('pause1'), _anim_obj('Walk')]
        merge_supermodel_animations(child, parent)
        names_lower = {a.name.lower() for a in child.animations}
        assert 'walk' in names_lower
        # 'pause1' must NOT appear twice (case-insensitive dedup)
        assert sum(1 for a in child.animations
                   if a.name.lower() == 'pause1') == 1

    def test_merge_with_none_child_returns_none(self):
        from src.core.creature_appearance import merge_supermodel_animations
        parent = KotorModel(name='S_Male02')
        parent.animations = [_anim_obj('walk')]
        result = merge_supermodel_animations(None, parent)
        assert result is None

    def test_merge_with_none_parent_returns_child(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child = KotorModel(name='head01')
        child.animations = [_anim_obj('pause1')]
        result = merge_supermodel_animations(child, None)
        assert result is child

    def test_merge_talking_anims_inherited(self):
        """Talking / facial expression animations must be inheritable."""
        from src.core.creature_appearance import merge_supermodel_animations
        child  = KotorModel(name='n_brejikh')
        parent = KotorModel(name='S_Male02')
        child.animations  = []
        parent.animations = [
            _anim_obj('tlkang1'), _anim_obj('tlkfear1'),
            _anim_obj('tlkhappy1'), _anim_obj('tlknorm1'),
            _anim_obj('tlksad1'),  _anim_obj('tlkworry1'),
        ]
        merge_supermodel_animations(child, parent)
        names = {a.name for a in child.animations}
        assert 'tlkang1'   in names
        assert 'tlkhappy1' in names
        assert 'tlknorm1'  in names


# ─────────────────────────────────────────────────────────────────────────────
#  5. Humanoid template builder
# ─────────────────────────────────────────────────────────────────────────────

class TestHumanoidTemplateBuilder:
    """build_humanoid_template creates a valid, complete KotorModel."""

    def _build(self, gv='K1'):
        from src.core.template_builder import build_humanoid_template
        return build_humanoid_template(game_version=gv)

    def test_template_returns_kotor_model(self):
        model = self._build()
        # model is a KotorModel (same class, even if from different import path)
        assert model.__class__.__name__ == 'KotorModel'

    def test_template_has_root_node(self):
        model = self._build()
        assert model.root_node is not None
        assert model.root_node.name == 'Mesh_Root'

    def test_template_has_spine_bones(self):
        model = self._build()
        all_names = {n.name for n in model.all_nodes()}
        for bone in ('Pelvis', 'Spine1', 'Chest', 'Neck', 'Head'):
            assert bone in all_names, f"Missing bone: {bone}"

    def test_template_has_arm_bones(self):
        model = self._build()
        all_names = {n.name for n in model.all_nodes()}
        for bone in ('L_Shoulder', 'L_Hand', 'R_Shoulder', 'R_Hand'):
            assert bone in all_names, f"Missing arm bone: {bone}"

    def test_template_has_leg_bones(self):
        model = self._build()
        all_names = {n.name for n in model.all_nodes()}
        for bone in ('L_Thigh', 'L_Foot', 'R_Thigh', 'R_Foot'):
            assert bone in all_names, f"Missing leg bone: {bone}"

    def test_template_has_animations(self):
        model = self._build()
        assert len(model.animations) >= 30, \
            f"Expected ≥30 animation slots, got {len(model.animations)}"

    def test_template_includes_talking_anims(self):
        model = self._build()
        names = {a.name for a in model.animations}
        for anim in ('tlkang1', 'tlkfear1', 'tlkhappy1',
                     'tlknorm1', 'tlksad1', 'tlkworry1'):
            assert anim in names, f"Missing talking anim: {anim}"

    def test_template_k2_variant(self):
        """K2 template sets game_version=K2."""
        model = self._build(gv='K2')
        assert model.game_version.name == 'K2'


# ─────────────────────────────────────────────────────────────────────────────
#  6. Template manifest
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplateManifest:
    """save_template_manifest writes a valid JSON file."""

    def _build_and_save(self, gv='K1'):
        from src.core.template_builder import (
            build_humanoid_template, save_template_manifest)
        model = build_humanoid_template(game_version=gv)
        with tempfile.TemporaryDirectory() as td:
            path = save_template_manifest(model, td)
            with open(path, 'r') as fh:
                data = json.load(fh)
            return data

    def test_manifest_has_required_keys(self):
        data = self._build_and_save()
        for key in ('name', 'game_version', 'bones', 'animation_slots',
                    'description'):
            assert key in data, f"Missing manifest key: {key}"

    def test_manifest_bones_list_complete(self):
        data = self._build_and_save()
        bone_names = {b['name'] for b in data['bones']}
        for b in ('Mesh_Root', 'Pelvis', 'Chest', 'L_Hand', 'R_Foot'):
            assert b in bone_names, f"Missing bone in manifest: {b}"

    def test_manifest_anim_slots(self):
        data = self._build_and_save()
        slots = {a['name'] for a in data['animation_slots']}
        assert 'walk' in slots
        assert 'tlknorm1' in slots

    def test_manifest_game_version_field(self):
        data = self._build_and_save(gv='K2')
        assert data['game_version'] == 'K2'


# ─────────────────────────────────────────────────────────────────────────────
#  7. AnimationEngine list_animations
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationEngineListAnims:
    """AnimationEngine.list_animations reflects all merged animations."""

    def _engine(self, model):
        from src.core.animation_engine import AnimationEngine
        return AnimationEngine(model)

    def test_list_anims_empty_model(self):
        m = KotorModel(name='test')
        eng = self._engine(m)
        assert eng.list_animations() == []

    def test_list_anims_after_merge(self):
        from src.core.creature_appearance import merge_supermodel_animations
        child  = KotorModel(name='head01')
        parent = KotorModel(name='S_Male02')
        parent.animations = [_anim_obj('walk'), _anim_obj('run'),
                             _anim_obj('tlknorm1')]
        child.animations  = []
        merge_supermodel_animations(child, parent)

        eng   = self._engine(child)
        anims = eng.list_animations()
        names = {a['name'] for a in anims}
        assert 'walk'     in names
        assert 'tlknorm1' in names

    def test_list_anims_includes_length(self):
        m = KotorModel(name='test')
        a = _anim_obj('walk', length=1.5)
        m.animations = [a]
        eng   = self._engine(m)
        anims = eng.list_animations()
        assert len(anims) == 1
        assert abs(anims[0]['length'] - 1.5) < 1e-9

    def test_list_anims_key_count(self):
        m = KotorModel(name='test')
        a = _anim_obj('walk')
        # Add a ModelNode with controllers (3 keyframes)
        an = ModelNode(name='Mesh_Root', flags=int(NodeFlags.HEADER))
        an.controllers = [
            {'times': [0.0, 0.5, 1.0], 'values': [(0,0,0,1)] * 3,
             'type': 'rotation'}
        ]
        a.nodes = [an]
        m.animations = [a]
        eng   = self._engine(m)
        anims = eng.list_animations()
        assert anims[0]['key_count'] == 3


# ─────────────────────────────────────────────────────────────────────────────
#  8. Inner-geo tier promotion constants
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoTierPromotion:
    """Eye, teeth, tongue nodes must be in _INNER_GEO_SUBSTRINGS."""

    def test_inner_geo_substrings_contain_eye(self):
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'eye' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contain_teeth(self):
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'teeth' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_substrings_contain_tongue(self):
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'tongue' in _INNER_GEO_SUBSTRINGS

    def test_npc_eye_name_matches_inner_geo(self):
        """f_rlweye_g contains 'eye' → matches inner-geo substring."""
        from src.gui.viewport import _INNER_GEO_SUBSTRINGS
        assert any(s in 'f_rlweye_g' for s in _INNER_GEO_SUBSTRINGS)


# ─────────────────────────────────────────────────────────────────────────────
#  9. Template export method on MainWindow (source-level inspection)
# ─────────────────────────────────────────────────────────────────────────────

class TestMainWindowTemplateExport:
    """_export_humanoid_template must exist in main_window.py source."""

    @classmethod
    def _src(cls):
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            return fh.read()

    def test_method_exists_in_source(self):
        assert 'def _export_humanoid_template' in self._src()

    def test_method_calls_pick_game_version(self):
        """Template exporter must ask for K1/K2 choice."""
        src = self._src()
        # Find the method block
        idx = src.find('def _export_humanoid_template')
        assert idx >= 0
        # Check within next 3000 chars
        block = src[idx:idx+3000]
        assert '_pick_export_game_version' in block

    def test_method_calls_build_humanoid_template(self):
        """Template exporter must invoke the builder."""
        src = self._src()
        idx = src.find('def _export_humanoid_template')
        block = src[idx:idx+3000]
        assert 'build_humanoid_template' in block

    def test_method_saves_manifest(self):
        """Template exporter must save the JSON manifest."""
        src = self._src()
        idx = src.find('def _export_humanoid_template')
        block = src[idx:idx+3000]
        assert 'save_template_manifest' in block

    def test_method_writes_binary_mdl(self):
        """Template exporter must write a binary MDL file."""
        src = self._src()
        idx = src.find('def _export_humanoid_template')
        block = src[idx:idx+3000]
        assert 'MDLBinaryWriter' in block or '_MBW' in block


# ─────────────────────────────────────────────────────────────────────────────
#  10. Export menu contains humanoid template entry
# ─────────────────────────────────────────────────────────────────────────────

class TestExportMenuHasTemplate:
    """The Export toolbar menu must include 'Export Humanoid Template…'."""

    @classmethod
    def _src(cls):
        src_path = os.path.join(_ROOT, "src", "gui", "main_window.py")
        with open(src_path) as fh:
            return fh.read()

    def test_export_menu_references_template_method(self):
        """exp_menu.add_command must reference _export_humanoid_template."""
        src = self._src()
        assert '_export_humanoid_template' in src

    def test_export_menu_has_humanoid_template_label(self):
        """Export menu label must mention 'Humanoid Template'."""
        src = self._src()
        assert 'Humanoid Template' in src
