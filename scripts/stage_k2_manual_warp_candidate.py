"""Safely stage one structurally-audited MOD for a manual KOTOR 2 warp.

This helper deliberately does not launch the game, edit ``swkotor2.ini``,
install a DirectInput hook, or touch any module other than the explicitly named
root.  Structural validation is an admission gate, not retail proof: the
manifest always records ``retail_game_proven=false`` until a person completes
the manual warp and traversal checklist.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_walkmesh_library import audit_mod  # noqa: E402


DEFAULT_K2_ROOT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)
DEFAULT_EVIDENCE_ROOT = ROOT / "Saved" / "KotorManualWarpEvidence"
_MODULE_ROOT_RE = re.compile(r"[A-Za-z0-9_]{1,16}\Z")


class StagingError(RuntimeError):
    """Raised when a candidate cannot be staged without violating safeguards."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "sha256": None, "byte_size": None}
    return {
        "path": str(path),
        "sha256": _sha256_file(path),
        "byte_size": path.stat().st_size,
    }


def _same_path(first: Path, second: Path) -> bool:
    try:
        return first.samefile(second)
    except (FileNotFoundError, OSError):
        return first.resolve() == second.resolve()


def is_swkotor2_running() -> bool:
    """Return whether the retail K2 executable is running.

    Query the Windows process table through ``System.Diagnostics`` rather than
    ``tasklist``.  Some Windows installs leave ``tasklist`` blocked behind a
    broken WMI/provider query even though the process table itself is healthy.
    A failed or ambiguous query remains unsafe and therefore blocks staging.
    """

    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                (
                    "try { "
                    "$p = [System.Diagnostics.Process]::GetProcessesByName('swkotor2'); "
                    "if ($p.Count -gt 0) { Write-Output 'RUNNING' } "
                    "else { Write-Output 'NOT_RUNNING' }; "
                    "exit 0 "
                    "} catch { Write-Error $_; exit 2 }"
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StagingError(
            "Could not verify whether swkotor2.exe is running; refusing to stage."
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "process query failed").strip()
        raise StagingError(
            "Could not verify whether swkotor2.exe is running; refusing to stage. "
            f"Windows process query returned {completed.returncode}: {detail}"
        )
    states = [line.strip().upper() for line in completed.stdout.splitlines() if line.strip()]
    if states == ["RUNNING"]:
        return True
    if states == ["NOT_RUNNING"]:
        return False
    raise StagingError(
        "Could not verify whether swkotor2.exe is running; refusing to stage. "
        f"Unexpected Windows process-query response: {completed.stdout!r}"
    )


def _validate_module_root(value: str) -> str:
    module_root = value.strip()
    if not _MODULE_ROOT_RE.fullmatch(module_root):
        raise StagingError(
            "--module-root must be a 1-16 character KOTOR resref containing only "
            "letters, digits, or underscores."
        )
    return module_root


def _timestamp_slug(moment: datetime) -> str:
    normalized = moment.astimezone(timezone.utc)
    return normalized.strftime("%Y%m%dT%H%M%S%fZ")


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _verified_copy(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied_hash = _sha256_file(destination)
    if copied_hash != expected_sha256:
        destination.unlink(missing_ok=True)
        raise StagingError(
            f"Hash verification failed while copying {source} to {destination}."
        )


def _manual_warp_checklist(module_root: str) -> list[str]:
    return [
        "Start KOTOR 2 only after this staging command has completed.",
        "Load a clean save whose current area is not the staged module.",
        f"Open the retail console and run: warp {module_root}",
        "Confirm the module finishes loading without a crash or infinite load.",
        "Confirm the player starts on a walkable floor and can click-to-move.",
        "Traverse every reachable room, ramp, seam, doorway, and elevation change.",
        "Check that holes, cliffs, walls, and other non-walkable boundaries block movement.",
        "Check camera collision and verify the camera does not pass through blocking geometry.",
        "Exercise doors and module transitions without crossing a broken WOK seam.",
        "Record the result and preserve any KotorLiveLogs evidence before marking retail proof.",
    ]


def audit_k2_engine_contract(
    candidate: Path,
    *,
    module_root: str,
    visual_only_room_resrefs: Sequence[str] = (),
) -> dict[str, Any]:
    """Run the all-resource, vanilla-derived K2 engine contract on a MOD.

    The walkmesh-library audit proves the BWM tables.  This second gate also
    checks MDL function pointers/node ``+8`` values, embedded AABB nodes,
    LYT/VIS/ARE/IFO/PTH agreement, and scoped visual-only room exceptions.
    """

    from pykotor.extract.capsule import Capsule
    from src.core.validation.kotor_module_engine_contract import (
        KotorModuleEngineContractRequest,
        validate_kotor_module_engine_contract,
    )

    resources: dict[tuple[str, str], bytes] = {}
    for item in Capsule(candidate):
        name = str(item.resname()).strip().lower()
        extension = str(item.restype().extension).strip().lower()
        if name and extension:
            resources[(name, extension)] = bytes(item.data())
    return validate_kotor_module_engine_contract(
        KotorModuleEngineContractRequest(
            game="K2",
            module_resref=module_root,
            resources=resources,
            visual_only_room_resrefs=tuple(visual_only_room_resrefs),
        )
    ).to_dict()


def stage_candidate(
    *,
    module_root: str,
    candidate: Path,
    game_root: Path = DEFAULT_K2_ROOT,
    evidence_root: Path = DEFAULT_EVIDENCE_ROOT,
    process_checker: Callable[[], bool] = is_swkotor2_running,
    audit_runner: Callable[..., Mapping[str, Any]] = audit_mod,
    engine_audit_runner: Callable[..., Mapping[str, Any]] = audit_k2_engine_contract,
    visual_only_room_resrefs: Sequence[str] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate, preserve evidence, and install exactly one K2 MOD candidate."""

    module_root = _validate_module_root(module_root)
    candidate = candidate.expanduser().resolve()
    game_root = game_root.expanduser().resolve()
    evidence_root = evidence_root.expanduser().resolve()

    if process_checker():
        raise StagingError("swkotor2.exe is running; quit KOTOR 2 before staging a module.")
    if candidate.suffix.lower() != ".mod" or not candidate.is_file():
        raise StagingError(f"Candidate must be an existing .mod file: {candidate}")

    executable = game_root / "swkotor2.exe"
    modules_dir = game_root / "Modules"
    if not executable.is_file():
        raise StagingError(f"KOTOR 2 executable was not found: {executable}")
    if not modules_dir.is_dir():
        raise StagingError(f"KOTOR 2 Modules directory was not found: {modules_dir}")

    installed_path = modules_dir / f"{module_root}.mod"
    cache_path = game_root / "currentgame" / f"{module_root}.mod"
    if _same_path(candidate, installed_path) or _same_path(candidate, cache_path):
        raise StagingError(
            "Candidate must be outside the installed and currentgame destination paths."
        )

    source_record = _file_record(candidate)
    source_hash = str(source_record["sha256"])
    visual_only_rooms = tuple(
        dict.fromkeys(
            _validate_module_root(str(room)).lower()
            for room in tuple(visual_only_room_resrefs or ())
        )
    )
    audit = dict(
        audit_runner(candidate, module=module_root, game="K2", roundtrip=True)
    )
    if not audit.get("audit_pass"):
        errors = audit.get("errors") or ["audit_pass was false"]
        raise StagingError(
            "Candidate failed the current audit_mod structural gate: "
            + "; ".join(str(error) for error in errors)
        )
    engine_contract = dict(
        engine_audit_runner(
            candidate,
            module_root=module_root,
            visual_only_room_resrefs=visual_only_rooms,
        )
    )
    if not engine_contract.get("export_ready"):
        errors = engine_contract.get("blocking_issues") or ["export_ready was false"]
        raise StagingError(
            "Candidate failed the vanilla-derived K2 engine-contract gate: "
            + "; ".join(str(error) for error in errors)
        )

    # Close the largest race window: the potentially expensive structural audit
    # must finish before the game is checked again and any game path is changed.
    if process_checker():
        raise StagingError(
            "swkotor2.exe started during validation; no game files were changed."
        )

    moment = now or datetime.now(timezone.utc)
    timestamp_utc = moment.astimezone(timezone.utc).isoformat()
    evidence_dir = evidence_root / f"{_timestamp_slug(moment)}_{module_root.lower()}"
    if evidence_dir.exists():
        raise StagingError(f"Evidence directory already exists: {evidence_dir}")
    evidence_dir.mkdir(parents=True, exist_ok=False)

    installed_backup: Path | None = None
    cache_backup: Path | None = None
    installed_before = _file_record(installed_path) if installed_path.is_file() else _file_record(None)
    cache_before = _file_record(cache_path) if cache_path.is_file() else _file_record(None)

    temporary_install = modules_dir / f".{module_root}.stage-{os.getpid()}.tmp"
    try:
        if installed_path.is_file():
            installed_backup = evidence_dir / "installed_backup" / installed_path.name
            _verified_copy(
                installed_path,
                installed_backup,
                str(installed_before["sha256"]),
            )

        if cache_path.is_file():
            cache_backup = evidence_dir / "currentgame_cache" / cache_path.name
            cache_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(cache_path), str(cache_backup))
            if cache_path.exists() or _sha256_file(cache_backup) != cache_before["sha256"]:
                raise StagingError(
                    f"Currentgame cache move could not be verified: {cache_path}"
                )

        _verified_copy(candidate, temporary_install, source_hash)
        os.replace(temporary_install, installed_path)
        installed_record = _file_record(installed_path)
        if installed_record["sha256"] != source_hash:
            raise StagingError(f"Installed module hash does not match candidate: {installed_path}")
    except Exception as exc:
        temporary_install.unlink(missing_ok=True)
        rollback_errors: list[str] = []
        if installed_backup is not None and installed_backup.is_file():
            try:
                _verified_copy(
                    installed_backup,
                    installed_path,
                    str(installed_before["sha256"]),
                )
            except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                rollback_errors.append(f"installed module: {rollback_exc}")
        elif not installed_before["path"] and installed_path.is_file():
            try:
                installed_path.unlink()
            except OSError as rollback_exc:  # pragma: no cover - catastrophic I/O
                rollback_errors.append(f"new installed module: {rollback_exc}")

        if cache_backup is not None and cache_backup.is_file():
            try:
                if cache_path.exists():
                    raise StagingError(
                        f"Cannot restore cache because its destination exists: {cache_path}"
                    )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(cache_backup), str(cache_path))
                if _sha256_file(cache_path) != cache_before["sha256"]:
                    raise StagingError(
                        f"Restored cache hash does not match the original: {cache_path}"
                    )
            except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                rollback_errors.append(f"currentgame cache: {rollback_exc}")

        if rollback_errors:
            raise StagingError(
                "Staging failed and rollback was incomplete ("
                + "; ".join(rollback_errors)
                + f"). Evidence remains at {evidence_dir}."
            ) from exc
        raise

    manifest_path = evidence_dir / "staging_manifest.json"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "operation": "stage_k2_manual_warp_candidate",
        "timestamp_utc": timestamp_utc,
        "game": "K2",
        "module_root": module_root,
        "game_root": str(game_root),
        "evidence_directory": str(evidence_dir),
        "manifest_path": str(manifest_path),
        "source": source_record,
        "installed": installed_record,
        "installed_previous": installed_before,
        "installed_backup": _file_record(installed_backup),
        "currentgame_cache_previous": cache_before,
        "currentgame_cache_moved_to": _file_record(cache_backup),
        "structural_audit": audit,
        "engine_contract": engine_contract,
        "visual_only_room_resrefs": list(visual_only_rooms),
        "retail_game_proven": False,
        "manual_warp_checklist": _manual_warp_checklist(module_root),
        "guardrails": {
            "game_was_running": False,
            "ini_modified": False,
            "input_hook_installed": False,
            "game_launched": False,
            "other_modules_modified": False,
            "currentgame_cache_deleted": False,
        },
    }
    _write_json_atomic(manifest_path, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-root", required=True, help="KOTOR module resref to install")
    parser.add_argument("--candidate", type=Path, required=True, help="structural .mod candidate")
    parser.add_argument(
        "--visual-only-room",
        action="append",
        default=[],
        help=(
            "explicit LYT visual partition using the vanilla no-AABB/empty-WOK contract; "
            "repeat for each room"
        ),
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        default=DEFAULT_K2_ROOT,
        help=f"KOTOR 2 installation root (default: {DEFAULT_K2_ROOT})",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
        help=f"timestamped evidence parent (default: {DEFAULT_EVIDENCE_ROOT})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = stage_candidate(
            module_root=args.module_root,
            candidate=args.candidate,
            game_root=args.game_root,
            evidence_root=args.evidence_root,
            visual_only_room_resrefs=tuple(args.visual_only_room),
        )
    except StagingError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
