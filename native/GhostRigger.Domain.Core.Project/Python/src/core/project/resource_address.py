"""Stable lightweight resource addresses for GhostRigger projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any


SUPPORTED_RESOURCE_ADDRESS_SCHEMES = {
    "game_resource",
    "module_resource",
    "override_resource",
    "project_resource",
    "local_file",
    "generated_output",
    "kmap_object",
    "kmax_object",
    "retarget_profile",
    "preview_result",
    "export_candidate",
}


def _clean_optional_text(value: Any, *, upper: bool = False, lower: bool = False) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if upper:
        return text.upper()
    if lower:
        return text.lower()
    return text


@dataclass(frozen=True)
class ResourceAddress:
    """JSON-friendly pointer to a game, project, generated, or local resource.

    A resource address stores identity and provenance only. It must not embed
    binary resource bytes or imported asset payloads.
    """

    scheme: str
    game: str | None = None
    module_id: str | None = None
    resref: str | None = None
    restype: str | None = None
    layer: str | None = None
    path: str | None = None
    object_id: str | None = None
    fragment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scheme", _clean_optional_text(self.scheme, lower=True) or "")
        object.__setattr__(self, "game", _clean_optional_text(self.game, lower=True))
        object.__setattr__(self, "module_id", _clean_optional_text(self.module_id, lower=True))
        object.__setattr__(self, "resref", _clean_optional_text(self.resref))
        restype = _clean_optional_text(self.restype, upper=True)
        if restype and restype.startswith("."):
            restype = restype[1:]
        object.__setattr__(self, "restype", restype)
        object.__setattr__(self, "layer", _clean_optional_text(self.layer, lower=True))
        object.__setattr__(self, "path", _clean_optional_text(self.path))
        object.__setattr__(self, "object_id", _clean_optional_text(self.object_id))
        object.__setattr__(self, "fragment", _clean_optional_text(self.fragment))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "game": self.game,
            "module_id": self.module_id,
            "resref": self.resref,
            "restype": self.restype,
            "layer": self.layer,
            "path": self.path,
            "object_id": self.object_id,
            "fragment": self.fragment,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | "ResourceAddress") -> "ResourceAddress":
        if isinstance(data, ResourceAddress):
            return data
        if not isinstance(data, dict):
            raise ValueError("ResourceAddress data must be a JSON object.")
        return cls(
            scheme=str(data.get("scheme") or ""),
            game=data.get("game"),
            module_id=data.get("module_id"),
            resref=data.get("resref"),
            restype=data.get("restype"),
            layer=data.get("layer"),
            path=data.get("path"),
            object_id=data.get("object_id"),
            fragment=data.get("fragment"),
            metadata=dict(data.get("metadata") or {}),
        )

    def stable_key(self) -> str:
        """Return a deterministic compact identity key for maps and diffs."""

        if self.scheme == "module_resource":
            return ":".join(
                str(part)
                for part in (
                    self.scheme,
                    self.game,
                    self.module_id,
                    self.layer,
                    self.restype,
                    self.resref,
                )
                if part
            )
        if self.scheme in {"game_resource", "override_resource", "project_resource", "generated_output"}:
            return ":".join(
                str(part)
                for part in (self.scheme, self.game, self.layer, self.restype, self.resref, self.path)
                if part
            )
        if self.scheme in {"kmap_object", "kmax_object"}:
            return ":".join(str(part) for part in (self.scheme, self.object_id, self.fragment) if part)
        if self.scheme == "local_file":
            return f"{self.scheme}:{self.path or ''}"
        return ":".join(
            str(part)
            for part in (
                self.scheme,
                self.game,
                self.module_id,
                self.layer,
                self.restype,
                self.resref,
                self.object_id,
                self.path,
                self.fragment,
            )
            if part
        )

    def display_name(self) -> str:
        """Return a short human-readable label for UI/log output."""

        if self.resref and self.restype:
            label = f"{self.resref}.{self.restype.lower()}"
            context = "/".join(part for part in (self.game, self.module_id, self.layer) if part)
            return f"{label} ({context})" if context else label
        if self.path:
            return PurePath(self.path).name or self.path
        if self.object_id:
            return self.object_id
        return self.scheme or "resource"
