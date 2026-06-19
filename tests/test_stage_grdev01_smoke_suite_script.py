from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stage_grdev01_smoke_suite.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_t2616_script_stages_both_grdev01_variants_as_json(tmp_path: Path) -> None:
    result = _run_script("--output-dir", str(tmp_path), "--json")

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "staged_variant_suite"
    assert Path(payload["suite_checklist_path"]).is_file()
    assert Path(payload["suite_manifest_path"]).is_file()
    assert [variant["variant_id"] for variant in payload["variants"]] == [
        "rectangular_composition",
        "floor_plan_opening",
    ]
    for variant in payload["variants"]:
        assert variant["ok"] is True
        assert Path(variant["module_path"]).is_file()
        assert Path(variant["pack_manifest_path"]).is_file()
        assert Path(variant["proof_manifest_path"]).is_file()

    manifest = json.loads(Path(payload["suite_manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["module_root"] == "grdev01"
    assert manifest["install_policy"] == "stage_all_copy_one_variant_at_a_time"


def test_t2616_script_can_stage_floor_plan_variant_only(tmp_path: Path) -> None:
    result = _run_script("--output-dir", str(tmp_path), "--no-rectangular", "--json")

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert [variant["variant_id"] for variant in payload["variants"]] == ["floor_plan_opening"]
    floor_manifest = json.loads(Path(payload["variants"][0]["pack_manifest_path"]).read_text(encoding="utf-8"))
    smoke = floor_manifest["map_studio_smoke_test"]
    assert smoke["contains"]["floor_plan_room"] is True
    assert smoke["contains"]["wall_opening"] is True
    assert smoke["game_tested"] is False


def test_t2616_script_reports_blocked_when_all_variants_disabled(tmp_path: Path) -> None:
    result = _run_script("--output-dir", str(tmp_path), "--no-rectangular", "--no-floor-plan", "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "variant_suite_preflight_failed"
    assert any("at least one enabled variant" in issue for issue in payload["blocking_issues"])
