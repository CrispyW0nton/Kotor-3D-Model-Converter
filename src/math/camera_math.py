"""Shared camera math for GhostRigger cinematic cameras."""

from __future__ import annotations

import math
from typing import Iterable

Vec3 = tuple[float, float, float]
Quat = tuple[float, float, float, float]


def vec3(value: object, fallback: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
        return fallback


def quat(value: object, fallback: Quat = (0.0, 0.0, 0.0, 1.0)) -> Quat:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return normalize_quat((float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3])))
    except Exception:
        return fallback


def clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def normalize(value: Iterable[float]) -> Vec3:
    x, y, z = vec3(value)
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-9 or not math.isfinite(length):
        return (0.0, 0.0, 0.0)
    return (x / length, y / length, z / length)


def cross(a: Iterable[float], b: Iterable[float]) -> Vec3:
    ax, ay, az = vec3(a)
    bx, by, bz = vec3(b)
    return (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)


def dot(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay, az = vec3(a)
    bx, by, bz = vec3(b)
    return ax * bx + ay * by + az * bz


def add(a: Iterable[float], b: Iterable[float]) -> Vec3:
    ax, ay, az = vec3(a)
    bx, by, bz = vec3(b)
    return (ax + bx, ay + by, az + bz)


def sub(a: Iterable[float], b: Iterable[float]) -> Vec3:
    ax, ay, az = vec3(a)
    bx, by, bz = vec3(b)
    return (ax - bx, ay - by, az - bz)


def mul(v: Iterable[float], scalar: float) -> Vec3:
    x, y, z = vec3(v)
    return (x * float(scalar), y * float(scalar), z * float(scalar))


def length(v: Iterable[float]) -> float:
    x, y, z = vec3(v)
    return math.sqrt(x * x + y * y + z * z)


def normalize_quat(q: Quat) -> Quat:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n <= 1e-9 or not math.isfinite(n):
        return (0.0, 0.0, 0.0, 1.0)
    return (x / n, y / n, z / n, w / n)


def multiply_quat(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return normalize_quat(
        (
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )
    )


def quat_to_euler_degrees(q: object) -> Vec3:
    try:
        x, y, z, w = [float(v) for v in list(q)[:4]]  # type: ignore[arg-type]
    except Exception:
        return (0.0, 0.0, 0.0)
    x, y, z, w = normalize_quat((x, y, z, w))
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


def euler_degrees_to_quat(euler: object) -> Quat:
    try:
        rx, ry, rz = (math.radians(float(v)) for v in list(euler)[:3])  # type: ignore[arg-type]
    except Exception:
        return (0.0, 0.0, 0.0, 1.0)

    def axis_quat(axis: str, angle: float) -> Quat:
        half = angle * 0.5
        s = math.sin(half)
        c = math.cos(half)
        if axis == "X":
            return (s, 0.0, 0.0, c)
        if axis == "Y":
            return (0.0, s, 0.0, c)
        return (0.0, 0.0, s, c)

    return multiply_quat(
        axis_quat("Z", rz),
        multiply_quat(axis_quat("Y", ry), axis_quat("X", rx)),
    )


def rotate_vector(q: Quat, v: Iterable[float]) -> Vec3:
    x, y, z = vec3(v)
    qx, qy, qz, qw = normalize_quat(q)
    # Quaternion-vector multiply expanded for speed and to avoid dependencies.
    tx = 2.0 * (qy * z - qz * y)
    ty = 2.0 * (qz * x - qx * z)
    tz = 2.0 * (qx * y - qy * x)
    return (
        x + qw * tx + (qy * tz - qz * ty),
        y + qw * ty + (qz * tx - qx * tz),
        z + qw * tz + (qx * ty - qy * tx),
    )


def quaternion_from_basis(right: Vec3, up: Vec3, forward: Vec3) -> Quat:
    # Local camera axes are +X right, +Y up, -Z forward.
    r = normalize(right)
    u = normalize(up)
    b = normalize(mul(forward, -1.0))
    m00, m01, m02 = r[0], u[0], b[0]
    m10, m11, m12 = r[1], u[1], b[1]
    m20, m21, m22 = r[2], u[2], b[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return normalize_quat(((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s))
    if m00 > m11 and m00 > m22:
        s = math.sqrt(max(0.0, 1.0 + m00 - m11 - m22)) * 2.0
        return normalize_quat((0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s))
    if m11 > m22:
        s = math.sqrt(max(0.0, 1.0 + m11 - m00 - m22)) * 2.0
        return normalize_quat(((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s))
    s = math.sqrt(max(0.0, 1.0 + m22 - m00 - m11)) * 2.0
    return normalize_quat(((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s))


def look_at_quaternion(position: Iterable[float], target: Iterable[float]) -> Quat:
    forward = normalize(sub(target, position))
    if length(forward) <= 1e-9:
        return (0.0, 0.0, 0.0, 1.0)
    world_up = (0.0, 0.0, 1.0)
    right = normalize(cross(forward, world_up))
    if length(right) <= 1e-9:
        right = normalize(cross(forward, (0.0, 1.0, 0.0)))
    up = normalize(cross(right, forward))
    return quaternion_from_basis(right, up, forward)


def camera_forward(q: Quat) -> Vec3:
    return normalize(rotate_vector(q, (0.0, 0.0, -1.0)))


def focal_length_to_fov(sensor_width_mm: float, focal_length_mm: float) -> float:
    sensor = max(0.001, float(sensor_width_mm))
    focal = max(0.001, float(focal_length_mm))
    return math.degrees(2.0 * math.atan(sensor / (2.0 * focal)))


def fov_to_focal_length(sensor_width_mm: float, fov_degrees: float) -> float:
    sensor = max(0.001, float(sensor_width_mm))
    fov = math.radians(clamp(float(fov_degrees), 1.0, 179.0))
    return sensor / (2.0 * math.tan(fov * 0.5))
