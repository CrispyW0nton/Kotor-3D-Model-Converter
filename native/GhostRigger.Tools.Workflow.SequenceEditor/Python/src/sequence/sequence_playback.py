"""Frame-accurate sequence playback state."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .sequence_model import GhostRiggerLevelSequence


@dataclass
class PlaybackTick:
    frame: int
    wrapped: bool = False
    playing: bool = False


class SequencePlaybackController:
    SPEEDS = (0.25, 0.5, 1.0, 2.0)

    def __init__(self, sequence: GhostRiggerLevelSequence | None = None) -> None:
        self.sequence = sequence
        self.playing = False
        self.loop = False
        self.playback_speed = 1.0
        self.stop_returns_to_start = False
        self._last_wall = perf_counter()
        self._frame_accum = 0.0

    def set_sequence(self, sequence: GhostRiggerLevelSequence | None) -> None:
        self.sequence = sequence
        self.playing = False
        self._frame_accum = 0.0
        self._last_wall = perf_counter()

    def play(self) -> None:
        self.playing = True
        self._last_wall = perf_counter()

    def pause(self) -> None:
        self.playing = False

    def toggle_play(self) -> None:
        if self.playing:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        if self.sequence is not None and self.stop_returns_to_start:
            self.sequence.set_current_frame(self.sequence.playback_start_frame)
        self.playing = False
        self._frame_accum = 0.0

    def go_to_start(self) -> int:
        if self.sequence is None:
            return 0
        return self.sequence.set_current_frame(self.sequence.playback_start_frame)

    def go_to_end(self) -> int:
        if self.sequence is None:
            return 0
        return self.sequence.set_current_frame(self.sequence.playback_end_frame)

    def set_speed(self, speed: float) -> None:
        self.playback_speed = min(self.SPEEDS, key=lambda value: abs(float(value) - float(speed)))

    def tick(self) -> PlaybackTick:
        if self.sequence is None:
            return PlaybackTick(0, playing=False)
        if not self.playing:
            return PlaybackTick(self.sequence.current_frame, playing=False)
        now = perf_counter()
        elapsed = max(0.0, now - self._last_wall)
        self._last_wall = now
        self._frame_accum += elapsed * float(self.sequence.frame_rate) * float(self.playback_speed)
        step = int(self._frame_accum)
        if step <= 0:
            return PlaybackTick(self.sequence.current_frame, playing=True)
        self._frame_accum -= step
        next_frame = int(self.sequence.current_frame) + step
        wrapped = False
        if next_frame > self.sequence.playback_end_frame:
            if self.loop:
                span = max(1, self.sequence.playback_end_frame - self.sequence.playback_start_frame + 1)
                next_frame = self.sequence.playback_start_frame + ((next_frame - self.sequence.playback_start_frame) % span)
                wrapped = True
            else:
                next_frame = self.sequence.playback_end_frame
                self.pause()
        self.sequence.set_current_frame(next_frame)
        return PlaybackTick(self.sequence.current_frame, wrapped=wrapped, playing=self.playing)
