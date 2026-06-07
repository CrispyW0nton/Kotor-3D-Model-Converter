"""Texture/resource reference helpers for KMAP projects."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .kmap_model import KMapProject, TextureReference


class LevelTextureResolver:
    def __init__(self, search_paths: Iterable[str | Path] = ()) -> None:
        self.search_paths = [Path(path) for path in search_paths if str(path)]

    def resolve(self, resref: str) -> str:
        clean = str(resref or "").strip()
        if not clean:
            return ""
        stem = Path(clean).stem.lower()
        for base in self.search_paths:
            for ext in ("", ".tga", ".tpc", ".dds", ".png"):
                path = base / f"{stem}{ext}"
                if path.exists():
                    return str(path)
        return ""

    def track_texture(
        self,
        project: KMapProject,
        resref: str,
        *,
        source: str = "",
        include_in_export: bool = True,
        lightmap: str = "",
    ) -> TextureReference:
        existing = next((tex for tex in project.textures if tex.resref.lower() == resref.lower()), None)
        if existing is None:
            existing = TextureReference(resref=resref)
            project.textures.append(existing)
        existing.source = source or existing.source
        existing.path = existing.path or self.resolve(resref)
        existing.include_in_export = include_in_export
        existing.lightmap = lightmap or existing.lightmap
        project.mark_dirty()
        return existing
