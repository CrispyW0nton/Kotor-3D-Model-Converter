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
    assert authored_manifest["capability_stage"] == "export_candidate"
    assert authored_manifest["game_tested"] is False
    assert authored_manifest["warp_command"] == "warp grdev01"
    contract = authored_manifest["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["warp_command"] == "warp grdev01"
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


def _dev_authored_project():
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload

    payload = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    return authored_project_from_kmap_payload(payload, fallback_name="grdev01", fallback_game="K1")


def test_t2644_prepare_authored_module_install_writes_checklist_and_proof_manifest(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install

    result = prepare_authored_module_install(AuthoredModuleInstallPrepRequest(project=_dev_authored_project(), output_dir=str(tmp_path)))

    assert result.ok is True
    assert result.code == "staged_for_manual_install"
    assert result.installed_module_path == ""
    assert Path(result.checklist_path).is_file()
    assert Path(result.proof_manifest_path).is_file()
    assert "No KOTOR Modules folder was supplied" in "\n".join(result.warnings)
    checklist = Path(result.checklist_path).read_text(encoding="utf-8")
    assert "warp grdev01" in checklist
    proof = json.loads(Path(result.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["task"] == "T2644"
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert proof["install"]["installed"] is False
    assert proof["package"]["verification"]["ok"] is True
    contract = proof["t2601_smoke_contract"]
    assert contract["task"] == "T2601"
    assert contract["all_required_resources_present"] is True
    assert contract["in_game_acceptance_checks"] == proof["acceptance_checks"]
    assert contract["expected_entry_point"]["position"] == [0.0, -3.0, 0.0]
    assert contract["expected_placeables"][0]["tag"] == "grdev01_test_placeable"
    assert contract["all_walkability_checks_passed"] is True
    assert "placeable:grdev01_test_placeable" in contract["pathing_anchor_labels"]


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
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
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

    pack_manifest = json.loads(Path(result.pack_manifest_path).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is True
    assert authored["capability_stage"] == "game_smoke_tested"
    assert authored["in_game_proof"]["checks"]["player_can_walk_on_floor"] is True
    assert authored["t2601_smoke_contract"]["capability_stage"] == "game_smoke_tested"


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
    assert "Stage Authored Module for Game Test" in panel_source
    assert panel_source == boundary_panel_source
    assert "self.export_panel.authoredModuleStageRequested.connect(self.stage_authored_module)" in window_source
    assert "self.controller.stage_authored_module(path, dry_run=dry_run)" in window_source
