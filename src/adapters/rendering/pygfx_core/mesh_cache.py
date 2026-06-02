"""Retained pygfx mesh cache keyed by renderer-neutral revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class PygfxMeshRecord:
    mesh_id: int
    source: Any
    geometry_key: tuple[Any, ...]
    material_key: tuple[Any, ...]
    mesh: Any
    geometry: Any
    material: Any
    gfx: Any
    scene: Any
    base_color: tuple[float, float, float, float]
    source_revision: tuple[Any, ...]
    material_revision: tuple[Any, ...]
    diffuse_map: Any = None
    edge_mesh: Any = None
    edge_material: Any = None
    world_matrix_key: tuple[float, ...] = ()
    view_style_key: tuple[Any, ...] = ()
    selected: bool = False
    transform_dirty: bool = False
    geometry_dirty: bool = False
    material_dirty: bool = False


class PygfxMeshCache:
    """Owns retained gfx Geometry/Material/Mesh objects for mesh DTOs."""

    def __init__(self) -> None:
        self.records: dict[int, PygfxMeshRecord] = {}
        self.texture_maps: dict[tuple[Any, ...], Any] = {}
        self.geometry_updates_this_frame = 0
        self.dynamic_geometry_updates_this_frame = 0
        self.material_updates_this_frame = 0

    def begin_frame(self) -> None:
        self.geometry_updates_this_frame = 0
        self.dynamic_geometry_updates_this_frame = 0
        self.material_updates_this_frame = 0

    def clear(self) -> None:
        self.records.clear()
        self.texture_maps.clear()
        self.begin_frame()

    @staticmethod
    def _view_style_key(
        *,
        show_solid: bool = True,
        show_wireframe: bool = False,
        show_texture: bool = True,
        render_mode: str = "realistic",
        xray: bool = False,
    ) -> tuple[Any, ...]:
        return (
            bool(show_solid),
            bool(show_wireframe),
            bool(show_texture),
            str(render_mode or "realistic").strip().lower(),
            bool(xray),
        )

    def apply_view_style(
        self,
        *,
        show_solid: bool = True,
        show_wireframe: bool = False,
        show_texture: bool = True,
        render_mode: str = "realistic",
        xray: bool = False,
    ) -> None:
        style_key = self._view_style_key(
            show_solid=show_solid,
            show_wireframe=show_wireframe,
            show_texture=show_texture,
            render_mode=render_mode,
            xray=xray,
        )
        for record in self.records.values():
            if record.view_style_key == style_key:
                continue
            record.view_style_key = style_key
            self._apply_material_style(record, style_key)
            self.material_updates_this_frame += 1

    def remove_missing(self, live_mesh_ids: set[int], scene) -> None:
        for mesh_id in list(self.records):
            if mesh_id in live_mesh_ids:
                continue
            record = self.records.pop(mesh_id)
            try:
                scene.remove(record.mesh)
            except Exception:
                pass
            if record.edge_mesh is not None:
                try:
                    scene.remove(record.edge_mesh)
                except Exception:
                    pass

    def get_or_create(self, mesh_data, gfx, scene, *, selected: bool = False, force_geometry_update: bool = False) -> PygfxMeshRecord:
        mesh_id = int(mesh_data.mesh_id)
        source_revision = tuple(mesh_data.source_revision or ())
        material_revision = tuple(getattr(mesh_data.material, "source_revision", ()) or ())
        geometry_key = (mesh_id, source_revision)
        material_key = (
            getattr(mesh_data.material, "material_id", ""),
            material_revision,
            bool(selected),
        )
        record = self.records.get(mesh_id)
        if record is None:
            geometry = self._build_geometry(mesh_data, gfx)
            diffuse_map = self._texture_map(mesh_data, gfx)
            material = self._build_material(mesh_data, gfx, selected=selected, diffuse_map=diffuse_map)
            mesh = gfx.Mesh(geometry, material)
            try:
                mesh.name = str(getattr(mesh_data.source, "name", "") or mesh_id)
            except Exception:
                pass
            scene.add(mesh)
            self.geometry_updates_this_frame += 1
            self.material_updates_this_frame += 1
            record = PygfxMeshRecord(
                mesh_id=mesh_id,
                source=getattr(mesh_data, "source", None),
                geometry_key=geometry_key,
                material_key=material_key,
                mesh=mesh,
                geometry=geometry,
                material=material,
                gfx=gfx,
                scene=scene,
                base_color=self._base_color(mesh_data),
                source_revision=source_revision,
                material_revision=material_revision,
                diffuse_map=diffuse_map,
                selected=bool(selected),
            )
            self.records[mesh_id] = record
            return record

        record.source = getattr(mesh_data, "source", record.source)
        if force_geometry_update and record.geometry_key == geometry_key:
            if not self._update_geometry_buffers(record, mesh_data):
                record.geometry_dirty = True
        if record.geometry_dirty or record.geometry_key != geometry_key:
            updated_in_place = self._update_geometry_buffers(record, mesh_data)
            if not updated_in_place:
                record.geometry = self._build_geometry(mesh_data, gfx)
                record.mesh.geometry = record.geometry
                if record.edge_mesh is not None:
                    record.edge_mesh.geometry = record.geometry
                self.geometry_updates_this_frame += 1
            record.geometry_key = geometry_key
            record.source_revision = source_revision
            record.geometry_dirty = False
        if record.material_dirty or record.material_key != material_key:
            record.diffuse_map = self._texture_map(mesh_data, gfx)
            record.material = self._build_material(mesh_data, gfx, selected=selected, diffuse_map=record.diffuse_map)
            record.mesh.material = record.material
            record.material_key = material_key
            record.material_revision = material_revision
            record.base_color = self._base_color(mesh_data)
            record.selected = bool(selected)
            record.view_style_key = ()
            record.material_dirty = False
            self.material_updates_this_frame += 1
        elif record.selected != bool(selected):
            self._apply_selection_state(record, bool(selected))
        return record

    def mark_transform_dirty(self, node=None) -> None:
        source_id = id(node) if node is not None else None
        for record in self.records.values():
            if source_id is None or id(record.source) == source_id:
                record.transform_dirty = True
                record.world_matrix_key = ()

    def mark_geometry_dirty(self, node) -> None:
        record = self.records.get(id(node))
        if record is not None:
            record.geometry_dirty = True
            record.transform_dirty = True

    def update_selection(self, gfx, selected_source_ids: set[int]) -> None:
        for record in self.records.values():
            selected = id(record.source) in selected_source_ids
            if record.selected != selected:
                self._apply_selection_state(record, selected)

    def update_visibility(self) -> None:
        for record in self.records.values():
            visible = self._source_visible(record.source)
            try:
                record.mesh.visible = bool(visible)
            except Exception:
                pass
            if record.edge_mesh is not None:
                try:
                    record.edge_mesh.visible = bool(visible and record.view_style_key and record.view_style_key[1])
                except Exception:
                    pass

    def _build_geometry(self, mesh_data, gfx):
        kwargs = {"positions": mesh_data.positions}
        if mesh_data.indices is not None:
            kwargs["indices"] = mesh_data.indices.reshape((-1, 3))
        if mesh_data.normals is not None:
            kwargs["normals"] = mesh_data.normals
        if mesh_data.uvs0 is not None:
            kwargs["texcoords"] = mesh_data.uvs0
        return gfx.Geometry(**kwargs)

    def _update_geometry_buffers(self, record: PygfxMeshRecord, mesh_data) -> bool:
        geometry = record.geometry
        checks = (
            ("positions", getattr(mesh_data, "positions", None)),
            ("normals", getattr(mesh_data, "normals", None)),
            ("texcoords", getattr(mesh_data, "uvs0", None)),
        )
        for attr, values in checks:
            if values is None:
                continue
            buffer = getattr(geometry, attr, None)
            data = getattr(buffer, "data", None)
            if data is None:
                return False
            arr = np.asarray(values, dtype=np.asarray(data).dtype)
            if tuple(arr.shape) != tuple(np.asarray(data).shape):
                return False
        index_values = getattr(mesh_data, "indices", None)
        index_buffer = getattr(geometry, "indices", None)
        if index_values is not None and index_buffer is not None and getattr(index_buffer, "data", None) is not None:
            arr = np.asarray(index_values, dtype=np.asarray(index_buffer.data).dtype).reshape(np.asarray(index_buffer.data).shape)
            if tuple(arr.shape) != tuple(np.asarray(index_buffer.data).shape):
                return False
        try:
            for attr, values in checks:
                if values is None:
                    continue
                buffer = getattr(geometry, attr, None)
                data = getattr(buffer, "data", None)
                if data is None:
                    continue
                arr = np.asarray(values, dtype=np.asarray(data).dtype).reshape(np.asarray(data).shape)
                data[...] = arr
                update_range = getattr(buffer, "update_range", None)
                if callable(update_range):
                    update_range(0, len(data))
            if index_values is not None and index_buffer is not None and getattr(index_buffer, "data", None) is not None:
                data = index_buffer.data
                arr = np.asarray(index_values, dtype=np.asarray(data).dtype).reshape(np.asarray(data).shape)
                data[...] = arr
                update_range = getattr(index_buffer, "update_range", None)
                if callable(update_range):
                    update_range(0, len(data))
            self.dynamic_geometry_updates_this_frame += 1
            return True
        except Exception:
            return False

    def _base_color(self, mesh_data) -> tuple[float, float, float, float]:
        base = tuple(float(c) for c in (mesh_data.material_color or (0.72, 0.74, 0.76, 1.0))[:4])
        if len(base) < 4:
            base = (*base[:3], 1.0)
        return base

    def _build_material(self, mesh_data, gfx, *, selected: bool = False, diffuse_map=None):
        base = self._base_color(mesh_data)
        color = self._selection_color(base) if selected else base
        material = gfx.MeshPhongMaterial(color=color)
        if diffuse_map is not None:
            self._set_material_attr(material, "map", diffuse_map)
        try:
            material.side = "FRONT_AND_BACK" if bool(getattr(mesh_data.material, "double_sided", False)) else "FRONT"
        except Exception:
            pass
        return material

    def _texture_map(self, mesh_data, gfx):
        texture_data = getattr(getattr(mesh_data, "material", None), "diffuse_texture_data", None)
        source = getattr(texture_data, "source", None)
        if source is None:
            return None
        texture_id = str(getattr(texture_data, "texture_id", "") or getattr(texture_data, "name", "") or id(source))
        revision = tuple(getattr(texture_data, "source_revision", ()) or ())
        key = (texture_id, revision)
        cached = self.texture_maps.get(key)
        if cached is not None:
            return cached
        try:
            image = source.convert("RGBA") if hasattr(source, "convert") else source
            pixels = np.asarray(image, dtype=np.uint8)
            if pixels.ndim != 3 or pixels.shape[2] < 4:
                return None
            pixels = np.ascontiguousarray(pixels[:, :, :4])
            texture = gfx.Texture(pixels, dim=2, colorspace="srgb", generate_mipmaps=True)
            texture_map = gfx.TextureMap(texture, uv_channel=0, wrap="repeat", filter="linear")
            self.texture_maps[key] = texture_map
            return texture_map
        except Exception:
            return None

    @staticmethod
    def _selection_color(base: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        return (
            min(1.0, base[0] * 0.6 + 0.35),
            min(1.0, base[1] * 0.6 + 0.32),
            min(1.0, base[2] * 0.6 + 0.08),
            base[3],
        )

    def _apply_selection_state(self, record: PygfxMeshRecord, selected: bool) -> None:
        record.selected = bool(selected)
        color = self._selection_color(record.base_color) if selected else record.base_color
        record.view_style_key = record.view_style_key or self._view_style_key()
        self._set_material_color(record.material, color)
        self._apply_material_style(record, record.view_style_key)
        self.material_updates_this_frame += 1

    def _apply_material_style(self, record: PygfxMeshRecord, style_key: tuple[Any, ...]) -> None:
        show_solid, show_wireframe, show_texture, render_mode, xray = style_key
        render_mode = str(render_mode or "realistic").strip().lower()
        self._ensure_material_class(record, render_mode)
        color = self._selection_color(record.base_color) if record.selected else record.base_color
        map_enabled = bool(show_texture) and render_mode == "realistic"
        if not map_enabled:
            luminance = max(0.18, min(0.82, color[0] * 0.3 + color[1] * 0.45 + color[2] * 0.25))
            color = (luminance, luminance, luminance, color[3])
        if render_mode == "flat":
            color = (min(1.0, color[0] * 1.08), min(1.0, color[1] * 1.08), min(1.0, color[2] * 1.08), color[3])
        elif render_mode == "shaded":
            color = (color[0] * 0.78, color[1] * 0.78, color[2] * 0.78, color[3])
        if bool(xray):
            color = (color[0], color[1], color[2], min(color[3], 0.38))
        self._set_material_color(record.material, color)
        self._set_material_attr(record.material, "opacity", color[3])
        self._set_material_attr(record.material, "map", record.diffuse_map if map_enabled else None)
        self._set_material_attr(record.material, "wireframe", bool(show_wireframe) and not bool(show_solid))
        self._set_material_attr(record.material, "flat_shading", render_mode in {"flat", "shaded"})
        self._set_material_attr(record.mesh, "visible", self._source_visible(record.source) and (bool(show_solid) or bool(show_wireframe)))
        if bool(show_solid):
            self._set_material_attr(record.mesh, "visible", self._source_visible(record.source))
        else:
            self._set_material_attr(record.mesh, "visible", False)
        self._set_edge_overlay_visible(record, bool(show_wireframe), color)

    def _ensure_material_class(self, record: PygfxMeshRecord, render_mode: str) -> None:
        target_name = "MeshBasicMaterial" if render_mode == "flat" else "MeshPhongMaterial"
        if type(record.material).__name__ == target_name:
            return
        cls = getattr(record.gfx, target_name, None)
        if cls is None:
            return
        try:
            record.material = cls(color=record.base_color)
            record.mesh.material = record.material
            self.material_updates_this_frame += 1
        except Exception:
            pass

    def _set_edge_overlay_visible(self, record: PygfxMeshRecord, visible: bool, color) -> None:
        if not visible:
            if record.edge_mesh is not None:
                self._set_material_attr(record.edge_mesh, "visible", False)
            return
        if record.edge_mesh is None:
            try:
                material = record.gfx.MeshBasicMaterial(color=(0.0, 0.84, 0.72, 1.0), wireframe=True)
                edge_mesh = record.gfx.Mesh(record.geometry, material)
                edge_mesh.name = f"{getattr(record.mesh, 'name', record.mesh_id)}-wire"
                record.scene.add(edge_mesh)
                record.edge_mesh = edge_mesh
                record.edge_material = material
            except Exception:
                return
        self._set_material_color(record.edge_material, (0.0, 0.84, 0.72, 1.0))
        self._set_material_attr(record.edge_material, "wireframe", True)
        self._set_material_attr(record.edge_mesh, "visible", self._source_visible(record.source))

    @staticmethod
    def _source_visible(source) -> bool:
        return not bool(getattr(source, "_gr_hidden", False)) and getattr(source, "render", True) is not False

    @staticmethod
    def _set_material_color(material, color: tuple[float, float, float, float]) -> None:
        try:
            material.color = color
        except Exception:
            pass

    @staticmethod
    def _set_material_attr(target, name: str, value) -> None:
        try:
            if hasattr(target, name):
                setattr(target, name, value)
        except Exception:
            pass

    def diagnostics(self) -> dict[str, int]:
        return {
            "mesh_cache_size": len(self.records),
            "texture_cache_size": len(self.texture_maps),
            "geometry_updates_this_frame": int(self.geometry_updates_this_frame),
            "dynamic_geometry_updates_this_frame": int(self.dynamic_geometry_updates_this_frame),
            "material_updates_this_frame": int(self.material_updates_this_frame),
            "transform_dirty_count": sum(1 for record in self.records.values() if record.transform_dirty),
        }
