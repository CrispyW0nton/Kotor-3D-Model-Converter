"""Render manifest records for still-frame output."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RenderManifestEntry:
    path: str
    camera_id: str = ""
    camera_name: str = ""
    width: int = 0
    height: int = 0
    render_mode: str = ""
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def append_render_manifest(output_directory: str | Path, entry: RenderManifestEntry) -> str:
    path = Path(output_directory) / "render_manifest.json"
    rows = []
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                rows = []
        except Exception:
            rows = []
    rows.append(asdict(entry))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return str(path)
