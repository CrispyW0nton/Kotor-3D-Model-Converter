"""Format-agnostic polygon connectivity and topology edit bookkeeping.

The runtime file formats remain indexed vertex/face arrays, but interactive
modeling needs stable adjacency, directed half-edges, seam-aware connectivity,
component remaps, and small dirty neighborhoods.  This module provides that
transient view without importing Qt, KOTOR formats, scene objects, or tool UI.

Render meshes frequently duplicate a geometric vertex for UV or hard-normal
seams.  ``MeshTopology`` therefore exposes both raw index connectivity and a
geometric connectivity view welded by a caller-controlled position tolerance.
No source vertex is destructively welded by building the topology cache.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from heapq import heapify, heappop
import math
from typing import Any, Iterable, Mapping, Sequence


Vector3 = tuple[float, float, float]
Face = tuple[int, ...]
Edge = tuple[int, int]
GeometricEdge = tuple[int, int]


def normalize_edge(first: int, second: int) -> Edge:
    """Return one deterministic undirected raw/geometric edge key."""

    a, b = int(first), int(second)
    return (a, b) if a <= b else (b, a)


def face_edges(face: Iterable[int]) -> list[Edge]:
    """Return the ordered, normalized boundary edges of a polygon face."""

    row = tuple(int(value) for value in face)
    if len(row) < 2:
        return []
    return [normalize_edge(row[index], row[(index + 1) % len(row)]) for index in range(len(row))]


def _sub(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _cross(a: Sequence[float], b: Sequence[float]) -> Vector3:
    return (
        (float(a[1]) * float(b[2])) - (float(a[2]) * float(b[1])),
        (float(a[2]) * float(b[0])) - (float(a[0]) * float(b[2])),
        (float(a[0]) * float(b[1])) - (float(a[1]) * float(b[0])),
    )


def _length(value: Sequence[float]) -> float:
    return math.sqrt(sum(float(component) * float(component) for component in value[:3]))


def _polygon_normal_and_area(vertices: Sequence[Vector3], face: Face) -> tuple[Vector3, float]:
    """Return a Newell normal and polygon area for any valid n-gon."""

    if len(face) < 3:
        return (0.0, 0.0, 0.0), 0.0
    nx = ny = nz = 0.0
    for index, vertex_index in enumerate(face):
        current = vertices[vertex_index]
        following = vertices[face[(index + 1) % len(face)]]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    magnitude = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
    if magnitude <= 1.0e-18:
        return (0.0, 0.0, 0.0), 0.0
    return (nx / magnitude, ny / magnitude, nz / magnitude), magnitude * 0.5


def _position_key(value: Sequence[float], tolerance: float) -> tuple[int, int, int] | tuple[float, float, float]:
    if tolerance <= 0.0:
        return (float(value[0]), float(value[1]), float(value[2]))
    inverse = 1.0 / tolerance
    return tuple(int(round(float(component) * inverse)) for component in value[:3])


@dataclass(frozen=True, slots=True)
class HalfEdge:
    """One directed face-boundary edge in raw and geometric index space."""

    index: int
    face: int
    corner: int
    origin: int
    destination: int
    geometric_origin: int
    geometric_destination: int
    next: int
    previous: int
    twin: int = -1


@dataclass(frozen=True, slots=True)
class TopologyComponent:
    """One edge-connected polygon shell and its cheap Euler diagnostics."""

    faces: tuple[int, ...]
    vertices: tuple[int, ...]
    geometric_vertices: tuple[int, ...]
    geometric_edges: tuple[GeometricEdge, ...]
    boundary_edges: tuple[GeometricEdge, ...]
    euler_characteristic: int
    closed: bool
    orientable: bool


@dataclass(slots=True)
class TopologyAudit:
    """Topology diagnostics shared by modeling, validation, and export gates."""

    has_errors: bool = False
    has_warnings: bool = False
    invalid_faces: list[int] = field(default_factory=list)
    non_manifold_edges: list[GeometricEdge] = field(default_factory=list)
    border_edges: list[GeometricEdge] = field(default_factory=list)
    isolated_vertices: list[int] = field(default_factory=list)
    degenerate_faces: list[int] = field(default_factory=list)
    inverted_faces: list[int] = field(default_factory=list)
    inconsistent_winding_edges: list[GeometricEdge] = field(default_factory=list)
    duplicate_vertices: list[int] = field(default_factory=list)
    duplicate_faces: list[int] = field(default_factory=list)
    branched_boundaries: list[int] = field(default_factory=list)
    components: list[TopologyComponent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def finalize(self) -> "TopologyAudit":
        self.has_errors = bool(self.invalid_faces or self.non_manifold_edges or self.degenerate_faces)
        self.has_warnings = bool(
            self.border_edges
            or self.isolated_vertices
            or self.inverted_faces
            or self.inconsistent_winding_edges
            or self.duplicate_vertices
            or self.duplicate_faces
            or self.branched_boundaries
            or self.notes
        )
        return self


@dataclass(frozen=True, slots=True)
class IndexRemap:
    """Stable old/new identity mapping emitted by a topology compaction."""

    old_vertex_to_new: tuple[int, ...]
    new_vertex_to_old: tuple[int, ...]
    old_face_to_new: tuple[int, ...]
    new_face_to_old: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CompactedMesh:
    vertices: tuple[Vector3, ...]
    faces: tuple[Face, ...]
    vertex_channels: dict[str, tuple[Any, ...]]
    remap: IndexRemap


@dataclass(frozen=True, slots=True)
class TopologyChangeSet:
    """Maya-style component dirty/change record for one modeling operation."""

    operation: str
    dirty_vertices: tuple[int, ...] = ()
    dirty_faces: tuple[int, ...] = ()
    created_vertices: tuple[int, ...] = ()
    created_faces: tuple[int, ...] = ()
    deleted_vertices: tuple[int, ...] = ()
    deleted_faces: tuple[int, ...] = ()
    remap: IndexRemap | None = None
    preview: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MeshTopology:
    """Transient raw-index and seam-aware half-edge view of a polygon mesh."""

    mesh: object | None = None
    vertices: list[Vector3] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)
    weld_tolerance: float = 1.0e-6
    face_normals: list[Vector3] = field(default_factory=list)
    face_areas: list[float] = field(default_factory=list)
    vertex_normals: list[Vector3] = field(default_factory=list)
    edges: set[Edge] = field(default_factory=set)
    edge_to_faces: dict[Edge, list[int]] = field(default_factory=dict)
    vertex_to_edges: dict[int, set[Edge]] = field(default_factory=dict)
    vertex_to_faces: dict[int, set[int]] = field(default_factory=dict)
    face_to_faces: dict[int, set[int]] = field(default_factory=dict)
    geometric_face_to_faces: dict[int, set[int]] = field(default_factory=dict)
    border_edges: set[Edge] = field(default_factory=set)
    geometric_border_edges: set[GeometricEdge] = field(default_factory=set)
    border_loops: list[list[int]] = field(default_factory=list)
    geometric_boundary_chains: list[list[int]] = field(default_factory=list)
    connected_elements: list[set[int]] = field(default_factory=list)
    material_groups: dict[int, set[int]] = field(default_factory=dict)
    smoothing_groups: dict[int, set[int]] = field(default_factory=dict)
    uv_channels: dict[str, object] = field(default_factory=dict)
    half_edges: tuple[HalfEdge, ...] = ()
    face_to_half_edges: dict[int, tuple[int, ...]] = field(default_factory=dict)
    geometric_edge_to_half_edges: dict[GeometricEdge, tuple[int, ...]] = field(default_factory=dict)
    geometric_edge_to_faces: dict[GeometricEdge, tuple[int, ...]] = field(default_factory=dict)
    raw_to_geometric_vertex: tuple[int, ...] = ()
    geometric_to_raw_vertices: dict[int, tuple[int, ...]] = field(default_factory=dict)
    geometric_positions: tuple[Vector3, ...] = ()
    invalid_faces: tuple[int, ...] = ()
    _components_cache: tuple[TopologyComponent, ...] | None = field(default=None, init=False, repr=False)

    @classmethod
    def build(
        cls,
        vertices: Iterable[Sequence[float]],
        faces: Iterable[Iterable[int]],
        *,
        weld_tolerance: float = 1.0e-6,
        mesh: object | None = None,
    ) -> "MeshTopology":
        topology = cls(mesh=mesh, weld_tolerance=max(0.0, float(weld_tolerance)))
        topology.vertices = [tuple(float(component) for component in tuple(vertex)[:3]) for vertex in vertices]
        topology.faces = [tuple(int(value) for value in face) for face in faces]
        topology._build()
        return topology

    @classmethod
    def build_from_mesh(cls, mesh: object, *, weld_tolerance: float = 1.0e-6) -> "MeshTopology":
        return cls.build(
            getattr(mesh, "vertices", ()) or (),
            getattr(mesh, "faces", ()) or (),
            weld_tolerance=weld_tolerance,
            mesh=mesh,
        )

    @classmethod
    def rebuild_after_edit(cls, mesh: object, *, weld_tolerance: float = 1.0e-6) -> "MeshTopology":
        return cls.build_from_mesh(mesh, weld_tolerance=weld_tolerance)

    def _build(self) -> None:
        self._build_geometric_vertices()
        raw_edge_faces: dict[Edge, list[int]] = defaultdict(list)
        vertex_edges: dict[int, set[Edge]] = defaultdict(set)
        vertex_faces: dict[int, set[int]] = defaultdict(set)
        face_half_edges: dict[int, tuple[int, ...]] = {}
        geometric_half_edges: dict[GeometricEdge, list[int]] = defaultdict(list)
        half_rows: list[HalfEdge] = []
        normals: list[Vector3] = []
        areas: list[float] = []
        invalid: list[int] = []

        for face_index, face in enumerate(self.faces):
            valid = (
                len(face) >= 3
                and all(0 <= vertex_index < len(self.vertices) for vertex_index in face)
            )
            if not valid:
                invalid.append(face_index)
                normals.append((0.0, 0.0, 0.0))
                areas.append(0.0)
                face_half_edges[face_index] = ()
                continue
            normal, area = _polygon_normal_and_area(self.vertices, face)
            normals.append(normal)
            areas.append(area)
            indices: list[int] = []
            base = len(half_rows)
            for corner, origin in enumerate(face):
                destination = face[(corner + 1) % len(face)]
                raw_edge = normalize_edge(origin, destination)
                raw_edge_faces[raw_edge].append(face_index)
                vertex_edges[origin].add(raw_edge)
                vertex_edges[destination].add(raw_edge)
                vertex_faces[origin].add(face_index)
                geometric_origin = self.raw_to_geometric_vertex[origin]
                geometric_destination = self.raw_to_geometric_vertex[destination]
                edge_key = normalize_edge(geometric_origin, geometric_destination)
                index = len(half_rows)
                indices.append(index)
                geometric_half_edges[edge_key].append(index)
                half_rows.append(
                    HalfEdge(
                        index=index,
                        face=face_index,
                        corner=corner,
                        origin=origin,
                        destination=destination,
                        geometric_origin=geometric_origin,
                        geometric_destination=geometric_destination,
                        next=base + ((corner + 1) % len(face)),
                        previous=base + ((corner - 1) % len(face)),
                    )
                )
            face_half_edges[face_index] = tuple(indices)

        # Resolve twins only for an unambiguous opposite-oriented pair. A
        # non-manifold group remains available through edge_to_half_edges.
        twin_by_index: dict[int, int] = {}
        for half_indices in geometric_half_edges.values():
            if len(half_indices) != 2:
                continue
            first, second = (half_rows[index] for index in half_indices)
            if (
                first.geometric_origin == second.geometric_destination
                and first.geometric_destination == second.geometric_origin
            ):
                twin_by_index[first.index] = second.index
                twin_by_index[second.index] = first.index
        self.half_edges = tuple(
            HalfEdge(
                index=row.index,
                face=row.face,
                corner=row.corner,
                origin=row.origin,
                destination=row.destination,
                geometric_origin=row.geometric_origin,
                geometric_destination=row.geometric_destination,
                next=row.next,
                previous=row.previous,
                twin=twin_by_index.get(row.index, -1),
            )
            for row in half_rows
        )
        self.invalid_faces = tuple(invalid)
        self.face_normals = normals
        self.face_areas = areas
        self.edge_to_faces = {edge: list(rows) for edge, rows in raw_edge_faces.items()}
        self.edges = set(self.edge_to_faces)
        self.vertex_to_edges = dict(vertex_edges)
        self.vertex_to_faces = dict(vertex_faces)
        self.border_edges = {edge for edge, rows in self.edge_to_faces.items() if len(rows) == 1}
        self.face_to_half_edges = face_half_edges
        self.geometric_edge_to_half_edges = {
            edge: tuple(rows) for edge, rows in geometric_half_edges.items()
        }
        self.geometric_edge_to_faces = {
            edge: tuple(dict.fromkeys(self.half_edges[index].face for index in rows))
            for edge, rows in self.geometric_edge_to_half_edges.items()
        }
        self.geometric_border_edges = {
            edge for edge, rows in self.geometric_edge_to_half_edges.items() if len(rows) == 1
        }
        self.face_to_faces = self._build_face_adjacency(self.edge_to_faces)
        self.geometric_face_to_faces = self._build_face_adjacency(self.geometric_edge_to_faces)
        self.border_loops = self._build_raw_border_loops()
        self.geometric_boundary_chains = self._build_geometric_boundary_chains()
        # Components are a full-mesh invariant of this transient topology.
        # Building them again during every validation/audit needlessly repeats
        # a complete graph traversal on large imported rooms.
        components = self.components()
        self._components_cache = components
        self.connected_elements = [set(component.faces) for component in components]
        self.vertex_normals = self._build_vertex_normals()
        self._build_optional_mesh_channels()

    def _build_geometric_vertices(self) -> None:
        by_key: dict[tuple[Any, Any, Any], int] = {}
        positions: list[Vector3] = []
        raw_to_geometric: list[int] = []
        grouped: dict[int, list[int]] = defaultdict(list)
        for raw_index, position in enumerate(self.vertices):
            key = _position_key(position, self.weld_tolerance)
            geometric = by_key.get(key)
            if geometric is None:
                geometric = len(positions)
                by_key[key] = geometric
                positions.append(position)
            raw_to_geometric.append(geometric)
            grouped[geometric].append(raw_index)
        self.raw_to_geometric_vertex = tuple(raw_to_geometric)
        self.geometric_to_raw_vertices = {key: tuple(value) for key, value in grouped.items()}
        self.geometric_positions = tuple(positions)

    @staticmethod
    def _build_face_adjacency(edge_faces: Mapping[Edge, Sequence[int]]) -> dict[int, set[int]]:
        """Build a sparse, deterministic face-neighbour graph.

        A manifold edge has at most two incident faces, so its exact adjacency
        is one symmetric pair.  Invalid meshes can put thousands of faces on
        the same edge (duplicate triangles are a common example).  Expanding
        that incidence into an all-pairs clique is quadratic in both time and
        memory and can exhaust the process before the non-manifold audit gets
        a chance to report the bad edge.

        For a non-manifold edge, connect every incident face to the lowest
        face index as a deterministic sparse star.  This keeps the faces in one
        connected shell and bounds stored adjacency to ``2 * (n - 1)`` entries.
        The complete edge incidence remains available through
        ``edge_to_faces``/``geometric_edge_to_faces`` for diagnostics and
        operations that explicitly need every owner.
        """

        adjacency: dict[int, set[int]] = defaultdict(set)
        for faces in edge_faces.values():
            incident = tuple(sorted({int(face) for face in faces}))
            if len(incident) < 2:
                continue
            anchor = incident[0]
            for face in incident[1:]:
                adjacency[anchor].add(face)
                adjacency[face].add(anchor)
        return dict(adjacency)

    def _build_raw_border_loops(self) -> list[list[int]]:
        unused = set(self.border_edges)
        # ``min(unused)`` on every disconnected raw boundary chain is
        # quadratic.  Imported render meshes commonly duplicate vertices at
        # UV/hard-normal seams, so a perfectly ordinary large OBJ can expose
        # tens of thousands of short raw chains even though its welded
        # geometric boundary is small.  A lazy heap returns the same
        # deterministic minimum edge while reducing chain-start selection to
        # O(E log E); consumed edges remain in the heap and are skipped when
        # encountered later.
        starts = list(unused)
        heapify(starts)
        incident: dict[int, set[Edge]] = defaultdict(set)
        for edge in unused:
            incident[edge[0]].add(edge)
            incident[edge[1]].add(edge)
        chains: list[list[int]] = []
        while unused:
            start = heappop(starts)
            while start not in unused:
                start = heappop(starts)
            unused.remove(start)
            chain = [start[0], start[1]]
            while True:
                candidates = sorted(edge for edge in incident[chain[-1]] if edge in unused)
                if not candidates:
                    break
                edge = candidates[0]
                unused.remove(edge)
                chain.append(edge[1] if edge[0] == chain[-1] else edge[0])
                if chain[-1] == chain[0]:
                    break
            chains.append(chain)
        return chains

    def _build_geometric_boundary_chains(self) -> list[list[int]]:
        boundary_half_edges = [
            rows[0]
            for rows in self.geometric_edge_to_half_edges.values()
            if len(rows) == 1
        ]
        outgoing: dict[int, list[int]] = defaultdict(list)
        for half_index in boundary_half_edges:
            outgoing[self.half_edges[half_index].geometric_origin].append(half_index)
        unused = set(boundary_half_edges)
        starts = list(unused)
        heapify(starts)
        chains: list[list[int]] = []
        while unused:
            start_index = heappop(starts)
            while start_index not in unused:
                start_index = heappop(starts)
            start = self.half_edges[start_index]
            unused.remove(start_index)
            chain = [start.geometric_origin, start.geometric_destination]
            while True:
                candidates = sorted(index for index in outgoing.get(chain[-1], ()) if index in unused)
                if not candidates:
                    break
                next_index = candidates[0]
                unused.remove(next_index)
                chain.append(self.half_edges[next_index].geometric_destination)
                if chain[-1] == chain[0]:
                    break
            chains.append(chain)
        return chains

    def _build_vertex_normals(self) -> list[Vector3]:
        accum = [[0.0, 0.0, 0.0] for _ in self.vertices]
        for face_index, face in enumerate(self.faces):
            if face_index in self.invalid_faces:
                continue
            normal = self.face_normals[face_index]
            area = self.face_areas[face_index]
            for vertex_index in face:
                accum[vertex_index][0] += normal[0] * area
                accum[vertex_index][1] += normal[1] * area
                accum[vertex_index][2] += normal[2] * area
        result: list[Vector3] = []
        for value in accum:
            magnitude = _length(value)
            result.append(
                (0.0, 0.0, 1.0)
                if magnitude <= 1.0e-18
                else (value[0] / magnitude, value[1] / magnitude, value[2] / magnitude)
            )
        return result

    def _build_optional_mesh_channels(self) -> None:
        if self.mesh is None:
            return
        materials = getattr(self.mesh, "face_mats", ()) or ()
        grouped_materials: dict[int, set[int]] = defaultdict(set)
        for face_index in range(len(self.faces)):
            grouped_materials[int(materials[face_index]) if face_index < len(materials) else 0].add(face_index)
        self.material_groups = dict(grouped_materials)
        smoothing = getattr(self.mesh, "smoothing_groups", ()) or getattr(self.mesh, "smooth_groups", ()) or ()
        grouped_smoothing: dict[int, set[int]] = defaultdict(set)
        for face_index, value in enumerate(tuple(smoothing)[: len(self.faces)]):
            grouped_smoothing[int(value)].add(face_index)
        self.smoothing_groups = dict(grouped_smoothing)
        self.uv_channels = {
            name: getattr(self.mesh, name)
            for name in ("uvs", "uvs_lm", "uvs_2", "uvs_3", "face_uvs")
            if hasattr(self.mesh, name)
        }

    def get_edges(self) -> list[Edge]:
        return sorted(self.edges)

    def get_border_edges(self) -> set[Edge]:
        return set(self.border_edges)

    def get_border_loops(self) -> list[list[int]]:
        return [list(loop) for loop in self.border_loops]

    def get_connected_elements(self) -> list[set[int]]:
        return [set(element) for element in self.connected_elements]

    def get_faces_for_edge(self, edge: Sequence[int]) -> list[int]:
        return list(self.edge_to_faces.get(normalize_edge(int(edge[0]), int(edge[1])), ()))

    def get_faces_for_geometric_edge(self, edge: Sequence[int]) -> list[int]:
        return list(self.geometric_edge_to_faces.get(normalize_edge(int(edge[0]), int(edge[1])), ()))

    def get_edges_for_face(self, face_index: int) -> list[Edge]:
        if not 0 <= int(face_index) < len(self.faces):
            return []
        return face_edges(self.faces[int(face_index)])

    def get_half_edges_for_face(self, face_index: int) -> tuple[HalfEdge, ...]:
        return tuple(self.half_edges[index] for index in self.face_to_half_edges.get(int(face_index), ()))

    def get_faces_for_vertex(self, vertex_index: int) -> list[int]:
        return sorted(self.vertex_to_faces.get(int(vertex_index), ()))

    def get_faces_for_geometric_vertex(self, geometric_vertex: int) -> list[int]:
        result: set[int] = set()
        for raw_index in self.geometric_to_raw_vertices.get(int(geometric_vertex), ()):
            result.update(self.vertex_to_faces.get(raw_index, ()))
        return sorted(result)

    def geometric_edge_for_face_corners(self, face_index: int, corners: Sequence[int]) -> GeometricEdge:
        face = self.faces[int(face_index)]
        first, second = (int(value) % len(face) for value in tuple(corners)[:2])
        return normalize_edge(
            self.raw_to_geometric_vertex[face[first]],
            self.raw_to_geometric_vertex[face[second]],
        )

    def region_boundary_half_edges(self, face_indices: Iterable[int]) -> tuple[HalfEdge, ...]:
        """Return oriented boundary half-edges for a selected face region."""

        selected = {int(value) for value in face_indices if 0 <= int(value) < len(self.faces)}
        boundary: list[HalfEdge] = []
        for edge, rows in self.geometric_edge_to_half_edges.items():
            selected_rows = [index for index in rows if self.half_edges[index].face in selected]
            if len(selected_rows) == 1:
                boundary.append(self.half_edges[selected_rows[0]])
            elif len(selected_rows) > 1 and len(selected_rows) != len(rows):
                # Non-manifold/partial selections remain explicit rather than
                # silently disappearing from the extrusion boundary.
                boundary.extend(self.half_edges[index] for index in selected_rows)
        return tuple(sorted(boundary, key=lambda row: (row.face, row.corner)))

    def boundary_index_for_edge(self, edge: Sequence[int]) -> int | None:
        wanted = normalize_edge(int(edge[0]), int(edge[1]))
        for index, loop in enumerate(self.border_loops):
            if wanted in {normalize_edge(loop[offset], loop[offset + 1]) for offset in range(len(loop) - 1)}:
                return index
        return None

    # Compatibility spelling retained for the existing Mesh Tools package.
    border_index_for_edge = boundary_index_for_edge

    def find_edge_loop(self, start_edge: Sequence[int]) -> list[Edge]:
        edge = normalize_edge(int(start_edge[0]), int(start_edge[1]))
        if edge not in self.edges:
            return []
        if edge in self.border_edges:
            border_index = self.boundary_index_for_edge(edge)
            if border_index is not None:
                loop = self.border_loops[border_index]
                return [normalize_edge(loop[index], loop[index + 1]) for index in range(len(loop) - 1)]
        return [edge]

    def find_edge_ring(self, start_edge: Sequence[int]) -> list[Edge]:
        edge = normalize_edge(int(start_edge[0]), int(start_edge[1]))
        faces = self.get_faces_for_edge(edge)
        if not faces:
            return []
        ring = {edge}
        for face_index in faces:
            for candidate in self.get_edges_for_face(face_index):
                if candidate != edge and not set(candidate).intersection(edge):
                    ring.add(candidate)
        return sorted(ring)

    def components(self, face_indices: Iterable[int] | None = None) -> tuple[TopologyComponent, ...]:
        if face_indices is None and self._components_cache is not None:
            return self._components_cache
        selected = (
            {int(value) for value in face_indices if 0 <= int(value) < len(self.faces)}
            if face_indices is not None
            else set(range(len(self.faces))) - set(self.invalid_faces)
        )
        remaining = set(selected)
        result: list[TopologyComponent] = []
        while remaining:
            start = min(remaining)
            remaining.remove(start)
            faces = {start}
            queue: deque[int] = deque((start,))
            while queue:
                face = queue.popleft()
                for adjacent in self.geometric_face_to_faces.get(face, ()):
                    if adjacent in remaining:
                        remaining.remove(adjacent)
                        faces.add(adjacent)
                        queue.append(adjacent)
            raw_vertices = {vertex for face in faces for vertex in self.faces[face]}
            geometric_vertices = {self.raw_to_geometric_vertex[vertex] for vertex in raw_vertices}
            geometric_edges = {
                normalize_edge(row.geometric_origin, row.geometric_destination)
                for face in faces
                for row in self.get_half_edges_for_face(face)
            }
            boundary = {
                edge
                for edge in geometric_edges
                if len([face for face in self.geometric_edge_to_faces.get(edge, ()) if face in faces]) == 1
            }
            orientable = not any(
                self._edge_has_inconsistent_winding(edge)
                for edge in geometric_edges
                if len(self.geometric_edge_to_half_edges.get(edge, ())) == 2
            )
            result.append(
                TopologyComponent(
                    faces=tuple(sorted(faces)),
                    vertices=tuple(sorted(raw_vertices)),
                    geometric_vertices=tuple(sorted(geometric_vertices)),
                    geometric_edges=tuple(sorted(geometric_edges)),
                    boundary_edges=tuple(sorted(boundary)),
                    euler_characteristic=len(geometric_vertices) - len(geometric_edges) + len(faces),
                    closed=not boundary,
                    orientable=orientable,
                )
            )
        return tuple(result)

    def affected_one_ring(
        self,
        *,
        vertices: Iterable[int] = (),
        faces: Iterable[int] = (),
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Expand a dirty component set to its geometric one-ring."""

        dirty_faces = {int(value) for value in faces if 0 <= int(value) < len(self.faces)}
        geometric_vertices = {
            self.raw_to_geometric_vertex[int(value)]
            for value in vertices
            if 0 <= int(value) < len(self.vertices)
        }
        for face in tuple(dirty_faces):
            geometric_vertices.update(self.raw_to_geometric_vertex[index] for index in self.faces[face])
            dirty_faces.update(self.geometric_face_to_faces.get(face, ()))
        for geometric in tuple(geometric_vertices):
            dirty_faces.update(self.get_faces_for_geometric_vertex(geometric))
        dirty_vertices = {
            raw
            for geometric in geometric_vertices
            for raw in self.geometric_to_raw_vertices.get(geometric, ())
        }
        dirty_vertices.update(vertex for face in dirty_faces for vertex in self.faces[face])
        return tuple(sorted(dirty_vertices)), tuple(sorted(dirty_faces))

    def _edge_has_inconsistent_winding(self, edge: GeometricEdge) -> bool:
        rows = self.geometric_edge_to_half_edges.get(edge, ())
        if len(rows) != 2:
            return False
        first, second = (self.half_edges[index] for index in rows)
        return not (
            first.geometric_origin == second.geometric_destination
            and first.geometric_destination == second.geometric_origin
        )

    def validate_manifold_state(self) -> TopologyAudit:
        report = TopologyAudit()
        report.invalid_faces = list(self.invalid_faces)
        report.non_manifold_edges = sorted(
            edge for edge, rows in self.geometric_edge_to_half_edges.items() if len(rows) > 2
        )
        report.border_edges = sorted(self.geometric_border_edges)
        used = {vertex for face_index, face in enumerate(self.faces) if face_index not in self.invalid_faces for vertex in face}
        report.isolated_vertices = [index for index in range(len(self.vertices)) if index not in used]
        report.degenerate_faces = sorted(
            {
                face_index
                for face_index, face in enumerate(self.faces)
                if face_index in self.invalid_faces
                or len({self.raw_to_geometric_vertex[index] for index in face if 0 <= index < len(self.vertices)}) < 3
                or self.face_areas[face_index] <= 1.0e-12
            }
        )
        report.inconsistent_winding_edges = sorted(
            edge for edge in self.geometric_edge_to_half_edges if self._edge_has_inconsistent_winding(edge)
        )
        report.inverted_faces = sorted(
            {
                self.half_edges[rows[1]].face
                for edge, rows in self.geometric_edge_to_half_edges.items()
                if len(rows) == 2 and self._edge_has_inconsistent_winding(edge)
            }
        )
        report.duplicate_vertices = sorted(
            raw
            for rows in self.geometric_to_raw_vertices.values()
            for raw in rows[1:]
        )
        seen_faces: dict[tuple[int, ...], int] = {}
        duplicates: list[int] = []
        for face_index, face in enumerate(self.faces):
            if face_index in self.invalid_faces:
                continue
            key = tuple(sorted(self.raw_to_geometric_vertex[index] for index in face))
            if key in seen_faces:
                duplicates.append(face_index)
            else:
                seen_faces[key] = face_index
        report.duplicate_faces = duplicates
        boundary_degree: dict[int, int] = defaultdict(int)
        for edge in self.geometric_border_edges:
            boundary_degree[edge[0]] += 1
            boundary_degree[edge[1]] += 1
        report.branched_boundaries = sorted(vertex for vertex, degree in boundary_degree.items() if degree > 2)
        report.components = list(self.components())
        if not self.smoothing_groups and self.mesh is not None:
            report.notes.append("No smoothing-group metadata is available; geometric normals are used.")
        return report.finalize()


def compact_indexed_mesh(
    vertices: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    *,
    vertex_channels: Mapping[str, Sequence[Any]] | None = None,
    kept_face_indices: Iterable[int] | None = None,
) -> CompactedMesh:
    """Compact unused vertices while emitting stable vertex and face remaps."""

    source_vertices = tuple(tuple(float(component) for component in tuple(vertex)[:3]) for vertex in vertices)
    source_faces = tuple(tuple(int(value) for value in face) for face in faces)
    kept = (
        tuple(dict.fromkeys(int(value) for value in kept_face_indices))
        if kept_face_indices is not None
        else tuple(range(len(source_faces)))
    )
    for face_index in kept:
        if not 0 <= face_index < len(source_faces):
            raise IndexError(f"Face index {face_index} is outside 0..{len(source_faces) - 1}.")
        if any(index < 0 or index >= len(source_vertices) for index in source_faces[face_index]):
            raise IndexError(f"Face {face_index} contains an out-of-range vertex index.")
    used = sorted({index for face_index in kept for index in source_faces[face_index]})
    old_vertex_to_new = [-1] * len(source_vertices)
    for new_index, old_index in enumerate(used):
        old_vertex_to_new[old_index] = new_index
    old_face_to_new = [-1] * len(source_faces)
    for new_index, old_index in enumerate(kept):
        old_face_to_new[old_index] = new_index
    remapped_faces = tuple(
        tuple(old_vertex_to_new[index] for index in source_faces[face_index])
        for face_index in kept
    )
    channels: dict[str, tuple[Any, ...]] = {}
    for name, values in dict(vertex_channels or {}).items():
        row = tuple(values)
        if len(row) == len(source_vertices):
            channels[str(name)] = tuple(row[index] for index in used)
    return CompactedMesh(
        vertices=tuple(source_vertices[index] for index in used),
        faces=remapped_faces,
        vertex_channels=channels,
        remap=IndexRemap(
            old_vertex_to_new=tuple(old_vertex_to_new),
            new_vertex_to_old=tuple(used),
            old_face_to_new=tuple(old_face_to_new),
            new_face_to_old=tuple(kept),
        ),
    )


__all__ = [
    "CompactedMesh",
    "Edge",
    "Face",
    "HalfEdge",
    "IndexRemap",
    "MeshTopology",
    "TopologyAudit",
    "TopologyChangeSet",
    "TopologyComponent",
    "Vector3",
    "compact_indexed_mesh",
    "face_edges",
    "normalize_edge",
]
