"""Lightmap preview/customisation state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LightmapController:
    available: bool = False
    enabled: bool = True
    intensity: float = 0.55
    mode: str = "baked"
    warning: str = ""

    def inspect_model(self, model: object | None) -> None:
        self.available = False
        if model is None or not hasattr(model, "all_nodes"):
            self.warning = "No module model loaded."
            return
        try:
            self.available = any(bool(getattr(node, "lightmap", "")) for node in model.all_nodes())
        except Exception:
            self.available = False
        self.warning = "" if self.available else "No lightmap data detected for this model."

    def set_settings(self, intensity: float, mode: str) -> None:
        try:
            self.intensity = max(0.0, min(float(intensity), 4.0))
        except (TypeError, ValueError):
            self.intensity = 0.55
        mode_value = str(mode or "baked").lower()
        self.mode = mode_value if mode_value in {"disabled", "baked", "dynamic_preview", "hybrid", "debug"} else "baked"
        self.enabled = self.mode != "disabled"
