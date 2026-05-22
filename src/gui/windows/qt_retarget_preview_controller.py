"""Qt controller for in-memory retarget preview playback."""

from __future__ import annotations

from dataclasses import dataclass
import time
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6 import QtCore

from src.core.animation.animation_engine import AnimationEngine
from src.core.retargeting.fbx_importer import import_ue_fbx_animation_clip
from src.core.retargeting.retarget_preview import (
    RetargetPreviewError,
    RetargetPreviewRequest,
    RetargetPreviewResult,
    apply_retarget_preview_to_viewport,
    build_retarget_preview,
)
from src.core.retargeting.retarget_preview_export import (
    RetargetPreviewExportRequest,
    RetargetPreviewExportResult,
    export_retarget_preview_override,
)
from src.core.retargeting.retarget_profile import RetargetProfile, load_retarget_profile
from src.core.retargeting.source_animation import SourceSkeletonClip


@dataclass
class RetargetPreviewUiState:
    """UI-owned retarget preview inputs and last successful preview."""

    source_clip: SourceSkeletonClip | None = None
    target_model: Any | None = None
    retarget_profile: RetargetProfile | None = None
    last_preview_result: RetargetPreviewResult | None = None
    last_preview_is_current: bool = False


class QtRetargetViewportAdapter:
    """Adapter that plays preview animations through the real Qt viewport."""

    def __init__(self, viewport: Any, *, parent: Optional[QtCore.QObject] = None) -> None:
        self.viewport = viewport
        self.model = None
        self.slot_name = ""
        self.engine: AnimationEngine | None = None
        self._last_tick: float | None = None
        self._timer = QtCore.QTimer(parent) if parent is not None else None
        if self._timer is not None:
            self._timer.setInterval(33)
            self._timer.timeout.connect(self._tick)

    def set_model(self, model) -> None:
        self.model = model
        self.engine = None
        self._last_tick = None
        if hasattr(self.viewport, "set_model"):
            self.viewport.set_model(model)
        elif hasattr(self.viewport, "load_model"):
            self.viewport.load_model(model)

    def set_active_animation(self, slot_name: str) -> None:
        self.slot_name = str(slot_name or "").strip()
        self.engine = None

    def set_time(self, time_seconds: float) -> None:
        engine = self._ensure_engine(play=False)
        if engine is None:
            return
        engine.seek(float(time_seconds))
        pose = engine.evaluate()
        self._apply_pose(pose)

    def play(self) -> None:
        engine = self._ensure_engine(play=True)
        if engine is None:
            return
        try:
            if hasattr(self.viewport, "set_anim_base_pose"):
                self.viewport.set_anim_base_pose(engine.evaluate(0.0))
        except Exception:
            pass
        self._last_tick = None
        if self._timer is not None:
            self._timer.start()
        else:
            self._apply_pose(engine.evaluate())

    def pause(self) -> None:
        if self._timer is not None:
            self._timer.stop()
        if self.engine is not None:
            self.engine.stop()

    def enable_node_overlay(self, enabled: bool) -> None:
        if hasattr(self.viewport, "toggle_bones"):
            self.viewport.toggle_bones(bool(enabled))
        if hasattr(self.viewport, "set_joint_dot_enabled"):
            self.viewport.set_joint_dot_enabled(bool(enabled))

    def _ensure_engine(self, *, play: bool) -> AnimationEngine | None:
        if self.model is None or not self.slot_name:
            return None
        if self.engine is None or getattr(self.engine, "model", None) is not self.model:
            self.engine = AnimationEngine(self.model)
        current = self.engine.current_animation
        if current is None or str(getattr(current, "name", "") or "").lower() != self.slot_name.lower():
            if not self.engine.play(self.slot_name, loop=True, blend=False):
                return None
            if not play:
                self.engine.stop()
        elif play and not self.engine.is_playing:
            self.engine.play(self.slot_name, loop=True, blend=False)
        return self.engine

    def _tick(self) -> None:
        engine = self.engine
        if engine is None or not engine.is_playing:
            if self._timer is not None:
                self._timer.stop()
            self._last_tick = None
            return
        now = time.perf_counter()
        dt = 1.0 / 30.0 if self._last_tick is None else max(1.0 / 60.0, min(now - self._last_tick, 0.25))
        self._last_tick = now
        still_playing = engine.advance(dt)
        self._apply_pose(engine.evaluate())
        if not still_playing and self._timer is not None:
            self._timer.stop()
            self._last_tick = None

    def _apply_pose(self, pose) -> None:
        if not hasattr(self.viewport, "set_animation_pose"):
            return
        anim = self.engine.current_animation if self.engine is not None else None
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim is not None else 0.0
        current_time = float(getattr(self.engine, "current_time", 0.0) or 0.0) if self.engine is not None else 0.0
        self.viewport.set_animation_pose(pose, name=self.slot_name, time=current_time, length=length)


class RetargetPreviewUiController:
    """Thin UI controller over the core retarget preview service."""

    def __init__(
        self,
        *,
        viewport: Any | None = None,
        preview_action: Any | None = None,
        export_action: Any | None = None,
        target_model_provider: Callable[[], Any | None] | None = None,
        log_callback: Callable[[str, str], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
        build_preview: Callable[[RetargetPreviewRequest], RetargetPreviewResult] = build_retarget_preview,
        apply_preview: Callable[..., None] = apply_retarget_preview_to_viewport,
        export_preview: Callable[..., RetargetPreviewExportResult] = export_retarget_preview_override,
    ) -> None:
        self.state = RetargetPreviewUiState()
        self.viewport = viewport
        self.preview_action = preview_action
        self.export_action = export_action
        self.target_model_provider = target_model_provider
        self.log_callback = log_callback
        self.status_callback = status_callback
        self._build_preview = build_preview
        self._apply_preview = apply_preview
        self._export_preview = export_preview
        self.last_error = ""
        self.update_enabled()

    def set_source_clip(self, clip: SourceSkeletonClip | None) -> None:
        self.state.source_clip = clip
        self._mark_preview_stale()
        self.update_enabled()

    def set_target_model(self, model: Any | None) -> None:
        self.state.target_model = model
        self._mark_preview_stale()
        self.update_enabled()

    def set_retarget_profile(self, profile: RetargetProfile | None) -> None:
        self.state.retarget_profile = profile
        self._mark_preview_stale()
        self.update_enabled()

    def invalidate_preview(self) -> None:
        """Mark the stored preview stale after external target/session changes."""

        self._mark_preview_stale()
        self.update_enabled()

    def load_source_clip(self, path: str | Path, *, clip_name: str | None = None, sample_rate: float = 30.0) -> SourceSkeletonClip:
        clip = import_ue_fbx_animation_clip(str(path), clip_name=clip_name, sample_rate=sample_rate)
        self.set_source_clip(clip)
        self._log(f"Loaded UE/FBX source animation: {Path(path).name}", "success")
        return clip

    def load_retarget_profile(self, path: str | Path) -> RetargetProfile:
        profile = load_retarget_profile(path)
        self.set_retarget_profile(profile)
        self._log(f"Loaded retarget profile: {Path(path).name}", "success")
        return profile

    def current_target_model(self):
        if self.target_model_provider is not None:
            provided = self.target_model_provider()
            if provided is not None:
                return provided
        return self.state.target_model

    def can_preview(self) -> bool:
        profile = self.state.retarget_profile
        return (
            self.state.source_clip is not None
            and self.current_target_model() is not None
            and profile is not None
            and bool(str(getattr(profile, "animation_slot", "") or "").strip())
        )

    def update_enabled(self) -> None:
        if self.preview_action is not None and hasattr(self.preview_action, "setEnabled"):
            self.preview_action.setEnabled(self.can_preview())
        if self.export_action is not None and hasattr(self.export_action, "setEnabled"):
            self.export_action.setEnabled(self.can_export())

    def can_export(self) -> bool:
        preview = self.state.last_preview_result
        audit = getattr(preview, "preview_audit", None)
        return (
            preview is not None
            and self.state.last_preview_is_current
            and audit is not None
            and bool(getattr(audit, "passed", False))
            and self.current_target_model() is not None
        )

    def preview_retarget(self, *, auto_play: bool = True, show_node_overlay: bool = True) -> RetargetPreviewResult | None:
        self.update_enabled()
        if not self.can_preview():
            message = (
                "Retarget preview requires a loaded target model, a UE/FBX source clip, "
                "and a retarget profile with a valid KOTOR animation slot. "
                "UE clip names are not KOTOR animation slots."
            )
            self.last_error = message
            self._log(message, "warning")
            self._status("Retarget preview inputs are incomplete")
            return None

        if self.preview_action is not None and hasattr(self.preview_action, "setEnabled"):
            self.preview_action.setEnabled(False)
        try:
            request = RetargetPreviewRequest(
                source_clip=self.state.source_clip,
                target_model=self.current_target_model(),
                profile=self.state.retarget_profile,
                auto_play=auto_play,
            )
            preview = self._build_preview(request)
            if self.viewport is not None:
                self._apply_preview(
                    preview,
                    self.viewport,
                    auto_play=auto_play,
                    show_node_overlay=show_node_overlay,
                )
            self.state.last_preview_result = preview
            self.state.last_preview_is_current = True
            self.last_error = ""
            self._report_success(preview)
            return preview
        except Exception as exc:
            self.state.last_preview_result = None
            self.state.last_preview_is_current = False
            self.last_error = str(exc)
            self._log(f"Retarget preview failed: {exc}", "error")
            self._status("Retarget preview failed")
            return None
        finally:
            self.update_enabled()

    def export_retarget_preview(
        self,
        output_mdl_path: str | Path,
        *,
        overwrite: bool = False,
        write_manifest: bool = True,
    ) -> RetargetPreviewExportResult | None:
        """Export the currently approved preview without rebuilding it."""

        self.update_enabled()
        if self.state.last_preview_result is None:
            message = (
                "No successful retarget preview is available to export. "
                "Preview the animation in GhostRigger before exporting MDL/MDX."
            )
            self.last_error = message
            self._log(message, "warning")
            self._status("No retarget preview to export")
            return None
        if not self.state.last_preview_is_current:
            message = (
                "The retarget preview is stale because the source clip, target model, "
                "or retarget profile changed. Run Preview Retarget again before exporting."
            )
            self.last_error = message
            self._log(message, "warning")
            self._status("Retarget preview is stale")
            return None
        if not self.can_export():
            message = (
                "Retarget preview cannot be exported because its audit did not pass. "
                "Run Preview Retarget again before exporting MDL/MDX."
            )
            self.last_error = message
            self._log(message, "error")
            self._status("Retarget preview export blocked")
            return None

        mdl_path = Path(output_mdl_path)
        if self.export_action is not None and hasattr(self.export_action, "setEnabled"):
            self.export_action.setEnabled(False)
        try:
            result = self._export_preview(
                RetargetPreviewExportRequest(
                    preview_result=self.state.last_preview_result,
                    original_target_model=self.current_target_model(),
                    output_mdl_path=mdl_path,
                    output_mdx_path=mdl_path.with_suffix(".mdx"),
                    overwrite=overwrite,
                    verify_roundtrip=True,
                    write_manifest=write_manifest,
                )
            )
            self.last_error = ""
            self._report_export_success(result)
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self._log(f"Retarget preview export failed: {exc}", "error")
            self._status("Retarget preview export failed")
            return None
        finally:
            self.update_enabled()

    def _report_success(self, preview: RetargetPreviewResult) -> None:
        report = getattr(preview, "solver_report", None)
        audit = getattr(preview, "preview_audit", None)
        duration = float(
            getattr(getattr(preview, "animation_block", None), "length", None)
            or getattr(report, "duration_seconds", 0.0)
            or 0.0
        )
        message = (
            "Retarget preview built successfully.\n"
            f"Slot: {preview.slot_name}\n"
            f"Duration: {duration:.3f}s\n"
            f"Mapped nodes: {int(getattr(report, 'mapped_node_count', 0) or 0)}\n"
            f"Orientation tracks: {int(getattr(report, 'generated_orientation_track_count', 0) or 0)}\n"
            f"Root drift: {float(getattr(audit, 'root_drift_distance', 0.0) or 0.0):.6g}"
        )
        self._log(message, "success")
        for warning in getattr(preview, "warnings", []) or []:
            self._log(str(warning), "warning")
        self._status(f"Retarget preview ready: {preview.slot_name}")

    def _report_export_success(self, result: RetargetPreviewExportResult) -> None:
        verified = "passed" if result.verified_roundtrip else "not requested"
        message = (
            "Retarget preview exported successfully.\n"
            f"Slot: {result.slot_name}\n"
            f"MDL: {result.mdl_path}\n"
            f"MDX: {result.mdx_path}\n"
            f"MDL readback verification: {verified}\n"
            "Ready for Override/Patch Manager testing."
        )
        self._log(message, "success")
        for warning in result.warnings:
            self._log(str(warning), "warning")
        self._status(f"Retarget preview exported: {result.slot_name}")

    def _mark_preview_stale(self) -> None:
        self.state.last_preview_is_current = False

    def _log(self, message: str, level: str = "info") -> None:
        if self.log_callback is not None:
            self.log_callback(message, level)

    def _status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)
