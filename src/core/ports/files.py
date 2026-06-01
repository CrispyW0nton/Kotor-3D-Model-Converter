"""Filesystem write port used by export and save workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class FileWriterPort(Protocol):
    """Minimal file-output boundary for staged writers and external adapters."""

    def write_bytes(self, path: str | Path, data: bytes) -> None:
        ...

    def write_text(self, path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
        ...
