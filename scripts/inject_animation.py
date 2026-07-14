"""CLI for Sprint 3 reverse animation extraction/injection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for python_root in reversed(_python_roots(ROOT)):
    python_root_text = str(python_root)
    if python_root_text not in sys.path:
        sys.path.insert(0, python_root_text)

from src.core.retargeting.animation_injector import (
    AnimationInjectionRequest,
    AnimationInjector,
)
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)
from src.core.retargeting.reverse_renamer import DEFAULT_REVERSE_RENAME_MAP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract UE5 animation for Aurora injection")
    parser.add_argument("--source-fbx", required=True, type=Path)
    parser.add_argument("--target-mdl", required=True, type=Path)
    parser.add_argument("--target-mdx", type=Path, default=None)
    parser.add_argument("--slot", default="victory")
    parser.add_argument("--rename-map", type=Path, default=DEFAULT_REVERSE_RENAME_MAP)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blender", type=Path, default=None)
    parser.add_argument("--action", default="")
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--game", default="K1", choices=["K1", "K2", "k1", "k2"])
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=None,
        help=(
            "Optional KOTOR installation used to resolve inherited animation slots through the target model's "
            "supermodel chain. Supply this when writing an override onto a model whose slot is not local."
        ),
    )
    parser.add_argument(
        "--source-reference-mode",
        default="hybrid_limb_source_rest",
        choices=["hybrid_limb_source_rest", "source_rest", "clip_frame_zero"],
        help=(
            "Reference pose for R3.B motion deltas. Use hybrid_limb_source_rest for authored UE idle poses; "
            "source_rest applies bind-pose deltas to every mapped node; "
            "clip_frame_zero preserves the legacy frame-0-as-zero behavior."
        ),
    )
    parser.add_argument(
        "--hybrid-limb-source-rest-weight",
        type=float,
        default=0.35,
        help="Blend weight from stable frame-0 limb solve toward FBX bind/rest limb solve in hybrid mode.",
    )
    parser.add_argument(
        "--write-mdl",
        action="store_true",
        help="Run R3.B after extraction and write a binary MDL/MDX with the injected animation",
    )
    parser.add_argument(
        "--output-mdl",
        type=Path,
        default=None,
        help="Output MDL path for --write-mdl. Defaults to <output>/<target>__<slot>__r3b.mdl",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    request = AnimationInjectionRequest(
        source_fbx=args.source_fbx,
        target_mdl=args.target_mdl,
        target_mdx=args.target_mdx,
        target_slot=args.slot,
        rename_map_path=args.rename_map,
        output_dir=args.output,
        blender_executable=args.blender,
        action_name=args.action,
        frame_step=args.frame_step,
        game=args.game.upper(),
    )
    result = AnimationInjector().inject(request)
    print("=" * 60)
    print("Sprint 3 R3.A Animation Extraction")
    print("=" * 60)
    print(f"Status: {'PASS' if result.success else 'HALT'}")
    print(f"Phase: {result.phase}")
    print(f"Source FBX: {result.source_fbx}")
    print(f"Target MDL: {result.target_mdl_original}")
    print(f"Target slot: {result.target_slot}")
    print(f"Frames: {result.frame_count} @ {result.fps:.3f} fps")
    print(f"Bones: source={result.source_bone_count}, target={result.target_bone_count}")
    print(
        "Adapter: "
        f"mapped={result.mapped_bone_count}, dropped={result.dropped_bone_count}, "
        f"collapsed={result.collapsed_bone_count}, unmapped={result.unmapped_bone_count}"
    )
    print(f"Extraction JSON: {result.extraction_json}")
    print(f"Retargeted JSON: {result.retargeted_animation_json}")
    print(f"Manifest: {result.manifest_path}")
    writer_result = None
    if result.success and args.write_mdl:
        if result.retargeted_animation_json is None:
            print("Errors:")
            print("  - R3.A did not produce a retargeted animation JSON")
            return 1
        output_mdl = args.output_mdl or (args.output / f"{args.target_mdl.stem}__{args.slot}__r3b.mdl")
        output_manifest = args.output / f"{args.target_mdl.stem}__{args.slot}__r3b_manifest.json"
        resource_manager = None
        if args.game_dir is not None:
            from src.core.assets.resource_manager import ResourceManager

            resource_manager = ResourceManager()
            configure_game = (
                resource_manager.set_k1_dir
                if args.game.upper() == "K1"
                else resource_manager.set_k2_dir
            )
            if not configure_game(str(args.game_dir)):
                print(f"Errors:\n  - Could not index {args.game.upper()} installation: {args.game_dir}")
                return 1
        writer_request = AuroraAnimationInjectionRequest(
            r3a_animation_json=result.retargeted_animation_json,
            target_mdl=args.target_mdl,
            target_mdx=args.target_mdx,
            animation_slot=args.slot,
            output_mdl=output_mdl,
            output_manifest=output_manifest,
            game=args.game.upper(),
            fps=result.fps,
            verify_roundtrip=True,
            source_reference_mode=args.source_reference_mode,
            hybrid_limb_source_rest_weight=args.hybrid_limb_source_rest_weight,
            resource_manager=resource_manager,
        )
        writer_result = AuroraAnimationWriter().inject(writer_request)
        print("-" * 60)
        print("Sprint 3 R3.B MDL Injection")
        print("-" * 60)
        print(f"Status: {'PASS' if writer_result.success else 'HALT'}")
        print(f"Operation: {writer_result.operation}")
        print(f"Output MDL: {writer_result.output_mdl}")
        print(f"Output MDX: {writer_result.output_mdx}")
        print(f"Output SHA-256: {writer_result.output_mdl_sha256}")
        print(f"Animation bones: {writer_result.bone_count_animated}")
        print(f"Manifest: {writer_result.manifest_path}")
        if writer_result.warnings:
            print("R3.B warnings:")
            for warning in writer_result.warnings:
                print(f"  - {warning}")
        if writer_result.errors:
            print("R3.B errors:")
            for error in writer_result.errors:
                print(f"  - {error}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")
    print("=" * 60)
    if result.manifest_path and result.manifest_path.exists():
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    if writer_result is not None and not writer_result.success:
        return 1
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
