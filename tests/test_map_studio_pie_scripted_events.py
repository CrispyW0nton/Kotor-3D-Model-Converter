"""Focused contracts for PIE scripted-event playback (cinematics engine).

Validates the per-entity FIFO action-queue runtime against the real 207TEL
Benok cantina exit: ``benok.dlg`` entry fires ``a_benokleave`` which pauses the
conversation, walks 207_benok to the GIT waypoint ``wp_exitcantina``, staggers
207_matu (+0.2 s) and 207_nahata (+0.4 s) behind him, despawns all three at
+7 s, and resumes the conversation. Ghidra grounding is documented in
``map_studio_pie_scripted_events.py``. Editor-side only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_207TEL_MOD = Path(
    r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio\Saved\VisibleProof"
    r"\2026-07-15_handoff_quality_pass\207tel_actual_source_fixture\Modules\207tel.mod"
)

_WAYPOINT_POSITIONS = {"wp_exitcantina": (4.46, -35.27, 0.0)}


def _runtime():
    from src.core.modules.map_studio_pie_scripted_events import (
        MapStudioPIEScriptedEventRuntime,
    )

    registry: dict[tuple[str, int], int] = {}
    tags: dict[int, str] = {}
    next_id = [1000]

    def object_by_tag(tag: str, nth: int):
        key = (tag, nth)
        if key not in registry:
            registry[key] = next_id[0]
            tags[next_id[0]] = tag
            next_id[0] += 1
        return registry[key]

    return MapStudioPIEScriptedEventRuntime(
        game="K2",
        object_by_tag=object_by_tag,
        tag_of_object=lambda oid: tags.get(int(oid), ""),
        position_of_tag=lambda tag: _WAYPOINT_POSITIONS.get(tag),
    )


@pytest.mark.skipif(not _207TEL_MOD.is_file(), reason="207TEL fixture module not present")
def test_benok_cantina_exit_plays_back_faithfully() -> None:
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.type import ResourceType as RT

    data = bytes(LazyCapsule(str(_207TEL_MOD)).resource("a_benokleave", RT.NCS))
    runtime = _runtime()
    runtime.run_script(data, self_tag="207_benok")
    assert not runtime.warnings, runtime.warnings

    # t=0: Benok's walk to the exit waypoint is queued and startable.
    frame0 = runtime.advance(0.0)
    started = {a.entity_tag: a for a in frame0.started_actions}
    assert "207_benok" in started
    benok_move = started["207_benok"]
    assert benok_move.kind == "move_to"
    assert benok_move.target_tag == "wp_exitcantina"
    assert benok_move.target_position == _WAYPOINT_POSITIONS["wp_exitcantina"]
    assert benok_move.run is False          # they walk out, cinematic pacing
    assert benok_move.arrival_range == pytest.approx(1.0)
    assert runtime.movement_speed(benok_move) == pytest.approx(1.75)

    # +0.25 s: Matu's staggered follow fires; +0.45 s: Nahata's.
    frame1 = runtime.advance(0.25)
    tags1 = {a.entity_tag for a in frame1.started_actions}
    assert "207_matu" in tags1
    frame2 = runtime.advance(0.2)
    tags2 = {a.entity_tag for a in frame2.started_actions}
    assert "207_nahata" in tags2
    matu = next(a for a in frame1.started_actions if a.entity_tag == "207_matu")
    assert matu.kind == "move_to" and matu.target_tag == "wp_exitcantina" and matu.run is False

    # +7 s: all three despawn (DestroyObject closures).
    frame3 = runtime.advance(6.6)
    despawned = set(frame3.despawned_tags)
    assert despawned == {"207_benok", "207_matu", "207_nahata"}
    assert runtime.current_action("207_benok") is None  # queue cleared


def test_action_queue_is_fifo_and_completion_advances() -> None:
    from src.core.modules.map_studio_pie_scripted_events import (
        MapStudioPIEScriptedEventRuntime,
        PIEScriptedAction,
    )

    runtime = MapStudioPIEScriptedEventRuntime(game="K2")
    first = PIEScriptedAction(kind="move_to", entity_tag="npc")
    second = PIEScriptedAction(kind="play_animation", entity_tag="npc", animation=38)
    runtime._queues["npc"] = [first, second]

    frame = runtime.advance(0.0)
    assert frame.started_actions == [first]
    # The head action must finish before the next starts (retail FIFO queues).
    frame = runtime.advance(0.1)
    assert frame.started_actions == []
    runtime.complete_action(first)
    frame = runtime.advance(0.1)
    assert frame.started_actions == [second]


def test_conversation_pause_depth_tracks_pause_resume() -> None:
    from types import SimpleNamespace

    from src.core.modules.map_studio_pie_scripted_events import (
        MapStudioPIEScriptedEventRuntime,
    )

    runtime = MapStudioPIEScriptedEventRuntime(game="K2")
    pause = SimpleNamespace(kind="ActionPauseConversation", object_tag="", args=(), delay_seconds=0.0, saved_state=None)
    resume = SimpleNamespace(kind="ActionResumeConversation", object_tag="", args=(), delay_seconds=0.0, saved_state=None)
    runtime._ingest_commands([pause])
    assert runtime.conversation_paused is True
    runtime._ingest_commands([resume])
    assert runtime.conversation_paused is False
