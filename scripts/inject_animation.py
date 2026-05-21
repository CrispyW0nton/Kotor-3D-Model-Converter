"""CLI for Sprint 3 reverse animation extraction/injection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
        writer_request = AuroraAnimationInjectionRequest(
            r3a_animation_json=result.retargeted_animation_json,
            target_mdl=args.target_mdl,
            target_mdx=args.target_mdx,
            animation_slot=args.slot,
            output_mdl=output_mdl,
            output_manifest=output_manifest,
            game=args.game.upper(),
            fps=result.fps,
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
