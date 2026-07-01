"""Generalized-winding-number containment primitives (foundation module).

This module provides a robust inside/outside oracle for *open-shell* triangle
meshes — the kind GhostRigger imports for KotOR creatures (Drexl, Rancor),
whose meshes have holes (eye/mouth cavities, open cuffs, UV-seam gaps) and are
therefore **not watertight**.  The current containment pipeline
(``containment_fit.fit_skeleton_inside_mesh``) uses a ray-parity crossing test
which is only valid on closed surfaces; open shells fall back to the
oriented-bounds box solution in
``headless_body_workflow._oriented_bounds_containment_solution`` (line 1970),
which is a bounding box, not a shell.

The Generalized Winding Number (GWN) fixes this.  Rather than counting ray
crossings, it integrates the signed solid angle each triangle subtends at a
query point.  For a watertight mesh it returns exactly ``1`` inside / ``0``
outside; for an open mesh it degrades *gracefully* to a continuous value in
roughly ``[0, 1]`` and is not fooled by a single nearby polygon or by holes,
self-intersections, or non-manifold edges.

Design split (see also Q1/Q2 of the containment-v2 research notes):

* **GWN is the authoritative inside/outside oracle.** See
  :func:`generalized_winding_number`.
* **Signed distance is only the margin / gradient signal** — "how far inside",
  never the classifier.  See :func:`signed_distance_to_surface`.

No callers are wired up in this module's PR; it is a pure foundation consumed
later by a v2 of ``containment_fit.py``.

References
----------
* Jacobson, Kavan & Sorkine-Hornung, "Robust Inside-Outside Segmentation Using
  Generalized Winding Numbers", ACM Transactions on Graphics (SIGGRAPH) 2013.
  Establishes the GWN as a robust inside/outside measure for imperfect meshes.
* van Oosterom & Strackee, "The Solid Angle of a Plane Triangle", IEEE
  Transactions on Biomedical Engineering, BME-30(2), 1983.  Gives the
  closed-form signed solid angle of a triangle seen from a point, used here as
  the per-face term of the winding-number sum.

Dependencies: pure NumPy + SciPy + trimesh.  No native/compiled additions
(the package ships as RCDATA-embedded Python inside native DLLs with
byte-identity tests, so new native deps are a build-system hazard).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import trimesh


# ---------------------------------------------------------------------------
# Tunable constants (documented judgment calls)
# ---------------------------------------------------------------------------

#: Default winding threshold returned when the GWN sample distribution has no
#: clear bimodal valley (Otsu cannot separate inside from outside).  0.4 sits
#: just below the natural 0.5 split so a unimodal-but-mostly-inside sample
#: still classifies interior points as inside.
DEFAULT_WINDING_THRESHOLD: float = 0.4

#: Fraction of inconsistently wound shared edges above which we stop trusting
#: face normals.  5% tolerates a handful of bad faces on an otherwise-clean
#: mesh while rejecting triangle soup / scrambled winding.
NORMAL_TRUST_MAX_INCONSISTENT_FRACTION: float = 0.05

#: Otsu between-class / within-class variance ratio below which a GWN sample is
#: declared unimodal (no inside/outside valley).  Empirically a uniform[0,1]
#: sample scores ~3 and a single Gaussian ~1.8, while a genuinely bimodal
#: inside/outside sample (tight peaks near 0 and 1) scores in the tens-to-
#: hundreds; 6.0 leaves comfortable margin on both sides.  See the module
#: report / test_otsu_* for the measured values this was tuned against.
OTSU_UNIMODAL_SEPARATION: float = 6.0


# ---------------------------------------------------------------------------
# 1. Normal repair + trust diagnostics
# ---------------------------------------------------------------------------

def repair_normals(mesh: "trimesh.Trimesh") -> Tuple["trimesh.Trimesh", Dict[str, Any]]:
    """Reprocess a mesh, fix its winding/normals, and report normal trust.

    Rebuilds the mesh with ``process=True`` (which merges duplicate vertices
    and drops degenerate/duplicate faces) and runs ``fix_normals()`` to make
    the face winding consistent and outward-facing where topology allows.

    Trust is assessed from the fraction of *inconsistently wound* shared edges:
    on a correctly oriented manifold every interior edge is traversed in
    opposite directions by its two incident faces, so the two per-face edge
    directions multiply to ``-1``.  A product of ``+1`` means the neighbours
    disagree (a winding flip).  Triangle soup has *no* shared edges, so winding
    cannot be verified at all and the mesh is reported as untrustworthy.

    Parameters
    ----------
    mesh:
        Input triangle mesh.  Only its ``vertices`` and ``faces`` are used.

    Returns
    -------
    (repaired_mesh, diagnostics) where ``diagnostics`` has keys:
        ``consistent`` (bool):
            True iff there is connectivity and *every* shared edge is wound
            consistently after repair.
        ``inconsistent_edge_fraction`` (float):
            Fraction of adjacent face pairs with disagreeing winding; ``1.0``
            when there is no connectivity to judge (triangle soup).
        ``should_trust_normals`` (bool):
            True iff ``inconsistent_edge_fraction <
            NORMAL_TRUST_MAX_INCONSISTENT_FRACTION`` (5%).
    """
    repaired = trimesh.Trimesh(
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        faces=np.asarray(mesh.faces, dtype=np.int64),
        process=True,
    )
    # fix_normals() makes winding consistent in-place where topology allows.
    repaired.fix_normals()

    adjacency = np.asarray(repaired.face_adjacency)          # (N, 2) face index pairs
    shared_edges = np.asarray(repaired.face_adjacency_edges)  # (N, 2) shared (u, v)
    faces = np.asarray(repaired.faces)
    n_pairs = int(adjacency.shape[0])

    if n_pairs == 0 or faces.shape[0] == 0:
        # No shared edges: cannot verify orientation (triangle soup / isolated
        # faces).  Do not trust normals.
        diagnostics: Dict[str, Any] = {
            "consistent": False,
            "inconsistent_edge_fraction": 1.0,
            "should_trust_normals": False,
        }
        return repaired, diagnostics

    # Per-face traversal direction of the shared edge.  For triangle
    # [v0, v1, v2] the directed cycle is v0->v1->v2->v0, so the vertex AFTER u
    # is v iff the face traverses the edge as u->v (+1); otherwise v->u (-1).
    u = shared_edges[:, 0]
    v = shared_edges[:, 1]

    def _edge_sign(face_indices: np.ndarray) -> np.ndarray:
        tri = faces[face_indices]                       # (N, 3)
        pos_u = np.argmax(tri == u[:, None], axis=1)    # index of u within each triangle
        nxt = tri[np.arange(tri.shape[0]), (pos_u + 1) % 3]
        return np.where(nxt == v, 1, -1)

    sign_a = _edge_sign(adjacency[:, 0])
    sign_b = _edge_sign(adjacency[:, 1])
    # Correctly oriented neighbours traverse the edge oppositely (product -1).
    inconsistent = int(np.count_nonzero(sign_a * sign_b == 1))
    inconsistent_fraction = inconsistent / float(n_pairs)

    diagnostics = {
        "consistent": bool(inconsistent == 0),
        "inconsistent_edge_fraction": float(inconsistent_fraction),
        "should_trust_normals": bool(
            inconsistent_fraction < NORMAL_TRUST_MAX_INCONSISTENT_FRACTION
        ),
    }
    return repaired, diagnostics


# ---------------------------------------------------------------------------
# 2. Generalized winding number (van Oosterom-Strackee solid angle sum)
# ---------------------------------------------------------------------------

def generalized_winding_number(
    query_points: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
) -> np.ndarray:
    r"""Generalized winding number of ``query_points`` w.r.t. a triangle mesh.

    For each query point :math:`p` the GWN is the sum over triangles of the
    signed solid angle each triangle subtends at :math:`p`, divided by
    :math:`4\pi`:

    .. math::

        w(p) = \frac{1}{4\pi} \sum_{t} \Omega_t(p)

    The per-triangle signed solid angle uses the van Oosterom & Strackee (1983)
    closed form.  With :math:`a, b, c` the triangle vertices relative to the
    query point and :math:`l_a = \lVert a \rVert` etc.:

    .. math::

        \tan\!\frac{\Omega}{2} =
          \frac{a \cdot (b \times c)}
               {l_a l_b l_c + (a\cdot b) l_c + (b\cdot c) l_a + (c\cdot a) l_b}

        \Omega = 2\,\operatorname{atan2}(\text{numerator}, \text{denominator})

    ``atan2`` keeps the result finite for every finite input, so degenerate
    (zero-area / collinear) triangles contribute exactly zero rather than NaN:
    their triple product (numerator) is zero, and ``atan2(0, denom)`` is ``0``.

    Following Jacobson et al. 2013, this returns ~1 for points inside a
    watertight mesh and ~0 outside, degrading continuously for open shells.

    Parameters
    ----------
    query_points: (Q, 3) float array of evaluation points.
    vertices:     (V, 3) float array of mesh vertices.
    faces:        (F, 3) int array of triangle vertex indices.

    Returns
    -------
    (Q,) float64 array of winding numbers.
    """
    query = np.asarray(query_points, dtype=np.float64).reshape(-1, 3)
    verts = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    tris = np.asarray(faces, dtype=np.int64).reshape(-1, 3)

    q_count = query.shape[0]
    if q_count == 0 or tris.shape[0] == 0:
        return np.zeros(q_count, dtype=np.float64)

    # Triangle corner positions, shape (F, 3) each.
    tri_a = verts[tris[:, 0]]
    tri_b = verts[tris[:, 1]]
    tri_c = verts[tris[:, 2]]

    # -- einsum axis convention (MOST bug-prone line in the module) -----------
    # We broadcast every triangle corner against every query point to form the
    # corner vectors relative to each query point:
    #     a, b, c  with shape (Q, F, 3)
    # Index letters used in every einsum below:
    #     'q' = query-point axis   (length Q)
    #     'f' = face/triangle axis (length F)
    #     'i' = the xyz component  (length 3, always contracted away)
    # So 'qfi,qfi->qf' is a per-(query, face) dot product over xyz, producing a
    # scalar field of shape (Q, F).  Never contract 'q' or 'f'; only 'i'.
    a = tri_a[None, :, :] - query[:, None, :]   # (Q, F, 3)
    b = tri_b[None, :, :] - query[:, None, :]   # (Q, F, 3)
    c = tri_c[None, :, :] - query[:, None, :]   # (Q, F, 3)

    len_a = np.sqrt(np.einsum("qfi,qfi->qf", a, a))
    len_b = np.sqrt(np.einsum("qfi,qfi->qf", b, b))
    len_c = np.sqrt(np.einsum("qfi,qfi->qf", c, c))

    # Numerator: scalar triple product a . (b x c), shape (Q, F).
    cross_bc = np.cross(b, c)                          # (Q, F, 3)
    numerator = np.einsum("qfi,qfi->qf", a, cross_bc)  # (Q, F)

    dot_ab = np.einsum("qfi,qfi->qf", a, b)
    dot_bc = np.einsum("qfi,qfi->qf", b, c)
    dot_ca = np.einsum("qfi,qfi->qf", c, a)

    denominator = (
        len_a * len_b * len_c
        + dot_ab * len_c
        + dot_bc * len_a
        + dot_ca * len_b
    )

    # atan2 is finite for all finite inputs; degenerate faces -> 0 contribution.
    solid_angle = 2.0 * np.arctan2(numerator, denominator)   # (Q, F)
    winding = solid_angle.sum(axis=1) / (4.0 * np.pi)         # (Q,)
    return winding.astype(np.float64, copy=False)


# ---------------------------------------------------------------------------
# 3. Signed distance (margin signal ONLY — not the inside/outside oracle)
# ---------------------------------------------------------------------------

def signed_distance_to_surface(
    query_points: np.ndarray,
    mesh: "trimesh.Trimesh",
) -> np.ndarray:
    """Signed distance from each query point to the mesh surface.

    Wraps ``trimesh.proximity.signed_distance`` (R-tree accelerated).  trimesh
    reports inside points as *positive*; we **negate** so the returned
    convention is:

        positive  ->  OUTSIDE the surface
        negative  ->  INSIDE the surface
        ~0        ->  on the surface

    IMPORTANT: this is the *margin / gradient* signal only — i.e. "how far in
    or out" a point is, useful for pushing bones a safe depth inside the shell
    during a future fit solve.  It is **not** the authoritative inside/outside
    classifier: nearest-point sign flips erratically near holes and thin
    features on open meshes.  Use :func:`generalized_winding_number` for the
    actual inside/outside decision.

    Parameters
    ----------
    query_points: (Q, 3) float array.
    mesh:         a ``trimesh.Trimesh``.

    Returns
    -------
    (Q,) float64 array; positive = outside, negative = inside.
    """
    query = np.asarray(query_points, dtype=np.float64).reshape(-1, 3)
    if query.shape[0] == 0:
        return np.zeros(0, dtype=np.float64)
    trimesh_signed = np.asarray(
        trimesh.proximity.signed_distance(mesh, query), dtype=np.float64
    )
    # trimesh: inside positive -> negate to get outside-positive convention.
    return -trimesh_signed


# ---------------------------------------------------------------------------
# 4. Adaptive winding threshold via Otsu's method
# ---------------------------------------------------------------------------

def adaptive_winding_threshold(
    gwn_samples: np.ndarray,
    n_bins: int = 256,
) -> Tuple[float, Dict[str, Any]]:
    """Pick an inside/outside winding threshold from a sample of GWN values.

    A watertight mesh produces GWN values tightly clustered near 0 (outside)
    and 1 (inside), so the histogram is bimodal and the natural cut sits in the
    valley between the modes.  Otsu's method finds the threshold that maximises
    between-class variance (equivalently the valley of a bimodal histogram).

    When the histogram is *unimodal* — no clear inside/outside valley, e.g. a
    box that fills its own bounding box (all-inside) or noise — Otsu would
    still return some arbitrary cut, so instead we fall back to
    :data:`DEFAULT_WINDING_THRESHOLD`.  Unimodality is detected via the Otsu
    between-class / within-class variance ratio (a Fisher-style separation
    score); below :data:`OTSU_UNIMODAL_SEPARATION` the modes are not separable.

    Parameters
    ----------
    gwn_samples: 1-D (or flattenable) array of GWN values.
    n_bins:      histogram resolution for the Otsu search.

    Returns
    -------
    (threshold, diagnostics) where ``diagnostics`` has keys:
        ``threshold`` (float)                : the returned threshold.
        ``unimodal`` (bool)                  : True if no valley was found.
        ``valley_location`` (float | None)   : GWN value at the Otsu cut, or
                                               None when unimodal.
        ``sample_count`` (int)               : number of finite samples used.
        ``otsu_separation_score`` (float)    : between/within variance ratio.
    """
    samples = np.asarray(gwn_samples, dtype=np.float64).ravel()
    samples = samples[np.isfinite(samples)]
    sample_count = int(samples.size)

    def _unimodal_result(score: float) -> Tuple[float, Dict[str, Any]]:
        return DEFAULT_WINDING_THRESHOLD, {
            "threshold": DEFAULT_WINDING_THRESHOLD,
            "unimodal": True,
            "valley_location": None,
            "sample_count": sample_count,
            "otsu_separation_score": float(score),
        }

    # Degenerate: too few samples or a single constant value -> no valley.
    if sample_count < 2 or float(samples.min()) == float(samples.max()):
        return _unimodal_result(0.0)

    hist, edges = np.histogram(samples, bins=n_bins)
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return _unimodal_result(0.0)

    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    prob = hist / total

    # Vectorised Otsu over every inter-bin threshold.
    omega = np.cumsum(prob)                       # class-0 weight w0(t)
    mu = np.cumsum(prob * bin_centers)            # class-0 cumulative mean*weight
    mu_total = mu[-1]

    denom = omega * (1.0 - omega)                 # w0 * w1
    with np.errstate(divide="ignore", invalid="ignore"):
        between_class = (mu_total * omega - mu) ** 2 / denom
    between_class = np.where(denom > 0, between_class, 0.0)

    # For a bimodal histogram with an *empty* valley (e.g. a cube that fills
    # only 1/8 of its bbox: a big peak near 0, a small peak near 1, nothing
    # between), the between-class variance is identical for every threshold
    # placed inside the empty gap.  np.argmax would return the leftmost such
    # bin, dragging the threshold to ~0.  Instead pick the centre of the
    # maximal-variance plateau so the cut lands in the middle of the valley.
    best_value = float(between_class.max())
    plateau = np.flatnonzero(
        np.isclose(between_class, best_value, rtol=1e-9, atol=1e-12)
    )
    best = int(plateau[plateau.size // 2])
    threshold_value = float(bin_centers[best])

    total_variance = float(np.sum(prob * (bin_centers - mu_total) ** 2))
    sigma_b = float(between_class[best])
    sigma_w = total_variance - sigma_b           # within-class variance at best t
    if sigma_w <= 0.0:
        # Perfect separation (e.g. two delta peaks): treat as strongly bimodal.
        separation = float("inf")
    else:
        separation = sigma_b / sigma_w

    if separation < OTSU_UNIMODAL_SEPARATION:
        return _unimodal_result(separation)

    diagnostics = {
        "threshold": threshold_value,
        "unimodal": False,
        "valley_location": threshold_value,
        "sample_count": sample_count,
        "otsu_separation_score": separation,
    }
    return threshold_value, diagnostics


# ---------------------------------------------------------------------------
# 5. End-to-end convenience classifier
# ---------------------------------------------------------------------------

def classify_points(
    points: np.ndarray,
    mesh: "trimesh.Trimesh",
    n_bbox_samples: int = 512,
) -> Dict[str, Any]:
    """Classify points as inside/outside a (possibly open) shell mesh.

    Pipeline:
      1. Repair normals / assess trust (:func:`repair_normals`).
      2. Compute GWN for the input points (:func:`generalized_winding_number`).
      3. Compute signed distance for the input points
         (:func:`signed_distance_to_surface`) as a margin signal.
      4. Draw ``n_bbox_samples`` uniform random points from the *repaired
         mesh's* bounding box, compute their GWN, and derive the adaptive
         threshold from that sample (:func:`adaptive_winding_threshold`).  The
         threshold is derived from the bbox sample rather than the input points
         because the input may not span the full inside/outside distribution.
      5. ``inside_mask = gwn_values >= threshold``.

    Parameters
    ----------
    points:         (Q, 3) float array of points to classify.
    mesh:           a ``trimesh.Trimesh`` shell.
    n_bbox_samples: number of bbox-uniform GWN samples for thresholding.

    Returns
    -------
    dict with keys:
        ``inside_mask`` (np.ndarray[bool], shape (Q,))
        ``gwn_values`` (np.ndarray[float], shape (Q,))
        ``signed_distance`` (np.ndarray[float], shape (Q,))  positive = outside
        ``threshold`` (float)
        ``normal_repair_diagnostics`` (dict)
        ``threshold_diagnostics`` (dict)
    """
    query = np.asarray(points, dtype=np.float64).reshape(-1, 3)

    repaired, normal_diag = repair_normals(mesh)
    vertices = np.asarray(repaired.vertices, dtype=np.float64)
    faces = np.asarray(repaired.faces, dtype=np.int64)

    gwn_values = generalized_winding_number(query, vertices, faces)
    signed_distance = signed_distance_to_surface(query, repaired)

    # Bounding-box-uniform GWN sample drives the adaptive threshold.
    bounds = np.asarray(repaired.bounds, dtype=np.float64)  # (2, 3): [min; max]
    rng = np.random.default_rng(0)  # deterministic threshold across runs
    bbox_samples = rng.uniform(
        low=bounds[0], high=bounds[1], size=(int(n_bbox_samples), 3)
    )
    sample_gwn = generalized_winding_number(bbox_samples, vertices, faces)
    threshold, threshold_diag = adaptive_winding_threshold(sample_gwn)

    inside_mask = gwn_values >= threshold

    return {
        "inside_mask": inside_mask,
        "gwn_values": gwn_values,
        "signed_distance": signed_distance,
        "threshold": float(threshold),
        "normal_repair_diagnostics": normal_diag,
        "threshold_diagnostics": threshold_diag,
    }
