"""Inspect vanilla PMBAM animation/model structures for Sprint 3 R3.B."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
from src.core.game.kotor_loader import load_model_from_file
from src.core.retargeting.sampler import StockCorpusResourceManager


def _public_attrs(obj) -> list[str]:
    return [name for name in dir(obj) if not name.startswith("_")]


def main() -> int:
    pmbam_path = ROOT / "tests" / "fixtures" / "kotor_stock" / "k1" / "pmbam.mdl"
    output = ROOT / "exports" / "r3_idle_test" / "pmbam_vanilla_animation_inspection.json"
    output.parent.mkdir(parents=True, exist_ok=True)

    SuperModelResolver.configure(StockCorpusResourceManager(ROOT / "tests" / "fixtures" / "kotor_stock"))
    SuperModelResolver.clear_cache()
    model = load_model_from_file(str(pmbam_path), str(pmbam_path.with_suffix(".mdx")))
    if model is None:
        raise RuntimeError(f"Could not load {pmbam_path}")
    SuperModelResolver.prime_cache(model.name, model)

    engine = AnimationEngine(model)
    inherited = engine.list_all_animations()
    local_names = [anim.name for anim in model.animations]
    inherited_names = [entry.get("name") for entry in inherited]

    report = {
        "model_type": type(model).__name__,
        "model_name": model.name,
        "supermodel": model.supermodel,
        "root_node": model.root_node.name if model.root_node else None,
        "model_attrs": _public_attrs(model),
        "node_count": len(model.all_nodes()),
        "mesh_count": len(model.mesh_nodes()),
        "local_animation_count": len(model.animations),
        "local_animation_names": local_names,
        "inherited_animation_count": len(inherited),
        "victory_local": any(str(name).lower() == "victory" for name in local_names),
        "victory_inherited": any(str(name).lower() == "victory" for name in inherited_names),
        "sample_nodes": [],
        "sample_inherited_animations": inherited[:12],
        "local_animation_samples": [],
    }

    for node in model.all_nodes()[:12]:
        report["sample_nodes"].append(
            {
                "name": node.name,
                "parent": node.parent.name if node.parent else None,
                "type": type(node).__name__,
                "flags": int(node.flags),
                "type_label": node.type_label,
                "position": list(node.position),
                "rotation_xyzw": list(node.rotation),
                "controller_count": len(node.controllers),
            }
        )

    for anim in model.animations[:5]:
        sample = {
            "name": anim.name,
            "type": type(anim).__name__,
            "attrs": _public_attrs(anim),
            "length": anim.length,
            "transition_time": anim.transition_time,
            "anim_root": anim.anim_root,
            "node_count": len(anim.nodes),
            "first_node": None,
        }
        if anim.nodes:
            node = anim.nodes[0]
            sample["first_node"] = {
                "name": node.name,
                "attrs": _public_attrs(node),
                "controller_count": len(node.controllers),
                "controllers": node.controllers[:3],
            }
        report["local_animation_samples"].append(sample)

    output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote inspection to {output}")
    print(
        f"PMBAM: {report['node_count']} nodes, {report['mesh_count']} meshes, "
        f"{report['local_animation_count']} local animations, "
        f"{report['inherited_animation_count']} inherited animations"
    )
    print(f"victory local={report['victory_local']} inherited={report['victory_inherited']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
