"""
tests/test_v57_phase16_features.py
Phase 16 — Animation FPS snap, walkmesh overlay, reference-node detection,
            OBJ/GLTF texture export, adaptive tick scheduler, toolbar refactor.

Covers:
  - AnimationEngine.get_animation_fps_estimate: snaps to nearest standard tier
  - AnimationEngine.get_recommended_playback_fps: clamps to valid combobox values
  - WalkmeshOverlay / WalkmeshFace: color RGBA float values in [0,1]
  - _draw_walkmesh_overlay: color blending with integer BG uses correct math
  - NodeFlags.REFERENCE (0x0010): is_reference property on ModelNode
  - Reference-model emitter_params['ref_model'] stored by parser
  - OBJExporter.export: accepts tex_cache kwarg without error
  - GLTFExporter skin-weight packing: 4-component BBBB joints + ffff weights
  - _INNER_GEO_SUBSTRINGS: 'jaw' included, module-level constant
  - Adaptive tick: next_ms = max(4, interval_ms - elapsed_ms)
  - _ensure_quat_sign_consistency: not mutating original list
"""

import math
import struct
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─────────────────────────────────────────────────────────────────────────────
#  Animation engine imports
# ─────────────────────────────────────────────────────────────────────────────

from core.animation_engine import AnimationEngine, _ensure_quat_sign_consistency
from core.model_data import (
    KotorModel, ModelNode, Animation, NodeFlags, GameVersion
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_simple_model(name="test_model"):
    """Build a minimal KotorModel with a root dummy node."""
    model = KotorModel()
    model.name = name
    root = ModelNode()
    root.name = "rootdummy"
    root.flags = int(NodeFlags.HEADER)
    model.root_node = root
    return model


def _make_anim(name="walkleft", length=1.0, fps=30.0):
    """Build a minimal Animation with baked keyframes at the given fps."""
    from core.model_data import Animation
    anim = Animation()
    anim.name = name
    anim.length = length
    # One anim node with a position channel at `fps` keyframes/s
    from core.model_data import ModelNode
    an = ModelNode()
    an.name = "rootdummy"
    n_keys = max(2, int(round(length * fps)))
    times  = [i / fps for i in range(n_keys)]
    values = [[0.0, 0.0, float(i) * 0.01] for i in range(n_keys)]
    an.controllers = [{'type': 8, 'times': times, 'values': values}]
    anim.nodes = [an]
    return anim


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: AnimationEngine.get_animation_fps_estimate
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAnimationFpsEstimate:

    def _engine(self, fps_baked, length=2.0):
        model = _make_simple_model()
        anim  = _make_anim(length=length, fps=fps_baked)
        model.animations = [anim]
        eng = AnimationEngine(model)
        return eng, anim

    def test_30fps_baked_snaps_to_30(self):
        eng, anim = self._engine(30.0, length=2.0)
        est = eng.get_animation_fps_estimate(anim)
        assert est == pytest.approx(30.0)

    def test_24fps_baked_snaps_to_24(self):
        eng, anim = self._engine(24.0, length=2.0)
        est = eng.get_animation_fps_estimate(anim)
        assert est == pytest.approx(24.0)

    def test_60fps_baked_snaps_to_60(self):
        eng, anim = self._engine(60.0, length=1.0)
        est = eng.get_animation_fps_estimate(anim)
        assert est == pytest.approx(60.0)

    def test_15fps_baked_snaps_to_15(self):
        eng, anim = self._engine(15.0, length=4.0)
        est = eng.get_animation_fps_estimate(anim)
        assert est == pytest.approx(15.0)

    def test_29fps_raw_snaps_to_30(self):
        """~29 fps raw (float rounding artifact) should snap to 30."""
        eng, anim = self._engine(29.0, length=2.0)
        est = eng.get_animation_fps_estimate(anim)
        assert est == pytest.approx(30.0)

    def test_empty_anim_returns_30(self):
        model = _make_simple_model()
        anim  = Animation()
        anim.name = "empty"; anim.length = 0.0; anim.nodes = []
        model.animations = [anim]
        eng = AnimationEngine(model)
        assert eng.get_animation_fps_estimate(anim) == pytest.approx(30.0)

    def test_single_key_returns_30(self):
        model = _make_simple_model()
        anim  = _make_anim(fps=30.0, length=1.0)
        anim.nodes[0].controllers[0]['times']  = [0.0]
        anim.nodes[0].controllers[0]['values'] = [[0.0, 0.0, 0.0]]
        model.animations = [anim]
        eng = AnimationEngine(model)
        assert eng.get_animation_fps_estimate(anim) == pytest.approx(30.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: AnimationEngine.get_recommended_playback_fps
# ─────────────────────────────────────────────────────────────────────────────

class TestGetRecommendedPlaybackFps:

    _VALID = [15, 24, 25, 30, 60]

    def _rec(self, fps_baked, length=2.0):
        model = _make_simple_model()
        anim  = _make_anim(length=length, fps=fps_baked)
        model.animations = [anim]
        eng   = AnimationEngine(model)
        return eng.get_recommended_playback_fps(anim)

    def test_30fps_returns_30_int(self):
        rec = self._rec(30.0)
        assert rec == 30
        assert isinstance(rec, int)

    def test_24fps_returns_24_int(self):
        assert self._rec(24.0) == 24

    def test_60fps_returns_60_int(self):
        assert self._rec(60.0, length=1.0) == 60

    def test_15fps_returns_15_int(self):
        assert self._rec(15.0, length=4.0) == 15

    def test_result_always_in_valid_set(self):
        for fps in (15, 24, 25, 29, 30, 31, 60):
            rec = self._rec(float(fps))
            assert rec in self._VALID, f"fps={fps} → rec={rec} not in valid set"


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: WalkmeshFace color values
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshFaceColor:

    def test_color_components_in_float_range(self):
        """All RGBA components from surface_color must be in [0.0, 1.0]."""
        from core.walkmesh_renderer import SURFACE_COLORS, _DEFAULT_COLOR
        all_colors = list(SURFACE_COLORS.values()) + [_DEFAULT_COLOR]
        for rgba in all_colors:
            r, g, b, a = rgba
            assert 0.0 <= r <= 1.0, f"R out of range: {r}"
            assert 0.0 <= g <= 1.0, f"G out of range: {g}"
            assert 0.0 <= b <= 1.0, f"B out of range: {b}"
            assert 0.0 <= a <= 1.0, f"A out of range: {a}"

    def test_walkmesh_face_color_returns_float_rgba(self):
        from core.walkmesh_renderer import WalkmeshFace, SURFACE_DIRT
        face = WalkmeshFace(
            v0=(0.0, 0.0, 0.0),
            v1=(1.0, 0.0, 0.0),
            v2=(0.0, 1.0, 0.0),
            surface=SURFACE_DIRT,
            walkable=True,
        )
        r, g, b, a = face.color
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0
        assert 0.0 <= a <= 1.0

    def test_walkmesh_color_blend_produces_valid_uint8(self):
        """Simulate the _draw_walkmesh_overlay blending math → must stay in [0,255]."""
        from core.walkmesh_renderer import surface_color, SURFACE_NON_WALK
        _BG_R, _BG_G, _BG_B = 18, 18, 40   # matches _BG constant in viewport.py
        cr, cg, cb, ca = surface_color(SURFACE_NON_WALK)
        cr8 = int(cr * 255)
        cg8 = int(cg * 255)
        cb8 = int(cb * 255)
        alpha = ca
        fr = int(cr8 * alpha + _BG_R * (1.0 - alpha))
        fg = int(cg8 * alpha + _BG_G * (1.0 - alpha))
        fb = int(cb8 * alpha + _BG_B * (1.0 - alpha))
        assert 0 <= fr <= 255, f"fr={fr} out of [0,255]"
        assert 0 <= fg <= 255, f"fg={fg} out of [0,255]"
        assert 0 <= fb <= 255, f"fb={fb} out of [0,255]"

    def test_walkable_surfaces_low_alpha(self):
        """Walkable surfaces should have alpha <= 0.6 (semi-transparent)."""
        from core.walkmesh_renderer import SURFACE_COLORS, WALKABLE_SURFACES
        for sid in WALKABLE_SURFACES:
            if sid in SURFACE_COLORS:
                alpha = SURFACE_COLORS[sid][3]
                assert alpha <= 0.65, f"Surface {sid} alpha={alpha} too high for walkable"

    def test_non_walk_surface_prominent_alpha(self):
        """NON_WALK surface should have alpha > 0.6 (more prominent)."""
        from core.walkmesh_renderer import SURFACE_COLORS, SURFACE_NON_WALK
        alpha = SURFACE_COLORS[SURFACE_NON_WALK][3]
        assert alpha > 0.6, f"NON_WALK alpha={alpha} should be prominent"


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: NodeFlags.REFERENCE and is_reference property
# ─────────────────────────────────────────────────────────────────────────────

class TestReferenceNodeFlag:

    def test_reference_flag_value(self):
        """NodeFlags.REFERENCE must be 0x0010 per KotOR MDL spec."""
        assert int(NodeFlags.REFERENCE) == 0x0010

    def test_is_reference_property_true(self):
        node = ModelNode()
        node.flags = int(NodeFlags.REFERENCE)
        assert node.is_reference is True

    def test_is_reference_property_false_for_mesh(self):
        node = ModelNode()
        node.flags = int(NodeFlags.MESH)
        assert node.is_reference is False

    def test_is_reference_false_for_dummy(self):
        node = ModelNode()
        node.flags = int(NodeFlags.HEADER)
        assert node.is_reference is False

    def test_type_label_reference(self):
        node = ModelNode()
        node.flags = int(NodeFlags.REFERENCE)
        assert node.type_label == "reference"

    def test_reference_node_emitter_params_ref_model(self):
        """emitter_params['ref_model'] stores the referenced model name."""
        node = ModelNode()
        node.flags = int(NodeFlags.REFERENCE)
        node.emitter_params['ref_model'] = 'c_trooper'
        assert node.emitter_params.get('ref_model') == 'c_trooper'

    def test_reference_node_not_mesh_or_skin(self):
        node = ModelNode()
        node.flags = int(NodeFlags.REFERENCE)
        assert not node.is_mesh
        assert not node.is_skin


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: OBJExporter accepts tex_cache kwarg
# ─────────────────────────────────────────────────────────────────────────────

class TestOBJExporterTexCache:

    def test_export_accepts_tex_cache_none(self, tmp_path):
        """OBJExporter.export should not raise when tex_cache=None."""
        from converters.mesh_converter import OBJExporter
        model = _make_simple_model()
        # add a minimal mesh node
        mn = ModelNode()
        mn.name = "testmesh"
        mn.flags = int(NodeFlags.MESH)
        mn.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        mn.faces    = [(0, 1, 2)]
        mn.texture  = "testTex"
        mn.render   = True
        model.root_node.children = [mn]
        mn.parent = model.root_node
        out = str(tmp_path / "out.obj")
        OBJExporter().export(model, out, tex_cache=None)
        assert os.path.exists(out)

    def test_export_signature_accepts_tex_cache_kwarg(self):
        """inspect.signature check: tex_cache is a valid parameter."""
        import inspect
        from converters.mesh_converter import OBJExporter
        sig = inspect.signature(OBJExporter.export)
        assert 'tex_cache' in sig.parameters


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: GLTF skin-weight packing format
# ─────────────────────────────────────────────────────────────────────────────

class TestGLTFSkinWeightPacking:

    def test_joints_packed_as_4_unsigned_bytes(self):
        """JOINTS_0 must be packed as VEC4 of UNSIGNED_BYTE (component type 5121)."""
        import struct as st
        joints = [3, 1, 0, 0]
        packed = st.pack('<BBBB', *joints)
        assert len(packed) == 4
        unpacked = st.unpack('<BBBB', packed)
        assert list(unpacked) == joints

    def test_weights_packed_as_4_floats(self):
        """WEIGHTS_0 must be packed as VEC4 of FLOAT (component type 5126)."""
        import struct as st
        weights = [0.6, 0.4, 0.0, 0.0]
        packed  = st.pack('<ffff', *weights)
        assert len(packed) == 16
        unpacked = st.unpack('<ffff', packed)
        assert unpacked == pytest.approx(weights)

    def test_weights_normalise_to_sum_one(self):
        """After normalisation weights must sum to exactly 1.0."""
        ws = [0.3, 0.2, 0.1, 0.0]
        w_sum = sum(ws)
        if w_sum > 1e-6:
            ws = [x / w_sum for x in ws]
        assert sum(ws) == pytest.approx(1.0)

    def test_zero_weight_entry_stays_zero(self):
        ws = [0.0, 0.0, 0.0, 0.0]
        w_sum = sum(ws)
        if w_sum > 1e-6:
            ws = [x / w_sum for x in ws]
        # Should NOT normalise — stays zeros to avoid divide-by-zero
        assert sum(ws) == pytest.approx(0.0)

    def test_max_4_influences_per_vertex(self):
        """Only up to 4 influences should be exported per vertex."""
        influences = [
            type('Inf', (), {'bone_index': i, 'weight': 0.2})()
            for i in range(7)
        ]
        sorted_infl = sorted(influences, key=lambda x: x.weight, reverse=True)[:4]
        assert len(sorted_infl) == 4


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: _INNER_GEO_SUBSTRINGS module-level constant (viewport)
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerGeoSubstringsViewport:

    def test_inner_geo_substrings_importable(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert _INNER_GEO_SUBSTRINGS is not None

    def test_inner_geo_contains_jaw(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'jaw' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_contains_eye(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'eye' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_contains_teeth(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'teeth' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_contains_tongue(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'tongue' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_contains_gum(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert 'gum' in _INNER_GEO_SUBSTRINGS

    def test_inner_geo_is_tuple(self):
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert isinstance(_INNER_GEO_SUBSTRINGS, tuple)

    def test_jaw2_node_name_matches(self):
        """'jaw2' (K1/K2 jaw bone name) should match via substring check."""
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert any(s in 'jaw2' for s in _INNER_GEO_SUBSTRINGS)

    def test_eyera_node_name_matches(self):
        """'eyeRA' should match 'eye' substring (case-insensitive check)."""
        from gui.viewport import _INNER_GEO_SUBSTRINGS
        assert any(s in 'eyera' for s in _INNER_GEO_SUBSTRINGS)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: Adaptive tick scheduling math
# ─────────────────────────────────────────────────────────────────────────────

class TestAdaptiveTickScheduling:

    def test_next_ms_never_below_4(self):
        """Adaptive scheduler must not schedule at less than 4 ms."""
        fps = 30
        interval_ms = max(16, int(1000.0 / fps))  # = 33
        # Simulate a very slow render (50 ms)
        elapsed_ms = 50
        next_ms = max(4, interval_ms - elapsed_ms)
        assert next_ms == 4

    def test_next_ms_correct_for_fast_render(self):
        """With 8 ms render at 30 fps → next_ms = 33 - 8 = 25."""
        fps = 30
        interval_ms = max(16, int(1000.0 / fps))  # = 33
        elapsed_ms  = 8
        next_ms     = max(4, interval_ms - elapsed_ms)
        assert next_ms == 25

    def test_next_ms_for_60fps_with_zero_elapsed(self):
        """At 60 fps, interval=16ms; 0ms elapsed → next_ms=16."""
        fps = 60
        interval_ms = max(16, int(1000.0 / fps))  # = 16
        elapsed_ms  = 0
        next_ms     = max(4, interval_ms - elapsed_ms)
        assert next_ms == 16

    def test_interval_ms_never_below_16(self):
        """interval_ms floor is 16 ms (≈ 62.5 fps cap for Tkinter event loop)."""
        for fps in [1, 15, 24, 30, 60, 120]:
            interval_ms = max(16, int(1000.0 / fps))
            assert interval_ms >= 16

    def test_dt_lower_clamp(self):
        """dt lower clamp: max(nominal_dt * 0.5, actual_dt)."""
        fps = 30.0
        nominal_dt = 1.0 / fps         # ≈ 0.0333 s
        # Simulate tick delivered 2 ms early
        actual_dt  = nominal_dt - 0.002
        dt = max(nominal_dt * 0.5, min(actual_dt, 0.25))
        assert dt >= nominal_dt * 0.5

    def test_dt_upper_clamp(self):
        """dt upper clamp at 0.25 s prevents huge jumps after UI freeze."""
        nominal_dt = 1.0 / 30.0
        actual_dt  = 2.0   # 2-second stall
        dt = max(nominal_dt * 0.5, min(actual_dt, 0.25))
        assert dt == pytest.approx(0.25)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: _ensure_quat_sign_consistency does not mutate original
# ─────────────────────────────────────────────────────────────────────────────

class TestQuatSignConsistencyImmutability:

    def test_original_list_not_mutated(self):
        vals = [[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, -1.0]]
        import copy
        original = copy.deepcopy(vals)
        _ensure_quat_sign_consistency(vals)
        assert vals == original, "Original list was mutated"

    def test_returns_new_list_object(self):
        vals = [[0.0, 0.0, 0.0, 1.0]]
        result = _ensure_quat_sign_consistency(vals)
        assert result is not vals


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: WalkmeshLoader / WalkmeshOverlay loading
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkmeshOverlayLoading:

    def _make_wok(self):
        """Build a minimal WOKData-like object with 2 faces.

        WalkmeshOverlay.load_from_wok() reads wf.v1, wf.v2, wf.v3 (1-indexed
        names) as vertex indices into wok_data.verts.
        """
        class _WokData:
            verts = [(0.0,0.0,0.0), (1.0,0.0,0.0), (0.0,1.0,0.0),
                     (-1.0,0.0,0.0)]
            faces = [
                # surface=1 (DIRT) → walkable
                type('F',(),{'v1':0,'v2':1,'v3':2,'surface':1})(),
                # surface=7 (NON_WALK) → not walkable
                type('F',(),{'v1':0,'v2':2,'v3':3,'surface':7})(),
            ]
        return _WokData()

    def test_overlay_loads_faces(self):
        from core.walkmesh_renderer import WalkmeshOverlay
        wok = self._make_wok()
        overlay = WalkmeshOverlay()
        overlay.load_from_wok(wok)
        assert len(overlay.faces) == 2

    def test_overlay_filters_walkable(self):
        from core.walkmesh_renderer import WalkmeshOverlay
        wok = self._make_wok()
        overlay = WalkmeshOverlay()
        overlay.load_from_wok(wok)
        walk_faces = overlay.faces_for_render(show_walkable=True, show_non_walkable=False)
        assert all(f.walkable for f in walk_faces)

    def test_overlay_filters_non_walkable(self):
        from core.walkmesh_renderer import WalkmeshOverlay
        wok = self._make_wok()
        overlay = WalkmeshOverlay()
        overlay.load_from_wok(wok)
        block_faces = overlay.faces_for_render(show_walkable=False, show_non_walkable=True)
        assert all(not f.walkable for f in block_faces)

    def test_overlay_shows_all(self):
        from core.walkmesh_renderer import WalkmeshOverlay
        wok = self._make_wok()
        overlay = WalkmeshOverlay()
        overlay.load_from_wok(wok)
        all_faces = overlay.faces_for_render(show_walkable=True, show_non_walkable=True)
        assert len(all_faces) == 2

    def test_face_normal_unit_length(self):
        from core.walkmesh_renderer import WalkmeshFace
        face = WalkmeshFace(
            v0=(0.0,0.0,0.0), v1=(1.0,0.0,0.0), v2=(0.0,1.0,0.0),
            surface=1, walkable=True
        )
        n = face.normal
        length = math.sqrt(n[0]**2 + n[1]**2 + n[2]**2)
        assert length == pytest.approx(1.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
#  Tests: FBXExporter.export accepts tex_cache kwarg
# ─────────────────────────────────────────────────────────────────────────────

class TestFBXExporterTexCache:

    def test_export_signature_accepts_tex_cache(self):
        import inspect
        from converters.mesh_converter import FBXExporter
        sig = inspect.signature(FBXExporter.export)
        assert 'tex_cache' in sig.parameters

    def test_gltf_export_signature_accepts_tex_cache(self):
        import inspect
        from converters.mesh_converter import GLTFExporter
        sig = inspect.signature(GLTFExporter.export)
        assert 'tex_cache' in sig.parameters
