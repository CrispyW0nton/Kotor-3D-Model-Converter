from __future__ import annotations

import sys
from pathlib import Path

import pytest


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


def test_t2605_authored_gameplay_placement_serializes_core_git_lists() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import (
        AuthoredCameraInstance,
        AuthoredCreatureInstance,
        AuthoredDoorInstance,
        AuthoredEncounterInstance,
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        AuthoredSoundInstance,
        AuthoredStoreInstance,
        AuthoredTriggerInstance,
        AuthoredWaypointInstance,
        ModuleEntryPoint,
        build_git_bytes,
    )
    from src.core.modules.module_format import GITData

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="grdev01"),
        creatures=(AuthoredCreatureInstance(template_resref="g_tataka", position=(1.0, 2.0, 0.0), bearing=1.25),),
        doors=(
            AuthoredDoorInstance(
                template_resref="door_dev",
                tag="door_to_next",
                position=(2.0, 3.0, 0.0),
                bearing=0.5,
                linked_to="wp_next",
                linked_to_module="grdev02",
                transition_destination=1,
            ),
        ),
        triggers=(
            AuthoredTriggerInstance(
                template_resref="tr_dev",
                tag="trigger_exit",
                position=(0.0, 0.0, 0.0),
                geometry=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
                linked_to="wp_next",
                transition_destination=1,
            ),
        ),
        encounters=(AuthoredEncounterInstance(template_resref="enc_dev", tag="ambush", position=(-1.0, 2.5, 0.0)),),
        sounds=(AuthoredSoundInstance(template_resref="snd_wind", tag="ambient_wind", position=(0.0, 1.0, 0.0)),),
        cameras=(
            AuthoredCameraInstance(
                camera_id=7,
                position=(4.0, 5.0, 1.5),
                orientation=(0.0, 0.0, 0.70710678, 0.70710678),
                field_of_view=55.0,
                height=1.25,
                mic_range=12.0,
                pitch=0.35,
            ),
        ),
        stores=(AuthoredStoreInstance(template_resref="st_dev", tag="dev_store"),),
        placeables=(AuthoredPlaceableInstance(template_resref="plc_bench", position=(1.75, 1.5, 0.0)),),
        waypoints=(AuthoredWaypointInstance(template_resref="sw_startloc001", tag="start", position=(0.0, -3.0, 0.0)),),
    )

    git = GITData.from_bytes(build_git_bytes(placement))

    assert len(git.creatures) == 1
    assert git.creatures[0].resref == "g_tataka"
    assert git.creatures[0].x == 1.0
    assert git.creatures[0].bearing == 1.25
    assert len(git.doors) == 1
    assert git.doors[0].resref == "door_dev"
    assert git.doors[0].tag == "door_to_next"
    assert git.doors[0].linked_to == "wp_next"
    assert git.doors[0].linked_to_module == "grdev02"
    assert git.doors[0].transition == 1
    assert len(git.triggers) == 1
    assert git.triggers[0].resref == "tr_dev"
    assert git.triggers[0].tag == "trigger_exit"
    assert git.triggers[0].linked_to == "wp_next"
    assert git.triggers[0].transition == 1
    assert len(git.triggers[0].geometry) == 3
    assert len(git.encounters) == 1
    assert git.encounters[0].resref == "enc_dev"
    assert git.encounters[0].tag == "ambush"
    assert git.encounters[0].x == -1.0
    assert len(git.sounds) == 1
    assert git.sounds[0].resref == "snd_wind"
    assert git.sounds[0].tag == "ambient_wind"
    assert git.sounds[0].y == 1.0
    assert len(git.cameras) == 1
    assert git.cameras[0].camera_id == 7
    assert git.cameras[0].x == 4.0
    assert git.cameras[0].z == 1.5
    assert git.cameras[0].orientation == pytest.approx((0.0, 0.0, 0.70710678, 0.70710678))
    assert git.cameras[0].field_of_view == 55.0
    assert git.cameras[0].height == 1.25
    assert git.cameras[0].mic_range == 12.0
    assert git.cameras[0].pitch == pytest.approx(0.35)
    assert len(git.stores) == 1
    assert git.stores[0].resref == "st_dev"
    assert git.stores[0].tag == "dev_store"
    assert len(git.placeables) == 1
    assert len(git.waypoints) == 1


def test_t2605_authored_gameplay_validation_blocks_missing_templates() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import (
        AuthoredCreatureInstance,
        AuthoredGameplayPlacement,
        ModuleEntryPoint,
        validate_authored_gameplay_placement,
    )

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="grdev01"),
        creatures=(AuthoredCreatureInstance(template_resref=""),),
    )

    validation = validate_authored_gameplay_placement(placement)

    assert validation.ok is False
    assert "Creature placement requires a template resref." in validation.blocking_issues


def test_t2605_project_validation_includes_gameplay_placement_issues() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import AuthoredCreatureInstance, AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec, validate_authored_module_project
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=(AuthoredRoomSpec(room_resref="grdev01_room01", primitive=RectangularRoomPrimitive(room_resref="grdev01_room01")),),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdev01"),
            creatures=(AuthoredCreatureInstance(template_resref=""),),
        ),
    )

    validation = validate_authored_module_project(project)

    assert validation.ok is False
    assert "Creature placement requires a template resref." in validation.blocking_issues


def test_t2630_gameplay_placements_validate_against_generated_walkmesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        AuthoredWaypointInstance,
        ModuleEntryPoint,
        validate_authored_gameplay_placement_against_walkmesh,
    )
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok

    wok = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="grdev01", position=(0.0, -3.0, 0.0)),
        placeables=(AuthoredPlaceableInstance(template_resref="plc_bench", tag="bench", position=(1.75, 1.5, 0.0)),),
        waypoints=(AuthoredWaypointInstance(template_resref="sw_startloc001", tag="start", position=(0.0, -3.0, 0.0)),),
    )

    validation = validate_authored_gameplay_placement_against_walkmesh(placement, wok)

    assert validation.ok is True
    assert [check.label for check in validation.checks] == ["entry_point", "placeable:bench", "waypoint:start"]
    assert all(check.face_index >= 0 for check in validation.checks)
    assert all(check.surface_id == 4 for check in validation.checks)


def test_t2630_gameplay_placement_walkmesh_validation_blocks_unsafe_positions() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        AuthoredWaypointInstance,
        ModuleEntryPoint,
        validate_authored_gameplay_placement_against_walkmesh,
    )
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok

    wok = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="grdev01", position=(99.0, 99.0, 0.0)),
        placeables=(AuthoredPlaceableInstance(template_resref="plc_bench", tag="bench", position=(1.75, 1.5, 1.0)),),
        waypoints=(AuthoredWaypointInstance(template_resref="sw_startloc001", tag="start", position=(0.0, -3.0, 0.0)),),
    )

    validation = validate_authored_gameplay_placement_against_walkmesh(placement, wok)

    assert validation.ok is False
    assert any("entry_point is outside the generated room walkmesh" in issue for issue in validation.blocking_issues)
    assert any("placeable:bench Z=1.000 is not on generated floor Z=0.000" in issue for issue in validation.blocking_issues)
    assert any(check.label == "waypoint:start" and check.ok for check in validation.checks)


def test_t2630_gameplay_placement_walkmesh_validation_blocks_non_walk_surfaces() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        ModuleEntryPoint,
        validate_authored_gameplay_placement_against_walkmesh,
    )
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        verts=[
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 7),
            WOKFace(0, 2, 3, 7),
        ],
    )
    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="grdev01", position=(0.0, 0.0, 0.0)),
        placeables=(AuthoredPlaceableInstance(template_resref="plc_bench", tag="bench", position=(0.25, 0.25, 0.0)),),
    )

    validation = validate_authored_gameplay_placement_against_walkmesh(placement, wok)

    assert validation.ok is False
    assert any("surface 7 (NON_WALK) is not walkable" in issue for issue in validation.blocking_issues)
