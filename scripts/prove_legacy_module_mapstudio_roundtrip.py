"""Prove a repaired MOD survives Map Studio import/editable KMAP round-trip."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.core.assets.resource_manager import ResourceManager
from src.core.level.kmap_serializer import KMapSerializer
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
from src.core.modules.module_editor_controller import ModuleEditorController


@dataclass
class ProofResult:
    ok: bool = False
    game: str = ""
    module_path: str = ""
    kmap_path: str = ""
    import_ok: bool = False
    import_message: str = ""
    import_ms: float = 0.0
    conversion_ok: bool = False
    conversion_message: str = ""
    conversion_ms: float = 0.0
    room_count: int = 0
    editable_room_count: int = 0
    render_surface_count: int = 0
    render_face_count: int = 0
    walkmesh_face_count: int = 0
    reopened_room_count: int = 0
    reopened_editable_room_count: int = 0
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    exception: str = ""
    retail_game_tested: bool = False


def prove(module_path: Path, game: str, game_root: Path, kmap_path: Path) -> ProofResult:
    result = ProofResult(
        game=game,
        module_path=str(module_path),
        kmap_path=str(kmap_path),
    )
    try:
        if not module_path.is_file():
            raise FileNotFoundError(module_path)
        if not (game_root / "chitin.key").is_file():
            raise FileNotFoundError(f"Invalid {game} installation: {game_root}")
        manager = ResourceManager()
        configured = manager.set_k1_dir(str(game_root)) if game == "K1" else manager.set_k2_dir(str(game_root))
        if not configured:
            raise RuntimeError(f"ResourceManager could not index {game_root}")
        controller = ModuleEditorController()
        controller.new_project(name=module_path.stem.lower(), game=game)
        started = time.perf_counter()
        result.import_ok, result.import_message = controller.import_stock_module_from_rim(
            module_resref=module_path.stem,
            modules_dir=str(module_path.parent),
            game=game,
            resource_manager=manager,
        )
        result.import_ms = round((time.perf_counter() - started) * 1000.0, 3)
        if not result.import_ok:
            result.blocking_issues.append(result.import_message or "Map Studio import failed.")
            return result

        started = time.perf_counter()
        result.conversion_ok, result.conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(
            resource_manager=manager
        )
        result.conversion_ms = round((time.perf_counter() - started) * 1000.0, 3)
        authored = controller._load_authored_project_or_raise()
        result.room_count = len(authored.rooms)
        imported = [room for room in authored.rooms if isinstance(room.primitive, ImportedMeshRoomPrimitive)]
        result.editable_room_count = len(imported)
        result.render_surface_count = sum(len(room.primitive.surfaces) for room in imported)
        result.render_face_count = sum(
            len(surface.faces)
            for room in imported
            for surface in room.primitive.surfaces
        )
        result.walkmesh_face_count = sum(
            len(room.primitive.wok.faces)
            for room in imported
            if room.primitive.wok is not None
        )
        result.warnings.extend(str(note) for note in authored.notes)
        if not result.conversion_ok or len(imported) != len(authored.rooms):
            result.blocking_issues.append(
                result.conversion_message
                or f"Only {len(imported)}/{len(authored.rooms)} rooms became editable."
            )
            return result

        kmap_path.parent.mkdir(parents=True, exist_ok=True)
        controller.save_project(kmap_path)
        reopened = KMapSerializer.load(kmap_path)
        restored = authored_project_from_kmap_payload(
            reopened.extra_sections["authored_module"],
            fallback_name=module_path.stem,
            fallback_game=game,
        )
        result.reopened_room_count = len(restored.rooms)
        result.reopened_editable_room_count = sum(
            isinstance(room.primitive, ImportedMeshRoomPrimitive)
            for room in restored.rooms
        )
        if result.reopened_room_count != result.room_count:
            result.blocking_issues.append(
                f"KMAP room count changed from {result.room_count} to {result.reopened_room_count}."
            )
        if result.reopened_editable_room_count != result.editable_room_count:
            result.blocking_issues.append(
                "KMAP reopen did not preserve every editable imported room."
            )
        result.ok = not result.blocking_issues
        return result
    except Exception:
        result.exception = traceback.format_exc()
        result.blocking_issues.append(result.exception.splitlines()[-1] if result.exception else "Unknown proof failure")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=("K1", "K2"), required=True)
    parser.add_argument("--game-root", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--kmap", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = prove(
        Path(args.module).expanduser().resolve(),
        args.game,
        Path(args.game_root).expanduser().resolve(),
        Path(args.kmap).expanduser().resolve(),
    )
    report = Path(args.report).expanduser().resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
