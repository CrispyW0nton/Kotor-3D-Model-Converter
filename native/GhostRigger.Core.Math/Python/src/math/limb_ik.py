"""Pure analytic position solving for a two-segment limb."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class TwoBoneIKResult:
    """Solved joint positions in the same space as the input points.

    ``target_position`` is the requested target when it is reachable.  For an
    overextended or overfolded chain it is the closest reachable point along a
    deterministic shoulder-to-target direction.  ``residual`` is the distance
    between that adjusted point and the requested target.
    """

    elbow_position: Vec3
    target_position: Vec3
    reached: bool
    residual: float


def solve_two_bone_positions(
    shoulder_position: Iterable[float],
    elbow_position: Iterable[float],
    wrist_position: Iterable[float],
    target_position: Iterable[float],
    pole_position: Iterable[float],
    epsilon: float = 1e-6,
) -> TwoBoneIKResult:
    """Solve a shoulder/elbow/wrist chain for a position goal.

    All positions must use the same coordinate space.  The current pose defines
    the upper- and lower-segment lengths.  The pole selects the elbow side; if
    it lies on the shoulder-target axis, the current elbow side is preserved.
    Fully degenerate inputs fall back to a stable world-axis choice.
    """

    tolerance = float(epsilon)
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("epsilon must be a positive finite value")

    shoulder = _vec3(shoulder_position, "shoulder_position")
    current_elbow = _vec3(elbow_position, "elbow_position")
    current_wrist = _vec3(wrist_position, "wrist_position")
    requested_target = _vec3(target_position, "target_position")
    pole = _vec3(pole_position, "pole_position")

    upper_length = _length(_sub(current_elbow, shoulder))
    lower_length = _length(_sub(current_wrist, current_elbow))
    minimum_reach = abs(upper_length - lower_length)
    maximum_reach = upper_length + lower_length

    requested_delta = _sub(requested_target, shoulder)
    requested_distance = _length(requested_delta)
    aim_direction = _unit(requested_delta, tolerance)
    if aim_direction is None:
        aim_direction = _fallback_direction(
            (
                _sub(current_wrist, shoulder),
                _sub(current_elbow, shoulder),
                _sub(pole, shoulder),
            ),
            tolerance,
        )

    reachable_distance = min(max(requested_distance, minimum_reach), maximum_reach)
    adjusted_target = _add(shoulder, _scale(aim_direction, reachable_distance))
    residual = _length(_sub(adjusted_target, requested_target))

    if reachable_distance == 0.0:
        # The endpoint is exactly at the shoulder, which is possible only when
        # both segments have equal length.  The pole directly selects one of
        # the infinitely many valid elbow positions.
        elbow_direction = _fallback_direction(
            (
                _sub(pole, shoulder),
                _sub(current_elbow, shoulder),
                (1.0, 0.0, 0.0),
            ),
            tolerance,
        )
        solved_elbow = _add(shoulder, _scale(elbow_direction, upper_length))
    else:
        # Sphere intersection: the elbow lies on a circle whose center is
        # ``axis_distance`` along the shoulder-to-target axis.
        if upper_length == lower_length:
            axis_distance = reachable_distance * 0.5
        else:
            axis_distance = (
                upper_length * upper_length
                - lower_length * lower_length
                + reachable_distance * reachable_distance
            ) / (2.0 * reachable_distance)
        bend_height_sq = max(0.0, upper_length * upper_length - axis_distance * axis_distance)
        bend_height = math.sqrt(bend_height_sq)
        bend_direction = _bend_direction(
            aim_direction,
            _sub(pole, shoulder),
            _sub(current_elbow, shoulder),
            tolerance,
        )
        solved_elbow = _add(
            shoulder,
            _add(
                _scale(aim_direction, axis_distance),
                _scale(bend_direction, bend_height),
            ),
        )

    return TwoBoneIKResult(
        elbow_position=solved_elbow,
        target_position=adjusted_target,
        reached=residual <= tolerance,
        residual=residual,
    )


def _vec3(value: Iterable[float], name: str) -> Vec3:
    try:
        values = tuple(float(component) for component in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain three finite numbers") from exc
    if len(values) < 3:
        raise ValueError(f"{name} must contain three finite numbers")
    result = (values[0], values[1], values[2])
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{name} must contain three finite numbers")
    return result


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(value: Vec3, scalar: float) -> Vec3:
    return (value[0] * scalar, value[1] * scalar, value[2] * scalar)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(value: Vec3) -> float:
    return math.sqrt(_dot(value, value))


def _unit(value: Vec3, epsilon: float) -> Vec3 | None:
    magnitude = _length(value)
    if magnitude <= epsilon or not math.isfinite(magnitude):
        return None
    return _scale(value, 1.0 / magnitude)


def _fallback_direction(candidates: Iterable[Vec3], epsilon: float) -> Vec3:
    for candidate in candidates:
        direction = _unit(candidate, epsilon)
        if direction is not None:
            return direction
    return (1.0, 0.0, 0.0)


def _bend_direction(
    aim_direction: Vec3,
    pole_delta: Vec3,
    current_elbow_delta: Vec3,
    epsilon: float,
) -> Vec3:
    for candidate in (pole_delta, current_elbow_delta):
        projected = _sub(candidate, _scale(aim_direction, _dot(candidate, aim_direction)))
        direction = _unit(projected, epsilon)
        if direction is not None:
            return direction

    # Pick the cardinal axis least aligned with the aim.  Projecting it onto
    # the bend plane produces a deterministic perpendicular direction.
    cardinals: tuple[Vec3, ...] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    fallback = min(cardinals, key=lambda axis: abs(_dot(axis, aim_direction)))
    projected = _sub(fallback, _scale(aim_direction, _dot(fallback, aim_direction)))
    return _fallback_direction((projected,), epsilon)


__all__ = ["TwoBoneIKResult", "solve_two_bone_positions"]
