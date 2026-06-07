"""Asset metadata helpers for GhostRigger Level Sequence files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sequence_serialization import load_sequence_file


@dataclass
class SequenceAssetInfo:
    path: str
    name: str
    duration: float
    frame_rate: float
    bindings: int
    tracks: int
    modified_date: str
    metadata: dict[str, Any]


def inspect_sequence_asset(path: str | Path) -> SequenceAssetInfo:
    source = Path(path)
    sequence = load_sequence_file(source)
    track_count = len(sequence.master_tracks) + sum(len(binding.tracks) for binding in sequence.bindings)
    try:
        modified = source.stat().st_mtime
    except OSError:
        modified = 0.0
    return SequenceAssetInfo(
        path=str(source),
        name=sequence.name,
        duration=sequence.duration_seconds,
        frame_rate=sequence.frame_rate,
        bindings=len(sequence.bindings),
        tracks=track_count,
        modified_date=str(int(modified)),
        metadata=dict(sequence.metadata),
    )
