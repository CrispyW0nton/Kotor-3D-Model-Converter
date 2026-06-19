from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "record_grdev01_smoke_proof.py"


def _install_native_payload_paths() -> None:
    for rel in (
        "native/GhostRigger.Core.Modules/Python",
        "native/GhostRigger.Core.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Walkmesh/Python",
        "native/GhostRigger.Core.Geometry/Python",
        "native/GhostRigger.Core.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Lighting/Python",
        ".",
    ):
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _prepare_smoke_proof(tmp_path: Path) -> object:
    _install_native_payload_paths()
    from src.core.modules.dev_module_smoke import DevModuleInstallPrepRequest, prepare_dev_test_module_install

    return prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_t2618_script_records_complete_grdev01_game_proof(tmp_path: Path) -> None:
    prep = _prepare_smoke_proof(tmp_path / "prep")
    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = _run_script(
        "--proof-manifest",
        prep.proof_manifest_path,
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

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "game_proof_recorded"
    assert payload["missing_checks"] == []
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is False
    assert proof["game_tested"] is True
    assert proof["game_test"]["checks"]["player_can_walk_on_floor"] is True
    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    smoke = pack_manifest["map_studio_smoke_test"]
    assert smoke["game_tested"] is True
    assert smoke["capability_stage"] == "game_smoke_tested"


def test_t2618_script_keeps_module_unproven_when_checks_are_missing(tmp_path: Path) -> None:
    prep = _prepare_smoke_proof(tmp_path / "prep")
    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = _run_script(
        "--proof-manifest",
        prep.proof_manifest_path,
        "--evidence",
        str(evidence),
        "--tester",
        "pytest",
        "--module-loads-in-game",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "game_proof_incomplete"
    assert "player_spawns_on_floor" in payload["missing_checks"]
    assert "test_placeable_visible" in payload["missing_checks"]
    assert "player_can_walk_on_floor" in payload["missing_checks"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    assert pack_manifest["map_studio_smoke_test"]["game_tested"] is False
