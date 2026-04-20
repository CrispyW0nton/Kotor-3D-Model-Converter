"""
tools/model_inspector.py — Headless KotOR MDL node-tree diagnostic.

Purpose
-------
Dump the full parsed node hierarchy of a KotOR MDL (+ optional MDX) without
opening the GUI viewport.  Useful for answering "is this model broken at the
parse layer or only at render time?" without screenshots.

For every node the report prints:
    * index and DFS depth
    * ModelNode.name
    * type_label  (dummy / trimesh / skin / danglymesh / light / emitter / ...)
    * flags  (raw int)
    * vertex_space  (NODE_LOCAL / WORLD / AABB_WALK)
    * local position, local rotation (xyzw quaternion)
    * computed world_position / world_transform (rotation)
    * vertex / face / uv counts
    * bone_map (for skin nodes)
    * an ``INNER_GEO`` marker when the node name matches
      ``render_constants.INNER_GEO_SUBSTRINGS``

Inner-geometry nodes (eyes / teeth / tongue / gum / jaw) get an explicit
world-position block so you can tell at a glance whether they are
mathematically positioned inside the outer face mesh — independent of any
rendering bug.

Usage
-----

    # Load from a raw MDL (+ optional MDX) on disk:
    python -m tools.model_inspector --mdl path/to/pfhc01.mdl

    # Load a resref through a full KotOR installation (uses KEY/BIF + Override):
    python -m tools.model_inspector --game-dir "C:/GOG/KotOR" --resref pfhc01

    # JSON output (for diffing / regression tests):
    python -m tools.model_inspector --mdl pfhc01.mdl --json > pfhc01.json

This script intentionally has ZERO rendering dependencies.  It must run on a
headless box (no Tk, no moderngl, no EGL) so it works inside CI and over SSH.

It is importable — ``inspect_model(model) -> dict`` returns the structured
report for programmatic use.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Project path wiring ────────────────────────────────────────────────────
# Allow invocation both as ``python -m tools.model_inspector`` (repo root) and
# as a plain script (``python tools/model_inspector.py``) — make ``src``
# importable either way.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


log = logging.getLogger("model_inspector")


# ── Lazy imports of project modules (keep startup headless-friendly) ───────
def _import_core():
    """Return (model_data, vertex_space, render_constants) modules."""
    from src.core import model_data as _md
    from src.core import vertex_space as _vs
    from src.core import render_constants as _rc
    return _md, _vs, _rc


# ── Vector helpers ─────────────────────────────────────────────────────────
def _fmt_vec3(v: Tuple[float, float, float], width: int = 9) -> str:
    return f"({v[0]:+{width}.4f}, {v[1]:+{width}.4f}, {v[2]:+{width}.4f})"


def _fmt_quat(q: Tuple[float, float, float, float]) -> str:
    return (
        f"({q[0]:+.4f}, {q[1]:+.4f}, {q[2]:+.4f}, {q[3]:+.4f})"
    )


# ── Core inspection logic ──────────────────────────────────────────────────
def inspect_model(model) -> Dict[str, Any]:
    """Return a structured report dict for ``model`` (a :class:`KotorModel`).

    The dict contains:
        'model'    : top-level metadata (name, classification, game_version,
                      supermodel, model_type, bb_min/max, radius)
        'nodes'    : list of per-node dicts in DFS order
        'inner_geo': list of per-inner-geo-node dicts (subset of 'nodes')
    """
    _md, _vs, _rc = _import_core()

    if model is None:
        raise ValueError("inspect_model: model is None")

    # Build per-node depth map (DFS, stack-based — same traversal as
    # KotorModel.all_nodes but we want depth too).
    depth: Dict[int, int] = {}
    all_nodes: List[Any] = []
    root = getattr(model, 'root_node', None)
    if root is not None:
        stack: List[Tuple[Any, int]] = [(root, 0)]
        visited: set = set()
        while stack:
            n, d = stack.pop()
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            depth[nid] = d
            all_nodes.append(n)
            for c in reversed(getattr(n, 'children', []) or []):
                stack.append((c, d + 1))

    try:
        vs_names = {int(m.value): m.name for m in _vs.VertexSpace}
    except Exception:
        vs_names = {0: 'NODE_LOCAL', 1: 'WORLD', 2: 'AABB_WALK'}

    inner_substrings = tuple(getattr(_rc, 'INNER_GEO_SUBSTRINGS', ()))
    is_inner = getattr(_rc, 'is_inner_geometry_name', None)
    if not callable(is_inner):
        def is_inner(name: str) -> bool:  # type: ignore[misc]
            nl = (name or '').lower()
            return any(s in nl for s in inner_substrings)

    nodes_out: List[Dict[str, Any]] = []
    inner_out: List[Dict[str, Any]] = []

    for idx, n in enumerate(all_nodes):
        name = str(getattr(n, 'name', '') or '')
        flags = int(getattr(n, 'flags', 0) or 0)
        vs_int = int(getattr(n, 'vertex_space', 0) or 0)
        pos = tuple(getattr(n, 'position', (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0))
        rot = tuple(getattr(n, 'rotation', (0.0, 0.0, 0.0, 1.0)) or
                    (0.0, 0.0, 0.0, 1.0))
        verts = getattr(n, 'vertices', []) or []
        faces = getattr(n, 'faces', []) or []
        uvs = getattr(n, 'uvs', []) or []

        # world_transform on the ModelNode gives us both world pos and quat.
        world_pos: Optional[Tuple[float, float, float]] = None
        world_rot: Optional[Tuple[float, float, float, float]] = None
        world_err: Optional[str] = None
        try:
            wp, wo = n.world_transform()
            world_pos = (float(wp[0]), float(wp[1]), float(wp[2]))
            world_rot = (float(wo[0]), float(wo[1]),
                         float(wo[2]), float(wo[3]))
        except Exception as exc:
            world_err = f"world_transform failed: {exc}"

        parent_name = ''
        p = getattr(n, 'parent', None)
        if p is not None:
            parent_name = str(getattr(p, 'name', '') or '')

        is_mesh = bool(getattr(n, 'is_mesh', False))
        is_skin = bool(getattr(n, 'is_skin', False))
        type_label = str(getattr(n, 'type_label', '') or '')

        # bone_map: only meaningful on skin nodes
        bone_map = list(getattr(n, 'bone_map', []) or [])
        bone_map_floats = list(getattr(n, 'bone_map_floats', []) or [])

        inner_match = is_inner(name)

        node_rec: Dict[str, Any] = {
            'index': idx,
            'depth': depth.get(id(n), 0),
            'name': name,
            'parent': parent_name,
            'type_label': type_label,
            'flags': flags,
            'flags_hex': f'0x{flags:04x}',
            'is_mesh': is_mesh,
            'is_skin': is_skin,
            'vertex_space': vs_int,
            'vertex_space_name': vs_names.get(vs_int, f'UNKNOWN({vs_int})'),
            'position_local': list(pos),
            'rotation_local': list(rot),
            'world_position': list(world_pos) if world_pos else None,
            'world_rotation': list(world_rot) if world_rot else None,
            'world_transform_error': world_err,
            'vertex_count': len(verts),
            'face_count': len(faces),
            'uv_count': len(uvs),
            'texture': str(getattr(n, 'texture', '') or ''),
            'lightmap': str(getattr(n, 'lightmap', '') or ''),
            'render_flag': bool(getattr(n, 'render', True)),
            'transparency_hint': int(getattr(n, 'transparency_hint', 0) or 0),
            'bone_map': bone_map,
            'bone_map_floats': bone_map_floats,
            'is_inner_geometry': inner_match,
        }
        nodes_out.append(node_rec)
        if inner_match:
            inner_out.append(node_rec)

    report: Dict[str, Any] = {
        'model': {
            'name': str(getattr(model, 'name', '') or ''),
            'supermodel': str(getattr(model, 'supermodel', '') or ''),
            'classification': str(getattr(model, 'classification', '') or ''),
            'model_type': int(getattr(model, 'model_type', 0) or 0),
            'subclassification': int(getattr(model, 'subclassification', 0)
                                     or 0),
            'game_version': str(getattr(
                getattr(model, 'game_version', ''), 'name',
                getattr(model, 'game_version', ''))) or '',
            'bb_min': list(getattr(model, 'bb_min', (0, 0, 0)) or (0, 0, 0)),
            'bb_max': list(getattr(model, 'bb_max', (0, 0, 0)) or (0, 0, 0)),
            'radius': float(getattr(model, 'radius', 0.0) or 0.0),
            'node_count': len(all_nodes),
            'animation_count': len(getattr(model, 'animations', []) or []),
            'mdl_path': str(getattr(model, 'mdl_path', '') or ''),
            'mdx_path': str(getattr(model, 'mdx_path', '') or ''),
        },
        'nodes': nodes_out,
        'inner_geo': inner_out,
    }
    return report


# ── Pretty-printer ─────────────────────────────────────────────────────────
def format_report(report: Dict[str, Any]) -> str:
    """Return a human-readable multi-line rendering of ``report``."""
    lines: List[str] = []
    m = report['model']
    lines.append("=" * 78)
    lines.append(f"MODEL: {m['name']!r}")
    lines.append(f"  classification  : {m['classification']} "
                 f"(model_type={m['model_type']}, "
                 f"subclass={m['subclassification']})")
    lines.append(f"  game_version    : {m['game_version']}")
    lines.append(f"  supermodel      : {m['supermodel']!r}")
    lines.append(f"  nodes           : {m['node_count']}")
    lines.append(f"  animations      : {m['animation_count']}")
    lines.append(f"  bb_min / bb_max : "
                 f"{_fmt_vec3(tuple(m['bb_min']))}  "
                 f"{_fmt_vec3(tuple(m['bb_max']))}")
    lines.append(f"  radius          : {m['radius']:.4f}")
    if m.get('mdl_path'):
        lines.append(f"  mdl_path        : {m['mdl_path']}")
    lines.append("=" * 78)
    lines.append("")

    # Full tree
    lines.append("NODE TREE (DFS order)")
    lines.append("-" * 78)
    for rec in report['nodes']:
        indent = "  " * rec['depth']
        marker = " [INNER_GEO]" if rec['is_inner_geometry'] else ""
        lines.append(
            f"{rec['index']:4d}  {indent}{rec['name']!r:<32s}  "
            f"{rec['type_label']:<12s}  flags={rec['flags_hex']:>6s}  "
            f"vs={rec['vertex_space_name']}{marker}"
        )
        lines.append(
            f"      {indent}  parent={rec['parent']!r}  "
            f"verts={rec['vertex_count']}  faces={rec['face_count']}  "
            f"uvs={rec['uv_count']}  "
            f"tex={rec['texture']!r}  render={rec['render_flag']}"
        )
        lines.append(
            f"      {indent}  pos_local ={_fmt_vec3(tuple(rec['position_local']))}  "
            f"rot_local ={_fmt_quat(tuple(rec['rotation_local']))}"
        )
        if rec['world_position'] is not None:
            lines.append(
                f"      {indent}  pos_world ={_fmt_vec3(tuple(rec['world_position']))}  "
                f"rot_world ={_fmt_quat(tuple(rec['world_rotation']))}"
            )
        elif rec['world_transform_error']:
            lines.append(f"      {indent}  WORLD TRANSFORM FAIL: "
                         f"{rec['world_transform_error']}")
        if rec['is_skin'] and rec['bone_map']:
            shown = rec['bone_map'][:8]
            extra = len(rec['bone_map']) - len(shown)
            bm_str = ', '.join(f"{i}={n!r}" for i, n in enumerate(shown))
            if extra > 0:
                bm_str += f", … ({extra} more)"
            lines.append(f"      {indent}  bone_map[{len(rec['bone_map'])}]: "
                         f"{bm_str}")
    lines.append("")

    # Inner-geo focused view
    lines.append("INNER-GEOMETRY NODES "
                 "(eye / eyelid / teeth / tongue / gum / jaw)")
    lines.append("-" * 78)
    if not report['inner_geo']:
        lines.append("  (none found)")
    else:
        for rec in report['inner_geo']:
            lines.append(
                f"  {rec['name']!r:<32s}  {rec['type_label']:<12s}  "
                f"vs={rec['vertex_space_name']:<10s}  "
                f"verts={rec['vertex_count']:>5d}  "
                f"faces={rec['face_count']:>5d}"
            )
            if rec['world_position'] is not None:
                lines.append(
                    f"      world_pos={_fmt_vec3(tuple(rec['world_position']))}  "
                    f"world_rot={_fmt_quat(tuple(rec['world_rotation']))}"
                )
            lines.append(
                f"      local_pos={_fmt_vec3(tuple(rec['position_local']))}  "
                f"parent={rec['parent']!r}"
            )
    lines.append("=" * 78)
    return "\n".join(lines)


# ── Model loaders ──────────────────────────────────────────────────────────
def _load_from_files(mdl_path: str, mdx_path: Optional[str] = None):
    """Parse an MDL (+ optional sibling MDX) from disk."""
    from src.core.kotor_loader import load_model_from_file

    mp = Path(mdl_path)
    if not mp.exists():
        raise FileNotFoundError(f"MDL not found: {mdl_path}")

    resolved_mdx = mdx_path or ''
    if not resolved_mdx:
        guess = mp.with_suffix('.mdx')
        if guess.exists():
            resolved_mdx = str(guess)

    return load_model_from_file(str(mp), resolved_mdx)


def _load_from_install(game_dir: str, resref: str):
    """Parse a model by resref using a KotOR installation root."""
    from src.core.kotor_install import KotorInstallation

    if not os.path.isdir(game_dir):
        raise FileNotFoundError(f"Game dir not found: {game_dir}")
    install = KotorInstallation(game_dir)
    model = install.load_model(resref)
    if model is None:
        raise LookupError(
            f"Model {resref!r} not found in installation at {game_dir!r}")
    return model


# ── CLI ────────────────────────────────────────────────────────────────────
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='model_inspector',
        description=(
            "Dump the parsed node tree of a KotOR MDL without opening the "
            "GUI.  Prints positions, orientations, vertex_space tags, bone "
            "maps, and computed world positions for every node, plus a "
            "focused view of inner-geometry (eye/teeth/tongue/gum/jaw) "
            "nodes."
        ),
    )
    src_grp = p.add_mutually_exclusive_group(required=True)
    src_grp.add_argument('--mdl', help='Path to a .mdl file on disk')
    src_grp.add_argument('--resref',
                         help='Resref name to resolve via --game-dir')

    p.add_argument('--mdx',
                   help='Path to a .mdx file (default: sibling of --mdl)')
    p.add_argument('--game-dir',
                   help='KotOR installation root (required with --resref)')
    p.add_argument('--json', action='store_true',
                   help='Emit JSON instead of the human-readable report')
    p.add_argument('--output', '-o',
                   help='Write output to this file instead of stdout')
    p.add_argument('--verbose', '-v', action='store_true',
                   help='Enable DEBUG logging')
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s %(name)s: %(message)s',
    )

    if args.resref and not args.game_dir:
        parser.error("--resref requires --game-dir")

    try:
        if args.mdl:
            model = _load_from_files(args.mdl, args.mdx)
        else:
            model = _load_from_install(args.game_dir, args.resref)
    except Exception as exc:
        log.error("Failed to load model: %s", exc, exc_info=args.verbose)
        return 2

    if model is None:
        log.error("Model loaded as None (loader returned no data)")
        return 3

    try:
        report = inspect_model(model)
    except Exception as exc:
        log.error("inspect_model failed: %s", exc, exc_info=args.verbose)
        return 4

    if args.json:
        text = json.dumps(report, indent=2, default=str)
    else:
        text = format_report(report)

    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
        log.info("Wrote report to %s", args.output)
    else:
        print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
