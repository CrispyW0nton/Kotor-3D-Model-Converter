"""Renderer-neutral viewport picking helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class PickRequest:
    x: int
    y: int
    viewport_width: int
    viewport_height: int
    device_pixel_ratio: float = 1.0
    camera: object | None = None
    selection_mode: str = "object"
    include_hidden: bool = False
    include_locked: bool = False
    prefer_gizmo: bool = True
    modifiers: object | None = None
    display_options: object | None = None


@dataclass(frozen=True)
class PickHit:
    hit: bool = False
    object_id: object | None = None
    object_ref: object | None = None
    mesh_id: object | None = None
    node_id: object | None = None
    face_index: int | None = None
    vertex_index: int | None = None
    edge_index: object | None = None
    distance: float = float("inf")
    world_position: Vec3 | None = None
    normal: Vec3 | None = None
    screen_position: tuple[int, int] | None = None
    hit_kind: str = ""
    renderer_backend: str = "cpu"
    diagnostic: dict[str, object] = field(default_factory=dict)


class IPickingProvider(Protocol):
    def pick(self, request: PickRequest, scene, camera) -> PickHit:
        ...

    def marquee_pick(self, request: PickRequest, scene, camera, rect) -> list[PickHit]:
        ...


def ray_triangle_intersection(origin: Iterable[float], direction: Iterable[float], v0, v1, v2) -> float | None:
    eps = 1.0e-8
    ox, oy, oz = _vec3(origin)
    dx, dy, dz = _vec3(direction)
    ax, ay, az = _vec3(v0)
    bx, by, bz = _vec3(v1)
    cx, cy, cz = _vec3(v2)

    e1x, e1y, e1z = bx - ax, by - ay, bz - az
    e2x, e2y, e2z = cx - ax, cy - ay, cz - az
    px, py, pz = dy * e2z - dz * e2y, dz * e2x - dx * e2z, dx * e2y - dy * e2x
    det = e1x * px + e1y * py + e1z * pz
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    tx, ty, tz = ox - ax, oy - ay, oz - az
    u = (tx * px + ty * py + tz * pz) * inv_det
    if u < -eps or u > 1.0 + eps:
        return None
    qx, qy, qz = ty * e1z - tz * e1y, tz * e1x - tx * e1z, tx * e1y - ty * e1x
    v = (dx * qx + dy * qy + dz * qz) * inv_det
    if v < -eps or u + v > 1.0 + eps:
        return None
    t = (e2x * qx + e2y * qy + e2z * qz) * inv_det
    return t if t > eps else None


def ray_intersects_aabb(origin: Iterable[float], direction: Iterable[float], bb_min, bb_max) -> bool:
    ox, oy, oz = _vec3(origin)
    dx, dy, dz = _vec3(direction)
    mn = _vec3(bb_min)
    mx = _vec3(bb_max)
    tmin = 0.0
    tmax = float("inf")
    for o, d, lo, hi in ((ox, dx, mn[0], mx[0]), (oy, dy, mn[1], mx[1]), (oz, dz, mn[2], mx[2])):
        if abs(d) <= 1.0e-12:
            if o < lo or o > hi:
                return False
            continue
        inv = 1.0 / d
        t1 = (lo - o) * inv
        t2 = (hi - o) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmax < tmin:
            return False
    return True


def triangle_normal(v0, v1, v2) -> Vec3:
    ax, ay, az = _vec3(v0)
    bx, by, bz = _vec3(v1)
    cx, cy, cz = _vec3(v2)
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = max(1.0e-12, (nx * nx + ny * ny + nz * nz) ** 0.5)
    return (nx / length, ny / length, nz / length)


class CpuMeshPickingProvider:
    """CPU ray picker over renderer-neutral mesh/node data."""

    method = "CPU raycast"

    def __init__(
        self,
        *,
        mesh_nodes: Callable[[object], Iterable[object]] | None = None,
        world_vertices: Callable[[object], list[Vec3]] | None = None,
        projected_bounds: Callable[[object, int, int], tuple | None] | None = None,
        ray_builder: Callable[[tuple[int, int], object, int, int], tuple[object, object]] | None = None,
        point_in_triangle: Callable[[float, float, object, object, object], bool] | None = None,
        bounds_from_points: Callable[[list[Vec3]], object] | None = None,
    ) -> None:
        self.mesh_nodes = mesh_nodes
        self.world_vertices = world_vertices
        self.projected_bounds = projected_bounds
        self.ray_builder = ray_builder
        self.point_in_triangle = point_in_triangle
        self.bounds_from_points = bounds_from_points
        self.last_request: PickRequest | None = None
        self.last_hit: PickHit = PickHit(renderer_backend="cpu", diagnostic={"method": self.method})

    def pick(self, request: PickRequest, scene, camera=None) -> PickHit:
        self.last_request = request
        camera = camera if camera is not None else request.camera
        nodes = list(self._iter_nodes(scene))
        diagnostic: dict[str, object] = {
            "method": self.method,
            "candidate_count": len(nodes),
            "x": int(request.x),
            "y": int(request.y),
            "device_pixel_ratio": float(request.device_pixel_ratio),
        }
        if camera is None or request.viewport_width <= 0 or request.viewport_height <= 0:
            hit = PickHit(renderer_backend="cpu", diagnostic={**diagnostic, "reason": "invalid camera or viewport"})
            self.last_hit = hit
            return hit
        try:
            ray_origin, ray_direction = self.ray_builder(
                (int(request.x), int(request.y)),
                camera,
                int(request.viewport_width),
                int(request.viewport_height),
            ) if self.ray_builder else (None, None)
        except Exception as exc:
            ray_origin = ray_direction = None
            diagnostic["ray_error"] = str(exc)

        best = PickHit(renderer_backend="cpu", diagnostic=diagnostic)
        best_face_bounds = None
        tested_triangles = 0
        broadphase_hits = 0
        for node in nodes:
            if not request.include_hidden and bool(getattr(node, "_gr_hidden", False)):
                continue
            if not request.include_locked and bool(getattr(node, "_gr_scene_object_locked", False)):
                continue
            bounds = self._projected_node_bounds(node, request.viewport_width, request.viewport_height)
            if bounds is None:
                continue
            min_x, min_y, max_x, max_y, world_verts, projected = bounds
            if request.x < min_x or request.x > max_x or request.y < min_y or request.y > max_y:
                continue
            bb_min, bb_max = _bounds(world_verts)
            if ray_origin is not None and ray_direction is not None and not ray_intersects_aabb(ray_origin, ray_direction, bb_min, bb_max):
                continue
            broadphase_hits += 1
            for face_index, face in enumerate(getattr(node, "faces", []) or []):
                try:
                    i0, i1, i2 = int(face[0]), int(face[1]), int(face[2])
                    if min(i0, i1, i2) < 0 or max(i0, i1, i2) >= len(world_verts):
                        continue
                    v0, v1, v2 = world_verts[i0], world_verts[i1], world_verts[i2]
                    tested_triangles += 1
                    hit_t = (
                        ray_triangle_intersection(ray_origin, ray_direction, v0, v1, v2)
                        if ray_origin is not None and ray_direction is not None
                        else None
                    )
                    if hit_t is None and self.point_in_triangle is not None:
                        p0, p1, p2 = projected[i0], projected[i1], projected[i2]
                        if p0 is None or p1 is None or p2 is None:
                            continue
                        if not self.point_in_triangle(float(request.x), float(request.y), p0, p1, p2):
                            continue
                        hit_t = max(1.0e-6, (float(p0[2]) + float(p1[2]) + float(p2[2])) / 3.0)
                    if hit_t is None or hit_t >= best.distance:
                        continue
                    world_position = None
                    if ray_origin is not None and ray_direction is not None:
                        ox, oy, oz = _vec3(ray_origin)
                        dx, dy, dz = _vec3(ray_direction)
                        world_position = (ox + dx * hit_t, oy + dy * hit_t, oz + dz * hit_t)
                    best_face_bounds = self.bounds_from_points([v0, v1, v2]) if self.bounds_from_points is not None else None
                    best = PickHit(
                        hit=True,
                        object_id=id(node),
                        object_ref=node,
                        mesh_id=id(node),
                        node_id=getattr(node, "name", id(node)),
                        face_index=face_index,
                        distance=float(hit_t),
                        world_position=world_position,
                        normal=triangle_normal(v0, v1, v2),
                        screen_position=(int(request.x), int(request.y)),
                        hit_kind="mesh",
                        renderer_backend="cpu",
                        diagnostic=diagnostic,
                    )
                except Exception:
                    continue
        diagnostic["broadphase_hits"] = broadphase_hits
        diagnostic["tested_triangles"] = tested_triangles
        if best.hit:
            diagnostic["face_bounds"] = best_face_bounds
            diagnostic["result"] = str(getattr(best.object_ref, "name", best.object_id))
        else:
            diagnostic["result"] = "miss"
        self.last_hit = best
        return best

    def marquee_pick(self, request: PickRequest, scene, camera, rect) -> list[PickHit]:
        return []

    def _iter_nodes(self, scene) -> Iterable[object]:
        if self.mesh_nodes is not None:
            return self.mesh_nodes(scene)
        if scene is None:
            return []
        if hasattr(scene, "mesh_nodes"):
            return scene.mesh_nodes()
        if hasattr(scene, "all_nodes"):
            return scene.all_nodes()
        return getattr(scene, "nodes", []) or []

    def _projected_node_bounds(self, node, width: int, height: int):
        if self.projected_bounds is not None:
            return self.projected_bounds(node, int(width), int(height))
        if self.world_vertices is None:
            return None
        verts = self.world_vertices(node)
        if not verts:
            return None
        return (0, 0, int(width), int(height), verts, [None] * len(verts))


def _vec3(value) -> Vec3:
    x, y, z = tuple(value)[:3]
    return (float(x), float(y), float(z))


def _bounds(points: Iterable[Vec3]) -> tuple[Vec3, Vec3]:
    pts = [_vec3(p) for p in points]
    if not pts:
        zero = (0.0, 0.0, 0.0)
        return zero, zero
    return (
        (min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts)),
        (max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts)),
    )
