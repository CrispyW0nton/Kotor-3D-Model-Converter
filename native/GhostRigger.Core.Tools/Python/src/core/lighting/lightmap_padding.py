"""Edge padding and dilation for generated lightmap textures."""

from __future__ import annotations

import numpy as np


class LightmapPadding:
    def dilate(self, image: np.ndarray, valid_mask: np.ndarray, passes: int) -> np.ndarray:
        out = image.copy()
        mask = valid_mask.copy()
        for _ in range(max(0, int(passes))):
            if mask.all():
                break
            new_out = out.copy()
            new_mask = mask.copy()
            ys, xs = np.nonzero(~mask)
            for y, x in zip(ys, xs):
                samples = []
                for ny in range(max(0, y - 1), min(mask.shape[0], y + 2)):
                    for nx in range(max(0, x - 1), min(mask.shape[1], x + 2)):
                        if mask[ny, nx]:
                            samples.append(out[ny, nx])
                if samples:
                    # Dilation copies nearby valid texels into empty edge pixels,
                    # preventing black seams when the lightmap is filtered/mipped.
                    new_out[y, x] = np.mean(samples, axis=0)
                    new_mask[y, x] = True
            out, mask = new_out, new_mask
        return out

    def pad_islands(self, image: np.ndarray, valid_mask: np.ndarray, padding_pixels: int) -> np.ndarray:
        return self.dilate(image, valid_mask, padding_pixels)
