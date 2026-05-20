"""Direct lighting solver for generated lightmap bakes."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np


class LightmapLightingSolver:
    def solve_buffer(self, buffer, lights: Iterable[object], settings, shadow_solver=None) -> np.ndarray:
        output = np.zeros_like(buffer.baked_rgb, dtype=np.float32)
        ys, xs = np.nonzero(buffer.valid_mask)
        active_lights = [light for light in lights if self._include_light(light, settings)]
        for y, x in zip(ys, xs):
            texel = {
                "position": buffer.world_positions[y, x],
                "normal": buffer.world_normals[y, x],
                "diffuse": buffer.base_diffuse[y, x],
                "mesh_id": int(buffer.mesh_ids[y, x]),
            }
            rgb = self.solve_texel_lighting(texel, active_lights, settings, shadow_solver)
            output[y, x] = rgb
        return output

    def solve_texel_lighting(self, texel, lights, settings, shadow_solver=None) -> np.ndarray:
        rgb = np.zeros(3, dtype=np.float32)
        if settings.include_ambient:
            rgb += self.solve_ambient(texel, settings)
        if settings.use_direct_lighting:
            for light in lights:
                contribution = self.solve_direct_light(texel, light, settings)
                if shadow_solver is not None and settings.use_shadows:
                    contribution *= float(shadow_solver.calculate_shadow_factor(texel, light, settings))
                rgb += contribution
        if settings.use_indirect_approximation:
            rgb += 0.08 * np.asarray(texel["diffuse"], dtype=np.float32)
        if settings.include_diffuse:
            rgb *= np.asarray(texel["diffuse"], dtype=np.float32)
        return self.apply_exposure_gamma(rgb, settings)

    def solve_direct_light(self, texel, light, settings) -> np.ndarray:
        kind = str(getattr(light, "type", getattr(light, "light_kind", "point")) or "point").lower()
        if "ambient" in kind or bool(getattr(light, "ambient_only", False)):
            return self.solve_ambient(texel, settings, light)
        if "spot" in kind:
            return self.solve_spot_light(texel, light, settings)
        if "directional" in kind:
            return self.solve_directional_light(texel, light, settings)
        if "area" in kind:
            return self.solve_area_light_approx(texel, light, settings)
        return self.solve_point_light(texel, light, settings)

    def solve_point_light(self, texel, light, settings) -> np.ndarray:
        position = np.asarray(texel["position"], dtype=np.float32)
        normal = _normalized(np.asarray(texel["normal"], dtype=np.float32))
        light_pos = np.asarray(getattr(light, "position", (0.0, 0.0, 0.0)), dtype=np.float32)
        vec = light_pos - position
        dist = max(float(np.linalg.norm(vec)), 1.0e-5)
        radius = max(float(getattr(light, "radius", getattr(light, "light_radius", 5.0)) or 5.0), 0.001)
        if dist > radius:
            return np.zeros(3, dtype=np.float32)
        ldir = vec / dist
        ndotl = max(float(np.dot(normal, ldir)), 0.0)
        if ndotl <= 0.0:
            return np.zeros(3, dtype=np.float32)
        # Bake-friendly falloff. The previous inverse-square * radius term
        # clipped most Aurora-heavy module bakes to white. Generated lightmaps
        # need preserved gradients more than photometric brightness, so use a
        # smooth radius falloff and leave final compression to tone mapping.
        falloff = max(0.0, 1.0 - (dist / radius))
        attenuation = falloff * falloff
        return _light_color(light) * _intensity(light) * ndotl * attenuation * 0.45

    def solve_spot_light(self, texel, light, settings) -> np.ndarray:
        base = self.solve_point_light(texel, light, settings)
        if not np.any(base):
            return base
        position = np.asarray(texel["position"], dtype=np.float32)
        light_pos = np.asarray(getattr(light, "position", (0.0, 0.0, 0.0)), dtype=np.float32)
        to_texel = _normalized(position - light_pos)
        direction = _normalized(np.asarray(getattr(light, "direction", (0.0, -1.0, -1.0)), dtype=np.float32))
        cone = math.radians(max(1.0, min(179.0, float(getattr(light, "cone_angle", 45.0)))))
        inner = math.cos(cone * 0.5)
        outer = math.cos(cone * 0.65)
        dot_val = float(np.dot(direction, to_texel))
        if dot_val <= outer:
            return np.zeros(3, dtype=np.float32)
        spot = 1.0 if dot_val >= inner else (dot_val - outer) / max(inner - outer, 1.0e-5)
        return base * spot

    def solve_directional_light(self, texel, light, settings) -> np.ndarray:
        normal = _normalized(np.asarray(texel["normal"], dtype=np.float32))
        direction = _normalized(-np.asarray(getattr(light, "direction", (0.0, -1.0, -1.0)), dtype=np.float32))
        ndotl = max(float(np.dot(normal, direction)), 0.0)
        return _light_color(light) * _intensity(light) * ndotl

    def solve_area_light_approx(self, texel, light, settings) -> np.ndarray:
        result = self.solve_point_light(texel, light, settings)
        size = max(0.0, float(getattr(light, "area_size", 0.0) or 0.0))
        return result * (0.75 + min(size, 10.0) * 0.025)

    def solve_ambient(self, texel, settings, light: object | None = None) -> np.ndarray:
        if light is not None:
            return _light_color(light) * _intensity(light) * 0.25
        return np.asarray(getattr(settings, "background_color", (0.0, 0.0, 0.0)), dtype=np.float32) + np.asarray((0.035, 0.035, 0.035), dtype=np.float32)

    def apply_exposure_gamma(self, rgb, settings) -> np.ndarray:
        value = np.asarray(rgb, dtype=np.float32) * float(settings.exposure)
        # Reinhard tone mapping keeps intense multi-light rooms from becoming
        # flat white while still allowing bright highlights to read as bright.
        value = value / (1.0 + np.maximum(value, 0.0))
        if settings.clamp_output:
            value = np.clip(value, 0.0, 1.0)
        gamma = max(float(settings.gamma), 1.0e-5)
        return np.power(np.clip(value, 0.0, None), 1.0 / gamma)

    def sample_normal_map(self, material, uv):
        return None

    def build_tangent_basis(self, mesh, triangle_index):
        return None

    def tangent_to_world(self, normal_ts, tangent, bitangent, normal):
        return normal

    def _include_light(self, light: object, settings) -> bool:
        if bool(getattr(light, "deleted", False)):
            return False
        if not settings.include_disabled_lights and not bool(getattr(light, "enabled", getattr(light, "light_enabled", True))):
            return False
        if not bool(getattr(light, "visible", not bool(getattr(light, "_gr_light_hidden", False)))):
            return False
        source = str(getattr(light, "source_type", "") or "").lower()
        kind = str(getattr(light, "type", getattr(light, "light_kind", "")) or "").lower()
        if source == "aurora" or kind.startswith("aurora_"):
            return bool(settings.include_aurora_lights)
        if source == "generatedrig":
            return bool(settings.include_generated_rig_lights)
        return bool(settings.include_dynamic_lights)


def _light_color(light: object) -> np.ndarray:
    value = getattr(light, "color", getattr(light, "light_color", (1.0, 1.0, 1.0)))
    try:
        return np.asarray((float(value[0]), float(value[1]), float(value[2])), dtype=np.float32)
    except Exception:
        return np.ones(3, dtype=np.float32)


def _intensity(light: object) -> float:
    return max(0.0, float(getattr(light, "intensity", getattr(light, "light_multiplier", 1.0)) or 0.0))


def _normalized(v: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(v))
    if length <= 1.0e-8:
        return np.asarray((0.0, 0.0, 1.0), dtype=np.float32)
    return v / length
