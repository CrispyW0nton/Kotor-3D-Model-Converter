"""Generate baseline renders and compare current headless renders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qa_common import (
    EXPORTS,
    add_common_args,
    image_metrics,
    iter_models,
    load_ghostrigger_model,
    safe_name,
    write_json,
)


BASELINE_DIR = EXPORTS / "baseline_renders"
CURRENT_DIR = EXPORTS / "current_renders"
BASELINE_META = EXPORTS / "baseline_renders_metadata.json"
DIFF_REPORT = EXPORTS / "render_diff_report.json"

ANGLES = {
    "diagonal": (-45.0, 20.0),
    "front": (0.0, 0.0),
    "right": (90.0, 0.0),
    "top": (0.0, 89.0),
}


def _selected_angles(all_angles: bool) -> dict[str, tuple[float, float]]:
    return ANGLES if all_angles else {"diagonal": ANGLES["diagonal"]}


def _render_model(game: str, resref: str, angle: str, out_dir: Path) -> dict[str, Any]:
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    model = load_ghostrigger_model(game, resref)
    camera = ArcBallCamera()
    renderer = FrameRenderer(camera)
    renderer.show_texture = False
    renderer.show_bones = False
    renderer.set_model(model)

    azimuth, elevation = ANGLES[angle]
    image = renderer.render_still(512, 512, az_deg=azimuth, el_deg=elevation)
    if image is None:
        raise RuntimeError("headless renderer returned None")

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / safe_name(game, resref, angle)
    image.save(path)
    metrics = image_metrics(path)
    metrics.update({"game": game, "resref": resref, "angle": angle, "path": str(path)})
    return metrics


def _generate(args: argparse.Namespace) -> int:
    metadata: list[dict[str, Any]] = []
    angles = _selected_angles(args.all_angles)
    total_failures = 0

    for index, (game, resref) in enumerate(iter_models(args.game, args.limit), start=1):
        for angle in angles:
            try:
                metrics = _render_model(game, resref, angle, BASELINE_DIR)
                metadata.append(metrics)
                print(f"[{index}] baseline {game}:{resref}:{angle} pixels={metrics['non_black_pixels']}")
            except Exception as exc:
                total_failures += 1
                metadata.append({
                    "game": game,
                    "resref": resref,
                    "angle": angle,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                print(f"[{index}] baseline {game}:{resref}:{angle} ERROR {type(exc).__name__}: {exc}")

    payload = {
        "mode": "generate",
        "image_size": [512, 512],
        "angles": list(angles),
        "failures": total_failures,
        "images": metadata,
    }
    write_json(BASELINE_META, payload)
    print(f"Baseline metadata written: {BASELINE_META}")
    return 0 if total_failures == 0 else 1


def _pixel_diff_pct(current: Path, baseline: Path) -> float:
    import numpy as np
    from PIL import Image

    cur = np.asarray(Image.open(current).convert("RGB"), dtype=np.int16)
    base = np.asarray(Image.open(baseline).convert("RGB"), dtype=np.int16)
    if cur.shape != base.shape:
        return 100.0
    diff = np.any(np.abs(cur - base) > 20, axis=2)
    return float(diff.sum() * 100.0 / diff.size)


def _classify(diff_pct: float, baseline_metrics: dict[str, Any], current_metrics: dict[str, Any]) -> str:
    base_pixels = int(baseline_metrics.get("non_black_pixels", 0) or 0)
    cur_pixels = int(current_metrics.get("non_black_pixels", 0) or 0)
    base_area = max(1, int(baseline_metrics.get("bbox_area", 0) or 0))
    cur_area = int(current_metrics.get("bbox_area", 0) or 0)

    if cur_pixels < 100 and base_pixels > 1000:
        return "DISAPPEARED"
    if cur_area > base_area * 2:
        return "EXPLODED"
    if diff_pct > 15.0:
        return "REGRESSION"
    if diff_pct >= 5.0:
        return "MINOR"
    return "MATCH"


def _compare(args: argparse.Namespace) -> int:
    if not BASELINE_META.exists():
        raise FileNotFoundError(f"missing baseline metadata: {BASELINE_META}")

    baseline_payload = json.loads(BASELINE_META.read_text(encoding="utf-8"))
    baseline_rows = [
        row for row in baseline_payload.get("images", [])
        if "error" not in row and (args.game == "all" or row.get("game") == args.game)
    ]
    if args.limit is not None:
        baseline_rows = baseline_rows[:args.limit]

    results: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for index, row in enumerate(baseline_rows, start=1):
        game = row["game"]
        resref = row["resref"]
        angle = row["angle"]
        baseline_path = Path(row["path"])
        try:
            current = _render_model(game, resref, angle, CURRENT_DIR)
            current_path = Path(current["path"])
            diff_pct = _pixel_diff_pct(current_path, baseline_path)
            bbox_ratio = float(current.get("bbox_area", 0) or 0) / max(1.0, float(row.get("bbox_area", 0) or 0))
            brightness_delta = abs(float(current.get("mean_brightness", 0.0)) - float(row.get("mean_brightness", 0.0)))
            non_black_ratio = float(current.get("non_black_pixels", 0) or 0) / max(1.0, float(row.get("non_black_pixels", 0) or 0))
            classification = _classify(diff_pct, row, current)
            result = {
                "game": game,
                "resref": resref,
                "angle": angle,
                "category": classification,
                "pixel_diff_pct": diff_pct,
                "bbox_area_ratio": bbox_ratio,
                "brightness_delta": brightness_delta,
                "non_black_pixel_ratio": non_black_ratio,
                "baseline": row,
                "current": current,
            }
            print(f"[{index}] compare {game}:{resref}:{angle} {classification} diff={diff_pct:.2f}%")
        except Exception as exc:
            classification = "ERROR"
            result = {
                "game": game,
                "resref": resref,
                "angle": angle,
                "category": classification,
                "error": f"{type(exc).__name__}: {exc}",
                "baseline": row,
            }
            print(f"[{index}] compare {game}:{resref}:{angle} ERROR {type(exc).__name__}: {exc}")
        counts[classification] = counts.get(classification, 0) + 1
        results.append(result)

    payload = {"summary": counts, "results": results}
    write_json(DIFF_REPORT, payload)
    print(f"Render diff report written: {DIFF_REPORT}")
    print(" | ".join(f"{key}: {counts[key]}" for key in sorted(counts)))
    return 0 if not any(key in counts for key in ("ERROR", "REGRESSION", "EXPLODED", "DISAPPEARED")) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--compare", action="store_true")
    parser.add_argument("--all-angles", action="store_true", help="Render front/right/top/diagonal instead of diagonal only.")
    add_common_args(parser)
    args = parser.parse_args()

    if args.generate:
        return _generate(args)
    return _compare(args)


if __name__ == "__main__":
    raise SystemExit(main())
