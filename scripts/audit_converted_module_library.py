"""Audit every staged converted module with Ghost Studio's current contracts.

This is a read-only audit of candidate ``.mod`` and ``.kmap`` artifacts.  It
does not mutate source downloads or promote structural evidence to retail-game
proof.  The JSON and Markdown outputs provide a reproducible library index for
Map Studio and record provenance classifications from ``CONVERSION_STATUS``.
"""

from __future__ import annotations

import argparse
from collections import Counter
import contextlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for _item in reversed(_python_roots(ROOT)):
    _text = str(_item)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from pykotor.extract.capsule import Capsule  # noqa: E402

from core.validation.kotor_module_engine_contract import (  # noqa: E402
    KotorModuleEngineContractRequest,
    validate_kotor_module_engine_contract,
)
from src.core.level.kmap_serializer import KMapSerializer  # noqa: E402
from src.core.modules.authored_imported_mesh import (  # noqa: E402
    ImportedMeshRoomPrimitive,
)
from src.core.modules.authored_module_kmap_bridge import (  # noqa: E402
    authored_project_from_kmap_payload,
)


DEFAULT_STATUS = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\CONVERSION_STATUS.json"
)
DEFAULT_OUTPUT = ROOT / "Saved" / "Audits" / "mediafire_module_conversion" / "post_repair"


@dataclass
class FileAudit:
    path: str = ""
    exists: bool = False
    size: int = 0
    sha256: str = ""
    openable: bool = False
    error: str = ""


@dataclass
class ModAudit(FileAudit):
    export_ready: bool = False
    resource_count: int = 0
    resource_types: dict[str, int] = field(default_factory=dict)
    room_count: int = 0
    lyt_rooms: list[str] = field(default_factory=list)
    are_rooms: list[str] = field(default_factory=list)
    pth_point_count: int = 0
    pth_connection_count: int = 0
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    engine_contract: dict[str, Any] = field(default_factory=dict)


@dataclass
class KMapAudit(FileAudit):
    project_name: str = ""
    game: str = ""
    authored_section: bool = False
    room_count: int = 0
    editable_room_count: int = 0
    note_count: int = 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_file(path: Path) -> FileAudit:
    if not path.is_file():
        return FileAudit(path=str(path), error="File does not exist.")
    return FileAudit(
        path=str(path),
        exists=True,
        size=path.stat().st_size,
        sha256=_sha256(path),
    )


def audit_mod(path: Path, module_resref: str, game: str) -> ModAudit:
    base = _base_file(path)
    result = ModAudit(**asdict(base))
    if not base.exists:
        return result
    try:
        resources: dict[tuple[str, str], bytes] = {}
        resource_types: Counter[str] = Counter()
        for resource in Capsule(path):
            resref = str(resource.resname()).strip().lower()
            restype = str(resource.restype().extension).strip().lower()
            resources[(resref, restype)] = bytes(resource.data())
            resource_types[restype] += 1

        # Some lower-level GFF helpers are intentionally verbose.  Preserve the
        # structured report and keep incidental diagnostics out of this audit.
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            report = validate_kotor_module_engine_contract(
                KotorModuleEngineContractRequest(
                    game=game,
                    module_resref=module_resref,
                    resources=resources,
                )
            )
        contract = report.to_dict()
        result.openable = True
        result.export_ready = report.export_ready
        result.resource_count = len(resources)
        result.resource_types = dict(sorted(resource_types.items()))
        result.room_count = len(report.rooms)
        result.lyt_rooms = list(report.lyt_rooms)
        result.are_rooms = list(report.are_rooms)
        result.pth_point_count = report.pth_point_count
        result.pth_connection_count = report.pth_connection_count
        result.warnings = list(report.warnings)
        result.blocking_issues = list(report.blocking_issues)
        result.engine_contract = contract
    except Exception:
        result.error = traceback.format_exc()
    return result


def audit_kmap(path: Path, module_resref: str) -> KMapAudit:
    base = _base_file(path)
    result = KMapAudit(**asdict(base))
    if not base.exists:
        return result
    try:
        project = KMapSerializer.load(path)
        result.openable = True
        result.project_name = str(project.name)
        result.game = str(project.game)
        payload = project.extra_sections.get("authored_module")
        result.authored_section = isinstance(payload, dict)
        if result.authored_section:
            authored = authored_project_from_kmap_payload(
                payload,
                fallback_name=module_resref,
                fallback_game=result.game,
            )
            result.room_count = len(authored.rooms)
            result.editable_room_count = sum(
                isinstance(room.primitive, ImportedMeshRoomPrimitive)
                for room in authored.rooms
            )
            result.note_count = len(authored.notes)
    except Exception:
        result.error = traceback.format_exc()
    return result


def _target_row(candidate: dict[str, Any], game: str, output: dict[str, Any]) -> dict[str, Any]:
    module = str(candidate["module"]).lower()
    mod_path = Path(str(output.get("mod", ""))) if output.get("mod") else Path()
    kmap_path = Path(str(output.get("kmap", ""))) if output.get("kmap") else Path()
    mod = audit_mod(mod_path, module, game) if output.get("mod") else ModAudit()
    kmap = audit_kmap(kmap_path, module) if output.get("kmap") else KMapAudit()
    return {
        "module": module,
        "game": game,
        "classification": candidate.get("classification", "unclassified"),
        "status_mapstudio_claim": output.get("mapstudio", ""),
        "mod": asdict(mod),
        "kmap": asdict(kmap),
        "structural_mod_ready": bool(mod.exists and mod.openable and mod.export_ready),
        "mapstudio_kmap_openable": bool(kmap.exists and kmap.openable),
        "editable_kmap": bool(
            kmap.exists
            and kmap.openable
            and kmap.room_count > 0
            and kmap.editable_room_count == kmap.room_count
        ),
        "openable_route": bool(
            (mod.exists and mod.openable and mod.export_ready)
            or (kmap.exists and kmap.openable)
        ),
        "retail_game_tested": False,
    }


def build_report(status_path: Path) -> dict[str, Any]:
    status = json.loads(status_path.read_text(encoding="utf-8"))
    targets: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for candidate in status.get("candidates", []):
        module = str(candidate.get("module", "")).lower()
        outputs = candidate.get("outputs", {})
        games = sorted(
            game
            for game in ("K1", "K2")
            if outputs.get(game)
            and (outputs[game].get("mod") or outputs[game].get("kmap"))
        )
        target_rows = [_target_row(candidate, game, outputs[game]) for game in games]
        targets.extend(target_rows)
        candidates.append(
            {
                "module": module,
                "classification": candidate.get("classification", "unclassified"),
                "available_games": games,
                "missing_target_games": [game for game in ("K1", "K2") if game not in games],
                "has_openable_route": any(row["openable_route"] for row in target_rows),
                "exact_missing_assets": list(candidate.get("exact_missing_assets", [])),
                "remaining_deficits": list(candidate.get("remaining_deficits", [])),
                "retail_proof": candidate.get("retail_proof", "not tested"),
                "evidence": candidate.get("evidence", ""),
            }
        )

    summary = {
        "candidate_identities": len(candidates),
        "target_game_packages": len(targets),
        "identities_with_openable_route": sum(row["has_openable_route"] for row in candidates),
        "dual_game_identities": sum(len(row["available_games"]) == 2 for row in candidates),
        "single_game_identities": sum(len(row["available_games"]) == 1 for row in candidates),
        "structural_mod_ready": sum(row["structural_mod_ready"] for row in targets),
        "mapstudio_kmap_openable": sum(row["mapstudio_kmap_openable"] for row in targets),
        "fully_editable_kmaps": sum(row["editable_kmap"] for row in targets),
        "target_packages_with_blockers": sum(
            bool(row["mod"]["blocking_issues"] or row["mod"]["error"] or row["kmap"]["error"])
            for row in targets
        ),
        "retail_game_proven": 0,
    }
    return {
        "schema": "ghoststudio.converted-module-library-audit.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status_path": str(status_path),
        "status_sha256": _sha256(status_path),
        "proof_scope": (
            "Strict byte-structural module validation plus KMAP serializer/"
            "authored-payload reopening. This is not retail KOTOR proof."
        ),
        "summary": summary,
        "candidates": candidates,
        "targets": targets,
    }


def compare_artifact_drift(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> list[dict[str, Any]]:
    """Describe target or hash changes since the previous audit."""

    if not previous:
        return []
    previous_targets = {
        (str(row.get("module", "")), str(row.get("game", ""))): row
        for row in previous.get("targets", [])
    }
    current_targets = {
        (str(row.get("module", "")), str(row.get("game", ""))): row
        for row in current.get("targets", [])
    }
    drift: list[dict[str, Any]] = []
    for key in sorted(previous_targets.keys() | current_targets.keys()):
        before = previous_targets.get(key)
        after = current_targets.get(key)
        if before is None or after is None:
            drift.append(
                {
                    "module": key[0],
                    "game": key[1],
                    "artifact": "target",
                    "change": "added" if before is None else "removed",
                }
            )
            continue
        for artifact in ("mod", "kmap"):
            old_file = before.get(artifact, {})
            new_file = after.get(artifact, {})
            old_signature = (
                str(old_file.get("path", "")),
                int(old_file.get("size", 0)),
                str(old_file.get("sha256", "")),
            )
            new_signature = (
                str(new_file.get("path", "")),
                int(new_file.get("size", 0)),
                str(new_file.get("sha256", "")),
            )
            if old_signature != new_signature:
                drift.append(
                    {
                        "module": key[0],
                        "game": key[1],
                        "artifact": artifact,
                        "change": "content_or_path_changed",
                        "before": {
                            "path": old_signature[0],
                            "size": old_signature[1],
                            "sha256": old_signature[2],
                        },
                        "after": {
                            "path": new_signature[0],
                            "size": new_signature[1],
                            "sha256": new_signature[2],
                        },
                    }
                )
    return drift


def _short_path(value: str) -> str:
    marker = "KotorMods\\Modules\\"
    if marker in value:
        return value.split(marker, 1)[1]
    return value


def write_markdown(report: dict[str, Any], path: Path) -> None:
    summary = report["summary"]
    lines = [
        "# Converted module library: post-repair audit",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        report["proof_scope"],
        "",
        "## Summary",
        "",
        f"- Module identities with an openable MOD or KMAP route: "
        f"**{summary['identities_with_openable_route']}/{summary['candidate_identities']}**",
        f"- Strict structurally ready MOD packages: "
        f"**{summary['structural_mod_ready']}/{summary['target_game_packages']}**",
        f"- KMAP serializer/authored-payload reopen: "
        f"**{summary['mapstudio_kmap_openable']}/{summary['target_game_packages']}**",
        f"- Fully editable KMAPs: **{summary['fully_editable_kmaps']}/"
        f"{summary['target_game_packages']}**",
        f"- Dual-game identities: **{summary['dual_game_identities']}**",
        f"- Single-game identities: **{summary['single_game_identities']}**",
        f"- Artifact drift since prior audit: **{summary['artifact_drift_count']}**",
        "- Retail-game proven: **0**",
        "",
        "## Target packages",
        "",
        "| Module | Game | Classification | MOD | KMAP | Editable | Rooms | Warnings |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["targets"]:
        mod = row["mod"]
        kmap = row["kmap"]
        lines.append(
            "| {module} | {game} | {classification} | {mod_ready} | {kmap_open} | "
            "{editable} | {rooms} | {warnings} |".format(
                module=row["module"],
                game=row["game"],
                classification=row["classification"],
                mod_ready="pass" if row["structural_mod_ready"] else "FAIL",
                kmap_open="pass" if row["mapstudio_kmap_openable"] else "FAIL",
                editable="yes" if row["editable_kmap"] else "reference",
                rooms=mod["room_count"],
                warnings=len(mod["warnings"]),
            )
        )

    lines.extend(["", "## Open paths", ""])
    for row in report["targets"]:
        lines.extend(
            [
                f"### `{row['module']}` {row['game']}",
                "",
                f"- MOD: `{_short_path(row['mod']['path'])}`",
                f"- KMAP: `{_short_path(row['kmap']['path'])}`",
            ]
        )
        if row["mod"]["warnings"]:
            lines.append(f"- Structural warnings: {len(row['mod']['warnings'])}")
        lines.append("")

    gaps = [row for row in report["candidates"] if row["missing_target_games"]]
    lines.extend(["## Target-game gaps", ""])
    if not gaps:
        lines.append("No target-game package gaps remain.")
    else:
        for row in gaps:
            lines.append(
                f"- `{row['module']}`: missing {', '.join(row['missing_target_games'])}; "
                f"classification `{row['classification']}`."
            )

    lines.extend(["", "## Artifact drift", ""])
    if not report["artifact_drift"]:
        lines.append("No indexed MOD/KMAP path, size, or SHA-256 changed since the prior audit.")
    else:
        for row in report["artifact_drift"]:
            lines.append(
                f"- `{row['module']}` {row['game']} {row['artifact']}: {row['change']}."
            )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A `pass` proves the packaged resources satisfy Ghost Studio's current "
            "byte-structural engine contract and that the indexed KMAP can be "
            "deserialized. It does not prove lighting, textures, room placement, "
            "walkability, scripts, transitions, or loading in K1/K2.",
            "",
            "Classifications are provenance, not quality scores. `donor overlay`, "
            "`reconstruction`, and `scaffold` outputs must not be described as "
            "recovered original geometry.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-both-games",
        action="store_true",
        help="Return failure when an identity lacks either a K1 or K2 package.",
    )
    parser.add_argument(
        "--allow-artifact-drift",
        action="store_true",
        help="Record but do not fail when an indexed MOD/KMAP changed since the prior audit.",
    )
    args = parser.parse_args()

    status_path = args.status.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "converted_module_library_audit.json"
    md_path = output_dir / "converted_module_library_audit.md"
    previous: dict[str, Any] | None = None
    if json_path.is_file():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
    report = build_report(status_path)
    report["artifact_drift"] = compare_artifact_drift(previous, report)
    report["summary"]["artifact_drift_count"] = len(report["artifact_drift"])
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")

    summary = report["summary"]
    failed = summary["target_packages_with_blockers"] > 0
    if not args.allow_artifact_drift:
        failed = failed or summary["artifact_drift_count"] > 0
    if args.require_both_games:
        failed = failed or summary["single_game_identities"] > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
