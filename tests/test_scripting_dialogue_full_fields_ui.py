from __future__ import annotations

import os
import importlib.util
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ghoststudio_canonical_scripting_dialogue_studio",
    ROOT / "src/gui/windows/qt_scripting_dialogue_studio.py",
)
assert SPEC is not None and SPEC.loader is not None
STUDIO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STUDIO)
DOCUMENT_ROLE = STUDIO.DOCUMENT_ROLE
DialogueEditorPage = STUDIO.DialogueEditorPage
QtScriptingDialogueStudioWindow = STUDIO.QtScriptingDialogueStudioWindow

CONTROLLER_SPEC = importlib.util.spec_from_file_location(
    "ghoststudio_canonical_scripting_studio_controller",
    ROOT / "src/gui/controllers/scripting_studio_controller.py",
)
assert CONTROLLER_SPEC is not None and CONTROLLER_SPEC.loader is not None
CONTROLLER_MODULE = importlib.util.module_from_spec(CONTROLLER_SPEC)
sys.modules[CONTROLLER_SPEC.name] = CONTROLLER_MODULE
CONTROLLER_SPEC.loader.exec_module(CONTROLLER_MODULE)
ScriptingStudioController = CONTROLLER_MODULE.ScriptingStudioController


def _application() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _node_row(*, link_id: str, node_id: str, parent_link_id: str, kind: str) -> dict[str, object]:
    return {
        "document_id": "dlg_doc",
        "link_id": link_id,
        "node_id": node_id,
        "parent_link_id": parent_link_id,
        "depth": int(bool(parent_link_id)),
        "kind": kind,
        "text": "NPC line" if kind == "entry" else "Player reply",
        "text_stringref": -1,
        "text_substrings": ((0, "NPC line" if kind == "entry" else "Player reply"), (1, "Localized")),
        "speaker": "OWNER" if kind == "entry" else "",
        "listener": "PLAYER",
        "node_comment": "node note",
        "script1": "on_line",
        "script2": "on_line_b",
        "script1_params": (1, 2, 3, 4, 5, "alpha"),
        "script2_params": (6, 7, 8, 9, 10, "beta"),
        "sound": "line_sound",
        "sound_exists": 1,
        "voice": "line_voice",
        "wait_flags": 3,
        "delay": -1,
        "quest": "quest_tag",
        "quest_entry": 20,
        "plot_index": 2,
        "plot_xp_percentage": 0.75,
        "animations": ({"participant": "OWNER", "animation_id": 6},),
        "camera_angle": 4,
        "camera_anim": 8,
        "camera_id": 12,
        "camera_fov": 60.0,
        "camera_height": 1.2,
        "camera_effect": 2,
        "target_height": 0.4,
        "fade_type": 1,
        "fade_color": (0.1, 0.2, 0.3, 1.0),
        "fade_delay": 0.2,
        "fade_length": 0.8,
        "alien_race_node": 5,
        "emotion_id": 6,
        "facial_id": 7,
        "node_id_tsl": 41,
        "post_proc_node": 9,
        "unskippable": True,
        "record_vo": True,
        "record_no_vo_override": True,
        "vo_text_changed": True,
        "active1": "condition_a",
        "active2": "condition_b",
        "active1_not": True,
        "active2_not": False,
        "logic": True,
        "active1_params": (11, 12, 13, 14, 15, "left"),
        "active2_params": (16, 17, 18, 19, 20, "right"),
        "is_child": bool(parent_link_id),
        "display_inactive": True,
        "link_comment": "link note",
    }


def _settings_row() -> dict[str, object]:
    return {
        "word_count": 25,
        "on_abort": "abort_script",
        "on_end": "end_script",
        "skippable": True,
        "ambient_track": "ambient_music",
        "animated_cut": 1,
        "camera_model": "camera_model",
        "computer_type": 1,
        "conversation_type": 2,
        "old_hit_check": True,
        "unequip_hands": True,
        "unequip_items": True,
        "vo_id": "voice_set",
        "comment": "root note",
        "alien_race_owner": 3,
        "post_proc_owner": 4,
        "record_no_vo": 1,
        "next_node_id": 42,
        "delay_entry": 100,
        "delay_reply": 200,
        "stunts": ({"participant": "OWNER", "stunt_model": "stunt_model"},),
    }


def test_dialogue_page_uses_graph_first_and_synchronizes_stable_selection() -> None:
    app = _application()
    page = DialogueEditorPage("dlg_doc")
    rows = [
        _node_row(link_id="link_start", node_id="node_entry", parent_link_id="", kind="entry"),
        _node_row(link_id="link_reply", node_id="node_reply", parent_link_id="link_start", kind="reply"),
    ]
    try:
        page.set_graph(rows)
        assert page.view_tabs.tabText(0) == "Graph"
        assert page.view_tabs.tabText(1) == "Outline"
        assert page.view_tabs.currentIndex() == 0
        assert page.graph.node_ids == ("node_entry", "node_reply")
        assert page.graph.link_ids == ("link_start", "link_reply")

        assert page.graph.select_link("link_reply")
        app.processEvents()
        assert page._selected_row["link_id"] == "link_reply"
        assert page.tree.currentItem().data(0, DOCUMENT_ROLE)["link_id"] == "link_reply"

        page.tree.setCurrentItem(page._tree_items["link_start"])
        app.processEvents()
        assert page._selected_row["node_id"] == "node_entry"
        assert any(item.isSelected() and item.row.link_id == "link_start" for item in page.graph._links.values())
    finally:
        page.deleteLater()
        app.processEvents()


def test_full_node_link_and_root_fields_are_editable_and_forwarded() -> None:
    app = _application()
    page = DialogueEditorPage("dlg_doc")
    node_rows = [_node_row(link_id="link_start", node_id="node_entry", parent_link_id="", kind="entry")]
    field_events: list[tuple[str, str, str, dict[str, object]]] = []
    setting_events: list[tuple[str, dict[str, object]]] = []
    page.fieldsApplied.connect(lambda document, node, link, values: field_events.append((document, node, link, dict(values))))
    page.settingsApplied.connect(lambda document, values: setting_events.append((document, dict(values))))
    try:
        page.set_graph(node_rows)
        page.set_settings(_settings_row())
        assert page.inspector_tabs.count() == 6
        assert all(isinstance(page.inspector_tabs.widget(index), QtWidgets.QScrollArea) for index in range(6))
        assert page.node_id_spin.value() == 41
        assert page.script2_params.values() == (6, 7, 8, 9, 10, "beta")
        assert page.condition2_params.values() == (16, 17, 18, 19, 20, "right")
        assert page.display_inactive_check.isChecked()
        assert page.animations_table.rowCount() == 1

        page.text_edit.setPlainText("Edited NPC line")
        page.camera_fov_edit.set_value(72.5)
        page.link_comment_edit.setText("edited link note")
        page._apply_fields()
        assert field_events
        document_id, node_id, link_id, values = field_events[-1]
        assert (document_id, node_id, link_id) == ("dlg_doc", "node_entry", "link_start")
        assert values["text"] == "Edited NPC line"
        assert values["camera_fov"] == 72.5
        assert values["script1_params"] == (1, 2, 3, 4, 5, "alpha")
        assert values["active2_params"] == (16, 17, 18, 19, 20, "right")
        assert values["display_inactive"] is True
        assert values["link_comment"] == "edited link note"
        assert values["animations"] == ({"participant": "OWNER", "animation_id": 6},)

        page.next_node_id_spin.setValue(55)
        page._apply_settings()
        assert setting_events
        document_id, values = setting_events[-1]
        assert document_id == "dlg_doc"
        assert values["on_end"] == "end_script"
        assert values["next_node_id"] == 55
        assert values["stunts"] == ({"participant": "OWNER", "stunt_model": "stunt_model"},)
    finally:
        page.deleteLater()
        app.processEvents()


def test_window_forwards_dialogue_settings_and_exposes_context_setter() -> None:
    app = _application()
    window = QtScriptingDialogueStudioWindow()
    events: list[tuple[str, dict[str, object]]] = []
    window.dialogueSettingsApplied.connect(lambda document, values: events.append((document, dict(values))))
    try:
        page = window.add_dialogue_document(
            {"document_id": "dlg_doc", "display_name": "test.dlg", "resref": "test", "kind": "dialogue"}
        )
        window.set_dialogue_graph(
            "dlg_doc",
            [_node_row(link_id="link_start", node_id="node_entry", parent_link_id="", kind="entry")],
        )
        window.set_dialogue_settings("dlg_doc", _settings_row())
        assert page.next_node_id_spin.value() == 42
        page.apply_settings_button.click()
        assert events[-1][0] == "dlg_doc"
        assert events[-1][1]["camera_model"] == "camera_model"
    finally:
        window.deleteLater()
        app.processEvents()


def test_canonical_controller_keeps_opaque_ids_and_applies_full_ui_fields() -> None:
    app = _application()
    window = QtScriptingDialogueStudioWindow()
    controller = ScriptingStudioController(window)
    try:
        document_id = controller.new_dialogue("K2", "full_ui_dlg")
        page = window.page_for_document(document_id)
        assert isinstance(page, DialogueEditorPage)
        row = controller.dialogue_snapshot(document_id)[0]
        assert str(row["node_id"]).startswith("node_")
        assert row["node_id_tsl"] == 0
        assert page.graph.node_ids == (row["node_id"],)

        page.text_edit.setPlainText("Integrated full-field line")
        page.display_inactive_check.setChecked(True)
        page._apply_fields()
        page.next_node_id_spin.setValue(75)
        page._apply_settings()
        app.processEvents()

        updated = controller.dialogue_snapshot(document_id)[0]
        assert updated["text"] == "Integrated full-field line"
        assert updated["display_inactive"] is True
        assert controller.dialogue_settings_snapshot(document_id)["next_node_id"] == 75
    finally:
        window.deleteLater()
        app.processEvents()


def test_dialogue_graph_and_inspector_use_palette_not_private_color_literals() -> None:
    graph_source = (ROOT / "src/gui/widgets/dialogue_graph_widget.py").read_text(encoding="utf-8")
    studio_source = (ROOT / "src/gui/windows/qt_scripting_dialogue_studio.py").read_text(encoding="utf-8")
    assert "QPalette.Highlight" in graph_source
    assert "QPalette.Link" in graph_source
    assert 'QColor("#' not in graph_source
    assert "DialogueGraphWidget" in studio_source
    assert "dialogueSettingsApplied" in studio_source
