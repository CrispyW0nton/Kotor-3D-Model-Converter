"""3ds Max-style system/display unit conversion.

GhostRigger keeps scene data in the active *system unit*. Changing only the
display unit must never mutate positions, vertices, animation data, or exports.
Exporters consume system-unit scene values and should convert only at a format
boundary when a target format explicitly requires a different unit.
"""

from __future__ import annotations

import re


UNIT_TO_CENTIMETERS: dict[str, float] = {
    "millimetres": 0.1,
    "millimeters": 0.1,
    "millimeter": 0.1,
    "millimetre": 0.1,
    "mm": 0.1,
    "centimetres": 1.0,
    "centimeters": 1.0,
    "centimeter": 1.0,
    "centimetre": 1.0,
    "cm": 1.0,
    "metres": 100.0,
    "meters": 100.0,
    "meter": 100.0,
    "metre": 100.0,
    "m": 100.0,
    "kilometres": 100000.0,
    "kilometers": 100000.0,
    "kilometer": 100000.0,
    "kilometre": 100000.0,
    "km": 100000.0,
    "inches": 2.54,
    "inch": 2.54,
    "in": 2.54,
    "feet": 30.48,
    "foot": 30.48,
    "ft": 30.48,
    "yards": 91.44,
    "yard": 91.44,
    "yd": 91.44,
}

CANONICAL_UNITS: tuple[str, ...] = (
    "millimetres",
    "centimetres",
    "metres",
    "kilometres",
    "inches",
    "feet",
    "yards",
)

UNIT_SYMBOLS: dict[str, str] = {
    "millimetres": "mm",
    "centimetres": "cm",
    "metres": "m",
    "kilometres": "km",
    "inches": "in",
    "feet": "ft",
    "yards": "yd",
}

_SYMBOL_TO_CANONICAL = {symbol: unit for unit, symbol in UNIT_SYMBOLS.items()}
_NAME_ALIASES = {
    "millimeters": "millimetres",
    "millimeter": "millimetres",
    "millimetre": "millimetres",
    "mm": "millimetres",
    "centimeters": "centimetres",
    "centimeter": "centimetres",
    "centimetre": "centimetres",
    "cm": "centimetres",
    "meters": "metres",
    "meter": "metres",
    "metre": "metres",
    "m": "metres",
    "kilometers": "kilometres",
    "kilometer": "kilometres",
    "kilometre": "kilometres",
    "km": "kilometres",
    "inch": "inches",
    "in": "inches",
    "foot": "feet",
    "ft": "feet",
    "yard": "yards",
    "yd": "yards",
}
_DISTANCE_RE = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-z]+)?\s*$"
)


def normalize_unit(unit_name: str, fallback: str = "centimetres") -> str:
    key = str(unit_name or "").strip().lower()
    if key in CANONICAL_UNITS:
        return key
    if key in _NAME_ALIASES:
        return _NAME_ALIASES[key]
    return fallback


class UnitSystem:
    """Convert and format distances between internal and display units."""

    def __init__(self, system_unit: str = "centimetres", display_unit: str = "centimetres"):
        self.system_unit = normalize_unit(system_unit)
        self.display_unit = normalize_unit(display_unit, fallback=self.system_unit)

    def set_system_unit(self, unit_name: str, rescale_scene: bool = False) -> None:
        """Set the internal scene unit.

        ``rescale_scene`` is accepted to match the UI contract. Actual scene
        rescaling is deliberately owned by higher-level scene controllers so a
        display/settings change cannot silently rewrite model data.
        """
        self.system_unit = normalize_unit(unit_name, fallback=self.system_unit)
        _ = bool(rescale_scene)

    def set_display_unit(self, unit_name: str) -> None:
        self.display_unit = normalize_unit(unit_name, fallback=self.display_unit)

    def to_display_units(self, value_in_system_units: float) -> float:
        return self.convert(float(value_in_system_units), self.system_unit, self.display_unit)

    def to_system_units(self, value_in_display_units: float) -> float:
        return self.convert(float(value_in_display_units), self.display_unit, self.system_unit)

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        src = normalize_unit(from_unit)
        dst = normalize_unit(to_unit)
        value_cm = float(value) * UNIT_TO_CENTIMETERS[src]
        return value_cm / UNIT_TO_CENTIMETERS[dst]

    def format_distance(self, value_in_system_units: float, precision: int = 3) -> str:
        precision = max(0, min(int(precision), 6))
        value = self.to_display_units(float(value_in_system_units))
        symbol = UNIT_SYMBOLS.get(self.display_unit, self.display_unit)
        if precision == 0:
            text = str(int(round(value)))
        else:
            text = f"{value:.{precision}f}".rstrip("0").rstrip(".")
            if text == "-0":
                text = "0"
        return f"{text} {symbol}"

    def parse_distance(self, text: str) -> float:
        match = _DISTANCE_RE.match(str(text or ""))
        if not match:
            raise ValueError(f"Invalid distance: {text!r}")
        value = float(match.group(1))
        suffix = match.group(2)
        if suffix:
            unit = normalize_unit(suffix, fallback="")
            if not unit:
                raise ValueError(f"Invalid distance unit: {suffix!r}")
            return self.convert(value, unit, self.system_unit)
        return self.to_system_units(value)
