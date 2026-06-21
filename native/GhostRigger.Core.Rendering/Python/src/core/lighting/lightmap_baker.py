"""Core generated lightmap baking pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from src.core.lighting.lightmap_bake_job import (
    BakeResult,
    BakeableMesh,
    LightmapBakeJob,
    LightmapBakeResult,
    LightmapMeshBake,
    ordered_unique,
)
from src.core.lighting.lightmap_lighting_solver import LightmapLightingSolver
from src.core.lighting.lightmap_manifest import LightmapManifest
from src.core.lighting.lightmap_output import LightmapOutput
from src.core.lighting.lightmap_padding import LightmapPadding
from src.core.lighting.lightmap_rasterizer import LightmapRasterizer
from src.core.lighting.lightmap_shadow_solver import LightmapShadowSolver
from src.core.lighting.lightmap_uv_validator import LightmapUVValidator
from src.core.lighting.uv_atlas_generator import UVAtlasGenerator, UVAtlasResult

from src.core.lighting.aurora_light_adapter import AuroraLightAdapter
from src.core.lighting.preview_cache import LightmapPreviewCache


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
        uv_generator: UVAtlasGenerator | None = None,
        preview_cache: LightmapPreviewCache | None = None,
    ) -> None:
        self.uv_validator = uv_validator or LightmapUVValidator()
        self.rasterizer = rasterizer or LightmapRasterizer()
        self.lighting_solver = lighting_solver or LightmapLightingSolver()
        self.shadow_solver = shadow_solver or LightmapShadowSolver()
        self.padding = padding or LightmapPadding()
        self.output = output or LightmapOutput()
        self.manifest = manifest or LightmapManifest()
        self.uv_generator = uv_generator or UVAtlasGenerator()
        self.preview_cache = preview_cache or LightmapPreviewCache()
        self.aurora_adapter = AuroraLightAdapter()

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
        lights = self._bake_lights(job, settings, result)
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
            if entry.uv_channel == 0 and validation.warnings:
                validation.warnings.append(
                    "Primary UV fallback has validation warnings; output may be unsuitable for replacement lightmaps."
                )
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
                    lights,
                    settings,
                    self.shadow_solver if settings.use_shadows else None,
                )
                warning = str(getattr(self.lighting_solver, "last_warning", "") or "")
                if warning and warning not in result.warnings:
                    result.warnings.append(warning)
                message = str(getattr(self.lighting_solver, "last_info", "") or "")
                if message and message not in result.messages:
                    result.messages.append(message)
                self._progress(job, "Dilation/padding", index, total, entry.name)
                image = self.padding.pad_islands(buffer.baked_rgb, buffer.valid_mask, settings.padding_pixels)
                image = self.padding.dilate(image, buffer.valid_mask, settings.dilation_passes)
                self._progress(job, "Saving textures", index, total, entry.name)
                path = self._collision_safe_path(
                    self.output.build_output_path(module_name, entry.name, entry.material_name, settings),
                    settings.overwrite_existing,
                )
                self.output.save_image(image, path, settings.output_format)
                self.assign_lightmap_to_mesh(entry.node, str(path), entry.uv_channel)
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
                result.manifest_path = self.manifest.write(result, settings, lights, settings.output_directory or "exports/lightmaps")
            except Exception as exc:
                result.errors.append(f"Cannot write manifest: {exc}")
        self._progress(job, "Complete", 12, 12, "")
        return result

    def bake_preview(
        self,
        mesh: object,
        lights: list[object] | tuple[object, ...],
        settings,
        *,
        texture_cache: object | None = None,
        should_cancel=None,
    ) -> BakeResult:
        settings = settings.normalized()
        preview_settings = settings
        preview_settings.resolution = settings.preview_resolution
        preview_settings.bake_resolution = settings.preview_resolution
        key = self.preview_cache.make_key(mesh, preview_settings, list(lights))
        cached = self.preview_cache.get(key)
        if isinstance(cached, Image.Image):
            return BakeResult(True, preview_image=cached, messages=["Preview cache hit."])

        validation = self.uv_validator.validate_mesh_uvs(mesh, settings.selected_uv_channel)
        if validation.errors:
            return BakeResult(False, warnings=validation.warnings, errors=validation.errors)
        if should_cancel and should_cancel():
            return BakeResult(False, errors=["Bake cancelled by user."])
        try:
            buffer = self.rasterizer.rasterize_mesh(mesh, settings.selected_uv_channel, settings.preview_resolution)
            if not buffer.valid_mask.any():
                return BakeResult(False, warnings=validation.warnings, errors=["No valid texels were rasterized from UVs."])
            if settings.use_shadows:
                self.shadow_solver.build_acceleration_structure([mesh])
            buffer.baked_rgb = self.lighting_solver.solve_buffer(
                buffer,
                lights,
                preview_settings,
                self.shadow_solver if settings.use_shadows else None,
            )
            image = self.padding.pad_islands(buffer.baked_rgb, buffer.valid_mask, min(settings.padding_pixels, 4))
            pil = Image.fromarray((np.clip(image, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), "RGB")
            self.preview_cache.put(key, pil)
            return BakeResult(True, preview_image=pil, warnings=validation.warnings)
        except Exception as exc:
            return BakeResult(False, warnings=validation.warnings, errors=[str(exc)])

    def generate_lightmap_uvs(
        self,
        mesh: object,
        *,
        target_channel: int = 1,
        replace_existing: bool = False,
        settings=None,
    ) -> UVAtlasResult:
        settings = (settings or object())
        return self.uv_generator.generate_lightmap_uvs(
            mesh,
            target_channel=target_channel,
            resolution=int(getattr(settings, "resolution", getattr(settings, "bake_resolution", 1024)) or 1024),
            padding_pixels=int(getattr(settings, "padding_pixels", 8) or 8),
            replace_existing=replace_existing,
        )

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
            requested_channel = int(getattr(settings, "selected_uv_channel", 1))
            if not self.uv_validator._uvs(mesh, requested_channel):
                if result is not None:
                    result.warnings.append(
                        f"{getattr(mesh, 'name', 'mesh')}: Requested UV{requested_channel + 1} is missing; generate lightmap UVs or explicitly choose another channel."
                    )
                continue
            uv_channel = requested_channel
            warnings: list[str] = []
            if uv_channel < 0:
                if result is not None:
                    result.warnings.append(f"{getattr(mesh, 'name', 'mesh')}: Mesh has no UVs.")
                continue
            if uv_channel == 0 and not self.uv_validator.has_lightmap_uvs(mesh):
                warnings.append("Mesh has no separate lightmap UVs; using primary UVs.")
            bakeable.append(BakeableMesh(mesh, str(getattr(mesh, "name", "mesh") or "mesh"), self._material_name(mesh), uv_channel, warnings))
        return bakeable

    def assign_lightmap_to_mesh(self, mesh: object, lightmap_path: str, uv_channel: int) -> None:
        """Record generated assignment without mutating the original MDL lightmap field."""
        try:
            setattr(mesh, "_gr_baked_lightmap_path", str(lightmap_path))
            setattr(mesh, "_gr_baked_lightmap_uv_channel", int(uv_channel))
        except Exception:
            pass

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

    def _bake_lights(self, job: LightmapBakeJob, settings, result: LightmapBakeResult) -> list[object]:
        lights = list(job.lights or [])
        if settings.include_aurora_lights:
            existing = {id(light) for light in lights}
            existing_names = {str(getattr(light, "name", "") or "").lower() for light in lights}
            for light in self.aurora_adapter.from_model(job.model):
                name = str(getattr(light, "name", "") or "").lower()
                if id(light) not in existing and name not in existing_names:
                    lights.append(light)
        if not lights:
            result.warnings.append("No active lights were found; bake may be black unless ambient is enabled.")
        return [light for light in lights if bool(getattr(light, "affects_lightmap", True))]

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


__all__ = ("LightmapBaker",)
