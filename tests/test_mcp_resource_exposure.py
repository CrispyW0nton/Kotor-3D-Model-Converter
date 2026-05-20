from __future__ import annotations

import pathlib
import sys
import asyncio

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_mcp_exposes_concrete_resources_and_templates() -> None:
    from kotormcp import mcp_resources

    async def _load():
        return (
            await mcp_resources.list_resources(),
            await mcp_resources.list_resource_templates(),
        )

    resources, templates = asyncio.run(_load())

    assert any(row["uri"] == "kotor://docs/capabilities" for row in resources)
    assert any(
        row["uriTemplate"] == "kotor://k1/resource/{resref}.{ext}"
        for row in templates
    )
    assert any(
        row["uriTemplate"] == "kotor://ghostrigger/model/{resref}"
        for row in templates
    )
    assert all("{" not in row["uri"] for row in resources)
