"""Skeleton pre-alignment for cross-skeleton mesh rebinding.

The raw transplant equation moves vertices from the source bind skeleton to the
target bind skeleton.  That is correct math, but it changes the mesh silhouette
when the target skeleton has different proportions.  This module builds a
target-named skeleton whose mapped bones use the source bind pose, giving the
mesh rebinder a Quinn hierarchy with Aurora proportions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Optional
import json

import numpy as np

from .coordinate_normalizer import BindPoseRegistry


class AlignmentError(RuntimeError):
    """Base exception for skeleton alignment failures."""


class AlignmentInputError(AlignmentError):
    """Raised when the alignment inputs are inconsistent."""


class AlignmentCycleError(AlignmentError):
    """Raised when a target hierarchy has a parent cycle."""


class AlignmentDriftExceeded(AlignmentError):
    """Raised when a mapped target bone fails to match its source bone."""


class AlignmentProducedDegenerateBind(AlignmentError):
    """Raised when alignment creates a degenerate bind matrix."""


@dataclass
class AlignmentOptions:
    scale_strategy: Literal["pelvis_to_head", "bounding_box", "explicit"] = "pelvis_to_head"
    explicit_scale: Optional[float] = None
    rotation_strategy: Literal["copy_source"] = "copy_source"
    twist_alignment: Literal["interpolate", "preserve_target"] = "interpolate"
    twist_segment_map_path: Path = field(
        default_factory=lambda: Path("knowledge_base/retargeting/twist_segment_maps/ue5_manny.json")
    )
    max_mapped_bone_drift: float = 0.01
    require_non_degenerate_bind: bool = True
    log_per_bone_deltas: bool = True
    capture_pre_alignment_snapshot: bool = True


@dataclass
class BoneAlignmentDelta:
    bone_name: str
    source_mapped_from: Optional[str]
    raw_target_world_pos: np.ndarray
    aligned_target_world_pos: np.ndarray
    source_world_pos: Optional[np.ndarray]
    position_delta_magnitude: float
    handling_strategy: Literal["direct_copy", "twist_interpolated", "ancestor_fallback", "root_anchor"]


@dataclass
class AlignmentMetadata:
    global_scale_factor: float
    root_translation: np.ndarray
    per_bone_deltas: Dict[str, BoneAlignmentDelta]
    unmapped_bones_handled: list[str]
    twist_bones_interpolated: list[str]
    validation_max_drift: float
    raw_target_snapshot: Optional[Dict[str, np.ndarray]] = None


@dataclass
class AlignedSkeleton:
    skeleton_id: str
    base_target_id: str
    source_id: str
    bone_names: list[str]
    bone_parents: Dict[str, Optional[str]]
    bind_world: Dict[str, np.ndarray]
    bind_local: Dict[str, np.ndarray]
    alignment_metadata: AlignmentMetadata


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def extract_position(matrix: np.ndarray) -> np.ndarray:
    return np.asarray(matrix, dtype=np.float64)[:3, 3].copy()


def extract_rotation(matrix: np.ndarray) -> np.ndarray:
    return np.asarray(matrix, dtype=np.float64)[:3, :3].copy()


def compose_matrix(position: np.ndarray, rotation_3x3: np.ndarray) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = np.asarray(rotation_3x3, dtype=np.float64)
    out[:3, 3] = np.asarray(position, dtype=np.float64)[:3]
    return out


def lerp_position(matrix_a: np.ndarray, matrix_b: np.ndarray, t: float) -> np.ndarray:
    return extract_position(matrix_a) * (1.0 - float(t)) + extract_position(matrix_b) * float(t)


def topological_sort(hierarchy: Mapping[str, Optional[str]]) -> list[str]:
    """Return root-first hierarchy order and raise on cycles."""

    keys = list(hierarchy)
    visiting: set[str] = set()
    visited: set[str] = set()
    out: list[str] = []

    def visit(node: str) -> None:
        key = _key(node)
        if key in visited:
            return
        if key in visiting:
            raise AlignmentCycleError(f"Cycle detected at '{key}'")
        visiting.add(key)
        parent = hierarchy.get(key)
        if parent:
            parent_key = _key(parent)
            if parent_key in hierarchy:
                visit(parent_key)
        visiting.remove(key)
        visited.add(key)
        out.append(key)

    for key in keys:
        visit(key)
    return out


def compute_local_from_world(
    world: Mapping[str, np.ndarray],
    hierarchy: Mapping[str, Optional[str]],
) -> Dict[str, np.ndarray]:
    local: Dict[str, np.ndarray] = {}
    for name in topological_sort(hierarchy):
        parent = hierarchy.get(name)
        if parent and parent in world:
            local[name] = np.linalg.inv(world[parent]) @ world[name]
        else:
            local[name] = np.asarray(world[name], dtype=np.float64).copy()
    return local


def _height_candidates(bind: Mapping[str, np.ndarray], candidates: list[str]) -> tuple[str, np.ndarray] | None:
    for name in candidates:
        key = _key(name)
        if key in bind:
            return key, extract_position(bind[key])
    return None


def compute_global_scale(
    source_bind: Mapping[str, np.ndarray],
    target_bind: Mapping[str, np.ndarray],
    bone_map: Mapping[str, str],
    strategy: str,
    explicit: Optional[float],
) -> float:
    if strategy == "explicit":
        return float(explicit if explicit is not None else 1.0)
    if strategy == "bounding_box":
        src = np.asarray([extract_position(m) for m in source_bind.values()], dtype=np.float64)
        tgt = np.asarray([extract_position(m) for m in target_bind.values()], dtype=np.float64)
        src_diag = float(np.linalg.norm(src.max(axis=0) - src.min(axis=0))) if src.size else 1.0
        tgt_diag = float(np.linalg.norm(tgt.max(axis=0) - tgt.min(axis=0))) if tgt.size else 1.0
        return 1.0 if tgt_diag <= 1e-12 else src_diag / tgt_diag

    # pelvis_to_head: use semantic anchors, not only bone_map, because pmbam is
    # a body model and uses headhook rather than a mapped head bone.
    source_pelvis = _height_candidates(source_bind, ["pelvis_g", "pelvis"])
    source_head = _height_candidates(source_bind, ["head_g", "headhook", "freelookhook", "camerahook", "torsoupr_g"])
    target_pelvis = _height_candidates(target_bind, ["pelvis"])
    target_head = _height_candidates(target_bind, ["head", "neck_02", "spine_05"])
    if source_pelvis and source_head and target_pelvis and target_head:
        source_dist = float(np.linalg.norm(source_head[1] - source_pelvis[1]))
        target_dist = float(np.linalg.norm(target_head[1] - target_pelvis[1]))
        if source_dist > 1e-12 and target_dist > 1e-12:
            return source_dist / target_dist

    # Last fallback: mapped-bone bounding box.
    src_pts = []
    tgt_pts = []
    for src, tgt in bone_map.items():
        src_key = _key(src)
        tgt_key = _key(tgt)
        if src_key in source_bind and tgt_key in target_bind:
            src_pts.append(extract_position(source_bind[src_key]))
            tgt_pts.append(extract_position(target_bind[tgt_key]))
    if len(src_pts) >= 2 and len(tgt_pts) >= 2:
        src_arr = np.asarray(src_pts, dtype=np.float64)
        tgt_arr = np.asarray(tgt_pts, dtype=np.float64)
        src_diag = float(np.linalg.norm(src_arr.max(axis=0) - src_arr.min(axis=0)))
        tgt_diag = float(np.linalg.norm(tgt_arr.max(axis=0) - tgt_arr.min(axis=0)))
        if tgt_diag > 1e-12:
            return src_diag / tgt_diag
    return 1.0


def _load_twist_segments(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return dict((json.loads(path.read_text(encoding="utf-8")).get("twist_segments", {}) or {}))


def _registry_hierarchy(registry: BindPoseRegistry) -> dict[str, Optional[str]]:
    return {
        _key(name): registry.parents.get(_key(name)) or None
        for name in registry.bone_names
    }


def _snapshot(bind: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {key: np.asarray(matrix, dtype=np.float64).copy() for key, matrix in bind.items()}


def _plain_bone_names(registry: BindPoseRegistry) -> list[str]:
    return [_key(name) for name in registry.bone_names]


def _source_alignment_score(source_key: str, source_registry: BindPoseRegistry) -> int:
    node = source_registry.node_lookup.get(source_key)
    score = 0
    if source_key.endswith("_g"):
        score += 50
    if node is not None and bool(getattr(node, "is_mesh", False)):
        score += 20
    if "hook" in source_key or "dummy" in source_key:
        score -= 25
    if node is not None and bool(getattr(node, "is_skin", False)):
        score -= 100
    return score


def _reverse_bone_map(
    bone_map: Mapping[str, str],
    source_registry: BindPoseRegistry,
) -> dict[str, str]:
    """Return target -> preferred source, resolving duplicate aliases.

    The current pmbam map contains pairs like ``lforearm_g -> lowerarm_l`` and
    ``lforearm -> lowerarm_l``.  For mesh rebinding the mesh-bone ``*_g`` node
    must win over dummy/helper aliases because skin palettes reference those
    renderable bone-meshes directly.
    """

    reverse: dict[str, str] = {}
    for source, target in bone_map.items():
        source_key = _key(source)
        target_key = _key(target)
        if not source_key or not target_key:
            continue
        existing = reverse.get(target_key)
        if existing is None:
            reverse[target_key] = source_key
            continue
        if _source_alignment_score(source_key, source_registry) > _source_alignment_score(existing, source_registry):
            reverse[target_key] = source_key
    return reverse


def align_target_skeleton_to_source(
    source_skeleton_id: str,
    target_skeleton_id: str,
    bone_map: Dict[str, str],
    registry: BindPoseRegistry,
    options: AlignmentOptions = AlignmentOptions(),
    *,
    source_registry: BindPoseRegistry | None = None,
    target_registry: BindPoseRegistry | None = None,
) -> AlignedSkeleton:
    """Build a target-named, source-proportioned skeleton."""

    if target_registry is None:
        target_registry = registry
    if source_registry is None:
        raise AlignmentInputError("source_registry is required for Day 3B.5 alignment")

    source_bind = source_registry.bind_world
    target_bind_raw = target_registry.bind_world
    target_hierarchy = _registry_hierarchy(target_registry)
    target_order = topological_sort(target_hierarchy)
    raw_snapshot = _snapshot(target_bind_raw) if options.capture_pre_alignment_snapshot else None
    clean_map = {_key(src): _key(dst) for src, dst in bone_map.items() if _key(src) and _key(dst)}

    for source_name, target_name in clean_map.items():
        if source_name not in source_bind:
            raise AlignmentInputError(f"Bone map references missing source: {source_name}")
        if target_name not in target_bind_raw:
            raise AlignmentInputError(f"Bone map references missing target: {target_name}")

    scale_factor = compute_global_scale(
        source_bind,
        target_bind_raw,
        clean_map,
        options.scale_strategy,
        options.explicit_scale,
    )
    reverse_map = _reverse_bone_map(clean_map, source_registry)
    twist_segments = _load_twist_segments(options.twist_segment_map_path)
    twist_keys = {_key(name) for name in twist_segments}

    aligned_world: Dict[str, np.ndarray] = {}
    deltas: Dict[str, BoneAlignmentDelta] = {}

    def record(
        target_name: str,
        source_name: Optional[str],
        matrix: np.ndarray,
        strategy: Literal["direct_copy", "twist_interpolated", "ancestor_fallback", "root_anchor"],
    ) -> None:
        raw_pos = extract_position(target_bind_raw[target_name])
        aligned_pos = extract_position(matrix)
        source_pos = extract_position(source_bind[source_name]) if source_name is not None else None
        deltas[target_name] = BoneAlignmentDelta(
            bone_name=target_name,
            source_mapped_from=source_name,
            raw_target_world_pos=raw_pos,
            aligned_target_world_pos=aligned_pos,
            source_world_pos=source_pos,
            position_delta_magnitude=float(np.linalg.norm(aligned_pos - raw_pos)),
            handling_strategy=strategy,
        )

    # First pass: direct mapped bones and regular fallback bones. Twist leaves
    # are handled after endpoints exist because Quinn's sibling order can place
    # a twist before its child endpoint.
    for target_name in target_order:
        if target_name in twist_keys and options.twist_alignment == "interpolate":
            continue
        if target_name in reverse_map:
            source_name = reverse_map[target_name]
            aligned_world[target_name] = source_bind[source_name].copy()
            record(target_name, source_name, aligned_world[target_name], "direct_copy")
            continue

        parent_name = target_hierarchy.get(target_name)
        if parent_name is None or parent_name not in aligned_world:
            aligned_world[target_name] = target_bind_raw[target_name].copy()
            record(target_name, None, aligned_world[target_name], "root_anchor")
            continue

        raw_local = np.linalg.inv(target_bind_raw[parent_name]) @ target_bind_raw[target_name]
        aligned_world[target_name] = aligned_world[parent_name] @ raw_local
        record(target_name, None, aligned_world[target_name], "ancestor_fallback")

    # Second pass: twist bones interpolate along aligned endpoint segments.
    for target_name in target_order:
        if target_name not in twist_keys or target_name in aligned_world:
            continue
        spec = twist_segments[target_name]
        parent = _key(spec.get("parent_bone", ""))
        child = _key(spec.get("child_bone", ""))
        if (
            options.twist_alignment == "interpolate"
            and parent in aligned_world
            and child in aligned_world
        ):
            t = float(spec.get("twist_position", 0.5))
            pos = lerp_position(aligned_world[parent], aligned_world[child], t)
            rot = extract_rotation(aligned_world[parent])
            aligned_world[target_name] = compose_matrix(pos, rot)
            record(target_name, None, aligned_world[target_name], "twist_interpolated")
            continue

        parent_name = target_hierarchy.get(target_name)
        if parent_name and parent_name in aligned_world:
            raw_local = np.linalg.inv(target_bind_raw[parent_name]) @ target_bind_raw[target_name]
            aligned_world[target_name] = aligned_world[parent_name] @ raw_local
            record(target_name, None, aligned_world[target_name], "ancestor_fallback")
        else:
            aligned_world[target_name] = target_bind_raw[target_name].copy()
            record(target_name, None, aligned_world[target_name], "root_anchor")

    max_drift = 0.0
    for target_name, source_name in reverse_map.items():
        drift = float(np.linalg.norm(extract_position(aligned_world[target_name]) - extract_position(source_bind[source_name])))
        if drift > options.max_mapped_bone_drift:
            raise AlignmentDriftExceeded(
                f"Mapped bone {target_name} drifted {drift:.4f}m > {options.max_mapped_bone_drift:.4f}m"
            )
        max_drift = max(max_drift, drift)

    if options.require_non_degenerate_bind:
        for bone_name, matrix in aligned_world.items():
            det = float(np.linalg.det(np.asarray(matrix, dtype=np.float64)[:3, :3]))
            if abs(det) < 1e-6:
                raise AlignmentProducedDegenerateBind(f"{bone_name} has det={det:g}")

    aligned_local = compute_local_from_world(aligned_world, target_hierarchy)
    root_translation = np.zeros(3, dtype=np.float64)
    if "root" in aligned_world and "root" in target_bind_raw:
        root_translation = extract_position(aligned_world["root"]) - (extract_position(target_bind_raw["root"]) * scale_factor)

    return AlignedSkeleton(
        skeleton_id=f"{target_skeleton_id}_aligned_to_{source_skeleton_id}",
        base_target_id=target_skeleton_id,
        source_id=source_skeleton_id,
        bone_names=_plain_bone_names(target_registry),
        bone_parents=target_hierarchy,
        bind_world=aligned_world,
        bind_local=aligned_local,
        alignment_metadata=AlignmentMetadata(
            global_scale_factor=float(scale_factor),
            root_translation=root_translation,
            per_bone_deltas=deltas,
            unmapped_bones_handled=[
                name for name, delta in deltas.items()
                if delta.handling_strategy == "ancestor_fallback"
            ],
            twist_bones_interpolated=[
                name for name, delta in deltas.items()
                if delta.handling_strategy == "twist_interpolated"
            ],
            validation_max_drift=max_drift,
            raw_target_snapshot=raw_snapshot,
        ),
    )


def aligned_skeleton_to_registry(aligned: AlignedSkeleton) -> BindPoseRegistry:
    bind_inv = {key: np.linalg.inv(matrix) for key, matrix in aligned.bind_world.items()}
    return BindPoseRegistry(
        skeleton_id=aligned.skeleton_id,
        bone_names=list(aligned.bone_names),
        bone_index={_key(name): idx for idx, name in enumerate(aligned.bone_names)},
        parents={key: parent for key, parent in aligned.bone_parents.items() if parent},
        bind_world={key: matrix.copy() for key, matrix in aligned.bind_world.items()},
        bind_world_inv=bind_inv,
        local_bind={key: matrix.copy() for key, matrix in aligned.bind_local.items()},
        node_lookup={},
        g5_inverse_bind_delta_max=0.0,
        g5_bone_count=len(aligned.bone_names),
    )


def alignment_summary(aligned: AlignedSkeleton) -> dict[str, Any]:
    metadata = aligned.alignment_metadata
    return {
        "skeleton_id": aligned.skeleton_id,
        "base_target_id": aligned.base_target_id,
        "source_id": aligned.source_id,
        "global_scale_factor": metadata.global_scale_factor,
        "root_translation": metadata.root_translation.tolist(),
        "validation_max_drift": metadata.validation_max_drift,
        "unmapped_bones_handled": list(metadata.unmapped_bones_handled),
        "twist_bones_interpolated": list(metadata.twist_bones_interpolated),
        "raw_target_snapshot_captured": metadata.raw_target_snapshot is not None,
        "handling_counts": {
            strategy: sum(
                1 for delta in metadata.per_bone_deltas.values()
                if delta.handling_strategy == strategy
            )
            for strategy in ("direct_copy", "twist_interpolated", "ancestor_fallback", "root_anchor")
        },
    }
