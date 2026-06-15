"""Sidecar-style summaries for KMAX scene export workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneManifest:
    scene_id: str = ""
    scene_name: str = ""
    path: str = ""
    object_count: int = 0
    model_count: int = 0
    selected_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_name": self.scene_name,
            "path": self.path,
            "object_count": int(self.object_count),
            "model_count": int(self.model_count),
            "selected_count": int(self.selected_count),
            "metadata": dict(self.metadata),
        }
