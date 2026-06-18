from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_grdev01_smoke_variant.py"
RECORD_SCRIPT = ROOT / "scripts" / "record_grdev01_smoke_proof.py"
STATUS_SCRIPT = ROOT / "scripts" / "check_grdev01_smoke_status.py"


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _install_variant(tmp_path: Path, *args: str) -> dict[str, object]:
    result = _run_script(
        INSTALL_SCRIPT,
        "--output-dir",
        str(tmp_path),
        "--json",
        *args,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def _status(proof_manifest: str, *args: str) -> subprocess.CompletedProcess[str]:
    return _run_script(STATUS_SCRIPT, "--proof-manifest", proof_manifest, "--json", *args)


def test_t2619_status_reports_export_candidate_ready_for_manual_install(tmp_path: Path) -> None:
    install = _install_variant(tmp_path / "prep", "--variant", "rectangular")

    result = _status(str(install["proof_manifest_path"]))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_manual_install"
    assert payload["package_verification"]["ok"] is True
    assert payload["proof"]["game_tested"] is False
    assert payload["proof"]["manual_proof_required"] is True
    assert payload["installed"]["checked"] is False


def test_t2619_status_reports_installed_variant_ready_for_game_test(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    install = _install_variant(
        tmp_path / "prep",
        "--variant",
        "floor-plan",
        "--game-modules-dir",
        str(modules_dir),
    )

    result = _status(str(install["proof_manifest_path"]), "--game-modules-dir", str(modules_dir))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["package_verification"]["ok"] is True
    assert payload["installed"]["exists"] is True
    assert payload["installed"]["matches_package"] is True
    assert payload["proof"]["game_tested"] is False


def test_t2619_status_reports_game_tested_after_complete_proof(tmp_path: Path) -> None:
    install = _install_variant(tmp_path / "prep", "--variant", "rectangular")
    evidence = tmp_path / "grdev01-proof.png"
    evidence.write_bytes(b"fake screenshot")
    record = _run_script(
        RECORD_SCRIPT,
        "--proof-manifest",
        str(install["proof_manifest_path"]),
        "--evidence",
        str(evidence),
        "--tester",
        "pytest",
        "--module-loads-in-game",
        "--player-spawns-on-floor",
        "--test-placeable-visible",
        "--player-can-walk-on-floor",
        "--json",
    )
    assert record.returncode == 0, record.stderr + record.stdout

    result = _status(str(install["proof_manifest_path"]))

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "game_tested"
    assert payload["ok"] is True
    assert payload["package_verification"]["ok"] is True
    assert payload["proof"]["game_tested"] is True
    assert payload["proof"]["manual_proof_required"] is False
    assert payload["proof"]["evidence_exists"] is True
    assert payload["proof"]["missing_checks"] == []
