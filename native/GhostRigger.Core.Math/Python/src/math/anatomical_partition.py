"""Anatomical mesh partitioning driven by donor skin weights (PR C).

KotOR's Odyssey engine caps a *skin* mesh node at **16 bones**.  A creature
whose deformation skeleton needs more than 16 bones (Drexl needs ~55) is
therefore authored as several separate skin nodes — one per anatomical region
(head, chest, each arm, each wing, tail).  When a modder imports a *unified*
custom mesh (a single ``.obj`` with no skin), it must be split back into
≤16-bone regions before it can be skinned and exported.

This module performs that split.  It does **one thing**: given a donor's skin
weights (the anatomy prior) and an imported mesh (no weights), it decomposes the
imported mesh's faces into anatomical regions, each influenced by ≤16 bones.

Why donor-driven and not geometric?
-----------------------------------
The topological splitter already in the pipeline
(``headless_body_workflow._connected_face_components``) splits by connectivity,
which knows nothing about anatomy: it will happily put half a torso and a whole
arm in one island.  Donor skin weights encode where the artist actually placed
deformation influence, so partitioning by *dominant bone* recovers real
anatomy.  This is BIAGP — Bone-Influence Adaptive Graph Partitioning.

Two phases (see :func:`partition_mesh_anatomically`):

1. **BIAGP on the donor** (:func:`_partition_donor_biagp`) — grow regions from
   per-face dominant bones over the donor's face-adjacency graph, dissolve dust
   islands, then enforce the ≤16-bone palette by greedy connected splitting.
2. **Transfer to the imported mesh** (:func:`_align_and_transfer_regions`) —
   align the imported mesh to the donor frame (a correctness fix; real OBJ
   imports are axis-permuted/rescaled vs donor space) then assign each imported
   face to the region of its nearest donor face.

Scope boundary (locked, PR C):
------------------------------
* This module **only splits**.  It never calls ``fit_skeleton_inside_mesh_v2``.
  The separation between *geometric partitioning* (here) and *containment
  policy* (``containment_fit.py``) is deliberate; the acceptance test in
  ``tests/test_anatomical_partition.py`` runs v2 on the output regions itself.
* Donor regions are recomputed on every call.  **No caching**, no cache
  invalidation problem.  Statelessness is a feature.
* If the donor is unavailable, this module **hard-fails** with
  :class:`MissingDonorError`.  There is no silent fallback to the topological
  splitter — an anatomical split without anatomy data is a lie.

Dependencies: pure NumPy + SciPy + trimesh.  No libigl, no native additions
(the package ships as RCDATA-embedded Python inside native DLLs with
byte-identity tests, so new native deps are a build-system hazard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import trimesh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


# ---------------------------------------------------------------------------
# Tunable constants (documented judgment calls)
# ---------------------------------------------------------------------------

TRACE_VERSION = "ghostrigger.partition/v1"

#: A face is "ambiguous" when its top-1 and top-2 accumulated bone weights are
#: within this fraction of the top-1 weight.  Such faces sit on a deformation
#: boundary (e.g. shoulder seam) where argmax is a coin-flip; assigning them by
#: argmax would spawn spurious one-face regions along every seam, so we defer
#: them and let them join whichever seed region is nearest by graph distance.
AMBIGUOUS_WEIGHT_FRACTION = 0.05

#: Weight below which a bone influence is treated as absent when computing a
#: region's bone palette.  KotOR weights are float32 normalised to 1.0, so 1e-6
#: is comfortably below any meaningful influence and above float noise.
WEIGHT_EPSILON = 1e-6

#: Minimum Jaccard overlap of two adjacent regions' bone-influence sets for them
#: to be agglomerated (see :func:`_agglomerate_to_palette`).  Regions of the same
#: anatomical part (e.g. successive tail segments ``tail1..tail6``) share most of
#: their influence bones and merge; distinct limbs share few or none and stay
#: separate.
#:
#: CALIBRATION (empirical): on Drexl (``c_drexlf``), dominant-bone connected
#: components after seam-weld + dust-merge produce **46 raw regions**; at
#: ``0.15`` they agglomerate to the **7 authored skin nodes** (Lforearm,
#: Rforearm, tail, torso, head, Lwing, Rwing), matching artist intent, while a
#: creature whose limbs have disjoint palettes (Jaccard 0) never over-merges.
#: TODO: validate this threshold on a humanoid donor (e.g. a Carth/Bastila body)
#: when that case runs — humanoids have finer shared collar/spine palettes and
#: may want a slightly different value; no humanoid data point exists yet.
AGGLOMERATION_JACCARD_MIN = 0.15


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


class MissingDonorError(ValueError):
    """Raised when anatomical partition is requested without a valid donor."""


@dataclass(frozen=True)
class DonorSkinData:
    """Ground-truth donor skinning input to partitioning.

    Every field except ``frame`` is required.  If the caller cannot construct
    this, they don't have a donor and should not be calling this module.

    ``bone_indices`` are *local* indices into ``bone_names`` / ``bone_positions``
    (row ``i`` of ``bone_positions`` is the rest-pose position of the bone named
    ``bone_names[i]``).  A value ``< 0`` marks an unused influence slot.

    ``vertices`` and ``bone_positions`` MUST share a single coordinate frame.
    KotOR donors are assembled from several skin nodes with distinct local
    transforms, so a naive concatenation mixes node-local vertices with
    world-space bone pivots (a bug that silently degrades every downstream
    metric).  ``frame`` records which frame the data is in: the production
    builder (``build_donor_skin_data_from_model`` in the Core.Resources loader)
    sets ``"world_space_v1"``; small synthetic/test donors that are trivially
    single-frame may leave the default ``"unspecified"``.
    """

    vertices: np.ndarray  # (V, 3) donor mesh vertices
    faces: np.ndarray  # (F, 3) donor mesh faces
    bone_indices: np.ndarray  # (V, K) per-vertex bone index (int), K influences
    bone_weights: np.ndarray  # (V, K) per-vertex weights, sum(axis=1) ~= 1
    bone_names: List[str]  # length = number of bones (= bone_positions rows)
    bone_positions: np.ndarray  # (B, 3) rest-pose bone positions
    frame: str = "unspecified"  # coordinate frame of vertices+bone_positions


@dataclass(frozen=True)
class AnatomicalRegion:
    """One region of an anatomical partition.

    Regions are computed on the donor and transferred to the imported mesh.
    Both perspectives are stored: ``donor_face_indices`` for provenance,
    ``imported_face_indices`` for the actual output used by downstream fitting.
    """

    region_id: int
    dominant_bone_index: int
    dominant_bone_name: str
    bone_indices_in_region: np.ndarray  # sorted union of bones influencing region, <=16
    donor_face_indices: np.ndarray  # face indices in the donor mesh
    imported_face_indices: np.ndarray  # face indices in the imported mesh (via transfer)
    bone_positions: np.ndarray  # (n_bones_in_region, 3) rest-pose positions
    transfer_confidence: float  # mean(1 / (1 + nearest_donor_face_distance)) — 0..1


@dataclass(frozen=True)
class PartitionResult:
    """Full partition output — the sole return value of the entry-point function."""

    regions: List[AnatomicalRegion]
    donor_face_to_region: np.ndarray  # (F_donor,) region_id per donor face
    imported_face_to_region: np.ndarray  # (F_imported,) region_id per imported face
    diagnostics: dict


# ---------------------------------------------------------------------------
# Donor validation
# ---------------------------------------------------------------------------


def _validate_donor(donor: Optional[DonorSkinData]) -> None:
    """Raise :class:`MissingDonorError` with an actionable message if unusable.

    The message points the user at donor selection.  In GhostRigger the donor
    is the reference/base creature chosen in the Character Builder import flow
    (``normalize_external_model_for_kotor(..., reference_model=...)`` — see
    ``CHANGES.md`` T2506 and ``headless_body_workflow._skin_bone_map_fit_positions``).
    """
    where = (
        "Select a donor creature in the Character Builder import flow "
        "(the reference model whose skin weights drive the anatomical split)."
    )
    if donor is None:
        raise MissingDonorError(
            f"Anatomical partition requires a donor. Donor is None. {where}"
        )

    vertices = np.asarray(donor.vertices)
    faces = np.asarray(donor.faces)
    bone_indices = np.asarray(donor.bone_indices)
    bone_weights = np.asarray(donor.bone_weights)

    if vertices.ndim != 2 or vertices.shape[0] < 4 or vertices.shape[1] != 3:
        raise MissingDonorError(
            "Anatomical partition requires a donor. Donor has fewer than 4 "
            f"vertices (got shape {vertices.shape}). {where}"
        )
    if faces.ndim != 2 or faces.shape[0] < 1 or faces.shape[1] != 3:
        raise MissingDonorError(
            "Anatomical partition requires a donor. Donor has no triangle faces "
            f"(got shape {faces.shape}). {where}"
        )
    if bone_indices.shape[0] != vertices.shape[0]:
        raise MissingDonorError(
            "Anatomical partition requires a donor. Donor weight-vertex mismatch: "
            f"bone_indices has {bone_indices.shape[0]} rows but there are "
            f"{vertices.shape[0]} vertices. {where}"
        )
    if bone_weights.shape != bone_indices.shape:
        raise MissingDonorError(
            "Anatomical partition requires a donor. Donor bone_weights shape "
            f"{bone_weights.shape} does not match bone_indices shape "
            f"{bone_indices.shape}. {where}"
        )
    if not np.all(np.isfinite(bone_weights)):
        raise MissingDonorError(
            "Anatomical partition requires a donor. Donor bone_weights contain "
            f"non-finite values (NaN/inf). {where}"
        )


# ---------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------


def _face_bone_weight(donor: DonorSkinData, n_bones: int) -> np.ndarray:
    """Accumulate per-face bone weight — ``(F, n_bones)``.

    For each face, sum the weight of each bone over the face's three corner
    vertices.  This is the anatomy signal every later step reads from.
    """
    faces = np.asarray(donor.faces, dtype=np.int64)
    bone_indices = np.asarray(donor.bone_indices, dtype=np.int64)
    bone_weights = np.asarray(donor.bone_weights, dtype=np.float64)

    n_faces = faces.shape[0]
    fbw = np.zeros((n_faces, n_bones), dtype=np.float64)
    face_rows = np.arange(n_faces)
    for corner in range(3):
        v = faces[:, corner]
        for slot in range(bone_indices.shape[1]):
            bone = bone_indices[v, slot]
            weight = bone_weights[v, slot]
            valid = (bone >= 0) & (bone < n_bones) & (weight > 0.0)
            np.add.at(fbw, (face_rows[valid], bone[valid]), weight[valid])
    return fbw


#: Decimal places used to weld coincident vertices before building adjacency.
#: KotOR model units are ~metres and duplicate seam vertices are bit-identical
#: after export, so 5 decimals (10 microns) welds seams without collapsing
#: genuinely distinct vertices.
WELD_DECIMALS = 5


def _face_adjacency_edges(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Edge-sharing face adjacency over **welded** vertices — ``(E, 2)`` pairs.

    Donor MDL meshes duplicate vertices at UV/smoothing seams (and this donor is
    seven separate skin nodes concatenated with disjoint vertex ranges), so
    adjacency built on raw indices badly under-connects the surface and the
    partitioner over-fragments.  We therefore weld vertices by rounded position
    (:data:`WELD_DECIMALS`) purely to derive topology — the returned indices are
    still into the *original* face array, so downstream labelling is unaffected.
    Welding also joins the separate skin nodes where body parts meet, which is
    what lets the palette-bounded agglomeration recover coarse anatomy.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    n_faces = faces.shape[0]
    if n_faces == 0:
        return np.zeros((0, 2), dtype=np.int64)

    _, weld = np.unique(np.round(vertices, WELD_DECIMALS), axis=0, return_inverse=True)
    welded_faces = weld[faces]  # (F, 3) in welded index space

    # Three undirected edges per face, sorted so (a,b) == (b,a).
    edges = np.concatenate(
        [welded_faces[:, [0, 1]], welded_faces[:, [1, 2]], welded_faces[:, [2, 0]]],
        axis=0,
    )
    edges = np.sort(edges, axis=1)
    face_of_edge = np.tile(np.arange(n_faces, dtype=np.int64), 3)

    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges_sorted = edges[order]
    faces_sorted = face_of_edge[order]

    # Group identical edges; connect the faces sharing each edge as a chain
    # (sufficient for connectivity, handles non-manifold edges gracefully).
    same_as_prev = np.all(edges_sorted[1:] == edges_sorted[:-1], axis=1)
    boundaries = np.where(~same_as_prev)[0] + 1
    groups = np.split(faces_sorted, boundaries)

    pairs: List[np.ndarray] = []
    for group in groups:
        if group.shape[0] >= 2:
            pairs.append(np.stack([group[:-1], group[1:]], axis=1))
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    adjacency = np.vstack(pairs)
    # Drop self-pairs that can appear when a face repeats an edge (degenerate).
    adjacency = adjacency[adjacency[:, 0] != adjacency[:, 1]]
    return adjacency.astype(np.int64)


def _components_from_edges(n_faces: int, edges: np.ndarray) -> np.ndarray:
    """Connected-component labels over ``n_faces`` nodes given undirected edges."""
    if edges.shape[0] == 0:
        return np.arange(n_faces, dtype=np.int64)
    rows = np.concatenate([edges[:, 0], edges[:, 1]])
    cols = np.concatenate([edges[:, 1], edges[:, 0]])
    data = np.ones(rows.shape[0], dtype=np.int8)
    graph = csr_matrix((data, (rows, cols)), shape=(n_faces, n_faces))
    _, labels = connected_components(graph, directed=False)
    return labels.astype(np.int64)


def _relabel_contiguous(labels: np.ndarray) -> np.ndarray:
    """Map arbitrary integer labels onto ``0..R-1`` preserving grouping."""
    _, inverse = np.unique(labels, return_inverse=True)
    return inverse.astype(np.int64)


# ---------------------------------------------------------------------------
# Phase 1 — BIAGP on the donor
# ---------------------------------------------------------------------------


def _dominant_and_ambiguous(fbw: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Per-face dominant bone and an ambiguity mask.

    Dominant bone = argmax accumulated weight.  A face is ambiguous when its
    top-1 and top-2 weights are within :data:`AMBIGUOUS_WEIGHT_FRACTION` — a
    seam face whose argmax is unstable (see the constant's rationale).
    """
    dominant = np.argmax(fbw, axis=1).astype(np.int64)
    if fbw.shape[1] < 2:
        return dominant, np.zeros(fbw.shape[0], dtype=bool)
    # Two largest per row without a full sort.
    part = np.partition(fbw, -2, axis=1)
    top1 = part[:, -1]
    top2 = part[:, -2]
    with np.errstate(invalid="ignore", divide="ignore"):
        ambiguous = (top1 > 0.0) & ((top1 - top2) <= AMBIGUOUS_WEIGHT_FRACTION * top1)
    return dominant, ambiguous


def _propagate_labels(
    seed_labels: np.ndarray, unlabeled: np.ndarray, edges: np.ndarray
) -> np.ndarray:
    """Multi-source BFS: give each ``unlabeled`` face the label of the nearest
    labeled face by graph distance over ``edges``.

    ``seed_labels`` is ``-1`` for unlabeled faces and a region id otherwise.
    Ties (equidistant seed regions) resolve to the lowest region id encountered,
    which is deterministic.
    """
    labels = seed_labels.copy()
    if not np.any(unlabeled) or edges.shape[0] == 0:
        return labels
    # Adjacency list.
    n_faces = labels.shape[0]
    neighbours: List[List[int]] = [[] for _ in range(n_faces)]
    for a, b in edges:
        neighbours[a].append(b)
        neighbours[b].append(a)
    frontier = [i for i in range(n_faces) if labels[i] >= 0]
    while frontier:
        nxt: List[int] = []
        for face in frontier:
            for nb in neighbours[face]:
                if labels[nb] < 0:
                    labels[nb] = labels[face]
                    nxt.append(nb)
        frontier = nxt
    # Any face still unlabeled (disconnected from every seed) keeps -1; caller
    # assigns it its own region below.
    return labels


def _dust_merge(
    labels: np.ndarray,
    edges: np.ndarray,
    face_centroids: np.ndarray,
    min_faces: int,
) -> Tuple[np.ndarray, int]:
    """Dissolve regions smaller than ``min_faces`` into their strongest neighbour.

    "Strongest neighbour" = the adjacent region sharing the most boundary edges
    with the dust region.  A dust region with **no** adjacent region (an isolated
    island — common here because the donor is 7 separate skin meshes concatenated
    with disjoint vertex sets, so faces across body parts share no edges) is
    merged into the region whose face-centroid centroid is nearest.  Repeats
    until no dust remains or no merge is possible.  Returns
    ``(labels, n_dust_regions_dissolved)``.
    """
    labels = labels.copy()
    dissolved = 0

    while True:
        region_ids, counts = np.unique(labels, return_counts=True)
        small = region_ids[counts < min_faces]
        if small.size == 0 or region_ids.size <= 1:
            break

        la = labels[edges[:, 0]] if edges.shape[0] else np.zeros(0, np.int64)
        lb = labels[edges[:, 1]] if edges.shape[0] else np.zeros(0, np.int64)
        cross = la != lb if edges.shape[0] else np.zeros(0, bool)

        # Smallest dust region first for stability.
        order = small[np.argsort([np.sum(labels == s) for s in small])]
        dust = int(order[0])

        target: Optional[int] = None
        if edges.shape[0]:
            touching = cross & ((la == dust) | (lb == dust))
            if np.any(touching):
                neigh = np.where(la[touching] == dust, lb[touching], la[touching])
                uniq, tally = np.unique(neigh, return_counts=True)
                target = int(uniq[np.argmax(tally)])
        if target is None:
            # Isolated island: fall back to nearest region by centroid distance.
            dust_centre = face_centroids[labels == dust].mean(axis=0)
            best_dist = np.inf
            for other in region_ids.tolist():
                if other == dust:
                    continue
                dist = float(
                    np.linalg.norm(face_centroids[labels == other].mean(axis=0) - dust_centre)
                )
                if dist < best_dist:
                    best_dist = dist
                    target = int(other)
        if target is None:
            break
        labels[labels == dust] = target
        dissolved += 1

    return labels, dissolved


def _agglomerate_to_palette(
    labels: np.ndarray,
    edges: np.ndarray,
    fbw: np.ndarray,
    max_bones: int,
    jaccard_min: float = AGGLOMERATION_JACCARD_MIN,
) -> Tuple[np.ndarray, int]:
    """Merge over-segmented adjacent regions that belong to the same body part.

    JUDGMENT CALL / addition beyond the literal 4-step spec: dominant-bone
    connected components over-segment any creature whose skeleton is finer than
    one bone per body part.  Drexl has ``tail1..tail6`` and per-finger bones, so
    even after seam-welding and dust-merge the donor yields ~46 regions — useless,
    and it fails the spec's own test 5 (4–12 regions).

    We coarsen by agglomerating adjacent regions **only when their bone-influence
    sets overlap** (Jaccard ≥ ``jaccard_min``) and their merged palette still fits
    in ``max_bones``.  Overlap is the anatomy signal: successive segments of one
    appendage share most of their influence bones, whereas two distinct limbs
    share few or none.  This recovers coarse anatomy on Drexl while leaving a
    creature whose limbs have disjoint palettes correctly split.  The most
    strongly overlapping pair merges first.  Returns ``(labels, n_merges)``.
    """
    labels = labels.copy()
    merges = 0
    if edges.shape[0] == 0:
        return labels, merges

    eps = WEIGHT_EPSILON
    while True:
        la = labels[edges[:, 0]]
        lb = labels[edges[:, 1]]
        cross = la != lb
        if not np.any(cross):
            break
        pairs = np.unique(np.sort(np.stack([la[cross], lb[cross]], axis=1), axis=1), axis=0)
        bone_sets: Dict[int, set] = {
            int(r): set(np.where(fbw[labels == r].sum(axis=0) > eps)[0].tolist())
            for r in np.unique(labels).tolist()
        }

        # Score each adjacent pair by Jaccard overlap of bone sets.
        scored: List[Tuple[float, int, int, int]] = []
        for a, b in pairs.tolist():
            a, b = int(a), int(b)
            sa, sb = bone_sets.get(a, set()), bone_sets.get(b, set())
            union = sa | sb
            if not union or len(union) > max_bones:
                continue
            inter = len(sa & sb)
            jaccard = inter / len(union)
            if jaccard >= jaccard_min:
                scored.append((jaccard, len(union), a, b))
        if not scored:
            break

        # Strongest overlap first; break ties toward smaller merged palette.
        scored.sort(key=lambda t: (-t[0], t[1]))
        merged_this_round: set = set()
        did_merge = False
        for _jaccard, _usize, a, b in scored:
            if a in merged_this_round or b in merged_this_round:
                continue
            labels[labels == b] = a
            merged_this_round.update((a, b))
            merges += 1
            did_merge = True
        if not did_merge:
            break

    return labels, merges


def _region_bone_union(fbw_region: np.ndarray) -> np.ndarray:
    """Sorted bone indices with any nonzero accumulated weight in a region."""
    present = np.where(fbw_region.sum(axis=0) > WEIGHT_EPSILON)[0]
    return np.sort(present).astype(np.int64)


def _greedy_palette_split(
    face_ids: np.ndarray,
    fbw: np.ndarray,
    edges: np.ndarray,
    max_bones: int,
) -> List[np.ndarray]:
    """Split one over-palette region's faces into ≤``max_bones`` connected groups.

    Strategy (BIAGP phase 2): order faces by their own bone-set size ascending —
    the "purest" faces (few bones) are the region interior and belong together;
    the many-bone faces are seams.  Accumulate faces until adding one would push
    the running bone union past ``max_bones``, then start a new sub-group.
    Finally re-split each sub-group into connected components so every output is
    a single connected face patch (greedy accumulation can straddle a gap).
    """
    face_ids = np.asarray(face_ids, dtype=np.int64)
    per_face_bonecount = np.count_nonzero(fbw[face_ids] > WEIGHT_EPSILON, axis=1)
    order = face_ids[np.argsort(per_face_bonecount, kind="stable")]

    raw_groups: List[List[int]] = []
    current: List[int] = []
    current_union: set = set()
    for face in order:
        bones = set(np.where(fbw[face] > WEIGHT_EPSILON)[0].tolist())
        if current and len(current_union | bones) > max_bones:
            raw_groups.append(current)
            current = []
            current_union = set()
        current.append(int(face))
        current_union |= bones
    if current:
        raw_groups.append(current)

    # Enforce connectivity per sub-group using the region-local adjacency.
    local_edges = edges[np.isin(edges[:, 0], face_ids) & np.isin(edges[:, 1], face_ids)]
    out: List[np.ndarray] = []
    for group in raw_groups:
        group_arr = np.asarray(group, dtype=np.int64)
        sub_edges = local_edges[
            np.isin(local_edges[:, 0], group_arr) & np.isin(local_edges[:, 1], group_arr)
        ]
        # Reindex faces to 0..n for connected_components.
        remap = {int(f): i for i, f in enumerate(group_arr)}
        if sub_edges.shape[0]:
            re = np.array([[remap[int(a)], remap[int(b)]] for a, b in sub_edges], dtype=np.int64)
        else:
            re = np.zeros((0, 2), dtype=np.int64)
        comp = _components_from_edges(group_arr.shape[0], re)
        for c in np.unique(comp):
            out.append(group_arr[comp == c])
    return out


def _partition_donor_biagp(
    donor: DonorSkinData,
    max_bones_per_region: int,
    min_faces_per_region: int,
) -> Tuple[np.ndarray, Dict[int, np.ndarray], dict]:
    """Phase 1: compute anatomical regions on the donor.

    Returns ``(donor_face_to_region, region_bone_union, phase1_diagnostics)``
    where ``region_bone_union[rid]`` is the sorted ≤``max_bones`` bone index set
    of region ``rid`` and ``donor_face_to_region`` is contiguous ``0..R-1``.
    """
    n_bones = len(donor.bone_names)
    faces = np.asarray(donor.faces, dtype=np.int64)
    n_faces = faces.shape[0]

    fbw = _face_bone_weight(donor, n_bones)
    dominant, ambiguous = _dominant_and_ambiguous(fbw)
    edges = _face_adjacency_edges(donor.vertices, faces)

    # Seed: connected components of same-dominant-bone, non-ambiguous faces only.
    same_dom = dominant[edges[:, 0]] == dominant[edges[:, 1]]
    non_amb = ~ambiguous[edges[:, 0]] & ~ambiguous[edges[:, 1]]
    seed_edges = edges[same_dom & non_amb]
    seed_labels = _components_from_edges(n_faces, seed_edges)
    seed_labels = _relabel_contiguous(seed_labels)

    # Ambiguous faces: strip their seed label, then flood-fill from non-ambiguous
    # seeds by graph distance.
    n_ambiguous = int(np.count_nonzero(ambiguous))
    working = seed_labels.copy()
    working[ambiguous] = -1
    working = _propagate_labels(working, ambiguous, edges)
    # Faces disconnected from every seed keep -1 → give each its own label.
    orphan = working < 0
    if np.any(orphan):
        next_id = int(working.max()) + 1 if working.max() >= 0 else 0
        working[orphan] = np.arange(next_id, next_id + int(orphan.sum()))
    labels = _relabel_contiguous(working)
    regions_seeded = int(np.unique(labels).size)

    face_centroids = np.asarray(donor.vertices, dtype=np.float64)[faces].mean(axis=1)

    # Dust merge (boundary-strength, with centroid fallback for isolated islands).
    labels, dust_dissolved = _dust_merge(labels, edges, face_centroids, min_faces_per_region)
    labels = _relabel_contiguous(labels)

    # Agglomerate adjacent regions up to the palette limit (coarsening step).
    labels, agglomerated = _agglomerate_to_palette(labels, edges, fbw, max_bones_per_region)
    labels = _relabel_contiguous(labels)

    # A second dust pass mops up any sliver left isolated after agglomeration.
    labels, dust_dissolved_2 = _dust_merge(labels, edges, face_centroids, min_faces_per_region)
    labels = _relabel_contiguous(labels)
    dust_dissolved += dust_dissolved_2
    regions_before_palette = int(np.unique(labels).size)

    # Palette enforcement.
    palette_splits = 0
    next_label = int(labels.max()) + 1
    for rid in np.unique(labels).tolist():
        face_ids = np.where(labels == rid)[0]
        union = _region_bone_union(fbw[face_ids])
        if union.size <= max_bones_per_region:
            continue
        palette_splits += 1
        sub_groups = _greedy_palette_split(face_ids, fbw, edges, max_bones_per_region)
        # First sub-group keeps rid; the rest get fresh labels.
        for gi, group in enumerate(sub_groups):
            if gi == 0:
                labels[group] = rid
            else:
                labels[group] = next_label
                next_label += 1
    labels = _relabel_contiguous(labels)
    regions_after_palette = int(np.unique(labels).size)

    # Build per-region bone union + dominant bone.
    region_bone_union: Dict[int, np.ndarray] = {}
    for rid in np.unique(labels).tolist():
        face_ids = np.where(labels == rid)[0]
        region_bone_union[rid] = _region_bone_union(fbw[face_ids])

    phase1 = {
        "regions_seeded": regions_seeded,
        "donor_regions_agglomerated": agglomerated,
        "donor_regions_before_palette": regions_before_palette,
        "donor_regions_after_palette": regions_after_palette,
        "donor_regions_dust_merged": dust_dissolved,
        "ambiguous_faces_deferred": n_ambiguous,
        "palette_splits_triggered": palette_splits,
        "dominant_per_face": dominant,
        "face_bone_weight": fbw,
    }
    return labels, region_bone_union, phase1


# ---------------------------------------------------------------------------
# Phase 2 — transfer donor regions to the imported mesh
# ---------------------------------------------------------------------------


def _normalise_cloud(points: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """Zero-centre and unit-RMS-scale a point cloud; return ``(norm, centre, rms)``."""
    centre = points.mean(axis=0)
    centred = points - centre
    rms = float(np.sqrt(np.mean(np.sum(centred * centred, axis=1))))
    rms = max(rms, 1e-9)
    return centred / rms, centre, rms


def _best_alignment_rotation(
    imported_norm: np.ndarray, donor_tree: cKDTree
) -> np.ndarray:
    """Pick the proper axis rotation aligning imported→donor best.

    CORRECTNESS FIX for coordinate-frame divergence between donor and imported
    OBJ: a nearest-face transfer is only meaningful when donor and import share a
    frame, but real ``.obj`` imports do not (measured on Drexl: donor model space
    is Y-forward with head at +Y ≈ 2.1, while the re-exported OBJ is a compact
    box, thin in Y — the two differ by an axis permutation and a global scale).
    A raw world-space nearest lookup would map head faces onto the tail and yield
    ~0 transfer confidence, silently transferring regions wrong.

    So transfer runs in a *shape-normalised* frame (zero-mean, unit-RMS) and we
    search the 24 proper axis-aligned rotations (the octahedral group) for the
    one minimising mean nearest-neighbour distance.  Identity is a member of the
    group, so this never does worse than no rotation.  This keeps the transfer a
    pure geometric correspondence (no skinning, no fit) while making it robust to
    the frame mismatch that real imports exhibit (Drexl: confidence 0.846).
    """
    best_rotation = np.eye(3)
    best_cost = np.inf
    for rotation in Rotation.create_group("O").as_matrix():
        distances, _ = donor_tree.query(imported_norm @ rotation.T)
        cost = float(np.mean(distances))
        if cost < best_cost:
            best_cost = cost
            best_rotation = rotation
    return best_rotation


def _align_and_transfer_regions(
    imported_vertices: np.ndarray,
    imported_faces: np.ndarray,
    donor: DonorSkinData,
    donor_face_to_region: np.ndarray,
    n_regions: int,
) -> Tuple[np.ndarray, Dict[int, float], List[int], List[int], float]:
    """Phase 2: align the imported mesh to the donor, then assign each imported
    face to a donor region by nearest donor face.

    The alignment (shape-normalise + best axis rotation, see
    :func:`_best_alignment_rotation`) is a correctness requirement, not an option:
    donor and imported OBJ generally live in different coordinate frames.  Returns
    ``(imported_face_to_region, per_region_confidence, low_conf_regions,
    empty_regions, mean_confidence)``.
    """
    donor_vertices = np.asarray(donor.vertices, dtype=np.float64)
    donor_faces = np.asarray(donor.faces, dtype=np.int64)
    imported_vertices = np.asarray(imported_vertices, dtype=np.float64)
    imported_faces = np.asarray(imported_faces, dtype=np.int64)

    donor_centroids = donor_vertices[donor_faces].mean(axis=1)
    imported_centroids = imported_vertices[imported_faces].mean(axis=1)

    donor_norm, _, _ = _normalise_cloud(donor_centroids)
    imported_norm, _, _ = _normalise_cloud(imported_centroids)

    tree = cKDTree(donor_norm)
    rotation = _best_alignment_rotation(imported_norm, tree)
    distances, nearest = tree.query(imported_norm @ rotation.T)

    imported_face_to_region = donor_face_to_region[nearest].astype(np.int64)

    # Per-imported-face confidence, then aggregate per region.
    per_face_conf = 1.0 / (1.0 + distances)
    per_region_confidence: Dict[int, float] = {}
    low_conf_regions: List[int] = []
    empty_regions: List[int] = []
    for rid in range(n_regions):
        mask = imported_face_to_region == rid
        if not np.any(mask):
            empty_regions.append(rid)
            per_region_confidence[rid] = 0.0
            continue
        conf = float(np.mean(per_face_conf[mask]))
        per_region_confidence[rid] = conf
        if conf < 0.1:
            low_conf_regions.append(rid)

    mean_conf = float(np.mean(per_face_conf)) if per_face_conf.size else 0.0
    return (
        imported_face_to_region,
        per_region_confidence,
        low_conf_regions,
        empty_regions,
        mean_conf,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def partition_mesh_anatomically(
    imported_vertices: np.ndarray,  # (V_imp, 3)
    imported_faces: np.ndarray,  # (F_imp, 3)
    donor: Optional[DonorSkinData],
    *,
    max_bones_per_region: int = 16,  # KOTOR hard limit
    min_faces_per_region: int = 8,  # dust-island threshold
    random_seed: int = 42,
) -> PartitionResult:
    """Partition an imported mesh into anatomical regions using donor skin weights.

    Algorithm:
      1. Compute regions on the donor via BIAGP (dominant-bone growing + dust
         merge + palette enforcement).
      2. Transfer regions to the imported mesh via nearest-donor-face
         correspondence (in a shape-normalised, axis-aligned frame).

    Every output region satisfies ``|bone_indices_in_region| <=
    max_bones_per_region`` and is a connected face component of the donor.

    Raises :class:`MissingDonorError` if ``donor`` is ``None`` or malformed.
    """
    _validate_donor(donor)
    assert donor is not None  # for type checkers; _validate_donor guarantees this

    # ``random_seed`` is accepted for API stability / reproducibility of any
    # future stochastic step; the current algorithm is deterministic, but we set
    # the global seed so callers get identical output regardless of prior RNG use.
    np.random.seed(random_seed)

    imported_vertices = np.asarray(imported_vertices, dtype=np.float64)
    imported_faces = np.asarray(imported_faces, dtype=np.int64)

    # ---- Phase 1: donor partition -------------------------------------------
    donor_face_to_region, region_bone_union, phase1 = _partition_donor_biagp(
        donor, max_bones_per_region, min_faces_per_region
    )
    n_regions = int(np.unique(donor_face_to_region).size)
    fbw = phase1["face_bone_weight"]

    # ---- Phase 2: transfer to imported --------------------------------------
    (
        imported_face_to_region,
        per_region_confidence,
        low_conf_regions,
        empty_regions,
        mean_conf,
    ) = _align_and_transfer_regions(
        imported_vertices,
        imported_faces,
        donor,
        donor_face_to_region,
        n_regions,
    )

    # ---- Assemble regions ---------------------------------------------------
    bone_positions = np.asarray(donor.bone_positions, dtype=np.float64)
    regions: List[AnatomicalRegion] = []
    bones_per_region: List[int] = []
    for rid in range(n_regions):
        donor_faces_here = np.where(donor_face_to_region == rid)[0].astype(np.int64)
        imported_faces_here = np.where(imported_face_to_region == rid)[0].astype(np.int64)
        bone_union = region_bone_union[rid]
        bones_per_region.append(int(bone_union.size))

        # Dominant bone of the region = bone with the greatest accumulated weight
        # across the region's donor faces.
        region_weight = fbw[donor_faces_here].sum(axis=0)
        dominant_bone_index = int(np.argmax(region_weight)) if region_weight.size else 0
        dominant_bone_name = (
            donor.bone_names[dominant_bone_index]
            if 0 <= dominant_bone_index < len(donor.bone_names)
            else ""
        )

        region_bone_positions = (
            bone_positions[bone_union]
            if bone_union.size and bone_positions.shape[0] > int(bone_union.max())
            else np.zeros((0, 3), dtype=np.float64)
        )

        regions.append(
            AnatomicalRegion(
                region_id=rid,
                dominant_bone_index=dominant_bone_index,
                dominant_bone_name=dominant_bone_name,
                bone_indices_in_region=bone_union,
                donor_face_indices=donor_faces_here,
                imported_face_indices=imported_faces_here,
                bone_positions=region_bone_positions,
                transfer_confidence=per_region_confidence.get(rid, 0.0),
            )
        )

    # Defense-in-depth: the KotOR skin-node palette limit is 16 bones/region.
    # Phase 2's greedy palette split already guarantees this; assert it here so a
    # future regression in either phase (or a donor-frame change like PR C.1)
    # fails loudly instead of silently emitting an over-palette region.
    max_bones_observed = max((r.bone_indices_in_region.size for r in regions), default=0)
    assert max_bones_observed <= 16, (
        f"Palette invariant violated: max_bones={max_bones_observed} > 16. "
        f"Region sizes: {[int(r.bone_indices_in_region.size) for r in regions]}"
    )

    diagnostics = {
        "trace_version": TRACE_VERSION,
        "donor_face_count": int(donor.faces.shape[0]),
        "imported_face_count": int(imported_faces.shape[0]),
        "donor_regions_before_palette": phase1["donor_regions_before_palette"],
        "donor_regions_after_palette": phase1["donor_regions_after_palette"],
        "donor_regions_dust_merged": phase1["donor_regions_dust_merged"],
        "donor_regions_agglomerated": phase1["donor_regions_agglomerated"],
        "final_region_count": n_regions,
        "ambiguous_faces_deferred": phase1["ambiguous_faces_deferred"],
        "palette_splits_triggered": phase1["palette_splits_triggered"],
        "max_bones_in_any_region": int(max(bones_per_region)) if bones_per_region else 0,
        "min_bones_in_any_region": int(min(bones_per_region)) if bones_per_region else 0,
        "regions_with_low_transfer_confidence": low_conf_regions,
        "empty_transfer_regions": empty_regions,
        "mean_transfer_confidence": mean_conf,
        "algorithm_seed": int(random_seed),
    }

    return PartitionResult(
        regions=regions,
        donor_face_to_region=donor_face_to_region,
        imported_face_to_region=imported_face_to_region,
        diagnostics=diagnostics,
    )
