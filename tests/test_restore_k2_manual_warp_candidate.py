from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from scripts.restore_k2_manual_warp_candidate import (
    RestorationError,
    restore_staged_candidate,
)
from scripts.stage_k2_manual_warp_candidate import stage_candidate


def _game_fixture(tmp_path: Path) -> Path:
    game_root = tmp_path / "KOTOR2"
    (game_root / "Modules").mkdir(parents=True)
    (game_root / "currentgame").mkdir()
    (game_root / "swkotor2.exe").write_bytes(b"fixture executable")
    return game_root


def _passing_audit(*args, **kwargs):
    return {"audit_pass": True, "errors": []}


def _passing_engine_contract(*args, **kwargs):
    return {"export_ready": True, "blocking_issues": []}


def _stage(tmp_path: Path, *, with_prior: bool = True) -> tuple[Path, Path, Path]:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate module")
    installed = game_root / "Modules" / "901mal.mod"
    cache = game_root / "currentgame" / "901mal.mod"
    if with_prior:
        installed.write_bytes(b"retail module")
        cache.write_bytes(b"prior cache")
    staged = stage_candidate(
        module_root="901mal",
        candidate=candidate,
        game_root=game_root,
        evidence_root=tmp_path / "evidence",
        process_checker=lambda: False,
        audit_runner=_passing_audit,
        engine_audit_runner=_passing_engine_contract,
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )
    return Path(staged["manifest_path"]), installed, cache


def test_restores_prior_module_and_cache_and_preserves_post_test_cache(tmp_path: Path) -> None:
    manifest, installed, cache = _stage(tmp_path)
    cache.write_bytes(b"post-test cache")

    restored = restore_staged_candidate(
        manifest_path=manifest,
        process_checker=lambda: False,
        now=datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc),
    )

    assert installed.read_bytes() == b"retail module"
    assert cache.read_bytes() == b"prior cache"
    post_test = Path(restored["post_test_currentgame_cache"]["path"])
    assert post_test.read_bytes() == b"post-test cache"
    assert Path(restored["restoration_manifest"]).is_file()


def test_removes_candidate_when_no_module_or_cache_existed_before_staging(tmp_path: Path) -> None:
    manifest, installed, cache = _stage(tmp_path, with_prior=False)

    restored = restore_staged_candidate(
        manifest_path=manifest,
        process_checker=lambda: False,
    )

    assert installed.exists() is False
    assert cache.exists() is False
    assert restored["restored_installed"]["path"] is None
    assert restored["restored_currentgame_cache"]["path"] is None


def test_refuses_running_game_before_reading_or_mutating_manifest(tmp_path: Path) -> None:
    manifest, installed, cache = _stage(tmp_path)

    with pytest.raises(RestorationError, match="is running"):
        restore_staged_candidate(manifest_path=manifest, process_checker=lambda: True)

    assert installed.read_bytes() == b"candidate module"
    assert cache.exists() is False


def test_refuses_when_installed_module_changed_after_staging(tmp_path: Path) -> None:
    manifest, installed, cache = _stage(tmp_path)
    installed.write_bytes(b"newer user change")

    with pytest.raises(RestorationError, match="newer change"):
        restore_staged_candidate(manifest_path=manifest, process_checker=lambda: False)

    assert installed.read_bytes() == b"newer user change"
    assert cache.exists() is False
    assert not (manifest.parent / "restoration_manifest.json").exists()


def test_refuses_second_restore_without_mutating_restored_state(tmp_path: Path) -> None:
    manifest, installed, cache = _stage(tmp_path)
    restore_staged_candidate(manifest_path=manifest, process_checker=lambda: False)

    with pytest.raises(RestorationError, match="already restored"):
        restore_staged_candidate(manifest_path=manifest, process_checker=lambda: False)

    assert installed.read_bytes() == b"retail module"
    assert cache.read_bytes() == b"prior cache"
    payload = json.loads((manifest.parent / "restoration_manifest.json").read_text(encoding="utf-8"))
    assert payload["operation"] == "restore_k2_manual_warp_candidate"
