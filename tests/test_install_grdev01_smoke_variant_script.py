from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_grdev01_smoke_variant.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_t2617_script_installs_one_floor_plan_variant_to_modules(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    output_dir = tmp_path / "out"

    result = _run_script(
        "--variant",
        "floor-plan",
        "--output-dir",
        str(output_dir),
        "--game-modules-dir",
        str(modules_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    installed = modules_dir / "grdev01.mod"
    assert payload["ok"] is True
    assert payload["code"] == "installed"
    assert payload["variant_id"] == "floor_plan_opening"
    assert payload["room_geometry_mode"] == "floor_plan"
    assert payload["installed_module_path"] == str(installed)
    assert payload["resolved_modules_dir"] == str(modules_dir)
    assert payload["resolved_game_root_dir"] == str(modules_dir.parent)
    assert "launch_grdev01_smoke_test.py" in payload["launch_helper_command"]
    assert "capture_grdev01_smoke_evidence.py" in payload["evidence_capture_command"]
    assert "--record-proof" in payload["evidence_capture_command"]
    assert Path(payload["elevated_launch_script_path"]).is_file()
    assert Path(payload["proof_recording_script_path"]).is_file()
    assert installed.is_file()
    assert Path(payload["checklist_path"]).is_file()
    assert Path(payload["proof_manifest_path"]).is_file()

    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is True
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["launch_handoff"]["resolved_game_root_dir"] == str(modules_dir.parent)
    assert proof["launch_handoff"]["evidence_capture_command"] == payload["evidence_capture_command"]
    assert proof["launch_handoff"]["proof_recording_script_path"] == payload["proof_recording_script_path"]
    assert proof["manual_proof_required"] is True
    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    smoke = pack_manifest["map_studio_smoke_test"]
    assert smoke["contains"]["floor_plan_room"] is True
    assert smoke["contains"]["wall_opening"] is True
    assert smoke["game_tested"] is False


def test_t2617_script_blocks_existing_module_without_overwrite(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "grdev01.mod").write_bytes(b"existing")

    result = _run_script(
        "--variant",
        "rectangular",
        "--output-dir",
        str(tmp_path / "out"),
        "--game-modules-dir",
        str(modules_dir),
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "install_preflight_failed"
    assert any("already exists" in issue for issue in payload["blocking_issues"])
    assert (modules_dir / "grdev01.mod").read_bytes() == b"existing"


def test_t2635_script_overwrite_backs_up_existing_module(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"existing")

    result = _run_script(
        "--variant",
        "rectangular",
        "--output-dir",
        str(tmp_path / "out"),
        "--game-modules-dir",
        str(modules_dir),
        "--overwrite",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    backup = modules_dir / "grdev01.mod.bak"
    assert payload["ok"] is True
    assert payload["code"] == "installed"
    assert payload["installed_module_path"] == str(installed)
    assert payload["backup_module_path"] == str(backup)
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    assert any("Backed up existing grdev01.mod" in warning for warning in payload["warnings"])


def test_t2617_script_dry_run_does_not_copy_to_modules(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)

    result = _run_script(
        "--variant",
        "rectangular",
        "--output-dir",
        str(tmp_path / "out"),
        "--game-modules-dir",
        str(modules_dir),
        "--dry-run",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "dry_run"
    assert payload["installed_module_path"] == ""
    assert not (modules_dir / "grdev01.mod").exists()
    assert any("Dry run" in warning for warning in payload["warnings"])
