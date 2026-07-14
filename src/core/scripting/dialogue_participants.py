"""Headless catalogue of real KOTOR dialogue participants.

Dialogue speaker/listener values are object tags, not ``appearance.2da`` row
labels.  This module deliberately keeps those concepts separate: placed
creatures and UTC blueprints establish which tags are selectable, while
``appearance.2da`` may only decorate those real records for the user.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable, Mapping


_MISSING_2DA_VALUE = "****"


@dataclass(frozen=True)
class DialogueParticipant:
    """One real or conventional dialogue participant tag."""

    tag: str
    appearance_id: str = ""
    body_model: str = ""
    head: str = ""
    race: str = ""
    source: str = ""
    template_resref: str = ""

    def as_row(self) -> dict[str, str]:
        return asdict(self)


def _value(record: object, *names: str) -> Any:
    if isinstance(record, Mapping):
        folded = {str(key).casefold(): value for key, value in record.items()}
        for name in names:
            if name.casefold() in folded:
                return folded[name.casefold()]
        return None
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return None


def _text(record: object, *names: str) -> str:
    value = _value(record, *names)
    if value is None:
        return ""
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            pass
    result = str(value if value is not None else "").strip()
    return "" if result == _MISSING_2DA_VALUE else result


def _payload(record: object) -> bytes:
    if isinstance(record, (bytes, bytearray, memoryview)):
        return bytes(record)
    value = _value(record, "utc_bytes", "blueprint_bytes", "payload", "data")
    return bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else b""


def _utc_identity(data: bytes) -> tuple[str, str]:
    if not data:
        return "", ""
    try:
        from pykotor.resource.formats.gff import read_gff

        root = read_gff(data).root
        tag = str(root.acquire("Tag", "") or "").strip()
        appearance = root.acquire("Appearance_Type", -1)
        appearance_id = "" if appearance is None or int(appearance) < 0 else str(int(appearance))
        return tag, appearance_id
    except Exception:
        return "", ""


def _appearance_decorations(data: bytes) -> dict[str, dict[str, str]]:
    """Return appearance metadata keyed only by row ID.

    Labels are intentionally not returned as participant candidates.  A label
    such as ``n_rodian`` describes an appearance row; it is not necessarily an
    instance tag present in the module.
    """

    if not data:
        return {}
    try:
        from src.core.scripting.data_authoring import TwoDADocument

        table = TwoDADocument.load(data)
    except Exception:
        return {}
    headers = {header.casefold(): header for header in table.headers}

    def cell(row: Mapping[str, str], *names: str) -> str:
        for name in names:
            value = str(row.get(headers.get(name.casefold(), ""), "") or "").strip()
            if value and value != _MISSING_2DA_VALUE:
                return value
        return ""

    result: dict[str, dict[str, str]] = {}
    for index, appearance_id in enumerate(table.labels):
        row = table.row(index)
        result[str(appearance_id)] = {
            "body_model": cell(row, "modela", "modelb", "modeltype"),
            "head": cell(row, "normalhead", "headtexe", "headtexve"),
            "race": cell(row, "race", "racetex"),
        }
    return result


class DialogueParticipantCatalogService:
    """Build a participant chooser catalogue without importing Qt."""

    @staticmethod
    def _participant(record: object, *, default_source: str) -> DialogueParticipant | None:
        if isinstance(record, str):
            tag = record.strip()
            return DialogueParticipant(tag=tag, source=default_source) if tag else None
        utc_tag, utc_appearance = _utc_identity(_payload(record))
        tag = _text(record, "tag", "creature_tag", "participant_tag") or utc_tag
        if not tag:
            return None
        appearance_id = _text(
            record,
            "appearance_id",
            "appearance_type",
            "appearance",
            "Appearance_Type",
        ) or utc_appearance
        return DialogueParticipant(
            tag=tag,
            appearance_id=appearance_id,
            body_model=_text(record, "body_model", "model", "modela"),
            head=_text(record, "head", "normalhead", "head_model"),
            race=_text(record, "race"),
            source=_text(record, "source") or default_source,
            template_resref=_text(
                record,
                "template_resref",
                "utc_resref",
                "creature_source_template_resref",
                "source_template_resref",
            ),
        )

    def build(
        self,
        *,
        placed_creatures: Iterable[object] = (),
        utc_blueprints: Iterable[object] = (),
        dialogue_tags: Iterable[object] = (),
        appearance_2da: bytes = b"",
        include_conventions: bool = True,
    ) -> tuple[DialogueParticipant, ...]:
        """Return only real/contextual tags, decorated by target-game metadata."""

        participants: dict[str, DialogueParticipant] = {}

        def include(record: object, source: str) -> None:
            participant = self._participant(record, default_source=source)
            if participant is None:
                return
            key = participant.tag.casefold()
            previous = participants.get(key)
            if previous is None:
                participants[key] = participant
                return
            # Preserve the established tag spelling/order while filling any
            # information that another trustworthy source knows.
            participants[key] = replace(
                previous,
                appearance_id=previous.appearance_id or participant.appearance_id,
                body_model=previous.body_model or participant.body_model,
                head=previous.head or participant.head,
                race=previous.race or participant.race,
                source=previous.source or participant.source,
                template_resref=previous.template_resref or participant.template_resref,
            )

        for row in placed_creatures:
            include(row, "Current module")
        for row in utc_blueprints:
            include(row, "UTC blueprint")
        for row in dialogue_tags:
            include(row, "Current dialogue")
        if include_conventions:
            include({"tag": "OWNER", "source": "KOTOR dialogue convention"}, "")
            include({"tag": "PLAYER", "source": "KOTOR dialogue convention"}, "")

        decorations = _appearance_decorations(bytes(appearance_2da or b""))
        for key, participant in tuple(participants.items()):
            decoration = decorations.get(participant.appearance_id, {})
            if not decoration:
                continue
            participants[key] = replace(
                participant,
                body_model=participant.body_model or decoration.get("body_model", ""),
                head=participant.head or decoration.get("head", ""),
                race=participant.race or decoration.get("race", ""),
            )
        return tuple(participants.values())


__all__ = ["DialogueParticipant", "DialogueParticipantCatalogService"]
