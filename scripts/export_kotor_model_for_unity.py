"""Export a KotOR MDL/MDX resource into a Unity project asset folder.

This is a small bridge utility for the GhostRigger <-> Unity MCP workflow.
It deliberately uses GhostRigger's ResourceManager and exporters directly so
Codex/CI can reproduce the same asset transfer without opening the GUI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The application is split across native package payload roots rather than a
# single root ``src`` tree. Make the standalone CLI reproduce the same import
# layout as the MCP host so it works from a normal terminal without a custom
# PYTHONPATH.
from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _root.exists() and _text not in sys.path:
        sys.path.insert(0, _text)

from src.converters.mesh_converter import FBXExporter
from src.core.assets.resource_manager import ResourceManager
from src.core.export.unity_export_bridge import export_model_for_unity


class _ResourceTextureCache:
    def __init__(self, manager: ResourceManager, game: str) -> None:
        self._manager = manager
        self._game = game

    def get(self, texture_name: str):
        return self._manager.load_texture_image(texture_name, self._game, max_size=0)


def _normalise_game(value: str) -> str:
    value = value.strip().lower()
    if value in {"k1", "1", "swkotor"}:
        return "K1"
    if value in {"k2", "2", "tsl", "swkotor2"}:
        return "K2"
    raise argparse.ArgumentTypeError("game must be k1 or k2")


def export_model(args: argparse.Namespace) -> dict[str, Any]:
    unity_project = Path(args.unity_project)
    game_dir = Path(args.game_dir)

    manager = ResourceManager()
    indexed = manager.set_k1_dir(str(game_dir)) if args.game == "K1" else manager.set_k2_dir(str(game_dir))
    if not indexed:
        raise SystemExit(f"could not index {args.game} game directory: {game_dir}")

    model = manager.load_model_strict(args.resref, args.game)
    if model is None:
        raise SystemExit(f"could not load {args.resref} from {args.game}")

    if args.format != "fbx":
        raise SystemExit(f"unsupported format: {args.format}")

    base_skeleton_model = None
    supermodel = str(getattr(model, "supermodel", "") or "").strip()
    if supermodel and supermodel.lower() not in {"null", "none", "****"}:
        base_skeleton_model = manager.load_model_strict(supermodel, args.game)

    selected_animation_names = (
        ()
        if bool(getattr(args, "no_animations", False))
        else getattr(args, "animation", None)
    )
    from src.core.animation.fbx_animation_selection import (  # noqa: PLC0415
        prepare_fbx_animation_export_model,
    )

    model = prepare_fbx_animation_export_model(
        model,
        selected_animation_names,
        game=args.game,
        resource_manager=manager,
        base_skeleton_model=base_skeleton_model,
    )

    return export_model_for_unity(
        model,
        game=args.game,
        resref=args.resref,
        asset_name=args.output_name,
        unity_project=unity_project,
        asset_subdir=args.asset_subdir,
        extension=args.format,
        export_rigging=not args.no_rigging,
        exporter=lambda loaded_model, out_path, rigging: FBXExporter().export(
            loaded_model,
            str(out_path),
            tex_cache=_ResourceTextureCache(manager, args.game),
            export_rigging=rigging,
            base_skeleton_model=base_skeleton_model,
            compatibility_profile="unity",
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a KotOR model resource into a Unity Assets folder.",
    )
    parser.add_argument("--game", type=_normalise_game, required=True, help="k1 or k2")
    parser.add_argument("--game-dir", required=True, help="KotOR install directory containing chitin.key")
    parser.add_argument("--resref", required=True, help="Model resref, for example n_darthmalak")
    parser.add_argument("--output-name", help="Optional output filename stem; defaults to resref")
    parser.add_argument("--unity-project", required=True, help="Unity project root")
    parser.add_argument(
        "--asset-subdir",
        default="Assets/KotorImported/GhostRigger",
        help="Unity-project-relative asset folder",
    )
    parser.add_argument("--format", choices=["fbx"], default="fbx")
    parser.add_argument("--no-rigging", action="store_true", help="Do not write rigging sidecar JSON files")
    animation_group = parser.add_mutually_exclusive_group()
    animation_group.add_argument(
        "--animation",
        action="append",
        metavar="NAME",
        help=(
            "Embed this effective local or inherited animation set in the FBX. "
            "Repeat the option to select multiple sets. When omitted, the model's "
            "legacy local animation blocks are preserved."
        ),
    )
    animation_group.add_argument(
        "--no-animations",
        action="store_true",
        help="Export only the mesh and rig, with no embedded animation takes.",
    )
    return parser.parse_args()


def main() -> int:
    result = export_model(parse_args())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
