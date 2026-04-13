"""
test_v470_particle_emitter.py — Phase 6.1: CPU Particle Emitter
================================================================
Tests for src/core/particle_emitter.py

Covers:
  • EmitterConfig creation defaults and from_node()
  • EmitterParticle alive / normalized_age properties
  • Interpolation helpers (_lerp, _interp1, _interp3)
  • ParticleEmitter: spawn, update, cull, burst, reset
  • ParticleEmitter: size/color/alpha interpolation
  • ParticleEmitter: spread / velocity generation
  • ParticleEmitter: drag physics
  • ParticleEmitter: flipbook frame calculation
  • ParticleEmitter: build_draw_list sort order
  • ParticleDrawEntry fields
  • LightningEmitter: bolt generation, update cycle
  • EmitterManager: add/remove, update, draw list aggregation
  • Factory functions: make_emitter_from_node, build_emitter_manager_from_model
  • Edge cases: zero dt, zero birth_rate, max_particles cap

All tests run headless (no OpenGL/GPU required).
"""

import math
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.particle_emitter import (
    EmitterConfig, EmitterParticle, ParticleDrawEntry,
    ParticleEmitter, LightningEmitter, EmitterManager,
    make_emitter_from_node, build_emitter_manager_from_model,
    _lerp, _lerp3, _interp1, _interp3, _clamp,
    BLEND_NORMAL, BLEND_LIGHTEN, BLEND_PUNCHTHROUGH,
    RENDER_NORMAL, RENDER_BILLBOARD_WORLD_Z_ROTATE,
    UPDATE_LIGHTNING, UPDATE_BILLBOARD_WORLD_Z,
    CTRL_BIRTHRATE, CTRL_LIFEEXP, CTRL_VELOCITY,
)
from core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_config(**kwargs) -> EmitterConfig:
    """Create an EmitterConfig with overrides."""
    defaults = dict(
        birth_rate=10.0, life_exp=2.0, max_particles=100,
        velocity=1.0, rand_velocity=0.0,
        spread_h=0.0, spread_v=0.0,
        mass=1.0, drag=0.0,
        size_start=0.2, size_mid=0.2, size_end=0.0,
        color_start=(1,1,1), color_mid=(1,1,1), color_end=(0,0,0),
        alpha_start=1.0, alpha_mid=1.0, alpha_end=0.0,
        texture='', grid_x=1, grid_y=1, fps=0.0,
        update_mode=UPDATE_BILLBOARD_WORLD_Z,
        render_mode=RENDER_NORMAL,
        blend_mode=BLEND_NORMAL,
        loop=True, two_sided=False,
        world_pos=(0,0,0),
    )
    defaults.update(kwargs)
    return EmitterConfig(**defaults)


def _make_node_with_emitter_params(**params) -> ModelNode:
    node = ModelNode(name='emit', flags=int(NodeFlags.EMITTER))
    node.emitter_params = params
    return node


# ─────────────────────────────────────────────────────────────────────────────
#  Interpolation Helper Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestInterpolation(unittest.TestCase):

    def test_lerp_zero(self):
        self.assertAlmostEqual(_lerp(0, 10, 0.0), 0.0)

    def test_lerp_one(self):
        self.assertAlmostEqual(_lerp(0, 10, 1.0), 10.0)

    def test_lerp_half(self):
        self.assertAlmostEqual(_lerp(0, 10, 0.5), 5.0)

    def test_lerp3_zero(self):
        r = _lerp3((0,0,0), (10,20,30), 0.0)
        self.assertAlmostEqual(r[0], 0)

    def test_lerp3_one(self):
        r = _lerp3((0,0,0), (10,20,30), 1.0)
        self.assertAlmostEqual(r[1], 20)

    def test_interp1_at_zero(self):
        self.assertAlmostEqual(_interp1(1.0, 2.0, 3.0, 0.0), 1.0)

    def test_interp1_at_half(self):
        self.assertAlmostEqual(_interp1(0.0, 1.0, 2.0, 0.5), 1.0)

    def test_interp1_at_one(self):
        self.assertAlmostEqual(_interp1(0.0, 1.0, 2.0, 1.0), 2.0)

    def test_interp3_at_quarter(self):
        r = _interp3((1,0,0), (0,1,0), (0,0,1), 0.25)
        self.assertAlmostEqual(r[0], 0.5, places=4)

    def test_clamp_lo(self):
        self.assertAlmostEqual(_clamp(-1, 0, 1), 0)

    def test_clamp_hi(self):
        self.assertAlmostEqual(_clamp(2, 0, 1), 1)

    def test_clamp_mid(self):
        self.assertAlmostEqual(_clamp(0.5, 0, 1), 0.5)


# ─────────────────────────────────────────────────────────────────────────────
#  EmitterConfig Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEmitterConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = EmitterConfig()
        self.assertAlmostEqual(cfg.birth_rate, 10.0)
        self.assertAlmostEqual(cfg.life_exp, 2.0)
        self.assertAlmostEqual(cfg.alpha_end, 0.0)

    def test_from_node_defaults(self):
        node = _make_node_with_emitter_params()
        cfg = EmitterConfig.from_node(node)
        self.assertIsInstance(cfg, EmitterConfig)

    def test_from_node_birth_rate(self):
        node = _make_node_with_emitter_params(birthrate=25.0)
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.birth_rate, 25.0)

    def test_from_node_life_exp(self):
        node = _make_node_with_emitter_params(lifeexp=3.5)
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.life_exp, 3.5)

    def test_from_node_velocity(self):
        node = _make_node_with_emitter_params(velocity=5.0)
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.velocity, 5.0)

    def test_from_node_world_pos(self):
        node = _make_node_with_emitter_params()
        node.position = (1.0, 2.0, 3.0)
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.world_pos[0], 1.0)
        self.assertAlmostEqual(cfg.world_pos[2], 3.0)

    def test_from_node_spread(self):
        node = _make_node_with_emitter_params(spreadh=0.5, spreadv=0.3)
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.spread_h, 0.5)
        self.assertAlmostEqual(cfg.spread_v, 0.3)

    def test_from_node_color_start(self):
        node = _make_node_with_emitter_params(colorstart=(0.5, 0.2, 1.0))
        cfg = EmitterConfig.from_node(node)
        self.assertAlmostEqual(cfg.color_start[0], 0.5)

    def test_max_particles(self):
        node = _make_node_with_emitter_params(maxparticles=50)
        cfg = EmitterConfig.from_node(node)
        self.assertEqual(cfg.max_particles, 50)

    def test_texture(self):
        node = _make_node_with_emitter_params(texture='fx_spark')
        cfg = EmitterConfig.from_node(node)
        self.assertEqual(cfg.texture, 'fx_spark')


# ─────────────────────────────────────────────────────────────────────────────
#  EmitterParticle Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEmitterParticle(unittest.TestCase):

    def test_alive_new(self):
        p = EmitterParticle(age=0.0, life=1.0)
        self.assertTrue(p.alive)

    def test_alive_at_end(self):
        p = EmitterParticle(age=1.0, life=1.0)
        self.assertFalse(p.alive)

    def test_dead(self):
        p = EmitterParticle(age=2.0, life=1.0)
        self.assertFalse(p.alive)

    def test_normalized_age_zero(self):
        p = EmitterParticle(age=0.0, life=1.0)
        self.assertAlmostEqual(p.normalized_age, 0.0)

    def test_normalized_age_half(self):
        p = EmitterParticle(age=0.5, life=1.0)
        self.assertAlmostEqual(p.normalized_age, 0.5)

    def test_normalized_age_clamped(self):
        p = EmitterParticle(age=5.0, life=1.0)
        self.assertAlmostEqual(p.normalized_age, 1.0)

    def test_normalized_age_zero_life(self):
        p = EmitterParticle(age=0, life=0)
        self.assertAlmostEqual(p.normalized_age, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  ParticleEmitter — Spawn Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleEmitterSpawn(unittest.TestCase):

    def test_no_particles_at_start(self):
        e = ParticleEmitter(_make_config(birth_rate=10))
        self.assertEqual(e.particle_count, 0)

    def test_spawn_after_update(self):
        e = ParticleEmitter(_make_config(birth_rate=10), seed=42)
        e.update(0.5)    # Should spawn 5 particles
        self.assertGreater(e.particle_count, 0)

    def test_spawn_rate(self):
        e = ParticleEmitter(_make_config(birth_rate=100), seed=0)
        e.update(1.0)    # Should spawn ~100
        self.assertGreater(e.particle_count, 50)

    def test_max_particles_respected(self):
        e = ParticleEmitter(_make_config(birth_rate=1000, max_particles=10, life_exp=10), seed=0)
        e.update(1.0)
        self.assertLessEqual(e.particle_count, 10)

    def test_zero_birth_rate(self):
        e = ParticleEmitter(_make_config(birth_rate=0.0))
        e.update(1.0)
        self.assertEqual(e.particle_count, 0)

    def test_burst_spawns_immediately(self):
        e = ParticleEmitter(_make_config(birth_rate=0, life_exp=10))
        e.burst(5)
        self.assertEqual(e.particle_count, 5)

    def test_burst_respects_max_particles(self):
        e = ParticleEmitter(_make_config(birth_rate=0, max_particles=3, life_exp=10))
        e.burst(10)
        self.assertLessEqual(e.particle_count, 3)

    def test_reset_clears_particles(self):
        e = ParticleEmitter(_make_config(birth_rate=100, life_exp=10), seed=0)
        e.update(1.0)
        e.reset()
        self.assertEqual(e.particle_count, 0)

    def test_elapsed_time_tracked(self):
        e = ParticleEmitter(_make_config())
        e.update(0.5)
        e.update(0.3)
        self.assertAlmostEqual(e.elapsed_time, 0.8, places=5)

    def test_zero_dt_no_spawn(self):
        e = ParticleEmitter(_make_config(birth_rate=1000))
        e.update(0.0)
        self.assertEqual(e.particle_count, 0)


# ─────────────────────────────────────────────────────────────────────────────
#  ParticleEmitter — Cull / Lifetime Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleEmitterCull(unittest.TestCase):

    def test_particles_die_after_lifetime(self):
        e = ParticleEmitter(_make_config(birth_rate=10, life_exp=0.1), seed=0)
        e.update(0.2)  # Spawn ~2
        count_initial = e.particle_count
        e.update(0.5)  # Wait > life_exp — all should die
        self.assertLessEqual(e.particle_count, count_initial)

    def test_all_particles_die(self):
        e = ParticleEmitter(_make_config(birth_rate=100, life_exp=0.01), seed=0)
        e.update(0.1)   # Spawn some
        e.update(1.0)   # Wait much longer
        self.assertEqual(e.particle_count, 0)


# ─────────────────────────────────────────────────────────────────────────────
#  ParticleEmitter — Physics / Movement Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleEmitterPhysics(unittest.TestCase):

    def test_particles_move(self):
        e = ParticleEmitter(_make_config(birth_rate=0, velocity=5.0, life_exp=10), seed=0)
        e.burst(1)
        p0 = (e.particles[0].pos[0], e.particles[0].pos[1], e.particles[0].pos[2])
        e.update(0.1)
        p1 = e.particles[0].pos
        dist = math.sqrt(sum((a-b)**2 for a,b in zip(p0, p1)))
        self.assertGreater(dist, 0.0)

    def test_drag_reduces_speed(self):
        e = ParticleEmitter(_make_config(birth_rate=0, velocity=10.0, drag=5.0, life_exp=100), seed=0)
        e.burst(1)
        speed_init = math.sqrt(sum(v**2 for v in e.particles[0].vel))
        e.update(0.5)
        speed_after = math.sqrt(sum(v**2 for v in e.particles[0].vel))
        self.assertLess(speed_after, speed_init)

    def test_no_drag_constant_speed(self):
        e = ParticleEmitter(_make_config(birth_rate=0, velocity=5.0, drag=0.0, life_exp=100,
                                         spread_h=0, spread_v=0), seed=0)
        e.burst(1)
        speed_init = math.sqrt(sum(v**2 for v in e.particles[0].vel))
        e.update(0.1)
        speed_after = math.sqrt(sum(v**2 for v in e.particles[0].vel))
        self.assertAlmostEqual(speed_init, speed_after, places=4)

    def test_spread_creates_varied_velocities(self):
        e = ParticleEmitter(_make_config(birth_rate=0, velocity=1.0, spread_h=1.0,
                                          spread_v=0.5, life_exp=100), seed=99)
        e.burst(20)
        vx_vals = [p.vel[0] for p in e.particles]
        self.assertGreater(max(vx_vals) - min(vx_vals), 0.0)

    def test_zero_velocity(self):
        e = ParticleEmitter(_make_config(birth_rate=0, velocity=0.0, life_exp=100,
                                          spread_h=0, spread_v=0, drag=0), seed=0)
        e.burst(1)
        pos_before = e.particles[0].pos
        e.update(0.5)
        pos_after = e.particles[0].pos
        dist = math.sqrt(sum((a-b)**2 for a,b in zip(pos_before, pos_after)))
        self.assertAlmostEqual(dist, 0.0, places=5)


# ─────────────────────────────────────────────────────────────────────────────
#  ParticleEmitter — Appearance Interpolation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleEmitterAppearance(unittest.TestCase):

    def test_size_starts_at_size_start(self):
        cfg = _make_config(birth_rate=0, life_exp=100, size_start=0.5, size_mid=0.5, size_end=0.5)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        self.assertAlmostEqual(e.particles[0].size, 0.5, places=3)

    def test_alpha_decreases_with_age(self):
        cfg = _make_config(birth_rate=0, life_exp=2.0,
                            alpha_start=1.0, alpha_mid=0.5, alpha_end=0.0)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        alpha_t0 = e.particles[0].alpha
        # Advance to half lifetime
        e.update(1.0)
        alpha_t1 = e.particles[0].alpha
        self.assertLessEqual(alpha_t1, alpha_t0)

    def test_color_interpolates(self):
        cfg = _make_config(birth_rate=0, life_exp=2.0,
                            color_start=(1,0,0), color_mid=(0,1,0), color_end=(0,0,1))
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        # At t=0, color should be near (1,0,0)
        self.assertAlmostEqual(e.particles[0].color[0], 1.0, places=3)

    def test_size_shrinks_to_zero(self):
        cfg = _make_config(birth_rate=0, life_exp=1.0,
                            size_start=1.0, size_mid=0.5, size_end=0.0)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        # Advance to 99% of lifetime
        e.update(0.99)
        if e.particles:
            self.assertLess(e.particles[0].size, 0.5)

    def test_flipbook_frame_advances(self):
        cfg = _make_config(birth_rate=0, life_exp=10.0, fps=4.0, grid_x=4, grid_y=4)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        e.update(0.0)
        frame0 = e.particles[0].frame
        e.update(0.5)  # 0.5s × 4fps = 2 frames
        if e.particles:
            frame1 = e.particles[0].frame
            self.assertGreaterEqual(frame1, frame0)

    def test_no_flipbook_when_fps_zero(self):
        cfg = _make_config(birth_rate=0, life_exp=10.0, fps=0.0)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        e.update(1.0)
        if e.particles:
            self.assertEqual(e.particles[0].frame, 0)


# ─────────────────────────────────────────────────────────────────────────────
#  ParticleDrawEntry Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleDrawEntry(unittest.TestCase):

    def test_draw_list_not_empty(self):
        e = ParticleEmitter(_make_config(birth_rate=0, life_exp=100), seed=0)
        e.burst(3)
        entries = e.build_draw_list()
        self.assertEqual(len(entries), 3)

    def test_draw_entry_has_color(self):
        e = ParticleEmitter(_make_config(birth_rate=0, life_exp=100), seed=0)
        e.burst(1)
        entry = e.build_draw_list()[0]
        self.assertEqual(len(entry.color), 4)

    def test_draw_entry_position_from_particle(self):
        cfg = _make_config(birth_rate=0, life_exp=100, world_pos=(5.0, 3.0, 1.0))
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        entry = e.build_draw_list()[0]
        self.assertAlmostEqual(entry.cx, 5.0)
        self.assertAlmostEqual(entry.cy, 3.0)

    def test_draw_list_sorted_back_to_front(self):
        """Entries should be sorted by -cz (descending Z)."""
        e = ParticleEmitter(_make_config(birth_rate=0, life_exp=100), seed=0)
        e.burst(5)
        # Manually set different Z values
        for i, p in enumerate(e.particles):
            p.pos = (0, 0, float(i))
        entries = e.build_draw_list()
        z_vals = [en.cz for en in entries]
        self.assertEqual(z_vals, sorted(z_vals, reverse=True))

    def test_draw_entry_radius_from_size(self):
        cfg = _make_config(birth_rate=0, life_exp=100, size_start=0.4)
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        entry = e.build_draw_list()[0]
        self.assertAlmostEqual(entry.r, 0.2, places=2)  # half of size

    def test_empty_draw_list_when_no_particles(self):
        e = ParticleEmitter(_make_config(birth_rate=0))
        entries = e.build_draw_list()
        self.assertEqual(len(entries), 0)


# ─────────────────────────────────────────────────────────────────────────────
#  LightningEmitter Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLightningEmitter(unittest.TestCase):

    def _make_lightning(self, branches=2):
        cfg = _make_config(birth_rate=0, life_exp=0.05, world_pos=(0,0,0))
        return LightningEmitter(cfg, end_pos=(0,5,0), branch_count=branches, seed=7)

    def test_bolt_generated_after_lifetime(self):
        le = self._make_lightning()
        le.update(0.1)  # > life_exp → regenerate
        self.assertGreater(len(le.bolt_points), 0)

    def test_bolt_starts_at_world_pos(self):
        le = self._make_lightning()
        le.update(0.1)
        if le.bolt_points:
            first = le.bolt_points[0]
            self.assertAlmostEqual(first[0], 0.0, places=3)

    def test_draw_list_non_empty_after_update(self):
        le = self._make_lightning()
        le.update(0.1)
        entries = le.build_draw_list()
        self.assertGreater(len(entries), 0)

    def test_bolt_points_have_3_coords(self):
        le = self._make_lightning()
        le.update(0.1)
        for pt in le.bolt_points:
            self.assertEqual(len(pt), 3)

    def test_more_branches_more_points(self):
        le1 = self._make_lightning(branches=1)
        le3 = self._make_lightning(branches=3)
        le1.update(0.1); le3.update(0.1)
        self.assertGreaterEqual(len(le3.bolt_points), len(le1.bolt_points))

    def test_update_mode_lightning(self):
        cfg = _make_config(update_mode=UPDATE_LIGHTNING)
        emitter = make_emitter_from_node(_make_node_with_emitter_params(update='Lightning'))
        self.assertIsInstance(emitter, LightningEmitter)


# ─────────────────────────────────────────────────────────────────────────────
#  EmitterManager Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEmitterManager(unittest.TestCase):

    def test_add_emitter(self):
        m = EmitterManager()
        e = ParticleEmitter(_make_config())
        m.add_emitter("sparks", e)
        self.assertEqual(m.emitter_count, 1)

    def test_remove_emitter(self):
        m = EmitterManager()
        e = ParticleEmitter(_make_config())
        m.add_emitter("sparks", e)
        m.remove_emitter("sparks")
        self.assertEqual(m.emitter_count, 0)

    def test_remove_nonexistent_returns_false(self):
        m = EmitterManager()
        self.assertFalse(m.remove_emitter("none"))

    def test_update_all(self):
        m = EmitterManager()
        e = ParticleEmitter(_make_config(birth_rate=100, life_exp=10), seed=0)
        m.add_emitter("e1", e)
        m.update(0.5)
        self.assertGreater(m.total_particles, 0)

    def test_draw_list_aggregates(self):
        m = EmitterManager()
        e1 = ParticleEmitter(_make_config(birth_rate=0, life_exp=100))
        e2 = ParticleEmitter(_make_config(birth_rate=0, life_exp=100))
        e1.burst(3)
        e2.burst(4)
        m.add_emitter("a", e1)
        m.add_emitter("b", e2)
        entries = m.build_draw_list()
        self.assertEqual(len(entries), 7)

    def test_reset_all(self):
        m = EmitterManager()
        e = ParticleEmitter(_make_config(birth_rate=100, life_exp=10), seed=0)
        m.add_emitter("e", e)
        m.update(1.0)
        m.reset_all()
        self.assertEqual(m.total_particles, 0)

    def test_emitter_names(self):
        m = EmitterManager()
        m.add_emitter("fire", ParticleEmitter(_make_config()))
        m.add_emitter("smoke", ParticleEmitter(_make_config()))
        names = m.emitter_names()
        self.assertIn("fire", names)
        self.assertIn("smoke", names)

    def test_get_emitter(self):
        m = EmitterManager()
        e = ParticleEmitter(_make_config())
        m.add_emitter("fx", e)
        self.assertIs(m.get_emitter("fx"), e)

    def test_get_nonexistent_returns_none(self):
        m = EmitterManager()
        self.assertIsNone(m.get_emitter("missing"))

    def test_total_particles_sum(self):
        m = EmitterManager()
        e1 = ParticleEmitter(_make_config(birth_rate=0, life_exp=100))
        e2 = ParticleEmitter(_make_config(birth_rate=0, life_exp=100))
        e1.burst(3); e2.burst(5)
        m.add_emitter("a", e1); m.add_emitter("b", e2)
        self.assertEqual(m.total_particles, 8)


# ─────────────────────────────────────────────────────────────────────────────
#  Factory Function Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFactoryFunctions(unittest.TestCase):

    def test_make_emitter_from_node_default(self):
        node = _make_node_with_emitter_params()
        e = make_emitter_from_node(node)
        self.assertIsInstance(e, ParticleEmitter)

    def test_make_emitter_from_node_lightning(self):
        node = _make_node_with_emitter_params(update='Lightning')
        e = make_emitter_from_node(node)
        self.assertIsInstance(e, LightningEmitter)

    def test_build_manager_from_empty_model(self):
        from core.model_data import KotorModel, ModelNode
        model = KotorModel(name='test')
        model.root_node = ModelNode(name='root')
        m = build_emitter_manager_from_model(model)
        self.assertEqual(m.emitter_count, 0)

    def test_build_manager_from_model_with_emitter(self):
        from core.model_data import KotorModel, ModelNode
        model = KotorModel(name='fx')
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        emit_node = ModelNode(name='emitter', flags=int(NodeFlags.EMITTER))
        emit_node.emitter_params = {'birthrate': 20.0, 'lifeexp': 1.0}
        root.children.append(emit_node)
        model.root_node = root
        m = build_emitter_manager_from_model(model)
        self.assertEqual(m.emitter_count, 1)

    def test_manager_has_correct_emitter_name(self):
        from core.model_data import KotorModel, ModelNode
        model = KotorModel(name='test')
        root = ModelNode(name='root', flags=int(NodeFlags.HEADER))
        en = ModelNode(name='sparkfx', flags=int(NodeFlags.EMITTER))
        en.emitter_params = {}
        root.children.append(en)
        model.root_node = root
        m = build_emitter_manager_from_model(model)
        self.assertIn('sparkfx', m.emitter_names())


# ─────────────────────────────────────────────────────────────────────────────
#  Edge Cases & Stress Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParticleEmitterEdgeCases(unittest.TestCase):

    def test_very_large_dt(self):
        """Extremely large dt should not crash."""
        e = ParticleEmitter(_make_config(birth_rate=10, life_exp=1.0), seed=0)
        e.update(9999.0)  # Should not raise

    def test_many_particles_update(self):
        """Performance: 1000 particles updated 10 frames should not hang."""
        e = ParticleEmitter(_make_config(birth_rate=0, life_exp=100, max_particles=1000))
        e.burst(1000)
        for _ in range(10):
            e.update(0.016)
        self.assertGreater(e.particle_count, 0)

    def test_rotating_billboard_sets_rot(self):
        cfg = _make_config(birth_rate=0, life_exp=100,
                            render_mode=RENDER_BILLBOARD_WORLD_Z_ROTATE)
        e = ParticleEmitter(cfg, seed=42)
        e.burst(5)
        rots = [p.rot for p in e.particles]
        # At least some should have non-zero rotation
        self.assertTrue(any(r != 0.0 for r in rots))

    def test_burst_zero(self):
        e = ParticleEmitter(_make_config(birth_rate=0))
        e.burst(0)
        self.assertEqual(e.particle_count, 0)

    def test_world_pos_origin(self):
        cfg = _make_config(birth_rate=0, life_exp=100, world_pos=(10, 20, 30))
        e = ParticleEmitter(cfg, seed=0)
        e.burst(1)
        p = e.particles[0]
        # Position should start at world_pos
        self.assertAlmostEqual(p.pos[0], 10.0)
        self.assertAlmostEqual(p.pos[1], 20.0)
        self.assertAlmostEqual(p.pos[2], 30.0)


if __name__ == '__main__':
    unittest.main()
