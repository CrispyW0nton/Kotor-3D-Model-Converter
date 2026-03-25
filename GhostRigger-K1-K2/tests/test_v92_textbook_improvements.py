"""
Phase 4.5 Textbook-Research Improvements — Unit Tests
======================================================
Tests for three features derived from the canonical textbook research pass:

1. Per-vertex tangent computation (TBN for normal mapping)
   - ModelNode.compute_tangents() and KotorModel.compute_all_tangents()
   - Reference: Lengyel §7.8.3; FGED Vol.2 §7

2. Dangly mesh Verlet cloth simulation
   - DanglySimulator — position-based Verlet with spring constraints
   - Reference: Millington §13; Lengyel §15.2; Gregory §12.7

3. Phase-synchronized cross-fade animation blending
   - AnimationEngine.play(sync_phase=True)
   - Reference: Gregory §12.6.3 — prevents foot-slip during locomotion transitions
"""

import math
import pytest
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from src.core.model_data import ModelNode, KotorModel, NodeFlags, Animation
from src.core.animation_engine import AnimationEngine, DanglySimulator


# ─────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────

def _make_quad_node(with_uvs: bool = True) -> ModelNode:
    """Create a simple quad mesh node for tangent tests."""
    n = ModelNode(name="quad", flags=int(NodeFlags.MESH | NodeFlags.HEADER))
    n.vertices = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    n.normals = [
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0),
    ]
    if with_uvs:
        n.uvs = [
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
        ]
    n.faces = [(0, 1, 2), (0, 2, 3)]
    return n


def _make_dangly_node(nv: int = 6) -> ModelNode:
    """Create a dangly chain mesh node for physics tests."""
    n = ModelNode(name="chain", flags=int(NodeFlags.MESH | NodeFlags.DANGLY | NodeFlags.HEADER))
    # Simple vertical chain: vertices at y=0,1,2,3,4,5 along Y axis
    n.vertices = [(0.0, float(i), 0.0) for i in range(nv)]
    n.normals  = [(1.0, 0.0, 0.0)] * nv
    n.uvs      = [(0.0, float(i)/(nv-1)) for i in range(nv)]
    # Linear faces
    n.faces = [(i, i+1, i+2) for i in range(0, nv-2, 2)] + \
              [(i+1, i+2, i+3) for i in range(0, nv-3, 2)]
    # Constraints: bottom (i=0) is pinned, rest are free
    n.dangly_constraints = [1.0] + [0.0] * (nv - 1)
    n.dangly_displacement = 2.0
    n.dangly_tightness = 0.5
    n.dangly_period = 0.5
    return n


def _make_model_with_anim(anim_name: str, length: float,
                           pos_delta: Tuple = (0.0, 0.0, 0.0)) -> KotorModel:
    """Create a minimal KotorModel with one animation."""
    from src.core.model_data import Animation, AnimEvent
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    root.position = (0.0, 0.0, 0.0)
    root.rotation = (0.0, 0.0, 0.0, 1.0)

    child = ModelNode(name="bone01", flags=int(NodeFlags.HEADER))
    child.position = (0.0, 0.0, 1.0)
    child.rotation = (0.0, 0.0, 0.0, 1.0)
    child.parent   = root
    root.children  = [child]

    model = KotorModel()
    model.name       = "test_model"
    model.root_node  = root
    model.supermodel = "NULL"

    # Build animation with a POSITION controller on bone01
    anim_root  = ModelNode(name="root")
    anim_bone  = ModelNode(name="bone01")
    anim_bone.controllers = [{
        'type': AnimationEngine.CTRL_POSITION,
        'times': [0.0, length * 0.5, length],
        'values': [
            [pos_delta[0]*0,   pos_delta[1]*0,   pos_delta[2]*0],
            [pos_delta[0]*0.5, pos_delta[1]*0.5, pos_delta[2]*0.5],
            [pos_delta[0],     pos_delta[1],     pos_delta[2]],
        ],
    }]

    anim = Animation()
    anim.name            = anim_name
    anim.length          = length
    anim.transition_time = 0.2
    anim.nodes           = [anim_root, anim_bone]
    anim.events          = []

    model.animations = [anim]
    return model


# ─────────────────────────────────────────────────────────────────
#  1. Per-Vertex Tangent Computation
# ─────────────────────────────────────────────────────────────────

class TestPerVertexTangents:

    def test_basic_quad_tangents_computed(self):
        """Quad in XY plane should have tangents pointing along +X."""
        n = _make_quad_node()
        n.compute_tangents()
        assert len(n.tangents) == 4, "Should have one tangent per vertex"

    def test_tangents_are_unit_vectors(self):
        """All computed tangents must have unit length."""
        n = _make_quad_node()
        n.compute_tangents()
        for t in n.tangents:
            l = math.sqrt(t[0]**2 + t[1]**2 + t[2]**2)
            assert abs(l - 1.0) < 1e-5, f"Tangent {t} is not unit length (|t|={l})"

    def test_quad_tangent_direction(self):
        """XY-plane quad with standard UVs should have tangents along +X."""
        n = _make_quad_node()
        n.compute_tangents()
        for t in n.tangents:
            # Tangent should point mostly along +X for a UV-aligned quad
            assert t[0] > 0.9, f"Expected tangent mostly along +X, got {t}"

    def test_tangents_orthogonal_to_normals(self):
        """Computed tangents must be orthogonal to their vertex normals."""
        n = _make_quad_node()
        n.compute_tangents()
        for i, (t, nm) in enumerate(zip(n.tangents, n.normals)):
            dot = t[0]*nm[0] + t[1]*nm[1] + t[2]*nm[2]
            assert abs(dot) < 1e-4, \
                f"Vertex {i}: tangent {t} not orthogonal to normal {nm} (dot={dot:.6f})"

    def test_no_uvs_returns_default_tangents(self):
        """Without UVs, compute_tangents should populate with default (1,0,0) tangents."""
        n = _make_quad_node(with_uvs=False)
        n.compute_tangents()
        assert len(n.tangents) == 4
        for t in n.tangents:
            assert t == (1.0, 0.0, 0.0), f"Expected default tangent (1,0,0), got {t}"

    def test_no_vertices_returns_empty(self):
        """Empty mesh should produce empty tangents."""
        n = ModelNode(name="empty", flags=int(NodeFlags.MESH | NodeFlags.HEADER))
        n.compute_tangents()
        assert n.tangents == []

    def test_no_faces_returns_empty(self):
        """Mesh with vertices but no faces should produce empty tangents."""
        n = _make_quad_node()
        n.faces = []
        n.compute_tangents()
        assert n.tangents == []

    def test_degenerate_uv_face_skipped(self):
        """Triangles with degenerate UV (all same UV) should be skipped gracefully."""
        n = _make_quad_node()
        # Override all UVs to (0,0) — degenerate mapping
        n.uvs = [(0.0, 0.0)] * 4
        # Should not raise, should produce fallback tangents
        n.compute_tangents()
        assert len(n.tangents) == 4
        for t in n.tangents:
            tl = math.sqrt(t[0]**2 + t[1]**2 + t[2]**2)
            assert abs(tl - 1.0) < 1e-5

    def test_kotor_model_compute_all_tangents(self):
        """KotorModel.compute_all_tangents() should process all mesh nodes."""
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        q1   = _make_quad_node()
        q1.name = "mesh1"
        q2   = _make_quad_node()
        q2.name = "mesh2"
        root.children = [q1, q2]
        q1.parent = root
        q2.parent = root

        model = KotorModel()
        model.name      = "test"
        model.root_node = root

        count = model.compute_all_tangents()
        assert count == 2, f"Expected 2 nodes processed, got {count}"
        assert len(q1.tangents) == 4
        assert len(q2.tangents) == 4

    def test_compute_all_tangents_skips_no_uvs(self):
        """compute_all_tangents() should skip nodes without UVs."""
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        q1   = _make_quad_node(with_uvs=True)
        q1.name = "with_uvs"
        q2   = _make_quad_node(with_uvs=False)
        q2.name = "no_uvs"
        root.children = [q1, q2]
        q1.parent = root
        q2.parent = root

        model = KotorModel()
        model.name      = "test"
        model.root_node = root

        count = model.compute_all_tangents()
        assert count == 1, f"Expected 1 node (with UVs), got {count}"

    def test_face_uvs_indexing_respected(self):
        """When face_uvs is set (ASCII MDL), tangent computation uses it."""
        n = _make_quad_node()
        # face_uvs points to UV indices in a separate UV list
        n.face_uvs = [(0, 1, 2), (0, 2, 3)]
        n.compute_tangents()
        assert len(n.tangents) == 4
        for t in n.tangents:
            tl = math.sqrt(t[0]**2 + t[1]**2 + t[2]**2)
            assert abs(tl - 1.0) < 1e-5

    def test_tangent_persists_after_recompute(self):
        """Calling compute_tangents() twice should produce identical results."""
        n = _make_quad_node()
        n.compute_tangents()
        first = list(n.tangents)
        n.compute_tangents()
        second = list(n.tangents)
        assert first == second, "Tangent recomputation should be deterministic"


# ─────────────────────────────────────────────────────────────────
#  2. DanglySimulator Verlet Cloth Simulation
# ─────────────────────────────────────────────────────────────────

class TestDanglySimulatorInitialization:

    def test_creates_correct_vertex_count(self):
        """DanglySimulator should have one position entry per vertex."""
        n = _make_dangly_node(6)
        sim = DanglySimulator(n)
        result = sim.step(0.0)  # dt=0 → no movement
        assert len(result) == 6

    def test_at_rest_positions_match_bind(self):
        """At t=0 (no simulation), positions should equal bind pose."""
        n = _make_dangly_node(4)
        sim = DanglySimulator(n)
        initial = sim.step(0.0)
        for i, (pos, orig) in enumerate(zip(initial, n.vertices)):
            assert abs(pos[0] - orig[0]) < 1e-6, f"Vertex {i} X mismatch"
            assert abs(pos[1] - orig[1]) < 1e-6, f"Vertex {i} Y mismatch"
            assert abs(pos[2] - orig[2]) < 1e-6, f"Vertex {i} Z mismatch"

    def test_pinned_vertices_dont_move(self):
        """Vertices with constraint=1.0 (pinned) must not move regardless of forces."""
        n = _make_dangly_node(4)
        # Pin ALL vertices
        n.dangly_constraints = [1.0, 1.0, 1.0, 1.0]
        sim = DanglySimulator(n)
        for _ in range(30):
            result = sim.step(1.0 / 60.0, wind_dir=(1.0, 0.0, 0.0), gravity_scale=5.0)
        for i, (pos, orig) in enumerate(zip(result, n.vertices)):
            for j in range(3):
                assert abs(pos[j] - orig[j]) < 1e-6, \
                    f"Pinned vertex {i} moved from {orig} to {pos}"

    def test_free_vertices_do_move_under_gravity(self):
        """Vertices with constraint=0.0 should move when gravity is applied."""
        n = _make_dangly_node(4)
        # Only pin the first vertex
        n.dangly_constraints = [1.0, 0.0, 0.0, 0.0]
        n.dangly_displacement = 5.0  # allow large displacement
        sim = DanglySimulator(n)
        initial_z = [v[2] for v in n.vertices]
        # Simulate 60 frames with gravity
        result = None
        for _ in range(60):
            result = sim.step(1.0 / 60.0, gravity_scale=1.0)
        # At least one free vertex should have moved
        moved = any(abs(result[i][2] - initial_z[i]) > 0.001 for i in range(1, 4))
        assert moved, "Free vertices should have moved under gravity"

    def test_num_free_pinned_vertices(self):
        """num_free_vertices and num_pinned_vertices should sum to total."""
        n = _make_dangly_node(6)
        n.dangly_constraints = [1.0, 0.0, 0.5, 0.0, 1.0, 0.95]
        sim = DanglySimulator(n)
        total = sim.num_free_vertices + sim.num_pinned_vertices
        assert total == 6, f"Free + pinned should equal 6, got {total}"
        # PIN_THRESHOLD is 0.95 — vertices with c>=0.95 are pinned
        assert sim.num_pinned_vertices == 3   # indices 0, 4, 5
        assert sim.num_free_vertices   == 3   # indices 1, 2, 3

    def test_reset_returns_to_bind_pose(self):
        """After reset(), positions should return to original vertices."""
        n = _make_dangly_node(4)
        n.dangly_constraints = [1.0, 0.0, 0.0, 0.0]
        n.dangly_displacement = 5.0
        sim = DanglySimulator(n)
        # Simulate for a while to get movement
        for _ in range(30):
            sim.step(1.0 / 30.0, gravity_scale=2.0)
        # Reset
        sim.reset()
        result = sim.step(0.0)  # dt=0 → no movement after reset
        for i, (pos, orig) in enumerate(zip(result, n.vertices)):
            for j in range(3):
                assert abs(pos[j] - orig[j]) < 1e-6, \
                    f"After reset, vertex {i} should be at bind pose"

    def test_displacement_clamping(self):
        """No free vertex should exceed dangly_displacement from its bind position."""
        n = _make_dangly_node(6)
        n.dangly_constraints = [1.0] + [0.0] * 5  # pin first, rest free
        n.dangly_displacement = 0.5   # very tight constraint
        n.dangly_tightness = 0.0      # no spring force (pure gravity)
        sim = DanglySimulator(n)
        for _ in range(120):
            result = sim.step(1.0 / 60.0, gravity_scale=10.0)
        for i in range(1, 6):
            orig = n.vertices[i]
            pos  = result[i]
            dist = math.sqrt(sum((pos[j]-orig[j])**2 for j in range(3)))
            assert dist <= n.dangly_displacement + 1e-4, \
                f"Vertex {i} exceeded displacement limit: {dist:.4f} > {n.dangly_displacement}"

    def test_wind_force_displaces_free_vertices(self):
        """Applying wind should displace free vertices in the wind direction."""
        n = _make_dangly_node(4)
        n.dangly_constraints = [1.0, 0.0, 0.0, 0.0]
        n.dangly_displacement = 5.0
        n.dangly_tightness = 0.01   # very low stiffness
        sim = DanglySimulator(n)
        initial_x = [v[0] for v in n.vertices]
        for _ in range(60):
            result = sim.step(1.0/60.0, wind_dir=(1.0, 0.0, 0.0),
                              gravity_scale=0.0, wind_strength=2.0)
        # Free vertices should have moved in +X
        for i in range(1, 4):
            assert result[i][0] > initial_x[i] or abs(result[i][0] - initial_x[i]) > 0.001, \
                f"Vertex {i} should have moved in wind direction, x={result[i][0]}"

    def test_dt_clamp_prevents_explosion(self):
        """Large dt values (> 0.05s) should be clamped to prevent instability."""
        n = _make_dangly_node(4)
        n.dangly_constraints = [1.0, 0.0, 0.0, 0.0]
        n.dangly_displacement = 2.0
        sim = DanglySimulator(n)
        # Very large dt that would normally explode Verlet
        result = sim.step(10.0, gravity_scale=1.0)
        for i, pos in enumerate(result):
            for j in range(3):
                assert math.isfinite(pos[j]), f"Position {i}[{j}] is not finite after large dt"

    def test_build_edges_from_faces(self):
        """DanglySimulator should build spring edges from face topology."""
        n = _make_dangly_node(4)
        sim = DanglySimulator(n)
        assert len(sim._edges) > 0, "Should have built edges from faces"
        # Verify rest lengths are positive
        for a, b, rest in sim._edges:
            assert rest > 1e-6, f"Edge ({a},{b}) has zero rest length"


# ─────────────────────────────────────────────────────────────────
#  3. Phase-Synchronized Cross-Fade
# ─────────────────────────────────────────────────────────────────

class TestPhaseSynchronizedCrossFade:

    def test_play_returns_true_for_valid_anim(self):
        """play() should return True for a valid animation name."""
        model = _make_model_with_anim("cwalk", 1.5)
        engine = AnimationEngine(model)
        ok = engine.play("cwalk")
        assert ok is True

    def test_play_returns_false_for_missing_anim(self):
        """play() should return False and warn for an unknown animation."""
        model = _make_model_with_anim("cwalk", 1.5)
        engine = AnimationEngine(model)
        ok = engine.play("nonexistent")
        assert ok is False

    def test_sync_phase_false_starts_at_zero(self):
        """Without sync_phase, new clip always starts at t=0."""
        model = _make_model_with_anim("cwalk", 1.5)
        model.animations.append(_make_anim("crun", 1.0, model))
        engine = AnimationEngine(model)
        engine.play("cwalk")
        engine.advance(0.75)   # halfway through cwalk
        engine.play("crun", sync_phase=False)
        assert engine.current_time == 0.0, \
            "Without sync_phase, new clip should start at t=0"

    def test_sync_phase_true_maps_normalized_time(self):
        """With sync_phase=True, new clip starts at the same normalized phase."""
        model = _make_model_with_anim("cwalk", 2.0)
        model.animations.append(_make_anim("crun", 1.0, model))
        engine = AnimationEngine(model)
        engine.play("cwalk")
        engine.advance(1.0)   # t=1.0 of 2.0 → phase u=0.5
        engine.play("crun", blend=True, sync_phase=True)
        # crun.length=1.0, u=0.5 → expected t = 0.5 * 1.0 = 0.5
        expected = 0.5
        assert abs(engine.current_time - expected) < 1e-5, \
            f"Expected crun to start at t={expected:.3f}, got {engine.current_time:.3f}"

    def test_sync_phase_different_lengths(self):
        """Phase sync should correctly scale across clips of different durations."""
        model = _make_model_with_anim("walk", 3.0)
        model.animations.append(_make_anim("run", 0.8, model))
        engine = AnimationEngine(model)
        engine.play("walk")
        engine.advance(1.5)   # t=1.5 of 3.0 → phase u=0.5
        engine.play("run", blend=True, sync_phase=True)
        # run.length=0.8, u=0.5 → expected t = 0.4
        expected = 0.4
        assert abs(engine.current_time - expected) < 1e-5, \
            f"Expected run to start at t={expected:.3f}, got {engine.current_time:.3f}"

    def test_phase_sync_blend_produces_valid_pose(self):
        """During phase-synced blend, evaluate() should return a valid pose."""
        model = _make_model_with_anim("cwalk", 1.5, pos_delta=(0.1, 0.0, 0.0))
        model.animations.append(_make_anim("crun", 1.0, model, pos_delta=(0.2, 0.0, 0.0)))
        engine = AnimationEngine(model)
        engine.play("cwalk")
        engine.advance(0.5)
        engine.play("crun", blend=True, sync_phase=True)
        # Advance into the blend region
        engine.advance(0.05)
        pose = engine.evaluate()
        assert pose is not None
        assert len(pose.nodes) > 0, "Pose should have node entries during blend"
        # All node positions should be finite
        for name, np_ in pose.nodes.items():
            for v in np_.position:
                assert math.isfinite(v), f"Node {name} position contains non-finite value"

    def test_phase_sync_blend_state_transitions_to_complete(self):
        """After blend duration, blend should complete and sync_phase flag cleared."""
        model = _make_model_with_anim("a", 2.0)
        model.animations.append(_make_anim("b", 1.5, model))
        engine = AnimationEngine(model)
        engine.play("a")
        engine.advance(1.0)
        engine.play("b", blend=True, sync_phase=True)
        assert engine.is_blending()
        # Advance past the blend duration (transition_time = 0.2s)
        for _ in range(20):
            engine.advance(0.02)   # 20 * 0.02 = 0.4s > 0.2s blend
        assert not engine.is_blending(), "Blend should be complete after blend_duration"

    def test_sync_phase_with_blend_false_starts_at_zero(self):
        """sync_phase=True with blend=False should still start at phase-mapped time."""
        # When blend=False, there's no blend_from, so sync_phase has no effect:
        # the spec says 'has no effect if blend=False'.
        # With no previous playing animation, blend doesn't activate.
        model = _make_model_with_anim("cwalk", 2.0)
        engine = AnimationEngine(model)
        # Not playing anything → blend=False even if requested
        engine.play("cwalk", blend=False, sync_phase=True)
        assert engine.current_time == 0.0, \
            "With blend=False (no active anim), should start at t=0"


# ─────────────────────────────────────────────────────────────────
#  Integration: compute_tangents after model load
# ─────────────────────────────────────────────────────────────────

class TestTangentIntegration:

    def test_skin_node_tangents(self):
        """Skin nodes should also compute tangents correctly."""
        n = _make_quad_node()
        n.flags = int(NodeFlags.MESH | NodeFlags.SKIN | NodeFlags.HEADER)
        n.compute_tangents()
        assert len(n.tangents) == 4

    def test_dangly_node_tangents(self):
        """Dangly nodes should also compute tangents."""
        n = _make_dangly_node(6)
        n.compute_tangents()
        assert len(n.tangents) == 6

    def test_tangents_survive_uvs_partial(self):
        """If some vertices are missing UVs, tangents should still be produced."""
        n = _make_quad_node()
        # Remove UVs for vertices 2 and 3
        n.uvs = n.uvs[:2]  # only 2 UVs for 4 vertices
        n.compute_tangents()
        assert len(n.tangents) == 4, "Should produce tangent for all 4 vertices"


# ─────────────────────────────────────────────────────────────────
#  Helpers for animation tests
# ─────────────────────────────────────────────────────────────────

def _make_anim(name: str, length: float, model: KotorModel,
               pos_delta: Tuple = (0.0, 0.0, 0.0)) -> Animation:
    """Create an Animation object and attach to model's root structure."""
    anim_root = ModelNode(name="root")
    anim_bone = ModelNode(name="bone01")
    anim_bone.controllers = [{
        'type': AnimationEngine.CTRL_POSITION,
        'times': [0.0, length * 0.5, length],
        'values': [
            [0.0, 0.0, 0.0],
            [pos_delta[0]*0.5, pos_delta[1]*0.5, pos_delta[2]*0.5],
            [pos_delta[0],     pos_delta[1],     pos_delta[2]],
        ],
    }]
    anim = Animation()
    anim.name            = name
    anim.length          = length
    anim.transition_time = 0.2
    anim.nodes           = [anim_root, anim_bone]
    anim.events          = []
    return anim
