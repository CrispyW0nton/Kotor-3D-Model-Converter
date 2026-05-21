"""Attribute preservation hooks for topology-changing mesh edits."""

from __future__ import annotations


VERTEX_ATTRIBUTE_NAMES = ("normals", "tangents", "uvs", "uvs_lm", "uvs_2", "uvs_3", "skin_data")
FACE_ATTRIBUTE_NAMES = ("face_mats", "face_uvs")


def remap_vertex_attributes(mesh, old_to_new: dict[int, int], new_count: int, *, target_values: dict[str, list] | None = None) -> list[str]:
    """Preserve per-vertex UV/material-adjacent data through index remaps.

    Aurora meshes often store UV/lightmap channels as vertex-aligned arrays,
    while ASCII imports may use ``face_uvs`` indirection. This helper remaps
    vertex-aligned channels and leaves face-indexed UVs to face preservation
    code, warning callers when a channel layout cannot be safely rewritten.
    """

    warnings: list[str] = []
    target_values = target_values or {}
    for attr in VERTEX_ATTRIBUTE_NAMES:
        if not hasattr(mesh, attr):
            continue
        values = list(getattr(mesh, attr) or [])
        if not values:
            continue
        if len(values) != len(old_to_new):
            warnings.append(f"{attr} layout is not vertex-aligned; preservation hook left it unchanged.")
            continue
        if attr in target_values:
            setattr(mesh, attr, target_values[attr])
            continue
        new_values = [None] * new_count
        for old_idx, new_idx in old_to_new.items():
            if 0 <= old_idx < len(values) and new_values[new_idx] is None:
                new_values[new_idx] = values[old_idx]
        fill = values[0] if values else None
        setattr(mesh, attr, [value if value is not None else fill for value in new_values])
    return warnings


def filter_face_attributes(mesh, kept_face_indices: list[int]) -> None:
    for attr in FACE_ATTRIBUTE_NAMES:
        if not hasattr(mesh, attr):
            continue
        values = list(getattr(mesh, attr) or [])
        if not values:
            continue
        setattr(mesh, attr, [values[i] for i in kept_face_indices if 0 <= i < len(values)])


def append_face_attributes(mesh, count: int, material_id: int = 0) -> None:
    if hasattr(mesh, "face_mats"):
        mesh.face_mats = list(getattr(mesh, "face_mats", []) or []) + [int(material_id)] * int(count)
