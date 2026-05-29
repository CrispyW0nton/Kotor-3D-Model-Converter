"""Command-line entry point for the ModernGL renderer facade."""

from __future__ import annotations

import logging
import sys
from typing import Sequence

from .benchmark import _benchmark
from .renderer import GpuRenderer


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "benchmark"
    if cmd == "benchmark":
        n = int(args[1]) if len(args) > 1 else 10_000
        print(f"Running triangle throughput benchmark (n_tris={n})...")
        r = _benchmark(n_tris=n, repeats=5)
        print(
            f"  GPU:  {r.get('gpu_ms')} ms/frame  →  {r.get('gpu_fps')} fps  "
            f"  ({r.get('gpu_tris_per_sec', 0):,} tris/sec)"
        )
        print(f"  CPU:  {r.get('cpu_ms')} ms/frame (estimated)  →  {r.get('cpu_fps')} fps")
        if r.get("gpu_fps") and r.get("cpu_fps"):
            speedup = r["gpu_fps"] / r["cpu_fps"]
            print(f"  Speedup: {speedup:.0f}×")
        return 0
    if cmd == "test":
        print("GpuRenderer smoke test...")
        gr = GpuRenderer()
        ok = gr._ensure_context()
        print(f"  GPU available: {ok}")
        if ok:
            print(f"  GL version: {gr._ctx.version_code}")
        gr.release()
        print("  PASS")
        return 0
    print(f"Unknown command: {cmd}. Use 'benchmark' or 'test'.")
    return 2


_main = main

__all__ = ("main", "_main")
