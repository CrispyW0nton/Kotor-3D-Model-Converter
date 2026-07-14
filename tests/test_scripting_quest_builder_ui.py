from __future__ import annotations

import json
import importlib
import os
from pathlib import Path
import sys
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]


def _prefer_canonical_quest_sources() -> None:
    """Test the canonical sources before payload generation copies them."""

    root_text = str(ROOT)
    if root_text in sys.path:
        sys.path.remove(root_text)
    sys.path.insert(0, root_text)
    for package_name, package_path in (
        ("src", ROOT / "src"),
        ("src.core", ROOT / "src" / "core"),
        ("src.core.scripting", ROOT / "src" / "core" / "scripting"),
        ("src.gui", ROOT / "src" / "gui"),
        ("src.gui.windows", ROOT / "src" / "gui" / "windows"),
        ("src.gui.controllers", ROOT / "src" / "gui" / "controllers"),
    ):
        package = importlib.import_module(package_name)
        paths = getattr(package, "__path__", None)
        if paths is not None:
            text = str(package_path)
            current = [str(item) for item in paths if str(item) != text]
            package.__path__ = [text, *current]
    for module_name in (
        "src.core.scripting.quest",
        "src.gui.windows.qt_scripting_quest_builder_page",
        "src.gui.windows.qt_scripting_project_package_pages",
        "src.gui.controllers.scripting_data_controller",
        "src.gui.controllers.scripting_project_controller",
    ):
        sys.modules.pop(module_name, None)


def test_quest_builder_page_edits_every_collection_and_preserves_unknown_fields() -> None:
    _prefer_canonical_quest_sources()
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_quest_builder_page import QtQuestScaffoldPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtQuestScaffoldPage()
    source = {
        "quest_id": "legacy_quest",
        "quest_name": "Legacy Quest",
        "legacy_top": {"keep": True},
        "variables": [
            {
                "variable_name": "LV_LEGACY",
                "variable_type": "Boolean",
                "default": False,
                "legacy_variable": "keep",
            }
        ],
        "states": [
            {
                "id": 0,
                "state_name": "Start",
                "spawned_npcs": ["legacy_npc"],
                "spawned_placeables": ["legacy_box"],
                "available_objectives": ["Talk to the guide"],
                "legacy_state": {"camera": 3},
            }
        ],
        "triggers": [
            {"type": "dialogue", "condition": "TRUE", "state": 0, "script": "legacy_run", "legacy_trigger": 9}
        ],
        "dialogues": ["legacy_dlg"],
        "scripts": ["legacy_run"],
        "dependencies": ["intro"],
        "conflicts_with": ["other_path"],
    }
    try:
        page.set_definition(source, source_name="legacy.quest.json")
        assert page.tabs.count() == 5
        assert page.variables_table.rowCount() == 1
        assert page.states_table.rowCount() == 1
        assert page.triggers_table.rowCount() == 1
        assert page.name_edit.text() == "Legacy Quest"
        assert page.states_table.item(0, 1).text() == "Start"
        assert page.states_table.item(0, 7).text() == "Talk to the guide"

        page.name_edit.setText("Edited Legacy Quest")
        page.variables_table.item(0, 3).setText("Edited variable")
        page.states_table.item(0, 3).setText("legacy_dlg")
        page.states_table.item(0, 4).setText("legacy_run")
        page.triggers_table.item(0, 1).setText("GetGlobalBoolean(\"LV_LEGACY\")")
        payload = page.definition_payload()

        assert payload["name"] == "Edited Legacy Quest"
        assert "quest_name" not in payload
        assert payload["legacy_top"] == {"keep": True}
        assert payload["variables"][0]["legacy_variable"] == "keep"
        assert payload["states"][0]["legacy_state"] == {"camera": 3}
        assert "state_name" not in payload["states"][0]
        assert "available_objectives" not in payload["states"][0]
        assert payload["states"][0]["name"] == "Start"
        assert payload["states"][0]["objectives"] == ["Talk to the guide"]
        assert payload["triggers"][0]["legacy_trigger"] == 9
        assert payload["states"][0]["spawned_npcs"] == ["legacy_npc"]
        assert payload["dialogues"] == ["legacy_dlg"]
        assert payload["dependencies"] == ["intro"]
        assert payload["conflicts"] == ["other_path"]
    finally:
        page.deleteLater()
        app.processEvents()


def test_quest_builder_row_metadata_follows_source_identity_through_sort_and_delete() -> None:
    _prefer_canonical_quest_sources()
    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.qt_scripting_quest_builder_page import QtQuestScaffoldPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtQuestScaffoldPage()
    source = {
        "quest_id": "identity_quest",
        "quest_name": "Identity Quest",
        "variables": [
            {"variable_name": "ZETA", "legacy_variable": "zeta-extra"},
            {"variable_name": "ALPHA", "legacy_variable": "alpha-extra"},
            {"variable_name": "DROP", "legacy_variable": "drop-extra"},
        ],
        "states": [
            {"state_id": 20, "state_name": "Twenty", "legacy_state": "twenty-extra"},
            {"state_id": 10, "state_name": "Ten", "legacy_state": "ten-extra"},
            {"state_id": 99, "state_name": "Drop", "legacy_state": "drop-extra"},
        ],
        "triggers": [
            {"trigger_type": "zeta", "legacy_trigger": "zeta-extra"},
            {"trigger_type": "alpha", "legacy_trigger": "alpha-extra"},
            {"trigger_type": "drop", "legacy_trigger": "drop-extra"},
        ],
    }

    def sort_and_remove(table: QtWidgets.QTableWidget, value: str) -> None:
        table.setSortingEnabled(True)
        table.sortItems(0, QtCore.Qt.AscendingOrder)
        matching = [row for row in range(table.rowCount()) if table.item(row, 0).text() == value]
        assert len(matching) == 1
        table.clearSelection()
        table.selectRow(matching[0])
        page._remove_rows(table)

    try:
        page.set_definition(source, source_name="identity.quest.json")
        sort_and_remove(page.variables_table, "DROP")
        sort_and_remove(page.states_table, "99")
        sort_and_remove(page.triggers_table, "drop")

        payload = page.definition_payload()
        variable_extras = {row["name"]: row["legacy_variable"] for row in payload["variables"]}
        state_extras = {row["name"]: row["legacy_state"] for row in payload["states"]}
        trigger_extras = {row["trigger_type"]: row["legacy_trigger"] for row in payload["triggers"]}

        assert variable_extras == {"ALPHA": "alpha-extra", "ZETA": "zeta-extra"}
        assert state_extras == {"Ten": "ten-extra", "Twenty": "twenty-extra"}
        assert trigger_extras == {"alpha": "alpha-extra", "zeta": "zeta-extra"}
        assert all("variable_name" not in row for row in payload["variables"])
        assert all("state_name" not in row for row in payload["states"])
    finally:
        page.deleteLater()
        app.processEvents()


def test_controller_reopens_edits_saves_and_commits_legacy_quest(tmp_path: Path) -> None:
    _prefer_canonical_quest_sources()
    from PySide6 import QtWidgets
    from src.core.scripting.quest import QuestDefinition
    from src.gui.controllers.scripting_data_controller import ScriptingDataController
    from src.gui.windows.qt_scripting_quest_builder_page import QtQuestScaffoldPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = QtQuestScaffoldPage()
    window = SimpleNamespace(quest_scaffold_page=page)
    generated_scripts: list[tuple[str, str, str]] = []
    controller = ScriptingDataController(
        window,
        script_sink=lambda game, resref, source: generated_scripts.append((game, resref, source)),
        game_provider=lambda: "K2",
    )
    legacy_path = tmp_path / "recovered.quest.json"
    legacy_path.write_text(
        json.dumps(
            {
                "quest_id": "recovered",
                "name": "Recovered",
                "target_game": "K2",
                "legacy_extension": {"preserve": 1},
                "variables": [
                    {"variable_name": "LV_RECOVERED", "variable_type": "Boolean", "default": False},
                    {"variable_name": "LV_RECOVERED_STATE", "variable_type": "Number", "default": 0},
                ],
                "states": [
                    {"id": 0, "name": "Not Started", "description": "Waiting"},
                    {"id": 1, "name": "Complete", "description": "Done", "end": True},
                ],
                "triggers": [{"type": "manual", "condition": "TRUE", "state": 1}],
                "dialogues": ["recover_dlg"],
                "scripts": ["recover_run"],
            }
        ),
        encoding="utf-8",
    )
    try:
        assert controller.open_quest_definition(legacy_path)
        assert page.states_table.rowCount() == 2
        page.name_edit.setText("Recovered and Edited")
        page.states_table.item(0, 5).setText("recover_npc")
        output = tmp_path / "edited.quest.json"
        assert controller.save_quest_definition(save_as=True, path=output)
        reloaded = QuestDefinition.load(output)
        assert reloaded.name == "Recovered and Edited"
        assert reloaded.extras["legacy_extension"] == {"preserve": 1}
        assert reloaded.states[0].spawned_npcs == ("recover_npc",)

        assert controller.preview_quest_scaffold(page.definition_payload()) is not None
        assert controller.commit_quest_scaffold()
        assert len(controller.journal.quests) == 1
        assert {row.name for row in controller.globals.variables} == {"LV_RECOVERED", "LV_RECOVERED_STATE"}
        assert len(generated_scripts) == 2
    finally:
        page.deleteLater()
        app.processEvents()


def test_migrated_quest_history_opens_directly_in_builder_handoff(tmp_path: Path) -> None:
    _prefer_canonical_quest_sources()
    from PySide6 import QtWidgets
    from src.core.scripting.project import NarrativeProjectService
    from src.gui.controllers.scripting_project_controller import ScriptingProjectController
    from src.gui.windows.qt_scripting_project_package_pages import PAGE_ROW_ROLE, QtScriptingProjectHistoryPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    project = NarrativeProjectService.create_project(tmp_path / "project", name="Migrated", game="K2")
    legacy_import = Path(project.root_path) / "legacy_import"
    legacy_import.mkdir()
    content = json.dumps(
        {
            "quest_id": "archived_quest",
            "name": "Archived Quest",
            "variables": [{"variable_name": "LV_ARCHIVED", "variable_type": "Boolean", "default": False}],
            "states": [{"id": 0, "name": "Start"}],
        }
    )
    (legacy_import / "ghostscripter-history.json").write_text(
        json.dumps(
            {
                "file_type": "GhostStudioLegacyGhostScripterHistory",
                "schema_version": 1,
                "legacy_project_id": "legacy-project",
                "rows": [
                    {
                        "table": "quest_snapshots",
                        "quest_id": "archived_quest",
                        "data_json": content,
                        "revision": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    page = QtScriptingProjectHistoryPage()
    controller = ScriptingProjectController(
        SimpleNamespace(project_history_page=page, package_override_page=None),
        recent_store_path=tmp_path / "recent.json",
    )
    opened: list[dict[str, object]] = []
    controller.legacyQuestOpened.connect(opened.append)
    try:
        controller._activate_project(project)
        item = page.legacy_history_view.topLevelItem(0)
        page.legacy_history_view.setCurrentItem(item)
        app.processEvents()
        row = dict(item.data(0, PAGE_ROW_ROLE) or {})
        assert page.open_legacy_quest_button.isEnabled()
        assert controller.open_legacy_quest_history(str(row["record_id"]))
        assert opened == [
            {
                "record_id": row["record_id"],
                "identity": "archived_quest",
                "content": content,
                "source": "data_json",
            }
        ]
    finally:
        page.deleteLater()
        controller.deleteLater()
        app.processEvents()
