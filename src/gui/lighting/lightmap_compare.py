"""Preview comparison helpers for generated and original lightmaps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops


COMPARISON_MODES = ("New Bake Only", "Original Lightmap Only", "Side-by-Side", "Split View", "Difference View")


@dataclass
class LightmapComparison:
    image: Image.Image | None
    warning: str = ""


class LightmapCompare:
    missing_message = "No original lightmap texture found for this mesh."

    def load_original_lightmap(self, mesh: object, texture_cache: object | None = None) -> Image.Image | None:
        name = str(getattr(mesh, "lightmap", "") or getattr(mesh, "lightmap_texture", "") or "").strip()
        if not name:
            return None
        if texture_cache is not None:
            try:
                image = texture_cache.get(name)
                if image is not None:
                    return image.convert("RGB")
            except Exception:
                pass
        path = Path(name)
        if path.is_file():
            try:
                return Image.open(path).convert("RGB")
            except Exception:
                return None
        return None

    def compare(self, new_image: Image.Image, original: Image.Image | None, mode: str) -> LightmapComparison:
        mode = mode if mode in COMPARISON_MODES else "New Bake Only"
        new_rgb = new_image.convert("RGB")
        if mode == "New Bake Only":
            return LightmapComparison(new_rgb)
        if original is None:
            return LightmapComparison(new_rgb, self.missing_message)
        old_rgb = original.convert("RGB").resize(new_rgb.size)
        if mode == "Original Lightmap Only":
            return LightmapComparison(old_rgb)
        if mode == "Difference View":
            return LightmapComparison(ImageChops.difference(new_rgb, old_rgb))
        if mode == "Split View":
            out = new_rgb.copy()
            half = out.width // 2
            out.paste(old_rgb.crop((0, 0, half, out.height)), (0, 0))
            return LightmapComparison(out)
        out = Image.new("RGB", (new_rgb.width * 2, new_rgb.height))
        out.paste(old_rgb, (0, 0))
        out.paste(new_rgb, (new_rgb.width, 0))
        return LightmapComparison(out)
