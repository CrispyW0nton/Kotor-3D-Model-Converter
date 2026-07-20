"""Runtime journal/quest state for Play-in-Editor.

KOTOR advances a quest by writing a numbered journal entry — either
``AddJournalQuestEntry(plot, state)`` from a script or a DLG node's
``Quest``/``QuestEntry`` fields when a line plays; the retail journal then shows
the highest entry a plot has reached. PIE runs no campaign and cannot mutate the
save's quest state, but it can *accumulate* the entries a play session touches
into a runtime-only quest log so a creator can watch the journal advance while
exercising a module (and seed it from a module's OnEnter journal writes).

Entries are monotonic: a higher entry supersedes a lower one for the same plot,
matching how the engine overwrites a plot's current state (it never regresses on
a normal advance). This is deliberately a preview log — never the campaign
journal, and it does not consult ``journal.2da`` for end/priority flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MapStudioPIEQuestState:
    """The current runtime entry reached for one quest plot tag."""

    quest_tag: str
    entry: int


def _parse_quest_value(value: Any) -> tuple[str, int] | None:
    """Parse a ``"plot:entry"`` journal event value into ``(tag, entry)``."""

    text = str(value or "").strip()
    if not text or ":" not in text:
        return None
    tag, _, raw = text.rpartition(":")
    tag = tag.strip()
    if not tag:
        return None
    try:
        return tag, int(str(raw).strip())
    except (TypeError, ValueError):
        return None


class MapStudioPIEJournalState:
    """A monotonic, runtime-only quest-log accumulator for a PIE session."""

    def __init__(self, *, seed: Iterable[Any] | None = None) -> None:
        self._entries: dict[str, int] = {}
        for item in tuple(seed or ()):
            tag, entry = self._coerce(item)
            if tag is not None:
                self.record(tag, entry)

    @staticmethod
    def _coerce(item: Any) -> tuple[str | None, int]:
        """Accept ``(tag, entry)`` pairs or ``"tag:entry"`` strings."""

        if isinstance(item, str):
            parsed = _parse_quest_value(item)
            return parsed if parsed is not None else (None, 0)
        try:
            tag, entry = item
        except (TypeError, ValueError):
            return None, 0
        tag = str(tag or "").strip()
        try:
            return (tag or None), int(entry)
        except (TypeError, ValueError):
            return None, 0

    def record(self, quest_tag: Any, entry: Any) -> bool:
        """Record a plot entry; returns True only if the log advanced.

        Monotonic: a lower or equal entry for a plot already reached is ignored.
        """

        tag = str(quest_tag or "").strip()
        if not tag:
            return False
        try:
            value = int(entry)
        except (TypeError, ValueError):
            return False
        current = self._entries.get(tag)
        if current is not None and value <= current:
            return False
        self._entries[tag] = value
        return True

    def record_value(self, value: Any) -> bool:
        """Record from a ``"plot:entry"`` journal event value."""

        parsed = _parse_quest_value(value)
        if parsed is None:
            return False
        return self.record(parsed[0], parsed[1])

    def entries(self) -> tuple[MapStudioPIEQuestState, ...]:
        """Current per-plot state, ordered by plot tag for stable display."""

        return tuple(
            MapStudioPIEQuestState(quest_tag=tag, entry=self._entries[tag])
            for tag in sorted(self._entries)
        )

    def as_dict(self) -> dict[str, int]:
        return dict(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)


__all__ = [
    "MapStudioPIEQuestState",
    "MapStudioPIEJournalState",
]
