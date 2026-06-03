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


CharacterAutoFitReport = AutoFitReport


__all__ = ["AutoFitReport", "CharacterAutoFitReport"]
