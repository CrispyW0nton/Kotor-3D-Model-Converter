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


def test_t2651_controller_bevel_converts_rectangular_dev_room_to_floor_plan() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_dev_test_authored_module()

    result = controller.apply_authored_room_operation(operation="bevel", distance=0.25)

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "floor_plan"
    assert len(primitive["points"]) == 8
    assert primitive["metadata"]["operation"] == "bevel"
    assert payload["runtime_resources"] == []
    assert payload["game_tested"] is False
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2651_rectangular_cut_splits_current_room_and_remains_exportable() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_room_operations import apply_authored_floor_plan_operation
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="rectangular_dev_room",
        module_root="grcut01",
        game="K1",
    )
    cut = apply_authored_floor_plan_operation(
        project,
        "rectangular_cut",
        center=(0.0, 0.0),
        size=(2.0, 1.0),
        room_resref_prefix="grcutpiece",
    )
    build = build_authored_module(cut)

    assert len(cut.rooms) == 4
    assert {room.metadata["cut_piece_role"] for room in cut.rooms} == {"left", "right", "bottom", "top"}
    assert all(room.visible_rooms == tuple(room.normalised_resref() for room in cut.rooms) for room in cut.rooms)
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 4
    assert ("grcut01", "lyt") in build.resources
    assert ("grcut01", "vis") in build.resources
    assert all((room.normalised_resref(), "wok") in build.resources for room in cut.rooms)
    assert all((room.normalised_resref(), "mdl") in build.resources for room in cut.rooms)
    assert all((room.normalised_resref(), "mdx") in build.resources for room in cut.rooms)


def test_t2651_room_operation_requires_authored_module_payload() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="empty", game="K1")

    with pytest.raises(ValueError, match="No authored Map Studio module"):
        controller.apply_authored_room_operation(operation="inset", distance=0.25)


def test_t2665_controller_moves_authored_room_outline_point() -> None:
    _install_native_payload_paths()

    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="doorway_blockout", module_root="grpoint")

    result = controller.move_authored_room_outline_point(
        room_resref="grpoint_room01",
        point_index=1,
        world_position=(6.5, -4.0, 0.0),
    )

    payload = controller.project.extra_sections["authored_module"]
    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "floor_plan"
    assert primitive["points"][1] == [6.5, -4.0]
    assert primitive["metadata"]["last_vertex_edit"] == 1
    assert payload["rooms"][0]["metadata"]["last_operation"] == "move_floor_plan_point"
    assert controller.project.dirty is True
    assert result.readiness is not None
    assert result.readiness.can_preview is True


def test_t2668_controller_creates_elevation_composition_room_preset() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")

    result = controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grelev01")
    payload = controller.project.extra_sections["authored_module"]
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)

    primitive = payload["rooms"][0]["primitive"]
    assert primitive["type"] == "composition"
    assert primitive["room_resref"] == "grelev01_room01"
    assert {item["type"] for item in primitive["primitives"]} >= {"wall", "ramp", "stairs", "arch"}
    assert len([item for item in primitive["primitives"] if item["type"] == "wall"]) == 4
    assert controller.project.name == "grelev01"
    assert result.readiness is not None
    assert result.readiness.can_preview is True
    assert not build.blocking_issues
    assert build.metadata["room_count"] == 1
    assert ("grelev01_room01", "mdl") in build.resources
    assert ("grelev01_room01", "wok") in build.resources
    assert build.module.room_geometry["grelev01_room01"].metadata["walkmesh_primitive_count"] == 2
    assert build.module.room_geometry["grelev01_room01"].wok.walkable_face_count() == 6


def test_t2670_controller_sets_composition_primitive_transform_and_preserves_exportable_wok() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="scratch", game="K1")
    controller.create_authored_room_preset_module(preset_id="elevation_test_room", module_root="grprim")

    readiness = controller.set_authored_room_primitive_transform(
        room_resref="grprim_room01",
        primitive_name="grprim_room01_ramp",
        translation=(1.0, 2.0, 0.0),
        rotation_degrees_z=0.0,
        scale=(1.0, 1.0, 1.0),
    )
    payload = controller.project.extra_sections["authored_module"]
    primitive_payload = payload["rooms"][0]["primitive"]
    ramp_payload = next(item for item in primitive_payload["primitives"] if item["name"] == "grprim_room01_ramp")
    authored = authored_project_from_kmap_payload(payload)
    build = build_authored_module(authored)
    wok = build.module.room_geometry["grprim_room01"].wok

    assert readiness.readiness is not None
    assert readiness.readiness.can_preview is True
    assert controller.project.dirty is True
    assert primitive_payload["type"] == "composition"
    assert ramp_payload["transform"]["translation"] == [1.0, 2.0, 0.0]
    assert not build.blocking_issues
    assert wok.verts[4] == (0.0, 0.25, 0.0)
    assert wok.walkable_face_count() == 6


def test_t2670_transforming_missing_composition_primitive_fails_clearly() -> None:
    _install_native_payload_paths()

    import pytest

    from src.core.modules.authored_room_operations import set_authored_room_composition_primitive_transform
    from src.core.modules.authored_room_presets import create_authored_module_from_room_preset

    project = create_authored_module_from_room_preset(
        preset_id="elevation_test_room",
        module_root="grprim",
        game="K1",
    )

    with pytest.raises(ValueError, match="no primitive named 'missing_ramp'"):
        set_authored_room_composition_primitive_transform(
            project,
            room_resref="grprim_room01",
            primitive_name="missing_ramp",
            translation=(0.0, 0.0, 0.0),
        )


def test_t2651_builder_tab_exposes_room_operation_controls() -> None:
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

    assert "mapStudioRoomOperationComboBox" in source
    assert "mapStudioApplyRoomOperationButton" in source
    assert "roomOperationRequested" in source
    assert "self.builder_tab.roomOperationRequested.connect(self.apply_authored_room_operation)" in window_source
    assert "self.controller.apply_authored_room_operation" in window_source
