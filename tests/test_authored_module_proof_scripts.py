from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE_SCRIPT = ROOT / "scripts" / "stage_authored_module_from_kmap.py"
PROOF_SCRIPT = ROOT / "scripts" / "record_authored_module_game_proof.py"


def _install_native_payload_paths() -> None:
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
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _write_authored_kmap(path: Path) -> None:
    _install_native_payload_paths()
    from src.core.level import new_kmap_project
    from src.core.level.kmap_serializer import KMapSerializer
    from src.core.modules.authored_module_kmap_bridge import create_dev_test_authored_module_payload

    project = new_kmap_project(name="grdev01", game="K1")
    project.extra_sections["authored_module"] = create_dev_test_authored_module_payload(module_root="grdev01", game="K1")
    KMapSerializer.save(project, path)


def _write_empty_kmap(path: Path) -> None:
    _install_native_payload_paths()
    from src.core.level import new_kmap_project
    from src.core.level.kmap_serializer import KMapSerializer

    KMapSerializer.save(new_kmap_project(name="empty", game="K1"), path)


def test_t2645_stages_authored_kmap_module_as_json(tmp_path: Path) -> None:
    kmap_path = tmp_path / "grdev01.kmap"
    _write_authored_kmap(kmap_path)

    result = _run(STAGE_SCRIPT, "--kmap", str(kmap_path), "--output-dir", str(tmp_path / "stage"), "--json")

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "staged_for_manual_install"
    assert payload["module_root"] == "grdev01"
    assert Path(payload["module_path"]).is_file()
    assert Path(payload["pack_manifest_path"]).is_file()
    assert Path(payload["checklist_path"]).is_file()
    assert Path(payload["proof_manifest_path"]).is_file()
    assert {"are", "git", "ifo", "lyt", "vis", "wok", "mdl", "mdx"} <= {item["restype"] for item in payload["resources"]}

    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is False
    assert authored["remaining_acceptance"]
    assert authored["package_verification"]["ok"] is True


def test_t2645_stage_script_blocks_kmap_without_authored_module(tmp_path: Path) -> None:
    kmap_path = tmp_path / "empty.kmap"
    _write_empty_kmap(kmap_path)

    result = _run(STAGE_SCRIPT, "--kmap", str(kmap_path), "--output-dir", str(tmp_path / "stage"), "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "authored_module_missing"
    assert "authored_module section" in payload["message"]


def test_t2645_records_authored_module_game_proof_from_script(tmp_path: Path) -> None:
    kmap_path = tmp_path / "grdev01.kmap"
    _write_authored_kmap(kmap_path)
    stage = _run(STAGE_SCRIPT, "--kmap", str(kmap_path), "--output-dir", str(tmp_path / "stage"), "--json")
    assert stage.returncode == 0, stage.stderr + stage.stdout
    stage_payload = json.loads(stage.stdout)
    evidence = tmp_path / "grdev01_authored_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = _run(
        PROOF_SCRIPT,
        "--proof-manifest",
        stage_payload["proof_manifest_path"],
        "--evidence",
        str(evidence),
        "--tester",
        "pytest",
        "--module-loads-in-game",
        "--player-spawns-on-floor",
        "--test-placeable-visible",
        "--player-can-walk-on-floor",
        "--json",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["code"] == "game_proof_recorded"
    assert payload["missing_checks"] == []
    proof = json.loads(Path(stage_payload["proof_manifest_path"]).read_text(encoding="utf-8"))
    assert proof["manual_proof_required"] is False
    assert proof["game_tested"] is True
    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is True
    assert authored["capability_stage"] == "game_smoke_tested"
    assert authored["remaining_acceptance"] == []


def test_t2645_authored_proof_script_keeps_module_unproven_when_checks_missing(tmp_path: Path) -> None:
    kmap_path = tmp_path / "grdev01.kmap"
    _write_authored_kmap(kmap_path)
    stage = _run(STAGE_SCRIPT, "--kmap", str(kmap_path), "--output-dir", str(tmp_path / "stage"), "--json")
    assert stage.returncode == 0, stage.stderr + stage.stdout
    stage_payload = json.loads(stage.stdout)
    evidence = tmp_path / "grdev01_authored_warp_proof.png"
    evidence.write_bytes(b"fake screenshot bytes")

    result = _run(
        PROOF_SCRIPT,
        "--proof-manifest",
        stage_payload["proof_manifest_path"],
        "--evidence",
        str(evidence),
        "--tester",
        "pytest",
        "--module-loads-in-game",
        "--json",
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "game_proof_incomplete"
    assert "player_spawns_on_floor" in payload["missing_checks"]
    assert "test_placeable_visible" in payload["missing_checks"]
    assert "player_can_walk_on_floor" in payload["missing_checks"]
    pack_manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
    authored = pack_manifest["map_studio_authored_module"]
    assert authored["game_tested"] is False
    assert authored["remaining_acceptance"]
