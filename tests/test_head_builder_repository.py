"""Focused persistence contracts for Custom Head Builder projects."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from src.core.characters.head_builder_project import (
    HEAD_BUILDER_PROJECT_SCHEMA,
    HeadBuilderProject,
)
from src.core.project.head_builder_repository import (
    FileHeadBuilderProjectRepository,
    HeadBuilderProjectConflictError,
    HeadBuilderProjectFormatError,
)


def test_save_load_roundtrip_preserves_unknown_fields_and_relocates_project_paths(
    tmp_path: Path,
) -> None:
    original_dir = tmp_path / "original"
    asset_dir = original_dir / "assets"
    asset_dir.mkdir(parents=True)
    source = asset_dir / "hero_head.fbx"
    source.write_bytes(b"fbx")

    project = HeadBuilderProject.new(display_name="Hero Head")
    project.game_install_dir = r"H:\Games\KOTOR2"
    project.output_project_dir = str(original_dir / "build")
    project.import_art = {"source_path": str(source)}
    project.extensions["_unknown_top_level"] = {
        "future_editor_state": {"source_path": str(original_dir / "future.bin")}
    }

    repository = FileHeadBuilderProjectRepository()
    path = original_dir / "hero.ghosthead.json"
    document = repository.new_document(project, path)
    repository.save(document)

    serialized = json.loads(path.read_text(encoding="utf-8"))
    assert serialized["game_install_dir"] == r"H:\Games\KOTOR2"
    assert serialized["output_project_dir"] == "./build"
    assert serialized["import_art"]["source_path"] == "./assets/hero_head.fbx"
    assert (
        serialized["future_editor_state"]["source_path"]
        == "./future.bin"
    )

    relocated_dir = tmp_path / "relocated"
    shutil.copytree(original_dir, relocated_dir)
    loaded = repository.load(relocated_dir / path.name)

    assert loaded.project.display_name == "Hero Head"
    assert loaded.project.import_art["source_path"] == str(
        (relocated_dir / "assets" / "hero_head.fbx").resolve()
    )
    assert loaded.project.output_project_dir == str(
        (relocated_dir / "build").resolve()
    )
    assert loaded.project.game_install_dir == r"H:\Games\KOTOR2"
    assert loaded.project.to_dict()["future_editor_state"]["source_path"] == str(
        (relocated_dir / "future.bin").resolve()
    )


def test_save_detects_external_change_and_does_not_overwrite_it(
    tmp_path: Path,
) -> None:
    repository = FileHeadBuilderProjectRepository()
    path = tmp_path / "conflict.ghosthead.json"
    document = repository.new_document(HeadBuilderProject.new(), path)
    repository.save(document)
    externally_changed = path.read_text(encoding="utf-8") + "\n"
    path.write_text(externally_changed, encoding="utf-8")
    document.project.display_name = "Unsaved local change"

    with pytest.raises(HeadBuilderProjectConflictError, match="changed on disk"):
        repository.save(document)

    assert path.read_text(encoding="utf-8") == externally_changed


def test_save_as_requires_explicit_force_for_existing_untracked_destination(
    tmp_path: Path,
) -> None:
    repository = FileHeadBuilderProjectRepository()
    source_path = tmp_path / "source.ghosthead.json"
    destination = tmp_path / "existing.ghosthead.json"
    document = repository.new_document(HeadBuilderProject.new(), source_path)
    repository.save(document)
    destination.write_text("do not replace", encoding="utf-8")

    with pytest.raises(
        HeadBuilderProjectConflictError,
        match="without its revision",
    ):
        repository.save(document, destination)

    assert destination.read_text(encoding="utf-8") == "do not replace"


def test_save_detects_external_deletion_instead_of_silently_recreating(
    tmp_path: Path,
) -> None:
    repository = FileHeadBuilderProjectRepository()
    path = tmp_path / "deleted.ghosthead.json"
    document = repository.new_document(HeadBuilderProject.new(), path)
    repository.save(document)
    path.unlink()

    with pytest.raises(HeadBuilderProjectConflictError, match="was deleted"):
        repository.save(document)

    assert path.exists() is False


def test_atomic_replace_failure_preserves_existing_file_and_project_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.core.project.head_builder_repository as repository_module

    repository = FileHeadBuilderProjectRepository()
    path = tmp_path / "atomic.ghosthead.json"
    document = repository.new_document(HeadBuilderProject.new(), path)
    repository.save(document)
    original_bytes = path.read_bytes()
    original_timestamp = document.project.updated_at
    document.project.display_name = "Changed"

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        repository.save(document)

    assert path.read_bytes() == original_bytes
    assert document.project.updated_at == original_timestamp
    assert not list(tmp_path.glob(".atomic.ghosthead.json.*.tmp"))


def test_load_migrates_v0_and_preserves_unknown_top_level_fields(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.ghosthead.json"
    path.write_text(
        json.dumps(
            {
                "schema": HEAD_BUILDER_PROJECT_SCHEMA,
                "version": 0,
                "project_name": "Legacy Head",
                "target_game": "k1",
                "resource_policy": "stock_only",
                "future_value": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )

    document = FileHeadBuilderProjectRepository().load(path)

    assert document.migrated_from_version == 0
    assert document.project.display_name == "Legacy Head"
    assert document.project.game.value == "K1"
    assert document.project.to_dict()["future_value"] == {"enabled": True}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            '{"schema":"ghostrigger.head_builder_project","schema":"duplicate"}',
            "Duplicate JSON key",
        ),
        (
            '{"schema":"ghostrigger.head_builder_project","version":999}',
            "newer Ghost Studio",
        ),
        (
            '{"schema":"ghostrigger.head_builder_project","version":1,'
            '"extensions":{"value":NaN}}',
            "Non-finite JSON number",
        ),
        ("[]", "root must be a JSON object"),
    ],
)
def test_load_rejects_ambiguous_or_unsupported_json(
    tmp_path: Path,
    text: str,
    message: str,
) -> None:
    path = tmp_path / "invalid.ghosthead.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(HeadBuilderProjectFormatError, match=message):
        FileHeadBuilderProjectRepository().load(path)
