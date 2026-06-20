from __future__ import annotations

import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
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


def _project_with_rooms(*rooms):
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject

    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=tuple(rooms),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="grdev01")),
    )


def test_t2606_compiles_single_room_layout_and_visibility() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import compile_authored_module_layout
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = _project_with_rooms(
        AuthoredRoomSpec(
            room_resref="grdev01_room01",
            primitive=RectangularRoomPrimitive(room_resref="grdev01_room01"),
            position=(1.0, 2.0, 3.0),
        )
    )

    layout = compile_authored_module_layout(project)

    assert layout.room_resrefs == ("grdev01_room01",)
    assert layout.metadata["source"] == "src.core.modules.authored_module_layout"
    assert layout.lyt.rooms[0].model == "grdev01_room01"
    assert layout.lyt.rooms[0].x == 1.0
    assert layout.lyt.to_text().startswith("roomcount 1")
    assert layout.vis.visibility == {"grdev01_room01": ["grdev01_room01"]}
    assert "grdev01_room01" in layout.vis.to_text()


def test_t2606_compiles_multi_room_explicit_visibility() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import compile_authored_module_layout
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    room_a = AuthoredRoomSpec(
        room_resref="grdev01_a",
        primitive=RectangularRoomPrimitive(room_resref="grdev01_a"),
        position=(0.0, 0.0, 0.0),
        visible_rooms=("grdev01_a", "grdev01_b"),
    )
    room_b = AuthoredRoomSpec(
        room_resref="grdev01_b",
        primitive=RectangularRoomPrimitive(room_resref="grdev01_b"),
        position=(10.0, 0.0, 0.0),
        visible_rooms=("grdev01_a", "grdev01_b"),
    )

    layout = compile_authored_module_layout(_project_with_rooms(room_a, room_b))

    assert layout.room_resrefs == ("grdev01_a", "grdev01_b")
    assert len(layout.lyt.rooms) == 2
    assert layout.lyt.rooms[1].x == 10.0
    assert layout.vis.visibility["grdev01_a"] == ["grdev01_a", "grdev01_b"]
    assert layout.vis.visibility["grdev01_b"] == ["grdev01_a", "grdev01_b"]


def test_t2606_layout_validation_blocks_missing_visibility_target() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import validate_authored_module_layout
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = _project_with_rooms(
        AuthoredRoomSpec(
            room_resref="grdev01_room01",
            primitive=RectangularRoomPrimitive(room_resref="grdev01_room01"),
            visible_rooms=("missing_room",),
        )
    )

    validation = validate_authored_module_layout(project)

    assert validation.ok is False
    assert "Room grdev01_room01 references missing visible room missing_room." in validation.blocking_issues


def test_t2632_compiles_authored_door_placements_to_lyt_door_hooks() -> None:
    _install_native_payload_paths()

    import math

    from src.core.modules.authored_module_layout import compile_authored_module_layout
    from src.core.modules.authored_module_objects import AuthoredDoorInstance, AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grdev01_room01",
                primitive=RectangularRoomPrimitive(room_resref="grdev01_room01"),
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdev01"),
            doors=(
                AuthoredDoorInstance(
                    template_resref="door_dev",
                    tag="door_exit",
                    position=(4.0, 0.0, 0.0),
                    bearing=math.pi * 0.5,
                ),
            ),
        ),
    )

    layout = compile_authored_module_layout(project)
    hook = layout.lyt.doorhooks[0]

    assert layout.metadata["door_hook_count"] == 1
    assert hook.name == "door_exit"
    assert hook.x == 4.0
    assert hook.y == 0.0
    assert hook.z == 0.0
    assert hook.qx == 0.0
    assert hook.qy == 0.0
    assert hook.qz == math.sin(math.pi * 0.25)
    assert hook.qw == math.cos(math.pi * 0.25)
    assert "doorhookcount 1" in layout.lyt.to_text()


def test_t2632_layout_validation_blocks_duplicate_door_hook_names() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import validate_authored_module_layout
    from src.core.modules.authored_module_objects import AuthoredDoorInstance, AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="grdev01"),
        rooms=(
            AuthoredRoomSpec(
                room_resref="grdev01_room01",
                primitive=RectangularRoomPrimitive(room_resref="grdev01_room01"),
            ),
        ),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="grdev01"),
            doors=(
                AuthoredDoorInstance(template_resref="door_a", tag="same_hook"),
                AuthoredDoorInstance(template_resref="door_b", tag="same_hook"),
            ),
        ),
    )

    validation = validate_authored_module_layout(project)

    assert validation.ok is False
    assert "Duplicate authored door hook name: same_hook" in validation.blocking_issues
