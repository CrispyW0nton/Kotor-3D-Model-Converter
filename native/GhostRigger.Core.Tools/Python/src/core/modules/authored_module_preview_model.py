"""Build a live viewport model from authored Map Studio geometry."""

from __future__ import annotations

import hashlib
import json
import math
import copy
from dataclasses import dataclass
from typing import Any

from .authored_imported_mesh import authored_room_uses_unresolved_stock_geometry
from .authored_module_metadata import authored_area_metadata
from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, compile_authored_room_spec
from .authored_module_world_lighting import authored_world_lighting_settings
from .authored_room_geometry import PrimitiveMesh


@dataclass(frozen=True)
class AuthoredModulePreviewModelResult:
    """Result for the live Map Studio mesh preview."""

    model: Any | None
    room_count: int = 0
    mesh_count: int = 0
    warnings: tuple[str, ...] = ()


def _import_model_data() -> Any:
    try:
        from src.core.geometry import model_data as md  # type: ignore

        return md
    except Exception:
        from core.geometry import model_data as md  # type: ignore

        return md


def _vec3(value: object) -> tuple[float, float, float]:
    try:
        x, y, z = tuple(value)[:3]  # type: ignore[arg-type]
    except Exception:
        return (0.0, 0.0, 0.0)
    return (float(x), float(y), float(z))


def _round_tuple(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(round(float(value), 5) for value in values)


def _point_summary(points: tuple[tuple[float, float, float], ...]) -> dict[str, object]:
    if not points:
        return {"count": 0}
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    zs = [float(point[2]) for point in points]
    return {
        "count": len(points),
        "min": _round_tuple((min(xs), min(ys), min(zs))),
        "max": _round_tuple((max(xs), max(ys), max(zs))),
        "sum": _round_tuple((sum(xs), sum(ys), sum(zs))),
        "first": _round_tuple(tuple(float(value) for value in points[0][:3])),
        "last": _round_tuple(tuple(float(value) for value in points[-1][:3])),
    }


def _face_summary(faces: tuple[tuple[int, int, int], ...]) -> dict[str, object]:
    if not faces:
        return {"count": 0}
    sums = (
        sum(int(face[0]) for face in faces),
        sum(int(face[1]) for face in faces),
        sum(int(face[2]) for face in faces),
    )
    return {
        "count": len(faces),
        "sum": sums,
        "first": tuple(int(value) for value in faces[0][:3]),
        "last": tuple(int(value) for value in faces[-1][:3]),
    }


def _mesh_signature(mesh: PrimitiveMesh) -> dict[str, object]:
    vertices = tuple(mesh.vertices or ())
    faces = tuple(mesh.faces or ())
    return {
        "name": str(mesh.name or ""),
        "vertices": _point_summary(vertices),
        "faces": _face_summary(faces),
        "texture": str(mesh.texture or ""),
        "diffuse": _round_tuple(tuple(float(value) for value in mesh.diffuse[:3])),
        "ambient": _round_tuple(tuple(float(value) for value in mesh.ambient[:3])),
    }


def _preview_key(signature_rows: list[dict[str, object]]) -> str:
    payload = json.dumps(signature_rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _mesh_node(
    md: Any,
    mesh: PrimitiveMesh,
    parent: Any,
    *,
    room_resref: str,
    role: str,
    stock_room_mesh: bool = False,
) -> Any:
    vertices = [tuple(float(value) for value in point[:3]) for point in tuple(mesh.vertices or ())]
    faces = [tuple(int(value) for value in face[:3]) for face in tuple(mesh.faces or ())]
    normals = [tuple(float(value) for value in normal[:3]) for normal in tuple(mesh.normals or ())]
    if len(normals) != len(vertices):
        normals = [(0.0, 0.0, 1.0)] * len(vertices)
    uvs = [tuple(float(value) for value in uv[:2]) for uv in tuple(mesh.uvs or ())]
    if len(uvs) != len(vertices):
        uvs = [(0.0, 0.0)] * len(vertices)
    texture = str(mesh.texture or "")
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    # Imported stock surfaces carry their full render recipe (multi-texture
    # names, lightmap channel) in metadata; without it a converted room
    # renders as an untextured fallback slab.
    texture_names = [str(name) for name in tuple(metadata.get("texture_names") or ()) if str(name).strip()]
    if not texture_names:
        texture_names = [
            str(row.get("texture") or "")
            for row in tuple(metadata.get("material_table") or ())
            if isinstance(row, dict) and str(row.get("texture") or "").strip()
        ]
    if not texture_names and texture:
        texture_names = [texture]
    lightmap = str(metadata.get("lightmap") or "")
    uvs_lm = [tuple(float(v) for v in uv[:2]) for uv in tuple(metadata.get("uvs_lm") or ())]
    face_mats = [
        int(value)
        for value in tuple(metadata.get("face_mats") or metadata.get("face_material_ids") or ())
    ]
    if len(face_mats) != len(faces):
        face_mats = [0] * len(faces)
    node = md.ModelNode(
        name=str(mesh.name or f"{room_resref}_{role}"),
        flags=int(md.NodeFlags.MESH),
        vertices=vertices,
        normals=normals,
        uvs=uvs,
        faces=faces,
        face_mats=face_mats,
        texture=texture,
        texture_names=texture_names,
        tex_count=max(1, int(metadata.get("tex_count") or len(texture_names) or 1)),
        lightmap=lightmap,
        has_lightmap=bool(lightmap),
        diffuse=tuple(float(value) for value in mesh.diffuse[:3]),
        ambient=tuple(float(value) for value in mesh.ambient[:3]),
        vertex_space=0,
    )
    if len(uvs_lm) == len(vertices):
        node.uvs_lm = uvs_lm
    node.parent = parent
    setattr(node, "_gr_map_studio_room_resref", room_resref)
    setattr(node, "_gr_map_studio_mesh_role", role)
    # Keep the stable authored primitive identity on the render node.  The
    # viewport uses it to preview multi-object transforms without rebuilding
    # the full authored module (or guessing from helper_<n> roles).
    setattr(
        node,
        "_gr_map_studio_primitive_name",
        str(metadata.get("logical_primitive_name") or mesh.name or ""),
    )
    transform = dict(metadata.get("transform") or {})
    setattr(
        node,
        "_gr_map_studio_transform_translation",
        _vec3(transform.get("translation", (0.0, 0.0, 0.0))),
    )
    setattr(
        node,
        "_gr_map_studio_transform_pivot",
        _vec3(transform.get("pivot", (0.0, 0.0, 0.0))),
    )
    setattr(node, "_gr_map_studio_authored_mesh", True)
    # Imported vanilla room surfaces are safe to compact only inside their own
    # room header.  Their vertices are room-local and the header carries the
    # magnet-snap placement; promoting them into a cross-room material batch
    # can otherwise discard that spatial contract and produce floating doors,
    # missing floors, or apparently warped rooms in PIE.
    setattr(node, "_gr_map_studio_stock_mesh", bool(stock_room_mesh))
    node.compute_bounds()
    return node


def _pie_static_batch_key(
    node: Any,
    *,
    allow_flattened_stock_static: bool = False,
) -> tuple[object, ...] | None:
    """Return a strict render-state key for one batchable authored mesh.

    The batch is deliberately PIE-only.  Edit mode keeps every primitive node
    intact for selection, transforms, undo, and topology tools.
    """

    is_stock_mesh = bool(getattr(node, "_gr_map_studio_stock_mesh", False))
    is_authored_mesh = bool(
        getattr(node, "_gr_map_studio_authored_mesh", False)
        and not is_stock_mesh
    )
    is_flattened_stock_mesh = bool(
        allow_flattened_stock_static
        and is_stock_mesh
    )
    if not is_authored_mesh and not is_flattened_stock_mesh:
        return None
    if bool(getattr(node, "_gr_map_studio_editor_preview_only", False)):
        return None
    if (
        bool(getattr(node, "is_emitter", False))
        or tuple(getattr(node, "controllers", ()) or ())
        or tuple(getattr(node, "skin_data", ()) or ())
        or tuple(getattr(node, "children", ()) or ())
    ):
        return None
    if not tuple(getattr(node, "vertices", ()) or ()) or not tuple(getattr(node, "faces", ()) or ()):
        return None
    fields = (
        "flags",
        "position",
        "rotation",
        "texture",
        "texture_names",
        "lightmap",
        "bump_map",
        "diffuse",
        "ambient",
        "specular",
        "shininess",
        "alpha",
        "has_shadow",
        "render",
        "selfillum",
        "transparency_hint",
        "has_lightmap",
        "beaming",
        "background_geometry",
        "rotate_texture",
        "animate_uv",
        "uv_dir_x",
        "uv_dir_y",
        "uv_jitter",
        "uv_jitter_speed",
        "tex_count",
        "txi_blending",
        "txi_cube",
        "txi_proceduretype",
        "txi_numx",
        "txi_numy",
        "txi_fps",
        "txi_envmaptexture",
        "txi_bumpmaptexture",
        "txi_bumpmapscaling",
        "txi_rotate",
        "txi_loop",
        "txi_clamp_s",
        "txi_clamp_t",
        "txi_wateralpha",
        "txi_decal",
        "txi_isbumpmap",
        "txi_islightmap",
        "txi_specularcolour",
        "txi_alpha_test",
    )

    def stable(value: object) -> object:
        if isinstance(value, list):
            return tuple(stable(item) for item in value)
        if isinstance(value, tuple):
            return tuple(stable(item) for item in value)
        return value

    return tuple(stable(getattr(node, field, None)) for field in fields) + (
        bool(getattr(node, "_gr_map_studio_backdrop", False)),
    )


def _merge_pie_static_mesh_nodes(nodes: list[Any]) -> Any:
    """Merge compatible local-space mesh nodes into the first copied node."""

    merged = nodes[0]
    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    tangents: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    uvs_lm: list[tuple[float, float]] = []
    uvs_2: list[tuple[float, float]] = []
    uvs_3: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int]] = []
    face_mats: list[int] = []
    face_uvs: list[tuple[int, int, int]] = []
    keep_tangents = all(len(tuple(getattr(node, "tangents", ()) or ())) == len(tuple(node.vertices or ())) for node in nodes)
    keep_lm = all(len(tuple(getattr(node, "uvs_lm", ()) or ())) == len(tuple(node.vertices or ())) for node in nodes)
    keep_uv2 = all(len(tuple(getattr(node, "uvs_2", ()) or ())) == len(tuple(node.vertices or ())) for node in nodes)
    keep_uv3 = all(len(tuple(getattr(node, "uvs_3", ()) or ())) == len(tuple(node.vertices or ())) for node in nodes)
    keep_face_uvs = all(len(tuple(getattr(node, "face_uvs", ()) or ())) == len(tuple(node.faces or ())) for node in nodes)

    for node in nodes:
        node_vertices = list(tuple(node.vertices or ()))
        node_faces = list(tuple(node.faces or ()))
        vertex_offset = len(vertices)
        uv_offset = len(uvs)
        vertices.extend(node_vertices)
        node_normals = list(tuple(getattr(node, "normals", ()) or ()))
        normals.extend(node_normals if len(node_normals) == len(node_vertices) else [(0.0, 0.0, 1.0)] * len(node_vertices))
        node_uvs = list(tuple(getattr(node, "uvs", ()) or ()))
        uvs.extend(node_uvs if len(node_uvs) == len(node_vertices) else [(0.0, 0.0)] * len(node_vertices))
        if keep_tangents:
            tangents.extend(tuple(getattr(node, "tangents", ()) or ()))
        if keep_lm:
            uvs_lm.extend(tuple(getattr(node, "uvs_lm", ()) or ()))
        if keep_uv2:
            uvs_2.extend(tuple(getattr(node, "uvs_2", ()) or ()))
        if keep_uv3:
            uvs_3.extend(tuple(getattr(node, "uvs_3", ()) or ()))
        faces.extend(tuple(index + vertex_offset for index in face) for face in node_faces)
        node_face_mats = list(tuple(getattr(node, "face_mats", ()) or ()))
        face_mats.extend(node_face_mats if len(node_face_mats) == len(node_faces) else [0] * len(node_faces))
        if keep_face_uvs:
            face_uvs.extend(
                tuple(index + uv_offset for index in face)
                for face in tuple(getattr(node, "face_uvs", ()) or ())
            )

    merged.name = f"{str(getattr(merged.parent, 'name', '') or 'room')}_pie_static_batch_{str(merged.texture or 'material')}"
    merged.vertices = vertices
    merged.normals = normals
    merged.tangents = tangents if keep_tangents else []
    merged.uvs = uvs
    merged.uvs_lm = uvs_lm if keep_lm else []
    merged.uvs_2 = uvs_2 if keep_uv2 else []
    merged.uvs_3 = uvs_3 if keep_uv3 else []
    merged.faces = faces
    merged.face_mats = face_mats
    merged.face_uvs = face_uvs if keep_face_uvs else []
    setattr(merged, "_gr_map_studio_mesh_role", "pie_static_batch")
    setattr(merged, "_gr_map_studio_pie_batch_source_count", len(nodes))
    setattr(
        merged,
        "_gr_map_studio_pie_batch_primitive_names",
        tuple(str(getattr(node, "_gr_map_studio_primitive_name", "") or node.name) for node in nodes),
    )
    merged.compute_bounds()
    return merged


def batch_authored_preview_model_for_pie_in_place(
    model: Any,
    *,
    preserve_room_boundaries: bool = True,
) -> Any:
    """Batch static authored surfaces on one disposable PIE preview.

    Stock rooms, doors, creatures, placeables, animated nodes, and all original
    authoring nodes stay untouched because callers may use this only on the
    disposable runtime copy created for one PIE run.
    """

    if model is None:
        return None
    optimized = model
    root = getattr(optimized, "root_node", None)
    if root is None:
        return optimized
    source_count = 0
    batch_count = 0
    known_room_names = {
        str(value or "").strip().lower()
        for value in tuple(
            getattr(optimized, "_gr_map_studio_pie_batched_room_names", ()) or ()
        )
        if str(value or "").strip()
    }
    stock_room_names = {
        str(value or "").strip().lower()
        for value in tuple(
            getattr(optimized, "_gr_map_studio_pie_stock_room_names", ()) or ()
        )
        if str(value or "").strip()
    }
    for node in tuple(
        optimized.all_nodes()
        if callable(getattr(optimized, "all_nodes", None))
        else (root,)
    ):
        if not bool(getattr(node, "_gr_map_studio_authored_room", False)):
            continue
        room_name = str(
            getattr(node, "_gr_map_studio_room_resref", "")
            or getattr(node, "name", "")
            or ""
        ).strip().lower()
        if not room_name:
            continue
        known_room_names.add(room_name)
        if bool(getattr(node, "_gr_map_studio_stock_room", False)):
            stock_room_names.add(room_name)
    setattr(
        optimized,
        "_gr_map_studio_pie_batched_room_names",
        tuple(sorted(known_room_names)),
    )
    setattr(
        optimized,
        "_gr_map_studio_pie_stock_room_names",
        tuple(sorted(stock_room_names)),
    )
    for parent in tuple(optimized.all_nodes() if callable(getattr(optimized, "all_nodes", None)) else (root,)):
        children = list(tuple(getattr(parent, "children", ()) or ()))
        parent_room_name = str(
            getattr(parent, "_gr_map_studio_room_resref", "")
            or getattr(parent, "name", "")
            or ""
        ).strip().lower()
        known_room_parent = parent_room_name in known_room_names
        rehydrated_room = (
            known_room_parent
            and not bool(getattr(parent, "_gr_map_studio_authored_room", False))
        )
        if known_room_parent:
            setattr(parent, "_gr_map_studio_room_resref", parent_room_name)
            setattr(parent, "_gr_map_studio_authored_room", True)
            if rehydrated_room:
                setattr(parent, "_gr_map_studio_pie_rehydrated_room", True)
            setattr(
                parent,
                "_gr_map_studio_stock_room",
                parent_room_name in stock_room_names,
            )
            for child in children:
                if (
                    tuple(getattr(child, "vertices", ()) or ())
                    and tuple(getattr(child, "faces", ()) or ())
                    and not bool(getattr(child, "_gr_map_studio_pie_actor", False))
                ):
                    setattr(child, "_gr_map_studio_authored_mesh", True)
                    setattr(
                        child,
                        "_gr_map_studio_stock_mesh",
                        parent_room_name in stock_room_names,
                    )
                    setattr(
                        child,
                        "_gr_map_studio_room_resref",
                        parent_room_name,
                    )
        allow_flattened_stock_static = bool(
            str(getattr(parent, "_gr_map_studio_placement_kind", "") or "").strip().lower()
            == "door"
            or getattr(parent, "_gr_map_studio_stock_room", False)
        )
        groups: dict[tuple[object, ...], list[Any]] = {}
        for child in children:
            key = _pie_static_batch_key(
                child,
                allow_flattened_stock_static=allow_flattened_stock_static,
            )
            if key is not None:
                groups.setdefault(key, []).append(child)
        if not groups:
            continue
        replacement_by_id: dict[int, Any] = {}
        skipped_ids: set[int] = set()
        for nodes in groups.values():
            source_count += len(nodes)
            if len(nodes) <= 1:
                batch_count += 1
                continue
            merged = _merge_pie_static_mesh_nodes(nodes)
            replacement_by_id[id(nodes[0])] = merged
            skipped_ids.update(id(node) for node in nodes[1:])
            batch_count += 1
        rebuilt: list[Any] = []
        for child in children:
            if id(child) in skipped_ids:
                continue
            replacement = replacement_by_id.get(id(child), child)
            replacement.parent = parent
            rebuilt.append(replacement)
        parent.children = rebuilt

    # Generated room meshes live below one translated header per authored
    # room.  Once the per-room pass above has reduced local primitive count,
    # compatible material batches can be collapsed across those headers by
    # baking their translation into vertices.  This remains PIE-only and is
    # deliberately restricted to identity rotations; edit-mode selection and
    # every non-translational room transform remain untouched.
    room_nodes = tuple(
        node
        for node in tuple(
            optimized.all_nodes()
            if callable(getattr(optimized, "all_nodes", None))
            else ()
        )
        if bool(getattr(node, "_gr_map_studio_authored_room", False))
    )
    known_room_names.update(
        str(
            getattr(room, "_gr_map_studio_room_resref", "")
            or getattr(room, "name", "")
            or ""
        ).strip().lower()
        for room in room_nodes
    )
    known_room_names.discard("")
    known_room_names.update(
        str(value or "").strip().lower()
        for value in tuple(
            getattr(optimized, "_gr_map_studio_pie_batched_room_names", ()) or ()
        )
        if str(value or "").strip()
    )
    setattr(
        optimized,
        "_gr_map_studio_pie_batched_room_names",
        tuple(sorted(known_room_names)),
    )

    def identity_rotation(value: object) -> bool:
        rotation = tuple(value or ())
        return len(rotation) >= 4 and all(
            abs(float(rotation[index]) - expected) <= 1.0e-7
            for index, expected in enumerate((0.0, 0.0, 0.0, 1.0))
        )

    # Retail modules use VIS room groups.  Keep those boundaries in the normal
    # PIE path so the runtime can hide distant rooms as the player crosses WOK
    # portals.  The older cross-room material merge saved a few submissions in
    # tiny synthetic scenes but made a whole authored district indivisible,
    # forcing every Cantina, Sky Ramp, and stock-room surface to render at once.
    if len(room_nodes) > 1 and not preserve_room_boundaries:
        global_groups: dict[tuple[object, ...], list[tuple[Any, Any]]] = {}
        for room in room_nodes:
            if not identity_rotation(getattr(room, "rotation", ())):
                continue
            for child in tuple(getattr(room, "children", ()) or ()):
                if not identity_rotation(getattr(child, "rotation", ())):
                    continue
                key = _pie_static_batch_key(child)
                if key is not None:
                    global_groups.setdefault(key, []).append((room, child))
        for rows in global_groups.values():
            parent_ids = {id(parent) for parent, _child in rows}
            if len(rows) <= 1 or len(parent_ids) <= 1:
                continue
            baked_nodes: list[Any] = []
            for parent, child in rows:
                parent_position = tuple(
                    float(value)
                    for value in tuple(
                        getattr(parent, "position", (0.0, 0.0, 0.0))
                        or (0.0, 0.0, 0.0)
                    )[:3]
                )
                child_position = tuple(
                    float(value)
                    for value in tuple(
                        getattr(child, "position", (0.0, 0.0, 0.0))
                        or (0.0, 0.0, 0.0)
                    )[:3]
                )
                offset = tuple(
                    parent_position[index] + child_position[index]
                    for index in range(3)
                )
                child.vertices = [
                    tuple(float(vertex[index]) + offset[index] for index in range(3))
                    for vertex in tuple(child.vertices or ())
                ]
                child.position = (0.0, 0.0, 0.0)
                baked_nodes.append(child)
                parent.children = [
                    candidate
                    for candidate in tuple(parent.children or ())
                    if candidate is not child
                ]
            merged = _merge_pie_static_mesh_nodes(baked_nodes)
            merged.parent = root
            root.children.append(merged)
            batch_count -= len(rows) - 1
    # A queued viewport/resource refresh can republish the authored room
    # headers while PIE is being assembled, after the material batches above
    # were already promoted to the runtime root.  Those rehydrated headers are
    # useful transform/light containers but their mesh payload is now a second
    # complete copy of geometry already represented by the root batches.
    # Hide only those room-descendant meshes on this disposable PIE model;
    # lights and hierarchy transforms remain intact.
    root_batches = tuple(
        node
        for node in tuple(getattr(root, "children", ()) or ())
        if str(getattr(node, "_gr_map_studio_mesh_role", "") or "")
        == "pie_static_batch"
    )
    batch_name_marker = "_pie_static_batch_"
    known_room_names.update(
        str(getattr(node, "name", "") or "").strip().lower().split(
            batch_name_marker,
            1,
        )[0]
        for node in root_batches
        if batch_name_marker in str(getattr(node, "name", "") or "").strip().lower()
    )
    setattr(
        optimized,
        "_gr_map_studio_pie_batched_room_names",
        tuple(sorted(name for name in known_room_names if name)),
    )
    suppressed_rehydrated_meshes = 0
    if root_batches:
        # The room headers collected above are the live source of every mesh
        # that was *not* eligible for a cross-room material batch.  Their
        # eligible children were already removed while being promoted, so
        # suppressing the remaining children here erased unique stock-room
        # floors, ceilings, and dressing whenever any unrelated global batch
        # existed.  Only headers re-published after the batching pass lack the
        # current authored-room identity and need duplicate suppression.
        suppression_rooms: list[Any] = []
        suppression_room_ids: set[int] = set()
        original_room_ids = {id(room) for room in room_nodes}
        for child in tuple(getattr(root, "children", ()) or ()):
            child_name = str(getattr(child, "name", "") or "").strip().lower()
            child_resref = str(
                getattr(child, "_gr_map_studio_room_resref", "") or ""
            ).strip().lower()
            if (
                (
                    id(child) not in original_room_ids
                    or bool(
                        getattr(
                            child,
                            "_gr_map_studio_pie_rehydrated_room",
                            False,
                        )
                    )
                )
                and id(child) not in suppression_room_ids
                and (child_name in known_room_names or child_resref in known_room_names)
                and str(getattr(child, "_gr_map_studio_mesh_role", "") or "")
                != "pie_static_batch"
            ):
                suppression_rooms.append(child)
                suppression_room_ids.add(id(child))
        for room in suppression_rooms:
            retained_children: list[Any] = []
            for node in tuple(getattr(room, "children", ()) or ()):
                if (
                    str(getattr(node, "_gr_map_studio_mesh_role", "") or "")
                    != "pie_static_batch"
                    and tuple(getattr(node, "vertices", ()) or ())
                    and tuple(getattr(node, "faces", ()) or ())
                    and not bool(getattr(node, "_gr_map_studio_pie_rehydrated_hidden", False))
                ):
                    setattr(node, "_gr_hidden", True)
                    setattr(node, "_gr_map_studio_pie_rehydrated_hidden", True)
                    suppressed_rehydrated_meshes += 1
                    continue
                retained_children.append(node)
            room.children = retained_children
    source_count += suppressed_rehydrated_meshes
    try:
        optimized.compute_bounds()
    except Exception:
        pass
    setattr(
        optimized,
        "_gr_map_studio_pie_static_batch_summary",
        {
            "source_meshes": int(source_count),
            "runtime_batches": int(batch_count),
            "draw_calls_saved": max(0, int(source_count) - int(batch_count)),
            "rehydrated_meshes_suppressed": int(suppressed_rehydrated_meshes),
        },
    )
    return optimized


def optimize_authored_preview_model_for_pie(model: Any) -> Any:
    """Return a copied preview with static authored surfaces batched for PIE."""

    if model is None:
        return None
    return batch_authored_preview_model_for_pie_in_place(copy.deepcopy(model))


def _source_room_light_rows(room: AuthoredRoomSpec) -> tuple[dict[str, object], ...]:
    """Return normalized stock-light preview records stored on an imported room."""

    primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
    runtime_graph = dict(primitive_metadata.get("source_runtime_graph") or {})
    return tuple(row for row in tuple(runtime_graph.get("light_nodes") or ()) if isinstance(row, dict))


def _room_signature(room: AuthoredRoomSpec, meshes: tuple[PrimitiveMesh, ...]) -> dict[str, object]:
    return {
        "room": str(room.room_resref or ""),
        "position": _round_tuple(_vec3(room.position)),
        "meshes": [_mesh_signature(mesh) for mesh in meshes],
        "source_room_lights": [
            {
                "name": str(row.get("source_node_name") or ""),
                "position": _round_tuple(_vec3(row.get("position", (0.0, 0.0, 0.0)))),
                "color": _round_tuple(_vec3(row.get("color", (1.0, 1.0, 1.0)))),
                "radius": round(float(row.get("radius", 0.0) or 0.0), 6),
                "multiplier": round(float(row.get("multiplier", 0.0) or 0.0), 6),
                "dynamic_type": int(row.get("dynamic_type", 0) or 0),
            }
            for row in _source_room_light_rows(room)
        ],
    }


def _light_node(md, light, root):
    """Adapt authored light intent to the renderer's normal scene-light node."""

    metadata = dict(getattr(light, "metadata", {}) or {})
    light_type = str(getattr(light, "light_type", "point") or "point").strip().lower()
    node = md.ModelNode(
        name=str(getattr(light, "name", "") or "room_light"),
        flags=int(md.NodeFlags.LIGHT),
        position=_vec3(getattr(light, "position", (0.0, 0.0, 2.25))),
    )
    node.parent = root
    setattr(node, "_gr_map_studio_authored_light", True)
    stable_id = str(getattr(light, "light_id", "") or node.name)
    setattr(node, "_gr_light_id", f"authored_light:{stable_id}")
    setattr(node, "_gr_light_metadata", metadata)
    setattr(node, "source_type", "MapStudioPreview")
    setattr(node, "light_kind", "point" if light_type == "ambient" else light_type)
    setattr(node, "light_enabled", bool(getattr(light, "enabled", metadata.get("enabled", True))))
    setattr(node, "light_color", _vec3(getattr(light, "color", (1.0, 0.92, 0.78))))
    setattr(node, "light_radius", max(0.001, float(getattr(light, "radius", 8.0) or 8.0)))
    setattr(node, "light_multiplier", max(0.0, float(getattr(light, "intensity", 1.0) or 1.0)))
    setattr(
        node,
        "light_cone_degrees",
        float(getattr(light, "cone_angle_degrees", metadata.get("cone_angle", 45.0)) or 45.0),
    )
    setattr(node, "light_area_size", float(metadata.get("area_size", 1.0) or 1.0))
    setattr(node, "light_ambient_only", light_type == "ambient")
    setattr(node, "light_shadow", bool(getattr(light, "casts_shadows", metadata.get("casts_shadows", True))))
    affects_diffuse = bool(getattr(light, "affects_diffuse", metadata.get("affects_diffuse", True)))
    setattr(node, "light_affects_diffuse", affects_diffuse)
    setattr(node, "light_affects_specular", affects_diffuse)
    setattr(node, "light_affects_lightmap", bool(getattr(light, "affects_lightmap", metadata.get("affects_lightmap", True))))
    setattr(node, "light_affects_environment", True)
    setattr(node, "_gr_light_group_id", str(getattr(light, "bake_group", "") or ""))
    node.rotation = _light_direction_quaternion(getattr(light, "direction", (0.0, 0.0, -1.0)))
    return node


def _source_room_light_node(md, row: dict[str, object], room_node, room_resref: str, index: int):
    """Rebuild one hidden-helper vanilla light for editor/PIE shading only."""

    try:
        source_index = int(row.get("source_node_index", index) or index)
    except (TypeError, ValueError):
        source_index = index
    source_name = str(row.get("source_node_name") or f"{room_resref}_source_light_{index + 1}")
    node = md.ModelNode(
        name=source_name,
        flags=int(md.NodeFlags.LIGHT),
        position=_vec3(row.get("position", (0.0, 0.0, 0.0))),
    )
    node.parent = room_node
    orientation = tuple(row.get("orientation", (0.0, 0.0, 0.0, 1.0)) or ())
    try:
        orientation = tuple(float(value) for value in orientation[:4])
    except (TypeError, ValueError):
        orientation = ()
    node.rotation = orientation if len(orientation) == 4 else (0.0, 0.0, 0.0, 1.0)
    setattr(node, "_gr_map_studio_source_room_light", True)
    setattr(node, "_gr_light_helper_hidden", True)
    setattr(node, "_gr_light_id", f"stock_room_light:{room_resref}:{source_index}:{source_name}")
    setattr(
        node,
        "_gr_light_metadata",
        {
            "preview_only": True,
            "source": "stock_room_runtime_graph",
            "room_resref": room_resref,
            "source_node_index": source_index,
            "source_dynamic_type": int(row.get("dynamic_type", 0) or 0),
            "runtime_graph_preserved": False,
        },
    )
    setattr(node, "source_type", "MapStudioStockRoomLightPreview")
    setattr(node, "light_kind", str(row.get("kind") or "point"))
    setattr(node, "light_enabled", bool(row.get("enabled", True)))
    setattr(node, "light_color", _vec3(row.get("color", (1.0, 1.0, 1.0))))
    setattr(node, "light_radius", max(0.001, float(row.get("radius", 5.0) or 5.0)))
    setattr(node, "light_multiplier", max(0.0, float(row.get("multiplier", 1.0) or 1.0)))
    setattr(node, "light_ambient_only", bool(row.get("ambient_only", False)))
    setattr(node, "light_dynamic", int(row.get("dynamic_type", 0) or 0))
    setattr(node, "light_shadow", bool(row.get("shadow", False)))
    setattr(node, "light_flare", bool(row.get("flare", False)))
    setattr(node, "light_fading", bool(row.get("fading", False)))
    return node


def _light_direction_quaternion(direction: object) -> tuple[float, float, float, float]:
    """Rotate the renderer's local -Z light axis onto a room-space direction."""

    target = _vec3(direction)
    length = math.sqrt(sum(float(value) * float(value) for value in target))
    if length <= 1.0e-9:
        return (0.0, 0.0, 0.0, 1.0)
    x, y, z = (float(value) / length for value in target)
    dot = max(-1.0, min(1.0, -z))
    if dot >= 1.0 - 1.0e-9:
        return (0.0, 0.0, 0.0, 1.0)
    if dot <= -1.0 + 1.0e-9:
        return (1.0, 0.0, 0.0, 0.0)
    qx, qy, qz, qw = (y, -x, 0.0, 1.0 + dot)
    qlen = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    return (qx / qlen, qy / qlen, qz / qlen, qw / qlen)


def _preview_rgb(value: object, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return one normalized ARE RGB triplet for renderer preview state."""

    try:
        channels = tuple(value)[:3]  # type: ignore[arg-type]
        if len(channels) < 3:
            raise ValueError
        return tuple(max(0, min(255, int(channel))) for channel in channels)  # type: ignore[return-value]
    except Exception:
        return fallback


def _world_lighting_preview_state(project: AuthoredModuleProject) -> dict[str, object]:
    """Adapt authored ARE colors to an explicitly approximate viewport rig.

    Odyssey applies these fields differently to static, dynamic, and baked
    geometry.  Imported room surfaces already take the baked-lightmap branch,
    so the remaining scene-lit meshes are predominantly dynamic actors and
    must use ``DynAmbientColor`` without averaging it down against
    ``SunAmbientColor``.  A fixed downward editor sun remains an approximation;
    fog and sun-shadow controls remain ARE/export-only and are called out as
    unsupported in the state consumed by the UI.
    """

    settings = authored_world_lighting_settings(project)
    sun_ambient = _preview_rgb(settings.get("sun_ambient"), (64, 64, 64))
    sun_diffuse = _preview_rgb(settings.get("sun_diffuse"), (255, 255, 255))
    dynamic_ambient = _preview_rgb(settings.get("dynamic_ambient"), sun_ambient)
    area = authored_area_metadata(project.metadata, None)
    dynamic_ambient_rgb = tuple(float(channel) / 255.0 for channel in dynamic_ambient)
    diffuse_headroom = max(0.0, 1.0 - max(dynamic_ambient_rgb))
    # Read the persisted ARE field directly as well as the normalized helper.
    # This keeps a just-applied kit preset visible even when a caller still
    # holds an earlier world-lighting settings cache for the project.
    fog_enabled = bool(getattr(area, "sun_fog_on", settings.get("fog_enabled")))
    fog_color = _preview_rgb(getattr(area, "fog_color", settings.get("fog_color")), (0, 0, 0))
    fog_near = max(0.0, float(getattr(area, "fog_near", settings.get("fog_near", 0.0)) or 0.0))
    fog_far = max(fog_near, float(getattr(area, "fog_far", settings.get("fog_far", 0.0)) or 0.0))
    # A 70 m retail exterior range is appropriate in-game but almost invisible
    # in a compact Map Studio view.  Keep the ARE values verbatim for export,
    # while its preview lens shortens only the displayed range so artists can
    # actually read the atmosphere before game testing.
    fog_preview_far = max(fog_near + 0.001, min(fog_far, fog_near + (fog_far - fog_near) * 0.55))
    fog_preview_color = tuple(float(channel) / 255.0 for channel in fog_color)
    area_payload = dict(getattr(project.metadata, "metadata", {}) or {}).get("area") or {}
    shadowlands_mist = str(dict(area_payload).get("environment_style_preset") or "").strip().lower() == "architecture:k1_shadowlands"
    if shadowlands_mist:
        # The raw Shadowlands fog color is intentionally near-black in the
        # ARE, where it mixes over a full 70 m exterior.  A compact editor
        # clearing needs a shorter lens and a small cool lift to read as mist
        # rather than as unlit terrain.  This is preview-only; the ARE still
        # serializes the measured raw color/range unchanged.
        fog_preview_far = max(fog_near + 0.001, min(fog_far, fog_near + (fog_far - fog_near) * 0.30))
        fog_preview_color = (0.20, 0.24, 0.27)
    grass_texture = str(getattr(area, "grass_texture", "") or "").strip().lower()
    grass_density = max(0.0, float(getattr(area, "grass_density", 0.0) or 0.0))
    grass_quad_size = max(0.0, float(getattr(area, "grass_quad_size", 0.0) or 0.0))
    return {
        "schema": "ghostrigger.map_studio_world_lighting_preview.v1",
        "profile": str(settings.get("profile") or "standard"),
        "sun_ambient": list(sun_ambient),
        "sun_diffuse": list(sun_diffuse),
        "dynamic_ambient": list(dynamic_ambient),
        # Keep the original key for project/UI compatibility.  Its value now
        # follows Odyssey's dynamic-object ambient channel instead of an
        # editor-authored average that halved 207TEL's (45, 43, 34) ambient.
        "ambient_blend_rgb": [round(channel, 7) for channel in dynamic_ambient_rgb],
        "dynamic_ambient_rgb": [round(channel, 7) for channel in dynamic_ambient_rgb],
        "ambient_preview_source": "dynamic_ambient",
        "sun_diffuse_rgb": [round(float(channel) / 255.0, 7) for channel in sun_diffuse],
        "sun_diffuse_intensity": round(diffuse_headroom, 7),
        "sun_direction": [0.0, 0.0, -1.0],
        "preview_scope": "non_lightmapped_scene_surfaces",
        "preserves_baked_lightmaps": True,
        # These remain renderer-preview approximations—the ARE stays the
        # authoritative export—but a Map Studio exterior must no longer look
        # like bare mud until the module is launched in the game.
        "fog_previewed": fog_enabled,
        "fog_enabled": fog_enabled,
        "fog_color_rgb": [round(float(channel) / 255.0, 7) for channel in fog_color],
        "fog_preview_color_rgb": [round(float(channel), 7) for channel in fog_preview_color],
        "fog_near": fog_near,
        "fog_far": fog_far,
        "fog_preview_near": fog_near,
        "fog_preview_far": fog_preview_far,
        "fog_preview_calibration": "shadowlands_mist_lens" if shadowlands_mist else "compact_map_studio_view",
        "grass_previewed": bool(grass_texture and grass_density > 0.0 and grass_quad_size > 0.0),
        "grass_texture": grass_texture,
        "grass_density": grass_density,
        "grass_quad_size": grass_quad_size,
        "sun_shadows_previewed": False,
        "preview_only": True,
    }


def _preview_hash(value: int) -> float:
    """Return a deterministic pseudo-random value without scene RNG state."""

    value = (int(value) ^ 0x9E3779B9) & 0xFFFFFFFF
    value = (value ^ (value >> 16)) * 0x85EBCA6B & 0xFFFFFFFF
    value = (value ^ (value >> 13)) * 0xC2B2AE35 & 0xFFFFFFFF
    return float((value ^ (value >> 16)) & 0xFFFFFFFF) / float(0xFFFFFFFF)


def _shadowlands_grass_preview_mesh(
    geometry: Any,
    *,
    room_resref: str,
    state: dict[str, object],
) -> PrimitiveMesh | None:
    """Generate a lightweight, non-exporting grass-card preview over the WOK.

    ``lka_grass`` is an Odyssey ARE grass field, not a regular TGA/TPC texture
    that can be placed on an isolated model card.  Reusing it as a diffuser is
    what produces white shards.  The editor therefore previews the ARE field
    as sparse crossed blade clusters on walkable WOK triangles.  Export keeps
    the retail ARE values verbatim; this mesh exists only in the live authoring
    model and is deliberately never serialized into the module.
    """

    if not bool(state.get("grass_previewed")):
        return None
    wok = getattr(geometry, "wok", None)
    vertices_source = tuple(getattr(wok, "verts", ()) or ())
    faces_source = tuple(getattr(wok, "faces", ()) or ())
    if len(vertices_source) < 3 or not faces_source:
        return None
    try:
        from .module_format import WALKABLE_IDS
    except ImportError:
        from core.modules.module_format import WALKABLE_IDS  # type: ignore

    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    uvs: list[tuple[float, float]] = []
    quad_size = max(0.45, min(1.20, float(state.get("grass_quad_size", 0.8) or 0.8)))
    # Retail density is a grass-system setting, not a blades-per-square-metre
    # value.  This bounded conversion gives a readable authoring preview while
    # keeping sculpting/placement responsive on large WOKs.
    density_scale = max(0.16, min(0.55, float(state.get("grass_density", 5.0) or 5.0) * 0.07))

    def append_blade(x: float, y: float, z: float, angle: float, height: float, width: float) -> None:
        dx = math.cos(angle) * width
        dy = math.sin(angle) * width
        # Give the tip a slight lean so every cluster has the loose, natural
        # silhouette of the K1 grass field instead of vertical pickets.
        tip_x = x + math.cos(angle + 0.85) * width * 0.42
        tip_y = y + math.sin(angle + 0.85) * width * 0.42
        start = len(vertices)
        triangle = ((x - dx, y - dy, z), (x + dx, y + dy, z), (tip_x, tip_y, z + height))
        vertices.extend(triangle)
        normals.extend(((0.0, 0.0, 1.0),) * 3)
        uvs.extend(((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)))
        # Double-sided blade cards: Map Studio retains back-face culling for
        # KOTOR winding, so grass needs both windings to read from any camera.
        faces.extend(((start, start + 1, start + 2), (start + 2, start + 1, start)))

    room_seed = sum((index + 1) * ord(character) for index, character in enumerate(room_resref))
    for face_index, face in enumerate(faces_source):
        if int(getattr(face, "surface", 0) or 0) not in WALKABLE_IDS:
            continue
        try:
            a = tuple(float(value) for value in vertices_source[int(face.v1)][:3])
            b = tuple(float(value) for value in vertices_source[int(face.v2)][:3])
            c = tuple(float(value) for value in vertices_source[int(face.v3)][:3])
        except (AttributeError, IndexError, TypeError, ValueError):
            continue
        area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5
        cluster_count = max(1, min(72, int(math.ceil(area * density_scale))))
        for cluster_index in range(cluster_count):
            seed = room_seed + face_index * 4099 + cluster_index * 37
            root_u = math.sqrt(_preview_hash(seed))
            root_v = _preview_hash(seed + 1)
            wa = 1.0 - root_u
            wb = root_u * (1.0 - root_v)
            wc = root_u * root_v
            x = a[0] * wa + b[0] * wb + c[0] * wc
            y = a[1] * wa + b[1] * wb + c[1] * wc
            z = a[2] * wa + b[2] * wb + c[2] * wc + 0.018
            for blade_index in range(3):
                variance = _preview_hash(seed + 7 + blade_index * 5)
                append_blade(
                    x,
                    y,
                    z,
                    angle=(variance + blade_index / 3.0) * math.tau,
                    height=quad_size * (0.58 + _preview_hash(seed + 13 + blade_index) * 0.58),
                    width=quad_size * (0.032 + _preview_hash(seed + 17 + blade_index) * 0.026),
                )
    if not faces:
        return None
    return PrimitiveMesh(
        name=f"{room_resref}_shadowlands_grass_preview",
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        diffuse=(0.12, 0.18, 0.095),
        ambient=(0.32, 0.38, 0.22),
        metadata={
            "primitive": "map_studio_shadowlands_grass_preview",
            "editor_preview_only": True,
            "source_are_grass_texture": str(state.get("grass_texture") or "lka_grass"),
            "source_are_grass_density": float(state.get("grass_density", 0.0) or 0.0),
            "blade_cluster_count": len(faces) // 6,
            "selfillum": (0.055, 0.075, 0.035),
        },
    )


def _world_lighting_preview_nodes(md: Any, root: Any, state: dict[str, object]) -> tuple[Any, Any]:
    """Build hidden-helper LIGHT nodes used by every GPU viewport backend."""

    ambient = md.ModelNode(
        name="_gr_world_ambient_preview",
        flags=int(md.NodeFlags.LIGHT),
    )
    ambient.parent = root
    ambient.light_kind = "directional"
    ambient.light_enabled = True
    ambient.light_ambient_only = True
    ambient.light_color = _vec3(state.get("ambient_blend_rgb", (0.25, 0.25, 0.25)))
    ambient.light_multiplier = 1.0
    ambient.light_radius = 1_000_000.0
    ambient.light_shadow = False

    sun = md.ModelNode(
        name="_gr_world_sun_preview",
        flags=int(md.NodeFlags.LIGHT),
    )
    sun.parent = root
    sun.light_kind = "directional"
    sun.light_enabled = float(state.get("sun_diffuse_intensity", 0.0) or 0.0) > 1.0e-7
    sun.light_ambient_only = False
    sun.light_color = _vec3(state.get("sun_diffuse_rgb", (1.0, 1.0, 1.0)))
    sun.light_multiplier = float(state.get("sun_diffuse_intensity", 0.0) or 0.0)
    sun.light_radius = 1_000_000.0
    sun.light_shadow = False

    for node, channel in ((ambient, "ambient_blend"), (sun, "sun_diffuse")):
        setattr(node, "_gr_map_studio_world_light", True)
        setattr(node, "_gr_light_helper_hidden", True)
        setattr(node, "_gr_light_id", f"map_studio_world_preview:{channel}")
        setattr(
            node,
            "_gr_light_metadata",
            {
                "preview_only": True,
                "world_channel": channel,
                "fog_previewed": False,
                "sun_shadows_previewed": False,
            },
        )
        setattr(node, "source_type", "MapStudioWorldPreview")
        setattr(node, "light_fading", False)
    return ambient, sun


def build_authored_module_preview_model(
    project: AuthoredModuleProject,
    *,
    include_backdrops: bool = False,
) -> AuthoredModulePreviewModelResult:
    """Compile authored KMAP room geometry into the viewport's normal KotorModel path."""

    md = _import_model_data()
    root = md.ModelNode(name=str(project.module_root or "map_studio_preview"), flags=int(md.NodeFlags.HEADER))
    world_lighting_preview = _world_lighting_preview_state(project)
    warnings: list[str] = []
    signature_rows: list[dict[str, object]] = []
    room_count = 0
    mesh_count = 0
    source_room_light_count = 0
    playable_points: list[tuple[float, float, float]] = []
    authored_room_resrefs: list[str] = []
    stock_room_resrefs: list[str] = []

    backdrop_room_resrefs: list[str] = []
    hidden_backdrop_surface_count = 0
    for room in tuple(project.rooms or ()):
        room_resref = str(room.room_resref or "room")
        room_metadata = dict(getattr(room, "metadata", {}) or {})
        if authored_room_uses_unresolved_stock_geometry(room):
            warnings.append(
                f"Room {room_resref} has no resolved stock model; its import placeholder was excluded from preview."
            )
            continue
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            warnings.append(f"Room {room_resref} could not compile for preview: {exc}")
            continue
        meshes = (geometry.room_mesh,) + tuple(geometry.helper_meshes or ())
        meshes = tuple(mesh for mesh in meshes if mesh.vertices and mesh.faces)
        if not meshes:
            warnings.append(f"Room {room_resref} has no previewable render mesh.")
            continue

        declared_room_backdrop = bool(room_metadata.get("backdrop_only") or room_metadata.get("is_backdrop"))
        mesh_rows: list[tuple[int, PrimitiveMesh, bool]] = []
        for index, mesh in enumerate(meshes):
            mesh_metadata = dict(getattr(mesh, "metadata", {}) or {})
            surface_backdrop = bool(mesh_metadata.get("is_backdrop", declared_room_backdrop))
            mesh_rows.append((index, mesh, surface_backdrop))
        room_backdrop_only = bool(room_metadata.get("backdrop_only")) or (
            declared_room_backdrop and all(row[2] for row in mesh_rows)
        )
        visible_mesh_rows = [row for row in mesh_rows if include_backdrops or not row[2]]
        hidden_backdrop_surface_count += sum(1 for row in mesh_rows if row[2] and not include_backdrops)
        if not visible_mesh_rows:
            backdrop_room_resrefs.append(room_resref)
            continue

        compiled_resref = str(geometry.room_resref or room_resref)
        room_node = md.ModelNode(
            name=compiled_resref,
            flags=int(md.NodeFlags.HEADER),
            position=_vec3(room.position),
        )
        room_node.parent = root
        setattr(room_node, "_gr_map_studio_room_resref", compiled_resref)
        setattr(room_node, "_gr_map_studio_authored_room", True)
        setattr(room_node, "_gr_map_studio_backdrop", room_backdrop_only)
        primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
        stock_room = bool(
            primitive_metadata.get("imported_from")
            or primitive_metadata.get("environment_kit_source_room")
            or type(getattr(room, "primitive", None)).__name__ == "ImportedMeshRoomPrimitive"
        )
        setattr(room_node, "_gr_map_studio_stock_room", stock_room)
        authored_room_resrefs.append(compiled_resref)
        if stock_room:
            stock_room_resrefs.append(compiled_resref)
        for index, mesh, surface_backdrop in visible_mesh_rows:
            role = "render" if index == 0 else str(getattr(mesh, "metadata", {}).get("role", "") or f"helper_{index}")
            mesh_node = _mesh_node(
                md,
                mesh,
                room_node,
                room_resref=compiled_resref,
                role=role,
                stock_room_mesh=stock_room,
            )
            setattr(mesh_node, "_gr_map_studio_backdrop", surface_backdrop)
            room_node.children.append(mesh_node)
            mesh_count += 1
        grass_preview = _shadowlands_grass_preview_mesh(
            geometry,
            room_resref=compiled_resref,
            state=world_lighting_preview,
        )
        if grass_preview is not None:
            grass_node = _mesh_node(
                md,
                grass_preview,
                room_node,
                room_resref=compiled_resref,
                role="shadowlands_grass_preview",
            )
            grass_node.selfillum = tuple(grass_preview.metadata["selfillum"])
            setattr(grass_node, "_gr_map_studio_editor_preview_only", True)
            room_node.children.append(grass_node)
            mesh_count += 1
        for light_index, light_row in enumerate(_source_room_light_rows(room)):
            try:
                room_node.children.append(
                    _source_room_light_node(md, light_row, room_node, compiled_resref, light_index)
                )
                source_room_light_count += 1
            except Exception as exc:
                warnings.append(
                    f"Stock room light {light_row.get('source_node_name', light_index + 1)} in {compiled_resref} "
                    f"could not preview: {exc}"
                )
        root.children.append(room_node)
        room_count += 1
        signature_rows.append(_room_signature(room, meshes))
        room_offset = _vec3(room.position)
        playable_points.extend(
            (
                float(vertex[0]) + room_offset[0],
                float(vertex[1]) + room_offset[1],
                float(vertex[2]) + room_offset[2],
            )
            for _index, mesh, surface_backdrop in mesh_rows
            if not surface_backdrop
            for vertex in tuple(mesh.vertices or ())
        )

    if hidden_backdrop_surface_count and not include_backdrops:
        room_summary = f" ({', '.join(backdrop_room_resrefs)})" if backdrop_room_resrefs else ""
        warnings.append(
            f"Hid {hidden_backdrop_surface_count} skybox/backdrop surface(s) from the edit view"
            f"{room_summary}; they still export and render in-game."
        )

    world_light_nodes = _world_lighting_preview_nodes(md, root, world_lighting_preview)
    root.children.extend(world_light_nodes)

    light_count = 0
    for light in tuple(getattr(project, "lights", ()) or ()):
        try:
            root.children.append(_light_node(md, light, root))
            light_count += 1
        except Exception as exc:
            warnings.append(f"Authored light {getattr(light, 'name', 'room_light')} could not preview: {exc}")

    if mesh_count <= 0:
        return AuthoredModulePreviewModelResult(model=None, room_count=room_count, mesh_count=0, warnings=tuple(warnings))

    model = md.KotorModel(
        name=str(project.module_root or "map_studio_preview"),
        supermodel="NULL",
        classification="area",
        game_version=md.GameVersion.K2 if str(project.game).upper() == "K2" else md.GameVersion.K1,
        model_type=int(md.ModelClassification.EFFECT),
        root_node=root,
    )
    model.disable_fog = not bool(world_lighting_preview.get("fog_previewed"))
    try:
        model.compute_all_tangents()
    except Exception:
        pass
    model.compute_bounds()
    if playable_points:
        minimum = tuple(min(point[axis] for point in playable_points) for axis in range(3))
        maximum = tuple(max(point[axis] for point in playable_points) for axis in range(3))
        setattr(model, "_gr_bounds_prepared", True)
        setattr(model, "_gr_render_bounds", (minimum, maximum))
    signature_rows.append(
        {
            "include_backdrops": bool(include_backdrops),
            "world_lighting_preview": world_lighting_preview,
            "lights": [
                {
                    "name": str(getattr(light, "name", "") or ""),
                    "position": _round_tuple(_vec3(getattr(light, "position", (0.0, 0.0, 0.0)))),
                    "color": _round_tuple(_vec3(getattr(light, "color", (1.0, 1.0, 1.0)))),
                    "radius": round(float(getattr(light, "radius", 0.0) or 0.0), 6),
                    "intensity": round(float(getattr(light, "intensity", 0.0) or 0.0), 6),
                    "type": str(getattr(light, "light_type", "point") or "point"),
                }
                for light in tuple(getattr(project, "lights", ()) or ())
            ],
        }
    )
    key = _preview_key(signature_rows)
    setattr(model, "_gr_map_studio_preview_model", True)
    setattr(model, "_gr_map_studio_preview_key", key)
    # Keep room identity on the model as well as the live node wrappers.
    # Viewport resource publication may recreate room headers without carrying
    # dynamic Python attributes.  PIE can then rehydrate the headers by name
    # before its first batching pass instead of submitting every wall panel.
    setattr(
        model,
        "_gr_map_studio_pie_batched_room_names",
        tuple(sorted({str(value).strip().lower() for value in authored_room_resrefs if str(value).strip()})),
    )
    setattr(
        model,
        "_gr_map_studio_pie_stock_room_names",
        tuple(sorted({str(value).strip().lower() for value in stock_room_resrefs if str(value).strip()})),
    )
    setattr(model, "_gr_map_studio_world_lighting_preview", dict(world_lighting_preview))
    setattr(
        model,
        "_gr_map_studio_preview_summary",
        {
            "rooms": room_count,
            "meshes": mesh_count,
            "lights": light_count,
            "source_room_lights": source_room_light_count,
            "world_preview_lights": len(world_light_nodes),
            "warnings": tuple(warnings),
        },
    )
    return AuthoredModulePreviewModelResult(model=model, room_count=room_count, mesh_count=mesh_count, warnings=tuple(warnings))
