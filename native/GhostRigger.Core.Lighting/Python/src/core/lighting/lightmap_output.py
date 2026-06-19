"""Image output helpers for generated lightmaps."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image


class LightmapOutput:
    def save_image(self, image: np.ndarray, path: str | Path, format: str) -> None:
        fmt = str(format or "png").lower().lstrip(".")
        pil_format = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "tga": "TGA"}.get(fmt, "PNG")
        arr = np.clip(image, 0.0, 1.0)
        data = (arr * 255.0 + 0.5).astype(np.uint8)
        Image.fromarray(data, "RGB").save(str(path), format=pil_format)

    def build_output_path(self, module_name: str, mesh_name: str, material_name: str, settings) -> Path:
        ext = "jpg" if settings.output_format == "jpeg" else settings.output_format
        pieces = [settings.filename_prefix, module_name, mesh_name]
        if material_name:
            pieces.append(material_name)
        pieces.extend(["LM", str(settings.resolution)])
        basename = "_".join(self.sanitize_filename(piece) for piece in pieces if piece)
        return Path(settings.output_directory or "exports/lightmaps") / f"{basename}.{ext}"

    def ensure_output_directory(self, path: str | Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, name: object) -> str:
        value = str(name or "unnamed").strip()
        value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]+", "_", value)
        value = re.sub(r"\s+", "_", value)
        return value.strip("._") or "unnamed"
