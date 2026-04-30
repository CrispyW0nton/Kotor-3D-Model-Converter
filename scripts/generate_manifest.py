"""Generate the complete K1/K2 MDL manifest through paged KotorMCP tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KOTORMCP_ROOT = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\KotorMCP")
PYKOTOR_ROOT = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\PyKotor")

PYTHONPATHS = [
    KOTORMCP_ROOT / "src",
    PYKOTOR_ROOT / "Libraries" / "PyKotor" / "src",
    PYKOTOR_ROOT / "Libraries" / "PyKotorGL" / "src",
    PYKOTOR_ROOT / "Libraries" / "Utility" / "src",
    ROOT,
]
for path in PYTHONPATHS:
    sys.path.insert(0, str(path))

os.environ.setdefault("K1_PATH", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
os.environ.setdefault(
    "K2_PATH",
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
)

from kotormcp.tools.discovery import handle_list_resources  # noqa: E402
from kotormcp.tools.installation import handle_load_installation  # noqa: E402


def _result_json(result: Any) -> dict[str, Any]:
    text = result.content[0].text
    payload = json.loads(text)
    if payload.get("truncated"):
        raise RuntimeError("MCP response was truncated; reduce page size or filters")
    return payload


async def _call_load_installation(game: str) -> dict[str, Any]:
    return _result_json(await handle_load_installation({"game": game}))


async def _call_list_resources(game: str, *, offset: int, limit: int) -> dict[str, Any]:
    return _result_json(
        await handle_list_resources(
            {
                "game": game,
                "location": "all",
                "resourceTypes": ["mdl"],
                "offset": offset,
                "limit": limit,
            }
        )
    )


async def enumerate_mdl_resrefs(game: str, *, limit: int) -> list[str]:
    """Enumerate every MDL resource for one game using paged KotorMCP results."""
    loaded = await _call_load_installation(game)
    print(f"{game}: loaded {loaded['path']}")

    seen: set[str] = set()
    offset = 0
    raw_count = 0

    while True:
        page = await _call_list_resources(game, offset=offset, limit=limit)
        items = page["items"]
        raw_count += len(items)

        for item in items:
            resref = str(item.get("resref") or item.get("resname") or item.get("resource") or "").strip()
            if resref:
                seen.add(resref.lower())

        print(
            f"{game}: page offset={page['offset']} count={len(items)} "
            f"unique={len(seen)} next={page['next_offset']}"
        )

        next_offset = page.get("next_offset")
        if next_offset is None:
            break
        offset = int(next_offset)

    print(f"{game}: raw MDL rows={raw_count} unique resrefs={len(seen)}")
    return sorted(seen)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "exports" / "scan_manifest.json",
        help="Manifest output path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="KotorMCP listResources page size; 50 avoids response truncation, API maximum is 500",
    )
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 500:
        raise SystemExit("--limit must be between 1 and 500")

    k1_models = await enumerate_mdl_resrefs("k1", limit=args.limit)
    k2_models = await enumerate_mdl_resrefs("k2", limit=args.limit)

    manifest = {
        "generated": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "k1": {"count": len(k1_models), "models": k1_models},
        "k2": {"count": len(k2_models), "models": k2_models},
        "total": len(k1_models) + len(k2_models),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"K1={manifest['k1']['count']} K2={manifest['k2']['count']} total={manifest['total']}")


if __name__ == "__main__":
    asyncio.run(main())
