"""
test_v99_full_character_export.py
==================================
Comprehensive tests for the full-character FBX export pipeline:

  1.  Facial geometry detection   — eyes, teeth, tongue, jaw, eyelids are
                                    always detected as facial geometry.
  2.  render=False bypass          — facial nodes with render=0 are still
                                    exported (viewport + mesh_converter).
  3.  NPC inner-geo detection      — f_rlweye_g style NPC eyeball names are
                                    correctly identified as facial geometry.
  4.  export_full_character_fbx    — combines body + head, merges animations,
                                    attaches head at headhook, exports FBX.
  5.  Base skeleton auto-merge     — merge_supermodel_animations copies clips
                                    from the base skeleton into the character.
  6.  Deformation helper exclusion — _g, _dum, extreme-UV nodes are excluded
                                    from exports UNLESS they are facial geo.
  7.  FBX AnimStack per clip        — each KotOR animation clip is a separate
                                    AnimStack + Takes entry in the FBX file.
  8.  Full pipeline integration    — body + head + base skeleton + animations
                                    → FBX → contains all required FBX sections.
"""
from __future__ import annotations

import os
import sys
import copy
import tempfile
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_HERE, '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.model_data import ModelNode, KotorModel, NodeFlags, BoneWeight
from converters.mesh_converter import OBJExporter, FBXExporter, _renderable_mesh_nodes
from core.creature_appearance import (
    export_full_character_fbx,
    merge_supermodel_animations,
    merge_supermodel,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mesh_node(name: str, texture: str = 'test_tex',
                    render: bool = True, is_skin: bool = False,
                    uvs=None, vertices=None) -> ModelNode:
    """Build a minimal renderable mesh node.
    Note: is_skin is a read-only property derived from flags; we set flags directly.
    """
    n = ModelNode()
    n.name = name
    n.texture = texture
    n.render = render
    # is_skin/is_emitter/is_light/is_dangly are all read-only @property derived
    # from NodeFlags — set the flags bitmask directly.
    n.flags      = NodeFlags.MESH | (NodeFlags.SKIN if is_skin else 0)
    n.vertices   = vertices if vertices is not None else [(0.0, 0.0, 0.0),
                                                          (1.0, 0.0, 0.0),
                                                          (0.5, 1.0, 0.0)]
    n.uvs        = uvs if uvs is not None else [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
    n.faces      = [(0, 1, 2)]
    n.normals    = [(0.0, 0.0, 1.0)] * 3
    n.diffuse    = [1.0, 1.0, 1.0]
    n.ambient    = [0.3, 0.3, 0.3]
    n.bone_map   = []
    n.skin_data  = []
    n.children   = []
    n.parent     = None
    n.position   = (0.0, 0.0, 0.0)
    n.orientation = (0.0, 0.0, 0.0, 1.0)
    return n


def _make_model(name: str, nodes=None) -> KotorModel:
    """Build a minimal KotorModel."""
    m = KotorModel()
    m.name = name
    m.supermodel = 'NULL'
    m.anim_scale = 1.0
    m.animations = []
    m.classification = 'character'

    root = ModelNode()
    root.name = name
    root.flags = NodeFlags.HEADER   # dummy/root node — no MESH/SKIN flags
    root.position = (0.0, 0.0, 0.0)
    root.orientation = (0.0, 0.0, 0.0, 1.0)
    root.children = []
    root.parent = None
    root.vertices = []
    # is_skin/is_emitter/is_light/is_dangly are read-only @property from flags
    m.root_node = root

    if nodes:
        for n in nodes:
            n.parent = root
            root.children.append(n)
    return m


def _make_animation(name: str, length: float = 1.0, n_keyframes: int = 3):
    """Build a minimal Animation object.

    Animation.nodes is a list of ModelNode objects (each with a .controllers
    list of dicts: {'type': int, 'times': list, 'values': list}).
    """
    from core.model_data import Animation, ModelNode, NodeFlags
    anim = Animation()
    anim.name = name
    anim.length = length
    anim.transition_time = 0.25
    anim.anim_root = 'Mesh_Root'
    anim.events = []
    # Build a minimal anim node (ModelNode) with position + orientation controllers
    an = ModelNode()
    an.name = 'pelvis'
    an.flags = 0
    an.position = (0.0, 0.0, 0.0)
    an.orientation = (0.0, 0.0, 0.0, 1.0)
    an.children = []
    an.parent = None
    an.vertices = []
    ts = [i * length / max(n_keyframes - 1, 1) for i in range(n_keyframes)]
    an.controllers = [
        {'type': 8,  'times': ts,
         'values': [(0.0, 0.0, float(i)) for i in range(n_keyframes)]},
        {'type': 20, 'times': ts,
         'values': [(0.0, 0.0, 0.0, 1.0)] * n_keyframes},
    ]
    anim.nodes = [an]
    return anim


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Facial geometry detection
# ─────────────────────────────────────────────────────────────────────────────

class TestFacialGeometryDetection:
    """_is_facial_geometry() correctly whitelists all facial mesh node types."""

    # Standard K1/K2 PC character head names
    @pytest.mark.parametrize("name", [
        'lseyeball01', 'rseyeball01',
        'lssupeyeball01', 'rssupeyeball01',
        'teethlower', 'teethupper',
        'tongue',
        'eyelidl', 'eyelidr',
        'eyewhite', 'eyecornea',
    ])
    def test_standard_facial_names(self, name):
        n = _make_mesh_node(name)
        assert OBJExporter._is_facial_geometry(n), \
            f"'{name}' should be recognised as facial geometry"

    # NPC inner-geometry names (contain facial substrings)
    @pytest.mark.parametrize("name,texture", [
        ('f_rlweye_g',  'npc_eye'),    # NPC right-lower-eye with real texture
        ('f_llweye_g',  'npc_eye'),    # NPC left-lower-eye with real texture
        ('f_teetha_g',  'npc_teeth'),  # NPC upper teeth
        ('jawskin',     'jaw_tex'),    # jaw skin mesh
        ('gumsmesh',    'gum_tex'),    # gum mesh
        ('tonguemesh',  'tongue_t'),   # tongue mesh
    ])
    def test_npc_inner_geo_names(self, name, texture):
        n = _make_mesh_node(name, texture=texture)
        assert OBJExporter._is_facial_geometry(n), \
            f"NPC facial node '{name}' should be recognised as facial geometry"

    # NON-facial names must NOT be detected as facial
    @pytest.mark.parametrize("name", [
        'body_mesh', 'pelvis_g', 'torso_g', 'head_g',
        'lbicep_g', 'rthigh_g', 'rootdummy',
    ])
    def test_non_facial_names_rejected(self, name):
        n = _make_mesh_node(name)
        assert not OBJExporter._is_facial_geometry(n), \
            f"'{name}' should NOT be detected as facial geometry"

    # Case-insensitivity
    def test_case_insensitive(self):
        for name in ('LSEYEBALL01', 'TeethLower', 'TEETHUPPER', 'Tongue'):
            n = _make_mesh_node(name)
            assert OBJExporter._is_facial_geometry(n), \
                f"Case-insensitive match failed for '{name}'"


# ─────────────────────────────────────────────────────────────────────────────
# 2.  render=False bypass for facial nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestFacialRenderFalseBypass:
    """Facial nodes are renderable even when their binary MDL stores render=0."""

    @pytest.mark.parametrize("name", [
        'lseyeball01', 'rseyeball01',
        'teethlower', 'teethupper',
        'tongue',
    ])
    def test_facial_render_false_is_renderable(self, name):
        n = _make_mesh_node(name, render=False)
        # _is_renderable must return True for facial nodes regardless of render flag
        assert OBJExporter._is_renderable(n), \
            f"Facial node '{name}' with render=False should still be renderable"

    def test_non_facial_render_false_is_not_renderable(self):
        n = _make_mesh_node('body_mesh', render=False)
        assert not OBJExporter._is_renderable(n), \
            "Non-facial node with render=False must NOT be renderable"

    def test_npc_eyeball_render_false_renderable(self):
        """NPC eyeball (f_rlweye_g) with render=False is still renderable."""
        n = _make_mesh_node('f_rlweye_g', texture='npc_eye', render=False)
        assert OBJExporter._is_renderable(n), \
            "NPC eyeball node with render=False should be renderable"


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Deformation helper exclusion with facial exception
# ─────────────────────────────────────────────────────────────────────────────

class TestDeformationHelperFacialException:
    """_is_deformation_helper() skips facial nodes even when they end in _g."""

    def test_regular_g_node_is_helper(self):
        n = _make_mesh_node('pelvis_g', texture='NULL', is_skin=False)
        assert OBJExporter._is_deformation_helper(n), \
            "pelvis_g (no texture) must be a deformation helper"

    def test_npc_eyeball_g_not_helper(self):
        """NPC eyeball node ending in _g but with a real texture is NOT a helper."""
        n = _make_mesh_node('f_rlweye_g', texture='npc_eye')
        assert not OBJExporter._is_deformation_helper(n), \
            "f_rlweye_g with real texture must NOT be a deformation helper"

    def test_null_texture_eyeball_not_helper(self):
        """An eyeball node even with NULL texture must not be a deformation helper."""
        n = _make_mesh_node('lseyeball01', texture='NULL')
        assert not OBJExporter._is_deformation_helper(n), \
            "lseyeball01 must never be a deformation helper"

    def test_extreme_uv_non_facial_is_helper(self):
        n = _make_mesh_node('torso_mesh', texture='body',
                            uvs=[(10.0, 10.0), (20.0, 20.0), (15.0, 15.0)])
        assert OBJExporter._is_deformation_helper(n), \
            "Extreme-UV non-facial mesh must be a deformation helper"

    def test_extreme_uv_eyeball_not_helper(self):
        """Eyeball nodes are never deformation helpers even with extreme UVs."""
        n = _make_mesh_node('lseyeball01', texture='eye_tex',
                            uvs=[(10.0, 10.0), (20.0, 20.0), (15.0, 15.0)])
        assert not OBJExporter._is_deformation_helper(n), \
            "Eyeball node must never be classified as a deformation helper"


# ─────────────────────────────────────────────────────────────────────────────
# 4.  _renderable_mesh_nodes includes facial nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestRenderableMeshNodesIncludesFacial:
    """_renderable_mesh_nodes() returns facial geometry nodes."""

    def test_head_mesh_with_facial_nodes(self):
        body  = _make_mesh_node('body_skin', texture='body_tex', is_skin=True)
        eye_l = _make_mesh_node('lseyeball01', texture='eye_tex')
        eye_r = _make_mesh_node('rseyeball01', texture='eye_tex')
        teeth = _make_mesh_node('teethlower', texture='teeth_tex')
        tongue= _make_mesh_node('tongue', texture='tongue_tex')
        model = _make_model('test_head', [body, eye_l, eye_r, teeth, tongue])

        renderable = _renderable_mesh_nodes(model)
        names = {n.name for n in renderable}
        assert 'lseyeball01' in names, "Left eyeball must be in renderable nodes"
        assert 'rseyeball01' in names, "Right eyeball must be in renderable nodes"
        assert 'teethlower'  in names, "Teethlower must be in renderable nodes"
        assert 'tongue'      in names, "Tongue must be in renderable nodes"

    def test_render_false_facial_nodes_included(self):
        """Facial nodes with render=False must still appear in _renderable_mesh_nodes."""
        eye = _make_mesh_node('lseyeball01', texture='eye_tex', render=False)
        model = _make_model('test_head', [eye])
        renderable = _renderable_mesh_nodes(model)
        assert any(n.name == 'lseyeball01' for n in renderable), \
            "lseyeball01 with render=False must be in renderable nodes"

    def test_deform_helpers_excluded(self):
        """Deformation helper nodes must not appear in _renderable_mesh_nodes."""
        helper = _make_mesh_node('pelvis_g', texture='NULL', is_skin=False)
        model = _make_model('test_body', [helper])
        renderable = _renderable_mesh_nodes(model)
        assert not any(n.name == 'pelvis_g' for n in renderable), \
            "pelvis_g helper must be excluded from renderable nodes"


# ─────────────────────────────────────────────────────────────────────────────
# 5.  FBX export includes facial geometry nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestFBXExportFacialNodes:
    """FBX exporter includes eye/teeth/tongue geometry."""

    def _make_head_model(self):
        nodes = [
            _make_mesh_node('head_skin',   texture='pfhc01',   is_skin=True),
            _make_mesh_node('lseyeball01', texture='lseye01',  render=True),
            _make_mesh_node('rseyeball01', texture='rseye01',  render=True),
            _make_mesh_node('teethlower',  texture='teeth',    render=True),
            _make_mesh_node('teethupper',  texture='teeth',    render=True),
            _make_mesh_node('tongue',      texture='tongue_t', render=True),
        ]
        return _make_model('pfhc01', nodes)

    def test_facial_nodes_in_fbx(self):
        model = self._make_head_model()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            ok = FBXExporter().export(model, path, export_rigging=False)
            assert ok, "FBX export must succeed"
            content = open(path).read()
            assert 'lseyeball01' in content, "lseyeball01 must be in FBX"
            assert 'rseyeball01' in content, "rseyeball01 must be in FBX"
            assert 'teethlower'  in content, "teethlower must be in FBX"
            assert 'teethupper'  in content, "teethupper must be in FBX"
            assert 'tongue'      in content, "tongue must be in FBX"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_facial_render_false_in_fbx(self):
        """Facial nodes with render=False must still appear in the exported FBX."""
        nodes = [
            _make_mesh_node('head_skin', texture='pfhc01', is_skin=True),
            _make_mesh_node('lseyeball01', texture='eye', render=False),
            _make_mesh_node('teethlower',  texture='tth', render=False),
        ]
        model = _make_model('pfhc01_test', nodes)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            ok = FBXExporter().export(model, path, export_rigging=False)
            assert ok
            content = open(path).read()
            assert 'lseyeball01' in content
            assert 'teethlower'  in content
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_deform_helpers_not_in_fbx(self):
        """Deformation helpers must NOT appear in the exported FBX geometry."""
        nodes = [
            _make_mesh_node('body_skin', texture='body', is_skin=True),
            _make_mesh_node('pelvis_g',  texture='NULL', is_skin=False),
        ]
        model = _make_model('p_male', nodes)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            ok = FBXExporter().export(model, path, export_rigging=False)
            assert ok
            content = open(path).read()
            # pelvis_g geometry should not appear as a Mesh node (it may appear
            # as a skeleton LimbNode — that is acceptable)
            import re
            mesh_sections = re.findall(r'Model: \d+, "Model::([^"]+)", "Mesh"', content)
            assert 'pelvis_g' not in mesh_sections, \
                "pelvis_g must not be exported as a Mesh geometry node"
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# 6.  merge_supermodel_animations
# ─────────────────────────────────────────────────────────────────────────────

class TestMergeSupermodelAnimations:
    """merge_supermodel_animations() correctly imports clips from base skeleton."""

    def test_copies_missing_animations(self):
        child  = _make_model('body')
        parent = _make_model('S_MALE02')
        parent.animations = [
            _make_animation('walk'),
            _make_animation('run'),
            _make_animation('attack1'),
        ]
        result = merge_supermodel_animations(child, parent)
        names = {a.name for a in result.animations}
        assert 'walk'    in names
        assert 'run'     in names
        assert 'attack1' in names

    def test_does_not_duplicate_existing_animations(self):
        child = _make_model('body')
        child.animations = [_make_animation('walk')]
        parent = _make_model('S_MALE02')
        parent.animations = [_make_animation('walk'), _make_animation('run')]
        result = merge_supermodel_animations(child, parent)
        walk_count = sum(1 for a in result.animations if a.name == 'walk')
        assert walk_count == 1, "Existing 'walk' must not be duplicated"
        assert any(a.name == 'run' for a in result.animations), \
            "'run' from parent must be added"

    def test_child_animations_take_priority(self):
        """Child's own animation overrides parent animation of the same name."""
        child = _make_model('body')
        child_walk = _make_animation('walk', length=2.0)  # different length
        child.animations = [child_walk]
        parent = _make_model('S_MALE02')
        parent_walk = _make_animation('walk', length=1.0)
        parent.animations = [parent_walk]
        result = merge_supermodel_animations(child, parent)
        walk = next(a for a in result.animations if a.name == 'walk')
        assert walk.length == 2.0, "Child walk animation must not be overwritten"

    def test_empty_parent_is_safe(self):
        child = _make_model('body')
        child.animations = [_make_animation('walk')]
        parent = _make_model('S_MALE02')
        parent.animations = []
        result = merge_supermodel_animations(child, parent)
        assert len(result.animations) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 7.  FBX AnimStack per-clip output
# ─────────────────────────────────────────────────────────────────────────────

class TestFBXAnimStackPerClip:
    """Each KotOR animation clip is exported as a separate AnimStack in the FBX."""

    def _animated_model(self, n_anims: int = 3) -> KotorModel:
        body = _make_mesh_node('body_skin', texture='body', is_skin=True)
        model = _make_model('char_test', [body])
        model.animations = [
            _make_animation(f'anim_{i}', length=float(i + 1))
            for i in range(n_anims)
        ]
        return model

    def test_animstack_count_matches_animations(self):
        model = self._animated_model(3)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            ok = FBXExporter().export(model, path, export_rigging=False)
            assert ok
            content = open(path).read()
            # Count AnimationStack entries
            import re
            stacks = re.findall(r'AnimationStack:', content)
            assert len(stacks) == 3, \
                f"Expected 3 AnimationStack entries, got {len(stacks)}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_each_anim_name_in_fbx(self):
        model = self._animated_model(3)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            FBXExporter().export(model, path, export_rigging=False)
            content = open(path).read()
            for i in range(3):
                assert f'anim_{i}' in content, \
                    f"Animation 'anim_{i}' must appear in FBX"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_takes_section_lists_all_clips(self):
        model = self._animated_model(4)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            FBXExporter().export(model, path, export_rigging=False)
            content = open(path).read()
            assert 'Takes:' in content, "Takes section must be present"
            import re
            takes = re.findall(r'Take:\s+"([^"]+)"', content)
            assert len(takes) == 4, \
                f"Expected 4 Take entries, got {len(takes)}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_anim_local_stop_in_ticks(self):
        model = self._animated_model(1)
        model.animations[0].length = 2.0  # 2 seconds
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            FBXExporter().export(model, path, export_rigging=False)
            content = open(path).read()
            # 2.0 seconds × 46186158000 ticks/sec = 92372316000
            expected_ticks = 2 * 46186158000
            assert str(expected_ticks) in content, \
                f"LocalStop ticks {expected_ticks} must appear in FBX"
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# 8.  export_full_character_fbx integration
# ─────────────────────────────────────────────────────────────────────────────

class TestExportFullCharacterFbx:
    """Full-pipeline integration tests for export_full_character_fbx."""

    def _make_body(self, anim_names=('walk', 'run')) -> KotorModel:
        body_mesh = _make_mesh_node('body_skin', texture='pmbc1', is_skin=True)
        # Add a headhook bone node
        headhook = ModelNode()
        headhook.name = 'headhook'
        headhook.flags = 0          # dummy/attachment-point node (no MESH/SKIN flags)
        headhook.position = (0.0, 0.0, 1.8)
        headhook.orientation = (0.0, 0.0, 0.0, 1.0)
        headhook.children = []
        headhook.parent = None
        headhook.vertices = []
        model = _make_model('p_malebody01', [body_mesh, headhook])
        model.supermodel = 'S_MALE02'
        model.animations = [_make_animation(n) for n in anim_names]
        return model

    def _make_head(self, with_eyes=True) -> KotorModel:
        nodes = [
            _make_mesh_node('head_skin',   texture='pfhc01', is_skin=True),
        ]
        if with_eyes:
            nodes += [
                _make_mesh_node('lseyeball01', texture='lseye01'),
                _make_mesh_node('rseyeball01', texture='rseye01'),
                _make_mesh_node('teethlower',  texture='teeth'),
                _make_mesh_node('tongue',      texture='tongue_t'),
            ]
        model = _make_model('pfhc01', nodes)
        model.animations = [_make_animation('blink')]
        return model

    def test_basic_export_succeeds(self):
        body = self._make_body()
        head = self._make_head()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok'], f"Export failed: {result['message']}"
            assert os.path.exists(path), "FBX file must exist after export"
            assert os.path.getsize(path) > 100, "FBX file must be non-empty"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_facial_nodes_detected(self):
        body = self._make_body()
        head = self._make_head(with_eyes=True)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok']
            assert 'lseyeball01' in result['facial_nodes'], \
                "lseyeball01 must be in facial_nodes"
            assert 'teethlower' in result['facial_nodes'], \
                "teethlower must be in facial_nodes"
            assert 'tongue' in result['facial_nodes'], \
                "tongue must be in facial_nodes"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_animations_merged(self):
        """Head and body animations are both present in the exported FBX."""
        body = self._make_body(anim_names=('walk', 'run'))
        head = self._make_head()
        head.animations = [_make_animation('blink'), _make_animation('jawopen')]
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok']
            # Body has walk+run, head has blink+jawopen → combined should have all 4
            assert result['anim_count'] == 4, \
                f"Expected 4 merged animations, got {result['anim_count']}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_base_skeleton_animations_merged(self):
        """Base skeleton animations are merged when base_skeleton_model is supplied."""
        body = self._make_body(anim_names=('walk',))
        head = self._make_head()
        head.animations = []

        base_skel = _make_model('S_MALE02')
        base_skel.animations = [
            _make_animation('walk'),      # duplicate — must not double
            _make_animation('run'),
            _make_animation('attack1'),
            _make_animation('attack2'),
            _make_animation('cpause1'),
        ]
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path,
                base_skeleton_model=base_skel,
                export_rigging=False)
            assert result['ok']
            # walk (from body) + run/attack1/attack2/cpause1 (from base skeleton)
            # = 5 total (no duplication of 'walk')
            assert result['anim_count'] == 5, \
                f"Expected 5 animations, got {result['anim_count']}"
            assert result['base_skeleton'] == 'S_MALE02'
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_no_head_model_still_exports(self):
        """export_full_character_fbx with head_model=None still produces an FBX."""
        body = self._make_body()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, None, path, export_rigging=False)
            # Should succeed (body-only export with a warning)
            assert result['ok'], f"Body-only export failed: {result['message']}"
            assert any('head' in w.lower() for w in result['warnings']), \
                "Warning about missing head model must be present"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_no_body_returns_error(self):
        result = export_full_character_fbx(None, None, '/tmp/no_body.fbx')
        assert not result['ok']
        assert 'body' in result['message'].lower()

    def test_fbx_contains_facial_nodes(self):
        """Exported FBX file content includes eye/teeth/tongue geometry."""
        body = self._make_body()
        head = self._make_head(with_eyes=True)
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok']
            content = open(path).read()
            assert 'lseyeball01' in content
            assert 'teethlower'  in content
            assert 'tongue'      in content
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_head_attached_at_headhook(self):
        """The head's root node becomes a child of the headhook bone."""
        body = self._make_body()
        head = self._make_head()
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok']
            # The FBX should contain a parent-child connection from headhook
            content = open(path).read()
            # headhook node must appear in FBX
            assert 'headhook' in content
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_fbx_has_animstack_per_animation(self):
        """Each animation appears as a distinct AnimStack in the FBX output."""
        body = self._make_body(anim_names=('walk', 'run', 'attack1'))
        head = self._make_head()
        head.animations = []
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            result = export_full_character_fbx(
                body, head, path, export_rigging=False)
            assert result['ok']
            content = open(path).read()
            import re
            stacks = re.findall(r'AnimationStack:', content)
            assert len(stacks) == 3, \
                f"Expected 3 AnimationStack entries, got {len(stacks)}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_originals_not_mutated(self):
        """export_full_character_fbx must not modify the original models."""
        body = self._make_body()
        head = self._make_head()
        orig_body_anims = list(body.animations)
        orig_head_nodes = list(head.root_node.children) if head.root_node else []
        with tempfile.NamedTemporaryFile(suffix='.fbx', delete=False) as f:
            path = f.name
        try:
            export_full_character_fbx(body, head, path, export_rigging=False)
            # Body animations must not have grown (head's 'blink' was merged
            # into the deep-copy, not the original)
            assert len(body.animations) == len(orig_body_anims), \
                "Original body model's animation list must not be mutated"
            # Head's children count must not change
            if head.root_node:
                assert len(head.root_node.children) == len(orig_head_nodes), \
                    "Original head model's node tree must not be mutated"
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# 9.  NPC inner-geo substring matching (regression)
# ─────────────────────────────────────────────────────────────────────────────

class TestNPCInnerGeoSubstringMatching:
    """Regression tests for NPC-style inner geometry node naming conventions."""

    @pytest.mark.parametrize("name,texture", [
        # Standard substrings
        ('f_rlweye_g',  'npc_e'),
        ('f_llweye_g',  'npc_e'),
        ('eyeLA',       'eye_t'),
        ('eyeRA',       'eye_t'),
        ('eyeLlid',     'lid_t'),
        ('eyeRlid',     'lid_t'),
        ('teethU',      'tth_t'),
        ('teethL',      'tth_t'),
        ('teethUa',     'tth_t'),
        ('teethLa',     'tth_t'),
        ('jaw2',        'jaw_t'),
        ('jawbone_g',   'jaw_t'),
        ('gumsmesh',    'gum_t'),
    ])
    def test_npc_names_are_facial_geo(self, name, texture):
        n = _make_mesh_node(name, texture=texture)
        assert OBJExporter._is_facial_geometry(n), \
            f"NPC inner-geo node '{name}' must be facial geometry"

    @pytest.mark.parametrize("name", [
        'pelvis_g', 'torso_g', 'head_g', 'lthigh_g',
        'rforearm_g', 'rootdummy', 'nulldummy',
    ])
    def test_bone_helper_names_not_facial(self, name):
        n = _make_mesh_node(name, texture='NULL')
        assert not OBJExporter._is_facial_geometry(n), \
            f"Bone helper '{name}' must NOT be facial geometry"


# ─────────────────────────────────────────────────────────────────────────────
# 9.  FBX Export Routing Fixes (Phase 33)
#     Ensures the ASCII FBX fallback always runs and produces valid output.
# ─────────────────────────────────────────────────────────────────────────────

class TestFBXExportRouting:
    """FBXExporter.export() must always produce a valid FBX file via the ASCII
    fallback even when pyassimp is installed but returns failure."""

    def _minimal_model_with_skin(self) -> KotorModel:
        """Return a model with a properly populated skin mesh + one animation."""
        from core.model_data import VertexSkinData, BoneWeight, Animation, ModelNode
        m = _make_model('routing_test')
        mesh = _make_mesh_node('skin_mesh', is_skin=True, texture='tex')
        mesh.bone_map = ['pelvis', 'torso']
        mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(1, 0.8)]),
        ]
        m.root_node.children.append(mesh)
        mesh.parent = m.root_node
        m.animations = [_make_animation('walk', 1.0)]
        return m

    def test_fbx_file_created(self, tmp_path):
        """FBXExporter.export() must create a non-empty FBX file."""
        model = self._minimal_model_with_skin()
        fbx_path = str(tmp_path / 'test_routing.fbx')
        ok = FBXExporter().export(model, fbx_path, export_rigging=False)
        assert ok, "export() must return True"
        assert os.path.exists(fbx_path), "FBX file must be created"
        assert os.path.getsize(fbx_path) > 500, "FBX file must be non-trivially sized"

    def test_fbx_has_header(self, tmp_path):
        """Exported FBX must start with the FBXHeaderExtension block."""
        model = self._minimal_model_with_skin()
        fbx_path = str(tmp_path / 'test_header.fbx')
        FBXExporter().export(model, fbx_path, export_rigging=False)
        with open(fbx_path) as f:
            content = f.read()
        assert 'FBXHeaderExtension' in content, "FBX must have header"
        assert 'FBXVersion: 7400' in content, "FBX version must be 7400"

    def test_skin_data_bool_does_not_crash(self, tmp_path):
        """Exporter must not crash when skin_data is a bool (legacy models)."""
        from core.model_data import VertexSkinData
        m = _make_model('bool_skin_test')
        mesh = _make_mesh_node('body_mesh', is_skin=True, texture='tex')
        mesh.bone_map = ['pelvis']
        mesh.skin_data = True  # legacy / test-assembled model — bool, not list
        m.root_node.children.append(mesh)
        mesh.parent = m.root_node
        fbx_path = str(tmp_path / 'bool_skin.fbx')
        ok = FBXExporter().export(m, fbx_path, export_rigging=False)
        assert ok, "export() must succeed even with skin_data=True"
        assert os.path.exists(fbx_path) and os.path.getsize(fbx_path) > 0

    def test_skin_data_none_does_not_crash(self, tmp_path):
        """Exporter must not crash when skin_data is None."""
        m = _make_model('none_skin_test')
        mesh = _make_mesh_node('body_mesh', is_skin=True, texture='tex')
        mesh.bone_map = ['pelvis']
        mesh.skin_data = None
        m.root_node.children.append(mesh)
        mesh.parent = m.root_node
        fbx_path = str(tmp_path / 'none_skin.fbx')
        ok = FBXExporter().export(m, fbx_path, export_rigging=False)
        assert ok, "export() must succeed even with skin_data=None"

    def test_skin_data_flat_bonewt_list_does_not_crash(self, tmp_path):
        """Exporter must not crash when skin_data is a flat list of BoneWeight."""
        from core.model_data import BoneWeight
        m = _make_model('flat_bw_test')
        mesh = _make_mesh_node('body_mesh', is_skin=True, texture='tex')
        mesh.bone_map = ['pelvis']
        # Flat list – each element is a BoneWeight, not VertexSkinData
        mesh.skin_data = [BoneWeight(0, 1.0), BoneWeight(0, 1.0), BoneWeight(0, 1.0)]
        m.root_node.children.append(mesh)
        mesh.parent = m.root_node
        fbx_path = str(tmp_path / 'flat_bw.fbx')
        ok = FBXExporter().export(m, fbx_path, export_rigging=False)
        assert ok, "export() must handle flat BoneWeight list"


# ─────────────────────────────────────────────────────────────────────────────
# 10.  UE5 AnimStack Naming Convention
#      Unreal Engine 5's FBX importer requires AnimStack names in the
#      "|<ClipName>" format to correctly identify individual animation clips.
# ─────────────────────────────────────────────────────────────────────────────

class TestUE5AnimStackNaming:
    """AnimStack objects in the exported FBX must use the |<name> convention."""

    def _export_model_with_anims(self, tmp_path, anim_names):
        """Build a model with the given animations and return FBX content."""
        m = _make_model('ue5_naming_test')
        m.animations = [_make_animation(name) for name in anim_names]
        fbx_path = str(tmp_path / 'ue5_naming.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            return f.read()

    def test_single_anim_uses_pipe_prefix(self, tmp_path):
        """A single animation must appear as AnimationStack with |name format."""
        content = self._export_model_with_anims(tmp_path, ['walk'])
        assert '|walk' in content, "AnimationStack name must use |walk format for UE5"

    def test_multiple_anims_all_use_pipe_prefix(self, tmp_path):
        """All animation clips must use the |<name> pipe-prefix format."""
        anims = ['walk', 'run', 'attack1', 'cpause1', 'idle']
        content = self._export_model_with_anims(tmp_path, anims)
        for name in anims:
            assert f'|{name}' in content, \
                f"AnimationStack for '{name}' must use |{name} format"

    def test_animstack_count_matches_anim_count(self, tmp_path):
        """Number of AnimationStack entries must equal the number of animations."""
        anims = ['walk', 'run', 'attack1']
        content = self._export_model_with_anims(tmp_path, anims)
        stack_count = content.count('AnimationStack:')
        assert stack_count == len(anims), \
            f"Expected {len(anims)} AnimationStack entries, got {stack_count}"

    def test_takes_section_lists_all_anims(self, tmp_path):
        """Takes section must list every animation regardless of anim.nodes."""
        anims = ['walk', 'run', 'idle']
        m = _make_model('takes_test')
        # Mix: some animations with nodes, some without (merged from base skeleton)
        for i, name in enumerate(anims):
            a = _make_animation(name) if i % 2 == 0 else \
                __import__('core.model_data', fromlist=['Animation']).Animation()
            a.name = name
            a.length = 1.0
            if not hasattr(a, 'nodes'):
                a.nodes = []
            m.animations.append(a)
        fbx_path = str(tmp_path / 'takes_all.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            content = f.read()
        for name in anims:
            assert f'Take: "{name}"' in content, \
                f"Takes section must include '{name}' even with empty anim.nodes"

    def test_anim_without_nodes_gets_animstack(self, tmp_path):
        """An animation with no keyframe nodes must still emit an AnimStack."""
        from core.model_data import Animation
        m = _make_model('empty_nodes_test')
        a = Animation()
        a.name = 'cpause1'
        a.length = 2.5
        a.transition_time = 0.25
        a.nodes = []   # inherited from base skeleton – no body-specific nodes
        m.animations = [a]
        fbx_path = str(tmp_path / 'empty_nodes.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            content = f.read()
        assert 'AnimationStack:' in content, "AnimStack must be emitted"
        assert '|cpause1' in content, "AnimStack must use |cpause1 name"
        assert 'Take: "cpause1"' in content, "Takes must include cpause1"


# ─────────────────────────────────────────────────────────────────────────────
# 11.  Skin Deformer Cluster Quality
#      Verifies that SubDeformer cluster blocks are written with proper
#      Indexes and Weights arrays for UE5 skeletal mesh import.
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinClusterQuality:
    """SubDeformer clusters must contain Indexes and Weights arrays."""

    def _export_skinned_model(self, tmp_path):
        from core.model_data import VertexSkinData, BoneWeight
        m = _make_model('cluster_test')
        mesh = _make_mesh_node('body_mesh', is_skin=True, texture='tex')
        mesh.bone_map = ['pelvis', 'torso']
        mesh.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 0.5), BoneWeight(1, 0.5)]),
            VertexSkinData(influences=[BoneWeight(1, 1.0)]),
        ]
        m.root_node.children.append(mesh)
        mesh.parent = m.root_node
        fbx_path = str(tmp_path / 'cluster_quality.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            return f.read()

    def test_subdeformer_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert 'SubDeformer:' in content, "SubDeformer cluster must be present"

    def test_indexes_array_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert 'Indexes:' in content, "SubDeformer must have Indexes array"

    def test_weights_array_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert 'Weights:' in content, "SubDeformer must have Weights array"

    def test_transform_link_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert 'TransformLink:' in content, "SubDeformer must have TransformLink matrix"

    def test_deformer_skin_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert '"Skin"' in content, "Skin Deformer block must be present"

    def test_bind_pose_present(self, tmp_path):
        content = self._export_skinned_model(tmp_path)
        assert 'BindPose' in content, "BindPose block must be present"


# ─────────────────────────────────────────────────────────────────────────────
# 12.  Facial Geometry Render=False FBX Export (Phase 33 regression)
#      Validates that facial nodes with render=False reach the FBX even
#      when pyassimp's return value could have short-circuited the path.
# ─────────────────────────────────────────────────────────────────────────────

class TestFacialRenderFalsePipelineRegression:
    """Full-pipeline regression: facial nodes with render=False must appear in FBX."""

    def test_eyes_teeth_tongue_in_fbx_when_render_false(self, tmp_path):
        """Eyes, teeth, and tongue with render=False must be exported."""
        m = _make_model('facial_render_false')
        for node_name, tex in [
            ('lseyeball01', 'pfhc01e'),
            ('rseyeball01', 'pfhc01e'),
            ('teethlower', 'pfhc01t'),
            ('teethupper', 'pfhc01t'),
            ('tongue', 'pfhc01t'),
        ]:
            n = _make_mesh_node(node_name, texture=tex, render=False)
            m.root_node.children.append(n)
            n.parent = m.root_node

        fbx_path = str(tmp_path / 'facial_false.fbx')
        ok = FBXExporter().export(m, fbx_path, export_rigging=False)
        assert ok
        with open(fbx_path) as f:
            content = f.read()
        for name in ('lseyeball01', 'rseyeball01', 'teethlower', 'teethupper', 'tongue'):
            assert name in content, f"Facial node '{name}' must appear in FBX"

    def test_npc_eyeball_g_in_fbx(self, tmp_path):
        """NPC-style eyeball nodes (f_rlweye_g) must appear in FBX."""
        m = _make_model('npc_eye_test')
        for node_name in ('f_rlweye_g', 'f_llweye_g', 'eyeLA', 'eyeRA'):
            n = _make_mesh_node(node_name, texture='npc_eye_tex', render=False)
            m.root_node.children.append(n)
            n.parent = m.root_node
        fbx_path = str(tmp_path / 'npc_eye.fbx')
        ok = FBXExporter().export(m, fbx_path, export_rigging=False)
        assert ok
        with open(fbx_path) as f:
            content = f.read()
        for name in ('f_rlweye_g', 'f_llweye_g', 'eyeLA', 'eyeRA'):
            assert name in content, f"NPC eyeball '{name}' must appear in FBX"


# ─────────────────────────────────────────────────────────────────────────────
# 13.  Animation Controller Format Compatibility
#      Both list-of-dicts and dict-keyed-by-type controller formats must work.
# ─────────────────────────────────────────────────────────────────────────────

class TestControllerFormatCompatibility:
    """The FBX exporter must handle both controller storage formats."""

    def _make_anim_with_controllers(self, ctrl_format='list'):
        """Build animation node with controllers in list or dict format."""
        from core.model_data import Animation, ModelNode
        anim = Animation()
        anim.name = 'ctrl_test'
        anim.length = 1.0
        anim.transition_time = 0.25
        anim.nodes = []
        an = ModelNode()
        an.name = 'pelvis'
        an.position = (0.0, 0.0, 0.0)
        an.orientation = (0.0, 0.0, 0.0, 1.0)
        an.children = []
        an.parent = None
        an.vertices = []
        if ctrl_format == 'list':
            an.controllers = [
                {'type': 8,  'times': [0.0, 1.0],
                 'values': [(0.0, 0.0, 0.0), (0.0, 0.0, 0.1)]},
                {'type': 20, 'times': [0.0, 1.0],
                 'values': [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)]},
            ]
        else:  # dict keyed by type int (legacy format)
            an.controllers = {
                8:  {'times': [0.0, 1.0],
                     'values': [(0.0, 0.0, 0.0), (0.0, 0.0, 0.1)]},
                20: {'times': [0.0, 1.0],
                     'values': [(0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)]},
            }
        anim.nodes = [an]
        return anim

    def test_list_format_controllers_export(self, tmp_path):
        """List-of-dicts controller format must produce AnimationCurve entries."""
        m = _make_model('list_ctrl_test')
        m.root_node.children.append(
            __import__('core.model_data', fromlist=['ModelNode']).ModelNode())
        # add a pelvis bone node
        from core.model_data import ModelNode
        pelvis = ModelNode()
        pelvis.name = 'pelvis'
        pelvis.flags = 0
        pelvis.position = (0.0, 0.0, 0.0)
        pelvis.orientation = (0.0, 0.0, 0.0, 1.0)
        pelvis.children = []
        pelvis.parent = m.root_node
        pelvis.vertices = []
        m.root_node.children.append(pelvis)
        m.animations = [self._make_anim_with_controllers('list')]
        fbx_path = str(tmp_path / 'list_ctrl.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            content = f.read()
        assert 'AnimationCurve:' in content, \
            "List-format controllers must produce AnimationCurve entries"

    def test_dict_format_controllers_export(self, tmp_path):
        """Dict-keyed-by-type controller format must also produce AnimationCurve entries."""
        m = _make_model('dict_ctrl_test')
        from core.model_data import ModelNode
        pelvis = ModelNode()
        pelvis.name = 'pelvis'
        pelvis.flags = 0
        pelvis.position = (0.0, 0.0, 0.0)
        pelvis.orientation = (0.0, 0.0, 0.0, 1.0)
        pelvis.children = []
        pelvis.parent = m.root_node
        pelvis.vertices = []
        m.root_node.children.append(pelvis)
        m.animations = [self._make_anim_with_controllers('dict')]
        fbx_path = str(tmp_path / 'dict_ctrl.fbx')
        FBXExporter()._export_fbx_ascii(m, fbx_path)
        with open(fbx_path) as f:
            content = f.read()
        assert 'AnimationCurve:' in content, \
            "Dict-format controllers must produce AnimationCurve entries"


# ─────────────────────────────────────────────────────────────────────────────
# 14.  Full Character Export – UE5 Import Readiness
#      Validates that export_full_character_fbx produces a file that contains
#      ALL sections required by Unreal Engine 5's FBX skeletal mesh importer.
# ─────────────────────────────────────────────────────────────────────────────

class TestUE5ImportReadiness:
    """The exported FBX must contain every section UE5 needs."""

    def _make_body_with_headhook(self) -> KotorModel:
        from core.model_data import VertexSkinData, BoneWeight, ModelNode
        m = _make_model('pfbc01_body')
        # Body mesh
        body = _make_mesh_node('body_mesh', texture='pfbc01_', is_skin=True)
        body.bone_map = ['pelvis', 'torso']
        body.skin_data = [
            VertexSkinData(influences=[BoneWeight(0, 1.0)]),
            VertexSkinData(influences=[BoneWeight(1, 1.0)]),
            VertexSkinData(influences=[BoneWeight(0, 0.5), BoneWeight(1, 0.5)]),
        ]
        m.root_node.children.append(body)
        body.parent = m.root_node
        # Headhook bone
        hh = ModelNode()
        hh.name = 'headhook'
        hh.flags = 0
        hh.position = (0.0, 0.0, 1.8)
        hh.orientation = (0.0, 0.0, 0.0, 1.0)
        hh.children = []
        hh.parent = m.root_node
        hh.vertices = []
        m.root_node.children.append(hh)
        m.animations = [
            _make_animation('walk', 1.0),
            _make_animation('run', 0.75),
        ]
        return m

    def _make_head_model(self) -> KotorModel:
        from core.model_data import ModelNode
        m = _make_model('pfhc01_head')
        for name, tex, render in [
            ('head_mesh', 'pfhc01_', True),
            ('lseyeball01', 'pfhc01e', False),
            ('rseyeball01', 'pfhc01e', False),
            ('teethlower', 'pfhc01t', False),
            ('tongue', 'pfhc01t', False),
        ]:
            n = _make_mesh_node(name, texture=tex, render=render)
            m.root_node.children.append(n)
            n.parent = m.root_node
        m.animations = [_make_animation('blink', 0.5), _make_animation('jawopen', 0.3)]
        return m

    def test_ue5_fbx_has_all_required_sections(self, tmp_path):
        """Full character FBX must have all UE5-required sections."""
        body = self._make_body_with_headhook()
        head = self._make_head_model()
        fbx_path = str(tmp_path / 'ue5_char.fbx')
        result = export_full_character_fbx(
            body_model=body,
            head_model=head,
            fbx_path=fbx_path,
            export_rigging=False,
        )
        assert result['ok'], f"Export failed: {result['message']}"
        with open(fbx_path) as f:
            content = f.read()

        # Every section UE5's FBX importer needs for a skeletal mesh
        required = {
            'FBXHeaderExtension':  'FBX file header',
            'GlobalSettings':      'Global coordinate settings',
            'Objects:':            'Objects block',
            'AnimationStack:':     'Animation stacks (clips)',
            'AnimationLayer:':     'Animation layers',
            'Takes:':              'Takes section (legacy)',
            'Deformer:':           'Skin deformer',
            'Pose':                'Bind pose',
            'Connections:':        'Connections block',
        }
        for token, description in required.items():
            assert token in content, f"Missing UE5 section: {description} ({token!r})"

    def test_ue5_fbx_all_animations_present(self, tmp_path):
        """All merged animations must appear in the FBX."""
        body = self._make_body_with_headhook()
        head = self._make_head_model()
        fbx_path = str(tmp_path / 'ue5_all_anims.fbx')
        result = export_full_character_fbx(
            body_model=body,
            head_model=head,
            fbx_path=fbx_path,
            export_rigging=False,
        )
        assert result['ok'], result['message']
        with open(fbx_path) as f:
            content = f.read()
        # walk + run from body, blink + jawopen from head = 4 clips
        for anim_name in ('walk', 'run', 'blink', 'jawopen'):
            assert anim_name in content, \
                f"Animation '{anim_name}' missing from exported FBX"

    def test_ue5_fbx_facial_nodes_present(self, tmp_path):
        """All facial geometry nodes must appear in the FBX."""
        body = self._make_body_with_headhook()
        head = self._make_head_model()
        fbx_path = str(tmp_path / 'ue5_facial.fbx')
        result = export_full_character_fbx(
            body_model=body,
            head_model=head,
            fbx_path=fbx_path,
            export_rigging=False,
        )
        assert result['ok'], result['message']
        with open(fbx_path) as f:
            content = f.read()
        for node_name in ('lseyeball01', 'rseyeball01', 'teethlower', 'tongue'):
            assert node_name in content, \
                f"Facial node '{node_name}' missing from FBX"

    def test_ue5_animstack_naming(self, tmp_path):
        """AnimStack names must use the UE5-required |<name> format."""
        body = self._make_body_with_headhook()
        fbx_path = str(tmp_path / 'ue5_naming.fbx')
        result = export_full_character_fbx(
            body_model=body,
            head_model=None,
            fbx_path=fbx_path,
            export_rigging=False,
        )
        assert result['ok']
        with open(fbx_path) as f:
            content = f.read()
        # Each walk/run AnimStack must appear with | prefix
        for name in ('walk', 'run'):
            assert f'|{name}' in content, \
                f"AnimStack for '{name}' must use UE5 |{name} naming format"

    def test_result_dict_has_correct_keys(self, tmp_path):
        """export_full_character_fbx must return a complete result dict."""
        body = self._make_body_with_headhook()
        fbx_path = str(tmp_path / 'result_keys.fbx')
        result = export_full_character_fbx(body_model=body, head_model=None,
                                           fbx_path=fbx_path,
                                           export_rigging=False)
        required_keys = {'ok', 'fbx_path', 'anim_count', 'node_count',
                         'mesh_count', 'facial_nodes', 'warnings', 'message'}
        assert required_keys.issubset(result.keys()), \
            f"Missing keys: {required_keys - set(result.keys())}"
        assert isinstance(result['ok'], bool)
        assert isinstance(result['facial_nodes'], list)
        assert isinstance(result['warnings'], list)
        assert isinstance(result['anim_count'], int)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
