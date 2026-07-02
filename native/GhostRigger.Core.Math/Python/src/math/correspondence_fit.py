"""Correspondence-based skeleton fit (T2509b).

Derives a rigid similarity ``(s, R, t)`` from donor-to-imported mesh **surface
correspondence** and carries the donor skeleton rigidly by that transform.
This is the successor objective to ``containment_fit``'s shell containment:
PR B (T2506) proved a single rigid containment fit balloons on open-shell
creatures (Drexl: scale ~87), and PR C (T2507) proved the failure is the
containment *objective* itself — proximal joint bones sit on a region's rim,
not its interior, so "push the pivot inside the shell" is incoherent.  The
donor artist already placed bones correctly at joints; correspondence fit
therefore never asks anything to be *inside* anything.  It aligns the donor
mesh surface onto the imported mesh surface and rides the skeleton along.

Algorithm (Stage 3 is Option 1 "align-then-refine" — locked by the 2026-07-01
design review after the raw nearest-surface spec was falsified on Drexl:
donor world frame diag 12.12 vs OBJ diag 1.37, raw confidence 0.86):

1. Classify donor bones; filter degenerates (duplicate-position FIRST — it is
   the filter that catches collapsed wing chains like Drexl ``Rwing_03/05/07``).
2. Record donor rim ratios ``d_nearest / spread`` per real bone (Falsifier A
   baseline).
3. **Pre-align**: shape-normalise donor + imported clouds
   (``landmark_alignment.normalise_cloud``), search the 24 octahedral rotations
   (``landmark_alignment.best_alignment_rotation``), compose into an
   original-frame similarity donor→imported.
4. **Correspond**: nearest-surface lookup of the pre-aligned donor vertices on
   the imported mesh (``trimesh.proximity``); weights ``w = 1/(1+d)``.
5. **Refine**: weighted Umeyama
   (``landmark_alignment.compute_weighted_rigid_transform``) on the
   correspondence; compose pre-alignment ∘ refinement into the returned total
   ``(scale, R, t)``.
6. Carry ``donor.bone_positions`` by the total transform; evaluate falsifiers.

Falsifier A — rim-ratio preservation (``RATIO_TOLERANCE = 0.50``): a bone's
relationship to its influence cluster is the artist's rigging intent; a good
fit preserves it.  NOTE (T2510 calibration debt): 0.50 is a deliberately loose
gate.  The only real fixture today (Drexl) is a self-fit (transfer confidence
1.0 post-T2508), so ratio preservation passes trivially there and CANNOT
calibrate this tolerance; a proportion-mismatched corpus (T2510) is required
before tightening.  On proportion-mismatched inputs, out-of-tolerance bones are
the retargeting-difficulty signal, not necessarily a failure.

Falsifier B — refinement-scale bracket: the weighted-Umeyama refinement runs
after pre-alignment already matched global scale, so its scale must be ~1.
Bracket ``[0.5, 2.0]`` around 1.0.

Sits on:
- ``landmark_alignment`` (weighted Umeyama, normalise_cloud,
  best_alignment_rotation — T2509a)
- ``containment_fit._bbox_diagonal`` (diagnostic scale estimate; read-only)
- ``anatomical_partition.DonorSkinData`` (duck-typed frozen input;
  ``frame == "world_space_v1"`` required — see PR C.1 / T2508)

Behind ``use_v3=False`` by default: dark code until PR D wires dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

TRACE_VERSION = "ghostrigger.correspondence/v1"

#: Influence-set membership threshold (same value the Q1/PR C probes used to
#: measure compact per-bone clusters on Drexl — 51/53 compact at w > 0.3).
INFLUENCE_WEIGHT_THRESHOLD = 0.3

#: Falsifier A relative tolerance on rim-ratio preservation.  LOOSE GATE —
#: T2510 calibration debt: Drexl is a self-fit and cannot calibrate this; do
#: not tighten without a proportion-mismatched corpus.
RATIO_TOLERANCE = 0.50

#: Degenerate-bone filter constants.  Ordering of the filters is load-bearing:
#: duplicate-position runs FIRST because it is what catches collapsed FK wing
#: chains (Drexl Rwing_03/05/07 share one world position; Rwing_07 has exactly
#: 5 influence verts and spread 0.017, so the count/spread filters alone would
#: miss it on the boundary).
_DUPLICATE_POSITION_EPS = 1e-5
_MIN_INFLUENCE_VERTS = 5
_MIN_INFLUENCE_SPREAD = 0.01

#: Falsifier B bracket on the REFINEMENT scale (not the total scale).
#: Deliberately tighter than v2 solver's 0.1x-20x bracket
#: (containment_fit.py:655-656); this guards the refinement step, not the
#: containment solver — the wide solver bracket is exactly what allowed v2's
#: Drexl balloon to s≈87.  Do not reconcile the two.
_SCALE_BRACKET_LOW = 0.5
_SCALE_BRACKET_HIGH = 2.0


def _load_math_sibling(module_name: str):
    """Import a sibling math module robustly across import styles.

    Same pattern as ``containment_fit._load_math_sibling``: this module may be
    imported as ``src.math.correspondence_fit`` in the embedded runtime, or
    loaded directly by file path in tests (no package context).
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


@dataclass(frozen=True)
class CorrespondenceFitResult:
    """Result of :func:`fit_skeleton_by_correspondence`.

    ``scale``/``rotation``/``translation`` are the **composed total** similarity
    (pre-alignment ∘ refinement) mapping donor world space onto imported space.
    ``falsifier_b`` brackets the *refinement* scale only (see module docstring).
    """

    scale: float
    rotation: np.ndarray  # (3, 3) total rotation
    translation: np.ndarray  # (3,) total translation
    fitted_bone_positions: np.ndarray  # (B, 3) donor bones after total transform
    surface_confidence: float  # [0, 1]; 1/(1 + mean_residual/imported_diag)
    falsifier_a: dict  # rim-ratio preservation report
    falsifier_b: dict  # refinement-scale bracket report
    degenerate_donor_bones: Dict[str, str]  # bone_name -> reason
    real_bone_count: int
    initial_scale_estimate: float  # diagnostic only (containment formula)
    trace_version: str = TRACE_VERSION
    diagnostics: Dict[str, Any] = field(default_factory=dict)


def _classify_donor_bones(donor) -> Tuple[Dict[str, str], Dict[int, dict]]:
    """Split donor bones into degenerate (excluded from Falsifier A) and real.

    Filter order is load-bearing (see the constants block): duplicate world
    position FIRST, then influence-vertex count, then influence spread.
    Returns ``(degenerate: {bone_name: reason}, real: {bone_index: info})``
    where ``info`` has ``world_pos``, ``influence_verts``, ``spread``,
    ``d_nearest``.
    """
    vertices = np.asarray(donor.vertices, dtype=np.float64)
    bone_indices = np.asarray(donor.bone_indices, dtype=np.int64)
    bone_weights = np.asarray(donor.bone_weights, dtype=np.float64)
    bone_positions = np.asarray(donor.bone_positions, dtype=np.float64)
    names: List[str] = list(donor.bone_names)
    n_bones = len(names)

    # Accumulated per-vertex weight for each bone (slots may repeat a bone).
    per_bone_weight = np.zeros((vertices.shape[0], n_bones), dtype=np.float64)
    for k in range(bone_indices.shape[1]):
        valid = (bone_indices[:, k] >= 0) & (bone_indices[:, k] < n_bones)
        rows = np.where(valid)[0]
        np.add.at(per_bone_weight, (rows, bone_indices[rows, k]), bone_weights[rows, k])

    degenerate: Dict[str, str] = {}
    real: Dict[int, dict] = {}
    for i in range(n_bones):
        pos_i = bone_positions[i]

        # Filter 1 (PRIMARY): duplicate world position.
        dup_j = -1
        for j in range(n_bones):
            if j == i:
                continue
            if float(np.linalg.norm(pos_i - bone_positions[j])) < _DUPLICATE_POSITION_EPS:
                dup_j = j
                break
        if dup_j >= 0:
            degenerate[names[i]] = f"duplicate_position_with_{names[dup_j]}"
            continue

        influence_idx = np.where(per_bone_weight[:, i] > INFLUENCE_WEIGHT_THRESHOLD)[0]

        # Filter 2: too few influenced vertices.
        if influence_idx.size < _MIN_INFLUENCE_VERTS:
            degenerate[names[i]] = "insufficient_influence_vertices"
            continue

        pts = vertices[influence_idx]
        centroid = pts.mean(axis=0)
        spread = float(np.sqrt(((pts - centroid) ** 2).sum(axis=1).mean()))

        # Filter 3: negligible influence extent.
        if spread < _MIN_INFLUENCE_SPREAD:
            degenerate[names[i]] = "negligible_spread"
            continue

        real[i] = {
            "world_pos": pos_i,
            "influence_verts": pts,
            "spread": spread,
            "d_nearest": float(np.linalg.norm(pts - pos_i, axis=1).min()),
        }
    return degenerate, real


def _run_falsifier_a(
    donor_ratios: Dict[str, float],
    fitted_ratios: Dict[str, float],
    degenerate_names: set,
) -> dict:
    """Rim-ratio preservation: |r_fitted - r_donor| / r_donor < RATIO_TOLERANCE.

    Skips degenerate bones and near-zero donor ratios.  On a self-fit (Drexl)
    this passes trivially — presence check, not calibration (T2510 debt).
    """
    violations: List[tuple] = []
    scored = 0
    for bone_name, r_donor in donor_ratios.items():
        if bone_name in degenerate_names or r_donor < 1e-6:
            continue
        scored += 1
        r_fitted = fitted_ratios.get(bone_name)
        if r_fitted is None:
            violations.append((bone_name, "missing_fitted_ratio"))
            continue
        relative_delta = abs(r_fitted - r_donor) / r_donor
        if relative_delta >= RATIO_TOLERANCE:
            violations.append(
                (
                    bone_name,
                    {
                        "r_donor": float(r_donor),
                        "r_fitted": float(r_fitted),
                        "relative_delta": float(relative_delta),
                    },
                )
            )
    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "tolerance_used": RATIO_TOLERANCE,
        "n_real_bones_scored": scored,
    }


def _run_falsifier_b(refinement_scale: float) -> dict:
    """Refinement-scale sanity bracket.

    Deliberately tighter than v2 solver's 0.1x-20x bracket
    (containment_fit.py:655-656); this guards the refinement step, not the
    containment solver.  Pre-alignment already matched global scale, so a
    refinement scale outside [0.5, 2.0] means the correspondence is not
    trustworthy (the balloon signature PR B's suite lacked a guard for).
    """
    passed = _SCALE_BRACKET_LOW <= refinement_scale <= _SCALE_BRACKET_HIGH
    return {
        "passed": bool(passed),
        "refinement_scale": float(refinement_scale),
        "bracket": [_SCALE_BRACKET_LOW, _SCALE_BRACKET_HIGH],
    }


def fit_skeleton_by_correspondence(
    imported_vertices: np.ndarray,  # (V, 3)
    imported_faces: np.ndarray,  # (F, 3)
    donor,  # DonorSkinData (duck-typed)
    *,
    use_v3: bool = False,
    random_seed: int = 42,
) -> Optional[CorrespondenceFitResult]:
    """Fit a similarity (s, R, t) mapping the donor mesh surface onto the
    imported mesh surface, then carry the donor skeleton rigidly by it.

    Behind the ``use_v3`` flag: the default ``False`` returns ``None`` with no
    side effects (caller falls back to the v1/v2 dispatch — wiring is PR D).

    Preconditions (raise ``ValueError``):
    - ``donor.frame == "world_space_v1"`` (frame-consistent donor, PR C.1)
    - ``donor.bone_names`` non-empty

    A failed falsifier is a *signal*, not an exception — the result is always
    returned; callers must check ``falsifier_b["passed"]`` before trusting the
    transform.
    """
    if not use_v3:
        return None

    frame = getattr(donor, "frame", "unspecified")
    if frame != "world_space_v1":
        raise ValueError(
            "correspondence fit requires a world-frame donor (PR C.1 builder "
            f'sets frame="world_space_v1"); got frame={frame!r}'
        )
    if not list(donor.bone_names):
        raise ValueError("donor has no bones")

    la = _load_math_sibling("landmark_alignment")
    containment = _load_math_sibling("containment_fit")
    import trimesh  # lazy — keep module import light

    donor_vertices = np.asarray(donor.vertices, dtype=np.float64)
    bone_positions = np.asarray(donor.bone_positions, dtype=np.float64)
    imported_vertices = np.asarray(imported_vertices, dtype=np.float64)
    imported_faces = np.asarray(imported_faces, dtype=np.int64)

    # ---- Stage 1: classify donor bones --------------------------------------
    degenerate, real_bones = _classify_donor_bones(donor)

    # ---- Stage 2: donor rim ratios (Falsifier A baseline) -------------------
    donor_ratios: Dict[str, float] = {}
    for i, info in real_bones.items():
        if info["spread"] > 1e-6:
            donor_ratios[donor.bone_names[i]] = info["d_nearest"] / info["spread"]

    # ---- Stage 3a: pre-alignment (shape-normalise + 24-rotation search) -----
    donor_norm, donor_centre, donor_rms = la.normalise_cloud(donor_vertices)
    imported_norm, imported_centre, imported_rms = la.normalise_cloud(imported_vertices)
    align_rotation = la.best_alignment_rotation(donor_norm, imported_norm)

    # Compose the normalised-frame alignment into an original-frame similarity
    # donor -> imported:  x_pre = s_pre * R_pre @ (x - c_D) + c_I
    s_pre = imported_rms / donor_rms
    r_pre = align_rotation
    t_pre = imported_centre - s_pre * (r_pre @ donor_centre)
    donor_pre = s_pre * (donor_vertices @ r_pre.T) + t_pre

    # ---- Stage 3b: nearest-surface correspondence ---------------------------
    imported_mesh = trimesh.Trimesh(
        vertices=imported_vertices, faces=imported_faces, process=False
    )
    proximity = trimesh.proximity.ProximityQuery(imported_mesh)
    closest_points, distances, _ = proximity.on_surface(donor_pre)
    weights = 1.0 / (1.0 + np.asarray(distances, dtype=np.float64))

    # ---- Stage 3c: weighted-Umeyama refinement ------------------------------
    r_refine, t_refine, s_refine = la.compute_weighted_rigid_transform(
        donor_pre, np.asarray(closest_points, dtype=np.float64), weights
    )

    # ---- Compose total = refinement ∘ pre-alignment -------------------------
    scale_total = float(s_refine * s_pre)
    rotation_total = r_refine @ r_pre
    translation_total = s_refine * (r_refine @ t_pre) + t_refine

    # ---- Stage 4: surface confidence (post-fit residual, diag-normalised) ---
    donor_fitted = scale_total * (donor_vertices @ rotation_total.T) + translation_total
    _, post_distances, _ = proximity.on_surface(donor_fitted)
    imported_diag = max(containment._bbox_diagonal(imported_vertices), 1e-9)
    mean_residual = float(np.mean(post_distances))
    surface_confidence = float(1.0 / (1.0 + mean_residual / imported_diag))

    # ---- Stage 5: rigid skeleton carry ---------------------------------------
    fitted_bone_positions = (
        scale_total * (bone_positions @ rotation_total.T) + translation_total
    )

    # ---- Stage 6: fitted rim ratios ------------------------------------------
    fitted_ratios: Dict[str, float] = {}
    for i, info in real_bones.items():
        fitted_influence = (
            scale_total * (info["influence_verts"] @ rotation_total.T) + translation_total
        )
        fitted_centroid = fitted_influence.mean(axis=0)
        fitted_spread = float(
            np.sqrt(((fitted_influence - fitted_centroid) ** 2).sum(axis=1).mean())
        )
        fitted_d_nearest = float(
            np.linalg.norm(fitted_influence - fitted_bone_positions[i], axis=1).min()
        )
        if fitted_spread > 1e-6:
            fitted_ratios[donor.bone_names[i]] = fitted_d_nearest / fitted_spread

    # ---- Stage 7: diagnostic initial scale estimate --------------------------
    # Formula source: containment_fit.py:587-589 (fit_skeleton_inside_mesh_v2).
    # DIAGNOSTIC ONLY: this is a containment heuristic, not the registration
    # scale — on Drexl it is ~8.99 while the total registration scale is ~0.11;
    # do not assert against it (falsified 2026-07-01 probe).
    mesh_diag = max(containment._bbox_diagonal(imported_vertices), 1e-9)
    bone_diag = max(containment._bbox_diagonal(bone_positions), 1e-9)
    initial_scale_estimate = float(bone_diag / mesh_diag * 1.2)

    # ---- Stage 8: falsifiers --------------------------------------------------
    falsifier_a = _run_falsifier_a(donor_ratios, fitted_ratios, set(degenerate.keys()))
    falsifier_b = _run_falsifier_b(float(s_refine))

    return CorrespondenceFitResult(
        scale=scale_total,
        rotation=rotation_total,
        translation=translation_total,
        fitted_bone_positions=fitted_bone_positions,
        surface_confidence=surface_confidence,
        falsifier_a=falsifier_a,
        falsifier_b=falsifier_b,
        degenerate_donor_bones=degenerate,
        real_bone_count=len(real_bones),
        initial_scale_estimate=initial_scale_estimate,
        diagnostics={
            "n_donor_vertices": int(donor_vertices.shape[0]),
            "n_imported_vertices": int(imported_vertices.shape[0]),
            "pre_alignment_scale": float(s_pre),
            "refinement_scale": float(s_refine),
            "total_scale": scale_total,
            "mean_correspondence_distance_pre_refine": float(np.mean(distances)),
            "mean_correspondence_distance_post_fit": mean_residual,
            "weight_min": float(weights.min()),
            "weight_max": float(weights.max()),
            "weight_mean": float(weights.mean()),
            "random_seed": int(random_seed),
        },
    )
