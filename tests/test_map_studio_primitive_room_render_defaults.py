from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_default_rectangular_room_uses_plcaa_style_diffuse_normals_and_uv_scale() -> None:
    _configure_native_python_roots()
    from core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_mesh
    from core.modules.authored_room_materials import (
        DEFAULT_AUTHORED_ROOM_TEXTURE,
        DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE,
    )

    mesh = build_rectangular_room_mesh(
        RectangularRoomPrimitive(
            room_resref="grgold01_room01",
            width=12.0,
            depth=12.0,
            wall_height=3.0,
            texture=DEFAULT_AUTHORED_ROOM_TEXTURE,
        )
    )

    assert DEFAULT_AUTHORED_ROOM_TEXTURE == "ruler01"
    assert DEFAULT_AUTHORED_ROOM_UV_TILE_SIZE == 2.0
    assert len(mesh.vertices) == 20
    assert len(mesh.faces) == 10
    assert set(mesh.normals) == {
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
        (1.0, 0.0, 0.0),
    }
    assert max(u for u, _v in mesh.uvs) == 6.0
    assert max(v for _u, v in mesh.uvs) == 6.0
    assert mesh.metadata["uv_layout"] == "plcaa_world_tiled"


def test_golden_room_uses_balanced_preview_lighting_instead_of_fullbright() -> None:
    _configure_native_python_roots()
    from core.modules.authored_module_kmap_bridge import create_golden_test_authored_module_payload

    payload = create_golden_test_authored_module_payload(module_root="grgold01", game="K1")
    lighting = payload["metadata"]["lighting"]

    assert payload["rooms"][0]["primitive"]["texture"] == "ruler01"
    assert payload["lights"][0]["intensity"] == 0.65
    assert lighting["profile"] == "standard"
    assert lighting["sun_ambient"] == [48, 48, 48]
    assert lighting["sun_diffuse"] == [150, 150, 150]
    assert lighting["dynamic_ambient"] == [72, 72, 72]


def test_new_authored_room_uses_the_same_balanced_preview_defaults() -> None:
    _configure_native_python_roots()
    from core.modules.authored_module_kmap_bridge import create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    lighting = payload["metadata"]["lighting"]

    assert payload["rooms"][0]["primitive"]["texture"] == "ruler01"
    assert payload["lights"][0]["intensity"] == 0.65
    assert lighting["profile"] == "standard"
    assert lighting["purpose"] == "textured_graybox_visibility"
