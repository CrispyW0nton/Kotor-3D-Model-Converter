from __future__ import annotations

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


def test_t2600_authored_placement_rename_duplicate_and_remove_update_project() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_placements import (
        add_authored_gameplay_placement,
        authored_gameplay_placement_rows,
        duplicate_authored_gameplay_placement,
        remove_authored_gameplay_placement,
        rename_authored_gameplay_placement,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="gredit01",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="guard_a",
        position=(1.0, 2.0, 0.0),
    ).project

    renamed = rename_authored_gameplay_placement(project, "authored:creature:0", tag="guard_renamed")
    duplicated = duplicate_authored_gameplay_placement(renamed.project, "authored:creature:0")
    removed = remove_authored_gameplay_placement(duplicated.project, "authored:creature:0")
    rows = authored_gameplay_placement_rows(removed.project)

    creature_rows = [row for row in rows if row.kind == "creature"]

    assert renamed.project.placements.creatures[0].tag == "guard_renamed"
    assert duplicated.placement_id == "authored:creature:1"
    assert duplicated.project.placements.creatures[1].tag == "guard_renamed_copy"
    assert duplicated.project.placements.creatures[1].position == (1.5, 2.5, 0.0)
    assert removed.count == 1
    assert len(creature_rows) == 1
    assert creature_rows[0].placement_id == "authored:creature:0"
    assert creature_rows[0].tag == "guard_renamed_copy"


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


def test_t2600_controller_placement_edit_actions_clear_export_and_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctledit")
    controller.add_authored_gameplay_placement(
        kind="creature",
        template_resref="c_drdmkone",
        tag="grctledit_guard",
        position=(0.0, 0.0, 0.0),
    )
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grctledit.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    renamed = controller.rename_authored_gameplay_placement("authored:creature:0", tag="grctledit_renamed")
    duplicated = controller.duplicate_authored_gameplay_placement("authored:creature:0")
    controller.model.select(duplicated.placement_id)
    removed = controller.remove_authored_gameplay_placement(duplicated.placement_id)
    updated = controller.project.extra_sections["authored_module"]

    assert renamed.tag == "grctledit_renamed"
    assert duplicated.placement_id == "authored:creature:1"
    assert removed.tag == "grctledit_renamed_copy"
    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["creatures"][0]["tag"] == "grctledit_renamed"
    assert controller.project.dirty is True


def test_t2655_module_editor_projects_authored_placements_into_selection_surfaces() -> None:
    repo = Path(__file__).resolve().parents[1]
    viewport_source = (
        repo
        / "native"
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.Windows.Editor.Level"
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
    assert "self.name_edit.setEnabled(True)" in properties_source
    assert "self.controller.authored_gameplay_placements()" in window_source
    assert "set_authored_gameplay_placement_transform" in window_source
    assert "rename_authored_gameplay_placement" in window_source
    assert 'item_id.startswith("authored:")' in window_source
