"""Restore the exact KOTOR 2 state preserved by a manual-warp staging manifest.

Run this only after the user has exited KOTOR 2.  The command refuses to touch
the install when the current module no longer matches the staged candidate,
preserves the post-test ``currentgame`` cache as evidence, restores the prior
module/cache byte-for-byte, and writes a restoration receipt.  It never edits
the game INI, hook DLLs, saves, or any other module.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.stage_k2_manual_warp_candidate import (  # noqa: E402
    StagingError,
    _file_record,
    _sha256_file,
    _validate_module_root,
    _verified_copy,
    _write_json_atomic,
    is_swkotor2_running,
)


class RestorationError(RuntimeError):
    """Raised when a staged K2 module cannot be restored safely."""


def _required_file_record(raw: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise RestorationError(f"Staging manifest has no valid {label} record.")
    record = dict(raw)
    path = record.get("path")
    digest = str(record.get("sha256") or "")
    if path and len(digest) != 64:
        raise RestorationError(f"Staging manifest has an invalid {label} hash.")
    return record


def _existing_record_path(record: Mapping[str, Any], *, label: str) -> Path | None:
    raw_path = record.get("path")
    if not raw_path:
        return None
    path = Path(str(raw_path)).expanduser().resolve()
    if not path.is_file():
        raise RestorationError(f"Preserved {label} file is missing: {path}")
    expected = str(record.get("sha256") or "")
    if _sha256_file(path) != expected:
        raise RestorationError(f"Preserved {label} hash no longer matches: {path}")
    return path


def restore_staged_candidate(
    *,
    manifest_path: Path,
    process_checker: Callable[[], bool] = is_swkotor2_running,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Restore one staged module transaction after validating every input."""

    manifest_path = manifest_path.expanduser().resolve()
    if process_checker():
        raise RestorationError(
            "swkotor2.exe is running; quit KOTOR 2 before restoring the prior module."
        )
    if not manifest_path.is_file():
        raise RestorationError(f"Staging manifest does not exist: {manifest_path}")
    try:
        staged = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RestorationError(f"Could not read staging manifest: {manifest_path}") from exc
    if not isinstance(staged, dict) or staged.get("operation") != "stage_k2_manual_warp_candidate":
        raise RestorationError("The selected JSON is not a K2 manual-warp staging manifest.")
    if str(staged.get("game") or "").upper() != "K2":
        raise RestorationError("The staging manifest is not for KOTOR 2.")

    module_root = _validate_module_root(str(staged.get("module_root") or ""))
    game_root = Path(str(staged.get("game_root") or "")).expanduser().resolve()
    evidence_dir = Path(str(staged.get("evidence_directory") or "")).expanduser().resolve()
    if manifest_path.parent != evidence_dir:
        raise RestorationError("Staging manifest is not inside its recorded evidence directory.")
    executable = game_root / "swkotor2.exe"
    modules_dir = game_root / "Modules"
    if not executable.is_file() or not modules_dir.is_dir():
        raise RestorationError(f"Recorded KOTOR 2 installation is incomplete: {game_root}")

    restoration_path = evidence_dir / "restoration_manifest.json"
    if restoration_path.exists():
        raise RestorationError(f"This staging transaction was already restored: {restoration_path}")

    staged_installed = _required_file_record(staged.get("installed"), label="installed candidate")
    prior_installed = _required_file_record(staged.get("installed_previous"), label="prior module")
    prior_installed_backup = _required_file_record(
        staged.get("installed_backup"), label="prior module backup"
    )
    prior_cache = _required_file_record(
        staged.get("currentgame_cache_previous"), label="prior currentgame cache"
    )
    prior_cache_backup = _required_file_record(
        staged.get("currentgame_cache_moved_to"), label="prior currentgame cache backup"
    )

    installed_path = modules_dir / f"{module_root}.mod"
    cache_path = game_root / "currentgame" / f"{module_root}.mod"
    if not installed_path.is_file():
        raise RestorationError(f"Staged module is no longer installed: {installed_path}")
    if _sha256_file(installed_path) != staged_installed.get("sha256"):
        raise RestorationError(
            "Installed module no longer matches the staged candidate; refusing to overwrite a newer change."
        )

    installed_backup = _existing_record_path(
        prior_installed_backup, label="prior installed module backup"
    )
    cache_backup = _existing_record_path(
        prior_cache_backup, label="prior currentgame cache backup"
    )
    if bool(prior_installed.get("path")) != bool(installed_backup):
        raise RestorationError("Prior module and backup records disagree.")
    if bool(prior_cache.get("path")) != bool(cache_backup):
        raise RestorationError("Prior cache and backup records disagree.")

    # Close the validation race before changing either game path.
    if process_checker():
        raise RestorationError(
            "swkotor2.exe started during restoration validation; no game files were changed."
        )

    moment = now or datetime.now(timezone.utc)
    post_test_cache: Path | None = None
    if cache_path.is_file():
        post_test_cache = evidence_dir / "post_test_currentgame_cache" / cache_path.name
        if post_test_cache.exists():
            raise RestorationError(f"Post-test cache evidence already exists: {post_test_cache}")
        post_test_cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(cache_path), str(post_test_cache))

    temporary_restore = modules_dir / f".{module_root}.restore-{os.getpid()}.tmp"
    try:
        if installed_backup is not None:
            _verified_copy(
                installed_backup,
                temporary_restore,
                str(prior_installed["sha256"]),
            )
            os.replace(temporary_restore, installed_path)
        else:
            installed_path.unlink()

        if cache_backup is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(cache_backup), str(cache_path))
            if _sha256_file(cache_path) != prior_cache["sha256"]:
                raise RestorationError(
                    f"Restored currentgame cache hash does not match: {cache_path}"
                )
    except Exception as exc:
        temporary_restore.unlink(missing_ok=True)
        source = Path(str(staged.get("source", {}).get("path") or ""))
        source_hash = str(staged.get("source", {}).get("sha256") or "")
        rollback_errors: list[str] = []
        try:
            if source.is_file() and _sha256_file(source) == source_hash:
                _verified_copy(source, installed_path, source_hash)
            else:
                rollback_errors.append("candidate source is unavailable for rollback")
        except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
            rollback_errors.append(f"candidate reinstall: {rollback_exc}")
        try:
            if post_test_cache is not None and post_test_cache.is_file() and not cache_path.exists():
                shutil.move(str(post_test_cache), str(cache_path))
        except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
            rollback_errors.append(f"post-test cache: {rollback_exc}")
        if rollback_errors:
            raise RestorationError(
                "Restoration failed and rollback was incomplete: " + "; ".join(rollback_errors)
            ) from exc
        raise

    restored_installed = _file_record(installed_path) if installed_path.is_file() else _file_record(None)
    restored_cache = _file_record(cache_path) if cache_path.is_file() else _file_record(None)
    if restored_installed.get("sha256") != prior_installed.get("sha256"):
        raise RestorationError("Final installed-module state does not match the preserved prior state.")
    if restored_cache.get("sha256") != prior_cache.get("sha256"):
        raise RestorationError("Final currentgame-cache state does not match the preserved prior state.")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "operation": "restore_k2_manual_warp_candidate",
        "timestamp_utc": moment.astimezone(timezone.utc).isoformat(),
        "game": "K2",
        "module_root": module_root,
        "staging_manifest": str(manifest_path),
        "restoration_manifest": str(restoration_path),
        "restored_installed": restored_installed,
        "restored_currentgame_cache": restored_cache,
        "post_test_currentgame_cache": _file_record(post_test_cache),
        "other_modules_modified": False,
        "game_was_running": False,
    }
    _write_json_atomic(restoration_path, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="staging_manifest.json written by stage_k2_manual_warp_candidate.py",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = restore_staged_candidate(manifest_path=args.manifest)
    except (RestorationError, StagingError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
