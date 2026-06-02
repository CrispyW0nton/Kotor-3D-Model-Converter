"""Retained pygfx mesh cache keyed by renderer-neutral revisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PygfxMeshRecord:
    mesh_id: int
    source: Any
    geometry_key: tuple[Any, ...]
    material_key: tuple[Any, ...]
    mesh: Any
    geometry: Any
    material: Any
    base_color: tuple[float, float, float, float]
    source_revision: tuple[Any, ...]
    material_revision: tuple[Any, ...]
    world_matrix_key: tuple[float, ...] = ()
    selected: bool = False
    transform_dirty: bool = False
    geometry_dirty: bool = False
    material_dirty: bool = False


class PygfxMeshCache:
    """Owns retained gfx Geometry/Material/Mesh objects for mesh DTOs."""

    def __init__(self) -> None:
        self.records: dict[int, PygfxMeshRecord] = {}
        self.geometry_updates_this_frame = 0
        self.material_updates_this_frame = 0

    def begin_frame(self) -> None:
        self.geometry_updates_this_frame = 0
        self.material_updates_this_frame = 0

    def clear(self) -> None:
        self.records.clear()
        self.begin_frame()

    def remove_missing(self, live_mesh_ids: set[int], scene) -> None:
        for mesh_id in list(self.records):
            if mesh_id in live_mesh_ids:
                continue
            record = self.records.pop(mesh_id)
            try:
                scene.remove(record.mesh)
            except Exception:
                pass

    def get_or_create(self, mesh_data, gfx, scene, *, selected: bool = False) -> PygfxMeshRecord:
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
            material = self._build_material(mesh_data, gfx, selected=selected)
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
                base_color=self._base_color(mesh_data),
                source_revision=source_revision,
                material_revision=material_revision,
                selected=bool(selected),
            )
            self.records[mesh_id] = record
            return record

        record.source = getattr(mesh_data, "source", record.source)
        if record.geometry_dirty or record.geometry_key != geometry_key:
            record.geometry = self._build_geometry(mesh_data, gfx)
            record.mesh.geometry = record.geometry
            record.geometry_key = geometry_key
            record.source_revision = source_revision
            record.geometry_dirty = False
            self.geometry_updates_this_frame += 1
        if record.material_dirty or record.material_key != material_key:
            record.material = self._build_material(mesh_data, gfx, selected=selected)
            record.mesh.material = record.material
            record.material_key = material_key
            record.material_revision = material_revision
            record.base_color = self._base_color(mesh_data)
            record.selected = bool(selected)
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
            source = record.source
            visible = not bool(getattr(source, "_gr_hidden", False)) and getattr(source, "render", True) is not False
            try:
                record.mesh.visible = bool(visible)
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

    def _base_color(self, mesh_data) -> tuple[float, float, float, float]:
        base = tuple(float(c) for c in (mesh_data.material_color or (0.72, 0.74, 0.76, 1.0))[:4])
        if len(base) < 4:
            base = (*base[:3], 1.0)
        return base

    def _build_material(self, mesh_data, gfx, *, selected: bool = False):
        base = self._base_color(mesh_data)
        color = self._selection_color(base) if selected else base
        material = gfx.MeshPhongMaterial(color=color)
        try:
            material.side = "FRONT_AND_BACK" if bool(getattr(mesh_data.material, "double_sided", False)) else "FRONT"
        except Exception:
            pass
        return material

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
        try:
            record.material.color = color
        except Exception:
            record.material = record.material.__class__(color=color)
            record.mesh.material = record.material
        self.material_updates_this_frame += 1

    def diagnostics(self) -> dict[str, int]:
        return {
            "mesh_cache_size": len(self.records),
            "geometry_updates_this_frame": int(self.geometry_updates_this_frame),
            "material_updates_this_frame": int(self.material_updates_this_frame),
            "transform_dirty_count": sum(1 for record in self.records.values() if record.transform_dirty),
        }
