"""Structural validation for Aurora animation blocks before MDL export."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import struct
from typing import Any, Dict, Iterable, List, Optional

from src.core.animation.animation_engine import AnimationEngine
from src.core.geometry.model_data import Animation, KotorModel, ModelNode


class AnimationBlockValidationError(ValueError):
    """Raised when an animation block is unsafe to export for a target model."""


_BASE = 12
_MODEL_FIELDS_ABS = _BASE + 80
_MODEL_ANIM_ARRAY_OFF_ABS = _MODEL_FIELDS_ABS + 8
_MODEL_ANIM_COUNT_ABS = _MODEL_FIELDS_ABS + 12
_MODEL_NAME_OFFSETS_OFF_ABS = _MODEL_FIELDS_ABS + 104
_MODEL_NAME_COUNT_ABS = _MODEL_FIELDS_ABS + 108


@dataclass(frozen=True)
class AnimationValidationIssue:
    """One structural animation-block validation issue."""

    message: str
    node_name: str = ""
    controller_name: str = ""
    time: Optional[float] = None


@dataclass
class AnimationValidationReport:
    """Validation result for one animation block against one Aurora model."""

    success: bool = True
    issues: List[AnimationValidationIssue] = field(default_factory=list)
    warnings: List[AnimationValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        *,
        node_name: str = "",
        controller_name: str = "",
        time: Optional[float] = None,
    ) -> None:
        self.success = False
        self.issues.append(
            AnimationValidationIssue(
                message=message,
                node_name=node_name,
                controller_name=controller_name,
                time=time,
            )
        )

    def raise_for_errors(self, animation_name: str, target_name: str) -> None:
        """Raise a user-readable export error if validation failed."""

        if self.success:
            return

        details = "; ".join(issue.message for issue in self.issues[:5])
        if len(self.issues) > 5:
            details += f"; ... and {len(self.issues) - 5} more"
        raise AnimationBlockValidationError(
            f"Animation block '{animation_name}' cannot be exported for target '{target_name}': "
            f"{details}. KOTOR animation controllers must target existing Aurora nodes "
            "on the model/supermodel hierarchy."
        )


@dataclass(frozen=True)
class RawAnimationNodeRecord:
    """Raw MDL fields needed by the engine's animation child walker."""

    name: str
    offset_rel: int
    child_array_rel: int
    child_count: int
    child_offsets_rel: List[int]
    controller_array_rel: int
    controller_count: int


@dataclass
class RawAnimationFootprintReport:
    """Raw-byte validation of an MDL animation tree."""

    success: bool = True
    animation_name: str = ""
    declared_node_count: int = 0
    visited_node_count: int = 0
    depth_first_order_ok: bool = True
    issues: List[str] = field(default_factory=list)
    nodes: List[RawAnimationNodeRecord] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.success = False
        self.issues.append(message)

    @property
    def node_names(self) -> List[str]:
        return [node.name for node in self.nodes]


def validate_raw_animation_footprint(
    mdl_bytes: bytes,
    animation_name: str,
    *,
    require_depth_first_layout: bool = True,
    require_declared_count_match: bool = True,
) -> RawAnimationFootprintReport:
    """Simulate the engine's raw child traversal for one MDL animation block.

    PyKotor can resolve child offsets even when the binary block is arranged in
    a more forgiving order.  KotOR's ResetMdlNode/UpdateAnimFootprint path is
    stricter: it reads each node's child count at ``+0x30``, takes the child
    pointer array from ``+0x2c``, and immediately dereferences every entry as an
    animation node pointer.  This validator checks those raw fields directly and
    optionally requires the vanilla depth-first layout where child subtrees are
    serialized before the parent controller arrays.
    """

    report = RawAnimationFootprintReport(animation_name=animation_name)
    try:
        anim_rel = _find_animation_offset(mdl_bytes, animation_name)
    except ValueError as exc:
        report.add_error(str(exc))
        return report

    names = _read_name_table(mdl_bytes)
    anim_abs = _BASE + anim_rel
    if anim_abs + 80 > len(mdl_bytes):
        report.add_error(f"animation '{animation_name}' offset 0x{anim_rel:x} is out of bounds")
        return report

    root_rel = _u32(mdl_bytes, anim_abs + 0x28)
    report.declared_node_count = _u32(mdl_bytes, anim_abs + 0x2C)
    visited: set[int] = set()
    stack: set[int] = set()

    def walk(node_rel: int) -> None:
        node_abs = _BASE + node_rel
        if node_rel == 0:
            report.add_error("encountered null animation node offset")
            return
        if node_abs < 0 or node_abs + 80 > len(mdl_bytes):
            report.add_error(f"animation node offset 0x{node_rel:x} is out of bounds")
            return
        if node_rel in stack:
            report.add_error(f"cycle detected at animation node offset 0x{node_rel:x}")
            return
        if node_rel in visited:
            report.add_error(f"animation node offset 0x{node_rel:x} is referenced more than once")
            return

        stack.add(node_rel)
        visited.add(node_rel)

        name_index = _u16(mdl_bytes, node_abs + 0x04)
        name = names[name_index] if 0 <= name_index < len(names) else f"<name:{name_index}>"
        child_array_rel = _u32(mdl_bytes, node_abs + 0x2C)
        child_count = _u32(mdl_bytes, node_abs + 0x30)
        child_count2 = _u32(mdl_bytes, node_abs + 0x34)
        controller_array_rel = _u32(mdl_bytes, node_abs + 0x38)
        controller_count = _u32(mdl_bytes, node_abs + 0x3C)
        controller_count2 = _u32(mdl_bytes, node_abs + 0x40)
        child_offsets: List[int] = []

        if child_count != child_count2:
            report.add_error(
                f"node '{name}' child count duplicate mismatch: {child_count} != {child_count2}"
            )
        if controller_count != controller_count2:
            report.add_error(
                f"node '{name}' controller count duplicate mismatch: {controller_count} != {controller_count2}"
            )

        if child_count > 0:
            child_array_abs = _BASE + child_array_rel
            array_size = child_count * 4
            if child_array_rel == 0 or child_array_abs + array_size > len(mdl_bytes):
                report.add_error(f"node '{name}' child pointer array is invalid: 0x{child_array_rel:x}")
            else:
                for index in range(child_count):
                    child_rel = _u32(mdl_bytes, child_array_abs + index * 4)
                    child_offsets.append(child_rel)
                    child_abs = _BASE + child_rel
                    if child_rel == 0:
                        report.add_error(f"node '{name}' child {index} is null")
                    elif child_abs + 80 > len(mdl_bytes):
                        report.add_error(
                            f"node '{name}' child {index} offset 0x{child_rel:x} is out of bounds"
                        )
                    elif child_rel == node_rel:
                        report.add_error(f"node '{name}' child {index} points back to itself")

                if child_offsets and require_depth_first_layout:
                    expected_first_child_abs = child_array_abs + array_size
                    actual_first_child_abs = _BASE + child_offsets[0]
                    if actual_first_child_abs != expected_first_child_abs:
                        report.depth_first_order_ok = False
                        report.add_error(
                            f"node '{name}' first child starts at 0x{actual_first_child_abs:x}, "
                            f"expected immediately after child array at 0x{expected_first_child_abs:x}"
                        )

        report.nodes.append(
            RawAnimationNodeRecord(
                name=name,
                offset_rel=node_rel,
                child_array_rel=child_array_rel,
                child_count=child_count,
                child_offsets_rel=child_offsets,
                controller_array_rel=controller_array_rel,
                controller_count=controller_count,
            )
        )

        for child_rel in child_offsets:
            walk(child_rel)
        stack.remove(node_rel)

    walk(root_rel)
    report.visited_node_count = len(visited)
    if require_declared_count_match and report.visited_node_count != report.declared_node_count:
        report.add_error(
            f"raw child traversal visited {report.visited_node_count} nodes, "
            f"but animation header declares {report.declared_node_count}"
        )
    return report


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"uint32 read at 0x{offset:x} is out of bounds")
    return struct.unpack_from("<I", data, offset)[0]


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"uint16 read at 0x{offset:x} is out of bounds")
    return struct.unpack_from("<H", data, offset)[0]


def _read_c_string(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def _read_name_table(mdl_bytes: bytes) -> List[str]:
    if len(mdl_bytes) < _MODEL_NAME_COUNT_ABS + 4:
        return []
    table_rel = _u32(mdl_bytes, _MODEL_NAME_OFFSETS_OFF_ABS)
    count = _u32(mdl_bytes, _MODEL_NAME_COUNT_ABS)
    table_abs = _BASE + table_rel
    names: List[str] = []
    for index in range(count):
        entry_abs = table_abs + index * 4
        if entry_abs + 4 > len(mdl_bytes):
            break
        name_rel = _u32(mdl_bytes, entry_abs)
        names.append(_read_c_string(mdl_bytes, _BASE + name_rel))
    return names


def _find_animation_offset(mdl_bytes: bytes, animation_name: str) -> int:
    if len(mdl_bytes) < _MODEL_ANIM_COUNT_ABS + 4:
        raise ValueError("MDL is too small to contain an animation table")
    wanted = str(animation_name or "").lower()
    count = _u32(mdl_bytes, _MODEL_ANIM_COUNT_ABS)
    table_rel = _u32(mdl_bytes, _MODEL_ANIM_ARRAY_OFF_ABS)
    if count <= 0 or table_rel <= 0:
        raise ValueError(f"animation '{animation_name}' is missing; model has no local animations")
    table_abs = _BASE + table_rel
    for index in range(count):
        entry_abs = table_abs + index * 4
        if entry_abs + 4 > len(mdl_bytes):
            break
        anim_rel = _u32(mdl_bytes, entry_abs)
        anim_abs = _BASE + anim_rel
        if anim_abs + 40 > len(mdl_bytes):
            continue
        name = _read_c_string(mdl_bytes, anim_abs + 8)
        if name.lower() == wanted:
            return anim_rel
    raise ValueError(f"animation '{animation_name}' was not found in the local animation table")


def _controller_label(ctrl: Dict[str, Any]) -> str:
    name = str(ctrl.get("name", "") or "").strip()
    if name:
        return name
    return str(ctrl.get("type", "controller"))


def _is_position_controller(ctrl: Dict[str, Any]) -> bool:
    return ctrl.get("type") == AnimationEngine.CTRL_POSITION or str(ctrl.get("name", "")).lower() == "position"


def _is_orientation_controller(ctrl: Dict[str, Any]) -> bool:
    return (
        ctrl.get("type") == AnimationEngine.CTRL_ORIENTATION
        or str(ctrl.get("name", "")).lower() == "orientation"
    )


def _finite_values(values: Iterable[Any]) -> bool:
    try:
        return all(math.isfinite(float(value)) for value in values)
    except (TypeError, ValueError):
        return False


def _validate_controller(
    report: AnimationValidationReport,
    node: ModelNode,
    ctrl: Dict[str, Any],
    *,
    animation_length: float,
    epsilon: float,
) -> None:
    label = _controller_label(ctrl)
    times = list(ctrl.get("times", []) or [])
    values = list(ctrl.get("values", []) or [])

    if len(times) != len(values):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has {len(times)} times but {len(values)} values",
            node_name=node.name,
            controller_name=label,
        )
        return
    if not times:
        return

    numeric_times: List[float] = []
    for raw_time in times:
        try:
            time_value = float(raw_time)
        except (TypeError, ValueError):
            report.add_error(
                f"controller '{label}' on node '{node.name}' has non-numeric key time {raw_time!r}",
                node_name=node.name,
                controller_name=label,
            )
            continue
        numeric_times.append(time_value)
        if not math.isfinite(time_value):
            report.add_error(
                f"controller '{label}' on node '{node.name}' has non-finite key time",
                node_name=node.name,
                controller_name=label,
                time=time_value,
            )
        elif time_value < -epsilon or time_value > animation_length + epsilon:
            report.add_error(
                f"controller '{label}' on node '{node.name}' has key time {time_value:g} outside animation length {animation_length:g}",
                node_name=node.name,
                controller_name=label,
                time=time_value,
            )

    if numeric_times != sorted(numeric_times):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has unsorted key times",
            node_name=node.name,
            controller_name=label,
        )
    if len(set(numeric_times)) != len(numeric_times):
        report.add_error(
            f"controller '{label}' on node '{node.name}' has duplicate key times",
            node_name=node.name,
            controller_name=label,
        )

    for index, row in enumerate(values):
        row_values = list(row or [])
        time_value = numeric_times[index] if index < len(numeric_times) else None
        if _is_position_controller(ctrl):
            if len(row_values) < 3 or not _finite_values(row_values[:3]):
                report.add_error(
                    f"invalid position key on node '{node.name}' at time {time_value}: non-finite or incomplete value",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )
        elif _is_orientation_controller(ctrl):
            if len(row_values) < 4 or not _finite_values(row_values[:4]):
                report.add_error(
                    f"invalid orientation key on node '{node.name}' at time {time_value}: non-finite or incomplete quaternion",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )
                continue
            x, y, z, w = (float(value) for value in row_values[:4])
            norm_sq = x * x + y * y + z * z + w * w
            if norm_sq <= 1e-12:
                report.add_error(
                    f"invalid orientation key on node '{node.name}' at time {time_value}: zero-length quaternion",
                    node_name=node.name,
                    controller_name=label,
                    time=time_value,
                )


def validate_animation_block_against_model(
    model: KotorModel,
    animation_block: Animation,
    *,
    strict: bool = True,
) -> AnimationValidationReport:
    """Validate that an animation block can be safely injected into ``model``."""

    report = AnimationValidationReport()
    animation_name = str(getattr(animation_block, "name", "") or "").strip()
    target_nodes = {str(node.name or "").lower(): node.name for node in model.all_nodes()}

    if not animation_name:
        report.add_error("animation name is empty")

    try:
        animation_length = float(getattr(animation_block, "length", 0.0) or 0.0)
    except (TypeError, ValueError):
        animation_length = -1.0
    if not math.isfinite(animation_length) or animation_length < 0.0:
        report.add_error(f"animation length is invalid: {getattr(animation_block, 'length', None)!r}")
        animation_length = 0.0

    epsilon = 1e-5
    for anim_node in getattr(animation_block, "nodes", []) or []:
        node_name = str(getattr(anim_node, "name", "") or "").strip()
        if not node_name:
            report.add_error("animation controller node name is empty")
            continue
        if node_name.lower() not in target_nodes:
            report.add_error(f"unknown controller node '{node_name}'", node_name=node_name)
            continue
        for ctrl in getattr(anim_node, "controllers", []) or []:
            _validate_controller(
                report,
                anim_node,
                ctrl,
                animation_length=animation_length,
                epsilon=epsilon if strict else 1e-4,
            )

    return report
