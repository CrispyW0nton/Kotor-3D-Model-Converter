"""Deterministic panorama/HDR conversion for Map Studio skybox authoring.

KOTOR room models reference ordinary 8-bit textures; the retail engine does
not consume a modern HDR environment map directly.  This IO-owned adapter
therefore decodes an equirectangular image, samples five inward-facing KOTOR
box panels, and tone-maps linear HDR values into sRGB RGBA sidecar pixels.
The Scene layer remains responsible for turning the resulting texture resrefs
into authored skybox room geometry.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


SKYBOX_PANORAMA_FACE_ORDER = ("north", "east", "south", "west", "top")
_HDR_SUFFIXES = {".hdr", ".exr", ".pfm", ".pic", ".rgbe"}


@dataclass(frozen=True)
class PanoramaSkyboxOptions:
    """Authoring settings persisted beside generated skybox textures."""

    face_size: int = 1024
    exposure_ev: float = 0.0
    longitude_offset_degrees: float = 0.0
    tone_mapper: str = "aces"


@dataclass(frozen=True)
class PanoramaSkyboxFace:
    name: str
    width: int
    height: int
    rgba: bytes


@dataclass(frozen=True)
class PanoramaSkyboxConversion:
    source_path: str
    source_width: int
    source_height: int
    source_is_hdr: bool
    face_size: int
    exposure_ev: float
    longitude_offset_degrees: float
    tone_mapper: str
    faces: tuple[PanoramaSkyboxFace, ...]

    def face(self, name: str) -> PanoramaSkyboxFace:
        key = str(name or "").strip().lower()
        for item in self.faces:
            if item.name == key:
                return item
        raise KeyError(f"Unknown converted skybox face: {name!r}")


def _validate_options(options: PanoramaSkyboxOptions) -> PanoramaSkyboxOptions:
    size = int(options.face_size)
    if size < 16 or size > 4096:
        raise ValueError("Skybox face size must be between 16 and 4096 pixels.")
    # KOTOR textures are most predictable at power-of-two dimensions.
    if size & (size - 1):
        raise ValueError("Skybox face size must be a power of two for KOTOR export.")
    exposure = float(options.exposure_ev)
    longitude = float(options.longitude_offset_degrees)
    if not math.isfinite(exposure) or not -20.0 <= exposure <= 20.0:
        raise ValueError("Skybox exposure must be a finite value between -20 and +20 EV.")
    if not math.isfinite(longitude):
        raise ValueError("Skybox longitude offset must be finite.")
    mapper = str(options.tone_mapper or "aces").strip().lower()
    if mapper not in {"aces", "reinhard", "clip"}:
        raise ValueError("Skybox tone mapper must be ACES, Reinhard, or Clip.")
    return PanoramaSkyboxOptions(
        face_size=size,
        exposure_ev=exposure,
        longitude_offset_degrees=longitude,
        tone_mapper=mapper,
    )


def _srgb_to_linear(value: np.ndarray) -> np.ndarray:
    return np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return np.where(clipped <= 0.0031308, clipped * 12.92, 1.055 * clipped ** (1.0 / 2.4) - 0.055)


def _tone_map(value: np.ndarray, mode: str) -> np.ndarray:
    nonnegative = np.maximum(value, 0.0)
    if mode == "reinhard":
        return nonnegative / (1.0 + nonnegative)
    if mode == "clip":
        return np.clip(nonnegative, 0.0, 1.0)
    # Narkowicz' inexpensive ACES filmic fit.  Conversion stays explicit and
    # deterministic; no display/ICC state leaks into project textures.
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((nonnegative * (a * nonnegative + b)) / (nonnegative * (c * nonnegative + d) + e), 0.0, 1.0)


def _normalise_panorama_pixels(pixels: Any, *, source_is_hdr: bool) -> np.ndarray:
    image = np.asarray(pixels)
    if image.ndim == 2:
        image = np.repeat(image[:, :, None], 3, axis=2)
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("Panorama image must contain at least three RGB channels.")
    rgb = image[:, :, :3]
    if rgb.shape[0] < 2 or rgb.shape[1] < 4:
        raise ValueError("Panorama image is too small to project into a skybox.")
    if np.issubdtype(rgb.dtype, np.integer):
        scale = float(np.iinfo(rgb.dtype).max)
        rgb_float = rgb.astype(np.float32) / scale
        return _srgb_to_linear(rgb_float)
    rgb_float = np.nan_to_num(rgb.astype(np.float32), nan=0.0, posinf=65504.0, neginf=0.0)
    if source_is_hdr:
        return np.maximum(rgb_float, 0.0)
    # Float LDR decoders conventionally return sRGB samples in 0..1.
    return _srgb_to_linear(np.clip(rgb_float, 0.0, 1.0))


def _face_directions(name: str, size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Output rows are top-down while KOTOR panel UVs are bottom-up.  The
    # resulting direction at the top row therefore has positive KOTOR Z.
    horizontal = ((np.arange(size, dtype=np.float32) + 0.5) / float(size)) * 2.0 - 1.0
    vertical = 1.0 - ((np.arange(size, dtype=np.float32) + 0.5) / float(size)) * 2.0
    sx, sz = np.meshgrid(horizontal, vertical)
    ones = np.ones_like(sx)
    if name == "north":
        return sx, ones, sz
    if name == "east":
        return ones, -sx, sz
    if name == "south":
        return -sx, -ones, sz
    if name == "west":
        return -ones, sx, sz
    if name == "top":
        # Matches authored_skybox.py's top-panel UV winding: +U is +Y and
        # +V is +X when the panel is viewed from inside the room.
        return sz, sx, ones
    raise KeyError(name)


def _sample_equirectangular(
    panorama: np.ndarray,
    *,
    face: str,
    size: int,
    longitude_offset_degrees: float,
) -> np.ndarray:
    dx, dy, dz = _face_directions(face, size)
    length = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy, dz = dx / length, dy / length, dz / length
    longitude = np.arctan2(dx, dy) + math.radians(float(longitude_offset_degrees))
    latitude = np.arcsin(np.clip(dz, -1.0, 1.0))
    source_height, source_width = panorama.shape[:2]
    x = ((longitude / (2.0 * math.pi) + 0.5) * source_width - 0.5) % source_width
    y = np.clip((0.5 - latitude / math.pi) * source_height - 0.5, 0.0, source_height - 1.0)

    x0 = np.floor(x).astype(np.int64)
    x1 = (x0 + 1) % source_width
    y0 = np.floor(y).astype(np.int64)
    y1 = np.minimum(y0 + 1, source_height - 1)
    fx = (x - x0)[:, :, None]
    fy = (y - y0)[:, :, None]
    top = panorama[y0, x0] * (1.0 - fx) + panorama[y0, x1] * fx
    bottom = panorama[y1, x0] * (1.0 - fx) + panorama[y1, x1] * fx
    return top * (1.0 - fy) + bottom * fy


def convert_equirectangular_pixels(
    pixels: Any,
    *,
    options: PanoramaSkyboxOptions | None = None,
    source_is_hdr: bool = False,
    source_path: str = "",
) -> PanoramaSkyboxConversion:
    """Project decoded panorama pixels into five KOTOR-oriented RGBA faces."""

    settings = _validate_options(options or PanoramaSkyboxOptions())
    linear = _normalise_panorama_pixels(pixels, source_is_hdr=bool(source_is_hdr))
    output: list[PanoramaSkyboxFace] = []
    exposure_scale = float(2.0 ** settings.exposure_ev)
    for name in SKYBOX_PANORAMA_FACE_ORDER:
        sampled = _sample_equirectangular(
            linear,
            face=name,
            size=settings.face_size,
            longitude_offset_degrees=settings.longitude_offset_degrees,
        )
        display_linear = _tone_map(sampled * exposure_scale, settings.tone_mapper)
        srgb = _linear_to_srgb(display_linear)
        rgba = np.empty((settings.face_size, settings.face_size, 4), dtype=np.uint8)
        rgba[:, :, :3] = np.rint(srgb * 255.0).astype(np.uint8)
        rgba[:, :, 3] = 255
        output.append(
            PanoramaSkyboxFace(
                name=name,
                width=settings.face_size,
                height=settings.face_size,
                rgba=rgba.tobytes(),
            )
        )
    return PanoramaSkyboxConversion(
        source_path=str(source_path or ""),
        source_width=int(linear.shape[1]),
        source_height=int(linear.shape[0]),
        source_is_hdr=bool(source_is_hdr),
        face_size=settings.face_size,
        exposure_ev=settings.exposure_ev,
        longitude_offset_degrees=settings.longitude_offset_degrees,
        tone_mapper=settings.tone_mapper,
        faces=tuple(output),
    )


def load_and_convert_equirectangular_panorama(
    source_path: str | Path,
    *,
    options: PanoramaSkyboxOptions | None = None,
) -> PanoramaSkyboxConversion:
    """Decode PNG/JPG/TIFF or Radiance HDR/EXR and project it offline."""

    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Skybox panorama does not exist: {source}")
    suffix = source.suffix.lower()
    source_is_hdr = suffix in _HDR_SUFFIXES
    if source_is_hdr:
        # imageio may silently route Radiance HDR through Pillow and return
        # uint8, destroying values above 1.0 before exposure/tone mapping.
        # OpenCV's ANYDEPTH path preserves Radiance/PFM/OpenEXR floats and is a
        # declared Ghost-Studio runtime dependency.  imageio remains a fallback
        # for formats a particular OpenCV build does not recognize, but an
        # integer fallback is rejected rather than mislabeled as HDR.
        os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
        pixels = None
        try:
            import cv2

            decoded = cv2.imread(
                str(source),
                cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH | cv2.IMREAD_ANYCOLOR,
            )
            if decoded is not None:
                decoded = np.asarray(decoded)
                if decoded.ndim == 3 and decoded.shape[2] >= 3:
                    decoded = decoded[:, :, :3][:, :, ::-1]
                pixels = decoded
        except Exception:
            pixels = None
        if pixels is None:
            import imageio.v3 as iio

            pixels = iio.imread(source)
        if not np.issubdtype(np.asarray(pixels).dtype, np.floating):
            raise RuntimeError(
                f"{source.name} was decoded as 8-bit data, so its HDR range would be lost. "
                "Install/enable the OpenCV HDR or OpenEXR codec before converting this panorama."
            )
    else:
        from PIL import Image

        with Image.open(source) as opened:
            pixels = np.asarray(opened.convert("RGB"))
    return convert_equirectangular_pixels(
        pixels,
        options=options,
        source_is_hdr=source_is_hdr,
        source_path=str(source),
    )


__all__ = [
    "PanoramaSkyboxConversion",
    "PanoramaSkyboxFace",
    "PanoramaSkyboxOptions",
    "SKYBOX_PANORAMA_FACE_ORDER",
    "convert_equirectangular_pixels",
    "load_and_convert_equirectangular_panorama",
]
