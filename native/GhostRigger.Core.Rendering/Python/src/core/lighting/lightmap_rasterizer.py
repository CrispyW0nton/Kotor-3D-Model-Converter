"""Software UV rasterizer for generated lightmap bakes."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite

import numpy as np

from .lightmap_uv_validator import face_uv_attr_for_channel, uv_attr_for_channel

try:
    from src.core.geometry.model_data import _quat_rotate
except Exception:  # pragma: no cover
    _quat_rotate = None


@dataclass
class LightmapTexelBuffer:
    resolution: int
    valid_mask: np.ndarray
    world_positions: np.ndarray
    world_normals: np.ndarray
    mesh_ids: np.ndarray
    triangle_ids: np.ndarray
    material_ids: np.ndarray
    base_diffuse: np.ndarray
    baked_rgb: np.ndarray
    warnings: list[str]


class LightmapRasterizer:
    """Rasterize existing UV triangles and interpolate world attributes."""

    def rasterize_mesh(self, mesh: object, uv_channel: int, resolution: int) -> LightmapTexelBuffer:
        res = int(resolution)
        buffer = LightmapTexelBuffer(
            resolution=res,
            valid_mask=np.zeros((res, res), dtype=bool),
            world_positions=np.zeros((res, res, 3), dtype=np.float32),
            world_normals=np.zeros((res, res, 3), dtype=np.float32),
            mesh_ids=np.full((res, res), -1, dtype=np.int32),
            triangle_ids=np.full((res, res), -1, dtype=np.int32),
            material_ids=np.full((res, res), -1, dtype=np.int32),
            base_diffuse=np.ones((res, res, 3), dtype=np.float32),
            baked_rgb=np.zeros((res, res, 3), dtype=np.float32),
            warnings=[],
        )
        world_verts = _world_vertices(mesh)
        world_normals = _world_normals(mesh, world_verts)
        diffuse = _safe_rgb(getattr(mesh, "diffuse", (1.0, 1.0, 1.0)), (1.0, 1.0, 1.0))
        faces = list(getattr(mesh, "faces", []) or [])
        face_mats = list(getattr(mesh, "face_mats", []) or [])

        for tri_index, face in enumerate(faces):
            uv_tri = self._uv_triangle(mesh, uv_channel, tri_index)
            if uv_tri is None:
                continue
            try:
                i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                p0, p1, p2 = world_verts[i0], world_verts[i1], world_verts[i2]
                n0, n1, n2 = world_normals[i0], world_normals[i1], world_normals[i2]
            except Exception:
                continue
            self.rasterize_triangle(
                buffer,
                uv_tri,
                (p0, p1, p2),
                (n0, n1, n2),
                tri_index,
                int(face_mats[tri_index]) if tri_index < len(face_mats) else 0,
                diffuse,
                id(mesh),
            )
        return buffer

    def rasterize_triangle(
        self,
        buffer: LightmapTexelBuffer,
        uv_tri: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
        positions: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
        normals: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
        triangle_index: int,
        material_id: int,
        diffuse: tuple[float, float, float],
        mesh_id: int = 0,
    ) -> None:
        res = buffer.resolution
        pix = [self.uv_to_texel(uv, res) for uv in uv_tri]
        if not all(isfinite(v) for point in pix for v in point):
            return
        min_x = max(0, int(floor(min(p[0] for p in pix) - 0.5)))
        max_x = min(res - 1, int(floor(max(p[0] for p in pix) + 0.5)))
        min_y = max(0, int(floor(min(p[1] for p in pix) - 0.5)))
        max_y = min(res - 1, int(floor(max(p[1] for p in pix) + 0.5)))
        if max_x < min_x or max_y < min_y:
            return

        # Barycentric coordinates are evaluated at texel centers in UV space.
        # This preserves interpolation accuracy and avoids edge gaps caused by
        # rounding the UV triangle directly to integer pixels.
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                uv = self.texel_to_uv(x, y, res)
                bary = self.calculate_barycentric(uv, uv_tri)
                if bary is None:
                    continue
                b0, b1, b2 = bary
                edge_eps = -1.0e-5
                if b0 < edge_eps or b1 < edge_eps or b2 < edge_eps:
                    continue
                pos = (
                    positions[0][0] * b0 + positions[1][0] * b1 + positions[2][0] * b2,
                    positions[0][1] * b0 + positions[1][1] * b1 + positions[2][1] * b2,
                    positions[0][2] * b0 + positions[1][2] * b1 + positions[2][2] * b2,
                )
                normal = _normalize((
                    normals[0][0] * b0 + normals[1][0] * b1 + normals[2][0] * b2,
                    normals[0][1] * b0 + normals[1][1] * b1 + normals[2][1] * b2,
                    normals[0][2] * b0 + normals[1][2] * b1 + normals[2][2] * b2,
                ))
                buffer.valid_mask[y, x] = True
                buffer.world_positions[y, x] = pos
                buffer.world_normals[y, x] = normal
                buffer.mesh_ids[y, x] = int(mesh_id) & 0x7FFFFFFF
                buffer.triangle_ids[y, x] = int(triangle_index)
                buffer.material_ids[y, x] = int(material_id)
                buffer.base_diffuse[y, x] = diffuse

    def calculate_barycentric(self, uv: tuple[float, float], tri) -> tuple[float, float, float] | None:
        (u0, v0), (u1, v1), (u2, v2) = tri
        u, v = uv
        denom = (v1 - v2) * (u0 - u2) + (u2 - u1) * (v0 - v2)
        if abs(denom) <= 1.0e-12:
            return None
        b0 = ((v1 - v2) * (u - u2) + (u2 - u1) * (v - v2)) / denom
        b1 = ((v2 - v0) * (u - u2) + (u0 - u2) * (v - v2)) / denom
        b2 = 1.0 - b0 - b1
        return b0, b1, b2

    def texel_to_uv(self, x: int, y: int, resolution: int) -> tuple[float, float]:
        return ((float(x) + 0.5) / float(resolution), 1.0 - ((float(y) + 0.5) / float(resolution)))

    def uv_to_texel(self, uv: tuple[float, float], resolution: int) -> tuple[float, float]:
        return (float(uv[0]) * float(resolution) - 0.5, (1.0 - float(uv[1])) * float(resolution) - 0.5)

    def _uv_triangle(self, mesh: object, uv_channel: int, face_index: int):
        attr = uv_attr_for_channel(uv_channel)
        uvs = list(getattr(mesh, attr, []) or [])
        if not uvs:
            return None
        faces = getattr(mesh, "faces", []) or []
        if face_index >= len(faces):
            return None
        face_uvs = getattr(mesh, face_uv_attr_for_channel(uv_channel), []) or []
        indices = face_uvs[face_index] if face_uvs and face_index < len(face_uvs) else faces[face_index]
        try:
            return tuple((float(uvs[int(i)][0]), float(uvs[int(i)][1])) for i in indices)
        except Exception:
            return None


def _world_vertices(mesh: object) -> list[tuple[float, float, float]]:
    verts = list(getattr(mesh, "vertices", []) or [])
    if int(getattr(mesh, "vertex_space", 0) or 0) == 1:
        return [tuple(map(float, v[:3])) for v in verts]
    try:
        wp, wo = mesh.world_transform()
    except Exception:
        wp, wo = getattr(mesh, "position", (0.0, 0.0, 0.0)), (0.0, 0.0, 0.0, 1.0)
    is_identity = (float(wo[0]) ** 2 + float(wo[1]) ** 2 + float(wo[2]) ** 2) ** 0.5 < 0.001
    result = []
    for v in verts:
        vv = (float(v[0]), float(v[1]), float(v[2]))
        if is_identity or _quat_rotate is None:
            rv = vv
        else:
            rv = _quat_rotate(wo, vv)
        result.append((rv[0] + float(wp[0]), rv[1] + float(wp[1]), rv[2] + float(wp[2])))
    return result


def _world_normals(mesh: object, world_verts: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    normals = list(getattr(mesh, "normals", []) or [])
    if len(normals) >= len(world_verts):
        try:
            _wp, wo = mesh.world_transform()
        except Exception:
            wo = (0.0, 0.0, 0.0, 1.0)
        is_identity = (float(wo[0]) ** 2 + float(wo[1]) ** 2 + float(wo[2]) ** 2) ** 0.5 < 0.001
        out = []
        for n in normals[:len(world_verts)]:
            nn = (float(n[0]), float(n[1]), float(n[2]))
            out.append(_normalize(nn if is_identity or _quat_rotate is None else _quat_rotate(wo, nn)))
        return out
    accum = np.zeros((len(world_verts), 3), dtype=np.float64)
    for face in getattr(mesh, "faces", []) or []:
        try:
            i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
            n = _face_normal(world_verts[i0], world_verts[i1], world_verts[i2])
            accum[i0] += n
            accum[i1] += n
            accum[i2] += n
        except Exception:
            continue
    return [_normalize(tuple(row)) for row in accum]


def _face_normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def _normalize(v):
    length = (float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2) ** 0.5
    if length <= 1.0e-9:
        return (0.0, 0.0, 1.0)
    return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)


def _safe_rgb(value: object, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        return (
            max(0.0, min(1.0, float(value[0]))),
            max(0.0, min(1.0, float(value[1]))),
            max(0.0, min(1.0, float(value[2]))),
        )
    except Exception:
        return fallback
