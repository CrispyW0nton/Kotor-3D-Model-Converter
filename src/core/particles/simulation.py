"""Pooled CPU particle simulation for KOTOR emitter nodes.

Architecture follows the classic OpenGL particle-system update/render split
(pooled particle storage, fractional-emission surplus accumulator, lifetime
decrement, over-lifetime interpolation, billboard batch output) as used by the
reference implementations this port draws from:

- jpaolasini/3D-OpenGL-Particle-System
- mehmetfatiherdem/Particle-System-Simulator (pool + ``emissionRate * dt +
  surplus`` accumulator, ColorOverLifetime/SizeOverLifetime components)
- konivo/particle_system (buffer-object batch rendering)
- sotoea/3D-Particle-System

Simulation state lives in numpy arrays; positions are kept in emitter-local
space and transformed by the emitter's current world transform when the render
batch is built, so particles follow animated emitter nodes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .emitter_data import (
    ChannelRows,
    CHANNEL_DEFAULTS,
    EmitterDefinition,
    EmitterFlags,
    animation_channels_for_node,
    sample_channel,
)

_MAX_PARTICLES = 4096
_TWO_PI = 2.0 * math.pi


@dataclass
class EffectiveEmitterParams:
    """Emitter parameters at one instant (bind pose merged with animation)."""

    birthrate: float = 0.0
    random_birthrate: float = 0.0
    lifeexp: float = 1.0
    velocity: float = 0.0
    randvel: float = 0.0
    spread: float = 0.0
    grav: float = 0.0
    drag: float = 0.0
    mass: float = 0.0
    particlerot: float = 0.0
    xsize: float = 0.0
    ysize: float = 0.0
    fps: float = 0.0
    framestart: float = 0.0
    frameend: float = 0.0
    blurlength: float = 0.0
    threshold: float = 0.0
    detonate: float = 0.0
    alphastart: float = 1.0
    alphamid: float = 0.5
    alphaend: float = 0.0
    sizestart: float = 1.0
    sizemid: float = 1.0
    sizeend: float = 1.0
    sizestart_y: float = 0.0
    sizemid_y: float = 0.0
    sizeend_y: float = 0.0
    percentstart: float = 0.0
    percentmid: float = 0.5
    percentend: float = 1.0
    colorstart: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    colormid: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    colorend: Tuple[float, float, float] = (1.0, 1.0, 1.0)


_SCALAR_PARAM_CHANNELS = (
    "birthrate", "lifeexp", "velocity", "randvel", "spread", "grav", "drag",
    "mass", "particlerot", "xsize", "ysize", "fps", "framestart", "frameend",
    "blurlength", "threshold", "detonate", "alphastart", "alphamid",
    "alphaend", "sizestart", "sizemid", "sizeend", "sizestart_y", "sizemid_y",
    "sizeend_y", "percentstart", "percentmid", "percentend",
)
_PARAM_FIELD_BY_CHANNEL = {name: name for name in _SCALAR_PARAM_CHANNELS}
_PARAM_FIELD_BY_CHANNEL["randombirthrate"] = "random_birthrate"


def effective_params(definition: EmitterDefinition,
                     anim_channels: Optional[Dict[str, ChannelRows]] = None,
                     anim_time: float = 0.0) -> EffectiveEmitterParams:
    """Merge bind-pose channels with active-animation channel overrides.

    Animation emitter controllers replace the bind-pose value for the channels
    they key (matching how the retail engine drives ``birthrate``/alpha to
    switch effects like the Star Map on and off).
    """
    params = EffectiveEmitterParams()
    anim_channels = anim_channels or {}

    for channel, field_name in _PARAM_FIELD_BY_CHANNEL.items():
        rows = anim_channels.get(channel)
        if rows:
            value = float(sample_channel(rows, anim_time, CHANNEL_DEFAULTS.get(channel, (0.0,)))[0])
        elif channel in definition.channels:
            value = definition.value(channel)
        else:
            continue
        setattr(params, field_name, value)

    for channel in ("colorstart", "colormid", "colorend"):
        rows = anim_channels.get(channel)
        if rows:
            sampled = sample_channel(rows, anim_time, CHANNEL_DEFAULTS[channel])
            if len(sampled) >= 3:
                setattr(params, channel, (float(sampled[0]), float(sampled[1]), float(sampled[2])))
        elif channel in definition.channels:
            setattr(params, channel, definition.color(channel))
    return params


def _spread_radians(spread: float) -> float:
    """Normalize a spread channel value to radians.

    Retail data stores spread inconsistently: ``Sun_gas`` uses 360 (degrees)
    while ``Projectorflare`` uses 6.283 (radians). Values above 2*pi are
    treated as degrees.
    """
    value = abs(float(spread))
    if value > _TWO_PI + 1e-3:
        value = math.radians(value)
    return min(value, _TWO_PI)


def _quat_rotate_many(quat: Tuple[float, float, float, float], vecs: np.ndarray) -> np.ndarray:
    """Rotate an (N, 3) array by an XYZW quaternion."""
    x, y, z, w = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
    q = np.array([x, y, z], dtype=np.float64)
    uv = np.cross(q, vecs)
    uuv = np.cross(q, uv)
    return vecs + 2.0 * (w * uv + uuv)


def _quat_conjugate(quat: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return (-float(quat[0]), -float(quat[1]), -float(quat[2]), float(quat[3]))


def _life_interp(u: np.ndarray, start: float, mid: float, end: float,
                 percent_mid: float = 0.5) -> np.ndarray:
    """start→mid→end interpolation over normalized age ``u`` in [0, 1].

    The Odyssey engine interpolates start→mid over the first half of a
    particle's life and mid→end over the second half (KotOR.js
    ShaderOdysseyEmitter ``getFloatOverLifetime``); the authored
    percentstart/mid/end channels do not shift the midpoint.
    """
    first = u < 0.5
    out = np.empty_like(u)
    out[first] = start + (mid - start) * (u[first] * 2.0)
    out[~first] = mid + (end - mid) * ((u[~first] - 0.5) * 2.0)
    return out


def _life_interp_color(u: np.ndarray, start: Tuple[float, float, float],
                       mid: Tuple[float, float, float], end: Tuple[float, float, float],
                       percent_mid: float) -> np.ndarray:
    channels = [
        _life_interp(u, start[k], mid[k], end[k], percent_mid) for k in range(3)
    ]
    return np.stack(channels, axis=1)


@dataclass
class ParticleBatch:
    """Renderer-neutral billboard batch for one emitter."""

    node_name: str
    texture: str
    blend: str
    render_mode: str
    two_sided: bool
    grid_x: int
    grid_y: int
    frame_blending: bool
    depth_key: float
    blur_length: float
    emitter_quat: Tuple[float, float, float, float]
    positions: np.ndarray        # (N, 3) world-space particle centers
    velocities: np.ndarray       # (N, 3) world-space velocities (motion blur)
    sizes: np.ndarray            # (N, 2) world-unit width/height
    colors: np.ndarray           # (N, 4) rgba in [0, 1]
    rotations: np.ndarray        # (N,) roll angle radians
    frames: np.ndarray           # (N,) int flipbook frame indices
    frame_frac: np.ndarray       # (N,) fractional progress to the next frame

    @property
    def count(self) -> int:
        return int(self.positions.shape[0])


class EmitterSimulation:
    """Live particle pool for a single emitter node."""

    def __init__(self, definition: EmitterDefinition, seed: int = 0,
                 spawn_frame_quat: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)):
        self.definition = definition
        self.rng = np.random.default_rng(seed or None)
        # For Normal/Motion_Blur ("points") render modes the engine spawns the
        # surface box rotated by the emitter NODE's own local rotation and the
        # particles are frozen in WORLD space where they were born (KotOR.js
        # parents OdysseyEmitter3D under its node; getRandomPosition applies
        # this.parent.quaternion — the node's local rotation — and adds the
        # world position).  ``spawn_frame_quat`` carries that local rotation.
        # Constrained render modes keep particles in emitter-local space.
        self.spawn_frame_quat = spawn_frame_quat
        render_mode = str(definition.render or "Normal").lower()
        update_mode = str(definition.update or "Fountain").lower()
        self.world_space = (
            render_mode in ("normal", "motion_blur", "")
            and update_mode != "single"
        )
        self._last_emitter_pos: Optional[Tuple[float, float, float]] = None
        self._capacity = 0
        self._surplus = 0.0
        self._detonated = False
        # world coordinates for points modes; emitter-local otherwise
        self.pos = np.zeros((0, 3), dtype=np.float64)
        self.vel = np.zeros((0, 3), dtype=np.float64)
        self.age = np.zeros((0,), dtype=np.float64)
        self.life = np.zeros((0,), dtype=np.float64)
        self.rot = np.zeros((0,), dtype=np.float64)
        self.alive = np.zeros((0,), dtype=bool)

    # ── Pool management ──────────────────────────────────────────────────────
    def _ensure_capacity(self, wanted: int) -> None:
        wanted = int(max(1, min(_MAX_PARTICLES, wanted)))
        if wanted <= self._capacity:
            return
        grow = wanted - self._capacity
        self.pos = np.vstack([self.pos, np.zeros((grow, 3))])
        self.vel = np.vstack([self.vel, np.zeros((grow, 3))])
        self.age = np.concatenate([self.age, np.zeros(grow)])
        self.life = np.concatenate([self.life, np.zeros(grow)])
        self.rot = np.concatenate([self.rot, np.zeros(grow)])
        self.alive = np.concatenate([self.alive, np.zeros(grow, dtype=bool)])
        self._capacity = wanted

    def reset(self) -> None:
        self.alive[:] = False
        self._surplus = 0.0
        self._detonated = False

    @property
    def alive_count(self) -> int:
        return int(np.count_nonzero(self.alive))

    # ── Spawning ─────────────────────────────────────────────────────────────
    def _spawn(self, count: int, params: EffectiveEmitterParams,
               emitter_pos: Tuple[float, float, float],
               emitter_quat: Tuple[float, float, float, float]) -> None:
        if count <= 0:
            return
        wanted = self.alive_count + count
        self._ensure_capacity(wanted)
        free = np.flatnonzero(~self.alive)[:count]
        if free.size == 0:
            return
        n = free.size
        rng = self.rng

        # Emitter surface dimensions are authored in centimeters (retail
        # ground truth: plc_starmap Stars_02 uses xsize=200/ysize=300 to fill
        # the ~3.5-unit dome; Galaxy uses 20x20 for a small center jitter).
        # Surface sampled as the ellipse inscribed in the authored (cm-scale)
        # rectangle: identical coverage from gameplay angles, but the corners
        # that poked visibly outside the Star Map dome from below are gone.
        half_x = max(0.0, float(params.xsize)) * 0.01 * 0.5
        half_y = max(0.0, float(params.ysize)) * 0.01 * 0.5
        if half_x > 0.0 or half_y > 0.0:
            radius = np.sqrt(rng.uniform(0.0, 1.0, n))
            theta = rng.uniform(0.0, _TWO_PI, n)
            px = half_x * radius * np.cos(theta)
            py = half_y * radius * np.sin(theta)
        else:
            px = np.zeros(n)
            py = np.zeros(n)
        offsets = np.stack([px, py, np.zeros(n)], axis=1)
        if self.world_space:
            # Parent-frame surface: undo the node's own local rotation, then
            # apply the full world orientation (P = Q * L^-1).
            sq = self.spawn_frame_quat
            if abs(sq[0]) > 1e-6 or abs(sq[1]) > 1e-6 or abs(sq[2]) > 1e-6:
                offsets = _quat_rotate_many(sq, offsets)
            offsets = _quat_rotate_many(emitter_quat, offsets)
            self.pos[free] = offsets + np.asarray(emitter_pos, dtype=np.float64)
        else:
            self.pos[free] = offsets

        # Direction: cone around emitter +Z with half-angle spread/2, rotated
        # into world by the full emitter orientation for points modes.
        spread = _spread_radians(params.spread)
        polar = (spread * 0.5) * np.sqrt(rng.uniform(0.0, 1.0, n))
        azimuth = rng.uniform(0.0, _TWO_PI, n)
        sin_p = np.sin(polar)
        directions = np.stack([
            sin_p * np.cos(azimuth),
            sin_p * np.sin(azimuth),
            np.cos(polar),
        ], axis=1)
        velocities = directions * float(params.velocity)
        if params.randvel:
            random_dirs = rng.normal(size=(n, 3))
            norms = np.linalg.norm(random_dirs, axis=1, keepdims=True)
            norms[norms < 1e-9] = 1.0
            velocities = velocities + (random_dirs / norms) * float(params.randvel)
        if self.world_space:
            velocities = _quat_rotate_many(emitter_quat, velocities)
        self.vel[free] = velocities

        life = max(0.0, float(params.lifeexp))
        self.age[free] = 0.0
        self.life[free] = life if life > 0 else float("inf")
        self.rot[free] = rng.uniform(0.0, _TWO_PI, n)
        self.alive[free] = True

    # ── Update ───────────────────────────────────────────────────────────────
    def update(self, dt: float, params: EffectiveEmitterParams,
               emitter_quat: Tuple[float, float, float, float],
               emitter_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        dt = float(max(0.0, dt))
        if dt <= 0.0:
            return
        definition = self.definition
        update_mode = str(definition.update or "Fountain").lower()

        if update_mode == "lightning":
            return

        if update_mode == "single":
            self._ensure_capacity(1)
            if not self.alive[0]:
                self._spawn(1, params, emitter_pos, emitter_quat)
                self.pos[0] = 0.0
                self.vel[0] = 0.0
            self.age[0] += dt
            life = max(1e-6, float(params.lifeexp))
            self.life[0] = life
            if definition.loop:
                self.age[0] = self.age[0] % life
            else:
                self.age[0] = min(self.age[0], life)
            # particlerot is radians/second (KotOR.js particle semantics;
            # plc_starmap galaxy=0.2 → slow visible spin, sunflares=±0.04).
            self.rot[self.alive] += float(params.particlerot) * dt
            return

        # Kill expired particles.
        expired = self.alive & (self.age >= self.life)
        self.alive[expired] = False

        # Inherit: points-mode particles follow emitter movement when the
        # INHERIT flag is set (KotOR.js adds the world-position delta).
        if self.world_space:
            if (self._last_emitter_pos is not None
                    and (int(self.definition.flags) & int(EmitterFlags.INHERIT))
                    and self.alive.any()):
                delta = np.asarray(emitter_pos, dtype=np.float64) - np.asarray(
                    self._last_emitter_pos, dtype=np.float64
                )
                if np.abs(delta).max() > 1e-9:
                    self.pos[self.alive] += delta
            self._last_emitter_pos = tuple(float(v) for v in emitter_pos)

        # Emission (fractional surplus accumulator, per the reference
        # Particle-System-Simulator emitter).
        if update_mode == "explosion":
            if not self._detonated and params.detonate >= 0.0:
                burst = int(round(max(1.0, params.birthrate)))
                self._spawn(burst, params, emitter_pos, emitter_quat)
                self._detonated = True
        else:
            rate = max(0.0, float(params.birthrate))
            if params.random_birthrate > 0.0:
                rate += float(self.rng.uniform(0.0, params.random_birthrate))
            result = rate * dt + self._surplus
            spawn_count = int(result)
            self._surplus = result - spawn_count
            room = _MAX_PARTICLES - self.alive_count
            self._spawn(min(spawn_count, room), params, emitter_pos, emitter_quat)

        live = self.alive
        if not live.any():
            return

        # Integrate: gravity pulls along world -Z.  Local-space pools convert
        # it into the emitter frame; world-space pools apply it directly.
        if params.grav:
            gravity_world = np.array([[0.0, 0.0, -float(params.grav)]])
            if self.world_space:
                self.vel[live] += gravity_world[0] * dt
            else:
                gravity_local = _quat_rotate_many(_quat_conjugate(emitter_quat), gravity_world)[0]
                self.vel[live] += gravity_local * dt
        if params.drag:
            self.vel[live] *= max(0.0, 1.0 - float(params.drag) * dt)
        self.pos[live] += self.vel[live] * dt
        self.age[live] += dt
        if params.particlerot:
            self.rot[live] += float(params.particlerot) * dt

    # ── Render batch ─────────────────────────────────────────────────────────
    def build_batch(self, params: EffectiveEmitterParams,
                    emitter_world_pos: Tuple[float, float, float],
                    emitter_quat: Tuple[float, float, float, float],
                    camera_eye: Tuple[float, float, float]) -> Optional[ParticleBatch]:
        live = np.flatnonzero(self.alive)
        if live.size == 0:
            return None
        life = self.life[live]
        life_safe = np.where(np.isfinite(life) & (life > 1e-9), life, 1.0)
        u = np.clip(self.age[live] / life_safe, 0.0, 1.0)

        alphas = np.clip(
            _life_interp(u, params.alphastart, params.alphamid, params.alphaend,
                         params.percentmid),
            0.0, 1.0,
        )
        visible = alphas > (1.0 / 255.0)
        if not visible.any():
            return None
        if not visible.all():
            live = live[visible]
            u = u[visible]
            alphas = alphas[visible]
        sizes_x = np.maximum(
            _life_interp(u, params.sizestart, params.sizemid, params.sizeend,
                         params.percentmid),
            0.0,
        )
        if params.sizestart_y > 0.0 or params.sizeend_y > 0.0 or params.sizemid_y > 0.0:
            sizes_y = np.maximum(
                _life_interp(u, params.sizestart_y, params.sizemid_y, params.sizeend_y,
                             params.percentmid),
                0.0,
            )
        else:
            sizes_y = sizes_x
        colors = np.clip(
            _life_interp_color(u, params.colorstart, params.colormid, params.colorend,
                               params.percentmid),
            0.0, 4.0,
        )
        rgba = np.concatenate([colors, alphas[:, None]], axis=1).astype(np.float32)

        if self.world_space:
            world_pos = self.pos[live]
            world_vel = self.vel[live]
        else:
            world_pos = _quat_rotate_many(emitter_quat, self.pos[live]) + np.asarray(
                emitter_world_pos, dtype=np.float64
            )
            world_vel = _quat_rotate_many(emitter_quat, self.vel[live])

        fps = max(0.0, float(params.fps))
        frame_start = float(params.framestart)
        frame_end = max(frame_start, float(params.frameend))
        total_cells = max(1, int(self.definition.grid_x) * int(self.definition.grid_y))
        span = frame_end - frame_start + 1.0 if frame_end > frame_start else float(total_cells)
        if fps > 0.0:
            frames_f = frame_start + (self.age[live] * fps) % span
        elif span > 1.0:
            # Without an FPS the flipbook advances with lifetime progress
            # (KotOR.js: frameNumber = positionInTime * totalFrames), e.g. the
            # Star Map's 2x2 star sprites cycle over each star's life.
            frames_f = frame_start + (u * span) % span
        else:
            frames_f = np.full(live.size, frame_start)
        frames = np.clip(np.floor(frames_f), 0, total_cells - 1).astype(np.int32)
        frame_frac = (frames_f - np.floor(frames_f)).astype(np.float32)

        eye = np.asarray(camera_eye, dtype=np.float64)
        emitter_np = np.asarray(emitter_world_pos, dtype=np.float64)
        depth_key = float(np.dot(emitter_np - eye, emitter_np - eye))

        return ParticleBatch(
            node_name=self.definition.name,
            texture=str(self.definition.texture or "").strip().lower(),
            blend=str(self.definition.blend or "Normal"),
            render_mode=str(self.definition.render or "Normal"),
            two_sided=bool(self.definition.two_sided_texture),
            grid_x=max(1, int(self.definition.grid_x)),
            grid_y=max(1, int(self.definition.grid_y)),
            frame_blending=bool(self.definition.frame_blending),
            depth_key=depth_key,
            blur_length=float(params.blurlength),
            emitter_quat=(
                float(emitter_quat[0]), float(emitter_quat[1]),
                float(emitter_quat[2]), float(emitter_quat[3]),
            ),
            positions=world_pos.astype(np.float32),
            velocities=world_vel.astype(np.float32),
            sizes=np.stack([sizes_x, sizes_y], axis=1).astype(np.float32),
            colors=rgba,
            rotations=self.rot[live].astype(np.float32),
            frames=frames,
            frame_frac=frame_frac,
        )


# Callable that maps a node to its (world_position, world_quaternion_xyzw).
WorldTransformFn = Callable[[Any], Tuple[Tuple[float, float, float], Tuple[float, float, float, float]]]


@dataclass
class _EmitterEntry:
    node: Any
    simulation: EmitterSimulation
    bind_params: Optional[EffectiveEmitterParams] = None
    anim_channels_key: int = 0
    anim_channels: Optional[Dict[str, ChannelRows]] = None


class ModelParticleSystems:
    """All emitter simulations for one loaded model."""

    def __init__(self, model: Any):
        self.model = model
        self._entries: Dict[int, _EmitterEntry] = {}
        self._effective: Dict[int, EffectiveEmitterParams] = {}
        self.enabled = True
        self._discover()

    @staticmethod
    def _spawn_frame_quat_for(node: Any, definition: EmitterDefinition):
        """Points-mode spawn surfaces ignore the emitter node's own rotation.

        The retail Star Map star fields are horizontal sheets hugging the
        galaxy plane; orienting the spawn box by the node's own (or full
        world) rotation turns them into vertical curtains seen edge-on.  The
        surface therefore spawns in the PARENT frame: the pool stores world
        positions, so the box is pre-rotated by the inverse of the node's own
        local rotation before the full world orientation is applied.
        """
        render_mode = str(definition.render or "").lower()
        if render_mode not in ("normal", "motion_blur", ""):
            return (0.0, 0.0, 0.0, 1.0)
        rot = tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)))
        mag = math.sqrt(sum(float(v) * float(v) for v in rot[:4]))
        if mag <= 1e-9:
            return (0.0, 0.0, 0.0, 1.0)
        return (-rot[0] / mag, -rot[1] / mag, -rot[2] / mag, rot[3] / mag)

    def _discover(self) -> None:
        from .emitter_data import emitter_nodes

        for index, node in enumerate(emitter_nodes(self.model)):
            key = id(node)
            if key not in self._entries:
                definition = EmitterDefinition.from_node(node)
                self._entries[key] = _EmitterEntry(
                    node=node,
                    simulation=EmitterSimulation(
                        definition,
                        seed=index + 1,
                        spawn_frame_quat=self._spawn_frame_quat_for(node, definition),
                    ),
                )

    @property
    def has_emitters(self) -> bool:
        return bool(self._entries)

    @property
    def active(self) -> bool:
        """True while any emitter can visibly produce or hold particles."""
        if not self.enabled:
            return False
        return bool(self._entries)

    def invalidate_node(self, node: Any) -> None:
        """Re-read a node's definition after editing and restart its pool."""
        entry = self._entries.get(id(node))
        if entry is None:
            self._discover()
            entry = self._entries.get(id(node))
            if entry is None:
                return
        definition = EmitterDefinition.from_node(node)
        entry.simulation = EmitterSimulation(
            definition,
            spawn_frame_quat=self._spawn_frame_quat_for(node, definition),
        )
        entry.bind_params = None
        entry.anim_channels_key = 0
        entry.anim_channels = None
        self._effective.pop(id(node), None)

    def invalidate_all(self) -> None:
        self._entries.clear()
        self._effective.clear()
        self._discover()

    def _params_for(self, key: int, entry: _EmitterEntry, animation: Any,
                    anim_time: float) -> EffectiveEmitterParams:
        anim_key = id(animation) if animation is not None else 0
        if entry.anim_channels_key != anim_key:
            entry.anim_channels_key = anim_key
            entry.anim_channels = (
                animation_channels_for_node(animation, getattr(entry.node, "name", ""))
                if animation is not None else None
            )
        if entry.anim_channels:
            params = effective_params(entry.simulation.definition, entry.anim_channels, anim_time)
        else:
            if entry.bind_params is None:
                entry.bind_params = effective_params(entry.simulation.definition)
            params = entry.bind_params
        self._effective[key] = params
        return params

    def update(self, dt: float, world_transform_fn: WorldTransformFn,
               animation: Any = None, anim_time: float = 0.0) -> None:
        if not self.enabled:
            return
        for key, entry in list(self._entries.items()):
            node = entry.node
            if bool(getattr(node, "_gr_hidden", False)):
                continue
            params = self._params_for(key, entry, animation, anim_time)
            try:
                pos, quat = world_transform_fn(node)
            except Exception:
                pos, quat = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
            entry.simulation.update(dt, params, quat, pos)

    def batches(self, world_transform_fn: WorldTransformFn,
                camera_eye: Tuple[float, float, float]) -> List[ParticleBatch]:
        if not self.enabled:
            return []
        results: List[ParticleBatch] = []
        for key, entry in self._entries.items():
            node = entry.node
            if bool(getattr(node, "_gr_hidden", False)):
                continue
            params = self._effective.get(key)
            if params is None:
                params = effective_params(entry.simulation.definition)
            try:
                pos, quat = world_transform_fn(node)
            except Exception:
                pos, quat = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
            batch = entry.simulation.build_batch(params, pos, quat, camera_eye)
            if batch is not None and batch.count > 0:
                results.append(batch)
        # Painter's order: farthest emitter first, then explicit render order.
        results.sort(key=lambda b: -b.depth_key)
        return results
