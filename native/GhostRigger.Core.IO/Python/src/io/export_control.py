"""Shared cooperative-cancellation and sidecar-result contracts for exporters.

This module is owned by ``GhostRigger.Core.IO`` because cancellation checkpoints
and emitted-sidecar truth are format-writing contracts. The active converter
pipeline is package-local, so this file intentionally has no root ``src`` copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


class ExportCancelledError(RuntimeError):
    """Raised when a cooperative export cancellation is observed."""


def check_export_cancelled(is_cancelled: Callable[[], bool] | None) -> None:
    """Raise a stable internal exception when ``is_cancelled`` is set."""

    if callable(is_cancelled) and is_cancelled():
        raise ExportCancelledError("Export cancelled")


@dataclass(frozen=True)
class TextureSidecarResult:
    """Truthful outcome for textures referenced by one exported model."""

    requested_names: tuple[str, ...] = ()
    saved_files: tuple[str, ...] = ()
    missing_names: tuple[str, ...] = ()
    failed_names: tuple[str, ...] = ()

    @property
    def requested(self) -> int:
        return len(self.requested_names)

    @property
    def saved(self) -> int:
        return len(self.saved_files)

    @property
    def unavailable(self) -> int:
        return len(self.missing_names) + len(self.failed_names)


__all__ = [
    "ExportCancelledError",
    "TextureSidecarResult",
    "check_export_cancelled",
]
