"""Compile one static NWMax/KOTORMax room into a non-destructive game candidate.

The input remains untouched.  The script combines a render-model ASCII MDL with
an embedded AABB source, reduces that AABB to upward-facing floor geometry, and
then writes a controller-free K1 or K2 MDL/MDX pair through Ghost Studio's
vanilla-derived writer.  The repository-pinned MDLOps still reads/compiles the
prepared ASCII as an independent compatibility audit, but its output is not
promoted: MDLOps synthesizes transform controllers on static room nodes whereas
known-loadable vanilla rooms do not.  The external WOK is serialized through
Ghost Studio's BWM writer so its AABB, adjacency, perimeter, and header tables
are not silently discarded by a third-party round trip.

This is a structural-candidate workflow.  It does not claim retail game proof;
the output still needs an install/warp/movement test in the selected game.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from src.core.modules.module_format import WOKData, WOKFace
from src.core.geometry.model_data import GameVersion, NodeFlags
from src.core.mdl.mdl_parser import MDLAsciiParser, MDLBinaryParser
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.validation.kotor_module_engine_contract import (
    VANILLA_ROOM_BASELINES,
    inspect_raw_mdl_structure,
    inspect_raw_wok_structure,
)


_MODEL_TOKEN_COMMANDS = frozenset(
    {"newmodel", "beginmodelgeom", "endmodelgeom", "donemodel"}
)
_WALKABLE_SURFACES = frozenset({1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30})


def _normalise_resref(value: str) -> str:
    result = str(value or "").strip().lower()
    if "." in result:
        result = result.rsplit(".", 1)[0]
    if not result:
        raise ValueError("Room resref is empty.")
    if len(result) > 16:
        raise ValueError(f"Room resref {result!r} exceeds the 16-character Odyssey limit.")
    if not re.fullmatch(r"[a-z0-9_]+", result):
        raise ValueError(f"Room resref {result!r} contains unsupported characters.")
    return result


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_ascii(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:4] == b"\x00\x00\x00\x00":
        raise ValueError(f"Expected NWMax/KOTORMax ASCII MDL, received binary MDL: {path}")
    return raw.decode("latin-1", errors="replace")


def _model_name(text: str) -> str:
    for line in text.splitlines():
        tokens = line.strip().split()
        if len(tokens) >= 2 and tokens[0].lower() == "newmodel":
            return tokens[1]
    raise ValueError("ASCII MDL has no newmodel declaration.")


def _node_blocks(text: str, node_type: str | None = None) -> list[list[str]]:
    lines = text.splitlines()
    result: list[list[str]] = []
    index = 0
    while index < len(lines):
        tokens = lines[index].strip().split()
        if len(tokens) >= 3 and tokens[0].lower() == "node":
            start = index
            depth = 1
            index += 1
            while index < len(lines) and depth:
                nested = lines[index].strip().split()
                if len(nested) >= 3 and nested[0].lower() == "node":
                    depth += 1
                elif nested and nested[0].lower() == "endnode":
                    depth -= 1
                index += 1
            if depth:
                raise ValueError(f"Unterminated ASCII node block starting at line {start + 1}.")
            if node_type is None or tokens[1].lower() == node_type.lower():
                result.append(lines[start:index])
            continue
        index += 1
    return result


def _without_node_type(text: str, node_type: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        tokens = lines[index].strip().split()
        if (
            len(tokens) >= 3
            and tokens[0].lower() == "node"
            and tokens[1].lower() == node_type.lower()
        ):
            depth = 1
            index += 1
            while index < len(lines) and depth:
                nested = lines[index].strip().split()
                if len(nested) >= 3 and nested[0].lower() == "node":
                    depth += 1
                elif nested and nested[0].lower() == "endnode":
                    depth -= 1
                index += 1
            if depth:
                raise ValueError(f"Unterminated {node_type} node block.")
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output) + "\n"


def _parse_counted_rows(block: list[str], command: str) -> list[list[str]]:
    command = command.lower()
    for index, line in enumerate(block):
        tokens = line.strip().split()
        if len(tokens) >= 2 and tokens[0].lower() == command:
            count = int(tokens[1])
            rows = [block[row].strip().split() for row in range(index + 1, index + 1 + count)]
            if len(rows) != count or any(not row for row in rows):
                raise ValueError(f"Malformed {command} table in AABB node.")
            return rows
    raise ValueError(f"AABB node has no {command} table.")


def _orientation_is_identity(values: tuple[float, float, float, float]) -> bool:
    axis_length = math.sqrt(sum(value * value for value in values[:3]))
    return abs(float(values[3])) <= 1e-6 or axis_length <= 1e-6


def _node_transform_records(text: str) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for block in _node_blocks(text):
        header = block[0].strip().split()
        if len(header) < 3:
            continue
        record: dict[str, Any] = {
            "name": header[2],
            "parent": "NULL",
            "position": (0.0, 0.0, 0.0),
            "orientation": (1.0, 0.0, 0.0, 0.0),
        }
        for line in block[1:]:
            tokens = line.strip().split()
            if len(tokens) >= 2 and tokens[0].lower() == "parent":
                record["parent"] = tokens[1]
            elif len(tokens) >= 4 and tokens[0].lower() == "position":
                record["position"] = tuple(float(value) for value in tokens[1:4])
            elif len(tokens) >= 5 and tokens[0].lower() == "orientation":
                record["orientation"] = tuple(float(value) for value in tokens[1:5])
        records.setdefault(header[2].lower(), []).append(record)
    return records


def _require_identity_aabb_ancestors(text: str, aabb_block: list[str]) -> None:
    parent = "NULL"
    for line in aabb_block:
        tokens = line.strip().split()
        if len(tokens) >= 2 and tokens[0].lower() == "parent":
            parent = tokens[1]
            break
    records = _node_transform_records(text)
    visited: set[str] = set()
    while parent and parent.lower() != "null":
        key = parent.lower()
        if key in visited:
            raise ValueError(f"AABB parent chain contains a cycle at {parent!r}.")
        visited.add(key)
        matches = records.get(key, [])
        if len(matches) != 1:
            raise ValueError(
                f"AABB parent {parent!r} resolves to {len(matches)} ASCII nodes; "
                "walkmesh space is ambiguous."
            )
        record = matches[0]
        position = tuple(float(value) for value in record["position"])
        orientation = tuple(float(value) for value in record["orientation"])
        if any(abs(value) > 1e-6 for value in position) or not _orientation_is_identity(orientation):
            raise ValueError(
                f"AABB ancestor {record['name']!r} has a non-identity transform. "
                "Reset/bake the hierarchy in 3ds Max before compiling."
            )
        parent = str(record["parent"])


def _remove_stacked_nonwalk_surfaces(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
) -> tuple[list[tuple[int, int, int, int]], int]:
    """Drop ceiling-like non-walk components stacked over a walkable floor.

    Ambiguous stacked *walkable* layers are rejected instead of guessed. Ramps
    and connected multi-level floors remain one edge-connected component.
    """

    if len(faces) < 2:
        return faces, 0
    parents = list(range(len(faces)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    edge_owner: dict[tuple[int, int], int] = {}
    for face_index, (v1, v2, v3, _surface) in enumerate(faces):
        for edge in ((v1, v2), (v2, v3), (v3, v1)):
            key = tuple(sorted(edge))
            previous = edge_owner.get(key)
            if previous is None:
                edge_owner[key] = face_index
            else:
                union(previous, face_index)

    components: dict[int, list[int]] = {}
    for face_index in range(len(faces)):
        components.setdefault(find(face_index), []).append(face_index)
    descriptors: list[dict[str, Any]] = []
    for indices in components.values():
        used = {
            vertex
            for face_index in indices
            for vertex in faces[face_index][:3]
        }
        points = [vertices[index] for index in used]
        descriptors.append(
            {
                "indices": indices,
                "min_x": min(point[0] for point in points),
                "max_x": max(point[0] for point in points),
                "min_y": min(point[1] for point in points),
                "max_y": max(point[1] for point in points),
                "min_z": min(point[2] for point in points),
                "max_z": max(point[2] for point in points),
                "walkable": any(faces[index][3] in _WALKABLE_SURFACES for index in indices),
            }
        )

    rejected: set[int] = set()
    for lower in descriptors:
        if not lower["walkable"]:
            continue
        for upper in descriptors:
            if lower is upper or lower["max_z"] >= upper["min_z"] - 0.05:
                continue
            overlap_x = min(lower["max_x"], upper["max_x"]) - max(lower["min_x"], upper["min_x"])
            overlap_y = min(lower["max_y"], upper["max_y"]) - max(lower["min_y"], upper["min_y"])
            if overlap_x <= 1e-6 or overlap_y <= 1e-6:
                continue
            if upper["walkable"]:
                raise ValueError(
                    "AABB contains vertically stacked walkable floor components. "
                    "Select the intended floor layer in 3ds Max before compiling."
                )
            rejected.update(upper["indices"])
    return [face for index, face in enumerate(faces) if index not in rejected], len(rejected)


def _parse_aabb_wok(text: str, *, room: str, max_slope_degrees: float) -> tuple[WOKData, dict[str, Any]]:
    max_slope_degrees = float(max_slope_degrees)
    if not math.isfinite(max_slope_degrees) or not 0.0 <= max_slope_degrees < 90.0:
        raise ValueError("Maximum walkmesh slope must be finite and in the range [0, 90).")
    blocks = _node_blocks(text, "aabb")
    if len(blocks) != 1:
        raise ValueError(f"Expected exactly one AABB node, found {len(blocks)}.")
    block = blocks[0]
    _require_identity_aabb_ancestors(text, block)

    position = (0.0, 0.0, 0.0)
    orientation = (1.0, 0.0, 0.0, 0.0)
    for line in block:
        tokens = line.strip().split()
        if len(tokens) >= 4 and tokens[0].lower() == "position":
            position = tuple(float(value) for value in tokens[1:4])
        elif len(tokens) >= 5 and tokens[0].lower() == "orientation":
            orientation = tuple(float(value) for value in tokens[1:5])
    if not _orientation_is_identity(orientation):
        raise ValueError(
            "AABB node has a non-identity rotation. Reset its transform in 3ds Max/KOTORMax "
            "before compiling so the external WOK and embedded node use the same room space."
        )

    vertex_rows = _parse_counted_rows(block, "verts")
    face_rows = _parse_counted_rows(block, "faces")
    source_vertices = [
        (
            float(row[0]) + position[0],
            float(row[1]) + position[1],
            float(row[2]) + position[2],
        )
        for row in vertex_rows
    ]

    source_faces: list[tuple[int, int, int, int]] = []
    for row in face_rows:
        if len(row) < 3:
            raise ValueError("Malformed AABB face row.")
        indices = (int(row[0]), int(row[1]), int(row[2]))
        if any(index < 0 or index >= len(source_vertices) for index in indices):
            raise ValueError(f"AABB face references an out-of-range vertex: {indices!r}")
        surface = int(row[7]) if len(row) >= 8 else 1
        source_faces.append((*indices, surface))

    cos_threshold = math.cos(math.radians(max_slope_degrees))
    kept: list[tuple[int, int, int, int]] = []
    rejected_steep = 0
    rejected_degenerate = 0
    for v1, v2, v3, surface in source_faces:
        a, b, c = source_vertices[v1], source_vertices[v2], source_vertices[v3]
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length <= 1e-9:
            rejected_degenerate += 1
            continue
        if nz / length < cos_threshold:
            rejected_steep += 1
            continue
        kept.append((v1, v2, v3, surface))

    kept, rejected_stacked = _remove_stacked_nonwalk_surfaces(source_vertices, kept)
    if not kept:
        raise ValueError("AABB source contains no upward-facing floor triangles after filtering.")
    if not any(surface in _WALKABLE_SURFACES for *_indices, surface in kept):
        raise ValueError("Filtered AABB contains no walkable floor material.")

    used_indices = sorted({index for v1, v2, v3, _surface in kept for index in (v1, v2, v3)})
    remap = {source_index: output_index for output_index, source_index in enumerate(used_indices)}
    wok = WOKData(name=room)
    wok.verts = [source_vertices[index] for index in used_indices]
    wok.faces = [
        WOKFace(remap[v1], remap[v2], remap[v3], surface)
        for v1, v2, v3, surface in kept
    ]
    metadata = {
        "source_vertex_count": len(source_vertices),
        "source_face_count": len(source_faces),
        "floor_vertex_count": len(wok.verts),
        "floor_face_count": len(wok.faces),
        "rejected_steep_face_count": rejected_steep,
        "rejected_degenerate_face_count": rejected_degenerate,
        "rejected_stacked_face_count": rejected_stacked,
        "max_slope_degrees": float(max_slope_degrees),
        "material_histogram": {
            str(surface): sum(1 for face in wok.faces if int(face.surface) == surface)
            for surface in sorted({int(face.surface) for face in wok.faces})
        },
    }
    return wok, metadata


def _aabb_ascii_block(room: str, wok: WOKData) -> list[str]:
    lines = [
        f"node aabb {room}_wg",
        f"  parent {room}",
        "  position 0 0 0",
        "  orientation 1 0 0 0",
        "  render 0",
        "  shadow 0",
        "  bitmap NULL",
        f"  verts {len(wok.verts)}",
    ]
    lines.extend(
        f"    {float(vertex[0]):.9g} {float(vertex[1]):.9g} {float(vertex[2]):.9g}"
        for vertex in wok.verts
    )
    lines.append(f"  faces {len(wok.faces)}")
    lines.extend(
        "    "
        f"{int(face.v1)} {int(face.v2)} {int(face.v3)} 1 0 0 0 {int(face.surface)}"
        for face in wok.faces
    )
    lines.append("endnode")
    return lines


def _rename_model(text: str, room: str) -> str:
    old_name = _model_name(text)
    output: list[str] = []
    for line in text.splitlines():
        indentation = line[: len(line) - len(line.lstrip())]
        tokens = line.strip().split()
        if not tokens:
            output.append(line)
            continue
        command = tokens[0].lower()
        if command in _MODEL_TOKEN_COMMANDS and len(tokens) >= 2 and tokens[1].lower() == old_name.lower():
            tokens[1] = room
            output.append(indentation + " ".join(tokens))
        elif command == "setsupermodel" and len(tokens) >= 3 and tokens[1].lower() == old_name.lower():
            tokens[1] = room
            output.append(indentation + " ".join(tokens))
        elif command == "node" and len(tokens) >= 3 and tokens[2].lower() == old_name.lower():
            tokens[2] = room
            output.append(indentation + " ".join(tokens))
        elif command == "parent" and len(tokens) >= 2 and tokens[1].lower() == old_name.lower():
            tokens[1] = room
            output.append(indentation + " ".join(tokens))
        else:
            output.append(line)
    return "\n".join(output) + "\n"


def prepare_room_ascii(
    render_text: str,
    walkmesh_text: str | None,
    *,
    room: str,
    max_slope_degrees: float = 45.0,
) -> tuple[str, WOKData, dict[str, Any]]:
    """Return canonical room ASCII plus its floor-only external WOK."""

    render_blocks = _node_blocks(render_text, "trimesh")
    if not render_blocks:
        raise ValueError("Render ASCII contains no trimesh visual geometry.")
    if walkmesh_text is not None:
        explicit_aabbs = _node_blocks(walkmesh_text, "aabb")
        if len(explicit_aabbs) != 1:
            raise ValueError(
                "Explicit walkmesh ASCII must contain exactly one AABB node; "
                f"found {len(explicit_aabbs)}."
            )
        aabb_source = walkmesh_text
    else:
        aabb_source = render_text
    wok, walkmesh_metadata = _parse_aabb_wok(
        aabb_source,
        room=room,
        max_slope_degrees=max_slope_degrees,
    )
    renamed = _rename_model(_without_node_type(render_text, "aabb"), room)
    lines = renamed.splitlines()
    insert_at = next(
        (index for index, line in enumerate(lines) if line.strip().lower().startswith("endmodelgeom")),
        None,
    )
    if insert_at is None:
        raise ValueError("Render ASCII has no endmodelgeom declaration.")
    lines[insert_at:insert_at] = [*_aabb_ascii_block(room, wok), ""]
    prepared = "\n".join(lines) + "\n"
    metadata = {
        "render_trimesh_node_count": len(render_blocks),
        "source_model_name": _model_name(render_text),
        "room_resref": room,
        "walkmesh": walkmesh_metadata,
    }
    return prepared, wok, metadata


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


def _model_geometry_fingerprint(model: Any) -> dict[str, Any]:
    visual_nodes: list[Any] = []
    aabb_nodes: list[Any] = []
    for node in model.all_nodes():
        if int(getattr(node, "flags", 0)) & int(NodeFlags.AABB):
            aabb_nodes.append(node)
        elif getattr(node, "faces", None):
            visual_nodes.append(node)
    textures = {
        str(getattr(node, "texture", "") or "").strip().lower()
        for node in visual_nodes
        if str(getattr(node, "texture", "") or "").strip().lower()
        not in {"", "null", "none"}
    }
    aabb_vertices = [
        tuple(float(value) for value in vertex)
        for node in aabb_nodes
        for vertex in tuple(getattr(node, "vertices", ()) or ())
    ]
    aabb_bounds = None
    if aabb_vertices:
        aabb_bounds = {
            "min": [min(vertex[axis] for vertex in aabb_vertices) for axis in range(3)],
            "max": [max(vertex[axis] for vertex in aabb_vertices) for axis in range(3)],
        }
    return {
        "visual_mesh_node_count": len(visual_nodes),
        "visual_vertex_count": sum(len(node.vertices) for node in visual_nodes),
        "visual_face_count": sum(len(node.faces) for node in visual_nodes),
        "visual_texture_count": len(textures),
        "visual_textures": sorted(textures),
        "aabb_node_count": len(aabb_nodes),
        "aabb_vertex_count": sum(len(node.vertices) for node in aabb_nodes),
        "aabb_face_count": sum(len(node.faces) for node in aabb_nodes),
        "aabb_bounds": aabb_bounds,
    }


def _blocking(rows: Iterable[dict[str, Any]]) -> list[str]:
    return [
        f"{row.get('code')}: {row.get('message')}".strip(": ")
        for row in rows
        if str(row.get("severity") or "").lower() in {"error", "blocking"}
    ]


def _single_generated(directory: Path, patterns: tuple[str, ...], *, label: str) -> Path:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(directory.glob(pattern))
    unique = sorted(set(matches), key=lambda item: item.name.lower())
    if len(unique) != 1:
        names = ", ".join(item.name for item in unique) or "none"
        raise RuntimeError(f"MDLOps generated {len(unique)} {label} candidate(s): {names}.")
    return unique[0]


def _run_mdlops(executable: Path, ascii_path: Path, *, game: str) -> dict[str, Any]:
    command = [
        str(executable),
        "-k2" if game == "K2" else "-k1",
        "--weight",
        "area",
        ascii_path.name,
    ]
    completed = subprocess.run(
        command,
        cwd=str(ascii_path.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "command": command,
        "cwd": str(ascii_path.parent),
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
    }


def compile_candidate(args: argparse.Namespace) -> dict[str, Any]:
    room = _normalise_resref(args.room)
    game = str(args.game).strip().upper()
    if game not in {"K1", "K2"}:
        raise ValueError("Target game must be K1 or K2.")
    render_path = Path(args.render_ascii).expanduser().resolve()
    walkmesh_path = Path(args.walkmesh_ascii).expanduser().resolve() if args.walkmesh_ascii else None
    mdlops_path = Path(args.mdlops).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    if not render_path.is_file():
        raise FileNotFoundError(f"Render ASCII does not exist: {render_path}")
    if walkmesh_path is not None and not walkmesh_path.is_file():
        raise FileNotFoundError(f"Walkmesh ASCII does not exist: {walkmesh_path}")
    if not mdlops_path.is_file():
        raise FileNotFoundError(f"MDLOps executable does not exist: {mdlops_path}")

    outputs = {
        "mdl": output_dir / f"{room}.mdl",
        "mdx": output_dir / f"{room}.mdx",
        "wok": output_dir / f"{room}.wok",
        "ascii": output_dir / f"{room}.source-combined.mdl.ascii",
        "manifest": output_dir / f"{room}.{game.lower()}.nwmax-compile.json",
    }
    existed_before = {key: path.is_file() for key, path in outputs.items()}
    existing = [path for path in outputs.values() if path.exists()]
    if existing and not args.overwrite:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"Candidate output exists and overwrite is disabled: {names}")

    render_text = _read_ascii(render_path)
    walkmesh_text = _read_ascii(walkmesh_path) if walkmesh_path is not None else None
    prepared_ascii, wok, preparation = prepare_room_ascii(
        render_text,
        walkmesh_text,
        room=room,
        max_slope_degrees=float(args.max_slope_degrees),
    )
    wok_bytes = wok.to_bytes()

    result: dict[str, Any] = {
        "schema": "ghoststudio.nwmax-room-compile.v1",
        "ok": False,
        "code": "not_run",
        "room_resref": room,
        "target_game": game,
        "source_render_ascii": str(render_path),
        "source_walkmesh_ascii": str(walkmesh_path) if walkmesh_path else str(render_path),
        "source_hashes": {
            "render_ascii": _hash_file(render_path),
            "walkmesh_ascii": _hash_file(walkmesh_path) if walkmesh_path else _hash_file(render_path),
        },
        "prepared_ascii_sha256": _hash_bytes(prepared_ascii.encode("latin-1", errors="replace")),
        "preparation": preparation,
        "outputs": {key: str(path) for key, path in outputs.items()},
        "vanilla_reference_baselines": [
            dict(row) for row in VANILLA_ROOM_BASELINES if str(row.get("game")) == game
        ],
        "retail_game_tested": False,
        "warnings": [],
        "blocking_issues": [],
    }

    try:
        direct_wok_fingerprint, direct_wok_report = inspect_raw_wok_structure(room, wok_bytes)
        direct_wok_rows = _validation_rows(direct_wok_report)
        result["wok_fingerprint"] = asdict(direct_wok_fingerprint)
        result["wok_validation"] = direct_wok_rows
        result["blocking_issues"].extend(_blocking(direct_wok_rows))
        if result["blocking_issues"]:
            raise RuntimeError("Generated floor WOK failed structural validation.")

        model = MDLAsciiParser().parse_string(prepared_ascii)
        model.name = room
        model.game_version = GameVersion.K2 if game == "K2" else GameVersion.K1
        # Room recovery is a static-geometry operation.  Never carry animation
        # blocks or synthesize position/orientation controllers into the room.
        model.animations = []
        source_geometry = _model_geometry_fingerprint(model)
        result["prepared_geometry_fingerprint"] = source_geometry
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
        mdl_fingerprint, mdl_report = inspect_raw_mdl_structure(
            room,
            mdl_bytes,
            mdx_bytes,
            game=game,
        )
        mdl_rows = _validation_rows(mdl_report)
        result["mdl_fingerprint"] = asdict(mdl_fingerprint)
        result["mdl_validation"] = mdl_rows
        result["blocking_issues"].extend(_blocking(mdl_rows))
        if int(mdl_fingerprint.controller_count) != 0:
            result["blocking_issues"].append(
                "Promoted static room MDL contains transform controllers; vanilla room baseline requires zero."
            )
        if result["blocking_issues"]:
            raise RuntimeError("Controller-free room candidate failed vanilla-derived structural gates.")

        binary_model = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
        if binary_model is None:
            raise RuntimeError("Promoted binary MDL could not be semantically read back.")
        binary_geometry = _model_geometry_fingerprint(binary_model)
        result["binary_geometry_fingerprint"] = binary_geometry
        parity_fields = (
            "visual_mesh_node_count",
            "visual_vertex_count",
            "visual_face_count",
            "visual_texture_count",
            "visual_textures",
            "aabb_node_count",
            "aabb_vertex_count",
            "aabb_face_count",
        )
        geometry_mismatches = {
            field: {"prepared_ascii": source_geometry[field], "binary_readback": binary_geometry[field]}
            for field in parity_fields
            if source_geometry[field] != binary_geometry[field]
        }
        result["binary_geometry_parity_mismatches"] = geometry_mismatches
        if geometry_mismatches:
            raise RuntimeError(
                "Promoted binary MDL changed visual or embedded-AABB geometry during write/readback."
            )
        expected_wok_bounds = {
            "min": [min(vertex[axis] for vertex in wok.verts) for axis in range(3)],
            "max": [max(vertex[axis] for vertex in wok.verts) for axis in range(3)],
        }
        result["external_wok_bounds"] = expected_wok_bounds
        binary_bounds = binary_geometry.get("aabb_bounds")
        if binary_bounds is None or any(
            abs(float(binary_bounds[bound][axis]) - float(expected_wok_bounds[bound][axis])) > 1e-5
            for bound in ("min", "max")
            for axis in range(3)
        ):
            raise RuntimeError(
                "Embedded AABB bounds do not match the external floor WOK after binary readback."
            )

        with tempfile.TemporaryDirectory(prefix=f"ghoststudio-nwmax-{room}-{game.lower()}-") as raw_temp:
            scratch = Path(raw_temp)
            staged_ascii = scratch / f"{room}.mdl"
            staged_ascii.write_text(prepared_ascii, encoding="latin-1", newline="\n")
            command_log = _run_mdlops(mdlops_path, staged_ascii, game=game)
            result["mdlops"] = command_log
            if int(command_log["returncode"]) != 0:
                raise RuntimeError(
                    f"MDLOps failed with exit code {command_log['returncode']}: "
                    f"{str(command_log['stderr'] or command_log['stdout']).strip()}"
                )

            mdlops_mdl = _single_generated(
                scratch,
                (f"{room}-*-bin.mdl", f"{room}*-bin.mdl"),
                label="binary MDL",
            )
            mdlops_mdx = _single_generated(
                scratch,
                (f"{room}-*-bin.mdx", f"{room}*-bin.mdx"),
                label="binary MDX",
            )
            mdlops_mdl_fingerprint, mdlops_mdl_report = inspect_raw_mdl_structure(
                room,
                mdlops_mdl.read_bytes(),
                mdlops_mdx.read_bytes(),
                game=game,
            )
            result["mdlops_mdl_fingerprint"] = asdict(mdlops_mdl_fingerprint)
            mdlops_mdl_rows = _validation_rows(mdlops_mdl_report)
            result["mdlops_mdl_validation"] = mdlops_mdl_rows
            mdlops_mdl_blocking = _blocking(mdlops_mdl_rows)
            if mdlops_mdl_blocking:
                raise RuntimeError(
                    "Independent MDLOps MDL audit failed: " + "; ".join(mdlops_mdl_blocking)
                )
            if int(mdlops_mdl_fingerprint.controller_count) != 0:
                result["warnings"].append(
                    "MDLOps compatibility audit synthesized "
                    f"{int(mdlops_mdl_fingerprint.controller_count)} static transform controllers; "
                    "its MDL/MDX was audited but deliberately not promoted."
                )

            mdlops_woks = sorted(scratch.glob(f"{room}*-bin.wok"), key=lambda item: item.name.lower())
            if mdlops_woks:
                if len(mdlops_woks) != 1:
                    raise RuntimeError(
                        "MDLOps produced ambiguous WOK candidates: "
                        + ", ".join(path.name for path in mdlops_woks)
                    )
                independent_wok = mdlops_woks[0].read_bytes()
                independent_fingerprint, independent_report = inspect_raw_wok_structure(room, independent_wok)
                independent_rows = _validation_rows(independent_report)
                result["mdlops_wok_fingerprint"] = asdict(independent_fingerprint)
                result["mdlops_wok_validation"] = independent_rows
                independent_blocking = _blocking(independent_rows)
                if independent_blocking:
                    raise RuntimeError(
                        "Independent MDLOps WOK audit failed: " + "; ".join(independent_blocking)
                    )
                parity_fields = (
                    "vertex_count",
                    "face_count",
                    "walkable_face_count",
                    "material_histogram",
                )
                direct_dict = asdict(direct_wok_fingerprint)
                independent_dict = asdict(independent_fingerprint)
                mismatches = {
                    field: {"ghoststudio": direct_dict[field], "mdlops": independent_dict[field]}
                    for field in parity_fields
                    if direct_dict[field] != independent_dict[field]
                }
                result["mdlops_wok_parity_mismatches"] = mismatches
                if mismatches:
                    result["warnings"].append(
                        "Independent MDLOps WOK changed floor geometry or surface semantics; "
                        "the validated Ghost Studio WOK remains authoritative."
                    )
            else:
                result["warnings"].append(
                    "MDLOps did not emit a standalone WOK; the candidate uses the validated "
                    "Ghost Studio BWM serialization of the embedded AABB floor."
                )

            output_dir.mkdir(parents=True, exist_ok=True)
            outputs["mdl"].write_bytes(mdl_bytes)
            outputs["mdx"].write_bytes(mdx_bytes)
            outputs["wok"].write_bytes(wok_bytes)
            outputs["ascii"].write_text(prepared_ascii, encoding="latin-1", newline="\n")

        result["output_hashes"] = {
            key: _hash_file(path)
            for key, path in outputs.items()
            if key != "manifest" and path.is_file()
        }
        result["ok"] = True
        result["code"] = "structural_candidate_ready"
        result["message"] = (
            f"Built a vanilla-structurally accepted {game} room candidate for {room}; "
            "retail install/warp/movement proof remains required."
        )
    except Exception as exc:
        if not result["blocking_issues"]:
            result["blocking_issues"].append(str(exc))
        result["code"] = "compile_or_validation_failed"
        result["message"] = f"NWMax room candidate failed: {exc}"
        for key in ("mdl", "mdx", "wok", "ascii"):
            try:
                if not existed_before[key] and outputs[key].is_file():
                    outputs[key].unlink()
            except OSError:
                pass
    finally:
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs["manifest"].write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--room", required=True, help="Output room resref (16 characters maximum).")
    parser.add_argument("--game", choices=("K1", "K2"), required=True)
    parser.add_argument("--render-ascii", required=True, help="NWMax/KOTORMax visual ASCII MDL.")
    parser.add_argument(
        "--walkmesh-ascii",
        default="",
        help="Optional second ASCII MDL containing the authoritative AABB node.",
    )
    parser.add_argument(
        "--mdlops",
        default=str(ROOT / "Saved" / "ExternalTools" / "mdlops" / "mdlops.exe"),
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-slope-degrees", default=45.0, type=float)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = compile_candidate(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
