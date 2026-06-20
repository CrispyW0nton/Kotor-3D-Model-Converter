"""Optional native renderer adapter for the GhostRigger runtime DLL."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sized

from src.adapters.rendering.native_core.binding import NativeRuntimeBinding
from src.adapters.rendering.null_renderer import NullDiagnosticRenderer
from src.core.rendering.renderer_backend import RendererBackend
from src.core.rendering.renderer_capabilities import RendererCapabilities
from src.core.rendering.picking import PickHit


class NativeViewportRenderer(NullDiagnosticRenderer):
    """N1 native-runtime contract adapter.

    The DLL currently exposes lifecycle and capability diagnostics only. Real
    rendering will be added behind this adapter in later native migration slices.
    """

    name = "GhostRigger Native Runtime"
    backend_id = RendererBackend.NATIVE_D3D12.value

    def __init__(self, binding: NativeRuntimeBinding | None = None):
        super().__init__()
        self.name = "GhostRigger Native Runtime"
        self.backend_id = RendererBackend.NATIVE_D3D12.value
        self._binding = binding
        self._load_error = ""
        self._runtime_handle = 0
        self._scene_handle = 0
        self._mesh_handles: dict[object, int] = {}
        self._native_mesh_keys: dict[int, object] = {}
        self._texture_handles: dict[object, int] = {}
        self._skin_palette_handles: dict[object, int] = {}
        self._dirty_mesh_count = 0
        self._dirty_texture_count = 0
        self._dirty_skin_palette_count = 0
        self._last_native_frame: dict[str, object] = {}
        if self._binding is None:
            try:
                self._binding = NativeRuntimeBinding.load()
            except OSError as exc:
                self._load_error = str(exc)
        if self._binding is not None:
            try:
                self._runtime_handle = self._binding.create()
                self._scene_handle = self._binding.scene_create(self._runtime_handle)
            except Exception as exc:
                self._load_error = str(exc)
                self._binding = None
                self._runtime_handle = 0
                self._scene_handle = 0

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass

    def is_available(self) -> bool:
        return self._binding is not None and not self._load_error

    def get_capabilities(self) -> RendererCapabilities:
        if self._binding is None:
            return RendererCapabilities(
                backend_id=self.backend_id,
                name=self.name,
                available=False,
                reason=self._load_error or "GhostRigger.Runtime.Core.Host.dll has not been built",
                api="Native/D3D12",
                diagnostic_only=True,
                requires_restart=False,
                supports_hot_switch=True,
            )
        payload = self._binding.capabilities()
        payload["backend_id"] = self.backend_id
        payload["name"] = self.name
        payload.setdefault("api", "Native/D3D12")
        payload.setdefault("diagnostic_only", True)
        payload.setdefault("supports_hot_switch", True)
        return RendererCapabilities.from_dict(payload)

    def get_diagnostics(self) -> dict:
        diagnostics = {
            "name": self.name,
            "backend_id": self.backend_id,
            "available": self.is_available(),
            "api": "Native/D3D12",
            "phase": "N1 adapter contract",
        }
        if self._load_error:
            diagnostics["reason"] = self._load_error
        if self._binding is not None:
            diagnostics["runtime_version"] = self._binding.version()
            diagnostics["runtime_path"] = str(self._binding.path)
            diagnostics.update(self._binding.diagnostics(self._runtime_handle))
            if self._scene_handle:
                diagnostics["scene"] = self._binding.scene_diagnostics(
                    self._runtime_handle, self._scene_handle
                )
            if self._last_native_frame:
                diagnostics["native_frame"] = dict(self._last_native_frame)
        return diagnostics

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        if self._binding is not None and self._runtime_handle and self._scene_handle:
            frame = self._binding.scene_render_frame(
                self._runtime_handle,
                self._scene_handle,
                viewport_width=max(0, int(W)),
                viewport_height=max(0, int(H)),
                device_pixel_ratio=float(kwargs.get("device_pixel_ratio", 1.0) or 1.0),
                time_seconds=float(kwargs.get("time_seconds", time.perf_counter())),
                flags=_frame_flags(self),
                dirty_mesh_count=self._dirty_mesh_count,
                dirty_texture_count=self._dirty_texture_count,
                dirty_skin_palette_count=self._dirty_skin_palette_count,
            )
            self._last_native_frame = frame
            if frame.get("available"):
                self.perf["tri_count"] = int(frame.get("triangle_count", 0) or 0)
                self._dirty_mesh_count = 0
                self._dirty_texture_count = 0
                self._dirty_skin_palette_count = 0
        return super().render(scene, camera, W, H, *args, **kwargs)

    def clear_caches(self) -> None:
        if self._binding is not None and self._runtime_handle and self._scene_handle:
            self._binding.scene_clear(self._runtime_handle, self._scene_handle)
        self._mesh_handles.clear()
        self._native_mesh_keys.clear()
        self._texture_handles.clear()
        self._skin_palette_handles.clear()
        self._dirty_mesh_count = 0
        self._dirty_texture_count = 0
        self._dirty_skin_palette_count = 0
        self._last_native_frame = {}
        super().clear_caches()

    def upload_mesh(self, mesh):
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return None

        mesh_key = getattr(mesh, "mesh_id", id(mesh))
        if mesh_key in self._mesh_handles:
            return self._mesh_handles[mesh_key]

        vertex_count = _safe_len(getattr(mesh, "positions", None))
        if vertex_count <= 0:
            return None

        index_count = _safe_len(getattr(mesh, "indices", None))
        material = getattr(mesh, "material", None)
        material_slot = _material_slot(material)
        flags = _mesh_flags(mesh)
        bounds_min, bounds_max = _mesh_bounds(getattr(mesh, "positions", None))
        native_id = self._binding.scene_add_mesh(
            self._runtime_handle,
            self._scene_handle,
            vertex_count=vertex_count,
            index_count=index_count,
            material_slot=material_slot,
            flags=flags,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
        )
        if native_id:
            self._mesh_handles[mesh_key] = native_id
            self._native_mesh_keys[native_id] = mesh_key
            self._binding.scene_update_mesh_buffers(
                self._runtime_handle,
                self._scene_handle,
                native_id,
                positions=getattr(mesh, "positions", None),
                indices=getattr(mesh, "indices", None),
                flags=flags,
            )
            self._binding.scene_update_mesh_transform(
                self._runtime_handle,
                self._scene_handle,
                native_id,
                world_matrix=getattr(mesh, "world_matrix", None),
                flags=flags,
            )
            if getattr(mesh, "bone_indices", None) is not None and getattr(mesh, "bone_weights", None) is not None:
                self._binding.scene_update_mesh_skinning(
                    self._runtime_handle,
                    self._scene_handle,
                    native_id,
                    bone_indices=getattr(mesh, "bone_indices", None),
                    bone_weights=getattr(mesh, "bone_weights", None),
                    flags=flags,
                )
            diffuse_texture_id = self._upload_material_texture(getattr(material, "diffuse_texture_data", None))
            lightmap_texture_id = self._upload_material_texture(getattr(material, "lightmap_texture_data", None))
            self._binding.scene_update_mesh_material(
                self._runtime_handle,
                self._scene_handle,
                native_id,
                material_slot=material_slot,
                flags=flags,
                diffuse_texture_id=diffuse_texture_id or 0,
                lightmap_texture_id=lightmap_texture_id or 0,
                base_color=_material_color(mesh, material),
            )
            self._dirty_mesh_count += 1
            return native_id
        return None

    def update_mesh_vertex_range(self, mesh_key, *, start_vertex: int, positions, flags: int = 0) -> bool:
        native_id = self._mesh_handles.get(mesh_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_mesh_vertex_range(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            start_vertex=max(0, int(start_vertex)),
            positions=positions,
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_mesh_count += 1
        return updated

    def update_mesh_index_range(self, mesh_key, *, start_index: int, indices, flags: int = 0) -> bool:
        native_id = self._mesh_handles.get(mesh_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_mesh_index_range(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            start_index=max(0, int(start_index)),
            indices=indices,
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_mesh_count += 1
        return updated

    def update_mesh_material_state(
        self,
        mesh_key,
        *,
        flags: int = 0,
        base_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> bool:
        native_id = self._mesh_handles.get(mesh_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_mesh_material_state(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            flags=max(0, int(flags)),
            base_color=base_color,
        )
        if updated:
            self._dirty_mesh_count += 1
        return updated

    def _upload_material_texture(self, texture) -> int:
        if texture is None:
            return 0
        native_id = self.upload_texture(texture)
        try:
            return int(native_id or 0)
        except Exception:
            return 0

    def query_bounds(
        self,
        bounds_min: tuple[float, float, float],
        bounds_max: tuple[float, float, float],
        *,
        flags: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_query_bounds(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native retained bounds query")
        return result

    def assemble_draw_list(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
        max_item_count: int | None = None,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_assemble_draw_list(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native draw list assembly")
        return result

    def record_commands(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
        max_item_count: int | None = None,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_record_commands(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native command recording stats")
        return result

    def get_resource_residency(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_get_resource_residency(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native resource residency stats")
        return result

    def get_resource_upload_plan(self, *, flags: int = 0, max_item_count: int = 0) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_get_resource_upload_plan(
            self._runtime_handle,
            self._scene_handle,
            flags=flags,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native resource upload plan")
        return result

    def allocate_device_resources(self, *, flags: int = 0, max_item_count: int = 0) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_allocate_device_resources(
            self._runtime_handle,
            self._scene_handle,
            flags=flags,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native device resource allocation")
        return result

    def commit_device_resource_uploads(self, *, flags: int = 0, max_item_count: int = 0) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_commit_device_resource_uploads(
            self._runtime_handle,
            self._scene_handle,
            flags=flags,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native device resource upload commit")
        return result

    def transition_device_resources(self, *, flags: int = 0, max_item_count: int = 0) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_transition_device_resources(
            self._runtime_handle,
            self._scene_handle,
            flags=flags,
            max_item_count=max_item_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native device resource transition")
        return result

    def get_gpu_skinning_dispatch(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_get_gpu_skinning_dispatch(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native GPU skinning dispatch stats")
        return result

    def get_cpu_skinning_fallback_batch(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_get_cpu_skinning_fallback_batch(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native CPU skinning fallback batch stats")
        return result

    def execute_cpu_skinning_fallback(
        self,
        *,
        bounds_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
        bounds_max: tuple[float, float, float] = (0.0, 0.0, 0.0),
        flags: int = 0,
        max_draw_count: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        result = self._binding.scene_execute_cpu_skinning_fallback(
            self._runtime_handle,
            self._scene_handle,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            flags=flags,
            max_draw_count=max_draw_count,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native CPU skinning fallback execution")
        return result

    def read_cpu_skinned_positions(
        self,
        mesh_key,
        *,
        start_vertex: int = 0,
        vertex_count: int = 0,
        flags: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        native_mesh_id = self._mesh_handles.get(mesh_key, 0)
        result = self._binding.scene_read_cpu_skinned_positions(
            self._runtime_handle,
            self._scene_handle,
            native_mesh_id,
            start_vertex=start_vertex,
            vertex_count=vertex_count,
            flags=flags,
        )
        result.setdefault("backend_id", self.backend_id)
        result.setdefault("method", "Native CPU skinned position readback")
        return result

    def pick(self, request, scene=None, camera=None):
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return PickHit(renderer_backend=self.backend_id, diagnostic={"reason": "native runtime unavailable"})
        ray = _pick_ray_from_request(request)
        diagnostic = {
            "method": "Native bounds raycast",
            "backend_id": self.backend_id,
            "candidate_count": len(self._native_mesh_keys),
        }
        if ray is None:
            diagnostic["reason"] = "pick request does not include ray_origin/ray_direction"
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)

        origin, direction = ray
        result = self._binding.scene_pick_bounds(
            self._runtime_handle,
            self._scene_handle,
            origin=origin,
            direction=direction,
            flags=0,
        )
        diagnostic.update(result)
        if not result.get("available"):
            return PickHit(renderer_backend=self.backend_id, diagnostic=diagnostic)
        native_mesh_id = int(result.get("mesh_id", 0) or 0)
        mesh_key = self._native_mesh_keys.get(native_mesh_id)
        if not result.get("hit") or mesh_key is None:
            diagnostic["result"] = "miss"
            return PickHit(renderer_backend=self.backend_id, source_backend=self.backend_id, diagnostic=diagnostic)
        diagnostic["result"] = "hit"
        return PickHit(
            hit=True,
            kind="mesh_bounds",
            object_id=mesh_key,
            mesh_id=mesh_key,
            node_id=mesh_key,
            distance=float(result.get("distance", 0.0) or 0.0),
            world_position=result.get("world_position"),
            screen_position=(
                int(getattr(request, "x", 0) or 0),
                int(getattr(request, "y", 0) or 0),
            ),
            hit_kind="mesh_bounds",
            source_backend=self.backend_id,
            raw_id=native_mesh_id,
            renderer_backend=self.backend_id,
            diagnostic=diagnostic,
        )

    def upload_texture(self, texture):
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return None

        texture_key = _texture_key(texture)
        if texture_key in self._texture_handles:
            return self._texture_handles[texture_key]

        width, height = _texture_size(texture)
        if width <= 0 or height <= 0:
            return None
        byte_size = _texture_byte_size(texture, width, height)
        native_id = self._binding.scene_add_texture(
            self._runtime_handle,
            self._scene_handle,
            width=width,
            height=height,
            byte_size=byte_size,
            format_id=_texture_format(texture),
            flags=_texture_flags(texture),
        )
        if native_id:
            self._texture_handles[texture_key] = native_id
            payload = _texture_payload(texture)
            if payload:
                self._binding.scene_update_texture_data(
                    self._runtime_handle,
                    self._scene_handle,
                    native_id,
                    data=payload,
                    row_pitch=_texture_row_pitch(texture, width),
                    flags=_texture_flags(texture),
                )
            self._dirty_texture_count += 1
            return native_id
        return None

    def update_texture_region(
        self,
        texture_key,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        data,
        row_pitch: int = 0,
        flags: int = 0,
    ) -> bool:
        native_id = self._texture_handles.get(texture_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_texture_region(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            x=max(0, int(x)),
            y=max(0, int(y)),
            width=max(0, int(width)),
            height=max(0, int(height)),
            data=data,
            row_pitch=max(0, int(row_pitch)),
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_texture_count += 1
        return updated

    def release_resource(self, resource_id) -> None:
        native_id = self._mesh_handles.pop(resource_id, None)
        if (
            native_id
            and self._binding is not None
            and self._runtime_handle
            and self._scene_handle
        ):
            self._binding.scene_remove_mesh(self._runtime_handle, self._scene_handle, native_id)
            self._native_mesh_keys.pop(native_id, None)
            self._dirty_mesh_count += 1
            return
        native_texture_id = self._texture_handles.pop(resource_id, None)
        if (
            native_texture_id
            and self._binding is not None
            and self._runtime_handle
            and self._scene_handle
        ):
            self._binding.scene_remove_texture(
                self._runtime_handle, self._scene_handle, native_texture_id
            )
            self._dirty_texture_count += 1
            return
        native_palette_id = self._skin_palette_handles.pop(resource_id, None)
        if (
            native_palette_id
            and self._binding is not None
            and self._runtime_handle
            and self._scene_handle
        ):
            self._binding.scene_remove_skin_palette(
                self._runtime_handle, self._scene_handle, native_palette_id
            )
            self._dirty_skin_palette_count += 1

    def upload_skin_palette(self, palette_key, *, bone_count: int, flags: int = 0):
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return None
        if palette_key in self._skin_palette_handles:
            return self._skin_palette_handles[palette_key]
        native_id = self._binding.scene_add_skin_palette(
            self._runtime_handle,
            self._scene_handle,
            bone_count=max(0, int(bone_count)),
            flags=max(0, int(flags)),
        )
        if native_id:
            self._skin_palette_handles[palette_key] = native_id
            self._dirty_skin_palette_count += 1
            return native_id
        return None

    def update_skin_palette(self, palette_key, *, bone_count: int, flags: int = 0, matrices=None) -> bool:
        native_id = self._skin_palette_handles.get(palette_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = True
        if bone_count >= 0:
            updated = self._binding.scene_update_skin_palette(
                self._runtime_handle,
                self._scene_handle,
                native_id,
                bone_count=max(0, int(bone_count)),
                flags=max(0, int(flags)),
            )
        if updated and matrices is not None:
            updated = self._binding.scene_update_skin_palette_matrices(
                self._runtime_handle,
                self._scene_handle,
                native_id,
                matrices=matrices,
                flags=max(0, int(flags)),
            )
        if updated:
            self._dirty_skin_palette_count += 1
        return updated

    def update_skin_palette_matrices(self, palette_key, matrices, *, flags: int = 0) -> bool:
        native_id = self._skin_palette_handles.get(palette_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_skin_palette_matrices(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            matrices=matrices,
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_skin_palette_count += 1
        return updated

    def update_skin_palette_matrix_range(
        self,
        palette_key,
        *,
        start_matrix: int,
        matrices,
        flags: int = 0,
    ) -> bool:
        native_id = self._skin_palette_handles.get(palette_key)
        if (
            not native_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_update_skin_palette_matrix_range(
            self._runtime_handle,
            self._scene_handle,
            native_id,
            start_matrix=max(0, int(start_matrix)),
            matrices=matrices,
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_skin_palette_count += 1
        return updated

    def bind_mesh_skin_palette(self, mesh_key, palette_key, *, flags: int = 0) -> bool:
        native_mesh_id = self._mesh_handles.get(mesh_key)
        native_palette_id = self._skin_palette_handles.get(palette_key)
        if (
            not native_mesh_id
            or not native_palette_id
            or self._binding is None
            or not self._runtime_handle
            or not self._scene_handle
        ):
            return False
        updated = self._binding.scene_bind_mesh_skin_palette(
            self._runtime_handle,
            self._scene_handle,
            native_mesh_id,
            palette_id=native_palette_id,
            flags=max(0, int(flags)),
        )
        if updated:
            self._dirty_mesh_count += 1
        return updated

    def update_animation_sample(
        self,
        clip,
        *,
        time_seconds: float,
        duration_seconds: float = 0.0,
        pose_matrices=None,
        looped: bool = False,
        flags: int = 0,
    ) -> bool:
        if self._binding is None or not self._runtime_handle or not self._scene_handle:
            return False
        sample_flags = max(0, int(flags))
        if looped:
            sample_flags |= 1
        return self._binding.scene_update_animation_sample(
            self._runtime_handle,
            self._scene_handle,
            clip_hash=_stable_clip_hash(clip),
            time_seconds=float(time_seconds),
            duration_seconds=max(0.0, float(duration_seconds)),
            pose_matrices=pose_matrices,
            flags=sample_flags,
        )

    def cpu_skin_vertices(
        self,
        *,
        positions,
        bone_indices,
        bone_weights,
        bone_matrices,
        normals=None,
        flags: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        return self._binding.cpu_skin_vertices(
            self._runtime_handle,
            positions=positions,
            normals=normals,
            bone_indices=bone_indices,
            bone_weights=bone_weights,
            bone_matrices=bone_matrices,
            flags=max(0, int(flags)),
        )

    def sample_animation_palette(
        self,
        *,
        previous_matrices,
        next_matrices,
        interpolation_t: float,
        flags: int = 0,
    ) -> dict:
        if self._binding is None or not self._runtime_handle:
            return {"available": False, "reason": "native runtime unavailable"}
        return self._binding.sample_animation_palette(
            self._runtime_handle,
            previous_matrices=previous_matrices,
            next_matrices=next_matrices,
            interpolation_t=float(interpolation_t),
            flags=max(0, int(flags)),
        )

    def shutdown(self) -> None:
        if self._binding is not None and self._runtime_handle and self._scene_handle:
            self._binding.scene_destroy(self._runtime_handle, self._scene_handle)
        self._scene_handle = 0
        self._mesh_handles.clear()
        self._native_mesh_keys.clear()
        self._texture_handles.clear()
        self._skin_palette_handles.clear()
        if self._binding is not None and self._runtime_handle:
            self._binding.destroy(self._runtime_handle)
        self._runtime_handle = 0
        self._last_native_frame = {}


def _safe_len(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Sized):
        return len(value)
    try:
        return len(value)  # type: ignore[arg-type]
    except Exception:
        return 0


def _material_slot(material) -> int:
    raw = getattr(material, "material_slot", 0)
    try:
        return max(0, int(raw))
    except Exception:
        return 0


def _mesh_flags(mesh) -> int:
    flags = 0
    if bool(getattr(mesh, "is_skinned", False)):
        flags |= 1
    material = getattr(mesh, "material", None)
    if bool(getattr(material, "double_sided", False)):
        flags |= 2
    if bool(getattr(material, "unlit", False)):
        flags |= 4
    return flags


def _material_color(mesh, material) -> tuple[float, float, float, float]:
    raw = getattr(mesh, "material_color", None)
    if raw is None and material is not None:
        raw = getattr(material, "base_color", None) or getattr(material, "color", None)
    if raw is None:
        return (1.0, 1.0, 1.0, 1.0)
    try:
        values = tuple(float(raw[index]) for index in range(min(4, len(raw))))
    except Exception:
        return (1.0, 1.0, 1.0, 1.0)
    if len(values) == 3:
        return values[0], values[1], values[2], 1.0
    if len(values) >= 4:
        return values[0], values[1], values[2], values[3]
    return (1.0, 1.0, 1.0, 1.0)


def _mesh_bounds(positions) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    if positions is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    try:
        mins = positions.min(axis=0)
        maxs = positions.max(axis=0)
        return _vec3(mins), _vec3(maxs)
    except Exception:
        pass

    try:
        iterator = iter(positions)
    except TypeError:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    found = False
    mins = [0.0, 0.0, 0.0]
    maxs = [0.0, 0.0, 0.0]
    for row in iterator:
        try:
            values = [float(row[0]), float(row[1]), float(row[2])]
        except Exception:
            continue
        if not found:
            mins = values[:]
            maxs = values[:]
            found = True
            continue
        for axis in range(3):
            mins[axis] = min(mins[axis], values[axis])
            maxs[axis] = max(maxs[axis], values[axis])
    if not found:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    return tuple(mins), tuple(maxs)  # type: ignore[return-value]


def _frame_flags(renderer: NativeViewportRenderer) -> int:
    flags = 0
    if bool(getattr(renderer, "show_solid", False)):
        flags |= 1
    if bool(getattr(renderer, "show_wireframe", False)):
        flags |= 2
    if bool(getattr(renderer, "show_texture", False)):
        flags |= 4
    if bool(getattr(renderer, "show_grid", False)):
        flags |= 8
    return flags


def _pick_ray_from_request(request) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    origin = getattr(request, "ray_origin", None)
    direction = getattr(request, "ray_direction", None)
    if origin is None or direction is None:
        ray = getattr(request, "ray", None)
        if ray is not None:
            origin = getattr(ray, "origin", None)
            direction = getattr(ray, "direction", None)
    if origin is None or direction is None:
        return None
    return _vec3(origin), _vec3(direction)


def _vec3(values) -> tuple[float, float, float]:
    try:
        return float(values[0]), float(values[1]), float(values[2])
    except Exception:
        return (0.0, 0.0, 0.0)


def _texture_key(texture):
    return (
        getattr(texture, "texture_id", None)
        or getattr(texture, "name", None)
        or id(texture)
    )


def _texture_size(texture) -> tuple[int, int]:
    width = getattr(texture, "width", None)
    height = getattr(texture, "height", None)
    source = getattr(texture, "source", None)
    if (width is None or height is None) and source is not None:
        size = getattr(source, "size", None)
        if size and len(size) >= 2:
            width, height = size[:2]
    try:
        return max(0, int(width or 0)), max(0, int(height or 0))
    except Exception:
        return 0, 0


def _texture_byte_size(texture, width: int, height: int) -> int:
    raw = getattr(texture, "byte_size", None)
    if raw is None:
        data = getattr(texture, "data", None)
        if data is not None:
            try:
                raw = len(data)
            except Exception:
                raw = None
    if raw is None:
        raw = width * height * 4
    try:
        return max(0, int(raw))
    except Exception:
        return width * height * 4


def _texture_format(texture) -> int:
    raw = getattr(texture, "format_id", 0)
    try:
        return max(0, int(raw))
    except Exception:
        return 0


def _texture_flags(texture) -> int:
    flags = 0
    if bool(getattr(texture, "has_alpha", False)):
        flags |= 1
    if bool(getattr(texture, "is_lightmap", False)):
        flags |= 2
    return flags


def _texture_payload(texture) -> bytes:
    data = getattr(texture, "data", None)
    if data is not None:
        try:
            return bytes(data)
        except Exception:
            try:
                return data.tobytes()
            except Exception:
                pass
    source = getattr(texture, "source", None)
    if source is not None:
        try:
            return source.tobytes()
        except Exception:
            pass
    return b""


def _texture_row_pitch(texture, width: int) -> int:
    raw = getattr(texture, "row_pitch", None)
    if raw is not None:
        try:
            return max(0, int(raw))
        except Exception:
            pass
    return max(0, int(width) * 4)


def _stable_clip_hash(clip) -> int:
    if isinstance(clip, int):
        return max(0, int(clip))
    text = str(clip or "")
    digest = hashlib.blake2b(text.encode("utf-8", errors="replace"), digest_size=8).digest()
    return int.from_bytes(digest, "little", signed=False)
