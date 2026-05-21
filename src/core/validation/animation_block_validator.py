"""Structural validation for Aurora animation blocks before MDL export."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, Iterable, List, Optional

from src.core.animation.animation_engine import AnimationEngine
from src.core.geometry.model_data import Animation, KotorModel, ModelNode


class AnimationBlockValidationError(ValueError):
    """Raised when an animation block is unsafe to export for a target model."""


@dataclass(frozen=True)
class AnimationValidationIssue:
    """One structural animation-block validation issue."""

    message: str
    node_name: str = ""
    controller_name: str = ""
    time: Optional[float] = None


@dataclass
class AnimationValidationReport:
    """Validation result for one animation block against one Aurora model."""

    success: bool = True
    issues: List[AnimationValidationIssue] = field(default_factory=list)
    warnings: List[AnimationValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        *,
        node_name: str = "",
        controller_name: str = "",
        time: Optional[float] = None,
    ) -> None:
        self.success = False
        self.issues.append(
            AnimationValidationIssue(
                message=message,
                node_name=node_name,
                controller_name=controller_name,
                time=time,
            )
        )

    def raise_for_errors(self, animation_name: str, target_name: str) -> None:
        """Raise a user-readable export error if validation failed."""

        if self.success:
            return

        details = "; ".join(issue.message for issue in self.issues[:5])
        if len(self.issues) > 5:
            details += f"; ... and {len(self.issues) - 5} more"
        raise AnimationBlockValidationError(
            f"Animation block '{animation_name}' cannot be exported for target '{target_name}': "
            f"{details}. KOTOR animation controllers must target existing Aurora nodes "
            "on the model/supermodel hierarchy."
        )


def _controller_label(ctrl: Dict[str, Any]) -> str:
    name = str(ctrl.get("name", "") or "").strip()
    if name:
        return name
    return str(ctrl.get("type", "controller"))


def _is_position_controller(ctrl: Dict[str, Any]) -> bool:
    return ctrl.get("type") == AnimationEngine.CTRL_POSITION or str(ctrl.get("name", "")).lower() == "position"


def _is_orientation_controller(ctrl: Dict[str, Any]) -> bool:
    return (
        ctrl.get("type") == AnimationEngine.CTRL_ORIENTATION
        or str(ctrl.get("name", "")).lower() == "orientation"
    )


def _finite_values(values: Iterable[Any]) -> bool:
    try:
        return all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError):
        return False


def _validate_controller(
    report: AnimationValidationReport,
    node: ModelNode,
    ctrl: Dict[str, Any],
    *,
    animation_length: float,
    epsilon: float,
) -> None:
    label = _controller_label(ctrl)
    times = list(ctrl.get("times", []) or [])
    values = list(ctrl.get("values", []) or [])

    if len(times) != len(values):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has {len(times)} times but {len(values)} values",
            node_name=node.name,
            controller_name=label,
        )
        return
    if not times:
        return

    numeric_times: List[float] = []
    for raw_time in times:
        try:
            time_value = float(raw_time)
        except (TypeError, ValueError):
            report.add_error(
                f"controller '{label}' on node '{node.name}' has non-numeric key time {raw_time!r}",
                node_name=node.name,
                controller_name=label,
            )
            continue
        numeric_times.append(time_value)
        if not math.isfinite(time_value):
            report.add_error(
                f"controller '{label}' on node '{node.name}' has non-finite key time",
                node_name=node.name,
                controller_name=label,
                time=time_value,
            )
        elif time_value < -epsilon or time_value > animation_length + epsilon:
            report.add_error(
                f"controller '{label}' on node '{node.name}' has key time {time_value:g} outside animation length {animation_length:g}",
                node_name=node.name,
                controller_name=label,
                time=time_value,
            )

    if numeric_times != sorted(numeric_times):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has unsorted key times",
            node_name=node.name,
            controller_name=label,
        )
    if len(set(numeric_times)) != len(numeric_times):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has duplicate key times",
            node_name=node.name,
            controller_name=label,
        )

    for index, row in enumerate(values):
        row_values = list(row or [])
        time_value = numeric_times[index] if index < len(numeric_times) else None
        if _is_position_controller(ctrl):
            if len(row_values) < 3 or not _finite_values(row_values[:3]):
                report.add_error(
                    f"invalid position key on node '{node.name}' at time {time_value}: non-finite or incomplete value",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )
        elif _is_orientation_controller(ctrl):
            if len(row_values) < 4 or not _finite_values(row_values[:4]):
                report.add_error(
                    f"invalid orientation key on node '{node.name}' at time {time_value}: non-finite or incomplete quaternion",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )
                continue
            x, y, z, w = (float(value) for value in row_values[:4])
            norm_sq = x * x + y * y + z * z + w * w
            if norm_sq <= 1e-12:
                report.add_error(
                    f"invalid orientation key on node '{node.name}' at time {time_value}: zero-length quaternion",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )


def validate_animation_block_against_model(
    model: KotorModel,
    animation_block: Animation,
    *,
    strict: bool = True,
) -> AnimationValidationReport:
    """Validate that an animation block can be safely injected into ``model``."""

    report = AnimationValidationReport()
    animation_name = str(getattr(animation_block, "name", "") or "").strip()
    target_nodes = {str(node.name or "").lower(): node.name for node in model.all_nodes()}

    if not animation_name:
        report.add_error("animation name is empty")

    try:
        animation_length = float(getattr(animation_block, "length", 0.0) or 0.0)
    except (TypeError, ValueError):
        animation_length = -1.0
    if not math.isfinite(animation_length) or animation_length < 0.0:
        report.add_error(f"animation length is invalid: {getattr(animation_block, 'length', None)!r}")
        animation_length = 0.0

    epsilon = 1e-5
    for anim_node in getattr(animation_block, "nodes", []) or []:
        node_name = str(getattr(anim_node, "name", "") or "").strip()
        if not node_name:
            report.add_error("animation controller node name is empty")
            continue
        if node_name.lower() not in target_nodes:
            report.add_error(f"unknown controller node '{node_name}'", node_name=node_name)
            continue
        for ctrl in getattr(anim_node, "controllers", []) or []:
            _validate_controller(
                report,
                anim_node,
                ctrl,
                animation_length=animation_length,
                epsilon=epsilon if strict else 1e-4,
            )

    return report
