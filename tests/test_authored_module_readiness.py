from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
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


def _placements(area_resref: str = "grdev01"):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint

    return AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref=area_resref))


def _placements_with_templates(area_resref: str = "grdev01"):
    from src.core.modules.authored_module_objects import (
        AuthoredCreatureInstance,
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        AuthoredWaypointInstance,
        ModuleEntryPoint,
    )

    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref=area_resref),
        creatures=(AuthoredCreatureInstance(template_resref="g_tresgencorp001", tag="TestCreature"),),
        placeables=(AuthoredPlaceableInstance(template_resref="PLC_bench", tag="TestBench"),),
        waypoints=(AuthoredWaypointInstance(template_resref="sw_startloc001", tag="StartWaypoint"),),
    )


def _placements_with_all_resource_categories(area_resref: str = "grdev01"):
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
    )

    return AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref=area_resref),
        creatures=(AuthoredCreatureInstance(template_resref="g_tresgencorp001", tag="TestCreature"),),
        placeables=(AuthoredPlaceableInstance(template_resref="PLC_bench", tag="TestBench"),),
        doors=(AuthoredDoorInstance(template_resref="plc_door01", tag="TestDoor"),),
        triggers=(
            AuthoredTriggerInstance(
                template_resref="gr_exit_trig",
                tag="TestTrigger",
                geometry=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
            ),
        ),
        encounters=(AuthoredEncounterInstance(template_resref="gr_encounter", tag="TestEncounter"),),
        cameras=(AuthoredCameraInstance(camera_id=1),),
        sounds=(AuthoredSoundInstance(template_resref="gr_ambient", tag="TestSound"),),
        stores=(AuthoredStoreInstance(template_resref="gr_store", tag="TestStore"),),
        waypoints=(AuthoredWaypointInstance(template_resref="sw_startloc001", tag="StartWaypoint"),),
    )


def _floor_plan_project(game: str = "K1"):
    from src.core.modules.authored_module_project import create_floor_plan_room_project
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive

    return create_floor_plan_room_project(
        module_root="grdev01",
        game=game,
        display_name="GhostRigger Dev Test",
        floor_plan=FloorPlanRoomPrimitive(
            room_resref="grdev01_room01",
            points=((-3.0, -2.0), (3.0, -2.0), (3.0, 2.0), (-3.0, 2.0)),
        ),
        placements=_placements(),
    )


def _floor_plan_project_with_templates():
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
        placements=_placements_with_templates(),
    )


def _floor_plan_project_with_all_resources():
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
        placements=_placements_with_all_resource_categories(),
    )


def _two_room_visibility_project(*, room_a_visible=(), room_b_visible=()):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grdev01_a",
                primitive=RectangularRoomPrimitive(room_resref="grdev01_a"),
                position=(0.0, 0.0, 0.0),
                visible_rooms=tuple(room_a_visible),
            ),
            AuthoredRoomSpec(
                room_resref="grdev01_b",
                primitive=RectangularRoomPrimitive(room_resref="grdev01_b"),
                position=(10.0, 0.0, 0.0),
                visible_rooms=tuple(room_b_visible),
            ),
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
    assert ("grdev01", "pth") in readiness.missing_runtime_resources
    assert ("grdev01_room01", "mdl") in readiness.missing_runtime_resources
    assert "ARE/GIT/IFO/PTH/LYT/VIS" in readiness.next_action
    assert readiness.rooms[0].can_preview_geometry is True
    assert readiness.rooms[0].walkable_face_count == 2
    runtime_status = readiness.metadata["runtime_output_status"]
    assert runtime_status["status"] == "Missing generated resources"
    assert runtime_status["regenerate_required"] is True
    assert "grdev01_room01.mdl" in runtime_status["missing"]


def test_t2606_curve_guides_are_reported_as_authoring_only_in_readiness() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.map_studio_curve_guides import add_authored_curve_guide

    project = add_authored_curve_guide(
        _floor_plan_project(),
        name="main_path",
        purpose="pth_planning",
        room_resref="grdev01_room01",
        coordinate_space="kmap_world",
        points=((0.0, 0.0, 0.0), (1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
    )

    readiness = build_authored_module_readiness(project)

    assert readiness.metadata["construction_curve_guide_count"] == 1
    assert readiness.metadata["construction_curve_guide_names"] == ["main_path"]
    assert readiness.metadata["construction_curve_guide_runtime_state"] == "guide_only_not_runtime_geometry"
    assert any(
        "previewable KMAP authoring guides only" in warning
        and "do not yet export as KOTOR runtime geometry" in warning
        for warning in readiness.warnings
    )


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
    runtime_status = readiness.metadata["runtime_output_status"]
    assert runtime_status["status"] == "Current"
    assert runtime_status["regenerate_required"] is False
    assert runtime_status["missing"] == []


def test_t2605_kmap_bridge_reports_missing_runtime_outputs_for_ui() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_to_kmap_payload,
        build_kmap_authored_module_readiness,
    )

    kmap = SimpleNamespace(
        name="grdev01",
        game="K1",
        metadata={},
        extra_sections={"authored_module": authored_project_to_kmap_payload(_floor_plan_project())},
    )

    result = build_kmap_authored_module_readiness(kmap)

    status = result.metadata["runtime_output_status"]
    assert result.readiness is not None
    assert result.readiness.metadata["runtime_output_status"] == status
    assert status["status"] == "Missing generated resources"
    assert status["regenerate_required"] is True
    assert "grdev01.are" in status["missing"]
    assert "grdev01_room01.mdl" in status["missing"]
    assert status["stale_outputs"] == []
    assert "regenerate missing KOTOR runtime resources" in status["fix_hint"]


def test_t2605_kmap_bridge_reports_current_runtime_outputs_for_ui() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_to_kmap_payload,
        build_kmap_authored_module_readiness,
    )

    payload = authored_project_to_kmap_payload(
        _floor_plan_project(),
        runtime_resources=tuple(f"{resref}.{restype}" for resref, restype in _runtime_keys()),
    )
    kmap = SimpleNamespace(name="grdev01", game="K1", metadata={}, extra_sections={"authored_module": payload})

    result = build_kmap_authored_module_readiness(kmap)

    status = result.metadata["runtime_output_status"]
    assert result.readiness is not None
    assert result.readiness.metadata["runtime_output_status"] == status
    assert status["status"] == "Current"
    assert status["regenerate_required"] is False
    assert status["missing"] == []
    assert "grdev01_room01.wok" in status["present"]


def test_t2605_kmap_bridge_reports_stale_component_edit_outputs_for_ui() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_to_kmap_payload,
        build_kmap_authored_module_readiness,
    )

    project = _floor_plan_project()
    audit = {
        "operation": "move_floor_plan_vertex",
        "summary": "Moved a floor-plan vertex.",
        "walkmesh_review_required": True,
        "export_candidate_stale": True,
        "game_proof_stale": True,
        "topology_changed": True,
        "stale_outputs": ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"],
        "next_action": "Regenerate room MDL/MDX/WOK, rebuild LYT/VIS/PTH, package the .mod, then verify in game.",
    }
    project = replace(
        project,
        rooms=(replace(project.rooms[0], metadata={"last_component_edit_audit": audit}),),
    )
    payload = authored_project_to_kmap_payload(
        project,
        runtime_resources=tuple(f"{resref}.{restype}" for resref, restype in _runtime_keys()),
    )
    kmap = SimpleNamespace(name="grdev01", game="K1", metadata={}, extra_sections={"authored_module": payload})

    result = build_kmap_authored_module_readiness(kmap)

    status = result.metadata["runtime_output_status"]
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert result.readiness.can_export_candidate is False
    assert result.readiness.ready_for_game_test is False
    assert result.readiness.capability_stage == "previewable"
    assert result.readiness.export_status == "Stale runtime resources"
    assert "Regenerate room MDL/MDX/WOK" in result.readiness.next_action
    assert result.readiness.metadata["runtime_output_status"] == status
    impacts = {row["resource"]: row for row in status["resource_impacts"]}
    assert status["status"] == "Stale generated resources"
    assert status["regenerate_required"] is True
    assert status["edited_resource"] == "grdev01_room01"
    assert status["latest_operation"] == "move_floor_plan_vertex"
    assert status["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
    assert impacts["WOK"]["why_stale"] == "Walkmesh may no longer match the edited floor or openings."
    assert "Regenerate room MDL/MDX/WOK" in status["fix_hint"]


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
        "Component edit audit",
        "Floor-plan validation",
        "Walkmesh",
        "PTH pathing",
        "VIS visibility",
        "Lighting",
        "Resource placement",
        "Gameplay layout",
        "Doorway/transition intent",
        "Transitions",
        "Scripts",
        "Runtime package",
        "In-game proof",
    }
    assert preview_steps["Geometry authoring"].ready is True
    assert "floor-plan extrusion" in preview_steps["Geometry authoring"].value_label
    assert "bevel" in preview_steps["Geometry authoring"].value_label
    assert "rectangular union" in preview_steps["Geometry authoring"].value_label
    assert preview_steps["Component edit audit"].ready is True
    assert preview_steps["Floor-plan validation"].ready is True
    assert preview_steps["Walkmesh"].ready is True
    assert preview_steps["PTH pathing"].ready is True
    assert preview_steps["VIS visibility"].ready is True
    assert preview_steps["Lighting"].ready is False
    assert preview_steps["Lighting"].status == "Lighting not planned"
    assert "lightmap: not_started" in preview_steps["Lighting"].value_label
    assert preview_steps["Resource placement"].ready is True
    assert preview_steps["Resource placement"].status == "Optional"
    assert "No extra KOTOR resources placed yet" in preview_steps["Resource placement"].value_label
    assert "creatures, placeables, doors, triggers" in preview_steps["Resource placement"].value_label
    assert "merchants/stores" in preview_steps["Resource placement"].value_label
    assert preview_steps["Gameplay layout"].ready is True
    assert preview_steps["Doorway/transition intent"].ready is True
    assert preview_steps["Transitions"].ready is True
    assert preview_steps["Transitions"].status == "Optional"
    assert preview_steps["Scripts"].ready is True
    assert preview_steps["Scripts"].status == "Optional"
    assert preview_steps["Runtime package"].ready is False
    assert "ARE/GIT/IFO/PTH/LYT/VIS" in preview_steps["Runtime package"].fix_hint
    assert export_steps["Runtime package"].ready is True
    assert export_steps["In-game proof"].ready is False
    assert export_steps["In-game proof"].status == "Recorder ready after warp test"
    assert export_candidate.metadata["toolchain"][0]["name"] == "Geometry authoring"


def test_t2911_readiness_metadata_reports_steep_walkable_wok_slope(monkeypatch) -> None:
    _install_native_payload_paths()

    import src.core.modules.authored_module_readiness as readiness_module
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.module_format import WOKData, WOKFace

    steep_wok = WOKData(
        name="grsteep_room01",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 2.0),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=4),
        ],
    )

    def compile_steep_room(room):
        return SimpleNamespace(
            room_resref=room.normalised_resref(),
            room_mesh=SimpleNamespace(name="grsteep_room01", texture="CM_Baremetal", faces=(0,)),
            helper_meshes=(),
            wok=steep_wok,
        )

    monkeypatch.setattr(readiness_module, "compile_authored_room_spec", compile_steep_room)

    readiness = build_authored_module_readiness(_floor_plan_project())

    assert readiness.metadata["steep_walkable_face_count"] == 1
    assert readiness.metadata["max_walkable_slope_degrees"] > readiness.metadata["max_allowed_walkable_slope_degrees"]
    # Steep faces are advisory now (vanilla 001ebo ships one).
    assert not any("steeper than" in message for message in readiness.blocking_messages)
    assert any("steeper than" in message for message in readiness.warnings)


def test_t2606_readiness_reports_multi_room_vis_visibility_gaps() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(_two_room_visibility_project())
    visibility = readiness.metadata["visibility"]
    visibility_status = {step.name: step for step in readiness.toolchain}["VIS visibility"]

    assert visibility_status.ready is False
    assert visibility_status.status == "Needs visibility links"
    assert visibility["ready"] is False
    assert visibility["room_count"] == 2
    assert visibility["cross_room_link_count"] == 0
    assert visibility["isolated_rooms"] == ["grdev01_a", "grdev01_b"]
    assert any("no cross-room VIS links" in warning for warning in readiness.warnings)


def test_t2606_broken_vis_target_blocks_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(
        _two_room_visibility_project(
            room_a_visible=("grdev01_a", "missing_room"),
            room_b_visible=("grdev01_b",),
        ),
        packaged_resources=(
            *_runtime_keys(),
            ("grdev01_a", "mdl"),
            ("grdev01_a", "mdx"),
            ("grdev01_a", "wok"),
            ("grdev01_b", "mdl"),
            ("grdev01_b", "mdx"),
            ("grdev01_b", "wok"),
        ),
    )
    visibility = readiness.metadata["visibility"]

    assert readiness.can_export_candidate is False
    assert readiness.export_status == "VIS visibility blocked"
    assert visibility["status"] == "Blocked: 1 broken VIS target(s)"
    assert visibility["missing_targets"] == [{"room": "grdev01_a", "target": "missing_room"}]
    assert "Room grdev01_a references missing visible room missing_room." in readiness.blocking_messages


def test_t2600_readiness_reports_resource_placement_palette_and_counts() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(
        _floor_plan_project_with_all_resources(),
        packaged_resources=_runtime_keys(),
    )
    placement = {step.name: step for step in readiness.toolchain}["Resource placement"]
    palette = {item["kind"]: item for item in readiness.metadata["resource_placement_palette"]}

    assert placement.ready is True
    assert placement.status == "Planned"
    assert "1 creatures" in placement.value_label
    assert "1 merchants/stores" in placement.value_label
    assert readiness.metadata["resource_placement_summary"] == (
        "1 creatures, 1 placeables, 1 doors, 1 triggers, 1 encounters, "
        "1 cameras, 1 sounds, 1 merchants/stores, 1 waypoints"
    )
    assert palette["creatures"] == {"kind": "creatures", "label": "creatures", "restype": "utc", "count": 1}
    assert palette["placeables"] == {"kind": "placeables", "label": "placeables", "restype": "utp", "count": 1}
    assert palette["doors"] == {"kind": "doors", "label": "doors", "restype": "utd", "count": 1}
    assert palette["triggers"] == {"kind": "triggers", "label": "triggers", "restype": "utt", "count": 1}
    assert palette["encounters"] == {"kind": "encounters", "label": "encounters", "restype": "ute", "count": 1}
    assert palette["cameras"] == {"kind": "cameras", "label": "cameras", "restype": "git", "count": 1}
    assert palette["sounds"] == {"kind": "sounds", "label": "sounds", "restype": "uts", "count": 1}
    assert palette["stores"] == {"kind": "stores", "label": "merchants/stores", "restype": "utm", "count": 1}
    assert palette["waypoints"] == {"kind": "waypoints", "label": "waypoints", "restype": "utw", "count": 1}


def test_t2700_readiness_reports_external_gameplay_template_references_without_blocking_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(
        _floor_plan_project_with_templates(),
        packaged_resources=_runtime_keys(),
    )

    refs = readiness.metadata["gameplay_template_references"]
    names = {(item["template_resref"], item["restype"], item["kind"]) for item in refs}

    assert readiness.capability_stage == "export_candidate"
    assert readiness.can_export_candidate is True
    assert readiness.metadata["gameplay_template_reference_count"] == 3
    assert readiness.metadata["gameplay_packaged_template_count"] == 0
    assert readiness.metadata["gameplay_external_template_count"] == 3
    assert ("plc_bench", "utp", "placeable") in names
    assert ("g_tresgencorp001", "utc", "creature") in names
    assert ("sw_startloc001", "utw", "waypoint") in names
    assert all(item["status"] == "external_or_base_game" for item in refs)
    assert any("base-game" in warning for warning in readiness.warnings)
    assert "template ref(s)" in {step.name: step for step in readiness.toolchain}["Gameplay layout"].value_label


def test_t2600_readiness_reports_authored_script_hooks() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = _floor_plan_project()
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            metadata={
                **dict(project.metadata.metadata),
                "area_scripts": {"OnEnter": "gr_onenter"},
                "module_scripts": {"Mod_OnModLoad": "gr_modload"},
            },
        ),
    )
    readiness = build_authored_module_readiness(project, packaged_resources=(*_runtime_keys(), ("gr_modload", "ncs")))
    scripts = readiness.metadata["script_references"]
    script_status = {step.name: step for step in readiness.toolchain}["Scripts"]

    assert readiness.metadata["script_reference_count"] == 2
    assert readiness.metadata["script_packaged_count"] == 1
    assert readiness.metadata["script_external_count"] == 1
    assert script_status.status == "Ready"
    assert "2 script hook(s), 1 packaged, 1 external/Override" in script_status.value_label
    assert ("module", "Mod_OnModLoad", "gr_modload", "packaged") in {
        (item["scope"], item["field_name"], item["script_resref"], item["status"]) for item in scripts
    }
    assert ("area", "OnEnter", "gr_onenter", "external_or_override") in {
        (item["scope"], item["field_name"], item["script_resref"], item["status"]) for item in scripts
    }
    assert any("script hook" in warning and "Override" in warning for warning in readiness.warnings)


def test_t2600_readiness_reports_authored_room_light_coverage() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = replace(
        _floor_plan_project(),
        lights=(
            AuthoredRoomLight(
                name="key_light",
                room_resref="grdev01_room01",
                position=(0.0, -1.5, 2.5),
                color=(1.0, 0.86, 0.62),
                radius=9.5,
                intensity=1.2,
            ),
        ),
    )

    readiness = build_authored_module_readiness(project)
    lighting = {step.name: step for step in readiness.toolchain}["Lighting"]

    assert lighting.ready is False
    assert lighting.status == "Viewport lit only"
    assert "1 authored light(s), 1/1 room(s) lit" in lighting.value_label
    assert readiness.metadata["lighting_count"] == 1
    assert readiness.metadata["lighting_room_count"] == 1
    assert readiness.metadata["rooms_with_authored_lights"] == ["grdev01_room01"]
    assert readiness.metadata["rooms_without_authored_lights"] == []
    assert readiness.metadata["lightmap_planning_status"] == "viewport_lit_only"
    assert readiness.metadata["lighting"]["status"] == "Viewport lit only"
    assert readiness.metadata["lighting"]["game_tested_lighting"] is False
    assert any("viewport/editor intent" in warning for warning in readiness.warnings)
    assert readiness.metadata["room_lights"][0]["name"] == "key_light"


def test_t3105_readiness_reports_fullbright_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    project = _floor_plan_project()
    project = replace(
        project,
        metadata=replace(
            project.metadata,
            metadata={
                **dict(project.metadata.metadata),
                "lighting": {
                    "profile": "fullbright",
                    "source": "map_studio:test_fullbright",
                },
            },
        ),
    )

    readiness = build_authored_module_readiness(project)
    lighting = {step.name: step for step in readiness.toolchain}["Lighting"]

    assert lighting.ready is True
    assert lighting.status == "Fullbright export candidate"
    assert "profile: fullbright" in lighting.value_label
    assert readiness.metadata["lighting_profile"] == "fullbright"
    assert readiness.metadata["lightmap_planning_status"] == "fullbright_export_candidate"
    assert readiness.metadata["lighting"]["lighting_profile"] == "fullbright"
    assert readiness.metadata["lighting"]["lightmap_status"] == "fullbright_export_candidate"
    assert readiness.metadata["lighting"]["game_tested_lighting"] is False
    assert readiness.metadata["lighting"]["warnings"] == []


def test_t2600_readiness_distinguishes_lightmap_export_candidate_and_game_tested_lighting() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    base = replace(
        _floor_plan_project(),
        lights=(
            AuthoredRoomLight(
                name="key_light",
                room_resref="grdev01_room01",
                position=(0.0, -1.5, 2.5),
                color=(1.0, 0.86, 0.62),
                radius=9.5,
                intensity=1.2,
            ),
        ),
    )
    export_candidate = replace(
        base,
        metadata=AuthoredModuleMetadata(
            module_root=base.metadata.module_root,
            game=base.metadata.game,
            display_name=base.metadata.display_name,
            tag=base.metadata.tag,
            description=base.metadata.description,
            capability_stage=base.metadata.capability_stage,
            metadata={
                **dict(base.metadata.metadata),
                "lightmap": {
                    "status": "baked",
                    "manifest_path": "C:/tmp/grdev01_lightmap_manifest.json",
                    "rooms": ["grdev01_room01"],
                },
            },
        ),
    )
    game_tested = replace(
        export_candidate,
        metadata=replace(
            export_candidate.metadata,
            metadata={
                **dict(export_candidate.metadata.metadata),
                "lightmap": {
                    "status": "game_tested",
                    "manifest_path": "C:/tmp/grdev01_lightmap_manifest.json",
                    "rooms": ["grdev01_room01"],
                    "game_tested": True,
                },
            },
        ),
    )

    candidate_readiness = build_authored_module_readiness(export_candidate)
    proven_readiness = build_authored_module_readiness(game_tested)
    candidate_lighting = {step.name: step for step in candidate_readiness.toolchain}["Lighting"]
    proven_lighting = {step.name: step for step in proven_readiness.toolchain}["Lighting"]

    assert candidate_lighting.ready is True
    assert candidate_lighting.status == "Lightmap export candidate"
    assert candidate_readiness.metadata["lighting"]["lightmap_status"] == "export_candidate"
    assert candidate_readiness.metadata["lighting"]["lightmap_manifest_path"].endswith("grdev01_lightmap_manifest.json")
    assert candidate_readiness.metadata["lighting"]["game_tested_lighting"] is False
    assert proven_lighting.ready is True
    assert proven_lighting.status == "Game-tested lighting"
    assert proven_readiness.metadata["lighting"]["lightmap_status"] == "game_tested"
    assert proven_readiness.metadata["lighting"]["game_tested_lighting"] is True


def test_t2700_packaged_gameplay_template_references_are_marked_as_packaged() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    readiness = build_authored_module_readiness(
        _floor_plan_project_with_templates(),
        packaged_resources=(*_runtime_keys(), ("PLC_bench", "utp")),
    )
    refs = readiness.metadata["gameplay_template_references"]
    bench = next(item for item in refs if item["template_resref"] == "plc_bench")

    assert bench["packaged"] is True
    assert bench["status"] == "packaged"
    assert readiness.metadata["gameplay_packaged_template_count"] == 1
    assert readiness.metadata["gameplay_external_template_count"] == 2


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


def test_t3104_readiness_metadata_keeps_package_resource_inventory() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    inventory = {
        "schema": "ghostrigger.map_studio.package_resource_inventory.v1",
        "module_root": "grdev01",
        "readback_ok": True,
        "required_runtime_resources": [
            {"resref": resref, "restype": restype}
            for resref, restype in _runtime_keys()
        ],
        "missing_required_runtime_resources": [],
        "resource_groups": {
            "verified_archive_resource_count": 9,
            "loose_staged_resource_count": 9,
        },
        "install": {"installed": False, "dry_run": True},
    }
    readiness = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        proof_metadata={
            "proof_manifest_path": "C:/tmp/grdev01_authored_module_game_manifest.json",
            "package_resource_inventory": inventory,
        },
    )

    assert readiness.metadata["package_resource_inventory"] == inventory
    assert readiness.metadata["package_resource_inventory"]["module_root"] == "grdev01"
    assert readiness.metadata["package_resource_inventory"]["readback_ok"] is True


def test_t2601_readiness_builds_k2_launch_helper() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    installed = build_authored_module_readiness(
        _floor_plan_project(game="K2"),
        packaged_resources=_runtime_keys(),
        proof_metadata={
            "proof_manifest_path": "C:/tmp/grdev01_authored_module_game_manifest.json",
            "installed_module_path": "C:/Games/KOTOR2/Modules/grdev01.mod",
            "resolved_modules_dir": "C:/Games/KOTOR2/Modules",
        },
    )

    assert installed.metadata["launch_status"] == "ready_for_launch_helper"
    assert "launch_grdev01_smoke_test.py" in installed.metadata["launch_helper_command"]
    assert '--game "K2"' in installed.metadata["launch_helper_command"]
    assert installed.metadata["expected_executable_path"].endswith("swkotor2.exe")


def test_t2639_game_tested_requires_recorded_proof_metadata(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_readiness import build_authored_module_readiness

    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")
    preview_only = build_authored_module_readiness(_floor_plan_project(), game_tested=True)
    bare_flag = build_authored_module_readiness(_floor_plan_project(), packaged_resources=_runtime_keys(), game_tested=True)
    missing_evidence = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        game_tested=True,
        proof_metadata={
            "game_tested": True,
            "manual_proof_required": False,
            "game_test": {
                "accepted": True,
                "missing_checks": [],
                "evidence_path": str(tmp_path / "missing_warp_proof.png"),
            },
        },
    )
    proven = build_authored_module_readiness(
        _floor_plan_project(),
        packaged_resources=_runtime_keys(),
        game_tested=True,
        proof_metadata={
            "game_tested": True,
            "manual_proof_required": False,
            "game_test": {
                "accepted": True,
                "missing_checks": [],
                "evidence_path": str(evidence),
            },
        },
    )

    assert preview_only.capability_stage == "previewable"
    assert preview_only.game_tested is False
    assert bare_flag.capability_stage == "export_candidate"
    assert bare_flag.game_tested is False
    assert bare_flag.ready_for_game_test is True
    assert missing_evidence.capability_stage == "export_candidate"
    assert missing_evidence.game_tested is False
    assert missing_evidence.ready_for_game_test is True
    assert proven.capability_stage == "game_tested"
    assert proven.game_tested is True
    assert proven.metadata["proof_game_tested"] is True
    assert proven.ready_for_game_test is False
