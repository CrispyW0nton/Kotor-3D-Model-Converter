"""Safe standalone-file IO for the Odyssey GUI Editor."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pykotor.resource.formats.gff import read_gff

from src.core.tools.kotor_gui_document import KotorGuiDocument


@dataclass(frozen=True, slots=True)
class KotorGuiWriteResult:
    path: Path
    backup_path: Path | None
    byte_count: int


def load_kotor_gui_document(path: str | Path, *, game: str = "K2") -> KotorGuiDocument:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    return KotorGuiDocument.from_bytes(
        source.read_bytes(),
        game=game,
        resref=source.stem,
        source_kind="local_gui",
        source_path=source,
    )


def write_kotor_gui_document(document: KotorGuiDocument, path: str | Path) -> KotorGuiWriteResult:
    """Validate, stage, verify, back up, and atomically promote one GUI file."""

    if not isinstance(document, KotorGuiDocument):
        raise TypeError("GUI output requires KotorGuiDocument")
    blocking = tuple(issue for issue in document.validation_issues() if issue.severity == "error")
    if blocking:
        summary = "; ".join(issue.message for issue in blocking[:4])
        raise ValueError(f"GUI validation blocked save: {summary}")
    target = Path(path).expanduser().resolve()
    if target.suffix.casefold() != ".gui":
        target = target.with_suffix(".gui")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = document.to_bytes()
    read_gff(data)  # Verify the staged bytes are a readable GFF before touching output.

    backup: Path | None = None
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        read_gff(temporary)
        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup)
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    document.mark_saved(target)
    return KotorGuiWriteResult(target, backup, len(data))


__all__ = ["KotorGuiWriteResult", "load_kotor_gui_document", "write_kotor_gui_document"]
