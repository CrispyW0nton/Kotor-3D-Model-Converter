"""Qt controller shell for the tri-mode Retarget Workbench."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from src.core.game.kotor_loader import get_valid_animation_slots
from src.core.retargeting.kotor_to_kotor_preview import (
    KotorToKotorPreviewRequest,
    KotorToKotorPreviewResult,
    build_kotor_to_kotor_retarget_preview,
)
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
    coerce_kotor_output_name_mode,
)
from src.core.retargeting.retarget_preview import apply_retarget_preview_to_viewport
from src.core.retargeting.retarget_preview_export import (
    RetargetPreviewExportRequest,
    export_retarget_preview_override,
)
from src.core.retargeting.retarget_modes import (
    RetargetMode,
    RetargetModeSpec,
    coerce_retarget_mode,
    get_retarget_mode_spec,
    list_retarget_mode_specs,
)


class RetargetWorkbenchError(RuntimeError):
    """Raised when the current Retarget Workbench mode cannot perform an action."""


@dataclass
class RetargetWorkbenchState:
    """UI-owned state shared by all retarget directions."""

    mode: RetargetMode = RetargetMode.UNREAL_TO_KOTOR

    # Current implemented Unreal -> KOTOR state.
    source_clip: Any | None = None
    target_model: Any | None = None
    retarget_profile: Any | None = None

    # Future KOTOR source modes.
    source_kotor_model: Any | None = None
    source_kotor_animation_slot: str | None = None

    # Future Unreal target mode.
    target_unreal_skeleton: Any | None = None
    target_unreal_profile: Any | None = None

    output_naming: RetargetOutputNaming | None = None

    last_kotor_to_kotor_preview_result: Any | None = None
    last_kotor_source_sample_result: Any | None = None
    last_preview_result: Any | None = None
    last_export_result: Any | None = None
    dirty_revision: int = 0


class RetargetWorkbenchController:
    """Mode-aware shell that delegates implemented UE-to-KOTOR work to the existing controller."""

    def __init__(
        self,
        *,
        ue_to_kotor_controller: Any | None = None,
        viewport: Any | None = None,
        preview_action: Any | None = None,
        export_action: Any | None = None,
        log_callback: Callable[[str, str], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
        build_kotor_to_kotor_preview: Callable[[KotorToKotorPreviewRequest], KotorToKotorPreviewResult] = build_kotor_to_kotor_retarget_preview,
        apply_preview: Callable[..., None] = apply_retarget_preview_to_viewport,
        export_preview: Callable[..., Any] = export_retarget_preview_override,
    ) -> None:
        self.state = RetargetWorkbenchState()
        self.ue_to_kotor_controller = ue_to_kotor_controller
        self.viewport = viewport
        self.preview_action = preview_action
        self.export_action = export_action
        self.log_callback = log_callback
        self.status_callback = status_callback
        self._build_kotor_to_kotor_preview = build_kotor_to_kotor_preview
        self._apply_preview = apply_preview
        self._export_preview = export_preview
        self.last_error = ""
        self.update_enabled()

    def current_mode_spec(self) -> RetargetModeSpec:
        return get_retarget_mode_spec(self.state.mode)

    def set_mode(self, mode: RetargetMode | str) -> None:
        next_mode = coerce_retarget_mode(mode)
        if next_mode == self.state.mode:
            self.update_enabled()
            return
        self.state.mode = next_mode
        spec = self.current_mode_spec()
        self.invalidate_preview(f"mode changed to {spec.label}")
        self._log(
            f"Retarget mode changed to {spec.label}.\nExisting preview/export state was invalidated.",
            "info",
        )
        self._status(self.mode_status_text())
        self.update_enabled()

    def set_source_clip(self, clip: Any | None) -> None:
        self.state.source_clip = clip
        if self.ue_to_kotor_controller is not None and hasattr(self.ue_to_kotor_controller, "set_source_clip"):
            self.ue_to_kotor_controller.set_source_clip(clip)
        self.invalidate_preview("source clip changed")
        self.update_enabled()

    def set_target_model(self, model: Any | None) -> None:
        self.state.target_model = model
        if self.ue_to_kotor_controller is not None and hasattr(self.ue_to_kotor_controller, "set_target_model"):
            self.ue_to_kotor_controller.set_target_model(model)
        self.invalidate_preview("target model changed")
        self.update_enabled()

    def set_retarget_profile(self, profile: Any | None) -> None:
        self.state.retarget_profile = profile
        if self.ue_to_kotor_controller is not None and hasattr(self.ue_to_kotor_controller, "set_retarget_profile"):
            self.ue_to_kotor_controller.set_retarget_profile(profile)
        self.invalidate_preview("retarget profile changed")
        self.update_enabled()

    def set_kotor_output_name_mode(self, mode: KotorOutputAnimationNameMode | str) -> None:
        naming = self.state.output_naming or RetargetOutputNaming()
        self.state.output_naming = replace(
            naming,
            kotor_name_mode=coerce_kotor_output_name_mode(mode),
        )
        self._push_output_naming()
        self.invalidate_preview("KOTOR output animation name mode changed")
        self.update_enabled()

    def set_target_kotor_animation_slot(self, slot_name: str | None) -> None:
        naming = self.state.output_naming or RetargetOutputNaming()
        self.state.output_naming = replace(
            naming,
            kotor_name_mode=KotorOutputAnimationNameMode.VANILLA_SLOT,
            requested_kotor_animation_name=str(slot_name or "").strip() or None,
            canonical_kotor_animation_name=None,
        )
        self._push_output_naming()
        self.invalidate_preview("target KOTOR animation slot changed")
        self.update_enabled()

    def set_custom_kotor_animation_name(self, name: str | None) -> None:
        naming = self.state.output_naming or RetargetOutputNaming(
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH
        )
        self.state.output_naming = replace(
            naming,
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_kotor_animation_name=str(name or "").strip() or None,
            canonical_kotor_animation_name=None,
        )
        self._push_output_naming()
        self.invalidate_preview("custom KOTOR animation name changed")
        self.update_enabled()

    def set_output_display_label(self, label: str | None) -> None:
        naming = self.state.output_naming or RetargetOutputNaming()
        self.state.output_naming = replace(
            naming,
            display_label=str(label or "").strip() or None,
        )
        self._push_output_naming()
        self.invalidate_preview("retarget output display label changed")
        self.update_enabled()

    def available_target_kotor_slots(self) -> list[str]:
        try:
            return list(get_valid_animation_slots(self.current_target_model()))
        except Exception:
            return []

    def set_source_kotor_model(self, model: Any | None) -> None:
        self.state.source_kotor_model = model
        self.invalidate_preview("source KOTOR model changed")
        self.update_enabled()

    def set_source_kotor_animation_slot(self, slot_name: str | None) -> None:
        self.state.source_kotor_animation_slot = str(slot_name or "").strip() or None
        self.invalidate_preview("source KOTOR animation slot changed")
        self.update_enabled()

    def set_target_unreal_skeleton(self, skeleton: Any | None) -> None:
        self.state.target_unreal_skeleton = skeleton
        self.invalidate_preview("target Unreal skeleton changed")
        self.update_enabled()

    def set_target_unreal_profile(self, profile: Any | None) -> None:
        self.state.target_unreal_profile = profile
        self.invalidate_preview("target Unreal profile changed")
        self.update_enabled()

    def load_source_clip(self, path: str | Path, *, clip_name: str | None = None, sample_rate: float = 30.0) -> Any:
        self._require_mode(RetargetMode.UNREAL_TO_KOTOR, "Load UE/FBX Source Animation")
        controller = self._require_ue_to_kotor_controller()
        clip = controller.load_source_clip(path, clip_name=clip_name, sample_rate=sample_rate)
        self.state.source_clip = clip
        self.invalidate_preview("source clip changed")
        self.update_enabled()
        return clip

    def load_retarget_profile(self, path: str | Path) -> Any:
        controller = self._require_ue_to_kotor_controller()
        profile = controller.load_retarget_profile(path)
        self.state.retarget_profile = profile
        self.invalidate_preview("retarget profile changed")
        self.update_enabled()
        return profile

    def current_target_model(self) -> Any | None:
        if self.state.mode == RetargetMode.UNREAL_TO_KOTOR and self.ue_to_kotor_controller is not None:
            if hasattr(self.ue_to_kotor_controller, "current_target_model"):
                return self.ue_to_kotor_controller.current_target_model()
        return self.state.target_model

    def can_preview(self) -> bool:
        spec = self.current_mode_spec()
        if not spec.implemented or not spec.supports_preview:
            return False
        if self.state.mode == RetargetMode.KOTOR_TO_KOTOR:
            return self._can_preview_kotor_to_kotor()
        controller = self._optional_ue_to_kotor_controller()
        return bool(controller is not None and controller.can_preview())

    def can_export(self) -> bool:
        spec = self.current_mode_spec()
        if not spec.implemented or not spec.supports_export:
            return False
        if self.state.mode == RetargetMode.KOTOR_TO_KOTOR:
            preview = self.state.last_preview_result
            audit = getattr(preview, "preview_audit", None)
            return bool(preview is not None and audit is not None and getattr(audit, "passed", False))
        controller = self._optional_ue_to_kotor_controller()
        return bool(controller is not None and controller.can_export())

    def update_enabled(self) -> None:
        if self.ue_to_kotor_controller is not None and hasattr(self.ue_to_kotor_controller, "update_enabled"):
            self.ue_to_kotor_controller.update_enabled()
        if self.preview_action is not None and hasattr(self.preview_action, "setEnabled"):
            self.preview_action.setEnabled(self.can_preview())
        if self.export_action is not None and hasattr(self.export_action, "setEnabled"):
            self.export_action.setEnabled(self.can_export())

    def preview(self, *, auto_play: bool = True, show_node_overlay: bool = True) -> Any | None:
        if self.state.mode == RetargetMode.KOTOR_TO_KOTOR:
            return self._preview_kotor_to_kotor(auto_play=auto_play, show_node_overlay=show_node_overlay)
        if self.state.mode != RetargetMode.UNREAL_TO_KOTOR:
            raise RetargetWorkbenchError(self.not_implemented_message("preview"))
        controller = self._require_ue_to_kotor_controller()
        self._push_output_naming()
        result = controller.preview_retarget(auto_play=auto_play, show_node_overlay=show_node_overlay)
        self._sync_from_ue_controller()
        self.last_error = str(getattr(controller, "last_error", "") or "")
        self.state.last_export_result = None
        self.update_enabled()
        return result

    def export_preview(self, output_mdl_path: str | Path, *, overwrite: bool = False, write_manifest: bool = True) -> Any | None:
        if self.state.mode == RetargetMode.KOTOR_TO_KOTOR:
            return self._export_kotor_to_kotor_preview(
                output_mdl_path,
                overwrite=overwrite,
                write_manifest=write_manifest,
            )
        if self.state.mode != RetargetMode.UNREAL_TO_KOTOR:
            raise RetargetWorkbenchError(self.not_implemented_message("export"))
        controller = self._require_ue_to_kotor_controller()
        result = controller.export_retarget_preview(
            output_mdl_path,
            overwrite=overwrite,
            write_manifest=write_manifest,
        )
        self._sync_from_ue_controller()
        self.last_error = str(getattr(controller, "last_error", "") or "")
        self.state.last_export_result = result
        self.update_enabled()
        return result

    def invalidate_preview(self, reason: str) -> None:
        self.state.last_preview_result = None
        self.state.last_export_result = None
        self.state.last_kotor_to_kotor_preview_result = None
        self.state.last_kotor_source_sample_result = None
        self.state.dirty_revision += 1
        if self.ue_to_kotor_controller is not None:
            ue_state = getattr(self.ue_to_kotor_controller, "state", None)
            if ue_state is not None:
                if hasattr(ue_state, "last_preview_result"):
                    ue_state.last_preview_result = None
                if hasattr(ue_state, "last_preview_is_current"):
                    ue_state.last_preview_is_current = False
            elif hasattr(self.ue_to_kotor_controller, "invalidate_preview"):
                self.ue_to_kotor_controller.invalidate_preview()
        self.last_error = reason

    def mode_status_text(self) -> str:
        spec = self.current_mode_spec()
        status = "implemented" if spec.implemented else _pending_status_for_mode(spec.mode)
        return (
            f"Mode: {spec.label}\n"
            f"Source: {_human_kind(spec.source_kind)}\n"
            f"Target: {_human_kind(spec.target_kind)}\n"
            f"Output: {_human_kind(spec.output_kind)}\n"
            f"Status: {status}"
        )

    def not_implemented_message(self, action: str) -> str:
        spec = self.current_mode_spec()
        if spec.mode == RetargetMode.KOTOR_TO_KOTOR:
            return "KOTOR → KOTOR is available when source/target inputs and output naming are complete."
        if spec.mode == RetargetMode.KOTOR_TO_UNREAL:
            return (
                "KOTOR → Unreal export is not implemented yet.\n"
                "Next step: add a UE-compatible FBX animation export adapter using sampled "
                "Aurora source poses."
            )
        return f"{spec.label} {action} is not available."

    def _sync_from_ue_controller(self) -> None:
        controller = self._optional_ue_to_kotor_controller()
        if controller is None:
            return
        ue_state = getattr(controller, "state", None)
        if ue_state is None:
            return
        self.state.source_clip = getattr(ue_state, "source_clip", self.state.source_clip)
        self.state.target_model = getattr(ue_state, "target_model", self.state.target_model)
        self.state.retarget_profile = getattr(ue_state, "retarget_profile", self.state.retarget_profile)
        self.state.last_preview_result = getattr(ue_state, "last_preview_result", None)

    def _push_output_naming(self) -> None:
        if self.ue_to_kotor_controller is not None and hasattr(self.ue_to_kotor_controller, "set_output_naming"):
            self.ue_to_kotor_controller.set_output_naming(self.state.output_naming)

    def _can_preview_kotor_to_kotor(self) -> bool:
        return bool(
            self.state.source_kotor_model is not None
            and str(self.state.source_kotor_animation_slot or "").strip()
            and self.current_target_model() is not None
            and self.state.retarget_profile is not None
            and self._has_target_output_animation_name()
        )

    def _has_target_output_animation_name(self) -> bool:
        naming = self.state.output_naming
        if naming is not None:
            raw = (
                naming.requested_kotor_animation_name
                or naming.canonical_kotor_animation_name
                or naming.unreal_clip_name
                or ""
            )
            if str(raw).strip():
                return True
        return bool(str(getattr(self.state.retarget_profile, "animation_slot", "") or "").strip())

    def _preview_kotor_to_kotor(self, *, auto_play: bool, show_node_overlay: bool) -> Any | None:
        if not self._can_preview_kotor_to_kotor():
            message = (
                "KOTOR → KOTOR preview requires a source KOTOR model, source animation name, "
                "target KOTOR model, retarget profile, and target output animation name."
            )
            self.last_error = message
            self._log(message, "warning")
            self._status("KOTOR → KOTOR preview inputs are incomplete")
            self.update_enabled()
            return None
        try:
            result = self._build_kotor_to_kotor_preview(
                KotorToKotorPreviewRequest(
                    source_model=self.state.source_kotor_model,
                    source_animation_slot=str(self.state.source_kotor_animation_slot or ""),
                    target_model=self.current_target_model(),
                    retarget_profile=self.state.retarget_profile,
                    output_naming=self.state.output_naming,
                    auto_play=auto_play,
                    enable_numeric_audit=True,
                )
            )
            preview = result.preview_result
            if self.viewport is not None:
                self._apply_preview(
                    preview,
                    self.viewport,
                    auto_play=auto_play,
                    show_node_overlay=show_node_overlay,
                )
            self.state.last_kotor_to_kotor_preview_result = result
            self.state.last_kotor_source_sample_result = result.source_sample_result
            self.state.last_preview_result = preview
            self.state.last_export_result = None
            self.last_error = ""
            self._report_kotor_to_kotor_preview_success(result)
            self.update_enabled()
            return preview
        except Exception as exc:
            self.state.last_preview_result = None
            self.state.last_export_result = None
            self.last_error = str(exc)
            self._log(f"KOTOR → KOTOR preview failed: {exc}", "error")
            self._status("KOTOR → KOTOR preview failed")
            self.update_enabled()
            return None

    def _export_kotor_to_kotor_preview(
        self,
        output_mdl_path: str | Path,
        *,
        overwrite: bool,
        write_manifest: bool,
    ) -> Any | None:
        preview = self.state.last_preview_result
        if preview is None or not self.can_export():
            message = (
                "No successful current KOTOR → KOTOR preview is available to export. "
                "Run Preview Retarget before exporting MDL/MDX."
            )
            self.last_error = message
            self._log(message, "warning")
            self._status("KOTOR → KOTOR export blocked")
            self.update_enabled()
            return None
        mdl_path = Path(output_mdl_path)
        try:
            result = self._export_preview(
                RetargetPreviewExportRequest(
                    preview_result=preview,
                    original_target_model=self.current_target_model(),
                    output_mdl_path=mdl_path,
                    output_mdx_path=mdl_path.with_suffix(".mdx"),
                    overwrite=overwrite,
                    verify_roundtrip=True,
                    write_manifest=write_manifest,
                    kotor_output_name_mode=getattr(
                        preview,
                        "output_name_mode",
                        KotorOutputAnimationNameMode.VANILLA_SLOT,
                    ),
                    requires_custom_animation_patch=bool(
                        getattr(preview, "requires_custom_animation_patch", False)
                    ),
                )
            )
            self.state.last_export_result = result
            self.last_error = ""
            self._status(f"KOTOR → KOTOR preview exported: {getattr(result, 'mdl_path', mdl_path)}")
            self.update_enabled()
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self._log(f"KOTOR → KOTOR export failed: {exc}", "error")
            self._status("KOTOR → KOTOR export failed")
            self.update_enabled()
            return None

    def _report_kotor_to_kotor_preview_success(self, result: KotorToKotorPreviewResult) -> None:
        sample_report = result.source_sample_result.report
        preview = result.preview_result
        output_mode = getattr(preview, "output_name_mode", KotorOutputAnimationNameMode.VANILLA_SLOT)
        mode_label = (
            "custom animation patch"
            if output_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
            else "vanilla slot override"
        )
        solver_report = getattr(preview, "solver_report", None)
        message = (
            "KOTOR → KOTOR preview built successfully.\n"
            f"Source animation: {sample_report.resolved_slot_name}\n"
            f"Target animation: {preview.slot_name}\n"
            f"Output mode: {mode_label}\n"
            f"Source sampled poses: {sample_report.sample_count}\n"
            f"Mapped target nodes: {int(getattr(solver_report, 'mapped_node_count', 0) or 0)}"
        )
        self._log(message, "success")
        for warning in result.warnings:
            self._log(str(warning), "warning")
        self._status(f"KOTOR → KOTOR preview ready: {preview.slot_name}")

    def _require_mode(self, mode: RetargetMode, action: str) -> None:
        if self.state.mode != mode:
            raise RetargetWorkbenchError(f"{action} is only available in {get_retarget_mode_spec(mode).label} mode.")

    def _optional_ue_to_kotor_controller(self) -> Any | None:
        if self.state.mode != RetargetMode.UNREAL_TO_KOTOR:
            return None
        return self.ue_to_kotor_controller

    def _require_ue_to_kotor_controller(self) -> Any:
        controller = self._optional_ue_to_kotor_controller()
        if controller is None:
            raise RetargetWorkbenchError("Unreal → KOTOR mode uses the verified GhostRigger preview/export pipeline, but its controller is unavailable.")
        return controller

    def _log(self, message: str, level: str = "info") -> None:
        if self.log_callback is not None:
            self.log_callback(message, level)

    def _status(self, message: str) -> None:
        if self.status_callback is not None:
            self.status_callback(message)


def populate_retarget_mode_combo(combo: Any, *, current_mode: RetargetMode = RetargetMode.UNREAL_TO_KOTOR) -> None:
    """Populate a QComboBox-like widget with all Retarget Workbench modes."""

    if hasattr(combo, "setObjectName"):
        combo.setObjectName("retargetModeComboBox")
    if hasattr(combo, "clear"):
        combo.clear()
    specs = list_retarget_mode_specs()
    current_index = 0
    for index, spec in enumerate(specs):
        combo.addItem(spec.label, spec.mode.value)
        if spec.mode == current_mode:
            current_index = index
    if hasattr(combo, "setCurrentIndex"):
        combo.setCurrentIndex(current_index)
    if hasattr(combo, "setToolTip"):
        combo.setToolTip(get_retarget_mode_spec(current_mode).description)


def combo_current_retarget_mode(combo: Any) -> RetargetMode:
    """Read the current RetargetMode from a QComboBox-like widget."""

    data = combo.currentData() if hasattr(combo, "currentData") else None
    if data is None and hasattr(combo, "currentText"):
        data = combo.currentText()
    return coerce_retarget_mode(data)


def _pending_status_for_mode(mode: RetargetMode) -> str:
    if mode == RetargetMode.KOTOR_TO_KOTOR:
        return "implemented through KOTOR source sampling and verified preview/export"
    if mode == RetargetMode.KOTOR_TO_UNREAL:
        return "KOTOR source animation sampler available; pending UE-compatible FBX export adapter"
    return "pending implementation"


def _human_kind(kind: str) -> str:
    labels = {
        "ue_fbx_source_clip": "UE/FBX animation clip",
        "kotor_aurora_model": "KOTOR Aurora model",
        "kotor_mdl_mdx_animation_override": "MDL/MDX local animation override",
        "kotor_aurora_model_animation_slot": "KOTOR model animation slot",
        "unreal_skeleton": "Unreal skeleton",
        "unreal_fbx_animation_clip": "UE-compatible FBX animation clip",
    }
    return labels.get(kind, kind.replace("_", " "))
