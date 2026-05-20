"""Reusable math helpers for the GhostRigger transform gizmo."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np

Vec3 = tuple[float, float, float]


AXIS_VECTORS: dict[str, Vec3] = {
    "X": (1.0, 0.0, 0.0),
    "Y": (0.0, 1.0, 0.0),
    "Z": (0.0, 0.0, 1.0),
}


def _as_vec3(value: Iterable[float]) -> np.ndarray:
    return np.asarray(tuple(value)[:3], dtype=np.float64)


def normalize(value: Iterable[float]) -> np.ndarray:
    vec = _as_vec3(value)
    length = float(np.linalg.norm(vec))
    if length <= 1e-9 or not math.isfinite(length):
        return np.zeros(3, dtype=np.float64)
    return vec / length


def ray_from_mouse(mouse_pos: tuple[int, int], camera, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """Build a world-space ray from a viewport pixel and the arcball camera."""
    sx, sy = float(mouse_pos[0]), float(mouse_pos[1])
    right, up, fwd, eye = camera._view_matrix()
    half_h = max(1.0, float(height)) * 0.5
    tan_half = math.tan(math.radians(float(camera.fov)) * 0.5)
    x_ndc = (sx - float(width) * 0.5) / half_h
    y_ndc = (float(height) * 0.5 - sy) / half_h
    direction = (
        _as_vec3(fwd)
        + _as_vec3(right) * (x_ndc * tan_half)
        + _as_vec3(up) * (y_ndc * tan_half)
    )
    return _as_vec3(eye), normalize(direction)


def closest_point_on_ray(origin: Iterable[float], direction: Iterable[float], point: Iterable[float]) -> np.ndarray:
    o = _as_vec3(origin)
    d = normalize(direction)
    p = _as_vec3(point)
    t = max(0.0, float(np.dot(p - o, d)))
    return o + d * t


def closest_point_between_rays(
    origin_a: Iterable[float],
    dir_a: Iterable[float],
    origin_b: Iterable[float],
    dir_b: Iterable[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return closest points on two rays, clamping ray parameters to >= 0."""
    p1 = _as_vec3(origin_a)
    d1 = normalize(dir_a)
    p2 = _as_vec3(origin_b)
    d2 = normalize(dir_b)
    r = p1 - p2
    a = float(np.dot(d1, d1))
    e = float(np.dot(d2, d2))
    b = float(np.dot(d1, d2))
    c = float(np.dot(d1, r))
    f = float(np.dot(d2, r))
    denom = a * e - b * b
    if abs(denom) <= 1e-9:
        s = 0.0
        t = max(0.0, f / max(e, 1e-9))
    else:
        s = max(0.0, (b * f - c * e) / denom)
        t = max(0.0, (a * f - b * c) / denom)
    return p1 + d1 * s, p2 + d2 * t


def project_point_to_screen(point: Iterable[float], projector, width: int, height: int):
    x, y, z = tuple(point)[:3]
    return projector(float(x), float(y), float(z), int(width), int(height))


def screen_space_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return math.sqrt(dx * dx + dy * dy)


def axis_drag_delta(
    start_mouse: tuple[int, int],
    mouse_pos: tuple[int, int],
    axis: str,
    camera,
    depth: float,
    viewport_height: int,
) -> float:
    """Convert a screen drag into signed motion along a world axis.

    The selected world axis is projected into the camera's screen basis, then
    the mouse delta is measured along that projected direction. This remains
    stable when the axis is shallow by falling back to horizontal mouse motion.
    """
    right, up, _fwd, _eye = camera._view_matrix()
    axis_vec = AXIS_VECTORS.get(axis, AXIS_VECTORS["X"])
    screen_x = float(np.dot(_as_vec3(axis_vec), _as_vec3(right)))
    screen_y = float(np.dot(_as_vec3(axis_vec), _as_vec3(up)))
    length = math.sqrt(screen_x * screen_x + screen_y * screen_y)
    if length <= 1e-5:
        screen_x, screen_y, length = 1.0, 0.0, 1.0
    dx = float(mouse_pos[0] - start_mouse[0])
    dy = float(mouse_pos[1] - start_mouse[1])
    pixel_delta = (dx * screen_x + (-dy) * screen_y) / length
    world_per_px = (2.0 * max(0.5, float(depth)) * math.tan(math.radians(float(camera.fov)) * 0.5)) / max(1, viewport_height)
    return pixel_delta * world_per_px


def rotation_angle_from_mouse_delta(
    start_mouse: tuple[int, int],
    mouse_pos: tuple[int, int],
    center_screen: tuple[float, float] | None = None,
) -> float:
    if center_screen is not None:
        cx, cy = center_screen
        a0 = math.atan2(float(start_mouse[1]) - cy, float(start_mouse[0]) - cx)
        a1 = math.atan2(float(mouse_pos[1]) - cy, float(mouse_pos[0]) - cx)
        delta = a1 - a0
        return (delta + math.pi) % (math.tau) - math.pi
    return float(mouse_pos[0] - start_mouse[0]) * 0.01


def axis_quaternion(axis: str, angle: float) -> tuple[float, float, float, float]:
    vec = AXIS_VECTORS.get(axis, AXIS_VECTORS["Z"])
    half = float(angle) * 0.5
    s = math.sin(half)
    return (vec[0] * s, vec[1] * s, vec[2] * s, math.cos(half))


def multiply_quaternions(a, b) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    result = (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )
    length = math.sqrt(sum(float(v) * float(v) for v in result))
    if length <= 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(float(v) / length for v in result)


def build_translation_matrix(delta: Iterable[float]) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, 3] = _as_vec3(delta)
    return matrix


def build_rotation_matrix(axis: str, angle: float) -> np.ndarray:
    x, y, z = AXIS_VECTORS.get(axis, AXIS_VECTORS["Z"])
    c = math.cos(float(angle))
    s = math.sin(float(angle))
    t = 1.0 - c
    return np.asarray(
        [
            [t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0.0],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0.0],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def build_scale_matrix(scale: Iterable[float] | float) -> np.ndarray:
    if isinstance(scale, (int, float)):
        sx = sy = sz = float(scale)
    else:
        sx, sy, sz = tuple(scale)[:3]
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 0] = float(sx)
    matrix[1, 1] = float(sy)
    matrix[2, 2] = float(sz)
    return matrix

