from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]


def _install_native_payload_paths() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_workbench_controller_authors_compiles_and_builds_without_exposing_dlg(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from PySide6 import QtCore, QtWidgets
    from src.gui.controllers.scripting_studio_controller import ScriptingStudioController
    from src.gui.qt_lib.windows.qt_scripting_dialogue_studio import (
        DialogueEditorPage,
        QtScriptingDialogueStudioWindow,
        ScriptEditorPage,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    controller = ScriptingStudioController(window, output_root=tmp_path)
    try:
        assert window.editor_tabs.tabText(0) == "Start"
        assert window.welcome_page.objectName() == "scriptingStudioWelcomePage"
        assert window.studio_toolbar.toolButtonStyle() == QtCore.Qt.ToolButtonTextBesideIcon
        script_id = controller.new_script("K2", "gs_ui_test")
        assert isinstance(window.page_for_document(script_id), ScriptEditorPage)
        controller.update_script_source(script_id, "void main()\n{\n}\n")
        compile_result = controller.compile_document(script_id)
        assert compile_result is not None and compile_result.ok

        dialogue_id = controller.new_dialogue("K2", "gs_ui_dlg")
        page = window.page_for_document(dialogue_id)
        assert isinstance(page, DialogueEditorPage)
        row = controller.dialogue_snapshot(dialogue_id)[0]
        controller.update_dialogue_fields(
            dialogue_id,
            row["node_id"],
            row["link_id"],
            {"text": "Integrated conversation", "speaker": "OWNER", "sound": "vo_test"},
        )
        assert controller.dialogue_snapshot(dialogue_id)[0]["text"] == "Integrated conversation"

        build = controller.build_documents("K2")
        assert build.ok
        assert {(resref, restype) for resref, restype, _data in controller.runtime_resources()} == {
            ("gs_ui_test", "ncs"),
            ("gs_ui_dlg", "dlg"),
        }
        assert isinstance(controller.documents, tuple)
        assert all(isinstance(item, dict) for item in controller.documents)
    finally:
        window.deleteLater()
        app.processEvents()


def test_map_context_uses_suggested_binding_and_main_shell_has_one_clear_launcher(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.application_core.shared.scripting_studio_workflow import (
        ScriptingStudioWorkflowMixin,
    )

    class Host(ScriptingStudioWorkflowMixin, QtWidgets.QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.app_root = tmp_path
            self._current_game = "K2"
            self._resource_manager = None
            self.messages: list[tuple[str, str]] = []

        def _get_resource_manager(self):
            return None

        def _log(self, message: str, severity: str = "info") -> None:
            self.messages.append((message, severity))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host = Host()
    try:
        first = host._open_scripting_dialogue_studio_window(
            {
                "source": "map_studio",
                "kind": "dialogue",
                "game": "K2",
                "restype": "DLG",
                "resref": "",
                "suggested_resref": "My Cantina Dialogue",
            }
        )
        second = host._open_scripting_dialogue_studio_window()
        assert second is first
        assert first.objectName() == "scriptingDialogueStudioWindow"
        assert first.property("ghostLayoutId") == "scriptingDialogueStudio"
        assert first.windowTitle() == "GhostStudio — Scripting Suite"
        assert {row["resref"] for row in host.scripting_dialogue_studio_controller.documents} == {
            "my_cantina_dialo"
        }
    finally:
        host.scripting_dialogue_studio_window.deleteLater()
        host.deleteLater()
        app.processEvents()

    chrome = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py"
    ).read_text(encoding="utf-8")
    main = (
        ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py"
    ).read_text(encoding="utf-8")
    assert '"Open Scripting Suite..."' in chrome
    assert "def _command_launcher_groups" in chrome
    assert "self.scripting_dialogue_studio_action," in chrome
    assert "tools_menu.addAction(self.scripting_dialogue_studio_action)" in chrome
    assert "tools_menu.addAction(self.ping_scripter_action)" not in chrome
    assert '"scripting_studio": self._open_scripting_dialogue_studio_window' in main
    assert '"dialogue_editor": self._open_scripting_dialogue_studio_window' in main


def test_map_dialogue_context_supplies_only_real_creature_placements() -> None:
    _install_native_payload_paths()

    from src.gui.windows.application_core.shared.scripting_studio_workflow import (
        ScriptingStudioWorkflowMixin,
    )

    placements = (
        {"kind": "creature", "tag": "cantina_guard", "template_resref": "guard_utc"},
        {"kind": "placeable", "tag": "cantina_console", "template_resref": "console_utp"},
    )

    class MapController:
        def authored_gameplay_placements(self):
            return placements

    class Host(ScriptingStudioWorkflowMixin):
        module_editor_window = SimpleNamespace(controller=MapController())

    context = Host()._scripting_context_with_map_participants(
        {"source": "map_studio", "kind": "dialogue", "restype": "DLG", "game": "K2"}
    )
    assert context["placed_creatures"] == (placements[0],)


def test_scripting_suite_navigation_composes_every_preserved_authoring_surface() -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import QtScriptingDialogueStudioWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    try:
        labels = [
            window.suite_navigation.item(index).text()
            for index in range(window.suite_navigation.count())
        ]
        assert labels == [
            "Scripts & Dialogue",
            "NWScript Reference",
            "Quest Builder",
            "Journal (JRL)",
            "2DA & Globals",
            "Talk Table (TLK)",
            "Voice, Lip & SSF",
            "Project & History",
            "Package & Test Install",
            "Guided Workflows",
            "Blueprint & GFF",
            "Integrated Tools",
        ]
        for key in (
            "code",
            "reference",
            "quest",
            "journal",
            "tables",
            "talk",
            "voice",
            "project",
            "package",
            "tutorial",
            "blueprint",
            "integrated",
        ):
            assert window.show_suite_page(key)
            assert window.suite_stack.currentIndex() == window._suite_page_rows[key]
        assert window.suite_splitter.childrenCollapsible() is False
        assert window.property("ghostLayoutId") == "scriptingDialogueStudio"
    finally:
        window.deleteLater()
        app.processEvents()


def test_workbench_exposes_original_style_editor_shortcuts_and_honest_proof_language() -> None:
    source = (ROOT / "src/gui/windows/qt_scripting_dialogue_studio.py").read_text(encoding="utf-8")
    for shortcut in ("Ctrl+Space", "Ctrl+F", "Ctrl+H", "Ctrl+G", "F3", "Shift+F3", "F7"):
        assert shortcut in source
    assert "not retail KOTOR execution proof" in source
    assert "retail KOTOR" in source
    assert "Imported unknown GFF fields are preserved" in source


def test_nwscript_completion_inserts_call_syntax_and_shows_definition_signature(monkeypatch) -> None:
    _install_native_payload_paths()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import NssCodeEditor

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    shown: list[str] = []
    monkeypatch.setattr(
        QtWidgets.QToolTip,
        "showText",
        lambda _point, value, *_args, **_kwargs: shown.append(str(value)),
    )
    editor = NssCodeEditor()
    editor.set_completion_definitions(
        (
            {
                "kind": "function",
                "name": "Random",
                "signature": "int Random(int nMaxInteger)",
                "description": "Returns a random integer.",
                "parameters": ("nMaxInteger",),
            },
            {
                "kind": "constant",
                "name": "OBJECT_INVALID",
                "signature": "object OBJECT_INVALID",
                "parameters": (),
            },
        )
    )
    try:
        editor.setPlainText("Ran")
        cursor = editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        editor.setTextCursor(cursor)
        editor._insert_completion("Random")

        assert editor.toPlainText() == "Random()"
        assert editor.textCursor().position() == len("Random(")
        assert shown == ["int Random(int nMaxInteger)\nReturns a random integer."]

        editor.setPlainText("OBJECT")
        cursor = editor.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        editor.setTextCursor(cursor)
        editor._insert_completion("OBJECT_INVALID")
        assert editor.toPlainText() == "OBJECT_INVALID"
    finally:
        editor.deleteLater()
        app.processEvents()


def test_dialogue_outline_filter_preserves_matching_ancestors() -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import DialogueEditorPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = DialogueEditorPage("dialogue_filter")
    try:
        page.set_graph(
            [
                {
                    "link_id": "root",
                    "node_id": "entry_1",
                    "parent_link_id": "",
                    "kind": "entry",
                    "text": "Welcome",
                    "speaker": "OWNER",
                },
                {
                    "link_id": "child",
                    "node_id": "reply_1",
                    "parent_link_id": "root",
                    "kind": "reply",
                    "text": "Tell me about the quest",
                    "speaker": "PLAYER",
                },
            ]
        )
        page.node_filter_edit.setText("quest")
        page._apply_node_filter()
        root = page.tree.topLevelItem(0)
        assert not root.isHidden()
        assert not root.child(0).isHidden()
        assert page.node_filter_result_label.text() == "1 of 2"

        page.node_filter_edit.clear()
        page.node_kind_filter.setCurrentIndex(1)
        page._apply_node_filter()
        assert not root.isHidden()
        assert root.child(0).isHidden()
        assert page.node_filter_result_label.text() == "1 of 2"
        assert page.tree.currentItem() is root
        assert page._selected_row["link_id"] == "root"

        page.node_filter_edit.setText("no such conversation node")
        page.node_kind_filter.setCurrentIndex(0)
        page._apply_node_filter()
        assert page.tree.currentItem() is None
        assert page._selected_row == {}
        assert page.kind_label.text() == "No node selected"

        page.node_filter_edit.setText("replacement target")
        page.set_graph(
            [
                {
                    "link_id": "old",
                    "node_id": "entry_old",
                    "parent_link_id": "",
                    "kind": "entry",
                    "text": "Does not match",
                },
                {
                    "link_id": "replacement",
                    "node_id": "entry_replacement",
                    "parent_link_id": "",
                    "kind": "entry",
                    "text": "Replacement target",
                },
            ]
        )
        assert page._selected_row["link_id"] == "replacement"
        assert not page.tree.currentItem().isHidden()
    finally:
        page.deleteLater()
        app.processEvents()


def test_dialogue_participant_browser_uses_module_and_utc_tags_not_appearance_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.core.scripting.data_authoring import TwoDADocument
    from src.gui.controllers.scripting_studio_controller import ScriptingStudioController
    from src.gui.windows.qt_scripting_dialogue_studio import QtScriptingDialogueStudioWindow

    table = TwoDADocument(
        ("label", "modela", "normalhead", "race"),
        ("0", "1"),
        (
            ("n_human", "p_hhm_a", "1", "human"),
            ("n_rodian", "n_rodian", "42", "rodian"),
        ),
    )

    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff

    utc = GFF(GFFContent.UTC)
    utc.root.set_string("Tag", "cantina_rodian")
    utc.root.set_uint16("Appearance_Type", 1)
    utc_payload = bytes_gff(utc)

    class Manager:
        def get(self, name: str, restype: int, game: str):
            assert game == "K2"
            if (name, restype) == ("appearance", 2017):
                return table.to_bytes()
            if (name, restype) == ("rodian_utc", 2027):
                return utc_payload
            raise AssertionError((name, restype, game))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    controller = ScriptingStudioController(window, resource_manager=Manager(), output_root=tmp_path)
    captured: list[dict[str, str]] = []

    def choose(_document_id: str, _field: str, rows: object, *, current: str = "") -> str:
        assert current == "OWNER"
        captured.extend(dict(row) for row in tuple(rows or ()))
        return "cantina_rodian"

    monkeypatch.setattr(window, "choose_dialogue_participant", choose)
    try:
        document_id = controller.new_dialogue("K2", "participant_test")
        controller.set_dialogue_participant_context(
            document_id,
            (
                {"tag": "placed_guard", "appearance_id": "0"},
                {"template_resref": "rodian_utc"},
            ),
        )
        assert controller.browse_dialogue_participant(document_id, "speaker", "OWNER") == "cantina_rodian"
        assert "n_human" not in {row["tag"] for row in captured}
        assert "n_rodian" not in {row["tag"] for row in captured}
        rodian = next(row for row in captured if row["tag"] == "cantina_rodian")
        assert rodian == {
            "tag": "cantina_rodian",
            "appearance_id": "1",
            "body_model": "n_rodian",
            "head": "42",
            "race": "rodian",
            "source": "Current module",
            "template_resref": "rodian_utc",
        }
    finally:
        window.deleteLater()
        app.processEvents()


def test_dialogue_participant_picker_clears_hidden_selection_and_disables_ok() -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import _DialogueParticipantPicker

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = _DialogueParticipantPicker(
        ({"tag": "cantina_guard", "source": "Current module"},),
        current="cantina_guard",
    )
    try:
        assert dialog.selected_tag == "cantina_guard"
        assert dialog._accept_button.isEnabled()
        dialog._apply_filter("no participant matches this")
        assert dialog.tree.currentItem() is None
        assert dialog.selected_tag == ""
        assert not dialog._accept_button.isEnabled()
        dialog._accept_selected()
        assert dialog.result() != QtWidgets.QDialog.Accepted
    finally:
        dialog.deleteLater()
        app.processEvents()


def test_dialogue_topology_actions_forward_targets_and_keep_selection(monkeypatch) -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import DialogueEditorPage

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    page = DialogueEditorPage("dialogue_topology")
    page.set_graph(
        [
            {
                "link_id": "start",
                "node_id": "entry_1",
                "parent_link_id": "",
                "kind": "entry",
                "text": "Opening line",
                "speaker": "OWNER",
            },
            {
                "link_id": "reply_link",
                "node_id": "reply_1",
                "parent_link_id": "start",
                "kind": "reply",
                "text": "Player answer",
            },
            {
                "link_id": "entry_link",
                "node_id": "entry_2",
                "parent_link_id": "reply_link",
                "kind": "entry",
                "text": "Second NPC line",
                "speaker": "OWNER",
            },
        ]
    )
    linked: list[tuple[str, str, str]] = []
    started: list[tuple[str, str]] = []
    retargeted: list[tuple[str, str, str]] = []
    deleted: list[tuple[str, str]] = []
    page.linkExistingRequested.connect(lambda *values: linked.append(tuple(values)))
    page.startExistingRequested.connect(lambda *values: started.append(tuple(values)))
    page.retargetLinkRequested.connect(lambda *values: retargeted.append(tuple(values)))
    page.deleteNodeRequested.connect(lambda *values: deleted.append(tuple(values)))
    targets = iter(("reply_1", "entry_2", "reply_1"))
    monkeypatch.setattr(page, "_choose_target", lambda *_args, **_kwargs: next(targets))
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *_args, **_kwargs: QtWidgets.QMessageBox.Yes,
    )
    try:
        assert page.select_link("start")
        page.link_existing_button.click()
        page.start_existing_button.click()
        assert page.select_link("reply_link")
        page.retarget_button.click()
        page.delete_node_button.click()

        assert linked == [("dialogue_topology", "start", "reply_1")]
        assert started == [("dialogue_topology", "entry_2")]
        assert retargeted == [("dialogue_topology", "reply_link", "reply_1")]
        assert deleted == [("dialogue_topology", "reply_1")]
        assert page._selected_row["link_id"] == "reply_link"

        page.set_topology_policy(True)
        assert not page.topology_lock_label.isHidden()
        assert not page.make_editable_copy_button.isHidden()
        assert not page.link_existing_button.isEnabled()
        assert not page.delete_node_button.isEnabled()
        page.set_topology_policy(False)
        assert page.make_editable_copy_button.isHidden()
        assert page.link_existing_button.isEnabled()
    finally:
        page.deleteLater()
        app.processEvents()


def test_dialogue_target_picker_searches_existing_node_metadata() -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.windows.qt_scripting_dialogue_studio import _DialogueTargetPicker

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    picker = _DialogueTargetPicker(
        (
            {
                "node_id": "entry_owner",
                "kind": "entry",
                "text": "Welcome aboard",
                "speaker": "OWNER",
                "listener": "PLAYER",
                "incoming_links": 2,
            },
            {
                "node_id": "entry_guard",
                "kind": "entry",
                "text": "Halt there",
                "speaker": "CANTINA_GUARD",
                "listener": "PLAYER",
                "incoming_links": 1,
            },
        ),
        title="Choose Existing Entry",
    )
    try:
        assert picker.selected_node_id == "entry_owner"
        picker._apply_filter("cantina_guard")
        assert picker.selected_node_id == "entry_guard"
        assert picker.tree.topLevelItem(0).isHidden()
        assert not picker.tree.topLevelItem(1).isHidden()
        picker._apply_filter("missing")
        assert picker.selected_node_id == ""
        assert not picker.buttons.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()
    finally:
        picker.deleteLater()
        app.processEvents()


def test_controller_topology_actions_roundtrip_ids_and_select_mutated_link(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.controllers.scripting_studio_controller import ScriptingStudioController
    from src.gui.windows.qt_scripting_dialogue_studio import QtScriptingDialogueStudioWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    controller = ScriptingStudioController(window, output_root=tmp_path)
    try:
        document_id = controller.new_dialogue("K2", "topology_ids")
        root = controller.dialogue_snapshot(document_id)[0]
        first_child_link = controller.add_dialogue_child(document_id, root["link_id"])
        second_child_link = controller.add_dialogue_child(document_id, root["link_id"])
        rows = controller.dialogue_snapshot(document_id)
        first_reply = next(row for row in rows if row["link_id"] == first_child_link)
        second_reply = next(row for row in rows if row["link_id"] == second_child_link)

        shared_link = controller.link_existing_dialogue_node(
            document_id,
            root["link_id"],
            first_reply["node_id"],
        )
        assert shared_link
        assert controller.retarget_dialogue_link(document_id, shared_link, second_reply["node_id"])
        page = window.page_for_document(document_id)
        assert page is not None
        assert page._selected_row["link_id"] == shared_link

        rows = controller.dialogue_snapshot(document_id)
        assert sum(row["node_id"] == second_reply["node_id"] for row in rows) == 2
        assert controller.delete_dialogue_node(document_id, second_reply["node_id"])
        rows = controller.dialogue_snapshot(document_id)
        assert all(row["node_id"] != second_reply["node_id"] for row in rows)
        assert any(row["node_id"] == first_reply["node_id"] for row in rows)

        new_starter = controller.start_dialogue_at_existing(document_id, root["node_id"])
        assert new_starter
        assert window.select_dialogue_link(document_id, new_starter)
        assert page._selected_row["link_id"] == new_starter
    finally:
        window.deleteLater()
        app.processEvents()


def test_successful_save_from_dirty_tab_closes_it_in_one_step(
    monkeypatch,
) -> None:
    _install_native_payload_paths()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_scripting_dialogue_studio import (
        QtScriptingDialogueStudioWindow,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtScriptingDialogueStudioWindow()
    row = {
        "document_id": "script_save_close",
        "display_name": "save_close.nss",
        "resref": "save_close",
        "kind": "script",
        "dirty": True,
    }
    page = window.add_script_document(row, "void main()\n{\n}\n")

    def save_success(document_id: str, _save_as: bool) -> None:
        assert document_id == "script_save_close"
        window.update_document_row({**row, "dirty": False})

    window.saveRequested.connect(save_success)
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *_args, **_kwargs: QtWidgets.QMessageBox.Save,
    )
    try:
        window._tab_close_requested(window.editor_tabs.indexOf(page))

        assert window.page_for_document("script_save_close") is None
        assert window.editor_tabs.count() == 1
        assert window.editor_tabs.tabText(0) == "Start"
    finally:
        window.deleteLater()
        app.processEvents()


def test_explicit_resource_refresh_is_cached_across_document_edits(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.gui.controllers.scripting_studio_controller import ScriptingStudioController

    class Provider:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def list_resources(self, query: dict[str, str]):
            self.calls.append(dict(query))
            restype = query["restype"]
            return (
                SimpleNamespace(
                    address=None,
                    resref=f"stock_{restype.lower()}",
                    source="Game resource",
                    source_path="chitin.key",
                    size=42,
                ),
            )

    provider = Provider()
    controller = ScriptingStudioController(resource_provider=provider, output_root=tmp_path)

    assert controller.show_current_catalog("K2") == []
    assert provider.calls == []

    refreshed = controller.refresh_resource_catalog("K2")
    assert [call["restype"] for call in provider.calls] == ["NSS", "NCS", "DLG"]
    external_ids = {
        row["catalog_id"] for row in refreshed if str(row["catalog_id"]).startswith("external:")
    }

    script_id = controller.new_script("K2", "catalog_cache")
    controller.update_script_source(script_id, "void main()\n{\n}\n")
    assert controller.compile_document(script_id) is not None
    assert controller.save_document(script_id, path=tmp_path / "catalog_cache.nss")
    current = controller.show_current_catalog("K2")

    assert len(provider.calls) == 3
    assert external_ids <= {row["catalog_id"] for row in current}

    controller.refresh_resource_catalog("K2")
    assert len(provider.calls) == 6


def test_qt_scripting_controller_is_owned_only_by_gui_display() -> None:
    assert not (ROOT / "src/core/tools/scripting_studio_controller.py").exists()
    assert not (
        ROOT
        / "native/GhostRigger.Core.Tools/Python/src/core/tools/scripting_studio_controller.py"
    ).exists()
    assert (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/controllers/scripting_studio_controller.py"
    ).is_file()

    workflow = (
        ROOT
        / "src/gui/windows/application_core/shared/scripting_studio_workflow.py"
    ).read_text(encoding="utf-8")
    assert "from src.gui.controllers.scripting_suite_controller import" in workflow
    assert "ScriptingSuiteController" in workflow
    assert "src.core.tools.scripting_studio_controller" not in workflow

    manifest = (ROOT / "native/GhostRigger.PythonPayloadManifest.json").read_text(encoding="utf-8")
    assert "src\\\\gui\\\\controllers\\\\scripting_studio_controller.py" in manifest
    assert "src\\\\core\\\\tools\\\\scripting_studio_controller.py" not in manifest


def test_document_edit_invalidates_staged_map_resources_and_failure_phases(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.scripting.studio import NarrativeBuildResult, StudioDiagnostic
    from src.gui.controllers.scripting_studio_controller import ScriptingStudioController
    from src.gui.windows.application_core.shared.scripting_studio_workflow import (
        ScriptingStudioWorkflowMixin,
    )

    class MapWindow:
        def __init__(self) -> None:
            self.staged: list[tuple[tuple[str, str, bytes], ...]] = []

        def set_scripting_studio_resources(self, resources) -> None:
            self.staged.append(tuple(resources or ()))

    class Host(ScriptingStudioWorkflowMixin):
        def __init__(self) -> None:
            self.module_editor_window = MapWindow()
            self.messages: list[tuple[str, str]] = []

        def _log(self, message: str, severity: str = "info") -> None:
            self.messages.append((message, severity))

    host = Host()
    controller = ScriptingStudioController(output_root=tmp_path)
    controller.buildCompleted.connect(host._on_scripting_studio_build_completed)
    controller.buildInvalidated.connect(host._on_scripting_studio_build_invalidated)
    invalidations: list[bool] = []
    controller.buildInvalidated.connect(lambda: invalidations.append(True))

    script_id = controller.new_script("K2", "stale_runtime")
    build = controller.build_documents("K2")
    assert build.ok
    assert host._scripting_studio_runtime_resources
    assert host.module_editor_window.staged[-1]

    edited_source = "void main()\n{\n    DelayCommand(0.1, ActionDoCommand());\n}\n"
    controller.update_script_source(script_id, edited_source)
    assert invalidations == [True]
    assert controller.runtime_resources() == ()
    assert host._scripting_studio_runtime_resources == ()
    assert host.module_editor_window.staged[-1] == ()
    assert host.messages[-1][1] == "warning"

    controller.update_script_source(script_id, edited_source)
    assert invalidations == [True]

    phases = {
        "script.compile_failed": "validation failed",
        "narrative.build_staging_failed": "staging failed",
        "narrative.build_promotion_failed": "promotion failed",
        "narrative.build_rollback_failed": "rollback failed",
    }
    for code, expected in phases.items():
        result = NarrativeBuildResult(
            str(tmp_path),
            "K2",
            diagnostics=(StudioDiagnostic("blocking", code, "forced failure"),),
        )
        assert expected in controller._build_failure_status(result).lower()
