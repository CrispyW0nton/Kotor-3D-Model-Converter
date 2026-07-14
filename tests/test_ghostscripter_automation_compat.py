from __future__ import annotations

import asyncio
import base64
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_SRC = ROOT / "native" / "GhostRigger.Core.Automation" / "Python" / "src"
if str(AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_SRC))
SCENE_SRC = ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src"
if str(SCENE_SRC) not in sys.path:
    sys.path.insert(0, str(SCENE_SRC))


def _payload(result: dict) -> dict:
    return json.loads(result["text"])


def test_readme_inventory_is_exactly_sixty_unique_names() -> None:
    from kotormcp.tools.legacy_ghostscripter import compatibility_report

    report = compatibility_report()
    names = [row["legacy_name"] for row in report["tools"]]

    assert report["advertised_tool_count"] == 60
    assert report["inventory_count"] == 60
    assert len(names) == len(set(names)) == 60
    assert report["category_counts"] == {
        "composite": 17,
        "installation_discovery": 7,
        "patching": 1,
        "read_formats": 17,
        "scripts": 3,
        "targeted_lookup": 7,
        "write_formats": 8,
    }
    assert report["status_counts"] == {
        "callable_alias": 59,
        "core_service_only": 0,
        "missing": 0,
        "native_name": 1,
        "partial": 0,
    }


def test_all_callable_registry_names_are_registered_without_duplicates() -> None:
    from kotormcp.tools import get_all_tools
    from kotormcp.tools.legacy_ghostscripter import compatibility_report

    tools = get_all_tools()
    names = [row["name"] for row in tools]
    report = compatibility_report()
    callable_names = {row["callable_name"] for row in report["tools"] if row["exposed"]}

    assert len(tools) == 168
    assert len(names) == len(set(names))
    assert report["callable_legacy_count"] == 60
    assert callable_names <= set(names)
    assert "ghostrigger_ghostscripter_compatibility" in names


def test_composite_compatibility_wrappers_preserve_legacy_required_inputs() -> None:
    from kotormcp.tools import get_all_tools
    from kotormcp.tools.legacy_ghostscripter import handles_service_alias, resolve_direct_alias

    definitions = {row["name"]: row for row in get_all_tools()}
    assert definitions["getResource"]["inputSchema"]["required"] == ["game", "resref", "type"]
    assert definitions["getQuest"]["inputSchema"]["required"] == ["game", "questId"]
    assert definitions["getModule"]["inputSchema"]["required"] == ["game", "module_id"]
    assert all(handles_service_alias(name) for name in ("getResource", "getQuest", "getModule"))
    assert all(resolve_direct_alias(name, {}) is None for name in ("getResource", "getQuest", "getModule"))


def test_get_resource_wrapper_preserves_legacy_format_specific_shapes(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg
    from src.core.scripting.data_authoring import TwoDADocument

    creature = GFF(GFFContent.UTC)
    creature.root.set_string("Tag", "compat_resource")
    dialogue = DLG()
    dialogue_entry = DLGEntry()
    dialogue_entry.list_index = 0
    dialogue_entry.text = LocalizedString.from_english("Compatibility dialogue line")
    dialogue_entry.speaker = "COMPAT_NPC"
    dialogue_entry.script1 = ResRef("compat_dlg_run")
    dialogue.starters.append(DLGLink(dialogue_entry, 0))
    resources = {
        ("compat_table", "2da"): TwoDADocument(
            ["label", "value"], ["zero", "one"], [["alpha", "1"], ["beta", "2"]]
        ).to_bytes(),
        ("compat_resource", "utc"): bytes_gff(creature),
        ("compat_dialog", "dlg"): bytes_dlg(dialogue),
        ("compat_blob", "bin"): b"not-a-gff-resource",
        ("compat_broken", "utc"): b"broken-gff",
    }

    class _Installation:
        @staticmethod
        def talktable_string(stringref: int) -> str:
            return f"TLK {stringref}"

        @staticmethod
        def get_resource(resref: str, restype: str):
            data = resources.get((resref, restype))
            return SimpleNamespace(data=data, source=f"fixture:{restype}") if data is not None else None

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    table = _payload(
        asyncio.run(handle_tool("getResource", {"game": "K2", "resref": "compat_table", "type": "2da"}))
    )
    creature_result = _payload(
        asyncio.run(handle_tool("getResource", {"game": "K2", "resref": "compat_resource", "type": "utc"}))
    )
    dialogue_result = _payload(
        asyncio.run(handle_tool("getResource", {"game": "K2", "resref": "compat_dialog", "type": "dlg"}))
    )
    blob = _payload(
        asyncio.run(handle_tool("getResource", {"game": "K2", "resref": "compat_blob", "type": "bin"}))
    )
    broken = _payload(
        asyncio.run(handle_tool("getResource", {"game": "K2", "resref": "compat_broken", "type": "utc"}))
    )

    assert {key: table[key] for key in ("game", "resref", "type", "size_bytes")} == {
        "game": "K2",
        "resref": "compat_table",
        "type": "2da",
        "size_bytes": table["size_bytes"],
    }
    assert table["columns"] == ["label", "value"]
    assert table["row_count"] == 2
    assert table["rows"] == {
        "columns": ["label", "value"],
        "total_rows": 2,
        "offset": 0,
        "returned": 2,
        "rows": [
            {"__label": "zero", "label": "alpha", "value": "1"},
            {"__label": "one", "label": "beta", "value": "2"},
        ],
    }
    assert creature_result["fields"]["Tag"] == "compat_resource"
    assert dialogue_result["entry_count"] == 1
    assert dialogue_result["reply_count"] == 0
    assert dialogue_result["entries"] == [
        {
            "text": "Compatibility dialogue line",
            "strref": -1,
            "speaker": "COMPAT_NPC",
            "script1": "compat_dlg_run",
            "branches": [],
        }
    ]
    assert dialogue_result["starters"] == [
        {
            "index": 0,
            "is_reply": False,
            "is_child": False,
            "active_script": "",
            "active_script2": "",
            "link_comment": "",
            "display_inactive": False,
        }
    ]
    assert blob["note"] == "Unknown format; first 4KB returned as base64."
    assert base64.b64decode(blob["raw_base64"]) == b"not-a-gff-resource"
    assert "parse_error" in broken
    assert all(
        len(result["ghoststudio"]["sha256"]) == 64
        for result in (table, creature_result, dialogue_result, blob, broken)
    )


def test_get_quest_wrapper_preserves_legacy_states_scripts_and_dialogues(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, bytes_gff

    journal = GFF(GFFContent.JRL)
    categories = GFFList()
    category = categories.add(0)
    category.set_string("Tag", "compat_quest")
    category.set_locstring("Name", LocalizedString.from_english("Compatibility Quest"))
    states = GFFList()
    state = states.add(0)
    state.set_uint32("ID", 10)
    state.set_locstring("Text", LocalizedString.from_english("Find the compatibility token."))
    state.set_uint8("End", 0)
    state.set_resref("Script", ResRef("compat_q_script"))
    category.set_list("EntryList", states)
    journal.root.set_list("Categories", categories)

    dialogue = GFF(GFFContent.DLG)
    entries = GFFList()
    entry = entries.add(0)
    entry.set_resref("Script", ResRef("compat_q_script"))
    dialogue.root.set_list("EntryList", entries)
    journal_bytes = bytes_gff(journal)
    dialogue_bytes = bytes_gff(dialogue)
    resources = {
        ("global", "jrl"): journal_bytes,
        ("compat_q_script", "nss"): b"void main() { SetGlobalNumber(\"compat\", 1); }\n",
    }
    dialogue_entry = SimpleNamespace(
        resref="compat_q_dialog",
        restype="DLG",
        extension="dlg",
        data=dialogue_bytes,
        source="fixture:module",
    )

    class _Installation:
        @staticmethod
        def talktable_string(stringref: int) -> str:
            return f"TLK {stringref}"

        @staticmethod
        def get_resource(resref: str, restype: str):
            data = resources.get((resref, restype))
            return SimpleNamespace(data=data, source=f"fixture:{restype}") if data is not None else None

        @staticmethod
        def iter_resources(location: str):
            assert location == "all"
            yield dialogue_entry

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    result = _payload(
        asyncio.run(
            handle_tool(
                "getQuest",
                {
                    "game": "K1",
                    "questId": "compat_quest",
                    "includeScripts": True,
                    "includeDialogues": True,
                },
            )
        )
    )

    assert {key: result[key] for key in ("game", "quest_id", "name", "state_count")} == {
        "game": "K1",
        "quest_id": "compat_quest",
        "name": "Compatibility Quest",
        "state_count": 1,
    }
    assert result["states"] == [
        {
            "id": 10,
            "text": "Find the compatibility token.",
            "end": False,
            "Script": "compat_q_script",
        }
    ]
    assert "SetGlobalNumber" in result["scripts"]["compat_q_script"]
    assert result["dialogues_referencing_quest"] == [
        {
            "dlg_resref": "compat_q_dialog",
            "references": ["entry #0: 'compat_q_script'"],
        }
    ]
    assert result["ghoststudio"]["dialogues_examined"] == 1


def test_get_module_wrapper_preserves_legacy_identity_entry_and_area_summaries(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, bytes_gff

    module = GFF(GFFContent.IFO)
    module.root.set_locstring("Mod_Name", LocalizedString.from_english("Compatibility Module"))
    module.root.set_string("Mod_Tag", "compat_module")
    module.root.set_string("Mod_VO_ID", "compat_vo")
    module.root.set_resref("Mod_Entry_Area", ResRef("compat_area"))
    module.root.set_single("Mod_Entry_X", 1.0)
    module.root.set_single("Mod_Entry_Y", 2.0)
    module.root.set_single("Mod_Entry_Z", 3.0)
    module.root.set_single("Mod_Entry_Dir_X", 0.0)
    module.root.set_single("Mod_Entry_Dir_Y", 1.0)
    module.root.set_resref("Mod_OnModLoad", ResRef("compat_load"))
    areas = GFFList()
    area = areas.add(0)
    area.set_resref("Area_Name", ResRef("compat_area"))
    module.root.set_list("Mod_Area_list", areas)

    git = GFF(GFFContent.GIT)
    creatures = GFFList()
    creatures.add(0)
    creatures.add(0)
    doors = GFFList()
    doors.add(0)
    git.root.set_list("Creature List", creatures)
    git.root.set_list("Door List", doors)
    ifo_entry = SimpleNamespace(
        resref="module", restype="IFO", extension="ifo", data=bytes_gff(module), source="module:compat_module"
    )
    git_entry = SimpleNamespace(
        resref="compat_area", restype="GIT", extension="git", data=bytes_gff(git), source="module:compat_module"
    )

    class _Installation:
        @staticmethod
        def talktable_string(stringref: int) -> str:
            return f"TLK {stringref}"

        @staticmethod
        def get_resource(resref: str, restype: str):
            if (resref, restype) == ("module", "ifo"):
                return ifo_entry
            if (resref, restype) == ("compat_area", "git"):
                return git_entry
            return None

        @staticmethod
        def iter_resources(location: str):
            assert location == "module:compat_module"
            yield ifo_entry
            yield git_entry

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    result = _payload(
        asyncio.run(
            handle_tool(
                "getModule",
                {"game": "K2", "module_id": "compat_module", "include_git": True},
            )
        )
    )

    assert {key: result[key] for key in ("game", "module_id", "mod_name", "tag", "vo_id")} == {
        "game": "K2",
        "module_id": "compat_module",
        "mod_name": "Compatibility Module",
        "tag": "compat_module",
        "vo_id": "compat_vo",
    }
    assert [result[key] for key in ("entry_area", "entry_x", "entry_y", "entry_z", "entry_dir_x", "entry_dir_y")] == [
        "compat_area", 1.0, 2.0, 3.0, 0.0, 1.0
    ]
    assert result["areas"] == ["compat_area"]
    assert result["scripts"] == {"Mod_OnModLoad": "compat_load"}
    assert result["area_summaries"] == [
        {
            "area": "compat_area",
            "creatures": 2,
            "doors": 1,
            "placeables": 0,
            "waypoints": 0,
            "triggers": 0,
            "stores": 0,
            "sounds": 0,
            "encounters": 0,
        }
    ]
    assert result["module_sources"] == ["module:compat_module"]
    assert result["fields"]["Mod_Tag"] == "compat_module"
    assert result["ghoststudio"]["type_breakdown"] == {"git": 1, "ifo": 1}


def test_all_legacy_writers_are_callable_through_safe_ghoststudio_contracts() -> None:
    from kotormcp.tools import get_all_tools
    from kotormcp.tools.legacy_ghostscripter import compatibility_report

    registered = {row["name"] for row in get_all_tools()}
    report = compatibility_report()
    writer_rows = {row["legacy_name"]: row for row in report["tools"] if row["category"] == "write_formats"}

    assert set(writer_rows) == {
        "writeGFF",
        "writeDLG",
        "writeTwoDA",
        "writeERF",
        "writeSSF",
        "writeLIP",
        "writePTH",
        "writeOverride",
    }
    assert set(writer_rows) <= registered
    assert all(row["status"] == "callable_alias" for row in writer_rows.values())
    assert all(row["callable_name"] == name for name, row in writer_rows.items())
    assert "workspace_root" in writer_rows["writeOverride"]["note"]


def test_write_gff_preserves_typed_fields_and_requires_lossy_opt_in() -> None:
    from kotormcp.tools import handle_tool
    from pykotor.resource.formats.gff import GFFFieldType, read_gff

    document = {
        "schema": "ghostscripter.gff.typed.v1",
        "file_type": "UTC ",
        "content": "UTC",
        "file_version": "V3.2",
        "complete": True,
        "root": {
            "struct_id": -1,
            "fields": [
                {"label": "Signed", "type": "Int32", "type_id": 5, "value": -7},
                {"label": "Ref", "type": "ResRef", "type_id": 11, "value": "n_test"},
                {
                    "label": "Name",
                    "type": "LocalizedString",
                    "type_id": 12,
                    "value": {"stringref": -1, "substrings": [{"id": 0, "text": "Test NPC"}]},
                },
                {
                    "label": "Children",
                    "type": "List",
                    "type_id": 15,
                    "value": [
                        {
                            "struct_id": 42,
                            "fields": [
                                {"label": "Flag", "type": "UInt8", "type_id": 0, "value": 1}
                            ],
                        }
                    ],
                },
            ],
        },
    }
    response = _payload(asyncio.run(handle_tool("writeGFF", {"document": document})))
    payload = base64.b64decode(response["data_base64"], validate=True)
    gff = read_gff(payload)
    fields = {label: (field_type, value) for label, field_type, value in gff.root}

    assert payload.startswith(b"UTC V3.2")
    assert response["fidelity"] == "lossless_typed"
    assert fields["Signed"] == (GFFFieldType.Int32, -7)
    assert fields["Ref"][0] == GFFFieldType.ResRef and str(fields["Ref"][1]) == "n_test"
    assert fields["Name"][0] == GFFFieldType.LocalizedString
    assert fields["Name"][1]._substrings_internal[0] == "Test NPC"
    assert fields["Children"][1][0].struct_id == 42
    assert dict((label, value) for label, _kind, value in fields["Children"][1][0])["Flag"] == 1

    rejected = _payload(
        asyncio.run(handle_tool("writeGFF", {"fileType": "UTC ", "fields": {"Tag": "unsafe"}}))
    )
    assert "allowLossy=true" in rejected["error"]
    lossy = _payload(
        asyncio.run(
            handle_tool(
                "writeGFF",
                {"fileType": "UTC ", "fields": {"Tag": "new_creature", "Plot": True}, "allowLossy": True},
            )
        )
    )
    assert lossy["fidelity"] == "lossy_legacy"
    assert read_gff(base64.b64decode(lossy["data_base64"])).root.what_type("Plot") == GFFFieldType.UInt8


def test_write_dlg_uses_validated_graph_readback_and_patches_k2_link_fields() -> None:
    from kotormcp.tools import handle_tool
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from src.core.scripting.studio import ScriptingStudioService, dialogue_node_text, dialogue_structure_summary

    dialogue = {
        "entries": [
            {
                "text": "Hello there!",
                "strref": -1,
                "speaker": "bastila",
                "branches": [{"index": 0, "is_reply": True, "display_inactive": True}],
            }
        ],
        "replies": [{"text": "General Kenobi.", "strref": -1, "branches": []}],
        "starters": [{"index": 0, "is_reply": False}],
        "end_script": "k_end_scene",
    }
    response = _payload(
        asyncio.run(handle_tool("writeDLG", {"game": "k2", "resref": "compat_dlg", "dialogue": dialogue}))
    )
    payload = base64.b64decode(response["data_base64"], validate=True)
    service = ScriptingStudioService()
    readback = service.dialogue_from_bytes(payload, game="K2", resref="compat_dlg")
    summary = dialogue_structure_summary(readback.dialogue)
    entry_link = readback.dialogue.starters[0]
    entry = entry_link.node
    reply = entry.links[0].node
    gff = read_gff(payload)
    branch_struct = gff.root.get_list("EntryList")[0].get_list("RepliesList")[0]

    assert response["entry_count"] == response["reply_count"] == 1
    assert summary == {"starters": 1, "links": 2, "nodes": 2, "entries": 1, "replies": 1}
    assert dialogue_node_text(entry) == "Hello there!"
    assert dialogue_node_text(reply) == "General Kenobi."
    assert str(readback.dialogue.on_end) == "k_end_scene"
    assert branch_struct.get_uint8("DisplayInactive") == 1

    source_gff = read_gff(payload)
    source_gff.root.set_string("CompatUnknown", "retain me")
    source_payload = bytes_gff(source_gff)
    imported = {
        **dialogue,
        "entries": [{**dialogue["entries"][0], "text": "Edited imported line"}],
        "source_fidelity": {
            "schema": "ghostscripter.dlg.source-gff.v1",
            "required_for_lossless_save": True,
            "source_game": "K2",
            "binary_base64": base64.b64encode(source_payload).decode("ascii"),
        },
    }
    preserved = _payload(
        asyncio.run(handle_tool("writeDLG", {"game": "k2", "resref": "compat_dlg", "dialogue": imported}))
    )
    preserved_payload = base64.b64decode(preserved["data_base64"], validate=True)
    preserved_gff = read_gff(preserved_payload)
    preserved_dialogue = service.dialogue_from_bytes(preserved_payload, game="K2", resref="compat_dlg")

    assert preserved_gff.root.get_string("CompatUnknown") == "retain me"
    assert dialogue_node_text(preserved_dialogue.dialogue.starters[0].node) == "Edited imported line"


def test_write_twoda_and_erf_roundtrip_every_resource() -> None:
    from kotormcp.tools import handle_tool
    from src.core.scripting.data_authoring import TwoDADocument
    from src.core.scripting.packaging import inspect_narrative_archive

    table_args = {
        "resref": "compat_table",
        "columns": ["name", "value"],
        "rows": [{"label": "0", "name": "alpha", "value": "1"}],
        "edits": [{"row": "0", "column": "value", "value": "2"}],
    }
    binary = _payload(asyncio.run(handle_tool("writeTwoDA", {**table_args, "format": "binary"})))
    text = _payload(asyncio.run(handle_tool("writeTwoDA", {**table_args, "format": "text"})))
    binary_payload = base64.b64decode(binary["data_base64"], validate=True)
    text_payload = base64.b64decode(text["data_base64"], validate=True)
    table = TwoDADocument.load(binary_payload)

    assert binary_payload.startswith(b"2DA V2.b")
    assert text_payload.startswith(b"2DA V2.0\n\n")
    assert table.cell(0, "value") == "2"
    assert b"0\talpha\t2" in text_payload

    resources = {
        "compat_table.2da": binary_payload,
        "compat_script.nss": b"void main()\n{\n}\n",
    }
    archive = _payload(
        asyncio.run(
            handle_tool(
                "writeERF",
                {
                    "archive_type": "MOD ",
                    "files": [
                        {
                            "resref": Path(filename).stem,
                            "type": Path(filename).suffix,
                            "data_b64": base64.b64encode(data).decode("ascii"),
                        }
                        for filename, data in resources.items()
                    ],
                },
            )
        )
    )
    inspection = inspect_narrative_archive(base64.b64decode(archive["data_base64"], validate=True))
    actual = {row.filename: row.data for row in inspection.resources}

    assert archive["archive_type"] == "MOD"
    assert archive["file_count"] == 2
    assert actual == resources


def test_write_lip_ssf_and_pth_use_lossless_core_documents() -> None:
    from kotormcp.tools import handle_tool
    from pykotor.resource.generics.pth import read_pth
    from src.core.scripting.data_authoring import LipDocument, SoundSetDocument

    lip = _payload(
        asyncio.run(
            handle_tool(
                "writeLIP",
                {"duration": 1.0, "keyframes": [{"time": 0.25, "shape": "AH"}, {"time": 0.75, "shape": "M"}]},
            )
        )
    )
    lip_document = LipDocument.load(base64.b64decode(lip["data"], validate=True))
    assert [(row.time, row.shape) for row in lip_document.keyframes] == [(0.25, 3), (0.75, 11)]

    ssf = _payload(
        asyncio.run(
            handle_tool(
                "writeSSF",
                {
                    "game": "k2",
                    "resref": "compat_ssf",
                    "slots": {"BATTLE_CRY_1": 42, "27": 99},
                    "unknown_slots": [{"index": 45, "strref": 314}],
                },
            )
        )
    )
    sound_set = SoundSetDocument.load(base64.b64decode(ssf["data"], validate=True))
    assert sound_set.get_slot("BATTLE_CRY_1") == 42
    assert sound_set.get_slot(27) == 99
    assert sound_set.stringrefs[45] == 314
    assert ssf["entry_count"] == 46

    pth = _payload(
        asyncio.run(
            handle_tool(
                "writePTH",
                {
                    "game": "k1",
                    "resref": "compat_pth",
                    "points": [
                        {"x": 0.0, "y": 0.0, "connections": [1]},
                        {"x": 1.0, "y": 0.0, "connections": [0]},
                    ],
                },
            )
        )
    )
    path_graph = read_pth(base64.b64decode(pth["data"], validate=True))
    assert len(path_graph) == 2
    assert [(edge.source, edge.target) for edge in path_graph._connections] == [(0, 1), (1, 0)]


def test_write_override_requires_explicit_gate_and_creates_backup_receipt(tmp_path: Path) -> None:
    from kotormcp.tools import handle_tool

    workspace = tmp_path / "workspace"
    game_root = tmp_path / "game"
    workspace.mkdir()
    game_root.mkdir()
    (game_root / "swkotor2.exe").write_bytes(b"fixture executable")
    (game_root / "chitin.key").write_bytes(b"fixture key")
    base_args = {
        "game": "k2",
        "resref": "compat_script",
        "restype": "nss",
        "data_b64": base64.b64encode(b"void main() {}\n").decode("ascii"),
    }
    rejected = _payload(asyncio.run(handle_tool("writeOverride", base_args)))
    assert "confirm_install" in rejected["error"]
    relative = _payload(
        asyncio.run(
            handle_tool(
                "writeOverride",
                {
                    **base_args,
                    "workspace_root": "relative-workspace",
                    "game_root": str(game_root),
                    "confirm_install": True,
                },
            )
        )
    )
    assert "absolute path" in relative["error"]
    guarded = {
        **base_args,
        "workspace_root": str(workspace),
        "game_root": str(game_root),
        "confirm_install": True,
        "on_conflict": "block",
    }
    installed = _payload(asyncio.run(handle_tool("writeOverride", guarded)))

    assert installed["written"] is True
    assert Path(installed["path"]).read_bytes() == b"void main() {}\n"
    assert Path(installed["stage_manifest"]).is_file()
    assert Path(installed["receipt_path"]).is_file()

    changed = {**guarded, "data_b64": base64.b64encode(b"void main() { int x = 1; }\n").decode("ascii")}
    conflict = _payload(asyncio.run(handle_tool("writeOverride", changed)))
    assert "choose the explicit backup policy" in conflict["error"]
    changed["on_conflict"] = "backup"
    replaced = _payload(asyncio.run(handle_tool("writeOverride", changed)))
    backup = Path(replaced["backup_path"]) / "Override" / "compat_script.nss"

    assert Path(replaced["path"]).read_bytes() == b"void main() { int x = 1; }\n"
    assert backup.read_bytes() == b"void main() {}\n"
    assert Path(replaced["receipt_path"]).is_file()


def test_direct_alias_dispatch_and_specialized_arguments(monkeypatch) -> None:
    from kotormcp import tools

    calls: list[dict] = []

    async def fake_read(arguments: dict) -> dict:
        calls.append(dict(arguments))
        return {"type": "text", "text": json.dumps(arguments)}

    monkeypatch.setattr(tools.gffdata, "handle_read_gff", fake_read)

    dlg = _payload(asyncio.run(tools.handle_tool("readDLG", {"game": "k2", "resref": "test"})))
    journal = _payload(asyncio.run(tools.handle_tool("readJournal", {"game": "k1"})))

    assert dlg == {"game": "k2", "resref": "test", "restype": "dlg"}
    assert journal == {"game": "k1", "resref": "global", "restype": "jrl"}
    assert calls == [dlg, journal]


def test_nwscript_reference_aliases_use_ghoststudio_compiler_definitions() -> None:
    from kotormcp.tools import handle_tool

    signature = _payload(
        asyncio.run(handle_tool("nwscriptSignature", {"game": "k2", "name": "GetFirstPC"}))
    )
    categories = _payload(asyncio.run(handle_tool("nwscriptCategories", {"game": "k1"})))
    search = _payload(
        asyncio.run(handle_tool("searchNWScript", {"game": "k2", "query": "GetFirstPC", "limit": 5}))
    )

    assert signature["found"] is True
    assert signature["function"]["name"] == "GetFirstPC"
    assert signature["function"]["signature"]
    assert categories["count"] == len(categories["categories"]) > 0
    assert any(row["name"] == "GetFirstPC" for row in search["functions"])


def test_compile_and_decompile_aliases_return_readback_evidence() -> None:
    from kotormcp.tools import handle_tool

    compiled = _payload(
        asyncio.run(
            handle_tool(
                "compileScript",
                {"game": "k1", "resref": "compat_test", "source": "void main()\n{\n}\n"},
            )
        )
    )

    assert compiled["ok"] is True
    assert compiled["readback_ok"] is True
    assert compiled["byte_count"] > 0
    assert len(compiled["sha256"]) == 64
    assert base64.b64decode(compiled["ncs_base64"], validate=True).startswith(b"NCS V1.0")

    decompiled = _payload(
        asyncio.run(
            handle_tool(
                "decompileScript",
                {
                    "game": "k1",
                    "resref": "compat_test",
                    "ncs_base64": compiled["ncs_base64"],
                },
            )
        )
    )

    assert decompiled["resref"] == "compat_test"
    assert decompiled["disassembly"]
    assert len(decompiled["ncs_sha256"]) == 64
    assert isinstance(decompiled["exact_recompile"], bool)


def test_ssf_and_lip_read_aliases_use_lossless_core_documents() -> None:
    from kotormcp.tools import handle_tool
    from src.core.scripting.data_authoring import LipDocument, SoundSetDocument

    sound_set = SoundSetDocument([-1] * 49)
    sound_set.set_slot("BATTLE_CRY_1", 42)
    sound_set.set_unknown_entry(33, 314)
    ssf = _payload(
        asyncio.run(
            handle_tool(
                "readSSF",
                {
                    "game": "k2",
                    "resref": "compat_ssf",
                    "ssf_base64": base64.b64encode(sound_set.to_bytes()).decode("ascii"),
                },
            )
        )
    )

    lip_document = LipDocument(1.0)
    lip_document.add_keyframe(0.25, "AH")
    lip = _payload(
        asyncio.run(
            handle_tool(
                "readLIP",
                {
                    "game": "k1",
                    "resref": "compat_lip",
                    "lip_base64": base64.b64encode(lip_document.to_bytes()).decode("ascii"),
                },
            )
        )
    )

    assert ssf["slot_count"] == 49
    assert ssf["named_slot_count"] == 28
    assert ssf["unnamed_slot_count"] == 21
    assert next(row for row in ssf["slots"] if row["name"] == "BATTLE_CRY_1")["strref"] == 42
    assert next(row for row in ssf["slots"] if row["index"] == 33) == {
        "index": 33,
        "name": None,
        "named": False,
        "strref": 314,
    }
    assert lip["duration"] == 1.0
    assert lip["keyframe_count"] == 1
    assert lip["keyframes"][0]["shape_name"] == "AH"


def test_ltr_vis_wav_and_txi_readers_return_bounded_structured_metadata() -> None:
    from kotormcp.tools import handle_tool
    from pykotor.resource.formats.ltr import LTR, bytes_ltr
    from pykotor.resource.formats.vis import VIS, bytes_vis
    from pykotor.resource.formats.wav import WAV, bytes_wav

    ltr_document = LTR()
    ltr_document.set_doubles_middle("a", "z", 0.625)
    ltr = _payload(
        asyncio.run(
            handle_tool(
                "readLTR",
                {
                    "game": "k1",
                    "resref": "compat_names",
                    "context": "a",
                    "ltr_base64": base64.b64encode(bytes_ltr(ltr_document)).decode("ascii"),
                },
            )
        )
    )

    vis_document = VIS()
    vis_document.add_room("room_a")
    vis_document.add_room("room_b")
    vis_document.set_visible("room_a", "room_b", True)
    vis = _payload(
        asyncio.run(
            handle_tool(
                "readVIS",
                {
                    "game": "k2",
                    "resref": "compat_layout",
                    "vis_base64": base64.b64encode(bytes_vis(vis_document)).decode("ascii"),
                },
            )
        )
    )

    wav_document = WAV(
        channels=1,
        sample_rate=8_000,
        bits_per_sample=16,
        bytes_per_sec=16_000,
        data=b"\0" * 16_000,
    )
    wav = _payload(
        asyncio.run(
            handle_tool(
                "readWAV",
                {
                    "game": "k1",
                    "resref": "compat_audio",
                    "wav_base64": base64.b64encode(bytes_wav(wav_document)).decode("ascii"),
                },
            )
        )
    )

    txi_source = b"blending additive\nproceduretype cycle\nnumx 2\nnumy 4\nfps 12\n"
    txi = _payload(
        asyncio.run(
            handle_tool(
                "readTXI",
                {
                    "game": "k2",
                    "resref": "compat_texture",
                    "txi_base64": base64.b64encode(txi_source).decode("ascii"),
                },
            )
        )
    )

    assert ltr["table"] == "doubles"
    assert ltr["context"] == "a"
    assert next(row for row in ltr["probabilities"] if row["character"] == "z")["middle"] == 0.625
    assert vis["rooms"] == ["room_a", "room_b"]
    assert vis["visibility"]["room_a"] == ["room_b"]
    assert vis["directed_edge_count"] == 1
    assert wav["encoding"] == "PCM"
    assert wav["sample_rate"] == 8_000
    assert wav["duration_seconds"] == 1.0
    assert "decoded_audio" not in wav
    assert txi["directives"]["blending"] == 1
    assert txi["directives"]["proceduretype"] == "cycle"
    assert txi["directive_count"] == 5


def test_read_save_returns_decoded_summary_and_bounded_archive_inventory(tmp_path: Path, monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.resource.formats.erf import ERF, bytes_erf
    from pykotor.resource.type import ResourceType

    archive = ERF(is_save=True)
    archive.set_data("207tel", ResourceType.SAV, b"module payload")
    (tmp_path / "SAVEGAME.sav").write_bytes(bytes_erf(archive))
    (tmp_path / "screen.tga").write_bytes(b"preview")

    class _Installation:
        @staticmethod
        def game_name() -> str:
            return "K2"

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    result = _payload(
        asyncio.run(
            handle_tool(
                "readSave",
                {"game": "k2", "save_folder": str(tmp_path), "resource_limit": 1},
            )
        )
    )

    assert result["game"] == "K2"
    assert result["summary"]["folder"] == str(tmp_path.resolve())
    assert result["resource_count"] == 1
    assert result["resources"] == [{"resref": "207tel", "restype": "sav"}]
    assert len(result["savegame_sha256"]) == 64
    assert {row["name"] for row in result["files"]} == {"SAVEGAME.sav", "screen.tga"}


def test_script_and_blueprint_composites_preserve_typed_evidence(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff
    from src.core.scripting.studio import ScriptDocument, ScriptingStudioService

    compiled = ScriptingStudioService().compile_script(
        ScriptDocument(resref="compat_script", game="K1", source="void main()\n{\n}\n")
    )
    assert compiled.ok

    utc = GFF(GFFContent.UTC)
    utc.root.set_resref("TemplateResRef", ResRef("compat_creature"))
    utc.root.set_string("Tag", "compat_creature")
    utc.root.set_resref("ScriptSpawn", ResRef("compat_spawn"))
    utc.root.set_resref("Conversation", ResRef("compat_dialogue"))
    utc.root.set_locstring("FirstName", LocalizedString.from_english("Compatibility Creature"))
    utc_bytes = bytes_gff(utc)

    class _Installation:
        @staticmethod
        def talktable_string(stringref: int) -> str:
            return f"TLK {stringref}"

        @staticmethod
        def get_resource(resref: str, restype: str):
            if resref == "compat_script" and restype == "nss":
                return SimpleNamespace(data=b"void main()\n{\n}\n", source="fixture:nss")
            if resref == "compat_script" and restype == "ncs":
                return SimpleNamespace(data=compiled.ncs_bytes, source="fixture:ncs")
            if resref == "compat_creature" and restype == "utc":
                return SimpleNamespace(data=utc_bytes, source="fixture:utc")
            return None

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    script = _payload(asyncio.run(handle_tool("getScript", {"game": "k1", "resref": "compat_script"})))
    creature = _payload(asyncio.run(handle_tool("getCreature", {"game": "k1", "resref": "compat_creature"})))

    assert script["nss_found"] is True
    assert script["ncs_found"] is True
    assert script["ncs"]["instruction_count"] > 0
    assert len(script["ncs"]["sha256"]) == 64
    assert creature["restype"] == "utc"
    assert creature["embedded_resource_type"] == "utc"
    assert creature["identity"]["Tag"] == "compat_creature"
    assert creature["script_references"] == [
        {"path": "$/ScriptSpawn", "label": "ScriptSpawn", "resref": "compat_spawn"}
    ]
    assert creature["conversation_references"] == [
        {"path": "$/Conversation", "label": "Conversation", "resref": "compat_dialogue"}
    ]
    assert creature["localized_fields"][0]["localized_data"]["substrings"]["0"] == "Compatibility Creature"


def test_blueprint_auto_detection_refuses_ambiguous_resrefs(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff

    utc = bytes_gff(GFF(GFFContent.UTC))
    utp = bytes_gff(GFF(GFFContent.UTP))

    class _Installation:
        @staticmethod
        def get_resource(resref: str, restype: str):
            if resref != "duplicate":
                return None
            if restype == "utc":
                return SimpleNamespace(data=utc, source="fixture:utc")
            if restype == "utp":
                return SimpleNamespace(data=utp, source="fixture:utp")
            return None

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    result = _payload(asyncio.run(handle_tool("getBlueprint", {"game": "k2", "resref": "duplicate"})))

    assert result["ambiguous"] is True
    assert [row["restype"] for row in result["candidates"]] == ["utc", "utp"]
    assert "specify restype" in result["error"].casefold()


def test_named_blueprint_composites_preserve_legacy_object_semantics(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, bytes_gff

    door = GFF(GFFContent.UTD)
    door.root.set_string("Tag", "compat_door")
    door.root.set_uint8("Locked", 1)
    door.root.set_uint8("TrapDetectable", 1)
    door.root.set_uint8("TrapDisarmable", 1)
    door.root.set_uint8("TrapType", 3)
    door.root.set_resref("OnOpen", ResRef("door_open"))
    door.root.set_resref("Conversation", ResRef("door_dialog"))

    placeable = GFF(GFFContent.UTP)
    placeable.root.set_string("Tag", "compat_place")
    placeable.root.set_uint8("Useable", 1)
    placeable.root.set_resref("OnUsed", ResRef("place_used"))
    place_items = GFFList()
    place_item = place_items.add(0)
    place_item.set_resref("InventoryRes", ResRef("compat_item"))
    placeable.root.set_list("ItemList", place_items)

    item = GFF(GFFContent.UTI)
    item.root.set_string("Tag", "compat_item")
    item.root.set_locstring("LocalizedName", LocalizedString.from_english("Compatibility Item"))
    item.root.set_uint16("BaseItem", 12)
    item.root.set_uint32("Cost", 150)
    properties = GFFList()
    prop = properties.add(0)
    prop.set_uint16("PropertyName", 6)
    prop.set_uint16("Subtype", 2)
    item.root.set_list("PropertiesList", properties)

    encounter = GFF(GFFContent.UTE)
    encounter.root.set_string("Tag", "compat_enc")
    encounter.root.set_uint8("Active", 1)
    encounter.root.set_resref("OnSpawn", ResRef("enc_spawn"))
    creatures = GFFList()
    creature = creatures.add(0)
    creature.set_resref("ResRef", ResRef("compat_creature"))
    creature.set_single("CR", 4.5)
    creature.set_uint8("SingleSpawn", 1)
    encounter.root.set_list("CreatureList", creatures)

    trigger = GFF(GFFContent.UTT)
    trigger.root.set_string("Tag", "compat_trigger")
    trigger.root.set_uint8("TrapType", 4)
    trigger.root.set_string("LinkedTo", "compat_destination")
    trigger.root.set_resref("ScriptOnEnter", ResRef("trigger_enter"))

    waypoint = GFF(GFFContent.UTW)
    waypoint.root.set_string("Tag", "compat_waypoint")
    waypoint.root.set_locstring("LocalizedName", LocalizedString.from_english("Compatibility Waypoint"))
    waypoint.root.set_single("XPosition", 1.25)
    waypoint.root.set_single("YPosition", 2.5)
    waypoint.root.set_locstring("MapNote", LocalizedString.from_english("Meet here"))
    waypoint.root.set_uint8("HasMapNote", 1)

    store = GFF(GFFContent.UTM)
    store.root.set_string("Tag", "compat_store")
    store.root.set_uint32("MarkUp", 125)
    store_items = GFFList()
    store_item = store_items.add(0)
    store_item.set_resref("InventoryRes", ResRef("compat_item"))
    store_item.set_uint8("Infinite", 1)
    store.root.set_list("ItemList", store_items)

    sound = GFF(GFFContent.UTS)
    sound.root.set_string("Tag", "compat_sound")
    sound.root.set_uint8("Active", 1)
    sound.root.set_uint8("Looping", 1)
    sounds = GFFList()
    sound_row = sounds.add(0)
    sound_row.set_resref("Sound", ResRef("compat_audio"))
    sound.root.set_list("Sounds", sounds)

    resources = {
        ("compat_door", "utd"): bytes_gff(door),
        ("compat_place", "utp"): bytes_gff(placeable),
        ("compat_item", "uti"): bytes_gff(item),
        ("compat_enc", "ute"): bytes_gff(encounter),
        ("compat_trigger", "utt"): bytes_gff(trigger),
        ("compat_waypoint", "utw"): bytes_gff(waypoint),
        ("compat_store", "utm"): bytes_gff(store),
        ("compat_sound", "uts"): bytes_gff(sound),
    }

    class _Installation:
        @staticmethod
        def talktable_string(_stringref: int) -> str:
            return ""

        @staticmethod
        def get_resource(resref: str, restype: str):
            data = resources.get((resref, restype))
            return SimpleNamespace(data=data, source=f"fixture:{restype}") if data is not None else None

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    calls = {
        name: _payload(asyncio.run(handle_tool(name, {"game": "k2", "resref": resref})) )
        for name, resref in {
            "getDoor": "compat_door",
            "getPlaceable": "compat_place",
            "getItem": "compat_item",
            "getEncounter": "compat_enc",
            "getTrigger": "compat_trigger",
            "getWaypoint": "compat_waypoint",
            "getStore": "compat_store",
            "getSound": "compat_sound",
        }.items()
    }

    assert calls["getDoor"]["lock"]["locked"] == 1
    assert calls["getDoor"]["trap"]["trap_type"] == 3
    assert calls["getDoor"]["scripts"] == {"OnOpen": "door_open"}
    assert calls["getDoor"]["conversation"] == "door_dialog"
    assert calls["getPlaceable"]["inventory"] == ["compat_item"]
    assert calls["getPlaceable"]["scripts"] == {"OnUsed": "place_used"}
    assert calls["getItem"]["name"] == "Compatibility Item"
    assert calls["getItem"]["properties"] == [{"PropertyName": 6, "Subtype": 2}]
    assert calls["getEncounter"]["spawn_list"] == [
        {"resref": "compat_creature", "cr": 4.5, "single_spawn": True}
    ]
    assert calls["getTrigger"]["linked_to"] == "compat_destination"
    assert calls["getTrigger"]["scripts"] == {"ScriptOnEnter": "trigger_enter"}
    assert calls["getWaypoint"]["name"] == "Compatibility Waypoint"
    assert calls["getWaypoint"]["map_note"] == "Meet here"
    assert calls["getStore"]["inventory"] == [{"resref": "compat_item", "infinite": True}]
    assert calls["getSound"]["sounds"] == ["compat_audio"]
    assert all("legacy_fields" in result and "fields" in result for result in calls.values())


def test_pathfind_route_uses_explicit_wok_and_pie_runtime_math() -> None:
    from kotormcp.tools import handle_tool
    from pykotor.resource.formats.bwm import BWM, BWMFace, bytes_bwm
    from pykotor.resource.formats.bwm.bwm_data import SurfaceMaterial
    from utility.common.geometry import Vector3

    walkmesh = BWM()
    first = BWMFace(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 1, 0))
    second = BWMFace(Vector3(1, 0, 0), Vector3(1, 1, 0), Vector3(0, 1, 0))
    first.material = SurfaceMaterial.DIRT
    second.material = SurfaceMaterial.DIRT
    walkmesh.faces = [first, second]

    result = _payload(
        asyncio.run(
            handle_tool(
                "pathfindRoute",
                {
                    "game": "k2",
                    "resref": "compat_room",
                    "mode": "wok_pie",
                    "start": [0.1, 0.1, 0.0],
                    "destination": [0.9, 0.9, 0.0],
                    "wok_base64": base64.b64encode(bytes_bwm(walkmesh)).decode("ascii"),
                },
            )
        )
    )

    assert result["connected"] is True
    assert result["start_sample"]["face_index"] == 0
    assert result["destination_sample"]["face_index"] == 1
    assert result["route"] == [[0.5, 0.5, 0.0], [0.9, 0.9, 0.0]]
    assert "retail KOTOR" in result["proof_scope"]


def _compatibility_pth_base64() -> str:
    from pykotor.common.misc import Game
    from pykotor.resource.generics.pth import PTH, bytes_pth

    graph = PTH()
    graph.add(0.0, 0.0)
    graph.add(3.0, 0.0)
    graph.add(3.0, 4.0)
    graph.add(30.0, 30.0)
    graph.connect(0, 1)
    graph.connect(1, 2)
    graph.connect(0, 3)
    graph.connect(3, 2)
    return base64.b64encode(bytes_pth(graph, Game.K2)).decode("ascii")


def test_pathfind_route_preserves_legacy_pth_node_index_contract() -> None:
    from kotormcp.tools import handle_tool

    result = _payload(
        asyncio.run(
            handle_tool(
                "pathfindRoute",
                {
                    "game": "k2",
                    "resref": "compat_area",
                    "start_index": 0,
                    "end_index": 2,
                    "pth_base64": _compatibility_pth_base64(),
                },
            )
        )
    )

    assert result == {
        "game": "K2",
        "resref": "compat_area",
        "start_index": 0,
        "end_index": 2,
        "path": [0, 1, 2],
        "step_count": 3,
        "total_distance": 7.0,
        "waypoints": [
            {"x": 0.0, "y": 0.0},
            {"x": 3.0, "y": 0.0},
            {"x": 3.0, "y": 4.0},
        ],
    }


def test_pathfind_route_preserves_legacy_xy_snapping_contract() -> None:
    from kotormcp.tools import handle_tool

    result = _payload(
        asyncio.run(
            handle_tool(
                "pathfindRoute",
                {
                    "game": "K2",
                    "resref": "compat_area",
                    "start_x": 0.25,
                    "start_y": 0.0,
                    "end_x": 3.0,
                    "end_y": 4.5,
                    "pth_base64": _compatibility_pth_base64(),
                },
            )
        )
    )

    assert result["path"] == [0, 1, 2]
    assert result["waypoints"] == [
        {"x": 0.0, "y": 0.0},
        {"x": 3.0, "y": 0.0},
        {"x": 3.0, "y": 4.0},
    ]
    assert result["start_nearest"] == {
        "snapped_to": 0,
        "snap_distance": 0.25,
        "from_x": 0.25,
        "from_y": 0.0,
    }
    assert result["end_nearest"] == {
        "snapped_to": 2,
        "snap_distance": 0.5,
        "from_x": 3.0,
        "from_y": 4.5,
    }


def test_area_and_faction_composites_return_paired_counts(monkeypatch) -> None:
    from kotormcp.tools import handle_tool
    from kotormcp.tools import legacy_ghostscripter
    from pykotor.common.language import LocalizedString
    from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, bytes_gff

    area = GFF(GFFContent.ARE)
    area.root.set_string("Tag", "compat_area")
    area.root.set_locstring("Name", LocalizedString.from_english("Compatibility Area"))
    git = GFF(GFFContent.GIT)
    creatures = GFFList()
    creatures.add(4)
    creatures.add(4)
    doors = GFFList()
    doors.add(8)
    git.root.set_list("Creature List", creatures)
    git.root.set_list("Door List", doors)
    faction = GFF(GFFContent.FAC)
    factions = GFFList()
    factions.add(1)
    factions.add(1)
    factions.add(1)
    faction.root.set_list("FactionList", factions)
    payloads = {
        ("compat_area", "are"): bytes_gff(area),
        ("compat_area", "git"): bytes_gff(git),
        ("repute", "fac"): bytes_gff(faction),
    }

    class _Installation:
        @staticmethod
        def talktable_string(stringref: int) -> str:
            return f"TLK {stringref}"

        @staticmethod
        def get_resource(resref: str, restype: str):
            data = payloads.get((resref, restype))
            return SimpleNamespace(data=data, source=f"fixture:{restype}") if data is not None else None

    monkeypatch.setattr(legacy_ghostscripter, "load_installation", lambda _game: _Installation())
    area_result = _payload(asyncio.run(handle_tool("getArea", {"game": "k2", "resref": "compat_area"})))
    faction_result = _payload(asyncio.run(handle_tool("getFaction", {"game": "k2", "resref": "repute"})))

    assert area_result["tag"] == "compat_area"
    assert area_result["area_name"] == "Compatibility Area"
    assert area_result["localized_name"]["localized_data"]["substrings"]["0"] == "Compatibility Area"
    assert area_result["instance_list_counts"] == {"Creature List": 2, "Door List": 1}
    assert len(area_result["creatures"]) == 2
    assert len(area_result["doors"]) == 1
    assert faction_result["relation_list_counts"] == {"FactionList": 3}
    assert faction_result["count"] == 3
    assert [row["name"] for row in faction_result["factions"]] == ["faction_0", "faction_1", "faction_2"]


def test_two_da_changes_ini_alias_is_bounded_and_refuses_deletes() -> None:
    from kotormcp.tools import handle_tool
    from src.core.scripting.data_authoring import TwoDADocument

    original = TwoDADocument(["label", "value"], ["0"], [["alpha", "1"]])
    modified = TwoDADocument(["label", "value"], ["0", "1"], [["alpha", "2"], ["beta", "3"]])
    response = _payload(
        asyncio.run(
            handle_tool(
                "twoDAChangesINI",
                {
                    "table_name": "compat.2da",
                    "original_2da_base64": base64.b64encode(original.to_bytes()).decode("ascii"),
                    "modified_2da_base64": base64.b64encode(modified.to_bytes()).decode("ascii"),
                },
            )
        )
    )

    assert "[2DAList]" in response["changes_ini"]
    assert "AddRow0" in response["changes_ini"]
    assert "ChangeRow0" in response["changes_ini"]
    assert len(response["sha256"]) == 64


def test_compatibility_report_tool_can_filter_machine_readable_rows() -> None:
    from kotormcp.tools import handle_tool

    filtered = _payload(
        asyncio.run(
            handle_tool(
                "ghostrigger_ghostscripter_compatibility",
                {"status": "callable_alias", "category": "write_formats"},
            )
        )
    )

    assert filtered["inventory_count"] == 60
    assert filtered["filtered_count"] == 8
    assert Counter(row["status"] for row in filtered["tools"]) == {"callable_alias": 8}
    assert all(row["category"] == "write_formats" for row in filtered["tools"])
