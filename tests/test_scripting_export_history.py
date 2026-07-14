from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]


def _canonical_project_controller():
    """Load the canonical source before its native payload is regenerated."""

    path = ROOT / "src/gui/controllers/scripting_project_controller.py"
    spec = importlib.util.spec_from_file_location("_ghoststudio_scripting_project_controller_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ScriptingProjectController


def _project(tmp_path: Path):
    from src.core.scripting.project import NarrativeProjectService

    return NarrativeProjectService.create_project(tmp_path / "narrative", name="History Proof", game="K2")


def test_export_history_persists_exact_hashes_filters_and_future_fields(tmp_path: Path) -> None:
    from src.core.scripting.project import NarrativeExportHistoryStore

    project = _project(tmp_path)
    store = NarrativeExportHistoryStore(project)
    first_bytes = b"NCS V1.0\x00compiled-story"
    first = store.record(
        operation="package",
        outcome="succeeded",
        destination=tmp_path / "story.mod",
        inputs=({"filename": "story_run.ncs", "data": first_bytes, "source_asset_id": "asset_run"},),
        receipt_path=tmp_path / "story.mod.ghoststudio.json",
        summary="Exact archive readback passed; engine proof is still pending.",
        metadata={"archive_type": "MOD", "structural_readback": True},
    )
    assert first.input_hashes[0].sha256 == hashlib.sha256(first_bytes).hexdigest()
    assert first.input_hashes[0].byte_count == len(first_bytes)
    assert first.engine_proof == "not_recorded"

    raw = json.loads(store.path.read_text(encoding="utf-8"))
    raw["future_top_level"] = {"preserve": True}
    raw["records"][0]["future_record_field"] = [1, 2, 3]
    store.path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    second = store.record(
        operation="stage_override",
        outcome="failed",
        destination=tmp_path / "stage",
        inputs=({"filename": "story_run.ncs", "data": first_bytes},),
        issues=({"severity": "blocking", "code": "test", "message": "Blocked on purpose"},),
    )

    payload = json.loads(store.path.read_text(encoding="utf-8"))
    assert payload["future_top_level"] == {"preserve": True}
    assert payload["records"][0]["future_record_field"] == [1, 2, 3]
    assert [row.receipt_id for row in store.list(operation="package")] == [first.receipt_id]
    assert [row.receipt_id for row in store.list(outcome="failed")] == [second.receipt_id]
    assert [row.receipt_id for row in store.list(query=first.input_hashes[0].sha256[:20])] == [
        second.receipt_id,
        first.receipt_id,
    ]

    proven = store.set_engine_proof(first.receipt_id, "in_game_confirmed", evidence="plcaa manual warp")
    assert proven.engine_proof == "in_game_confirmed"
    assert proven.engine_proof_evidence == "plcaa manual warp"
    assert store.list(operation="package")[0].extensions["future_record_field"] == [1, 2, 3]


def test_revision_can_filter_and_recover_one_asset_without_touching_live_data(tmp_path: Path) -> None:
    from src.core.scripting.project import NarrativeProjectService, NarrativeRevisionStore

    project = _project(tmp_path)
    source_a = tmp_path / "story_run.nss"
    source_b = tmp_path / "story_line.dlg"
    source_a.write_bytes(b"void main() {}\n")
    source_b.write_bytes(b"dialogue-v1")
    asset_a = NarrativeProjectService.import_asset(project, source_a)
    asset_b = NarrativeProjectService.import_asset(project, source_b)
    store = NarrativeRevisionStore(project)
    revision = store.create(message="Before dialogue edit", author="tester")

    live_b = Path(project.root_path) / asset_b.path
    live_b.write_bytes(b"dialogue-v2")
    assert [row.revision_id for row in store.list_for_asset(asset_a.asset_id)] == [revision.revision_id]
    snapshot_assets = {row.asset_id: row for row in store.list_assets(revision.revision_id)}
    assert snapshot_assets[asset_b.asset_id].sha256 == hashlib.sha256(b"dialogue-v1").hexdigest()
    assert snapshot_assets[asset_b.asset_id].asset["resref"] == asset_b.resref

    recovery_root = tmp_path / "recovered-one-asset"
    metadata_path = store.materialize_asset(revision.revision_id, asset_b.asset_id, recovery_root)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["asset_id"] == asset_b.asset_id
    assert metadata["sha256"] == hashlib.sha256(b"dialogue-v1").hexdigest()
    assert (recovery_root / asset_b.path).read_bytes() == b"dialogue-v1"
    assert live_b.read_bytes() == b"dialogue-v2"
    with pytest.raises(FileExistsError, match="never overwritten"):
        store.materialize_asset(revision.revision_id, asset_b.asset_id, recovery_root)


def test_project_controller_records_package_stage_install_and_tlk_receipts(tmp_path: Path) -> None:
    from PySide6 import QtWidgets
    from src.core.scripting.data_authoring import TalkTableDocument
    from src.core.scripting.project import NarrativeExportHistoryStore, NarrativeProjectService
    ScriptingProjectController = _canonical_project_controller()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project = _project(tmp_path)
    NarrativeProjectService.write_asset(
        project,
        resref="story_run",
        restype="ncs",
        data=b"NCS V1.0\x00compiled",
        role="runtime",
    )
    tlk = TalkTableDocument()
    tlk.add_entry("GhostStudio history fixture")
    NarrativeProjectService.write_asset(
        project,
        resref="dialog",
        restype="tlk",
        data=tlk.to_bytes(),
        role="global_install",
    )
    controller = ScriptingProjectController(
        SimpleNamespace(project_history_page=None, package_override_page=None),
        recent_store_path=tmp_path / "recent.json",
    )
    controller._activate_project(project)

    package_result = controller.build_package(
        {"output_path": str(tmp_path / "story.mod"), "archive_type": "MOD", "overwrite": False}
    )
    assert package_result is not None and package_result.ok
    stage_result = controller.stage_override({"output_dir": str(tmp_path / "stage")})
    assert stage_result is not None and stage_result.ok
    game_root = tmp_path / "fake-k2"
    game_root.mkdir()
    (game_root / "dialog.tlk").write_bytes(tlk.to_bytes())
    install_result = controller.install_override(
        {"stage_path": str(tmp_path / "stage"), "game_root": str(game_root), "on_conflict": "block"}
    )
    assert install_result is not None and install_result.ok
    tlk_result = controller.install_global_tlk({"game_root": str(game_root), "resref": "dialog"})
    assert tlk_result is not None and tlk_result.ok
    restore_result = controller.restore_global_tlk(
        {"receipt_path": tlk_result.receipt_path, "game_root": str(game_root)}
    )
    assert restore_result is not None and restore_result.ok

    records = NarrativeExportHistoryStore(project).list()
    assert [row.operation for row in records] == [
        "restore_global_tlk",
        "install_global_tlk",
        "install_override",
        "stage_override",
        "package",
    ]
    assert all(row.outcome == "succeeded" for row in records)
    assert all(row.engine_proof == "not_recorded" for row in records)
    assert records[1].backup_path and records[1].receipt_path
    assert records[2].destination == str((game_root / "Override").resolve())
    assert records[2].input_hashes[0].filename == "story_run.ncs"
    assert records[-1].metadata["structural_readback"] is True
    app.processEvents()
