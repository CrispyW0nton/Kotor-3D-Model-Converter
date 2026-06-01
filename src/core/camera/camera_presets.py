"""Lens, sensor, resolution, and framing presets."""

from __future__ import annotations

SENSOR_PRESETS: dict[str, tuple[float, float]] = {
    "16mm Film": (10.26, 7.49),
    "35mm Academy": (21.95, 16.00),
    "Super 35": (24.89, 18.66),
    "Full Frame 36x24": (36.00, 24.00),
    "IMAX Approx": (70.00, 48.50),
    "Digital Cinema": (27.03, 14.25),
}

LENS_PRESETS: dict[str, float] = {
    "18mm Wide": 18.0,
    "24mm Wide": 24.0,
    "35mm Standard": 35.0,
    "50mm Normal": 50.0,
    "85mm Portrait": 85.0,
    "135mm Telephoto": 135.0,
}

RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
    "2560x1440": (2560, 1440),
    "3840x2160": (3840, 2160),
}

LETTERBOX_PRESETS: dict[str, float] = {
    "16:9": 16.0 / 9.0,
    "4:3": 4.0 / 3.0,
    "1.85:1": 1.85,
    "2.35:1": 2.35,
    "2.39:1": 2.39,
    "2.76:1": 2.76,
}

FRAMING_PRESETS: dict[str, dict] = {
    "Clean View": {"show_safe_frame": False, "show_letterbox": False},
    "Safe Frame": {"show_safe_frame": True, "show_letterbox": False},
    "Letterboxed 2.35": {"show_safe_frame": True, "show_letterbox": True, "letterbox_ratio": 2.35},
    "Letterboxed 2.39": {"show_safe_frame": True, "show_letterbox": True, "letterbox_ratio": 2.39},
    "Rule of Thirds": {"show_safe_frame": True, "show_letterbox": False},
    "Director View": {"show_safe_frame": True, "show_letterbox": True, "letterbox_ratio": 2.39},
}
