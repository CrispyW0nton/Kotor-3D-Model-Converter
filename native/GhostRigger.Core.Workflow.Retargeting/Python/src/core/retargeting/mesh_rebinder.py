"""Skeleton-transplant helpers for retargeting skinned meshes.

This module performs the mesh side of GhostRigger's Day 3B retargeting path:
given a KotOR skin mesh in canonical world space, remap its vertex influences
onto a target skeleton and transform bind-pose vertices through the source and
target bind matrices.  Animation baking stays in :mod:`baker`; this file is
pure mesh/bind-pose math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Mapping
import json

import numpy as np

from .coordinate_normalizer import BindPoseRegistry
from .skeleton_aligner import (
    AlignedSkeleton,
    AlignmentOptions,
    aligned_skeleton_to_registry,
    align_target_skeleton_to_source,
    alignment_summary,
)


class RebindError(RuntimeError):
    """Base exception for mesh rebinding failures."""


class BindPoseDegenerate(RebindError):
    """Raised when a bind matrix cannot be safely inverted."""


@dataclass
class SourceMesh:
    name: str
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray
    bone_indices: np.ndarray
    bone_weights: np.ndarray
    faces: np.ndarray
    source_bind_world: Dict[str, np.ndarray]
    bbox_diagonal: float
    source_bone_names: list[str] = field(default_factory=list)
    source_bone_index: dict[str, int] = field(default_factory=dict)
    local_bone_map: list[str] = field(default_factory=list)
    local_to_global_bone_indices: list[int] = field(default_factory=list)
    mesh_node_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReboundMesh:
    name: str
    positions: np.ndarray
    normals: np.ndarray
    uvs: np.ndarray
    bone_indices: np.ndarray
    bone_weights: np.ndarray
    faces: np.ndarray
    target_skeleton_id: str
    transplant_metadata: Dict[str, Any]
    dense_bone_weights: np.ndarray | None = None
    aligned_skeleton: AlignedSkeleton | None = None


@dataclass
class RebindOptions:
    enable_skeleton_prealignment: bool = True
    alignment_options: AlignmentOptions = field(default_factory=AlignmentOptions)
    enable_twist_redistribution: bool = True
    twist_max_contribution: float = 0.5
    twist_curve: Literal["linear", "smoothstep", "ease_out"] = "smoothstep"
    twist_segment_map_path: Path = field(
        default_factory=lambda: Path("knowledge_base/retargeting/twist_segment_maps/ue5_manny.json")
    )
    unmapped_bone_strategy: Literal["nearest_ancestor", "zero_weight", "fail"] = "nearest_ancestor"
    weight_normalization_epsilon: float = 1e-6
    validate_determinants: bool = True
    log_redistribution_stats: bool = True


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def _det3(matrix: np.ndarray) -> float:
    return float(np.linalg.det(np.asarray(matrix, dtype=np.float64)[:3, :3]))


def _target_export_bones(registry: BindPoseRegistry) -> list[str]:
    """Return target bones in FBX/export index space.

    ``unreal_skeleton_model`` wraps the real 89 Quinn bones under a model root
    named ``SKM_Quinn_Simple``.  The FBX skin cluster should not count that
    wrapper as a deform bone, so indices are built from all registry bones except
    the wrapper node.
    """

    return [
        name
        for name in registry.bone_names
        if _key(name) != "skm_quinn_simple"
    ]


def _target_index_map(registry: BindPoseRegistry) -> dict[str, int]:
    return {_key(name): idx for idx, name in enumerate(_target_export_bones(registry))}


def _nearest_mapped_ancestor(
    source_key: str,
    *,
    source_registry: BindPoseRegistry,
    target_registry: BindPoseRegistry,
    bone_map: Mapping[str, str],
    strategy: str,
) -> tuple[str, str]:
    source_key = _key(source_key)
    if source_key in bone_map:
        return _key(bone_map[source_key]), "direct"

    # Skin palettes sometimes include the model root.  That is not a semantic
    # limb bone, but mapping it to Quinn's root preserves the influence without
    # inventing motion.
    if source_key == _key(source_registry.skeleton_id) and target_registry.has_bone("root"):
        return "root", "root_fallback"

    parent = source_registry.parent_key(source_key)
    while parent:
        if parent in bone_map:
            return _key(bone_map[parent]), f"ancestor:{parent}"
        parent = source_registry.parent_key(parent)

    if strategy == "fail":
        raise RebindError(f"No target mapping or mapped ancestor for source bone '{source_key}'")
    if strategy == "zero_weight":
        return "", "zero_weight"
    if target_registry.has_bone("root"):
        return "root", "root_fallback"
    first = _key(_target_export_bones(target_registry)[0])
    return first, "first_bone_fallback"


def _validate_bind_matrices(
    registry: BindPoseRegistry,
    *,
    names: list[str],
    label: str,
    epsilon: float = 1e-6,
) -> None:
    for name in names:
        key = _key(name)
        if key not in registry.bind_world:
            raise RebindError(f"{label} bind matrix missing for '{key}'")
        det = abs(_det3(registry.bind_world[key]))
        if det <= epsilon:
            raise BindPoseDegenerate(f"{label} bind matrix for '{key}' is degenerate (det={det:g})")


def build_index_remap_table(
    mesh: SourceMesh,
    source_registry: BindPoseRegistry,
    target_registry: BindPoseRegistry,
    bone_map: Mapping[str, str],
    options: RebindOptions,
) -> tuple[dict[int, int], dict[int, str], dict[str, Any]]:
    target_indices = _target_index_map(target_registry)
    remap: dict[int, int] = {}
    target_by_source: dict[int, str] = {}
    direct = 0
    fallback_counts: dict[str, int] = {}
    fallback_sources: dict[str, int] = {}

    used_source_indices = sorted({
        int(idx)
        for idx in np.asarray(mesh.bone_indices).reshape(-1)
        if int(idx) >= 0
    })
    for source_idx in used_source_indices:
        if source_idx >= len(mesh.source_bone_names):
            raise RebindError(f"Source vertex references bone index {source_idx}, but only {len(mesh.source_bone_names)} bones exist")
        source_name = _key(mesh.source_bone_names[source_idx])
        target_name, reason = _nearest_mapped_ancestor(
            source_name,
            source_registry=source_registry,
            target_registry=target_registry,
            bone_map=bone_map,
            strategy=options.unmapped_bone_strategy,
        )
        if not target_name:
            remap[source_idx] = -1
            target_by_source[source_idx] = ""
            fallback_counts[reason] = fallback_counts.get(reason, 0) + 1
            fallback_sources[source_name] = fallback_sources.get(source_name, 0) + 1
            continue
        if target_name not in target_indices:
            raise RebindError(f"Mapped target bone '{target_name}' is not part of export skeleton")
        remap[source_idx] = target_indices[target_name]
        target_by_source[source_idx] = target_name
        if reason == "direct":
            direct += 1
        else:
            fallback_counts[reason] = fallback_counts.get(reason, 0) + 1
            fallback_sources[source_name] = fallback_sources.get(source_name, 0) + 1

    metadata = {
        "used_source_bone_count": len(used_source_indices),
        "direct_source_bone_count": direct,
        "fallback_source_bone_count": len(used_source_indices) - direct,
        "fallback_reason_counts": fallback_counts,
        "fallback_source_bone_counts": fallback_sources,
        "source_to_target": {
            mesh.source_bone_names[idx]: target_by_source.get(idx, "")
            for idx in used_source_indices
        },
    }
    return remap, target_by_source, metadata


def _curve_value(t: np.ndarray | float, curve: str) -> np.ndarray | float:
    if curve == "smoothstep":
        return t * t * (3.0 - 2.0 * t)
    if curve == "ease_out":
        return 1.0 - (1.0 - t) ** 2
    return t


def redistribute_to_twist_bone(
    vertex_pos: np.ndarray,
    parent_bone_world: np.ndarray,
    child_bone_world: np.ndarray,
    *,
    twist_position: float = 0.5,
    twist_curve: str = "smoothstep",
    twist_max_contribution: float = 0.5,
) -> tuple[float, float]:
    """Return primary/twist weight multipliers for one vertex."""

    del twist_position  # The actual point is stored in the skeleton; t is geometric.
    axis = np.asarray(child_bone_world, dtype=np.float64) - np.asarray(parent_bone_world, dtype=np.float64)
    axis_len_sq = float(np.dot(axis, axis))
    if axis_len_sq < 1e-8:
        return (1.0, 0.0)
    t_raw = float(np.dot(np.asarray(vertex_pos, dtype=np.float64) - parent_bone_world, axis) / axis_len_sq)
    t = max(0.0, min(1.0, t_raw))
    t = float(_curve_value(t, twist_curve))
    w_twist = t * float(twist_max_contribution)
    return (1.0 - w_twist, w_twist)


def _load_twist_segments(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return dict(data.get("twist_segments", {}) or {})


def _apply_twist_redistribution(
    dense_weights: np.ndarray,
    positions: np.ndarray,
    target_registry: BindPoseRegistry,
    target_indices: dict[str, int],
    options: RebindOptions,
) -> dict[str, Any]:
    if not options.enable_twist_redistribution:
        return {"enabled": False, "twist_bones": {}}

    segments = _load_twist_segments(options.twist_segment_map_path)
    stats: dict[str, Any] = {}
    for twist_name, spec in segments.items():
        twist_key = _key(twist_name)
        parent_key = _key(spec.get("parent_bone", ""))
        child_key = _key(spec.get("child_bone", ""))
        if twist_key not in target_indices or parent_key not in target_indices:
            continue
        if not (target_registry.has_bone(parent_key) and target_registry.has_bone(child_key)):
            continue

        primary_idx = target_indices[parent_key]
        twist_idx = target_indices[twist_key]
        primary_weights = dense_weights[:, primary_idx].copy()
        affected = primary_weights > 1e-12
        if not np.any(affected):
            stats[twist_key] = {"vertices_affected": 0}
            continue

        parent_pos = target_registry.world_position(parent_key)
        child_pos = target_registry.world_position(child_key)
        axis = child_pos - parent_pos
        axis_len_sq = float(np.dot(axis, axis))
        if axis_len_sq <= 1e-8:
            stats[twist_key] = {"vertices_affected": 0, "skipped": "degenerate_segment"}
            continue

        t_raw = ((positions - parent_pos) @ axis) / axis_len_sq
        t = np.clip(t_raw, 0.0, 1.0)
        t_curve = np.asarray(_curve_value(t, options.twist_curve), dtype=np.float64)
        transfer = primary_weights * t_curve * float(options.twist_max_contribution)
        dense_weights[:, primary_idx] -= transfer
        dense_weights[:, twist_idx] += transfer

        moved = transfer[affected]
        stats[twist_key] = {
            "vertices_affected": int(np.count_nonzero(affected)),
            "mean_weight_transferred": float(np.mean(moved)) if moved.size else 0.0,
            "max_weight_transferred": float(np.max(moved)) if moved.size else 0.0,
            "min_t": float(np.min(t[affected])) if np.any(affected) else 0.0,
            "max_t": float(np.max(t[affected])) if np.any(affected) else 0.0,
            "twist_position_config": float(spec.get("twist_position", 0.5)),
        }

    return {
        "enabled": True,
        "map_path": str(options.twist_segment_map_path),
        "twist_bones": stats,
    }


def _compress_weights(dense_weights: np.ndarray, epsilon: float) -> tuple[np.ndarray, np.ndarray]:
    vertex_count, bone_count = dense_weights.shape
    if bone_count == 0:
        raise RebindError("Target skeleton has zero export bones")

    indices = np.zeros((vertex_count, 4), dtype=np.uint16)
    weights = np.zeros((vertex_count, 4), dtype=np.float32)
    for vi in range(vertex_count):
        row = dense_weights[vi]
        if float(np.sum(row)) <= epsilon:
            indices[vi, 0] = 0
            weights[vi, 0] = 1.0
            continue
        order = np.argsort(-row)[:4]
        selected = np.maximum(row[order], 0.0)
        total = float(np.sum(selected))
        if total <= epsilon:
            indices[vi, 0] = 0
            weights[vi, 0] = 1.0
            continue
        indices[vi, :] = order.astype(np.uint16)
        weights[vi, :] = (selected / total).astype(np.float32)
    return indices, weights


def rebind_mesh_to_target_skeleton(
    mesh: SourceMesh,
    source_skeleton_id: str,
    target_skeleton_id: str,
    bone_map: Dict[str, str],
    registry: BindPoseRegistry,
    normalizer: Any,
    options: RebindOptions = RebindOptions(),
) -> ReboundMesh:
    """Rebind a canonical-world KotOR skin mesh to a target skeleton."""

    del normalizer  # The mesh loader and registries own all space normalization.
    source_registry = getattr(mesh, "source_registry", None) or mesh.metadata.get("source_registry")
    if source_registry is None:
        raise RebindError("SourceMesh must carry source_registry in metadata")
    if not isinstance(source_registry, BindPoseRegistry):
        raise RebindError("SourceMesh metadata['source_registry'] must be a BindPoseRegistry")

    positions = np.asarray(mesh.positions, dtype=np.float64)
    normals = np.asarray(mesh.normals, dtype=np.float64)
    weights = np.asarray(mesh.bone_weights, dtype=np.float64)
    source_indices = np.asarray(mesh.bone_indices, dtype=np.int64)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise RebindError("mesh.positions must have shape [V, 3]")
    if weights.shape != source_indices.shape or weights.shape[1] != 4:
        raise RebindError("bone_indices and bone_weights must both have shape [V, 4]")
    if positions.shape[0] != weights.shape[0]:
        raise RebindError("vertex and skin arrays have different lengths")

    if options.validate_determinants:
        _validate_bind_matrices(registry, names=_target_export_bones(registry), label="raw target")

    aligned_skeleton: AlignedSkeleton | None = None
    effective_target_registry = registry
    rebound_target_id = target_skeleton_id
    if options.enable_skeleton_prealignment:
        aligned_skeleton = align_target_skeleton_to_source(
            source_skeleton_id,
            target_skeleton_id,
            bone_map,
            registry,
            options.alignment_options,
            source_registry=source_registry,
            target_registry=registry,
        )
        effective_target_registry = aligned_skeleton_to_registry(aligned_skeleton)
        rebound_target_id = aligned_skeleton.skeleton_id

    target_bones = _target_export_bones(effective_target_registry)
    target_indices = _target_index_map(effective_target_registry)
    if options.validate_determinants:
        _validate_bind_matrices(effective_target_registry, names=target_bones, label="target")
        _validate_bind_matrices(source_registry, names=source_registry.bone_names, label="source")

    clean_map = {_key(src): _key(dst) for src, dst in bone_map.items() if _key(src) and _key(dst)}
    remap, target_by_source, remap_metadata = build_index_remap_table(
        mesh,
        source_registry,
        effective_target_registry,
        clean_map,
        options,
    )

    transplant_mats: dict[int, np.ndarray] = {}
    normal_mats: dict[int, np.ndarray] = {}
    for source_idx, target_idx in remap.items():
        if target_idx < 0:
            continue
        source_name = _key(mesh.source_bone_names[source_idx])
        target_name = target_by_source[source_idx]
        source_bind = source_registry.world_matrix(source_name)
        target_bind = effective_target_registry.world_matrix(target_name)
        matrix = target_bind @ np.linalg.inv(source_bind)
        if options.validate_determinants and abs(_det3(matrix)) <= 1e-6:
            raise BindPoseDegenerate(f"Transplant matrix for '{source_name}' -> '{target_name}' is degenerate")
        transplant_mats[source_idx] = matrix
        normal_mats[source_idx] = np.linalg.inv(matrix[:3, :3]).T

    out_positions = np.zeros_like(positions)
    out_normals = np.zeros_like(normals)
    dense_weights = np.zeros((positions.shape[0], len(target_bones)), dtype=np.float64)
    for slot in range(4):
        slot_indices = source_indices[:, slot]
        slot_weights = weights[:, slot]
        for source_idx in sorted(set(int(i) for i in slot_indices if int(i) >= 0)):
            mask = (slot_indices == source_idx) & (slot_weights > options.weight_normalization_epsilon)
            if not np.any(mask):
                continue
            target_idx = remap.get(source_idx, -1)
            if target_idx < 0:
                continue
            matrix = transplant_mats[source_idx]
            normal_matrix = normal_mats[source_idx]
            hom = np.concatenate([positions[mask], np.ones((int(np.count_nonzero(mask)), 1), dtype=np.float64)], axis=1)
            transformed = (matrix @ hom.T).T[:, :3]
            weighted = transformed * slot_weights[mask, None]
            out_positions[mask] += weighted

            transformed_normals = (normal_matrix @ normals[mask].T).T
            out_normals[mask] += transformed_normals * slot_weights[mask, None]
            dense_weights[mask, target_idx] += slot_weights[mask]

    row_sums = dense_weights.sum(axis=1)
    empty = row_sums <= options.weight_normalization_epsilon
    if np.any(empty):
        out_positions[empty] = positions[empty]
        out_normals[empty] = normals[empty]
        dense_weights[empty, 0] = 1.0
        row_sums = dense_weights.sum(axis=1)

    if not np.all(np.isfinite(out_positions)):
        raise RebindError("Rebound vertex positions contain NaN/inf")

    normal_lengths = np.linalg.norm(out_normals, axis=1)
    zero_normals = normal_lengths <= 1e-12
    if np.any(zero_normals):
        out_normals[zero_normals] = normals[zero_normals]
        normal_lengths = np.linalg.norm(out_normals, axis=1)
    normal_lengths = np.where(normal_lengths <= 1e-12, 1.0, normal_lengths)
    out_normals = out_normals / normal_lengths[:, None]

    twist_metadata = _apply_twist_redistribution(
        dense_weights,
        out_positions,
        effective_target_registry,
        target_indices,
        options,
    )
    dense_sums = dense_weights.sum(axis=1)
    drift = float(np.max(np.abs(dense_sums - 1.0))) if dense_sums.size else 0.0
    if drift > options.weight_normalization_epsilon:
        dense_weights = dense_weights / np.where(dense_sums[:, None] <= 1e-12, 1.0, dense_sums[:, None])
        dense_sums = dense_weights.sum(axis=1)
        drift = float(np.max(np.abs(dense_sums - 1.0))) if dense_sums.size else 0.0
    if drift > options.weight_normalization_epsilon:
        raise RebindError(f"Weight normalization drift {drift:g} exceeds epsilon {options.weight_normalization_epsilon:g}")

    out_indices, out_weights = _compress_weights(dense_weights, options.weight_normalization_epsilon)
    final_drift = float(np.max(np.abs(out_weights.astype(np.float64).sum(axis=1) - 1.0))) if out_weights.size else 0.0
    if final_drift > options.weight_normalization_epsilon:
        raise RebindError(f"Packed weight drift {final_drift:g} exceeds epsilon {options.weight_normalization_epsilon:g}")
    if int(out_indices.max(initial=0)) >= len(target_bones):
        raise RebindError("Packed bone index exceeds target bone count")
    if not np.all(np.isfinite(out_normals)):
        raise RebindError("Rebound normals contain NaN/inf")
    normal_unit_drift = float(np.max(np.abs(np.linalg.norm(out_normals, axis=1) - 1.0))) if out_normals.size else 0.0
    if normal_unit_drift > 1e-5:
        raise RebindError(f"Normal unit-length drift {normal_unit_drift:g} exceeds 1e-5")

    metadata = {
        "source_skeleton_id": source_skeleton_id,
        "target_skeleton_id": rebound_target_id,
        "target_bone_count": len(target_bones),
        "target_bone_names": target_bones,
        "skeleton_prealignment": {
            "enabled": bool(options.enable_skeleton_prealignment),
            "summary": alignment_summary(aligned_skeleton) if aligned_skeleton is not None else None,
        },
        "index_remap": remap_metadata,
        "twist_redistribution": twist_metadata,
        "weight_conservation_max_drift": final_drift,
        "normal_unit_max_drift": normal_unit_drift,
        "options": {
            "enable_twist_redistribution": options.enable_twist_redistribution,
            "enable_skeleton_prealignment": options.enable_skeleton_prealignment,
            "twist_max_contribution": options.twist_max_contribution,
            "twist_curve": options.twist_curve,
            "twist_segment_map_path": str(options.twist_segment_map_path),
            "unmapped_bone_strategy": options.unmapped_bone_strategy,
        },
    }
    return ReboundMesh(
        name=mesh.name,
        positions=out_positions,
        normals=out_normals,
        uvs=np.asarray(mesh.uvs, dtype=np.float64),
        bone_indices=out_indices,
        bone_weights=out_weights,
        faces=np.asarray(mesh.faces, dtype=np.int64),
        target_skeleton_id=rebound_target_id,
        transplant_metadata=metadata,
        dense_bone_weights=dense_weights,
        aligned_skeleton=aligned_skeleton,
    )
