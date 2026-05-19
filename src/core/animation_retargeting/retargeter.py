"""KotOR-to-KotOR animation retargeting.

This module is intentionally scoped to Odyssey/KotOR models. Unreal target
skeleton handling lives under ``src.unreal`` so the Animation Retargeting
Workbench keeps its game-model assumptions stable.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

from ..animation_engine import AnimPose, NodePose
from ..model_data import Animation


_ALIASES: Dict[str, tuple[str, ...]] = {
    "rootdummy": ("root", "root_g", "dummyroot"),
    "pelvis_g": ("pelvis", "hips", "hip_g"),
    "torso_g": ("spine", "spine_g", "chest_g"),
    "torsoupr_g": ("spine1", "spine_01", "chest"),
    "neck_g": ("neck", "necklwr_g"),
    "rhand": ("r_hand", "rhand_g", "hand_r"),
    "lhand": ("l_hand", "lhand_g", "hand_l"),
    "rfoot_g": ("rfoot", "foot_r", "r_foot"),
    "lfoot_g": ("lfoot", "foot_l", "l_foot"),
}


@dataclass(frozen=True)
class RetargetConfig:
    """Controls how KotOR poses are transferred between models."""

    preserve_model_scale: bool = True
    ignore_scale_keys: bool = True
    copy_material_animation: bool = True
    allow_unmapped_nodes: bool = False
    root_motion_scale: float = 1.0


@dataclass(frozen=True)
class BoneMappingReport:
    source_model: str = ""
    target_model: str = ""
    mapping: Dict[str, str] = field(default_factory=dict)
    exact_matches: int = 0
    alias_matches: int = 0
    manual_matches: int = 0
    missing_source: tuple[str, ...] = ()
    missing_target: tuple[str, ...] = ()

    @property
    def matched_count(self) -> int:
        return len(self.mapping)


@dataclass(frozen=True)
class RetargetResult:
    pose: AnimPose
    report: BoneMappingReport


def _nodes_by_name(model) -> Dict[str, object]:
    nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
    out: Dict[str, object] = {}
    for node in nodes:
        key = str(getattr(node, "name", "") or "").lower()
        if not key or "hook" in key:
            continue
        out[key] = node
    return out


def _candidate_names(source_name: str) -> Iterable[str]:
    key = source_name.lower()
    yield key
    for alias in _ALIASES.get(key, ()):
        yield alias.lower()
    for src, aliases in _ALIASES.items():
        if key in aliases:
            yield src
            for alias in aliases:
                yield alias.lower()


def _clean_manual_mapping(manual_mapping: Optional[dict[str, str]]) -> Dict[str, str]:
    if not manual_mapping:
        return {}
    out: Dict[str, str] = {}
    for src, dst in manual_mapping.items():
        src_key = str(src or "").strip().lower()
        dst_key = str(dst or "").strip().lower()
        if src_key and dst_key:
            out[src_key] = dst_key
    return out


def build_bone_map(
    source_model,
    target_model,
    manual_mapping: Optional[dict[str, str]] = None,
) -> BoneMappingReport:
    """Build a conservative source-node-name to target-node-name map."""
    src_nodes = _nodes_by_name(source_model)
    dst_nodes = _nodes_by_name(target_model)
    manual = _clean_manual_mapping(manual_mapping)
    mapping: Dict[str, str] = {}
    exact = 0
    alias = 0
    manual_count = 0

    for src_name in src_nodes:
        manual_target = manual.get(src_name, "")
        if manual_target and manual_target in dst_nodes:
            mapping[src_name] = manual_target
            manual_count += 1
            continue

        target_name = ""
        for candidate in _candidate_names(src_name):
            if candidate in dst_nodes:
                target_name = candidate
                break
        if not target_name:
            continue
        mapping[src_name] = target_name
        if target_name == src_name:
            exact += 1
        else:
            alias += 1

    missing_source = tuple(sorted(src for src in src_nodes if src not in mapping))
    mapped_targets = set(mapping.values())
    missing_target = tuple(sorted(dst for dst in dst_nodes if dst not in mapped_targets))
    return BoneMappingReport(
        source_model=str(getattr(source_model, "name", "") or ""),
        target_model=str(getattr(target_model, "name", "") or ""),
        mapping=mapping,
        exact_matches=exact,
        alias_matches=alias,
        manual_matches=manual_count,
        missing_source=missing_source,
        missing_target=missing_target,
    )


def _sub3(a, b) -> tuple[float, float, float]:
    return (
        float(a[0]) - float(b[0]),
        float(a[1]) - float(b[1]),
        float(a[2]) - float(b[2]),
    )


def _add3(a, b, scale: float = 1.0) -> tuple[float, float, float]:
    return (
        float(a[0]) + float(b[0]) * scale,
        float(a[1]) + float(b[1]) * scale,
        float(a[2]) + float(b[2]) * scale,
    )


def _mul3(a, scale: float) -> tuple[float, float, float]:
    return (float(a[0]) * scale, float(a[1]) * scale, float(a[2]) * scale)


def _normal_quat(q) -> tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-8:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / length, y / length, z / length, w / length)


def _quat_conjugate(q) -> tuple[float, float, float, float]:
    x, y, z, w = _normal_quat(q)
    return (-x, -y, -z, w)


def _quat_mul(a, b) -> tuple[float, float, float, float]:
    ax, ay, az, aw = _normal_quat(a)
    bx, by, bz, bw = _normal_quat(b)
    return _normal_quat((
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ))


def _retarget_rotation(src_pose_rot, src_bind_rot, dst_bind_rot) -> tuple[float, float, float, float]:
    src_delta = _quat_mul(src_pose_rot, _quat_conjugate(src_bind_rot))
    return _quat_mul(src_delta, dst_bind_rot)


def _world_positions_by_key(model) -> dict[str, tuple[float, float, float]]:
    out: dict[str, tuple[float, float, float]] = {}

    def visit(node: object, parent_pos: tuple[float, float, float]) -> None:
        local = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
        world = _add3(parent_pos, local)
        key = str(getattr(node, "name", "") or "").lower()
        if key:
            out[key] = world
        for child in getattr(node, "children", []) or []:
            visit(child, world)

    root = getattr(model, "root_node", None)
    if root is not None:
        visit(root, (0.0, 0.0, 0.0))
    else:
        for node in list(model.all_nodes()) if hasattr(model, "all_nodes") else []:
            key = str(getattr(node, "name", "") or "").lower()
            if key:
                out[key] = tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
    return out


def _height_from_positions(positions: Iterable[tuple[float, float, float]]) -> float:
    zs = [float(pos[2]) for pos in positions]
    return max(zs) - min(zs) if zs else 0.0


def _position_delta_scale(cfg: RetargetConfig, source_model, target_model, report: BoneMappingReport) -> float:
    if not cfg.preserve_model_scale:
        return 1.0
    src_world = _world_positions_by_key(source_model)
    dst_world = _world_positions_by_key(target_model)
    src_points = []
    dst_points = []
    for src_key, dst_key in report.mapping.items():
        if src_key in src_world and dst_key in dst_world:
            src_points.append(src_world[src_key])
            dst_points.append(dst_world[dst_key])
    src_height = _height_from_positions(src_points)
    dst_height = _height_from_positions(dst_points)
    if src_height <= 1e-6 or dst_height <= 1e-6:
        return 1.0
    return max(0.01, min(100.0, dst_height / src_height))


def retarget_pose(
    source_pose: AnimPose,
    source_model,
    target_model,
    config: Optional[RetargetConfig] = None,
    mapping_report: Optional[BoneMappingReport] = None,
) -> RetargetResult:
    """Retarget one evaluated KotOR pose onto another KotOR model."""
    cfg = config or RetargetConfig()
    report = mapping_report or build_bone_map(source_model, target_model)
    src_nodes = _nodes_by_name(source_model)
    dst_nodes = _nodes_by_name(target_model)
    position_delta_scale = _position_delta_scale(cfg, source_model, target_model, report)
    out = AnimPose(time=float(getattr(source_pose, "time", 0.0) or 0.0))

    for src_name, src_np in (getattr(source_pose, "nodes", {}) or {}).items():
        src_key = str(src_name or "").lower()
        dst_key = report.mapping.get(src_key)
        if not dst_key and cfg.allow_unmapped_nodes:
            dst_key = src_key
        if not dst_key or dst_key not in dst_nodes:
            continue

        src_node = src_nodes.get(src_key)
        dst_node = dst_nodes[dst_key]
        src_bind_pos = getattr(src_node, "position", (0.0, 0.0, 0.0)) if src_node else (0.0, 0.0, 0.0)
        src_bind_rot = getattr(src_node, "rotation", (0.0, 0.0, 0.0, 1.0)) if src_node else (0.0, 0.0, 0.0, 1.0)
        dst_bind_pos = getattr(dst_node, "position", (0.0, 0.0, 0.0))
        dst_bind_rot = getattr(dst_node, "rotation", (0.0, 0.0, 0.0, 1.0))
        delta = _sub3(getattr(src_np, "position", (0.0, 0.0, 0.0)), src_bind_pos)
        motion_scale = position_delta_scale
        if src_key in {"rootdummy", "root"}:
            motion_scale *= cfg.root_motion_scale
        position = _add3(dst_bind_pos, delta, motion_scale)
        rotation = _retarget_rotation(
            getattr(src_np, "rotation", (0.0, 0.0, 0.0, 1.0)),
            src_bind_rot,
            dst_bind_rot,
        )

        out.nodes[dst_key] = NodePose(
            name=str(getattr(dst_node, "name", dst_key) or dst_key),
            position=position,
            rotation=rotation,
            scale=1.0 if cfg.ignore_scale_keys else float(getattr(src_np, "scale", 1.0) or 1.0),
            alpha=getattr(src_np, "alpha", None) if cfg.copy_material_animation else None,
            selfillum=getattr(src_np, "selfillum", None) if cfg.copy_material_animation else None,
        )

    return RetargetResult(pose=out, report=report)


def _scaled_position_values(values, scale: float):
    if abs(scale - 1.0) <= 1e-8:
        return values
    out = []
    for val in values or []:
        if len(val) >= 3:
            out.append(_mul3(val, scale))
        else:
            out.append(val)
    return out


def retarget_animation(
    source_animation: Animation,
    source_model,
    target_model,
    config: Optional[RetargetConfig] = None,
    mapping_report: Optional[BoneMappingReport] = None,
    name_suffix: str = "_retarget",
) -> tuple[Animation, BoneMappingReport]:
    """Create a KotOR target-model animation clip from ``source_animation``."""
    cfg = config or RetargetConfig()
    report = mapping_report or build_bone_map(source_model, target_model)
    dst_nodes = _nodes_by_name(target_model)
    position_delta_scale = _position_delta_scale(cfg, source_model, target_model, report)
    new_anim = Animation(
        name=f"{getattr(source_animation, 'name', 'animation')}{name_suffix}",
        length=float(getattr(source_animation, "length", 0.0) or 0.0),
        transition_time=float(getattr(source_animation, "transition_time", 0.25) or 0.25),
        anim_root=report.mapping.get(str(getattr(source_animation, "anim_root", "") or "").lower(), ""),
        events=copy.deepcopy(getattr(source_animation, "events", []) or []),
        nodes=[],
    )

    for src_anim_node in getattr(source_animation, "nodes", []) or []:
        src_key = str(getattr(src_anim_node, "name", "") or "").lower()
        dst_key = report.mapping.get(src_key)
        if not dst_key or dst_key not in dst_nodes:
            continue
        dst_node = dst_nodes[dst_key]
        anim_node = dst_node.clone_shallow() if hasattr(dst_node, "clone_shallow") else copy.copy(dst_node)
        anim_node.name = str(getattr(dst_node, "name", dst_key) or dst_key)
        anim_node.children = []
        anim_node.parent = None
        anim_node.controllers = []
        for ctrl in getattr(src_anim_node, "controllers", []) or []:
            ctype = int(ctrl.get("type", -1)) if isinstance(ctrl, dict) else -1
            if cfg.ignore_scale_keys and ctype == 36:
                continue
            new_ctrl = copy.deepcopy(ctrl)
            if ctype == 8:
                scale = position_delta_scale
                if src_key in {"rootdummy", "root"}:
                    scale *= cfg.root_motion_scale
                new_ctrl["values"] = _scaled_position_values(new_ctrl.get("values", []) or [], scale)
            anim_node.controllers.append(new_ctrl)
        if anim_node.controllers:
            new_anim.nodes.append(anim_node)

    return new_anim, report
