"""Sequence image-sequence rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.camera.camera_render_settings import RenderSettings
from src.core.camera.render_output import RenderOutput

from .sequence_evaluator import SequenceEvaluator
from .sequence_model import GhostRiggerLevelSequence


@dataclass
class SequenceRenderSettings:
    output_directory: str = "exports/sequences"
    output_format: str = "PNG"
    resolution_width: int = 1920
    resolution_height: int = 1080
    start_frame: int = 0
    end_frame: int = 240
    frame_step: int = 1
    use_camera_cut_track: bool = True
    include_letterbox: bool = True
    include_safe_frame: bool = False
    include_helpers: bool = False
    include_grid: bool = False
    render_mode: str = "Cinematic Preview"
    overwrite_existing: bool = False

    @classmethod
    def for_sequence(cls, sequence: GhostRiggerLevelSequence) -> "SequenceRenderSettings":
        return cls(start_frame=sequence.playback_start_frame, end_frame=sequence.playback_end_frame)


class SequenceRenderer:
    def __init__(self, viewport, evaluator: SequenceEvaluator | None = None) -> None:
        self.viewport = viewport
        self.evaluator = evaluator or SequenceEvaluator(viewport)
        self.output = RenderOutput()

    def render(
        self,
        sequence: GhostRiggerLevelSequence,
        settings: SequenceRenderSettings | None = None,
        *,
        progress: Callable[[int, int, str], bool] | None = None,
    ) -> list[str]:
        if self.viewport is None:
            raise RuntimeError("No viewport available for sequence render.")
        settings = settings or SequenceRenderSettings.for_sequence(sequence)
        if settings.end_frame < settings.start_frame:
            raise ValueError("Invalid frame range.")
        frame_step = max(1, int(settings.frame_step))
        frames = list(range(int(settings.start_frame), int(settings.end_frame) + 1, frame_step))
        output_dir = Path(settings.output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        render_settings = RenderSettings(
            output_format=settings.output_format,
            output_directory=str(output_dir),
            filename_prefix=RenderOutput().sanitize_filename(sequence.name),
            resolution_width=int(settings.resolution_width),
            resolution_height=int(settings.resolution_height),
            resolution_source="custom",
            render_mode=settings.render_mode,
            include_letterbox=bool(settings.include_letterbox),
            include_safe_frame=bool(settings.include_safe_frame),
            include_helpers=bool(settings.include_helpers),
            include_grid=bool(settings.include_grid),
            overwrite_existing=bool(settings.overwrite_existing),
        )
        frame_renderer = getattr(self.viewport, "_camera_frame_renderer", None)
        if frame_renderer is None:
            from src.adapters.qt_viewport.frame_renderer import create_viewport_frame_renderer

            frame_renderer = create_viewport_frame_renderer(self.viewport)
        written: list[str] = []
        self.evaluator.capture_original_state(sequence)
        try:
            total = len(frames)
            for index, frame in enumerate(frames, start=1):
                self.evaluator.evaluate(sequence, frame, scrubbing=False)
                active_binding = self.evaluator.active_camera_binding(sequence, frame) if settings.use_camera_cut_track else None
                camera = self.evaluator.resolver.camera_for_binding(active_binding) if active_binding is not None else None
                image = frame_renderer.render_current_frame(render_settings, camera)
                if image is None:
                    raise RuntimeError(f"Cannot render frame {frame}.")
                ext = "jpg" if render_settings.output_format.upper() in {"JPG", "JPEG"} else render_settings.output_format.lower()
                path = output_dir / f"{RenderOutput().sanitize_filename(sequence.name)}_{int(frame):06d}.{ext}"
                if path.exists() and not settings.overwrite_existing:
                    raise FileExistsError(f"Output exists: {path}")
                self.output.save_frame(image, path, render_settings.output_format)
                written.append(str(path))
                if progress is not None and progress(index, total, str(path)) is False:
                    break
        finally:
            self.evaluator.restore_original_state(sequence)
        return written
