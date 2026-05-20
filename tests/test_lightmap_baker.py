from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from src.core.model_data import KotorModel, ModelNode, NodeFlags
from src.gui.lighting.lightmap_bake_job import LightmapBakeJob
from src.gui.lighting.lightmap_bake_settings import LightmapBakeSettings
from src.gui.lighting.lightmap_baker import LightmapBaker
from src.gui.lighting.lightmap_export_bridge import (
    export_baked_lightmap_manifest,
    get_baked_lightmap_assignments,
    resolve_lightmap_for_material,
)
from src.gui.lighting.lightmap_gpu_solver import LightmapGpuSolver
from src.gui.lighting.lightmap_lighting_solver import LightmapLightingSolver
from src.gui.lighting.lightmap_rasterizer import LightmapRasterizer
from src.gui.lighting.lightmap_padding import LightmapPadding
from src.gui.lighting.lightmap_uv_validator import LightmapUVValidator


def _model_with_lightmapped_triangle() -> tuple[KotorModel, ModelNode]:
    model = KotorModel(name="danm13aa")
    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    mesh = ModelNode(
        name="floor01",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="stone_floor",
        lightmap="old_floor_lm",
        has_lightmap=True,
        diffuse=(1.0, 1.0, 1.0),
    )
    root.children.append(mesh)
    model.root_node = root
    return model, mesh


def test_lightmap_settings_validation_is_non_throwing() -> None:
    settings = LightmapBakeSettings(
        resolution=999,
        output_format="bmp",
        samples_per_texel=0,
        shadow_samples=0,
        padding_pixels=-4,
        exposure=-1.0,
        gamma=0.0,
    ).normalized()

    assert settings.resolution == 1024
    assert settings.output_format == "png"
    assert settings.samples_per_texel == 1
    assert settings.shadow_samples == 1
    assert settings.padding_pixels == 0
    assert settings.exposure == 1.0
    assert settings.gamma == 2.2
    assert settings.warnings


def test_lightmap_bake_defaults_do_not_add_synthetic_ambient() -> None:
    settings = LightmapBakeSettings()

    assert settings.include_ambient is False
    assert settings.use_gpu_acceleration is True
    assert settings.use_shadows is False


def test_gpu_solver_bypasses_to_cpu_when_shadows_are_enabled() -> None:
    solver = LightmapGpuSolver()
    settings = LightmapBakeSettings(use_shadows=True)

    assert solver.can_use_gpu(settings, shadow_solver=object()) is False
    assert "shadow rays" in solver.last_warning


def test_uv_validator_prefers_lightmap_uvs_and_warns_for_primary_fallback() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    validator = LightmapUVValidator()

    assert validator.has_lightmap_uvs(mesh)
    assert validator.find_best_uv_channel(mesh) == 1
    mesh.uvs_lm = []
    assert validator.find_best_uv_channel(mesh) == 0
    result = validator.validate_mesh_uvs(mesh, 0)
    assert result.usable
    assert result.severity == "ok"


def test_uv_validation_result_reports_warning_severity_for_risky_bakeable_uvs() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    mesh.uvs_lm = []
    mesh.uvs = [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)]

    result = LightmapUVValidator().validate_mesh_uvs(mesh, 0)

    assert result.usable
    assert result.severity == "warning"
    assert any("outside the 0-1 range" in message for message in result.warnings)


def test_padding_dilates_from_valid_texels() -> None:
    image = np.zeros((4, 4, 3), dtype=np.float32)
    image[1, 1] = (1.0, 0.5, 0.25)
    mask = np.zeros((4, 4), dtype=bool)
    mask[1, 1] = True

    padded = LightmapPadding().dilate(image, mask, 1)

    assert np.allclose(padded[1, 2], (1.0, 0.5, 0.25))
    assert np.allclose(padded[2, 2], (1.0, 0.5, 0.25))


def test_lightmap_baker_writes_png_manifest_and_keeps_original_lightmap(tmp_path: Path) -> None:
    model, mesh = _model_with_lightmapped_triangle()
    light = SimpleNamespace(
        name="AuroraLight001",
        source_type="Aurora",
        enabled=True,
        visible=True,
        type="aurora_point",
        position=(0.25, 0.25, 2.0),
        color=(1.0, 1.0, 1.0),
        intensity=3.0,
        radius=10.0,
        casts_shadows=False,
        affects_lightmap=True,
    )
    settings = LightmapBakeSettings(
        resolution=256,
        output_format="png",
        output_directory=str(tmp_path),
        bake_visible_only=False,
        use_shadows=False,
        padding_pixels=2,
        dilation_passes=2,
    )

    result = LightmapBaker().bake(LightmapBakeJob(model=model, lights=[light], settings=settings))

    assert result.ok
    assert mesh.lightmap == "old_floor_lm"
    assert result.bakes[0].uv_channel == 1
    assert Path(result.bakes[0].output_path).is_file()
    assert Path(result.manifest_path).is_file()
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["module"] == "danm13aa"
    assert manifest["bakes"][0]["mesh"] == "floor01"


def test_lighting_solver_tone_maps_aurora_light_clusters_instead_of_clipping_white() -> None:
    solver = LightmapLightingSolver()
    settings = LightmapBakeSettings(include_diffuse=False, use_shadows=False)
    texel = {
        "position": np.asarray((0.0, 0.0, 0.0), dtype=np.float32),
        "normal": np.asarray((0.0, 0.0, 1.0), dtype=np.float32),
        "diffuse": np.ones(3, dtype=np.float32),
        "mesh_id": 1,
    }
    lights = [
        SimpleNamespace(
            name=f"AuroraLight{idx}",
            source_type="Aurora",
            enabled=True,
            visible=True,
            type="aurora_point",
            position=(0.1 * idx, 0.0, 1.0),
            color=(1.0, 0.95, 0.8),
            intensity=3.5,
            radius=4.5,
            casts_shadows=False,
        )
        for idx in range(8)
    ]

    rgb = solver.solve_texel_lighting(texel, lights, settings)

    assert float(rgb.max()) < 0.98
    assert float(rgb.min()) > 0.0
    assert not np.allclose(rgb, np.ones(3), atol=0.02)


def test_lighting_solver_vectorized_buffer_matches_scalar_path() -> None:
    model, mesh = _model_with_lightmapped_triangle()
    buffer = LightmapRasterizer().rasterize_mesh(mesh, 1, 16)
    lights = [
        SimpleNamespace(
            name="AuroraLight001",
            source_type="Aurora",
            enabled=True,
            visible=True,
            type="aurora_point",
            position=(0.2, 0.2, 1.5),
            color=(1.0, 0.9, 0.7),
            intensity=2.0,
            radius=4.0,
            casts_shadows=False,
        ),
        SimpleNamespace(
            name="Fill",
            source_type="Editable",
            enabled=True,
            visible=True,
            type="directional",
            direction=(0.0, 0.0, -1.0),
            color=(0.4, 0.5, 1.0),
            intensity=0.35,
            casts_shadows=False,
        ),
    ]
    settings = LightmapBakeSettings(include_ambient=False, use_shadows=False)
    solver = LightmapLightingSolver()

    vector = solver.solve_buffer(buffer, lights, settings)
    scalar = solver._solve_buffer_scalar(buffer, lights, settings)

    assert np.allclose(vector, scalar, atol=1.0e-5)


def test_lightmap_export_bridge_discovers_generated_assignments(tmp_path: Path) -> None:
    model, mesh = _model_with_lightmapped_triangle()
    generated = tmp_path / "danm13aa_floor01_LM_256.png"
    generated.write_bytes(b"not-an-image-for-metadata-only")
    setattr(mesh, "_gr_baked_lightmap_path", str(generated))

    assignments = get_baked_lightmap_assignments(model)
    manifest = export_baked_lightmap_manifest(model, tmp_path)

    assert assignments == {"floor01": str(generated)}
    assert resolve_lightmap_for_material(mesh, "stone_floor") == str(generated)
    assert Path(manifest).is_file()
