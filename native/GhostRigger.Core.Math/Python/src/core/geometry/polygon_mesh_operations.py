"""Format-agnostic polygon Combine Meshes and Separate Shells operations.

These operations deliberately model Maya-style polygon object operations, not
scene grouping or KOTOR room extraction.  Combine bakes each operand's object
transform into one indexed polygon mesh without welding away UV/hard-normal
seams.  Separate uses seam-aware geometric edge connectivity to produce one
mesh per disconnected polygon shell.

The module owns no Qt, KMAP, MDL, material-resource, or scene policy.  Callers
adapt their mesh representation to :class:`IndexedPolygonMesh`, then retain the
returned remaps/provenance while applying their own undo and export policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Mapping, Sequence

from .mesh_topology import IndexRemap, MeshTopology, TopologyComponent, compact_indexed_mesh


Vector3 = tuple[float, float, float]
Face = tuple[int, ...]
Matrix4 = tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]

IDENTITY_MATRIX4: Matrix4 = (
    (1.0, 0.0, 0.0, 0.0),
    (0.0, 1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)

_CHANNEL_SEMANTICS = {"auto", "attribute", "point", "vector", "normal", "tangent"}


@dataclass(frozen=True, slots=True)
class AttributeChannel:
    """One aligned mesh attribute channel.

    ``semantic`` controls spatial transform baking in any component domain.
    Ordinary UV, color, weight, material, smoothing, and provenance data use
    ``attribute``. ``auto`` infers normals/tangents/positions from the name.
    """

    values: tuple[Any, ...]
    semantic: str = "auto"
    default: Any = None

    @classmethod
    def build(
        cls,
        values: Iterable[Any],
        *,
        semantic: str = "auto",
        default: Any = None,
    ) -> "AttributeChannel":
        return cls(tuple(values), str(semantic).strip().lower(), default)


@dataclass(frozen=True, slots=True)
class IndexedPolygonMesh:
    """Portable indexed n-gon mesh plus aligned component channels."""

    vertices: tuple[Vector3, ...]
    faces: tuple[Face, ...]
    vertex_channels: dict[str, AttributeChannel] = field(default_factory=dict)
    face_channels: dict[str, AttributeChannel] = field(default_factory=dict)
    corner_channels: dict[str, AttributeChannel] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        vertices: Iterable[Sequence[float]],
        faces: Iterable[Iterable[int]],
        *,
        vertex_channels: Mapping[str, AttributeChannel | Iterable[Any]] | None = None,
        face_channels: Mapping[str, AttributeChannel | Iterable[Any]] | None = None,
        corner_channels: Mapping[str, AttributeChannel | Iterable[Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "IndexedPolygonMesh":
        mesh = cls(
            vertices=tuple(_coerce_vector3(value, label="vertex") for value in vertices),
            faces=tuple(tuple(int(index) for index in face) for face in faces),
            vertex_channels=_coerce_channels(vertex_channels),
            face_channels=_coerce_channels(face_channels),
            corner_channels=_coerce_channels(corner_channels),
            metadata=dict(metadata or {}),
        )
        mesh.validate()
        return mesh

    def validate(self) -> None:
        """Reject malformed component alignment before an edit can lose data."""

        vertex_count = len(self.vertices)
        face_count = len(self.faces)
        for face_index, face in enumerate(self.faces):
            if len(face) < 3:
                raise ValueError(f"Face {face_index} has {len(face)} corners; polygon faces need at least three.")
            invalid = [index for index in face if index < 0 or index >= vertex_count]
            if invalid:
                raise IndexError(
                    f"Face {face_index} contains out-of-range indices {invalid}; vertex count is {vertex_count}."
                )
        _validate_channels(self.vertex_channels, vertex_count, "vertex")
        _validate_channels(self.face_channels, face_count, "face")
        _validate_channels(self.corner_channels, face_count, "corner-face")
        for name, channel in self.corner_channels.items():
            for face_index, row in enumerate(channel.values):
                try:
                    corner_count = len(row)
                except TypeError as exc:
                    raise TypeError(
                        f"Corner channel {name!r} face {face_index} is not a per-corner sequence."
                    ) from exc
                if corner_count != len(self.faces[face_index]):
                    raise ValueError(
                        f"Corner channel {name!r} face {face_index} has {corner_count} values; "
                        f"expected {len(self.faces[face_index])}."
                    )


@dataclass(frozen=True, slots=True)
class IndexedMeshOperand:
    """One source mesh and its affine object-to-result transform."""

    mesh: IndexedPolygonMesh
    transform: Matrix4 = IDENTITY_MATRIX4
    source_id: str = ""

    @classmethod
    def build(
        cls,
        mesh: IndexedPolygonMesh,
        *,
        transform: Sequence[Sequence[float]] = IDENTITY_MATRIX4,
        source_id: str = "",
    ) -> "IndexedMeshOperand":
        mesh.validate()
        return cls(mesh=mesh, transform=_coerce_affine_matrix(transform), source_id=str(source_id))


@dataclass(frozen=True, slots=True)
class SourceElement:
    """Stable provenance for one output vertex or face."""

    operand_index: int
    source_id: str
    source_index: int


@dataclass(frozen=True, slots=True)
class CombinedMeshRemap:
    """Bidirectional source/output identity maps for a Combine operation."""

    source_vertex_to_output: tuple[tuple[int, ...], ...]
    output_vertex_to_source: tuple[SourceElement, ...]
    source_face_to_output: tuple[tuple[int, ...], ...]
    output_face_to_source: tuple[SourceElement, ...]
    output_face_corner_to_source: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class CombinedMeshResult:
    mesh: IndexedPolygonMesh
    remap: CombinedMeshRemap


@dataclass(frozen=True, slots=True)
class ShellElementRef:
    shell_index: int
    element_index: int


@dataclass(frozen=True, slots=True)
class SeparatedShell:
    """One disconnected polygon shell and its source-to-shell compaction map."""

    mesh: IndexedPolygonMesh
    remap: IndexRemap
    component: TopologyComponent | None
    loose_vertex: bool = False


@dataclass(frozen=True, slots=True)
class SeparateShellsResult:
    shells: tuple[SeparatedShell, ...]
    source_vertex_to_shells: tuple[tuple[ShellElementRef, ...], ...]
    source_face_to_shell: tuple[ShellElementRef | None, ...]
    unassigned_vertices: tuple[int, ...] = ()


def combine_indexed_meshes(
    operands: Sequence[IndexedMeshOperand | IndexedPolygonMesh],
) -> CombinedMeshResult:
    """Bake operands into one genuine indexed polygon mesh.

    The operation concatenates rather than welds source vertices, preserving
    disconnected shells and seam duplication.  Affine transforms use the
    conventional column-vector equation ``result = matrix @ source``.  A
    negative-determinant transform reverses polygon/corner winding so baked
    normals remain consistent with the visible source object.
    """

    if not operands:
        raise ValueError("Combine Meshes needs at least one polygon mesh operand.")
    normalized: list[IndexedMeshOperand] = []
    for operand_index, value in enumerate(operands):
        if isinstance(value, IndexedMeshOperand):
            value.mesh.validate()
            normalized.append(
                IndexedMeshOperand(
                    mesh=value.mesh,
                    transform=_coerce_affine_matrix(value.transform),
                    source_id=value.source_id or f"mesh_{operand_index}",
                )
            )
        elif isinstance(value, IndexedPolygonMesh):
            value.validate()
            normalized.append(
                IndexedMeshOperand(
                    mesh=value,
                    transform=IDENTITY_MATRIX4,
                    source_id=str(value.metadata.get("source_id") or f"mesh_{operand_index}"),
                )
            )
        else:
            raise TypeError(f"Operand {operand_index} is not an IndexedPolygonMesh or IndexedMeshOperand.")

    vertex_schemas = _merged_channel_schemas(normalized, "vertex_channels")
    face_schemas = _merged_channel_schemas(normalized, "face_channels")
    corner_schemas = _merged_channel_schemas(normalized, "corner_channels")
    combined_vertex_channels = {name: [] for name in vertex_schemas}
    combined_face_channels = {name: [] for name in face_schemas}
    combined_corner_channels = {name: [] for name in corner_schemas}
    vertices: list[Vector3] = []
    faces: list[Face] = []
    source_vertex_to_output: list[tuple[int, ...]] = []
    source_face_to_output: list[tuple[int, ...]] = []
    output_vertex_to_source: list[SourceElement] = []
    output_face_to_source: list[SourceElement] = []
    output_face_corner_to_source: list[tuple[int, ...]] = []

    for operand_index, operand in enumerate(normalized):
        mesh = operand.mesh
        matrix = operand.transform
        determinant = _linear_determinant(matrix)
        mirrored = determinant < 0.0
        vertex_offset = len(vertices)
        vertex_outputs: list[int] = []
        for source_index, vertex in enumerate(mesh.vertices):
            output_index = len(vertices)
            vertex_outputs.append(output_index)
            vertices.append(_transform_point(matrix, vertex))
            output_vertex_to_source.append(SourceElement(operand_index, operand.source_id, source_index))
        source_vertex_to_output.append(tuple(vertex_outputs))

        face_outputs: list[int] = []
        for source_index, face in enumerate(mesh.faces):
            output_index = len(faces)
            face_outputs.append(output_index)
            corner_order = _corner_order(len(face), mirrored=mirrored)
            faces.append(tuple(vertex_offset + face[index] for index in corner_order))
            output_face_to_source.append(SourceElement(operand_index, operand.source_id, source_index))
            output_face_corner_to_source.append(corner_order)
        source_face_to_output.append(tuple(face_outputs))

        for name, schema in vertex_schemas.items():
            source = mesh.vertex_channels.get(name)
            if source is None:
                combined_vertex_channels[name].extend(
                    _transform_channel_value(
                        schema.default,
                        semantic=schema.semantic,
                        matrix=matrix,
                        determinant=determinant,
                    )
                    for _ in mesh.vertices
                )
                continue
            semantic = _resolved_semantic(name, source.semantic)
            combined_vertex_channels[name].extend(
                _transform_channel_value(
                    value,
                    semantic=semantic,
                    matrix=matrix,
                    determinant=determinant,
                )
                for value in source.values
            )
        for name, schema in face_schemas.items():
            source = mesh.face_channels.get(name)
            if source is None:
                combined_face_channels[name].extend(
                    _transform_channel_value(
                        schema.default,
                        semantic=schema.semantic,
                        matrix=matrix,
                        determinant=determinant,
                    )
                    for _ in mesh.faces
                )
            else:
                semantic = _resolved_semantic(name, source.semantic)
                combined_face_channels[name].extend(
                    _transform_channel_value(
                        value,
                        semantic=semantic,
                        matrix=matrix,
                        determinant=determinant,
                    )
                    for value in source.values
                )
        for name, schema in corner_schemas.items():
            source = mesh.corner_channels.get(name)
            if source is None:
                default = _transform_channel_value(
                    schema.default,
                    semantic=schema.semantic,
                    matrix=matrix,
                    determinant=determinant,
                )
                combined_corner_channels[name].extend(
                    tuple(default for _ in face) for face in mesh.faces
                )
                continue
            semantic = _resolved_semantic(name, source.semantic)
            for face_index, row in enumerate(source.values):
                order = _corner_order(len(mesh.faces[face_index]), mirrored=mirrored)
                combined_corner_channels[name].append(
                    tuple(
                        _transform_channel_value(
                            row[index],
                            semantic=semantic,
                            matrix=matrix,
                            determinant=determinant,
                        )
                        for index in order
                    )
                )

    metadata = {
        "operation": "combine_meshes",
        "source_ids": tuple(operand.source_id for operand in normalized),
        "source_metadata": tuple(dict(operand.mesh.metadata) for operand in normalized),
        "source_transforms": tuple(operand.transform for operand in normalized),
    }
    result_mesh = IndexedPolygonMesh.build(
        vertices,
        faces,
        vertex_channels={
            name: AttributeChannel(tuple(combined_vertex_channels[name]), schema.semantic, schema.default)
            for name, schema in vertex_schemas.items()
        },
        face_channels={
            name: AttributeChannel(tuple(combined_face_channels[name]), schema.semantic, schema.default)
            for name, schema in face_schemas.items()
        },
        corner_channels={
            name: AttributeChannel(tuple(combined_corner_channels[name]), schema.semantic, schema.default)
            for name, schema in corner_schemas.items()
        },
        metadata=metadata,
    )
    return CombinedMeshResult(
        mesh=result_mesh,
        remap=CombinedMeshRemap(
            source_vertex_to_output=tuple(source_vertex_to_output),
            output_vertex_to_source=tuple(output_vertex_to_source),
            source_face_to_output=tuple(source_face_to_output),
            output_face_to_source=tuple(output_face_to_source),
            output_face_corner_to_source=tuple(output_face_corner_to_source),
        ),
    )


def separate_indexed_mesh_shells(
    mesh: IndexedPolygonMesh,
    *,
    weld_tolerance: float = 1.0e-6,
    include_loose_vertices: bool = True,
) -> SeparateShellsResult:
    """Split a polygon mesh into seam-aware, edge-connected shells.

    Each shell keeps all vertex, face, and face-corner channels.  Face order and
    vertex compaction are deterministic, and every output carries an
    :class:`IndexRemap`.  Loose vertices become individual vertex-only shells
    by default so Separate never silently loses authored data.
    """

    mesh.validate()
    topology = MeshTopology.build(mesh.vertices, mesh.faces, weld_tolerance=weld_tolerance)
    if topology.invalid_faces:
        raise ValueError(f"Cannot Separate Shells with invalid faces {list(topology.invalid_faces)}.")

    shells: list[SeparatedShell] = []
    vertex_refs: list[list[ShellElementRef]] = [[] for _ in mesh.vertices]
    face_refs: list[ShellElementRef | None] = [None for _ in mesh.faces]
    used_vertices: set[int] = set()

    for shell_faces in _shell_face_components(topology):
        component_rows = topology.components(shell_faces)
        if len(component_rows) != 1:
            raise RuntimeError(f"Internal shell partition was not connected: {shell_faces!r}.")
        component = component_rows[0]
        shell_index = len(shells)
        kept_faces = component.faces
        compacted = compact_indexed_mesh(
            mesh.vertices,
            mesh.faces,
            vertex_channels={name: channel.values for name, channel in mesh.vertex_channels.items()},
            kept_face_indices=kept_faces,
        )
        shell_mesh = IndexedPolygonMesh.build(
            compacted.vertices,
            compacted.faces,
            vertex_channels={
                name: AttributeChannel(
                    compacted.vertex_channels[name], channel.semantic, channel.default
                )
                for name, channel in mesh.vertex_channels.items()
            },
            face_channels={
                name: AttributeChannel(
                    tuple(channel.values[index] for index in kept_faces),
                    channel.semantic,
                    channel.default,
                )
                for name, channel in mesh.face_channels.items()
            },
            corner_channels={
                name: AttributeChannel(
                    tuple(channel.values[index] for index in kept_faces),
                    channel.semantic,
                    channel.default,
                )
                for name, channel in mesh.corner_channels.items()
            },
            metadata=_shell_metadata(mesh.metadata, shell_index, loose_vertex=False),
        )
        shell = SeparatedShell(shell_mesh, compacted.remap, component, False)
        shells.append(shell)
        for new_index, old_index in enumerate(compacted.remap.new_vertex_to_old):
            used_vertices.add(old_index)
            vertex_refs[old_index].append(ShellElementRef(shell_index, new_index))
        for new_index, old_index in enumerate(compacted.remap.new_face_to_old):
            face_refs[old_index] = ShellElementRef(shell_index, new_index)

    loose_vertices = tuple(index for index in range(len(mesh.vertices)) if index not in used_vertices)
    if include_loose_vertices:
        for old_index in loose_vertices:
            shell_index = len(shells)
            old_vertex_to_new = [-1] * len(mesh.vertices)
            old_vertex_to_new[old_index] = 0
            remap = IndexRemap(
                old_vertex_to_new=tuple(old_vertex_to_new),
                new_vertex_to_old=(old_index,),
                old_face_to_new=tuple(-1 for _ in mesh.faces),
                new_face_to_old=(),
            )
            shell_mesh = IndexedPolygonMesh.build(
                (mesh.vertices[old_index],),
                (),
                vertex_channels={
                    name: AttributeChannel(
                        (channel.values[old_index],), channel.semantic, channel.default
                    )
                    for name, channel in mesh.vertex_channels.items()
                },
                face_channels={
                    name: AttributeChannel((), channel.semantic, channel.default)
                    for name, channel in mesh.face_channels.items()
                },
                corner_channels={
                    name: AttributeChannel((), channel.semantic, channel.default)
                    for name, channel in mesh.corner_channels.items()
                },
                metadata=_shell_metadata(mesh.metadata, shell_index, loose_vertex=True),
            )
            shells.append(SeparatedShell(shell_mesh, remap, None, True))
            vertex_refs[old_index].append(ShellElementRef(shell_index, 0))

    return SeparateShellsResult(
        shells=tuple(shells),
        source_vertex_to_shells=tuple(tuple(refs) for refs in vertex_refs),
        source_face_to_shell=tuple(face_refs),
        unassigned_vertices=() if include_loose_vertices else loose_vertices,
    )


def _coerce_channels(
    channels: Mapping[str, AttributeChannel | Iterable[Any]] | None,
) -> dict[str, AttributeChannel]:
    result: dict[str, AttributeChannel] = {}
    for name, value in dict(channels or {}).items():
        channel = value if isinstance(value, AttributeChannel) else AttributeChannel.build(value)
        semantic = str(channel.semantic).strip().lower()
        if semantic not in _CHANNEL_SEMANTICS:
            raise ValueError(
                f"Channel {name!r} has unsupported semantic {channel.semantic!r}; "
                f"expected one of {sorted(_CHANNEL_SEMANTICS)}."
            )
        result[str(name)] = AttributeChannel(tuple(channel.values), semantic, channel.default)
    return result


def _validate_channels(channels: Mapping[str, AttributeChannel], count: int, domain: str) -> None:
    for name, channel in channels.items():
        if channel.semantic not in _CHANNEL_SEMANTICS:
            raise ValueError(f"Channel {name!r} has unsupported semantic {channel.semantic!r}.")
        if len(channel.values) != count:
            raise ValueError(
                f"{domain.title()} channel {name!r} has {len(channel.values)} values; expected {count}."
            )


def _coerce_vector3(value: Sequence[float], *, label: str) -> Vector3:
    if len(value) < 3:
        raise ValueError(f"A {label} needs at least three coordinates, received {value!r}.")
    return (float(value[0]), float(value[1]), float(value[2]))


def _coerce_affine_matrix(value: Sequence[Sequence[float]]) -> Matrix4:
    rows = tuple(tuple(float(component) for component in row) for row in value)
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise ValueError("Object transforms must be 4x4 matrices.")
    if any(abs(rows[3][index] - expected) > 1.0e-9 for index, expected in enumerate((0, 0, 0, 1))):
        raise ValueError("Combine Meshes accepts affine transforms only (last row must be 0,0,0,1).")
    return rows  # type: ignore[return-value]


def _transform_point(matrix: Matrix4, value: Sequence[float]) -> Vector3:
    x, y, z = _coerce_vector3(value, label="point")
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def _transform_linear(matrix: Matrix4, value: Sequence[float]) -> Vector3:
    x, y, z = _coerce_vector3(value, label="vector")
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z,
    )


def _linear_determinant(matrix: Matrix4) -> float:
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _inverse_transpose_linear(matrix: Matrix4) -> tuple[Vector3, Vector3, Vector3]:
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    determinant = _linear_determinant(matrix)
    if abs(determinant) <= 1.0e-15:
        raise ValueError("Cannot bake normal channels through a singular object transform.")
    inverse = 1.0 / determinant
    return (
        ((e * i - f * h) * inverse, (f * g - d * i) * inverse, (d * h - e * g) * inverse),
        ((c * h - b * i) * inverse, (a * i - c * g) * inverse, (b * g - a * h) * inverse),
        ((b * f - c * e) * inverse, (c * d - a * f) * inverse, (a * e - b * d) * inverse),
    )


def _transform_normal(matrix: Matrix4, value: Sequence[float]) -> Vector3:
    x, y, z = _coerce_vector3(value, label="normal")
    normal_matrix = _inverse_transpose_linear(matrix)
    transformed = (
        normal_matrix[0][0] * x + normal_matrix[0][1] * y + normal_matrix[0][2] * z,
        normal_matrix[1][0] * x + normal_matrix[1][1] * y + normal_matrix[1][2] * z,
        normal_matrix[2][0] * x + normal_matrix[2][1] * y + normal_matrix[2][2] * z,
    )
    return _normalized(transformed)


def _normalized(value: Sequence[float]) -> Vector3:
    length = math.sqrt(sum(float(component) * float(component) for component in value[:3]))
    if length <= 1.0e-15:
        return (0.0, 0.0, 0.0)
    return tuple(float(component) / length for component in value[:3])  # type: ignore[return-value]


def _replace_vector_prefix(source: Any, vector: Vector3, *, tangent_sign: float = 1.0) -> Vector3 | tuple[Any, ...]:
    row = tuple(source)
    if len(row) == 3:
        return vector
    tail = list(row[3:])
    if tail and isinstance(tail[0], (int, float)):
        tail[0] = float(tail[0]) * tangent_sign
    return (*vector, *tail)


def _transform_channel_value(
    value: Any,
    *,
    semantic: str,
    matrix: Matrix4,
    determinant: float,
) -> Any:
    if semantic == "attribute":
        return value
    if semantic == "point":
        return _replace_vector_prefix(value, _transform_point(matrix, value))
    if semantic == "vector":
        return _replace_vector_prefix(value, _transform_linear(matrix, value))
    if semantic == "normal":
        return _replace_vector_prefix(value, _transform_normal(matrix, value))
    if semantic == "tangent":
        tangent = _normalized(_transform_linear(matrix, value))
        return _replace_vector_prefix(value, tangent, tangent_sign=-1.0 if determinant < 0.0 else 1.0)
    raise ValueError(f"Unsupported transformed channel semantic {semantic!r}.")


def _resolved_semantic(name: str, semantic: str) -> str:
    if semantic != "auto":
        return semantic
    lowered = str(name).casefold()
    if "normal" in lowered:
        return "normal"
    if "tangent" in lowered:
        return "tangent"
    if lowered in {"position", "positions", "point", "points"}:
        return "point"
    return "attribute"


def _default_for_channel(name: str, channel: AttributeChannel, *, corner_channel: bool = False) -> Any:
    if channel.default is not None:
        return channel.default
    sample = channel.values[0] if channel.values else 0
    if corner_channel and hasattr(sample, "__len__") and len(sample):
        sample = sample[0]
    semantic = _resolved_semantic(name, channel.semantic)
    if semantic in {"point", "vector"}:
        return (0.0, 0.0, 0.0)
    if semantic == "normal":
        return (0.0, 0.0, 1.0)
    if semantic == "tangent":
        return (1.0, 0.0, 0.0, 1.0) if hasattr(sample, "__len__") and len(sample) >= 4 else (1.0, 0.0, 0.0)
    lowered = str(name).casefold()
    if "color" in lowered or "colour" in lowered:
        return (1.0, 1.0, 1.0, 1.0) if hasattr(sample, "__len__") and len(sample) >= 4 else (1.0, 1.0, 1.0)
    return _zero_like(sample)


def _zero_like(value: Any) -> Any:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    if isinstance(value, tuple):
        return tuple(_zero_like(component) for component in value)
    if isinstance(value, list):
        return [_zero_like(component) for component in value]
    if isinstance(value, str):
        return ""
    return None


def _merged_channel_schemas(
    operands: Sequence[IndexedMeshOperand],
    member: str,
) -> dict[str, AttributeChannel]:
    result: dict[str, AttributeChannel] = {}
    for operand in operands:
        channels: Mapping[str, AttributeChannel] = getattr(operand.mesh, member)
        for name, channel in channels.items():
            resolved = _resolved_semantic(name, channel.semantic)
            current = result.get(name)
            if current is None:
                result[name] = AttributeChannel(
                    (),
                    resolved,
                    _default_for_channel(name, channel, corner_channel=member == "corner_channels"),
                )
                continue
            if current.semantic != resolved:
                raise ValueError(
                    f"Channel {name!r} has conflicting semantics {current.semantic!r} and {resolved!r}."
                )
            if channel.default is not None and current.default != channel.default:
                raise ValueError(
                    f"Channel {name!r} has conflicting defaults {current.default!r} and {channel.default!r}."
                )
    return result


def _corner_order(count: int, *, mirrored: bool) -> tuple[int, ...]:
    if not mirrored or count < 3:
        return tuple(range(count))
    return (0, *range(count - 1, 0, -1))


def _shell_face_components(topology: MeshTopology) -> tuple[tuple[int, ...], ...]:
    """Return raw-topology shells plus only unambiguous seam adjacencies.

    Raw edge connectivity is authoritative.  A geometric edge joins two raw
    islands only when it has exactly one opposite-oriented half-edge pair, as
    expected at a UV/hard-normal seam.  Ambiguous coincident/non-manifold edge
    groups stay separate, preventing two overlapping but disconnected objects
    from collapsing into one shell merely because their positions match.
    """

    valid_faces = set(range(len(topology.faces))) - set(topology.invalid_faces)
    adjacency: dict[int, set[int]] = {face: set() for face in valid_faces}
    for face, rows in topology.face_to_faces.items():
        if face in valid_faces:
            adjacency[face].update(other for other in rows if other in valid_faces)
    for half_indices in topology.geometric_edge_to_half_edges.values():
        if len(half_indices) != 2:
            continue
        first, second = (topology.half_edges[index] for index in half_indices)
        if first.twin != second.index or second.twin != first.index:
            continue
        first_vertices = {
            topology.raw_to_geometric_vertex[index] for index in topology.faces[first.face]
        }
        second_vertices = {
            topology.raw_to_geometric_vertex[index] for index in topology.faces[second.face]
        }
        if first_vertices == second_vertices:
            # Opposite coincident faces are separate overlapping shells, not a
            # render seam between two different surface regions.
            continue
        adjacency[first.face].add(second.face)
        adjacency[second.face].add(first.face)

    remaining = set(valid_faces)
    components: list[tuple[int, ...]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        connected = {start}
        pending = [start]
        while pending:
            face = pending.pop()
            for adjacent in sorted(adjacency.get(face, ())):
                if adjacent in remaining:
                    remaining.remove(adjacent)
                    connected.add(adjacent)
                    pending.append(adjacent)
        components.append(tuple(sorted(connected)))
    return tuple(components)


def _shell_metadata(source: Mapping[str, Any], shell_index: int, *, loose_vertex: bool) -> dict[str, Any]:
    metadata = dict(source)
    metadata.update(
        {
            "operation": "separate_shells",
            "source_metadata": dict(source),
            "source_shell_index": int(shell_index),
            "loose_vertex_shell": bool(loose_vertex),
        }
    )
    return metadata


__all__ = [
    "AttributeChannel",
    "CombinedMeshRemap",
    "CombinedMeshResult",
    "IDENTITY_MATRIX4",
    "IndexedMeshOperand",
    "IndexedPolygonMesh",
    "Matrix4",
    "SeparateShellsResult",
    "SeparatedShell",
    "ShellElementRef",
    "SourceElement",
    "combine_indexed_meshes",
    "separate_indexed_mesh_shells",
]
