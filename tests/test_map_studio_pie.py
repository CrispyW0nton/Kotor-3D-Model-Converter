"""Focused contracts for Map Studio's read-only PIE walkmesh simulation."""

from __future__ import annotations

import copy
import ast
import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _install_pie_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    # Scene owns the authored-module runtime; Math owns the reusable movement
    # and collision indexes.  Keep the repository root available for the new
    # canonical sources while matching the embedded host's package layout.
    for rel in reversed(
        (
            ".",
            "native/GhostRigger.Core.Math/Python",
            "native/GhostRigger.Core.Scene/Python",
        )
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


_install_pie_payload_paths()


def _face(
    v1: int,
    v2: int,
    v3: int,
    surface: int = 4,
    *,
    adj1: int = -1,
    adj2: int = -1,
    adj3: int = -1,
):
    return SimpleNamespace(
        v1=v1,
        v2=v2,
        v3=v3,
        surface=surface,
        adj1=adj1,
        adj2=adj2,
        adj3=adj3,
    )


def _wok(vertices, faces):
    return SimpleNamespace(verts=list(vertices), faces=list(faces))


def _quad_wok(
    *,
    minimum: float = 0.0,
    maximum: float = 10.0,
    surface: int = 4,
    z_at_x=lambda _x: 0.0,
):
    vertices = [
        (minimum, minimum, z_at_x(minimum)),
        (maximum, minimum, z_at_x(maximum)),
        (maximum, maximum, z_at_x(maximum)),
        (minimum, maximum, z_at_x(minimum)),
    ]
    return _wok(vertices, (_face(0, 1, 2, surface), _face(0, 2, 3, surface)))


def _session(wok, *, game: str = "K1", spawn=(5.0, 5.0, 0.0), collision=()):
    from src.core.modules.map_studio_pie import MapStudioPIESession

    return MapStudioPIESession(
        wok,
        game=game,
        spawn_position=spawn,
        collision_triangles=collision,
    )


def _canonical_pie_module():
    """Load the root source even before its embedded payload copies regenerate."""

    repo = Path(__file__).resolve().parents[1]
    module_name = "src.core.modules._map_studio_pie_canonical_contract"
    loaded = sys.modules.get(module_name)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(module_name, repo / "src" / "core" / "modules" / "map_studio_pie.py")
    assert spec is not None and spec.loader is not None
    canonical_pie = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = canonical_pie
    spec.loader.exec_module(canonical_pie)
    return canonical_pie


def test_pie_uses_retail_game_specific_walk_surface_contracts() -> None:
    from src.math.walkmesh_runtime import (
        K1_WALKABLE_SURFACE_IDS,
        K2_WALKABLE_SURFACE_IDS,
        WalkmeshRuntimeIndex,
        kotor_walkable_surface_ids,
    )

    assert 16 not in K1_WALKABLE_SURFACE_IDS
    assert 16 in K2_WALKABLE_SURFACE_IDS
    assert kotor_walkable_surface_ids("k1") is K1_WALKABLE_SURFACE_IDS
    assert kotor_walkable_surface_ids("K2") is K2_WALKABLE_SURFACE_IDS

    bottomless_pit = _quad_wok(surface=16)
    assert WalkmeshRuntimeIndex(bottomless_pit, game="K1").walkable_faces == ()
    assert WalkmeshRuntimeIndex(bottomless_pit, game="K2").walkable_faces == (0, 1)


def test_pie_fixed_step_moves_at_retail_walk_speed() -> None:
    from src.core.modules.map_studio_pie import kotor_player_walk_speed

    session = _session(_quad_wok(maximum=20.0), spawn=(5.0, 5.0, 0.0))
    assert session.validation.ok
    # At azimuth 180 degrees the camera-relative forward vector is +X.
    session.set_move_input(1.0, 0.0, camera_azimuth_degrees=180.0, run=False)
    for _index in range(30):
        frame = session.advance(1.0 / 60.0)

    assert frame.simulation_time == pytest.approx(0.5)
    assert frame.position[0] == pytest.approx(5.0 + (kotor_player_walk_speed("K1") * 0.5))
    assert frame.position[1:] == pytest.approx((5.0, 0.0))
    assert frame.moving and not frame.blocked


def test_pie_player_actor_faces_actual_wok_constrained_motion() -> None:
    """A boundary slide must turn the +Y-forward actor toward its real velocity."""

    kotor_actor_yaw_for_world_facing = _canonical_pie_module().kotor_actor_yaw_for_world_facing

    session = _session(_quad_wok(maximum=2.0), spawn=(1.75, 1.0, 0.0))
    assert session.validation.ok
    # Camera-relative forward + right requests a +X/+Y diagonal, but the player
    # disc is already against the +X boundary and can only slide along +Y.
    session.set_move_input(1.0, -1.0, camera_azimuth_degrees=180.0, run=True)
    frame = session.advance(1.0 / 60.0)

    assert frame.blocked and frame.moving
    assert frame.velocity[0] == pytest.approx(0.0, abs=1.0e-9)
    assert frame.velocity[1] > 0.0
    assert frame.facing_radians == pytest.approx(math.pi * 0.5)
    # KOTOR character geometry is +Y-forward, so a +Y world movement needs no
    # wrapper yaw. Applying the bearing directly would turn it 90 degrees left.
    assert kotor_actor_yaw_for_world_facing(frame.facing_radians) == pytest.approx(0.0)


def test_pie_player_disc_stays_inside_walkmesh_boundary() -> None:
    session = _session(_quad_wok(maximum=2.0), spawn=(1.0, 1.0, 0.0))
    assert session.validation.ok
    session.set_move_input(1.0, 0.0, camera_azimuth_degrees=180.0, run=True)

    blocked = False
    for _index in range(30):
        frame = session.advance(1.0 / 60.0)
        blocked = blocked or frame.blocked

    assert blocked
    assert frame.position[0] <= 2.0 - (session.config.player_radius * 0.90)
    assert session.walkmesh.validate_disc(
        frame.position,
        preferred_face=frame.face_index,
        radius=session.config.player_radius,
    ) is not None


def test_pie_follows_ramp_height_instead_of_staying_on_spawn_z() -> None:
    session = _session(
        _quad_wok(maximum=20.0, z_at_x=lambda x: x * 0.1),
        spawn=(5.0, 5.0, 0.5),
    )
    assert session.validation.ok
    session.set_move_input(1.0, 0.0, camera_azimuth_degrees=180.0)
    for _index in range(30):
        frame = session.advance(1.0 / 60.0)

    assert frame.position[0] > 6.5
    assert frame.position[2] == pytest.approx(frame.position[0] * 0.1)
    assert frame.velocity[2] > 0.0


def test_pie_stacked_floor_sampling_keeps_nearest_height_layer() -> None:
    from src.math.walkmesh_runtime import WalkmeshRuntimeIndex

    low = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0)]
    high = [(x, y, 5.0) for x, y, _z in low]
    wok = _wok(
        low + high,
        (
            _face(0, 1, 2),
            _face(0, 2, 3),
            _face(4, 5, 6),
            _face(4, 6, 7),
        ),
    )
    index = WalkmeshRuntimeIndex(wok, game="K2")

    lower = index.sample_at(2.0, 2.0, 0.1)
    upper = index.sample_at(2.0, 2.0, 4.9)
    assert lower is not None and lower.position[2] == pytest.approx(0.0)
    assert upper is not None and upper.position[2] == pytest.approx(5.0)
    assert lower.face_index in {0, 1}
    assert upper.face_index in {2, 3}


@pytest.mark.parametrize(
    ("fixture_name", "root_z", "mesh_z", "vertex_floor", "support_name", "support_local_z", "expected_plane"),
    (
        ("humanoid", 0.8, -0.2, -0.8, "lfootT_g", -1.0, -0.2),
        ("creature", -0.5, 0.2, 0.55, "front_paw_g", 0.75, 0.25),
    ),
)
def test_pie_actor_grounding_uses_corroborated_support_for_differently_rooted_models(
    fixture_name: str,
    root_z: float,
    mesh_z: float,
    vertex_floor: float,
    support_name: str,
    support_local_z: float,
    expected_plane: float,
) -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.modules.map_studio_pie import (
        actor_model_support_plane_z,
        attach_map_studio_pie_actor,
        resolve_map_studio_pie_actor_grounding,
    )
    from src.math.walkmesh_runtime import WalkmeshRuntimeIndex

    root = ModelNode(name=f"{fixture_name}_root", flags=int(NodeFlags.HEADER), position=(0.0, 0.0, root_z))
    mesh = ModelNode(
        name=f"{fixture_name}_body",
        flags=int(NodeFlags.MESH),
        position=(0.0, 0.0, mesh_z),
        vertices=[
            (-0.25, -0.25, vertex_floor),
            (0.25, -0.25, vertex_floor),
            (0.0, 0.25, vertex_floor + 0.8),
        ],
        faces=[(0, 1, 2)],
    )
    support = ModelNode(
        name=support_name,
        flags=int(NodeFlags.HEADER),
        position=(0.0, 0.0, support_local_z),
    )
    mesh.parent = root
    support.parent = root
    root.children = [mesh, support]
    model = KotorModel(name=fixture_name, root_node=root)
    source_positions = tuple(node.position for node in model.all_nodes())
    walkmesh = WalkmeshRuntimeIndex(
        _quad_wok(maximum=10.0, z_at_x=lambda _x: 4.0),
        game="K2",
    )

    assert actor_model_support_plane_z(model) == pytest.approx(expected_plane)
    grounding = resolve_map_studio_pie_actor_grounding(
        walkmesh,
        model,
        (5.0, 5.0, 4.1),
    )

    assert grounding.sampled_walkmesh is True
    assert grounding.surface_position == pytest.approx((5.0, 5.0, 4.0))
    assert grounding.support_plane_z == pytest.approx(expected_plane)
    assert grounding.actor_root_position[2] == pytest.approx(4.0 - expected_plane)
    assert grounding.visual_support_z == pytest.approx(4.0)
    assert grounding.support_source == "corroborated_support_geometry"

    preview = KotorModel(
        name="map",
        root_node=ModelNode(name="map", flags=int(NodeFlags.HEADER)),
    )
    attached = attach_map_studio_pie_actor(
        preview,
        model,
        position=grounding.surface_position,
        support_plane_z=grounding.support_plane_z,
        recompute_bounds=False,
    )
    assert attached is not None
    assert attached.root_node.position == pytest.approx(grounding.actor_root_position)
    assert attached.surface_position == pytest.approx(grounding.surface_position)
    assert tuple(node.position for node in model.all_nodes()) == source_positions


def test_pie_actor_grounding_preserves_retail_root_plane_for_millimetre_pose_clearance() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.modules.map_studio_pie import actor_model_support_plane_z

    root = ModelNode(name="retail_body", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="boots",
        flags=int(NodeFlags.MESH),
        vertices=[(-0.2, 0.0, -0.013), (0.2, 0.0, -0.013), (0.0, 0.2, 0.2)],
        faces=[(0, 1, 2)],
    )
    toe = ModelNode(name="rfootT_g", flags=int(NodeFlags.HEADER), position=(0.0, 0.0, 0.03))
    mesh.parent = root
    toe.parent = root
    root.children = [mesh, toe]

    assert actor_model_support_plane_z(KotorModel(name="retail", root_node=root)) == 0.0


def test_pie_click_route_rejects_disconnected_walkmesh_island() -> None:
    vertices = [
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 4.0, 0.0),
        (0.0, 4.0, 0.0),
        (10.0, 0.0, 0.0),
        (14.0, 0.0, 0.0),
        (14.0, 4.0, 0.0),
        (10.0, 4.0, 0.0),
    ]
    wok = _wok(
        vertices,
        (_face(0, 1, 2), _face(0, 2, 3), _face(4, 5, 6), _face(4, 6, 7)),
    )
    session = _session(wok, spawn=(2.0, 2.0, 0.0))
    assert session.validation.ok

    assert session.set_destination((12.0, 2.0, 0.0)) is False
    frame = session.advance(0.0)
    assert session.state.destination is None
    assert [event.kind for event in frame.events] == ["destination_unreachable"]


def test_pie_camera_is_clipped_in_front_of_static_room_triangle() -> None:
    from src.math.walkmesh_runtime import CollisionTriangle

    wall = CollisionTriangle(
        a=(2.0, -2.0, -1.0),
        b=(2.0, 2.0, -1.0),
        c=(2.0, 0.0, 3.0),
        source="room:wall",
    )
    session = _session(_quad_wok(), collision=(wall,))
    distance = session.resolve_camera_distance(
        (0.0, 0.0, 1.0),
        (4.0, 0.0, 1.0),
        delta_time=1.0 / 60.0,
    )

    assert distance == pytest.approx(2.0 - session.config.camera_padding)
    assert distance < 4.0


def test_pie_fixed_step_result_is_deterministic_across_frame_chunking() -> None:
    wok = _quad_wok(maximum=30.0)
    fine = _session(wok, spawn=(5.0, 5.0, 0.0))
    coarse = _session(wok, spawn=(5.0, 5.0, 0.0))
    for session in (fine, coarse):
        session.set_move_input(1.0, 0.0, camera_azimuth_degrees=180.0)

    for _index in range(60):
        fine_frame = fine.advance(1.0 / 60.0)
    for _index in range(10):
        coarse_frame = coarse.advance(0.1)

    assert fine_frame.simulation_time == pytest.approx(1.0)
    assert coarse_frame.simulation_time == pytest.approx(1.0)
    assert coarse_frame.position == pytest.approx(fine_frame.position, abs=1.0e-9)
    assert coarse_frame.velocity == pytest.approx(fine_frame.velocity, abs=1.0e-9)


def test_pie_collision_extraction_filters_non_static_room_geometry() -> None:
    from src.core.modules.map_studio_pie import collision_triangles_from_preview_model

    def node(name: str, **overrides):
        values = {
            "name": name,
            "vertices": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            "faces": [(0, 1, 2)],
            "_gr_map_studio_room_resref": "207tel_1",
            "_gr_map_studio_placement_id": "",
            "_gr_map_studio_backdrop": False,
            "background_geometry": False,
            "render": True,
            "is_aabb": False,
            "vertex_space": 1,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    valid = node("floor")
    rows = [
        valid,
        node("placeable", _gr_map_studio_placement_id="placeable:1"),
        node("backdrop", _gr_map_studio_backdrop=True),
        node("background", background_geometry=True),
        node("hidden", render=False),
        node("aabb", is_aabb=True),
        node("placement_space", vertex_space=2),
        node("unowned", _gr_map_studio_room_resref=""),
        node("degenerate", vertices=[(0.0, 0.0, 0.0)] * 3),
    ]
    model = SimpleNamespace(all_nodes=lambda: rows)

    triangles = collision_triangles_from_preview_model(model)
    assert len(triangles) == 1
    assert triangles[0].source == "207tel_1:floor"
    assert triangles[0].a == (0.0, 0.0, 0.0)


def test_pie_stock_module_wok_is_not_double_offset_and_kmap_is_unchanged() -> None:
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )
    from src.core.modules.authored_module_walkmesh import combine_authored_module_walkmesh
    from src.core.modules.map_studio_pie import build_map_studio_pie_session
    from src.core.modules.module_format import WOKData, WOKFace

    stock_vertices = [(10.0, 10.0, 0.0), (14.0, 10.0, 0.0), (14.0, 14.0, 0.0), (10.0, 14.0, 0.0)]
    stock_wok = WOKData(
        name="207tel_1",
        verts=list(stock_vertices),
        faces=[WOKFace(0, 1, 2, 4), WOKFace(0, 2, 3, 4)],
    )
    surface = ImportedMeshSurface(
        name="render",
        texture="lka_wall01",
        vertices=tuple(stock_vertices),
        faces=((0, 1, 2), (0, 2, 3)),
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="207tel_1",
        surfaces=(surface,),
        source_model="207tel_1",
        game="K2",
        wok=stock_wok,
        metadata={"imported_from": "207TEL", "wok_coordinate_space": "module"},
    )
    room = AuthoredRoomSpec(
        room_resref="207tel_1",
        primitive=primitive,
        position=(8.410, -44.268, 0.0),
        metadata={"source": "stock_module_import"},
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="plcaa", game="K2"),
        rooms=(room,),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="plcaa", position=(12.0, 12.0, 0.0)),
        ),
    )
    frozen_copy = copy.deepcopy(project)
    payload_before = authored_project_to_kmap_payload(project)

    combined = combine_authored_module_walkmesh(project)
    built = build_map_studio_pie_session(project)
    payload_after = authored_project_to_kmap_payload(project)

    assert combined.wok.verts == stock_vertices
    assert any("not applied a second time" in warning for warning in combined.warnings)
    assert built.validation.ok and built.session is not None
    assert built.session.state.position == pytest.approx((12.0, 12.0, 0.0))
    assert project == frozen_copy
    assert payload_after == payload_before


def test_pie_excludes_explicitly_unresolved_stock_placeholder_from_collision() -> None:
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import (
        ImportedMeshRoomPrimitive,
        ImportedMeshSurface,
        authored_room_uses_unresolved_stock_geometry,
    )
    from src.core.modules.authored_module_export import build_authored_module
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_preview_model import build_authored_module_preview_model
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )
    from src.core.modules.authored_module_readiness import build_authored_module_readiness
    from src.core.modules.authored_module_walkmesh import combine_authored_module_walkmesh
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.map_studio_pie import build_map_studio_pie_session, collision_triangles_from_preview_model
    from src.core.modules.module_format import WOKData, WOKFace

    vertices = ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 4.0, 0.0))
    resolved = AuthoredRoomSpec(
        room_resref="koq200_01a",
        primitive=ImportedMeshRoomPrimitive(
            room_resref="koq200_01a",
            surfaces=(
                ImportedMeshSurface(
                    name="render",
                    texture="canyon",
                    vertices=vertices,
                    faces=((0, 1, 2),),
                ),
            ),
            source_model="koq200_01a",
            game="K1",
            wok=WOKData(name="koq200_01a", verts=list(vertices), faces=[WOKFace(0, 1, 2, 4)]),
        ),
        metadata={"source": "stock_room_conversion"},
    )
    unresolved = AuthoredRoomSpec(
        room_resref="koq200_01l",
        primitive=FloorPlanRoomPrimitive(
            room_resref="koq200_01l",
            points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ),
        metadata={
            "source": "stock_module_import",
            "stock_geometry_status": "unresolved",
            "stock_geometry_issue": "Stock room model koq200_01l could not be loaded.",
            "pie_exclude_unresolved_stock_geometry": True,
        },
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="rnvcanyon", game="K1"),
        rooms=(resolved, unresolved),
        placements=AuthoredGameplayPlacement(
            entry_point=ModuleEntryPoint(area_resref="rnvcanyon", position=(1.0, 1.0, 0.0)),
        ),
    )

    combined = combine_authored_module_walkmesh(project)
    preview = build_authored_module_preview_model(project, include_backdrops=True)
    built = build_map_studio_pie_session(project)
    readiness = build_authored_module_readiness(project)
    export_build = build_authored_module(project)

    assert authored_room_uses_unresolved_stock_geometry(unresolved)
    assert not authored_room_uses_unresolved_stock_geometry(
        replace(unresolved, metadata={"source": "stock_module_import", "pie_exclude_unresolved_stock_geometry": True})
    )
    assert combined.source_rooms == ("koq200_01a",)
    assert combined.wok.verts == list(vertices)
    assert any("koq200_01l was excluded from PIE collision" in warning for warning in combined.warnings)
    assert preview.room_count == 1 and preview.model is not None
    assert all(str(getattr(node, "name", "")).lower() != "koq200_01l" for node in preview.model.all_nodes())
    assert all(not triangle.source.startswith("koq200_01l:") for triangle in collision_triangles_from_preview_model(preview.model))
    assert built.validation.ok and built.session is not None
    assert any("koq200_01l was excluded from PIE collision" in warning for warning in built.validation.warnings)
    unresolved_readiness = next(room for room in readiness.rooms if room.room_resref == "koq200_01l")
    assert not unresolved_readiness.can_preview_geometry
    assert any("unresolved stock geometry" in message for message in unresolved_readiness.blocking_messages)
    assert any("koq200_01l has no resolved stock geometry" in message for message in export_build.blocking_issues)


def test_stock_conversion_marks_missing_optional_room_as_pie_excluded() -> None:
    from src.core.modules.authored_module_kmap_bridge import authored_project_to_kmap_payload
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import (
        AuthoredModuleMetadata,
        AuthoredModuleProject,
        AuthoredRoomSpec,
    )
    from src.core.modules.authored_room_floorplan import FloorPlanRoomPrimitive
    from src.core.modules.module_editor_controller import ModuleEditorController

    room = AuthoredRoomSpec(
        room_resref="koq200_01l",
        primitive=FloorPlanRoomPrimitive(
            room_resref="koq200_01l",
            points=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ),
        metadata={"source": "stock_module_import"},
    )
    authored = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="rnvcanyon", game="K1"),
        rooms=(room,),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="rnvcanyon")),
    )
    controller = ModuleEditorController()
    controller.new_project(name="rnvcanyon", game="K1")
    controller.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    controller.convert_stock_room_to_imported_mesh = lambda **_kwargs: (
        False,
        "Stock room model koq200_01l could not be loaded from the K1 game resources.",
    )

    ok, message = controller.convert_all_stock_rooms_to_imported_mesh(resource_manager=object())
    updated = controller._load_authored_project_or_raise()
    metadata = dict(updated.rooms[0].metadata or {})

    assert ok
    assert "Skipped 1 unresolved stock room reference" in message
    assert metadata["stock_geometry_status"] == "unresolved"
    assert metadata["pie_exclude_unresolved_stock_geometry"] is True
    assert "could not be loaded" in metadata["stock_geometry_issue"]


def test_prepared_actor_hierarchy_preserves_bas_source_identity_until_atomic_attach() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.modules.map_studio_pie import (
        attach_map_studio_pie_actor,
        prepare_map_studio_pie_actor_hierarchy,
    )

    body_root = ModelNode(name="body", flags=int(NodeFlags.HEADER))
    head_root = ModelNode(name="head", flags=int(NodeFlags.HEADER))
    head_source = KotorModel(name="head_source", root_node=ModelNode(name="head_source_root"))
    setattr(head_root, "_gr_bas_attachment_source_model_ref", head_source)
    head_root.parent = body_root
    body_root.children = [head_root]
    actor_model = KotorModel(name="actor", root_node=body_root)
    preview_root = ModelNode(name="map", flags=int(NodeFlags.HEADER))
    preview = KotorModel(name="preview", root_node=preview_root)

    prepared = prepare_map_studio_pie_actor_hierarchy(actor_model)
    assert prepared is not body_root
    assert prepared.children[0] is not head_root
    assert prepared.children[0]._gr_bas_attachment_source_model_ref is head_source

    actor = attach_map_studio_pie_actor(
        preview,
        actor_model,
        position=(1.0, 2.0, 3.0),
        prepared_root=prepared,
        append_to_preview=False,
    )
    assert actor is not None
    assert actor.root_node not in preview_root.children
    preview_root.children.append(actor.root_node)
    assert actor.root_node in preview_root.children


def test_creature_promotion_publishes_same_model_without_full_viewport_reload() -> None:
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class Engine:
        current_time = 0.0
        current_animation = SimpleNamespace(name="pause1", length=1.0)

        def evaluate(self):
            return SimpleNamespace(nodes={})

    class Viewport:
        def __init__(self) -> None:
            self.load_calls = 0
            self.playback_calls = 0
            self.frame_calls: list[dict[str, object]] = []

        def load_model(self, *_args, **_kwargs) -> None:
            self.load_calls += 1

        def set_animation_playback_active(self, *_args) -> None:
            self.playback_calls += 1

        def update_runtime_character_frames(self, rows, **kwargs) -> None:
            self.frame_calls.append({"rows": tuple(rows), **kwargs})

    viewport = Viewport()
    source_model = SimpleNamespace()
    actor = SimpleNamespace(
        root_node=SimpleNamespace(),
        actor_id="npc:1",
        source_model=source_model,
    )
    window = SimpleNamespace(
        viewport_panel=SimpleNamespace(viewport=viewport, _project_texture_dirs=()),
        _map_studio_pie_actor=None,
        _map_studio_pie_animation_engine=None,
        _map_studio_pie_animation_name="",
        _map_studio_pie_creature_entries=(
            {
                "actor": actor,
                "engine": Engine(),
                "initial_pose": SimpleNamespace(nodes={}),
            },
        ),
    )
    preview = SimpleNamespace(compute_bounds=lambda: pytest.fail("promotion must reuse prepared bounds"))

    warning = ModuleEditorWindow._activate_map_studio_pie_runtime_actors(
        window,
        preview,
        recompute_bounds=False,
        reload_model=False,
    )

    assert warning == ""
    assert viewport.load_calls == 0
    assert viewport.playback_calls == 1
    assert len(viewport.frame_calls) == 1
    assert viewport.frame_calls[0]["scene_changed"] is True
    assert viewport.frame_calls[0]["camera_changed"] is True

    source_path = (
        Path(__file__).parents[1]
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "viewports"
        / "viewport_core"
        / "widgets"
        / "history_animation.py"
    )
    viewport_source = source_path.read_text(encoding="utf-8")
    batch = _method_source(viewport_source, "update_runtime_character_frames")
    assert "scene=bool(scene_changed)" in batch
    assert "resources=bool(scene_changed)" in batch
    assert batch.count("self._request_render(") == 1

    window_source = (
        Path(__file__).parents[1]
        / "native"
        / "GhostRigger.Core.Tools"
        / "Python"
        / "src"
        / "gui"
        / "windows"
        / "module_editor_window.py"
    ).read_text(encoding="utf-8")
    stop = _method_source(window_source, "_remove_map_studio_pie_runtime_actors")
    assert "viewport.load_model" in stop


def test_pie_actor_attachment_is_runtime_only_and_preserves_source_hierarchy() -> None:
    """The animated PIE actor must never become authored KMAP/model state."""

    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.rendering.mesh_render_data import runtime_source_model_for_node

    # Load the canonical root source explicitly.  During development the
    # already-imported embedded Scene payload may intentionally lag until the
    # package generator runs; payload identity is checked separately.
    attach_map_studio_pie_actor = _canonical_pie_module().attach_map_studio_pie_actor

    authored_room = ModelNode(name="plcaa_room", flags=int(NodeFlags.HEADER))
    preview_root = ModelNode(
        name="plcaa_preview",
        flags=int(NodeFlags.HEADER),
        children=[authored_room],
    )
    authored_room.parent = preview_root
    preview_model = KotorModel(name="plcaa_preview", root_node=preview_root)
    # This represents the project data owned by KMAP.  The runtime actor helper
    # can coexist with it, but may not read, rewrite, or append to it.
    authored_payload = {
        "version": 1,
        "rooms": [{"id": "room:plcaa", "position": [0.0, 0.0, 0.0]}],
        "placements": [{"id": "waypoint:entry", "tag": "entry"}],
    }
    preview_model._gr_authored_kmap_payload = authored_payload
    authored_payload_before = copy.deepcopy(authored_payload)

    source_mesh = ModelNode(
        name="torso_g",
        flags=int(NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    source_bone = ModelNode(
        name="rootdummy",
        flags=int(NodeFlags.HEADER),
        children=[source_mesh],
    )
    source_root = ModelNode(
        name="PMBAM",
        flags=int(NodeFlags.HEADER),
        children=[source_bone],
    )
    source_bone.parent = source_root
    source_mesh.parent = source_bone
    actor_model = KotorModel(name="PMBAM", supermodel="S_Female02", root_node=source_root)
    source_names_before = [node.name for node in actor_model.all_nodes()]
    source_positions_before = [node.position for node in actor_model.all_nodes()]
    source_children_before = tuple(source_root.children)

    actor = attach_map_studio_pie_actor(
        preview_model,
        actor_model,
        position=(3.0, 4.0, 0.5),
        facing_radians=math.pi / 2.0,
        actor_id="pie:player:test",
    )

    assert actor is not None
    assert actor.source_model is actor_model
    assert actor.root_node.parent is preview_root
    assert preview_root.children == [authored_room, actor.root_node]
    assert actor.root_node._gr_scene_object_root_ref is actor.root_node
    assert actor.root_node._gr_runtime_source_model_ref is actor_model
    assert actor.root_node.position == pytest.approx((3.0, 4.0, 0.5))
    # Native KOTOR actors are +Y-forward, so a +Y world facing requires no
    # additional wrapper yaw.
    assert actor.root_node.rotation == pytest.approx((0.0, 0.0, 0.0, 1.0))
    assert actor.root_node.children[0] is not source_root
    copied_actor = KotorModel(name="copied_pie_actor", root_node=actor.root_node.children[0])
    assert [node.name for node in copied_actor.all_nodes()] == source_names_before
    for copied_node in copied_actor.all_nodes():
        assert copied_node._gr_scene_object_id == "pie:player:test"
        assert copied_node._gr_scene_import_id == "pie:player:test"
        assert copied_node._gr_scene_object_root_ref is actor.root_node
        assert copied_node._gr_runtime_source_model_id == id(actor_model)
        assert copied_node._gr_map_studio_pie_actor is True
        assert runtime_source_model_for_node(copied_node) is actor_model

    actor.set_transform((-2.0, 7.5, 1.25), math.pi)
    assert actor.root_node.position == pytest.approx((-2.0, 7.5, 1.25))
    assert actor.root_node.rotation == pytest.approx(
        (0.0, 0.0, math.sin(math.pi / 4.0), math.cos(math.pi / 4.0)),
        abs=1.0e-12,
    )

    # Neither the source Odyssey DAG nor authored project payload was tagged,
    # transformed, reparented, or otherwise mutated by the runtime copy.
    assert [node.name for node in actor_model.all_nodes()] == source_names_before
    assert [node.position for node in actor_model.all_nodes()] == source_positions_before
    assert tuple(source_root.children) == source_children_before
    assert source_bone.parent is source_root
    assert source_mesh.parent is source_bone
    assert not hasattr(source_root, "_gr_map_studio_pie_actor")
    assert authored_payload == authored_payload_before

    actor.detach()
    assert preview_root.children == [authored_room]
    assert authored_room.parent is preview_root
    assert actor.root_node.parent is None
    assert actor.root_node.children[0].parent is actor.root_node
    assert authored_payload == authored_payload_before


def _method_source(source: str, method_name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            segment = ast.get_source_segment(source, node)
            if segment is not None:
                return segment
    raise AssertionError(f"Method {method_name!r} was not found in source")


def test_pie_native_surface_flicker_guard_and_camera_only_fallback_contract() -> None:
    """PIE must not race a Qt pixmap sibling against the native WGPU child."""

    repo = Path(__file__).resolve().parents[1]
    display = repo / "native" / "GhostRigger.Core.GUI.Display" / "Python" / "src" / "gui"
    tools = repo / "native" / "GhostRigger.Core.Tools" / "Python" / "src" / "gui"
    render_source = (
        display / "viewports" / "viewport_core" / "widgets" / "rendering_pipeline.py"
    ).read_text(encoding="utf-8")
    scene_source = (
        display / "viewports" / "viewport_core" / "widgets" / "scene_models.py"
    ).read_text(encoding="utf-8")
    panel_source = (
        display / "panels" / "module_editor" / "module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")
    window_source = (tools / "windows" / "module_editor_window.py").read_text(encoding="utf-8")

    draw_overlay = _method_source(render_source, "_draw_live_surface_tool_overlay")
    assert "_live_surface_overlay_suppressed" in draw_overlay
    assert "_skip_overlay_pixmap_update = True" in draw_overlay
    assert "return img" in draw_overlay

    suppression = _method_source(scene_source, "set_live_surface_overlay_suppressed")
    assert "self.canvas.clear_overlay()" in suppression
    assert "self._pixmap = None" in suppression

    pie_mode = _method_source(panel_source, "set_map_studio_pie_active")
    assert "set_live_surface_overlay_suppressed" in pie_mode
    assert "suppress(True)" in pie_mode
    assert "suppress(False)" in pie_mode

    pie_tick = _method_source(window_source, "_tick_map_studio_pie")
    assert 'reason="Map Studio PIE camera frame"' in pie_tick
    assert "camera=True" in pie_tick
    # The retained room/model scene is unchanged on the actor-unavailable
    # fallback.  Marking it dirty here was the stock-module frame-rate reset.
    assert "scene=True" not in pie_tick
    assert "overlay=True" not in pie_tick
    assert "hud=True" not in pie_tick


def test_pie_clean_runtime_presentation_masks_editor_helpers_without_disabling_lighting() -> None:
    """Every renderer backend must receive a game-like PIE presentation."""

    repo = Path(__file__).resolve().parents[1]
    display = repo / "native" / "GhostRigger.Core.GUI.Display" / "Python" / "src" / "gui"
    render_source = (
        display / "viewports" / "viewport_core" / "widgets" / "rendering_pipeline.py"
    ).read_text(encoding="utf-8")
    panel_source = (
        display / "panels" / "module_editor" / "module_editor_viewport_panel.py"
    ).read_text(encoding="utf-8")

    pie_mode = _method_source(panel_source, "set_map_studio_pie_active")
    assert '_gr_map_studio_pie_clean_runtime", True' in pie_mode
    assert "_pie_previous_clean_runtime_presentation" in pie_mode
    assert "self._sync_marker_geometry_overlay()" in pie_mode

    marker_sync = _method_source(panel_source, "_sync_marker_geometry_overlay")
    assert "geometry = None if self._pie_active else base" in marker_sync

    frame = _method_source(render_source, "_render_frame")
    assert 'property("_gr_map_studio_pie_clean_runtime")' in frame
    assert "self._record_overlay_rebuild(0.0)" in frame
    assert "return img" in frame

    gpu_frame = _method_source(render_source, "_render_gpu_frame")
    assert 'clean_runtime = bool(self.property("_gr_map_studio_pie_clean_runtime"))' in gpu_frame
    assert "show_light_gizmos" in gpu_frame and "and not clean_runtime" in gpu_frame
    assert "show_light_radius_volumes" in gpu_frame
    assert "show_dummy_helpers" in gpu_frame
    assert "selected_node = None if clean_runtime" in gpu_frame
    assert "gizmo_render_data = None if clean_runtime" in gpu_frame
    assert "helper_render_data = None" in gpu_frame
    assert "show_mesh_hover=bool" in gpu_frame
    # The authored lights still feed the shader; only their editor wireframes
    # and selection state are masked.
    assert "build_scene_lighting_render_data" in gpu_frame
    assert "lighting_render_data=lighting_render_data" in gpu_frame


def test_pie_uses_documented_kotor_keyboard_and_free_look_controls() -> None:
    """The PIE preset must not silently substitute a modern WASD editor map."""

    repo = Path(__file__).resolve().parents[1]
    panel_source = (
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

    movement = _method_source(panel_source, "_emit_pie_move_input")
    assert "QtCore.Qt.Key_W" in movement and "QtCore.Qt.Key_S" in movement
    assert "QtCore.Qt.Key_Z" in movement and "QtCore.Qt.Key_C" in movement
    assert '"camera_turn"' in movement
    assert "QtCore.Qt.Key_A" in movement and "QtCore.Qt.Key_D" in movement

    input_events = _method_source(panel_source, "_handle_pie_input_event")
    assert "QtCore.Qt.Key_CapsLock" in input_events
    assert "QtCore.Qt.MiddleButton" in input_events
    assert "QtCore.Qt.ControlModifier" in input_events
    assert '"zoom_steps"' not in input_events

    camera_input = _method_source(window_source, "_handle_map_studio_pie_camera_input")
    assert 'values.get("zoom_steps"' not in camera_input
    pie_tick = _method_source(window_source, "_tick_map_studio_pie")
    assert "target_turn_velocity = camera_turn * 200.0" in pie_tick
    assert "turn_acceleration = 2000.0 if slowing_or_reversing else 500.0" in pie_tick
    assert "self._map_studio_pie_camera_turn_velocity = current_turn_velocity" in pie_tick


def test_pie_batches_all_retained_actor_poses_before_one_viewport_render() -> None:
    repo = Path(__file__).resolve().parents[1]
    renderer_source = (
        repo
        / "native"
        / "GhostRigger.Core.Rendering"
        / "Python"
        / "src"
        / "core"
        / "rendering"
        / "frame_core"
        / "renderer_setup.py"
    ).read_text(encoding="utf-8")
    viewport_source = (
        repo
        / "native"
        / "GhostRigger.Core.GUI.Display"
        / "Python"
        / "src"
        / "gui"
        / "viewports"
        / "viewport_core"
        / "widgets"
        / "history_animation.py"
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

    renderer_batch = _method_source(renderer_source, "set_character_animation_poses")
    assert "for row in tuple(rows or ())" in renderer_batch
    assert "request_render=request_render" in renderer_batch

    viewport_batch = _method_source(viewport_source, "update_runtime_character_frames")
    assert "set_character_animation_poses" in viewport_batch
    assert "request_render=False" in viewport_batch
    assert viewport_batch.count("self._request_render(") == 1

    pie_tick = _method_source(window_source, "_tick_map_studio_pie")
    assert "_update_map_studio_pie_player_actor" in pie_tick
    assert "_update_map_studio_pie_creature_actors" in pie_tick
    assert pie_tick.count("update_runtime_character_frames(") == 1
    assert "actor_rendered = bool(runtime_rows)" in pie_tick


def test_pie_staggers_stock_sized_npc_pose_work_without_backlog_spikes() -> None:
    """A 32-actor stock scene must not evaluate every idle skeleton at once."""

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class Engine:
        def __init__(self) -> None:
            self.current_time = 0.0
            self.current_animation = SimpleNamespace(name="pause1", length=1.0)
            self.advance_calls: list[float] = []
            self.evaluate_calls = 0

        def advance(self, step: float) -> None:
            self.advance_calls.append(float(step))
            self.current_time += float(step)

        def evaluate(self):
            self.evaluate_calls += 1
            return SimpleNamespace(nodes={})

    engines = [Engine() for _ in range(32)]
    window = SimpleNamespace(
        _map_studio_pie_creature_entries=[
            {
                "actor": SimpleNamespace(
                    root_node=SimpleNamespace(),
                    actor_id=f"npc:{index}",
                    source_model=SimpleNamespace(),
                ),
                "engine": engine,
            }
            for index, engine in enumerate(engines)
        ],
        _map_studio_pie_creature_animation_budget=0.0,
        _map_studio_pie_creature_animation_cursor=0,
    )

    batch_sizes = [
        len(ModuleEditorWindow._update_map_studio_pie_creature_actors(window, 1.0 / 60.0))
        for _ in range(5)
    ]

    assert max(batch_sizes) <= 7
    assert 31 <= sum(batch_sizes) <= 32
    assert max(engine.evaluate_calls for engine in engines) <= 1

    # Slow frames must not request extra pose work.  Before the adaptive cap,
    # the measured 80 ms frame requested about 30 NPCs and the resulting
    # 131 ms frame requested all 32 indefinitely.
    lagged_batch_sizes = [
        len(ModuleEditorWindow._update_map_studio_pie_creature_actors(window, delta))
        for delta in (0.080, 0.131, 0.131, 0.080)
    ]
    assert max(lagged_batch_sizes) <= 7


def test_pie_lagged_pose_cohorts_keep_elapsed_time_and_round_robin_fairness() -> None:
    """Load shedding must not reset an NPC's clock before its turn."""

    from src.gui.windows.module_editor_window import ModuleEditorWindow

    class Engine:
        def __init__(self) -> None:
            self.current_time = 0.0
            self.current_animation = SimpleNamespace(name="pause1", length=1.0)
            self.advance_calls: list[float] = []

        def advance(self, step: float) -> None:
            self.advance_calls.append(float(step))
            self.current_time += float(step)

        def evaluate(self):
            return SimpleNamespace(nodes={})

    engines = [Engine() for _ in range(32)]
    entries = [
        {
            "actor": SimpleNamespace(
                root_node=SimpleNamespace(),
                actor_id=f"npc:{index}",
                source_model=SimpleNamespace(),
            ),
            "engine": engine,
        }
        for index, engine in enumerate(engines)
    ]
    window = SimpleNamespace(
        _map_studio_pie_creature_entries=entries,
        _map_studio_pie_creature_animation_budget=0.0,
        _map_studio_pie_creature_animation_cursor=0,
    )

    first = ModuleEditorWindow._update_map_studio_pie_creature_actors(window, 0.25)
    first_ids = {row[1] for row in first}
    assert len(first) <= 7
    for index, entry in enumerate(entries):
        if f"npc:{index}" in first_ids:
            assert entry["pie_animation_elapsed"] == pytest.approx(0.0)
        else:
            assert entry["pie_animation_elapsed"] == pytest.approx(0.25)

    sampled_ids = set(first_ids)
    for _ in range(4):
        sampled_ids.update(
            row[1]
            for row in ModuleEditorWindow._update_map_studio_pie_creature_actors(window, 0.25)
        )

    assert sampled_ids == {f"npc:{index}" for index in range(32)}
    assert all(engine.advance_calls for engine in engines)
    assert all(engine.advance_calls[0] == pytest.approx(0.25) for engine in engines)


K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


@pytest.mark.skipif(
    not (K2_ROOT / "chitin.key").is_file(),
    reason="Local KOTOR 2 resource installation is unavailable",
)
def test_real_207tel_pie_actor_grounding_keeps_all_32_stock_root_planes_on_their_wok_strata() -> None:
    """Machine proof for the stock positions visible in the reported PIE frame."""

    repo = Path(__file__).resolve().parents[1]
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(repo)):
        item_text = str(item)
        if item_text not in sys.path:
            sys.path.insert(0, item_text)

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_pie import resolve_map_studio_pie_actor_grounding
    from src.core.modules.map_studio_pie_creatures import build_map_studio_pie_creature_plan
    from src.core.modules.map_studio_stock_content_preview import RES_UTC, TemplateModelResolver
    from src.core.modules.module_editor_controller import ModuleEditorController

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="207tel_grounding", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(K2_ROOT / "Modules"),
        game="K2",
        resource_manager=manager,
    )
    assert ok, message
    converted, conversion_message = controller.convert_all_stock_rooms_to_imported_mesh(
        resource_manager=manager
    )
    assert converted, conversion_message
    preview = controller.map_studio_viewport_preview_model(manager)
    built = controller.create_map_studio_pie_session(preview_model=preview)
    assert built.session is not None and built.validation.ok

    placements = controller.map_studio_authored_placements_snapshot()
    template_resources = tuple(getattr(controller, "_authored_creature_resources", ()) or ())
    resolver = TemplateModelResolver(
        manager,
        "K2",
        template_resources=template_resources,
    )
    plan = build_map_studio_pie_creature_plan(
        placements,
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: resolver._template_bytes(resref, RES_UTC),
        template_resources=template_resources,
    )
    authored_positions = tuple(spec.position for spec in plan.specs)
    assert len(plan.specs) == 32

    models: dict[str, object] = {}
    groundings = []
    for spec in plan.specs:
        body_resref = spec.render.body_model_resref
        if body_resref not in models:
            models[body_resref] = manager.load_model_strict(
                body_resref,
                "K2",
                prefer_base_archive=True,
            )
        grounding = resolve_map_studio_pie_actor_grounding(
            built.session.walkmesh,
            models[body_resref],
            spec.position,
        )
        groundings.append(grounding)
        assert grounding.sampled_walkmesh is True
        assert grounding.face_index >= 0
        assert grounding.surface_position[:2] == pytest.approx(spec.position[:2])
        assert abs(grounding.surface_position[2] - spec.position[2]) <= 0.005
        # Every installed 207TEL body follows the retail placement-root plane;
        # a detached BAS head must not be allowed to change this value.
        assert grounding.support_plane_z == 0.0
        assert grounding.support_source == "kotor_root_plane"
        assert grounding.actor_root_position == pytest.approx(grounding.surface_position)
        assert grounding.visual_support_z == pytest.approx(grounding.surface_position[2])

    sampled_z = [row.surface_position[2] for row in groundings]
    assert any(value == pytest.approx(10.621, abs=0.001) for value in sampled_z)
    assert any(value == pytest.approx(10.2005, abs=0.001) for value in sampled_z)
    assert tuple(spec.position for spec in plan.specs) == authored_positions


@pytest.mark.skipif(
    not (K2_ROOT / "chitin.key").is_file(),
    reason="Local KOTOR 2 resource installation is unavailable",
)
def test_pie_default_k2_bas_actor_has_head_and_inherited_locomotion_clips() -> None:
    """Optional machine proof for the exact PMBAM + PMHC01 PIE defaults."""

    import numpy as np

    repo = Path(__file__).resolve().parents[1]
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(repo)):
        item_text = str(item)
        if item_text not in sys.path:
            sys.path.insert(0, item_text)

    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.animation.gpu_skinning import MAX_BONES, MatrixPaletteUploader
    from src.core.assets.resource_manager import ResourceManager
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.modules.map_studio_pie import attach_map_studio_pie_actor
    from src.core.rendering.mesh_render_data import (
        _animated_node_world_transform,
        bas_attachment_palette_model_for_node,
        runtime_source_model_for_node,
    )
    from src.core.rendering.skeleton_render_data import (
        _cached_matrix_palette_uploader,
        _skinning_palette_model_for_node,
        cpu_skin_vbo_arrays,
        extract_skinning_arrays,
    )
    from src.systems.bas.preview_composer import build_bas_preview_model

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    body = manager.load_model_strict("pmbam", "K2", prefer_base_archive=True)
    head = manager.load_model_strict("pmhc01", "K2", prefer_base_archive=True)
    assert body is not None and body.root_node is not None
    assert head is not None and head.root_node is not None
    assert body._gr_source_game == "K2" and head._gr_source_game == "K2"

    actor = build_bas_preview_model(
        body_model=body,
        attachment_models={"head": head},
        name="pmbam_pmhc01_pie_contract",
    )
    assert actor.root_node is not body.root_node
    head_layers = [
        node
        for node in actor.all_nodes()
        if bool(getattr(node, "_gr_bas_attachment_root", False))
        and str(getattr(node, "_gr_bas_attachment_slot", "")).lower() == "head"
    ]
    assert len(head_layers) == 1
    assert str(getattr(head_layers[0], "_gr_bas_attachment_source_model_name", "")).lower() == "pmhc01"

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)
    try:
        entries = AnimationEngine(actor).list_all_animations()
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)
    by_name = {str(entry["name"]).lower(): entry for entry in entries}
    assert {"pause1", "walk", "run"}.issubset(by_name)
    for name in ("pause1", "walk", "run"):
        assert by_name[name]["inherited"] is True
        assert by_name[name]["source_scope"] == "inherited"

    preview = KotorModel(
        name="synthetic_pie_map",
        root_node=ModelNode(name="synthetic_pie_map", flags=int(NodeFlags.HEADER)),
    )
    attached = attach_map_studio_pie_actor(
        preview,
        actor,
        position=(2.0, -3.0, 0.5),
        facing_radians=0.3,
        recompute_bounds=False,
    )
    assert attached is not None
    torso = next(
        node
        for node in preview.all_nodes()
        if str(getattr(node, "name", "")).lower() == "torso"
        and not bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    assert _skinning_palette_model_for_node(torso, preview) is actor

    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)
    try:
        engine = AnimationEngine(actor)
        assert engine.play("pause1", loop=True, blend=False)
        pose = engine.evaluate(0.5)
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)
    pose._gr_animation_scene_object_id = attached.actor_id
    pose._gr_animation_source_model_id = id(actor)
    pose._gr_animation_name = "pause1"

    copied_body_rootdummy = next(
        node
        for node in preview.all_nodes()
        if str(getattr(node, "name", "")).lower() == "rootdummy"
        and not bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    assert engine._base_nodes["rootdummy"].name == copied_body_rootdummy.name
    assert not bool(getattr(engine._base_nodes["rootdummy"], "_gr_bas_attachment_layer", False))
    assert engine._base_nodes["rootdummy"].position[2] == pytest.approx(1.12557, abs=1.0e-5)
    assert pose.nodes["rootdummy"].position[2] == pytest.approx(1.118915, abs=1.0e-5)

    # The actual detachable face skin must retain the head model's palette and
    # land at the non-zero PIE placement exactly once.  The regression applied
    # the actor wrapper matrix a second time only to this BAS skin, while rigid
    # eyes/teeth stayed on the headhook and made the character look headless.
    copied_head_skin = next(
        node
        for node in preview.all_nodes()
        if str(getattr(node, "name", "")).lower() == "head"
        and bool(getattr(node, "is_skin", False))
        and bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    copied_headhook = next(
        node
        for node in preview.all_nodes()
        if str(getattr(node, "name", "")).lower() == "headhook"
        and not bool(getattr(node, "_gr_bas_attachment_layer", False))
    )
    assert runtime_source_model_for_node(copied_head_skin) is actor
    head_palette_model = bas_attachment_palette_model_for_node(copied_head_skin)
    assert head_palette_model is not None
    assert len(head_palette_model.all_nodes()) == len(head.all_nodes()) == 34
    hook_world, _ = _animated_node_world_transform(copied_headhook, pose)
    head_world, _ = _animated_node_world_transform(copied_head_skin, pose)
    assert hook_world[0] == pytest.approx(2.0, abs=0.5)
    assert hook_world[1] == pytest.approx(-3.0, abs=0.5)
    assert hook_world[2] > 0.5
    assert max(abs(head_world[axis] - hook_world[axis]) for axis in range(3)) < 0.5

    positions = np.asarray(torso.vertices, dtype=np.float32)
    skinning = extract_skinning_arrays(torso, len(positions), skeleton_id=id(preview))
    posed_positions, _ = cpu_skin_vbo_arrays(
        torso,
        positions,
        None,
        skinning,
        pose,
        model=preview,
        anim_base_pose=None,
    )
    uploader = _cached_matrix_palette_uploader(actor, MAX_BONES, MatrixPaletteUploader)
    uploader.compute_skin_node_palette(torso, pose)
    assert uploader._skin_palette_formula == "G5_FULL_REF"
    assert uploader._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"
    assert uploader._model_node_count == 61

    edges = {
        (min(int(start), int(end)), max(int(start), int(end)))
        for a, b, c in torso.faces
        for start, end in ((a, b), (b, c), (c, a))
    }
    edge_indices = np.asarray(sorted(edges), dtype=np.int64)
    base_lengths = np.linalg.norm(
        positions[edge_indices[:, 0]] - positions[edge_indices[:, 1]],
        axis=1,
    )
    posed = np.asarray(posed_positions, dtype=np.float32)
    # The body root plane is z=0 in actor space.  Before the BAS duplicate-name
    # fix, PMHC01's zeroed rootdummy replaced PMBAM's 1.12557 m bind and this
    # exact torso landed at z=[-1.124, 0.308], matching the PIE screenshot.
    assert float(np.min(posed[:, 2])) >= -0.01
    assert float(np.max(posed[:, 2])) > 1.5
    posed_lengths = np.linalg.norm(
        posed[edge_indices[:, 0]] - posed[edge_indices[:, 1]],
        axis=1,
    )
    ratios = posed_lengths[base_lengths > 1.0e-7] / base_lengths[base_lengths > 1.0e-7]
    assert float(np.max(ratios)) < 3.0
    assert float(np.percentile(ratios, 99)) < 1.5


@pytest.mark.skipif(
    not (K2_ROOT / "Modules" / "207TEL.rim").is_file(),
    reason="Local KOTOR 2 207TEL module is unavailable",
)
def test_pie_installed_207tel_ramana_retains_detachable_head_actor_contract() -> None:
    """The real Ramana UTC must reach PIE as one body+headhook actor."""

    from dataclasses import replace

    repo = Path(__file__).resolve().parents[1]
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(repo)):
        item_text = str(item)
        if item_text not in sys.path:
            sys.path.insert(0, item_text)

    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_pie import prepare_map_studio_pie_actor_hierarchy
    from src.core.modules.map_studio_pie_creatures import (
        build_map_studio_pie_creature_plan,
        prepare_map_studio_pie_creature_actor_artifacts,
    )
    from src.core.modules.map_studio_stock_content_preview import (
        RES_UTC,
        TemplateModelResolver,
        load_kotor_model_from_bytes,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController
    from src.systems.bas.preview_composer import build_bas_preview_model

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="207tel", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(K2_ROOT / "Modules"),
        game="K2",
        resource_manager=manager,
    )
    assert ok, message
    placements = controller.map_studio_authored_placements_snapshot()
    assert placements is not None
    template_resources = tuple(
        getattr(controller, "_authored_creature_resources", ()) or ()
    )
    resolver = TemplateModelResolver(
        manager,
        "K2",
        template_resources=template_resources,
    )
    plan = build_map_studio_pie_creature_plan(
        placements,
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: resolver._template_bytes(resref, RES_UTC),
        template_resources=template_resources,
    )
    assert len(plan.specs) == 32
    assert sum(bool(spec.render.head_model_resref) for spec in plan.specs) == 23
    ramana = next(
        spec for spec in plan.specs if spec.source_template_resref == "203_ramana"
    )
    assert ramana.render.body_model_resref == "n_twilekf"
    assert ramana.render.head_model_resref == "twilek_f"
    assert ramana.warnings == ()

    result = prepare_map_studio_pie_creature_actor_artifacts(
        replace(plan, specs=(ramana,)),
        manager,
        resolver,
        "K2",
        {},
        {},
        model_bytes_loader=load_kotor_model_from_bytes,
        model_composer=build_bas_preview_model,
        animation_engine_factory=AnimationEngine,
        hierarchy_preparer=prepare_map_studio_pie_actor_hierarchy,
        supermodel_configurer=SuperModelResolver.configure,
    )
    try:
        assert result.failures == ()
        assert len(result.entries) == 1
        entry = result.entries[0]
        assert entry.animation_name == "pause1"
        body_rootdummy = next(
            node
            for node in entry.actor_model.all_nodes()
            if str(getattr(node, "name", "")).lower() == "rootdummy"
            and not bool(getattr(node, "_gr_bas_attachment_layer", False))
        )
        assert entry.animation_engine._base_nodes["rootdummy"] is body_rootdummy
        assert body_rootdummy.position[2] == pytest.approx(1.06298, abs=1.0e-5)
        assert entry.initial_pose.nodes["rootdummy"].position[2] == pytest.approx(
            1.04256,
            abs=1.0e-5,
        )
        nodes = []
        stack = [entry.prepared_root]
        visited = set()
        while stack:
            node = stack.pop()
            if node is None or id(node) in visited:
                continue
            visited.add(id(node))
            nodes.append(node)
            stack.extend(tuple(getattr(node, "children", ()) or ()))
        head_roots = [
            node
            for node in nodes
            if bool(getattr(node, "_gr_bas_attachment_root", False))
            and str(getattr(node, "_gr_bas_attachment_slot", "")).lower() == "head"
        ]
        assert len(head_roots) == 1
        assert str(
            getattr(head_roots[0], "_gr_bas_attachment_source_model_name", "")
        ).lower() == "twilek_f"
        assert str(getattr(head_roots[0], "_gr_bas_socket_name", "")).lower() == "headhook"
        head_skins = {
            str(getattr(node, "name", "")).lower(): len(getattr(node, "vertices", ()) or ())
            for node in nodes
            if bool(getattr(node, "_gr_bas_attachment_layer", False))
            and bool(getattr(node, "is_skin", False))
        }
        assert head_skins == {"head": 343, "hair": 359, "tongue": 22}

        import numpy as np

        from src.core.rendering.skeleton_render_data import (
            cpu_skin_vbo_arrays,
            extract_skinning_arrays,
        )

        body_torso = next(
            node
            for node in entry.actor_model.all_nodes()
            if str(getattr(node, "name", "")).lower() == "torso"
            and bool(getattr(node, "is_skin", False))
            and not bool(getattr(node, "_gr_bas_attachment_layer", False))
        )
        body_positions = np.asarray(body_torso.vertices, dtype=np.float32)
        body_skinning = extract_skinning_arrays(
            body_torso,
            len(body_positions),
            skeleton_id=id(entry.actor_model),
        )
        posed_body, _ = cpu_skin_vbo_arrays(
            body_torso,
            body_positions,
            None,
            body_skinning,
            entry.initial_pose,
            model=entry.actor_model,
            anim_base_pose=None,
        )
        posed_body = np.asarray(posed_body, dtype=np.float32)
        assert float(np.min(posed_body[:, 2])) > 0.5
        assert float(np.max(posed_body[:, 2])) > 1.4
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)


@pytest.mark.skipif(
    not (K2_ROOT / "Modules" / "207TEL.rim").is_file(),
    reason="Local KOTOR 2 207TEL module is unavailable",
)
def test_pie_installed_207tel_g_exthgr_uses_retail_full_body_racetex() -> None:
    """The real modeltype-F Rodian uses exact RaceTex on a copy-owned DAG."""

    from dataclasses import replace

    repo = Path(__file__).resolve().parents[1]
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(repo)):
        item_text = str(item)
        if item_text not in sys.path:
            sys.path.insert(0, item_text)

    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_pie import prepare_map_studio_pie_actor_hierarchy
    from src.core.modules.map_studio_pie_creatures import (
        build_map_studio_pie_creature_plan,
        prepare_map_studio_pie_creature_actor_artifacts,
    )
    from src.core.modules.map_studio_stock_content_preview import (
        RES_UTC,
        TemplateModelResolver,
        load_kotor_model_from_bytes,
    )
    from src.core.modules.module_editor_controller import ModuleEditorController
    from src.systems.bas.preview_composer import build_bas_preview_model

    def render_meshes(root):
        meshes = []
        stack = [root]
        visited = set()
        while stack:
            node = stack.pop()
            if node is None or id(node) in visited:
                continue
            visited.add(id(node))
            stack.extend(tuple(getattr(node, "children", ()) or ()))
            if (
                tuple(getattr(node, "vertices", ()) or ())
                and tuple(getattr(node, "faces", ()) or ())
                and bool(getattr(node, "render", True))
                and not bool(getattr(node, "is_aabb", False))
            ):
                meshes.append(node)
        return meshes

    manager = ResourceManager()
    assert manager.set_k2_dir(str(K2_ROOT))
    controller = ModuleEditorController()
    controller.new_project(name="207tel", game="K2")
    ok, message = controller.import_stock_module_from_rim(
        module_resref="207tel",
        modules_dir=str(K2_ROOT / "Modules"),
        game="K2",
        resource_manager=manager,
    )
    assert ok, message
    placements = controller.map_studio_authored_placements_snapshot()
    assert placements is not None
    template_resources = tuple(
        getattr(controller, "_authored_creature_resources", ()) or ()
    )
    resolver = TemplateModelResolver(
        manager,
        "K2",
        template_resources=template_resources,
    )
    plan = build_map_studio_pie_creature_plan(
        placements,
        resolver,
        game="K2",
        utc_reader=lambda resref, _game: resolver._template_bytes(resref, RES_UTC),
        template_resources=template_resources,
    )
    rodian = next(
        spec for spec in plan.specs if spec.source_template_resref == "g_exthgr"
    )
    assert rodian.render.body_model_resref == "n_rodian"
    assert rodian.render.head_model_resref == ""
    assert rodian.render.body_texture_resref == "n_rodian02"
    assert manager.load_texture_image("n_rodian02", "K2", max_size=16) is not None

    result = prepare_map_studio_pie_creature_actor_artifacts(
        replace(plan, specs=(rodian,)),
        manager,
        resolver,
        "K2",
        {},
        {},
        model_bytes_loader=load_kotor_model_from_bytes,
        model_composer=build_bas_preview_model,
        animation_engine_factory=AnimationEngine,
        hierarchy_preparer=prepare_map_studio_pie_actor_hierarchy,
        supermodel_configurer=SuperModelResolver.configure,
    )
    try:
        assert result.failures == ()
        assert len(result.entries) == 1
        entry = result.entries[0]
        source_textures = {
            str(getattr(node, "name", "") or "").strip().lower():
            str(getattr(node, "texture_clean", "") or "").strip().lower()
            for node in render_meshes(entry.actor_model.root_node)
        }
        assert source_textures["rarm"] == "null"
        assert source_textures["larm"] == "null"
        assert source_textures["torso02"] == "null"
        assert source_textures["head"] == "null"
        assert source_textures["hair"] == "n_rodian01"

        prepared_meshes = render_meshes(entry.prepared_root)
        assert prepared_meshes
        assert {
            str(getattr(node, "texture_clean", "") or "").strip().lower()
            for node in prepared_meshes
        } == {"n_rodian02"}
        assert all(
            getattr(node, "_gr_instance_texture_override", "") == "n_rodian02"
            for node in prepared_meshes
        )
        # The shared retail model/prototype was not mutated by this instance.
        assert source_textures == {
            str(getattr(node, "name", "") or "").strip().lower():
            str(getattr(node, "texture_clean", "") or "").strip().lower()
            for node in render_meshes(entry.actor_model.root_node)
        }
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)
