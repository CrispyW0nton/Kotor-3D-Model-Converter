"""Diagnose current bind-pose transforms for skin vs trimesh nodes."""

from __future__ import annotations

import argparse
from typing import Any

from qa_common import load_ghostrigger_model


def _round_vec(values: Any, places: int = 5) -> list[float]:
    out = []
    for item in values or []:
        try:
            out.append(round(float(item), places))
        except Exception:
            out.append(0.0)
    return out


def _parent_chain(node: Any) -> list[Any]:
    chain = []
    seen: set[int] = set()
    current = node
    while current is not None and id(current) not in seen and len(chain) < 512:
        seen.add(id(current))
        chain.append(current)
        current = getattr(current, "parent", None)
    chain.reverse()
    return chain


def _print_chain(node: Any) -> None:
    print("  parent_chain root->node:")
    for item in _parent_chain(node):
        print(
            f"    {getattr(item, 'name', '<unnamed>')} "
            f"pos={_round_vec(getattr(item, 'position', (0, 0, 0)))} "
            f"rot={_round_vec(getattr(item, 'rotation', (0, 0, 0, 1)))}"
        )


def _print_vertex_rows(label: str, rows: list[Any]) -> None:
    print(f"  {label}:")
    for index, row in enumerate(rows[:5]):
        print(f"    [{index}] {_round_vec(row)}")


def _diagnose_node(renderer: Any, node: Any, kind: str) -> None:
    print()
    print(f"{kind} NODE {getattr(node, 'name', '<unnamed>')}")
    print(
        f"  flags=0x{int(getattr(node, 'flags', 0)):04x} "
        f"is_skin={bool(getattr(node, 'is_skin', False))} "
        f"is_mesh={bool(getattr(node, 'is_mesh', False))} "
        f"vertex_space={getattr(node, 'vertex_space', None)}"
    )
    print(f"  local_position={_round_vec(getattr(node, 'position', (0, 0, 0)))}")
    print(f"  local_rotation={_round_vec(getattr(node, 'rotation', (0, 0, 0, 1)))}")
    _print_chain(node)

    wp, wo = node.world_transform()
    rwp, rwo, rid = renderer._node_world_transform(node)
    print(f"  model_data.world_transform wp={_round_vec(wp)} wo={_round_vec(wo)}")
    print(f"  renderer._node_world_transform wp={_round_vec(rwp)} wo={_round_vec(rwo)} is_id={rid}")

    raw = list(getattr(node, "vertices", None) or [])[:5]
    current = renderer._get_world_verts_for_node(node)[:5]
    if bool(getattr(node, "is_skin", False)):
        should = raw
    else:
        should = current
    _print_vertex_rows("raw vertices", raw)
    _print_vertex_rows("current renderer vertices", current)
    _print_vertex_rows("expected bind-pose vertices", should)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=["k1", "k2"], default="k2")
    parser.add_argument("--resref", default="c_bantha")
    args = parser.parse_args()

    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    model = load_ghostrigger_model(args.game, args.resref)
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)

    nodes = list(model.all_nodes())
    skin_nodes = [
        node for node in nodes
        if bool(getattr(node, "is_mesh", False)) and bool(getattr(node, "is_skin", False))
    ]
    trimesh = next(
        (
            node for node in nodes
            if bool(getattr(node, "is_mesh", False))
            and not bool(getattr(node, "is_skin", False))
            and getattr(node, "vertices", None)
            and getattr(node, "faces", None)
        ),
        None,
    )

    print(f"Transform diagnosis for {args.game}:{args.resref}")
    print(f"nodes={len(nodes)} skin_nodes={len(skin_nodes)}")
    for node in skin_nodes:
        _diagnose_node(renderer, node, "SKIN")
    if trimesh is not None:
        _diagnose_node(renderer, trimesh, "TRIMESH CONTROL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
