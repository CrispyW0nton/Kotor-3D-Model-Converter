from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.sequence.sequence_interpolation import _ease, interpolate_values
from src.sequence.sequence_keyframe import InterpolationMode
from src.sequence.sequence_model import SequenceTime


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Domain.Core.Sequence.dll"
PROJECT = ROOT / "native" / "GhostRigger.Domain.Core.Sequence" / "GhostRigger.Domain.Core.Sequence.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Domain.Core.Sequence" / "GhostRigger.Domain.Core.Sequence.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Domain.Core.Sequence" / "Public" / "SequenceContracts.h"
SOURCE = ROOT / "native" / "GhostRigger.Domain.Core.Sequence" / "Private" / "SequenceContracts.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_sequence_interpolation_mode.argtypes = [ctypes.c_char_p]
    lib.gr_sequence_interpolation_mode.restype = ctypes.c_char_p
    lib.gr_sequence_ease.argtypes = [ctypes.c_double, ctypes.c_char_p]
    lib.gr_sequence_ease.restype = ctypes.c_double
    lib.gr_sequence_lerp_number.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    lib.gr_sequence_lerp_number.restype = ctypes.c_double
    lib.gr_sequence_interpolate_number.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_char_p]
    lib.gr_sequence_interpolate_number.restype = ctypes.c_double
    lib.gr_sequence_interpolate_bool.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_char_p]
    lib.gr_sequence_interpolate_bool.restype = ctypes.c_int
    lib.gr_sequence_clamp_frame.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.gr_sequence_clamp_frame.restype = ctypes.c_int
    lib.gr_sequence_frame_to_seconds.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
    lib.gr_sequence_frame_to_seconds.restype = ctypes.c_double
    lib.gr_sequence_seconds_to_frame.argtypes = [ctypes.c_double, ctypes.c_int, ctypes.c_int, ctypes.c_double]
    lib.gr_sequence_seconds_to_frame.restype = ctypes.c_int
    lib.gr_sequence_duration_frames.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.gr_sequence_duration_frames.restype = ctypes.c_int
    lib.gr_sequence_duration_seconds.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
    lib.gr_sequence_duration_seconds.restype = ctypes.c_double
    lib.gr_sequence_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def test_sequence_interpolation_contracts_match_python() -> None:
    lib = _dll()
    modes = [
        InterpolationMode.CONSTANT,
        InterpolationMode.LINEAR,
        InterpolationMode.EASE_IN,
        InterpolationMode.EASE_OUT,
        InterpolationMode.EASE_IN_OUT,
        InterpolationMode.CUBIC,
    ]

    assert lib.gr_sequence_interpolation_mode(b"Bogus").decode("utf-8") == InterpolationMode.LINEAR.value
    for mode in modes:
        for t in [-1.0, 0.0, 0.25, 0.75, 1.0, 2.0]:
            assert math.isclose(lib.gr_sequence_ease(t, _b(mode.value)), _ease(t, mode))
            assert math.isclose(
                lib.gr_sequence_interpolate_number(2.0, 10.0, t, _b(mode.value)),
                interpolate_values(2.0, 10.0, t, mode),
            )
            assert bool(lib.gr_sequence_interpolate_bool(0, 1, t, _b(mode.value))) == interpolate_values(
                False, True, t, mode
            )


def test_sequence_time_contracts_match_python() -> None:
    lib = _dll()
    sequence_time = SequenceTime(start_frame=10, end_frame=110, frame_rate=24.0, current_frame=10)

    for frame in [-50, 10, 42, 125]:
        assert lib.gr_sequence_clamp_frame(frame, 10, 110) == sequence_time.clamp_frame(frame)
        assert math.isclose(lib.gr_sequence_frame_to_seconds(frame, 10, 24.0), sequence_time.frame_to_seconds(frame))

    for seconds in [-1.0, 0.0, 1.25, 10.0]:
        assert lib.gr_sequence_seconds_to_frame(seconds, 10, 110, 24.0) == sequence_time.seconds_to_frame(seconds)

    assert lib.gr_sequence_duration_frames(10, 110) == sequence_time.get_duration_frames()
    assert math.isclose(lib.gr_sequence_duration_seconds(10, 110, 24.0), sequence_time.get_duration_seconds())


def test_sequence_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\SequenceContracts.cpp"' in project_text
    assert 'ClInclude Include="Public\\SequenceContracts.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::domain::core::sequence::core::sequence::contracts" in source_text
    assert "namespace ghostrigger::domain::core::sequence::core::sequence::contracts" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_sequence_contracts_document_native_and_python_boundaries() -> None:
    schema = json.loads(_dll().gr_sequence_contracts_schema_json().decode("utf-8"))

    assert schema["schema"] == "sequence_contracts_native.v1"
    assert "easing curves" in schema["native_scope"]
    assert "track mutation" in schema["python_fallback"]
