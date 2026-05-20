"""Conversion between Aurora MDL light nodes and editable GhostRigger lights."""

from __future__ import annotations

from typing import Any, Iterable

from .light_model import GhostRiggerLight


class AuroraLightAdapter:
    """Preserve source Aurora fields while exposing editable light records."""

    KNOWN_FIELDS = {
        "name",
        "position",
        "rotation",
        "light_kind",
        "light_enabled",
        "light_color",
        "light_radius",
        "light_multiplier",
        "light_cone_degrees",
        "light_area_size",
        "light_ambient_only",
        "light_shadow",
        "light_flare",
        "light_fading",
        "light_dynamic",
    }

    @staticmethod
    def is_aurora_light(record: object) -> bool:
        if bool(getattr(record, "is_light", False)):
            return True
        return str(getattr(record, "name", "") or "").lower().startswith("auroralight")

    def from_record(self, record: object) -> GhostRiggerLight:
        light = GhostRiggerLight.from_object(record, source_type="Aurora")
        light.source_type = "Aurora"
        if light.type in {"point", "spot", "directional", "area", "ambient"}:
            if bool(getattr(record, "light_ambient_only", False)):
                light.type = "aurora_ambient"
            elif light.type == "point":
                light.type = "aurora_point"
        else:
            light.type = "aurora_unknown"
        light.metadata.update(self._unsupported_fields(record))
        light.metadata.setdefault("aurora_name", light.name)
        light.apply_to_original()
        return light

    def from_model(self, model: object | None) -> list[GhostRiggerLight]:
        if model is None or not hasattr(model, "all_nodes"):
            return []
        result: list[GhostRiggerLight] = []
        for node in self._safe_nodes(model):
            if self.is_aurora_light(node):
                result.append(self.from_record(node))
        return result

    def _safe_nodes(self, model: object) -> Iterable[object]:
        try:
            return list(model.all_nodes())
        except Exception:
            return []

    def _unsupported_fields(self, record: object) -> dict[str, Any]:
        data: dict[str, Any] = {}
        raw = getattr(record, "__dict__", None)
        if not isinstance(raw, dict):
            return data
        for key, value in raw.items():
            if key in self.KNOWN_FIELDS or key.startswith("_gr_"):
                continue
            if key.startswith("light_"):
                data[key] = value
        return data
