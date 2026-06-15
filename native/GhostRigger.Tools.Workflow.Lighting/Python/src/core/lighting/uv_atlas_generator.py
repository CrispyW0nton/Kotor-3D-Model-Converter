"""xatlas-backed lightmap UV generation.

xatlas is used because lightmaps need non-overlapping UV islands inside the
0..1 square. Diffuse/material UVs can legally tile or stack faces, but a
lightmap texel can only represent one surface point without lighting leaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

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

        try:
            uvs, uv_faces, messages = self._generate_with_xatlas(vertices[:, :3], faces, resolution, padding_pixels)
        except Exception as exc:
            uvs, uv_faces, messages = self._generate_fallback(faces)
            messages.append(f"xatlas generation failed; used simple fallback atlas: {exc}")

        try:
            setattr(mesh, uv_attr, [(float(u), float(v)) for u, v in uvs])
            setattr(mesh, face_attr, [tuple(int(i) for i in tri[:3]) for tri in uv_faces])
            setattr(mesh, "_gr_generated_lightmap_uv_channel", channel)
            setattr(mesh, "_gr_generated_lightmap_uv_source", "xatlas" if xatlas is not None else "fallback")
        except Exception as exc:
            return UVAtlasResult(False, channel, self.display_name(channel), errors=[f"Could not store generated UVs: {exc}"])

        return UVAtlasResult(
            True,
            channel,
            self.display_name(channel),
            uv_count=len(uvs),
            face_count=len(uv_faces),
            messages=messages,
        )

    def choose_free_channel(self, mesh: object, preferred: int = 1, max_channel: int = 6) -> int:
        if not getattr(mesh, uv_attr_for_channel(preferred), None):
            return preferred
        for channel in range(1, max_channel + 1):
            if not getattr(mesh, uv_attr_for_channel(channel), None):
                return channel
        return max_channel + 1

    def display_name(self, channel: int) -> str:
        return f"UV{int(channel) + 1}"

    def _generate_with_xatlas(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        resolution: int,
        padding_pixels: int,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
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
        _vmapping, indices, uvs = atlas.get_mesh(0)
        uv_faces = np.asarray(indices, dtype=np.uint32).reshape((-1, 3))
        out_uvs = np.asarray(uvs, dtype=np.float32)
        out_uvs[:, 0] = np.clip(out_uvs[:, 0], 0.0, 1.0)
        out_uvs[:, 1] = np.clip(out_uvs[:, 1], 0.0, 1.0)
        return out_uvs, uv_faces, ["Generated non-overlapping lightmap UVs with xatlas."]

    def _generate_fallback(self, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
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
            ["Generated fallback non-overlapping UVs; install xatlas for production atlas quality."],
        )
