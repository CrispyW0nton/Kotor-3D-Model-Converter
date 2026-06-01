"""Deep diagnosis for PyKotor skin.bonemap -> GhostRigger bone_map conversion."""

from __future__ import annotations

import argparse
import inspect
import math
from collections import defaultdict
from typing import Any

from qa_common import configure_paths, load_ghostrigger_model


def _vec(value: Any, size: int) -> list[float]:
    out: list[float] = []
    for i in range(size):
        try:
            item = value[i]
        except Exception:
            item = getattr(value, ("x", "y", "z", "w")[i], 0.0)
        try:
            out.append(round(float(item), 6))
        except Exception:
            out.append(0.0)
    return out


def _raw_list(values: Any) -> list[Any]:
    try:
        return list(values or [])
    except Exception:
        return []


def _build_id_maps(pk_mdl: Any) -> tuple[dict[int, Any], dict[str, Any]]:
    id_to_node: dict[int, Any] = {}
    name_to_node: dict[str, Any] = {}
    for node in pk_mdl.all_nodes():
        try:
            id_to_node[int(node.node_id)] = node
        except Exception:
            pass
        name = str(getattr(node, "name", "") or "").lower()
        if name and name not in name_to_node:
            name_to_node[name] = node
    return id_to_node, name_to_node


def _ghost_nodes_by_name(model: Any) -> dict[str, list[Any]]:
    by_name: dict[str, list[Any]] = defaultdict(list)
    for node in model.all_nodes():
        by_name[str(getattr(node, "name", "") or "").lower()].append(node)
    return by_name


def _resolve_raw_bonemap(raw_bonemap: list[Any], id_to_node: dict[int, Any]) -> list[dict[str, Any]]:
    resolved = []
    for index, raw in enumerate(raw_bonemap):
        try:
            value = float(raw)
        except Exception:
            value = math.nan
        if not math.isfinite(value):
            node_id = None
            node_name = ""
            status = "NON_FINITE"
        else:
            node_id = int(round(value))
            if node_id < 0 or node_id == 0xFFFF:
                node_name = ""
                status = "PADDING"
            else:
                node = id_to_node.get(node_id)
                node_name = str(getattr(node, "name", "") or "") if node is not None else ""
                status = "OK" if node_name else "UNRESOLVED"
        resolved.append({
            "index": index,
            "raw": raw,
            "node_id": node_id,
            "node_name": node_name,
            "status": status,
        })
    return resolved


def _raw_references(skin: Any, resolved: list[dict[str, Any]]) -> tuple[dict[int, int], list[dict[str, Any]]]:
    refs: dict[int, int] = defaultdict(int)
    bad_refs: list[dict[str, Any]] = []
    for vi, vertex in enumerate(_raw_list(getattr(skin, "vertex_bones", None))):
        indices = _raw_list(getattr(vertex, "vertex_indices", ()))
        weights = _raw_list(getattr(vertex, "vertex_weights", ()))
        for slot in range(min(4, len(indices), len(weights))):
            try:
                weight = float(weights[slot])
                raw_index = float(indices[slot])
            except Exception:
                continue
            if weight <= 1e-6 or raw_index < 0 or not math.isfinite(raw_index):
                continue
            local_index = int(raw_index)
            refs[local_index] += 1
            status = resolved[local_index]["status"] if 0 <= local_index < len(resolved) else "OUT_OF_RANGE"
            if status != "OK":
                bad_refs.append({
                    "vertex": vi,
                    "slot": slot,
                    "local_index": local_index,
                    "weight": round(weight, 6),
                    "status": status,
                })
    return dict(sorted(refs.items())), bad_refs


def _ghost_references(node: Any) -> tuple[dict[int, int], list[dict[str, Any]]]:
    refs: dict[int, int] = defaultdict(int)
    bad_refs: list[dict[str, Any]] = []
    bone_map = _raw_list(getattr(node, "bone_map", None))
    for vi, vertex in enumerate(_raw_list(getattr(node, "skin_data", None))):
        for slot, influence in enumerate(_raw_list(getattr(vertex, "influences", None))):
            try:
                weight = float(getattr(influence, "weight", 0.0) or 0.0)
                bone_index = int(getattr(influence, "bone_index", -1))
            except Exception:
                continue
            if weight <= 1e-6:
                continue
            refs[bone_index] += 1
            name = bone_map[bone_index] if 0 <= bone_index < len(bone_map) else ""
            if not name:
                bad_refs.append({
                    "vertex": vi,
                    "slot": slot,
                    "bone_index": bone_index,
                    "weight": round(weight, 6),
                })
    return dict(sorted(refs.items())), bad_refs


def diagnose(game: str, resref: str, print_source: bool = False) -> int:
    configure_paths()
    from kotormcp.tools.ghostrigger_tools import _resource_pair
    from src.core.game import kotor_loader
    from src.core.mdl.mdl_reader_wrapper import read_mdl_safe

    _, mdl, mdx = _resource_pair(game, resref)
    pk_mdl = read_mdl_safe(mdl.data, source_ext=mdx.data if mdx is not None else b"")
    gr_model = load_ghostrigger_model(game, resref)
    id_to_node, _ = _build_id_maps(pk_mdl)
    gr_by_name = _ghost_nodes_by_name(gr_model)

    if print_source:
        print("===== _read_skin_weights SOURCE =====")
        print(inspect.getsource(kotor_loader._read_skin_weights))
        print("===== END SOURCE =====")

    print(f"Model {game}:{resref}")
    print(f"PyKotor nodes={len(pk_mdl.all_nodes())} GhostRigger nodes={len(gr_model.all_nodes())}")
    print(f"id_to_pknode keys={sorted(id_to_node.keys())[:20]} ... total={len(id_to_node)}")

    total_bad_raw = 0
    total_bad_ghost = 0
    for pk_node in pk_mdl.all_nodes():
        skin = getattr(pk_node, "skin", None)
        if skin is None:
            continue
        name = str(getattr(pk_node, "name", "") or "")
        raw_bonemap = _raw_list(getattr(skin, "bonemap", None))
        raw_bone_indices = _raw_list(getattr(skin, "bone_indices", None))
        qbone_len = len(_raw_list(getattr(skin, "qbones", None)))
        tbone_len = len(_raw_list(getattr(skin, "tbones", None)))
        resolved = _resolve_raw_bonemap(raw_bonemap, id_to_node)
        raw_refs, raw_bad_refs = _raw_references(skin, resolved)
        total_bad_raw += len(raw_bad_refs)

        ghost_candidates = gr_by_name.get(name.lower(), [])
        ghost_skin = next((node for node in ghost_candidates if getattr(node, "is_skin", False)), None)
        if ghost_skin is None:
            ghost_skin = ghost_candidates[0] if ghost_candidates else None
        ghost_bone_map = _raw_list(getattr(ghost_skin, "bone_map", None)) if ghost_skin is not None else []
        ghost_refs, ghost_bad_refs = _ghost_references(ghost_skin) if ghost_skin is not None else ({}, [])
        total_bad_ghost += len(ghost_bad_refs)

        print()
        print(f"SKIN NODE {name}")
        print(f"  PyKotor bone_indices[{len(raw_bone_indices)}] = {raw_bone_indices}")
        print(f"  PyKotor bonemap[{len(raw_bonemap)}] = {raw_bonemap}")
        print(f"  PyKotor qbone_len={qbone_len} tbone_len={tbone_len}")
        print("  bonemap resolution:")
        for item in resolved:
            print(
                "    [{index:02d}] raw={raw!r} node_id={node_id!r} "
                "status={status} name={node_name!r}".format(**item)
            )
        print(f"  raw referenced local indices = {raw_refs}")
        print(f"  raw unresolved referenced count = {len(raw_bad_refs)}")
        if raw_bad_refs:
            print(f"  raw unresolved referenced sample = {raw_bad_refs[:20]}")

        print(f"  GhostRigger bone_map[{len(ghost_bone_map)}] = {ghost_bone_map}")
        print(f"  GhostRigger qbone_len={len(_raw_list(getattr(ghost_skin, 'qbone_list', None))) if ghost_skin is not None else 0} "
              f"tbone_len={len(_raw_list(getattr(ghost_skin, 'tbone_list', None))) if ghost_skin is not None else 0}")
        print(f"  GhostRigger referenced bone indices = {ghost_refs}")
        print(f"  GhostRigger unresolved referenced count = {len(ghost_bad_refs)}")
        if ghost_bad_refs:
            print(f"  GhostRigger unresolved referenced sample = {ghost_bad_refs[:20]}")

    print()
    print(f"TOTAL raw unresolved referenced influences = {total_bad_raw}")
    print(f"TOTAL GhostRigger unresolved referenced influences = {total_bad_ghost}")
    return 0 if total_bad_raw == 0 and total_bad_ghost == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=["k1", "k2"], default="k2")
    parser.add_argument("--resref", default="c_bantha")
    parser.add_argument("--print-source", action="store_true")
    args = parser.parse_args()
    return diagnose(args.game, args.resref, print_source=args.print_source)


if __name__ == "__main__":
    raise SystemExit(main())

