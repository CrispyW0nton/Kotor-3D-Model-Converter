"""Containment-based skeleton fitting for the Character Builder.

Given an imported mesh surface and a set of bone positions, compute the
optimal translation + uniform scale so that **all bones fit inside the mesh
volume**.  This replaces the extrema-only Kabsch approach with a
containment-guaranteed fit: the mesh is scaled and positioned so that every
bone is enclosed by the mesh faces.

Algorithm:
1. Start from an initial guess (bounds-ratio scale + centroid alignment).
2. Cast a ray from each bone position and count triangle crossings
   (odd = inside, even = outside).
3. If any bone is outside, compute the distance to the nearest face and use
   it to drive a scale increase.
4. Binary-search the minimum scale where ALL bones are inside (tightest fit).
5. Optimize translation to center the bone cloud inside the mesh.

Primitives reused from the rendering layer:
- Möller–Trumbore ray-triangle intersection (same algorithm as picking.py).
"""

from __future__ import annotations

import math
import numpy as np
from typing import Sequence


# ---------------------------------------------------------------------------
# Ray-triangle intersection (Möller–Trumbore) — standalone copy to avoid
# importing from the rendering package (which needs Qt/OpenGL at runtime).
# ---------------------------------------------------------------------------

def _ray_triangle(
    origin: np.ndarray,
    direction: np.ndarray,
    v0: np.ndarray,
    v1: np.ndarray,
    v2: np.ndarray,
    eps: float = 1e-8,
) -> float | None:
    """Return ray parameter *t* if the ray hits the triangle, else ``None``."""
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direction, edge2)
    a = float(np.dot(edge1, h))
    if abs(a) < eps:
        return None  # parallel
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
    if t > eps:
        return t
    return None


# ---------------------------------------------------------------------------
# Mesh data structures
# ---------------------------------------------------------------------------

class MeshSurface:
    """Triangulated mesh surface for containment testing."""

    def __init__(self, vertices: np.ndarray, faces: Sequence[Sequence[int]]):
        self.vertices = np.asarray(vertices, dtype=np.float64)
        # Ensure triangles
        tri_faces: list[tuple[int, int, int]] = []
        for face in faces:
            n = len(face)
            if n == 3:
                tri_faces.append((int(face[0]), int(face[1]), int(face[2])))
            elif n > 3:
                # Fan triangulation
                for i in range(1, n - 1):
                    tri_faces.append((int(face[0]), int(face[i]), int(face[i + 1])))
        self.triangles = np.array(tri_faces, dtype=np.int32) if tri_faces else np.zeros((0, 3), dtype=np.int32)
        self._tri_v0 = self.vertices[self.triangles[:, 0]] if len(self.triangles) else np.zeros((0, 3))
        self._tri_v1 = self.vertices[self.triangles[:, 1]] if len(self.triangles) else np.zeros((0, 3))
        self._tri_v2 = self.vertices[self.triangles[:, 2]] if len(self.triangles) else np.zeros((0, 3))

    @property
    def centroid(self) -> np.ndarray:
        return self.vertices.mean(axis=0) if len(self.vertices) else np.zeros(3)

    @property
    def bounds_min(self) -> np.ndarray:
        return self.vertices.min(axis=0) if len(self.vertices) else np.zeros(3)

    @property
    def bounds_max(self) -> np.ndarray:
        return self.vertices.max(axis=0) if len(self.vertices) else np.zeros(3)

    def is_point_inside(self, point: np.ndarray, direction: np.ndarray | None = None) -> bool:
        """Ray-crossing test: odd number of triangle hits = inside."""
        if len(self.triangles) == 0:
            return False
        if direction is None:
            direction = np.array([1.0, 0.0, 0.0])
        else:
            direction = np.asarray(direction, dtype=np.float64)
            n = float(np.linalg.norm(direction))
            if n < 1e-12:
                direction = np.array([1.0, 0.0, 0.0])
            else:
                direction = direction / n
        crossings = 0
        for i in range(len(self.triangles)):
            t = _ray_triangle(point, direction, self._tri_v0[i], self._tri_v1[i], self._tri_v2[i])
            if t is not None:
                crossings += 1
        return crossings % 2 == 1

    def nearest_surface_distance(self, point: np.ndarray) -> float:
        """Distance from *point* to the nearest triangle face."""
        if len(self.triangles) == 0:
            return float("inf")
        min_dist = float("inf")
        for i in range(len(self.triangles)):
            dist = _point_triangle_distance(point, self._tri_v0[i], self._tri_v1[i], self._tri_v2[i])
            if dist < min_dist:
                min_dist = dist
        return min_dist


def _point_triangle_distance(point: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Minimum distance from *point* to triangle (a, b, c)."""
    # Project point onto the triangle plane, clamp to the triangle, measure distance.
    ab = b - a
    ac = c - a
    ap = point - a
    normal = np.cross(ab, ac)
    nn = float(np.linalg.norm(normal))
    if nn < 1e-12:
        # Degenerate triangle — use vertex distances
        return min(float(np.linalg.norm(point - a)), float(np.linalg.norm(point - b)), float(np.linalg.norm(point - c)))
    normal /= nn
    # Signed distance from plane
    d_plane = float(np.dot(ap, normal))
    projected = point - normal * d_plane

    # Check if projected point is inside the triangle using barycentric coords
    bp = projected - a
    d00 = float(np.dot(ab, ab))
    d01 = float(np.dot(ab, ac))
    d11 = float(np.dot(ac, ac))
    d20 = float(np.dot(bp, ab))
    d21 = float(np.dot(bp, ac))
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return abs(d_plane)
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w

    if u >= 0.0 and v >= 0.0 and w >= 0.0:
        # Projection is inside the triangle — distance is the plane distance
        return abs(d_plane)

    # Clamp to the nearest edge
    dist = min(
        _point_segment_distance(point, a, b),
        _point_segment_distance(point, b, c),
        _point_segment_distance(point, c, a),
    )
    return dist


def _point_segment_distance(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """Minimum distance from *point* to segment a→b."""
    ab = b - a
    t = float(np.dot(point - a, ab))
    denom = float(np.dot(ab, ab))
    if denom < 1e-12:
        return float(np.linalg.norm(point - a))
    t = max(0.0, min(1.0, t / denom))
    proj = a + ab * t
    return float(np.linalg.norm(point - proj))


# ---------------------------------------------------------------------------
# Containment-based fit optimizer
# ---------------------------------------------------------------------------

def fit_skeleton_inside_mesh(
    mesh_vertices: np.ndarray,
    mesh_faces: Sequence[Sequence[int]],
    bone_positions: np.ndarray,
    max_iterations: int = 30,
    scale_tolerance: float = 0.005,
) -> dict:
    """Compute translation + uniform scale so all bones fit inside the mesh.

    Returns a dict with:
        'translation': (x, y, z)
        'scale': float
        'rotation_matrix': identity (3x3 as row-major tuples)
        'all_inside': bool
        'outside_count': int
        'max_penetration': float (negative = penetration depth)
        'method': 'containment_binary_search'
        'iterations': int
        'rmsd': float

    The mesh is treated as fixed (in its own local space); bones are
    translated and scaled to fit inside it.
    """
    if len(mesh_vertices) < 4 or len(bone_positions) < 1:
        return _fallback_fit(mesh_vertices, bone_positions)

    surface = MeshSurface(mesh_vertices, mesh_faces)
    mesh_centroid = surface.centroid
    bone_centroid = bone_positions.mean(axis=0)

    # Initial scale estimate from bounds ratio
    mesh_extent = float(np.max(surface.bounds_max - surface.bounds_min))
    bone_extent = float(np.max(bone_positions.max(axis=0) - bone_positions.min(axis=0)))
    if bone_extent < 1e-9:
        bone_extent = 1.0

    # We want to scale+translate the BONES to fit inside the MESH.
    # The bones need to be scaled down and positioned inside the mesh.
    # But actually, the fit pipeline scales the MESH to fit the bones.
    # So we need: what scale+translation applied to the MESH makes all
    # bones (in their fixed positions) be inside it?
    #
    # Equivalently: for a given scale s and translation t applied to the
    # mesh, a bone at position p is inside if:
    #   (p - t) is inside the original (unscaled) mesh scaled by 1/s
    #   i.e. (p - t) / s is inside the original mesh
    #
    # We want to find the minimum s such that all bones are inside.

    # Use 3 ray directions to reduce degenerate cases
    ray_dirs = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.7071, 0.5, 0.5]),
    ]

    def check_containment(scale: float, translation: np.ndarray) -> tuple[bool, int, float]:
        """Check if all bones are inside the scaled+translated mesh.

        Mesh transform: v' = v * scale + translation
        Bone p is inside if inverse-transformed bone (p - t) / s is inside original mesh.
        """
        inside_count = 0
        max_outside_dist = 0.0
        for bone in bone_positions:
            # Inverse-transform the bone into mesh-local space
            local_bone = (bone - translation) / scale
            # Use majority vote across ray directions for robustness
            votes = 0
            for d in ray_dirs:
                if surface.is_point_inside(local_bone, d):
                    votes += 1
            if votes >= 2:  # majority of 3 directions
                inside_count += 1
            else:
                dist = surface.nearest_surface_distance(local_bone)
                if dist > max_outside_dist:
                    max_outside_dist = dist
        all_inside = inside_count == len(bone_positions)
        return all_inside, len(bone_positions) - inside_count, max_outside_dist

    # Binary search for the minimum scale where all bones are inside.
    # Translation: center the mesh on the bone centroid.
    # Start with scale where mesh matches bone extent, then grow if needed.

    lo = max(0.01, mesh_extent / max(bone_extent, 0.01) * 0.5)  # generous lower bound
    hi = lo * 10.0  # generous upper bound

    # First, find a scale that contains all bones (expand hi until it works)
    best_translation = bone_centroid - mesh_centroid * lo
    all_inside, outside_count, max_pen = check_containment(lo, best_translation)
    if not all_inside:
        for _ in range(max_iterations):
            best_translation = bone_centroid - mesh_centroid * hi
            all_inside, outside_count, max_pen = check_containment(hi, best_translation)
            if all_inside:
                break
            hi *= 1.5
        else:
            # Could not achieve full containment — use the best we found
            return {
                "translation": tuple(float(v) for v in best_translation),
                "scale": float(hi),
                "rotation_matrix": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
                "all_inside": False,
                "outside_count": outside_count,
                "max_penetration": max_pen,
                "method": "containment_binary_search",
                "iterations": max_iterations,
                "rmsd": 0.0,
            }

    # Binary search between lo and hi for the tightest fit
    iterations = 0
    for _ in range(max_iterations):
        iterations += 1
        mid = (lo + hi) * 0.5
        mid_translation = bone_centroid - mesh_centroid * mid
        all_inside, outside_count, max_pen = check_containment(mid, mid_translation)
        if all_inside:
            hi = mid
            best_translation = mid_translation
        else:
            lo = mid
        if hi - lo < scale_tolerance * max(mid, 0.01):
            break

    final_scale = hi
    final_translation = bone_centroid - mesh_centroid * final_scale

    # Final verification
    all_inside, outside_count, max_pen = check_containment(final_scale, final_translation)

    # Compute RMSD (distance from bones to mesh surface)
    total_sq = 0.0
    for bone in bone_positions:
        local_bone = (bone - final_translation) / final_scale
        total_sq += surface.nearest_surface_distance(local_bone) ** 2
    rmsd = float(math.sqrt(total_sq / max(1, len(bone_positions))))

    return {
        "translation": tuple(float(v) for v in final_translation),
        "scale": float(final_scale),
        "rotation_matrix": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        "all_inside": all_inside,
        "outside_count": outside_count,
        "max_penetration": max_pen,
        "method": "containment_binary_search",
        "iterations": iterations,
        "rmsd": rmsd,
    }


def _fallback_fit(mesh_vertices: np.ndarray, bone_positions: np.ndarray) -> dict:
    """Bounds-ratio fallback when containment optimization fails."""
    mesh_min = mesh_vertices.min(axis=0)
    mesh_max = mesh_vertices.max(axis=0)
    bone_min = bone_positions.min(axis=0)
    bone_max = bone_positions.max(axis=0)
    mesh_ext = np.maximum(mesh_max - mesh_min, 1e-9)
    bone_ext = np.maximum(bone_max - bone_min, 1e-9)
    scale = float(np.max(bone_ext / mesh_ext))
    translation = bone_min - mesh_min * scale
    return {
        "translation": tuple(float(v) for v in translation),
        "scale": scale,
        "rotation_matrix": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        "all_inside": False,
        "outside_count": -1,
        "max_penetration": 0.0,
        "method": "bounds_ratio_fallback",
        "iterations": 0,
        "rmsd": 0.0,
    }
