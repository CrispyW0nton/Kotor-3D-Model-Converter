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

    updated = update_authored_gameplay_transition(
        project,
        "authored:door:0",
        linked_to="wp_grtran02_start",
        linked_to_module="grtran02",
        transition_destination=1,
    )
    rows = authored_gameplay_placement_rows(updated.project)
    door_row = next(row for row in rows if row.placement_id == "authored:door:0")
    door_marker = next(marker for marker in authored_gameplay_preview_markers(updated.project) if marker.placement_id == "authored:door:0")
    payload = authored_project_to_kmap_payload(updated.project)

    assert updated.project.placements.doors[0].linked_to == "wp_grtran02_start"
    assert updated.project.placements.doors[0].linked_to_module == "grtran02"
    assert updated.project.placements.doors[0].transition_destination == 1
    assert door_row.transition_capable is True
    assert door_row.linked_to == "wp_grtran02_start"
    assert door_row.linked_to_module == "grtran02"
    assert door_row.transition_destination == 1
    assert door_row.transition_status == "module_transition"
    assert door_row.transition_summary == "Links to wp_grtran02_start in grtran02"
    assert door_marker.metadata["transition_status"] == "module_transition"
    assert door_marker.metadata["transition_summary"] == "Links to wp_grtran02_start in grtran02"
    assert door_marker.metadata["linked_to"] == "wp_grtran02_start"
    assert door_marker.metadata["linked_to_module"] == "grtran02"
    assert payload["placements"]["doors"][0]["linked_to"] == "wp_grtran02_start"
    assert payload["placements"]["doors"][0]["linked_to_module"] == "grtran02"
    assert payload["placements"]["doors"][0]["transition_destination"] == 1

    with pytest.raises(ValueError, match="do not support transition"):
        update_authored_gameplay_transition(updated.project, "authored:placeable:0", linked_to="wp_any")


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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.Windows.Editor.Level"
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
