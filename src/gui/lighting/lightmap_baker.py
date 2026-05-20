"""Core generated lightmap baking pipeline."""

from __future__ import annotations

from pathlib import Path

from .lightmap_bake_job import BakeableMesh, LightmapBakeJob, LightmapBakeResult, LightmapMeshBake, ordered_unique
from .lightmap_lighting_solver import LightmapLightingSolver
from .lightmap_manifest import LightmapManifest
from .lightmap_output import LightmapOutput
from .lightmap_padding import LightmapPadding
from .lightmap_rasterizer import LightmapRasterizer
from .lightmap_shadow_solver import LightmapShadowSolver
from .lightmap_uv_validator import LightmapUVValidator


class LightmapBaker:
    def __init__(
        self,
        uv_validator: LightmapUVValidator | None = None,
        rasterizer: LightmapRasterizer | None = None,
        lighting_solver: LightmapLightingSolver | None = None,
        shadow_solver: LightmapShadowSolver | None = None,
        padding: LightmapPadding | None = None,
        output: LightmapOutput | None = None,
        manifest: LightmapManifest | None = None,
    ) -> None:
        self.uv_validator = uv_validator or LightmapUVValidator()
        self.rasterizer = rasterizer or LightmapRasterizer()
        self.lighting_solver = lighting_solver or LightmapLightingSolver()
        self.shadow_solver = shadow_solver or LightmapShadowSolver()
        self.padding = padding or LightmapPadding()
        self.output = output or LightmapOutput()
        self.manifest = manifest or LightmapManifest()

    def bake(self, job: LightmapBakeJob) -> LightmapBakeResult:
        settings = job.settings.normalized()
        module_name = job.module_name or self._module_name(job.model)
        result = LightmapBakeResult(module_name, settings.resolution, settings.output_format)
        result.warnings.extend(settings.warnings)
        if settings.output_format in {"jpg", "jpeg"}:
            result.warnings.append("JPG is lossy and may introduce lightmap filtering artifacts.")
        if settings.resolution >= 2048:
            result.warnings.append("2048 lightmap bakes may be slow on large module meshes.")

        try:
            self.output.ensure_output_directory(settings.output_directory or "exports/lightmaps")
        except Exception as exc:
            result.errors.append(f"Cannot create output directory: {exc}")
            return result

        bakeable = self.collect_bakeable_meshes(job, result)
        if not bakeable:
            result.errors.append("No bakeable meshes found.")
            return result
        self._progress(job, "Building shadow acceleration", 1, 12, "")
        if settings.use_shadows:
            self.shadow_solver.build_acceleration_structure([mesh.node for mesh in bakeable])

        total = len(bakeable)
        for index, entry in enumerate(bakeable, start=1):
            if job.cancelled():
                result.cancelled = True
                result.errors.append("Bake cancelled.")
                break
            self._progress(job, "Rasterizing UVs", index, total, entry.name)
            validation = self.uv_validator.validate_mesh_uvs(entry.node, entry.uv_channel)
            if validation.errors:
                result.bakes.append(LightmapMeshBake(entry.name, entry.material_name, entry.uv_channel, "", warnings=validation.warnings, errors=validation.errors))
                continue
            try:
                buffer = self.rasterizer.rasterize_mesh(entry.node, entry.uv_channel, settings.resolution)
                if not buffer.valid_mask.any():
                    raise RuntimeError("No valid texels were rasterized from UVs.")
                self._progress(job, "Baking direct lighting", index, total, entry.name)
                buffer.baked_rgb = self.lighting_solver.solve_buffer(
                    buffer,
                    job.lights,
                    settings,
                    self.shadow_solver if settings.use_shadows else None,
                )
                self._progress(job, "Dilation/padding", index, total, entry.name)
                image = self.padding.pad_islands(buffer.baked_rgb, buffer.valid_mask, settings.padding_pixels)
                image = self.padding.dilate(image, buffer.valid_mask, settings.dilation_passes)
                self._progress(job, "Saving textures", index, total, entry.name)
                path = self._collision_safe_path(
                    self.output.build_output_path(module_name, entry.name, entry.material_name, settings),
                    settings.overwrite_existing,
                )
                self.output.save_image(image, path, settings.output_format)
                result.bakes.append(
                    LightmapMeshBake(
                        mesh_name=entry.name,
                        material_name=entry.material_name,
                        uv_channel=entry.uv_channel,
                        output_path=str(path),
                        preview_name=Path(path).stem.lower(),
                        warnings=[*entry.warnings, *validation.warnings],
                    )
                )
            except Exception as exc:
                result.bakes.append(LightmapMeshBake(entry.name, entry.material_name, entry.uv_channel, "", errors=[str(exc)]))
        if settings.generate_manifest and not result.cancelled:
            self._progress(job, "Writing manifest", 11, 12, "")
            try:
                result.manifest_path = self.manifest.write(result, settings, job.lights, settings.output_directory or "exports/lightmaps")
            except Exception as exc:
                result.errors.append(f"Cannot write manifest: {exc}")
        self._progress(job, "Complete", 12, 12, "")
        return result

    def collect_bakeable_meshes(self, job: LightmapBakeJob, result: LightmapBakeResult | None = None) -> list[BakeableMesh]:
        settings = job.settings.normalized()
        if settings.bake_selected_only and job.selected_meshes:
            candidates = ordered_unique(job.selected_meshes)
        elif settings.bake_visible_only and job.visible_meshes:
            candidates = ordered_unique(job.visible_meshes)
        else:
            candidates = self._all_meshes(job.model)
            if settings.bake_visible_only:
                candidates = [mesh for mesh in candidates if not bool(getattr(mesh, "_gr_hidden", False))]

        bakeable: list[BakeableMesh] = []
        for mesh in candidates:
            if not self._is_mesh(mesh):
                continue
            uv_channel = self.uv_validator.find_best_uv_channel(mesh)
            warnings: list[str] = []
            if uv_channel < 0:
                if result is not None:
                    result.warnings.append(f"{getattr(mesh, 'name', 'mesh')}: Mesh has no UVs.")
                continue
            if uv_channel == 0 and not self.uv_validator.has_lightmap_uvs(mesh):
                warnings.append("Mesh has no separate lightmap UVs; using primary UVs.")
            bakeable.append(BakeableMesh(mesh, str(getattr(mesh, "name", "mesh") or "mesh"), self._material_name(mesh), uv_channel, warnings))
        return bakeable

    def _all_meshes(self, model: object | None) -> list[object]:
        if model is None:
            return []
        try:
            return [node for node in model.all_nodes() if self._is_mesh(node)]
        except Exception:
            return [node for node in getattr(model, "nodes", []) if self._is_mesh(node)]

    def _is_mesh(self, node: object) -> bool:
        return bool(getattr(node, "is_mesh", False) or getattr(node, "is_skin", False) or getattr(node, "faces", None))

    def _material_name(self, mesh: object) -> str:
        for attr in ("texture_clean", "texture"):
            value = getattr(mesh, attr, "")
            if value and str(value).upper() not in {"NULL", "NONE"}:
                return str(value)
        return ""

    def _module_name(self, model: object | None) -> str:
        raw = str(getattr(model, "name", "") or Path(str(getattr(model, "mdl_path", "") or "module")).stem)
        return self.output.sanitize_filename(raw or "module").lower()

    def _collision_safe_path(self, path: Path, overwrite: bool) -> Path:
        if overwrite or not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        index = 2
        while True:
            candidate = parent / f"{stem}_{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _progress(self, job: LightmapBakeJob, stage: str, value: int, total: int, detail: str) -> None:
        if job.progress is not None:
            job.progress(stage, value, total, detail)
