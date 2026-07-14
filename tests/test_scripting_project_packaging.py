from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.core.scripting.packaging import (
    NarrativePackagingService,
    PackageResource,
    inspect_gff_resource,
    inspect_narrative_archive,
)
from src.core.scripting.project import (
    PROJECT_FILE_NAME,
    LegacyNarrativeHistoryStore,
    NarrativeAssetDependency,
    NarrativeProjectService,
    NarrativeExportHistoryStore,
    NarrativeRevisionStore,
    RecentNarrativeProjectStore,
)


def _project(tmp_path: Path):
    return NarrativeProjectService.create_project(tmp_path / "cantina_story", name="Cantina Story", game="K2")


def test_project_manifest_is_portable_typed_and_preserves_extensions(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = tmp_path / "outside.nss"
    source.write_text("void main() { }\n", encoding="utf-8")
    dependency = NarrativeAssetDependency("story_run", "ncs", relation="compiles_to")
    vanilla_dependency = NarrativeAssetDependency("k_con_talkedto", "ncs", scope="game")
    script = NarrativeProjectService.import_asset(
        project,
        source,
        resref="story_run",
        dependencies=(dependency, vanilla_dependency),
    )

    manifest_path = Path(project.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["file_type"] == "GhostStudioNarrativeProject"
    assert payload["schema_version"] == 1
    assert payload["assets"][0]["path"] == "scripts/story_run.nss"
    assert payload["assets"][0]["dependencies"][1]["scope"] == "game"
    assert "void main" not in manifest_path.read_text(encoding="utf-8")
    assert script.role == "source"
    assert any(issue.code == "narrative_project.dependency_missing" for issue in NarrativeProjectService.validate_project(project))

    compiled = tmp_path / "story_run.ncs"
    compiled.write_bytes(b"NCS V1.0\x00test")
    NarrativeProjectService.import_asset(project, compiled, resref="story_run")
    assert not any(issue.blocking for issue in NarrativeProjectService.validate_project(project))

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["community_extension"] = {"owner": "modder"}
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = NarrativeProjectService.load_project(manifest_path)
    NarrativeProjectService.save_project(loaded)
    roundtrip = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert roundtrip["community_extension"] == {"owner": "modder"}
    assert roundtrip["revision"] == payload["revision"] + 1


def test_project_rejects_escape_paths_and_nonempty_create_target(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        NarrativeProjectService.create_project(occupied, name="Unsafe")
    assert (occupied / "keep.txt").read_text(encoding="utf-8") == "keep"

    project = _project(tmp_path)
    payload = json.loads(Path(project.manifest_path).read_text(encoding="utf-8"))
    payload["assets"] = [
        {
            "asset_id": "asset_escape",
            "resref": "escape",
            "restype": "nss",
            "path": "../outside.nss",
        }
    ]
    Path(project.manifest_path).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="escape"):
        NarrativeProjectService.load_project(project.manifest_path)


def test_legacy_ghostscripter_project_import_preserves_tree_resources_and_history(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy"
    (legacy / "scripts").mkdir(parents=True)
    (legacy / "quests").mkdir()
    source_text = "void main() { /* legacy */ }\n"
    (legacy / "scripts" / "legacy_run.nss").write_text(source_text, encoding="utf-8")
    quest_payload = {"quest_id": "legacy_quest", "states": [{"id": 10}]}
    (legacy / "quests" / "legacy_quest.json").write_text(json.dumps(quest_payload), encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "project_id": "legacy-project-id",
        "name": "Legacy Story",
        "version": "3.6.0",
        "author": "Modder",
        "description": "Preserve me",
        "target_game": "K2",
        "dependencies": [{"name": "Community Patch", "version": "1.0"}],
        "twoda_edits": {"appearance.2da": [{"row": "900", "label": "LEGACY_NPC"}]},
        "artifacts": {
            "scripts": [{"path": "scripts/legacy_run.nss", "name": "legacy_run"}],
            "quests": [{"path": "quests/legacy_quest.json"}],
        },
    }
    (legacy / "project.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    database = tmp_path / "ghostscripter.db"
    quest_snapshot_text = json.dumps(
        {"quest_id": "legacy_quest", "states": [{"id": 10}], "note": "café"},
        ensure_ascii=False,
    )
    dialogue_snapshot_text = json.dumps(
        {"dlg_name": "legacy_dlg", "entries": [{"text": "Exact archived line"}]},
        ensure_ascii=False,
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE script_history (project_id TEXT, script_name TEXT, content TEXT, saved_at TEXT, revision INTEGER)"
        )
        connection.execute(
            "INSERT INTO script_history VALUES (?, ?, ?, ?, ?)",
            ("legacy-project-id", "legacy_run", source_text, "2026-07-13T00:00:00", 1),
        )
        connection.execute(
            "CREATE TABLE quest_snapshots (project_id TEXT, quest_id TEXT, data_json TEXT, saved_at TEXT, revision INTEGER)"
        )
        connection.execute(
            "INSERT INTO quest_snapshots VALUES (?, ?, ?, ?, ?)",
            ("legacy-project-id", "legacy_quest", quest_snapshot_text, "2026-07-13T00:15:00", 2),
        )
        connection.execute(
            "CREATE TABLE dialogue_snapshots (project_id TEXT, dlg_name TEXT, data_json TEXT, saved_at TEXT, revision INTEGER)"
        )
        connection.execute(
            "INSERT INTO dialogue_snapshots VALUES (?, ?, ?, ?, ?)",
            ("legacy-project-id", "legacy_dlg", dialogue_snapshot_text, "2026-07-13T00:30:00", 3),
        )
        connection.execute(
            "CREATE TABLE export_history (project_id TEXT, export_type TEXT, output_path TEXT, files_count INTEGER, exported_at TEXT, success INTEGER)"
        )
        connection.execute(
            "INSERT INTO export_history VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-project-id", "erf", "C:/legacy/story.erf", 3, "2026-07-13T01:00:00", 1),
        )
        connection.execute("CREATE TABLE user_prefs (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO user_prefs VALUES (?, ?)", ("editor_font_size", "14"))
        connection.execute(
            "CREATE TABLE recent_projects (project_id TEXT, name TEXT, path TEXT, game TEXT, last_opened TEXT, created TEXT)"
        )
        connection.execute(
            "INSERT INTO recent_projects VALUES (?, ?, ?, ?, ?, ?)",
            ("legacy-project-id", "Legacy Story", str(legacy), "K2", "2026-07-13", "2026-07-12"),
        )

    result = NarrativeProjectService.import_legacy_ghostscripter_project(
        legacy,
        tmp_path / "migrated",
        legacy_database=database,
    )

    assert result.project.name == "Legacy Story"
    assert result.history_rows == 4
    assert result.preference_rows == 1
    assert result.recent_project_rows == 1
    assert "legacy_run.nss" in result.imported_resources
    assert (legacy / "scripts" / "legacy_run.nss").read_text(encoding="utf-8") == source_text
    migrated_root = Path(result.project.root_path)
    assert (migrated_root / "legacy_source" / "quests" / "legacy_quest.json").read_text(encoding="utf-8") == json.dumps(quest_payload)
    assert (migrated_root / "scripts" / "legacy_run.nss").read_text(encoding="utf-8") == source_text
    history = json.loads((migrated_root / "legacy_import" / "ghostscripter-history.json").read_text(encoding="utf-8"))
    assert history["rows"][0]["table"] == "script_history"
    settings = json.loads((migrated_root / "legacy_import" / "ghostscripter-settings.json").read_text(encoding="utf-8"))
    assert settings["preferences"][0]["key"] == "editor_font_size"
    assert settings["recent_projects"][0]["project_id"] == "legacy-project-id"
    export_rows = NarrativeExportHistoryStore(result.project).list()
    assert len(export_rows) == 1
    assert export_rows[0].operation == "legacy_erf"
    assert export_rows[0].destination == "C:/legacy/story.erf"
    assert export_rows[0].metadata["legacy"] is True

    legacy_store = LegacyNarrativeHistoryStore(result.project)
    legacy_rows = legacy_store.list()
    assert [row.kind for row in legacy_rows] == [
        "script",
        "quest",
        "dialogue",
        "legacy_project",
        "quest",
        "twoda_edits",
        "dependencies",
        "legacy_settings",
        "preferences",
        "recent_projects",
    ]
    assert [row.record_id for row in legacy_rows] == [row.record_id for row in legacy_store.list()]
    assert next(row for row in legacy_rows if row.source_table == "project_artifact_quests").content == json.dumps(
        quest_payload
    )
    assert "appearance.2da" in next(row for row in legacy_rows if row.kind == "twoda_edits").content
    assert "Community Patch" in next(row for row in legacy_rows if row.kind == "dependencies").content
    assert "editor_font_size" in next(row for row in legacy_rows if row.kind == "preferences").content
    assert "Legacy Story" in next(row for row in legacy_rows if row.kind == "recent_projects").content
    history_before = (migrated_root / "legacy_import" / "ghostscripter-history.json").read_bytes()
    for row in legacy_rows:
        output = tmp_path / f"recovered_{row.record_id}"
        recovery_manifest = legacy_store.recover(row.record_id, output)
        recovered = output / row.suggested_filename
        assert recovered.read_text(encoding="utf-8") == row.content
        recovery = json.loads(recovery_manifest.read_text(encoding="utf-8"))
        assert recovery["record_id"] == row.record_id
        assert recovery["sha256"] == row.sha256
        assert recovery["byte_count"] == row.byte_count
        assert recovery["source"]["table"] == row.source_table
        assert recovery["source"]["row"] == row.source_row
        if row.kind in {"quest", "dialogue"}:
            assert recovery["valid_json"] is True
    assert (migrated_root / "legacy_import" / "ghostscripter-history.json").read_bytes() == history_before

    with pytest.raises(FileExistsError, match="new output folder"):
        legacy_store.recover(legacy_rows[0].record_id, tmp_path / f"recovered_{legacy_rows[0].record_id}")
    with pytest.raises(ValueError, match="outside the open project"):
        legacy_store.recover(legacy_rows[0].record_id, migrated_root / "unsafe_recovery")
    assert not (migrated_root / "unsafe_recovery").exists()


def test_recent_projects_are_explicit_json_and_deduplicated(tmp_path: Path) -> None:
    first = _project(tmp_path)
    second = NarrativeProjectService.create_project(tmp_path / "second", name="Second", game="K1")
    registry_path = tmp_path / "preferences" / "recent-narrative.json"
    store = RecentNarrativeProjectStore(registry_path, limit=2)
    assert store.list() == ()
    store.remember(first)
    store.remember(second)
    rows = store.remember(first)
    assert [row.project_id for row in rows] == [first.project_id, second.project_id]
    assert json.loads(registry_path.read_text(encoding="utf-8"))["file_type"] == "GhostStudioRecentNarrativeProjects"
    assert [row.project_id for row in store.forget(first.project_id)] == [second.project_id]


def test_revision_snapshot_is_immutable_and_materializes_without_overwrite(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = tmp_path / "line.dlg"
    source.write_bytes(b"original dialogue bytes")
    asset = NarrativeProjectService.import_asset(project, source, resref="cantina_line")
    store = NarrativeRevisionStore(project)
    revision = store.create(message="Before rewrite", author="tester")

    live_path = Path(project.root_path) / asset.path
    live_path.write_bytes(b"changed dialogue bytes")
    recovered_manifest = store.materialize(revision.revision_id, tmp_path / "recovered")
    assert recovered_manifest.name == PROJECT_FILE_NAME
    assert (tmp_path / "recovered" / asset.path).read_bytes() == b"original dialogue bytes"
    assert live_path.read_bytes() == b"changed dialogue bytes"
    assert store.list()[0].message == "Before rewrite"

    with pytest.raises(FileExistsError, match="never overwritten"):
        store.materialize(revision.revision_id, tmp_path / "recovered")


@pytest.mark.parametrize("archive_type, extension", [("ERF", "erf"), ("MOD", "mod"), ("SAV", "sav")])
def test_archive_build_uses_pykotor_and_exact_resource_readback(
    tmp_path: Path, archive_type: str, extension: str
) -> None:
    resources = (
        PackageResource("story_run", "ncs", b"NCS V1.0\x00compiled"),
        PackageResource("story_dlg", "dlg", b"dialogue payload"),
    )
    output = tmp_path / f"story.{extension}"
    result = NarrativePackagingService.build_archive(resources, output, archive_type=archive_type)
    assert result.ok
    inspection = inspect_narrative_archive(output)
    assert inspection.archive_type == archive_type
    assert {(row.resref, row.restype, row.data) for row in inspection.resources} == {
        (row.resref, row.restype, row.data) for row in resources
    }
    assert json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))["engine_proof"] == "not_recorded"

    original = output.read_bytes()
    blocked = NarrativePackagingService.build_archive(resources, output, archive_type=archive_type)
    assert not blocked.ok
    assert output.read_bytes() == original


def test_gff_blueprint_inspection_reports_typed_metadata_without_mutation() -> None:
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff

    gff = GFF(GFFContent.UTC)
    gff.root.set_string("Tag", "cantina_npc")
    gff.root.set_resref("TemplateResRef", ResRef("cantina_npc"))
    gff.root.set_uint32("Appearance_Type", 42)
    gff.root.set_resref("ScriptSpawn", ResRef("story_spawn"))
    data = bytes(bytes_gff(gff))
    metadata = inspect_gff_resource(data, restype="utc")
    assert metadata["content"] == "UTC"
    assert metadata["blueprint_kind"] == "creature"
    assert metadata["is_blueprint"] is True
    assert metadata["semantic_fields"]["Tag"] == "cantina_npc"
    assert metadata["semantic_fields"]["TemplateResRef"] == "cantina_npc"
    assert metadata["field_count"] == 4
    assert metadata["sha256"]


def test_override_is_staged_first_and_conflicts_require_explicit_backup(tmp_path: Path) -> None:
    first_resources = (PackageResource("story_run", "ncs", b"first compiled script"),)
    stage = tmp_path / "override-stage"
    staged = NarrativePackagingService.stage_override(first_resources, stage, game="K2")
    assert staged.ok
    game_root = tmp_path / "fake-k2"
    game_root.mkdir()
    assert not (game_root / "Override").exists()  # Staging cannot mutate the game install.

    installed = NarrativePackagingService.install_override(stage, game_root)
    assert installed.ok
    destination = game_root / "Override" / "story_run.ncs"
    assert destination.read_bytes() == b"first compiled script"

    second_stage = tmp_path / "override-stage-2"
    assert NarrativePackagingService.stage_override(
        (PackageResource("story_run", "ncs", b"second compiled script"),),
        second_stage,
        game="K2",
    ).ok
    backups_before = tuple((game_root / "GhostStudioBackups").glob("*"))
    blocked = NarrativePackagingService.install_override(second_stage, game_root)
    assert not blocked.ok
    assert destination.read_bytes() == b"first compiled script"
    assert tuple((game_root / "GhostStudioBackups").glob("*")) == backups_before

    replaced = NarrativePackagingService.install_override(second_stage, game_root, on_conflict="backup")
    assert replaced.ok
    assert destination.read_bytes() == b"second compiled script"
    assert (Path(replaced.backup_path) / "Override" / "story_run.ncs").read_bytes() == b"first compiled script"
    assert Path(replaced.receipt_path).is_file()


def test_override_stage_blocks_module_archives(tmp_path: Path) -> None:
    result = NarrativePackagingService.stage_override(
        (PackageResource("storymod", "mod", b"MOD V1.0"),),
        tmp_path / "stage",
        game="K1",
    )
    assert not result.ok
    assert result.issues[0].code == "override_stage.archive_resource_blocked"
    assert not (tmp_path / "stage").exists()


def test_game_global_tlk_is_blocked_from_module_and_override_delivery(tmp_path: Path) -> None:
    resources = (PackageResource("dialog", "tlk", b"TLK V3.0\x00replacement"),)

    archive = NarrativePackagingService.build_archive(
        resources,
        tmp_path / "unsafe.mod",
        archive_type="MOD",
    )
    assert not archive.ok
    assert archive.issues[0].code == "narrative_package.global_resource_blocked"
    assert not (tmp_path / "unsafe.mod").exists()

    stage = NarrativePackagingService.stage_override(
        resources,
        tmp_path / "unsafe-stage",
        game="K2",
    )
    assert not stage.ok
    assert stage.issues[0].code == "override_stage.global_resource_blocked"
    assert not (tmp_path / "unsafe-stage").exists()


def test_global_tlk_install_is_backed_up_receipted_and_restorable(tmp_path: Path) -> None:
    from src.core.scripting.data_authoring import TalkTableDocument

    original_doc = TalkTableDocument()
    original_doc.add_entry("Original retail-style string")
    original = original_doc.to_bytes()
    replacement_doc = TalkTableDocument.load(original)
    replacement_doc.update_entry(0, text="GhostStudio replacement")
    replacement = replacement_doc.to_bytes()

    game_root = tmp_path / "fake-k2"
    game_root.mkdir()
    (game_root / "dialog.tlk").write_bytes(original)

    installed = NarrativePackagingService.install_global_tlk(
        replacement,
        game_root,
        game="K2",
    )
    assert installed.ok
    assert (game_root / "dialog.tlk").read_bytes() == replacement
    assert Path(installed.backup_path).read_bytes() == original
    assert Path(installed.receipt_path).is_file()

    restored = NarrativePackagingService.restore_global_tlk(installed.receipt_path, game_root)
    assert restored.ok
    assert restored.restored
    assert (game_root / "dialog.tlk").read_bytes() == original
    assert Path(restored.backup_path).read_bytes() == replacement
