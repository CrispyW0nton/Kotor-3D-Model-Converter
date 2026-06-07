"""Sample KOTOR/Odyssey Aurora animation slots as retarget source clips."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, List

from src.core.animation.animation_engine import evaluate_aurora_animation_pose
from src.core.game.kotor_loader import resolve_animation_slot
from src.core.geometry.model_data import Animation, KotorModel, ModelNode, ResolvedAnimationSlot

from .source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
    hemisphere_continuity_xyzw,
    normalize_quat_xyzw,
    quat_dot_xyzw,
)


class KotorAnimationSourceError(ValueError):
    """Raised when a KOTOR animation slot cannot be sampled as a source clip."""


@dataclass
class KotorAnimationSourceRequest:
    """Inputs for sampling a local or inherited Aurora animation slot."""

    source_model: KotorModel
    animation_slot: str
    supermodel_chain: Any | None = None
    sample_rate: float = 30.0
    reference_mode: str = "model_rest"  # model_rest, slot_time
    reference_time: float = 0.0
    clamp: bool = True


@dataclass
class KotorAnimationSourceReport:
    """Diagnostics for a sampled KOTOR/Aurora source animation."""

    source_model_name: str | None
    resolved_slot_name: str
    slot_source: str | None
    duration_seconds: float
    sample_count: int
    node_count: int
    controller_node_count: int
    inherited_from_supermodel: bool
    root_drift_distance: float = 0.0
    max_quaternion_norm_error: float = 0.0
    max_adjacent_rotation_degrees: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class KotorAnimationSourceResult:
    """Sampled source clip plus resolution metadata."""

    source_clip: SourceSkeletonClip
    resolved_slot: ResolvedAnimationSlot
    report: KotorAnimationSourceReport


def sample_kotor_animation_slot_as_source_clip(
    request: KotorAnimationSourceRequest,
) -> KotorAnimationSourceResult:
    """Evaluate a KOTOR/Aurora animation slot into SourceSkeletonClip samples.

    The returned source clip intentionally reuses the source-animation data
    model, but its nodes are Aurora object nodes, not Unreal bones.
    """

    model = request.source_model
    slot = str(request.animation_slot or "").strip()
    if not slot:
        raise KotorAnimationSourceError("KOTOR source animation slot cannot be empty.")
    sample_rate = float(request.sample_rate or 0.0)
    if sample_rate <= 0.0 or not math.isfinite(sample_rate):
        raise KotorAnimationSourceError("KOTOR source sample rate must be a positive finite number.")

    resolved = _resolve_source_slot(model, slot)
    animation = get_resolved_animation_block(model, resolved, request.supermodel_chain)
    _validate_source_model(model)
    _validate_animation_nodes(model, animation)

    rest_pose = _build_reference_pose(model, animation, request)
    nodes = _build_source_nodes(model, rest_pose)
    sample_times = _sample_times(float(animation.length or 0.0), sample_rate)
    sampled_poses, report_metrics = _sample_poses(model, animation, sample_times, clamp=bool(request.clamp))

    warnings = [
        "KOTOR source clip uses Aurora node hierarchy; not a UE skeleton.",
        "KOTOR source clip has no explicit unit scale metadata.",
    ]
    if resolved.inherited:
        warnings.append(f"Animation slot '{resolved.slot_name}' is inherited from '{resolved.source_model_name}'.")
    if float(animation.length or 0.0) <= 0.0:
        warnings.append(f"Animation slot '{resolved.slot_name}' has zero duration.")
    helper_count = sum(1 for node in nodes if node.classification in {"hook", "mesh", "helper"})
    if helper_count:
        warnings.append(f"KOTOR source hierarchy includes {helper_count} hook/helper/mesh node(s).")

    clip = SourceSkeletonClip(
        source_path=_source_identifier(model),
        clip_name=resolved.slot_name,
        duration_seconds=max(0.0, float(animation.length or 0.0)),
        sample_rate=sample_rate,
        nodes=nodes,
        rest_pose=rest_pose,
        sampled_poses=sampled_poses,
        axis_system="kotor_aurora",
        unit_scale_to_meters=None,
        handedness=None,
        import_warnings=warnings,
    )
    report = KotorAnimationSourceReport(
        source_model_name=str(getattr(model, "name", "") or "") or None,
        resolved_slot_name=resolved.slot_name,
        slot_source=resolved.source_model_name or None,
        duration_seconds=clip.duration_seconds,
        sample_count=len(sampled_poses),
        node_count=len(nodes),
        controller_node_count=len({node.name.lower() for node in animation.nodes}),
        inherited_from_supermodel=bool(resolved.inherited),
        root_drift_distance=report_metrics["root_drift_distance"],
        max_quaternion_norm_error=report_metrics["max_quaternion_norm_error"],
        max_adjacent_rotation_degrees=report_metrics["max_adjacent_rotation_degrees"],
        warnings=warnings,
    )
    return KotorAnimationSourceResult(source_clip=clip, resolved_slot=resolved, report=report)


def get_resolved_animation_block(
    source_model: KotorModel,
    resolved_slot: ResolvedAnimationSlot,
    supermodel_chain: Any | None = None,
) -> Animation:
    """Return the AnimationBlock selected by a resolved local/inherited slot."""

    if resolved_slot.animation is not None:
        return resolved_slot.animation
    raise KotorAnimationSourceError(
        f"Resolved KOTOR animation slot '{resolved_slot.slot_name}' but could not locate its AnimationBlock "
        "in the local model or supermodel chain."
    )


def audit_kotor_animation_source_clip(clip: SourceSkeletonClip) -> KotorAnimationSourceReport:
    """Return a lightweight report for an already-sampled KOTOR source clip."""

    duration = max(0.0, float(getattr(clip, "duration_seconds", 0.0) or 0.0))
    root_name = _root_node_name(clip.nodes)
    root_drift = 0.0
    max_norm_error = 0.0
    max_adjacent = 0.0
    previous_by_node: dict[str, tuple[float, float, float, float]] = {}
    first_root_position = None
    for pose in clip.sampled_poses:
        if root_name and root_name in pose.world_transforms:
            root_position = pose.world_transforms[root_name].position
            if first_root_position is None:
                first_root_position = root_position
            root_drift = max(root_drift, _horizontal_distance(first_root_position, root_position))
        for node_name, transform in pose.local_transforms.items():
            q = normalize_quat_xyzw(transform.rotation)
            norm = math.sqrt(sum(value * value for value in q))
            max_norm_error = max(max_norm_error, abs(1.0 - norm))
            previous = previous_by_node.get(node_name)
            if previous is not None:
                dot = abs(quat_dot_xyzw(previous, q))
                dot = max(-1.0, min(1.0, dot))
                max_adjacent = max(max_adjacent, math.degrees(2.0 * math.acos(dot)))
            previous_by_node[node_name] = q
    return KotorAnimationSourceReport(
        source_model_name=None,
        resolved_slot_name=clip.clip_name,
        slot_source=None,
        duration_seconds=duration,
        sample_count=len(clip.sampled_poses),
        node_count=len(clip.nodes),
        controller_node_count=0,
        inherited_from_supermodel=False,
        root_drift_distance=root_drift,
        max_quaternion_norm_error=max_norm_error,
        max_adjacent_rotation_degrees=max_adjacent,
        warnings=list(clip.import_warnings),
    )


def _resolve_source_slot(model: KotorModel, slot: str) -> ResolvedAnimationSlot:
    try:
        return resolve_animation_slot(model, slot, require_valid=True)
    except ValueError as exc:
        raise KotorAnimationSourceError(
            f"Invalid KOTOR source animation slot '{slot}'. "
            "KOTOR source sampling requires a valid local or inherited Aurora animation slot. "
            "UE clip names are not KOTOR animation slot names."
        ) from exc


def _validate_source_model(model: KotorModel) -> None:
    nodes = model.all_nodes()
    if not nodes:
        raise KotorAnimationSourceError("KOTOR source model has no Aurora nodes to sample.")
    lowered = [node.name.lower() for node in nodes]
    duplicates = sorted({name for name in lowered if lowered.count(name) > 1})
    if duplicates:
        raise KotorAnimationSourceError(
            "KOTOR source model has duplicate Aurora node name(s): " + ", ".join(duplicates)
        )


def _validate_animation_nodes(model: KotorModel, animation: Animation) -> None:
    known = {node.name.lower() for node in model.all_nodes()}
    for anim_node in getattr(animation, "nodes", []) or []:
        name = str(getattr(anim_node, "name", "") or "").strip()
        if not name:
            continue
        if name.lower() not in known:
            raise KotorAnimationSourceError(
                f"KOTOR source animation '{animation.name}' has a controller for unknown Aurora node '{name}'. "
                "Source sampling cannot produce a deterministic retarget clip."
            )
        for controller in getattr(anim_node, "controllers", []) or []:
            _validate_controller_values(animation.name, name, controller)


def _validate_controller_values(animation_name: str, node_name: str, controller: dict) -> None:
    label = str(controller.get("name", controller.get("type", "controller")))
    for raw_time in controller.get("times", []) or []:
        if not math.isfinite(float(raw_time)):
            raise KotorAnimationSourceError(
                f"KOTOR source animation '{animation_name}' has a non-finite key time on node '{node_name}'."
            )
    for index, row in enumerate(controller.get("values", []) or []):
        try:
            values = [float(value) for value in row]
        except (TypeError, ValueError) as exc:
            raise KotorAnimationSourceError(
                f"KOTOR source animation '{animation_name}' has a non-numeric {label} key on node '{node_name}'."
            ) from exc
        if not all(math.isfinite(value) for value in values):
            raise KotorAnimationSourceError(
                f"KOTOR source animation '{animation_name}' has a non-finite {label} key on node '{node_name}'."
            )
        if (controller.get("type") == 20 or label.lower() == "orientation") and len(values) >= 4:
            norm = math.sqrt(sum(value * value for value in values[:4]))
            if norm <= 1e-9:
                raise KotorAnimationSourceError(
                    f"KOTOR source animation '{animation_name}' has a zero-length orientation key on node '{node_name}'."
                )


def _build_reference_pose(model: KotorModel, animation: Animation, request: KotorAnimationSourceRequest) -> SourcePose:
    mode = str(request.reference_mode or "model_rest").strip().lower()
    if mode == "model_rest":
        empty = Animation(name="__model_rest__", length=0.0, nodes=[])
        evaluated = evaluate_aurora_animation_pose(model, empty, 0.0, clamp=True)
        return _source_pose_from_evaluated(0.0, evaluated)
    if mode == "slot_time":
        evaluated = evaluate_aurora_animation_pose(
            model,
            animation,
            float(request.reference_time or 0.0),
            clamp=bool(request.clamp),
        )
        return _source_pose_from_evaluated(float(request.reference_time or 0.0), evaluated)
    raise KotorAnimationSourceError(f"Unsupported KOTOR source reference mode '{request.reference_mode}'.")


def _build_source_nodes(model: KotorModel, rest_pose: SourcePose) -> list[SourceSkeletonNode]:
    nodes: list[SourceSkeletonNode] = []
    for index, node in enumerate(model.all_nodes()):
        rest_local = rest_pose.local_transforms.get(node.name)
        rest_global = rest_pose.global_transforms.get(node.name)
        if rest_local is None or rest_global is None:
            raise KotorAnimationSourceError(f"Missing rest transform for KOTOR source node '{node.name}'.")
        nodes.append(
            SourceSkeletonNode(
                name=node.name,
                parent_name=node.parent.name if node.parent is not None else None,
                index=index,
                rest_local=rest_local,
                rest_global=rest_global,
                classification=_classify_aurora_source_node(node),
            )
        )
    return nodes


def _sample_poses(
    model: KotorModel,
    animation: Animation,
    sample_times: list[float],
    *,
    clamp: bool,
) -> tuple[list[SourcePose], dict[str, float]]:
    poses: list[SourcePose] = []
    previous_local: dict[str, tuple[float, float, float, float]] = {}
    previous_global: dict[str, tuple[float, float, float, float]] = {}
    previous_report_local: dict[str, tuple[float, float, float, float]] = {}
    root_name = model.root_node.name if model.root_node is not None else ""
    first_root_position = None
    root_drift = 0.0
    max_norm_error = 0.0
    max_adjacent = 0.0

    for time_seconds in sample_times:
        evaluated = evaluate_aurora_animation_pose(model, animation, time_seconds, clamp=clamp)
        pose = _source_pose_from_evaluated(
            time_seconds,
            evaluated,
            previous_local=previous_local,
            previous_global=previous_global,
        )
        for node_name, transform in pose.local_transforms.items():
            _validate_transform(animation.name, node_name, time_seconds, transform)
            quat = normalize_quat_xyzw(transform.rotation)
            norm = math.sqrt(sum(value * value for value in quat))
            max_norm_error = max(max_norm_error, abs(1.0 - norm))
            previous = previous_report_local.get(node_name)
            if previous is not None:
                dot = abs(quat_dot_xyzw(previous, quat))
                dot = max(-1.0, min(1.0, dot))
                max_adjacent = max(max_adjacent, math.degrees(2.0 * math.acos(dot)))
            previous_report_local[node_name] = quat
        for node_name, transform in pose.global_transforms.items():
            _validate_transform(animation.name, node_name, time_seconds, transform)
        if root_name and root_name in pose.global_transforms:
            root_position = pose.global_transforms[root_name].position
            if first_root_position is None:
                first_root_position = root_position
            root_drift = max(root_drift, _horizontal_distance(first_root_position, root_position))
        poses.append(pose)

    return poses, {
        "root_drift_distance": root_drift,
        "max_quaternion_norm_error": max_norm_error,
        "max_adjacent_rotation_degrees": max_adjacent,
    }


def _source_pose_from_evaluated(
    time_seconds: float,
    evaluated,
    *,
    previous_local: dict[str, tuple[float, float, float, float]] | None = None,
    previous_global: dict[str, tuple[float, float, float, float]] | None = None,
) -> SourcePose:
    local_transforms: dict[str, Transform] = {}
    global_transforms: dict[str, Transform] = {}
    for node_name, transform in evaluated.local_transforms_by_node.items():
        local_transforms[node_name] = _to_source_transform(transform, previous_local, node_name)
    for node_name, transform in evaluated.world_transforms_by_node.items():
        global_transforms[node_name] = _to_source_transform(transform, previous_global, node_name)
    return SourcePose(
        time_seconds=float(time_seconds),
        global_transforms=global_transforms,
        local_transforms=local_transforms,
    )


def _to_source_transform(
    transform,
    previous_by_node: dict[str, tuple[float, float, float, float]] | None,
    node_name: str,
) -> Transform:
    previous = previous_by_node.get(node_name) if previous_by_node is not None else None
    rotation = hemisphere_continuity_xyzw(transform.rotation, previous)
    if previous_by_node is not None:
        previous_by_node[node_name] = rotation
    return Transform(
        position=tuple(float(value) for value in transform.position),
        rotation=rotation,
        scale=(1.0, 1.0, 1.0),
    )


def _validate_transform(animation_name: str, node_name: str, time_seconds: float, transform: Transform) -> None:
    if not transform.is_finite():
        raise KotorAnimationSourceError(
            f"KOTOR source animation '{animation_name}' produced a non-finite transform "
            f"for node '{node_name}' at t={time_seconds:.3f}."
        )
    qx, qy, qz, qw = transform.rotation
    if math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) <= 1e-9:
        raise KotorAnimationSourceError(
            f"KOTOR source animation '{animation_name}' produced a zero-length quaternion "
            f"for node '{node_name}' at t={time_seconds:.3f}."
        )


def _sample_times(duration: float, sample_rate: float) -> list[float]:
    duration = max(0.0, float(duration or 0.0))
    if duration <= 0.0:
        return [0.0]
    frame_count = int(math.floor(duration * sample_rate + 1e-9))
    times = [round(index / sample_rate, 9) for index in range(frame_count + 1)]
    times = [time for time in times if time <= duration + 1e-9]
    times.append(duration)
    return sorted({round(float(time), 9) for time in times})


def _classify_aurora_source_node(node: ModelNode) -> str:
    name = str(getattr(node, "name", "") or "").lower()
    if node.parent is None:
        return "root"
    if "hook" in name or name in {"rhand", "lhand", "talkdummy"}:
        return "hook"
    if getattr(node, "is_mesh", False):
        return "mesh"
    if "helper" in name or "dummy" in name:
        return "helper"
    return "aurora_node"


def _source_identifier(model: KotorModel) -> str:
    path = str(getattr(model, "mdl_path", "") or "").strip()
    if path:
        return path
    return str(getattr(model, "name", "") or "kotor_source_model")


def _root_node_name(nodes: list[SourceSkeletonNode]) -> str:
    for node in nodes:
        if not node.parent_name:
            return node.name
    return nodes[0].name if nodes else ""


def _horizontal_distance(a, b) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)
