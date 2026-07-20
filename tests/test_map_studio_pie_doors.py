"""PIE door auto-open and room-to-room transitions.

Doors in the running module now open as the player approaches and close
behind them. Because the combined module walkmesh keeps each room as its own
island, walking into a room boundary next to an open door steps the player
across into the adjoining room — an editor stand-in for the engine's room
transition. Inter-module doors are reported, not teleported (PIE simulates a
single module).
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _two_island_wok(gap: float = 2.0):
    """Two 10x10 walkable quads separated by a Y gap (two walkmesh islands)."""
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(name="twoislands")
    # Island A: y 0..10
    wok.verts.extend([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)])
    # Island B: y (10+gap)..(20+gap)
    b0 = 10.0 + gap
    wok.verts.extend([(0.0, b0, 0.0), (10.0, b0, 0.0), (10.0, b0 + 10.0, 0.0), (0.0, b0 + 10.0, 0.0)])
    wok.faces.append(WOKFace(0, 1, 2, 1, -1, -1, -1))
    wok.faces.append(WOKFace(0, 2, 3, 1, -1, -1, -1))
    wok.faces.append(WOKFace(4, 5, 6, 1, -1, -1, -1))
    wok.faces.append(WOKFace(4, 6, 7, 1, -1, -1, -1))
    return wok


def _registry_with_door(
    *,
    position,
    tag="TestDoor",
    transition_module="",
    transition_target="",
    facing=math.pi * 0.5,
    locked=False,
    target_radius=1.0,
):
    from src.core.modules.map_studio_pie_entities import PIEEntity, PIEEntityRegistry

    door = PIEEntity(
        entity_id="authored:door:0",
        kind="door",
        tag=tag,
        display_name=tag,
        template_resref="door_test",
        position=position,
        facing=facing,
        interaction="door",
        locked=locked,
        target_radius=target_radius,
        transition_module=transition_module,
        transition_target=transition_target,
    )
    return PIEEntityRegistry(entities=(door,))


def _session(wok, registry, spawn=(5.0, 2.0, 0.0)):
    from src.core.modules.map_studio_pie import MapStudioPIESession

    session = MapStudioPIESession(wok, game="K1", spawn_position=spawn)
    session.entity_registry = registry
    assert session.validation.ok, session.validation.blocking_issues
    return session


def _walk(session, direction, seconds, azimuth):
    events = []
    for _ in range(int(seconds * 30)):
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=azimuth, run=True)
        frame = session.advance(1.0 / 30.0)
        events.extend(frame.events)
    return events


def test_doors_are_detected_from_the_registry() -> None:
    _configure_native_python_roots()
    session = _session(_two_island_wok(), _registry_with_door(position=(5.0, 11.0, 0.0)))
    doors = session.door_states()
    assert len(doors) == 1
    assert doors[0].tag == "TestDoor"
    assert doors[0].facing == math.pi * 0.5
    assert doors[0].is_open is False


def test_door_opens_on_approach_and_player_crosses_to_next_room() -> None:
    _configure_native_python_roots()
    session = _session(_two_island_wok(gap=2.0), _registry_with_door(position=(5.0, 11.0, 0.0)))
    start_face = session.state.face_index
    # Camera azimuth chosen so forward (W press) drives +Y toward the door.
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    kinds = [e.kind for e in events]
    assert "door_opened" in kinds, kinds
    assert "room_transition" in kinds, kinds
    # The player ended up on the far island (a different walkable face) past the gap.
    assert session.state.position[1] > 12.0
    assert session.state.face_index != start_face


def test_door_closes_after_the_player_leaves() -> None:
    _configure_native_python_roots()
    # Door near the far edge of island A; the gap is too wide to cross, so the
    # player halts at the door (open) and can then retreat to close it.
    session = _session(_two_island_wok(gap=8.0), _registry_with_door(position=(5.0, 9.0, 0.0)))
    _walk(session, "forward", seconds=4.0, azimuth=-90.0)
    assert any(d.is_open for d in session.door_states()), "door should be open at the threshold"
    _walk(session, "forward", seconds=5.0, azimuth=90.0)  # retreat (-Y)
    assert not any(d.is_open for d in session.door_states()), "door should close once the player leaves"


def test_inter_module_door_is_reported_not_teleported() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        _registry_with_door(position=(5.0, 11.0, 0.0), transition_module="921srt2", transition_target="wp_entry"),
    )
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    kinds = [e.kind for e in events]
    assert kinds.count("module_transition_blocked") == 1, kinds
    assert "room_transition" not in kinds
    # The player stays on the near island (no fabricated cross-module teleport).
    assert session.state.position[1] < 11.0


def test_locked_door_stays_closed_and_reports_contact_once() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        _registry_with_door(position=(5.0, 11.0, 0.0), locked=True),
    )
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    kinds = [event.kind for event in events]
    assert kinds.count("door_locked") == 1, kinds
    assert "door_opened" not in kinds
    assert "room_transition" not in kinds
    assert session.door_states()[0].locked is True
    assert session.door_states()[0].is_open is False


def test_nearby_side_door_does_not_teleport_player_across_gap() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        # Three metres to the side: close enough for the broad auto-open reach,
        # but outside this doorway's actual width.
        _registry_with_door(position=(8.0, 11.0, 0.0)),
    )
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    assert "room_transition" not in [event.kind for event in events]
    assert session.state.position[1] < 11.0


def test_crossing_requires_motion_through_door_plane() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        # Facing +X makes +Y travel parallel to this door plane normal.
        _registry_with_door(position=(5.0, 11.0, 0.0), facing=0.0),
    )
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    assert "door_opened" in [event.kind for event in events]
    assert "room_transition" not in [event.kind for event in events]


def test_crossing_requires_a_different_walkmesh_component() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        _registry_with_door(position=(5.0, 5.0, 0.0)),
        spawn=(5.0, 3.0, 0.0),
    )
    door = session.door_states()[0]
    door.is_open = True
    assert session._try_room_transition((0.0, 1.0)) is False


def test_upper_floor_door_does_not_open_or_cross_for_lower_floor_player() -> None:
    _configure_native_python_roots()
    session = _session(
        _two_island_wok(gap=2.0),
        # Same XY doorway as the lower islands, but on a stacked floor only
        # 1.5 metres above it (still outside the derived collision/step reach).
        _registry_with_door(position=(5.0, 11.0, 1.5)),
    )
    events = _walk(session, "forward", seconds=6.0, azimuth=-90.0)
    kinds = [event.kind for event in events]
    assert "door_opened" not in kinds
    assert "room_transition" not in kinds
    assert session.door_states()[0].is_open is False


def test_real_921srt_doors_open() -> None:
    _configure_native_python_roots()
    from src.core.modules.module_editor_controller import ModuleEditorController

    kmap = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\921srt\921srt.fixed.kmap")
    if not kmap.is_file():
        import pytest

        pytest.skip("921srt.fixed.kmap not present")
    controller = ModuleEditorController()
    controller.open_project(kmap)
    session = controller.create_map_studio_pie_session().session
    assert session is not None
    doors = session.door_states()
    assert len(doors) > 10  # 921srt has 33 doors
    # Walk toward the nearest door and confirm it opens.
    px, py, _ = session.state.position
    nearest = min(doors, key=lambda d: math.hypot(d.position[0] - px, d.position[1] - py))
    for _ in range(600):
        cx, cy, _ = session.state.position
        if math.hypot(nearest.position[0] - cx, nearest.position[1] - cy) < 1.5:
            break
        azimuth = math.degrees(math.atan2(-(nearest.position[1] - cy), -(nearest.position[0] - cx)))
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=azimuth, run=True)
        session.advance(1.0 / 30.0)
    assert any(d.is_open for d in session.door_states())
