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
    assert layout.lyt.to_text().startswith("#MAXLAYOUT ASCII")
    assert "roomcount 1" in layout.lyt.to_text()
    # Rooms are implicitly visible to themselves; a synthetic self-entry
    # crashed the K2 engine's room resolver (vanilla VIS never self-refs).
    assert layout.vis.visibility == {"grdev01_room01": []}
    assert "grdev01_room01 0" in layout.vis.to_text()


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
    # Self-references are stripped (engine contract); only OTHER rooms remain.
    assert layout.vis.visibility["grdev01_a"] == ["grdev01_b"]
    assert layout.vis.visibility["grdev01_b"] == ["grdev01_a"]


def test_t2606_layout_validation_drops_missing_imported_visibility_target_with_warning() -> None:
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

    assert validation.ok is True
    assert validation.blocking_issues == ()
    assert any("missing_room" in warning and "visibility link is dropped" in warning for warning in validation.warnings)


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


def test_t2632_layout_dedupes_duplicate_door_hook_names() -> None:
    """Vanilla modules reuse door models (plcaa's man26aa_door05 x2); duplicate
    hook names warn and emission numbers the extras instead of blocking."""

    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import (
        compile_authored_module_layout,
        validate_authored_module_layout,
    )
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

    assert validation.ok is True
    assert any("same_hook" in warning for warning in validation.warnings)

    layout = compile_authored_module_layout(project)
    hook_names = [str(hook.name) for hook in layout.lyt.doorhooks]
    assert len(layout.lyt.doorhooks) == 2
    assert len(set(hook_names)) == 2
    # Every hook line carries its room (engine sscanf contract).
    assert all(hook.room == "grdev01_room01" for hook in layout.lyt.doorhooks)


def test_t2906_connects_floor_plan_openings_and_persists_vis_intent() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import (
        audit_authored_room_connections,
        authored_room_connection_hooks,
        compile_authored_module_layout,
        connect_authored_room_openings,
    )
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening

    room_a = AuthoredRoomSpec(
        room_resref="grdev01_a",
        primitive=FloorPlanRoomPrimitive(
            room_resref="grdev01_a",
            points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
            openings=(FloorPlanWallOpening(name="east_door", edge_index=1),),
        ),
    )
    room_b = AuthoredRoomSpec(
        room_resref="grdev01_b",
        primitive=FloorPlanRoomPrimitive(
            room_resref="grdev01_b",
            points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
            openings=(FloorPlanWallOpening(name="west_door", edge_index=3),),
        ),
        position=(10.0, 0.0, 0.0),
    )
    project = _project_with_rooms(room_a, room_b)
    hooks = authored_room_connection_hooks(project)
    source = next(hook for hook in hooks if hook.room_resref == "grdev01_b")
    target = next(hook for hook in hooks if hook.room_resref == "grdev01_a")

    update = connect_authored_room_openings(project, source.hook_id, target.hook_id)
    audit = audit_authored_room_connections(update.project)
    updated_b = next(room for room in update.project.rooms if room.room_resref == "grdev01_b")
    updated_a = next(room for room in update.project.rooms if room.room_resref == "grdev01_a")

    assert updated_b.position == (4.0, 0.0, 0.0)
    assert updated_b.visible_rooms == ("grdev01_a",)
    assert updated_a.visible_rooms == ("grdev01_b",)
    assert updated_b.primitive.openings[0].metadata["connected_room_resref"] == "grdev01_a"
    assert updated_a.primitive.openings[0].metadata["connected_room_resref"] == "grdev01_b"
    assert len(audit.connections) == 1
    assert audit.unconnected_hook_ids == ()
    assert audit.ready is True

    layout = compile_authored_module_layout(update.project)
    assert layout.vis.visibility["grdev01_a"] == ["grdev01_b"]
    assert layout.vis.visibility["grdev01_b"] == ["grdev01_a"]
    assert layout.metadata["room_connection_count"] == 1
    assert layout.metadata["unconnected_room_opening_count"] == 0


def test_t2906_connection_audit_keeps_windows_and_external_exits_nonblocking() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import audit_authored_room_connections
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening

    room = AuthoredRoomSpec(
        room_resref="grdev01_a",
        primitive=FloorPlanRoomPrimitive(
            room_resref="grdev01_a",
            points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
            openings=(
                FloorPlanWallOpening(name="window", edge_index=1, bottom=1.0),
                FloorPlanWallOpening(name="module_exit", edge_index=3, metadata={"external": True}),
            ),
        ),
    )

    audit = audit_authored_room_connections(_project_with_rooms(room))

    assert len(audit.hooks) == 2
    assert audit.unconnected_hook_ids == ()
    assert audit.ready is True


def test_t2906_controller_connects_openings_as_one_undoable_kmap_command() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_layout import authored_room_connection_hooks
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive, FloorPlanWallOpening
    from src.core.modules.module_editor_controller import ModuleEditorController

    project = _project_with_rooms(
        AuthoredRoomSpec(
            room_resref="grdev01_a",
            primitive=FloorPlanRoomPrimitive(
                room_resref="grdev01_a",
                points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
                openings=(FloorPlanWallOpening(name="east_door", edge_index=1),),
            ),
        ),
        AuthoredRoomSpec(
            room_resref="grdev01_b",
            primitive=FloorPlanRoomPrimitive(
                room_resref="grdev01_b",
                points=((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)),
                openings=(FloorPlanWallOpening(name="south_door", edge_index=0),),
            ),
            position=(12.0, 3.0, 0.0),
        ),
    )
    controller = ModuleEditorController()
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(project)
    hooks = authored_room_connection_hooks(project)
    source = next(hook for hook in hooks if hook.room_resref == "grdev01_b")
    target = next(hook for hook in hooks if hook.room_resref == "grdev01_a")

    update = controller.connect_authored_room_openings(
        source_hook_id=source.hook_id,
        target_hook_id=target.hook_id,
    )

    assert abs(update.rotation_degrees) == 90.0
    assert controller.command_history.undo_label == "Connect grdev01_b to grdev01_a"
    assert controller.authored_room_connection_audit().ready is True
    assert controller.can_undo_map_studio_command() is True


def test_t2906_room_grid_snap_and_geometry_aware_auto_arrange() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_layout import auto_arrange_authored_rooms, snap_authored_rooms_to_grid
    from src.core.modules.authored_module_project import AuthoredRoomSpec
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive

    project = _project_with_rooms(
        AuthoredRoomSpec(
            room_resref="grdev01_a",
            primitive=RectangularRoomPrimitive(room_resref="grdev01_a", width=4.0, depth=4.0),
            position=(1.24, 2.76, 0.5),
        ),
        AuthoredRoomSpec(
            room_resref="grdev01_b",
            primitive=RectangularRoomPrimitive(room_resref="grdev01_b", width=2.0, depth=3.0),
            position=(30.0, 30.0, 1.0),
        ),
    )

    snapped = snap_authored_rooms_to_grid(project, ("grdev01_a",), grid_size=1.0)
    assert snapped.rooms[0].position == (1.0, 3.0, 0.5)
    assert snapped.rooms[1].position == (30.0, 30.0, 1.0)

    arranged = auto_arrange_authored_rooms(snapped, spacing=1.0)
    # Rectangular authored geometry is centered at local origin. Arrangement
    # offsets each room so its exported minimum XY starts at the row cursor.
    assert arranged.rooms[0].position == (2.0, 2.0, 0.5)
    assert arranged.rooms[1].position == (6.0, 1.5, 1.0)
