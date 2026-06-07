"""Small optional denoising pass for low-sample lightmap bakes."""

from __future__ import annotations

import numpy as np


class LightmapDenoiser:
    def denoise(self, image: np.ndarray, valid_mask: np.ndarray, strength: float = 0.0) -> np.ndarray:
        if strength <= 0.0:
            return image
        out = image.copy()
        padded = np.pad(image, ((1, 1), (1, 1), (0, 0)), mode="edge")
        for y, x in zip(*np.nonzero(valid_mask)):
            neighbourhood = padded[y:y + 3, x:x + 3]
            out[y, x] = image[y, x] * (1.0 - strength) + neighbourhood.mean(axis=(0, 1)) * strength
        return out
