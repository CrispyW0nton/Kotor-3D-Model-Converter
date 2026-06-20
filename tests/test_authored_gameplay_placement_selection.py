from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene/Python",
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


def test_t2655_authored_placement_rows_have_stable_virtual_ids() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_id,
        authored_gameplay_placement_rows,
        parse_authored_gameplay_placement_id,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grsel01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grsel01_guard",
        position=(1.0, 2.0, 0.0),
        bearing=0.25,
    ).project
    project = add_authored_gameplay_placement(
        project,
        kind="store",
        template_resref="stm_shop",
        tag="grsel01_store",
    ).project

    rows = authored_gameplay_placement_rows(project)
    row_ids = {row.placement_id for row in rows}

    assert authored_gameplay_placement_id("creature", 0) in row_ids
    assert authored_gameplay_placement_id("placeable", 0) in row_ids
    assert "authored:store:0" not in row_ids
    assert parse_authored_gameplay_placement_id("authored:creature:0") == ("creature", 0)


def test_t2655_transform_update_moves_authored_placement_and_preserves_build_contract() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        update_authored_gameplay_placement_transform,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="wide_hall",
        module_root="grmove01",
        game="K2",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grmove01_guard",
        position=(1.0, 1.0, 0.0),
    ).project

    moved = update_authored_gameplay_placement_transform(
        project,
        "authored:creature:0",
        position=(3.0, -2.0, 0.0),
        bearing=1.5,
    )
    build = build_authored_module(moved.project)

    assert moved.project.placements.creatures[0].position == (3.0, -2.0, 0.0)
    assert moved.project.placements.creatures[0].bearing == 1.5
    assert not build.blocking_issues
    assert ("grmove01", "git") in build.resources


def test_t2655_controller_transform_update_clears_stale_runtime_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctlmv")
    controller.add_authored_gameplay_placement(
        kind="creature",
        template_resref="c_drdmkone",
        tag="grctlmv_guard",
        position=(0.0, 0.0, 0.0),
    )
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grctlmv.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.set_authored_gameplay_placement_transform(
        "authored:creature:0",
        position=(2.0, 3.0, 0.0),
        bearing=0.75,
    )
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["creatures"][0]["position"] == [2.0, 3.0, 0.0]
    assert updated["placements"]["creatures"][0]["bearing"] == 0.75
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2655_module_editor_projects_authored_placements_into_selection_surfaces() -> None:
    repo = Path(__file__).resolve().parents[1]
    viewport_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")
    outliner_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "module_editor_outliner.py"
    ).read_text(encoding="utf-8")
    properties_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "module_editor_properties.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "authored_gameplay_placements" in viewport_source
    assert "Authored Gameplay" in outliner_source
    assert "authored_gameplay" in outliner_source
    assert "_authored_placements" in properties_source
    assert "Authored {kind} Placement" in properties_source
    assert "self.controller.authored_gameplay_placements()" in window_source
    assert "set_authored_gameplay_placement_transform" in window_source
    assert 'item_id.startswith("authored:")' in window_source
