"""Qt viewport host for the GhostRigger UI migration."""

from __future__ import annotations

import logging
import math
import os
import threading
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from .qt_uv_viewer import QtUVViewerWindow
from .viewport import ArcBallCamera, FrameRenderer

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
        self._gimbal_dragging = False
        self._gimbal_axis = ""
        self._gimbal_drag_start = (0, 0)
        self._gimbal_node_start_pos = (0.0, 0.0, 0.0)
        self._render_pending = False
        self._last_canvas_size = (0, 0)
        self._pixmap: Optional[QtGui.QPixmap] = None
        self._fast_drag_enabled = False
        self._uv_viewer: Optional[QtUVViewerWindow] = None

        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_now)
        self._build()

    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tb = QtWidgets.QFrame()
        tb.setStyleSheet("background:#0e0e20;")
        tb.setFixedHeight(32)
        row = QtWidgets.QHBoxLayout(tb)
        row.setContentsMargins(4, 3, 4, 3)
        row.setSpacing(4)

        self.wire_button = self._button("Wire  W", self.toggle_wireframe, checkable=True)
        self.bones_button = self._button("Bones  B", self.toggle_bones, checkable=True, active=True)
        self.texture_button = self._button("Texture  T", self.toggle_texture, checkable=True, active=True)
        row.addWidget(self.wire_button)
        row.addWidget(self.bones_button)
        row.addWidget(self.texture_button)
        row.addWidget(self._separator())

        self.shade_combo = QtWidgets.QComboBox()
        self.shade_combo.addItems(["Solid", "Wire", "Both"])
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
        row.addStretch(1)

        self.canvas = QtWidgets.QLabel("No model loaded")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(480, 320)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setStyleSheet(
            "background:#111128; color:#8a8ac8; border:1px solid #252550;"
        )
        self.canvas.installEventFilter(self)
        self.shade_combo.currentTextChanged.connect(self._on_shade_change)

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
        button.setStyleSheet(
            "QPushButton { background:#1a1a3a; color:#ccccff; border:0; padding:3px 7px; }"
            "QPushButton:checked { background:#333322; color:#ffffff; }"
            "QPushButton:hover { background:#3333aa; color:#ffffff; }"
        )
        button.clicked.connect(lambda checked=False: callback(checked) if checkable else callback())
        return button

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("background:#252550;")
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

        if model is None:
            self.canvas.setText("No model loaded")
            self.canvas.setPixmap(QtGui.QPixmap())
        else:
            self._compute_bb(model)
            self.frame_all()
            self._prewarm_textures(model)
            self._update_uv_viewer_model()
        self.modelChanged.emit(model)
        self._request_render()

    def set_model(self, model) -> None:
        self.load_model(model)

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
        if self._renderer.show_wireframe and self._renderer.show_solid:
            self.shade_combo.setCurrentText("Both")
        elif self._renderer.show_wireframe:
            self.shade_combo.setCurrentText("Wire")
        self._request_render()

    def toggle_bones(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_bones = bool(checked) if checked is not None else not self._renderer.show_bones
        self._request_render()

    def toggle_texture(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_texture = bool(checked) if checked is not None else not self._renderer.show_texture
        if self._renderer.show_texture and not self._renderer.show_solid:
            self.shade_combo.setCurrentText("Both")
        self._request_render()

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
        self.frame_all()

    def set_selected_node(self, node) -> None:
        self._renderer.selected_node = node
        if self._uv_viewer is not None:
            self._uv_viewer.set_selected_node(node)
        self.nodeSelected.emit(node)
        self._request_render()

    def refresh_node_transform(self, node=None) -> None:
        if node is not None:
            self._evict_transform_cache(node)
        else:
            self._renderer._wt_cache.clear()
        self._request_render()

    def set_anim_base_pose(self, base_pose) -> None:
        self._renderer.set_anim_base_pose(base_pose)

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0) -> None:
        self._renderer.set_animation_pose(pose, name=name, time=time, length=length)
        self._request_render(fast=True)

    def clear_animation_pose(self) -> None:
        self._renderer.set_animation_pose(None)
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
                if event.button() == QtCore.Qt.LeftButton:
                    self._press_lmb(event)
                    return True
                if event.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
                    self._press_pan(event)
                    return True
            if et == QtCore.QEvent.MouseMove:
                if event.buttons() & QtCore.Qt.LeftButton:
                    self._drag_lmb(event)
                    return True
                if event.buttons() & (QtCore.Qt.MiddleButton | QtCore.Qt.RightButton):
                    self._drag_pan(event)
                    return True
            if et == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton:
                    self._release_lmb(event)
                    return True
                if event.button() in (QtCore.Qt.MiddleButton, QtCore.Qt.RightButton):
                    self._release_pan(event)
                    return True
            if et == QtCore.QEvent.Wheel:
                steps = event.angleDelta().y() / 120.0
                self.camera.zoom(steps)
                self._renderer.is_interactive = False
                self._request_render()
                return True
            if et == QtCore.QEvent.KeyPress:
                key = event.key()
                if key == QtCore.Qt.Key_F:
                    self.frame_all(); return True
                if key == QtCore.Qt.Key_R:
                    self.reset_camera(); return True
                if key == QtCore.Qt.Key_W:
                    self.wire_button.click(); return True
                if key == QtCore.Qt.Key_B:
                    self.bones_button.click(); return True
                if key == QtCore.Qt.Key_T:
                    self.texture_button.click(); return True
                if key == QtCore.Qt.Key_G:
                    self.gimbal_button.click(); return True
                if key == QtCore.Qt.Key_Tab:
                    self.cycle_gimbal_mode(); return True
        return super().eventFilter(obj, event)

    def _request_render(self, fast: bool = False) -> None:
        self._render_pending = True
        self._render_timer.start(0 if fast else 16)

    def _render_now(self) -> None:
        if not self._render_pending:
            return
        self._render_pending = False
        if self.model is None:
            return
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        img = self._renderer.render(w, h)
        if img is None:
            mesh_count = len(self.model.mesh_nodes()) if hasattr(self.model, "mesh_nodes") else 0
            node_count = self.model.node_count() if hasattr(self.model, "node_count") else 0
            self.canvas.setText(f"{getattr(self.model, 'name', 'model')}\nRender unavailable\n{mesh_count} mesh | {node_count} nodes")
            return
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        qimg = QtGui.QImage(
            img.tobytes("raw", "RGBA"),
            img.width,
            img.height,
            img.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        self._pixmap = QtGui.QPixmap.fromImage(qimg)
        self.canvas.setPixmap(self._pixmap)

    def _on_shade_change(self, text: str) -> None:
        mode = "Wireframe" if text == "Wire" else text
        self._renderer.show_solid = mode in ("Solid", "Both")
        self._renderer.show_wireframe = mode in ("Wireframe", "Both")
        if self._renderer.show_texture and not self._renderer.show_solid and self._renderer.show_wireframe:
            self._renderer.show_solid = True
            if self.shade_combo.currentText() != "Both":
                self.shade_combo.setCurrentText("Both")
        self.wire_button.setChecked(self._renderer.show_wireframe)
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
            dx, dy = x - self._mx, y - self._my
            self._mx, self._my = x, y
            self.camera.orbit(dx * 0.4, -dy * 0.4)
            self._renderer.is_interactive = self._fast_drag_enabled
            self._request_render(fast=True)

    def _release_lmb(self, event) -> None:
        x, y = int(event.position().x()), int(event.position().y())
        if self._gimbal_dragging:
            self._gimbal_dragging = False
            self._renderer.gimbal_active_axis = None
            self._renderer.is_interactive = False
            self._renderer._wt_cache.clear()
            node = self._renderer.selected_node
            if node is not None:
                if self.on_node_moved:
                    self.on_node_moved(node)
                self.nodeMoved.emit(node)
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
