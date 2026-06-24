from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


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
    assert readiness.metadata["package_manifest_evidence"]["ready"] is False
    assert readiness.metadata["package_manifest_evidence"]["missing"] == [
        "pack_manifest_path",
        "proof_manifest_path",
        "package_resource_inventory",
    ]
    assert any(issue.code == "MAP_STUDIO_PACKAGE_MANIFEST_EVIDENCE_MISSING" for issue in issues)
    assert any(issue.code == "MAP_STUDIO_GAME_PROOF_REQUIRED" for issue in issues)
    assert any("warp" in issue.suggested_fix for issue in issues)


def test_t2600_staged_export_candidate_has_package_manifest_evidence() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    inventory = {
        "schema": "ghostrigger.map_studio.package_resource_inventory.v1",
        "module_root": "grdev01",
        "readback_ok": True,
        "required_runtime_resources": [{"resref": resref, "restype": restype} for resref, restype in _runtime_keys()],
        "missing_required_runtime_resources": [],
    }
    readiness = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        proof_metadata={
            "pack_manifest_path": "C:/tmp/grdev01_pack_manifest.json",
            "proof_manifest_path": "C:/tmp/grdev01_authored_module_game_manifest.json",
            "package_resource_inventory": inventory,
        },
    )
    issues = authored_module_readiness_validation_issues(readiness)

    assert readiness.can_export_candidate is True
    assert readiness.metadata["package_manifest_evidence"]["ready"] is True
    assert readiness.metadata["package_manifest_evidence"]["missing"] == []
    assert not any(issue.code == "MAP_STUDIO_PACKAGE_MANIFEST_EVIDENCE_MISSING" for issue in issues)


def test_t2911_open_wok_edges_project_specific_validation_rows() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    readiness = build_authored_module_readiness(_floor_plan_project())
    issues = authored_module_readiness_validation_issues(readiness)
    open_edge_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_WOK_OPEN_EDGE_WARNING"]

    assert readiness.metadata["open_wok_edge_count"] > 0
    assert open_edge_rows
    assert open_edge_rows[0].severity == "Warning"
    assert "open/boundary walkable edge" in open_edge_rows[0].message
    assert "intentional room perimeter" in open_edge_rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_WARNING"
        and "open/boundary walkable edge" in issue.message
        for issue in issues
    )


def test_t2911_player_start_off_walkmesh_projects_specific_validation_row() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    project = replace(
        _floor_plan_project(),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdev01", position=(99.0, 99.0, 0.0)),
        ),
    )
    readiness = build_authored_module_readiness(project)
    issues = authored_module_readiness_validation_issues(readiness)
    player_start_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_PLAYER_START_NOT_WALKABLE"]

    assert readiness.metadata["pathing"]["ready"] is False
    assert readiness.metadata["pathing"]["blocking_targets"][0]["target_id"] == "entry_point"
    assert player_start_rows
    assert player_start_rows[0].severity == "Error"
    assert "player start" in player_start_rows[0].message
    assert "walkmesh" in player_start_rows[0].message.lower()
    assert "entry point controls" in player_start_rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_PTH_PATHING_BLOCKER"
        and "entry_point is outside" in issue.message
        for issue in issues
    )


def test_t2911_bad_walkable_wok_slope_projects_specific_validation_row() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    readiness = SimpleNamespace(
        metadata={
            "steep_walkable_face_count": 1,
            "max_walkable_slope_degrees": 63.4,
            "max_allowed_walkable_slope_degrees": 45.0,
        },
        inputs=(),
        blocking_messages=("Room grsteep generated WOK has 1 walkable face(s) steeper than 45.0 degrees.",),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=(),
        can_preview=False,
        ready_for_game_test=False,
        game_tested=False,
    )
    issues = authored_module_readiness_validation_issues(readiness)
    slope_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_WOK_BAD_SLOPE"]

    assert slope_rows
    assert slope_rows[0].severity == "Error"
    assert "steeper than 45.0 degrees" in slope_rows[0].message
    assert "paint steep faces non-walkable" in slope_rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_BLOCKER"
        and "steeper than 45.0 degrees" in issue.message
        for issue in issues
    )


def test_t2911_wok_topology_blockers_project_specific_validation_rows() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    readiness = SimpleNamespace(
        metadata={
            "invalid_wok_face_count": 1,
            "degenerate_wok_face_count": 2,
            "non_manifold_wok_edge_count": 3,
        },
        inputs=(),
        blocking_messages=(
            "Room grbad generated WOK has 1 face(s) with invalid vertex indices.",
            "Room grbad generated WOK has 2 degenerate face(s).",
            "Room grbad generated WOK has 3 non-manifold walkable edge(s).",
        ),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=(),
        can_preview=False,
        ready_for_game_test=False,
        game_tested=False,
    )
    issues = authored_module_readiness_validation_issues(readiness)
    by_code = {issue.code: issue for issue in issues}

    assert by_code["MAP_STUDIO_WOK_INVALID_TRIANGLE"].severity == "Error"
    assert "invalid vertex indices" in by_code["MAP_STUDIO_WOK_INVALID_TRIANGLE"].message
    assert "valid vertices" in by_code["MAP_STUDIO_WOK_INVALID_TRIANGLE"].suggested_fix
    assert by_code["MAP_STUDIO_WOK_DEGENERATE_TRIANGLE"].severity == "Error"
    assert "degenerate face" in by_code["MAP_STUDIO_WOK_DEGENERATE_TRIANGLE"].message
    assert "zero-area WOK triangles" in by_code["MAP_STUDIO_WOK_DEGENERATE_TRIANGLE"].suggested_fix
    assert by_code["MAP_STUDIO_WOK_NON_MANIFOLD_EDGE"].severity == "Error"
    assert "non-manifold walkable edge" in by_code["MAP_STUDIO_WOK_NON_MANIFOLD_EDGE"].message
    assert "valid ownership" in by_code["MAP_STUDIO_WOK_NON_MANIFOLD_EDGE"].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_BLOCKER"
        and "generated WOK has" in issue.message
        for issue in issues
    )


def test_t2911_degenerate_authored_faces_project_specific_validation_row() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    message = "Room grbad floor-plan has 1 degenerate zero-area face after split/bridge cleanup."
    readiness = SimpleNamespace(
        metadata={
            "geometry_validation": {
                "ready": False,
                "blocking_messages": (message,),
                "warnings": (),
            },
        },
        inputs=(),
        blocking_messages=(message,),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=(),
        can_preview=False,
        ready_for_game_test=False,
        game_tested=False,
    )
    issues = authored_module_readiness_validation_issues(readiness)
    rows = [issue for issue in issues if issue.code == "MAP_STUDIO_DEGENERATE_FACE"]

    assert rows
    assert rows[0].severity == "Error"
    assert "degenerate zero-area face" in rows[0].message
    assert "zero-area authored faces" in rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_BLOCKER"
        and "degenerate zero-area face" in issue.message
        for issue in issues
    )
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_BLOCKER"
        and "degenerate zero-area face" in issue.message
        for issue in issues
    )


def test_t2912_stale_package_and_proof_state_projects_validation_row(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    staged = controller.stage_authored_module(tmp_path)
    assert staged.ok is True

    controller.apply_authored_room_style(texture="CM_Baremetal", floor_surface="metal", room_resref="grdev01_room01")
    readiness = controller.authored_module_readiness().readiness
    issues = authored_module_readiness_validation_issues(readiness)
    stale_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_EXPORT_PROOF_STALE"]

    assert stale_rows
    assert stale_rows[0].severity == "Warning"
    assert "MDL, MDX, WOK, LYT, VIS, PTH, .mod" in stale_rows[0].message
    assert "fresh in-game proof" in stale_rows[0].suggested_fix


def test_t2911_doorway_transition_intent_projects_specific_validation_row() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues

    warning = (
        "1 floor-plan opening(s) exist without authored door, trigger, or waypoint markers. "
        "Add a KOTOR door/transition marker and review DOOR WOK surface intent before game proof."
    )
    readiness = SimpleNamespace(
        metadata={
            "doorway_transition": {
                "ready": False,
                "status": "Needs door/trigger/waypoint marker",
                "opening_count": 1,
                "transition_marker_count": 0,
                "transition_reference_count": 0,
                "linked_transition_count": 0,
                "warnings": [warning],
                "fix_hint": "Use Placement > Door, Trigger, or Waypoint near the opening, then set transition destinations if it leaves the area.",
            }
        },
        inputs=(),
        blocking_messages=(),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=(warning,),
        can_preview=True,
        ready_for_game_test=False,
        game_tested=False,
    )
    issues = authored_module_readiness_validation_issues(readiness)
    doorway_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_DOORWAY_TRANSITION_INTENT_MISSING"]

    assert doorway_rows
    assert doorway_rows[0].severity == "Warning"
    assert "floor-plan opening" in doorway_rows[0].message
    assert "Door, Trigger, or Waypoint" in doorway_rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_READINESS_WARNING"
        and "floor-plan opening" in issue.message
        for issue in issues
    )


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
    winding_rows = [issue for issue in issues if issue.code == "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING"]

    assert readiness.geometry_validation.ready is True
    assert winding_rows
    assert winding_rows[0].severity == "Warning"
    assert "Cleanup Face Normals" in winding_rows[0].message
    assert "generated room geometry and WOK winding" in winding_rows[0].suggested_fix
    assert not any(
        issue.code == "MAP_STUDIO_FLOOR_PLAN_GEOMETRY_WARNING"
        and "Cleanup Face Normals" in issue.message
        for issue in issues
    )
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
