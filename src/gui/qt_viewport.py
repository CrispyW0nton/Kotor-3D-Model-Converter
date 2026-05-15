"""Qt viewport host for the GhostRigger UI migration."""

from __future__ import annotations

import logging
import math
import os
import threading
import time as time_module
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_gpu_renderer import GpuRenderer
from .qt_uv_viewer import QtUVViewerWindow
from .viewport import ArcBallCamera, FrameRenderer
from .viewport_navigation import (
    DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
    has_modifier,
    normalize_viewport_navigation_profile,
    viewport_profile_label,
)

log = logging.getLogger(__name__)


class QtViewportWidget(QtWidgets.QWidget):
    """Qt model viewport backed by GhostRigger's shared frame renderer."""

    modelChanged = QtCore.Signal(object)
    nodeSelected = QtCore.Signal(object)
    nodeMoved = QtCore.Signal(object)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.camera = ArcBallCamera()
        self._renderer = FrameRenderer(self.camera)
        self.model = None
        self.on_bone_selected = None
        self.on_node_selected = None
        self.on_node_moved = None

        self._mx = self._my = 0
        self._press_x = self._press_y = 0
        self._drag_threshold = 4
        self._is_dragging = False
        self._pan_dragging = False
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._gimbal_dragging = False
        self._gimbal_axis = ""
        self._gimbal_drag_start = (0, 0)
        self._gimbal_node_start_pos = (0.0, 0.0, 0.0)
        self._gimbal_node_start_rot = (0.0, 0.0, 0.0, 1.0)
        self._undo_limit = 250
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._render_pending = False
        self._last_canvas_size = (0, 0)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._fast_drag_enabled = False
        self._uv_viewer: Optional[QtUVViewerWindow] = None
        self._use_gpu = True
        self._gpu_renderer: Optional[GpuRenderer] = None
        self._gpu_tex_preload_model_id = 0
        self._navigation_profile = DEFAULT_VIEWPORT_NAVIGATION_PROFILE
        self._xray_mode = False
        self._dual_viewport_mode = False
        self._last_render_wall = 0.0
        self._last_render_ms = 0.0
        self._fps_accum = 0.0
        self._fps_frames = 0
        self._fps_last_wall = time_module.perf_counter()
        self._fps_display = 0.0
        self._fast_frame_until = 0.0

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_now)
        self._build()

    @property
    def navigation_profile(self) -> str:
        return self._navigation_profile

    def set_navigation_profile(self, profile: object) -> None:
        self._navigation_profile = normalize_viewport_navigation_profile(profile)
        if hasattr(self, "navigation_button"):
            self.navigation_button.setText(viewport_profile_label(self._navigation_profile))
            self.navigation_button.setToolTip(self._navigation_tooltip())

    def _navigation_tooltip(self) -> str:
        label = viewport_profile_label(self._navigation_profile)
        controls = {
            "3dsmax": "3ds Max: Alt+MMB orbit, MMB pan, Alt+RMB zoom, wheel zoom; Shift+F/T/L/P views",
            "blender": "Blender: MMB orbit, Shift+MMB pan, Ctrl+MMB zoom, wheel zoom; 1/3/7/Home views",
            "maya": "Maya: Alt+LMB orbit, Alt+MMB pan, Alt+RMB zoom, wheel zoom; A/F frame",
        }.get(self._navigation_profile, "")
        return f"Viewport navigation profile: {label}\n{controls}"

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tb = QtWidgets.QFrame()
        tb.setObjectName("ViewportToolbar")
        tb.setStyleSheet(
            "#ViewportToolbar { background:#202124; border:0; border-bottom:1px solid #3a3d42; }"
        )
        tb.setFixedHeight(30)
        row = QtWidgets.QHBoxLayout(tb)
        row.setContentsMargins(5, 3, 5, 3)
        row.setSpacing(3)

        self.wire_button = self._button("Wire  W", self.toggle_wireframe, checkable=True)
        self.bones_button = self._button("Bones  B", self.toggle_bones, checkable=True)
        self.texture_button = self._button("Texture  T", self.toggle_texture, checkable=True, active=True)
        self.renderer_button = self._button("GPU", self.toggle_gpu_renderer, checkable=True, active=True)
        self.xray_button = self._button("X-Ray  Alt+X", self.toggle_xray, checkable=True)
        row.addWidget(self.wire_button)
        row.addWidget(self.bones_button)
        row.addWidget(self.texture_button)
        row.addWidget(self.renderer_button)
        row.addWidget(self.xray_button)
        row.addWidget(self._separator())

        self.shade_combo = QtWidgets.QComboBox()
        self.shade_combo.addItems(["Solid", "Wire", "Both"])
        self.shade_combo.setFixedHeight(22)
        self.shade_combo.setStyleSheet(
            "QComboBox { background:#2b2e33; color:#d7dde6; border:1px solid #464b53; "
            "padding:2px 18px 2px 7px; min-width:68px; }"
            "QComboBox:hover { border-color:#6d747f; }"
            "QComboBox::drop-down { border:0; width:16px; }"
            "QComboBox QAbstractItemView { background:#24272c; color:#d7dde6; selection-background-color:#3d5f8a; }"
        )
        row.addWidget(self.shade_combo)
        row.addWidget(self._button("Frame  F", self.frame_all))
        row.addWidget(self._button("Camera  R", self.reset_camera))
        self.walkmesh_button = self._button("WalkMesh", self.toggle_walkmesh, checkable=True)
        row.addWidget(self.walkmesh_button)
        row.addWidget(self._separator())
        self.gimbal_button = self._button("Gimbal  G", self.toggle_gimbal, checkable=True, active=True)
        row.addWidget(self.gimbal_button)
        self.gimbal_mode_button = self._button("[Translate]", self.cycle_gimbal_mode)
        row.addWidget(self.gimbal_mode_button)
        row.addWidget(self._button("UV View", self.open_uv_viewer))
        row.addWidget(self._separator())
        self.navigation_button = self._button(viewport_profile_label(self._navigation_profile), self._cycle_navigation_profile)
        self.navigation_button.setToolTip(self._navigation_tooltip())
        row.addWidget(self.navigation_button)
        row.addStretch(1)

        self.canvas = QtWidgets.QLabel("No model loaded")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(480, 320)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setStyleSheet(
            "background:#17191c; color:#8f9aaa; border:1px solid #34383f;"
        )
        self.canvas.installEventFilter(self)
        self.shade_combo.currentTextChanged.connect(self._on_shade_change)
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_wireframe = self.wire_button.isChecked()

        root.addWidget(tb)
        root.addWidget(self.canvas, 1)

    def _button(
        self,
        text: str,
        callback,
        *,
        checkable: bool = False,
        active: bool = False,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setCheckable(checkable)
        button.setChecked(active if checkable else False)
        button.setFixedHeight(22)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton { background:#2b2e33; color:#d7dde6; border:1px solid #464b53; padding:2px 7px; }"
            "QPushButton:checked { background:#35506f; color:#ffffff; border-color:#6ea0d8; }"
            "QPushButton:hover { background:#363a40; color:#ffffff; border-color:#6d747f; }"
            "QPushButton:pressed { background:#1f2227; }"
        )
        button.clicked.connect(lambda checked=False: callback(checked) if checkable else callback())
        return button

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("background:#4a4f58;")
        sep.setFixedWidth(1)
        return sep

    def load_model(
        self,
        model,
        texture_dir: str = "",
        extra_texture_dirs: Optional[list[str]] = None,
        texture_cache: Optional[dict[str, bytes]] = None,
    ) -> None:
        self.model = model
        self._renderer.set_model(model)
        self._clear_edit_history()
        self._gpu_tex_preload_model_id = 0
        if self._gpu_renderer is not None:
            self._gpu_renderer.clear_caches()
        if model is None:
            self._pixmap = None
            self._render_pending = False
            self._renderer.set_animation_pose(None)
            self._renderer.clear_walkmesh()
            self.walkmesh_button.setChecked(False)
            self._renderer._frame_view = None
            self._renderer._frame_verts_cache = {}
            self._renderer._frame_norms_cache = {}
            self.renderer_button.setText("GPU" if self._use_gpu else "CPU")
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("No model loaded")
            self._update_uv_viewer_model()
            self.modelChanged.emit(None)
            return
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_wireframe = self.wire_button.isChecked()
        self._on_shade_change(self.shade_combo.currentText())

        search_dirs = []
        if texture_dir and os.path.isdir(texture_dir):
            search_dirs.append(texture_dir)
        for directory in extra_texture_dirs or []:
            if directory and os.path.isdir(directory) and directory not in search_dirs:
                search_dirs.append(directory)
        if search_dirs:
            self._renderer.tex_cache.set_search_dirs(search_dirs)

        self._compute_bb(model)
        self.frame_all()
        self._prewarm_textures(model)
        self._update_uv_viewer_model()
        self.modelChanged.emit(model)
        self._request_render()

    def set_model(self, model) -> None:
        self.load_model(model)

    def set_dual_viewport_mode(self, enabled: bool) -> None:
        self._dual_viewport_mode = bool(enabled)

    def set_game_library(self, library, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_game_library(library, game_tag)

    def set_installation(self, installation, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_installation(installation, game_tag)

    def set_resource_manager(self, manager, game_tag: str = "K1") -> None:
        self._renderer.tex_cache.set_resource_manager(manager, game_tag)

    @property
    def tex_cache(self):
        return self._renderer.tex_cache

    def toggle_wireframe(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_wireframe = bool(checked) if checked is not None else not self._renderer.show_wireframe
        if self._renderer.show_wireframe:
            mode = "Both" if self._renderer.show_solid else "Wire"
        else:
            if not self._renderer.show_solid:
                self._renderer.show_solid = True
            mode = "Solid"
        self.shade_combo.blockSignals(True)
        self.shade_combo.setCurrentText(mode)
        self.shade_combo.blockSignals(False)
        self.wire_button.blockSignals(True)
        self.wire_button.setChecked(self._renderer.show_wireframe)
        self.wire_button.blockSignals(False)
        self._request_render()

    def toggle_bones(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_bones = bool(checked) if checked is not None else not self._renderer.show_bones
        self._request_render()

    def toggle_texture(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_texture = bool(checked) if checked is not None else not self._renderer.show_texture
        self.texture_button.blockSignals(True)
        self.texture_button.setChecked(self._renderer.show_texture)
        self.texture_button.blockSignals(False)
        self._request_render()

    def toggle_gpu_renderer(self, checked: Optional[bool] = None) -> None:
        self._use_gpu = bool(checked) if checked is not None else not self._use_gpu
        self.renderer_button.setChecked(self._use_gpu)
        self.renderer_button.setText("GPU" if self._use_gpu else "CPU")
        self._request_render(fast=True)

    def toggle_xray(self, checked: Optional[bool] = None) -> None:
        self._xray_mode = bool(checked) if checked is not None else not self._xray_mode
        self.xray_button.blockSignals(True)
        self.xray_button.setChecked(self._xray_mode)
        self.xray_button.blockSignals(False)
        self._request_render(fast=True)

    def toggle_walkmesh(self, checked: Optional[bool] = None) -> None:
        if self._renderer._walkmesh_overlay is None:
            parent = self.window()
            coload = getattr(parent, "_try_coload_walkmesh", None)
            if callable(coload):
                try:
                    coload()
                except TypeError:
                    coload(None)
            if self._renderer._walkmesh_overlay is None:
                self.walkmesh_button.setChecked(False)
                self._request_render()
                return
        self._renderer.show_walkmesh = bool(checked) if checked is not None else not self._renderer.show_walkmesh
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def toggle_gimbal(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_gimbal = bool(checked) if checked is not None else not self._renderer.show_gimbal
        self.gimbal_button.setChecked(self._renderer.show_gimbal)
        self._request_render()

    def cycle_gimbal_mode(self) -> None:
        self.set_gimbal_mode(2 if self._renderer.gimbal_mode == 1 else 1)
        self._request_render()

    def set_gimbal_mode(self, mode: int) -> None:
        self._renderer.gimbal_mode = 2 if mode == 2 else 1
        mode_label = "Rotate" if self._renderer.gimbal_mode == 2 else "Translate"
        self.gimbal_mode_button.setText(f"[{mode_label}]")

    def frame_all(self) -> None:
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max)
        self._request_render()

    def reset_camera(self) -> None:
        self.camera.__init__()
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max, reset_view=True)
        self._request_render()

    def set_selected_node(self, node) -> None:
        self._renderer.selected_node = node
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(node)
        self.nodeSelected.emit(node)
        self._request_render()

    def refresh_node_transform(self, node=None) -> None:
        if node is not None:
            before = getattr(node, "_gr_undo_before_transform", None)
            if before is not None:
                try:
                    self._commit_node_transform(
                        node,
                        before[0],
                        before[1],
                        tuple(getattr(node, "position", (0.0, 0.0, 0.0))),
                        tuple(getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))),
                        "Set Position",
                    )
                finally:
                    try:
                        delattr(node, "_gr_undo_before_transform")
                    except Exception:
                        pass
            self._evict_transform_cache(node)
        else:
            self._renderer._wt_cache.clear()
        self._request_render()

    def _clear_edit_history(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()

    @staticmethod
    def _state_changed(before_pos, before_rot, after_pos, after_rot) -> bool:
        values = tuple(before_pos) + tuple(before_rot) + tuple(after_pos) + tuple(after_rot)
        if any(not math.isfinite(float(v)) for v in values):
            return False
        return (
            any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_pos, after_pos))
            or any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(before_rot, after_rot))
        )

    def _commit_node_transform(self, node, before_pos, before_rot, after_pos, after_rot, label: str) -> None:
        if node is None or not self._state_changed(before_pos, before_rot, after_pos, after_rot):
            return
        self._undo_stack.append(
            {
                "node": node,
                "before_pos": tuple(before_pos),
                "before_rot": tuple(before_rot),
                "after_pos": tuple(after_pos),
                "after_rot": tuple(after_rot),
                "label": label,
            }
        )
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _apply_transform_action(self, action: dict, use_after: bool) -> None:
        node = action.get("node")
        if node is None:
            return
        node.position = action["after_pos"] if use_after else action["before_pos"]
        node.rotation = action["after_rot"] if use_after else action["before_rot"]
        self._evict_transform_cache(node)
        self._notify_node_moved(node)
        self._request_render()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        action = self._undo_stack.pop()
        self._apply_transform_action(action, use_after=False)
        self._redo_stack.append(action)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._apply_transform_action(action, use_after=True)
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._undo_limit:
            self._undo_stack.pop(0)
        return True

    def _notify_node_moved(self, node) -> None:
        if self.on_node_moved:
            self.on_node_moved(node)
        self.nodeMoved.emit(node)
        if self._renderer.rig_edit_mode and self._renderer.on_bone_moved:
            try:
                self._renderer.on_bone_moved(node.name, node.position)
            except Exception:
                pass

    def set_anim_base_pose(self, base_pose) -> None:
        self._renderer.set_anim_base_pose(base_pose)

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        self._fast_frame_until = max(self._fast_frame_until, time_module.perf_counter() + 0.12)
        self._request_render(fast=True)

    def clear_animation_pose(self) -> None:
        self._renderer.set_animation_pose(None)
        self._fast_frame_until = 0.0
        self._request_render()

    def load_walkmesh(self, wok_data_or_path, world_offset=(0.0, 0.0, 0.0)) -> None:
        self._renderer.load_walkmesh(wok_data_or_path, world_offset)
        self.walkmesh_button.setChecked(self._renderer.show_walkmesh)
        self._request_render()

    def clear_walkmesh(self) -> None:
        self._renderer.clear_walkmesh()
        self.walkmesh_button.setChecked(False)
        self._request_render()

    def open_uv_viewer(self) -> None:
        if self._uv_viewer is None:
            self._uv_viewer = QtUVViewerWindow(self.window())
            self._uv_viewer.destroyed.connect(lambda *_: setattr(self, "_uv_viewer", None))
            self._uv_viewer._tex_cache = self._renderer.tex_cache
            self._update_uv_viewer_model()
            if self._renderer.selected_node:
                self._uv_viewer.set_selected_node(self._renderer.selected_node)
        self._uv_viewer.show()
        self._uv_viewer.raise_()
        self._uv_viewer.activateWindow()

    def _cycle_navigation_profile(self) -> None:
        order = ["3dsmax", "blender", "maya"]
        try:
            index = order.index(self._navigation_profile)
        except ValueError:
            index = -1
        self.set_navigation_profile(order[(index + 1) % len(order)])

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        if obj is self.canvas:
            et = event.type()
            if et == QtCore.QEvent.Resize:
                size = (event.size().width(), event.size().height())
                if size != self._last_canvas_size:
                    self._last_canvas_size = size
                    self._request_render()
                return False
            if et == QtCore.QEvent.MouseButtonPress:
                self.canvas.setFocus()
                action = self._navigation_action(event.button(), event.modifiers())
                if action:
                    self._press_navigation(event, action)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._press_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseMove:
                if self._nav_dragging:
                    self._drag_navigation(event)
                    return True
                if event.buttons() & QtCore.Qt.LeftButton:
                    self._drag_lmb(event)
                    return True
            if et == QtCore.QEvent.MouseButtonRelease:
                if self._nav_dragging and event.button() == self._nav_button:
                    self._release_navigation(event)
                    return True
                if event.button() == QtCore.Qt.LeftButton:
                    self._release_lmb(event)
                    return True
            if et == QtCore.QEvent.Wheel:
                steps = event.angleDelta().y() / 120.0
                self.camera.zoom(steps)
                self._renderer.is_interactive = False
                self._request_render()
                return True
            if et == QtCore.QEvent.KeyPress:
                key = event.key()
                modifiers = event.modifiers()
                no_modifiers = not (
                    modifiers
                    & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
                )
                if key == QtCore.Qt.Key_F and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_Home and no_modifiers:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_R and no_modifiers:
                    self.reset_camera(); return True
                if key == QtCore.Qt.Key_W and no_modifiers:
                    self.wire_button.click(); return True
                if key == QtCore.Qt.Key_B and no_modifiers:
                    self.bones_button.click(); return True
                if key == QtCore.Qt.Key_T and no_modifiers:
                    self.texture_button.click(); return True
                if key == QtCore.Qt.Key_G and no_modifiers:
                    self.gimbal_button.click(); return True
                if key == QtCore.Qt.Key_Tab and no_modifiers:
                    self.cycle_gimbal_mode(); return True
                if key == QtCore.Qt.Key_Z and (event.modifiers() & QtCore.Qt.ControlModifier):
                    if event.modifiers() & QtCore.Qt.ShiftModifier:
                        self.redo()
                    else:
                        self.undo()
                    return True
                if key == QtCore.Qt.Key_Y and (event.modifiers() & QtCore.Qt.ControlModifier):
                    self.redo()
                    return True
                if key == QtCore.Qt.Key_X and (event.modifiers() & QtCore.Qt.AltModifier):
                    self.xray_button.click()
                    return True
                if self._handle_view_key(event):
                    return True
        return super().eventFilter(obj, event)

    def _navigation_action(self, button, modifiers) -> str:
        alt = has_modifier(modifiers, QtCore.Qt.AltModifier)
        shift = has_modifier(modifiers, QtCore.Qt.ShiftModifier)
        ctrl = has_modifier(modifiers, QtCore.Qt.ControlModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if button == QtCore.Qt.MiddleButton and alt:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton and alt:
                return "zoom"
            return ""
        if profile == "blender":
            if button == QtCore.Qt.MiddleButton and shift:
                return "pan"
            if button == QtCore.Qt.MiddleButton and ctrl:
                return "zoom"
            if button == QtCore.Qt.MiddleButton:
                return "orbit"
            return ""
        if profile == "maya":
            if not alt:
                return ""
            if button == QtCore.Qt.LeftButton:
                return "orbit"
            if button == QtCore.Qt.MiddleButton:
                return "pan"
            if button == QtCore.Qt.RightButton:
                return "zoom"
        return ""

    def _press_navigation(self, event, action: str) -> None:
        self._nav_dragging = action
        self._nav_button = event.button()
        self._mx = int(event.position().x())
        self._my = int(event.position().y())
        self._renderer._hovered_bone = None

    def _drag_navigation(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        if self._nav_dragging == "orbit":
            self.camera.orbit(dx * 0.4, -dy * 0.4)
        elif self._nav_dragging == "pan":
            self.camera.pan(dx, dy, self.canvas.height())
        elif self._nav_dragging == "zoom":
            self.camera.zoom((-dy + dx) / 120.0)
        self._renderer.is_interactive = self._fast_drag_enabled
        self._request_render(fast=True)

    def _release_navigation(self, _event) -> None:
        self._nav_dragging = ""
        self._nav_button = QtCore.Qt.NoButton
        self._renderer.is_interactive = False
        self._fast_frame_until = 0.0
        self._request_render()

    def _handle_view_key(self, event) -> bool:
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & QtCore.Qt.ControlModifier)
        alt = bool(modifiers & QtCore.Qt.AltModifier)
        shift = bool(modifiers & QtCore.Qt.ShiftModifier)
        profile = self._navigation_profile
        if profile == "3dsmax":
            if ctrl or alt:
                return False
            if key == QtCore.Qt.Key_F and shift:
                self._set_camera_view("front")
            elif key == QtCore.Qt.Key_T and shift:
                self._set_camera_view("top")
            elif key == QtCore.Qt.Key_L and shift:
                self._set_camera_view("left")
            elif key == QtCore.Qt.Key_P and shift:
                self.reset_camera()
            elif key == QtCore.Qt.Key_Z and not shift:
                self.frame_all()
            else:
                return False
            return True
        if profile == "blender":
            if alt or shift:
                return False
            if key == QtCore.Qt.Key_1:
                self._set_camera_view("back" if ctrl else "front")
            elif key == QtCore.Qt.Key_3:
                self._set_camera_view("left" if ctrl else "right")
            elif key == QtCore.Qt.Key_7:
                self._set_camera_view("bottom" if ctrl else "top")
            elif key == QtCore.Qt.Key_Home:
                self.frame_all()
            else:
                return False
            return True
        if profile == "maya":
            if ctrl or alt or shift:
                return False
            if key in (QtCore.Qt.Key_A, QtCore.Qt.Key_F):
                self.frame_all()
                return True
            return False
        return False

    def _set_camera_view(self, view: str) -> None:
        views = {
            "front": (90.0, 0.0),
            "back": (270.0, 0.0),
            "right": (0.0, 0.0),
            "left": (180.0, 0.0),
            "top": (90.0, 85.0),
            "bottom": (90.0, -85.0),
        }
        azimuth, elevation = views.get(view, views["front"])
        self.camera.azimuth = azimuth
        self.camera.elevation = elevation
        self._request_render()

    def _request_render(self, fast: bool = False) -> None:
        self._render_pending = True
        now = time_module.perf_counter()
        min_interval_ms = 33 if self._dual_viewport_mode else 16
        if fast:
            self._fast_frame_until = max(self._fast_frame_until, now + 0.08)
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            delay = max(1, int(min_interval_ms - elapsed_ms))
        else:
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            delay = max(16, int(min_interval_ms - elapsed_ms))
        if self._render_timer.isActive():
            delay = min(delay, max(1, self._render_timer.remainingTime()))
        self._render_timer.start(delay)

    def _render_now(self) -> None:
        if not self._render_pending:
            return
        self._render_pending = False
        if self.model is None:
            self._pixmap = None
            self.canvas.setPixmap(QtGui.QPixmap())
            self.canvas.setText("No model loaded")
            return
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        t0 = time_module.perf_counter()
        img = self._render_frame(w, h)
        self._last_render_ms = (time_module.perf_counter() - t0) * 1000.0
        self._last_render_wall = time_module.perf_counter()
        if img is None:
            mesh_count = len(self.model.mesh_nodes()) if hasattr(self.model, "mesh_nodes") else 0
            node_count = self.model.node_count() if hasattr(self.model, "node_count") else 0
            self.canvas.setText(f"{getattr(self.model, 'name', 'model')}\nRender unavailable\n{mesh_count} mesh | {node_count} nodes")
            return
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        self._update_fps()
        img = self._draw_performance_overlay(img, w, h)
        qimg = QtGui.QImage(
            img.tobytes("raw", "RGBA"),
            img.width,
            img.height,
            img.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        self._pixmap = QtGui.QPixmap.fromImage(qimg)
        self.canvas.setPixmap(self._pixmap)

    def _render_frame(self, w: int, h: int):
        gpu_can_match_mode = (
            self._renderer.show_solid
            and self._renderer.show_texture
        )
        if self._use_gpu and self.model is not None and gpu_can_match_mode:
            img = self._render_gpu_frame(w, h)
            if img is not None:
                self._set_renderer_badge(True)
                return self._draw_cpu_overlays(img, w, h, gpu_base=True)
        self._set_renderer_badge(False)
        img = self._renderer.render(w, h)
        if self._xray_mode:
            img = self._draw_xray_grid_overlay(img, w, h)
        return img

    def _draw_xray_grid_overlay(self, img, w: int, h: int):
        if img is None:
            return None
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self._renderer._draw_grid(ImageDraw.Draw(img, "RGBA"), w, h)
            return img
        except Exception as exc:
            log.debug("X-Ray grid overlay draw failed: %s", exc)
            return img

    def _render_gpu_frame(self, w: int, h: int):
        if self._gpu_renderer is None:
            self._gpu_renderer = GpuRenderer()
        self._preload_gpu_textures()
        tex_cache = getattr(self._renderer, "tex_cache", None)
        textures = {
            key: value
            for key, value in getattr(tex_cache, "_cache", {}).items()
            if value is not None
        }
        self._gpu_renderer.interactive = bool(
            self._renderer.is_interactive
            or self._pan_dragging
            or self._nav_dragging
            or self._is_dragging
            or time_module.perf_counter() < self._fast_frame_until
        )
        self._gpu_renderer.show_wireframe = bool(self._renderer.show_wireframe)
        self._gpu_renderer.show_grid = True
        self._gpu_renderer.cull_faces = False
        return self._gpu_renderer.render(
            self.model,
            self.camera,
            w,
            h,
            textures=textures,
            anim_pose=getattr(self._renderer, "_anim_pose", None),
            anim_time=float(getattr(self._renderer, "_anim_time", 0.0)),
            anim_base_pose=getattr(self._renderer, "_anim_base_pose", None),
        )

    def _draw_cpu_overlays(self, img, w: int, h: int, *, gpu_base: bool = False):
        if img is None:
            return None
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            self._renderer._last_W = w
            self._renderer._last_H = h
            try:
                self._renderer._frame_view = self._renderer._cam_view_matrix()
                self._renderer._frame_verts_cache = {}
                self._renderer._frame_norms_cache = {}
            except Exception:
                pass
            draw = ImageDraw.Draw(img, "RGBA")
            if self._xray_mode or not gpu_base:
                self._renderer._draw_grid(draw, w, h)
            if self._renderer.show_bones:
                self._renderer._draw_bones(draw, w, h)
            if self._renderer.show_walkmesh:
                self._renderer._draw_walkmesh_overlay(draw, w, h)
            if self._renderer.show_wireframe:
                old_solid = self._renderer.show_solid
                try:
                    self._renderer.show_solid = False
                    self._renderer._draw_mesh_flat(draw, img, w, h)
                finally:
                    self._renderer.show_solid = old_solid
            if self._renderer.show_gimbal:
                self._renderer._draw_gimbal(draw, w, h)
            self._renderer._draw_axes(draw, w, h)
            self._renderer._draw_stats(draw, w, h)
            return img
        except Exception as exc:
            log.debug("Qt GPU overlay draw failed: %s", exc)
            return img

    def _update_fps(self) -> None:
        now = time_module.perf_counter()
        delta = max(0.0, now - self._fps_last_wall)
        self._fps_last_wall = now
        self._fps_accum += delta
        self._fps_frames += 1
        if self._fps_accum >= 0.5:
            self._fps_display = self._fps_frames / max(self._fps_accum, 1e-6)
            self._fps_accum = 0.0
            self._fps_frames = 0

    def _draw_performance_overlay(self, img, w: int, h: int):
        try:
            from PIL import ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")
            fps = self._fps_display
            if fps <= 0.0 and self._last_render_ms > 0.0:
                fps = 1000.0 / max(self._last_render_ms, 1.0)
            mode = "fast" if time_module.perf_counter() < self._fast_frame_until else "hq"
            label = f"{fps:4.0f} fps  {self._last_render_ms:4.0f} ms  {mode}"
            text_w = self._renderer._hud_text_width(label) if hasattr(self._renderer, "_hud_text_width") else len(label) * 7
            x = max(8, w - text_w - 20)
            self._renderer._draw_hud_pill(
                draw,
                x,
                8,
                label,
                fill=(18, 22, 27),
                fg=(156, 232, 184),
                outline=(42, 90, 62),
            )
            return img
        except Exception as exc:
            log.debug("Viewport FPS overlay draw failed: %s", exc)
            return img

    def _preload_gpu_textures(self) -> None:
        model = self.model
        tex_cache = getattr(self._renderer, "tex_cache", None)
        if model is None or tex_cache is None or id(model) == self._gpu_tex_preload_model_id:
            return
        try:
            nodes = list(model.all_nodes()) if hasattr(model, "all_nodes") else []
            for node in nodes:
                if not getattr(node, "is_mesh", False):
                    continue
                names = [
                    getattr(node, "texture", ""),
                    getattr(node, "lightmap", ""),
                    getattr(node, "txi_envmaptexture", ""),
                    getattr(node, "txi_specularcolour", ""),
                    getattr(node, "txi_bumpmaptexture", ""),
                ]
                names.extend(getattr(node, "texture_names", []) or [])
                for name in names:
                    clean = str(name or "").strip()
                    if clean and clean.upper() not in ("NULL", "NONE"):
                        tex_cache.get(clean)
            self._gpu_tex_preload_model_id = id(model)
        except Exception as exc:
            log.debug("Qt GPU texture preload failed: %s", exc)

    def _set_renderer_badge(self, gpu_active: bool) -> None:
        if not hasattr(self, "renderer_button"):
            return
        if not self._use_gpu:
            self.renderer_button.setText("CPU")
            return
        self.renderer_button.setText("GPU" if gpu_active else "CPU*")

    def _on_shade_change(self, text: str) -> None:
        mode = "Wireframe" if text == "Wire" else text
        self._renderer.show_solid = mode in ("Solid", "Both")
        self._renderer.show_wireframe = mode in ("Wireframe", "Both")
        self.wire_button.blockSignals(True)
        self.wire_button.setChecked(self._renderer.show_wireframe)
        self.wire_button.blockSignals(False)
        self._request_render()

    def _press_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        self._mx = self._press_x = x
        self._my = self._press_y = y
        self._is_dragging = False
        self._gimbal_dragging = False

        if self._renderer.show_gimbal and self._renderer.selected_node and self._renderer._gimbal_handles:
            axis = self._renderer.hit_test_gimbal(x, y)
            if axis:
                self._gimbal_dragging = True
                self._gimbal_axis = axis
                self._gimbal_drag_start = (x, y)
                self._gimbal_node_start_pos = tuple(self._renderer.selected_node.position)
                self._gimbal_node_start_rot = tuple(self._renderer.selected_node.rotation)
                self._renderer.gimbal_active_axis = axis
                self._request_render()
                return

        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(x, y)
            if node:
                self._renderer._hovered_bone = node
                self._request_render()

    def _drag_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._gimbal_dragging and self._renderer.selected_node:
            self._apply_gimbal_drag(x, y)
            self._request_render(fast=True)
            return

        if not self._is_dragging:
            if abs(x - self._press_x) > self._drag_threshold or abs(y - self._press_y) > self._drag_threshold:
                self._is_dragging = True
                self._renderer._hovered_bone = None
        if self._is_dragging:
            self._mx, self._my = x, y

    def _release_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            node = self._renderer.selected_node
            if node is not None:
                self._commit_node_transform(
                    node,
                    self._gimbal_node_start_pos,
                    self._gimbal_node_start_rot,
                    tuple(node.position),
                    tuple(node.rotation),
                    "Gimbal Transform",
                )
                self._notify_node_moved(node)
            self._request_render()
            return

        self._renderer._hovered_bone = None
        self._renderer.is_interactive = False
        if self._is_dragging:
            self._is_dragging = False
            self._request_render()
            return

        if self._renderer.show_bones:
            node = self._renderer.hit_test_bone(x, y)
            if node:
                self.set_selected_node(node)
                if self.on_bone_selected:
                    self.on_bone_selected(node)
                return
        self.set_selected_node(None)
        if self.on_bone_selected:
            self.on_bone_selected(None)

    def _press_pan(self, event) -> None:
        self._pan_dragging = True
        self._mx = int(event.position().x())
        self._my = int(event.position().y())

    def _drag_pan(self, event) -> None:
        if not self._pan_dragging:
            return
        x, y = int(event.position().x()), int(event.position().y())
        dx, dy = x - self._mx, y - self._my
        self._mx, self._my = x, y
        self.camera.pan(dx, dy, self.canvas.height())
        self._request_render(fast=True)

    def _release_pan(self, event) -> None:
        self._pan_dragging = False
        self._renderer.is_interactive = False
        self._request_render()

    def _apply_gimbal_drag(self, mx: int, my: int) -> None:
        node = self._renderer.selected_node
        if not node:
            return
        sx0, sy0 = self._gimbal_drag_start
        dx_screen = mx - sx0
        dy_screen = my - sy0
        w = self.canvas.width() or 800
        h = self.canvas.height() or 600
        wp, _, _ = self._renderer._node_world_transform(node)
        proj = self._renderer._proj(*wp, w, h)
        dist = max(0.5, proj[2] if proj else 1.0)
        world_per_px = (2.0 * dist * math.tan(math.radians(self.camera.fov) * 0.5)) / max(h, 1)
        axis = self._gimbal_axis
        start = self._gimbal_node_start_pos

        if self._renderer.gimbal_mode == 1:
            right, up, _fwd, _eye = self.camera._view_matrix()

            def axis_delta(axis_name: str):
                w_dir = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0)}.get(axis_name, (0.0, 0.0, 1.0))
                sc_x = w_dir[0] * right[0] + w_dir[1] * right[1] + w_dir[2] * right[2]
                sc_y = w_dir[0] * up[0] + w_dir[1] * up[1] + w_dir[2] * up[2]
                ll = math.sqrt(sc_x * sc_x + sc_y * sc_y)
                if ll < 1e-6:
                    return (0.0, 0.0, 0.0)
                delta = ((dx_screen * sc_x + (-dy_screen) * sc_y) / ll) * world_per_px
                return (delta * w_dir[0], delta * w_dir[1], delta * w_dir[2])

            if len(axis) == 1:
                d = axis_delta(axis)
                node.position = (start[0] + d[0], start[1] + d[1], start[2] + d[2])
            else:
                d1 = axis_delta(axis[0])
                d2 = axis_delta(axis[1])
                node.position = (start[0] + d1[0] + d2[0], start[1] + d1[1] + d2[1], start[2] + d1[2] + d2[2])
        elif self._renderer.gimbal_mode == 2:
            angle = dx_screen * 0.01
            ha = angle * 0.5
            c, s = math.cos(ha), math.sin(ha)
            rq = {"X": (s, 0.0, 0.0, c), "Y": (0.0, s, 0.0, c)}.get(axis, (0.0, 0.0, s, c))
            ax, ay, az, aw = rq
            bx, by, bz, bw = node.rotation
            new_rot = (
                aw * bx + ax * bw + ay * bz - az * by,
                aw * by - ax * bz + ay * bw + az * bx,
                aw * bz + ax * by - ay * bx + az * bw,
                aw * bw - ax * bx - ay * by - az * bz,
            )
            ll = math.sqrt(sum(v * v for v in new_rot))
            if ll > 1e-9:
                node.rotation = tuple(v / ll for v in new_rot)

        self._evict_transform_cache(node)

    def _evict_transform_cache(self, node) -> None:
        self._renderer._wt_cache.pop(id(node), None)
        stack = list(getattr(node, "children", []) or [])
        visited = set()
        while stack:
            child = stack.pop()
            cid = id(child)
            if cid in visited:
                continue
            visited.add(cid)
            self._renderer._wt_cache.pop(cid, None)
            stack.extend(getattr(child, "children", []) or [])

    def _compute_bb(self, model) -> None:
        if model is None or not getattr(model, "root_node", None):
            return
        mins = [1e18, 1e18, 1e18]
        maxs = [-1e18, -1e18, -1e18]
        has_data = False
        visited = set()
        stack = [model.root_node]
        while stack:
            node = stack.pop()
            nid = id(node)
            if nid in visited:
                continue
            visited.add(nid)
            stack.extend(getattr(node, "children", []) or [])
            verts = getattr(node, "vertices", None) or []
            if not verts:
                continue
            try:
                wp, wo, _ = self._renderer._node_world_transform(node)
            except Exception:
                wp = node.world_position() if hasattr(node, "world_position") else (0.0, 0.0, 0.0)
            for vx, vy, vz in verts:
                x, y, z = vx + wp[0], vy + wp[1], vz + wp[2]
                mins[0] = min(mins[0], x); mins[1] = min(mins[1], y); mins[2] = min(mins[2], z)
                maxs[0] = max(maxs[0], x); maxs[1] = max(maxs[1], y); maxs[2] = max(maxs[2], z)
                has_data = True
        if has_data:
            model.bb_min = tuple(mins)
            model.bb_max = tuple(maxs)

    def _prewarm_textures(self, model) -> None:
        try:
            tex_names = list({
                node.texture_clean
                for node in model.mesh_nodes()
                if getattr(node, "texture_clean", "") and node.texture_clean.upper() not in ("NULL", "")
            })
        except Exception:
            return
        if not tex_names:
            return
        tex_cache = self._renderer.tex_cache

        def load() -> None:
            any_loaded = False
            for name in tex_names:
                try:
                    any_loaded = tex_cache.get(name) is not None or any_loaded
                except Exception:
                    pass
            if any_loaded:
                QtCore.QTimer.singleShot(0, self._request_render)

        threading.Thread(target=load, daemon=True, name="qt-tex-prewarm").start()

    def _update_uv_viewer_model(self) -> None:
        if self._uv_viewer is not None:
            self._uv_viewer.set_model(self.model)
