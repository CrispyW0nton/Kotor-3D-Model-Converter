"""Human-in-the-loop review for render diff failures."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from qa_common import EXPORTS, write_json


DIFF_REPORT = EXPORTS / "render_diff_report.json"
VERDICTS = EXPORTS / "visual_review_verdicts.json"
REVIEW_CATEGORIES = {"REGRESSION", "EXPLODED", "DISAPPEARED", "ERROR"}


def _post_load_model(base_url: str, game: str, resref: str) -> None:
    body = json.dumps({"game": game, "resref": resref}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/load_model",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        response.read()


def _load_review_items(path: Path, include_minor: bool) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    categories = set(REVIEW_CATEGORIES)
    if include_minor:
        categories.add("MINOR")
    rows = payload.get("results", [])
    return [row for row in rows if row.get("category") in categories]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DIFF_REPORT)
    parser.add_argument("--output", type=Path, default=VERDICTS)
    parser.add_argument("--base-url", default="http://127.0.0.1:7001")
    parser.add_argument("--include-minor", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    items = _load_review_items(args.report, args.include_minor)
    verdicts: list[dict[str, Any]] = []
    print(f"Visual review queue: {len(items)} models")

    for index, item in enumerate(items, start=1):
        game = str(item.get("game", "k2"))
        resref = str(item.get("resref", ""))
        category = str(item.get("category", "UNKNOWN"))
        angle = str(item.get("angle", "diagonal"))
        if not resref:
            continue

        try:
            _post_load_model(args.base_url, game, resref)
            time.sleep(args.delay)
            load_error = ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            load_error = f"{type(exc).__name__}: {exc}"
            print(f"[{index}/{len(items)}] Could not load {game}:{resref}: {load_error}")

        while True:
            answer = input(
                f"[{index}/{len(items)}] Review: {game} {resref} {angle} — {category}. "
                "Press Y=OK, N=BUG, S=Skip: "
            ).strip().lower()
            if answer in {"y", "n", "s"}:
                break
            print("Please enter Y, N, or S.")

        verdict = {"y": "OK", "n": "BUG", "s": "SKIP"}[answer]
        verdicts.append({
            "game": game,
            "resref": resref,
            "angle": angle,
            "failure_type": category,
            "verdict": verdict,
            "load_error": load_error,
            "metrics": {
                "pixel_diff_pct": item.get("pixel_diff_pct"),
                "bbox_area_ratio": item.get("bbox_area_ratio"),
                "brightness_delta": item.get("brightness_delta"),
                "non_black_pixel_ratio": item.get("non_black_pixel_ratio"),
            },
        })
        write_json(args.output, {"verdicts": verdicts})

    write_json(args.output, {"verdicts": verdicts})
    bugs = sum(1 for item in verdicts if item["verdict"] == "BUG")
    print(f"Visual review complete: {len(verdicts)} reviewed, {bugs} marked BUG")
    return 0 if bugs == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

