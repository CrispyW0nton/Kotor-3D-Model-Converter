"""KMAP project manager for create/open/save workflows."""

from __future__ import annotations

from pathlib import Path

from .kmap_model import KMapProject, new_kmap_project
from .kmap_serializer import KMapSerializer


class KMapProjectManager:
    def __init__(self, serializer: type[KMapSerializer] = KMapSerializer) -> None:
        self.serializer = serializer
        self.project: KMapProject = new_kmap_project()

    def new(self, name: str = "new_level", game: str = "K1", author: str = "") -> KMapProject:
        self.project = new_kmap_project(name=name, game=game, author=author)
        self.project.dirty = True
        return self.project

    def open(self, path: str | Path) -> KMapProject:
        self.project = self.serializer.load(path)
        return self.project

    def save(self) -> None:
        self.serializer.save(self.project)

    def save_as(self, path: str | Path) -> None:
        self.serializer.save(self.project, path)
