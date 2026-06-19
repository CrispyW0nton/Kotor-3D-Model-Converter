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


def test_t2650_room_primitive_presets_are_named_and_stable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_room_presets import available_authored_room_primitive_presets

    presets = available_authored_room_primitive_presets()
    ids = {preset.preset_id for preset in presets}

    assert {"rectangular_dev_room", "doorway_blockout", "wide_hall", "octagonal_room", "terrain_heightfield"} <= ids
    assert all(preset.label for preset in presets)
    assert all(len(preset.points) >= 3 for preset in presets)


def test_t2650_doorway_preset_builds_exportable_authored_module() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="doorway_blockout",
        module_root="grdoor01",
        game="K1",
    )
    build = build_authored_module(project)

    primitive = project.rooms[0].primitive
    assert project.module_root == "grdoor01"
    assert primitive.room_resref == "grdoor01_room01"
    assert primitive.openings[0].name == "south_doorway"
    assert not build.blocking_issues
    assert ("grdoor01", "are") in build.resources
    assert ("grdoor01", "git") in build.resources
    assert ("module", "ifo") in build.resources
    assert ("grdoor01", "lyt") in build.resources
    assert ("grdoor01", "vis") in build.resources
    assert ("grdoor01_room01", "wok") in build.resources
    assert ("grdoor01_room01", "mdl") in build.resources
    assert ("grdoor01_room01", "mdx") in build.resources
    assert build.module_root == "grdoor01"


def test_t2650_controller_stores_room_preset_as_kmap_authored_module() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K2")

    result = controller.create_authored_room_preset_module(preset_id="octagonal_room", module_root="groct01")

    payload = controller.project.extra_sections["authored_module"]
    assert controller.project.name == "groct01"
    assert controller.project.game == "K2"
    assert controller.project.dirty is True
    assert payload["module_root"] == "groct01"
    assert payload["rooms"][0]["primitive"]["type"] == "floor_plan"
    assert payload["rooms"][0]["primitive"]["metadata"]["preset_id"] == "octagonal_room"
    assert len(payload["rooms"][0]["primitive"]["points"]) == 8
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2650_builder_tab_exposes_room_preset_controls() -> None:
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

    assert "mapStudioRoomPrimitivePresetComboBox" in source
    assert "mapStudioCreatePrimitiveRoomButton" in source
    assert "primitivePresetRequested" in source
    assert "self.builder_tab.set_primitive_presets(self.controller.available_authored_room_presets())" in window_source
    assert "self.builder_tab.primitivePresetRequested.connect(self.create_authored_room_preset)" in window_source


def test_t2907_terrain_preset_builds_valid_terrain_project() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_project import compile_authored_room_spec, validate_authored_module_project
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="terrain_heightfield",
        module_root="grterr01",
        game="K1",
    )
    validation = validate_authored_module_project(project)
    geometry = compile_authored_room_spec(project.rooms[0])

    assert validation.ok
    assert project.metadata.metadata["room_geometry_mode"] == "terrain_heightfield"
    assert project.rooms[0].metadata["primitive"] == "terrain_heightfield"
    assert project.rooms[0].primitive.metadata["preset_id"] == "terrain_heightfield"
    assert geometry.metadata["primitive"] == "terrain_heightfield"
    assert geometry.room_mesh.metadata["source"] == "src.core.modules.authored_terrain_builder"
    assert geometry.wok.walkable_face_count() > 0
    assert geometry.wok.non_walk_face_count() == 0


def test_t2907_controller_stores_terrain_preset_as_kmap_authored_module() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")

    result = controller.create_authored_room_preset_module(preset_id="terrain_heightfield", module_root="grterr02")
    payload = controller.project.extra_sections["authored_module"]

    assert controller.project.name == "grterr02"
    assert controller.project.dirty is True
    assert payload["module_root"] == "grterr02"
    assert payload["rooms"][0]["primitive"]["type"] == "terrain_heightfield"
    assert payload["rooms"][0]["primitive"]["metadata"]["preset_id"] == "terrain_heightfield"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
