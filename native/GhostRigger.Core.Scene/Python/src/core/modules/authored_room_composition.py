"""Composable authored room geometry for Map Studio.

This module is the headless bridge between Map Studio creation tools and the
module export pipeline.  Editors should store primitive intent here first, then
compile it into ``AuthoredRoomGeometry`` for MDL/MDX/WOK packaging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Union

from src.core.geometry.mesh_topology import compact_indexed_mesh
from src.core.geometry.polygon_mesh_operations import (
    AttributeChannel,
    CombinedMeshResult,
    IndexedMeshOperand,
    IndexedPolygonMesh,
    combine_indexed_meshes,
)

from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh, RectangularRoomPrimitive
from .authored_walkmesh_surfaces import require_walkable_walkmesh_surface, resolve_walkmesh_surface_id, walkmesh_surface_name
from .authored_room_primitives import (
    ArchPrimitive,
    CubePrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    FloorPrimitive,
    PrimitiveMaterial,
    RampPrimitive,
    StairsPrimitive,
    WallPrimitive,
    build_arch_mesh,
    build_cube_mesh,
    build_cylinder_mesh,
    build_door_frame_mesh,
    build_floor_mesh,
    build_floor_wok,
    build_ramp_mesh,
    build_ramp_wok,
    build_stairs_mesh,
    build_stairs_wok,
    build_wall_mesh,
)
from .module_format import WOKData, WOKFace


DOOR_TRANSITION_SURFACE_ID = 18


BaseRoomPrimitive = Union[
    FloorPrimitive,
    WallPrimitive,
    CubePrimitive,
    RampPrimitive,
    StairsPrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    ArchPrimitive,
]


@dataclass(frozen=True)
class PrimitiveTransform:
    """Durable transform intent for one authored primitive instance.

    Map Studio gizmos should persist transforms here before compilation so the
    visible MDL mesh and derived WOK stay in lockstep for export.
    """

    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_degrees_z: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class PlacedRoomPrimitive:
    """A primitive plus editor-authored transform data."""

    primitive: BaseRoomPrimitive | "CombinedRoomPrimitive"
    transform: PrimitiveTransform = field(default_factory=PrimitiveTransform)
    name: str = ""


@dataclass(frozen=True)
class CombinedRoomPrimitiveSource:
    """One procedural source recipe used by a true polygon mesh combine.

    ``face_indices`` is an optional selection in the source recipe's compiled
    face space.  An empty tuple means all faces.  WOK faces are not render-face
    indexed, so ``inherit`` deliberately retains the source's complete authored
    WOK proxy; ``exclude`` explicitly transfers no WOK ownership.
    """

    primitive: "RoomPrimitive"
    face_indices: tuple[int, ...] = ()
    source_name: str = ""
    walkmesh_policy: str = "inherit"


@dataclass(frozen=True)
class CombinedRoomPrimitive:
    """Human-readable procedural recipe for one genuine polygon mesh object."""

    name: str
    sources: tuple[CombinedRoomPrimitiveSource, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


RoomPrimitive = Union[BaseRoomPrimitive, PlacedRoomPrimitive, CombinedRoomPrimitive]


@dataclass(frozen=True)
class CombinedRoomPrimitiveCompilation:
    """Compiled mesh plus stable source provenance used by Separate Shells."""

    mesh: PrimitiveMesh
    indexed_result: CombinedMeshResult
    source_face_indices: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class AuthoredRoomComposition:
    """Editable primitive collection for one room model."""

    room_resref: str
    floor: FloorPrimitive | PlacedRoomPrimitive
    primitives: tuple[RoomPrimitive, ...] = ()
    helper_meshes: tuple[PrimitiveMesh, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoredRoomCompositionValidation:
    """Validation result for primitive room intent before compilation."""

    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def _normalise_name(value: Any) -> str:
    return str(value or "").strip().lower()[:16]


def _transform_manifest(transform: PrimitiveTransform) -> dict[str, Any]:
    return {
        "translation": [float(value) for value in transform.translation],
        "rotation_degrees_z": float(transform.rotation_degrees_z),
        "scale": [float(value) for value in transform.scale],
        "pivot": [float(value) for value in transform.pivot],
    }


def _transform_point(point: tuple[float, float, float], transform: PrimitiveTransform) -> tuple[float, float, float]:
    px, py, pz = (float(value) for value in transform.pivot)
    sx, sy, sz = (float(value) for value in transform.scale)
    tx, ty, tz = (float(value) for value in transform.translation)
    x = (float(point[0]) - px) * sx
    y = (float(point[1]) - py) * sy
    z = (float(point[2]) - pz) * sz
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (
        x * cos_a - y * sin_a + px + tx,
        x * sin_a + y * cos_a + py + ty,
        z + pz + tz,
    )


def _transform_normal(normal: tuple[float, float, float], transform: PrimitiveTransform) -> tuple[float, float, float]:
    # Points are scaled before the authored Z rotation, so normals must use
    # the inverse-transpose of that scale before the rotation.  Applying only
    # the rotation makes lighting visibly wrong under non-uniform scale.
    sx, sy, sz = (float(value) for value in transform.scale)
    epsilon = 1.0e-12
    nx = float(normal[0]) / sx if abs(sx) > epsilon else 0.0
    ny = float(normal[1]) / sy if abs(sy) > epsilon else 0.0
    nz = float(normal[2]) / sz if abs(sz) > epsilon else 0.0
    angle = math.radians(float(transform.rotation_degrees_z))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    x = nx * cos_a - ny * sin_a
    y = nx * sin_a + ny * cos_a
    z = nz
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 0.0:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def transform_primitive_mesh(mesh: PrimitiveMesh, transform: PrimitiveTransform, *, name: str = "") -> PrimitiveMesh:
    """Apply an editor transform to a primitive mesh without mutating it."""

    return PrimitiveMesh(
        name=name or mesh.name,
        vertices=tuple(_transform_point(vertex, transform) for vertex in mesh.vertices),
        faces=tuple(mesh.faces),
        normals=tuple(_transform_normal(normal, transform) for normal in mesh.normals),
        uvs=tuple(mesh.uvs),
        texture=mesh.texture,
        diffuse=mesh.diffuse,
        ambient=mesh.ambient,
        metadata={
            **dict(mesh.metadata),
            "transform": _transform_manifest(transform),
            "transform_source": "src.core.modules.authored_room_composition",
        },
    )


def transform_wok_data(wok: WOKData, transform: PrimitiveTransform) -> WOKData:
    """Apply the same editor transform to WOK vertices as the visible mesh."""

    return WOKData(
        name=wok.name,
        verts=[_transform_point(vertex, transform) for vertex in wok.verts],
        faces=[
            WOKFace(
                face.v1,
                face.v2,
                face.v3,
                face.surface,
                face.adj1,
                face.adj2,
                face.adj3,
                face.trans1,
                face.trans2,
                face.trans3,
            )
            for face in wok.faces
        ],
    )


def _base_primitive(primitive: RoomPrimitive) -> BaseRoomPrimitive | CombinedRoomPrimitive:
    return primitive.primitive if isinstance(primitive, PlacedRoomPrimitive) else primitive


def _floor_base_and_transform(floor: FloorPrimitive | PlacedRoomPrimitive) -> tuple[FloorPrimitive, PrimitiveTransform | None]:
    if isinstance(floor, PlacedRoomPrimitive):
        base = floor.primitive
        if not isinstance(base, FloorPrimitive):
            raise TypeError(f"Authored room composition floor must be a FloorPrimitive, not {type(base)!r}.")
        return base, floor.transform
    return floor, None


def _primitive_name(primitive: FloorPrimitive | RoomPrimitive) -> str:
    if isinstance(primitive, PlacedRoomPrimitive):
        return str(primitive.name or getattr(primitive.primitive, "name", "") or "").strip()
    return str(getattr(primitive, "name", "") or "").strip()


def _combined_source_face_indices(source: CombinedRoomPrimitiveSource, mesh: PrimitiveMesh) -> tuple[int, ...]:
    if not source.face_indices:
        return tuple(range(len(mesh.faces)))
    selected = tuple(sorted(dict.fromkeys(int(index) for index in source.face_indices)))
    invalid = tuple(index for index in selected if index < 0 or index >= len(mesh.faces))
    if invalid:
        name = source.source_name or mesh.name or "(unnamed source)"
        raise IndexError(
            f"Combined source {name} selects face {invalid[0]}, outside 0..{len(mesh.faces) - 1}."
        )
    return selected


def _mesh_materials(mesh: PrimitiveMesh) -> tuple[tuple[dict[str, Any], ...], tuple[int, ...]]:
    """Return a local material table and aligned per-face material IDs."""

    metadata = dict(mesh.metadata or {})
    raw_table = tuple(metadata.get("material_table") or ())
    table = tuple(dict(item) for item in raw_table if isinstance(item, dict))
    if not table:
        table = (
            {
                "texture": str(mesh.texture or ""),
                "diffuse": tuple(float(value) for value in mesh.diffuse),
                "ambient": tuple(float(value) for value in mesh.ambient),
                "metadata": {},
            },
        )
    raw_ids = tuple(int(value) for value in tuple(metadata.get("face_material_ids") or ()))
    if len(raw_ids) != len(mesh.faces) or any(value < 0 or value >= len(table) for value in raw_ids):
        raw_ids = tuple(0 for _ in mesh.faces)
    return table, raw_ids


def _material_vec3(value: Any, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return fallback
    return (float(value[0]), float(value[1]), float(value[2]))


def compile_combined_room_primitive_indexed(
    primitive: CombinedRoomPrimitive,
) -> CombinedRoomPrimitiveCompilation:
    """Compile a procedural combine recipe through the shared topology engine."""

    name = str(primitive.name or "").strip()
    if not name:
        raise ValueError("CombinedRoomPrimitive requires a stable name.")
    if not primitive.sources:
        raise ValueError(f"CombinedRoomPrimitive {name} requires at least one source recipe.")

    operands: list[IndexedMeshOperand] = []
    source_face_indices: list[tuple[int, ...]] = []
    material_table: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    for source_index, source in enumerate(primitive.sources):
        policy = str(source.walkmesh_policy or "inherit").strip().lower()
        if policy not in {"inherit", "exclude"}:
            raise ValueError(
                f"Combined source {source.source_name or source_index} has unsupported WOK policy {source.walkmesh_policy!r}."
            )
        source_mesh = _primitive_to_mesh(source.primitive)
        selected_faces = _combined_source_face_indices(source, source_mesh)
        if not selected_faces:
            raise ValueError(f"Combined source {source.source_name or source_mesh.name} has no polygon faces.")
        local_materials, local_face_material_ids = _mesh_materials(source_mesh)
        local_to_global: dict[int, int] = {}
        for local_id in sorted({local_face_material_ids[index] for index in selected_faces}):
            global_id = len(material_table)
            local_to_global[local_id] = global_id
            material_table.append(
                {
                    **dict(local_materials[local_id]),
                    "material_id": global_id,
                    "source_material_id": local_id,
                    "source_index": source_index,
                    "source_name": str(source.source_name or source_mesh.name or f"source_{source_index:02d}"),
                }
            )

        vertex_channels: dict[str, tuple[Any, ...]] = {}
        if len(source_mesh.normals) == len(source_mesh.vertices):
            vertex_channels["normals"] = tuple(source_mesh.normals)
        if len(source_mesh.uvs) == len(source_mesh.vertices):
            vertex_channels["uvs"] = tuple(source_mesh.uvs)
        compacted = compact_indexed_mesh(
            source_mesh.vertices,
            source_mesh.faces,
            vertex_channels=vertex_channels,
            kept_face_indices=selected_faces,
        )
        indexed = IndexedPolygonMesh.build(
            compacted.vertices,
            compacted.faces,
            vertex_channels={
                channel_name: AttributeChannel.build(
                    values,
                    semantic="normal" if channel_name == "normals" else "attribute",
                )
                for channel_name, values in compacted.vertex_channels.items()
            },
            face_channels={
                "material_ids": AttributeChannel.build(
                    tuple(local_to_global[local_face_material_ids[index]] for index in selected_faces),
                    default=0,
                )
            },
            metadata={
                "source_name": str(source.source_name or source_mesh.name or f"source_{source_index:02d}"),
                "source_face_indices": selected_faces,
                "walkmesh_policy": policy,
            },
        )
        operands.append(
            IndexedMeshOperand.build(
                indexed,
                source_id=str(source.source_name or source_mesh.name or f"source_{source_index:02d}"),
            )
        )
        source_face_indices.append(tuple(compacted.remap.new_face_to_old))
        source_manifest.append(
            {
                "source_index": source_index,
                "source_name": str(source.source_name or source_mesh.name or f"source_{source_index:02d}"),
                "selected_face_count": len(selected_faces),
                "source_face_count": len(source_mesh.faces),
                "walkmesh_policy": policy,
            }
        )

    result = combine_indexed_meshes(tuple(operands))
    for face in result.mesh.faces:
        if len(face) != 3:
            raise ValueError(f"KOTOR authored room output requires triangles; combined face has {len(face)} corners.")
    normals_channel = result.mesh.vertex_channels.get("normals")
    uvs_channel = result.mesh.vertex_channels.get("uvs")
    material_channel = result.mesh.face_channels.get("material_ids")
    face_material_ids = tuple(int(value) for value in (material_channel.values if material_channel else ()))
    if len(face_material_ids) != len(result.mesh.faces):
        face_material_ids = tuple(0 for _ in result.mesh.faces)
    primary_material = material_table[0] if material_table else {}
    compiled_mesh = PrimitiveMesh(
        name=name,
        vertices=tuple(result.mesh.vertices),
        faces=tuple(tuple(int(index) for index in face) for face in result.mesh.faces),  # type: ignore[arg-type]
        normals=tuple(normals_channel.values) if normals_channel is not None else (),
        uvs=tuple(uvs_channel.values) if uvs_channel is not None else (),
        texture=str(primary_material.get("texture") or ""),
        diffuse=_material_vec3(primary_material.get("diffuse"), (0.8, 0.8, 0.8)),
        ambient=_material_vec3(primary_material.get("ambient"), (0.35, 0.35, 0.35)),
        metadata={
            **dict(primitive.metadata),
            "primitive": "combined_polygon_mesh",
            "source": "src.core.modules.authored_room_composition",
            "procedural_recipe": True,
            "source_count": len(primitive.sources),
            "sources": source_manifest,
            "material_table": material_table,
            "face_material_ids": list(face_material_ids),
            "material_count": len(material_table),
            "topology_policy": "true_polygon_combine_preserve_source_seams",
        },
    )
    return CombinedRoomPrimitiveCompilation(
        mesh=compiled_mesh,
        indexed_result=result,
        source_face_indices=tuple(source_face_indices),
    )


def compile_combined_room_primitive(primitive: CombinedRoomPrimitive) -> PrimitiveMesh:
    """Return the compiled polygon mesh for a human-readable combine recipe."""

    return compile_combined_room_primitive_indexed(primitive).mesh


def _primitive_to_mesh(primitive: RoomPrimitive) -> PrimitiveMesh:
    if isinstance(primitive, PlacedRoomPrimitive):
        mesh = _primitive_to_mesh(primitive.primitive)
        return transform_primitive_mesh(mesh, primitive.transform, name=_primitive_name(primitive))
    if isinstance(primitive, CombinedRoomPrimitive):
        return compile_combined_room_primitive(primitive)
    if isinstance(primitive, FloorPrimitive):
        return build_floor_mesh(primitive)
    if isinstance(primitive, WallPrimitive):
        return build_wall_mesh(primitive)
    if isinstance(primitive, CubePrimitive):
        return build_cube_mesh(primitive)
    if isinstance(primitive, RampPrimitive):
        return build_ramp_mesh(primitive)
    if isinstance(primitive, StairsPrimitive):
        return build_stairs_mesh(primitive)
    if isinstance(primitive, CylinderPrimitive):
        return build_cylinder_mesh(primitive)
    if isinstance(primitive, DoorFramePrimitive):
        return build_door_frame_mesh(primitive)
    if isinstance(primitive, ArchPrimitive):
        return build_arch_mesh(primitive)
    raise TypeError(f"Unsupported authored room primitive: {type(primitive)!r}")


def primitive_to_mesh(primitive: RoomPrimitive) -> PrimitiveMesh:
    """Return the compiled mesh for one authored primitive instance.

    Map Studio tools such as the Universal Manipulator need exact selected
    bounds without owning primitive-specific mesh math in the UI layer.
    """

    return _primitive_to_mesh(primitive)


def _primitive_render_meshes(primitive: RoomPrimitive) -> tuple[PrimitiveMesh, ...]:
    """Materialize KOTOR-safe mesh nodes for one logical authored object.

    A Maya-style Combined Mesh may retain several material assignments, while
    Odyssey room nodes have one reliable texture recipe per mesh node.  Split
    the compiled object into material submeshes for MDL export/preview but keep
    the same ``logical_primitive_name`` so selection and Separate Shells still
    treat them as one polygon object.
    """

    mesh = _primitive_to_mesh(primitive)
    base = _base_primitive(primitive)
    logical_name = _primitive_name(primitive) or mesh.name
    if not isinstance(base, CombinedRoomPrimitive):
        return (mesh,)
    metadata = dict(mesh.metadata or {})
    material_table = tuple(
        dict(row) for row in tuple(metadata.get("material_table") or ()) if isinstance(row, dict)
    )
    face_material_ids = tuple(int(value) for value in tuple(metadata.get("face_material_ids") or ()))
    if len(face_material_ids) != len(mesh.faces):
        face_material_ids = tuple(0 for _ in mesh.faces)
    material_ids = tuple(sorted(set(face_material_ids)))
    if len(material_ids) <= 1:
        return (
            replace(
                mesh,
                metadata={**metadata, "logical_primitive_name": logical_name},
            ),
        )
    vertex_channels: dict[str, tuple[Any, ...]] = {}
    if len(mesh.normals) == len(mesh.vertices):
        vertex_channels["normals"] = tuple(mesh.normals)
    if len(mesh.uvs) == len(mesh.vertices):
        vertex_channels["uvs"] = tuple(mesh.uvs)
    result: list[PrimitiveMesh] = []
    for material_id in material_ids:
        material_suffix = f"_mat{material_id:02d}"
        material_node_name = f"{logical_name[: max(1, 32 - len(material_suffix))]}{material_suffix}"
        kept_faces = tuple(index for index, value in enumerate(face_material_ids) if value == material_id)
        compacted = compact_indexed_mesh(
            mesh.vertices,
            mesh.faces,
            vertex_channels=vertex_channels,
            kept_face_indices=kept_faces,
        )
        material = material_table[material_id] if 0 <= material_id < len(material_table) else {}
        result.append(
            PrimitiveMesh(
                name=material_node_name,
                vertices=tuple(compacted.vertices),
                faces=tuple(tuple(int(value) for value in face) for face in compacted.faces),
                normals=tuple(compacted.vertex_channels.get("normals", ())),
                uvs=tuple(compacted.vertex_channels.get("uvs", ())),
                texture=str(material.get("texture") or mesh.texture or ""),
                diffuse=_material_vec3(material.get("diffuse"), mesh.diffuse),
                ambient=_material_vec3(material.get("ambient"), mesh.ambient),
                metadata={
                    **metadata,
                    "logical_primitive_name": logical_name,
                    "material_table": [material] if material else [],
                    "face_material_ids": [0] * len(compacted.faces),
                    "material_count": 1,
                    "source_material_id": material_id,
                    "source_face_indices": list(compacted.remap.new_face_to_old),
                    "kotor_material_submesh": True,
                },
            )
        )
    return tuple(result)


def _append_wok(base: WOKData, extra: WOKData) -> WOKData:
    """Append one primitive WOK to another while preserving local adjacency."""

    vertex_offset = len(base.verts)
    face_offset = len(base.faces)
    base.verts.extend(tuple(vertex) for vertex in extra.verts)
    for face in extra.faces:
        base.faces.append(
            WOKFace(
                face.v1 + vertex_offset,
                face.v2 + vertex_offset,
                face.v3 + vertex_offset,
                face.surface,
                face.adj1 + face_offset if face.adj1 >= 0 else -1,
                face.adj2 + face_offset if face.adj2 >= 0 else -1,
                face.adj3 + face_offset if face.adj3 >= 0 else -1,
                face.trans1,
                face.trans2,
                face.trans3,
            )
        )
    return base


def primitive_to_wok(primitive: RoomPrimitive) -> WOKData | None:
    """Compile one primitive recipe's inherited walkable WOK contribution.

    Polygon face selections never guess at a render-face-to-WOK-face mapping.
    A combined source therefore inherits its complete authored WOK proxy once,
    unless its explicit ``walkmesh_policy`` is ``exclude``.
    """

    if isinstance(primitive, PlacedRoomPrimitive):
        primitive_wok = primitive_to_wok(primitive.primitive)
        return transform_wok_data(primitive_wok, primitive.transform) if primitive_wok is not None else None
    if isinstance(primitive, CombinedRoomPrimitive):
        combined = WOKData(name=primitive.name)
        contributed = False
        for source in primitive.sources:
            policy = str(source.walkmesh_policy or "inherit").strip().lower()
            if policy not in {"inherit", "exclude"}:
                raise ValueError(
                    f"Combined source {source.source_name or '(unnamed)'} has unsupported WOK policy {source.walkmesh_policy!r}."
                )
            if policy == "exclude":
                continue
            source_wok = primitive_to_wok(source.primitive)
            if source_wok is not None:
                _append_wok(combined, source_wok)
                contributed = True
        return combined if contributed else None
    if isinstance(primitive, FloorPrimitive):
        return build_floor_wok(primitive)
    if isinstance(primitive, RampPrimitive):
        return build_ramp_wok(primitive)
    if isinstance(primitive, StairsPrimitive):
        return build_stairs_wok(primitive)
    return None


def _build_floor_wok_for_composition(composition: AuthoredRoomComposition) -> WOKData:
    """Build the base floor WOK, optionally reserving a doorway transition strip."""

    floor, transform = _floor_base_and_transform(composition.floor)
    if not bool(dict(composition.metadata or {}).get("include_door_transition_surface", False)):
        wok = build_floor_wok(floor)
        return transform_wok_data(wok, transform) if transform is not None else wok

    surface_id = resolve_walkmesh_surface_id(floor.surface_id)
    half_w = float(floor.width) * 0.5
    half_d = float(floor.depth) * 0.5
    z = float(floor.z)
    strip_depth = max(0.25, min(2.0, float(floor.depth) * 0.25))
    strip_y = half_d - strip_depth
    wok = WOKData(
        verts=[
            (-half_w, -half_d, z),
            (half_w, -half_d, z),
            (half_w, strip_y, z),
            (-half_w, strip_y, z),
            (half_w, half_d, z),
            (-half_w, half_d, z),
        ],
        faces=[
            WOKFace(0, 1, 2, surface=surface_id, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=surface_id, adj1=0, adj2=2, adj3=-1),
            WOKFace(3, 2, 4, surface=DOOR_TRANSITION_SURFACE_ID, adj1=1, adj2=-1, adj3=3),
            WOKFace(3, 4, 5, surface=DOOR_TRANSITION_SURFACE_ID, adj1=2, adj2=-1, adj3=-1),
        ],
    )
    return transform_wok_data(wok, transform) if transform is not None else wok


def build_composition_wok(composition: AuthoredRoomComposition) -> WOKData:
    """Build the room WOK from the floor plus walkable authored primitives."""

    wok = _build_floor_wok_for_composition(composition)
    for primitive in composition.primitives:
        primitive_wok = primitive_to_wok(primitive)
        if primitive_wok is not None:
            _append_wok(wok, primitive_wok)
    return wok


def validate_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomCompositionValidation:
    """Validate a primitive room composition before it is compiled."""

    warnings: list[str] = []
    blocking: list[str] = []
    floor, floor_transform = _floor_base_and_transform(composition.floor)
    if not _normalise_name(composition.room_resref):
        blocking.append("Authored room composition requires a room resref.")
    if float(floor.width) <= 0.0 or float(floor.depth) <= 0.0:
        blocking.append("Authored room floor must have positive width and depth.")
    try:
        require_walkable_walkmesh_surface(floor.surface_id, context=f"{composition.room_resref} floor")
    except ValueError as exc:
        blocking.append(str(exc))
    if floor_transform is not None and any(float(value) <= 0.0 for value in floor_transform.scale):
        blocking.append(f"Placed floor {_primitive_name(composition.floor) or '(unnamed)'} must have positive transform scale.")
    names: set[str] = set()
    for primitive in (composition.floor, *composition.primitives):
        name = _primitive_name(primitive)
        if not name:
            blocking.append("Every authored room primitive requires a stable name.")
            continue
        if name in names:
            blocking.append(f"Duplicate authored room primitive name: {name}")
        names.add(name)
    for primitive in composition.primitives:
        if isinstance(primitive, PlacedRoomPrimitive) and any(float(value) <= 0.0 for value in primitive.transform.scale):
            blocking.append(f"Placed primitive {_primitive_name(primitive) or '(unnamed)'} must have positive transform scale.")
        base = _base_primitive(primitive)
        base_name = _primitive_name(primitive) or str(getattr(base, "name", "") or "(unnamed)")
        if isinstance(base, FloorPrimitive):
            if float(base.width) <= 0.0 or float(base.depth) <= 0.0:
                blocking.append(f"Plane primitive {base_name} must have positive width and depth.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} plane")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, RampPrimitive):
            if float(base.width) <= 0.0 or float(base.length) <= 0.0 or float(base.height) <= 0.0:
                blocking.append(f"Ramp primitive {base_name} must have positive width, length, and height.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} ramp")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, StairsPrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.height) <= 0.0
                or int(base.steps) <= 0
            ):
                blocking.append(f"Stairs primitive {base_name} must have positive width, depth, height, and step count.")
            try:
                require_walkable_walkmesh_surface(base.surface_id, context=f"{base_name} stairs")
            except ValueError as exc:
                blocking.append(str(exc))
        if isinstance(base, ArchPrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.height) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.frame_thickness) <= 0.0
            ):
                blocking.append(f"Arch primitive {base_name} must have positive width, height, depth, and frame thickness.")
        if isinstance(base, DoorFramePrimitive):
            if (
                float(base.width) <= 0.0
                or float(base.height) <= 0.0
                or float(base.depth) <= 0.0
                or float(base.jamb_width) <= 0.0
                or float(base.lintel_height) <= 0.0
            ):
                blocking.append(f"Door frame primitive {base_name} must have positive width, height, depth, jamb width, and lintel height.")
            if float(base.width) <= float(base.jamb_width) * 2.0:
                blocking.append(f"Door frame primitive {base_name} must leave a positive doorway opening width.")
            if float(base.height) <= float(base.lintel_height):
                blocking.append(f"Door frame primitive {base_name} must leave a positive doorway opening height.")
    if not composition.primitives and not composition.helper_meshes:
        warnings.append("Authored room composition has only a floor; add walls or helpers before game-facing export.")
    return AuthoredRoomCompositionValidation(
        ok=not blocking,
        warnings=tuple(warnings),
        blocking_issues=tuple(blocking),
    )


def compile_authored_room_composition(composition: AuthoredRoomComposition) -> AuthoredRoomGeometry:
    """Compile editable room primitives into room geometry and a derived WOK."""

    validation = validate_authored_room_composition(composition)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    floor, _floor_transform = _floor_base_and_transform(composition.floor)
    floor_mesh = _primitive_to_mesh(composition.floor)
    floor_surface_id = resolve_walkmesh_surface_id(floor.surface_id)
    primitive_meshes = tuple(
        mesh
        for primitive in composition.primitives
        for mesh in _primitive_render_meshes(primitive)
    )
    room_resref = _normalise_name(composition.room_resref)
    return AuthoredRoomGeometry(
        room_resref=room_resref,
        room_mesh=floor_mesh,
        helper_meshes=primitive_meshes + tuple(composition.helper_meshes),
        wok=build_composition_wok(composition),
        metadata={
            **dict(composition.metadata),
            "primitive": "authored_room_composition",
            "source": "src.core.modules.authored_room_composition",
            "floor": floor_mesh.name,
            "floor_surface_id": floor_surface_id,
            "floor_surface_name": walkmesh_surface_name(floor_surface_id),
            "transition_surface_id": DOOR_TRANSITION_SURFACE_ID
            if bool(dict(composition.metadata or {}).get("include_door_transition_surface", False))
            else 0,
            "primitive_count": len(composition.primitives),
            "helper_mesh_count": len(composition.helper_meshes),
            "compiled_mesh_count": 1 + len(primitive_meshes) + len(composition.helper_meshes),
            "walkmesh_primitive_count": sum(
                1
                for primitive in composition.primitives
                if primitive_to_wok(primitive) is not None
            ),
            "transformed_primitive_count": sum(
                1 for primitive in (composition.floor,) + tuple(composition.primitives) if isinstance(primitive, PlacedRoomPrimitive)
            ),
            "warnings": list(validation.warnings),
        },
    )


def create_rectangular_room_composition(primitive: RectangularRoomPrimitive) -> AuthoredRoomComposition:
    """Convert the legacy rectangular smoke-room primitive to editable parts."""

    room_resref = _normalise_name(primitive.room_resref)
    material = PrimitiveMaterial(texture=str(primitive.texture or "default"))
    floor_surface_id = resolve_walkmesh_surface_id(primitive.floor_surface_id)
    half_w = float(primitive.width) * 0.5
    half_d = float(primitive.depth) * 0.5
    wall_height = float(primitive.wall_height)
    thickness = 0.15
    floor = FloorPrimitive(
        name=f"{room_resref}_mesh",
        width=float(primitive.width),
        depth=float(primitive.depth),
        z=0.0,
        surface_id=floor_surface_id,
        material=material,
    )
    walls: tuple[RoomPrimitive, ...] = (
        WallPrimitive(
            name=f"{room_resref}_wall_n",
            width=float(primitive.width),
            height=wall_height,
            thickness=thickness,
            axis="x",
            center=(0.0, half_d, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_s",
            width=float(primitive.width),
            height=wall_height,
            thickness=thickness,
            axis="x",
            center=(0.0, -half_d, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_e",
            width=float(primitive.depth),
            height=wall_height,
            thickness=thickness,
            axis="y",
            center=(half_w, 0.0, wall_height * 0.5),
            material=material,
        ),
        WallPrimitive(
            name=f"{room_resref}_wall_w",
            width=float(primitive.depth),
            height=wall_height,
            thickness=thickness,
            axis="y",
            center=(-half_w, 0.0, wall_height * 0.5),
            material=material,
        ),
    )
    helper_meshes = ()
    if primitive.include_doorway_marker:
        from .authored_room_geometry import build_doorway_marker_mesh

        helper_meshes = (replace(build_doorway_marker_mesh(primitive), metadata={"primitive": "doorway_marker", "source": "map_studio:t2601"}),)
    return AuthoredRoomComposition(
        room_resref=room_resref,
        floor=floor,
        primitives=walls,
        helper_meshes=helper_meshes,
        metadata={
            "composition_source": "map_studio:rectangular_room_composition",
            "width": float(primitive.width),
            "depth": float(primitive.depth),
            "wall_height": wall_height,
            "floor_surface_id": floor_surface_id,
            "floor_surface_name": walkmesh_surface_name(floor_surface_id),
            "include_door_transition_surface": bool(primitive.include_doorway_marker),
        },
    )


__all__ = [
    "AuthoredRoomComposition",
    "AuthoredRoomCompositionValidation",
    "CombinedRoomPrimitive",
    "CombinedRoomPrimitiveCompilation",
    "CombinedRoomPrimitiveSource",
    "PlacedRoomPrimitive",
    "PrimitiveTransform",
    "RoomPrimitive",
    "build_composition_wok",
    "compile_authored_room_composition",
    "compile_combined_room_primitive",
    "compile_combined_room_primitive_indexed",
    "create_rectangular_room_composition",
    "primitive_to_mesh",
    "primitive_to_wok",
    "transform_primitive_mesh",
    "transform_wok_data",
    "validate_authored_room_composition",
]
