from __future__ import annotations

import json
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


def test_t2643_exports_kmap_authored_module_package(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.level import new_kmap_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

    kmap = new_kmap_project(name="grdev01", game="K1")
    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    kmap.extra_sections["authored_module"] = payload
    authored = authored_project_from_kmap_payload(payload, fallback_name=kmap.name, fallback_game=kmap.game)

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "export_candidate"
    assert Path(result.module_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert result.package_verification is not None
    assert result.package_verification.ok is True
    assert ("grdev01_room01", "mdl") in {(item.resref, item.restype) for item in result.package_verification.resources}
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {summary.restype for summary in result.resources}

    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    authored_manifest = manifest["map_studio_authored_module"]
    assert authored_manifest["module_root"] == "grdev01"
    assert authored_manifest["content_origin"] == "map_studio_original"
    assert authored_manifest["authored_from_scratch"] is True
    assert authored_manifest["copied_from_base_game_module"] is False
    assert authored_manifest["source_module_resref"] == ""
    assert authored_manifest["inherited_base_game_module_content"] is False
    assert authored_manifest["capability_stage"] == "export_candidate"
    assert authored_manifest["game_tested"] is False
    assert authored_manifest["warp_command"] == "warp grdev01"
    assert authored_manifest["lighting_count"] == 1
    assert authored_manifest["room_lights"][0]["name"] == "grdev01_key_light"
    assert authored_manifest["room_lights"][0]["room_resref"] == "grdev01_room01"
    assert authored_manifest["room_lights"][0]["metadata"]["purpose"] == "canonical_smoke_visibility"
    assert authored_manifest["rooms"][0]["wok_walkable_faces"] == 2
    assert authored_manifest["rooms"][0]["wok_non_walk_faces"] == 8
    assert authored_manifest["rooms"][0]["walkmesh_boundary_wall_faces"] == 8
    contract = authored_manifest["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["warp_command"] == "warp grdev01"
    assert contract["content_origin"] == "map_studio_original"
    assert contract["authored_from_scratch"] is True
    assert contract["copied_from_base_game_module"] is False
    assert contract["expected_absent_runtime_observations"]["base_game_module_geometry"] is True
    assert contract["expected_absent_runtime_observations"]["inherited_scripted_moving_test_objects"] is True
    assert "PLCaa" in contract["expected_absent_runtime_observations"]["forbidden_source_module_resrefs"]
    assert contract["all_required_resources_present"] is True
    assert contract["pre_game_package_readback_ok"] is True
    assert {row["filename"] for row in contract["required_resources"]} >= {
        "grdev01.are",
        "grdev01.git",
        "module.ifo",
        "grdev01.pth",
        "grdev01.lyt",
        "grdev01.vis",
        "grdev01_room01.wok",
        "grdev01_room01.mdl",
        "grdev01_room01.mdx",
    }
    assert contract["expected_entry_point"]["area_resref"] == "grdev01"
    assert contract["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert contract["expected_runtime_observations"]["module_identity_resref"] == "grdev01"
    assert contract["expected_runtime_observations"]["no_inherited_base_game_geometry_or_scripted_movers"] is True
    assert contract["expected_placeables"] == [
        {
            "kind": "placeable",
            "index": 0,
            "template_resref": "plc_bench",
            "tag": "grdev01_test_placeable",
            "label": "placeable:grdev01_test_placeable",
            "position": [1.75, 1.5, 0.0],
            "bearing": 0.0,
        }
    ]
    assert contract["expected_waypoints"][0]["tag"] == "start"
    assert contract["all_walkability_checks_passed"] is True
    walkability_by_label = {row["label"]: row for row in contract["walkability"]["checks"]}
    assert walkability_by_label["entry_point"]["ok"] is True
    assert walkability_by_label["placeable:grdev01_test_placeable"]["ok"] is True
    assert walkability_by_label["waypoint:start"]["ok"] is True
    assert {"entry_point", "placeable:grdev01_test_placeable", "waypoint:start"} <= set(contract["pathing_anchor_labels"])
    assert authored_manifest["smoke_expectations"]["expected_runtime_observations"]["test_placeable_tags"] == ["grdev01_test_placeable"]
    test_plan = authored_manifest["modder_test_plan"]
    assert test_plan["task"] == "T2605"
    assert test_plan["capability_stage"] == "export_candidate"
    assert test_plan["game_ready"] is False
    assert test_plan["proof_state"] == "requires_live_warp_proof"
    assert test_plan["warp_command"] == "warp grdev01"
    assert test_plan["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert test_plan["expected_runtime_observations"]["test_placeable_tags"] == ["grdev01_test_placeable"]
    assert test_plan["expected_runtime_observations"]["module_identity_resref"] == "grdev01"
    assert test_plan["expected_absent_runtime_observations"]["inherited_scripted_moving_test_objects"] is True
    assert "screenshot" in test_plan["evidence"]["accepted_kinds"]
    assert test_plan["missing_acceptance_checks"] == contract["in_game_acceptance_checks"]
    template_dependencies = authored_manifest["gameplay_template_dependencies"]
    template_keys = {(row["template_resref"], row["restype"], row["kind"]) for row in template_dependencies}
    assert authored_manifest["gameplay_template_dependency_count"] == 2
    assert authored_manifest["gameplay_packaged_template_dependency_count"] == 0
    assert authored_manifest["gameplay_external_template_dependency_count"] == 2
    assert ("plc_bench", "utp", "placeable") in template_keys
    assert ("sw_startloc001", "utw", "waypoint") in template_keys
    assert all(row["status"] == "external_or_base_game" for row in template_dependencies)


def test_t2643_exports_diagnostic_kmap_authored_module_without_optional_placed_content(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    payload = create_dev_test_authored_module_payload(
        module_root="grdev01",
        game="K1",
        include_test_placeable=False,
        include_start_waypoint=False,
    )
    authored = authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")

    result = export_authored_module_project(AuthoredModuleExportRequest(project=authored, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.metadata["gameplay_counts"]["placeables"] == 0
    assert result.metadata["gameplay_counts"]["waypoints"] == 0
    contract = result.metadata["smoke_expectations"]
    assert contract["expected_placeables"] == []
    assert contract["expected_waypoints"] == []
    assert contract["pathing_anchor_labels"] == ["entry_point"]
    assert result.metadata["gameplay_template_dependency_count"] == 0


def test_t2643_controller_exports_current_kmap_authored_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=False)

    assert result.ok is True
    assert Path(result.module_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert "grdev01.are" in payload["runtime_resources"]
    assert "grdev01_room01.mdl" in payload["runtime_resources"]


def test_t2680_pathing_includes_walkable_spatial_gameplay_anchors() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grpth01",
        game="K1",
    )
    for kind, template, tag, position in (
        ("creature", "c_drdmkone", "grpth_guard", (1.0, 1.0, 0.0)),
        ("door", "door_t01", "grpth_door", (-1.0, 1.0, 0.0)),
        ("trigger", "trg_test", "grpth_trig", (1.0, -1.0, 0.0)),
        ("encounter", "enc_test", "grpth_enc", (-1.0, -1.0, 0.0)),
        ("placeable", "plc_bench", "grpth_bench", (2.0, 0.0, 0.0)),
        ("waypoint", "wp_test", "grpth_wp", (0.0, 2.0, 0.0)),
        ("sound", "snd_test", "grpth_sound", (0.0, -2.0, 0.0)),
    ):
        project = add_authored_gameplay_placement(
            project,
            kind=kind,
            template_resref=template,
            tag=tag,
            position=position,
        ).project
    project = add_authored_gameplay_placement(
        project,
        kind="camera",
        tag="7",
        position=(2.0, 2.0, 0.0),
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="store",
        template_resref="stm_shop",
        tag="grpth_store",
    ).project

    build = build_authored_module(project)
    pathing = build.metadata["pathing"]
    labels = set(pathing["anchor_labels"])

    assert not build.blocking_issues
    assert ("grpth01", "pth") in build.resources
    assert {
        "entry_point",
        "creature:grpth_guard",
        "door:grpth_door",
        "trigger:grpth_trig",
        "encounter:grpth_enc",
        "placeable:grpth_bench",
        "waypoint:grpth_wp",
    } <= labels
    assert "sound:grpth_sound" not in labels
    assert "camera:7" not in labels
    assert "store:grpth_store" not in labels
    assert pathing["point_count"] >= 7
    assert build.metadata["gameplay_counts"]["creatures"] == 1
    assert build.metadata["gameplay_counts"]["doors"] == 1
    assert build.metadata["gameplay_counts"]["triggers"] == 1
    assert build.metadata["gameplay_counts"]["encounters"] == 1
    template_dependencies = build.metadata["gameplay_template_dependencies"]
    template_keys = {(row["template_resref"], row["restype"], row["kind"]) for row in template_dependencies}
    assert build.metadata["gameplay_template_dependency_count"] >= 8
    assert ("c_drdmkone", "utc", "creature") in template_keys
    assert ("door_t01", "utd", "door") in template_keys
    assert ("trg_test", "utt", "trigger") in template_keys
    assert ("enc_test", "ute", "encounter") in template_keys
    assert ("plc_bench", "utp", "placeable") in template_keys
    assert ("wp_test", "utw", "waypoint") in template_keys
    assert ("snd_test", "uts", "sound") in template_keys
    assert ("stm_shop", "utm", "store") in template_keys


def test_t2605_incomplete_door_transition_blocks_authored_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grtran01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grtran_exit",
        position=(0.0, 1.0, 0.0),
        linked_to_module="grnext01",
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    joined_blockers = "\n".join(build.blocking_issues + list(readiness.blocking_messages))
    assert "incomplete transition" in joined_blockers
    assert "LinkedToModule is set to grnext01" in joined_blockers
    assert readiness.can_export_candidate is False
    assert readiness.metadata["transition_incomplete_count"] == 1
    assert readiness.metadata["transition_references"][0]["status"] == "missing_destination"


def test_t2605_complete_door_module_transition_is_export_candidate() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grtran02",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="door",
        template_resref="door_t01",
        tag="grtran_exit",
        position=(0.0, 1.0, 0.0),
        linked_to="wp_arrive",
        linked_to_module="grnext01",
    ).project

    build = build_authored_module(project)
    readiness = build_authored_module_readiness(project, packaged_resources=build.resource_summaries)

    assert not build.blocking_issues
    assert readiness.metadata["transition_count"] == 1
    assert readiness.metadata["transition_complete_count"] == 1
    assert readiness.metadata["transition_incomplete_count"] == 0
    assert readiness.metadata["transition_references"][0]["status"] == "module_transition"
    assert readiness.can_export_candidate is True


def test_t2907_terrain_preset_exports_walkable_wok_pathing_and_lighting(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grterr01",
        game="K1",
    )

    result = export_authored_module_project(AuthoredModuleExportRequest(project=project, output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "export_candidate"
    assert result.blocking_issues == []
    resource_keys = {(summary.resref, summary.restype) for summary in result.resources}
    assert {
        ("grterr01", "are"),
        ("grterr01", "git"),
        ("grterr01", "lyt"),
        ("grterr01", "vis"),
        ("grterr01", "pth"),
        ("module", "ifo"),
        ("grterr01_room01", "mdl"),
        ("grterr01_room01", "mdx"),
        ("grterr01_room01", "wok"),
    } <= resource_keys
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    authored_manifest = manifest["map_studio_authored_module"]
    room = authored_manifest["rooms"][0]
    assert room["resref"] == "grterr01_room01"
    assert room["wok_walkable_faces"] == 32
    assert room["wok_non_walk_faces"] == 32
    assert room["walkmesh_boundary_wall_faces"] == 32
    assert room["floor_surface_id"] == 3
    assert authored_manifest["lighting_count"] == 1
    assert authored_manifest["room_lights"][0]["name"] == "grterr01_key_light"
    assert authored_manifest["room_lights"][0]["room_resref"] == "grterr01_room01"
    assert authored_manifest["room_lights"][0]["metadata"]["purpose"] == "starter_room_visibility"
    assert authored_manifest["walkability"]["ok"] is True
    walkability_labels = {row["label"] for row in authored_manifest["walkability"]["checks"]}
    assert {"entry_point", "placeable:grterr01_test_placeable", "waypoint:start"} <= walkability_labels
    assert authored_manifest["pathing"]["walkmesh_component_count"] == 1
    assert {"entry_point", "placeable:grterr01_test_placeable", "waypoint:start"} <= set(
        authored_manifest["pathing"]["anchor_labels"]
    )


def test_t2600_camera_properties_update_survives_kmap_payload_roundtrip() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import (
        authored_project_from_kmap_payload,
        authored_project_to_kmap_payload,
    )
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        update_authored_gameplay_camera_properties,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcam01",
        game="K1",
    )
    update = add_authored_gameplay_placement(
        project,
        kind="camera",
        tag="2",
        position=(1.0, 2.0, 3.0),
    )

    update = update_authored_gameplay_camera_properties(
        update.project,
        update.placement_id,
        camera_id=42,
        field_of_view=62.5,
        height=1.25,
        mic_range=18.0,
        pitch=-12.0,
    )

    row = next(row for row in authored_gameplay_placement_rows(update.project) if row.kind == "camera")
    assert row.kind == "camera"
    assert row.camera_id == 42
    assert row.field_of_view == 62.5
    assert row.height == 1.25
    assert row.mic_range == 18.0
    assert row.pitch == -12.0

    payload = authored_project_to_kmap_payload(update.project)
    camera_payload = payload["placements"]["cameras"][0]
    assert camera_payload == {
        "camera_id": 42,
        "position": [1.0, 2.0, 3.0],
        "orientation": [0.0, 0.0, 0.0, 1.0],
        "field_of_view": 62.5,
        "height": 1.25,
        "mic_range": 18.0,
        "pitch": -12.0,
    }

    round_tripped = authored_project_from_kmap_payload(payload, fallback_name="grcam01", fallback_game="K1")
    camera = round_tripped.placements.cameras[0]
    assert camera.camera_id == 42
    assert camera.field_of_view == 62.5
    assert camera.height == 1.25
    assert camera.mic_range == 18.0
    assert camera.pitch == -12.0


def test_t2686_export_forwards_game_root_to_authored_material_preflight(tmp_path: Path, monkeypatch) -> None:
    _install_native_payload_paths()

    from types import SimpleNamespace

    from src.core.modules import authored_module_export as export_module
    from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    captured: dict[str, str] = {}

    def fake_preflight(texture: str, *, game: str = "K1", game_root_dir: str = "", require_game_resolution: bool = False):
        captured["texture"] = texture
        captured["game_root_dir"] = game_root_dir
        return SimpleNamespace(warnings=[], blocking_issues=[])

    monkeypatch.setattr(export_module, "compile_authored_room_material_preflight", fake_preflight)
    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grmat01",
        game="K1",
    )
    game_root = tmp_path / "swkotor"

    result = export_authored_module_project(
        AuthoredModuleExportRequest(
            project=project,
            output_dir=str(tmp_path / "out"),
            game_root_dir=str(game_root),
        )
    )

    assert result.ok is True
    assert captured["game_root_dir"] == str(game_root)


def test_t2643_dry_run_does_not_mark_runtime_resources(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.export_authored_module(tmp_path, dry_run=True)

    assert result.ok is True
    assert result.code == "dry_run_passed"
    assert result.module_path == ""
    assert controller.project.extra_sections["authored_module"].get("runtime_resources", []) == []


def test_t2643_export_panel_exposes_authored_module_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    boundary_panel_source = Path(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authoredModuleRequested" in panel_source
    assert "mapStudioExportAuthoredModuleButton" in panel_source
    assert "Export Authored KMAP Module" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleRequested.connect(self.export_authored_module)" in window_source
    assert "self.controller.export_authored_module(path, dry_run=dry_run)" in window_source
    assert "authored_module_smoke_summary_lines" in window_source


def _dev_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    return authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")


def _room_only_dev_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(
        module_root="grdev01",
        game="K1",
        include_test_placeable=False,
        include_start_waypoint=False,
    )
    return authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")


def test_t2644_prepare_authored_module_install_writes_checklist_and_proof_manifest(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleInstallPrepRequest,
        authored_module_smoke_summary_lines,
        prepare_authored_module_install,
    )

    result = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "staged_for_manual_install"
    assert result.installed_module_path == ""
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    assert Path(result.proof_recording_script_path).is_file()
    assert "No KOTOR Modules folder was supplied" in "\n".join(result.warnings)
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    assert "warp grdev01" in checklist
    assert "Evidence capture helper:" in checklist
    assert "capture_grdev01_smoke_evidence.py" in checklist
    assert "Proof recorder:" in checklist
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    assert "record_authored_module_game_proof.py" in proof_recorder
    assert "--module-loads-in-game" in proof_recorder
    assert "--module-identity-matches-authored-resref" in proof_recorder
    assert "--no-inherited-base-game-geometry-or-scripted-movers" in proof_recorder
    assert "Drag or paste screenshot/video evidence path" in proof_recorder
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["task"] == "T2644"
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert proof["install"]["installed"] is False
    assert proof["package"]["verification"]["ok"] is True
    assert "capture_grdev01_smoke_evidence.py" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--record-proof" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--module-identity-matches-authored-resref" in proof["launch_handoff"]["evidence_capture_command"]
    assert "--no-inherited-base-game-geometry-or-scripted-movers" in proof["launch_handoff"]["evidence_capture_command"]
    test_plan = proof["modder_test_plan"]
    assert test_plan["task"] == "T2605"
    assert test_plan["game_ready"] is False
    assert test_plan["proof_state"] == "requires_live_warp_proof"
    assert test_plan["install"]["proof_manifest_path"] == result.proof_manifest_path
    assert test_plan["install"]["dry_run"] is False
    assert test_plan["acceptance_checks"] == proof["acceptance_checks"]
    assert test_plan["missing_acceptance_checks"] == proof["acceptance_checks"]
    contract = proof["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["all_required_resources_present"] is True
    assert contract["in_game_acceptance_checks"] == proof["acceptance_checks"]
    assert contract["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert contract["expected_placeables"][0]["tag"] == "grdev01_test_placeable"
    assert contract["all_walkability_checks_passed"] is True
    assert "placeable:grdev01_test_placeable" in contract["pathing_anchor_labels"]
    summary = authored_module_smoke_summary_lines(result.export_result)
    assert any("warp grdev01" in line for line in summary)
    assert "Expected player start: grdev01 at (0.00, -3.00, 0.00)." in summary
    assert any("grdev01_test_placeable" in line for line in summary)
    assert "Walkability preflight: 3/3 gameplay anchor(s) on generated WOK." in summary
    assert summary[-1] == "Capability: export candidate; in-game screenshot/video proof is still required."


def test_t2644_room_only_authored_install_omits_placeable_proof_requirement(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(project=_room_only_dev_authored_project(), output_dir=str(tmp_path))
    )

    assert result.ok is True
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    proof_recorder = Path(result.proof_recording_script_path).read_text(encoding="utf-8")
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))

    assert "authored test placeable appears" not in checklist
    assert "--test-placeable-visible" not in proof_recorder
    assert "--test-placeable-visible" not in proof["launch_handoff"]["evidence_capture_command"]
    assert proof["acceptance_checks"] == [
        "module_loads_in_game",
        "module_identity_matches_authored_resref",
        "player_spawns_on_floor",
        "player_can_walk_on_floor",
        "no_inherited_base_game_geometry_or_scripted_movers",
        "screenshot_or_video_captured",
    ]
    assert proof["t2601_smoke_contract"]["expected_placeables"] == []
    assert proof["t2601_smoke_contract"]["in_game_acceptance_checks"] == proof["acceptance_checks"]


def test_t2644_prepare_authored_module_install_copies_to_modules_with_backup(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"existing")

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=_dev_authored_project(),
            output_dir=str(tmp_path / "out"),
            game_modules_dir=str(modules_dir),
            overwrite=True,
        )
    )

    backup = modules_dir / "grdev01.mod.bak"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert result.backup_module_path == str(backup)
    assert backup.read_bytes() == b"existing"
    assert installed.read_bytes() != b"existing"
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["install"]["installed_module_path"] == str(installed)
    assert proof["install"]["backup_module_path"] == str(backup)


def test_t2644_prepare_authored_module_install_refreshes_stale_currentgame_cache(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    game_root = tmp_path / "KOTOR"
    modules_dir = game_root / "Modules"
    cache_dir = game_root / "currentgame"
    modules_dir.mkdir(parents=True)
    cache_dir.mkdir()
    stale_cache = cache_dir / "grdev01.mod"
    stale_cache.write_bytes(b"old cached runtime module")

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=_dev_authored_project(),
            output_dir=str(tmp_path / "out"),
            game_modules_dir=str(modules_dir),
        )
    )

    installed = modules_dir / "grdev01.mod"
    stale_backup = cache_dir / "grdev01.mod.bak"
    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert installed.exists()
    assert stale_cache.read_bytes() == installed.read_bytes()
    assert stale_backup.read_bytes() == b"old cached runtime module"
    assert any("currentgame cache" in warning for warning in result.warnings)
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["install"]["installed"] is True
    assert any("currentgame cache" in warning for warning in proof["warnings"])


def test_t2644_records_authored_module_game_proof(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    evidence = tmp_path / "grdev01_authored_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
        )
    )

    assert result.ok is True
    assert result.code == "game_proof_recorded"
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is False
    assert proof["game_tested"] is True
    assert proof["game_test"]["accepted"] is True
    assert proof["t2601_smoke_contract"]["game_tested"] is True
    assert proof["t2601_smoke_contract"]["proof_required"] is False
    assert proof["modder_test_plan"]["game_ready"] is True
    assert proof["modder_test_plan"]["proof_state"] == "game_smoke_tested"
    assert proof["modder_test_plan"]["capability_stage"] == "game_smoke_tested"
    assert proof["modder_test_plan"]["missing_acceptance_checks"] == []
    assert proof["modder_test_plan"]["evidence"]["path"] == str(evidence)

    pack_manifest = json.loads(Path(result.pack_manifest_path).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is True
    assert authored["capability_stage"] == "game_smoke_tested"
    assert authored["in_game_proof"]["checks"]["module_identity_matches_authored_resref"] is True
    assert authored["in_game_proof"]["checks"]["player_can_walk_on_floor"] is True
    assert authored["in_game_proof"]["checks"]["no_inherited_base_game_geometry_or_scripted_movers"] is True
    assert authored["t2601_smoke_contract"]["capability_stage"] == "game_smoke_tested"
    assert authored["modder_test_plan"]["game_ready"] is True
    assert authored["modder_test_plan"]["proof_state"] == "game_smoke_tested"
    assert authored["modder_test_plan"]["evidence"]["path"] == str(evidence)


def test_t2644_allow_missing_evidence_keeps_authored_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    missing_evidence = tmp_path / "missing_authored_warp_proof.mp4"

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(missing_evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
            allow_missing_evidence=True,
        )
    )

    assert result.ok is False
    assert result.code == "game_proof_incomplete"
    assert result.missing_checks == ["screenshot_or_video_captured"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False


def test_t2601_authored_module_rejects_unsupported_game_proof_evidence(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import (
        AuthoredModuleGameProofRequest,
        AuthoredModuleInstallPrepRequest,
        prepare_authored_module_install,
        record_authored_module_game_proof,
    )

    prep = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))
    evidence = tmp_path / "notes.txt"
    evidence.write_text("warp worked", encoding="utf-8")

    result = record_authored_module_game_proof(
        AuthoredModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            module_identity_matches_authored_resref=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            no_inherited_base_game_geometry_or_scripted_movers=True,
        )
    )

    assert result.ok is False
    assert result.missing_checks == ["screenshot_or_video_captured"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["game_tested"] is False
    assert proof["game_test"]["checks"]["screenshot_or_video_captured"] is False


def test_t2644_controller_stages_current_authored_module(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.stage_authored_module(tmp_path)

    assert result.ok is True
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    payload = controller.project.extra_sections["authored_module"]
    assert payload["proof_manifest_path"] == result.proof_manifest_path
    assert "grdev01_room01.mdl" in payload["runtime_resources"]
    assert payload["pack_manifest_path"] == result.export_result.manifest_path
    assert payload["modder_test_plan"]["proof_state"] == "requires_live_warp_proof"
    assert payload["modder_test_plan"]["warp_command"] == "warp grdev01"
    readiness = controller.authored_module_readiness().readiness
    assert readiness.metadata["modder_test_plan"]["warp_command"] == "warp grdev01"
    assert readiness.metadata["modder_test_plan"]["missing_acceptance_checks"] == payload["modder_test_plan"]["missing_acceptance_checks"]


def test_t2683_controller_installs_authored_module_to_modules_folder_with_backup(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    installed = modules_dir / "grdev01.mod"
    installed.write_bytes(b"old module")

    result = controller.stage_authored_module(
        tmp_path / "stage",
        game_modules_dir=modules_dir,
        overwrite=True,
    )

    assert result.ok is True
    assert result.code == "installed"
    assert result.installed_module_path == str(installed)
    assert result.resolved_game_root_dir == str(modules_dir.parent)
    assert "launch_grdev01_smoke_test.py" in result.launch_helper_command
    assert str(modules_dir.parent) in result.launch_helper_command
    assert Path(result.elevated_launch_script_path).is_file()
    launch_script = Path(result.elevated_launch_script_path).read_text(encoding="utf-8")
    assert "Start-Process" in launch_script
    assert "-Verb RunAs" in launch_script
    assert "warp grdev01" in launch_script
    assert installed.read_bytes() != b"old module"
    assert Path(result.backup_module_path).read_bytes() == b"old module"
    payload = controller.project.extra_sections["authored_module"]
    assert payload["installed_module_path"] == str(installed)
    assert payload["resolved_modules_dir"] == str(modules_dir)
    assert payload["resolved_game_root_dir"] == str(modules_dir.parent)
    assert payload["launch_helper_command"] == result.launch_helper_command
    assert payload["elevated_launch_script_path"] == result.elevated_launch_script_path
    assert payload["proof_recording_script_path"] == result.proof_recording_script_path
    assert payload["backup_module_path"] == result.backup_module_path
    assert payload["proof_manifest_path"] == result.proof_manifest_path
    assert payload["modder_test_plan"]["install"]["installed_module_path"] == str(installed)
    assert payload["modder_test_plan"]["install"]["proof_manifest_path"] == result.proof_manifest_path
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["launch_handoff"]["resolved_game_root_dir"] == str(modules_dir.parent)
    assert proof["launch_handoff"]["expected_executable_path"].endswith("swkotor.exe")
    assert proof["launch_handoff"]["elevated_launch_script_path"] == result.elevated_launch_script_path
    assert proof["launch_handoff"]["proof_recording_script_path"] == result.proof_recording_script_path
    assert proof["launch_handoff"]["warp_command"] == "warp grdev01"


def test_t2644_export_panel_exposes_authored_module_stage_action() -> None:
    panel_source = Path(
        "native/GhostRigger.Tools.Workflow.ModuleMeshes/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    boundary_panel_source = Path(
        "native/GhostRigger.GUI.Boundary.Panels/Python/src/gui/panels/module_editor/export_panel.py"
    ).read_text(encoding="utf-8")
    window_source = Path(
        "native/GhostRigger.Windows.Editor.Level/Python/src/gui/windows/module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authoredModuleStageRequested" in panel_source
    assert "mapStudioStageAuthoredModuleButton" in panel_source
    assert "authoredModuleInstallRequested" in panel_source
    assert "mapStudioInstallAuthoredModuleButton" in panel_source
    assert "Stage Authored Module for Game Test" in panel_source
    assert "Install Authored Module for Game Test" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleStageRequested.connect(self.stage_authored_module)" in window_source
    assert "self.export_panel.authoredModuleInstallRequested.connect(self.install_authored_module)" in window_source
    assert "self.controller.stage_authored_module(path, dry_run=dry_run)" in window_source
    assert "game_modules_dir=modules_path" in window_source
