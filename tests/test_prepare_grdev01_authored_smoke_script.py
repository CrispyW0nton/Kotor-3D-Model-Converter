from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_grdev01_authored_smoke.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_t2647_prepare_grdev01_authored_smoke_creates_kmap_and_package(tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"

    result = _run("--output-dir", str(output_dir), "--json")

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "staged_for_manual_install"
    assert payload["module_root"] == "grdev01"
    assert Path(payload["kmap_path"]).is_file()
    assert Path(payload["module_path"]).is_file()
    assert Path(payload["pack_manifest_path"]).is_file()
    assert Path(payload["checklist_path"]).is_file()
    assert Path(payload["proof_manifest_path"]).is_file()
    assert payload["elevated_launch_script_path"] == ""
    assert Path(payload["proof_recording_script_path"]).is_file()
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {item["restype"] for item in payload["resources"]}
    assert any("record_authored_module_game_proof.py" in action for action in payload["next_actions"])
    assert any("record_game_proof.cmd" in action for action in payload["next_actions"])

    kmap = json.loads(Path(payload["kmap_path"]).read_text(encoding="utf-8"))
    assert kmap["authored_module"]["module_root"] == "grdev01"
    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False


def test_t2647_prepare_grdev01_authored_smoke_refuses_existing_kmap_without_overwrite(tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"
    output_dir.mkdir()
    kmap = output_dir / "grdev01.kmap"
    kmap.write_text("existing", encoding="utf-8")

    result = _run("--output-dir", str(output_dir), "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "kmap_exists"
    assert kmap.read_text(encoding="utf-8") == "existing"


def test_t2647_prepare_grdev01_authored_smoke_installs_with_backup(tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"existing")

    result = _run(
        "--output-dir",
        str(output_dir),
        "--game-modules-dir",
        str(modules_dir),
        "--overwrite-module",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    backup = modules_dir / "grdev01.mod.bak"
    assert payload["ok"] is True
    assert payload["code"] == "installed"
    assert payload["installed_module_path"] == str(installed)
    assert payload["backup_module_path"] == str(backup)
    assert payload["resolved_modules_dir"] == str(modules_dir)
    assert payload["resolved_game_root_dir"] == str(modules_dir.parent)
    assert "launch_grdev01_smoke_test.py" in payload["launch_helper_command"]
    assert str(modules_dir.parent) in payload["launch_helper_command"]
    assert "capture_grdev01_smoke_evidence.py" in payload["evidence_capture_command"]
    assert "--record-proof" in payload["evidence_capture_command"]
    assert Path(payload["elevated_launch_script_path"]).is_file()
    assert Path(payload["proof_recording_script_path"]).is_file()
    assert "RunAs" in Path(payload["elevated_launch_script_path"]).read_text(encoding="utf-8")
    assert "record_authored_module_game_proof.py" in Path(payload["proof_recording_script_path"]).read_text(encoding="utf-8")
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is True
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["launch_handoff"]["resolved_game_root_dir"] == payload["resolved_game_root_dir"]
    assert proof["launch_handoff"]["launch_helper_command"] == payload["launch_helper_command"]
    assert proof["launch_handoff"]["evidence_capture_command"] == payload["evidence_capture_command"]
    assert proof["launch_handoff"]["elevated_launch_script_path"] == payload["elevated_launch_script_path"]
    assert proof["launch_handoff"]["proof_recording_script_path"] == payload["proof_recording_script_path"]


def test_t2601_authored_install_refreshes_stale_currentgame_cache(tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"
    modules_dir = tmp_path / "KOTOR" / "Modules"
    currentgame_dir = tmp_path / "KOTOR" / "currentgame"
    modules_dir.mkdir(parents=True)
    currentgame_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    currentgame = currentgame_dir / "grdev01.mod"
    installed.write_bytes(b"old modules package")
    currentgame.write_bytes(b"stale currentgame package")

    result = _run(
        "--output-dir",
        str(output_dir),
        "--game-modules-dir",
        str(modules_dir),
        "--overwrite-module",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    currentgame_backup = currentgame_dir / "grdev01.mod.bak"
    assert payload["ok"] is True
    assert payload["code"] == "installed"
    assert installed.read_bytes() == currentgame.read_bytes()
    assert currentgame_backup.read_bytes() == b"stale currentgame package"
    assert any("currentgame cache" in warning for warning in payload["warnings"])


def test_t2647_prepare_grdev01_room_only_summary_omits_placeable_check(tmp_path: Path) -> None:
    output_dir = tmp_path / "room_only"

    result = _run(
        "--output-dir",
        str(output_dir),
        "--without-test-placeable",
        "--without-start-waypoint",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "--test-placeable-visible" not in payload["evidence_capture_command"]
    assert not any("test placeable appears" in action for action in payload["next_actions"])
    assert not any("--test-placeable-visible" in action for action in payload["next_actions"])
    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["acceptance_checks"] == [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]


def test_t2647_prepare_grdev01_without_doorway_marker_keeps_placeable_proof(tmp_path: Path) -> None:
    output_dir = tmp_path / "no_marker"

    result = _run(
        "--output-dir",
        str(output_dir),
        "--without-doorway-marker",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "--test-placeable-visible" in payload["evidence_capture_command"]

    kmap = json.loads(Path(payload["kmap_path"]).read_text(encoding="utf-8"))
    primitive = kmap["authored_module"]["rooms"][0]["primitive"]
    assert primitive["include_doorway_marker"] is False

    manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    authored = manifest["map_studio_authored_module"]
    assert authored["rooms"][0]["model_nodes"] == 1
    assert authored["smoke_expectations"]["expected_placeables"][0]["tag"] == "grdev01_test_placeable"

    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert "test_placeable_visible" in proof["acceptance_checks"]
