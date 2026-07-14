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
    from src.core.modules.authored_gameplay_preview import authored_gameplay_preview_markers
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
    creature_row = next(row for row in rows if row.kind == "creature")
    placeable_row = next(row for row in rows if row.kind == "placeable")
    store_row = next(row for row in rows if row.kind == "store")
    markers = authored_gameplay_preview_markers(project)
    marker_ids = {marker.placement_id for marker in markers}

    assert creature_row.placement_id.startswith("authored:creature:i_")
    # Preset fixtures without an editor identity retain their legacy selector
    # until the KMAP bridge migrates them on save/open.
    assert placeable_row.placement_id == authored_gameplay_placement_id("placeable", 0)
    assert store_row.placement_id.startswith("authored:store:i_")
    assert creature_row.placement_id in row_ids
    assert store_row.placement_id in row_ids
    # Vanilla 202TEL GIT stores are spatial: struct 11 carries ResRef +
    # XPosition/YPosition/ZPosition + orientation (tag lives in the UTM).
    assert store_row.is_spatial is True
    assert store_row.placement_id not in marker_ids
    assert parse_authored_gameplay_placement_id("authored:creature:0") == ("creature", 0)
    assert parse_authored_gameplay_placement_id(creature_row.placement_id) == (
        "creature",
        creature_row.placement_id.rsplit(":", 1)[-1],
    )


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
    original_id = next(row.placement_id for row in authored_gameplay_placement_rows(project) if row.kind == "creature")

    renamed = rename_authored_gameplay_placement(project, original_id, tag="guard_renamed")
    duplicated = duplicate_authored_gameplay_placement(renamed.project, original_id)
    removed = remove_authored_gameplay_placement(duplicated.project, original_id)
    rows = authored_gameplay_placement_rows(removed.project)

    creature_rows = [row for row in rows if row.kind == "creature"]

    assert renamed.project.placements.creatures[0].tag == "guard_renamed"
    assert duplicated.placement_id.startswith("authored:creature:i_")
    assert duplicated.placement_id != original_id
    assert duplicated.project.placements.creatures[1].tag == "guard_renamed_copy"
    assert duplicated.project.placements.creatures[1].position == (1.5, 2.5, 0.0)
    assert removed.count == 1
    assert len(creature_rows) == 1
    assert creature_rows[0].placement_id == duplicated.placement_id
    assert creature_rows[0].tag == "guard_renamed_copy"


def test_t2600_spatial_store_can_be_renamed_duplicated_and_removed() -> None:
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
        module_root="grstore",
        game="K1",
    )
    project = add_authored_gameplay_placement(
        project,
        kind="merchant",
        template_resref="stm_shop",
        tag="store_a",
    ).project
    original_id = next(row.placement_id for row in authored_gameplay_placement_rows(project) if row.kind == "store")

    renamed = rename_authored_gameplay_placement(project, original_id, tag="store_renamed")
    duplicated = duplicate_authored_gameplay_placement(renamed.project, original_id)
    removed = remove_authored_gameplay_placement(duplicated.project, original_id)
    rows = authored_gameplay_placement_rows(removed.project)
    store_rows = [row for row in rows if row.kind == "store"]

    assert renamed.project.placements.stores[0].tag == "store_renamed"
    assert duplicated.placement_id.startswith("authored:store:i_")
    assert duplicated.placement_id != original_id
    assert duplicated.project.placements.stores[1].tag == "store_renamed_copy"
    assert removed.count == 1
    assert len(store_rows) == 1
    assert store_rows[0].placement_id == duplicated.placement_id
    assert store_rows[0].tag == "store_renamed_copy"
    # Stores follow the vanilla 202TEL GIT engine contract and are spatial.
    assert store_rows[0].is_spatial is True


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

    original_id = next(row.placement_id for row in controller.authored_gameplay_placements() if row.kind == "creature")
    renamed = controller.rename_authored_gameplay_placement(original_id, tag="grctledit_renamed")
    duplicated = controller.duplicate_authored_gameplay_placement(original_id)
    controller.model.select(duplicated.placement_id)
    removed = controller.remove_authored_gameplay_placement(duplicated.placement_id)
    updated = controller.project.extra_sections["authored_module"]

    assert renamed.tag == "grctledit_renamed"
    assert duplicated.placement_id.startswith("authored:creature:i_")
    assert duplicated.placement_id != original_id
    assert removed.tag == "grctledit_renamed_copy"
    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["creatures"][0]["tag"] == "grctledit_renamed"
    assert controller.project.dirty is True


def test_t2600_controller_transition_edit_clears_export_and_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctlink")
    controller.add_authored_gameplay_placement(
        kind="door",
        template_resref="door_t01",
        tag="exit_door",
        position=(1.0, 0.0, 0.0),
    )
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grctlink.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.set_authored_gameplay_transition(
        "authored:door:0",
        linked_to="wp_next_start",
        linked_to_module="grnext",
        linked_to_flags=2,
        transition_destination=2,
    )
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["doors"][0]["linked_to"] == "wp_next_start"
    assert updated["placements"]["doors"][0]["linked_to_module"] == "grnext"
    assert updated["placements"]["doors"][0]["linked_to_flags"] == 2
    assert updated["placements"]["doors"][0]["transition_destination"] == 2
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert controller.project.dirty is True


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
    assert "transition_summary" in viewport_source
    assert "Authored Gameplay" in outliner_source
    assert "authored_gameplay" in outliner_source
    assert "transition_summary" in outliner_source
    assert "_authored_placements" in properties_source
    assert "is_spatial" in properties_source
    assert "module-level resource" in properties_source
    assert "transition_summary" in properties_source
    # T2605: item_id, LinkedTo, LinkedToModule, LinkedToFlags (destination
    # door/waypoint type), and the TransitionDestin StringRef.
    assert "transitionChanged = QtCore.Signal(str, str, str, int, int)" in properties_source
    assert "mapStudioTransitionPropertiesGroup" in properties_source
    assert "mapStudioTransitionLinkedToLineEdit" in properties_source
    assert "mapStudioTransitionLinkedModuleLineEdit" in properties_source
    assert "mapStudioTransitionDestinationSpinBox" in properties_source
    assert "def _transition_changed" in properties_source
    assert "Authored {kind} Placement" in properties_source
    assert "self.name_edit.setEnabled(True)" in properties_source
    assert "self.controller.authored_gameplay_placements()" in window_source
    assert "set_authored_gameplay_placement_transform" in window_source
    assert "self.properties.transitionChanged.connect(self._set_authored_gameplay_transition)" in window_source
    assert "def _set_authored_gameplay_transition" in window_source
    assert "self.controller.set_authored_gameplay_transition" in window_source
    assert "rename_authored_gameplay_placement" in window_source
    assert 'item_id.startswith("authored:")' in window_source
    assert 'if not bool(getattr(placement, "is_spatial", True))' in viewport_source
