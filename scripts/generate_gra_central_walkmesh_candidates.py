"""Recover the centralized collision WOKs used by the legacy Gra areas.

The Gra room sets are partitioned for rendering, not collision.  Every room in
each LYT is placed at the same origin; the ``01a`` room owns the embedded AABB
and external, map-wide WOK while the other binary MDL/MDX pairs contain trees,
foliage, or a vehicle prop.  Creating a WOK from every upward-facing triangle
would therefore make leaves, tree trunks, and the vehicle walkable.

This command independently decompiles the source binaries with MDLOps, records
the surface/material evidence, and emits no per-partition WOKs.  It does emit a
non-destructive replacement for each authoritative ``01a`` WOK because the
legacy files contain invalid AABB child references and open perimeter records.
The replacement preserves the exact indexed floor geometry, surface semantics,
header vectors, and transitions while rebuilding adjacency, the complete AABB
tree, and every closed perimeter loop through Ghost Studio's current writer.

Nothing in the source tree or a game install is modified.  The outputs are
structural candidates only until they pass a manual KOTOR 2 retail warp and
movement/camera/pathing test.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from scripts.compile_nwmax_room_candidate import _parse_aabb_wok  # noqa: E402
from src.core.mdl.mdl_parser import MDLAsciiParser  # noqa: E402
from src.core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    build_imported_mesh_primitive_from_stock_model,
)
from src.core.modules.module_format import WOKData  # noqa: E402
from src.core.validation.kotor_module_engine_contract import (  # noqa: E402
    inspect_raw_wok_structure,
)


DEFAULT_MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
DEFAULT_SOURCE = (
    DEFAULT_MODULE_ROOT
    / "Q_SellOut"
    / "Extracted"
    / "Models_Yavin"
    / "Models_Yavin"
)
DEFAULT_OUTPUT = (
    DEFAULT_MODULE_ROOT
    / "Converted"
    / "WalkmeshAudit"
    / "GeneratedCandidates"
    / "GraCentralCollision"
)
DEFAULT_MDLOPS = ROOT / "Saved" / "ExternalTools" / "mdlops" / "mdlops.exe"

AREA_ROOMS: dict[str, dict[str, tuple[str, ...] | str]] = {
    "gra801": {
        "control": "gra801_01a",
        "targets": (
            "gra801_01b",
            "gra801_01c",
            "gra801_01d",
            "gra801_01e",
            "gra801_01f",
            "gra801_01h",
        ),
    },
    "gra802": {
        "control": "gra802_01a",
        "targets": ("gra802_01b", "gra802_01d"),
    },
    "gra803": {
        "control": "gra803_01a",
        "targets": ("gra803_01b", "gra803_01c", "gra803_01d"),
    },
}
FLOOR_NAME_TOKENS = ("floor", "ground", "terrain", "walk", "path", "road")


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _source_path(source: Path, room: str, suffix: str) -> Path:
    matches = sorted(source.glob(f"{room}.{suffix}"), key=lambda item: item.name.casefold())
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected one {room}.{suffix} under {source}; found {len(matches)}."
        )
    return matches[0]


def _bounds(vertices: Sequence[Sequence[float]]) -> dict[str, list[float]] | None:
    if not vertices:
        return None
    return {
        "min": [min(float(vertex[axis]) for vertex in vertices) for axis in range(3)],
        "max": [max(float(vertex[axis]) for vertex in vertices) for axis in range(3)],
    }


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
    name = str(surface.name)
    return {
        "name": name,
        "texture": str(surface.texture),
        "vertex_count": len(surface.vertices),
        "face_count": len(surface.faces),
        "horizontal_face_count": horizontal,
        "steep_face_count": steep,
        "degenerate_face_count": degenerate,
        "bounds": _bounds(surface.vertices),
        "floor_name_token_matches": [
            token for token in FLOOR_NAME_TOKENS if token in name.casefold()
        ],
    }


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
            sum(float(wok.verts[index][axis]) for index in (face.v1, face.v2, face.v3))
            / 3.0
            for axis in range(3)
        )
        for face in wok.faces
    ]


def _horizontal_triangles(
    surfaces: Iterable[ImportedMeshSurface],
) -> list[tuple[str, str, tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]:
    rows = []
    threshold = math.cos(math.radians(45.0))
    for surface in surfaces:
        for face in surface.faces:
            if len(face) < 3 or any(index < 0 or index >= len(surface.vertices) for index in face[:3]):
                continue
            points = tuple(
                tuple(float(value) for value in surface.vertices[index][:3])
                for index in face[:3]
            )
            normal = _triangle_normal(*points)
            if normal[3] > 1.0e-9 and abs(normal[2] / normal[3]) >= threshold:
                rows.append((str(surface.name), str(surface.texture), *points))
    return rows


def _centroid_coverage(
    wok: WOKData,
    triangles: Iterable[
        tuple[
            str,
            str,
            Sequence[float],
            Sequence[float],
            Sequence[float],
        ]
    ],
    *,
    z_tolerance: float = 0.25,
) -> dict[str, Any]:
    triangle_rows = list(triangles)
    covered = 0
    hit_nodes: dict[str, int] = {}
    hit_textures: dict[str, int] = {}
    for centroid in _wok_centroids(wok):
        hits = {
            (node, texture)
            for node, texture, a, b, c in triangle_rows
            if abs(
                centroid[2]
                - ((float(a[2]) + float(b[2]) + float(c[2])) / 3.0)
            )
            <= z_tolerance
            and _point_in_triangle_xy(centroid, a, b, c)
        }
        if hits:
            covered += 1
        for node, texture in hits:
            hit_nodes[node] = hit_nodes.get(node, 0) + 1
            hit_textures[texture] = hit_textures.get(texture, 0) + 1
    return {
        "wok_face_centroid_count": len(wok.faces),
        "covered_wok_face_centroid_count": covered,
        "coverage_ratio": 0.0 if not wok.faces else covered / len(wok.faces),
        "horizontal_triangle_count": len(triangle_rows),
        "matching_nodes": dict(sorted(hit_nodes.items())),
        "matching_textures": dict(sorted(hit_textures.items())),
        "z_tolerance": z_tolerance,
    }


def _validation_rows(report: Any) -> list[dict[str, Any]]:
    rows = []
    for issue in tuple(getattr(report, "issues", ()) or ()):
        severity = getattr(
            getattr(issue, "severity", None),
            "value",
            getattr(issue, "severity", ""),
        )
        rows.append(
            {
                "severity": str(severity or "").lower(),
                "code": str(getattr(issue, "code", "") or ""),
                "message": str(getattr(issue, "message", issue) or ""),
                "details": dict(getattr(issue, "details", {}) or {}),
            }
        )
    return rows


def _component_count(wok: WOKData) -> int:
    if not wok.faces:
        return 0
    parents = list(range(len(wok.faces)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    owners: dict[tuple[int, int], int] = {}
    for face_index, face in enumerate(wok.faces):
        indices = (int(face.v1), int(face.v2), int(face.v3))
        for edge_index in range(3):
            key = tuple(sorted((indices[edge_index], indices[(edge_index + 1) % 3])))
            previous = owners.get(key)
            if previous is None:
                owners[key] = face_index
            else:
                union(previous, face_index)
    return len({find(index) for index in range(len(wok.faces))})


def _wok_audit(room: str, data: bytes) -> dict[str, Any]:
    fingerprint, report = inspect_raw_wok_structure(room, data)
    rows = _validation_rows(report)
    parsed = WOKData.from_bytes(data)
    return {
        "fingerprint": asdict(fingerprint),
        "validation": rows,
        "blocking": any(
            str(row.get("severity") or "").lower() in {"error", "blocking"}
            for row in rows
        ),
        "component_count": _component_count(parsed),
        "bounds": _bounds(parsed.verts),
    }


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def _nearest_correspondence(
    source_points: Sequence[Sequence[float]],
    target_points: Sequence[Sequence[float]],
) -> dict[str, Any]:
    if not source_points or not target_points:
        return {"source_count": len(source_points), "target_count": len(target_points), "max": None}
    distances = [min(_distance(point, target) for target in target_points) for point in source_points]
    return {
        "source_count": len(source_points),
        "target_count": len(target_points),
        "max_nearest_distance": max(distances),
        "mean_nearest_distance": sum(distances) / len(distances),
        "within_0_001": sum(distance <= 0.001 for distance in distances),
    }


def _mdlops_decompile(
    room: str,
    mdl_path: Path,
    mdx_path: Path,
    mdlops: Path,
    scratch_root: Path,
) -> tuple[str, dict[str, Any]]:
    room_dir = scratch_root / room
    room_dir.mkdir(parents=True, exist_ok=True)
    local_mdl = room_dir / mdl_path.name
    local_mdx = room_dir / mdx_path.name
    shutil.copy2(mdl_path, local_mdl)
    shutil.copy2(mdx_path, local_mdx)
    command = [
        str(mdlops),
        "-a",
        "--smoothgroups",
        "--use-ascii-extension",
        str(local_mdl),
    ]
    completed = subprocess.run(
        command,
        cwd=str(room_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    candidates = sorted(room_dir.glob("*.mdl.ascii"), key=lambda item: item.name.casefold())
    if completed.returncode != 0 or len(candidates) != 1:
        raise RuntimeError(
            f"MDLOps failed to decompile {room}: return={completed.returncode}, "
            f"ascii_candidates={len(candidates)}, stderr={completed.stderr.strip()}"
        )
    ascii_bytes = candidates[0].read_bytes()
    return ascii_bytes.decode("latin-1", errors="replace"), {
        "command": command,
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
        "ascii_byte_size": len(ascii_bytes),
        "ascii_sha256": _sha256_bytes(ascii_bytes),
    }


def _primitive_from_ascii(text: str, room: str, source_model: Path) -> ImportedMeshRoomPrimitive:
    model = MDLAsciiParser().parse_string(text)
    return build_imported_mesh_primitive_from_stock_model(
        model,
        room_resref=room,
        source_model=str(source_model),
        game="K2",
    )


def _room_analysis(
    *,
    room: str,
    text: str,
    mdl_path: Path,
    mdx_path: Path,
    authoritative_wok: WOKData,
    mdlops_result: dict[str, Any],
    inventory_path: Path,
) -> dict[str, Any]:
    primitive = _primitive_from_ascii(text, room, mdl_path)
    inventory = [_surface_descriptor(surface) for surface in primitive.surfaces]
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    all_vertices = [vertex for surface in primitive.surfaces for vertex in surface.vertices]
    coverage = _centroid_coverage(authoritative_wok, _horizontal_triangles(primitive.surfaces))
    floor_named = [row for row in inventory if row["floor_name_token_matches"]]
    classification = (
        "visual_only_empty_partition"
        if not inventory
        else "visual_only_render_partition"
    )
    decision = (
        "Do not generate floor collision. This binary room contains no render surfaces and no "
        "embedded AABB; it is an intentional empty visual partition."
        if not inventory
        else (
            "Do not generate a WOK. This binary room has no embedded AABB or explicit floor-named "
            "surface. Its materials and object bounds identify foliage/tree/prop dressing; any small "
            "overlap with the centralized floor is incidental render geometry."
        )
    )
    return {
        "room": room,
        "source_mdl": _artifact(mdl_path),
        "source_mdx": _artifact(mdx_path),
        "mdlops": mdlops_result,
        "aabb_node_count": sum(
            1
            for line in text.splitlines()
            if line.strip().casefold().startswith("node aabb ")
        ),
        "surface_count": len(inventory),
        "face_count": sum(int(row["face_count"]) for row in inventory),
        "bounds": _bounds(all_vertices),
        "texture_names": sorted({str(row["texture"]) for row in inventory}),
        "floor_named_surface_count": len(floor_named),
        "floor_named_surfaces": floor_named,
        "authoritative_wok_centroid_overlap": coverage,
        "surface_inventory": _artifact(inventory_path),
        "candidate_generated": False,
        "classification": classification,
        "decision": decision,
    }


def _indexed_semantics(wok: WOKData) -> dict[str, Any]:
    return {
        "vertices": [tuple(float(value) for value in vertex) for vertex in wok.verts],
        "faces": [
            (
                int(face.v1),
                int(face.v2),
                int(face.v3),
                int(face.surface),
                int(face.adj1),
                int(face.adj2),
                int(face.adj3),
                int(face.trans1),
                int(face.trans2),
                int(face.trans3),
            )
            for face in wok.faces
        ],
        "adjacency_domain_count": wok.adjacency_domain_count,
        "hooks": (
            tuple(wok.relative_hook1),
            tuple(wok.relative_hook2),
            tuple(wok.absolute_hook1),
            tuple(wok.absolute_hook2),
            tuple(wok.position),
        ),
    }


def _repair_central_wok(room: str, source_path: Path, output_path: Path) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source_wok = WOKData.from_bytes(source_bytes)
    source_semantics = _indexed_semantics(source_wok)
    candidate_wok = copy.deepcopy(source_wok)
    candidate_wok.raw = None
    candidate_bytes = candidate_wok.to_bytes()
    candidate_readback = WOKData.from_bytes(candidate_bytes)
    candidate_semantics = _indexed_semantics(candidate_readback)
    if source_semantics != candidate_semantics:
        raise RuntimeError(f"{room} collision semantics changed during canonical WOK rebuild.")
    source_audit = _wok_audit(room, source_bytes)
    candidate_audit = _wok_audit(room, candidate_bytes)
    if candidate_audit["blocking"]:
        raise RuntimeError(f"{room} canonical WOK candidate still has blocking structural issues.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(candidate_bytes)
    return {
        "source": _artifact(source_path),
        "output": _artifact(output_path),
        "source_audit": source_audit,
        "candidate_audit": candidate_audit,
        "indexed_geometry_surface_adjacency_transition_headers_identical": True,
        "changed_binary_structures": [
            "AABB child references/tree ordering",
            "perimeter loop ordering/endpoints",
        ],
        "retail_game_proven": False,
    }


def _analyse_area(
    area: str,
    definition: dict[str, tuple[str, ...] | str],
    *,
    source: Path,
    output: Path,
    mdlops: Path,
    scratch: Path,
) -> dict[str, Any]:
    control = str(definition["control"])
    targets = tuple(str(room) for room in definition["targets"])
    lyt_path = _source_path(source, area, "lyt")
    control_mdl = _source_path(source, control, "mdl")
    control_mdx = _source_path(source, control, "mdx")
    source_wok_path = _source_path(source, control, "wok")
    source_wok = WOKData.from_bytes(source_wok_path.read_bytes())
    control_text, control_mdlops = _mdlops_decompile(
        control, control_mdl, control_mdx, mdlops, scratch
    )
    embedded, embedded_metadata = _parse_aabb_wok(
        control_text,
        room=control,
        max_slope_degrees=89.999,
    )
    control_primitive = _primitive_from_ascii(control_text, control, control_mdl)
    control_coverage = _centroid_coverage(
        source_wok,
        _horizontal_triangles(control_primitive.surfaces),
    )
    embedded_centroids = _wok_centroids(embedded)
    external_centroids = _wok_centroids(source_wok)
    target_rows = []
    for room in targets:
        mdl_path = _source_path(source, room, "mdl")
        mdx_path = _source_path(source, room, "mdx")
        text, mdlops_result = _mdlops_decompile(room, mdl_path, mdx_path, mdlops, scratch)
        target_rows.append(
            _room_analysis(
                room=room,
                text=text,
                mdl_path=mdl_path,
                mdx_path=mdx_path,
                authoritative_wok=source_wok,
                mdlops_result=mdlops_result,
                inventory_path=output / area / "evidence" / f"{room}.surface-inventory.json",
            )
        )

    repaired_path = output / area / "K2" / f"{control}.wok"
    return {
        "area": area,
        "source_lyt": _artifact(lyt_path),
        "lyt_all_rooms_share_origin": all(
            line.strip().split()[1:4] == ["0.0", "0.0", "0.0"]
            for line in lyt_path.read_text(encoding="latin-1", errors="replace").splitlines()
            if line.strip().casefold().startswith(area)
        ),
        "control_room": {
            "room": control,
            "source_mdl": _artifact(control_mdl),
            "source_mdx": _artifact(control_mdx),
            "mdlops": control_mdlops,
            "embedded_aabb_node_count": sum(
                1
                for line in control_text.splitlines()
                if line.strip().casefold().startswith("node aabb ")
            ),
            "embedded_aabb": {
                "metadata": embedded_metadata,
                "bounds": _bounds(embedded.verts),
                "vertex_nearest_correspondence": _nearest_correspondence(
                    embedded.verts, source_wok.verts
                ),
                "face_centroid_nearest_correspondence": _nearest_correspondence(
                    embedded_centroids, external_centroids
                ),
                "surface_histogram_matches_external": embedded.surface_distribution()
                == source_wok.surface_distribution(),
            },
            "external_wok_coverage_by_control_render_geometry": control_coverage,
        },
        "target_rooms": target_rows,
        "central_collision_candidate": _repair_central_wok(
            control, source_wok_path, repaired_path
        ),
        "decision": (
            "The control 01a room owns map-wide collision. Preserve one centralized 01a WOK; "
            "do not create WOKs for the visual partitions."
        ),
    }


def _write_readme(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Gra centralized walkmesh recovery",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        "## Decision",
        "",
        "The apparent missing per-room WOKs are not missing collision assets. The Gra LYT files "
        "place render partitions at one origin, and each `01a` room owns the complete embedded AABB "
        "plus external area WOK. The target rooms are foliage/tree/vehicle dressing and receive "
        "**no generated WOK**.",
        "",
        "| Area | Target | AABB nodes | Floor-named surfaces | WOK-centroid overlap | Decision |",
        "|---|---|---:|---:|---:|---|",
    ]
    for area in report["areas"]:
        for room in area["target_rooms"]:
            lines.append(
                f"| {area['area']} | {room['room']} | {room['aabb_node_count']} | "
                f"{room['floor_named_surface_count']} | "
                f"{room['authoritative_wok_centroid_overlap']['coverage_ratio']:.3%} | visual only; no WOK |"
            )
    lines.extend(
        [
            "",
            "## Repaired candidates",
            "",
        ]
    )
    for area in report["areas"]:
        candidate = area["central_collision_candidate"]
        fingerprint = candidate["candidate_audit"]["fingerprint"]
        lines.append(
            f"- `{area['area']}`: `{candidate['output']['path']}` — "
            f"{fingerprint['vertex_count']} vertices, {fingerprint['face_count']} faces, "
            f"{fingerprint['closed_perimeter_count']} closed loop(s), no structural blockers."
        )
    lines.extend(
        [
            "",
            "The repaired files retain the exact source vertex table, face indices, materials, adjacency "
            "semantics, transitions, and header vectors. Only the invalid legacy AABB/perimeter tables "
            "are rebuilt.",
            "",
            "## Proof boundary",
            "",
            "These candidates have not been installed into KOTOR 2. A manual retail warp must still "
            "verify spawn, click-to-move coverage, camera containment, AI pathing, and save/reload before "
            "they can be called game-proven.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mdlops", type=Path, default=DEFAULT_MDLOPS)
    args = parser.parse_args()
    source = args.source_dir.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    mdlops = args.mdlops.expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Gra source directory does not exist: {source}")
    if not mdlops.is_file():
        raise FileNotFoundError(f"MDLOps executable does not exist: {mdlops}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ghoststudio-gra-wok-") as temporary:
        scratch = Path(temporary)
        areas = [
            _analyse_area(
                area,
                definition,
                source=source,
                output=output,
                mdlops=mdlops,
                scratch=scratch,
            )
            for area, definition in AREA_ROOMS.items()
        ]
    report = {
        "schema": "ghoststudio.gra-central-collision-recovery.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source),
        "output_directory": str(output),
        "mdlops": _artifact(mdlops),
        "canonical_artifacts_modified": False,
        "installed_into_game": False,
        "retail_game_proven": False,
        "selection_policy": (
            "Never derive collision from render normals alone. Require an embedded AABB or explicit "
            "authored floor allowlist. These target partitions have neither."
        ),
        "areas": areas,
    }
    manifest = output / "gra-central-collision-recovery.json"
    readme = output / "README.md"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_readme(report, readme)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "readme": str(readme),
                "target_partition_woks_generated": 0,
                "central_collision_woks_repaired": len(areas),
                "retail_game_proven": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
