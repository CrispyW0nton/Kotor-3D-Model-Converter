"""Resource references for GhostRigger KMAX scenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.scene._native import native_scene


def _sanitize_resource_game(game: Any) -> str:
    dll = native_scene()
    if dll is not None:
        try:
            raw = dll.gr_scene_sanitize_resource_game(str(game or "").encode("utf-8"))
            if raw:
                return raw.decode("utf-8")
        except OSError:
            pass
    return str(game or "K1").upper()


@dataclass
class SceneResourceRef:
    """Lightweight pointer to a scene asset.

    KMAX stores references and editor overrides, not bulky MDL/MDX/TPC payloads.
    """

    resource_type: str = "model"
    game: str = "K1"
    resref: str = ""
    source_path: str = ""
    source_module: str = ""
    source_archive: str = ""
    original_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "game": self.game,
            "resref": self.resref,
            "source_path": self.source_path,
            "source_module": self.source_module,
            "source_archive": self.source_archive,
            "original_name": self.original_name,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SceneResourceRef":
        payload = data or {}
        return cls(
            resource_type=str(payload.get("resource_type") or "model"),
            game=_sanitize_resource_game(payload.get("game")),
            resref=str(payload.get("resref") or ""),
            source_path=str(payload.get("source_path") or ""),
            source_module=str(payload.get("source_module") or ""),
            source_archive=str(payload.get("source_archive") or ""),
            original_name=str(payload.get("original_name") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )
