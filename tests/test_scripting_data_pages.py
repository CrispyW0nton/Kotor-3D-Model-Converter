from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtWidgets

from src.core.scripting.data_authoring import SoundSetDocument

from src.gui.windows.qt_scripting_data_pages import (
    LipSoundSetPage,
    QuestJournalPage,
    TalkTablePage,
    TwoDAGlobalsPage,
)


@pytest.fixture(scope="module")
def app() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_quest_journal_page_presents_tree_and_emits_inspector_edits(app: QtWidgets.QApplication) -> None:
    page = QuestJournalPage()
    page.set_journal(
        [
            {
                "tag": "K_TEST",
                "name": "Test Quest",
                "comment": "note",
                "priority": 1,
                "planet_id": 2,
                "plot_index": 3,
                "entries": [{"entry_id": 10, "text": "Started", "end": False, "xp_percentage": 0.0}],
            }
        ],
        source_name="global.jrl",
    )
    assert page.model.rowCount() == 1
    assert page.model.item(0, 0).rowCount() == 1

    quest_edits: list[tuple[int, dict[str, object]]] = []
    entry_edits: list[tuple[int, int, dict[str, object]]] = []
    page.editQuestRequested.connect(lambda index, payload: quest_edits.append((index, payload)))
    page.editEntryRequested.connect(lambda quest, entry, payload: entry_edits.append((quest, entry, payload)))

    page.tree.setCurrentIndex(page.proxy.mapFromSource(page.model.index(0, 0)))
    app.processEvents()
    page.quest_tag_edit.setText("K_EDITED")
    page.quest_apply_button.click()
    assert quest_edits[-1][0] == 0
    assert quest_edits[-1][1]["tag"] == "K_EDITED"

    child = page.model.index(0, 0, page.model.index(0, 0))
    page.tree.setCurrentIndex(page.proxy.mapFromSource(child))
    app.processEvents()
    page.entry_text_edit.setPlainText("Updated journal text")
    page.entry_apply_button.click()
    assert entry_edits[-1][:2] == (0, 0)
    assert entry_edits[-1][2]["text"] == "Updated journal text"
    assert "1 quest categories" in page.status_label.text()


def test_2da_globals_page_uses_filtered_model_and_emits_cell_and_global_intent(app: QtWidgets.QApplication) -> None:
    page = TwoDAGlobalsPage()
    page.set_table(
        ("name", "type"),
        ("0", "1"),
        ({"name": "MYMOD_A", "type": "Boolean"}, {"name": "MYMOD_B", "type": "Number"}),
        source_name="globalcat.2da",
    )
    assert page.model.rowCount() == 2
    edits: list[tuple[int, str, object]] = []
    globals_added: list[tuple[str, str]] = []
    page.cellEditRequested.connect(lambda row, column, value: edits.append((row, column, value)))
    page.addGlobalRequested.connect(lambda name, value_type: globals_added.append((name, value_type)))

    page.model.item(0, 2).setText("String")
    assert edits[-1] == (0, "type", "String")
    page.search_edit.setText("MYMOD_B")
    app.processEvents()
    assert page.proxy.rowCount() == 1

    page.set_global_mode(True)
    page.global_name_edit.setText("MYMOD_NEW")
    page.global_type_combo.setCurrentText("String")
    page.add_global_button.click()
    assert globals_added[-1] == ("MYMOD_NEW", "String")
    assert not page.global_name_edit.isHidden()


def test_tlk_page_search_jump_and_inline_edit_are_controller_driven(app: QtWidgets.QApplication) -> None:
    page = TalkTablePage()
    page.set_entries(
        (
            {"strref": 0, "text": "Hello there", "voiceover": "vo_hello", "sound_length": 1.0},
            {"strref": 1, "text": "Goodbye", "voiceover": "vo_bye", "sound_length": 0.5},
        ),
        language="English",
    )
    edits: list[tuple[int, dict[str, object]]] = []
    jumps: list[int] = []
    page.entryEditRequested.connect(lambda strref, payload: edits.append((strref, payload)))
    page.jumpRequested.connect(jumps.append)

    page.model.item(1, 1).setText("Farewell")
    assert edits[-1] == (1, {"text": "Farewell"})
    page.search_edit.setText("farewell")
    app.processEvents()
    assert page.proxy.rowCount() == 1
    page.jump_spin.setValue(1)
    page.jump_button.click()
    assert jumps[-1] == 1


def test_lip_ssf_page_presents_both_formats_and_emits_edit_intent(app: QtWidgets.QApplication) -> None:
    page = LipSoundSetPage()
    shapes = (
        "NEUTRAL", "EE", "EH", "AH", "OH", "OOH", "Y", "STS",
        "FV", "NG", "TH", "MPB", "TD", "SH", "L", "KG",
    )
    page.set_lip(1.0, ({"time": 0.0, "shape": 0}, {"time": 0.5, "shape": 3}), shapes)
    page.set_sound_set(tuple(f"SLOT_{index}" for index in range(28)), tuple(-1 for _ in range(28)))
    assert page.lip_model.rowCount() == 2
    assert page.ssf_model.rowCount() == 28

    lip_edits: list[tuple[int, dict[str, object]]] = []
    ssf_edits: list[tuple[int, int]] = []
    page.lipKeyframeEditRequested.connect(lambda index, payload: lip_edits.append((index, payload)))
    page.soundSetSlotEditRequested.connect(lambda index, strref: ssf_edits.append((index, strref)))
    page.lip_model.item(1, 0).setText("0.75")
    page.ssf_model.item(6, 1).setText("42001")
    assert lip_edits[-1] == (1, {"time": 0.75})
    assert ssf_edits[-1] == (6, 42001)

    audio_requests: list[str] = []
    page.lipAudioPlayRequested.connect(audio_requests.append)
    page.set_lip_audio_path("C:/preview/line.wav")
    page.lip_audio_play_button.click()
    assert audio_requests == ["C:/preview/line.wav"]
    page.set_lip_audio_state(
        "Previewing matching audio",
        position_ms=720,
        duration_ms=1000,
        playing=True,
    )
    assert page.lip_audio_progress.value() == 720
    assert page.lip_table.currentIndex().row() == 1
    assert page.lip_audio_stop_button.isEnabled()

    page.set_sound_set(SoundSetDocument.slot_names(), tuple(range(49)), source_name="retail.ssf")
    assert page.ssf_model.rowCount() == 49
    assert "Unnamed Retail Entry 33" in page.ssf_model.item(33, 0).text()

    page.apply_ghost_theme(type("Theme", (), {"name": "Dark"})())
    page.apply_ghost_layout(type("Layout", (), {"id": "Default"})())
    assert page.property("ghostTheme") == "Dark"
    assert page.property("ghostLayout") == "Default"
