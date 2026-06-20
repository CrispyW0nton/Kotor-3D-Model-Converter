"""Create the first from-scratch grdev01 Map Studio KMAP project.

The generated KMAP contains an `authored_module` section with the T2601 dev
room: one primitive rectangular room, generated walkmesh intent, player start,
and one test placeable. Use `stage_authored_module_from_kmap.py` next to build
the MOD package and manual proof files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATHS = (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Rendering/Python",
    ".",
)


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "map_studio" / "grdev01" / "grdev01.kmap",
        help="Output KMAP path.",
    )
    parser.add_argument("--module-root", default="grdev01", help="Module resref to store in the authored KMAP.")
    parser.add_argument("--game", default="K1", choices=("K1", "K2", "k1", "k2"), help="Target game.")
    parser.add_argument("--author", default="", help="Optional project author field.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing KMAP file.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _room_payload_summary(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rooms = []
    for room in payload.get("rooms", []) or []:
        primitive = dict(room.get("primitive") or {})
        rooms.append(
            {
                "room_resref": room.get("room_resref", ""),
                "primitive_type": primitive.get("type", ""),
                "width": primitive.get("width"),
                "depth": primitive.get("depth"),
                "wall_height": primitive.get("wall_height"),
                "floor_surface_id": primitive.get("floor_surface_id"),
                "texture": primitive.get("texture"),
            }
        )
    return rooms


def _summary(
    *,
    ok: bool,
    code: str,
    message: str,
    output_path: Path,
    module_root: str = "",
    game: str = "",
    readiness: Any = None,
    payload: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    blocking_issues: list[str] | None = None,
) -> dict[str, Any]:
    warnings = list(warnings or [])
    blocking_issues = list(blocking_issues or [])
    payload = dict(payload or {})
    readiness_blocking = list(getattr(readiness, "blocking_messages", ()) or ())
    readiness_warnings = list(getattr(readiness, "warnings", ()) or ())
    return {
        "ok": ok,
        "code": code,
        "message": message,
        "output_path": str(output_path),
        "module_root": module_root,
        "game": game,
        "authored_module_present": bool(payload),
        "capability_stage": getattr(readiness, "capability_stage", ""),
        "can_preview": bool(getattr(readiness, "can_preview", False)),
        "can_export_candidate": bool(getattr(readiness, "can_export_candidate", False)),
        "ready_for_game_test": bool(getattr(readiness, "ready_for_game_test", False)),
        "rooms": _room_payload_summary(payload),
        "warnings": warnings + readiness_warnings,
        "blocking_issues": blocking_issues + readiness_blocking,
        "next_command": f"python scripts/stage_authored_module_from_kmap.py --kmap \"{output_path}\" --output-dir \"{output_path.parent / 'stage'}\"",
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 authored KMAP seed: {status} ({summary['code']})")
    print(summary["message"])
    print(f"KMAP: {summary['output_path']}")
    print(f"Module root: {summary['module_root'] or '(not written)'}")
    print(f"Game: {summary['game'] or '(not written)'}")
    print(f"Capability stage: {summary['capability_stage'] or '(not evaluated)'}")
    for room in summary["rooms"]:
        print(
            f"- Room {room['room_resref']}: {room['primitive_type']} "
            f"{room['width']} x {room['depth']} x {room['wall_height']}, WOK surface {room['floor_surface_id']}"
        )
    if summary["warnings"]:
        print("")
        print("Warnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")
    if summary["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")
    if summary["ok"]:
        print("")
        print("Next:")
        print(summary["next_command"])


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_path = args.output
    if output_path.exists() and not args.overwrite:
        summary = _summary(
            ok=False,
            code="output_exists",
            message=f"KMAP already exists: {output_path}. Re-run with --overwrite to replace it.",
            output_path=output_path,
            blocking_issues=[f"KMAP already exists: {output_path}"],
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(summary)
        return 1

    _install_payload_paths()
    from src.core.level import new_kmap_project  # noqa: WPS433
    from src.core.level.kmap_serializer import KMapSerializer  # noqa: WPS433
    from src.core.modules.authored_module_kmap_bridge import (  # noqa: WPS433
        build_kmap_authored_module_readiness,
        create_dev_test_authored_module_payload,
    )

    module_root = str(args.module_root or "grdev01").strip() or "grdev01"
    game = str(args.game or "K1").upper()
    project = new_kmap_project(name=module_root, game=game, author=str(args.author or ""))
    payload = create_dev_test_authored_module_payload(module_root=module_root, game=game)
    project.extra_sections["authored_module"] = payload
    readiness = build_kmap_authored_module_readiness(project).readiness
    output_path.parent.mkdir(parents=True, exist_ok=True)
    KMapSerializer.save(project, output_path)
    summary = _summary(
        ok=readiness is not None and not bool(readiness.blocking_messages),
        code="created" if readiness is not None and not bool(readiness.blocking_messages) else "created_with_blockers",
        message=f"Created authored Map Studio KMAP: {output_path}",
        output_path=output_path,
        module_root=module_root,
        game=game,
        readiness=readiness,
        payload=payload,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
