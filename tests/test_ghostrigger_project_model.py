import json
from pathlib import Path

import pytest

from src.core.project import (
    CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION,
    ExportCandidateRef,
    GameInstallRef,
    GhostRiggerProject,
    MapProjectRef,
    ModuleWorkspaceRef,
    ProjectAssetRef,
    ResourceAddress,
    RetargetJobRef,
    ScenarioPackageRef,
    ValidationSnapshotRef,
    load_ghostrigger_project,
    save_ghostrigger_project,
    validate_ghostrigger_project,
    validate_resource_address,
)
from src.core.project.placeable_asset import (
    PlaceableAppearanceMappingEvidence,
    PlaceableAsset,
    PlaceableBaseTemplateEvidence,
    PlaceableGameplay,
    PlaceableResourceRefs,
    load_placeable_asset,
    save_placeable_asset,
    validate_placeable_asset,
)


def _module_resource(resref: str = "gr_beklead", restype: str = "UTC") -> ResourceAddress:
    return ResourceAddress(
        scheme="module_resource",
        game="k1",
        module_id="tar_m09aa",
        layer="project",
        resref=resref,
        restype=restype,
    )


def _local_file(path: str = "C:/imports/custom_mesh.fbx") -> ResourceAddress:
    return ResourceAddress(scheme="local_file", path=path)


def test_placeable_asset_json_roundtrip_preserves_editable_contract(tmp_path: Path) -> None:
    base = ResourceAddress(scheme="game_resource", game="k2", resref="plc_bench", restype="UTP", layer="base")
    mdl = ResourceAddress(scheme="project_resource", game="k2", resref="gr_console", restype="MDL", path="models/gr_console.mdl")
    asset = PlaceableAsset(
        game="K2",
        template_resref="gr_console",
        tag="gr_console",
        display_name="Ghost Console",
        description="Reusable terminal",
        category="terminal",
        visual_source="custom",
        appearance_id=321,
        gameplay=PlaceableGameplay(
            static=False,
            useable=True,
            has_inventory=True,
            inventory_items=["g_i_datapad01"],
            lockable=True,
            locked=True,
            unlock_dc=25,
            maximum_hp=40,
            current_hp=35,
            conversation_resref="gr_console_dlg",
        ),
        scripts={"on_used": "gr_console_use", "on_open": "gr_console_open"},
        resources=PlaceableResourceRefs(
            mdl=mdl,
            mdx=ResourceAddress(scheme="project_resource", game="k2", resref="gr_console", restype="MDX", path="models/gr_console.mdx"),
            pwk=ResourceAddress(scheme="project_resource", game="k2", resref="gr_console", restype="PWK", path="models/gr_console.pwk"),
            textures=[ResourceAddress(scheme="project_resource", game="k2", resref="gr_console01", restype="TPC", path="textures/gr_console01.tpc")],
        ),
        base_template=base,
        base_evidence=PlaceableBaseTemplateEvidence(template=base, sha256="a" * 64, field_count=55, source="templates.bif"),
        appearance_evidence=PlaceableAppearanceMappingEvidence(
            game="K2",
            appearance_id=321,
            model_resref="gr_console",
            source="placeables.2da",
            source_sha256="b" * 64,
            verified=True,
        ),
    )

    path = save_placeable_asset(asset, tmp_path / "gr_console.ghostplaceable.json")
    restored = load_placeable_asset(path)

    assert restored.to_dict() == asset.to_dict()
    assert restored.asset_id == asset.asset_id
    assert restored.gameplay.inventory_items == ["g_i_datapad01"]
    validation = validate_placeable_asset(restored)
    assert validation.document_valid is True
    assert validation.utp_export_ready is True
    assert validation.structural_evidence_ready is True
    assert validation.engine_ready is False
    assert "bytes" not in path.read_text(encoding="utf-8").lower()
    assert list(tmp_path.glob(".*.tmp")) == []


def test_placeable_asset_validation_rejects_unsafe_gameplay_and_visual_contract() -> None:
    asset = PlaceableAsset(
        asset_id="unstable",
        game="K3",
        template_resref="bad/template/that/is/too/long",
        tag="",
        category="vehicle",
        visual_source="custom",
        appearance_id=None,
        gameplay=PlaceableGameplay(locked=True, lockable=False, key_required=True, inventory_items=["bad/item"]),
        scripts={"not_a_hook": "bad/script"},
    )

    validation = validate_placeable_asset(asset)
    codes = {issue.code for issue in validation.issues if issue.severity == "blocking"}

    assert validation.document_valid is False
    assert validation.utp_export_ready is False
    assert validation.engine_ready is False
    assert {
        "invalid_placeable_asset_id",
        "invalid_placeable_game",
        "invalid_placeable_resref",
        "missing_placeable_tag",
        "invalid_placeable_category",
        "missing_placeable_appearance",
        "locked_not_lockable",
        "invalid_placeable_key",
        "inventory_flag_missing",
        "unknown_placeable_script_hook",
        "custom_placeable_model_pair_missing",
    } <= codes


def test_project_json_roundtrip_across_studios(tmp_path: Path) -> None:
    project = GhostRiggerProject(
        schema_version=CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION,
        project_id="project_test",
        name="Taris Expansion",
        created_at_utc="2026-05-22T00:00:00Z",
        updated_at_utc="2026-05-22T00:00:00Z",
        game_install_refs=[
            GameInstallRef(id="k1_steam", game="k1", root_path="C:/Games/swkotor", label="K1 Steam")
        ],
        imported_assets=[
            ProjectAssetRef(
                id="mesh_001",
                kind="mesh",
                address=_local_file(),
                label="Imported body mesh",
                metadata={"source": "artist"},
            )
        ],
        retarget_jobs=[
            RetargetJobRef(
                id="retarget_001",
                mode="unreal_to_kotor",
                source=ResourceAddress(scheme="local_file", path="C:/imports/idle.fbx"),
                target=ResourceAddress(scheme="game_resource", game="k1", layer="base", resref="pmbam", restype="MDL"),
                profile=ResourceAddress(scheme="retarget_profile", path="profiles/ue_to_pmbam.json"),
                output_animation_name="gr_spin_attack_01",
                output_name_mode="custom_patch",
                requires_custom_animation_patch=True,
                metadata={"approved_in_viewport": True},
            )
        ],
        module_workspaces=[
            ModuleWorkspaceRef(
                id="module_001",
                module_id="tar_m09aa",
                game="k1",
                base_module=ResourceAddress(
                    scheme="module_resource",
                    game="k1",
                    module_id="tar_m09aa",
                    layer="base",
                    resref="tar_m09aa",
                    restype="MOD",
                ),
                edited_resources=[_module_resource()],
            )
        ],
        map_projects=[
            MapProjectRef(
                id="map_001",
                module_id="tar_m09aa",
                kmap_address=ResourceAddress(scheme="local_file", path="maps/taris_expansion.kmap"),
                kmax_scene_address=ResourceAddress(scheme="local_file", path="maps/taris_expansion.kmax"),
            )
        ],
        scenario_packages=[
            ScenarioPackageRef(
                id="scenario_001",
                module_ids=["tar_m09aa"],
                actors=[_module_resource("gr_beklead", "UTC")],
                scripts=[_module_resource("gr_bek_join", "NCS")],
                dialogs=[_module_resource("gr_beklead", "DLG")],
                sequences=[ResourceAddress(scheme="kmap_object", object_id="sequence_bek_reinforcement")],
            )
        ],
        validation_snapshots=[
            ValidationSnapshotRef(
                id="validation_001",
                address=ResourceAddress(scheme="project_resource", path="validation/last_report.json"),
                issue_count=1,
            )
        ],
        export_candidates=[
            ExportCandidateRef(
                id="export_001",
                kind="mdl_mdx",
                outputs=[
                    ResourceAddress(scheme="generated_output", game="k1", resref="pmbam", restype="MDL", path="out/pmbam.mdl"),
                    ResourceAddress(scheme="generated_output", game="k1", resref="pmbam", restype="MDX", path="out/pmbam.mdx"),
                ],
                manifest=ResourceAddress(scheme="generated_output", path="out/pmbam.retarget_preview.json"),
                verified=True,
                validation_snapshot=ResourceAddress(scheme="project_resource", path="validation/last_report.json"),
            )
        ],
        metadata={"campaign": "Hidden Bek reinforcements"},
    )

    path = tmp_path / "taris.ghostrigger.json"
    save_ghostrigger_project(project, path)
    loaded = load_ghostrigger_project(path)

    assert loaded.to_dict() == project.to_dict()
    assert loaded.metadata["campaign"] == "Hidden Bek reinforcements"
    assert loaded.schema_version == CURRENT_GHOSTRIGGER_PROJECT_SCHEMA_VERSION
    assert not validate_ghostrigger_project(loaded).has_blocking


def test_resource_address_stable_key_is_deterministic() -> None:
    first = _module_resource()
    second = ResourceAddress(
        scheme="module_resource",
        game="K1",
        module_id="TAR_M09AA",
        layer="project",
        resref="gr_beklead",
        restype=".utc",
    )

    assert first.stable_key() == second.stable_key()
    assert first.stable_key() == "module_resource:k1:tar_m09aa:project:UTC:gr_beklead"
    assert "gr_beklead.utc" in first.display_name()


@pytest.mark.parametrize(
    "address",
    [
        ResourceAddress(scheme="module_resource", game="k1", resref="foo", restype="UTC"),
        ResourceAddress(scheme="module_resource", game="k1", module_id="tar_m09aa", restype="UTC"),
        ResourceAddress(scheme="module_resource", game="k1", module_id="tar_m09aa", resref="foo"),
    ],
)
def test_module_resource_address_requires_module_resref_restype(address: ResourceAddress) -> None:
    issues = validate_resource_address(address)

    assert any(issue.severity == "blocking" for issue in issues)


@pytest.mark.parametrize("bad_resref", ["bad/name", "bad\\name", "bad name?", "this_resref_is_way_too_long", ""])
def test_invalid_kotor_resref_is_reported(bad_resref: str) -> None:
    address = _module_resource(bad_resref)
    issues = validate_resource_address(address)

    assert issues
    assert any("resref" in issue.code or "resref" in issue.message.lower() for issue in issues)


def test_local_file_address_requires_path() -> None:
    issues = validate_resource_address(ResourceAddress(scheme="local_file"))

    assert any(issue.code == "missing_path" for issue in issues)


def test_duplicate_project_object_ids_are_detected() -> None:
    project = GhostRiggerProject.new("Duplicate ids")
    project.imported_assets = [
        ProjectAssetRef(id="dup", kind="mesh", address=_local_file("a.fbx")),
        ProjectAssetRef(id="dup", kind="mesh", address=_local_file("b.fbx")),
    ]
    project.retarget_jobs = [
        RetargetJobRef(id="job", mode="unreal_to_kotor"),
        RetargetJobRef(id="job", mode="kotor_to_kotor"),
    ]
    project.module_workspaces = [
        ModuleWorkspaceRef(id="module", module_id="tar_m09aa", game="k1"),
        ModuleWorkspaceRef(id="module", module_id="danm13aa", game="k1"),
    ]
    project.export_candidates = [
        ExportCandidateRef(id="export", kind="mdl_mdx"),
        ExportCandidateRef(id="export", kind="module_mod"),
    ]

    report = validate_ghostrigger_project(project)

    duplicate_codes = [issue for issue in report.issues if issue.code == "duplicate_id"]
    assert len(duplicate_codes) == 4
    assert report.has_blocking


def test_raw_bytes_cannot_be_serialized_into_project_json(tmp_path: Path) -> None:
    project = GhostRiggerProject.new("No blobs")
    project.metadata["raw_mdl_bytes"] = b"not allowed"

    with pytest.raises(ValueError, match="non-JSON-serializable"):
        save_ghostrigger_project(project, tmp_path / "bad.ghostrigger.json")


def test_retarget_custom_patch_metadata_is_representable(tmp_path: Path) -> None:
    project = GhostRiggerProject.new("Custom animation patch")
    project.retarget_jobs.append(
        RetargetJobRef(
            id="retarget_custom",
            mode="unreal_to_kotor",
            output_animation_name="gr_spin_attack_01",
            output_name_mode="custom_patch",
            requires_custom_animation_patch=True,
        )
    )

    report = validate_ghostrigger_project(project)
    assert not report.has_blocking

    path = tmp_path / "custom_patch.ghostrigger.json"
    save_ghostrigger_project(project, path)
    loaded = load_ghostrigger_project(path)
    assert loaded.retarget_jobs[0].requires_custom_animation_patch is True
    assert loaded.retarget_jobs[0].output_animation_name == "gr_spin_attack_01"


def test_export_candidate_validation() -> None:
    project = GhostRiggerProject.new("Exports")
    project.export_candidates.append(ExportCandidateRef(id="bad_export", kind="mdl_mdx", verified=True))

    bad_report = validate_ghostrigger_project(project)
    assert any(issue.code == "verified_export_without_outputs" for issue in bad_report.issues)

    project.export_candidates = [
        ExportCandidateRef(
            id="good_export",
            kind="mdl_mdx",
            outputs=[
                ResourceAddress(scheme="generated_output", game="k1", resref="pmbam", restype="MDL", path="out/pmbam.mdl"),
                ResourceAddress(scheme="generated_output", game="k1", resref="pmbam", restype="MDX", path="out/pmbam.mdx"),
            ],
            manifest=ResourceAddress(scheme="generated_output", path="out/pmbam_manifest.json"),
            verified=True,
        )
    ]

    good_report = validate_ghostrigger_project(project)
    assert not good_report.has_blocking


def test_future_schema_version_fails_clearly(tmp_path: Path) -> None:
    path = tmp_path / "future.ghostrigger.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported GhostRigger project schema version 99"):
        load_ghostrigger_project(path)
