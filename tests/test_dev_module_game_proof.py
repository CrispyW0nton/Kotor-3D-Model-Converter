from __future__ import annotations

import json
import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Resources.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene.Walkmesh/Python",
        "native/GhostRigger.Core.Math.Geometry/Python",
        "native/GhostRigger.Core.Math.Camera/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2610_records_complete_in_game_smoke_proof(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleGameProofRequest,
        DevModuleInstallPrepRequest,
        prepare_dev_test_module_install,
        record_dev_module_game_proof,
    )

    prep = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))
    evidence = tmp_path / "grdev01_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
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
    assert result.missing_checks == []

    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is False
    assert proof["game_tested"] is True
    assert proof["game_test"]["accepted"] is True
    assert proof["game_test"]["evidence_path"] == str(evidence)

    pack_manifest = json.loads(Path(result.pack_manifest_path).read_text(encoding="utf-8"))
    smoke = pack_manifest["map_studio_smoke_test"]
    assert smoke["game_tested"] is True
    assert smoke["capability_stage"] == "game_smoke_tested"
    assert smoke["in_game_proof"]["checks"]["player_can_walk_on_floor"] is True


def test_t2610_missing_evidence_keeps_smoke_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleGameProofRequest,
        DevModuleInstallPrepRequest,
        prepare_dev_test_module_install,
        record_dev_module_game_proof,
    )

    prep = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))
    missing_evidence = tmp_path / "missing_video.mp4"

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(missing_evidence),
            tester="pytest",
            module_loads_in_game=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
        )
    )

    assert result.ok is False
    assert result.code == "game_proof_incomplete"
    assert result.missing_checks == ["screenshot_or_video_captured"]

    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is True
    assert proof["game_tested"] is False
    assert proof["game_test"]["accepted"] is False

    pack_manifest = json.loads(Path(result.pack_manifest_path).read_text(encoding="utf-8"))
    smoke = pack_manifest["map_studio_smoke_test"]
    assert smoke["game_tested"] is False
    assert smoke["in_game_proof"]["missing_checks"] == ["screenshot_or_video_captured"]


def test_t2601_unsupported_evidence_file_keeps_smoke_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleGameProofRequest,
        DevModuleInstallPrepRequest,
        prepare_dev_test_module_install,
        record_dev_module_game_proof,
    )

    prep = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))
    evidence = tmp_path / "not_a_screenshot.txt"
    evidence.write_text("I saw it work", encoding="utf-8")

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
        )
    )

    assert result.ok is False
    assert result.missing_checks == ["screenshot_or_video_captured"]
    proof = json.loads(Path(prep.proof_manifest_path).read_text(encoding="utf-8"))
    assert proof["game_tested"] is False
    assert proof["game_test"]["checks"]["screenshot_or_video_captured"] is False


def test_t2601_empty_image_evidence_keeps_smoke_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleGameProofRequest,
        DevModuleInstallPrepRequest,
        prepare_dev_test_module_install,
        record_dev_module_game_proof,
    )

    prep = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))
    evidence = tmp_path / "empty_proof.png"
    evidence.write_bytes(b"")

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(evidence),
            tester="pytest",
            module_loads_in_game=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
        )
    )

    assert result.ok is False
    assert result.missing_checks == ["screenshot_or_video_captured"]


def test_t2610_allow_missing_evidence_keeps_smoke_module_unproven(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.dev_module_smoke import (
        DevModuleGameProofRequest,
        DevModuleInstallPrepRequest,
        prepare_dev_test_module_install,
        record_dev_module_game_proof,
    )

    prep = prepare_dev_test_module_install(DevModuleInstallPrepRequest(output_dir=str(tmp_path)))
    missing_evidence = tmp_path / "missing_video.mp4"

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
            proof_manifest_path=prep.proof_manifest_path,
            evidence_path=str(missing_evidence),
            tester="pytest",
            module_loads_in_game=True,
            player_spawns_on_floor=True,
            test_placeable_visible=True,
            player_can_walk_on_floor=True,
            allow_missing_evidence=True,
        )
    )

    assert result.ok is False
    assert result.code == "game_proof_incomplete"
    assert result.missing_checks == ["screenshot_or_video_captured"]
