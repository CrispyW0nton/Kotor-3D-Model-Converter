from __future__ import annotations

import configparser
import io
import struct

import pytest

from src.core.scripting.data_authoring import (
    GLOBAL_BOOLEAN,
    GLOBAL_NUMBER,
    GLOBAL_STRING,
    GlobalVariableTable,
    JournalDocument,
    JournalEntryRecord,
    LipDocument,
    LocalizedText,
    SoundSetDocument,
    TalkTableDocument,
    TwoDADocument,
)


def test_2da_edit_snapshot_binary_roundtrip_and_tslpatcher_diff() -> None:
    original = TwoDADocument(("label", "value"), ("0",), (("base", "1"),))
    edited = TwoDADocument.from_snapshot(original.snapshot())
    undo_point = edited.snapshot()

    edited.add_column("added", "****")
    edited.set_cell(0, "value", "2")
    edited.set_cell(0, "added", "X")
    edited.add_row({"label": "new", "value": "3", "added": "Y"}, label="1")

    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_file(io.StringIO(edited.export_changes_ini(original, "appearance.2da")))
    assert parser["2DAList"]["Table0"] == "appearance.2da"
    assert parser["appearance.2da"]["AddColumn0"] == "appearance_add_column_0"
    assert parser["appearance.2da"]["ChangeRow0"] == "appearance_change_row_0"
    assert parser["appearance.2da"]["AddRow0"] == "appearance_add_row_0"
    assert parser["appearance_change_row_0"]["RowIndex"] == "0"
    assert parser["appearance_change_row_0"]["value"] == "2"
    assert parser["appearance_add_row_0"]["RowLabel"] == "1"

    reloaded = TwoDADocument.load(edited.to_bytes())
    assert reloaded.snapshot() == edited.snapshot()
    edited.restore(undo_point)
    assert edited.snapshot() == original.snapshot()

    deleted = TwoDADocument.from_snapshot(original.snapshot())
    deleted.remove_row(0)
    with pytest.raises(ValueError, match="DeleteRow"):
        deleted.export_changes_ini(original, "appearance.2da")


def test_2da_duplicate_rename_and_atomic_clipboard_edits_restore_from_snapshot() -> None:
    document = TwoDADocument(
        ("name", "value"),
        ("0", "1"),
        (("alpha", "10"), ("beta", "20")),
    )
    original = document.snapshot()

    assert document.duplicate_rows((1, 0)) == (2, 3)
    assert document.labels == ("0", "1", "2", "3")
    assert document.row(2) == {"name": "beta", "value": "20"}
    assert document.row(3) == {"name": "alpha", "value": "10"}
    assert document.rename_column("value", "amount") == 1
    assert document.headers == ("name", "amount")

    before_paste = document.snapshot()
    document.apply_cell_edits(
        (
            (0, None, "1"),
            (1, None, "0"),
            (0, "amount", "99"),
        )
    )
    assert document.labels[:2] == ("1", "0")
    assert document.cell(0, "amount") == "99"

    with pytest.raises(ValueError, match="unique"):
        document.apply_cell_edits(((0, None, "0"),))
    assert document.cell(0, "amount") == "99"

    document.restore(before_paste)
    assert document.snapshot() == before_paste
    document.restore(original)
    assert document.snapshot() == original


def test_tlk_edit_preserves_unknown_flags_metadata_raw_resref_and_trailing_data() -> None:
    flags = 0x01 | 0x02 | 0x04 | 0x08
    text = "Original".encode("cp1252")
    sound_raw = b"vo\xffice".ljust(16, b"\0")
    header = struct.pack("<4s4sIII", b"TLK ", b"V3.0", 0, 1, 60)
    entry = struct.pack("<I16sIIIIf", flags, sound_raw, 11, 22, 0, len(text), 1.25)
    source = header + entry + text + b"\xAA\xBB"

    document = TalkTableDocument.load(source)
    assert document.entry(0).voiceover == "voice"
    document.update_entry(0, text="Changed — text")
    output = document.to_bytes()
    out_flags, out_sound, volume, pitch, _, _, sound_length = struct.unpack_from("<I16sIIIIf", output, 20)

    assert out_flags & 0x08
    assert out_flags & 0x04
    assert out_sound == sound_raw
    assert volume == 11
    assert pitch == 22
    assert sound_length == pytest.approx(1.25)
    assert output.endswith(b"\xAA\xBB")
    assert TalkTableDocument.load(output).search("changed") == (0,)


def test_jrl_roundtrip_uses_entrylist_word_end_and_preserves_unknown_fields() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFFieldType, GFFList, bytes_gff, read_gff

    source = GFF(GFFContent.JRL)
    source.root.set_string("GhostRootField", "keep-root")
    categories = source.root.set_list("Categories", GFFList())
    category = categories.add(0)
    category.set_string("Comment", "developer note")
    category.set_locstring("Name", LocalizedString.from_english("Quest Name"))
    category.set_int32("PlanetID", 2)
    category.set_int32("PlotIndex", 3)
    category.set_uint32("Priority", 1)
    category.set_string("Tag", "K_TEST_QUEST")
    category.set_uint8("GhostCatField", 77)
    entries = category.set_list("EntryList", GFFList())
    entry = entries.add(0)
    entry.set_uint16("End", 0)
    entry.set_uint32("ID", 10)
    entry.set_locstring("Text", LocalizedString.from_english("Started"))
    entry.set_single("XP_Percentage", 0.0)
    entry.set_string("GhostEntryField", "keep-entry")

    document = JournalDocument.load(bytes(bytes_gff(source)))
    old = document.quests[0].entries[0]
    document.update_entry(0, 0, text=old.text.with_english("Updated"), end=True)
    document.add_entry(0, JournalEntryRecord(20, LocalizedText.from_english("Complete"), True))

    result = read_gff(document.to_bytes())
    result_category = result.root.get_list("Categories")[0]
    result_entries = result_category.get_list("EntryList")
    assert result.root.get_string("GhostRootField") == "keep-root"
    assert result_category.get_uint8("GhostCatField") == 77
    assert result_entries[0].get_string("GhostEntryField") == "keep-entry"
    assert result_entries[0].what_type("End") is GFFFieldType.UInt16
    assert not result_category.exists("Entries")
    assert JournalDocument.load(document.to_bytes()).quests[0].entries[0].text.english == "Updated"


def test_globalcat_contract_registers_boolean_number_string_and_preserves_location() -> None:
    source = TwoDADocument(
        ("name", "type"),
        ("0",),
        (("K_LAST_LOCATION", "Location"),),
    )
    globals_table = GlobalVariableTable(TwoDADocument.load(source.to_bytes()))
    undo_point = globals_table.snapshot()
    globals_table.add_variable("MYMOD_ENABLED", GLOBAL_BOOLEAN)
    globals_table.add_variable("MYMOD_STATE", GLOBAL_NUMBER)
    globals_table.add_variable("MYMOD_LABEL", GLOBAL_STRING)

    assert [variable.value_type for variable in globals_table.variables] == [
        "Location",
        "Boolean",
        "Number",
        "String",
    ]
    assert not globals_table.validate()
    reloaded = GlobalVariableTable.load(globals_table.to_bytes())
    assert [variable.name for variable in reloaded.variables][-3:] == [
        "MYMOD_ENABLED",
        "MYMOD_STATE",
        "MYMOD_LABEL",
    ]
    with pytest.raises(ValueError, match="already exists"):
        globals_table.add_variable("mymod_enabled", GLOBAL_BOOLEAN)
    globals_table.restore(undo_point)
    assert len(globals_table.variables) == 1


def test_lip_keyframe_authoring_snapshot_and_pykotor_roundtrip() -> None:
    document = LipDocument()
    document.add_keyframe(0.0, "NEUTRAL")
    document.add_keyframe(0.25, "AH")
    snapshot = document.snapshot()
    document.add_keyframe(0.5, "MPB")
    document.set_duration(1.0)

    assert len(document.shape_names()) == 16
    assert document.shape_for_phoneme("B") == 11
    assert not document.validate()
    reloaded = LipDocument.load(document.to_bytes())
    assert reloaded.duration == pytest.approx(1.0)
    assert [(frame.time, frame.shape) for frame in reloaded.keyframes] == [
        (pytest.approx(0.0), 0),
        (pytest.approx(0.25), 3),
        (pytest.approx(0.5), 11),
    ]
    document.restore(snapshot)
    assert document.snapshot() == snapshot


def test_ssf_28_slot_edit_snapshot_and_pykotor_roundtrip() -> None:
    document = SoundSetDocument()
    assert len(document.slot_names()) == 28
    assert document.slot_names()[0] == "BATTLE_CRY_1"
    assert document.slot_names()[-1] == "POISONED"
    snapshot = document.snapshot()

    assert document.set_slot("SELECT_1", 42001) == -1
    document.set_slot(27, 42002)
    assert document.get_slot("SELECT_1") == 42001
    assert document.get_slot("POISONED") == 42002
    assert not document.validate()

    reloaded = SoundSetDocument.load(document.to_bytes())
    assert reloaded.get_slot("SELECT_1") == 42001
    assert reloaded.get_slot("POISONED") == 42002
    document.restore(snapshot)
    assert set(document.stringrefs) == {-1}


def test_ssf_preserves_meaningful_retail_tail_entries_byte_exactly() -> None:
    import struct

    values = list(range(49))
    values[33] = 456_789
    raw = b"SSF V1.1" + struct.pack("<I", 12) + struct.pack("<49I", *values)

    document = SoundSetDocument.load(raw)

    assert len(document.stringrefs) == 49
    assert document.unknown_entries[5] == (33, 456_789)
    assert document.to_bytes() == raw
    document.set_slot("SELECT_1", 42001)
    assert document.stringrefs[33] == 456_789
    assert SoundSetDocument.load(document.to_bytes()).stringrefs[33] == 456_789
