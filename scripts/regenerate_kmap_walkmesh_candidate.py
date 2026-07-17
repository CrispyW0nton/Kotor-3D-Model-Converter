"""Regenerate a converted map's walkmesh from render geometry, end to end.

For a KMAP whose imported rooms carry stale or donor-space WOKs, this command:

* runs Map Studio's census-derived auto walkmesh generator on every room
  (up-facing near-horizontal floors, walls/ceilings dropped, source WOK
  materials projected onto covered floor, floor-only serialized WOK);
* saves the regenerated KMAP in place (caller should back it up first);
* rebuilds every room MDL/MDX from the existing candidate MOD through the
  binary route so each embedded AABB mirrors its new room-local WOK;
* repackages the MOD with ``wok_coordinate_space="room_local"`` (vanilla
  shape: room-local WOK vertices placed by the LYT offset), preserved
  ARE/GIT/VIS, and a regenerated PTH;
* reruns the Map Studio roundtrip, K2 engine contract, and MOD<->KMAP
  walkmesh parity proofs.

The output is a structural candidate.  Walking and running through the whole
map must still be proven by a manual retail warp.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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

from src.core.level.kmap_serializer import KMapSerializer  # noqa: E402
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive  # noqa: E402
from src.core.modules.authored_module_kmap_bridge import (  # noqa: E402
    authored_project_from_kmap_payload,
)
from src.core.modules.authored_module_project import compile_authored_room_spec  # noqa: E402
from src.core.modules.module_editor_controller import ModuleEditorController  # noqa: E402
from src.core.modules.module_format import WALKABLE_IDS, WOKData  # noqa: E402
from src.core.workflow.legacy_module_repair import (  # noqa: E402
    LegacyModuleCandidateRequest,
    build_legacy_module_candidate,
)

from scripts.generate_legacy_room_walkmesh_candidates import (  # noqa: E402
    _artifact,
    _candidate_proofs,
    _compile_static_binary_room,
)


def _capsule_resources(path: Path) -> dict[tuple[str, str], bytes]:
    resources: dict[tuple[str, str], bytes] = {}
    for resource in Capsule(path):
        key = (str(resource.resname()).strip().lower(), resource.restype().extension.lower())
        resources[key] = bytes(resource.data())
    return resources


def _wok_summary(wok: WOKData | None) -> dict[str, Any] | None:
    if wok is None:
        return None
    walkable = sum(1 for face in wok.faces if int(face.surface) in WALKABLE_IDS)
    return {
        "vertices": len(wok.verts),
        "faces": len(wok.faces),
        "walkable_faces": walkable,
        "bounds": None
        if not wok.verts
        else [
            [round(min(v[a] for v in wok.verts), 2) for a in range(3)],
            [round(max(v[a] for v in wok.verts), 2) for a in range(3)],
        ],
    }


def _apply_reviewed_floor_intent(
    project: Any,
    floor_textures: tuple[str, ...],
    reason: str,
) -> tuple[Any, dict[str, Any]]:
    """Record the reviewed floor-surface allowlist on every imported room.

    The generator rightly refuses to guess floor intent from up-facing render
    triangles; this converts a human/texture review into the persisted
    ``walkmesh_generation_intent`` rows it requires. Slope and normal
    filtering still run afterwards.
    """

    from dataclasses import replace as _replace

    from src.core.modules.authored_imported_mesh import (
        prepare_imported_mesh_walkmesh_generation_intent,
    )

    wanted = {texture.strip().casefold() for texture in floor_textures if texture.strip()}
    rooms = list(project.rooms)
    review: dict[str, Any] = {}
    for index, room in enumerate(rooms):
        primitive = room.primitive
        if not isinstance(primitive, ImportedMeshRoomPrimitive):
            continue
        surface_faces = {
            surface_index: None
            for surface_index, surface in enumerate(primitive.surfaces)
            if str(surface.texture or "").strip().casefold() in wanted
        }
        if not surface_faces:
            raise RuntimeError(
                f"{room.normalised_resref()} has no surface matching the reviewed floor "
                f"textures {sorted(wanted)}; refusing to generate collision blindly."
            )
        reviewed = prepare_imported_mesh_walkmesh_generation_intent(
            primitive,
            surface_faces=surface_faces,
            reason=reason,
        )
        rooms[index] = _replace(room, primitive=reviewed)
        review[room.normalised_resref()] = sorted(
            str(primitive.surfaces[surface_index].name or "")
            for surface_index in surface_faces
        )
    return _replace(project, rooms=tuple(rooms)), review


def regenerate(
    module: str,
    kmap_path: Path,
    source_mod: Path,
    output_dir: Path,
    *,
    source_wok_policy: str = "preserve",
    disconnected_island_policy: str = "reject",
    floor_textures: tuple[str, ...] = (),
    floor_review_reason: str = "",
) -> dict[str, Any]:
    if not kmap_path.is_file():
        raise FileNotFoundError(kmap_path)
    if not source_mod.is_file():
        raise FileNotFoundError(source_mod)

    project_file = KMapSerializer.load(kmap_path)
    project = authored_project_from_kmap_payload(
        project_file.extra_sections["authored_module"],
        fallback_name=module,
        fallback_game="K2",
    )
    before = {
        room.normalised_resref(): _wok_summary(
            room.primitive.wok if isinstance(room.primitive, ImportedMeshRoomPrimitive) else None
        )
        for room in project.rooms
    }
    floor_review: dict[str, Any] = {}
    if floor_textures:
        project, floor_review = _apply_reviewed_floor_intent(
            project, floor_textures, floor_review_reason
        )

    controller = ModuleEditorController()
    controller.new_project(name=module, game="K2")
    controller._store_authored_project(project)
    ok, message = controller.auto_generate_map_studio_walkmesh(
        source_wok_policy=source_wok_policy,
        disconnected_island_policy=disconnected_island_policy,
    )
    if not ok:
        raise RuntimeError(f"Auto walkmesh generation refused the map: {message}")
    if source_wok_policy == "replace" and "Auto-generated walkmesh" not in message:
        raise RuntimeError(
            f"Replacement was requested but no room was regenerated: {message}"
        )
    controller.save_project(kmap_path)

    regenerated = controller._load_authored_project_or_raise()
    after: dict[str, Any] = {}
    room_positions: dict[str, tuple[float, float, float]] = {}
    room_dir = output_dir / "Rooms"
    source_rooms_dir = output_dir / "SourceRooms"
    room_dir.mkdir(parents=True, exist_ok=True)
    source_rooms_dir.mkdir(parents=True, exist_ok=True)
    resources = _capsule_resources(source_mod)

    room_compiles: list[dict[str, Any]] = []
    for room in regenerated.rooms:
        resref = room.normalised_resref()
        room_positions[resref] = tuple(float(v) for v in room.position)
        primitive = room.primitive
        if not isinstance(primitive, ImportedMeshRoomPrimitive) or primitive.wok is None:
            raise RuntimeError(f"{resref} did not receive a generated WOK.")
        after[resref] = {
            **(_wok_summary(primitive.wok) or {}),
            "wok_coordinate_space": dict(primitive.metadata or {}).get("wok_coordinate_space"),
        }
        geometry = compile_authored_room_spec(room)
        wok_path = room_dir / f"{resref}.generated.wok"
        wok_path.write_bytes(geometry.wok.to_bytes())

        for extension in ("mdl", "mdx"):
            data = resources.get((resref, extension))
            if data is None:
                raise FileNotFoundError(f"{module} source MOD is missing {resref}.{extension}")
            (source_rooms_dir / f"{resref}.{extension}").write_bytes(data)
        room_compiles.append(
            _compile_static_binary_room(
                room=resref,
                source_mdl_path=source_rooms_dir / f"{resref}.mdl",
                source_mdx_path=source_rooms_dir / f"{resref}.mdx",
                output_dir=room_dir,
                visual_only=False,
                external_wok_path=wok_path,
            )
        )

    build = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref=module,
            target_game="K2",
            repaired_rooms_dir=str(room_dir),
            output_dir=str(output_dir),
            source_mod=str(source_mod),
            regenerate_pth=True,
            wok_coordinate_space="room_local",
            overwrite=True,
        )
    )
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module=module, candidate_root=output_dir)

    module_path = output_dir / "Modules" / f"{module}.mod"
    kmap_proof_path = output_dir / "MapStudioProof" / f"{module}.kmap"
    return {
        "module": module,
        "generation_message": message,
        "floor_review": floor_review,
        "kmap": _artifact(kmap_path),
        "source_mod": _artifact(source_mod),
        "rooms_before": before,
        "rooms_after": after,
        "room_positions": room_positions,
        "room_compiles": room_compiles,
        "module_build": build.to_dict(),
        "proofs": proofs,
        "mod": _artifact(module_path) if module_path.is_file() else None,
        "proof_kmap": _artifact(kmap_proof_path) if kmap_proof_path.is_file() else None,
        "ready_for_manual_k2_test": bool(build.ok and proofs.get("ready_for_manual_k2_test")),
        "retail_game_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, help="Module resref, e.g. 921srt")
    parser.add_argument("--kmap", type=Path, required=True)
    parser.add_argument("--source-mod", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source-wok-policy",
        choices=("preserve", "replace"),
        default="preserve",
        help=(
            "'replace' destructively rebuilds each imported room WOK from its "
            "render geometry; requires an explicit user request because render "
            "triangles cannot distinguish pits/tables/roofs from floor intent."
        ),
    )
    parser.add_argument(
        "--island-policy",
        choices=("reject", "preserve"),
        default="reject",
        help="Disconnected walkable island policy for generated rooms.",
    )
    parser.add_argument(
        "--floor-texture",
        action="append",
        default=[],
        help=(
            "Reviewed floor texture; repeatable. Surfaces using these textures "
            "become the explicit walkmesh_generation_intent floor allowlist on "
            "every imported room."
        ),
    )
    parser.add_argument(
        "--floor-review-reason",
        default="",
        help="Written review reason recorded with the floor intent.",
    )
    args = parser.parse_args()
    if args.source_wok_policy == "replace" and not args.floor_texture:
        parser.error("--source-wok-policy replace requires at least one --floor-texture review.")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = regenerate(
        args.module.strip().lower(),
        args.kmap.expanduser().resolve(),
        args.source_mod.expanduser().resolve(),
        output_dir,
        source_wok_policy=args.source_wok_policy,
        disconnected_island_policy=args.island_policy,
        floor_textures=tuple(args.floor_texture),
        floor_review_reason=args.floor_review_reason,
    )
    report["source_wok_policy"] = args.source_wok_policy
    report["disconnected_island_policy"] = args.island_policy
    report["generated_utc"] = datetime.now(timezone.utc).isoformat()
    report_path = output_dir / f"{report['module']}.walkmesh-regen.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(report_path),
                "generation_message": report["generation_message"],
                "mod": (report.get("mod") or {}).get("path"),
                "ready_for_manual_k2_test": report["ready_for_manual_k2_test"],
                "retail_game_tested": False,
            },
            indent=2,
        )
    )
    return 0 if report["ready_for_manual_k2_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
