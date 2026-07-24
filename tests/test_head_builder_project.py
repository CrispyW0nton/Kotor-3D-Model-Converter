"""Focused contracts for the Custom Head Builder project state."""

from __future__ import annotations

import pytest

from src.core.characters.head_builder_project import (
    EvidenceLevel,
    EvidenceOutcome,
    EvidenceRecord,
    HEAD_BUILDER_PROJECT_EXTENSION,
    HEAD_BUILDER_PROJECT_SCHEMA,
    HeadBuilderGame,
    HeadBuilderProject,
    HeadBuilderStep,
    ResourceOrigin,
    ResourceProvenance,
    ResourceView,
    StepStatus,
)


def test_new_project_exposes_all_eleven_manual_workflow_steps() -> None:
    project = HeadBuilderProject.new(display_name="Ayla Head", game=HeadBuilderGame.K1)

    assert HEAD_BUILDER_PROJECT_EXTENSION == ".ghosthead.json"
    assert project.game is HeadBuilderGame.K1
    assert project.resource_view is ResourceView.STOCK_ONLY
    assert project.current_step is HeadBuilderStep.PROJECT_GAME
    assert len(project.workflow_steps) == 11
    assert project.workflow_steps[HeadBuilderStep.PROJECT_GAME].status is StepStatus.READY
    assert all(
        project.workflow_steps[step].status is StepStatus.NOT_STARTED
        for step in HeadBuilderStep
        if step is not HeadBuilderStep.PROJECT_GAME
    )


def test_project_roundtrip_preserves_provenance_contracts_and_unknown_metadata() -> None:
    project = HeadBuilderProject.new(display_name="Ayla Head")
    project.output_head_resref = "p_aylah"
    project.resource_view = ResourceView.STOCK_ONLY
    project.put_resource(
        ResourceProvenance(
            resource_id="donor-head",
            resource_type="kotor_mdl",
            resref="PFHA04",
            origin=ResourceOrigin.CHITIN_BIF,
            source_path="data/models.bif",
            container="models.bif",
            sha256="a" * 64,
            stock=True,
        )
    )
    project.donor_contract = {
        "geometry_root": "PFHA04",
        "attachment_target": "neck_g",
        "supermodel": "S_Female03",
        "local_node_count": 38,
        "inherited_node_declaration": 564,
        "retail_model_envelope": {
            "min": [-5.0, -5.0, -1.0],
            "max": [5.0, 5.0, 10.0],
            "radius": 7.0,
        },
    }
    project.skin_transfer = {
        "method": "nearest_triangle_barycentric",
        "maximum_distance": 0.05,
        "rigid_fallback_bone": "head_g",
        "preserve_palette_order": True,
        "preserve_inverse_bind_rows": True,
    }
    project.appearance_customization = {
        "schema": "ghostrigger.head_builder_component_recipe",
        "version": 1,
        "mode": "vanilla_components",
        "recipe_name": "Ayla stock mix",
        "selections": {
            "face": "PFHA01",
            "eyes": "PFHA02",
            "eyelashes": "PFHA03",
            "hair": "PFHA04",
        },
    }
    payload = project.to_dict()
    payload["future_contract"] = {"preserve_me": [1, 2, 3]}

    reopened = HeadBuilderProject.from_dict(payload)
    reopened_payload = reopened.to_dict()

    assert reopened_payload["schema"] == HEAD_BUILDER_PROJECT_SCHEMA
    assert reopened.output_head_resref == "p_aylah"
    assert reopened.resources["donor-head"].sha256 == "A" * 64
    assert reopened.donor_contract["attachment_target"] == "neck_g"
    assert reopened.skin_transfer["rigid_fallback_bone"] == "head_g"
    assert (
        reopened.appearance_customization["selections"]["eyes"]
        == "PFHA02"
    )
    assert reopened_payload["future_contract"] == {"preserve_me": [1, 2, 3]}


def test_version_one_project_opens_with_empty_customization_recipe() -> None:
    payload = HeadBuilderProject.new(display_name="Legacy head").to_dict()
    payload["version"] = 1
    payload.pop("appearance_customization")

    reopened = HeadBuilderProject.from_dict(payload)

    assert reopened.appearance_customization == {}
    assert reopened.to_dict()["version"] == 2


def test_retail_pass_requires_explicit_user_confirmation_and_observer_session() -> None:
    with pytest.raises(ValueError, match="explicit user confirmation"):
        EvidenceRecord(
            evidence_id="retail-1",
            check_id="retail_idle",
            label="Retail idle attachment",
            level=EvidenceLevel.RETAIL_OBSERVED,
            outcome=EvidenceOutcome.PASS,
            observer_session="20260723-retail-proof",
        )

    with pytest.raises(ValueError, match="observer session"):
        EvidenceRecord(
            evidence_id="retail-2",
            check_id="retail_idle",
            label="Retail idle attachment",
            level=EvidenceLevel.RETAIL_OBSERVED,
            outcome=EvidenceOutcome.PASS,
            confirmed_by_user=True,
        )

    accepted = EvidenceRecord(
        evidence_id="retail-3",
        check_id="retail_idle",
        label="Retail idle attachment",
        level=EvidenceLevel.RETAIL_OBSERVED,
        outcome=EvidenceOutcome.PASS,
        observer_session="20260723-retail-proof",
        confirmed_by_user=True,
    )
    assert accepted.outcome is EvidenceOutcome.PASS


def test_step_completion_can_reference_recorded_structural_evidence() -> None:
    project = HeadBuilderProject.new()
    project.record_evidence(
        EvidenceRecord(
            evidence_id="structural-preflight-1",
            check_id="modular_head_contract",
            label="Modular head binary contract",
            level=EvidenceLevel.STRUCTURAL,
            outcome=EvidenceOutcome.PASS,
            message="Geometry root and neck_g attachment target are distinct.",
        )
    )
    project.mark_step(
        HeadBuilderStep.BINARY_PREFLIGHT,
        StepStatus.COMPLETE,
        evidence_ids=["structural-preflight-1"],
    )

    progress = project.workflow_steps[HeadBuilderStep.BINARY_PREFLIGHT]
    assert progress.status is StepStatus.COMPLETE
    assert progress.completed_at
    assert progress.evidence_ids == ["structural-preflight-1"]

    with pytest.raises(ValueError, match="unknown evidence"):
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            StepStatus.COMPLETE,
            evidence_ids=["not-recorded"],
        )


def test_safe_retail_step_requires_referenced_user_observed_pass() -> None:
    project = HeadBuilderProject.new()
    project.record_evidence(
        EvidenceRecord(
            evidence_id="editor-preview-1",
            check_id="headhook_preview",
            label="Editor headhook preview",
            level=EvidenceLevel.EDITOR_VISUAL,
            outcome=EvidenceOutcome.PASS,
        )
    )

    with pytest.raises(ValueError, match="retail-observed passing evidence"):
        project.mark_step(
            HeadBuilderStep.SAFE_RETAIL_TEST,
            StepStatus.COMPLETE,
            evidence_ids=["editor-preview-1"],
        )

    project.record_evidence(
        EvidenceRecord(
            evidence_id="retail-proof-1",
            check_id="retail_acceptance",
            label="Retail head acceptance",
            level=EvidenceLevel.RETAIL_OBSERVED,
            outcome=EvidenceOutcome.PASS,
            observer_session="20260723-retail-proof",
            confirmed_by_user=True,
        )
    )
    project.mark_step(
        HeadBuilderStep.SAFE_RETAIL_TEST,
        StepStatus.COMPLETE,
        evidence_ids=["retail-proof-1"],
    )

    progress = project.workflow_steps[HeadBuilderStep.SAFE_RETAIL_TEST]
    assert progress.status is StepStatus.COMPLETE
    assert progress.evidence_ids == ["retail-proof-1"]


def test_project_contract_has_no_qt_or_filesystem_io_dependency() -> None:
    source = __import__(
        "src.core.characters.head_builder_project",
        fromlist=["__name__"],
    ).__loader__.get_source("src.core.characters.head_builder_project")

    assert "PySide6" not in source
    assert "src.gui" not in source
    assert "open(" not in source
    assert "Path(" not in source
