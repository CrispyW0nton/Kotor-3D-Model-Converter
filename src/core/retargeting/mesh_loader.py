"""Skinned KotOR mesh extraction for retargeting.

The loader resolves KotOR's skin-local palette indices into the global
model/skeleton index space before the mesh reaches ``mesh_rebinder``.  This is
the important MDL-specific step: MDX vertex indices point at the skin node's
compact palette, not directly at the model DFS node list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from src.core.game.kotor_loader import load_model_from_file
from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode

from .coordinate_normalizer import (
    CoordinateNormalizer,
    BindPoseRegistry,
    compose_matrix,
    xyzw_to_wxyz,
)
from .mesh_rebinder import SourceMesh, RebindError


def _game_version_from_path(path: Path) -> GameVersion:
    parts = {part.lower() for part in path.parts}
    return GameVersion.K2 if "k2" in parts or "tsl" in parts else GameVersion.K1


def _load_model_pair(mdl_path: Path) -> KotorModel:
    mdx_path = mdl_path.with_suffix(".mdx")
    return load_model_from_file(
        str(mdl_path),
        str(mdx_path) if mdx_path.exists() else "",
        _game_version_from_path(mdl_path),
    )


def _node_world_matrix(node: ModelNode) -> np.ndarray:
    local = compose_matrix(
        getattr(node, "position", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0),
        xyzw_to_wxyz(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0)) or (0.0, 0.0, 0.0, 1.0)),
    )
    parent = getattr(node, "parent", None)
    if parent is None:
        return local
    return _node_world_matrix(parent) @ local


def _find_skin_node(model: KotorModel, mesh_node_name: Optional[str]) -> ModelNode:
    target = str(mesh_node_name or "").strip().lower()
    candidates = [
        node for node in model.all_nodes()
        if bool(getattr(node, "is_skin", False))
        and len(getattr(node, "vertices", []) or []) > 0
        and len(getattr(node, "skin_data", []) or []) > 0
    ]
    if target:
        for node in candidates:
            if str(getattr(node, "name", "") or "").lower() == target:
                return node
        raise RebindError(f"Skinned mesh node '{mesh_node_name}' not found")
    if not candidates:
        raise RebindError(f"Model '{getattr(model, 'name', '')}' has no skinned mesh nodes")
    return candidates[0]


def _model_bbox_diagonal(model: KotorModel, fallback_positions: np.ndarray) -> float:
    try:
        bb_min = np.asarray(getattr(model, "bb_min", None), dtype=np.float64)
        bb_max = np.asarray(getattr(model, "bb_max", None), dtype=np.float64)
        if bb_min.shape == (3,) and bb_max.shape == (3,):
            diag = float(np.linalg.norm(bb_max - bb_min))
            if diag > 1e-12:
                return diag
    except Exception:
        pass
    if fallback_positions.size == 0:
        return 1.0
    return float(np.linalg.norm(np.max(fallback_positions, axis=0) - np.min(fallback_positions, axis=0))) or 1.0


def _normalize_normals(normals: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if normals.size == 0:
        return np.zeros((0, 3), dtype=np.float64)
    normal_matrix = np.linalg.inv(matrix[:3, :3]).T
    out = (normal_matrix @ normals.T).T
    lengths = np.linalg.norm(out, axis=1)
    lengths = np.where(lengths <= 1e-12, 1.0, lengths)
    return out / lengths[:, None]


def _skin_arrays_from_node(
    node: ModelNode,
    registry: BindPoseRegistry,
) -> tuple[np.ndarray, np.ndarray, list[str], list[int]]:
    vertex_count = len(getattr(node, "vertices", []) or [])
    indices = np.full((vertex_count, 4), -1, dtype=np.int32)
    weights = np.zeros((vertex_count, 4), dtype=np.float32)

    local_bone_map = [str(name or "") for name in (getattr(node, "bone_map", []) or [])]
    local_to_global = [registry.bone_index.get(name.lower(), -1) for name in local_bone_map]

    for vi, skin_data in enumerate(getattr(node, "skin_data", []) or []):
        slot = 0
        for influence in getattr(skin_data, "influences", []) or []:
            if slot >= 4:
                break
            local_idx = int(getattr(influence, "bone_index", -1))
            if local_idx < 0 or local_idx >= len(local_to_global):
                continue
            global_idx = local_to_global[local_idx]
            if global_idx < 0:
                continue
            weight = float(getattr(influence, "weight", 0.0) or 0.0)
            if weight <= 1e-8 or not np.isfinite(weight):
                continue
            indices[vi, slot] = global_idx
            weights[vi, slot] = weight
            slot += 1
        total = float(np.sum(weights[vi]))
        if total > 1e-8:
            weights[vi] /= total

    empty = np.sum(weights, axis=1) <= 1e-8
    if np.any(empty):
        root_idx = 0
        indices[empty, 0] = root_idx
        weights[empty, 0] = 1.0

    return indices, weights, local_bone_map, local_to_global


def load_kotor_skinned_mesh(
    mdl_path: Path,
    mesh_node_name: Optional[str] = None,
) -> SourceMesh:
    """Extract one skinned KotOR mesh from an MDL/MDX pair.

    The returned vertex positions are canonical world-space positions.  Skin
    indices are global non-skin skeleton indices, not the compact local palette
    slots stored in each MDL skin header.
    """

    mdl_path = Path(mdl_path)
    model = _load_model_pair(mdl_path)
    normalizer = CoordinateNormalizer()
    registry = normalizer.normalize_aurora_bind(model, f"kotor_{mdl_path.stem}")
    node = _find_skin_node(model, mesh_node_name)
    node_world = _node_world_matrix(node)

    local_positions = np.asarray(getattr(node, "vertices", []) or [], dtype=np.float64)
    positions = normalizer.normalize_vertex_positions(local_positions, node_world)
    normals = _normalize_normals(np.asarray(getattr(node, "normals", []) or [], dtype=np.float64), node_world)
    if normals.shape[0] != positions.shape[0]:
        normals = np.zeros_like(positions)
        normals[:, 2] = 1.0

    uvs = np.asarray(getattr(node, "uvs", []) or [], dtype=np.float64)
    if uvs.shape[0] != positions.shape[0]:
        uvs = np.zeros((positions.shape[0], 2), dtype=np.float64)
    faces = np.asarray(getattr(node, "faces", []) or [], dtype=np.int64)
    bone_indices, bone_weights, local_bone_map, local_to_global = _skin_arrays_from_node(node, registry)
    weight_sums = np.sum(bone_weights.astype(np.float64), axis=1)
    if not np.allclose(weight_sums, 1.0, atol=1e-5):
        max_drift = float(np.max(np.abs(weight_sums - 1.0))) if weight_sums.size else 0.0
        raise RebindError(f"Loaded skin weights are not normalized (max drift {max_drift:g})")

    mesh = SourceMesh(
        name=str(getattr(model, "name", "") or mdl_path.stem),
        positions=positions,
        normals=normals,
        uvs=uvs,
        bone_indices=bone_indices,
        bone_weights=bone_weights,
        faces=faces,
        source_bind_world={name.lower(): matrix for name, matrix in registry.bind_world.items()},
        bbox_diagonal=_model_bbox_diagonal(model, positions),
        source_bone_names=list(registry.bone_names),
        source_bone_index=dict(registry.bone_index),
        local_bone_map=local_bone_map,
        local_to_global_bone_indices=local_to_global,
        mesh_node_name=str(getattr(node, "name", "") or ""),
        metadata={
            "source_registry": registry,
            "model_name": getattr(model, "name", ""),
            "supermodel": getattr(model, "supermodel", ""),
            "mdl_path": str(mdl_path),
            "mesh_node_name": getattr(node, "name", ""),
            "local_palette_to_global_indices": local_to_global,
            "local_palette": local_bone_map,
            "qbone_count": len(getattr(node, "qbone_list", []) or []),
            "tbone_count": len(getattr(node, "tbone_list", []) or []),
        },
    )
    setattr(mesh, "source_registry", registry)
    return mesh
