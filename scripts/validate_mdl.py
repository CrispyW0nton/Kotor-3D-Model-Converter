"""Validate a KOTOR MDL through the Ghost Rigger viewport renderer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.validation.capture_specs import CameraPreset, ViewportCaptureSpec
from src.core.validation.viewport_validator import ViewportValidator


def parse_frames(frames: str) -> list[int]:
    """Parse a comma-separated frame list."""

    parsed: list[int] = []
    for item in frames.split(","):
        item = item.strip()
        if item:
            parsed.append(int(item))
    if not parsed:
        raise argparse.ArgumentTypeError("frames must contain at least one integer")
    return parsed


def parse_resolution(value: str) -> tuple[int, int]:
    """Parse WIDTHxHEIGHT."""

    try:
        width_raw, height_raw = value.lower().split("x", 1)
        width = int(width_raw)
        height = int(height_raw)
    except Exception as exc:
        raise argparse.ArgumentTypeError("resolution must look like 512x512") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("resolution values must be positive")
    return width, height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate KOTOR MDL output via Ghost Rigger viewport"
    )
    parser.add_argument("--mdl", required=True, type=Path, help="Path to MDL file")
    parser.add_argument("--mdx", type=Path, default=None, help="Optional MDX path")
    parser.add_argument(
        "--game",
        default="K1",
        choices=["K1", "K2", "k1", "k2"],
        help="Game version for binary parsing",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for captures and validation JSON",
    )
    parser.add_argument(
        "--frames",
        default="0",
        help="Comma-separated frame indices, default: 0",
    )
    parser.add_argument(
        "--animation",
        default=None,
        help="Animation name to evaluate, default: bind pose",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="Optional reference capture directory for SSIM comparison",
    )
    parser.add_argument(
        "--ssim-threshold",
        type=float,
        default=0.85,
        help="Minimum acceptable SSIM when reference captures are provided",
    )
    parser.add_argument(
        "--resolution",
        default="512x512",
        help="Capture resolution as WIDTHxHEIGHT, default: 512x512",
    )
    parser.add_argument(
        "--camera",
        default=CameraPreset.FRONT_ORTHO.value,
        choices=[preset.value for preset in CameraPreset],
        help="Camera preset",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frame-to-time conversion FPS for animation captures",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    spec = ViewportCaptureSpec(
        frames=parse_frames(args.frames),
        animation_name=args.animation,
        resolution=parse_resolution(args.resolution),
        camera_preset=CameraPreset(args.camera),
        fps=args.fps,
    )

    validator = ViewportValidator(output_dir=args.output)
    result = validator.validate_mdl(
        mdl_path=args.mdl,
        mdx_path=args.mdx,
        game=args.game.upper(),
        capture_spec=spec,
        reference_captures_dir=args.reference,
        ssim_threshold=args.ssim_threshold,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output / f"{args.mdl.stem}_validation.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2)

    status = "SUCCESS" if result.success else "FAILED"
    print("=" * 60)
    print("Ghost Rigger Viewport Validation Report")
    print("=" * 60)
    print(f"MDL: {args.mdl}")
    print(f"SHA-256: {result.mdl_sha256}")
    print(f"Status: {status}")
    print(f"Nodes: {result.node_count}, meshes: {result.mesh_count}")
    print(f"Animations: {result.animation_count}")
    if args.animation:
        print(f"Animation: {args.animation}")
    print(f"Captures: {len(result.captures)}")
    print(f"Render time: {result.total_render_time_ms:.1f} ms")

    if result.ssim_scores:
        print("SSIM scores:")
        for frame, score in sorted(result.ssim_scores.items()):
            print(f"  Frame {frame}: {score:.4f}")
        trust = result.trust_level.value if result.trust_level else "n/a"
        print(f"Trust level: {trust}")

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"  - {error}")

    print(f"Manifest: {manifest_path}")
    print("=" * 60)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
