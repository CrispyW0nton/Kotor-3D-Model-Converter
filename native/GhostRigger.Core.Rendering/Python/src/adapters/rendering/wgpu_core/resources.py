from __future__ import annotations

import logging
import math
import time

from .shared import (
    WgpuMaterialResource,
    WgpuMeshResource,
    WgpuSkinResource,
    WgpuTextureResource,
    _rgba8,
)

log = logging.getLogger(__name__)


class WgpuResourceCache:
    """Renderer-owned WGPU resources keyed by GhostRigger object identity."""

    def __init__(self, renderer: "WgpuRenderer") -> None:
        self._renderer = renderer
        self.meshes: dict[int, WgpuMeshResource] = {}
        self.skins: dict[int, WgpuSkinResource] = {}
        self.textures: dict[str, WgpuTextureResource] = {}
        self.materials: dict[str, WgpuMaterialResource] = {}
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.uploaded_edge_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self.last_skinning_error = ""
        self.uploaded_bone_matrix_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.mesh_upload_count = 0
        self.texture_upload_count = 0
        self.buffer_upload_count = 0
        self.bind_group_creation_count = 0
        self.last_invalidation_reason = ""
        self._white_diffuse: WgpuTextureResource | None = None
        self._white_lightmap: WgpuTextureResource | None = None
        self._missing_checker: WgpuTextureResource | None = None

    def get_or_upload_mesh(self, mesh_data) -> WgpuMeshResource | None:
        mesh_id = int(mesh_data.mesh_id)
        cached = self.meshes.get(mesh_id)
        if cached is not None and cached.source_revision == mesh_data.source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        if not self._renderer._consume_upload_budget("mesh", mesh_id):
            return None
        return self.upload_mesh(mesh_id, mesh_data)

    def upload_mesh(self, mesh_id: int, mesh_data) -> WgpuMeshResource | None:
        import numpy as np
        import wgpu

        device = self._renderer.device
        if device is None:
            return None
        positions = np.asarray(mesh_data.positions, dtype=np.float32)
        if positions.ndim != 2 or positions.shape[1] != 3 or len(positions) == 0:
            return None
        normals = mesh_data.normals
        if normals is None:
            normals = np.zeros_like(positions, dtype=np.float32)
            normals[:, 2] = 1.0
        normals = np.asarray(normals, dtype=np.float32)
        if normals.shape != positions.shape:
            fixed = np.zeros_like(positions, dtype=np.float32)
            fixed[:, 2] = 1.0
            rows = min(len(fixed), len(normals))
            if rows:
                fixed[:rows, :] = normals[:rows, :3]
            normals = fixed
        uvs0 = self._coerce_uvs(getattr(mesh_data, "uvs0", None), len(positions))
        uvs1 = self._coerce_uvs(getattr(mesh_data, "uvs1", None), len(positions))
        bone_indices = self._coerce_bone_indices(getattr(mesh_data, "bone_indices", None), len(positions))
        bone_weights = self._coerce_bone_weights(getattr(mesh_data, "bone_weights", None), len(positions))
        packed_dtype = np.dtype(
            [
                ("position", "<f4", 3),
                ("normal", "<f4", 3),
                ("uv0", "<f4", 2),
                ("uv1", "<f4", 2),
                ("bone_indices", "<u4", 4),
                ("bone_weights", "<f4", 4),
            ]
        )
        packed = np.empty(len(positions), dtype=packed_dtype)
        packed["position"] = positions
        packed["normal"] = normals
        packed["uv0"] = uvs0
        packed["uv1"] = uvs1
        packed["bone_indices"] = bone_indices
        packed["bone_weights"] = bone_weights
        vertex_buffer = device.create_buffer_with_data(data=packed.tobytes(), usage=wgpu.BufferUsage.VERTEX)
        self.buffer_upload_count += 1
        index_buffer = None
        index_count = 0
        edge_index_buffer = None
        edge_index_count = 0
        sprite_wire_hull = self._uses_sprite_wire_hull(getattr(mesh_data, "material", None))
        if mesh_data.indices is not None and len(mesh_data.indices):
            indices = np.ascontiguousarray(mesh_data.indices, dtype=np.uint32)
            index_buffer = device.create_buffer_with_data(data=indices, usage=wgpu.BufferUsage.INDEX)
            self.buffer_upload_count += 1
            index_count = int(len(indices))
            edge_indices = self._build_edge_indices(indices, len(positions), positions=positions, geometric=sprite_wire_hull)
        else:
            edge_indices = self._build_edge_indices(None, len(positions), positions=positions, geometric=sprite_wire_hull)
        if edge_indices is not None and len(edge_indices):
            edge_index_buffer = device.create_buffer_with_data(data=edge_indices, usage=wgpu.BufferUsage.INDEX)
            self.buffer_upload_count += 1
            edge_index_count = int(len(edge_indices))
        mins = positions.min(axis=0)
        maxs = positions.max(axis=0)
        resource = WgpuMeshResource(
            vertex_buffer=vertex_buffer,
            index_buffer=index_buffer,
            edge_index_buffer=edge_index_buffer,
            vertex_count=int(len(positions)),
            index_count=index_count,
            edge_index_count=edge_index_count,
            vertex_stride=72,
            bounds=(tuple(float(v) for v in mins), tuple(float(v) for v in maxs)),
            source_revision=mesh_data.source_revision,
        )
        self.meshes[int(mesh_id)] = resource
        self.mesh_upload_count += 1
        self._recount()
        return resource

    def get_or_update_skin_palette(self, mesh_data, anim_pose, model, anim_base_pose=None) -> WgpuSkinResource | None:
        import wgpu

        is_bas_attachment = bool(getattr(getattr(mesh_data, "source", None), "_gr_bas_attachment_layer", False))
        if not bool(getattr(mesh_data, "is_skinned", False)) or (anim_pose is None and not is_bas_attachment):
            return None
        device = self._renderer.device
        layout = getattr(self._renderer, "skin_bind_group_layout", None)
        if device is None or layout is None:
            self.last_skinning_error = "WGPU skin bind group layout is not ready"
            return None
        try:
            from src.core.animation.gpu_skinning import MatrixPaletteUploader, MAX_BONES
            from src.core.rendering.mesh_render_data import (
                animation_pose_applies_to_node,
                animation_pose_for_node,
                bas_attachment_palette_model_for_node,
                runtime_source_model_for_node,
            )
            from src.core.rendering.skeleton_render_data import (
                bas_attachment_root_local_skin_palette,
                skin_palette_flat_bytes,
            )
        except Exception as exc:
            self.last_skinning_error = f"WGPU palette builder unavailable: {exc}"
            return None

        source_model = runtime_source_model_for_node(mesh_data.source) or model
        if bool(getattr(mesh_data.source, "_gr_bas_attachment_layer", False)):
            source_model = bas_attachment_palette_model_for_node(mesh_data.source) or source_model
        node_anim_pose = animation_pose_for_node(mesh_data.source, anim_pose) if anim_pose is not None else None
        node_anim_base_pose = animation_pose_for_node(mesh_data.source, anim_base_pose) if anim_base_pose is not None else None
        if anim_pose is not None and node_anim_pose is None:
            if not bool(getattr(mesh_data.source, "_gr_bas_attachment_layer", False)):
                return None
            anim_pose = None
        else:
            anim_pose = node_anim_pose
        if anim_pose is not None and not animation_pose_applies_to_node(mesh_data.source, anim_pose):
            if not bool(getattr(mesh_data.source, "_gr_bas_attachment_layer", False)):
                return None
            anim_pose = None

        mesh_id = int(mesh_data.mesh_id)
        source_revision = tuple(getattr(mesh_data, "source_revision", ()) or ())
        cached = self.skins.get(mesh_id)
        if cached is None or cached.source_revision != source_revision:
            self.cache_misses += 1
            max_bones = int(MAX_BONES)
            byte_size = max_bones * 16 * 4
            palette_buffer = device.create_buffer(
                label=f"WGPU skin palette {getattr(mesh_data.source, 'name', mesh_id)}",
                size=byte_size,
                usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST,
            )
            bind_group = device.create_bind_group(
                layout=layout,
                entries=[
                    {
                        "binding": 0,
                        "resource": {"buffer": palette_buffer, "offset": 0, "size": byte_size},
                    }
                ],
            )
            self.bind_group_creation_count += 1
            uploader = MatrixPaletteUploader(max_bones=max_bones)
            uploader.build_inverse_bind_pose(source_model)
            cached = WgpuSkinResource(
                palette_buffer=palette_buffer,
                bind_group=bind_group,
                uploader=uploader,
                source_revision=source_revision,
                pose_revision=-1,
                matrix_count=0,
                max_bones=max_bones,
                byte_size=byte_size,
            )
            self.skins[mesh_id] = cached

        pose_revision = self._pose_revision(anim_pose, mesh_data)
        if node_anim_base_pose is not None:
            pose_revision = (pose_revision, id(node_anim_base_pose))
        if cached.pose_revision != pose_revision:
            started = time.perf_counter()
            palette = cached.uploader.compute_skin_node_palette(
                mesh_data.source,
                anim_pose,
                anim_base_pose=node_anim_base_pose,
            )
            palette_arr = cached.uploader.as_numpy_array()
            palette_arr = bas_attachment_root_local_skin_palette(mesh_data.source, palette_arr, anim_pose)
            payload = skin_palette_flat_bytes(palette_arr, cached.max_bones) or cached.uploader.as_flat_bytes()
            if not payload:
                self.last_skinning_error = f"empty WGPU skin palette for {getattr(mesh_data.source, 'name', mesh_id)}"
                return None
            self._renderer.queue.write_buffer(cached.palette_buffer, 0, payload[: cached.byte_size])
            self.buffer_upload_count += 1
            cached.pose_revision = pose_revision
            cached.matrix_count = min(len(palette), cached.max_bones)
            self.uploaded_bone_matrix_count = max(self.uploaded_bone_matrix_count, int(cached.matrix_count))
            profiler = getattr(self._renderer, "profiler", None)
            if profiler is not None:
                profiler.add("skeleton_pose_upload_count", 1)
                if bool(getattr(profiler, "enabled", False)):
                    profiler.current.animation_pose_upload_ms += (time.perf_counter() - started) * 1000.0
        else:
            self.cache_hits += 1
        return cached

    @staticmethod
    def _uses_sprite_wire_hull(material) -> bool:
        if material is None:
            return False
        blend_mode = str(getattr(material, "blend_mode", "") or "").upper()
        sprite_alpha = int(getattr(material, "sprite_alpha_source", 0) or 0)
        return blend_mode in {"ADDITIVE", "LIGHTEN"} and sprite_alpha > 0

    def _build_edge_indices(self, indices, vertex_count: int, *, positions=None, geometric: bool = False):
        import numpy as np

        if vertex_count <= 1:
            return None
        if indices is None:
            tri_indices = np.arange(vertex_count, dtype=np.uint32)
        else:
            tri_indices = np.asarray(indices, dtype=np.uint32).reshape(-1)
        if len(tri_indices) < 3:
            return None
        usable = len(tri_indices) - (len(tri_indices) % 3)
        if geometric and positions is not None:
            hull = self._build_geometric_boundary_edges(tri_indices[:usable], positions, vertex_count)
            if hull is not None and len(hull):
                return hull
        edge_set: set[tuple[int, int]] = set()
        out: list[int] = []
        for i in range(0, usable, 3):
            tri = [int(tri_indices[i]), int(tri_indices[i + 1]), int(tri_indices[i + 2])]
            if any(v < 0 or v >= vertex_count for v in tri):
                continue
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = (a, b) if a <= b else (b, a)
                if key in edge_set:
                    continue
                edge_set.add(key)
                out.extend((a, b))
        if not out:
            return None
        return np.ascontiguousarray(out, dtype=np.uint32)

    @staticmethod
    def _build_geometric_boundary_edges(tri_indices, positions, vertex_count: int):
        import numpy as np

        pos = np.asarray(positions, dtype=np.float32)
        tri = np.asarray(tri_indices, dtype=np.uint32).reshape(-1)
        if pos.ndim != 2 or pos.shape[1] < 3 or len(tri) < 3:
            return None

        def key(vertex_index: int) -> tuple[int, int, int]:
            vertex = pos[int(vertex_index), :3]
            return tuple(int(round(float(component) * 100000.0)) for component in vertex)

        edge_counts: dict[tuple[tuple[int, int, int], tuple[int, int, int]], int] = {}
        edge_representatives: dict[tuple[tuple[int, int, int], tuple[int, int, int]], tuple[int, int]] = {}
        for i in range(0, (len(tri) // 3) * 3, 3):
            face = [int(tri[i]), int(tri[i + 1]), int(tri[i + 2])]
            if any(v < 0 or v >= vertex_count for v in face):
                continue
            for left, right in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                a = key(left)
                b = key(right)
                if a == b:
                    continue
                edge_key = (a, b) if a <= b else (b, a)
                edge_counts[edge_key] = edge_counts.get(edge_key, 0) + 1
                edge_representatives.setdefault(edge_key, (left, right))

        out: list[int] = []
        for edge_key, count in edge_counts.items():
            if count != 1:
                continue
            left, right = edge_representatives[edge_key]
            out.extend((left, right))
        if not out:
            return None
        return np.ascontiguousarray(out, dtype=np.uint32)

    def _coerce_uvs(self, values, count: int):
        import numpy as np

        fixed = np.full((count, 2), 0.5, dtype=np.float32)
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < 2:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = arr[:rows, :2]
        except Exception:
            return fixed
        return fixed

    def _coerce_bone_indices(self, values, count: int):
        import numpy as np

        fixed = np.zeros((count, 4), dtype=np.uint32)
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.uint32)
            if arr.ndim != 2 or arr.shape[1] < 4:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = np.clip(arr[:rows, :4], 0, 127).astype(np.uint32)
        except Exception:
            return fixed
        return fixed

    def _coerce_bone_weights(self, values, count: int):
        import numpy as np

        fixed = np.zeros((count, 4), dtype=np.float32)
        fixed[:, 0] = 1.0
        if values is None:
            return fixed
        try:
            arr = np.asarray(values, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[1] < 4:
                return fixed
            rows = min(count, len(arr))
            if rows:
                fixed[:rows, :] = arr[:rows, :4]
                sub = fixed[:rows, :]
                sums = sub.sum(axis=1)
                valid = sums > 1e-8
                sub[valid] = sub[valid] / sums[valid, None]
                sub[~valid] = (1.0, 0.0, 0.0, 0.0)
        except Exception:
            return fixed
        return fixed

    def _pose_revision(self, anim_pose, mesh_data) -> int:
        return hash(
            (
                id(anim_pose),
                int(round(float(getattr(anim_pose, "time", 0.0) or 0.0) * 100000.0)),
                int(getattr(mesh_data, "skin_revision", 0) or 0),
                int(mesh_data.mesh_id),
            )
        ) & 0x7FFFFFFF

    def get_mesh_resource(self, mesh_id: int):
        return self.meshes.get(int(mesh_id))

    def get_or_upload_texture(
        self,
        texture_data,
        *,
        fallback_kind: str = "diffuse",
        lightmap: bool = False,
    ) -> WgpuTextureResource:
        texture_id = str(getattr(texture_data, "texture_id", "") or "")
        source_revision = tuple(getattr(texture_data, "source_revision", (0, 0, 0)) or (0, 0, 0))
        if not texture_id or texture_data is None or getattr(texture_data, "source", None) is None:
            self.missing_texture_count += 1
            log.debug("WgpuResourceCache: using fallback texture for %s", texture_id or fallback_kind)
            return self._fallback_texture("lightmap" if lightmap else fallback_kind, lightmap=lightmap)
        cached = self.textures.get(texture_id)
        if cached is not None and cached.source_revision == source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        if not self._renderer._consume_upload_budget("texture", texture_id):
            return self._fallback_texture("lightmap" if lightmap else fallback_kind, lightmap=lightmap)
        try:
            from src.core.rendering.mesh_render_data import texture_image_to_rgba8

            converted = texture_image_to_rgba8(texture_data)
            if converted is None:
                raise ValueError("texture adapter returned no RGBA8 data")
            width, height, rgba = converted
            resource = self._upload_rgba8_texture(
                texture_id,
                rgba,
                width,
                height,
                source_revision=source_revision,
                label=str(getattr(texture_data, "name", texture_id) or texture_id),
                lightmap=lightmap,
            )
            self.textures[texture_id] = resource
            self._recount()
            if bool(getattr(self._renderer, "debug_texture_uploads", False)):
                log.info("WgpuResourceCache: uploaded texture %s %sx%s rgba8", texture_id, width, height)
            return resource
        except Exception as exc:
            self.last_texture_upload_error = f"{texture_id}: {exc}"
            log.warning("WgpuResourceCache: using fallback texture for %s: %s", texture_id, exc)
            return self._fallback_texture("lightmap" if lightmap else fallback_kind, lightmap=lightmap)

    def get_or_create_material(self, material_data) -> WgpuMaterialResource | None:
        material_id = str(getattr(material_data, "material_id", "") or id(material_data))
        source_revision = tuple(getattr(material_data, "source_revision", (0, 0, 0, 0)) or (0, 0, 0, 0))
        cached = self.materials.get(material_id)
        if cached is not None and cached.source_revision == source_revision:
            self.cache_hits += 1
            return cached
        self.cache_misses += 1
        try:
            deferred_before = int(getattr(self._renderer, "_frame_deferred_texture_uploads", 0) or 0)
            diffuse_data = getattr(material_data, "diffuse_texture_data", None)
            diffuse = self.get_or_upload_texture(
                diffuse_data,
                fallback_kind="diffuse",
                lightmap=False,
            ) if diffuse_data is not None else self._fallback_texture("diffuse")
            lightmap_data = getattr(material_data, "lightmap_texture_data", None)
            has_lightmap = lightmap_data is not None and getattr(lightmap_data, "source", None) is not None
            lightmap = (
                self.get_or_upload_texture(lightmap_data, fallback_kind="lightmap", lightmap=True)
                if has_lightmap
                else self._fallback_texture("lightmap", lightmap=True)
            )
            layout = self._renderer.texture_bind_group_layout
            if layout is None:
                raise RuntimeError("texture bind group layout is not ready")
            bind_group = self._renderer.device.create_bind_group(
                layout=layout,
                entries=[
                    {"binding": 0, "resource": diffuse.texture_view},
                    {"binding": 1, "resource": diffuse.sampler},
                    {"binding": 2, "resource": lightmap.texture_view},
                    {"binding": 3, "resource": lightmap.sampler},
                ],
            )
            self.bind_group_creation_count += 1
            resource = WgpuMaterialResource(
                bind_group=bind_group,
                diffuse_texture_resource=diffuse,
                lightmap_texture_resource=lightmap,
                alpha_mode=str(getattr(material_data, "alpha_mode", "OPAQUE") or "OPAQUE"),
                alpha_cutoff=float(getattr(material_data, "alpha_cutoff", 0.5) or 0.5),
                blend_mode=str(getattr(material_data, "blend_mode", "ALPHA") or "ALPHA").upper(),
                sprite_alpha_source=int(getattr(material_data, "sprite_alpha_source", 0) or 0),
                sprite_glow=float(getattr(material_data, "sprite_glow", 0.0) or 0.0),
                double_sided=bool(getattr(material_data, "double_sided", False)),
                has_lightmap=has_lightmap,
                source_revision=source_revision,
            )
            deferred_after = int(getattr(self._renderer, "_frame_deferred_texture_uploads", 0) or 0)
            if deferred_after == deferred_before:
                self.materials[material_id] = resource
            return resource
        except Exception as exc:
            self.last_material_binding_error = f"{material_id}: {exc}"
            log.warning("WgpuResourceCache: material bind failed for %s: %s", material_id, exc)
            return None

    def _upload_rgba8_texture(
        self,
        texture_id: str,
        rgba: bytes,
        width: int,
        height: int,
        *,
        source_revision: tuple[int, int, int],
        label: str,
        lightmap: bool = False,
        fallback: bool = False,
    ) -> WgpuTextureResource:
        import wgpu

        device = self._renderer.device
        if device is None:
            raise RuntimeError("WGPU device is not ready")
        texture_format = self._texture_format(lightmap=lightmap)
        mip_chain = self._rgba8_mip_chain(rgba, int(width), int(height), lightmap=lightmap)
        mip_count = max(1, len(mip_chain))
        texture = device.create_texture(
            label=label,
            size=(int(width), int(height), 1),
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            dimension=wgpu.TextureDimension.d2,
            format=texture_format,
            mip_level_count=mip_count,
            sample_count=1,
        )
        byte_size = 0
        for mip_level, (mip_width, mip_height, mip_rgba) in enumerate(mip_chain):
            row_bytes = int(mip_width) * 4
            aligned_row_bytes = ((row_bytes + 255) // 256) * 256
            upload_row_bytes = aligned_row_bytes if int(mip_height) > 1 else row_bytes
            upload_bytes = mip_rgba
            if int(mip_height) > 1 and aligned_row_bytes != row_bytes:
                padded = bytearray(aligned_row_bytes * int(mip_height))
                for row in range(int(mip_height)):
                    src0 = row * row_bytes
                    dst0 = row * aligned_row_bytes
                    padded[dst0 : dst0 + row_bytes] = mip_rgba[src0 : src0 + row_bytes]
                upload_bytes = bytes(padded)
            device.queue.write_texture(
                {"texture": texture, "mip_level": int(mip_level), "origin": (0, 0, 0)},
                upload_bytes,
                {"offset": 0, "bytes_per_row": upload_row_bytes, "rows_per_image": int(mip_height)},
                (int(mip_width), int(mip_height), 1),
            )
            byte_size += int(mip_width) * int(mip_height) * 4
        self.texture_upload_count += 1
        sampler = device.create_sampler(
            address_mode_u=wgpu.AddressMode.clamp_to_edge if lightmap else wgpu.AddressMode.repeat,
            address_mode_v=wgpu.AddressMode.clamp_to_edge if lightmap else wgpu.AddressMode.repeat,
            address_mode_w=wgpu.AddressMode.clamp_to_edge,
            mag_filter=wgpu.FilterMode.linear,
            min_filter=wgpu.FilterMode.linear,
            mipmap_filter=wgpu.MipmapFilterMode.nearest if lightmap else wgpu.MipmapFilterMode.linear,
            lod_min_clamp=0.0,
            lod_max_clamp=float(max(0, mip_count - 1)),
        )
        return WgpuTextureResource(
            texture=texture,
            texture_view=texture.create_view(),
            sampler=sampler,
            width=int(width),
            height=int(height),
            mip_level_count=mip_count,
            format=str(texture_format),
            source_id=texture_id,
            source_revision=source_revision,
            label=label,
            byte_size=byte_size,
            fallback=fallback,
            lightmap=lightmap,
        )

    @staticmethod
    def _rgba8_mip_chain(
        rgba: bytes,
        width: int,
        height: int,
        *,
        lightmap: bool = False,
    ) -> list[tuple[int, int, bytes]]:
        base = (int(width), int(height), bytes(rgba))
        if lightmap or width <= 4 or height <= 4:
            return [base]
        try:
            from PIL import Image

            max_dim = max(int(width), int(height))
            max_level = min(6, max(0, int(math.log2(max_dim)) - 2)) if max_dim > 4 else 0
            if max_level <= 0:
                return [base]
            image = Image.frombytes("RGBA", (int(width), int(height)), bytes(rgba))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            chain = [base]
            for _level in range(1, max_level + 1):
                next_width = max(1, chain[-1][0] // 2)
                next_height = max(1, chain[-1][1] // 2)
                if next_width == chain[-1][0] and next_height == chain[-1][1]:
                    break
                mip = image.resize((next_width, next_height), resample)
                chain.append((next_width, next_height, mip.tobytes()))
                image = mip
            return chain
        except Exception:
            return [base]

    @staticmethod
    def _texture_format(*, lightmap: bool):
        import wgpu

        if lightmap:
            return wgpu.TextureFormat.rgba8unorm
        return getattr(wgpu.TextureFormat, "rgba8unorm_srgb", "rgba8unorm-srgb")

    def _fallback_texture(self, kind: str, *, lightmap: bool = False) -> WgpuTextureResource:
        if kind == "lightmap":
            if self._white_lightmap is None:
                self._white_lightmap = self._upload_rgba8_texture(
                    "__fallback_lightmap__",
                    bytes([255, 255, 255, 255]),
                    1,
                    1,
                    source_revision=(0, 1, 1),
                    label="WGPU white lightmap fallback",
                    lightmap=True,
                    fallback=True,
                )
                self.fallback_texture_count += 1
            return self._white_lightmap
        if kind == "missing_checker" or bool(getattr(self._renderer, "show_missing_texture_checker", False)):
            if self._missing_checker is None:
                a = _rgba8(getattr(self._renderer, "missing_texture_color_a", (1.0, 0.0, 1.0)))
                b = _rgba8(getattr(self._renderer, "missing_texture_color_b", (0.0, 0.0, 0.0)))
                self._missing_checker = self._upload_rgba8_texture(
                    "__fallback_missing_checker__",
                    a + b + b + a,
                    2,
                    2,
                    source_revision=(0, 2, 2),
                    label="WGPU missing texture checker",
                    fallback=True,
                )
                self.fallback_texture_count += 1
            return self._missing_checker
        if self._white_diffuse is None:
            self._white_diffuse = self._upload_rgba8_texture(
                "__fallback_diffuse__",
                bytes([255, 255, 255, 255]),
                1,
                1,
                source_revision=(0, 1, 1),
                label="WGPU white diffuse fallback",
                fallback=True,
            )
            self.fallback_texture_count += 1
        return self._white_diffuse

    def release_mesh(self, mesh_id: int) -> None:
        self.meshes.pop(int(mesh_id), None)
        self.skins.pop(int(mesh_id), None)
        self.last_invalidation_reason = f"mesh released: {mesh_id}"
        self._recount()

    def invalidate_texture(self, texture_id: str) -> None:
        removed = self.textures.pop(str(texture_id), None)
        if removed is not None:
            self._drop_materials_for_textures((removed,))
        self.last_invalidation_reason = f"texture invalidated: {texture_id}"
        self._recount()

    def invalidate_texture_source(self, texture_name: str, image=None) -> bool:
        """Evict one named texture and only materials bound to that resource."""
        clean = str(texture_name or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
        clean = clean.rsplit(".", 1)[0].lower()
        if not clean:
            return False
        image_suffix = f":{id(image)}" if image is not None else ""
        removed = []
        for texture_id in tuple(self.textures):
            key = str(texture_id).lower()
            matches_name = key == clean or key.startswith(clean + ":")
            matches_image = not image_suffix or key == clean + image_suffix
            if not (matches_name and matches_image):
                continue
            resource = self.textures.pop(texture_id, None)
            if resource is not None:
                removed.append(resource)
        if not removed and image_suffix:
            # The cache may predate image-qualified IDs; fall back to the name.
            for texture_id in tuple(self.textures):
                key = str(texture_id).lower()
                if key != clean and not key.startswith(clean + ":"):
                    continue
                resource = self.textures.pop(texture_id, None)
                if resource is not None:
                    removed.append(resource)
        if not removed:
            return False
        self._drop_materials_for_textures(tuple(removed))
        self.last_invalidation_reason = f"texture source invalidated: {clean}"
        self._recount()
        return True

    def _drop_materials_for_textures(self, removed_resources: tuple[object, ...]) -> None:
        removed_ids = {id(resource) for resource in removed_resources}
        for material_id, material in tuple(self.materials.items()):
            diffuse = getattr(material, "diffuse_texture_resource", None)
            lightmap = getattr(material, "lightmap_texture_resource", None)
            if id(diffuse) in removed_ids or id(lightmap) in removed_ids:
                self.materials.pop(material_id, None)

    def invalidate_material(self, material_id: str) -> None:
        self.materials.pop(str(material_id), None)
        self.last_invalidation_reason = f"material invalidated: {material_id}"

    def invalidate_all(self, reason: str = "all renderer resources invalidated") -> None:
        self.meshes.clear()
        self.skins.clear()
        self.textures.clear()
        self.materials.clear()
        self.uploaded_vertex_count = 0
        self.uploaded_index_count = 0
        self.uploaded_edge_index_count = 0
        self.texture_memory_bytes = 0
        self.fallback_texture_count = 0
        self.missing_texture_count = 0
        self.lightmap_texture_count = 0
        self.last_texture_upload_error = ""
        self.last_material_binding_error = ""
        self.last_skinning_error = ""
        self.uploaded_bone_matrix_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.mesh_upload_count = 0
        self.texture_upload_count = 0
        self.buffer_upload_count = 0
        self.bind_group_creation_count = 0
        self.last_invalidation_reason = str(reason or "all renderer resources invalidated")
        self._white_diffuse = None
        self._white_lightmap = None
        self._missing_checker = None

    def _recount(self) -> None:
        self.uploaded_vertex_count = sum(int(item.vertex_count) for item in self.meshes.values())
        self.uploaded_index_count = sum(int(item.index_count) for item in self.meshes.values())
        self.uploaded_edge_index_count = sum(int(item.edge_index_count) for item in self.meshes.values())
        self.texture_memory_bytes = sum(int(item.byte_size) for item in self.textures.values())
        self.lightmap_texture_count = sum(1 for item in self.textures.values() if item.lightmap)
        self.uploaded_bone_matrix_count = max((int(item.matrix_count) for item in self.skins.values()), default=0)



__all__ = tuple(name for name in globals() if not name.startswith("__"))
