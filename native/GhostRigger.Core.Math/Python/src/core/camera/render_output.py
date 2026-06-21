"""Image output helpers for camera still rendering."""

from __future__ import annotations

import re
from pathlib import Path


class RenderOutput:
    def save_frame(self, image, path: str | Path, format: str, quality: int = 95) -> str:
        output = Path(path)
        self.ensure_output_directory(output.parent)
        fmt = str(format or output.suffix.lstrip(".") or "PNG").upper()
        if fmt == "JPG":
            fmt = "JPEG"
        save_kwargs = {}
        if fmt == "JPEG":
            save_kwargs["quality"] = max(1, min(100, int(quality)))
            if getattr(image, "mode", "") == "RGBA":
                image = image.convert("RGB")
        image.save(str(output), fmt, **save_kwargs)
        return str(output)

    def build_output_path(self, camera_name: str, settings, *, module_name: str = "scene", frame_number: int = 1) -> str:
        settings.validate()
        directory = Path(settings.output_directory)
        self.ensure_output_directory(directory)
        ext = "jpg" if settings.output_format.upper() in {"JPG", "JPEG"} else settings.output_format.lower()
        module = self.sanitize_filename(module_name or "scene")
        camera = self.sanitize_filename(camera_name or "Camera")
        prefix = self.sanitize_filename(settings.filename_prefix) if settings.filename_prefix else f"{module}_{camera}"
        number = max(1, int(frame_number))
        candidate = directory / f"{prefix}_{number:04d}.{ext}"
        if settings.overwrite_existing:
            return str(candidate)
        while candidate.exists():
            number += 1
            candidate = directory / f"{prefix}_{number:04d}.{ext}"
        return str(candidate)

    def sanitize_filename(self, name: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())
        clean = clean.strip("._")
        return clean or "render"

    def ensure_output_directory(self, path: str | Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
