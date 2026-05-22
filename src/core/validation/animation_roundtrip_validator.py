"""MDL writer/readback verification for local Aurora animation overrides."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.core.animation.animation_engine import (
    AuroraTransform,
    evaluate_aurora_animation_pose,
)
from src.core.game.kotor_loader import load_model_from_file
from src.core.geometry.model_data import Animation, GameVersion, KotorModel, ModelNode


class AnimationRoundTripValidationError(ValueError):
    """Raised when a written MDL animation override fails readback verification."""


@dataclass(frozen=True)
class AnimationRoundTripIssue:
    """One readback mismatch found at the MDL writer boundary."""

    message: str
    node_name: str = ""
    time: Optional[float] = None


@dataclass
class AnimationRoundTripReport:
    """Readback verification result for one written local animation override."""

    success: bool = True
    issues: List[AnimationRoundTripIssue] = field(default_factory=list)
    warnings: List[AnimationRoundTripIssue] = field(default_factory=list)
    readback_model: Optional[KotorModel] = None
    readback_animation: Optional[Animation] = None

    def add_error(self, message: str, *, node_name: str = "", time: Optional[float] = None) -> None:
        self.success = False
        self.issues.append(AnimationRoundTripIssue(message=message, node_name=node_name, time=time))

    def add_warning(self, message: str, *, node_name: str = "", time: Optional[float] = None) -> None:
        self.warnings.append(AnimationRoundTripIssue(message=message, node_name=node_name, time=time))

    def raise_for_errors(self, slot_name: str) -> None:
        """Raise a concise user-facing readback verification failure."""

        if self.success:
            return
        details = "; ".join(issue.message for issue in self.issues[:5])
        if len(self.issues) > 5:
            details += f"; ... and {len(self.issues) - 5} more"
        raise AnimationRoundTripValidationError(
            f"Exported animation override '{slot_name}' failed MDL readback verification: "
            f"{details}. This usually indicates quaternion order, controller serialization, "
            "or MDL writer corruption."
        )


def quaternion_angular_difference_degrees(
    q_a: Sequence[float],
    q_b: Sequence[float],
) -> float:
    """Return angular distance between XYZW quaternions, treating q and -q as equal."""

    a = _normalize_quat(q_a)
    b = _normalize_quat(q_b)
    dot_value = abs(sum(x * y for x, y in zip(a, b)))
    dot_value = max(-1.0, min(1.0, dot_value))
    return math.degrees(2.0 * math.acos(dot_value))


def verify_written_animation_override_roundtrip(
    *,
    original_model: KotorModel,
    prepared_animation: Animation,
    written_mdl_path: Path,
    written_mdx_path: Path,
    slot_name: str,
    sample_times: Optional[List[float]] = None,
    tolerance: float = 1e-4,
    game_version: Optional[GameVersion] = None,
) -> AnimationRoundTripReport:
    """Read a written MDL/MDX back and compare the local override semantically."""

    report = AnimationRoundTripReport()
    written_mdl = Path(written_mdl_path)
    written_mdx = Path(written_mdx_path)
    readback_model = load_model_from_file(
        str(written_mdl),
        str(written_mdx) if written_mdx.exists() else "",
        game_version,
    )
    report.readback_model = readback_model
    if readback_model is None:
        report.add_error(f"could not load written MDL '{written_mdl}'")
        return report

    _compare_model_structure(report, original_model, readback_model, tolerance=tolerance)

    readback_animation = _find_animation(readback_model, slot_name)
    report.readback_animation = readback_animation
    if readback_animation is None:
        report.add_error(f"local animation '{slot_name}' is missing after readback")
        return report

    if str(readback_animation.name or "").lower() != str(slot_name or "").lower():
        report.add_error(
            f"readback animation name '{readback_animation.name}' does not match requested slot '{slot_name}'"
        )

    _compare_animation_metadata(report, prepared_animation, readback_animation, tolerance=tolerance)
    _compare_animation_controllers(report, prepared_animation, readback_animation, tolerance=tolerance)
    _compare_evaluated_poses(
        report,
        original_model,
        prepared_animation,
        readback_model,
        readback_animation,
        sample_times=sample_times,
        tolerance=tolerance,
    )
    _compare_mdx_bytes_if_available(report, original_model, written_mdx)
    return report


def _find_animation(model: KotorModel, slot_name: str) -> Optional[Animation]:
    wanted = str(slot_name or "").lower()
    for anim in getattr(model, "animations", []) or []:
        if str(anim.name or "").lower() == wanted:
            return anim
    return None


def _normalize_quat(values: Sequence[float]) -> Tuple[float, float, float, float]:
    x, y, z, w = (float(values[0]), float(values[1]), float(values[2]), float(values[3]))
    mag_sq = x * x + y * y + z * z + w * w
    if mag_sq <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    mag = math.sqrt(mag_sq)
    return (x / mag, y / mag, z / mag, w / mag)


def _controller_key(ctrl: Dict[str, Any]) -> Tuple[int, str]:
    return (int(ctrl.get("type", 0) or 0), str(ctrl.get("name", "") or "").lower())


def _node_map(animation: Animation) -> Dict[str, ModelNode]:
    return {
        str(node.name or "").lower(): node
        for node in getattr(animation, "nodes", []) or []
        if str(node.name or "").strip()
    }


def _controller_map(node: ModelNode) -> Dict[Tuple[int, str], Dict[str, Any]]:
    return {_controller_key(ctrl): ctrl for ctrl in getattr(node, "controllers", []) or []}


def _float_close(a: float, b: float, tolerance: float) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def _vec_close(a: Iterable[float], b: Iterable[float], tolerance: float) -> bool:
    return all(_float_close(x, y, tolerance) for x, y in zip(a, b))


def _compare_model_structure(
    report: AnimationRoundTripReport,
    original: KotorModel,
    readback: KotorModel,
    *,
    tolerance: float,
) -> None:
    original_nodes = original.all_nodes()
    readback_nodes = readback.all_nodes()
    if len(original_nodes) != len(readback_nodes):
        report.add_error(f"node count changed: {len(original_nodes)} -> {len(readback_nodes)}")
        return

    for index, (orig_node, read_node) in enumerate(zip(original_nodes, readback_nodes)):
        if str(orig_node.name or "").lower() != str(read_node.name or "").lower():
            report.add_error(
                f"node order/name changed at index {index}: '{orig_node.name}' -> '{read_node.name}'",
                node_name=read_node.name,
            )
        elif orig_node.name != read_node.name:
            report.add_warning(
                f"node name casing normalized at index {index}: '{orig_node.name}' -> '{read_node.name}'",
                node_name=read_node.name,
            )
        orig_parent = orig_node.parent.name if orig_node.parent is not None else None
        read_parent = read_node.parent.name if read_node.parent is not None else None
        if str(orig_parent or "").lower() != str(read_parent or "").lower():
            report.add_error(
                f"parent changed for node '{orig_node.name}': {orig_parent!r} -> {read_parent!r}",
                node_name=orig_node.name,
            )
        elif orig_parent != read_parent:
            report.add_warning(
                f"parent name casing normalized for node '{orig_node.name}': {orig_parent!r} -> {read_parent!r}",
                node_name=orig_node.name,
            )
        if not _vec_close(orig_node.position, read_node.position, tolerance):
            report.add_error(
                f"rest position changed for node '{orig_node.name}'",
                node_name=orig_node.name,
            )
        if quaternion_angular_difference_degrees(orig_node.rotation, read_node.rotation) > max(tolerance, 1e-3):
            report.add_error(
                f"rest rotation changed for node '{orig_node.name}'",
                node_name=orig_node.name,
            )
        if len(orig_node.vertices) != len(read_node.vertices):
            report.add_error(
                f"vertex count changed for node '{orig_node.name}': {len(orig_node.vertices)} -> {len(read_node.vertices)}",
                node_name=orig_node.name,
            )
        if len(orig_node.faces) != len(read_node.faces):
            report.add_error(
                f"face count changed for node '{orig_node.name}': {len(orig_node.faces)} -> {len(read_node.faces)}",
                node_name=orig_node.name,
            )

    for node in readback_nodes:
        if str(node.name or "").startswith("UE_"):
            report.add_error(f"UE skeleton node leaked into written model: '{node.name}'", node_name=node.name)


def _compare_animation_metadata(
    report: AnimationRoundTripReport,
    expected: Animation,
    readback: Animation,
    *,
    tolerance: float,
) -> None:
    if str(expected.name or "").lower() != str(readback.name or "").lower():
        report.add_error(f"animation name changed: '{expected.name}' -> '{readback.name}'")
    if not _float_close(expected.length or 0.0, readback.length or 0.0, tolerance):
        report.add_error(f"animation length changed: {expected.length} -> {readback.length}")
    if not _float_close(expected.transition_time or 0.0, readback.transition_time or 0.0, tolerance):
        report.add_error(
            f"transition time changed: {expected.transition_time} -> {readback.transition_time}"
        )
    if expected.anim_root and readback.anim_root and expected.anim_root.lower() != readback.anim_root.lower():
        report.add_error(f"animation root changed: '{expected.anim_root}' -> '{readback.anim_root}'")


def _compare_animation_controllers(
    report: AnimationRoundTripReport,
    expected: Animation,
    readback: Animation,
    *,
    tolerance: float,
) -> None:
    readback_nodes = _node_map(readback)
    for expected_node in getattr(expected, "nodes", []) or []:
        read_node = readback_nodes.get(str(expected_node.name or "").lower())
        if read_node is None:
            report.add_error(f"animation node '{expected_node.name}' missing after readback", node_name=expected_node.name)
            continue
        read_controllers = _controller_map(read_node)
        for expected_ctrl in getattr(expected_node, "controllers", []) or []:
            key = _controller_key(expected_ctrl)
            read_ctrl = read_controllers.get(key)
            if read_ctrl is None:
                report.add_error(
                    f"controller '{expected_ctrl.get('name', key[0])}' missing on node '{expected_node.name}'",
                    node_name=expected_node.name,
                )
                continue
            _compare_controller(report, expected_node.name, expected_ctrl, read_ctrl, tolerance=tolerance)


def _compare_controller(
    report: AnimationRoundTripReport,
    node_name: str,
    expected: Dict[str, Any],
    readback: Dict[str, Any],
    *,
    tolerance: float,
) -> None:
    expected_times = [float(value) for value in expected.get("times", []) or []]
    read_times = [float(value) for value in readback.get("times", []) or []]
    if len(expected_times) != len(read_times):
        report.add_error(
            f"controller '{expected.get('name')}' on node '{node_name}' key count changed: {len(expected_times)} -> {len(read_times)}",
            node_name=node_name,
        )
        return
    for index, (expected_time, read_time) in enumerate(zip(expected_times, read_times)):
        if not _float_close(expected_time, read_time, tolerance):
            report.add_error(
                f"node '{node_name}' key {index} time changed: {expected_time} -> {read_time}",
                node_name=node_name,
                time=read_time,
            )

    expected_values = list(expected.get("values", []) or [])
    read_values = list(readback.get("values", []) or [])
    if len(expected_values) != len(read_values):
        report.add_error(
            f"controller '{expected.get('name')}' on node '{node_name}' value count changed: {len(expected_values)} -> {len(read_values)}",
            node_name=node_name,
        )
        return

    is_orientation = int(expected.get("type", 0) or 0) == 20 or str(expected.get("name", "")).lower() == "orientation"
    for index, (expected_row, read_row) in enumerate(zip(expected_values, read_values)):
        if is_orientation:
            angle = quaternion_angular_difference_degrees(expected_row[:4], read_row[:4])
            if angle > max(tolerance, 1e-3):
                key_time = read_times[index] if index < len(read_times) else None
                report.add_error(
                    f"node '{node_name}' orientation at t={key_time:.3f} differs by {angle:.4f} degrees",
                    node_name=node_name,
                    time=key_time,
                )
        else:
            columns = int(expected.get("columns", len(expected_row)) or len(expected_row))
            if not _vec_close(expected_row[:columns], read_row[:columns], tolerance):
                key_time = read_times[index] if index < len(read_times) else None
                report.add_error(
                    f"node '{node_name}' controller '{expected.get('name')}' value at t={key_time:.3f} changed",
                    node_name=node_name,
                    time=key_time,
                )


def _sample_times_for(animation: Animation, sample_times: Optional[List[float]]) -> List[float]:
    if sample_times:
        return sorted(set(float(value) for value in sample_times))
    length = max(0.0, float(animation.length or 0.0))
    if length <= 0.0:
        return [0.0]
    return sorted({0.0, length * 0.25, length * 0.5, length * 0.75, length})


def _compare_evaluated_poses(
    report: AnimationRoundTripReport,
    original_model: KotorModel,
    expected_animation: Animation,
    readback_model: KotorModel,
    readback_animation: Animation,
    *,
    sample_times: Optional[List[float]],
    tolerance: float,
) -> None:
    for time_value in _sample_times_for(expected_animation, sample_times):
        expected_pose = evaluate_aurora_animation_pose(original_model, expected_animation, time_value)
        readback_pose = evaluate_aurora_animation_pose(readback_model, readback_animation, time_value)
        read_local_by_lower = {
            str(name or "").lower(): transform
            for name, transform in readback_pose.local_transforms_by_node.items()
        }
        read_world_by_lower = {
            str(name or "").lower(): transform
            for name, transform in readback_pose.world_transforms_by_node.items()
        }
        for node_name, expected_local in expected_pose.local_transforms_by_node.items():
            read_key = str(node_name or "").lower()
            read_local = read_local_by_lower.get(read_key)
            read_world = read_world_by_lower.get(read_key)
            expected_world = expected_pose.world_transforms_by_node[node_name]
            if read_local is None or read_world is None:
                report.add_error(f"node '{node_name}' missing from evaluated readback pose", node_name=node_name, time=time_value)
                continue
            _compare_transform(report, node_name, time_value, "local", expected_local, read_local, tolerance)
            _compare_transform(report, node_name, time_value, "world", expected_world, read_world, tolerance)


def _compare_transform(
    report: AnimationRoundTripReport,
    node_name: str,
    time_value: float,
    label: str,
    expected: AuroraTransform,
    readback: AuroraTransform,
    tolerance: float,
) -> None:
    if not _vec_close(expected.position, readback.position, tolerance):
        report.add_error(
            f"node '{node_name}' {label} position at t={time_value:.3f} changed",
            node_name=node_name,
            time=time_value,
        )
    angle = quaternion_angular_difference_degrees(expected.rotation, readback.rotation)
    if angle > max(tolerance, 1e-3):
        report.add_error(
            f"node '{node_name}' {label} rotation at t={time_value:.3f} differs by {angle:.4f} degrees",
            node_name=node_name,
            time=time_value,
        )


def _compare_mdx_bytes_if_available(
    report: AnimationRoundTripReport,
    original_model: KotorModel,
    written_mdx_path: Path,
) -> None:
    original_mdx_raw = str(getattr(original_model, "mdx_path", "") or "")
    if not original_mdx_raw:
        report.add_warning("MDX byte-for-byte preservation could not be checked")
        return
    original_mdx_path = Path(original_mdx_raw)
    if (
        not original_mdx_path.exists()
        or not original_mdx_path.is_file()
        or not Path(written_mdx_path).exists()
        or not Path(written_mdx_path).is_file()
    ):
        report.add_warning("MDX byte-for-byte preservation could not be checked")
        return
    original_bytes = original_mdx_path.read_bytes()
    written_bytes = Path(written_mdx_path).read_bytes()
    if original_bytes != written_bytes:
        report.add_warning(
            "MDX bytes changed during animation-only export; semantic geometry checks passed, "
            "but byte-for-byte MDX preservation remains preferred"
        )
