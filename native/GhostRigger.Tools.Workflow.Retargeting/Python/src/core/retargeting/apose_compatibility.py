"""A-pose compatibility checks for reverse UE5 -> Aurora retargeting."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import math


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def _normalize_quat(quat: Sequence[float]) -> tuple[float, float, float, float]:
    if len(quat) != 4:
        raise ValueError(f"Quaternion must have 4 components, got {len(quat)}")
    values = tuple(float(component) for component in quat)
    length = math.sqrt(sum(component * component for component in values))
    if not math.isfinite(length) or length <= 0.0:
        raise ValueError(f"Invalid quaternion length: {length}")
    return tuple(component / length for component in values)  # type: ignore[return-value]


def quaternion_angular_delta_degrees(
    source_wxyz: Sequence[float],
    target_wxyz: Sequence[float],
) -> float:
    """Return the shortest angular difference between two WXYZ quaternions."""

    source = _normalize_quat(source_wxyz)
    target = _normalize_quat(target_wxyz)
    dot = abs(sum(a * b for a, b in zip(source, target, strict=True)))
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


@dataclass(frozen=True)
class APoseBoneDelta:
    source_bone: str
    target_bone: str
    angular_delta_degrees: float
    within_tolerance: bool


@dataclass(frozen=True)
class APoseCompatibilityReport:
    compatible: bool
    tolerance_degrees: float
    max_delta_degrees: float
    bone_deltas: list[APoseBoneDelta]
    missing_source_bones: list[str]
    missing_target_bones: list[str]

    def failing_bones(self) -> list[APoseBoneDelta]:
        return [delta for delta in self.bone_deltas if not delta.within_tolerance]


def validate_apose_compatibility(
    source_world_rotations_wxyz: Mapping[str, Sequence[float]],
    target_world_rotations_wxyz: Mapping[str, Sequence[float]],
    rename_pairs: Mapping[str, str],
    *,
    tolerance_degrees: float = 15.0,
) -> APoseCompatibilityReport:
    """Compare mapped source/target rest-pose world rotations."""

    source = {_key(name): value for name, value in source_world_rotations_wxyz.items()}
    target = {_key(name): value for name, value in target_world_rotations_wxyz.items()}

    bone_deltas: list[APoseBoneDelta] = []
    missing_source: list[str] = []
    missing_target: list[str] = []
    for source_bone, target_bone in sorted((_key(src), _key(dst)) for src, dst in rename_pairs.items()):
        if source_bone not in source:
            missing_source.append(source_bone)
            continue
        if target_bone not in target:
            missing_target.append(target_bone)
            continue
        delta = quaternion_angular_delta_degrees(source[source_bone], target[target_bone])
        bone_deltas.append(
            APoseBoneDelta(
                source_bone=source_bone,
                target_bone=target_bone,
                angular_delta_degrees=delta,
                within_tolerance=delta <= tolerance_degrees,
            )
        )

    max_delta = max((delta.angular_delta_degrees for delta in bone_deltas), default=0.0)
    compatible = not missing_source and not missing_target and all(delta.within_tolerance for delta in bone_deltas)
    return APoseCompatibilityReport(
        compatible=compatible,
        tolerance_degrees=tolerance_degrees,
        max_delta_degrees=max_delta,
        bone_deltas=bone_deltas,
        missing_source_bones=missing_source,
        missing_target_bones=missing_target,
    )


def rotations_from_rest_pose_bones(
    bones: Iterable[Mapping[str, object]],
    *,
    field: str = "world_rotation_wxyz",
) -> dict[str, tuple[float, float, float, float]]:
    """Extract named WXYZ rotations from existing rest-pose capture JSON."""

    rotations: dict[str, tuple[float, float, float, float]] = {}
    for bone in bones:
        name = _key(str(bone.get("key") or bone.get("name") or ""))
        value = bone.get(field)
        if not name or not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            continue
        rotations[name] = _normalize_quat(value)  # type: ignore[arg-type]
    return rotations
