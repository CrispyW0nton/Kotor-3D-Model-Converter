"""Character Builder auto-fit report contract.

The Character Builder keeps the selected native KOTOR skeleton as the final
export DAG.  External FBX/OBJ meshes are only fitted into that space before the
native template rig is applied.  This report captures the evidence behind that
fit so UI and tests can distinguish confident landmark fits from fallback
bounds fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class AutoFitReport:
    """Structured evidence for one Character Builder external-mesh auto-fit."""

    source_forward_axis: str
    source_up_axis: str
    target_forward_axis: str
    target_up_axis: str
    scale_factor: float
    height_source: str
    ground_origin_basis: str
    used_landmarks: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    fallback_used: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for metadata and UI labels."""
        return {
            "source_forward_axis": str(self.source_forward_axis),
            "source_up_axis": str(self.source_up_axis),
            "target_forward_axis": str(self.target_forward_axis),
            "target_up_axis": str(self.target_up_axis),
            "scale_factor": float(self.scale_factor),
            "height_source": str(self.height_source),
            "ground_origin_basis": str(self.ground_origin_basis),
            "used_landmarks": list(self.used_landmarks),
            "confidence": float(self.confidence),
            "fallback_used": bool(self.fallback_used),
            "notes": str(self.notes),
        }


@dataclass(frozen=True)
class AutoFitOverride:
    """Optional modder-supplied axes/ground rules for deterministic re-fit."""

    source_forward_axis: str | None = None
    source_up_axis: str | None = None
    height_source: str = "auto"
    ground_origin_basis: str = "auto"

    def is_active(self) -> bool:
        """Return True when at least one override value should affect fitting."""
        return any(
            str(value or "").strip().lower() not in {"", "auto"}
            for value in (
                self.source_forward_axis,
                self.source_up_axis,
                self.height_source,
                self.ground_origin_basis,
            )
        )

    @classmethod
    def from_mapping(cls, data: Any) -> "AutoFitOverride":
        """Create an override from a UI/controller mapping."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            source_forward_axis=data.get("source_forward_axis"),
            source_up_axis=data.get("source_up_axis"),
            height_source=str(data.get("height_source") or "auto"),
            ground_origin_basis=str(data.get("ground_origin_basis") or "auto"),
        )


CharacterAutoFitReport = AutoFitReport


def summarize_auto_fit_quality(
    fit_report: Any,
    *,
    min_confidence: float = 0.60,
    min_paired_landmarks: int = 8,
    max_rms_error: float = 0.15,
    max_pair_error: float = 0.16,
    min_toe_forward_alignment: float = 0.50,
) -> dict[str, Any]:
    """Return a modder-facing quality summary for Character Builder Auto-Fit.

    This is intentionally UI-free.  The native KOTOR skeleton remains final DAG
    authority; this helper only explains whether the imported payload was
    positioned by trustworthy skeleton evidence or by a fallback fit.
    """

    fit = fit_report if isinstance(fit_report, dict) else {}
    if not fit:
        return {
            "stage": "missing",
            "summary": "Auto-fit evidence is missing.",
            "reasons": ["fit_report_missing"],
            "pair_count": 0,
            "rms_error": None,
            "max_error": None,
            "worst_pair_role": "",
            "source_landmark_domain": "not_recorded",
            "imported_skeleton_driven": False,
        }

    auto_fit = _mapping(fit.get("auto_fit_report"))
    fit_transform = _mapping(fit.get("fit_transform"))
    alignment = _mapping(fit_transform.get("landmark_alignment"))
    source_frame = _mapping(fit.get("source_frame"))
    target_frame = _mapping(fit.get("target_frame"))
    source_sources = _string_mapping(source_frame.get("landmark_sources"))
    source_domain, imported_skeleton_driven = _source_landmark_domain(source_sources)

    reasons: list[str] = []
    fallback_used = bool(
        fit.get("fallback_used", auto_fit.get("fallback_used", False))
    )
    policy = str(fit.get("fit_policy") or "").strip()
    confidence = _safe_float(fit.get("confidence", auto_fit.get("confidence")))
    pair_count = _safe_int(alignment.get("pair_count")) if alignment else 0
    rms_error = _safe_float(alignment.get("rms_error")) if alignment else None
    max_error = _safe_float(alignment.get("max_error")) if alignment else None
    worst_pair_role = str(alignment.get("worst_pair_role") or "")

    if fallback_used:
        reasons.append("fallback_fit_used")
    if policy and policy != "bone_landmark_basis":
        reasons.append(f"policy={policy}")
    if confidence is None:
        reasons.append("confidence_missing")
    elif confidence < float(min_confidence):
        reasons.append("confidence_low")
    if source_domain != "skeleton_landmarks":
        reasons.append(f"source_landmarks={source_domain}")
    if not imported_skeleton_driven:
        reasons.append("imported_skeleton_not_driving_source")
    if not alignment:
        reasons.append("paired_landmark_alignment_missing")
    else:
        if pair_count < int(min_paired_landmarks):
            reasons.append("too_few_paired_landmarks")
        if rms_error is None:
            reasons.append("rms_error_missing")
        elif rms_error > float(max_rms_error):
            reasons.append("rms_error_high")
        if max_error is None:
            reasons.append("max_error_missing")
        elif max_error > float(max_pair_error):
            reasons.append("max_error_high")

    toe_reasons = _toe_forward_quality_reasons(
        source_frame=source_frame,
        target_frame=target_frame,
        min_alignment=float(min_toe_forward_alignment),
    )
    reasons.extend(toe_reasons)

    if fallback_used:
        stage = "fallback"
    elif reasons:
        stage = "needs_review"
    else:
        stage = "passed"

    summary = _quality_summary_text(
        stage=stage,
        pair_count=pair_count,
        rms_error=rms_error,
        max_error=max_error,
        worst_pair_role=worst_pair_role,
        source_domain=source_domain,
    )
    return {
        "stage": stage,
        "summary": summary,
        "reasons": sorted(set(reasons)),
        "policy": policy,
        "confidence": confidence,
        "pair_count": int(pair_count),
        "rms_error": rms_error,
        "max_error": max_error,
        "worst_pair_role": worst_pair_role,
        "source_landmark_domain": source_domain,
        "imported_skeleton_driven": bool(imported_skeleton_driven),
        "source_toe_forward_alignment": _safe_float(
            source_frame.get("toe_forward_alignment")
        ),
        "target_toe_forward_alignment": _safe_float(
            target_frame.get("toe_forward_alignment")
        ),
        "thresholds": {
            "min_confidence": float(min_confidence),
            "min_paired_landmarks": int(min_paired_landmarks),
            "max_rms_error": float(max_rms_error),
            "max_pair_error": float(max_pair_error),
            "min_toe_forward_alignment": float(min_toe_forward_alignment),
        },
    }


def _quality_summary_text(
    *,
    stage: str,
    pair_count: int,
    rms_error: float | None,
    max_error: float | None,
    worst_pair_role: str,
    source_domain: str,
) -> str:
    if stage == "missing":
        return "Auto-fit evidence is missing."
    if stage == "fallback":
        return "Auto-fit used fallback bounds/origin evidence; review manually."
    metric = (
        f"{pair_count} skeleton pairs, "
        f"RMS {_fmt_float(rms_error)}, max {_fmt_float(max_error)}"
    )
    if worst_pair_role:
        metric += f", worst {worst_pair_role}"
    if stage == "passed":
        return f"Skeleton-driven Auto-Fit passed ({metric})."
    return (
        "Skeleton-driven Auto-Fit needs review "
        f"({metric}; source={source_domain})."
    )


def _toe_forward_quality_reasons(
    *,
    source_frame: dict[str, Any],
    target_frame: dict[str, Any],
    min_alignment: float,
) -> list[str]:
    reasons: list[str] = []
    for label, frame in (("source", source_frame), ("target", target_frame)):
        landmarks = _mapping(frame.get("landmarks"))
        has_toes = all(
            bool(landmarks.get(role))
            for role in ("left_foot", "right_foot", "left_toe", "right_toe")
        )
        alignment = _safe_float(frame.get("toe_forward_alignment"))
        if not has_toes:
            reasons.append(f"{label}_toe_landmarks_missing")
        elif alignment is None:
            reasons.append(f"{label}_toe_forward_missing")
        elif alignment < float(min_alignment):
            reasons.append(f"{label}_toe_forward_low")
    return reasons


def _source_landmark_domain(sources: dict[str, str]) -> tuple[str, bool]:
    if not sources:
        return "not_recorded", False
    skeleton_roles = [
        role for role, source in sources.items()
        if source in {"imported_skeleton", "skeleton_node"}
    ]
    mesh_roles = [
        role for role, source in sources.items()
        if source == "mesh_payload"
    ]
    imported_skeleton_driven = any(
        source == "imported_skeleton" for source in sources.values()
    )
    if skeleton_roles and not mesh_roles:
        return "skeleton_landmarks", imported_skeleton_driven
    if skeleton_roles and mesh_roles:
        return "mixed_skeleton_and_mesh_landmarks", imported_skeleton_driven
    if mesh_roles:
        return "mesh_payload_landmarks", imported_skeleton_driven
    return "non_mesh_landmarks", imported_skeleton_driven


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_mapping(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        str(key or ""): str(value or "")
        for key, value in raw.items()
        if str(key or "").strip()
    }


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if math.isfinite(out) else None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def _fmt_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


__all__ = [
    "AutoFitReport",
    "AutoFitOverride",
    "CharacterAutoFitReport",
    "summarize_auto_fit_quality",
]
