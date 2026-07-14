"""Base-game module contract gate tests (evidence-backed export validation)."""
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


def _check(**kwargs):
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import check_module_against_base_game_contract

    return check_module_against_base_game_contract(**kwargs)


_GOOD = dict(
    module_resref="grtest01",
    are_room_names=("grtest01_room1", "grtest01_room2"),
    lyt_room_names=("GRTEST01_room1", "grtest01_room2"),
    vis_pairs=(("grtest01_room1", "grtest01_room2"), ("grtest01_room2", "grtest01_room1")),
    rooms_with_wok=("grtest01_room1", "grtest01_room2"),
    ifo_area_names=("grtest01",),
    entry_area="grtest01",
    has_pth=True,
    pth_point_count=12,
    surface_id_histogram={1: 120, 7: 80, 19: 4},
    sun_shadows=False,
    creature_count=3,
    waypoint_count=8,
)


def test_polished_module_passes_all_gates() -> None:
    report = _check(**_GOOD)
    assert report.export_ready, [i.message for i in report.issues]
    assert not report.issues


def test_are_lyt_room_mismatch_blocks_export() -> None:
    bad = dict(_GOOD, are_room_names=("grtest01_room1",))
    report = _check(**bad)
    assert not report.export_ready
    assert any(i.gate == "are_rooms_match_lyt" for i in report.blockers)


def test_vis_asymmetry_blocks_export() -> None:
    bad = dict(_GOOD, vis_pairs=(("grtest01_room1", "grtest01_room2"),))
    report = _check(**bad)
    assert any(i.gate == "vis_symmetry" for i in report.blockers)


def test_missing_wok_and_placeholder_rooms_block_export() -> None:
    bad = dict(_GOOD, rooms_with_wok=("grtest01_room1",))
    report = _check(**bad)
    assert any(i.gate == "room_wok_coverage" for i in report.blockers)

    stunt = dict(_GOOD, lyt_room_names=("grtest01_room1", "grtest01_room2", "****"))
    report = _check(**stunt)
    assert any(i.gate == "lyt_placeholder_room" for i in report.blockers)


def test_pth_and_ifo_gates() -> None:
    report = _check(**dict(_GOOD, has_pth=False))
    assert any(i.gate == "pth_present" for i in report.blockers)

    report = _check(**dict(_GOOD, pth_point_count=0))
    assert any(i.gate == "pth_points_for_creatures" for i in report.warnings)
    assert report.export_ready  # warning only

    report = _check(**dict(_GOOD, ifo_area_names=()))
    assert any(i.gate == "ifo_single_area" for i in report.blockers)

    report = _check(**dict(_GOOD, entry_area="elsewhere"))
    assert any(i.gate == "ifo_entry_area" for i in report.blockers)


def test_walkability_and_surface_vocabulary_gates() -> None:
    report = _check(**dict(_GOOD, surface_id_histogram={7: 200, 2: 12}))
    assert any(i.gate == "wok_walkable_faces" for i in report.blockers)

    report = _check(**dict(_GOOD, surface_id_histogram={1: 50, 25: 3}))
    assert any(i.gate == "wok_surface_vocabulary" for i in report.warnings)
    assert report.export_ready

    report = _check(**dict(_GOOD, sun_shadows=True))
    assert any(i.gate == "are_sun_shadows" for i in report.warnings)


def test_resref_length_gate() -> None:
    report = _check(**dict(_GOOD, module_resref="a_very_long_module_resref"))
    assert any(i.gate == "resref_length" for i in report.blockers)


def test_contract_payload_copies_are_byte_identical() -> None:
    name = "map_studio_base_game_contract.py"
    scene = (ROOT / f"native/GhostRigger.Core.Scene/Python/src/core/modules/{name}").read_bytes()
    tools = (ROOT / f"native/GhostRigger.Core.Tools/Python/src/core/modules/{name}").read_bytes()
    assert scene == tools
