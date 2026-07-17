from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2604_walkmesh_surface_palette_resolves_modder_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_walkmesh_surfaces import (
        authored_walkmesh_surface_palette,
        is_walkable_walkmesh_surface,
        resolve_walkmesh_surface_id,
        walkmesh_surface_name,
    )

    palette = authored_walkmesh_surface_palette()

    assert resolve_walkmesh_surface_id("metal") == 10
    assert resolve_walkmesh_surface_id("non walk") == 7
    assert resolve_walkmesh_surface_id("default") == 4
    assert resolve_walkmesh_surface_id("visual only") == 8
    assert resolve_walkmesh_surface_id("door transition") == 18
    assert walkmesh_surface_name(10) == "METAL"
    assert is_walkable_walkmesh_surface("metal") is True
    assert is_walkable_walkmesh_surface("water") is True
    assert is_walkable_walkmesh_surface("non_walk") is False
    assert is_walkable_walkmesh_surface("non_walk_grass") is False
    assert is_walkable_walkmesh_surface(20) is False
    assert is_walkable_walkmesh_surface("visual_only") is False
    assert is_walkable_walkmesh_surface("door_transition") is True
    assert {surface.authoring_name for surface in palette} >= {
        "stone",
        "grass",
        "metal",
        "non_walk",
        "water",
        "visual_only",
        "door_transition",
    }
    assert walkmesh_surface_name(19) == "NON_WALK_GRASS"
    assert walkmesh_surface_name(20) == "SURFACE_MATERIAL_20"
    assert walkmesh_surface_name(30) == "TRIGGER"


def test_t2604_unknown_walkmesh_surface_is_rejected() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_walkmesh_surfaces import resolve_walkmesh_surface_id

    try:
        resolve_walkmesh_surface_id("ice_cream")
    except ValueError as exc:
        assert "Unknown KOTOR walkmesh surface" in str(exc)
    else:
        raise AssertionError("Unknown surface should fail.")
