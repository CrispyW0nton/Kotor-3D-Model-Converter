#!/usr/bin/env python
"""Run the GhostRigger -> Unity Malak main-menu smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.special.unity_malak_smoke import (  # noqa: E402
    DEFAULT_ASSET_PATH,
    DEFAULT_INSTANCE_NAME,
    DEFAULT_SCENE_PATH,
    run_malak_main_menu_smoke,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity-project", required=True, help="Absolute Unity project root")
    parser.add_argument("--host", default="127.0.0.1", help="Unity MCP Ghost host")
    parser.add_argument("--port", type=int, default=6400, help="Unity MCP Ghost port")
    parser.add_argument("--scene-path", default=DEFAULT_SCENE_PATH, help="Unity scene asset path")
    parser.add_argument("--asset-path", default=DEFAULT_ASSET_PATH, help="Fresh GhostRigger FBX asset path")
    parser.add_argument("--instance-name", default=DEFAULT_INSTANCE_NAME, help="Expected menu instance name")
    parser.add_argument("--output", help="Optional report JSON path")
    parser.add_argument("--screenshot-delay", type=float, default=1.0, help="Delay between screenshots")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_malak_main_menu_smoke(
        unity_project=Path(args.unity_project),
        host=args.host,
        port=args.port,
        scene_path=args.scene_path,
        asset_path=args.asset_path,
        instance_name=args.instance_name,
        output_path=Path(args.output) if args.output else None,
        screenshot_delay=args.screenshot_delay,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
