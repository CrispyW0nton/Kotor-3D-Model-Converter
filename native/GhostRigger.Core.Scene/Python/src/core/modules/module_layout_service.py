"""LYT layout service for KMAP room placement."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.level import KMapProject, LevelScene, LevelTransform, RoomInstance


def _import_module_format():
    try:
        from src.core.modules import module_format as mf  # type: ignore
    except ImportError:
        from core.modules import module_format as mf  # type: ignore
    return mf


@dataclass
class LayoutLoadResult:
    ok: bool = False
    rooms: list[RoomInstance] = field(default_factory=list)
    lyt: Any = None
    message: str = ""
    code: str = "not_loaded"


class ModuleLayoutService:
    def load_lyt_file(
        self,
        project: KMapProject,
        path: str | Path,
        *,
        module_id: str = "",
        source_module: str = "",
    ) -> LayoutLoadResult:
        mf = _import_module_format()
        source = Path(path)
        try:
            lyt = mf.LYTLayout.from_file(str(source))
        except Exception as exc:
            return LayoutLoadResult(ok=False, message=f"Could not load LYT: {exc}", code="lyt_error")
        return self.import_lyt(project, lyt, module_id=module_id, source_module=source_module or source.stem, source_path=str(source))

    def load_lyt_text(
        self,
        project: KMapProject,
        text: str,
        *,
        module_id: str = "",
        source_module: str = "",
        source_path: str = "",
    ) -> LayoutLoadResult:
        mf = _import_module_format()
        try:
            lyt = mf.LYTLayout.from_text(str(text or ""))
        except Exception as exc:
            return LayoutLoadResult(ok=False, message=f"Could not load LYT: {exc}", code="lyt_error")
        return self.import_lyt(
            project,
            lyt,
            module_id=module_id,
            source_module=source_module,
            source_path=source_path or f"{source_module}.lyt",
        )

    def load_lyt_bytes(
        self,
        project: KMapProject,
        data: bytes,
        *,
        module_id: str = "",
        source_module: str = "",
        source_path: str = "",
        encoding: str = "latin-1",
    ) -> LayoutLoadResult:
        try:
            text = bytes(data or b"").decode(encoding, errors="replace")
        except Exception as exc:
            return LayoutLoadResult(ok=False, message=f"Could not decode LYT: {exc}", code="lyt_error")
        return self.load_lyt_text(
            project,
            text,
            module_id=module_id,
            source_module=source_module,
            source_path=source_path,
        )

    def import_lyt(
        self,
        project: KMapProject,
        lyt: Any,
        *,
        module_id: str = "",
        source_module: str = "",
        source_path: str = "",
    ) -> LayoutLoadResult:
        scene = LevelScene(project)
        rooms: list[RoomInstance] = []
        module = project.find_module(module_id) if module_id else None
        for entry in getattr(lyt, "rooms", []) or []:
            model = str(getattr(entry, "model", "") or "").lower()
            if not model or model == "null":
                continue
            transform = LevelTransform(position=(float(getattr(entry, "x", 0.0)), float(getattr(entry, "y", 0.0)), float(getattr(entry, "z", 0.0))))
            room = scene.add_room(
                model,
                model_resref=model,
                source_module=source_module or (module.module_id if module else ""),
                module_id=module.module_id if module else "",
                transform=transform,
                lyt_entry={"source_path": source_path, "model": model},
            )
            rooms.append(room)
        if module and source_path:
            module.resources.append({"resref": Path(source_path).stem, "restype": "lyt", "source_path": source_path})
        return LayoutLoadResult(ok=True, rooms=rooms, lyt=lyt, message=f"Loaded {len(rooms)} LYT room(s).", code="loaded")

    def save_lyt_text(self, project: KMapProject, path: str | Path) -> None:
        mf = _import_module_format()
        layout = mf.LYTLayout()
        for room in project.rooms:
            x, y, z = room.transform.position
            layout.rooms.append(mf.LYTRoom(room.model_resref.lower(), float(x), float(y), float(z)))
        Path(path).write_text(layout.to_text(), encoding="latin-1")
