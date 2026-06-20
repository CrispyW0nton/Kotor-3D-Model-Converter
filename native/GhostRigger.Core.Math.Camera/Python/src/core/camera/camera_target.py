"""Camera target handle records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CameraTarget:
    camera_id: str
    position: tuple[float, float, float]
    selected: bool = False
    locked: bool = False
