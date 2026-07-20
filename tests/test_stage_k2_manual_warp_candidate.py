from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.stage_k2_manual_warp_candidate as staging
from scripts.stage_k2_manual_warp_candidate import StagingError, stage_candidate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _game_fixture(tmp_path: Path) -> Path:
    game_root = tmp_path / "KOTOR2"
    (game_root / "Modules").mkdir(parents=True)
    (game_root / "currentgame").mkdir()
    (game_root / "swkotor2.exe").write_bytes(b"fixture executable")
    return game_root


def _passing_audit(path: Path, *, module: str, game: str, roundtrip: bool):
    assert path.suffix.lower() == ".mod"
    assert module == "vul803"
    assert game == "K2"
    assert roundtrip is True
    return {
        "audit_pass": True,
        "errors": [],
        "walkmeshes": [{"resref": "vul803_01a", "raw_structure_valid": True}],
    }


def _passing_engine_contract(
    path: Path,
    *,
    module_root: str,
    visual_only_room_resrefs=(),
):
    assert path.suffix.lower() == ".mod"
    assert module_root == "vul803"
    return {
        "export_ready": True,
        "blocking_issues": [],
        "visual_only_room_resrefs": list(visual_only_room_resrefs),
    }


@pytest.mark.parametrize(
    ("stdout", "expected"),
    (("RUNNING\n", True), ("NOT_RUNNING\n", False)),
)
def test_windows_process_probe_has_unambiguous_states(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    expected: bool,
) -> None:
    def fake_run(args, **kwargs):
        assert args[0].lower() == "powershell.exe"
        assert "System.Diagnostics.Process" in args[-1]
        assert kwargs["check"] is False
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(staging.subprocess, "run", fake_run)

    assert staging.is_swkotor2_running() is expected


def test_windows_process_probe_refuses_failed_or_ambiguous_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        staging.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout="", stderr="provider failed"),
    )
    with pytest.raises(StagingError, match="provider failed"):
        staging.is_swkotor2_running()

    monkeypatch.setattr(
        staging.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(StagingError, match="Unexpected Windows process-query response"):
        staging.is_swkotor2_running()


def test_stages_only_requested_module_and_preserves_installed_and_cache_evidence(
    tmp_path: Path,
) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate_bytes = b"structurally audited candidate"
    candidate.write_bytes(candidate_bytes)

    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"previous installed module")
    other_module = game_root / "Modules" / "901mal.mod"
    other_module.write_bytes(b"unrelated module")
    cache = game_root / "currentgame" / "vul803.mod"
    cache.write_bytes(b"stale currentgame cache")
    ini = game_root / "swkotor2.ini"
    ini.write_text("[Game Options]\nEnableCheats=0\n", encoding="utf-8")
    hook = game_root / "dinput8.dll"
    hook.write_bytes(b"existing hook sentinel")

    payload = stage_candidate(
        module_root="vul803",
        candidate=candidate,
        game_root=game_root,
        evidence_root=tmp_path / "evidence",
        process_checker=lambda: False,
        audit_runner=_passing_audit,
        engine_audit_runner=_passing_engine_contract,
        visual_only_room_resrefs=("vul803_01b",),
        now=datetime(2026, 7, 16, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert installed.read_bytes() == candidate_bytes
    assert payload["installed"]["sha256"] == _sha256(candidate_bytes)
    assert payload["source"]["sha256"] == _sha256(candidate_bytes)
    assert cache.exists() is False
    assert Path(payload["installed_backup"]["path"]).read_bytes() == b"previous installed module"
    assert Path(payload["currentgame_cache_moved_to"]["path"]).read_bytes() == b"stale currentgame cache"
    assert payload["installed_backup"]["sha256"] == _sha256(b"previous installed module")
    assert payload["currentgame_cache_moved_to"]["sha256"] == _sha256(b"stale currentgame cache")
    assert payload["retail_game_proven"] is False
    assert payload["engine_contract"]["export_ready"] is True
    assert payload["visual_only_room_resrefs"] == ["vul803_01b"]
    assert any("warp vul803" in step for step in payload["manual_warp_checklist"])
    assert payload["guardrails"]["ini_modified"] is False
    assert payload["guardrails"]["game_launched"] is False
    assert other_module.read_bytes() == b"unrelated module"
    assert ini.read_text(encoding="utf-8") == "[Game Options]\nEnableCheats=0\n"
    assert hook.read_bytes() == b"existing hook sentinel"
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest == payload


def test_refuses_immediately_when_kotor2_is_running(tmp_path: Path) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate")
    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"installed")
    audit_called = False

    def audit_runner(*args, **kwargs):
        nonlocal audit_called
        audit_called = True
        return {"audit_pass": True}

    with pytest.raises(StagingError, match="is running"):
        stage_candidate(
            module_root="vul803",
            candidate=candidate,
            game_root=game_root,
            evidence_root=tmp_path / "evidence",
            process_checker=lambda: True,
            audit_runner=audit_runner,
        )

    assert audit_called is False
    assert installed.read_bytes() == b"installed"
    assert not (tmp_path / "evidence").exists()


def test_failed_structural_audit_makes_no_game_or_evidence_mutation(tmp_path: Path) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate")
    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"installed")
    cache = game_root / "currentgame" / "vul803.mod"
    cache.write_bytes(b"cache")

    with pytest.raises(StagingError, match="structural gate"):
        stage_candidate(
            module_root="vul803",
            candidate=candidate,
            game_root=game_root,
            evidence_root=tmp_path / "evidence",
            process_checker=lambda: False,
            audit_runner=lambda *args, **kwargs: {
                "audit_pass": False,
                "errors": ["perimeter loop is open"],
            },
        )

    assert installed.read_bytes() == b"installed"
    assert cache.read_bytes() == b"cache"
    assert not (tmp_path / "evidence").exists()


def test_second_process_check_closes_audit_race_without_mutation(tmp_path: Path) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate")
    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"installed")
    checks = iter((False, True))

    with pytest.raises(StagingError, match="started during validation"):
        stage_candidate(
            module_root="vul803",
            candidate=candidate,
            game_root=game_root,
            evidence_root=tmp_path / "evidence",
            process_checker=lambda: next(checks),
            audit_runner=_passing_audit,
            engine_audit_runner=_passing_engine_contract,
        )

    assert installed.read_bytes() == b"installed"
    assert not (tmp_path / "evidence").exists()


def test_install_failure_restores_installed_module_and_currentgame_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate")
    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"installed")
    cache = game_root / "currentgame" / "vul803.mod"
    cache.write_bytes(b"cache")
    original_verified_copy = staging._verified_copy

    def fail_candidate_install(source: Path, destination: Path, expected_sha256: str):
        if destination.name.startswith(".vul803.stage-"):
            raise OSError("simulated candidate install failure")
        return original_verified_copy(source, destination, expected_sha256)

    monkeypatch.setattr(staging, "_verified_copy", fail_candidate_install)

    with pytest.raises(OSError, match="simulated candidate install failure"):
        stage_candidate(
            module_root="vul803",
            candidate=candidate,
            game_root=game_root,
            evidence_root=tmp_path / "evidence",
            process_checker=lambda: False,
            audit_runner=_passing_audit,
            engine_audit_runner=_passing_engine_contract,
        )

    assert installed.read_bytes() == b"installed"
    assert cache.read_bytes() == b"cache"


def test_failed_engine_contract_makes_no_game_or_evidence_mutation(tmp_path: Path) -> None:
    game_root = _game_fixture(tmp_path)
    candidate = tmp_path / "candidate.mod"
    candidate.write_bytes(b"candidate")
    installed = game_root / "Modules" / "vul803.mod"
    installed.write_bytes(b"installed")
    cache = game_root / "currentgame" / "vul803.mod"
    cache.write_bytes(b"cache")

    with pytest.raises(StagingError, match="engine-contract gate"):
        stage_candidate(
            module_root="vul803",
            candidate=candidate,
            game_root=game_root,
            evidence_root=tmp_path / "evidence",
            process_checker=lambda: False,
            audit_runner=_passing_audit,
            engine_audit_runner=lambda *args, **kwargs: {
                "export_ready": False,
                "blocking_issues": ["room MDL has no embedded AABB node"],
            },
        )

    assert installed.read_bytes() == b"installed"
    assert cache.read_bytes() == b"cache"
    assert not (tmp_path / "evidence").exists()
