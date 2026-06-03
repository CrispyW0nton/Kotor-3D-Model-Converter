"""Character Builder auto-fit report contract.

The Character Builder keeps the selected native KOTOR skeleton as the final
export DAG.  External FBX/OBJ meshes are only fitted into that space before the
native template rig is applied.  This report captures the evidence behind that
fit so UI and tests can distinguish confident landmark fits from fallback
bounds fits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


__all__ = ["AutoFitReport", "AutoFitOverride", "CharacterAutoFitReport"]
