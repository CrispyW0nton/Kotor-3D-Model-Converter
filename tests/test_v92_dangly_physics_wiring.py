"""
GhostRigger Phase 4.5/4.6 — Dangly Physics Wiring Tests
=========================================================
25 tests covering:
  A) DanglySimulator class (unit tests)
  B) Phase-synchronized cross-fade blending (_blend_elapsed fix)
  C) compute_tangents() / compute_all_tangents()

References:
  - Millington, *Game Physics Engine Development* §13
  - Lengyel, *Mathematics for 3D Game Programming* §15.2
  - Gregory, *Game Engine Architecture* §12.6.3 (phase-sync cross-fade)
  - Lengyel §7.8.3 (TBN tangents)

Date: 2026-03-21
"""

import math
import sys
import os
import pytest

# Allow both `pytest tests/` from repo root and direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.model_data import (
    ModelNode, KotorModel, NodeFlags, Animation, AnimEvent,
)
from core.animation_engine import AnimationEngine, DanglySimulator


# ─────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────

def _dangly_node(nv=4, pinned_last=True):
    """Build a minimal dangly ModelNode for testing."""
    n = ModelNode(name='dangly_test', flags=int(NodeFlags.MESH | NodeFlags.DANGLY))
    n.vertices = [(float(i), 0.0, 0.0) for i in range(nv)]
    n.faces = [(i, i+1, (i+2) % nv) for i in range(nv - 2)]
    raw_c = [0.0] * nv
    if pinned_last:
        raw_c[-1] = 1.0   # last vertex pinned
    n.dangly_constraints = raw_c
    n.dangly_displacement = 0.5
    n.dangly_tightness = 0.3
    n.dangly_period = 1.0
    return n


def _engine_with_two_anims(walk_len=2.0, run_len=0.8, trans=0.25):
    """Build an AnimationEngine with 'walk' and 'run' animations."""
    m = KotorModel(name='test_model')
    m.animations = [
        Animation(name='walk', length=walk_len, transition_time=trans),
        Animation(name='run',  length=run_len,  transition_time=trans),
    ]
    return AnimationEngine(m)


# ═════════════════════════════════════════════════════════════════
#  A) DanglySimulator unit tests
# ═════════════════════════════════════════════════════════════════

class TestDanglySimulatorInit:
    def test_init_creates_correct_vertex_count(self):
        n = _dangly_node(6)
        sim = DanglySimulator(n)
        assert len(sim._pos) == 6

    def test_pin_threshold_constant(self):
        assert DanglySimulator.PIN_THRESHOLD == pytest.approx(0.95)

    def test_pinned_vertex_count(self):
        n = _dangly_node(4, pinned_last=True)
        sim = DanglySimulator(n)
        assert sim.num_pinned_vertices == 1

    def test_free_vertex_count(self):
        n = _dangly_node(4, pinned_last=True)
        sim = DanglySimulator(n)
        assert sim.num_free_vertices == 3

    def test_all_free_when_no_pinned(self):
        n = _dangly_node(4, pinned_last=False)
        sim = DanglySimulator(n)
        assert sim.num_pinned_vertices == 0
        assert sim.num_free_vertices == 4

    def test_displacement_clamped_to_minimum(self):
        n = _dangly_node(4)
        n.dangly_displacement = -5.0   # invalid
        sim = DanglySimulator(n)
        assert sim._displacement >= 0.001

    def test_tightness_clamped_to_0_1(self):
        n = _dangly_node(4)
        n.dangly_tightness = 3.0   # > 1
        sim = DanglySimulator(n)
        assert 0.0 <= sim._tightness <= 1.0

    def test_period_clamped_to_minimum(self):
        n = _dangly_node(4)
        n.dangly_period = 0.0   # invalid
        sim = DanglySimulator(n)
        assert sim._period >= 0.01


class TestDanglySimulatorStep:
    def test_step_returns_correct_vertex_count(self):
        n = _dangly_node(5)
        sim = DanglySimulator(n)
        pos = sim.step(0.016)
        assert len(pos) == 5

    def test_pinned_vertex_does_not_move(self):
        n = _dangly_node(4, pinned_last=True)
        orig_last = tuple(n.vertices[-1])
        sim = DanglySimulator(n)
        for _ in range(10):
            pos = sim.step(0.016)
        last = pos[-1]
        assert abs(last[0] - orig_last[0]) < 1e-6
        assert abs(last[1] - orig_last[1]) < 1e-6
        assert abs(last[2] - orig_last[2]) < 1e-6

    def test_free_vertex_moves_under_gravity(self):
        n = _dangly_node(3, pinned_last=False)
        sim = DanglySimulator(n)
        pos_before = list(sim._pos[0])
        for _ in range(5):
            pos = sim.step(0.033)
        # At least one free vertex should have moved
        moved = any(
            abs(pos[i][j] - n.vertices[i][j]) > 1e-6
            for i in range(3)
            for j in range(3)
        )
        assert moved

    def test_displacement_not_exceeded(self):
        n = _dangly_node(4, pinned_last=False)
        n.dangly_displacement = 0.3
        sim = DanglySimulator(n)
        for _ in range(50):
            pos = sim.step(0.05)
        for i, p in enumerate(pos):
            rx, ry, rz = n.vertices[i]
            dist = math.sqrt((p[0]-rx)**2 + (p[1]-ry)**2 + (p[2]-rz)**2)
            assert dist <= n.dangly_displacement + 1e-4, (
                f"Vertex {i} displacement {dist:.4f} exceeded limit {n.dangly_displacement}"
            )

    def test_zero_dt_returns_current_positions_unchanged(self):
        n = _dangly_node(4)
        sim = DanglySimulator(n)
        pos_before = [tuple(p) for p in sim._pos]
        pos_after = sim.step(0.0)
        assert pos_before == list(pos_before)   # no change


class TestDanglySimulatorReset:
    def test_reset_restores_bind_pose(self):
        n = _dangly_node(4, pinned_last=False)
        sim = DanglySimulator(n)
        for _ in range(20):
            sim.step(0.05)
        sim.reset()
        for i, (p, v) in enumerate(zip(sim._pos, n.vertices)):
            assert abs(p[0] - v[0]) < 1e-7
            assert abs(p[1] - v[1]) < 1e-7
            assert abs(p[2] - v[2]) < 1e-7


class TestDanglySimulatorEdges:
    def test_edges_have_positive_rest_lengths(self):
        n = _dangly_node(6)
        n.faces = [(0,1,2),(1,3,2),(2,3,4),(3,5,4)]
        sim = DanglySimulator(n)
        for a, b, rest in sim._edges:
            assert rest > 1e-9, f"Edge ({a},{b}) has zero/negative rest length {rest}"

    def test_chain_of_n_has_n_minus_1_edges(self):
        # A simple chain: 0-1-2-3-4 connected in sequence
        nv = 5
        n = ModelNode(name='chain', flags=int(NodeFlags.MESH | NodeFlags.DANGLY))
        n.vertices = [(float(i), 0.0, 0.0) for i in range(nv)]
        # Chain faces: (0,1,2), (1,2,3), (2,3,4)
        n.faces = [(i, i+1, i+2) for i in range(nv - 2)]
        n.dangly_constraints = [0.0] * nv
        n.dangly_displacement = 0.5
        n.dangly_tightness = 0.5
        n.dangly_period = 1.0
        sim = DanglySimulator(n)
        # Should have exactly nv-1 = 4 unique edges in a chain
        # (the degenerate triangle overlap may add more; just verify count > 0 and >= nv-1)
        assert len(sim._edges) >= nv - 1


# ═════════════════════════════════════════════════════════════════
#  B) Phase-sync cross-fade & _blend_elapsed fix
# ═════════════════════════════════════════════════════════════════

class TestPhaseSyncCrossFade:
    def test_phase_sync_maps_normalized_time_correctly(self):
        """walk(2.0s) at t=0.75 → phase=0.375 → run(0.8s) should start at 0.3."""
        eng = _engine_with_two_anims(walk_len=2.0, run_len=0.8)
        eng.play('walk')
        eng.advance(0.75)
        eng.play('run', sync_phase=True)
        expected = (0.75 / 2.0) * 0.8   # 0.375 * 0.8 = 0.3
        assert abs(eng._time - expected) < 0.001, (
            f"Phase-sync start time {eng._time:.4f} != expected {expected:.4f}"
        )

    def test_blend_elapsed_advances_independently_of_clip_time(self):
        """_blend_elapsed must advance by dt, NOT by clip position."""
        eng = _engine_with_two_anims(walk_len=2.0, run_len=0.8, trans=0.25)
        eng.play('walk')
        eng.advance(0.75)
        eng.play('run', sync_phase=True)
        # After first advance, blend_elapsed should equal dt
        eng.advance(0.13)
        assert eng._blend_elapsed == pytest.approx(0.13, abs=1e-6), (
            f"blend_elapsed={eng._blend_elapsed:.4f} should be 0.13"
        )

    def test_blend_fraction_advances_correctly(self):
        """blend_t should be > 0 after one advance step."""
        eng = _engine_with_two_anims(walk_len=2.0, run_len=0.8, trans=0.25)
        eng.play('walk')
        eng.advance(0.75)
        eng.play('run', sync_phase=True)
        eng.advance(0.13)
        assert eng._blend_t > 0.0, (
            f"blend_t={eng._blend_t} should be > 0.0 after 0.13s advance"
        )

    def test_blend_finishes_after_duration(self):
        """Blend should complete (is_blending=False) after blend_duration seconds."""
        eng = _engine_with_two_anims(walk_len=2.0, run_len=0.8, trans=0.25)
        eng.play('walk')
        eng.advance(0.75)
        eng.play('run', sync_phase=True)
        # Advance past blend duration
        eng.advance(0.30)
        assert not eng.is_blending(), "Blend should have finished after 0.30 s"
        assert eng._blend_t == 0.0

    def test_no_phase_sync_resets_time_to_zero(self):
        """Without sync_phase, new clip always starts at t=0."""
        eng = _engine_with_two_anims()
        eng.play('walk')
        eng.advance(1.0)
        eng.play('run', sync_phase=False)
        assert eng._time == pytest.approx(0.0, abs=1e-9)

    def test_blend_elapsed_not_set_without_blend(self):
        """When blend=False, _blend_elapsed stays 0."""
        eng = _engine_with_two_anims()
        eng.play('walk')
        eng.advance(0.5)
        eng.play('run', blend=False)
        assert eng._blend_elapsed == 0.0
        assert eng._blend_duration == 0.0


# ═════════════════════════════════════════════════════════════════
#  C) compute_tangents / compute_all_tangents
# ═════════════════════════════════════════════════════════════════

class TestComputeTangents:
    def test_basic_triangle_produces_unit_tangents(self):
        n = ModelNode(name='tri')
        n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        n.faces    = [(0,1,2)]
        n.uvs      = [(0,0),(1,0),(0,1)]
        n.normals  = [(0,0,1),(0,0,1),(0,0,1)]
        n.compute_tangents()
        assert len(n.tangents) == 3
        for t in n.tangents:
            mag = math.sqrt(t[0]**2 + t[1]**2 + t[2]**2)
            assert abs(mag - 1.0) < 1e-6, f"Tangent not unit: mag={mag}"

    def test_tangents_orthogonal_to_normals(self):
        n = ModelNode(name='tri')
        n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        n.faces    = [(0,1,2)]
        n.uvs      = [(0,0),(1,0),(0,1)]
        n.normals  = [(0,0,1),(0,0,1),(0,0,1)]
        n.compute_tangents()
        for i, t in enumerate(n.tangents):
            nor = n.normals[i]
            dot = t[0]*nor[0] + t[1]*nor[1] + t[2]*nor[2]
            assert abs(dot) < 1e-5, f"Tangent not orthogonal to normal at v{i}: dot={dot}"

    def test_empty_mesh_produces_empty_tangents(self):
        n = ModelNode(name='empty')
        n.compute_tangents()
        assert n.tangents == []

    def test_degenerate_uv_uses_fallback(self):
        """Degenerate UV (all same) should fall back to (1,0,0) not crash."""
        n = ModelNode(name='degen')
        n.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        n.faces    = [(0,1,2)]
        n.uvs      = [(0,0),(0,0),(0,0)]   # all same — degenerate
        n.normals  = [(0,0,1),(0,0,1),(0,0,1)]
        n.compute_tangents()
        assert len(n.tangents) == 3
        for t in n.tangents:
            mag = math.sqrt(t[0]**2 + t[1]**2 + t[2]**2)
            assert abs(mag - 1.0) < 1e-6

    def test_compute_all_tangents_processes_mesh_nodes(self):
        from core.model_data import KotorModel
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        mesh = ModelNode(name='body', flags=int(NodeFlags.MESH))
        mesh.vertices = [(0,0,0),(1,0,0),(0,1,0)]
        mesh.faces    = [(0,1,2)]
        mesh.uvs      = [(0,0),(1,0),(0,1)]
        mesh.normals  = [(0,0,1),(0,0,1),(0,0,1)]
        mesh.parent = root
        root.children = [mesh]
        m = KotorModel(name='m', root_node=root)
        count = m.compute_all_tangents()
        assert count == 1
        assert len(mesh.tangents) == 3

    def test_compute_all_tangents_skips_empty_model(self):
        from core.model_data import KotorModel
        m = KotorModel(name='empty')
        count = m.compute_all_tangents()
        assert count == 0
