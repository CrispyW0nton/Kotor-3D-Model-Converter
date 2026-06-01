"""Texture decoder port for game-format and image adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.core.project.resource_address import ResourceAddress


@dataclass(frozen=True)
class TextureDecodeResult:
    """Renderer-neutral decoded texture payload."""

    width: int
    height: int
    pixels: bytes
    mode: str = "RGBA"
    source: ResourceAddress | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class TextureDecoder(Protocol):
    """Decode encoded texture bytes without tying callers to a concrete library."""

    def decode_texture(
        self,
        data: bytes,
        *,
        name: str | None = None,
        source: ResourceAddress | None = None,
    ) -> TextureDecodeResult:
        ...
