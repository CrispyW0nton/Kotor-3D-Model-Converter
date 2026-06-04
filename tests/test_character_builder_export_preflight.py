from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json

from src.core.characters import character_validation_report as cv_report
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
    CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA,
    CharacterBuilderValidationReport,
    build_character_game_test_evidence,
    character_game_test_evidence_passed,
)
from src.core.characters.native_skeleton import native_skeleton_fingerprint
from src.core.geometry.model_data import (
    BoneWeight,
    KotorModel,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)
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


def _valid_fit_report(
    *,
    confidence: float = 0.95,
    fallback_used: bool = False,
    used_landmarks: list[str] | None = None,
    source_landmark_sources: dict[str, str] | None = None,
) -> dict:
    landmarks = list(used_landmarks or [
        "source:head=Head",
        "source:left_foot=LeftFoot",
        "source:pelvis=Hips",
        "source:right_foot=RightFoot",
        "source:side_pair=shoulder",
        "target:head=head_g",
        "target:left_foot=lfoot_g",
        "target:pelvis=pelvis_g",
        "target:right_foot=rfoot_g",
        "target:side_pair=shoulder",
    ])
    source_sources = dict(source_landmark_sources or {
        "head": "imported_skeleton",
        "left_foot": "imported_skeleton",
        "pelvis": "imported_skeleton",
        "right_foot": "imported_skeleton",
        "left": "imported_skeleton",
        "right": "imported_skeleton",
    })
    return {
        "fit_policy": "bone_landmark_basis",
        "confidence": confidence,
        "fallback_used": fallback_used,
        "source_forward_axis": "+y",
        "source_up_axis": "+z",
        "target_forward_axis": "+y",
        "target_up_axis": "+z",
        "fit_transform": {
            "formula": "kotor_point = linear_matrix * source_point + translation",
            "scale": 0.8,
            "rotation_matrix": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "linear_matrix": [
                [0.8, 0.0, 0.0],
                [0.0, 0.8, 0.0],
                [0.0, 0.0, 0.8],
            ],
            "translation": [0.0, 0.0, 0.0],
            "landmark_alignment": {
                "method": "paired_skeleton_landmark_similarity",
                "pair_count": 6,
                "paired_roles": [
                    "pelvis",
                    "head",
                    "left",
                    "right",
                    "left_foot",
                    "right_foot",
                ],
                "rms_error": 0.04,
                "max_error": 0.08,
                "worst_pair_role": "right_foot",
                "pair_errors": [
                    {
                        "role": "pelvis",
                        "source_position": [0.0, 0.0, 0.8],
                        "target_position": [0.0, 0.0, 0.64],
                        "mapped_position": [0.0, 0.0, 0.64],
                        "error": 0.0,
                    },
                    {
                        "role": "right_foot",
                        "source_position": [0.3, 0.0, 0.0],
                        "target_position": [0.24, 0.0, 0.0],
                        "mapped_position": [0.22, 0.0, 0.0],
                        "error": 0.08,
                    },
                ],
                "translation_basis": "native_fit_origin",
                "height_scale": 0.8,
                "height_scale_basis": "bone_landmark_height",
                "solved_scale": 0.79,
                "applied_scale": 0.8,
                "applied_scale_basis": "bone_landmark_height",
            },
        },
        "kotor_contract": {
            "native_skeleton_is_authority": True,
            "imported_mesh_role": "payload_guest",
            "final_dag_source": "selected_kotor_base",
        },
        "source_imported_armature": {
            "source": "imported_fbx_armature",
            "guide_joint_count": 6,
            "scene_guide_joint_count": 6,
            "armature_names": ["Armature"],
        },
        "auto_fit_report": {
            "source_forward_axis": "+y",
            "source_up_axis": "+z",
            "target_forward_axis": "+y",
            "target_up_axis": "+z",
            "scale_factor": 0.8,
            "height_source": "landmarks",
            "ground_origin_basis": "source_pelvis_ground",
            "used_landmarks": landmarks,
            "confidence": confidence,
            "fallback_used": fallback_used,
            "notes": "",
        },
        "used_landmarks": landmarks,
        "source_frame": {
            "landmarks": {
                "head": "Head",
                "left_foot": "LeftFoot",
                "pelvis": "Hips",
                "right_foot": "RightFoot",
                "side_pair": "shoulder",
            },
            "landmark_sources": source_sources,
        },
        "target_frame": {
            "landmarks": {
                "head": "head_g",
                "left_foot": "lfoot_g",
                "pelvis": "pelvis_g",
                "right_foot": "rfoot_g",
                "side_pair": "shoulder",
            },
            "landmark_sources": {
                "head": "kotor_deform_helper",
                "left_foot": "kotor_deform_helper",
                "pelvis": "kotor_deform_helper",
                "right_foot": "kotor_deform_helper",
                "left": "kotor_deform_helper",
                "right": "kotor_deform_helper",
            },
        },
    }


def _stamp_valid_fit_evidence(result: dict, *, confidence: float = 0.95) -> dict:
    model = result["model"]
    model.metadata["kotor_fit_report"] = _valid_fit_report(confidence=confidence)
    model.metadata["kotor_normalization"] = {
        "fit_policy": "bone_landmark_basis",
        "scale": 0.8,
        "scale_basis": "bone_landmark_height",
        "fit_transform": model.metadata["kotor_fit_report"]["fit_transform"],
    }
    return result


def _stamp_animation_library_evidence(
    model: KotorModel,
    *,
    supermodel: str = "S_KPMF0200",
    game: str = "K1",
) -> None:
    model.metadata["character_builder_motion_assignment"] = {
        "schema": "ghostrigger.character_motion_assignment.v1",
        "source": "inherited_supermodel",
        "supermodel": supermodel,
        "code": "inherited",
        "ok": True,
        "available_preview_names": ["pause1", "walk", "run", "tlknorm"],
        "missing_preview_names": [],
    }
    model.metadata["character_builder_animation_library"] = {
        "schema": "ghostrigger.character_animation_library_evidence.v1",
        "status": "resolved",
        "ok": True,
        "code": "listed",
        "message": "267 animation clip(s) available.",
        "game": game,
        "body": model.name,
        "motion_source": "inherited_supermodel",
        "selected_supermodel": supermodel,
        "effective_supermodel": supermodel,
        "resolved_supermodel": supermodel,
        "resolver_configured": True,
        "local_animation_count": 0,
        "resolved_supermodel_local_animation_count": 43,
        "available_count": 267,
        "sample_animation_names": [
            "pause1",
            "pause2",
            "walk",
            "run",
            "tlknorm",
            "victory",
        ],
        "required_preview_names": ["pause1", "walk", "run", "tlknorm"],
        "required_preview_available": ["pause1", "walk", "run", "tlknorm"],
        "required_preview_missing": [],
        "diagnostics": [],
    }


def _test_output_hashes() -> dict[str, dict[str, int | str]]:
    return {
        "mdl": {"sha256": hashlib.sha256(b"mdl").hexdigest(), "size": 3},
        "mdx": {"sha256": hashlib.sha256(b"mdx").hexdigest(), "size": 3},
    }


def _game_ready_workflow() -> dict:
    return {
        "fit_report": _valid_fit_report(),
        "rig_state": {
            "state": RIG_STATE_NATIVE_TEMPLATE_FINAL,
            "dag_authority": RIG_DAG_AUTHORITY_NATIVE_KOTOR,
        },
        "native_snapshot": {
            "model_name": "pmbam",
            "game": "K1",
            "dag_fingerprint": "native-dag",
        },
        "bind": {
            "status": "bound_to_native_kotor_skeleton",
            "native_base": {
                "source_resref": "pmbam",
                "dag_authority": RIG_DAG_AUTHORITY_NATIVE_KOTOR,
            },
            "imported_payload": {
                "mesh_role": "payload_guest",
                "mesh_names": ["custom_body"],
            },
            "skin_binding": {
                "weighting_method": "native_template_nearest_vertex_donor",
                "quality_stage": "donor_transfer_verified",
                "donor_weight_transfer": True,
                "mesh_reports": [
                    {
                        "mesh_name": "custom_body",
                        "weighted_vertices": 3,
                    }
                ],
            },
        },
        "animation_library": {
            "motion_source": "inherited_supermodel",
            "selected_supermodel": "S_Female02",
            "effective_supermodel": "S_Female02",
            "resolved_supermodel": "S_Female02",
            "game": "K1",
            "available_count": 4,
            "sample_animation_names": ["pause1", "walk", "run", "tlknorm"],
            "required_preview_available": ["pause1", "walk", "run", "tlknorm"],
            "required_preview_missing": [],
            "diagnostics": [],
        },
    }


def _rigged_character(template: KotorModel | None = None, *, game: str = "K1") -> dict:
    return _stamp_valid_fit_evidence(
        apply_template_rig(
            _mesh_model(),
            template or _native_template(game=game),
            game=game,
            scale_mode="manual",
        )
    )


def _donor_weight_rigged_character() -> dict:
    root = _node("import_root")
    mesh = _node("custom_body", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=root)
    mesh.vertices = [(-1.1, 0.0, 0.0), (1.1, 0.0, 0.0)]
    mesh.faces = [(0, 1, 1)]
    mesh_model = KotorModel(name="grbody", root_node=root)

    kotor_root = _node("PMBAM")
    _node("left_g", parent=kotor_root)
    _node("right_g", parent=kotor_root)
    donor = _node(
        "Torso",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=kotor_root,
    )
    donor.vertices = [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    donor.faces = [(0, 1, 1)]
    donor.bone_map = ["left_g", "right_g"]
    donor.skin_data = [
        VertexSkinData([BoneWeight(0, 1.0)]),
        VertexSkinData([BoneWeight(1, 1.0)]),
    ]
    template = KotorModel(name="pmbam", root_node=kotor_root, supermodel="S_KPMF0200")
    template._gr_source_resref = "pmbam"
    template._gr_source_game = "K1"
    template._gr_source_layer = "game_library"
    return _stamp_valid_fit_evidence(
        apply_template_rig(
            mesh_model,
            template,
            game="K1",
            scale_mode="manual",
        )
    )


def _codes(result) -> set[str]:
    return {issue.code for issue in result.report.issues}


def _issue_by_code(result, code: str):
    for issue in result.report.issues:
        if issue.code == code:
            return issue
    raise AssertionError(f"missing issue code {code}")


def _detach_node(model: KotorModel, name: str) -> None:
    for node in model.all_nodes():
        if node.name != name:
            continue
        parent = getattr(node, "parent", None)
        if parent is not None:
            parent.children = [
                child for child in parent.children if child is not node
            ]
        node.parent = None
        return
    raise AssertionError(f"missing node {name}")


def _find_model_node(model: KotorModel, name: str) -> ModelNode:
    for node in model.all_nodes():
        if node.name == name:
            return node
    raise AssertionError(f"missing node {name}")


def test_apply_template_rig_preserves_selected_native_supermodel() -> None:
    result = _rigged_character()

    assert result["ok"] is True
    assert result["model"].supermodel == "S_KPMF0200"
    assert result["native_skeleton_snapshot"].supermodel == "S_KPMF0200"
    bind_native = result["model"].metadata["character_builder_bind"]["native_base"]
    expected_fingerprint = native_skeleton_fingerprint(result["native_skeleton_snapshot"])
    assert bind_native["dag_fingerprint"] == expected_fingerprint
    assert bind_native["dag_fingerprint_algorithm"] == "sha256"
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


def test_character_export_preflight_warns_when_payload_material_evidence_is_missing() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    texture_issue = _issue_by_code(preflight, "character.export.payload_texture_missing")
    uv_issue = _issue_by_code(preflight, "character.export.payload_uvs_missing")
    assert texture_issue.severity.value == "warning"
    assert uv_issue.severity.value == "warning"
    assert texture_issue.details["node_name"] == "custom_body"
    assert uv_issue.details["vertex_count"] == 3
    assert preflight.export_allowed is True


def test_character_export_preflight_accepts_payload_texture_and_uvs_without_material_warning() -> None:
    result = _rigged_character()
    mesh = _find_model_node(result["model"], "custom_body")
    mesh.texture = "bendak_body"
    mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.payload_texture_missing" not in _codes(preflight)
    assert "character.export.payload_uvs_missing" not in _codes(preflight)
    assert "character.export.payload_uv_count_mismatch" not in _codes(preflight)
    assert preflight.export_allowed is True


def test_character_export_preflight_blocks_missing_auto_fit_evidence() -> None:
    result = _rigged_character()
    result["model"].metadata.pop("kotor_fit_report", None)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.missing_auto_fit_evidence")
    assert issue.severity.value == "blocking"
    assert "Run Auto-Fit" in issue.fix_hint
    assert preflight.export_allowed is False


def test_character_export_preflight_blocks_low_confidence_auto_fit() -> None:
    result = _rigged_character()
    result["model"].metadata["kotor_fit_report"] = _valid_fit_report(confidence=0.35)

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.low_auto_fit_confidence")
    assert issue.details["confidence"] == 0.35
    assert issue.details["required_confidence"] == 0.60
    assert preflight.export_allowed is False


def test_character_export_preflight_blocks_fallback_auto_fit() -> None:
    result = _rigged_character()
    result["model"].metadata["kotor_fit_report"] = _valid_fit_report(
        confidence=0.75,
        fallback_used=True,
    )

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.fallback_auto_fit_used")
    assert issue.details["fit_policy"] == "bone_landmark_basis"
    assert preflight.export_allowed is False


def test_character_export_preflight_warns_when_auto_fit_matrices_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["fit_transform"].pop("rotation_matrix", None)
    fit["fit_transform"].pop("linear_matrix", None)
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_transform_matrix_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == [
        "linear_matrix_not_recorded",
        "rotation_matrix_not_recorded",
    ]
    assert issue.details["scale"] == 0.8
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_on_reflected_auto_fit_matrix() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["fit_transform"]["rotation_matrix"] = [
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    fit["fit_transform"]["linear_matrix"] = [
        [-0.8, 0.0, 0.0],
        [0.0, 0.8, 0.0],
        [0.0, 0.0, 0.8],
    ]
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_transform_matrix_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == [
        "linear_matrix_reflected_or_degenerate",
        "rotation_matrix_reflected_or_degenerate",
    ]
    assert issue.details["rotation_determinant"] == -1.0
    assert abs(issue.details["linear_determinant"] + 0.512) < 1.0e-9
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_linear_matrix_scale_mismatches() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["fit_transform"]["linear_matrix"] = [
        [0.7, 0.0, 0.0],
        [0.0, 0.8, 0.0],
        [0.0, 0.0, 0.8],
    ]
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_transform_matrix_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == ["linear_matrix_scale_mismatch"]
    assert abs(issue.details["max_linear_scale_delta"] - 0.1) < 1.0e-9
    assert preflight.export_allowed is True


def test_character_export_preflight_blocks_auto_fit_contract_mismatch() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["kotor_contract"]["imported_mesh_role"] = "skeleton_authority"
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.auto_fit_contract_mismatch")
    assert issue.details["mismatches"]["imported_mesh_role"] == "skeleton_authority"
    assert preflight.export_allowed is False


def test_character_export_preflight_warns_when_auto_fit_source_landmark_sources_are_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit.pop("source_frame", None)
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_landmark_sources_not_recorded",
    )
    assert issue.severity.value == "warning"
    assert issue.details["source_landmark_domain"] == "not_recorded"
    assert "records whether imported skeleton" in issue.fix_hint
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_auto_fit_uses_mesh_payload_landmarks() -> None:
    result = _rigged_character()
    result["model"].metadata["kotor_fit_report"] = _valid_fit_report(
        source_landmark_sources={
            "head": "mesh_payload",
            "left_foot": "mesh_payload",
            "pelvis": "mesh_payload",
            "right_foot": "mesh_payload",
        },
    )

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_source_landmarks_need_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["source_landmark_source_counts"] == {"mesh_payload": 4}
    assert issue.details["non_skeleton_sources"] == {
        "head": "mesh_payload",
        "left_foot": "mesh_payload",
        "pelvis": "mesh_payload",
        "right_foot": "mesh_payload",
    }
    assert "mesh-only import" in issue.fix_hint
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_imported_skeleton_guides_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit.pop("source_imported_armature", None)
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_imported_skeleton_guides_not_recorded",
    )
    assert issue.severity.value == "warning"
    assert issue.details["imported_skeleton_roles"] == [
        "head",
        "left",
        "left_foot",
        "pelvis",
        "right",
        "right_foot",
    ]
    assert issue.details["source_imported_armature"] == {}
    assert "records the imported FBX armature or skeleton guide count" in issue.fix_hint
    assert preflight.export_allowed is True


def test_character_export_preflight_accepts_imported_skeleton_guide_inventory() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.auto_fit_imported_skeleton_guides_not_recorded" not in _codes(preflight)
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_paired_landmark_alignment_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["fit_transform"].pop("landmark_alignment", None)
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_paired_landmarks_need_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reason"] == "not_recorded"
    assert issue.details["required_pair_count"] == 4
    assert issue.details["max_pair_error"] == 0.16
    assert "paired skeleton-landmark" in issue.message
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_paired_landmark_alignment_is_weak() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    alignment = fit["fit_transform"]["landmark_alignment"]
    alignment["pair_count"] = 3
    alignment["paired_roles"] = ["pelvis", "head", "left"]
    alignment["rms_error"] = 0.42
    alignment["worst_pair_role"] = "left"
    alignment["pair_errors"] = [
        {
            "role": "left",
            "source_position": [-0.5, 0.0, 1.2],
            "target_position": [-0.4, 0.0, 0.96],
            "mapped_position": [-0.2, 0.0, 0.9],
            "error": 0.42,
        },
    ]
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_paired_landmarks_need_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == ["too_few_pairs", "high_rms_error"]
    assert issue.details["pair_count"] == 3
    assert issue.details["rms_error"] == 0.42
    assert issue.details["max_rms_error"] == 0.15
    assert issue.details["paired_roles"] == ["pelvis", "head", "left"]
    assert issue.details["worst_pair_role"] == "left"
    assert issue.details["pair_errors"][0]["role"] == "left"
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_single_fit_landmark_is_far() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    alignment = fit["fit_transform"]["landmark_alignment"]
    alignment["rms_error"] = 0.04
    alignment["max_error"] = 0.22
    alignment["worst_pair_role"] = "pelvis"
    alignment["pair_errors"] = [
        {
            "role": "pelvis",
            "source_position": [0.0, 0.0, 0.8],
            "target_position": [0.0, 0.0, 0.64],
            "mapped_position": [0.0, 0.18, 0.58],
            "error": 0.22,
        },
    ]
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_paired_landmarks_need_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == ["high_max_error"]
    assert issue.details["rms_error"] == 0.04
    assert issue.details["max_error"] == 0.22
    assert issue.details["max_pair_error"] == 0.16
    assert issue.details["worst_pair_role"] == "pelvis"
    assert issue.details["pair_errors"][0]["role"] == "pelvis"
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_toe_forward_disagrees() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["source_frame"]["landmarks"].update({
        "left_toe": "LeftToeBase",
        "right_toe": "RightToeBase",
    })
    fit["source_frame"]["landmark_sources"].update({
        "left_toe": "imported_skeleton",
        "right_toe": "imported_skeleton",
    })
    fit["source_frame"]["toe_forward_alignment"] = -0.2
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_toe_forward_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["frame"] == "source_frame"
    assert issue.details["reasons"] == ["low_alignment"]
    assert issue.details["toe_forward_alignment"] == -0.2
    assert issue.details["required_alignment"] == 0.5
    assert issue.details["landmarks"]["left_toe"] == "LeftToeBase"
    assert preflight.export_allowed is True


def test_character_export_preflight_accepts_aligned_toe_forward_evidence() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    for frame_name in ("source_frame", "target_frame"):
        fit[frame_name]["landmarks"].update({
            "left_toe": "LeftToeBase" if frame_name == "source_frame" else "lfootT_g",
            "right_toe": "RightToeBase" if frame_name == "source_frame" else "rfootT_g",
        })
        fit[frame_name]["toe_forward_alignment"] = 0.91
    fit["source_frame"]["landmark_sources"].update({
        "left_toe": "imported_skeleton",
        "right_toe": "imported_skeleton",
    })
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.auto_fit_toe_forward_needs_review" not in _codes(preflight)
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_rigged_source_toe_evidence_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["source_imported_armature"]["guide_joint_count"] = 65
    fit["source_imported_armature"]["scene_guide_joint_count"] = 65
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_toe_forward_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == ["source_toe_landmarks_not_recorded"]
    assert issue.details["frame"] == "source_frame"
    assert issue.details["source_imported_armature"]["guide_joint_count"] == 65
    assert issue.details["landmarks"]["left_foot"] == "LeftFoot"
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_target_toe_evidence_missing() -> None:
    result = _rigged_character()
    fit = copy.deepcopy(result["model"].metadata["kotor_fit_report"])
    fit["source_imported_armature"]["guide_joint_count"] = 65
    fit["source_imported_armature"]["scene_guide_joint_count"] = 65
    fit["source_frame"]["landmarks"].update({
        "left_toe": "LeftToeBase",
        "right_toe": "RightToeBase",
    })
    fit["source_frame"]["landmark_sources"].update({
        "left_toe": "imported_skeleton",
        "right_toe": "imported_skeleton",
    })
    fit["source_frame"]["toe_forward_alignment"] = 0.91
    result["model"].metadata["kotor_fit_report"] = fit

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.auto_fit_toe_forward_needs_review",
    )
    assert issue.severity.value == "warning"
    assert issue.details["reasons"] == ["target_toe_landmarks_not_recorded"]
    assert issue.details["frame"] == "target_frame"
    assert issue.details["source_imported_armature"]["guide_joint_count"] == 65
    assert issue.details["landmarks"]["left_foot"] == "lfoot_g"
    assert preflight.export_allowed is True


def test_character_export_preflight_accepts_small_source_without_toe_guides() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    assert "character.export.auto_fit_toe_forward_needs_review" not in _codes(preflight)
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_on_fallback_skin_binding() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.fallback_skin_binding")
    assert issue.severity.value == "warning"
    assert issue.details["weighting_method"] == "nearest_kotor_bone_segment"
    assert issue.details["quality_stage"] == "fallback_first_pass"
    assert issue.details["donor_weight_transfer"] is False
    assert issue.details["mesh_reports"][0]["mesh_name"] == "custom_body"
    assert "donor weight transfer" in issue.fix_hint
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_skin_binding_evidence_is_missing() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind.pop("skin_binding", None)
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.missing_skin_binding_evidence")
    assert issue.severity.value == "warning"
    assert preflight.export_allowed is True


def test_character_export_preflight_accepts_complete_donor_skin_binding_without_fallback_warning() -> None:
    result = _donor_weight_rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(
            required_socket_categories=(),
            recommended_socket_categories=(),
        ),
    )

    assert result["model"].metadata["character_builder_bind"]["skin_binding"]["donor_weight_transfer"] is True
    assert "character.export.fallback_skin_binding" not in _codes(preflight)
    assert "character.export.donor_skin_binding_landmarks_incomplete" not in _codes(preflight)
    assert preflight.export_allowed is True


def test_character_export_preflight_warns_when_donor_transfer_lacks_fit_landmarks() -> None:
    result = _donor_weight_rigged_character()
    result["model"].metadata["kotor_fit_report"] = _valid_fit_report(
        used_landmarks=[
            "source:pelvis=Hips",
            "target:pelvis=pelvis_g",
        ],
    )

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(
            required_socket_categories=(),
            recommended_socket_categories=(),
        ),
    )

    issue = _issue_by_code(
        preflight,
        "character.export.donor_skin_binding_landmarks_incomplete",
    )
    assert issue.severity.value == "warning"
    assert issue.details["donor_weight_transfer"] is True
    assert issue.details["missing_source_landmarks"] == [
        "head",
        "left_foot",
        "right_foot",
        "side_pair",
    ]
    assert issue.details["missing_target_landmarks"] == [
        "head",
        "left_foot",
        "right_foot",
        "side_pair",
    ]
    assert "character.export.fallback_skin_binding" not in _codes(preflight)
    assert preflight.export_allowed is True


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


def test_character_export_preflight_blocks_missing_bind_dag_fingerprint() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"].pop("dag_fingerprint", None)
    bind["native_base"].pop("dag_fingerprint_algorithm", None)
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.missing_bind_provenance")
    assert issue.severity.value == "blocking"
    assert (
        "character_builder_bind.native_base.dag_fingerprint"
        in issue.details["missing_bind_fields"]
    )
    assert (
        "character_builder_bind.native_base.dag_fingerprint_algorithm"
        in issue.details["missing_bind_fields"]
    )
    assert preflight.report.has_blocking is True


def test_character_export_preflight_blocks_stale_bind_dag_fingerprint() -> None:
    result = _rigged_character()
    bind = copy.deepcopy(result["model"].metadata["character_builder_bind"])
    bind["native_base"]["dag_fingerprint"] = "0" * 64
    bind["native_base"]["dag_fingerprint_algorithm"] = "sha256"
    result["model"].metadata["character_builder_bind"] = bind

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.bind_provenance_mismatch")
    assert issue.severity.value == "blocking"
    mismatch = issue.details["mismatches"]["native_snapshot_dag_fingerprint"]
    assert mismatch["bind"] == "0" * 64
    assert mismatch["native_snapshot"] == native_skeleton_fingerprint(
        result["native_skeleton_snapshot"]
    )
    assert mismatch["algorithm"] == "sha256"
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


def test_character_export_preflight_skips_recommended_socket_absent_from_native_base() -> None:
    result = _rigged_character()

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(
            recommended_socket_categories=("headgear",),
        ),
    )

    assert "character.export.recommended_socket_missing" not in _codes(preflight)


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


def test_character_export_preflight_blocks_empty_imported_mesh_flag_helper() -> None:
    result = _rigged_character()
    root = result["model"].root_node
    assert root is not None
    helper = _node(
        "ArmatureGuide",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        parent=root,
    )
    helper._gr_imported_armature_joint = True

    preflight = preflight_character_mdl_export(
        result["model"],
        native_snapshot=result["native_skeleton_snapshot"],
        options=CharacterExportPreflightOptions(recommended_socket_categories=()),
    )

    issue = _issue_by_code(preflight, "character.export.non_native_skeleton_node")
    assert issue.details["node_name"] == "ArmatureGuide"
    assert issue.details["allowed_non_native_role"] == "mesh_or_skin_payload"
    assert issue.details["actual_path"] == ["PMBAM", "ArmatureGuide"]
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
    assert data["capability"]["game_ready"] is False
    assert "game_test=not_requested" in data["capability"]["game_ready_blockers"]
    assert "fit=missing" in data["capability"]["game_ready_blockers"]
    assert data["capability"]["game_test_status"] == "not_game_tested"
    text = report.to_text()
    assert "Capability stage: export_candidate" in text
    assert "Game ready: False" in text
    assert "Game-ready blockers:" in text
    assert "Game tested: False" in text
    assert "1. Load as player character without crash" in text
    assert "12. Loading in both KOTOR 1 and KOTOR 2" in text


def test_character_builder_validation_report_downgrades_donor_weights_without_landmarks() -> None:
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.donor_skin_binding_landmarks_incomplete",
                    message="Donor transfer lacks landmark evidence.",
                )
            ],
        ),
        metadata={
            "character_builder_workflow": {
                "fit_report": _valid_fit_report(
                    used_landmarks=[
                        "source:pelvis=Hips",
                        "target:pelvis=pelvis_g",
                    ],
                ),
                "bind": {
                    "skin_binding": {
                        "weighting_method": "native_template_nearest_vertex_donor",
                        "quality_stage": "donor_transfer_first_pass",
                        "donor_weight_transfer": True,
                        "mesh_reports": [{"mesh_name": "custom_body"}],
                    }
                },
                "rig_state": {
                    "state": "native_template_final",
                    "dag_authority": "native_kotor_base",
                },
                "native_snapshot": {
                    "model_name": "pmbam",
                    "game": "K1",
                    "dag_fingerprint": "a" * 64,
                },
            }
        },
    )

    data = report.to_dict()

    gates = data["character_builder_evidence_gates"]
    assert gates["fit"]["stage"] == "passed"
    assert gates["bind"]["stage"] == "passed"
    assert gates["weight"]["stage"] == "donor_transfer_landmarks_incomplete"
    assert gates["weight"]["warning_issue_codes"] == [
        "character.export.donor_skin_binding_landmarks_incomplete"
    ]
    assert "weight=donor_transfer_landmarks_incomplete" in report.to_text()


def test_character_builder_validation_report_records_mesh_payload_fit_landmarks() -> None:
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.auto_fit_source_landmarks_need_review",
                    message="Fit used mesh payload landmarks.",
                )
            ],
        ),
        metadata={
            "character_builder_workflow": {
                "fit_report": _valid_fit_report(
                    source_landmark_sources={
                        "head": "mesh_payload",
                        "left_foot": "mesh_payload",
                        "pelvis": "mesh_payload",
                        "right_foot": "mesh_payload",
                    },
                ),
                "bind": {
                    "skin_binding": {
                        "weighting_method": "native_template_nearest_vertex_donor",
                        "quality_stage": "donor_transfer_first_pass",
                        "donor_weight_transfer": True,
                        "mesh_reports": [{"mesh_name": "custom_body"}],
                    }
                },
                "rig_state": {
                    "state": "native_template_final",
                    "dag_authority": "native_kotor_base",
                },
                "native_snapshot": {
                    "model_name": "pmbam",
                    "game": "K1",
                    "dag_fingerprint": "a" * 64,
                },
            }
        },
    )

    data = report.to_dict()

    fit = data["character_builder_evidence_gates"]["fit"]
    assert fit["stage"] == "needs_review"
    assert fit["warning_issue_codes"] == [
        "character.export.auto_fit_source_landmarks_need_review"
    ]
    assert fit["source_landmark_domain"] == "mesh_payload_landmarks"
    assert fit["source_uses_imported_skeleton_landmarks"] is False
    assert fit["source_landmark_source_counts"] == {"mesh_payload": 4}
    assert fit["source_mesh_payload_landmark_roles"] == [
        "head",
        "left_foot",
        "pelvis",
        "right_foot",
    ]
    assert "fit=needs_review" in report.to_text()
    assert "Fit landmark sources: mesh_payload_landmarks (mesh_payload=4)" in report.to_text()


def test_character_builder_validation_report_records_missing_imported_guide_evidence() -> None:
    fit_report = _valid_fit_report()
    fit_report.pop("source_imported_armature", None)
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.auto_fit_imported_skeleton_guides_not_recorded",
                    message="Imported guide inventory missing.",
                )
            ],
        ),
        metadata={
            "character_builder_workflow": {
                "fit_report": fit_report,
                "bind": {
                    "skin_binding": {
                        "weighting_method": "native_template_nearest_vertex_donor",
                        "quality_stage": "donor_transfer_first_pass",
                        "donor_weight_transfer": True,
                        "mesh_reports": [{"mesh_name": "custom_body"}],
                    }
                },
                "rig_state": {
                    "state": "native_template_final",
                    "dag_authority": "native_kotor_base",
                },
                "native_snapshot": {
                    "model_name": "pmbam",
                    "game": "K1",
                    "dag_fingerprint": "a" * 64,
                },
            }
        },
    )

    fit = report.to_dict()["character_builder_evidence_gates"]["fit"]
    assert fit["stage"] == "needs_review"
    assert fit["source_uses_imported_skeleton_landmarks"] is True
    assert fit["source_imported_armature_guide_count"] == 0
    assert fit["warning_issue_codes"] == [
        "character.export.auto_fit_imported_skeleton_guides_not_recorded"
    ]


def test_character_builder_validation_report_records_paired_landmark_alignment_gate() -> None:
    fit_report = _valid_fit_report()
    fit_report["fit_transform"]["landmark_alignment"]["pair_count"] = 3
    fit_report["fit_transform"]["landmark_alignment"]["paired_roles"] = [
        "pelvis",
        "head",
        "left",
    ]
    fit_report["fit_transform"]["landmark_alignment"]["rms_error"] = 0.42
    fit_report["fit_transform"]["landmark_alignment"]["max_error"] = 0.55
    fit_report["fit_transform"]["landmark_alignment"]["worst_pair_role"] = "left"
    fit_report["fit_transform"]["landmark_alignment"]["translation_basis"] = (
        "ground_snapped_native_fit_origin"
    )
    fit_report["fit_transform"]["landmark_alignment"]["error_basis"] = (
        "applied_fit_transform"
    )
    fit_report["fit_transform"]["landmark_alignment"]["pair_errors"] = [
        {
            "role": "left",
            "source_position": [-0.5, 0.0, 1.2],
            "target_position": [-0.4, 0.0, 0.96],
            "mapped_position": [-0.2, 0.0, 0.9],
            "error": 0.42,
        },
    ]
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.auto_fit_paired_landmarks_need_review",
                    message="Paired landmark fit needs review.",
                )
            ],
        ),
        metadata={
            "character_builder_workflow": {
                "fit_report": fit_report,
                "bind": {
                    "skin_binding": {
                        "weighting_method": "native_template_nearest_vertex_donor",
                        "quality_stage": "donor_transfer_first_pass",
                        "donor_weight_transfer": True,
                        "mesh_reports": [{"mesh_name": "custom_body"}],
                    }
                },
                "rig_state": {
                    "state": "native_template_final",
                    "dag_authority": "native_kotor_base",
                },
                "native_snapshot": {
                    "model_name": "pmbam",
                    "game": "K1",
                    "dag_fingerprint": "a" * 64,
                },
            }
        },
    )

    data = report.to_dict()

    fit = data["character_builder_evidence_gates"]["fit"]
    paired = fit["paired_landmark_alignment"]
    assert fit["stage"] == "needs_review"
    assert fit["warning_issue_codes"] == [
        "character.export.auto_fit_paired_landmarks_need_review"
    ]
    assert paired["present"] is True
    assert paired["pair_count"] == 3
    assert paired["paired_roles"] == ["pelvis", "head", "left"]
    assert paired["rms_error"] == 0.42
    assert paired["worst_pair_role"] == "left"
    assert paired["translation_basis"] == "ground_snapped_native_fit_origin"
    assert paired["error_basis"] == "applied_fit_transform"
    assert paired["height_scale"] == 0.8
    assert paired["height_scale_basis"] == "bone_landmark_height"
    assert paired["solved_scale"] == 0.79
    assert paired["applied_scale"] == 0.8
    assert paired["applied_scale_basis"] == "bone_landmark_height"
    assert paired["pair_errors"][0]["role"] == "left"
    assert paired["pair_errors"][0]["error"] == 0.42
    quality = fit["quality_summary"]
    assert quality["stage"] == "needs_review"
    assert "too_few_paired_landmarks" in quality["reasons"]
    assert "rms_error_high" in quality["reasons"]
    assert "max_error_high" in quality["reasons"]
    assert "Skeleton-driven Auto-Fit needs review" in quality["summary"]
    assert "Fit quality: Skeleton-driven Auto-Fit needs review" in report.to_text()
    assert "Fit paired landmarks: 3 pairs, rms=0.42" in report.to_text()
    assert "worst=left" in report.to_text()
    assert "scale height=0.8 / solved=0.79 / applied=0.8 (bone_landmark_height)" in (
        report.to_text()
    )


def test_character_builder_validation_report_records_toe_forward_gate() -> None:
    fit_report = _valid_fit_report()
    fit_report["source_frame"]["landmarks"].update({
        "left_toe": "LeftToeBase",
        "right_toe": "RightToeBase",
    })
    fit_report["source_frame"]["toe_forward_alignment"] = -0.2
    fit_report["target_frame"]["landmarks"].update({
        "left_toe": "lfootT_g",
        "right_toe": "rfootT_g",
    })
    fit_report["target_frame"]["toe_forward_alignment"] = 0.91

    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(
            source="test.preflight",
            issues=[
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    subsystem=ValidationSubsystem.CHARACTER,
                    code="character.export.auto_fit_toe_forward_needs_review",
                    message="Toe-forward fit needs review.",
                )
            ],
        ),
        metadata={
            "character_builder_workflow": {
                "fit_report": fit_report,
                "bind": {
                    "skin_binding": {
                        "weighting_method": "native_template_nearest_vertex_donor",
                        "quality_stage": "donor_transfer_first_pass",
                        "donor_weight_transfer": True,
                        "mesh_reports": [{"mesh_name": "custom_body"}],
                    }
                },
                "rig_state": {
                    "state": "native_template_final",
                    "dag_authority": "native_kotor_base",
                },
                "native_snapshot": {
                    "model_name": "pmbam",
                    "game": "K1",
                    "dag_fingerprint": "a" * 64,
                },
            }
        },
    )

    fit = report.to_dict()["character_builder_evidence_gates"]["fit"]
    assert fit["stage"] == "needs_review"
    assert fit["warning_issue_codes"] == [
        "character.export.auto_fit_toe_forward_needs_review"
    ]
    toe = fit["toe_forward_alignment"]
    assert toe["source"]["has_toe_landmarks"] is True
    assert toe["source"]["toe_forward_alignment"] == -0.2
    assert toe["source"]["landmarks"]["left_toe"] == "LeftToeBase"
    assert toe["target"]["has_toe_landmarks"] is True
    assert toe["target"]["toe_forward_alignment"] == 0.91
    assert toe["target"]["landmarks"]["right_toe"] == "rfootT_g"
    assert "Fit toe-forward: source=-0.200, target=0.910" in report.to_text()


def test_character_builder_validation_report_records_engine_evidence_gate() -> None:
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

    engine = data["character_builder_evidence_gates"]["engine"]
    assert engine["stage"] == "partial_reverse_engineering"
    assert engine["findings_doc"] == "docs/ghidra_findings.md"
    assert engine["pending_ghidra_count"] >= 1
    assert "mdl_loader_function_addresses" in engine["pending_ghidra"]
    assert engine["warning_issue_codes"] == [
        "character.export.engine_reverse_engineering_pending"
    ]
    assert "engine=partial_reverse_engineering" in report.to_text()
    assert "Engine evidence: fixture_verified_function_addresses_pending" in report.to_text()


def test_character_builder_validation_report_requires_complete_game_test_evidence() -> None:
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(source="test.preflight"),
        game_tested=True,
    )

    data = report.to_dict()

    assert data["capability"]["stage"] == "export_candidate"
    assert data["capability"]["game_tested"] is False
    assert data["capability"]["game_test_requested"] is True
    assert data["capability"]["game_test_evidence_complete"] is False
    assert data["capability"]["game_test_status"] == "game_test_evidence_incomplete"


def test_character_builder_game_test_evidence_requires_per_game_checklists() -> None:
    legacy_global_only_evidence = {
        "schema": CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA,
        "status": "passed",
        "tested_games": ["K1", "K2"],
        "checklist_results": {
            item: True for item in CHARACTER_BUILDER_MANUAL_CHECKLIST
        },
    }

    assert character_game_test_evidence_passed(legacy_global_only_evidence) is False
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        preflight_report=ValidationReport(source="test.preflight"),
        game_tested=True,
        game_test_evidence=legacy_global_only_evidence,
    )

    data = report.to_dict()

    assert data["capability"]["stage"] == "export_candidate"
    assert data["capability"]["game_tested"] is False
    assert data["capability"]["game_test_evidence_complete"] is False
    assert data["game_test_evidence_missing"]["missing_per_game_checklists"] == [
        "K1",
        "K2",
    ]
    text = report.to_text()
    assert "Game-test evidence gaps:" in text
    assert "missing_per_game_checklists=[K1, K2]" in text


def test_character_builder_validation_report_promotes_complete_k1_k2_game_test_evidence() -> None:
    output_hashes = _test_output_hashes()
    evidence = build_character_game_test_evidence(
        tested_games=["K1", "K2"],
        checklist_results={item: True for item in CHARACTER_BUILDER_MANUAL_CHECKLIST},
        tested_output_hashes=output_hashes,
        tester="manual qa",
        notes="Bendak replacement smoke passed.",
        artifacts=["k1_screenshot.png", "k2_screenshot.png"],
    )
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        output_hashes=output_hashes,
        preflight_report=ValidationReport(source="test.preflight"),
        game_tested=True,
        game_test_evidence=evidence,
    )

    data = report.to_dict()

    assert data["capability"]["stage"] == "game_tested"
    assert data["capability"]["game_tested"] is True
    assert data["capability"]["game_ready"] is False
    assert "fit=missing" in data["capability"]["game_ready_blockers"]
    assert "engine=partial_reverse_engineering" in data["capability"]["game_ready_blockers"]
    assert data["capability"]["game_test_status"] == "manual_checklist_passed"
    assert data["game_test_evidence"]["tested_games"] == ["K1", "K2"]
    assert data["game_test_evidence"]["checklist_results"][
        "Load as player character without crash"
    ] is True
    assert data["game_test_evidence"]["per_game_checklist_results"]["K1"][
        "Load as player character without crash"
    ] is True
    assert data["game_test_evidence"]["per_game_checklist_results"]["K2"][
        "Loading in both KOTOR 1 and KOTOR 2"
    ] is True
    assert data["game_test_evidence"]["tested_output_hashes"] == output_hashes
    assert data["output_hashes"] == output_hashes
    assert data["game_test_evidence_missing"] == {}


def test_character_builder_validation_report_marks_game_ready_only_when_all_gates_pass(
    monkeypatch,
) -> None:
    output_hashes = _test_output_hashes()
    evidence = build_character_game_test_evidence(
        tested_games=["K1", "K2"],
        checklist_results={item: True for item in CHARACTER_BUILDER_MANUAL_CHECKLIST},
        tested_output_hashes=output_hashes,
        tester="manual qa",
    )
    engine_evidence = copy.deepcopy(cv_report.CHARACTER_EXPORT_EVIDENCE)
    engine_evidence["pending_ghidra"] = ()
    monkeypatch.setattr(cv_report, "CHARACTER_EXPORT_EVIDENCE", engine_evidence)
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        output_hashes=output_hashes,
        preflight_report=ValidationReport(source="test.preflight"),
        metadata={"character_builder_workflow": _game_ready_workflow()},
        game_tested=True,
        game_test_evidence=evidence,
    )

    data = report.to_dict()

    assert data["capability"]["stage"] == "game_tested"
    assert data["capability"]["game_tested"] is True
    assert data["capability"]["game_ready"] is True
    assert data["capability"]["game_ready_blockers"] == []
    assert data["capability"]["game_ready_actual_gate_stages"] == {
        "fit": "passed",
        "bind": "passed",
        "weight": "trusted_donor_transfer",
        "animation": "passed",
        "material": "passed",
        "engine": "passed",
    }
    text = report.to_text()
    assert "Game ready: True" in text
    assert "Game-ready blockers:" not in text


def test_character_builder_validation_report_blocks_game_test_hash_mismatch() -> None:
    output_hashes = _test_output_hashes()
    tested_hashes = copy.deepcopy(output_hashes)
    tested_hashes["mdl"]["sha256"] = "0" * 64
    evidence = build_character_game_test_evidence(
        tested_games=["K1", "K2"],
        checklist_results={item: True for item in CHARACTER_BUILDER_MANUAL_CHECKLIST},
        tested_output_hashes=tested_hashes,
        tester="manual qa",
    )
    report = CharacterBuilderValidationReport(
        status="verified",
        verified=True,
        job_id="character_grbody",
        export_kind="character_mdl_mdx",
        game="K1",
        resref="grbody",
        outputs={"mdl": "grbody.mdl", "mdx": "grbody.mdx"},
        output_hashes=output_hashes,
        preflight_report=ValidationReport(source="test.preflight"),
        game_tested=True,
        game_test_evidence=evidence,
    )

    data = report.to_dict()

    assert data["capability"]["stage"] == "export_candidate"
    assert data["capability"]["game_tested"] is False
    mismatch = data["game_test_evidence_missing"]["mismatched_tested_output_hashes"]["mdl"]
    assert mismatch["expected"] == output_hashes["mdl"]
    assert mismatch["actual"] == tested_hashes["mdl"]


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
    result["model"].metadata["kotor_fit_report"] = _valid_fit_report()
    result["model"].metadata["kotor_normalization"] = {
        "fit_policy": "bone_landmark_basis",
        "scale": 0.8,
        "scale_basis": "bone_landmark_height",
        "fit_transform": result["model"].metadata["kotor_fit_report"]["fit_transform"],
    }
    _stamp_animation_library_evidence(result["model"])
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
    assert (
        "Evidence gates: fit=passed, bind=passed, "
        "weight=fallback_first_pass, animation=passed"
    ) in (
        text_path.read_text(encoding="utf-8")
    )
    assert "material=needs_review" in text_path.read_text(encoding="utf-8")
    assert "engine=partial_reverse_engineering" in text_path.read_text(encoding="utf-8")
    assert "Fit landmark sources: skeleton_landmarks (imported_skeleton=6)" in (
        text_path.read_text(encoding="utf-8")
    )
    assert "Engine evidence: fixture_verified_function_addresses_pending" in (
        text_path.read_text(encoding="utf-8")
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "ghostrigger.character_export_validation.v1"
    assert payload["verified"] is True
    assert payload["status"] == "verified"
    assert payload["capability"]["stage"] == "export_candidate"
    assert payload["capability"]["game_tested"] is False
    assert payload["capability"]["game_test_status"] == "not_game_tested"
    assert payload["output_hashes"]["mdl"] == {
        "sha256": hashlib.sha256(b"mdl").hexdigest(),
        "size": 3,
    }
    assert payload["output_hashes"]["mdx"] == {
        "sha256": hashlib.sha256(b"mdx").hexdigest(),
        "size": 3,
    }
    assert payload["engine_evidence"]["findings_doc"] == "docs/ghidra_findings.md"
    assert len(payload["manual_in_game_checklist"]) == 12
    workflow = payload["metadata"]["character_builder_workflow"]
    assert workflow["native_skeleton_is_authority"] is True
    assert workflow["imported_mesh_role"] == "payload_guest"
    assert workflow["final_dag_source"] == "selected_kotor_base"
    gates = payload["character_builder_evidence_gates"]
    assert gates["schema"]["name"] == "ghostrigger.character_builder_evidence_gates.v1"
    assert gates["fit"]["stage"] == "passed"
    assert gates["fit"]["policy"] == "bone_landmark_basis"
    assert gates["fit"]["confidence"] == 0.95
    assert gates["fit"]["source_landmark_domain"] == "skeleton_landmarks"
    assert gates["fit"]["source_uses_imported_skeleton_landmarks"] is True
    assert gates["fit"]["source_landmark_source_counts"] == {"imported_skeleton": 6}
    assert gates["fit"]["source_imported_armature_guide_count"] == 6
    assert gates["fit"]["source_imported_armature_scene_guide_count"] == 6
    assert gates["fit"]["source_imported_armature_names"] == ["Armature"]
    assert gates["fit"]["source_skeleton_landmark_roles"] == [
        "head",
        "left",
        "left_foot",
        "pelvis",
        "right",
        "right_foot",
    ]
    assert gates["bind"]["stage"] == "passed"
    assert gates["bind"]["rig_state"] == "native_template_final"
    assert gates["bind"]["dag_authority"] == "native_kotor_base"
    assert gates["weight"]["stage"] == "fallback_first_pass"
    assert gates["weight"]["weighting_method"] == "nearest_kotor_bone_segment"
    assert gates["weight"]["donor_weight_transfer"] is False
    assert gates["weight"]["warning_issue_codes"] == [
        "character.export.fallback_skin_binding"
    ]
    assert gates["animation"]["stage"] == "passed"
    assert gates["animation"]["motion_source"] == "inherited_supermodel"
    assert gates["animation"]["assigned_supermodel"] == "S_KPMF0200"
    assert gates["animation"]["available_count"] == 267
    assert gates["animation"]["required_preview_missing"] == []
    assert gates["material"]["stage"] == "needs_review"
    assert gates["material"]["warning_issue_codes"] == [
        "character.export.payload_texture_missing",
        "character.export.payload_uvs_missing",
    ]
    assert gates["engine"]["stage"] == "partial_reverse_engineering"
    assert gates["engine"]["pending_ghidra_count"] >= 1
    assert "mdl_loader_function_addresses" in gates["engine"]["pending_ghidra"]
    assert workflow["rig_state"]["state"] == "native_template_final"
    assert workflow["rig_state"]["native_base_resref"] == "pmbam"
    assert workflow["rig_state"]["native_base_model_name"] == "pmbam"
    assert workflow["rig_state"]["native_base_game"] == "K1"
    assert workflow["rig_state"]["imported_payload_name"] == "grbody"
    assert workflow["rig_state"]["payload_mesh_names"] == ["custom_body"]
    assert workflow["bind"]["status"] == "bound_to_native_kotor_skeleton"
    assert workflow["bind"]["native_base"]["source_resref"] == "pmbam"
    assert workflow["bind"]["native_base"]["dag_authority"] == "native_kotor_base"
    assert workflow["bind"]["skin_binding"]["weighting_method"] == "nearest_kotor_bone_segment"
    assert workflow["bind"]["skin_binding"]["quality_stage"] == "fallback_first_pass"
    assert workflow["bind"]["skin_binding"]["donor_weight_transfer"] is False
    assert workflow["bind"]["skin_binding"]["mesh_reports"][0]["mesh_name"] == "custom_body"
    assert workflow["bind"]["skin_binding"]["mesh_reports"][0]["weighted_vertices"] == 3
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
    assert workflow["motion_assignment"]["source"] == "inherited_supermodel"
    assert workflow["animation_library"]["effective_supermodel"] == "S_KPMF0200"
    assert workflow["animation_library"]["available_count"] == 267
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
    reload_dag = reload_issues["character.export.reload_native_dag_verified"]
    assert reload_dag["details"]["native_snapshot"]["dag_fingerprint"] == expected_fingerprint
    assert reload_dag["details"]["native_snapshot"]["dag_fingerprint_algorithm"] == "sha256"
    assert reload_dag["details"]["checked_path_count"] >= 3
    assert ["PMBAM", "cutscenedummy"] in reload_dag["details"]["checked_paths"]
    assert ["PMBAM", "cutscenedummy", "rootdummy", "torso_g", "torsoUpr_g", "headhook"] in reload_dag["details"]["checked_paths"]
    reload_payload = reload_issues["character.export.reload_payload_verified"]
    assert reload_payload["details"]["payload_names"] == ["custom_body"]
    assert reload_payload["details"]["checked_payload_count"] == 1
    assert reload_payload["details"]["payloads"][0]["name"] == "custom_body"
    assert reload_payload["details"]["payloads"][0]["vertices"] == 3
    assert reload_payload["details"]["payloads"][0]["skin_rows"] == 3
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
    assert "Animation library: 267 clip(s)" in text
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


def test_character_export_transaction_blocks_reloaded_native_dag_loss(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    reloaded_model = copy.deepcopy(result["model"])
    _detach_node(reloaded_model, "headhook")
    output = tmp_path / "grbody_reload_lost_hook.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: reloaded_model,
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    codes = {issue.code for issue in tx.export_job_result.validation_report.issues}
    assert "character.export.reload_node_path_missing" in codes
    issue = next(
        issue for issue in tx.export_job_result.validation_report.issues
        if issue.code == "character.export.reload_node_path_missing"
    )
    assert issue.navigation.node_name == "headhook"
    assert issue.details["expected_path"] == [
        "PMBAM",
        "cutscenedummy",
        "rootdummy",
        "torso_g",
        "torsoUpr_g",
        "headhook",
    ]
    assert issue.details["native_snapshot"]["dag_fingerprint"] == (
        native_skeleton_fingerprint(result["native_skeleton_snapshot"])
    )


def test_character_export_transaction_blocks_reloaded_payload_skin_row_loss(tmp_path) -> None:
    _FakeCharacterWriter.calls = []
    result = _rigged_character()
    reloaded_model = copy.deepcopy(result["model"])
    payload = _find_model_node(reloaded_model, "custom_body")
    payload.skin_data = list(payload.skin_data)[:-1]
    output = tmp_path / "grbody_reload_payload_loss.mdl"

    tx = export_character_mdl_mdx_transaction(
        CharacterBuilderExportTransactionRequest(
            model=result["model"],
            output_mdl_path=output,
            native_snapshot=result["native_skeleton_snapshot"],
            writer_cls=_FakeCharacterWriter,
            loader=lambda _mdl, _mdx: reloaded_model,
        )
    )

    assert tx.succeeded is False
    assert _FakeCharacterWriter.calls
    assert not output.exists()
    assert not output.with_suffix(".mdx").exists()
    issue = next(
        issue for issue in tx.export_job_result.validation_report.issues
        if issue.code == "character.export.reload_payload_skin_rows_changed"
    )
    assert issue.navigation.node_name == "custom_body"
    assert issue.details["payload_name"] == "custom_body"
    assert issue.details["field"] == "skin_rows"
    assert issue.details["expected"] == 3
    assert issue.details["actual"] == 2


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
