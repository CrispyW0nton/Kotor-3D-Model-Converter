from __future__ import annotations

import json
from pathlib import Path

import pytest


MANIFEST = Path(__file__).resolve().parents[1] / "exports" / "scan_manifest.json"


def _load_test_models() -> list[tuple[str, str]]:
    if not MANIFEST.exists():
        return []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [
        *[("k1", resref) for resref in data.get("k1", {}).get("models", [])],
        *[("k2", resref) for resref in data.get("k2", {}).get("models", [])],
    ]


ALL_MODELS = _load_test_models()


@pytest.mark.slow
@pytest.mark.skipif(not ALL_MODELS, reason="No manifest found")
@pytest.mark.parametrize("game,resref", ALL_MODELS, ids=[f"{g}:{r}" for g, r in ALL_MODELS])
def test_model_textures_found_and_loadable(game: str, resref: str, ghostrigger_tools) -> None:
    result = ghostrigger_tools.validate_textures(game, resref)
    missing = [name for name, info in result["textures"].items() if not info["found"]]
    unloadable = [name for name, info in result["textures"].items() if not info.get("loadable")]

    assert result["all_found"], f"{game}:{resref} missing textures: {missing}"
    assert result["all_loadable"], f"{game}:{resref} unloadable textures: {unloadable}"
