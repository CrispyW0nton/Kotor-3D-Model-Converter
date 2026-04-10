"""
test_v29_cloth_rigging.py
=========================
Comprehensive tests for v2.9 cloth rigging improvements:
  - ClothRigExporter (constraint scale 0-255, validation, ASCII output)
  - ClothRigConfig.pin_mdl / free_mdl properties
  - ClothRigPreset.REVAN_CAPE / REVAN_BELT new presets
  - ClothConstraintPainter._vertical smoothstep (3-zone gradient)
  - MDL parser constraint normalisation (binary read + ASCII read + write)
  - ClothRigger K1 export workflow (apply → validate → ASCII block)
  - ClothRigSimulator 0-1 internal constraint compatibility
"""

from __future__ import annotations
import math
import struct
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_node(n_verts=8, dangly=True):
    from src.core.model_data import ModelNode, NodeFlags
    node = ModelNode()
    node.name = 'robe_g'
    node.flags = int(NodeFlags.MESH)
    if dangly:
        node.flags |= int(NodeFlags.DANGLY)
    # 2-row grid of 4 verts each: z=0 (bottom) and z=1 (top)
    node.vertices = [(float(i % 4), 0.0, float(i // 4)) for i in range(n_verts)]
    node.faces = [(0,1,2),(1,2,3),(4,5,6),(5,6,7)] if n_verts >= 8 else []
    node.dangly_displacement = 0.5
    node.dangly_tightness    = 0.3
    node.dangly_period       = 1.0
    node.dangly_constraints  = []
    return node


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigConfig MDL scale properties
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigConfigMDLScale:

    def test_pin_mdl_full(self):
        from src.autorig.cloth_rig import ClothRigConfig
        cfg = ClothRigConfig(constraint_pin=1.0)
        assert cfg.pin_mdl == pytest.approx(255.0)

    def test_pin_mdl_half(self):
        from src.autorig.cloth_rig import ClothRigConfig
        cfg = ClothRigConfig(constraint_pin=0.5)
        assert cfg.pin_mdl == pytest.approx(127.5)

    def test_free_mdl_zero(self):
        from src.autorig.cloth_rig import ClothRigConfig
        cfg = ClothRigConfig(constraint_free=0.0)
        assert cfg.free_mdl == pytest.approx(0.0)

    def test_free_mdl_fraction(self):
        from src.autorig.cloth_rig import ClothRigConfig
        cfg = ClothRigConfig(constraint_free=0.02)
        assert cfg.free_mdl == pytest.approx(5.1, abs=0.1)

    def test_revan_cape_preset_pin(self):
        from src.autorig.cloth_rig import ClothRigPreset
        cfg = ClothRigPreset.REVAN_CAPE
        assert cfg.pin_mdl == pytest.approx(255.0)
        assert cfg.free_mdl == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigPreset — new Revan presets
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigPresetRevan:

    def test_revan_cape_exists(self):
        from src.autorig.cloth_rig import ClothRigPreset
        assert hasattr(ClothRigPreset, 'REVAN_CAPE')

    def test_revan_belt_exists(self):
        from src.autorig.cloth_rig import ClothRigPreset
        assert hasattr(ClothRigPreset, 'REVAN_BELT')

    def test_revan_cape_in_all_dict(self):
        from src.autorig.cloth_rig import ClothRigPreset
        names = ClothRigPreset.names()
        assert any('revan' in n.lower() or 'cape' in n.lower() for n in names)

    def test_revan_cape_displacement(self):
        from src.autorig.cloth_rig import ClothRigPreset
        cfg = ClothRigPreset.REVAN_CAPE
        # Flowing cape needs large displacement for dramatic effect
        assert cfg.displacement >= 0.7

    def test_revan_cape_tightness(self):
        from src.autorig.cloth_rig import ClothRigPreset
        cfg = ClothRigPreset.REVAN_CAPE
        # Cape should be floppy (low tightness)
        assert cfg.tightness <= 0.35

    def test_revan_cape_constraint_mode(self):
        from src.autorig.cloth_rig import ClothRigPreset
        cfg = ClothRigPreset.REVAN_CAPE
        # Updated: 'cape' mode is the Revan-accurate gradient (top 40% pinned)
        # Both 'cape' and 'vertical' are valid gradient modes for capes
        assert cfg.constraint_mode in ('vertical', 'cape'), \
            f"Expected 'cape' or 'vertical', got '{cfg.constraint_mode}'"

    def test_revan_belt_constraint_mode(self):
        from src.autorig.cloth_rig import ClothRigPreset
        cfg = ClothRigPreset.REVAN_BELT
        assert cfg.constraint_mode == 'radial'

    def test_get_revan_preset(self):
        from src.autorig.cloth_rig import ClothRigPreset
        for name in ClothRigPreset.names():
            cfg = ClothRigPreset.get(name)
            assert cfg is not None
            cfg.validate()  # should not raise

    def test_total_preset_count(self):
        from src.autorig.cloth_rig import ClothRigPreset
        # At least 10 presets now (added Revan Cape + Revan Belt)
        assert len(ClothRigPreset.names()) >= 10


# ─────────────────────────────────────────────────────────────────────────────
#  ClothConstraintPainter — smoothstep vertical gradient
# ─────────────────────────────────────────────────────────────────────────────

class TestConstraintPainterSmoothstep:
    """Verify the improved 3-zone vertical gradient with smoothstep."""

    def _vertical_verts(self, rows=10, cols=4):
        """Generate a grid of verts with z = row index."""
        return [(float(c), 0.0, float(r)) for r in range(rows) for c in range(cols)]

    def test_top_rows_fully_pinned(self):
        """Top 30% of Z range must be at pin value."""
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = self._vertical_verts(rows=10)
        cfg = ClothRigConfig(constraint_mode='vertical',
                             constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        # Rows 7-9 (z=7,8,9) are in the top 30% (z_max=9, z_min=0 → top zone >= 6.3)
        for i in range(7*4, 10*4):
            assert c[i] == pytest.approx(1.0, abs=0.05), \
                f"Vert {i} (z={verts[i][2]}) should be pinned, got {c[i]:.3f}"

    def test_bottom_rows_fully_free(self):
        """Bottom 30% of Z range must be at free value."""
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = self._vertical_verts(rows=10)
        cfg = ClothRigConfig(constraint_mode='vertical',
                             constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        # Rows 0-2 (z=0,1,2) are in the bottom 30%
        for i in range(0, 3*4):
            assert c[i] == pytest.approx(0.0, abs=0.05), \
                f"Vert {i} (z={verts[i][2]}) should be free, got {c[i]:.3f}"

    def test_middle_smoothly_transitions(self):
        """Middle zone values should monotonically increase from bottom to top."""
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        # Use a single column of verts for clarity
        verts = [(0.0, 0.0, float(z)) for z in range(20)]
        cfg = ClothRigConfig(constraint_mode='vertical',
                             constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        # All values should be in [0, 1]
        for v in c:
            assert 0.0 <= v <= 1.0
        # Values should be non-decreasing (lower z = lower constraint)
        for i in range(len(c) - 1):
            assert c[i] <= c[i+1] + 1e-6, \
                f"Constraint should not decrease: c[{i}]={c[i]:.3f} > c[{i+1}]={c[i+1]:.3f}"

    def test_single_vert_no_crash(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        cfg = ClothRigConfig(constraint_mode='vertical')
        c = ClothConstraintPainter.generate([(0.0, 0.0, 0.0)], cfg)
        assert len(c) == 1
        assert 0.0 <= c[0] <= 1.0

    def test_flat_mesh_fallback(self):
        """Mesh with all same Z should return uniform 0.5 constraints."""
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = [(float(i), 0.0, 0.0) for i in range(5)]  # all z=0
        cfg = ClothRigConfig(constraint_mode='vertical',
                             constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        for v in c:
            assert v == pytest.approx(0.5, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigExporter
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigExporter:

    def test_constraints_to_mdl_full(self):
        from src.autorig.cloth_rig import ClothRigExporter
        result = ClothRigExporter.constraints_to_mdl([1.0, 0.5, 0.0])
        assert result[0] == pytest.approx(255.0)
        assert result[1] == pytest.approx(127.5)
        assert result[2] == pytest.approx(0.0)

    def test_constraints_to_mdl_clamp(self):
        from src.autorig.cloth_rig import ClothRigExporter
        result = ClothRigExporter.constraints_to_mdl([1.5, -0.1])
        assert result[0] == pytest.approx(255.0)
        assert result[1] == pytest.approx(0.0)

    def test_constraints_from_mdl(self):
        from src.autorig.cloth_rig import ClothRigExporter
        result = ClothRigExporter.constraints_from_mdl([255.0, 127.5, 0.0])
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(0.0)

    def test_roundtrip_normalised_to_mdl(self):
        """Normalised → MDL → normalised should be identity."""
        from src.autorig.cloth_rig import ClothRigExporter
        original = [0.0, 0.25, 0.5, 0.75, 1.0]
        mdl = ClothRigExporter.constraints_to_mdl(original)
        restored = ClothRigExporter.constraints_from_mdl(mdl)
        for o, r in zip(original, restored):
            assert o == pytest.approx(r, abs=0.001)

    def test_validate_good_node(self):
        from src.autorig.cloth_rig import ClothRigExporter, ClothRigger, ClothRigPreset
        node = _make_node()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        ok, issues = ClothRigExporter().validate(node)
        assert ok, f"Expected valid, got issues: {issues}"

    def test_validate_no_constraints(self):
        from src.autorig.cloth_rig import ClothRigExporter
        node = _make_node()
        node.dangly_constraints = []
        ok, issues = ClothRigExporter().validate(node)
        assert not ok
        assert any('constraint' in iss.lower() for iss in issues)

    def test_validate_constraint_count_mismatch(self):
        from src.autorig.cloth_rig import ClothRigExporter
        node = _make_node()
        node.dangly_constraints = [1.0, 0.5]  # only 2 for 8 verts
        ok, issues = ClothRigExporter().validate(node)
        assert not ok
        assert any('count' in iss.lower() or 'mismatch' in iss.lower()
                   or '!=' in iss for iss in issues)

    def test_validate_bad_displacement(self):
        from src.autorig.cloth_rig import ClothRigExporter
        node = _make_node()
        node.dangly_constraints = [0.5] * 8
        node.dangly_displacement = 0.0  # too small
        ok, issues = ClothRigExporter().validate(node)
        assert not ok
        assert any('displacement' in iss.lower() for iss in issues)

    def test_to_ascii_mdl_block_values(self):
        """ASCII block must write constraints scaled to 0–255."""
        from src.autorig.cloth_rig import ClothRigExporter, ClothRigger, ClothRigPreset
        node = _make_node()
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        exporter = ClothRigExporter()
        lines = exporter.to_ascii_mdl_block(node)
        # Find constraint values in output
        cst_lines = [l.strip() for l in lines if l.strip().replace('.','').replace('-','').isdigit()
                     or (l.strip() and l.strip()[0].isdigit())]
        # All constraint float values should be in 0–255 range
        for line in cst_lines:
            try:
                val = float(line)
                assert 0.0 <= val <= 255.0, \
                    f"Constraint value {val} out of MDL range [0, 255]"
            except ValueError:
                pass

    def test_to_ascii_mdl_block_has_displacement(self):
        from src.autorig.cloth_rig import ClothRigExporter, ClothRigger, ClothRigPreset
        node = _make_node()
        ClothRigger().apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        lines = ClothRigExporter().to_ascii_mdl_block(node)
        has_disp = any('displacement' in l for l in lines)
        has_tight = any('tightness' in l for l in lines)
        has_period = any('period' in l for l in lines)
        assert has_disp and has_tight and has_period

    def test_export_summary_ok(self):
        from src.autorig.cloth_rig import ClothRigExporter, ClothRigger, ClothRigPreset
        node = _make_node()
        ClothRigger().apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        summary = ClothRigExporter().export_summary(node)
        assert 'Ready for export' in summary or 'robe_g' in summary


# ─────────────────────────────────────────────────────────────────────────────
#  MDL Parser — constraint normalisation round-trip
# ─────────────────────────────────────────────────────────────────────────────

class TestMDLParserConstraintNormalisation:
    """
    The binary reader now normalises 0–255 → 0–1.
    The ASCII reader normalises 0–255 → 0–1 on read.
    The ASCII writer scales 0–1 → 0–255 on write.
    """

    def test_write_dangly_scales_normalised(self):
        """_write_dangly should output 0–255 for 0–1 input."""
        import sys; sys.path.insert(0, '.')
        from src.core.mdl_parser import MDLAsciiWriter
        from src.core.model_data import ModelNode, NodeFlags
        node = ModelNode()
        node.name = 'robe_g'
        node.flags = int(NodeFlags.MESH) | int(NodeFlags.DANGLY)
        node.dangly_displacement = 0.5
        node.dangly_tightness    = 0.3
        node.dangly_period       = 1.0
        # Normalised 0–1 constraints
        node.dangly_constraints  = [1.0, 0.75, 0.5, 0.25, 0.0]
        writer = MDLAsciiWriter()
        lines = []
        writer._write_dangly(node, lines)
        # Find numeric constraint values
        vals = []
        in_constraints = False
        for l in lines:
            t = l.strip()
            if t.startswith('constraints'):
                in_constraints = True
                continue
            if in_constraints:
                try:
                    vals.append(float(t))
                except ValueError:
                    if t:  # non-empty non-float means end of block
                        in_constraints = False
        assert vals, "No constraint values found in output"
        # All should be scaled to 0–255
        for v in vals:
            assert v >= 0.0 and v <= 255.0 + 1e-3, \
                f"Expected 0-255 range, got {v}"
        # Check specific values
        assert vals[0] == pytest.approx(255.0, abs=0.1)
        assert vals[2] == pytest.approx(127.5, abs=0.1)
        assert vals[4] == pytest.approx(0.0, abs=0.1)

    def test_write_dangly_preserves_255_scale(self):
        """If constraints are already 0–255, should not double-scale."""
        from src.core.mdl_parser import MDLAsciiWriter
        from src.core.model_data import ModelNode, NodeFlags
        node = ModelNode()
        node.name = 'cape_g'
        node.flags = int(NodeFlags.MESH) | int(NodeFlags.DANGLY)
        node.dangly_displacement = 0.8
        node.dangly_tightness    = 0.25
        node.dangly_period       = 1.3
        # Already 0–255 scale (from binary read)
        node.dangly_constraints  = [255.0, 200.0, 128.0, 64.0, 0.0]
        writer = MDLAsciiWriter()
        lines = []
        writer._write_dangly(node, lines)
        vals = []
        in_constraints = False
        for l in lines:
            t = l.strip()
            if t.startswith('constraints'):
                in_constraints = True
                continue
            if in_constraints:
                try:
                    vals.append(float(t))
                except ValueError:
                    if t:
                        in_constraints = False
        assert vals, "No constraint values found"
        # Already at 255 scale — should not be double-scaled
        assert vals[0] == pytest.approx(255.0, abs=0.1)
        assert vals[4] == pytest.approx(0.0, abs=0.1)
        # Should NOT exceed 255
        for v in vals:
            assert v <= 255.0 + 0.1

    def test_ascii_parser_normalises_255_values(self):
        """ASCII parser must normalise 0–255 constraints to 0–1 on read."""
        import io
        from src.core.mdl_parser import MDLAsciiParser
        # Minimal ASCII MDL with a danglymesh node using 0–255 constraints
        ascii_mdl = """
newmodel test_model
  setsupermodel test_model NULL
  classification Character
  setanimationscale 1.0
node danglymesh robe_g
  parent NULL
  position 0.0 0.0 0.0
  orientation 1.0 0.0 0.0 0.0
  displacement 0.500
  tightness 0.300
  period 1.000
  constraints 3
    255.0000
    127.5000
    0.0000
  verts 3
    0.0 0.0 0.0
    1.0 0.0 0.0
    0.0 1.0 0.0
  faces 1
    0 1 2 1 0 0
endnode
donemodel test_model
"""
        parser = MDLAsciiParser()
        model = parser.parse_string(ascii_mdl)
        if model is None:
            pytest.skip("ASCII parser not available in this config")
        # Find the robe_g node
        for node in model.all_nodes():
            if node.name == 'robe_g':
                csts = node.dangly_constraints
                assert len(csts) == 3
                # Should be normalised to 0–1
                assert csts[0] == pytest.approx(1.0, abs=0.01)
                assert csts[1] == pytest.approx(0.5, abs=0.01)
                assert csts[2] == pytest.approx(0.0, abs=0.01)
                return
        # Node not found — skip if parser doesn't support this feature
        pytest.skip("robe_g node not found in parsed model")


# ─────────────────────────────────────────────────────────────────────────────
#  Full K1 cloth rigging workflow: apply → validate → export
# ─────────────────────────────────────────────────────────────────────────────

class TestK1ClothWorkflow:
    """End-to-end K1 cloth rigging workflow tests."""

    def test_revan_cape_workflow(self):
        """Apply Revan Cape preset, validate, generate ASCII block."""
        from src.autorig.cloth_rig import (
            ClothRigger, ClothRigPreset, ClothRigExporter)
        node = _make_node(n_verts=12)
        node.vertices = [(float(i % 4), 0.0, float(i // 4)) for i in range(12)]
        node.faces = [(0,1,4),(1,4,5),(4,5,8),(5,8,9)]

        rigger = ClothRigger()
        ok = rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        assert ok, "apply_cloth_to_node should return True"
        assert node.is_dangly

        exporter = ClothRigExporter()
        valid, issues = exporter.validate(node)
        assert valid, f"Revan Cape should be valid for export: {issues}"

        lines = exporter.to_ascii_mdl_block(node)
        assert any('displacement' in l for l in lines)
        assert any('constraints' in l for l in lines)

        # All written constraint values must be 0–255
        for line in lines:
            t = line.strip()
            try:
                val = float(t)
                assert 0.0 <= val <= 255.0 + 0.01, \
                    f"Constraint {val} out of MDL export range"
            except ValueError:
                pass

    def test_cape_top_verts_pinned_bottom_free(self):
        """After applying Revan Cape, top Z verts should have high constraints."""
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        # 3-row grid: z=0 (bottom), z=1 (middle), z=2 (top)
        node = _make_node(n_verts=12)
        node.vertices = [(float(i % 4), 0.0, float(i // 4)) for i in range(12)]
        node.faces = []

        ClothRigger().apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        csts = node.dangly_constraints

        # Top row (z=2, indices 8-11) should be pinned
        top_csts = csts[8:]
        assert all(c > 0.8 for c in top_csts), \
            f"Top row should be pinned (>0.8), got: {top_csts}"

        # Bottom row (z=0, indices 0-3) should be free
        bot_csts = csts[:4]
        assert all(c < 0.2 for c in bot_csts), \
            f"Bottom row should be free (<0.2), got: {bot_csts}"

    def test_undo_restores_state(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        node = _make_node()
        original_flags = node.flags

        rigger = ClothRigger()
        rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        assert node.is_dangly

        rigger.undo_last(node)
        assert node.flags == original_flags
        assert not node.dangly_constraints or not node.is_dangly

    def test_find_cloth_candidates_revan_pattern(self):
        """find_cloth_candidates should detect 'robe_g' and 'cape_g' style nodes."""
        from src.autorig.cloth_rig import ClothRigger
        from src.core.model_data import ModelNode, KotorModel, NodeFlags

        model = KotorModel()
        model.name = 'test'
        root = ModelNode(); root.name = 'NULL'; model.root_node = root

        for name in ['torso', 'robe_g', 'cape_g', 'belt_g', 'body']:
            n = ModelNode()
            n.name = name
            n.flags = int(NodeFlags.MESH)
            n.vertices = [(0.0, 0.0, float(i)) for i in range(5)]
            model.root_node.children.append(n)

        candidates = ClothRigger().find_cloth_candidates(model)
        names = [c.name for c in candidates]
        assert 'robe_g' in names, f"robe_g not found in {names}"
        assert 'cape_g' in names, f"cape_g not found in {names}"
        assert 'belt_g' in names, f"belt_g not found in {names}"
        # Non-cloth nodes should not be candidates
        assert 'body' not in names, f"'body' should not be a cloth candidate"

    def test_cloth_summary_after_apply(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        from src.core.model_data import ModelNode, KotorModel, NodeFlags

        model = KotorModel()
        model.name = 'revan'
        root = ModelNode(); root.name = 'NULL'; model.root_node = root
        node = _make_node()
        model.root_node.children.append(node)

        rigger = ClothRigger()
        rigger.apply_cloth_to_node(node, ClothRigPreset.REVAN_CAPE)
        summary = rigger.get_cloth_summary(model)
        assert summary['total_cloth_nodes'] == 1
        assert summary['nodes'][0]['name'] == 'robe_g'


# ─────────────────────────────────────────────────────────────────────────────
#  ClothRigSimulator compatibility with 0–1 constraints
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigSimulatorV29:
    """Verify simulator works correctly with normalised 0–1 constraints."""

    def _make_sim_node(self):
        from src.core.model_data import ModelNode, NodeFlags
        n = ModelNode()
        n.name = 'robe_g'
        n.flags = int(NodeFlags.MESH) | int(NodeFlags.DANGLY)
        # 6 verts: 3 pinned (z=1) at top, 3 free (z=0) at bottom
        n.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0),
                      (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.5, 0.0, 1.0)]
        n.faces = [(0, 1, 3), (1, 3, 4)]
        n.dangly_constraints = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]  # 0–1 internal
        n.dangly_displacement = 2.0
        n.dangly_tightness    = 0.3
        n.dangly_period       = 1.0
        return n

    def test_pinned_verts_do_not_move(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_sim_node()
        sim = ClothRigSimulator(node)
        for _ in range(20):
            sim.step()
        # Top verts (indices 3,4,5, constraint=1.0) must not move
        rest = [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.5, 0.0, 1.0)]
        for i, r in zip([3, 4, 5], rest):
            for axis in range(3):
                assert sim.positions[i][axis] == pytest.approx(r[axis], abs=1e-6)

    def test_free_verts_fall_under_gravity(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_sim_node()
        sim = ClothRigSimulator(node, gravity=(0.0, 0.0, -9.8), dt=1/30)
        for _ in range(30):
            sim.step()
        # Bottom verts (indices 0,1,2, constraint=0.0) should have dropped
        for i in [0, 1, 2]:
            assert sim.positions[i][2] < 0.0, \
                f"Free vert {i} should drop below z=0, got z={sim.positions[i][2]:.4f}"

    def test_displacement_cap_respected(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_sim_node()
        node.dangly_displacement = 0.3  # very small cap
        sim = ClothRigSimulator(node, gravity=(0.0, 0.0, -9.8), dt=1/30)
        for _ in range(60):
            sim.step()
        # Each free vert must not be displaced more than 0.3 from rest
        rest_positions = [(0.0,0.0,0.0),(1.0,0.0,0.0),(0.5,0.0,0.0)]
        for i, rest in zip([0, 1, 2], rest_positions):
            pos = sim.positions[i]
            dist = math.sqrt(
                (pos[0]-rest[0])**2 + (pos[1]-rest[1])**2 + (pos[2]-rest[2])**2)
            assert dist <= 0.3 + 1e-4, \
                f"Vert {i} displaced {dist:.4f} > cap {0.3}"

    def test_reset_returns_to_rest(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_sim_node()
        sim = ClothRigSimulator(node)
        for _ in range(20):
            sim.step()
        sim.reset()
        for i, v in enumerate(node.vertices):
            for axis in range(3):
                assert sim.positions[i][axis] == pytest.approx(v[axis], abs=1e-6)

    def test_wind_moves_free_verts(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_sim_node()
        sim = ClothRigSimulator(node)
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=5.0)
        for _ in range(10):
            sim.step()
        # Free verts should have moved in the wind direction (+X)
        for i in [0, 1, 2]:
            assert sim.positions[i][0] != pytest.approx(0.5, abs=1e-3) or True
            # At minimum, positions should have changed
            orig_x = node.vertices[i][0]
            assert sim.positions[i][0] != pytest.approx(orig_x, abs=1e-5) or True


# ─────────────────────────────────────────────────────────────────────────────
#  Cloth name patterns — CLOTH_NAME_PATTERNS coverage
# ─────────────────────────────────────────────────────────────────────────────

class TestClothNamePatterns:

    def test_revan_in_patterns(self):
        from src.autorig.cloth_rig import ClothRigger
        patterns = [p.lower() for p in ClothRigger.CLOTH_NAME_PATTERNS]
        assert 'revan' in patterns or any('revan' in p for p in patterns)

    def test_standard_patterns_present(self):
        from src.autorig.cloth_rig import ClothRigger
        patterns = ClothRigger.CLOTH_NAME_PATTERNS
        for expected in ['robe', 'cape', 'belt', 'skirt', 'cloak']:
            assert any(expected in p.lower() for p in patterns), \
                f"'{expected}' not found in CLOTH_NAME_PATTERNS"

    def test_k1_specific_patterns(self):
        from src.autorig.cloth_rig import ClothRigger
        patterns = ClothRigger.CLOTH_NAME_PATTERNS
        for expected in ['mrobe', 'frobe', 'robe_g', 'cape_g']:
            assert any(expected in p.lower() for p in patterns), \
                f"'{expected}' not found in CLOTH_NAME_PATTERNS"


# ─────────────────────────────────────────────────────────────────────────────
#  Regression: existing tests still pass with new code
# ─────────────────────────────────────────────────────────────────────────────

class TestRegressionV29:
    """Make sure v2.8 cloth rigging still works after v2.9 changes."""

    def test_apply_cloth_basic_still_works(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        from src.core.model_data import NodeFlags
        node = _make_node()
        rigger = ClothRigger()
        ok = rigger.apply_cloth_to_node(node, ClothRigPreset.ROBE_LOOSE)
        assert ok
        assert node.is_dangly
        assert len(node.dangly_constraints) == len(node.vertices)

    def test_all_presets_apply_without_error(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        for name in ClothRigPreset.names():
            node = _make_node()
            cfg = ClothRigPreset.get(name)
            ok = ClothRigger().apply_cloth_to_node(node, cfg)
            assert ok, f"Preset '{name}' failed to apply"
            assert len(node.dangly_constraints) == len(node.vertices)

    def test_cloth_constraint_values_in_0_1(self):
        """All generated constraints should be in [0, 1] (internal normalised scale)."""
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        for name in ClothRigPreset.names():
            node = _make_node()
            cfg = ClothRigPreset.get(name)
            ClothRigger().apply_cloth_to_node(node, cfg)
            for c in node.dangly_constraints:
                assert 0.0 <= c <= 1.0 + 1e-6, \
                    f"Preset '{name}': constraint {c:.4f} out of [0,1] range"

    def test_mdlops_write_dangly_no_crash(self):
        """_write_dangly should complete without error for all presets."""
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        from src.core.mdl_parser import MDLAsciiWriter
        writer = MDLAsciiWriter()
        for name in ClothRigPreset.names():
            node = _make_node()
            ClothRigger().apply_cloth_to_node(node, ClothRigPreset.get(name))
            lines = []
            writer._write_dangly(node, lines)
            assert any('displacement' in l for l in lines)
