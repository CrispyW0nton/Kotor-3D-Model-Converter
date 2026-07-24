"""Retail-derived environment-kit collections for Map Studio.

Kotor.NET's Area Designer supplies the data idea: a kit is a collection of
typed geometry templates with local magnet sockets and compatibility classes.
Ghost Studio derives that metadata from installed K1/K2 LYTs and the existing
retail terrain-surface census. No game bytes are copied into the catalog.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any


ENVIRONMENT_KIT_SCHEMA = "ghostrigger.environment-kits/v1"
ENVIRONMENT_KIT_MIME_TYPE = "application/x-ghostrigger-map-environment-kit+json"
ENVIRONMENT_KIT_PAYLOAD_SCHEMA = "ghostrigger.map-environment-kit/v1"
_CATALOG_RELATIVE = Path("assets/map_studio/environment_kits/vanilla_kits.json")


def trim_environment_kit_connection_overlap(
    primitive: Any,
    *,
    portal_midpoint: tuple[float, float, float],
    outward_normal: tuple[float, float],
    epsilon: float = 0.002,
) -> Any:
    """Keep a snapped vanilla room on the far side of its shared portal plane.

    An exterior room is a broad piece of a retail level, not an isolated Lego
    wall.  Its source geometry often continues behind the LYT doorway and can
    therefore overlap an authored clearing even when its WOK portal is exactly
    snapped.  Trim the *connection side* from render geometry so the authored
    cave throat owns that visible volume.  The imported WOK is intentionally
    preserved: its raw-index edge at the threshold is the source of truth for
    the generated room-to-room transition.  This is a local-space operation:
    the caller supplies the already-rotated portal and the target wall's
    outward normal, while room translation remains unchanged.
    """

    try:
        from .authored_imported_mesh import ImportedMeshSurface
    except ImportError:  # pragma: no cover - supports the embedded package route.
        from core.modules.authored_imported_mesh import ImportedMeshSurface  # type: ignore

    ox, oy, _oz = (float(value) for value in tuple(portal_midpoint)[:3])
    nx, ny = (float(value) for value in tuple(outward_normal)[:2])
    normal_length = math.hypot(nx, ny)
    if normal_length <= 1.0e-8:
        raise ValueError("A connected environment room needs a non-zero outward portal normal.")
    nx, ny = nx / normal_length, ny / normal_length
    tolerance = max(0.0, float(epsilon))

    def distance(point: tuple[float, float, float]) -> float:
        return (float(point[0]) - ox) * nx + (float(point[1]) - oy) * ny

    def lerp(first: tuple[float, ...], second: tuple[float, ...], fraction: float) -> tuple[float, ...]:
        return tuple(float(a) + (float(b) - float(a)) * fraction for a, b in zip(first, second))

    def normalise(normal: tuple[float, ...]) -> tuple[float, float, float]:
        x, y, z = (float(normal[index]) if index < len(normal) else 0.0 for index in range(3))
        length = math.sqrt((x * x) + (y * y) + (z * z))
        return (x / length, y / length, z / length) if length > 1.0e-8 else (0.0, 0.0, 1.0)

    def clip_polygon(vertices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not vertices:
            return []
        clipped: list[dict[str, Any]] = []
        previous = vertices[-1]
        previous_distance = distance(previous["position"])
        previous_inside = previous_distance >= -tolerance
        for current in vertices:
            current_distance = distance(current["position"])
            current_inside = current_distance >= -tolerance
            if current_inside != previous_inside:
                denominator = previous_distance - current_distance
                fraction = 0.0 if abs(denominator) <= 1.0e-12 else previous_distance / denominator
                fraction = max(0.0, min(1.0, fraction))
                intersection: dict[str, Any] = {}
                for key, value in previous.items():
                    if key == "key":
                        continue
                    next_value = current.get(key, value)
                    intersection[key] = lerp(value, next_value, fraction)
                previous_key = previous.get("key")
                current_key = current.get("key")
                # A generated clip vertex belongs to the original raw-index
                # edge, not to its rounded coordinate.  Reusing this identity
                # is what keeps adjacent clipped WOK triangles adjacent while
                # still preserving intentional vanilla seams.
                if repr(previous_key) > repr(current_key):
                    previous_key, current_key = current_key, previous_key
                intersection["key"] = ("clip_edge", previous_key, current_key)
                intersection["position"] = tuple(float(value) for value in intersection["position"][:3])
                if "normal" in intersection:
                    intersection["normal"] = normalise(intersection["normal"])
                clipped.append(intersection)
            if current_inside:
                clipped.append(current)
            previous = current
            previous_distance = current_distance
            previous_inside = current_inside
        return clipped

    def triangle_area(first: tuple[float, float, float], second: tuple[float, float, float], third: tuple[float, float, float]) -> float:
        ux, uy, uz = (second[index] - first[index] for index in range(3))
        vx, vy, vz = (third[index] - first[index] for index in range(3))
        return math.sqrt(
            ((uy * vz) - (uz * vy)) ** 2
            + ((uz * vx) - (ux * vz)) ** 2
            + ((ux * vy) - (uy * vx)) ** 2
        ) * 0.5

    trimmed_surfaces: list[Any] = []
    original_render_faces = 0
    trimmed_render_faces = 0
    for surface in tuple(getattr(primitive, "surfaces", ()) or ()):
        source_vertices = tuple(getattr(surface, "vertices", ()) or ())
        source_uvs = tuple(getattr(surface, "uvs", ()) or ())
        source_normals = tuple(getattr(surface, "normals", ()) or ())
        source_uvs_lm = tuple(getattr(surface, "uvs_lm", ()) or ())
        has_uvs = len(source_uvs) == len(source_vertices)
        has_normals = len(source_normals) == len(source_vertices)
        has_uvs_lm = len(source_uvs_lm) == len(source_vertices)
        vertices: list[tuple[float, float, float]] = []
        uvs: list[tuple[float, float]] = []
        normals: list[tuple[float, float, float]] = []
        uvs_lm: list[tuple[float, float]] = []
        faces: list[tuple[int, int, int]] = []
        face_mats: list[int] = []
        for face_index, face in enumerate(tuple(getattr(surface, "faces", ()) or ())):
            try:
                indices = tuple(int(index) for index in face[:3])
                source = [
                    {
                        "key": ("render", int(index)),
                        "position": tuple(float(value) for value in source_vertices[index][:3]),
                        "uv": tuple(float(value) for value in source_uvs[index][:2]) if has_uvs else (0.0, 0.0),
                        "normal": tuple(float(value) for value in source_normals[index][:3]) if has_normals else (0.0, 0.0, 1.0),
                        "uv_lm": tuple(float(value) for value in source_uvs_lm[index][:2]) if has_uvs_lm else (0.0, 0.0),
                    }
                    for index in indices
                ]
            except (IndexError, TypeError, ValueError):
                continue
            original_render_faces += 1
            polygon = clip_polygon(source)
            for index in range(1, len(polygon) - 1):
                triangle = (polygon[0], polygon[index], polygon[index + 1])
                points = tuple(tuple(float(value) for value in vertex["position"][:3]) for vertex in triangle)
                if triangle_area(*points) <= 1.0e-10:
                    continue
                first_index = len(vertices)
                vertices.extend(points)
                if has_uvs:
                    uvs.extend(tuple(float(value) for value in vertex["uv"][:2]) for vertex in triangle)
                if has_normals:
                    normals.extend(normalise(vertex["normal"]) for vertex in triangle)
                if has_uvs_lm:
                    uvs_lm.extend(tuple(float(value) for value in vertex["uv_lm"][:2]) for vertex in triangle)
                faces.append((first_index, first_index + 1, first_index + 2))
                material_rows = tuple(getattr(surface, "face_mats", ()) or ())
                face_mats.append(int(material_rows[face_index]) if face_index < len(material_rows) else 0)
                trimmed_render_faces += 1
        if faces:
            trimmed_surfaces.append(
                replace(
                    surface,
                    vertices=tuple(vertices),
                    faces=tuple(faces),
                    face_mats=tuple(face_mats),
                    uvs=tuple(uvs) if has_uvs else (),
                    normals=tuple(normals) if has_normals else (),
                    uvs_lm=tuple(uvs_lm) if has_uvs_lm else (),
                )
            )

    wok = getattr(primitive, "wok", None)
    # Do not alter a retail WOK simply to cure a render overlap.  The stock
    # threshold's raw indexed edge is needed later when the automatic portal
    # compiler writes reciprocal transition records for the two authored rooms.
    preserved_wok_faces = len(tuple(getattr(wok, "faces", ()) or ()))
    preserved_wok_vertices = len(tuple(getattr(wok, "verts", ()) or ()))

    metadata = dict(getattr(primitive, "metadata", {}) or {})
    metadata["environment_kit_connection_trim"] = {
        "operation": "portal_half_space_trim",
        "portal_midpoint": [ox, oy, float(portal_midpoint[2])],
        "outward_normal": [nx, ny],
        "epsilon_m": tolerance,
        "render_faces_before": original_render_faces,
        "render_faces_after": trimmed_render_faces,
        "wok_faces_after": preserved_wok_faces,
        "wok_vertices_after": preserved_wok_vertices,
        "wok_shared_vertex_policy": "preserved-imported-raw-indices",
        "wok_visual_clip_excluded": True,
    }
    return replace(primitive, surfaces=tuple(trimmed_surfaces), wok=wok, metadata=metadata)


def seal_environment_kit_exterior_bounds(
    primitive: Any,
    *,
    portal_midpoint: tuple[float, float, float] | None = None,
    portal_width: float = 0.0,
    texture: str = "lka_mud02",
    bank_height: float = 7.5,
    bank_depth: float = 4.25,
) -> Any:
    """Add a continuous visual berm to an attached outdoor room's WOK edge.

    A single retail exterior render partition normally relies on neighbouring
    LYT partitions to hide its far perimeter.  Pulling only that partition
    into a custom map therefore exposes the world void even though its doorway
    and collision are valid.  The authored continuation follows the imported
    WOK's *raw-index* boundary edges, leaves the snapped doorway open, and is
    visual-only: the stock WOK remains the movement authority.

    This is deliberately a closure for a partial exterior tile, not a fake
    replacement for the source module.  A future full-cluster import can add
    its actual neighbouring tiles without needing to undo this seam-safe
    boundary contract.
    """

    try:
        from .authored_imported_mesh import ImportedMeshSurface
        from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface
    except ImportError:  # pragma: no cover - supports the embedded package route.
        from core.modules.authored_imported_mesh import ImportedMeshSurface  # type: ignore
        from core.modules.authored_walkmesh_surfaces import is_walkable_walkmesh_surface  # type: ignore

    wok = getattr(primitive, "wok", None)
    if wok is None or not tuple(getattr(wok, "faces", ()) or ()):
        return primitive
    height = max(2.5, float(bank_height))
    depth = max(1.0, float(bank_depth))
    portal = tuple(float(value) for value in tuple(portal_midpoint or ())[:3])
    has_portal = len(portal) == 3
    portal_radius = max(1.15, float(portal_width) * 0.70) if has_portal else 0.0

    edge_records: list[dict[str, Any]] = []
    outward_by_vertex: dict[int, list[float]] = {}
    sealed_edges = 0
    skipped_portal_edges = 0
    for face in tuple(getattr(wok, "faces", ()) or ()):
        if not is_walkable_walkmesh_surface(int(getattr(face, "surface", -1))):
            continue
        indices = (int(face.v1), int(face.v2), int(face.v3))
        adjacency = (int(face.adj1), int(face.adj2), int(face.adj3))
        try:
            triangle = tuple(tuple(float(value) for value in wok.verts[index][:3]) for index in indices)
        except (IndexError, TypeError, ValueError):
            continue
        centroid = tuple(sum(point[axis] for point in triangle) / 3.0 for axis in range(3))
        for edge_index, neighbour in enumerate(adjacency):
            if neighbour >= 0:
                continue
            first = triangle[edge_index]
            second = triangle[(edge_index + 1) % 3]
            midpoint = tuple((first[axis] + second[axis]) * 0.5 for axis in range(3))
            if has_portal and math.dist(midpoint, portal) <= portal_radius:
                skipped_portal_edges += 1
                continue
            dx = midpoint[0] - centroid[0]
            dy = midpoint[1] - centroid[1]
            lateral = math.hypot(dx, dy)
            if lateral <= 1.0e-7:
                continue
            outward = (dx / lateral, dy / lateral)
            for raw_index in (indices[edge_index], indices[(edge_index + 1) % 3]):
                bucket = outward_by_vertex.setdefault(raw_index, [0.0, 0.0, 0.0])
                bucket[0] += outward[0]
                bucket[1] += outward[1]
                bucket[2] += 1.0
            edge_records.append(
                {
                    "first_index": indices[edge_index],
                    "second_index": indices[(edge_index + 1) % 3],
                    "first": first,
                    "second": second,
                    "outward": outward,
                    "sealed_index": sealed_edges,
                }
            )
            sealed_edges += 1

    if not edge_records:
        return primitive
    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertex_cache: dict[tuple[int, int, str], int] = {}
    profile_rings = (
        (0.035, -0.045, 0.00),
        (0.30, 0.22, 0.18),
        (0.72, 0.56, 0.12),
        (1.00, 1.00, 0.05),
        (1.22, 0.96, 0.02),
    )

    def averaged_outward(raw_index: int, fallback: tuple[float, float]) -> tuple[float, float]:
        bucket = outward_by_vertex.get(raw_index)
        if not bucket:
            return fallback
        length = math.hypot(bucket[0], bucket[1])
        if length <= 1.0e-7:
            return fallback
        return (bucket[0] / length, bucket[1] / length)

    def shared_vertex(
        *,
        raw_index: int,
        source_position: tuple[float, float, float],
        ring_index: int,
        fallback_outward: tuple[float, float],
        u_value: float,
    ) -> int:
        uv_axis = "y" if abs(fallback_outward[0]) >= abs(fallback_outward[1]) else "x"
        key = (int(raw_index), int(ring_index), uv_axis)
        cached = vertex_cache.get(key)
        if cached is not None:
            return cached
        offset_factor, height_factor, settle = profile_rings[ring_index]
        outward = averaged_outward(raw_index, fallback_outward)
        tangent = (-outward[1], outward[0])
        wobble = math.sin((float(raw_index) * 12.9898) + (float(ring_index) * 78.233)) * depth * 0.035 * settle
        x = source_position[0] + outward[0] * depth * offset_factor + tangent[0] * wobble
        y = source_position[1] + outward[1] * depth * offset_factor + tangent[1] * wobble
        z = source_position[2] + height * height_factor
        if ring_index == 0:
            z -= 0.045
        index = len(vertices)
        vertices.append((x, y, z))
        normal_length = math.hypot(outward[0] * 0.78, outward[1] * 0.78, 0.62)
        normals.append((outward[0] * 0.78 / normal_length, outward[1] * 0.78 / normal_length, 0.62 / normal_length))
        uv_scale = 0.22
        if uv_axis == "y":
            u_coord = y * uv_scale
        else:
            u_coord = x * uv_scale
        uvs.append((u_coord, z * uv_scale))
        vertex_cache[key] = index
        return index

    for record in edge_records:
        first_index = int(record["first_index"])
        second_index = int(record["second_index"])
        first = tuple(float(value) for value in tuple(record["first"])[:3])
        second = tuple(float(value) for value in tuple(record["second"])[:3])
        fallback_outward = tuple(float(value) for value in tuple(record["outward"])[:2])
        edge_u = float(record["sealed_index"])
        for ring_index in range(len(profile_rings) - 1):
            lower_first = shared_vertex(
                raw_index=first_index,
                source_position=first,
                ring_index=ring_index,
                fallback_outward=fallback_outward,
                u_value=edge_u,
            )
            lower_second = shared_vertex(
                raw_index=second_index,
                source_position=second,
                ring_index=ring_index,
                fallback_outward=fallback_outward,
                u_value=edge_u + 1.0,
            )
            upper_second = shared_vertex(
                raw_index=second_index,
                source_position=second,
                ring_index=ring_index + 1,
                fallback_outward=fallback_outward,
                u_value=edge_u + 1.0,
            )
            upper_first = shared_vertex(
                raw_index=first_index,
                source_position=first,
                ring_index=ring_index + 1,
                fallback_outward=fallback_outward,
                u_value=edge_u,
            )
            # Both windings keep the mound opaque from the authored clearing
            # and from the attached stock room under KOTOR's culled materials.
            faces.append((lower_first, lower_second, upper_second))
            faces.append((lower_first, upper_second, upper_first))
            faces.append((lower_first, upper_second, lower_second))
            faces.append((lower_first, upper_first, upper_second))

        # Add a shallow upper cap so top-down editor and PIE views do not see
        # through the mound into the world void.  This stays render-only; the
        # stock WOK remains the movement authority.
        cap_inner_first = shared_vertex(
            raw_index=first_index,
            source_position=first,
            ring_index=len(profile_rings) - 2,
            fallback_outward=fallback_outward,
            u_value=edge_u,
        )
        cap_inner_second = shared_vertex(
            raw_index=second_index,
            source_position=second,
            ring_index=len(profile_rings) - 2,
            fallback_outward=fallback_outward,
            u_value=edge_u + 1.0,
        )
        cap_outer_second = shared_vertex(
            raw_index=second_index,
            source_position=second,
            ring_index=len(profile_rings) - 1,
            fallback_outward=fallback_outward,
            u_value=edge_u + 1.0,
        )
        cap_outer_first = shared_vertex(
            raw_index=first_index,
            source_position=first,
            ring_index=len(profile_rings) - 1,
            fallback_outward=fallback_outward,
            u_value=edge_u,
        )
        faces.append((cap_inner_first, cap_inner_second, cap_outer_second))
        faces.append((cap_inner_first, cap_outer_second, cap_outer_first))
        faces.append((cap_inner_first, cap_outer_second, cap_inner_second))
        faces.append((cap_inner_first, cap_outer_first, cap_outer_second))

    metadata = dict(getattr(primitive, "metadata", {}) or {})
    metadata["environment_kit_exterior_closure"] = {
        "operation": "organic_boundary_mound",
        "visual_only": True,
        "texture": str(texture or "lka_mud02").strip().lower(),
        "sealed_boundary_edges": sealed_edges,
        "skipped_portal_edges": skipped_portal_edges,
        "bank_height_m": height,
        "bank_depth_m": depth,
        "raw_index_topology": True,
        "shared_indexed_vertices": True,
        "profile_ring_count": len(profile_rings),
        "top_cap_faces": sealed_edges * 4,
        "uv_projection": "local_vertical_meter_projection",
    }
    closure = ImportedMeshSurface(
        name=f"{str(getattr(primitive, 'room_resref', 'room') or 'room')}_shadowlands_exterior_closure",
        texture=str(texture or "lka_mud02").strip().lower(),
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=(0,) * len(faces),
        uvs=tuple(uvs),
        normals=tuple(normals),
        texture_names=(str(texture or "lka_mud02").strip().lower(),),
        has_shadow=True,
        render=True,
    )
    return replace(primitive, surfaces=tuple(getattr(primitive, "surfaces", ()) or ()) + (closure,), metadata=metadata)


_K1_MODULE_WORLDS = (
    (1, 1, "Endar Spire"),
    (2, 11, "Taris"),
    (12, 12, "Ebon Hawk"),
    (13, 16, "Dantooine"),
    (17, 21, "Tatooine"),
    (22, 25, "Kashyyyk"),
    (26, 29, "Manaan"),
    (33, 39, "Korriban"),
    (40, 43, "Leviathan"),
    (44, 44, "Unknown World"),
    (45, 45, "Star Forge"),
    (50, 50, "Yavin Station"),
)

_K2_MODULE_WORLDS = {
    "ebo": "Ebon Hawk",
    "per": "Peragus",
    "har": "Harbinger",
    "tel": "Telos",
    "nar": "Nar Shaddaa",
    "dxn": "Dxun",
    "ond": "Onderon",
    "dan": "Dantooine",
    "kor": "Korriban",
    "dro": "Ravager",
    "nih": "Ravager",
    "mal": "Malachor V",
    "cor": "Coruscant",
    "trl": "Prologue",
}


def kotor_module_world_label(game: str, module_resref: str) -> str:
    """Return a user-facing planet/ship name for a vanilla module family."""

    target_game = str(game or "").strip().upper()
    module = str(module_resref or "").strip().lower()
    if not module:
        return "Vanilla KOTOR"
    if target_game == "K2":
        suffix = "".join(character for character in module if character.isalpha())[-3:]
        if suffix in _K2_MODULE_WORLDS:
            return _K2_MODULE_WORLDS[suffix]
        if module.startswith("000test") or module.startswith("999dia"):
            return "Development"
        return "KOTOR II"
    if module == "plcaa":
        return "Neutral Blockout"
    if "ebon" in module or module.startswith("stunt_ebo") or module.startswith("mgf_ebo"):
        return "Ebon Hawk"
    for token, label in (
        ("stunt_end", "Endar Spire"),
        ("stunt_lev", "Leviathan"),
        ("stunt_starforge", "Star Forge"),
        ("stunt_unk", "Unknown World"),
    ):
        if module.startswith(token):
            return label
    if module.startswith("m") and len(module) >= 3 and module[1:3].isdigit():
        number = int(module[1:3])
        for first, last, label in _K1_MODULE_WORLDS:
            if first <= number <= last:
                return label
    return "KOTOR I"


def environment_kit_collection_display_label(collection: "EnvironmentKitCollection") -> str:
    world = kotor_module_world_label(collection.game, collection.module_resref)
    kind = (
        "Dressing"
        if any(piece.role == "dressing" for piece in collection.pieces)
        else "Exterior"
        if collection.environment_kind == "exterior"
        else "Interior"
    )
    return f"{world} — {kind} · {collection.module_resref}"


def environment_kit_builder_style_id(game: str, module_resref: str, collection_id: str = "") -> str:
    """Map vanilla module collections onto the measured Pascal builder styles.

    A style is deliberately broader than one LYT collection: selecting Endar
    Spire should expose both ship sections plus the portable dressing shelf.
    """

    target_game = str(game or "").strip().upper()
    module = str(module_resref or "").strip().lower()
    collection = str(collection_id or "").strip().lower()
    if target_game == "K1" and (module in {"m01aa", "m01ab"} or collection.startswith("k1_endar_spire")):
        return "architecture:k1_endar_spire"
    if target_game == "K1" and (module in {"m02aa", "m02ad"} or collection.startswith("k1_taris_apartments")):
        return "architecture:k1_taris_apartments"
    if target_game == "K1" and (module in {"m24aa", "m25aa"} or collection.startswith("k1_shadowlands")):
        return "architecture:k1_shadowlands"
    if target_game == "K1" and (
        module in {"m37aa", "m38aa", "m38ab", "m39aa"}
        or collection.startswith(("k1_m37aa", "k1_m38aa", "k1_m38ab", "k1_m39aa", "k1_korriban_tombs"))
    ):
        return "architecture:k1_korriban_tombs"
    if target_game == "K1" and (
        module == "m34aa"
        or collection.startswith(("k1_m34aa", "k1_korriban_caves"))
    ):
        return "architecture:k1_korriban_caves"
    if target_game == "K2" and (
        module == "711kor"
        or collection.startswith(("k2_711kor", "k2_korriban_tombs"))
    ):
        return "architecture:k2_korriban_tombs"
    if target_game == "K2" and (
        module == "710kor"
        or collection.startswith(("k2_710kor", "k2_korriban_caves"))
    ):
        return "architecture:k2_korriban_caves"
    if target_game == "K2" and (module in {"151har", "152har", "153har", "154har"} or collection.startswith("k2_harbinger")):
        return "architecture:k2_harbinger"
    if target_game == "K2" and (
        module in {"201tel", "202tel", "203tel", "204tel", "207tel", "208tel", "209tel", "211tel", "220tel", "221tel", "222tel"}
        or collection.startswith(
            (
                "k2_201tel",
                "k2_202tel",
                "k2_203tel",
                "k2_204tel",
                "k2_207tel",
                "k2_208tel",
                "k2_209tel",
                "k2_211tel",
                "k2_220tel",
                "k2_221tel",
                "k2_222tel",
                "k2_telos_citadel",
            )
        )
    ):
        return "architecture:k2_telos_citadel"
    return f"kit:{collection}" if collection else ""


def environment_kit_builder_style_label(style_id: str) -> str:
    return {
        "architecture:k1_endar_spire": "Endar Spire — All Vanilla Rooms + Dressing",
        "architecture:k1_taris_apartments": "Taris Apartments — All Vanilla Rooms",
        "architecture:k1_shadowlands": "Shadowlands — Upper + Lower Clearings, Roots & Terrain",
        "architecture:k1_korriban_tombs": "K1 Korriban Tombs — Ajunta Pall, Marka Ragnos, Tulak Hord & Naga Sadow",
        "architecture:k1_korriban_caves": "K1 Shyrack Caves — All Corridors, Caverns & Webbed Passages",
        "architecture:k2_korriban_tombs": "K2 Secret Tomb — All Ruined Chambers & Corridors",
        "architecture:k2_korriban_caves": "K2 Shyrack Caves — All Corridors, Caverns & Webbed Passages",
        "architecture:k2_harbinger": "Harbinger — All Vanilla Rooms + Dressing",
        "architecture:k2_telos_citadel": "Telos Citadel Station — All Public, Residential & Entertainment Rooms + Dressing",
    }.get(str(style_id or "").strip().lower(), "Selected Building Style")


@dataclass(frozen=True)
class EnvironmentKitMagnet:
    magnet_id: str
    kind: str
    magnet_class: str
    local_position: tuple[float, float, float]
    local_orientation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    target_piece_id: str = ""
    source: str = "inferred"

    @property
    def yaw_radians(self) -> float:
        x, y, z, w = self.local_orientation
        return math.atan2(2.0 * ((w * z) + (x * y)), 1.0 - 2.0 * ((y * y) + (z * z)))

    @property
    def snap_facing_radians(self) -> float:
        """Return the useful horizontal facing for connection placement.

        Retail LYT door-hook rotations are not consistently represented as a
        conventional Z-yaw quaternion by the legacy readers.  The hook itself
        sits on the room perimeter, so its local radial direction is the more
        reliable Kotor.NET-style connection normal.  Tiny/origin hooks retain
        the quaternion fallback.
        """

        # WOK-derived cave portals have a measured outward normal.  Their
        # reusable room origin is an arbitrary LYT placement, so treating the
        # socket position as a radial vector can rotate a cave tile toward the
        # middle of its source module instead of through its actual passage.
        if str(self.source or "").startswith("wok_transition"):
            return self.yaw_radians
        x = float(self.local_position[0])
        y = float(self.local_position[1])
        if self.kind == "doorway" and math.hypot(x, y) >= 0.35:
            return math.atan2(y, x)
        return self.yaw_radians


@dataclass(frozen=True)
class EnvironmentKitPiece:
    piece_id: str
    collection_id: str
    label: str
    game: str
    module_resref: str
    room_resref: str
    role: str
    class_id: str
    model_resref: str
    terrain_asset_id: str = ""
    surface_index: int = -1
    texture_resref: str = ""
    lightmap_resref: str = ""
    source_bounds_m: tuple[float, float, float, float, float, float] = ()
    source_surface_names: tuple[str, ...] = ()
    anchor_mode: str = "floor"
    local_normal_axis: str = "y"
    backdrop_texture_resref: str = ""
    backdrop_axis: str = ""
    dimensions_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    triangle_count: int = 0
    magnets: tuple[EnvironmentKitMagnet, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvironmentKitCollection:
    collection_id: str
    label: str
    game: str
    module_resref: str
    environment_kind: str
    floor_texture: str = "ruler01"
    wall_texture: str = "ruler01"
    ceiling_texture: str = "ruler01"
    pieces: tuple[EnvironmentKitPiece, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def terrain_piece_count(self) -> int:
        return sum(piece.role == "terrain" for piece in self.pieces)

    @property
    def room_piece_count(self) -> int:
        return sum(piece.role in {"room_tile", "exterior_tile"} for piece in self.pieces)


@dataclass(frozen=True)
class EnvironmentKitSnapResult:
    position: tuple[float, float, float]
    yaw_radians: float
    source_magnet_id: str
    target_magnet_id: str
    target_piece_id: str
    target_room_resref: str = ""
    cursor_distance: float = 0.0
    target_is_authored_wall: bool = False
    target_edge_index: int = -1
    target_center_fraction: float = 0.5
    opening_width: float = 0.0
    opening_height: float = 0.0
    opening_bottom: float = 0.0


@dataclass(frozen=True)
class EnvironmentKitWallTarget:
    """One authored wall edge exposed as a live vanilla-room magnet target."""

    room_resref: str
    edge_index: int
    start: tuple[float, float]
    end: tuple[float, float]
    floor_z: float
    outward_yaw_radians: float
    opening_width: float
    opening_height: float
    opening_bottom: float = 0.0


def _candidate_roots() -> tuple[Path, ...]:
    roots = [Path.cwd(), Path(sys.executable).resolve().parent]
    try:
        roots.extend(Path(__file__).resolve().parents)
    except (OSError, RuntimeError):
        pass
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def environment_kit_catalog_path(*, writable: bool = False) -> Path:
    configured = str(os.environ.get("GHOSTRIGGER_ENVIRONMENT_KIT_CATALOG", "") or "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(root / _CATALOG_RELATIVE for root in _candidate_roots())
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "GhostStudio" / "cache" / "vanilla_environment_kits.json")
    if not writable:
        for candidate in candidates:
            if candidate.is_file():
                return candidate
    if local:
        return Path(local) / "GhostStudio" / "cache" / "vanilla_environment_kits.json"
    return Path.cwd() / _CATALOG_RELATIVE


def _magnet_from_payload(raw: object) -> EnvironmentKitMagnet:
    row = dict(raw or {})
    return EnvironmentKitMagnet(
        magnet_id=str(row.get("magnet_id") or "magnet"),
        kind=str(row.get("kind") or "edge"),
        magnet_class=str(row.get("magnet_class") or "generic"),
        local_position=tuple(float(value) for value in tuple(row.get("local_position") or (0, 0, 0))[:3]),
        local_orientation=tuple(float(value) for value in tuple(row.get("local_orientation") or (0, 0, 0, 1))[:4]),
        target_piece_id=str(row.get("target_piece_id") or ""),
        source=str(row.get("source") or "inferred"),
    )


def _piece_from_payload(raw: object) -> EnvironmentKitPiece:
    row = dict(raw or {})
    dimensions = tuple(float(value) for value in tuple(row.get("dimensions_m") or (0, 0, 0))[:3])
    source_bounds = tuple(float(value) for value in tuple(row.get("source_bounds_m") or ())[:6])
    magnet_rows = tuple(row.get("magnets") or ())
    magnets = tuple(_magnet_from_payload(value) for value in magnet_rows)
    if not magnets and str(row.get("magnet_profile") or "") == "bounds_4":
        magnets = _terrain_edge_magnets(dimensions)
    return EnvironmentKitPiece(
        piece_id=str(row.get("piece_id") or ""),
        collection_id=str(row.get("collection_id") or ""),
        label=str(row.get("label") or row.get("piece_id") or "Kit piece"),
        game=str(row.get("game") or "").upper(),
        module_resref=str(row.get("module_resref") or "").lower(),
        room_resref=str(row.get("room_resref") or "").lower(),
        role=str(row.get("role") or "generic"),
        class_id=str(row.get("class_id") or "generic"),
        model_resref=str(row.get("model_resref") or "").lower(),
        terrain_asset_id=str(row.get("terrain_asset_id") or ""),
        surface_index=int(row.get("surface_index", -1)),
        texture_resref=str(row.get("texture_resref") or "").lower(),
        lightmap_resref=str(row.get("lightmap_resref") or "").lower(),
        source_bounds_m=source_bounds if len(source_bounds) == 6 else (),
        source_surface_names=tuple(
            str(value).strip().lower()
            for value in tuple(row.get("source_surface_names") or ())
            if str(value).strip()
        ),
        anchor_mode=str(row.get("anchor_mode") or "floor").strip().lower(),
        local_normal_axis=str(row.get("local_normal_axis") or "y").strip().lower(),
        backdrop_texture_resref=str(row.get("backdrop_texture_resref") or "").strip().lower(),
        backdrop_axis=str(row.get("backdrop_axis") or "").strip().lower(),
        dimensions_m=dimensions,
        triangle_count=int(row.get("triangle_count") or 0),
        magnets=magnets,
        tags=tuple(str(value) for value in tuple(row.get("tags") or ())),
    )


def _republic_warship_dressing_collection(*, game: str) -> EnvironmentKitCollection:
    """Curated portable detail pieces clipped from measured vanilla rooms.

    Endar m01aa_01a and Harbinger 152har25 have the same 61-surface,
    4,802-triangle room topology.  Keeping the clip recipes data-only lets the
    user's own installation supply the model and texture bytes while both
    games expose the same useful Republic-warship dressing vocabulary.
    """

    tag = str(game or "K1").upper()
    is_k2 = tag == "K2"
    module = "152har" if is_k2 else "m01aa"
    room = "152har25" if is_k2 else "m01aa_01a"
    prefix = "k2_harbinger" if is_k2 else "k1_endar_spire"
    collection_id = f"{prefix}_dressing"
    source_tags = (
        tag.lower(),
        "harbinger" if is_k2 else "endar spire",
        "republic warship",
        "vanilla-derived",
        "dressing",
    )

    def piece(
        suffix: str,
        label: str,
        class_name: str,
        bounds: tuple[float, float, float, float, float, float],
        surface_names: tuple[str, ...],
        dimensions: tuple[float, float, float],
        *,
        anchor_mode: str,
        local_normal_axis: str = "y",
        backdrop: str = "",
        backdrop_axis: str = "",
        extra_tags: tuple[str, ...] = (),
    ) -> EnvironmentKitPiece:
        return EnvironmentKitPiece(
            piece_id=f"{prefix}_dressing_{suffix}",
            collection_id=collection_id,
            label=label,
            game=tag,
            module_resref=module,
            room_resref=room,
            role="dressing",
            class_id=f"dressing:{class_name}",
            model_resref=room,
            source_bounds_m=bounds,
            source_surface_names=surface_names,
            anchor_mode=anchor_mode,
            local_normal_axis=local_normal_axis,
            backdrop_texture_resref=backdrop,
            backdrop_axis=backdrop_axis,
            dimensions_m=dimensions,
            tags=source_tags + extra_tags,
        )

    name = "Harbinger" if is_k2 else "Endar Spire"
    # The command bank is the low, broad Loft27/Object5017/Object76 assembly.
    # The previous Object52 clip was a tall wall bay and produced two oversized
    # white slabs when dropped inside an authored room.
    console_bounds = (-3.02, 1.69, -1.28, 2.48, 3.94, -0.31)
    console_surfaces = (
        ("object5490", "object5491", "mesh422")
        if is_k2
        else ("loft27", "object5017", "object76")
    )
    wall_control_bounds = (0.72, 8.18, -0.36, 1.50, 8.36, 0.26) if is_k2 else (-1.50, 8.18, -0.36, -0.72, 8.36, 0.26)
    wall_control_surfaces = ("object5480",) if is_k2 else ("object10",)
    port_bounds = (4.68, 4.82, 0.50, 6.85, 6.62, 2.08) if is_k2 else (-6.85, 4.82, 0.50, -4.68, 6.62, 2.08)
    port_surfaces = ("object5492", "win_side02") if is_k2 else ("object3224", "win_side")
    light_bounds = (0.10, -6.43, -0.42, 0.46, -6.30, 0.98) if is_k2 else (-0.46, -6.43, -0.42, -0.10, -6.30, 0.98)
    light_surfaces = ("object5479",) if is_k2 else ("object09",)
    pieces = (
        piece(
            "bridge_console",
            f"{name} Bridge Command Console Bank",
            "bridge_console",
            console_bounds,
            console_surfaces,
            (5.51, 2.25, 0.97),
            anchor_mode="floor",
            local_normal_axis="y",
            extra_tags=("computer", "console", "bridge", "command"),
        ),
        piece(
            "wall_control",
            f"{name} Wall Control Panel",
            "wall_control",
            wall_control_bounds,
            wall_control_surfaces,
            (0.78, 0.18, 0.62),
            anchor_mode="wall",
            local_normal_axis="y",
            extra_tags=("computer", "control", "panel", "wall decor"),
        ),
        piece(
            "observation_port",
            f"{name} Observation Port",
            "observation_port",
            port_bounds,
            port_surfaces,
            (2.17, 1.80, 1.58),
            anchor_mode="wall",
            local_normal_axis="x",
            backdrop="" if is_k2 else "lhr_space01",
            backdrop_axis="x",
            extra_tags=("window", "port", "space", "starfield", "wall decor"),
        ),
        piece(
            "vertical_light",
            f"{name} Vertical Light Strip",
            "wall_light",
            light_bounds,
            light_surfaces,
            (0.36, 0.13, 1.40),
            anchor_mode="wall",
            local_normal_axis="y",
            extra_tags=("light", "luminaire", "wall decor"),
        ),
    )
    return EnvironmentKitCollection(
        collection_id=collection_id,
        label=f"{name} — Dressing",
        game=tag,
        module_resref=module,
        environment_kind="interior",
        floor_texture="har_fl01" if is_k2 else "lhr_flr01",
        wall_texture="har_wl07" if is_k2 else "lhr_wall01",
        ceiling_texture="har_tc01" if is_k2 else "lhr_tech01",
        pieces=pieces,
        tags=source_tags + ("portable", "content-browser"),
    )


def _korriban_dressing_collection(*, game: str, family: str) -> EnvironmentKitCollection:
    """Curated tomb and cave vocabulary clipped from installed Korriban rooms.

    The recipes identify retail surface names and bounds only.  Geometry,
    textures, and lightmaps still come from the user's own K1/K2 installation.
    """

    tag = str(game or "K1").upper()
    family_id = str(family or "tombs").strip().lower()
    is_k2 = tag == "K2"
    if family_id not in {"tombs", "caves"}:
        raise ValueError(f"Unsupported Korriban dressing family {family!r}.")
    if family_id == "caves":
        module = "710kor" if is_k2 else "m34aa"
        room = "710korb" if is_k2 else "m34aa_01a"
        prefix = f"{tag.lower()}_korriban_caves"
        cliff_texture = "kor_cliff01" if is_k2 else "lko_cliff01"
        pieces = (
            EnvironmentKitPiece(
                piece_id=f"{prefix}_cliff_outcrop",
                collection_id=f"{prefix}_dressing",
                label=f"{tag} Shyrack Cave Cliff Outcrop",
                game=tag,
                module_resref=module,
                room_resref=room,
                role="dressing",
                class_id="dressing:cave_cliff",
                model_resref=room,
                source_bounds_m=(2.777, -58.234, -4.403, 15.721, -40.359, 0.402),
                source_surface_names=("m34aa_mesh023",),
                anchor_mode="floor",
                dimensions_m=(12.944, 17.875, 4.805),
                texture_resref=cliff_texture,
                tags=(tag.lower(), "korriban", "shyrack cave", "rock", "cliff", "vanilla-derived"),
            ),
            EnvironmentKitPiece(
                piece_id=f"{prefix}_web_cluster",
                collection_id=f"{prefix}_dressing",
                label=f"{tag} Shyrack Web Cluster",
                game=tag,
                module_resref=module,
                room_resref=room,
                role="dressing",
                class_id="dressing:cave_web",
                model_resref=room,
                source_bounds_m=(24.867, -66.603, -1.673, 28.489, -65.226, 0.383),
                source_surface_names=("object14", "object15"),
                anchor_mode="wall",
                local_normal_axis="y",
                dimensions_m=(3.622, 1.377, 2.056),
                texture_resref="kor_web" if is_k2 else "lko_web",
                tags=(tag.lower(), "korriban", "shyrack cave", "web", "organic", "vanilla-derived"),
            ),
            EnvironmentKitPiece(
                piece_id=f"{prefix}_water_pool",
                collection_id=f"{prefix}_dressing",
                label=f"{tag} Shyrack Shallow Water Pool",
                game=tag,
                module_resref=module,
                room_resref=room,
                role="dressing",
                class_id="dressing:cave_water",
                model_resref=room,
                source_bounds_m=(4.633, -44.683, -4.913, 8.423, -38.672, -4.913),
                source_surface_names=("plane05",),
                anchor_mode="floor",
                dimensions_m=(3.790, 6.011, 0.02),
                texture_resref="kor_water01" if is_k2 else "lko_water01",
                tags=(tag.lower(), "korriban", "shyrack cave", "water", "pool", "vanilla-derived"),
            ),
        )
        if not is_k2:
            pieces += (
                EnvironmentKitPiece(
                    piece_id=f"{prefix}_rock_ridge",
                    collection_id=f"{prefix}_dressing",
                    label="K1 Shyrack Cave Long Rock Ridge",
                    game=tag,
                    module_resref="m34aa",
                    room_resref="m34aa_05a",
                    role="dressing",
                    class_id="dressing:cave_rock_ridge",
                    model_resref="m34aa_05a",
                    source_bounds_m=(91.945, -84.265, -7.072, 106.089, -77.413, -4.961),
                    source_surface_names=("m34aa_mesh091",),
                    anchor_mode="floor",
                    dimensions_m=(14.144, 6.852, 2.111),
                    texture_resref="lko_rock5",
                    tags=("k1", "korriban", "shyrack cave", "rock", "ridge", "terrain form", "vanilla-derived"),
                ),
                EnvironmentKitPiece(
                    piece_id=f"{prefix}_rock_shelf",
                    collection_id=f"{prefix}_dressing",
                    label="K1 Shyrack Cave Layered Rock Shelf",
                    game=tag,
                    module_resref="m34aa",
                    room_resref="m34aa_06a",
                    role="dressing",
                    class_id="dressing:cave_rock_shelf",
                    model_resref="m34aa_06a",
                    source_bounds_m=(88.790, -83.373, -7.005, 102.332, -78.092, -4.960),
                    source_surface_names=("m34aa_mesh226",),
                    anchor_mode="floor",
                    dimensions_m=(13.542, 5.281, 2.045),
                    texture_resref="lko_rock5",
                    tags=("k1", "korriban", "shyrack cave", "rock", "shelf", "terrain form", "vanilla-derived"),
                ),
                EnvironmentKitPiece(
                    piece_id=f"{prefix}_web_curtain",
                    collection_id=f"{prefix}_dressing",
                    label="K1 Shyrack Cave Hanging Web Curtain",
                    game=tag,
                    module_resref="m34aa",
                    room_resref="m34aa_07b",
                    role="dressing",
                    class_id="dressing:cave_web_curtain",
                    model_resref="m34aa_07b",
                    source_bounds_m=(-14.298, -103.560, -0.422, -12.005, -97.435, 4.086),
                    source_surface_names=("mesh27",),
                    anchor_mode="wall",
                    local_normal_axis="x",
                    dimensions_m=(2.293, 6.125, 4.508),
                    texture_resref="lko_web",
                    tags=("k1", "korriban", "shyrack cave", "web", "curtain", "wall dressing", "vanilla-derived"),
                ),
                EnvironmentKitPiece(
                    piece_id=f"{prefix}_large_water_sheet",
                    collection_id=f"{prefix}_dressing",
                    label="K1 Shyrack Cave Large Water Sheet",
                    game=tag,
                    module_resref="m34aa",
                    room_resref="m34aa_03a",
                    role="dressing",
                    class_id="dressing:cave_water_large",
                    model_resref="m34aa_03a",
                    source_bounds_m=(35.073, -78.267, -5.005, 59.349, -59.406, -5.001),
                    source_surface_names=("plane01",),
                    anchor_mode="floor",
                    dimensions_m=(24.276, 18.861, 0.004),
                    texture_resref="lko_water01",
                    tags=("k1", "korriban", "shyrack cave", "water", "large pool", "floor dressing", "vanilla-derived"),
                ),
            )
        return EnvironmentKitCollection(
            collection_id=f"{prefix}_dressing",
            label=f"{tag} Shyrack Caves — Rock Formations, Webs & Water",
            game=tag,
            module_resref=module,
            environment_kind="interior",
            floor_texture="lrk_flr03",
            wall_texture=cliff_texture,
            ceiling_texture=cliff_texture,
            pieces=pieces,
            tags=(tag.lower(), "korriban", "shyrack cave", "dressing", "content-browser", "vanilla-derived"),
        )

    module = "711kor" if is_k2 else "m37aa"
    room = "711kora" if is_k2 else "m37aa_02"
    prefix = f"{tag.lower()}_korriban_tombs"
    collection_id = f"{prefix}_dressing"
    if is_k2:
        rows = (
            (
                "rune_wall",
                "K2 Secret Tomb Rune Wall Assembly",
                "tomb_rune_wall",
                (-8.944, -37.159, -1.680, 8.374, -19.835, 7.223),
                ("runes",),
                "wall",
                (17.318, 17.324, 8.903),
                "kor_wal06",
                ("runes", "relief", "wall decor"),
            ),
            (
                "column_assembly",
                "K2 Secret Tomb Ruined Column Assembly",
                "tomb_columns",
                (-4.582, -40.741, 0.744, 12.002, -16.236, 11.105),
                ("columns",),
                "floor",
                (16.584, 24.505, 10.361),
                "kor_wal09",
                ("column", "ruin", "masonry"),
            ),
            (
                "ritual_stones",
                "K2 Secret Tomb Ritual Stone Cluster",
                "tomb_altar",
                (-3.000, -30.097, 0.750, 2.387, -26.822, 5.123),
                ("tstone", "tstone2", "tstone3"),
                "floor",
                (5.387, 3.275, 4.373),
                "kor_wal09",
                ("altar", "ritual", "sarcophagus"),
            ),
            (
                "upper_trim",
                "K2 Secret Tomb Upper Trim Relief",
                "tomb_trim",
                (-2.806, -31.058, 6.526, 2.407, -25.845, 8.216),
                ("object02",),
                "wall",
                (5.213, 5.213, 1.690),
                "kor_tr01",
                ("trim", "relief", "wall decor"),
            ),
        )
    else:
        rows = (
            (
                "masonry_relief",
                "K1 Tomb Carved Masonry Relief",
                "tomb_relief",
                (3.391, -24.523, 6.657, 8.487, -21.477, 8.642),
                ("object20", "object21"),
                "wall",
                (5.096, 3.046, 1.985),
                "lko_wal09",
                ("relief", "masonry", "wall decor"),
            ),
            (
                "stone_buttress",
                "K1 Tomb Weathered Stone Buttress",
                "tomb_buttress",
                (-11.569, -24.752, 6.618, -7.529, -17.128, 11.869),
                ("chamferbox01", "chamferbox02"),
                "floor",
                (4.040, 7.624, 5.251),
                "lko_wal07",
                ("buttress", "weathered stone", "ruin"),
            ),
            (
                "rock_cap",
                "K1 Tomb Ceiling Rock Cap",
                "tomb_ceiling_rock",
                (-5.925, -26.700, 14.933, 11.250, -15.300, 17.625),
                ("plane02",),
                "ceiling",
                (17.175, 11.400, 2.692),
                "lko_rocks",
                ("ceiling", "rock", "cave intrusion"),
            ),
            (
                "rubble",
                "K1 Tomb Fallen Rock Cluster",
                "tomb_rubble",
                (-0.389, -25.868, 10.220, 4.838, -15.914, 11.477),
                ("chamferbox03", "chamferbox04"),
                "floor",
                (5.227, 9.954, 1.257),
                "lko_rock04",
                ("rubble", "rock", "debris"),
            ),
        )
    source_rows = tuple((module, room) + row for row in rows)
    if not is_k2:
        source_rows += (
            (
                "m37aa",
                "m37aa_12",
                "sarcophagus",
                "K1 Tomb Sarcophagus & Reliquary Frame",
                "tomb_sarcophagus",
                (-3.000, -30.286, 0.724, 1.350, -25.747, 2.695),
                ("tombframe01", "chamferbox07"),
                "floor",
                (4.350, 4.539, 1.971),
                "lko_wal08",
                ("sarcophagus", "reliquary", "burial furnishing"),
            ),
            (
                "m37aa",
                "m37aa_12",
                "offering_stones",
                "K1 Tomb Burial Offering Stones",
                "tomb_offerings",
                (-3.397, -31.808, 0.639, 1.366, -25.815, 1.163),
                ("box1758", "box1759", "box1760", "box1761"),
                "floor",
                (4.763, 5.993, 0.524),
                "lko_wal09",
                ("offering", "burial", "stone slabs"),
            ),
            (
                "m37aa",
                "m37aa_12",
                "floor_dais",
                "K1 Tomb Carved Chamber Floor Dais",
                "tomb_floor_dais",
                (-12.634, -40.875, 1.875, 12.001, -16.123, 2.475),
                ("mesh01", "mesh04", "mesh07", "mesh10"),
                "floor",
                (24.635, 24.752, 0.600),
                "lko_wal09",
                ("floor insert", "dais", "chamber centerpiece"),
            ),
            (
                "m37aa",
                "m37aa_12",
                "vault_pier",
                "K1 Tomb Carved Vault Pier",
                "tomb_vault_pier",
                (-1.950, -18.941, 5.100, 1.200, -16.241, 11.100),
                ("object1831",),
                "wall",
                (3.150, 2.700, 6.000),
                "lko_wal07",
                ("pier", "vault support", "wall architecture"),
            ),
            (
                "m37aa",
                "m37aa_12",
                "vault_ring",
                "K1 Tomb Circular Vault Trim",
                "tomb_vault_ring",
                (-4.427, -33.002, 5.062, 4.127, -24.448, 6.246),
                ("object11",),
                "ceiling",
                (8.554, 8.554, 1.184),
                "lko_tirm01",
                ("vault ring", "ceiling trim", "ritual architecture"),
            ),
            (
                "m39aa",
                "m39aa_07",
                "ritual_dais",
                "K1 Naga Sadow Ritual Stone Dais",
                "tomb_ritual_dais",
                (31.787, 16.631, 6.029, 38.811, 21.696, 7.568),
                ("box1677162", "box1677163", "chamferbox6114", "chamferbox6115"),
                "floor",
                (7.024, 5.065, 1.539),
                "lko_wal09",
                ("ritual", "dais", "monumental hall"),
            ),
            (
                "m39aa",
                "m39aa_07",
                "monument_pylon",
                "K1 Naga Sadow Monument Pylon",
                "tomb_monument_pylon",
                (2.513, 18.750, -1.500, 5.963, 22.200, 9.787),
                ("box1655",),
                "floor",
                (3.450, 3.450, 11.287),
                "lko_wal09",
                ("pylon", "monument", "structural dressing"),
            ),
            (
                "m39aa",
                "m39aa_07",
                "monument_rock",
                "K1 Naga Sadow Fallen Monument Rock",
                "tomb_monument_rock",
                (2.880, 14.203, 5.529, 5.588, 17.179, 8.367),
                ("box1677155",),
                "floor",
                (2.708, 2.976, 2.838),
                "lko_rocks",
                ("rock", "fallen monument", "debris"),
            ),
        )
    pieces = tuple(
        EnvironmentKitPiece(
            piece_id=f"{prefix}_{suffix}",
            collection_id=collection_id,
            label=label,
            game=tag,
            module_resref=source_module,
            room_resref=source_room,
            role="dressing",
            class_id=f"dressing:{class_name}",
            model_resref=source_room,
            source_bounds_m=bounds,
            source_surface_names=surface_names,
            anchor_mode=anchor_mode,
            local_normal_axis="y",
            dimensions_m=dimensions,
            texture_resref=texture,
            tags=(tag.lower(), "korriban", "sith tomb", "vanilla-derived") + tuple(extra_tags),
        )
        for (
            source_module,
            source_room,
            suffix,
            label,
            class_name,
            bounds,
            surface_names,
            anchor_mode,
            dimensions,
            texture,
            extra_tags,
        ) in source_rows
    )
    return EnvironmentKitCollection(
        collection_id=collection_id,
        label=f"{tag} Korriban Tombs — Architectural Dressing",
        game=tag,
        module_resref=module,
        environment_kind="interior",
        floor_texture="kor_flr01" if is_k2 else "lko_flr01",
        wall_texture="kor_wal09" if is_k2 else "lko_wal09",
        ceiling_texture="kor_wal07a" if is_k2 else "lko_wal07",
        pieces=pieces,
        tags=(tag.lower(), "korriban", "sith tomb", "dressing", "content-browser", "vanilla-derived"),
    )


def _telos_citadel_dressing_collection() -> EnvironmentKitCollection:
    """Portable Citadel Station fixtures clipped from installed K2 rooms.

    These are deliberately separate content-browser pieces. The recipes retain
    retail UVs and materials while stripping room lightmaps and walkability, so
    a builder can stage signs, seating, terminals, lights, and structural trim
    without dragging an entire vanilla room.
    """

    collection_id = "k2_telos_citadel_dressing"
    source_rows = (
        (
            "201tel",
            "201tel05",
            "directory_wide",
            "Citadel Wide Directory Panel",
            "directory_panel",
            (10.30, 13.88, 14.10, 14.32, 14.36, 15.68),
            ("billa1", "billa2", "billa3"),
            "wall",
            "y",
            (3.853, 0.346, 1.432),
            "tel_bbrds",
            ("sign", "directory", "wall panel", "wayfinding"),
        ),
        (
            "201tel",
            "201tel05",
            "directory_tall",
            "Citadel Tall Directory Panel",
            "directory_panel",
            (17.28, 13.92, 13.64, 20.63, 14.36, 16.16),
            ("billb1", "billb2", "billb3"),
            "wall",
            "y",
            (3.206, 0.303, 2.370),
            "tel_bbrds",
            ("sign", "directory", "wall panel", "wayfinding"),
        ),
        (
            "201tel",
            "201tel05",
            "directory_split",
            "Citadel Split Directory Panel",
            "directory_panel",
            (23.55, 13.93, 13.78, 28.05, 14.38, 15.84),
            ("billc1", "billc2", "billc3"),
            "wall",
            "y",
            (4.340, 0.303, 1.904),
            "tel_bbrds",
            ("sign", "directory", "wall panel", "wayfinding"),
        ),
        (
            "201tel",
            "201tel05",
            "directory_pillar",
            "Citadel Directory Pillar",
            "directory_pillar",
            (21.84, 13.90, 13.34, 22.78, 14.34, 16.08),
            ("lbbrds1", "lbbrds3"),
            "wall",
            "y",
            (0.783, 0.303, 2.604),
            "tel_bbrds3",
            ("sign", "directory", "vertical panel", "wayfinding"),
        ),
        (
            "202tel",
            "202tel02",
            "wall_monitor",
            "Citadel Wall Monitor Cluster",
            "wall_monitor",
            (-21.30, 12.50, 13.10, -17.90, 14.10, 14.70),
            ("wr_mon02", "wr_scrn06", "wr_scrn07", "wr_scrn08", "wr_scrn09", "wr_scrn10"),
            "wall",
            "y",
            (3.187, 1.366, 1.366),
            "tel_hjk",
            ("computer", "monitor", "screen", "wall control"),
        ),
        (
            "202tel",
            "202tel02",
            "corridor_bench",
            "Citadel Corridor Bench",
            "seating",
            (-20.18, -1.20, 11.45, -18.94, 9.30, 11.96),
            ("bench03",),
            "floor",
            "x",
            (1.098, 10.358, 0.380),
            "tel_hw8",
            ("bench", "seating", "public space", "furniture"),
        ),
        (
            "202tel",
            "202tel08",
            "doorway_pier",
            "Citadel Structural Doorway Pier",
            "structural_trim",
            (17.48, -11.84, 12.88, 18.42, -6.35, 16.56),
            ("object10", "object11"),
            "floor",
            "x",
            (0.788, 5.356, 3.558),
            "tel_hw10",
            ("doorway", "pier", "structural", "wall trim"),
        ),
        (
            "207tel",
            "207tel_1",
            "cantina_terminal",
            "Citadel Cantina Service Terminal",
            "service_terminal",
            (-0.98, 11.65, 10.60, 0.42, 12.55, 12.10),
            ("gr_bar1", "gr_bar2", "gr_bar3", "gr_duct"),
            "floor",
            "y",
            (1.232, 0.796, 1.375),
            "nar_bar1",
            ("cantina", "terminal", "service", "computer"),
        ),
        (
            "207tel",
            "207tel_1",
            "civic_light_band",
            "Citadel Civic Light Band",
            "wall_light",
            (-5.78, 35.00, 10.12, 4.18, 35.58, 14.54),
            ("object09",),
            "wall",
            "y",
            (9.787, 0.412, 4.261),
            "tel_lt02",
            ("light", "wall light", "civic", "luminaire"),
        ),
    )
    pieces = tuple(
        EnvironmentKitPiece(
            piece_id=f"k2_telos_citadel_{suffix}",
            collection_id=collection_id,
            label=label,
            game="K2",
            module_resref=module_resref,
            room_resref=room_resref,
            role="dressing",
            class_id=f"dressing:{class_name}",
            model_resref=room_resref,
            source_bounds_m=bounds,
            source_surface_names=surface_names,
            anchor_mode=anchor_mode,
            local_normal_axis=local_normal_axis,
            dimensions_m=dimensions,
            texture_resref=texture,
            tags=("k2", "telos", "citadel station", "vanilla-derived") + tuple(extra_tags),
        )
        for (
            module_resref,
            room_resref,
            suffix,
            label,
            class_name,
            bounds,
            surface_names,
            anchor_mode,
            local_normal_axis,
            dimensions,
            texture,
            extra_tags,
        ) in source_rows
    )
    return EnvironmentKitCollection(
        collection_id=collection_id,
        label="Telos Citadel Station — Environment Pieces",
        game="K2",
        module_resref="203tel",
        environment_kind="interior",
        floor_texture="tel_fl05",
        wall_texture="tel_wl06",
        ceiling_texture="tel_fl01",
        pieces=pieces,
        tags=(
            "k2",
            "telos",
            "citadel station",
            "dressing",
            "content-browser",
            "individually-placeable",
            "vanilla-derived",
        ),
    )


def _builtin_environment_kit_collections() -> tuple[EnvironmentKitCollection, ...]:
    return (
        _republic_warship_dressing_collection(game="K1"),
        _republic_warship_dressing_collection(game="K2"),
        _telos_citadel_dressing_collection(),
        _korriban_dressing_collection(game="K1", family="tombs"),
        _korriban_dressing_collection(game="K2", family="tombs"),
        _korriban_dressing_collection(game="K1", family="caves"),
        _korriban_dressing_collection(game="K2", family="caves"),
    )


@lru_cache(maxsize=2)
def vanilla_environment_kit_collections(path_text: str = "") -> tuple[EnvironmentKitCollection, ...]:
    path = Path(path_text) if path_text else environment_kit_catalog_path()
    if not path.is_file():
        return _builtin_environment_kit_collections()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return ()
    if str(payload.get("schema") or "") != ENVIRONMENT_KIT_SCHEMA:
        return ()
    rows: list[EnvironmentKitCollection] = []
    for raw in tuple(payload.get("collections") or ()):
        row = dict(raw or {})
        collection_id = str(row.get("collection_id") or "")
        game = str(row.get("game") or "").upper()
        if not collection_id or game not in {"K1", "K2"}:
            continue
        rows.append(
            EnvironmentKitCollection(
                collection_id=collection_id,
                label=str(row.get("label") or collection_id),
                game=game,
                module_resref=str(row.get("module_resref") or "").lower(),
                environment_kind=str(row.get("environment_kind") or "interior"),
                floor_texture=str(row.get("floor_texture") or "ruler01").lower(),
                wall_texture=str(row.get("wall_texture") or "ruler01").lower(),
                ceiling_texture=str(row.get("ceiling_texture") or "ruler01").lower(),
                pieces=tuple(_piece_from_payload(value) for value in tuple(row.get("pieces") or ())),
                tags=tuple(str(value) for value in tuple(row.get("tags") or ())),
            )
        )
    merged = {collection.collection_id: collection for collection in rows}
    for collection in _builtin_environment_kit_collections():
        merged[collection.collection_id] = collection
    return tuple(merged.values())


def _yaw_quaternion(yaw: float) -> tuple[float, float, float, float]:
    return (0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5))


def _terrain_edge_magnets(dimensions: tuple[float, float, float]) -> tuple[EnvironmentKitMagnet, ...]:
    width = max(0.01, float(dimensions[0]))
    depth = max(0.01, float(dimensions[1]))
    return tuple(
        EnvironmentKitMagnet(
            magnet_id=name,
            kind="terrain_edge",
            magnet_class="terrain_edge",
            local_position=position,
            local_orientation=_yaw_quaternion(yaw),
            source="bounds_inference",
        )
        for name, position, yaw in (
            ("east", (width * 0.5, 0.0, 0.0), 0.0),
            ("north", (0.0, depth * 0.5, 0.0), math.pi * 0.5),
            ("west", (-width * 0.5, 0.0, 0.0), math.pi),
            ("south", (0.0, -depth * 0.5, 0.0), -math.pi * 0.5),
        )
    )


def _doorway_archetype(magnets: tuple[EnvironmentKitMagnet, ...]) -> str:
    """Classify a retail room tile by its LYT doorway topology.

    Kotor.NET-style kits need semantic piece types, not only an arbitrary room
    name and connection count.  LYT door hooks are the strongest retail signal
    available without redistributing model bytes: they state exactly where a
    room is intended to connect and which way the connection faces.
    """

    count = len(magnets)
    if count <= 0:
        return "chamber"
    if count == 1:
        return "dead_end"
    angles = sorted(magnet.snap_facing_radians for magnet in magnets)
    if count == 2:
        delta = abs(math.atan2(math.sin(angles[1] - angles[0]), math.cos(angles[1] - angles[0])))
        degrees = math.degrees(delta)
        if degrees >= 145.0:
            return "straight"
        if 55.0 <= degrees <= 125.0:
            return "corner"
        return "bend"
    if count == 3:
        return "t_junction"
    if count == 4:
        gaps = [
            (angles[(index + 1) % count] - angles[index]) % (2.0 * math.pi)
            for index in range(count)
        ]
        if all(math.radians(55.0) <= gap <= math.radians(125.0) for gap in gaps):
            return "cross"
        return "four_way_hub"
    return "hub"


def _walkmesh_transition_magnets(
    resource_manager: Any,
    *,
    game: str,
    room_resref: str,
    source_room_position: tuple[float, float, float],
) -> tuple[EnvironmentKitMagnet, ...]:
    """Infer connection sockets from grouped retail WOK transition edges.

    Cave LYTs commonly omit door hooks even though their WOKs carry the exact
    passage boundaries.  Grouping contiguous directed edges by the retail
    transition index preserves that source-of-truth portal and makes the cave
    rooms behave like ordinary magnetized kit pieces.
    """

    try:
        from .module_format import WOKData
    except ImportError:  # pragma: no cover - supports the embedded package route.
        from core.modules.module_format import WOKData  # type: ignore

    getter = getattr(resource_manager, "get", None)
    if not callable(getter):
        return ()
    try:
        raw = getter(str(room_resref or "").strip().lower(), 2016, str(game or "K1").upper())
    except Exception:
        return ()
    if not raw:
        return ()
    wok = WOKData.from_bytes(bytes(raw))
    vertices = tuple(getattr(wok, "verts", ()) or ())
    faces = tuple(getattr(wok, "faces", ()) or ())
    grouped: dict[int, list[tuple[float, tuple[float, float, float], tuple[float, float]]]] = {}
    for face in faces:
        indices = (
            int(getattr(face, "v1", -1)),
            int(getattr(face, "v2", -1)),
            int(getattr(face, "v3", -1)),
        )
        transitions = (
            int(getattr(face, "trans1", -1)),
            int(getattr(face, "trans2", -1)),
            int(getattr(face, "trans3", -1)),
        )
        if min(indices) < 0 or max(indices) >= len(vertices):
            continue
        centroid = tuple(
            sum(float(vertices[index][axis]) for index in indices) / 3.0
            for axis in range(3)
        )
        for local_edge, transition in enumerate(transitions):
            if transition < 0:
                continue
            first = vertices[indices[local_edge]]
            second = vertices[indices[(local_edge + 1) % 3]]
            midpoint = tuple((float(first[axis]) + float(second[axis])) * 0.5 for axis in range(3))
            length = math.dist(
                (float(first[0]), float(first[1]), float(first[2])),
                (float(second[0]), float(second[1]), float(second[2])),
            )
            if length <= 1.0e-6:
                continue
            # The triangle centroid lies inside the walkable room.  Pointing
            # away from it yields the passage-facing socket normal.
            outward = (float(midpoint[0]) - float(centroid[0]), float(midpoint[1]) - float(centroid[1]))
            outward_length = math.hypot(*outward)
            if outward_length <= 1.0e-8:
                continue
            grouped.setdefault(transition, []).append(
                (
                    length,
                    midpoint,
                    (outward[0] / outward_length, outward[1] / outward_length),
                )
            )

    origin = tuple(float(value) for value in source_room_position)
    magnets: list[EnvironmentKitMagnet] = []
    for transition, rows in sorted(grouped.items()):
        total = sum(row[0] for row in rows)
        if total <= 1.0e-8:
            continue
        midpoint = tuple(sum(row[0] * row[1][axis] for row in rows) / total for axis in range(3))
        outward = (
            sum(row[0] * row[2][0] for row in rows) / total,
            sum(row[0] * row[2][1] for row in rows) / total,
        )
        outward_length = math.hypot(*outward)
        if outward_length <= 1.0e-8:
            continue
        yaw = math.atan2(outward[1] / outward_length, outward[0] / outward_length)
        magnets.append(
            EnvironmentKitMagnet(
                magnet_id=f"wok_portal_{transition:03d}",
                kind="doorway",
                magnet_class="doorway",
                local_position=tuple(float(midpoint[axis]) - origin[axis] for axis in range(3)),
                local_orientation=_yaw_quaternion(yaw),
                source="wok_transition_edge_group",
            )
        )
    return tuple(magnets)


def _read_base_game_layouts(resource_manager: Any, game: str) -> tuple[tuple[str, Any], ...]:
    try:
        from src.core.assets.resource_manager import RES_LYT
        from pykotor.resource.formats.lyt import read_lyt
        from .map_studio_room_catalog import _parse_ascii_lyt
    except Exception:
        return ()
    tag = str(game or "K1").upper()
    getter = getattr(resource_manager, "get_k2" if tag == "K2" else "get_k1", None)
    installation = getter() if callable(getter) else None
    if installation is None:
        return ()
    key_map = dict(getattr(installation, "_key_map", {}) or {})
    modules = sorted(key.rsplit(":", 1)[0] for key in key_map if key.endswith(f":{int(RES_LYT)}"))
    result: list[tuple[str, Any]] = []
    for module_resref in modules:
        try:
            raw = installation.get_bif(module_resref, RES_LYT)
            if not raw:
                continue
            try:
                layout = read_lyt(bytes(raw))
            except Exception:
                layout = _parse_ascii_lyt(bytes(raw))
            if layout is not None:
                result.append((module_resref, layout))
        except Exception:
            continue
    return tuple(result)


def environment_kit_source_room_position(
    piece: EnvironmentKitPiece,
    resource_manager: Any,
) -> tuple[float, float, float]:
    """Return a tile's original LYT translation for WOK localization.

    Retail room render meshes are room-local, while their external WOK
    vertices are already translated into source-module space. Reusable kit
    placement must subtract this exact LYT row before applying a new room
    transform; otherwise collision stays tens of metres from the visible tile.
    """

    try:
        from src.core.assets.resource_manager import RES_LYT
        from pykotor.resource.formats.lyt import read_lyt
        from .map_studio_room_catalog import _parse_ascii_lyt
    except Exception as exc:
        raise ValueError(f"KOTOR layout support is unavailable: {exc}") from exc
    getter = getattr(resource_manager, "get", None)
    if not callable(getter):
        raise ValueError("The configured game resource manager cannot read module layouts.")
    raw = getter(piece.module_resref, RES_LYT, piece.game)
    if not raw:
        raise ValueError(f"Source layout {piece.module_resref}.lyt was not found for {piece.label}.")
    try:
        layout = read_lyt(bytes(raw))
    except Exception:
        layout = _parse_ascii_lyt(bytes(raw))
    wanted = str(piece.room_resref or "").strip().lower()
    for room in tuple(getattr(layout, "rooms", ()) or ()):
        model = str(getattr(room, "model", getattr(room, "name", "")) or "").strip().lower()
        if model != wanted:
            continue
        position = getattr(room, "position", room)
        values = (
            float(getattr(position, "x", getattr(room, "x", 0.0))),
            float(getattr(position, "y", getattr(room, "y", 0.0))),
            float(getattr(position, "z", getattr(room, "z", 0.0))),
        )
        if not all(math.isfinite(value) for value in values):
            break
        return values
    raise ValueError(f"Room {piece.room_resref} is not listed in source layout {piece.module_resref}.lyt.")


def scan_vanilla_environment_kits(
    resource_manager: Any,
    *,
    games: tuple[str, ...] = ("K1", "K2"),
    module_resrefs: tuple[str, ...] = (),
    progress: Any = None,
) -> tuple[EnvironmentKitCollection, ...]:
    """Build lightweight kit metadata from retail layouts and terrain census."""

    from .map_studio_room_catalog import _door_hooks_by_room
    from .map_studio_terrain_kit import vanilla_terrain_kit_assets
    from .map_studio_pascal_building import vanilla_pascal_building_styles

    terrain_assets = tuple(vanilla_terrain_kit_assets())
    terrain_by_module: dict[tuple[str, str], list[Any]] = {}
    for asset in terrain_assets:
        terrain_by_module.setdefault((asset.game, asset.module_resref), []).append(asset)
    palettes = {(style.game, style.source_module): style for style in vanilla_pascal_building_styles()}
    wanted_modules = {
        str(value or "").strip().lower()
        for value in tuple(module_resrefs or ())
        if str(value or "").strip()
    }
    layouts: list[tuple[str, str, Any]] = []
    for game in tuple(dict.fromkeys(str(value or "").upper() for value in games)):
        if game in {"K1", "K2"}:
            layouts.extend(
                (game, module, layout)
                for module, layout in _read_base_game_layouts(resource_manager, game)
                if not wanted_modules or str(module or "").strip().lower() in wanted_modules
            )
    result: list[EnvironmentKitCollection] = []
    total = len(layouts)
    for ordinal, (game, module_resref, layout) in enumerate(layouts, 1):
        if callable(progress):
            progress(ordinal - 1, total, f"{game} {module_resref}")
        collection_id = f"{game.lower()}_{module_resref}"
        terrain = terrain_by_module.get((game, module_resref), [])
        hooks_by_room = _door_hooks_by_room(layout)
        pieces: list[EnvironmentKitPiece] = []
        terrain_rooms = {asset.room_resref for asset in terrain}
        for room in tuple(getattr(layout, "rooms", ()) or ()):
            room_resref = str(getattr(room, "model", getattr(room, "name", "")) or "").strip().lower()
            if not room_resref:
                continue
            magnets = tuple(
                EnvironmentKitMagnet(
                    magnet_id=str(hook.door or f"door_{index + 1}"),
                    kind="doorway",
                    magnet_class="doorway",
                    local_position=tuple(float(value) for value in hook.local_position),
                    local_orientation=tuple(float(value) for value in hook.orientation),
                    source="lyt_doorhook",
                )
                for index, hook in enumerate(hooks_by_room.get(room_resref, ()))
            )
            if not magnets:
                position = getattr(room, "position", room)
                source_room_position = (
                    float(getattr(position, "x", getattr(room, "x", 0.0))),
                    float(getattr(position, "y", getattr(room, "y", 0.0))),
                    float(getattr(position, "z", getattr(room, "z", 0.0))),
                )
                magnets = _walkmesh_transition_magnets(
                    resource_manager,
                    game=game,
                    room_resref=room_resref,
                    source_room_position=source_room_position,
                )
            role = "exterior_tile" if room_resref in terrain_rooms else "room_tile"
            archetype = _doorway_archetype(magnets)
            pieces.append(
                EnvironmentKitPiece(
                    piece_id=f"{collection_id}_{room_resref}",
                    collection_id=collection_id,
                    label=f"{room_resref} · {module_resref}",
                    game=game,
                    module_resref=module_resref,
                    room_resref=room_resref,
                    role=role,
                    class_id=f"{role}:{archetype}",
                    model_resref=room_resref,
                    magnets=magnets,
                    tags=(game.lower(), module_resref, room_resref, role, archetype, "vanilla"),
                )
            )
        textures: Counter[str] = Counter()
        for asset in terrain:
            textures[str(asset.texture_resref or "ruler01").lower()] += max(1, int(asset.triangle_count))
            pieces.append(
                EnvironmentKitPiece(
                    piece_id=asset.asset_id,
                    collection_id=collection_id,
                    label=asset.label,
                    game=game,
                    module_resref=module_resref,
                    room_resref=asset.room_resref,
                    role="terrain",
                    class_id=f"terrain:{str(asset.category).lower()}",
                    model_resref=asset.room_resref,
                    terrain_asset_id=asset.asset_id,
                    surface_index=int(asset.surface_index),
                    texture_resref=str(asset.texture_resref or "").lower(),
                    lightmap_resref=str(asset.lightmap_resref or "").lower(),
                    dimensions_m=tuple(float(value) for value in asset.dimensions_m),
                    triangle_count=int(asset.triangle_count),
                    magnets=_terrain_edge_magnets(tuple(float(value) for value in asset.dimensions_m)),
                    tags=tuple(asset.tags) + ("magnetized",),
                )
            )
        palette = palettes.get((game, module_resref))
        common_texture = textures.most_common(1)[0][0] if textures else "ruler01"
        exterior = bool(terrain)
        result.append(
            EnvironmentKitCollection(
                collection_id=collection_id,
                label=f"{game} · {module_resref} · {'Exterior' if exterior else 'Interior'}",
                game=game,
                module_resref=module_resref,
                environment_kind="exterior" if exterior else "interior",
                floor_texture=str(getattr(palette, "floor_texture", common_texture) or common_texture),
                wall_texture=str(getattr(palette, "wall_texture", common_texture) or common_texture),
                ceiling_texture=str(getattr(palette, "ceiling_texture", common_texture) or common_texture),
                pieces=tuple(pieces),
                tags=(game.lower(), module_resref, "vanilla", "environment-kit", "exterior" if exterior else "interior"),
            )
        )
    if callable(progress):
        progress(total, total, f"Learned {len(result)} retail environment collections")
    return tuple(result)


def write_vanilla_environment_kit_catalog(
    collections: tuple[EnvironmentKitCollection, ...],
    path: str | Path = "",
) -> Path:
    target = Path(path) if path else environment_kit_catalog_path(writable=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    collection_rows = [asdict(collection) for collection in collections]
    for collection in collection_rows:
        for piece in collection["pieces"]:
            if piece.get("role") == "terrain":
                # The four axis-aligned bounds magnets are deterministic from
                # dimensions, so store one profile token instead of repeating
                # ~26k identical socket records in the generated catalog.
                piece["magnets"] = []
                piece["magnet_profile"] = "bounds_4"
    payload = {
        "schema": ENVIRONMENT_KIT_SCHEMA,
        "collection_count": len(collections),
        "piece_count": sum(len(collection.pieces) for collection in collections),
        "collections": collection_rows,
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    # Generated metadata can contain thousands of pieces and magnets; keep it
    # compact without storing any retail geometry or texture bytes.
    temporary.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)
    vanilla_environment_kit_collections.cache_clear()
    environment_kit_piece_index.cache_clear()
    return target


def environment_kit_collection_rows(*, game: str = "", kind: str = "") -> tuple[dict[str, Any], ...]:
    wanted_game = str(game or "").upper()
    wanted_kind = str(kind or "").lower()
    return tuple(
        {
            "collection_id": collection.collection_id,
            "label": environment_kit_collection_display_label(collection),
            "world_label": kotor_module_world_label(collection.game, collection.module_resref),
            "game": collection.game,
            "module_resref": collection.module_resref,
            "environment_kind": collection.environment_kind,
            "floor_texture": collection.floor_texture,
            "wall_texture": collection.wall_texture,
            "ceiling_texture": collection.ceiling_texture,
            "piece_count": len(collection.pieces),
            "room_piece_count": collection.room_piece_count,
            "terrain_piece_count": collection.terrain_piece_count,
            "tags": collection.tags,
            "building_style_id": environment_kit_builder_style_id(
                collection.game,
                collection.module_resref,
                collection.collection_id,
            ),
        }
        for collection in vanilla_environment_kit_collections()
        if (not wanted_game or collection.game == wanted_game)
        and (not wanted_kind or collection.environment_kind == wanted_kind)
    )


def environment_kit_piece_rows(
    *,
    game: str = "",
    kind: str = "",
    collection_id: str = "",
    roles: tuple[str, ...] = ("room_tile", "exterior_tile", "dressing"),
) -> tuple[dict[str, Any], ...]:
    """Return lightweight content-browser rows without retail geometry bytes."""

    wanted_game = str(game or "").upper()
    wanted_kind = str(kind or "").strip().lower()
    wanted_collection = str(collection_id or "").strip().lower()
    wanted_roles = {str(value or "").strip().lower() for value in tuple(roles or ())}
    rows: list[dict[str, Any]] = []
    for collection in vanilla_environment_kit_collections():
        if wanted_game and collection.game != wanted_game:
            continue
        if wanted_kind and collection.environment_kind != wanted_kind:
            continue
        if wanted_collection and collection.collection_id.lower() != wanted_collection:
            continue
        for piece in collection.pieces:
            if wanted_roles and piece.role.lower() not in wanted_roles:
                continue
            rows.append(
                {
                    "piece_id": piece.piece_id,
                    "asset_id": piece.piece_id,
                    "collection_id": collection.collection_id,
                    "collection_label": environment_kit_collection_display_label(collection),
                    "world_label": kotor_module_world_label(collection.game, collection.module_resref),
                    "label": piece.label,
                    "game": piece.game,
                    "module_resref": piece.module_resref,
                    "room_resref": piece.room_resref,
                    "role": piece.role,
                    "class_id": piece.class_id,
                    "model_resref": piece.model_resref,
                    "anchor_mode": piece.anchor_mode,
                    "local_normal_axis": piece.local_normal_axis,
                    "dimensions_m": piece.dimensions_m,
                    "has_backdrop": bool(piece.backdrop_texture_resref),
                    "environment_kind": collection.environment_kind,
                    "magnet_count": len(piece.magnets),
                    "floor_texture": collection.floor_texture,
                    "wall_texture": collection.wall_texture,
                    "ceiling_texture": collection.ceiling_texture,
                    "tags": piece.tags,
                    "building_style_id": environment_kit_builder_style_id(
                        collection.game,
                        collection.module_resref,
                        collection.collection_id,
                    ),
                }
            )
    return tuple(rows)


def environment_kit_drag_payload(
    piece: EnvironmentKitPiece | str,
    *,
    rotation_degrees_z: float = 0.0,
    scale: float = 1.0,
) -> dict[str, Any]:
    """Build the typed payload consumed by Map Studio's viewport drop target."""

    entry = environment_kit_piece(piece) if isinstance(piece, str) else piece
    if entry is None:
        raise ValueError(f"Unknown environment-kit piece {piece!r}.")
    return {
        "schema": ENVIRONMENT_KIT_PAYLOAD_SCHEMA,
        "piece_id": entry.piece_id,
        "asset_id": entry.piece_id,
        "collection_id": entry.collection_id,
        "label": entry.label,
        "game": entry.game,
        "module_resref": entry.module_resref,
        "room_resref": entry.room_resref,
        "role": entry.role,
        "class_id": entry.class_id,
        "anchor_mode": entry.anchor_mode,
        "local_normal_axis": entry.local_normal_axis,
        "rotation_degrees_z": float(rotation_degrees_z),
        "scale": float(scale),
        "snap_to_surface": True,
        "snap_to_magnets": bool(entry.magnets),
    }


@lru_cache(maxsize=1)
def environment_kit_piece_index() -> dict[str, EnvironmentKitPiece]:
    result: dict[str, EnvironmentKitPiece] = {}
    for collection in vanilla_environment_kit_collections():
        for piece in collection.pieces:
            result[piece.piece_id.lower()] = piece
            if piece.terrain_asset_id:
                result[piece.terrain_asset_id.lower()] = piece
    return result


def environment_kit_piece(piece_id: str) -> EnvironmentKitPiece | None:
    return environment_kit_piece_index().get(str(piece_id or "").strip().lower())


def magnet_snap_transform(
    source: EnvironmentKitMagnet,
    target: EnvironmentKitMagnet,
    *,
    target_world_position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    target_world_yaw: float = 0.0,
    source_scale: float = 1.0,
    target_scale: float = 1.0,
) -> tuple[tuple[float, float, float], float]:
    """Align a source magnet to face a target magnet, Kotor.NET-style."""

    yaw = target_world_yaw + target.snap_facing_radians - source.snap_facing_radians + math.pi
    cosine = math.cos(yaw)
    sine = math.sin(yaw)
    sx, sy, sz = (float(value) * float(source_scale) for value in source.local_position)
    rotated_source = ((sx * cosine) - (sy * sine), (sx * sine) + (sy * cosine), sz)
    target_yaw = target_world_yaw
    target_cos = math.cos(target_yaw)
    target_sin = math.sin(target_yaw)
    tx, ty, tz = (float(value) * float(target_scale) for value in target.local_position)
    rotated_target = ((tx * target_cos) - (ty * target_sin), (tx * target_sin) + (ty * target_cos), tz)
    world_target = tuple(float(target_world_position[index]) + rotated_target[index] for index in range(3))
    position = tuple(world_target[index] - rotated_source[index] for index in range(3))
    return position, yaw


def nearest_environment_kit_snap(
    source_piece: EnvironmentKitPiece,
    *,
    proposed_position: tuple[float, float, float],
    proposed_yaw: float,
    source_scale: float,
    targets: tuple[tuple[EnvironmentKitPiece, tuple[float, float, float], float, float, str], ...],
    max_distance: float = 1.5,
) -> EnvironmentKitSnapResult | None:
    """Find and align the nearest compatible Kotor.NET-style magnet pair.

    Content-browser drags are cursor anchored: the pointer identifies the
    target doorway, while the room origin may be tens of metres from any of its
    hooks. Rank targets by pointer distance first, then choose the source hook
    whose exact snap transform moves the preview origin least.
    """

    best: EnvironmentKitSnapResult | None = None
    best_score: tuple[float, float] | None = None
    for source_magnet in source_piece.magnets:
        for target_piece, target_position, target_yaw, target_scale, target_room in targets:
            target_cos = math.cos(float(target_yaw))
            target_sin = math.sin(float(target_yaw))
            for target_magnet in target_piece.magnets:
                if source_magnet.kind != target_magnet.kind:
                    continue
                if source_magnet.magnet_class != target_magnet.magnet_class:
                    continue
                tx = float(target_magnet.local_position[0]) * float(target_scale)
                ty = float(target_magnet.local_position[1]) * float(target_scale)
                tz = float(target_magnet.local_position[2]) * float(target_scale)
                target_world = (
                    float(target_position[0]) + (tx * target_cos) - (ty * target_sin),
                    float(target_position[1]) + (tx * target_sin) + (ty * target_cos),
                    float(target_position[2]) + tz,
                )
                cursor_distance = math.hypot(
                    float(proposed_position[0]) - target_world[0],
                    float(proposed_position[1]) - target_world[1],
                )
                if cursor_distance > float(max_distance):
                    continue
                snapped_position, snapped_yaw = magnet_snap_transform(
                    source_magnet,
                    target_magnet,
                    target_world_position=target_position,
                    target_world_yaw=float(target_yaw),
                    source_scale=float(source_scale),
                    target_scale=float(target_scale),
                )
                transform_distance = math.dist(
                    tuple(float(value) for value in proposed_position[:3]),
                    snapped_position,
                )
                score = (cursor_distance, transform_distance)
                if best_score is not None and score >= best_score:
                    continue
                best_score = score
                best = EnvironmentKitSnapResult(
                    position=snapped_position,
                    yaw_radians=snapped_yaw,
                    source_magnet_id=source_magnet.magnet_id,
                    target_magnet_id=target_magnet.magnet_id,
                    target_piece_id=target_piece.piece_id,
                    target_room_resref=str(target_room or ""),
                    cursor_distance=cursor_distance,
                )
    return best


def nearest_environment_kit_wall_snap(
    source_piece: EnvironmentKitPiece,
    *,
    proposed_position: tuple[float, float, float],
    proposed_yaw: float,
    source_scale: float,
    walls: tuple[EnvironmentKitWallTarget, ...],
    max_distance: float = 3.0,
) -> EnvironmentKitSnapResult | None:
    """Snap a retail room doorway exactly onto any authored-room wall side.

    The dragged room keeps its real LYT hook as the source anchor.  The target
    is the nearest point on a wall edge, so the resulting transform aligns the
    source hook position and opposing normal without grid approximation.
    """

    best: EnvironmentKitSnapResult | None = None
    best_score: tuple[float, float] | None = None
    scale = float(source_scale)
    for source in source_piece.magnets:
        if source.kind != "doorway" or source.magnet_class != "doorway":
            continue
        sx = float(source.local_position[0]) * scale
        sy = float(source.local_position[1]) * scale
        sz = float(source.local_position[2]) * scale
        for wall in walls:
            dx = float(wall.end[0]) - float(wall.start[0])
            dy = float(wall.end[1]) - float(wall.start[1])
            length_squared = (dx * dx) + (dy * dy)
            if length_squared <= 1.0e-10:
                continue
            center_fraction = max(
                0.0,
                min(
                    1.0,
                    (((float(proposed_position[0]) - float(wall.start[0])) * dx) + ((float(proposed_position[1]) - float(wall.start[1])) * dy))
                    / length_squared,
                ),
            )
            target_world = (
                float(wall.start[0]) + dx * center_fraction,
                float(wall.start[1]) + dy * center_fraction,
                float(wall.floor_z) + float(wall.opening_bottom),
            )
            # Browser drags are cursor-anchored, not module-origin-anchored.
            # Retail room origins can be several metres from their LYT door
            # hooks; comparing a transformed hook to the wall made a room miss
            # even while the pointer was directly over the destination wall.
            # Let the pointer choose the wall and then solve the exact origin
            # transform that places the selected real hook on that wall.
            distance = math.hypot(
                float(proposed_position[0]) - target_world[0],
                float(proposed_position[1]) - target_world[1],
            )
            if distance > float(max_distance):
                continue
            snapped_yaw = float(wall.outward_yaw_radians) + math.pi - float(source.snap_facing_radians)
            snapped_cos = math.cos(snapped_yaw)
            snapped_sin = math.sin(snapped_yaw)
            rotated_source = (
                (sx * snapped_cos) - (sy * snapped_sin),
                (sx * snapped_sin) + (sy * snapped_cos),
                sz,
            )
            snapped_position = tuple(target_world[index] - rotated_source[index] for index in range(3))
            transform_distance = math.dist(
                tuple(float(value) for value in proposed_position[:3]),
                snapped_position,
            )
            score = (distance, transform_distance)
            if best_score is not None and score >= best_score:
                continue
            best_score = score
            best = EnvironmentKitSnapResult(
                position=snapped_position,
                yaw_radians=snapped_yaw,
                source_magnet_id=source.magnet_id,
                target_magnet_id=f"wall_{int(wall.edge_index):03d}",
                target_piece_id=f"authored_wall:{str(wall.room_resref or '').strip().lower()}",
                target_room_resref=str(wall.room_resref or "").strip().lower(),
                cursor_distance=distance,
                target_is_authored_wall=True,
                target_edge_index=int(wall.edge_index),
                target_center_fraction=center_fraction,
                opening_width=float(wall.opening_width),
                opening_height=float(wall.opening_height),
                opening_bottom=float(wall.opening_bottom),
            )
    return best


__all__ = [
    "ENVIRONMENT_KIT_SCHEMA",
    "ENVIRONMENT_KIT_MIME_TYPE",
    "ENVIRONMENT_KIT_PAYLOAD_SCHEMA",
    "EnvironmentKitCollection",
    "EnvironmentKitMagnet",
    "EnvironmentKitPiece",
    "EnvironmentKitSnapResult",
    "EnvironmentKitWallTarget",
    "environment_kit_catalog_path",
    "environment_kit_builder_style_id",
    "environment_kit_builder_style_label",
    "environment_kit_collection_rows",
    "environment_kit_collection_display_label",
    "environment_kit_drag_payload",
    "environment_kit_piece",
    "environment_kit_piece_index",
    "environment_kit_piece_rows",
    "environment_kit_source_room_position",
    "kotor_module_world_label",
    "magnet_snap_transform",
    "nearest_environment_kit_snap",
    "nearest_environment_kit_wall_snap",
    "scan_vanilla_environment_kits",
    "seal_environment_kit_exterior_bounds",
    "trim_environment_kit_connection_overlap",
    "vanilla_environment_kit_collections",
    "write_vanilla_environment_kit_catalog",
]
