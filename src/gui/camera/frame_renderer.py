"""Lightweight still-frame renderer using the active Qt viewport pipeline."""

from __future__ import annotations

from pathlib import Path

from .camera_overlays import CameraOverlays
from .camera_render_settings import RenderSettings
from .render_manifest import RenderManifestEntry, append_render_manifest
from .render_output import RenderOutput


class FrameRenderer:
    def __init__(self, viewport=None, output: RenderOutput | None = None) -> None:
        self.viewport = viewport
        self.output = output or RenderOutput()
        self.last_output_path: str = ""
        self.last_warning: str = ""

    def render_current_frame(self, settings: RenderSettings | None = None, camera=None) -> object | None:
        if self.viewport is None:
            raise RuntimeError("No viewport/render context available.")
        settings = settings or RenderSettings()
        settings.validate()
        width, height = self._resolution(settings, camera)
        self.last_warning = ""
        if camera is None:
            self.last_warning = "No active camera; rendering from viewport instead."
        render_frame = getattr(self.viewport, "_render_frame", None)
        if not callable(render_frame):
            raise RuntimeError("No viewport/render context available.")
        old_helpers = self._snapshot_helpers()
        try:
            if not settings.include_helpers:
                self._set_helpers(False)
            if not settings.include_grid:
                setattr(self.viewport._renderer, "show_grid", False)
                gpu = getattr(self.viewport, "_gpu_renderer", None)
                if gpu is not None:
                    setattr(gpu, "show_grid", False)
            setattr(self.viewport, "_render_suppress_camera_overlays", True)
            image = render_frame(width, height)
            if image is None:
                raise RuntimeError("Viewport render returned no image.")
            if image.mode != "RGBA":
                image = image.convert("RGBA")
            if camera is not None and (settings.include_letterbox or settings.include_safe_frame or settings.include_camera_guides):
                from PIL import ImageDraw

                overlays = CameraOverlays()
                draw = ImageDraw.Draw(image, "RGBA")
                if settings.include_letterbox and settings.burn_letterbox_into_render:
                    overlays.draw_letterbox(
                        draw,
                        overlays.active_frame_rect(camera, width, height),
                        width,
                        height,
                        opaque=True,
                    )
                if settings.include_safe_frame:
                    overlays.draw_safe_frame(draw, overlays.active_frame_rect(camera, width, height))
                if settings.include_camera_guides:
                    overlays.draw_guides(draw, overlays.active_frame_rect(camera, width, height))
            return image
        finally:
            self._restore_helpers(old_helpers)

    def render_to_file(self, settings: RenderSettings | None = None, camera=None, *, module_name: str = "scene") -> str:
        settings = settings or RenderSettings()
        image = self.render_current_frame(settings, camera)
        if image is None:
            raise RuntimeError("No image was rendered.")
        camera_name = getattr(camera, "name", "Viewport") if camera is not None else "Viewport"
        path = self.output.build_output_path(camera_name, settings, module_name=module_name)
        self.output.save_frame(image, path, settings.output_format, settings.jpg_quality)
        self.last_output_path = path
        append_render_manifest(
            settings.output_directory,
            RenderManifestEntry(
                path=path,
                camera_id=str(getattr(camera, "id", "")),
                camera_name=str(camera_name),
                width=image.width,
                height=image.height,
                render_mode=settings.render_mode,
                settings=settings.to_dict(),
            ),
        )
        return path

    def _resolution(self, settings: RenderSettings, camera) -> tuple[int, int]:
        source = str(settings.resolution_source or "camera").lower()
        if source == "viewport" and self.viewport is not None:
            canvas = getattr(self.viewport, "canvas", None)
            return (max(1, int(canvas.width() if canvas is not None else settings.resolution_width)), max(1, int(canvas.height() if canvas is not None else settings.resolution_height)))
        if source == "camera" and camera is not None:
            return (max(1, int(camera.resolution_width)), max(1, int(camera.resolution_height)))
        return (settings.resolution_width, settings.resolution_height)

    def _snapshot_helpers(self) -> dict:
        viewport = self.viewport
        if viewport is None:
            return {}
        renderer = getattr(viewport, "_renderer", None)
        gpu = getattr(viewport, "_gpu_renderer", None)
        return {
            "show_gimbal": getattr(renderer, "show_gimbal", None),
            "show_grid": getattr(renderer, "show_grid", None),
            "show_light_gizmos": getattr(renderer, "show_light_gizmos", None),
            "gpu_show_grid": getattr(gpu, "show_grid", None) if gpu is not None else None,
            "gpu_show_light_gizmos": getattr(gpu, "show_light_gizmos", None) if gpu is not None else None,
            "show_camera_helpers": getattr(getattr(viewport, "_camera_helper_renderer", None), "show_camera_helpers", None),
            "render_suppress_camera_overlays": getattr(viewport, "_render_suppress_camera_overlays", False),
        }

    def _set_helpers(self, enabled: bool) -> None:
        renderer = getattr(self.viewport, "_renderer", None)
        gpu = getattr(self.viewport, "_gpu_renderer", None)
        if renderer is not None:
            setattr(renderer, "show_gimbal", bool(enabled))
            setattr(renderer, "show_light_gizmos", bool(enabled))
        if gpu is not None:
            setattr(gpu, "show_light_gizmos", bool(enabled))
        camera_helpers = getattr(self.viewport, "_camera_helper_renderer", None)
        if camera_helpers is not None:
            setattr(camera_helpers, "show_camera_helpers", bool(enabled))

    def _restore_helpers(self, state: dict) -> None:
        renderer = getattr(self.viewport, "_renderer", None)
        gpu = getattr(self.viewport, "_gpu_renderer", None)
        if renderer is not None:
            for key in ("show_gimbal", "show_grid", "show_light_gizmos"):
                if state.get(key) is not None:
                    setattr(renderer, key, state[key])
        if gpu is not None:
            if state.get("gpu_show_grid") is not None:
                setattr(gpu, "show_grid", state["gpu_show_grid"])
            if state.get("gpu_show_light_gizmos") is not None:
                setattr(gpu, "show_light_gizmos", state["gpu_show_light_gizmos"])
        camera_helpers = getattr(self.viewport, "_camera_helper_renderer", None)
        if camera_helpers is not None and state.get("show_camera_helpers") is not None:
            setattr(camera_helpers, "show_camera_helpers", state["show_camera_helpers"])
        if "render_suppress_camera_overlays" in state:
            setattr(self.viewport, "_render_suppress_camera_overlays", state["render_suppress_camera_overlays"])
