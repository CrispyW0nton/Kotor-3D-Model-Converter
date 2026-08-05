"""Render a complete Aurora animation as a Ghost Studio motion-proof video.

Unlike a sparse pose sheet, this utility samples the complete animation at a
fixed temporal cadence through the production viewport renderer.  It keeps the
individual PNG captures and writes a lossless-enough H.264 review video, so a
retarget can be audited both frame-by-frame and at normal playback speed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.animation.animation_engine import AnimationEngine  # noqa: E402
from src.core.validation.capture_specs import (  # noqa: E402
    CameraPreset,
    ViewportCaptureSpec,
)
from src.core.validation.viewport_validator import ViewportValidator  # noqa: E402


def _parse_resolution(value: str) -> tuple[int, int]:
    try:
        width_raw, height_raw = value.lower().split("x", 1)
        width, height = int(width_raw), int(height_raw)
    except Exception as exc:
        raise argparse.ArgumentTypeError(
            "resolution must look like 320x320"
        ) from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("resolution values must be positive")
    return width, height


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mdl", required=True, type=Path)
    parser.add_argument("--mdx", type=Path, default=None)
    parser.add_argument("--game", choices=("K1", "K2", "k1", "k2"), default="K2")
    parser.add_argument("--animation", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument(
        "--frame-step",
        type=int,
        default=2,
        help="Capture every Nth source frame; 2 at 30 fps yields 15 fps proof.",
    )
    parser.add_argument("--resolution", type=_parse_resolution, default=(320, 320))
    parser.add_argument(
        "--camera",
        choices=[preset.value for preset in CameraPreset],
        default=CameraPreset.THREE_QUARTER.value,
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser


def _animation_length(
    validator: ViewportValidator,
    mdl: Path,
    mdx: Path | None,
    game: str,
    animation_name: str,
) -> float:
    model = validator._load_mdl(mdl, mdx_path=mdx, game=game)
    entries = AnimationEngine(model).list_all_animations()
    for entry in entries:
        if str(entry.get("name", "")).lower() == animation_name.lower():
            return float(entry["length"])
    available = ", ".join(sorted(str(entry.get("name", "")) for entry in entries))
    raise ValueError(f"Animation {animation_name!r} not found. Available: {available}")


def _write_video(
    captures,
    *,
    output_dir: Path,
    frame_duration: float,
    ffmpeg: str,
    animation_name: str,
    camera: str,
) -> Path:
    executable = shutil.which(ffmpeg) if Path(ffmpeg).name == ffmpeg else ffmpeg
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")

    concat_path = output_dir / "frames.ffconcat"
    lines = ["ffconcat version 1.0"]
    for capture in captures:
        escaped = str(capture.png_path.resolve()).replace("'", "'\\''")
        lines.extend((f"file '{escaped}'", f"duration {frame_duration:.9f}"))
    escaped_last = str(captures[-1].png_path.resolve()).replace("'", "'\\''")
    lines.append(f"file '{escaped_last}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    video_path = output_dir / f"{animation_name}_{camera}_motion_proof.mp4"
    subprocess.run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ],
        check=True,
    )
    return video_path


def main() -> int:
    args = _parser().parse_args()
    if args.fps <= 0.0:
        raise SystemExit("--fps must be positive")
    if args.frame_step < 1:
        raise SystemExit("--frame-step must be positive")

    args.output.mkdir(parents=True, exist_ok=True)
    validator = ViewportValidator(output_dir=args.output)
    game = args.game.upper()
    length = _animation_length(
        validator,
        args.mdl,
        args.mdx,
        game,
        args.animation,
    )
    last_frame = max(0, int(round(length * args.fps)))
    frames = list(range(0, last_frame + 1, args.frame_step))
    if frames[-1] != last_frame:
        frames.append(last_frame)

    spec = ViewportCaptureSpec(
        frames=frames,
        animation_name=args.animation,
        resolution=args.resolution,
        camera_preset=CameraPreset(args.camera),
        fps=args.fps,
    )
    result = validator.validate_mdl(
        mdl_path=args.mdl,
        mdx_path=args.mdx,
        game=game,
        capture_spec=spec,
    )
    if not result.success:
        raise RuntimeError("; ".join(result.errors) or "viewport validation failed")
    if not result.captures:
        raise RuntimeError("viewport validation produced no captures")

    video_path = _write_video(
        result.captures,
        output_dir=args.output,
        frame_duration=args.frame_step / args.fps,
        ffmpeg=args.ffmpeg,
        animation_name=args.animation,
        camera=args.camera,
    )
    manifest = {
        "schema": 1,
        "mdl": str(args.mdl.resolve()),
        "mdx": str(args.mdx.resolve()) if args.mdx else None,
        "animation": args.animation,
        "animation_length_seconds": length,
        "source_fps": args.fps,
        "frame_step": args.frame_step,
        "capture_count": len(result.captures),
        "camera": args.camera,
        "resolution": list(args.resolution),
        "video": str(video_path.resolve()),
        "viewport_validation": result.to_dict(),
    }
    manifest_path = args.output / "motion_proof.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "animation": args.animation,
                "length_seconds": length,
                "capture_count": len(result.captures),
                "video": str(video_path),
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
