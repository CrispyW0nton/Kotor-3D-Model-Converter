from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_grdev01_renamed_stock_area_clone.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("prepare_grdev01_renamed_stock_area_clone_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_t2601_dual_root_diagnostic_manifest_records_stock_root_resources() -> None:
    module = _load_script_module()
    summary = {
        "ok": True,
        "code": "prepared",
        "root_resource_mode": "dual_grdev01_and_m02aa_roots",
        "room_resref_mode": "stock_m02aa_rooms",
    }
    manifest = module._manifest(
        summary,
        ["m02aa_01a"],
        {"resource_count": 62},
        rename_room_resrefs=False,
        include_stock_roots=True,
        unique_module_id=True,
        minimal_git=False,
        minimal_git_test_placeable=False,
        scriptless_root=False,
    )

    assert manifest["root_resource_mode"] == "dual_grdev01_and_m02aa_roots"
    assert manifest["room_resref_mode"] == "stock_m02aa_rooms"
    assert manifest["module_id_mode"] == "unique_grdev01_uuid"
    assert manifest["git_mode"] == "stock_runtime_objects"
    assert manifest["diagnostic_module_id_hex"]
    assert manifest["summary"]["root_resource_mode"] == "dual_grdev01_and_m02aa_roots"
    assert "both grdev01 and stock m02aa root resources" in manifest["diagnostic_question"]


def test_t2601_unique_module_id_rewrites_stock_ifo_identity() -> None:
    module = _load_script_module()
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent

    stock_id = b"\x9d\xef\xf8\x9f\x07sq\x1c\x86\xecI\xf8\xd1\\\x1f\x9f"
    gff = GFF(GFFContent.IFO)
    gff.root.set_binary("Mod_ID", stock_id)
    gff.root.set_resref("Mod_Entry_Area", "m02aa")
    gff.root.set_string("Mod_VO_ID", "m02aa")

    rewritten = read_gff(module._rename_stock_ifo(bytes_gff(gff), unique_module_id=True)).root

    assert rewritten.get("Mod_ID") == module.DIAGNOSTIC_MODULE_ID
    assert rewritten.get("Mod_ID") != stock_id
    assert str(rewritten.get("Mod_Entry_Area")) == "grdev01"
    assert rewritten.get("Mod_VO_ID") == "grdev01"
    assert rewritten.get("Mod_Tag") == "grdev01"


def test_t2601_scriptless_root_clears_stock_module_and_area_scripts() -> None:
    module = _load_script_module()
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent

    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_Entry_Area", "m02aa")
    ifo.root.set_string("Mod_VO_ID", "m02aa")
    ifo.root.set_resref("Mod_OnModLoad", "k_ptar_load")
    ifo.root.set_resref("Mod_OnPlrDeath", "nw_o0_death")
    are = GFF(GFFContent.ARE)
    are.root.set_string("Tag", "Untitled")
    are.root.set_resref("OnEnter", "k_ptar_02aa_en")
    are.root.set_resref("OnHeartbeat", "k_ptar_hb")

    rewritten_ifo = read_gff(module._rename_stock_ifo(bytes_gff(ifo), scriptless_root=True)).root
    rewritten_are = read_gff(module._rename_stock_are(bytes_gff(are), scriptless_root=True)).root

    assert str(rewritten_ifo.get("Mod_Entry_Area")) == "grdev01"
    assert rewritten_ifo.get("Mod_VO_ID") == "grdev01"
    assert rewritten_ifo.get("Mod_Tag") == "grdev01"
    assert str(rewritten_ifo.get("Mod_OnModLoad")) == ""
    assert str(rewritten_ifo.get("Mod_OnPlrDeath")) == ""
    assert rewritten_are.get("Tag") == "grdev01"
    assert str(rewritten_are.get("OnEnter")) == ""
    assert str(rewritten_are.get("OnHeartbeat")) == ""


def test_t2601_minimal_git_strips_runtime_object_lists() -> None:
    module = _load_script_module()
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent, GFFList, GFFStruct

    gff = GFF(GFFContent.GIT)
    root = gff.root
    root.set_uint8("UseTemplates", 1)
    root.set_struct("AreaProperties", GFFStruct(100))
    for field in module._RUNTIME_GIT_LIST_FIELDS:
        values = GFFList()
        values.add(1)
        root.set_list(field, values)

    rewritten = read_gff(module._minimal_stock_git(bytes_gff(gff))).root

    assert rewritten.get("UseTemplates") == 1
    assert rewritten.get("AreaProperties").struct_id == 100
    for field in module._RUNTIME_GIT_LIST_FIELDS:
        assert len(rewritten.get(field)) == 0


def test_t2601_minimal_git_can_add_single_test_placeable() -> None:
    module = _load_script_module()
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent

    gff = GFF(GFFContent.GIT)
    rewritten = read_gff(module._minimal_stock_git(bytes_gff(gff), add_test_placeable=True)).root
    placeables = rewritten.get("Placeable List")

    assert len(placeables) == 1
    item = placeables.at(0)
    assert item.struct_id == 9
    assert str(item.get("TemplateResRef")) == module.TEST_PLACEABLE_TEMPLATE
    assert item.get("Tag") == module.TEST_PLACEABLE_TAG
    assert item.get("X") == module.TEST_PLACEABLE_POSITION[0]
    assert item.get("Y") == module.TEST_PLACEABLE_POSITION[1]
    assert item.get("Z") == module.TEST_PLACEABLE_POSITION[2]
    assert item.get("Bearing") == 0.0


def test_t2601_minimal_git_manifest_records_runtime_object_strip() -> None:
    module = _load_script_module()
    summary = {
        "ok": True,
        "code": "prepared",
        "root_resource_mode": "grdev01_roots_only",
        "room_resref_mode": "stock_m02aa_rooms",
        "git_mode": "minimal_no_runtime_objects",
    }
    manifest = module._manifest(
        summary,
        ["m02aa_01a"],
        {"resource_count": 57},
        rename_room_resrefs=False,
        include_stock_roots=False,
        unique_module_id=True,
        minimal_git=True,
        minimal_git_test_placeable=False,
        scriptless_root=False,
    )

    assert manifest["git_mode"] == "minimal_no_runtime_objects"
    assert manifest["summary"]["git_mode"] == "minimal_no_runtime_objects"
    assert "dynamic GIT objects are stripped" in manifest["diagnostic_question"]


def test_t2601_minimal_git_test_placeable_manifest_records_single_placeable() -> None:
    module = _load_script_module()
    summary = {
        "ok": True,
        "code": "prepared",
        "root_resource_mode": "grdev01_roots_only",
        "room_resref_mode": "stock_m02aa_rooms",
        "git_mode": "minimal_with_test_placeable",
    }
    manifest = module._manifest(
        summary,
        ["m02aa_01a"],
        {"resource_count": 57},
        rename_room_resrefs=False,
        include_stock_roots=False,
        unique_module_id=True,
        minimal_git=True,
        minimal_git_test_placeable=True,
        scriptless_root=False,
    )

    assert manifest["git_mode"] == "minimal_with_test_placeable"
    assert manifest["test_placeable"]["template"] == module.TEST_PLACEABLE_TEMPLATE
    assert manifest["test_placeable"]["tag"] == module.TEST_PLACEABLE_TAG
    assert "test bench is visible" in manifest["diagnostic_question"]


def test_t2601_scriptless_manifest_records_root_script_mode() -> None:
    module = _load_script_module()
    summary = {
        "ok": True,
        "code": "prepared",
        "root_resource_mode": "grdev01_roots_only",
        "room_resref_mode": "stock_m02aa_rooms",
        "git_mode": "minimal_no_runtime_objects",
        "root_script_mode": "scriptless",
    }
    manifest = module._manifest(
        summary,
        ["m02aa_01a"],
        {"resource_count": 57},
        rename_room_resrefs=False,
        include_stock_roots=False,
        unique_module_id=True,
        minimal_git=True,
        minimal_git_test_placeable=False,
        scriptless_root=True,
    )

    assert manifest["root_script_mode"] == "scriptless"
    assert manifest["summary"]["root_script_mode"] == "scriptless"
