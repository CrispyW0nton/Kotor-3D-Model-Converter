"""Head-specific structural preflight for modular KOTOR MDL/MDX export."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Iterable

from src.core.characters.head_donor_snapshot import (
    HeadDonorSnapshot,
    compare_head_donor_contract,
)
from src.io.head_binary_export import (
    HeadBinaryBuild,
    build_verified_head_binary,
)


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class HeadBuilderValidationIssue:
    severity: str
    check_id: str
    message: str
    fix_hint: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "check_id": self.check_id,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class HeadBuilderPreflightReport:
    """Checklist result plus a verified in-memory binary candidate."""

    game: str
    output_resref: str
    issues: tuple[HeadBuilderValidationIssue, ...]
    acknowledged_warning_ids: tuple[str, ...]
    unacknowledged_warning_ids: tuple[str, ...]
    binary_build: HeadBinaryBuild | None = field(
        repr=False,
        compare=False,
        default=None,
    )
    report_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.report_sha256:
            payload = self.to_dict()
            payload["report_sha256"] = ""
            object.__setattr__(
                self,
                "report_sha256",
                _canonical_sha256(payload),
            )

    @property
    def blocking_issues(self) -> tuple[HeadBuilderValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "blocking"
        )

    @property
    def warning_issues(self) -> tuple[HeadBuilderValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == "warning"
        )

    @property
    def export_allowed(self) -> bool:
        return (
            not self.blocking_issues
            and not self.unacknowledged_warning_ids
            and self.binary_build is not None
            and self.binary_build.inspection.accepted
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "output_resref": self.output_resref,
            "export_allowed": self.export_allowed,
            "blocking_count": len(self.blocking_issues),
            "warning_count": len(self.warning_issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "acknowledged_warning_ids": list(
                self.acknowledged_warning_ids
            ),
            "unacknowledged_warning_ids": list(
                self.unacknowledged_warning_ids
            ),
            "binary_inspection": (
                self.binary_build.inspection.to_dict()
                if self.binary_build is not None
                else None
            ),
            "report_sha256": self.report_sha256,
        }


def _issue(
    severity: str,
    check_id: str,
    message: str,
    *,
    fix_hint: str = "",
    details: dict[str, Any] | None = None,
) -> HeadBuilderValidationIssue:
    return HeadBuilderValidationIssue(
        severity=severity,
        check_id=check_id,
        message=message,
        fix_hint=fix_hint,
        details=dict(details or {}),
    )


def _nodes(model: Any) -> list[Any]:
    try:
        return list(model.all_nodes())
    except Exception:
        return []


def _numeric_components(value: Any) -> list[float]:
    if isinstance(value, dict):
        out: list[float] = []
        for item in value.values():
            out.extend(_numeric_components(item))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_numeric_components(item))
        return out
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return []


def _graph_issues(model: Any) -> list[HeadBuilderValidationIssue]:
    issues: list[HeadBuilderValidationIssue] = []
    root = getattr(model, "root_node", None)
    if root is None:
        return [
            _issue(
                "blocking",
                "head.preflight.geometry_root",
                "The candidate has no geometry root.",
                fix_hint="Rehydrate the donor before export.",
            )
        ]
    visited: set[int] = set()
    active: set[int] = set()
    stack: list[tuple[Any, bool]] = [(root, False)]
    while stack:
        node, leaving = stack.pop()
        identity = id(node)
        if leaving:
            active.discard(identity)
            continue
        if identity in active:
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.dag_cycle",
                    "The candidate DAG contains a child cycle.",
                    fix_hint="Restore the donor DAG before export.",
                )
            )
            continue
        if identity in visited:
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.dag_shared_child",
                    "One node appears beneath multiple DAG parents.",
                    fix_hint="Restore one unique donor parent per node.",
                )
            )
            continue
        visited.add(identity)
        active.add(identity)
        stack.append((node, True))
        for child in reversed(
            list(getattr(node, "children", ()) or ())
        ):
            if getattr(child, "parent", None) is not node:
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.parent_child_mismatch",
                        (
                            f"Node '{getattr(child, 'name', '')}' does not "
                            "point back to its declared parent."
                        ),
                        fix_hint="Restore donor parent/child arrays.",
                    )
                )
            stack.append((child, False))
    return issues


def _finite_geometry_issues(
    model: Any,
) -> list[HeadBuilderValidationIssue]:
    issues: list[HeadBuilderValidationIssue] = []
    for node in _nodes(model):
        node_name = str(getattr(node, "name", "") or "")
        for channel in ("position", "rotation", "bb_min", "bb_max"):
            value = getattr(node, channel, None)
            if value is None:
                continue
            numbers = _numeric_components(value)
            if numbers and not all(math.isfinite(number) for number in numbers):
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.nonfinite_node",
                        f"Node '{node_name}' has non-finite {channel} values.",
                        fix_hint="Repair the named transform/bounds channel.",
                        details={"node": node_name, "channel": channel},
                    )
                )
        vertices = list(getattr(node, "vertices", ()) or ())
        normals = list(getattr(node, "normals", ()) or ())
        uvs = list(getattr(node, "uvs", ()) or ())
        for channel, rows in (
            ("vertices", vertices),
            ("normals", normals),
            ("uvs", uvs),
        ):
            if any(
                not all(
                    math.isfinite(value)
                    for value in _numeric_components(row)
                )
                for row in rows
            ):
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.nonfinite_payload",
                        f"Node '{node_name}' has non-finite {channel}.",
                        fix_hint="Repair or remove the invalid mesh values.",
                        details={"node": node_name, "channel": channel},
                    )
                )
        vertex_count = len(vertices)
        for face_index, face in enumerate(
            list(getattr(node, "faces", ()) or ())
        ):
            try:
                indices = tuple(int(value) for value in face)
            except Exception:
                indices = ()
            if (
                len(indices) != 3
                or len(set(indices)) != 3
                or any(
                    value < 0 or value >= vertex_count
                    for value in indices
                )
            ):
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.invalid_face",
                        (
                            f"Node '{node_name}' face {face_index} is not a "
                            "valid indexed triangle."
                        ),
                        fix_hint="Repair the face topology before export.",
                    )
                )
                break
        controllers = getattr(node, "controllers", None)
        controller_values = _numeric_components(controllers)
        if controller_values and not all(
            math.isfinite(value) for value in controller_values
        ):
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.nonfinite_controller",
                    f"Node '{node_name}' has non-finite controller data.",
                    fix_hint="Repair or remove the invalid controller.",
                )
            )
    return issues


def _skin_issues(
    model: Any,
    snapshot: HeadDonorSnapshot,
) -> list[HeadBuilderValidationIssue]:
    issues: list[HeadBuilderValidationIssue] = []
    nodes = _nodes(model)
    for ordinal in snapshot.mutable_payload_node_ordinals:
        if ordinal < 0 or ordinal >= len(nodes):
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.payload_missing",
                    "The donor's mutable rendered head payload is missing.",
                    fix_hint="Rebuild geometry/skin transfer.",
                )
            )
            continue
        node = nodes[ordinal]
        palette = list(getattr(node, "bone_map", ()) or ())
        if len(palette) > 16:
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.palette_limit",
                    "The head skin palette exceeds KOTOR's 16-bone limit.",
                    fix_hint="Reduce influences without changing donor order.",
                )
            )
        totals = [0.0] * len(palette)
        rows = list(getattr(node, "skin_data", ()) or ())
        if len(rows) != len(list(getattr(node, "vertices", ()) or ())):
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.skin_row_count",
                    "The head does not have one skin row per vertex.",
                    fix_hint="Rebuild the transfer baseline.",
                )
            )
        for row_index, row in enumerate(rows):
            influences = getattr(row, "influences", None)
            if influences is None:
                influences = getattr(row, "weights", ())
            weights = list(influences or ())
            if not weights or len(weights) > 4:
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.influence_limit",
                        (
                            f"Skin row {row_index} has {len(weights)} "
                            "influences; KOTOR requires 1-4."
                        ),
                        fix_hint="Normalize and prune the skin row.",
                    )
                )
                continue
            total = 0.0
            for weight in weights:
                index = int(getattr(weight, "bone_index", -1))
                value = float(getattr(weight, "weight", 0.0))
                if (
                    index < 0
                    or index >= len(palette)
                    or not math.isfinite(value)
                    or value <= 0.0
                ):
                    issues.append(
                        _issue(
                            "blocking",
                            "head.preflight.invalid_influence",
                            f"Skin row {row_index} has an invalid influence.",
                            fix_hint="Repair weights within the donor palette.",
                        )
                    )
                    continue
                total += value
                totals[index] += value
            if abs(total - 1.0) > 1.0e-5:
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.weight_normalization",
                        (
                            f"Skin row {row_index} sums to {total:.8f}, "
                            "not 1.0."
                        ),
                        fix_hint="Normalize the skin row.",
                    )
                )
        palette_lookup = {
            str(name).casefold(): index
            for index, name in enumerate(palette)
        }
        required = [
            name
            for name in (
                snapshot.attachment_target_name,
                "head_g",
                "f_jaw_g",
            )
            if name.casefold() in palette_lookup
        ]
        missing_weight = [
            name
            for name in required
            if totals[palette_lookup[name.casefold()]] <= 1.0e-8
        ]
        if missing_weight:
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.required_facial_weights",
                    (
                        "Required donor controls have no final skin weight: "
                        + ", ".join(missing_weight)
                    ),
                    fix_hint=(
                        "Paint at least one appropriate vertex to each named "
                        "donor control without changing the palette."
                    ),
                    details={"missing_controls": missing_weight},
                )
            )
    return issues


def preflight_head_builder_export(
    model: Any,
    *,
    donor_snapshot: HeadDonorSnapshot,
    game: str,
    output_resref: str,
    texture_report: Any,
    attachment_report: Any,
    acknowledged_warning_ids: Iterable[str] = (),
) -> HeadBuilderPreflightReport:
    """Validate memory, binary writer, raw headers, and critical reload facts."""

    issues: list[HeadBuilderValidationIssue] = []
    normalized_game = str(game or "").upper()
    donor_diff = compare_head_donor_contract(
        donor_snapshot,
        model,
        output_resref=output_resref,
    )
    if donor_diff.blocking:
        issues.append(
            _issue(
                "blocking",
                "head.preflight.donor_contract",
                "The candidate has blocking immutable-donor differences.",
                fix_hint="Rehydrate the donor and rebuild the payload.",
                details={"diff": donor_diff.to_dict()},
            )
        )
    if str(donor_snapshot.game or "").upper() != normalized_game:
        issues.append(
            _issue(
                "blocking",
                "head.preflight.game_mismatch",
                "The donor game does not match the export game.",
                fix_hint="Select a donor from the configured target game.",
            )
        )
    issues.extend(_graph_issues(model))
    issues.extend(_finite_geometry_issues(model))
    issues.extend(_skin_issues(model, donor_snapshot))

    local_animations = tuple(
        str(getattr(animation, "name", "") or "")
        for animation in list(getattr(model, "animations", ()) or ())
    )
    if local_animations != donor_snapshot.local_animation_names:
        issues.append(
            _issue(
                "blocking",
                "head.preflight.local_animations",
                (
                    "The modular head local animation inventory changed; "
                    "body/supermodel clips must remain inherited."
                ),
                fix_hint="Remove materialized preview/body clips.",
            )
        )
    if not bool(getattr(texture_report, "accepted", False)):
        issues.append(
            _issue(
                "blocking",
                "head.preflight.texture_policy",
                "The UV/texture/material contract is not accepted.",
                fix_hint="Return to UVs, textures, and materials.",
            )
        )
    if not bool(
        getattr(texture_report, "preview_matches_serialized", False)
    ):
        issues.append(
            _issue(
                "blocking",
                "head.preflight.uv_orientation",
                "Preview and serialized UV orientation do not match.",
                fix_hint="Choose one explicit V-orientation policy.",
            )
        )
    texture_warnings = tuple(
        list(getattr(texture_report, "uv_warnings", ()) or ())
        + list(getattr(texture_report, "texture_warnings", ()) or ())
    )
    if texture_warnings:
        issues.append(
            _issue(
                "warning",
                "head.preflight.uv_texture_warnings",
                (
                    f"UV/texture review has {len(texture_warnings)} warning(s)."
                ),
                fix_hint=(
                    "Review mirrored/overlapping UVs and explicitly "
                    "acknowledge them if intentional."
                ),
                details={"warnings": list(texture_warnings)},
            )
        )
    if not bool(getattr(attachment_report, "accepted", False)):
        issues.append(
            _issue(
                "blocking",
                "head.preflight.attachment_preview",
                "The exact-headhook inherited-animation preview is not accepted.",
                fix_hint="Return to attachment and animation preview.",
            )
        )
    if tuple(
        getattr(
            attachment_report,
            "source_head_local_animation_names",
            (),
        )
    ) != tuple(
        getattr(
            attachment_report,
            "preview_head_local_animation_names",
            (),
        )
    ):
        issues.append(
            _issue(
                "blocking",
                "head.preflight.preview_materialized_animation",
                "Preview construction changed the head's local clips.",
                fix_hint="Rebuild preview without copying body animations.",
            )
        )

    build: HeadBinaryBuild | None = None
    if not any(issue.severity == "blocking" for issue in issues):
        try:
            build = build_verified_head_binary(
                model,
                donor_snapshot=donor_snapshot,
                game=normalized_game,
                output_resref=output_resref,
            )
        except Exception as exc:
            issues.append(
                _issue(
                    "blocking",
                    "head.preflight.binary_writer",
                    f"Binary write/reload verification failed: {exc}",
                    fix_hint="Inspect the expandable raw binary diagnostics.",
                )
            )
        else:
            for message in build.inspection.blocking_issues:
                issues.append(
                    _issue(
                        "blocking",
                        "head.preflight.binary_readback",
                        message,
                        fix_hint="Repair the binary/readback mismatch.",
                    )
                )
            for message in build.inspection.warnings:
                issues.append(
                    _issue(
                        "warning",
                        "head.preflight.binary_warning",
                        message,
                        fix_hint="Review and acknowledge if intentional.",
                    )
                )
    acknowledged = tuple(
        sorted(
            {
                str(value)
                for value in acknowledged_warning_ids
                if str(value)
            }
        )
    )
    warning_ids = {
        issue.check_id
        for issue in issues
        if issue.severity == "warning"
    }
    unacknowledged = tuple(sorted(warning_ids - set(acknowledged)))
    return HeadBuilderPreflightReport(
        game=normalized_game,
        output_resref=str(output_resref),
        issues=tuple(issues),
        acknowledged_warning_ids=acknowledged,
        unacknowledged_warning_ids=unacknowledged,
        binary_build=build,
    )


__all__ = [
    "HeadBuilderPreflightReport",
    "HeadBuilderValidationIssue",
    "preflight_head_builder_export",
]
