from __future__ import annotations

import copy
from dataclasses import replace
import json

from src.core.characters.character_builder import apply_template_rig
from src.core.characters.character_export_transaction import (
    CharacterBuilderExportTransactionRequest,
    export_character_mdl_mdx_transaction,
)
from src.core.characters.character_export_preflight import (
    CharacterExportPreflightOptions,
    preflight_character_mdl_export,
)
from src.core.characters.character_rig_state import (
    RIG_DAG_AUTHORITY_NATIVE_KOTOR,
    RIG_STATE_NATIVE_TEMPLATE_FINAL,
    get_character_rig_state,
    mark_imported_temporary_skeleton,
)
from src.core.characters.character_validation_report import (
    CHARACTER_BUILDER_MANUAL_CHECKLIST,
    CharacterBuilderValidationReport,
)
from src.core.characters.native_skeleton import native_skeleton_fingerprint
from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
from src.core.validation.validation_bus import (
    ValidationIssue,
    ValidationNavigationTarget,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


def _node(
    name: str,
    *,
    flags: int = int(NodeFlags.HEADER),
    parent: ModelNode | None = None,
) -> ModelNode:
    node = ModelNode(name=name, flags=flags)
    if parent is not None:
        node.parent = parent
        parent.children.append(node)
    return node


def _mesh_model() -> KotorModel:
    root = _node("import_root")
    mesh = _node("custom_body", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=root)
    mesh.vertices = [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.2, 0.0)]
    mesh.normals = [(0.0, 0.0, 1.0)] * 3
    mesh.faces = [(0, 1, 2)]
    return KotorModel(name="grbody", root_node=root)


def _native_template(*, include_lhand: bool = True, game: str = "K1") -> KotorModel:
    root = _node("PMBAM")
    cutscene = _node("cutscenedummy", parent=root)
    rootdummy = _node("rootdummy", parent=cutscene)
    pelvis = _node("pelvis_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=rootdummy)
    pelvis.vertices = [(0.0, 0.0, 0.0)]
    pelvis.faces = [(0, 0, 0)]
    torso = _node("torso_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=rootdummy)
    torso.vertices = [(0.0, 0.0, 0.5)]
    torso.faces = [(0, 0, 0)]
    torso_upr = _node("torsoUpr_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=torso)
    torso_upr.vertices = [(0.0, 0.0, 0.8)]
    torso_upr.faces = [(0, 0, 0)]
    _node("headhook", parent=torso_upr)
    r_hand_g = _node("Rhand_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=torso_upr)
    r_hand_g.vertices = [(0.2, 0.0, 0.5)]
    r_hand_g.faces = [(0, 0, 0)]
    _node("rhand", parent=r_hand_g)
    if include_lhand:
        l_hand_g = _node("Lhand_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=torso_upr)
        l_hand_g.vertices = [(-0.2, 0.0, 0.5)]
        l_hand_g.faces = [(0, 0, 0)]
        _node("lhand", parent=l_hand_g)
    _node("LightsaberHook", parent=root)
    _node("DeflectHook", parent=root)
    _node("Impact", parent=torso_upr)
    _node("camerahook", parent=root)
    _node("FreeLookHook", parent=root)
    render_skin = _node("Torso", flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN), parent=root)
    render_skin.vertices = [(0.0, 0.0, 0.0)]
    render_skin.faces = [(0, 0, 0)]
    game = str(game or "K1").upper()
    supermodel = "S_Female02" if game == "K2" else "S_KPMF0200"
    model = KotorModel(name="pmbam", root_node=root, supermodel=supermodel)
    model._gr_source_resref = "pmbam"
    model._gr_source_game = game
    model._gr_source_layer = "game_library"
    return model


def _rigged_character(template: KotorModel | None = None, *, game: str = "K1") -> dict:
    return apply_template_rig(
        _mesh_model(),
        template or _native_template(game=game),
        game=game,
        scale_mode="manual",
    )


def _codes(result) -> set[str]:
    return {issue.code for issue in result.report.issues}


def _issue_by_code(result, code: str):
    for issue in result.report.issues:
        if issue.code == code:
            return issue
    raise AssertionError(f"missing issue code {code}")


def test_apply_template_rig_preserves_selected_native_supermodel() -> None:
    result = _rigged_character()

    assert result["ok"] is True
    assert result["model"].supermodel == "S_KPMF0200"
    assert result["native_skeleton_snapshot"].supermodel == "S_KPMF0200"
    state = get_character_rig_state(result["model"])
    assert state is not None
    assert state.state == RIG_STATE_NATIVE_TEMPLATE_FINAL
    assert state.dag_authority == RIG_DAG_AUTHORITY_NATIVE_KOTOR


def test_character_export_preflight_accepts_native_snapshot_and_skin_payload() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert preflight.export_allowed is True
    assert preflight.report.has_blocking is False
    assert "character.export.non_native_skeleton_node" not in _codes(preflight)


def test_character_export_preflight_accepts_k2_native_snapshot_and_supermodel() -> None:
    result = _rigged_character(game="K2")

    assert result["ok"] is True
    assert result["model"].supermodel == "S_Female02"
    assert result["native_skeleton_snapshot"].game == "K2"
    assert result["native_skeleton_snapshot"].supermodel == "S_Female02"
    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(
            export_game="K2",
            recommended_socket_categories=(),
        ),
    )

    assert preflight.export_allowed is True
    assert preflight.report.has_blocking is False


def test_character_export_preflight_blocks_supermodel_case_change() -> None:
    result = _rigged_character()
    result["model"].supermodel = "s_kpmf0200"

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.supermodel_case_changed")
    assert issue.severity.value == "blocking"
    assert issue.details["expected"] == "S_KPMF0200"
    assert issue.details["actual"] == "s_kpmf0200"
    assert issue.details["pending_ghidra"] == "supermodel name resolution and resref case behavior"
    assert "Restore the exact supermodel casing" in issue.fix_hint
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_native_snapshot_game_mismatch() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(
            export_game="K2",
            recommended_socket_categories=(),
        ),
    )

    issue = _issue_by_code(preflight, "character.export.native_snapshot_game_mismatch")
    assert issue.details["export_game"] == "K2"
    assert issue.details["normalized_native_game_facts"]["snapshot_game"] == "K1"
    assert issue.details["normalized_native_game_facts"]["metadata_source_game"] == "K1"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_unknown_native_snapshot_game() -> None:
    result = _rigged_character()
    snapshot = result["native_skeleton_snapshot"]
    unknown_snapshot = replace(
        snapshot,
        game="unknown",
        metadata={
            **dict(snapshot.metadata or {}),
            "source_game": "",
            "game": "",
        },
    )

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=unknown_snapshot,
        options=CharacterExportPreflightOptions(
            export_game="K1",
            recommended_socket_categories=(),
        ),
    )

    issue = _issue_by_code(preflight, "character.export.native_snapshot_game_unknown")
    assert issue.details["export_game"] == "K1"
    assert issue.details["normalized_native_game_facts"]["snapshot_game"] == "UNKNOWN"
    assert issue.details["native_game_facts"]["metadata_source_game"] == ""
    assert "configured K1/K2 game library" in issue.fix_hint
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_native_snapshot() -> None:
    result = _rigged_character()
    delattr(result["model"], "_gr_native_skeleton_snapshot")

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=None,
    )

    assert "character.export.missing_native_snapshot" in _codes(preflight)


def test_character_export_preflight_blocks_imported_temporary_skeleton_state() -> None:
    result = _rigged_character()
    mark_imported_temporary_skeleton(result["model"], source="test_override")

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.not_native_template_final_rig")
    assert issue.details["expected_state"] == RIG_STATE_NATIVE_TEMPLATE_FINAL
    assert issue.details["actual_state"]["state"] == "imported_temporary_skeleton"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_bind_provenance() -> None:
    result = _rigged_character()
    result["model"].metadata.pop("character_builder_bind", None)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.missing_bind_provenance")
    assert issue.severity.value == "blocking"
    assert "character_builder_bind.status" in issue.details["missing_bind_fields"]
    assert "character_builder_bind.native_base.source_resref" in issue.details["missing_bind_fields"]
    assert "character_builder_bind.imported_payload.model_name" in issue.details["missing_bind_fields"]
    assert issue.details["missing_rig_state_fields"] == []
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_bind_provenance_mismatch() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"]["source_resref"] = "n_mandalorian03"
    bind["imported_payload"]["model_name"] = "wrong_payload"
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.bind_provenance_mismatch")
    assert issue.severity.value == "blocking"
    mismatches = issue.details["mismatches"]
    assert mismatches["native_base_resref"]["rig_state"] == "pmbam"
    assert mismatches["native_base_resref"]["bind"] == "n_mandalorian03"
    assert mismatches["imported_payload_name"]["rig_state"] == "grbody"
    assert mismatches["imported_payload_name"]["bind"] == "wrong_payload"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_render_replacement_evidence() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"]["replaced_render_payload_nodes"] = []
    bind["native_base"]["replaced_render_payload_count"] = 0
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.missing_native_render_replacement_evidence",
    )
    assert issue.severity.value == "blocking"
    missing = issue.details["missing_replacements"]
    assert missing == [
        {
            "name": "Torso",
            "path": ["PMBAM", "Torso"],
            "role": "skin_mesh",
            "vertex_count": 1,
            "face_count": 1,
            "texture": "",
        }
    ]
    assert issue.details["expected_replacement"] == "imported_mesh_payload"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_invalid_render_replacement_evidence() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"]["replaced_render_payload_nodes"] = [
        *bind["native_base"]["replaced_render_payload_nodes"],
        {
            "name": "rootdummy",
            "path": ["PMBAM", "cutscenedummy", "rootdummy"],
            "replacement": "imported_mesh_payload",
        },
    ]
    bind["native_base"]["replaced_render_payload_count"] = 2
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.invalid_native_render_replacement_evidence",
    )
    assert issue.severity.value == "blocking"
    invalid = issue.details["invalid_replacements"]
    assert invalid == [
        {
            "reason": "not_replaceable_render_payload",
            "path": ["PMBAM", "cutscenedummy", "rootdummy"],
            "role": "helper",
        }
    ]
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_stale_render_replacement_facts() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"]["replaced_render_payload_nodes"][0]["vertex_count"] = 99
    bind["native_base"]["replaced_render_payload_nodes"][0]["name"] = "WrongTorso"
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.invalid_native_render_replacement_evidence",
    )
    invalid = issue.details["invalid_replacements"]
    assert invalid == [
        {
            "reason": "native_fact_mismatch",
            "path": ["PMBAM", "Torso"],
            "mismatches": {
                "name": {"expected": "Torso", "actual": "WrongTorso"},
                "vertex_count": {"expected": 1, "actual": 99},
            },
        }
    ]
    assert "character.export.missing_native_render_replacement_evidence" in _codes(preflight)
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_replacement_record_for_present_node() -> None:
    result = _rigged_character()
    root = result["model"].root_node
    assert root is not None
    torso = _node(
        "Torso",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=root,
    )
    torso.vertices = [(0.0, 0.0, 0.0)]
    torso.faces = [(0, 0, 0)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.invalid_native_render_replacement_evidence",
    )
    invalid = issue.details["invalid_replacements"]
    assert invalid == [
        {
            "reason": "node_still_present",
            "path": ["PMBAM", "Torso"],
            "role": "skin_mesh",
        }
    ]
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_required_socket() -> None:
    result = _rigged_character()
    lhand = result["model"].find_node("lhand")
    assert lhand is not None
    assert lhand.parent is not None
    lhand.parent.children.remove(lhand)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.required_socket_missing" in _codes(preflight)
    issue = _issue_by_code(preflight, "character.export.required_socket_missing")
    assert issue.details["category"] == "left_hand"
    assert issue.details["expected_native_socket_nodes"] == ["lhand"]
    assert issue.details["engine_string_evidence_status"] == "selected_hook_string_refs_verified_parser_pending"
    assert issue.details["engine_string_refs"][0]["string"] == "lhand"
    assert "SwitchWeaponEvent@00610f40" in issue.details["engine_string_refs"][0]["representative_refs"]
    assert issue.details["engine_evidence_tier"] == "engine_string_ref_verified"
    assert issue.details["engine_verified_socket_nodes"] == ["lhand"]
    assert issue.details["pending_engine_string_ref_nodes"] == []
    assert preflight.report.has_blocking is True


def test_character_export_preflight_marks_fixture_only_socket_evidence_pending() -> None:
    result = _rigged_character()
    lightsaber_hook = result["model"].find_node("LightsaberHook")
    assert lightsaber_hook is not None
    assert lightsaber_hook.parent is not None
    lightsaber_hook.parent.children.remove(lightsaber_hook)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
    )

    issue = _issue_by_code(preflight, "character.export.recommended_socket_missing")
    assert issue.details["category"] == "lightsaber"
    assert issue.details["expected_native_socket_nodes"] == ["LightsaberHook"]
    assert issue.details["engine_string_refs"] == []
    assert issue.details["engine_verified_socket_nodes"] == []
    assert issue.details["pending_engine_string_ref_nodes"] == ["LightsaberHook"]
    assert issue.details["engine_evidence_tier"] == "native_fixture_only_pending_engine_string_ref"
    assert issue.details["findings_doc"] == "docs/ghidra_findings.md"


def test_character_export_preflight_detects_exact_node_case_changes() -> None:
    result = _rigged_character()
    rhand = result["model"].find_node("rhand")
    assert rhand is not None
    rhand.name = "RHand"

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.node_case_changed" in _codes(preflight)
    issue = _issue_by_code(preflight, "character.export.node_case_changed")
    assert issue.details["socket_category"] == "right_hand"
    assert issue.details["engine_string_refs"][0]["string"] == "rhand"
    assert "SwitchWeaponEvent@00610f40" in issue.details["engine_string_refs"][0]["representative_refs"]
    assert issue.details["engine_evidence_tier"] == "engine_string_ref_verified"
    assert issue.details["pending_engine_string_ref_nodes"] == []
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_reparented_native_deform_helper() -> None:
    result = _rigged_character()
    torso_upr = result["model"].find_node("torsoUpr_g")
    assert torso_upr is not None
    assert torso_upr.parent is not None
    old_parent = torso_upr.parent
    old_parent.children.remove(torso_upr)
    root = result["model"].root_node
    assert root is not None
    torso_upr.parent = root
    root.children.append(torso_upr)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.node_path_changed")
    assert issue.details["role"] == "deform_helper"
    assert issue.details["expected_path"] == [
        "PMBAM",
        "cutscenedummy",
        "rootdummy",
        "torso_g",
        "torsoUpr_g",
    ]
    assert issue.details["actual_path"] == ["PMBAM", "torsoUpr_g"]
    assert "animation inheritance depends on exact node paths" in issue.fix_hint
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_skin_payload() -> None:
    template = _native_template()

    preflight = preflight_character_mdl_export(
        template,
        native_snapshot=None,
        options=CharacterExportPreflightOptions(
            require_source_mdl=False,
            require_native_snapshot=False,
            recommended_socket_categories=(),
        ),
    )

    assert "character.export.empty_bonemap" in _codes(preflight)
    assert "character.export.no_skin_rows" in _codes(preflight)
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_missing_source_provenance() -> None:
    template = _native_template()
    delattr(template, "_gr_source_resref")
    result = _rigged_character(template)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.no_native_source" in _codes(preflight)
    assert preflight.report.has_blocking is True


def test_character_export_preflight_issues_carry_engine_evidence() -> None:
    result = _rigged_character()
    delattr(result["model"], "_gr_native_skeleton_snapshot")

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=None,
    )

    issue = _issue_by_code(preflight, "character.export.missing_native_snapshot")
    evidence = issue.details["engine_evidence"]
    assert evidence["findings_doc"] == "docs/ghidra_findings.md"
    assert evidence["status"] == "fixture_verified_function_addresses_pending"
    assert evidence["engine_string_evidence_status"] == "selected_hook_string_refs_verified_parser_pending"
    assert "mcp:ghostrigger_model_info:k1:pmbam" in evidence["verified_sources"]
    assert "mcp:kotor_engine_script:k1:selected_hook_string_refs" in evidence["verified_sources"]
    assert "selected_native_base_owns_final_dag" in evidence["verified_native_contract"]
    function_evidence = {
        entry["function"]: entry
        for entry in evidence["function_disassembly_evidence"]
        if entry["game"] == "k1"
    }
    assert function_evidence["LoadVisualEffect"]["address"] == "006a1880"
    assert (
        function_evidence["LoadVisualEffect"]["evidence_kind"]
        == "function_metadata_and_disassembly_decompiler_unavailable"
    )
    assert "Imp_HeadCon_Node" in " ".join(
        function_evidence["LoadVisualEffect"]["observed_instruction_notes"]
    )
    refs = {
        (entry["game"], entry["string"]): tuple(entry["representative_refs"])
        for entry in evidence["engine_string_refs"]
    }
    assert "SwitchWeaponEvent@00610f40" in refs[("k1", "rhand")]
    assert "SwitchWeaponEvent@0040f4a0" in refs[("k2", "rhand")]
    assert refs[("k1", "lhand")]
    assert refs[("k2", "lhand")]


def test_character_export_preflight_blocks_qbone_tbone_mismatch() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.qbone_list = []
    mesh.tbone_list = []

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.qbone_mismatch" in _codes(preflight)
    assert "character.export.tbone_mismatch" in _codes(preflight)
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_nonfinite_skin_geometry() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.vertices[1] = (float("nan"), 0.0, 0.0)
    mesh.normals[0] = (0.0, float("inf"), 1.0)
    mesh.faces = [(0, 1, 99)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    vertex = _issue_by_code(preflight, "character.export.vertex_nonfinite")
    normal = _issue_by_code(preflight, "character.export.normal_nonfinite")
    face = _issue_by_code(preflight, "character.export.face_index_out_of_range")
    assert vertex.details["vertex_index"] == 1
    assert vertex.details["coordinates"] == ["nan", "0.0", "0.0"]
    assert normal.details["normal_index"] == 0
    assert face.details["bad_indices"] == [99]
    assert face.details["vertex_count"] == 3
    assert preflight.report.has_blocking is True


def test_character_export_preflight_reports_malformed_geometry_without_crashing() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.vertices[0] = "not-a-vertex"
    mesh.normals[0] = "not-a-normal"

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    vertex = _issue_by_code(preflight, "character.export.vertex_malformed")
    normal = _issue_by_code(preflight, "character.export.normal_nonfinite")
    assert vertex.details["vertex_index"] == 0
    assert vertex.details["component_count"] == 0
    assert normal.details["normal_index"] == 0
    assert normal.details["components"] == []
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_noninteger_face_indices() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.faces = [(0, 1.5, 2)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.face_index_noninteger")
    assert issue.severity.value == "blocking"
    assert issue.details["face_index"] == 0
    assert issue.details["indices"] == ["1.5"]
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_invalid_bind_transform_metadata() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    assert mesh.qbone_list
    assert mesh.tbone_list
    mesh.qbone_list[0] = (0.0, 0.0, float("nan"), 1.0)
    mesh.tbone_list[0] = (0.0, float("inf"), 0.0)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    qbone = _issue_by_code(preflight, "character.export.qbone_nonfinite")
    tbone = _issue_by_code(preflight, "character.export.tbone_nonfinite")
    assert qbone.details["expected_components"] == 4
    assert qbone.details["components"] == ["0.0", "0.0", "nan", "1.0"]
    assert tbone.details["expected_components"] == 3
    assert tbone.details["components"] == ["0.0", "inf", "0.0"]
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_vertices_with_more_than_four_influences() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.bone_map = list(mesh.bone_map) + list(mesh.bone_map) * 4
    mesh.qbone_list = list(mesh.bone_map)
    mesh.tbone_list = list(mesh.bone_map)
    mesh.skin_data[0].influences = [
        type("Influence", (), {"bone_index": index, "weight": 0.2})()
        for index in range(5)
    ]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.vertex_too_many_influences")
    assert issue.details["max_influences"] == 4
    assert issue.details["evidence_status"] == "writer_format_contract_verified_ghidra_pending"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_negative_and_nonfinite_skin_weights() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.skin_data[0].influences = [
        type("Influence", (), {"bone_index": 0, "weight": -0.25})(),
        type("Influence", (), {"bone_index": 0, "weight": float("inf")})(),
    ]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    negative = _issue_by_code(preflight, "character.export.vertex_weight_negative")
    nonfinite = _issue_by_code(preflight, "character.export.vertex_weight_nonfinite")
    assert negative.severity.value == "blocking"
    assert nonfinite.severity.value == "blocking"
    assert negative.details["weight"] == -0.25
    assert nonfinite.details["weight"] == "inf"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_zero_sum_skin_weights() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.skin_data[0].influences = [
        type("Influence", (), {"bone_index": 0, "weight": 0.0})(),
    ]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.vertex_weight_zero_sum")
    assert issue.severity.value == "blocking"
    assert issue.details["weight_sum"] == 0.0
    assert issue.details["evidence_status"] == "writer_format_contract_verified_ghidra_pending"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_warns_on_positive_unnormalized_skin_weights() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.skin_data[0].influences = [
        type("Influence", (), {"bone_index": 0, "weight": 0.5})(),
    ]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.vertex_weight_sum")
    assert issue.severity.value == "warning"
    assert issue.details["weight_sum"] == 0.5
    assert issue.details["tolerance"] == 0.01
    assert issue.details["pending_ghidra"] == "engine_weight_normalization_behavior"
    assert preflight.export_allowed is True


def test_character_export_preflight_blocks_missing_bonemap_target() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.bone_map = ["missing_native_node"]
    mesh.qbone_list = [(0.0, 0.0, 0.0, 1.0)]
    mesh.tbone_list = [(0.0, 0.0, 0.0)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.bonemap_target_missing")
    assert issue.details["bone_name"] == "missing_native_node"
    assert issue.details["bone_map_index"] == 0
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_bonemap_case_change() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.bone_map = ["RootDummy"]
    mesh.qbone_list = [(0.0, 0.0, 0.0, 1.0)]
    mesh.tbone_list = [(0.0, 0.0, 0.0)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.bonemap_target_case_changed")
    assert issue.details["bone_name"] == "RootDummy"
    assert issue.details["actual_node_name"] == "rootdummy"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_bonemap_target_outside_native_snapshot() -> None:
    result = _rigged_character()
    mesh = result["model"].find_node("custom_body")
    assert mesh is not None
    mesh.bone_map = ["custom_body"]
    mesh.qbone_list = [(0.0, 0.0, 0.0, 1.0)]
    mesh.tbone_list = [(0.0, 0.0, 0.0)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.bonemap_target_not_native")
    assert issue.details["bone_name"] == "custom_body"
    assert issue.details["native_snapshot_model"] == "pmbam"
    assert issue.details["engine_evidence_status"] == "fixture_verified_function_addresses_pending"
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_leftover_imported_armature_node() -> None:
    result = _rigged_character()
    root = result["model"].root_node
    assert root is not None
    _node("mixamorig:Hips", parent=root)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.non_native_skeleton_node")
    assert issue.details["node_name"] == "mixamorig:Hips"
    assert issue.details["actual_path"] == ["PMBAM", "mixamorig:Hips"]
    assert issue.details["allowed_non_native_role"] == "mesh_or_skin_payload"
    assert "imported armature/helper nodes" in issue.fix_hint
    assert preflight.report.has_blocking is True


def test_character_builder_validation_report_has_full_manual_checklist() -> None:
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(source="test.preflight"),
    )

    data = report.to_dict()

    assert data["manual_in_game_checklist"] == list(CHARACTER_BUILDER_MANUAL_CHECKLIST)
    assert len(data["manual_in_game_checklist"]) == 12
    assert "Two-handed weapon both hand sockets" in data["manual_in_game_checklist"]
    assert "Loading in both KOTOR 1 and KOTOR 2" in data["manual_in_game_checklist"]
    assert data["capability"]["stage"] == "export_candidate"
    assert data["capability"]["game_tested"] is False
    assert data["capability"]["game_test_status"] == "not_game_tested"
    text = report.to_text()
    assert "Capability stage: export_candidate" in text
    assert "Game tested: False" in text
    assert "1. Load as player character without crash" in text
    assert "12. Loading in both KOTOR 1 and KOTOR 2" in text


def test_character_builder_validation_text_includes_actionable_issue_context() -> None:
    report = CharacterBuilderValidationReport(
        status="blocked",
        verified=False,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.BLOCKING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.node_path_changed",
                    message="Native node moved.",
                    navigation=ValidationNavigationTarget(node_name="torsoUpr_g"),
                    fix_hint="Restore the selected native skeleton hierarchy before export.",
                    details={
                        "expected_path": ["PMBAM", "rootdummy", "torsoUpr_g"],
                        "actual_path": ["PMBAM", "torsoUpr_g"],
                        "role": "deform_helper",
                    },
                )
            ],
        ),
    )

    text = report.to_text()

    assert "Capability stage: blocked" in text
    assert "character.export.node_path_changed: Native node moved." in text
    assert "Fix: Restore the selected native skeleton hierarchy before export." in text
    assert "Navigate: node_name=torsoUpr_g" in text
    assert "actual_path=[PMBAM, torsoUpr_g]" in text
    assert "expected_path=[PMBAM, rootdummy, torsoUpr_g]" in text
    assert "role=deform_helper" in text


class _FakeCharacterWriter:
    calls: list = []

    def write_files(self, model, mdl_path: str) -> None:
        from pathlib import Path

        _FakeCharacterWriter.calls.append((model, mdl_path))
        path = Path(mdl_path)
        path.write_bytes(b"mdl")
        path.with_suffix(".mdx").write_bytes(b"mdx")


def test_character_export_transaction_stages_verifies_and_writes_reports(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    result["model"].metadata["kotor_fit_report"] = {
        "fit_policy": "bone_landmark_basis",
        "confidence": 0.95,
        "fit_transform": {
            "formula": "kotor_point = linear_matrix * source_point + translation",
            "scale": 0.8,
            "translation": [0.0, 0.0, 0.0],
        },
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
    }
    result["model"].metadata["kotor_normalization"] = {
        "fit_policy": "bone_landmark_basis",
        "scale": 0.8,
        "scale_basis": "bone_landmark_height",
        "fit_transform": result["model"].metadata["kotor_fit_report"]["fit_transform"],
    }
    output = tmp_path / "grbody.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is True
    assert _FakeCharacterWriter.calls
    assert output.read_bytes() == b"mdl"
    assert output.with_suffix(".mdx").read_bytes() == b"mdx"
    report_path = tmp_path / "grbody_validation_report.json"
    text_path = tmp_path / "grbody_validation_report.txt"
    assert report_path.exists()
    assert text_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "ghostrigger.character_export_validation.v1"
    assert payload["verified"] is True
    assert payload["status"] == "verified"
    assert payload["capability"]["stage"] == "export_candidate"
    assert payload["capability"]["game_tested"] is False
    assert payload["capability"]["game_test_status"] == "not_game_tested"
    assert payload["engine_evidence"]["findings_doc"] == "docs/ghidra_findings.md"
    assert len(payload["manual_in_game_checklist"]) == 12
    workflow = payload["metadata"]["character_builder_workflow"]
    assert workflow["native_skeleton_is_authority"] is True
    assert workflow["imported_mesh_role"] == "payload_guest"
    assert workflow["final_dag_source"] == "selected_kotor_base"
    assert workflow["rig_state"]["state"] == "native_template_final"
    assert workflow["rig_state"]["native_base_resref"] == "pmbam"
    assert workflow["rig_state"]["native_base_model_name"] == "pmbam"
    assert workflow["rig_state"]["native_base_game"] == "K1"
    assert workflow["rig_state"]["imported_payload_name"] == "grbody"
    assert workflow["rig_state"]["payload_mesh_names"] == ["custom_body"]
    assert workflow["bind"]["status"] == "bound_to_native_kotor_skeleton"
    assert workflow["bind"]["native_base"]["source_resref"] == "pmbam"
    assert workflow["bind"]["native_base"]["dag_authority"] == "native_kotor_base"
    replaced_render_nodes = workflow["bind"]["native_base"]["replaced_render_payload_nodes"]
    assert replaced_render_nodes == [
        {
            "name": "Torso",
            "path": ["PMBAM", "Torso"],
            "is_mesh": True,
            "is_skin": True,
            "vertex_count": 1,
            "face_count": 1,
            "texture": "",
            "replacement": "imported_mesh_payload",
        }
    ]
    assert workflow["bind"]["native_base"]["replaced_render_payload_count"] == 1
    assert workflow["bind"]["imported_payload"]["model_name"] == "grbody"
    assert workflow["bind"]["imported_payload"]["mesh_role"] == "payload_guest"
    assert workflow["bind"]["imported_payload"]["mesh_names"] == ["custom_body"]
    assert workflow["fit_report"]["fit_policy"] == "bone_landmark_basis"
    assert workflow["fit_report"]["fit_transform"]["scale"] == 0.8
    assert workflow["normalization"]["fit_transform"]["translation"] == [0.0, 0.0, 0.0]
    assert workflow["native_snapshot"]["model_name"] == "pmbam"
    assert workflow["native_snapshot"]["game"] == "K1"
    assert workflow["native_snapshot"]["supermodel"] == "S_KPMF0200"
    expected_fingerprint = native_skeleton_fingerprint(result["native_skeleton_snapshot"])
    assert workflow["native_snapshot"]["dag_fingerprint"] == expected_fingerprint
    assert workflow["native_snapshot"]["dag_fingerprint_algorithm"] == "sha256"
    assert len(workflow["native_snapshot"]["dag_fingerprint"]) == 64
    reload_issues = {
        issue["code"]: issue
        for issue in payload["reload_report"]["issues"]
    }
    reload_summary = reload_issues["character.export.reload_verified"]["details"]["reloaded_model"]
    assert reload_summary["model_name"] == "grbody"
    assert reload_summary["supermodel"] == "S_KPMF0200"
    assert reload_summary["node_count"] >= result["native_skeleton_snapshot"].node_count
    assert reload_summary["skin_node_count"] >= 1
    assert reload_summary["skin_payloads"][0]["name"] == "custom_body"
    assert reload_summary["skin_payloads"][0]["skin_rows"] == 3
    assert reload_summary["native_snapshot_checked"]["game"] == "K1"
    assert reload_summary["native_snapshot_checked"]["supermodel"] == "S_KPMF0200"
    assert reload_summary["native_snapshot_checked"]["dag_fingerprint"] == expected_fingerprint
    assert reload_summary["native_snapshot_checked"]["dag_fingerprint_algorithm"] == "sha256"
    text = text_path.read_text(encoding="utf-8")
    assert "Capability stage: export_candidate" in text
    assert "Game tested: False" in text
    assert "Character Builder workflow evidence" in text
    assert "Rig state: native_template_final" in text
    assert "Auto-fit policy: bone_landmark_basis" in text
    assert "reloaded_model={model_name: grbody" in text
    assert "Manual in-game checklist" in text
    assert "12. Loading in both KOTOR 1 and KOTOR 2" in text


def test_native_skeleton_fingerprint_tracks_dag_contract_not_paths() -> None:
    result = _rigged_character()
    snapshot = result["native_skeleton_snapshot"]
    baseline = native_skeleton_fingerprint(snapshot)

    path_only = replace(
        snapshot,
        metadata={
            **dict(snapshot.metadata or {}),
            "source_mdl_path": "C:/different/install/pmbam.mdl",
            "source_mdx_path": "C:/different/install/pmbam.mdx",
        },
    )
    assert native_skeleton_fingerprint(path_only) == baseline

    game_changed = replace(snapshot, game="K2")
    assert native_skeleton_fingerprint(game_changed) != baseline

    node = snapshot.nodes[0]
    node_changed = replace(
        snapshot,
        nodes=(
            replace(node, full_path=("DifferentRoot",), parent_path=()),
            *snapshot.nodes[1:],
        ),
    )
    assert native_skeleton_fingerprint(node_changed) != baseline


def test_character_export_transaction_reload_verifies_without_workflow_markers(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    reloaded_model = copy.deepcopy(result["model"])
    for attr in (
        "_gr_character_builder_rig_state",
        "_gr_character_builder_dag_authority",
        "_gr_native_skeleton_snapshot",
        "_gr_character_builder_bind_complete",
    ):
        if hasattr(reloaded_model, attr):
            delattr(reloaded_model, attr)
    reloaded_model.metadata.pop("character_builder_rig_state", None)
    output = tmp_path / "grbody_reload_clean.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: reloaded_model,
        )
    )

    assert tx.succeeded is True
    assert output.exists()
    assert output.with_suffix(".mdx").exists()
    assert "character.export.not_native_template_final_rig" not in {
        issue.code for issue in tx.export_job_result.validation_report.issues
    }
    assert "character.export.reload_verified" in {
        issue.code for issue in tx.export_job_result.validation_report.issues
    }


def test_character_export_transaction_preflight_failure_never_calls_writer(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    delattr(result["model"], "_gr_native_skeleton_snapshot")
    output = tmp_path / "blocked.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=None,
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls == []
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    assert not (tmp_path / "blocked_validation_report.json").exists()
    assert "character.export.missing_native_snapshot" in {
        issue.code for issue in tx.export_job_result.validation_report.issues
    }


def test_character_export_transaction_blocks_wrong_game_before_writer(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    output = tmp_path / "wrong_game.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            game="K2",
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls == []
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    issue = _issue_by_code(
        tx.preflight_result,
        "character.export.native_snapshot_game_mismatch",
    )
    assert issue.details["export_game"] == "K2"


def test_character_export_transaction_blocks_supermodel_case_before_writer(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    result["model"].supermodel = "s_kpmf0200"
    output = tmp_path / "bad_supermodel_case.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls == []
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    issue = _issue_by_code(
        tx.preflight_result,
        "character.export.supermodel_case_changed",
    )
    assert issue.details["expected"] == "S_KPMF0200"
    assert issue.details["actual"] == "s_kpmf0200"


def test_character_export_transaction_blocks_unknown_game_before_writer(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    snapshot = result["native_skeleton_snapshot"]
    unknown_snapshot = replace(
        snapshot,
        game="unknown",
        metadata={
            **dict(snapshot.metadata or {}),
            "source_game": "",
            "game": "",
        },
    )
    output = tmp_path / "unknown_game.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            game="K1",
            native_snapshot=unknown_snapshot,
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls == []
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    issue = _issue_by_code(
        tx.preflight_result,
        "character.export.native_snapshot_game_unknown",
    )
    assert issue.details["export_game"] == "K1"


def test_character_export_transaction_accepts_k2_native_snapshot(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character(game="K2")
    output = tmp_path / "grbody_k2.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            game="K2",
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: result["model"],
        )
    )

    assert tx.succeeded is True
    assert output.exists()
    assert output.with_suffix(".mdx").exists()
    payload = json.loads(
        (tmp_path / "grbody_k2_validation_report.json").read_text(encoding="utf-8")
    )
    assert payload["game"] == "K2"
    assert payload["metadata"]["game"] == "K2"
    workflow = payload["metadata"]["character_builder_workflow"]
    assert workflow["native_snapshot"]["game"] == "K2"
    assert workflow["native_snapshot"]["supermodel"] == "S_Female02"
    assert workflow["rig_state"]["state"] == "native_template_final"
    assert payload["capability"]["stage"] == "export_candidate"


def test_character_export_transaction_reload_failure_leaves_no_final_files(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    output = tmp_path / "reload_fail.mdl"

    def _broken_loader(_mdl, _mdx):
        raise RuntimeError("readback broke")

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=_broken_loader,
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    assert not (tmp_path / "reload_fail_validation_report.json").exists()
    assert "character.export.reload_failed" in {
        issue.code for issue in tx.export_job_result.validation_report.issues
    }
