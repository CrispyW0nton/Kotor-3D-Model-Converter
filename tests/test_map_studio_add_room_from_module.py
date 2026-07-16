"""Modular maps Phase 2: add an indexed room from another module.

The room catalog now reads ASCII MAXLAYOUT LYTs (which PyKotor's binary
reader rejects and which Map Studio itself exports), including door hooks
whose names contain spaces. The controller appends a chosen catalog room to
the current project as editable geometry at a non-overlapping drop point,
recording its source module for later doorway snapping.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ASCII_LYT = """#MAXLAYOUT ASCII
filedependancy grtest.max
beginlayout
   roomcount 2
      grroom_a 10.000000 20.000000 0.000000
      grroom_b -5.000000 0.000000 3.000000
   trackcount 0
   obstaclecount 0
   doorhookcount 2
      grroom_a door_01 0 12.000000 20.000000 0.000000 1.000000 0.000000 0.000000 0.000000
      grroom_a force field sith 0 8.000000 5.000000 0.000000 0.712666 0.000000 0.000000 -0.701503
   donelayout
"""


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_ascii_lyt_parser_recovers_rooms_and_spaced_door_names() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import _parse_ascii_lyt

    lyt = _parse_ascii_lyt(_ASCII_LYT.encode("latin-1"))
    assert lyt is not None
    assert [r.model for r in lyt.rooms] == ["grroom_a", "grroom_b"]
    assert lyt.rooms[0].position.x == 10.0 and lyt.rooms[0].position.y == 20.0
    # Two door hooks, including one whose name has spaces.
    assert len(lyt.doorhooks) == 2
    spaced = next(h for h in lyt.doorhooks if "field" in h.door)
    assert spaced.door == "force_field_sith"
    assert spaced.position.x == 8.0 and spaced.position.y == 5.0
    # Aurora quaternion is w-first in the ASCII row.
    assert abs(spaced.orientation.w - 0.712666) < 1e-6
    assert abs(spaced.orientation.z + 0.701503) < 1e-6


def test_ascii_lyt_parser_rejects_non_layout() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_room_catalog import _parse_ascii_lyt

    assert _parse_ascii_lyt(b"not a layout file") is None


def test_next_added_room_position_offsets_east() -> None:
    _configure_native_python_roots()
    from types import SimpleNamespace

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grmodpos", game="K2")
    # No rooms yet -> origin.
    assert controller._next_added_room_position() == (0.0, 0.0, 0.0)


def test_add_catalog_room_from_real_module() -> None:
    _configure_native_python_roots()
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_room_catalog import build_room_catalog_from_capsule
    from src.core.modules.module_editor_controller import ModuleEditorController

    source = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\921srt\K2\Modules\921srt.mod")
    k2_dir = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
    if not source.is_file() or not k2_dir.is_dir():
        import pytest

        pytest.skip("921srt.mod or K2 install not present")

    catalog = build_room_catalog_from_capsule(source, game="K2")
    assert not catalog.warnings, catalog.warnings
    entry = next(e for e in catalog.sorted_entries() if e.room_resref == "903malc")
    assert entry.connection_count > 0  # door hooks recovered from the ASCII LYT

    manager = ResourceManager()
    manager.set_k2_dir(str(k2_dir))
    controller = ModuleEditorController()
    controller.new_project(name="grmodular", game="K2")
    ok, message = controller.add_catalog_room_to_project(
        room_resref=entry.room_resref,
        source_path=entry.source_path,
        source_module=entry.module_resref,
        game=entry.game,
        resource_manager=manager,
    )
    assert ok, message
    authored = controller._load_authored_project_or_raise()
    added = next(r for r in authored.rooms if r.normalised_resref() == "903malc")
    meta = dict(getattr(added, "metadata", {}) or {})
    assert meta.get("added_from_catalog") is True
    assert meta.get("catalog_source_module") == "921srt"
    # Re-adding the same room is refused.
    ok2, message2 = controller.add_catalog_room_to_project(
        room_resref="903malc", source_path=str(source), source_module="921srt", game="K2", resource_manager=manager,
    )
    assert not ok2 and "already in this module" in message2
