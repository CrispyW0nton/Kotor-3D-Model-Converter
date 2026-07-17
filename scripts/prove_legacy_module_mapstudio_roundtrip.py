"""Prove a repaired MOD survives Map Studio import/editable KMAP round-trip."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from pykotor.extract.capsule import Capsule  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402
from src.core.assets.resource_manager import ResourceManager  # noqa: E402
from src.core.level.kmap_serializer import KMapSerializer  # noqa: E402
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive  # noqa: E402
from src.core.modules.authored_module_kmap_bridge import (  # noqa: E402
    authored_project_from_kmap_payload,
)
from src.core.modules.authored_module_project import compile_authored_room_spec  # noqa: E402
from src.core.modules.module_editor_controller import ModuleEditorController  # noqa: E402

from scripts.audit_walkmesh_library import audit_bwm_bytes  # noqa: E402

_WOK_FINGERPRINT_FIELDS = (
    "semantic",
    "face_indices",
    "material_order",
    "adjacency",
    "transition_records",
)


@dataclass
class ProofResult:
    ok: bool = False
    game: str = ""
    module_path: str = ""
    module_size: int = 0
    module_sha256: str = ""
    kmap_path: str = ""
    kmap_size: int = 0
    kmap_sha256: str = ""
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
    wok_parity_room_count: int = 0
    wok_parity_match_count: int = 0
    visual_only_empty_wok_rooms: list[str] = field(default_factory=list)
    wok_parity: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    exception: str = ""
    retail_game_tested: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _module_woks(module_path: Path) -> dict[str, bytes]:
    woks: dict[str, bytes] = {}
    for resource in Capsule(module_path):
        if resource.restype() != ResourceType.WOK:
            continue
        resref = str(resource.resname()).strip().lower()
        if resref in woks:
            raise ValueError(f"Module contains duplicate WOK resource {resref}.wok.")
        woks[resref] = bytes(resource.data())
    return woks


def _wok_parity_row(room_resref: str, source_bytes: bytes, compiled_bytes: bytes) -> dict[str, object]:
    _source_parsed, source = audit_bwm_bytes(
        source_bytes,
        source="source MOD",
        resref=room_resref,
    )
    _compiled_parsed, compiled = audit_bwm_bytes(
        compiled_bytes,
        source="reopened KMAP compile",
        resref=room_resref,
    )
    fingerprint_match = {
        field: source.get("fingerprints", {}).get(field)
        == compiled.get("fingerprints", {}).get(field)
        for field in _WOK_FINGERPRINT_FIELDS
    }
    header_vectors_match = source.get("header_vectors") == compiled.get("header_vectors")
    source_counts = dict(source.get("counts", {}) or {})
    compiled_counts = dict(compiled.get("counts", {}) or {})
    counts_match = source_counts == compiled_counts
    source_face_count = int(source_counts.get("faces", 0) or 0)
    canonical_empty_preserved = source_face_count != 0 or (
        len(source_bytes) == 136 and len(compiled_bytes) == 136
    )
    semantic_match = bool(
        all(fingerprint_match.values())
        and header_vectors_match
        and counts_match
        and canonical_empty_preserved
    )
    return {
        "room_resref": room_resref,
        "semantic_match": semantic_match,
        "fingerprint_match": fingerprint_match,
        "header_vectors_match": header_vectors_match,
        "counts_match": counts_match,
        "canonical_empty_preserved": canonical_empty_preserved,
        "source": {
            "byte_size": len(source_bytes),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
            "counts": source_counts,
            "fingerprints": dict(source.get("fingerprints", {}) or {}),
            "header_vectors": dict(source.get("header_vectors", {}) or {}),
        },
        "reopened_kmap_compile": {
            "byte_size": len(compiled_bytes),
            "sha256": hashlib.sha256(compiled_bytes).hexdigest(),
            "counts": compiled_counts,
            "fingerprints": dict(compiled.get("fingerprints", {}) or {}),
            "header_vectors": dict(compiled.get("header_vectors", {}) or {}),
        },
    }


def prove(module_path: Path, game: str, game_root: Path, kmap_path: Path) -> ProofResult:
    result = ProofResult(
        game=game,
        module_path=str(module_path),
        kmap_path=str(kmap_path),
    )
    try:
        if not module_path.is_file():
            raise FileNotFoundError(module_path)
        result.module_size = module_path.stat().st_size
        result.module_sha256 = _sha256(module_path)
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
        result.kmap_size = kmap_path.stat().st_size
        result.kmap_sha256 = _sha256(kmap_path)
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

        source_woks = _module_woks(module_path)
        restored_by_resref = {
            room.normalised_resref(): room
            for room in restored.rooms
        }
        result.wok_parity_room_count = len(restored_by_resref)
        for room_resref in sorted(restored_by_resref):
            source_wok = source_woks.get(room_resref)
            if source_wok is None:
                result.blocking_issues.append(
                    f"Source MOD has no {room_resref}.wok for KMAP parity proof."
                )
                continue
            geometry = compile_authored_room_spec(restored_by_resref[room_resref])
            compiled_wok = geometry.wok.to_bytes()
            row = _wok_parity_row(room_resref, source_wok, compiled_wok)
            result.wok_parity.append(row)
            if int(dict(row["source"]).get("counts", {}).get("faces", 0) or 0) == 0:
                result.visual_only_empty_wok_rooms.append(room_resref)
            if bool(row["semantic_match"]):
                result.wok_parity_match_count += 1
            else:
                result.blocking_issues.append(
                    f"KMAP compile changed {room_resref}.wok semantics from the source MOD."
                )
        if result.wok_parity_match_count != result.wok_parity_room_count:
            result.blocking_issues.append(
                "KMAP WOK parity is incomplete: "
                f"{result.wok_parity_match_count}/{result.wok_parity_room_count} room(s) match."
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
