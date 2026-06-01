"""ViewportTransformCamera methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportTransformCameraMixin:
    @staticmethod
    def _snapshot_vertices(node):
        vertices = getattr(node, "vertices", None)
        if vertices is None:
            return None
        return tuple(tuple(float(c) for c in vertex[:3]) for vertex in vertices)

    @staticmethod
    def _optional_tuple_attr(node, name: str):
        raw = getattr(node, name, None)
        if raw is None:
            return None
        try:
            return tuple(float(v) for v in raw)
        except Exception:
            return None

    @staticmethod
    def _node_scale(node) -> tuple[float, float, float]:
        raw = getattr(node, "_gr_scale", getattr(node, "scale", (1.0, 1.0, 1.0)))
        try:
            values = tuple(float(v) for v in raw[:3])
        except Exception:
            values = (1.0, 1.0, 1.0)
        return (values + (1.0, 1.0, 1.0))[:3]

    @staticmethod
    def _quat_to_euler_degrees(q) -> tuple[float, float, float]:
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

    @staticmethod
    def _euler_degrees_to_quat(euler) -> tuple[float, float, float, float]:
        rx, ry, rz = (math.radians(float(v)) for v in tuple(euler)[:3])

        def axis_quat(axis: str, angle: float) -> tuple[float, float, float, float]:
            half = angle * 0.5
            s = math.sin(half)
            c = math.cos(half)
            if axis == "X":
                return (s, 0.0, 0.0, c)
            if axis == "Y":
                return (0.0, s, 0.0, c)
            return (0.0, 0.0, s, c)

        return multiply_quaternions(
            axis_quat("Z", rz),
            multiply_quaternions(axis_quat("Y", ry), axis_quat("X", rx)),
        )

    def cycle_gimbal_mode(self) -> None:
        self._transform_gizmo.cycle_mode()
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {self._transform_gizmo.mode.value.title()}")
        self._request_render()

    def set_gimbal_mode(self, mode: int) -> None:
        if mode == 2:
            self._transform_gizmo.set_mode(GizmoMode.ROTATE)
        elif mode == 3:
            self._transform_gizmo.set_mode(GizmoMode.SCALE)
        else:
            self._transform_gizmo.set_mode(GizmoMode.TRANSLATE)
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {self._transform_gizmo.mode.value.title()}")
        self._request_render(fast=True)

    def _set_transform_gizmo_mode(self, mode: GizmoMode) -> None:
        self._transform_gizmo.set_mode(mode)
        self._sync_legacy_gimbal_mode()
        self._sync_gimbal_mode_button()
        self._sync_transform_typein_bar()
        self.statusMessage.emit(f"Gizmo: {mode.value.title()}")
        self._request_render(fast=True)

    def _sync_legacy_gimbal_mode(self) -> None:
        if self._transform_gizmo.mode == GizmoMode.ROTATE:
            self._renderer.gimbal_mode = 2
        elif self._transform_gizmo.mode == GizmoMode.SCALE:
            self._renderer.gimbal_mode = 3
        else:
            self._renderer.gimbal_mode = 1

    def frame_all(self) -> None:
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max)
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._request_render()

    def frame_selection_or_all(self) -> None:
        bounds = self._selection_navigation_bounds()
        if bounds is not None:
            self.camera.frame_bounds(bounds[0], bounds[1])
        else:
            self.frame_all()
            return
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._request_render()

    def reset_camera(self) -> None:
        self.camera.__init__()
        if self.model:
            bb_min, bb_max = self._renderer._get_render_bounds()
            self.camera.frame_bounds(bb_min, bb_max, reset_view=True)
        if self.is_camera_view_active():
            self.update_camera_from_view()
        self._request_render()

    # ── M6 / T605 — Head-mode camera preset ──────────────────────────
    def apply_head_camera_preset(self) -> tuple:
        """Apply :data:`head_workflow.HEAD_CAMERA_PRESET` to the camera.

        Pulls the canonical ``(eye, target, up, fov_deg, clip)`` framing
        for Head mode from :func:`head_workflow.head_camera_preset` and
        converts the eye→target vector into the :class:`ArcBallCamera`'s
        spherical state ``(target, distance, azimuth, elevation)``,
        then sets ``fov``, ``_near`` and ``_far`` to match.  Triggers a
        single render request on success.

        Returns
        -------
        (ok, message) : Tuple[bool, str]
            ``ok=False`` is returned when ``head_workflow`` is
            unavailable or the preset payload is malformed.  Callers
            (M6 / T605 mode-switch glue) can surface ``message`` via
            the bottom strip / status bar.
        """
        # Lazy-import the workflow service — same fallback chain the
        # other M6 UI hooks use so we don't bind to a particular
        # ``sys.path`` layout.
        hw = None
        try:
            from src.core.characters import head_workflow as hw       # type: ignore
        except Exception:
            try:
                from core.characters import head_workflow as hw      # type: ignore
            except Exception:
                try:                                      # pragma: no cover
                    import importlib.util as _u
                    import pathlib as _pl
                    _here = _pl.Path(__file__).resolve().parents[1]
                    _hw_path = _here / "core" / "head_workflow.py"
                    if _hw_path.is_file():
                        _spec = _u.spec_from_file_location(
                            "_gr_head_workflow_inline_t605", str(_hw_path),
                        )
                        _mod = _u.module_from_spec(_spec)
                        import sys as _sys
                        _sys.modules[_spec.name] = _mod
                        _spec.loader.exec_module(_mod)
                        hw = _mod
                except Exception:
                    hw = None
        if hw is None:                                    # pragma: no cover
            return False, "head_workflow unavailable; head camera preset skipped."

        try:
            sph = hw.head_camera_spherical()
        except ValueError as exc:
            return False, f"Head camera preset malformed: {exc}"
        except Exception as exc:                          # pragma: no cover
            return False, f"head_camera_spherical() raised: {exc}"

        cam = self.camera
        cam.target    = [sph["target_x"], sph["target_y"], sph["target_z"]]
        cam.distance  = sph["distance"]
        cam.azimuth   = sph["azimuth"]
        cam.elevation = sph["elevation"]
        cam.fov       = sph["fov"]
        cam._near     = sph["near"]
        cam._far      = sph["far"]

        try:
            self._request_render()
        except Exception:                                 # pragma: no cover
            pass

        return True, (
            f"Head camera preset applied (fov={cam.fov:.1f}°, "
            f"dist={cam.distance:.2f})."
        )

    # ── T403: Mini-thumbnail inset wiring ──────────────────────────────
    def _reposition_thumbnail(self) -> None:
        """Pin the thumbnail to the top-right corner of the canvas."""
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        cw = max(0, self.canvas.width())
        x = cw - THUMBNAIL_WIDTH_PX - THUMBNAIL_MARGIN_PX
        y = THUMBNAIL_MARGIN_PX
        viewcube = getattr(self, "_viewcube_widget", None)
        if viewcube is not None and viewcube.isVisible():
            y = max(y, viewcube.y() + viewcube.height() + THUMBNAIL_MARGIN_PX)
        # Guard against collapsing canvases: if the widget would clip
        # off-screen, hide it rather than render half-off.
        if x < THUMBNAIL_MARGIN_PX or y + THUMBNAIL_HEIGHT_PX + THUMBNAIL_MARGIN_PX > self.canvas.height():
            self._thumbnail_widget.hide()
            return
        self._thumbnail_widget.move(x, y)
        self._apply_thumbnail_visibility()

    def _apply_thumbnail_visibility(self) -> None:
        """Combine user-setting + force-hide (Head close-up) flags."""
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        if self._thumbnail_force_hidden or not self._thumbnail_visible_setting:
            self._thumbnail_widget.hide()
            return
        # Only show once we actually have a model + a thumbnail to render.
        if self.model is None:
            self._thumbnail_widget.hide()
            return
        self._thumbnail_widget.show()
        self._thumbnail_widget.raise_()

    def set_thumbnail_visible(self, visible: bool) -> None:
        """User-level setting (Body / Creature modes)."""
        self._thumbnail_visible_setting = bool(visible)
        self._apply_thumbnail_visibility()

    def set_thumbnail_force_hidden(self, hidden: bool) -> None:
        """Auto-hide hook used by Head close-up mode."""
        self._thumbnail_force_hidden = bool(hidden)
        self._apply_thumbnail_visibility()

    @property
    def thumbnail_widget(self) -> Optional["_MiniThumbnailWidget"]:
        return getattr(self, "_thumbnail_widget", None)

    def refresh_thumbnail(self) -> None:
        """Re-render the neutral-pose thumbnail from the current model.

        Cheap to call: only runs when a model is loaded and the
        thumbnail is currently visible / configured-visible.  The
        render uses a *dedicated* throwaway camera + a clean
        FrameRenderer state (no joint overlay, no walkmesh, no
        gimbal) so the inset is a clean reference image.
        """
        if not hasattr(self, "_thumbnail_widget") or self._thumbnail_widget is None:
            return
        if self.model is None:
            self._thumbnail_widget.set_thumbnail(None)
            self._apply_thumbnail_visibility()
            return
        try:
            pixmap = self._render_neutral_pose_thumbnail(
                THUMBNAIL_WIDTH_PX - 4, THUMBNAIL_HEIGHT_PX - 4
            )
        except Exception as exc:
            log.debug("Thumbnail render failed: %s", exc)
            pixmap = None
        self._thumbnail_widget.set_thumbnail(pixmap)
        self._apply_thumbnail_visibility()

    def _refresh_thumbnail_safe(self) -> None:
        """Defensive wrapper around :meth:`refresh_thumbnail`.

        Used from hot paths (``load_model``, ``_render_now``) where a
        crash in the thumbnail render path must not propagate up and
        kill the main viewport.  Any exception is logged and swallowed.
        """
        try:
            self.refresh_thumbnail()
        except Exception as exc:
            log.debug("Thumbnail refresh suppressed: %s", exc)

    def _render_neutral_pose_thumbnail(self, w: int, h: int) -> Optional[QtGui.QPixmap]:
        """Render a clean, joint-overlay-free preview at neutral pose.

        Implementation notes:
          • Uses a private ``ArcBallCamera`` framed to the model bbox
            so the thumbnail composition is independent of the user's
            main-view camera (avoids zoomed-in / panned-off-screen
            thumbnails after the user pokes the main view).
          • Temporarily flips the renderer's ``show_bones`` /
            ``selected_node`` / animation state to neutral so the
            preview reads as a clean reference; original state is
            restored in a try/finally.
          • Uses the viewport GPU renderer only; if GPU rendering is
            unavailable, no CPU thumbnail is generated.
        """
        if self.model is None:
            return None
        ren = self._renderer
        # Snapshot state we are about to override.
        snap = {
            "show_bones": ren.show_bones,
            "selected_node": ren.selected_node,
            "show_gimbal": getattr(ren, "show_gimbal", False),
            "show_walkmesh": getattr(ren, "show_walkmesh", False),
            "show_wireframe": ren.show_wireframe,
            "anim_pose": getattr(ren, "_anim_pose", None),
        }
        # Use a private camera framed to the model bbox.
        main_cam = ren.cam
        try:
            thumb_cam = ArcBallCamera()
            try:
                bb_min, bb_max = ren._get_render_bounds()
                thumb_cam.frame_bounds(bb_min, bb_max, reset_view=True)
            except Exception:
                pass
            ren.cam = thumb_cam
            ren.show_bones = False
            ren.selected_node = None
            if hasattr(ren, "show_gimbal"):
                ren.show_gimbal = False
            if hasattr(ren, "show_walkmesh"):
                ren.show_walkmesh = False
            ren.show_wireframe = False
            if hasattr(ren, "_anim_pose"):
                ren._anim_pose = None
            img = None
            if self.model is not None:
                try:
                    if self._gpu_renderer is None:
                        self._gpu_renderer = create_viewport_renderer(self._renderer_settings)
                    self._preload_gpu_textures()
                    tex_cache = getattr(ren, "tex_cache", None)
                    textures = {
                        key: value
                        for key, value in getattr(tex_cache, "_cache", {}).items()
                        if value is not None
                    }
                    self._gpu_renderer.interactive = False
                    self._gpu_renderer.show_wireframe = False
                    self._gpu_renderer.show_grid = True
                    self._gpu_renderer.cull_faces = False
                    img = self._gpu_renderer.render(
                        self.model,
                        thumb_cam,
                        int(w),
                        int(h),
                        textures=textures,
                        anim_pose=None,
                        anim_time=0.0,
                        anim_base_pose=None,
                    )
                except Exception as exc:
                    log.debug("Thumbnail GPU render failed: %s", exc)
                    img = None
            if img is None:
                return None
        finally:
            ren.cam = main_cam
            ren.show_bones = snap["show_bones"]
            ren.selected_node = snap["selected_node"]
            if hasattr(ren, "show_gimbal"):
                ren.show_gimbal = snap["show_gimbal"]
            if hasattr(ren, "show_walkmesh"):
                ren.show_walkmesh = snap["show_walkmesh"]
            ren.show_wireframe = snap["show_wireframe"]
            if hasattr(ren, "_anim_pose"):
                ren._anim_pose = snap["anim_pose"]
        if img is None:
            return None
        try:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            qimg = QtGui.QImage(
                img.tobytes("raw", "RGBA"),
                img.width,
                img.height,
                img.width * 4,
                QtGui.QImage.Format_RGBA8888,
            ).copy()
            return QtGui.QPixmap.fromImage(qimg)
        except Exception as exc:
            log.debug("Thumbnail QImage conversion failed: %s", exc)
            return None

__all__ = ("ViewportTransformCameraMixin",)
