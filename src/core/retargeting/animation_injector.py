"""Sprint 3 reverse animation injector.

R3.A implements extraction and adaptation only:

* import a UE5 FBX animation through headless Blender,
* classify source channels through the reverse rename policy,
* load the PMBAM target to validate Aurora bone coverage,
* write a retarget-ready JSON payload for the later MDL writer stage.

R3.B will consume this payload and append/replace an Aurora animation block in
the native `MDLBinaryWriter` path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from src.core.game.kotor_loader import load_model_from_file

from .blender_animation_injection import run_blender_animation_extraction
from .reverse_renamer import DEFAULT_REVERSE_RENAME_MAP, load_reverse_rename_spec
from .ue5_source_adapter import UE5SourceAdapter


logger = logging.getLogger(__name__)


@dataclass
class AnimationInjectionRequest:
    """Input specification for reverse animation extraction/injection."""

    source_fbx: Path
    target_mdl: Path
    target_slot: str
    output_dir: Path
    rename_map_path: Path = DEFAULT_REVERSE_RENAME_MAP
    target_mdx: Optional[Path] = None
    blender_executable: Optional[Path] = None
    action_name: str = ""
    frame_step: int = 1
    game: str = "K1"

    def __post_init__(self) -> None:
        self.source_fbx = Path(self.source_fbx)
        self.target_mdl = Path(self.target_mdl)
        self.rename_map_path = Path(self.rename_map_path)
        self.output_dir = Path(self.output_dir)
        if self.target_mdx is not None:
            self.target_mdx = Path(self.target_mdx)
        if self.blender_executable is not None:
            self.blender_executable = Path(self.blender_executable)
        if not self.source_fbx.exists():
            raise FileNotFoundError(f"Source FBX not found: {self.source_fbx}")
        if not self.target_mdl.exists():
            raise FileNotFoundError(f"Target MDL not found: {self.target_mdl}")
        if not self.rename_map_path.exists():
            raise FileNotFoundError(f"Reverse rename map not found: {self.rename_map_path}")
        if not str(self.target_slot or "").strip():
            raise ValueError("target_slot is required")
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class AnimationInjectionResult:
    """Output of the R3.A extraction/adaptation phase."""

    success: bool
    source_fbx: Path
    target_mdl_original: Path
    target_slot: str
    phase: str = "R3A_EXTRACT_ONLY"
    source_sha256: str = ""
    target_mdl_original_sha256: str = ""
    extraction_json: Optional[Path] = None
    retargeted_animation_json: Optional[Path] = None
    manifest_path: Optional[Path] = None
    blender_log_path: Optional[Path] = None
    source_bone_count: int = 0
    target_bone_count: int = 0
    mapped_bone_count: int = 0
    dropped_bone_count: int = 0
    collapsed_bone_count: int = 0
    unmapped_bone_count: int = 0
    frame_count: int = 0
    fps: float = 30.0
    duration_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "phase": self.phase,
            "source_fbx": str(self.source_fbx),
            "source_sha256": self.source_sha256,
            "target_mdl_original": str(self.target_mdl_original),
            "target_mdl_original_sha256": self.target_mdl_original_sha256,
            "target_slot": self.target_slot,
            "extraction_json": str(self.extraction_json) if self.extraction_json else None,
            "retargeted_animation_json": (
                str(self.retargeted_animation_json) if self.retargeted_animation_json else None
            ),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "blender_log_path": str(self.blender_log_path) if self.blender_log_path else None,
            "source_bone_count": self.source_bone_count,
            "target_bone_count": self.target_bone_count,
            "mapped_bone_count": self.mapped_bone_count,
            "dropped_bone_count": self.dropped_bone_count,
            "collapsed_bone_count": self.collapsed_bone_count,
            "unmapped_bone_count": self.unmapped_bone_count,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration_seconds": self.duration_seconds,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


class AnimationInjector:
    """Reverse animation extraction/adaptation facade."""

    def __init__(self, adapter: Optional[UE5SourceAdapter] = None):
        self.adapter = adapter or UE5SourceAdapter()

    @staticmethod
    def _sha256(path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _game_version(game: str):
        from src.core.geometry.model_data import GameVersion

        return GameVersion.K2 if str(game or "").upper() == "K2" else GameVersion.K1

    def _load_target_model(self, request: AnimationInjectionRequest):
        mdx = request.target_mdx
        if mdx is None:
            mdx = request.target_mdl.with_suffix(".mdx")
        return load_model_from_file(
            str(request.target_mdl),
            str(mdx) if mdx.exists() else "",
            self._game_version(request.game),
        )

    def extract_for_injection(self, request: AnimationInjectionRequest) -> AnimationInjectionResult:
        """Run R3.A and emit a retarget-ready animation JSON payload."""

        result = AnimationInjectionResult(
            success=False,
            source_fbx=request.source_fbx,
            target_mdl_original=request.target_mdl,
            target_slot=request.target_slot,
        )
        try:
            result.source_sha256 = self._sha256(request.source_fbx)
            result.target_mdl_original_sha256 = self._sha256(request.target_mdl)
            spec = load_reverse_rename_spec(request.rename_map_path)
            target_model = self._load_target_model(request)
            if target_model is None:
                result.errors.append(f"Could not load target MDL: {request.target_mdl}")
                return result
            target_bones = [node.name for node in target_model.all_nodes()]
            result.target_bone_count = len(target_bones)

            extraction_json = request.output_dir / f"{request.source_fbx.stem}_r3a_extraction.json"
            extraction = run_blender_animation_extraction(
                source_fbx=request.source_fbx,
                output_json=extraction_json,
                action_name=request.action_name,
                frame_step=request.frame_step,
                blender_executable=request.blender_executable,
            )
            result.extraction_json = extraction_json
            if extraction.get("log_path"):
                result.blender_log_path = Path(extraction["log_path"])
            if not extraction.get("success"):
                result.errors.extend(str(err) for err in extraction.get("errors", []))
                return result

            source_bones = [str(name).lower() for name in extraction.get("source_bones", [])]
            adapter_result = self.adapter.adapt(source_bones, spec, target_bones)
            result.source_bone_count = int(extraction.get("source_bone_count") or len(source_bones))
            result.mapped_bone_count = len(adapter_result.mapped)
            result.dropped_bone_count = len(adapter_result.dropped)
            result.collapsed_bone_count = len(adapter_result.collapsed)
            result.unmapped_bone_count = len(adapter_result.unmapped)
            result.frame_count = int(extraction.get("frame_count") or 0)
            result.fps = float(extraction.get("fps") or 30.0)
            result.duration_seconds = result.frame_count / result.fps if result.fps else 0.0

            target_curves: dict[str, dict] = {}
            source_curves = extraction.get("curves", {}) or {}
            source_curve_by_key = {str(name).lower(): frames for name, frames in source_curves.items()}
            bone_parent_by_key = {
                str(name).lower(): (str(parent).lower() if parent else None)
                for name, parent in (extraction.get("bone_parents", {}) or {}).items()
            }
            rest_world_by_key = {
                str(name).lower(): data
                for name, data in (extraction.get("rest_world", {}) or {}).items()
            }
            rest_basis_by_key = {
                str(name).lower(): data
                for name, data in (extraction.get("rest_pose_bases", {}) or {}).items()
            }
            for decision in adapter_result.mapped:
                if not decision.target_bone:
                    continue
                frames = source_curve_by_key.get(decision.source_bone)
                if frames is None:
                    result.warnings.append(f"Mapped source bone has no curve data: {decision.source_bone}")
                    continue
                source_parent = bone_parent_by_key.get(decision.source_bone)
                target_curves[decision.target_bone] = {
                    "source_bone": decision.source_bone,
                    "target_bone": decision.target_bone,
                    "space": "source_world_ue5_raw",
                    "conversion_status": "pending_r3b_aurora_basis_remap",
                    "source_rest_world": rest_world_by_key.get(decision.source_bone),
                    "source_rest_basis": rest_basis_by_key.get(decision.source_bone),
                    "source_parent": source_parent,
                    "source_parent_rest_world": (
                        rest_world_by_key.get(source_parent) if source_parent else None
                    ),
                    "source_parent_rest_basis": (
                        rest_basis_by_key.get(source_parent) if source_parent else None
                    ),
                    "source_parent_frames": source_curve_by_key.get(source_parent) if source_parent else None,
                    "frames": frames,
                }

            if result.mapped_bone_count < 19:
                result.errors.append(f"Mapped core count below gate: {result.mapped_bone_count} < 19")
                return result

            retargeted_path = request.output_dir / f"{request.target_mdl.stem}__{request.target_slot}__r3a_animation.json"
            payload = {
                "schema": "sprint3_r3a_retarget_ready_animation",
                "phase": result.phase,
                "source_fbx": str(request.source_fbx),
                "source_sha256": result.source_sha256,
                "target_mdl": str(request.target_mdl),
                "target_mdl_sha256": result.target_mdl_original_sha256,
                "target_slot": request.target_slot,
                "action_name": extraction.get("action_name"),
                "frame_start": extraction.get("frame_start"),
                "frame_end": extraction.get("frame_end"),
                "frame_count": result.frame_count,
                "fps": result.fps,
                "duration_seconds": result.duration_seconds,
                "source_bone_count": result.source_bone_count,
                "target_bone_count": result.target_bone_count,
                "adapter": adapter_result.to_dict(),
                "source_rest_pose_bases": rest_basis_by_key,
                "target_curves": target_curves,
                "notes": [
                    "R3.A extraction keeps UE5 world-space transforms raw.",
                    "R3.B converts source-local deltas through per-bone basis remapping before MDL writing.",
                ],
            }
            retargeted_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result.retargeted_animation_json = retargeted_path

            manifest_path = request.output_dir / f"{request.target_mdl.stem}__{request.target_slot}__r3a_manifest.json"
            result.manifest_path = manifest_path
            result.success = not result.errors
            manifest_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.exception("R3.A animation extraction failed")
            result.errors.append(f"Exception: {type(exc).__name__}: {exc}")
        return result

    def inject(self, request: AnimationInjectionRequest) -> AnimationInjectionResult:
        """Compatibility alias for the current R3.A-only implementation."""

        return self.extract_for_injection(request)
