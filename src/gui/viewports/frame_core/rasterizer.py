"""Per-triangle software rasterization helpers."""

from __future__ import annotations

from .dependencies import *  # noqa: F401,F403
from .math_helpers import _clamp

# ─────────────────────────────────────────────────────────────────────
#  Triangle rasterizer helper  (KotOR shader-accurate)
# ─────────────────────────────────────────────────────────────────────

def _rasterize_triangle_textured(pixels, W, H, z_buf,
                                  p0, p1, p2,
                                  uv0, uv1, uv2,
                                  n0, n1, n2,
                                  tex_img, tex_cache,
                                  light_dir, eye_dir,
                                  diffuse_color, ambient_color,
                                  specular_col, shininess,
                                  selfillum,
                                  alpha,
                                  shade_mode):
    """
    Software rasterizes a single triangle with KotOR-accurate shading:
    - Affine UV interpolation
    - Per-vertex normal Gouraud shading
    - Phong specular (approximated)
    - Self-illumination color (additive)
    - Alpha transparency (written to pixels directly – no true blending in SW rasterizer)
    - Depth buffer test

    p0,p1,p2 = (sx, sy, depth)  screen pixels + depth
    uv0,uv1,uv2 = (u, v) texture coords
    n0,n1,n2 = (nx, ny, nz) vertex normals in world space
    selfillum = (r,g,b) 0..1 self-illumination color
    alpha     = float 0..1 opacity
    """
    x0, y0, d0 = p0
    x1, y1, d1 = p1
    x2, y2, d2 = p2

    min_x = max(0, min(x0, x1, x2))
    max_x = min(W-1, max(x0, x1, x2))
    min_y = max(0, min(y0, y1, y2))
    max_y = min(H-1, max(y0, y1, y2))

    if min_x > max_x or min_y > max_y:
        return

    denom = (y1 - y2)*(x0 - x2) + (x2 - x1)*(y0 - y2)
    if abs(denom) < 0.5:
        return

    inv_denom = 1.0 / denom
    si_r, si_g, si_b = selfillum

    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            w0 = ((y1 - y2)*(px - x2) + (x2 - x1)*(py - y2)) * inv_denom
            w1 = ((y2 - y0)*(px - x2) + (x0 - x2)*(py - y2)) * inv_denom
            w2 = 1.0 - w0 - w1

            if w0 < 0 or w1 < 0 or w2 < 0:
                continue

            depth = w0*d0 + w1*d1 + w2*d2
            buf_idx = py * W + px
            if depth >= z_buf[buf_idx]:
                continue
            z_buf[buf_idx] = depth

            u = w0*uv0[0] + w1*uv1[0] + w2*uv2[0]
            v = w0*uv0[1] + w1*uv1[1] + w2*uv2[1]

            nx = w0*n0[0] + w1*n1[0] + w2*n2[0]
            ny = w0*n0[1] + w1*n1[1] + w2*n2[1]
            nz = w0*n0[2] + w1*n1[2] + w2*n2[2]
            nl = math.sqrt(nx*nx + ny*ny + nz*nz)
            if nl > 1e-9:
                nx /= nl; ny /= nl; nz /= nl

            # KotOR lighting: ambient + diffuse (two-sided)
            ndotl = nx*light_dir[0] + ny*light_dir[1] + nz*light_dir[2]
            ndotl_pos = max(0.0, ndotl)
            ndotl_neg = max(0.0, -ndotl) * 0.35   # back-face fill (KotOR uses ~35%)
            ndotl_f   = ndotl_pos + ndotl_neg

            # Blinn-Phong specular
            spec = 0.0
            if shininess > 0.5 and ndotl_pos > 0:
                hx = light_dir[0] + eye_dir[0]
                hy = light_dir[1] + eye_dir[1]
                hz = light_dir[2] + eye_dir[2]
                hl = math.sqrt(hx*hx + hy*hy + hz*hz)
                if hl > 1e-9:
                    hx /= hl; hy /= hl; hz /= hl
                ndoth = max(0.0, nx*hx + ny*hy + nz*hz)
                spec = ndoth ** min(shininess * 2.0, 128.0)

            shade = ambient_color + (1.0 - ambient_color) * ndotl_f

            if tex_img is not None:
                tr, tg, tb, ta = tex_cache.sample_bilinear(tex_img, u, v)
                # Skip fully transparent pixels
                if ta < 8:
                    continue
                # Modulate: texture × lighting
                r = int(_clamp(tr * shade + specular_col * spec * 255
                               + si_r * 255, 0, 255))
                g = int(_clamp(tg * shade + specular_col * spec * 255
                               + si_g * 255, 0, 255))
                b = int(_clamp(tb * shade + specular_col * spec * 255
                               + si_b * 255, 0, 255))
            else:
                r = int(_clamp(diffuse_color[0] * shade * 255
                               + specular_col * spec * 255 + si_r * 255, 0, 255))
                g = int(_clamp(diffuse_color[1] * shade * 255
                               + specular_col * spec * 255 + si_g * 255, 0, 255))
                b = int(_clamp(diffuse_color[2] * shade * 255
                               + specular_col * spec * 255 + si_b * 255, 0, 255))

            pixels[px, py] = (r, g, b)



__all__ = tuple(name for name in globals() if not name.startswith('__'))
