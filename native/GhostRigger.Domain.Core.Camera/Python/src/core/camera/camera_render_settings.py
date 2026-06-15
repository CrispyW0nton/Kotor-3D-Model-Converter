"""Still-frame render settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RenderSettings:
    output_format: str = "PNG"
    output_directory: str = field(default_factory=lambda: str(Path("exports") / "renders"))
    filename_prefix: str = ""
    resolution_width: int = 1920
    resolution_height: int = 1080
    resolution_source: str = "camera"
    render_mode: str = "Cinematic Preview"
    include_letterbox: bool = True
    include_safe_frame: bool = False
    include_helpers: bool = False
    include_grid: bool = False
    include_camera_guides: bool = False
    transparent_background: bool = False
    jpg_quality: int = 95
    overwrite_existing: bool = False
    burn_letterbox_into_render: bool = True

    def validate(self) -> None:
        fmt = str(self.output_format or "PNG").upper()
        self.output_format = fmt if fmt in {"JPG", "JPEG", "PNG", "TGA"} else "PNG"
        self.resolution_width = max(1, int(self.resolution_width))
        self.resolution_height = max(1, int(self.resolution_height))
        self.jpg_quality = max(1, min(100, int(self.jpg_quality)))

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RenderSettings":
        allowed = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        settings = cls(**{key: value for key, value in dict(data or {}).items() if key in allowed})
        settings.validate()
        return settings
