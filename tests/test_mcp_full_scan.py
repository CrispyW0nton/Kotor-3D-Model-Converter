from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "exports" / "scan_manifest.json"
RESULTS_PATH = ROOT / "exports" / "full_scan_results.json"


def _load_test_models() -> list[tuple[str, str]]:
    """Load all manifest models for parametrization."""
    if not MANIFEST.exists():
        return []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    pairs.extend(("k1", resref) for resref in data.get("k1", {}).get("models", []))
    pairs.extend(("k2", resref) for resref in data.get("k2", {}).get("models", []))
    return pairs


ALL_MODELS = _load_test_models()


@pytest.fixture(scope="session", autouse=True)
def _reset_full_scan_results() -> None:
    if RESULTS_PATH.exists():
        RESULTS_PATH.unlink()


def _record_result(record: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RESULTS_PATH.exists():
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    else:
        data = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "results": []}
    data["results"].append(record)
    data["summary"] = {
        "total": len(data["results"]),
        "match": sum(1 for item in data["results"] if item.get("match") is True),
        "mismatch": sum(1 for item in data["results"] if item.get("match") is False),
        "error": sum(1 for item in data["results"] if item.get("error")),
    }
    RESULTS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@pytest.mark.slow
@pytest.mark.skipif(not ALL_MODELS, reason="No manifest found")
@pytest.mark.parametrize("game,resref", ALL_MODELS, ids=[f"{g}:{r}" for g, r in ALL_MODELS])
def test_model_pipeline_match(game: str, resref: str, ghostrigger_tools) -> None:
    """Verify GhostRigger's loader matches raw PyKotor for every manifest model."""
    try:
        result = ghostrigger_tools.compare_model_pipelines(game, resref)
    except Exception as exc:
        _record_result({"game": game, "resref": resref, "error": f"{type(exc).__name__}: {exc}"})
        raise

    _record_result(
        {
            "game": game,
            "resref": resref,
            "match": bool(result["match"]),
            "discrepancies": result.get("discrepancies", []),
            "missing_in_ghostrigger": result.get("missing_in_ghostrigger", []),
            "extra_in_ghostrigger": result.get("extra_in_ghostrigger", []),
        }
    )
    assert result["match"], f"{game}:{resref} mismatch: {result.get('discrepancies', [])}"
