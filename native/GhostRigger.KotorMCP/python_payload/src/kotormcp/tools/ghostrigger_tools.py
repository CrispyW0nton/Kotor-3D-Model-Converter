"""Compatibility helpers for GhostRigger MCP model validation.

Older scan scripts import ``kotormcp.tools.ghostrigger_tools`` directly.  The
MCP tool handlers now live in :mod:`kotormcp.tools.ghostrigger`, but the full
scan still needs direct, synchronous helpers for PyKotor-vs-GhostRigger parity.
"""

from __future__ import annotations

import os
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Optional

from kotormcp.adapters import get_default_registry
from kotormcp.ports import ResourceEntry


ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = ROOT / "settings.json"
_game_library: Any = None


def _load_local_game_paths() -> None:
    """Seed K1_PATH/K2_PATH from settings.json when the environment is empty."""
    if os.environ.get("K1_PATH") and os.environ.get("K2_PATH"):
        return
    try:
        import json

        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if data.get("k1_dir"):
        os.environ.setdefault("K1_PATH", str(data["k1_dir"]))
    if data.get("k2_dir"):
        os.environ.setdefault("K2_PATH", str(data["k2_dir"]))


def _game_version(game: str):
    from src.core.geometry.model_data import GameVersion

    return GameVersion.K2 if str(game).lower() in {"k2", "tsl", "kotor2"} else GameVersion.K1


def _resource_pair(game: str, resref: str) -> tuple[str, ResourceEntry, Optional[ResourceEntry]]:
    """Return the installation MDL/MDX resources for ``game:resref``."""
    _load_local_game_paths()
    registry = get_default_registry()
    game_obj = registry.resolve(game)
    if game_obj is None:
        raise ValueError(f"Unknown game alias: {game!r}")
    installation = registry.load(game_obj)
    mdl = installation.get_resource(resref, "mdl")
    if mdl is None:
        raise FileNotFoundError(f"MDL not found in {game}: {resref}")
    mdx = installation.get_resource(resref, "mdx")
    label = f"{installation.game_name()}:{mdl.resref}.mdl"
    return label, mdl, mdx


def _load_pykotor_model(game: str, resref: str):
    from src.core.mdl.mdl_reader_wrapper import read_mdl_safe

    _, mdl, mdx = _resource_pair(game, resref)
    return read_mdl_safe(mdl.data, source_ext=mdx.data if mdx is not None else None)


def _load_ghostrigger_model(game: str, resref: str):
    from src.core.game.kotor_loader import load_model_from_bytes

    _, mdl, mdx = _resource_pair(game, resref)
    model = load_model_from_bytes(
        mdl.data,
        mdx.data if mdx is not None else b"",
        game_version=_game_version(game),
    )
    if model is None:
        raise ValueError(f"GhostRigger failed to load {game}:{resref}")
    return model


def _vec(values: Any) -> list[float]:
    if values is None:
        return []
    if all(hasattr(values, attr) for attr in ("x", "y", "z")):
        return [float(values.x), float(values.y), float(values.z)]
    try:
        return [float(v) for v in values]
    except Exception:
        return []


def _close_quat(left: Any, right: Any, tol: float = 1e-5) -> bool:
    """Return True when quaternions match, allowing the equivalent negated form."""
    a = _vec(left)
    b = _vec(right)
    if len(a) != 4 or len(b) != 4:
        return False
    if any(not math.isfinite(v) for v in (*a, *b)):
        return False

    def close(sign: float) -> bool:
        return all(abs(a[i] - sign * b[i]) <= tol for i in range(4))

    return close(1.0) or close(-1.0)


def _face_tuple(face: Any) -> tuple[int, int, int] | None:
    if all(hasattr(face, attr) for attr in ("v1", "v2", "v3")):
        return (int(face.v1), int(face.v2), int(face.v3))
    try:
        a, b, c = face
        return (int(a), int(b), int(c))
    except Exception:
        return None


def _node_type_value(node: Any) -> int:
    raw = getattr(node, "node_type", getattr(node, "flags", 0))
    try:
        return int(raw)
    except Exception:
        return 0


def _pk_mesh(node: Any) -> Any:
    return getattr(node, "skin", None) or getattr(node, "mesh", None)


def _pk_node_summary(node: Any) -> dict[str, Any]:
    mesh = _pk_mesh(node)
    vertices = list(getattr(mesh, "vertex_positions", []) or []) if mesh is not None else []
    if not vertices:
        vertices = list(getattr(mesh, "vertex_bones", []) or []) if mesh is not None else []
    faces = list(getattr(mesh, "faces", []) or []) if mesh is not None else []
    texture = str(getattr(mesh, "texture_1", "") or "") if mesh is not None else ""
    lightmap = str(getattr(mesh, "texture_2", "") or "") if mesh is not None else ""
    return {
        "name": str(getattr(node, "name", "")),
        "node_id": int(getattr(node, "node_id", -1)),
        "parent_id": int(getattr(node, "parent_id", -1)),
        "node_type": _node_type_value(node),
        "position": _vec(getattr(node, "position", None)),
        "orientation": _vec(getattr(node, "orientation", None)),
        "is_mesh": mesh is not None,
        "is_skin": getattr(node, "skin", None) is not None,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "texture": texture,
        "lightmap": lightmap,
    }


def _gr_node_summary(node: Any) -> dict[str, Any]:
    vertices = list(getattr(node, "vertices", []) or [])
    faces = list(getattr(node, "faces", []) or [])
    parent = getattr(node, "parent", None)
    return {
        "name": str(getattr(node, "name", "")),
        "node_id": int(getattr(node, "index", getattr(node, "number", -1)) or -1),
        "parent_id": int(getattr(parent, "index", -1) if parent is not None else -1),
        "node_type": _node_type_value(node),
        "position": _vec(getattr(node, "position", None)),
        "orientation": _vec(getattr(node, "rotation", None)),
        "is_mesh": bool(getattr(node, "is_mesh", False)),
        "is_skin": bool(getattr(node, "is_skin", False)),
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "texture": str(getattr(node, "texture", "") or ""),
        "lightmap": str(getattr(node, "lightmap", "") or ""),
    }


def _all_nodes(model: Any) -> list[Any]:
    nodes = getattr(model, "all_nodes", None)
    if callable(nodes):
        return list(nodes())
    return list(nodes or [])


def _animation_names(model: Any) -> list[str]:
    return [str(getattr(anim, "name", anim)) for anim in getattr(model, "animations", []) or []]


def _model_type(model: Any) -> int:
    if hasattr(model, "model_type"):
        try:
            return int(getattr(model, "model_type"))
        except Exception:
            return 0
    try:
        return int(getattr(model, "classification", 0))
    except Exception:
        return 0


def inspect_mdl(game: str, resref: str) -> dict[str, Any]:
    """Inspect the raw PyKotor model, used as MCP ground truth."""
    model = _load_pykotor_model(game, resref)
    nodes = _all_nodes(model)
    summaries = [_pk_node_summary(node) for node in nodes]
    mesh_nodes = [item for item in summaries if item["is_mesh"]]
    skin_nodes = [item for item in summaries if item["is_skin"]]
    return {
        "game": game,
        "resref": resref,
        "name": str(getattr(model, "name", "")),
        "supermodel": str(getattr(model, "supermodel", "") or ""),
        "model_type": _model_type(model),
        "node_count": len(nodes),
        "mesh_node_count": len(mesh_nodes),
        "skin_node_count": len(skin_nodes),
        "total_vertices": sum(int(item["vertex_count"]) for item in mesh_nodes),
        "total_faces": sum(int(item["face_count"]) for item in mesh_nodes),
        "animations": _animation_names(model),
        "nodes": summaries,
        "skin_nodes": skin_nodes,
    }


def inspect_mdl_ghostrigger(game: str, resref: str) -> dict[str, Any]:
    """Inspect GhostRigger's imported model representation."""
    model = _load_ghostrigger_model(game, resref)
    nodes = _all_nodes(model)
    summaries = [_gr_node_summary(node) for node in nodes]
    mesh_nodes = [item for item in summaries if item["is_mesh"] or item["is_skin"]]
    skin_nodes = [item for item in summaries if item["is_skin"]]
    return {
        "game": game,
        "resref": resref,
        "name": str(getattr(model, "name", "")),
        "supermodel": str(getattr(model, "supermodel", "") or ""),
        "model_type": _model_type(model),
        "node_count": len(nodes),
        "mesh_node_count": len(mesh_nodes),
        "skin_node_count": len(skin_nodes),
        "total_vertices": sum(int(item["vertex_count"]) for item in mesh_nodes),
        "total_faces": sum(int(item["face_count"]) for item in mesh_nodes),
        "animations": _animation_names(model),
        "nodes": summaries,
        "skin_nodes": skin_nodes,
    }


def _names(summary: dict[str, Any]) -> list[str]:
    return [str(node.get("name", "")) for node in summary.get("nodes", [])]


def compare_model_pipelines(game: str, resref: str) -> dict[str, Any]:
    """Compare PyKotor ground truth against GhostRigger's imported model."""
    raw = inspect_mdl(game, resref)
    gr = inspect_mdl_ghostrigger(game, resref)
    raw_names = _names(raw)
    gr_names = _names(gr)
    raw_set = set(raw_names)
    gr_set = set(gr_names)
    discrepancies: list[dict[str, Any]] = []

    def add(field: str, pykotor: Any, ghostrigger: Any) -> None:
        if pykotor != ghostrigger:
            discrepancies.append(
                {"field": field, "pykotor": pykotor, "ghostrigger": ghostrigger},
            )

    add("name", raw["name"].lower(), gr["name"].lower())
    add("supermodel", raw["supermodel"].lower(), gr["supermodel"].lower())
    add("model_type", raw["model_type"], gr["model_type"])
    add("node_count", raw["node_count"], gr["node_count"])
    add("node_order", raw_names, gr_names)
    add("animations", raw["animations"], gr["animations"])

    raw_by_name = {str(item["name"]).lower(): item for item in raw["nodes"]}
    gr_by_name = {str(item["name"]).lower(): item for item in gr["nodes"]}
    for name in sorted(set(raw_by_name) & set(gr_by_name)):
        raw_node = raw_by_name[name]
        gr_node = gr_by_name[name]
        add(f"node:{name}:is_skin", raw_node["is_skin"], gr_node["is_skin"])
        add(f"node:{name}:vertex_count", raw_node["vertex_count"], gr_node["vertex_count"])

    return {
        "game": game,
        "resref": resref,
        "match": not discrepancies and raw_set == gr_set,
        "node_count_pykotor": raw["node_count"],
        "node_count_ghostrigger": gr["node_count"],
        "missing_in_ghostrigger": sorted(raw_set - gr_set),
        "extra_in_ghostrigger": sorted(gr_set - raw_set),
        "discrepancies": discrepancies,
        "pykotor": raw,
        "ghostrigger": gr,
    }


def _texture_names(model: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in _all_nodes(model):
        for attr in ("texture", "lightmap", "bump_map", "txi_bumpmaptexture", "txi_envmaptexture"):
            value = str(getattr(node, attr, "") or "").strip().lower()
            if value and value not in {"null", "none"} and value not in seen:
                names.append(value)
                seen.add(value)
        for value in getattr(node, "texture_names", []) or []:
            text = str(value or "").strip().lower()
            if text and text not in {"null", "none"} and text not in seen:
                names.append(text)
                seen.add(text)
    return names


def _get_game_library():
    """Return a cached GhostRigger GameLibrary for texture archive lookup."""
    global _game_library
    if _game_library is not None:
        return _game_library
    _load_local_game_paths()
    from src.resources.game_library import GameLibrary

    lib = GameLibrary()
    k1 = os.environ.get("K1_PATH", "")
    k2 = os.environ.get("K2_PATH", "")
    if k1:
        lib.set_k1_dir(k1)
    if k2:
        lib.set_k2_dir(k2)
    lib.scan(auto_detect=False)
    _game_library = lib
    return _game_library


def validate_textures(game: str, resref: str) -> dict[str, Any]:
    """Validate that GhostRigger-referenced textures are present and decodable."""
    from src.core.game.kotor_loader import load_tpc_as_pil

    model = _load_ghostrigger_model(game, resref)
    _, _, _ = _resource_pair(game, resref)
    registry = get_default_registry()
    game_obj = registry.resolve(game)
    installation = registry.load(game_obj) if game_obj is not None else None
    textures: dict[str, dict[str, Any]] = {}

    for name in _texture_names(model):
        resource = None
        raw = None
        if installation is not None:
            resource = installation.get_resource(name, "tpc") or installation.get_resource(name, "tga")
        if resource is not None:
            raw = resource.data
        else:
            try:
                raw = _get_game_library().get_texture_data(
                    name,
                    "K2" if str(game).lower() in {"k2", "tsl", "kotor2"} else "K1",
                )
            except Exception:
                raw = None
        loadable = False
        error = ""
        if raw is not None:
            try:
                image = load_tpc_as_pil(raw)
                loadable = image is not None
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        textures[name] = {
            "found": raw is not None,
            "loadable": loadable,
            "size": len(raw) if raw is not None else 0,
            "error": error,
        }

    return {
        "game": game,
        "resref": resref,
        "texture_count": len(textures),
        "all_found": all(item["found"] for item in textures.values()),
        "all_loadable": all(item["loadable"] for item in textures.values()),
        "textures": textures,
    }


def _skin_weight_summary(skin_data: Iterable[Any], bone_count: int) -> dict[str, Any]:
    out_of_range = 0
    sums: list[float] = []
    max_influences = 0
    for vertex in skin_data:
        influences = list(getattr(vertex, "influences", []) or [])
        max_influences = max(max_influences, len(influences))
        total = 0.0
        for influence in influences:
            index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0) or 0.0)
            total += weight
            if index < 0 or index >= bone_count:
                out_of_range += 1
        if influences:
            sums.append(total)
    return {
        "out_of_range_indices": out_of_range,
        "weight_sum_range": [min(sums), max(sums)] if sums else [0.0, 0.0],
        "max_influences": max_influences,
    }


def inspect_skinning(game: str, resref: str) -> dict[str, Any]:
    """Return skin-weight diagnostics for GhostRigger's imported model."""
    model = _load_ghostrigger_model(game, resref)
    skin_nodes: list[dict[str, Any]] = []
    for node in _all_nodes(model):
        if not bool(getattr(node, "is_skin", False)):
            continue
        bone_map = list(getattr(node, "bone_map", []) or [])
        skin_data = list(getattr(node, "skin_data", []) or [])
        summary = _skin_weight_summary(skin_data, len(bone_map))
        skin_nodes.append(
            {
                "name": str(getattr(node, "name", "")),
                "vertex_count": len(getattr(node, "vertices", []) or []),
                "bone_count": len(bone_map),
                "bone_map": [str(item) for item in bone_map],
                **summary,
            },
        )
    return {"game": game, "resref": resref, "skin_nodes": skin_nodes}


def get_tools() -> list[dict[str, Any]]:
    from kotormcp.tools.ghostrigger import get_tools as _get_tools

    return _get_tools()


def __getattr__(name: str) -> Any:
    from kotormcp.tools import ghostrigger

    if hasattr(ghostrigger, name):
        return getattr(ghostrigger, name)
    raise AttributeError(name)
