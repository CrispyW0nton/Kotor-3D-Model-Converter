from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "scripts" / "install_grdev01_smoke_variant.py"
PREPARE_AUTHORED_SCRIPT = ROOT / "scripts" / "prepare_grdev01_authored_smoke.py"
RECORD_SCRIPT = ROOT / "scripts" / "record_grdev01_smoke_proof.py"
STATUS_SCRIPT = ROOT / "scripts" / "check_grdev01_smoke_status.py"


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _install_variant(tmp_path: Path, *args: str) -> dict[str, object]:
    result = _run_script(
        INSTALL_SCRIPT,
        "--output-dir",
        str(tmp_path),
        "--json",
        *args,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def _prepare_authored(tmp_path: Path, *args: str) -> dict[str, object]:
    result = _run_script(
        PREPARE_AUTHORED_SCRIPT,
        "--output-dir",
        str(tmp_path),
        "--overwrite-kmap",
        "--json",
        *args,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def _status(proof_manifest: str, *args: str) -> subprocess.CompletedProcess[str]:
    return _run_script(STATUS_SCRIPT, "--proof-manifest", proof_manifest, "--json", *args)


def _load_status_module():
    spec = importlib.util.spec_from_file_location("check_grdev01_smoke_status", STATUS_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_t2619_status_reports_export_candidate_ready_for_manual_install(tmp_path: Path) -> None:
    install = _install_variant(tmp_path / "prep", "--variant", "rectangular")

    result = _status(str(install["proof_manifest_path"]))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_manual_install"
    assert payload["package_verification"]["ok"] is True
    assert payload["runtime_archive"]["engine_ifo_key_ok"] is True
    assert payload["runtime_archive"]["missing_required_resource_keys"] == []
    assert "module.ifo" in payload["runtime_archive"]["required_resource_keys"]
    assert payload["ready_for_game_launch"] is False
    assert payload["next_action"].startswith("Install/copy grdev01.mod")
    assert payload["proof"]["game_tested"] is False
    assert payload["proof"]["manual_proof_required"] is True
    assert payload["installed"]["checked"] is False
    assert payload["installed"]["package_sha256"] == payload["package_verification"]["module_sha256"]
    assert payload["launch_handoff"]["warp_command"] == "warp grdev01"
    assert payload["launch_handoff"]["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")
    assert "record_grdev01_smoke_proof.py" in payload["launch_handoff"]["proof_recording_command_template"]


def test_t2619_status_reports_installed_variant_ready_for_game_test(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    install = _install_variant(
        tmp_path / "prep",
        "--variant",
        "floor-plan",
        "--game-modules-dir",
        str(modules_dir),
    )

    result = _status(str(install["proof_manifest_path"]), "--game-modules-dir", str(modules_dir))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["package_verification"]["ok"] is True
    assert payload["installed"]["exists"] is True
    assert payload["installed"]["matches_package"] is True
    assert payload["installed"]["installed_sha256"] == payload["installed"]["package_sha256"]
    assert payload["ready_for_game_launch"] is True
    assert payload["next_action"].startswith("Launch KOTOR")
    assert payload["proof"]["game_tested"] is False
    assert payload["launch_handoff"]["elevated_launch_script_path"].endswith("grdev01_launch_kotor_as_admin.cmd")
    assert payload["launch_handoff"]["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")


def test_t2619_status_reports_game_tested_after_complete_proof(tmp_path: Path) -> None:
    install = _install_variant(tmp_path / "prep", "--variant", "rectangular")
    evidence = tmp_path / "grdev01-proof.png"
    evidence.write_bytes(b"fake screenshot")
    record = _run_script(
        RECORD_SCRIPT,
        "--proof-manifest",
        str(install["proof_manifest_path"]),
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
    assert record.returncode == 0, record.stderr + record.stdout

    result = _status(str(install["proof_manifest_path"]))

    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "game_tested"
    assert payload["ok"] is True
    assert payload["package_verification"]["ok"] is True
    assert payload["proof"]["game_tested"] is True
    assert payload["proof"]["manual_proof_required"] is False
    assert payload["proof"]["evidence_exists"] is True
    assert payload["proof"]["evidence_accepted"] is True
    assert payload["proof"]["missing_checks"] == []
    assert payload["ready_for_game_launch"] is False
    assert payload["next_action"].startswith("No action required")


def test_t2601_status_does_not_accept_unsupported_proof_evidence(tmp_path: Path) -> None:
    install = _install_variant(tmp_path / "prep", "--variant", "rectangular")
    proof_path = Path(str(install["proof_manifest_path"]))
    evidence = tmp_path / "grdev01-proof.txt"
    evidence.write_text("not screenshot/video evidence", encoding="utf-8")
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["manual_proof_required"] = False
    proof["game_tested"] = True
    proof["game_test"] = {
        "accepted": True,
        "missing_checks": [],
        "evidence_path": str(evidence),
        "checks": {
            "module_loads_in_game": True,
            "player_spawns_on_floor": True,
            "test_placeable_visible": True,
            "player_can_walk_on_floor": True,
            "screenshot_or_video_captured": True,
        },
    }
    proof_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")

    result = _status(str(proof_path))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] != "game_tested"
    assert payload["proof"]["game_tested"] is True
    assert payload["proof"]["evidence_exists"] is True
    assert payload["proof"]["evidence_accepted"] is False
    assert payload["ok"] is False


def test_t2698_status_accepts_authored_smoke_package_before_manual_install(tmp_path: Path) -> None:
    authored = _prepare_authored(tmp_path / "authored", "--dry-run")

    result = _status(str(authored["proof_manifest_path"]))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "ready_for_manual_install"
    assert payload["package_verification"]["ok"] is True
    assert payload["runtime_archive"]["missing_required_resource_keys"] == []
    assert payload["runtime_archive"]["path_key_ok"] is True
    assert payload["ready_for_game_launch"] is False
    assert payload["proof"]["missing_checks"] == [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "test_placeable_visible",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]
    assert payload["launch_handoff"]["warp_command"] == "warp grdev01"
    assert "record_authored_module_game_proof.py" in payload["launch_handoff"]["proof_recording_command_template"]
    assert "--module-loads-in-game" in payload["launch_handoff"]["proof_recording_command_template"]


def test_t2698_status_accepts_installed_authored_smoke_package(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    authored = _prepare_authored(
        tmp_path / "authored",
        "--game-modules-dir",
        str(modules_dir),
    )

    result = _status(str(authored["proof_manifest_path"]), "--game-modules-dir", str(modules_dir))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["package_verification"]["ok"] is True
    assert payload["runtime_archive"]["missing_required_resource_keys"] == []
    assert payload["installed"]["exists"] is True
    assert payload["installed"]["matches_package"] is True
    assert payload["ready_for_game_launch"] is True
    assert payload["next_action"].startswith("Launch KOTOR")
    assert "proof recording command" in payload["next_action"]
    assert payload["launch_handoff"]["warp_command"] == "warp grdev01"
    assert "launch_grdev01_smoke_test.py" in payload["launch_handoff"]["launch_helper_command"]
    assert payload["launch_handoff"]["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")


def test_t2601_status_can_include_kotormcp_module_visibility_check(tmp_path: Path, monkeypatch) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    authored = _prepare_authored(
        tmp_path / "authored",
        "--game-modules-dir",
        str(modules_dir),
    )
    status_module = _load_status_module()
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run_kotormcp_tool(name: str, arguments: dict[str, object], *, game_root_dir: str = "") -> dict[str, object]:
        calls.append((name, arguments))
        if name == "kotor_module_resources":
            return {
                "module_root": "grdev01",
                "count": 9,
                "total": 9,
                "items": [
                    {"resref": "grdev01", "type": "ARE", "extension": "are", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01", "type": "GIT", "extension": "git", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01", "type": "LYT", "extension": "lyt", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01", "type": "PTH", "extension": "pth", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01", "type": "VIS", "extension": "vis", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01_room01", "type": "MDL", "extension": "mdl", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01_room01", "type": "THG", "extension": "thg", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "grdev01_room01", "type": "WOK", "extension": "wok", "size": 10, "source": "module:grdev01.mod"},
                    {"resref": "module", "type": "IFO", "extension": "ifo", "size": 10, "source": "module:grdev01.mod"},
                ],
            }
        return {
            "module_root": "grdev01",
            "resource_count": 9,
            "type_breakdown": {
                "ARE": 1,
                "GIT": 1,
                "IFO": 1,
                "LYT": 1,
                "PTH": 1,
                "VIS": 1,
                "MDL": 1,
                "THG": 1,
                "WOK": 1,
            },
            "area_info": {"error": "I/O operation on closed file."},
        }

    monkeypatch.setattr(status_module, "_run_kotormcp_module_tool", fake_run_kotormcp_tool)

    payload = status_module.build_status(
        proof_manifest=Path(str(authored["proof_manifest_path"])),
        game_modules_dir=modules_dir,
        use_kotormcp=True,
    )

    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["kotormcp"]["checked"] is True
    assert payload["kotormcp"]["ok"] is True
    assert payload["kotormcp"]["resource_count"] == 9
    assert payload["kotormcp"]["missing_required_types"] == []
    assert payload["kotormcp"]["model_buffer_entry_type"] == "THG"
    assert payload["kotormcp"]["warnings"] == ["KotorMCP area summary warning: I/O operation on closed file."]
    assert [name for name, _args in calls] == ["kotor_module_resources", "kotor_describe_module"]
