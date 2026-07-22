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
    triangle_id: int
    v0: np.ndarray
    v1: np.ndarray
    v2: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray


@dataclass
class _ShadowBVHNode:
    bounds_min: np.ndarray
    bounds_max: np.ndarray
    left: "_ShadowBVHNode | None" = None
    right: "_ShadowBVHNode | None" = None
    triangle_indices: tuple[int, ...] = ()


class LightmapShadowSolver:
    """Cached triangle shadow acceleration with exact source-face rejection.

    Open3D is used when available.  The dependency-free path builds a compact
    median-split BVH and performs Moller-Trumbore tests only in intersected
    leaves, keeping room-wide authored bakes usable without optional packages.
    """

    def __init__(self) -> None:
        self._triangles: list[ShadowTriangle] = []
        self._bvh_root: _ShadowBVHNode | None = None
        self._o3d_scene = None
        self._last_error = ""

    def build_acceleration_structure(self, scene_meshes) -> None:
        triangles: list[ShadowTriangle] = []
        vertices: list[np.ndarray] = []
        indices: list[tuple[int, int, int]] = []
        for mesh in scene_meshes:
            verts = _world_vertices(mesh)
            mesh_id = _mesh_identifier(mesh)
            for triangle_id, face in enumerate(getattr(mesh, "faces", []) or []):
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
                        mesh_id=mesh_id,
                        triangle_id=int(triangle_id),
                        v0=pts[0],
                        v1=pts[1],
                        v2=pts[2],
                        bounds_min=stack.min(axis=0),
                        bounds_max=stack.max(axis=0),
                    )
                )
        self._triangles = triangles
        if triangles:
            triangle_bounds_min = np.asarray([triangle.bounds_min for triangle in triangles], dtype=np.float32)
            triangle_bounds_max = np.asarray([triangle.bounds_max for triangle in triangles], dtype=np.float32)
            triangle_centroids = (triangle_bounds_min + triangle_bounds_max) * 0.5
            self._bvh_root = self._build_bvh(
                np.arange(len(triangles), dtype=np.int32),
                triangle_bounds_min,
                triangle_bounds_max,
                triangle_centroids,
            )
        else:
            self._bvh_root = None
        self._build_open3d_scene(vertices, indices)

    def is_occluded(
        self,
        origin,
        direction,
        max_distance: float,
        ignored_mesh_id: int | None = None,
        ignored_triangle_id: int | None = None,
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
        if max_dist <= 1.0e-4:
            return False
        ignored_triangle = None
        if ignored_mesh_id is not None and ignored_triangle_id is not None:
            ignored_triangle = (int(ignored_mesh_id) & 0x7FFFFFFF, int(ignored_triangle_id))
        if self._o3d_scene is not None:
            try:
                result = self._is_occluded_open3d(o, d, max_dist, ignored_triangle)
                if result is not None:
                    return result
            except Exception as exc:
                self._last_error = str(exc)
        return self._is_occluded_cpu(o, d, max_dist, ignored_triangle)

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
        if self.is_occluded(
            origin,
            direction,
            max_distance,
            texel.get("mesh_id"),
            texel.get("triangle_id"),
        ):
            return 0.0
        return 1.0

    def clear_cache(self) -> None:
        self._triangles = []
        self._bvh_root = None
        self._o3d_scene = None

    def _is_occluded_cpu(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float,
        ignored_triangle: tuple[int, int] | None,
    ) -> bool:
        if self._bvh_root is None:
            return False
        stack = [self._bvh_root]
        while stack:
            node = stack.pop()
            if not _ray_intersects_bounds(
                origin,
                direction,
                node.bounds_min,
                node.bounds_max,
                max_distance,
            ):
                continue
            if node.triangle_indices:
                for index in node.triangle_indices:
                    tri = self._triangles[index]
                    if ignored_triangle == (tri.mesh_id, tri.triangle_id):
                        continue
                    hit = _ray_triangle(origin, direction, tri.v0, tri.v1, tri.v2)
                    if hit is not None and 1.0e-4 < hit < max_distance - 1.0e-4:
                        return True
                continue
            if node.left is not None:
                stack.append(node.left)
            if node.right is not None:
                stack.append(node.right)
        return False

    def _is_occluded_open3d(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float,
        ignored_triangle: tuple[int, int] | None,
    ) -> bool | None:
        """Return the first non-source hit while retaining Open3D acceleration.

        Open3D reports the source primitive as the first hit when a smoothed
        normal bias places the ray just behind its own polygon.  Advance past
        only that exact primitive and recast; never discard the rest of the
        source mesh, because folded surfaces must be able to self-shadow.
        """

        travelled = 0.0
        current_origin = np.asarray(origin, dtype=np.float32)
        for _attempt in range(8):
            remaining = max_distance - travelled
            if remaining <= 1.0e-4:
                return False
            rays = o3d.core.Tensor(
                [[
                    current_origin[0],
                    current_origin[1],
                    current_origin[2],
                    direction[0],
                    direction[1],
                    direction[2],
                ]],
                dtype=o3d.core.Dtype.Float32,
            )
            hits = self._o3d_scene.cast_rays(rays)
            t_hit = float(hits["t_hit"].numpy()[0])
            if not np.isfinite(t_hit) or t_hit >= remaining - 1.0e-4:
                return False
            try:
                primitive_values = hits["primitive_ids"]
            except Exception:
                return None
            primitive_id = int(primitive_values.numpy()[0])
            if primitive_id < 0 or primitive_id >= len(self._triangles):
                return None
            triangle = self._triangles[primitive_id]
            hit_key = (triangle.mesh_id, triangle.triangle_id)
            if t_hit > 1.0e-4 and hit_key != ignored_triangle:
                return True
            step = max(t_hit + 2.0e-4, 2.0e-4)
            travelled += step
            current_origin = origin + direction * travelled
        # A pathological stack of coincident source polygons is rare.  The
        # exact CPU BVH path remains authoritative when the recast limit is hit.
        return None

    def _build_bvh(
        self,
        triangle_indices: np.ndarray,
        triangle_bounds_min: np.ndarray,
        triangle_bounds_max: np.ndarray,
        triangle_centroids: np.ndarray,
    ) -> _ShadowBVHNode | None:
        if triangle_indices.size == 0:
            return None
        bounds_min = np.min(triangle_bounds_min[triangle_indices], axis=0)
        bounds_max = np.max(triangle_bounds_max[triangle_indices], axis=0)
        if triangle_indices.size <= 8:
            return _ShadowBVHNode(
                bounds_min,
                bounds_max,
                triangle_indices=tuple(int(index) for index in triangle_indices),
            )
        axis = int(np.argmax(bounds_max - bounds_min))
        order = np.argsort(triangle_centroids[triangle_indices, axis], kind="stable")
        ordered = triangle_indices[order]
        midpoint = ordered.size // 2
        left = self._build_bvh(
            ordered[:midpoint],
            triangle_bounds_min,
            triangle_bounds_max,
            triangle_centroids,
        )
        right = self._build_bvh(
            ordered[midpoint:],
            triangle_bounds_min,
            triangle_bounds_max,
            triangle_centroids,
        )
        return _ShadowBVHNode(bounds_min, bounds_max, left=left, right=right)

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


def _ray_intersects_bounds(origin, direction, bounds_min, bounds_max, max_distance: float) -> bool:
    t_min = 0.0
    t_max = float(max_distance)
    for axis in range(3):
        component = float(direction[axis])
        coordinate = float(origin[axis])
        lower = float(bounds_min[axis]) - 1.0e-5
        upper = float(bounds_max[axis]) + 1.0e-5
        if abs(component) <= 1.0e-12:
            if coordinate < lower or coordinate > upper:
                return False
            continue
        inverse = 1.0 / component
        near = (lower - coordinate) * inverse
        far = (upper - coordinate) * inverse
        if near > far:
            near, far = far, near
        t_min = max(t_min, near)
        t_max = min(t_max, far)
        if t_max < t_min:
            return False
    return t_max > 1.0e-4 and t_min < max_distance - 1.0e-4


def _mesh_identifier(mesh: object) -> int:
    """Match the signed-int-safe identifier stored by LightmapRasterizer."""

    return int(id(mesh)) & 0x7FFFFFFF


def _direction_from_light(light: object) -> tuple[float, float, float]:
    direction = getattr(light, "direction", None)
    if direction is not None:
        try:
            return (float(direction[0]), float(direction[1]), float(direction[2]))
        except Exception:
            pass
    return (0.0, -1.0, -1.0)
