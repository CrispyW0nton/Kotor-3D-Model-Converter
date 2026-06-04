"""Character Builder export validation report artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.validation.validation_bus import (
    ValidationReport,
    merge_validation_reports,
    validation_report_to_dict,
)

from .kotor_constants import CHARACTER_EXPORT_EVIDENCE


CHARACTER_BUILDER_MANUAL_CHECKLIST: tuple[str, ...] = (
    "Load as player character without crash",
    "Idle/pause animation plays correctly",
    "Walk/run animations with proper foot contact",
    "Dialog animation (tlknorm) works",
    "One-handed weapon rhand socket attachment",
    "Two-handed weapon both hand sockets",
    "Head model headhook attachment",
    "Lightsaber LightsaberHook functionality",
    "Dialog camerahook positioning",
    "DeflectHook animation behavior",
    "Supermodel animation inheritance",
    "Loading in both KOTOR 1 and KOTOR 2",
)

CAPABILITY_STAGE_BLOCKED = "blocked"
CAPABILITY_STAGE_EXPORT_CANDIDATE = "export_candidate"
CAPABILITY_STAGE_GAME_TESTED = "game_tested"


@dataclass(frozen=True)
class CharacterBuilderValidationReport:
    """Machine-readable and human-readable Character Builder export proof."""

    status: str
    verified: bool
    job_id: str
    export_kind: str
    game: str
    resref: str
    outputs: dict[str, str]
    preflight_report: ValidationReport
    reload_report: ValidationReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    game_tested: bool = False

    @property
    def merged_report(self) -> ValidationReport:
        return merge_validation_reports(
            self.preflight_report,
            self.reload_report or ValidationReport(source="character.export_transaction.verify"),
        )

    @property
    def capability_stage(self) -> str:
        """Return the strongest proven Character Builder export stage."""

        if self.game_tested:
            return CAPABILITY_STAGE_GAME_TESTED
        if self.verified:
            return CAPABILITY_STAGE_EXPORT_CANDIDATE
        return CAPABILITY_STAGE_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        merged = self.merged_report
        data = {
            "schema": "ghostrigger.character_export_validation.v1",
            "status": self.status,
            "verified": bool(self.verified),
            "capability": {
                "stage": self.capability_stage,
                "game_tested": bool(self.game_tested),
                "game_test_status": (
                    "manual_checklist_passed"
                    if self.game_tested else "not_game_tested"
                ),
                "honesty_note": (
                    "GhostRigger verification proves staged export and reload "
                    "preflight only. Treat this as an export candidate until "
                    "the manual in-game checklist passes in KOTOR."
                ),
            },
            "job_id": self.job_id,
            "export_kind": self.export_kind,
            "game": self.game,
            "resref": self.resref,
            "outputs": dict(self.outputs),
            "engine_evidence": CHARACTER_EXPORT_EVIDENCE,
            "manual_in_game_checklist": list(CHARACTER_BUILDER_MANUAL_CHECKLIST),
            "preflight_report": validation_report_to_dict(self.preflight_report),
            "reload_report": validation_report_to_dict(self.reload_report)
            if self.reload_report is not None else None,
            "summary": {
                "issue_count": len(merged.issues),
                "blocking_count": len(merged.blocking_issues),
                "export_allowed": not merged.has_blocking,
            },
            "metadata": dict(self.metadata),
        }
        json.dumps(data)
        return data

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_text(self) -> str:
        payload = self.to_dict()
        lines = [
            "GhostRigger Character Builder Export Validation",
            f"Status: {payload.get('status')}",
            f"Verified: {payload.get('verified')}",
            f"Capability stage: {payload.get('capability', {}).get('stage')}",
            f"Game tested: {payload.get('capability', {}).get('game_tested')}",
            f"Game: {payload.get('game')}",
            f"Resref: {payload.get('resref')}",
            "",
            "Outputs:",
        ]
        for key, value in dict(payload.get("outputs") or {}).items():
            lines.append(f"- {key}: {value}")

        workflow = dict(payload.get("metadata", {}).get("character_builder_workflow") or {})
        if workflow:
            rig_state = dict(workflow.get("rig_state") or {})
            fit_report = dict(workflow.get("fit_report") or {})
            fit_transform = dict(fit_report.get("fit_transform") or {})
            native_snapshot = dict(workflow.get("native_snapshot") or {})
            lines.extend(["", "Character Builder workflow evidence:"])
            lines.append(
                f"- Final DAG source: {workflow.get('final_dag_source')}"
            )
            lines.append(
                f"- Rig state: {rig_state.get('state')} "
                f"({rig_state.get('dag_authority')})"
            )
            if native_snapshot:
                lines.append(
                    f"- Native snapshot: {native_snapshot.get('game')} "
                    f"{native_snapshot.get('model_name')} "
                    f"supermodel {native_snapshot.get('supermodel')}"
                )
            if fit_report:
                lines.append(
                    f"- Auto-fit policy: {fit_report.get('fit_policy')} "
                    f"confidence {fit_report.get('confidence')}"
                )
            if fit_transform:
                lines.append(
                    f"- Fit transform: scale {fit_transform.get('scale')} "
                    f"translation {fit_transform.get('translation')}"
                )

        lines.extend(["", "Issues:"])
        issue_count = 0
        reports = [
            ("preflight", payload.get("preflight_report")),
            ("reload", payload.get("reload_report")),
        ]
        for report_name, report in reports:
            if not isinstance(report, dict):
                continue
            for issue in list(report.get("issues") or []):
                issue_count += 1
                lines.append(
                    f"- [{report_name}] {issue.get('severity')} "
                    f"{issue.get('code')}: {issue.get('message')}"
                )
        if issue_count == 0:
            lines.append("- none")

        lines.extend(["", "Manual in-game checklist:"])
        for index, item in enumerate(CHARACTER_BUILDER_MANUAL_CHECKLIST, start=1):
            lines.append(f"{index}. {item}")
        return "\n".join(lines) + "\n"


def validation_report_paths(mdl_path: str | Path) -> tuple[Path, Path]:
    """Return the JSON and text report paths for a Character Builder MDL."""

    path = Path(mdl_path)
    return (
        path.with_name(f"{path.stem}_validation_report.json"),
        path.with_name(f"{path.stem}_validation_report.txt"),
    )
