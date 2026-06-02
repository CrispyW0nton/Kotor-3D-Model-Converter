"""Bridge GhostRigger render DTOs into a retained pygfx scene."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.rendering.mesh_render_data import iter_mesh_render_data, node_world_matrix

from .mesh_cache import PygfxMeshCache


class PygfxSceneBridge:
    """Updates retained pygfx objects from renderer-neutral scene data."""

    def __init__(self, gfx, scene, mesh_cache: PygfxMeshCache | None = None) -> None:
        self.gfx = gfx
        self.scene = scene
        self.mesh_cache = mesh_cache or PygfxMeshCache()
        self._ambient_light = None
        self._lights: dict[str, Any] = {}
        self.object_count = 0
        self.triangle_count = 0
        self.lighting_revision = None
        self.unsupported_lighting_features: list[str] = []

    def clear(self) -> None:
        for record in list(self.mesh_cache.records.values()):
            try:
                self.scene.remove(record.mesh)
            except Exception:
                pass
        self.mesh_cache.clear()
        for light in list(self._lights.values()):
            try:
                self.scene.remove(light)
            except Exception:
                pass
        self._lights.clear()
        if self._ambient_light is not None:
            try:
                self.scene.remove(self._ambient_light)
            except Exception:
                pass
        self._ambient_light = None

    def update_scene(
        self,
        model,
        *,
        textures: dict | None = None,
        selected_nodes: list | tuple | None = None,
        hovered_node=None,
        anim_pose=None,
        anim_base_pose=None,
        lighting_render_data=None,
    ) -> None:
        self.mesh_cache.begin_frame()
        selected_ids = {id(node) for node in (selected_nodes or ()) if node is not None}
        if hovered_node is not None:
            selected_ids.add(id(hovered_node))
        live_mesh_ids: set[int] = set()
        object_count = 0
        triangle_count = 0
        for mesh_data in iter_mesh_render_data(
            model,
            textures=textures or {},
            anim_pose=anim_pose,
            anim_base_pose=anim_base_pose,
        ):
            live_mesh_ids.add(int(mesh_data.mesh_id))
            selected = id(getattr(mesh_data, "source", None)) in selected_ids
            record = self.mesh_cache.get_or_create(mesh_data, self.gfx, self.scene, selected=selected)
            self._apply_world_matrix(record.mesh, mesh_data.world_matrix, record)
            object_count += 1
            if mesh_data.indices is not None:
                triangle_count += int(np.asarray(mesh_data.indices).reshape(-1).shape[0] // 3)
            else:
                triangle_count += int(np.asarray(mesh_data.positions).shape[0] // 3)
        self.mesh_cache.remove_missing(live_mesh_ids, self.scene)
        self.object_count = object_count
        self.triangle_count = triangle_count
        self.update_lighting(lighting_render_data)

    def update_dirty_transforms(self) -> None:
        """Apply transform-only changes to retained meshes without geometry extraction."""

        for record in self.mesh_cache.records.values():
            if not record.transform_dirty:
                continue
            try:
                matrix = node_world_matrix(record.source)
            except Exception:
                record.transform_dirty = False
                continue
            self._apply_world_matrix(record.mesh, matrix, record)
            record.transform_dirty = False

    def update_selection(self, selected_nodes: list | tuple | None, hovered_node=None) -> None:
        selected_ids = {id(node) for node in (selected_nodes or ()) if node is not None}
        if hovered_node is not None:
            selected_ids.add(id(hovered_node))
        self.mesh_cache.update_selection(self.gfx, selected_ids)

    def update_visibility(self) -> None:
        self.mesh_cache.update_visibility()

    def update_lighting(self, lighting_render_data) -> None:
        if lighting_render_data is None:
            return
        revision = getattr(lighting_render_data, "revision", None)
        if revision == self.lighting_revision:
            return
        self.lighting_revision = revision
        self.unsupported_lighting_features = []
        gfx = self.gfx
        ambient = tuple(float(c) for c in getattr(lighting_render_data, "ambient_color_rgb", (0.06, 0.06, 0.06))[:3])
        intensity = float(getattr(lighting_render_data, "global_intensity", 1.0) or 1.0)
        if self._ambient_light is None:
            self._ambient_light = gfx.AmbientLight(ambient, intensity=max(0.02, intensity))
            self.scene.add(self._ambient_light)
        else:
            self._ambient_light.color = ambient
            self._ambient_light.intensity = max(0.02, intensity)

        live_ids: set[str] = set()
        for light_data in getattr(lighting_render_data, "enabled_lights", ()):
            kind = str(getattr(light_data, "light_type", "point") or "point").replace("aurora_", "")
            if kind in {"ambient", "area", "spot"}:
                self.unsupported_lighting_features.append(kind)
                if kind != "spot":
                    continue
            light_id = str(getattr(light_data, "node_id", "") or getattr(light_data, "light_id", ""))
            live_ids.add(light_id)
            light = self._lights.get(light_id)
            if light is None:
                cls = gfx.DirectionalLight if kind == "directional" else gfx.PointLight
                light = cls(
                    tuple(getattr(light_data, "color_rgb", (1.0, 1.0, 1.0))),
                    intensity=float(getattr(light_data, "intensity", 1.0) or 1.0) * intensity,
                )
                self.scene.add(light)
                self._lights[light_id] = light
            light.color = tuple(getattr(light_data, "color_rgb", (1.0, 1.0, 1.0)))
            light.intensity = float(getattr(light_data, "intensity", 1.0) or 1.0) * intensity
            try:
                light.local.position = tuple(getattr(light_data, "position", (0.0, 0.0, 0.0)))
            except Exception:
                pass
        for light_id in list(self._lights):
            if light_id in live_ids:
                continue
            light = self._lights.pop(light_id)
            try:
                self.scene.remove(light)
            except Exception:
                pass

    def _apply_world_matrix(self, mesh, matrix, record) -> None:
        try:
            arr = np.asarray(matrix, dtype=np.float32).reshape((4, 4))
        except Exception:
            return
        key = tuple(round(float(v), 6) for v in arr.reshape(-1))
        if key == record.world_matrix_key:
            return
        record.world_matrix_key = key
        try:
            mesh.local.matrix = arr
        except Exception:
            try:
                mesh.local.position = (float(arr[0, 3]), float(arr[1, 3]), float(arr[2, 3]))
            except Exception:
                pass

    def diagnostics(self) -> dict[str, object]:
        return {
            "object_count": int(self.object_count),
            "triangle_count": int(self.triangle_count),
            "unsupported_lighting_features": tuple(sorted(set(self.unsupported_lighting_features))),
            **self.mesh_cache.diagnostics(),
        }
