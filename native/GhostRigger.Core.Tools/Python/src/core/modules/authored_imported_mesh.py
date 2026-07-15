"""Imported stock-geometry room primitive for Map Studio.

Owns the "edit a real game room" seam: a stock KOTOR room model (MDL/MDX from
the game directory) is baked into an editable, KMAP-serializable room
primitive so GModeler face operations (delete, retexture) can customize any
module and the export pipeline can compile the result as a new map.

Geometry is stored per texture surface (mirroring MDL trimesh nodes), with
transforms baked to room-local space.  Original UVs are preserved on import
so texture swaps work without re-unwrapping; faces that gain a new texture
keep their existing UVs, and brand-new geometry can fall back to
``planar_uvs_for_vertices``.

KMAP payloads pack vertex data as base64 little-endian float32/int32 blocks:
a stock room holds tens of thousands of floats, and inline JSON lists would
bloat .kmap files past usability.  Everything else stays readable JSON.
"""

from __future__ import annotations

import base64
import math
import struct
from dataclasses import dataclass, field, replace
from typing import Any

from src.core.geometry.mesh_topology import MeshTopology, compact_indexed_mesh

from .authored_room_geometry import AuthoredRoomGeometry, PrimitiveMesh
from .authored_walkmesh_surfaces import is_walkable_walkmesh_surface
from .module_format import WOKData, WOKFace

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]

IMPORTED_MESH_PRIMITIVE_KIND = "imported_mesh"

#: Named, versioned policy written only when a creator deliberately chooses
#: to replace an imported room's dynamic stock node graph with a newly
#: compiled static room graph.  Keeping this separate from ``preserved`` is
#: important: the source animations/lights/emitters/references are still lost,
#: but the loss is acknowledged instead of being misreported as preservation.
SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_POLICY = "authored_static_room_rebuild"
SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_VERSION = 1
_SOURCE_RUNTIME_GRAPH_COUNT_KEYS = (
    "animation_count",
    "light_count",
    "emitter_count",
    "reference_count",
)

#: Mesh role of the first surface (the preview model names the room mesh
#: "render"); remaining surfaces use ``imported_srf_<index>``.
RENDER_SURFACE_ROLE = "render"


@dataclass(frozen=True)
class ImportedMeshSurface:
    """One texture surface of an imported room (room-local space)."""

    name: str
    texture: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    face_mats: tuple[int, ...] = ()
    uvs: tuple[Vec2, ...] = ()
    normals: tuple[Vec3, ...] = ()
    lightmap: str = ""
    diffuse: Vec3 = (1.0, 1.0, 1.0)
    ambient: Vec3 = (1.0, 1.0, 1.0)
    #: Multi-texture data from the source MDL node: KOTOR area meshes often
    #: keep the diffuse map in texture_names[0] with a lightmap channel, and
    #: dropping these renders the room as an untextured fallback slab.
    texture_names: tuple[str, ...] = ()
    tex_count: int = 1
    uvs_lm: tuple[Vec2, ...] = ()
    specular: Vec3 = (0.0, 0.0, 0.0)
    shininess: float = 0.0
    alpha: float = 1.0
    has_shadow: bool = True
    render: bool = True
    selfillum: Vec3 = (0.0, 0.0, 0.0)
    transparency_hint: int = 0
    beaming: bool = False
    background_geometry: bool = False
    rotate_texture: bool = False
    animate_uv: bool = False
    uv_dir_x: float = 0.0
    uv_dir_y: float = 0.0
    uv_jitter: float = 0.0
    uv_jitter_speed: float = 0.0
    dirt_enabled: bool = False
    dirt_texture: int = 0
    dirt_coord_space: int = 0
    hide_in_holograms: bool = False
    mesh_average_point: Vec3 = (0.0, 0.0, 0.0)
    mesh_unknown0: bytes = b"\x00" * 24
    #: Visual sky/far-backdrop layer. The stable surface index is unchanged;
    #: Map Studio only changes visibility/pickability for this surface.
    backdrop: bool = False


@dataclass(frozen=True)
class ImportedMeshRoomPrimitive:
    """A stock KOTOR room baked into editable authored geometry."""

    room_resref: str
    surfaces: tuple[ImportedMeshSurface, ...]
    source_model: str = ""
    game: str = "K1"
    wok: WOKData | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportedMeshValidation:
    ok: bool
    warnings: tuple[str, ...] = ()
    blocking_issues: tuple[str, ...] = ()


def authored_room_uses_unresolved_stock_geometry(room: Any) -> bool:
    """Return whether ``room`` is a source-preservation placeholder.

    The explicit source/status/type checks keep a stray metadata boolean from
    suppressing ordinary authored geometry, collision, or export validation.
    """

    if isinstance(getattr(room, "primitive", None), ImportedMeshRoomPrimitive):
        return False
    metadata = dict(getattr(room, "metadata", {}) or {})
    return (
        str(metadata.get("source") or "").strip().lower() == "stock_module_import"
        and str(metadata.get("stock_geometry_status") or "").strip().lower() == "unresolved"
        and bool(metadata.get("pie_exclude_unresolved_stock_geometry", False))
    )


def imported_mesh_source_runtime_counts(primitive: ImportedMeshRoomPrimitive) -> dict[str, int]:
    """Return the dynamic source-node counts recorded by stock import."""

    graph = dict(dict(getattr(primitive, "metadata", {}) or {}).get("source_runtime_graph") or {})
    return {
        key: int(graph.get(key, 0) or 0)
        for key in _SOURCE_RUNTIME_GRAPH_COUNT_KEYS
        if int(graph.get(key, 0) or 0) > 0
    }


def imported_mesh_has_explicit_static_runtime_rebuild(primitive: ImportedMeshRoomPrimitive) -> bool:
    """Validate the lossy static-rebuild acknowledgement on one primitive.

    The recorded source counts must exactly match the current import audit, so
    a stale or hand-copied acknowledgement cannot silently waive a different
    room's runtime graph gate.
    """

    graph = dict(dict(getattr(primitive, "metadata", {}) or {}).get("source_runtime_graph") or {})
    policy = dict(graph.get("replacement_policy") or {})
    source_counts = imported_mesh_source_runtime_counts(primitive)
    try:
        recorded_counts = {
            str(key): int(value)
            for key, value in dict(policy.get("discarded_source_counts") or {}).items()
            if int(value or 0) > 0
        }
    except (TypeError, ValueError):
        return False
    return bool(
        source_counts
        and not bool(graph.get("preserved", False))
        and str(policy.get("kind") or "") == SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_POLICY
        and int(policy.get("version", 0) or 0) == SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_VERSION
        and str(policy.get("output_contract") or "") == "new_static_room_mdl"
        and bool(str(policy.get("reason") or "").strip())
        and recorded_counts == source_counts
    )


def prepare_imported_mesh_for_static_runtime_rebuild(
    primitive: ImportedMeshRoomPrimitive,
    *,
    reason: str,
) -> ImportedMeshRoomPrimitive:
    """Explicitly authorize replacing a stock runtime graph with static MDL.

    This is intentionally lossy and is suitable only when the creator has
    decided that the imported animations, model lights, emitters, and
    references are not part of the authored result.  Their original counts
    stay in KMAP for auditability; export emits a warning and compiles a fresh
    static room rather than claiming the graph was preserved.
    """

    clean_reason = str(reason or "").strip()
    if not clean_reason:
        raise ValueError("Static runtime-graph rebuild requires a written reason.")
    metadata = dict(getattr(primitive, "metadata", {}) or {})
    graph = dict(metadata.get("source_runtime_graph") or {})
    if not graph:
        raise ValueError("Imported room has no audited source runtime graph to replace.")
    source_counts = imported_mesh_source_runtime_counts(primitive)
    if not source_counts:
        raise ValueError("Imported room has no dynamic source runtime components to replace.")
    if bool(graph.get("preserved", False)):
        raise ValueError("Imported room runtime graph is already marked as preserved.")
    graph["replacement_policy"] = {
        "kind": SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_POLICY,
        "version": SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_VERSION,
        "output_contract": "new_static_room_mdl",
        "reason": clean_reason,
        "discarded_source_counts": dict(source_counts),
    }
    metadata["source_runtime_graph"] = graph
    return replace(primitive, metadata=metadata)


@dataclass(frozen=True)
class ImportedMeshBevelOptions:
    """Persistent operator state for a Maya-style imported-mesh edge bevel."""

    width: float = 0.25
    segments: int = 1
    profile: float = 0.5
    miter: str = "auto"
    smoothing_angle_degrees: float = 180.0
    uv_mode: str = "preserve"
    clamp_overlap: bool = True


def imported_mesh_surface_role(index: int) -> str:
    return RENDER_SURFACE_ROLE if index == 0 else f"imported_srf_{index}"


# Texture/name hints that mark an individual skybox / far-backdrop surface.
# K2 often uses ``*_sb01..05`` rather than spelling out "sky"; star fields
# and lightning layers can also live inside otherwise normal playable rooms.
_BACKDROP_TEXTURE_HINTS = ("sky", "cloud", "backdrop", "horizon", "stars", "_sb0")
_BACKDROP_NODE_HINTS = ("sky", "backdrop", "horizon", "star_field", "space", "lightning")
# A gameplay room rarely spans more than a couple hundred units; a backdrop
# dome spans thousands (RNVcity koq201_01j ~2100 units).
_BACKDROP_EXTENT_THRESHOLD = 300.0


def imported_mesh_surface_is_backdrop(
    surface: ImportedMeshSurface,
    *,
    extent_threshold: float = _BACKDROP_EXTENT_THRESHOLD,
) -> bool:
    """Return True when one stable imported surface is visual far backdrop.

    Classification is deliberately surface-scoped. Vanilla K2 rooms such as
    ``151harsb`` and ``231telsb`` mix giant sky/star layers with ordinary
    lightmapped or walkable geometry, so a room-name/whole-bounds heuristic
    would hide real level content and remove its WOK from pathing.
    """

    if bool(getattr(surface, "backdrop", False)):
        return True
    vertices = tuple(getattr(surface, "vertices", ()) or ())
    if not vertices:
        return False
    texture = str(getattr(surface, "texture", "") or "").strip().lower()
    name = str(getattr(surface, "name", "") or "").strip().lower()
    hinted = any(hint in texture for hint in _BACKDROP_TEXTURE_HINTS) or any(
        hint in name for hint in _BACKDROP_NODE_HINTS
    )
    if not hinted:
        return False
    spans = tuple(
        max(float(vertex[axis]) for vertex in vertices) - min(float(vertex[axis]) for vertex in vertices)
        for axis in range(3)
    )
    return max(spans, default=0.0) > float(extent_threshold)


def imported_mesh_room_is_backdrop(
    primitive: ImportedMeshRoomPrimitive,
    *,
    extent_threshold: float = _BACKDROP_EXTENT_THRESHOLD,
) -> bool:
    """Return True only for a backdrop-only room with no playable WOK.

    This is intentionally stricter than surface classification. Mixed rooms
    retain their gameplay WOK/pathing even when one or more render surfaces are
    hidden by the editor's Skybox visibility toggle.
    """

    surfaces = tuple(getattr(primitive, "surfaces", ()) or ())
    if not surfaces:
        return False
    if not all(imported_mesh_surface_is_backdrop(surface, extent_threshold=extent_threshold) for surface in surfaces):
        return False
    wok = getattr(primitive, "wok", None)
    return not any(
        is_walkable_walkmesh_surface(int(getattr(face, "surface", -1)))
        for face in tuple(getattr(wok, "faces", ()) or ())
    )


def imported_mesh_surface_index_for_role(primitive: ImportedMeshRoomPrimitive, role: str) -> int:
    """Resolve a viewport mesh role back to a surface index (-1 if unknown)."""

    wanted = str(role or "").strip()
    # Rooms baked from composition primitives arrive with preview roles
    # ("helper_<n>"); surface order matches, so alias them.
    if wanted.startswith("helper_") and wanted[7:].isdigit():
        wanted = imported_mesh_surface_role(int(wanted[7:]))
    for index in range(len(primitive.surfaces)):
        if imported_mesh_surface_role(index) == wanted:
            return index
    return -1


# ---------------------------------------------------------------------------
# Validation + compile


#: MDL mesh nodes index vertices with u16 values; a surface past this cannot export.
MDL_MAX_VERTICES_PER_SURFACE = 65535
#: Vanilla KOTOR rooms run low thousands of triangles; warn well before the
#: engine starts struggling with area geometry.
ROOM_TRIANGLE_WARNING_BUDGET = 15000


def validate_imported_mesh_room_primitive(primitive: ImportedMeshRoomPrimitive) -> ImportedMeshValidation:
    warnings: list[str] = []
    blocking: list[str] = []
    if not primitive.surfaces:
        blocking.append(f"Imported room {primitive.room_resref} has no surfaces.")
    total_triangles = sum(len(surface.faces) for surface in primitive.surfaces)
    if total_triangles > ROOM_TRIANGLE_WARNING_BUDGET:
        warnings.append(
            f"Imported room {primitive.room_resref} has {total_triangles} triangles;"
            f" vanilla KOTOR rooms stay in the low thousands — consider splitting or decimating."
        )
    for index, surface in enumerate(primitive.surfaces):
        role = imported_mesh_surface_role(index)
        if not surface.vertices or not surface.faces:
            blocking.append(f"Imported room {primitive.room_resref} surface {role} is empty.")
            continue
        vertex_count = len(surface.vertices)
        if vertex_count > MDL_MAX_VERTICES_PER_SURFACE:
            blocking.append(
                f"Imported room {primitive.room_resref} surface {role} has {vertex_count} vertices,"
                f" past the MDL u16 index limit ({MDL_MAX_VERTICES_PER_SURFACE}); split the surface."
            )
        for face in surface.faces:
            if min(face) < 0 or max(face) >= vertex_count:
                blocking.append(
                    f"Imported room {primitive.room_resref} surface {role} has out-of-range face indices."
                )
                break
        topology_audit = MeshTopology.build(surface.vertices, surface.faces).validate_manifold_state()
        if topology_audit.degenerate_faces:
            warnings.append(
                f"Imported room {primitive.room_resref} surface {role} has "
                f"{len(topology_audit.degenerate_faces)} degenerate face(s)."
            )
        if topology_audit.non_manifold_edges:
            warnings.append(
                f"Imported room {primitive.room_resref} surface {role} has "
                f"{len(topology_audit.non_manifold_edges)} non-manifold edge(s)."
            )
        if topology_audit.duplicate_faces:
            warnings.append(
                f"Imported room {primitive.room_resref} surface {role} has "
                f"{len(topology_audit.duplicate_faces)} overlapping duplicate face(s)."
            )
        if topology_audit.inconsistent_winding_edges:
            warnings.append(
                f"Imported room {primitive.room_resref} surface {role} has "
                f"{len(topology_audit.inconsistent_winding_edges)} inconsistent winding edge(s)."
            )
        if len(surface.uvs) not in (0, vertex_count):
            warnings.append(f"Imported room {primitive.room_resref} surface {role} UV count mismatch; UVs regenerate on compile.")
        if len(surface.uvs_lm) not in (0, vertex_count):
            blocking.append(
                f"Imported room {primitive.room_resref} surface {role} lightmap UV count does not match its vertices."
            )
        if not surface.texture:
            warnings.append(f"Imported room {primitive.room_resref} surface {role} has no texture assigned.")
    if primitive.wok is None:
        warnings.append(
            f"Imported room {primitive.room_resref} has no imported WOK; a flat floor walkmesh is derived from mesh bounds."
        )
    return ImportedMeshValidation(ok=not blocking, warnings=tuple(warnings), blocking_issues=tuple(blocking))


def _surface_primitive_mesh(primitive: ImportedMeshRoomPrimitive, index: int) -> PrimitiveMesh:
    surface = primitive.surfaces[index]
    vertex_count = len(surface.vertices)
    uvs = (
        surface.uvs
        if len(surface.uvs) == vertex_count
        else tiled_uvs_for_vertices(
            surface.vertices,
            tile_size=matched_uv_tile_size(primitive, texture=surface.texture),
        )
    )
    normals = surface.normals if len(surface.normals) == vertex_count else ()
    role = imported_mesh_surface_role(index)
    return PrimitiveMesh(
        name=str(surface.name or f"{primitive.room_resref}_{role}"),
        vertices=tuple(surface.vertices),
        faces=tuple(surface.faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        texture=str(surface.texture or ""),
        diffuse=tuple(surface.diffuse),
        ambient=tuple(surface.ambient),
        metadata={
            "role": role,
            "primitive": IMPORTED_MESH_PRIMITIVE_KIND,
            "is_backdrop": bool(imported_mesh_surface_is_backdrop(surface)),
            "lightmap": str(surface.lightmap or ""),
            "source_model": str(primitive.source_model or ""),
            "texture_names": tuple(surface.texture_names or ()),
            "tex_count": max(1, int(surface.tex_count or 1)),
            "uvs_lm": tuple(surface.uvs_lm or ()) if len(surface.uvs_lm) == vertex_count else (),
            "face_mats": tuple(surface.face_mats or ()) if len(surface.face_mats) == len(surface.faces) else (),
            "specular": tuple(surface.specular),
            "shininess": float(surface.shininess),
            "alpha": float(surface.alpha),
            "has_shadow": bool(surface.has_shadow),
            "render": bool(surface.render),
            "selfillum": tuple(surface.selfillum),
            "transparency_hint": int(surface.transparency_hint),
            "beaming": bool(surface.beaming),
            "background_geometry": bool(surface.background_geometry),
            "rotate_texture": bool(surface.rotate_texture),
            "animate_uv": bool(surface.animate_uv),
            "uv_dir_x": float(surface.uv_dir_x),
            "uv_dir_y": float(surface.uv_dir_y),
            "uv_jitter": float(surface.uv_jitter),
            "uv_jitter_speed": float(surface.uv_jitter_speed),
            "dirt_enabled": bool(surface.dirt_enabled),
            "dirt_texture": int(surface.dirt_texture),
            "dirt_coord_space": int(surface.dirt_coord_space),
            "hide_in_holograms": bool(surface.hide_in_holograms),
            "mesh_average_point": tuple(surface.mesh_average_point),
            "mesh_unknown0": bytes(surface.mesh_unknown0 or b"")[:24].ljust(24, b"\x00"),
        },
    )


def _mesh_bounds(primitive: ImportedMeshRoomPrimitive) -> tuple[Vec3, Vec3]:
    points = [point for surface in primitive.surfaces for point in surface.vertices]
    if not points:
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _fallback_floor_wok(primitive: ImportedMeshRoomPrimitive) -> WOKData:
    """Two walkable triangles across the room footprint at the lowest Z."""

    (x0, y0, z0), (x1, y1, _z1) = _mesh_bounds(primitive)
    return WOKData(
        name=str(primitive.room_resref or ""),
        verts=[(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        faces=[
            WOKFace(0, 1, 2, surface=4, adj1=-1, adj2=-1, adj3=1),
            WOKFace(0, 2, 3, surface=4, adj1=0, adj2=-1, adj3=-1),
        ],
    )


def compile_imported_mesh_room_geometry(primitive: ImportedMeshRoomPrimitive) -> AuthoredRoomGeometry:
    """Compile the imported room into render meshes plus its walkmesh."""

    validation = validate_imported_mesh_room_primitive(primitive)
    if not validation.ok:
        raise ValueError("; ".join(validation.blocking_issues))
    meshes = tuple(_surface_primitive_mesh(primitive, index) for index in range(len(primitive.surfaces)))
    backdrop_only = imported_mesh_room_is_backdrop(primitive)
    wok = (
        primitive.wok
        if primitive.wok is not None and (primitive.wok.faces or backdrop_only)
        else _fallback_floor_wok(primitive)
    )
    return AuthoredRoomGeometry(
        room_resref=str(primitive.room_resref or ""),
        room_mesh=meshes[0],
        helper_meshes=meshes[1:],
        wok=wok,
        metadata={
            "primitive": IMPORTED_MESH_PRIMITIVE_KIND,
            "source_model": str(primitive.source_model or ""),
            "surface_count": len(meshes),
            "imported_wok": primitive.wok is not None,
            "backdrop_only": backdrop_only,
            "warnings": validation.warnings,
        },
    )


# ---------------------------------------------------------------------------
# Face operations


def resolve_imported_mesh_face_target(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    target: str,
) -> tuple[int, ...]:
    """Resolve a marking-menu face target without broadening it accidentally.

    ``Material Region`` is the connected same-material flood fill, ``Same
    Texture Faces`` is the whole material slot, and ``Room Island`` is the
    connected geometric shell.  This distinction mirrors the labels shown to
    users and prevents a local edit from silently mutating every room face.
    """

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    selected = int(face_index)
    if not 0 <= selected < len(surface.faces):
        raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
    key = " ".join(str(target or "Single Face").strip().lower().split())
    if key in {"single face", "this face", "each face", "face corners"}:
        return (selected,)
    if key in {"all faces", "all mesh"}:
        return tuple(range(len(surface.faces)))

    face_mats = (
        tuple(int(value) for value in surface.face_mats)
        if len(surface.face_mats) == len(surface.faces)
        else (0,) * len(surface.faces)
    )
    material = face_mats[selected]
    if key == "same texture faces":
        return tuple(index for index, value in enumerate(face_mats) if value == material)

    topology = MeshTopology.build(surface.vertices, surface.faces)
    if key == "room island":
        for component in topology.components():
            if selected in component.faces:
                return tuple(sorted(int(index) for index in component.faces))
        return (selected,)
    if key == "material region":
        pending = [selected]
        region = {selected}
        while pending:
            current = pending.pop()
            for neighbor in topology.geometric_face_to_faces.get(current, ()):
                neighbor_index = int(neighbor)
                if neighbor_index in region or face_mats[neighbor_index] != material:
                    continue
                region.add(neighbor_index)
                pending.append(neighbor_index)
        return tuple(sorted(region))
    return (selected,)


def _compact_surface(surface: ImportedMeshSurface, faces: list[Face]) -> ImportedMeshSurface:
    """Compact through the shared stable remap while preserving all channels."""

    compacted_face_mats: list[int] = []
    if len(surface.face_mats) == len(surface.faces):
        material_queues: dict[Face, list[int]] = {}
        for source_face, material in zip(surface.faces, surface.face_mats):
            material_queues.setdefault(tuple(source_face), []).append(int(material))
        for face in faces:
            queue = material_queues.get(tuple(face), [])
            compacted_face_mats.append(queue.pop(0) if queue else 0)
    elif faces:
        compacted_face_mats = [0] * len(faces)
    compacted = compact_indexed_mesh(
        surface.vertices,
        faces,
        vertex_channels={
            "uvs": surface.uvs,
            "normals": surface.normals,
            "uvs_lm": surface.uvs_lm,
        },
    )
    return replace(
        surface,
        vertices=compacted.vertices,
        faces=tuple(tuple(int(value) for value in face) for face in compacted.faces),
        face_mats=tuple(compacted_face_mats),
        uvs=tuple(compacted.vertex_channels.get("uvs", ())),
        normals=tuple(compacted.vertex_channels.get("normals", ())),
        uvs_lm=tuple(compacted.vertex_channels.get("uvs_lm", ())),
    )


def _validate_face_indices(surface: ImportedMeshSurface, face_indices: tuple[int, ...], *, role: str) -> None:
    face_count = len(surface.faces)
    for index in face_indices:
        if not (0 <= int(index) < face_count):
            raise ValueError(f"Face index {index} out of range for surface {role} ({face_count} faces).")


def delete_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
) -> ImportedMeshRoomPrimitive:
    """Delete faces from one surface; empty surfaces are removed entirely."""

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)
    kept = [face for index, face in enumerate(surface.faces) if index not in set(wanted)]
    surfaces = list(primitive.surfaces)
    if kept:
        surfaces[surface_index] = _compact_surface(surface, kept)
    else:
        del surfaces[surface_index]
    if not surfaces:
        raise ValueError(f"Deleting these faces would leave imported room {primitive.room_resref} empty.")
    return replace(primitive, surfaces=tuple(surfaces))


def set_imported_mesh_face_texture(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
    texture: str,
) -> ImportedMeshRoomPrimitive:
    """Assign a texture to faces, splitting them into a surface of that texture.

    UVs travel with the faces so KOTOR texture swaps stay mapped without a
    re-unwrap.  Retexturing every face of a surface just renames its texture.
    """

    clean_texture = str(texture or "").strip().lower()
    if not clean_texture:
        raise ValueError("A texture resref is required.")
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)
    if str(surface.texture or "").lower() == clean_texture:
        return primitive
    surfaces = list(primitive.surfaces)
    moved_faces = [surface.faces[index] for index in wanted]
    kept_faces = [face for index, face in enumerate(surface.faces) if index not in set(wanted)]
    moved = _compact_surface(replace(surface, texture=clean_texture), moved_faces)
    if kept_faces:
        surfaces[surface_index] = _compact_surface(surface, kept_faces)
    else:
        del surfaces[surface_index]

    merge_index = next(
        (
            index
            for index, existing in enumerate(surfaces)
            if str(existing.texture or "").lower() == clean_texture
            and str(existing.lightmap or "") == str(surface.lightmap or "")
        ),
        -1,
    )
    if merge_index >= 0:
        target = surfaces[merge_index]
        offset = len(target.vertices)
        vertex_count = len(target.vertices)
        tile = matched_uv_tile_size(primitive, texture=clean_texture)
        target_uvs = target.uvs if len(target.uvs) == vertex_count else tiled_uvs_for_vertices(target.vertices, tile_size=tile)
        target_normals = target.normals if len(target.normals) == vertex_count else tuple((0.0, 0.0, 1.0) for _ in target.vertices)
        moved_uvs = moved.uvs if len(moved.uvs) == len(moved.vertices) else tiled_uvs_for_vertices(moved.vertices, tile_size=tile)
        moved_normals = moved.normals if len(moved.normals) == len(moved.vertices) else tuple((0.0, 0.0, 1.0) for _ in moved.vertices)
        target_uvs_lm = target.uvs_lm if len(target.uvs_lm) == vertex_count else ()
        moved_uvs_lm = moved.uvs_lm if len(moved.uvs_lm) == len(moved.vertices) else ()
        merged_uvs_lm = (
            tuple(target_uvs_lm) + tuple(moved_uvs_lm)
            if target_uvs_lm and moved_uvs_lm
            else ()
        )
        surfaces[merge_index] = replace(
            target,
            vertices=tuple(target.vertices) + tuple(moved.vertices),
            faces=tuple(target.faces) + tuple((a + offset, b + offset, c + offset) for a, b, c in moved.faces),
            face_mats=(
                tuple(target.face_mats) if len(target.face_mats) == len(target.faces) else (0,) * len(target.faces)
            ) + (
                tuple(moved.face_mats) if len(moved.face_mats) == len(moved.faces) else (0,) * len(moved.faces)
            ),
            uvs=tuple(target_uvs) + tuple(moved_uvs),
            normals=tuple(target_normals) + tuple(moved_normals),
            uvs_lm=merged_uvs_lm,
        )
    else:
        surfaces.append(replace(moved, name=f"{primitive.room_resref}_{clean_texture}"))
    return replace(primitive, surfaces=tuple(surfaces))


def _vec_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vec_scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _vec_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    )


def _vec_dot(a: Vec3, b: Vec3) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _vec_lerp(a: Vec3, b: Vec3, amount: float) -> Vec3:
    t = float(amount)
    return (
        a[0] + ((b[0] - a[0]) * t),
        a[1] + ((b[1] - a[1]) * t),
        a[2] + ((b[2] - a[2]) * t),
    )


def _vec_slerp(a: Vec3, b: Vec3, amount: float) -> Vec3:
    """Spherical interpolation for two normalized directions."""

    first = _vec_normalized(a)
    second = _vec_normalized(b)
    dot = max(-1.0, min(1.0, _vec_dot(first, second)))
    t = max(0.0, min(1.0, float(amount)))
    if abs(dot) > 0.9995:
        return _vec_normalized(_vec_lerp(first, second, t), fallback=first)
    angle = math.acos(dot)
    denominator = math.sin(angle)
    if abs(denominator) <= 1.0e-9:
        return first
    first_weight = math.sin((1.0 - t) * angle) / denominator
    second_weight = math.sin(t * angle) / denominator
    return _vec_normalized(
        (
            (first[0] * first_weight) + (second[0] * second_weight),
            (first[1] * first_weight) + (second[1] * second_weight),
            (first[2] * first_weight) + (second[2] * second_weight),
        ),
        fallback=first,
    )


def _vec_length(a: Vec3) -> float:
    return ((a[0] * a[0]) + (a[1] * a[1]) + (a[2] * a[2])) ** 0.5


def _vec_normalized(a: Vec3, fallback: Vec3 = (0.0, 0.0, 1.0)) -> Vec3:
    length = _vec_length(a)
    if length <= 1.0e-9:
        return fallback
    return (a[0] / length, a[1] / length, a[2] / length)


def _face_normal(surface: ImportedMeshSurface, face: Face) -> Vec3:
    a, b, c = (surface.vertices[i] for i in face)
    return _vec_normalized(_vec_cross(_vec_sub(b, a), _vec_sub(c, a)))


def _surface_arrays(
    surface: ImportedMeshSurface,
) -> tuple[list[Vec3], list[Face], list[Vec2], list[Vec3], list[Vec2]]:
    vertex_count = len(surface.vertices)
    uvs = list(surface.uvs) if len(surface.uvs) == vertex_count else list(tiled_uvs_for_vertices(surface.vertices))
    normals = list(surface.normals) if len(surface.normals) == vertex_count else [(0.0, 0.0, 1.0)] * vertex_count
    uvs_lm = list(surface.uvs_lm) if len(surface.uvs_lm) == vertex_count else []
    return list(surface.vertices), list(surface.faces), uvs, normals, uvs_lm


def extrude_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
    distance: float,
    *,
    point_normal: bool = False,
    tile_size: float = 0.0,
    direction: Vec3 | None = None,
) -> ImportedMeshRoomPrimitive:
    """Extrude a face region along its normal, creating side walls.

    The cap keeps the original UVs; each side quad gets world-density tiled
    UVs so new walls blend with vanilla texturing.  The cap is duplicated
    rather than welded to the ring — visually correct for KOTOR render
    meshes, and the WOK is untouched.

    ``direction`` overrides the pull axis (Maya world-mode extrude); the
    region normal is used when omitted.
    """

    offset_distance = float(distance)
    if abs(offset_distance) <= 1.0e-9:
        return primitive
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)
    region = [surface.faces[index] for index in wanted]
    tile = float(tile_size) if tile_size > 0.0 else matched_uv_tile_size(primitive, texture=surface.texture)

    topology = MeshTopology.build(surface.vertices, surface.faces)
    selected_half_edges = tuple(
        half_edge
        for face_index in wanted
        for half_edge in topology.get_half_edges_for_face(face_index)
    )
    unsafe_edges = {
        (min(row.geometric_origin, row.geometric_destination), max(row.geometric_origin, row.geometric_destination))
        for row in selected_half_edges
        if len(
            topology.geometric_edge_to_half_edges.get(
                (min(row.geometric_origin, row.geometric_destination), max(row.geometric_origin, row.geometric_destination)),
                (),
            )
        )
        > 2
    }
    if unsafe_edges:
        raise ValueError("Extrude requires a manifold selected region; repair non-manifold edges first.")

    vertices, faces, uvs, normals, uvs_lm = _surface_arrays(surface)
    source_face_mats = (
        tuple(int(value) for value in surface.face_mats)
        if len(surface.face_mats) == len(surface.faces)
        else (0,) * len(surface.faces)
    )

    face_normals = {index: topology.face_normals[index] for index in wanted}
    region_normal = _vec_normalized(
        (
            sum(face_normals[index][0] * topology.face_areas[index] for index in wanted),
            sum(face_normals[index][1] * topology.face_areas[index] for index in wanted),
            sum(face_normals[index][2] * topology.face_areas[index] for index in wanted),
        )
    )
    if direction is not None:
        region_normal = _vec_normalized(tuple(float(v) for v in tuple(direction)[:3]))
        point_normal = False

    def _vertex_offset(vertex_index: int) -> Vec3:
        if not point_normal:
            return _vec_scale(region_normal, offset_distance)
        adjacent = [
            face_normals[index]
            for index in wanted
            if vertex_index in surface.faces[index]
        ]
        combined = _vec_normalized(
            (
                sum(n[0] for n in adjacent),
                sum(n[1] for n in adjacent),
                sum(n[2] for n in adjacent),
            ),
            fallback=region_normal,
        )
        return _vec_scale(combined, offset_distance)

    # Cap: duplicate the region's vertices offset along the normal.
    cap_map: dict[int, int] = {}
    for face in region:
        for vertex_index in face:
            if vertex_index not in cap_map:
                cap_map[vertex_index] = len(vertices)
                vertices.append(_vec_add(surface.vertices[vertex_index], _vertex_offset(vertex_index)))
                uvs.append(uvs[vertex_index])
                normals.append(normals[vertex_index])
                if uvs_lm:
                    uvs_lm.append(uvs_lm[vertex_index])
    cap_faces = [(cap_map[a], cap_map[b], cap_map[c]) for a, b, c in region]

    # The shared topology view recognizes UV/hard-normal seam copies as one
    # geometric edge, so internal selected edges do not sprout duplicate walls.
    boundary = topology.region_boundary_half_edges(wanted)

    side_faces: list[Face] = []
    side_face_mats: list[int] = []
    v_extent = abs(offset_distance) / max(1.0e-6, tile)
    for boundary_edge in boundary:
        start, end = boundary_edge.origin, boundary_edge.destination
        pa = surface.vertices[start]
        pb = surface.vertices[end]
        pa_top = vertices[cap_map[start]]
        pb_top = vertices[cap_map[end]]
        edge_length = _vec_length(_vec_sub(pb, pa))
        u_extent = edge_length / max(1.0e-6, tile)
        side_normal = _vec_normalized(_vec_cross(_vec_sub(pb, pa), _vec_sub(pa_top, pa)))
        base = len(vertices)
        vertices.extend((pa, pb, pb_top, pa_top))
        uvs.extend(((0.0, 0.0), (u_extent, 0.0), (u_extent, v_extent), (0.0, v_extent)))
        normals.extend((side_normal,) * 4)
        if uvs_lm:
            uvs_lm.extend((uvs_lm[start], uvs_lm[end], uvs_lm[cap_map[end]], uvs_lm[cap_map[start]]))
        side_faces.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
        side_face_mats.extend((source_face_mats[boundary_edge.face],) * 2)

    wanted_set = set(wanted)
    kept_indices = [index for index in range(len(surface.faces)) if index not in wanted_set]
    kept_faces = [surface.faces[index] for index in kept_indices]
    new_faces = kept_faces + cap_faces + side_faces
    new_face_mats = (
        [source_face_mats[index] for index in kept_indices]
        + [source_face_mats[index] for index in wanted]
        + side_face_mats
    )
    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(new_faces),
        face_mats=tuple(new_face_mats),
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    rebuilt = _compact_surface(rebuilt, list(rebuilt.faces))
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    return replace(primitive, surfaces=tuple(surfaces))


def inset_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
    inset: float,
) -> ImportedMeshRoomPrimitive:
    """Inset each target face toward its centroid, creating a border ring.

    UVs interpolate toward the face's UV centroid so the original mapping is
    preserved across the inset (doorway/recess workflow).
    """

    amount = float(inset)
    if amount <= 1.0e-9:
        return primitive
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)

    vertices, faces, uvs, normals, uvs_lm = _surface_arrays(surface)
    source_face_mats = (
        tuple(int(value) for value in surface.face_mats)
        if len(surface.face_mats) == len(surface.faces)
        else (0,) * len(surface.faces)
    )
    replacement_faces: list[Face] = []
    replacement_face_mats: list[int] = []
    for face_index in wanted:
        a, b, c = surface.faces[face_index]
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        centroid = ((pa[0] + pb[0] + pc[0]) / 3.0, (pa[1] + pb[1] + pc[1]) / 3.0, (pa[2] + pb[2] + pc[2]) / 3.0)
        uv_centroid = (
            (uvs[a][0] + uvs[b][0] + uvs[c][0]) / 3.0,
            (uvs[a][1] + uvs[b][1] + uvs[c][1]) / 3.0,
        )
        lm_centroid = (
            (
                (uvs_lm[a][0] + uvs_lm[b][0] + uvs_lm[c][0]) / 3.0,
                (uvs_lm[a][1] + uvs_lm[b][1] + uvs_lm[c][1]) / 3.0,
            )
            if uvs_lm
            else None
        )
        min_reach = min(_vec_length(_vec_sub(centroid, p)) for p in (pa, pb, pc))
        ratio = max(0.05, min(0.95, amount / max(1.0e-6, min_reach)))
        inner: list[int] = []
        for corner in (a, b, c):
            point = vertices[corner]
            inner_index = len(vertices)
            vertices.append(_vec_add(point, _vec_scale(_vec_sub(centroid, point), ratio)))
            uvs.append(
                (
                    uvs[corner][0] + ((uv_centroid[0] - uvs[corner][0]) * ratio),
                    uvs[corner][1] + ((uv_centroid[1] - uvs[corner][1]) * ratio),
                )
            )
            normals.append(normals[corner])
            if uvs_lm and lm_centroid is not None:
                uvs_lm.append(
                    (
                        uvs_lm[corner][0] + ((lm_centroid[0] - uvs_lm[corner][0]) * ratio),
                        uvs_lm[corner][1] + ((lm_centroid[1] - uvs_lm[corner][1]) * ratio),
                    )
                )
            inner.append(inner_index)
        ia, ib, ic = inner
        replacement_faces.extend(
            (
                (ia, ib, ic),
                (a, b, ib),
                (a, ib, ia),
                (b, c, ic),
                (b, ic, ib),
                (c, a, ia),
                (c, ia, ic),
            )
        )
        replacement_face_mats.extend((source_face_mats[face_index],) * 7)
    wanted_set = set(wanted)
    kept_indices = [index for index in range(len(surface.faces)) if index not in wanted_set]
    kept_faces = [surface.faces[index] for index in kept_indices]
    new_faces = kept_faces + replacement_faces
    new_face_mats = [source_face_mats[index] for index in kept_indices] + replacement_face_mats
    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(new_faces),
        face_mats=tuple(new_face_mats),
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    rebuilt = _compact_surface(rebuilt, list(rebuilt.faces))
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    return replace(primitive, surfaces=tuple(surfaces))


def move_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
    delta: Vec3,
) -> ImportedMeshRoomPrimitive:
    """Translate target-face points and every co-located seam copy.

    KOTOR room meshes commonly split one geometric point into several raw
    vertices for UV, lightmap, normal, or material seams.  Moving only the raw
    indices referenced by a selected triangle opens cracks along those seams.
    Face movement therefore follows the same position-welded policy as the
    edge and vertex manipulators below.
    """

    offset = tuple(float(v) for v in tuple(delta)[:3])
    if _vec_length(offset) <= 1.0e-9:
        return primitive
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)
    moved_positions: set[tuple[float, float, float]] = set()
    for face_index in wanted:
        moved_positions.update(_position_key(surface.vertices[index]) for index in surface.faces[face_index])
    return _translate_positions(primitive, list(moved_positions), offset)


# ---------------------------------------------------------------------------
# Edge / vertex component operations (position-welded)
#
# Stock KOTOR meshes duplicate vertices at UV seams and texture-surface
# boundaries.  Component ops therefore key on rounded world POSITIONS and
# touch every co-located copy across every surface, or edits would tear the
# mesh open at seams.

_POSITION_EPSILON_DIGITS = 4


def _position_key(point: Vec3) -> tuple[float, float, float]:
    return (
        round(float(point[0]), _POSITION_EPSILON_DIGITS),
        round(float(point[1]), _POSITION_EPSILON_DIGITS),
        round(float(point[2]), _POSITION_EPSILON_DIGITS),
    )


def _resolve_component_positions(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    *,
    vertex_corner: int = -1,
    edge_corners: tuple[int, int] = (-1, -1),
) -> tuple[ImportedMeshSurface, list[tuple[float, float, float]]]:
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    if not (0 <= int(face_index) < len(surface.faces)):
        raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
    face = surface.faces[int(face_index)]
    if vertex_corner >= 0:
        corner = int(vertex_corner) % 3
        return surface, [_position_key(surface.vertices[face[corner]])]
    a, b = (int(v) % 3 for v in edge_corners)
    if a == b:
        raise ValueError("Edge corners must reference two different face corners.")
    return surface, [_position_key(surface.vertices[face[a]]), _position_key(surface.vertices[face[b]])]


def _translate_positions(
    primitive: ImportedMeshRoomPrimitive,
    positions: list[tuple[float, float, float]],
    delta: Vec3,
) -> ImportedMeshRoomPrimitive:
    wanted = set(positions)
    offset = tuple(float(v) for v in tuple(delta)[:3])
    surfaces = []
    for surface in primitive.surfaces:
        vertices = tuple(
            _vec_add(vertex, offset) if _position_key(vertex) in wanted else vertex
            for vertex in surface.vertices
        )
        surfaces.append(replace(surface, vertices=vertices) if vertices != surface.vertices else surface)
    return replace(primitive, surfaces=tuple(surfaces))


def _snap_positions(
    primitive: ImportedMeshRoomPrimitive,
    positions: list[tuple[float, float, float]],
    target: Vec3,
) -> ImportedMeshRoomPrimitive:
    wanted = set(positions)
    surfaces = []
    for surface in primitive.surfaces:
        vertices = tuple(
            tuple(target) if _position_key(vertex) in wanted else vertex for vertex in surface.vertices
        )
        surfaces.append(replace(surface, vertices=vertices) if vertices != surface.vertices else surface)
    return _drop_degenerate_faces(replace(primitive, surfaces=tuple(surfaces)))


def _drop_degenerate_faces(primitive: ImportedMeshRoomPrimitive) -> ImportedMeshRoomPrimitive:
    surfaces: list[ImportedMeshSurface] = []
    for surface in primitive.surfaces:
        kept = [
            face
            for face in surface.faces
            if len(
                {
                    _position_key(surface.vertices[face[0]]),
                    _position_key(surface.vertices[face[1]]),
                    _position_key(surface.vertices[face[2]]),
                }
            )
            == 3
        ]
        if not kept:
            continue
        if len(kept) == len(surface.faces):
            surfaces.append(surface)
        else:
            surfaces.append(_compact_surface(surface, kept))
    if not surfaces:
        raise ValueError(f"Edit would leave imported room {primitive.room_resref} empty.")
    return replace(primitive, surfaces=tuple(surfaces))


def move_imported_mesh_vertex(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    vertex_corner: int,
    delta: Vec3,
) -> ImportedMeshRoomPrimitive:
    """Translate a vertex and every co-located seam copy across all surfaces."""

    _surface, positions = _resolve_component_positions(
        primitive, mesh_role, face_index, vertex_corner=vertex_corner
    )
    return _translate_positions(primitive, positions, delta)


def move_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
    delta: Vec3,
) -> ImportedMeshRoomPrimitive:
    """Translate both edge endpoints (and their seam copies)."""

    _surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, edge_corners=edge_corners)
    return _translate_positions(primitive, positions, delta)


def extrude_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
    delta: Vec3,
    *,
    tile_size: float = 0.0,
) -> ImportedMeshRoomPrimitive:
    """Extrude one edge into a new quad offset by delta (Maya Ctrl+E on edges).

    The edge endpoints stay put; two offset copies form the far side of the
    quad.  The quad is duplicated rather than welded, matching face extrusion,
    so seams stay paintable per-face and the WOK is untouched.
    """

    offset = tuple(float(v) for v in tuple(delta)[:3])
    if _vec_length(offset) <= 1.0e-9:
        return primitive
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    if not (0 <= int(face_index) < len(surface.faces)):
        raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
    face = surface.faces[int(face_index)]
    a_corner, b_corner = (int(v) % 3 for v in edge_corners)
    if a_corner == b_corner:
        raise ValueError("Edge corners must reference two different face corners.")
    start = surface.vertices[face[a_corner]]
    end = surface.vertices[face[b_corner]]
    tile = float(tile_size) if tile_size > 0.0 else matched_uv_tile_size(primitive, texture=surface.texture)
    vertices, faces, uvs, normals, uvs_lm = _surface_arrays(surface)
    source_face_mats = (
        tuple(int(value) for value in surface.face_mats)
        if len(surface.face_mats) == len(surface.faces)
        else (0,) * len(surface.faces)
    )
    edge_length = _vec_length(_vec_sub(end, start))
    u_extent = edge_length / max(1.0e-6, tile)
    v_extent = _vec_length(offset) / max(1.0e-6, tile)
    quad_normal = _vec_normalized(_vec_cross(_vec_sub(end, start), offset))
    base = len(vertices)
    vertices.extend((start, end, _vec_add(end, offset), _vec_add(start, offset)))
    uvs.extend(((0.0, 0.0), (u_extent, 0.0), (u_extent, v_extent), (0.0, v_extent)))
    normals.extend((quad_normal,) * 4)
    if uvs_lm:
        uvs_lm.extend(
            (
                uvs_lm[face[a_corner]],
                uvs_lm[face[b_corner]],
                uvs_lm[face[b_corner]],
                uvs_lm[face[a_corner]],
            )
        )
    faces.extend(((base, base + 1, base + 2), (base, base + 2, base + 3)))
    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(faces),
        face_mats=source_face_mats + (source_face_mats[int(face_index)],) * 2,
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    return replace(primitive, surfaces=tuple(surfaces))


def _legacy_bevel_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
    amount: float,
) -> ImportedMeshRoomPrimitive:
    """Chamfer one manifold hard edge into a new renderable strip.

    This follows Maya's selected-edge contract: the original edge is replaced
    by two parallel edges and a new face.  KOTOR room meshes commonly share
    indexed vertices across planar triangle fans, so the rebuild duplicates
    the affected surface vertices per face before applying the two plane
    offsets.  Small end caps keep the result closed at both edge endpoints.

    Boundary and non-manifold edges are rejected instead of producing an open
    room seam.  The amount is clamped against the adjacent triangle altitudes
    so a large drag cannot invert those faces.
    """

    requested = abs(float(amount))
    if requested <= 1.0e-9:
        return primitive
    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    if not (0 <= int(face_index) < len(surface.faces)):
        raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
    selected_face = surface.faces[int(face_index)]
    a_corner, b_corner = (int(value) % 3 for value in edge_corners)
    if a_corner == b_corner:
        raise ValueError("Edge corners must reference two different face corners.")
    start = tuple(surface.vertices[selected_face[a_corner]])
    end = tuple(surface.vertices[selected_face[b_corner]])
    edge_vector = _vec_sub(end, start)
    edge_length = _vec_length(edge_vector)
    if edge_length <= 1.0e-8:
        raise ValueError("Cannot bevel a zero-length edge.")
    edge_unit = _vec_scale(edge_vector, 1.0 / edge_length)
    start_key, end_key = _position_key(start), _position_key(end)

    incident: list[tuple[int, Face, Vec3, Vec3, float]] = []
    for index, face in enumerate(surface.faces):
        keys = tuple(_position_key(surface.vertices[vertex_index]) for vertex_index in face)
        if start_key not in keys or end_key not in keys:
            continue
        third_index = next(
            (vertex_index for vertex_index in face if _position_key(surface.vertices[vertex_index]) not in {start_key, end_key}),
            -1,
        )
        if third_index < 0:
            continue
        normal = _face_normal(surface, face)
        inward = _vec_normalized(_vec_cross(normal, edge_unit), fallback=(0.0, 0.0, 0.0))
        third = tuple(surface.vertices[third_index])
        if sum(inward[axis] * (third[axis] - start[axis]) for axis in range(3)) < 0.0:
            inward = _vec_scale(inward, -1.0)
        altitude = abs(sum(inward[axis] * (third[axis] - start[axis]) for axis in range(3)))
        incident.append((index, face, normal, inward, altitude))
    if len(incident) != 2:
        raise ValueError(
            f"Bevel requires one manifold edge shared by exactly two faces; found {len(incident)} incident face(s)."
        )
    if abs(sum(incident[0][2][axis] * incident[1][2][axis] for axis in range(3))) > 0.999:
        raise ValueError("The selected edge is coplanar; select a hard edge between two surface planes.")

    distance = min(requested, max(1.0e-5, min(row[4] for row in incident) * 0.45))
    plane_rows = tuple(incident)
    offset_edges = tuple(
        (_vec_add(start, _vec_scale(row[3], distance)), _vec_add(end, _vec_scale(row[3], distance)))
        for row in plane_rows
    )
    vertices: list[Vec3] = []
    faces: list[Face] = []
    uvs: list[Vec2] = []
    normals: list[Vec3] = []

    def append_triangle(points: tuple[Vec3, Vec3, Vec3], desired_normal: Vec3) -> None:
        if _vec_length(_vec_cross(_vec_sub(points[1], points[0]), _vec_sub(points[2], points[0]))) <= 1.0e-8:
            return
        actual = _vec_cross(_vec_sub(points[1], points[0]), _vec_sub(points[2], points[0]))
        if sum(actual[axis] * desired_normal[axis] for axis in range(3)) < 0.0:
            points = (points[0], points[2], points[1])
        base = len(vertices)
        vertices.extend(points)
        faces.append((base, base + 1, base + 2))
        uvs.extend(tiled_uvs_for_vertices(points))
        normals.extend((desired_normal,) * 3)

    # Rebuild each original triangle.  Triangles on either adjacent plane use
    # that plane's inset copies of the selected endpoints; all other planes
    # keep the original corner and meet the generated endpoint caps.
    for face in surface.faces:
        face_normal = _face_normal(surface, face)
        plane_index = -1
        for candidate_index, row in enumerate(plane_rows):
            if sum(face_normal[axis] * row[2][axis] for axis in range(3)) > 0.999:
                plane_index = candidate_index
                break
        rebuilt_points: list[Vec3] = []
        for vertex_index in face:
            point = tuple(surface.vertices[vertex_index])
            key = _position_key(point)
            if plane_index >= 0 and key == start_key:
                point = offset_edges[plane_index][0]
            elif plane_index >= 0 and key == end_key:
                point = offset_edges[plane_index][1]
            rebuilt_points.append(point)
        append_triangle(tuple(rebuilt_points), face_normal)

    a0, b0 = offset_edges[0]
    a1, b1 = offset_edges[1]
    bevel_normal = _vec_normalized(_vec_add(plane_rows[0][2], plane_rows[1][2]), fallback=plane_rows[0][2])
    append_triangle((a0, b0, b1), bevel_normal)
    append_triangle((a0, b1, a1), bevel_normal)
    append_triangle((start, a1, a0), _vec_scale(edge_unit, -1.0))
    append_triangle((end, b0, b1), edge_unit)

    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(faces),
        uvs=tuple(uvs),
        normals=tuple(normals),
    )
    rebuilt = _compact_surface(rebuilt, list(rebuilt.faces))
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    return replace(primitive, surfaces=tuple(surfaces))


def bevel_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
    amount: float = 0.25,
    *,
    segments: int = 1,
    profile: float = 0.5,
    miter: str = "auto",
    smoothing_angle_degrees: float = 180.0,
    uv_mode: str = "preserve",
    clamp_overlap: bool = True,
    options: ImportedMeshBevelOptions | None = None,
) -> ImportedMeshRoomPrimitive:
    """Bevel one manifold hard edge without rebuilding unrelated topology.

    The operator evaluates from the immutable input primitive on every call,
    which makes it safe for an interactive preview session.  Original faces,
    UVs, lightmap UVs, normals, texture/lightmap recipe, and face ordering are
    preserved; only the selected edge's geometric one-ring is rewired.
    """

    if options is not None:
        amount = options.width
        segments = options.segments
        profile = options.profile
        miter = options.miter
        smoothing_angle_degrees = options.smoothing_angle_degrees
        uv_mode = options.uv_mode
        clamp_overlap = options.clamp_overlap
    requested = abs(float(amount))
    if requested <= 1.0e-9:
        return primitive
    segment_count = max(1, min(64, int(segments)))
    round_profile = max(0.0, min(1.0, float(profile)))
    miter_mode = str(miter or "auto").strip().lower()
    if miter_mode not in {"auto", "sharp", "patch"}:
        raise ValueError("Single-edge bevel miter must be Auto, Sharp, or Patch.")
    uv_policy = str(uv_mode or "preserve").strip().lower()
    if uv_policy not in {"preserve", "tiled", "none"}:
        raise ValueError("Bevel UV mode must be Preserve, Tiled, or None.")

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    selected_face_index = int(face_index)
    if not 0 <= selected_face_index < len(surface.faces):
        raise ValueError(f"Face index {face_index} out of range for surface {mesh_role}.")
    selected_face = surface.faces[selected_face_index]
    first_corner, second_corner = (int(value) % len(selected_face) for value in edge_corners)
    if first_corner == second_corner:
        raise ValueError("Edge corners must reference two different face corners.")

    topology = MeshTopology.build(surface.vertices, surface.faces)
    geometric_edge = topology.geometric_edge_for_face_corners(
        selected_face_index,
        (first_corner, second_corner),
    )
    edge_half_indices = topology.geometric_edge_to_half_edges.get(geometric_edge, ())
    if len(edge_half_indices) != 2:
        raise ValueError(
            "Bevel requires one manifold edge shared by exactly two faces; "
            f"found {len(edge_half_indices)} incident face(s)."
        )
    first_half, second_half = (topology.half_edges[index] for index in edge_half_indices)
    if first_half.twin != second_half.index or second_half.twin != first_half.index:
        raise ValueError("Bevel requires consistently wound adjacent faces; repair the selected edge first.")

    start_raw = selected_face[first_corner]
    end_raw = selected_face[second_corner]
    start = tuple(surface.vertices[start_raw])
    end = tuple(surface.vertices[end_raw])
    edge_vector = _vec_sub(end, start)
    edge_length = _vec_length(edge_vector)
    if edge_length <= 1.0e-8:
        raise ValueError("Cannot bevel a zero-length edge.")
    edge_unit = _vec_scale(edge_vector, 1.0 / edge_length)
    start_geometric = topology.raw_to_geometric_vertex[start_raw]
    end_geometric = topology.raw_to_geometric_vertex[end_raw]

    plane_rows: list[tuple[int, Vec3, Vec3, float]] = []
    for half_edge in (first_half, second_half):
        incident_face = surface.faces[half_edge.face]
        normal = topology.face_normals[half_edge.face]
        third_raw = next(
            (
                raw_index
                for raw_index in incident_face
                if topology.raw_to_geometric_vertex[raw_index] not in {start_geometric, end_geometric}
            ),
            -1,
        )
        if third_raw < 0:
            raise ValueError("Bevel adjacent faces must contain a third non-edge vertex.")
        inward = _vec_normalized(_vec_cross(normal, edge_unit), fallback=(0.0, 0.0, 0.0))
        third = surface.vertices[third_raw]
        if _vec_dot(inward, _vec_sub(third, start)) < 0.0:
            inward = _vec_scale(inward, -1.0)
        altitude = abs(_vec_dot(inward, _vec_sub(third, start)))
        plane_rows.append((half_edge.face, normal, inward, altitude))
    if abs(_vec_dot(plane_rows[0][1], plane_rows[1][1])) > 0.999:
        raise ValueError("The selected edge is coplanar; select a hard edge between two surface planes.")
    maximum = max(1.0e-5, min(row[3] for row in plane_rows) * 0.45)
    if not clamp_overlap and requested > maximum:
        raise ValueError(
            f"Bevel width {requested:.4f}m would invert an adjacent face; maximum safe width is {maximum:.4f}m."
        )
    distance = min(requested, maximum) if clamp_overlap else requested

    vertices, faces, uvs, normals, uvs_lm = _surface_arrays(surface)
    source_face_mats = (
        tuple(int(value) for value in surface.face_mats)
        if len(surface.face_mats) == len(surface.faces)
        else (0,) * len(surface.faces)
    )
    component_faces = next(
        (
            set(component.faces)
            for component in topology.components()
            if selected_face_index in component.faces
        ),
        {selected_face_index},
    )
    replacement_vertices: dict[tuple[int, int], int] = {}
    rewritten_faces = list(faces)
    for candidate_face_index in sorted(component_faces):
        candidate_face = surface.faces[candidate_face_index]
        face_normal = topology.face_normals[candidate_face_index]
        plane_index = next(
            (
                index
                for index, row in enumerate(plane_rows)
                if _vec_dot(face_normal, row[1]) > 0.999
            ),
            -1,
        )
        if plane_index < 0:
            continue
        changed = False
        replacement_face: list[int] = []
        for raw_index in candidate_face:
            geometric = topology.raw_to_geometric_vertex[raw_index]
            if geometric not in {start_geometric, end_geometric}:
                replacement_face.append(raw_index)
                continue
            key = (raw_index, plane_index)
            replacement_index = replacement_vertices.get(key)
            if replacement_index is None:
                replacement_index = len(vertices)
                replacement_vertices[key] = replacement_index
                vertices.append(_vec_add(surface.vertices[raw_index], _vec_scale(plane_rows[plane_index][2], distance)))
                uvs.append(uvs[raw_index])
                normals.append(normals[raw_index])
                if uvs_lm:
                    uvs_lm.append(uvs_lm[raw_index])
            replacement_face.append(replacement_index)
            changed = True
        if changed:
            rewritten_faces[candidate_face_index] = tuple(replacement_face)

    def _channel_value(channel: list, plane_index: int, geometric_vertex: int, fallback):
        face = surface.faces[plane_rows[plane_index][0]]
        raw_index = next(
            index
            for index in face
            if topology.raw_to_geometric_vertex[index] == geometric_vertex
        )
        return channel[raw_index] if channel else fallback

    plane_uvs = tuple(
        (
            _channel_value(uvs, plane_index, start_geometric, (0.0, 0.0)),
            _channel_value(uvs, plane_index, end_geometric, (0.0, 0.0)),
        )
        for plane_index in range(2)
    )
    plane_lightmap_uvs = (
        tuple(
            (
                _channel_value(uvs_lm, plane_index, start_geometric, (0.0, 0.0)),
                _channel_value(uvs_lm, plane_index, end_geometric, (0.0, 0.0)),
            )
            for plane_index in range(2)
        )
        if uvs_lm
        else ()
    )
    tile = matched_uv_tile_size(primitive, texture=surface.texture)
    dihedral_degrees = math.degrees(math.acos(max(-1.0, min(1.0, _vec_dot(plane_rows[0][1], plane_rows[1][1])))))
    smooth_strip = float(smoothing_angle_degrees) > 0.0 and dihedral_degrees <= float(smoothing_angle_degrees)
    resolved_miter = (
        ("patch" if segment_count > 1 else "sharp")
        if miter_mode == "auto"
        else miter_mode
    )

    def _offset_direction(t: float) -> Vec3:
        linear = _vec_lerp(plane_rows[0][2], plane_rows[1][2], t)
        center = _vec_add(plane_rows[0][2], plane_rows[1][2])
        arc = _vec_sub(center, _vec_slerp(plane_rows[0][2], plane_rows[1][2], 1.0 - t))
        return _vec_lerp(linear, arc, round_profile)

    line_vertices: list[tuple[int, int]] = []
    for segment_index in range(segment_count + 1):
        t = segment_index / float(segment_count)
        offset = _vec_scale(_offset_direction(t), distance)
        line_normal = (
            _vec_slerp(plane_rows[0][1], plane_rows[1][1], t)
            if smooth_strip
            else _vec_normalized(_vec_add(plane_rows[0][1], plane_rows[1][1]), fallback=plane_rows[0][1])
        )
        pair: list[int] = []
        for endpoint_index, point in enumerate((start, end)):
            vertex_index = len(vertices)
            pair.append(vertex_index)
            vertices.append(_vec_add(point, offset))
            if uv_policy == "preserve":
                first_uv = plane_uvs[0][endpoint_index]
                second_uv = plane_uvs[1][endpoint_index]
                uvs.append(
                    (
                        first_uv[0] + ((second_uv[0] - first_uv[0]) * t),
                        first_uv[1] + ((second_uv[1] - first_uv[1]) * t),
                    )
                )
            elif uv_policy == "tiled":
                uvs.append(
                    (
                        edge_length / max(1.0e-6, tile) if endpoint_index else 0.0,
                        (distance * t) / max(1.0e-6, tile),
                    )
                )
            else:
                uvs.append((0.0, 0.0))
            normals.append(line_normal)
            if uvs_lm:
                first_lm = plane_lightmap_uvs[0][endpoint_index]
                second_lm = plane_lightmap_uvs[1][endpoint_index]
                uvs_lm.append(
                    (
                        first_lm[0] + ((second_lm[0] - first_lm[0]) * t),
                        first_lm[1] + ((second_lm[1] - first_lm[1]) * t),
                    )
                )
        line_vertices.append((pair[0], pair[1]))

    generated_faces: list[Face] = []

    def _append_oriented(first: int, second: int, third: int, desired_normal: Vec3) -> None:
        actual = _vec_cross(_vec_sub(vertices[second], vertices[first]), _vec_sub(vertices[third], vertices[first]))
        if _vec_length(actual) <= 1.0e-10:
            raise ValueError("Bevel generated a degenerate triangle; reduce width or segments.")
        if _vec_dot(actual, desired_normal) < 0.0:
            second, third = third, second
        generated_faces.append((first, second, third))

    for segment_index in range(segment_count):
        start0, end0 = line_vertices[segment_index]
        start1, end1 = line_vertices[segment_index + 1]
        desired = _vec_normalized(
            _vec_add(normals[start0], normals[start1]),
            fallback=_vec_normalized(_vec_add(plane_rows[0][1], plane_rows[1][1])),
        )
        _append_oriented(start0, end0, end1, desired)
        _append_oriented(start0, end1, start1, desired)

    # A single selected edge always needs endpoint patches. Sharp converges the
    # cap at the original endpoint; Patch pulls the fan center halfway toward
    # the rounded rail average, producing a visibly broader corner. Auto uses
    # Sharp for a one-segment chamfer and Patch for a multi-segment roundover.
    cap_centers: list[int] = []
    for endpoint_index, point in enumerate((start, end)):
        track_indices = tuple(pair[endpoint_index] for pair in line_vertices)
        track_points = tuple(vertices[index] for index in track_indices)
        track_average = (
            sum(value[0] for value in track_points) / len(track_points),
            sum(value[1] for value in track_points) / len(track_points),
            sum(value[2] for value in track_points) / len(track_points),
        )
        cap_point = _vec_lerp(point, track_average, 0.5) if resolved_miter == "patch" else point
        center_index = len(vertices)
        cap_centers.append(center_index)
        vertices.append(cap_point)
        uvs.append(
            (
                sum(uvs[index][0] for index in track_indices) / len(track_indices),
                sum(uvs[index][1] for index in track_indices) / len(track_indices),
            )
        )
        normals.append(_vec_scale(edge_unit, -1.0 if endpoint_index == 0 else 1.0))
        if uvs_lm:
            uvs_lm.append(
                (
                    sum(uvs_lm[index][0] for index in track_indices) / len(track_indices),
                    sum(uvs_lm[index][1] for index in track_indices) / len(track_indices),
                )
            )
    for segment_index in range(segment_count):
        _append_oriented(
            cap_centers[0],
            line_vertices[segment_index + 1][0],
            line_vertices[segment_index][0],
            _vec_scale(edge_unit, -1.0),
        )
        _append_oriented(
            cap_centers[1],
            line_vertices[segment_index][1],
            line_vertices[segment_index + 1][1],
            edge_unit,
        )

    # Hard bevel shading needs independent face-corner normals.  Duplicate the
    # generated triangle corners while retaining coincident geometric positions;
    # the shared topology engine welds those positions for manifold auditing,
    # while Odyssey receives the split vertices required for flat shading.
    if not smooth_strip:
        hardened_faces: list[Face] = []
        for first, second, third in generated_faces:
            face_normal = _vec_normalized(
                _vec_cross(_vec_sub(vertices[second], vertices[first]), _vec_sub(vertices[third], vertices[first])),
                fallback=(0.0, 0.0, 1.0),
            )
            hardened_face: list[int] = []
            for source_index in (first, second, third):
                hardened_face.append(len(vertices))
                vertices.append(vertices[source_index])
                uvs.append(uvs[source_index])
                normals.append(face_normal)
                if uvs_lm:
                    uvs_lm.append(uvs_lm[source_index])
            hardened_faces.append(tuple(hardened_face))
        generated_faces = hardened_faces

    generated_face_start = len(rewritten_faces)
    rewritten_faces.extend(generated_faces)
    rebuilt = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(rewritten_faces),
        face_mats=source_face_mats + (source_face_mats[selected_face_index],) * len(generated_faces),
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    rebuilt = _compact_surface(rebuilt, list(rebuilt.faces))
    audit = MeshTopology.build(rebuilt.vertices, rebuilt.faces).validate_manifold_state()
    if audit.degenerate_faces or audit.non_manifold_edges:
        raise ValueError(
            "Bevel would create invalid topology "
            f"({len(audit.degenerate_faces)} degenerate face(s), "
            f"{len(audit.non_manifold_edges)} non-manifold edge(s))."
        )
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = rebuilt
    metadata = {
        **dict(primitive.metadata),
        "last_topology_edit": {
            "operation": "edge_bevel",
            "mesh_role": mesh_role,
            "source_face": selected_face_index,
            "source_edge_corners": [first_corner, second_corner],
            "width": distance,
            "requested_width": requested,
            "segments": segment_count,
            "profile": round_profile,
            "miter": miter_mode,
            "resolved_miter": resolved_miter,
            "smoothing_angle_degrees": float(smoothing_angle_degrees),
            "smooth_strip": smooth_strip,
            "uv_mode": uv_policy,
            "generated_face_start": generated_face_start,
            "generated_face_count": len(generated_faces),
            "walkmesh_policy": "requires_review",
        },
    }
    return replace(primitive, surfaces=tuple(surfaces), metadata=metadata)


def weld_imported_mesh_vertex(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    vertex_corner: int,
    *,
    max_distance: float = 0.5,
) -> ImportedMeshRoomPrimitive:
    """Snap a vertex onto its nearest neighbor position; drops collapsed faces."""

    surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, vertex_corner=vertex_corner)
    source = positions[0]
    best: Vec3 | None = None
    best_distance = float(max_distance)
    for candidate_surface in primitive.surfaces:
        for vertex in candidate_surface.vertices:
            if _position_key(vertex) == source:
                continue
            distance = _vec_length(_vec_sub(vertex, source))
            if distance < best_distance:
                best_distance = distance
                best = tuple(vertex)
    if best is None:
        raise ValueError(f"No weld target within {float(max_distance):.2f}m of the vertex.")
    return _snap_positions(primitive, [source], best)


def delete_imported_mesh_vertex_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    vertex_corner: int,
) -> ImportedMeshRoomPrimitive:
    """Delete the vertex's face fan (every face touching the position, all surfaces)."""

    _surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, vertex_corner=vertex_corner)
    wanted = set(positions)
    surfaces: list[ImportedMeshSurface] = []
    for surface in primitive.surfaces:
        kept = [
            face
            for face in surface.faces
            if not any(_position_key(surface.vertices[index]) in wanted for index in face)
        ]
        if not kept:
            continue
        surfaces.append(surface if len(kept) == len(surface.faces) else _compact_surface(surface, kept))
    if not surfaces:
        raise ValueError(f"Deleting this vertex fan would leave imported room {primitive.room_resref} empty.")
    return replace(primitive, surfaces=tuple(surfaces))


def delete_imported_mesh_edge_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
) -> ImportedMeshRoomPrimitive:
    """Delete every face (all surfaces) that uses this edge's position pair."""

    _surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, edge_corners=edge_corners)
    pair = set(positions)
    surfaces: list[ImportedMeshSurface] = []
    for surface in primitive.surfaces:
        kept = []
        for face in surface.faces:
            keys = {
                _position_key(surface.vertices[face[0]]),
                _position_key(surface.vertices[face[1]]),
                _position_key(surface.vertices[face[2]]),
            }
            if pair <= keys:
                continue
            kept.append(face)
        if not kept:
            continue
        surfaces.append(surface if len(kept) == len(surface.faces) else _compact_surface(surface, kept))
    if not surfaces:
        raise ValueError(f"Deleting this edge would leave imported room {primitive.room_resref} empty.")
    return replace(primitive, surfaces=tuple(surfaces))


def split_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
) -> ImportedMeshRoomPrimitive:
    """Insert a midpoint vertex into every face sharing the edge (seam-aware)."""

    _surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, edge_corners=edge_corners)
    key_a, key_b = positions[0], positions[1]
    surfaces: list[ImportedMeshSurface] = []
    for surface in primitive.surfaces:
        vertices, _faces, uvs, normals, uvs_lm = _surface_arrays(surface)
        new_faces: list[Face] = []
        changed = False
        for face in surface.faces:
            corner_keys = [_position_key(surface.vertices[index]) for index in face]
            split_pair = None
            for first in range(3):
                second = (first + 1) % 3
                if {corner_keys[first], corner_keys[second]} == {key_a, key_b}:
                    split_pair = (first, second)
                    break
            if split_pair is None:
                new_faces.append(face)
                continue
            changed = True
            first, second = split_pair
            third = 3 - first - second
            ia, ib, ic = face[first], face[second], face[third]
            mid_index = len(vertices)
            vertices.append(_vec_scale(_vec_add(vertices[ia], vertices[ib]), 0.5))
            uvs.append(((uvs[ia][0] + uvs[ib][0]) * 0.5, (uvs[ia][1] + uvs[ib][1]) * 0.5))
            normals.append(_vec_normalized(_vec_add(normals[ia], normals[ib])))
            if uvs_lm:
                uvs_lm.append(
                    (
                        (uvs_lm[ia][0] + uvs_lm[ib][0]) * 0.5,
                        (uvs_lm[ia][1] + uvs_lm[ib][1]) * 0.5,
                    )
                )
            # Preserve winding: (ia, ib, ic) -> (ia, mid, ic) + (mid, ib, ic).
            new_faces.extend(((ia, mid_index, ic), (mid_index, ib, ic)))
        if changed:
            surfaces.append(
                replace(
                    surface,
                    vertices=tuple(vertices),
                    faces=tuple(new_faces),
                    uvs=tuple(uvs),
                    normals=tuple(normals),
                    uvs_lm=tuple(uvs_lm),
                )
            )
        else:
            surfaces.append(surface)
    return replace(primitive, surfaces=tuple(surfaces))


def collapse_imported_mesh_edge(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
    edge_corners: tuple[int, int],
) -> ImportedMeshRoomPrimitive:
    """Merge the edge's endpoints at their midpoint; degenerate faces drop."""

    surface, positions = _resolve_component_positions(primitive, mesh_role, face_index, edge_corners=edge_corners)
    face = surface.faces[int(face_index)]
    a_corner, b_corner = (int(v) % 3 for v in edge_corners)
    midpoint = _vec_scale(
        _vec_add(surface.vertices[face[a_corner]], surface.vertices[face[b_corner]]),
        0.5,
    )
    return _snap_positions(primitive, positions, midpoint)


def split_imported_mesh_face(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_index: int,
) -> ImportedMeshRoomPrimitive:
    """Insert a centroid vertex: one triangle becomes three (Insert Point)."""

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    face = int(face_index)
    _validate_face_indices(surface, (face,), role=mesh_role)
    vertices, _faces, uvs, normals, uvs_lm = _surface_arrays(surface)
    a, b, c = surface.faces[face]
    centroid_index = len(vertices)
    vertices.append(
        (
            (vertices[a][0] + vertices[b][0] + vertices[c][0]) / 3.0,
            (vertices[a][1] + vertices[b][1] + vertices[c][1]) / 3.0,
            (vertices[a][2] + vertices[b][2] + vertices[c][2]) / 3.0,
        )
    )
    uvs.append(
        (
            (uvs[a][0] + uvs[b][0] + uvs[c][0]) / 3.0,
            (uvs[a][1] + uvs[b][1] + uvs[c][1]) / 3.0,
        )
    )
    normals.append(_vec_normalized(_vec_add(_vec_add(normals[a], normals[b]), normals[c])))
    if uvs_lm:
        uvs_lm.append(
            (
                (uvs_lm[a][0] + uvs_lm[b][0] + uvs_lm[c][0]) / 3.0,
                (uvs_lm[a][1] + uvs_lm[b][1] + uvs_lm[c][1]) / 3.0,
            )
        )
    new_faces = [f for index, f in enumerate(surface.faces) if index != face]
    new_faces.extend(((a, b, centroid_index), (b, c, centroid_index), (c, a, centroid_index)))
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = replace(
        surface,
        vertices=tuple(vertices),
        faces=tuple(new_faces),
        uvs=tuple(uvs),
        normals=tuple(normals),
        uvs_lm=tuple(uvs_lm),
    )
    return replace(primitive, surfaces=tuple(surfaces))


def flatten_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
) -> ImportedMeshRoomPrimitive:
    """Project the region's vertices onto its average plane (seam copies too)."""

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = tuple(sorted({int(index) for index in face_indices}))
    _validate_face_indices(surface, wanted, role=mesh_role)
    region_vertices: set[int] = set()
    normal_sum = (0.0, 0.0, 0.0)
    for index in wanted:
        region_vertices.update(surface.faces[index])
        normal_sum = _vec_add(normal_sum, _face_normal(surface, surface.faces[index]))
    plane_normal = _vec_normalized(normal_sum)
    points = [surface.vertices[index] for index in region_vertices]
    centroid = (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
        sum(p[2] for p in points) / len(points),
    )
    moves: dict[tuple[float, float, float], Vec3] = {}
    for index in region_vertices:
        point = surface.vertices[index]
        offset = _vec_sub(point, centroid)
        height = (offset[0] * plane_normal[0]) + (offset[1] * plane_normal[1]) + (offset[2] * plane_normal[2])
        moves[_position_key(point)] = _vec_sub(point, _vec_scale(plane_normal, height))
    surfaces = []
    for candidate in primitive.surfaces:
        vertices = tuple(moves.get(_position_key(vertex), vertex) for vertex in candidate.vertices)
        surfaces.append(replace(candidate, vertices=vertices) if vertices != candidate.vertices else candidate)
    return _drop_degenerate_faces(replace(primitive, surfaces=tuple(surfaces)))


def flip_imported_mesh_faces(
    primitive: ImportedMeshRoomPrimitive,
    mesh_role: str,
    face_indices: tuple[int, ...] | list[int],
) -> ImportedMeshRoomPrimitive:
    """Reverse the winding (and exclusive vertex normals) of the target faces."""

    surface_index = imported_mesh_surface_index_for_role(primitive, mesh_role)
    if surface_index < 0:
        raise ValueError(f"Unknown imported mesh surface role: {mesh_role!r}")
    surface = primitive.surfaces[surface_index]
    wanted = set(int(index) for index in face_indices)
    _validate_face_indices(surface, tuple(sorted(wanted)), role=mesh_role)
    flipped_faces = tuple(
        (face[0], face[2], face[1]) if index in wanted else face for index, face in enumerate(surface.faces)
    )
    flipped_vertices: set[int] = set()
    kept_vertices: set[int] = set()
    for index, face in enumerate(surface.faces):
        (flipped_vertices if index in wanted else kept_vertices).update(face)
    exclusive = flipped_vertices - kept_vertices
    vertex_count = len(surface.vertices)
    normals = surface.normals if len(surface.normals) == vertex_count else tuple((0.0, 0.0, 1.0) for _ in surface.vertices)
    normals = tuple(
        _vec_scale(normal, -1.0) if index in exclusive else normal for index, normal in enumerate(normals)
    )
    surfaces = list(primitive.surfaces)
    surfaces[surface_index] = replace(surface, faces=flipped_faces, normals=normals)
    return replace(primitive, surfaces=tuple(surfaces))


def planar_uvs_for_vertices(vertices: tuple[Vec3, ...]) -> tuple[Vec2, ...]:
    """Dominant-axis planar projection normalized to [0, 1].

    Only for previews/thumbnails.  Architecture UVs must use
    ``tiled_uvs_for_vertices`` so KOTOR tiling textures repeat at world-space
    density like vanilla rooms instead of stretching one repeat across the
    whole surface.
    """

    if not vertices:
        return ()
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    drop = spans.index(min(spans))
    axes = [axis for axis in (0, 1, 2) if axis != drop]
    u_values = [v[axes[0]] for v in vertices]
    v_values = [v[axes[1]] for v in vertices]
    u_min, v_min = min(u_values), min(v_values)
    u_span = max(1.0e-6, max(u_values) - u_min)
    v_span = max(1.0e-6, max(v_values) - v_min)
    return tuple(((u - u_min) / u_span, (v - v_min) / v_span) for u, v in zip(u_values, v_values))


#: Default world meters covered by one texture repeat when no vanilla
#: reference surface is available to sample the density from.
DEFAULT_UV_TILE_SIZE = 2.0


def tiled_uvs_for_vertices(vertices: tuple[Vec3, ...], *, tile_size: float = DEFAULT_UV_TILE_SIZE) -> tuple[Vec2, ...]:
    """World-space dominant-axis projection: one texture repeat per ``tile_size`` meters.

    This is how vanilla KOTOR architecture is mapped — tiling level textures
    at consistent world density — so new geometry textured this way blends
    with surrounding stock rooms.
    """

    if not vertices:
        return ()
    scale = 1.0 / max(1.0e-6, float(tile_size))
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    drop = spans.index(min(spans))
    axes = [axis for axis in (0, 1, 2) if axis != drop]
    return tuple((v[axes[0]] * scale, v[axes[1]] * scale) for v in vertices)


def surface_uv_tile_size(surface: ImportedMeshSurface) -> float:
    """Estimate a surface's world meters per UV repeat (0.0 when unknown).

    Sampling a vanilla surface's density lets new geometry tile at the same
    rate as the room it extends.
    """

    if len(surface.uvs) != len(surface.vertices) or not surface.faces:
        return 0.0
    total_world = 0.0
    total_uv = 0.0
    for a, b, c in surface.faces:
        try:
            pa, pb, pc = surface.vertices[a], surface.vertices[b], surface.vertices[c]
            ta, tb, tc = surface.uvs[a], surface.uvs[b], surface.uvs[c]
        except IndexError:
            continue
        abx, aby, abz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
        acx, acy, acz = pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2]
        cx = (aby * acz) - (abz * acy)
        cy = (abz * acx) - (abx * acz)
        cz = (abx * acy) - (aby * acx)
        total_world += 0.5 * ((cx * cx) + (cy * cy) + (cz * cz)) ** 0.5
        u1, v1 = tb[0] - ta[0], tb[1] - ta[1]
        u2, v2 = tc[0] - ta[0], tc[1] - ta[1]
        total_uv += 0.5 * abs((u1 * v2) - (u2 * v1))
    if total_uv <= 1.0e-9 or total_world <= 1.0e-9:
        return 0.0
    return (total_world / total_uv) ** 0.5


def matched_uv_tile_size(
    primitive: ImportedMeshRoomPrimitive,
    *,
    texture: str = "",
    default: float = DEFAULT_UV_TILE_SIZE,
) -> float:
    """Tile size matching an existing surface (same texture first, then any)."""

    wanted = str(texture or "").strip().lower()
    fallback = 0.0
    for surface in primitive.surfaces:
        tile = surface_uv_tile_size(surface)
        if tile <= 0.0:
            continue
        if wanted and str(surface.texture or "").lower() == wanted:
            return tile
        if fallback <= 0.0:
            fallback = tile
    return fallback if fallback > 0.0 else float(default)


# ---------------------------------------------------------------------------
# Stock model import


def _stock_source_light_descriptor(node: Any, source_node_index: int) -> dict[str, Any]:
    """Return a small, JSON-safe preview record for one vanilla room light.

    Converting a stock room deliberately flattens its editable render meshes,
    but the live editor still needs the room's original Aurora lights to shade
    dynamic actors and non-lightmapped surfaces.  Keep only renderer-facing
    values here; the runtime-graph export gate remains ``preserved=False`` and
    therefore cannot mistake this preview record for an engine-safe MDL node
    round trip.
    """

    def _float_tuple(value: Any, size: int, default: tuple[float, ...]) -> tuple[float, ...]:
        try:
            result = tuple(float(item) for item in tuple(value)[:size])
        except (TypeError, ValueError):
            result = ()
        if len(result) != size or not all(math.isfinite(item) for item in result):
            return default
        return result

    try:
        world_position, world_orientation = node.world_transform()
    except Exception:
        world_position = getattr(node, "position", (0.0, 0.0, 0.0))
        world_orientation = getattr(
            node,
            "rotation",
            getattr(node, "orientation", (0.0, 0.0, 0.0, 1.0)),
        )
    controller_types: list[int] = []
    for controller in tuple(getattr(node, "controllers", ()) or ()):
        try:
            value = controller.get("type", 0) if isinstance(controller, dict) else getattr(controller, "type", 0)
            controller_types.append(int(value or 0))
        except (TypeError, ValueError):
            continue
    return {
        "schema": "ghostrigger.stock_room_light_preview.v1",
        "source_node_index": int(source_node_index),
        "source_node_name": str(getattr(node, "name", "") or f"room_light_{source_node_index + 1}"),
        "position_space": "room_local",
        "position": list(_float_tuple(world_position, 3, (0.0, 0.0, 0.0))),
        "orientation": list(_float_tuple(world_orientation, 4, (0.0, 0.0, 0.0, 1.0))),
        "color": list(_float_tuple(getattr(node, "light_color", (1.0, 1.0, 1.0)), 3, (1.0, 1.0, 1.0))),
        "radius": max(0.001, float(getattr(node, "light_radius", 5.0) or 5.0)),
        "multiplier": max(0.0, float(getattr(node, "light_multiplier", 1.0) or 1.0)),
        "kind": str(getattr(node, "light_kind", "point") or "point"),
        "enabled": bool(getattr(node, "light_enabled", True)),
        "ambient_only": bool(getattr(node, "light_ambient_only", False)),
        "dynamic_type": int(getattr(node, "light_dynamic", 0) or 0),
        "shadow": bool(getattr(node, "light_shadow", False)),
        "flare": bool(getattr(node, "light_flare", False)),
        "fading": bool(getattr(node, "light_fading", False)),
        "controller_types": controller_types,
        "preview_only": True,
    }


def build_imported_mesh_primitive_from_stock_model(
    model: Any,
    *,
    room_resref: str,
    source_model: str,
    game: str = "K1",
    wok_bytes: bytes | None = None,
) -> ImportedMeshRoomPrimitive:
    """Bake a loaded KotorModel into an editable imported-mesh primitive.

    Baking rules match the stock viewport preview: world transforms applied,
    non-render and AABB (walkmesh proxy) nodes skipped, one surface per
    trimesh node.  Lightmap names are retained as authoring metadata even
    though the fullbright export path does not re-emit them yet.
    """

    try:
        from src.core.geometry import model_data as _md  # type: ignore

        aabb_flag = int(_md.NodeFlags.AABB)
        skin_flag = int(_md.NodeFlags.SKIN)
        light_flag = int(_md.NodeFlags.LIGHT)
        emitter_flag = int(_md.NodeFlags.EMITTER)
        reference_flag = int(_md.NodeFlags.REFERENCE)
    except Exception:
        try:
            from core.geometry import model_data as _md  # type: ignore

            aabb_flag = int(_md.NodeFlags.AABB)
            skin_flag = int(_md.NodeFlags.SKIN)
            light_flag = int(_md.NodeFlags.LIGHT)
            emitter_flag = int(_md.NodeFlags.EMITTER)
            reference_flag = int(_md.NodeFlags.REFERENCE)
        except Exception:
            aabb_flag = 0x0200
            skin_flag = 0x0020
            light_flag = 0x0002
            emitter_flag = 0x0004
            reference_flag = 0x0010

    surfaces: list[ImportedMeshSurface] = []
    root = getattr(model, "root_node", None)
    source_nodes: list[Any] = []
    source_stack = [root] if root is not None else []
    while source_stack:
        source_node = source_stack.pop()
        source_nodes.append(source_node)
        source_stack.extend(tuple(getattr(source_node, "children", ()) or ()))
    source_light_nodes = [
        _stock_source_light_descriptor(node, index)
        for index, node in enumerate(source_nodes)
        if int(getattr(node, "flags", 0) or 0) & light_flag
    ]
    source_runtime_graph = {
        "node_count": len(source_nodes),
        "animation_count": len(tuple(getattr(model, "animations", ()) or ())),
        "animation_names": [
            str(getattr(animation, "name", "") or "")
            for animation in tuple(getattr(model, "animations", ()) or ())
        ],
        "light_count": len(source_light_nodes),
        "light_nodes": source_light_nodes,
        "emitter_count": sum(1 for node in source_nodes if int(getattr(node, "flags", 0) or 0) & emitter_flag),
        "reference_count": sum(1 for node in source_nodes if int(getattr(node, "flags", 0) or 0) & reference_flag),
        "controller_count": sum(len(tuple(getattr(node, "controllers", ()) or ())) for node in source_nodes),
        "preserved": False,
    }
    # Traversal order and skip rules must match the stock preview's
    # _flattened_mesh_nodes so hover roles ("stock_room_<i>") map 1:1 onto
    # imported surface indices.
    stack = [root] if root is not None else []
    while stack:
        node = stack.pop()
        stack.extend(tuple(getattr(node, "children", ()) or ()))
        vertices = tuple(getattr(node, "vertices", ()) or ())
        faces = tuple(getattr(node, "faces", ()) or ())
        if not vertices or not faces:
            continue
        if not bool(getattr(node, "render", True)):
            continue
        flags = int(getattr(node, "flags", 0) or 0)
        if flags & aabb_flag:
            continue
        try:
            (wx, wy, wz), wq = node.world_transform()
        except Exception:
            (wx, wy, wz), wq = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
        qx, qy, qz, qw = (float(v) for v in wq)
        is_skin = bool(flags & skin_flag)

        def _rotate(point: tuple[float, float, float]) -> tuple[float, float, float]:
            px, py, pz = point
            tx = 2.0 * ((qy * pz) - (qz * py))
            ty = 2.0 * ((qz * px) - (qx * pz))
            tz = 2.0 * ((qx * py) - (qy * px))
            return (
                px + (qw * tx) + ((qy * tz) - (qz * ty)),
                py + (qw * ty) + ((qz * tx) - (qx * tz)),
                pz + (qw * tz) + ((qx * ty) - (qy * tx)),
            )

        def _bake(point: tuple[float, float, float]) -> tuple[float, float, float]:
            if is_skin:
                return (point[0] + wx, point[1] + wy, point[2] + wz)
            rotated = _rotate(point)
            return (rotated[0] + wx, rotated[1] + wy, rotated[2] + wz)

        baked_vertices = tuple(_bake((float(v[0]), float(v[1]), float(v[2]))) for v in vertices)
        normals = tuple(getattr(node, "normals", ()) or ())
        baked_normals = (
            tuple(
                (float(n[0]), float(n[1]), float(n[2])) if is_skin else _rotate((float(n[0]), float(n[1]), float(n[2])))
                for n in normals
            )
            if len(normals) == len(vertices)
            else ()
        )
        uvs = tuple(tuple(float(value) for value in uv[:2]) for uv in tuple(getattr(node, "uvs", ()) or ()))
        if len(uvs) != len(vertices):
            uvs = ()
        uvs_lm = tuple(tuple(float(value) for value in uv[:2]) for uv in tuple(getattr(node, "uvs_lm", ()) or ()))
        if len(uvs_lm) != len(vertices):
            uvs_lm = ()
        texture_names = tuple(str(name) for name in tuple(getattr(node, "texture_names", ()) or ()) if str(name).strip())
        texture = str(getattr(node, "texture", "") or "")
        if not texture and texture_names:
            texture = texture_names[0]
        imported_surface = ImportedMeshSurface(
            name=str(getattr(node, "name", "") or f"{room_resref}_srf{len(surfaces)}"),
            texture=texture,
            vertices=baked_vertices,
            faces=tuple(tuple(int(value) for value in face[:3]) for face in faces),
            face_mats=tuple(int(value) for value in tuple(getattr(node, "face_mats", ()) or ())),
            uvs=uvs,
            normals=baked_normals,
            lightmap=str(getattr(node, "lightmap", "") or ""),
            diffuse=tuple(float(v) for v in tuple(getattr(node, "diffuse", (1.0, 1.0, 1.0)))[:3]),
            ambient=tuple(float(v) for v in tuple(getattr(node, "ambient", (1.0, 1.0, 1.0)))[:3]),
            texture_names=texture_names or ((texture,) if texture else ()),
            tex_count=max(1, int(getattr(node, "tex_count", 1) or 1)),
            uvs_lm=uvs_lm,
            specular=tuple(float(v) for v in tuple(getattr(node, "specular", (0.0, 0.0, 0.0)))[:3]),
            shininess=float(getattr(node, "shininess", 0.0) or 0.0),
            alpha=float(getattr(node, "alpha", 1.0) if getattr(node, "alpha", None) is not None else 1.0),
            has_shadow=bool(getattr(node, "has_shadow", True)),
            render=bool(getattr(node, "render", True)),
            selfillum=tuple(float(v) for v in tuple(getattr(node, "selfillum", (0.0, 0.0, 0.0)))[:3]),
            transparency_hint=int(getattr(node, "transparency_hint", 0) or 0),
            beaming=bool(getattr(node, "beaming", False)),
            background_geometry=bool(getattr(node, "background_geometry", False)),
            rotate_texture=bool(getattr(node, "rotate_texture", False)),
            animate_uv=bool(getattr(node, "animate_uv", False)),
            uv_dir_x=float(getattr(node, "uv_dir_x", 0.0) or 0.0),
            uv_dir_y=float(getattr(node, "uv_dir_y", 0.0) or 0.0),
            uv_jitter=float(getattr(node, "uv_jitter", 0.0) or 0.0),
            uv_jitter_speed=float(getattr(node, "uv_jitter_speed", 0.0) or 0.0),
            dirt_enabled=bool(getattr(node, "dirt_enabled", False)),
            dirt_texture=int(getattr(node, "dirt_texture", 0) or 0),
            dirt_coord_space=int(getattr(node, "dirt_coord_space", 0) or 0),
            hide_in_holograms=bool(getattr(node, "hide_in_holograms", False)),
            mesh_average_point=tuple(float(v) for v in tuple(getattr(node, "mesh_average_point", (0.0, 0.0, 0.0)))[:3]),
            mesh_unknown0=bytes(getattr(node, "mesh_unknown0", b"") or b"")[:24].ljust(24, b"\x00"),
        )
        surfaces.append(
            replace(
                imported_surface,
                backdrop=imported_mesh_surface_is_backdrop(imported_surface),
            )
        )
    wok = None
    if wok_bytes:
        try:
            parsed = WOKData.from_bytes(bytes(wok_bytes))
            # A zero-face WOK is meaningful source data for vanilla visual-only
            # sky rooms (for example K1 m02aa_sky). Discarding it makes compile
            # synthesize a thousand-unit walkable floor and an AABB node.
            wok = parsed
        except Exception:
            wok = None
    return ImportedMeshRoomPrimitive(
        room_resref=str(room_resref or ""),
        surfaces=tuple(surfaces),
        source_model=str(source_model or ""),
        game=str(game or "K1").upper(),
        wok=wok,
        metadata={
            "imported_from": str(source_model or ""),
            "surface_count": len(surfaces),
            "source_runtime_graph": source_runtime_graph,
            # Retail room WOK vertices are already in module/area coordinates;
            # unlike authored geometry they must not receive the LYT position
            # again when combined for pathing or simulation.
            "wok_coordinate_space": "module" if wok is not None else "room_local",
        },
    )


# ---------------------------------------------------------------------------
# KMAP payload (base64-packed arrays)


def _pack_floats(values, dims: int) -> str:
    flat: list[float] = []
    for item in values:
        flat.extend(float(v) for v in tuple(item)[:dims])
    return base64.b64encode(struct.pack(f"<{len(flat)}f", *flat)).decode("ascii")


def _unpack_floats(payload: str, dims: int) -> tuple[tuple[float, ...], ...]:
    raw = base64.b64decode(str(payload or ""))
    count = len(raw) // 4
    flat = struct.unpack(f"<{count}f", raw)
    return tuple(tuple(flat[i : i + dims]) for i in range(0, count - (count % dims), dims))


def _pack_ints(values, dims: int) -> str:
    flat: list[int] = []
    for item in values:
        flat.extend(int(v) for v in tuple(item)[:dims])
    return base64.b64encode(struct.pack(f"<{len(flat)}i", *flat)).decode("ascii")


def _unpack_ints(payload: str, dims: int) -> tuple[tuple[int, ...], ...]:
    raw = base64.b64decode(str(payload or ""))
    count = len(raw) // 4
    flat = struct.unpack(f"<{count}i", raw)
    return tuple(tuple(flat[i : i + dims]) for i in range(0, count - (count % dims), dims))


def imported_mesh_primitive_payload(primitive: ImportedMeshRoomPrimitive) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": IMPORTED_MESH_PRIMITIVE_KIND,
        "kind": IMPORTED_MESH_PRIMITIVE_KIND,
        "room_resref": str(primitive.room_resref or ""),
        "source_model": str(primitive.source_model or ""),
        "game": str(primitive.game or "K1"),
        "metadata": dict(primitive.metadata),
        "surfaces": [
            {
                "name": str(surface.name or ""),
                "texture": str(surface.texture or ""),
                "lightmap": str(surface.lightmap or ""),
                "diffuse": [float(v) for v in surface.diffuse],
                "ambient": [float(v) for v in surface.ambient],
                "vertex_count": len(surface.vertices),
                "face_count": len(surface.faces),
                "vertices_b64": _pack_floats(surface.vertices, 3),
                "faces_b64": _pack_ints(surface.faces, 3),
                "face_mats_b64": _pack_ints(tuple((value,) for value in surface.face_mats), 1) if surface.face_mats else "",
                "uvs_b64": _pack_floats(surface.uvs, 2) if surface.uvs else "",
                "normals_b64": _pack_floats(surface.normals, 3) if surface.normals else "",
                "texture_names": [str(name) for name in surface.texture_names],
                "tex_count": max(1, int(surface.tex_count or 1)),
                "uvs_lm_b64": _pack_floats(surface.uvs_lm, 2) if surface.uvs_lm else "",
                "specular": [float(v) for v in surface.specular],
                "shininess": float(surface.shininess),
                "alpha": float(surface.alpha),
                "has_shadow": bool(surface.has_shadow),
                "render": bool(surface.render),
                "selfillum": [float(v) for v in surface.selfillum],
                "transparency_hint": int(surface.transparency_hint),
                "beaming": bool(surface.beaming),
                "background_geometry": bool(surface.background_geometry),
                "rotate_texture": bool(surface.rotate_texture),
                "animate_uv": bool(surface.animate_uv),
                "uv_dir_x": float(surface.uv_dir_x),
                "uv_dir_y": float(surface.uv_dir_y),
                "uv_jitter": float(surface.uv_jitter),
                "uv_jitter_speed": float(surface.uv_jitter_speed),
                "dirt_enabled": bool(surface.dirt_enabled),
                "dirt_texture": int(surface.dirt_texture),
                "dirt_coord_space": int(surface.dirt_coord_space),
                "hide_in_holograms": bool(surface.hide_in_holograms),
                "mesh_average_point": [float(v) for v in surface.mesh_average_point],
                "mesh_unknown0_b64": base64.b64encode(bytes(surface.mesh_unknown0 or b"")[:24].ljust(24, b"\x00")).decode("ascii"),
                "backdrop": bool(imported_mesh_surface_is_backdrop(surface)),
            }
            for surface in primitive.surfaces
        ],
    }
    if primitive.wok is not None:
        payload["wok"] = {
            "verts_b64": _pack_floats(primitive.wok.verts, 3),
            "face_stride": 10,
            "faces_b64": _pack_ints(
                [
                    (
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
                    for face in primitive.wok.faces
                ],
                10,
            ),
        }
    return payload


def imported_mesh_primitive_from_payload(data: dict[str, Any], room_resref: str) -> ImportedMeshRoomPrimitive:
    surfaces: list[ImportedMeshSurface] = []
    for entry in tuple(data.get("surfaces") or ()):
        surface = ImportedMeshSurface(
            name=str(entry.get("name") or ""),
            texture=str(entry.get("texture") or ""),
            vertices=_unpack_floats(entry.get("vertices_b64") or "", 3),
            faces=tuple(tuple(int(v) for v in face) for face in _unpack_ints(entry.get("faces_b64") or "", 3)),
            face_mats=tuple(
                int(row[0])
                for row in _unpack_ints(entry.get("face_mats_b64") or "", 1)
            ) if entry.get("face_mats_b64") else (),
            uvs=_unpack_floats(entry.get("uvs_b64") or "", 2) if entry.get("uvs_b64") else (),
            normals=_unpack_floats(entry.get("normals_b64") or "", 3) if entry.get("normals_b64") else (),
            lightmap=str(entry.get("lightmap") or ""),
            diffuse=tuple(float(v) for v in tuple(entry.get("diffuse") or (1.0, 1.0, 1.0))[:3]),
            ambient=tuple(float(v) for v in tuple(entry.get("ambient") or (1.0, 1.0, 1.0))[:3]),
            texture_names=tuple(str(name) for name in tuple(entry.get("texture_names") or ())),
            tex_count=max(1, int(entry.get("tex_count") or 1)),
            uvs_lm=_unpack_floats(entry.get("uvs_lm_b64") or "", 2) if entry.get("uvs_lm_b64") else (),
            specular=tuple(float(v) for v in tuple(entry.get("specular") or (0.0, 0.0, 0.0))[:3]),
            shininess=float(entry.get("shininess") or 0.0),
            alpha=float(entry.get("alpha", 1.0) if entry.get("alpha") is not None else 1.0),
            has_shadow=bool(entry.get("has_shadow", True)),
            render=bool(entry.get("render", True)),
            selfillum=tuple(float(v) for v in tuple(entry.get("selfillum") or (0.0, 0.0, 0.0))[:3]),
            transparency_hint=int(entry.get("transparency_hint") or 0),
            beaming=bool(entry.get("beaming", False)),
            background_geometry=bool(entry.get("background_geometry", False)),
            rotate_texture=bool(entry.get("rotate_texture", False)),
            animate_uv=bool(entry.get("animate_uv", False)),
            uv_dir_x=float(entry.get("uv_dir_x") or 0.0),
            uv_dir_y=float(entry.get("uv_dir_y") or 0.0),
            uv_jitter=float(entry.get("uv_jitter") or 0.0),
            uv_jitter_speed=float(entry.get("uv_jitter_speed") or 0.0),
            dirt_enabled=bool(entry.get("dirt_enabled", False)),
            dirt_texture=int(entry.get("dirt_texture") or 0),
            dirt_coord_space=int(entry.get("dirt_coord_space") or 0),
            hide_in_holograms=bool(entry.get("hide_in_holograms", False)),
            mesh_average_point=tuple(float(v) for v in tuple(entry.get("mesh_average_point") or (0.0, 0.0, 0.0))[:3]),
            mesh_unknown0=(
                base64.b64decode(str(entry.get("mesh_unknown0_b64") or ""))[:24].ljust(24, b"\x00")
                if entry.get("mesh_unknown0_b64")
                else b"\x00" * 24
            ),
            backdrop=bool(entry.get("backdrop", False)),
        )
        if "backdrop" not in entry:
            surface = replace(surface, backdrop=imported_mesh_surface_is_backdrop(surface))
        surfaces.append(surface)
    wok = None
    wok_data = data.get("wok")
    if isinstance(wok_data, dict):
        verts = [tuple(v) for v in _unpack_floats(wok_data.get("verts_b64") or "", 3)]
        face_stride = 10 if int(wok_data.get("face_stride") or 7) >= 10 else 7
        wok = WOKData(
            name=str(room_resref or ""),
            verts=verts,
            faces=[
                WOKFace(
                    int(row[0]),
                    int(row[1]),
                    int(row[2]),
                    surface=int(row[3]),
                    adj1=int(row[4]),
                    adj2=int(row[5]),
                    adj3=int(row[6]),
                    trans1=int(row[7]) if face_stride >= 10 else -1,
                    trans2=int(row[8]) if face_stride >= 10 else -1,
                    trans3=int(row[9]) if face_stride >= 10 else -1,
                )
                for row in _unpack_ints(wok_data.get("faces_b64") or "", face_stride)
            ],
        )
    return ImportedMeshRoomPrimitive(
        room_resref=str(room_resref or data.get("room_resref") or ""),
        surfaces=tuple(surfaces),
        source_model=str(data.get("source_model") or ""),
        game=str(data.get("game") or "K1").upper(),
        wok=wok,
        metadata=dict(data.get("metadata") or {}),
    )


__all__ = [
    "DEFAULT_UV_TILE_SIZE",
    "IMPORTED_MESH_PRIMITIVE_KIND",
    "MDL_MAX_VERTICES_PER_SURFACE",
    "ROOM_TRIANGLE_WARNING_BUDGET",
    "SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_POLICY",
    "SOURCE_RUNTIME_GRAPH_STATIC_REBUILD_VERSION",
    "ImportedMeshBevelOptions",
    "ImportedMeshRoomPrimitive",
    "ImportedMeshSurface",
    "ImportedMeshValidation",
    "build_imported_mesh_primitive_from_stock_model",
    "bevel_imported_mesh_edge",
    "collapse_imported_mesh_edge",
    "compile_imported_mesh_room_geometry",
    "delete_imported_mesh_edge_faces",
    "delete_imported_mesh_faces",
    "delete_imported_mesh_vertex_faces",
    "extrude_imported_mesh_edge",
    "extrude_imported_mesh_faces",
    "flatten_imported_mesh_faces",
    "flip_imported_mesh_faces",
    "imported_mesh_primitive_from_payload",
    "imported_mesh_primitive_payload",
    "imported_mesh_room_is_backdrop",
    "imported_mesh_has_explicit_static_runtime_rebuild",
    "imported_mesh_source_runtime_counts",
    "imported_mesh_surface_is_backdrop",
    "imported_mesh_surface_index_for_role",
    "imported_mesh_surface_role",
    "inset_imported_mesh_faces",
    "matched_uv_tile_size",
    "move_imported_mesh_edge",
    "move_imported_mesh_faces",
    "move_imported_mesh_vertex",
    "planar_uvs_for_vertices",
    "prepare_imported_mesh_for_static_runtime_rebuild",
    "resolve_imported_mesh_face_target",
    "set_imported_mesh_face_texture",
    "split_imported_mesh_edge",
    "split_imported_mesh_face",
    "surface_uv_tile_size",
    "tiled_uvs_for_vertices",
    "validate_imported_mesh_room_primitive",
    "weld_imported_mesh_vertex",
]
