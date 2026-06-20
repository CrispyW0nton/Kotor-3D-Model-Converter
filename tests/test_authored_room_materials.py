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


def test_t2609_normalizes_default_room_texture_to_vanilla_baseline() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_materials import (
        DEFAULT_AUTHORED_ROOM_TEXTURE,
        compile_authored_room_material_preflight,
        normalize_authored_room_texture,
    )

    assert normalize_authored_room_texture("default") == DEFAULT_AUTHORED_ROOM_TEXTURE
    assert normalize_authored_room_texture("") == DEFAULT_AUTHORED_ROOM_TEXTURE

    preflight = compile_authored_room_material_preflight("default")

    assert preflight.texture == DEFAULT_AUTHORED_ROOM_TEXTURE
    assert preflight.blocking_issues == ()
    assert "not resolved against KOTOR data" in preflight.message
    assert preflight.metadata["source"] == "src.core.modules.authored_room_materials"


def test_t2609_blocks_path_like_room_texture_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_materials import compile_authored_room_material_preflight

    preflight = compile_authored_room_material_preflight("bad/texture")

    assert preflight.resolved is False
    assert preflight.blocking_issues
    assert "must be a texture resref" in preflight.blocking_issues[0]
