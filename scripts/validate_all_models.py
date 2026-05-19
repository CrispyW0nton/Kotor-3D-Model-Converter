"""Run structural validation across all K1/K2 MDL resources."""

from __future__ import annotations

import argparse
import math
import time
from collections import Counter
from typing import Any

from qa_common import EXPORTS, add_common_args, finite_vec, iter_models, load_ghostrigger_model, write_json


VERTEX_LIMIT = 10000.0


def _node_name(node: Any) -> str:
    return str(getattr(node, "name", "") or "<unnamed>")


def _iter_mesh_nodes(model: Any):
    for node in model.all_nodes():
        if bool(getattr(node, "is_mesh", False)):
            yield node


def _validate_model(game: str, resref: str) -> dict[str, Any]:
    started = time.perf_counter()
    failures: list[str] = []
    model = None

    try:
        model = load_ghostrigger_model(game, resref)
    except Exception as exc:
        return {
            "game": game,
            "resref": resref,
            "passed": False,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "failures": [f"LOAD SUCCESS: {type(exc).__name__}: {exc}"],
        }

    try:
        from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

        renderer = FrameRenderer(ArcBallCamera())
        renderer.set_model(model)
    except Exception as exc:
        renderer = None
        failures.append(f"TRANSFORM CHAIN: renderer setup failed: {type(exc).__name__}: {exc}")

    for node in _iter_mesh_nodes(model):
        name = _node_name(node)
        vertices = list(getattr(node, "vertices", None) or [])
        faces = list(getattr(node, "faces", None) or [])
        uvs = list(getattr(node, "uvs", None) or [])

        if not vertices or not faces:
            failures.append(f"NODE INTEGRITY: {name} has {len(vertices)} vertices and {len(faces)} faces")

        if bool(getattr(node, "is_skin", False)):
            bone_map = list(getattr(node, "bone_map", None) or [])
            skin_data = list(getattr(node, "skin_data", None) or [])
            if not bone_map:
                failures.append(f"SKIN SANITY: {name} has empty bone_map")
            for vi, skin_vertex in enumerate(skin_data):
                for influence in list(getattr(skin_vertex, "influences", None) or []):
                    weight = float(getattr(influence, "weight", 0.0) or 0.0)
                    if weight <= 1e-6:
                        continue
                    bone_index = int(getattr(influence, "bone_index", -1))
                    if bone_index < 0 or bone_index >= len(bone_map):
                        failures.append(
                            f"SKIN SANITY: {name} vertex {vi} bone index {bone_index} out of range {len(bone_map)}"
                        )
                        break

        for ui, uv in enumerate(uvs):
            if not finite_vec(uv[:2]):
                failures.append(f"UV SANITY: {name} uv {ui} is non-finite")
                break

        for vi, vertex in enumerate(vertices):
            if not finite_vec(vertex[:3]):
                failures.append(f"VERTEX BOUNDS: {name} vertex {vi} is non-finite")
                break
            if any(abs(float(axis)) > VERTEX_LIMIT for axis in vertex[:3]):
                failures.append(f"VERTEX BOUNDS: {name} vertex {vi} exceeds +/-{VERTEX_LIMIT:g}")
                break

        for fi, face in enumerate(faces):
            try:
                idx = [int(face[0]), int(face[1]), int(face[2])]
            except Exception:
                failures.append(f"FACE WINDING: {name} face {fi} is malformed")
                break
            if any(i < 0 or i >= len(vertices) for i in idx):
                failures.append(f"FACE WINDING: {name} face {fi} index {idx} outside vertex range {len(vertices)}")
                break

        if renderer is not None:
            try:
                wp, wo, _ = renderer._node_world_transform(node)
                if not finite_vec(wp) or not finite_vec(wo):
                    failures.append(f"TRANSFORM CHAIN: {name} world transform is non-finite")
            except Exception as exc:
                failures.append(f"TRANSFORM CHAIN: {name}: {type(exc).__name__}: {exc}")

    # Check non-mesh transforms too.
    if renderer is not None:
        for node in model.all_nodes():
            if bool(getattr(node, "is_mesh", False)):
                continue
            try:
                wp, wo, _ = renderer._node_world_transform(node)
                if not finite_vec(wp) or not finite_vec(wo):
                    failures.append(f"TRANSFORM CHAIN: {_node_name(node)} world transform is non-finite")
            except Exception as exc:
                failures.append(f"TRANSFORM CHAIN: {_node_name(node)}: {type(exc).__name__}: {exc}")

    return {
        "game": game,
        "resref": resref,
        "passed": not failures,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "node_count": int(model.node_count() if hasattr(model, "node_count") else len(model.all_nodes())),
        "mesh_count": len(list(_iter_mesh_nodes(model))),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_args(parser)
    args = parser.parse_args()

    results = []
    summary = Counter()
    for index, (game, resref) in enumerate(iter_models(args.game, args.limit), start=1):
        result = _validate_model(game, resref)
        results.append(result)
        summary[(game, "passed" if result["passed"] else "failed")] += 1
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{index}] {game}:{resref} {status} ({result['duration_ms']} ms)")

    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    payload = {
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "by_game": {
                game: {
                    "passed": summary[(game, "passed")],
                    "failed": summary[(game, "failed")],
                    "total": summary[(game, "passed")] + summary[(game, "failed")],
                }
                for game in ("k1", "k2")
            },
        },
        "results": results,
    }
    write_json(EXPORTS / "structural_validation.json", payload)

    k1 = payload["summary"]["by_game"]["k1"]
    k2 = payload["summary"]["by_game"]["k2"]
    print(
        f"K1: {k1['passed']}/{k1['total']} passed | "
        f"K2: {k2['passed']}/{k2['total']} passed | "
        f"Total failures: {total - passed}"
    )
    print(f"{passed}/{total} passed, {total - passed} failures")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

