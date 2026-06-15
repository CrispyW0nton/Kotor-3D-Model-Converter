"""
particle_emitter.py — GhostRigger-K1-K2  Phase 6.1
====================================================
CPU particle simulation for KotOR emitter nodes.

Implements the ``ParticleEmitter`` CPU simulator that advances particles each
frame and produces a draw list for the viewport.

References:
  KotOR.js OdysseyEmitter3D.ts (1,276 lines, GPL 3.0)
  xoreos model_kotor.cpp — emitter struct
  PyKotor/mdl_data.py MDLEmitter (224 bytes)
  Roadmap Phase 6.1

Emitter update modes (from KotOR.js OdysseyEmitter3D.ts):
  Billboard_to_World_Z  — particles face the camera (billboard, world Z up)
  Billboard_to_Local_Z  — particles face camera in local space
  Linked                — particle chain / lightning
  Lightning             — branched lightning bolt
  P2P                   — point-to-point bezier path

Render modes:
  Normal                — simple billboard quad
  Linked                — linked quads forming a ribbon
  Billboard_to_World_Z_Rotate — rotating billboard
  Motion_Blur           — stretched in velocity direction
  AlignedToParticleDir  — oriented along velocity

Blend modes:
  Normal         — alpha blend
  Punch-Through  — binary alpha
  Lighten        — additive

Controller IDs (from animation_engine.py):
  BirthRate=160, LifeExp=186, Velocity=216, Mass=188,
  SizeStart=198, SizeEnd=200, SizeMid=202,
  ColorStart=76, ColorEnd=84, ColorMid=80,
  AlphaStart=78, AlphaEnd=86, AlphaMid=82,
  SpreadH=204, SpreadV=206, RandVelocity=196,
  ParticleRot=160, Drag=180, FPS=182.
"""

from __future__ import annotations

import math
import logging
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

# Controller IDs (matches animation_engine.py)
CTRL_BIRTHRATE     = 160
CTRL_LIFEEXP       = 186
CTRL_VELOCITY      = 216
CTRL_MASS          = 188
CTRL_SIZE_START    = 198
CTRL_SIZE_END      = 200
CTRL_SIZE_MID      = 202
CTRL_COLOR_START   = 76
CTRL_COLOR_END     = 84
CTRL_COLOR_MID     = 80
CTRL_ALPHA_START   = 78
CTRL_ALPHA_END     = 86
CTRL_ALPHA_MID     = 82
CTRL_SPREAD_H      = 204
CTRL_SPREAD_V      = 206
CTRL_RAND_VELOCITY = 196
CTRL_DRAG          = 180
CTRL_FPS           = 182
CTRL_FRAME_BLEND   = 184
CTRL_BLUR_LENGTH   = 222

# Update modes
UPDATE_BILLBOARD_WORLD_Z = 'Billboard_to_World_Z'
UPDATE_BILLBOARD_LOCAL_Z = 'Billboard_to_Local_Z'
UPDATE_LINKED            = 'Linked'
UPDATE_LIGHTNING         = 'Lightning'
UPDATE_P2P               = 'P2P'

# Render modes
RENDER_NORMAL                   = 'Normal'
RENDER_LINKED                   = 'Linked'
RENDER_BILLBOARD_WORLD_Z_ROTATE = 'Billboard_to_World_Z_Rotate'
RENDER_MOTION_BLUR              = 'Motion_Blur'
RENDER_ALIGNED                  = 'AlignedToParticleDir'

# Blend modes
BLEND_NORMAL      = 'Normal'
BLEND_PUNCHTHROUGH = 'Punch-Through'
BLEND_LIGHTEN     = 'Lighten'

# Maximum particles per emitter to prevent performance issues
MAX_PARTICLES_DEFAULT = 256

# ─────────────────────────────────────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EmitterParticle:
    """
    A single active particle in a KotOR emitter simulation.

    All vectors are 3-tuples (x, y, z) in world space.
    Colors are (r, g, b) floats in [0, 1].

    References:
        KotOR.js OdysseyEmitter3D.ts — OdysseyParticle structure
        xoreos — ModelNode particle layout
    """
    pos:   Tuple[float, float, float] = (0.0, 0.0, 0.0)
    vel:   Tuple[float, float, float] = (0.0, 0.0, 0.0)
    age:   float = 0.0          # seconds since spawn
    life:  float = 1.0          # max lifetime (seconds)
    size:  float = 0.1          # current rendered size
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    alpha: float = 1.0          # current alpha
    rot:   float = 0.0          # rotation in degrees (for billboard spin)
    frame: int   = 0            # current flipbook frame index

    @property
    def alive(self) -> bool:
        """True if the particle is still within its lifetime."""
        return self.age < self.life

    @property
    def normalized_age(self) -> float:
        """Particle age as fraction of lifetime [0, 1]."""
        if self.life <= 0.0:
            return 1.0
        return min(self.age / self.life, 1.0)


@dataclass
class ParticleDrawEntry:
    """
    A single particle ready for rendering by the viewport.

    All coordinates in world space.  The renderer uses this to draw a
    billboard quad (or motion-blur streak) at (cx, cy, cz) with given
    half-size ``r`` and RGBA color.
    """
    cx:    float = 0.0          # world X
    cy:    float = 0.0          # world Y
    cz:    float = 0.0          # world Z
    r:     float = 0.1          # half-size (billboard radius)
    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    rot:   float = 0.0          # rotation (degrees) for spinning billboards
    frame: int   = 0            # flipbook frame index
    # Velocity for motion-blur rendering
    vx:   float = 0.0
    vy:   float = 0.0
    vz:   float = 0.0


@dataclass
class EmitterConfig:
    """
    Resolved emitter configuration extracted from a ModelNode emitter_params dict.

    All float values are resolved at config-creation time from the emitter's
    controller array (Phase 6.1 uses constant defaults; animated values come
    from the AnimationEngine controller pipeline in a later phase).

    Ref: xoreos model_kotor.cpp:readEmitter() + MDLEmitter 224-byte struct.
    """
    # Spawn / lifetime
    birth_rate:   float = 10.0      # particles per second
    life_exp:     float = 2.0       # particle lifetime in seconds
    max_particles: int  = MAX_PARTICLES_DEFAULT

    # Motion
    velocity:     float = 1.0       # initial speed along spawn direction
    rand_velocity: float = 0.0      # random velocity jitter (m/s)
    spread_h:     float = 0.0       # horizontal spread (radians)
    spread_v:     float = 0.0       # vertical spread (radians)
    mass:         float = 1.0       # mass (affects gravity drag)
    drag:         float = 0.0       # drag coefficient (0 = no drag)

    # Size interpolation (start → mid → end, with normalized_age)
    size_start: float = 0.2
    size_mid:   float = 0.2
    size_end:   float = 0.0

    # Color interpolation
    color_start: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    color_mid:   Tuple[float, float, float] = (1.0, 1.0, 1.0)
    color_end:   Tuple[float, float, float] = (1.0, 1.0, 1.0)

    # Alpha interpolation
    alpha_start: float = 1.0
    alpha_mid:   float = 1.0
    alpha_end:   float = 0.0

    # Texture / flipbook
    texture:  str   = ""
    grid_x:   int   = 1
    grid_y:   int   = 1
    fps:      float = 0.0       # flipbook FPS (0 = static)

    # Rendering
    update_mode: str = UPDATE_BILLBOARD_WORLD_Z
    render_mode: str = RENDER_NORMAL
    blend_mode:  str = BLEND_NORMAL
    loop:        bool = True
    two_sided:   bool = False

    # World offset (emitter node position)
    world_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    @classmethod
    def from_node(cls, node) -> 'EmitterConfig':
        """
        Build an EmitterConfig from a ModelNode with emitter_params populated.

        Falls back to defaults for any missing parameter.
        """
        p = getattr(node, 'emitter_params', {}) or {}
        pos = getattr(node, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
        return cls(
            birth_rate    = float(p.get('birthrate',     10.0)),
            life_exp      = float(p.get('lifeexp',        2.0)),
            max_particles = int  (p.get('maxparticles',  MAX_PARTICLES_DEFAULT)),
            velocity      = float(p.get('velocity',       1.0)),
            rand_velocity = float(p.get('randvelocity',   0.0)),
            spread_h      = float(p.get('spreadh',        0.0)),
            spread_v      = float(p.get('spreadv',        0.0)),
            mass          = float(p.get('mass',            1.0)),
            drag          = float(p.get('drag',            0.0)),
            size_start    = float(p.get('sizestart',      0.2)),
            size_mid      = float(p.get('sizemid',        0.2)),
            size_end      = float(p.get('sizeend',        0.0)),
            color_start   = tuple(p.get('colorstart',    (1.0, 1.0, 1.0)))[:3],
            color_mid     = tuple(p.get('colormid',      (1.0, 1.0, 1.0)))[:3],
            color_end     = tuple(p.get('colorend',      (1.0, 1.0, 1.0)))[:3],
            alpha_start   = float(p.get('alphastart',    1.0)),
            alpha_mid     = float(p.get('alphamid',      1.0)),
            alpha_end     = float(p.get('alphaend',      0.0)),
            texture       = str  (p.get('texture',       '')),
            grid_x        = int  (p.get('gridx',          1)),
            grid_y        = int  (p.get('gridy',          1)),
            fps           = float(p.get('fps',            0.0)),
            update_mode   = str  (p.get('update',        UPDATE_BILLBOARD_WORLD_Z)),
            render_mode   = str  (p.get('render',        RENDER_NORMAL)),
            blend_mode    = str  (p.get('blend',         BLEND_NORMAL)),
            loop          = bool (p.get('loop',           True)),
            two_sided     = bool (p.get('twosided',       False)),
            world_pos     = tuple(float(c) for c in pos[:3]),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Interpolation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by t ∈ [0, 1]."""
    return a + (b - a) * t


def _lerp3(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
    t: float,
) -> Tuple[float, float, float]:
    return (_lerp(a[0], b[0], t), _lerp(a[1], b[1], t), _lerp(a[2], b[2], t))


def _interp3(
    start: Tuple[float, float, float],
    mid:   Tuple[float, float, float],
    end:   Tuple[float, float, float],
    t:     float,
) -> Tuple[float, float, float]:
    """3-key midpoint interpolation (start→mid at t=0.5, mid→end at t=1.0)."""
    if t <= 0.5:
        return _lerp3(start, mid, t * 2.0)
    else:
        return _lerp3(mid, end, (t - 0.5) * 2.0)


def _interp1(start: float, mid: float, end: float, t: float) -> float:
    """3-key midpoint interpolation for scalars."""
    if t <= 0.5:
        return _lerp(start, mid, t * 2.0)
    else:
        return _lerp(mid, end, (t - 0.5) * 2.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


# ─────────────────────────────────────────────────────────────────────────────
#  Core simulator
# ─────────────────────────────────────────────────────────────────────────────

class ParticleEmitter:
    """
    CPU particle simulator for a single KotOR emitter node.

    Lifecycle::

        emitter = ParticleEmitter(config)
        # Each frame:
        emitter.update(dt)
        draw_list = emitter.build_draw_list()

    The draw list can be consumed by the viewport software renderer to draw
    billboard quads or the GPU renderer to upload an instanced quad VBO.

    Simulation algorithm:
      1. Spawn: accumulate spawn_accumulator each frame; when ≥ 1 spawn a particle.
      2. Integrate: each particle's position advances by velocity × dt.
         Drag reduces velocity: vel *= exp(-drag × dt).
         (No gravity in base implementation; gravity = mass × (0,0,-9.8)
         can be added by subclasses if needed.)
      3. Update appearance: interpolate size, color, alpha from 3-key curves.
      4. Cull: remove particles with age ≥ life.

    The simulation is intentionally simple (no SPH, no collision) and is
    designed to reproduce the KotOR aurora engine's visual result at ~60 fps
    without a physics step.

    Reference:
        KotOR.js OdysseyEmitter3D.ts:update() / OdysseyParticle
    """

    def __init__(self, config: EmitterConfig, seed: Optional[int] = None) -> None:
        self.config = config
        self._rng   = random.Random(seed)
        self._particles: List[EmitterParticle] = []
        self._spawn_acc: float = 0.0          # fractional particle debt
        self._time:       float = 0.0          # total elapsed time

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """
        Advance the simulation by dt seconds.

        Spawns new particles, integrates existing ones, and culls dead ones.
        """
        if dt <= 0.0:
            return
        self._time += dt

        # 1 — Spawn new particles
        cfg = self.config
        if cfg.birth_rate > 0.0 and len(self._particles) < cfg.max_particles:
            self._spawn_acc += cfg.birth_rate * dt
            while self._spawn_acc >= 1.0 and len(self._particles) < cfg.max_particles:
                self._spawn_acc -= 1.0
                self._particles.append(self._spawn_particle())

        # 2 — Integrate + update appearance
        drag_factor = math.exp(-cfg.drag * dt) if cfg.drag > 0.0 else 1.0
        for p in self._particles:
            p.age += dt
            # Position integration
            p.pos = (
                p.pos[0] + p.vel[0] * dt,
                p.pos[1] + p.vel[1] * dt,
                p.pos[2] + p.vel[2] * dt,
            )
            # Drag (exponential decay of velocity)
            if drag_factor < 1.0:
                p.vel = (p.vel[0] * drag_factor,
                         p.vel[1] * drag_factor,
                         p.vel[2] * drag_factor)

        # 3 — Update appearance from keyframes
        for p in self._particles:
            t = p.normalized_age
            p.size  = _interp1(cfg.size_start, cfg.size_mid, cfg.size_end, t)
            p.color = _interp3(cfg.color_start, cfg.color_mid, cfg.color_end, t)
            p.alpha = _interp1(cfg.alpha_start, cfg.alpha_mid, cfg.alpha_end, t)
            # Flipbook frame
            if cfg.fps > 0.0:
                frames = max(cfg.grid_x * cfg.grid_y, 1)
                p.frame = int(p.age * cfg.fps) % frames

        # 4 — Cull dead particles
        self._particles = [p for p in self._particles if p.alive]

    def build_draw_list(self) -> List[ParticleDrawEntry]:
        """
        Return a list of ParticleDrawEntry objects for the current frame.

        Entries are sorted back-to-front by Z (descending) so that additive /
        alpha-blended particles composite correctly.  The viewport renderer
        is expected to draw them in order.
        """
        entries = []
        for p in self._particles:
            entries.append(ParticleDrawEntry(
                cx=p.pos[0], cy=p.pos[1], cz=p.pos[2],
                r=p.size * 0.5,
                color=(p.color[0], p.color[1], p.color[2], p.alpha),
                rot=p.rot,
                frame=p.frame,
                vx=p.vel[0], vy=p.vel[1], vz=p.vel[2],
            ))
        # Back-to-front sort on Z (simple; real renderer would use camera distance)
        entries.sort(key=lambda e: -e.cz)
        return entries

    def reset(self) -> None:
        """Clear all particles and reset spawn accumulator."""
        self._particles.clear()
        self._spawn_acc = 0.0
        self._time      = 0.0

    def burst(self, count: int) -> None:
        """
        Instantly spawn ``count`` particles (for burst emitters).

        Respects max_particles cap.
        """
        remaining = self.config.max_particles - len(self._particles)
        for _ in range(min(count, remaining)):
            self._particles.append(self._spawn_particle())

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def particle_count(self) -> int:
        """Current number of active particles."""
        return len(self._particles)

    @property
    def particles(self) -> List[EmitterParticle]:
        """Direct access to the particle list (read-only by convention)."""
        return self._particles

    @property
    def elapsed_time(self) -> float:
        """Total elapsed simulation time in seconds."""
        return self._time

    # ── Internal ──────────────────────────────────────────────────────────────

    def _spawn_particle(self) -> EmitterParticle:
        """
        Create a new particle at the emitter origin with random velocity.

        Velocity is sampled from a cone defined by spread_h / spread_v.
        A random jitter (rand_velocity) is added.

        Ref: KotOR.js OdysseyEmitter3D.ts:_spawnParticle()
        """
        cfg = self.config
        rng = self._rng

        # Base position = emitter world pos
        px, py, pz = cfg.world_pos

        # Velocity: forward = +Z, scattered by spread_h (azimuth) + spread_v (elevation)
        sh = cfg.spread_h
        sv = cfg.spread_v
        azimuth   = rng.uniform(-sh, sh) if sh > 0.0 else 0.0
        elevation = rng.uniform(-sv, sv) if sv > 0.0 else 0.0

        speed = cfg.velocity + rng.uniform(-cfg.rand_velocity, cfg.rand_velocity)
        speed = max(speed, 0.0)

        # Convert spherical offset to Cartesian (local Z-up)
        ca, sa = math.cos(azimuth), math.sin(azimuth)
        ce, se = math.cos(elevation), math.sin(elevation)
        vx = speed * sa * ce
        vy = speed * ca * ce
        vz = speed * se

        life = max(cfg.life_exp + rng.uniform(-0.1, 0.1) * cfg.life_exp, 0.01)

        return EmitterParticle(
            pos=(px, py, pz),
            vel=(vx, vy, vz),
            age=0.0,
            life=life,
            size=cfg.size_start,
            color=cfg.color_start,
            alpha=cfg.alpha_start,
            rot=rng.uniform(0.0, 360.0) if cfg.render_mode == RENDER_BILLBOARD_WORLD_Z_ROTATE else 0.0,
            frame=0,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Lightning emitter (Phase 6.2 stub)
# ─────────────────────────────────────────────────────────────────────────────

class LightningEmitter(ParticleEmitter):
    """
    Emitter for lightning-type effects (update_mode='Lightning').

    Phase 6.2 extension — for now, generates a simple branching line segment
    path between ``start_pos`` and ``end_pos`` using midpoint displacement.

    Each "particle" in this mode is a line segment endpoint rather than a
    billboard.  The draw list contains pairs of adjacent ParticleDrawEntry
    objects that the renderer should connect with a line primitive.
    """

    def __init__(
        self,
        config: EmitterConfig,
        end_pos: Tuple[float, float, float] = (0.0, 5.0, 0.0),
        branch_count: int = 3,
        seed: Optional[int] = None,
    ) -> None:
        super().__init__(config, seed=seed)
        self._end_pos = end_pos
        self._branch_count = branch_count
        self._bolt_points: List[Tuple[float, float, float]] = []
        self._bolt_age: float = 0.0
        self._bolt_lifetime: float = max(config.life_exp, 0.05)

    def update(self, dt: float) -> None:
        """Regenerate the lightning bolt at regular intervals."""
        self._bolt_age += dt
        if self._bolt_age >= self._bolt_lifetime:
            self._bolt_age = 0.0
            self._regenerate_bolt()

    def _regenerate_bolt(self) -> None:
        """Midpoint displacement to generate a jagged lightning path."""
        start = self.config.world_pos
        end   = self._end_pos
        points = [start, end]
        for _ in range(self._branch_count):
            new_points = [points[0]]
            for i in range(len(points) - 1):
                a, b = points[i], points[i + 1]
                mid = ((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2)
                disp = self._rng.uniform(-0.5, 0.5)
                mid  = (mid[0] + disp, mid[1] + disp, mid[2])
                new_points.append(mid)
                new_points.append(b)
            points = new_points
        self._bolt_points = points

    def build_draw_list(self) -> List[ParticleDrawEntry]:
        cfg = self.config
        entries = []
        for pt in self._bolt_points:
            entries.append(ParticleDrawEntry(
                cx=pt[0], cy=pt[1], cz=pt[2],
                r=cfg.size_start,
                color=(cfg.color_start[0], cfg.color_start[1], cfg.color_start[2],
                       cfg.alpha_start),
            ))
        return entries

    @property
    def bolt_points(self) -> List[Tuple[float, float, float]]:
        return list(self._bolt_points)


# ─────────────────────────────────────────────────────────────────────────────
#  Emitter Manager — owns multiple emitters for a scene
# ─────────────────────────────────────────────────────────────────────────────

class EmitterManager:
    """
    Manages all active ``ParticleEmitter`` instances for a loaded scene.

    Usage::

        manager = EmitterManager()
        manager.add_emitter("sparks", ParticleEmitter(config))
        # Each frame:
        manager.update(dt)
        all_entries = manager.build_draw_list()

    The manager deduplicates emitter names and provides bulk update /
    draw-list assembly for the viewport.
    """

    def __init__(self) -> None:
        self._emitters: Dict[str, ParticleEmitter] = {}

    def add_emitter(self, name: str, emitter: ParticleEmitter) -> None:
        self._emitters[name] = emitter

    def remove_emitter(self, name: str) -> bool:
        if name in self._emitters:
            del self._emitters[name]
            return True
        return False

    def update(self, dt: float) -> None:
        """Update all emitters by dt seconds."""
        for emitter in self._emitters.values():
            emitter.update(dt)

    def build_draw_list(self) -> List[ParticleDrawEntry]:
        """Collect draw entries from all emitters (merged, no sort)."""
        entries: List[ParticleDrawEntry] = []
        for emitter in self._emitters.values():
            entries.extend(emitter.build_draw_list())
        return entries

    def reset_all(self) -> None:
        for emitter in self._emitters.values():
            emitter.reset()

    @property
    def emitter_count(self) -> int:
        return len(self._emitters)

    @property
    def total_particles(self) -> int:
        return sum(e.particle_count for e in self._emitters.values())

    def get_emitter(self, name: str) -> Optional[ParticleEmitter]:
        return self._emitters.get(name)

    def emitter_names(self) -> List[str]:
        return list(self._emitters.keys())


# ─────────────────────────────────────────────────────────────────────────────
#  Factory helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_emitter_from_node(node, seed: Optional[int] = None) -> ParticleEmitter:
    """
    Create the appropriate ParticleEmitter subclass for a ModelNode emitter.

    Dispatches on emitter_params['update'] mode.  Falls back to the base
    ParticleEmitter for unknown modes.
    """
    cfg = EmitterConfig.from_node(node)
    if cfg.update_mode == UPDATE_LIGHTNING:
        return LightningEmitter(cfg, seed=seed)
    return ParticleEmitter(cfg, seed=seed)


def build_emitter_manager_from_model(model, seed: Optional[int] = None) -> EmitterManager:
    """
    Scan a KotorModel for emitter nodes and build an EmitterManager.

    Returns an EmitterManager with one ParticleEmitter per emitter node.
    """
    manager = EmitterManager()
    for node in model.all_nodes():
        if getattr(node, 'is_emitter', False):
            try:
                emitter = make_emitter_from_node(node, seed=seed)
                manager.add_emitter(node.name, emitter)
            except Exception as e:
                log.warning("Failed to create emitter for node '%s': %s", node.name, e)
    return manager
