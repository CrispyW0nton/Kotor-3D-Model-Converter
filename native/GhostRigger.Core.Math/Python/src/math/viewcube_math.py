"""ViewCube orientation mapping and hit-test helpers.

GhostRigger's viewport camera is Z-up.  KotOR actors face +Y, so the canonical
Front view keeps the camera on +Y and looks back toward the scene target.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable


class ViewAction(str, Enum):
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    PERSPECTIVE = "perspective"
    HOME = "home"


@dataclass(frozen=True)
class ViewCubeRegion:
    kind: str
    key: str
    direction: tuple[float, float, float]
    action: ViewAction | None = None
    label: str = ""


FACE_DIRECTIONS: dict[ViewAction, tuple[float, float, float]] = {
    ViewAction.FRONT: (0.0, 1.0, 0.0),
    ViewAction.BACK: (0.0, -1.0, 0.0),
    ViewAction.LEFT: (-1.0, 0.0, 0.0),
    ViewAction.RIGHT: (1.0, 0.0, 0.0),
    ViewAction.TOP: (0.0, 0.0, 1.0),
    ViewAction.BOTTOM: (0.0, 0.0, -1.0),
}

FACE_LABELS: dict[ViewAction, str] = {
    ViewAction.FRONT: "FRONT",
    ViewAction.BACK: "BACK",
    ViewAction.LEFT: "LEFT",
    ViewAction.RIGHT: "RIGHT",
    ViewAction.TOP: "TOP",
    ViewAction.BOTTOM: "BOTTOM",
}

SNAP_VIEW_PRESETS: dict[str, tuple[float, float]] = {
    ViewAction.FRONT.value: (90.0, 0.0),
    ViewAction.BACK.value: (270.0, 0.0),
    ViewAction.LEFT.value: (180.0, 0.0),
    ViewAction.RIGHT.value: (0.0, 0.0),
    ViewAction.TOP.value: (90.0, 85.0),
    ViewAction.BOTTOM.value: (90.0, -85.0),
}


CUBE_VERTICES: dict[tuple[int, int, int], tuple[float, float, float]] = {
    (x, y, z): (float(x), float(y), float(z))
    for x in (-1, 1)
    for y in (-1, 1)
    for z in (-1, 1)
}

FACE_VERTEX_KEYS: dict[ViewAction, tuple[tuple[int, int, int], ...]] = {
    ViewAction.FRONT: ((-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)),
    ViewAction.BACK: ((1, -1, -1), (-1, -1, -1), (-1, -1, 1), (1, -1, 1)),
    ViewAction.LEFT: ((-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)),
    ViewAction.RIGHT: ((1, 1, -1), (1, -1, -1), (1, -1, 1), (1, 1, 1)),
    ViewAction.TOP: ((-1, 1, 1), (1, 1, 1), (1, -1, 1), (-1, -1, 1)),
    ViewAction.BOTTOM: ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)),
}


def _normalize(v: Iterable[float]) -> tuple[float, float, float]:
    x, y, z = (float(c) for c in v)
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-9:
        return (0.0, 1.0, 0.0)
    return (x / length, y / length, z / length)


def _cross(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def azimuth_elevation_from_direction(direction: Iterable[float]) -> tuple[float, float]:
    """Convert a camera eye direction into GhostRigger azimuth/elevation."""

    x, y, z = _normalize(direction)
    azimuth = math.degrees(math.atan2(y, x)) % 360.0
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    return azimuth, max(-85.0, min(85.0, elevation))


def action_from_view_name(view: str) -> ViewAction | None:
    key = str(view or "").strip().lower()
    aliases = {
        "f": "front",
        "front": "front",
        "b": "back",
        "back": "back",
        "l": "left",
        "left": "left",
        "r": "right",
        "right": "right",
        "t": "top",
        "top": "top",
        "bo": "bottom",
        "bottom": "bottom",
        "persp": "perspective",
        "perspective": "perspective",
        "home": "home",
    }
    value = aliases.get(key, key)
    try:
        return ViewAction(value)
    except ValueError:
        return None


def target_for_action(action: ViewAction) -> tuple[float, float] | None:
    preset = SNAP_VIEW_PRESETS.get(action.value)
    if preset is None:
        return None
    return preset


def target_for_region(region: ViewCubeRegion) -> tuple[float, float] | None:
    if region.action is not None and region.action in FACE_DIRECTIONS:
        return target_for_action(region.action)
    if region.kind in {"edge", "corner"}:
        return azimuth_elevation_from_direction(region.direction)
    return None


def view_direction_from_angles(azimuth: float, elevation: float) -> tuple[float, float, float]:
    """Return the target-to-eye direction for the existing arcball camera."""

    az = math.radians(float(azimuth))
    el = math.radians(float(elevation))
    ce = math.cos(el)
    return _normalize((ce * math.cos(az), ce * math.sin(az), math.sin(el)))


def camera_basis_from_angles(
    azimuth: float,
    elevation: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return right/up/forward basis matching ``ArcBallCamera._view_matrix``."""

    eye_dir = view_direction_from_angles(azimuth, elevation)
    fwd = (-eye_dir[0], -eye_dir[1], -eye_dir[2])
    world_up = (0.0, 0.0, 1.0)
    right = _normalize(_cross(fwd, world_up))
    if _dot(right, right) < 1e-6:
        right = _normalize(_cross(fwd, (0.0, 1.0, 0.0)))
    up = _cross(right, fwd)
    return right, up, fwd


def view_orientation_quaternion(azimuth: float, elevation: float) -> tuple[float, float, float, float]:
    """Return a quaternion for the current view direction.

    The viewport camera itself stores azimuth/elevation, so this helper is
    mainly for extension points such as future compass rings or roll controls.
    """

    base = (0.0, 1.0, 0.0)
    target = view_direction_from_angles(azimuth, elevation)
    dot = max(-1.0, min(1.0, _dot(base, target)))
    if dot > 0.999999:
        return (0.0, 0.0, 0.0, 1.0)
    if dot < -0.999999:
        return (0.0, 0.0, 1.0, 0.0)
    axis = _cross(base, target)
    quat = (axis[0], axis[1], axis[2], 1.0 + dot)
    length = math.sqrt(sum(component * component for component in quat))
    return tuple(component / length for component in quat)  # type: ignore[return-value]
