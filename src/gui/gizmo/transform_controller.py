"""Apply transform gizmo edits to GhostRigger scene objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .gizmo_mode import GizmoMode
from .transform_math import (
    AXIS_VECTORS,
    axis_drag_delta,
    axis_quaternion,
    multiply_quaternions,
    rotation_angle_from_mouse_delta,
)


@dataclass
class TransformSnapshot:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    vertices: tuple[tuple[float, float, float], ...] | None = None


class TransformController:
    """Small state machine that applies one active gizmo drag."""

    def __init__(self, invalidate_callback: Optional[Callable[[object], None]] = None):
        self.invalidate_callback = invalidate_callback
        self.object = None
        self.mode: GizmoMode | None = None
        self.handle = ""
        self.start_mouse = (0, 0)
        self.start_depth = 1.0
        self.center_screen: tuple[float, float] | None = None
        self.original: TransformSnapshot | None = None
        self.active = False

    def snapshot(self, obj) -> TransformSnapshot:
        vertices = getattr(obj, "vertices", None)
        vertex_snapshot = tuple(tuple(float(c) for c in v[:3]) for v in vertices) if vertices is not None else None
        return TransformSnapshot(
            position=tuple(float(v) for v in getattr(obj, "position", (0.0, 0.0, 0.0))),
            rotation=tuple(float(v) for v in getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
            vertices=vertex_snapshot,
        )

    def begin_drag(
        self,
        obj,
        mode: GizmoMode,
        handle: str,
        mouse_pos: tuple[int, int],
        camera,
        *,
        depth: float,
        center_screen: tuple[float, float] | None = None,
    ) -> None:
        self.object = obj
        self.mode = mode
        self.handle = str(handle)
        self.start_mouse = (int(mouse_pos[0]), int(mouse_pos[1]))
        self.start_depth = float(depth)
        self.center_screen = center_screen
        self.original = self.snapshot(obj)
        self.active = True

    def drag(self, mouse_pos: tuple[int, int], camera, viewport_height: int) -> None:
        if not self.active or self.object is None or self.original is None or self.mode is None:
            return
        axis = self.handle.rsplit("_", 1)[-1]
        if self.mode == GizmoMode.TRANSLATE:
            self._apply_translate(axis, mouse_pos, camera, viewport_height)
        elif self.mode == GizmoMode.ROTATE:
            self._apply_rotate(axis, mouse_pos)
        elif self.mode == GizmoMode.SCALE:
            self._apply_scale(axis, mouse_pos, camera, viewport_height)
        self._invalidate()

    def _apply_translate(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        delta = axis_drag_delta(self.start_mouse, mouse_pos, axis, camera, self.start_depth, viewport_height)
        av = AXIS_VECTORS.get(axis, AXIS_VECTORS["X"])
        p = self.original.position
        self.object.position = (
            p[0] + av[0] * delta,
            p[1] + av[1] * delta,
            p[2] + av[2] * delta,
        )

    def _apply_rotate(self, axis: str, mouse_pos) -> None:
        # Screen-space drag angles are clockwise-positive in Qt's y-down
        # coordinate system; world-space quaternion rotation expects the
        # opposite handedness for the viewport gizmo interaction.
        angle = -rotation_angle_from_mouse_delta(self.start_mouse, mouse_pos, self.center_screen)
        delta_q = axis_quaternion(axis, angle)
        self.object.rotation = multiply_quaternions(delta_q, self.original.rotation)

    def _apply_scale(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        if self.original.vertices is None:
            return
        if axis == "UNIFORM":
            raw = float(mouse_pos[0] - self.start_mouse[0] - (mouse_pos[1] - self.start_mouse[1]))
            factor = max(0.01, 1.0 + raw * 0.01)
            sx = sy = sz = factor
        else:
            delta = axis_drag_delta(self.start_mouse, mouse_pos, axis, camera, self.start_depth, viewport_height)
            factor = max(0.01, 1.0 + delta)
            sx = sy = sz = 1.0
            if axis == "X":
                sx = factor
            elif axis == "Y":
                sy = factor
            else:
                sz = factor
        # GhostRigger ModelNode has no persistent scale field; mutating the
        # mesh's local vertices is the durable transform representation.
        self.object.vertices = [(x * sx, y * sy, z * sz) for x, y, z in self.original.vertices]
        compute_bounds = getattr(self.object, "compute_bounds", None)
        if callable(compute_bounds):
            compute_bounds()

    def cancel(self) -> None:
        if self.object is not None and self.original is not None:
            self.restore(self.object, self.original)
            self._invalidate()
        self.active = False

    def end_drag(self) -> tuple[TransformSnapshot | None, TransformSnapshot | None, object | None]:
        obj = self.object
        before = self.original
        after = self.snapshot(obj) if obj is not None else None
        self.active = False
        return before, after, obj

    def restore(self, obj, snapshot: TransformSnapshot) -> None:
        obj.position = tuple(snapshot.position)
        obj.rotation = tuple(snapshot.rotation)
        if snapshot.vertices is not None:
            obj.vertices = [tuple(v) for v in snapshot.vertices]
            compute_bounds = getattr(obj, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()

    def _invalidate(self) -> None:
        if self.invalidate_callback is not None and self.object is not None:
            self.invalidate_callback(self.object)
