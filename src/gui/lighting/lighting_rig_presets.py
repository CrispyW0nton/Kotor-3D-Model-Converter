"""Generated preview lighting rigs."""

from __future__ import annotations

from .light_model import GhostRiggerLight


class LightingRigPresets:
    @staticmethod
    def create(preset: str) -> list[GhostRiggerLight]:
        key = str(preset or "none").lower()
        if key in {"none", "kotor_original"}:
            return []
        recipes = {
            "neutral_studio": [
                ("Studio Key", "area", (-4.0, -5.0, 6.0), (1.0, 0.95, 0.86), 3.0, 12.0, 5.0),
                ("Studio Fill", "point", (4.0, 3.0, 3.0), (0.62, 0.72, 1.0), 0.8, 10.0, 1.0),
                ("Studio Rim", "directional", (0.0, 5.0, 5.0), (0.85, 1.0, 0.9), 1.1, 8.0, 1.0),
            ],
            "cinematic_warm": [
                ("Warm Key", "spot", (-4.0, -4.5, 5.0), (1.0, 0.62, 0.32), 2.8, 12.0, 1.0),
                ("Low Fill", "point", (4.0, 2.0, 2.2), (0.35, 0.48, 0.72), 0.45, 8.0, 1.0),
                ("Amber Rim", "directional", (0.0, 4.0, 4.5), (1.0, 0.72, 0.38), 1.0, 10.0, 1.0),
            ],
            "cinematic_cold": [
                ("Cold Key", "spot", (-4.0, -4.5, 5.0), (0.52, 0.7, 1.0), 2.4, 12.0, 1.0),
                ("Soft Fill", "point", (3.5, 2.0, 2.0), (0.45, 0.52, 0.64), 0.35, 8.0, 1.0),
                ("Pale Rim", "directional", (0.0, 4.0, 4.5), (0.8, 0.95, 1.0), 1.0, 10.0, 1.0),
            ],
            "interior_torch": [
                ("Torch Left", "point", (-3.0, -2.0, 2.0), (1.0, 0.48, 0.16), 2.4, 5.5, 1.0),
                ("Torch Right", "point", (3.0, -2.0, 2.0), (1.0, 0.42, 0.12), 1.8, 5.0, 1.0),
                ("Warm Ambient", "ambient", (0.0, 0.0, 2.5), (0.5, 0.32, 0.18), 0.35, 1.0, 1.0),
            ],
            "exterior_moonlight": [
                ("Moon Direction", "directional", (-2.0, -4.0, 8.0), (0.55, 0.66, 1.0), 1.6, 20.0, 1.0),
                ("Sky Ambient", "ambient", (0.0, 0.0, 4.0), (0.18, 0.24, 0.42), 0.5, 1.0, 1.0),
                ("Ground Fill", "point", (3.0, 2.0, 1.0), (0.38, 0.44, 0.52), 0.25, 8.0, 1.0),
            ],
            "photoreal_softbox": [
                ("Softbox Main", "area", (-3.5, -4.0, 5.5), (1.0, 0.96, 0.9), 4.5, 14.0, 7.5),
                ("Soft Fill", "area", (4.0, 2.0, 3.5), (0.75, 0.82, 1.0), 0.9, 10.0, 4.0),
            ],
            "unreal_preview": [
                ("Preview Key", "directional", (-4.0, -4.0, 6.0), (1.0, 0.92, 0.82), 2.0, 18.0, 1.0),
                ("Preview Fill", "point", (3.0, 2.0, 3.0), (0.55, 0.65, 0.85), 0.7, 9.0, 1.0),
            ],
            "max_style_preview": [
                ("Preview Key", "spot", (-4.0, -5.0, 6.0), (1.0, 0.92, 0.8), 2.4, 12.0, 1.0),
                ("Preview Fill", "point", (4.0, 3.0, 3.0), (0.72, 0.8, 1.0), 0.8, 10.0, 1.0),
                ("Preview Back", "directional", (0.0, 4.0, 5.0), (0.92, 1.0, 0.9), 1.0, 10.0, 1.0),
            ],
        }
        return [
            GhostRiggerLight(
                name=name,
                source_type="GeneratedRig",
                type=kind,
                position=pos,
                color=color,
                intensity=intensity,
                radius=radius,
                area_size=area,
                metadata={"preview_generated": True, "preset": key},
            )
            for name, kind, pos, color, intensity, radius, area in recipes.get(key, [])
        ]
