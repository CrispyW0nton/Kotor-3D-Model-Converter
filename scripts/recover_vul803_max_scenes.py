"""Export forensic vul803 geometry from legacy .MAX scenes via KOTORMax v0.4.2.

This runner is intentionally non-destructive: it copies KOTORMax into the
selected 3ds Max user scripts directory, runs each original scene through
``3dsmaxbatch.exe``, and writes NWMax/KOTORMax ASCII candidates under the
requested output directory.  It never saves the source .MAX file.

KOTORMax is the modern visual-geometry fallback, not the lossless first opener:
legacy NWMax light/reference classes do not all share its superclass contracts.
Use the guarded NWMax 0.8 b60 workflow in ``scripts/kotormax/README.md`` for
authoritative partition export. The machine must have a licensed 3ds Max
installation. Use ``--preflight`` to report readiness without changing it.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterable
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KOTORMAX = ROOT / "Saved" / "ExternalTools" / "kotormax"
DEFAULT_MAXSCRIPT = ROOT / "scripts" / "max2021_mcp" / "kotormax_batch_export.ms"
DEFAULT_SOURCE_ROOT = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Q_SellOut\Extracted"
    r"\LavaPlanet_2011-12-26\LavaPlanet\LavaPlanet\3DsMax_Files"
)
DEFAULT_SANITY_ROOT = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Marius_Things\Extracted"
    r"\NWMAX\NWMAX\NWmax\sanity"
)
DEFAULT_OUTPUT = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\WalkmeshAudit"
    r"\GeneratedCandidates\vul803\MaxExports"
)
DEFAULT_SCENES = (
    DEFAULT_SOURCE_ROOT / "LavaTemple024.max",
    DEFAULT_SOURCE_ROOT / "LavaTemple025Sky.max",
    DEFAULT_SOURCE_ROOT / "LavaTemple023.max",
)

EXPECTED_EXPORTS = {
    "lavatemple023": ("vul803_01a", "vul803_01c", "vul803_01d"),
    "lavatemple024": ("vul803_01b",),
    "lavatemple025sky": ("vul803_01e",),
}


@dataclass
class SceneExport:
    scene: str
    output_dir: str
    command: list[str] = field(default_factory=list)
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    ascii_mdls: list[str] = field(default_factory=list)
    ascii_woks: list[str] = field(default_factory=list)
    report_path: str = ""
    expected_resrefs: list[str] = field(default_factory=list)
    missing_resrefs: list[str] = field(default_factory=list)
    output_hashes: dict[str, str] = field(default_factory=dict)
    source_sha256_before: str = ""
    source_sha256_after: str = ""
    source_untouched: bool = False


@dataclass
class RecoveryReport:
    schema: str = "ghoststudio.vul803-kotormax-recovery.v2"
    run_id: str = ""
    report_path: str = ""
    ok: bool = False
    code: str = "not_run"
    max_batch_executable: str = ""
    max_scripts_dir: str = ""
    kotormax_root: str = ""
    kotormax_revision: str = ""
    original_scenes_untouched: bool = False
    retail_game_tested: bool = False
    scene_exports: list[SceneExport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["scene_exports"] = [asdict(item) for item in self.scene_exports]
        return data


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"), key=lambda item: str(item).lower())
        if path.is_file() and ".git" not in path.parts
    }


def _kotormax_revision(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        revision = str(completed.stdout or "").strip()
        if completed.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            return revision.lower()
    except (OSError, subprocess.SubprocessError):
        pass
    plugin = root / "KOTORMax"
    if not plugin.is_dir():
        return ""
    digest = sha256()
    for relative, file_hash in _directory_manifest(plugin).items():
        digest.update(relative.encode("utf-8"))
        digest.update(file_hash.encode("ascii"))
    return "tree-sha256:" + digest.hexdigest()


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


def _write_report(path: Path, report: RecoveryReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")


def _validate_exported_ascii(path: Path, expected_resref: str) -> str | None:
    if not path.is_file() or path.stat().st_size <= 0:
        return f"{path.name} is missing or empty"
    text = path.read_text(encoding="latin-1", errors="replace")
    lowered = text.lower()
    expected = expected_resref.lower()
    if f"newmodel {expected}" not in lowered:
        return f"{path.name} has no newmodel {expected_resref} declaration"
    if f"donemodel {expected}" not in lowered:
        return f"{path.name} has no donemodel {expected_resref} declaration"
    if "beginmodelgeom" not in lowered or "endmodelgeom" not in lowered:
        return f"{path.name} has an incomplete geometry block"
    return None


def _max_version_from_path(path: Path) -> str:
    match = re.search(r"3ds Max\s+(\d{4})", str(path.parent), flags=re.IGNORECASE)
    return match.group(1) if match else ""


def discover_3dsmax_batch(explicit: str = "") -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return (
            candidate
            if candidate.is_file() and candidate.name.lower() == "3dsmaxbatch.exe"
            else None
        )
    roots = (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Autodesk",)
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(root.glob("3ds Max */3dsmaxbatch.exe"))
    return sorted(candidates, key=lambda item: str(item).lower(), reverse=True)[0] if candidates else None


def default_user_scripts_dir(max_batch: Path) -> Path:
    version = _max_version_from_path(max_batch)
    if not version:
        raise ValueError(f"Cannot infer 3ds Max version from path: {max_batch}")
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    version_root = local / "Autodesk" / "3dsMax" / f"{version} - 64bit" / "ENU"
    existing = sorted(version_root.glob("*/scripts"), key=lambda item: str(item).lower())
    return existing[0] if existing else version_root / "scripts"


def install_kotormax(kotormax_root: Path, scripts_dir: Path) -> None:
    source_plugin = kotormax_root / "KOTORMax"
    source_startup = kotormax_root / "autokotormax.ms"
    if not source_plugin.is_dir() or not source_startup.is_file():
        raise FileNotFoundError(f"KOTORMax v0.4.2 checkout is incomplete: {kotormax_root}")
    startup_dir = scripts_dir / "Startup"
    conflicts = [
        path
        for path in startup_dir.glob("*.ms")
        if path.is_file() and "nwmax" in path.name.lower()
    ]
    if conflicts:
        raise RuntimeError(
            "NWMax and KOTORMax cannot load together. Move this startup script aside first: "
            + ", ".join(str(path) for path in conflicts)
        )
    scripts_dir.mkdir(parents=True, exist_ok=True)
    startup_dir.mkdir(parents=True, exist_ok=True)
    destination_plugin = scripts_dir / "KOTORMax"
    destination_startup = startup_dir / "autokotormax.ms"
    if destination_plugin.exists():
        if not destination_plugin.is_dir() or _directory_manifest(destination_plugin) != _directory_manifest(source_plugin):
            raise RuntimeError(
                "Refusing to merge KOTORMax over a different existing installation: "
                f"{destination_plugin}. Use a clean 3ds Max user scripts directory."
            )
    else:
        shutil.copytree(source_plugin, destination_plugin)
    if destination_startup.exists():
        if not destination_startup.is_file() or _sha256_file(destination_startup) != _sha256_file(source_startup):
            raise RuntimeError(
                "Refusing to replace a different KOTORMax startup script: "
                f"{destination_startup}"
            )
    else:
        shutil.copy2(source_startup, destination_startup)


def _iter_scenes(values: Iterable[str]) -> tuple[Path, ...]:
    raw = tuple(values)
    return tuple(Path(value).expanduser().resolve() for value in raw) if raw else DEFAULT_SCENES


def run(args: argparse.Namespace) -> RecoveryReport:
    report = RecoveryReport(run_id=_new_run_id())
    report.warnings.extend(
        [
            "KOTORMax output is a visual-geometry fallback; use the isolated legacy NWMax bridge for lossless first export.",
            "LavaTemple023's saved whole 01a root contains other historical partitions; batch 01a/c/d exports are forensic and must not be packaged together without partition review.",
            "Late 01b overlaps 354/356 nodes with 01a, while 01d/01e are absent from the surviving ARE roster; these exports are optional evidence, not committed rooms.",
        ]
    )
    output_root = Path(args.output).expanduser().resolve()
    report_path = output_root / "Reports" / f"vul803-kotormax-recovery-{report.run_id}.json"
    report.report_path = str(report_path)
    kotormax_root = Path(args.kotormax).expanduser().resolve()
    report.kotormax_root = str(kotormax_root)
    report.kotormax_revision = _kotormax_revision(kotormax_root)
    scenes = _iter_scenes(args.scene)
    missing = [str(scene) for scene in scenes if not scene.is_file()]
    if missing:
        report.blocking_issues.append("Missing source scene(s): " + ", ".join(missing))
    if not kotormax_root.is_dir():
        report.blocking_issues.append(f"KOTORMax v0.4.2 checkout is missing: {kotormax_root}")
    if not DEFAULT_MAXSCRIPT.is_file():
        report.blocking_issues.append(f"Ghost Studio batch bridge is missing: {DEFAULT_MAXSCRIPT}")

    max_batch = discover_3dsmax_batch(args.max_batch)
    if max_batch is None:
        report.blocking_issues.append(
            "No valid 3dsmaxbatch.exe was found. The proprietary .MAX scene container requires a "
            "licensed 3ds Max runtime; Ghost Studio cannot decode it with MDLOps, PyKotor, Assimp, "
            "or Blender."
        )
    else:
        report.max_batch_executable = str(max_batch)
        try:
            scripts_dir = (
                Path(args.max_scripts_dir).expanduser().resolve()
                if args.max_scripts_dir
                else default_user_scripts_dir(max_batch)
            )
            report.max_scripts_dir = str(scripts_dir)
        except ValueError as exc:
            report.blocking_issues.append(str(exc))

    if report.blocking_issues or args.preflight:
        if report.blocking_issues:
            report.code = (
                "3dsmax_not_installed"
                if max_batch is None
                else "preflight_blocked"
            )
        else:
            report.ok = True
            report.code = "preflight_ready"
        _write_report(report_path, report)
        return report

    try:
        install_kotormax(kotormax_root, Path(report.max_scripts_dir))
    except (OSError, RuntimeError) as exc:
        report.code = "kotormax_install_failed"
        report.blocking_issues.append(str(exc))
        _write_report(report_path, report)
        return report

    run_root = output_root / "Runs" / report.run_id
    run_root.mkdir(parents=True, exist_ok=False)
    timeout_seconds = max(1.0, float(getattr(args, "timeout", 1800.0)))
    for scene in scenes:
        scene_output = run_root / scene.stem
        scene_output.mkdir(parents=True, exist_ok=False)
        source_hash_before = _sha256_file(scene)
        command = [
            str(max_batch),
            str(DEFAULT_MAXSCRIPT),
            "-sceneFile",
            str(scene),
            "-listenerlog",
            str(scene_output / "3dsmax-listener.log"),
            "-log",
            str(scene_output / "3dsmax.log"),
            "-dm",
            "on",
            "-v",
            "3",
        ]
        env = dict(os.environ)
        env["GHOSTSTUDIO_KOTOR_EXPORT_DIR"] = str(scene_output)
        env["GHOSTSTUDIO_KOTOR_ROOT_PATTERN"] = "vul803_01?"
        env["GHOSTSTUDIO_KOTOR_SANITY_DIR"] = str(DEFAULT_SANITY_ROOT)
        env["GHOSTSTUDIO_KOTOR_RECONSTRUCT_ROOMS"] = (
            "vul803_01c;vul803_01d" if scene.stem.lower() == "lavatemple023" else ""
        )
        item = SceneExport(
            scene=str(scene),
            output_dir=str(scene_output),
            command=command,
            expected_resrefs=list(EXPECTED_EXPORTS.get(scene.stem.lower(), ())),
            report_path=str(scene_output / "ghoststudio-kotormax-export.tsv"),
            source_sha256_before=source_hash_before,
        )
        report.scene_exports.append(item)
        try:
            completed = subprocess.run(
                command,
                cwd=str(max_batch.parent),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout_seconds,
            )
            item.returncode = int(completed.returncode)
            item.stdout = str(completed.stdout or "")
            item.stderr = str(completed.stderr or "")
        except subprocess.TimeoutExpired as exc:
            item.returncode = -1
            item.stdout = str(exc.stdout or "")
            item.stderr = f"3ds Max batch export exceeded {timeout_seconds:g} seconds."
        except OSError as exc:
            item.returncode = -1
            item.stderr = f"Could not launch 3ds Max batch: {exc}"

        item.source_sha256_after = _sha256_file(scene)
        item.source_untouched = item.source_sha256_before == item.source_sha256_after
        item.ascii_mdls = [str(path) for path in sorted(scene_output.glob("*.mdl.ascii"))]
        item.ascii_woks = [str(path) for path in sorted(scene_output.glob("*.wok.ascii"))]
        item.output_hashes = {
            str(path): _sha256_file(path)
            for path in sorted(scene_output.glob("*"), key=lambda value: value.name.lower())
            if path.is_file() and path.stat().st_size > 0
        }
        exported_paths = {
            Path(path).name.lower().removesuffix(".mdl.ascii"): Path(path)
            for path in item.ascii_mdls
        }
        item.missing_resrefs = sorted(set(item.expected_resrefs) - set(exported_paths))
        invalid_exports = [
            issue
            for resref in item.expected_resrefs
            if resref in exported_paths
            for issue in [_validate_exported_ascii(exported_paths[resref], resref)]
            if issue is not None
        ]
        export_report = Path(item.report_path)
        if not export_report.is_file() or export_report.stat().st_size <= 0:
            invalid_exports.append("KOTORMax export evidence TSV is missing or empty")
        if not item.source_untouched:
            report.blocking_issues.append(f"Source scene changed during export: {scene}")
        if item.returncode != 0 or item.missing_resrefs or invalid_exports:
            failure_details = [*item.missing_resrefs, *invalid_exports]
            if item.returncode != 0:
                failure_details.append(
                    item.stderr.strip() or f"3ds Max batch exited with code {item.returncode}."
                )
            report.blocking_issues.append(
                f"KOTORMax batch export failed or omitted {scene.name} room(s): "
                + "; ".join(failure_details or ["unknown batch failure"])
            )

    report.original_scenes_untouched = bool(report.scene_exports) and all(
        item.source_untouched for item in report.scene_exports
    )
    report.ok = not report.blocking_issues
    report.code = "forensic_ascii_candidates_ready" if report.ok else "max_export_failed"
    _write_report(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-batch", default="", help="Explicit 3dsmaxbatch.exe path.")
    parser.add_argument("--max-scripts-dir", default="", help="Explicit 3ds Max user scripts folder.")
    parser.add_argument("--kotormax", default=str(DEFAULT_KOTORMAX))
    parser.add_argument("--scene", action="append", default=[])
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="Maximum seconds allowed for each 3ds Max batch scene export.",
    )
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
