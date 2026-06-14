"""Renderer-neutral color conversion helpers."""

from __future__ import annotations

import ctypes

from src.core.rendering._native import native_rendering


_Double3 = ctypes.c_double * 3


def _python_hex_to_rgb_float(value: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return (
            int(raw[0:2], 16) / 255.0,
            int(raw[2:4], 16) / 255.0,
            int(raw[4:6], 16) / 255.0,
        )
    except ValueError:
        return fallback


def _hex_to_rgb_float(value: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    dll = native_rendering()
    if dll is not None:
        try:
            native_fallback = _Double3(*fallback)
            out = _Double3()
            if dll.gr_rendering_hex_to_rgb_float(str(value or "").encode("utf-8"), native_fallback, out):
                return (out[0], out[1], out[2])
        except (OSError, TypeError, ValueError):
            pass
    return _python_hex_to_rgb_float(value, fallback)


__all__ = tuple(name for name in globals() if not name.startswith("__"))
