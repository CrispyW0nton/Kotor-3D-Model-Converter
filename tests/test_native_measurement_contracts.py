from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.measurement.angle_snap import AngleSnap
from src.measurement.measurement_formatter import MeasurementFormatter
from src.measurement.percent_snap import PercentSnap
from src.measurement.unit_system import UnitSystem, normalize_unit


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Measurement.dll"
PROJECT = ROOT / "native" / "GhostRigger.Domain.Core.Measurement" / "GhostRigger.Domain.Core.Measurement.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Domain.Core.Measurement" / "GhostRigger.Domain.Core.Measurement.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Domain.Core.Measurement" / "Public" / "MeasurementContracts.h"
SOURCE = ROOT / "native" / "GhostRigger.Domain.Core.Measurement" / "Private" / "MeasurementContracts.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_measurement_normalize_unit.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.gr_measurement_normalize_unit.restype = ctypes.c_char_p
    lib.gr_measurement_unit_symbol.argtypes = [ctypes.c_char_p]
    lib.gr_measurement_unit_symbol.restype = ctypes.c_char_p
    lib.gr_measurement_convert_distance.argtypes = [ctypes.c_double, ctypes.c_char_p, ctypes.c_char_p]
    lib.gr_measurement_convert_distance.restype = ctypes.c_double
    lib.gr_measurement_format_distance.argtypes = [ctypes.c_double, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    lib.gr_measurement_format_distance.restype = ctypes.c_char_p
    lib.gr_measurement_parse_distance.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.gr_measurement_parse_distance.restype = ctypes.c_int
    lib.gr_measurement_format_angle_degrees.argtypes = [ctypes.c_double, ctypes.c_int]
    lib.gr_measurement_format_angle_degrees.restype = ctypes.c_char_p
    lib.gr_measurement_format_scale.argtypes = [ctypes.c_double]
    lib.gr_measurement_format_scale.restype = ctypes.c_char_p
    lib.gr_measurement_snap_degrees.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double]
    lib.gr_measurement_snap_degrees.restype = ctypes.c_double
    lib.gr_measurement_snap_radians.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double]
    lib.gr_measurement_snap_radians.restype = ctypes.c_double
    lib.gr_measurement_snap_percent.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double]
    lib.gr_measurement_snap_percent.restype = ctypes.c_double
    lib.gr_measurement_snap_scale_factor.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double]
    lib.gr_measurement_snap_scale_factor.restype = ctypes.c_double
    lib.gr_measurement_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _parse(lib: ctypes.CDLL, text: str, system_unit: str, display_unit: str) -> float:
    out = ctypes.c_double()
    ok = lib.gr_measurement_parse_distance(_b(text), _b(system_unit), _b(display_unit), ctypes.byref(out))
    assert ok == 1
    return out.value


def test_measurement_unit_conversion_and_formatting_match_python() -> None:
    lib = _dll()
    units = ["mm", "centimeters", "metre", "km", "inch", "ft", "yards", "bogus"]

    for unit in units:
        assert lib.gr_measurement_normalize_unit(_b(unit), b"centimetres").decode("utf-8") == normalize_unit(unit)

    for system_unit, display_unit, value, precision in [
        ("centimetres", "metres", 123.456, 3),
        ("metres", "centimetres", 1.25, 2),
        ("feet", "inches", 2.5, 1),
        ("yards", "feet", -0.0001, 3),
        ("millimetres", "centimetres", 125.0, 0),
    ]:
        py_units = UnitSystem(system_unit, display_unit)
        assert math.isclose(
            lib.gr_measurement_convert_distance(value, _b(system_unit), _b(display_unit)),
            py_units.convert(value, system_unit, display_unit),
        )
        assert (
            lib.gr_measurement_format_distance(value, _b(system_unit), _b(display_unit), precision).decode("utf-8")
            == py_units.format_distance(value, precision)
        )


def test_measurement_parse_and_formatter_helpers_match_python() -> None:
    lib = _dll()
    unit_system = UnitSystem("centimetres", "metres")
    formatter = MeasurementFormatter(unit_system, 3)

    for text in ["1.25 m", "10 cm", "-2.5ft", "3.5"]:
        assert math.isclose(_parse(lib, text, "centimetres", "metres"), unit_system.parse_distance(text))

    out = ctypes.c_double()
    assert lib.gr_measurement_parse_distance(b"wat", b"centimetres", b"metres", ctypes.byref(out)) == 0

    for angle, precision in [(12.345, 2), (-7.5, 0), (2.5, 4)]:
        assert lib.gr_measurement_format_angle_degrees(angle, precision).decode("utf-8") == formatter.angle_degrees(
            angle, precision
        )

    for scale in [1.0, 1.2345, 0.001, float("inf")]:
        assert lib.gr_measurement_format_scale(scale).decode("utf-8") == formatter.scale(scale)


def test_measurement_snap_contracts_match_python() -> None:
    lib = _dll()
    angle_snap = AngleSnap(True, 15.0)
    percent_snap = PercentSnap(True, 10.0)

    for angle in [-31.0, -7.0, 0.0, 14.0, 31.0]:
        assert math.isclose(lib.gr_measurement_snap_degrees(1, angle, 15.0), angle_snap.snap_degrees(angle))
        assert math.isclose(lib.gr_measurement_snap_radians(1, math.radians(angle), 15.0), angle_snap.snap_radians(math.radians(angle)))
        assert math.isclose(lib.gr_measurement_snap_degrees(0, angle, 15.0), angle)

    for value in [-12.0, 0.0, 14.0, 26.0]:
        assert math.isclose(lib.gr_measurement_snap_percent(1, value, 10.0), percent_snap.snap_percent(value))
        assert math.isclose(lib.gr_measurement_snap_percent(0, value, 10.0), value)

    for scale in [-2.0, 0.0001, 1.11, 1.26]:
        assert math.isclose(lib.gr_measurement_snap_scale_factor(1, scale, 10.0), percent_snap.snap_scale_factor(scale))
        assert math.isclose(lib.gr_measurement_snap_scale_factor(0, scale, 10.0), max(0.001, scale))


def test_measurement_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\MeasurementContracts.cpp"' in project_text
    assert 'ClInclude Include="Public\\MeasurementContracts.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::domain::core::measurement::core::measurement::contracts" in source_text
    assert "namespace ghostrigger::domain::core::measurement::core::measurement::contracts" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_measurement_contracts_document_native_and_python_boundaries() -> None:
    schema = json.loads(_dll().gr_measurement_contracts_schema_json().decode("utf-8"))

    assert schema["schema"] == "measurement_contracts_native.v1"
    assert "distance conversion" in schema["native_scope"]
    assert "measurement overlay drawing" in schema["python_fallback"]
