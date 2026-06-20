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
    assert payload["module_contract"]["ok"] is True
    assert payload["module_contract"]["ifo"]["entry_area"] == "grdev01"
    assert payload["module_contract"]["ifo"]["area_list"] == ["grdev01"]
    assert payload["module_contract"]["expected_room"] == "grdev01_room01"
    assert payload["module_contract"]["are"]["rooms"] == ["grdev01_room01"]
    assert payload["module_contract"]["layout"]["rooms"] == ["grdev01_room01"]
    assert payload["module_contract"]["git"]["placeables"] >= 1
    assert payload["module_contract"]["walkmesh"]["walkable_face_count"] >= 1
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
    assert payload["module_contract"]["ok"] is True
    assert payload["module_contract"]["ifo"]["entry_area"] == "grdev01"
    assert payload["module_contract"]["git"]["placeables"] >= 1
    assert payload["module_contract"]["walkmesh"]["walkable_face_count"] >= 1
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


def test_t2698_status_can_write_modder_readable_smoke_report(tmp_path: Path) -> None:
    authored = _prepare_authored(tmp_path / "authored", "--dry-run")
    report_path = tmp_path / "grdev01_smoke_status.md"

    result = _status(str(authored["proof_manifest_path"]), "--write-report", str(report_path))

    assert result.returncode == 1
    text = report_path.read_text(encoding="utf-8")
    assert "# grdev01 Smoke Status" in text
    assert "## Engine Handoff Contract" in text
    assert "- Module root: `grdev01`" in text
    assert "- IFO entry area: `grdev01`" in text
    assert "- GIT placeables: `1`" in text
    assert "- WOK walkable/non-walk: `2 / 8`" in text
    assert "- [x] `module.ifo`" in text
    assert "- [ ] module_loads_in_game" in text


def test_t2698_status_surfaces_authored_gameplay_template_dependencies(tmp_path: Path) -> None:
    authored = _prepare_authored(tmp_path / "authored", "--dry-run")

    result = _status(str(authored["proof_manifest_path"]))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    templates = payload["template_dependencies"]
    labels = {
        (item["kind"], item["template_resref"], item["restype"], item["resolved"])
        for item in templates["dependencies"]
    }
    assert ("placeable", "plc_bench", "utp", None) in labels
    assert ("waypoint", "sw_startloc001", "utw", None) in labels
    assert templates["checked"] is False
    assert templates["all_required_resolved"] is False
    assert any("no valid KOTOR game root" in warning for warning in templates["warnings"])


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
    assert payload["module_contract"]["ok"] is True
    assert payload["module_contract"]["are"]["rooms"] == ["grdev01_room01"]
    assert payload["module_contract"]["layout"]["rooms"] == ["grdev01_room01"]
    assert payload["installed"]["exists"] is True
    assert payload["installed"]["matches_package"] is True
    assert payload["currentgame_cache"]["checked"] is True
    assert payload["currentgame_cache"]["exists"] is False
    assert payload["ready_for_game_launch"] is True
    assert payload["next_action"].startswith("Launch KOTOR")
    assert "evidence capture command" in payload["next_action"]
    assert payload["launch_handoff"]["warp_command"] == "warp grdev01"
    assert "launch_grdev01_smoke_test.py" in payload["launch_handoff"]["launch_helper_command"]
    assert "capture_grdev01_smoke_evidence.py" in payload["launch_handoff"]["evidence_capture_command"]
    assert payload["launch_handoff"]["proof_recording_script_path"].endswith("grdev01_record_game_proof.cmd")


def test_t2698_status_blocks_stale_currentgame_module_cache(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    authored = _prepare_authored(
        tmp_path / "authored",
        "--game-modules-dir",
        str(modules_dir),
    )
    currentgame = modules_dir.parent / "currentgame"
    currentgame.mkdir(parents=True)
    stale_cache = currentgame / "grdev01.mod"
    stale_cache.write_bytes(b"stale older module bytes")

    result = _status(str(authored["proof_manifest_path"]), "--game-modules-dir", str(modules_dir))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["currentgame_cache"]["checked"] is True
    assert payload["currentgame_cache"]["exists"] is True
    assert payload["currentgame_cache"]["matches_package"] is False
    assert payload["ready_for_game_launch"] is False
    assert any("currentgame cache contains a stale grdev01.mod" in issue for issue in payload["blocking_issues"])


def test_t2698_status_uses_room_only_authored_proof_checks(tmp_path: Path) -> None:
    modules_dir = tmp_path / "KOTOR" / "Modules"
    modules_dir.mkdir(parents=True)
    authored = _prepare_authored(
        tmp_path / "authored_room_only",
        "--game-modules-dir",
        str(modules_dir),
        "--without-test-placeable",
        "--without-start-waypoint",
    )

    result = _status(str(authored["proof_manifest_path"]), "--game-modules-dir", str(modules_dir))

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "installed_ready_for_game_test"
    assert payload["proof"]["required_checks"] == [
        "module_loads_in_game",
        "player_spawns_on_floor",
        "player_can_walk_on_floor",
        "screenshot_or_video_captured",
    ]
    assert "--test-placeable-visible" not in payload["launch_handoff"]["proof_recording_command_template"]
    assert "floor/walkability" in payload["next_action"]
    assert "floor/placeable/walkability" not in payload["next_action"]


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


def test_t2601_status_accepts_renamed_stock_room_bridge_profile(tmp_path: Path, monkeypatch) -> None:
    status_module = _load_status_module()
    from pykotor.resource.formats.gff import bytes_gff
    from pykotor.resource.formats.gff.gff_data import GFF, GFFContent, GFFList

    ifo = GFF(GFFContent.IFO)
    ifo.root.set_resref("Mod_Entry_Area", "grdev01")
    ifo.root.set_binary("Mod_ID", b"1234567890abcdef")
    areas = GFFList()
    areas.add(6).set_resref("Area_Name", "grdev01")
    ifo.root.set_list("Mod_Area_list", areas)

    are = GFF(GFFContent.ARE)
    are.root.set_string("Tag", "grdev01")
    rooms = GFFList()
    rooms.add(0).set_resref("RoomName", "m02aa_01a")
    are.root.set_list("Rooms", rooms)

    git = GFF(GFFContent.GIT)
    for field in (
        "Creature List",
        "Door List",
        "Placeable List",
        "WaypointList",
        "TriggerList",
    ):
        git.root.set_list(field, GFFList())

    payloads = {
        "module.ifo": bytes_gff(ifo),
        "grdev01.are": bytes_gff(are),
        "grdev01.git": bytes_gff(git),
        "grdev01.lyt": b"#MAXLAYOUT ASCII\nbeginlayout\nroomcount 1\nm02aa_01a 0 0 0\ndonelayout\n",
        "grdev01.vis": b"m02aa_01a 0\n",
        "grdev01.pth": b"fake pth",
        "m02aa_01a.mdl": b"fake mdl",
        "m02aa_01a.mdx": b"fake mdx",
        "m02aa_01a.wok": b"fake wok",
    }
    monkeypatch.setattr(status_module, "_archive_payloads", lambda _path: payloads)
    monkeypatch.setattr(
        status_module,
        "_wok_summary",
        lambda _data: {
            "vertex_count": 3,
            "face_count": 1,
            "walkable_face_count": 1,
            "non_walk_face_count": 0,
            "surface_counts": {"walk": 1},
        },
    )
    proof = {
        "kind": "grdev01_renamed_stock_area_clone",
        "package_module_root": "grdev01",
        "room_resref_mode": "stock_m02aa_rooms",
    }
    verification = {"resource_keys": sorted(payloads)}

    runtime = status_module._runtime_archive_summary(
        verification,
        module_path=tmp_path / "grdev01.mod",
        module_root="grdev01",
        proof=proof,
    )
    contract = status_module._module_contract_summary(
        module_path=tmp_path / "grdev01.mod",
        module_root="grdev01",
        proof=proof,
    )

    assert runtime["profile"] == "stock_rooms"
    assert runtime["missing_required_resource_keys"] == []
    assert "m02aa_01a.mdl" in runtime["required_resource_keys"]
    assert "grdev01_room01.mdl" not in runtime["required_resource_keys"]
    assert runtime["room_model_pair_ok"] is True
    assert runtime["walkmesh_key_ok"] is True
    assert contract["ok"] is True
    assert contract["profile"] == "stock_rooms"
    assert contract["expected_rooms"] == ["m02aa_01a"]
    assert contract["are"]["rooms"] == ["m02aa_01a"]
    assert contract["layout"]["rooms"] == ["m02aa_01a"]
    assert contract["git"]["placeables"] == 0
    assert contract["warnings"] == []


def test_t2601_stock_room_bridge_handoff_records_runtime_outcome() -> None:
    status_module = _load_status_module()
    handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "git_mode": "minimal_no_runtime_objects",
        },
        proof_manifest=Path("bridge_manifest.json"),
    )

    assert handoff["diagnostic_variant_id"] == "renamed_root_minimal_git"
    assert "record_grdev01_runtime_diagnostic_outcome.py" in handoff["proof_recording_command_template"]
    assert "--variant renamed_root_minimal_git" in handoff["proof_recording_command_template"]
    assert "record_authored_module_game_proof.py" not in handoff["proof_recording_command_template"]

    placeable_handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "git_mode": "minimal_with_test_placeable",
        },
        proof_manifest=Path("bridge_placeable_manifest.json"),
    )
    assert placeable_handoff["diagnostic_variant_id"] == "renamed_root_minimal_git_placeable"
    assert "--variant renamed_root_minimal_git_placeable" in placeable_handoff["proof_recording_command_template"]

    scriptless_handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "git_mode": "minimal_no_runtime_objects",
            "root_script_mode": "scriptless",
        },
        proof_manifest=Path("bridge_scriptless_manifest.json"),
    )
    assert scriptless_handoff["diagnostic_variant_id"] == "renamed_root_scriptless_minimal_git"
    assert "--variant renamed_root_scriptless_minimal_git" in scriptless_handoff["proof_recording_command_template"]

    scriptless_placeable_handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "git_mode": "minimal_with_test_placeable",
            "root_script_mode": "scriptless",
        },
        proof_manifest=Path("bridge_scriptless_placeable_manifest.json"),
    )
    assert scriptless_placeable_handoff["diagnostic_variant_id"] == "renamed_root_scriptless_minimal_git_placeable"
    assert (
        "--variant renamed_root_scriptless_minimal_git_placeable"
        in scriptless_placeable_handoff["proof_recording_command_template"]
    )

    scriptless_dual_handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "root_resource_mode": "dual_grdev01_and_m02aa_roots",
            "git_mode": "minimal_no_runtime_objects",
            "root_script_mode": "scriptless",
        },
        proof_manifest=Path("bridge_scriptless_dual_manifest.json"),
    )
    assert scriptless_dual_handoff["diagnostic_variant_id"] == "renamed_root_scriptless_dual_minimal_git"
    assert "--variant renamed_root_scriptless_dual_minimal_git" in scriptless_dual_handoff["proof_recording_command_template"]

    scriptless_dual_placeable_handoff = status_module._launch_handoff_summary(
        proof={
            "kind": "grdev01_renamed_stock_area_clone",
            "room_resref_mode": "stock_m02aa_rooms",
            "root_resource_mode": "dual_grdev01_and_m02aa_roots",
            "git_mode": "minimal_with_test_placeable",
            "root_script_mode": "scriptless",
        },
        proof_manifest=Path("bridge_scriptless_dual_placeable_manifest.json"),
    )
    assert scriptless_dual_placeable_handoff["diagnostic_variant_id"] == "renamed_root_scriptless_dual_minimal_git_placeable"
    assert (
        "--variant renamed_root_scriptless_dual_minimal_git_placeable"
        in scriptless_dual_placeable_handoff["proof_recording_command_template"]
    )
