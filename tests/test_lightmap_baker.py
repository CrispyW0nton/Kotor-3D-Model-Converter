from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from src.adapters.gpu.lightmap_baker import LightmapBaker
from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver
from src.core.lighting.lightmap_bake_job import LightmapBakeJob
from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings
from src.core.lighting.lightmap_export_bridge import (
    export_baked_lightmap_manifest,
    get_baked_lightmap_assignments,
    resolve_lightmap_for_material,
)
from src.core.lighting.lightmap_lighting_solver import LightmapLightingSolver
from src.core.lighting.lightmap_padding import LightmapPadding
from src.core.lighting.lightmap_rasterizer import LightmapRasterizer
from src.core.lighting.lightmap_shadow_solver import LightmapShadowSolver
from src.core.lighting.lightmap_uv_validator import LightmapUVValidator
from src.core.lighting.uv_atlas_generator import UVAtlasGenerator
from src.core.geometry.model_data import BoneWeight, KotorModel, ModelNode, NodeFlags, VertexSkinData


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


def test_uv_channel_info_uses_artist_facing_names_and_zero_indexed_data() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    mesh.uvs_lm = []

    infos = LightmapUVValidator().inspect_mesh_uv_channels(mesh, 3)

    assert infos[0].display_name == "UV1"
    assert infos[0].channel_index == 0
    assert infos[0].has_uvs
    assert infos[1].display_name == "UV2"
    assert infos[1].channel_index == 1
    assert not infos[1].has_uvs


def test_xatlas_generator_preserves_uv1_and_creates_uv2_faces() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    original_uv1 = list(mesh.uvs)
    mesh.uvs_lm = []

    result = UVAtlasGenerator().generate_lightmap_uvs(mesh, target_channel=1, replace_existing=False)

    assert result.success
    assert mesh.uvs == original_uv1
    assert getattr(mesh, "uvs_lm")
    assert getattr(mesh, "face_uvs_lm")
    assert result.vertex_mapping == getattr(mesh, "_gr_generated_lightmap_vertex_mapping")
    assert result.atlas_faces == getattr(mesh, "_gr_generated_lightmap_faces")
    assert [
        tuple(result.vertex_mapping[index] for index in atlas_face)
        for atlas_face in result.atlas_faces
    ] == mesh.faces
    assert all(0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0 for uv in mesh.uvs_lm)


def test_lightmap_vertex_stream_remap_preserves_all_mesh_streams_across_uv_seam() -> None:
    mesh = ModelNode(
        name="seamed_floor",
        flags=int(NodeFlags.HEADER | NodeFlags.SKIN | NodeFlags.MESH),
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        normals=[(0.0, 0.0, 1.0)] * 4,
        tangents=[(1.0, 0.0, 0.0)] * 4,
        uvs=[
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
            (0.25, 0.25),
        ],
        uvs_lm=[
            (0.05, 0.05),
            (0.45, 0.05),
            (0.45, 0.45),
            (0.55, 0.55),
            (0.95, 0.95),
            (0.55, 0.95),
        ],
        uvs_2=[(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)],
        faces=[(0, 1, 2), (0, 2, 3)],
        face_mats=[2, 4],
        face_uvs=[(0, 1, 2), (4, 2, 3)],
        skin_data=[
            VertexSkinData([BoneWeight(index, 1.0)])
            for index in range(4)
        ],
    )
    mesh.face_uvs_lm = [(0, 1, 2), (3, 4, 5)]
    mesh._gr_generated_lightmap_uv_channel = 1
    mesh._gr_generated_lightmap_vertex_mapping = [0, 1, 2, 0, 2, 3]
    mesh._gr_generated_lightmap_faces = [(0, 1, 2), (3, 4, 5)]
    mesh._gr_generated_lightmap_source_vertex_count = 4

    result = UVAtlasGenerator().remap_vertex_stream_for_lightmap(mesh, target_channel=1)

    assert result.success
    assert result.changed
    assert result.source_vertex_count == 4
    assert result.vertex_count == 6
    assert result.duplicated_vertex_count == 2
    assert mesh.faces == [(0, 1, 2), (3, 4, 5)]
    assert mesh.vertices == [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    assert len(mesh.normals) == len(mesh.tangents) == len(mesh.vertices)
    assert mesh.uvs == [
        (0.0, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.25, 0.25),
        (1.0, 1.0),
        (0.0, 1.0),
    ]
    assert mesh.uvs_lm == [
        (0.05, 0.05),
        (0.45, 0.05),
        (0.45, 0.45),
        (0.55, 0.55),
        (0.95, 0.95),
        (0.55, 0.95),
    ]
    assert mesh.uvs_2 == [
        (0.1, 0.1),
        (0.2, 0.1),
        (0.2, 0.2),
        (0.1, 0.1),
        (0.2, 0.2),
        (0.1, 0.2),
    ]
    assert mesh.face_uvs == []
    assert mesh.face_uvs_lm == []
    assert mesh.face_uvs_2 == []
    assert mesh.face_mats == [2, 4]
    assert [skin.influences[0].bone_index for skin in mesh.skin_data] == [0, 1, 2, 0, 2, 3]
    assert mesh.skin_data[0] is not mesh.skin_data[3]
    assert mesh.skin_data[0].influences[0] is not mesh.skin_data[3].influences[0]
    assert mesh._gr_lightmap_vertex_source_mapping == [0, 1, 2, 0, 2, 3]


def test_lightmap_vertex_stream_remap_is_noop_for_existing_per_vertex_uv2() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    original_vertices = mesh.vertices
    original_faces = mesh.faces
    original_uv1 = mesh.uvs
    original_uv2 = mesh.uvs_lm
    original_normals = mesh.normals

    result = UVAtlasGenerator().remap_vertex_stream_for_lightmap(mesh, target_channel=1)

    assert result.success
    assert not result.changed
    assert result.source_vertex_count == result.vertex_count == 3
    assert mesh.vertices is original_vertices
    assert mesh.faces is original_faces
    assert mesh.uvs is original_uv1
    assert mesh.uvs_lm is original_uv2
    assert mesh.normals is original_normals


def test_baker_does_not_fallback_to_diffuse_uvs_unless_selected() -> None:
    model, mesh = _model_with_lightmapped_triangle()
    mesh.uvs_lm = []

    default_result = LightmapBaker().collect_bakeable_meshes(
        LightmapBakeJob(model=model, selected_meshes=[mesh], settings=LightmapBakeSettings(bake_selected_only=True))
    )
    selected_uv1 = LightmapBaker().collect_bakeable_meshes(
        LightmapBakeJob(
            model=model,
            selected_meshes=[mesh],
            settings=LightmapBakeSettings(bake_selected_only=True, selected_uv_channel=0),
        )
    )

    assert default_result == []
    assert selected_uv1[0].uv_channel == 0


def test_live_preview_bake_returns_pil_image_without_writing_file() -> None:
    _model, mesh = _model_with_lightmapped_triangle()
    light = SimpleNamespace(
        name="AuroraLight001",
        source_type="Aurora",
        enabled=True,
        visible=True,
        type="aurora_point",
        position=(0.25, 0.25, 2.0),
        color=(1.0, 1.0, 1.0),
        intensity=2.0,
        radius=4.0,
        casts_shadows=False,
        affects_lightmap=True,
    )
    settings = LightmapBakeSettings(preview_resolution=64, selected_uv_channel=1, include_ambient=True)

    result = LightmapBaker().bake_preview(mesh, [light], settings)

    assert result.success
    assert result.image_path is None
    assert result.preview_image is not None
    assert result.preview_image.size == (64, 64)


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


def test_shadow_solver_rejects_only_the_source_triangle_and_keeps_folded_self_shadow() -> None:
    mesh = SimpleNamespace(
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
        ],
        faces=[(0, 1, 2), (3, 4, 5)],
        position=(0.0, 0.0, 0.0),
        vertex_space=1,
    )
    settings = LightmapBakeSettings(use_shadows=True, normal_bias=0.002)
    light = SimpleNamespace(
        type="point",
        position=(0.2, 0.2, 2.0),
        casts_shadows=True,
    )
    solver = LightmapShadowSolver()
    solver.build_acceleration_structure([mesh])
    # Keep this contract deterministic even when a developer has Open3D.
    solver._o3d_scene = None

    shadowed = solver.calculate_shadow_factor(
        {
            "position": (0.2, 0.2, 0.0),
            "normal": (0.0, 0.0, 1.0),
            "mesh_id": id(mesh) & 0x7FFFFFFF,
            "triangle_id": 0,
        },
        light,
        settings,
    )

    assert shadowed == 0.0

    source_only = SimpleNamespace(
        vertices=mesh.vertices[:3],
        faces=[(0, 1, 2)],
        position=(0.0, 0.0, 0.0),
        vertex_space=1,
    )
    solver.build_acceleration_structure([source_only])
    solver._o3d_scene = None
    acne_safe = solver.calculate_shadow_factor(
        {
            "position": (0.2, 0.2, 0.0),
            # Deliberately point the bias behind the polygon. The exact source
            # triangle must still be rejected without ignoring its whole mesh.
            "normal": (0.0, 0.0, -1.0),
            "mesh_id": id(source_only) & 0x7FFFFFFF,
            "triangle_id": 0,
        },
        light,
        settings,
    )

    assert acne_safe == 1.0


def test_uv_overlap_validation_preserves_small_mesh_results_and_scales_to_room_atlases() -> None:
    validator = LightmapUVValidator()
    small = SimpleNamespace(
        name="overlap_fixture",
        uvs_lm=[
            (0.0, 0.0),
            (0.5, 0.0),
            (0.0, 0.5),
            (0.1, 0.1),
            (0.6, 0.1),
            (0.1, 0.6),
            (0.5, 0.0),
            (1.0, 0.0),
            (0.5, 0.5),
        ],
        faces=[(0, 1, 2), (3, 4, 5), (6, 7, 8)],
    )
    assert validator.detect_overlaps(small, 1) == [(0, 1), (1, 2)]

    grid_size = 64
    uvs = [
        (x / grid_size, y / grid_size)
        for y in range(grid_size + 1)
        for x in range(grid_size + 1)
    ]
    faces = []
    stride = grid_size + 1
    for y in range(grid_size):
        for x in range(grid_size):
            lower_left = y * stride + x
            faces.append((lower_left, lower_left + 1, lower_left + stride + 1))
            faces.append((lower_left, lower_left + stride + 1, lower_left + stride))
    atlas = SimpleNamespace(name="room_atlas", uvs_lm=uvs, faces=faces)

    started = time.perf_counter()
    overlaps = validator.detect_overlaps(atlas, 1)
    elapsed = time.perf_counter() - started

    assert overlaps == []
    assert elapsed < 2.0, f"8,192-triangle UV broadphase took {elapsed:.3f}s"


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
