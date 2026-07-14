"""Transactional Map Studio lightmap bake/apply workflow.

This module is deliberately headless.  It joins the immutable authored-module
scene contract to the renderer-owned UV atlas and lightmap bake pipeline, but
does not write files or mutate a KMAP document.  Callers decide when the
returned project and sidecar resources become part of a save/export
transaction.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Sequence

import numpy as np
from PIL import Image

from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings
from src.core.lighting.lightmap_baker import LightmapBaker
from src.core.lighting.uv_atlas_generator import UVAtlasGenerator
from src.core.modules.authored_imported_mesh import (
    MDL_MAX_VERTICES_PER_SURFACE,
    ImportedMeshRoomPrimitive,
    ImportedMeshSurface,
    imported_mesh_surface_index_for_role,
    imported_mesh_surface_role,
)
from src.core.modules.authored_module_lighting import AuthoredRoomLight, validate_authored_room_lights
from src.core.modules.authored_module_project import AuthoredModuleProject, normalise_resref


LIGHTMAP_TXI_TEXT = (
    "islightmap 1\n"
    "compresstexture 0\n"
    "mipmap 0\n"
    "downsamplemax 0\n"
)
LIGHTMAP_TPC_TXI_BYTES = LIGHTMAP_TXI_TEXT.replace("\n", "\r\n").encode("ascii")


@dataclass(frozen=True)
class MapStudioLightmapSidecar:
    """In-memory texture resources and deterministic proof for one surface."""

    room_resref: str
    surface_role: str
    surface_index: int
    lightmap_resref: str
    width: int
    height: int
    rgba_bytes: bytes
    tpc_bytes: bytes
    tga_bytes: bytes
    txi_text: str = LIGHTMAP_TXI_TEXT
    rgba_sha256: str = ""
    tpc_sha256: str = ""
    tga_sha256: str = ""
    txi_sha256: str = ""
    topology_before_sha256: str = ""
    topology_after_sha256: str = ""
    triangle_geometry_sha256: str = ""
    vertex_source_mapping: tuple[int, ...] = ()
    duplicated_vertex_count: int = 0
    generated_uv2: bool = False
    uv_atlas_source: str = "existing_uv2"
    settings: dict[str, Any] = field(default_factory=dict)
    proof: dict[str, Any] = field(default_factory=dict)

    @property
    def resources(self) -> tuple[tuple[str, str, bytes], ...]:
        """Return the existing TGA+TXI fallback resource pair.

        Keep this compatibility view for callers that have not yet opted into
        TPC staging.  ``preferred_resources`` is the vanilla-shaped KOTOR
        resource and ``all_resources`` exposes both choices to a transaction.
        """

        return (
            (self.lightmap_resref, "TGA", self.tga_bytes),
            (self.lightmap_resref, "TXI", self.txi_text.encode("ascii")),
        )

    @property
    def preferred_resources(self) -> tuple[tuple[str, str, bytes], ...]:
        """Return the engine-preferred TPC resource with embedded TXI."""

        return ((self.lightmap_resref, "TPC", self.tpc_bytes),)

    @property
    def all_resources(self) -> tuple[tuple[str, str, bytes], ...]:
        """Return TPC plus the retained TGA+TXI fallback resources."""

        return self.preferred_resources + self.resources


@dataclass(frozen=True)
class MapStudioLightmapApplyResult:
    """Transactional result: failures always retain the original project."""

    success: bool
    project: AuthoredModuleProject
    sidecar: MapStudioLightmapSidecar | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.success and self.sidecar is not None and not self.errors


@dataclass
class _SurfaceBakeMesh:
    """Mutable renderer adapter built only from a copied authored surface."""

    name: str
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]
    face_mats: list[int]
    uvs: list[tuple[float, float]]
    normals: list[tuple[float, float, float]]
    uvs_lm: list[tuple[float, float]]
    diffuse: tuple[float, float, float]
    texture: str
    position: tuple[float, float, float]
    face_uvs: list[tuple[int, int, int]] = field(default_factory=list)
    face_uvs_lm: list[tuple[int, int, int]] = field(default_factory=list)
    vertex_space: int = 0


@dataclass(frozen=True)
class _AuthoredBakeLight:
    """Renderer-light view of immutable Map Studio light intent."""

    name: str
    position: tuple[float, float, float]
    color: tuple[float, float, float]
    radius: float
    intensity: float
    type: str
    direction: tuple[float, float, float] = (0.0, 0.0, -1.0)
    cone_angle: float = 45.0
    enabled: bool = True
    visible: bool = True
    affects_lightmap: bool = True
    casts_shadows: bool = True
    source_type: str = "map_studio"
    ambient_only: bool = False


def apply_imported_surface_lightmap(
    project: AuthoredModuleProject,
    *,
    room_resref: str,
    surface_role_or_index: str | int,
    lightmap_resref: str,
    resolution: int | None = None,
    settings: LightmapBakeSettings | None = None,
    room_lights: Sequence[AuthoredRoomLight] | None = None,
    baker: LightmapBaker | None = None,
    uv_generator: UVAtlasGenerator | None = None,
) -> MapStudioLightmapApplyResult:
    """Bake and apply one imported-room surface lightmap in memory.

    The function never mutates ``project``, its room/surface records, the
    caller's settings, or a KMAP object.  Any validation, atlas, remap, bake,
    encoding, or preservation failure returns the original project object.
    """

    warnings: list[str] = []
    try:
        if not isinstance(project, AuthoredModuleProject):
            raise TypeError("Map Studio lightmap apply requires an AuthoredModuleProject.")
        target_room_resref = _strict_resref(room_resref, label="room")
        final_lightmap_resref = _strict_resref(lightmap_resref, label="lightmap")
        room_index, room = _find_room(project, target_room_resref)
        primitive = room.primitive
        if not isinstance(primitive, ImportedMeshRoomPrimitive):
            raise ValueError(
                f"Room {target_room_resref} is not an imported-mesh room; compile it to imported surfaces before baking."
            )
        surface_index = _surface_index(primitive, surface_role_or_index)
        surface_role = imported_mesh_surface_role(surface_index)
        source_surface = primitive.surfaces[surface_index]
        bake_settings = _normalized_settings(settings, resolution)
        warnings.extend(tuple(getattr(bake_settings, "warnings", ()) or ()))

        source_proof = _surface_proof(source_surface)
        mesh = _surface_bake_mesh(source_surface, room.position)
        atlas_generator = uv_generator or UVAtlasGenerator()
        generated_uv2 = not bool(mesh.uvs_lm)
        atlas_source = "existing_uv2"
        if generated_uv2:
            atlas_result = atlas_generator.generate_lightmap_uvs(
                mesh,
                target_channel=1,
                resolution=bake_settings.resolution,
                padding_pixels=bake_settings.padding_pixels,
                replace_existing=False,
            )
            warnings.extend(tuple(atlas_result.warnings or ()))
            warnings.extend(tuple(atlas_result.messages or ()))
            if not atlas_result.success:
                raise ValueError("; ".join(atlas_result.errors or ["UV2 atlas generation failed."]))
            atlas_source = str(getattr(mesh, "_gr_generated_lightmap_uv_source", "generated") or "generated")

        # This explicit boundary is required even when UV2 is already
        # per-vertex: it proves whether a seam split is needed before the baker
        # and KOTOR's single-index MDX stream see the mesh.
        remap_result = atlas_generator.remap_vertex_stream_for_lightmap(mesh, target_channel=1)
        warnings.extend(tuple(remap_result.warnings or ()))
        warnings.extend(tuple(remap_result.messages or ()))
        if not remap_result.success:
            raise ValueError("; ".join(remap_result.errors or ["UV2 vertex-stream remap failed."]))
        if len(mesh.vertices) > MDL_MAX_VERTICES_PER_SURFACE:
            raise ValueError(
                f"Lightmap seam remap produced {len(mesh.vertices)} vertices; KOTOR MDL surfaces support at most "
                f"{MDL_MAX_VERTICES_PER_SURFACE}. Split the surface before baking."
            )
        if len(mesh.uvs_lm) != len(mesh.vertices):
            raise ValueError("Lightmap UV2 is not a complete per-vertex stream after remapping.")

        mapping = tuple(
            int(value)
            for value in tuple(
                getattr(mesh, "_gr_lightmap_vertex_source_mapping", tuple(range(len(mesh.vertices)))) or ()
            )
        )
        if not mapping:
            mapping = tuple(range(len(mesh.vertices)))
        if len(mapping) != len(mesh.vertices):
            raise ValueError("Lightmap vertex source mapping does not match the remapped vertex count.")

        applied_surface = replace(
            source_surface,
            vertices=_vec3_tuple(mesh.vertices),
            faces=_face_tuple(mesh.faces),
            face_mats=tuple(int(value) for value in mesh.face_mats),
            uvs=_vec2_tuple(mesh.uvs),
            normals=_vec3_tuple(mesh.normals),
            uvs_lm=_vec2_tuple(mesh.uvs_lm),
            lightmap=final_lightmap_resref,
            tex_count=max(2, int(source_surface.tex_count or 1)),
        )
        applied_proof = _surface_proof(applied_surface)
        preservation = _preservation_proof(source_proof, applied_proof)
        if not all(preservation.values()):
            failed = ", ".join(name for name, ok in preservation.items() if not ok)
            raise ValueError(f"Lightmap remap failed stream-preservation proof: {failed}.")

        requested_lights = tuple(project.lights if room_lights is None else room_lights)
        light_validation = validate_authored_room_lights(
            requested_lights,
            room_resrefs={candidate.normalised_resref() for candidate in project.rooms},
        )
        warnings.extend(light_validation.warnings)
        if not light_validation.ok:
            raise ValueError("; ".join(light_validation.blocking_issues))
        active_lights, ignored_light_count = _room_bake_lights(
            requested_lights,
            target_room_resref,
        )
        if not active_lights and not bake_settings.include_ambient and not bake_settings.use_indirect_approximation:
            warnings.append(
                f"Room {target_room_resref} has no active lightmap lights and ambient/indirect lighting is disabled; "
                "the baked lightmap will be black."
            )
        renderer_baker = baker or LightmapBaker()
        rgba_bytes, tga_bytes, bake_warnings = _bake_surface_bytes(
            renderer_baker,
            mesh,
            active_lights,
            bake_settings,
        )
        warnings.extend(bake_warnings)
        tpc_bytes = encode_kotor_lightmap_tpc_rgba(
            rgba_bytes,
            width=int(bake_settings.resolution),
            height=int(bake_settings.resolution),
        )

        rgba_sha256 = hashlib.sha256(rgba_bytes).hexdigest()
        tpc_sha256 = hashlib.sha256(tpc_bytes).hexdigest()
        tga_sha256 = hashlib.sha256(tga_bytes).hexdigest()
        txi_sha256 = hashlib.sha256(LIGHTMAP_TXI_TEXT.encode("ascii")).hexdigest()
        proof = {
            "schema": "ghostrigger.map_studio_lightmap_apply.v1",
            "status": "headless_bake_complete",
            "engine_game_proof": False,
            "room_resref": target_room_resref,
            "surface_role": surface_role,
            "surface_index": surface_index,
            "surface_name": str(source_surface.name or ""),
            "lightmap_resref": final_lightmap_resref,
            "resolution": int(bake_settings.resolution),
            "source": source_proof,
            "applied": applied_proof,
            "preservation": preservation,
            "vertex_source_mapping": list(mapping),
            "duplicated_vertex_count": max(0, len(mesh.vertices) - len(source_surface.vertices)),
            "uv2": {
                "generated": generated_uv2,
                "atlas_source": atlas_source,
                "single_index_stream": True,
                "count": len(mesh.uvs_lm),
            },
            "lights": {
                "active_room_light_count": len(active_lights),
                "ignored_other_room_light_count": ignored_light_count,
            },
            "structural_preservation": {
                "stable_surface_role": imported_mesh_surface_role(surface_index) == surface_role,
                "wok_reference_preserved": True,
                "other_surface_count": max(0, len(primitive.surfaces) - 1),
                "other_room_count": max(0, len(project.rooms) - 1),
            },
            "resources": {
                "rgba_sha256": rgba_sha256,
                "tpc_sha256": tpc_sha256,
                "tga_sha256": tga_sha256,
                "txi_sha256": txi_sha256,
                "txi": LIGHTMAP_TXI_TEXT.strip(),
                "preferred_format": "TPC",
                "fallback_formats": ["TGA", "TXI"],
            },
        }
        sidecar = MapStudioLightmapSidecar(
            room_resref=target_room_resref,
            surface_role=surface_role,
            surface_index=surface_index,
            lightmap_resref=final_lightmap_resref,
            width=int(bake_settings.resolution),
            height=int(bake_settings.resolution),
            rgba_bytes=rgba_bytes,
            tpc_bytes=tpc_bytes,
            tga_bytes=tga_bytes,
            rgba_sha256=rgba_sha256,
            tpc_sha256=tpc_sha256,
            tga_sha256=tga_sha256,
            txi_sha256=txi_sha256,
            topology_before_sha256=str(source_proof["topology_sha256"]),
            topology_after_sha256=str(applied_proof["topology_sha256"]),
            triangle_geometry_sha256=str(applied_proof["triangle_geometry_sha256"]),
            vertex_source_mapping=mapping,
            duplicated_vertex_count=max(0, len(mesh.vertices) - len(source_surface.vertices)),
            generated_uv2=generated_uv2,
            uv_atlas_source=atlas_source,
            settings=_settings_summary(bake_settings),
            proof=copy.deepcopy(proof),
        )

        surfaces = list(primitive.surfaces)
        surfaces[surface_index] = applied_surface
        primitive_metadata = copy.deepcopy(dict(primitive.metadata or {}))
        existing_lightmap_records = primitive_metadata.get("lightmap_bakes")
        lightmap_records = dict(existing_lightmap_records) if isinstance(existing_lightmap_records, dict) else {}
        if existing_lightmap_records is not None and not isinstance(existing_lightmap_records, dict):
            primitive_metadata["lightmap_bakes_legacy"] = copy.deepcopy(existing_lightmap_records)
        lightmap_records[surface_role] = copy.deepcopy(proof)
        primitive_metadata["lightmap_bakes"] = lightmap_records
        updated_primitive = replace(primitive, surfaces=tuple(surfaces), metadata=primitive_metadata)
        rooms = list(project.rooms)
        rooms[room_index] = replace(room, primitive=updated_primitive)
        updated_project = replace(project, rooms=tuple(rooms))
        return MapStudioLightmapApplyResult(
            success=True,
            project=updated_project,
            sidecar=sidecar,
            warnings=tuple(dict.fromkeys(str(value) for value in warnings if str(value).strip())),
        )
    except Exception as exc:
        return MapStudioLightmapApplyResult(
            success=False,
            project=project,
            sidecar=None,
            warnings=tuple(dict.fromkeys(str(value) for value in warnings if str(value).strip())),
            errors=(str(exc),),
        )


def encode_kotor_lightmap_tpc_rgba(
    rgba_bytes: bytes | bytearray | memoryview,
    *,
    width: int,
    height: int,
) -> bytes:
    """Encode one uncompressed RGBA lightmap using PyKotor's TPC writer.

    K2's ``001ebo1_lm0`` and ``001ebo1_lm1`` establish the exact structural
    contract used here: ``data_size=0``, RGBA encoding 4, one mip level, alpha
    coverage in the header, and a CRLF-terminated embedded TXI trailer with no
    trailing NUL.  PyKotor reliably writes the binary header and pixel payload,
    but its generic TXI serializer reorders these commands and adds a NUL byte.
    The wrapper therefore asks PyKotor to write only the header/pixels and then
    appends the byte-exact vanilla trailer.
    """

    payload = bytes(rgba_bytes)
    frame_width = int(width)
    frame_height = int(height)
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("KOTOR lightmap dimensions must be positive.")
    if frame_width >= 0x8000 or frame_height >= 0x8000:
        raise ValueError("KOTOR lightmap dimensions must be smaller than 32768 pixels.")
    if frame_width & (frame_width - 1) or frame_height & (frame_height - 1):
        raise ValueError("KOTOR lightmap dimensions must be powers of two.")
    expected_size = frame_width * frame_height * 4
    if len(payload) != expected_size:
        raise ValueError(
            f"RGBA lightmap payload has {len(payload)} bytes; expected {expected_size} "
            f"for {frame_width}x{frame_height}."
        )

    try:
        from pykotor.resource.formats.tpc.tpc_auto import bytes_tpc, read_tpc
        from pykotor.resource.formats.tpc.tpc_data import TPC, TPCTextureFormat
        from pykotor.resource.type import ResourceType
    except ImportError as exc:  # pragma: no cover - embedded distribution guard
        raise RuntimeError("PyKotor TPC support is required to encode Map Studio lightmaps.") from exc

    texture = TPC()
    texture.set_single(payload, TPCTextureFormat.RGBA, frame_width, frame_height)
    # ``TPC.set_single`` deliberately builds a complete mip chain.  Vanilla
    # 001ebo1 lightmaps declare exactly one level and explicitly disable
    # mipmapping in TXI, so retain the base level only.
    texture.layers[0].mipmaps[:] = texture.layers[0].mipmaps[:1]
    # Vanilla K2 RGBA lightmaps store normalized alpha coverage here.  The
    # 001ebo1 fixtures use binary 0/255 alpha, making this their exact ratio of
    # occupied atlas texels; an opaque authored bake therefore writes 1.0.
    texture.alpha_test = sum(payload[3::4]) / float(255 * frame_width * frame_height)
    binary = bytes_tpc(texture, ResourceType.TPC)
    if len(binary) != 128 + expected_size:
        raise ValueError("PyKotor emitted an unexpected uncompressed TPC payload size.")
    if binary[0:4] != b"\x00\x00\x00\x00":
        raise ValueError("PyKotor did not emit vanilla uncompressed TPC data_size=0.")
    if binary[8:14] != (
        frame_width.to_bytes(2, "little")
        + frame_height.to_bytes(2, "little")
        + b"\x04\x01"
    ):
        raise ValueError("PyKotor emitted an unexpected RGBA TPC dimension/encoding header.")
    if binary[128:] != payload:
        raise ValueError("PyKotor changed the RGBA lightmap payload during TPC encoding.")

    candidate = binary + LIGHTMAP_TPC_TXI_BYTES
    reopened = read_tpc(candidate)
    if reopened.dimensions() != (frame_width, frame_height):
        raise ValueError("TPC readback dimensions do not match the authored lightmap.")
    if reopened.format() != TPCTextureFormat.RGBA:
        raise ValueError("TPC readback is not uncompressed RGBA.")
    if bytes(reopened.get().data) != payload:
        raise ValueError("TPC readback pixels do not match the authored lightmap.")
    txi_lines = {line.strip().lower() for line in str(reopened.txi).splitlines() if line.strip()}
    expected_txi_lines = {line.strip().lower() for line in LIGHTMAP_TXI_TEXT.splitlines() if line.strip()}
    if not expected_txi_lines.issubset(txi_lines):
        raise ValueError("TPC readback did not preserve the vanilla lightmap TXI contract.")
    return candidate


def _strict_resref(value: Any, *, label: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"Map Studio {label} resref is required.")
    if "." in raw:
        raise ValueError(f"Map Studio {label} resref must not include a file extension.")
    if len(raw) > 16:
        raise ValueError(f"Map Studio {label} resref must be 16 characters or fewer.")
    normalized = normalise_resref(raw)
    if not normalized or any(not (character.isascii() and (character.isalnum() or character == "_")) for character in raw):
        raise ValueError(f"Map Studio {label} resref may only contain ASCII letters, numbers, and underscores.")
    return normalized


def _find_room(project: AuthoredModuleProject, room_resref: str) -> tuple[int, Any]:
    for index, room in enumerate(project.rooms):
        if room.normalised_resref() == room_resref:
            return index, room
    raise ValueError(f"Map Studio room {room_resref!r} does not exist in the authored project.")


def _surface_index(primitive: ImportedMeshRoomPrimitive, role_or_index: str | int) -> int:
    if isinstance(role_or_index, bool):
        raise ValueError("A boolean is not a valid imported-mesh surface index.")
    if isinstance(role_or_index, int):
        index = int(role_or_index)
    else:
        role = str(role_or_index or "").strip()
        index = imported_mesh_surface_index_for_role(primitive, role)
    if index < 0 or index >= len(primitive.surfaces):
        raise ValueError(f"Unknown imported-mesh surface role/index: {role_or_index!r}.")
    return index


def _normalized_settings(settings: LightmapBakeSettings | None, resolution: int | None) -> LightmapBakeSettings:
    candidate = copy.deepcopy(settings) if settings is not None else LightmapBakeSettings()
    if not isinstance(candidate, LightmapBakeSettings):
        raise TypeError("Map Studio lightmap settings must be LightmapBakeSettings.")
    if resolution is not None:
        candidate.resolution = int(resolution)
        candidate.bake_resolution = int(resolution)
    candidate.selected_uv_channel = 1
    candidate.output_format = "tga"
    candidate.generate_manifest = False
    candidate.preview_after_bake = False
    normalized = candidate.normalized()
    normalized.selected_uv_channel = 1
    normalized.output_format = "tga"
    normalized.generate_manifest = False
    normalized.preview_after_bake = False
    return normalized


def _surface_bake_mesh(surface: ImportedMeshSurface, room_position: Any) -> _SurfaceBakeMesh:
    return _SurfaceBakeMesh(
        name=str(surface.name or "imported_surface"),
        vertices=list(_vec3_tuple(surface.vertices)),
        faces=list(_face_tuple(surface.faces)),
        face_mats=[int(value) for value in surface.face_mats],
        uvs=list(_vec2_tuple(surface.uvs)),
        normals=list(_vec3_tuple(surface.normals)),
        uvs_lm=list(_vec2_tuple(surface.uvs_lm)),
        diffuse=tuple(float(value) for value in surface.diffuse[:3]),
        texture=str(surface.texture or ""),
        position=tuple(float(value) for value in tuple(room_position)[:3]),
    )


def _room_bake_lights(
    lights: Sequence[AuthoredRoomLight],
    room_resref: str,
) -> tuple[tuple[_AuthoredBakeLight, ...], int]:
    active: list[_AuthoredBakeLight] = []
    ignored = 0
    for light in tuple(lights or ()):
        light_room = normalise_resref(getattr(light, "room_resref", ""))
        if light_room != room_resref:
            ignored += 1
            continue
        metadata = dict(getattr(light, "metadata", {}) or {})
        enabled = bool(getattr(light, "enabled", metadata.get("enabled", True)))
        affects_lightmap = bool(
            getattr(light, "affects_lightmap", metadata.get("affects_lightmap", True))
        )
        if not enabled or not affects_lightmap:
            ignored += 1
            continue
        light_type = str(getattr(light, "light_type", "point") or "point").strip().lower()
        direction = getattr(light, "direction", metadata.get("direction", (0.0, 0.0, -1.0)))
        cone_angle = getattr(
            light,
            "cone_angle_degrees",
            metadata.get("cone_angle_degrees", metadata.get("cone_angle", 45.0)),
        )
        casts_shadows = bool(
            getattr(light, "casts_shadows", metadata.get("casts_shadows", True))
        )
        active.append(
            _AuthoredBakeLight(
                name=str(getattr(light, "name", "") or "room_light"),
                position=tuple(float(value) for value in tuple(getattr(light, "position", (0.0, 0.0, 0.0)))[:3]),
                color=tuple(float(value) for value in tuple(getattr(light, "color", (1.0, 1.0, 1.0)))[:3]),
                radius=float(getattr(light, "radius", 8.0) or 8.0),
                intensity=float(getattr(light, "intensity", 1.0) or 0.0),
                type=light_type,
                direction=tuple(float(value) for value in tuple(direction)[:3]),
                cone_angle=float(cone_angle),
                enabled=enabled,
                visible=bool(metadata.get("visible", True)),
                affects_lightmap=affects_lightmap,
                casts_shadows=casts_shadows,
                ambient_only=light_type == "ambient",
            )
        )
    return tuple(active), ignored


def _bake_surface_bytes(
    baker: LightmapBaker,
    mesh: _SurfaceBakeMesh,
    lights: Sequence[_AuthoredBakeLight],
    settings: LightmapBakeSettings,
) -> tuple[bytes, bytes, tuple[str, ...]]:
    """Run the existing renderer bake stages without invoking file output."""

    validation = baker.uv_validator.validate_mesh_uvs(mesh, 1)
    if validation.errors:
        raise ValueError("; ".join(validation.errors))
    shadow_solver = None
    if settings.use_shadows:
        baker.shadow_solver.build_acceleration_structure([mesh])
        shadow_solver = baker.shadow_solver
    buffer = baker.rasterizer.rasterize_mesh(mesh, 1, settings.resolution)
    if not buffer.valid_mask.any():
        raise ValueError("No valid texels were rasterized from the remapped UV2 stream.")
    buffer.baked_rgb = baker.lighting_solver.solve_buffer(buffer, lights, settings, shadow_solver)
    image = baker.padding.pad_islands(buffer.baked_rgb, buffer.valid_mask, settings.padding_pixels)
    image = baker.padding.dilate(image, buffer.valid_mask, settings.dilation_passes)
    rgb8 = (np.clip(image, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    alpha = np.full((settings.resolution, settings.resolution, 1), 255, dtype=np.uint8)
    rgba8 = np.concatenate((rgb8[:, :, :3], alpha), axis=2)
    rgba_bytes = rgba8.tobytes(order="C")
    output = io.BytesIO()
    Image.fromarray(rgba8, "RGBA").save(output, format="TGA")
    bake_warnings = list(validation.warnings)
    solver_warning = str(getattr(baker.lighting_solver, "last_warning", "") or "")
    if solver_warning:
        bake_warnings.append(solver_warning)
    return rgba_bytes, output.getvalue(), tuple(bake_warnings)


def _surface_proof(surface: ImportedMeshSurface) -> dict[str, Any]:
    payload = {
        "vertex_count": len(surface.vertices),
        "face_count": len(surface.faces),
        "topology_sha256": _json_sha256({"vertex_count": len(surface.vertices), "faces": surface.faces}),
        "geometry_sha256": _json_sha256({"vertices": surface.vertices, "faces": surface.faces}),
        "triangle_geometry_sha256": _corner_stream_sha256(surface.vertices, surface.faces),
        "uv0_corner_sha256": _corner_stream_sha256(surface.uvs, surface.faces),
        "normal_corner_sha256": _corner_stream_sha256(surface.normals, surface.faces),
        "face_mats_sha256": _json_sha256(tuple(int(value) for value in surface.face_mats)),
        "material_sha256": _json_sha256(
            {
                "texture": surface.texture,
                "texture_names": surface.texture_names,
                "diffuse": surface.diffuse,
                "ambient": surface.ambient,
                "specular": surface.specular,
                "shininess": surface.shininess,
                "alpha": surface.alpha,
                "has_shadow": surface.has_shadow,
                "render": surface.render,
                "selfillum": surface.selfillum,
                "transparency_hint": surface.transparency_hint,
                "beaming": surface.beaming,
                "background_geometry": surface.background_geometry,
                "rotate_texture": surface.rotate_texture,
                "animate_uv": surface.animate_uv,
                "uv_dir_x": surface.uv_dir_x,
                "uv_dir_y": surface.uv_dir_y,
                "uv_jitter": surface.uv_jitter,
                "uv_jitter_speed": surface.uv_jitter_speed,
                "dirt_enabled": surface.dirt_enabled,
                "dirt_texture": surface.dirt_texture,
                "dirt_coord_space": surface.dirt_coord_space,
                "hide_in_holograms": surface.hide_in_holograms,
                "mesh_average_point": surface.mesh_average_point,
                "mesh_unknown0": bytes(surface.mesh_unknown0 or b"").hex(),
                "backdrop": surface.backdrop,
            }
        ),
    }
    return payload


def _preservation_proof(before: dict[str, Any], after: dict[str, Any]) -> dict[str, bool]:
    return {
        "face_count": before["face_count"] == after["face_count"],
        "triangle_geometry": before["triangle_geometry_sha256"] == after["triangle_geometry_sha256"],
        "uv0": before["uv0_corner_sha256"] == after["uv0_corner_sha256"],
        "normals": before["normal_corner_sha256"] == after["normal_corner_sha256"],
        "face_mats": before["face_mats_sha256"] == after["face_mats_sha256"],
        "material": before["material_sha256"] == after["material_sha256"],
    }


def _corner_stream_sha256(values: Sequence[Any], faces: Sequence[Any]) -> str:
    if not values:
        return _json_sha256(())
    corners: list[Any] = []
    for face in faces:
        try:
            corners.extend(values[int(index)] for index in tuple(face)[:3])
        except (IndexError, TypeError, ValueError) as exc:
            raise ValueError(f"Cannot prove per-corner stream preservation: {exc}") from exc
    return _json_sha256(corners)


def _json_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _settings_summary(settings: LightmapBakeSettings) -> dict[str, Any]:
    data = asdict(settings)
    data.pop("warnings", None)
    return data


def _vec2_tuple(values: Sequence[Any]) -> tuple[tuple[float, float], ...]:
    return tuple((float(value[0]), float(value[1])) for value in tuple(values or ()))


def _vec3_tuple(values: Sequence[Any]) -> tuple[tuple[float, float, float], ...]:
    return tuple((float(value[0]), float(value[1]), float(value[2])) for value in tuple(values or ()))


def _face_tuple(values: Sequence[Any]) -> tuple[tuple[int, int, int], ...]:
    return tuple((int(value[0]), int(value[1]), int(value[2])) for value in tuple(values or ()))


__all__ = [
    "LIGHTMAP_TPC_TXI_BYTES",
    "LIGHTMAP_TXI_TEXT",
    "MapStudioLightmapApplyResult",
    "MapStudioLightmapSidecar",
    "apply_imported_surface_lightmap",
    "encode_kotor_lightmap_tpc_rgba",
]
