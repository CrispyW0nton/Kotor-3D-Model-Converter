"""ModernGL bloom post-process for the offscreen viewport renderer.

Bright-pass → two-iteration separable gaussian blur at quarter resolution →
additive composite back onto the scene framebuffer.  This is what gives the
retail-style glow to additive content: emitter particles (Star Map nav rings,
galaxy, flares), lightsaber blades, holograms, and self-illuminated panels.

Package-local to ``GhostRigger.Core.Rendering`` like the other ModernGL
adapter modules.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

try:
    import moderngl
except Exception:  # pragma: no cover - renderer guards availability
    moderngl = None

log = logging.getLogger(__name__)

_FULLSCREEN_VERT = """
#version 330
out vec2 v_uv;
void main() {
    // Fullscreen triangle from gl_VertexID; no vertex buffer required.
    vec2 pos = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_uv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
"""

_BRIGHT_FRAG = """
#version 330
uniform sampler2D u_scene;
uniform float u_threshold;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    vec3 c = texture(u_scene, v_uv).rgb;
    // Soft knee: keep energy proportional above the threshold.
    vec3 bright = max(c - vec3(u_threshold), vec3(0.0));
    fragColor = vec4(bright / max(1e-4, 1.0 - u_threshold), 1.0);
}
"""

_BLUR_FRAG = """
#version 330
uniform sampler2D u_tex;
uniform vec2 u_dir;   // (1/width, 0) or (0, 1/height)
in vec2 v_uv;
out vec4 fragColor;
void main() {
    // 9-tap gaussian, sigma ~2.4
    float w0 = 0.2270270270;
    float w1 = 0.1945945946;
    float w2 = 0.1216216216;
    float w3 = 0.0540540541;
    float w4 = 0.0162162162;
    vec3 c = texture(u_tex, v_uv).rgb * w0;
    c += texture(u_tex, v_uv + u_dir * 1.3846153846).rgb * (w1 + w2);
    c += texture(u_tex, v_uv - u_dir * 1.3846153846).rgb * (w1 + w2);
    c += texture(u_tex, v_uv + u_dir * 3.2307692308).rgb * (w3 + w4);
    c += texture(u_tex, v_uv - u_dir * 3.2307692308).rgb * (w3 + w4);
    fragColor = vec4(c, 1.0);
}
"""

_COMPOSITE_FRAG = """
#version 330
uniform sampler2D u_bloom;
uniform float u_strength;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    vec3 bloom = texture(u_bloom, v_uv).rgb * u_strength;
    fragColor = vec4(bloom, 1.0);
}
"""


class ModernGLBloomPass:
    """Owns the bloom programs and reduced-resolution ping-pong targets."""

    def __init__(self) -> None:
        self._bright_prog = None
        self._blur_prog = None
        self._composite_prog = None
        self._bright_vao = None
        self._blur_vao = None
        self._composite_vao = None
        self._fbo_a = None
        self._fbo_b = None
        self._tex_a = None
        self._tex_b = None
        self._size: Tuple[int, int] = (0, 0)
        self._failed = False

    def release(self) -> None:
        for resource in (
            self._bright_vao, self._blur_vao, self._composite_vao,
            self._fbo_a, self._fbo_b, self._tex_a, self._tex_b,
            self._bright_prog, self._blur_prog, self._composite_prog,
        ):
            if resource is not None:
                try:
                    resource.release()
                except Exception:
                    pass
        self._bright_prog = None
        self._blur_prog = None
        self._composite_prog = None
        self._bright_vao = None
        self._blur_vao = None
        self._composite_vao = None
        self._fbo_a = None
        self._fbo_b = None
        self._tex_a = None
        self._tex_b = None
        self._size = (0, 0)

    def _ensure(self, ctx, width: int, height: int) -> bool:
        if moderngl is None or self._failed:
            return False
        if self._bright_prog is None:
            try:
                self._bright_prog = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                                fragment_shader=_BRIGHT_FRAG)
                self._blur_prog = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                              fragment_shader=_BLUR_FRAG)
                self._composite_prog = ctx.program(vertex_shader=_FULLSCREEN_VERT,
                                                   fragment_shader=_COMPOSITE_FRAG)
                self._bright_vao = ctx.vertex_array(self._bright_prog, [])
                self._blur_vao = ctx.vertex_array(self._blur_prog, [])
                self._composite_vao = ctx.vertex_array(self._composite_prog, [])
            except Exception as exc:
                log.warning("Bloom shader setup failed: %s", exc)
                self._failed = True
                return False

        # Half-resolution (was quarter): a quarter-res blur upsamples into a
        # coarse, blocky blob that veils the whole frame — the "washed out"
        # look.  Half-res keeps the glow tight and crisp (KotOR.js Forge shows
        # no bloom at all, so a subtle accent is closer to that than a wide
        # smear).  Trivial cost on modern GPUs.
        wanted = (max(16, width // 2), max(16, height // 2))
        if wanted != self._size:
            for resource in (self._fbo_a, self._fbo_b, self._tex_a, self._tex_b):
                if resource is not None:
                    try:
                        resource.release()
                    except Exception:
                        pass
            try:
                self._tex_a = ctx.texture(wanted, 4)
                self._tex_b = ctx.texture(wanted, 4)
                for tex in (self._tex_a, self._tex_b):
                    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
                    tex.repeat_x = False
                    tex.repeat_y = False
                self._fbo_a = ctx.framebuffer(color_attachments=[self._tex_a])
                self._fbo_b = ctx.framebuffer(color_attachments=[self._tex_b])
            except Exception as exc:
                log.warning("Bloom target allocation failed: %s", exc)
                self._failed = True
                return False
            self._size = wanted
        return True

    def apply(self, ctx, blend_submission, scene_fbo, scene_texture,
              width: int, height: int, *, threshold: float = 0.5,
              strength: float = 0.85, iterations: int = 2) -> bool:
        """Composite bloom extracted from ``scene_texture`` onto ``scene_fbo``."""
        if scene_fbo is None or scene_texture is None:
            return False
        if not self._ensure(ctx, width, height):
            return False

        small_w, small_h = self._size
        depth_was_enabled = True
        try:
            ctx.disable(moderngl.DEPTH_TEST)
        except Exception:
            depth_was_enabled = False

        # 1. Bright pass into A (no blending).
        blend_submission.apply(ctx, enabled=False)
        self._fbo_a.use()
        ctx.viewport = (0, 0, small_w, small_h)
        scene_texture.use(location=0)
        self._bright_prog["u_scene"].value = 0
        self._bright_prog["u_threshold"].value = float(max(0.0, min(0.95, threshold)))
        self._bright_vao.render(mode=moderngl.TRIANGLES, vertices=3)

        # 2. Separable gaussian blur, ping-pong A <-> B.
        for _ in range(max(1, int(iterations))):
            self._fbo_b.use()
            self._tex_a.use(location=0)
            self._blur_prog["u_tex"].value = 0
            self._blur_prog["u_dir"].value = (1.0 / small_w, 0.0)
            self._blur_vao.render(mode=moderngl.TRIANGLES, vertices=3)

            self._fbo_a.use()
            self._tex_b.use(location=0)
            self._blur_prog["u_dir"].value = (0.0, 1.0 / small_h)
            self._blur_vao.render(mode=moderngl.TRIANGLES, vertices=3)

        # 3. Additive composite onto the scene framebuffer.
        scene_fbo.use()
        ctx.viewport = (0, 0, width, height)
        blend_submission.apply(ctx, enabled=True,
                               func=(moderngl.ONE, moderngl.ONE))
        self._tex_a.use(location=0)
        self._composite_prog["u_bloom"].value = 0
        self._composite_prog["u_strength"].value = float(max(0.0, strength))
        self._composite_vao.render(mode=moderngl.TRIANGLES, vertices=3)
        blend_submission.apply(ctx, enabled=False)

        if depth_was_enabled:
            try:
                ctx.enable(moderngl.DEPTH_TEST)
            except Exception:
                pass
        return True
