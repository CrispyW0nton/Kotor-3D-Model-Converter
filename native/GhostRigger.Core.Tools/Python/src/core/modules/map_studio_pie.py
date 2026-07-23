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
from .map_studio_pie_party import party_follow_positions


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
    # Doors auto-open when the player's planar distance to the door is within
    # this radius (approx. door width plus reach), and re-close past it plus a
    # small hysteresis margin so a player lingering on the threshold does not
    # flicker the door.
    door_open_radius: float = 2.75
    door_close_hysteresis: float = 0.6
    # When movement stalls at an open doorway between two disconnected room
    # walkmesh islands, PIE probes this far past the door for the far-side
    # floor and steps the player across (an editor stand-in for the engine's
    # room-to-room transition, which PIE does not otherwise simulate).
    door_transition_reach: float = 2.75


@dataclass
class MapStudioPIEDoorState:
    """Runtime open/closed state for one authored door in the simulation."""

    entity_id: str
    tag: str
    position: Vec3
    facing: float = 0.0
    open_radius: float = 2.75
    half_width: float = 1.0
    vertical_reach: float = 1.75
    locked: bool = False
    is_open: bool = False
    transition_module: str = ""
    transition_target: str = ""
    external_contact_reported: bool = False
    locked_contact_reported: bool = False


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
    entity_id: str = ""
    target_id: str = ""
    animation_role: str = ""
    animation_candidates: tuple[str, ...] = ()
    value: int | float | str | None = None


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
    door_states: tuple[MapStudioPIEDoorState, ...] = ()
    gameplay: Any = None


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
    model_yaw_offset_radians: float = -(math.pi * 0.5)

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
        half = (float(facing_radians) + float(self.model_yaw_offset_radians)) * 0.5
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
    model_yaw_offset_radians: float = -(math.pi * 0.5),
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
        model_yaw_offset_radians=float(model_yaw_offset_radians),
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
        self.entity_registry: Any = None
        self.gameplay: Any = None
        self._doors: list[MapStudioPIEDoorState] | None = None
        self._walkmesh_face_components: dict[int, int] | None = None

    @property
    def simulation_time(self) -> float:
        return float(self._simulation_time)

    def _ensure_doors(self) -> list[MapStudioPIEDoorState]:
        """Build the door-state list once from the attached entity registry."""

        if self._doors is not None:
            return self._doors
        doors: list[MapStudioPIEDoorState] = []
        registry = getattr(self, "entity_registry", None)
        of_kind = getattr(registry, "of_kind", None)
        if callable(of_kind):
            for entity in of_kind("door"):
                position = tuple(float(v) for v in tuple(getattr(entity, "position", ()) or ())[:3])
                if len(position) < 3:
                    continue
                metadata = dict(getattr(entity, "metadata", {}) or {})
                opening_width = float(metadata.get("doorway_opening_width", 0.0) or 0.0)
                doors.append(
                    MapStudioPIEDoorState(
                        entity_id=str(getattr(entity, "entity_id", "")),
                        tag=str(getattr(entity, "tag", "")),
                        position=position,  # type: ignore[arg-type]
                        facing=float(getattr(entity, "facing", 0.0) or 0.0),
                        open_radius=max(1.0, float(getattr(entity, "target_radius", 1.0) or 1.0) + self.config.door_open_radius),
                        half_width=max(
                            0.25,
                            opening_width * 0.5,
                            float(getattr(entity, "target_radius", 1.0) or 1.0),
                        ),
                        vertical_reach=max(
                            0.75,
                            float(getattr(entity, "target_radius", 1.0) or 1.0) * 0.5
                            + self.config.player_radius
                            + self.config.max_step_up,
                        ),
                        locked=bool(getattr(entity, "locked", False)),
                        transition_module=str(getattr(entity, "transition_module", "") or ""),
                        transition_target=str(getattr(entity, "transition_target", "") or ""),
                    )
                )
        self._doors = doors
        return doors

    def door_states(self) -> tuple[MapStudioPIEDoorState, ...]:
        return tuple(self._ensure_doors())

    def configure_gameplay(
        self,
        entity_registry: Any,
        *,
        dialogue_loader: Any = None,
        item_inspector: Any = None,
        tlk_lookup: Any = None,
        dialogue_condition_evaluator: Any = None,
        dialogue_start_overrides: Any = None,
        journal_seed: Any = None,
        script_loader: Any = None,
        party_combatants: Any = None,
        player_combat_stats: Any = None,
    ) -> Any:
        """Attach one runtime-only gameplay coordinator to this PIE session."""

        from .map_studio_pie_gameplay import MapStudioPIEGameplayRuntime

        self.entity_registry = entity_registry
        self._doors = None
        self.gameplay = MapStudioPIEGameplayRuntime(
            entity_registry,
            game=self.game,
            dialogue_loader=dialogue_loader,
            item_inspector=item_inspector,
            tlk_lookup=tlk_lookup,
            dialogue_condition_evaluator=dialogue_condition_evaluator,
            dialogue_start_overrides=dialogue_start_overrides,
            journal_seed=journal_seed,
            script_loader=script_loader,
            party_combatants=party_combatants,
            player_combat_stats=player_combat_stats,
        )
        self.gameplay.advance(
            0.0,
            player_position=self.state.position,
            player_facing_radians=self.state.facing_radians,
            camera_forward=self._gameplay_camera_forward(),
        )
        self._append_gameplay_events()
        return self.gameplay

    def _gameplay_camera_forward(self) -> Vec3:
        azimuth = math.radians(self._camera_azimuth_degrees)
        return (-math.cos(azimuth), -math.sin(azimuth), 0.0)

    def _append_gameplay_events(self) -> None:
        gameplay = self.gameplay
        if gameplay is None:
            return
        for event in gameplay.drain_events():
            entity = self.entity_registry.by_id(event.entity_id) if self.entity_registry is not None else None
            position = tuple(getattr(entity, "position", self.state.position) or self.state.position)
            self._events.append(
                MapStudioPIEEvent(
                    kind=event.kind,
                    message=event.message,
                    position=position,  # type: ignore[arg-type]
                    entity_id=event.entity_id,
                    target_id=event.target_id,
                    animation_role=event.animation_role,
                    animation_candidates=event.animation_candidates,
                    value=event.value,
                )
            )

    def gameplay_snapshot(self) -> Any:
        return self.gameplay.snapshot() if self.gameplay is not None else None

    def cycle_gameplay_focus(self, direction: int = 1) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.cycle_focus(direction)
        self._append_gameplay_events()
        return result

    def focus_gameplay_entity(self, entity_id: str) -> Any:
        """Focus one world-picked entity without running its primary action."""

        if self.gameplay is None:
            return None
        result = self.gameplay.focus_entity(entity_id)
        self._append_gameplay_events()
        return result

    def activate_gameplay_focus(self, command: str | None = None) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.activate_focused(command)
        self._sync_gameplay_door_states()
        self._append_gameplay_events()
        return result

    def activate_gameplay_entity(self, entity_id: str, command: str | None = None) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.activate_entity(entity_id, command)
        self._sync_gameplay_door_states()
        self._append_gameplay_events()
        return result

    def continue_gameplay_dialogue(self) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.continue_dialogue()
        self._append_gameplay_events()
        return result

    def choose_gameplay_dialogue(self, number: int) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.choose_dialogue(number)
        self._append_gameplay_events()
        return result

    def take_gameplay_item(self, entity_id: str, resref: str, quantity: int = 1) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.take_item(entity_id, resref, quantity)
        self._append_gameplay_events()
        return result

    def take_all_gameplay_items(self, entity_id: str) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.take_all(entity_id)
        self._append_gameplay_events()
        return result

    def toggle_gameplay_combat_pause(self) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.toggle_combat_pause()
        self._append_gameplay_events()
        return result

    def clear_gameplay_combat_queue(self) -> Any:
        if self.gameplay is None:
            return None
        result = self.gameplay.clear_combat_queue()
        self._append_gameplay_events()
        return result

    def close_gameplay_modal(self) -> bool:
        if self.gameplay is None:
            return False
        closed = bool(self.gameplay.close_modal())
        self._append_gameplay_events()
        return closed

    def _sync_gameplay_door_states(self) -> None:
        if self.gameplay is None:
            return
        interaction = self.gameplay.snapshot().interaction
        open_doors = set(interaction.open_doors)
        unlocked = set(interaction.unlocked_entities)
        for door in self._ensure_doors():
            if door.entity_id in unlocked:
                door.locked = False
            if door.entity_id in open_doors:
                door.is_open = True

    def _update_doors(self) -> None:
        """Open doors the player is near; close them past the hysteresis band."""

        self._sync_gameplay_door_states()
        px, py, pz = self.state.position
        for door in self._ensure_doors():
            distance = math.hypot(door.position[0] - px, door.position[1] - py)
            vertical_distance = abs(door.position[2] - pz)
            in_open_reach = distance <= door.open_radius and vertical_distance <= door.vertical_reach
            outside_close_reach = (
                distance > door.open_radius + self.config.door_close_hysteresis
                or vertical_distance > door.vertical_reach
            )
            if outside_close_reach:
                door.external_contact_reported = False
                door.locked_contact_reported = False
            if door.locked:
                if door.is_open:
                    door.is_open = False
                if in_open_reach and not door.locked_contact_reported:
                    door.locked_contact_reported = True
                    self._events.append(
                        MapStudioPIEEvent(
                            "door_locked",
                            f"Door {door.tag or door.entity_id} is locked and stays closed in PIE.",
                            door.position,
                        )
                    )
                continue
            if not door.is_open and in_open_reach:
                door.is_open = True
                self._events.append(
                    MapStudioPIEEvent("door_opened", f"Door {door.tag or door.entity_id} opened as the player approached.", door.position)
                )
            elif door.is_open and outside_close_reach:
                door.is_open = False
                self._events.append(
                    MapStudioPIEEvent("door_closed", f"Door {door.tag or door.entity_id} closed behind the player.", door.position)
                )

    def _walkmesh_component(self, face_index: int) -> int:
        """Return the connected walkmesh-island id for one walkable face."""

        if self._walkmesh_face_components is None:
            adjacency = dict(getattr(self.walkmesh, "_adjacency", {}) or {})
            components: dict[int, int] = {}
            component_id = 0
            for root in sorted(int(index) for index in adjacency):
                if root in components:
                    continue
                stack = [root]
                components[root] = component_id
                while stack:
                    current = stack.pop()
                    for neighbour in adjacency.get(current, ()):
                        neighbour = int(neighbour)
                        if neighbour not in components:
                            components[neighbour] = component_id
                            stack.append(neighbour)
                component_id += 1
            self._walkmesh_face_components = components
        return self._walkmesh_face_components.get(int(face_index), -1)

    def _door_side_sample(
        self,
        door: MapStudioPIEDoorState,
        normal: tuple[float, float],
        side: float,
        reference_z: float,
    ):
        """Find the nearest valid floor on one intended side of a door plane."""

        minimum = max(0.5, self.config.player_radius * 2.1)
        offsets = tuple(dict.fromkeys((minimum, min(1.25, self.config.door_transition_reach), self.config.door_transition_reach)))
        for offset in offsets:
            probe = (
                door.position[0] + normal[0] * side * offset,
                door.position[1] + normal[1] * side * offset,
                reference_z,
            )
            sample = self.walkmesh.validate_disc(
                probe,
                radius=self.config.player_radius,
                max_step_up=math.inf,
                max_step_down=math.inf,
            )
            if sample is not None and sample.face_index >= 0:
                return sample
        return None

    def _try_room_transition(self, direction: tuple[float, float]) -> bool:
        """Step the player across an open doorway between two walkmesh islands.

        The combined module walkmesh keeps each room as its own island, so
        ``move_disc`` stops the player at a room boundary. When movement stalls
        next to an open door, probe just past the door along the travel
        direction; if the far side is a walkable face on a different island,
        move the player onto it. Inter-module doors (with a transition target)
        cannot be simulated, so PIE reports the intended destination instead.
        """

        px, py, pz = self.state.position
        direction_length = math.hypot(float(direction[0]), float(direction[1]))
        if direction_length <= 1.0e-8:
            return False
        travel = (float(direction[0]) / direction_length, float(direction[1]) / direction_length)
        current_component = self._walkmesh_component(self.state.face_index)
        for door in self._ensure_doors():
            if not door.is_open or door.locked:
                continue
            if math.hypot(door.position[0] - px, door.position[1] - py) > door.open_radius:
                continue
            if abs(door.position[2] - pz) > door.vertical_reach:
                continue
            normal = (math.cos(door.facing), math.sin(door.facing))
            tangent = (-normal[1], normal[0])
            forward_dot = (travel[0] * normal[0]) + (travel[1] * normal[1])
            if abs(forward_dot) < 0.5:
                continue
            relative = (px - door.position[0], py - door.position[1])
            signed_plane_distance = (relative[0] * normal[0]) + (relative[1] * normal[1])
            lateral_distance = abs((relative[0] * tangent[0]) + (relative[1] * tangent[1]))
            if lateral_distance > door.half_width + self.config.player_radius:
                continue
            # The player must be moving toward/across the plane, not away from
            # a nearby door or parallel to it.
            if signed_plane_distance * forward_dot > 1.0e-6:
                continue
            travel_side = 1.0 if forward_dot > 0.0 else -1.0
            source_sample = self._door_side_sample(door, normal, -travel_side, pz)
            destination_sample = self._door_side_sample(door, normal, travel_side, pz)
            if source_sample is None or destination_sample is None:
                continue
            source_component = self._walkmesh_component(source_sample.face_index)
            destination_component = self._walkmesh_component(destination_sample.face_index)
            if (
                current_component < 0
                or source_component != current_component
                or destination_component < 0
                or destination_component == current_component
            ):
                continue
            if door.transition_target or door.transition_module:
                if not door.external_contact_reported:
                    door.external_contact_reported = True
                    self._events.append(
                        MapStudioPIEEvent(
                            "module_transition_blocked",
                            f"Door {door.tag or door.entity_id} transitions to "
                            f"{door.transition_module or 'another area'}/{door.transition_target or '(entry)'}; "
                            "PIE simulates a single module and cannot follow module transitions.",
                            door.position,
                        )
                    )
                continue
            self.state.position = destination_sample.position
            self.state.face_index = destination_sample.face_index
            self.state.blocked = False
            self._events.append(
                MapStudioPIEEvent(
                    "room_transition",
                    f"Player stepped through door {door.tag or door.entity_id} into the adjoining room.",
                    destination_sample.position,
                )
            )
            return True
        return False

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
        gameplay = self.gameplay_snapshot()
        if gameplay is not None and bool(getattr(gameplay, "movement_locked", False)):
            self._events.append(
                MapStudioPIEEvent(
                    "destination_rejected",
                    f"Movement is paused while PIE is presenting {getattr(gameplay, 'mode', 'gameplay')} state.",
                    self.state.position,
                )
            )
            return False
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
        gameplay = self.gameplay_snapshot()
        if gameplay is not None and bool(getattr(gameplay, "movement_locked", False)):
            self.state.velocity = (0.0, 0.0, 0.0)
            self.state.moving = False
            self.state.blocked = False
            self._blocked_time = 0.0
            return
        self._update_doors()
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
        # If the walkmesh stopped the player at a room boundary (little or no
        # forward progress) and an open door is right there, step across into
        # the adjoining room's island.
        forward_progress = ((move.position[0] - before[0]) * direction[0]) + ((move.position[1] - before[1]) * direction[1])
        if move.blocked and forward_progress <= self.config.player_radius * 0.25 and self._try_room_transition(direction):
            self._update_doors()
            self.state.velocity = tuple((self.state.position[index] - before[index]) / delta_time for index in range(3))  # type: ignore[assignment]
            self.state.moving = True
            self.state.facing_radians = math.atan2(direction[1], direction[0])
            self._blocked_time = 0.0
            return
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
        if self.gameplay is not None:
            self.gameplay.advance(
                delta,
                player_position=self.state.position,
                player_facing_radians=self.state.facing_radians,
                camera_forward=self._gameplay_camera_forward(),
            )
            self._sync_gameplay_door_states()
            self._append_gameplay_events()
        gameplay_snapshot = self.gameplay_snapshot()
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
            door_states=tuple(self._ensure_doors()),
            gameplay=gameplay_snapshot,
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

    def party_follow_targets(self, follower_count: int) -> tuple[Vec3, ...]:
        """Walkmesh-snapped trailing formation slots for PIE party followers.

        The leader is the player; followers trail behind the player's current
        facing, each slot projected onto the walkmesh floor near the player's
        height so companions stay on walkable ground.
        """

        reference_z = float(self.state.position[2])

        def _sampler(point: Vec3) -> Vec3 | None:
            sample = self.walkmesh.sample_at(float(point[0]), float(point[1]), reference_z)
            return sample.position if sample is not None else None

        return party_follow_positions(
            self.state.position,
            self.state.facing_radians,
            int(follower_count),
            walkmesh_sampler=_sampler,
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
        footprints: list[AuthoredGameplayMarkerFootprint] = [
            AuthoredGameplayMarkerFootprint(
                    placement_id="__map_studio_pie_player__",
                    kind="pie_player",
                    label="PIE Player",
                    points=points,
                    color=color,
                    role="pie_player",
                )
        ]
        focus = getattr(self.gameplay_snapshot(), "focus", None)
        if focus is not None:
            fx, fy, fz = focus.position
            focus_radius = max(0.35, float(focus.target_radius) + 0.12)
            focus_points = tuple(
                (
                    fx + math.cos((math.tau * index) / 24.0) * focus_radius,
                    fy + math.sin((math.tau * index) / 24.0) * focus_radius,
                    fz + 0.04,
                )
                for index in range(24)
            )
            footprints.append(
                AuthoredGameplayMarkerFootprint(
                    placement_id=focus.entity_id,
                    kind="pie_focus",
                    label=focus.display_name,
                    points=focus_points,
                    color="#ffd54f" if focus.in_range else "#ff8a65",
                    role="pie_focus",
                )
            )
        follower_count = int(getattr(self, "_party_follower_count", 0) or 0)
        if follower_count > 0:
            for slot_index, target in enumerate(self.party_follow_targets(follower_count), start=1):
                tx, ty, tz = target
                slot_points = tuple(
                    (
                        tx + math.cos((math.tau * index) / 20.0) * 0.4,
                        ty + math.sin((math.tau * index) / 20.0) * 0.4,
                        tz + 0.03,
                    )
                    for index in range(20)
                )
                footprints.append(
                    AuthoredGameplayMarkerFootprint(
                        placement_id=f"__map_studio_pie_party_{slot_index}__",
                        kind="pie_party",
                        label=f"Party {slot_index}",
                        points=slot_points,
                        color="#66bb6a",
                        role="pie_party",
                    )
                )
        return AuthoredGameplayMarkerGeometry(
            marker_count=len(footprints),
            footprints=tuple(footprints),
            lines=tuple(lines),
        )

    def set_party_follower_count(self, count: int) -> None:
        """Set how many trailing party follow-slot markers PIE previews (0 hides)."""

        self._party_follower_count = max(0, min(2, int(count)))


def build_map_studio_pie_session(
    project: Any,
    *,
    preview_model: Any = None,
    config: MapStudioPIEConfig | None = None,
    combined_walkmesh: Any = None,
    template_inspector: Any = None,
    dialogue_loader: Any = None,
    item_inspector: Any = None,
    tlk_lookup: Any = None,
    dialogue_condition_evaluator: Any = None,
    dialogue_start_overrides: Any = None,
    journal_seed: Any = None,
    script_loader: Any = None,
    party_combatants: Any = None,
    player_combat_stats: Any = None,
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

    entity_registry = build_pie_entity_registry(project, template_inspector=template_inspector)
    warnings.extend(entity_registry.coverage_warnings)
    validation = MapStudioPIEValidation(
        ok=not blocking,
        blocking_issues=tuple(dict.fromkeys(blocking)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
    session.validation = validation
    session.configure_gameplay(
        entity_registry,
        dialogue_loader=dialogue_loader,
        item_inspector=item_inspector,
        tlk_lookup=tlk_lookup,
        dialogue_condition_evaluator=dialogue_condition_evaluator,
        dialogue_start_overrides=dialogue_start_overrides,
        journal_seed=journal_seed,
        script_loader=script_loader,
        party_combatants=party_combatants,
        player_combat_stats=player_combat_stats,
    )
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
    "MapStudioPIEDoorState",
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
