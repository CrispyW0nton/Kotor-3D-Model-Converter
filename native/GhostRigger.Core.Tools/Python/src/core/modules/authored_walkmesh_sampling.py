"""Triangle sampling helpers for authored Map Studio WOK checks."""

from __future__ import annotations

import math
from typing import Any


Vec3 = tuple[float, float, float]
POINT_IN_TRIANGLE_EPSILON = 1.0e-7


def _face_indices(face: Any) -> tuple[int, int, int]:
    return int(getattr(face, "v1", -1)), int(getattr(face, "v2", -1)), int(getattr(face, "v3", -1))


def _vertex3(value: Any) -> Vec3:
    return (float(value[0]), float(value[1]), float(value[2]))


def _orient2d(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> float:
    return ((bx - ax) * (py - ay)) - ((by - ay) * (px - ax))


def _point_in_triangle_xy(point: tuple[float, float], a: Vec3, b: Vec3, c: Vec3, *, epsilon: float) -> bool:
    px, py = point
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    area = _orient2d(ax, ay, bx, by, cx, cy)
    if abs(area) <= float(epsilon):
        return False
    d1 = _orient2d(ax, ay, bx, by, px, py)
    d2 = _orient2d(bx, by, cx, cy, px, py)
    d3 = _orient2d(cx, cy, ax, ay, px, py)
    has_negative = d1 < -epsilon or d2 < -epsilon or d3 < -epsilon
    has_positive = d1 > epsilon or d2 > epsilon or d3 > epsilon
    return not (has_negative and has_positive)


def _face_contains_xy(verts: list[Any], face: Any, x: float, y: float, *, epsilon: float) -> bool:
    indices = _face_indices(face)
    if any(index < 0 or index >= len(verts) for index in indices):
        return False
    try:
        a = _vertex3(verts[indices[0]])
        b = _vertex3(verts[indices[1]])
        c = _vertex3(verts[indices[2]])
    except (TypeError, ValueError, IndexError):
        return False
    return _point_in_triangle_xy((float(x), float(y)), a, b, c, epsilon=epsilon)


def walkmesh_face_at_xy(
    wok: Any,
    x: float,
    y: float,
    *,
    epsilon: float = POINT_IN_TRIANGLE_EPSILON,
) -> int:
    """Return the WOK face containing an XY point, using vertices/faces when needed."""

    if not (math.isfinite(float(x)) and math.isfinite(float(y))):
        return -1

    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    face_at_point = getattr(wok, "face_at_point", None)
    if callable(face_at_point):
        try:
            face_index = int(face_at_point(float(x), float(y)))
        except (TypeError, ValueError):
            face_index = -1
        if face_index >= 0:
            if not faces or face_index >= len(faces) or _face_contains_xy(verts, faces[face_index], float(x), float(y), epsilon=epsilon):
                return face_index

    if not faces or not verts:
        return -2
    for face_index, face in enumerate(faces):
        if _face_contains_xy(verts, face, float(x), float(y), epsilon=epsilon):
            return face_index
    return -1


def walkmesh_floor_z_at_xy(wok: Any, face_index: int, x: float, y: float) -> float | None:
    """Return the WOK triangle plane Z under an XY point."""

    faces = list(getattr(wok, "faces", ()) or ())
    verts = list(getattr(wok, "verts", ()) or ())
    if face_index < 0 or face_index >= len(faces):
        return None
    indices = _face_indices(faces[face_index])
    if any(index < 0 or index >= len(verts) for index in indices):
        return None
    try:
        a = _vertex3(verts[indices[0]])
        b = _vertex3(verts[indices[1]])
        c = _vertex3(verts[indices[2]])
    except (TypeError, ValueError, IndexError):
        return None
    ax, ay, az = a
    bx, by, bz = b
    cx, cy, cz = c
    denominator = ((by - cy) * (ax - cx)) + ((cx - bx) * (ay - cy))
    if abs(denominator) <= POINT_IN_TRIANGLE_EPSILON:
        return (az + bz + cz) / 3.0
    w_a = (((by - cy) * (float(x) - cx)) + ((cx - bx) * (float(y) - cy))) / denominator
    w_b = (((cy - ay) * (float(x) - cx)) + ((ax - cx) * (float(y) - cy))) / denominator
    w_c = 1.0 - w_a - w_b
    return (w_a * az) + (w_b * bz) + (w_c * cz)


__all__ = [
    "POINT_IN_TRIANGLE_EPSILON",
    "walkmesh_face_at_xy",
    "walkmesh_floor_z_at_xy",
]
