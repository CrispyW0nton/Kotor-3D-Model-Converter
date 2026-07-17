"""Repair a room WOK that is stored room-local but must ship module-space.

Odyssey room WOKs are serialized in module coordinates: the LYT offset places
render models, not collision (see ``scripts/audit_walkmesh_library.py``).  A
converted module can carry one room whose WOK vertices are still room-local
while its metadata claims module space; Ghost Studio's audits auto-correct the
offset for validation, but the retail engine does not, so the room's floor has
no collision under it in game.

This command translates the named room's WOK vertices by the LYT room offset
inside both the packaged MOD and the editable KMAP, sets the header position
vector to the donor/vanilla ``-room_position`` convention, rebuilds only the
derived tables, and proves indexed topology, surfaces, adjacency structure,
and transition records did not drift.  Every other resource byte is preserved.

The output is a structural repair; walking the room end to end in retail
KOTOR 2 remains the only real proof.
"""

from __future__ import annotations

import argparse
from dataclasses import replace as dataclass_replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from pykotor.extract.capsule import Capsule  # noqa: E402
from pykotor.resource.formats.erf import ERF, ERFType, write_erf  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

from src.core.level.kmap_serializer import KMapSerializer  # noqa: E402
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive  # noqa: E402
from src.core.modules.authored_module_kmap_bridge import (  # noqa: E402
    authored_project_from_kmap_payload,
)
from src.core.modules.module_editor_controller import ModuleEditorController  # noqa: E402
from src.core.modules.module_format import WOKData  # noqa: E402

from scripts.audit_walkmesh_library import audit_bwm_bytes, audit_mod  # noqa: E402

_SEMANTIC_KEYS = ("face_indices", "material_order", "transition_records")


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _translate_wok(wok: WOKData, offset: tuple[float, float, float]) -> WOKData:
    translated = WOKData(
        name=wok.name,
        verts=[
            (float(v[0]) + offset[0], float(v[1]) + offset[1], float(v[2]) + offset[2])
            for v in wok.verts
        ],
        faces=[dataclass_replace(face) for face in wok.faces],
        raw=None,
        relative_hook1=wok.relative_hook1,
        relative_hook2=wok.relative_hook2,
        absolute_hook1=wok.absolute_hook1,
        absolute_hook2=wok.absolute_hook2,
        position=(-offset[0], -offset[1], -offset[2]),
        adjacency_domain_count=wok.adjacency_domain_count,
    )
    return translated


def _prove_translation(room: str, before: bytes, after: bytes, offset: tuple[float, float, float]) -> dict[str, Any]:
    _parsed_before, before_audit = audit_bwm_bytes(before, source="before", resref=room)
    _parsed_after, after_audit = audit_bwm_bytes(after, source="after", resref=room)
    checks: dict[str, Any] = {
        "raw_structure_valid_after": bool(after_audit.get("raw_structure_valid")),
        "counts_match": dict(before_audit.get("counts", {})) == dict(after_audit.get("counts", {})),
        "surface_distribution_match": dict(before_audit.get("surface_distribution", {}))
        == dict(after_audit.get("surface_distribution", {})),
    }
    for key in _SEMANTIC_KEYS:
        checks[f"{key}_match"] = (
            before_audit.get("fingerprints", {}).get(key)
            == after_audit.get("fingerprints", {}).get(key)
        )
    before_wok = WOKData.from_bytes(before)
    after_wok = WOKData.from_bytes(after)
    max_delta = max(
        (
            max(
                abs(float(a[axis]) + offset[axis] - float(b[axis]))
                for axis in range(3)
            )
            for a, b in zip(before_wok.verts, after_wok.verts)
        ),
        default=0.0,
    )
    checks["max_translated_vertex_delta"] = max_delta
    checks["vertex_translation_exact"] = max_delta <= 1.0e-4
    failed = [name for name, value in checks.items() if value is False]
    if failed:
        raise RuntimeError(f"{room} WOK translation drifted: {failed}")
    return {
        "checks": checks,
        "before_sha256": _sha256_bytes(before),
        "after_sha256": _sha256_bytes(after),
        "offset": list(offset),
    }


def repair(
    module: str,
    room: str,
    mod_path: Path,
    kmap_path: Path,
    output_mod: Path,
) -> dict[str, Any]:
    room = room.strip().lower()

    project = authored_project_from_kmap_payload(
        KMapSerializer.load(kmap_path).extra_sections["authored_module"],
        fallback_name=module,
        fallback_game="K2",
    )
    target_index = None
    for index, spec in enumerate(project.rooms):
        if spec.normalised_resref() == room:
            target_index = index
            break
    if target_index is None:
        raise ValueError(f"{room} is not a room of {kmap_path.name}.")
    spec = project.rooms[target_index]
    primitive = spec.primitive
    if not isinstance(primitive, ImportedMeshRoomPrimitive) or primitive.wok is None:
        raise ValueError(f"{room} has no imported WOK to repair.")
    offset = tuple(float(v) for v in tuple(spec.position or (0.0, 0.0, 0.0))[:3])
    if max(abs(v) for v in offset) <= 1.0e-6:
        raise ValueError(f"{room} has a zero LYT offset; nothing to translate.")

    # 1. MOD resource repair.
    resources: dict[tuple[str, str], bytes] = {}
    for resource in Capsule(mod_path):
        key = (str(resource.resname()).strip().lower(), resource.restype().extension.lower())
        resources[key] = bytes(resource.data())
    source_wok_bytes = resources.get((room, "wok"))
    if source_wok_bytes is None:
        raise FileNotFoundError(f"{mod_path.name} has no {room}.wok resource.")
    translated = _translate_wok(WOKData.from_bytes(source_wok_bytes), offset)
    translated_bytes = translated.to_bytes()
    translation_proof = _prove_translation(room, source_wok_bytes, translated_bytes, offset)

    erf = ERF(ERFType.MOD)
    changed = 0
    for (resref, extension), data in sorted(resources.items()):
        if (resref, extension) == (room, "wok"):
            data = translated_bytes
            changed += 1
        erf.set_data(resref, ResourceType.from_extension(extension), data)
    if changed != 1:
        raise RuntimeError(f"Expected to replace exactly one WOK resource, replaced {changed}.")
    output_mod.parent.mkdir(parents=True, exist_ok=True)
    write_erf(erf, output_mod)

    # 2. KMAP repair: same translation, truthful module-space label.
    translated_primitive = dataclass_replace(
        primitive,
        wok=translated,
        metadata={
            **dict(primitive.metadata or {}),
            "wok_coordinate_space": "module",
            "wok_coordinate_space_repair": {
                "repaired_utc": datetime.now(timezone.utc).isoformat(),
                "applied_lyt_offset": list(offset),
                "reason": (
                    "Room WOK vertices were serialized room-local while Odyssey "
                    "ships room WOKs in module coordinates; the render floor had "
                    "no collision under it in game."
                ),
            },
        },
    )
    rooms = list(project.rooms)
    rooms[target_index] = dataclass_replace(spec, primitive=translated_primitive)
    controller = ModuleEditorController()
    controller.new_project(name=module, game="K2")
    controller._store_authored_project(dataclass_replace(project, rooms=tuple(rooms)))
    controller.save_project(kmap_path)

    # 3. Full MOD audit including entry containment and per-room round trips.
    mod_audit = audit_mod(output_mod, module=module, game="K2", roundtrip=True)
    if not mod_audit.get("audit_pass"):
        raise RuntimeError(
            f"Repaired MOD failed its walkmesh audit: {mod_audit.get('errors')}"
        )
    return {
        "module": module,
        "room": room,
        "lyt_offset": list(offset),
        "translation_proof": translation_proof,
        "source_mod": {"path": str(mod_path), "sha256": _sha256_bytes(mod_path.read_bytes())},
        "output_mod": {"path": str(output_mod), "sha256": _sha256_bytes(output_mod.read_bytes())},
        "kmap": {"path": str(kmap_path), "sha256": _sha256_bytes(kmap_path.read_bytes())},
        "mod_audit_pass": bool(mod_audit.get("audit_pass")),
        "entry_point": mod_audit.get("entry_point"),
        "retail_game_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--room", required=True)
    parser.add_argument("--mod", type=Path, required=True)
    parser.add_argument("--kmap", type=Path, required=True)
    parser.add_argument("--output-mod", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = repair(
        args.module.strip().lower(),
        args.room,
        args.mod.expanduser().resolve(),
        args.kmap.expanduser().resolve(),
        args.output_mod.expanduser().resolve(),
    )
    report["generated_utc"] = datetime.now(timezone.utc).isoformat()
    report_path = args.report.expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("module", "room", "lyt_offset", "mod_audit_pass")}, indent=2))
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
