"""Tests for the KOTOR KB cross-reference improvements:
- surfacemat.2da 3-bit field logic
- multi-level walkmesh overlap warning
- -0.0 sanitization in MDL writer
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


# ── surfacemat.2da bit-field tests ──────────────────────────────────────

def test_surface_bitfield_walkable_surfaces_have_walk_bit() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import (
        SURFACE_BITFIELDS,
        SURFMAT_BIT_WALK,
        SURFMAT_BIT_WALK_CHECK,
        SURFMAT_BIT_LINE_OF_SIGHT,
        is_walkable_surface,
        is_walkcheck_surface,
        is_los_blocking_surface,
    )

    # Walkable surfaces (1,3,4,5,6,9,10,11,13,14,16,17,19) must have Walk bit
    walkable_ids = {1, 3, 4, 5, 6, 9, 10, 11, 13, 14, 16, 17, 19}
    for sid in walkable_ids:
        assert is_walkable_surface(sid), f"Surface {sid} should be walkable"
        assert SURFACE_BITFIELDS[sid] & SURFMAT_BIT_WALK, f"Surface {sid} missing Walk bit"

    # Non-walkable surfaces (0,2,7,8,15) must NOT have Walk bit
    for sid in (0, 2, 7, 8, 15):
        assert not is_walkable_surface(sid), f"Surface {sid} should NOT be walkable"

    # Surface 7 (NonWalk) must have NO bits — engine never tests it
    assert SURFACE_BITFIELDS[7] == 0, "Surface 7 must have zero flags — engine skips it entirely"
    assert not is_walkcheck_surface(7), "Surface 7 must not be walkcheck-tested"
    assert is_los_blocking_surface(7), "Surface 7 blocks LOS"


def test_surface_bitfield_walkcheck_bit_matches_engine_behavior() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import is_walkcheck_surface

    # Dirt (1) and Stone (4) have WalkCheck — engine tests them
    assert is_walkcheck_surface(1)
    assert is_walkcheck_surface(4)
    # NonWalk (7) and Transparent (8) do NOT have WalkCheck
    assert not is_walkcheck_surface(7)
    assert not is_walkcheck_surface(8)


# ── multi-level walkmesh overlap tests ──────────────────────────────────

_GOOD = dict(
    module_resref="grtest01",
    are_room_names=("room_a",),
    lyt_room_names=("room_a",),
    vis_pairs=(),
    rooms_with_wok=("room_a",),
    ifo_area_names=("grtest01",),
    entry_area="grtest01",
    has_pth=True,
    pth_point_count=5,
    surface_id_histogram={1: 100, 7: 20},
)


def test_multi_level_walkmesh_overlap_warning() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import check_module_against_base_game_contract

    # Two rooms with overlapping XY at different Z heights
    room_positions = [
        ("ground_floor", (0.0, 0.0, 0.0), (10.0, 10.0, 0.5)),
        ("upper_bridge", (2.0, 2.0, 5.0), (8.0, 8.0, 5.5)),
    ]
    report = check_module_against_base_game_contract(**{**_GOOD, "room_positions": room_positions})
    multi_level = [i for i in report.warnings if i.gate == "multi_level_walkmesh"]
    assert len(multi_level) == 1, [i.message for i in report.issues]
    assert "upper_bridge" in multi_level[0].message
    assert report.export_ready  # warning, not blocker


def test_multi_level_walkmesh_no_warning_for_separate_rooms() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import check_module_against_base_game_contract

    # Rooms far apart in XY — no overlap
    room_positions = [
        ("room_east", (0.0, 0.0, 0.0), (10.0, 10.0, 0.5)),
        ("room_west", (50.0, 50.0, 0.0), (60.0, 60.0, 0.5)),
    ]
    report = check_module_against_base_game_contract(**{**_GOOD, "room_positions": room_positions})
    multi_level = [i for i in report.warnings if i.gate == "multi_level_walkmesh"]
    assert len(multi_level) == 0, [i.message for i in report.issues]


def test_multi_level_walkmesh_no_warning_for_same_z() -> None:
    _configure_native_python_roots()
    from src.core.modules.map_studio_base_game_contract import check_module_against_base_game_contract

    # Overlapping XY but SAME Z — not multi-level (just bad layout, different gate)
    room_positions = [
        ("room_a", (0.0, 0.0, 0.0), (10.0, 10.0, 0.5)),
        ("room_b", (5.0, 5.0, 0.0), (15.0, 15.0, 0.5)),
    ]
    report = check_module_against_base_game_contract(**{**_GOOD, "room_positions": room_positions})
    multi_level = [i for i in report.warnings if i.gate == "multi_level_walkmesh"]
    assert len(multi_level) == 0


# ── -0.0 sanitization tests ─────────────────────────────────────────────

def test_sanitize_float_converts_negative_zero() -> None:
    _configure_native_python_roots()
    from src.core.mdl.mdl_writer import _sanitize_float
    import math

    # -0.0 must become +0.0
    result = _sanitize_float(-0.0)
    assert result == 0.0
    assert math.copysign(1.0, result) > 0.0, "Must be positive zero, not negative"

    # +0.0 stays +0.0
    assert _sanitize_float(0.0) == 0.0
    assert math.copysign(1.0, _sanitize_float(0.0)) > 0.0

    # Normal values pass through
    assert _sanitize_float(1.5) == 1.5
    assert _sanitize_float(-3.14) == -3.14

    # NaN → 0.0
    assert _sanitize_float(float("nan")) == 0.0
    # Inf → 0.0
    assert _sanitize_float(float("inf")) == 0.0
    assert _sanitize_float(float("-inf")) == 0.0


def test_wf32_does_not_produce_negative_zero_bytes() -> None:
    _configure_native_python_roots()
    from src.core.mdl.mdl_writer import _wf32

    # struct.pack of -0.0 produces 0x80000000 (sign bit set)
    negative_zero_bytes = struct.pack("<f", -0.0)
    assert negative_zero_bytes == b"\x00\x00\x00\x80"

    # _wf32(-0.0) must NOT produce those bytes
    sanitized = _wf32(-0.0)
    assert sanitized != b"\x00\x00\x00\x80", "_wf32 must sanitize -0.0 to +0.0"
    assert sanitized == b"\x00\x00\x00\x00"


def test_wf32_normal_values_unchanged() -> None:
    _configure_native_python_roots()
    from src.core.mdl.mdl_writer import _wf32

    assert _wf32(1.0) == struct.pack("<f", 1.0)
    assert _wf32(-2.5) == struct.pack("<f", -2.5)
    assert _wf32(3.14159) == struct.pack("<f", 3.14159)


def test_contract_payload_copies_byte_identical_after_kb_fixes() -> None:
    name = "map_studio_base_game_contract.py"
    scene = (ROOT / f"native/GhostRigger.Core.Scene/Python/src/core/modules/{name}").read_bytes()
    tools = (ROOT / f"native/GhostRigger.Core.Tools/Python/src/core/modules/{name}").read_bytes()
    assert scene == tools
