"""JSON manifest writer for generated lightmap bakes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class LightmapManifest:
    FILENAME = "lightmap_bake_manifest.json"

    def write(self, result, settings, lights, output_directory: str | Path) -> str:
        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / self.FILENAME
        data = {
            "module": result.module_name,
            "bake_date": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "resolution": result.resolution,
            "format": result.output_format,
            "settings": settings.to_summary(),
            "source_lights_used": [self._light_summary(light) for light in lights],
            "bakes": [
                {
                    "mesh": bake.mesh_name,
                    "material": bake.material_name,
                    "uv_channel": bake.uv_channel,
                    "output": bake.output_path,
                    "warnings": list(bake.warnings),
                    "errors": list(bake.errors),
                }
                for bake in result.bakes
            ],
            "warnings": list(result.warnings),
            "errors": list(result.errors),
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return str(path)

    def _light_summary(self, light: object) -> dict:
        return {
            "name": str(getattr(light, "name", "Light")),
            "type": str(getattr(light, "type", getattr(light, "light_kind", "point"))),
            "source_type": str(getattr(light, "source_type", "")),
            "enabled": bool(getattr(light, "enabled", getattr(light, "light_enabled", True))),
            "intensity": float(getattr(light, "intensity", getattr(light, "light_multiplier", 1.0)) or 0.0),
        }
