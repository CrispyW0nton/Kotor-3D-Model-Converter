from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import struct
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


def _ok_quality(output_path: Path) -> dict[str, object]:
    return {
        "checked": True,
        "ok": True,
        "code": "evidence_quality_ok",
        "message": "Screenshot evidence contains visible image content.",
        "width": 10,
        "height": 10,
        "sampled_pixels": 100,
        "visible_pixel_ratio": 1.0,
        "dark_pixel_ratio": 0.0,
        "blocking_issues": [],
    }


def _write_bmp(path: Path, *, rgb: tuple[int, int, int]) -> None:
    width = 4
    height = 4
    row_size = ((width * 24 + 31) // 32) * 4
    image_size = row_size * height
    pixel_offset = 54
    padding = b"\x00" * (row_size - width * 3)
    r, g, b = rgb
    with path.open("wb") as handle:
        handle.write(struct.pack("<2sIHHI", b"BM", pixel_offset + image_size, 0, 0, pixel_offset))
        handle.write(struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, image_size, 0, 0, 0, 0))
        for _row in range(height):
            handle.write(bytes((b, g, r)) * width)
            handle.write(padding)


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
    monkeypatch.setattr(module, "_bmp_evidence_quality", _ok_quality)
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
    monkeypatch.setattr(module, "_bmp_evidence_quality", _ok_quality)
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


def test_t2601_capture_grdev01_evidence_can_capture_kotor_window_only(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    authored = _prepare_authored(tmp_path)
    proof_manifest = str(authored["proof_manifest_path"])
    evidence = tmp_path / "proof.bmp"
    module = _load_capture_module()

    monkeypatch.setattr(
        module,
        "_kotor_process_summary",
        lambda *, skip_check=False: {
            "checked": True,
            "required_for_recording": True,
            "running": True,
            "process_names": ["swkotor", "swkotor2"],
            "processes": [{"process_name": "swkotor", "pid": 1234, "window_title": "Knights of the Old Republic", "window_handle": 5678}],
            "warnings": [],
            "blocking_issues": [],
        },
    )

    def fake_window_capture(output_path: Path, kotor_process: dict[str, object]) -> dict[str, object]:
        output_path.write_bytes(b"BM fake kotor window evidence")
        return {
            "ok": True,
            "message": "fake window capture",
            "capture_scope": "kotor_window",
            "window_handle": kotor_process["processes"][0]["window_handle"],  # type: ignore[index]
            "width": 640,
            "height": 480,
            "blocking_issues": [],
        }

    monkeypatch.setattr(module, "_capture_kotor_window_bmp", fake_window_capture)
    monkeypatch.setattr(module, "_bmp_evidence_quality", _ok_quality)

    code = module.main(["--proof-manifest", proof_manifest, "--output", str(evidence), "--kotor-window-only", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["capture"]["capture_scope"] == "kotor_window"
    assert payload["capture"]["window_handle"] == 5678
    assert payload["kotor_process"]["running"] is True
    assert payload["record"] is None
    assert evidence.is_file()


def test_t2601_capture_grdev01_evidence_rejects_mostly_blank_bmp(tmp_path: Path) -> None:
    module = _load_capture_module()
    evidence = tmp_path / "blank.bmp"
    _write_bmp(evidence, rgb=(0, 0, 0))

    quality = module._bmp_evidence_quality(evidence)

    assert quality["ok"] is False
    assert quality["code"] == "evidence_mostly_blank"
    assert quality["blocking_issues"]


def test_t2601_capture_grdev01_evidence_accepts_visible_bmp(tmp_path: Path) -> None:
    module = _load_capture_module()
    evidence = tmp_path / "visible.bmp"
    _write_bmp(evidence, rgb=(80, 80, 80))

    quality = module._bmp_evidence_quality(evidence)

    assert quality["ok"] is True
    assert quality["code"] == "evidence_quality_ok"
    assert quality["blocking_issues"] == []
