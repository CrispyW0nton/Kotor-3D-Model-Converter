from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Game/Python",
        "native/GhostRigger.Domain.Core.Scene/Python",
        "native/GhostRigger.Domain.Core.Walkmesh/Python",
        "native/GhostRigger.Domain.Core.Geometry/Python",
        "native/GhostRigger.Domain.Core.Camera/Python",
        "native/GhostRigger.Domain.Core.Math/Python",
        "native/GhostRigger.Domain.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _placements(area_resref: str = "grdev01"):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint

    return AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref=area_resref))


def _floor_plan_project():
    from src.core.modules.authored_module_project import create_floor_plan_room_project
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive

    return create_floor_plan_room_project(
        module_root="grdev01",
        game="K1",
        display_name="GhostRigger Dev Test",
        floor_plan=FloorPlanRoomPrimitive(
            room_resref="grdev01_room01",
            points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        ),
        placements=_placements(),
    )


def _runtime_keys():
    return (
        ("grdev01", "are"),
        ("grdev01", "git"),
        ("module", "ifo"),
        ("grdev01", "lyt"),
        ("grdev01", "vis"),
        ("grdev01_room01", "wok"),
        ("grdev01_room01", "mdl"),
        ("grdev01_room01", "mdx"),
    )


def test_t2639_readiness_blocks_invalid_authored_project_before_preview() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject
    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="bad module name"),
        rooms=(),
        placements=_placements(area_resref="missing"),
    )

    readiness = build_authored_module_readiness(project)

    assert readiness.capability_stage == "blocked"
    assert readiness.can_preview is False
    assert readiness.can_export_candidate is False
    assert readiness.preview_status == "Not ready"
    assert any("bad module name" in issue for issue in readiness.blocking_messages)
    assert any("requires at least one room" in issue for issue in readiness.blocking_messages)


def test_t2639_floor_plan_project_is_previewable_but_not_export_candidate_without_runtime_resources() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(_floor_plan_project())

    assert readiness.capability_stage == "previewable"
    assert readiness.can_preview is True
    assert readiness.can_export_candidate is False
    assert readiness.export_status == "Missing runtime resources"
    assert ("grdev01", "are") in readiness.missing_runtime_resources
    assert ("grdev01_room01", "mdl") in readiness.missing_runtime_resources
    assert readiness.rooms[0].can_preview_geometry is True
    assert readiness.rooms[0].walkable_face_count == 2


def test_t2639_runtime_resources_promote_project_to_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(_floor_plan_project(), packaged_resources=_runtime_keys())

    assert readiness.capability_stage == "export_candidate"
    assert readiness.can_preview is True
    assert readiness.can_export_candidate is True
    assert readiness.ready_for_game_test is True
    assert readiness.missing_runtime_resources == ()
    assert "warp grdev01" in readiness.next_action


def test_t2692_readiness_reports_full_map_studio_toolchain_scope() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    preview_only = build_authored_module_readiness(_floor_plan_project())
    export_candidate = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        proof_metadata={"proof_recording_script_path": "C:/tmp/grdev01_record_game_proof.cmd"},
    )

    preview_steps = {step.name: step for step in preview_only.toolchain}
    export_steps = {step.name: step for step in export_candidate.toolchain}

    assert set(preview_steps) == {
        "Geometry authoring",
        "Walkmesh",
        "Lighting",
        "Gameplay layout",
        "Runtime package",
        "In-game proof",
    }
    assert preview_steps["Geometry authoring"].ready is True
    assert "floor-plan extrusion" in preview_steps["Geometry authoring"].value_label
    assert "bevel" in preview_steps["Geometry authoring"].value_label
    assert "rectangular union" in preview_steps["Geometry authoring"].value_label
    assert preview_steps["Walkmesh"].ready is True
    assert preview_steps["Lighting"].ready is True
    assert preview_steps["Lighting"].status == "Optional"
    assert preview_steps["Gameplay layout"].ready is True
    assert preview_steps["Runtime package"].ready is False
    assert "ARE/GIT/IFO/PTH/LYT/VIS" in preview_steps["Runtime package"].fix_hint
    assert export_steps["Runtime package"].ready is True
    assert export_steps["In-game proof"].ready is False
    assert export_steps["In-game proof"].status == "Recorder ready after warp test"
    assert export_candidate.metadata["toolchain"][0]["name"] == "Geometry authoring"


def test_t2684_readiness_reports_staged_and_installed_game_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    staged = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        proof_metadata={
            "proof_manifest_path": "C:/tmp/grdev01_authored_module_game_manifest.json",
            "checklist_path": "C:/tmp/grdev01_authored_module_game_checklist.md",
        },
    )
    installed = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        proof_metadata={
            "proof_manifest_path": "C:/tmp/grdev01_authored_module_game_manifest.json",
            "installed_module_path": "C:/Games/KOTOR/Modules/grdev01.mod",
            "resolved_modules_dir": "C:/Games/KOTOR/Modules",
            "elevated_launch_script_path": "C:/tmp/grdev01_launch_kotor_as_admin.cmd",
            "proof_recording_script_path": "C:/tmp/grdev01_record_game_proof.cmd",
        },
    )

    assert staged.metadata["proof_status"] == "staged_for_game_test"
    assert staged.metadata["proof_manifest_path"].endswith("grdev01_authored_module_game_manifest.json")
    assert "Install/copy the staged package" in staged.next_action
    assert installed.metadata["proof_status"] == "installed_for_game_test"
    assert installed.metadata["installed_module_path"].endswith("grdev01.mod")
    assert installed.metadata["resolved_game_root_dir"].endswith("KOTOR")
    assert installed.metadata["launch_status"] == "ready_for_launch_helper"
    assert "launch_grdev01_smoke_test.py" in installed.metadata["launch_helper_command"]
    assert installed.metadata["elevated_launch_script_path"].endswith("grdev01_launch_kotor_as_admin.cmd")
    assert installed.metadata["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")
    assert "Run the launch helper dry-run" in installed.next_action


def test_t2639_game_tested_flag_is_only_honored_for_export_candidates() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    preview_only = build_authored_module_readiness(_floor_plan_project(), game_tested=True)
    proven = build_authored_module_readiness(_floor_plan_project(), packaged_resources=_runtime_keys(), game_tested=True)

    assert preview_only.capability_stage == "previewable"
    assert preview_only.game_tested is False
    assert proven.capability_stage == "game_tested"
    assert proven.game_tested is True
    assert proven.ready_for_game_test is False
