from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE_SCRIPT = ROOT / "scripts" / "prepare_grdev01_authored_smoke.py"
LAUNCH_SCRIPT = ROOT / "scripts" / "launch_grdev01_smoke_test.py"


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _prepare_installed_smoke(tmp_path: Path, *, create_exe: bool = True, game: str = "K1") -> tuple[dict[str, object], Path]:
    output_dir = tmp_path / "smoke"
    game = game.upper()
    game_root = tmp_path / ("KOTOR2" if game == "K2" else "KOTOR")
    modules_dir = game_root / "Modules"
    modules_dir.mkdir(parents=True)
    if create_exe:
        executable_name = "swkotor2.exe" if game == "K2" else "swkotor.exe"
        (game_root / executable_name).write_bytes(b"fake exe")
    result = _run_script(
        PREPARE_SCRIPT,
        "--output-dir",
        str(output_dir),
        "--game",
        game,
        "--game-modules-dir",
        str(modules_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout), game_root


def _launch(proof_manifest: str, game_root: Path) -> subprocess.CompletedProcess[str]:
    return _run_script(
        LAUNCH_SCRIPT,
        "--proof-manifest",
        proof_manifest,
        "--game-root-dir",
        str(game_root),
        "--dry-run",
        "--json",
    )


def test_t2649_launch_grdev01_smoke_dry_run_accepts_ready_install(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)

    result = _launch(str(prep["proof_manifest_path"]), game_root)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["game"] == "K1"
    assert payload["code"] == "dry_run_ready"
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["ready_for_game_launch"] is True
    assert payload["installed_matches_package"] is True
    assert payload["dry_run"] is True
    assert payload["launch_command"] == [str(game_root / "swkotor.exe")]
    assert payload["warp_command"] == "warp grdev01"
    assert payload["elevated_launch_script_path"] == prep["elevated_launch_script_path"]
    assert "warp grdev01" in payload["next_action"]
    assert payload["proof_recording_script_path"] == prep["proof_recording_script_path"]
    assert "record_game_proof.cmd" in payload["next_action"]
    assert payload["console"]["checked"] is True
    assert payload["console"]["ready"] is False
    assert payload["warnings"]
    assert "EnableCheats=1" in payload["console"]["fix_hint"]


def test_t2601_launch_grdev01_smoke_uses_k2_executable_from_proof_manifest(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path, game="K2")
    (game_root / "swkotor2.ini").write_text("[Game Options]\nEnableCheats=1\n", encoding="utf-8")

    result = _launch(str(prep["proof_manifest_path"]), game_root)

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["game"] == "K2"
    assert payload["code"] == "dry_run_ready"
    assert payload["launch_command"] == [str(game_root / "swkotor2.exe")]
    assert payload["ready_for_game_launch"] is True
    assert "warp grdev01" in payload["next_action"]
    assert payload["console"]["checked"] is True
    assert payload["console"]["ready"] is True
    assert payload["console"]["game_ini_path"] == str(game_root / "swkotor2.ini")
    assert payload["console"]["enable_cheats_value"] == "1"


def test_t2649_launch_grdev01_smoke_blocks_missing_executable(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path, create_exe=False)

    result = _launch(str(prep["proof_manifest_path"]), game_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "not_ready"
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["ready_for_game_launch"] is True
    assert any("swkotor.exe" in issue for issue in payload["blocking_issues"])


def test_t2601_launch_can_require_console_ready_for_warp(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)

    result = _run_script(
        LAUNCH_SCRIPT,
        "--proof-manifest",
        str(prep["proof_manifest_path"]),
        "--game-root-dir",
        str(game_root),
        "--dry-run",
        "--require-console-ready",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "not_ready"
    assert payload["ready_for_game_launch"] is True
    assert payload["console"]["checked"] is True
    assert payload["console"]["ready"] is False
    assert any("EnableCheats=1" in issue for issue in payload["blocking_issues"])


def test_t2601_launch_strict_console_ready_accepts_enabled_ini(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)
    (game_root / "swkotor.ini").write_text("[Game Options]\nEnableCheats=1\n", encoding="utf-8")

    result = _run_script(
        LAUNCH_SCRIPT,
        "--proof-manifest",
        str(prep["proof_manifest_path"]),
        "--game-root-dir",
        str(game_root),
        "--dry-run",
        "--require-console-ready",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "dry_run_ready"
    assert payload["console"]["ready"] is True
    assert payload["console"]["game_ini_path"] == str(game_root / "swkotor.ini")


def test_t2601_launch_elevated_dry_run_reports_powershell_command(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)
    (game_root / "swkotor.ini").write_text("[Game Options]\nEnableCheats=1\n", encoding="utf-8")

    result = _run_script(
        LAUNCH_SCRIPT,
        "--proof-manifest",
        str(prep["proof_manifest_path"]),
        "--game-root-dir",
        str(game_root),
        "--dry-run",
        "--require-console-ready",
        "--elevated",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["elevated"] is True
    assert payload["launch_command"][:4] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"]
    assert "Start-Process" in payload["launch_command"][-1]
    assert "-Verb RunAs" in payload["launch_command"][-1]


def test_t2601_launch_elevated_uses_powershell_start_process(tmp_path: Path, monkeypatch, capsys) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)
    (game_root / "swkotor.ini").write_text("[Game Options]\nEnableCheats=1\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("launch_grdev01_smoke_test_elevated_under_test", LAUNCH_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    code = module.main(
        [
            "--proof-manifest",
            str(prep["proof_manifest_path"]),
            "--game-root-dir",
            str(game_root),
            "--require-console-ready",
            "--elevated",
            "--json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["elevated"] is True
    assert payload["message"].startswith("Elevated KOTOR launch request")
    assert captured["command"] == payload["launch_command"]
    assert captured["command"][0] == "powershell"


def test_t2649_launch_grdev01_smoke_blocks_stale_installed_module(tmp_path: Path) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)
    installed = game_root / "Modules" / "grdev01.mod"
    installed.write_bytes(b"stale module")

    result = _launch(str(prep["proof_manifest_path"]), game_root)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "not_ready"
    assert payload["status"] == "installed_copy_mismatch"
    assert payload["installed_matches_package"] is False
    assert any("does not match" in issue for issue in payload["blocking_issues"])


def test_t2687_launch_reports_elevation_without_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    prep, game_root = _prepare_installed_smoke(tmp_path)
    spec = importlib.util.spec_from_file_location("launch_grdev01_smoke_test_under_test", LAUNCH_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def raise_elevation(*args, **kwargs):
        exc = OSError(740, "The requested operation requires elevation")
        exc.winerror = 740
        raise exc

    monkeypatch.setattr(module.subprocess, "Popen", raise_elevation)

    code = module.main(
        [
            "--proof-manifest",
            str(prep["proof_manifest_path"]),
            "--game-root-dir",
            str(game_root),
            "--json",
        ]
    )

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["code"] == "launch_requires_elevation"
    assert "requires elevation" in payload["message"]
    assert any("administrator" in issue for issue in payload["blocking_issues"])
    assert payload["elevated_launch_script_path"] == prep["elevated_launch_script_path"]
    assert any(str(prep["elevated_launch_script_path"]) in issue for issue in payload["blocking_issues"])
