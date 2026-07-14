from __future__ import annotations

from pathlib import Path

import pytest

from src.core.scripting.blueprint_authoring import BlueprintGFFDocument


def _fixture_bytes() -> bytes:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, GFFStruct, bytes_gff
    from utility.common.geometry import Vector3, Vector4

    gff = GFF(GFFContent.UTP)
    root = gff.root
    root.set_uint8("Useable", 1)
    root.set_int8("TinySigned", -7)
    root.set_uint16("Faction", 12)
    root.set_int16("Penalty", -20)
    root.set_uint32("Cost", 4000)
    root.set_int32("Plot", -1)
    root.set_uint64("UnknownCounter", 2**48 + 17)
    root.set_int64("UnknownSigned", -(2**40))
    root.set_single("Bearing", 1.25)
    root.set_double("Precise", 3.141592653589793)
    root.set_string("Tag", "fixture_placeable")
    root.set_resref("TemplateResRef", ResRef("fixture_plc"))
    root.set_locstring("LocName", LocalizedString(42, {0: "Male", 1: "Female"}))
    root.set_binary("UnknownBlob", b"\x00\x10\xFE\xFF")
    root.set_vector3("Position", Vector3(1.0, 2.0, 3.0))
    root.set_vector4("Orientation", Vector4(0.0, 0.0, 0.5, 1.0))
    root.set_string("", "empty labels are still addressable")
    root.set_string(" spaced ", "whitespace labels are not normalized")

    child = GFFStruct(77)
    child.set_int32("Signed", -99)
    child.set_string("~Meta", "keep this unknown nested field")
    root.set_struct("Child/Struct", child)

    inventory = GFFList()
    first = GFFStruct(501)
    first.set_resref("InventoryRes", ResRef("g_w_blstrpstl01"))
    first.set_uint16("Repos_PosX", 2)
    inventory.append(first)
    second = GFFStruct(777)
    second.set_string("Tag", "second_item")
    second.set_binary("Opaque", b"\xAA\xBB\xCC")
    inventory.append(second)
    root.set_list("InventoryList", inventory)
    return bytes_gff(gff)


def test_blueprint_document_addresses_nested_fields_and_preserves_complete_graph() -> None:
    from pykotor.resource.formats.gff import GFFFieldType, read_gff

    document = BlueprintGFFDocument.load(_fixture_bytes())
    summary = document.summary()
    assert summary.content_type == "UTP"
    assert summary.is_blueprint
    assert summary.root_struct_id == -1
    paths = {row.path for row in document.fields()}
    assert "$/Child~1Struct/Signed" in paths
    assert "$/Child~1Struct/~0Meta" in paths
    assert "$/InventoryList/#0/InventoryRes" in paths
    assert "$/InventoryList/#1/Opaque" in paths
    assert "$/" in paths
    assert document.value("$/") == "empty labels are still addressable"
    assert document.value("$/ spaced ") == "whitespace labels are not normalized"
    assert document.field("$/InventoryList").editable is False
    assert document.field("$/UnknownCounter").field_type == "UInt64"

    document.set_text("$/Child~1Struct/Signed", "-1234")
    document.set_text("$/InventoryList/#1/Tag", "edited_second")
    document.set_text("$/UnknownBlob", "0xDE AD:BE-EF")
    document.set_text("$/Position", "10.5, -2, 9")
    with pytest.raises(ValueError, match="between 0 and 255"):
        document.set_text("$/Useable", "256")
    with pytest.raises(TypeError, match="container"):
        document.set_text("$/InventoryList", "[]")

    written = read_gff(document.to_bytes())
    root = written.root
    assert written.content.name == "UTP"
    assert root.get_struct("Child/Struct").struct_id == 77
    assert root.get_struct("Child/Struct").get_int32("Signed") == -1234
    assert root.get_struct("Child/Struct").get_string("~Meta") == "keep this unknown nested field"
    assert root.what_type("UnknownCounter") is GFFFieldType.UInt64
    assert root.get_uint64("UnknownCounter") == 2**48 + 17
    assert root.get_binary("UnknownBlob") == b"\xDE\xAD\xBE\xEF"
    assert root.get_locstring("LocName").to_dict() == {"stringref": 42, "substrings": {0: "Male", 1: "Female"}}
    assert tuple(root.get_vector3("Position")) == pytest.approx((10.5, -2.0, 9.0))
    inventory = root.get_list("InventoryList")
    assert len(inventory) == 2
    assert inventory.at(0).struct_id == 501
    assert inventory.at(0).get_resref("InventoryRes").get() == "g_w_blstrpstl01"
    assert inventory.at(1).struct_id == 777
    assert inventory.at(1).get_string("Tag") == "edited_second"
    assert inventory.at(1).get_binary("Opaque") == b"\xAA\xBB\xCC"


def test_blueprint_document_edits_every_scalar_type_with_exact_type_retention() -> None:
    from pykotor.resource.formats.gff import GFFFieldType, read_gff

    document = BlueprintGFFDocument.load(_fixture_bytes())
    edits = {
        "$/Useable": "2",
        "$/TinySigned": "-8",
        "$/Faction": "65535",
        "$/Penalty": "-32768",
        "$/Cost": "0xFFFFFFFF",
        "$/Plot": "-2147483648",
        "$/UnknownCounter": str(2**64 - 1),
        "$/UnknownSigned": str(-(2**63)),
        "$/Bearing": "1.75",
        "$/Precise": "2.718281828459045",
        "$/Tag": "new_tag",
        "$/TemplateResRef": "new_plc",
        "$/LocName": '{"stringref": 9001, "substrings": {"0": "Edited", "1": "Edited female"}}',
        "$/UnknownBlob": "CA FE BA BE",
        "$/Position": "4, 5, 6",
        "$/Orientation": "0, 0.25, 0.5, 0.75",
    }
    original_types = {path: document.field(path).field_type for path in edits}
    for path, text in edits.items():
        document.set_text(path, text)
    root = read_gff(document.to_bytes()).root
    for path, field_type_name in original_types.items():
        label = path.rsplit("/", 1)[-1]
        assert root.what_type(label).name == field_type_name
    assert root.what_type("Useable") is GFFFieldType.UInt8
    assert root.get_uint8("Useable") == 2
    assert root.get_uint32("Cost") == 0xFFFFFFFF
    assert root.get_uint64("UnknownCounter") == 2**64 - 1
    assert root.get_resref("TemplateResRef").get() == "new_plc"
    assert root.get_locstring("LocName").stringref == 9001


def test_blueprint_document_atomic_save_and_content_mismatch_diagnostic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pykotor.resource.formats.gff import read_gff

    target = tmp_path / "fixture.utc"
    target.write_bytes(b"existing user data")
    document = BlueprintGFFDocument.load(_fixture_bytes())
    document.set_text("$/Tag", "saved_tag")
    diagnostics = document.validate()
    assert diagnostics == ()  # No source extension exists yet.

    def reject_write(_self: BlueprintGFFDocument) -> bytes:
        raise ValueError("synthetic verification failure")

    original_to_bytes = BlueprintGFFDocument.to_bytes
    monkeypatch.setattr(BlueprintGFFDocument, "to_bytes", reject_write)
    with pytest.raises(ValueError, match="synthetic verification failure"):
        document.save(target)
    assert target.read_bytes() == b"existing user data"
    assert not tuple(tmp_path.glob("*.tmp"))

    monkeypatch.setattr(BlueprintGFFDocument, "to_bytes", original_to_bytes)
    saved = document.save(target)
    assert saved == target
    assert read_gff(target).root.get_string("Tag") == "saved_tag"
    assert not document.dirty
    assert not tuple(tmp_path.glob("*.tmp"))
    mismatch = document.validate()
    assert any(row.code == "gff.extension_content_mismatch" for row in mismatch)


def test_blueprint_search_returns_paths_types_and_values() -> None:
    document = BlueprintGFFDocument.load(_fixture_bytes())
    assert [row.path for row in document.search("second_item")] == ["$/InventoryList/#1/Tag"]
    uint64_matches = document.search("uint64")
    assert {row.path for row in uint64_matches} == {"$/UnknownCounter"}
    assert document.search("") == document.fields()


def test_blueprint_checkpoint_restores_verified_values_path_and_dirty_state(tmp_path: Path) -> None:
    source = tmp_path / "checkpoint.utp"
    source.write_bytes(_fixture_bytes())
    document = BlueprintGFFDocument.load(source)
    document.set_text("$/Tag", "first_unsaved_edit")
    checkpoint = document.checkpoint()
    document.set_text("$/Tag", "second_edit")
    document.restore(checkpoint)
    assert document.value("$/Tag") == "first_unsaved_edit"
    assert document.source_path == source
    assert document.dirty
