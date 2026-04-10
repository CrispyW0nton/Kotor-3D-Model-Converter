"""
Phase 24.1 – Model Orientation / Axis-Alignment Tests
======================================================
Tests for ModelOrientFixer and RetargetEngine.orient_model().

KotOR (Odyssey engine) uses Z-up right-handed coordinates:
  X = right,  Y = forward,  Z = up (height)

Source application conventions:
  Blender / Maya OBJ export  → Y-up  (most common user problem)
  3ds Max / Cinema4D / KotOR → Z-up  (already correct)
  Rare legacy workflows      → X-up
"""
import sys
import math
import tempfile
import os
import pytest

sys.path.insert(0, "src")

from core.model_data import ModelNode, NodeFlags, KotorModel, GameVersion
from autorig.retarget_engine import (
    RetargetEngine, RetargetStage,
    OrientationMode, ModelOrientFixer,
)
from converters.mesh_converter import OBJImporter


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_model(verts, name="test") -> KotorModel:
    """Build a minimal KotorModel with a single mesh node using the given verts."""
    model = KotorModel(name=name, game_version=GameVersion.K1)
    root  = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    node  = ModelNode(name="mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=root)
    node._imported = True
    node.render    = True
    node.texture   = ""
    node.vertices  = list(verts)
    node.uvs       = [(0, 0)] * len(verts)
    node.faces     = []
    for i in range(1, len(verts) - 1):
        node.faces.append((0, i, i + 1))
    root.children  = [node]
    model.root_node = root
    model.compute_bounds()
    return model


def _yup_model(height=1.8) -> KotorModel:
    """Character with height along Y (Blender OBJ export convention)."""
    return _make_model([
        (-0.3,    0.0, -0.1),  # foot L
        ( 0.3,    0.0, -0.1),  # foot R
        ( 0.3, height,  0.1),  # head R
        (-0.3, height,  0.1),  # head L
    ])


def _zup_model(height=1.8) -> KotorModel:
    """Character with height along Z (KotOR / 3ds Max convention)."""
    return _make_model([
        (-0.3, -0.1,    0.0),
        ( 0.3, -0.1,    0.0),
        ( 0.3,  0.1, height),
        (-0.3,  0.1, height),
    ])


def _xup_model(height=1.8) -> KotorModel:
    """Character with height along X (unusual)."""
    return _make_model([
        (  0.0, -0.1, -0.3),
        (  0.0, -0.1,  0.3),
        (height, 0.1,  0.3),
        (height, 0.1, -0.3),
    ])


def _spans(model: KotorModel):
    model.compute_bounds()
    mn, mx = model.bb_min, model.bb_max
    return (mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2])


# ─────────────────────────────────────────────────────────────────────────────
# OrientationMode.detect()
# ─────────────────────────────────────────────────────────────────────────────

class TestDetect:
    def test_detect_yup(self):
        assert ModelOrientFixer.detect(_yup_model()) == OrientationMode.YUP

    def test_detect_zup(self):
        assert ModelOrientFixer.detect(_zup_model()) == OrientationMode.ZUP

    def test_detect_xup(self):
        assert ModelOrientFixer.detect(_xup_model()) == OrientationMode.XUP

    def test_detect_degenerate_defaults_to_zup(self):
        m = _make_model([(0, 0, 0), (0, 0, 0), (0, 0, 0)])
        assert ModelOrientFixer.detect(m) == OrientationMode.ZUP

    def test_detect_cube_defaults_to_zup(self):
        """Equal spans → ZUP (already correct, no rotation)."""
        m = _make_model([(-1,-1,-1),(1,-1,-1),(1,1,1),(-1,1,1)])
        assert ModelOrientFixer.detect(m) == OrientationMode.ZUP


# ─────────────────────────────────────────────────────────────────────────────
# ModelOrientFixer.apply() – rotation
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyRotation:
    def test_yup_to_zup_height_axis_becomes_z(self):
        m = _yup_model(height=1.8)
        result = ModelOrientFixer.apply(m, mode=OrientationMode.YUP, floor_snap=False)
        dx, dy, dz = _spans(m)
        # After rotation, Z span should be the tall dimension
        assert dz == pytest.approx(1.8, abs=0.01)
        assert result["rotation_applied"] is True

    def test_yup_to_zup_detected_mode(self):
        m = _yup_model()
        result = ModelOrientFixer.apply(m, mode=OrientationMode.AUTO)
        assert result["detected_mode"] == OrientationMode.YUP
        assert result["rotation_applied"] is True

    def test_zup_no_rotation(self):
        m = _zup_model()
        result = ModelOrientFixer.apply(m, mode=OrientationMode.ZUP, floor_snap=False)
        assert result["rotation_applied"] is False
        assert result["detected_mode"] == OrientationMode.ZUP

    def test_xup_to_zup_height_axis_becomes_z(self):
        m = _xup_model(height=1.8)
        result = ModelOrientFixer.apply(m, mode=OrientationMode.XUP, floor_snap=False)
        dx, dy, dz = _spans(m)
        assert dz == pytest.approx(1.8, abs=0.01)
        assert result["rotation_applied"] is True

    def test_auto_yup_same_as_explicit_yup(self):
        m1 = _yup_model()
        m2 = _yup_model()
        ModelOrientFixer.apply(m1, mode=OrientationMode.AUTO,  floor_snap=False)
        ModelOrientFixer.apply(m2, mode=OrientationMode.YUP,   floor_snap=False)
        # Bounds should be identical
        m1.compute_bounds()
        m2.compute_bounds()
        for i in range(3):
            assert m1.bb_min[i] == pytest.approx(m2.bb_min[i], abs=1e-6)
            assert m1.bb_max[i] == pytest.approx(m2.bb_max[i], abs=1e-6)

    def test_normals_also_rotated(self):
        m = _make_model([(-0.3, 0.0, -0.1), (0.3, 0.0, -0.1),
                         (0.3, 1.8, 0.1), (-0.3, 1.8, 0.1)])
        n = m.root_node.children[0]
        n.normals = [(0.0, 0.0, 1.0)] * len(n.vertices)  # Y-up normal = Z
        ModelOrientFixer.apply(m, mode=OrientationMode.YUP, floor_snap=False)
        # After Y-up→Z-up rotation: (0,0,1) → (0,-1,0)
        assert n.normals[0] == pytest.approx((0.0, -1.0, 0.0), abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Floor-snap
# ─────────────────────────────────────────────────────────────────────────────

class TestFloorSnap:
    def test_floor_snap_sets_min_z_to_zero(self):
        m = _yup_model(height=1.8)
        ModelOrientFixer.apply(m, mode=OrientationMode.YUP, floor_snap=True)
        m.compute_bounds()
        assert m.bb_min[2] == pytest.approx(0.0, abs=1e-6)

    def test_floor_snap_applied_flag(self):
        m = _zup_model()
        # Shift model upward so it's not floor-snapped
        n = m.root_node.children[0]
        n.vertices = [(v[0], v[1], v[2] + 2.0) for v in n.vertices]
        m.compute_bounds()
        result = ModelOrientFixer.apply(m, mode=OrientationMode.ZUP, floor_snap=True)
        assert result["floor_snap_applied"] is True

    def test_no_floor_snap_respects_flag(self):
        m = _yup_model()
        ModelOrientFixer.apply(m, mode=OrientationMode.YUP, floor_snap=False)
        m.compute_bounds()
        # min_z should NOT necessarily be 0
        # (model was at Y=0 before rotation, which becomes Z=0 after; so it
        # may still be 0 naturally — but floor_snap_applied should be False)
        result = ModelOrientFixer.apply(
            _yup_model(), mode=OrientationMode.YUP, floor_snap=False
        )
        assert result["floor_snap_applied"] is False

    def test_floor_snap_height_preserved(self):
        m = _yup_model(height=2.0)
        ModelOrientFixer.apply(m, mode=OrientationMode.YUP, floor_snap=True)
        dx, dy, dz = _spans(m)
        assert dz == pytest.approx(2.0, abs=0.02)

    def test_floor_snap_message_includes_delta(self):
        m = _zup_model()
        n = m.root_node.children[0]
        n.vertices = [(v[0], v[1], v[2] + 0.5) for v in n.vertices]
        m.compute_bounds()
        result = ModelOrientFixer.apply(m, mode=OrientationMode.ZUP, floor_snap=True)
        assert "floor-snap" in result["message"].lower() or "Δz" in result["message"]


# ─────────────────────────────────────────────────────────────────────────────
# Center XZ
# ─────────────────────────────────────────────────────────────────────────────

class TestCenterXZ:
    def test_center_xz_puts_centroid_at_origin(self):
        m = _make_model([(1, 2, 0), (3, 4, 0), (5, 6, 0)])
        ModelOrientFixer.apply(m, mode=OrientationMode.ZUP,
                               floor_snap=False, center_xz=True)
        m.compute_bounds()
        cx = (m.bb_min[0] + m.bb_max[0]) / 2.0
        cy = (m.bb_min[1] + m.bb_max[1]) / 2.0
        assert cx == pytest.approx(0.0, abs=1e-5)
        assert cy == pytest.approx(0.0, abs=1e-5)

    def test_no_center_by_default(self):
        m = _make_model([(2, 2, 0), (4, 4, 0), (6, 6, 0)])
        ModelOrientFixer.apply(m, mode=OrientationMode.ZUP,
                               floor_snap=False, center_xz=False)
        m.compute_bounds()
        cx = (m.bb_min[0] + m.bb_max[0]) / 2.0
        # Should not be at origin
        assert cx != pytest.approx(0.0, abs=1e-5)


# ─────────────────────────────────────────────────────────────────────────────
# RetargetEngine.orient_model()
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineOrientModel:
    def _import_yup(self):
        engine = RetargetEngine()
        model  = _yup_model(height=1.75)
        r = engine.set_imported_model(model)
        assert r["ok"]
        return engine

    def test_orient_before_import_fails(self):
        engine = RetargetEngine()
        r = engine.orient_model()
        assert r["ok"] is False

    def test_orient_yup_model_corrects_height(self):
        engine = self._import_yup()
        r = engine.orient_model(mode=OrientationMode.YUP, floor_snap=True)
        assert r["ok"]
        assert r["rotation_applied"] is True
        assert r["height_after"] == pytest.approx(1.75, abs=0.02)

    def test_orient_auto_detects_yup(self):
        engine = self._import_yup()
        r = engine.orient_model(mode=OrientationMode.AUTO)
        assert r["detected_mode"] == OrientationMode.YUP
        assert r["rotation_applied"] is True

    def test_orient_preserves_imported_flag(self):
        engine = self._import_yup()
        engine.orient_model(mode=OrientationMode.AUTO, floor_snap=True)
        wm = engine.working_model
        for n in wm.all_nodes():
            if n.is_mesh:
                assert getattr(n, "_imported", False), f"{n.name}: _imported lost"

    def test_orient_floor_snap_minz_zero(self):
        engine = self._import_yup()
        engine.orient_model(mode=OrientationMode.AUTO, floor_snap=True)
        wm = engine.working_model
        wm.compute_bounds()
        assert wm.bb_min[2] == pytest.approx(0.0, abs=1e-5)

    def test_orient_does_not_change_stage(self):
        engine = self._import_yup()
        assert engine.stage == RetargetStage.IMPORTED
        engine.orient_model()
        assert engine.stage == RetargetStage.IMPORTED

    def test_orient_idempotent_for_zup(self):
        """Calling orient twice on a ZUP model should not change bounds."""
        engine = RetargetEngine()
        model  = _zup_model(height=1.8)
        engine.set_imported_model(model)
        engine.orient_model(mode=OrientationMode.ZUP, floor_snap=False)
        wm = engine.working_model
        wm.compute_bounds()
        b1 = (tuple(wm.bb_min), tuple(wm.bb_max))
        engine.orient_model(mode=OrientationMode.ZUP, floor_snap=False)
        wm.compute_bounds()
        b2 = (tuple(wm.bb_min), tuple(wm.bb_max))
        assert b1 == b2


# ─────────────────────────────────────────────────────────────────────────────
# OBJ import → auto-orient via engine pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestOBJOrientPipeline:
    OBJ_YUP = """\
v -0.3  0.0 -0.1
v  0.3  0.0 -0.1
v  0.3  1.8  0.1
v -0.3  1.8  0.1
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
g body
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/3/1 4/4/1
"""

    def _import(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".obj", delete=False) as f:
            f.write(self.OBJ_YUP)
            path = f.name
        try:
            return OBJImporter().import_file(path)
        finally:
            os.unlink(path)

    def test_obj_yup_auto_orient_upright(self):
        model = self._import()
        engine = RetargetEngine()
        engine.set_imported_model(model)
        r = engine.orient_model(mode=OrientationMode.AUTO, floor_snap=True)
        wm = engine.working_model
        wm.compute_bounds()
        dz = wm.bb_max[2] - wm.bb_min[2]
        assert dz == pytest.approx(1.8, abs=0.02), f"Expected height ~1.8m, got {dz:.3f}"

    def test_obj_orient_height_correct_in_kotor_z_axis(self):
        model = self._import()
        engine = RetargetEngine()
        engine.set_imported_model(model)
        engine.orient_model(mode=OrientationMode.YUP, floor_snap=True)
        wm = engine.working_model
        wm.compute_bounds()
        # Z is now the height axis
        dz = wm.bb_max[2] - wm.bb_min[2]
        dy = wm.bb_max[1] - wm.bb_min[1]
        assert dz > dy * 3, f"Z should be tall axis after orient: dz={dz:.3f} dy={dy:.3f}"

    def test_obj_orient_floor_snapped(self):
        model = self._import()
        engine = RetargetEngine()
        engine.set_imported_model(model)
        engine.orient_model(mode=OrientationMode.AUTO, floor_snap=True)
        wm = engine.working_model
        wm.compute_bounds()
        assert wm.bb_min[2] >= -1e-5, f"Model not floor-snapped: min_z={wm.bb_min[2]:.4f}"


# ─────────────────────────────────────────────────────────────────────────────
# ModelOrientFixer.align_to_reference()
# ─────────────────────────────────────────────────────────────────────────────

class TestAlignToReference:
    """Tests for ModelOrientFixer.align_to_reference and engine.align_to_reference."""

    def _ref_model(self, floor_z=0.0, cx=0.0, cy=0.0, height=1.8) -> KotorModel:
        """Reference model sitting at (cx±0.3, cy±0.1, floor_z…floor_z+height)."""
        return _make_model([
            (cx - 0.3, cy - 0.1, floor_z),
            (cx + 0.3, cy - 0.1, floor_z),
            (cx + 0.3, cy + 0.1, floor_z + height),
            (cx - 0.3, cy + 0.1, floor_z + height),
        ], name="reference")

    def test_align_centers_xy(self):
        """Imported model XY centroid moves to match reference centroid."""
        imported = _make_model([(10, 20, 0), (12, 22, 0), (11, 21, 1.8)], name="imp")
        ref      = self._ref_model(cx=0.0, cy=0.0)
        ModelOrientFixer.align_to_reference(imported, ref, match_floor=False, center_xy=True)
        imported.compute_bounds()
        cx = (imported.bb_min[0] + imported.bb_max[0]) * 0.5
        cy = (imported.bb_min[1] + imported.bb_max[1]) * 0.5
        ref.compute_bounds()
        ref_cx = (ref.bb_min[0] + ref.bb_max[0]) * 0.5
        ref_cy = (ref.bb_min[1] + ref.bb_max[1]) * 0.5
        assert cx == pytest.approx(ref_cx, abs=1e-4)
        assert cy == pytest.approx(ref_cy, abs=1e-4)

    def test_align_matches_floor(self):
        """Imported model floor (min Z) matches reference floor after alignment."""
        imported = _make_model([(0, 0, 5), (1, 0, 5), (0.5, 0, 6.8)], name="imp")
        ref      = self._ref_model(floor_z=0.0)
        ModelOrientFixer.align_to_reference(imported, ref, match_floor=True, center_xy=False)
        imported.compute_bounds()
        ref.compute_bounds()
        assert imported.bb_min[2] == pytest.approx(ref.bb_min[2], abs=1e-4)

    def test_align_height_preserved(self):
        """Alignment translates but does not scale – height must be unchanged."""
        h = 1.75
        imported = _make_model([(0, 0, 0), (0.5, 0, 0), (0.5, 0, h)], name="imp")
        ref      = self._ref_model(cx=3.0, cy=-2.0, floor_z=0.0, height=1.8)
        ModelOrientFixer.align_to_reference(imported, ref, match_floor=True, center_xy=True)
        imported.compute_bounds()
        dz = imported.bb_max[2] - imported.bb_min[2]
        assert dz == pytest.approx(h, abs=1e-4), f"Height changed after align: {dz:.4f} ≠ {h}"

    def test_align_returns_translate(self):
        """align_to_reference returns a non-zero translate tuple."""
        imported = _make_model([(5, 5, 0), (6, 5, 0), (5.5, 5, 1.8)], name="imp")
        ref      = self._ref_model(cx=0.0, cy=0.0)
        result   = ModelOrientFixer.align_to_reference(imported, ref)
        tx, ty, tz = result['translate']
        assert abs(tx) > 0.1 or abs(ty) > 0.1, "Expected non-zero XY translation"

    def test_align_no_center_xy(self):
        """When center_xy=False the XY position is unchanged."""
        imported = _make_model([(5, 5, 0), (6, 5, 0), (5.5, 5, 1.8)], name="imp")
        imported.compute_bounds()
        orig_cx = (imported.bb_min[0] + imported.bb_max[0]) * 0.5
        ref      = self._ref_model(cx=0.0, cy=0.0)
        ModelOrientFixer.align_to_reference(imported, ref, match_floor=False, center_xy=False)
        imported.compute_bounds()
        new_cx = (imported.bb_min[0] + imported.bb_max[0]) * 0.5
        assert new_cx == pytest.approx(orig_cx, abs=1e-4)

    def test_align_no_match_floor(self):
        """When match_floor=False the Z position is unchanged."""
        imported = _make_model([(0, 0, 5), (1, 0, 5), (0.5, 0, 6.8)], name="imp")
        imported.compute_bounds()
        orig_minz = imported.bb_min[2]
        ref      = self._ref_model(floor_z=0.0)
        ModelOrientFixer.align_to_reference(imported, ref, match_floor=False, center_xy=False)
        imported.compute_bounds()
        assert imported.bb_min[2] == pytest.approx(orig_minz, abs=1e-4)

    def test_align_message_contains_align(self):
        imported = _make_model([(5, 5, 0), (6, 5, 0), (5.5, 5, 1.8)], name="imp")
        ref      = self._ref_model()
        result   = ModelOrientFixer.align_to_reference(imported, ref)
        assert "align" in result['message'].lower()

    # ── Engine-level tests ────────────────────────────────────────────────────

    def test_engine_align_requires_import(self):
        engine = RetargetEngine()
        r = engine.align_to_reference()
        assert not r['ok']
        assert "No model" in r['message']

    def test_engine_align_requires_reference(self):
        engine = RetargetEngine()
        engine.set_imported_model(_zup_model())
        r = engine.align_to_reference()
        assert not r['ok']
        assert "reference" in r['message'].lower()

    def test_engine_align_moves_model_to_origin(self):
        """After align_to_reference the working model centroid is near (0,0)."""
        imported = _make_model([(8, 9, 0), (10, 11, 0), (9, 10, 1.8)], name="imp")
        ref      = _zup_model(height=1.8)   # centred at (0,0,0..1.8)

        engine = RetargetEngine()
        engine.set_imported_model(imported)
        engine.set_reference_model(ref)
        r = engine.align_to_reference(match_floor=True, center_xy=True)
        assert r['ok'], r['message']

        wm = engine.working_model
        wm.compute_bounds()
        cx = (wm.bb_min[0] + wm.bb_max[0]) * 0.5
        cy = (wm.bb_min[1] + wm.bb_max[1]) * 0.5
        ref.compute_bounds()
        ref_cx = (ref.bb_min[0] + ref.bb_max[0]) * 0.5
        ref_cy = (ref.bb_min[1] + ref.bb_max[1]) * 0.5
        assert cx == pytest.approx(ref_cx, abs=0.01)
        assert cy == pytest.approx(ref_cy, abs=0.01)

    def test_engine_align_height_unchanged(self):
        """align_to_reference does not change the model height."""
        imported = _make_model([(8, 9, 2), (10, 11, 2), (9, 10, 3.8)], name="imp")
        ref      = _zup_model(height=1.8)
        engine   = RetargetEngine()
        engine.set_imported_model(imported)
        engine.set_reference_model(ref)
        h_before = engine.align_to_reference()['height_before']
        h_after  = engine.align_to_reference()['height_after']
        # Height is the Z span – must be the same after XY/floor alignment
        wm = engine.working_model
        wm.compute_bounds()
        dz = wm.bb_max[2] - wm.bb_min[2]
        assert dz == pytest.approx(1.8, abs=0.05)
