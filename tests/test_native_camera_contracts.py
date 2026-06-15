from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.core.camera.camera_model import CAMERA_TYPES
from src.core.camera.camera_presets import LENS_PRESETS, SENSOR_PRESETS
from src.core.camera.camera_render_settings import RenderSettings
from src.core.camera.render_output import RenderOutput
from src.math.camera_math import focal_length_to_fov, fov_to_focal_length, normalize_quat


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Camera.dll"
PROJECT = ROOT / "native" / "GhostRigger.Domain.Core.Camera" / "GhostRigger.Domain.Core.Camera.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Domain.Core.Camera" / "GhostRigger.Domain.Core.Camera.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Domain.Core.Camera" / "Public" / "CameraContracts.h"
SOURCE = ROOT / "native" / "GhostRigger.Domain.Core.Camera" / "Private" / "CameraContracts.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_camera_capabilities_json.restype = ctypes.c_char_p
    lib.gr_camera_focal_length_to_fov.argtypes = [ctypes.c_double, ctypes.c_double]
    lib.gr_camera_focal_length_to_fov.restype = ctypes.c_double
    lib.gr_camera_fov_to_focal_length.argtypes = [ctypes.c_double, ctypes.c_double]
    lib.gr_camera_fov_to_focal_length.restype = ctypes.c_double
    lib.gr_camera_normalize_quat.argtypes = [
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.c_double,
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.gr_camera_normalize_quat.restype = None
    lib.gr_camera_normalize_type.argtypes = [ctypes.c_char_p]
    lib.gr_camera_normalize_type.restype = ctypes.c_char_p
    lib.gr_camera_normalize_render_format.argtypes = [ctypes.c_char_p]
    lib.gr_camera_normalize_render_format.restype = ctypes.c_char_p
    lib.gr_camera_render_output_extension.argtypes = [ctypes.c_char_p]
    lib.gr_camera_render_output_extension.restype = ctypes.c_char_p
    lib.gr_camera_validate_dimension.argtypes = [ctypes.c_int]
    lib.gr_camera_validate_dimension.restype = ctypes.c_int
    lib.gr_camera_validate_jpg_quality.argtypes = [ctypes.c_int]
    lib.gr_camera_validate_jpg_quality.restype = ctypes.c_int
    lib.gr_camera_sanitize_filename.argtypes = [ctypes.c_char_p]
    lib.gr_camera_sanitize_filename.restype = ctypes.c_char_p
    lib.gr_camera_sensor_preset_json.argtypes = [ctypes.c_char_p]
    lib.gr_camera_sensor_preset_json.restype = ctypes.c_char_p
    lib.gr_camera_lens_preset_mm.argtypes = [ctypes.c_char_p, ctypes.c_double]
    lib.gr_camera_lens_preset_mm.restype = ctypes.c_double
    lib.gr_camera_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _text(value: bytes) -> str:
    return value.decode("utf-8")


def test_camera_math_contracts_match_python() -> None:
    lib = _dll()

    for sensor, focal in [(36.0, 35.0), (10.26, 18.0), (0.0, -2.0), (70.0, 135.0)]:
        assert math.isclose(lib.gr_camera_focal_length_to_fov(sensor, focal), focal_length_to_fov(sensor, focal))

    for sensor, fov in [(36.0, 54.432), (10.26, 31.8), (0.0, -4.0), (70.0, 179.5)]:
        assert math.isclose(lib.gr_camera_fov_to_focal_length(sensor, fov), fov_to_focal_length(sensor, fov))

    for quat in [(0.0, 0.0, 0.0, 0.0), (2.0, -3.0, 4.0, 5.0), (float("inf"), 0.0, 0.0, 1.0)]:
        out = (ctypes.c_double * 4)()
        lib.gr_camera_normalize_quat(*quat, out)
        assert tuple(out) == normalize_quat(quat)


def test_camera_validation_and_render_contracts_match_python() -> None:
    lib = _dll()
    output = RenderOutput()

    for camera_type in [*CAMERA_TYPES, "Unsupported", ""]:
        expected = camera_type if camera_type in CAMERA_TYPES else "Cinematic Camera"
        assert _text(lib.gr_camera_normalize_type(_b(camera_type))) == expected

    for fmt in ["png", "jpg", "jpeg", "tga", "bmp", ""]:
        settings = RenderSettings(output_format=fmt, resolution_width=0, resolution_height=-4, jpg_quality=142)
        settings.validate()
        assert _text(lib.gr_camera_normalize_render_format(_b(fmt))) == settings.output_format
        expected_ext = "jpg" if settings.output_format.upper() in {"JPG", "JPEG"} else settings.output_format.lower()
        assert _text(lib.gr_camera_render_output_extension(_b(fmt))) == expected_ext

    assert lib.gr_camera_validate_dimension(0) == 1
    assert lib.gr_camera_validate_dimension(1920) == 1920
    assert lib.gr_camera_validate_jpg_quality(-10) == 1
    assert lib.gr_camera_validate_jpg_quality(142) == 100

    for name in ["Main Camera", "  weird//name??  ", "..hidden__", "", "module.room camera"]:
        assert _text(lib.gr_camera_sanitize_filename(_b(name))) == output.sanitize_filename(name)


def test_camera_presets_match_python_tables() -> None:
    lib = _dll()

    for name, (width, height) in SENSOR_PRESETS.items():
        row = json.loads(lib.gr_camera_sensor_preset_json(_b(name)).decode("utf-8"))
        assert row["name"] == name
        assert math.isclose(row["width_mm"], width)
        assert math.isclose(row["height_mm"], height)

    assert json.loads(lib.gr_camera_sensor_preset_json(b"missing").decode("utf-8")) == {
        "name": "",
        "width_mm": 36.0,
        "height_mm": 24.0,
    }

    for name, focal in LENS_PRESETS.items():
        assert math.isclose(lib.gr_camera_lens_preset_mm(_b(name), 1.0), focal)
    assert math.isclose(lib.gr_camera_lens_preset_mm(b"missing", 77.0), 77.0)


def test_camera_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\CameraContracts.cpp"' in project_text
    assert 'ClInclude Include="Public\\CameraContracts.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::domain::core::camera::core::camera::contracts" in source_text
    assert "namespace ghostrigger::domain::core::camera::core::camera::contracts" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_camera_capabilities_document_native_and_python_boundaries() -> None:
    lib = _dll()
    capabilities = json.loads(lib.gr_camera_capabilities_json().decode("utf-8"))
    schema = json.loads(lib.gr_camera_contracts_schema_json().decode("utf-8"))

    assert capabilities["camera_contracts_native"] is True
    assert capabilities["camera_runtime_python_fallback"] is True
    assert schema["schema"] == "camera_contracts_native.v1"
    assert "focal length/FOV conversion" in schema["native_scope"]
    assert "image save/encoding" in schema["python_fallback"]
