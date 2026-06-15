"""WOK/walkmesh service for KMAP room associations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.level import KMapProject, LevelScene
from src.core.walkmesh import walkmesh_editor


def _import_module_format():
    try:
        from src.core.modules import module_format as mf  # type: ignore
    except ImportError:
        from core.modules import module_format as mf  # type: ignore
    return mf


@dataclass
class WalkmeshLoadResult:
    ok: bool = False
    walkmesh_ref: Any = None
    wok: Any = None
    workbench: Any = None
    message: str = ""
    code: str = "not_loaded"


class ModuleWalkmeshService:
    def load_wok_file(self, project: KMapProject, path: str | Path, *, room_id: str = "") -> WalkmeshLoadResult:
        source = Path(path)
        try:
            wok = _import_module_format().WOKData.from_file(str(source))
        except Exception as exc:
            return WalkmeshLoadResult(ok=False, message=f"Could not load WOK: {exc}", code="wok_error")
        face_types = {str(index): int(getattr(face, "surface", 0)) for index, face in enumerate(getattr(wok, "faces", []) or [])}
        walkmesh_ref = LevelScene(project).associate_walkmesh(room_id, source_path=str(source), face_types=face_types)
        workbench = walkmesh_editor.build_walkmesh_workbench(wok, room=source.stem)
        return WalkmeshLoadResult(ok=True, walkmesh_ref=walkmesh_ref, wok=wok, workbench=workbench, message=workbench.message, code="loaded")

    def paint_face(self, wok: Any, face_indices: int | list[int], surface_id: int, *, room: str = "") -> Any:
        return walkmesh_editor.set_walkmesh_face_surface(wok, face_indices, surface_id, room=room)

    def validate(self, wok: Any, *, room: str = "") -> Any:
        return walkmesh_editor.validate_walkmesh(wok, room=room)

    def generate_walls(self, wok: Any) -> Any:
        generator = _import_module_format().WalkmeshWallGenerator()
        return generator.generate(wok)

    def save_wok(self, wok: Any, path: str | Path) -> None:
        if hasattr(wok, "write_binary"):
            wok.write_binary(str(path))
            return
        if hasattr(wok, "to_bytes"):
            Path(path).write_bytes(wok.to_bytes())
            return
        raise ValueError("The selected walkmesh object cannot be serialized.")
