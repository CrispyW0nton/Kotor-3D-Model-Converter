from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Scene.Level/Python",
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


def test_t2653_add_creature_and_trigger_export_through_git() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grnpc01",
        game="K1",
    )
    creature_update = add_authored_gameplay_placement(
        project,
        kind="creature",
        template_resref="c_drdmkone",
        tag="grnpc01_test_droid",
        position=(0.0, 0.0, 0.0),
        bearing=1.57,
    )
    trigger_update = add_authored_gameplay_placement(
        creature_update.project,
        kind="trigger",
        template_resref="newgeneric001",
        tag="grnpc01_trigger",
        position=(0.5, 0.5, 0.0),
    )
    build = build_authored_module(trigger_update.project)

    assert trigger_update.project.placements.creatures[0].template_resref == "c_drdmkone"
    assert trigger_update.project.placements.triggers[0].geometry
    assert not build.blocking_issues
    assert ("grnpc01", "git") in build.resources


def test_t2653_kmap_payload_preserves_authored_gameplay_placement_types() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="wide_hall",
        module_root="grgit01",
        game="K2",
    )
    project = add_authored_gameplay_placement(project, kind="door", template_resref="door_t01", tag="exit_door", position=(2.0, 0.0, 0.0)).project
    project = add_authored_gameplay_placement(project, kind="sound", template_resref="mus_area", tag="ambient_sound", position=(0.0, 0.0, 0.0)).project
    payload = authored_project_to_kmap_payload(project)
    roundtrip = authored_project_from_kmap_payload(payload)

    assert payload["placements"]["doors"][0]["template_resref"] == "door_t01"
    assert payload["placements"]["sounds"][0]["template_resref"] == "mus_area"
    assert roundtrip.placements.doors[0].tag == "exit_door"
    assert roundtrip.placements.sounds[0].tag == "ambient_sound"


def test_t2653_controller_adds_placement_and_clears_runtime_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grctl01")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grctl01.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.add_authored_gameplay_placement(
        kind="placeable",
        template_resref="plc_torch",
        tag="grctl01_torch",
        position=(1.0, 1.0, 0.0),
    )
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["placements"]["placeables"][-1]["template_resref"] == "plc_torch"
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2653_invalid_placement_blocks_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_module_placements import add_authored_gameplay_placement
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grbadgit",
        game="K1",
    )

    with pytest.raises(ValueError, match="Unsupported authored gameplay placement kind"):
        add_authored_gameplay_placement(project, kind="magic_box", template_resref="plc_bench")
    with pytest.raises(ValueError, match="Placeable placement requires a template resref"):
        add_authored_gameplay_placement(project, kind="placeable", template_resref="")


def test_t2653_builder_tab_exposes_gameplay_placement_controls() -> None:
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
        / "builder_tab.py"
    ).read_text(encoding="utf-8")
    window_source = (
        repo
        / "native"
        / "GhostRigger.Core.Tools.ModuleEditor"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioGameplayPlacementKindComboBox" in source
    assert "mapStudioGameplayTemplateLineEdit" in source
    assert "mapStudioAddGameplayPlacementButton" in source
    assert "gameplayPlacementRequested" in source
    assert "self.builder_tab.set_gameplay_placement_kinds(self.controller.available_authored_gameplay_placement_kinds())" in window_source
    assert "self.builder_tab.gameplayPlacementRequested.connect(self.add_authored_gameplay_placement)" in window_source
    assert "self.controller.add_authored_gameplay_placement" in window_source
