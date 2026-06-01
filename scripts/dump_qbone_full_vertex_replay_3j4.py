"""3j Step 4 - Full-vertex bind-pose replay against the env-gated G5 path.

The 3j-3 single-vertex replay tested 5 probe vertices per skin node and
proved that the G5_FULL_REF candidate (DFS index + W-first quaternion +
no inversion of T*R) collapses the bind-pose self-test on every probe.
3j-4 escalates that proof to **every weighted vertex** on the three
audit creatures (c_drexlf, c_brith, c_bomabeast), exercising the
production ``MatrixPaletteUploader`` directly under
``GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF`` so the result validates the
implementation actually shipped in ``src/core/gpu_skinning.py``.

For each skin node we compute the palette twice:

    F1   - production baseline (env unset, slot-indexed, X-first, inverted)
    G5   - env-gated reference (DFS-indexed, W-first, no invert)

For every vertex we then build the LBS-weighted world position::

    v_world_pred = sum_i w_i * palette[slot_i] * v_local

and compare against the bind-pose ground truth::

    v_world_expected = skin_world * v_local

The G5 path must satisfy ``|v_world_pred - v_world_expected| <=
DISPLACEMENT_TOLERANCE`` for **every** weighted vertex by construction
(its inverse-bind matrix equals ``inverse(bone_world) * skin_world`` per
reone's documented convention). F1 is expected to fail on a large
fraction of vertices because it builds inverse binds from the wrong
slot and convention.

Output (one JSONL per creature plus a summary):

    diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_drexlf.jsonl
    diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_brith.jsonl
    diagnostics/skinning/2026_05/qbone_full_vertex_replay_3j4_c_bomabeast.jsonl

Each file's first record is the creature summary (counts, percentile
displacements, decision verdict). Subsequent records are per-skin-node
roll-ups (no per-vertex records to keep file sizes manageable on a
multi-thousand-vertex creature).

Usage::

    python scripts/dump_qbone_full_vertex_replay_3j4.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K1_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
K2_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

OUT_DIR = ROOT / "diagnostics" / "skinning" / "2026_05"

TARGETS: Tuple[Tuple[str, str, str], ...] = (
    ("c_drexlf",    "K2", "qbone_full_vertex_replay_3j4_c_drexlf.jsonl"),
    ("c_brith",     "K2", "qbone_full_vertex_replay_3j4_c_brith.jsonl"),
    ("c_bomabeast", "K1", "qbone_full_vertex_replay_3j4_c_bomabeast.jsonl"),
)

# Tolerance budget: the production palette stores float32 column-major
# matrices and we replay through Python floats, so a healthy headroom
# above the float32 epsilon is appropriate. 1e-3 mirrors the 3j-3
# DISPLACEMENT_TOLERANCE so the verdicts compare apples-to-apples.
DISPLACEMENT_TOLERANCE = 1e-3


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _apply_mat4_row_major(m: List[List[float]],
                          v: Tuple[float, float, float]
                          ) -> Tuple[float, float, float]:
    """Transform a position by a 4x4 row-major affine matrix."""
    x = m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2] + m[0][3]
    y = m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2] + m[1][3]
    z = m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2] + m[2][3]
    return (x, y, z)


def _vec3_norm(v: Tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _vec3_sub(a: Tuple[float, float, float],
              b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _palette_to_row_major(palette_records) -> List[List[List[float]]]:
    """Convert ``BoneMatrix.flat_col`` (column-major) to row-major 4x4 lists.

    Mirrors ``MatrixPaletteUploader.as_numpy_array`` but keeps the
    output as nested Python lists so this script has no NumPy hard
    dependency for the replay maths.
    """
    out: List[List[List[float]]] = []
    for bm in palette_records:
        col = bm.flat_col
        m: List[List[float]] = [[0.0] * 4 for _ in range(4)]
        for r in range(4):
            for c in range(4):
                m[r][c] = float(col[c * 4 + r])
        out.append(m)
    return out


# ---------------------------------------------------------------------------
# Per-skin-node replay
# ---------------------------------------------------------------------------


def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if pct <= 0.0:
        return sorted_values[0]
    if pct >= 100.0:
        return sorted_values[-1]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return sorted_values[lo]
    frac = rank - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _replay_skin_node_full(
    *, skin_node: Any, uploader: Any, formula_label: str,
) -> Dict[str, Any]:
    """Replay every weighted vertex on a single skin node.

    The uploader's env state must already be configured (caller is
    responsible for setting/clearing ``GHOSTRIGGER_SKIN_FORMULA``). This
    function builds the palette via the production code path, then
    iterates every (vertex, influence) tuple and accumulates the
    weighted predicted position.
    """
    bone_map = list(getattr(skin_node, "bone_map", []) or [])
    vertices = list(getattr(skin_node, "vertices", []) or [])
    skin_data = list(getattr(skin_node, "skin_data", []) or [])
    if not vertices or not skin_data or not bone_map:
        return {
            "skin_node_name": str(getattr(skin_node, "name", "") or ""),
            "vertices_total": len(vertices),
            "vertices_weighted": 0,
            "vertices_collapsed": 0,
            "skipped_reason": "no_vertices_skin_data_or_bone_map",
        }

    uploader.compute_skin_node_palette(skin_node, anim_pose=None)
    palette = _palette_to_row_major(uploader.palette)
    if not palette:
        return {
            "skin_node_name": str(getattr(skin_node, "name", "") or ""),
            "vertices_total": len(vertices),
            "vertices_weighted": 0,
            "vertices_collapsed": 0,
            "skipped_reason": "empty_palette",
        }

    # ``_skin_bind_matrix`` is the row-major skin_world built inside
    # ``compute_skin_node_palette`` from the same hierarchy walk that
    # produced the palette. Using it (rather than a freshly computed
    # value) guarantees the comparison reflects exactly what production
    # would render with.
    skin_world = uploader._skin_bind_matrix
    if skin_world is None:
        return {
            "skin_node_name": str(getattr(skin_node, "name", "") or ""),
            "vertices_total": len(vertices),
            "vertices_weighted": 0,
            "vertices_collapsed": 0,
            "skipped_reason": "missing_skin_bind_matrix",
        }

    n = min(len(vertices), len(skin_data))
    palette_len = len(palette)
    bone_map_len = len(bone_map)

    displacements: List[float] = []
    weighted_vertices = 0
    collapsed = 0
    worst_displacement = 0.0
    worst_vertex_index = -1
    skipped_zero_weight = 0
    skipped_out_of_palette = 0

    for vidx in range(n):
        v_raw = vertices[vidx]
        v_local: Tuple[float, float, float] = (
            float(v_raw[0]), float(v_raw[1]), float(v_raw[2])
        )
        sd = skin_data[vidx]
        influences = list(getattr(sd, "influences", []) or [])

        weight_sum = 0.0
        v_pred: List[float] = [0.0, 0.0, 0.0]
        had_valid_influence = False
        for inf in influences:
            local_idx = int(getattr(inf, "bone_index", -1))
            weight = float(getattr(inf, "weight", 0.0))
            if weight <= 0.0:
                continue
            if local_idx < 0 or local_idx >= bone_map_len:
                skipped_out_of_palette += 1
                continue
            if local_idx >= palette_len:
                skipped_out_of_palette += 1
                continue
            had_valid_influence = True
            m = palette[local_idx]
            x = (m[0][0] * v_local[0] + m[0][1] * v_local[1]
                 + m[0][2] * v_local[2] + m[0][3])
            y = (m[1][0] * v_local[0] + m[1][1] * v_local[1]
                 + m[1][2] * v_local[2] + m[1][3])
            z = (m[2][0] * v_local[0] + m[2][1] * v_local[1]
                 + m[2][2] * v_local[2] + m[2][3])
            v_pred[0] += weight * x
            v_pred[1] += weight * y
            v_pred[2] += weight * z
            weight_sum += weight

        if not had_valid_influence or weight_sum <= 1e-6:
            skipped_zero_weight += 1
            continue

        v_pred_t: Tuple[float, float, float] = (
            v_pred[0] / weight_sum,
            v_pred[1] / weight_sum,
            v_pred[2] / weight_sum,
        )
        v_expected = _apply_mat4_row_major(skin_world, v_local)
        disp = _vec3_norm(_vec3_sub(v_pred_t, v_expected))

        weighted_vertices += 1
        displacements.append(disp)
        if disp <= DISPLACEMENT_TOLERANCE:
            collapsed += 1
        if disp > worst_displacement:
            worst_displacement = disp
            worst_vertex_index = vidx

    sorted_d = sorted(displacements)
    return {
        "skin_node_name": str(getattr(skin_node, "name", "") or ""),
        "formula": formula_label,
        "palette_formula_recorded": uploader._skin_palette_formula,
        "inverse_bind_source_recorded": uploader._skin_inverse_bind_source,
        "vertices_total": int(n),
        "vertices_weighted": int(weighted_vertices),
        "vertices_collapsed_within_tolerance": int(collapsed),
        "collapse_fraction": (
            float(collapsed) / float(weighted_vertices)
            if weighted_vertices else 0.0
        ),
        "displacement_max": float(worst_displacement),
        "displacement_median": float(_percentile(sorted_d, 50.0)),
        "displacement_p95": float(_percentile(sorted_d, 95.0)),
        "displacement_p99": float(_percentile(sorted_d, 99.0)),
        "worst_vertex_index": int(worst_vertex_index),
        "skipped_zero_weight": int(skipped_zero_weight),
        "skipped_out_of_palette": int(skipped_out_of_palette),
        "tolerance_displacement": DISPLACEMENT_TOLERANCE,
    }


def _aggregate_creature(per_node_records: List[Dict[str, Any]],
                        formula_label: str) -> Dict[str, Any]:
    total_weighted = 0
    total_collapsed = 0
    total_skin_nodes_with_data = 0
    worst_displacement = 0.0
    nodes_fully_collapsed = 0
    per_node_fraction: List[float] = []
    for rec in per_node_records:
        if rec.get("skipped_reason"):
            continue
        total_skin_nodes_with_data += 1
        wv = int(rec.get("vertices_weighted", 0))
        col = int(rec.get("vertices_collapsed_within_tolerance", 0))
        total_weighted += wv
        total_collapsed += col
        worst_displacement = max(
            worst_displacement,
            float(rec.get("displacement_max", 0.0)),
        )
        per_node_fraction.append(float(rec.get("collapse_fraction", 0.0)))
        if wv > 0 and col == wv:
            nodes_fully_collapsed += 1
    overall_fraction = (
        float(total_collapsed) / float(total_weighted)
        if total_weighted else 0.0
    )
    return {
        "formula": formula_label,
        "skin_nodes_with_data": total_skin_nodes_with_data,
        "skin_nodes_fully_collapsed": nodes_fully_collapsed,
        "vertices_weighted_total": total_weighted,
        "vertices_collapsed_total": total_collapsed,
        "collapse_fraction_overall": overall_fraction,
        "displacement_max_overall": worst_displacement,
        "tolerance_displacement": DISPLACEMENT_TOLERANCE,
    }


def _verdict(g5_agg: Dict[str, Any], f1_agg: Dict[str, Any]) -> str:
    """Compute the final per-creature verdict for the audit doc."""
    g5_collapsed = (
        g5_agg["vertices_weighted_total"] > 0
        and g5_agg["collapse_fraction_overall"] >= 1.0 - 1e-9
        and g5_agg["displacement_max_overall"] <= DISPLACEMENT_TOLERANCE
    )
    f1_failed = (
        f1_agg["vertices_weighted_total"] > 0
        and f1_agg["collapse_fraction_overall"] < 1.0 - 1e-9
    )
    if g5_collapsed and f1_failed:
        return "G5_PASSES_FULL_VERTEX_REPLAY_F1_FAILS"
    if g5_collapsed and not f1_failed:
        return "G5_AND_F1_BOTH_PASS_NO_REGRESSION_RISK"
    if not g5_collapsed and not f1_failed:
        return "G5_REGRESSES_VS_F1"
    return "G5_AND_F1_BOTH_FAIL_FURTHER_AUDIT_NEEDED"


# ---------------------------------------------------------------------------
# Per-creature driver
# ---------------------------------------------------------------------------


def _dump_one(rm: Any, resref: str, game: str, out_path: Path) -> int:
    from src.core.animation.gpu_skinning import (
        MatrixPaletteUploader,
        _SKIN_FORMULA_ENV,
        _SKIN_FORMULA_F1,
        _SKIN_FORMULA_G5,
    )

    model = rm.load_model(resref, game)
    if model is None:
        print(f"[3j-4] ERR: failed to load {resref} from {game}",
              file=sys.stderr)
        return 0

    all_nodes = list(model.all_nodes())
    skin_nodes = [n for n in all_nodes if getattr(n, "is_skin", False)]

    # Run G5 first so its env state never leaks into F1's run; then run
    # F1 with the env explicitly cleared. Each formula gets a fresh
    # uploader so the palette state from one cannot contaminate the other.
    g5_records: List[Dict[str, Any]] = []
    os.environ[_SKIN_FORMULA_ENV] = _SKIN_FORMULA_G5
    try:
        uploader_g5 = MatrixPaletteUploader()
        uploader_g5.build_inverse_bind_pose(model)
        for node in skin_nodes:
            g5_records.append(_replay_skin_node_full(
                skin_node=node,
                uploader=uploader_g5,
                formula_label=_SKIN_FORMULA_G5,
            ))
    finally:
        os.environ.pop(_SKIN_FORMULA_ENV, None)

    f1_records: List[Dict[str, Any]] = []
    uploader_f1 = MatrixPaletteUploader()
    uploader_f1.build_inverse_bind_pose(model)
    for node in skin_nodes:
        f1_records.append(_replay_skin_node_full(
            skin_node=node,
            uploader=uploader_f1,
            formula_label=_SKIN_FORMULA_F1,
        ))

    g5_agg = _aggregate_creature(g5_records, "G5_FULL_REF")
    f1_agg = _aggregate_creature(f1_records, "F1_current_TR_inverse")

    verdict = _verdict(g5_agg, f1_agg)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_kind": "creature_summary",
            "_generated_by": "scripts/dump_qbone_full_vertex_replay_3j4.py",
            "_generated_at": time.time(),
            "resref": resref,
            "game": game,
            "skin_nodes_total": len(skin_nodes),
            "G5_FULL_REF_aggregate": g5_agg,
            "F1_current_TR_inverse_aggregate": f1_agg,
            "verdict": verdict,
        }, sort_keys=True))
        fh.write("\n")
        for rec in g5_records:
            fh.write(json.dumps({"_kind": "g5_per_node", **rec},
                                sort_keys=True))
            fh.write("\n")
        for rec in f1_records:
            fh.write(json.dumps({"_kind": "f1_per_node", **rec},
                                sort_keys=True))
            fh.write("\n")

    print(f"[3j-4] {game}:{resref} -> {out_path.name}: "
          f"G5 collapsed {g5_agg['vertices_collapsed_total']}/"
          f"{g5_agg['vertices_weighted_total']} "
          f"({100.0 * g5_agg['collapse_fraction_overall']:.2f}%) "
          f"max disp {g5_agg['displacement_max_overall']:.3e} | "
          f"F1 collapsed {f1_agg['vertices_collapsed_total']}/"
          f"{f1_agg['vertices_weighted_total']} "
          f"({100.0 * f1_agg['collapse_fraction_overall']:.2f}%) | "
          f"verdict {verdict}")
    return g5_agg["vertices_weighted_total"]


def main() -> int:
    from src.core.assets.resource_manager import ResourceManager

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[3j-4] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[3j-4] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        print("[3j-4] FATAL: no game install indexed", file=sys.stderr)
        return 2

    total = 0
    for resref, game, name in TARGETS:
        total += _dump_one(rm, resref, game, OUT_DIR / name)
    print(f"[3j-4] total weighted vertices replayed: {total}")
    return 0 if total else 3


if __name__ == "__main__":
    raise SystemExit(main())
