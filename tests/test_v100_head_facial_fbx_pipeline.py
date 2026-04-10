"""
test_v100_head_facial_fbx_pipeline.py
======================================
Tests for the three major fixes introduced in the head-model / FBX-export
pipeline overhaul:

  A. Facial geometry detection (mesh_converter._is_facial_geometry)
       – Prefix-match names: lseyeball01, teethlower, tongue, eyelidl …
       – Substring-match NPC names: f_rlweye_g, f_llweye_g, f_teetha_g, jawskin …
       – render=False bypass: facial nodes are still renderable even with render=0
       – Deformation-helper exclusion: _g/_dum helpers never misclassified as facial

  B. FBX AnimStack / Takes per animation clip
       – Every KotOR animation clip → separate AnimationStack object in FBX
       – Every AnimationStack → separate Take: entry in Takes block
       – Correct LocalStop / ReferenceStop tick values
       – AnimStack → AnimLayer connections in Connections block

  C. export_full_character_fbx pipeline
       – body-only export (head=None) succeeds
       – body + head: head attached under headhook bone
       – Facial nodes in head are found and force-enabled (render=True)
       – Animations from head merged into combined model
       – base_skeleton animations merged (priority: body > head > base)
       – FBX contains skeleton + skin clusters + animations
       – merge_supermodel injects missing bones from base skeleton
"""
from __future__ import annotations

import os
import sys
import copy
import tempfile
import pytest

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
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mesh_node(name: str, texture: str = 'tex', render: bool = True,
               skin: bool = False, uvs=None, verts=None) -> ModelNode:
    n = ModelNode()
    n.name     = name
    n.texture  = texture
    n.render   = render
    n.flags    = (NodeFlags.SKIN | NodeFlags.MESH) if skin else NodeFlags.MESH
    n.uvs      = uvs if uvs is not None else [(0.1, 0.2), (0.3, 0.4)]
    n.vertices = verts if verts is not None else [(0.0, 0.0, 0.0),
                                                   (1.0, 0.0, 0.0),
                                                   (0.0, 1.0, 0.0)]
    n.faces    = [(0, 1, 2)]
    n.normals  = [(0.0, 0.0, 1.0)] * 3
    return n


def _bone_node(name: str) -> ModelNode:
    n = ModelNode()
    n.name  = name
    n.flags = NodeFlags.HEADER
    return n


def _anim(name: str, length: float = 1.0, with_nodes: bool = True):
    """Create a minimal Animation object.

    Animation.nodes is List[ModelNode].  Each ModelNode has a .controllers
    list of dicts: {'type': int, 'times': list, 'values': list}.
    CTRL_POSITION=8, CTRL_ORIENTATION=20.
    """
    from core.model_data import Animation
    a = Animation()
    a.name   = name
    a.length = length
    a.nodes  = []
    if with_nodes:
        # anim.nodes = list of ModelNode objects that carry keyframe controllers
        an = ModelNode()
        an.name = 'pelvis'
        an.controllers = [{
            'type':   8,           # CTRL_POSITION
            'times':  [0.0, length],
            'values': [[0.0, 0.0, 0.0], [0.0, 0.0, 0.1]],
        }]
        a.nodes = [an]
    return a


def _simple_body() -> KotorModel:
    """Body model: root dummy → pelvis bone → body mesh (skin)."""
    m = KotorModel()
    m.name       = 'pmbc1'
    m.supermodel = 'S_MALE02'

    root = _bone_node('pmbc1')
    root.position = (0.0, 0.0, 0.0)

    pelvis = _bone_node('pelvis')
    pelvis.position = (0.0, 0.0, 0.9)
    pelvis.parent   = root
    root.children   = [pelvis]

    # headhook bone – required for head attachment
    headhook = _bone_node('headhook')
    headhook.position = (0.0, 0.0, 1.7)
    headhook.parent   = pelvis
    pelvis.children   = [headhook]

    body = _mesh_node('bodymesh', texture='pmbc1', skin=True)
    body.parent = pelvis
    body.bone_map   = ['pelvis']
    body.skin_data  = [type('SD', (), {
        'influences': [BoneWeight(0, 1.0)]
    })()]
    # bodymesh is a child of pelvis (sibling of headhook)
    pelvis.children  = [headhook, body]
    headhook.children = []

    m.root_node = root
    m.animations = [_anim('cpause1'), _anim('walk'), _anim('run')]
    return m


def _simple_head(with_facial: bool = True) -> KotorModel:
    """Head model: root → head_g bone → face mesh + optional eyes/teeth/tongue."""
    m = KotorModel()
    m.name       = 'pmhc1'
    m.supermodel = 'S_MALE02'

    root = _bone_node('pmhc1')
    root.position = (0.0, 0.0, 0.0)

    head_g = _bone_node('head_g')
    head_g.position = (0.0, 0.0, 0.1)
    head_g.parent   = root
    root.children   = [head_g]

    face = _mesh_node('face01', texture='pmhc1', skin=True)
    face.parent = head_g

    nodes = [face]
    if with_facial:
        eye_l = _mesh_node('lseyeball01', texture='lseyeball01')
        eye_r = _mesh_node('rseyeball01', texture='rseyeball01')
        teeth = _mesh_node('teethlower',  texture='mouthc1')
        tongue = _mesh_node('tongue',     texture='mouthc1')

        for nd in (eye_l, eye_r, teeth, tongue):
            nd.parent = head_g

        nodes += [eye_l, eye_r, teeth, tongue]

    head_g.children = nodes
    m.root_node = root
    m.animations = [_anim('head_blink', 0.5)]
    return m


def _simple_base_skeleton() -> KotorModel:
    """Minimal base skeleton: root → pelvis → spine → head chain + many animations."""
    m = KotorModel()
    m.name = 'S_MALE02'
    m.supermodel = 'NULL'

    root   = _bone_node('S_MALE02')
    pelvis = _bone_node('pelvis');   pelvis.parent  = root
    spine  = _bone_node('spine');    spine.parent   = pelvis
    head   = _bone_node('head');     head.parent    = spine
    root.children   = [pelvis]
    pelvis.children = [spine]
    spine.children  = [head]
    head.children   = []

    m.root_node  = root
    m.animations = [
        _anim('cpause1'),   # body already has this → should NOT be duplicated
        _anim('walk'),      # body already has this → NOT duplicated
        _anim('run'),       # body already has this → NOT duplicated
        _anim('attack1'),   # new clip → SHOULD be merged
        _anim('attack2'),   # new clip → SHOULD be merged
        _anim('talk'),      # new clip → SHOULD be merged
        _anim('dead1'),     # new clip → SHOULD be merged
    ]
    return m


# ═════════════════════════════════════════════════════════════════════════════
# A — Facial geometry detection
# ═════════════════════════════════════════════════════════════════════════════

class TestFacialGeometryDetection:
    """OBJExporter._is_facial_geometry / _is_deformation_helper / _is_renderable."""

    # ── A1: Standard K1/K2 PC head prefix names ──────────────────────────────

    @pytest.mark.parametrize("name", [
        'lseyeball01', 'rseyeball01',
        'lssupeyeball01', 'rssupeyeball01',
        'teethlower', 'teethupper', 'teeth01',
        'tongue', 'tongue_geo',
        'eyelidl', 'eyelidr',
    ])
    def test_prefix_names_are_facial(self, name):
        n = _mesh_node(name, texture='tex', uvs=[(0.1,0.2)])
        assert OBJExporter._is_facial_geometry(n), \
            f"'{name}' should be facial geometry"

    # ── A2: NPC inner-geo substring names ────────────────────────────────────

    @pytest.mark.parametrize("name,texture", [
        ('f_rlweye_g',  'eyetex'),   # NPC right-eye ending in _g
        ('f_llweye_g',  'eyetex'),   # NPC left-eye ending in _g
        ('f_teetha_g',  'mouthc1'),  # NPC teeth ending in _g
        ('jawskin',     'headtex'),  # jaw substring, non-_g
        ('gumskin01',   'headtex'),  # gum substring
        ('tonguemesh',  'mouthtex'), # tongue substring non-prefix
        ('eyelid_mesh', 'headtex'),  # eyelid substring
    ])
    def test_npc_substring_names_are_facial(self, name, texture):
        n = _mesh_node(name, texture=texture, uvs=[(0.1,0.2)])
        assert OBJExporter._is_facial_geometry(n), \
            f"NPC node '{name}' should be facial geometry"

    # ── A3: NPC facial nodes NOT classified as deformation helpers ────────────

    @pytest.mark.parametrize("name", [
        'f_rlweye_g', 'f_llweye_g', 'f_teetha_g',
        'lseyeball01', 'teethlower',
    ])
    def test_facial_never_deform_helper(self, name):
        n = _mesh_node(name, texture='real_tex', uvs=[(0.1,0.2)])
        assert not OBJExporter._is_deformation_helper(n), \
            f"Facial node '{name}' must never be a deformation helper"

    # ── A4: render=False does NOT exclude facial nodes from export ────────────

    @pytest.mark.parametrize("name", [
        'lseyeball01', 'rseyeball01', 'teethlower', 'tongue',
        'f_rlweye_g', 'f_llweye_g',
    ])
    def test_render_false_bypassed_for_facial(self, name):
        n = _mesh_node(name, texture='tex', render=False)
        n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        assert OBJExporter._is_renderable(n), \
            f"Facial node '{name}' with render=False must still be renderable"

    # ── A5: Non-facial _g nodes with null texture remain helpers ─────────────

    @pytest.mark.parametrize("name", [
        'pelvis_g', 'torso_g', 'lbicep_g', 'rthigh_g', 'head_g_deform',
    ])
    def test_nonfacial_g_nodes_are_helpers(self, name):
        n = _mesh_node(name, texture='NULL', uvs=[(0.1,0.2)])
        n.flags = NodeFlags.MESH   # not a skin node
        assert OBJExporter._is_deformation_helper(n), \
            f"Non-facial _g node '{name}' should be a deformation helper"

    # ── A6: Bone-helper 'jaw_g' with null texture is NOT facial ──────────────

    def test_jaw_g_with_null_texture_is_not_facial(self):
        """jaw_g with texture=NULL is a skeleton helper, NOT facial geometry."""
        n = _mesh_node('jaw_g', texture='NULL', uvs=[(0.1,0.2)])
        n.flags = NodeFlags.MESH
        # Not facial because it has no real texture
        assert not OBJExporter._is_facial_geometry(n)

    # ── A7: Eyeball with extreme UVs is still facial (bypass UV gate) ─────────

    def test_eyeball_extreme_uvs_still_facial(self):
        """lseyeball01 should always be facial regardless of UV values."""
        n = _mesh_node('lseyeball01', texture='eyetex',
                       uvs=[(5.0, 5.0), (-4.0, 3.5)])  # extreme UVs
        assert OBJExporter._is_facial_geometry(n)
        assert not OBJExporter._is_deformation_helper(n)

    # ── A8: _renderable_mesh_nodes includes facial nodes from a model ─────────

    def test_renderable_mesh_nodes_includes_facial(self):
        body = _simple_body()
        head = _simple_head(with_facial=True)

        # Attach head to body
        hook = next((n for n in body.all_nodes()
                     if n.name.lower() == 'headhook'), None)
        if hook is None:
            hook = body.root_node
        hr = head.root_node
        hr.parent = hook
        if not hasattr(hook, 'children') or hook.children is None:
            hook.children = []
        hook.children.append(hr)

        renderable = _renderable_mesh_nodes(body)
        names = [n.name for n in renderable]
        assert 'lseyeball01' in names, "lseyeball01 must be in renderable nodes"
        assert 'rseyeball01' in names, "rseyeball01 must be in renderable nodes"
        assert 'teethlower'  in names, "teethlower must be in renderable nodes"
        assert 'tongue'      in names, "tongue must be in renderable nodes"

    # ── A9: render=False on eyeball forced to True by export_full_character_fbx

    def test_export_forces_render_true_on_facial_nodes(self, tmp_path):
        body = _simple_body()
        head = _simple_head(with_facial=True)

        # Forcibly set render=False on all facial nodes in the head
        for n in head.all_nodes():
            if OBJExporter._is_facial_geometry(n):
                n.render = False

        fbx_path = str(tmp_path / 'forced_render_test.fbx')
        result = export_full_character_fbx(
            body_model=body,
            head_model=head,
            fbx_path=fbx_path,
        )
        # Should still export successfully with facial nodes included
        assert result['ok'], f"Export failed: {result['message']}"
        assert result['facial_nodes'], \
            "facial_nodes list must not be empty when head has eyes/teeth/tongue"


# ═════════════════════════════════════════════════════════════════════════════
# B — FBX AnimStack / Takes per animation clip
# ═════════════════════════════════════════════════════════════════════════════

class TestFBXAnimationTakes:
    """Each KotOR animation clip → separate AnimStack + Take in FBX."""

    def _export_with_anims(self, tmp_path, num_anims: int = 3) -> str:
        model = KotorModel()
        model.name = 'test_char'
        root = _bone_node('test_char'); root.position = (0,0,0)
        pelvis = _bone_node('pelvis'); pelvis.position=(0,0,0.9); pelvis.parent=root
        root.children = [pelvis]
        body = _mesh_node('bodymesh', skin=True)
        body.parent = pelvis; body.bone_map=['pelvis']
        body.skin_data=[type('SD',(),{'influences':[BoneWeight(0,1.0)]})()]
        pelvis.children = [body]
        model.root_node  = root
        anim_names = [f'clip_{i:02d}' for i in range(num_anims)]
        model.animations = [_anim(n, length=1.0+i*0.25)
                            for i, n in enumerate(anim_names)]
        path = str(tmp_path / 'multi_anim.fbx')
        ok = FBXExporter().export(model, path, export_rigging=False)
        assert ok, "FBX export must succeed"
        with open(path) as f:
            return f.read()

    def test_animstack_count_matches_clip_count(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=4)
        stack_count = content.count('AnimationStack:')
        assert stack_count == 4, \
            f"Expected 4 AnimationStack objects, got {stack_count}"

    def test_takes_count_matches_clip_count(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=4)
        take_count = content.count('\tTake: "')
        assert take_count == 4, \
            f"Expected 4 Take entries in Takes block, got {take_count}"

    def test_animstack_names_match_clip_names(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=3)
        for i in range(3):
            name = f'clip_{i:02d}'
            assert f'AnimationStack: ' in content
            assert f'"{name}"' in content, \
                f"AnimStack name '{name}' not found in FBX"

    def test_takes_names_match_clip_names(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=3)
        for i in range(3):
            name = f'clip_{i:02d}'
            assert f'Take: "{name}"' in content, \
                f"Take name '{name}' not found in FBX Takes block"

    def test_localstop_nonzero_for_each_clip(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=2)
        # Each AnimStack should have LocalStop > 0
        import re
        stops = re.findall(r'"LocalStop",\s*"KTime",\s*"Time",\s*"",(\d+)', content)
        assert len(stops) >= 2
        for val in stops:
            assert int(val) > 0, f"LocalStop must be > 0, got {val}"

    def test_animlayer_connection_present(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=2)
        # Every AnimLayer must be connected to its AnimStack via "OO"
        assert content.count('"OO"') >= 2, \
            "Each AnimStack must have at least one OO connection to AnimLayer"

    def test_single_anim_model_still_has_stack_and_take(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=1)
        assert 'AnimationStack:' in content
        assert 'Take: "clip_00"' in content

    def test_takes_block_current_is_first_anim(self, tmp_path):
        content = self._export_with_anims(tmp_path, num_anims=3)
        # The 'Current:' entry in Takes block must list the first clip
        assert 'Current: "clip_00"' in content


# ═════════════════════════════════════════════════════════════════════════════
# C — export_full_character_fbx pipeline
# ═════════════════════════════════════════════════════════════════════════════

class TestExportFullCharacterFBX:

    # ── C1: Body-only export succeeds ────────────────────────────────────────

    def test_body_only_export(self, tmp_path):
        body = _simple_body()
        result = export_full_character_fbx(
            body_model=body,
            head_model=None,
            fbx_path=str(tmp_path / 'body_only.fbx'),
        )
        assert result['ok'], f"Body-only export failed: {result['message']}"
        assert result['mesh_count'] >= 1

    # ── C2: Head is attached under headhook ──────────────────────────────────

    def test_head_attached_at_headhook(self, tmp_path):
        body = _simple_body()
        head = _simple_head(with_facial=False)
        fbx_path = str(tmp_path / 'body_head.fbx')
        result = export_full_character_fbx(
            body_model=body, head_model=head, fbx_path=fbx_path)
        assert result['ok'], f"Export failed: {result['message']}"
        with open(fbx_path) as f:
            content = f.read()
        # Head root node name should appear in the FBX
        assert 'pmhc1' in content, "Head root node 'pmhc1' not found in FBX"

    # ── C3: Facial nodes are detected and listed in result ───────────────────

    def test_facial_nodes_detected(self, tmp_path):
        body = _simple_body()
        head = _simple_head(with_facial=True)
        result = export_full_character_fbx(
            body_model=body, head_model=head,
            fbx_path=str(tmp_path / 'facial.fbx'),
        )
        assert result['ok']
        facial = result['facial_nodes']
        assert 'lseyeball01' in facial, "lseyeball01 must be in facial_nodes"
        assert 'rseyeball01' in facial, "rseyeball01 must be in facial_nodes"
        assert 'teethlower'  in facial, "teethlower must be in facial_nodes"
        assert 'tongue'      in facial, "tongue must be in facial_nodes"

    # ── C4: Head animations merged into combined model ────────────────────────

    def test_head_animations_merged(self, tmp_path):
        body = _simple_body()        # has cpause1, walk, run
        head = _simple_head()        # has head_blink
        result = export_full_character_fbx(
            body_model=body, head_model=head,
            fbx_path=str(tmp_path / 'head_anim.fbx'),
        )
        assert result['ok']
        # head_blink not in body → must be merged
        assert result['anim_count'] >= 4, \
            f"Expected ≥4 animations (body3 + head1), got {result['anim_count']}"

    # ── C5: Base skeleton animations merged, no duplicates ───────────────────

    def test_base_skeleton_animations_merged_no_duplicates(self, tmp_path):
        body = _simple_body()        # has cpause1, walk, run
        head = _simple_head()        # has head_blink
        skel = _simple_base_skeleton()  # has cpause1(dup), walk(dup), run(dup),
                                         #     attack1, attack2, talk, dead1

        result = export_full_character_fbx(
            body_model=body, head_model=head,
            fbx_path=str(tmp_path / 'base_skel.fbx'),
            base_skeleton_model=skel,
        )
        assert result['ok'], f"Export failed: {result['message']}"
        # body:3 + head:1 (head_blink) + skel new:4 (attack1/2,talk,dead1) = 8
        assert result['anim_count'] == 8, \
            f"Expected 8 unique animations, got {result['anim_count']}"
        assert result['base_skeleton'] == 'S_MALE02'

    # ── C6: FBX contains correct number of AnimStack objects ─────────────────

    def test_fbx_contains_correct_animstack_count(self, tmp_path):
        body = _simple_body()   # 3 anims
        fbx_path = str(tmp_path / 'animstack.fbx')
        result = export_full_character_fbx(
            body_model=body, head_model=None, fbx_path=fbx_path)
        assert result['ok']
        with open(fbx_path) as f:
            content = f.read()
        n_stacks = content.count('AnimationStack:')
        assert n_stacks == 3, f"Expected 3 AnimStack objects, got {n_stacks}"

    # ── C7: FBX contains Takes block with one entry per clip ─────────────────

    def test_fbx_takes_count_matches_anim_count(self, tmp_path):
        body = _simple_body()   # 3 anims: cpause1, walk, run
        fbx_path = str(tmp_path / 'takes.fbx')
        result = export_full_character_fbx(
            body_model=body, head_model=None, fbx_path=fbx_path)
        assert result['ok']
        with open(fbx_path) as f:
            content = f.read()
        takes = content.count('\tTake: "')
        assert takes == 3, f"Expected 3 Take entries, got {takes}"

    # ── C8: Full pipeline → FBX has skeleton + mesh + skin clusters + anims ──

    def test_full_pipeline_fbx_structure(self, tmp_path):
        body = _simple_body()
        head = _simple_head(with_facial=True)
        skel = _simple_base_skeleton()
        fbx_path = str(tmp_path / 'full.fbx')

        result = export_full_character_fbx(
            body_model=body, head_model=head,
            fbx_path=fbx_path, base_skeleton_model=skel)
        assert result['ok'], f"Full pipeline failed: {result['message']}"

        with open(fbx_path) as f:
            content = f.read()

        assert 'AnimationStack:' in content,   "FBX must have AnimationStack"
        assert 'Takes:' in content,             "FBX must have Takes block"
        assert 'Deformer:' in content,          "FBX must have Skin Deformer"
        assert 'SubDeformer:' in content,       "FBX must have bone Clusters"
        assert 'Pose:' in content,              "FBX must have BindPose"
        assert result['anim_count'] > 0,        "Must have at least one animation"
        assert result['mesh_count'] > 0,        "Must have at least one mesh"
        assert result['facial_nodes'],          "Must have facial nodes listed"

    # ── C9: No head model → no head_blink in result animations ───────────────

    def test_body_only_no_head_animations(self, tmp_path):
        body = _simple_body()   # only cpause1, walk, run
        result = export_full_character_fbx(
            body_model=body, head_model=None,
            fbx_path=str(tmp_path / 'no_head.fbx'),
        )
        assert result['ok']
        assert result['anim_count'] == 3, \
            f"Body-only should have 3 anims, got {result['anim_count']}"

    # ── C10: merge_supermodel injects missing bones from base skeleton ─────────

    def test_merge_supermodel_injects_bones(self):
        """merge_supermodel should add spine/head bones from base skeleton."""
        body = _simple_body()   # has pelvis only
        skel = _simple_base_skeleton()  # has pelvis → spine → head

        body_nodes_before = {n.name for n in body.all_nodes()}
        assert 'spine' not in body_nodes_before
        assert 'head'  not in body_nodes_before

        merged = merge_supermodel(copy.deepcopy(body), skel)
        body_nodes_after = {n.name for n in merged.all_nodes()}

        assert 'spine' in body_nodes_after, \
            "spine bone should be injected from base skeleton"
        assert 'head' in body_nodes_after, \
            "head bone should be injected from base skeleton"

    # ── C11: result dict always contains required keys ────────────────────────

    def test_result_dict_has_required_keys(self, tmp_path):
        body = _simple_body()
        result = export_full_character_fbx(
            body_model=body, head_model=None,
            fbx_path=str(tmp_path / 'keys_check.fbx'),
        )
        for key in ('ok', 'fbx_path', 'anim_count', 'node_count',
                    'mesh_count', 'facial_nodes', 'base_skeleton',
                    'warnings', 'message'):
            assert key in result, f"result dict missing key '{key}'"

    # ── C12: FBX file actually written to disk ────────────────────────────────

    def test_fbx_file_written(self, tmp_path):
        body = _simple_body()
        fbx_path = str(tmp_path / 'written.fbx')
        result = export_full_character_fbx(
            body_model=body, head_model=None, fbx_path=fbx_path)
        assert result['ok']
        assert os.path.isfile(fbx_path), "FBX file must exist after export"
        assert os.path.getsize(fbx_path) > 500, "FBX file must not be empty"

    # ── C13: No facial-nodes warning when head lacks separate eye meshes ──────

    def test_no_facial_warning_when_head_has_no_eye_meshes(self, tmp_path):
        body = _simple_body()
        head = _simple_head(with_facial=False)
        result = export_full_character_fbx(
            body_model=body, head_model=head,
            fbx_path=str(tmp_path / 'no_facial.fbx'),
        )
        assert result['ok']
        # Should produce a warning about missing facial nodes
        warn_text = ' '.join(result['warnings']).lower()
        assert 'facial' in warn_text or result['facial_nodes'] == [], \
            "Should warn or report empty facial_nodes when head has no eye meshes"


# ═════════════════════════════════════════════════════════════════════════════
# D — merge_supermodel_animations de-duplication
# ═════════════════════════════════════════════════════════════════════════════

class TestMergeSupermodelAnimations:

    def test_merge_adds_missing_clips(self):
        child  = KotorModel(); child.name  = 'child'
        parent = KotorModel(); parent.name = 'parent'
        child.animations  = [_anim('walk'), _anim('run')]
        parent.animations = [_anim('walk'), _anim('attack1'), _anim('attack2')]

        result = merge_supermodel_animations(child, parent)
        names = [a.name for a in result.animations]
        assert 'attack1' in names
        assert 'attack2' in names
        assert names.count('walk') == 1, "walk must not be duplicated"

    def test_merge_does_not_duplicate_existing(self):
        child  = KotorModel(); child.name  = 'c'
        parent = KotorModel(); parent.name = 'p'
        child.animations  = [_anim('cpause1'), _anim('walk')]
        parent.animations = [_anim('cpause1'), _anim('walk'), _anim('run')]

        result = merge_supermodel_animations(child, parent)
        assert len(result.animations) == 3
        assert len(result.animations) == 3  # no duplicates beyond the 3 unique names

    def test_merge_with_empty_parent_is_safe(self):
        child  = KotorModel(); child.name = 'c'
        parent = KotorModel(); parent.name = 'p'
        child.animations  = [_anim('walk')]
        parent.animations = []
        result = merge_supermodel_animations(child, parent)
        assert len(result.animations) == 1

    def test_merge_with_none_parent_returns_child(self):
        child = KotorModel(); child.name = 'c'
        child.animations = [_anim('walk')]
        result = merge_supermodel_animations(child, None)
        assert result is child

    def test_merge_case_insensitive(self):
        """Animation names 'Walk' and 'walk' are the same clip."""
        child  = KotorModel(); child.name  = 'c'
        parent = KotorModel(); parent.name = 'p'
        child.animations  = [_anim('Walk')]
        parent.animations = [_anim('walk'), _anim('run')]

        result = merge_supermodel_animations(child, parent)
        names_lower = [a.name.lower() for a in result.animations]
        assert names_lower.count('walk') == 1, "Walk/walk must not be duplicated"
        assert 'run' in names_lower


# ═════════════════════════════════════════════════════════════════════════════
# E — Deformation helper exclusion regression
# ═════════════════════════════════════════════════════════════════════════════

class TestDeformHelperExclusion:

    @pytest.mark.parametrize("name,texture,skin,uvs,expected_helper", [
        # Real deformation helpers → True
        ('pelvis_g',   'NULL', False, [(0.1,0.2)], True),
        ('torso_g',    'NULL', False, [(0.1,0.2)], True),
        ('head_g',     'NULL', False, [(0.1,0.2)], True),
        ('lbicep_g',   'torso',False, [(99,99)],   True),  # extreme UVs
        # Real renderable mesh → False
        ('bodymesh',   'pmbc1', True,  [(0.1,0.2)], False),
        ('face01',     'pmhc1', True,  [(0.2,0.3)], False),
        # NPC eyeball ending in _g WITH texture + valid UVs → not helper
        ('f_rlweye_g', 'eyetex', False, [(0.1,0.2)], False),
        ('f_llweye_g', 'eyetex', False, [(0.1,0.2)], False),
    ])
    def test_deformation_helper_classification(
            self, name, texture, skin, uvs, expected_helper):
        n = _mesh_node(name, texture=texture, skin=skin, uvs=uvs)
        result = OBJExporter._is_deformation_helper(n)
        assert result == expected_helper, \
            f"'{name}': is_deformation_helper={result}, expected {expected_helper}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
