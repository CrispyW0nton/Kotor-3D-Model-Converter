"""Build a live viewport model from authored Map Studio geometry."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from .authored_imported_mesh import authored_room_uses_unresolved_stock_geometry
from .authored_module_metadata import authored_area_metadata
from .authored_module_project import AuthoredModuleProject, AuthoredRoomSpec, compile_authored_room_spec
from .authored_module_world_lighting import authored_world_lighting_settings
from .authored_room_geometry import PrimitiveMesh


@dataclass(frozen=True)
class AuthoredModulePreviewModelResult:
    """Result for the live Map Studio mesh preview."""

    model: Any | None
    room_count: int = 0
    mesh_count: int = 0
    warnings: tuple[str, ...] = ()


def _import_model_data() -> Any:
    try:
        from src.core.geometry import model_data as md  # type: ignore

        return md
    except Exception:
        from core.geometry import model_data as md  # type: ignore

        return md


def _vec3(value: object) -> tuple[float, float, float]:
    try:
        x, y, z = tuple(value)[:3]  # type: ignore[arg-type]
    except Exception:
        return (0.0, 0.0, 0.0)
    return (float(x), float(y), float(z))


def _round_tuple(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(round(float(value), 5) for value in values)


def _point_summary(points: tuple[tuple[float, float, float], ...]) -> dict[str, object]:
    if not points:
        return {"count": 0}
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    zs = [float(point[2]) for point in points]
    return {
        "count": len(points),
        "min": _round_tuple((min(xs), min(ys), min(zs))),
        "max": _round_tuple((max(xs), max(ys), max(zs))),
        "sum": _round_tuple((sum(xs), sum(ys), sum(zs))),
        "first": _round_tuple(tuple(float(value) for value in points[0][:3])),
        "last": _round_tuple(tuple(float(value) for value in points[-1][:3])),
    }


def _face_summary(faces: tuple[tuple[int, int, int], ...]) -> dict[str, object]:
    if not faces:
        return {"count": 0}
    sums = (
        sum(int(face[0]) for face in faces),
        sum(int(face[1]) for face in faces),
        sum(int(face[2]) for face in faces),
    )
    return {
        "count": len(faces),
        "sum": sums,
        "first": tuple(int(value) for value in faces[0][:3]),
        "last": tuple(int(value) for value in faces[-1][:3]),
    }


def _mesh_signature(mesh: PrimitiveMesh) -> dict[str, object]:
    vertices = tuple(mesh.vertices or ())
    faces = tuple(mesh.faces or ())
    return {
        "name": str(mesh.name or ""),
        "vertices": _point_summary(vertices),
        "faces": _face_summary(faces),
        "texture": str(mesh.texture or ""),
        "diffuse": _round_tuple(tuple(float(value) for value in mesh.diffuse[:3])),
        "ambient": _round_tuple(tuple(float(value) for value in mesh.ambient[:3])),
    }


def _preview_key(signature_rows: list[dict[str, object]]) -> str:
    payload = json.dumps(signature_rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _mesh_node(md: Any, mesh: PrimitiveMesh, parent: Any, *, room_resref: str, role: str) -> Any:
    vertices = [tuple(float(value) for value in point[:3]) for point in tuple(mesh.vertices or ())]
    faces = [tuple(int(value) for value in face[:3]) for face in tuple(mesh.faces or ())]
    normals = [tuple(float(value) for value in normal[:3]) for normal in tuple(mesh.normals or ())]
    if len(normals) != len(vertices):
        normals = [(0.0, 0.0, 1.0)] * len(vertices)
    uvs = [tuple(float(value) for value in uv[:2]) for uv in tuple(mesh.uvs or ())]
    if len(uvs) != len(vertices):
        uvs = [(0.0, 0.0)] * len(vertices)
    texture = str(mesh.texture or "")
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    # Imported stock surfaces carry their full render recipe (multi-texture
    # names, lightmap channel) in metadata; without it a converted room
    # renders as an untextured fallback slab.
    texture_names = [str(name) for name in tuple(metadata.get("texture_names") or ()) if str(name).strip()]
    if not texture_names:
        texture_names = [
            str(row.get("texture") or "")
            for row in tuple(metadata.get("material_table") or ())
            if isinstance(row, dict) and str(row.get("texture") or "").strip()
        ]
    if not texture_names and texture:
        texture_names = [texture]
    lightmap = str(metadata.get("lightmap") or "")
    uvs_lm = [tuple(float(v) for v in uv[:2]) for uv in tuple(metadata.get("uvs_lm") or ())]
    face_mats = [
        int(value)
        for value in tuple(metadata.get("face_mats") or metadata.get("face_material_ids") or ())
    ]
    if len(face_mats) != len(faces):
        face_mats = [0] * len(faces)
    node = md.ModelNode(
        name=str(mesh.name or f"{room_resref}_{role}"),
        flags=int(md.NodeFlags.MESH),
        vertices=vertices,
        normals=normals,
        uvs=uvs,
        faces=faces,
        face_mats=face_mats,
        texture=texture,
        texture_names=texture_names,
        tex_count=max(1, int(metadata.get("tex_count") or len(texture_names) or 1)),
        lightmap=lightmap,
        has_lightmap=bool(lightmap),
        diffuse=tuple(float(value) for value in mesh.diffuse[:3]),
        ambient=tuple(float(value) for value in mesh.ambient[:3]),
        vertex_space=0,
    )
    if len(uvs_lm) == len(vertices):
        node.uvs_lm = uvs_lm
    node.parent = parent
    setattr(node, "_gr_map_studio_room_resref", room_resref)
    setattr(node, "_gr_map_studio_mesh_role", role)
    # Keep the stable authored primitive identity on the render node.  The
    # viewport uses it to preview multi-object transforms without rebuilding
    # the full authored module (or guessing from helper_<n> roles).
    setattr(
        node,
        "_gr_map_studio_primitive_name",
        str(metadata.get("logical_primitive_name") or mesh.name or ""),
    )
    transform = dict(metadata.get("transform") or {})
    setattr(
        node,
        "_gr_map_studio_transform_translation",
        _vec3(transform.get("translation", (0.0, 0.0, 0.0))),
    )
    setattr(
        node,
        "_gr_map_studio_transform_pivot",
        _vec3(transform.get("pivot", (0.0, 0.0, 0.0))),
    )
    setattr(node, "_gr_map_studio_authored_mesh", True)
    node.compute_bounds()
    return node


def _source_room_light_rows(room: AuthoredRoomSpec) -> tuple[dict[str, object], ...]:
    """Return normalized stock-light preview records stored on an imported room."""

    primitive_metadata = dict(getattr(getattr(room, "primitive", None), "metadata", {}) or {})
    runtime_graph = dict(primitive_metadata.get("source_runtime_graph") or {})
    return tuple(row for row in tuple(runtime_graph.get("light_nodes") or ()) if isinstance(row, dict))


def _room_signature(room: AuthoredRoomSpec, meshes: tuple[PrimitiveMesh, ...]) -> dict[str, object]:
    return {
        "room": str(room.room_resref or ""),
        "position": _round_tuple(_vec3(room.position)),
        "meshes": [_mesh_signature(mesh) for mesh in meshes],
        "source_room_lights": [
            {
                "name": str(row.get("source_node_name") or ""),
                "position": _round_tuple(_vec3(row.get("position", (0.0, 0.0, 0.0)))),
                "color": _round_tuple(_vec3(row.get("color", (1.0, 1.0, 1.0)))),
                "radius": round(float(row.get("radius", 0.0) or 0.0), 6),
                "multiplier": round(float(row.get("multiplier", 0.0) or 0.0), 6),
                "dynamic_type": int(row.get("dynamic_type", 0) or 0),
            }
            for row in _source_room_light_rows(room)
        ],
    }


def _light_node(md, light, root):
    """Adapt authored light intent to the renderer's normal scene-light node."""

    metadata = dict(getattr(light, "metadata", {}) or {})
    light_type = str(getattr(light, "light_type", "point") or "point").strip().lower()
    node = md.ModelNode(
        name=str(getattr(light, "name", "") or "room_light"),
        flags=int(md.NodeFlags.LIGHT),
        position=_vec3(getattr(light, "position", (0.0, 0.0, 2.25))),
    )
    node.parent = root
    setattr(node, "_gr_map_studio_authored_light", True)
    stable_id = str(getattr(light, "light_id", "") or node.name)
    setattr(node, "_gr_light_id", f"authored_light:{stable_id}")
    setattr(node, "_gr_light_metadata", metadata)
    setattr(node, "source_type", "MapStudioPreview")
    setattr(node, "light_kind", "point" if light_type == "ambient" else light_type)
    setattr(node, "light_enabled", bool(getattr(light, "enabled", metadata.get("enabled", True))))
    setattr(node, "light_color", _vec3(getattr(light, "color", (1.0, 0.92, 0.78))))
    setattr(node, "light_radius", max(0.001, float(getattr(light, "radius", 8.0) or 8.0)))
    setattr(node, "light_multiplier", max(0.0, float(getattr(light, "intensity", 1.0) or 1.0)))
    setattr(
        node,
        "light_cone_degrees",
        float(getattr(light, "cone_angle_degrees", metadata.get("cone_angle", 45.0)) or 45.0),
    )
    setattr(node, "light_area_size", float(metadata.get("area_size", 1.0) or 1.0))
    setattr(node, "light_ambient_only", light_type == "ambient")
    setattr(node, "light_shadow", bool(getattr(light, "casts_shadows", metadata.get("casts_shadows", True))))
    affects_diffuse = bool(getattr(light, "affects_diffuse", metadata.get("affects_diffuse", True)))
    setattr(node, "light_affects_diffuse", affects_diffuse)
    setattr(node, "light_affects_specular", affects_diffuse)
    setattr(node, "light_affects_lightmap", bool(getattr(light, "affects_lightmap", metadata.get("affects_lightmap", True))))
    setattr(node, "light_affects_environment", True)
    setattr(node, "_gr_light_group_id", str(getattr(light, "bake_group", "") or ""))
    node.rotation = _light_direction_quaternion(getattr(light, "direction", (0.0, 0.0, -1.0)))
    return node


def _source_room_light_node(md, row: dict[str, object], room_node, room_resref: str, index: int):
    """Rebuild one hidden-helper vanilla light for editor/PIE shading only."""

    try:
        source_index = int(row.get("source_node_index", index) or index)
    except (TypeError, ValueError):
        source_index = index
    source_name = str(row.get("source_node_name") or f"{room_resref}_source_light_{index + 1}")
    node = md.ModelNode(
        name=source_name,
        flags=int(md.NodeFlags.LIGHT),
        position=_vec3(row.get("position", (0.0, 0.0, 0.0))),
    )
    node.parent = room_node
    orientation = tuple(row.get("orientation", (0.0, 0.0, 0.0, 1.0)) or ())
    try:
        orientation = tuple(float(value) for value in orientation[:4])
    except (TypeError, ValueError):
        orientation = ()
    node.rotation = orientation if len(orientation) == 4 else (0.0, 0.0, 0.0, 1.0)
    setattr(node, "_gr_map_studio_source_room_light", True)
    setattr(node, "_gr_light_helper_hidden", True)
    setattr(node, "_gr_light_id", f"stock_room_light:{room_resref}:{source_index}:{source_name}")
    setattr(
        node,
        "_gr_light_metadata",
        {
            "preview_only": True,
            "source": "stock_room_runtime_graph",
            "room_resref": room_resref,
            "source_node_index": source_index,
            "source_dynamic_type": int(row.get("dynamic_type", 0) or 0),
            "runtime_graph_preserved": False,
        },
    )
    setattr(node, "source_type", "MapStudioStockRoomLightPreview")
    setattr(node, "light_kind", str(row.get("kind") or "point"))
    setattr(node, "light_enabled", bool(row.get("enabled", True)))
    setattr(node, "light_color", _vec3(row.get("color", (1.0, 1.0, 1.0))))
    setattr(node, "light_radius", max(0.001, float(row.get("radius", 5.0) or 5.0)))
    setattr(node, "light_multiplier", max(0.0, float(row.get("multiplier", 1.0) or 1.0)))
    setattr(node, "light_ambient_only", bool(row.get("ambient_only", False)))
    setattr(node, "light_dynamic", int(row.get("dynamic_type", 0) or 0))
    setattr(node, "light_shadow", bool(row.get("shadow", False)))
    setattr(node, "light_flare", bool(row.get("flare", False)))
    setattr(node, "light_fading", bool(row.get("fading", False)))
    return node


def _light_direction_quaternion(direction: object) -> tuple[float, float, float, float]:
    """Rotate the renderer's local -Z light axis onto a room-space direction."""

    target = _vec3(direction)
    length = math.sqrt(sum(float(value) * float(value) for value in target))
    if length <= 1.0e-9:
        return (0.0, 0.0, 0.0, 1.0)
    x, y, z = (float(value) / length for value in target)
    dot = max(-1.0, min(1.0, -z))
    if dot >= 1.0 - 1.0e-9:
        return (0.0, 0.0, 0.0, 1.0)
    if dot <= -1.0 + 1.0e-9:
        return (1.0, 0.0, 0.0, 0.0)
    qx, qy, qz, qw = (y, -x, 0.0, 1.0 + dot)
    qlen = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw) or 1.0
    return (qx / qlen, qy / qlen, qz / qlen, qw / qlen)


def _preview_rgb(value: object, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return one normalized ARE RGB triplet for renderer preview state."""

    try:
        channels = tuple(value)[:3]  # type: ignore[arg-type]
        if len(channels) < 3:
            raise ValueError
        return tuple(max(0, min(255, int(channel))) for channel in channels)  # type: ignore[return-value]
    except Exception:
        return fallback


def _world_lighting_preview_state(project: AuthoredModuleProject) -> dict[str, object]:
    """Adapt authored ARE colors to an explicitly approximate viewport rig.

    Odyssey applies these fields differently to static, dynamic, and baked
    geometry.  Imported room surfaces already take the baked-lightmap branch,
    so the remaining scene-lit meshes are predominantly dynamic actors and
    must use ``DynAmbientColor`` without averaging it down against
    ``SunAmbientColor``.  A fixed downward editor sun remains an approximation;
    fog and sun-shadow controls remain ARE/export-only and are called out as
    unsupported in the state consumed by the UI.
    """

    settings = authored_world_lighting_settings(project)
    sun_ambient = _preview_rgb(settings.get("sun_ambient"), (64, 64, 64))
    sun_diffuse = _preview_rgb(settings.get("sun_diffuse"), (255, 255, 255))
    dynamic_ambient = _preview_rgb(settings.get("dynamic_ambient"), sun_ambient)
    area = authored_area_metadata(project.metadata, None)
    dynamic_ambient_rgb = tuple(float(channel) / 255.0 for channel in dynamic_ambient)
    diffuse_headroom = max(0.0, 1.0 - max(dynamic_ambient_rgb))
    # Read the persisted ARE field directly as well as the normalized helper.
    # This keeps a just-applied kit preset visible even when a caller still
    # holds an earlier world-lighting settings cache for the project.
    fog_enabled = bool(getattr(area, "sun_fog_on", settings.get("fog_enabled")))
    fog_color = _preview_rgb(getattr(area, "fog_color", settings.get("fog_color")), (0, 0, 0))
    fog_near = max(0.0, float(getattr(area, "fog_near", settings.get("fog_near", 0.0)) or 0.0))
    fog_far = max(fog_near, float(getattr(area, "fog_far", settings.get("fog_far", 0.0)) or 0.0))
    # A 70 m retail exterior range is appropriate in-game but almost invisible
    # in a compact Map Studio view.  Keep the ARE values verbatim for export,
    # while its preview lens shortens only the displayed range so artists can
    # actually read the atmosphere before game testing.
    fog_preview_far = max(fog_near + 0.001, min(fog_far, fog_near + (fog_far - fog_near) * 0.55))
    fog_preview_color = tuple(float(channel) / 255.0 for channel in fog_color)
    area_payload = dict(getattr(project.metadata, "metadata", {}) or {}).get("area") or {}
    shadowlands_mist = str(dict(area_payload).get("environment_style_preset") or "").strip().lower() == "architecture:k1_shadowlands"
    if shadowlands_mist:
        # The raw Shadowlands fog color is intentionally near-black in the
        # ARE, where it mixes over a full 70 m exterior.  A compact editor
        # clearing needs a shorter lens and a small cool lift to read as mist
        # rather than as unlit terrain.  This is preview-only; the ARE still
        # serializes the measured raw color/range unchanged.
        fog_preview_far = max(fog_near + 0.001, min(fog_far, fog_near + (fog_far - fog_near) * 0.30))
        fog_preview_color = (0.20, 0.24, 0.27)
    grass_texture = str(getattr(area, "grass_texture", "") or "").strip().lower()
    grass_density = max(0.0, float(getattr(area, "grass_density", 0.0) or 0.0))
    grass_quad_size = max(0.0, float(getattr(area, "grass_quad_size", 0.0) or 0.0))
    return {
        "schema": "ghostrigger.map_studio_world_lighting_preview.v1",
        "profile": str(settings.get("profile") or "standard"),
        "sun_ambient": list(sun_ambient),
        "sun_diffuse": list(sun_diffuse),
        "dynamic_ambient": list(dynamic_ambient),
        # Keep the original key for project/UI compatibility.  Its value now
        # follows Odyssey's dynamic-object ambient channel instead of an
        # editor-authored average that halved 207TEL's (45, 43, 34) ambient.
        "ambient_blend_rgb": [round(channel, 7) for channel in dynamic_ambient_rgb],
        "dynamic_ambient_rgb": [round(channel, 7) for channel in dynamic_ambient_rgb],
        "ambient_preview_source": "dynamic_ambient",
        "sun_diffuse_rgb": [round(float(channel) / 255.0, 7) for channel in sun_diffuse],
        "sun_diffuse_intensity": round(diffuse_headroom, 7),
        "sun_direction": [0.0, 0.0, -1.0],
        "preview_scope": "non_lightmapped_scene_surfaces",
        "preserves_baked_lightmaps": True,
        # These remain renderer-preview approximations—the ARE stays the
        # authoritative export—but a Map Studio exterior must no longer look
        # like bare mud until the module is launched in the game.
        "fog_previewed": fog_enabled,
        "fog_enabled": fog_enabled,
        "fog_color_rgb": [round(float(channel) / 255.0, 7) for channel in fog_color],
        "fog_preview_color_rgb": [round(float(channel), 7) for channel in fog_preview_color],
        "fog_near": fog_near,
        "fog_far": fog_far,
        "fog_preview_near": fog_near,
        "fog_preview_far": fog_preview_far,
        "fog_preview_calibration": "shadowlands_mist_lens" if shadowlands_mist else "compact_map_studio_view",
        "grass_previewed": bool(grass_texture and grass_density > 0.0 and grass_quad_size > 0.0),
        "grass_texture": grass_texture,
        "grass_density": grass_density,
        "grass_quad_size": grass_quad_size,
        "sun_shadows_previewed": False,
        "preview_only": True,
    }


def _preview_hash(value: int) -> float:
    """Return a deterministic pseudo-random value without scene RNG state."""

    value = (int(value) ^ 0x9E3779B9) & 0xFFFFFFFF
    value = (value ^ (value >> 16)) * 0x85EBCA6B & 0xFFFFFFFF
    value = (value ^ (value >> 13)) * 0xC2B2AE35 & 0xFFFFFFFF
    return float((value ^ (value >> 16)) & 0xFFFFFFFF) / float(0xFFFFFFFF)


def _shadowlands_grass_preview_mesh(
    geometry: Any,
    *,
    room_resref: str,
    state: dict[str, object],
) -> PrimitiveMesh | None:
    """Generate a lightweight, non-exporting grass-card preview over the WOK.

    ``lka_grass`` is an Odyssey ARE grass field, not a regular TGA/TPC texture
    that can be placed on an isolated model card.  Reusing it as a diffuser is
    what produces white shards.  The editor therefore previews the ARE field
    as sparse crossed blade clusters on walkable WOK triangles.  Export keeps
    the retail ARE values verbatim; this mesh exists only in the live authoring
    model and is deliberately never serialized into the module.
    """

    if not bool(state.get("grass_previewed")):
        return None
    wok = getattr(geometry, "wok", None)
    vertices_source = tuple(getattr(wok, "verts", ()) or ())
    faces_source = tuple(getattr(wok, "faces", ()) or ())
    if len(vertices_source) < 3 or not faces_source:
        return None
    try:
        from .module_format import WALKABLE_IDS
    except ImportError:
        from core.modules.module_format import WALKABLE_IDS  # type: ignore

    vertices: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    uvs: list[tuple[float, float]] = []
    quad_size = max(0.45, min(1.20, float(state.get("grass_quad_size", 0.8) or 0.8)))
    # Retail density is a grass-system setting, not a blades-per-square-metre
    # value.  This bounded conversion gives a readable authoring preview while
    # keeping sculpting/placement responsive on large WOKs.
    density_scale = max(0.16, min(0.55, float(state.get("grass_density", 5.0) or 5.0) * 0.07))

    def append_blade(x: float, y: float, z: float, angle: float, height: float, width: float) -> None:
        dx = math.cos(angle) * width
        dy = math.sin(angle) * width
        # Give the tip a slight lean so every cluster has the loose, natural
        # silhouette of the K1 grass field instead of vertical pickets.
        tip_x = x + math.cos(angle + 0.85) * width * 0.42
        tip_y = y + math.sin(angle + 0.85) * width * 0.42
        start = len(vertices)
        triangle = ((x - dx, y - dy, z), (x + dx, y + dy, z), (tip_x, tip_y, z + height))
        vertices.extend(triangle)
        normals.extend(((0.0, 0.0, 1.0),) * 3)
        uvs.extend(((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)))
        # Double-sided blade cards: Map Studio retains back-face culling for
        # KOTOR winding, so grass needs both windings to read from any camera.
        faces.extend(((start, start + 1, start + 2), (start + 2, start + 1, start)))

    room_seed = sum((index + 1) * ord(character) for index, character in enumerate(room_resref))
    for face_index, face in enumerate(faces_source):
        if int(getattr(face, "surface", 0) or 0) not in WALKABLE_IDS:
            continue
        try:
            a = tuple(float(value) for value in vertices_source[int(face.v1)][:3])
            b = tuple(float(value) for value in vertices_source[int(face.v2)][:3])
            c = tuple(float(value) for value in vertices_source[int(face.v3)][:3])
        except (AttributeError, IndexError, TypeError, ValueError):
            continue
        area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5
        cluster_count = max(1, min(72, int(math.ceil(area * density_scale))))
        for cluster_index in range(cluster_count):
            seed = room_seed + face_index * 4099 + cluster_index * 37
            root_u = math.sqrt(_preview_hash(seed))
            root_v = _preview_hash(seed + 1)
            wa = 1.0 - root_u
            wb = root_u * (1.0 - root_v)
            wc = root_u * root_v
            x = a[0] * wa + b[0] * wb + c[0] * wc
            y = a[1] * wa + b[1] * wb + c[1] * wc
            z = a[2] * wa + b[2] * wb + c[2] * wc + 0.018
            for blade_index in range(3):
                variance = _preview_hash(seed + 7 + blade_index * 5)
                append_blade(
                    x,
                    y,
                    z,
                    angle=(variance + blade_index / 3.0) * math.tau,
                    height=quad_size * (0.58 + _preview_hash(seed + 13 + blade_index) * 0.58),
                    width=quad_size * (0.032 + _preview_hash(seed + 17 + blade_index) * 0.026),
                )
    if not faces:
        return None
    return PrimitiveMesh(
        name=f"{room_resref}_shadowlands_grass_preview",
        vertices=tuple(vertices),
        faces=tuple(faces),
        normals=tuple(normals),
        uvs=tuple(uvs),
        diffuse=(0.12, 0.18, 0.095),
        ambient=(0.32, 0.38, 0.22),
        metadata={
            "primitive": "map_studio_shadowlands_grass_preview",
            "editor_preview_only": True,
            "source_are_grass_texture": str(state.get("grass_texture") or "lka_grass"),
            "source_are_grass_density": float(state.get("grass_density", 0.0) or 0.0),
            "blade_cluster_count": len(faces) // 6,
            "selfillum": (0.055, 0.075, 0.035),
        },
    )


def _world_lighting_preview_nodes(md: Any, root: Any, state: dict[str, object]) -> tuple[Any, Any]:
    """Build hidden-helper LIGHT nodes used by every GPU viewport backend."""

    ambient = md.ModelNode(
        name="_gr_world_ambient_preview",
        flags=int(md.NodeFlags.LIGHT),
    )
    ambient.parent = root
    ambient.light_kind = "directional"
    ambient.light_enabled = True
    ambient.light_ambient_only = True
    ambient.light_color = _vec3(state.get("ambient_blend_rgb", (0.25, 0.25, 0.25)))
    ambient.light_multiplier = 1.0
    ambient.light_radius = 1_000_000.0
    ambient.light_shadow = False

    sun = md.ModelNode(
        name="_gr_world_sun_preview",
        flags=int(md.NodeFlags.LIGHT),
    )
    sun.parent = root
    sun.light_kind = "directional"
    sun.light_enabled = float(state.get("sun_diffuse_intensity", 0.0) or 0.0) > 1.0e-7
    sun.light_ambient_only = False
    sun.light_color = _vec3(state.get("sun_diffuse_rgb", (1.0, 1.0, 1.0)))
    sun.light_multiplier = float(state.get("sun_diffuse_intensity", 0.0) or 0.0)
    sun.light_radius = 1_000_000.0
    sun.light_shadow = False

    for node, channel in ((ambient, "ambient_blend"), (sun, "sun_diffuse")):
        setattr(node, "_gr_map_studio_world_light", True)
        setattr(node, "_gr_light_helper_hidden", True)
        setattr(node, "_gr_light_id", f"map_studio_world_preview:{channel}")
        setattr(
            node,
            "_gr_light_metadata",
            {
                "preview_only": True,
                "world_channel": channel,
                "fog_previewed": False,
                "sun_shadows_previewed": False,
            },
        )
        setattr(node, "source_type", "MapStudioWorldPreview")
        setattr(node, "light_fading", False)
    return ambient, sun


def build_authored_module_preview_model(
    project: AuthoredModuleProject,
    *,
    include_backdrops: bool = False,
) -> AuthoredModulePreviewModelResult:
    """Compile authored KMAP room geometry into the viewport's normal KotorModel path."""

    md = _import_model_data()
    root = md.ModelNode(name=str(project.module_root or "map_studio_preview"), flags=int(md.NodeFlags.HEADER))
    world_lighting_preview = _world_lighting_preview_state(project)
    warnings: list[str] = []
    signature_rows: list[dict[str, object]] = []
    room_count = 0
    mesh_count = 0
    source_room_light_count = 0
    playable_points: list[tuple[float, float, float]] = []

    backdrop_room_resrefs: list[str] = []
    hidden_backdrop_surface_count = 0
    for room in tuple(project.rooms or ()):
        room_resref = str(room.room_resref or "room")
        room_metadata = dict(getattr(room, "metadata", {}) or {})
        if authored_room_uses_unresolved_stock_geometry(room):
            warnings.append(
                f"Room {room_resref} has no resolved stock model; its import placeholder was excluded from preview."
            )
            continue
        try:
            geometry = compile_authored_room_spec(room)
        except Exception as exc:
            warnings.append(f"Room {room_resref} could not compile for preview: {exc}")
            continue
        meshes = (geometry.room_mesh,) + tuple(geometry.helper_meshes or ())
        meshes = tuple(mesh for mesh in meshes if mesh.vertices and mesh.faces)
        if not meshes:
            warnings.append(f"Room {room_resref} has no previewable render mesh.")
            continue

        declared_room_backdrop = bool(room_metadata.get("backdrop_only") or room_metadata.get("is_backdrop"))
        mesh_rows: list[tuple[int, PrimitiveMesh, bool]] = []
        for index, mesh in enumerate(meshes):
            mesh_metadata = dict(getattr(mesh, "metadata", {}) or {})
            surface_backdrop = bool(mesh_metadata.get("is_backdrop", declared_room_backdrop))
            mesh_rows.append((index, mesh, surface_backdrop))
        room_backdrop_only = bool(room_metadata.get("backdrop_only")) or (
            declared_room_backdrop and all(row[2] for row in mesh_rows)
        )
        visible_mesh_rows = [row for row in mesh_rows if include_backdrops or not row[2]]
        hidden_backdrop_surface_count += sum(1 for row in mesh_rows if row[2] and not include_backdrops)
        if not visible_mesh_rows:
            backdrop_room_resrefs.append(room_resref)
            continue

        compiled_resref = str(geometry.room_resref or room_resref)
        room_node = md.ModelNode(
            name=compiled_resref,
            flags=int(md.NodeFlags.HEADER),
            position=_vec3(room.position),
        )
        room_node.parent = root
        setattr(room_node, "_gr_map_studio_room_resref", compiled_resref)
        setattr(room_node, "_gr_map_studio_authored_room", True)
        setattr(room_node, "_gr_map_studio_backdrop", room_backdrop_only)
        for index, mesh, surface_backdrop in visible_mesh_rows:
            role = "render" if index == 0 else str(getattr(mesh, "metadata", {}).get("role", "") or f"helper_{index}")
            mesh_node = _mesh_node(md, mesh, room_node, room_resref=compiled_resref, role=role)
            setattr(mesh_node, "_gr_map_studio_backdrop", surface_backdrop)
            room_node.children.append(mesh_node)
            mesh_count += 1
        grass_preview = _shadowlands_grass_preview_mesh(
            geometry,
            room_resref=compiled_resref,
            state=world_lighting_preview,
        )
        if grass_preview is not None:
            grass_node = _mesh_node(
                md,
                grass_preview,
                room_node,
                room_resref=compiled_resref,
                role="shadowlands_grass_preview",
            )
            grass_node.selfillum = tuple(grass_preview.metadata["selfillum"])
            setattr(grass_node, "_gr_map_studio_editor_preview_only", True)
            room_node.children.append(grass_node)
            mesh_count += 1
        for light_index, light_row in enumerate(_source_room_light_rows(room)):
            try:
                room_node.children.append(
                    _source_room_light_node(md, light_row, room_node, compiled_resref, light_index)
                )
                source_room_light_count += 1
            except Exception as exc:
                warnings.append(
                    f"Stock room light {light_row.get('source_node_name', light_index + 1)} in {compiled_resref} "
                    f"could not preview: {exc}"
                )
        root.children.append(room_node)
        room_count += 1
        signature_rows.append(_room_signature(room, meshes))
        room_offset = _vec3(room.position)
        playable_points.extend(
            (
                float(vertex[0]) + room_offset[0],
                float(vertex[1]) + room_offset[1],
                float(vertex[2]) + room_offset[2],
            )
            for _index, mesh, surface_backdrop in mesh_rows
            if not surface_backdrop
            for vertex in tuple(mesh.vertices or ())
        )

    if hidden_backdrop_surface_count and not include_backdrops:
        room_summary = f" ({', '.join(backdrop_room_resrefs)})" if backdrop_room_resrefs else ""
        warnings.append(
            f"Hid {hidden_backdrop_surface_count} skybox/backdrop surface(s) from the edit view"
            f"{room_summary}; they still export and render in-game."
        )

    world_light_nodes = _world_lighting_preview_nodes(md, root, world_lighting_preview)
    root.children.extend(world_light_nodes)

    light_count = 0
    for light in tuple(getattr(project, "lights", ()) or ()):
        try:
            root.children.append(_light_node(md, light, root))
            light_count += 1
        except Exception as exc:
            warnings.append(f"Authored light {getattr(light, 'name', 'room_light')} could not preview: {exc}")

    if mesh_count <= 0:
        return AuthoredModulePreviewModelResult(model=None, room_count=room_count, mesh_count=0, warnings=tuple(warnings))

    model = md.KotorModel(
        name=str(project.module_root or "map_studio_preview"),
        supermodel="NULL",
        classification="area",
        game_version=md.GameVersion.K2 if str(project.game).upper() == "K2" else md.GameVersion.K1,
        model_type=int(md.ModelClassification.EFFECT),
        root_node=root,
    )
    model.disable_fog = not bool(world_lighting_preview.get("fog_previewed"))
    try:
        model.compute_all_tangents()
    except Exception:
        pass
    model.compute_bounds()
    if playable_points:
        minimum = tuple(min(point[axis] for point in playable_points) for axis in range(3))
        maximum = tuple(max(point[axis] for point in playable_points) for axis in range(3))
        setattr(model, "_gr_bounds_prepared", True)
        setattr(model, "_gr_render_bounds", (minimum, maximum))
    signature_rows.append(
        {
            "include_backdrops": bool(include_backdrops),
            "world_lighting_preview": world_lighting_preview,
            "lights": [
                {
                    "name": str(getattr(light, "name", "") or ""),
                    "position": _round_tuple(_vec3(getattr(light, "position", (0.0, 0.0, 0.0)))),
                    "color": _round_tuple(_vec3(getattr(light, "color", (1.0, 1.0, 1.0)))),
                    "radius": round(float(getattr(light, "radius", 0.0) or 0.0), 6),
                    "intensity": round(float(getattr(light, "intensity", 0.0) or 0.0), 6),
                    "type": str(getattr(light, "light_type", "point") or "point"),
                }
                for light in tuple(getattr(project, "lights", ()) or ())
            ],
        }
    )
    key = _preview_key(signature_rows)
    setattr(model, "_gr_map_studio_preview_model", True)
    setattr(model, "_gr_map_studio_preview_key", key)
    setattr(model, "_gr_map_studio_world_lighting_preview", dict(world_lighting_preview))
    setattr(
        model,
        "_gr_map_studio_preview_summary",
        {
            "rooms": room_count,
            "meshes": mesh_count,
            "lights": light_count,
            "source_room_lights": source_room_light_count,
            "world_preview_lights": len(world_light_nodes),
            "warnings": tuple(warnings),
        },
    )
    return AuthoredModulePreviewModelResult(model=model, room_count=room_count, mesh_count=mesh_count, warnings=tuple(warnings))
