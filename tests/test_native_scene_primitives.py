from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path

from src.core.scene.scene_object import PivotData, Transform
from src.core.scene.scene_object_instance import SceneObjectInstance
from src.core.scene.scene_resource_ref import SceneResourceRef


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "native" / "GhostRigger.Scene"
DLL_PATH = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Scene.dll"


Double3 = ctypes.c_double * 3


def _load_scene_dll() -> ctypes.CDLL:
    dll = ctypes.CDLL(str(DLL_PATH))
    dll.gr_scene_sanitize_vec3.argtypes = [
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    dll.gr_scene_sanitize_vec3.restype = ctypes.c_int
    dll.gr_scene_transform_defaults.argtypes = [
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    dll.gr_scene_transform_defaults.restype = ctypes.c_int
    dll.gr_scene_pivot_defaults.argtypes = [
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_int),
    ]
    dll.gr_scene_pivot_defaults.restype = ctypes.c_int
    dll.gr_scene_pivot_values_are_valid.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    dll.gr_scene_pivot_values_are_valid.restype = ctypes.c_int
    dll.gr_scene_sanitize_resource_game.argtypes = [ctypes.c_char_p]
    dll.gr_scene_sanitize_resource_game.restype = ctypes.c_char_p
    dll.gr_scene_resource_ref_defaults_json.argtypes = []
    dll.gr_scene_resource_ref_defaults_json.restype = ctypes.c_char_p
    dll.gr_scene_metadata_key_is_persisted.argtypes = [ctypes.c_char_p]
    dll.gr_scene_metadata_key_is_persisted.restype = ctypes.c_int
    dll.gr_scene_capabilities_json.argtypes = []
    dll.gr_scene_capabilities_json.restype = ctypes.c_char_p
    dll.gr_scene_primitives_schema_json.argtypes = []
    dll.gr_scene_primitives_schema_json.restype = ctypes.c_char_p
    return dll


def _tuple3(values: Double3) -> tuple[float, float, float]:
    return (values[0], values[1], values[2])


def test_scene_project_declares_scene_primitive_files_and_exports() -> None:
    project = (PROJECT_DIR / "GhostRigger.Scene.vcxproj").read_text(encoding="utf-8")
    filters = (PROJECT_DIR / "GhostRigger.Scene.vcxproj.filters").read_text(encoding="utf-8")
    package_header = (PROJECT_DIR / "Public" / "GhostRiggerScene.h").read_text(encoding="utf-8")
    public_header = (PROJECT_DIR / "Public" / "ScenePrimitives.h").read_text(encoding="utf-8")
    implementation = (PROJECT_DIR / "Private" / "ScenePrimitives.cpp").read_text(encoding="utf-8")

    assert '<ClInclude Include="Public\\ScenePrimitives.h" />' in project
    assert '<ClCompile Include="Private\\ScenePrimitives.cpp" />' in project
    assert '<Filter>Public</Filter>' in filters
    assert '<Filter>Private</Filter>' in filters
    assert "gr_scene_sanitize_vec3" in package_header
    assert "namespace ghostrigger::scene::core::scene::scene_primitives" in public_header
    assert "namespace ghostrigger::scene::core::scene::scene_primitives" in implementation
    assert "phase15" not in public_header
    assert "pyfn_" not in implementation
    assert "using namespace" not in implementation


def test_native_vec3_transform_and_pivot_defaults_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    out = Double3()
    fallback = Double3(9.0, 8.0, 7.0)
    assert dll.gr_scene_sanitize_vec3(Double3(1.0, 2.0, 3.0), fallback, out) == 1
    assert _tuple3(out) == (1.0, 2.0, 3.0)
    assert dll.gr_scene_sanitize_vec3(Double3(1.0, math.inf, 3.0), fallback, out) == 1
    assert _tuple3(out) == (9.0, 8.0, 7.0)

    position = Double3()
    rotation = Double3()
    scale = Double3()
    assert dll.gr_scene_transform_defaults(position, rotation, scale) == 1
    transform = Transform()
    assert _tuple3(position) == transform.position
    assert _tuple3(rotation) == transform.rotation
    assert _tuple3(scale) == transform.scale

    pivot_position = Double3()
    pivot_rotation = Double3()
    enabled = ctypes.c_int()
    assert dll.gr_scene_pivot_defaults(pivot_position, pivot_rotation, ctypes.byref(enabled)) == 1
    pivot = PivotData()
    assert _tuple3(pivot_position) == pivot.position_local
    assert _tuple3(pivot_rotation) == pivot.rotation_local
    assert bool(enabled.value) is pivot.enabled


def test_native_pivot_validity_and_resource_ref_defaults_match_python() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    assert dll.gr_scene_pivot_values_are_valid(Double3(0.0, 1.0, 2.0), Double3(3.0, 4.0, 5.0)) == 1
    assert PivotData((0.0, 1.0, 2.0), (3.0, 4.0, 5.0)).is_valid()
    assert dll.gr_scene_pivot_values_are_valid(Double3(0.0, math.nan, 2.0), Double3(3.0, 4.0, 5.0)) == 0
    assert not PivotData((0.0, math.nan, 2.0), (3.0, 4.0, 5.0)).is_valid()

    defaults = json.loads(dll.gr_scene_resource_ref_defaults_json().decode("utf-8"))
    assert defaults == SceneResourceRef().to_dict()

    for value in ["", "k1", "k2", "tsl", " custom "]:
        native = dll.gr_scene_sanitize_resource_game(value.encode("utf-8")).decode("utf-8")
        expected = SceneResourceRef.from_dict({"game": value}).game
        assert native == expected


def test_native_scene_metadata_persistence_rule_matches_scene_object_instance() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    obj = SceneObjectInstance(
        id="obj-1",
        name="Scene Object",
        metadata={"artist": "LordVaderCW", "_runtime_model": object(), "_runtime_cache": {"x": 1}},
    )
    payload = obj.to_dict()
    assert "artist" in payload["metadata"]
    assert "_runtime_model" not in payload["metadata"]
    assert "_runtime_cache" not in payload["metadata"]

    assert dll.gr_scene_metadata_key_is_persisted(b"artist") == 1
    assert dll.gr_scene_metadata_key_is_persisted(b"_runtime_model") == 0
    assert dll.gr_scene_metadata_key_is_persisted(b"_runtime_cache") == 0


def test_native_scene_primitive_capabilities_document_python_fallback_scope() -> None:
    assert DLL_PATH.exists(), f"Build Release first: {DLL_PATH}"
    dll = _load_scene_dll()

    capabilities = json.loads(dll.gr_scene_capabilities_json().decode("utf-8"))
    schema = json.loads(dll.gr_scene_primitives_schema_json().decode("utf-8"))

    assert capabilities["native_implementation_enabled"] is True
    assert capabilities["python_fallback_required"] is True
    assert "scene_primitive_contracts" in capabilities["capabilities"]
    assert "vec3 finite sanitation" in schema["native_scope"]
    assert "Python dataclass object construction" in schema["python_fallback"]
