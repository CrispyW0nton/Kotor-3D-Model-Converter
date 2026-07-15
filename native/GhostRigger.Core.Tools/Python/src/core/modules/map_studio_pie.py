"""Read-only Map Studio Play-in-Editor simulation.

PIE is a deterministic authoring preflight, not an embedded Odyssey runtime.
It validates player spawn, walkmesh traversal, boundary blocking, ramp height,
click-to-move reachability, and third-person camera obstruction without
mutating the KMAP project.  Export plus a manual ``warp plcaa`` remains the
authoritative KOTOR proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import math
from typing import Any, Iterable

from src.math.walkmesh_runtime import (
    CollisionTriangle,
    SegmentCollisionIndex,
    WalkmeshRuntimeIndex,
)

from .authored_gameplay_marker_geometry import (
    AuthoredGameplayMarkerFootprint,
    AuthoredGameplayMarkerGeometry,
    AuthoredGameplayMarkerLine,
)
from .authored_imported_mesh import authored_room_uses_unresolved_stock_geometry
from .authored_module_walkmesh import combine_authored_module_walkmesh


Vec3 = tuple[float, float, float]


def kotor_player_walk_speed(game: object) -> float:
    """Retail ``creaturespeed.2da`` PLAYER walk speed."""

    return 1.70 if str(game or "K1").strip().upper() == "K2" else 3.20


def kotor_player_run_speed(_game: object) -> float:
    """Retail K1/K2 ``creaturespeed.2da`` PLAYER run speed."""

    return 5.40


def kotor_actor_yaw_for_world_facing(facing_radians: float) -> float:
    """Convert a world XY bearing into the yaw of a native KOTOR actor.

    PIE movement uses the same bearing convention as authored gameplay markers:
    zero points along world ``+X``. Native KOTOR character models face ``+Y``
    in model space, so their runtime wrapper needs a negative quarter-turn before
    applying that world bearing.
    """

    return float(facing_radians) - (math.pi * 0.5)


@dataclass(frozen=True)
class MapStudioPIEConfig:
    """Stable simulation and player-controller tuning."""

    fixed_step: float = 1.0 / 60.0
    max_frame_delta: float = 0.25
    max_substeps: int = 16
    player_radius: float = 0.24
    max_step_up: float = 0.45
    max_step_down: float = 0.75
    eye_height: float = 1.45
    camera_padding: float = 0.12
    minimum_camera_distance: float = 0.35
    camera_return_speed: float = 8.0
    path_block_timeout: float = 0.75


@dataclass(frozen=True)
class MapStudioPIEValidation:
    """Honest start gate for simulation."""

    ok: bool
    blocking_issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapStudioPIEEvent:
    """One deterministic diagnostic produced by the simulation."""

    kind: str
    message: str
    position: Vec3 = (0.0, 0.0, 0.0)


@dataclass
class MapStudioPIEPlayerState:
    """Mutable runtime-only player proxy state."""

    position: Vec3
    facing_radians: float = 0.0
    velocity: Vec3 = (0.0, 0.0, 0.0)
    face_index: int = -1
    moving: bool = False
    blocked: bool = False
    destination: Vec3 | None = None
    path: tuple[Vec3, ...] = ()


@dataclass(frozen=True)
class MapStudioPIEFrame:
    """Immutable frame snapshot consumed by the GUI."""

    simulation_time: float
    position: Vec3
    facing_radians: float
    velocity: Vec3
    face_index: int
    moving: bool
    blocked: bool
    destination: Vec3 | None
    path: tuple[Vec3, ...]
    events: tuple[MapStudioPIEEvent, ...] = ()


@dataclass(frozen=True)
class MapStudioPIEBuildResult:
    """Session construction result with proof-relevant counts."""

    session: "MapStudioPIESession | None"
    validation: MapStudioPIEValidation
    walkable_face_count: int = 0
    collision_triangle_count: int = 0
    entity_registry: Any = None


@dataclass
class MapStudioPIEActorAttachment:
    """Runtime-only character subtree attached to the resident map model."""

    preview_model: Any
    source_model: Any
    root_node: Any
    actor_id: str = "__map_studio_pie_player__"
    support_plane_z: float = 0.0
    surface_position: Vec3 = (0.0, 0.0, 0.0)

    def set_transform(self, position: Vec3, facing_radians: float) -> None:
        """Place the actor's support plane without touching authored KMAP transforms.

        ``position`` is a module-world walkmesh point.  ``support_plane_z`` is
        measured once in actor-model space, so locomotion may update this
        runtime wrapper without baking an offset into the source Odyssey DAG or
        the authored GIT/IFO placement.
        """

        point = tuple(float(value) for value in tuple(position)[:3])
        if len(point) < 3:
            return
        half = kotor_actor_yaw_for_world_facing(facing_radians) * 0.5
        self.surface_position = point  # type: ignore[assignment]
        self.root_node.position = (
            point[0],
            point[1],
            point[2] - float(self.support_plane_z),
        )
        self.root_node.rotation = (0.0, 0.0, math.sin(half), math.cos(half))

    def detach(self, *, recompute_bounds: bool = True) -> None:
        """Remove only this transient subtree from the preview model."""

        model_root = getattr(self.preview_model, "root_node", None)
        if model_root is None:
            return
        model_root.children = [
            child for child in tuple(getattr(model_root, "children", ()) or ())
            if child is not self.root_node
        ]
        self.root_node.parent = None
        if recompute_bounds:
            try:
                self.preview_model.compute_bounds()
            except Exception:
                pass


@dataclass(frozen=True)
class MapStudioPIEActorGrounding:
    """Runtime placement result keeping model support on one WOK stratum.

    The authored position remains evidence and is never rewritten.  The actor
    root position is a derived preview value only.  This distinction matters
    for stock modules: tiny GIT/WOK float differences are normal and must not
    become silent source edits merely because PIE presents the actor on the
    exact sampled triangle.
    """

    authored_position: Vec3
    surface_position: Vec3
    actor_root_position: Vec3
    support_plane_z: float = 0.0
    face_index: int = -1
    sampled_walkmesh: bool = False
    support_source: str = "kotor_root_plane"

    @property
    def visual_support_z(self) -> float:
        return float(self.actor_root_position[2]) + float(self.support_plane_z)


def prepare_map_studio_pie_actor_hierarchy(actor_model: Any) -> Any | None:
    """Return one copy-owned Odyssey DAG for later GUI-thread attachment.

    PIE actor preparation may run away from the Qt thread, but publishing the
    resulting hierarchy into the live map model must not.  Keeping this copy
    step separate lets the worker do the expensive traversal while the GUI
    continues to render the flattened authoring previews.

    BAS attachment roots intentionally retain references to their immutable
    source models so the renderer can resolve head-local animation.  A plain
    ``deepcopy`` follows those references and needlessly clones the complete
    head model (including animation data) once per placed creature.  Seed the
    copy memo with those read-only source objects so the copied DAG preserves
    their identity without duplicating them.
    """

    source_root = getattr(actor_model, "root_node", None)
    if source_root is None:
        return None
    memo: dict[int, Any] = {}
    stack = [source_root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        if node is None or id(node) in visited:
            continue
        visited.add(id(node))
        source_model = getattr(node, "_gr_bas_attachment_source_model_ref", None)
        if source_model is not None:
            memo[id(source_model)] = source_model
        stack.extend(tuple(getattr(node, "children", ()) or ()))
    copied_root = deepcopy(source_root, memo)
    copied_root.parent = None
    return copied_root


def attach_map_studio_pie_actor(
    preview_model: Any,
    actor_model: Any,
    *,
    position: Vec3,
    facing_radians: float = 0.0,
    actor_id: str = "__map_studio_pie_player__",
    recompute_bounds: bool = True,
    prepared_root: Any = None,
    append_to_preview: bool = True,
    support_plane_z: float | None = None,
) -> MapStudioPIEActorAttachment | None:
    """Attach one preserved, animatable MDL hierarchy to a map preview.

    Stock Map Studio placements are deliberately flattened for inexpensive
    authoring selection.  A PIE player cannot use that representation because
    skinning and animation require the original Odyssey DAG.  This function
    adds a runtime-only wrapper plus a deep copy of the actor hierarchy; it
    never serializes the subtree into KMAP or authored module resources.
    """

    preview_root = getattr(preview_model, "root_node", None)
    source_root = getattr(actor_model, "root_node", None)
    clean_id = str(actor_id or "__map_studio_pie_player__").strip()
    if preview_root is None or source_root is None or not clean_id:
        return None
    try:
        from src.core.geometry.model_data import ModelNode, NodeFlags
    except Exception:
        from core.geometry.model_data import ModelNode, NodeFlags  # type: ignore

    wrapper = ModelNode(name="map_studio_pie_player", flags=int(NodeFlags.HEADER))
    copied_root = prepared_root or prepare_map_studio_pie_actor_hierarchy(actor_model)
    if copied_root is None or copied_root is source_root:
        return None
    wrapper.parent = preview_root
    copied_root.parent = wrapper
    wrapper.children = [copied_root]
    setattr(wrapper, "_gr_scene_object_id", clean_id)
    setattr(wrapper, "_gr_scene_import_id", clean_id)
    setattr(wrapper, "_gr_scene_object_root", True)
    setattr(wrapper, "_gr_scene_object_root_ref", wrapper)
    setattr(wrapper, "_gr_scene_gpu_transform", True)
    setattr(wrapper, "_gr_runtime_source_model_id", id(actor_model))
    # The resident map model is not a valid skin-palette authority for this
    # copied actor.  Keep the immutable actor model on the runtime-only wrapper
    # so render backends can preserve its Odyssey DFS/qBone contract without
    # serializing a model object into KMAP or duplicating the reference per node.
    setattr(wrapper, "_gr_runtime_source_model_ref", actor_model)
    setattr(wrapper, "_gr_map_studio_pie_actor", True)
    stack = [copied_root]
    visited: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        setattr(node, "_gr_scene_object_id", clean_id)
        setattr(node, "_gr_scene_import_id", clean_id)
        setattr(node, "_gr_scene_object_root_ref", wrapper)
        setattr(node, "_gr_runtime_source_model_id", id(actor_model))
        setattr(node, "_gr_map_studio_pie_actor", True)
        for child in tuple(getattr(node, "children", ()) or ()):
            child.parent = node
            stack.append(child)
    if append_to_preview:
        preview_root.children.append(wrapper)
    attachment = MapStudioPIEActorAttachment(
        preview_model=preview_model,
        source_model=actor_model,
        root_node=wrapper,
        actor_id=clean_id,
        support_plane_z=(
            actor_model_support_plane_z(actor_model)
            if support_plane_z is None
            else float(support_plane_z)
        ),
    )
    attachment.set_transform(position, facing_radians)
    if recompute_bounds:
        try:
            preview_model.compute_bounds()
        except Exception:
            pass
    return attachment


def _quat_rotate(quaternion: object, point: Vec3) -> Vec3:
    try:
        qx, qy, qz, qw = (float(value) for value in tuple(quaternion)[:4])
    except Exception:
        return point
    length_sq = (qx * qx) + (qy * qy) + (qz * qz) + (qw * qw)
    if length_sq <= 1.0e-12:
        return point
    inverse_length = 1.0 / math.sqrt(length_sq)
    qx, qy, qz, qw = (value * inverse_length for value in (qx, qy, qz, qw))
    px, py, pz = point
    tx = 2.0 * ((qy * pz) - (qz * py))
    ty = 2.0 * ((qz * px) - (qx * pz))
    tz = 2.0 * ((qx * py) - (qy * px))
    return (
        px + (qw * tx) + ((qy * tz) - (qz * ty)),
        py + (qw * ty) + ((qz * tx) - (qx * tz)),
        pz + (qw * tz) + ((qx * ty) - (qy * tx)),
    )


def _model_nodes(model: Any) -> tuple[Any, ...]:
    all_nodes = getattr(model, "all_nodes", None)
    if callable(all_nodes):
        try:
            return tuple(all_nodes() or ())
        except Exception:
            pass
    root = getattr(model, "root_node", None)
    if root is None:
        return ()
    rows: list[Any] = []
    stack = [root]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        rows.append(node)
        stack.extend(reversed(tuple(getattr(node, "children", ()) or ())))
    return tuple(rows)


def _is_actor_support_node_name(name: object) -> bool:
    clean = "".join(character for character in str(name or "").strip().lower() if character.isalnum())
    return any(token in clean for token in ("foot", "paw", "hoof", "toe"))


def _actor_model_support_measurement(actor_model: Any) -> tuple[float, str]:
    """Measure a corroborated model-space support plane for a retained actor.

    Retail Odyssey character roots are authored on the placement plane.  Small
    negative skinned-vertex excursions during an idle pose are therefore not a
    license to lift the whole actor; doing so creates visible foot skating.
    Only a materially different root is compensated, and only when a named
    foot/paw/hoof/toe node corroborates the render-geometry support height.
    BAS attachments are excluded so a malformed or temporarily detached head
    can never move the body off the floor.
    """

    geometry_z: list[float] = []
    support_node_z: list[float] = []
    for node in _model_nodes(actor_model):
        if bool(getattr(node, "_gr_bas_attachment_layer", False)):
            continue
        try:
            world_position, world_rotation = node.world_transform()
            wx, wy, wz = (float(value) for value in tuple(world_position)[:3])
            wq = tuple(float(value) for value in tuple(world_rotation)[:4])
        except Exception:
            wx, wy, wz = (0.0, 0.0, 0.0)
            wq = (0.0, 0.0, 0.0, 1.0)
        if _is_actor_support_node_name(getattr(node, "name", "")):
            if math.isfinite(wz):
                support_node_z.append(wz)

        vertices = tuple(getattr(node, "vertices", ()) or ())
        faces = tuple(getattr(node, "faces", ()) or ())
        if not vertices or not faces:
            continue
        if (
            not bool(getattr(node, "render", True))
            or bool(getattr(node, "_gr_hidden", False))
            or bool(getattr(node, "is_aabb", False))
            or bool(getattr(node, "background_geometry", False))
            or int(getattr(node, "vertex_space", 0) or 0) == 2
        ):
            continue
        referenced: set[int] = set()
        for face in faces:
            for raw_index in tuple(face)[:3]:
                try:
                    index = int(raw_index)
                except (TypeError, ValueError):
                    continue
                if 0 <= index < len(vertices):
                    referenced.add(index)
        vertex_space = int(getattr(node, "vertex_space", 0) or 0)
        for index in referenced:
            try:
                local = tuple(float(value) for value in tuple(vertices[index])[:3])
            except (TypeError, ValueError):
                continue
            if len(local) < 3 or not all(math.isfinite(value) for value in local):
                continue
            if vertex_space == 1:
                z_value = local[2]
            else:
                rotated = _quat_rotate(wq, local)  # type: ignore[arg-type]
                z_value = rotated[2] + wz
            if math.isfinite(z_value):
                geometry_z.append(float(z_value))

    if not geometry_z:
        return 0.0, "kotor_root_plane_no_geometry"
    geometry_floor = min(geometry_z)
    # KOTOR bodies in both games intentionally straddle the placement root by
    # a few millimetres.  Preserve that retail contract instead of chasing an
    # animation-dependent bounding-box minimum every frame.
    if abs(geometry_floor) <= 0.05:
        return 0.0, "kotor_root_plane"
    if (
        support_node_z
        and abs(min(support_node_z) - geometry_floor) <= 0.35
        and abs(geometry_floor) <= 2.0
    ):
        return float(geometry_floor), "corroborated_support_geometry"
    return 0.0, "kotor_root_plane_unverified_offset"


def actor_model_support_plane_z(actor_model: Any) -> float:
    """Return the stable model-space support plane used by PIE placement."""

    return _actor_model_support_measurement(actor_model)[0]


def resolve_map_studio_pie_actor_grounding(
    walkmesh: Any,
    actor_model: Any,
    authored_position: Vec3,
    *,
    radius: float = 0.0,
    max_step_up: float = 0.45,
    max_step_down: float = 0.75,
    support_plane_z: float | None = None,
) -> MapStudioPIEActorGrounding:
    """Derive one feet-on-WOK preview transform without editing source data.

    Sampling is height-aware, so stacked floors keep the stratum nearest the
    authored GIT Z.  Step bounds deliberately prevent airborne or deliberately
    elevated actors from being teleported to a distant floor.
    """

    values = tuple(float(value) for value in tuple(authored_position)[:3])
    if len(values) < 3:
        values = (0.0, 0.0, 0.0)
    authored = (values[0], values[1], values[2])
    surface = authored
    face_index = -1
    sampled = False
    validate = getattr(walkmesh, "validate_disc", None)
    if callable(validate):
        try:
            sample = validate(
                authored,
                radius=max(0.0, float(radius)),
                max_step_up=max(0.0, float(max_step_up)),
                max_step_down=max(0.0, float(max_step_down)),
            )
        except Exception:
            sample = None
        if sample is not None:
            sampled_values = tuple(float(value) for value in tuple(getattr(sample, "position", ()))[:3])
            if len(sampled_values) == 3 and all(math.isfinite(value) for value in sampled_values):
                surface = (sampled_values[0], sampled_values[1], sampled_values[2])
                face_index = int(getattr(sample, "face_index", -1) or 0)
                sampled = True

    if support_plane_z is None:
        support, support_source = _actor_model_support_measurement(actor_model)
    else:
        support = float(support_plane_z)
        support_source = "explicit_support_plane"
    if not math.isfinite(support):
        support = 0.0
        support_source = "kotor_root_plane_nonfinite_support"
    root_position = (surface[0], surface[1], surface[2] - support)
    return MapStudioPIEActorGrounding(
        authored_position=authored,
        surface_position=surface,
        actor_root_position=root_position,
        support_plane_z=support,
        face_index=face_index,
        sampled_walkmesh=sampled,
        support_source=support_source,
    )


def collision_triangles_from_preview_model(model: Any) -> tuple[CollisionTriangle, ...]:
    """Extract static room collision from the already-resident preview model.

    Placement actors, backdrops, hidden meshes, and AABB helper nodes are
    intentionally excluded.  The output is immutable and indexed once at PIE
    start, so camera movement never reloads room geometry or renderer assets.
    """

    triangles: list[CollisionTriangle] = []
    for node in _model_nodes(model):
        vertices = tuple(getattr(node, "vertices", ()) or ())
        faces = tuple(getattr(node, "faces", ()) or ())
        if not vertices or not faces:
            continue
        if not str(getattr(node, "_gr_map_studio_room_resref", "") or ""):
            continue
        if bool(getattr(node, "_gr_map_studio_placement_id", "")):
            continue
        if bool(getattr(node, "_gr_map_studio_backdrop", False)) or bool(getattr(node, "background_geometry", False)):
            continue
        if not bool(getattr(node, "render", True)) or bool(getattr(node, "is_aabb", False)):
            continue
        vertex_space = int(getattr(node, "vertex_space", 0) or 0)
        if vertex_space == 2:
            continue
        if vertex_space == 1:
            world_vertices = [tuple(float(value) for value in tuple(vertex)[:3]) for vertex in vertices]
        else:
            try:
                world_position, world_rotation = node.world_transform()
                wx, wy, wz = (float(value) for value in tuple(world_position)[:3])
            except Exception:
                wx, wy, wz = (0.0, 0.0, 0.0)
                world_rotation = (0.0, 0.0, 0.0, 1.0)
            world_vertices = []
            for vertex in vertices:
                local = tuple(float(value) for value in tuple(vertex)[:3])
                rotated = _quat_rotate(world_rotation, local)  # type: ignore[arg-type]
                world_vertices.append((rotated[0] + wx, rotated[1] + wy, rotated[2] + wz))
        source = f"{getattr(node, '_gr_map_studio_room_resref', '')}:{getattr(node, 'name', '')}"
        for face in faces:
            try:
                a, b, c = (world_vertices[int(index)] for index in tuple(face)[:3])
            except (IndexError, TypeError, ValueError):
                continue
            cross = (
                ((b[1] - a[1]) * (c[2] - a[2])) - ((b[2] - a[2]) * (c[1] - a[1])),
                ((b[2] - a[2]) * (c[0] - a[0])) - ((b[0] - a[0]) * (c[2] - a[2])),
                ((b[0] - a[0]) * (c[1] - a[1])) - ((b[1] - a[1]) * (c[0] - a[0])),
            )
            if sum(value * value for value in cross) <= 1.0e-16:
                continue
            triangles.append(CollisionTriangle(a=a, b=b, c=c, source=source))
    return tuple(triangles)


class MapStudioPIESession:
    """Fixed-step, read-only player and camera simulation."""

    def __init__(
        self,
        wok: Any,
        *,
        game: str,
        spawn_position: Vec3,
        spawn_facing: float = 0.0,
        collision_triangles: Iterable[CollisionTriangle] = (),
        config: MapStudioPIEConfig | None = None,
    ) -> None:
        self.game = str(game or "K1").strip().upper()
        self.config = config or MapStudioPIEConfig()
        self.walkmesh = WalkmeshRuntimeIndex(
            wok,
            game=self.game,
            player_radius=self.config.player_radius,
        )
        self.collision_triangles = tuple(collision_triangles or ())
        self.collision = SegmentCollisionIndex(self.collision_triangles)
        spawn = tuple(float(value) for value in tuple(spawn_position)[:3])
        sample = self.walkmesh.validate_disc(
            spawn,
            radius=self.config.player_radius,
            max_step_up=math.inf,
            max_step_down=math.inf,
        )
        blocking: list[str] = []
        warnings: list[str] = []
        if not self.walkmesh.walkable_faces:
            blocking.append(f"{self.game} PIE found no retail-walkable WOK faces.")
        if sample is None:
            blocking.append(
                "Player start is not on a walkable WOK face with enough capsule clearance. "
                "Move the authored player start onto a green walkmesh region."
            )
            start_position, face_index = spawn, -1
        else:
            start_position, face_index = sample.position, sample.face_index
        if not self.collision_triangles:
            warnings.append("No static room triangles were available; camera obstruction cannot be simulated.")
        self.validation = MapStudioPIEValidation(ok=not blocking, blocking_issues=tuple(blocking), warnings=tuple(warnings))
        self.state = MapStudioPIEPlayerState(
            position=start_position,
            facing_radians=float(spawn_facing),
            face_index=face_index,
        )
        self._move_input = (0.0, 0.0)
        self._camera_azimuth_degrees = 90.0
        self._run_input = False
        self._path_index = 0
        self._path_run = True
        self._blocked_time = 0.0
        self._accumulator = 0.0
        self._simulation_time = 0.0
        self._events: list[MapStudioPIEEvent] = []
        self._resolved_camera_distance: float | None = None

    @property
    def simulation_time(self) -> float:
        return float(self._simulation_time)

    def set_move_input(
        self,
        forward: float,
        strafe: float,
        *,
        camera_azimuth_degrees: float,
        run: bool = False,
    ) -> None:
        self._move_input = (
            max(-1.0, min(1.0, float(forward))),
            max(-1.0, min(1.0, float(strafe))),
        )
        self._camera_azimuth_degrees = float(camera_azimuth_degrees)
        self._run_input = bool(run)
        if abs(self._move_input[0]) > 1.0e-7 or abs(self._move_input[1]) > 1.0e-7:
            self.clear_destination()

    def set_camera_azimuth(self, camera_azimuth_degrees: float) -> None:
        """Update camera-relative locomotion while movement keys stay held."""

        self._camera_azimuth_degrees = float(camera_azimuth_degrees)

    def clear_destination(self) -> None:
        self.state.destination = None
        self.state.path = ()
        self._path_index = 0
        self._blocked_time = 0.0

    def set_destination(self, position: Vec3, *, run: bool = True) -> bool:
        if self.state.face_index < 0:
            return False
        target = tuple(float(value) for value in tuple(position)[:3])
        sample = self.walkmesh.validate_disc(
            target,
            radius=self.config.player_radius,
            max_step_up=math.inf,
            max_step_down=math.inf,
        )
        if sample is None:
            self._events.append(MapStudioPIEEvent("destination_rejected", "Destination is outside walkable WOK clearance.", target))
            return False
        route = self.walkmesh.route(self.state.face_index, sample.face_index, sample.position)
        if not route:
            self._events.append(
                MapStudioPIEEvent(
                    "destination_unreachable",
                    "Destination is on a disconnected walkmesh island; PIE did not fabricate a route.",
                    sample.position,
                )
            )
            return False
        self.state.destination = sample.position
        self.state.path = route
        self._path_index = 0
        self._path_run = bool(run)
        self._blocked_time = 0.0
        return True

    def _manual_direction(self) -> tuple[float, float] | None:
        forward, strafe = self._move_input
        magnitude = math.sqrt((forward * forward) + (strafe * strafe))
        if magnitude <= 1.0e-7:
            return None
        forward, strafe = forward / max(1.0, magnitude), strafe / max(1.0, magnitude)
        azimuth = math.radians(self._camera_azimuth_degrees)
        camera_forward = (-math.cos(azimuth), -math.sin(azimuth))
        camera_right = (-math.sin(azimuth), math.cos(azimuth))
        direction = (
            (camera_forward[0] * forward) + (camera_right[0] * strafe),
            (camera_forward[1] * forward) + (camera_right[1] * strafe),
        )
        length = math.sqrt((direction[0] * direction[0]) + (direction[1] * direction[1])) or 1.0
        return (direction[0] / length, direction[1] / length)

    def _path_direction(self) -> tuple[float, float] | None:
        while self._path_index < len(self.state.path):
            target = self.state.path[self._path_index]
            dx = target[0] - self.state.position[0]
            dy = target[1] - self.state.position[1]
            distance = math.sqrt((dx * dx) + (dy * dy))
            if distance <= max(0.08, self.config.player_radius * 0.5):
                self._path_index += 1
                continue
            return (dx / distance, dy / distance)
        if self.state.destination is not None:
            self._events.append(MapStudioPIEEvent("destination_reached", "Player reached the simulated destination.", self.state.position))
        self.clear_destination()
        return None

    def _step(self, delta_time: float) -> None:
        if not self.validation.ok:
            return
        direction = self._manual_direction()
        speed = kotor_player_run_speed(self.game) if self._run_input else kotor_player_walk_speed(self.game)
        path_driven = direction is None and bool(self.state.path)
        if path_driven:
            direction = self._path_direction()
            speed = kotor_player_run_speed(self.game) if self._path_run else kotor_player_walk_speed(self.game)
        if direction is None:
            self.state.velocity = (0.0, 0.0, 0.0)
            self.state.moving = False
            self.state.blocked = False
            self._blocked_time = 0.0
            return
        before = self.state.position
        move = self.walkmesh.move_disc(
            before,
            self.state.face_index,
            (direction[0] * speed * delta_time, direction[1] * speed * delta_time),
            radius=self.config.player_radius,
            max_step_up=self.config.max_step_up,
            max_step_down=self.config.max_step_down,
        )
        self.state.position = move.position
        self.state.face_index = move.face_index
        self.state.blocked = move.blocked
        self.state.moving = move.moved
        self.state.velocity = tuple((move.position[index] - before[index]) / delta_time for index in range(3))  # type: ignore[assignment]
        if move.moved:
            self.state.facing_radians = math.atan2(self.state.velocity[1], self.state.velocity[0])
        if move.blocked and path_driven:
            self._blocked_time += delta_time
            if self._blocked_time >= self.config.path_block_timeout:
                self._events.append(
                    MapStudioPIEEvent(
                        "path_blocked",
                        "Click-to-move was blocked by WOK clearance; route stopped instead of crossing invalid ground.",
                        self.state.position,
                    )
                )
                self.clear_destination()
        else:
            self._blocked_time = 0.0

    def advance(self, real_delta_time: float) -> MapStudioPIEFrame:
        """Advance using a bounded fixed-step accumulator independent of paint FPS."""

        delta = max(0.0, min(float(real_delta_time), self.config.max_frame_delta))
        self._accumulator += delta
        steps = 0
        fixed = max(1.0e-6, float(self.config.fixed_step))
        while self._accumulator + 1.0e-12 >= fixed and steps < max(1, int(self.config.max_substeps)):
            self._step(fixed)
            self._accumulator -= fixed
            self._simulation_time += fixed
            steps += 1
        if steps >= max(1, int(self.config.max_substeps)) and self._accumulator >= fixed:
            self._accumulator = math.fmod(self._accumulator, fixed)
            self._events.append(
                MapStudioPIEEvent(
                    "simulation_backlog_dropped",
                    "PIE dropped stale simulation backlog after a long editor stall.",
                    self.state.position,
                )
            )
        events = tuple(self._events)
        self._events.clear()
        return MapStudioPIEFrame(
            simulation_time=self._simulation_time,
            position=self.state.position,
            facing_radians=self.state.facing_radians,
            velocity=self.state.velocity,
            face_index=self.state.face_index,
            moving=self.state.moving,
            blocked=self.state.blocked,
            destination=self.state.destination,
            path=self.state.path[self._path_index :],
            events=events,
        )

    def resolve_camera_distance(
        self,
        target: Vec3,
        desired_eye: Vec3,
        *,
        delta_time: float,
    ) -> float:
        """Clamp inward immediately and ease outward after obstruction clears."""

        desired_distance = math.sqrt(sum((desired_eye[index] - target[index]) ** 2 for index in range(3)))
        collision_distance = self.collision.clipped_distance(
            target,
            desired_eye,
            padding=self.config.camera_padding,
            minimum_distance=self.config.minimum_camera_distance,
        )
        if self._resolved_camera_distance is None:
            self._resolved_camera_distance = min(desired_distance, collision_distance)
        elif collision_distance < self._resolved_camera_distance:
            self._resolved_camera_distance = collision_distance
        else:
            alpha = min(1.0, max(0.0, float(delta_time)) * self.config.camera_return_speed)
            self._resolved_camera_distance += (collision_distance - self._resolved_camera_distance) * alpha
        return max(0.0, min(desired_distance, self._resolved_camera_distance))

    def reset_camera_collision(self) -> None:
        self._resolved_camera_distance = None

    def player_eye_target(self) -> Vec3:
        return (
            self.state.position[0],
            self.state.position[1],
            self.state.position[2] + self.config.eye_height,
        )

    def overlay_geometry(self) -> AuthoredGameplayMarkerGeometry:
        """Return transient player/facing/path guides for the existing overlay renderer."""

        x, y, z = self.state.position
        radius = self.config.player_radius
        points = tuple(
            (x + math.cos((math.tau * index) / 16.0) * radius, y + math.sin((math.tau * index) / 16.0) * radius, z + 0.025)
            for index in range(16)
        )
        color = "#29b6f6"
        lines: list[AuthoredGameplayMarkerLine] = [
            AuthoredGameplayMarkerLine(
                placement_id="__map_studio_pie_player__",
                kind="pie_player",
                label="PIE Player",
                start=(x, y, z + 0.05),
                end=(
                    x + math.cos(self.state.facing_radians) * 0.8,
                    y + math.sin(self.state.facing_radians) * 0.8,
                    z + 0.05,
                ),
                color=color,
                role="pie_facing",
            )
        ]
        route = (self.state.position,) + tuple(self.state.path[self._path_index :])
        for index, (start, end) in enumerate(zip(route, route[1:])):
            lines.append(
                AuthoredGameplayMarkerLine(
                    placement_id=f"__map_studio_pie_path_{index}__",
                    kind="pie_path",
                    label="PIE Route",
                    start=(start[0], start[1], start[2] + 0.035),
                    end=(end[0], end[1], end[2] + 0.035),
                    color=color,
                    role="pie_path",
                )
            )
        return AuthoredGameplayMarkerGeometry(
            marker_count=1,
            footprints=(
                AuthoredGameplayMarkerFootprint(
                    placement_id="__map_studio_pie_player__",
                    kind="pie_player",
                    label="PIE Player",
                    points=points,
                    color=color,
                    role="pie_player",
                ),
            ),
            lines=tuple(lines),
        )


def build_map_studio_pie_session(
    project: Any,
    *,
    preview_model: Any = None,
    config: MapStudioPIEConfig | None = None,
    combined_walkmesh: Any = None,
) -> MapStudioPIEBuildResult:
    """Build one immutable-derived simulation session from an authored project.

    ``combined_walkmesh`` may supply a precombined
    ``combine_authored_module_walkmesh`` result (the controller caches it per
    authored revision); recombining large converted modules costs seconds per
    Play press otherwise.
    """

    blocking: list[str] = []
    warnings: list[str] = []
    for room in tuple(getattr(project, "rooms", ()) or ()):
        metadata = dict(getattr(room, "metadata", {}) or {})
        if str(metadata.get("source") or "").strip().lower() != "stock_module_import":
            continue
        if type(getattr(room, "primitive", None)).__name__ != "ImportedMeshRoomPrimitive":
            if authored_room_uses_unresolved_stock_geometry(room):
                # The walkmesh compiler emits the user-facing warning and
                # excludes this source-preservation placeholder from collision.
                continue
            blocking.append(
                f"Stock room {getattr(room, 'room_resref', '(unnamed)')} still uses placeholder geometry. "
                "Convert stock rooms to editable imported meshes before simulation."
            )
    combined = combined_walkmesh if combined_walkmesh is not None else combine_authored_module_walkmesh(project)
    blocking.extend(tuple(combined.blocking_issues or ()))
    warnings.extend(tuple(combined.warnings or ()))
    placements = getattr(project, "placements", None)
    entry = getattr(placements, "entry_point", None)
    if entry is None:
        blocking.append("Authored module has no IFO player entry point.")
        spawn = (0.0, 0.0, 0.0)
        facing = 0.0
    else:
        values = tuple(getattr(entry, "position", ()) or ())
        if len(values) < 3:
            blocking.append("Authored IFO player entry point has no XYZ position.")
            spawn = (0.0, 0.0, 0.0)
        else:
            spawn = tuple(float(value) for value in values[:3])
        facing = float(getattr(entry, "facing", 0.0) or 0.0)
    collision_triangles = collision_triangles_from_preview_model(preview_model) if preview_model is not None else ()
    session = MapStudioPIESession(
        combined.wok,
        game=str(getattr(project, "game", "K1") or "K1"),
        spawn_position=spawn,  # type: ignore[arg-type]
        spawn_facing=facing,
        collision_triangles=collision_triangles,
        config=config,
    )
    blocking.extend(session.validation.blocking_issues)
    warnings.extend(session.validation.warnings)
    from .map_studio_pie_entities import build_pie_entity_registry

    entity_registry = build_pie_entity_registry(project)
    warnings.extend(entity_registry.coverage_warnings)
    validation = MapStudioPIEValidation(
        ok=not blocking,
        blocking_issues=tuple(dict.fromkeys(blocking)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    session.validation = validation
    session.entity_registry = entity_registry
    return MapStudioPIEBuildResult(
        session=session if validation.ok else None,
        validation=validation,
        walkable_face_count=len(session.walkmesh.walkable_faces),
        collision_triangle_count=len(collision_triangles),
        entity_registry=entity_registry,
    )


__all__ = [
    "MapStudioPIEBuildResult",
    "MapStudioPIEActorAttachment",
    "MapStudioPIEActorGrounding",
    "MapStudioPIEConfig",
    "MapStudioPIEEvent",
    "MapStudioPIEFrame",
    "MapStudioPIEPlayerState",
    "MapStudioPIESession",
    "MapStudioPIEValidation",
    "attach_map_studio_pie_actor",
    "actor_model_support_plane_z",
    "prepare_map_studio_pie_actor_hierarchy",
    "build_map_studio_pie_session",
    "collision_triangles_from_preview_model",
    "kotor_actor_yaw_for_world_facing",
    "kotor_player_run_speed",
    "kotor_player_walk_speed",
    "resolve_map_studio_pie_actor_grounding",
]
