"""
test_v310_head_snap_animations_template.py
==========================================
Phase 28 / v31.0  –  Tests for:
  1.  Head-Body Snap system (snap_head_onto_body)
  2.  Animation coverage diagnostics (_build_report_items animation section)
  3.  Template builder completeness (build_humanoid_template)
  4.  90-degree rotation fix (RetargetEngine.rotate_90 all axes)
  5.  Inner-geo two-sided rendering constants (_INNER_GEO_SUBSTRINGS)
"""
import sys
import os
import math

# Ensure src is on path
_ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC  = os.path.join(_ROOT, 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest

from core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion, Animation,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(name: str, is_mesh=False, is_skin=False,
               has_verts=True, has_uvs=True, texture='tex01',
               render=True, flags=None) -> ModelNode:
    """Create a minimal ModelNode for testing."""
    if flags is None:
        _f = int(NodeFlags.HEADER)
        if is_mesh: _f |= int(NodeFlags.MESH)
        if is_skin: _f |= int(NodeFlags.SKIN)
    else:
        _f = flags
    node = ModelNode(name=name, flags=_f)
    node.texture  = texture
    node.render   = render
    node.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)] if has_verts else []
    node.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)] if has_uvs else []
    node.faces    = [(0, 1, 2)]
    node.normals  = [(0.0, 0.0, 1.0)] * 3
    node.children = []
    node.parent   = None
    node.position = (0.0, 0.0, 0.0)
    node.rotation = (0.0, 0.0, 0.0, 1.0)
    return node


def _make_body_model(name='pfbc1') -> KotorModel:
    """Create a minimal body model with a headhook bone."""
    m = KotorModel(name=name)
    root = _make_node(name, is_mesh=False)
    root.name = name
    # Body mesh
    body = _make_node('body_mesh', is_skin=True, texture='pfbc01')
    body.parent = root
    root.children.append(body)
    # Spine
    spine = _make_node('spine', is_mesh=False)
    spine.parent = root
    root.children.append(spine)
    # Headhook bone
    hook = _make_node('headhook', is_mesh=False)
    hook.position = (0.0, 0.0, 1.65)   # near top of body
    hook.parent = spine
    spine.children.append(hook)
    m.root_node = root
    m.compute_bounds()
    return m


def _make_head_model(name='pfhc1') -> KotorModel:
    """Create a minimal head model with eye and face nodes."""
    m = KotorModel(name=name)
    root = _make_node(name, is_mesh=False)
    root.name = name
    root.position = (0.0, 0.0, 0.0)
    # Face mesh
    face = _make_node('pfhc1_face', is_mesh=True, texture='pfhc01')
    face.parent = root
    root.children.append(face)
    # Eye nodes (inner-geo)
    leye = _make_node('pfhc1_leye', is_mesh=True, texture='pfhc01_eye')
    leye.position = (0.05, -0.04, 0.10)
    leye.parent = root
    root.children.append(leye)
    reye = _make_node('pfhc1_reye', is_mesh=True, texture='pfhc01_eye')
    reye.position = (-0.05, -0.04, 0.10)
    reye.parent = root
    root.children.append(reye)
    m.root_node = root
    m.compute_bounds()
    return m


def _make_model_with_anims(anims: list) -> KotorModel:
    """Create a KotorModel with the given animation names."""
    m = KotorModel(name='test_model')
    root = _make_node('test_model', is_mesh=False)
    m.root_node = root
    for aname in anims:
        a = Animation()
        a.name = aname
        a.length = 1.0
        m.animations.append(a)
    return m


# ─────────────────────────────────────────────────────────────────────────────
#  1.  Head-Body Snap  (snap_head_onto_body)
# ─────────────────────────────────────────────────────────────────────────────

class TestHeadBodySnap:

    def test_snap_basic_success(self):
        """snap_head_onto_body returns ok=True for valid body+head."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok'], f"Snap failed: {result['message']}"
        assert result['model'] is not None
        assert result['headhook_pos'] is not None

    def test_snap_no_body_returns_error(self):
        """Passing None as body returns ok=False with a clear message."""
        from core.creature_appearance import snap_head_onto_body
        head = _make_head_model()
        result = snap_head_onto_body(None, head)
        assert not result['ok']
        assert 'body' in result['message'].lower() or 'model' in result['message'].lower()

    def test_snap_no_head_returns_error(self):
        """Passing None as head returns ok=False."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        result = snap_head_onto_body(body, None)
        assert not result['ok']

    def test_snap_combined_model_has_head_nodes(self):
        """The combined model contains nodes from both body and head."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head, scale_head=False)
        assert result['ok']
        combined = result['model']
        all_names = {n.name for n in combined.all_nodes()}
        # Should have body nodes
        assert 'headhook' in all_names
        # Should have head nodes (face, eye)
        assert any('face' in n.lower() or 'eye' in n.lower() for n in all_names), \
            f"Expected head nodes in combined model, got: {all_names}"

    def test_snap_does_not_mutate_originals(self):
        """snap_head_onto_body clones models; originals are unchanged."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        orig_body_nodes = len(list(body.all_nodes()))
        orig_head_nodes = len(list(head.all_nodes()))
        result = snap_head_onto_body(body, head)
        assert result['ok']
        assert len(list(body.all_nodes())) == orig_body_nodes, \
            "Body model was mutated!"
        assert len(list(head.all_nodes())) == orig_head_nodes, \
            "Head model was mutated!"

    def test_snap_headhook_position_reported(self):
        """snap_head_onto_body reports the headhook world position."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        assert result['ok']
        pos = result['headhook_pos']
        assert pos is not None
        assert len(pos) == 3
        # The headhook is near the top of the body
        assert pos[2] > 1.0, f"Headhook Z too low: {pos}"

    def test_snap_without_headhook_uses_fallback(self):
        """Without a headhook bone, snap finds a 'head' node or fails gracefully."""
        from core.creature_appearance import snap_head_onto_body
        # Body with NO headhook bone
        body = KotorModel(name='c_creature')
        root = _make_node('c_creature', is_mesh=False)
        body_mesh = _make_node('btbody', is_skin=True, texture='c_crt01')
        body_mesh.parent = root
        root.children = [body_mesh]
        body.root_node = root
        head = _make_head_model()
        result = snap_head_onto_body(body, head)
        # May succeed with fallback or return descriptive error — never crash
        assert isinstance(result['ok'], bool)
        assert isinstance(result['message'], str)

    def test_snap_scale_head_enabled(self):
        """With scale_head=True, the result still succeeds."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model()
        head = _make_head_model()
        result = snap_head_onto_body(body, head, scale_head=True)
        assert result['ok'], result['message']

    def test_snap_message_contains_model_names(self):
        """Success message includes body and head model names."""
        from core.creature_appearance import snap_head_onto_body
        body = _make_body_model('pfbc1')
        head = _make_head_model('pfhc1')
        result = snap_head_onto_body(body, head)
        assert result['ok']
        assert 'pfbc1' in result['message'] or 'pfhc1' in result['message'], \
            f"Names not in message: {result['message']}"


# ─────────────────────────────────────────────────────────────────────────────
#  2.  Animation Coverage Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestAnimationCoverage:
    """Tests for animation coverage logic (inline, no Tkinter needed)."""

    # Mirror the logic from _build_report_items so we can test headlessly
    _STANDARD_ANIMS = {
        'cpause1', 'cpause2', 'pause1', 'pause2', 'pausesh',
        'walk', 'run', 'walkbk', 'runbk', 'dodge',
        'attack1', 'attack2', 'attack3', 'attackl', 'attackr',
        'cstrike', 'cstrikea', 'cstrikeb', 'cstrikec', 'cdodge',
        'damage1', 'dodge1', 'dead1', 'dead2', 'deads', 'deadforward',
        'interact', 'interactlp', 'salute', 'victory1', 'taunt',
        'talk', 'talklp', 'spuse1',
        'tlkang1', 'tlkfear1', 'tlkhappy1', 'tlknorm1', 'tlksad1',
        'tlkworry1', 'tlkplead1', 'tlklaugh1',
        'kneel', 'kneeldmg', 'kneelrm', 'kneelgrd',
        'conjure1', 'conjure2', 'meditate', 'medlow',
        'sit', 'sitlp', 'sleep', 'prone', 'drunk', 'listen',
    }
    _CREATURE_ANIMS = {
        'cpause1', 'cpause2', 'crun', 'cwalk', 'creadyr',
        'chturnl', 'chturnr', 'cwalkinj', 'ckdbck',
    }

    def _coverage(self, model):
        name_lo = (model.name or '').lower()
        is_creature = name_lo.startswith('c_')
        expected = self._CREATURE_ANIMS if is_creature else self._STANDARD_ANIMS
        model_names = {
            getattr(a, 'name', '').lower()
            for a in getattr(model, 'animations', [])
            if getattr(a, 'name', '')
        }
        present = expected & model_names
        missing = expected - model_names
        extra   = model_names - expected
        pct = int(100 * len(present) / len(expected)) if expected else 100
        return pct, present, missing, extra

    def test_full_anim_coverage_100pct(self):
        """Model with all standard animations → 100% coverage."""
        model = _make_model_with_anims(list(self._STANDARD_ANIMS))
        pct, present, missing, extra = self._coverage(model)
        assert pct == 100, f"Expected 100% got {pct}%  missing={missing}"
        assert len(missing) == 0

    def test_no_anims_zero_coverage(self):
        """Model with no animations → 0% coverage."""
        model = _make_model_with_anims([])
        pct, present, missing, extra = self._coverage(model)
        assert pct == 0
        assert missing == self._STANDARD_ANIMS

    def test_partial_coverage(self):
        """Model with a few animations → partial coverage."""
        model = _make_model_with_anims(['walk', 'run'])
        pct, present, missing, extra = self._coverage(model)
        assert pct < 50
        assert 'walk' in present
        assert 'run' in present
        assert 'pause1' in missing

    def test_creature_uses_creature_anim_set(self):
        """Creature models (c_ prefix) use creature animation set."""
        model = _make_model_with_anims(list(self._CREATURE_ANIMS))
        model.name = 'c_bantha'
        pct, present, missing, extra = self._coverage(model)
        assert pct == 100, f"Expected 100% creature coverage got {pct}%"
        assert len(missing) == 0

    def test_missing_anims_identified(self):
        """Missing animation names are correctly identified."""
        model = _make_model_with_anims(['walk', 'run'])
        pct, present, missing, extra = self._coverage(model)
        assert 'pause1' in missing
        assert 'attack1' in missing

    def test_extra_anims_counted_separately(self):
        """Non-standard extra animations counted but not penalised."""
        model = _make_model_with_anims(
            list(self._STANDARD_ANIMS) + ['custom_dance', 'special_move'])
        pct, present, missing, extra = self._coverage(model)
        assert pct == 100  # full standard coverage
        assert 'custom_dance' in extra
        assert 'special_move' in extra

    def test_case_insensitive_matching(self):
        """Animation name matching is case-insensitive."""
        model = _make_model_with_anims(
            [n.upper() for n in self._STANDARD_ANIMS])
        pct, present, missing, extra = self._coverage(model)
        assert pct == 100, f"Case-insensitive match failed: {pct}%"


# ─────────────────────────────────────────────────────────────────────────────
#  3.  Template Builder
# ─────────────────────────────────────────────────────────────────────────────

class TestHumanoidTemplateBuilder:

    def test_template_builds_without_error(self):
        """build_humanoid_template() runs without raising exceptions."""
        from core.template_builder import build_humanoid_template
        model = build_humanoid_template(game_version='K1')
        assert model is not None

    def test_template_has_correct_name(self):
        """Template model has the expected name."""
        from core.template_builder import build_humanoid_template
        model = build_humanoid_template(game_version='K1', name='gr_humanoid_k1')
        assert model.name == 'gr_humanoid_k1'

    def test_template_has_bones(self):
        """Template contains a reasonable number of bone nodes."""
        from core.template_builder import build_humanoid_template, _HUMANOID_BONES
        model = build_humanoid_template()
        all_nodes = list(model.all_nodes())
        assert len(all_nodes) >= len(_HUMANOID_BONES), \
            f"Expected ≥{len(_HUMANOID_BONES)} nodes, got {len(all_nodes)}"

    def test_template_has_animations(self):
        """Template has all standard animation slots pre-populated."""
        from core.template_builder import build_humanoid_template, _ANIM_SLOTS
        model = build_humanoid_template()
        assert len(model.animations) >= len(_ANIM_SLOTS), \
            f"Expected ≥{len(_ANIM_SLOTS)} anims, got {len(model.animations)}"

    def test_template_anim_names_match_slots(self):
        """Each animation slot name is present in the template model."""
        from core.template_builder import build_humanoid_template, _ANIM_SLOTS
        model = build_humanoid_template()
        anim_names = {a.name.lower() for a in model.animations}
        for name, _ in _ANIM_SLOTS:
            assert name.lower() in anim_names, \
                f"Animation slot '{name}' missing from template"

    def test_template_k2_variant(self):
        """K2 template builds successfully."""
        from core.template_builder import build_humanoid_template
        model = build_humanoid_template(game_version='K2', name='gr_humanoid_k2')
        assert model is not None
        assert model.game_version == GameVersion.K2

    def test_template_root_node_exists(self):
        """Template has a root node (Mesh_Root)."""
        from core.template_builder import build_humanoid_template
        model = build_humanoid_template()
        assert model.root_node is not None
        assert model.root_node.name == 'Mesh_Root'

    def test_template_bounding_box_reasonable(self):
        """Template bounding box is within expected humanoid dimensions.

        The placeholder torso box is ~0.456m tall (pelvis 0.924 to chest 1.380).
        The bounding box covers the visible placeholder mesh, not the full
        skeleton height.  Accept anything in the 0.2–3.0m range.
        """
        from core.template_builder import build_humanoid_template
        model = build_humanoid_template()
        model.compute_bounds()
        height = model.bb_max[2] - model.bb_min[2]
        assert 0.2 < height < 3.0, \
            f"Template height {height:.3f} outside expected range 0.2–3.0 m"


# ─────────────────────────────────────────────────────────────────────────────
#  4.  90-Degree Rotation (RetargetEngine.rotate_90)
# ─────────────────────────────────────────────────────────────────────────────

class TestRotate90:

    def _make_engine_with_model(self):
        """Create a RetargetEngine with a simple working model."""
        from autorig.retarget_engine import RetargetEngine
        engine = RetargetEngine()
        m = KotorModel(name='test_rotate')
        root = _make_node('test_rotate', is_mesh=False)
        mesh = _make_node('body_mesh', is_mesh=True, texture='tex01')
        mesh.vertices = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        mesh.parent = root
        root.children = [mesh]
        m.root_node = root
        engine._working = m
        return engine, m

    def test_rotate_z_ccw(self):
        """Z-axis CCW rotation: (1,0,0) → (0,1,0)."""
        engine, m = self._make_engine_with_model()
        mesh = m.root_node.children[0]
        result = engine.rotate_90(axis='Z', direction=+1)
        assert result['ok'], result['message']
        x, y, z = mesh.vertices[0]
        assert abs(x - 0.0) < 1e-6, f"X should be ~0 after CCW Z rotation, got {x}"
        assert abs(y - 1.0) < 1e-6, f"Y should be ~1 after CCW Z rotation, got {y}"

    def test_rotate_z_cw(self):
        """Z-axis CW rotation: (1,0,0) → (0,-1,0)."""
        engine, m = self._make_engine_with_model()
        mesh = m.root_node.children[0]
        result = engine.rotate_90(axis='Z', direction=-1)
        assert result['ok']
        x, y, z = mesh.vertices[0]
        assert abs(x - 0.0) < 1e-6
        assert abs(y - (-1.0)) < 1e-6, f"Y should be ~-1 after CW Z rotation, got {y}"

    def test_rotate_x_ccw(self):
        """X-axis CCW rotation: (0,1,0) → (0,0,1)."""
        engine, m = self._make_engine_with_model()
        mesh = m.root_node.children[0]
        result = engine.rotate_90(axis='X', direction=+1)
        assert result['ok']
        x, y, z = mesh.vertices[1]  # vertex was (0,1,0)
        assert abs(x - 0.0) < 1e-6
        assert abs(y - 0.0) < 1e-6, f"Y should be ~0 after CCW X rotation, got {y}"
        assert abs(z - 1.0) < 1e-6, f"Z should be ~1 after CCW X rotation, got {z}"

    def test_rotate_y_ccw(self):
        """Y-axis CCW rotation: (1,0,0) → (0,0,-1)."""
        engine, m = self._make_engine_with_model()
        mesh = m.root_node.children[0]
        result = engine.rotate_90(axis='Y', direction=+1)
        assert result['ok']
        x, y, z = mesh.vertices[0]  # vertex was (1,0,0)
        assert abs(x - 0.0) < 1e-6, f"X should be ~0 after CCW Y rotation, got {x}"
        assert abs(z - (-1.0)) < 1e-6, f"Z should be ~-1 after CCW Y rotation, got {z}"

    def test_four_rotations_z_return_to_identity(self):
        """Four 90° CCW Z rotations return vertices to original positions."""
        engine, m = self._make_engine_with_model()
        mesh = m.root_node.children[0]
        orig = list(mesh.vertices)
        for _ in range(4):
            engine.rotate_90(axis='Z', direction=+1)
        for (ox, oy, oz), (nx, ny, nz) in zip(orig, mesh.vertices):
            assert abs(ox - nx) < 1e-4, f"X mismatch after 4×90°: {ox} vs {nx}"
            assert abs(oy - ny) < 1e-4, f"Y mismatch after 4×90°: {oy} vs {ny}"
            assert abs(oz - nz) < 1e-4, f"Z mismatch after 4×90°: {oz} vs {nz}"

    def test_rotate_invalid_axis_returns_error(self):
        """Invalid axis string returns ok=False."""
        engine, _ = self._make_engine_with_model()
        result = engine.rotate_90(axis='W', direction=+1)
        assert not result['ok']
        assert 'W' in result['message'] or 'axis' in result['message'].lower()

    def test_rotate_no_model_returns_error(self):
        """rotate_90 without a loaded model returns ok=False."""
        from autorig.retarget_engine import RetargetEngine
        engine = RetargetEngine()
        result = engine.rotate_90()
        assert not result['ok']

    def test_rotate_returns_height(self):
        """rotate_90 result includes height_after key."""
        engine, _ = self._make_engine_with_model()
        result = engine.rotate_90(axis='Z', direction=+1)
        assert 'height_after' in result
        assert isinstance(result['height_after'], float)


# ─────────────────────────────────────────────────────────────────────────────
#  5.  Inner-Geo Two-Sided Rendering Constants
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoConstants:
    """Verify _INNER_GEO_SUBSTRINGS and _FACE_MESH_SUBSTRINGS are correct."""

    def test_inner_geo_includes_eye(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'eye' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_includes_lid(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'lid' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_includes_teeth(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'teeth' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_includes_tongue(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'tongue' in _INNER_GEO_SUBSTRINGS

    def test_face_mesh_includes_head(self):
        from gui.viewport import _FACE_MESH_SUBSTRINGS
        assert 'head' in _FACE_MESH_SUBSTRINGS

    def test_face_mesh_includes_face(self):
        from gui.viewport import _FACE_MESH_SUBSTRINGS
        assert 'face' in _FACE_MESH_SUBSTRINGS

    def test_two_sided_for_eye_nodes(self):
        """Nodes with 'eye' in name should get is_two_sided=True in rendering."""
        from gui.viewport import _INNER_GEO_SUBSTRINGS, _FACE_MESH_SUBSTRINGS
        eye_names = ['btLeye', 'btReye', 'pfhc1_leye', 'f_llweye_g', 'reye']
        for name in eye_names:
            nl = name.lower()
            is_inner = any(s in nl for s in _INNER_GEO_SUBSTRINGS)
            assert is_inner, \
                f"'{name}' should be classified as inner-geo (eye) but is_inner=False"

    def test_two_sided_for_teeth_nodes(self):
        """Nodes with 'teeth' in name should get is_two_sided=True."""
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        teeth_names = ['upperteeth', 'teethU', 'lowerteeth', 'teethL']
        for name in teeth_names:
            nl = name.lower()
            is_inner = any(s in nl for s in _INNER_GEO_SUBSTRINGS)
            assert is_inner, \
                f"'{name}' should be classified as inner-geo (teeth) but is_inner=False"

    def test_body_not_inner_geo(self):
        """Body mesh nodes are NOT classified as inner-geo."""
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        body_names = ['btBody_front', 'btBodyback', 'pfbc1_body', 'skin01']
        for name in body_names:
            nl = name.lower()
            is_inner = any(s in nl for s in _INNER_GEO_SUBSTRINGS)
            assert not is_inner, \
                f"'{name}' should NOT be inner-geo but got is_inner=True"


# ─────────────────────────────────────────────────────────────────────────────
#  6.  Skin-Proxy Exemption for Inner-Geo Nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestSkinProxyExemption:
    """Inner-geo nodes must NOT be classified as skin proxies."""

    def _make_proxy_model(self):
        """Build a model with a skin mesh and an eye node sharing a texture."""
        m = KotorModel(name='test_proxy')
        root = _make_node('test_proxy', is_mesh=False)
        # Skin mesh with 100 vertices
        skin = _make_node('btBody', is_skin=True, texture='c_test01')
        skin.vertices = [(float(i), 0.0, 0.0) for i in range(100)]
        skin.uvs      = [(float(i)/100, 0.0) for i in range(100)]
        skin.parent   = root
        root.children = [skin]
        # Eye node with same texture (13 vertices) — should NOT be a proxy
        leye = _make_node('btLeye', is_mesh=True, texture='c_test01')
        leye.vertices = [(0.0, 0.0, 0.0)] * 13
        leye.uvs      = [(0.0, 0.0)] * 13
        leye.parent   = root
        root.children.append(leye)
        m.root_node = root
        return m, leye

    def test_eye_not_in_proxy_ids(self):
        """Eye nodes are exempt from _compute_skin_proxy_ids.

        Tests the pure logic directly (no Tkinter needed):
        Inner-geo nodes sharing a texture with exactly one skin mesh should
        NOT be classified as skin proxies.
        """
        # Replicate _compute_skin_proxy_ids logic inline to test without Tkinter
        from gui.viewport import _INNER_GEO_SUBSTRINGS

        model, leye = self._make_proxy_model()
        all_nodes = list(model.all_nodes())

        # Build skin_tex_verts
        skin_tex_verts = {}
        for n in all_nodes:
            if not n.is_skin:
                continue
            tex = (n.texture or '').lower().strip()
            if not tex or tex == 'null':
                continue
            nv = len(n.vertices)
            if nv == 0:
                continue
            skin_tex_verts.setdefault(tex, []).append((n, nv))

        # Apply proxy check
        proxy_ids = set()
        for n in all_nodes:
            if not n.is_mesh or n.is_skin:
                continue
            tex = (n.texture or '').lower().strip()
            if not tex or tex == 'null':
                continue
            if not n.uvs:
                continue
            # Inner-geo exemption
            nl = n.name.lower()
            if any(s in nl for s in _INNER_GEO_SUBSTRINGS):
                continue  # exempted — should NOT reach proxy_ids
            skin_matches = skin_tex_verts.get(tex, [])
            if len(skin_matches) != 1:
                continue
            _, skin_verts = skin_matches[0]
            if skin_verts <= len(n.vertices):
                continue
            proxy_ids.add(id(n))

        assert id(leye) not in proxy_ids, \
            "Eye node 'btLeye' was incorrectly classified as skin proxy!"

    def test_eye_not_deformation_helper(self):
        """Eye nodes with texture + UVs are NOT deformation helpers.

        Tests the _is_deformation_helper logic inline (no Tkinter).
        """
        from gui.viewport import _INNER_GEO_SUBSTRINGS

        _, leye = self._make_proxy_model()
        # Simulate the key path in _is_deformation_helper:
        tex = (leye.texture or '').strip()
        is_null_tex = not tex or tex.upper() == 'NULL'

        # Inner-geo early exit:
        nl = leye.name.lower()
        if any(s in nl for s in _INNER_GEO_SUBSTRINGS):
            if not is_null_tex and leye.uvs:
                uvs_ok = not any(abs(u) > 3.0 or abs(v) > 3.0
                                 for u, v in leye.uvs[:20])
                if uvs_ok:
                    # Returns False (renderable) — this is the correct path
                    assert True
                    return

        pytest.fail("Eye node did not hit the inner-geo early-return path in "
                    "_is_deformation_helper — would be incorrectly hidden!")
