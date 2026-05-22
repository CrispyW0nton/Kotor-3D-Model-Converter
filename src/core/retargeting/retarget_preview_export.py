"""Export a verified in-memory retarget preview to MDL/MDX."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy
import tempfile
from pathlib import Path
from typing import Any, List

from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)
from src.core.retargeting.retarget_preview import RetargetPreviewResult


class RetargetPreviewExportError(RuntimeError):
    """Raised when a retarget preview cannot be exported safely."""


@dataclass
class RetargetPreviewExportRequest:
    """Inputs for exporting the last approved retarget preview."""

    preview_result: RetargetPreviewResult
    original_target_model: Any
    output_mdl_path: Path
    output_mdx_path: Path
    overwrite: bool = False
    replace_existing: bool = True
    verify_roundtrip: bool = True
    write_manifest: bool = True
    roundtrip_tolerance: float = 1e-4

    def __post_init__(self) -> None:
        self.output_mdl_path = Path(self.output_mdl_path)
        self.output_mdx_path = Path(self.output_mdx_path)


@dataclass
class RetargetPreviewExportResult:
    """Result of writing a retarget preview MDL/MDX candidate."""

    mdl_path: Path
    mdx_path: Path
    manifest_path: Path | None
    slot_name: str
    verified_roundtrip: bool
    warnings: List[str] = field(default_factory=list)


def export_retarget_preview_override(
    request: RetargetPreviewExportRequest,
    *,
    writer: AuroraAnimationWriter | None = None,
) -> RetargetPreviewExportResult:
    """Export the exact animation block from a successful preview result."""

    preview = request.preview_result
    _validate_preview_for_export(preview)
    if request.output_mdx_path != request.output_mdl_path.with_suffix(".mdx"):
        raise RetargetPreviewExportError(
            "Output MDX path must match the MDL basename "
            f"({request.output_mdl_path.with_suffix('.mdx')})."
        )
    existing = [path for path in (request.output_mdl_path, request.output_mdx_path) if path.exists()]
    if existing and not request.overwrite:
        raise RetargetPreviewExportError(
            "Retarget preview export would overwrite existing file(s): "
            + ", ".join(str(path) for path in existing)
        )

    target_mdl = _target_mdl_path(request.original_target_model)
    target_mdx = _target_mdx_path(request.original_target_model, target_mdl)
    warnings = _basename_warnings(request.original_target_model, request.output_mdl_path)
    manifest_path = request.output_mdl_path.with_suffix(".retarget_preview.json")
    request.output_mdl_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_json = _write_temporary_preview_payload(request.output_mdl_path.parent)
    try:
        try:
            injection_request = AuroraAnimationInjectionRequest(
                r3a_animation_json=tmp_json,
                target_mdl=target_mdl,
                target_mdx=target_mdx,
                animation_slot=preview.slot_name,
                output_mdl=request.output_mdl_path,
                output_manifest=manifest_path,
                game=_game_tag(request.original_target_model),
                overwrite_existing=request.replace_existing,
                verify_roundtrip=request.verify_roundtrip,
                roundtrip_tolerance=request.roundtrip_tolerance,
                target_model_override=copy.deepcopy(request.original_target_model),
            )
            export_writer = writer or AuroraAnimationWriter()
            injection_result = export_writer.inject_animation_block(
                injection_request,
                copy.deepcopy(preview.animation_block),
            )
        except Exception as exc:
            _discard_export_outputs(request.output_mdl_path, manifest_path)
            raise RetargetPreviewExportError(f"Export failed: {exc}") from exc
    finally:
        try:
            tmp_json.unlink()
        except OSError:
            pass

    if not injection_result.success:
        _discard_export_outputs(request.output_mdl_path, manifest_path)
        message = "; ".join(injection_result.errors or ["unknown export failure"])
        raise RetargetPreviewExportError(f"Export failed: {message}")

    if not request.write_manifest and manifest_path.exists():
        manifest_path.unlink()
        manifest_path_out: Path | None = None
    else:
        manifest_path_out = manifest_path if manifest_path.exists() else None

    return RetargetPreviewExportResult(
        mdl_path=request.output_mdl_path,
        mdx_path=request.output_mdx_path,
        manifest_path=manifest_path_out,
        slot_name=injection_result.animation_slot or preview.slot_name,
        verified_roundtrip=bool(request.verify_roundtrip),
        warnings=[*warnings, *list(injection_result.warnings or [])],
    )


def _validate_preview_for_export(preview: RetargetPreviewResult | None) -> None:
    if preview is None:
        raise RetargetPreviewExportError(
            "No successful retarget preview is available to export. "
            "Preview the animation in GhostRigger before exporting MDL/MDX."
        )
    audit = getattr(preview, "preview_audit", None)
    if audit is None or not bool(getattr(audit, "passed", False)):
        raise RetargetPreviewExportError(
            "Retarget preview audit did not pass. Run Preview Retarget again "
            "before exporting MDL/MDX."
        )
    if getattr(preview, "animation_block", None) is None:
        raise RetargetPreviewExportError("Retarget preview has no animation block to export.")
    if not str(getattr(preview, "slot_name", "") or "").strip():
        raise RetargetPreviewExportError("Retarget preview has no KOTOR animation slot name.")


def _target_mdl_path(model: Any) -> Path:
    raw = str(getattr(model, "mdl_path", "") or "").strip()
    if not raw:
        raise RetargetPreviewExportError(
            "Original target model has no source MDL path. Load the target from an MDL file before exporting."
        )
    path = Path(raw)
    if not path.exists():
        raise RetargetPreviewExportError(f"Original target MDL path is not available: {raw}")
    return path


def _target_mdx_path(model: Any, target_mdl: Path) -> Path | None:
    raw = str(getattr(model, "mdx_path", "") or "").strip()
    if raw and Path(raw).exists():
        return Path(raw)
    guessed = target_mdl.with_suffix(".mdx")
    return guessed if guessed.exists() else None


def _game_tag(model: Any) -> str:
    raw = getattr(getattr(model, "game_version", None), "name", getattr(model, "game_version", "K1"))
    text = str(raw or "K1").upper()
    return "K2" if text == "K2" else "K1"


def _basename_warnings(model: Any, output_mdl: Path) -> list[str]:
    target_name = str(getattr(model, "name", "") or "").strip()
    if target_name and output_mdl.stem.lower() != target_name.lower():
        return [
            "Override install usually requires the MDL/MDX filename to match "
            f"the target model resref ('{target_name}')."
        ]
    return []


def _write_temporary_preview_payload(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        prefix=".retarget_preview_export_",
        dir=str(directory),
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write('{"frame_count": 0, "target_curves": {}}\n')
        return Path(handle.name)


def _discard_export_outputs(output_mdl: Path, manifest_path: Path) -> None:
    for path in (output_mdl, output_mdl.with_suffix(".mdx"), manifest_path):
        try:
            if Path(path).exists():
                Path(path).unlink()
        except OSError:
            pass
