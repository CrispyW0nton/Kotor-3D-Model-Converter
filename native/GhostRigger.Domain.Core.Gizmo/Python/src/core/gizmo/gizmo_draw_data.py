"""Renderer-neutral transform gizmo draw commands."""

from __future__ import annotations

from dataclasses import dataclass, field


Vec3 = tuple[float, float, float]
Color = tuple[float, float, float, float]


@dataclass(frozen=True)
class GizmoDrawCommand:
    kind: str
    points: tuple[Vec3, ...] = ()
    colour: Color = (1.0, 1.0, 1.0, 1.0)
    thickness: float = 1.0
    depth_mode: str = "overlay"
    screen_space: bool = False
    world_space: bool = True
    pick_id: str = ""
    label: str = ""


@dataclass(frozen=True)
class GizmoRenderData:
    origin: Vec3 = (0.0, 0.0, 0.0)
    orientation: object | None = None
    scale: float = 1.0
    active_tool: str = ""
    active_axis: str | None = None
    hover_axis: str | None = None
    axis_mode: str = "world"
    commands: tuple[GizmoDrawCommand, ...] = field(default_factory=tuple)
    handle_count: int = 0


def rgba255_to_float(color) -> Color:
    r, g, b, *rest = tuple(color)
    a = rest[0] if rest else 255
    return (
        max(0.0, min(1.0, float(r) / 255.0)),
        max(0.0, min(1.0, float(g) / 255.0)),
        max(0.0, min(1.0, float(b) / 255.0)),
        max(0.0, min(1.0, float(a) / 255.0)),
    )
