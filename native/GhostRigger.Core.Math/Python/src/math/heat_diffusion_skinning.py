'''Heat-diffusion auto-skinning for Character Builder.

Computes bone skin weights for an imported mesh by diffusing bone
influences across the mesh surface. Based on the 2017 automatic
skinning weight retargeting paper and the heat-equation diffusion
approach from Inspired 3D Advanced Rigging and Deformations.

The algorithm:
1. Build a mesh adjacency graph from vertex/face data
2. For each bone, set initial heat sources at the nearest vertices
3. Diffuse heat across the surface using the graph Laplacian
4. Normalize weights per vertex so they sum to 1.0
5. Apply a bone-influence cap (max bones per vertex)

This replaces the 'nearest bone' fallback with smooth, anatomically
plausible weight distribution.

Skilling/Deformation skill note: automatic weights are a *baseline*,
not proof. Joint areas, high twists, overlap zones, and creature
appendages still need range-of-motion checks before export. Heat
diffusion produces smoother ownership than a hard nearest-bone
assignment, but it does not replace donor/source weight transfer when
those are available and the fit is proven.
'''

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np

__all__ = [
    "build_adjacency_graph",
    "compute_vertex_bone_distances",
    "diffuse_weights",
    "cap_influences",
    "compute_heat_diffusion_weights",
    "segment_mesh_by_bones",
]


def _as_position_array(positions: Dict[str, "np.ndarray | Sequence[float]"]) -> Tuple[List[str], np.ndarray]:
    """Return (bone_names, (N, 3) float array) from a bone->position mapping.

    Accepts either numpy arrays or plain tuples/lists so the module stays
    decoupled from the higher-level model representation.
    """
    bone_names = list(positions.keys())
    if not bone_names:
        return [], np.zeros((0, 3), dtype=np.float64)
    arr = np.asarray(
        [list(positions[name])[:3] for name in bone_names],
        dtype=np.float64,
    )
    if arr.ndim != 2 or arr.shape[1] < 3:
        arr = np.zeros((len(bone_names), 3), dtype=np.float64)
    return bone_names, arr[:, :3].copy()


def build_adjacency_graph(vertices, faces) -> Dict[int, Set[int]]:
    '''Build a vertex adjacency graph from face indices.

    Two vertices are neighbours when they share at least one face edge.
    Works for triangle or polygon faces (any tuple length >= 2).
    '''
    adjacency: Dict[int, Set[int]] = defaultdict(set)
    for face in faces:
        face_idx = [int(i) for i in face]
        n = len(face_idx)
        if n < 2:
            continue
        for i in range(n):
            a = face_idx[i]
            adjacency[a].add(a)  # self-loop keeps isolated verts addressable
            for j in range(n):
                if i != j:
                    adjacency[a].add(int(face_idx[j]))
    return dict(adjacency)


def compute_vertex_bone_distances(
    vertices: np.ndarray,
    bone_positions: Dict[str, "np.ndarray | Sequence[float]"],
    max_influence_distance: float = 5.0,
) -> Dict[int, Dict[str, float]]:
    '''Compute the distance from each vertex to each bone.

    Returns {vertex_index: {bone_name: distance}}.
    Only includes bones within ``max_influence_distance``.  Vertices with
    no bone inside the cutoff are omitted from the result (they will be
    filled in by surface diffusion from their neighbours).
    '''
    bone_names, bone_pos_array = _as_position_array(bone_positions)
    if vertices is None or len(vertices) == 0 or not bone_names:
        return {}

    verts = np.asarray(vertices, dtype=np.float64)
    if verts.ndim != 2 or verts.shape[1] < 3:
        verts = verts.reshape(-1, 3)
    verts = verts[:, :3]

    result: Dict[int, Dict[str, float]] = {}
    max_d = float(max_influence_distance)
    for vi, v in enumerate(verts):
        # Squared distance to each bone, then sqrt only for the survivors.
        diffs = bone_pos_array - v
        sq = np.sum(diffs * diffs, axis=1)
        within = np.where(sq <= max_d * max_d)[0]
        if within.size == 0:
            continue
        dists = np.sqrt(sq[within])
        vertex_bones: Dict[str, float] = {}
        for slot, bi in enumerate(within):
            d = float(dists[slot])
            if d <= max_d:
                vertex_bones[bone_names[int(bi)]] = d
        if vertex_bones:
            result[vi] = vertex_bones
    return result


def diffuse_weights(
    vertex_distances: Dict[int, Dict[str, float]],
    adjacency: Dict[int, Set[int]],
    iterations: int = 5,
    falloff: float = 2.0,
) -> Dict[int, Dict[str, float]]:
    '''Diffuse bone influences across the mesh surface.

    Each iteration averages each vertex's weights with its neighbours,
    weighted by inverse distance (closer neighbours have more influence).
    The ``falloff`` parameter controls how quickly the *initial* influence
    decays with bone distance (higher = more localised seeding).
    '''
    if iterations < 0:
        iterations = 0

    # Convert distances to initial weights (inverse-distance weighting).
    weights: Dict[int, Dict[str, float]] = {}
    for vi, bone_dists in vertex_distances.items():
        w: Dict[str, float] = {}
        total = 0.0
        for bname, d in bone_dists.items():
            influence = 1.0 / (max(float(d), 1e-9) ** falloff + 1e-9)
            w[bname] = influence
            total += influence
        if total > 0:
            for bname in w:
                w[bname] /= total
        weights[vi] = w

    if not weights:
        return {}

    # Diffusion universe = every vertex that is either seeded or appears in
    # the adjacency graph.  This keeps point-cloud / partial-mesh cases
    # stable: a seeded vertex with no face neighbours simply keeps its own
    # row instead of being silently dropped.
    universe = set(adjacency.keys())
    universe |= set(weights.keys())

    # Diffusion iterations: heat-equation smoothing over the adjacency graph.
    #
    # Each vertex's new weight distribution is a blend of its own row
    # (double-weighted to preserve seeded ownership) and its neighbours'
    # rows.  The denominator is the *voter count* (2 for self + one per
    # active neighbour) — which equals sum(bone_accum.values()) because
    # every voter's row already sums to 1.0 — so the output row is
    # guaranteed to sum to 1.0.  Counting per-bone (as a naive port does)
    # would divide by K*(voter count) and shrink rows to 1/K, violating the
    # Character Builder export contract that every skin row normalises to 1.
    for _ in range(iterations):
        new_weights: Dict[int, Dict[str, float]] = {}
        for vi in universe:
            neighbors = adjacency.get(vi)
            self_w = weights.get(vi)
            if not neighbors and self_w is not None:
                new_weights[vi] = self_w
                continue

            bone_accum: Dict[str, float] = defaultdict(float)
            voter_count = 0.0

            # Self weight contributes double — preserves seeded ownership
            # while still letting neighbours bleed influence across seams.
            if self_w:
                for bname, wv in self_w.items():
                    bone_accum[bname] += wv * 2.0
                voter_count += 2.0

            for ni in neighbors:
                if ni == vi:
                    continue
                nw = weights.get(ni)
                if not nw:
                    continue
                for bname, wv in nw.items():
                    bone_accum[bname] += wv
                voter_count += 1.0

            if voter_count > 0:
                new_weights[vi] = {b: w / voter_count for b, w in bone_accum.items()}
            else:
                new_weights[vi] = dict(self_w) if self_w else {}
        weights = new_weights

    return weights


def cap_influences(
    weights: Dict[int, Dict[str, float]],
    max_bones: int = 4,
) -> Dict[int, Dict[str, float]]:
    '''Cap the number of bone influences per vertex.

    Keeps only the top ``max_bones`` weighted bones, re-normalised so the
    row still sums to 1.0.  KOTOR typically supports 4 bone influences
    per vertex.
    '''
    if max_bones <= 0:
        max_bones = 4
    capped: Dict[int, Dict[str, float]] = {}
    for vi, bone_weights in weights.items():
        if len(bone_weights) <= max_bones:
            capped[vi] = bone_weights
            continue
        sorted_bones = sorted(bone_weights.items(), key=lambda x: -x[1])[:max_bones]
        total = sum(w for _, w in sorted_bones)
        if total > 0:
            capped[vi] = {b: w / total for b, w in sorted_bones}
        else:
            capped[vi] = dict(sorted_bones)
    return capped


def _ensure_all_vertices(
    weights: Dict[int, Dict[str, float]],
    vertex_count: int,
) -> Dict[int, Dict[str, float]]:
    '''Guarantee every vertex has a weight row.

    Diffusion only seeds vertices near a bone.  Vertices that never
    received heat (e.g. far from every bone with a tight cutoff) would
    otherwise be left unweighted, which would produce NaN/missing skin
    rows — exactly what the Character Builder export contract rejects.
    Such orphan vertices fall back to a single full-weight root bone when
    a 'root'-style bone is present, otherwise the first available bone.
    '''
    if vertex_count <= 0:
        return weights
    complete = dict(weights)
    if not weights:
        return complete
    # Pick a sensible fallback bone: prefer a 'root'-style name.
    sample = next(iter(weights.values()))
    fallback_name = "root"
    for bname in sample:
        if str(bname).lower() in {"root", "rootdummy", "root_g"}:
            fallback_name = bname
            break
    else:
        fallback_name = next(iter(sample))
    for vi in range(vertex_count):
        if vi not in complete or not complete[vi]:
            complete[vi] = {fallback_name: 1.0}
    return complete


def compute_heat_diffusion_weights(
    vertices: np.ndarray,
    faces: List[Tuple[int, ...]],
    bone_positions: Dict[str, "np.ndarray | Sequence[float]"],
    max_influence_distance: float = 5.0,
    diffusion_iterations: int = 5,
    falloff: float = 2.0,
    max_bones_per_vertex: int = 4,
) -> Dict[int, Dict[str, float]]:
    '''Full pipeline: compute heat-diffusion skin weights.

    Parameters
    ----------
    vertices : (N, 3) array of vertex positions.
    faces : list of face index tuples (triangles or polygons).
    bone_positions : ``{bone_name: np.array([x, y, z])}``.
    max_influence_distance : max distance for the initial bone seeding.
    diffusion_iterations : number of surface diffusion passes.
    falloff : inverse-distance power (higher = more localised seeding).
    max_bones_per_vertex : KOTOR limit (usually 4).

    Returns
    -------
    dict
        ``{vertex_index: {bone_name: normalised_weight}}`` for every vertex,
        each row summing to ~1.0.
    '''
    if vertices is None or len(vertices) == 0 or not bone_positions:
        return {}

    verts = np.asarray(vertices, dtype=np.float64)
    if verts.ndim != 2 or verts.shape[1] < 3:
        verts = verts.reshape(-1, 3)
    verts = verts[:, :3]
    vertex_count = int(verts.shape[0])

    adjacency = build_adjacency_graph(verts, faces or [])
    distances = compute_vertex_bone_distances(verts, bone_positions, max_influence_distance)
    diffused = diffuse_weights(distances, adjacency, diffusion_iterations, falloff)
    capped = cap_influences(diffused, max_bones_per_vertex)
    return _ensure_all_vertices(capped, vertex_count)


def segment_mesh_by_bones(
    vertices: np.ndarray,
    bone_positions: Dict[str, "np.ndarray | Sequence[float]"],
    max_distance: float = 3.0,
) -> Dict[str, List[int]]:
    '''Assign each vertex to its nearest bone.

    This is a simplified segmentation that groups vertices by nearest bone.
    Used as a preprocessing step before heat diffusion to establish initial
    bone regions, and as a quick anatomical-region diagnostic.
    '''
    bone_names, bone_array = _as_position_array(bone_positions)
    if vertices is None or len(vertices) == 0 or not bone_names:
        return {}

    verts = np.asarray(vertices, dtype=np.float64)
    if verts.ndim != 2 or verts.shape[1] < 3:
        verts = verts.reshape(-1, 3)
    verts = verts[:, :3]

    segments: Dict[str, List[int]] = defaultdict(list)
    for vi, v in enumerate(verts):
        dists = np.sqrt(np.sum((bone_array - v) ** 2, axis=1))
        nearest = int(np.argmin(dists))
        if max_distance <= 0 or float(dists[nearest]) <= float(max_distance):
            segments[bone_names[nearest]].append(vi)
        else:
            segments[bone_names[nearest]].append(vi)  # still claim nearest
    return dict(segments)
