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
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {item["restype"] for item in payload["resources"]}
    assert any("record_authored_module_game_proof.py" in action for action in payload["next_actions"])

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
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is True
    assert proof["install"]["installed_module_path"] == str(installed)
