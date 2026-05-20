"""Non-mutating object dimension calculations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable


Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class ObjectDimensions:
    name: str
    position: Vec3
    rotation_degrees: Vec3
    scale: Vec3
    size: Vec3 | None
    bounds: tuple[Vec3, Vec3] | None


def _quat_to_euler_degrees(q) -> Vec3:
    try:
        x, y, z, w = [float(v) for v in q[:4]]
    except Exception:
        return (0.0, 0.0, 0.0)
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-9:
        return (0.0, 0.0, 0.0)
    x, y, z, w = x / length, y / length, z / length, w / length
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


class DimensionCalculator:
    """Calculate selected object size without mutating geometry."""

    def calculate(
        self,
        obj,
        *,
        world_vertices_provider: Callable[[object], Iterable[Vec3]] | None = None,
    ) -> ObjectDimensions:
        position = self._position(obj)
        rotation = _quat_to_euler_degrees(getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0)))
        raw_scale = getattr(obj, "_gr_scale", getattr(obj, "scale", (1.0, 1.0, 1.0)))
        if isinstance(raw_scale, (int, float)):
            scale = (float(raw_scale), float(raw_scale), float(raw_scale))
        else:
            scale_values = tuple(raw_scale)[:3]
            scale = tuple(float(v) for v in (scale_values + (1.0, 1.0, 1.0))[:3])
        bounds = self.bounds(obj, world_vertices_provider=world_vertices_provider)
        size = None
        if bounds is not None:
            size = tuple(max(0.0, bounds[1][i] - bounds[0][i]) for i in range(3))
        return ObjectDimensions(
            name=str(getattr(obj, "name", "") or "<unnamed>"),
            position=position,
            rotation_degrees=rotation,
            scale=scale,
            size=size,
            bounds=bounds,
        )

    def bounds(
        self,
        obj,
        *,
        world_vertices_provider: Callable[[object], Iterable[Vec3]] | None = None,
    ) -> tuple[Vec3, Vec3] | None:
        vertices = None
        if world_vertices_provider is not None:
            try:
                vertices = list(world_vertices_provider(obj))
            except Exception:
                vertices = None
        if vertices is None:
            vertices = list(getattr(obj, "vertices", []) or [])
        valid: list[Vec3] = []
        for vertex in vertices:
            try:
                x, y, z = float(vertex[0]), float(vertex[1]), float(vertex[2])
            except Exception:
                continue
            if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                valid.append((x, y, z))
        if not valid:
            return None
        return (
            tuple(min(point[i] for point in valid) for i in range(3)),
            tuple(max(point[i] for point in valid) for i in range(3)),
        )

    def _position(self, obj) -> Vec3:
        try:
            if hasattr(obj, "world_position"):
                return tuple(float(v) for v in obj.world_position()[:3])
        except Exception:
            pass
        return tuple(float(v) for v in getattr(obj, "position", (0.0, 0.0, 0.0))[:3])
