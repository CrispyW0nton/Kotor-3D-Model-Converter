from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2653_add_creature_and_trigger_export_through_git() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grnpc01",
        game="K1",
    )
    creature_update = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grnpc01_test_droid",
        position=(0.0, 0.0, 0.0),
        bearing=1.57,
    )
    trigger_update = add_authored_gameplay_placement(
        creature_update.project,
        kind="trigger",
        template_resref="newgeneric001",
        tag="grnpc01_trigger",
        position=(0.5, 0.5, 0.0),
    )
    build = build_authored_module(trigger_update.project)

    assert trigger_update.project.placements.creatures[0].template_resref == "c_drdmkone"
    assert trigger_update.project.placements.triggers[0].geometry
    assert not build.blocking_issues
    assert ("grnpc01", "git") in build.resources


def test_t2653_kmap_payload_preserves_authored_gameplay_placement_types() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="wide_hall",
        module_root="grgit01",
        game="K2",
    )
    project = add_authored_gameplay_placement(project, kind="door", template_resref="door_t01", tag="exit_door", position=(2.0, 0.0, 0.0)).project
    project = add_authored_gameplay_placement(project, kind="sound", template_resref="mus_area", tag="ambient_sound", position=(0.0, 0.0, 0.0)).project
    payload = authored_project_to_kmap_payload(project)
    roundtrip = authored_project_from_kmap_payload(payload)

    assert payload["placements"]["doors"][0]["template_resref"] == "door_t01"
    assert payload["placements"]["sounds"][0]["template_resref"] == "mus_area"
    assert roundtrip.placements.doors[0].tag == "exit_door"
    assert roundtrip.placements.sounds[0].tag == "ambient_sound"


def test_t2600_readiness_reports_authored_transitions() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="wide_hall",
        module_root="grlink01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="exit_door",
        position=(2.0, 0.0, 0.0),
        linked_to="wp_grlink02_start",
        linked_to_module="grlink02",
        linked_to_flags=2,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="trigger",
        template_resref="newgeneric001",
        tag="missing_destination_trigger",
        position=(0.5, 0.5, 0.0),
        linked_to_module="grlink03",
    ).project

    readiness = build_authored_module_readiness(project)
    transition_status = next(item for item in readiness.toolchain if item.name == "Transitions")
    transition_refs = readiness.metadata["transition_references"]

    assert readiness.metadata["transition_count"] == 2
    assert readiness.metadata["transition_complete_count"] == 1
    assert readiness.metadata["transition_incomplete_count"] == 1
    assert transition_status.status == "Needs destination"
    assert transition_status.ready is False
    assert "1/2 authored transition(s) linked" in transition_status.value_label
    assert transition_refs[0]["linked_to"] == "wp_grlink02_start"
    assert transition_refs[0]["linked_to_module"] == "grlink02"
    assert transition_refs[0]["linked_to_flags"] == 2
    assert transition_refs[0]["status"] == "module_transition"
    assert any("missing a destination" in warning for warning in readiness.warnings)


def test_t2600_readiness_reports_generated_pth_pathing() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grpthrd",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="placeable",
        template_resref="plc_bench",
        tag="bench_anchor",
        position=(1.0, 1.0, 0.0),
    ).project

    readiness = build_authored_module_readiness(project)
    pathing = readiness.metadata["pathing"]
    pathing_status = next(item for item in readiness.toolchain if item.name == "PTH pathing")

    assert pathing["ready"] is True
    assert pathing["pth_resource"] == "grpthrd.pth"
    assert pathing["point_count"] >= 2
    assert pathing["connection_count"] >= 2
    assert "entry_point" in pathing["anchor_labels"]
    assert "placeable:bench_anchor" in pathing["anchor_labels"]
    assert pathing_status.ready is True
    assert "grpthrd.pth" in pathing_status.value_label
    assert "placeable:bench_anchor" in pathing_status.value_label


def test_t2602_pathing_blocker_blocks_export_candidate_and_validation_issue() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_validation_projection import authored_module_readiness_validation_issues
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grpthrd",
        game="K1",
    )
    project = replace(
        project,
        placements=replace(
            project.placements,
            entry_point=ModuleEntryPoint(area_resref="grpthrd", position=(100.0, 100.0, 0.0)),
        ),
    )

    readiness = build_authored_module_readiness(project)
    issues = authored_module_readiness_validation_issues(readiness)
    pathing = readiness.metadata["pathing"]
    pathing_status = next(item for item in readiness.toolchain if item.name == "PTH pathing")

    assert readiness.can_preview is True
    assert readiness.can_export_candidate is False
    assert readiness.export_status == "Pathing blocked"
    assert pathing["ready"] is False
    assert pathing["blocking_messages"]
    assert pathing["blocking_targets"]
    assert any("entry_point" in message for message in pathing["blocking_messages"])
    assert pathing["blocking_targets"][0]["target_id"] == "entry_point"
    assert pathing["blocking_targets"][0]["workspace"] == "entry_point"
    assert pathing_status.ready is False
    assert pathing_status.status == "Blocked"
    assert any(issue.code == "MAP_STUDIO_PTH_PATHING_BLOCKER" for issue in issues)
    pathing_issue = next(issue for issue in issues if issue.code == "MAP_STUDIO_PTH_PATHING_BLOCKER")
    assert pathing_issue.severity == "Error"
    assert "walkable WOK" in pathing_issue.suggested_fix


def test_t2602_pathing_blocker_targets_off_walkmesh_authored_placement() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grpthtg",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="placeable",
        template_resref="plc_bench",
        tag="bench_far",
        position=(100.0, 100.0, 0.0),
    ).project

    readiness = build_authored_module_readiness(project)
    pathing = readiness.metadata["pathing"]
    target = next(item for item in pathing["blocking_targets"] if item.get("placement_kind") == "placeable")

    assert readiness.can_export_candidate is False
    assert pathing["ready"] is False
    assert target["anchor_label"] == "placeable:bench_far"
    assert target["target_id"].startswith("authored:placeable:")
    assert target["workspace"] == "placement"
    assert "move it onto generated walkable WOK" in target["fix_action"]


def test_t2604_pathing_validates_placements_against_offset_multi_room_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, AuthoredPlaceableInstance, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grmulti", game="K1", display_name="Multi Room WOK"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grmulti_a",
                primitive=RectangularRoomPrimitive(room_resref="grmulti_a", width=8.0, depth=8.0),
                position=(0.0, 0.0, 0.0),
            ),
            AuthoredRoomSpec(
                room_resref="grmulti_b",
                primitive=RectangularRoomPrimitive(room_resref="grmulti_b", width=8.0, depth=8.0),
                position=(20.0, 0.0, 0.0),
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grmulti", position=(0.0, 0.0, 0.0)),
            placeables=(
                AuthoredPlaceableInstance(
                    template_resref="plc_bench",
                    tag="bench_room_b",
                    position=(20.0, 0.0, 0.0),
                ),
            ),
        ),
    )

    readiness = build_authored_module_readiness(project)
    pathing = readiness.metadata["pathing"]

    assert readiness.can_preview is True
    assert pathing["ready"] is True
    assert pathing["walkmesh_component_count"] == 2
    assert "placeable:bench_room_b" in pathing["anchor_labels"]
    assert not pathing["blocking_messages"]


def test_t2600_authored_transition_edit_updates_rows_and_payload() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_gameplay_preview import authored_gameplay_preview_markers
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        update_authored_gameplay_transition,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="wide_hall",
        module_root="grtran01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="exit_door",
        position=(2.0, 0.0, 0.0),
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="placeable",
        template_resref="plc_bench",
        tag="bench",
        position=(0.0, 0.0, 0.0),
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="waypoint",
        template_resref="wp_test",
        tag="wp_grtran02_start",
        position=(3.0, 0.0, 0.0),
    ).project

    updated = update_authored_gameplay_transition(
        project,
        "authored:door:0",
        linked_to="wp_grtran02_start",
        linked_to_module="grtran02",
        linked_to_flags=2,
        transition_destination=1,
    )
    rows = authored_gameplay_placement_rows(updated.project)
    door_row = next(row for row in rows if row.kind == "door" and row.tag == "exit_door")
    waypoint_row = next(row for row in rows if row.kind == "waypoint")
    door_marker = next(
        marker
        for marker in authored_gameplay_preview_markers(updated.project)
        if marker.placement_id == door_row.placement_id
    )
    payload = authored_project_to_kmap_payload(updated.project)

    assert updated.project.placements.doors[0].linked_to == "wp_grtran02_start"
    assert updated.project.placements.doors[0].linked_to_module == "grtran02"
    assert updated.project.placements.doors[0].linked_to_flags == 2
    assert updated.project.placements.doors[0].transition_destination == 1
    assert door_row.transition_capable is True
    assert door_row.linked_to == "wp_grtran02_start"
    assert door_row.linked_to_module == "grtran02"
    assert door_row.linked_to_flags == 2
    assert door_row.transition_destination == 1
    assert door_row.transition_status == "module_transition"
    assert waypoint_row.transition_capable is False
    assert waypoint_row.transition_status == "not_applicable"
    assert door_row.transition_summary == "Links to waypoint wp_grtran02_start in grtran02"
    assert door_marker.metadata["transition_status"] == "module_transition"
    assert door_marker.metadata["transition_summary"] == "Links to waypoint wp_grtran02_start in grtran02"
    assert door_marker.metadata["linked_to"] == "wp_grtran02_start"
    assert door_marker.metadata["linked_to_module"] == "grtran02"
    assert door_marker.metadata["linked_to_flags"] == 2
    assert payload["placements"]["doors"][0]["linked_to"] == "wp_grtran02_start"
    assert payload["placements"]["doors"][0]["linked_to_module"] == "grtran02"
    assert payload["placements"]["doors"][0]["linked_to_flags"] == 2
    assert payload["placements"]["doors"][0]["transition_destination"] == 1

    with pytest.raises(ValueError, match="do not support transition"):
        update_authored_gameplay_transition(updated.project, "authored:placeable:0", linked_to="wp_any")
    with pytest.raises(ValueError, match="do not support transition"):
        update_authored_gameplay_transition(updated.project, waypoint_row.placement_id, linked_to="wp_any")


def test_t2653_controller_adds_placement_and_clears_runtime_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctl01")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grctl01.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_torch",
        tag="grctl01_torch",
        position=(1.0, 1.0, 0.0),
    )
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["placeables"][-1]["template_resref"] == "plc_torch"
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t3002_walkmesh_snap_uses_module_space_room_offset() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_walkmesh import snap_position_to_authored_walkmesh
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsnap01",
        game="K2",
    )
    project = replace(project, rooms=(replace(project.rooms[0], position=(20.0, -5.0, 3.0)),))

    snap = snap_position_to_authored_walkmesh(project, (20.0, -5.0, 99.0))

    assert snap is not None
    assert snap.inside_face is True
    assert snap.horizontal_distance == 0.0
    assert snap.position == (20.0, -5.0, 3.0)


def test_end_key_ground_snap_ignores_stacked_walkmesh_above_object() -> None:
    _install_native_payload_paths()

    from dataclasses import replace

    from src.core.modules.authored_module_walkmesh import snap_position_to_authored_walkmesh
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grend01",
        game="K2",
    )
    lower = replace(project.rooms[0], position=(0.0, 0.0, 0.0))
    upper = replace(project.rooms[0], room_resref="grend02", position=(0.0, 0.0, 5.0))
    project = replace(project, rooms=(lower, upper))

    nearest = snap_position_to_authored_walkmesh(project, (0.0, 0.0, 3.0))
    grounded = snap_position_to_authored_walkmesh(project, (0.0, 0.0, 3.0), downward_only=True)

    assert nearest is not None and nearest.position[2] == 5.0
    assert grounded is not None and grounded.position[2] == 0.0


def test_controller_end_key_ground_snap_is_one_durable_transform_command() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grendctl")
    controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="ground_me",
        position=(0.0, 0.0, 3.0),
        snap_to_walkmesh=False,
    )
    placement_id = next(
        row.placement_id for row in controller.authored_gameplay_placements() if row.tag == "ground_me"
    )
    undo_count = len(controller.command_history.undo_stack)

    update, snap = controller.snap_authored_gameplay_placement_to_walkmesh(
        placement_id,
        downward_only=True,
    )

    assert placement_id.startswith("authored:placeable:i_")
    assert update.placement_id == placement_id
    assert update.position[2] == 0.0
    assert snap.position[2] == 0.0
    assert len(controller.command_history.undo_stack) == undo_count + 1
    assert controller.command_history.undo_stack[-1].metadata["downward_only"] is True


def test_t3002_trigger_transform_moves_polygon_with_marker() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        update_authored_gameplay_placement_transform,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grtrigmv",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="trigger",
        template_resref="newgeneric001",
        tag="moving_trigger",
        position=(1.0, 2.0, 0.0),
    ).project
    before = project.placements.triggers[0].geometry

    update = update_authored_gameplay_placement_transform(
        project,
        "authored:trigger:0",
        position=(4.0, 1.0, 2.0),
    )
    after = update.project.placements.triggers[0].geometry

    assert after == tuple((x + 3.0, y - 1.0, z + 2.0) for x, y, z in before)


def test_t3002_controller_places_on_walkmesh_in_one_undoable_command() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grsnap02")
    before_undo_count = len(controller.command_history.undo_stack)

    controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_bench",
        tag="snapped_bench",
        position=(1.0, 1.0, 18.0),
        snap_to_walkmesh=True,
    )

    row = next(row for row in controller.authored_gameplay_placements() if row.tag == "snapped_bench")
    assert row.position[2] == 0.0
    assert len(controller.command_history.undo_stack) == before_undo_count + 1
    assert "Add placeable placement" in controller.command_history.undo_label


def test_authored_placement_identity_survives_delete_save_and_reopen(tmp_path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        remove_authored_gameplay_placement,
        update_authored_gameplay_placement_transform,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grid01",
        game="K2",
    )
    first = add_authored_gameplay_placement(
        project, kind="placeable", template_resref="plc_bench", tag="first", position=(0.0, 0.0, 0.0)
    )
    second = add_authored_gameplay_placement(
        first.project, kind="placeable", template_resref="plc_bench", tag="second", position=(1.0, 0.0, 0.0)
    )
    second_id = second.placement_id

    assert second_id.startswith("authored:placeable:i_")
    assert second_id != "authored:placeable:1"

    removed = remove_authored_gameplay_placement(second.project, first.placement_id)
    rows = authored_gameplay_placement_rows(removed.project)
    remaining_second = next(row for row in rows if row.tag == "second")
    assert remaining_second.placement_id == second_id

    moved = update_authored_gameplay_placement_transform(
        removed.project,
        second_id,
        position=(4.0, 5.0, 0.0),
    )
    payload = authored_project_to_kmap_payload(moved.project)
    instance_id = next(
        row["instance_id"] for row in payload["placements"]["placeables"] if row.get("tag") == "second"
    )
    reopened = authored_project_from_kmap_payload(payload)
    reopened_rows = authored_gameplay_placement_rows(reopened)
    reopened_second = next(row for row in reopened_rows if row.tag == "second")

    assert reopened_second.placement_id == second_id
    assert reopened_second.position == (4.0, 5.0, 0.0)
    assert second_id.endswith(instance_id)


def test_placeable_builder_provenance_survives_kmap_and_blocks_unbundled_headless_export() -> None:
    _install_native_payload_paths()

    import pytest
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.module_editor_controller import ModuleEditorController

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcustom",
        game="K2",
    )
    added = add_authored_gameplay_placement(
        project,
        kind="placeable",
        template_resref="pb_custom",
        tag="custom_prop",
        provenance={
            "game": "K2",
            "library_source": "placeable_builder",
            "asset_id": "asset-123",
            "asset_path": "Placeable Library/pb_custom.ghostplaceable.json",
        },
    )
    payload = authored_project_to_kmap_payload(added.project)
    reopened = authored_project_from_kmap_payload(payload)
    restored_payload = authored_project_to_kmap_payload(reopened)

    provenance = restored_payload["placements"]["metadata"]["instance_provenance"]
    assert provenance[added.placement_id]["template_resref"] == "pb_custom"
    assert provenance[added.placement_id]["library_source"] == "placeable_builder"

    controller = ModuleEditorController()
    controller.new_project(name="grcustom", game="K2")
    controller.project.extra_sections["authored_module"] = restored_payload
    with pytest.raises(ValueError, match="pb_custom"):
        controller._require_authored_placeable_resources_ready()

    controller._authored_placeable_resources = (("pb_custom", "utp", b"utp-bytes"),)
    controller._require_authored_placeable_resources_ready()


def test_legacy_indexed_placement_migrates_deterministically_without_entering_git() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_placements import authored_gameplay_placement_rows

    payload = create_dev_test_authored_module_payload(module_root="grlegacy", game="K1")
    for values in payload["placements"].values():
        if isinstance(values, list):
            for row in values:
                row.pop("instance_id", None)

    first = authored_project_from_kmap_payload(payload)
    second = authored_project_from_kmap_payload(payload)
    first_id = authored_gameplay_placement_rows(first)[0].placement_id
    second_id = authored_gameplay_placement_rows(second)[0].placement_id
    saved = authored_project_to_kmap_payload(first)
    build = build_authored_module(first)

    assert first_id == second_id
    assert first_id.startswith("authored:") and ":i_" in first_id
    assert saved["placements"]["placeables"][0]["instance_id"] == first_id.rsplit(":", 1)[-1]
    assert first_id.encode("ascii") not in build.resources[("grlegacy", "git")].data


def test_t2653_invalid_placement_blocks_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grbadgit",
        game="K1",
    )

    with pytest.raises(ValueError, match="Unsupported authored gameplay placement kind"):
        add_authored_gameplay_placement(project, kind="magic_box", template_resref="plc_bench")
    with pytest.raises(ValueError, match="Placeable placement requires a template resref"):
        add_authored_gameplay_placement(project, kind="placeable", template_resref="")


def test_t2653_builder_tab_exposes_gameplay_placement_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioGameplayPlacementKindComboBox" in source
    assert "mapStudioGameplayTemplateLineEdit" in source
    assert "mapStudioGameplaySpatialHintLabel" in source
    assert "mapStudioAddGameplayPlacementButton" in source
    assert "gameplayPlacementRequested" in source
    assert "_update_gameplay_spatial_controls" in source
    assert "Stores/merchants are module-level resources" in source
    assert "self.builder_tab.set_gameplay_placement_kinds(self.controller.available_authored_gameplay_placement_kinds())" in window_source
    assert "self.builder_tab.gameplayPlacementRequested.connect(self.add_authored_gameplay_placement)" in window_source
    assert "self.controller.add_authored_gameplay_placement" in window_source
