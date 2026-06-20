from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Domain.Core.Modules/Python",
        "native/GhostRigger.Domain.Core.Level/Python",
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


def _floor_plan_project():
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
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
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grdev01")),
    )


def _runtime_keys():
    return (
        ("grdev01", "are"),
        ("grdev01", "git"),
        ("module", "ifo"),
        ("grdev01", "pth"),
        ("grdev01", "lyt"),
        ("grdev01", "vis"),
        ("grdev01_room01", "wok"),
        ("grdev01_room01", "mdl"),
        ("grdev01_room01", "mdx"),
    )


def test_t2600_missing_authored_module_becomes_actionable_validation_issue() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    issues = authored_module_readiness_validation_issues(
        None,
        bridge_warnings=("No authored Map Studio module section is stored in this KMAP yet.",),
    )

    assert len(issues) == 1
    assert issues[0].severity == "Warning"
    assert issues[0].code == "MAP_STUDIO_AUTHORED_MODULE_MISSING"
    assert "Map Studio Builder" in issues[0].suggested_fix


def test_t2600_previewable_project_surfaces_missing_runtime_resources_as_validation_rows() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    readiness = build_authored_module_readiness(_floor_plan_project())
    issues = authored_module_readiness_validation_issues(readiness)
    codes = [issue.code for issue in issues]
    messages = [issue.message for issue in issues]

    assert "MAP_STUDIO_RUNTIME_RESOURCE_MISSING" in codes
    assert "MAP_STUDIO_TOOLCHAIN_NOT_READY" in codes
    assert any("grdev01.are" in message for message in messages)
    assert any("Runtime package" in message for message in messages)
    assert all(issue.suggested_fix for issue in issues)


def test_t2600_export_candidate_requires_game_proof_in_validation_rows() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    readiness = build_authored_module_readiness(_floor_plan_project(), packaged_resources=_runtime_keys())
    issues = authored_module_readiness_validation_issues(readiness)

    assert readiness.can_export_candidate is True
    assert any(issue.code == "MAP_STUDIO_GAME_PROOF_REQUIRED" for issue in issues)
    assert any("warp" in issue.suggested_fix for issue in issues)


def test_t2911_floor_plan_geometry_readiness_projects_actionable_validation_rows() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive

    project = _floor_plan_project()
    bad_room = replace(
        project.rooms[0],
        primitive=FloorPlanRoomPrimitive(
            room_resref="grdev01_room01",
            points=((-3.0, -2.0), (3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        ),
    )
    readiness = build_authored_module_readiness(replace(project, rooms=(bad_room,)))
    issues = authored_module_readiness_validation_issues(readiness)
    floor_plan_issues = [issue for issue in issues if issue.code == "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_BLOCKER"]

    assert readiness.geometry_validation.ready is False
    assert len(floor_plan_issues) == 1
    assert "duplicate points or zero-length edges" in floor_plan_issues[0].message
    assert "Cleanup Footprint" in floor_plan_issues[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_BLOCKER"
        and "duplicate points or zero-length edges" in issue.message
        for issue in issues
    )


def test_t2911_floor_plan_geometry_warnings_project_specific_validation_rows() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive

    project = _floor_plan_project()
    clockwise_room = replace(
        project.rooms[0],
        primitive=FloorPlanRoomPrimitive(
            room_resref="grdev01_room01",
            points=((-3.0, -2.0), (-3.0, 2.0), (3.0, 2.0), (3.0, -2.0)),
        ),
    )
    readiness = build_authored_module_readiness(replace(project, rooms=(clockwise_room,)))
    issues = authored_module_readiness_validation_issues(readiness)
    warning_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_WARNING"]

    assert readiness.geometry_validation.ready is True
    assert warning_rows
    assert any("Cleanup Face Normals" in issue.message for issue in warning_rows)
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_WARNING"
        and "Cleanup Face Normals" in issue.message
        for issue in issues
    )


def test_t2600_module_editor_controller_validate_includes_map_studio_readiness_issues() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    missing_authored = controller.validate()

    assert any(issue.code == "MAP_STUDIO_AUTHORED_MODULE_MISSING" for issue in missing_authored)

    controller.create_dev_test_authored_module(module_root="grdev01")
    issues = controller.validate()

    assert any(issue.code == "MAP_STUDIO_RUNTIME_RESOURCE_MISSING" for issue in issues)
    assert any("Stage/build" in issue.suggested_fix for issue in issues)
