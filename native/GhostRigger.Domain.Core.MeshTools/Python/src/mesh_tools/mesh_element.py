"""Connected element helpers."""

from __future__ import annotations

from .mesh_topology import MeshTopology


def select_element_for_face(topology: MeshTopology, face_index: int) -> int | None:
    for idx, faces in enumerate(topology.connected_elements):
        if int(face_index) in faces:
            return idx
    return None
