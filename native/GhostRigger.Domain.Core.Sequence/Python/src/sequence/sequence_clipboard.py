"""Clipboard model for sequence key editing."""

from __future__ import annotations

from dataclasses import dataclass, field

from .sequence_keyframe import SequenceKeyframe


@dataclass
class SequenceClipboard:
    keys_by_track: dict[str, list[SequenceKeyframe]] = field(default_factory=dict)
    source_frame: int = 0

    def copy_selected(self, tracks) -> int:
        self.keys_by_track.clear()
        frames: list[int] = []
        for track in tracks:
            selected = [key.duplicate(selected=False) for key in track.selected_keyframes()]
            if selected:
                self.keys_by_track[track.track_id] = selected
                frames.extend(key.frame for key in selected)
        self.source_frame = min(frames) if frames else 0
        return sum(len(keys) for keys in self.keys_by_track.values())

    def paste(self, tracks, target_frame: int) -> int:
        by_id = {track.track_id: track for track in tracks}
        count = 0
        for track_id, keys in self.keys_by_track.items():
            track = by_id.get(track_id)
            if track is None:
                continue
            for key in keys:
                pasted = key.duplicate(frame_offset=int(target_frame) - int(self.source_frame), selected=True)
                track.add_keyframe(pasted.frame, pasted.value, pasted.interpolation, select=True)
                count += 1
        return count
