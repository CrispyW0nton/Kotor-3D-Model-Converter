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
def test_model_skinning_valid(game: str, resref: str, ghostrigger_tools) -> None:
    result = ghostrigger_tools.inspect_skinning(game, resref)

    for skin in result["skin_nodes"]:
        assert skin["out_of_range_indices"] == 0, (
            f"{game}:{resref}/{skin['name']} has "
            f"{skin['out_of_range_indices']} out-of-range bone indices"
        )
        wmin, wmax = skin["weight_sum_range"]
        assert wmin >= 0.99 and wmax <= 1.01, (
            f"{game}:{resref}/{skin['name']} weight sums [{wmin:.4f}, {wmax:.4f}]"
        )
