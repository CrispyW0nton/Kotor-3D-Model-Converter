"""Map Studio export-object boundary summaries.

The Level Editor stores editable authored intent, but modders need to know
which objects/rooms will become independent MDL/MDX/WOK outputs before they
leave GhostRigger for UVs or texture work.  This module keeps that policy in
the headless module layer instead of making Qt panels inspect KMAP payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_module_project import (
    AuthoredModuleProject,
    compile_authored_room_spec,
    normalise_resref,
)
from .authored_room_composition import AuthoredRoomComposition, PlacedRoomPrimitive
from .authored_room_floorplan import FloorPlanRoomPrimitive
from .authored_room_geometry import RectangularRoomPrimitive
from .authored_terrain_builder import TerrainHeightfieldPrimitive


@dataclass(frozen=True)
class MapStudioExportObjectBoundary:
    """One modder-facing object/room boundary produced by Map Studio export."""

    object_id: str
    label: str
    source_room_resref: str
    object_kind: str
    export_resref: str
    resources: tuple[tuple[str, str], ...]
    primitive_type: str
    primitive_count: int = 0
    member_primitive_names: tuple[str, ...] = ()
    helper_mesh_count: int = 0
    render_mesh_count: int = 0
    walkmesh_face_count: int = 0
    walkable_face_count: int = 0
    material_textures: tuple[str, ...] = ()
    normal_policy_status: str = "default_exporter_normals"
    normal_policy_summary: str = "Default exporter normals; no authored soften/harden edge policy."
    edge_normal_policy_targets: tuple[dict[str, Any], ...] = ()
    bounds_coordinate_space: str = ""
    bounds_min: tuple[float, float, float] | None = None
    bounds_max: tuple[float, float, float] | None = None
    center: tuple[float, float, float] | None = None
    dimensions: tuple[float, float, float] | None = None
    uv_handoff_recommended: bool = False
    dcc_handoff_status: str = "keep_in_map_studio"
    dcc_handoff_reason: str = ""
    resource_boundary_policy: str = "one_room_mdl_mdx_wok"
    owns_walkmesh: bool = False
    source_operation: str = ""
    source_room_resrefs: tuple[str, ...] = ()
    status: str = "export_candidate"
    notes: tuple[str, ...] = ()
    blocking_messages: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        """Return a stable JSON/KMAP-friendly dictionary for readiness panels."""

        return {
            "object_id": self.object_id,
            "label": self.label,
            "source_room_resref": self.source_room_resref,
            "object_kind": self.object_kind,
            "export_resref": self.export_resref,
            "resources": [[resref, restype] for resref, restype in self.resources],
            "primitive_type": self.primitive_type,
            "primitive_count": self.primitive_count,
            "member_primitive_names": list(self.member_primitive_names),
            "helper_mesh_count": self.helper_mesh_count,
            "render_mesh_count": self.render_mesh_count,
            "walkmesh_face_count": self.walkmesh_face_count,
            "walkable_face_count": self.walkable_face_count,
            "material_textures": list(self.material_textures),
            "normal_policy_status": self.normal_policy_status,
            "normal_policy_summary": self.normal_policy_summary,
            "edge_normal_policy_targets": [dict(row) for row in self.edge_normal_policy_targets],
            "bounds_coordinate_space": self.bounds_coordinate_space,
            "bounds_min": list(self.bounds_min) if self.bounds_min is not None else [],
            "bounds_max": list(self.bounds_max) if self.bounds_max is not None else [],
            "center": list(self.center) if self.center is not None else [],
            "dimensions": list(self.dimensions) if self.dimensions is not None else [],
            "uv_handoff_recommended": self.uv_handoff_recommended,
            "dcc_handoff_status": self.dcc_handoff_status,
            "dcc_handoff_reason": self.dcc_handoff_reason,
            "resource_boundary_policy": self.resource_boundary_policy,
            "owns_walkmesh": self.owns_walkmesh,
            "source_operation": self.source_operation,
            "source_room_resrefs": list(self.source_room_resrefs),
            "status": self.status,
            "notes": list(self.notes),
            "blocking_messages": list(self.blocking_messages),
        }


def _primitive_texture(value: Any) -> str:
    material = getattr(value, "material", None)
    return str(getattr(material, "texture", "") or "").strip()


def _base_primitive(value: Any) -> Any:
    return value.primitive if isinstance(value, PlacedRoomPrimitive) else value


def _placed_primitive_name(value: Any) -> str:
    return str(getattr(value, "name", "") or "").strip()


def _composition_textures(composition: AuthoredRoomComposition) -> tuple[str, ...]:
    textures: list[str] = []
    floor_texture = _primitive_texture(composition.floor)
    if floor_texture:
        textures.append(floor_texture)
    for primitive in tuple(composition.primitives or ()):
        texture = _primitive_texture(_base_primitive(primitive))
        if texture:
            textures.append(texture)
    return tuple(dict.fromkeys(textures))


def _normal_policy_entry(target: str, source: dict[str, Any]) -> dict[str, Any] | None:
    policy = str(source.get("edge_normal_policy") or "").strip().lower()
    if not policy:
        return None
    edges = source.get("edge_normal_policy_edges")
    if isinstance(edges, (list, tuple)):
        edge_values = [int(edge) for edge in edges]
    else:
        edge_values = []
    return {
        "target": str(target or "room"),
        "policy": policy,
        "operation": str(source.get("edge_normal_policy_operation") or ""),
        "scope": str(source.get("edge_normal_policy_scope") or "all_edges"),
        "edge_count": int(source.get("edge_normal_policy_edge_count") or 0),
        "coordinate_space": str(source.get("edge_normal_policy_coordinate_space") or ""),
        "edges": edge_values,
    }


def _normal_policy_targets(primitive: Any, metadata: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    targets: list[dict[str, Any]] = []
    primitive_metadata = dict(getattr(primitive, "metadata", {}) or {})
    by_target = primitive_metadata.get("edge_normal_policy_by_target")
    has_targeted_policy = isinstance(by_target, dict) and bool(by_target)
    if not has_targeted_policy:
        room_entry = _normal_policy_entry("room", primitive_metadata) or _normal_policy_entry("room", metadata)
        if room_entry is not None:
            targets.append(room_entry)
    if isinstance(by_target, dict):
        for target_name in sorted(str(name or "").strip() for name in by_target if str(name or "").strip()):
            target_entry = by_target.get(target_name)
            if isinstance(target_entry, dict):
                entry = _normal_policy_entry(target_name, dict(target_entry))
                if entry is not None:
                    targets.append(entry)
    return tuple(targets)


def _normal_policy_targets_for_members(
    composition: AuthoredRoomComposition,
    member_names: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    if not member_names:
        return ()
    wanted = set(member_names)
    return tuple(row for row in _normal_policy_targets(composition, {}) if str(row.get("target") or "") in wanted)


def _normal_policy_status(targets: tuple[dict[str, Any], ...]) -> str:
    return "authored_visual_normal_policy" if targets else "default_exporter_normals"


def _normal_policy_summary(targets: tuple[dict[str, Any], ...]) -> str:
    if not targets:
        return "Default exporter normals; no authored soften/harden edge policy."
    parts = []
    for row in targets[:4]:
        policy = str(row.get("policy") or "authored")
        target = str(row.get("target") or "room")
        scope = str(row.get("scope") or "all_edges")
        edge_count = int(row.get("edge_count") or 0)
        selected_edges = tuple(row.get("edges") or ())
        selected_count = len(selected_edges) if selected_edges else edge_count
        if scope == "selected_edges" and edge_count:
            parts.append(f"{policy} {selected_count} {target} edge(s)")
        else:
            parts.append(f"{policy} {target} {scope}")
    suffix = "" if len(targets) <= 4 else f"; +{len(targets) - 4} more"
    return "Authored visual-normal policy: " + "; ".join(parts) + suffix + ". WOK traversal remains validated separately."


def _composition_primitives_by_name(composition: AuthoredRoomComposition) -> dict[str, PlacedRoomPrimitive]:
    return {
        name: primitive
        for primitive in tuple(composition.primitives or ())
        if isinstance(primitive, PlacedRoomPrimitive) and (name := _placed_primitive_name(primitive))
    }


def _group_member_names(group: dict[str, Any]) -> tuple[str, ...]:
    values = group.get("primitive_names")
    if isinstance(values, (str, bytes)):
        text = values.decode("utf-8", errors="ignore") if isinstance(values, bytes) else values
        return tuple(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))
    if isinstance(values, (list, tuple)):
        return tuple(dict.fromkeys(str(value or "").strip() for value in values if str(value or "").strip()))
    return ()


def _vec3_from_group(group: dict[str, Any], key: str) -> tuple[float, float, float] | None:
    values = group.get(key)
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return None
    try:
        return (float(values[0]), float(values[1]), float(values[2]))
    except (TypeError, ValueError):
        return None


def _mesh_vertices(mesh: Any) -> tuple[tuple[float, float, float], ...]:
    vertices: list[tuple[float, float, float]] = []
    for vertex in tuple(getattr(mesh, "vertices", ()) or ()):
        if not isinstance(vertex, (list, tuple)) or len(vertex) < 3:
            continue
        try:
            vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
        except (TypeError, ValueError):
            continue
    return tuple(vertices)


def _bounds_from_vertices(
    vertices: tuple[tuple[float, float, float], ...],
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None:
    if not vertices:
        return None
    xs = tuple(vertex[0] for vertex in vertices)
    ys = tuple(vertex[1] for vertex in vertices)
    zs = tuple(vertex[2] for vertex in vertices)
    bounds_min = (min(xs), min(ys), min(zs))
    bounds_max = (max(xs), max(ys), max(zs))
    center = tuple((bounds_min[index] + bounds_max[index]) * 0.5 for index in range(3))  # type: ignore[return-value]
    dimensions = tuple(max(0.0, bounds_max[index] - bounds_min[index]) for index in range(3))  # type: ignore[return-value]
    return bounds_min, bounds_max, center, dimensions


def _object_kind(primitive: Any, metadata: dict[str, Any]) -> str:
    if isinstance(primitive, AuthoredRoomComposition):
        if metadata.get("separated_from_room"):
            return "separated_primitive_object"
        return "composition_room"
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        return "terrain_room"
    if isinstance(primitive, FloorPlanRoomPrimitive):
        return "floor_plan_room"
    if isinstance(primitive, RectangularRoomPrimitive):
        return "rectangular_room"
    return type(primitive).__name__.removesuffix("Primitive").lower() or "room"


def _primitive_count(primitive: Any) -> int:
    if isinstance(primitive, AuthoredRoomComposition):
        return len(tuple(primitive.primitives or ())) + 1
    if isinstance(primitive, TerrainHeightfieldPrimitive):
        rows = len(tuple(primitive.heights or ()))
        cols = len(tuple(primitive.heights[0] or ())) if rows else 0
        return rows * cols
    return 1


def _object_notes(*, primitive: Any, metadata: dict[str, Any], resref: str) -> tuple[str, ...]:
    notes = [f"Exports as {resref}.mdl, {resref}.mdx, and {resref}.wok."]
    if isinstance(primitive, AuthoredRoomComposition):
        if metadata.get("separated_from_room"):
            notes.append(
                f"Separated from {normalise_resref(metadata.get('separated_from_room'))}; "
                "safe for independent DCC UV/texturing handoff."
            )
        else:
            notes.append("Composition room keeps authored primitives as one export boundary.")
    elif isinstance(primitive, TerrainHeightfieldPrimitive):
        notes.append("Terrain boundary should keep sculpt changes and WOK validation together.")
    elif isinstance(primitive, FloorPlanRoomPrimitive):
        notes.append("Floor-plan boundary is suitable for external UV cleanup after geometry stabilizes.")
    return tuple(notes)


def _source_operation(*, primitive: Any, metadata: dict[str, Any]) -> str:
    """Return the operation that produced the current export boundary."""

    for source in (metadata, getattr(primitive, "metadata", {}) or {}):
        operation = str(dict(source).get("last_operation") or dict(source).get("operation") or "").strip()
        if operation:
            return operation
    return "authored_room"


def _source_room_resrefs(metadata: dict[str, Any], resref: str) -> tuple[str, ...]:
    """Return source room lineage for merge/separate handoff reporting."""

    merged = metadata.get("merged_room_resrefs")
    if isinstance(merged, (list, tuple)):
        values = tuple(normalise_resref(item) for item in merged if normalise_resref(item))
        if values:
            return values
    separated_from = normalise_resref(metadata.get("separated_from_room"))
    if separated_from:
        return (separated_from,)
    return (normalise_resref(resref),) if normalise_resref(resref) else ()


def _dcc_handoff_state(
    *,
    uv_handoff_recommended: bool,
    walkmesh_face_count: int,
    blocking: tuple[str, ...],
    kind: str,
) -> tuple[str, str]:
    """Classify whether this boundary is ready for outside UV/texturing work."""

    if blocking:
        return "blocked", "Fix export-object blockers before leaving GhostRigger."
    if not uv_handoff_recommended:
        return "keep_in_map_studio", "Keep this terrain or gameplay-derived object editable in Map Studio until geometry stabilizes."
    if walkmesh_face_count <= 0:
        return "needs_wok", "Generate or validate WOK faces before treating this as a KOTOR room handoff."
    if kind == "separated_primitive_object":
        return "ready_for_external_uv", "Separated object can be UV/textured externally, then returned as its own room MDL/MDX/WOK boundary."
    return "ready_for_external_uv", "Room boundary can be UV/textured externally while preserving its MDL/MDX/WOK resref triplet."


def _composition_group_boundaries(
    *,
    composition: AuthoredRoomComposition,
    resref: str,
) -> tuple[MapStudioExportObjectBoundary, ...]:
    """Return export/readiness projections for authored combined primitive groups."""

    groups = tuple(dict(item) for item in tuple(dict(composition.metadata).get("combined_primitive_groups") or ()))
    if not groups:
        return ()
    primitives_by_name = _composition_primitives_by_name(composition)
    boundaries: list[MapStudioExportObjectBoundary] = []
    for group_index, group in enumerate(groups, start=1):
        raw_name = str(group.get("name") or f"combined_primitive_group_{group_index:02d}").strip()
        group_name = raw_name or f"combined_primitive_group_{group_index:02d}"
        member_names = _group_member_names(group)
        missing = tuple(name for name in member_names if name not in primitives_by_name)
        member_primitives = tuple(primitives_by_name[name] for name in member_names if name in primitives_by_name)
        textures = tuple(
            dict.fromkeys(
                texture
                for primitive in member_primitives
                if (texture := _primitive_texture(_base_primitive(primitive)))
            )
        )
        blocking = tuple(
            f"Combined primitive group '{group_name}' references missing primitive '{name}'."
            for name in missing
        )
        face_count = int(group.get("face_count") or 0)
        vertex_count = int(group.get("vertex_count") or 0)
        dimensions = _vec3_from_group(group, "dimensions")
        normal_targets = _normal_policy_targets_for_members(composition, member_names)
        dcc_status = "blocked" if blocking else "ready_for_external_uv"
        dcc_reason = (
            "Fix missing grouped primitives before using this object group for UV/texturing handoff."
            if blocking
            else (
                "Combined primitive group can be UV/textured as a modder-facing object, "
                "but it still exports through the parent room until a future bake/separate step."
            )
        )
        notes = (
            f"Primitive group is authored inside {resref}.mdl/{resref}.mdx/{resref}.wok.",
            "Topology is preserved as individual primitives; arbitrary baked mesh combine is planned.",
            f"Group source mesh estimate: {vertex_count} vertices, {face_count} faces.",
            (
                f"Group KMAP-world dimensions: {dimensions[0]:.3f} x {dimensions[1]:.3f} x {dimensions[2]:.3f}."
                if dimensions is not None
                else "Group KMAP-world dimensions are not recorded yet; recombine the group to refresh bounds."
            ),
        )
        boundaries.append(
            MapStudioExportObjectBoundary(
                object_id=f"primitive_group:{resref}:{group_name}",
                label=f"{group_name} (combined primitive group)",
                source_room_resref=resref,
                object_kind="combined_primitive_group",
                export_resref=resref,
                resources=((resref, "mdl"), (resref, "mdx"), (resref, "wok")),
                primitive_type="AuthoredCombinedPrimitiveGroup",
                primitive_count=len(member_names),
                member_primitive_names=member_names,
                helper_mesh_count=0,
                render_mesh_count=len(member_primitives),
                walkmesh_face_count=0,
                walkable_face_count=0,
                material_textures=textures,
                normal_policy_status=_normal_policy_status(normal_targets),
                normal_policy_summary=_normal_policy_summary(normal_targets),
                edge_normal_policy_targets=normal_targets,
                bounds_coordinate_space=str(group.get("bounds_coordinate_space") or ""),
                bounds_min=_vec3_from_group(group, "bounds_min"),
                bounds_max=_vec3_from_group(group, "bounds_max"),
                center=_vec3_from_group(group, "center"),
                dimensions=dimensions,
                uv_handoff_recommended=True,
                dcc_handoff_status=dcc_status,
                dcc_handoff_reason=dcc_reason,
                resource_boundary_policy="combined_group_within_parent_room",
                owns_walkmesh=False,
                source_operation="combine_primitives",
                source_room_resrefs=(resref,),
                status="blocked" if blocking else "export_candidate",
                notes=notes,
                blocking_messages=blocking,
            )
        )
    return tuple(boundaries)


def map_studio_export_object_boundaries(project: AuthoredModuleProject) -> tuple[MapStudioExportObjectBoundary, ...]:
    """Return modder-facing export object boundaries for an authored module."""

    boundaries: list[MapStudioExportObjectBoundary] = []
    for room in tuple(project.rooms or ()):
        resref = normalise_resref(room.room_resref)
        metadata = dict(room.metadata or {})
        primitive = room.primitive
        primitive_type = type(primitive).__name__
        blocking: list[str] = []
        helper_mesh_count = 0
        render_mesh_count = 0
        walkmesh_face_count = 0
        walkable_face_count = 0
        material_textures: tuple[str, ...] = ()
        normal_targets: tuple[dict[str, Any], ...] = ()
        bounds_min: tuple[float, float, float] | None = None
        bounds_max: tuple[float, float, float] | None = None
        center: tuple[float, float, float] | None = None
        dimensions: tuple[float, float, float] | None = None
        try:
            geometry = compile_authored_room_spec(room)
            helpers = tuple(getattr(geometry, "helper_meshes", ()) or ())
            helper_mesh_count = len(helpers)
            render_mesh_count = 1 + helper_mesh_count
            render_vertices = _mesh_vertices(getattr(geometry, "room_mesh", None))
            for helper in helpers:
                render_vertices += _mesh_vertices(helper)
            bounds = _bounds_from_vertices(render_vertices)
            if bounds is not None:
                bounds_min, bounds_max, center, dimensions = bounds
            faces = tuple(getattr(getattr(geometry, "wok", None), "faces", ()) or ())
            walkmesh_face_count = len(faces)
            walkable_face_count = int(getattr(geometry.wok, "walkable_face_count", lambda: 0)())
            room_texture = str(getattr(geometry.room_mesh, "texture", "") or "").strip()
            if room_texture:
                material_textures = (room_texture,)
        except Exception as exc:
            blocking.append(f"Export object {resref or '(unnamed)'} could not compile: {exc}")
        if isinstance(primitive, AuthoredRoomComposition):
            material_textures = _composition_textures(primitive) or material_textures
        normal_targets = _normal_policy_targets(primitive, metadata)
        kind = _object_kind(primitive, metadata)
        uv_handoff = kind in {"composition_room", "separated_primitive_object", "floor_plan_room", "rectangular_room"}
        owns_walkmesh = walkmesh_face_count > 0
        source_operation = _source_operation(primitive=primitive, metadata=metadata)
        source_room_resrefs = _source_room_resrefs(metadata, resref)
        dcc_status, dcc_reason = _dcc_handoff_state(
            uv_handoff_recommended=uv_handoff,
            walkmesh_face_count=walkmesh_face_count,
            blocking=tuple(blocking),
            kind=kind,
        )
        boundaries.append(
            MapStudioExportObjectBoundary(
                object_id=f"room:{resref}",
                label=f"{resref} ({kind.replace('_', ' ')})",
                source_room_resref=resref,
                object_kind=kind,
                export_resref=resref,
                resources=((resref, "mdl"), (resref, "mdx"), (resref, "wok")),
                primitive_type=primitive_type,
                primitive_count=_primitive_count(primitive),
                helper_mesh_count=helper_mesh_count,
                render_mesh_count=render_mesh_count,
                walkmesh_face_count=walkmesh_face_count,
                walkable_face_count=walkable_face_count,
                material_textures=material_textures,
                normal_policy_status=_normal_policy_status(normal_targets),
                normal_policy_summary=_normal_policy_summary(normal_targets),
                edge_normal_policy_targets=normal_targets,
                bounds_coordinate_space="kmap_world" if bounds_min is not None else "",
                bounds_min=bounds_min,
                bounds_max=bounds_max,
                center=center,
                dimensions=dimensions,
                uv_handoff_recommended=uv_handoff,
                dcc_handoff_status=dcc_status,
                dcc_handoff_reason=dcc_reason,
                resource_boundary_policy="one_room_mdl_mdx_wok",
                owns_walkmesh=owns_walkmesh,
                source_operation=source_operation,
                source_room_resrefs=source_room_resrefs,
                status="blocked" if blocking else "export_candidate",
                notes=_object_notes(primitive=primitive, metadata=metadata, resref=resref),
                blocking_messages=tuple(blocking),
            )
        )
        if isinstance(primitive, AuthoredRoomComposition):
            boundaries.extend(_composition_group_boundaries(composition=primitive, resref=resref))
    return tuple(boundaries)


__all__ = [
    "MapStudioExportObjectBoundary",
    "map_studio_export_object_boundaries",
]
