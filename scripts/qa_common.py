"""Shared helpers for GhostRigger structural and render QA scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MCP_CONFIG_PATH = ROOT / ".cursor" / "mcp.json"
EXPORTS = ROOT / "exports"


def configure_paths() -> None:
    configured = [ROOT / "src", ROOT]
    if MCP_CONFIG_PATH.exists():
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        env = data.get("mcpServers", {}).get("kotormcp", {}).get("env", {})
        for key in ("K1_PATH", "K2_PATH"):
            if env.get(key):
                os.environ.setdefault(key, env[key])
        configured.extend(Path(p) for p in str(env.get("PYTHONPATH", "")).split(";") if p)
    for path in configured:
        text = str(path)
        if path.exists() and text not in sys.path:
            sys.path.insert(0, text)


def parse_mcp_json(result: Any) -> dict[str, Any]:
    content = getattr(result, "content", None) or []
    if not content:
        return {}
    text = getattr(content[0], "text", "{}")
    return json.loads(text)


def call_mcp_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    configure_paths()
    from kotormcp.tools import handle_tool

    return parse_mcp_json(asyncio.run(handle_tool(name, arguments)))


def list_mdl_resources(game: str, limit: int | None = None) -> list[str]:
    """Return MDL resrefs via KotorMCP listResources, paginating past its cap."""
    resources: list[str] = []
    offset = 0
    # KotorMCP truncates very large JSON responses, so keep pages small enough
    # that each CallToolResult remains parseable JSON.
    page_size = 25
    while True:
        payload = call_mcp_tool(
            "listResources",
            {
                "game": game,
                "resourceTypes": ["mdl"],
                "limit": page_size,
                "offset": offset,
            },
        )
        for item in payload.get("items", []):
            resref = str(item.get("resref", "")).strip().lower()
            if resref and resref not in resources:
                resources.append(resref)
                if limit is not None and len(resources) >= limit:
                    return resources
        if not payload.get("has_more"):
            return resources
        offset = int(payload.get("next_offset") or (offset + page_size))


def iter_models(game_arg: str = "all", limit: int | None = None):
    games = ("k1", "k2") if game_arg == "all" else (game_arg,)
    remaining = limit
    for game in games:
        game_limit = remaining if remaining is not None else None
        resrefs = list_mdl_resources(game, game_limit)
        for resref in resrefs:
            yield game, resref
        if remaining is not None:
            remaining -= len(resrefs)
            if remaining <= 0:
                break


def load_ghostrigger_model(game: str, resref: str):
    configure_paths()
    from kotormcp.tools.ghostrigger_tools import _resource_pair
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.geometry.model_data import GameVersion

    _, mdl, mdx = _resource_pair(game, resref)
    model = load_model_from_bytes(mdl.data, mdx.data if mdx is not None else b"")
    if model is None:
        raise ValueError(f"GhostRigger failed to load {game}:{resref}")
    model.game_version = GameVersion.K1 if game == "k1" else GameVersion.K2
    return model


def finite_vec(values: Any) -> bool:
    try:
        return all(math.isfinite(float(v)) for v in values)
    except Exception:
        return False


def safe_name(game: str, resref: str, angle: str) -> str:
    return f"{game}_{resref.lower()}_{angle}.png"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def image_metrics(path: Path) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    image = Image.open(path).convert("RGB")
    arr = np.asarray(image, dtype=np.float32)
    mask = np.any(arr > 10.0, axis=2)
    ys, xs = np.where(mask)
    non_black = int(mask.sum())
    if non_black:
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    else:
        bbox = [0, 0, 0, 0]
    pixels = arr.reshape(-1, 3)
    quant = (pixels // 32).astype("uint8")
    packed = quant[:, 0].astype("uint32") << 16 | quant[:, 1].astype("uint32") << 8 | quant[:, 2].astype("uint32")
    dominant = int(np.bincount(packed).argmax()) if packed.size else 0
    return {
        "width": int(image.width),
        "height": int(image.height),
        "non_black_pixels": non_black,
        "bbox": bbox,
        "bbox_area": max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1]),
        "mean_brightness": float(arr.mean()),
        "dominant_color_bucket": dominant,
    }


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--game", choices=["all", "k1", "k2"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="Limit models for smoke tests.")

