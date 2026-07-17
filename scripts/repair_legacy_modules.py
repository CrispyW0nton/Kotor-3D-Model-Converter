"""Build non-destructive K1/K2 candidates from recovered module bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.core.workflow.legacy_module_repair import (
    LegacyModuleCandidateRequest,
    LegacyRoomRepairRequest,
    build_legacy_module_candidate,
    repair_legacy_room_with_mdlops,
)
from src.core.workflow.legacy_texture_port import (
    LegacyTexturePortRequest,
    stage_vanilla_texture_dependencies,
)


def _room(args: argparse.Namespace) -> int:
    result = repair_legacy_room_with_mdlops(
        LegacyRoomRepairRequest(
            room_resref=args.room,
            source_mdl=args.mdl,
            source_mdx=args.mdx,
            source_wok=args.wok,
            target_game=args.game,
            output_dir=args.output,
            mdlops_executable=args.mdlops,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


def _module(args: argparse.Namespace) -> int:
    result = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref=args.module,
            target_game=args.game,
            repaired_rooms_dir=args.rooms,
            output_dir=args.output,
            source_mod=args.source_mod,
            source_are=args.are,
            source_git=args.git,
            source_ifo=args.ifo,
            source_lyt=args.lyt,
            source_vis=args.vis,
            source_pth=args.pth,
            extra_resource_paths=tuple(args.extra or ()),
            extra_resource_dirs=tuple(args.extra_dir or ()),
            visual_only_room_resrefs=tuple(args.visual_only_room or ()),
            regenerate_pth=bool(args.regenerate_pth),
            wok_coordinate_space=args.wok_space,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


def _textures(args: argparse.Namespace) -> int:
    result = stage_vanilla_texture_dependencies(
        LegacyTexturePortRequest(
            source_game_root=args.source_root,
            target_game_root=args.target_root,
            texture_resrefs=tuple(args.texture or ()),
            output_dir=args.output,
            overwrite=args.overwrite,
        )
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    room = subparsers.add_parser("room", help="Convert one MDL/MDX/WOK through MDLOps")
    room.add_argument("--room", required=True)
    room.add_argument("--game", choices=("K1", "K2"), required=True)
    room.add_argument("--mdl", required=True)
    room.add_argument("--mdx", default="")
    room.add_argument("--wok", default="")
    room.add_argument("--mdlops", required=True)
    room.add_argument("--output", required=True)
    room.add_argument("--overwrite", action="store_true")
    room.set_defaults(handler=_room)

    module = subparsers.add_parser("module", help="Package repaired rooms and preserved core metadata")
    module.add_argument("--module", required=True)
    module.add_argument("--game", choices=("K1", "K2"), required=True)
    module.add_argument("--rooms", required=True)
    module.add_argument("--output", required=True)
    module.add_argument("--source-mod", default="")
    module.add_argument("--are", default="")
    module.add_argument("--git", default="")
    module.add_argument("--ifo", default="")
    module.add_argument("--lyt", default="")
    module.add_argument("--vis", default="")
    module.add_argument("--pth", default="")
    module.add_argument("--extra", action="append", default=[])
    module.add_argument("--extra-dir", action="append", default=[])
    module.add_argument(
        "--visual-only-room",
        action="append",
        default=[],
        help="LYT room using the vanilla no-AABB/empty-WOK visual-partition contract; repeat as needed",
    )
    module.add_argument(
        "--regenerate-pth",
        action="store_true",
        help="Ignore any source PTH and rebuild pathing from the final repaired room WOK set",
    )
    module.add_argument("--wok-space", choices=("room_local", "module"), default="room_local")
    module.add_argument("--overwrite", action="store_true")
    module.set_defaults(handler=_module)

    textures = subparsers.add_parser(
        "textures",
        help="Stage exact donor-game TPCs that are absent from the target game",
    )
    textures.add_argument("--source-root", required=True)
    textures.add_argument("--target-root", required=True)
    textures.add_argument("--texture", action="append", required=True)
    textures.add_argument("--output", required=True)
    textures.add_argument("--overwrite", action="store_true")
    textures.set_defaults(handler=_textures)

    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
