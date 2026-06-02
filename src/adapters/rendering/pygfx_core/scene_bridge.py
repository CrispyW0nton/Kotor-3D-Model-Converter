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
        self._default_directional_light = None
        self._lights: dict[str, Any] = {}
        self._overlay_objects: list[Any] = []
        self.object_count = 0
        self.triangle_count = 0
        self.lighting_revision = None
        self.unsupported_lighting_features: list[str] = []
        self.gizmo_overlay_segments = 0
        self.skeleton_overlay_segments = 0
        self.light_overlay_segments = 0

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
        if self._default_directional_light is not None:
            try:
                self.scene.remove(self._default_directional_light)
            except Exception:
                pass
        self._default_directional_light = None
        self.clear_overlays()

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
        force_geometry_update: bool = False,
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
            record = self.mesh_cache.get_or_create(
                mesh_data,
                self.gfx,
                self.scene,
                selected=selected,
                force_geometry_update=force_geometry_update,
            )
            self._apply_world_matrix(record.mesh, mesh_data.world_matrix, record)
            if getattr(record, "edge_mesh", None) is not None:
                self._apply_world_matrix(record.edge_mesh, mesh_data.world_matrix, record)
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
            if getattr(record, "edge_mesh", None) is not None:
                self._apply_world_matrix(record.edge_mesh, matrix, record)
            record.transform_dirty = False

    def update_selection(self, selected_nodes: list | tuple | None, hovered_node=None) -> None:
        selected_ids = {id(node) for node in (selected_nodes or ()) if node is not None}
        if hovered_node is not None:
            selected_ids.add(id(hovered_node))
        self.mesh_cache.update_selection(self.gfx, selected_ids)

    def update_visibility(self) -> None:
        self.mesh_cache.update_visibility()

    def apply_view_style(
        self,
        *,
        show_solid: bool = True,
        show_wireframe: bool = False,
        show_texture: bool = True,
        render_mode: str = "realistic",
        xray: bool = False,
    ) -> None:
        self.mesh_cache.apply_view_style(
            show_solid=show_solid,
            show_wireframe=show_wireframe,
            show_texture=show_texture,
            render_mode=render_mode,
            xray=xray,
        )

    def update_overlays(
        self,
        *,
        gizmo_render_data=None,
        skeleton_render_data=None,
        lighting_render_data=None,
    ) -> None:
        self.clear_overlays()
        self._add_gizmo_overlay(gizmo_render_data)
        self._add_skeleton_overlay(skeleton_render_data)
        self._add_lighting_overlay(lighting_render_data)

    def clear_overlays(self) -> None:
        for obj in self._overlay_objects:
            try:
                self.scene.remove(obj)
            except Exception:
                pass
        self._overlay_objects.clear()
        self.gizmo_overlay_segments = 0
        self.skeleton_overlay_segments = 0
        self.light_overlay_segments = 0

    def update_lighting(self, lighting_render_data) -> None:
        if lighting_render_data is None:
            self._ensure_default_lighting()
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
            self._ambient_light = gfx.AmbientLight(ambient, intensity=max(0.22, intensity))
            self.scene.add(self._ambient_light)
        else:
            self._ambient_light.color = ambient
            self._ambient_light.intensity = max(0.22, intensity)

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
                if kind == "directional":
                    direction = self._vec3(getattr(light_data, "direction", (0.0, 0.0, -1.0)))
                    target = (
                        float(light.local.position[0]) + direction[0],
                        float(light.local.position[1]) + direction[1],
                        float(light.local.position[2]) + direction[2],
                    )
                    try:
                        light.local.reference_up = (0.0, 0.0, 1.0)
                    except Exception:
                        pass
                    light.look_at(target)
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
        if not live_ids:
            self._ensure_default_directional_light()
        elif self._default_directional_light is not None:
            try:
                self.scene.remove(self._default_directional_light)
            except Exception:
                pass
            self._default_directional_light = None

    def _ensure_default_lighting(self) -> None:
        gfx = self.gfx
        if self._ambient_light is None:
            self._ambient_light = gfx.AmbientLight((0.72, 0.76, 0.82), intensity=0.55)
            self.scene.add(self._ambient_light)
        else:
            self._ambient_light.color = (0.72, 0.76, 0.82)
            self._ambient_light.intensity = max(float(getattr(self._ambient_light, "intensity", 0.0) or 0.0), 0.55)
        self._ensure_default_directional_light()

    def _ensure_default_directional_light(self) -> None:
        gfx = self.gfx
        if self._default_directional_light is None:
            self._default_directional_light = gfx.DirectionalLight((1.0, 0.96, 0.88), intensity=1.35)
            self.scene.add(self._default_directional_light)
        light = self._default_directional_light
        try:
            light.local.position = (12.0, -18.0, 18.0)
            light.local.reference_up = (0.0, 0.0, 1.0)
            light.look_at((0.0, 0.0, 0.0))
        except Exception:
            pass

    def _add_gizmo_overlay(self, gizmo_render_data) -> None:
        if gizmo_render_data is None:
            return
        for command in getattr(gizmo_render_data, "commands", ()) or ():
            if not bool(getattr(command, "world_space", True)):
                continue
            points = tuple(getattr(command, "points", ()) or ())
            if len(points) < 2:
                continue
            colour = tuple(float(c) for c in getattr(command, "colour", (1.0, 1.0, 1.0, 1.0))[:4])
            thickness = max(1.0, float(getattr(command, "thickness", 2.0) or 2.0))
            kind = str(getattr(command, "kind", "line") or "line").lower()
            segment_points = self._polyline_to_segments(points) if kind == "polyline" else points
            self.gizmo_overlay_segments += self._add_line_segments(
                segment_points,
                colour,
                thickness=thickness,
                name="pygfx-gizmo",
            )

    def _add_skeleton_overlay(self, skeleton_render_data) -> None:
        if skeleton_render_data is None:
            return
        line_points: list[tuple[float, float, float]] = []
        selected_points: list[tuple[float, float, float]] = []
        joint_points: list[tuple[float, float, float]] = []
        for bone in getattr(skeleton_render_data, "bones", ()) or ():
            if not bool(getattr(bone, "visible", True)):
                continue
            head = self._vec3(getattr(bone, "head_position", (0.0, 0.0, 0.0)))
            tail = self._vec3(getattr(bone, "tail_position", head))
            if bool(getattr(skeleton_render_data, "show_links", True)) and head != tail:
                target = selected_points if bool(getattr(bone, "selected", False)) else line_points
                target.extend((head, tail))
            if bool(getattr(skeleton_render_data, "show_dots", True)):
                joint_points.append(head)
        self.skeleton_overlay_segments += self._add_line_segments(line_points, (0.38, 0.68, 1.0, 1.0), thickness=2.0, name="pygfx-skeleton")
        self.skeleton_overlay_segments += self._add_line_segments(selected_points, (1.0, 0.82, 0.20, 1.0), thickness=3.0, name="pygfx-skeleton-selected")
        self._add_points(joint_points, (0.95, 0.95, 1.0, 1.0), size=5.0, name="pygfx-joints")

    def _add_lighting_overlay(self, lighting_render_data) -> None:
        if lighting_render_data is None:
            return
        try:
            from src.core.lighting.render_data import (
                build_light_helper_line_batches,
                build_light_volume_line_batches,
            )
        except Exception:
            return
        for color, vertices in build_light_helper_line_batches(lighting_render_data):
            rgba = tuple(float(c) for c in (*color[:3], 1.0))
            self.light_overlay_segments += self._add_line_segments(vertices, rgba, thickness=2.0, name="pygfx-light-helper")
        for color, vertices in build_light_volume_line_batches(lighting_render_data):
            rgba = tuple(float(c) for c in (*color[:3], 0.45))
            self.light_overlay_segments += self._add_line_segments(vertices, rgba, thickness=1.0, name="pygfx-light-volume")

    def _add_line_segments(
        self,
        points,
        color: tuple[float, float, float, float],
        *,
        thickness: float,
        name: str,
    ) -> int:
        if len(points) < 2:
            return 0
        usable = (len(points) // 2) * 2
        if usable < 2:
            return 0
        positions = np.asarray([self._vec3(point) for point in points[:usable]], dtype=np.float32)
        try:
            geometry = self.gfx.Geometry(positions=positions)
            material = self.gfx.LineSegmentMaterial(color=color, thickness=thickness, thickness_space="screen")
            line = self.gfx.Line(geometry, material, render_order=9000, name=name)
            self.scene.add(line)
            self._overlay_objects.append(line)
            return usable // 2
        except Exception:
            return 0

    def _add_points(
        self,
        points,
        color: tuple[float, float, float, float],
        *,
        size: float,
        name: str,
    ) -> None:
        if not points:
            return
        positions = np.asarray([self._vec3(point) for point in points], dtype=np.float32)
        try:
            geometry = self.gfx.Geometry(positions=positions)
            material = self.gfx.PointsMaterial(color=color, size=size, size_space="screen")
            obj = self.gfx.Points(geometry, material, render_order=9001, name=name)
            self.scene.add(obj)
            self._overlay_objects.append(obj)
        except Exception:
            pass

    @classmethod
    def _polyline_to_segments(cls, points) -> tuple[tuple[float, float, float], ...]:
        segment_points: list[tuple[float, float, float]] = []
        previous = cls._vec3(points[0])
        for point in points[1:]:
            current = cls._vec3(point)
            segment_points.extend((previous, current))
            previous = current
        return tuple(segment_points)

    @staticmethod
    def _vec3(value) -> tuple[float, float, float]:
        try:
            x, y, z = tuple(value)[:3]
            return (float(x), float(y), float(z))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _apply_world_matrix(self, mesh, matrix, record) -> None:
        try:
            arr = np.asarray(matrix, dtype=np.float32).reshape((4, 4))
        except Exception:
            return
        key = tuple(round(float(v), 6) for v in arr.reshape(-1))
        is_primary_mesh = mesh is getattr(record, "mesh", None)
        if is_primary_mesh and key == record.world_matrix_key:
            return
        if is_primary_mesh:
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
            "gizmo_overlay_segments": int(self.gizmo_overlay_segments),
            "skeleton_overlay_segments": int(self.skeleton_overlay_segments),
            "light_overlay_segments": int(self.light_overlay_segments),
            **self.mesh_cache.diagnostics(),
        }
