from __future__ import annotations

import io
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _install_native_payload_paths() -> None:
    root = Path(__file__).resolve().parents[1]
    for project in (
        "GhostRigger.Core.Workflow",
        "GhostRigger.Core.Rendering",
        "GhostRigger.Core.Scene",
        "GhostRigger.Core.Math",
    ):
        path = str(root / "native" / project / "Python")
        if path not in sys.path:
            sys.path.insert(0, path)


_install_native_payload_paths()


def _surface(*, name: str = "floor", with_uv2: bool = False):
    from src.core.modules.authored_imported_mesh import ImportedMeshSurface

    return ImportedMeshSurface(
        name=name,
        texture="floortex",
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (0.0, 2.0, 0.0)),
        faces=((0, 1, 2), (0, 2, 3)),
        face_mats=(7, 9),
        uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        normals=((0.0, 0.0, 1.0),) * 4,
        uvs_lm=((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95)) if with_uv2 else (),
        diffuse=(0.8, 0.7, 0.6),
        ambient=(0.2, 0.2, 0.2),
        specular=(0.1, 0.1, 0.1),
        shininess=4.0,
        texture_names=("floortex",),
        tex_count=1,
    )


def _project(*, with_uv2: bool = False):
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name="bake_room",
        verts=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)],
        faces=[WOKFace(0, 1, 2, surface=4)],
    )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="bake_room",
        surfaces=(_surface(with_uv2=with_uv2), _surface(name="wall")),
        source_model="bake_room",
        game="K2",
        wok=wok,
        metadata={"unknown_source_metadata": {"preserve": True}},
    )
    other = ImportedMeshRoomPrimitive(
        room_resref="other_room",
        surfaces=(_surface(name="other"),),
        source_model="other_room",
        game="K2",
    )
    project = AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="lmbaketest", game="K2"),
        rooms=(
            AuthoredRoomSpec(room_resref="bake_room", primitive=primitive, position=(10.0, 20.0, 0.0)),
            AuthoredRoomSpec(room_resref="other_room", primitive=other),
        ),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="lmbaketest")),
        lights=(
            AuthoredRoomLight(
                name="key",
                room_resref="bake_room",
                position=(11.0, 21.0, 3.0),
                color=(1.0, 0.8, 0.6),
                radius=8.0,
                intensity=2.0,
            ),
            AuthoredRoomLight(name="ignored", room_resref="other_room", position=(1.0, 1.0, 2.0)),
        ),
        extra={"unknown_project_data": {"preserve": True}},
    )
    return project, wok


def _shadow_project(*, with_blocker: bool):
    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, ImportedMeshSurface
    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata, AuthoredModuleProject, AuthoredRoomSpec

    surfaces = [_surface(with_uv2=True)]
    if with_blocker:
        surfaces.append(
            ImportedMeshSurface(
                name="ceiling_blocker",
                texture="blocker",
                vertices=(
                    (0.55, 0.55, 1.0),
                    (1.45, 0.55, 1.0),
                    (1.45, 1.45, 1.0),
                    (0.55, 1.45, 1.0),
                ),
                faces=((0, 1, 2), (0, 2, 3)),
                face_mats=(0, 0),
                uvs=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
                normals=((0.0, 0.0, -1.0),) * 4,
            )
        )
    primitive = ImportedMeshRoomPrimitive(
        room_resref="shadow_room",
        surfaces=tuple(surfaces),
        source_model="shadow_room",
        game="K2",
    )
    return AuthoredModuleProject(
        metadata=AuthoredModuleMetadata(module_root="lmshadow", game="K2"),
        rooms=(AuthoredRoomSpec(room_resref="shadow_room", primitive=primitive),),
        placements=AuthoredGameplayPlacement(entry_point=ModuleEntryPoint(area_resref="lmshadow")),
        lights=(
            AuthoredRoomLight(
                name="shadow_key",
                room_resref="shadow_room",
                position=(1.0, 1.0, 3.0),
                color=(1.0, 1.0, 1.0),
                radius=10.0,
                intensity=4.0,
                casts_shadows=True,
            ),
        ),
    )


def test_map_studio_lightmap_apply_generates_uv2_remaps_and_returns_tga_sidecar() -> None:
    from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings
    from src.core.workflow.map_studio_lightmap_apply import LIGHTMAP_TXI_TEXT, apply_imported_surface_lightmap

    project, wok = _project(with_uv2=False)
    original_room = project.rooms[0]
    original_surface = original_room.primitive.surfaces[0]
    original_other_room = project.rooms[1]
    settings = LightmapBakeSettings(
        resolution=256,
        bake_resolution=256,
        padding_pixels=2,
        dilation_passes=2,
        use_shadows=False,
        include_diffuse=False,
    )

    result = apply_imported_surface_lightmap(
        project,
        room_resref="bake_room",
        surface_role_or_index="render",
        lightmap_resref="gr_lm_floor",
        settings=settings,
        room_lights=project.lights,
    )

    assert result.ok, result.errors
    assert result.project is not project
    assert result.sidecar is not None
    assert project.rooms[0] is original_room
    assert project.rooms[0].primitive.surfaces[0] is original_surface
    assert original_surface.lightmap == ""
    assert original_surface.uvs_lm == ()
    assert result.project.rooms[1] is original_other_room
    assert result.project.extra == project.extra

    updated_primitive = result.project.rooms[0].primitive
    updated = updated_primitive.surfaces[0]
    assert updated_primitive.wok is wok
    assert updated_primitive.surfaces[1] is original_room.primitive.surfaces[1]
    assert updated.lightmap == "gr_lm_floor"
    assert updated.tex_count == 2
    assert len(updated.uvs_lm) == len(updated.vertices)
    assert updated.faces != ()
    assert updated.face_mats == original_surface.face_mats
    assert updated.texture == original_surface.texture
    assert updated.texture_names == original_surface.texture_names
    assert updated.diffuse == original_surface.diffuse
    assert updated.ambient == original_surface.ambient

    mapping = result.sidecar.vertex_source_mapping
    assert len(mapping) == len(updated.vertices)
    assert tuple(updated.vertices[index] for index in range(len(updated.vertices))) == tuple(
        original_surface.vertices[source] for source in mapping
    )
    assert tuple(updated.uvs[index] for index in range(len(updated.uvs))) == tuple(
        original_surface.uvs[source] for source in mapping
    )
    assert tuple(updated.normals[index] for index in range(len(updated.normals))) == tuple(
        original_surface.normals[source] for source in mapping
    )

    sidecar = result.sidecar
    assert sidecar.surface_role == "render"
    assert sidecar.surface_index == 0
    assert sidecar.generated_uv2 is True
    assert len(sidecar.rgba_bytes) == 256 * 256 * 4
    assert any(value for offset, value in enumerate(sidecar.rgba_bytes) if offset % 4 != 3)
    assert sidecar.txi_text == LIGHTMAP_TXI_TEXT
    assert sidecar.txi_text.splitlines() == [
        "islightmap 1",
        "compresstexture 0",
        "mipmap 0",
        "downsamplemax 0",
    ]
    assert sidecar.resources[0] == ("gr_lm_floor", "TGA", sidecar.tga_bytes)
    assert sidecar.resources[1] == ("gr_lm_floor", "TXI", LIGHTMAP_TXI_TEXT.encode("ascii"))
    assert sidecar.preferred_resources == (("gr_lm_floor", "TPC", sidecar.tpc_bytes),)
    assert sidecar.all_resources == sidecar.preferred_resources + sidecar.resources
    data_size, alpha_coverage, width, height, encoding, mipmaps = struct.unpack_from(
        "<IfHHBB", sidecar.tpc_bytes, 0
    )
    assert (data_size, alpha_coverage, width, height, encoding, mipmaps) == (0, 1.0, 256, 256, 4, 1)
    assert sidecar.tpc_bytes[128 : 128 + len(sidecar.rgba_bytes)] == sidecar.rgba_bytes
    assert sidecar.tpc_bytes[128 + len(sidecar.rgba_bytes) :] == (
        LIGHTMAP_TXI_TEXT.replace("\n", "\r\n").encode("ascii")
    )
    with Image.open(io.BytesIO(sidecar.tga_bytes)) as image:
        assert image.format == "TGA"
        assert image.mode == "RGBA"
        assert image.size == (256, 256)
    assert len(sidecar.rgba_sha256) == 64
    assert len(sidecar.tpc_sha256) == 64
    assert len(sidecar.tga_sha256) == 64
    assert sidecar.proof["preservation"] == {
        "face_count": True,
        "triangle_geometry": True,
        "uv0": True,
        "normals": True,
        "face_mats": True,
        "material": True,
    }
    assert sidecar.proof["engine_game_proof"] is False
    assert sidecar.proof["lights"] == {
        "active_room_light_count": 1,
        "ignored_other_room_light_count": 1,
    }
    assert updated_primitive.metadata["unknown_source_metadata"] == {"preserve": True}
    assert updated_primitive.metadata["lightmap_bakes"]["render"]["resources"]["tpc_sha256"] == sidecar.tpc_sha256
    assert updated_primitive.metadata["lightmap_bakes"]["render"]["resources"]["tga_sha256"] == sidecar.tga_sha256

    # The workflow owns a normalized copy, not the caller's mutable settings.
    assert settings.output_format == "png"
    assert settings.generate_manifest is True


def test_map_studio_selected_surface_bake_uses_every_room_surface_as_shadow_occluder() -> None:
    from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings
    from src.core.workflow.map_studio_lightmap_apply import apply_imported_surface_lightmap

    settings = LightmapBakeSettings(
        resolution=64,
        bake_resolution=64,
        padding_pixels=0,
        dilation_passes=0,
        use_shadows=True,
        include_ambient=False,
        include_diffuse=False,
        exposure=1.0,
        gamma=1.0,
    )
    blocked_project = _shadow_project(with_blocker=True)
    clear_project = _shadow_project(with_blocker=False)

    blocked = apply_imported_surface_lightmap(
        blocked_project,
        room_resref="shadow_room",
        surface_role_or_index=0,
        lightmap_resref="blocked_lm",
        settings=settings,
        room_lights=blocked_project.lights,
    )
    clear = apply_imported_surface_lightmap(
        clear_project,
        room_resref="shadow_room",
        surface_role_or_index=0,
        lightmap_resref="clear_lm",
        settings=settings,
        room_lights=clear_project.lights,
    )

    assert blocked.ok, blocked.errors
    assert clear.ok, clear.errors
    blocked_pixels = np.frombuffer(blocked.sidecar.rgba_bytes, dtype=np.uint8).reshape((64, 64, 4))
    clear_pixels = np.frombuffer(clear.sidecar.rgba_bytes, dtype=np.uint8).reshape((64, 64, 4))
    blocked_center = float(blocked_pixels[32, 32, :3].mean())
    clear_center = float(clear_pixels[32, 32, :3].mean())

    assert clear_center > 64.0
    assert blocked_center < clear_center * 0.1
    assert blocked.sidecar.proof["shadows"] == {
        "room_occluder_surface_count": 2,
        "source_rejection": "exact_mesh_triangle",
    }


def test_pykotor_rgba_lightmap_encoder_has_vanilla_structural_shape() -> None:
    from pykotor.resource.formats.tpc.tpc_auto import read_tpc

    from src.core.workflow.map_studio_lightmap_apply import (
        LIGHTMAP_TPC_TXI_BYTES,
        encode_kotor_lightmap_tpc_rgba,
    )

    rgba = bytes(
        (
            10,
            20,
            30,
            255,
            40,
            50,
            60,
            0,
            70,
            80,
            90,
            255,
            100,
            110,
            120,
            0,
        )
    )
    encoded = encode_kotor_lightmap_tpc_rgba(rgba, width=2, height=2)

    assert struct.unpack_from("<I", encoded, 0)[0] == 0
    assert struct.unpack_from("<f", encoded, 4)[0] == 0.5
    assert struct.unpack_from("<HHBB", encoded, 8) == (2, 2, 4, 1)
    assert encoded[14:128] == bytes(114)
    assert encoded[128:144] == rgba
    assert encoded[144:] == LIGHTMAP_TPC_TXI_BYTES
    assert not encoded.endswith(b"\x00")

    reopened = read_tpc(encoded)
    assert reopened.dimensions() == (2, 2)
    assert bytes(reopened.get().data) == rgba
    assert set(reopened.txi.splitlines()) >= {
        "islightmap 1",
        "compresstexture 0",
        "mipmap 0",
        "downsamplemax 0",
    }


def test_map_studio_lightmap_adapter_uses_direct_authored_light_fields() -> None:
    from src.core.modules.authored_module_lighting import AuthoredRoomLight
    from src.core.workflow.map_studio_lightmap_apply import _room_bake_lights

    lights = (
        AuthoredRoomLight(
            name="disabled",
            room_resref="bake_room",
            enabled=False,
            affects_lightmap=True,
            metadata={"enabled": True},
        ),
        AuthoredRoomLight(
            name="diffuse_only",
            room_resref="bake_room",
            enabled=True,
            affects_lightmap=False,
            metadata={"affects_lightmap": True},
        ),
        AuthoredRoomLight(
            name="spot",
            room_resref="bake_room",
            light_type="spot",
            enabled=True,
            affects_lightmap=True,
            casts_shadows=False,
            direction=(0.0, 1.0, 0.0),
            cone_angle_degrees=32.0,
            metadata={
                "casts_shadows": True,
                "direction": (1.0, 0.0, 0.0),
                "cone_angle": 70.0,
            },
        ),
    )

    active, ignored = _room_bake_lights(lights, "bake_room")

    assert ignored == 2
    assert len(active) == 1
    assert active[0].name == "spot"
    assert active[0].enabled is True
    assert active[0].affects_lightmap is True
    assert active[0].casts_shadows is False
    assert active[0].direction == (0.0, 1.0, 0.0)
    assert active[0].cone_angle == 32.0


@pytest.mark.skipif(not (K2_ROOT / "chitin.key").is_file(), reason="K2 installation fixture unavailable")
def test_pykotor_rgba_lightmap_encoder_matches_001ebo1_vanilla_bytes() -> None:
    from pykotor.extract.installation import Installation
    from pykotor.resource.type import ResourceType

    from src.core.workflow.map_studio_lightmap_apply import encode_kotor_lightmap_tpc_rgba

    installation = Installation(K2_ROOT)
    for resref in ("001ebo1_lm0", "001ebo1_lm1"):
        resource = installation.resource(resref, ResourceType.TPC)
        assert resource is not None
        vanilla = bytes(resource.data)
        data_size, _alpha_coverage, width, height, encoding, mipmaps = struct.unpack_from(
            "<IfHHBB", vanilla, 0
        )
        assert (data_size, width, height, encoding, mipmaps) == (0, 64, 64, 4, 1)
        rgba = vanilla[128 : 128 + width * height * 4]

        candidate = encode_kotor_lightmap_tpc_rgba(rgba, width=width, height=height)

        assert candidate == vanilla


def test_map_studio_lightmap_apply_accepts_surface_index_and_preserves_existing_uv2_topology() -> None:
    from src.core.workflow.map_studio_lightmap_apply import apply_imported_surface_lightmap

    project, _wok = _project(with_uv2=True)
    before = project.rooms[0].primitive.surfaces[0]
    result = apply_imported_surface_lightmap(
        project,
        room_resref="BAKE_ROOM",
        surface_role_or_index=0,
        lightmap_resref="existing_lm",
        resolution=256,
        room_lights=project.lights,
    )

    assert result.ok, result.errors
    assert result.sidecar is not None
    after = result.project.rooms[0].primitive.surfaces[0]
    assert result.sidecar.generated_uv2 is False
    assert result.sidecar.uv_atlas_source == "existing_uv2"
    assert result.sidecar.duplicated_vertex_count == 0
    assert result.sidecar.topology_before_sha256 == result.sidecar.topology_after_sha256
    assert after.vertices == before.vertices
    assert after.faces == before.faces
    assert after.uvs == before.uvs
    assert after.normals == before.normals
    assert after.uvs_lm == before.uvs_lm


def test_map_studio_lightmap_apply_failure_is_transactional() -> None:
    from src.core.workflow.map_studio_lightmap_apply import apply_imported_surface_lightmap

    project, _wok = _project(with_uv2=False)
    too_long = apply_imported_surface_lightmap(
        project,
        room_resref="bake_room",
        surface_role_or_index="render",
        lightmap_resref="this_lightmap_name_is_too_long",
        resolution=256,
        room_lights=project.lights,
    )
    extension = apply_imported_surface_lightmap(
        project,
        room_resref="bake_room",
        surface_role_or_index="render",
        lightmap_resref="badname.tga",
        resolution=256,
        room_lights=project.lights,
    )
    missing = apply_imported_surface_lightmap(
        project,
        room_resref="missing_room",
        surface_role_or_index="render",
        lightmap_resref="valid_lm",
        resolution=256,
        room_lights=project.lights,
    )

    for result in (too_long, extension, missing):
        assert not result.ok
        assert result.project is project
        assert result.sidecar is None
        assert result.errors
    assert project.rooms[0].primitive.surfaces[0].uvs_lm == ()
    assert project.rooms[0].primitive.surfaces[0].lightmap == ""


def test_map_studio_lightmap_apply_bake_error_does_not_commit_remapped_surface() -> None:
    from src.core.lighting.lightmap_baker import LightmapBaker
    from src.core.workflow.map_studio_lightmap_apply import apply_imported_surface_lightmap

    class FailingRasterizer:
        def rasterize_mesh(self, *_args, **_kwargs):
            raise RuntimeError("synthetic renderer failure")

    project, _wok = _project(with_uv2=False)
    baker = LightmapBaker()
    baker.rasterizer = FailingRasterizer()
    result = apply_imported_surface_lightmap(
        project,
        room_resref="bake_room",
        surface_role_or_index="render",
        lightmap_resref="failed_lm",
        resolution=256,
        room_lights=project.lights,
        baker=baker,
    )

    assert not result.ok
    assert result.project is project
    assert result.sidecar is None
    assert result.errors == ("synthetic renderer failure",)
    assert project.rooms[0].primitive.surfaces[0].uvs_lm == ()
    assert project.rooms[0].primitive.metadata == {"unknown_source_metadata": {"preserve": True}}


def test_map_studio_lightmap_apply_is_embedded_in_workflow_payload() -> None:
    root = Path(__file__).resolve().parents[1]
    owner = root / "native" / "GhostRigger.Core.Workflow"
    manifest = json.loads((owner / "GhostRiggerPythonPayload.json").read_text(encoding="utf-8"))
    packaged_path = "Python/src/core/workflow/map_studio_lightmap_apply.py"
    row = next(entry for entry in manifest["files"] if entry["packaged_path"] == packaged_path)
    packaged = owner / packaged_path

    assert packaged.exists()
    assert hashlib.sha256(packaged.read_bytes()).hexdigest() == row["sha256"]
    assert row["resource_name"] == "PYTHON_PAYLOAD_CORE_WORKFLOW_MAP_STUDIO_LIGHTMAP_APPLY"
    assert f'{row["resource_name"]} RCDATA "{packaged_path}"' in (
        owner / "GhostRiggerPythonPayload.rc"
    ).read_text(encoding="utf-8")
    assert packaged_path.replace("/", "\\") in (
        owner / "GhostRigger.Core.Workflow.vcxproj"
    ).read_text(encoding="utf-8")
