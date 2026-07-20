"""Generate evidence-pinned legacy room walkmesh candidates.

This command is deliberately narrower than Map Studio's general render-derived
walkmesh generator.  It never guesses from a node name, texture name, normal,
or bounding box alone.  A room is emitted only when this file contains an
explicit, source-hash-audited node allowlist backed by surviving sibling WOKs.

The current evidence set has two different outcomes:

* ``505QGM`` keeps its authoritative, map-wide ``505QGM_01a`` WOK.  That WOK
  overlaps the authored floor surfaces in all eight surviving visual
  partitions, so generating per-partition WOKs would duplicate collision.
* ``KOQ202_01d`` receives a narrow structural candidate from the explicitly
  allowlisted ``Object428`` surface.  It is the only flat ``LKOa_flr03`` floor
  surface in that room, and the same material covers most WOK centroids in all
  four surviving KOQ202 collision rooms.  This does not prove that the room is
  complete or that retail KOTOR accepts it.

Outputs are written only below
``Converted/WalkmeshAudit/GeneratedCandidates``.  Source files and indexed
conversion artifacts are never modified.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from src.core.geometry.model_data import GameVersion, ModelNode, NodeFlags  # noqa: E402
from src.core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    build_imported_mesh_primitive_from_stock_model,
)
from src.core.modules.module_format import (  # noqa: E402
    LYTLayout,
    LYTRoom,
    VISData,
    WOKData,
    WOKFace,
)
from src.core.workflow.legacy_module_repair import (  # noqa: E402
    LegacyModuleCandidateRequest,
    build_legacy_module_candidate,
)

from scripts.audit_walkmesh_library import (  # noqa: E402
    audit_kmap,
    audit_mod,
    compare_mod_kmap_walkmeshes,
)
from scripts.compile_nwmax_room_candidate import (  # noqa: E402
    _aabb_ascii_block,
    _model_geometry_fingerprint,
    _parse_aabb_wok,
    _read_ascii,
    _rename_model,
    _without_node_type,
    compile_candidate,
    prepare_room_ascii,
)
from scripts.prove_legacy_module_mapstudio_roundtrip import prove  # noqa: E402
from src.core.mdl.mdl_parser import MDLAsciiParser, MDLBinaryParser  # noqa: E402
from src.core.mdl.mdl_writer import MDLBinaryWriter  # noqa: E402
from src.core.validation.kotor_module_engine_contract import (  # noqa: E402
    inspect_raw_mdl_structure,
    inspect_raw_wok_structure,
)

DEFAULT_MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
DEFAULT_OUTPUT = (
    DEFAULT_MODULE_ROOT
    / "Converted"
    / "WalkmeshAudit"
    / "GeneratedCandidates"
    / "LegacyRoomFloorSelection"
)
WALKABLE_SURFACE = 1
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
ROOM_COMPARISON_FIELDS = (
    "visual_mesh_node_count",
    "visual_face_count",
    "visual_texture_count",
    "visual_textures",
    "aabb_node_count",
    "aabb_face_count",
)
VISUAL_COMPARISON_FIELDS = (
    "visual_mesh_node_count",
    "visual_face_count",
    "visual_texture_count",
    "visual_textures",
)


@dataclass(frozen=True)
class ExplicitFloorSelection:
    """A human-reviewed collision selection; never populated heuristically."""

    room_resref: str
    selected_node_names: tuple[str, ...]
    expected_texture: str
    max_slope_degrees: float = 45.0
    output_surface: int = WALKABLE_SURFACE
    require_single_component: bool = True
    weld_epsilon: float = 1.0e-5


KOQ202_01D_SELECTION = ExplicitFloorSelection(
    room_resref="koq202_01d",
    selected_node_names=("Object428",),
    expected_texture="LKOa_flr03",
)


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "byte_size": path.stat().st_size,
        "sha256": _hash_file(path),
    }


def _validation_rows(report: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in tuple(getattr(report, "issues", ()) or ()):
        severity = getattr(getattr(issue, "severity", None), "value", getattr(issue, "severity", ""))
        rows.append(
            {
                "severity": str(severity or "").lower(),
                "code": str(getattr(issue, "code", "") or ""),
                "message": str(getattr(issue, "message", issue) or ""),
                "details": dict(getattr(issue, "details", {}) or {}),
            }
        )
    return rows


def _is_blocking(rows: Iterable[dict[str, Any]]) -> bool:
    return any(str(row.get("severity") or "").lower() in {"error", "blocking"} for row in rows)


def _triangle_normal(
    a: Sequence[float],
    b: Sequence[float],
    c: Sequence[float],
) -> tuple[float, float, float, float]:
    ux, uy, uz = (float(b[index]) - float(a[index]) for index in range(3))
    vx, vy, vz = (float(c[index]) - float(a[index]) for index in range(3))
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    return nx, ny, nz, math.sqrt(nx * nx + ny * ny + nz * nz)


def _bounds(vertices: Sequence[Sequence[float]]) -> dict[str, list[float]] | None:
    if not vertices:
        return None
    return {
        "min": [min(float(vertex[axis]) for vertex in vertices) for axis in range(3)],
        "max": [max(float(vertex[axis]) for vertex in vertices) for axis in range(3)],
    }


def _surface_descriptor(surface: ImportedMeshSurface) -> dict[str, Any]:
    horizontal = 0
    steep = 0
    degenerate = 0
    for face in surface.faces:
        if len(face) < 3 or any(index < 0 or index >= len(surface.vertices) for index in face[:3]):
            degenerate += 1
            continue
        normal = _triangle_normal(*(surface.vertices[index] for index in face[:3]))
        if normal[3] <= 1.0e-9:
            degenerate += 1
        elif abs(normal[2] / normal[3]) >= math.cos(math.radians(45.0)):
            horizontal += 1
        else:
            steep += 1
    return {
        "name": str(surface.name),
        "texture": str(surface.texture),
        "vertex_count": len(surface.vertices),
        "face_count": len(surface.faces),
        "horizontal_face_count": horizontal,
        "steep_face_count": steep,
        "degenerate_face_count": degenerate,
        "bounds": _bounds(surface.vertices),
    }


def _find_welded_vertex(
    vertices: list[tuple[float, float, float]],
    point: tuple[float, float, float],
    epsilon: float,
) -> int:
    epsilon_squared = epsilon * epsilon
    for index, existing in enumerate(vertices):
        if sum((existing[axis] - point[axis]) ** 2 for axis in range(3)) <= epsilon_squared:
            return index
    vertices.append(point)
    return len(vertices) - 1


def _component_count(wok: WOKData) -> int:
    if not wok.faces:
        return 0
    owners: dict[tuple[int, int], int] = {}
    neighbours: list[set[int]] = [set() for _ in wok.faces]
    for face_index, face in enumerate(wok.faces):
        for edge in ((int(face.v1), int(face.v2)), (int(face.v2), int(face.v3)), (int(face.v3), int(face.v1))):
            key = tuple(sorted(edge))
            previous = owners.get(key)
            if previous is None:
                owners[key] = face_index
            else:
                neighbours[face_index].add(previous)
                neighbours[previous].add(face_index)
    remaining = set(range(len(wok.faces)))
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            current = stack.pop()
            for neighbour in neighbours[current]:
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    stack.append(neighbour)
    return count


def _geometry_signature(wok: WOKData, decimals: int = 3) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for face in wok.faces:
        points = tuple(
            sorted(
                tuple(round(float(value), decimals) for value in wok.verts[index])
                for index in (int(face.v1), int(face.v2), int(face.v3))
            )
        )
        rows.append((points, int(face.surface)))
    return sorted(rows)


def build_explicit_floor_wok(
    primitive: ImportedMeshRoomPrimitive,
    selection: ExplicitFloorSelection,
) -> tuple[WOKData, dict[str, Any]]:
    """Compile only explicitly allowlisted, planar render surfaces into WOK.

    Downward render winding is normalized to upward WOK winding.  A selected
    node with even one steep/degenerate face blocks the whole operation rather
    than silently discarding geometry.
    """

    epsilon = float(selection.weld_epsilon)
    if not math.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("Weld epsilon must be finite and positive.")
    max_slope = float(selection.max_slope_degrees)
    if not math.isfinite(max_slope) or not 0.0 <= max_slope < 90.0:
        raise ValueError("Maximum slope must be finite and in [0, 90).")
    threshold = math.cos(math.radians(max_slope))

    by_name: dict[str, list[ImportedMeshSurface]] = {}
    for surface in primitive.surfaces:
        by_name.setdefault(str(surface.name).casefold(), []).append(surface)
    selected: list[ImportedMeshSurface] = []
    for requested in selection.selected_node_names:
        matches = by_name.get(str(requested).casefold(), [])
        if len(matches) != 1:
            raise ValueError(
                f"Explicit floor node {requested!r} resolves to {len(matches)} surfaces; expected exactly one."
            )
        surface = matches[0]
        if str(surface.texture).casefold() != str(selection.expected_texture).casefold():
            raise ValueError(
                f"Explicit floor node {requested!r} uses texture {surface.texture!r}; "
                f"expected {selection.expected_texture!r}."
            )
        selected.append(surface)

    vertices: list[tuple[float, float, float]] = []
    faces: list[WOKFace] = []
    selected_rows: list[dict[str, Any]] = []
    seen_triangles: set[tuple[int, int, int]] = set()
    for surface in selected:
        row = _surface_descriptor(surface)
        for face_index, face in enumerate(surface.faces):
            if len(face) < 3 or any(index < 0 or index >= len(surface.vertices) for index in face[:3]):
                raise ValueError(f"{surface.name} face {face_index} has invalid indices {face!r}.")
            points = [tuple(float(value) for value in surface.vertices[index][:3]) for index in face[:3]]
            nx, ny, nz, length = _triangle_normal(*points)
            if length <= 1.0e-9:
                raise ValueError(f"{surface.name} face {face_index} is degenerate.")
            if abs(nz / length) < threshold:
                raise ValueError(
                    f"{surface.name} face {face_index} exceeds the {max_slope:g}-degree floor slope gate."
                )
            if nz < 0.0:
                points[1], points[2] = points[2], points[1]
            indices = tuple(_find_welded_vertex(vertices, point, epsilon) for point in points)
            if len(set(indices)) != 3:
                raise ValueError(f"{surface.name} face {face_index} collapses under the weld policy.")
            signature = tuple(sorted(indices))
            if signature in seen_triangles:
                raise ValueError(f"{surface.name} face {face_index} duplicates selected collision geometry.")
            seen_triangles.add(signature)
            faces.append(WOKFace(indices[0], indices[1], indices[2], int(selection.output_surface)))
        selected_rows.append(row)

    if not faces:
        raise ValueError("Explicit floor selection produced no faces.")
    wok = WOKData(name=str(selection.room_resref))
    wok.verts = vertices
    wok.faces = faces
    components = _component_count(wok)
    if selection.require_single_component and components != 1:
        raise ValueError(
            f"Explicit floor selection produced {components} disconnected components; expected one."
        )
    return wok, {
        "policy": "exact_node_allowlist_and_exact_texture_v1",
        "selection": asdict(selection),
        "selected_nodes": selected_rows,
        "output_vertex_count": len(vertices),
        "output_face_count": len(faces),
        "component_count": components,
        "bounds": _bounds(vertices),
    }


def _ascii_primitive(path: Path, room: str) -> ImportedMeshRoomPrimitive:
    model = MDLAsciiParser().parse_string(_read_ascii(path))
    return build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=room,
        source_model=str(path),
        game="K2",
    )


def _binary_primitive(mdl: Path, mdx: Path, room: str) -> ImportedMeshRoomPrimitive:
    model = MDLBinaryParser(mdl.read_bytes(), mdx.read_bytes()).parse()
    if model is None:
        raise ValueError(f"Could not parse {mdl} with {mdx}.")
    return build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=room,
        source_model=str(mdl),
        game="K2",
    )


def _point_in_triangle_xy(
    point: Sequence[float],
    a: Sequence[float],
    b: Sequence[float],
    c: Sequence[float],
    epsilon: float = 1.0e-5,
) -> bool:
    def side(p1: Sequence[float], p2: Sequence[float], p3: Sequence[float]) -> float:
        return (float(p1[0]) - float(p3[0])) * (float(p2[1]) - float(p3[1])) - (
            float(p2[0]) - float(p3[0])
        ) * (float(p1[1]) - float(p3[1]))

    values = (side(point, a, b), side(point, b, c), side(point, c, a))
    return not (min(values) < -epsilon and max(values) > epsilon)


def _wok_centroids(wok: WOKData) -> list[tuple[float, float, float]]:
    return [
        tuple(
            sum(float(wok.verts[index][axis]) for index in (int(face.v1), int(face.v2), int(face.v3))) / 3.0
            for axis in range(3)
        )
        for face in wok.faces
    ]


def _horizontal_triangles(
    surfaces: Iterable[ImportedMeshSurface],
    *,
    predicate: Any,
) -> list[tuple[str, str, tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]:
    rows = []
    for surface in surfaces:
        if not predicate(surface):
            continue
        for face in surface.faces:
            if len(face) < 3 or any(index < 0 or index >= len(surface.vertices) for index in face[:3]):
                continue
            points = tuple(tuple(float(value) for value in surface.vertices[index][:3]) for index in face[:3])
            normal = _triangle_normal(*points)
            if normal[3] > 1.0e-9 and abs(normal[2] / normal[3]) >= math.cos(math.radians(45.0)):
                rows.append((str(surface.name), str(surface.texture), *points))
    return rows


def _centroid_coverage(
    wok: WOKData,
    triangles: Iterable[tuple[str, str, Sequence[float], Sequence[float], Sequence[float]]],
    *,
    z_tolerance: float = 0.25,
) -> dict[str, Any]:
    triangle_rows = list(triangles)
    hit_count = 0
    hit_nodes: dict[str, int] = {}
    hit_textures: dict[str, int] = {}
    for centroid in _wok_centroids(wok):
        hits = {
            (node, texture)
            for node, texture, a, b, c in triangle_rows
            if abs(centroid[2] - ((float(a[2]) + float(b[2]) + float(c[2])) / 3.0)) <= z_tolerance
            and _point_in_triangle_xy(centroid, a, b, c)
        }
        if hits:
            hit_count += 1
        for node, texture in hits:
            hit_nodes[node] = hit_nodes.get(node, 0) + 1
            hit_textures[texture] = hit_textures.get(texture, 0) + 1
    return {
        "wok_face_centroid_count": len(wok.faces),
        "covered_wok_face_centroid_count": hit_count,
        "coverage_ratio": 0.0 if not wok.faces else hit_count / len(wok.faces),
        "triangle_count": len(triangle_rows),
        "hit_nodes": dict(sorted(hit_nodes.items())),
        "hit_textures": dict(sorted(hit_textures.items())),
    }


def _wok_audit(room: str, data: bytes) -> dict[str, Any]:
    fingerprint, report = inspect_raw_wok_structure(room, data)
    rows = _validation_rows(report)
    parsed = WOKData.from_bytes(data)
    return {
        "fingerprint": asdict(fingerprint),
        "validation": rows,
        "blocking": _is_blocking(rows),
        "component_count": _component_count(parsed),
        "bounds": _bounds(parsed.verts),
    }


def _parse_lyt_rooms(path: Path) -> list[str]:
    rooms: list[str] = []
    remaining = 0
    for raw_line in path.read_text(encoding="latin-1", errors="replace").splitlines():
        tokens = raw_line.strip().split()
        if not tokens or tokens[0].startswith("#"):
            continue
        if tokens[0].casefold() == "roomcount":
            remaining = int(tokens[1])
            continue
        if remaining > 0:
            rooms.append(tokens[0].casefold())
            remaining -= 1
    return rooms


def _analyse_505(module_root: Path) -> dict[str, Any]:
    source_root = module_root / "Q_SellOut" / "Extracted" / "Aqua" / "Aqua" / "LabFloor2"
    collision_root = module_root / "Q_SellOut" / "Extracted" / "505QGM" / "505QGM"
    ascii_paths = sorted((source_root / "ASCII").glob("505QGM_*.mdl"), key=lambda item: item.name.casefold())
    wok_path = collision_root / "505QGM_01a.wok"
    repaired_wok_path = (
        module_root
        / "Converted"
        / "Candidates"
        / "505qgm"
        / "K2"
        / "Candidate"
        / "Resources"
        / "505qgm_01a.wok"
    )
    lyt_path = collision_root / "505qgm.lyt"
    authoritative = WOKData.from_bytes(wok_path.read_bytes())
    embedded, embedded_metadata = _parse_aabb_wok(
        _read_ascii(source_root / "ASCII" / "505QGM_01a.mdl"),
        room="505qgm_01a",
        max_slope_degrees=45.0,
    )
    indexed_vertex_delta = math.inf
    if len(embedded.verts) == len(authoritative.verts):
        indexed_vertex_delta = max(
            (math.dist(embedded.verts[index], authoritative.verts[index]) for index in range(len(embedded.verts))),
            default=0.0,
        )
    face_index_topology_matches = [
        (int(face.v1), int(face.v2), int(face.v3), int(face.surface)) for face in embedded.faces
    ] == [
        (int(face.v1), int(face.v2), int(face.v3), int(face.surface)) for face in authoritative.faces
    ]
    repaired = WOKData.from_bytes(repaired_wok_path.read_bytes())
    repaired_geometry_matches_source = _geometry_signature(repaired, 5) == _geometry_signature(authoritative, 5)
    if not repaired_geometry_matches_source:
        raise RuntimeError("Repaired 505QGM_01a WOK changed authoritative floor geometry.")

    all_floor_triangles = []
    per_partition: dict[str, Any] = {}
    for path in ascii_paths:
        primitive = _ascii_primitive(path, path.stem.casefold())
        triangles = _horizontal_triangles(
            primitive.surfaces,
            predicate=lambda surface: "floor" in str(surface.name).casefold()
            and "trim" not in str(surface.name).casefold(),
        )
        coverage = _centroid_coverage(authoritative, triangles)
        per_partition[path.stem.casefold()] = {
            "source": _artifact(path),
            "floor_intent": "node name contains 'floor' and excludes 'trim' (calibration only)",
            "floor_triangle_count": len(triangles),
            "authoritative_wok_overlap": coverage,
        }
        all_floor_triangles.extend(triangles)

    lyt_rooms = _parse_lyt_rooms(lyt_path)
    surviving_rooms = {path.stem.casefold() for path in ascii_paths}
    blocked: list[dict[str, Any]] = []
    for room in lyt_rooms:
        if room == "505qgm_01a":
            continue
        if room not in surviving_rooms:
            reason = "No surviving ASCII or MAX visual source exists; collision cannot be inferred."
        elif int(per_partition[room]["authoritative_wok_overlap"]["covered_wok_face_centroid_count"]) > 0:
            reason = (
                "The authoritative 505QGM_01a WOK already overlaps this partition's explicit floor-named "
                "render surfaces. A second per-room WOK would duplicate collision at the same LYT origin."
            )
        else:
            reason = "The authoritative centralized-collision hypothesis is not proven for this partition."
        blocked.append({"room": room, "candidate_generated": False, "reason": reason})

    return {
        "module": "505qgm",
        "decision": "preserve_authoritative_map_wide_01a_geometry_in_repaired_wok_and_do_not_generate_partition_woks",
        "source_lyt": _artifact(lyt_path),
        "lyt_rooms": lyt_rooms,
        "authoritative_wok": _artifact(wok_path),
        "authoritative_wok_audit": _wok_audit("505qgm_01a", wok_path.read_bytes()),
        "repaired_authoritative_wok": _artifact(repaired_wok_path),
        "repaired_authoritative_wok_audit": _wok_audit("505qgm_01a", repaired_wok_path.read_bytes()),
        "repaired_wok_geometry_matches_source": repaired_geometry_matches_source,
        "serialization_repair": (
            "The recovered source WOK has intact indexed floor, adjacency, perimeter, and face coverage, but "
            "its internal AABB child table is invalid. The promoted candidate uses the existing rebuilt-AABB "
            "serialization with the same authoritative geometry."
        ),
        "embedded_aabb": {
            "metadata": embedded_metadata,
            "vertex_set_matches_external_at_0_001": {
                tuple(round(float(value), 3) for value in vertex) for vertex in embedded.verts
            }
            == {
                tuple(round(float(value), 3) for value in vertex) for vertex in authoritative.verts
            },
            "face_index_topology_matches_external": face_index_topology_matches,
            "max_vertex_delta_by_index": indexed_vertex_delta,
            "geometry_matches_external_with_0_00001_tolerance": bool(
                face_index_topology_matches and indexed_vertex_delta <= 1.0e-5
            ),
        },
        "combined_floor_overlap": _centroid_coverage(authoritative, all_floor_triangles),
        "partition_floor_overlap": per_partition,
        "blocked_partition_candidates": blocked,
        "trust": {
            "structural": True,
            "authoring_intent": (
                "Strong evidence for one centralized collision WOK: the source 01a embedded AABB and external "
                "WOK have identical indexed face topology and vertices within 0.00001 units, and that WOK "
                "overlaps all eight surviving visual partitions. The promoted bytes retain that geometry with "
                "a rebuilt valid AABB table."
            ),
            "retail_game_proven": False,
        },
    }


def _analyse_koq202_calibration(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for room in ("koq202_01a", "koq202_01b", "koq202_01c", "koq202_01g"):
        mdl = root / "BIN" / f"{room.upper()}.mdl"
        mdx = root / "BIN" / f"{room.upper()}.mdx"
        wok_path = root / "BIN" / f"{room.upper()}.wok"
        primitive = _binary_primitive(mdl, mdx, room)
        wok = WOKData.from_bytes(wok_path.read_bytes())
        triangles = _horizontal_triangles(
            primitive.surfaces,
            predicate=lambda surface: str(surface.texture).casefold() == "lkoa_flr03",
        )
        rows.append(
            {
                "room": room,
                "mdl": _artifact(mdl),
                "mdx": _artifact(mdx),
                "wok": _artifact(wok_path),
                "wok_audit": _wok_audit(room, wok_path.read_bytes()),
                "lkoa_flr03_centroid_coverage": _centroid_coverage(wok, triangles),
            }
        )
    return rows


def _aabb_source_text(room: str, wok: WOKData) -> str:
    lines = [
        f"newmodel {room}",
        f"setsupermodel {room} NULL",
        "classification TILE",
        f"beginmodelgeom {room}",
        f"node dummy {room}",
        "  parent NULL",
        "  position 0 0 0",
        "  orientation 1 0 0 0",
        "endnode",
        *_aabb_ascii_block(room, wok),
        f"endmodelgeom {room}",
        f"donemodel {room}",
        "",
    ]
    return "\n".join(lines)


def _generate_koq202_01d(module_root: Path, output_root: Path) -> dict[str, Any]:
    source_root = (
        module_root
        / "Q_SellOut"
        / "Extracted"
        / "Korr_Expand2"
        / "Korr_Expand2"
        / "InnerTemple"
    )
    ascii_path = source_root / "ASCII" / "KOQ202_01d.mdl"
    max_path = source_root / "Export_Parts" / "KOQ202_01d.max"
    lyt_path = source_root / "BIN" / "KOQ202.lyt"
    vis_path = source_root / "BIN" / "KOQ202.vis"
    destination = output_root / "koq202" / "K2" / "koq202_01d-explicit-floor"
    destination.mkdir(parents=True, exist_ok=True)

    primitive = _ascii_primitive(ascii_path, KOQ202_01D_SELECTION.room_resref)
    wok, selection_metadata = build_explicit_floor_wok(primitive, KOQ202_01D_SELECTION)
    wok_bytes = wok.to_bytes()
    wok_audit = _wok_audit(KOQ202_01D_SELECTION.room_resref, wok_bytes)
    if wok_audit["blocking"]:
        raise RuntimeError("Explicit KOQ202_01d WOK failed raw structural validation.")
    readback = WOKData.from_bytes(wok_bytes)
    if _geometry_signature(readback, 5) != _geometry_signature(wok, 5):
        raise RuntimeError("Explicit KOQ202_01d WOK changed geometry during write/readback.")

    standalone_wok = destination / "koq202_01d.floor-selection.wok"
    standalone_wok.write_bytes(wok_bytes)
    aabb_source = destination / "koq202_01d.floor-selection-aabb.mdl.ascii"
    aabb_source.write_text(
        _aabb_source_text(KOQ202_01D_SELECTION.room_resref, wok),
        encoding="latin-1",
        newline="\n",
    )

    selected_names = {name.casefold() for name in KOQ202_01D_SELECTION.selected_node_names}
    excluded_nodes = []
    for surface in primitive.surfaces:
        if str(surface.name).casefold() in selected_names:
            continue
        descriptor = _surface_descriptor(surface)
        if str(surface.texture).casefold() == KOQ202_01D_SELECTION.expected_texture.casefold():
            reason = "same floor texture but not allowlisted; geometry is non-planar/steep and cannot be inferred as WOK"
        else:
            reason = "not present in the reviewed collision-node allowlist"
        excluded_nodes.append({**descriptor, "exclusion_reason": reason})

    compile_args = argparse.Namespace(
        room=KOQ202_01D_SELECTION.room_resref,
        game="K2",
        render_ascii=[str(ascii_path)],
        walkmesh_ascii=str(aabb_source),
        mdlops=str(ROOT / "Saved" / "ExternalTools" / "mdlops" / "mdlops.exe"),
        output=str(destination),
        max_slope_degrees=45.0,
        overwrite=True,
    )
    compile_result = compile_candidate(compile_args)
    compiled_wok = destination / "koq202_01d.wok"
    compiled_match = False
    if compiled_wok.is_file():
        compiled_match = _geometry_signature(WOKData.from_bytes(compiled_wok.read_bytes()), 5) == _geometry_signature(
            wok, 5
        )

    return {
        "module": "koq202",
        "room": "koq202_01d",
        "decision": "explicit_floor_candidate_generated",
        "source_ascii": _artifact(ascii_path),
        "source_max": _artifact(max_path),
        "source_lyt": _artifact(lyt_path),
        "source_vis": _artifact(vis_path),
        "lyt_contains_room": "koq202_01d" in _parse_lyt_rooms(lyt_path),
        "selection": selection_metadata,
        "excluded_nodes": excluded_nodes,
        "standalone_wok": _artifact(standalone_wok),
        "aabb_source": _artifact(aabb_source),
        "wok_audit": wok_audit,
        "compile_result": compile_result,
        "compiled_wok_matches_explicit_selection": compiled_match,
        "calibration": _analyse_koq202_calibration(source_root),
        "max_live_inspection": {
            "completed": False,
            "blocker": (
                "3ds Max 2019 interactive MCP launch failed before scene load with a WPF FontCache "
                "System.UriFormatException; ASCII and surviving binary/WOK evidence were used instead."
            ),
        },
        "trust": {
            "structural_candidate": bool(compile_result.get("ok") and compiled_match),
            "authoring_intent": (
                "Narrow evidence: exact reviewed node Object428, exact LKOa_flr03 material, two planar faces, "
                "single component, and sibling-room material calibration. Completeness remains unproven."
            ),
            "module_complete": False,
            "module_blocker": (
                "The source LYT also lists KOQ202_01e/01f/01h/01i/01j, whose render and collision sources "
                "are absent. This room candidate must not be represented as a complete KOQ202 recovery."
            ),
            "retail_game_proven": False,
        },
    }


def _mdl_audit(
    room: str,
    mdl_bytes: bytes,
    mdx_bytes: bytes,
    *,
    allow_missing_aabb: bool,
) -> dict[str, Any]:
    fingerprint, report = inspect_raw_mdl_structure(
        room,
        mdl_bytes,
        mdx_bytes,
        game="K2",
        allow_missing_aabb=allow_missing_aabb,
    )
    rows = _validation_rows(report)
    return {
        "fingerprint": asdict(fingerprint),
        "validation": rows,
        "blocking": _is_blocking(rows),
    }


def _compile_static_ascii_room(
    *,
    room: str,
    ascii_path: Path,
    output_dir: Path,
    visual_only: bool,
    external_wok_path: Path | None = None,
    legacy_binary_root: Path | None = None,
    generate_floor_wok_from_embedded_aabb: bool = False,
    legacy_comparison_fields: Sequence[str] = ROOM_COMPARISON_FIELDS,
) -> dict[str, Any]:
    """Compile one reviewed ASCII room through Ghost Studio's K2 writer.

    Visual-only rooms deliberately receive the retail-style no-AABB MDL plus
    canonical 136-byte empty WOK.  The playable room must instead preserve an
    independently recovered WOK that agrees with its embedded ASCII AABB.
    """

    room = room.casefold()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_text = _read_ascii(ascii_path)
    if visual_only:
        prepared_ascii = _rename_model(_without_node_type(source_text, "aabb"), room)
        prepared_wok = WOKData(name=room)
        preparation: dict[str, Any] = {
            "policy": "retail_k2_visual_only_partition",
            "embedded_aabb_removed": True,
            "external_wok": "canonical empty 136-byte BWM",
        }
        external_wok_bytes = prepared_wok.to_bytes()
    else:
        if (
            not generate_floor_wok_from_embedded_aabb
            and (external_wok_path is None or not external_wok_path.is_file())
        ):
            raise FileNotFoundError(f"Playable room {room} requires an authoritative external WOK.")
        prepared_ascii, prepared_wok, preparation = prepare_room_ascii(
            source_text,
            None,
            room=room,
            max_slope_degrees=45.0,
        )
        if generate_floor_wok_from_embedded_aabb:
            external_wok_bytes = prepared_wok.to_bytes()
            preparation = {
                **preparation,
                "external_wok_policy": "floor_only_from_reviewed_embedded_aabb",
                "generated_external_wok_matches_embedded_aabb": True,
            }
        else:
            assert external_wok_path is not None
            external_wok_bytes = external_wok_path.read_bytes()
            external_wok = WOKData.from_bytes(external_wok_bytes)
            embedded_faces = [
                (int(face.v1), int(face.v2), int(face.v3), int(face.surface))
                for face in prepared_wok.faces
            ]
            external_faces = [
                (int(face.v1), int(face.v2), int(face.v3), int(face.surface))
                for face in external_wok.faces
            ]
            if embedded_faces != external_faces or len(prepared_wok.verts) != len(external_wok.verts):
                raise RuntimeError(
                    f"{room} embedded AABB and authoritative external WOK do not share indexed topology."
                )
            indexed_vertex_delta = max(
                (
                    math.dist(prepared_wok.verts[index], external_wok.verts[index])
                    for index in range(len(prepared_wok.verts))
                ),
                default=0.0,
            )
            if indexed_vertex_delta > 1.0e-5:
                raise RuntimeError(
                    f"{room} embedded/external WOK vertex delta {indexed_vertex_delta:g} exceeds 0.00001."
                )
            preparation = {
                **preparation,
                "authoritative_external_wok": _artifact(external_wok_path),
                "embedded_external_face_index_topology_matches": True,
                "embedded_external_max_indexed_vertex_delta": indexed_vertex_delta,
            }

    wok_audit = _wok_audit(room, external_wok_bytes)
    if visual_only:
        _fingerprint, empty_report = inspect_raw_wok_structure(
            room,
            external_wok_bytes,
            allow_empty_visual=True,
        )
        wok_audit["visual_only_validation"] = _validation_rows(empty_report)
        wok_audit["blocking"] = _is_blocking(wok_audit["visual_only_validation"])
        if len(external_wok_bytes) != 136:
            raise RuntimeError(f"{room} visual-only WOK is {len(external_wok_bytes)} bytes, expected 136.")
    if wok_audit["blocking"]:
        raise RuntimeError(f"{room} external WOK failed its structural contract.")

    model = MDLAsciiParser().parse_string(prepared_ascii)
    model.name = room
    model.game_version = GameVersion.K2
    model.animations = []
    controller_count = sum(
        len(tuple(getattr(node, "controllers", ()) or ()))
        for node in model.all_nodes()
    )
    if controller_count:
        raise RuntimeError(f"{room} static ASCII unexpectedly contains {controller_count} controllers.")
    source_geometry = _model_geometry_fingerprint(model)
    expected_aabb_count = 0 if visual_only else 1
    if int(source_geometry["aabb_node_count"]) != expected_aabb_count:
        raise RuntimeError(
            f"{room} prepared ASCII has {source_geometry['aabb_node_count']} AABB nodes; "
            f"expected {expected_aabb_count}."
        )

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    mdl_audit = _mdl_audit(
        room,
        mdl_bytes,
        mdx_bytes,
        allow_missing_aabb=visual_only,
    )
    if mdl_audit["blocking"]:
        raise RuntimeError(f"{room} K2 binary MDL failed vanilla-derived structural gates.")
    if int(mdl_audit["fingerprint"]["controller_count"]) != 0:
        raise RuntimeError(f"{room} promoted static MDL contains transform controllers.")

    binary_model = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
    if binary_model is None:
        raise RuntimeError(f"{room} promoted MDL/MDX failed semantic readback.")
    binary_geometry = _model_geometry_fingerprint(binary_model)
    geometry_mismatches = {
        field: {"prepared_ascii": source_geometry[field], "binary_readback": binary_geometry[field]}
        for field in source_geometry
        if field != "aabb_bounds" and source_geometry[field] != binary_geometry[field]
    }
    source_bounds = source_geometry.get("aabb_bounds")
    binary_bounds = binary_geometry.get("aabb_bounds")
    bounds_match = source_bounds is None and binary_bounds is None
    if source_bounds is not None and binary_bounds is not None:
        bounds_match = all(
            abs(float(source_bounds[bound][axis]) - float(binary_bounds[bound][axis])) <= 1.0e-5
            for bound in ("min", "max")
            for axis in range(3)
        )
    if not bounds_match:
        geometry_mismatches["aabb_bounds"] = {
            "prepared_ascii": source_bounds,
            "binary_readback": binary_bounds,
        }
    if geometry_mismatches:
        raise RuntimeError(f"{room} K2 writer changed geometry: {geometry_mismatches}")

    legacy_comparison: dict[str, Any] = {"available": False}
    if legacy_binary_root is not None:
        legacy_mdl_path = legacy_binary_root / f"{room}.mdl"
        legacy_mdx_path = legacy_binary_root / f"{room}.mdx"
        if legacy_mdl_path.is_file() and legacy_mdx_path.is_file():
            legacy_model = MDLBinaryParser(
                legacy_mdl_path.read_bytes(),
                legacy_mdx_path.read_bytes(),
            ).parse()
            if legacy_model is None:
                raise RuntimeError(f"Could not semantically parse legacy binary comparison for {room}.")
            legacy_geometry = _model_geometry_fingerprint(legacy_model)
            comparison_mismatches = {
                field: {"legacy_binary": legacy_geometry[field], "new_k2_binary": binary_geometry[field]}
                for field in legacy_comparison_fields
                if legacy_geometry[field] != binary_geometry[field]
            }
            if comparison_mismatches:
                raise RuntimeError(
                    f"{room} visual face/node/texture comparison changed: {comparison_mismatches}"
                )
            legacy_mdl_audit = _mdl_audit(
                room,
                legacy_mdl_path.read_bytes(),
                legacy_mdx_path.read_bytes(),
                allow_missing_aabb=visual_only,
            )
            legacy_comparison = {
                "available": True,
                "mdl": _artifact(legacy_mdl_path),
                "mdx": _artifact(legacy_mdx_path),
                "geometry": legacy_geometry,
                "raw_structure": legacy_mdl_audit,
                "comparison_fields": list(legacy_comparison_fields),
                "comparison_mismatches": {},
                "note": (
                    "Legacy binary vertex counts may be expanded by its writer; node, face, texture, "
                    "and AABB semantics are exact."
                ),
            }

    mdl_path = output_dir / f"{room}.mdl"
    mdx_path = output_dir / f"{room}.mdx"
    wok_path = output_dir / f"{room}.wok"
    ascii_output = output_dir / f"{room}.source-combined.mdl.ascii"
    mdl_path.write_bytes(mdl_bytes)
    mdx_path.write_bytes(mdx_bytes)
    wok_path.write_bytes(external_wok_bytes)
    ascii_output.write_text(prepared_ascii, encoding="latin-1", newline="\n")
    return {
        "room": room,
        "visual_only": visual_only,
        "source_ascii": _artifact(ascii_path),
        "preparation": preparation,
        "prepared_geometry": source_geometry,
        "binary_geometry": binary_geometry,
        "binary_geometry_parity_mismatches": {},
        "mdl_audit": mdl_audit,
        "wok_audit": wok_audit,
        "legacy_binary_comparison": legacy_comparison,
        "outputs": {
            "mdl": _artifact(mdl_path),
            "mdx": _artifact(mdx_path),
            "wok": _artifact(wok_path),
            "ascii": _artifact(ascii_output),
        },
    }


def _node_kinds(flags: int) -> str:
    names = [
        flag.name
        for flag in (NodeFlags.MESH, NodeFlags.LIGHT, NodeFlags.EMITTER, NodeFlags.REFERENCE, NodeFlags.SKIN, NodeFlags.DANGLY, NodeFlags.AABB, NodeFlags.SABER)
        if flags & int(flag)
    ]
    return "|".join(names) if names else "dummy"


def _quaternion_delta(a: Sequence[float], b: Sequence[float]) -> float:
    """Sign-normalized max component delta between two XYZW quaternions."""

    dot = sum(float(x) * float(y) for x, y in zip(a, b))
    sign = -1.0 if dot < 0.0 else 1.0
    return max(abs(float(x) - sign * float(y)) for x, y in zip(a, b))


def _audit_static_room_controllers(model: Any, *, tolerance: float = 1.0e-5) -> dict[str, Any]:
    """Prove that a room's controllers are redundant bind-transform keys.

    Legacy MDLOps/NWMax room compiles commonly emitted one position and one
    orientation controller at time zero for every non-root node.  Those keys
    merely duplicate the node-header bind transform; they are not animation.
    The controller-free K2 room writer is the proven promotion route for these
    recovered static rooms.  It may strip this exact redundant pattern but must
    reject real animation, multi-key curves, other controller types, or a value
    that differs from the node's bind transform.
    """

    animations = tuple(getattr(model, "animations", ()) or ())
    invalid: list[str] = []
    controller_count = 0
    redundant_count = 0
    nodes_with_controllers = 0
    type_counts: dict[str, int] = {}
    for node in tuple(model.all_nodes()):
        controllers = tuple(getattr(node, "controllers", ()) or ())
        if not controllers:
            continue
        nodes_with_controllers += 1
        seen_types: set[int] = set()
        for controller in controllers:
            controller_count += 1
            if not isinstance(controller, dict):
                invalid.append(f"{node.name}: controller {controller_count - 1} is not a decoded mapping.")
                continue
            controller_type = int(controller.get("type", controller.get("controller_type", -1)))
            type_counts[str(controller_type)] = type_counts.get(str(controller_type), 0) + 1
            if controller_type not in (8, 20):
                invalid.append(f"{node.name}: controller type {controller_type} is not a static transform key.")
                continue
            if controller_type in seen_types:
                invalid.append(f"{node.name}: duplicate controller type {controller_type}.")
                continue
            seen_types.add(controller_type)
            times = tuple(controller.get("times", ()) or ())
            values = tuple(controller.get("values", ()) or ())
            if len(times) != 1 or len(values) != 1:
                invalid.append(
                    f"{node.name}: controller type {controller_type} has {len(times)} time(s) and "
                    f"{len(values)} value row(s), expected one redundant key."
                )
                continue
            if not math.isfinite(float(times[0])) or abs(float(times[0])) > tolerance:
                invalid.append(
                    f"{node.name}: controller type {controller_type} key time {times[0]!r} is not zero."
                )
                continue
            value = tuple(float(component) for component in values[0])
            expected = tuple(
                float(component)
                for component in (
                    getattr(node, "position", (0.0, 0.0, 0.0))
                    if controller_type == 8
                    else getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
                )
            )
            expected_columns = 3 if controller_type == 8 else 4
            if len(value) != expected_columns or len(expected) != expected_columns:
                invalid.append(
                    f"{node.name}: controller type {controller_type} has an invalid transform width."
                )
                continue
            delta = (
                max(abs(a - b) for a, b in zip(value, expected))
                if controller_type == 8
                else _quaternion_delta(value, expected)
            )
            if delta > tolerance:
                invalid.append(
                    f"{node.name}: controller type {controller_type} differs from its bind transform "
                    f"by {delta:g}."
                )
                continue
            redundant_count += 1

    if animations:
        invalid.append(f"model contains {len(animations)} animation block(s).")
    safe_to_strip = not invalid and redundant_count == controller_count
    return {
        "animation_count": len(animations),
        "controller_count": controller_count,
        "controller_type_counts": type_counts,
        "nodes_with_controllers": nodes_with_controllers,
        "redundant_bind_transform_controller_count": redundant_count,
        "pattern": "controller_free" if controller_count == 0 else "single_key_bind_transform",
        "safe_to_strip": safe_to_strip,
        "invalid_reasons": invalid,
        "tolerance": tolerance,
    }


def _freeze_behavior_value(value: Any) -> Any:
    """Return a stable, exact-comparison representation of node behavior data."""

    if isinstance(value, dict):
        return tuple(
            (str(key), _freeze_behavior_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_behavior_value(item) for item in value)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if value is None:
        return None
    return str(value)


def _controller_inventory(controller: Any) -> tuple[Any, ...]:
    """Capture every decoded and raw controller field required for lossless writing."""

    if not isinstance(controller, dict):
        return ("invalid", repr(controller))
    fields = (
        "type",
        "name",
        "columns",
        "times",
        "values",
        "binary_unknown0",
        "binary_column_count",
        "binary_unknown1",
        "binary_compressed_quaternion_words",
        "is_bezier",
        "binary_bezier_rows",
    )
    return tuple((field, _freeze_behavior_value(controller.get(field))) for field in fields)


def _audit_preserved_room_controllers(model: Any) -> dict[str, Any]:
    """Prove a static room controller bank is finite and safe to preserve exactly.

    True K2 CHITIN rooms are the oracle: ``001ebo1`` carries 199 established
    controllers and emitter partition ``001ebo17`` carries 837.  A conversion
    must therefore retain source controller rows and raw entry metadata; it may
    not infer that a room should be controller-free from an Override copy.
    """

    invalid: list[str] = []
    type_counts: dict[str, int] = {}
    controller_count = 0
    nodes_with_controllers = 0
    for node in tuple(model.all_nodes()):
        controllers = tuple(getattr(node, "controllers", ()) or ())
        if controllers:
            nodes_with_controllers += 1
        for ordinal, controller in enumerate(controllers):
            controller_count += 1
            if not isinstance(controller, dict):
                invalid.append(f"{node.name}[{ordinal}] is not a decoded controller mapping.")
                continue
            controller_type = int(controller.get("type", -1))
            type_counts[str(controller_type)] = type_counts.get(str(controller_type), 0) + 1
            times = tuple(controller.get("times", ()) or ())
            values = tuple(controller.get("values", ()) or ())
            if not times or len(times) != len(values):
                invalid.append(
                    f"{node.name}[{ordinal}] type {controller_type} has {len(times)} time row(s) "
                    f"and {len(values)} value row(s)."
                )
                continue
            raw_columns = int(
                controller.get("binary_column_count", controller.get("columns", 1)) or 1
            )
            logical_columns = raw_columns & 0x0F
            if logical_columns <= 0:
                invalid.append(
                    f"{node.name}[{ordinal}] type {controller_type} has invalid column byte "
                    f"0x{raw_columns & 0xFF:02x}."
                )
                continue
            for time in times:
                if not math.isfinite(float(time)):
                    invalid.append(f"{node.name}[{ordinal}] contains a non-finite key time.")
                    break
            for row in values:
                if not isinstance(row, (list, tuple)) or not all(
                    math.isfinite(float(value)) for value in row
                ):
                    invalid.append(f"{node.name}[{ordinal}] contains a malformed/non-finite row.")
                    break

    animations = tuple(getattr(model, "animations", ()) or ())
    if animations:
        invalid.append(f"model contains {len(animations)} animation block(s).")
    return {
        "animation_count": len(animations),
        "controller_count": controller_count,
        "controller_type_counts": type_counts,
        "nodes_with_controllers": nodes_with_controllers,
        "safe_to_preserve": not invalid,
        "invalid_reasons": invalid,
        "oracle": "true K2 CHITIN 001ebo1/001ebo17 controller-bearing rooms",
    }


def _model_controller_inventory(model: Any) -> tuple[tuple[Any, ...], ...]:
    """Controller banks in DFS node order, including the embedded AABB node."""

    return tuple(
        (
            str(getattr(node, "name", "") or ""),
            int(getattr(node, "flags", 0) or 0),
            tuple(
                _controller_inventory(controller)
                for controller in (getattr(node, "controllers", ()) or ())
            ),
        )
        for node in model.all_nodes()
    )


def _node_inventory(model: Any) -> list[dict[str, Any]]:
    """DFS inventory of every non-AABB node for source/output parity checks.

    The payload fields deliberately cover the complete static visual surface,
    not only aggregate counts: indexed geometry, UV channels, normal/tangent
    data, face-material assignments, texture slots, and render-material state.
    Parsed source/output values are float32, so exact equality here proves the
    writer did not numerically alter the room payload.
    """

    rows: list[dict[str, Any]] = []
    for node in model.all_nodes():
        flags = int(getattr(node, "flags", 0))
        if flags & int(NodeFlags.AABB):
            continue
        rows.append(
            {
                "name": str(getattr(node, "name", "") or ""),
                "parent": str(getattr(getattr(node, "parent", None), "name", "") or ""),
                "kinds": _node_kinds(flags),
                "face_count": len(getattr(node, "faces", []) or []),
                "vertex_count": len(getattr(node, "vertices", []) or []),
                "texture": str(getattr(node, "texture", "") or "").strip().casefold(),
                "lightmap": str(getattr(node, "lightmap", "") or "").strip().casefold(),
                "flags": flags,
                "faces": tuple(tuple(int(value) for value in face) for face in (getattr(node, "faces", ()) or ())),
                "vertices": tuple(tuple(float(value) for value in row) for row in (getattr(node, "vertices", ()) or ())),
                "normals": tuple(tuple(float(value) for value in row) for row in (getattr(node, "normals", ()) or ())),
                "tangents": tuple(tuple(float(value) for value in row) for row in (getattr(node, "tangents", ()) or ())),
                "uvs": tuple(tuple(float(value) for value in row) for row in (getattr(node, "uvs", ()) or ())),
                "uvs_lm": tuple(tuple(float(value) for value in row) for row in (getattr(node, "uvs_lm", ()) or ())),
                "uvs_2": tuple(tuple(float(value) for value in row) for row in (getattr(node, "uvs_2", ()) or ())),
                "uvs_3": tuple(tuple(float(value) for value in row) for row in (getattr(node, "uvs_3", ()) or ())),
                "face_uvs": tuple(tuple(int(value) for value in row) for row in (getattr(node, "face_uvs", ()) or ())),
                "face_mats": tuple(int(value) for value in (getattr(node, "face_mats", ()) or ())),
                "texture_raw": str(getattr(node, "texture", "") or ""),
                "lightmap_raw": str(getattr(node, "lightmap", "") or ""),
                "bump_map": str(getattr(node, "bump_map", "") or ""),
                "texture_names": tuple(str(value) for value in (getattr(node, "texture_names", ()) or ())),
                "material_state": (
                    tuple(float(value) for value in getattr(node, "diffuse", ())),
                    tuple(float(value) for value in getattr(node, "ambient", ())),
                    tuple(float(value) for value in getattr(node, "specular", ())),
                    float(getattr(node, "shininess", 0.0)),
                    float(getattr(node, "alpha", 1.0)),
                    tuple(float(value) for value in getattr(node, "selfillum", ())),
                    bool(getattr(node, "has_shadow", False)),
                    bool(getattr(node, "render", False)),
                    bool(getattr(node, "has_lightmap", False)),
                    bool(getattr(node, "beaming", False)),
                    bool(getattr(node, "background_geometry", False)),
                    bool(getattr(node, "rotate_texture", False)),
                    int(getattr(node, "transparency_hint", 0)),
                    int(getattr(node, "tex_count", 1)),
                ),
                "uv_animation_state": (
                    bool(getattr(node, "animate_uv", False)),
                    float(getattr(node, "uv_dir_x", 0.0)),
                    float(getattr(node, "uv_dir_y", 0.0)),
                    float(getattr(node, "uv_jitter", 0.0)),
                    float(getattr(node, "uv_jitter_speed", 0.0)),
                ),
                "controllers": tuple(
                    _controller_inventory(controller)
                    for controller in (getattr(node, "controllers", ()) or ())
                ),
                "light_header_state": (
                    (
                        float(getattr(node, "light_flare_radius", 0.0) or 0.0),
                        int(getattr(node, "light_priority", 0) or 0),
                        bool(getattr(node, "light_ambient_only", False)),
                        int(getattr(node, "light_dynamic", 0) or 0),
                        bool(getattr(node, "light_affect_dynamic", False)),
                        bool(getattr(node, "light_shadow", False)),
                        bool(getattr(node, "light_flare", False)),
                        bool(getattr(node, "light_fading", False)),
                        _freeze_behavior_value(getattr(node, "light_flare_sizes", ()) or ()),
                        _freeze_behavior_value(getattr(node, "light_flare_positions", ()) or ()),
                        _freeze_behavior_value(getattr(node, "light_flare_color_shifts", ()) or ()),
                        _freeze_behavior_value(getattr(node, "light_flare_textures", ()) or ()),
                    )
                    if flags & int(NodeFlags.LIGHT)
                    else None
                ),
                "emitter_header_state": (
                    _freeze_behavior_value(getattr(node, "emitter_params", {}) or {})
                    if flags & int(NodeFlags.EMITTER)
                    else None
                ),
                "position": tuple(float(value) for value in (getattr(node, "position", None) or (0.0, 0.0, 0.0))),
                "rotation": tuple(float(value) for value in (getattr(node, "rotation", None) or (0.0, 0.0, 0.0, 1.0))),
            }
        )
    return rows


def _compare_node_inventories(
    source_rows: list[dict[str, Any]],
    output_rows: list[dict[str, Any]],
    *,
    renamed_root: tuple[str, str],
    tolerance: float = 1.0e-5,
) -> list[str]:
    """Blocking mismatches between the source-binary and output node lists."""

    mismatches: list[str] = []
    if len(source_rows) != len(output_rows):
        mismatches.append(
            f"non-AABB node count changed from {len(source_rows)} to {len(output_rows)}."
        )
        return mismatches
    source_root, output_root = renamed_root

    def canonical_name(name: str) -> str:
        return output_root if name.casefold() == source_root.casefold() else name

    for index, (before, after) in enumerate(zip(source_rows, output_rows)):
        label = f"node[{index}] {before['name']!r}"
        if canonical_name(before["name"]) != after["name"]:
            mismatches.append(f"{label}: name changed to {after['name']!r}.")
            continue
        if canonical_name(before["parent"]) != after["parent"]:
            mismatches.append(f"{label}: parent {before['parent']!r} -> {after['parent']!r}.")
        scalar_fields = (
            "kinds", "face_count", "vertex_count", "texture", "lightmap", "flags",
            "texture_raw", "lightmap_raw", "bump_map", "texture_names", "material_state",
            "uv_animation_state", "controllers", "light_header_state", "emitter_header_state",
        )
        payload_fields = (
            "faces", "vertices", "normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3",
            "face_uvs", "face_mats",
        )
        for field in scalar_fields:
            if before.get(field) != after.get(field):
                mismatches.append(f"{label}: {field} changed.")
        for field in payload_fields:
            if before.get(field) != after.get(field):
                mismatches.append(f"{label}: indexed {field} payload changed.")
        position_delta = max(
            abs(before["position"][axis] - after["position"][axis]) for axis in range(3)
        )
        if position_delta > tolerance:
            mismatches.append(f"{label}: position delta {position_delta:g} exceeds {tolerance:g}.")
        rotation_delta = _quaternion_delta(before["rotation"], after["rotation"])
        if rotation_delta > tolerance:
            mismatches.append(f"{label}: rotation delta {rotation_delta:g} exceeds {tolerance:g}.")
    return mismatches


def _build_embedded_aabb_node(room: str, wok: WOKData, parent: ModelNode) -> ModelNode:
    """Author the embedded AABB walkmesh node directly from the external WOK.

    Matches the verified vanilla shape: identity transform, render/shadow off,
    NULL bitmap, and vertex/face topology identical to the serialized WOK so
    the embedded/external agreement gate passes by construction.
    """

    node = ModelNode()
    node.name = f"{room}_wg"
    node.flags = int(NodeFlags.HEADER | NodeFlags.AABB)
    node.position = (0.0, 0.0, 0.0)
    node.rotation = (0.0, 0.0, 0.0, 1.0)
    node.texture = "NULL"
    node.lightmap = ""
    node.render = False
    node.has_shadow = False
    node.vertices = [tuple(float(value) for value in vertex) for vertex in wok.verts]
    node.faces = [(int(face.v1), int(face.v2), int(face.v3)) for face in wok.faces]
    node.face_mats = [int(face.surface) for face in wok.faces]
    node.controllers = []
    node.parent = parent
    parent.children.append(node)
    return node


def _replace_embedded_aabb_geometry(node: ModelNode, wok: WOKData) -> None:
    """Replace only AABB topology while retaining the source node contract.

    Legacy rooms already carry a named AABB node with source-authored transform
    controllers.  Keeping that node preserves its identity and controller bank;
    the writer rebuilds the invalid tree pointers from the authoritative WOK.
    """

    node.texture = "NULL"
    node.lightmap = ""
    node.render = False
    node.has_shadow = False
    node.vertices = [tuple(float(value) for value in vertex) for vertex in wok.verts]
    node.faces = [(int(face.v1), int(face.v2), int(face.v3)) for face in wok.faces]
    node.face_mats = [int(face.surface) for face in wok.faces]


def _compile_static_binary_room(
    *,
    room: str,
    source_mdl_path: Path,
    source_mdx_path: Path,
    output_dir: Path,
    visual_only: bool,
    external_wok_path: Path | None = None,
) -> dict[str, Any]:
    """Compile one raw-valid binary source room through Ghost Studio's K2 writer.

    MDLOps ASCII decompilation can silently drop real visual nodes (Gra802
    ``Cylinder01``: 176 faces, texture ``LKO_dor01``), so this route parses the
    source MDL/MDX binary directly and makes exact source parity blocking:
    node names/counts/order, hierarchy, per-node vertex/face counts, textures,
    lightmaps, bind transforms, controllers, and light/emitter headers must
    survive unchanged.  A source AABB node keeps its identity/controllers while
    its geometry and tree are rebuilt from the authoritative external WOK;
    visual-only partitions receive the retail no-AABB MDL plus the canonical
    136-byte empty WOK when that matches their source topology.
    """

    room = room.casefold()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_mdl_bytes = source_mdl_path.read_bytes()
    source_mdx_bytes = source_mdx_path.read_bytes()
    source_model = MDLBinaryParser(source_mdl_bytes, source_mdx_bytes).parse()
    if source_model is None or source_model.root_node is None:
        raise RuntimeError(f"{room} source binary MDL could not be semantically parsed.")
    source_geometry = _model_geometry_fingerprint(source_model)
    source_inventory = _node_inventory(source_model)
    source_controller_inventory = _model_controller_inventory(source_model)
    source_root_name = str(source_model.root_node.name or room)
    controller_preservation_audit = _audit_preserved_room_controllers(source_model)
    if not controller_preservation_audit["safe_to_preserve"]:
        raise RuntimeError(
            f"{room} source controller bank cannot be preserved safely: "
            f"{controller_preservation_audit['invalid_reasons'][:8]}"
        )

    model = MDLBinaryParser(source_mdl_bytes, source_mdx_bytes).parse()
    if model is None or model.root_node is None:
        raise RuntimeError(f"{room} source binary MDL failed its second parse.")

    parsed_controller_count = sum(
        len(getattr(node, "controllers", ()) or ()) for node in model.all_nodes()
    )
    if parsed_controller_count != int(controller_preservation_audit["controller_count"]):
        raise RuntimeError(
            f"{room} controller audit counted {controller_preservation_audit['controller_count']} "
            f"controller(s), but the promotion parse exposed {parsed_controller_count}."
        )
    source_aabb_nodes = [
        node
        for node in model.all_nodes()
        if int(getattr(node, "flags", 0)) & int(NodeFlags.AABB)
    ]
    if len(source_aabb_nodes) > 1:
        raise RuntimeError(f"{room} source contains {len(source_aabb_nodes)} AABB nodes; expected at most one.")
    for node in source_aabb_nodes:
        if getattr(node, "children", None):
            raise RuntimeError(f"{room} source AABB node {node.name!r} has children.")
    model.name = room
    model.root_node.name = room
    model.game_version = GameVersion.K2
    # The audit above rejects animation blocks, so this is an assertion of the
    # parsed source rather than destructive animation stripping.
    if model.animations:
        raise RuntimeError(f"{room} unexpectedly retained animation blocks after the controller audit.")

    if visual_only:
        removed_aabb_nodes: list[str] = []
        for node in source_aabb_nodes:
            parent = getattr(node, "parent", None)
            if parent is None:
                raise RuntimeError(f"{room} source AABB node {node.name!r} is the model root.")
            parent.children = [child for child in parent.children if child is not node]
            removed_aabb_nodes.append(str(node.name))
        prepared_wok = WOKData(name=room)
        external_wok_bytes = prepared_wok.to_bytes()
        preparation: dict[str, Any] = {
            "policy": "retail_k2_visual_only_partition",
            "compile_route": "ghoststudio_binary_mdl",
            "embedded_aabb_removed": removed_aabb_nodes,
            "preserved_controller_count": parsed_controller_count - sum(
                len(getattr(node, "controllers", ()) or ()) for node in source_aabb_nodes
            ),
            "controller_preservation_audit": controller_preservation_audit,
            "external_wok": "canonical empty 136-byte BWM",
        }
    else:
        if external_wok_path is None or not external_wok_path.is_file():
            raise FileNotFoundError(f"Playable room {room} requires an authoritative external WOK.")
        external_wok_bytes = external_wok_path.read_bytes()
        external_wok = WOKData.from_bytes(external_wok_bytes)
        if source_aabb_nodes:
            embedded_aabb = source_aabb_nodes[0]
            _replace_embedded_aabb_geometry(embedded_aabb, external_wok)
            embedded_aabb_policy = "source_node_identity_and_controllers_preserved"
        else:
            embedded_aabb = _build_embedded_aabb_node(room, external_wok, model.root_node)
            embedded_aabb_policy = "new_source_missing_aabb_node"
        preparation = {
            "policy": "binary_source_with_wok_derived_embedded_aabb",
            "compile_route": "ghoststudio_binary_mdl",
            "authoritative_external_wok": _artifact(external_wok_path),
            "embedded_aabb_node": str(embedded_aabb.name),
            "embedded_aabb_policy": embedded_aabb_policy,
            "preserved_controller_count": parsed_controller_count,
            "controller_preservation_audit": controller_preservation_audit,
            "embedded_aabb_faces": len(external_wok.faces),
            "embedded_aabb_vertices": len(external_wok.verts),
        }

    wok_audit = _wok_audit(room, external_wok_bytes)
    if visual_only:
        _fingerprint, empty_report = inspect_raw_wok_structure(
            room,
            external_wok_bytes,
            allow_empty_visual=True,
        )
        wok_audit["visual_only_validation"] = _validation_rows(empty_report)
        wok_audit["blocking"] = _is_blocking(wok_audit["visual_only_validation"])
        if len(external_wok_bytes) != 136:
            raise RuntimeError(f"{room} visual-only WOK is {len(external_wok_bytes)} bytes, expected 136.")
    if wok_audit["blocking"]:
        raise RuntimeError(f"{room} external WOK failed its structural contract.")

    prepared_controller_inventory = _model_controller_inventory(model)
    expected_controller_count = sum(
        len(getattr(node, "controllers", ()) or ()) for node in model.all_nodes()
    )
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    mdl_audit = _mdl_audit(
        room,
        mdl_bytes,
        mdx_bytes,
        allow_missing_aabb=visual_only,
    )
    if mdl_audit["blocking"]:
        raise RuntimeError(f"{room} K2 binary MDL failed vanilla-derived structural gates.")
    if int(mdl_audit["fingerprint"]["controller_count"]) != expected_controller_count:
        raise RuntimeError(
            f"{room} promoted MDL exposes {mdl_audit['fingerprint']['controller_count']} controller(s); "
            f"expected the preserved {expected_controller_count}."
        )

    binary_model = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
    if binary_model is None:
        raise RuntimeError(f"{room} promoted MDL/MDX failed semantic readback.")
    output_controller_inventory = _model_controller_inventory(binary_model)
    if output_controller_inventory != prepared_controller_inventory:
        raise RuntimeError(f"{room} K2 writer changed source controller entry/order/payload data.")
    binary_geometry = _model_geometry_fingerprint(binary_model)
    geometry_mismatches = {
        field: {"source_binary": source_geometry[field], "binary_readback": binary_geometry[field]}
        for field in VISUAL_COMPARISON_FIELDS
        if source_geometry[field] != binary_geometry[field]
    }
    visual_vertex_delta = {
        "source_binary": source_geometry["visual_vertex_count"],
        "binary_readback": binary_geometry["visual_vertex_count"],
    }
    if source_geometry["visual_vertex_count"] != binary_geometry["visual_vertex_count"]:
        geometry_mismatches["visual_vertex_count"] = visual_vertex_delta
    if geometry_mismatches:
        raise RuntimeError(f"{room} K2 writer changed source-binary geometry: {geometry_mismatches}")

    node_parity_mismatches = _compare_node_inventories(
        source_inventory,
        _node_inventory(binary_model),
        renamed_root=(source_root_name, room),
    )
    if node_parity_mismatches:
        raise RuntimeError(
            f"{room} binary route broke source node parity: {node_parity_mismatches[:8]}"
        )

    embedded_aabb_parity: dict[str, Any] = {"required": not visual_only}
    readback_aabb_nodes = [
        node
        for node in binary_model.all_nodes()
        if int(getattr(node, "flags", 0)) & int(NodeFlags.AABB)
    ]
    if visual_only:
        if readback_aabb_nodes:
            raise RuntimeError(f"{room} visual-only MDL unexpectedly contains an AABB node.")
    else:
        if len(readback_aabb_nodes) != 1:
            raise RuntimeError(f"{room} promoted MDL has {len(readback_aabb_nodes)} AABB nodes; expected 1.")
        aabb_node = readback_aabb_nodes[0]
        external_wok = WOKData.from_bytes(external_wok_bytes)
        wok_faces = [(int(face.v1), int(face.v2), int(face.v3)) for face in external_wok.faces]
        readback_faces = [tuple(int(index) for index in face) for face in aabb_node.faces]
        if readback_faces != wok_faces:
            raise RuntimeError(f"{room} embedded AABB face topology diverged from the external WOK.")
        if len(aabb_node.vertices) != len(external_wok.verts):
            raise RuntimeError(
                f"{room} embedded AABB has {len(aabb_node.vertices)} vertices; "
                f"external WOK has {len(external_wok.verts)}."
            )
        vertex_delta = max(
            (
                max(abs(float(a) - float(b)) for a, b in zip(av, bv))
                for av, bv in zip(aabb_node.vertices, external_wok.verts)
            ),
            default=0.0,
        )
        if vertex_delta > 1.0e-5:
            raise RuntimeError(
                f"{room} embedded/external WOK vertex delta {vertex_delta:g} exceeds 0.00001."
            )
        embedded_aabb_parity = {
            "required": True,
            "aabb_node_name": str(aabb_node.name),
            "face_count": len(readback_faces),
            "vertex_count": len(aabb_node.vertices),
            "max_indexed_vertex_delta": vertex_delta,
            "face_index_topology_matches": True,
        }

    mdl_path = output_dir / f"{room}.mdl"
    mdx_path = output_dir / f"{room}.mdx"
    wok_path = output_dir / f"{room}.wok"
    mdl_path.write_bytes(mdl_bytes)
    mdx_path.write_bytes(mdx_bytes)
    wok_path.write_bytes(external_wok_bytes)
    return {
        "room": room,
        "visual_only": visual_only,
        "compile_route": "ghoststudio_binary_mdl",
        "source_binary": {
            "mdl": _artifact(source_mdl_path),
            "mdx": _artifact(source_mdx_path),
        },
        "preparation": preparation,
        "prepared_geometry": source_geometry,
        "binary_geometry": binary_geometry,
        "binary_geometry_parity_mismatches": {},
        "source_node_parity": {
            "non_aabb_node_count": len(source_inventory),
            "exact_payload_fields": [
                "flags", "faces", "vertices", "normals", "tangents", "uvs", "uvs_lm", "uvs_2",
                "uvs_3", "face_uvs", "face_mats", "texture_raw", "lightmap_raw", "bump_map",
                "texture_names", "material_state", "uv_animation_state", "controllers",
                "light_header_state", "emitter_header_state",
            ],
            "bind_transform_tolerance": 1.0e-5,
            "exact_visual_geometry_material_texture_parity": True,
            "mismatches": [],
        },
        "controller_parity": {
            "source_node_count": len(source_controller_inventory),
            "prepared_controller_count": expected_controller_count,
            "binary_readback_controller_count": int(mdl_audit["fingerprint"]["controller_count"]),
            "exact_entry_order_metadata_times_values": True,
            "mismatches": [],
        },
        "embedded_aabb_parity": embedded_aabb_parity,
        "mdl_audit": mdl_audit,
        "wok_audit": wok_audit,
        "legacy_binary_comparison": {
            "available": True,
            "note": "The source binary itself is the parity oracle on this route.",
        },
        "outputs": {
            "mdl": _artifact(mdl_path),
            "mdx": _artifact(mdx_path),
            "wok": _artifact(wok_path),
        },
    }


def _filtered_lyt(source_path: Path, rooms: Sequence[str], destination: Path) -> dict[str, Any]:
    source = LYTLayout.from_text(source_path.read_text(encoding="latin-1", errors="replace"))
    wanted = tuple(room.casefold() for room in rooms)
    by_name = {str(room.model).casefold(): room for room in source.rooms}
    missing = [room for room in wanted if room not in by_name]
    if missing:
        raise RuntimeError(f"Source LYT is missing requested room rows: {missing}")
    layout = LYTLayout(
        rooms=[
            LYTRoom(room, float(by_name[room].x), float(by_name[room].y), float(by_name[room].z))
            for room in wanted
        ],
        doorhooks=[hook for hook in source.doorhooks if str(hook.room).casefold() in set(wanted)],
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(layout.to_text().encode("latin-1"))
    return {
        "source": _artifact(source_path),
        "output": _artifact(destination),
        "rooms": wanted,
        "positions": {
            room: [float(by_name[room].x), float(by_name[room].y), float(by_name[room].z)]
            for room in wanted
        },
        "excluded_source_rooms": sorted(set(by_name) - set(wanted)),
    }


def _write_505_star_vis(rooms: Sequence[str], destination: Path) -> dict[str, Any]:
    wanted = tuple(room.casefold() for room in rooms)
    collision_room = "505qgm_01a"
    if collision_room not in wanted:
        raise RuntimeError("505QGM centralized-collision VIS requires 505qgm_01a.")
    vis = VISData()
    vis.visibility = {
        room: ([target for target in wanted if target != room] if room == collision_room else [collision_room])
        for room in wanted
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(vis.to_text().encode("latin-1"))
    return {
        "output": _artifact(destination),
        "policy": "symmetric_collision_room_star",
        "rationale": (
            "01a owns the only playable WOK and sees every complementary visual partition; each visual-only "
            "partition links back to 01a for the engine's symmetric VIS contract. No unsupported visual-to-visual "
            "adjacency was invented."
        ),
        "visibility": vis.visibility,
    }


def _filtered_vis(source_path: Path, rooms: Sequence[str], destination: Path) -> dict[str, Any]:
    source = VISData.from_text(source_path.read_text(encoding="latin-1", errors="replace"))
    wanted = tuple(room.casefold() for room in rooms)
    missing_headers = [room for room in wanted if room not in source.visibility]
    if missing_headers:
        raise RuntimeError(f"Source VIS is missing retained room headers: {missing_headers}")
    vis = VISData()
    vis.visibility = {
        room: sorted(
            target.casefold()
            for target in source.visibility[room]
            if target.casefold() in wanted and target.casefold() != room
        )
        for room in wanted
    }
    for room in wanted:
        expected = set(wanted) - {room}
        if set(vis.visibility[room]) != expected:
            raise RuntimeError(
                f"Recovered KOQ202 VIS row {room} does not preserve all retained source links: "
                f"{sorted(vis.visibility[room])} vs {sorted(expected)}"
            )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(vis.to_text().encode("latin-1"))
    return {
        "source": _artifact(source_path),
        "output": _artifact(destination),
        "policy": "exact_source_links_trimmed_to_surviving_rooms",
        "visibility": vis.visibility,
    }


def _candidate_proofs(
    *,
    module: str,
    candidate_root: Path,
) -> dict[str, Any]:
    module_path = candidate_root / "Modules" / f"{module}.mod"
    kmap_path = candidate_root / "MapStudioProof" / f"{module}.kmap"
    proof = prove(module_path, "K2", K2_ROOT, kmap_path)
    proof_dict = asdict(proof)
    proof_report = candidate_root / "MapStudioProof" / f"{module}.mapstudio-roundtrip.json"
    proof_report.parent.mkdir(parents=True, exist_ok=True)
    proof_report.write_text(json.dumps(proof_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mod_audit = audit_mod(module_path, module=module, game="K2", roundtrip=True)
    kmap_audit = audit_kmap(kmap_path, module=module, game="K2", roundtrip=True)
    walkmesh_parity = compare_mod_kmap_walkmeshes(mod_audit, kmap_audit)
    audit_report = candidate_root / "MapStudioProof" / f"{module}.walkmesh-audit.json"
    audit_report.write_text(
        json.dumps(
            {"mod": mod_audit, "kmap": kmap_audit, "walkmesh_parity": walkmesh_parity},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "map_studio_roundtrip": proof_dict,
        "map_studio_roundtrip_report": _artifact(proof_report),
        "mod_walkmesh_audit": mod_audit,
        "kmap_walkmesh_audit": kmap_audit,
        "walkmesh_parity": walkmesh_parity,
        "walkmesh_audit_report": _artifact(audit_report),
        "ready_for_manual_k2_test": bool(
            proof.ok
            and mod_audit.get("audit_pass")
            and kmap_audit.get("audit_pass")
            and walkmesh_parity.get("all_match")
        ),
    }


def _generate_505_eight_room_candidate(module_root: Path, output_root: Path) -> dict[str, Any]:
    rooms = tuple(f"505qgm_01{suffix}" for suffix in ("a", "b", "c", "d", "e", "f", "h", "l"))
    visual_only_rooms = tuple(room for room in rooms if room != "505qgm_01a")
    ascii_root = module_root / "Q_SellOut" / "Extracted" / "Aqua" / "Aqua" / "LabFloor2" / "ASCII"
    legacy_root = module_root / "Q_SellOut" / "Extracted" / "505QGM" / "505QGM"
    source_candidate = module_root / "Converted" / "Candidates" / "505qgm" / "K2" / "Candidate"
    destination = output_root / "505qgm" / "K2" / "EightRoomCandidate"
    room_dir = destination / "Rooms"
    room_results = []
    for room in rooms:
        room_results.append(
            _compile_static_ascii_room(
                room=room,
                ascii_path=ascii_root / f"{room}.mdl",
                output_dir=room_dir,
                visual_only=room in visual_only_rooms,
                external_wok_path=(source_candidate / "Resources" / "505qgm_01a.wok")
                if room == "505qgm_01a"
                else None,
                legacy_binary_root=legacy_root,
            )
        )

    core_inputs = destination / "CoreInputs"
    lyt = _filtered_lyt(legacy_root / "505qgm.lyt", rooms, core_inputs / "505qgm.lyt")
    vis = _write_505_star_vis(rooms, core_inputs / "505qgm.vis")
    build = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref="505qgm",
            target_game="K2",
            repaired_rooms_dir=str(room_dir),
            output_dir=str(destination),
            source_mod=str(source_candidate / "Modules" / "505qgm.mod"),
            source_lyt=str(core_inputs / "505qgm.lyt"),
            source_vis=str(core_inputs / "505qgm.vis"),
            visual_only_room_resrefs=visual_only_rooms,
            regenerate_pth=True,
            wok_coordinate_space="module",
            overwrite=True,
        )
    )
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module="505qgm", candidate_root=destination)
    return {
        "module": "505qgm",
        "candidate_kind": "eight_visual_partitions_one_centralized_collision_room",
        "candidate_root": str(destination),
        "rooms": rooms,
        "visual_only_rooms": visual_only_rooms,
        "excluded_missing_rooms": tuple(lyt["excluded_source_rooms"]),
        "room_compiles": room_results,
        "lyt": lyt,
        "vis": vis,
        "module_build": build.to_dict(),
        "proofs": proofs,
        "retail_game_tested": False,
        "ready_for_manual_k2_test": bool(build.ok and proofs.get("ready_for_manual_k2_test")),
    }


def _generate_koq202_five_room_candidate(module_root: Path, output_root: Path) -> dict[str, Any]:
    rooms = tuple(f"koq202_01{suffix}" for suffix in ("a", "b", "c", "d", "g"))
    source_root = (
        module_root
        / "Q_SellOut"
        / "Extracted"
        / "Korr_Expand2"
        / "Korr_Expand2"
        / "InnerTemple"
    )
    source_candidate = module_root / "Converted" / "Candidates" / "koq202" / "K2" / "Candidate"
    generated_01d = output_root / "koq202" / "K2" / "koq202_01d-explicit-floor"
    destination = output_root / "koq202" / "K2" / "FiveRoomCandidate"
    room_dir = destination / "Rooms"
    room_dir.mkdir(parents=True, exist_ok=True)
    room_sources: dict[str, dict[str, Any]] = {}
    room_compiles: dict[str, dict[str, Any]] = {}
    for room in rooms:
        source_dir = generated_01d if room == "koq202_01d" else source_candidate / "Resources"
        source_paths = {restype: source_dir / f"{room}.{restype}" for restype in ("mdl", "mdx", "wok")}
        for source_path in source_paths.values():
            if not source_path.is_file():
                raise FileNotFoundError(f"Missing retained KOQ202 room resource: {source_path}")
        room_compile = _compile_static_binary_room(
            room=room,
            source_mdl_path=source_paths["mdl"],
            source_mdx_path=source_paths["mdx"],
            output_dir=room_dir,
            visual_only=False,
            external_wok_path=source_paths["wok"],
        )
        room_compiles[room] = room_compile
        room_sources[room] = {
            restype: {
                "source": _artifact(source_paths[restype]),
                "output": dict(room_compile["outputs"][restype]),
            }
            for restype in ("mdl", "mdx", "wok")
        }

    core_inputs = destination / "CoreInputs"
    source_lyt_path = source_root / "BIN" / "KOQ202.lyt"
    source_transition_rooms = tuple(_parse_lyt_rooms(source_lyt_path))
    lyt = _filtered_lyt(source_lyt_path, rooms, core_inputs / "koq202.lyt")
    vis = _filtered_vis(source_root / "BIN" / "KOQ202.vis", rooms, core_inputs / "koq202.vis")
    build = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref="koq202",
            target_game="K2",
            repaired_rooms_dir=str(room_dir),
            output_dir=str(destination),
            source_mod=str(source_candidate / "Modules" / "koq202.mod"),
            source_lyt=str(core_inputs / "koq202.lyt"),
            source_vis=str(core_inputs / "koq202.vis"),
            regenerate_pth=True,
            wok_coordinate_space="module",
            source_transition_room_resrefs=source_transition_rooms,
            overwrite=True,
        )
    )
    proof_overlay_sync: dict[str, dict[str, Any]] = {}
    if build.ok:
        # Map Studio deliberately indexes loose companion resources beside a
        # community MOD.  This candidate also keeps its pre-package ``Rooms``
        # worktree for review, so make that overlay byte-identical to the
        # workflow's repaired final WOKs before running the KMAP proof.  Without
        # this synchronization a loose stale WOK can outrank the correct MOD
        # resource and make the proof test the wrong transition table.
        for room in rooms:
            module_wok = destination / "Resources" / f"{room}.wok"
            overlay_wok = room_dir / f"{room}.wok"
            if not module_wok.is_file():
                raise FileNotFoundError(f"Module workflow did not stage final WOK: {module_wok}")
            module_wok_bytes = module_wok.read_bytes()
            overlay_wok.write_bytes(module_wok_bytes)
            room_sources[room]["wok"]["output"] = _artifact(overlay_wok)
            proof_overlay_sync[room] = {
                "module_resource": _artifact(module_wok),
                "loose_overlay": _artifact(overlay_wok),
                "byte_identical": module_wok_bytes == overlay_wok.read_bytes(),
            }
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module="koq202", candidate_root=destination)
    return {
        "module": "koq202",
        "candidate_kind": "five_surviving_collision_rooms",
        "candidate_root": str(destination),
        "rooms": rooms,
        "source_transition_room_resrefs": source_transition_rooms,
        "excluded_missing_rooms": tuple(lyt["excluded_source_rooms"]),
        "room_sources": room_sources,
        "room_compiles": room_compiles,
        "lyt": lyt,
        "vis": vis,
        "module_build": build.to_dict(),
        "proof_overlay_sync": proof_overlay_sync,
        "proofs": proofs,
        "retail_game_tested": False,
        "ready_for_manual_k2_test": bool(build.ok and proofs.get("ready_for_manual_k2_test")),
    }


def _write_readme(report: dict[str, Any], path: Path) -> None:
    koq = report["koq202_01d"]
    five = report["505qgm"]
    eight_room = report["505qgm_eight_room_candidate"]
    five_room = report["koq202_five_room_candidate"]
    lines = [
        "# Legacy room walkmesh candidates",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        "## Outcome",
        "",
        "- `505QGM`: no new partition WOKs were generated. The authoritative `505QGM_01a` WOK "
        "already spans and overlaps all eight surviving visual partitions at their shared LYT origin.",
        "- `KOQ202_01d`: one explicit-node structural candidate was generated from `Object428` only. "
        "It passed raw WOK and controller-free room compile gates, but room completeness and retail behavior "
        "are not proven.",
        "- `505QGM`: an eight-partition K2 candidate now uses 01a as the sole playable collision room and "
        "seven retail-style visual-only room triplets. 01m/01n remain explicitly excluded because their "
        "visual sources are absent.",
        "- `KOQ202`: a five-room K2 candidate now contains surviving 01a/01b/01c/01g plus the reviewed 01d "
        "floor candidate. 01e/01f/01h/01i/01j remain explicitly missing.",
        "",
        "## Structural summary",
        "",
        f"- 505QGM WOK: {five['authoritative_wok_audit']['fingerprint']['vertex_count']} vertices, "
        f"{five['authoritative_wok_audit']['fingerprint']['face_count']} faces, "
        f"{five['authoritative_wok_audit']['fingerprint']['closed_perimeter_count']} closed perimeter loops.",
        f"- KOQ202_01d WOK: {koq['wok_audit']['fingerprint']['vertex_count']} vertices, "
        f"{koq['wok_audit']['fingerprint']['face_count']} faces, "
        f"{koq['wok_audit']['fingerprint']['closed_perimeter_count']} closed perimeter loops.",
        f"- 505QGM eight-room candidate ready for manual K2 test: "
        f"`{eight_room['ready_for_manual_k2_test']}`.",
        f"- KOQ202 five-room candidate ready for manual K2 test: "
        f"`{five_room['ready_for_manual_k2_test']}`.",
        "",
        "## Proof boundary",
        "",
        "These are evidence and structural candidates only. They have not been installed into KOTOR 2. "
        "Only a manual retail warp plus movement, camera containment, seams, transitions, and AI pathing "
        "can promote them to game-proven status.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-root", type=Path, default=DEFAULT_MODULE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    module_root = args.module_root.expanduser().resolve()
    output_root = args.output_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    koq202_01d = _generate_koq202_01d(module_root, output_root)
    report = {
        "schema": "ghoststudio.legacy-room-walkmesh-candidates.v2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "module_root": str(module_root),
        "output_root": str(output_root),
        "canonical_artifacts_modified": False,
        "installed_into_game": False,
        "proof_scope": "source hashes, explicit selection, raw WOK/MDL structure, and round-trip only",
        "505qgm": _analyse_505(module_root),
        "koq202_01d": koq202_01d,
        "505qgm_eight_room_candidate": _generate_505_eight_room_candidate(module_root, output_root),
        "koq202_five_room_candidate": _generate_koq202_five_room_candidate(module_root, output_root),
    }
    manifest = output_root / "legacy_walkmesh_recovery_manifest.json"
    readme = output_root / "README.md"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_readme(report, readme)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "readme": str(readme),
                "505qgm_candidate_count": 1,
                "koq202_01d_structural_candidate": report["koq202_01d"]["trust"]["structural_candidate"],
                "505qgm_eight_room_ready_for_manual_k2": report["505qgm_eight_room_candidate"][
                    "ready_for_manual_k2_test"
                ],
                "koq202_five_room_ready_for_manual_k2": report["koq202_five_room_candidate"][
                    "ready_for_manual_k2_test"
                ],
                "retail_game_proven": False,
            },
            indent=2,
        )
    )
    return 0 if (
        report["koq202_01d"]["trust"]["structural_candidate"]
        and report["505qgm_eight_room_candidate"]["ready_for_manual_k2_test"]
        and report["koq202_five_room_candidate"]["ready_for_manual_k2_test"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
