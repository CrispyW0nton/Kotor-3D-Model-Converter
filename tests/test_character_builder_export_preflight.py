from __future__ import annotations

from src.core.characters.character_builder import apply_template_rig
from src.core.characters.character_export_preflight import (
    CharacterExportPreflightOptions,
    preflight_character_mdl_export,
)
from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags


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
