"""ViewportDisplayControls methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportDisplayControlsMixin:
    def _set_display_options(self, options: ViewportDisplayOptions, *, announce: bool = True) -> None:
        self.display_options = options
        setattr(self._renderer, "display_options", options)
        self._renderer.show_grid = bool(options.show_grid)
        self._renderer.show_texture = bool(options.show_textures)
        self._renderer.show_lightmap_map = bool(options.show_lightmaps)
        if options.display_mode is ViewportDisplayMode.WIREFRAME:
            self._renderer.show_solid = False
            self._renderer.show_wireframe = True
        else:
            self._renderer.show_solid = True
            self._renderer.show_wireframe = bool(options.show_wire_overlay or options.show_edged_faces)
        self._xray_mode = bool(options.xray)
        if self._gpu_renderer is not None:
            setattr(self._gpu_renderer, "display_options", options)
            setattr(self._gpu_renderer, "show_grid", bool(options.show_grid))
        self._sync_display_buttons()
        self._refresh_display_button_availability()
        self._emit_render_state_changed()
        if announce:
            self.statusMessage.emit(f"Viewport display: {options.display_mode.value.replace('_', ' ').title()}")

    @staticmethod
    def _display_mode_label(options: ViewportDisplayOptions) -> str:
        mode = options.display_mode.value.replace("_", " ").title()
        extras: list[str] = []
        if options.show_edged_faces or options.show_wire_overlay:
            extras.append("Edges")
        if options.xray:
            extras.append("X-Ray")
        if options.show_lightmaps and options.display_mode not in {
            ViewportDisplayMode.TEXTURED_LIGHTMAPPED,
            ViewportDisplayMode.FULL_MATERIAL,
        }:
            extras.append("Lightmaps")
        return f"{mode} ({', '.join(extras)})" if extras else mode

    @staticmethod
    def _renderer_label_for_backend(backend: object) -> str:
        try:
            return renderer_backend_label(normalize_renderer_backend(getattr(backend, "value", backend)))
        except Exception:
            return str(backend or "Unknown Renderer").replace("_", " ").title()

    @staticmethod
    def _normalized_renderer_backend(backend: object):
        return normalize_renderer_backend(getattr(backend, "value", backend))

    def _active_renderer_backend(self):
        renderer = getattr(self, "_gpu_renderer", None)
        backend = None
        if renderer is not None:
            backend = getattr(renderer, "active_backend", None)
            if backend is None:
                diagnostics = {}
                get_diagnostics = getattr(renderer, "get_diagnostics", None)
                if callable(get_diagnostics):
                    try:
                        diagnostics = get_diagnostics() or {}
                    except Exception:
                        diagnostics = {}
                backend = diagnostics.get("backend_id") or getattr(renderer, "backend_id", None)
        if backend is None:
            backend = "modern_gl"
        return backend

    def _active_renderer_status_label(self) -> str:
        return self._renderer_label_for_backend(self._active_renderer_backend())

    def _configured_renderer_status_label(self) -> str:
        settings = getattr(self, "_renderer_settings", RendererSettings())
        return self._renderer_label_for_backend(getattr(settings, "backend", None))

    def render_state_status_text(self) -> str:
        configured_backend = getattr(getattr(self, "_renderer_settings", RendererSettings()), "backend", None)
        active_backend = self._active_renderer_backend()
        renderer_label = self._configured_renderer_status_label()
        if self._normalized_renderer_backend(active_backend) != self._normalized_renderer_backend(configured_backend):
            renderer_label = f"{renderer_label} (Active: {self._active_renderer_status_label()})"
        return f"Renderer: {renderer_label} | Display: {self._display_mode_label(self.display_options)}"

    def _emit_render_state_changed(self) -> None:
        text = self.render_state_status_text()
        if text == self._last_render_state_text:
            return
        self._last_render_state_text = text
        self.renderStateChanged.emit(text)

    def _display_mode_for_current_controls(self) -> ViewportDisplayMode:
        if not bool(getattr(self._renderer, "show_solid", True)) and bool(getattr(self._renderer, "show_wireframe", False)):
            return ViewportDisplayMode.WIREFRAME
        render_mode = str(getattr(self._renderer, "render_mode", "realistic") or "realistic").lower()
        if render_mode == "flat":
            return ViewportDisplayMode.SOLID
        if render_mode == "shaded":
            return ViewportDisplayMode.SHADED
        if bool(getattr(self._renderer, "show_texture", True)):
            return ViewportDisplayMode.FULL_MATERIAL if bool(getattr(self._renderer, "show_lightmap_map", False)) else ViewportDisplayMode.TEXTURED
        return ViewportDisplayMode.SOLID

    def _rebuild_display_options_from_renderer(self) -> ViewportDisplayOptions:
        return self.display_options.with_changes(
            display_mode=self._display_mode_for_current_controls(),
            show_grid=bool(getattr(self._renderer, "show_grid", True)),
            show_wire_overlay=bool(getattr(self._renderer, "show_solid", True) and getattr(self._renderer, "show_wireframe", False)),
            show_edged_faces=bool(getattr(self._renderer, "show_solid", True) and getattr(self._renderer, "show_wireframe", False)),
            show_textures=bool(getattr(self._renderer, "show_texture", True)),
            show_lightmaps=bool(getattr(self._renderer, "show_lightmap_map", False)),
            xray=bool(getattr(self, "_xray_mode", False)),
            force_flat_colour=str(getattr(self._renderer, "render_mode", "") or "").lower() == "flat",
        )

    def _sync_display_buttons(self) -> None:
        self._sync_shade_buttons()
        self._sync_render_mode_buttons()
        for name, value in (
            ("texture_button", self.display_options.show_textures),
            ("grid_button", self.display_options.show_grid),
            ("xray_button", self.display_options.xray),
        ):
            button = getattr(self, name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(bool(value))
            button.blockSignals(False)

    def _refresh_display_button_availability(self) -> None:
        caps = None
        renderer = self._gpu_renderer
        if renderer is not None and hasattr(renderer, "get_capabilities"):
            try:
                caps = renderer.get_capabilities()
            except Exception:
                caps = None
        if caps is None:
            return
        diagnostic_only = bool(getattr(caps, "diagnostic_only", False))
        for button_name in (
            "solid_button",
            "wire_button",
            "solid_wire_button",
            "texture_button",
            "render_realistic_button",
            "render_shaded_button",
            "render_flat_button",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setEnabled(not diagnostic_only)
        if diagnostic_only:
            self.statusMessage.emit("Null Diagnostic renderer does not draw scene display modes.")

    def toggle_wireframe(self, checked: Optional[bool] = None) -> None:
        if checked is False:
            self.set_shade_mode("solid")
        else:
            self.set_shade_mode("wire")

    def set_shade_mode(self, mode: str) -> None:
        mode_key = (mode or "solid").strip().lower()
        if mode_key in {"wireframe", "wire"}:
            self._renderer.show_solid = False
            self._renderer.show_wireframe = True
        elif mode_key in {"both", "solid+wire", "solid_wire"}:
            self._renderer.show_solid = True
            self._renderer.show_wireframe = True
        else:
            self._renderer.show_solid = True
            self._renderer.show_wireframe = False
        self._set_display_options(self._rebuild_display_options_from_renderer())
        self._request_render(fast=True, reason="shade mode changed", style=True, overlay=True, hud=True)

    def _sync_shade_buttons(self) -> None:
        state = {
            "solid_button": self._renderer.show_solid and not self._renderer.show_wireframe,
            "wire_button": self._renderer.show_wireframe and not self._renderer.show_solid,
            "solid_wire_button": self._renderer.show_solid and self._renderer.show_wireframe,
        }
        for name, checked in state.items():
            button = getattr(self, name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)

    def set_render_mode(self, mode: str) -> None:
        mode_key = (mode or "realistic").strip().lower()
        if mode_key not in {"realistic", "shaded", "flat"}:
            mode_key = "realistic"
        self._renderer.render_mode = mode_key
        self.toggle_gpu_renderer(True)
        self._set_display_options(self._rebuild_display_options_from_renderer())
        self._request_render(fast=True, reason="render mode changed", style=True, overlay=True, hud=True)

    def _sync_render_mode_buttons(self) -> None:
        active = getattr(self._renderer, "render_mode", "realistic") or "realistic"
        for mode, name in (
            ("realistic", "render_realistic_button"),
            ("shaded", "render_shaded_button"),
            ("flat", "render_flat_button"),
        ):
            button = getattr(self, name, None)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(active == mode)
            button.blockSignals(False)

    def toggle_bones(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_bones = bool(checked) if checked is not None else not self._renderer.show_bones
        self._request_render()

    def toggle_texture(self, checked: Optional[bool] = None) -> None:
        self._renderer.show_texture = bool(checked) if checked is not None else not self._renderer.show_texture
        self._set_display_options(self._rebuild_display_options_from_renderer())
        self._request_render(fast=True, reason="texture mode changed", style=True, overlay=True, hud=True)

    def toggle_grid(self, checked: Optional[bool] = None) -> None:
        enabled = bool(checked) if checked is not None else not bool(getattr(self._renderer, "show_grid", True))
        self._renderer.show_grid = enabled
        if self._gpu_renderer is not None:
            self._gpu_renderer.show_grid = enabled
        self._set_display_options(self.display_options.with_changes(show_grid=enabled))
        self._request_render(fast=True)

    def set_lighting_mode(self, mode: str) -> None:
        mode = str(mode or "scene").strip().lower()
        allowed = {
            "scene",
            "unlit",
            "studio",
            "fullbright",
            "lightmap_preview",
            "diffuse_only",
            "normal_only",
            "specular_only",
            "environment_only",
            "shader_complexity",
            "photoreal_preview",
        }
        if mode not in allowed:
            mode = "scene"
        setattr(self._renderer, "lighting_mode", mode)
        if self._gpu_renderer is not None:
            self._gpu_renderer.lighting_mode = mode
        self._request_render()

    def set_texture_map_enabled(self, map_name: str, enabled: bool) -> None:
        key = str(map_name or "").strip().lower()
        attr = {
            "diffuse": "show_diffuse_map",
            "lightmap": "show_lightmap_map",
            "environment": "show_environment_map",
            "env": "show_environment_map",
            "specular": "show_specular_map",
            "normal": "show_normal_map",
        }.get(key)
        if not attr:
            return
        setattr(self._renderer, attr, bool(enabled))
        if self._gpu_renderer is not None:
            setattr(self._gpu_renderer, attr, bool(enabled))
        if attr == "show_lightmap_map":
            self._set_display_options(self._rebuild_display_options_from_renderer())
        self._request_render()

    def set_lightmap_settings(self, intensity: float, mode: str) -> None:
        try:
            intensity_value = max(0.0, min(float(intensity), 4.0))
        except (TypeError, ValueError):
            intensity_value = 0.55
        mode_value = str(mode or "baked").strip().lower()
        if mode_value not in {"disabled", "baked", "dynamic_preview", "hybrid", "debug", "phong", "emissive"}:
            mode_value = "baked"
        setattr(self._renderer, "lightmap_intensity", intensity_value)
        setattr(self._renderer, "lightmap_mode", mode_value)
        if self._gpu_renderer is not None:
            self._gpu_renderer.lightmap_intensity = intensity_value
            self._gpu_renderer.lightmap_mode = mode_value
        self._request_render()

    def set_shader_complexity_mode(self, mode: str) -> None:
        value = str(mode or "off").strip().lower()
        if value not in {"off", "basic", "overdraw", "texture_cost", "lighting_cost", "full_complexity"}:
            value = "off"
        setattr(self._renderer, "shader_complexity_mode", value)
        if self._gpu_renderer is not None:
            setattr(self._gpu_renderer, "shader_complexity_mode", value)
        self._request_render()

    def set_light_helper_visibility(self, helpers: bool, volumes: bool) -> None:
        button = getattr(self, "light_helpers_button", None)
        if button is not None:
            with QtCore.QSignalBlocker(button):
                button.setChecked(bool(helpers) and bool(volumes))
        for target in (self._renderer, self._gpu_renderer):
            if target is None:
                continue
            setattr(target, "show_light_gizmos", bool(helpers))
            setattr(target, "show_light_radius_volumes", bool(volumes))
        self._request_render()

    def toggle_light_helpers(self, checked: bool = False) -> None:
        enabled = bool(checked)
        self.set_light_helper_visibility(enabled, enabled)

    def refresh_lighting(self) -> None:
        if self._gpu_renderer is not None:
            invalidate = getattr(self._gpu_renderer, "invalidate_lighting", None)
            if callable(invalidate):
                invalidate("lighting changed")
            else:
                self._gpu_renderer.clear_caches()
        self._request_render()

__all__ = ("ViewportDisplayControlsMixin",)
