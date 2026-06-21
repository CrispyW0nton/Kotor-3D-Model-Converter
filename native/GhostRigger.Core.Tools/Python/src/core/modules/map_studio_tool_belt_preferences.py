"""Persistent Map Studio tool-belt preference contract.

The Level Editor owns buttons and dialogs; this module owns the KMAP-safe
preference shape for selected belt presets and custom action ordering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .map_studio_modeling_tools import (
    available_map_studio_tool_belt_actions,
    available_map_studio_tool_belt_presets,
)


MAP_STUDIO_TOOL_BELT_SECTION = "map_studio_tool_belt"


@dataclass(frozen=True)
class MapStudioToolBeltPreferences:
    """Portable authoring-workspace preferences stored in a KMAP extra section."""

    preset_key: str = "blockout"
    custom_action_keys: tuple[str, ...] = ()

    def to_kmap_section(self) -> dict[str, Any]:
        return {
            "preset_key": self.preset_key,
            "custom_action_keys": list(self.custom_action_keys),
        }


def _valid_preset_keys() -> set[str]:
    return {str(getattr(preset, "key", "") or "") for preset in available_map_studio_tool_belt_presets()}


def _valid_action_keys() -> set[str]:
    return {str(getattr(action, "key", "") or "") for action in available_map_studio_tool_belt_actions()}


def normalise_map_studio_tool_belt_preferences(
    value: Any = None,
    *,
    preset_key: str | None = None,
    custom_action_keys: tuple[str, ...] | list[str] | None = None,
) -> MapStudioToolBeltPreferences:
    """Return a validated preference object from a KMAP section or UI values."""

    source = dict(value or {}) if isinstance(value, dict) else {}
    raw_preset = str(preset_key if preset_key is not None else source.get("preset_key", "blockout") or "blockout").strip()
    valid_presets = _valid_preset_keys()
    selected_preset = raw_preset if raw_preset in valid_presets else "blockout"
    raw_keys = custom_action_keys if custom_action_keys is not None else source.get("custom_action_keys", ())
    valid_actions = _valid_action_keys()
    ordered_keys: list[str] = []
    for item in tuple(raw_keys or ()):
        key = str(item or "").strip()
        if key and key in valid_actions and key not in ordered_keys:
            ordered_keys.append(key)
    return MapStudioToolBeltPreferences(
        preset_key=selected_preset,
        custom_action_keys=tuple(ordered_keys),
    )


__all__ = [
    "MAP_STUDIO_TOOL_BELT_SECTION",
    "MapStudioToolBeltPreferences",
    "normalise_map_studio_tool_belt_preferences",
]
