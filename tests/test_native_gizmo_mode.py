from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.gizmo import gizmo_mode
from src.core.gizmo.gizmo_mode import GizmoMode, TransformGizmoMode, TransformSpace


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Gizmo"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Gizmo.dll"


def _load_gizmo_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_gizmo_normalize_mode.argtypes = [ctypes.c_char_p]
    dll.gr_gizmo_normalize_mode.restype = ctypes.c_char_p
    dll.gr_gizmo_cycle_mode.argtypes = [ctypes.c_char_p]
    dll.gr_gizmo_cycle_mode.restype = ctypes.c_char_p
    dll.gr_gizmo_mode_values_json.argtypes = []
    dll.gr_gizmo_mode_values_json.restype = ctypes.c_char_p
    dll.gr_gizmo_normalize_transform_space.argtypes = [ctypes.c_char_p]
    dll.gr_gizmo_normalize_transform_space.restype = ctypes.c_char_p
    dll.gr_gizmo_transform_space_values_json.argtypes = []
    dll.gr_gizmo_transform_space_values_json.restype = ctypes.c_char_p
    dll.gr_gizmo_capabilities_json.argtypes = []
    dll.gr_gizmo_capabilities_json.restype = ctypes.c_char_p
    dll.gr_gizmo_mode_contracts_schema_json.argtypes = []
    dll.gr_gizmo_mode_contracts_schema_json.restype = ctypes.c_char_p
    return dll


def test_gizmo_project_declares_mode_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Gizmo.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Gizmo.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerGizmo.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "GizmoMode.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "GizmoMode.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\GizmoMode.h" />' in project
    assert '<ClCompile Include="Private\\GizmoMode.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_gizmo_normalize_mode" in package_header
    assert "namespace ghostrigger::gizmo::core::gizmo::gizmo_mode" in public_header
    assert "namespace ghostrigger::gizmo::core::gizmo::gizmo_mode" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_gizmo_mode_values_and_cycle_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_gizmo_dll()

    assert TransformGizmoMode is GizmoMode
    assert tuple(json.loads(dll.gr_gizmo_mode_values_json().decode("utf-8"))) == tuple(mode.value for mode in GizmoMode)

    for mode in GizmoMode:
        actual = dll.gr_gizmo_normalize_mode(mode.value.encode("utf-8")).decode("utf-8")
        assert actual == mode.value

    assert dll.gr_gizmo_normalize_mode(b"").decode("utf-8") == GizmoMode.TRANSLATE.value
    assert dll.gr_gizmo_normalize_mode(b"not-real").decode("utf-8") == GizmoMode.TRANSLATE.value

    order = (GizmoMode.TRANSLATE, GizmoMode.ROTATE, GizmoMode.SCALE)
    for index, mode in enumerate(order):
        expected = order[(index + 1) % len(order)].value
        actual = dll.gr_gizmo_cycle_mode(mode.value.encode("utf-8")).decode("utf-8")
        assert actual == expected


def test_native_transform_space_values_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_gizmo_dll()

    assert tuple(json.loads(dll.gr_gizmo_transform_space_values_json().decode("utf-8"))) == tuple(
        space.value for space in TransformSpace
    )

    for space in TransformSpace:
        actual = dll.gr_gizmo_normalize_transform_space(space.value.encode("utf-8")).decode("utf-8")
        assert actual == space.value

    assert dll.gr_gizmo_normalize_transform_space(b"").decode("utf-8") == TransformSpace.WORLD.value
    assert dll.gr_gizmo_normalize_transform_space(b"not-real").decode("utf-8") == TransformSpace.WORLD.value


def test_native_gizmo_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_gizmo_dll()

    capabilities = json.loads(dll.gr_gizmo_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_gizmo_mode_contracts_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "gizmo_mode_contracts" in capabilities["capabilities"]
    assert "TransformSpace values" in schema["native_scope"]
    assert "TransformController drag math" in schema["python_fallback"]


def test_python_gizmo_mode_helpers_prefer_native_contract(monkeypatch) -> None:
    class _NativeGizmoProbe:
        def gr_gizmo_normalize_mode(self, value: bytes) -> bytes:
            return b"scale"

        def gr_gizmo_cycle_mode(self, value: bytes) -> bytes:
            return b"rotate"

        def gr_gizmo_mode_values_json(self) -> bytes:
            return b'["native-translate","native-rotate"]'

        def gr_gizmo_normalize_transform_space(self, value: bytes) -> bytes:
            return b"local"

        def gr_gizmo_transform_space_values_json(self) -> bytes:
            return b'["native-world","native-local"]'

    monkeypatch.setattr(gizmo_mode, "_native_gizmo", lambda: _NativeGizmoProbe())

    assert gizmo_mode.normalize_gizmo_mode("anything") is GizmoMode.SCALE
    assert gizmo_mode.cycle_gizmo_mode(GizmoMode.TRANSLATE) is GizmoMode.ROTATE
    assert gizmo_mode.gizmo_mode_values() == ("native-translate", "native-rotate")
    assert gizmo_mode.normalize_transform_space("anything") is TransformSpace.LOCAL
    assert gizmo_mode.transform_space_values() == ("native-world", "native-local")


def test_python_gizmo_mode_helpers_fall_back_when_native_missing(monkeypatch) -> None:
    monkeypatch.setattr(gizmo_mode, "_native_gizmo", lambda: None)

    assert gizmo_mode.normalize_gizmo_mode("not-real") is GizmoMode.TRANSLATE
    assert gizmo_mode.cycle_gizmo_mode(GizmoMode.SCALE) is GizmoMode.TRANSLATE
    assert gizmo_mode.gizmo_mode_values() == tuple(mode.value for mode in GizmoMode)
    assert gizmo_mode.normalize_transform_space("not-real") is TransformSpace.WORLD
    assert gizmo_mode.transform_space_values() == tuple(space.value for space in TransformSpace)
