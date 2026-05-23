"""Inject R3.A retargeted UE5 animation data into an Aurora MDL.

R3.B consumes the JSON emitted by :mod:`animation_injector`, converts raw UE5
world-space rotations into Aurora local orientation controllers, appends a local
animation override, and writes binary MDL/MDX through GhostRigger's native
``MDLBinaryWriter``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import copy
import json
import logging
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from src.core.game.kotor_loader import (
    get_valid_animation_slots,
    load_model_from_file,
    resolve_animation_slot,
)
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.geometry.model_data import (
    Animation,
    GameVersion,
    KotorModel,
    ModelNode,
    ResolvedAnimationSlot,
)
from src.core.retargeting.coordinate_converter import aurora_from_ue5_quat
from src.core.retargeting.coordinate_normalizer import (
    CoordinateNormalizer,
    matrix_to_quat_wxyz,
    normalize_quat_wxyz,
    quat_inverse_wxyz,
    quat_mul_wxyz,
    quat_to_matrix_wxyz,
    wxyz_to_xyzw,
    xyzw_to_wxyz,
)
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    coerce_kotor_output_name_mode,
    validate_custom_kotor_animation_name,
)
from src.core.validation.animation_block_validator import (
    AnimationBlockValidationError,
    validate_animation_block_against_model,
    validate_raw_animation_footprint,
)
from src.core.validation.animation_roundtrip_validator import (
    AnimationRoundTripValidationError,
    verify_written_animation_override_roundtrip,
)


logger = logging.getLogger(__name__)


CTRL_POSITION = 8
CTRL_ORIENTATION = 20


class InvalidAnimationSlotError(ValueError):
    """Raised when export tries to write a non-KOTOR animation slot."""


def _coerce_matrix3(value: Iterable[Iterable[float]]) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape == (4, 4):
        matrix = matrix[:3, :3]
    if matrix.shape != (3, 3):
        raise ValueError(f"Basis matrix must be 3x3 or 4x4, got {matrix.shape}")
    return matrix


def compute_basis_change_matrix(ue5_rest_basis: np.ndarray, aurora_rest_basis: np.ndarray) -> np.ndarray:
    """Return the per-bone basis bridge where ``M`` sends Aurora -> UE5.

    Both inputs are local-to-world rest bases in the same coordinate system.
    Therefore ``M = inverse(B_ue5) @ B_aurora`` converts target-local vectors
    into source-local vectors.  Animation deltas are moved back into Aurora
    local space with ``inverse(M) @ R_ue5 @ M``.
    """

    ue5_basis = _coerce_matrix3(ue5_rest_basis)
    aurora_basis = _coerce_matrix3(aurora_rest_basis)
    ue5_det = float(np.linalg.det(ue5_basis))
    aurora_det = float(np.linalg.det(aurora_basis))
    if abs(ue5_det) <= 1e-8:
        raise ValueError(f"Degenerate UE5 rest basis determinant: {ue5_det}")
    if abs(aurora_det) <= 1e-8:
        raise ValueError(f"Degenerate Aurora rest basis determinant: {aurora_det}")
    return np.linalg.inv(ue5_basis) @ aurora_basis


def conjugate_rotation_matrix(rotation: np.ndarray, basis_change_matrix: np.ndarray) -> np.ndarray:
    """Conjugate a source-local rotation through a per-bone basis change."""

    rot = _coerce_matrix3(rotation)
    basis = _coerce_matrix3(basis_change_matrix)
    return np.linalg.inv(basis) @ rot @ basis


def conjugate_quat_wxyz(quat_wxyz: Iterable[float], basis_change_matrix: np.ndarray) -> np.ndarray:
    """Conjugate a WXYZ quaternion through ``basis_change_matrix``."""

    rotated = conjugate_rotation_matrix(
        quat_to_matrix_wxyz(quat_wxyz)[:3, :3],
        basis_change_matrix,
    )
    return matrix_to_quat_wxyz(rotated)


def _format_slot_suggestions(slots: List[str], *, limit: int = 12) -> str:
    if not slots:
        return "(no local or inherited slots resolved)"
    shown = slots[:limit]
    suffix = "" if len(slots) <= limit else f", ... ({len(slots) - limit} more)"
    return ", ".join(shown) + suffix


def _normalize_source_reference_mode(mode: str) -> str:
    """Return the source pose reference policy used by R3.B.

    ``hybrid_limb_source_rest`` keeps root/torso motion stable while treating
    shoulder/arm/finger frame-0 poses as motion from the FBX bind pose.  This is
    the safest current default for UE idle clips on PMBAM: it lowers/extents the
    upper limbs without copying a whole-body bind-to-idle bend into Aurora's
    torso or lower-body stacks.
    """

    normalized = str(mode or "hybrid_limb_source_rest").strip().lower().replace("-", "_")
    aliases = {
        "bind": "source_rest",
        "bind_rest": "source_rest",
        "rest": "source_rest",
        "source_rest": "source_rest",
        "hybrid": "hybrid_limb_source_rest",
        "hybrid_limb": "hybrid_limb_source_rest",
        "hybrid_limb_source_rest": "hybrid_limb_source_rest",
        "limb_source_rest": "hybrid_limb_source_rest",
        "clip_frame_0": "clip_frame_zero",
        "clip_frame_zero": "clip_frame_zero",
        "frame0": "clip_frame_zero",
        "frame_0": "clip_frame_zero",
    }
    if normalized not in aliases:
        raise ValueError(
            "source_reference_mode must be 'hybrid_limb_source_rest', 'source_rest', or 'clip_frame_zero', "
            f"got '{mode}'."
        )
    return aliases[normalized]


def _curve_reference_mode(reference_mode: str, curve: dict, target_node: ModelNode) -> str:
    """Return the source reference policy for one R3.A curve."""

    if reference_mode != "hybrid_limb_source_rest":
        return reference_mode
    target_name = str(getattr(target_node, "name", "") or "").lower()
    source_name = str(curve.get("source_bone") or "").lower()
    limb_tokens = (
        "clavicle",
        "collar",
        "shoulder",
        "bicep",
        "upperarm",
        "forearm",
        "lowerarm",
        "hand",
        "fngr",
        "finger",
        "thumb",
    )
    if any(token in target_name or token in source_name for token in limb_tokens):
        return "source_rest"
    return "clip_frame_zero"


def _clamped_weight(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.35
    if not math.isfinite(numeric):
        return 0.35
    return max(0.0, min(1.0, numeric))


def _slerp_xyzw(
    a_xyzw: Iterable[float],
    b_xyzw: Iterable[float],
    t: float,
) -> List[float]:
    """Shortest-path slerp for Aurora/GhostRigger XYZW quaternions."""

    a = np.asarray(list(a_xyzw), dtype=np.float64)
    b = np.asarray(list(b_xyzw), dtype=np.float64)
    if a.shape[0] < 4:
        a = np.pad(a, (0, 4 - a.shape[0]))
        a[3] = 1.0
    if b.shape[0] < 4:
        b = np.pad(b, (0, 4 - b.shape[0]))
        b[3] = 1.0
    a = a[:4]
    b = b[:4]
    a_norm = float(np.linalg.norm(a))
    b_norm = float(np.linalg.norm(b))
    if a_norm <= 1e-12:
        a = np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    else:
        a = a / a_norm
    if b_norm <= 1e-12:
        b = np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    else:
        b = b / b_norm

    dot = float(np.dot(a, b))
    if dot < 0.0:
        b = -b
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    amount = _clamped_weight(t)
    if dot > 0.9995:
        out = a + amount * (b - a)
        out_norm = float(np.linalg.norm(out))
        if out_norm <= 1e-12:
            out = np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
        else:
            out = out / out_norm
        return [float(value) for value in out]

    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * amount
    sin_theta = math.sin(theta)
    scale_a = math.cos(theta) - dot * sin_theta / sin_theta_0
    scale_b = sin_theta / sin_theta_0
    out = scale_a * a + scale_b * b
    return [float(value) for value in out / float(np.linalg.norm(out))]


def prepare_local_animation_override_for_export(
    target_model: KotorModel,
    animation_block: Animation,
    requested_slot_name: str,
    *,
    game: Optional[object] = None,
    resource_manager: object | None = None,
    require_valid_slot: bool = True,
    replace_existing: bool = True,
    kotor_output_name_mode: KotorOutputAnimationNameMode | str = KotorOutputAnimationNameMode.VANILLA_SLOT,
) -> tuple[Animation, ResolvedAnimationSlot]:
    """Validate and prepare a local animation override before MDL export.

    The caller receives a deep-copied animation block whose name is the
    canonical KOTOR slot resolved from the target model/supermodel chain. The
    original animation is not mutated, and no model state or output files are
    touched by this helper.
    """

    requested = str(requested_slot_name or "").strip()
    name_mode = coerce_kotor_output_name_mode(kotor_output_name_mode)
    if name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH:
        custom_name = validate_custom_kotor_animation_name(requested)
        if not replace_existing:
            wanted = custom_name.lower()
            if any(str(anim.name or "").lower() == wanted for anim in getattr(target_model, "animations", [])):
                raise ValueError(f"Local animation '{custom_name}' already exists")
        prepared = copy.deepcopy(animation_block)
        prepared.name = custom_name
        return prepared, ResolvedAnimationSlot(
            slot_name=custom_name,
            animation=None,
            source_model_name=str(getattr(target_model, "name", "") or ""),
            inherited=False,
            cumulative_scale=1.0,
            transtime=float(getattr(prepared, "transition_time", 0.25) or 0.25),
            anim_root=str(getattr(prepared, "anim_root", "") or ""),
            events=list(getattr(prepared, "events", []) or []),
        )
    try:
        resolved_slot = resolve_animation_slot(
            target_model,
            requested,
            game=game,
            resource_manager=resource_manager,
            require_valid=require_valid_slot,
        )
    except ValueError as exc:
        valid_slots = get_valid_animation_slots(
            target_model,
            game=game,
            resource_manager=resource_manager,
        )
        target_name = str(getattr(target_model, "name", "") or "target model")
        raise InvalidAnimationSlotError(
            f"Invalid animation slot '{requested}' for target '{target_name}'. "
            "Valid slots are inherited from the target model/supermodel chain. "
            f"Choose one of: {_format_slot_suggestions(valid_slots)}. "
            "UE clip names are not KOTOR animation slot names."
        ) from exc

    prepared = copy.deepcopy(animation_block)
    prepared.name = resolved_slot.slot_name
    if resolved_slot.animation is not None:
        prepared.transition_time = resolved_slot.transtime
        if resolved_slot.anim_root and not prepared.anim_root:
            prepared.anim_root = resolved_slot.anim_root
        if resolved_slot.events and not prepared.events:
            prepared.events = copy.deepcopy(resolved_slot.events)

    if not replace_existing:
        wanted = resolved_slot.slot_name.lower()
        if any(str(anim.name or "").lower() == wanted for anim in getattr(target_model, "animations", [])):
            raise ValueError(f"Local animation '{resolved_slot.slot_name}' already exists")

    return prepared, resolved_slot


@dataclass
class AuroraAnimationInjectionRequest:
    """Input contract for R3.B MDL injection."""

    r3a_animation_json: Path
    target_mdl: Path
    animation_slot: str
    output_mdl: Path
    output_manifest: Path
    target_mdx: Optional[Path] = None
    game: str = "K1"
    fps: float = 30.0
    overwrite_existing: bool = True
    write_zero_position_controllers: bool = False
    max_size_multiplier: float = 5.0
    verify_roundtrip: bool = False
    roundtrip_tolerance: float = 1e-4
    target_model_override: Optional[KotorModel] = None
    source_reference_mode: str = "hybrid_limb_source_rest"
    hybrid_limb_source_rest_weight: float = 0.35
    kotor_output_name_mode: KotorOutputAnimationNameMode = KotorOutputAnimationNameMode.VANILLA_SLOT
    requires_custom_animation_patch: bool = False

    def __post_init__(self) -> None:
        self.r3a_animation_json = Path(self.r3a_animation_json)
        self.target_mdl = Path(self.target_mdl)
        self.output_mdl = Path(self.output_mdl)
        self.output_manifest = Path(self.output_manifest)
        if self.target_mdx is not None:
            self.target_mdx = Path(self.target_mdx)
        if not self.r3a_animation_json.exists():
            raise FileNotFoundError(f"R3.A JSON not found: {self.r3a_animation_json}")
        if not self.target_mdl.exists():
            raise FileNotFoundError(f"Target MDL not found: {self.target_mdl}")
        if not str(self.animation_slot or "").strip():
            raise ValueError("animation_slot is required")
        self.output_mdl.parent.mkdir(parents=True, exist_ok=True)
        self.output_manifest.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class AuroraAnimationInjectionResult:
    """Result for R3.B binary MDL injection."""

    success: bool
    phase: str = "R3B_MDL_INJECTION"
    input_mdl_sha256: str = ""
    output_mdl_sha256: str = ""
    output_mdx_sha256: str = ""
    output_mdl: Optional[Path] = None
    output_mdx: Optional[Path] = None
    manifest_path: Optional[Path] = None
    animation_slot: str = ""
    frame_count: int = 0
    fps: float = 30.0
    duration_seconds: float = 0.0
    bone_count_animated: int = 0
    operation: str = ""
    input_size_bytes: int = 0
    output_size_bytes: int = 0
    kotor_output_name_mode: str = KotorOutputAnimationNameMode.VANILLA_SLOT.value
    requires_custom_animation_patch: bool = False
    vanilla_slot_safe: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "phase": self.phase,
            "input_mdl_sha256": self.input_mdl_sha256,
            "output_mdl_sha256": self.output_mdl_sha256,
            "output_mdx_sha256": self.output_mdx_sha256,
            "output_mdl": str(self.output_mdl) if self.output_mdl else None,
            "output_mdx": str(self.output_mdx) if self.output_mdx else None,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "animation_slot": self.animation_slot,
            "frame_count": self.frame_count,
            "fps": self.fps,
            "duration_seconds": self.duration_seconds,
            "bone_count_animated": self.bone_count_animated,
            "operation": self.operation,
            "input_size_bytes": self.input_size_bytes,
            "output_size_bytes": self.output_size_bytes,
            "kotor_output_name_mode": self.kotor_output_name_mode,
            "requires_custom_animation_patch": self.requires_custom_animation_patch,
            "vanilla_slot_safe": self.vanilla_slot_safe,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


class AuroraAnimationWriter:
    """Build and inject Aurora animation controllers into a loaded model."""

    @staticmethod
    def sha256(path: Path) -> str:
        sha = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _game_version(game: str) -> GameVersion:
        return GameVersion.K2 if str(game or "").upper() == "K2" else GameVersion.K1

    def inject(self, request: AuroraAnimationInjectionRequest) -> AuroraAnimationInjectionResult:
        """Load target MDL, append/replace local animation, write binary MDL/MDX."""

        result = AuroraAnimationInjectionResult(
            success=False,
            animation_slot=request.animation_slot,
            output_mdl=request.output_mdl,
            output_mdx=request.output_mdl.with_suffix(".mdx"),
            manifest_path=request.output_manifest,
            fps=float(request.fps or 30.0),
            kotor_output_name_mode=coerce_kotor_output_name_mode(request.kotor_output_name_mode).value,
            requires_custom_animation_patch=bool(request.requires_custom_animation_patch),
            vanilla_slot_safe=not bool(request.requires_custom_animation_patch),
        )
        try:
            result.input_mdl_sha256 = self.sha256(request.target_mdl)
            result.input_size_bytes = request.target_mdl.stat().st_size

            with open(request.r3a_animation_json, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            model = self._load_model(request)
            if model is None:
                result.errors.append(f"Could not load target MDL: {request.target_mdl}")
                return self._finish(result, request)

            original_model_for_roundtrip = copy.deepcopy(model) if request.verify_roundtrip else None

            animation = self.build_animation_from_r3a(
                payload=payload,
                model=model,
                slot_name=request.animation_slot,
                fps=request.fps,
                write_zero_position_controllers=request.write_zero_position_controllers,
                source_reference_mode=request.source_reference_mode,
                hybrid_limb_source_rest_weight=request.hybrid_limb_source_rest_weight,
                warnings=result.warnings,
            )
            result.frame_count = int(payload.get("frame_count") or 0)
            result.duration_seconds = float(animation.length or 0.0)
            result.bone_count_animated = len(animation.nodes)
            amplitude_issues = self._validate_export_motion_amplitude(payload, animation)
            if amplitude_issues:
                result.errors.append(
                    "Exported animation lost source motion amplitude before MDL write: "
                    + "; ".join(amplitude_issues[:8])
                )
                return self._finish(result, request)

            self._write_animation_block_to_output(
                request=request,
                result=result,
                model=model,
                animation=animation,
                original_model_for_roundtrip=original_model_for_roundtrip,
            )
            if result.errors:
                return result
        except Exception as exc:
            logger.exception("Aurora animation injection failed")
            result.errors.append(f"Exception: {type(exc).__name__}: {exc}")
            return result
        return self._finish(result, request)

    def inject_animation_block(
        self,
        request: AuroraAnimationInjectionRequest,
        animation_block: Animation,
    ) -> AuroraAnimationInjectionResult:
        """Inject an already-built Aurora animation block through export gates."""

        result = AuroraAnimationInjectionResult(
            success=False,
            animation_slot=request.animation_slot,
            output_mdl=request.output_mdl,
            output_mdx=request.output_mdl.with_suffix(".mdx"),
            manifest_path=request.output_manifest,
            fps=float(request.fps or 30.0),
            kotor_output_name_mode=coerce_kotor_output_name_mode(request.kotor_output_name_mode).value,
            requires_custom_animation_patch=bool(request.requires_custom_animation_patch),
            vanilla_slot_safe=not bool(request.requires_custom_animation_patch),
        )
        try:
            result.input_mdl_sha256 = self.sha256(request.target_mdl)
            result.input_size_bytes = request.target_mdl.stat().st_size
            model = self._load_model(request)
            if model is None:
                result.errors.append(f"Could not load target MDL: {request.target_mdl}")
                return self._finish(result, request)

            result.frame_count = self._animation_frame_count(animation_block)
            result.duration_seconds = float(animation_block.length or 0.0)
            result.bone_count_animated = len(getattr(animation_block, "nodes", []) or [])
            original_model_for_roundtrip = copy.deepcopy(model) if request.verify_roundtrip else None

            self._write_animation_block_to_output(
                request=request,
                result=result,
                model=model,
                animation=copy.deepcopy(animation_block),
                original_model_for_roundtrip=original_model_for_roundtrip,
            )
            if result.errors:
                return result
        except Exception as exc:
            logger.exception("Aurora animation block injection failed")
            result.errors.append(f"Exception: {type(exc).__name__}: {exc}")
            return result
        return self._finish(result, request)

    def _finish(
        self,
        result: AuroraAnimationInjectionResult,
        request: AuroraAnimationInjectionRequest,
    ) -> AuroraAnimationInjectionResult:
        request.output_manifest.write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result

    @staticmethod
    def _discard_outputs(request: AuroraAnimationInjectionRequest) -> None:
        for path in (
            request.output_mdl,
            request.output_mdl.with_suffix(".mdx"),
            request.output_manifest,
        ):
            try:
                if Path(path).exists():
                    Path(path).unlink()
            except OSError:
                logger.warning("Could not discard failed export output: %s", path)

    def _load_model(self, request: AuroraAnimationInjectionRequest) -> Optional[KotorModel]:
        override = getattr(request, "target_model_override", None)
        if override is not None:
            model = copy.deepcopy(override)
            model.mdl_path = str(request.target_mdl)
            model.mdx_path = str(request.target_mdx or request.target_mdl.with_suffix(".mdx"))
            return model
        mdx = request.target_mdx or request.target_mdl.with_suffix(".mdx")
        return load_model_from_file(
            str(request.target_mdl),
            str(mdx) if mdx.exists() else "",
            self._game_version(request.game),
        )

    def _load_output_model(self, mdl_path: Path, game: str) -> Optional[KotorModel]:
        mdx = mdl_path.with_suffix(".mdx")
        return load_model_from_file(
            str(mdl_path),
            str(mdx) if mdx.exists() else "",
            self._game_version(game),
        )

    def _write_animation_block_to_output(
        self,
        *,
        request: AuroraAnimationInjectionRequest,
        result: AuroraAnimationInjectionResult,
        model: KotorModel,
        animation: Animation,
        original_model_for_roundtrip: Optional[KotorModel],
    ) -> None:
        try:
            animation, resolved_slot = prepare_local_animation_override_for_export(
                model,
                animation,
                request.animation_slot,
                game=request.game,
                require_valid_slot=True,
                replace_existing=request.overwrite_existing,
                kotor_output_name_mode=request.kotor_output_name_mode,
            )
        except InvalidAnimationSlotError as exc:
            result.errors.append(str(exc))
            return
        except ValueError as exc:
            result.errors.append(str(exc))
            return
        result.animation_slot = resolved_slot.slot_name

        validation = validate_animation_block_against_model(model, animation, strict=True)
        try:
            validation.raise_for_errors(animation.name, getattr(model, "name", "") or "target model")
        except AnimationBlockValidationError as exc:
            result.errors.append(str(exc))
            return

        existing_index = self._find_local_animation_index(model, resolved_slot.slot_name)
        if existing_index is None:
            model.animations.append(animation)
            result.operation = "appended_local_override"
        elif request.overwrite_existing:
            model.animations[existing_index] = animation
            result.operation = "replaced_local"
        else:
            result.errors.append(f"Local animation '{resolved_slot.slot_name}' already exists")
            return

        source_mdx = request.target_mdx or request.target_mdl.with_suffix(".mdx")
        MDLBinaryWriter().write_animation_override_files(
            model,
            request.target_mdl,
            source_mdx if source_mdx.exists() else None,
            request.output_mdl,
            animation,
            replace_existing=request.overwrite_existing,
        )
        if not request.output_mdl.exists():
            result.errors.append(f"Output MDL was not written: {request.output_mdl}")
            return

        raw_footprint = validate_raw_animation_footprint(
            request.output_mdl.read_bytes(),
            resolved_slot.slot_name,
        )
        if not raw_footprint.success:
            result.errors.append(
                f"Exported animation '{resolved_slot.slot_name}' failed raw UpdateAnimFootprint validation: "
                + "; ".join(raw_footprint.issues[:5])
            )
            self._discard_outputs(request)
            return

        result.output_size_bytes = request.output_mdl.stat().st_size
        if (
            result.input_size_bytes > 0
            and result.output_size_bytes > result.input_size_bytes * request.max_size_multiplier
        ):
            result.errors.append(
                "Output MDL grew beyond size gate: "
                f"{result.output_size_bytes} > {request.max_size_multiplier}x {result.input_size_bytes}"
            )
            return

        reloaded = self._load_output_model(request.output_mdl, request.game)
        if reloaded is None:
            result.errors.append(f"Output MDL failed reload: {request.output_mdl}")
            return
        if self._find_local_animation_index(reloaded, resolved_slot.slot_name) is None:
            result.errors.append(f"Animation '{resolved_slot.slot_name}' missing after reload")
            return

        if request.verify_roundtrip:
            roundtrip_report = verify_written_animation_override_roundtrip(
                original_model=original_model_for_roundtrip or model,
                prepared_animation=animation,
                written_mdl_path=request.output_mdl,
                written_mdx_path=request.output_mdl.with_suffix(".mdx"),
                slot_name=resolved_slot.slot_name,
                tolerance=request.roundtrip_tolerance,
                game_version=self._game_version(request.game),
            )
            try:
                roundtrip_report.raise_for_errors(resolved_slot.slot_name)
            except AnimationRoundTripValidationError as exc:
                result.errors.append(str(exc))
                self._discard_outputs(request)
                return
            for warning in roundtrip_report.warnings:
                result.warnings.append(warning.message)

        result.output_mdl_sha256 = self.sha256(request.output_mdl)
        mdx_path = request.output_mdl.with_suffix(".mdx")
        if mdx_path.exists():
            result.output_mdx = mdx_path
            result.output_mdx_sha256 = self.sha256(mdx_path)
        result.success = True

    @staticmethod
    def _animation_frame_count(animation: Animation) -> int:
        frame_count = 0
        for node in getattr(animation, "nodes", []) or []:
            for ctrl in getattr(node, "controllers", []) or []:
                frame_count = max(frame_count, len(ctrl.get("times", []) or []))
        return frame_count

    @classmethod
    def _validate_export_motion_amplitude(
        cls,
        payload: dict,
        animation: Animation,
        *,
        source_motion_threshold_degrees: float = 1.0,
        minimum_ratio: float = 0.5,
    ) -> List[str]:
        """Return issues when important source tracks are flattened in export."""

        nodes_by_key = {
            str(getattr(node, "name", "") or "").lower(): node
            for node in getattr(animation, "nodes", []) or []
        }
        issues: List[str] = []
        target_curves = payload.get("target_curves", {}) or {}
        for requested_name, curve in target_curves.items():
            target_name = str(curve.get("target_bone") or requested_name or "")
            if not cls._is_motion_gate_node(target_name):
                continue
            source_amp = cls._source_world_rotation_amplitude_degrees(curve)
            if source_amp < source_motion_threshold_degrees:
                continue
            anim_node = nodes_by_key.get(target_name.lower())
            export_amp = cls._export_orientation_amplitude_degrees(anim_node) if anim_node else 0.0
            if export_amp + 1e-5 < source_amp * minimum_ratio:
                issues.append(
                    f"{target_name} source={source_amp:.3f}deg export={export_amp:.3f}deg"
                )
        return issues

    @staticmethod
    def _is_motion_gate_node(node_name: str) -> bool:
        key = str(node_name or "").lower()
        if key in {"rootdummy", "pelvis_g", "torso_g", "torsoupr_g"}:
            return True
        return any(
            token in key
            for token in (
                "collar",
                "bicep",
                "forearm",
                "hand",
                "thigh",
                "shin",
            )
        )

    @classmethod
    def _source_world_rotation_amplitude_degrees(cls, curve: dict) -> float:
        frames = sorted(curve.get("frames", []) or [], key=lambda item: int(item.get("frame") or 0))
        rotations = [
            cls._normalize_quat_wxyz(cls._four_floats(frame.get("rotation_wxyz"), (1.0, 0.0, 0.0, 0.0)))
            for frame in frames
        ]
        return cls._rotation_amplitude_wxyz(rotations)

    @classmethod
    def _export_orientation_amplitude_degrees(cls, node: Optional[ModelNode]) -> float:
        if node is None:
            return 0.0
        for ctrl in getattr(node, "controllers", []) or []:
            if int(ctrl.get("type", 0) or 0) == CTRL_ORIENTATION or str(ctrl.get("name", "")).lower() == "orientation":
                rotations = [
                    cls._normalize_quat_wxyz(xyzw_to_wxyz(row[:4]))
                    for row in (ctrl.get("values", []) or [])
                    if len(row or []) >= 4
                ]
                return cls._rotation_amplitude_wxyz(rotations)
        return 0.0

    @staticmethod
    def _normalize_quat_wxyz(values: Iterable[float]) -> Tuple[float, float, float, float]:
        raw = list(values) if values is not None else []
        padded = (raw + [1.0, 0.0, 0.0, 0.0])[:4]
        quat = np.asarray([float(value) for value in padded], dtype=np.float64)
        norm = float(np.linalg.norm(quat))
        if norm <= 1e-12 or not math.isfinite(norm):
            return (1.0, 0.0, 0.0, 0.0)
        return tuple(float(value) for value in quat / norm)  # type: ignore[return-value]

    @staticmethod
    def _rotation_amplitude_wxyz(rotations: List[Tuple[float, float, float, float]]) -> float:
        if not rotations:
            return 0.0
        first = rotations[0]
        max_angle = 0.0
        for quat in rotations[1:]:
            dot = abs(sum(a * b for a, b in zip(first, quat)))
            dot = max(-1.0, min(1.0, dot))
            max_angle = max(max_angle, math.degrees(2.0 * math.acos(dot)))
        return max_angle

    def build_animation_from_r3a(
        self,
        payload: dict,
        model: KotorModel,
        slot_name: str,
        fps: float = 30.0,
        write_zero_position_controllers: bool = True,
        source_reference_mode: str = "hybrid_limb_source_rest",
        hybrid_limb_source_rest_weight: float = 0.35,
        warnings: Optional[List[str]] = None,
    ) -> Animation:
        """Create an Aurora ``Animation`` from R3.A target curves."""

        warnings = warnings if warnings is not None else []
        reference_mode = _normalize_source_reference_mode(source_reference_mode)
        hybrid_weight = _clamped_weight(hybrid_limb_source_rest_weight)
        frame_count = int(payload.get("frame_count") or 0)
        duration = float(payload.get("duration_seconds") or 0.0)
        if duration <= 0.0 and frame_count > 0:
            duration = frame_count / float(fps or 30.0)
        anim = Animation(
            name=slot_name,
            length=duration,
            transition_time=0.25,
            anim_root=getattr(getattr(model, "root_node", None), "name", "") or getattr(model, "name", ""),
        )

        aurora_rest_bases = self._capture_aurora_rest_bases(model)
        target_curves = payload.get("target_curves", {}) or {}
        orientation_tracks: Dict[str, Tuple[List[float], List[List[float]]]] = {}
        position_tracks: Dict[str, Tuple[List[float], List[List[float]]]] = {}
        canonical_times: List[float] = []
        for requested_name, curve in sorted(target_curves.items()):
            target_node = model.find_node(curve.get("target_bone") or requested_name)
            if target_node is None:
                warnings.append(f"Skipping missing target node: {requested_name}")
                continue

            frames = sorted(curve.get("frames", []) or [], key=lambda item: int(item.get("frame") or 0))
            if not frames:
                warnings.append(f"Skipping target node with no frames: {target_node.name}")
                continue

            times = self._normalized_times(frames, fps)
            source_rest = curve.get("source_rest_world")
            source_parent_rest = curve.get("source_parent_rest_world")
            parent_frames = sorted(
                curve.get("source_parent_frames", []) or [],
                key=lambda item: int(item.get("frame") or 0),
            )
            curve_reference_mode = _curve_reference_mode(reference_mode, curve, target_node)
            source_reference_frame = frames[0]
            source_parent_reference_frame = parent_frames[0] if parent_frames else None
            if curve_reference_mode == "source_rest":
                source_reference_frame = None
                source_parent_reference_frame = None
            basis_change = self._basis_change_for_curve(
                curve=curve,
                target_node=target_node,
                source_rest=source_rest,
                aurora_rest_bases=aurora_rest_bases,
            )
            rotations = []
            for index, frame in enumerate(frames):
                parent_frame = parent_frames[index] if index < len(parent_frames) else None
                source_rest_rotation = self._motion_rotation_xyzw_from_ue5_world(
                    frame,
                    target_node,
                    source_rest,
                    source_parent_rest,
                    parent_frame,
                    basis_change,
                    source_reference_frame,
                    source_parent_reference_frame,
                )
                if reference_mode == "hybrid_limb_source_rest" and curve_reference_mode == "source_rest":
                    frame_zero_rotation = self._motion_rotation_xyzw_from_ue5_world(
                        frame,
                        target_node,
                        source_rest,
                        source_parent_rest,
                        parent_frame,
                        basis_change,
                        frames[0],
                        parent_frames[0] if parent_frames else None,
                    )
                    rotations.append(_slerp_xyzw(frame_zero_rotation, source_rest_rotation, hybrid_weight))
                else:
                    rotations.append(source_rest_rotation)
            rotations = self._hemisphere_continuous_xyzw(rotations)
            self._validate_controller_rows(target_node.name, times, rotations, 4)
            key = str(target_node.name or "").lower()
            orientation_tracks[key] = (times, rotations)
            position_tracks[key] = (
                times,
                self._position_values_from_frames(frames, default_position=target_node.position),
            )
            canonical_times = self._merge_controller_times(canonical_times, times)

        if not canonical_times:
            canonical_times = self._fallback_animation_times(frame_count, duration, fps)
        if canonical_times:
            anim.length = max(float(anim.length or 0.0), max(canonical_times))

        root_motion_present = any(
            self._is_root_or_pelvis_node(model, node_name)
            and self._position_values_have_motion(values)
            for node_name, (_times, values) in position_tracks.items()
        )

        for target_node in model.all_nodes():
            key = str(target_node.name or "").lower()
            times, rotations = orientation_tracks.get(
                key,
                (
                    canonical_times,
                    self._constant_orientation_values(target_node.rotation, len(canonical_times)),
                ),
            )
            rotations = self._hemisphere_continuous_xyzw(rotations)
            self._validate_controller_rows(target_node.name, times, rotations, 4)

            controllers = []
            if write_zero_position_controllers:
                controllers.append(
                    {
                        "type": CTRL_POSITION,
                        "name": "position",
                        "columns": 3,
                        "times": times,
                        "values": [[0.0, 0.0, 0.0] for _ in times],
                    }
                )
            elif root_motion_present and self._is_root_or_pelvis_node(model, key):
                pos_times, pos_values = position_tracks.get(
                    key,
                    (
                        canonical_times,
                        [
                            [float(target_node.position[0]), float(target_node.position[1]), float(target_node.position[2])]
                            for _ in canonical_times
                        ],
                    ),
                )
                self._validate_controller_rows(target_node.name, pos_times, pos_values, 3)
                controllers.append(
                    {
                        "type": CTRL_POSITION,
                        "name": "position",
                        "columns": 3,
                        "times": pos_times,
                        "values": pos_values,
                    }
                )
            controllers.append(
                {
                    "type": CTRL_ORIENTATION,
                    "name": "orientation",
                    "columns": 4,
                    "times": times,
                    "values": rotations,
                }
            )

            anim.nodes.append(ModelNode(name=target_node.name, controllers=controllers))

        if write_zero_position_controllers:
            warnings.append(
                "R3.B writes zero Aurora position deltas to preserve PMBAM bind proportions."
            )
        else:
            warnings.append(
                "R3.B/R3.5 omits Aurora position controllers to preserve PMBAM bind proportions."
            )
        warnings.append("R3.5 per-bone local basis remapping enabled for orientation controllers.")
        if reference_mode == "clip_frame_zero":
            warnings.append(
                "R3.5 uses source clip frame 0 as the retarget reference pose before applying motion deltas."
            )
        elif reference_mode == "hybrid_limb_source_rest":
            warnings.append(
                "R3.5 uses source rest as the shoulder/arm/finger reference and source frame 0 as the "
                f"root/torso/lower-body reference (upper-limb rest weight={hybrid_weight:.3f})."
            )
        else:
            warnings.append(
                "R3.5 uses the FBX bind/rest pose as the source retarget reference before applying motion deltas."
            )
        warnings.append(
            "R3.6 emits full-hierarchy Aurora orientation controllers, including constant keys for "
            "unmoving target nodes, so in-game playback does not fall back to A-pose branches."
        )
        if root_motion_present:
            warnings.append(
                "R3.6 detected source root motion and emitted root/pelvis position controllers."
            )
        return anim

    @staticmethod
    def _normalized_times(frames: List[dict], fps: float) -> List[float]:
        if not frames:
            return []
        raw = [
            float(frame.get("time_seconds"))
            if frame.get("time_seconds") is not None
            else float(index) / float(fps or 30.0)
            for index, frame in enumerate(frames)
        ]
        start = raw[0]
        return [max(0.0, value - start) for value in raw]

    @staticmethod
    def _merge_controller_times(existing: List[float], incoming: List[float]) -> List[float]:
        merged = [float(value) for value in existing]
        merged.extend(float(value) for value in incoming)
        finite = [value for value in merged if math.isfinite(value) and value >= 0.0]
        return sorted(set(round(value, 7) for value in finite))

    @staticmethod
    def _fallback_animation_times(frame_count: int, duration: float, fps: float) -> List[float]:
        if frame_count <= 1:
            return [0.0]
        if duration > 0.0:
            step = float(duration) / float(max(1, frame_count - 1))
            return [round(index * step, 7) for index in range(frame_count)]
        step = 1.0 / float(fps or 30.0)
        return [round(index * step, 7) for index in range(frame_count)]

    @staticmethod
    def _normalize_quat_xyzw(values: Iterable[float]) -> List[float]:
        raw = list(values or [])
        padded = (raw + [0.0, 0.0, 0.0, 1.0])[:4]
        quat = np.asarray([float(value) for value in padded], dtype=np.float64)
        norm = float(np.linalg.norm(quat))
        if norm <= 1e-12 or not math.isfinite(norm):
            return [0.0, 0.0, 0.0, 1.0]
        return [float(value) for value in quat / norm]

    @classmethod
    def _hemisphere_continuous_xyzw(cls, values: List[List[float]]) -> List[List[float]]:
        result: List[List[float]] = []
        previous: Optional[np.ndarray] = None
        for raw in values:
            quat = np.asarray(cls._normalize_quat_xyzw(raw), dtype=np.float64)
            if previous is not None and float(np.dot(previous, quat)) < 0.0:
                quat = -quat
            result.append([float(value) for value in quat])
            previous = quat
        return result

    @classmethod
    def _constant_orientation_values(
        cls,
        rotation_xyzw: Iterable[float],
        count: int,
    ) -> List[List[float]]:
        quat = cls._normalize_quat_xyzw(rotation_xyzw)
        return [list(quat) for _ in range(max(1, count))]

    @staticmethod
    def _three_floats(values: Iterable[float], default: Tuple[float, float, float]) -> List[float]:
        raw = list(values or [])
        padded = (raw + list(default))[:3]
        result = []
        for index, value in enumerate(padded):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = float(default[index])
            result.append(numeric if math.isfinite(numeric) else float(default[index]))
        return result

    @classmethod
    def _position_values_from_frames(
        cls,
        frames: List[dict],
        *,
        default_position: Tuple[float, float, float],
    ) -> List[List[float]]:
        default = (
            float(default_position[0]),
            float(default_position[1]),
            float(default_position[2]),
        )
        return [
            cls._three_floats(frame.get("location_xyz"), default)
            for frame in frames
        ]

    @staticmethod
    def _position_values_have_motion(values: List[List[float]], epsilon: float = 1e-5) -> bool:
        if len(values) < 2:
            return False
        first = np.asarray(values[0][:3], dtype=np.float64)
        for value in values[1:]:
            current = np.asarray(value[:3], dtype=np.float64)
            if float(np.linalg.norm(current - first)) > epsilon:
                return True
        return False

    @staticmethod
    def _is_root_or_pelvis_node(model: KotorModel, node_name: str) -> bool:
        key = str(node_name or "").lower()
        root = str(getattr(getattr(model, "root_node", None), "name", "") or "").lower()
        return key in {
            root,
            "root",
            "rootdummy",
            "pelvis",
            "pelvis_g",
        }

    def _capture_aurora_rest_bases(self, model: KotorModel) -> Dict[str, np.ndarray]:
        """Capture Aurora world-space rest rotation bases by node name."""

        registry = CoordinateNormalizer().normalize_aurora_bind(model, skeleton_id=getattr(model, "name", "aurora"))
        bases: Dict[str, np.ndarray] = {}
        for name in registry.bone_names:
            key = str(name or "").lower()
            bases[key] = quat_to_matrix_wxyz(registry.world_rotation(name))[:3, :3]
        return bases

    def _source_rest_basis_aurora(self, curve: dict, source_rest: Optional[dict]) -> np.ndarray:
        """Return the source rest basis converted into Aurora coordinate space."""

        basis_data = curve.get("source_rest_basis") or source_rest or {}
        raw_rotation = basis_data.get("rotation_wxyz")
        if raw_rotation is None and basis_data.get("world_matrix_at_rest"):
            raw_rotation = matrix_to_quat_wxyz(np.asarray(basis_data["world_matrix_at_rest"], dtype=np.float64))
        if raw_rotation is None and basis_data.get("matrix"):
            raw_rotation = matrix_to_quat_wxyz(np.asarray(basis_data["matrix"], dtype=np.float64))

        ue5_w, ue5_x, ue5_y, ue5_z = self._four_floats(raw_rotation, (1.0, 0.0, 0.0, 0.0))
        aurora_wxyz = aurora_from_ue5_quat((ue5_x, ue5_y, ue5_z, ue5_w)).to_wxyz()
        return quat_to_matrix_wxyz(aurora_wxyz)[:3, :3]

    def _basis_change_for_curve(
        self,
        *,
        curve: dict,
        target_node: ModelNode,
        source_rest: Optional[dict],
        aurora_rest_bases: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """Compute the per-bone source-to-target rest-basis bridge."""

        target_key = str(target_node.name or "").lower()
        aurora_basis = aurora_rest_bases.get(target_key)
        if aurora_basis is None:
            raise ValueError(f"Missing Aurora rest basis for target node '{target_node.name}'")
        source_basis = self._source_rest_basis_aurora(curve, source_rest)
        return compute_basis_change_matrix(source_basis, aurora_basis)

    def _motion_rotation_xyzw_from_ue5_world(
        self,
        frame: dict,
        target_node: ModelNode,
        source_rest: Optional[dict] = None,
        source_parent_rest: Optional[dict] = None,
        source_parent_frame: Optional[dict] = None,
        basis_change_matrix: Optional[np.ndarray] = None,
        source_reference_frame: Optional[dict] = None,
        source_parent_reference_frame: Optional[dict] = None,
    ) -> List[float]:
        """Convert source world-space bone motion into an Aurora local controller.

        The first R3.B implementation subtracted the animated source parent
        before building a local delta. That is mathematically tidy for matched
        skeletons, but it flattens authored UE motion when several source bones
        move together or when a longer UE chain is collapsed onto PMBAM. For
        KOTOR injection we need the mapped source bone's visible motion to
        survive as local Aurora controller motion, so this path transfers the
        source bone's world-space rotation delta onto the target bind-local
        rotation.
        """

        ue5_wxyz = frame.get("rotation_wxyz") or (1.0, 0.0, 0.0, 0.0)
        ue5_w, ue5_x, ue5_y, ue5_z = self._four_floats(ue5_wxyz, (1.0, 0.0, 0.0, 0.0))

        reference_wxyz: Tuple[float, float, float, float]
        if source_reference_frame and source_reference_frame.get("rotation_wxyz"):
            reference_wxyz = self._four_floats(
                source_reference_frame.get("rotation_wxyz"),
                (ue5_w, ue5_x, ue5_y, ue5_z),
            )
        elif source_rest and source_rest.get("rotation_wxyz"):
            reference_wxyz = self._four_floats(
                source_rest.get("rotation_wxyz"),
                (1.0, 0.0, 0.0, 0.0),
            )
        else:
            return self._local_rotation_xyzw_from_ue5_world(
                frame,
                target_node,
                source_rest,
                source_parent_rest,
                source_parent_frame,
                basis_change_matrix,
                source_reference_frame,
                source_parent_reference_frame,
            )

        source_delta = quat_mul_wxyz(
            quat_inverse_wxyz(reference_wxyz),
            (ue5_w, ue5_x, ue5_y, ue5_z),
        )
        delta_w, delta_x, delta_y, delta_z = source_delta
        aurora_delta = aurora_from_ue5_quat((delta_x, delta_y, delta_z, delta_w)).to_wxyz()
        if basis_change_matrix is not None:
            aurora_delta = conjugate_quat_wxyz(aurora_delta, basis_change_matrix)
        bind_local = xyzw_to_wxyz(target_node.rotation)
        local_wxyz = quat_mul_wxyz(bind_local, aurora_delta)
        local_xyzw = wxyz_to_xyzw(local_wxyz)
        return [float(v) for v in local_xyzw]

    def _local_rotation_xyzw_from_ue5_world(
        self,
        frame: dict,
        target_node: ModelNode,
        source_rest: Optional[dict] = None,
        source_parent_rest: Optional[dict] = None,
        source_parent_frame: Optional[dict] = None,
        basis_change_matrix: Optional[np.ndarray] = None,
        source_reference_frame: Optional[dict] = None,
        source_parent_reference_frame: Optional[dict] = None,
    ) -> List[float]:
        ue5_wxyz = frame.get("rotation_wxyz") or (1.0, 0.0, 0.0, 0.0)
        ue5_w, ue5_x, ue5_y, ue5_z = self._four_floats(ue5_wxyz, (1.0, 0.0, 0.0, 0.0))

        if source_rest and source_rest.get("rotation_wxyz"):
            rest_w, rest_x, rest_y, rest_z = self._four_floats(
                source_rest.get("rotation_wxyz"),
                (1.0, 0.0, 0.0, 0.0),
            )
            source_anim = (ue5_w, ue5_x, ue5_y, ue5_z)
            source_rest_rot = (rest_w, rest_x, rest_y, rest_z)
            if source_reference_frame and source_reference_frame.get("rotation_wxyz"):
                source_rest_rot = self._four_floats(
                    source_reference_frame.get("rotation_wxyz"),
                    (rest_w, rest_x, rest_y, rest_z),
                )
            if (
                source_parent_frame
                and source_parent_frame.get("rotation_wxyz")
                and source_parent_rest
                and source_parent_rest.get("rotation_wxyz")
            ):
                parent_anim = self._four_floats(
                    source_parent_frame.get("rotation_wxyz"),
                    (1.0, 0.0, 0.0, 0.0),
                )
                parent_rest = self._four_floats(
                    source_parent_rest.get("rotation_wxyz"),
                    (1.0, 0.0, 0.0, 0.0),
                )
                if source_parent_reference_frame and source_parent_reference_frame.get("rotation_wxyz"):
                    parent_rest = self._four_floats(
                        source_parent_reference_frame.get("rotation_wxyz"),
                        (1.0, 0.0, 0.0, 0.0),
                    )
                source_anim = quat_mul_wxyz(quat_inverse_wxyz(parent_anim), source_anim)
                source_rest_rot = quat_mul_wxyz(quat_inverse_wxyz(parent_rest), source_rest_rot)
            source_delta = quat_mul_wxyz(
                quat_inverse_wxyz(source_rest_rot),
                source_anim,
            )
            delta_w, delta_x, delta_y, delta_z = source_delta
            aurora_delta = aurora_from_ue5_quat((delta_x, delta_y, delta_z, delta_w)).to_wxyz()
            if basis_change_matrix is not None:
                aurora_delta = conjugate_quat_wxyz(aurora_delta, basis_change_matrix)
            bind_local = xyzw_to_wxyz(target_node.rotation)
            local_wxyz = quat_mul_wxyz(bind_local, aurora_delta)
        else:
            aurora_world = aurora_from_ue5_quat((ue5_x, ue5_y, ue5_z, ue5_w)).to_wxyz()
            parent = getattr(target_node, "parent", None)
            if parent is not None:
                parent_world_xyzw = parent.world_transform()[1]
                parent_world_wxyz = xyzw_to_wxyz(parent_world_xyzw)
                local_wxyz = quat_mul_wxyz(quat_inverse_wxyz(parent_world_wxyz), aurora_world)
            else:
                local_wxyz = normalize_quat_wxyz(aurora_world)
        local_xyzw = wxyz_to_xyzw(local_wxyz)
        return [float(v) for v in local_xyzw]

    @staticmethod
    def _four_floats(values: Iterable[float], default: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        raw = list(values or default)
        raw = (raw + list(default))[:4]
        return tuple(float(value) for value in raw)  # type: ignore[return-value]

    @staticmethod
    def _validate_controller_rows(name: str, times: List[float], values: List[List[float]], columns: int) -> None:
        if len(times) != len(values):
            raise ValueError(f"{name}: controller times/values row mismatch")
        for time_value in times:
            if not math.isfinite(time_value):
                raise ValueError(f"{name}: non-finite controller time")
        for row in values:
            if len(row) != columns:
                raise ValueError(f"{name}: controller row has {len(row)} columns, expected {columns}")
            if not all(math.isfinite(value) for value in row):
                raise ValueError(f"{name}: non-finite controller value")

    @staticmethod
    def _find_local_animation_index(model: KotorModel, slot_name: str) -> Optional[int]:
        wanted = str(slot_name or "").lower()
        for index, anim in enumerate(model.animations):
            if str(anim.name or "").lower() == wanted:
                return index
        return None
