from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_grdev01_runtime_variant.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("install_grdev01_runtime_variant_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_t2601_runtime_variant_installer_exposes_renamed_root_bridge_variants() -> None:
    module = _load_script_module()

    assert "renamed-root-minimal" in module.VARIANTS
    assert "renamed-root-minimal-placeable" in module.VARIANTS
    assert "renamed-root-scriptless-dual-minimal" in module.VARIANTS
    assert "renamed-root-scriptless-dual-placeable" in module.VARIANTS
    assert module.VARIANTS["renamed-root-minimal"]["id"] == "renamed_root_minimal_git"
    assert module.VARIANTS["renamed-root-minimal-placeable"]["id"] == "renamed_root_minimal_git_placeable"
    assert module.VARIANTS["renamed-root-scriptless-dual-minimal"]["id"] == "renamed_root_scriptless_dual_minimal_git"
    assert (
        module.VARIANTS["renamed-root-scriptless-dual-placeable"]["id"]
        == "renamed_root_scriptless_dual_minimal_git_placeable"
    )
    assert "grdev01.rim" in module.VARIANTS["renamed-root-minimal"]["conflicting_destination_names"]
    assert "grdev01_s.rim" in module.VARIANTS["renamed-root-minimal-placeable"]["conflicting_destination_names"]
    assert "grdev01_s.rim" in module.VARIANTS["renamed-root-scriptless-dual-minimal"]["conflicting_destination_names"]


def test_t2601_runtime_variant_installer_blocks_without_overwrite(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "stock_mod" / "grdev01.mod"
    source.parent.mkdir()
    source.write_bytes(b"MOD V1.0\x00\x00\x00\x00" + b"stock mod")
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    existing = modules_dir / "grdev01.mod"
    existing.write_bytes(b"existing package")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "stock-mod": {
                "id": "ghostrigger_stock_area_mod",
                "label": "GhostRigger-built stock-area MOD baseline",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "expected_header": "MOD V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="stock-mod",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=False,
    )

    assert summary["ok"] is False
    assert existing.read_bytes() == b"existing package"
    assert any("already exists" in issue for issue in summary["blocking_issues"])


def test_t2601_runtime_variant_installer_installs_with_backup(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "exact_rim" / "grdev01.mod"
    source.parent.mkdir()
    source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"exact rim")
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    existing = modules_dir / "grdev01.mod"
    existing.write_bytes(b"previous diagnostic")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "exact-rim": {
                "id": "exact_stock_rim_rename",
                "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.mod",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "expected_header": "RIM V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="exact-rim",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=True,
    )
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))

    assert summary["ok"] is True
    assert existing.read_bytes() == source.read_bytes()
    assert Path(summary["backup_module_path"]).read_bytes() == b"previous diagnostic"
    assert summary["source_sha256"] == summary["installed_sha256"]
    assert manifest["summary"]["variant"] == "exact-rim"


def test_t2601_runtime_variant_installer_refreshes_stale_currentgame_cache(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "variant" / "grdev01.mod"
    source.parent.mkdir()
    source.write_bytes(b"MOD V1.0\x00\x00\x00\x00" + b"known loaded diagnostic")
    modules_dir = tmp_path / "KOTOR" / "Modules"
    currentgame_dir = tmp_path / "KOTOR" / "currentgame"
    modules_dir.mkdir(parents=True)
    currentgame_dir.mkdir(parents=True)
    existing = modules_dir / "grdev01.mod"
    currentgame = currentgame_dir / "grdev01.mod"
    existing.write_bytes(b"previous active package")
    currentgame.write_bytes(b"stale crash package")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "renamed-root-scriptless-minimal": {
                "id": "renamed_root_scriptless_minimal_git",
                "label": "Known loaded stock-room diagnostic",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "expected_header": "MOD V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="renamed-root-scriptless-minimal",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=True,
    )

    currentgame_backup = currentgame_dir / "grdev01.mod.bak1"
    assert summary["ok"] is True
    assert existing.read_bytes() == source.read_bytes()
    assert currentgame.read_bytes() == source.read_bytes()
    assert currentgame_backup.read_bytes() == b"stale crash package"
    assert summary["currentgame_refreshed_paths"] == [str(currentgame)]
    assert any("currentgame cache" in warning for warning in summary["warnings"])


def test_t2601_runtime_variant_installer_installs_rim_and_removes_conflicting_mod(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "exact_rim" / "grdev01.rim"
    source.parent.mkdir()
    source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"exact rim")
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    conflict = modules_dir / "grdev01.mod"
    conflict.write_bytes(b"previous mod diagnostic")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "exact-rim-file": {
                "id": "exact_stock_rim_custom_filename",
                "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.rim",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "destination_name": "grdev01.rim",
                "conflicting_destination_names": "grdev01.mod",
                "expected_header": "RIM V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="exact-rim-file",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=True,
    )

    assert summary["ok"] is True
    assert (modules_dir / "grdev01.rim").read_bytes() == source.read_bytes()
    assert not conflict.exists()
    assert len(summary["conflict_backup_paths"]) == 1
    assert Path(summary["conflict_backup_paths"][0]).read_bytes() == b"previous mod diagnostic"


def test_t2601_runtime_variant_installer_installs_rim_pair_with_companion_backup(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "exact_rim_pair" / "grdev01.rim"
    static_source = tmp_path / "exact_rim_pair" / "grdev01_s.rim"
    source.parent.mkdir()
    source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"exact rim")
    static_source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"exact static rim")
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    existing_static = modules_dir / "grdev01_s.rim"
    existing_static.write_bytes(b"old static rim")
    conflict = modules_dir / "grdev01.mod"
    conflict.write_bytes(b"previous mod diagnostic")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "exact-rim-pair": {
                "id": "exact_stock_rim_pair",
                "label": "Byte-for-byte stock tar_m02aa RIM pair renamed to grdev01.rim and grdev01_s.rim",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "destination_name": "grdev01.rim",
                "extra_relative_paths": str(static_source.relative_to(module.ROOT))
                if static_source.is_relative_to(module.ROOT)
                else str(static_source),
                "extra_destination_names": "grdev01_s.rim",
                "conflicting_destination_names": "grdev01.mod",
                "expected_header": "RIM V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="exact-rim-pair",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=True,
    )

    assert summary["ok"] is True
    assert (modules_dir / "grdev01.rim").read_bytes() == source.read_bytes()
    assert (modules_dir / "grdev01_s.rim").read_bytes() == static_source.read_bytes()
    assert summary["installed_extra_paths"] == [str(modules_dir / "grdev01_s.rim")]
    assert Path(summary["extra_backup_paths"][0]).read_bytes() == b"old static rim"
    assert Path(summary["conflict_backup_paths"][0]).read_bytes() == b"previous mod diagnostic"
    assert summary["installed_extra_sha256"] == summary["extra_source_sha256"]


def test_t2601_runtime_variant_dry_run_reports_plan_without_touching_files(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "exact_rim" / "grdev01.rim"
    source.parent.mkdir()
    source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"exact rim")
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    destination = modules_dir / "grdev01.rim"
    destination.write_bytes(b"existing rim diagnostic")
    conflict = modules_dir / "grdev01.mod"
    conflict.write_bytes(b"active mod diagnostic")
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "exact-rim-file": {
                "id": "exact_stock_rim_custom_filename",
                "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.rim",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "destination_name": "grdev01.rim",
                "conflicting_destination_names": "grdev01.mod",
                "expected_header": "RIM V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="exact-rim-file",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        dry_run=True,
    )

    assert summary["ok"] is True
    assert summary["code"] == "planned"
    assert summary["installed_module_path"] == ""
    assert summary["target_module_path"] == str(destination)
    assert destination.read_bytes() == b"existing rim diagnostic"
    assert conflict.read_bytes() == b"active mod diagnostic"
    assert summary["install_plan"]["destination_exists"] is True
    assert summary["install_plan"]["conflicting_paths"] == [str(conflict)]
    assert summary["install_plan"]["would_block_without_overwrite"] is True
    assert summary["install_plan"]["would_backup_destination_to"].endswith("grdev01.rim.bak1")
    assert summary["install_plan"]["would_backup_conflicts_to"][0]["backup_path"].endswith("grdev01.mod.bak1")
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["summary"]["code"] == "planned"


def test_t2601_runtime_variant_installer_rejects_unexpected_header(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    source = tmp_path / "bad" / "grdev01.mod"
    source.parent.mkdir()
    source.write_bytes(b"RIM V1.0\x00\x00\x00\x00" + b"wrong package")
    modules_dir = tmp_path / "Modules"
    monkeypatch.setattr(
        module,
        "VARIANTS",
        {
            "stock-mod": {
                "id": "ghostrigger_stock_area_mod",
                "label": "GhostRigger-built stock-area MOD baseline",
                "relative_path": str(source.relative_to(module.ROOT)) if source.is_relative_to(module.ROOT) else str(source),
                "expected_header": "MOD V1.0",
                "proof_question": "test",
            }
        },
    )

    summary = module.install_variant(
        variant_key="stock-mod",
        game_modules_dir=modules_dir,
        output_dir=tmp_path / "out",
        overwrite=True,
    )

    assert summary["ok"] is False
    assert not (modules_dir / "grdev01.mod").exists()
    assert any("expected 'MOD V1.0'" in issue for issue in summary["blocking_issues"])
