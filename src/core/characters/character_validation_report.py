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

CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA = "ghostrigger.character_game_test.v1"
REQUIRED_CHARACTER_BUILDER_GAME_TEST_GAMES: tuple[str, ...] = ("K1", "K2")

CAPABILITY_STAGE_BLOCKED = "blocked"
CAPABILITY_STAGE_EXPORT_CANDIDATE = "export_candidate"
CAPABILITY_STAGE_GAME_TESTED = "game_tested"


def build_character_game_test_evidence(
    *,
    tested_games: tuple[str, ...] | list[str],
    checklist_results: dict[str, bool] | list[dict[str, Any]],
    tester: str = "",
    notes: str = "",
    artifacts: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Build a JSON-friendly in-game evidence record for Character Builder.

    This helper intentionally records only manual/visual game-test facts.  It
    does not run the game, and it does not promote a candidate by itself.
    """

    return {
        "schema": CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA,
        "status": "passed",
        "tested_games": [_normalize_game(game) for game in tested_games],
        "checklist_results": _normalize_checklist_results(checklist_results),
        "tester": str(tester or ""),
        "notes": str(notes or ""),
        "artifacts": [str(item or "") for item in artifacts if str(item or "").strip()],
    }


def character_game_test_evidence_passed(evidence: Any) -> bool:
    """Return True when evidence proves the full K1/K2 in-game checklist."""

    if not isinstance(evidence, dict):
        return False
    if evidence.get("schema") != CHARACTER_BUILDER_GAME_TEST_EVIDENCE_SCHEMA:
        return False
    if str(evidence.get("status") or "").strip().lower() != "passed":
        return False
    tested_games = {
        _normalize_game(game)
        for game in list(evidence.get("tested_games") or [])
        if str(game or "").strip()
    }
    if not set(REQUIRED_CHARACTER_BUILDER_GAME_TEST_GAMES).issubset(tested_games):
        return False
    checklist = _normalize_checklist_results(evidence.get("checklist_results") or {})
    if not checklist:
        return False
    return all(bool(checklist.get(item)) for item in CHARACTER_BUILDER_MANUAL_CHECKLIST)


def _normalize_game(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"1", "KOTOR1", "KOTOR 1", "KNIGHTS OF THE OLD REPUBLIC"}:
        return "K1"
    if text in {"2", "KOTOR2", "KOTOR 2", "TSL", "THE SITH LORDS"}:
        return "K2"
    return text


def _normalize_checklist_results(value: Any) -> dict[str, bool]:
    if isinstance(value, dict):
        return {str(key): bool(item) for key, item in value.items()}
    results: dict[str, bool] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            key = str(item.get("item") or item.get("name") or "").strip()
            if key:
                results[key] = bool(item.get("passed"))
    return results


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
    game_test_evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def merged_report(self) -> ValidationReport:
        return merge_validation_reports(
            self.preflight_report,
            self.reload_report or ValidationReport(source="character.export_transaction.verify"),
        )

    @property
    def capability_stage(self) -> str:
        """Return the strongest proven Character Builder export stage."""

        if self.game_tested and character_game_test_evidence_passed(self.game_test_evidence):
            return CAPABILITY_STAGE_GAME_TESTED
        if self.verified:
            return CAPABILITY_STAGE_EXPORT_CANDIDATE
        return CAPABILITY_STAGE_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        merged = self.merged_report
        game_evidence_complete = character_game_test_evidence_passed(self.game_test_evidence)
        data = {
            "schema": "ghostrigger.character_export_validation.v1",
            "status": self.status,
            "verified": bool(self.verified),
            "capability": {
                "stage": self.capability_stage,
                "game_tested": bool(self.game_tested and game_evidence_complete),
                "game_test_requested": bool(self.game_tested),
                "game_test_evidence_complete": bool(game_evidence_complete),
                "game_test_status": (
                    "manual_checklist_passed"
                    if self.game_tested and game_evidence_complete else
                    "game_test_evidence_incomplete"
                    if self.game_tested else
                    "not_game_tested"
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
            "game_test_evidence": dict(self.game_test_evidence or {}),
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
                fix_hint = str(issue.get("fix_hint") or "").strip()
                if fix_hint:
                    lines.append(f"  Fix: {fix_hint}")
                navigation = _format_navigation(issue.get("navigation"))
                if navigation:
                    lines.append(f"  Navigate: {navigation}")
                details = _format_issue_details(issue.get("details"))
                if details:
                    lines.append(f"  Details: {details}")
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


def _format_navigation(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    for key in ("route", "field_path", "node_name", "object_id", "camera_angle"):
        item = value.get(key)
        if item not in (None, ""):
            parts.append(f"{key}={item}")
    if value.get("time_seconds") is not None:
        parts.append(f"time_seconds={value.get('time_seconds')}")
    return ", ".join(parts)


def _format_issue_details(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    skipped = {"engine_evidence"}
    parts: list[str] = []
    for key in sorted(value):
        if key in skipped:
            continue
        item = value.get(key)
        if item in (None, "", [], {}):
            continue
        parts.append(f"{key}={_compact_detail_value(item)}")
        if len(parts) >= 6:
            remaining = len([k for k in value if k not in skipped]) - len(parts)
            if remaining > 0:
                parts.append(f"... {remaining} more")
            break
    return "; ".join(parts)


def _compact_detail_value(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(
            f"{key}: {_compact_detail_value(item)}"
            for key, item in list(value.items())[:4]
        ) + ("..." if len(value) > 4 else "") + "}"
    if isinstance(value, (list, tuple)):
        items = list(value)
        text = ", ".join(_compact_detail_value(item) for item in items[:6])
        if len(items) > 6:
            text += ", ..."
        return "[" + text + "]"
    return str(value)
