"""Diagnostic shader/material complexity scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShaderComplexitySettings:
    mode: str = "off"
    low_color: tuple[float, float, float] = (0.18, 0.45, 0.85)
    high_color: tuple[float, float, float] = (1.0, 0.45, 0.12)


class ShaderComplexity:
    def __init__(self) -> None:
        self.settings = ShaderComplexitySettings()

    def score_node(self, node: object, *, active_map_count: int = 0, affecting_lights: int = 0) -> float:
        score = 0.1
        score += max(0, active_map_count) * 0.12
        score += max(0, affecting_lights) * 0.05
        if bool(getattr(node, "txi_blending", 0)):
            score += 0.2
        raw_alpha = getattr(node, "alpha", None)
        if float(1.0 if raw_alpha is None else raw_alpha) < 1.0:
            score += 0.15
        return max(0.0, min(1.0, score))
