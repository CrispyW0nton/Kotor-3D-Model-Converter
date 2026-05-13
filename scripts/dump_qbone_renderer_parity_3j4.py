"""3j Step 4 - In-renderer parity proof for the env-gated G5 path.

Goal 3 of the 3j-4 audit: prove that the corrected palette path
reproduces the same semantic win seen in the offline 3j-3 replay when
exercised inside the real renderer, not just in headless replay.

Procedure
---------

For each audit creature (c_drexlf, c_brith, c_bomabeast):

  1. Wipe any prior skin dump JSONL.
  2. Set ``GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF`` and
     ``GHOSTRIGGER_SKIN_DUMP=<dump path>``.
  3. Build a fresh ``GpuRenderer`` and render the model with a
     non-None but EMPTY anim_pose (``SimpleNamespace(nodes={})``).
     The renderer requires a non-None pose to activate GPU skinning
     (``gpu_renderer.py:5125``), but with an empty pose dict every
     bone falls back to its bind-time transform via
     ``MatrixPaletteUploader._world_pose_matrix``. The result is
     ``bone_world_anim == bone_world_bind`` for every bone --- so the
     bind-pose self-test from 3j-3 still applies AND the G5 code path
     is exercised end-to-end. The renderer's skin-dump path emits one
     record per skin draw whose ``live_slots[*].uploaded_u_bones_matrix``
     field contains the literal float32 matrix that was uploaded to
     the SSBO and consumed by the vertex shader.
  4. Build a fresh ``MatrixPaletteUploader`` under the same env and
     call ``compute_skin_node_palette`` offline for the same skin
     nodes. The resulting palette is the offline G5 ground truth.
  5. Reconcile per (skin_node, palette_slot):
       - max-abs delta between the in-renderer composed matrix and
         the offline G5 matrix (bit-exact expected: both derive from
         the same ``as_flat_bytes`` round-trip);
       - max-abs delta between the in-renderer composed matrix and
         ``skin_world`` (the bind-pose collapse target from 3j-3).

A passing run produces ``renderer_vs_offline_max_abs == 0`` and
``renderer_vs_skin_world_max_abs <= 1e-3`` for every slot of every
skin node on every creature. Anything else is a regression.

Outputs
-------

    diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_drexlf.jsonl
    diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_brith.jsonl
    diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_c_bomabeast.jsonl
    diagnostics/skinning/2026_05/qbone_renderer_parity_3j4_summary.json

Usage::

    python scripts/dump_qbone_renderer_parity_3j4.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K1_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
K2_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

OUT_DIR = ROOT / "diagnostics" / "skinning" / "2026_05"
SUMMARY_PATH = OUT_DIR / "qbone_renderer_parity_3j4_summary.json"

WIDTH = 256
HEIGHT = 256

TARGETS: Tuple[Tuple[str, str, str, str], ...] = (
    ("c_drexlf",    "K2",
     "qbone_renderer_parity_3j4_c_drexlf.jsonl",
     "skin_dump_g5_c_drexlf.jsonl"),
    ("c_brith",     "K2",
     "qbone_renderer_parity_3j4_c_brith.jsonl",
     "skin_dump_g5_c_brith.jsonl"),
    ("c_bomabeast", "K1",
     "qbone_renderer_parity_3j4_c_bomabeast.jsonl",
     "skin_dump_g5_c_bomabeast.jsonl"),
)

# Tolerance budget: the in-renderer composed matrix is the SSBO bytes
# round-tripped through float32, and the offline replay is the same
# matrix taken from ``as_flat_bytes()`` directly. Bit-exact equality
# (delta == 0.0) is the expected outcome --- we use a small float32
# epsilon as a safety margin in case any intermediate stage forces a
# minor truncation, but a non-zero delta should still be flagged as a
# regression for investigation.
RENDERER_VS_OFFLINE_TOLERANCE = 1e-6
RENDERER_VS_SKIN_WORLD_TOLERANCE = 1e-3


def _max_abs_delta_4x4(a, b) -> float:
    worst = 0.0
    for r in range(4):
        for c in range(4):
            worst = max(worst, abs(float(a[r][c]) - float(b[r][c])))
    return worst


def _setup_resource_manager():
    from src.core.animation_engine import SuperModelResolver
    from src.core.resource_manager import ResourceManager

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[3j-4-rp] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[3j-4-rp] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        raise SystemExit("[3j-4-rp] FATAL: no game install indexed")
    SuperModelResolver._resource_manager = rm
    return rm


def _render_under_g5(*, rm, resref: str, game: str,
                     dump_path: Path) -> Optional[str]:
    """Render the model in bind pose with G5 + skin dump enabled.

    Returns the renderer backend name (``"gpu"`` on success) or None
    if the render failed. The dump JSONL is written by the renderer
    as a side effect.
    """
    from src.core.resource_manager import resolve_model_textures
    from src.gui.gpu_renderer import GpuRenderer
    from src.gui.viewport import ArcBallCamera

    prior_formula = os.environ.get("GHOSTRIGGER_SKIN_FORMULA")
    prior_dump = os.environ.get("GHOSTRIGGER_SKIN_DUMP")
    os.environ["GHOSTRIGGER_SKIN_FORMULA"] = "G5_FULL_REF"
    os.environ["GHOSTRIGGER_SKIN_DUMP"] = str(dump_path)
    if dump_path.exists():
        try:
            dump_path.unlink()
        except OSError:
            pass

    renderer: Optional[GpuRenderer] = None
    backend = None
    try:
        model = rm.load_model(resref, game)
        if model is None:
            print(f"[3j-4-rp] ERR: failed to load {resref} from {game}",
                  file=sys.stderr)
            return None

        textures: Dict[str, Any] = {}
        try:
            textures = resolve_model_textures(model, rm, game=game)
        except Exception as exc:
            print(f"[3j-4-rp] WARN: texture load failed for {resref}: "
                  f"{exc!r}", file=sys.stderr)

        camera = ArcBallCamera()
        try:
            bb_min, bb_max = model.bounding_box()
        except Exception:
            bb_min = getattr(model, "bb_min", None)
            bb_max = getattr(model, "bb_max", None)
        if bb_min is not None and bb_max is not None:
            camera.frame_bounds(bb_min, bb_max)

        renderer = GpuRenderer()
        # Empty-but-non-None anim_pose: triggers the GPU skinning
        # branch in GpuRenderer (which requires anim_pose is not None,
        # see gpu_renderer.py:5125) while every bone falls back to its
        # bind transform via MatrixPaletteUploader._world_pose_matrix
        # (see gpu_skinning.py:538-550). This keeps the bind-pose
        # self-test target ``skin_world * v_local`` valid while the G5
        # code path actually executes inside the renderer.
        bind_anim_pose = SimpleNamespace(nodes={})
        img = renderer.render(
            model, camera, WIDTH, HEIGHT,
            textures=textures,
            anim_pose=bind_anim_pose,
            anim_time=0.0,
            anim_base_pose=bind_anim_pose,
        )
        if img is None:
            print(f"[3j-4-rp] ERR: renderer returned None for {resref}",
                  file=sys.stderr)
            return None
        backend = renderer.perf.get("backend", "unknown")
    finally:
        if renderer is not None:
            try:
                renderer.release()
            except Exception:
                pass
        if prior_formula is None:
            os.environ.pop("GHOSTRIGGER_SKIN_FORMULA", None)
        else:
            os.environ["GHOSTRIGGER_SKIN_FORMULA"] = prior_formula
        if prior_dump is None:
            os.environ.pop("GHOSTRIGGER_SKIN_DUMP", None)
        else:
            os.environ["GHOSTRIGGER_SKIN_DUMP"] = prior_dump

    return backend


def _read_dump_records(dump_path: Path) -> List[Dict[str, Any]]:
    """Read the skin dump JSONL and return only top-level records (the
    renderer wraps each emit in a dict with a single ``payload`` key
    holding the actual ``_build_skin_dump_record`` output)."""
    if not dump_path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with dump_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def _extract_skin_node_payload(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort extraction: the renderer dumps the
    ``_build_skin_dump_record`` output either inline or under a
    ``payload``/``record`` field depending on ``_append_jsonl_record``.
    """
    for key in ("payload", "record", "skin_dump"):
        if isinstance(rec.get(key), dict):
            return rec[key]
    return rec


def _build_offline_g5_palette(model, skin_node) -> Tuple[
    List[List[List[float]]], List[List[float]],
]:
    """Compute the offline G5 palette and skin_world for a skin node.

    Returns ``(palette_row_major, skin_world_row_major)`` where the
    palette is row-major float matrices indexed by ``palette_slot``
    and ``skin_world`` is the bind-pose skin node world matrix.
    """
    from src.core.gpu_skinning import (
        MatrixPaletteUploader,
        _SKIN_FORMULA_ENV,
        _SKIN_FORMULA_G5,
    )

    prior = os.environ.get(_SKIN_FORMULA_ENV)
    os.environ[_SKIN_FORMULA_ENV] = _SKIN_FORMULA_G5
    try:
        uploader = MatrixPaletteUploader()
        uploader.build_inverse_bind_pose(model)
        uploader.compute_skin_node_palette(skin_node, anim_pose=None)
        palette: List[List[List[float]]] = []
        for bm in uploader.palette:
            col = bm.flat_col
            m: List[List[float]] = [[0.0] * 4 for _ in range(4)]
            for r in range(4):
                for c in range(4):
                    m[r][c] = float(col[c * 4 + r])
            palette.append(m)
        skin_world = uploader._skin_bind_matrix or [
            [1.0 if r == c else 0.0 for c in range(4)] for r in range(4)
        ]
        return palette, skin_world
    finally:
        if prior is None:
            os.environ.pop(_SKIN_FORMULA_ENV, None)
        else:
            os.environ[_SKIN_FORMULA_ENV] = prior


def _reconcile_creature(*, rm, resref: str, game: str,
                        out_path: Path,
                        dump_path: Path) -> Dict[str, Any]:
    backend = _render_under_g5(rm=rm, resref=resref, game=game,
                               dump_path=dump_path)
    if backend != "gpu":
        return {
            "resref": resref,
            "game": game,
            "verdict": "RENDER_FAILED_OR_CPU_BACKEND",
            "backend": backend,
        }

    raw_records = _read_dump_records(dump_path)
    if not raw_records:
        return {
            "resref": resref,
            "game": game,
            "verdict": "NO_SKIN_DUMP_RECORDS_PRODUCED",
            "backend": backend,
            "dump_path": str(dump_path),
        }

    model = rm.load_model(resref, game)
    if model is None:
        return {
            "resref": resref,
            "game": game,
            "verdict": "MODEL_RELOAD_FAILED",
            "backend": backend,
        }

    nodes_by_name: Dict[str, Any] = {}
    for node in model.all_nodes():
        nm = str(getattr(node, "name", "") or "").lower()
        if nm:
            nodes_by_name[nm] = node

    per_node_records: List[Dict[str, Any]] = []
    worst_renderer_vs_offline = 0.0
    worst_renderer_vs_skin_world = 0.0
    slots_total = 0
    slots_offline_match = 0
    slots_skin_world_match = 0

    for rec in raw_records:
        payload = _extract_skin_node_payload(rec)
        # The renderer's _build_skin_dump_record stores the skin-node
        # name in the ``node`` field (see gpu_renderer.py:1655 area).
        # Fall back to other plausible names so a refactor of the dump
        # builder doesn't silently break this script.
        skin_node_name = ""
        for k in ("node", "skin_node_name", "node_name", "name",
                  "model_node_name", "skin_node"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                skin_node_name = v
                break
        if not skin_node_name:
            continue
        skin_node = nodes_by_name.get(skin_node_name.lower())
        if skin_node is None:
            per_node_records.append({
                "skin_node_name": skin_node_name,
                "skipped_reason": "skin_node_not_found_in_reloaded_model",
            })
            continue

        offline_palette, skin_world = _build_offline_g5_palette(
            model, skin_node,
        )

        # The renderer dumps every bone slot the skin node actually
        # uses under ``live_slots`` (12-17 entries per node on the
        # audit creatures), and only the probe vertex's influences
        # under ``referenced_bones`` (typically 1-4). Crucially, in
        # the live-slots view the actual uploaded matrix lives in
        # ``uploaded_u_bones_matrix`` --- the ``composed_skinning_matrix``
        # field there is None by design. The referenced-bones view
        # populates both fields with the same value. We accept either
        # source per slot so the comparison covers the full bone_map.
        referenced = payload.get("referenced_bones") or payload.get(
            "bone_influences") or []
        if not isinstance(referenced, list):
            referenced = []
        live_slots = payload.get("live_slots") or []
        if not isinstance(live_slots, list):
            live_slots = []

        uploaded_by_slot: Dict[int, List[List[float]]] = {}
        for entry in list(live_slots) + list(referenced):
            if not isinstance(entry, dict):
                continue
            pidx_raw = entry.get("palette_index")
            if pidx_raw is None:
                pidx_raw = entry.get("local_bone_index")
            try:
                pidx = int(pidx_raw)
            except (TypeError, ValueError):
                continue
            mat = entry.get("uploaded_u_bones_matrix")
            if not (isinstance(mat, list) and len(mat) == 4):
                mat = entry.get("composed_skinning_matrix")
            if not (isinstance(mat, list) and len(mat) == 4):
                continue
            uploaded_by_slot[pidx] = mat

        node_record: Dict[str, Any] = {
            "skin_node_name": skin_node_name,
            "palette_slots_compared": 0,
            "renderer_vs_offline_max_abs_per_slot": [],
            "renderer_vs_skin_world_max_abs_per_slot": [],
            "worst_renderer_vs_offline": 0.0,
            "worst_renderer_vs_skin_world": 0.0,
        }

        for pidx, uploaded_m in sorted(uploaded_by_slot.items()):
            if pidx < 0 or pidx >= len(offline_palette):
                continue
            offline_m = offline_palette[pidx]
            d_off = _max_abs_delta_4x4(uploaded_m, offline_m)
            d_sw = _max_abs_delta_4x4(uploaded_m, skin_world)
            node_record["palette_slots_compared"] += 1
            node_record["renderer_vs_offline_max_abs_per_slot"].append({
                "palette_slot": pidx,
                "max_abs_delta": d_off,
            })
            node_record["renderer_vs_skin_world_max_abs_per_slot"].append({
                "palette_slot": pidx,
                "max_abs_delta": d_sw,
            })
            node_record["worst_renderer_vs_offline"] = max(
                node_record["worst_renderer_vs_offline"], d_off,
            )
            node_record["worst_renderer_vs_skin_world"] = max(
                node_record["worst_renderer_vs_skin_world"], d_sw,
            )
            slots_total += 1
            if d_off <= RENDERER_VS_OFFLINE_TOLERANCE:
                slots_offline_match += 1
            if d_sw <= RENDERER_VS_SKIN_WORLD_TOLERANCE:
                slots_skin_world_match += 1
            worst_renderer_vs_offline = max(
                worst_renderer_vs_offline, d_off)
            worst_renderer_vs_skin_world = max(
                worst_renderer_vs_skin_world, d_sw)

        per_node_records.append(node_record)

    if slots_total == 0:
        verdict = "NO_PALETTE_SLOTS_RECONCILABLE"
    elif (slots_offline_match == slots_total
          and slots_skin_world_match == slots_total):
        verdict = ("G5_RENDERER_BIT_EXACT_TO_OFFLINE_AND_BIND_POSE"
                   "_SELF_TEST_COLLAPSES")
    elif slots_offline_match == slots_total:
        verdict = ("G5_RENDERER_BIT_EXACT_TO_OFFLINE_BUT_BIND_POSE"
                   "_SELF_TEST_FAILS")
    elif slots_skin_world_match == slots_total:
        verdict = ("G5_BIND_POSE_OK_BUT_RENDERER_DIVERGES_FROM_OFFLINE"
                   "_PALETTE")
    else:
        verdict = "G5_RENDERER_FAILS_BOTH_PARITY_CHECKS"

    summary = {
        "_kind": "creature_summary",
        "_generated_by": "scripts/dump_qbone_renderer_parity_3j4.py",
        "_generated_at": time.time(),
        "resref": resref,
        "game": game,
        "backend": backend,
        "skin_dump_path": str(dump_path),
        "skin_nodes_in_dump": len(per_node_records),
        "palette_slots_compared_total": slots_total,
        "palette_slots_renderer_vs_offline_within_tol":
            slots_offline_match,
        "palette_slots_renderer_vs_skin_world_within_tol":
            slots_skin_world_match,
        "worst_renderer_vs_offline_max_abs":
            worst_renderer_vs_offline,
        "worst_renderer_vs_skin_world_max_abs":
            worst_renderer_vs_skin_world,
        "tolerance_renderer_vs_offline":
            RENDERER_VS_OFFLINE_TOLERANCE,
        "tolerance_renderer_vs_skin_world":
            RENDERER_VS_SKIN_WORLD_TOLERANCE,
        "verdict": verdict,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, sort_keys=True))
        fh.write("\n")
        for rec in per_node_records:
            fh.write(json.dumps({"_kind": "skin_node", **rec},
                                sort_keys=True))
            fh.write("\n")

    print(f"[3j-4-rp] {game}:{resref} -> {out_path.name}: "
          f"{slots_offline_match}/{slots_total} slots offline-bit-exact, "
          f"{slots_skin_world_match}/{slots_total} skin-world-collapse | "
          f"worst d_off={worst_renderer_vs_offline:.3e} "
          f"d_sw={worst_renderer_vs_skin_world:.3e} | "
          f"verdict {verdict}")
    return summary


def main() -> int:
    rm = _setup_resource_manager()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    overall: List[Dict[str, Any]] = []
    for resref, game, out_name, dump_name in TARGETS:
        out_path = OUT_DIR / out_name
        dump_path = OUT_DIR / dump_name
        overall.append(_reconcile_creature(
            rm=rm, resref=resref, game=game,
            out_path=out_path, dump_path=dump_path,
        ))

    SUMMARY_PATH.write_text(json.dumps({
        "_generated_by": "scripts/dump_qbone_renderer_parity_3j4.py",
        "_generated_at": time.time(),
        "tolerance_renderer_vs_offline":
            RENDERER_VS_OFFLINE_TOLERANCE,
        "tolerance_renderer_vs_skin_world":
            RENDERER_VS_SKIN_WORLD_TOLERANCE,
        "creatures": overall,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[3j-4-rp] summary -> {SUMMARY_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
