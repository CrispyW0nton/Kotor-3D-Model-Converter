from __future__ import annotations

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


def test_t2654_readiness_reports_room_style_and_gameplay_counts() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_room_style import apply_authored_room_style

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grreport",
        game="K1",
    )
    project = apply_authored_room_style(project, texture="LME_Floor01", floor_surface="metal")
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="report_droid",
        position=(0.0, 0.0, 0.0),
    ).project

    readiness = build_authored_module_readiness(project)
    build = build_authored_module(project)

    assert readiness.rooms[0].texture == "LME_Floor01"
    assert readiness.rooms[0].floor_surface_id == 10
    assert readiness.rooms[0].floor_surface_name == "METAL"
    assert readiness.metadata["gameplay_counts"]["creatures"] == 1
    assert readiness.metadata["gameplay_placement_count"] == 3
    assert readiness.metadata["room_styles"][0]["texture"] == "LME_Floor01"
    assert build.metadata["gameplay_counts"]["creatures"] == 1


def test_t2654_readiness_panel_exposes_authored_summary_label() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display.Panels"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "readiness_panel.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioReadinessAuthoredSummaryLabel" in source
    assert "mapStudioReadinessToolchainLabel" in source
    assert "mapStudioReadinessGameProofLabel" in source
    assert "mapStudioReadinessProofRecorderLabel" in source
    assert "mapStudioReadinessLaunchHandoffLabel" in source
    assert "mapStudioOpenLaunchHandoffButton" in source
    assert "launchHandoffRequested" in source
    assert "gameplay_counts" in source
    assert "room_styles" in source
    assert "Pipeline:" in source
    assert "proof_status" in source
    assert "launch_helper_command" in source
    assert "elevated_launch_script_path" in source
    assert "proof_recording_script_path" in source
    assert "Elevated launcher ready" in source
    assert "Proof recorder: Ready" in source


def test_t2689_module_editor_wires_launch_handoff_button() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Windows.Editor.Level"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "self.readiness_panel.launchHandoffRequested.connect(self.open_map_studio_launch_handoff)" in source
    assert "def open_map_studio_launch_handoff" in source
    assert "elevated_launch_script_path" in source
    assert "proof_recording_script_path" in source
    assert "QDesktopServices.openUrl" in source
