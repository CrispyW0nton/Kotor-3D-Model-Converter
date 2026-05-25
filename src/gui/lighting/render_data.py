"""Renderer-neutral lighting snapshots for viewport backends."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .light_gizmo_renderer import (
    LIGHT_HELPER_AREA_SIZE,
    LIGHT_HELPER_COLORS,
    LIGHT_HELPER_DIRECTION_LENGTH,
    LIGHT_HELPER_MARKER_RADIUS,
    LIGHT_HELPER_POINT_RADIUS,
    LIGHT_HELPER_SELECTED_BOOST,
    LIGHT_HELPER_SPOT_CAP_MAX_RADIUS,
    LIGHT_HELPER_SPOT_LENGTH,
)

Vec3 = tuple[float, float, float]
Color = tuple[float, float, float]


@dataclass(frozen=True)
class SceneLightRenderData:
    light_id: int
    node_id: str
    name: str
    enabled: bool
    light_type: str
    position: Vec3
    direction: Vec3
    color_rgb: Color
    intensity: float
    radius: float
    cone_angle_degrees: float
    area_size: float
    ambient_only: bool
    cast_shadows: bool
    group: str
    selected: bool
    hovered: bool
    visible: bool
    revision: int
    original_ref: object | None = field(default=None, compare=False)


@dataclass(frozen=True)
class SceneLightingRenderData:
    lights: tuple[SceneLightRenderData, ...] = ()
    ambient_color_rgb: Color = (0.06, 0.06, 0.06)
    global_intensity: float = 1.0
    mode: str = "scene"
    rig: str = "kotor_original"
    complexity: str = "basic"
    show_helpers: bool = True
    show_volumes: bool = False
    diffuse_enabled: bool = True
    specular_enabled: bool = True
    normal_enabled: bool = True
    environment_enabled: bool = True
    lightmap_enabled: bool = True
    lm_intensity: float = 0.55
    lm_mode: str = "baked"
    revision: int = 0

    @property
    def enabled_lights(self) -> tuple[SceneLightRenderData, ...]:
        return tuple(light for light in self.lights if light.enabled and light.visible)


def build_scene_lighting_render_data(
    model: object | None,
    *,
    selected_node: object | None = None,
    hovered_node: object | None = None,
    ambient_color_rgb: Color | float = (0.06, 0.06, 0.06),
    global_intensity: float = 1.0,
    mode: str = "scene",
    rig: str = "kotor_original",
    complexity: str = "basic",
    show_helpers: bool = True,
    show_volumes: bool = False,
    diffuse_enabled: bool = True,
    specular_enabled: bool = True,
    normal_enabled: bool = True,
    environment_enabled: bool = True,
    lightmap_enabled: bool = True,
    lm_intensity: float = 0.55,
    lm_mode: str = "baked",
) -> SceneLightingRenderData:
    lights = tuple(
        _light_from_node(node, index, selected_node=selected_node, hovered_node=hovered_node)
        for index, node in enumerate(_light_nodes(model), start=1)
    )
    revision = _lighting_revision(
        lights,
        mode,
        rig,
        complexity,
        show_helpers,
        show_volumes,
        diffuse_enabled,
        specular_enabled,
        normal_enabled,
        environment_enabled,
        lightmap_enabled,
        lm_intensity,
        lm_mode,
        global_intensity,
        _ambient_tuple(ambient_color_rgb),
    )
    return SceneLightingRenderData(
        lights=lights,
        ambient_color_rgb=_ambient_tuple(ambient_color_rgb),
        global_intensity=max(0.0, float(global_intensity)),
        mode=str(mode or "scene").strip().lower(),
        rig=str(rig or "kotor_original").strip().lower(),
        complexity=str(complexity or "basic").strip().lower(),
        show_helpers=bool(show_helpers),
        show_volumes=bool(show_volumes),
        diffuse_enabled=bool(diffuse_enabled),
        specular_enabled=bool(specular_enabled),
        normal_enabled=bool(normal_enabled),
        environment_enabled=bool(environment_enabled),
        lightmap_enabled=bool(lightmap_enabled),
        lm_intensity=max(0.0, float(lm_intensity)),
        lm_mode=str(lm_mode or "baked").strip().lower(),
        revision=revision,
    )


def light_kind_int(light_type: str) -> int:
    kind = str(light_type or "point").strip().lower().replace("aurora_", "")
    if kind == "directional":
        return 1
    if kind == "spot":
        return 2
    if kind == "area":
        return 3
    if kind == "ambient":
        return 4
    return 0


def build_light_helper_line_batches(lighting: SceneLightingRenderData | None) -> list[tuple[Color, list[Vec3]]]:
    if lighting is None or not lighting.show_helpers:
        return []
    batches: dict[tuple[float, float, float], list[Vec3]] = {}
    for light in lighting.lights:
        if not light.visible:
            continue
        color = _helper_color(light)
        vertices = _marker_lines(light)
        if not vertices:
            continue
        batches.setdefault(color, []).extend(vertices)
    return [(color, vertices) for color, vertices in batches.items() if vertices]


def build_light_volume_line_batches(lighting: SceneLightingRenderData | None) -> list[tuple[Color, list[Vec3]]]:
    if lighting is None or not lighting.show_helpers or not lighting.show_volumes:
        return []
    batches: dict[tuple[float, float, float], list[Vec3]] = {}
    for light in lighting.lights:
        if not light.visible:
            continue
        color = _helper_color(light)
        vertices = _volume_lines(light)
        if not vertices:
            continue
        batches.setdefault(color, []).extend(vertices)
    return [(color, vertices) for color, vertices in batches.items() if vertices]


def _light_nodes(model: object | None) -> Iterable[object]:
    if model is None or not hasattr(model, "all_nodes"):
        return ()
    try:
        nodes = list(model.all_nodes())
    except Exception:
        return ()
    return tuple(node for node in nodes if bool(getattr(node, "is_light", False)))


def _light_from_node(
    node: object,
    index: int,
    *,
    selected_node: object | None,
    hovered_node: object | None,
) -> SceneLightRenderData:
    try:
        world_pos, world_orient = node.world_transform()
    except Exception:
        world_pos = getattr(node, "position", (0.0, 0.0, 0.0))
        world_orient = getattr(node, "rotation", (0.0, 0.0, 0.0, 1.0))
    light_type = str(getattr(node, "light_kind", "point") or "point").strip().lower()
    if light_type == "point" and str(getattr(node, "name", "") or "").lower().startswith("auroralight"):
        light_type = "aurora_point"
    ambient_only = bool(getattr(node, "light_ambient_only", False))
    if ambient_only and light_type in {"point", "aurora_point"}:
        light_type = "aurora_ambient"
    selected = bool(
        node is selected_node
        or bool(getattr(node, "_gr_light_selected", False))
        or bool(getattr(node, "_gr_light_metadata", {}).get("active_selection", False))
    )
    return SceneLightRenderData(
        light_id=index,
        node_id=str(getattr(node, "_gr_light_id", "") or id(node)),
        name=str(getattr(node, "name", "") or f"Light {index}"),
        enabled=bool(getattr(node, "light_enabled", True)) and not bool(getattr(node, "_gr_light_deleted", False)),
        light_type=light_type,
        position=_vec3(world_pos),
        direction=_rotate_vec_by_quat((0.0, 0.0, -1.0), _quat(world_orient)),
        color_rgb=_color(getattr(node, "light_color", (1.0, 1.0, 1.0))),
        intensity=max(0.0, float(getattr(node, "light_multiplier", 1.0) or 0.0)),
        radius=max(0.001, float(getattr(node, "light_radius", 5.0) or 0.0)),
        cone_angle_degrees=max(1.0, min(179.0, float(getattr(node, "light_cone_degrees", 45.0) or 45.0))),
        area_size=max(0.0, float(getattr(node, "light_area_size", 1.0) or 0.0)),
        ambient_only=ambient_only,
        cast_shadows=bool(getattr(node, "light_shadow", True)),
        group=str(getattr(node, "_gr_light_group_id", "") or ""),
        selected=selected,
        hovered=node is hovered_node,
        visible=not bool(getattr(node, "_gr_light_hidden", False)) and not bool(getattr(node, "_gr_light_deleted", False)),
        revision=int(getattr(node, "_gr_light_revision", 0) or 0),
        original_ref=node,
    )


def _lighting_revision(lights: tuple[SceneLightRenderData, ...], *settings: object) -> int:
    light_values = tuple(
        (
            light.node_id,
            light.enabled,
            light.visible,
            light.selected,
            light.light_type,
            tuple(round(v, 5) for v in light.position),
            tuple(round(v, 5) for v in light.direction),
            tuple(round(v, 5) for v in light.color_rgb),
            round(light.intensity, 5),
            round(light.radius, 5),
            round(light.cone_angle_degrees, 5),
            round(light.area_size, 5),
            light.ambient_only,
            light.cast_shadows,
            light.group,
            light.revision,
        )
        for light in lights
    )
    return hash((light_values, settings)) & 0x7FFFFFFF


def _ambient_tuple(value: Color | float) -> Color:
    if isinstance(value, (int, float)):
        ambient = max(0.0, float(value))
        return (ambient, ambient, ambient)
    return _color(value, fallback=(0.06, 0.06, 0.06))


def _vec3(value: object, fallback: Vec3 = (0.0, 0.0, 0.0)) -> Vec3:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    except Exception:
        return fallback


def _quat(value: object) -> tuple[float, float, float, float]:
    try:
        seq = list(value)  # type: ignore[arg-type]
        return (float(seq[0]), float(seq[1]), float(seq[2]), float(seq[3]))
    except Exception:
        return (0.0, 0.0, 0.0, 1.0)


def _color(value: object, fallback: Color = (1.0, 1.0, 1.0)) -> Color:
    raw = _vec3(value, fallback)
    return tuple(max(0.0, min(1.0, float(c))) for c in raw[:3])  # type: ignore[return-value]


def _rotate_vec_by_quat(v: Vec3, q: tuple[float, float, float, float]) -> Vec3:
    try:
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        qx, qy, qz, qw = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        tx = 2.0 * (qy * z - qz * y)
        ty = 2.0 * (qz * x - qx * z)
        tz = 2.0 * (qx * y - qy * x)
        rx = x + qw * tx + (qy * tz - qz * ty)
        ry = y + qw * ty + (qz * tx - qx * tz)
        rz = z + qw * tz + (qx * ty - qy * tx)
        length = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        return (rx / length, ry / length, rz / length)
    except Exception:
        return (0.0, 0.0, -1.0)


def _helper_color(light: SceneLightRenderData) -> Color:
    helper_kind = light.light_type.replace("aurora_", "")
    base = LIGHT_HELPER_COLORS.get(helper_kind, LIGHT_HELPER_COLORS["point"])
    color = tuple(max(0.0, min(1.0, float(base[i]) * max(0.25, light.color_rgb[i]))) for i in range(3))
    if not light.enabled:
        color = tuple(c * 0.38 for c in color)
    if light.selected or light.hovered:
        color = tuple(min(1.0, c * LIGHT_HELPER_SELECTED_BOOST) for c in color)
    if light.selected:
        color = (0.90, 0.95, 1.0)
    return color  # type: ignore[return-value]


def _marker_lines(light: SceneLightRenderData) -> list[Vec3]:
    _forward, right, up = _basis(light.direction)
    return _ring(light.position, right, up, LIGHT_HELPER_MARKER_RADIUS, steps=16)


def _volume_lines(light: SceneLightRenderData) -> list[Vec3]:
    kind = light.light_type.replace("aurora_", "")
    if kind == "ambient":
        return []
    forward, right, up = _basis(light.direction)
    if kind == "directional":
        target = _v_add(light.position, _v_mul(forward, LIGHT_HELPER_DIRECTION_LENGTH))
        head = LIGHT_HELPER_DIRECTION_LENGTH * 0.22
        return [
            light.position,
            target,
            target,
            _v_add(_v_sub(target, _v_mul(forward, head)), _v_mul(right, head * 0.45)),
            target,
            _v_add(_v_sub(target, _v_mul(forward, head)), _v_mul(right, -head * 0.45)),
        ]
    if kind == "spot":
        length = min(max(light.radius, LIGHT_HELPER_SPOT_LENGTH), 500.0)
        cap_radius = min(math.tan(math.radians(light.cone_angle_degrees * 0.5)) * length, max(length, LIGHT_HELPER_SPOT_CAP_MAX_RADIUS))
        cap = _v_add(light.position, _v_mul(forward, length))
        rows = _ring(cap, right, up, cap_radius, steps=24)
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            edge = _v_add(cap, _v_add(_v_mul(right, cap_radius * sx), _v_mul(up, cap_radius * sy)))
            rows.extend((light.position, edge))
        return rows
    if kind == "area":
        half = max(LIGHT_HELPER_AREA_SIZE, light.area_size) * 0.5
        c0 = _v_add(light.position, _v_add(_v_mul(right, -half), _v_mul(up, -half)))
        c1 = _v_add(light.position, _v_add(_v_mul(right, half), _v_mul(up, -half)))
        c2 = _v_add(light.position, _v_add(_v_mul(right, half), _v_mul(up, half)))
        c3 = _v_add(light.position, _v_add(_v_mul(right, -half), _v_mul(up, half)))
        return [c0, c1, c1, c2, c2, c3, c3, c0]
    radius = max(LIGHT_HELPER_POINT_RADIUS, min(float(light.radius), 500.0))
    rows = _ring(light.position, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), radius, steps=36)
    rows.extend(_ring(light.position, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), radius, steps=36))
    rows.extend(_ring(light.position, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), radius, steps=36))
    return rows


def _ring(center: Vec3, axis_a: Vec3, axis_b: Vec3, radius: float, *, steps: int) -> list[Vec3]:
    rows: list[Vec3] = []
    prev: Vec3 | None = None
    for i in range(steps + 1):
        t = (i / steps) * math.tau
        point = _v_add(center, _v_add(_v_mul(axis_a, math.cos(t) * radius), _v_mul(axis_b, math.sin(t) * radius)))
        if prev is not None:
            rows.extend((prev, point))
        prev = point
    return rows


def _basis(direction: Vec3) -> tuple[Vec3, Vec3, Vec3]:
    forward = _v_norm(direction)
    seed = (0.0, 0.0, 1.0) if abs(forward[2]) < 0.92 else (0.0, 1.0, 0.0)
    right = _v_norm(_v_cross(seed, forward))
    up = _v_norm(_v_cross(forward, right))
    return forward, right, up


def _v_add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _v_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _v_mul(a: Vec3, scalar: float) -> Vec3:
    return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


def _v_cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _v_norm(a: Vec3) -> Vec3:
    length = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)

