"""Persistence for viewport lighting preferences."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class LightingSettings:
    scene_lighting_mode: str = "scene"
    diffuse_map: bool = True
    normal_map: bool = True
    environment_map: bool = True
    specular_map: bool = True
    lightmap_map: bool = True
    lightmap_intensity: float = 0.55
    lightmap_mode: str = "baked"
    shader_complexity_mode: str = "off"
    show_light_helpers: bool = True
    show_light_radius_volumes: bool = False
    selected_lighting_rig_preset: str = "none"
    light_table_visible_columns: list[str] = field(default_factory=lambda: [
        "enabled", "color", "name", "type", "radius", "intensity"
    ])
    last_selected_light: str = ""


class LightingSettingsStore:
    def __init__(self, path: str | Path = "config/lighting_settings.json") -> None:
        self.path = Path(path)

    def load(self) -> LightingSettings:
        if not self.path.exists():
            return LightingSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            settings = LightingSettings()
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            return settings
        except Exception:
            return LightingSettings()

    def save(self, settings: LightingSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), indent=2, sort_keys=True) + "\n", encoding="utf-8")
