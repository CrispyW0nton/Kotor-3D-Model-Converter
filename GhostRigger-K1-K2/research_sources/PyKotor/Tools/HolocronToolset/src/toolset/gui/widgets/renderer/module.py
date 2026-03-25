"""Module/area renderer widget for KotOR LYT and walkmesh (BWM) with OpenGL.

Used by the module designer and level editor to display and interact with layout and walkmesh.
"""
from __future__ import annotations

import math

from collections import deque
from copy import copy, deepcopy
from time import monotonic, perf_counter
from typing import TYPE_CHECKING

import qtpy

from qtpy import QtCore
from qtpy.QtCore import QMetaObject, QThread, QTimer, Qt
from qtpy.QtGui import QColor, QPainter, QPen, QPolygonF
from qtpy.QtWidgets import (
    QApplication,
    QMessageBox,
    QOpenGLWidget,  # pyright: ignore[reportPrivateImportUsage]
)

from loggerplus import RobustLogger
from pykotor.gl.scene import Scene
from pykotor.resource.formats.bwm.bwm_data import BWM
from pykotor.resource.formats.lyt.lyt_data import LYT
from pykotor.resource.generics.git import GITInstance
from pykotor.resource.type import ResourceType
from toolset.utils.misc import keyboard_modifiers_to_qt_keys
from utility.common.geometry import Vector2, Vector3, Vector4
from utility.error_handling import assert_with_variable_trace

if TYPE_CHECKING:
    from glm import vec3  # pyright: ignore[reportMissingImports]
    from qtpy.QtCore import (
        QPoint,  # pyright: ignore[reportAttributeAccessIssue]
        QPointF,  # pyright: ignore[reportAttributeAccessIssue]
    )
    from qtpy.QtGui import QFocusEvent, QKeyEvent, QMouseEvent, QOpenGLContext, QResizeEvent, QWheelEvent
    from qtpy.QtWidgets import QWidget

    from pykotor.common.module import Module, ModuleResource
    from pykotor.gl.scene import RenderObject
    from pykotor.resource.formats.bwm import BWMFace
    from pykotor.resource.formats.lyt.lyt_data import LYT, LYTDoorHook, LYTObstacle, LYTRoom, LYTTrack
    from toolset.data.installation import HTInstallation


class FrameStats:
    """Lightweight frame statistics tracker used to estimate FPS."""

    __slots__ = ("_timestamps", "_frame_count")

    def __init__(self, max_samples: int = 512):
        self._timestamps: deque[float] = deque(maxlen=max_samples)
        self._frame_count: int = 0

    def reset(self) -> None:
        self._timestamps.clear()
        self._frame_count = 0

    def frame_rendered(self) -> None:
        self._timestamps.append(perf_counter())
        self._frame_count += 1

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def average_fps(self, window_seconds: float | None = 1.0) -> float:
        """Return the average frames-per-second over the requested window."""
        if len(self._timestamps) < 2:
            return 0.0

        if window_seconds is not None:
            cutoff = self._timestamps[-1] - window_seconds
            while len(self._timestamps) > 2 and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return float("inf")
        return (len(self._timestamps) - 1) / elapsed


class ModuleRenderer(QOpenGLWidget):
    sig_renderer_initialized = QtCore.Signal()  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when the context is being setup, the QMainWindow must be in an activated/unhidden state."""

    sig_scene_initialized = QtCore.Signal()  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when scene has been initialized."""

    sig_mouse_moved = QtCore.Signal(
        object, object, object, object, object
    )  # screen coords, screen delta, world/mouse pos, mouse, keys  # pyright: ignore[reportPrivateImportUsage]  # noqa: E501
    """Signal emitted when mouse is moved over the widget."""

    sig_mouse_scrolled = QtCore.Signal(object, object, object)  # screen delta, mouse, keys  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when mouse is scrolled over the widget."""

    sig_mouse_released = QtCore.Signal(object, object, object)  # screen coords, mouse, keys  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when a mouse button is released after being pressed on the widget."""

    sig_mouse_pressed = QtCore.Signal(object, object, object)  # screen coords, mouse, keys  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when a mouse button is pressed on the widget."""

    sig_keyboard_pressed = QtCore.Signal(object, object)  # mouse, keys  # pyright: ignore[reportPrivateImportUsage]

    sig_keyboard_released = QtCore.Signal(object, object)  # mouse, keys  # pyright: ignore[reportPrivateImportUsage]

    sig_object_selected = QtCore.Signal(object)  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when an object has been selected through the renderer."""

    sig_lyt_updated = QtCore.Signal(object)  # pyright: ignore[reportPrivateImportUsage]
    """Signal emitted when the LYT data has been updated."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        from toolset.gui.windows.module_designer import (
            ModuleDesignerSettings,  # noqa: PLC0415  # pylint: disable=C0415
        )

        self._scene: Scene | None = None
        self.settings: ModuleDesignerSettings = ModuleDesignerSettings()
        self._module: Module | None = None
        self._installation: HTInstallation | None = None
        self._lyt: LYT | None = None
        self._lyt_editor = None  # Will hold the LYT editor instance

        self.loop_timer: QTimer = QTimer(self)
        self.loop_timer.timeout.connect(self.loop)
        self.loop_interval: int = 16  # ms, approx 60 FPS (improved from 30)

        self._render_time: int = 0
        self._keys_down: set[Qt.Key] = set()
        self._mouse_down: set[Qt.MouseButton] = set()
        self._mouse_prev: Vector2 = Vector2(self.cursor().pos().x(), self.cursor().pos().y())
        self._mouse_press_time: float = monotonic()  # seconds (monotonic clock, cheap)
        # Cached mouse world position computed inside paintGL (GL context is current there).
        # This is intentionally separate from `scene.cursor` (which is the camera focal point).
        self._mouse_world: Vector3 = Vector3(0.0, 0.0, 0.0)
        self._mouse_world_last_screen: Vector2 | None = None

        self.do_select: bool = False  # Set to true to select object at mouse pointer
        self.free_cam: bool = False  # Changes how screenDelta is calculated in mouseMoveEvent
        self.delta: float = 0.0166  # Approx 60 FPS frame time
        self._frame_stats: FrameStats = FrameStats()
        self._initializing = False  # Flag to prevent resize events during initialization
        self._gl_initialized = False  # Track if initializeGL has been called
        self._selected_walkmesh_face: tuple[BWM, int, Vector3] | None = None
        self._selected_walkmesh_edge: tuple[BWM, int, int, Vector3] | None = None
        self._selected_walkmesh_vertex: tuple[BWM, int, int, Vector3] | None = None
        self._walkmesh_vertex_drag_axis: str | None = None
        self._walkmesh_vertex_hover_axis: str | None = None
        self._selected_object_position: Vector3 | None = None
        self._object_gizmo_mode: str = "translate"
        self._object_gizmo_drag_axis: str | None = None
        self._object_gizmo_hover_axis: str | None = None
        self._drop_preview_world: Vector3 | None = None
        self._drop_preview_label: str | None = None
        self._vis_overlay_points: dict[int, Vector3] = {}
        self._vis_overlay_matrix: dict[int, set[int]] = {}
        self._show_vis_overlay: bool = True

    @property
    def scene(self) -> Scene:
        if self._scene is None:
            instance: QtCore.QCoreApplication | None = QApplication.instance()  # pyright: ignore[reportAttributeAccessIssue]
            assert instance is not None
            if QThread.currentThread() == instance.thread():
                self.show_scene_not_ready_message()
            else:
                QMetaObject.invokeMethod(self, "showSceneNotReadyMessage", Qt.ConnectionType.QueuedConnection)
            raise ValueError("Scene is not initialized.")
        assert self._scene is not None
        return self._scene

    def show_scene_not_ready_message(self):
        from toolset.gui.common.localization import translate as tr

        QMessageBox.warning(self, tr("Scene Not Ready"), tr("The scene is not ready yet."))

    def isReady(self) -> bool:
        return bool(self._module and self._installation)

    def initialize_renderer(
        self,
        installation: HTInstallation,
        module: Module,
    ):
        RobustLogger().debug("Initialize ModuleRenderer")
        self.shutdown_renderer()
        self._initializing = True  # Set flag to prevent resize events during initialization
        try:
            self.show()
        finally:
            # Flag will be cleared after initializeGL is called
            pass
        QApplication.processEvents()  # Force the application to process all pending events
        self.sig_renderer_initialized.emit()  # Tell QMainWindow to show itself, required for a gl context to be created.

        # Check if the widget and its top-level window are visible
        win = self.window()
        if not self.isVisible() or (win is not None and not win.isVisible()):
            RobustLogger().error("Widget or its window is not visible; OpenGL context may not be initialized.")
            raise RuntimeError("The OpenGL context is not available because the widget or its parent window is not visible.")

        # Wait for OpenGL context to be created and initialized
        # Qt calls initializeGL() when the widget is first shown, but this may happen asynchronously
        # In headless/offscreen mode, we need to wait a bit longer and process events
        max_attempts = 50
        for attempt in range(max_attempts):
            ctx = self.context()
            if ctx is not None and ctx.isValid():
                # Try to make the context current to ensure initializeGL was called
                try:
                    self.makeCurrent()
                    # Force initializeGL call if it hasn't been called yet (headless mode workaround)
                    # Qt should call it automatically, but in headless mode we may need to ensure it
                    if hasattr(self, "_gl_initialized") and not self._gl_initialized:
                        self.initializeGL()
                        self._gl_initialized = True
                    break  # Context is ready
                except Exception:
                    pass  # Context exists but not ready yet

            # Process events to allow Qt to call initializeGL
            QApplication.processEvents()
            QApplication.processEvents()  # Process twice to ensure events are handled

            if attempt < max_attempts - 1:
                from time import sleep

                sleep(0.01)  # Small delay to allow Qt to initialize

        # Final check if a context is available
        ctx = self.context()
        if ctx is None or not ctx.isValid():
            RobustLogger().error("initializeGL was not called or did not complete successfully after waiting.")
            raise RuntimeError("Failed to initialize OpenGL context. Ensure that the widget is visible and properly integrated into the application's window.")

        # Ensure OpenGL context is current before creating Scene
        # NOTE: makeCurrent() returns None in PyQt5, so we can't check its return value
        self.makeCurrent()

        self._installation = installation
        self._module = module
        self._scene = Scene(
            installation=installation,
            module=module,
        )

        # Initialize module data
        lyt: ModuleResource[LYT] | None = module.layout()
        if lyt is not None:
            self._scene.layout = lyt.resource()

        self.scene.camera.fov = self.settings.fieldOfView
        self.scene.camera.width = self.width()
        self.scene.camera.height = self.height()
        self.sig_scene_initialized.emit()
        self.resume_render_loop()

    def initializeGL(self):
        RobustLogger().debug("ModuleRenderer.initializeGL called.")
        # Ensure OpenGL context is current
        self.makeCurrent()

        super().initializeGL()
        self._gl_initialized = True  # Mark as initialized
        self._initializing = False  # Clear initialization flag - resize events are now safe
        RobustLogger().debug("ModuleRenderer.initializeGL - opengl context setup.")

    def resizeEvent(self, e: QResizeEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        RobustLogger().debug("ModuleRenderer resizeEvent called.")
        # Skip resize events during initialization to avoid access violations
        if self._initializing:
            RobustLogger().debug("Skipping resizeEvent during initialization")
            return

        # Ensure OpenGL context is valid and current before Qt tries to resize
        ctx = self.context()
        if ctx is None or not ctx.isValid():
            RobustLogger().warning("OpenGL context not valid in resizeEvent, skipping resize")
            return

        try:
            self.makeCurrent()
        except Exception as exc:
            RobustLogger().warning("Failed to make context current in resizeEvent: %s", exc)
            return

        super().resizeEvent(e)

    def resizeGL(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        width: int,
        height: int,
    ):
        RobustLogger().debug("ModuleRenderer resizeGL called.")
        # Ensure context is current before Qt tries to resize
        try:
            self.makeCurrent()
        except Exception:
            RobustLogger().warning("Failed to make context current in resizeGL, continuing anyway")
        super().resizeGL(width, height)
        if not self._scene:
            RobustLogger().debug("ignoring scene camera width/height updates in ModuleRenderer resizeGL - the scene is not initialized yet.")
            return
        self.scene.camera.width = width
        self.scene.camera.height = height

    def resume_render_loop(self):
        """Resumes the rendering loop by starting the timer."""
        RobustLogger().debug("ModuleRenderer - resumeRenderLoop called.")
        if not self.loop_timer.isActive():
            self.loop_timer.start(self.loop_interval)
        self.scene.camera.width = self.width()
        self.scene.camera.height = self.height()

    def pause_render_loop(self):
        """Pauses the rendering loop by stopping the timer."""
        RobustLogger().debug("ModuleRenderer - pauseRenderLoop called.")
        if self.loop_timer.isActive():
            self.loop_timer.stop()

    def shutdown_renderer(self):
        """Stops the rendering loop, unloads the module and installation, and attempts to destroy the OpenGL context."""
        RobustLogger().debug("ModuleRenderer - shutdownRenderer called.")
        self.pause_render_loop()
        self._frame_stats.reset()
        self._module = None
        self._installation = None
        self._lyt = None

        # Attempt to destroy the OpenGL context
        gl_context: QOpenGLContext | None = self.context()
        if gl_context:
            gl_context.doneCurrent()  # Ensure the context is not current
            self.update()  # Trigger an update which will indirectly handle context recreation when needed

        self.hide()
        self._scene = None

    def set_lyt(self, lyt: LYT) -> None:
        """Set the current LYT data and update the scene."""
        self._lyt = deepcopy(lyt)
        if self._scene:
            self._scene.layout = self._lyt
            self.update()
        self.sig_lyt_updated.emit(self._lyt)

    def apply_render_overrides(
        self,
        *,
        backface_culling: bool | None = None,
        use_lightmap: bool | None = None,
        show_cursor: bool | None = None,
    ) -> None:
        """Apply renderer overlay/display toggles to the active scene."""
        if self._scene is None:
            return
        if backface_culling is not None:
            self._scene.backface_culling = backface_culling
        if use_lightmap is not None:
            self._scene.use_lightmap = use_lightmap
        if show_cursor is not None:
            self._scene.show_cursor = show_cursor
        self.update()

    def get_lyt(self) -> LYT | None:
        """Returns the current LYT data."""
        return self._lyt

    def add_room(
        self,
        room: LYTRoom,
    ):
        """Adds a new room to the LYT data and triggers a redraw."""
        if self._lyt is not None:
            self._lyt.rooms.append(room)
            self.sig_lyt_updated.emit(self._lyt)
            self.update()

    def add_track(
        self,
        track: LYTTrack,
    ):
        """Adds a new track to the LYT data and triggers a redraw."""
        if self._lyt is not None:
            self._lyt.tracks.append(track)
            self.sig_lyt_updated.emit(self._lyt)
            self.update()

    def add_obstacle(
        self,
        obstacle: LYTObstacle,
    ):
        """Adds a new obstacle to the LYT data and triggers a redraw."""
        if self._lyt is not None:
            self._lyt.obstacles.append(obstacle)
            self.sig_lyt_updated.emit(self._lyt)
            self.update()

    def add_door_hook(
        self,
        doorhook: LYTDoorHook,
    ):
        """Adds a new doorhook to the LYT data and triggers a redraw."""
        if self._lyt is not None:
            self._lyt.doorhooks.append(doorhook)
            self.sig_lyt_updated.emit(self._lyt)
            self.update()

    def update_lyt_preview(self) -> None:
        """Update the LYT preview in the scene."""
        if self._scene and self._lyt:
            self._scene.layout = self._lyt
            self.update()
            self.sig_lyt_updated.emit(self._lyt)

    def remove_room(self, room: LYTRoom) -> None:
        """Remove a room from the LYT."""
        if self._lyt and room in self._lyt.rooms:
            self._lyt.rooms.remove(room)
            self.update_lyt_preview()

    def remove_track(self, track: LYTTrack) -> None:
        """Remove a track from the LYT."""
        if self._lyt and track in self._lyt.tracks:
            self._lyt.tracks.remove(track)
            self.update_lyt_preview()

    def remove_obstacle(self, obstacle: LYTObstacle) -> None:
        """Remove an obstacle from the LYT."""
        if self._lyt and obstacle in self._lyt.obstacles:
            self._lyt.obstacles.remove(obstacle)
            self.update_lyt_preview()

    def remove_door_hook(
        self,
        doorhook: LYTDoorHook,
    ) -> None:
        """Remove a door hook from the LYT."""
        if self._lyt and doorhook in self._lyt.doorhooks:
            self._lyt.doorhooks.remove(doorhook)
            self.update_lyt_preview()

    def paintGL(self):
        """Optimized paintGL with lazy cursor updates.

        Performance optimizations:
        - Cursor world position only calculated when mouse is within bounds
        - screen_to_world only called when cursor position has changed significantly
        - Selection picking separated from rendering

        Reference: Standard game engine practice - minimize expensive per-frame operations
        """
        if not self.loop_timer.isActive():
            return
        if not self.isReady():
            return  # Do nothing if not initialized

        # Ensure OpenGL context is current before any GL calls
        self.makeCurrent()
        super().paintGL()

        # Handle object selection (only when requested)
        if self.do_select:
            self.do_select = False
            obj: RenderObject | None = self.scene.pick(self._mouse_prev.x, self.height() - self._mouse_prev.y)

            if obj is not None and isinstance(obj.data, GITInstance):
                self.sig_object_selected.emit(obj.data)
            else:
                self.scene.selection.clear()
                self.sig_object_selected.emit(None)

        # Cursor represents the mouse world position (where the mouse ray hits the scene).
        # Use the previous frame's cached _mouse_world to avoid chicken-and-egg with depth read.
        # Fallback: camera focal point for first frame or when mouse is outside widget.
        if self._mouse_world_last_screen is not None:
            self.scene.cursor.set_position(
                self._mouse_world.x,
                self._mouse_world.y,
                self._mouse_world.z,
            )
        else:
            self.scene.cursor.set_position(
                self.scene.camera.x,
                self.scene.camera.y,
                self.scene.camera.z,
            )

        # Main render pass
        self.scene.render()
        self._draw_walkmesh_selection_overlay()
        self._draw_object_gizmo_overlay()
        self._draw_vis_overlay()
        self._draw_drop_preview_overlay()
        self._frame_stats.frame_rendered()

        # Update cached mouse world position from the *current* depth buffer.
        # This avoids the extremely expensive `Scene.screen_to_world()` extra render pass,
        # which was a major FPS bottleneck during interactive editing.
        # Single glReadPixels is negligible; we update every frame when mouse is in bounds.
        x = float(self._mouse_prev.x)
        y = float(self._mouse_prev.y)
        if 0.0 <= x < float(self.width()) and 0.0 <= y < float(self.height()):
            try:
                world = self.scene.screen_to_world_from_depth_buffer(int(x), int(y))
                self._mouse_world = world
                self._mouse_world_last_screen = Vector2(x, y)
            except Exception:  # noqa: BLE001
                # If context is lost during teardown, keep last cached value.
                pass

    def set_walkmesh_selection(
        self,
        *,
        face: tuple[BWM, int, Vector3] | None,
        edge: tuple[BWM, int, int, Vector3] | None,
        vertex: tuple[BWM, int, int, Vector3] | None,
        drag_axis: str | None = None,
    ) -> None:
        self._selected_walkmesh_face = face
        self._selected_walkmesh_edge = edge
        self._selected_walkmesh_vertex = vertex
        self._walkmesh_vertex_drag_axis = drag_axis
        if vertex is None:
            self._walkmesh_vertex_hover_axis = None
        self.update()

    def set_drop_preview(self, world: Vector3 | None, label: str | None = None) -> None:
        if world is None:
            self._drop_preview_world = None
            self._drop_preview_label = None
        else:
            self._drop_preview_world = Vector3(world.x, world.y, world.z)
            self._drop_preview_label = label
        self.update()

    def set_object_gizmo(self, position: Vector3 | None, *, mode: str = "translate", drag_axis: str | None = None) -> None:
        if position is None:
            self._selected_object_position = None
            self._object_gizmo_mode = "translate"
            self._object_gizmo_drag_axis = None
            self._object_gizmo_hover_axis = None
        else:
            self._selected_object_position = Vector3(position.x, position.y, position.z)
            self._object_gizmo_mode = "rotate" if mode == "rotate" else "translate"
            self._object_gizmo_drag_axis = drag_axis
            if drag_axis is not None:
                self._object_gizmo_hover_axis = drag_axis
        self.update()

    def set_vis_overlay_data(self, room_positions: dict[int, Vector3], vis_matrix: dict[int, set[int]]) -> None:
        self._vis_overlay_points = {
            room_id: Vector3(position.x, position.y, position.z)
            for room_id, position in room_positions.items()
        }
        self._vis_overlay_matrix = {
            room_id: set(targets)
            for room_id, targets in vis_matrix.items()
        }
        self.update()

    def set_show_vis_overlay(self, enabled: bool) -> None:
        self._show_vis_overlay = enabled
        self.update()

    def _selected_walkmesh_vertex_local_object(self) -> Vector3 | None:
        selection = self._selected_walkmesh_vertex
        if selection is None:
            return None

        walkmesh, face_index, vertex_index, _ = selection
        if not (0 <= face_index < len(walkmesh.faces)):
            return None
        if vertex_index not in (0, 1, 2):
            return None

        face = walkmesh.faces[face_index]
        return [face.v1, face.v2, face.v3][vertex_index]

    def _selected_walkmesh_vertex_world(self) -> Vector3 | None:
        selection = self._selected_walkmesh_vertex
        local_vertex = self._selected_walkmesh_vertex_local_object()
        if selection is None or local_vertex is None:
            return None
        _, _, _, room_offset = selection
        return Vector3(
            local_vertex.x + room_offset.x,
            local_vertex.y + room_offset.y,
            local_vertex.z + room_offset.z,
        )

    def _walkmesh_vertex_gizmo_size(self, vertex: Vector3) -> float:
        if self._scene is None:
            return 0.6
        camera = self.scene.camera
        distance = math.sqrt(
            (camera.x - vertex.x) ** 2
            + (camera.y - vertex.y) ** 2
            + (camera.z - vertex.z) ** 2
        )
        return max(0.45, min(2.0, distance * 0.08))

    def _walkmesh_vertex_gizmo_lines(self, vertex: Vector3) -> dict[str, tuple[Vector3, Vector3]]:
        size = self._walkmesh_vertex_gizmo_size(vertex)
        return {
            "x": (vertex, Vector3(vertex.x + size, vertex.y, vertex.z)),
            "y": (vertex, Vector3(vertex.x, vertex.y + size, vertex.z)),
            "z": (vertex, Vector3(vertex.x, vertex.y, vertex.z + size)),
        }

    def _object_gizmo_lines(self, position: Vector3) -> dict[str, tuple[Vector3, Vector3]]:
        size = self._walkmesh_vertex_gizmo_size(position)
        return {
            "x": (position, Vector3(position.x + size, position.y, position.z)),
            "y": (position, Vector3(position.x, position.y + size, position.z)),
            "z": (position, Vector3(position.x, position.y, position.z + size)),
        }

    def _object_rotate_gizmo_radii(self, position: Vector3) -> dict[str, float]:
        center = self._project_world_to_screen(position)
        if center is None:
            return {"x": 34.0, "y": 44.0, "z": 54.0}

        x_end = self._project_world_to_screen(self._object_gizmo_lines(position)["x"][1])
        base_radius = 42.0
        if x_end is not None:
            base_radius = max(24.0, math.hypot(x_end.x() - center.x(), x_end.y() - center.y()))
        return {
            "x": base_radius * 0.85,
            "y": base_radius * 1.00,
            "z": base_radius * 1.15,
        }

    @staticmethod
    def _point_segment_distance_screen(point: QPointF, start: QPointF, end: QPointF) -> float:
        seg_x = end.x() - start.x()
        seg_y = end.y() - start.y()
        seg_len_sq = seg_x * seg_x + seg_y * seg_y
        if seg_len_sq <= 1e-9:
            return math.hypot(point.x() - start.x(), point.y() - start.y())

        t = ((point.x() - start.x()) * seg_x + (point.y() - start.y()) * seg_y) / seg_len_sq
        t = max(0.0, min(1.0, t))
        proj_x = start.x() + t * seg_x
        proj_y = start.y() + t * seg_y
        return math.hypot(point.x() - proj_x, point.y() - proj_y)

    def walkmesh_vertex_gizmo_handle(self, screen_x: float, screen_y: float, *, max_distance_px: float = 12.0) -> str | None:
        vertex = self._selected_walkmesh_vertex_world()
        if vertex is None:
            return None

        point = QtCore.QPointF(float(screen_x), float(screen_y))
        lines = self._walkmesh_vertex_gizmo_lines(vertex)
        best_axis: str | None = None
        best_distance = float("inf")

        for axis, (start_world, end_world) in lines.items():
            start_screen = self._project_world_to_screen(start_world)
            end_screen = self._project_world_to_screen(end_world)
            if start_screen is None or end_screen is None:
                continue

            distance = self._point_segment_distance_screen(point, start_screen, end_screen)
            if distance < best_distance:
                best_distance = distance
                best_axis = axis

        if best_axis is None or best_distance > max_distance_px:
            return None
        return best_axis

    def object_gizmo_handle(self, screen_x: float, screen_y: float, *, max_distance_px: float = 12.0) -> str | None:
        position = self._selected_object_position
        if position is None:
            return None

        if self._object_gizmo_mode == "rotate":
            center = self._project_world_to_screen(position)
            if center is None:
                return None
            point = QtCore.QPointF(float(screen_x), float(screen_y))
            radial_distance = math.hypot(point.x() - center.x(), point.y() - center.y())
            best_axis: str | None = None
            best_distance = float("inf")
            for axis, radius in self._object_rotate_gizmo_radii(position).items():
                distance = abs(radial_distance - radius)
                if distance < best_distance:
                    best_distance = distance
                    best_axis = axis
            if best_axis is None or best_distance > max_distance_px:
                return None
            return best_axis

        point = QtCore.QPointF(float(screen_x), float(screen_y))
        lines = self._object_gizmo_lines(position)
        best_axis: str | None = None
        best_distance = float("inf")

        for axis, (start_world, end_world) in lines.items():
            start_screen = self._project_world_to_screen(start_world)
            end_screen = self._project_world_to_screen(end_world)
            if start_screen is None or end_screen is None:
                continue

            distance = self._point_segment_distance_screen(point, start_screen, end_screen)
            if distance < best_distance:
                best_distance = distance
                best_axis = axis

        if best_axis is None or best_distance > max_distance_px:
            return None
        return best_axis

    def _project_world_to_screen(self, point: Vector3) -> QPointF | None:
        if self._scene is None:
            return None

        view = self.scene.camera.view()
        projection = self.scene.camera.projection()
        clip = projection * (view * Vector4(point.x, point.y, point.z, 1.0))
        w = clip.w
        if abs(w) <= 1e-7:
            return None
        if w < 0:
            return None

        ndc_x = clip.x / w
        ndc_y = clip.y / w
        ndc_z = clip.z / w
        if ndc_z < -1.0 or ndc_z > 1.0:
            return None

        screen_x = (ndc_x * 0.5 + 0.5) * float(self.width())
        screen_y = (1.0 - (ndc_y * 0.5 + 0.5)) * float(self.height())
        return QtCore.QPointF(screen_x, screen_y)

    def _draw_walkmesh_selection_overlay(self) -> None:
        selected = self._selected_walkmesh_face
        if selected is None:
            return

        walkmesh, face_index, room_offset = selected
        if not (0 <= face_index < len(walkmesh.faces)):
            return

        face = walkmesh.faces[face_index]
        face_points = [
            self._project_world_to_screen(Vector3(face.v1.x + room_offset.x, face.v1.y + room_offset.y, face.v1.z + room_offset.z)),
            self._project_world_to_screen(Vector3(face.v2.x + room_offset.x, face.v2.y + room_offset.y, face.v2.z + room_offset.z)),
            self._project_world_to_screen(Vector3(face.v3.x + room_offset.x, face.v3.y + room_offset.y, face.v3.z + room_offset.z)),
        ]
        if any(point is None for point in face_points):
            return

        p1, p2, p3 = face_points
        assert p1 is not None and p2 is not None and p3 is not None

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            polygon = QPolygonF([p1, p2, p3])
            painter.setBrush(QColor(255, 200, 0, 70))
            painter.setPen(QPen(QColor(255, 215, 0, 220), 2.0))
            painter.drawPolygon(polygon)

            adjacencies = walkmesh.adjacencies(face)
            perimeter_pen = QPen(QColor(255, 150, 0, 210), 2.0)
            perimeter_pen.setStyle(Qt.PenStyle.DashLine)
            edge_points: list[tuple[Vector3, Vector3]] = [
                (
                    Vector3(face.v1.x + room_offset.x, face.v1.y + room_offset.y, face.v1.z + room_offset.z),
                    Vector3(face.v2.x + room_offset.x, face.v2.y + room_offset.y, face.v2.z + room_offset.z),
                ),
                (
                    Vector3(face.v2.x + room_offset.x, face.v2.y + room_offset.y, face.v2.z + room_offset.z),
                    Vector3(face.v3.x + room_offset.x, face.v3.y + room_offset.y, face.v3.z + room_offset.z),
                ),
                (
                    Vector3(face.v3.x + room_offset.x, face.v3.y + room_offset.y, face.v3.z + room_offset.z),
                    Vector3(face.v1.x + room_offset.x, face.v1.y + room_offset.y, face.v1.z + room_offset.z),
                ),
            ]
            for edge_index, adjacency in enumerate(adjacencies):
                if adjacency is not None:
                    continue
                start_vertex, end_vertex = edge_points[edge_index]
                start_point = self._project_world_to_screen(start_vertex)
                end_point = self._project_world_to_screen(end_vertex)
                if start_point is None or end_point is None:
                    continue
                painter.setPen(perimeter_pen)
                painter.drawLine(start_point, end_point)

            if self._selected_walkmesh_edge is not None:
                _, edge_face_index, edge_index, _ = self._selected_walkmesh_edge
                if edge_face_index == face_index and 0 <= edge_index <= 2:
                    start_vertex, end_vertex = edge_points[edge_index]
                    start_point = self._project_world_to_screen(start_vertex)
                    end_point = self._project_world_to_screen(end_vertex)
                    if start_point is not None and end_point is not None:
                        selected_edge_color = QColor(255, 165, 0, 245) if adjacencies[edge_index] is None else QColor(0, 220, 255, 245)
                        painter.setPen(QPen(selected_edge_color, 3.0))
                        painter.drawLine(start_point, end_point)

                        face_center = Vector3(
                            (face.v1.x + face.v2.x + face.v3.x) / 3.0,
                            (face.v1.y + face.v2.y + face.v3.y) / 3.0,
                            (face.v1.z + face.v2.z + face.v3.z) / 3.0,
                        )
                        edge_midpoint = Vector3(
                            (start_vertex.x + end_vertex.x) / 2.0,
                            (start_vertex.y + end_vertex.y) / 2.0,
                            (start_vertex.z + end_vertex.z) / 2.0,
                        )
                        edge_dx = end_vertex.x - start_vertex.x
                        edge_dy = end_vertex.y - start_vertex.y
                        edge_length = math.hypot(edge_dx, edge_dy)
                        if edge_length > 1e-6:
                            normal_x = -edge_dy / edge_length
                            normal_y = edge_dx / edge_length
                            to_center_x = face_center.x - edge_midpoint.x
                            to_center_y = face_center.y - edge_midpoint.y
                            if normal_x * to_center_x + normal_y * to_center_y > 0.0:
                                normal_x = -normal_x
                                normal_y = -normal_y

                            arrow_scale = max(0.3, min(1.0, edge_length * 0.3))
                            arrow_tip_world = Vector3(
                                edge_midpoint.x + normal_x * arrow_scale,
                                edge_midpoint.y + normal_y * arrow_scale,
                                edge_midpoint.z,
                            )
                            arrow_base_screen = self._project_world_to_screen(edge_midpoint)
                            arrow_tip_screen = self._project_world_to_screen(arrow_tip_world)
                            if arrow_base_screen is not None and arrow_tip_screen is not None:
                                painter.setPen(QPen(QColor(255, 80, 80, 235), 2.0))
                                painter.drawLine(arrow_base_screen, arrow_tip_screen)

                                dir_x = arrow_tip_screen.x() - arrow_base_screen.x()
                                dir_y = arrow_tip_screen.y() - arrow_base_screen.y()
                                dir_len = math.hypot(dir_x, dir_y)
                                if dir_len > 1e-6:
                                    ux = dir_x / dir_len
                                    uy = dir_y / dir_len
                                    side_x = -uy
                                    side_y = ux
                                    head_len = 8.0
                                    head_w = 4.0
                                    left = QtCore.QPointF(
                                        arrow_tip_screen.x() - ux * head_len + side_x * head_w,
                                        arrow_tip_screen.y() - uy * head_len + side_y * head_w,
                                    )
                                    right = QtCore.QPointF(
                                        arrow_tip_screen.x() - ux * head_len - side_x * head_w,
                                        arrow_tip_screen.y() - uy * head_len - side_y * head_w,
                                    )
                                    painter.setBrush(QColor(255, 80, 80, 235))
                                    painter.drawPolygon(QPolygonF([arrow_tip_screen, left, right]))

            if self._selected_walkmesh_vertex is not None:
                _, vertex_face_index, vertex_index, _ = self._selected_walkmesh_vertex
                if vertex_face_index == face_index and 0 <= vertex_index <= 2:
                    local_vertex = [face.v1, face.v2, face.v3][vertex_index]
                    vertex = Vector3(
                        local_vertex.x + room_offset.x,
                        local_vertex.y + room_offset.y,
                        local_vertex.z + room_offset.z,
                    )
                    vertex_point = self._project_world_to_screen(vertex)
                    if vertex_point is not None:
                        painter.setBrush(QColor(255, 64, 160, 220))
                        painter.setPen(QPen(QColor(255, 225, 245, 255), 2.0))
                        painter.drawEllipse(vertex_point, 5.0, 5.0)

                        line_colors: dict[str, QColor] = {
                            "x": QColor(255, 96, 96, 230),
                            "y": QColor(96, 255, 120, 230),
                            "z": QColor(96, 170, 255, 230),
                        }
                        active_axis = self._walkmesh_vertex_drag_axis
                        hover_axis = self._walkmesh_vertex_hover_axis
                        for axis, (start_world, end_world) in self._walkmesh_vertex_gizmo_lines(vertex).items():
                            start_screen = self._project_world_to_screen(start_world)
                            end_screen = self._project_world_to_screen(end_world)
                            if start_screen is None or end_screen is None:
                                continue
                            is_active = axis == active_axis
                            is_hover = axis == hover_axis
                            pen_width = 4.0 if is_active else 3.5 if is_hover else 2.5
                            pen = QPen(line_colors[axis], pen_width)
                            painter.setPen(pen)
                            painter.drawLine(start_screen, end_screen)
                            painter.setBrush(line_colors[axis])
                            tip_radius = 3.0 if is_active else 2.8 if is_hover else 2.5
                            painter.drawEllipse(end_screen, tip_radius, tip_radius)
        finally:
            painter.end()

    def _draw_drop_preview_overlay(self) -> None:
        world = self._drop_preview_world
        if world is None:
            return

        screen_point = self._project_world_to_screen(world)
        if screen_point is None:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            ring_pen = QPen(QColor(120, 230, 255, 230), 2.0)
            painter.setPen(ring_pen)
            painter.setBrush(QColor(120, 230, 255, 40))
            painter.drawEllipse(screen_point, 10.0, 10.0)

            cross_pen = QPen(QColor(120, 230, 255, 220), 1.8)
            painter.setPen(cross_pen)
            painter.drawLine(
                QtCore.QPointF(screen_point.x() - 6.0, screen_point.y()),
                QtCore.QPointF(screen_point.x() + 6.0, screen_point.y()),
            )
            painter.drawLine(
                QtCore.QPointF(screen_point.x(), screen_point.y() - 6.0),
                QtCore.QPointF(screen_point.x(), screen_point.y() + 6.0),
            )

            if self._drop_preview_label:
                text_pos = QtCore.QPointF(screen_point.x() + 12.0, screen_point.y() - 12.0)
                painter.setPen(QPen(QColor(210, 245, 255, 240), 1.0))
                painter.drawText(text_pos, self._drop_preview_label)
        finally:
            painter.end()

    def _draw_object_gizmo_overlay(self) -> None:
        position = self._selected_object_position
        if position is None:
            return

        center_screen = self._project_world_to_screen(position)
        if center_screen is None:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            painter.setBrush(QColor(255, 255, 255, 210))
            painter.setPen(QPen(QColor(20, 20, 20, 180), 1.0))
            painter.drawEllipse(center_screen, 3.5, 3.5)

            line_colors: dict[str, QColor] = {
                "x": QColor(255, 96, 96, 230),
                "y": QColor(96, 255, 120, 230),
                "z": QColor(96, 170, 255, 230),
            }
            active_axis = self._object_gizmo_drag_axis
            hover_axis = self._object_gizmo_hover_axis
            if self._object_gizmo_mode == "rotate":
                for axis, radius in self._object_rotate_gizmo_radii(position).items():
                    is_active = axis == active_axis
                    is_hover = axis == hover_axis
                    pen_width = 4.4 if is_active else 3.5 if is_hover else 2.4
                    alpha = 250 if is_active else 235 if is_hover else 205
                    color = QColor(line_colors[axis])
                    color.setAlpha(alpha)
                    painter.setPen(QPen(color, pen_width))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(center_screen, radius, radius)
            else:
                for axis, (start_world, end_world) in self._object_gizmo_lines(position).items():
                    start_screen = self._project_world_to_screen(start_world)
                    end_screen = self._project_world_to_screen(end_world)
                    if start_screen is None or end_screen is None:
                        continue
                    is_active = axis == active_axis
                    is_hover = axis == hover_axis
                    pen_width = 4.2 if is_active else 3.4 if is_hover else 2.4
                    painter.setPen(QPen(line_colors[axis], pen_width))
                    painter.drawLine(start_screen, end_screen)
                    painter.setBrush(line_colors[axis])
                    tip_radius = 3.2 if is_active else 2.9 if is_hover else 2.5
                    painter.drawEllipse(end_screen, tip_radius, tip_radius)
        finally:
            painter.end()

    def _draw_vis_overlay(self) -> None:
        if not self._show_vis_overlay:
            return
        if len(self._vis_overlay_points) < 2 or not self._vis_overlay_matrix:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            bidirectional_pen = QPen(QColor(80, 180, 255, 175), 2.0)
            one_way_pen = QPen(QColor(255, 170, 70, 195), 2.0)
            one_way_pen.setStyle(Qt.PenStyle.DashLine)
            one_way_fill = QColor(255, 170, 70, 215)

            seen_pairs: set[tuple[int, int]] = set()
            for src_room_id, visible_targets in self._vis_overlay_matrix.items():
                src_world = self._vis_overlay_points.get(src_room_id)
                if src_world is None:
                    continue

                for dst_room_id in visible_targets:
                    dst_world = self._vis_overlay_points.get(dst_room_id)
                    if dst_world is None or dst_room_id == src_room_id:
                        continue

                    pair = (min(src_room_id, dst_room_id), max(src_room_id, dst_room_id))
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)

                    src_has_dst = dst_room_id in self._vis_overlay_matrix.get(src_room_id, set())
                    dst_has_src = src_room_id in self._vis_overlay_matrix.get(dst_room_id, set())

                    src_screen = self._project_world_to_screen(src_world)
                    dst_screen = self._project_world_to_screen(dst_world)
                    if src_screen is None or dst_screen is None:
                        continue

                    is_bidirectional = src_has_dst and dst_has_src
                    painter.setPen(bidirectional_pen if is_bidirectional else one_way_pen)
                    painter.drawLine(src_screen, dst_screen)

                    if is_bidirectional:
                        continue

                    direction_start = src_screen if src_has_dst else dst_screen
                    direction_end = dst_screen if src_has_dst else src_screen

                    dx = direction_end.x() - direction_start.x()
                    dy = direction_end.y() - direction_start.y()
                    length = math.hypot(dx, dy)
                    if length <= 1e-6:
                        continue

                    ux = dx / length
                    uy = dy / length
                    px = -uy
                    py = ux

                    arrow_len = 10.0
                    arrow_width = 6.0
                    t = 0.60
                    tip = QtCore.QPointF(
                        direction_start.x() + dx * t,
                        direction_start.y() + dy * t,
                    )
                    base = QtCore.QPointF(
                        tip.x() - ux * arrow_len,
                        tip.y() - uy * arrow_len,
                    )
                    left = QtCore.QPointF(
                        base.x() + px * arrow_width * 0.5,
                        base.y() + py * arrow_width * 0.5,
                    )
                    right = QtCore.QPointF(
                        base.x() - px * arrow_width * 0.5,
                        base.y() - py * arrow_width * 0.5,
                    )

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(one_way_fill)
                    painter.drawPolygon(QPolygonF([tip, left, right]))
        finally:
            painter.end()

    def loop(self):
        """Repaints and checks for keyboard input on mouse press.

        Processing Logic:
        ----------------
            - Always repaints to ensure smooth rendering
            - Checks if mouse is over object and keyboard keys are pressed
            - Emits keyboardPressed signal with mouse/key info
        """
        # Use update() instead of repaint() - this schedules a repaint rather than
        # forcing an immediate synchronous paint. Qt will batch multiple update()
        # calls into a single paint, which is more efficient.
        # repaint() bypasses the event queue and can cause stuttering.
        self.update()

        if self.underMouse() and self.free_cam and len(self._keys_down) > 0:
            self.sig_keyboard_pressed.emit(self._mouse_down, self._keys_down)

    @property
    def frame_stats(self) -> FrameStats:
        """Expose frame statistics for diagnostics and tests."""
        return self._frame_stats

    def average_fps(self, window_seconds: float | None = 1.0) -> float:
        """Return the average FPS calculated over the requested time window."""
        return self._frame_stats.average_fps(window_seconds)

    @property
    def renderer_type(self) -> str:
        """Return the renderer backend identifier (for tests/diagnostics)."""
        return "pyopengl"

    def _pick_walkmesh_face(self, x: float, y: float) -> tuple[BWM, BWMFace, Vector3] | None:
        if self._module is None:
            return None

        layout = self._scene.layout if self._scene is not None else None
        best: tuple[BWM, BWMFace, Vector3] | None = None
        for module_resource in self._module.resources.values():
            if module_resource.restype() is not ResourceType.WOK:
                continue
            walkmesh_resource = module_resource.resource()
            if walkmesh_resource is None:
                continue
            assert isinstance(walkmesh_resource, BWM), assert_with_variable_trace(isinstance(walkmesh_resource, BWM))
            room_offset = Vector3(0.0, 0.0, 0.0)
            if layout is not None:
                room = layout.find_room_by_model(module_resource.resname())
                if room is not None:
                    room_offset = Vector3(room.position.x, room.position.y, room.position.z)
            local_x = x - room_offset.x
            local_y = y - room_offset.y
            over = walkmesh_resource.faceAt(local_x, local_y)
            if over is None:
                continue
            if best is None:
                best = (walkmesh_resource, over, room_offset)
                continue
            if not best[1].material.walkable() and over.material.walkable():
                best = (walkmesh_resource, over, room_offset)

        return best

    def walkmesh_face(self, x: float, y: float) -> tuple[BWM, int, Vector3] | None:
        picked = self._pick_walkmesh_face(x, y)
        if picked is None:
            return None
        walkmesh, face, room_offset = picked
        face_index = next((index for index, candidate in enumerate(walkmesh.faces) if candidate is face), -1)
        if face_index < 0:
            return None
        return walkmesh, face_index, room_offset

    @staticmethod
    def _point_segment_distance_2d(point_x: float, point_y: float, start: Vector3, end: Vector3) -> float:
        segment_dx = end.x - start.x
        segment_dy = end.y - start.y
        segment_length_sq = segment_dx * segment_dx + segment_dy * segment_dy
        if segment_length_sq <= 1e-9:
            return math.hypot(point_x - start.x, point_y - start.y)

        t = ((point_x - start.x) * segment_dx + (point_y - start.y) * segment_dy) / segment_length_sq
        t = max(0.0, min(1.0, t))
        projection_x = start.x + t * segment_dx
        projection_y = start.y + t * segment_dy
        return math.hypot(point_x - projection_x, point_y - projection_y)

    def walkmesh_edge(self, x: float, y: float, *, max_distance: float = 0.35) -> tuple[BWM, int, int, Vector3] | None:
        picked_face = self.walkmesh_face(x, y)
        if picked_face is None:
            return None

        walkmesh, face_index, room_offset = picked_face
        if not (0 <= face_index < len(walkmesh.faces)):
            return None
        face = walkmesh.faces[face_index]

        edge_vertices: list[tuple[Vector3, Vector3]] = [
            (face.v1, face.v2),
            (face.v2, face.v3),
            (face.v3, face.v1),
        ]
        best_edge_index = -1
        best_distance = float("inf")
        local_x = x - room_offset.x
        local_y = y - room_offset.y
        for edge_index, (start_vertex, end_vertex) in enumerate(edge_vertices):
            distance = self._point_segment_distance_2d(local_x, local_y, start_vertex, end_vertex)
            if distance < best_distance:
                best_distance = distance
                best_edge_index = edge_index

        if best_edge_index < 0 or best_distance > max_distance:
            return None
        return walkmesh, face_index, best_edge_index, room_offset

    def walkmesh_vertex(self, x: float, y: float, *, max_distance: float = 0.30) -> tuple[BWM, int, int, Vector3] | None:
        picked_face = self.walkmesh_face(x, y)
        if picked_face is None:
            return None

        walkmesh, face_index, room_offset = picked_face
        if not (0 <= face_index < len(walkmesh.faces)):
            return None
        face = walkmesh.faces[face_index]

        vertices: list[Vector3] = [face.v1, face.v2, face.v3]
        best_vertex_index = -1
        best_distance = float("inf")
        local_x = x - room_offset.x
        local_y = y - room_offset.y
        for vertex_index, vertex in enumerate(vertices):
            distance = math.hypot(local_x - vertex.x, local_y - vertex.y)
            if distance < best_distance:
                best_distance = distance
                best_vertex_index = vertex_index

        if best_vertex_index < 0 or best_distance > max_distance:
            return None
        return walkmesh, face_index, best_vertex_index, room_offset

    def walkmesh_point(
        self,
        x: float,
        y: float,
        default_z: float = 0.0,
    ) -> Vector3:
        """Finds the face and z-height at a point on the walkmesh.

        Args:
        ----
            x: float - The x coordinate of the point
            y: float - The y coordinate of the point
            default_z: float = 0.0 - The default z height if no face is found

        Returns:
        -------
            Vector3 - The (x, y, z) position on the walkmesh

        Processing Logic:
        ----------------
            - Iterates through walkmesh resources to find the face at the given (x,y) coordinates
            - Checks if the found face is walkable, and overrides any previous less walkable face
            - Returns a Vector3 with the input x,y coords and either the face z height or default z if no face.
        """
        picked = self._pick_walkmesh_face(x, y)
        face = None if picked is None else picked[1]
        z: float = default_z if face is None else face.determine_z(x, y)
        return Vector3(x, y, z)

    def reset_buttons_down(self):
        self._mouse_down.clear()

    def reset_keys_down(self):
        self._keys_down.clear()

    def reset_all_down(self):
        self._mouse_down.clear()
        self._keys_down.clear()

    # region Accessors
    def keys_down(self) -> set[Qt.Key]:
        return copy(self._keys_down)

    def mouse_down(self) -> set[Qt.MouseButton]:
        return copy(self._mouse_down)

    # endregion

    # region Camera Transformations
    def snap_camera_to_point(
        self,
        point: Vector3,
        distance: float = 6.0,
    ):
        camera = self.scene.camera
        camera.x, camera.y, camera.z = point.x, point.y, point.z + 1.0
        camera.distance = distance

    def pan_camera(
        self,
        forward: float,
        right: float,
        up: float,
    ):
        forward_vec: vec3 = forward * self.scene.camera.forward()
        sideways: vec3 = right * self.scene.camera.sideward()

        self.scene.camera.x += forward_vec.x + sideways.x
        self.scene.camera.y += forward_vec.y + sideways.y
        self.scene.camera.z += up

    def move_camera(
        self,
        forward: float,
        right: float,
        up: float,
    ):
        forward_vec: vec3 = forward * self.scene.camera.forward(ignore_z=False)
        sideways: vec3 = right * self.scene.camera.sideward(ignore_z=False)
        upward: vec3 = -up * self.scene.camera.upward(ignore_xy=False)

        self.scene.camera.x += upward.x + sideways.x + forward_vec.x
        self.scene.camera.y += upward.y + sideways.y + forward_vec.y
        self.scene.camera.z += upward.z + sideways.z + forward_vec.z

    def rotate_camera(
        self,
        yaw: float,
        pitch: float,
        *,
        clamp_rotations: bool = True,  # noqa: FBT001
    ):
        self.scene.camera.rotate(yaw, pitch, clamp=clamp_rotations)

    def zoom_camera(
        self,
        distance: float,
    ):
        self.scene.camera.distance -= distance
        self.scene.camera.distance = max(self.scene.camera.distance, 0)

    # endregion

    # region Events

    def focusOutEvent(self, e: QFocusEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        self._mouse_down.clear()  # Clears the set when focus is lost
        self._keys_down.clear()  # Clears the set when focus is lost
        super().focusOutEvent(e)  # Ensures that the default handler is still executed
        print("ModuleRenderer.focusOutEvent: clearing all keys/buttons held down.")

    def wheelEvent(self, e: QWheelEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        super().wheelEvent(e)
        if e is None:
            return
        keys_to_emit = self._keys_down | keyboard_modifiers_to_qt_keys(e.modifiers())
        self.sig_mouse_scrolled.emit(Vector2(e.angleDelta().x(), e.angleDelta().y()), self._mouse_down, keys_to_emit)

    def mouseMoveEvent(self, e: QMouseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        # super().mouseMoveEvent(e)
        if e is None:
            return
        pos: QPoint = e.pos() if qtpy.QT5 else e.position().toPoint()  # type: ignore[attr-defined] # pyright: ignore[reportAttributeAccessIssue]
        screen: Vector2 = Vector2(pos.x(), pos.y())
        if self.free_cam:
            screenDelta = Vector2(screen.x - self.width() / 2, screen.y - self.height() / 2)
        else:
            screenDelta = Vector2(screen.x - self._mouse_prev.x, screen.y - self._mouse_prev.y)

        # Use the last cached mouse world position.
        # Computing `screen_to_world` during mouse-move is prohibitively expensive because it
        # requires depth reads (and previously an extra render pass). The cached value is
        # refreshed once per frame in `paintGL` using the already-rendered depth buffer.
        world: Vector3 = self._mouse_world
        # Debounce: suppress drag signals for 60 ms after a mouse-button press to prevent
        # accidental drags. In free-cam mode we never debounce — the user needs immediate
        # mouse response for look rotation.
        if self.free_cam or (monotonic() - self._mouse_press_time) > 0.06:
            self.sig_mouse_moved.emit(screen, screenDelta, world, self._mouse_down, self._keys_down)
        if self._selected_walkmesh_vertex is not None:
            hovered_axis = self.walkmesh_vertex_gizmo_handle(screen.x, screen.y)
            if hovered_axis != self._walkmesh_vertex_hover_axis:
                self._walkmesh_vertex_hover_axis = hovered_axis
                self.update()
        elif self._walkmesh_vertex_hover_axis is not None:
            self._walkmesh_vertex_hover_axis = None
            self.update()
        if self._selected_object_position is not None:
            hovered_axis = self.object_gizmo_handle(screen.x, screen.y)
            if hovered_axis != self._object_gizmo_hover_axis:
                self._object_gizmo_hover_axis = hovered_axis
                self.update()
        elif self._object_gizmo_hover_axis is not None:
            self._object_gizmo_hover_axis = None
            self.update()
        self._mouse_prev = screen  # Always assign mouse_prev after emitting: allows signal handlers (e.g. ModuleDesigner, GITEditor) to handle cursor lock.

    def mousePressEvent(self, e: QMouseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        super().mousePressEvent(e)
        self._mouse_press_time = monotonic()
        button: Qt.MouseButton = e.button()
        self._mouse_down.add(button)
        pos: QPoint = e.pos() if qtpy.QT5 else e.position().toPoint()  # type: ignore[attr-defined] # pyright: ignore[reportAttributeAccessIssue]
        coords: Vector2 = Vector2(pos.x(), pos.y())
        self.sig_mouse_pressed.emit(coords, self._mouse_down, self._keys_down)
        # RobustLogger().debug(f"ModuleRenderer.mousePressEvent: {self._mouse_down}, e.button() '{button}'")

    def mouseReleaseEvent(self, e: QMouseEvent):  # pyright: ignore[reportIncompatibleMethodOverride]
        super().mouseReleaseEvent(e)
        button = e.button()
        self._mouse_down.discard(button)

        pos: QPoint = e.pos() if qtpy.QT5 else e.position().toPoint()  # type: ignore[attr-defined] # pyright: ignore[reportAttributeAccessIssue]
        coords: Vector2 = Vector2(pos.x(), pos.y())
        self.sig_mouse_released.emit(coords, self._mouse_down, self._keys_down)
        # RobustLogger().debug(f"ModuleRenderer.mouseReleaseEvent: {self._mouse_down}, e.button() '{button}'")

    def keyPressEvent(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        e: QKeyEvent | None,
        bubble: bool = True,  # noqa: FBT001, FBT002
    ):
        super().keyPressEvent(e)
        if e is None:
            return
        key = e.key()
        self._keys_down.add(key)  # pyright: ignore[reportArgumentType]
        if self.underMouse() and not self.free_cam:
            self.sig_keyboard_pressed.emit(self._mouse_down, self._keys_down)
        # key_name = get_qt_key_string_localized(key)
        # RobustLogger().debug(f"ModuleRenderer.keyPressEvent: {self._keys_down}, e.key() '{key_name}'")

    def keyReleaseEvent(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        e: QKeyEvent | None,
        bubble: bool = True,  # noqa: FBT002, FBT001
    ):
        super().keyReleaseEvent(e)
        if e is None:
            return
        key: Qt.Key | int = e.key()
        self._keys_down.discard(key)  # pyright: ignore[reportArgumentType]
        if self.underMouse() and not self.free_cam:
            self.sig_keyboard_released.emit(self._mouse_down, self._keys_down)
        # key_name = get_qt_key_string_localized(key)
        # RobustLogger().debug(f"ModuleRenderer.keyReleaseEvent: {self._keys_down}, e.key() '{key_name}'")

    # endregion
