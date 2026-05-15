"""3j Step 2 - qBone/tBone consumption convention replay.

Reads the 3j-1 byte-parity dumps and reconstructs the per-bone bind
matrix under each of the four engine conventions audited in 3j-2:

    F1_GHOSTRIGGER     : XYZW byte order, T * R, INVERTED
                         (current production via qbone_inverse_bind_matrix)

    G1_GR_NO_INVERT    : XYZW byte order, T * R, NOT inverted
                         (Outcome A only - fix invert direction, leave
                          PyKotor's wrong byte order in place)

    G2_REF_BYTE_ORDER  : WXYZ byte order, T * R, INVERTED
                         (Outcome C only - fix byte order, leave the
                          spurious invert in place)

    G3_REF_FULL        : WXYZ byte order, T * R, NOT inverted
                         (Outcomes A AND C together - matches KotOR.js
                          and reone exactly; the candidate to beat in
                          the 3j-3 single-vertex replay)

For each slot record from the 3j-1 dump, this script writes:

    - qBone components under each byte order
    - quaternion axis + angle under each byte order
    - 4x4 bind matrix under each of the four conventions
    - rotation matrix max-abs delta vs G3_REF_FULL (the reference)
    - translation column delta vs G3_REF_FULL

Outputs (one JSONL per audited creature):

    diagnostics/skinning/2026_05/qbone_consumption_replay_c_drexlf.jsonl
    diagnostics/skinning/2026_05/qbone_consumption_replay_c_brith.jsonl
    diagnostics/skinning/2026_05/qbone_consumption_replay_c_bomabeast.jsonl

Each JSONL has one ``_creature_summary`` row first, then one record per
slot. Reduction is straightforward: any non-zero ``vs_G3_REF_FULL_delta``
means GhostRigger's per-bone bind matrix differs from what KotOR.js /
reone would build from the same on-disk bytes.

Usage::

    python scripts/dump_qbone_consumption_replay.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PARITY_DIR = ROOT / "diagnostics" / "skinning" / "2026_05"

TARGETS: Tuple[Tuple[str, str, str], ...] = (
    ("c_drexlf",    "qbone_byte_parity_c_drexlf.jsonl",
                    "qbone_consumption_replay_c_drexlf.jsonl"),
    ("c_brith",     "qbone_byte_parity_c_brith.jsonl",
                    "qbone_consumption_replay_c_brith.jsonl"),
    ("c_bomabeast", "qbone_byte_parity_c_bomabeast.jsonl",
                    "qbone_consumption_replay_c_bomabeast.jsonl"),
)


def _normalize_quat(qx: float, qy: float, qz: float, qw: float
                    ) -> Tuple[float, float, float, float]:
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if n < 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    return (qx / n, qy / n, qz / n, qw / n)


def _quat_to_mat3(qx: float, qy: float, qz: float, qw: float
                  ) -> List[List[float]]:
    qx, qy, qz, qw = _normalize_quat(qx, qy, qz, qw)
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return [
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ]


def _quat_axis_angle_deg(qx: float, qy: float, qz: float, qw: float
                         ) -> Tuple[float, float, float, float]:
    qx, qy, qz, qw = _normalize_quat(qx, qy, qz, qw)
    # Force qw >= 0 so axis sign is canonical.
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    angle = 2.0 * math.acos(max(-1.0, min(1.0, qw)))
    s = math.sqrt(max(0.0, 1.0 - qw * qw))
    if s < 1e-6:
        return (1.0, 0.0, 0.0, 0.0)
    return (qx / s, qy / s, qz / s, math.degrees(angle))


def _mat3_to_mat4(m3: List[List[float]], tx: float, ty: float, tz: float
                  ) -> List[List[float]]:
    """Build T(t) * R(m3) as a 4x4 row-major matrix."""
    return [
        [m3[0][0], m3[0][1], m3[0][2], tx],
        [m3[1][0], m3[1][1], m3[1][2], ty],
        [m3[2][0], m3[2][1], m3[2][2], tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_invert(m: List[List[float]]) -> List[List[float]]:
    """Invert a 4x4 affine matrix [R|t; 0 0 0 1] using transpose-of-rotation
    plus -R^T*t for the translation column. Returns identity on failure."""
    r00, r01, r02 = m[0][0], m[0][1], m[0][2]
    r10, r11, r12 = m[1][0], m[1][1], m[1][2]
    r20, r21, r22 = m[2][0], m[2][1], m[2][2]
    tx, ty, tz = m[0][3], m[1][3], m[2][3]
    # Inverse of pure rotation = transpose
    irx = -(r00 * tx + r10 * ty + r20 * tz)
    iry = -(r01 * tx + r11 * ty + r21 * tz)
    irz = -(r02 * tx + r12 * ty + r22 * tz)
    return [
        [r00, r10, r20, irx],
        [r01, r11, r21, iry],
        [r02, r12, r22, irz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_max_abs_delta(a: List[List[float]], b: List[List[float]]) -> float:
    worst = 0.0
    for r in range(4):
        for c in range(4):
            worst = max(worst, abs(a[r][c] - b[r][c]))
    return worst


def _mat4_translation_column_delta(a: List[List[float]],
                                   b: List[List[float]]) -> float:
    worst = 0.0
    for r in range(3):
        worst = max(worst, abs(a[r][3] - b[r][3]))
    return worst


def _mat4_rotation_max_abs_delta(a: List[List[float]],
                                 b: List[List[float]]) -> float:
    worst = 0.0
    for r in range(3):
        for c in range(3):
            worst = max(worst, abs(a[r][c] - b[r][c]))
    return worst


def _build_candidates(raw_q: List[float], raw_t: List[float]
                      ) -> Dict[str, List[List[float]]]:
    """Build all four candidate bind matrices from the same on-disk bytes."""
    # GhostRigger convention: (X,Y,Z,W) with X first
    gr_q = (raw_q[0], raw_q[1], raw_q[2], raw_q[3])
    # Reference convention: (W,X,Y,Z) with W first; remap to our (qx,qy,qz,qw)
    ref_q = (raw_q[1], raw_q[2], raw_q[3], raw_q[0])

    tx, ty, tz = raw_t[0], raw_t[1], raw_t[2]

    gr_TR = _mat3_to_mat4(_quat_to_mat3(*gr_q), tx, ty, tz)
    ref_TR = _mat3_to_mat4(_quat_to_mat3(*ref_q), tx, ty, tz)

    return {
        "F1_GHOSTRIGGER":    _mat4_invert(gr_TR),  # current production
        "G1_GR_NO_INVERT":   gr_TR,                # fix only the invert
        "G2_REF_BYTE_ORDER": _mat4_invert(ref_TR), # fix only the byte order
        "G3_REF_FULL":       ref_TR,               # fix both: matches KotOR.js / reone
    }


def _summarize_creature(slot_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(slot_records)
    counts = {
        "F1_GHOSTRIGGER_eq_G3_REF_FULL": 0,
        "G1_GR_NO_INVERT_eq_G3_REF_FULL": 0,
        "G2_REF_BYTE_ORDER_eq_G3_REF_FULL": 0,
    }
    worst = {
        "F1_GHOSTRIGGER_vs_G3_REF_FULL_max_abs": 0.0,
        "G1_GR_NO_INVERT_vs_G3_REF_FULL_max_abs": 0.0,
        "G2_REF_BYTE_ORDER_vs_G3_REF_FULL_max_abs": 0.0,
    }
    worst_rot = {
        "F1_GHOSTRIGGER_vs_G3_REF_FULL_rotation_max_abs": 0.0,
        "G1_GR_NO_INVERT_vs_G3_REF_FULL_rotation_max_abs": 0.0,
        "G2_REF_BYTE_ORDER_vs_G3_REF_FULL_rotation_max_abs": 0.0,
    }
    for rec in slot_records:
        diffs = rec["vs_G3_REF_FULL"]
        for key in counts:
            base = key.replace("_eq_G3_REF_FULL", "")
            if diffs[base + "_max_abs"] <= 1e-6:
                counts[key] += 1
        for k in worst:
            base = k.replace("_vs_G3_REF_FULL_max_abs", "")
            worst[k] = max(worst[k], diffs[base + "_max_abs"])
        for k in worst_rot:
            base = k.replace("_vs_G3_REF_FULL_rotation_max_abs", "")
            worst_rot[k] = max(worst_rot[k],
                               diffs[base + "_rotation_max_abs"])
    return {
        "slots_total": n,
        "candidate_matches_reference_count": counts,
        "candidate_vs_reference_max_abs": worst,
        "candidate_vs_reference_rotation_max_abs": worst_rot,
        "interpretation": (
            "G3_REF_FULL is the convention KotOR.js and reone both apply: "
            "WXYZ byte order, T*R, NOT inverted. F1_GHOSTRIGGER (current "
            "production) differs from G3 by both invert direction (Outcome A) "
            "and quaternion byte order (Outcome C). G1 and G2 isolate each "
            "bug; both should still differ materially from G3 because the "
            "two bugs do not cancel. G3_REF_FULL is the candidate the 3j-3 "
            "single-vertex replay should reconstruct numerically before any "
            "wrapper or visual gate."
        ),
    }


def _dump_one(parity_path: Path, out_path: Path, resref: str) -> int:
    if not parity_path.exists():
        print(f"[3j-2] ERR: parity dump not found: {parity_path}",
              file=sys.stderr)
        return 0

    slot_records: List[Dict[str, Any]] = []
    with parity_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("_kind") != "slot_parity":
                continue

            raw_q = rec["qbone"]["raw"]
            raw_t = rec["tbone"]["raw"]

            if not all(math.isfinite(v) for v in raw_q + raw_t):
                continue

            cands = _build_candidates(raw_q, raw_t)
            ref = cands["G3_REF_FULL"]
            diffs: Dict[str, float] = {}
            for key, m in cands.items():
                if key == "G3_REF_FULL":
                    continue
                diffs[key + "_max_abs"] = _mat4_max_abs_delta(m, ref)
                diffs[key + "_rotation_max_abs"] = (
                    _mat4_rotation_max_abs_delta(m, ref))
                diffs[key + "_translation_max_abs"] = (
                    _mat4_translation_column_delta(m, ref))

            gr_axis = _quat_axis_angle_deg(
                raw_q[0], raw_q[1], raw_q[2], raw_q[3])
            ref_axis = _quat_axis_angle_deg(
                raw_q[1], raw_q[2], raw_q[3], raw_q[0])

            slot_records.append({
                "_kind": "consumption_candidate",
                "resref": resref,
                "skin_node_name": rec["skin_node_name"],
                "node_id": rec["node_id"],
                "slot": rec["slot"],
                "bone_name_from_ghostrigger_bone_map": (
                    rec["bone_name_from_ghostrigger_bone_map"]),
                "raw_qbone_bytes_as_4f": list(raw_q),
                "raw_tbone_bytes_as_3f": list(raw_t),
                "as_xyzw_axis_xyz_then_angle_deg": list(gr_axis),
                "as_wxyz_axis_xyz_then_angle_deg": list(ref_axis),
                "candidates": {k: [list(row) for row in m]
                               for k, m in cands.items()},
                "vs_G3_REF_FULL": diffs,
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_kind": "creature_summary",
            "_generated_by": "scripts/dump_qbone_consumption_replay.py",
            "_generated_at": time.time(),
            "resref": resref,
            "summary": _summarize_creature(slot_records),
        }, sort_keys=True))
        fh.write("\n")
        for rec in slot_records:
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")

    print(f"[3j-2] {resref} -> {out_path.name}: {len(slot_records)} slots replayed")
    return len(slot_records)


def main() -> int:
    total = 0
    for resref, parity_name, replay_name in TARGETS:
        total += _dump_one(
            PARITY_DIR / parity_name,
            PARITY_DIR / replay_name,
            resref,
        )
    print(f"[3j-2] total slot records replayed: {total}")
    return 0 if total else 3


if __name__ == "__main__":
    raise SystemExit(main())
