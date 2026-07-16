"""Room catalog: enumerate rooms + doorway connection points from any source.

Foundation for the modular map builder — pick rooms from the game library,
a .mod capsule, or a .kmap, each labeled and carrying its LYT door-hooks so a
later pass can snap two rooms entrance-to-entrance.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_door_hooks_are_grouped_per_room_in_local_coordinates() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import _door_hooks_by_room

    lyt = SimpleNamespace(
        rooms=[
            SimpleNamespace(model="roomA", position=SimpleNamespace(x=10.0, y=20.0, z=0.0)),
            SimpleNamespace(model="roomB", position=SimpleNamespace(x=-5.0, y=0.0, z=3.0)),
        ],
        doorhooks=[
            SimpleNamespace(room="roomA", door="door_1", position=SimpleNamespace(x=12.0, y=20.0, z=0.0), orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)),
            SimpleNamespace(room="roomB", door="door_2", position=SimpleNamespace(x=-5.0, y=2.0, z=3.0), orientation=SimpleNamespace(x=0.0, y=0.0, z=1.0, w=0.0)),
        ],
    )
    grouped = _door_hooks_by_room(lyt)
    # Hook world position minus the room origin -> room-local position.
    assert grouped["rooma"][0].local_position == (2.0, 0.0, 0.0)
    assert grouped["roomb"][0].local_position == (0.0, 2.0, 0.0)
    # z=1,w=0 quaternion is a 180-degree yaw.
    assert math.isclose(abs(grouped["roomb"][0].facing_radians), math.pi, abs_tol=1e-6)


def test_kmap_catalog_lists_authored_rooms(tmp_path) -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import build_room_catalog_from_kmap

    kmap = {
        "authored_module": {
            "module_root": "grcat01",
            "game": "K2",
            "rooms": [
                {"room_resref": "grroom_a", "position": [0.0, 0.0, 0.0], "primitive": {"room_resref": "grroom_a"}},
                {"position": [5.0, 1.0, 0.0], "primitive": {"room_resref": "grroom_b", "metadata": {"original_room_name": "grroom_b"}}},
            ],
        }
    }
    path = tmp_path / "grcat01.k2.kmap"
    path.write_text(json.dumps(kmap), encoding="utf-8")
    result = build_room_catalog_from_kmap(path)
    assert not result.warnings
    resrefs = {e.room_resref for e in result.entries}
    assert resrefs == {"grroom_a", "grroom_b"}
    entry = next(e for e in result.entries if e.room_resref == "grroom_b")
    assert entry.source_kind == "kmap"
    assert entry.module_position == (5.0, 1.0, 0.0)
    assert entry.game == "K2"
    assert entry.entry_id == "kmap:grcat01:grroom_b"


def test_catalog_result_sorts_deterministically() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import RoomCatalogEntry, RoomCatalogResult

    a = RoomCatalogEntry("mod", "p", "modb", "r2", "K2", "b/r2")
    b = RoomCatalogEntry("mod", "p", "moda", "r1", "K2", "a/r1")
    c = RoomCatalogEntry("mod", "p", "moda", "r2", "K2", "a/r2")
    ordered = RoomCatalogResult(entries=(a, b, c)).sorted_entries()
    assert [e.entry_id for e in ordered] == ["mod:moda:r1", "mod:moda:r2", "mod:modb:r2"]


def test_missing_sources_degrade_to_warnings(tmp_path) -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import (
        build_room_catalog_from_capsule,
        build_room_catalog_from_kmap,
        scan_room_catalog_sources,
    )

    assert build_room_catalog_from_capsule(tmp_path / "nope.mod").warnings
    assert build_room_catalog_from_kmap(tmp_path / "nope.kmap").warnings
    scanned = scan_room_catalog_sources(module_dirs=[tmp_path / "missing"], game="K2")
    assert scanned.entries == ()
    assert any("not found" in w for w in scanned.warnings)


def test_real_921srt_module_smoke() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import build_room_catalog_from_capsule

    mod = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\921srt\K2\Modules\921srt.mod")
    if not mod.is_file():
        import pytest

        pytest.skip("921srt.mod not present on this machine")
    result = build_room_catalog_from_capsule(mod, game="K2")
    assert not result.warnings
    resrefs = {e.room_resref for e in result.entries}
    assert "921srtb" in resrefs
    assert any(r.startswith("903mal") for r in resrefs)
    # At least one room exposes doorway connection points from the LYT hooks.
    assert any(e.connection_count > 0 for e in result.entries)
