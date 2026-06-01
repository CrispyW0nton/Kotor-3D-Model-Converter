"""Diagnose K2 skin/render transform issues against MCP inspection data.

This script is intentionally read-only: it loads game MDL/MDX resources, records
skin-node transforms and bone-map health, and writes a JSON report for debugging
visual geometry issues that data-parity scans do not catch.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KOTORMCP_SRC = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\KotorMCP\src")
PYKOTOR_SRC = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor\Libraries\PyKotor\src")
PYKOTOR_GL_SRC = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor\Libraries\PyKotorGL\src")
UTILITY_SRC = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor\Libraries\Utility\src")

for path in (ROOT, KOTORMCP_SRC, PYKOTOR_SRC, PYKOTOR_GL_SRC, UTILITY_SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


DEFAULT_K2_MODELS = [
    "c_bantha",
    "c_cannok",
    "c_zakkeg",
    "n_darthsion",
    "n_darthtraya",
    "p_hk47",
    *[f"PFHB{i:02d}" for i in range(1, 6)],
    *[f"PMHB{i:02d}" for i in range(1, 6)],
    *[f"PFHC{i:02d}" for i in range(1, 11)],
    *[f"PMHC{i:02d}" for i in range(1, 11)],
]


def _vec(value: Any, size: int) -> list[float]:
    if value is None:
        return [0.0] * size
    out: list[float] = []
    names = ("x", "y", "z", "w")
    for i in range(size):
        try:
            item = getattr(value, names[i])
        except Exception:
            try:
                item = value[i]
            except Exception:
                item = 0.0
        try:
            out.append(float(item))
        except Exception:
            out.append(0.0)
    return out


def _vec3(value: Any) -> list[float]:
    return _vec(value, 3)


def _quat(value: Any) -> list[float]:
    out = _vec(value, 4)
    if out == [0.0, 0.0, 0.0, 0.0]:
        out[3] = 1.0
    return out


def _round_float(value: float, places: int = 6) -> float:
    if not math.isfinite(value):
        return value
    return round(float(value), places)


def _round_vec(values: Any, places: int = 6) -> list[float]:
    return [_round_float(float(v), places) for v in values]


def _bbox(points: list[Any]) -> dict[str, list[float]]:
    if not points:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
    rows = [[float(p[0]), float(p[1]), float(p[2])] for p in points]
    return {
        "min": [_round_float(min(row[i] for row in rows)) for i in range(3)],
        "max": [_round_float(max(row[i] for row in rows)) for i in range(3)],
    }


def _quat_is_identity(q: Any, tol: float = 1e-4) -> bool:
    qv = _round_vec(q, 8)
    direct = abs(qv[0]) <= tol and abs(qv[1]) <= tol and abs(qv[2]) <= tol and abs(qv[3] - 1.0) <= tol
    negated = abs(qv[0]) <= tol and abs(qv[1]) <= tol and abs(qv[2]) <= tol and abs(qv[3] + 1.0) <= tol
    return direct or negated


def _node_chain(node: Any) -> list[Any]:
    chain = []
    seen: set[int] = set()
    cur = node
    while cur is not None and id(cur) not in seen and len(chain) < 512:
        seen.add(id(cur))
        chain.append(cur)
        cur = getattr(cur, "parent", None)
    chain.reverse()
    return chain


def _parent_chain_orientation(node: Any) -> list[float]:
    from src.core.geometry.model_data import _quat_mul, _quat_normalize_bind

    aq: list[float] = [0.0, 0.0, 0.0, 1.0]
    for item in _node_chain(node)[:-1]:
        aq = _quat_mul(aq, _quat_normalize_bind(_quat(getattr(item, "rotation", None))))
    return _round_vec(aq)


def _apply_transform(vertex: Any, position: Any, orientation: Any) -> list[float]:
    from src.core.geometry.model_data import _quat_rotate

    v = (float(vertex[0]), float(vertex[1]), float(vertex[2]))
    p = _vec3(position)
    q = _quat(orientation)
    rotated = _quat_rotate(q, v)
    return _round_vec((rotated[0] + p[0], rotated[1] + p[1], rotated[2] + p[2]))


def _translate_only(vertex: Any, position: Any) -> list[float]:
    p = _vec3(position)
    return _round_vec((float(vertex[0]) + p[0], float(vertex[1]) + p[1], float(vertex[2]) + p[2]))


def _skin_weight_stats(node: Any) -> dict[str, Any]:
    skin_data = list(getattr(node, "skin_data", None) or [])
    bone_map = list(getattr(node, "bone_map", None) or [])
    out_of_range = 0
    zero_weight = 0
    max_influences = 0
    weight_sums: list[float] = []
    used_indices: set[int] = set()

    for vertex in skin_data:
        influences = list(getattr(vertex, "influences", None) or [])
        active = [inf for inf in influences if float(getattr(inf, "weight", 0.0) or 0.0) > 1e-6]
        max_influences = max(max_influences, len(active))
        total = sum(float(getattr(inf, "weight", 0.0) or 0.0) for inf in influences)
        weight_sums.append(total)
        if total <= 1e-6:
            zero_weight += 1
        for inf in active:
            idx = int(getattr(inf, "bone_index", -1))
            used_indices.add(idx)
            if idx < 0 or idx >= len(bone_map):
                out_of_range += 1

    return {
        "vertex_skin_count": len(skin_data),
        "bone_map_count": len(bone_map),
        "bone_map": bone_map,
        "empty_bone_map_slots": [i for i, name in enumerate(bone_map) if not name],
        "used_bone_indices": sorted(used_indices),
        "max_used_bone_index": max(used_indices) if used_indices else None,
        "out_of_range_influences": out_of_range,
        "vertices_with_zero_weight": zero_weight,
        "max_influences_per_vertex": max_influences,
        "weight_sum_range": [
            _round_float(min(weight_sums)) if weight_sums else 0.0,
            _round_float(max(weight_sums)) if weight_sums else 0.0,
        ],
    }


def _summarize_skin_node(node: Any, raw_node: dict[str, Any] | None, skinning_node: dict[str, Any] | None) -> dict[str, Any]:
    world_position, world_orientation = node.world_transform()
    parent_orientation = _parent_chain_orientation(node)
    vertices = list(getattr(node, "vertices", None) or [])
    first_vertices = vertices[:5]

    chain = []
    for item in _node_chain(node):
        try:
            wp, wo = item.world_transform()
        except Exception:
            wp, wo = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
        chain.append(
            {
                "name": str(getattr(item, "name", "")),
                "type": item.type_name() if hasattr(item, "type_name") else "",
                "position": _round_vec(_vec3(getattr(item, "position", None))),
                "orientation": _round_vec(_quat(getattr(item, "rotation", None))),
                "world_position": _round_vec(wp),
                "world_orientation": _round_vec(wo),
            }
        )

    return {
        "name": str(getattr(node, "name", "")),
        "parent": str(getattr(getattr(node, "parent", None), "name", "") or ""),
        "vertex_space": int(getattr(node, "vertex_space", 0) or 0),
        "local_position": _round_vec(_vec3(getattr(node, "position", None))),
        "local_orientation": _round_vec(_quat(getattr(node, "rotation", None))),
        "world_position": _round_vec(world_position),
        "world_orientation": _round_vec(world_orientation),
        "parent_chain_orientation": parent_orientation,
        "parent_chain_identity_rotation": _quat_is_identity(parent_orientation),
        "parent_chain": chain,
        "raw_mcp_summary": raw_node or {},
        "skinning_mcp_summary": skinning_node or {},
        "bone_health": _skin_weight_stats(node),
        "raw_vertex_bbox": _bbox(vertices),
        "world_transform_vertex_bbox": _bbox([_apply_transform(v, world_position, world_orientation) for v in vertices]),
        "translate_only_vertex_bbox": _bbox([_translate_only(v, world_position) for v in vertices]),
        "raw_vertices_first5": [_round_vec(v) for v in first_vertices],
        "world_transform_vertices_first5": [_apply_transform(v, world_position, world_orientation) for v in first_vertices],
        "translate_only_vertices_first5": [_translate_only(v, world_position) for v in first_vertices],
    }


def _load_ghostrigger_model(game: str, resref: str) -> Any:
    from kotormcp.tools.ghostrigger_tools import _resource_pair
    from src.core.game.kotor_loader import load_model_from_bytes

    _, mdl, mdx = _resource_pair(game, resref)
    model = load_model_from_bytes(mdl.data, mdx.data if mdx is not None else b"")
    if model is None:
        raise RuntimeError(f"GhostRigger failed to load {game}:{resref}")
    return model


def diagnose_model(game: str, resref: str, include_k1_equivalent: bool = True) -> dict[str, Any]:
    from kotormcp.tools.ghostrigger_tools import inspect_mdl, inspect_mdl_ghostrigger, inspect_skinning

    raw_summary = inspect_mdl(game, resref)
    ghost_summary = inspect_mdl_ghostrigger(game, resref)
    skinning = inspect_skinning(game, resref)
    model = _load_ghostrigger_model(game, resref)

    raw_nodes = {node["name"]: node for node in raw_summary.get("nodes", [])}
    skin_nodes_by_name = {node["name"]: node for node in skinning.get("skin_nodes", [])}
    skin_nodes = [node for node in model.all_nodes() if bool(getattr(node, "is_skin", False))]

    result: dict[str, Any] = {
        "game": game.lower(),
        "resref": resref,
        "status": "OK",
        "mcp": {
            "raw": {
                "node_count": raw_summary.get("node_count"),
                "skin_nodes": raw_summary.get("skin_nodes", []),
                "classification": raw_summary.get("classification"),
                "supermodel": raw_summary.get("supermodel"),
            },
            "ghostrigger": {
                "node_count": ghost_summary.get("node_count"),
                "skin_nodes": ghost_summary.get("skin_nodes", []),
                "classification": ghost_summary.get("classification"),
                "supermodel": ghost_summary.get("supermodel"),
            },
        },
        "skin_nodes": [
            _summarize_skin_node(
                node,
                raw_nodes.get(str(getattr(node, "name", ""))),
                skin_nodes_by_name.get(str(getattr(node, "name", ""))),
            )
            for node in skin_nodes
        ],
    }

    result["diagnostic_flags"] = _diagnostic_flags(result)
    category, basis = _diagnostic_category(result)
    result["diagnostic_category"] = category
    result["diagnostic_category_basis"] = basis

    if include_k1_equivalent and game.lower() == "k2":
        try:
            k1 = diagnose_model("k1", resref, include_k1_equivalent=False)
            result["k1_equivalent"] = {
                "status": k1["status"],
                "skin_node_count": len(k1.get("skin_nodes", [])),
                "skin_nodes": [
                    {
                        "name": n["name"],
                        "parent_chain_identity_rotation": n["parent_chain_identity_rotation"],
                        "parent_chain_orientation": n["parent_chain_orientation"],
                        "world_position": n["world_position"],
                        "world_orientation": n["world_orientation"],
                        "bone_health": n["bone_health"],
                    }
                    for n in k1.get("skin_nodes", [])
                ],
                "diagnostic_flags": k1.get("diagnostic_flags", []),
            }
        except Exception as exc:
            result["k1_equivalent"] = {"status": "ERROR", "error": str(exc)}

    return result


def _diagnostic_flags(result: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for skin in result.get("skin_nodes", []):
        name = skin.get("name", "")
        if not skin.get("parent_chain_identity_rotation", True):
            flags.append(f"{name}: non-identity parent-chain rotation")
        bone_health = skin.get("bone_health", {})
        if bone_health.get("out_of_range_influences", 0):
            flags.append(f"{name}: out-of-range bone influences")
        if bone_health.get("vertices_with_zero_weight", 0):
            flags.append(f"{name}: zero-weight vertices")
        low, high = bone_health.get("weight_sum_range", [1.0, 1.0])
        if low < 0.99 or high > 1.01:
            flags.append(f"{name}: weight sums outside tolerance")
        if skin.get("vertex_space") != 0:
            flags.append(f"{name}: unexpected vertex_space={skin.get('vertex_space')}")
    return flags


def _diagnostic_category(result: dict[str, Any]) -> tuple[str, str]:
    """Map diagnostic evidence to the requested visual-failure buckets."""
    flags = result.get("diagnostic_flags", [])
    text = " ".join(flags).lower()
    if "out-of-range bone" in text:
        return "SPIKES", "out-of-range bone indices usually produce vertex spikes"
    if "non-identity parent-chain rotation" in text:
        return "OFFSET", "skin node parent chain is non-identity; double-transform risk"
    if "zero-weight" in text or "weight sums outside" in text:
        return "STRETCHED", "weight normalization/coverage issue"
    return "OK", "no diagnostic transform, bonemap, or weight-health flags"


def _error_category(error: str) -> tuple[str, str]:
    lowered = error.lower()
    if "not found" in lowered:
        return "MISSING", "resource was not present in the target game installation"
    return "MISSING", "model could not be loaded for diagnosis"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="*", default=DEFAULT_K2_MODELS, help="K2 model resrefs to diagnose")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of K2 models")
    parser.add_argument("--output", default=str(ROOT / "exports" / "k2_geometry_diagnosis.json"))
    args = parser.parse_args()

    models = args.models[: args.limit] if args.limit else args.models
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "K2 visual geometry diagnosis: skin parent transforms, bonemaps, and vertex transform samples",
        "models_requested": models,
        "models": [],
    }

    for index, resref in enumerate(models, 1):
        print(f"[{index}/{len(models)}] k2:{resref}", flush=True)
        try:
            item = diagnose_model("k2", resref)
        except Exception as exc:
            category, basis = _error_category(str(exc))
            item = {
                "game": "k2",
                "resref": resref,
                "status": "ERROR",
                "error": str(exc),
                "diagnostic_category": category,
                "diagnostic_category_basis": basis,
            }
        report["models"].append(item)
        status = item.get("status", "ERROR")
        flags = item.get("diagnostic_flags", [])
        print(
            f"  {status}/{item.get('diagnostic_category', 'UNKNOWN')}: "
            f"{len(item.get('skin_nodes', []))} skin node(s), {len(flags)} diagnostic flag(s)",
            flush=True,
        )
        for flag in flags[:5]:
            print(f"    - {flag}", flush=True)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
