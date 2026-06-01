"""Local filesystem implementation of the file-writer port."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.ports import FileWriterPort


@dataclass(frozen=True)
class LocalFileWriter(FileWriterPort):
    """Write files directly to the local filesystem."""

    def write_bytes(self, path: str | Path, data: bytes) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(data or b""))

    def write_text(self, path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(text), encoding=encoding)
