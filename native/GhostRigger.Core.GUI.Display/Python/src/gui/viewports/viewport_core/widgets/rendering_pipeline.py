"""ViewportRenderingPipeline methods for the Qt viewport widget."""

from __future__ import annotations

from types import SimpleNamespace

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportRenderingPipelineMixin:
    @staticmethod
    def _renderer_consumes_scene_lighting_render_data(renderer) -> bool:
        """Return whether the active backend consumes the shared light payload.

        ModernGL resolves the canonical room/model lights directly inside its
        retained renderer.  Building the WGPU/Pygfx payload for that backend is
        discarded by the renderer factory and walks every node in a stock module
        on every PIE frame.
        """
        backend_id = str(getattr(renderer, "backend_id", "") or "").strip().lower()
        return backend_id == "pygfx_wgpu" or backend_id.startswith("wgpu_")

    def _request_render(self, fast: bool = False, reason: str = "viewport change", **dirty_flags: bool) -> None:
        if hasattr(self, "_viewcube_widget") and self._viewcube_widget is not None and (fast or dirty_flags.get("camera")):
            self._viewcube_widget.update()
        self._render_pending = True
        now = time_module.perf_counter()
        governor = getattr(self, "_frame_governor", None)
        if governor is not None:
            governor.request_redraw(reason, **(dirty_flags or {"scene": True}))
        min_interval_ms = max(1, int(round(1000.0 / max(1, int(getattr(self._renderer_settings, "target_fps", 60) or 60)))))
        if getattr(self, "_dual_viewport_mode", False):
            min_interval_ms = max(min_interval_ms, 33)
        if fast:
            self._fast_frame_until = max(self._fast_frame_until, now + 0.08)
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            # Animation remains continuously eligible for rendering through the
            # frame governor, but it must still respect the target frame interval.
            # Dense PIE frames are synchronous; rearming this timer after 1 ms can
            # outrun the QLabel UpdateRequest posted by setPixmap(), so the scene
            # appears frozen until locomotion/animation stops.  Leaving one paced
            # event-loop window lets Qt present the completed frame and process
            # input without reducing animation-time fidelity.
            delay = max(1, int(min_interval_ms - elapsed_ms))
        else:
            elapsed_ms = (now - self._last_render_wall) * 1000.0 if self._last_render_wall else min_interval_ms
            delay = max(min_interval_ms, int(min_interval_ms - elapsed_ms))
        if self._render_timer.isActive():
            # A render request is a coalesced dirty-state notification, not a
            # timer reset.  PIE submits its newest camera/pose state every
            # 16 ms; restarting the same single-shot timer can perpetually move
            # its deadline and leave the last scene pixmap on screen while the
            # simulation and HUD continue advancing.
            return
        self._render_timer.start(delay)

    def set_runtime_qimage_compositor(self, callback, *, request_render: bool = True) -> None:
        """Install one GUI-thread compositor applied before the QPixmap publish."""

        self._runtime_qimage_compositor = callback if callable(callback) else None
        if request_render:
            self._request_render(
                fast=True,
                reason="runtime frame compositor changed",
                hud=True,
                overlay=True,
            )

    def _clear_live_surface_diagnostics(self) -> None:
        clear_text = getattr(getattr(self, "canvas", None), "clear_diagnostics_text", None)
        if callable(clear_text):
            clear_text()

    def _queue_post_load_gpu_refresh(self) -> None:
        self._post_load_refresh_model_id = id(self.model) if self.model is not None else 0
        self._post_load_refresh_timer.start(250)

    def _post_load_gpu_refresh(self) -> None:
        if self.model is None or id(self.model) != self._post_load_refresh_model_id:
            return
        self._request_render()

    def _on_texture_prewarm_finished(self, model_id: object) -> None:
        if self.model is not None and id(self.model) == model_id:
            self._queue_post_load_gpu_refresh()

    def _start_deferred_txi_metadata(self, model) -> None:
        if model is None or not getattr(model, "_gr_defer_txi_metadata", False):
            return
        try:
            setattr(model, "_gr_defer_txi_metadata", False)
        except Exception:
            pass
        model_id = id(model)
        renderer = self._renderer

        def load() -> None:
            try:
                renderer._load_txi_metadata_for_model(model)
            except Exception:
                log.debug("Deferred TXI metadata load failed", exc_info=True)
            self._deferredTxiFinished.emit(model_id)

        threading.Thread(target=load, daemon=True, name="qt-txi-prewarm").start()

    def _on_deferred_txi_finished(self, model_id: object) -> None:
        if self.model is not None and id(self.model) == model_id:
            self._prewarm_textures(self.model)
            self._queue_post_load_gpu_refresh()

    def _render_now(self) -> None:
        if not self._render_pending:
            return
        now = time_module.perf_counter()
        governor = getattr(self, "_frame_governor", None)
        if governor is not None and not governor.should_render_now(now):
            if self._render_pending and (governor.dirty or governor.active_interaction or governor.animation_playing):
                self._render_timer.start(governor.delay_until_next_frame_ms(now))
            return
        self._render_pending = False
        w = max(8, self.canvas.width())
        h = max(8, self.canvas.height())
        t0 = time_module.perf_counter()
        render_reason = str(getattr(governor, "pending_reason", "") or "viewport render")
        try:
            img = self._render_frame(w, h)
        except Exception as exc:
            log.error("GPU viewport render failed for %s: %s", getattr(self.model, "name", "scene"), exc, exc_info=True)
            img = None
        self._last_render_ms = (time_module.perf_counter() - t0) * 1000.0
        self._last_render_wall = time_module.perf_counter()
        if governor is not None:
            governor.mark_clean_after_render(render_reason, self._last_render_wall)
        if img is None:
            if self.model is None:
                if bool(self.property("_gr_suppress_renderer_diagnostics")) or (
                    hasattr(self, "_map_studio_should_hide_empty_scene_label")
                    and self._map_studio_should_hide_empty_scene_label()
                ):
                    self.canvas.setText("")
                else:
                    self.canvas.setText("GPU render unavailable\nEmpty Scene")
                return
            mesh_count = len(self.model.mesh_nodes()) if hasattr(self.model, "mesh_nodes") else 0
            node_count = self.model.node_count() if hasattr(self.model, "node_count") else 0
            self.canvas.setText(f"{getattr(self.model, 'name', 'model')}\nGPU render unavailable\n{mesh_count} mesh | {node_count} nodes")
            return
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        self._update_fps()
        if self.canvas.is_live_surface() and bool(getattr(self, "_skip_overlay_pixmap_update", False)):
            rendered_size = (w, h)
            self._last_rendered_canvas_size = rendered_size
            current_size = (max(8, self.canvas.width()), max(8, self.canvas.height()))
            if current_size != rendered_size:
                self._request_render()
            return
        qimg = QtGui.QImage(
            img.tobytes("raw", "RGBA"),
            img.width,
            img.height,
            img.width * 4,
            QtGui.QImage.Format_RGBA8888,
        ).copy()
        compositor = getattr(self, "_runtime_qimage_compositor", None)
        if callable(compositor):
            try:
                compositor(qimg)
            except Exception as exc:
                log.warning("Runtime frame compositor failed: %s", exc, exc_info=True)
        self._pixmap = QtGui.QPixmap.fromImage(qimg)
        if self.canvas.is_live_surface():
            self.canvas.set_overlay_pixmap(self._pixmap)
        else:
            present = getattr(self.canvas, "present_pixmap", None)
            if callable(present):
                # A runtime compositor means PIE owns this full retained frame.
                # Finish the QLabel paint now so a due simulation/render timer
                # cannot starve presentation until movement stops.
                present(self._pixmap, immediate=callable(compositor))
            else:
                self.canvas.setPixmap(self._pixmap)
        rendered_size = (w, h)
        self._last_rendered_canvas_size = rendered_size
        current_size = (max(8, self.canvas.width()), max(8, self.canvas.height()))
        if current_size != rendered_size:
            self._request_render()

    def _render_frame(self, w: int, h: int):
        self._skip_overlay_pixmap_update = False
        self._use_gpu = True
        img = self._render_gpu_frame(w, h)
        if img is None:
            self._set_renderer_badge(False)
            return None
        self._set_renderer_badge(True)
        if bool(self.property("_gr_map_studio_pie_clean_runtime")):
            # ModernGL returns a composited image rather than a native child
            # surface.  Returning its scene image here is the backend-neutral
            # counterpart to the live-surface overlay guard: no axes, helper
            # diamonds, placement guides, selections, measurements, or HUD
            # diagnostics are painted over the runtime frame.
            self._clear_live_surface_diagnostics()
            if self.canvas.is_live_surface():
                self._skip_overlay_pixmap_update = True
            self._record_overlay_rebuild(0.0)
            return img
        if self.canvas.is_live_surface() and self._gpu_renderer_requires_native_surface_passthrough():
            self._update_live_surface_diagnostics()
            img = self._draw_live_surface_tool_overlay(img, w, h)
            if bool(getattr(self, "_skip_overlay_pixmap_update", False)):
                return img
            img = self._draw_performance_overlay(img, w, h)
            return img
        self._clear_live_surface_diagnostics()
        if self._can_skip_live_overlay_rebuild():
            self._skip_overlay_pixmap_update = True
            return img
        img = self._draw_gpu_viewport_overlays(img, w, h)
        img = self._draw_performance_overlay(img, w, h)
        return img

    def _draw_live_surface_tool_overlay(self, img, w: int, h: int):
        """Draw editor tools over a renderer-owned live surface.

        pygfx owns the retained 3D scene; this transparent image is only for
        legacy screen-space tools that are still Qt/PIL overlay based.
        """
        if bool(getattr(self, "_live_surface_overlay_suppressed", False)):
            # Do not place a QWidget/QPixmap over a native child surface while
            # it is animating.  On Windows the child HWND and Qt sibling do not
            # have reliable per-pixel composition ordering, which presents as
            # whole-frame black/blank flicker.  PIE exposes its status in the
            # surrounding Qt HUD and renders moving actors natively instead.
            self._record_overlay_rebuild(0.0)
            self._skip_overlay_pixmap_update = True
            return img
        if self._can_skip_animation_cpu_overlay():
            self._record_overlay_rebuild(0.0)
            self._skip_overlay_pixmap_update = True
            return img
        try:
            from PIL import Image

            overlay = Image.new("RGBA", (max(1, int(w)), max(1, int(h))), (0, 0, 0, 0))
        except Exception:
            overlay = img
        return self._draw_gpu_viewport_overlays(overlay, w, h)

    def _can_skip_live_overlay_rebuild(self) -> bool:
        if not self.canvas.is_live_surface():
            return False
        if not bool(getattr(self._renderer_settings, "overlay_dirty_rendering", True)):
            return False
        if self._pixmap is None:
            return False
        governor = getattr(self, "_frame_governor", None)
        dirty_flags = dict(getattr(governor, "dirty_flags", {}) or {})
        selected_node = getattr(getattr(self, "_renderer", None), "selected_node", None)
        if (
            self._gpu_renderer_supports_native_gizmo_drawing()
            and bool(dirty_flags.get("gizmo", False))
            and not bool(getattr(selected_node, "is_camera", False))
            and not any(
                bool(dirty_flags.get(name, False))
                for name in ("camera", "overlay", "resources", "selection", "lighting", "diagnostics", "hud")
            )
        ):
            return True
        if any(bool(dirty_flags.get(name, False)) for name in ("camera", "overlay", "resources", "selection", "lighting", "gizmo", "diagnostics", "hud")):
            return False
        if bool(getattr(self, "_xray_mode", False) or getattr(self, "_weight_heatmap_enabled", False)):
            return False
        if governor is not None and governor.animation_playing:
            if self._can_skip_animation_cpu_overlay():
                return True
            return bool(dirty_flags.get("scene", False))
        if bool(getattr(self._renderer, "show_bones", False) or getattr(self._renderer, "show_walkmesh", False)):
            return False
        if getattr(self._renderer, "_ext_skeleton", None) is not None:
            return False
        return bool(dirty_flags.get("scene", False))

    def _gpu_renderer_requires_native_surface_passthrough(self) -> bool:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return False
        backend_id = str(getattr(renderer, "backend_id", "") or "").lower()
        if backend_id == "pygfx_wgpu":
            return True
        try:
            diagnostics = renderer.get_diagnostics() if hasattr(renderer, "get_diagnostics") else {}
            return bool((diagnostics or {}).get("native_surface_passthrough", False))
        except Exception:
            return False

    def _can_skip_animation_cpu_overlay(self) -> bool:
        governor = getattr(self, "_frame_governor", None)
        if governor is None or not bool(getattr(governor, "animation_playing", False)):
            return False
        if not self._gpu_renderer_supports_native_skeleton_overlay():
            return False
        if bool(getattr(self, "_xray_mode", False) or getattr(self, "_weight_heatmap_enabled", False)):
            return False
        if bool(getattr(getattr(self, "_renderer", None), "show_walkmesh", False)):
            return False
        if getattr(getattr(self, "_renderer", None), "_ext_skeleton", None) is not None:
            return False
        if bool(getattr(self, "_joint_marquee_selecting", False)):
            return False
        return True

    def _update_live_surface_diagnostics(self) -> None:
        set_text = getattr(self.canvas, "set_diagnostics_text", None)
        clear_text = getattr(self.canvas, "clear_diagnostics_text", None)
        if not callable(set_text):
            return
        if bool(self.property("_gr_suppress_renderer_diagnostics")):
            if callable(clear_text):
                clear_text()
            return
        if not bool(getattr(self._renderer_settings, "show_renderer_diagnostics", True)):
            if callable(clear_text):
                clear_text()
            return
        text = self._live_surface_diagnostics_text()
        if text:
            set_text(text)
        elif callable(clear_text):
            clear_text()

    def _live_surface_diagnostics_text(self) -> str:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return ""
        try:
            diagnostics = renderer.get_diagnostics() if hasattr(renderer, "get_diagnostics") else {}
        except Exception:
            diagnostics = {}
        bridge = diagnostics or {}
        lines = self._renderer_statistics_lines(renderer, bridge)
        adapter = dict((diagnostics or {}).get("adapter") or {})
        adapter_name = str(
            adapter.get("description")
            or adapter.get("device")
            or adapter.get("name")
            or ""
        )
        if len(adapter_name) > 48:
            adapter_name = adapter_name[:45] + "..."
        if adapter_name:
            lines.append(adapter_name)
        counters = []
        for label, key in (
            ("Geo", "geometry_updates_this_frame"),
            ("Dyn", "dynamic_geometry_updates_this_frame"),
            ("Mat", "material_updates_this_frame"),
            ("Lights", "light_overlay_segments"),
            ("Bones", "skeleton_overlay_segments"),
        ):
            value = int(bridge.get(key, 0) or 0)
            if value:
                counters.append(f"{label} {value}")
        if counters:
            lines.append("  ".join(counters))
        reason = str(bridge.get("reason") or "")
        if reason:
            lines.append(f"Last: {reason[:72]}")
        return "\n".join(lines)

    def _draw_xray_grid_overlay(self, img, w: int, h: int):
        if img is None:
            return None
        try:
            from PIL import Image, ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            self._renderer._draw_grid(ImageDraw.Draw(overlay, "RGBA"), w, h)
            return Image.alpha_composite(img, overlay)
        except Exception as exc:
            log.debug("X-Ray grid overlay draw failed: %s", exc)
            return img

    def _render_gpu_frame(self, w: int, h: int):
        if self._gpu_renderer is None:
            self._gpu_renderer = create_viewport_renderer(self._renderer_settings)
            theme = getattr(self, "_current_theme", None)
            if theme is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
                self._gpu_renderer.set_theme_colors(theme)
            else:
                self._apply_native_palette_to_renderers()
            self._sync_renderer_surface(force=True)
        else:
            self._sync_renderer_surface()
        self._preload_gpu_textures()
        textures = self._gpu_texture_snapshot()
        clean_runtime = bool(self.property("_gr_map_studio_pie_clean_runtime"))
        self._gpu_renderer.interactive = bool(
            self._renderer.is_interactive
            or self._pan_dragging
            or self._nav_dragging
            or self._is_dragging
            or time_module.perf_counter() < self._fast_frame_until
            # PIE is a continuously interactive runtime even when the mouse is
            # not held.  Keeping it on the stationary editor path forced a 4x
            # MSAA resolve and alpha-composite readback for every locomotion
            # frame, which made dense stock modules visibly stutter.  The
            # renderer's interactive path remains full resolution by default.
            or clean_runtime
        )
        self._gpu_renderer.show_solid = bool(self._renderer.show_solid)
        self._gpu_renderer.show_texture = bool(self._renderer.show_texture)
        self._gpu_renderer.show_diffuse_map = bool(getattr(self._renderer, "show_diffuse_map", True))
        self._gpu_renderer.show_lightmap_map = bool(getattr(self._renderer, "show_lightmap_map", True))
        self._gpu_renderer.show_environment_map = bool(getattr(self._renderer, "show_environment_map", True))
        self._gpu_renderer.show_specular_map = bool(getattr(self._renderer, "show_specular_map", True))
        self._gpu_renderer.show_normal_map = bool(getattr(self._renderer, "show_normal_map", True))
        self._gpu_renderer.lighting_mode = str(getattr(self._renderer, "lighting_mode", "scene") or "scene")
        self._gpu_renderer.scene_ambient = float(getattr(self._renderer, "scene_ambient", 0.06))
        self._gpu_renderer.lightmap_intensity = float(getattr(self._renderer, "lightmap_intensity", 0.55))
        self._gpu_renderer.lightmap_mode = str(getattr(self._renderer, "lightmap_mode", "baked") or "baked")
        self._gpu_renderer.show_light_gizmos = bool(
            getattr(self._renderer, "show_light_gizmos", True)
        ) and not clean_runtime
        self._gpu_renderer.show_light_radius_volumes = bool(
            getattr(self._renderer, "show_light_radius_volumes", False)
        ) and not clean_runtime
        self._gpu_renderer.show_dummy_helpers = bool(
            getattr(self._renderer, "show_dummy_helpers", True)
        ) and not clean_runtime
        self._gpu_renderer.show_wireframe = bool(self._renderer.show_wireframe)
        self._gpu_renderer.render_mode = str(getattr(self._renderer, "render_mode", "realistic") or "realistic")
        self._gpu_renderer.display_options = self.display_options
        self._gpu_renderer.selected_node = None if clean_runtime else getattr(self._renderer, "selected_node", None)
        self._gpu_renderer.selected_nodes = [] if clean_runtime else list(getattr(self, "_selected_meshes", []) or [])
        self._gpu_renderer.show_grid = bool(getattr(self._renderer, "show_grid", True))
        self._gpu_renderer.show_particles = bool(getattr(self._renderer, "show_particles", True))
        self._gpu_renderer.show_bones = bool(getattr(self._renderer, "show_bones", False)) and not clean_runtime
        self._gpu_renderer.show_joint_dots = bool(getattr(self, "_joint_dot_enabled", True)) and not clean_runtime
        self._gpu_renderer._hovered_bone = getattr(self._renderer, "_hovered_bone", None)
        self._gpu_renderer.cull_faces = False
        gizmo_render_data = None if clean_runtime else self._build_transform_gizmo_render_data(w, h)
        skeleton_render_data = None
        if not clean_runtime and bool(getattr(self._renderer, "show_bones", False)):
            try:
                from src.core.rendering.skeleton_render_data import build_skeleton_render_data

                skeleton_render_data = build_skeleton_render_data(
                    self.model,
                    anim_pose=getattr(self._renderer, "_anim_pose", None),
                    selected_node=getattr(self._renderer, "selected_node", None),
                    selected_nodes=list(getattr(self, "_selected_joint_nodes", []) or []),
                    hovered_node=getattr(self._renderer, "_hovered_bone", None),
                    show_dots=bool(getattr(self, "_joint_dot_enabled", True)),
                    show_links=True,
                )
            except Exception as exc:
                log.debug("WGPU skeleton render data build failed: %s", exc)
        lighting_render_data = None
        if self._renderer_consumes_scene_lighting_render_data(self._gpu_renderer):
            try:
                from src.core.lighting.render_data import build_scene_lighting_render_data

                lighting_render_data = build_scene_lighting_render_data(
                    self.model,
                    selected_node=None if clean_runtime else getattr(self._renderer, "selected_node", None),
                    hovered_node=None if clean_runtime else getattr(self._renderer, "_hovered_light", None),
                    ambient_color_rgb=float(getattr(self._renderer, "scene_ambient", 0.06)),
                    mode=str(getattr(self._renderer, "lighting_mode", "scene") or "scene"),
                    rig=str(getattr(self._renderer, "lighting_rig", "kotor_original") or "kotor_original"),
                    complexity=str(getattr(self._renderer, "shader_complexity_mode", "basic") or "basic"),
                    show_helpers=bool(getattr(self._renderer, "show_light_gizmos", True)) and not clean_runtime,
                    show_volumes=bool(getattr(self._renderer, "show_light_radius_volumes", False)) and not clean_runtime,
                    diffuse_enabled=bool(getattr(self._renderer, "show_diffuse_map", True)),
                    specular_enabled=bool(getattr(self._renderer, "show_specular_map", True)),
                    normal_enabled=bool(getattr(self._renderer, "show_normal_map", True)),
                    environment_enabled=bool(getattr(self._renderer, "show_environment_map", True)),
                    lightmap_enabled=bool(getattr(self._renderer, "show_lightmap_map", True)),
                    lm_intensity=float(getattr(self._renderer, "lightmap_intensity", 0.55)),
                    lm_mode=str(getattr(self._renderer, "lightmap_mode", "baked") or "baked"),
                )
            except Exception as exc:
                log.debug("WGPU lighting render data build failed: %s", exc)
        helper_render_data = None
        if not clean_runtime and str(getattr(self._gpu_renderer, "backend_id", "") or "") == "pygfx_wgpu":
            helper_render_data = self._build_pygfx_helper_render_data()
        try:
            self._gpu_renderer.surface_host_diagnostics = self.canvas.diagnostics()
        except Exception:
            pass
        try:
            self._gpu_renderer.viewport_frame_governor_diagnostics = self._frame_governor.diagnostics()
            self._gpu_renderer.viewport_overlay_diagnostics = self._overlay_diagnostics()
        except Exception:
            pass
        dirty_flags = {}
        try:
            dirty_flags = dict(getattr(self._frame_governor, "dirty_flags", {}) or {})
        except Exception:
            dirty_flags = {}
        img = self._gpu_renderer.render(
            self.model,
            self.camera,
            w,
            h,
            textures=textures,
            display_options=self.display_options,
            gizmo_render_data=gizmo_render_data,
            skeleton_render_data=skeleton_render_data,
            lighting_render_data=lighting_render_data,
            helper_render_data=helper_render_data,
            picking_diagnostics=self._viewport_picking_diagnostics(),
            hovered_node=None if clean_runtime else getattr(self, "_hovered_mesh_node", None),
            show_mesh_hover=bool(getattr(self, "mesh_hover_enabled", True)) and not clean_runtime,
            anim_pose=getattr(self._renderer, "_anim_pose", None),
            anim_time=float(getattr(self._renderer, "_anim_time", 0.0)),
            anim_base_pose=getattr(self._renderer, "_anim_base_pose", None),
            anim_name=(
                str(getattr(self._renderer, "_anim_name", "") or "")
                if getattr(self._renderer, "_anim_pose", None) is not None
                else ""
            ),
            dirty_flags=dirty_flags,
        )
        diagnostics = {}
        get_diagnostics = getattr(self._gpu_renderer, "get_diagnostics", None)
        if callable(get_diagnostics):
            try:
                diagnostics = get_diagnostics() or {}
            except Exception:
                diagnostics = {}
        backend_id = str(diagnostics.get("backend_id") or getattr(self._gpu_renderer, "backend_id", "") or "")
        if backend_id and (
            self.canvas.surface_backend_id() != backend_id
            or self.canvas.is_live_surface() != self._renderer_uses_live_surface(backend_id)
        ):
            self._sync_renderer_surface(force=True)
        if backend_id and backend_id != self._last_renderer_backend_id:
            self._last_renderer_backend_id = backend_id
            label = str(diagnostics.get("name") or backend_id)
            self.statusMessage.emit(f"Renderer: {label}")
            self._refresh_display_button_availability()
            self._emit_render_state_changed()
        warning = str(diagnostics.get("last_display_mode_warning") or "")
        if warning and warning != self._last_display_mode_warning:
            self._last_display_mode_warning = warning
            self.statusMessage.emit(warning)
        elif not warning:
            self._last_display_mode_warning = ""
        if getattr(self._gpu_renderer, "deferred_mesh_uploads", False):
            model_id = id(self.model)

            def _continue_uploads() -> None:
                if self.model is not None and id(self.model) == model_id:
                    self._request_render(fast=True)

            QtCore.QTimer.singleShot(1, _continue_uploads)
        if bool(getattr(self._gpu_renderer, "particles_active", False)):
            # Visible emitter particles keep their own frame cadence alive, the
            # same way animation playback does.  The reschedule stops as soon as
            # every particle batch fades out or the model changes.  These frames
            # deliberately stay on the quality path (fast=True would pin the
            # renderer in no-MSAA interactive mode for as long as any particle
            # is visible, leaving sprites aliased and washed out).
            particle_model_id = id(self.model)
            interval_ms = max(
                16,
                int(round(1000.0 / max(1, int(getattr(self._renderer_settings, "target_fps", 60) or 60)))),
            )

            def _advance_particles() -> None:
                if self.model is not None and id(self.model) == particle_model_id:
                    self._request_render(reason="particle simulation", scene=True)

            QtCore.QTimer.singleShot(interval_ms, _advance_particles)
        if self._gpu_upload_total > 0 and self.model is not None and id(self.model) == self._gpu_upload_model_id:
            uploaded = min(len(getattr(self._gpu_renderer, "_mesh_cache", {}) or {}), self._gpu_upload_total)
            if not getattr(self._gpu_renderer, "deferred_mesh_uploads", False):
                uploaded = self._gpu_upload_total
            self.gpuUploadProgress.emit(uploaded, self._gpu_upload_total)
            if uploaded >= self._gpu_upload_total:
                self._gpu_upload_total = 0
                self._gpu_upload_model_id = 0
        return img

    def _build_pygfx_helper_render_data(self):
        if self.model is None:
            return None
        if not bool(getattr(self._renderer, "show_dummy_helpers", getattr(self, "_dummy_helpers_visible", True))):
            return None
        try:
            nodes = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            return None
        selected = getattr(self._renderer, "selected_node", None)
        selected_ids = {id(node) for node in getattr(self, "_selected_viewport_nodes", []) or []}
        hovered = getattr(self, "_hovered_helper_node", None)
        helpers = []
        for node in nodes:
            if not self._is_general_helper_node(node):
                continue
            if bool(getattr(node, "_gr_hidden", False)):
                continue
            try:
                position = self._helper_world_position(node)
            except Exception:
                continue
            helpers.append(
                SimpleNamespace(
                    position=position,
                    selected=node is selected or id(node) in selected_ids or bool(getattr(node, "_gr_selected", False)),
                    hovered=node is hovered,
                    visible=True,
                )
            )
        if not helpers:
            return None
        return SimpleNamespace(helpers=tuple(helpers))

    def _draw_gpu_viewport_overlays(self, img, w: int, h: int):
        """Draw screen-space viewport tools over an already-rendered GPU frame.

        This intentionally does not call FrameRenderer.render() or any CPU mesh
        rasterizer.  It only restores the interactive overlay layer that lives
        above the GPU scene: gimbal tools, transform gizmo, HUD stats, axes,
        hover outlines, subobject selection, measurement/camera helpers, and editor markers.
        """
        if img is None:
            return None
        overlay_started = time_module.perf_counter()
        try:
            from PIL import Image, ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            # Every editor guide is transient.  Keep brushes, placement ghosts,
            # selections, gizmos, helpers, walkmesh guides, and future building
            # previews on a disposable transparent layer instead of mutating the
            # renderer's scene image.  Retained backends may reuse their last
            # readback for overlay-only frames; direct drawing then leaves old
            # guides behind as cyan/selection "paint" trails.
            scene_img = img
            overlay_img = Image.new("RGBA", scene_img.size, (0, 0, 0, 0))
            self._renderer._last_W = w
            self._renderer._last_H = h
            try:
                self._renderer._frame_view = self._renderer._cam_view_matrix()
                self._renderer._frame_verts_cache = {}
                self._renderer._frame_norms_cache = {}
            except Exception:
                pass
            draw = ImageDraw.Draw(overlay_img, "RGBA")
            # Map Studio camera navigation is a latency-sensitive interaction.
            # The final mouse-release frame restores every authoring guide, but
            # orbit/pan/zoom frames retain only feedback needed to understand
            # selection and placement.  On 207tel, diagnostics plus unrelated
            # room/helper overlays consumed roughly 7 ms of every Qt frame.
            map_interaction_lod = bool(
                getattr(self, "_map_studio_authoring_chrome_enabled", False)
                and getattr(self, "_nav_dragging", "")
            )
            if self._xray_mode:
                self._renderer._draw_grid(draw, w, h)
            # T405: weight heat-map runs BEFORE bones so the joint dots
            # stay clearly visible on top of the colored vertex cloud.
            if self._weight_heatmap_enabled:
                self._draw_weight_heatmap(draw, w, h)
            native_skeleton = self._gpu_renderer_supports_native_skeleton_overlay()
            if self._renderer.show_bones and not native_skeleton:
                self._renderer._draw_bones(draw, w, h)
                if self._locomotion_disc_enabled:
                    self._draw_locomotion_discs(overlay_img, w, h)
                # T401: paint AccuRig-style color-coded joint dots on top.
                # Runs only when the skeleton is visible — the dots are
                # meant to make joints clickable/identifiable during rig
                # editing.  Cheap (one pass over `_bone_screen_positions`).
                if self._joint_dot_enabled:
                    self._draw_joint_dots(overlay_img, w, h)
            if getattr(self._renderer, "_ext_skeleton", None) is not None:
                self._renderer._draw_ext_skeleton(draw, w, h)
            if getattr(self._renderer, "_character_fit_overlay", None):
                self._renderer._draw_character_fit_overlay(draw, w, h)
            if self._renderer.show_walkmesh:
                self._renderer._draw_walkmesh_overlay(draw, w, h)
            if not map_interaction_lod:
                self._draw_camera_helpers(draw, w, h)
                self._draw_map_studio_terrain_walkability(draw, w, h)
            self._draw_map_studio_component_selection(draw, w, h)
            self._draw_map_studio_component_extrude_gizmo(draw, w, h)
            self._draw_map_studio_modeling_points_overlay(draw, w, h)
            self._draw_map_studio_hover_highlight(draw, w, h)
            self._draw_map_studio_terrain_brush_cursor(draw, w, h)
            self._draw_map_studio_texture_paint_cursor(draw, w, h)
            if not map_interaction_lod:
                self._draw_map_studio_room_outlines(draw, w, h)
            self._draw_map_studio_building_preview(draw, w, h)
            self._draw_map_studio_universal_transform_overlay(draw, w, h)
            self._draw_map_studio_placement_markers(draw, w, h)
            if not map_interaction_lod:
                self._draw_wgpu_helper_markers(draw, w, h)
            if self._ensure_renderer_gimbal_state() and not self._gpu_renderer_supports_native_gizmo_drawing():
                self._draw_transform_gizmo(draw, w, h)
            if not map_interaction_lod:
                self._draw_measurement_overlay(draw, w, h)
            self._draw_selected_model_outline(draw, w, h)
            self._draw_mesh_subobject_selection(draw, w, h)
            if not map_interaction_lod:
                self._draw_joint_marquee(draw)
            self._renderer._draw_axes(draw, w, h)
            if not map_interaction_lod and not bool(self.property("_gr_suppress_renderer_diagnostics")):
                self._renderer._draw_stats(draw, w, h)
                self._draw_renderer_statistics_overlay(draw, w, h)
            if not map_interaction_lod:
                self._draw_active_camera_overlays(draw, w, h)
            self._record_overlay_rebuild(time_module.perf_counter() - overlay_started)
            return Image.alpha_composite(scene_img, overlay_img)
        except Exception as exc:
            log.debug("Qt GPU overlay draw failed: %s", exc)
            return img

    def _draw_renderer_statistics_overlay(self, draw, w: int, h: int) -> None:
        if not bool(getattr(self._renderer_settings, "show_renderer_diagnostics", True)):
            return
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return
        try:
            diagnostics = renderer.get_diagnostics() if hasattr(renderer, "get_diagnostics") else {}
        except Exception:
            diagnostics = {}
        lines = self._renderer_statistics_lines(renderer, diagnostics or {})
        if not lines:
            return
        hud_fill = getattr(self._renderer, "hud_fill", (30, 34, 40))
        hud_text = getattr(self._renderer, "hud_text", (213, 220, 230))
        hud_outline = getattr(self._renderer, "hud_outline", (78, 88, 102))
        hud_muted = getattr(self._renderer, "hud_muted_text", (165, 176, 190))
        max_width = max(120, min(520, w - 184))
        y = 84
        if getattr(self._renderer, "_anim_pose", None) is not None and getattr(self._renderer, "_anim_name", ""):
            y += 22
        for index, line in enumerate(lines[:3]):
            self._renderer._draw_hud_pill(
                draw,
                12,
                min(max(12, h - 84), y + index * 22),
                line,
                fill=hud_fill,
                fg=hud_text if index == 0 else hud_muted,
                outline=hud_outline,
                max_width=max_width,
            )

    def _renderer_statistics_lines(self, renderer, diagnostics: dict) -> list[str]:
        name = str(diagnostics.get("name") or getattr(renderer, "name", "") or diagnostics.get("backend_id") or "Renderer")
        backend = str(diagnostics.get("backend") or diagnostics.get("api") or "")
        gpu = str(diagnostics.get("gpu") or "")
        if len(gpu) > 42:
            gpu = gpu[:39] + "..."
        perf = dict(diagnostics.get("performance") or {})
        perf_summary = perf.get("summary") if isinstance(perf.get("summary"), dict) else {}

        def _number(*keys: str) -> float:
            for key in keys:
                if key in perf:
                    try:
                        return float(perf.get(key) or 0.0)
                    except Exception:
                        pass
                if isinstance(perf_summary, dict) and key in perf_summary:
                    try:
                        return float(perf_summary.get(key) or 0.0)
                    except Exception:
                        pass
            return 0.0

        frame_ms = _number("frame_time_ms", "last_frame_ms", "cpu_frame_ms")
        draw_ms = _number("draw_ms")
        upload_ms = _number("upload_ms", "gpu_upload_ms", "geometry_upload_ms")
        readback_ms = _number("readback_ms")
        renderer_perf = getattr(renderer, "perf", {})
        renderer_tris = renderer_perf.get("tri_count", 0) if isinstance(renderer_perf, dict) else 0
        tris = int(diagnostics.get("triangle_count") or diagnostics.get("tri_count") or renderer_tris or 0)
        cache = int(diagnostics.get("mesh_cache_size") or 0)
        lines = [f"{name}{(' / ' + backend) if backend and backend not in name else ''}"]
        timing = f"Frame {frame_ms:.1f} ms"
        if draw_ms > 0.0:
            timing += f"  Draw {draw_ms:.1f}"
        if upload_ms > 0.0:
            timing += f"  Upload {upload_ms:.1f}"
        if readback_ms > 0.0:
            timing += f"  Read {readback_ms:.1f}"
        timing += f"  Tris {tris:,}"
        lines.append(timing)
        details = []
        if gpu:
            details.append(gpu)
        if cache:
            details.append(f"Meshes {cache}")
        texture_cache = int(diagnostics.get("texture_cache_size") or 0)
        if texture_cache:
            details.append(f"Textures {texture_cache}")
        if details:
            lines.append("  |  ".join(details))
        return lines

    def _record_overlay_rebuild(self, elapsed_s: float = 0.0) -> None:
        self._overlay_rebuild_count += 1
        now = time_module.perf_counter()
        window = max(1.0e-6, now - float(getattr(self, "_overlay_rebuild_window_started", now)))
        if window >= 1.0:
            self._overlay_rebuild_rate_hz = self._overlay_rebuild_count / window
            self._overlay_rebuild_count = 0
            self._overlay_rebuild_window_started = now
        self._last_overlay_rebuild_ms = float(elapsed_s) * 1000.0

    def _overlay_diagnostics(self) -> dict[str, object]:
        return {
            "dirty_rendering": bool(getattr(self._renderer_settings, "overlay_dirty_rendering", True)),
            "rebuild_rate_hz": round(float(getattr(self, "_overlay_rebuild_rate_hz", 0.0)), 2),
            "last_rebuild_ms": round(float(getattr(self, "_last_overlay_rebuild_ms", 0.0)), 3),
            "texture_snapshot_rebuilds": int(getattr(self, "_gpu_texture_snapshot_rebuilds", 0)),
            "live_overlay_layer": bool(self.canvas.is_live_surface()) if hasattr(self, "canvas") else False,
        }

    def _draw_cpu_overlays(self, img, w: int, h: int, *, gpu_base: bool = False):
        return self._draw_gpu_viewport_overlays(img, w, h)

    def _draw_transform_gizmo_overlay(self, img, w: int, h: int):
        if img is None:
            return None
        try:
            from PIL import Image, ImageDraw

            if img.mode != "RGBA":
                img = img.convert("RGBA")
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            self._renderer._last_W = w
            self._renderer._last_H = h
            self._renderer._frame_view = self._renderer._cam_view_matrix()
            draw = ImageDraw.Draw(overlay, "RGBA")
            self._draw_camera_helpers(draw, w, h)
            self._draw_transform_gizmo(draw, w, h)
            self._draw_measurement_overlay(draw, w, h)
            self._draw_active_camera_overlays(draw, w, h)
            return Image.alpha_composite(img, overlay)
        except Exception as exc:
            log.debug("Transform gizmo overlay draw failed: %s", exc)
            return img

    def _build_transform_gizmo_render_data(self, w: int, h: int):
        if not self._ensure_renderer_gimbal_state():
            return None
        node = self._active_gizmo_node()
        if node is None:
            return None
        try:
            wp = self._gizmo_world_position(node)
            setattr(node, "_gr_gizmo_world_position", wp)
        except Exception:
            pass
        self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)
        self._transform_gizmo.renderer.AXIS_COLORS = {
            "X": tuple(getattr(self._renderer, "gimbal_x_color", (220, 60, 60)))[:3] + (255,),
            "Y": tuple(getattr(self._renderer, "gimbal_y_color", (60, 220, 80)))[:3] + (255,),
            "Z": tuple(getattr(self._renderer, "gimbal_z_color", (70, 135, 240)))[:3] + (255,),
        }
        self._transform_gizmo.renderer.HILITE = (
            tuple(getattr(self._renderer, "gimbal_active_color", (255, 235, 80)))[:3] + (255,)
        )
        try:
            return self._transform_gizmo.build_render_data(self.camera, self._renderer._proj, w, h)
        except Exception as exc:
            log.debug("Transform gizmo render data build failed: %s", exc)
            return None

    def _draw_transform_gizmo(self, draw, w: int, h: int) -> None:
        if not self._ensure_renderer_gimbal_state():
            return
        self._transform_gizmo.visible = True
        node = self._active_gizmo_node()
        if node is None:
            self._transform_gizmo.clear_selection()
            return
        if node is not None:
            try:
                wp = self._gizmo_world_position(node)
                setattr(node, "_gr_gizmo_world_position", wp)
            except Exception:
                pass
            self._sync_transform_reference_for_node(node)
        self._transform_gizmo.set_selected_object(node)
        self._transform_gizmo.renderer.AXIS_COLORS = {
            "X": tuple(getattr(self._renderer, "gimbal_x_color", (220, 60, 60)))[:3] + (255,),
            "Y": tuple(getattr(self._renderer, "gimbal_y_color", (60, 220, 80)))[:3] + (255,),
            "Z": tuple(getattr(self._renderer, "gimbal_z_color", (70, 135, 240)))[:3] + (255,),
        }
        self._transform_gizmo.renderer.HILITE = (
            tuple(getattr(self._renderer, "gimbal_active_color", (255, 235, 80)))[:3] + (255,)
        )
        self._transform_gizmo.draw(draw, self.camera, self._renderer._proj, w, h)

    def _viewport_picking_diagnostics(self) -> dict[str, object]:
        selected = [node for node in getattr(self, "_selected_meshes", []) or [] if node is not None]
        active = getattr(self._renderer, "selected_node", None)
        last_pick = dict(getattr(self, "_last_pick_diagnostics", {}) or {})
        picking_method = str(
            last_pick.get("method")
            or ("GPU ID" if self._gpu_renderer_supports_gpu_picking() else getattr(self._picking_provider, "method", "CPU raycast"))
        )
        active_kind = self._selection_kind_for_node(active)
        selected_ids = {
            "object_id": getattr(active, "_gr_scene_object_id", None) if active is not None else None,
            "node_id": getattr(active, "name", None) if active is not None else None,
            "mesh_id": getattr(active, "name", None) if active is not None and self._is_selectable_mesh_node(active) else None,
            "light_id": getattr(active, "_gr_light_id", None) if active is not None and bool(getattr(active, "is_light", False)) else None,
            "camera_id": getattr(active, "_gr_camera_id", None) if active is not None and bool(getattr(active, "is_camera", False)) else None,
            "helper_id": getattr(active, "name", None) if active is not None and active_kind == "helper" else None,
        }
        return {
            "picking_provider_active": self._picking_provider is not None,
            "picking_method": picking_method,
            "last_pick": last_pick,
            "active_selection_kind": active_kind,
            "selected_display_name": str(getattr(active, "_gr_scene_object_name", getattr(active, "name", "")) or ""),
            "selection_source": str(getattr(self, "_last_selection_source", "") or ""),
            "selected_ids": selected_ids,
            "selected_object_count": 1 if active is not None and not selected else len(selected),
            "selected_node_count": len(getattr(self, "_selected_joint_nodes", []) or []),
            "gizmo_hover_target": getattr(self._transform_gizmo, "hovered_handle", None),
            "active_gizmo_tool": getattr(getattr(self._transform_gizmo, "mode", None), "value", ""),
            "active_axis_mode": str(getattr(getattr(self, "transform_reference_controller", None), "axis_mode", "")),
            "device_pixel_ratio": float(self.canvas.devicePixelRatioF()),
            "surface_widget_class": type(self.canvas.current_surface()).__name__ if self.canvas.current_surface() is not None else "",
            "input_bridge_installed": self.canvas.input_bridge_installed(),
        }

    def _renderer_is_wgpu_like(self) -> bool:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return False
        try:
            backend_id = str(getattr(renderer, "backend_id", "") or "")
            if "wgpu" in backend_id or "direct3d" in backend_id:
                return True
            diagnostics = renderer.get_diagnostics() if hasattr(renderer, "get_diagnostics") else {}
            backend_id = str((diagnostics or {}).get("backend_id") or "")
            name = str((diagnostics or {}).get("name") or "")
            return "wgpu" in backend_id.lower() or "direct3d" in backend_id.lower() or "wgpu" in name.lower()
        except Exception:
            return False

    def _selection_kind_for_node(self, node) -> str:
        if node is None:
            return "none"
        if bool(getattr(node, "is_light", False)):
            return "light"
        if bool(getattr(node, "is_camera", False)):
            return "camera"
        if self._is_selectable_mesh_node(node):
            return "mesh"
        if self._is_general_helper_node(node):
            return "helper"
        if bool(getattr(node, "_gr_scene_object_root", False)):
            return "scene_node"
        return "scene_node"

    def _gpu_renderer_supports_gpu_picking(self) -> bool:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return False
        try:
            caps = renderer.get_capabilities() if hasattr(renderer, "get_capabilities") else None
            return bool(getattr(caps, "supports_gpu_id_picking", False))
        except Exception:
            return False

    def _gpu_renderer_supports_native_gizmo_drawing(self) -> bool:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return False
        backend_id = str(getattr(renderer, "backend_id", "") or "").lower()
        if not (backend_id.startswith("wgpu_") or backend_id == "pygfx_wgpu"):
            return False
        try:
            caps = renderer.get_capabilities() if hasattr(renderer, "get_capabilities") else None
            return bool(getattr(caps, "supports_gizmo_drawing", False))
        except Exception:
            return False

    def _gpu_renderer_supports_native_skeleton_overlay(self) -> bool:
        renderer = getattr(self, "_gpu_renderer", None)
        if renderer is None:
            return False
        backend_id = str(getattr(renderer, "backend_id", "") or "").lower()
        if not (backend_id.startswith("wgpu_") or backend_id == "pygfx_wgpu"):
            return False
        try:
            caps = renderer.get_capabilities() if hasattr(renderer, "get_capabilities") else None
            return bool(getattr(caps, "skeleton_overlay_supported", False))
        except Exception:
            return False

    def _draw_measurement_overlay(self, draw, w: int, h: int) -> None:
        try:
            self.measurement_controller.draw_overlay(draw, self._renderer._proj, w, h)
        except Exception as exc:
            log.debug("Measurement overlay draw failed: %s", exc)

    def _draw_camera_helpers(self, draw, w: int, h: int) -> None:
        try:
            active_id = self.camera_manager.active_camera_id
            hovered = self.camera_manager.find_by_original(getattr(self, "_hovered_camera_node", None))
            self._camera_helper_renderer.hovered_camera_id = getattr(hovered, "id", "") if hovered is not None else ""
            self._camera_helper_renderer.draw(
                draw,
                self.camera_manager.get_all_cameras(),
                active_id,
                self._renderer._proj,
                w,
                h,
            )
        except Exception as exc:
            log.debug("Camera helper draw failed: %s", exc)

__all__ = ("ViewportRenderingPipelineMixin",)
