"""Topology cache and queries for triangle-based Aurora mesh nodes."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import math
from typing import Iterable

from .mesh_edit_types import MeshValidationReport


def normalize_edge(v1: int, v2: int) -> tuple[int, int]:
    """Store every edge once, independent of face winding direction."""

    a, b = int(v1), int(v2)
    return (a, b) if a <= b else (b, a)


def _vec_sub(a, b) -> tuple[float, float, float]:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _cross(a, b) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(v) -> float:
    return math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)


def _normal(a, b, c) -> tuple[float, float, float]:
    n = _cross(_vec_sub(b, a), _vec_sub(c, a))
    ln = _length(n)
    if ln <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (n[0] / ln, n[1] / ln, n[2] / ln)


@dataclass
class MeshTopology:
    mesh: object | None = None
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)
    face_normals: list[tuple[float, float, float]] = field(default_factory=list)
    vertex_normals: list[tuple[float, float, float]] = field(default_factory=list)
    edges: set[tuple[int, int]] = field(default_factory=set)
    edge_to_faces: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    vertex_to_edges: dict[int, set[tuple[int, int]]] = field(default_factory=dict)
    vertex_to_faces: dict[int, set[int]] = field(default_factory=dict)
    face_to_faces: dict[int, set[int]] = field(default_factory=dict)
    border_edges: set[tuple[int, int]] = field(default_factory=set)
    border_loops: list[list[int]] = field(default_factory=list)
    connected_elements: list[set[int]] = field(default_factory=list)
    material_groups: dict[int, set[int]] = field(default_factory=dict)
    smoothing_groups: dict[int, set[int]] = field(default_factory=dict)
    uv_channels: dict[str, object] = field(default_factory=dict)

    @classmethod
    def build_from_mesh(cls, mesh) -> "MeshTopology":
        topo = cls(mesh=mesh)
        topo.vertices = [tuple(map(float, v[:3])) for v in (getattr(mesh, "vertices", []) or [])]
        topo.faces = [tuple(map(int, f[:3])) for f in (getattr(mesh, "faces", []) or [])]
        topo._build()
        return topo

    @classmethod
    def rebuild_after_edit(cls, mesh) -> "MeshTopology":
        return cls.build_from_mesh(mesh)

    def _build(self) -> None:
        edge_to_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
        vertex_to_edges: dict[int, set[tuple[int, int]]] = defaultdict(set)
        vertex_to_faces: dict[int, set[int]] = defaultdict(set)
        face_to_edges: list[list[tuple[int, int]]] = []
        self.face_normals = []
        for fi, face in enumerate(self.faces):
            if len(set(face)) < 3 or any(v < 0 or v >= len(self.vertices) for v in face):
                self.face_normals.append((0.0, 0.0, 0.0))
                face_to_edges.append([])
                continue
            a, b, c = face
            edges = [normalize_edge(a, b), normalize_edge(b, c), normalize_edge(c, a)]
            face_to_edges.append(edges)
            self.face_normals.append(_normal(self.vertices[a], self.vertices[b], self.vertices[c]))
            for edge in edges:
                edge_to_faces[edge].append(fi)
                vertex_to_edges[edge[0]].add(edge)
                vertex_to_edges[edge[1]].add(edge)
            for vi in face:
                vertex_to_faces[vi].add(fi)
        self.edge_to_faces = {edge: list(faces) for edge, faces in edge_to_faces.items()}
        self.edges = set(self.edge_to_faces)
        self.vertex_to_edges = dict(vertex_to_edges)
        self.vertex_to_faces = dict(vertex_to_faces)
        self.border_edges = {edge for edge, faces in self.edge_to_faces.items() if len(faces) == 1}
        self.face_to_faces = self._build_face_adjacency()
        self.border_loops = self._build_border_loops()
        self.connected_elements = self._build_connected_elements()
        self.vertex_normals = self._build_vertex_normals()
        mats = getattr(self.mesh, "face_mats", []) or []
        self.material_groups = defaultdict(set)
        for fi in range(len(self.faces)):
            self.material_groups[int(mats[fi]) if fi < len(mats) else 0].add(fi)
        self.material_groups = dict(self.material_groups)
        smooth = getattr(self.mesh, "smoothing_groups", []) or getattr(self.mesh, "smooth_groups", []) or []
        self.smoothing_groups = defaultdict(set)
        for fi, value in enumerate(smooth[: len(self.faces)]):
            self.smoothing_groups[int(value)].add(fi)
        self.smoothing_groups = dict(self.smoothing_groups)
        self.uv_channels = {
            name: getattr(self.mesh, name)
            for name in ("uvs", "uvs_lm", "uvs_2", "uvs_3", "face_uvs")
            if hasattr(self.mesh, name)
        }

    def _build_face_adjacency(self) -> dict[int, set[int]]:
        adjacency: dict[int, set[int]] = {fi: set() for fi in range(len(self.faces))}
        for faces in self.edge_to_faces.values():
            for fi in faces:
                adjacency.setdefault(fi, set()).update(other for other in faces if other != fi)
        return adjacency

    def _build_border_loops(self) -> list[list[int]]:
        unused = set(self.border_edges)
        vertex_to_border_edges: dict[int, set[tuple[int, int]]] = defaultdict(set)
        for edge in self.border_edges:
            vertex_to_border_edges[edge[0]].add(edge)
            vertex_to_border_edges[edge[1]].add(edge)
        loops: list[list[int]] = []
        while unused:
            start = unused.pop()
            chain = [start[0], start[1]]
            for end_index in (1, 0):
                while True:
                    end_vertex = chain[-1] if end_index == 1 else chain[0]
                    next_edge = next((edge for edge in vertex_to_border_edges[end_vertex] if edge in unused), None)
                    if next_edge is None:
                        break
                    unused.remove(next_edge)
                    next_vertex = next_edge[1] if next_edge[0] == end_vertex else next_edge[0]
                    if end_index == 1:
                        chain.append(next_vertex)
                    else:
                        chain.insert(0, next_vertex)
                    if len(chain) > len(self.border_edges) + 2:
                        break
            loops.append(chain)
        return loops

    def _build_connected_elements(self) -> list[set[int]]:
        remaining = set(range(len(self.faces)))
        elements: list[set[int]] = []
        while remaining:
            start = remaining.pop()
            component = {start}
            queue: deque[int] = deque([start])
            while queue:
                fi = queue.popleft()
                for other in self.face_to_faces.get(fi, set()):
                    if other in remaining:
                        remaining.remove(other)
                        component.add(other)
                        queue.append(other)
            elements.append(component)
        return elements

    def _build_vertex_normals(self) -> list[tuple[float, float, float]]:
        accum = [[0.0, 0.0, 0.0] for _ in self.vertices]
        for fi, face in enumerate(self.faces):
            n = self.face_normals[fi] if fi < len(self.face_normals) else (0.0, 0.0, 0.0)
            for vi in face:
                if 0 <= vi < len(accum):
                    accum[vi][0] += n[0]
                    accum[vi][1] += n[1]
                    accum[vi][2] += n[2]
        normals = []
        for n in accum:
            ln = _length(n)
            normals.append((0.0, 0.0, 1.0) if ln <= 1e-12 else (n[0] / ln, n[1] / ln, n[2] / ln))
        return normals

    def get_edges(self) -> list[tuple[int, int]]:
        return sorted(self.edges)

    def get_border_edges(self) -> set[tuple[int, int]]:
        return set(self.border_edges)

    def get_border_loops(self) -> list[list[int]]:
        return [list(loop) for loop in self.border_loops]

    def get_connected_elements(self) -> list[set[int]]:
        return [set(element) for element in self.connected_elements]

    def get_faces_for_edge(self, edge) -> list[int]:
        return list(self.edge_to_faces.get(normalize_edge(*edge), []))

    def get_edges_for_face(self, face_index: int) -> list[tuple[int, int]]:
        if face_index < 0 or face_index >= len(self.faces):
            return []
        a, b, c = self.faces[face_index]
        return [normalize_edge(a, b), normalize_edge(b, c), normalize_edge(c, a)]

    def get_faces_for_vertex(self, vertex_index: int) -> list[int]:
        return sorted(self.vertex_to_faces.get(int(vertex_index), set()))

    def border_index_for_edge(self, edge) -> int | None:
        edge = normalize_edge(*edge)
        for idx, loop in enumerate(self.border_loops):
            loop_edges = {normalize_edge(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop) - 1)}
            if len(loop) > 2 and loop[0] == loop[-1]:
                loop_edges.add(normalize_edge(loop[-2], loop[-1]))
            if edge in loop_edges:
                return idx
        return None

    def find_edge_loop(self, start_edge) -> list[tuple[int, int]]:
        edge = normalize_edge(*start_edge)
        if edge not in self.edges:
            return []
        # First pass: boundary chains are reliable on triangulated KotOR meshes.
        if edge in self.border_edges:
            border_idx = self.border_index_for_edge(edge)
            if border_idx is None:
                return [edge]
            loop = self.border_loops[border_idx]
            return [normalize_edge(loop[i], loop[i + 1]) for i in range(len(loop) - 1)]
        return [edge]

    def find_edge_ring(self, start_edge) -> list[tuple[int, int]]:
        edge = normalize_edge(*start_edge)
        faces = self.get_faces_for_edge(edge)
        if not faces:
            return []
        ring = {edge}
        for fi in faces:
            for candidate in self.get_edges_for_face(fi):
                if candidate != edge and not set(candidate).intersection(edge):
                    ring.add(candidate)
        return sorted(ring)

    def validate_manifold_state(self) -> MeshValidationReport:
        report = MeshValidationReport()
        report.non_manifold_edges = sorted(edge for edge, faces in self.edge_to_faces.items() if len(faces) > 2)
        report.border_edges = sorted(self.border_edges)
        used = {vi for face in self.faces for vi in face}
        report.isolated_vertices = [vi for vi in range(len(self.vertices)) if vi not in used]
        report.degenerate_faces = [
            fi
            for fi, face in enumerate(self.faces)
            if len(set(face)) < 3 or any(vi < 0 or vi >= len(self.vertices) for vi in face)
            or _length(self.face_normals[fi]) <= 1e-12
        ]
        seen: dict[tuple[int, int, int], int] = {}
        duplicates = []
        for vi, vertex in enumerate(self.vertices):
            key = tuple(round(float(v) * 1000000.0) for v in vertex[:3])
            if key in seen:
                duplicates.append(vi)
            else:
                seen[key] = vi
        report.duplicate_vertices = duplicates
        if not self.smoothing_groups:
            report.notes.append("No smoothing-group metadata is available; normal tools will use geometric normals.")
        return report.finalize()


def face_edges(face: Iterable[int]) -> list[tuple[int, int]]:
    a, b, c = tuple(face)
    return [normalize_edge(a, b), normalize_edge(b, c), normalize_edge(c, a)]
