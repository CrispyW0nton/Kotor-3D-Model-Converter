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


def test_t2652_room_style_updates_floor_plan_material_surface_and_export() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_room_style import update_authored_room_style

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grmat01",
        game="K1",
    )

    update = update_authored_room_style(project, texture="LME_Floor01.tga", floor_surface="metal")
    build = build_authored_module(update.project)
    room = update.project.rooms[0]
    geometry = build.module.room_geometry[room.normalised_resref()]

    assert update.texture == "LME_Floor01"
    assert update.floor_surface_id == 10
    assert room.primitive.material.texture == "LME_Floor01"
    assert geometry.room_mesh.texture == "LME_Floor01"
    assert {face.surface for face in geometry.wok.faces} == {10}
    assert not build.blocking_issues
    assert (room.normalised_resref(), "wok") in build.resources


def test_t2652_room_style_updates_rectangular_smoke_room_and_invalidates_composition() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, create_dev_test_authored_module_payload
    from src.core.modules.authored_room_style import update_authored_room_style

    project = authored_project_from_kmap_payload(create_dev_test_authored_module_payload(module_root="grstone01", game="K1"))

    update = update_authored_room_style(project, texture="CM_Test_Floor", floor_surface=4)
    room = update.project.rooms[0]
    build = build_authored_module(update.project)
    geometry = build.module.room_geometry[room.normalised_resref()]

    assert room.composition is None
    assert room.primitive.texture == "CM_Test_Floor"
    assert geometry.room_mesh.texture == "CM_Test_Floor"
    assert {face.surface for face in geometry.wok.faces} == {4}


def test_t2652_controller_style_update_stores_kmap_and_clears_runtime_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")
    controller.create_authored_room_preset_module(preset_id="wide_hall", module_root="grstyle01")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grstyle01.are"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.apply_authored_room_style(texture="CM_NewWall", floor_surface="sand")
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["rooms"][0]["primitive"]["material"]["texture"] == "CM_NewWall"
    assert updated["rooms"][0]["primitive"]["floor_surface_id"] == 20
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2652_invalid_surface_blocks_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset
    from src.core.modules.authored_room_style import update_authored_room_style

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grbad01",
        game="K1",
    )

    with pytest.raises(ValueError, match="Unknown KOTOR walkmesh surface"):
        update_authored_room_style(project, texture="CM_Baremetal", floor_surface="not_a_surface")


def test_t2652_builder_tab_exposes_room_style_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.GUI.Boundary.Panels"
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
        / "GhostRigger.Windows.Editor.Level"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")

    assert "mapStudioRoomTextureLineEdit" in source
    assert "mapStudioRoomSurfaceComboBox" in source
    assert "mapStudioApplyRoomStyleButton" in source
    assert "roomStyleRequested" in source
    assert "self.builder_tab.set_walkmesh_surfaces(self.controller.available_authored_walkmesh_surfaces())" in window_source
    assert "self.builder_tab.roomStyleRequested.connect(self.apply_authored_room_style)" in window_source
    assert "self.controller.apply_authored_room_style" in window_source
