from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]


def test_project_history_page_presents_inventory_and_emits_user_intent() -> None:
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import PAGE_ROW_ROLE, QtScriptingProjectHistoryPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtScriptingProjectHistoryPage()
    events: dict[str, list[object]] = {
        "new": [],
        "asset": [],
        "snapshot": [],
        "recover": [],
        "legacy_recover": [],
        "legacy_open": [],
        "recent": [],
    }
    page.newProjectRequested.connect(events["new"].append)
    page.assetActivated.connect(events["asset"].append)
    page.createRevisionRequested.connect(events["snapshot"].append)
    page.recoverRevisionRequested.connect(events["recover"].append)
    page.recoverLegacyHistoryRequested.connect(events["legacy_recover"].append)
    page.openLegacyQuestRequested.connect(events["legacy_open"].append)
    page.recentProjectActivated.connect(events["recent"].append)
    try:
        page.set_project(
            {
                "project_id": "narrative_test",
                "name": "Cantina Story",
                "game": "K2",
                "revision": 7,
                "manifest_path": "C:/mods/cantina/ghoststudio-narrative.json",
                "status": "ready",
            }
        )
        page.set_asset_rows(
            [
                {
                    "asset_id": "asset_script",
                    "resref": "story_run",
                    "restype": "nss",
                    "role": "source",
                    "path": "scripts/story_run.nss",
                    "dependencies": [{"resref": "story_run", "restype": "ncs"}],
                    "status": "tracked",
                },
                {
                    "asset_id": "asset_dialogue",
                    "resref": "story_dlg",
                    "restype": "dlg",
                    "role": "runtime",
                    "path": "dialogues/story_dlg.dlg",
                    "dependencies": [],
                    "status": "ready",
                },
            ]
        )
        page.set_revision_rows(
            [
                {
                    "revision_id": "20260713_test",
                    "created_at": "2026-07-13T23:00:00Z",
                    "message": "Dialogue pass",
                    "project_revision": 7,
                    "asset_count": 2,
                }
            ]
        )
        page.set_recent_rows(
            [
                {
                    "project_id": "narrative_test",
                    "name": "Cantina Story",
                    "game": "K2",
                    "manifest_path": "C:/mods/cantina/ghoststudio-narrative.json",
                    "last_opened_at": "2026-07-13T23:00:00Z",
                }
            ]
        )
        page.set_legacy_history_rows(
            [
                {
                    "record_id": "legacy_quest_000001_deadbeef1234",
                    "kind": "quest",
                    "identity": "legacy_quest",
                    "created_at": "2026-07-13T22:30:00Z",
                    "revision": 4,
                    "summary": "Legacy quest snapshot revision 4",
                    "content": '{"quest_id":"legacy_quest","states":[{"id":10}]}',
                    "suggested_filename": "legacy_quest.quest.json",
                    "source_table": "quest_snapshots",
                    "source_row_index": 1,
                    "source_row": {"table": "quest_snapshots", "quest_id": "legacy_quest"},
                    "byte_count": 51,
                    "sha256": "deadbeef1234",
                }
            ]
        )
        page.set_project_issues(
            [{"severity": "warning", "asset_id": "asset_script", "message": "Source changed"}]
        )

        assert page.objectName() == "scriptingStudioProjectHistoryPage"
        assert page.property("ghostLayoutId") == "scriptingStudioProjectHistory"
        assert page.project_name_label.text() == "Cantina Story"
        assert page.asset_model.rowCount() == 2
        assert page.revision_view.topLevelItemCount() == 1
        assert page.legacy_history_view.topLevelItemCount() == 1
        assert page.recent_view.topLevelItemCount() == 1
        assert page.issue_view.topLevelItemCount() == 1

        page.asset_search_edit.setText("dialogue")
        app.processEvents()
        assert page.asset_proxy.rowCount() == 1
        page._activate_asset(page.asset_proxy.index(0, 0))
        assert events["asset"][0]["asset_id"] == "asset_dialogue"

        page.target_game_combo.setCurrentText("K1")
        page.new_project_button.click()
        assert events["new"] == [{"game": "K1"}]
        page.revision_message_edit.setText("Before branching rewrite")
        page.create_revision_button.click()
        assert events["snapshot"] == ["Before branching rewrite"]
        page.revision_view.setCurrentItem(page.revision_view.topLevelItem(0))
        page.recover_revision_button.click()
        assert events["recover"] == ["20260713_test"]
        page.legacy_history_view.setCurrentItem(page.legacy_history_view.topLevelItem(0))
        app.processEvents()
        assert "legacy_quest.quest.json" in page.legacy_history_details.toPlainText()
        assert "quest_snapshots" in page.legacy_history_details.toPlainText()
        page.recover_legacy_history_button.click()
        assert events["legacy_recover"] == ["legacy_quest_000001_deadbeef1234"]
        assert page.open_legacy_quest_button.isEnabled()
        page.open_legacy_quest_button.click()
        assert events["legacy_open"] == ["legacy_quest_000001_deadbeef1234"]
        page.recent_view.setCurrentItem(page.recent_view.topLevelItem(0))
        page.open_recent_button.click()
        assert events["recent"] == ["C:/mods/cantina/ghoststudio-narrative.json"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_package_override_page_keeps_staging_and_install_as_separate_intents(tmp_path: Path) -> None:
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import QtScriptingPackageOverridePage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtScriptingPackageOverridePage()
    packages: list[dict[str, object]] = []
    stages: list[dict[str, object]] = []
    installs: list[dict[str, object]] = []
    page.packageBuildRequested.connect(lambda row: packages.append(dict(row)))
    page.stageOverrideRequested.connect(lambda row: stages.append(dict(row)))
    page.installOverrideRequested.connect(lambda row: installs.append(dict(row)))
    fake_game = tmp_path / "KOTOR2"
    fake_game.mkdir()
    try:
        page.set_package_resources(
            [
                {
                    "resref": "story_run",
                    "restype": "ncs",
                    "filename": "story_run.ncs",
                    "byte_count": 128,
                    "role": "runtime",
                    "status": "ready",
                }
            ]
        )
        assert not page.build_package_button.isEnabled()
        page.set_readiness({"ready": True, "summary": "Ready to package"}, issues=[])
        assert page.build_package_button.isEnabled()
        assert page.stage_override_button.isEnabled()

        page.archive_type_combo.setCurrentIndex(page.archive_type_combo.findData("ERF"))
        page.package_output_edit.setText(str(tmp_path / "story.erf"))
        page.include_source_check.setChecked(True)
        page.overwrite_package_check.setChecked(True)
        page.build_package_button.click()
        assert packages == [
            {
                "archive_type": "ERF",
                "output_path": str(tmp_path / "story.erf"),
                "include_source": True,
                "overwrite": True,
            }
        ]

        stage_path = tmp_path / "stage"
        page.stage_output_edit.setText(str(stage_path))
        page.replace_owned_stage_check.setChecked(True)
        page.stage_override_button.click()
        assert stages[0]["output_dir"] == str(stage_path)
        assert stages[0]["replace_owned"] is True
        assert not fake_game.joinpath("Override").exists()  # A page signal cannot write to the game.

        page.set_override_stage_result({"committed": True, "stage_path": str(stage_path)})
        assert not page.install_override_button.isEnabled()
        page.game_root_edit.setText(str(fake_game))
        assert page.install_override_button.isEnabled()
        assert page.conflict_policy_combo.currentData() == "block"
        page.conflict_policy_combo.setCurrentIndex(page.conflict_policy_combo.findData("backup"))
        page.install_override_button.click()
        assert installs == [
            {
                "stage_path": str(stage_path),
                "game_root": str(fake_game),
                "on_conflict": "backup",
            }
        ]
        assert not fake_game.joinpath("Override").exists()

        page.set_archive_result({"committed": True, "output_path": str(tmp_path / "story.erf")})
        page.set_install_result(
            {"committed": True, "installed": ["story_run.ncs"], "backup_path": str(tmp_path / "backup")}
        )
        assert "Verified archive" in page.package_result_label.text()
        assert "Installed 1 file" in page.install_result_label.text()
    finally:
        page.deleteLater()
        app.processEvents()


def test_project_controller_presents_and_recovers_legacy_history(tmp_path: Path) -> None:
    import json

    from PySide6 import QtWidgets
    from src.core.scripting.project import NarrativeProjectService
    from src.gui.controllers.scripting_project_controller import ScriptingProjectController
    from src.gui.windows.qt_scripting_project_package_pages import PAGE_ROW_ROLE, QtScriptingProjectHistoryPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project = NarrativeProjectService.create_project(tmp_path / "project", name="Migrated Story", game="K2")
    legacy_import = Path(project.root_path) / "legacy_import"
    legacy_import.mkdir()
    snapshot_text = '{"quest_id":"archived_quest","states":[{"id":20}]}'
    (legacy_import / "ghostscripter-history.json").write_text(
        json.dumps(
            {
                "file_type": "GhostStudioLegacyGhostScripterHistory",
                "schema_version": 1,
                "legacy_project_id": "legacy-project",
                "rows": [
                    {
                        "table": "quest_snapshots",
                        "project_id": "legacy-project",
                        "quest_id": "archived_quest",
                        "data_json": snapshot_text,
                        "saved_at": "2026-07-13T20:00:00Z",
                        "revision": 2,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    page = QtScriptingProjectHistoryPage()
    window = SimpleNamespace(project_history_page=page, package_override_page=None)
    controller = ScriptingProjectController(
        window,
        recent_store_path=tmp_path / "recent-projects.json",
    )
    opened_quests: list[dict[str, object]] = []
    controller.legacyQuestOpened.connect(opened_quests.append)
    try:
        controller._activate_project(project)
        assert page.legacy_history_view.topLevelItemCount() == 1
        item = page.legacy_history_view.topLevelItem(0)
        page.legacy_history_view.setCurrentItem(item)
        app.processEvents()
        row = dict(item.data(0, PAGE_ROW_ROLE) or {})
        output = tmp_path / "recovered_legacy_quest"
        manifest = controller.recover_legacy_history(str(row["record_id"]), output)
        assert Path(manifest).is_file()
        assert (output / "archived_quest.quest.json").read_text(encoding="utf-8") == snapshot_text
        assert controller.open_legacy_quest_history(str(row["record_id"]))
        assert opened_quests[0]["content"] == snapshot_text
    finally:
        page.deleteLater()
        controller.deleteLater()
        app.processEvents()


def test_project_package_pages_use_theme_layout_hooks_without_hardcoded_palette() -> None:
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import (
        QtScriptingPackageOverridePage,
        QtScriptingProjectHistoryPage,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project_page = QtScriptingProjectHistoryPage()
    package_page = QtScriptingPackageOverridePage()
    layout = SimpleNamespace(spacing_value=lambda name, default: 11 if name == "splitterHandleWidth" else 9)
    try:
        for page in (project_page, package_page):
            page.apply_ghost_theme(object())
            page.apply_ghost_layout(layout)
        assert project_page.project_splitter.handleWidth() == 11
        assert package_page.package_splitter.handleWidth() == 11
    finally:
        project_page.deleteLater()
        package_page.deleteLater()
        app.processEvents()

    source = (ROOT / "src/gui/windows/qt_scripting_project_package_pages.py").read_text(encoding="utf-8")
    assert "QFileDialog" not in source
    assert "setStyleSheet" not in source
    assert "QColor(" not in source
    assert "install_override(" not in source
    assert "write_bytes(" not in source
    assert "Stage is safe and does not touch the game" in source
    assert "Recover as New Copy" in source


def test_package_page_preserves_advanced_sav_container_choice() -> None:
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import QtScriptingPackageOverridePage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtScriptingPackageOverridePage()
    try:
        index = page.archive_type_combo.findData("SAV")
        assert index >= 0
        page.archive_type_combo.setCurrentIndex(index)
        assert "save-game container" in page.archive_type_combo.currentText().casefold()
        assert any(
            "complete playable save" in label.text().casefold()
            for label in page.findChildren(QtWidgets.QLabel)
        )
    finally:
        page.deleteLater()
        app.processEvents()
