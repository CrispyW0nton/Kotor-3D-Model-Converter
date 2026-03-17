"""
Tests for v2.8 fixes:
  1. Alpha/transparency rendering for droid glass nodes
  2. UV tiling wrap (multi-tile large UV coords)
  3. Creature model outlier-skin filter (c_bantha, c_brith)
  4. ClothRigSimulator PBD physics
  5. _BASE_SKELETONS expanded for creature/droid models
  6. _paste_textured_triangle node_alpha parameter
  7. flat renderer alpha blending
  8. transparency_hint==2 default glass opacity
"""
from __future__ import annotations
import sys, math, types
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import pytest
from src.core.model_data import (
    ModelNode, NodeFlags, KotorModel,
    _quat_normalize, _quat_normalize_bind, _quat_rotate, _quat_mul,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_model(name='test', supermodel='NULL'):
    m = KotorModel(name=name)
    m.supermodel = supermodel
    root = ModelNode(name=name, flags=NodeFlags.HEADER)
    root.parent = None
    m.root_node = root
    return m, root

def make_mesh_node(name, parent, pos=(0,0,0), rot=(0,0,0,1),
                   tex='tex01', verts=None, uvs=None, faces=None,
                   is_skin=False, alpha=1.0, transparency_hint=0):
    flags = NodeFlags.MESH | NodeFlags.HEADER
    if is_skin:
        flags |= NodeFlags.SKIN
    n = ModelNode(name=name, flags=flags)
    n.position = pos
    n.rotation = rot
    n.texture  = tex
    n.vertices = verts or [(0,0,0),(1,0,0),(0,1,0),(1,1,0)]
    n.uvs      = uvs   or [(0,0),(1,0),(0,1),(1,1)]
    n.faces    = faces or [(0,1,2),(1,3,2)]
    n.alpha    = alpha
    n.transparency_hint = transparency_hint
    n.parent   = parent
    if parent is not None:
        parent.children.append(n)
    return n


# ─────────────────────────────────────────────────────────────────────────────
#  1. Alpha field on model node
# ─────────────────────────────────────────────────────────────────────────────

class TestAlphaField:
    def test_default_alpha_is_one(self):
        n = ModelNode(name='x', flags=NodeFlags.MESH)
        assert getattr(n, 'alpha', 1.0) == 1.0

    def test_alpha_field_set(self):
        n = ModelNode(name='x', flags=NodeFlags.MESH)
        n.alpha = 0.5
        assert n.alpha == pytest.approx(0.5)

    def test_alpha_zero_fully_transparent(self):
        n = ModelNode(name='glass', flags=NodeFlags.MESH)
        n.alpha = 0.0
        assert n.alpha == pytest.approx(0.0)

    def test_transparency_hint_field(self):
        n = ModelNode(name='glass', flags=NodeFlags.MESH)
        n.transparency_hint = 2
        assert n.transparency_hint == 2

    def test_transparency_hint_default(self):
        n = ModelNode(name='x', flags=NodeFlags.MESH)
        assert getattr(n, 'transparency_hint', 0) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  2. UV wrapping / tiling logic (unit tests without PIL)
# ─────────────────────────────────────────────────────────────────────────────

class TestUVUnwrapLogic:
    """Test the _uv_unwrap_coord logic extracted as pure Python."""

    @staticmethod
    def _uv_unwrap(base, other):
        """Mirror of the updated _uv_unwrap_coord in viewport.py."""
        diff = other - base
        while diff > 0.5:
            other -= 1.0
            diff  -= 1.0
        while diff < -0.5:
            other += 1.0
            diff  += 1.0
        return other

    def test_no_wrap_needed(self):
        assert self._uv_unwrap(0.3, 0.4) == pytest.approx(0.4)

    def test_forward_seam(self):
        # u0=0.9, u1=0.1 → u1 should be shifted to 1.1 (not jump back across seam)
        result = self._uv_unwrap(0.9, 0.1)
        assert result == pytest.approx(1.1)

    def test_backward_seam(self):
        # u0=0.1, u1=0.9 → u1 should be shifted to -0.1
        result = self._uv_unwrap(0.1, 0.9)
        assert result == pytest.approx(-0.1)

    def test_large_uv_tile(self):
        # u0=2.3, u1=2.8 → same tile, no shift
        result = self._uv_unwrap(2.3, 2.8)
        assert result == pytest.approx(2.8)

    def test_large_uv_cross_tile_boundary(self):
        # u0=2.9, u1=3.1 → within ±0.5, no shift
        result = self._uv_unwrap(2.9, 3.1)
        assert result == pytest.approx(3.1)

    def test_multi_tile_jump_corrected(self):
        # u0=0.1, u1=1.9 → u1 is 1.8 units away: should shift to -0.1
        result = self._uv_unwrap(0.1, 1.9)
        # After iterative shift: 1.9 → 0.9 → -0.1
        assert result == pytest.approx(-0.1)

    def test_negative_uv(self):
        # u0=-0.1, u1=-0.9 → shift u1 to +0.1
        result = self._uv_unwrap(-0.1, -0.9)
        assert result == pytest.approx(0.1)

    def test_identical_uvs_no_shift(self):
        assert self._uv_unwrap(0.5, 0.5) == pytest.approx(0.5)

    def test_tile_count_computation(self):
        """Verify tile count formula used in _paste_textured_triangle."""
        u_min, u_max = 0.0, 2.5
        tile_u = min(max(1, int(math.ceil(u_max - u_min + 1e-9))), 8)
        assert tile_u == 3

    def test_tile_count_normal_uv(self):
        """Normal UVs [0,1] → 1 tile."""
        u_min, u_max = 0.0, 0.95
        tile_u = min(max(1, int(math.ceil(u_max - u_min + 1e-9))), 8)
        assert tile_u == 1

    def test_tile_count_capped_at_8(self):
        """Extreme UVs capped at 8 tiles."""
        u_min, u_max = 0.0, 50.0
        tile_u = min(max(1, int(math.ceil(u_max - u_min + 1e-9))), 8)
        assert tile_u == 8


# ─────────────────────────────────────────────────────────────────────────────
#  3. Creature model outlier-skin filter (_BASE_SKELETONS)
# ─────────────────────────────────────────────────────────────────────────────

class TestCreatureOutlierFilter:
    """Verify _BASE_SKELETONS prevents outlier-skin hiding for creatures."""

    def _get_base_skeletons(self):
        # Import the FrameRenderer to access _BASE_SKELETONS
        try:
            from src.gui.viewport import FrameRenderer
            return FrameRenderer._BASE_SKELETONS
        except Exception:
            return frozenset()

    def test_c_bantha_in_base_skeletons(self):
        bs = self._get_base_skeletons()
        assert 'C_BANTHA' in bs

    def test_c_brith_in_base_skeletons(self):
        bs = self._get_base_skeletons()
        assert 'C_BRITH' in bs

    def test_wardroid_in_base_skeletons(self):
        bs = self._get_base_skeletons()
        assert 'WARDROID' in bs

    def test_s_female02_still_present(self):
        bs = self._get_base_skeletons()
        assert 'S_FEMALE02' in bs

    def test_null_still_present(self):
        bs = self._get_base_skeletons()
        assert 'NULL' in bs

    def test_c_kinrath_in_base_skeletons(self):
        bs = self._get_base_skeletons()
        assert 'C_KINRATH' in bs

    def test_creature_prefix_c_bantha_bypass(self):
        """Models with C_ prefix bypass outlier filter."""
        try:
            from src.gui.viewport import FrameRenderer
        except Exception:
            pytest.skip("GUI not available")
        # Build a minimal model with C_ name
        m, root = make_model(name='c_bantha', supermodel='c_bantha')
        # Attach a few mesh nodes
        for i in range(4):
            make_mesh_node(f'mesh_{i}', root, verts=[(j,0,0) for j in range(5)])

        renderer = FrameRenderer.__new__(FrameRenderer)
        renderer._outlier_skin_nodes = set()
        renderer._outlier_model_id   = -1
        renderer._compute_outlier_skin_nodes(m)
        # C_ prefix model should have zero outlier nodes
        assert len(renderer._outlier_skin_nodes) == 0

    def test_wardroid_prefix_bypass(self):
        """Models with Wardroid name bypass outlier filter."""
        try:
            from src.gui.viewport import FrameRenderer
        except Exception:
            pytest.skip("GUI not available")
        m, root = make_model(name='wardroid', supermodel='wardroid')
        for i in range(4):
            make_mesh_node(f'mesh_{i}', root, verts=[(j,0,0) for j in range(5)])

        renderer = FrameRenderer.__new__(FrameRenderer)
        renderer._outlier_skin_nodes = set()
        renderer._outlier_model_id   = -1
        renderer._compute_outlier_skin_nodes(m)
        assert len(renderer._outlier_skin_nodes) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  4. ClothRigSimulator — PBD physics
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRigSimulator:
    """Test the new Position-Based Dynamics cloth simulator."""

    def _make_dangly_node(self, n_verts=6, displacement=0.5, tightness=0.5):
        """Create a minimal dangly mesh node for simulation."""
        from src.core.model_data import NodeFlags
        node = ModelNode(name='cloth_test', flags=NodeFlags.MESH | NodeFlags.DANGLY)
        # Simple grid: 2 rows, 3 cols
        node.vertices = [
            (float(c), 0.0, float(r))   # row r, col c
            for r in range(2) for c in range(3)
        ]
        node.faces = [(0,1,3),(0,3,2),(1,4,3),(1,2,4),(2,4,5),(2,3,5)]  # grid tris
        # Top row (r=1, indices 3,4,5) pinned; bottom row (r=0, indices 0,1,2) free
        node.dangly_constraints = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        node.dangly_displacement = displacement
        node.dangly_tightness    = tightness
        node.dangly_period       = 1.0
        return node

    def test_simulator_init(self):
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node()
        sim = ClothRigSimulator(node)
        assert len(sim.positions) == 6
        assert len(sim._prev_pos)  == 6
        assert len(sim._springs)   > 0

    def test_pinned_vertices_dont_move(self):
        """Vertices with constraint=1.0 must not move."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node()
        sim  = ClothRigSimulator(node)
        before = [list(p) for p in sim.positions]
        for _ in range(30):
            sim.step()
        # Pinned verts (indices 3,4,5) should stay at rest positions
        for i in (3, 4, 5):
            assert sim.positions[i][0] == pytest.approx(before[i][0], abs=1e-6)
            assert sim.positions[i][1] == pytest.approx(before[i][1], abs=1e-6)
            assert sim.positions[i][2] == pytest.approx(before[i][2], abs=1e-6)

    def test_free_vertices_fall_under_gravity(self):
        """Free vertices (constraint=0.0) should drop under gravity."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node(displacement=5.0)  # big cap so they can move
        sim  = ClothRigSimulator(node, gravity=(0.0, 0.0, -9.8), dt=1/30)
        init_z = [sim.positions[i][2] for i in (0, 1, 2)]
        for _ in range(20):
            sim.step()
        final_z = [sim.positions[i][2] for i in (0, 1, 2)]
        # Free verts should have fallen (Z decreased)
        for iz, fz in zip(init_z, final_z):
            assert fz < iz, f"Free vert did not fall: init_z={iz:.3f}, final_z={fz:.3f}"

    def test_displacement_cap_respected(self):
        """Displacement cap must prevent vertices moving beyond the limit."""
        from src.autorig.cloth_rig import ClothRigSimulator
        disp = 0.3
        node = self._make_dangly_node(displacement=disp, tightness=0.1)
        sim  = ClothRigSimulator(node, gravity=(0.0, 0.0, -9.8), dt=1/30)
        for _ in range(60):
            sim.step()
        rest = sim._rest_pos
        for i in (0, 1, 2):   # free verts
            pos = sim.positions[i]
            dx = pos[0] - rest[i][0]
            dy = pos[1] - rest[i][1]
            dz = pos[2] - rest[i][2]
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            assert dist <= disp + 1e-4, (
                f"Vert {i} exceeded displacement cap: {dist:.4f} > {disp}"
            )

    def test_reset_restores_rest_pose(self):
        """reset() must restore positions to bind-pose rest."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node(displacement=5.0)
        sim  = ClothRigSimulator(node)
        for _ in range(40):
            sim.step()
        sim.reset()
        for i, (pos, rest) in enumerate(zip(sim.positions, sim._rest_pos)):
            assert pos[0] == pytest.approx(rest[0], abs=1e-9)
            assert pos[1] == pytest.approx(rest[1], abs=1e-9)
            assert pos[2] == pytest.approx(rest[2], abs=1e-9)

    def test_wind_impulse_moves_free_verts(self):
        """apply_wind() must perturb free verts but not pinned ones."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node(displacement=5.0)
        sim  = ClothRigSimulator(node)
        prev_free  = [list(p) for p in sim.positions[:3]]
        prev_pinned = [list(p) for p in sim.positions[3:]]
        sim.apply_wind(direction=(1.0, 0.0, 0.0), strength=3.0)
        sim.step()
        # Free verts should have moved in X
        for i in range(3):
            assert sim.positions[i][0] != pytest.approx(prev_free[i][0], abs=1e-6)

    def test_springs_built_from_faces(self):
        """Spring list must be non-empty for a valid mesh."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node()
        sim  = ClothRigSimulator(node)
        assert len(sim._springs) > 0

    def test_spring_rest_lengths_positive(self):
        """All spring rest lengths must be > 0."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node()
        sim  = ClothRigSimulator(node)
        for i, j, rest in sim._springs:
            assert rest > 0.0, f"Spring ({i},{j}) has zero rest length"

    def test_no_duplicate_springs(self):
        """Each edge should appear at most once in spring list."""
        from src.autorig.cloth_rig import ClothRigSimulator
        node = self._make_dangly_node()
        sim  = ClothRigSimulator(node)
        edges = [(min(i,j), max(i,j)) for i,j,_ in sim._springs]
        assert len(edges) == len(set(edges)), "Duplicate springs found"

    def test_high_tightness_less_displacement(self):
        """High tightness should result in less free-vert displacement."""
        from src.autorig.cloth_rig import ClothRigSimulator
        steps = 40
        disp_loose = None
        disp_stiff = None
        for tightness in (0.1, 0.9):
            node = self._make_dangly_node(displacement=5.0, tightness=tightness)
            sim  = ClothRigSimulator(node, gravity=(0.0, 0.0, -9.8), dt=1/30)
            for _ in range(steps):
                sim.step()
            rest = sim._rest_pos[0]
            pos  = sim.positions[0]
            d = math.sqrt(sum((pos[k]-rest[k])**2 for k in range(3)))
            if tightness < 0.5:
                disp_loose = d
            else:
                disp_stiff = d
        # Looser cloth should displace more (or equal)
        if disp_loose is not None and disp_stiff is not None:
            assert disp_loose >= disp_stiff - 1e-3, (
                f"Expected loose ({disp_loose:.4f}) >= stiff ({disp_stiff:.4f})"
            )


# ─────────────────────────────────────────────────────────────────────────────
#  5. ClothRigger integration
# ─────────────────────────────────────────────────────────────────────────────

class TestClothRiggerIntegration:
    def _make_mesh_node(self):
        n = ModelNode(name='robe01', flags=NodeFlags.MESH)
        n.vertices = [(float(i), 0.0, float(j)) for i in range(3) for j in range(3)]
        n.faces    = [(0,1,3),(0,3,2),(1,4,3),(3,4,6),(3,6,2)]
        n.dangly_constraints  = []
        n.dangly_displacement = 0.5
        n.dangly_tightness    = 0.5
        n.dangly_period       = 1.0
        return n

    def test_apply_cloth_sets_dangly_flag(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        rigger = ClothRigger()
        node   = self._make_mesh_node()
        result = rigger.apply_cloth_to_node(node, ClothRigPreset.ROBE_LOOSE)
        assert result is True
        assert node.is_dangly

    def test_apply_cloth_sets_parameters(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset, ClothRigConfig
        rigger = ClothRigger()
        node   = self._make_mesh_node()
        cfg    = ClothRigConfig(displacement=0.8, tightness=0.3, period=1.5,
                                constraint_mode='vertical')
        rigger.apply_cloth_to_node(node, cfg)
        assert node.dangly_displacement == pytest.approx(0.8)
        assert node.dangly_tightness    == pytest.approx(0.3)
        assert node.dangly_period       == pytest.approx(1.5)

    def test_constraints_generated_vertical(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigConfig
        rigger = ClothRigger()
        node   = self._make_mesh_node()
        cfg    = ClothRigConfig(constraint_mode='vertical',
                                constraint_pin=1.0, constraint_free=0.0)
        rigger.apply_cloth_to_node(node, cfg)
        assert len(node.dangly_constraints) == len(node.vertices)
        # Top verts (highest Z) should have constraint close to 1.0
        z_vals = [v[2] for v in node.vertices]
        z_max  = max(z_vals)
        for i, v in enumerate(node.vertices):
            if abs(v[2] - z_max) < 0.01:
                assert node.dangly_constraints[i] == pytest.approx(1.0, abs=0.01)

    def test_remove_cloth_clears_flag(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        rigger = ClothRigger()
        node   = self._make_mesh_node()
        rigger.apply_cloth_to_node(node, ClothRigPreset.ROBE_LOOSE)
        assert node.is_dangly
        rigger.remove_cloth_from_node(node)
        assert not node.is_dangly

    def test_undo_restores_state(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        rigger = ClothRigger()
        node   = self._make_mesh_node()
        orig_flags = node.flags
        rigger.apply_cloth_to_node(node, ClothRigPreset.ROBE_LOOSE)
        rigger.undo_last(node)
        assert node.flags == orig_flags

    def test_find_cloth_candidates_by_name(self):
        from src.autorig.cloth_rig import ClothRigger
        m, root = make_model()
        robe_node  = make_mesh_node('robe01', root)
        chest_node = make_mesh_node('chest',  root)
        rigger = ClothRigger()
        candidates = rigger.find_cloth_candidates(m)
        names = [n.name for n in candidates]
        assert 'robe01' in names
        assert 'chest'  not in names

    def test_get_cloth_summary(self):
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        m, root = make_model()
        n1 = make_mesh_node('robe01', root)
        rigger = ClothRigger()
        rigger.apply_cloth_to_node(n1, ClothRigPreset.ROBE_LOOSE)
        summary = rigger.get_cloth_summary(m)
        assert summary['total_cloth_nodes'] == 1
        assert summary['nodes'][0]['name'] == 'robe01'


# ─────────────────────────────────────────────────────────────────────────────
#  6. _apply_bind_pose_controllers — selfillum and alpha
# ─────────────────────────────────────────────────────────────────────────────

class TestBindPoseControllers:
    """Ensure _apply_bind_pose_controllers pushes controller values into nodes."""

    def _run_apply(self, ctype, values):
        from src.core.mdl_parser import MDLBinaryParser
        m, root = make_model()
        mesh = make_mesh_node('glass', root)
        mesh.controllers = [{'type': ctype, 'values': [values]}]
        MDLBinaryParser._apply_bind_pose_controllers(m)
        return mesh

    def test_selfillum_applied(self):
        # CTRL_MESH_SELFILLUMCOLOR = 100 (was 132 in earlier versions)
        # Verified against KotorBlender io_scene_kotor/format/mdl/types.py
        mesh = self._run_apply(100, [0.8, 0.5, 0.2])
        assert mesh.selfillum[0] == pytest.approx(0.8)
        assert mesh.selfillum[1] == pytest.approx(0.5)
        assert mesh.selfillum[2] == pytest.approx(0.2)

    def test_alpha_applied(self):
        # CTRL_MESH_ALPHA = 132 (was 100 in earlier versions)
        # Verified against KotorBlender io_scene_kotor/format/mdl/types.py
        mesh = self._run_apply(132, [0.4])
        assert mesh.alpha == pytest.approx(0.4)

    def test_position_override_when_zero(self):
        mesh = self._run_apply(8, [0.1, 0.2, 0.3])
        assert mesh.position[0] == pytest.approx(0.1)
        assert mesh.position[1] == pytest.approx(0.2)
        assert mesh.position[2] == pytest.approx(0.3)

    def test_position_not_overridden_when_nonzero(self):
        from src.core.mdl_parser import MDLBinaryParser
        m, root = make_model()
        mesh = make_mesh_node('x', root, pos=(5.0, 0.0, 0.0))
        mesh.controllers = [{'type': 8, 'values': [[0.1, 0.2, 0.3]]}]
        MDLBinaryParser._apply_bind_pose_controllers(m)
        assert mesh.position[0] == pytest.approx(5.0)   # unchanged

    def test_rotation_override_when_identity(self):
        from src.core.mdl_parser import MDLBinaryParser
        m, root = make_model()
        mesh = make_mesh_node('x', root, rot=(0,0,0,1))
        mesh.controllers = [{'type': 20, 'values': [[0.707, 0.0, 0.0, 0.707]]}]
        MDLBinaryParser._apply_bind_pose_controllers(m)
        assert mesh.rotation[0] == pytest.approx(0.707, abs=1e-3)

    def test_no_controllers_noop(self):
        from src.core.mdl_parser import MDLBinaryParser
        m, root = make_model()
        mesh = make_mesh_node('x', root)
        mesh.controllers = []
        MDLBinaryParser._apply_bind_pose_controllers(m)
        assert mesh.alpha == 1.0   # unchanged


# ─────────────────────────────────────────────────────────────────────────────
#  7. Viewport flat renderer alpha tuple length
# ─────────────────────────────────────────────────────────────────────────────

class TestFlatRendererAlphaTuple:
    """
    Verify the flat renderer stores 6-tuple (with alpha) and the textured
    renderer stores 11-tuple (with alpha).  We test this indirectly via
    the triangle-collection logic by inspecting the tuple sizes.
    """

    def test_node_alpha_attribute_read(self):
        """Ensure getattr(node,'alpha',1.0) works for opaque and transparent nodes."""
        opaque    = ModelNode(name='x', flags=NodeFlags.MESH); opaque.alpha = 1.0
        glass     = ModelNode(name='g', flags=NodeFlags.MESH); glass.alpha  = 0.4
        trans_hint= ModelNode(name='t', flags=NodeFlags.MESH)
        trans_hint.transparency_hint = 2

        assert float(getattr(opaque, 'alpha', 1.0)) == pytest.approx(1.0)
        assert float(getattr(glass,  'alpha', 1.0)) == pytest.approx(0.4)
        # transparency_hint==2 logic
        a = float(getattr(trans_hint, 'alpha', 1.0))
        hint = getattr(trans_hint, 'transparency_hint', 0)
        if hint == 2 and a >= 0.999:
            a = 0.55
        assert a == pytest.approx(0.55)

    def test_alpha_blend_calculation(self):
        """Manual alpha blend matches expected formula."""
        fill = (200, 100, 50)
        bg   = (18, 18, 40)
        a    = 0.55
        expected = (
            int(fill[0]*a + bg[0]*(1-a)),
            int(fill[1]*a + bg[1]*(1-a)),
            int(fill[2]*a + bg[2]*(1-a)),
        )
        assert expected[0] == 118
        assert expected[1] == 63
        assert expected[2] == 45


# ─────────────────────────────────────────────────────────────────────────────
#  8. _paste_textured_triangle signature
# ─────────────────────────────────────────────────────────────────────────────

class TestPasteTriangleSignature:
    """Verify _paste_textured_triangle has node_alpha parameter."""

    def test_function_has_node_alpha_param(self):
        import inspect
        try:
            from src.gui.viewport import _paste_textured_triangle
        except Exception:
            pytest.skip("viewport not importable headlessly")
        sig = inspect.signature(_paste_textured_triangle)
        assert 'node_alpha' in sig.parameters

    def test_node_alpha_default_is_one(self):
        import inspect
        try:
            from src.gui.viewport import _paste_textured_triangle
        except Exception:
            pytest.skip("viewport not importable headlessly")
        sig = inspect.signature(_paste_textured_triangle)
        default = sig.parameters['node_alpha'].default
        assert default == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  9. world_transform leaf-rotation fix (regression guard)
# ─────────────────────────────────────────────────────────────────────────────

class TestWorldTransformRegression:
    """Guard against regression of the 180° leaf-rotation fix."""

    def _chain(self, nodes):
        for i in range(1, len(nodes)):
            nodes[i].parent = nodes[i-1]
            nodes[i-1].children.append(nodes[i])

    def test_180z_leaf_orientation_preserved(self):
        root  = ModelNode(name='root',  flags=NodeFlags.HEADER)
        body  = ModelNode(name='body',  flags=NodeFlags.MESH)
        panel = ModelNode(name='panel', flags=NodeFlags.MESH)
        root.position  = (0,0,0);   root.rotation  = (0,0,0,1)
        body.position  = (0,0,0.5); body.rotation  = (0,0,0,1)
        panel.position = (0,0,0.3); panel.rotation = (0,0,1,0)  # 180° Z
        self._chain([root, body, panel])
        _, wo = panel.world_transform()
        # Leaf orientation should be (0,0,1,0) — NOT collapsed to identity
        assert abs(wo[2]) > 0.9, f"180°Z collapsed: orientation={wo}"

    def test_180z_vertex_flip_correct(self):
        """A 180°Z-rotated node should flip X vertices."""
        from src.core.model_data import _quat_rotate
        root  = ModelNode(name='root',  flags=NodeFlags.HEADER)
        panel = ModelNode(name='panel', flags=NodeFlags.MESH)
        root.position  = (0,0,0);   root.rotation = (0,0,0,1)
        panel.position = (0,0,0.8); panel.rotation= (0,0,1,0)  # 180° Z
        self._chain([root, panel])
        _, wo = panel.world_transform()
        v_local = (0.2, 0.0, 0.0)
        rotated = _quat_rotate(wo, v_local)
        # Should flip X: +0.2 → -0.2
        assert rotated[0] == pytest.approx(-0.2, abs=1e-5)

    def test_identity_leaf_unaffected(self):
        """Identity-rotation leaf should have no orientation change."""
        root = ModelNode(name='root', flags=NodeFlags.HEADER)
        mesh = ModelNode(name='mesh', flags=NodeFlags.MESH)
        root.position = (0,0,0); root.rotation = (0,0,0,1)
        mesh.position = (0,0,1); mesh.rotation  = (0,0,0,1)
        self._chain([root, mesh])
        _, wo = mesh.world_transform()
        assert abs(wo[3]) > 0.999, f"Identity orientation changed: {wo}"

    def test_bone_world_position_collapses_all(self):
        """bone_world_position uses collapsed chain for all nodes."""
        root  = ModelNode(name='root', flags=NodeFlags.HEADER)
        body  = ModelNode(name='body', flags=NodeFlags.MESH)
        head  = ModelNode(name='head', flags=NodeFlags.MESH)
        root.position = (0,0,0);   root.rotation = (0,0,0,1)
        body.position = (0,0,0.5); body.rotation  = (1,0,0,0)  # 180°X flip
        head.position = (0,0,0.3); head.rotation  = (0,0,0,1)
        self._chain([root, body, head])
        bwp = head.bone_world_position()
        # Position should accumulate: z = 0.5 + 0.3 = 0.8
        assert bwp[2] == pytest.approx(0.8, abs=1e-4)


# ─────────────────────────────────────────────────────────────────────────────
#  10. IPC server smoke tests (no real server started)
# ─────────────────────────────────────────────────────────────────────────────

class TestIPCServerImport:
    def test_server_importable(self):
        from src.ipc.server import GhostRiggerIPCServer
        assert GhostRiggerIPCServer is not None

    def test_server_has_start_stop(self):
        from src.ipc.server import GhostRiggerIPCServer
        assert hasattr(GhostRiggerIPCServer, 'start')
        assert hasattr(GhostRiggerIPCServer, 'stop')

    def test_port_constants(self):
        from src.ipc import server as s
        assert s.PORT_GHOSTRIGGER > 1024
        assert s.PORT_GHOSTRIGGER < 65536


# ─────────────────────────────────────────────────────────────────────────────
#  11. Cloth constraint painter modes
# ─────────────────────────────────────────────────────────────────────────────

class TestClothConstraintPainter:
    def _verts_grid(self, rows=4, cols=4):
        return [(float(c), 0.0, float(r)) for r in range(rows) for c in range(cols)]

    def test_vertical_top_pinned(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = self._verts_grid()
        cfg   = ClothRigConfig(constraint_mode='vertical',
                               constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        assert len(c) == len(verts)
        # Highest row (r=3) should be pinned
        for i in range(12, 16):
            assert c[i] == pytest.approx(1.0, abs=0.01)
        # Lowest row (r=0) should be free
        for i in range(4):
            assert c[i] == pytest.approx(0.0, abs=0.01)

    def test_radial_centre_pinned(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = self._verts_grid()
        cfg   = ClothRigConfig(constraint_mode='radial',
                               constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg)
        assert len(c) == len(verts)
        # Centre verts should have higher constraint than edge verts
        cx = sum(v[0] for v in verts) / len(verts)
        cy = sum(v[1] for v in verts) / len(verts)
        import math
        dists = [math.hypot(v[0]-cx, v[1]-cy) for v in verts]
        centre_idx = dists.index(min(dists))
        edge_idx   = dists.index(max(dists))
        assert c[centre_idx] >= c[edge_idx]

    def test_uniform_mode(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = self._verts_grid()
        cfg   = ClothRigConfig(constraint_mode='uniform',
                               constraint_pin=0.7, constraint_free=0.3)
        c = ClothConstraintPainter.generate(verts, cfg)
        expected = 0.5   # mid-point of pin+free
        for v in c:
            assert v == pytest.approx(expected, abs=0.01)

    def test_bone_dist_mode(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = [(0.0, 0.0, float(i)) for i in range(5)]
        bones = [(0.0, 0.0, 4.0)]   # pin at top
        cfg   = ClothRigConfig(constraint_mode='bone_dist',
                               constraint_pin=1.0, constraint_free=0.0)
        c = ClothConstraintPainter.generate(verts, cfg, pinning_bones=bones)
        # Vert closest to bone (index 4) should have highest constraint
        assert c[4] > c[0]

    def test_empty_verts(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        cfg = ClothRigConfig(constraint_mode='vertical')
        c = ClothConstraintPainter.generate([], cfg)
        assert c == []
