"""Focused proof: PIE start reuses cached walkmesh and player-actor work.

On large converted modules (koq201: 9 imported rooms, ~48k triangles) every
Play press measured ~62 s: ~49 s reloading the player body/head and their
supermodel animation chains, and ~9 s recombining the module walkmesh. Both
are pure projections of unchanged state, so they are now cached — the
combined WOK per authored revision, and the composed player actor per
(manager, resource revision, game, body, head).
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_repeated_pie_requests_coalesce_without_restarting_scheduled_render() -> None:
    """A 16 ms simulation tick must not perpetually postpone one queued frame."""

    _configure_native_python_roots()
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import (
        ViewportRenderingPipelineMixin,
    )

    class _Timer:
        def __init__(self) -> None:
            self.active = True
            self.starts: list[int] = []

        def isActive(self) -> bool:  # noqa: N802 - Qt-shaped probe
            return self.active

        def start(self, delay: int) -> None:
            self.starts.append(int(delay))
            self.active = True

    class _Governor:
        def __init__(self) -> None:
            self.requests: list[tuple[str, dict[str, bool]]] = []

        def request_redraw(self, reason: str, **flags: bool) -> None:
            self.requests.append((reason, dict(flags)))

    timer = _Timer()
    governor = _Governor()
    harness = SimpleNamespace(
        _render_pending=False,
        _render_timer=timer,
        _frame_governor=governor,
        _renderer_settings=SimpleNamespace(target_fps=60),
        _dual_viewport_mode=False,
        _fast_frame_until=0.0,
        _last_render_wall=0.0,
    )

    request = ViewportRenderingPipelineMixin._request_render
    for _tick in range(20):
        request(harness, fast=True, reason="Map Studio PIE camera frame", camera=True)

    assert harness._render_pending is True
    assert len(governor.requests) == 20
    assert timer.starts == []

    timer.active = False
    request(harness, fast=True, reason="Map Studio PIE camera frame", camera=True)
    assert len(timer.starts) == 1
    assert timer.starts[0] >= 1


def test_controller_reuses_combined_walkmesh_until_authored_revision_changes(monkeypatch) -> None:
    _configure_native_python_roots()
    from src.core.modules import module_editor_controller as controller_module

    controller = controller_module.ModuleEditorController()
    controller.new_project(name="grpieperf", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grpieperf")

    calls = {"combine": 0}
    original = controller_module.combine_authored_module_walkmesh

    def counting_combine(project):
        calls["combine"] += 1
        return original(project)

    monkeypatch.setattr(controller_module, "combine_authored_module_walkmesh", counting_combine)

    first = controller.create_map_studio_pie_session()
    assert first.session is not None
    assert calls["combine"] == 1
    second = controller.create_map_studio_pie_session()
    assert second.session is not None
    assert calls["combine"] == 1

    controller.set_authored_module_entry_point(
        area_resref="grpieperf",
        position=(0.25, 0.25, 0.0),
        facing=0.0,
    )
    third = controller.create_map_studio_pie_session()
    assert third.session is not None
    # One authored mutation advances the revision and rebuilds exactly once.
    assert calls["combine"] == 2


def test_player_actor_model_is_cached_across_play_presses() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpieactor", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        loads: list[str] = []

        class _Manager:
            def load_model_strict(self, resref, game):
                loads.append(str(resref))
                return _stub_model(str(resref))

            def load_model(self, resref, game):
                return _stub_model(str(resref))

        window.resource_manager = _Manager()
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))

        window._create_map_studio_pie_player_actor(session, preview, "K1")
        first_loads = list(loads)
        assert "pmbam" in first_loads
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        # The composed actor is reused: no further strict loads on replay.
        assert loads == first_loads
        cache = window._map_studio_pie_player_model_cache
        assert len(cache) == 1
        # A different player body is a different cache entry.
        window._map_studio_pie_player_settings = lambda: ("pfbam", "pfhc01")
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert "pfbam" in loads
        assert len(cache) == 2
    finally:
        window.deleteLater()


def test_pie_runtime_player_replaces_and_restores_complete_player_start_preview() -> None:
    """PIE must never render its player over the editor Player Start character."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    root = md.ModelNode(name="map_root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="room", flags=int(md.NodeFlags.HEADER))
    player_start = md.ModelNode(name="player_start", flags=int(md.NodeFlags.HEADER))
    body = md.ModelNode(name="player_body", flags=int(md.NodeFlags.HEADER))
    head = md.ModelNode(name="player_head", flags=int(md.NodeFlags.HEADER))
    body.parent = player_start
    head.parent = player_start
    player_start.children = [body, head]
    setattr(player_start, "_gr_map_studio_placement_id", "entry_point")
    setattr(player_start, "_gr_map_studio_placement_kind", "entry_point")
    room.parent = root
    player_start.parent = root
    root.children = [room, player_start]
    preview = md.KotorModel(name="map_preview", root_node=root)
    harness = SimpleNamespace(
        _map_studio_pie_actor=object(),
        _map_studio_pie_hidden_player_start_groups=[],
    )

    ModuleEditorWindow._hide_map_studio_pie_player_start_preview(harness, preview)

    assert root.children == [room]
    assert player_start.children == [body, head]
    assert harness._map_studio_pie_hidden_player_start_groups == [(1, player_start)]

    ModuleEditorWindow._restore_map_studio_pie_player_start_preview(harness, preview)

    assert root.children == [room, player_start]
    assert player_start.parent is root
    assert harness._map_studio_pie_hidden_player_start_groups == []


def test_pie_runtime_upload_publishes_closed_door_pose_before_player_approaches() -> None:
    """Animated doors must be resident on the first PIE frame, not proximity-spawned."""

    _configure_native_python_roots()
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class _Viewport:
        def __init__(self) -> None:
            self.loaded = []
            self.runtime_rows = []

        def load_model(self, model, *, extra_texture_dirs=()):
            self.loaded.append((model, tuple(extra_texture_dirs)))

        def set_animation_playback_active(self, *_args):
            return None

        def update_runtime_character_frames(self, rows, **_kwargs):
            self.runtime_rows = list(rows)

    class _Preview:
        def compute_bounds(self):
            return None

    pose = SimpleNamespace()
    door_root = object()
    door_actor = SimpleNamespace(
        root_node=door_root,
        actor_id="__map_studio_pie_door__:authored:door:1",
        source_model=SimpleNamespace(name="dor_ond01"),
    )
    closed_animation = SimpleNamespace(name="closed", length=1.0)
    door_engine = SimpleNamespace(
        current_animation=closed_animation,
        current_time=0.0,
        evaluate=lambda: pose,
    )
    viewport = _Viewport()
    harness = SimpleNamespace(
        viewport_panel=SimpleNamespace(viewport=viewport, _project_texture_dirs=[]),
        _map_studio_pie_actor=None,
        _map_studio_pie_animation_engine=None,
        _map_studio_pie_animation_name="",
        _map_studio_pie_creature_entries=[],
        _map_studio_pie_door_entries=[{"actor": door_actor, "engine": door_engine}],
    )

    warning = ModuleEditorWindow._activate_map_studio_pie_runtime_actors(harness, _Preview())

    assert warning == ""
    assert len(viewport.runtime_rows) == 1
    assert viewport.runtime_rows[0][0] is door_root
    assert viewport.runtime_rows[0][1] == door_actor.actor_id
    assert viewport.runtime_rows[0][2] is pose
    assert viewport.runtime_rows[0][3] == "closed"
    assert getattr(pose, "_gr_animation_scene_object_id") == door_actor.actor_id


def test_pie_exploration_lod_hides_only_close_facial_layers() -> None:
    """Exploration keeps the visible head/eyes while deferring mouth close-ups."""

    _configure_native_python_roots()
    from types import SimpleNamespace

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    def node(name: str):
        return SimpleNamespace(name=name, children=[], _gr_hidden=False)

    head = node("head")
    eye = node("eyeLA")
    teeth = node("teethUa")
    tongue = node("tongue")
    lid = node("eyeLlid")
    root = node("root")
    root.children = [head, eye, teeth, tongue, lid]
    preview = SimpleNamespace(_gr_classification_revision=0)
    harness = SimpleNamespace(
        _map_studio_pie_actor=SimpleNamespace(root_node=root),
        _map_studio_pie_runtime_preview_model=preview,
    )

    ModuleEditorWindow._set_map_studio_pie_player_facial_detail_visible(harness, False)

    assert head._gr_hidden is False
    assert eye._gr_hidden is True
    assert teeth._gr_hidden is True
    assert tongue._gr_hidden is True
    assert lid._gr_hidden is True
    assert preview._gr_classification_revision == 1

    ModuleEditorWindow._set_map_studio_pie_player_facial_detail_visible(harness, True)

    assert all(node._gr_hidden is False for node in (head, eye, teeth, tongue, lid))
    assert preview._gr_classification_revision == 2


def test_pie_static_batch_reduces_authored_draw_nodes_without_mutating_edit_model() -> None:
    """Compatible architecture batches in PIE while edit-mode primitives stay separate."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import optimize_authored_preview_model_for_pie

    def mesh(name: str, texture: str, x_offset: float):
        node = md.ModelNode(
            name=name,
            flags=int(md.NodeFlags.MESH),
            vertices=[
                (x_offset + 0.0, 0.0, 0.0),
                (x_offset + 1.0, 0.0, 0.0),
                (x_offset + 0.0, 1.0, 0.0),
            ],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            face_mats=[0],
            texture=texture,
            texture_names=[texture],
        )
        setattr(node, "_gr_map_studio_authored_mesh", True)
        setattr(node, "_gr_map_studio_primitive_name", name)
        return node

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="room", flags=int(md.NodeFlags.HEADER), parent=root)
    wall_a = mesh("wall_a", "ond_wall", 0.0)
    wall_b = mesh("wall_b", "ond_wall", 1.0)
    trim = mesh("trim", "ond_trim", 2.0)
    for node in (wall_a, wall_b, trim):
        node.parent = room
    room.children = [wall_a, wall_b, trim]
    root.children = [room]
    source = md.KotorModel(name="source", root_node=root)

    optimized = optimize_authored_preview_model_for_pie(source)
    optimized_room = optimized.root_node.children[0]
    summary = getattr(optimized, "_gr_map_studio_pie_static_batch_summary")

    assert len(source.root_node.children[0].children) == 3
    assert [node.name for node in source.root_node.children[0].children] == ["wall_a", "wall_b", "trim"]
    assert len(optimized_room.children) == 2
    assert summary == {
        "source_meshes": 3,
        "runtime_batches": 2,
        "draw_calls_saved": 1,
        "rehydrated_meshes_suppressed": 0,
    }
    wall_batch = next(node for node in optimized_room.children if node.texture == "ond_wall")
    assert len(wall_batch.vertices) == 6
    assert wall_batch.faces == [(0, 1, 2), (3, 4, 5)]
    assert getattr(wall_batch, "_gr_map_studio_pie_batch_source_count") == 2


def test_pie_static_batch_preserves_flattened_placeable_meshes_for_culling() -> None:
    """UTP pieces stay separate so their small bounds can be culled independently."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    placeable = md.ModelNode(
        name="placeable_console",
        flags=int(md.NodeFlags.HEADER),
        parent=root,
    )
    setattr(placeable, "_gr_map_studio_placement_kind", "placeable")

    meshes = []
    for index in range(3):
        node = md.ModelNode(
            name=f"console_part_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=placeable,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            face_mats=[0],
            texture="plc_console",
            texture_names=["plc_console"],
        )
        setattr(node, "_gr_map_studio_stock_mesh", True)
        meshes.append(node)
    meshes[-1].controllers = [{"type": "position"}]
    placeable.children = meshes
    root.children = [placeable]
    source = md.KotorModel(name="source", root_node=root)

    optimized = optimize_authored_preview_model_for_pie(source)
    optimized_meshes = optimized.root_node.children[0].children

    assert len(source.root_node.children[0].children) == 3
    assert len(optimized_meshes) == 3
    assert [node.name for node in optimized_meshes] == [
        "console_part_0",
        "console_part_1",
        "console_part_2",
    ]
    assert optimized._gr_map_studio_pie_static_batch_summary == {
        "source_meshes": 0,
        "runtime_batches": 0,
        "draw_calls_saved": 0,
        "rehydrated_meshes_suppressed": 0,
    }


def test_pie_static_batch_compacts_closed_door_proxy_only() -> None:
    """Closed stock doors batch by material while animated panels stay separate."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    door = md.ModelNode(
        name="door_proxy",
        flags=int(md.NodeFlags.HEADER),
        parent=root,
    )
    setattr(door, "_gr_map_studio_placement_kind", "door")
    meshes = []
    for index in range(3):
        node = md.ModelNode(
            name=f"door_part_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=door,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            face_mats=[0],
            texture="ond_door",
            texture_names=["ond_door"],
        )
        setattr(node, "_gr_map_studio_stock_mesh", True)
        meshes.append(node)
    meshes[-1].controllers = [{"type": "position"}]
    door.children = meshes
    root.children = [door]
    source = md.KotorModel(name="source", root_node=root)

    optimized = optimize_authored_preview_model_for_pie(source)
    optimized_meshes = optimized.root_node.children[0].children

    assert len(source.root_node.children[0].children) == 3
    assert len(optimized_meshes) == 2
    static_batch = next(
        node
        for node in optimized_meshes
        if getattr(node, "_gr_map_studio_pie_batch_source_count", 0) == 2
    )
    assert len(static_batch.faces) == 2
    assert any(tuple(getattr(node, "controllers", ()) or ()) for node in optimized_meshes)
    assert optimized._gr_map_studio_pie_static_batch_summary == {
        "source_meshes": 2,
        "runtime_batches": 1,
        "draw_calls_saved": 1,
        "rehydrated_meshes_suppressed": 0,
    }


def test_pie_stock_room_batches_remain_below_their_room_transforms() -> None:
    """Vanilla room meshes compact locally but never cross room headers."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    rooms = []
    for room_index, room_x in enumerate((0.0, 24.0)):
        room = md.ModelNode(
            name=f"stock_room_{room_index}",
            flags=int(md.NodeFlags.HEADER),
            parent=root,
            position=(room_x, 0.0, 0.0),
        )
        setattr(room, "_gr_map_studio_authored_room", True)
        setattr(room, "_gr_map_studio_stock_room", True)
        meshes = []
        for mesh_index in range(2):
            node = md.ModelNode(
                name=f"stock_wall_{room_index}_{mesh_index}",
                flags=int(md.NodeFlags.MESH),
                parent=room,
                vertices=[
                    (float(mesh_index), 0.0, 0.0),
                    (float(mesh_index + 1), 0.0, 0.0),
                    (float(mesh_index), 1.0, 0.0),
                ],
                normals=[(0.0, 0.0, 1.0)] * 3,
                uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
                faces=[(0, 1, 2)],
                texture="ond_stock_wall",
                texture_names=["ond_stock_wall"],
            )
            setattr(node, "_gr_map_studio_authored_mesh", True)
            setattr(node, "_gr_map_studio_stock_mesh", True)
            meshes.append(node)
        room.children = meshes
        rooms.append(room)
    root.children = rooms

    optimized = optimize_authored_preview_model_for_pie(
        md.KotorModel(name="source", root_node=root)
    )

    assert not any(
        bool(getattr(node, "_gr_map_studio_stock_mesh", False))
        for node in optimized.root_node.children
    )
    optimized_rooms = [
        node
        for node in optimized.root_node.children
        if bool(getattr(node, "_gr_map_studio_stock_room", False))
    ]
    assert [room.position for room in optimized_rooms] == [
        (0.0, 0.0, 0.0),
        (24.0, 0.0, 0.0),
    ]
    assert [len(room.children) for room in optimized_rooms] == [1, 1]
    assert all(
        bool(getattr(room.children[0], "_gr_map_studio_stock_mesh", False))
        and len(room.children[0].faces) == 2
        for room in optimized_rooms
    )
    assert optimized._gr_map_studio_pie_static_batch_summary == {
        "source_meshes": 4,
        "runtime_batches": 2,
        "draw_calls_saved": 2,
        "rehydrated_meshes_suppressed": 0,
    }


def test_pie_static_batch_preserves_room_boundaries_for_runtime_visibility() -> None:
    """Compatible materials stay room-local so PIE can cull distant rooms."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    rooms = []
    for index, x in enumerate((0.0, 12.0)):
        room = md.ModelNode(
            name=f"room_{index}",
            flags=int(md.NodeFlags.HEADER),
            parent=root,
            position=(x, 0.0, 0.0),
        )
        setattr(room, "_gr_map_studio_authored_room", True)
        mesh = md.ModelNode(
            name=f"wall_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            face_mats=[0],
            texture="ond_wall",
            texture_names=["ond_wall"],
        )
        setattr(mesh, "_gr_map_studio_authored_mesh", True)
        room.children = [mesh]
        rooms.append(room)
    root.children = rooms
    source = md.KotorModel(name="source", root_node=root)

    optimized = optimize_authored_preview_model_for_pie(source)
    optimized_rooms = optimized.root_node.children
    assert [room.name for room in optimized_rooms] == ["room_0", "room_1"]
    assert [len(room.children) for room in optimized_rooms] == [1, 1]
    assert [room.position for room in optimized_rooms] == [
        (0.0, 0.0, 0.0),
        (12.0, 0.0, 0.0),
    ]
    assert source.root_node.children[1].position == (12.0, 0.0, 0.0)
    assert source.root_node.children[1].children[0].vertices[0] == (0.0, 0.0, 0.0)
    assert getattr(optimized, "_gr_map_studio_pie_static_batch_summary") == {
        "source_meshes": 2,
        "runtime_batches": 2,
        "draw_calls_saved": 0,
        "rehydrated_meshes_suppressed": 0,
    }


def test_pie_room_visibility_keeps_current_connected_and_nearby_rooms_only() -> None:
    """PIE room culling follows WOK/VIS boundaries without dropping thresholds."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.map_studio_pie import (
        apply_map_studio_pie_room_visibility,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    rooms = []
    for name, x in (("current", 0.0), ("threshold", 10.0), ("distant", 100.0)):
        room = md.ModelNode(
            name=name,
            flags=int(md.NodeFlags.HEADER),
            parent=root,
            position=(x, 0.0, 0.0),
        )
        setattr(room, "_gr_map_studio_authored_room", True)
        setattr(room, "_gr_map_studio_room_resref", name)
        mesh = md.ModelNode(
            name=f"{name}_mesh",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (0.0, 2.0, 0.0),
            ],
            faces=[(0, 1, 2)],
            texture="ond_wall",
        )
        room.children = [mesh]
        rooms.append(room)
    root.children = rooms
    model = md.KotorModel(name="rooms", root_node=root)

    first = apply_map_studio_pie_room_visibility(
        model,
        active_room_resref="current",
        connected_room_resrefs=("threshold",),
        player_position=(1.0, 1.0, 0.0),
        nearby_distance=2.0,
    )

    assert first.visible_room_resrefs == ("current", "threshold")
    assert first.hidden_room_resrefs == ("distant",)
    assert not bool(getattr(rooms[0].children[0], "_gr_hidden", False))
    assert not bool(getattr(rooms[1].children[0], "_gr_hidden", False))
    assert rooms[2].children[0]._gr_hidden is True

    second = apply_map_studio_pie_room_visibility(
        model,
        active_room_resref="distant",
        player_position=(101.0, 1.0, 0.0),
        nearby_distance=2.0,
    )

    assert second.visible_room_resrefs == ("distant",)
    assert rooms[0].children[0]._gr_hidden is True
    assert rooms[1].children[0]._gr_hidden is True
    assert not bool(getattr(rooms[2].children[0], "_gr_hidden", False))


def test_pie_global_batch_retains_unique_stock_room_surfaces() -> None:
    """A shared-material batch must not erase unrelated room surfaces."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    rooms = []
    unique_floor = None
    for index, x in enumerate((0.0, 12.0)):
        room = md.ModelNode(
            name=f"room_{index}",
            flags=int(md.NodeFlags.HEADER),
            parent=root,
            position=(x, 0.0, 0.0),
        )
        setattr(room, "_gr_map_studio_authored_room", True)
        shared = md.ModelNode(
            name=f"shared_wall_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            face_mats=[0],
            texture="ond_wall",
            texture_names=["ond_wall"],
        )
        setattr(shared, "_gr_map_studio_authored_mesh", True)
        room.children = [shared]
        if index == 1:
            unique_floor = md.ModelNode(
                name="stock_floor",
                flags=int(md.NodeFlags.MESH),
                parent=room,
                vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
                normals=[(0.0, 0.0, 1.0)] * 3,
                uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
                faces=[(0, 1, 2)],
                face_mats=[0],
                texture="ond_unique_floor",
                texture_names=["ond_unique_floor"],
            )
            setattr(unique_floor, "_gr_map_studio_authored_mesh", True)
            room.children.append(unique_floor)
        rooms.append(room)
    root.children = rooms

    optimized = optimize_authored_preview_model_for_pie(
        md.KotorModel(name="source", root_node=root)
    )
    optimized_floor = next(
        node
        for node in optimized.all_nodes()
        if str(getattr(node, "name", "")) == "stock_floor"
    )

    assert optimized_floor.texture == "ond_unique_floor"
    assert optimized_floor.faces == [(0, 1, 2)]
    assert not bool(getattr(optimized_floor, "_gr_hidden", False))
    assert optimized_floor in optimized.root_node.children[1].children


def test_pie_final_batch_hides_rehydrated_room_mesh_duplicate() -> None:
    """A queued room refresh cannot redraw geometry already promoted to batches."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        batch_authored_preview_model_for_pie_in_place,
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="room", flags=int(md.NodeFlags.HEADER), parent=root)
    setattr(room, "_gr_map_studio_authored_room", True)
    meshes = []
    for index in range(2):
        node = md.ModelNode(
            name=f"wall_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            texture="ond_wall",
            texture_names=["ond_wall"],
        )
        setattr(node, "_gr_map_studio_authored_mesh", True)
        meshes.append(node)
    room.children = meshes
    root.children = [room]
    optimized = optimize_authored_preview_model_for_pie(
        md.KotorModel(name="source", root_node=root)
    )

    runtime_room = optimized.root_node.children[0]
    promoted_batch = runtime_room.children.pop()
    promoted_batch.parent = optimized.root_node
    optimized.root_node.children.append(promoted_batch)
    # Resource publication recreates room headers without preserving dynamic
    # Python marker attributes.  The PIE model must retain room identity
    # independently so that a final batching pass still recognizes this node.
    delattr(runtime_room, "_gr_map_studio_authored_room")
    rehydrated = md.ModelNode(
        name="rehydrated_wall",
        flags=int(md.NodeFlags.MESH),
        parent=runtime_room,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="ond_wall",
    )
    runtime_room.children.append(rehydrated)
    batch_authored_preview_model_for_pie_in_place(optimized)

    assert rehydrated._gr_hidden is True
    assert rehydrated._gr_map_studio_pie_rehydrated_hidden is True
    assert rehydrated not in runtime_room.children
    assert optimized._gr_map_studio_pie_static_batch_summary[
        "rehydrated_meshes_suppressed"
    ] == 1


def test_pie_final_batch_recompacts_rehydrated_room_without_global_batch() -> None:
    """A queued room refresh remains room-local and is compacted before upload."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        batch_authored_preview_model_for_pie_in_place,
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="room", flags=int(md.NodeFlags.HEADER), parent=root)
    setattr(room, "_gr_map_studio_authored_room", True)
    setattr(room, "_gr_map_studio_room_resref", "room")
    room.children = []
    for index in range(2):
        mesh = md.ModelNode(
            name=f"wall_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[
                (float(index), 0.0, 0.0),
                (float(index) + 1.0, 0.0, 0.0),
                (float(index), 1.0, 0.0),
            ],
            faces=[(0, 1, 2)],
            texture="ond_wall",
        )
        setattr(mesh, "_gr_map_studio_authored_mesh", True)
        room.children.append(mesh)
    root.children = [room]
    optimized = optimize_authored_preview_model_for_pie(
        md.KotorModel(name="source", root_node=root)
    )
    runtime_room = optimized.root_node.children[0]
    assert len(runtime_room.children) == 1

    delattr(runtime_room, "_gr_map_studio_authored_room")
    delattr(runtime_room, "_gr_map_studio_room_resref")
    runtime_room.children = []
    for index in range(2):
        refreshed = md.ModelNode(
            name=f"refreshed_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=runtime_room,
            vertices=[
                (float(index), 0.0, 0.0),
                (float(index) + 1.0, 0.0, 0.0),
                (float(index), 1.0, 0.0),
            ],
            faces=[(0, 1, 2)],
            texture="ond_wall",
        )
        runtime_room.children.append(refreshed)

    batch_authored_preview_model_for_pie_in_place(optimized)

    assert runtime_room._gr_map_studio_authored_room is True
    assert runtime_room._gr_map_studio_room_resref == "room"
    assert len(runtime_room.children) == 1
    assert len(runtime_room.children[0].faces) == 2
    assert optimized._gr_map_studio_pie_static_batch_summary == {
        "source_meshes": 2,
        "runtime_batches": 1,
        "draw_calls_saved": 1,
        "rehydrated_meshes_suppressed": 0,
    }


def test_pie_first_batch_rehydrates_room_identity_from_model_manifest() -> None:
    """The initial PIE pass survives viewport wrappers losing node-only tags."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.core.modules.authored_module_preview_model import (
        optimize_authored_preview_model_for_pie,
    )

    root = md.ModelNode(name="root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="gronderon_room", flags=int(md.NodeFlags.HEADER), parent=root)
    room.children = []
    for index in range(96):
        mesh = md.ModelNode(
            name=f"wall_{index}",
            flags=int(md.NodeFlags.MESH),
            parent=room,
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            faces=[(0, 1, 2)],
            texture="ond_wall",
            texture_names=["ond_wall"],
        )
        room.children.append(mesh)
    root.children = [room]
    source = md.KotorModel(name="source", root_node=root)
    setattr(source, "_gr_map_studio_pie_batched_room_names", ("gronderon_room",))
    setattr(source, "_gr_map_studio_pie_stock_room_names", ())

    optimized = optimize_authored_preview_model_for_pie(source)
    optimized_room = optimized.root_node.children[0]

    assert bool(getattr(optimized_room, "_gr_map_studio_authored_room", False))
    assert len(optimized_room.children) == 1
    assert getattr(optimized, "_gr_map_studio_pie_static_batch_summary") == {
        "source_meshes": 96,
        "runtime_batches": 1,
        "draw_calls_saved": 95,
        "rehydrated_meshes_suppressed": 0,
    }


def test_prewarm_is_deferred_and_guarded() -> None:
    _configure_native_python_roots()
    source = (ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py").read_text(encoding="utf-8")
    assert "_prewarm_map_studio_pie_player_model" in source
    # Deferred off the refresh hot path: the MDL parse contends for the GIL.
    assert "QtCore.QTimer.singleShot(1500, self._prewarm_map_studio_pie_player_model)" in source
    mirror = (ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie.py").read_text(encoding="utf-8")
    assert "combined_walkmesh" in mirror


def test_prewarm_worker_does_not_touch_process_global_animation_state(monkeypatch) -> None:
    _configure_native_python_roots()
    import threading

    from PySide6 import QtWidgets
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpieprewarm", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            def load_model_strict(self, resref, game):
                return _stub_model(str(resref))

        class _ImmediateThread:
            def __init__(self, *, target, **_kwargs):
                self._target = target

            def start(self):
                self._target()

        configure_calls: list[object] = []
        play_calls: list[str] = []
        monkeypatch.setattr(threading, "Thread", _ImmediateThread)
        monkeypatch.setattr(
            SuperModelResolver,
            "configure",
            lambda manager: configure_calls.append(manager),
        )
        monkeypatch.setattr(
            AnimationEngine,
            "play",
            lambda _engine, name, **_kwargs: play_calls.append(str(name)) or True,
        )
        window.resource_manager = _Manager()
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")

        window._prewarm_map_studio_pie_player_model()

        assert len(window._map_studio_pie_player_model_cache) == 1
        assert configure_calls == []
        assert play_calls == []
    finally:
        window.deleteLater()


def test_player_actor_cache_invalidates_when_resource_revision_changes() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpierevision", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def __init__(self) -> None:
                self.loads: list[tuple[int, str]] = []

            def load_model_strict(self, resref, _game):
                self.loads.append((self.revision, str(resref)))
                return _stub_model(f"{resref}_r{self.revision}")

            def load_model(self, resref, _game):
                return _stub_model(str(resref))

        manager = _Manager()
        window.resource_manager = manager
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))

        window._create_map_studio_pie_player_actor(session, preview, "K1")
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert manager.loads == [(0, "pmbam")]

        manager.revision = 1
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert manager.loads == [(0, "pmbam"), (1, "pmbam")]
        cache = window._map_studio_pie_player_model_cache
        assert len(cache) == 1
        cache_key = next(iter(cache))
        assert cache_key[0] is manager
        assert cache_key[1] == 1
    finally:
        window.deleteLater()


def test_play_does_not_duplicate_an_inflight_player_prewarm(monkeypatch) -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows import module_editor_window as window_module

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = window_module.ModuleEditorWindow()
    release_loader = threading.Event()
    try:
        window.controller.new_project(name="grpiepending", game="K1")
        load_started = threading.Event()
        loads: list[str] = []

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def load_model_strict(self, resref, _game):
                loads.append(str(resref))
                load_started.set()
                assert release_loader.wait(2.0)
                return _stub_model(str(resref))

            def load_model(self, resref, _game):
                return _stub_model(str(resref))

        window.resource_manager = _Manager()
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))
        monkeypatch.setattr(window_module, "_MAP_STUDIO_PIE_PLAYER_PREWARM_WAIT_SECONDS", 0.01)

        window._prewarm_map_studio_pie_player_model()
        assert load_started.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            completion = next(iter(window._map_studio_pie_player_prewarm_pending.values()))

        warning = window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert "still preparing" in warning
        assert loads == ["pmbam"]

        release_loader.set()
        assert completion.wait(2.0)
        warning = window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert warning == ""
        assert loads == ["pmbam"]
    finally:
        release_loader.set()
        window.deleteLater()


def test_prewarm_discards_model_when_resource_revision_changes() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    release_loader = threading.Event()
    try:
        window.controller.new_project(name="grpieworkrev", game="K1")
        load_started = threading.Event()

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def load_model_strict(self, resref, _game):
                load_started.set()
                assert release_loader.wait(2.0)
                return _stub_model(str(resref))

        manager = _Manager()
        window.resource_manager = manager
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        window._prewarm_map_studio_pie_player_model()
        assert load_started.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            old_key, completion = next(iter(window._map_studio_pie_player_prewarm_pending.items()))

        manager.revision = 1
        release_loader.set()
        assert completion.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            assert old_key not in window._map_studio_pie_player_model_cache
            assert old_key not in window._map_studio_pie_player_prewarm_pending
    finally:
        release_loader.set()
        window.deleteLater()
