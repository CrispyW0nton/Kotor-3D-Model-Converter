"""Attach/combine selected mesh nodes into one editable mesh."""

from __future__ import annotations

import copy

from .mesh_edit_types import MeshOperationResult


def attach_selected_meshes(meshes: list[object]) -> tuple[MeshOperationResult, object | None]:
    clean = [mesh for mesh in meshes if _is_mesh(mesh)]
    if len(clean) < 2:
        return MeshOperationResult.fail("Attach / Combine requires two or more selected mesh objects."), None
    combined = copy.deepcopy(clean[0])
    combined.name = _combined_name(clean)
    combined.position = (0.0, 0.0, 0.0)
    combined.rotation = (0.0, 0.0, 0.0, 1.0)
    combined.parent = None
    combined.children = []
    combined.vertices = []
    combined.faces = []
    combined.normals = []
    combined.tangents = []
    combined.uvs = []
    combined.uvs_lm = []
    combined.uvs_2 = []
    combined.uvs_3 = []
    combined.face_mats = []
    combined.face_uvs = []
    combined.texture_names = []
    combined_slots: list[str] = []
    offset = 0
    original_names = []
    warnings = []
    for mesh in clean:
        original_names.append(str(getattr(mesh, "name", "mesh")))
        verts = _world_vertices(mesh)
        combined.vertices.extend(verts)
        for face in getattr(mesh, "faces", []) or []:
            combined.faces.append(tuple(int(v) + offset for v in face[:3]))
        _extend_vertex_channel(combined, mesh, "normals", len(verts), (0.0, 0.0, 1.0))
        _extend_vertex_channel(combined, mesh, "tangents", len(verts), (1.0, 0.0, 0.0))
        _extend_vertex_channel(combined, mesh, "uvs", len(verts), (0.0, 0.0))
        _extend_vertex_channel(combined, mesh, "uvs_lm", len(verts), (0.0, 0.0))
        _extend_vertex_channel(combined, mesh, "uvs_2", len(verts), (0.0, 0.0))
        _extend_vertex_channel(combined, mesh, "uvs_3", len(verts), (0.0, 0.0))
        mats = list(getattr(mesh, "face_mats", []) or [])
        slots = list(getattr(mesh, "texture_names", []) or [])
        if not slots:
            slots = [str(getattr(mesh, "texture", "") or "")]
        remapped_mats = []
        face_count = len(getattr(mesh, "faces", []) or [])
        for fi in range(face_count):
            source_mat = int(mats[fi]) if fi < len(mats) else 0
            source_name = slots[source_mat] if 0 <= source_mat < len(slots) else slots[0]
            if source_name not in combined_slots:
                combined_slots.append(source_name)
            remapped_mats.append(combined_slots.index(source_name))
        combined.face_mats.extend(remapped_mats)
        face_uvs = list(getattr(mesh, "face_uvs", []) or [])
        if face_uvs:
            combined.face_uvs.extend(tuple(int(v) + offset for v in uv_face[:3]) for uv_face in face_uvs)
        elif combined.face_uvs:
            combined.face_uvs.extend(tuple(int(v) + offset for v in face[:3]) for face in getattr(mesh, "faces", []) or [])
        if not _compatible_channels(clean[0], mesh):
            warnings.append(f"{getattr(mesh, 'name', 'mesh')} has a different attribute layout; missing channels were padded.")
        offset += len(verts)
    combined._gr_original_object_names = original_names
    combined.texture_names = combined_slots
    combined.tex_count = max(1, len(combined_slots))
    combined.texture = combined_slots[0] if combined_slots else str(getattr(combined, "texture", "") or "")
    combined._gr_attach_does_not_weld = True
    combined._gr_aurora_metadata_sources = [getattr(mesh, "__dict__", {}).copy() for mesh in clean]
    if hasattr(combined, "compute_bounds"):
        combined.compute_bounds()
    result = MeshOperationResult.ok(
        "Attached meshes. Overlapping vertices remain separate until Weld or Target Weld is used.",
        changed_mesh_ids=[str(getattr(combined, "name", id(combined)))],
        selection_changed=True,
        topology_changed=True,
        warnings=warnings,
    )
    return result, combined


def _is_mesh(mesh) -> bool:
    return bool(getattr(mesh, "vertices", None) and getattr(mesh, "faces", None))


def _world_vertices(mesh) -> list[tuple[float, float, float]]:
    verts = [tuple(map(float, v[:3])) for v in (getattr(mesh, "vertices", []) or [])]
    try:
        wp, _rot = mesh.world_transform()
    except Exception:
        wp = getattr(mesh, "position", (0.0, 0.0, 0.0))
    if int(getattr(mesh, "vertex_space", 0) or 0) == 1:
        return verts
    return [(v[0] + float(wp[0]), v[1] + float(wp[1]), v[2] + float(wp[2])) for v in verts]


def _extend_vertex_channel(combined, mesh, attr: str, count: int, default) -> None:
    values = list(getattr(mesh, attr, []) or [])
    if len(values) == count:
        getattr(combined, attr).extend(copy.deepcopy(values))
    else:
        getattr(combined, attr).extend([default] * count)


def _compatible_channels(reference, mesh) -> bool:
    for attr in ("uvs", "uvs_lm", "normals", "face_mats"):
        if bool(getattr(reference, attr, [])) != bool(getattr(mesh, attr, [])):
            return False
    return True


def _combined_name(meshes: list[object]) -> str:
    stem = str(getattr(meshes[0], "name", "mesh") or "mesh")
    return f"{stem}_combined"
