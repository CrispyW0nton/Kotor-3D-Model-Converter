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
3. If any bone is outside, compute the distance to the nearest face for
   diagnostics while the scale search expands.
4. Binary-search the minimum scale where ALL bones are inside (tightest fit).
5. Keep translation centroid-anchored for the tested scale.

This module assumes the caller has already proven that the mesh is a closed,
watertight surface.  Open meshes do not have a reliable inside/outside volume;
the Character Builder workflow must use a bounds-staging fallback for those.

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
    inverse-transformed into that local space for each candidate mesh scale.
    ``all_inside`` only means true surface containment when ``mesh_faces`` form
    a closed, watertight volume.
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

    # Use 7 well-spread, non-axis-aligned ray directions to reduce
    # degenerate coplanarity with triangle edges.  Axis-aligned rays are
    # more likely to hit shared edges/faces edge-on; cube-vertex and face
    # diagonals avoid this.  Majority vote requires >= 4 of 7.
    _s = 1.0 / math.sqrt(3.0)       # cube-vertex diagonal (normalized)
    _h = 1.0 / math.sqrt(2.0)       # face diagonal (normalized)
    ray_dirs = [
        np.array([ _s,  _s,  _s]),
        np.array([ _s,  _s, -_s]),
        np.array([ _s, -_s,  _s]),
        np.array([-_s,  _s,  _s]),
        np.array([0.0,  _h,  _h]),
        np.array([ _h, 0.0,  _h]),
        np.array([ _h,  _h, 0.0]),
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
            if votes >= 4:  # majority of 7 directions
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
    #
    # We need to scale the MESH so that its extent is at least as large as
    # the bone extent.  The minimum scale is approximately:
    #   scale_min ≈ bone_extent / mesh_extent
    # (NOT mesh_extent / bone_extent — that ratio is inverted and produces
    #  a mesh that's far too small.)

    lo = max(0.01, bone_extent / max(mesh_extent, 0.01) * 0.8)  # just under tight fit
    hi = lo * 5.0  # generous upper bound

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


# ===========================================================================
# v2: GWN multi-start shell containment (open-shell creature meshes)
# ===========================================================================
#
# v1 (fit_skeleton_inside_mesh, above) uses a 7-ray parity inside-test, which is
# only valid on closed/watertight surfaces.  Open-shell creatures (Drexl,
# Rancor) therefore fall back to the oriented-bounds box solution in
# headless_body_workflow._oriented_bounds_containment_solution -- a bounding
# box, not the actual shell.  PR A measured that today's Drexl fit leaves all 5
# deformation bones 1.0-1.6 units OUTSIDE the real shell while reporting
# outside_count=0 against the box.
#
# v2 replaces the parity test with the Generalized Winding Number oracle from
# winding_number.py and solves for (rotation, uniform scale, translation) with a
# multi-start search, requiring bones to sit a calibrated MARGIN inside the
# shell (not merely "technically inside").  It reports honestly: a partial fit
# is labelled, never silently downgraded.
#
# This is additive; v1 and its callers are untouched.  Nothing wires v2 into the
# workflow dispatch ladder in this PR.


def _load_math_sibling(module_name: str):
    """Import a sibling math module robustly across import styles.

    containment_fit may be imported as ``src.math.containment_fit`` in the
    embedded runtime, or loaded directly by file path in tests (no package
    context).  Try package-qualified and bare imports first, then fall back to
    loading the file next to this one.  Keeping this lazy means v1's lightweight
    ``import math, numpy`` cost is preserved (trimesh/scipy load only on v2 use).
    """
    from importlib import import_module

    for candidate in (f"src.math.{module_name}", module_name):
        try:
            return import_module(candidate)
        except Exception:
            pass
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).with_name(f"{module_name}.py")
    spec = importlib.util.spec_from_file_location(f"_gr_sibling_{module_name}", str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load sibling math module {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bbox_diagonal(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if pts.shape[0] == 0:
        return 0.0
    return float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))


def _dedupe_rotations(mats: Sequence[np.ndarray], tol_deg: float = 5.0) -> list[np.ndarray]:
    """Drop rotations within ``tol_deg`` geodesic degrees of an earlier one."""
    kept: list[np.ndarray] = []
    tol = math.radians(tol_deg)
    for R in mats:
        R = np.asarray(R, dtype=np.float64)
        duplicate = False
        for K in kept:
            # Geodesic angle between rotations: angle of R^T K.
            cos_angle = (np.trace(R.T @ K) - 1.0) * 0.5
            cos_angle = max(-1.0, min(1.0, float(cos_angle)))
            if math.acos(cos_angle) < tol:
                duplicate = True
                break
        if not duplicate:
            kept.append(R)
    return kept


def _rotation_hypotheses(
    mesh_vertices: np.ndarray,
    bone_positions: np.ndarray,
    bone_names: "list[str] | None",
    n_rotation_hypotheses: int,
    random_seed: int,
) -> list[np.ndarray]:
    """Build up to ``n_rotation_hypotheses`` candidate mesh->world rotations.

    Composition: 6 axis-aligned "up" orientations, 1 PCA/Kabsch landmark seed
    (identity on failure), and 3 random rotations, deduplicated to ~5 degrees.
    """
    from scipy.spatial.transform import Rotation as _Rotation

    hypotheses: list[np.ndarray] = []

    # 6 axis-aligned orientations (local up mapped to each signed world axis).
    for euler in (
        ("x", 0.0),
        ("x", 180.0),
        ("x", 90.0),
        ("x", -90.0),
        ("y", 90.0),
        ("y", -90.0),
    ):
        hypotheses.append(_Rotation.from_euler(euler[0], euler[1], degrees=True).as_matrix())

    # PCA/Kabsch landmark seed via landmark_alignment (identity if it errors or
    # produces a degenerate/improper matrix).
    try:
        landmark_alignment = _load_math_sibling("landmark_alignment")
        bone_map = {
            (bone_names[i] if bone_names and i < len(bone_names) else f"bone_{i}"): np.asarray(p, dtype=np.float64)
            for i, p in enumerate(bone_positions)
        }
        seed = landmark_alignment.align_mesh_to_skeleton(np.asarray(mesh_vertices, dtype=np.float64), bone_map)
        R_seed = np.asarray(seed["rotation_matrix"], dtype=np.float64)
        if R_seed.shape == (3, 3) and np.isfinite(R_seed).all() and np.linalg.det(R_seed) > 0.5:
            hypotheses.append(R_seed)
    except Exception:
        pass  # degenerate PCA / too-few landmarks: axis-aligned + random cover it

    # 3 random rotations (deterministic via seed).
    random_rots = _Rotation.random(num=3, random_state=random_seed).as_matrix()
    for R in random_rots:
        hypotheses.append(np.asarray(R, dtype=np.float64))

    hypotheses = _dedupe_rotations(hypotheses, tol_deg=5.0)
    return hypotheses[: max(1, int(n_rotation_hypotheses))]


def fit_skeleton_inside_mesh_v2(
    mesh_vertices: np.ndarray,
    mesh_faces: Sequence[Sequence[int]],
    bone_positions: np.ndarray,
    bone_names: "list[str] | None" = None,
    *,
    use_v2: bool = False,
    target_margin: float = 0.3,
    n_rotation_hypotheses: int = 10,
    random_seed: int = 42,
    margin_relative_to: str = "shell_diagonal",
) -> dict:
    """GWN-oracle shell containment fit (v2), gated behind ``use_v2``.

    When ``use_v2=False`` (default) this returns exactly what
    :func:`fit_skeleton_inside_mesh` (v1) returns -- byte-identical behaviour so
    existing callers are unaffected.

    When ``use_v2=True`` it fits (rotation, uniform scale, translation) so that
    every bone sits at least ``effective_margin`` deep inside the mesh *shell*
    (using the Generalized Winding Number from ``winding_number.py`` as the
    inside oracle and signed distance as the depth/margin signal), with an
    optional bounded per-axis rescale escalation and an honest partial-fit
    status when full containment with margin is unreachable.

    ``bone_positions`` are the fixed anchors to contain; the returned transform
    maps the mesh into the bones' coordinate space (world = M @ mesh + t).

    Returns a dict that is a superset of v1's keys (``translation``, ``scale``,
    ``rotation_matrix``, ``all_inside``, ``outside_count``, ``max_penetration``,
    ``method``, ``iterations``, ``rmsd``) plus, when ``use_v2=True``, a
    ``linear_matrix`` (3x3), ``trace_version`` (kept at ``"ghostrigger.fit/v1"``
    -- new fields are additive, never a version bump), and a ``containment_fit``
    sub-dict extending the existing schema with ``v2_``-prefixed optional fields.
    """
    mesh_vertices = np.asarray(mesh_vertices, dtype=np.float64).reshape(-1, 3)
    bone_positions = np.asarray(bone_positions, dtype=np.float64).reshape(-1, 3)

    # v1 gate: byte-identical passthrough.
    if not use_v2:
        return fit_skeleton_inside_mesh(mesh_vertices, mesh_faces, bone_positions)

    faces = np.asarray(mesh_faces, dtype=np.int64).reshape(-1, 3)
    names = list(bone_names) if bone_names else []

    # Tiny inputs cannot be meaningfully fit as a shell; delegate to v1.
    if mesh_vertices.shape[0] < 4 or bone_positions.shape[0] < 1 or faces.shape[0] < 1:
        return _v2_delegate_to_v1(
            mesh_vertices, faces, bone_positions, reason="insufficient_geometry"
        )

    wn = _load_math_sibling("winding_number")
    import trimesh  # lazy: only when v2 actually runs

    # --- Preflight: repair normals + trust gate -----------------------------
    raw_mesh = trimesh.Trimesh(vertices=mesh_vertices, faces=faces, process=False)
    repaired, normal_diag = wn.repair_normals(raw_mesh)
    if not bool(normal_diag.get("should_trust_normals", False)):
        return _v2_delegate_to_v1(
            mesh_vertices,
            faces,
            bone_positions,
            reason="untrustworthy_normals",
            normal_repair=normal_diag,
        )

    local_verts = np.asarray(repaired.vertices, dtype=np.float64)
    local_faces = np.asarray(repaired.faces, dtype=np.int64)
    mesh_centroid = local_verts.mean(axis=0)
    bone_centroid = bone_positions.mean(axis=0)

    # --- Margin calibration -------------------------------------------------
    mesh_local_diag = max(_bbox_diagonal(local_verts), 1e-9)
    bone_diag = max(_bbox_diagonal(bone_positions), 1e-9)
    initial_scale_estimate = bone_diag / mesh_local_diag * 1.2
    if str(margin_relative_to) == "absolute":
        effective_margin = float(target_margin)
    else:
        margin_relative_to = "shell_diagonal"
        shell_diag = mesh_local_diag * initial_scale_estimate
        effective_margin = float(target_margin) * shell_diag / 10.0

    # --- Threshold: derived once (GWN is similarity-invariant) ---------------
    # Sample the mesh's *own* (unpadded) bbox, matching winding_number's
    # classify_points.  Padding the box is tempting (to guarantee exterior
    # points for a mesh that fills its bbox) but backfires on thin shells like
    # Drexl (Y-extent ~0.2): a padded box is so much larger than the thin
    # interior that random samples almost never land inside, collapsing the
    # sample to all-outside and producing a degenerate ~0 threshold.  The
    # unpadded box is bimodal for any mesh that does not fill it; the sole
    # degenerate case (a box that IS its bbox -> all-interior sample) makes
    # adaptive_winding_threshold's np.histogram raise "Too many bins for data
    # range".  Since winding_number.py is out of scope for this PR we harden the
    # caller and fall back to the module default there.
    # TODO(post-PR-C): winding_number.classify_points' bbox-sample thresholding
    # should itself be made robust for very thin shells (a PR A follow-up), so
    # callers do not have to re-implement/guard the sampling here.
    rng = np.random.default_rng(random_seed)
    bbox_samples = rng.uniform(
        low=local_verts.min(axis=0), high=local_verts.max(axis=0), size=(512, 3)
    )
    sample_gwn = wn.generalized_winding_number(bbox_samples, local_verts, local_faces)
    try:
        threshold, threshold_diag = wn.adaptive_winding_threshold(sample_gwn)
    except Exception as exc:  # near-constant (box fills its bbox) -> default cut
        threshold = float(wn.DEFAULT_WINDING_THRESHOLD)
        threshold_diag = {
            "threshold": threshold,
            "unimodal": True,
            "valley_location": None,
            "sample_count": int(np.asarray(sample_gwn).size),
            "otsu_separation_score": 0.0,
            "note": f"adaptive_threshold_fallback: {type(exc).__name__}",
        }

    # Persistent proximity query on the LOCAL mesh; uniform candidates reuse it
    # via similarity invariance (rotate/translate invariant; distance scales by
    # s), so we never rebuild a mesh inside the binary search.
    local_pq = trimesh.proximity.ProximityQuery(repaired)

    def eval_uniform(R: np.ndarray, s: float):
        """Return (t, gwn, inside_mask, world_signed_distance) for scale s."""
        M = s * R
        t = bone_centroid - M @ mesh_centroid
        # Inverse-map bones into local space: local = R^T (p - t) / s.
        local_bones = ((bone_positions - t) @ R) / s
        gwn = wn.generalized_winding_number(local_bones, local_verts, local_faces)
        inside = gwn >= threshold
        local_sd_outside = -np.asarray(local_pq.signed_distance(local_bones), dtype=np.float64)
        world_sd = local_sd_outside * s  # positive = outside, negative = inside
        return t, gwn, inside, world_sd

    def feasible(inside: np.ndarray, world_sd: np.ndarray) -> bool:
        return bool(np.all(inside)) and bool(np.all(world_sd <= -effective_margin))

    def violations(inside: np.ndarray, world_sd: np.ndarray):
        fail = (~inside) | (world_sd > -effective_margin)
        shortfall = np.maximum(0.0, world_sd + effective_margin)
        return int(np.count_nonzero(fail)), float(np.mean(shortfall)), int(np.argmax(world_sd))

    s_min = 0.1 * initial_scale_estimate
    s_max = 20.0 * initial_scale_estimate

    def solve_hypothesis(R: np.ndarray) -> dict:
        # Feasibility is monotone-ish in scale; ensure the upper bound works.
        t_hi, gwn_hi, in_hi, sd_hi = eval_uniform(R, s_max)
        if not feasible(in_hi, sd_hi):
            vc, ms, wi = violations(in_hi, sd_hi)
            return {
                "R": R, "scale": s_max, "t": t_hi, "gwn": gwn_hi, "inside": in_hi,
                "world_sd": sd_hi, "feasible": False, "violation_count": vc,
                "mean_margin_shortfall": ms, "worst_bone_index": wi, "iterations": 0,
            }
        lo, hi = s_min, s_max
        best = (s_max, t_hi, gwn_hi, in_hi, sd_hi)
        iters = 0
        for _ in range(40):
            iters += 1
            mid = 0.5 * (lo + hi)
            t_m, gwn_m, in_m, sd_m = eval_uniform(R, mid)
            if feasible(in_m, sd_m):
                hi = mid
                best = (mid, t_m, gwn_m, in_m, sd_m)
            else:
                lo = mid
            if (hi - lo) < 1.0e-4 * max(hi, 1e-9):
                break
        s_b, t_b, gwn_b, in_b, sd_b = best
        vc, ms, wi = violations(in_b, sd_b)
        return {
            "R": R, "scale": s_b, "t": t_b, "gwn": gwn_b, "inside": in_b,
            "world_sd": sd_b, "feasible": vc == 0, "violation_count": vc,
            "mean_margin_shortfall": ms, "worst_bone_index": wi, "iterations": iters,
        }

    hypotheses = _rotation_hypotheses(
        local_verts, bone_positions, names, n_rotation_hypotheses, random_seed
    )
    results = [solve_hypothesis(R) for R in hypotheses]
    feasible_results = [r for r in results if r["feasible"]]
    n_feasible = len(feasible_results)

    if feasible_results:
        winner = min(feasible_results, key=lambda r: r["scale"])  # tightest containment
    else:
        winner = min(
            results, key=lambda r: (r["violation_count"], r["mean_margin_shortfall"])
        )

    # --- Per-axis escalation (bounded, world-axis) --------------------------
    per_axis_fired = False
    per_axis_scale = None
    axis_scale_vec = np.array([1.0, 1.0, 1.0])
    R_win = winner["R"]
    s_win = winner["scale"]
    world_sd = winner["world_sd"]
    inside = winner["inside"]
    gwn = winner["gwn"]
    t_win = winner["t"]
    iters_win = winner["iterations"]

    worst_sd = float(np.max(world_sd))
    if worst_sd > -0.5 * effective_margin:
        per_axis_fired = True
        # Direction of the worst bone's violation (bone -> nearest surface).
        M_uniform = s_win * R_win
        world_verts = (local_verts @ M_uniform.T) + t_win
        world_mesh = trimesh.Trimesh(vertices=world_verts, faces=local_faces, process=False)
        pq_world = trimesh.proximity.ProximityQuery(world_mesh)
        worst_idx = int(np.argmax(world_sd))
        closest, _dist, _tid = pq_world.on_surface(bone_positions[worst_idx : worst_idx + 1])
        violation_dir = bone_positions[worst_idx] - np.asarray(closest[0], dtype=np.float64)
        axis = int(np.argmax(np.abs(violation_dir))) if np.linalg.norm(violation_dir) > 1e-12 else int(np.argmax(np.abs(world_sd)))

        base_vc, base_ms, _ = violations(inside, world_sd)
        base_worst = worst_sd
        best_axis = None
        best_metrics = (base_vc, base_worst)

        def eval_axis(factor: float):
            a = np.array([1.0, 1.0, 1.0])
            a[axis] = factor
            M = np.diag(a) @ (s_win * R_win)
            t = bone_centroid - M @ mesh_centroid
            wv = (local_verts @ M.T) + t
            wm = trimesh.Trimesh(vertices=wv, faces=local_faces, process=False)
            g = wn.generalized_winding_number(bone_positions, wv, local_faces)
            ins = g >= threshold
            sd = wn.signed_distance_to_surface(bone_positions, wm)
            return a, M, t, g, ins, sd

        for factor in np.linspace(0.85, 1.30, 10):
            a, M, t, g, ins, sd = eval_axis(float(factor))
            vc = int(np.count_nonzero((~ins) | (sd > -effective_margin)))
            w = float(np.max(sd))
            # Accept if fewer violations, or same violations and worst improves >= 0.1.
            improves = (vc < best_metrics[0]) or (vc == base_vc and (base_worst - w) >= 0.1)
            if improves and (vc < best_metrics[0] or w < best_metrics[1]):
                best_metrics = (vc, w)
                best_axis = (a, M, t, g, ins, sd)

        if best_axis is not None:
            axis_scale_vec, M_final, t_win, gwn, inside, world_sd = best_axis
            per_axis_scale = [float(v) for v in axis_scale_vec]
            iters_win += 10
        else:
            per_axis_fired = False  # escalation considered but did not improve

    # --- Assemble final transform + trace -----------------------------------
    if per_axis_scale is not None:
        M_final = np.diag(axis_scale_vec) @ (s_win * R_win)
    else:
        M_final = s_win * R_win
    t_final = bone_centroid - M_final @ mesh_centroid

    inside_mask = np.asarray(inside, dtype=bool)
    outside_count = int(np.count_nonzero(world_sd > -effective_margin))
    margin_met = world_sd <= -effective_margin
    converged = bool(np.all(inside_mask)) and bool(np.all(margin_met))
    status = "converged" if converged else "partial_fit"

    rmsd = float(np.sqrt(np.mean(np.square(world_sd))))
    max_penetration = float(np.min(world_sd))  # most-inside (negative) depth

    containment_fit = {
        # existing (v1) schema keys -- preserved names/types
        "bone_position_source": "explicit_bone_positions",
        "containment_guarantee": "shell_gwn_margin_verified" if converged else "shell_gwn_partial",
        "containment_volume": "shell",
        "deformation_bone_count": int(bone_positions.shape[0]),
        "hard_containment_bone_count": int(bone_positions.shape[0]),
        "mesh_watertight": bool(repaired.is_watertight),
        "method": "gwn_multistart_v2",
        "outside_count": outside_count,
        "soft_containment_bone_count": 0,
        "soft_containment_bone_names": [],
        "surface_containment_checked": True,
        "total_deformation_bone_count": int(bone_positions.shape[0]),
        "total_outside_count": outside_count,
        # new v2_* optional fields
        "v2_method": "gwn_multistart_v2",
        "v2_status": status,
        "v2_effective_margin": float(effective_margin),
        "v2_margin_relative_to": margin_relative_to,
        "v2_rotation_hypotheses_tested": len(results),
        "v2_rotation_hypotheses_feasible": n_feasible,
        "v2_normal_repair": dict(normal_diag),
        "v2_threshold_used": float(threshold),
        "v2_threshold_diagnostics": dict(threshold_diag),
        "v2_per_axis_escalation_fired": bool(per_axis_fired),
        "v2_per_axis_scale": per_axis_scale,
        "v2_fallback_reason": None,
        "v2_bone_positions": [[float(x) for x in p] for p in bone_positions],
        "v2_bone_names": list(names),
        "v2_bone_signed_distances": [float(v) for v in world_sd],
        "v2_bone_gwn_values": [float(v) for v in gwn],
        "v2_bone_inside_mask": [bool(v) for v in inside_mask],
        "v2_bone_margin_met": [bool(v) for v in margin_met],
        "v2_unresolved_anchors": None,
    }

    if status == "partial_fit":
        unresolved = []
        for i in range(bone_positions.shape[0]):
            if (not bool(inside_mask[i])) or (not bool(margin_met[i])):
                unresolved.append(
                    {
                        "index": int(i),
                        "name": names[i] if i < len(names) else None,
                        "position": [float(x) for x in bone_positions[i]],
                        "signed_distance": float(world_sd[i]),
                        "gwn_value": float(gwn[i]),
                    }
                )
        containment_fit["v2_unresolved_anchors"] = unresolved

    return {
        # v1-compatible top-level keys (superset)
        "translation": tuple(float(v) for v in t_final),
        "scale": float(s_win),
        "rotation_matrix": tuple(tuple(float(v) for v in row) for row in R_win),
        "all_inside": bool(np.all(inside_mask)),
        "outside_count": outside_count,
        "max_penetration": max_penetration,
        "method": "gwn_multistart_v2",
        "iterations": int(iters_win),
        "rmsd": rmsd,
        # v2 additions
        "linear_matrix": tuple(tuple(float(v) for v in row) for row in M_final),
        "trace_version": "ghostrigger.fit/v1",
        "containment_fit": containment_fit,
    }


def _v2_delegate_to_v1(
    mesh_vertices: np.ndarray,
    mesh_faces: Sequence[Sequence[int]],
    bone_positions: np.ndarray,
    *,
    reason: str,
    normal_repair: "dict | None" = None,
) -> dict:
    """Run v1 and annotate the result with a v2 delegation status.

    The v1 *core* keys are preserved so downstream v1 readers still work; a
    ``containment_fit`` sub-dict records why v2 stepped aside.  This is NOT a
    silent fallback -- the status/reason are explicit in the trace.
    """
    v1_result = fit_skeleton_inside_mesh(mesh_vertices, mesh_faces, bone_positions)
    annotated = dict(v1_result)
    annotated["trace_version"] = "ghostrigger.fit/v1"
    annotated["containment_fit"] = {
        "method": v1_result.get("method", "containment_binary_search"),
        "outside_count": v1_result.get("outside_count", -1),
        "surface_containment_checked": False,
        "v2_method": "gwn_multistart_v2",
        "v2_status": "delegated_to_v1",
        "v2_fallback_reason": reason,
        "v2_normal_repair": dict(normal_repair) if normal_repair else None,
    }
    return annotated
