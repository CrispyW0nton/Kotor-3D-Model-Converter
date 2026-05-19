"""Regenerate the 3i diagnostic dumps including Step 6 pre-qBone basis
provenance and Step 7 B-translation diagnostic fields.

This is a headless probe.  It does NOT spin up an OpenGL context; it
imports ``_build_skin_dump_record`` directly and feeds it a fully
constructed ``MatrixPaletteUploader`` plus an ``AnimPose`` evaluated at
``cwalk t=0.0``.  The Step 6/7 diagnostic fields fall back gracefully
when no ``_GpuMesh`` is provided (``vbo == raw`` is already proven by
Step 1).

Outputs (one JSONL per audited creature):

- ``diagnostics/skinning/2026_05/skin_c_drexlf_3i.jsonl``
- ``diagnostics/skinning/2026_05/skin_c_brith_3i.jsonl``
- ``diagnostics/skinning/2026_05/skin_c_bomabeast_3i.jsonl``

Usage::

    python scripts/regen_skin_3i_step6_dump.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

K1_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
K2_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

OUT_DIR = ROOT / "diagnostics" / "skinning" / "2026_05"

# (resref, game, dump filename) — the three audit-control creatures.
TARGETS: Tuple[Tuple[str, str, str], ...] = (
    ("c_drexlf",   "K2", "skin_c_drexlf_3i.jsonl"),
    ("c_brith",    "K2", "skin_c_brith_3i.jsonl"),
    ("c_bomabeast","K1", "skin_c_bomabeast_3i.jsonl"),
)


def _dump_one(rm, resref: str, game: str, out_path: Path) -> int:
    from src.core.animation_engine import AnimationEngine
    from src.core.gpu_skinning import MatrixPaletteUploader
    from src.gui.qt_lib.rendering.gpu_renderer import _build_skin_dump_record

    model = rm.load_model(resref, game)
    if model is None:
        print(f"[regen_3i] ERR: failed to load {resref} from {game}", file=sys.stderr)
        return 0
    engine = AnimationEngine(model)
    try:
        engine.play("cwalk", loop=True, blend=False)
        pose = engine.evaluate(0.0)
    except Exception as exc:
        print(
            f"[regen_3i] WARN: {resref} engine.play('cwalk') raised {exc!r}; "
            f"falling back to bind pose",
            file=sys.stderr,
        )
        pose = None
    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(model)
    skin_nodes = [n for n in model.all_nodes() if getattr(n, "is_skin", False)]
    if not skin_nodes:
        print(f"[regen_3i] ERR: no skin nodes in {resref}", file=sys.stderr)
        return 0
    written: List[str] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for node in skin_nodes:
            try:
                uploader.compute_skin_node_palette(node, pose)
            except Exception as exc:
                print(
                    f"[regen_3i] WARN: {resref}/{node.name} "
                    f"compute_skin_node_palette raised {exc!r}",
                    file=sys.stderr,
                )
                continue
            try:
                rec = _build_skin_dump_record(
                    model=model,
                    node=node,
                    pass_name="opaque",
                    uploader=uploader,
                    bone_remap=None,
                    uniforms={},
                    gm=None,
                    anim_pose=pose,
                    anim_base_pose=pose,
                    anim_time=0.0,
                )
            except Exception as exc:
                print(
                    f"[regen_3i] WARN: {resref}/{node.name} "
                    f"_build_skin_dump_record raised {exc!r}",
                    file=sys.stderr,
                )
                continue
            rec["_regen_source"] = "scripts/regen_skin_3i_step6_dump.py"
            rec["_regen_at"] = time.time()
            rec["_regen_resref"] = resref
            rec["_regen_game"] = game
            fh.write(json.dumps(rec, sort_keys=True))
            fh.write("\n")
            written.append(getattr(node, "name", "?"))
    print(f"[regen_3i] {resref} ({game}): wrote {len(written)} skin draws to {out_path}")
    if written:
        print(f"[regen_3i]   nodes: {', '.join(written)}")
    return len(written)


def main() -> int:
    from src.core.resource_manager import ResourceManager
    from src.core.animation_engine import SuperModelResolver

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[regen_3i] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[regen_3i] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        print("[regen_3i] ERR: no game install indexed", file=sys.stderr)
        return 2
    SuperModelResolver._resource_manager = rm

    total = 0
    for resref, game, name in TARGETS:
        total += _dump_one(rm, resref, game, OUT_DIR / name)
    print(f"[regen_3i] total skin draws written: {total}")
    return 0 if total else 3


if __name__ == "__main__":
    raise SystemExit(main())
