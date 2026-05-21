"""In-memory viewport preview gate for generated Aurora retarget animations."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import copy
import math
from pathlib import Path
from typing import Any, List, Optional, Protocol

from src.core.animation.animation_engine import evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel
from src.core.validation.animation_block_validator import validate_animation_block_against_model

from .retarget_profile import RetargetProfile, normalize_retarget_profile
from .retarget_solve_audit import RetargetSolveReport
from .retarget_solver import (
    RetargetResult,
    RetargetSolveError,
    RetargetSolverOptions,
    retarget_source_clip_to_aurora_animation,
)
from .source_animation import SourceSkeletonClip, normalize_quat_xyzw, quat_dot_xyzw


class RetargetPreviewError(ValueError):
    """Raised when a retarget preview cannot be safely built or applied."""


@dataclass
class RetargetPreviewRequest:
    """Inputs for building an in-memory retarget preview."""

    source_clip: SourceSkeletonClip
    target_model: KotorModel
    profile: RetargetProfile
    supermodel_chain: Any | None = None
    solver_options: RetargetSolverOptions | None = None
    animation_slot: str | None = None
    auto_play: bool = True
    enable_numeric_audit: bool = True


@dataclass
class RetargetPreviewAudit:
    """Headless numeric preview audit for generated Aurora animation playback."""

    slot_name: str
    duration_seconds: float
    sample_count: int
    finite_transform_failures: List[str] = field(default_factory=list)
    non_root_translation_deviations: List[str] = field(default_factory=list)
    root_drift_distance: float = 0.0
    max_quaternion_norm_error: float = 0.0
    max_adjacent_rotation_degrees: float = 0.0
    missing_controller_nodes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            not self.finite_transform_failures
            and not self.non_root_translation_deviations
            and not self.missing_controller_nodes
            and self.root_drift_distance <= 1e-4
        )


@dataclass
class RetargetPreviewResult:
    """Prepared preview model plus diagnostics for viewport playback."""

    preview_model: KotorModel
    animation_block: Animation
    slot_name: str
    solver_report: RetargetSolveReport
    preview_audit: RetargetPreviewAudit
    warnings: List[str] = field(default_factory=list)


class RetargetViewportAdapter(Protocol):
    """Small adapter surface needed by the retarget preview gate."""

    def set_model(self, model) -> None:
        ...

    def set_active_animation(self, slot_name: str) -> None:
        ...

    def set_time(self, time_seconds: float) -> None:
        ...

    def play(self) -> None:
        ...

    def pause(self) -> None:
        ...

    def enable_node_overlay(self, enabled: bool) -> None:
        ...


def build_retarget_preview(request: RetargetPreviewRequest) -> RetargetPreviewResult:
    """Build an in-memory local animation override ready for viewport playback."""

    profile = normalize_retarget_profile(request.profile)
    if request.animation_slot:
        profile = replace(profile, animation_slot=str(request.animation_slot).strip())

    try:
        solver_result = retarget_source_clip_to_aurora_animation(
            source_clip=request.source_clip,
            target_model=request.target_model,
            profile=profile,
            supermodel_chain=request.supermodel_chain,
            options=request.solver_options,
        )
    except RetargetSolveError as exc:
        raise RetargetPreviewError(f"Cannot preview retargeted animation: {exc}") from exc
    validation = validate_animation_block_against_model(
        request.target_model,
        solver_result.animation_block,
        strict=True,
    )
    validation.raise_for_errors(
        solver_result.animation_block.name,
        getattr(request.target_model, "name", "target"),
    )

    preview_model = copy.deepcopy(request.target_model)
    animation_for_preview = copy.deepcopy(solver_result.animation_block)
    _attach_local_animation_override(preview_model, animation_for_preview)

    audit = RetargetPreviewAudit(
        slot_name=animation_for_preview.name,
        duration_seconds=float(animation_for_preview.length),
        sample_count=0,
        warnings=["numeric preview audit disabled"] if not request.enable_numeric_audit else [],
    )
    if request.enable_numeric_audit:
        audit = audit_retarget_preview_animation(
            model=preview_model,
            animation_block=animation_for_preview,
        )
        if not audit.passed:
            raise RetargetPreviewError(_format_audit_failure(animation_for_preview.name, audit))

    warnings = [*solver_result.warnings, *audit.warnings]
    return RetargetPreviewResult(
        preview_model=preview_model,
        animation_block=animation_for_preview,
        slot_name=animation_for_preview.name,
        solver_report=solver_result.report,
        preview_audit=audit,
        warnings=warnings,
    )


def apply_retarget_preview_to_viewport(
    preview: RetargetPreviewResult,
    viewport: RetargetViewportAdapter,
    *,
    auto_play: bool = True,
    show_node_overlay: bool = True,
) -> None:
    """Apply a built preview to a viewport adapter."""

    if not preview.preview_audit.passed:
        raise RetargetPreviewError(
            f"Retarget preview audit failed for slot '{preview.slot_name}'. "
            "Preview was not applied to the viewport."
        )
    viewport.set_model(preview.preview_model)
    viewport.set_active_animation(preview.slot_name)
    viewport.set_time(0.0)
    viewport.enable_node_overlay(show_node_overlay)
    if auto_play:
        viewport.play()
    else:
        viewport.pause()


def audit_retarget_preview_animation(
    *,
    model: KotorModel,
    animation_block: Animation,
    sample_times: list[float] | None = None,
) -> RetargetPreviewAudit:
    """Evaluate a preview animation and report numeric playback hazards."""

    times = _sample_times(animation_block, sample_times)
    target_nodes = {node.name.lower(): node for node in model.all_nodes()}
    audit = RetargetPreviewAudit(
        slot_name=animation_block.name,
        duration_seconds=float(animation_block.length),
        sample_count=len(times),
    )
    for anim_node in getattr(animation_block, "nodes", []) or []:
        if str(anim_node.name or "").lower() not in target_nodes:
            audit.missing_controller_nodes.append(str(anim_node.name or ""))
        _audit_raw_controllers(audit, anim_node)

    previous_root_position = None
    root_name = model.root_node.name if model.root_node is not None else ""
    rest_positions = {
        node.name: tuple(float(value) for value in node.position)
        for node in model.all_nodes()
    }
    previous_quat_by_node: dict[str, tuple[float, float, float, float]] = {}

    for time_seconds in times:
        try:
            pose = evaluate_aurora_animation_pose(model, animation_block, time_seconds)
        except Exception as exc:  # pragma: no cover - defensive
            audit.finite_transform_failures.append(
                f"slot '{animation_block.name}' failed to evaluate at t={time_seconds:.3f}: {exc}"
            )
            continue

        for node_name, transform in pose.local_transforms_by_node.items():
            _audit_transform(audit, "local", node_name, time_seconds, transform)
            if node_name != root_name:
                delta = _distance(transform.position, rest_positions.get(node_name, transform.position))
                if delta > 1e-4:
                    audit.non_root_translation_deviations.append(
                        f"node '{node_name}' local translation changed by {delta:.6g} at t={time_seconds:.3f}"
                    )
            quat = normalize_quat_xyzw(transform.rotation)
            norm = math.sqrt(sum(value * value for value in quat))
            audit.max_quaternion_norm_error = max(audit.max_quaternion_norm_error, abs(1.0 - norm))
            previous = previous_quat_by_node.get(node_name)
            if previous is not None:
                dot = abs(quat_dot_xyzw(previous, quat))
                dot = max(-1.0, min(1.0, dot))
                audit.max_adjacent_rotation_degrees = max(
                    audit.max_adjacent_rotation_degrees,
                    math.degrees(2.0 * math.acos(dot)),
                )
            previous_quat_by_node[node_name] = quat

        for node_name, transform in pose.world_transforms_by_node.items():
            _audit_transform(audit, "world", node_name, time_seconds, transform)

        if root_name and root_name in pose.world_transforms_by_node:
            root_position = pose.world_transforms_by_node[root_name].position
            if previous_root_position is None:
                previous_root_position = root_position
            audit.root_drift_distance = max(
                audit.root_drift_distance,
                _horizontal_distance(root_position, previous_root_position),
            )

    audit.warnings.append("mesh deformation audit skipped: no headless skinning evaluator available")
    return audit


def capture_retarget_preview_angles(
    viewport,
    output_dir: Path,
    *,
    basename: str,
) -> list[Path]:
    """Capture standard retarget-preview camera angles through a viewport adapter."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for angle in ("front", "side", "back", "top", "three_quarter"):
        if hasattr(viewport, "set_camera_preset"):
            viewport.set_camera_preset(angle)
        elif hasattr(viewport, "set_camera_angle"):
            viewport.set_camera_angle(angle)
        else:
            raise RetargetPreviewError("Viewport capture API is not available: missing camera preset method.")

        requested_path = output_dir / f"{basename}_{angle}.png"
        if hasattr(viewport, "capture_viewport"):
            result = viewport.capture_viewport(requested_path)
        elif hasattr(viewport, "capture"):
            result = viewport.capture(requested_path)
        else:
            raise RetargetPreviewError("Viewport capture API is not available: missing capture method.")
        paths.append(Path(result) if result else requested_path)
    return paths


def _attach_local_animation_override(model: KotorModel, animation_block: Animation) -> None:
    wanted = animation_block.name.lower()
    model.animations = [
        existing
        for existing in getattr(model, "animations", []) or []
        if str(existing.name or "").lower() != wanted
    ]
    model.animations.insert(0, animation_block)


def _sample_times(animation_block: Animation, sample_times: list[float] | None) -> list[float]:
    if sample_times is not None:
        return sorted({float(value) for value in sample_times})
    duration = max(0.0, float(getattr(animation_block, "length", 0.0) or 0.0))
    if duration <= 0.0:
        return [0.0]
    return sorted({0.0, duration * 0.25, duration * 0.5, duration * 0.75, duration})


def _audit_transform(audit: RetargetPreviewAudit, space: str, node_name: str, time_seconds: float, transform) -> None:
    values = (*transform.position, *transform.rotation)
    if not all(math.isfinite(float(value)) for value in values):
        audit.finite_transform_failures.append(
            f"node '{node_name}' has non-finite {space} transform at t={time_seconds:.3f}"
        )
        return
    norm = math.sqrt(sum(float(value) * float(value) for value in transform.rotation))
    if norm <= 1e-9:
        audit.finite_transform_failures.append(
            f"node '{node_name}' has zero-length {space} quaternion at t={time_seconds:.3f}"
        )


def _audit_raw_controllers(audit: RetargetPreviewAudit, anim_node) -> None:
    node_name = str(getattr(anim_node, "name", "") or "")
    for ctrl in getattr(anim_node, "controllers", []) or []:
        label = str(ctrl.get("name", ctrl.get("type", "controller")))
        for raw_time in ctrl.get("times", []) or []:
            try:
                if not math.isfinite(float(raw_time)):
                    audit.finite_transform_failures.append(
                        f"node '{node_name}' controller '{label}' has non-finite key time"
                    )
            except (TypeError, ValueError):
                audit.finite_transform_failures.append(
                    f"node '{node_name}' controller '{label}' has non-numeric key time"
                )
        for index, row in enumerate(ctrl.get("values", []) or []):
            try:
                values = [float(value) for value in row]
            except (TypeError, ValueError):
                audit.finite_transform_failures.append(
                    f"node '{node_name}' controller '{label}' key {index} has non-numeric value"
                )
                continue
            if not all(math.isfinite(value) for value in values):
                audit.finite_transform_failures.append(
                    f"node '{node_name}' controller '{label}' key {index} has non-finite value"
                )
            if label.lower() == "orientation" or ctrl.get("type") == 20:
                if len(values) >= 4:
                    norm = math.sqrt(sum(value * value for value in values[:4]))
                    if norm <= 1e-9:
                        audit.finite_transform_failures.append(
                            f"node '{node_name}' controller '{label}' key {index} has zero-length quaternion"
                        )


def _distance(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _horizontal_distance(a, b) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def _format_audit_failure(slot_name: str, audit: RetargetPreviewAudit) -> str:
    details = []
    if audit.finite_transform_failures:
        details.append(audit.finite_transform_failures[0])
    if audit.non_root_translation_deviations:
        details.append(
            audit.non_root_translation_deviations[0]
            + ". Non-root translation transfer is disabled to protect KOTOR mesh deformation."
        )
    if audit.missing_controller_nodes:
        details.append(f"unknown controller node '{audit.missing_controller_nodes[0]}'")
    if audit.root_drift_distance > 1e-4:
        details.append(f"root drift distance {audit.root_drift_distance:.6g} exceeds tolerance")
    suffix = " ".join(details) if details else "unknown audit failure"
    return f"Retarget preview audit failed for slot '{slot_name}': {suffix}. Preview was not applied to the viewport."
