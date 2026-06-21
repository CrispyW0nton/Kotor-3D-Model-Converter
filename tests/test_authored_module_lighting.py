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


def test_t2693_room_light_persists_in_kmap_and_readiness() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload, authored_project_to_kmap_payload
    from src.core.modules.authored_module_lighting import add_authored_room_light
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grlight", game="K1")
    project = add_authored_room_light(
        project,
        name="warm_key",
        position=(1.0, 2.0, 2.5),
        color=(1.0, 0.82, 0.48),
        radius=10.0,
        intensity=1.25,
        light_type="point",
    ).project
    payload = authored_project_to_kmap_payload(project)
    roundtrip = authored_project_from_kmap_payload(payload)
    readiness = build_authored_module_readiness(roundtrip)
    toolchain = {step.name: step for step in readiness.toolchain}

    assert payload["lights"][0]["name"] == "warm_key"
    assert roundtrip.lights[0].position == (1.0, 2.0, 2.5)
    assert readiness.metadata["lighting_count"] == 1
    assert readiness.metadata["room_lights"][0]["light_type"] == "point"
    assert toolchain["Lighting"].status == "1 authored light(s)"
    assert any(item.name == "Room lighting" and item.value_label == "1 authored light(s)" for item in readiness.inputs)


def test_t2693_invalid_room_light_blocks_missing_room() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_module_lighting import add_authored_room_light
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grlight", game="K1")

    with pytest.raises(ValueError, match="targets missing room missing_room"):
        add_authored_room_light(project, room_resref="missing_room", name="bad_light")


def test_t2693_controller_adds_room_light_and_clears_runtime_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlight")
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grlight.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.add_authored_room_light(
        name="fill_light",
        position=(0.0, 0.0, 2.25),
        color=(0.65, 0.75, 1.0),
        light_type="spot",
    )
    updated = controller.project.extra_sections["authored_module"]

    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["lights"][-1]["name"] == "fill_light"
    assert result.readiness is not None
    assert result.readiness.metadata["lighting_count"] == 1


def test_t2694_controller_lists_and_moves_authored_room_lights() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlight")
    controller.add_authored_room_light(name="selectable_key", position=(0.0, 0.0, 2.25))

    row = controller.authored_room_lights()[0]
    result = controller.set_authored_room_light_transform(row.light_id, position=(1.5, -0.5, 2.75))
    moved = controller.authored_room_lights()[0]

    assert row.light_id == "authored_light:selectable_key"
    assert moved.position == (1.5, -0.5, 2.75)
    assert result.readiness is not None
    assert result.readiness.metadata["room_lights"][0]["position"] == [1.5, -0.5, 2.75]


def test_t2600_controller_edits_selected_room_light_properties() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlight")
    controller.add_authored_room_light(name="key_light", position=(0.0, 0.0, 2.25))
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grlight.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    result = controller.set_authored_room_light_properties(
        "authored_light:key_light",
        light_type="spot",
        color=(0.25, 0.5, 1.0),
        radius=12.5,
        intensity=1.75,
    )
    updated = controller.project.extra_sections["authored_module"]
    row = controller.authored_room_lights()[0]

    assert row.light_type == "spot"
    assert row.color == (0.25, 0.5, 1.0)
    assert row.radius == 12.5
    assert row.intensity == 1.75
    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert result.readiness is not None
    assert result.readiness.metadata["room_lights"][0]["light_type"] == "spot"
    assert result.readiness.metadata["room_lights"][0]["color"] == [0.25, 0.5, 1.0]


def test_t2600_room_light_rename_duplicate_and_remove_update_project() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_lighting import (
        add_authored_room_light,
        authored_room_light_rows,
        duplicate_authored_room_light,
        remove_authored_room_light,
        rename_authored_room_light,
        update_authored_room_light_properties,
    )
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grlight", game="K1")
    project = add_authored_room_light(project, name="key_light", position=(1.0, 2.0, 2.5)).project

    renamed = rename_authored_room_light(project, "authored_light:key_light", name="warm_key")
    edited = update_authored_room_light_properties(
        renamed.project,
        "authored_light:warm_key",
        color=(0.85, 0.72, 0.35),
        radius=9.5,
        intensity=1.5,
        light_type="spot",
    )
    duplicated = duplicate_authored_room_light(edited.project, "authored_light:warm_key")
    removed = remove_authored_room_light(duplicated.project, "authored_light:warm_key")
    rows = authored_room_light_rows(removed.project)

    assert renamed.light.name == "warm_key"
    assert renamed.light_id == "authored_light:warm_key"
    assert edited.light.color == (0.85, 0.72, 0.35)
    assert edited.light.radius == 9.5
    assert edited.light.intensity == 1.5
    assert edited.light.light_type == "spot"
    assert duplicated.light.name == "warm_key_copy"
    assert duplicated.light_id == "authored_light:warm_key_copy"
    assert duplicated.light.position == (1.5, 2.5, 2.5)
    assert removed.light.name == "warm_key"
    assert removed.count == 1
    assert rows[0].light_id == "authored_light:warm_key_copy"


def test_t2600_controller_room_light_edit_actions_clear_export_and_proof_state() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grlight")
    controller.add_authored_room_light(name="key_light", position=(0.0, 0.0, 2.25))
    payload = dict(controller.project.extra_sections["authored_module"])
    payload["runtime_resources"] = ["grlight.git"]
    payload["game_tested"] = True
    controller.project.extra_sections["authored_module"] = payload

    renamed = controller.rename_authored_room_light("authored_light:key_light", name="warm_key")
    duplicated = controller.duplicate_authored_room_light("authored_light:warm_key")
    controller.model.select(duplicated.light_id)
    removed = controller.remove_authored_room_light(duplicated.light_id)
    updated = controller.project.extra_sections["authored_module"]

    assert renamed.light.name == "warm_key"
    assert duplicated.light_id == "authored_light:warm_key_copy"
    assert removed.light.name == "warm_key_copy"
    assert updated["runtime_resources"] == []
    assert updated["game_tested"] is False
    assert updated["lights"][0]["name"] == "warm_key"
    assert controller.project.dirty is True


def test_t2693_export_manifest_records_room_lighting_intent(tmp_path: Path) -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_lighting import add_authored_room_light
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(preset_id="rectangular_dev_room", module_root="grlight", game="K1")
    project = add_authored_room_light(project, name="export_key", intensity=2.0).project
    build = build_authored_module(project)

    assert build.metadata["lighting_count"] == 1
    assert build.metadata["room_lights"][0]["name"] == "export_key"
    assert build.metadata["room_lights"][0]["intensity"] == 2.0


def test_t2693_builder_tab_exposes_room_light_controls() -> None:
    repo = Path(__file__).resolve().parents[1]
    source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
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
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")
    readiness_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "panels"
        / "module_editor"
        / "readiness_panel.py"
    ).read_text(encoding="utf-8")

    assert "Room Lighting" in source
    assert "mapStudioRoomLightNameLineEdit" in source
    assert "mapStudioRoomLightTypeComboBox" in source
    assert "mapStudioAddRoomLightButton" in source
    assert "roomLightRequested" in source
    assert "self.builder_tab.roomLightRequested.connect(self.add_authored_room_light)" in window_source
    assert "self.controller.add_authored_room_light" in window_source
    assert "lighting_count" in readiness_source
    assert "room light(s)" in readiness_source


def test_t2694_module_editor_surfaces_room_lights_as_selectable_rows() -> None:
    repo = Path(__file__).resolve().parents[1]
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
    viewport_panel_source = (
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

    assert "Authored Room Lights" in outliner_source
    assert "authored_room_light" in outliner_source
    assert "Authored Room Light" in properties_source
    assert "_authored_room_lights" in properties_source
    assert "self.name_edit.setEnabled(True)" in properties_source
    assert "Authored Room Light" in viewport_panel_source
    assert "authored_room_lights = self.controller.authored_room_lights()" in window_source
    assert "self.controller.set_authored_room_light_transform(" in window_source
    assert "rename_authored_room_light" in window_source
