"""Allocation-free topology budgets for retained Map Studio primitives.

Maya exposes a soft subdivision maximum of 50, but typed construction-history
values may exceed that guide.  Map Studio preserves the same distinction: this
module never clamps or rewrites a recipe.  It estimates the evaluated render
cost with integer arithmetic before any mesh lists/tuples are allocated, then
applies two separate policies:

* the interactive preview budget protects the 8.33 ms viewport target; a
  recipe above it remains valid and can be committed once with Apply;
* the absolute budget rejects only requests large enough to risk a long stall
  or Python-object-memory exhaustion during either preview or commit.

The limits are intentionally conservative.  On the 2026-07-14 Map Studio
fixture, a 10x10x10 cube evaluated in about 2 ms, 20x20x20 in about 9 ms,
25x25x25 in about 16 ms, and 100x100x100 in about 442 ms.  The preview budget
therefore stays close to the existing 8.33 ms viewport policy; the absolute
budget allows useful typed values well beyond Maya's soft 50 while bounding a
single synchronous Python evaluation to 500,000 modeled work entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .authored_room_primitives import (
    ArchPrimitive,
    ConePrimitive,
    CubePrimitive,
    CylinderPrimitive,
    DoorFramePrimitive,
    FloorPrimitive,
    RampPrimitive,
    SpherePrimitive,
    StairsPrimitive,
    TorusPrimitive,
    WallPrimitive,
)


MAYA_SUBDIVISION_SOFT_MAXIMUM = 50
PRIMITIVE_PREVIEW_MAX_WORK_UNITS = 8_000
PRIMITIVE_PREVIEW_MAX_ESTIMATED_BYTES = 1 * 1024 * 1024
PRIMITIVE_ABSOLUTE_MAX_WORK_UNITS = 500_000
PRIMITIVE_ABSOLUTE_MAX_ESTIMATED_BYTES = 256 * 1024 * 1024


class PrimitivePreviewDeferred(ValueError):
    """The retained recipe is valid but too costly for synchronous preview."""


class PrimitiveTopologySafetyError(ValueError):
    """The retained recipe exceeds the absolute pre-allocation safety budget."""


@dataclass(frozen=True)
class PrimitiveTopologyCost:
    """Allocation-free upper-bound estimate for one primitive evaluation."""

    primitive_kind: str
    render_vertices: int
    render_triangles: int
    work_units: int
    estimated_python_bytes: int
    supported: bool = True

    @property
    def preview_allowed(self) -> bool:
        return bool(
            self.supported
            and self.work_units <= PRIMITIVE_PREVIEW_MAX_WORK_UNITS
            and self.estimated_python_bytes <= PRIMITIVE_PREVIEW_MAX_ESTIMATED_BYTES
        )

    @property
    def absolute_allowed(self) -> bool:
        return bool(
            not self.supported
            or (
                self.work_units <= PRIMITIVE_ABSOLUTE_MAX_WORK_UNITS
                and self.estimated_python_bytes <= PRIMITIVE_ABSOLUTE_MAX_ESTIMATED_BYTES
            )
        )


def _base_primitive(primitive: Any) -> Any:
    """Unwrap a placed primitive without importing the composition module."""

    candidate = getattr(primitive, "primitive", None)
    return candidate if candidate is not None else primitive


def _positive_int(value: Any, minimum: int) -> int:
    """Mirror evaluator minimums without allocating topology."""

    return max(int(minimum), int(value))


def _cost(kind: str, vertices: int, triangles: int) -> PrimitiveTopologyCost:
    # Tuple/list-heavy Python mesh channels cost much more than their packed
    # GPU equivalents.  256 bytes per evaluated vertex and 96 per triangle is
    # a conservative, deterministic upper bound for positions, normals, UVs,
    # face tuples, list references, and allocator overhead.
    safe_vertices = max(0, int(vertices))
    safe_triangles = max(0, int(triangles))
    return PrimitiveTopologyCost(
        primitive_kind=kind,
        render_vertices=safe_vertices,
        render_triangles=safe_triangles,
        work_units=safe_vertices + safe_triangles,
        estimated_python_bytes=safe_vertices * 256 + safe_triangles * 96,
    )


def estimate_primitive_topology_cost(primitive: Any) -> PrimitiveTopologyCost:
    """Estimate a retained recipe before its mesh builder allocates arrays.

    Counts mirror the current deterministic render evaluators, including
    face-corner expansion for curved primitives.  Unknown/custom primitives
    are reported as unsupported and are not rejected by this policy because
    no truthful formula is available for them.
    """

    base = _base_primitive(primitive)
    if isinstance(base, FloorPrimitive):
        width = _positive_int(base.subdivisions_width, 1)
        depth = _positive_int(base.subdivisions_depth, 1)
        return _cost("plane", (width + 1) * (depth + 1), 2 * width * depth)
    if isinstance(base, CubePrimitive):
        x = _positive_int(base.subdivisions_x, 1)
        y = _positive_int(base.subdivisions_y, 1)
        z = _positive_int(base.subdivisions_z, 1)
        grid_cells = x * y + x * z + y * z
        vertices = 2 * ((x + 1) * (y + 1) + (x + 1) * (z + 1) + (y + 1) * (z + 1))
        return _cost("cube", vertices, 4 * grid_cells)
    if isinstance(base, CylinderPrimitive):
        axis = _positive_int(base.segments, 3)
        height = _positive_int(base.subdivisions_height, 1)
        caps = max(0, int(base.subdivisions_caps))
        side_triangles = 2 * axis * height
        cap_triangles = 2 * (axis - 2) if caps == 0 else 2 * axis * (2 * caps - 1)
        triangles = side_triangles + cap_triangles
        return _cost("cylinder", triangles * 3, triangles)
    if isinstance(base, SpherePrimitive):
        axis = _positive_int(base.subdivisions_axis, 3)
        height = _positive_int(base.subdivisions_height, 3)
        triangles = 2 * axis * (height - 1)
        return _cost("sphere", triangles * 3, triangles)
    if isinstance(base, ConePrimitive):
        axis = _positive_int(base.subdivisions_axis, 3)
        height = _positive_int(base.subdivisions_height, 1)
        caps = max(0, int(base.subdivisions_caps))
        side_triangles = axis * (2 * height - 1)
        cap_triangles = axis - 2 if caps == 0 else axis * (2 * caps - 1)
        triangles = side_triangles + cap_triangles
        return _cost("cone", triangles * 3, triangles)
    if isinstance(base, TorusPrimitive):
        axis = _positive_int(base.subdivisions_axis, 3)
        height = _positive_int(base.subdivisions_height, 3)
        triangles = 2 * axis * height
        return _cost("torus", triangles * 3, triangles)
    if isinstance(base, StairsPrimitive):
        steps = _positive_int(base.steps, 1)
        return _cost("stairs", 8 * steps, 12 * steps)
    if isinstance(base, ArchPrimitive):
        segments = _positive_int(base.segments, 4)
        return _cost("arch", 20 + 4 * segments, 28 + 8 * segments)
    if isinstance(base, DoorFramePrimitive):
        return _cost("door_frame", 24, 36)
    if isinstance(base, WallPrimitive):
        return _cost("wall", 24, 12)
    if isinstance(base, RampPrimitive):
        return _cost("ramp", 6, 9)
    return PrimitiveTopologyCost(
        primitive_kind=type(base).__name__,
        render_vertices=0,
        render_triangles=0,
        work_units=0,
        estimated_python_bytes=0,
        supported=False,
    )


def enforce_primitive_topology_budget(
    primitive: Any,
    *,
    operation: str,
) -> PrimitiveTopologyCost:
    """Validate preview/commit cost without modifying the retained recipe."""

    cost = estimate_primitive_topology_cost(primitive)
    if not cost.absolute_allowed:
        raise PrimitiveTopologySafetyError(
            "Construction request blocked before mesh allocation: "
            f"{cost.primitive_kind} estimates {cost.render_vertices:,} render vertices, "
            f"{cost.render_triangles:,} triangles, and {cost.work_units:,} work units; "
            f"the absolute safety budget is {PRIMITIVE_ABSOLUTE_MAX_WORK_UNITS:,} work units "
            f"and {PRIMITIVE_ABSOLUTE_MAX_ESTIMATED_BYTES // (1024 * 1024):,} MiB. "
            "Reduce subdivisions and Apply again. The retained recipe was not changed."
        )
    operation_key = str(operation or "").strip().lower()
    if operation_key == "preview" and not cost.preview_allowed:
        raise PrimitivePreviewDeferred(
            "Preview deferred; Apply to build once. "
            f"{cost.primitive_kind} estimates {cost.render_vertices:,} render vertices, "
            f"{cost.render_triangles:,} triangles, and {cost.work_units:,} work units, above the "
            f"interactive preview budget of {PRIMITIVE_PREVIEW_MAX_WORK_UNITS:,} work units. "
            "The typed construction values are preserved and were not clamped."
        )
    if operation_key not in {"preview", "commit"}:
        raise ValueError("Primitive topology budget operation must be 'preview' or 'commit'.")
    return cost


__all__ = [
    "MAYA_SUBDIVISION_SOFT_MAXIMUM",
    "PRIMITIVE_ABSOLUTE_MAX_ESTIMATED_BYTES",
    "PRIMITIVE_ABSOLUTE_MAX_WORK_UNITS",
    "PRIMITIVE_PREVIEW_MAX_ESTIMATED_BYTES",
    "PRIMITIVE_PREVIEW_MAX_WORK_UNITS",
    "PrimitivePreviewDeferred",
    "PrimitiveTopologyCost",
    "PrimitiveTopologySafetyError",
    "enforce_primitive_topology_budget",
    "estimate_primitive_topology_cost",
]
