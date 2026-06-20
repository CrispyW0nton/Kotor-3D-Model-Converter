"""Discovery helpers for generated lightmaps during export."""

from __future__ import annotations

import json
from pathlib import Path


def get_baked_lightmap_assignments(model: object | None) -> dict[str, str]:
    if model is None:
        return {}
    assignments = dict(getattr(model, "_gr_baked_lightmap_assignments", {}) or {})
    try:
        for node in model.all_nodes():
            path = str(getattr(node, "_gr_baked_lightmap_path", "") or "")
            if path:
                assignments[str(getattr(node, "name", "mesh"))] = path
    except Exception:
        pass
    return assignments


def resolve_lightmap_for_material(mesh: object, material: object | str | None = None) -> str:
    path = str(getattr(mesh, "_gr_baked_lightmap_path", "") or "")
    if path:
        return path
    return str(getattr(mesh, "lightmap", "") or "")


def export_baked_lightmap_manifest(model: object, output_directory: str | Path) -> str:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "baked_lightmap_assignments.json"
    assignments = get_baked_lightmap_assignments(model)
    data = {
        "assignments": [
            {"mesh": mesh, "lightmap": lightmap}
            for mesh, lightmap in sorted(assignments.items())
        ],
        "note": "Generated lightmaps are replacement assets; original KOTOR lightmap files were not overwritten.",
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)
