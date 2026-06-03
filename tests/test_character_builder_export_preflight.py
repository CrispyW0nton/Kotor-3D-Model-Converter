from __future__ import annotations

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
from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
from src.core.validation.validation_bus import ValidationReport


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


def _native_template(*, include_lhand: bool = True) -> KotorModel:
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
    model = KotorModel(name="pmbam", root_node=root, supermodel="S_KPMF0200")
    model._gr_source_resref = "pmbam"
    model._gr_source_game = "K1"
    model._gr_source_layer = "game_library"
    return model


def _rigged_character(template: KotorModel | None = None) -> dict:
    return apply_template_rig(
        _mesh_model(),
        template or _native_template(),
        game="K1",
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


def test_character_export_preflight_blocks_missing_required_socket() -> None:
    result = _rigged_character(_native_template(include_lhand=False))

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.required_socket_missing" in _codes(preflight)
    assert preflight.report.has_blocking is True


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
    assert "mcp:ghostrigger_model_info:k1:pmbam" in evidence["verified_sources"]
    assert "selected_native_base_owns_final_dag" in evidence["verified_native_contract"]


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
    text = report.to_text()
    assert "1. Load as player character without crash" in text
    assert "12. Loading in both KOTOR 1 and KOTOR 2" in text


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
    assert payload["engine_evidence"]["findings_doc"] == "docs/ghidra_findings.md"
    assert len(payload["manual_in_game_checklist"]) == 12
    text = text_path.read_text(encoding="utf-8")
    assert "Manual in-game checklist" in text
    assert "12. Loading in both KOTOR 1 and KOTOR 2" in text


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
