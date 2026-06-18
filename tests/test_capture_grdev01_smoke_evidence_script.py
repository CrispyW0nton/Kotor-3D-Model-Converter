from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE_SCRIPT = ROOT / "scripts" / "prepare_grdev01_authored_smoke.py"
CAPTURE_SCRIPT = ROOT / "scripts" / "capture_grdev01_smoke_evidence.py"
STATUS_SCRIPT = ROOT / "scripts" / "check_grdev01_smoke_status.py"


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _prepare_authored(tmp_path: Path) -> dict[str, object]:
    result = _run_script(
        PREPARE_SCRIPT,
        "--output-dir",
        str(tmp_path / "authored"),
        "--overwrite-kmap",
        "--json",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_grdev01_smoke_evidence", CAPTURE_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _status(proof_manifest: str) -> dict[str, object]:
    result = _run_script(STATUS_SCRIPT, "--proof-manifest", proof_manifest, "--json")
    assert result.stdout
    return json.loads(result.stdout)


def test_t2601_capture_grdev01_evidence_does_not_mark_game_tested_without_record_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    authored = _prepare_authored(tmp_path)
    proof_manifest = str(authored["proof_manifest_path"])
    evidence = tmp_path / "proof.bmp"
    module = _load_capture_module()

    def fake_capture(output_path: Path) -> dict[str, object]:
        output_path.write_bytes(b"BM fake screenshot evidence")
        return {"ok": True, "message": "fake capture", "width": 10, "height": 10, "blocking_issues": []}

    monkeypatch.setattr(module, "_capture_screen_bmp", fake_capture)

    code = module.main(["--proof-manifest", proof_manifest, "--output", str(evidence), "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["code"] == "captured"
    assert payload["record"] is None
    assert evidence.is_file()
    status = _status(proof_manifest)
    assert status["proof"]["game_tested"] is False


def test_t2601_capture_grdev01_evidence_can_record_complete_authored_proof(tmp_path: Path, monkeypatch, capsys) -> None:
    authored = _prepare_authored(tmp_path)
    proof_manifest = str(authored["proof_manifest_path"])
    evidence = tmp_path / "proof.bmp"
    module = _load_capture_module()

    def fake_capture(output_path: Path) -> dict[str, object]:
        output_path.write_bytes(b"BM fake screenshot evidence")
        return {"ok": True, "message": "fake capture", "width": 10, "height": 10, "blocking_issues": []}

    monkeypatch.setattr(module, "_capture_screen_bmp", fake_capture)
    monkeypatch.setattr(
        module,
        "_kotor_process_summary",
        lambda *, skip_check=False: {
            "checked": True,
            "required_for_recording": True,
            "running": True,
            "process_names": ["swkotor", "swkotor2"],
            "processes": [{"process_name": "swkotor", "pid": 1234, "window_title": "Knights of the Old Republic"}],
            "warnings": [],
            "blocking_issues": [],
        },
    )

    code = module.main(
        [
            "--proof-manifest",
            proof_manifest,
            "--output",
            str(evidence),
            "--record-proof",
            "--tester",
            "pytest",
            "--module-loads-in-game",
            "--player-spawns-on-floor",
            "--test-placeable-visible",
            "--player-can-walk-on-floor",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["record"]["ok"] is True
    assert payload["record"]["missing_checks"] == []
    status = _status(proof_manifest)
    assert status["status"] == "game_tested"
    assert status["proof"]["game_tested"] is True
    assert status["proof"]["evidence_accepted"] is True


def test_t2601_capture_grdev01_evidence_blocks_proof_recording_without_kotor_process(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    authored = _prepare_authored(tmp_path)
    proof_manifest = str(authored["proof_manifest_path"])
    evidence = tmp_path / "proof.bmp"
    module = _load_capture_module()

    def fake_capture(output_path: Path) -> dict[str, object]:
        output_path.write_bytes(b"BM fake screenshot evidence")
        return {"ok": True, "message": "fake capture", "width": 10, "height": 10, "blocking_issues": []}

    monkeypatch.setattr(module, "_capture_screen_bmp", fake_capture)
    monkeypatch.setattr(
        module,
        "_kotor_process_summary",
        lambda *, skip_check=False: {
            "checked": True,
            "required_for_recording": True,
            "running": False,
            "process_names": ["swkotor", "swkotor2"],
            "processes": [],
            "warnings": [],
            "blocking_issues": ["No running KOTOR process was detected. Launch KOTOR, warp to grdev01, then record proof."],
        },
    )

    code = module.main(
        [
            "--proof-manifest",
            proof_manifest,
            "--output",
            str(evidence),
            "--record-proof",
            "--tester",
            "pytest",
            "--module-loads-in-game",
            "--player-spawns-on-floor",
            "--test-placeable-visible",
            "--player-can-walk-on-floor",
            "--json",
        ]
    )

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["code"] == "kotor_process_not_running"
    assert payload["kotor_process"]["running"] is False
    assert payload["record"]["ok"] is False
    assert evidence.is_file()
    status = _status(proof_manifest)
    assert status["proof"]["game_tested"] is False
