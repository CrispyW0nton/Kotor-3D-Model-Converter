from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import src.core.scripting.studio as studio_module

from src.core.scripting.studio import (
    ScriptingStudioService,
    dialogue_node_text,
    dialogue_structure_summary,
    set_dialogue_node_text,
)


def _quiet_call(function, *args, **kwargs):
    """Contain diagnostic prints emitted by the currently bundled PyKotor GFF reader."""

    with redirect_stdout(io.StringIO()):
        return function(*args, **kwargs)


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("game", ["K1", "K2"])
def test_script_compile_produces_parseable_ncs_readback(game: str) -> None:
    from pykotor.resource.formats.ncs import read_ncs

    service = ScriptingStudioService()
    document = service.new_script(game=game, resref=f"gs_{game.lower()}_proof")
    document.source = "void main()\n{\n}\n"

    result = service.compile_script(document)

    assert result.ok is True
    assert result.readback_ok is True
    assert result.ncs_bytes.startswith(b"NCS V1.0")
    assert read_ncs(result.ncs_bytes) is not None
    assert "script.compiler_readback_passed" in {row.code for row in result.diagnostics}
    if game == "K2":
        assert "script.k2_dialect_subset" in {row.code for row in result.diagnostics}


def test_script_validation_blocks_invalid_resrefs_and_embedded_bytecode() -> None:
    service = ScriptingStudioService()

    invalid_resref = service.new_script(game="K2", resref="valid_name")
    invalid_resref.resref = "Invalid Resource Name"
    invalid_result = service.compile_script(invalid_resref)

    embedded_bytecode = service.new_script(game="K2", resref="gs_embedded")
    embedded_bytecode.source = (
        "void main() {}\n"
        "__NCS_BYTECODE__\n"
        "TkNTIFYxLjAAAA==\n"
        "__END_NCS_BYTECODE__\n"
    )
    embedded_result = service.compile_script(embedded_bytecode)

    assert invalid_result.ok is False
    assert invalid_result.ncs_bytes == b""
    assert "narrative.invalid_resref" in {row.code for row in invalid_result.diagnostics}
    assert embedded_result.ok is False
    assert embedded_result.ncs_bytes == b""
    assert "script.embedded_bytecode_blocked" in {
        row.code for row in embedded_result.diagnostics
    }


def test_new_dialogue_roundtrips_without_changing_graph() -> None:
    from pykotor.resource.generics.dlg import read_dlg

    service = ScriptingStudioService()
    document = service.new_dialogue(game="K2", resref="gs_roundtrip")
    before = dialogue_structure_summary(document.dialogue)

    payload, diagnostics = _quiet_call(service.dialogue_bytes, document)
    readback = _quiet_call(read_dlg, payload)

    assert payload.startswith(b"DLG V3.2")
    assert dialogue_structure_summary(readback) == before
    assert dialogue_node_text(readback.starters[0].node) == "New dialogue line"
    assert not any(row.blocking for row in diagnostics)
    assert "dialogue.structural_readback_passed" in {row.code for row in diagnostics}


def _add_player_reply(document, *, display_inactive: bool = False):
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLGLink, DLGReply

    reply = DLGReply()
    reply.text = LocalizedString.from_english("Player reply")
    link = DLGLink(reply)
    link.display_inactive = bool(display_inactive)
    document.dialogue.starters[0].node.links.append(link)
    return link


def test_k2_authored_display_inactive_roundtrips_as_typed_gff_byte() -> None:
    from pykotor.resource.formats.gff import GFFFieldType, read_gff

    service = ScriptingStudioService()
    document = service.new_dialogue(game="K2", resref="gs_display")
    _add_player_reply(document, display_inactive=True)

    payload, diagnostics = _quiet_call(service.dialogue_bytes, document)
    gff = read_gff(payload)
    link_struct = gff.root.get_list("EntryList")[0].get_list("RepliesList")[0]
    readback = _quiet_call(
        service.dialogue_from_bytes,
        payload,
        game="K2",
        resref="gs_display",
    )

    assert payload and not any(row.blocking for row in diagnostics)
    assert link_struct.what_type("DisplayInactive") is GFFFieldType.UInt8
    assert link_struct.get_uint8("DisplayInactive") == 1
    assert readback.dialogue.starters[0].node.links[0].display_inactive is True
    assert "dialogue.display_inactive_not_serialized" not in {
        row.code for row in diagnostics
    }


def test_k2_imported_display_inactive_edits_preserve_unknown_fields() -> None:
    from pykotor.resource.formats.gff import GFFFieldType, bytes_gff, read_gff

    service = ScriptingStudioService()
    authored = service.new_dialogue(game="K2", resref="gs_display_edit")
    _add_player_reply(authored)
    source_payload, source_diagnostics = _quiet_call(service.dialogue_bytes, authored)
    assert source_payload and not any(row.blocking for row in source_diagnostics)

    source_gff = read_gff(source_payload)
    source_gff.root.set_string("GSRootUnknown", "retain_root")
    source_payload = bytes(bytes_gff(source_gff))
    document = _quiet_call(
        service.dialogue_from_bytes,
        source_payload,
        game="K2",
        resref="gs_display_edit",
    )
    imported_link = document.dialogue.starters[0].node.links[0]
    assert imported_link.display_inactive is False

    imported_link.display_inactive = True
    enabled_payload, enabled_diagnostics = _quiet_call(service.dialogue_bytes, document)
    enabled_gff = read_gff(enabled_payload)
    enabled_struct = enabled_gff.root.get_list("EntryList")[0].get_list("RepliesList")[0]
    assert enabled_struct.what_type("DisplayInactive") is GFFFieldType.UInt8
    assert enabled_struct.get_uint8("DisplayInactive") == 1
    assert enabled_gff.root.get_string("GSRootUnknown") == "retain_root"
    assert not any(row.blocking for row in enabled_diagnostics)

    reloaded = _quiet_call(
        service.dialogue_from_bytes,
        enabled_payload,
        game="K2",
        resref="gs_display_edit",
    )
    reloaded.dialogue.starters[0].node.links[0].display_inactive = False
    disabled_payload, disabled_diagnostics = _quiet_call(service.dialogue_bytes, reloaded)
    disabled_gff = read_gff(disabled_payload)
    disabled_struct = disabled_gff.root.get_list("EntryList")[0].get_list("RepliesList")[0]

    assert disabled_struct.what_type("DisplayInactive") is GFFFieldType.UInt8
    assert disabled_struct.get_uint8("DisplayInactive") == 0
    assert disabled_gff.root.get_string("GSRootUnknown") == "retain_root"
    assert not any(row.blocking for row in disabled_diagnostics)


def test_k1_display_inactive_is_not_added_and_reports_k2_only_warning() -> None:
    from pykotor.resource.formats.gff import read_gff

    service = ScriptingStudioService()
    document = service.new_dialogue(game="K1", resref="gs_display_k1")
    _add_player_reply(document, display_inactive=True)

    payload, diagnostics = _quiet_call(service.dialogue_bytes, document)
    gff = read_gff(payload)
    link_struct = gff.root.get_list("EntryList")[0].get_list("RepliesList")[0]

    assert payload and not any(row.blocking for row in diagnostics)
    assert not link_struct.exists("DisplayInactive")
    assert "dialogue.k2_link_fields_ignored_for_k1" in {
        row.code for row in diagnostics
    }


def test_imported_dialogue_preserves_localized_string_when_display_text_is_unchanged() -> None:
    from pykotor.common.language import Gender, Language, LocalizedString
    from pykotor.resource.generics.dlg import read_dlg

    service = ScriptingStudioService()
    authored = service.new_dialogue(game="K2", resref="gs_localized")
    node = authored.dialogue.starters[0].node
    original = LocalizedString(4242)
    original.set_data(Language.ENGLISH, Gender.MALE, "Embedded English fallback")
    original.set_data(Language.FRENCH, Gender.FEMALE, "Texte francais conserve")
    node.text = original

    source_payload, source_diagnostics = _quiet_call(service.dialogue_bytes, authored)
    assert source_payload and not any(row.blocking for row in source_diagnostics)
    document = _quiet_call(
        service.dialogue_from_bytes,
        source_payload,
        game="K2",
        resref="gs_localized",
    )
    node = document.dialogue.starters[0].node
    imported_localized_string = node.text
    original_substrings = dict(imported_localized_string._substrings_internal)

    displayed = dialogue_node_text(
        node,
        tlk_lookup=lambda stringref: "Resolved TLK dialogue" if stringref == 4242 else "",
    )
    set_dialogue_node_text(node, displayed)
    node.speaker = "ChangedSpeaker"

    assert node.text is imported_localized_string
    assert node.text.stringref == 4242
    assert dict(node.text._substrings_internal) == original_substrings

    payload, diagnostics = _quiet_call(service.dialogue_bytes, document)
    readback = _quiet_call(read_dlg, payload)
    persisted = readback.starters[0].node.text

    assert persisted.stringref == 4242
    assert dict(persisted._substrings_internal) == original_substrings
    assert readback.starters[0].node.speaker == "ChangedSpeaker"
    assert not any(row.blocking for row in diagnostics)


def _dialogue_with_unknown_fields(service: ScriptingStudioService) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    authored = service.new_dialogue(game="K2", resref="gs_preserve")
    canonical_bytes, diagnostics = _quiet_call(service.dialogue_bytes, authored)
    assert canonical_bytes and not any(row.blocking for row in diagnostics)
    gff = read_gff(canonical_bytes)
    gff.root.set_string("GSRootUnknown", "retain_root")
    gff.root.get_list("EntryList")[0].set_string("GSNodeUnknown", "retain_node")
    return bytes(bytes_gff(gff))


def test_imported_dialogue_preserves_unknown_root_and_nested_gff_fields() -> None:
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.generics.dlg import read_dlg

    service = ScriptingStudioService()
    source_bytes = _dialogue_with_unknown_fields(service)
    document = _quiet_call(
        service.dialogue_from_bytes,
        source_bytes,
        game="K2",
        resref="gs_preserve",
    )
    set_dialogue_node_text(document.dialogue.starters[0].node, "Edited safely")
    document.dirty = True

    written_bytes, diagnostics = _quiet_call(service.dialogue_bytes, document)
    written_gff = read_gff(written_bytes)
    written_dialogue = _quiet_call(read_dlg, written_bytes)

    assert written_gff.root.get_string("GSRootUnknown") == "retain_root"
    assert (
        written_gff.root.get_list("EntryList")[0].get_string("GSNodeUnknown")
        == "retain_node"
    )
    assert dialogue_node_text(written_dialogue.starters[0].node) == "Edited safely"
    assert "dialogue.unknown_fields_preserved" in {row.code for row in diagnostics}
    assert not any(row.blocking for row in diagnostics)


def test_imported_dialogue_blocks_topology_change_when_unknown_fields_exist() -> None:
    from pykotor.resource.generics.dlg import DLGEntry, DLGLink

    service = ScriptingStudioService()
    document = _quiet_call(
        service.dialogue_from_bytes,
        _dialogue_with_unknown_fields(service),
        game="K2",
        resref="gs_preserve",
    )
    document.dialogue.starters.append(DLGLink(DLGEntry()))

    written_bytes, diagnostics = _quiet_call(service.dialogue_bytes, document)

    assert written_bytes == b""
    assert any(row.blocking for row in diagnostics)
    failure = next(row for row in diagnostics if row.code == "dialogue.write_readback_failed")
    assert "blocked the write instead of discarding unmapped data" in failure.message


def test_explicit_editable_copy_preserves_imported_source_and_allows_topology(tmp_path: Path) -> None:
    from src.core.scripting.dialogue_contract import start_dialogue_at_existing_node

    service = ScriptingStudioService()
    source_bytes = _dialogue_with_unknown_fields(service)
    original_path = tmp_path / "protected_source.dlg"
    original_path.write_bytes(source_bytes)
    document = _quiet_call(service.load_dialogue, original_path, game="K2")
    original_dialogue = document.dialogue
    original_summary = dialogue_structure_summary(original_dialogue)

    assert service.dialogue_topology_requires_editable_copy(document) is True
    with pytest.raises(ValueError, match="new path"):
        service.make_editable_dialogue_copy(
            document,
            resref="protected_source",
            source_path=original_path,
        )

    authored_path = tmp_path / "protected_editable.dlg"
    authored = service.make_editable_dialogue_copy(
        document,
        resref="protected_editable",
        source_path=authored_path,
    )
    start_dialogue_at_existing_node(authored.dialogue, authored.dialogue.starters[0].node)
    payload, diagnostics = _quiet_call(service.dialogue_bytes, authored)

    assert payload.startswith(b"DLG ")
    assert not any(row.blocking for row in diagnostics)
    assert dialogue_structure_summary(authored.dialogue)["starters"] == 2
    assert authored.source_bytes == b""
    assert authored.origin == "authored_copy"
    assert document.dialogue is original_dialogue
    assert document.source_bytes == source_bytes
    assert document.source_path == str(original_path)
    assert dialogue_structure_summary(document.dialogue) == original_summary
    assert original_path.read_bytes() == source_bytes


def test_shared_and_cyclic_topology_passes_structural_writer_readback() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLGLink, DLGReply, read_dlg
    from src.core.scripting.dialogue_contract import connect_existing_dialogue_node

    service = ScriptingStudioService()
    document = service.new_dialogue(game="K2", resref="gs_graph")
    entry = document.dialogue.starters[0].node
    reply = DLGReply()
    reply.text = LocalizedString.from_english("Loop back")
    entry.links.append(DLGLink(reply))
    connect_existing_dialogue_node(document.dialogue, entry, reply)
    connect_existing_dialogue_node(document.dialogue, reply, entry)

    payload, diagnostics = _quiet_call(service.dialogue_bytes, document)
    readback = _quiet_call(read_dlg, payload)

    assert payload.startswith(b"DLG ")
    assert not any(row.blocking for row in diagnostics)
    assert dialogue_structure_summary(readback) == {
        "starters": 1,
        "links": 4,
        "nodes": 2,
        "entries": 1,
        "replies": 1,
    }
    assert "dialogue.structural_readback_passed" in {row.code for row in diagnostics}


def test_blocked_build_is_non_mutating_and_successful_build_writes_manifest(
    tmp_path: Path,
) -> None:
    service = ScriptingStudioService()
    blocked_output = tmp_path / "blocked"
    blocked_resources = blocked_output / "resources"
    blocked_resources.mkdir(parents=True)
    sentinel = blocked_resources / "existing.ncs"
    sentinel.write_bytes(b"existing-resource")
    old_manifest = blocked_output / "narrative-build.json"
    old_manifest.write_text('{"state":"existing"}\n', encoding="utf-8")

    broken_script = service.new_script(game="K2", resref="gs_broken")
    broken_script.source = "void main(\n"
    blocked_result = service.build([broken_script], blocked_output, game="K2")

    assert blocked_result.ok is False
    assert blocked_result.committed is False
    assert "script.compile_failed" in {row.code for row in blocked_result.diagnostics}
    assert sentinel.read_bytes() == b"existing-resource"
    assert old_manifest.read_text(encoding="utf-8") == '{"state":"existing"}\n'

    script = service.new_script(game="K2", resref="gs_success")
    script.source = "void main()\n{\n}\n"
    dialogue = service.new_dialogue(game="K2", resref="gs_dialogue")
    output = tmp_path / "success"
    result = _quiet_call(service.build, [script, dialogue], output, game="K2")

    assert result.ok is True
    assert result.committed is True
    assert Path(result.manifest_path) == output / "narrative-build.json"
    assert {(row.resref, row.restype) for row in result.resources} == {
        ("gs_success", "nss"),
        ("gs_success", "ncs"),
        ("gs_dialogue", "dlg"),
    }
    assert {(resref, restype) for resref, restype, _data in result.resource_tuples()} == {
        ("gs_success", "ncs"),
        ("gs_dialogue", "dlg"),
    }

    manifest = json.loads((output / "narrative-build.json").read_text(encoding="utf-8"))
    assert manifest["file_type"] == "GhostStudioNarrativeBuild"
    assert manifest["schema_version"] == 1
    assert manifest["game"] == "K2"
    assert manifest["engine_proof"] == "not_recorded"
    assert {row["filename"] for row in manifest["resources"]} == {
        "gs_success.nss",
        "gs_success.ncs",
        "gs_dialogue.dlg",
    }
    for row in manifest["resources"]:
        payload = (output / "resources" / row["filename"]).read_bytes()
        assert row["byte_count"] == len(payload)
        assert row["sha256"] == hashlib.sha256(payload).hexdigest()


def test_successful_rebuild_replaces_tree_and_removes_previous_resources(tmp_path: Path) -> None:
    service = ScriptingStudioService()
    output = tmp_path / "replace-build"
    old_script = service.new_script(game="K2", resref="gs_old")
    old_script.source = "void main()\n{\n}\n"
    old_dialogue = service.new_dialogue(game="K2", resref="gs_old_dlg")

    first = _quiet_call(service.build, [old_script, old_dialogue], output, game="K2")
    assert first.ok
    new_script = service.new_script(game="K2", resref="gs_new")
    new_script.source = "void main()\n{\n}\n"
    second = _quiet_call(service.build, [new_script], output, game="K2")

    assert second.ok
    manifest = json.loads((output / "narrative-build.json").read_text(encoding="utf-8"))
    expected = {row["filename"] for row in manifest["resources"]}
    actual = {path.name for path in (output / "resources").iterdir() if path.is_file()}
    assert actual == expected == {"gs_new.nss", "gs_new.ncs"}
    assert not any(name.startswith("gs_old") for name in actual)


def test_promotion_failure_restores_previous_build_without_mixed_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ScriptingStudioService()
    output = tmp_path / "rollback-build"
    old_script = service.new_script(game="K2", resref="gs_before")
    old_script.source = "void main()\n{\n}\n"
    assert _quiet_call(service.build, [old_script], output, game="K2").ok
    before = _snapshot_tree(output)

    new_script = service.new_script(game="K2", resref="gs_after")
    new_script.source = "void main()\n{\n}\n"
    real_replace = studio_module.os.replace
    failed = False

    def fail_staging_promotion(source, destination):
        nonlocal failed
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            not failed
            and source_path.name.startswith(f".{output.name}.stage-")
            and destination_path == output
        ):
            failed = True
            raise PermissionError("simulated locked promotion")
        return real_replace(source, destination)

    monkeypatch.setattr(studio_module.os, "replace", fail_staging_promotion)
    result = _quiet_call(service.build, [new_script], output, game="K2")

    assert not result.ok and not result.committed
    assert "narrative.build_promotion_failed" in {row.code for row in result.diagnostics}
    assert _snapshot_tree(output) == before
    assert not list(tmp_path.glob(f".{output.name}.stage-*"))
    assert not list(tmp_path.glob(f".{output.name}.backup-*"))


def test_nonempty_unowned_output_is_never_replaced(tmp_path: Path) -> None:
    service = ScriptingStudioService()
    output = tmp_path / "user-folder"
    output.mkdir()
    user_file = output / "do-not-delete.txt"
    user_file.write_bytes(b"user-owned")
    script = service.new_script(game="K2", resref="gs_safe")
    script.source = "void main()\n{\n}\n"

    result = _quiet_call(service.build, [script], output, game="K2")

    assert not result.ok and not result.committed
    assert "narrative.output_not_owned" in {row.code for row in result.diagnostics}
    assert _snapshot_tree(output) == {"do-not-delete.txt": b"user-owned"}
