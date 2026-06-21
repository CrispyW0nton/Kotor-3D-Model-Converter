from __future__ import annotations

import ctypes
import json
from pathlib import Path

from src.core.walkmesh import walkmesh_renderer


ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "build" / "vs" / "x64" / "Release" / "GhostRigger.Core.Scene.dll"
PROJECT = ROOT / "native" / "GhostRigger.Core.Scene" / "GhostRigger.Core.Scene.vcxproj"
FILTERS = ROOT / "native" / "GhostRigger.Core.Scene" / "GhostRigger.Core.Scene.vcxproj.filters"
HEADER = ROOT / "native" / "GhostRigger.Core.Scene" / "Public" / "WalkmeshSurface.h"
SOURCE = ROOT / "native" / "GhostRigger.Core.Scene" / "Private" / "WalkmeshSurface.cpp"


def _dll() -> ctypes.CDLL:
    lib = ctypes.CDLL(str(DLL))
    lib.gr_walkmesh_surface_name.argtypes = [ctypes.c_int]
    lib.gr_walkmesh_surface_name.restype = ctypes.c_char_p
    lib.gr_walkmesh_surface_color.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.gr_walkmesh_surface_is_walkable.argtypes = [ctypes.c_int]
    lib.gr_walkmesh_surface_is_walkable.restype = ctypes.c_int
    lib.gr_walkmesh_surface_is_non_walkable.argtypes = [ctypes.c_int]
    lib.gr_walkmesh_surface_is_non_walkable.restype = ctypes.c_int
    lib.gr_walkmesh_fbx_material_name.argtypes = [ctypes.c_int]
    lib.gr_walkmesh_fbx_material_name.restype = ctypes.c_char_p
    lib.gr_walkmesh_fbx_material_diffuse.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double),
    ]
    lib.gr_walkmesh_surface_contracts_schema_json.restype = ctypes.c_char_p
    return lib


def _surface_color(lib: ctypes.CDLL, surface_id: int) -> tuple[float, float, float, float]:
    r = ctypes.c_double()
    g = ctypes.c_double()
    b = ctypes.c_double()
    a = ctypes.c_double()
    lib.gr_walkmesh_surface_color(surface_id, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a))
    return (r.value, g.value, b.value, a.value)


def _fbx_diffuse(lib: ctypes.CDLL, surface_id: int) -> tuple[float, float, float]:
    r = ctypes.c_double()
    g = ctypes.c_double()
    b = ctypes.c_double()
    lib.gr_walkmesh_fbx_material_diffuse(surface_id, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b))
    return (r.value, g.value, b.value)


def test_walkmesh_surface_contracts_match_python_renderer() -> None:
    lib = _dll()

    for surface_id in [*range(23), 99, -1]:
        assert lib.gr_walkmesh_surface_name(surface_id).decode("utf-8") == walkmesh_renderer.surface_name(surface_id)
        assert _surface_color(lib, surface_id) == walkmesh_renderer.surface_color(surface_id)
        assert bool(lib.gr_walkmesh_surface_is_walkable(surface_id)) == (
            surface_id in walkmesh_renderer.WALKABLE_SURFACES
        )
        assert bool(lib.gr_walkmesh_surface_is_non_walkable(surface_id)) == (
            surface_id in walkmesh_renderer.NON_WALKABLE_SURFACES
        )

        fbx_material = walkmesh_renderer.get_walkmesh_fbx_material(surface_id)
        assert lib.gr_walkmesh_fbx_material_name(surface_id).decode("utf-8") == fbx_material["name"]
        assert _fbx_diffuse(lib, surface_id) == fbx_material["diffuse"]


def test_walkmesh_surface_contracts_are_explicit_in_visual_studio_project() -> None:
    project_text = PROJECT.read_text(encoding="utf-8")
    filters_text = FILTERS.read_text(encoding="utf-8")
    source_text = SOURCE.read_text(encoding="utf-8")
    header_text = HEADER.read_text(encoding="utf-8")

    assert 'ClCompile Include="Private\\WalkmeshSurface.cpp"' in project_text
    assert 'ClInclude Include="Public\\WalkmeshSurface.h"' in project_text
    assert "<Filter>Private</Filter>" in filters_text
    assert "<Filter>Public</Filter>" in filters_text
    assert "namespace ghostrigger::core::walkmesh::core::walkmesh::surface" in source_text
    assert "namespace ghostrigger::core::walkmesh::core::walkmesh::surface" in header_text

    forbidden = ("*.cpp", "*.h", "using namespace", "phase15", "pyfn_")
    for token in forbidden:
        assert token not in project_text
        assert token not in source_text
        assert token not in header_text


def test_walkmesh_surface_contracts_document_native_and_python_boundaries() -> None:
    lib = _dll()
    schema = json.loads(lib.gr_walkmesh_surface_contracts_schema_json().decode("utf-8"))

    assert schema["schema"] == "walkmesh_surface_native.v1"
    assert "surface overlay colors" in schema["native_scope"]
    assert "WOK object traversal" in schema["python_fallback"]
