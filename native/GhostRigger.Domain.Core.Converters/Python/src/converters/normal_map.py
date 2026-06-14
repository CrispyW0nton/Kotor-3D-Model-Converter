"""
Normal Map & ZBrush High-Fidelity Pipeline
Tools for projecting high-res detail onto low-poly KotOR meshes.

Workflow:
  1. Import low-poly OBJ from KotOR (decompiled via MDLOps)
  2. Import high-poly OBJ from ZBrush / Substance Painter
  3. Generate normal map (tangent-space)
  4. Convert normal map TGA → KotOR TPC format
  5. Configure TXI metadata for normal/bump mapping
  6. Bake AO, cavity maps optionally
"""

import os
import math
import struct
import logging
import array
from typing import List, Tuple, Optional, Dict, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
#  TXI Metadata Builder
#  Controls how KotOR engine interprets a texture (bump, env, etc.)
# ─────────────────────────────────────────────────────────────────────

class TXIBuilder:
    """
    Build TXI (Texture Extra Information) strings for KotOR textures.

    TXI files are optional plain-text metadata files that sit alongside
    TGA textures (same name, .txi extension) or are embedded at the end
    of TPC files. They control engine-side texture features.
    """

    def __init__(self):
        self._entries: Dict[str, str] = {}

    # ── Normal / Bump ──────────────────────────────────────────────
    def set_bumpmapped(self, enabled: bool = True) -> 'TXIBuilder':
        """Enable bump/normal mapping via environment map distortion"""
        if enabled:
            self._entries['bumpmapped'] = '1'
        else:
            self._entries.pop('bumpmapped', None)
        return self

    def set_envmapped(self, enabled: bool = True) -> 'TXIBuilder':
        """Enable environment cube mapping"""
        if enabled:
            self._entries['envmapped'] = '1'
        else:
            self._entries.pop('envmapped', None)
        return self

    def set_bumpmap_scaling(self, scale: float = 1.0) -> 'TXIBuilder':
        """Control strength of bump distortion (higher = stronger)"""
        self._entries['bumpintensity'] = f"{scale:.3f}"
        return self

    def set_specular_power(self, power: float = 16.0) -> 'TXIBuilder':
        """Shininess/specular exponent"""
        self._entries['specularpower'] = f"{power:.1f}"
        return self

    # ── Transparency / Blending ───────────────────────────────────
    def set_alpha_blend(self, mode: str = "default") -> 'TXIBuilder':
        """
        Blending mode: 'default', 'additive', 'punchthrough'
        """
        if mode == 'additive':
            self._entries['blending'] = 'additive'
        elif mode == 'punchthrough':
            self._entries['blending'] = 'punchthrough'
        else:
            self._entries.pop('blending', None)
        return self

    def set_procedural(self, enabled: bool = False) -> 'TXIBuilder':
        if enabled:
            self._entries['procedural'] = '1'
        return self

    # ── Wrapping ──────────────────────────────────────────────────
    def set_clamp(self, mode: str = "clamp") -> 'TXIBuilder':
        """
        Wrapping: 'clamp', 'wrapx', 'wrapy'
        """
        self._entries['clamp'] = mode
        return self

    # ── Channels ─────────────────────────────────────────────────
    def set_isbumpmap(self, enabled: bool = True) -> 'TXIBuilder':
        """Mark this texture as a bumpmap texture for K2 normal mapping"""
        if enabled:
            self._entries['isbumpmap'] = '1'
        return self

    def set_wateralpha(self, alpha: float = 0.5) -> 'TXIBuilder':
        self._entries['wateralpha'] = f"{alpha:.3f}"
        return self

    def set_fps(self, fps: int = 0) -> 'TXIBuilder':
        """For animated textures"""
        if fps > 0:
            self._entries['fps'] = str(fps)
        return self

    def set_numx(self, n: int = 1) -> 'TXIBuilder':
        """Number of horizontal frames for animated textures"""
        if n > 1:
            self._entries['numx'] = str(n)
        return self

    def set_numy(self, n: int = 1) -> 'TXIBuilder':
        """Number of vertical frames for animated textures"""
        if n > 1:
            self._entries['numy'] = str(n)
        return self

    def build(self) -> str:
        """Render TXI text string"""
        return '\n'.join(f"{k} {v}" for k, v in self._entries.items())

    def save_txi(self, path: str):
        """Save TXI as standalone .txi file"""
        with open(path, 'w', encoding='ascii') as f:
            f.write(self.build())

    @classmethod
    def normal_map_preset(cls, bump_scale: float = 1.0) -> 'TXIBuilder':
        """Standard TXI settings for a normal map texture in KotOR"""
        return (cls()
                .set_bumpmapped(True)
                .set_isbumpmap(True)
                .set_bumpmap_scaling(bump_scale))

    @classmethod
    def envmap_preset(cls) -> 'TXIBuilder':
        """TXI for cube/environment mapped specular texture"""
        return cls().set_envmapped(True).set_specular_power(32.0)

    @classmethod
    def diffuse_preset(cls) -> 'TXIBuilder':
        """Plain diffuse texture, no special effects"""
        return cls()


# ─────────────────────────────────────────────────────────────────────
#  Software Normal Map Baker
#  CPU-based baking for small meshes; use external tools for large ones
# ─────────────────────────────────────────────────────────────────────

class SoftwareNormalBaker:
    """
    Software ray-cast normal baker.
    Projects high-poly surface details onto a low-poly UV-mapped mesh.

    For best results use Marmoset Toolbag, Substance Painter, or xNormal.
    This software bake is a fallback for simple cases.

    Algorithm:
      - For each texel in the output map, find the closest surface point
        on the low-poly mesh using UV coordinates.
      - Cast a ray along that surface normal and find intersection with
        the high-poly mesh.
      - Store the high-poly surface normal in tangent space.
    """

    def __init__(self, width: int = 1024, height: int = 1024):
        self.width  = width
        self.height = height

    def bake(self,
             lo_verts: List[Tuple[float,float,float]],
             lo_uvs:   List[Tuple[float,float]],
             lo_norms: List[Tuple[float,float,float]],
             lo_faces: List[Tuple[int,int,int]],
             hi_verts: List[Tuple[float,float,float]],
             hi_norms: List[Tuple[float,float,float]],
             hi_faces: List[Tuple[int,int,int]],
             output_path: str,
             progress_callback: Optional[Callable[[int], None]] = None
             ) -> bool:
        """
        Bake a tangent-space normal map.
        Returns True on success, False on failure.
        """
        try:
            # Build low-poly per-triangle tangent space
            tris = self._build_triangle_data(lo_verts, lo_uvs, lo_norms, lo_faces)
            if not tris:
                logger.error("No valid low-poly triangles to bake")
                return False

            # Build high-poly BVH (simple grid)
            hi_tris = [(hi_verts[f[0]], hi_verts[f[1]], hi_verts[f[2]],
                        hi_norms[f[0]] if f[0] < len(hi_norms) else (0,0,1),
                        hi_norms[f[1]] if f[1] < len(hi_norms) else (0,0,1),
                        hi_norms[f[2]] if f[2] < len(hi_norms) else (0,0,1))
                       for f in hi_faces
                       if f[0]<len(hi_verts) and f[1]<len(hi_verts) and f[2]<len(hi_verts)]

            # Output: RGBA buffer (will be RGB normal + A=1)
            W, H = self.width, self.height
            buffer = bytearray(W * H * 4)
            # Default to flat normal (128,128,255)
            for i in range(W * H):
                buffer[i*4+0] = 128
                buffer[i*4+1] = 128
                buffer[i*4+2] = 255
                buffer[i*4+3] = 255

            # Build UV-to-triangle map
            tri_uv_lookup = self._build_uv_lookup(tris, W, H)

            total = W * H
            processed = 0

            for y in range(H):
                for x in range(W):
                    u = (x + 0.5) / W
                    v = (y + 0.5) / H
                    # Find triangle containing this UV
                    tri = tri_uv_lookup.get((x, y))
                    if tri is None:
                        processed += 1
                        continue

                    # Barycentric coords in UV space
                    bary = _barycentric_uv(u, v,
                        tri['uv0'], tri['uv1'], tri['uv2'])
                    if bary is None:
                        processed += 1
                        continue

                    # Interpolate world position & surface normal
                    wp = _lerp3(tri['v0'],tri['v1'],tri['v2'], bary)
                    wn = _normalize3(_lerp3(tri['n0'],tri['n1'],tri['n2'], bary))

                    # Cast ray and find closest hi-poly hit
                    hit_normal = self._ray_cast_normal(wp, wn, hi_tris)

                    if hit_normal:
                        # Transform to tangent space
                        tn = _world_to_tangent(hit_normal, wn,
                                               tri['tangent'], tri['bitangent'])
                        # Pack to RGB (0..1 -> 0..255)
                        r = int((tn[0] * 0.5 + 0.5) * 255)
                        g = int((tn[1] * 0.5 + 0.5) * 255)
                        b = int((tn[2] * 0.5 + 0.5) * 255)
                        idx = (y * W + x) * 4
                        buffer[idx+0] = max(0, min(255, r))
                        buffer[idx+1] = max(0, min(255, g))
                        buffer[idx+2] = max(0, min(255, b))
                        buffer[idx+3] = 255

                    processed += 1
                    if progress_callback and processed % (W*10) == 0:
                        progress_callback(int(processed * 100 / total))

            # Write as TGA (RGBA 32-bit)
            tga_header = struct.pack('<BBBHHHHHHHBB',
                0, 0, 2, 0, 0, 0, 0, 0, W, H, 32, 0x20)
            # Swap R and B for TGA BGR format
            for i in range(W * H):
                buffer[i*4], buffer[i*4+2] = buffer[i*4+2], buffer[i*4]

            with open(output_path, 'wb') as f:
                f.write(tga_header)
                f.write(bytes(buffer))

            logger.info(f"Baked normal map: {output_path} ({W}x{H})")
            return True

        except Exception as e:
            logger.error(f"Normal map bake failed: {e}")
            import traceback; traceback.print_exc()
            return False

    def _build_triangle_data(self, verts, uvs, norms, faces):
        tris = []
        for f in faces:
            v0,v1,v2 = f
            if v0>=len(verts) or v1>=len(verts) or v2>=len(verts):
                continue
            uv0 = uvs[v0] if v0<len(uvs) else (0.0, 0.0)
            uv1 = uvs[v1] if v1<len(uvs) else (0.0, 0.0)
            uv2 = uvs[v2] if v2<len(uvs) else (0.0, 0.0)
            n0  = norms[v0] if v0<len(norms) else (0.,0.,1.)
            n1  = norms[v1] if v1<len(norms) else (0.,0.,1.)
            n2  = norms[v2] if v2<len(norms) else (0.,0.,1.)

            tangent, bitangent = _compute_tangent(
                verts[v0], verts[v1], verts[v2],
                uv0, uv1, uv2)

            tris.append({
                'v0': verts[v0], 'v1': verts[v1], 'v2': verts[v2],
                'uv0': uv0, 'uv1': uv1, 'uv2': uv2,
                'n0': n0, 'n1': n1, 'n2': n2,
                'tangent': tangent, 'bitangent': bitangent,
            })
        return tris

    def _build_uv_lookup(self, tris: List[Dict], W: int, H: int) -> Dict:
        """Rasterize triangle UVs into a pixel lookup table"""
        lookup: Dict[Tuple[int,int], Dict] = {}
        for tri in tris:
            # Get pixel bounding box
            uv0, uv1, uv2 = tri['uv0'], tri['uv1'], tri['uv2']
            min_x = max(0, int(min(uv0[0], uv1[0], uv2[0]) * W) - 1)
            max_x = min(W-1, int(max(uv0[0], uv1[0], uv2[0]) * W) + 1)
            min_y = max(0, int(min(uv0[1], uv1[1], uv2[1]) * H) - 1)
            max_y = min(H-1, int(max(uv0[1], uv1[1], uv2[1]) * H) + 1)
            for y in range(min_y, max_y+1):
                for x in range(min_x, max_x+1):
                    u = (x + 0.5) / W
                    v = (y + 0.5) / H
                    bary = _barycentric_uv(u, v, uv0, uv1, uv2)
                    if bary is not None:
                        lookup[(x, y)] = tri
        return lookup

    def _ray_cast_normal(self, origin, direction, hi_tris):
        """Find closest intersection with high-poly mesh"""
        best_t = float('inf')
        best_normal = None
        ox, oy, oz = origin
        dx, dy, dz = direction

        for v0, v1, v2, n0, n1, n2 in hi_tris:
            t, bary = _ray_triangle_intersect(
                (ox,oy,oz), (dx,dy,dz), v0, v1, v2)
            if t is not None and 0 < t < best_t:
                best_t = t
                # Interpolate normal at hit point
                b0, b1, b2 = bary
                nx = n0[0]*b0 + n1[0]*b1 + n2[0]*b2
                ny = n0[1]*b0 + n1[1]*b1 + n2[1]*b2
                nz = n0[2]*b0 + n1[2]*b1 + n2[2]*b2
                best_normal = _normalize3((nx, ny, nz))

        return best_normal


# ─────────────────────────────────────────────
#  Math Helpers
# ─────────────────────────────────────────────

def _normalize3(v) -> Tuple[float,float,float]:
    l = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if l < 1e-8:
        return (0.0, 0.0, 1.0)
    return (v[0]/l, v[1]/l, v[2]/l)

def _dot3(a, b) -> float:
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def _cross3(a, b) -> Tuple[float,float,float]:
    return (a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0])

def _lerp3(v0, v1, v2, bary) -> Tuple[float,float,float]:
    b0,b1,b2 = bary
    return (v0[0]*b0+v1[0]*b1+v2[0]*b2,
            v0[1]*b0+v1[1]*b1+v2[1]*b2,
            v0[2]*b0+v1[2]*b1+v2[2]*b2)

def _barycentric_uv(u, v, uv0, uv1, uv2) -> Optional[Tuple[float,float,float]]:
    """Compute barycentric coords for (u,v) in triangle (uv0,uv1,uv2)"""
    v0 = (uv1[0]-uv0[0], uv1[1]-uv0[1])
    v1 = (uv2[0]-uv0[0], uv2[1]-uv0[1])
    v2 = (u-uv0[0], v-uv0[1])
    d00 = v0[0]*v0[0] + v0[1]*v0[1]
    d01 = v0[0]*v1[0] + v0[1]*v1[1]
    d11 = v1[0]*v1[0] + v1[1]*v1[1]
    d20 = v2[0]*v0[0] + v2[1]*v0[1]
    d21 = v2[0]*v1[0] + v2[1]*v1[1]
    denom = d00*d11 - d01*d01
    if abs(denom) < 1e-10:
        return None
    b1 = (d11*d20 - d01*d21) / denom
    b2 = (d00*d21 - d01*d20) / denom
    b0 = 1.0 - b1 - b2
    if b0 < -0.001 or b1 < -0.001 or b2 < -0.001:
        return None
    return (b0, b1, b2)

def _compute_tangent(v0, v1, v2, uv0, uv1, uv2):
    """Compute tangent/bitangent vectors from triangle geometry"""
    e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
    e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
    d1 = (uv1[0]-uv0[0], uv1[1]-uv0[1])
    d2 = (uv2[0]-uv0[0], uv2[1]-uv0[1])
    denom = d1[0]*d2[1] - d2[0]*d1[1]
    if abs(denom) < 1e-10:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    r = 1.0 / denom
    tangent   = ((d2[1]*e1[0]-d1[1]*e2[0])*r,
                 (d2[1]*e1[1]-d1[1]*e2[1])*r,
                 (d2[1]*e1[2]-d1[1]*e2[2])*r)
    bitangent = ((d1[0]*e2[0]-d2[0]*e1[0])*r,
                 (d1[0]*e2[1]-d2[0]*e1[1])*r,
                 (d1[0]*e2[2]-d2[0]*e1[2])*r)
    return _normalize3(tangent), _normalize3(bitangent)

def _world_to_tangent(world_n, surface_n, tangent, bitangent):
    """Convert world-space normal to tangent space"""
    tx = _dot3(world_n, tangent)
    ty = _dot3(world_n, bitangent)
    tz = _dot3(world_n, surface_n)
    return _normalize3((tx, ty, tz))

def _ray_triangle_intersect(origin, direction, v0, v1, v2):
    """Möller–Trumbore intersection"""
    EPSILON = 1e-7
    e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
    e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
    h  = _cross3(direction, e2)
    a  = _dot3(e1, h)
    if abs(a) < EPSILON:
        return None, None
    f  = 1.0 / a
    s  = (origin[0]-v0[0], origin[1]-v0[1], origin[2]-v0[2])
    u  = f * _dot3(s, h)
    if u < 0.0 or u > 1.0:
        return None, None
    q  = _cross3(s, e1)
    v  = f * _dot3(direction, q)
    if v < 0.0 or u+v > 1.0:
        return None, None
    t  = f * _dot3(e2, q)
    if t < EPSILON:
        return None, None
    return t, (1.0-u-v, u, v)
