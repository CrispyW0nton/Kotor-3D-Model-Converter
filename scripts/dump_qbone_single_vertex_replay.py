"""3j Step 3 - Single-vertex end-to-end replay against the reference convention.

This script implements the bind-pose self-test for THREE candidate consumption
pipelines:

    F1_GHOSTRIGGER  - current production:
                      qbones[bone_map_slot] interpreted as (qx,qy,qz,qw),
                      build T*R, then INVERT.

    G3_REF_FULL     - 3j-2's "two compounding bugs fixed" candidate:
                      qbones[bone_map_slot] interpreted as (qw,qx,qy,qz),
                      build T*R, do NOT invert.
                      NOTE: still uses the WRONG indexing (per-skin-node slot,
                      not global DFS), which is why it failed the 3j-3 self
                      test on the first run.

    G5_FULL_REF     - 3j-3's three-compounding-bugs-fixed candidate:
                      LOOK UP the bone's GLOBAL DFS NODE INDEX, then read
                      qbones[dfs_idx]/tbones[dfs_idx], interpret as W-first,
                      build T*R, do NOT invert. This is reone's actual
                      consumption convention (mdlmdxreader.cpp + modelnode.h).

The bind-pose self-test:

    In bind pose, each per-bone skinning matrix M_i = bone_world * inv_bind_i
    must reduce to skin_world (NOT identity), because the LBS chain in a
    NODE_LOCAL vertex pipeline is:

        v_world = sum_i w_i * bone_world_anim_i * inv_bind_i * v_local

    where inv_bind_i = inverse(bone_world_bind_i) * skin_world. In bind pose,
    bone_world_anim == bone_world_bind, so the chain collapses to:

        v_world_bind = (sum_i w_i) * skin_world * v_local
                     = skin_world * v_local

    which is the correct world-space position of the bind-pose vertex.

    G5_FULL_REF must produce per_bone_matrix == skin_world (and therefore
    weighted final position == skin_world * v_local) on every probe by
    construction. F1 and G3 will not, because they feed inv_bind values
    that do not equal inverse(bone_world_bind) * skin_world.

Per the 3j-3 user brief, each probe record dumps for every bone influence:

    - authored qBone quaternion bytes (raw 4 floats from disk)
    - interpreted quaternion under current GhostRigger (X,Y,Z,W) convention
    - interpreted quaternion under reference (W,X,Y,Z) byte remap
    - T * R matrix before any inversion (under both conventions)
    - the bone's actual DFS node index in the model
    - the qbones[]/tbones[] entry at that DFS index (the value the reference
      engine actually reads for this bone) and its T*R
    - F1 stored inverse-bind matrix (= inverse of T*R under GR convention,
      slot-indexed)
    - G3_REF_FULL stored inverse-bind matrix (= T*R under reference convention,
      slot-indexed)
    - G5_FULL_REF stored inverse-bind matrix (= T*R under reference
      convention, DFS-indexed)
    - bone_world matrix (bind-pose, walked from node hierarchy)
    - skin_world matrix (bind-pose for the skin node)
    - F1, G3, G5 per-bone matrices (= bone_world * inv_bind_*)
    - F1, G3, G5 max-abs deltas vs the expected per-bone matrix in bind pose
      (which is skin_world)
    - post-qBone single-bone transformed position for F1, G3, G5
    - post-bone-world single-bone transformed position for F1, G3, G5
    - final weighted replay position for F1, G3, G5
    - bind-pose displacement |weighted - skin_world * v_local| for F1, G3, G5
      (THE decision metric: G5 should be ~0 by construction)
    - first divergence stage classification

Probe selection per skin node: vertex indices 0, N//4, N//2, 3*N//4, N-1
(deduplicated, capped at the node's vertex count). Five probes per skin
node when the node has >= 5 vertices.

Outputs (one JSONL per audited creature, plus a summary text):

    diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_drexlf.jsonl
    diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_brith.jsonl
    diagnostics/skinning/2026_05/qbone_single_vertex_replay_c_bomabeast.jsonl

Usage::

    python scripts/dump_qbone_single_vertex_replay.py
"""

from __future__ import annotations

import json
import math
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
    ("c_drexlf",    "K2", "qbone_single_vertex_replay_c_drexlf.jsonl"),
    ("c_brith",     "K2", "qbone_single_vertex_replay_c_brith.jsonl"),
    ("c_bomabeast", "K1", "qbone_single_vertex_replay_c_bomabeast.jsonl"),
)

# Tolerance for "matches identity" in the bind-pose self-test. The matrix
# arithmetic here is single-precision float32 + double-precision Python
# composition; an ideal G3 should be within ~1e-4 of identity. F1 will be
# off by units, so the threshold has plenty of headroom.
IDENTITY_TOLERANCE = 1e-3
DISPLACEMENT_TOLERANCE = 1e-3


# ---------------------------------------------------------------------------
# Math helpers (kept self-contained so the script is auditable without
# importing GhostRigger's internal helpers, even though they would agree).
# ---------------------------------------------------------------------------


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


def _mat4_identity() -> List[List[float]]:
    return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]


def _build_TR(qx: float, qy: float, qz: float, qw: float,
              tx: float, ty: float, tz: float) -> List[List[float]]:
    """Build T(t) * R(q) as a 4x4 row-major matrix."""
    r = _quat_to_mat3(qx, qy, qz, qw)
    return [
        [r[0][0], r[0][1], r[0][2], tx],
        [r[1][0], r[1][1], r[1][2], ty],
        [r[2][0], r[2][1], r[2][2], tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_invert_affine(m: List[List[float]]) -> List[List[float]]:
    """Inverse of an affine matrix [R | t]; assumes R is orthonormal."""
    r00, r01, r02 = m[0][0], m[0][1], m[0][2]
    r10, r11, r12 = m[1][0], m[1][1], m[1][2]
    r20, r21, r22 = m[2][0], m[2][1], m[2][2]
    tx, ty, tz = m[0][3], m[1][3], m[2][3]
    irx = -(r00 * tx + r10 * ty + r20 * tz)
    iry = -(r01 * tx + r11 * ty + r21 * tz)
    irz = -(r02 * tx + r12 * ty + r22 * tz)
    return [
        [r00, r10, r20, irx],
        [r01, r11, r21, iry],
        [r02, r12, r22, irz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_mul(a: List[List[float]],
              b: List[List[float]]) -> List[List[float]]:
    out = [[0.0] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            out[r][c] = sum(a[r][k] * b[k][c] for k in range(4))
    return out


def _apply_mat4(m: List[List[float]],
                v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x = m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2] + m[0][3]
    y = m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2] + m[1][3]
    z = m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2] + m[2][3]
    return (x, y, z)


def _max_abs_delta_4x4(a: List[List[float]],
                       b: List[List[float]]) -> float:
    worst = 0.0
    for r in range(4):
        for c in range(4):
            worst = max(worst, abs(a[r][c] - b[r][c]))
    return worst


def _vec3_norm(v: Tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _vec3_sub(a: Tuple[float, float, float],
              b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


# ---------------------------------------------------------------------------
# Probe selection and replay
# ---------------------------------------------------------------------------


def _probe_indices(vertex_count: int, target: int = 5) -> List[int]:
    if vertex_count <= 0:
        return []
    if vertex_count <= target:
        return list(range(vertex_count))
    quarters = [0, vertex_count // 4, vertex_count // 2,
                (3 * vertex_count) // 4, vertex_count - 1]
    seen: List[int] = []
    for idx in quarters:
        if 0 <= idx < vertex_count and idx not in seen:
            seen.append(idx)
    return seen


def _build_per_bone_replay(
    *, qbone_xyzw_at_slot: Tuple[float, float, float, float],
    tbone_at_slot: Tuple[float, float, float],
    qbone_xyzw_at_dfs: Tuple[float, float, float, float],
    tbone_at_dfs: Tuple[float, float, float],
    bone_dfs_index: int,
    bone_world: List[List[float]],
    skin_world: List[List[float]],
    v_bind: Tuple[float, float, float],
) -> Dict[str, Any]:
    """Build the F1 vs G3 vs G5 per-bone replay record for a single bone."""

    # F1 / GhostRigger production: slot-indexed, XYZW byte order, INVERTED.
    f1_qx, f1_qy, f1_qz, f1_qw = qbone_xyzw_at_slot
    f1_TR = _build_TR(f1_qx, f1_qy, f1_qz, f1_qw,
                      tbone_at_slot[0], tbone_at_slot[1], tbone_at_slot[2])
    f1_inv_bind = _mat4_invert_affine(f1_TR)

    # G3_REF_FULL (3j-2): slot-indexed (still wrong), W-first byte order,
    # NOT inverted. Tests the "two compounding bugs fixed" hypothesis.
    g3_qx, g3_qy, g3_qz, g3_qw = (
        qbone_xyzw_at_slot[1], qbone_xyzw_at_slot[2],
        qbone_xyzw_at_slot[3], qbone_xyzw_at_slot[0],
    )
    g3_TR = _build_TR(g3_qx, g3_qy, g3_qz, g3_qw,
                      tbone_at_slot[0], tbone_at_slot[1], tbone_at_slot[2])
    g3_inv_bind = g3_TR

    # G5_FULL_REF (3j-3): DFS-indexed, W-first byte order, NOT inverted.
    # This is reone's actual mdlmdxreader convention: qBone[bone_dfs] read
    # W-first into glm::quat(w,x,y,z), then T*R, stored as
    # "inverse of bone transform in this node space" (modelnode.h:40).
    g5_qx, g5_qy, g5_qz, g5_qw = (
        qbone_xyzw_at_dfs[1], qbone_xyzw_at_dfs[2],
        qbone_xyzw_at_dfs[3], qbone_xyzw_at_dfs[0],
    )
    g5_TR = _build_TR(g5_qx, g5_qy, g5_qz, g5_qw,
                      tbone_at_dfs[0], tbone_at_dfs[1], tbone_at_dfs[2])
    g5_inv_bind = g5_TR

    # Per-bone skinning matrix M_i = bone_world * inv_bind_i.
    # In bind pose, the correct M_i collapses to skin_world (NOT identity).
    f1_per_bone = _mat4_mul(bone_world, f1_inv_bind)
    g3_per_bone = _mat4_mul(bone_world, g3_inv_bind)
    g5_per_bone = _mat4_mul(bone_world, g5_inv_bind)

    # Stage 1: post-qBone single-bone transformed position
    # (inv_bind * v_local).
    f1_post_qbone = _apply_mat4(f1_inv_bind, v_bind)
    g3_post_qbone = _apply_mat4(g3_inv_bind, v_bind)
    g5_post_qbone = _apply_mat4(g5_inv_bind, v_bind)

    # Stage 2: post-animated-world single-bone transformed position
    # (bone_world * inv_bind * v_local). In bind pose
    # animated_world == bone_world.
    f1_post_anim = _apply_mat4(f1_per_bone, v_bind)
    g3_post_anim = _apply_mat4(g3_per_bone, v_bind)
    g5_post_anim = _apply_mat4(g5_per_bone, v_bind)

    return {
        "bone_dfs_index": bone_dfs_index,
        "qbone_at_slot_bytes": list(qbone_xyzw_at_slot),
        "tbone_at_slot_bytes": list(tbone_at_slot),
        "qbone_at_dfs_bytes": list(qbone_xyzw_at_dfs),
        "tbone_at_dfs_bytes": list(tbone_at_dfs),
        "GR_quaternion_xyzw_qx_qy_qz_qw_at_slot":
            [f1_qx, f1_qy, f1_qz, f1_qw],
        "REF_quaternion_xyzw_qx_qy_qz_qw_at_slot":
            [g3_qx, g3_qy, g3_qz, g3_qw],
        "REF_quaternion_xyzw_qx_qy_qz_qw_at_dfs":
            [g5_qx, g5_qy, g5_qz, g5_qw],
        "F1_TR_matrix_at_slot": f1_TR,
        "G3_TR_matrix_at_slot": g3_TR,
        "G5_TR_matrix_at_dfs":  g5_TR,
        "F1_inv_bind_matrix_after_inversion": f1_inv_bind,
        "G3_inv_bind_matrix_no_inversion_slot": g3_inv_bind,
        "G5_inv_bind_matrix_no_inversion_dfs":  g5_inv_bind,
        "bone_world_at_bind_pose": bone_world,
        "skin_world_at_bind_pose": skin_world,
        "F1_per_bone_matrix": f1_per_bone,
        "G3_per_bone_matrix": g3_per_bone,
        "G5_per_bone_matrix": g5_per_bone,
        "F1_per_bone_vs_skin_world_max_abs_delta":
            _max_abs_delta_4x4(f1_per_bone, skin_world),
        "G3_per_bone_vs_skin_world_max_abs_delta":
            _max_abs_delta_4x4(g3_per_bone, skin_world),
        "G5_per_bone_vs_skin_world_max_abs_delta":
            _max_abs_delta_4x4(g5_per_bone, skin_world),
        "F1_post_qbone_position": list(f1_post_qbone),
        "G3_post_qbone_position": list(g3_post_qbone),
        "G5_post_qbone_position": list(g5_post_qbone),
        "F1_post_animated_world_position": list(f1_post_anim),
        "G3_post_animated_world_position": list(g3_post_anim),
        "G5_post_animated_world_position": list(g5_post_anim),
    }


def _classify_first_divergence(
    g5_per_bone_skin_world_delta: float,
    g3_per_bone_skin_world_delta: float,
    f1_per_bone_skin_world_delta: float,
    f1_displacement: float,
    g3_displacement: float,
    g5_displacement: float,
) -> str:
    """First-divergence classification (newest decision):

        G5_collapses_F1_and_G3_diverge      - 3j-3 expected: third bug found
        G5_collapses_only_F1_diverges       - 3j-2 hypothesis (G3) survives
        all_three_collapse                  - GR was secretly correct already
        all_three_diverge                   - even G5 has another bug
        unclassified                        - mixed
    """
    g5_per_bone_ok = (g5_per_bone_skin_world_delta <= IDENTITY_TOLERANCE
                      and g5_displacement <= DISPLACEMENT_TOLERANCE)
    g3_per_bone_ok = (g3_per_bone_skin_world_delta <= IDENTITY_TOLERANCE
                      and g3_displacement <= DISPLACEMENT_TOLERANCE)
    f1_per_bone_ok = (f1_per_bone_skin_world_delta <= IDENTITY_TOLERANCE
                      and f1_displacement <= DISPLACEMENT_TOLERANCE)

    if g5_per_bone_ok and g3_per_bone_ok and f1_per_bone_ok:
        return "all_three_collapse"
    if g5_per_bone_ok and not g3_per_bone_ok and not f1_per_bone_ok:
        return "G5_collapses_F1_and_G3_diverge"
    if g5_per_bone_ok and g3_per_bone_ok and not f1_per_bone_ok:
        return "G5_and_G3_collapse_F1_diverges"
    if not g5_per_bone_ok and not g3_per_bone_ok and not f1_per_bone_ok:
        return "all_three_diverge"
    if g5_per_bone_ok:
        return "G5_collapses_mixed_others"
    return "unclassified"


def _replay_skin_node(
    *, model: Any, skin_node: Any, uploader: Any,
    name_to_dfs: Dict[str, int], resref: str, game: str,
) -> List[Dict[str, Any]]:
    bone_map = list(getattr(skin_node, "bone_map", []) or [])
    qbones = list(getattr(skin_node, "qbone_list", []) or [])
    tbones = list(getattr(skin_node, "tbone_list", []) or [])
    vertices = list(getattr(skin_node, "vertices", []) or [])
    skin_data = list(getattr(skin_node, "skin_data", []) or [])
    if not vertices or not skin_data or not bone_map:
        return []

    # Pre-compute bind-pose bone_world for every bone referenced by this
    # skin node, using GhostRigger's own _world_pose_matrix so the basis
    # for "bone_world" matches what production uses at render time.
    cache: Dict[str, List[List[float]]] = {}
    bone_world_by_slot: Dict[int, List[List[float]]] = {}
    bone_dfs_by_slot: Dict[int, int] = {}
    for slot, bname in enumerate(bone_map):
        bkey = str(bname or "").lower()
        if not bkey:
            bone_world_by_slot[slot] = _mat4_identity()
            bone_dfs_by_slot[slot] = -1
            continue
        bone_world_by_slot[slot] = uploader._world_pose_matrix(bkey, {}, cache)
        bone_dfs_by_slot[slot] = name_to_dfs.get(bkey, -1)

    skin_key = str(getattr(skin_node, "name", "") or "").lower()
    skin_world = (uploader._world_pose_matrix(skin_key, {}, cache)
                  if skin_key else _mat4_identity())

    records: List[Dict[str, Any]] = []
    for probe_idx in _probe_indices(min(len(vertices), len(skin_data))):
        v_bind_raw = vertices[probe_idx]
        v_bind: Tuple[float, float, float] = (
            float(v_bind_raw[0]), float(v_bind_raw[1]), float(v_bind_raw[2])
        )
        # Expected world position of the bind-pose vertex:
        # skin_world * v_local. This is what the LBS chain MUST collapse to
        # in bind pose under the correct convention.
        v_world_expected = _apply_mat4(skin_world, v_bind)

        sd = skin_data[probe_idx]
        influences = list(getattr(sd, "influences", []) or [])

        per_bone: List[Dict[str, Any]] = []
        f1_weighted: List[float] = [0.0, 0.0, 0.0]
        g3_weighted: List[float] = [0.0, 0.0, 0.0]
        g5_weighted: List[float] = [0.0, 0.0, 0.0]
        weight_sum = 0.0
        f1_per_bone_worst = 0.0
        g3_per_bone_worst = 0.0
        g5_per_bone_worst = 0.0

        for bw in influences:
            bone_local = int(getattr(bw, "bone_index", -1))
            weight = float(getattr(bw, "weight", 0.0))
            if weight <= 0.0:
                continue
            if bone_local < 0 or bone_local >= len(bone_map):
                continue
            if bone_local >= len(qbones) or bone_local >= len(tbones):
                continue

            # Slot-indexed arrays (what production currently reads).
            qb_slot = qbones[bone_local]
            tb_slot = tbones[bone_local]
            qb_slot_xyzw: Tuple[float, float, float, float] = (
                float(qb_slot[0]), float(qb_slot[1]),
                float(qb_slot[2]), float(qb_slot[3]),
            )
            tb_slot_t: Tuple[float, float, float] = (
                float(tb_slot[0]), float(tb_slot[1]), float(tb_slot[2])
            )

            # DFS-indexed arrays (what reference engines read).
            bone_dfs = bone_dfs_by_slot.get(bone_local, -1)
            if 0 <= bone_dfs < len(qbones) and bone_dfs < len(tbones):
                qb_dfs = qbones[bone_dfs]
                tb_dfs = tbones[bone_dfs]
                qb_dfs_xyzw: Tuple[float, float, float, float] = (
                    float(qb_dfs[0]), float(qb_dfs[1]),
                    float(qb_dfs[2]), float(qb_dfs[3]),
                )
                tb_dfs_t: Tuple[float, float, float] = (
                    float(tb_dfs[0]), float(tb_dfs[1]), float(tb_dfs[2])
                )
            else:
                qb_dfs_xyzw = (0.0, 0.0, 0.0, 1.0)
                tb_dfs_t = (0.0, 0.0, 0.0)

            bone_world = bone_world_by_slot.get(bone_local, _mat4_identity())
            replay = _build_per_bone_replay(
                qbone_xyzw_at_slot=qb_slot_xyzw,
                tbone_at_slot=tb_slot_t,
                qbone_xyzw_at_dfs=qb_dfs_xyzw,
                tbone_at_dfs=tb_dfs_t,
                bone_dfs_index=bone_dfs,
                bone_world=bone_world, skin_world=skin_world,
                v_bind=v_bind,
            )
            replay["bone_local_index"] = bone_local
            replay["bone_name"] = str(bone_map[bone_local] or "")
            replay["weight"] = weight
            per_bone.append(replay)

            f1_post = replay["F1_post_animated_world_position"]
            g3_post = replay["G3_post_animated_world_position"]
            g5_post = replay["G5_post_animated_world_position"]
            for i in range(3):
                f1_weighted[i] += weight * f1_post[i]
                g3_weighted[i] += weight * g3_post[i]
                g5_weighted[i] += weight * g5_post[i]
            weight_sum += weight

            f1_per_bone_worst = max(
                f1_per_bone_worst,
                replay["F1_per_bone_vs_skin_world_max_abs_delta"],
            )
            g3_per_bone_worst = max(
                g3_per_bone_worst,
                replay["G3_per_bone_vs_skin_world_max_abs_delta"],
            )
            g5_per_bone_worst = max(
                g5_per_bone_worst,
                replay["G5_per_bone_vs_skin_world_max_abs_delta"],
            )

        if weight_sum > 1e-6:
            f1_final: Tuple[float, float, float] = (
                f1_weighted[0] / weight_sum,
                f1_weighted[1] / weight_sum,
                f1_weighted[2] / weight_sum,
            )
            g3_final: Tuple[float, float, float] = (
                g3_weighted[0] / weight_sum,
                g3_weighted[1] / weight_sum,
                g3_weighted[2] / weight_sum,
            )
            g5_final: Tuple[float, float, float] = (
                g5_weighted[0] / weight_sum,
                g5_weighted[1] / weight_sum,
                g5_weighted[2] / weight_sum,
            )
        else:
            f1_final = v_world_expected
            g3_final = v_world_expected
            g5_final = v_world_expected

        f1_displacement = _vec3_norm(_vec3_sub(f1_final, v_world_expected))
        g3_displacement = _vec3_norm(_vec3_sub(g3_final, v_world_expected))
        g5_displacement = _vec3_norm(_vec3_sub(g5_final, v_world_expected))

        classification = _classify_first_divergence(
            g5_per_bone_skin_world_delta=g5_per_bone_worst,
            g3_per_bone_skin_world_delta=g3_per_bone_worst,
            f1_per_bone_skin_world_delta=f1_per_bone_worst,
            f1_displacement=f1_displacement,
            g3_displacement=g3_displacement,
            g5_displacement=g5_displacement,
        )

        records.append({
            "_kind": "single_vertex_replay",
            "resref": resref,
            "game": game,
            "skin_node_name": str(getattr(skin_node, "name", "") or ""),
            "probe_vertex_index": probe_idx,
            "v_bind_authored_position_node_local": list(v_bind),
            "v_world_expected_skin_world_times_v_bind": list(v_world_expected),
            "non_zero_influence_count": len(per_bone),
            "weight_sum": weight_sum,
            "F1_final_weighted_position": list(f1_final),
            "G3_final_weighted_position": list(g3_final),
            "G5_final_weighted_position": list(g5_final),
            "F1_bind_pose_displacement_from_expected": f1_displacement,
            "G3_bind_pose_displacement_from_expected": g3_displacement,
            "G5_bind_pose_displacement_from_expected": g5_displacement,
            "F1_per_bone_vs_skin_world_max_abs_delta_worst":
                f1_per_bone_worst,
            "G3_per_bone_vs_skin_world_max_abs_delta_worst":
                g3_per_bone_worst,
            "G5_per_bone_vs_skin_world_max_abs_delta_worst":
                g5_per_bone_worst,
            "first_divergence_classification": classification,
            "per_bone_influence_records": per_bone,
        })
    return records


def _summarize_creature(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(records)
    if n == 0:
        return {"probes_total": 0}

    def _median(xs: List[float]) -> float:
        if not xs:
            return 0.0
        m = len(xs) // 2
        if len(xs) % 2 == 1:
            return xs[m]
        return 0.5 * (xs[m - 1] + xs[m])

    def _stats(key: str) -> Dict[str, float]:
        vals = sorted(r[key] for r in records)
        return {"min": vals[0], "median": _median(vals), "max": vals[-1]}

    f1_d = _stats("F1_bind_pose_displacement_from_expected")
    g3_d = _stats("G3_bind_pose_displacement_from_expected")
    g5_d = _stats("G5_bind_pose_displacement_from_expected")
    f1_p = _stats("F1_per_bone_vs_skin_world_max_abs_delta_worst")
    g3_p = _stats("G3_per_bone_vs_skin_world_max_abs_delta_worst")
    g5_p = _stats("G5_per_bone_vs_skin_world_max_abs_delta_worst")

    g5_collapses = sum(
        1 for r in records
        if r["G5_per_bone_vs_skin_world_max_abs_delta_worst"]
        <= IDENTITY_TOLERANCE
    )
    g5_disp_ok = sum(
        1 for r in records
        if r["G5_bind_pose_displacement_from_expected"]
        <= DISPLACEMENT_TOLERANCE
    )
    g3_collapses = sum(
        1 for r in records
        if r["G3_per_bone_vs_skin_world_max_abs_delta_worst"]
        <= IDENTITY_TOLERANCE
    )
    f1_collapses = sum(
        1 for r in records
        if r["F1_per_bone_vs_skin_world_max_abs_delta_worst"]
        <= IDENTITY_TOLERANCE
    )

    classifications: Dict[str, int] = {}
    for r in records:
        c = r["first_divergence_classification"]
        classifications[c] = classifications.get(c, 0) + 1

    if g5_collapses == n and g5_disp_ok == n:
        outcome = "OUTCOME_1_G5_FULL_REF_COLLAPSES_BIND_POSE_SELF_TEST"
    elif g3_collapses == n:
        outcome = "OUTCOME_INTERMEDIATE_G3_REF_FULL_SUFFICES"
    else:
        outcome = "OUTCOME_2_NO_CANDIDATE_COLLAPSES_BIND_POSE"

    return {
        "probes_total": n,
        "F1_displacement_stats": f1_d,
        "G3_displacement_stats": g3_d,
        "G5_displacement_stats": g5_d,
        "F1_per_bone_skin_world_delta_stats": f1_p,
        "G3_per_bone_skin_world_delta_stats": g3_p,
        "G5_per_bone_skin_world_delta_stats": g5_p,
        "F1_per_bone_collapses_count": f1_collapses,
        "G3_per_bone_collapses_count": g3_collapses,
        "G5_per_bone_collapses_count": g5_collapses,
        "G5_displacement_within_tolerance_count": g5_disp_ok,
        "first_divergence_classifications": classifications,
        "outcome": outcome,
        "tolerance_identity_max_abs": IDENTITY_TOLERANCE,
        "tolerance_displacement": DISPLACEMENT_TOLERANCE,
    }


def _dump_one(rm: Any, resref: str, game: str, out_path: Path) -> int:
    from src.core.gpu_skinning import MatrixPaletteUploader

    model = rm.load_model(resref, game)
    if model is None:
        print(f"[3j-3] ERR: failed to load {resref} from {game}",
              file=sys.stderr)
        return 0

    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)

    # Build name -> global DFS node index lookup. qbones[]/tbones[] are
    # parallel to this index space (per reone mdlmdxreader.cpp:280-288 and
    # the empirical 3j-3 indexing audit, see 'diagnostics/skinning/2026_05/
    # _qbone_correct_index_search.txt').
    all_nodes = list(model.all_nodes())
    name_to_dfs: Dict[str, int] = {}
    for i, node in enumerate(all_nodes):
        nm = str(getattr(node, "name", "") or "")
        if nm:
            name_to_dfs[nm.lower()] = i

    skin_nodes = [n for n in all_nodes if getattr(n, "is_skin", False)]
    all_records: List[Dict[str, Any]] = []
    for node in skin_nodes:
        all_records.extend(_replay_skin_node(
            model=model, skin_node=node, uploader=uploader,
            name_to_dfs=name_to_dfs, resref=resref, game=game,
        ))

    summary = _summarize_creature(all_records)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_kind": "creature_summary",
            "_generated_by": "scripts/dump_qbone_single_vertex_replay.py",
            "_generated_at": time.time(),
            "resref": resref,
            "game": game,
            "skin_nodes_total": len(skin_nodes),
            "probes_total": len(all_records),
            "summary": summary,
        }, sort_keys=True))
        fh.write("\n")
        for rec in all_records:
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")

    print(f"[3j-3] {game}:{resref} -> {out_path.name}: "
          f"{len(all_records)} probes / {summary['outcome']}")
    return len(all_records)


def main() -> int:
    from src.core.resource_manager import ResourceManager

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[3j-3] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[3j-3] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        print("[3j-3] FATAL: no game install indexed", file=sys.stderr)
        return 2

    total = 0
    for resref, game, name in TARGETS:
        total += _dump_one(rm, resref, game, OUT_DIR / name)
    print(f"[3j-3] total probes written: {total}")
    return 0 if total else 3


if __name__ == "__main__":
    raise SystemExit(main())
