"""Apply transform gizmo edits to GhostRigger scene objects."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Optional

from .gizmo_mode import GizmoMode
from src.math.transform_math import (
    AXIS_VECTORS,
    axis_drag_delta,
    axis_quaternion,
    axis_quaternion_from_vector,
    multiply_quaternions,
    ray_from_mouse,
    rotate_vector,
    rotation_angle_from_mouse_delta,
    rotation_angle_from_ray_plane,
)
from src.measurement.angle_snap import AngleSnap
from src.measurement.percent_snap import PercentSnap


@dataclass
class TransformSnapshot:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    vertices: tuple[tuple[float, float, float], ...] | None = None
    light_radius: float | None = None
    light_area_size: float | None = None
    light_cone_degrees: float | None = None
    camera_helper_size: float | None = None
    pivot_world: tuple[float, float, float] | None = None
    pivot_rotation: tuple[float, float, float, float] | None = None


class TransformController:
    """Small state machine that applies one active gizmo drag."""

    def __init__(
        self,
        invalidate_callback: Optional[Callable[[object], None]] = None,
        angle_snap: AngleSnap | None = None,
        percent_snap: PercentSnap | None = None,
    ):
        self.invalidate_callback = invalidate_callback
        self.angle_snap = angle_snap
        self.percent_snap = percent_snap
        self.position_snap_enabled = False
        self.position_snap_increment = 10.0
        self.object = None
        self.mode: GizmoMode | None = None
        self.handle = ""
        self.start_mouse = (0, 0)
        self.start_depth = 1.0
        self.center_screen: tuple[float, float] | None = None
        self.original: TransformSnapshot | None = None
        self.active = False
        self.axis_vectors = dict(AXIS_VECTORS)
        self._start_ray_origin = None
        self._start_ray_dir = None
        self._viewport_width = 1
        self._viewport_height = 1
        self._camera = None

    def snapshot(self, obj) -> TransformSnapshot:
        vertices = getattr(obj, "vertices", None)
        vertex_snapshot = tuple(tuple(float(c) for c in v[:3]) for v in vertices) if vertices is not None else None
        return TransformSnapshot(
            position=tuple(float(v) for v in getattr(obj, "position", (0.0, 0.0, 0.0))),
            rotation=tuple(float(v) for v in getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0))),
            scale=tuple(float(v) for v in getattr(obj, "_gr_scale", (1.0, 1.0, 1.0))[:3]),
            vertices=vertex_snapshot,
            light_radius=float(getattr(obj, "light_radius", 0.0) or 0.0) if bool(getattr(obj, "is_light", False)) else None,
            light_area_size=float(getattr(obj, "light_area_size", 0.0) or 0.0) if bool(getattr(obj, "is_light", False)) else None,
            light_cone_degrees=float(getattr(obj, "light_cone_degrees", 45.0) or 45.0) if bool(getattr(obj, "is_light", False)) else None,
            camera_helper_size=float(getattr(obj, "_gr_helper_size", 1.0) or 1.0) if bool(getattr(obj, "is_camera", False)) else None,
            pivot_world=self._tuple_attr(obj, "_gr_pivot_world", getattr(obj, "position", (0.0, 0.0, 0.0)), 3),
            pivot_rotation=self._tuple_attr(obj, "_gr_pivot_rotation", getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0)), 4),
        )

    @staticmethod
    def _tuple_attr(obj, name: str, fallback, count: int):
        raw = getattr(obj, name, None)
        if raw is None:
            raw = fallback
        try:
            return tuple(float(v) for v in tuple(raw)[:count])
        except Exception:
            return tuple(float(v) for v in tuple(fallback)[:count])

    def set_position_snap(self, enabled: bool, increment: float) -> None:
        self.position_snap_enabled = bool(enabled)
        try:
            self.position_snap_increment = max(1e-6, float(increment))
        except (TypeError, ValueError):
            self.position_snap_increment = 10.0

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
        axis_vectors: dict[str, tuple[float, float, float]] | None = None,
        viewport_size: tuple[int, int] | None = None,
    ) -> None:
        self.object = obj
        self.mode = mode
        self.handle = str(handle)
        self.start_mouse = (int(mouse_pos[0]), int(mouse_pos[1]))
        self.start_depth = float(depth)
        self.center_screen = center_screen
        self.axis_vectors = axis_vectors or dict(AXIS_VECTORS)
        self.original = self.snapshot(obj)
        self.active = True
        self._camera = camera
        if viewport_size is not None:
            self._viewport_width = max(1, int(viewport_size[0]))
            self._viewport_height = max(1, int(viewport_size[1]))
        # Capture the start ray for ray-plane rotation (Tier 1 gizmo fix)
        try:
            self._start_ray_origin, self._start_ray_dir = ray_from_mouse(
                self.start_mouse, camera, self._viewport_width, self._viewport_height,
            )
        except Exception:
            self._start_ray_origin = None
            self._start_ray_dir = None

    def drag(self, mouse_pos: tuple[int, int], camera, viewport_height: int) -> None:
        if not self.active or self.object is None or self.original is None or self.mode is None:
            return
        axis = self.handle.rsplit("_", 1)[-1]
        if self.mode == GizmoMode.TRANSLATE:
            self._apply_translate(axis, mouse_pos, camera, viewport_height)
        elif self.mode == GizmoMode.ROTATE:
            self._apply_rotate(axis, mouse_pos, camera, viewport_height)
        elif self.mode == GizmoMode.SCALE:
            self._apply_scale(axis, mouse_pos, camera, viewport_height)
        self._invalidate()

    def _apply_translate(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        if axis in {"VIEW", "SCREEN", "CENTER"}:
            self._apply_view_translate(mouse_pos, camera, viewport_height)
            return
        delta = axis_drag_delta(
            self.start_mouse,
            mouse_pos,
            axis,
            camera,
            self.start_depth,
            viewport_height,
            self.axis_vectors,
        )
        av = self.axis_vectors.get(axis, AXIS_VECTORS["X"])
        if str(getattr(self.object, "_gr_pivot_edit_mode", "") or "") == "affect_pivot_only":
            p = self.original.pivot_world or self.original.position
            self.object._gr_pivot_world = (
                p[0] + av[0] * delta,
                p[1] + av[1] * delta,
                p[2] + av[2] * delta,
            )
            self.object._gr_pivot_world_dirty = True
            self.object._gr_gizmo_world_position = tuple(self.object._gr_pivot_world)
            return
        p = self.original.position
        delta_vec = (av[0] * delta, av[1] * delta, av[2] * delta)
        new_position = (
            p[0] + delta_vec[0],
            p[1] + delta_vec[1],
            p[2] + delta_vec[2],
        )
        if self.position_snap_enabled:
            inc = self.position_snap_increment
            if axis == "X":
                new_position = (round(new_position[0] / inc) * inc, new_position[1], new_position[2])
            elif axis == "Y":
                new_position = (new_position[0], round(new_position[1] / inc) * inc, new_position[2])
            elif axis == "Z":
                new_position = (new_position[0], new_position[1], round(new_position[2] / inc) * inc)
        self.object.position = new_position
        if self.original.pivot_world is not None:
            actual_delta = (
                new_position[0] - self.original.position[0],
                new_position[1] - self.original.position[1],
                new_position[2] - self.original.position[2],
            )
            self.object._gr_pivot_world = (
                self.original.pivot_world[0] + actual_delta[0],
                self.original.pivot_world[1] + actual_delta[1],
                self.original.pivot_world[2] + actual_delta[2],
            )
            self.object._gr_pivot_world_dirty = True
            self.object._gr_gizmo_world_position = tuple(self.object._gr_pivot_world)

    def _apply_view_translate(self, mouse_pos, camera, viewport_height: int) -> None:
        right, up, _fwd, _eye = camera._view_matrix()
        dx = float(mouse_pos[0] - self.start_mouse[0])
        dy = float(mouse_pos[1] - self.start_mouse[1])
        world_per_px = (
            2.0
            * max(0.5, float(self.start_depth))
            * math.tan(math.radians(float(camera.fov)) * 0.5)
        ) / max(1, int(viewport_height))
        delta_vec = (
            (float(right[0]) * dx + float(up[0]) * -dy) * world_per_px,
            (float(right[1]) * dx + float(up[1]) * -dy) * world_per_px,
            (float(right[2]) * dx + float(up[2]) * -dy) * world_per_px,
        )
        if str(getattr(self.object, "_gr_pivot_edit_mode", "") or "") == "affect_pivot_only":
            p = self.original.pivot_world or self.original.position
            self.object._gr_pivot_world = (
                p[0] + delta_vec[0],
                p[1] + delta_vec[1],
                p[2] + delta_vec[2],
            )
            self.object._gr_pivot_world_dirty = True
            self.object._gr_gizmo_world_position = tuple(self.object._gr_pivot_world)
            return
        p = self.original.position
        new_position = (p[0] + delta_vec[0], p[1] + delta_vec[1], p[2] + delta_vec[2])
        if self.position_snap_enabled:
            inc = self.position_snap_increment
            new_position = tuple(round(v / inc) * inc for v in new_position)
        self.object.position = new_position
        if self.original.pivot_world is not None:
            actual_delta = (
                new_position[0] - self.original.position[0],
                new_position[1] - self.original.position[1],
                new_position[2] - self.original.position[2],
            )
            self.object._gr_pivot_world = (
                self.original.pivot_world[0] + actual_delta[0],
                self.original.pivot_world[1] + actual_delta[1],
                self.original.pivot_world[2] + actual_delta[2],
            )
            self.object._gr_pivot_world_dirty = True
            self.object._gr_gizmo_world_position = tuple(self.object._gr_pivot_world)

    def _apply_rotate(self, axis: str, mouse_pos, camera=None, viewport_height: int = 0) -> None:
        # Resolve the world-space rotation axis vector.
        world_axis = self.axis_vectors.get(axis, AXIS_VECTORS.get(axis, (0.0, 0.0, 1.0)))

        # For LOCAL transform space, rotate the axis by the object's original
        # rotation so the gizmo operates on local axes (Tier 1 gizmo fix).
        transform_space = getattr(self, "transform_space", None)
        if transform_space is not None and str(transform_space).upper() == "LOCAL" and self.original is not None:
            world_axis = tuple(rotate_vector(self.original.rotation, world_axis))

        # Use ray-plane projection for accurate rotation at oblique viewing
        # angles (Tier 1 gizmo fix).  Falls back to legacy screen-space angle
        # if the camera/ray info is unavailable.
        pivot = self.original.pivot_world if self.original and self.original.pivot_world else (
            self.original.position if self.original else (0.0, 0.0, 0.0)
        )
        angle = None
        if camera is not None and self._start_ray_origin is not None and viewport_height > 0:
            try:
                cur_origin, cur_dir = ray_from_mouse(
                    mouse_pos, camera, self._viewport_width, viewport_height,
                )
                angle = rotation_angle_from_ray_plane(
                    self._start_ray_origin, self._start_ray_dir,
                    cur_origin, cur_dir,
                    pivot, world_axis,
                )
            except Exception:
                angle = None

        if angle is None:
            # Legacy screen-space fallback
            angle = -rotation_angle_from_mouse_delta(self.start_mouse, mouse_pos, self.center_screen)

        if self.angle_snap is not None:
            angle = self.angle_snap.snap_radians(angle)

        # Build the rotation quaternion about the resolved world-space axis.
        delta_q = axis_quaternion_from_vector(world_axis, angle)

        if str(getattr(self.object, "_gr_pivot_edit_mode", "") or "") == "affect_pivot_only":
            base = self.original.pivot_rotation or self.original.rotation
            self.object._gr_pivot_rotation = multiply_quaternions(delta_q, base)
            return
        pivot_world = self.original.pivot_world
        if pivot_world is not None:
            rel = (
                self.original.position[0] - pivot_world[0],
                self.original.position[1] - pivot_world[1],
                self.original.position[2] - pivot_world[2],
            )
            rotated = rotate_vector(delta_q, rel)
            self.object.position = (
                pivot_world[0] + rotated[0],
                pivot_world[1] + rotated[1],
                pivot_world[2] + rotated[2],
            )
            self.object._gr_gizmo_world_position = tuple(pivot_world)
        self.object.rotation = multiply_quaternions(delta_q, self.original.rotation)

    def _apply_scale(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        if bool(getattr(self.object, "is_light", False)):
            self._apply_light_scale(axis, mouse_pos, camera, viewport_height)
            return
        if bool(getattr(self.object, "is_camera", False)):
            self._apply_camera_scale(axis, mouse_pos, camera, viewport_height)
            return
        scene_root_scale = bool(getattr(self.object, "_gr_scene_object_root", False))
        if self.original.vertices is None and not scene_root_scale:
            return
        if axis == "UNIFORM":
            raw = float(mouse_pos[0] - self.start_mouse[0] - (mouse_pos[1] - self.start_mouse[1]))
            factor = max(0.01, 1.0 + raw * 0.01)
            if self.percent_snap is not None:
                factor = self.percent_snap.snap_scale_factor(factor)
            sx = sy = sz = factor
        else:
            delta = axis_drag_delta(
                self.start_mouse,
                mouse_pos,
                axis,
                camera,
                self.start_depth,
                viewport_height,
                self.axis_vectors,
            )
            factor = max(0.01, 1.0 + delta)
            if self.percent_snap is not None:
                factor = self.percent_snap.snap_scale_factor(factor)
            sx = sy = sz = 1.0
            if axis == "X":
                sx = factor
            elif axis == "Y":
                sy = factor
            else:
                sz = factor
        pivot_world = self.original.pivot_world
        if pivot_world is not None:
            rel = (
                self.original.position[0] - pivot_world[0],
                self.original.position[1] - pivot_world[1],
                self.original.position[2] - pivot_world[2],
            )
            if axis == "UNIFORM":
                scaled_rel = (rel[0] * sx, rel[1] * sy, rel[2] * sz)
            else:
                av = self.axis_vectors.get(axis, AXIS_VECTORS["X"])
                length = max(1e-9, (av[0] * av[0] + av[1] * av[1] + av[2] * av[2]) ** 0.5)
                unit = (av[0] / length, av[1] / length, av[2] / length)
                component = rel[0] * unit[0] + rel[1] * unit[1] + rel[2] * unit[2]
                scaled_rel = (
                    rel[0] + unit[0] * component * (factor - 1.0),
                    rel[1] + unit[1] * component * (factor - 1.0),
                    rel[2] + unit[2] * component * (factor - 1.0),
                )
            self.object.position = (
                pivot_world[0] + scaled_rel[0],
                pivot_world[1] + scaled_rel[1],
                pivot_world[2] + scaled_rel[2],
            )
            self.object._gr_gizmo_world_position = tuple(pivot_world)
        # GhostRigger ModelNode has no universal persistent scale field. Mesh
        # nodes keep scale by mutating local vertices; scene wrappers keep the
        # authored KMAX scale metadata for the owning scene object.
        if self.original.vertices is not None and not scene_root_scale:
            self.object.vertices = [(x * sx, y * sy, z * sz) for x, y, z in self.original.vertices]
        osx, osy, osz = self.original.scale
        self.object._gr_scale = (
            max(0.001, osx * sx),
            max(0.001, osy * sy),
            max(0.001, osz * sz),
        )
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
        obj._gr_scale = tuple(snapshot.scale)
        if snapshot.vertices is not None:
            obj.vertices = [tuple(v) for v in snapshot.vertices]
            compute_bounds = getattr(obj, "compute_bounds", None)
            if callable(compute_bounds):
                compute_bounds()
        if snapshot.light_radius is not None:
            obj.light_radius = float(snapshot.light_radius)
        if snapshot.light_area_size is not None:
            obj.light_area_size = float(snapshot.light_area_size)
        if snapshot.light_cone_degrees is not None:
            obj.light_cone_degrees = float(snapshot.light_cone_degrees)
        if snapshot.camera_helper_size is not None:
            obj._gr_helper_size = float(snapshot.camera_helper_size)
        if snapshot.pivot_world is not None:
            obj._gr_pivot_world = tuple(snapshot.pivot_world)
        if snapshot.pivot_rotation is not None:
            obj._gr_pivot_rotation = tuple(snapshot.pivot_rotation)

    def _invalidate(self) -> None:
        if self.invalidate_callback is not None and self.object is not None:
            self.invalidate_callback(self.object)

    def _apply_light_scale(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        if self.original is None:
            return
        if axis == "UNIFORM":
            raw = float(mouse_pos[0] - self.start_mouse[0] - (mouse_pos[1] - self.start_mouse[1]))
            factor = max(0.01, 1.0 + raw * 0.01)
        else:
            delta = axis_drag_delta(self.start_mouse, mouse_pos, axis, camera, self.start_depth, viewport_height, self.axis_vectors)
            factor = max(0.01, 1.0 + delta)
        if self.percent_snap is not None:
            factor = self.percent_snap.snap_scale_factor(factor)
        kind = str(getattr(self.object, "light_kind", "point") or "point").lower()
        if kind in {"area"}:
            base = max(0.001, float(self.original.light_area_size or 1.0))
            self.object.light_area_size = base * factor
            base_radius = max(0.001, float(self.original.light_radius or 1.0))
            self.object.light_radius = base_radius * factor
        elif kind in {"spot"}:
            base_radius = max(0.001, float(self.original.light_radius or 1.0))
            self.object.light_radius = base_radius * factor
        elif kind not in {"directional", "ambient", "aurora_ambient"}:
            base_radius = max(0.001, float(self.original.light_radius or 1.0))
            self.object.light_radius = base_radius * factor

    def _apply_camera_scale(self, axis: str, mouse_pos, camera, viewport_height: int) -> None:
        if self.original is None:
            return
        if axis == "UNIFORM":
            raw = float(mouse_pos[0] - self.start_mouse[0] - (mouse_pos[1] - self.start_mouse[1]))
            factor = max(0.01, 1.0 + raw * 0.01)
        else:
            delta = axis_drag_delta(self.start_mouse, mouse_pos, axis, camera, self.start_depth, viewport_height, self.axis_vectors)
            factor = max(0.01, 1.0 + delta)
        if self.percent_snap is not None:
            factor = self.percent_snap.snap_scale_factor(factor)
        base = max(0.05, float(self.original.camera_helper_size or 1.0))
        self.object._gr_helper_size = max(0.05, base * factor)
