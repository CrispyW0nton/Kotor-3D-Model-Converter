from __future__ import annotations

import importlib.util as _il_util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "exports" / "scan_manifest.json"
RESULTS_PATH = ROOT / "exports" / "full_scan_results.json"
MODE_DISTRIBUTION_PATH = ROOT / "tests" / "_artifacts" / "mode_distribution.json"
_MODEL_DATA = None


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
    if MODE_DISTRIBUTION_PATH.exists():
        MODE_DISTRIBUTION_PATH.unlink()


def _load_model_data_module():
    """Load model_data directly so scan tests avoid core package side effects."""
    global _MODEL_DATA
    if _MODEL_DATA is not None:
        return _MODEL_DATA
    path = ROOT / "src" / "core" / "model_data.py"
    spec = _il_util.spec_from_file_location("ghostrigger_mcp_scan_model_data", str(path))
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _MODEL_DATA = module
    return module


def _mode_adapter_from_summary(summary: dict[str, Any]) -> Any:
    nodes = [
        SimpleNamespace(name=str(item.get("name", "")))
        for item in list(summary.get("nodes", []) or [])
    ]

    class _ModelAdapter:
        name = str(summary.get("resref", "") or "")
        supermodel = str(summary.get("supermodel", "") or "")
        model_type = int(summary.get("model_type", 0) or 0)

        def all_nodes(self):
            return list(nodes)

    return _ModelAdapter()


def _detect_character_mode_record(game: str, resref: str, ghostrigger_tools) -> dict[str, Any]:
    """Return CharacterMode metadata for one GhostRigger-loaded model."""
    try:
        summary = ghostrigger_tools.inspect_mdl_ghostrigger(game, resref)
        md = _load_model_data_module()
        mode = md.detect_character_mode(_mode_adapter_from_summary(summary))
        return {
            "character_mode": getattr(mode, "name", str(mode)),
            "model_type": int(summary.get("model_type", 0) or 0),
            "supermodel": str(summary.get("supermodel", "") or ""),
            "node_count_ghostrigger": int(summary.get("node_count", 0) or 0),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "character_mode": "ERROR",
            "mode_error": f"{type(exc).__name__}: {exc}",
        }


def _write_mode_distribution(results: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    by_game: dict[str, dict[str, int]] = {}
    errors: list[dict[str, str]] = []
    for row in results:
        mode = str(row.get("character_mode") or "UNKNOWN")
        counts[mode] = counts.get(mode, 0) + 1
        game = str(row.get("game") or "unknown")
        by_game.setdefault(game, {})
        by_game[game][mode] = by_game[game].get(mode, 0) + 1
        if row.get("mode_error"):
            errors.append(
                {
                    "game": game,
                    "resref": str(row.get("resref") or ""),
                    "error": str(row.get("mode_error") or ""),
                }
            )

    total = len(results)
    ambiguous = counts.get("AMBIGUOUS", 0)
    error_count = counts.get("ERROR", 0)
    non_ambiguous = max(0, total - ambiguous - error_count)
    payload = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": total,
        "counts": dict(sorted(counts.items())),
        "by_game": {
            game: dict(sorted(values.items()))
            for game, values in sorted(by_game.items())
        },
        "ambiguous": ambiguous,
        "errors": error_count,
        "non_ambiguous": non_ambiguous,
        "non_ambiguous_ratio": (non_ambiguous / total) if total else 0.0,
        "threshold": 0.95,
        "sample_errors": errors[:10],
    }
    MODE_DISTRIBUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODE_DISTRIBUTION_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    _write_mode_distribution(data["results"])


@pytest.mark.slow
@pytest.mark.skipif(not ALL_MODELS, reason="No manifest found")
@pytest.mark.parametrize("game,resref", ALL_MODELS, ids=[f"{g}:{r}" for g, r in ALL_MODELS])
def test_model_pipeline_match(game: str, resref: str, ghostrigger_tools) -> None:
    """Verify GhostRigger's loader matches raw PyKotor for every manifest model."""
    mode_record = _detect_character_mode_record(game, resref, ghostrigger_tools)
    try:
        result = ghostrigger_tools.compare_model_pipelines(game, resref)
    except Exception as exc:
        _record_result({
            "game": game,
            "resref": resref,
            "error": f"{type(exc).__name__}: {exc}",
            **mode_record,
        })
        raise

    _record_result(
        {
            "game": game,
            "resref": resref,
            "match": bool(result["match"]),
            **mode_record,
            "discrepancies": result.get("discrepancies", []),
            "missing_in_ghostrigger": result.get("missing_in_ghostrigger", []),
            "extra_in_ghostrigger": result.get("extra_in_ghostrigger", []),
        }
    )
    assert result["match"], f"{game}:{resref} mismatch: {result.get('discrepancies', [])}"


@pytest.mark.slow
@pytest.mark.skipif(not ALL_MODELS, reason="No manifest found")
def test_mode_distribution_non_ambiguous_threshold() -> None:
    """T1103: full scan emits a CharacterMode histogram with >=95% clarity."""
    if not MODE_DISTRIBUTION_PATH.exists():
        pytest.skip("mode distribution artifact has not been generated")
    data = json.loads(MODE_DISTRIBUTION_PATH.read_text(encoding="utf-8"))
    if int(data.get("total", 0) or 0) < len(ALL_MODELS):
        pytest.skip("mode distribution artifact is from a partial scan")
    assert float(data.get("non_ambiguous_ratio", 0.0) or 0.0) >= 0.95, (
        "detect_character_mode non-ambiguous ratio "
        f"{float(data.get('non_ambiguous_ratio', 0.0) or 0.0):.1%} "
        "is below the M11/T1103 threshold"
    )


def test_t1103_mode_distribution_writer_counts_ambiguous_and_errors(tmp_path, monkeypatch):
    artifact = tmp_path / "mode_distribution.json"
    monkeypatch.setattr(sys.modules[__name__], "MODE_DISTRIBUTION_PATH", artifact)

    _write_mode_distribution(
        [
            {"game": "k1", "resref": "pmbam", "character_mode": "HEADLESS_BODY"},
            {"game": "k1", "resref": "pmhc01", "character_mode": "HEAD"},
            {"game": "k2", "resref": "odd", "character_mode": "AMBIGUOUS"},
            {
                "game": "k2",
                "resref": "bad",
                "character_mode": "ERROR",
                "mode_error": "load failed",
            },
        ]
    )

    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["counts"]["HEADLESS_BODY"] == 1
    assert data["counts"]["HEAD"] == 1
    assert data["ambiguous"] == 1
    assert data["errors"] == 1
    assert data["non_ambiguous"] == 2
    assert data["non_ambiguous_ratio"] == 0.5
    assert data["sample_errors"][0]["resref"] == "bad"
