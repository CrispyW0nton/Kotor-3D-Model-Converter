"""High-level transform gizmo coordinator."""

from __future__ import annotations

from .gizmo_mode import GizmoMode, TransformSpace
from .gizmo_picker import GizmoPicker
from .gizmo_renderer import GizmoRenderer
from .transform_controller import TransformController


class TransformGizmo:
    """Owns gizmo state and delegates drawing, picking, and transform edits."""

    def __init__(self, controller: TransformController | None = None):
        self.mode = GizmoMode.TRANSLATE
        self.transform_space = TransformSpace.WORLD
        self.visible = True
        self.selected_object = None
        self.position = (0.0, 0.0, 0.0)
        self.orientation = (0.0, 0.0, 0.0, 1.0)
        self.scale = 1.0
        self.hovered_handle: str | None = None
        self.active_handle: str | None = None
        self.renderer = GizmoRenderer()
        self.picker = GizmoPicker()
        self.controller = controller or TransformController()
        self._last_depth = 1.0
        self._last_center_screen: tuple[float, float] | None = None

    def set_selected_object(self, obj) -> None:
        self.selected_object = obj
        self.update_from_selection()

    def clear_selection(self) -> None:
        self.selected_object = None
        self.hovered_handle = None
        self.active_handle = None

    def cycle_mode(self) -> GizmoMode:
        order = (GizmoMode.TRANSLATE, GizmoMode.ROTATE, GizmoMode.SCALE)
        self.mode = order[(order.index(self.mode) + 1) % len(order)]
        self.hovered_handle = None
        return self.mode

    def set_mode(self, mode: GizmoMode | str) -> None:
        self.mode = mode if isinstance(mode, GizmoMode) else GizmoMode(str(mode).lower())
        self.hovered_handle = None

    def update_from_selection(self) -> None:
        obj = self.selected_object
        if obj is None:
            self.position = (0.0, 0.0, 0.0)
            self.orientation = (0.0, 0.0, 0.0, 1.0)
            return
        position = getattr(obj, "_gr_gizmo_world_position", None)
        if position is None:
            position = getattr(obj, "position", (0.0, 0.0, 0.0))
        self.position = tuple(float(v) for v in position)
        self.orientation = tuple(float(v) for v in getattr(obj, "rotation", (0.0, 0.0, 0.0, 1.0)))

    def begin_drag(self, axis_or_handle: str, mouse_pos: tuple[int, int], camera) -> None:
        if self.selected_object is None:
            return
        self.active_handle = axis_or_handle
        self.controller.begin_drag(
            self.selected_object,
            self.mode,
            axis_or_handle,
            mouse_pos,
            camera,
            depth=self._last_depth,
            center_screen=self._last_center_screen,
        )

    def drag(self, mouse_pos: tuple[int, int], camera, viewport_height: int = 1) -> None:
        self.controller.drag(mouse_pos, camera, viewport_height)
        self.update_from_selection()

    def end_drag(self):
        result = self.controller.end_drag()
        self.active_handle = None
        self.update_from_selection()
        return result

    def cancel_drag(self) -> None:
        self.controller.cancel()
        self.active_handle = None
        self.update_from_selection()

    def draw(self, draw, camera, projector, width: int, height: int) -> None:
        self.update_from_selection()
        center = projector(self.position[0], self.position[1], self.position[2], width, height)
        if center is not None:
            self._last_center_screen = (float(center[0]), float(center[1]))
            self._last_depth = float(center[2])
        self.renderer.draw(draw, self, camera, projector, width, height)

    def hit_test(self, mouse_pos: tuple[int, int], camera=None) -> str | None:
        self.hovered_handle = self.picker.hit_test(mouse_pos, self.renderer.handles)
        return self.hovered_handle
