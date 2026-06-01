"""Viewport weight heat-map color helpers."""

from __future__ import annotations

from .dependencies import Tuple

# ── T405: Weight heat-map gradient ─────────────────────────────────────────
# Blue → green → red gradient identical to AccuRig's weight visualization.
# Matches the normalization convention from src/autorig/accurig.py: weights
# are already in [0, 1] (sum-to-one per vertex), so we use the raw value
# directly without re-normalization.
#
#   w == 0.00  →  blue   (0, 0, 255)   "no influence"
#   w == 0.50  →  green  (0, 255, 0)   "partial influence"
#   w == 1.00  →  red    (255, 0, 0)   "full influence"
#
# Two linear segments avoid a muddy yellow midpoint (matches AccuRig).
def _weight_to_heatmap_color(w: float) -> Tuple[int, int, int]:
    """Map a weight in [0, 1] to a (r, g, b) heat-map color."""
    w = max(0.0, min(1.0, float(w)))
    if w <= 0.5:
        # Blue → Green
        t = w * 2.0   # [0, 1]
        r = 0
        g = int(round(255 * t))
        b = int(round(255 * (1.0 - t)))
    else:
        # Green → Red
        t = (w - 0.5) * 2.0   # [0, 1]
        r = int(round(255 * t))
        g = int(round(255 * (1.0 - t)))
        b = 0
    return (r, g, b)

__all__ = tuple(name for name in globals() if not name.startswith("__"))
