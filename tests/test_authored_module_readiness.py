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
