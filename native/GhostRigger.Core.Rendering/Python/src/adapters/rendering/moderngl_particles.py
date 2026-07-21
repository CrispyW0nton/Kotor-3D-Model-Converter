"""ModernGL billboard pass for KOTOR emitter particle batches.

Package-local to ``GhostRigger.Core.Rendering`` (renderer backend
implementation; no root ``src`` twin, matching the other ModernGL adapter
modules).  Geometry is expanded CPU-side with numpy — per-frame particle
counts are small (hundreds), and building world-space quad corners on the CPU
lets one tiny shader cover every Odyssey emitter render mode.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional, Sequence, Tuple

_PARTICLE_DEBUG = bool(os.environ.get("GHOSTRIGGER_PARTICLE_DEBUG"))

import numpy as np

try:
    import moderngl
except Exception:  # pragma: no cover - renderer already guards availability
    moderngl = None

log = logging.getLogger(__name__)

_FLOATS_PER_VERTEX = 12  # xyz + uv + uv2 + frame blend + rgba
_VERTS_PER_PARTICLE = 6

_VERT_SHADER = """
#version 330
uniform mat4 u_mvp;
in vec3 in_pos;
in vec2 in_uv;
in vec2 in_uv2;
in float in_blend;
in vec4 in_color;
out vec2 v_uv;
out vec2 v_uv2;
out float v_blend;
out vec4 v_color;
void main() {
    v_uv = in_uv;
    v_uv2 = in_uv2;
    v_blend = in_blend;
    v_color = in_color;
    gl_Position = u_mvp * vec4(in_pos, 1.0);
}
"""

_FRAG_SHADER = """
#version 330
uniform sampler2D u_tex;
uniform int u_punch;
in vec2 v_uv;
in vec2 v_uv2;
in float v_blend;
in vec4 v_color;
out vec4 fragColor;
void main() {
    // Flipbook frame blending: cross-fade to the next frame cell when the
    // emitter's frameblending flag is set (v_blend stays 0 otherwise).
    vec4 t = mix(texture(u_tex, v_uv), texture(u_tex, v_uv2), v_blend);
    vec4 c = t * v_color;
    if (u_punch == 1 && c.a < 0.5) discard;
    fragColor = c;
}
"""


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms < 1e-9] = 1.0
    return vectors / norms


def _quat_rotate_vec(quat, vec) -> np.ndarray:
    x, y, z, w = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
    q = np.array([x, y, z], dtype=np.float64)
    v = np.asarray(vec, dtype=np.float64)
    uv = np.cross(q, v)
    uuv = np.cross(q, uv)
    return v + 2.0 * (w * uv + uuv)


class ModernGLParticlePass:
    """Owns the particle shader/VBO/VAO and draws ``ParticleBatch`` payloads."""

    def __init__(self) -> None:
        self._prog = None
        self._vbo = None
        self._vao = None
        self._capacity_bytes = 0

    def release(self) -> None:
        for resource in (self._vao, self._vbo, self._prog):
            if resource is not None:
                try:
                    resource.release()
                except Exception:
                    pass
        self._prog = None
        self._vbo = None
        self._vao = None
        self._capacity_bytes = 0

    def _ensure(self, ctx) -> bool:
        if moderngl is None:
            return False
        if self._prog is None:
            try:
                self._prog = ctx.program(vertex_shader=_VERT_SHADER,
                                         fragment_shader=_FRAG_SHADER)
            except Exception as exc:
                log.warning("Particle shader compile failed: %s", exc)
                self._prog = None
                return False
        return True

    def _ensure_buffer(self, ctx, needed_bytes: int) -> bool:
        if self._vbo is not None and needed_bytes <= self._capacity_bytes:
            return True
        capacity = 1 << max(12, int(needed_bytes - 1).bit_length())
        if self._vao is not None:
            try:
                self._vao.release()
            except Exception:
                pass
            self._vao = None
        if self._vbo is not None:
            try:
                self._vbo.release()
            except Exception:
                pass
        try:
            self._vbo = ctx.buffer(reserve=capacity, dynamic=True)
            self._vao = ctx.vertex_array(
                self._prog,
                [(self._vbo, "3f 2f 2f 1f 4f",
                  "in_pos", "in_uv", "in_uv2", "in_blend", "in_color")],
            )
        except Exception as exc:
            log.warning("Particle buffer allocation failed: %s", exc)
            self._vbo = None
            self._vao = None
            self._capacity_bytes = 0
            return False
        self._capacity_bytes = capacity
        return True

    # ── Geometry expansion ───────────────────────────────────────────────────
    @staticmethod
    def _batch_axes(batch, eye: np.ndarray, cam_right: np.ndarray,
                    cam_up: np.ndarray, emitter_quat) -> Tuple[np.ndarray, np.ndarray]:
        """Per-particle width/height axis vectors for the batch render mode."""
        n = batch.count
        mode = str(batch.render_mode or "Normal").lower()
        positions = batch.positions.astype(np.float64)

        # Mode semantics from KotOR.js ShaderOdysseyEmitter:
        # - Billboard_to_World_Z renders with an identity world rotation under
        #   the view matrix → a camera-facing billboard.
        # - Aligned_to_World_Z rotates that plane 90° to stand perpendicular
        #   to the ground → vertical quad, cylindrical facing around world Z.
        # - Billboard_to_Local_Z keeps the emitter's model rotation → the quad
        #   lies in the emitter's local XY plane (Star Map nav rings/galaxy).
        if mode == "billboard_to_local_z":
            a = np.tile(_quat_rotate_vec(emitter_quat, (1.0, 0.0, 0.0)), (n, 1))
            b = np.tile(_quat_rotate_vec(emitter_quat, (0.0, 1.0, 0.0)), (n, 1))
            return a, b
        if mode == "aligned_to_world_z":
            axis = np.array([0.0, 0.0, 1.0])
            to_cam = _normalize_rows(eye[None, :] - positions)
            a = _normalize_rows(np.cross(np.tile(axis, (n, 1)), to_cam))
            b = np.tile(axis, (n, 1))
            return a, b
        if mode in ("aligned_to_particle_dir", "motion_blur"):
            velocities = batch.velocities.astype(np.float64)
            speeds = np.linalg.norm(velocities, axis=1, keepdims=True)
            moving = speeds[:, 0] > 1e-6
            b = np.tile(cam_up, (n, 1))
            b[moving] = velocities[moving] / speeds[moving]
            to_cam = _normalize_rows(eye[None, :] - positions)
            a = np.cross(b, to_cam)
            a_norm = np.linalg.norm(a, axis=1, keepdims=True)
            degenerate = a_norm[:, 0] < 1e-6
            a = np.where(a_norm > 1e-6, a / np.maximum(a_norm, 1e-9), a)
            a[degenerate] = cam_right
            return a, b
        # Normal / Linked / unknown → full camera billboard.
        a = np.tile(cam_right, (n, 1))
        b = np.tile(cam_up, (n, 1))
        return a, b

    @classmethod
    def _expand_batch(cls, batch, eye: np.ndarray, forward: np.ndarray,
                      cam_right: np.ndarray, cam_up: np.ndarray,
                      emitter_quat) -> np.ndarray:
        n = batch.count
        positions = batch.positions.astype(np.float64)
        sizes = batch.sizes.astype(np.float64)
        mode = str(batch.render_mode or "Normal").lower()

        a, b = cls._batch_axes(batch, eye, cam_right, cam_up, emitter_quat)

        half_w = sizes[:, 0:1] * 0.5
        half_h = sizes[:, 1:2] * 0.5
        if mode == "motion_blur":
            # KotOR.js: stretch along velocity by |v| * blurLength.
            speeds = np.linalg.norm(batch.velocities.astype(np.float64), axis=1, keepdims=True)
            blur = max(0.0, float(getattr(batch, "blur_length", 0.0)))
            half_h = half_h * (1.0 + speeds * blur)

        # Roll spins the quad in its own plane (particlerot) for every mode
        # except velocity-stretched quads, whose long axis must stay on the
        # motion vector.  The Star Map galaxy is a rolling Billboard_to_Local_Z.
        if mode not in ("aligned_to_particle_dir", "motion_blur"):
            cos_r = np.cos(batch.rotations.astype(np.float64))[:, None]
            sin_r = np.sin(batch.rotations.astype(np.float64))[:, None]
            a_rot = a * cos_r + b * sin_r
            b_rot = -a * sin_r + b * cos_r
            a, b = a_rot, b_rot

        half_a = a * half_w
        half_b = b * half_h

        corner0 = positions - half_a - half_b   # uv (u0, v1)
        corner1 = positions + half_a - half_b   # uv (u1, v1)
        corner2 = positions + half_a + half_b   # uv (u1, v0)
        corner3 = positions - half_a + half_b   # uv (u0, v0)

        grid_x = max(1, int(batch.grid_x))
        grid_y = max(1, int(batch.grid_y))
        total_cells = grid_x * grid_y

        def _cell_uv(frames: np.ndarray):
            gx = (frames % grid_x).astype(np.float64)
            gy = (frames // grid_x % grid_y).astype(np.float64)
            u0 = gx / grid_x
            u1 = (gx + 1.0) / grid_x
            v0 = 1.0 - gy / grid_y
            v1 = 1.0 - (gy + 1.0) / grid_y
            return u0, u1, v0, v1

        frames = batch.frames.astype(np.int64)
        u0, u1, v0, v1 = _cell_uv(frames)
        if bool(batch.frame_blending) and total_cells > 1:
            next_frames = (frames + 1) % total_cells
            n_u0, n_u1, n_v0, n_v1 = _cell_uv(next_frames)
            blend = np.asarray(getattr(batch, "frame_frac", None), dtype=np.float64)
            if blend is None or blend.shape[0] != n:
                blend = np.zeros(n)
        else:
            n_u0, n_u1, n_v0, n_v1 = u0, u1, v0, v1
            blend = np.zeros(n)

        colors = batch.colors.astype(np.float64)

        verts = np.empty((n, _VERTS_PER_PARTICLE, _FLOATS_PER_VERTEX), dtype=np.float64)
        corner_order = (
            (corner0, u0, v1, n_u0, n_v1),
            (corner1, u1, v1, n_u1, n_v1),
            (corner2, u1, v0, n_u1, n_v0),
            (corner0, u0, v1, n_u0, n_v1),
            (corner2, u1, v0, n_u1, n_v0),
            (corner3, u0, v0, n_u0, n_v0),
        )
        for index, (corner, u_coord, v_coord, u2_coord, v2_coord) in enumerate(corner_order):
            verts[:, index, 0:3] = corner
            verts[:, index, 3] = u_coord
            verts[:, index, 4] = v_coord
            verts[:, index, 5] = u2_coord
            verts[:, index, 6] = v2_coord
            verts[:, index, 7] = blend
            verts[:, index, 8:12] = colors

        if str(batch.blend or "").lower() == "normal" and n > 1:
            # Painter's order within alpha-blended batches.
            depth = positions @ forward
            order = np.argsort(-depth)
            verts = verts[order]
        return verts.reshape(-1, _FLOATS_PER_VERTEX).astype(np.float32)

    # ── Drawing ──────────────────────────────────────────────────────────────
    def draw(self, ctx, blend_submission, tex_cache, white_tex,
             textures: Dict[str, object], batches: Sequence[object],
             mvp_bytes: bytes,
             eye: Tuple[float, float, float],
             target: Tuple[float, float, float],
             up: Tuple[float, float, float],
             restore_cull: bool = False) -> Tuple[int, int]:
        """Draw batches; returns (particle_count, draw_calls)."""
        if not batches or not self._ensure(ctx):
            return (0, 0)

        eye_np = np.asarray(eye, dtype=np.float64)
        forward = np.asarray(target, dtype=np.float64) - eye_np
        norm = np.linalg.norm(forward)
        forward = forward / norm if norm > 1e-9 else np.array([0.0, 1.0, 0.0])
        up_np = np.asarray(up, dtype=np.float64)
        cam_right = np.cross(forward, up_np)
        norm = np.linalg.norm(cam_right)
        cam_right = cam_right / norm if norm > 1e-9 else np.array([1.0, 0.0, 0.0])
        cam_up = np.cross(cam_right, forward)

        self._prog["u_mvp"].write(mvp_bytes)
        self._prog["u_tex"].value = 0

        try:
            ctx.disable(moderngl.CULL_FACE)
        except Exception:
            pass
        # glDepthMask lives on the bound Framebuffer in moderngl; assigning
        # ctx.depth_mask is an inert Python attribute.
        try:
            ctx.fbo.depth_mask = False
        except Exception:
            pass

        total = 0
        draw_calls = 0
        for batch in batches:
            texture_name = str(batch.texture or "").strip().lower()
            gl_texture = None
            if texture_name:
                image = textures.get(texture_name)
                if image is None:
                    if _PARTICLE_DEBUG:
                        log.warning("particle batch %s SKIP: texture %r not resident (%d textures known)",
                                    batch.node_name, texture_name, len(textures))
                    continue  # not resident yet; prewarm will deliver it
                gl_texture = tex_cache.get(image) if tex_cache is not None else None
                if gl_texture is None:
                    if _PARTICLE_DEBUG:
                        log.warning("particle batch %s SKIP: GL upload failed for %r",
                                    batch.node_name, texture_name)
                    continue
            else:
                gl_texture = white_tex
            if gl_texture is None:
                continue

            quat = tuple(getattr(batch, "emitter_quat", (0.0, 0.0, 0.0, 1.0)))
            verts = self._expand_batch(batch, eye_np, forward, cam_right, cam_up, quat)
            needed = verts.nbytes
            if needed <= 0 or not self._ensure_buffer(ctx, needed):
                continue

            blend_mode = str(batch.blend or "Normal").lower()
            if blend_mode == "punch-through" or blend_mode == "punchthrough":
                # KotOR.js: NormalBlending plus alphaTest 0.5.
                blend_submission.apply(
                    ctx, enabled=True,
                    func=(moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA),
                )
                self._prog["u_punch"].value = 1
            elif blend_mode == "lighten":
                blend_submission.apply(
                    ctx, enabled=True,
                    func=(moderngl.SRC_ALPHA, moderngl.ONE),
                )
                self._prog["u_punch"].value = 0
            else:
                blend_submission.apply(
                    ctx, enabled=True,
                    func=(moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA),
                )
                self._prog["u_punch"].value = 0

            gl_texture.use(location=0)
            self._vbo.orphan(self._capacity_bytes)
            self._vbo.write(verts.tobytes())
            vertex_count = verts.shape[0]
            self._vao.render(mode=moderngl.TRIANGLES, vertices=vertex_count)
            if _PARTICLE_DEBUG:
                log.warning(
                    "particle batch %s: verts=%d tex=%s blend=%s gl_error=%s "
                    "xyz0=%s rgba0=%s",
                    batch.node_name, vertex_count, texture_name, blend_mode,
                    getattr(ctx, "error", "?"),
                    np.round(verts[0, 0:3], 2).tolist(),
                    np.round(verts[0, 8:12], 3).tolist(),
                )
            total += vertex_count // _VERTS_PER_PARTICLE
            draw_calls += 1

        try:
            ctx.fbo.depth_mask = True
        except Exception:
            pass
        blend_submission.apply(ctx, enabled=False)
        if restore_cull:
            try:
                ctx.enable(moderngl.CULL_FACE)
            except Exception:
                pass
        return (total, draw_calls)
