"""JSON serialization for .grseq sequence assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sequence_model import GhostRiggerLevelSequence


SEQUENCE_EXTENSION = ".grseq"


class SequenceSerializationError(RuntimeError):
    pass


def sequence_to_json(sequence: GhostRiggerLevelSequence) -> str:
    return json.dumps(sequence.serialize(), indent=2, sort_keys=True) + "\n"


def sequence_from_json(text: str) -> GhostRiggerLevelSequence:
    try:
        payload: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SequenceSerializationError(f"Invalid .grseq JSON: {exc}") from exc
    return GhostRiggerLevelSequence.deserialize(payload)


def save_sequence_file(sequence: GhostRiggerLevelSequence, path: str | Path) -> Path:
    output = Path(path)
    if output.suffix.lower() != SEQUENCE_EXTENSION:
        output = output.with_suffix(SEQUENCE_EXTENSION)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        sequence.asset_path = str(output)
        sequence.touch()
        output.write_text(sequence_to_json(sequence), encoding="utf-8")
    except OSError as exc:
        raise SequenceSerializationError(f"Cannot save sequence: {exc}") from exc
    return output


def load_sequence_file(path: str | Path) -> GhostRiggerLevelSequence:
    source = Path(path)
    try:
        sequence = sequence_from_json(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SequenceSerializationError(f"Cannot load sequence: {exc}") from exc
    sequence.asset_path = str(source)
    return sequence
