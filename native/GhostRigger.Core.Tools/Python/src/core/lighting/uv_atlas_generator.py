"""xatlas-backed lightmap UV generation.

xatlas is used because lightmaps need non-overlapping UV islands inside the
0..1 square. Diffuse/material UVs can legally tile or stack faces, but a
lightmap texel can only represent one surface point without lighting leaks.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import math
import re

import numpy as np

from .lightmap_uv_validator import face_uv_attr_for_channel, uv_attr_for_channel

try:  # pragma: no cover - depends on optional native wheel availability.
    import xatlas
except Exception:  # pragma: no cover
    xatlas = None


@dataclass
class UVAtlasResult:
    success: bool
    channel_index: int
    display_name: str
    uv_count: int = 0
    face_count: int = 0
    # xatlas emits one entry per atlas vertex.  Each value is the source mesh
    # vertex that must be duplicated when the atlas introduces a seam.
    vertex_mapping: list[int] = field(default_factory=list)
    atlas_faces: list[tuple[int, int, int]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class UVVertexStreamRemapResult:
    """Outcome of explicitly baking corner UV seams into the vertex stream."""

    success: bool
    changed: bool
    channel_index: int
    display_name: str
    source_vertex_count: int = 0
    vertex_count: int = 0
    face_count: int = 0
    duplicated_vertex_count: int = 0
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class UVAtlasGenerator:
    def generate_lightmap_uvs(
        self,
        mesh: object,
        *,
        target_channel: int = 1,
        resolution: int = 1024,
        padding_pixels: int = 8,
        replace_existing: bool = False,
    ) -> UVAtlasResult:
        channel = int(target_channel)
        uv_attr = uv_attr_for_channel(channel)
        face_attr = face_uv_attr_for_channel(channel)
        if getattr(mesh, uv_attr, None) and not replace_existing:
            return UVAtlasResult(
                False,
                channel,
                self.display_name(channel),
                errors=[f"{self.display_name(channel)} already exists. Choose replace or create another channel."],
            )

        vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float32)
        faces = np.asarray(getattr(mesh, "faces", []) or [], dtype=np.uint32)
        if vertices.size == 0 or faces.size == 0:
            return UVAtlasResult(False, channel, self.display_name(channel), errors=["Mesh has no vertices or triangles."])

        source = "xatlas"
        try:
            uvs, uv_faces, vertex_mapping, messages = self._generate_with_xatlas(
                vertices[:, :3], faces, resolution, padding_pixels
            )
        except Exception as exc:
            source = "fallback"
            uvs, uv_faces, vertex_mapping, messages = self._generate_fallback(faces)
            messages.append(f"xatlas generation failed; used simple fallback atlas: {exc}")

        mapping = [int(index) for index in np.asarray(vertex_mapping).reshape((-1,))]
        stored_faces = [tuple(int(i) for i in tri[:3]) for tri in uv_faces]
        if len(mapping) != len(uvs):
            return UVAtlasResult(
                False,
                channel,
                self.display_name(channel),
                errors=["Atlas vertex mapping does not match the generated UV vertex count."],
            )
        if len(stored_faces) != len(faces):
            return UVAtlasResult(
                False,
                channel,
                self.display_name(channel),
                errors=["Atlas face count does not match the source mesh face count."],
            )
        if any(index < 0 or index >= len(vertices) for index in mapping):
            return UVAtlasResult(
                False,
                channel,
                self.display_name(channel),
                errors=["Atlas vertex mapping contains an out-of-range source vertex."],
            )
        if any(index < 0 or index >= len(uvs) for tri in stored_faces for index in tri):
            return UVAtlasResult(
                False,
                channel,
                self.display_name(channel),
                errors=["Atlas faces contain an out-of-range generated UV vertex."],
            )

        try:
            setattr(mesh, uv_attr, [(float(u), float(v)) for u, v in uvs])
            setattr(mesh, face_attr, stored_faces)
            setattr(mesh, "_gr_generated_lightmap_uv_channel", channel)
            setattr(mesh, "_gr_generated_lightmap_uv_source", source)
            setattr(mesh, "_gr_generated_lightmap_vertex_mapping", mapping)
            setattr(mesh, "_gr_generated_lightmap_faces", stored_faces)
            setattr(mesh, "_gr_generated_lightmap_source_vertex_count", len(vertices))
        except Exception as exc:
            return UVAtlasResult(False, channel, self.display_name(channel), errors=[f"Could not store generated UVs: {exc}"])

        messages.append(
            "Atlas seams are stored non-destructively; explicitly remap the vertex stream before exporting this UV channel."
        )
        return UVAtlasResult(
            True,
            channel,
            self.display_name(channel),
            uv_count=len(uvs),
            face_count=len(uv_faces),
            vertex_mapping=mapping,
            atlas_faces=stored_faces,
            messages=messages,
        )

    def remap_vertex_stream_for_lightmap(
        self,
        mesh: object,
        *,
        target_channel: int = 1,
    ) -> UVVertexStreamRemapResult:
        """Opt in to a single-index mesh suitable for KOTOR MDL/MDX export.

        Atlas generation deliberately keeps the source topology untouched and
        stores separate corner indices.  This operation is the destructive
        boundary: it duplicates vertices at every UV seam, remaps every known
        per-vertex stream, and clears the now-redundant per-face UV indices.
        Validation completes before any mesh attribute is changed.
        """

        channel = int(target_channel)
        display_name = self.display_name(channel)
        vertices = list(getattr(mesh, "vertices", []) or [])
        raw_faces = list(getattr(mesh, "faces", []) or [])
        result = UVVertexStreamRemapResult(
            success=False,
            changed=False,
            channel_index=channel,
            display_name=display_name,
            source_vertex_count=len(vertices),
            vertex_count=len(vertices),
            face_count=len(raw_faces),
        )
        if not vertices or not raw_faces:
            result.errors.append("Mesh has no vertices or triangles.")
            return result
        try:
            if any(len(face) != 3 for face in raw_faces):
                raise ValueError
            faces = [tuple(int(index) for index in face) for face in raw_faces]
        except (TypeError, ValueError):
            result.errors.append("Only triangle meshes can be remapped for lightmap export.")
            return result
        if any(index < 0 or index >= len(vertices) for face in faces for index in face):
            result.errors.append("Mesh faces contain an out-of-range source vertex.")
            return result

        uv_channels = self._existing_uv_channels(mesh)
        if channel not in uv_channels:
            result.errors.append(f"Mesh has no {display_name} coordinates to remap.")
            return result
        uv_values = {
            uv_channel: list(getattr(mesh, uv_attr_for_channel(uv_channel), []) or [])
            for uv_channel in uv_channels
        }
        try:
            face_uv_values = {
                uv_channel: [
                    tuple(int(index) for index in tri)
                    for tri in (getattr(mesh, face_uv_attr_for_channel(uv_channel), []) or [])
                ]
                for uv_channel in uv_channels
            }
            if any(len(tri) != 3 for channel_faces in face_uv_values.values() for tri in channel_faces):
                raise ValueError
        except (TypeError, ValueError):
            result.errors.append("A UV face-index stream contains a non-triangle record.")
            return result

        generated_channel = getattr(mesh, "_gr_generated_lightmap_uv_channel", None)
        generated_mapping = list(getattr(mesh, "_gr_generated_lightmap_vertex_mapping", []) or [])
        try:
            generated_faces = [
                tuple(int(index) for index in tri)
                for tri in (getattr(mesh, "_gr_generated_lightmap_faces", []) or [])
            ]
            if any(len(tri) != 3 for tri in generated_faces):
                raise ValueError
        except (TypeError, ValueError):
            result.errors.append("Stored atlas faces contain a non-triangle record.")
            return result
        generated_source_count = getattr(mesh, "_gr_generated_lightmap_source_vertex_count", None)
        use_generated_mapping = bool(generated_mapping and generated_faces and generated_channel == channel)

        target_face_uvs = face_uv_values[channel]
        if use_generated_mapping:
            if generated_source_count is not None and int(generated_source_count) != len(vertices):
                result.errors.append("The mesh vertex count changed after atlas generation; regenerate lightmap UVs.")
                return result
            if len(generated_mapping) != len(uv_values[channel]):
                result.errors.append("Stored atlas mapping does not match the generated UV vertex count.")
                return result
            if len(generated_faces) != len(faces):
                result.errors.append("Stored atlas faces do not match the mesh face count.")
                return result
            target_face_uvs = generated_faces

        if not target_face_uvs:
            if len(uv_values[channel]) == len(vertices):
                result.success = True
                result.messages.append(f"{display_name} already has one coordinate per mesh vertex; no remap was needed.")
                return result
            result.errors.append(
                f"{display_name} is not per-vertex and has no complete face-corner index stream."
            )
            return result
        if len(target_face_uvs) != len(faces):
            result.errors.append(f"{display_name} face indices do not match the mesh face count.")
            return result

        per_vertex_streams: dict[str, list] = {}
        for attr in ("normals", "tangents", "skin_data"):
            values = list(getattr(mesh, attr, []) or [])
            if values and len(values) != len(vertices):
                result.errors.append(
                    f"Cannot safely remap {attr}: expected {len(vertices)} entries, found {len(values)}."
                )
                return result
            per_vertex_streams[attr] = values
        face_mats = list(getattr(mesh, "face_mats", []) or [])
        if face_mats and len(face_mats) != len(faces):
            result.errors.append(
                f"Cannot safely preserve face materials: expected {len(faces)} entries, found {len(face_mats)}."
            )
            return result

        # Resolve every face corner before mutation.  UV seams from any channel
        # participate in the key so diffuse/detail UVs are not accidentally
        # welded while making UV2 exportable.
        corner_records: list[list[tuple[int, dict[int, int]]]] = []
        for face_index, face in enumerate(faces):
            corner_face: list[tuple[int, dict[int, int]]] = []
            for corner_index, geometric_source in enumerate(face):
                if use_generated_mapping:
                    atlas_vertex = int(target_face_uvs[face_index][corner_index])
                    if atlas_vertex < 0 or atlas_vertex >= len(generated_mapping):
                        result.errors.append("Stored atlas faces contain an out-of-range atlas vertex.")
                        return result
                    source_vertex = int(generated_mapping[atlas_vertex])
                    if source_vertex != geometric_source:
                        result.errors.append(
                            "Stored atlas mapping no longer matches the mesh face topology; regenerate lightmap UVs."
                        )
                        return result
                else:
                    source_vertex = geometric_source

                uv_indices: dict[int, int] = {}
                for uv_channel in uv_channels:
                    channel_faces = target_face_uvs if uv_channel == channel else face_uv_values[uv_channel]
                    if channel_faces:
                        if len(channel_faces) != len(faces):
                            result.errors.append(
                                f"{self.display_name(uv_channel)} face indices do not match the mesh face count."
                            )
                            return result
                        uv_index = int(channel_faces[face_index][corner_index])
                    elif len(uv_values[uv_channel]) == len(vertices):
                        uv_index = source_vertex
                    else:
                        result.errors.append(
                            f"Cannot safely preserve {self.display_name(uv_channel)}: it is neither per-vertex nor face-indexed."
                        )
                        return result
                    if uv_index < 0 or uv_index >= len(uv_values[uv_channel]):
                        result.errors.append(f"{self.display_name(uv_channel)} contains an out-of-range UV index.")
                        return result
                    uv_indices[uv_channel] = uv_index
                corner_face.append((source_vertex, uv_indices))
            corner_records.append(corner_face)

        new_vertices: list = []
        new_streams: dict[str, list] = {attr: [] for attr, values in per_vertex_streams.items() if values}
        new_uvs: dict[int, list] = {uv_channel: [] for uv_channel in uv_channels}
        new_faces: list[tuple[int, int, int]] = []
        new_to_source: list[int] = []
        vertex_keys: dict[tuple, int] = {}
        for corner_face in corner_records:
            remapped_face: list[int] = []
            for source_vertex, uv_indices in corner_face:
                key = (source_vertex, tuple((uv_channel, uv_indices[uv_channel]) for uv_channel in uv_channels))
                remapped_index = vertex_keys.get(key)
                if remapped_index is None:
                    remapped_index = len(new_vertices)
                    vertex_keys[key] = remapped_index
                    new_vertices.append(copy.deepcopy(vertices[source_vertex]))
                    new_to_source.append(source_vertex)
                    for attr, values in per_vertex_streams.items():
                        if values:
                            new_streams[attr].append(copy.deepcopy(values[source_vertex]))
                    for uv_channel in uv_channels:
                        new_uvs[uv_channel].append(copy.deepcopy(uv_values[uv_channel][uv_indices[uv_channel]]))
                remapped_face.append(remapped_index)
            new_faces.append(tuple(remapped_face))

        # Commit only after every stream and corner has validated successfully.
        setattr(mesh, "vertices", new_vertices)
        setattr(mesh, "faces", new_faces)
        for attr, values in per_vertex_streams.items():
            setattr(mesh, attr, new_streams.get(attr, []) if values else [])
        for uv_channel in uv_channels:
            setattr(mesh, uv_attr_for_channel(uv_channel), new_uvs[uv_channel])
            setattr(mesh, face_uv_attr_for_channel(uv_channel), [])
        if hasattr(mesh, "face_mats"):
            setattr(mesh, "face_mats", copy.deepcopy(face_mats))
        setattr(mesh, "_gr_lightmap_vertex_source_mapping", new_to_source)
        setattr(mesh, "_gr_lightmap_vertex_stream_channel", channel)
        setattr(mesh, "_gr_generated_lightmap_vertex_mapping", [])
        setattr(mesh, "_gr_generated_lightmap_faces", [])
        setattr(mesh, "_gr_generated_lightmap_source_vertex_count", len(new_vertices))

        result.success = True
        result.changed = True
        result.vertex_count = len(new_vertices)
        result.duplicated_vertex_count = max(0, len(new_vertices) - len(vertices))
        result.messages.append(
            f"Remapped {display_name} into a single-index vertex stream ({len(vertices)} -> {len(new_vertices)} vertices)."
        )
        return result

    def choose_free_channel(self, mesh: object, preferred: int = 1, max_channel: int = 6) -> int:
        if not getattr(mesh, uv_attr_for_channel(preferred), None):
            return preferred
        for channel in range(1, max_channel + 1):
            if not getattr(mesh, uv_attr_for_channel(channel), None):
                return channel
        return max_channel + 1

    def display_name(self, channel: int) -> str:
        return f"UV{int(channel) + 1}"

    def _existing_uv_channels(self, mesh: object) -> list[int]:
        channels: set[int] = set()
        for attr in vars(mesh):
            if attr == "uvs":
                channel = 0
            elif attr == "uvs_lm":
                channel = 1
            else:
                match = re.fullmatch(r"uvs_(\d+)", attr)
                if match is None:
                    continue
                channel = int(match.group(1))
            if getattr(mesh, attr, None):
                channels.add(channel)
        return sorted(channels)

    def _generate_with_xatlas(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        resolution: int,
        padding_pixels: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
        if xatlas is None:
            raise RuntimeError("xatlas is not installed")
        atlas = xatlas.Atlas()
        atlas.add_mesh(vertices, faces)
        try:
            chart_options = xatlas.ChartOptions()
            pack_options = xatlas.PackOptions()
            pack_options.resolution = int(resolution)
            pack_options.padding = int(padding_pixels)
            atlas.generate(chart_options=chart_options, pack_options=pack_options)
        except TypeError:
            atlas.generate()
        vmapping, indices, uvs = atlas.get_mesh(0)
        uv_faces = np.asarray(indices, dtype=np.uint32).reshape((-1, 3))
        out_uvs = np.asarray(uvs, dtype=np.float32)
        out_uvs[:, 0] = np.clip(out_uvs[:, 0], 0.0, 1.0)
        out_uvs[:, 1] = np.clip(out_uvs[:, 1], 0.0, 1.0)
        return (
            out_uvs,
            uv_faces,
            np.asarray(vmapping, dtype=np.uint32),
            ["Generated non-overlapping lightmap UVs with xatlas."],
        )

    def _generate_fallback(self, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
        face_count = int(len(faces))
        cols = max(1, math.ceil(math.sqrt(face_count)))
        cell = 1.0 / float(cols)
        margin = cell * 0.12
        uvs: list[tuple[float, float]] = []
        uv_faces: list[tuple[int, int, int]] = []
        for idx in range(face_count):
            col = idx % cols
            row = idx // cols
            u0 = col * cell + margin
            v0 = row * cell + margin
            u1 = (col + 1) * cell - margin
            v1 = (row + 1) * cell - margin
            base = len(uvs)
            uvs.extend([(u0, v0), (u1, v0), (u0, v1)])
            uv_faces.append((base, base + 1, base + 2))
        return (
            np.asarray(uvs, dtype=np.float32),
            np.asarray(uv_faces, dtype=np.uint32),
            np.asarray(faces, dtype=np.uint32).reshape((-1,)),
            ["Generated fallback non-overlapping UVs; install xatlas for production atlas quality."],
        )
