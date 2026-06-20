"""Shadow-ray support for generated lightmap bakes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .lightmap_rasterizer import _world_vertices

try:  # pragma: no cover - exercised when Open3D is installed locally.
    import open3d as o3d
except Exception:  # pragma: no cover
    o3d = None


@dataclass
class ShadowTriangle:
    mesh_id: int
    v0: np.ndarray
    v1: np.ndarray
    v2: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray


class LightmapShadowSolver:
    """Simple cached triangle acceleration interface.

    This first pass stores per-triangle AABBs and rejects most ray tests before
    Moller-Trumbore intersection. It is intentionally small, but the public
    methods are ready for a BVH replacement without touching the baker.
    """

    def __init__(self) -> None:
        self._triangles: list[ShadowTriangle] = []
        self._o3d_scene = None
        self._last_error = ""

    def build_acceleration_structure(self, scene_meshes) -> None:
        triangles: list[ShadowTriangle] = []
        vertices: list[np.ndarray] = []
        indices: list[tuple[int, int, int]] = []
        for mesh in scene_meshes:
            verts = _world_vertices(mesh)
            for face in getattr(mesh, "faces", []) or []:
                try:
                    pts = [
                        np.asarray(verts[int(face[0])], dtype=np.float32),
                        np.asarray(verts[int(face[1])], dtype=np.float32),
                        np.asarray(verts[int(face[2])], dtype=np.float32),
                    ]
                except Exception:
                    continue
                stack = np.vstack(pts)
                base = len(vertices)
                vertices.extend(pts)
                indices.append((base, base + 1, base + 2))
                triangles.append(
                    ShadowTriangle(
                        mesh_id=id(mesh),
                        v0=pts[0],
                        v1=pts[1],
                        v2=pts[2],
                        bounds_min=stack.min(axis=0),
                        bounds_max=stack.max(axis=0),
                    )
                )
        self._triangles = triangles
        self._build_open3d_scene(vertices, indices)

    def is_occluded(
        self,
        origin,
        direction,
        max_distance: float,
        ignored_mesh_id: int | None = None,
    ) -> bool:
        if not self._triangles:
            return False
        o = np.asarray(origin, dtype=np.float32)
        d = np.asarray(direction, dtype=np.float32)
        length = float(np.linalg.norm(d))
        if length <= 1.0e-8:
            return False
        d = d / length
        max_dist = float(max_distance)
        if self._o3d_scene is not None:
            try:
                rays = o3d.core.Tensor([[o[0], o[1], o[2], d[0], d[1], d[2]]], dtype=o3d.core.Dtype.Float32)
                hits = self._o3d_scene.cast_rays(rays)
                t_hit = float(hits["t_hit"].numpy()[0])
                return np.isfinite(t_hit) and 1.0e-4 < t_hit < max_dist - 1.0e-4
            except Exception as exc:
                self._last_error = str(exc)
        ray_min = np.minimum(o, o + d * max_dist) - 1.0e-5
        ray_max = np.maximum(o, o + d * max_dist) + 1.0e-5
        for tri in self._triangles:
            if ignored_mesh_id is not None and tri.mesh_id == ignored_mesh_id:
                continue
            if np.any(tri.bounds_max < ray_min) or np.any(tri.bounds_min > ray_max):
                continue
            hit = _ray_triangle(o, d, tri.v0, tri.v1, tri.v2)
            if hit is not None and 1.0e-4 < hit < max_dist - 1.0e-4:
                return True
        return False

    def calculate_shadow_factor(self, texel: dict, light: object, settings) -> float:
        if not bool(getattr(settings, "use_shadows", True)):
            return 1.0
        if not bool(getattr(light, "casts_shadows", getattr(light, "light_shadow", True))):
            return 1.0
        position = np.asarray(texel["position"], dtype=np.float32)
        normal = np.asarray(texel["normal"], dtype=np.float32)
        origin = position + normal * float(getattr(settings, "normal_bias", 0.002))
        kind = str(getattr(light, "type", getattr(light, "light_kind", "point")) or "point").lower()
        if kind.endswith("ambient") or bool(getattr(light, "ambient_only", False)):
            return 1.0
        if "directional" in kind:
            direction = -np.asarray(_direction_from_light(light), dtype=np.float32)
            max_distance = 100000.0
        else:
            light_pos = np.asarray(getattr(light, "position", (0.0, 0.0, 0.0)), dtype=np.float32)
            vec = light_pos - origin
            max_distance = float(np.linalg.norm(vec))
            direction = vec
        if self.is_occluded(origin, direction, max_distance, texel.get("mesh_id")):
            return 0.0
        return 1.0

    def clear_cache(self) -> None:
        self._triangles = []
        self._o3d_scene = None

    def _build_open3d_scene(self, vertices: list[np.ndarray], indices: list[tuple[int, int, int]]) -> None:
        self._o3d_scene = None
        if o3d is None or not vertices or not indices:
            return
        try:
            scene = o3d.t.geometry.RaycastingScene()
            verts = o3d.core.Tensor(np.asarray(vertices, dtype=np.float32), dtype=o3d.core.Dtype.Float32)
            tris = o3d.core.Tensor(np.asarray(indices, dtype=np.uint32), dtype=o3d.core.Dtype.UInt32)
            mesh = o3d.t.geometry.TriangleMesh(verts, tris)
            scene.add_triangles(mesh)
            self._o3d_scene = scene
        except Exception as exc:
            self._last_error = str(exc)
            self._o3d_scene = None


def _ray_triangle(origin, direction, v0, v1, v2) -> float | None:
    # Moller-Trumbore ray/triangle test. Returns ray distance on hit.
    eps = 1.0e-7
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direction, edge2)
    a = float(np.dot(edge1, h))
    if -eps < a < eps:
        return None
    f = 1.0 / a
    s = origin - v0
    u = f * float(np.dot(s, h))
    if u < 0.0 or u > 1.0:
        return None
    q = np.cross(s, edge1)
    v = f * float(np.dot(direction, q))
    if v < 0.0 or u + v > 1.0:
        return None
    t = f * float(np.dot(edge2, q))
    return t if t > eps else None


def _direction_from_light(light: object) -> tuple[float, float, float]:
    direction = getattr(light, "direction", None)
    if direction is not None:
        try:
            return (float(direction[0]), float(direction[1]), float(direction[2]))
        except Exception:
            pass
    return (0.0, -1.0, -1.0)
