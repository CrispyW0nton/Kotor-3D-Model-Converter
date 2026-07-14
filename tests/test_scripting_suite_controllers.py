from __future__ import annotations

import json
import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The test harness prepends packaged payload roots to mirror the native host.
# These controller files are canonical sources until the parent task regenerates
# the GUI payload, so make the canonical package portions visible here.
import src  # noqa: E402

root_src = str(ROOT / "src")
if root_src not in src.__path__:
    src.__path__.insert(0, root_src)
import src.gui  # noqa: E402

root_gui = str(ROOT / "src" / "gui")
if root_gui not in src.gui.__path__:
    src.gui.__path__.insert(0, root_gui)
import src.gui.controllers  # noqa: E402

root_controllers = str(ROOT / "src" / "gui" / "controllers")
if root_controllers not in src.gui.controllers.__path__:
    src.gui.controllers.__path__.insert(0, root_controllers)


def _project_window():
    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_project_package_pages import (
        QtScriptingPackageOverridePage,
        QtScriptingProjectHistoryPage,
    )

    class ProjectWindow(QtWidgets.QWidget):
        pass

    window = ProjectWindow()
    window.project_history_page = QtScriptingProjectHistoryPage(window)
    window.package_override_page = QtScriptingPackageOverridePage(window)
    return window


def test_project_controller_preserves_project_history_and_safe_package_flow(tmp_path: Path) -> None:
    from PySide6 import QtWidgets
    from src.core.scripting.packaging import inspect_narrative_archive
    from src.core.scripting.data_authoring import TalkTableDocument
    from src.gui.controllers.scripting_project_controller import ScriptingProjectController

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _project_window()
    talk_table = TalkTableDocument()
    talk_table.add_entry("GhostStudio project string")
    talk_table_bytes = talk_table.to_bytes()
    snapshots = (
        ("story_run", "nss", b"void main() {}\n", "source", "K2"),
        ("story_run", "ncs", b"NCS V1.0\x00compiled", "runtime", "K2"),
        ("story_dlg", "dlg", b"DLG fixture bytes", "runtime", "K2"),
        ("dialog", "tlk", talk_table_bytes, "global_install", "K2"),
    )
    controller = ScriptingProjectController(
        window,
        recent_store_path=tmp_path / "preferences" / "recent.json",
        snapshot_provider=lambda: snapshots,
    )
    try:
        project = controller.create_project(
            {"game": "K2"}, root=tmp_path / "narrative", name="Cantina Story"
        )
        assert project is not None
        assert controller.save_project()
        assert {(row.resref, row.restype, row.role) for row in project.assets} == {
            ("story_run", "nss", "source"),
            ("story_run", "ncs", "runtime"),
            ("story_dlg", "dlg", "runtime"),
            ("dialog", "tlk", "global_install"),
        }
        assert window.project_history_page.asset_model.rowCount() == 4
        assert window.project_history_page.recent_view.topLevelItemCount() == 1

        # The visible status proves the global resource is preserved but
        # deliberately excluded from module and Override output.
        assert any(
            window.package_override_page.package_resource_view.topLevelItem(index).text(4)
            == "Excluded (global install)"
            for index in range(window.package_override_page.package_resource_view.topLevelItemCount())
        )

        archive = tmp_path / "cantina.erf"
        package = controller.build_package(
            {
                "archive_type": "ERF",
                "output_path": str(archive),
                "include_source": False,
                "overwrite": False,
            }
        )
        assert package is not None and package.ok
        inspection = inspect_narrative_archive(archive)
        assert {(row.resref, row.restype) for row in inspection.resources} == {
            ("story_run", "ncs"),
            ("story_dlg", "dlg"),
        }
        assert not any(row.restype == "tlk" for row in inspection.resources)

        stage = controller.stage_override(
            {"output_dir": str(tmp_path / "stage"), "include_source": False, "replace_owned": False}
        )
        assert stage is not None and stage.ok
        assert not (tmp_path / "stage" / "Override" / "dialog.tlk").exists()
        game_root = tmp_path / "KOTOR2"
        game_root.mkdir()
        installed = controller.install_override(
            {
                "stage_path": stage.stage_path,
                "game_root": str(game_root),
                "on_conflict": "block",
            }
        )
        assert installed is not None and installed.ok
        assert (game_root / "Override" / "story_run.ncs").read_bytes() == snapshots[1][2]

        original_talk_table = TalkTableDocument()
        original_talk_table.add_entry("Original game string")
        original_tlk_bytes = original_talk_table.to_bytes()
        (game_root / "dialog.tlk").write_bytes(original_tlk_bytes)
        tlk_install = controller.install_global_tlk({"game_root": str(game_root), "game": "K2"})
        assert tlk_install is not None and tlk_install.ok
        assert (game_root / "dialog.tlk").read_bytes() == talk_table_bytes
        tlk_restore = controller.restore_global_tlk(
            {"game_root": str(game_root), "receipt_path": tlk_install.receipt_path}
        )
        assert tlk_restore is not None and tlk_restore.ok
        assert (game_root / "dialog.tlk").read_bytes() == original_tlk_bytes

        revision = controller.create_revision("Before dialogue rewrite")
        assert revision is not None
        recovered = controller.recover_revision(revision.revision_id, tmp_path / "recovered")
        assert Path(recovered).is_file()
        assert (tmp_path / "recovered" / "scripts" / "story_run.nss").read_bytes() == snapshots[0][2]
    finally:
        window.deleteLater()
        app.processEvents()


def test_project_controller_exposes_non_destructive_legacy_migration(tmp_path: Path) -> None:
    from PySide6 import QtWidgets
    from src.gui.controllers.scripting_project_controller import ScriptingProjectController

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    legacy = tmp_path / "legacy"
    (legacy / "scripts").mkdir(parents=True)
    (legacy / "scripts" / "legacy_run.nss").write_text("void main() {}\n", encoding="utf-8")
    (legacy / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "project_id": "legacy-id",
                "name": "Legacy Story",
                "target_game": "K1",
            }
        ),
        encoding="utf-8",
    )
    window = _project_window()
    controller = ScriptingProjectController(
        window,
        recent_store_path=tmp_path / "recent.json",
    )
    try:
        result = controller.import_legacy_project(legacy / "project.json", tmp_path / "migrated")
        assert result is not None
        assert controller.project is result.project
        assert result.project.game == "K1"
        assert (legacy / "scripts" / "legacy_run.nss").read_text(encoding="utf-8") == "void main() {}\n"
        assert (tmp_path / "migrated" / "legacy_source" / "project.json").is_file()
        assert (tmp_path / "migrated" / "scripts" / "legacy_run.nss").is_file()
    finally:
        window.deleteLater()
        app.processEvents()


def test_journal_controller_edits_preserve_stringrefs_and_translations() -> None:
    from PySide6 import QtWidgets
    from src.core.scripting.data_authoring import (
        JournalDocument,
        JournalEntryRecord,
        JournalQuestRecord,
        LocalizedText,
    )
    from src.gui.controllers.scripting_data_controller import ScriptingDataController

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtWidgets.QWidget()
    controller = ScriptingDataController(window)
    controller.journal = JournalDocument(
        (
            JournalQuestRecord(
                tag="localized_quest",
                name=LocalizedText(12001, ((0, "Original quest"), (2, "Quete francaise"))),
                entries=(
                    JournalEntryRecord(
                        10,
                        LocalizedText(12002, ((0, "Original entry"), (2, "Entree francaise"))),
                    ),
                ),
            ),
        )
    )
    try:
        controller.edit_quest(0, {"name": "Edited quest", "comment": "Still localized"})
        controller.edit_journal_entry(0, 0, {"text": "Edited entry", "end": True})

        quest = controller.journal.quests[0]
        assert quest.name.stringref == 12001
        assert dict(quest.name.substrings) == {0: "Edited quest", 2: "Quete francaise"}
        assert quest.comment == "Still localized"

        entry = quest.entries[0]
        assert entry.text.stringref == 12002
        assert dict(entry.text.substrings) == {0: "Edited entry", 2: "Entree francaise"}
        assert entry.end is True
    finally:
        window.deleteLater()
        app.processEvents()


def test_suite_facade_merges_runtime_data_and_invalidates_after_edits(tmp_path: Path) -> None:
    from PySide6 import QtWidgets
    from src.core.scripting.data_authoring import TwoDADocument
    from src.gui.controllers.scripting_suite_controller import ScriptingSuiteController
    from src.gui.windows.qt_scripting_dialogue_studio import QtScriptingDialogueStudioWindow
    from src.gui.windows.qt_scripting_project_package_pages import (
        QtScriptingPackageOverridePage,
        QtScriptingProjectHistoryPage,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    window.project_history_page = QtScriptingProjectHistoryPage(window)
    window.package_override_page = QtScriptingPackageOverridePage(window)
    controller = ScriptingSuiteController(
        window,
        output_root=tmp_path / "build",
        recent_store_path=tmp_path / "recent.json",
    )
    builds: list[tuple[str, tuple[tuple[str, str, bytes], ...]]] = []
    invalidations: list[bool] = []
    controller.buildCompleted.connect(lambda output, rows: builds.append((output, tuple(rows))))
    controller.buildInvalidated.connect(lambda: invalidations.append(True))
    try:
        controller.new_dialogue("K2", "story_dlg")
        controller.data_controller.table = TwoDADocument(("label", "value"), ("0",), (("test", "1"),))
        result = controller.build_documents("K2", tmp_path / "build" / "k2")
        assert result.ok
        assert builds
        assert {(resref, restype) for resref, restype, _data in builds[-1][1]} == {
            ("story_dlg", "dlg"),
            ("new_table", "2da"),
        }
        assert controller.runtime_resources() == builds[-1][1]

        controller.data_controller._changed()
        assert invalidations == [True]
        assert controller.runtime_resources() == ()

        snapshots = controller.project_resource_snapshots()
        assert {(row.resref, row.restype, row.role) for row in snapshots} == {
            ("story_dlg", "dlg", "runtime"),
            ("new_table", "2da", "runtime"),
        }
    finally:
        window.deleteLater()
        app.processEvents()
