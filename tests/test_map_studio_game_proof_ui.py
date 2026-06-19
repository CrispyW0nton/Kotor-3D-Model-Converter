from __future__ import annotations

import json
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Modules/Python",
        "native/GhostRigger.Core.Level/Python",
        "native/GhostRigger.Core.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Walkmesh/Python",
        "native/GhostRigger.Core.Geometry/Python",
        "native/GhostRigger.Core.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2658_controller_records_authored_game_proof_and_updates_kmap_readiness(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grdev01", game="K1")
    controller.create_dev_test_authored_module()
    staged = controller.stage_authored_module(tmp_path)
    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = controller.record_map_studio_game_proof(
        proof_manifest_path=staged.proof_manifest_path,
        evidence_path=evidence,
        tester="pytest",
        module_loads_in_game=True,
        player_spawns_on_floor=True,
        test_placeable_visible=True,
        player_can_walk_on_floor=True,
    )
    readiness = controller.authored_module_readiness().readiness
    payload = controller.project.extra_sections["authored_module"]

    assert result.ok is True
    assert result.code == "game_proof_recorded"
    assert payload["game_tested"] is True
    assert payload["in_game_proof_evidence_path"] == str(evidence)
    assert readiness is not None
    assert readiness.game_tested is True
    assert readiness.capability_stage == "game_tested"


def test_t2658_controller_dispatches_grdev01_smoke_proof_manifest(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    staged = controller.stage_dev_test_module(tmp_path)
    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = controller.record_map_studio_game_proof(
        proof_manifest_path=staged.proof_manifest_path,
        evidence_path=evidence,
        tester="pytest",
        module_loads_in_game=True,
        player_spawns_on_floor=True,
        test_placeable_visible=True,
        player_can_walk_on_floor=True,
    )
    proof = json.loads(Path(staged.proof_manifest_path).read_text(encoding="utf-8"))

    assert result.ok is True
    assert result.code == "game_proof_recorded"
    assert proof["task"] == "T2601"
    assert proof["game_tested"] is True


def test_t2658_module_editor_has_in_app_game_proof_dialog_and_recorder() -> None:
    repo = Path(__file__).resolve().parents[1]
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
    panel_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Panels"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "readiness_panel.py"
    ).read_text(encoding="utf-8")
    controller_source = (
        repo
        / "native"
        / "GhostRigger.Core.Modules"
        / "Python"
        / "src"
        / "core"
        / "modules"
        / "module_editor_controller.py"
    ).read_text(encoding="utf-8")

    assert "_MapStudioGameProofDialog" in window_source
    assert "mapStudioProofManifestLineEdit" in window_source
    assert "mapStudioProofEvidenceLineEdit" in window_source
    assert "mapStudioProofModuleLoadsCheckBox" in window_source
    assert "self.readiness_panel.gameTestRequested.connect(self.record_game_smoke_proof)" in window_source
    assert "self.controller.record_map_studio_game_proof(**values)" in window_source
    assert "mapStudioRecordGameProofButton" in panel_source
    assert "record_map_studio_game_proof" in controller_source
    assert "record_dev_module_game_proof" in controller_source
    assert "record_authored_module_game_proof" in controller_source
