from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.templates.template_builder import get_anim_slots_for_version, get_bones_for_version
from src.core.templates.twoda import TwoDA, TwoDARow, _split_2da_line


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Templates.dll"
PROJECT = ROOT / "native" / "GhostRigger.Templates" / "GhostRigger.Templates.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Templates" / "GhostRigger.Templates.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Templates" / "Public" / "TemplateContracts.h"
SOURCE = ROOT / "native" / "GhostRigger.Templates" / "Private" / "TemplateContracts.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_templates_capabilities_json.restype = ctypes.c_char_p
    lib.gr_templates_normalize_game_version.argtypes = [ctypes.c_char_p]
    lib.gr_templates_normalize_game_version.restype = ctypes.c_char_p
    lib.gr_templates_humanoid_bone_count.argtypes = [ctypes.c_char_p]
    lib.gr_templates_humanoid_bone_count.restype = ctypes.c_int
    lib.gr_templates_humanoid_animation_slot_count.argtypes = [ctypes.c_char_p]
    lib.gr_templates_humanoid_animation_slot_count.restype = ctypes.c_int
    lib.gr_templates_humanoid_rig_source.argtypes = [ctypes.c_char_p]
    lib.gr_templates_humanoid_rig_source.restype = ctypes.c_char_p
    lib.gr_templates_detect_twoda_format.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint]
    lib.gr_templates_detect_twoda_format.restype = ctypes.c_char_p
    lib.gr_templates_twoda_cell_or_default.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.gr_templates_twoda_cell_or_default.restype = ctypes.c_char_p
    lib.gr_templates_split_twoda_line_json.argtypes = [ctypes.c_char_p]
    lib.gr_templates_split_twoda_line_json.restype = ctypes.c_char_p
    lib.gr_templates_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def _text(value: bytes) -> str:
    return value.decode("utf-8")


def _detect(lib: ctypes.CDLL, payload: bytes) -> str:
    array = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    return _text(lib.gr_templates_detect_twoda_format(array, len(payload)))


def test_template_version_counts_match_python() -> None:
    lib = _dll()

    for raw, expected_version in [("K1", "K1"), ("k2", "K2"), ("", "K1"), ("TSL", "K1")]:
        assert _text(lib.gr_templates_normalize_game_version(_b(raw))) == expected_version

    for version in ["K1", "K2"]:
        assert lib.gr_templates_humanoid_bone_count(_b(version)) == len(get_bones_for_version(version))
        assert lib.gr_templates_humanoid_animation_slot_count(_b(version)) == len(get_anim_slots_for_version(version))
        source = _text(lib.gr_templates_humanoid_rig_source(_b(version)))
        assert ("KotOR 2" in source) == (version == "K2")


def test_twoda_format_and_cell_contracts_match_python_behavior() -> None:
    lib = _dll()

    assert _detect(lib, b"") == "empty"
    assert _detect(lib, b"2DA V2.b\ncols\x00") == "binary_v2b"
    assert _detect(lib, b"2DA V2.0\n\nlabel model\n") == "ascii_v2"
    assert _detect(lib, b"not a 2da") == "unknown"

    row = TwoDARow(0, ["label"], ["****"])
    assert row.get("label", "fallback") == "fallback"
    assert _text(lib.gr_templates_twoda_cell_or_default(b"****", b"fallback")) == "fallback"
    assert _text(lib.gr_templates_twoda_cell_or_default(b"", b"fallback")) == "fallback"
    assert _text(lib.gr_templates_twoda_cell_or_default(b"value", b"fallback")) == "value"


def test_twoda_line_splitter_matches_python() -> None:
    lib = _dll()

    for line in [
        "0 c_bastila **** 123",
        '1 "Quoted Value" model_a',
        "2\talpha\tbeta\t****",
        '3 "unterminated quote value',
        "          label             modela",
    ]:
        assert json.loads(lib.gr_templates_split_twoda_line_json(_b(line)).decode("utf-8")) == _split_2da_line(line)

    table = TwoDA()
    table.columns = ["label", "model"]
    table._rows = [["c_bastila", "p_bastila"]]
    assert table.get(0, "model") == "p_bastila"


def test_templates_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\TemplateContracts.cpp"' in project_text
    assert 'ClInclude Include="Public\\TemplateContracts.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::templates::core::templates::contracts" in source_text
    assert "namespace ghostrigger::templates::core::templates::contracts" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_templates_capabilities_document_native_and_python_boundaries() -> None:
    lib = _dll()
    capabilities = json.loads(lib.gr_templates_capabilities_json().decode("utf-8"))
    schema = json.loads(lib.gr_templates_contracts_schema_json().decode("utf-8"))

    assert capabilities["templates_contracts_native"] is True
    assert capabilities["templates_runtime_python_fallback"] is True
    assert schema["schema"] == "templates_contracts_native.v1"
    assert "ASCII 2DA line tokenization" in schema["native_scope"]
    assert "KotorModel construction" in schema["python_fallback"]
