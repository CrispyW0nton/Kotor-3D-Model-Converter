from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_grdev01_exact_stock_module_rename.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("prepare_grdev01_exact_stock_module_rename_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_game_root(tmp_path: Path) -> Path:
    game_root = tmp_path / "KOTOR"
    modules = game_root / "Modules"
    modules.mkdir(parents=True)
    (modules / "tar_m02aa.rim").write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock module bytes")
    (modules / "tar_m02aa_s.rim").write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"stock static module bytes")
    return game_root


def test_t2601_exact_stock_module_rename_stages_byte_for_byte_copy(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = _fake_game_root(tmp_path)
    output_dir = tmp_path / "out"

    code = module.main(["--game-root-dir", str(game_root), "--output-dir", str(output_dir), "--json"])

    assert code == 0
    staged = output_dir / "install" / "Modules" / "grdev01.mod"
    staged_rim = output_dir / "install" / "Modules" / "grdev01.rim"
    staged_static_rim = output_dir / "install" / "Modules" / "grdev01_s.rim"
    stock = game_root / "Modules" / "tar_m02aa.rim"
    stock_static = game_root / "Modules" / "tar_m02aa_s.rim"
    manifest = json.loads((output_dir / "grdev01_exact_stock_module_rename_manifest.json").read_text(encoding="utf-8"))

    assert staged.read_bytes() == stock.read_bytes()
    assert staged_rim.read_bytes() == stock.read_bytes()
    assert staged_static_rim.read_bytes() == stock_static.read_bytes()
    assert manifest["archive_mode"] == "byte_for_byte_stock_rim_and_static_sidecar_custom_module_filenames"
    assert manifest["summary"]["source_sha256"] == manifest["summary"]["staged_sha256"]
    assert manifest["summary"]["source_static_sha256"] == manifest["summary"]["staged_static_sha256"]
    assert manifest["summary"]["source_header"].startswith("RIM V1.0")
    assert manifest["summary"]["source_static_header"].startswith("RIM V1.0")
    assert manifest["summary"]["installed_module_path"] == ""
    assert manifest["summary"]["rim_path"] == str(staged_rim)
    assert manifest["summary"]["static_rim_path"] == str(staged_static_rim)


def test_t2601_exact_stock_module_rename_installs_with_backup_only_when_requested(tmp_path: Path) -> None:
    module = _load_script_module()
    game_root = _fake_game_root(tmp_path)
    modules_dir = tmp_path / "RuntimeModules"
    modules_dir.mkdir()
    existing = modules_dir / "grdev01.mod"
    existing.write_bytes(b"previous diagnostic")
    output_dir = tmp_path / "out"

    blocked = module.main(
        [
            "--game-root-dir",
            str(game_root),
            "--game-modules-dir",
            str(modules_dir),
            "--output-dir",
            str(output_dir),
            "--install",
            "--json",
        ]
    )

    assert blocked == 1
    assert existing.read_bytes() == b"previous diagnostic"

    ok = module.main(
        [
            "--game-root-dir",
            str(game_root),
            "--game-modules-dir",
            str(modules_dir),
            "--output-dir",
            str(output_dir),
            "--install",
            "--overwrite-module",
            "--json",
        ]
    )
    manifest = json.loads((output_dir / "grdev01_exact_stock_module_rename_manifest.json").read_text(encoding="utf-8"))

    assert ok == 0
    assert existing.read_bytes() == (game_root / "Modules" / "tar_m02aa.rim").read_bytes()
    assert Path(manifest["summary"]["backup_module_path"]).read_bytes() == b"previous diagnostic"
    assert manifest["summary"]["installed_module_path"] == str(existing)
