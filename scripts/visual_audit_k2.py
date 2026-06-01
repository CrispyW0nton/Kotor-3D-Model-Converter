"""Visual audit for representative K2 models.

This is a diagnostic-only script. It loads representative TSL models through
GhostRigger, inspects skin-node metadata, renders one headless PNG per model,
and prints enough information to identify renderer-vs-loader failure patterns.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from qa_common import EXPORTS, list_mdl_resources, load_ghostrigger_model, write_json


REQUIRED_K2_MODELS = [
    "c_bantha",
    "p_hanharr",
    "c_drdspyder",
    "c_drdminelg",
    "c_cannok",
    "c_zakkeg",
    "n_darthsion",
    "101peraz",
    "c_kinrath",
    "c_laigrek",
    "c_maalraas",
    "c_tuk_ata",
    "c_hsiss",
    "c_mykal",
    "c_orbalis",
    "c_skreev",
    "p_atton",
    "p_bao",
    "p_disciple",
    "p_goto",
    "p_handmaiden",
    "p_hk47",
    "p_kreia",
    "p_mandalore",
    "p_mira",
    "p_t3m4",
    "p_visas",
]


def _round_vec(values: Any, places: int = 5) -> list[float]:
    out: list[float] = []
    for item in values or []:
        try:
            value = float(item)
        except Exception:
            value = 0.0
        out.append(round(value, places) if math.isfinite(value) else value)
    return out


def _is_identity_quat(quat: Any, eps: float = 1e-3) -> bool:
    q = _round_vec(quat, 8)
    if len(q) < 4:
        return False
    direct = abs(q[0]) < eps and abs(q[1]) < eps and abs(q[2]) < eps and abs(q[3] - 1.0) < eps
    negated = abs(q[0]) < eps and abs(q[1]) < eps and abs(q[2]) < eps and abs(q[3] + 1.0) < eps
    return direct or negated


def _is_zero_pos(pos: Any, eps: float = 1e-3) -> bool:
    p = _round_vec(pos, 8)
    return len(p) >= 3 and all(abs(axis) < eps for axis in p[:3])


def _node_names(model: Any) -> set[str]:
    return {str(getattr(node, "name", "") or "").lower() for node in model.all_nodes()}


def _skin_summary(node: Any, names: set[str], renderer: Any | None) -> dict[str, Any]:
    vertices = list(getattr(node, "vertices", None) or [])
    skin_data = list(getattr(node, "skin_data", None) or [])
    bone_map = list(getattr(node, "bone_map", None) or [])
    qbone_list = list(getattr(node, "qbone_list", None) or [])
    tbone_list = list(getattr(node, "tbone_list", None) or [])

    unresolved = [
        {"index": index, "name": name}
        for index, name in enumerate(bone_map)
        if not name or str(name).lower() not in names
    ]

    try:
        world_pos, world_rot = node.world_transform()
    except Exception as exc:
        world_pos, world_rot = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
        unresolved.append({"index": -1, "name": f"world_transform error: {type(exc).__name__}: {exc}"})

    renderer_pos = renderer_rot = None
    renderer_identity = None
    if renderer is not None:
        try:
            renderer_pos, renderer_rot, renderer_identity = renderer._node_world_transform(node)
        except Exception as exc:
            renderer_pos, renderer_rot = None, f"{type(exc).__name__}: {exc}"
            renderer_identity = None

    first_skin_data = []
    for vertex in skin_data[:3]:
        influences = []
        for influence in list(getattr(vertex, "influences", None) or []):
            influences.append({
                "bone_index": int(getattr(influence, "bone_index", -1)),
                "weight": round(float(getattr(influence, "weight", 0.0) or 0.0), 6),
            })
        first_skin_data.append(influences)

    return {
        "name": str(getattr(node, "name", "") or ""),
        "bone_map_len": len(bone_map),
        "skin_data_len": len(skin_data),
        "vertex_count": len(vertices),
        "unresolved_bone_map": unresolved,
        "qbone_len": len(qbone_list),
        "tbone_len": len(tbone_list),
        "has_qbone_tbone": bool(qbone_list and tbone_list),
        "world_position": _round_vec(world_pos),
        "world_rotation": _round_vec(world_rot),
        "world_position_is_zero": _is_zero_pos(world_pos),
        "world_rotation_is_identity": _is_identity_quat(world_rot),
        "renderer_world_position": _round_vec(renderer_pos) if isinstance(renderer_pos, (tuple, list)) else renderer_pos,
        "renderer_world_rotation": _round_vec(renderer_rot) if isinstance(renderer_rot, (tuple, list)) else renderer_rot,
        "renderer_rotation_is_identity": renderer_identity,
        "first_vertices": [_round_vec(vertex) for vertex in vertices[:3]],
        "first_skin_data": first_skin_data,
    }


def _foreground_metrics(path: Path, background: tuple[int, int, int]) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    image = Image.open(path).convert("RGB")
    arr = np.asarray(image, dtype=np.int16)
    bg = np.asarray(background, dtype=np.int16)
    diff = np.abs(arr - bg).sum(axis=2)
    mask = diff > 10
    ys, xs = np.where(mask)
    if int(mask.sum()):
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    else:
        bbox = [0, 0, 0, 0]
    return {
        "width": int(image.width),
        "height": int(image.height),
        "non_black_pixels": int(mask.sum()),
        "bbox": bbox,
        "bbox_area": max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1]),
        "mean_brightness": float(arr.mean()),
    }


def _render_png(model: Any, game: str, resref: str, out_dir: Path) -> dict[str, Any]:
    import src.core.rendering.frame_core.colors as viewport_colors
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    old_bg = getattr(viewport_colors, "_BG", (18, 18, 40, 255))
    viewport_colors._BG = (0, 0, 0, 255)
    renderer = FrameRenderer(ArcBallCamera())
    renderer.show_texture = False
    renderer.show_bones = False
    renderer.set_model(model)
    try:
        image = renderer.render_still(512, 512, az_deg=-45.0, el_deg=20.0)
        if image is None:
            raise RuntimeError("headless renderer returned None")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{game}_{resref}_visual_audit.png"
        image.save(path)
    finally:
        viewport_colors._BG = old_bg

    metrics = _foreground_metrics(path, (0, 0, 0))
    metrics["path"] = str(path)
    pixels = int(metrics["non_black_pixels"])
    if pixels < 100:
        metrics["classification"] = "EMPTY"
    elif pixels > 5000:
        metrics["classification"] = "OK"
    else:
        metrics["classification"] = "BROKEN"
    return metrics


def _select_models(limit: int) -> list[str]:
    selected: list[str] = []
    for resref in REQUIRED_K2_MODELS:
        if resref not in selected:
            selected.append(resref)
    for resref in list_mdl_resources("k2"):
        if len(selected) >= limit:
            break
        if resref not in selected:
            selected.append(resref)
    return selected[:limit]


def audit_model(resref: str, out_dir: Path) -> dict[str, Any]:
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    result: dict[str, Any] = {"game": "k2", "resref": resref}
    try:
        model = load_ghostrigger_model("k2", resref)
    except Exception as exc:
        result.update({"status": "LOAD_FAIL", "error": f"{type(exc).__name__}: {exc}"})
        return result

    nodes = list(model.all_nodes())
    mesh_nodes = [node for node in nodes if bool(getattr(node, "is_mesh", False))]
    skin_nodes = [node for node in mesh_nodes if bool(getattr(node, "is_skin", False))]
    trimesh_nodes = [node for node in mesh_nodes if not bool(getattr(node, "is_skin", False))]
    names = _node_names(model)

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)

    result.update({
        "status": "LOADED",
        "node_count": len(nodes),
        "mesh_count": len(mesh_nodes),
        "skin_count": len(skin_nodes),
        "trimesh_count": len(trimesh_nodes),
        "skin_nodes": [_skin_summary(node, names, renderer) for node in skin_nodes],
    })

    try:
        result["render"] = _render_png(model, "k2", resref, out_dir)
    except Exception as exc:
        result["render"] = {"classification": "RENDER_FAIL", "error": f"{type(exc).__name__}: {exc}"}
    return result


def print_model(result: dict[str, Any]) -> None:
    resref = result["resref"]
    status = result.get("status")
    if status != "LOADED":
        print(f"k2:{resref} LOAD_FAIL {result.get('error')}")
        return
    render = result.get("render", {})
    print(
        f"k2:{resref} nodes={result['node_count']} mesh={result['mesh_count']} "
        f"skin={result['skin_count']} trimesh={result['trimesh_count']} "
        f"render={render.get('classification')} non_black={render.get('non_black_pixels')}"
    )
    for skin in result.get("skin_nodes", []):
        unresolved = skin.get("unresolved_bone_map", [])
        print(
            f"  skin {skin['name']}: bone_map={skin['bone_map_len']} "
            f"skin_data={skin['skin_data_len']} verts={skin['vertex_count']} "
            f"unresolved={len(unresolved)} qbone={skin['qbone_len']} tbone={skin['tbone_len']} "
            f"world_pos={skin['world_position']} zero={skin['world_position_is_zero']} "
            f"world_rot={skin['world_rotation']} identity={skin['world_rotation_is_identity']} "
            f"renderer_rot={skin['renderer_world_rotation']} renderer_identity={skin['renderer_rotation_is_identity']}"
        )
        if unresolved:
            print(f"    unresolved sample: {unresolved[:5]}")
        print(f"    first_vertices={skin['first_vertices']}")
        print(f"    first_skin_data={skin['first_skin_data']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out-dir", type=Path, default=EXPORTS / "visual_audit_k2")
    args = parser.parse_args()

    models = _select_models(args.limit)
    print(f"Visual audit K2 models: {len(models)}")
    results = []
    counts: dict[str, int] = {}
    for index, resref in enumerate(models, start=1):
        print(f"[{index}/{len(models)}] auditing k2:{resref}")
        result = audit_model(resref, args.out_dir)
        results.append(result)
        classification = result.get("render", {}).get("classification", result.get("status", "UNKNOWN"))
        counts[classification] = counts.get(classification, 0) + 1
        print_model(result)

    payload = {"summary": counts, "models": results}
    write_json(EXPORTS / "visual_audit_k2.json", payload)
    print(f"Summary: {counts}")
    print(f"Wrote {EXPORTS / 'visual_audit_k2.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
