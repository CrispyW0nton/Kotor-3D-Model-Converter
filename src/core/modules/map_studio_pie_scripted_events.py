"""Scripted-event playback for Play-in-Editor cinematics.

Turns NCS virtual-machine command timelines into per-entity action queues the
PIE gameplay loop can play back — the editor-side counterpart of the retail
AI master processing ``CSWSObject`` action queues.

Evidence basis (clean-room Ghidra, K1 ``k1_win_gog_swkotor.exe``):
- ``ExecuteCommandMoveToObject`` @0053fb00: ActionMoveToObject pops
  ``(oMoveTo, bRun=0, fRange=1.0)``, resolves the TARGET's position at queue
  time, clamps range to the 0.5 use-range floor, and queues a MoveToPoint
  action (id 0x11) on the caller's FIFO action queue.
- ``ExecuteCommandDelayCommand`` @0052fe30 / ``ExecuteCommandAssignCommand``
  @0052e720: closures are AI events (delay ms / delay 0) whose saved state
  later runs via ``RunScriptSituation`` @005d4ad0 with OBJECT_SELF = target.
- ``ExecuteCommandDestroyObject`` @0052ff20: ``fDelay`` schedules the removal.
- ``ActionPauseConversation`` / ``ActionResumeConversation`` gate the dialogue
  while queued cinematic actions play out (the 207TEL Benok cantina exit).

Validated against the real 207TEL ``a_benokleave``: Benok walks to the GIT
waypoint ``wp_exitcantina``, thugs 207_matu/207_nahata follow at +0.2 s/+0.4 s,
all three despawn at +7 s, conversation pauses for the exit and then resumes.

Editor-side simulation only; retail KOTOR remains the in-game authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Retail creature locomotion rates (walk/run) used across PIE.
_WALK_SPEED = 1.75
_RUN_SPEED = 5.4
_MIN_ARRIVAL_RANGE = 0.5  # GetUseRange floor from ExecuteCommandMoveToObject


@dataclass
class PIEScriptedAction:
    """One playable action on an entity's queue (retail AddAction analogue)."""

    kind: str                      # "move_to" | "despawn" | "play_animation" | "wait"
    entity_tag: str
    target_position: tuple[float, float, float] | None = None
    target_tag: str = ""
    run: bool = False
    arrival_range: float = 1.0
    animation: int = -1
    duration: float = 0.0
    started: bool = False
    done: bool = False


@dataclass
class _ScheduledClosure:
    fire_at: float
    saved_state: Any
    bound_object_id: int


@dataclass
class PIEScriptedEventFrame:
    """What changed during one advance() — the PIE tick consumes this."""

    started_actions: list[PIEScriptedAction] = field(default_factory=list)
    despawned_tags: list[str] = field(default_factory=list)
    conversation_paused: bool = False
    events: list[str] = field(default_factory=list)


class MapStudioPIEScriptedEventRuntime:
    """Plays VM command timelines through per-entity FIFO action queues.

    ``position_of_tag`` resolves an object tag (creature, waypoint, door…) to
    its world position from the PIE entity registry/GIT — the analogue of the
    engine reading the target object's position at queue time.
    """

    def __init__(
        self,
        *,
        game: str = "K2",
        object_by_tag: Callable[[str, int], int | None] | None = None,
        tag_of_object: Callable[[int], str] | None = None,
        position_of_tag: Callable[[str], tuple[float, float, float] | None] | None = None,
    ) -> None:
        self.game = str(game or "K2").strip().upper()
        self._object_by_tag = object_by_tag
        self._tag_of_object = tag_of_object
        self._position_of_tag = position_of_tag
        self._queues: dict[str, list[PIEScriptedAction]] = {}
        self._closures: list[_ScheduledClosure] = []
        self._despawns: list[tuple[float, str]] = []
        self._time = 0.0
        self._conversation_pause_depth = 0
        self._vm: Any = None
        self._context: Any = None
        self.warnings: list[str] = []

    # -- script execution ----------------------------------------------------
    def run_script(self, ncs_bytes: bytes, *, self_tag: str = "") -> None:
        """Execute one compiled script; enqueue its commands and closures."""

        from .map_studio_pie_nwscript_vm import (
            MapStudioPIEScriptContext,
            NCSVirtualMachine,
        )
        import io

        try:
            from pykotor.resource.formats.ncs import NCSBinaryReader

            ncs = NCSBinaryReader(io.BytesIO(bytes(ncs_bytes))).load()
        except Exception as exc:
            self.warnings.append(f"scripted-event NCS decode failed: {exc}")
            return
        context = MapStudioPIEScriptContext(
            game=self.game,
            object_by_tag=self._object_by_tag,
            tag_of_object=self._tag_of_object,
        )
        if self_tag and callable(self._object_by_tag):
            resolved = self._object_by_tag(str(self_tag).strip().lower(), 0)
            if resolved is not None:
                context.self_object_id = int(resolved)
        machine = NCSVirtualMachine(list(getattr(ncs, "instructions", ()) or ()), context)
        self._vm = machine
        self._context = context
        consumed_from = len(context.result.commands)
        machine.run()
        self.warnings.extend(context.result.warnings)
        self._ingest_commands(context.result.commands[consumed_from:])

    def _ingest_commands(self, commands) -> None:
        for command in tuple(commands or ()):
            kind = str(command.kind)
            if command.saved_state is not None and kind in ("DelayCommand", "AssignCommand", "ActionDoCommand"):
                self._closures.append(
                    _ScheduledClosure(
                        fire_at=self._time + max(0.0, float(command.delay_seconds)),
                        saved_state=command.saved_state,
                        bound_object_id=int(command.saved_state.bound_object_id),
                    )
                )
                continue
            tag = str(command.object_tag or "")
            if kind in ("ActionMoveToObject", "ActionForceMoveToObject", "ActionMoveToLocation"):
                target_tag = ""
                position = None
                if command.args and callable(self._tag_of_object):
                    target_tag = str(self._tag_of_object(int(command.args[0])) or "")
                if not target_tag and command.args and self._context is not None:
                    target_tag = self._context.object_tag(int(command.args[0]))
                if target_tag and callable(self._position_of_tag):
                    position = self._position_of_tag(target_tag)
                run_flag = bool(int(command.args[1])) if len(command.args) > 1 else False
                arrival = max(_MIN_ARRIVAL_RANGE, float(command.args[2])) if len(command.args) > 2 else 1.0
                self._queues.setdefault(tag, []).append(
                    PIEScriptedAction(
                        kind="move_to",
                        entity_tag=tag,
                        target_position=position,
                        target_tag=target_tag,
                        run=run_flag,
                        arrival_range=arrival,
                    )
                )
            elif kind == "DestroyObject":
                self._despawns.append((self._time + max(0.0, float(command.delay_seconds)), tag))
            elif kind in ("ActionPlayAnimation", "PlayAnimation"):
                self._queues.setdefault(tag, []).append(
                    PIEScriptedAction(
                        kind="play_animation",
                        entity_tag=tag,
                        animation=int(command.args[0]) if command.args else -1,
                        duration=float(command.args[2]) if len(command.args) > 2 else 0.0,
                    )
                )
            elif kind == "ActionWait":
                self._queues.setdefault(tag, []).append(
                    PIEScriptedAction(
                        kind="wait",
                        entity_tag=tag,
                        duration=float(command.args[0]) if command.args else 0.0,
                    )
                )
            elif kind == "ActionPauseConversation":
                self._conversation_pause_depth += 1
            elif kind == "ActionResumeConversation":
                self._conversation_pause_depth = max(0, self._conversation_pause_depth - 1)

    # -- playback ------------------------------------------------------------
    @property
    def conversation_paused(self) -> bool:
        return self._conversation_pause_depth > 0

    def queue_for(self, tag: str) -> tuple[PIEScriptedAction, ...]:
        return tuple(self._queues.get(str(tag).strip().lower(), ()) or self._queues.get(str(tag), ()))

    def current_action(self, tag: str) -> PIEScriptedAction | None:
        queue = self._queues.get(str(tag), [])
        for action in queue:
            if not action.done:
                return action
        return None

    def complete_action(self, action: PIEScriptedAction) -> None:
        """The gameplay loop reports arrival/finish; FIFO advances (retail
        action-queue completion semantics)."""

        action.done = True

    def advance(self, delta_time: float) -> PIEScriptedEventFrame:
        """Fire due closures/despawns and surface newly-startable actions."""

        self._time += max(0.0, float(delta_time))
        frame = PIEScriptedEventFrame(conversation_paused=self.conversation_paused)

        due = [c for c in self._closures if c.fire_at <= self._time]
        if due and self._vm is not None:
            self._closures = [c for c in self._closures if c.fire_at > self._time]
            for closure in sorted(due, key=lambda c: c.fire_at):
                before = len(self._context.result.commands)
                self._vm.run_saved_state(closure.saved_state, self_object_id=closure.bound_object_id)
                self._ingest_commands(self._context.result.commands[before:])
                frame.events.append(f"closure fired at +{closure.fire_at:.1f}s")

        ready = [(t, tag) for (t, tag) in self._despawns if t <= self._time]
        if ready:
            self._despawns = [(t, tag) for (t, tag) in self._despawns if t > self._time]
            for _t, tag in ready:
                if tag:
                    frame.despawned_tags.append(tag)
                    self._queues.pop(tag, None)

        for tag, queue in self._queues.items():
            for action in queue:
                if action.done:
                    continue
                if not action.started:
                    action.started = True
                    frame.started_actions.append(action)
                break  # FIFO: only the head action runs
        frame.conversation_paused = self.conversation_paused
        return frame

    @staticmethod
    def movement_speed(action: PIEScriptedAction) -> float:
        return _RUN_SPEED if action.run else _WALK_SPEED


__all__ = [
    "MapStudioPIEScriptedEventRuntime",
    "PIEScriptedAction",
    "PIEScriptedEventFrame",
]
