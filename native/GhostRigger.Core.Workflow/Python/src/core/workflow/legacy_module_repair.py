"""Non-destructive repair workflow for recovered KOTOR module room assets.

The old community-module bundles handled by Map Studio often contain binary
room models written by early MDLOps releases, NWMax ASCII sources, or WOK files
whose derived perimeter tables are no longer accepted by current tools.  This
module owns the multi-step conversion transaction:

* copy the source MDL/MDX/WOK into an isolated scratch directory;
* decompile binary input with MDLOps, including the walkmesh;
* compile a separate K1 or K2 binary pair;
* normalise the generated filenames into a target worktree;
* compare the output structure with both the input and vanilla-derived engine
  invariants before it may be packaged.

It deliberately does not edit the downloaded source tree and does not claim a
retail-game proof.  A structurally accepted output remains an export candidate
until a human completes the install/warp test in the matching game.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable


_SUPPORTED_GAMES = frozenset({"K1", "K2"})


@dataclass(frozen=True)
class LegacyRoomRepairRequest:
    """One immutable room-model conversion request."""

    room_resref: str
    source_mdl: str
    source_mdx: str = ""
    source_wok: str = ""
    target_game: str = "K2"
    output_dir: str = ""
    mdlops_executable: str = ""
    overwrite: bool = False


@dataclass
class LegacyRoomRepairResult:
    """Files and evidence produced by :func:`repair_legacy_room_with_mdlops`."""

    ok: bool = False
    room_resref: str = ""
    target_game: str = ""
    output_mdl: str = ""
    output_mdx: str = ""
    output_wok: str = ""
    manifest_path: str = ""
    source_hashes: dict[str, str] = field(default_factory=dict)
    output_hashes: dict[str, str] = field(default_factory=dict)
    source_fingerprints: dict[str, Any] = field(default_factory=dict)
    output_fingerprints: dict[str, Any] = field(default_factory=dict)
    commands: list[list[str]] = field(default_factory=list)
    command_logs: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    code: str = "not_run"
    message: str = ""
    game_tested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LegacyModuleCandidateRequest:
    """Assemble repaired room assets and preserved metadata into one MOD."""

    module_resref: str
    target_game: str
    repaired_rooms_dir: str
    output_dir: str
    source_mod: str = ""
    source_are: str = ""
    source_git: str = ""
    source_ifo: str = ""
    source_lyt: str = ""
    source_vis: str = ""
    source_pth: str = ""
    extra_resource_paths: tuple[str, ...] = ()
    extra_resource_dirs: tuple[str, ...] = ()
    # Vanilla modules may split one area into a playable collision room plus
    # visual-only LYT partitions.  Those partitions still require an
    # MDL/MDX/WOK triplet, but retail examples use no embedded AABB and the
    # canonical empty 136-byte WOK.  Keep the exception explicit per room so a
    # playable room can never silently bypass the strict collision contract.
    visual_only_room_resrefs: tuple[str, ...] = ()
    # Recovered source capsules often contain a stale PTH for a smaller room
    # set.  Callers changing the LYT/WOK set must be able to rebuild it from
    # the final combined walkmesh instead of preserving incompatible bytes.
    regenerate_pth: bool = False
    wok_coordinate_space: str = "room_local"
    # A WOK transition stores an integer index into the LYT room ordering that
    # existed when the walkmesh was authored.  When a recovery deliberately
    # trims that source layout, retained destinations must be remapped to the
    # new ordering and destinations for omitted rooms must be removed.  Leave
    # this empty when the input WOKs were already authored against the final
    # LYT supplied to this request.
    source_transition_room_resrefs: tuple[str, ...] = ()
    # A recovered community module may have been cloned from a stock shell and
    # still carry that donor's 16-byte Mod_ID.  Reusing it lets two installed
    # modules claim the same runtime/save identity.  Keep stock preservation
    # available for same-module repairs, but make regeneration an explicit
    # policy for renamed or recovered community candidates.
    regenerate_module_id: bool = False
    overwrite: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LegacyModuleCandidateResult:
    """Install candidate plus structural/readback evidence."""

    ok: bool = False
    module_resref: str = ""
    target_game: str = ""
    module_path: str = ""
    resources_dir: str = ""
    manifest_path: str = ""
    room_resrefs: list[str] = field(default_factory=list)
    source_transition_room_resrefs: list[str] = field(default_factory=list)
    generated_resources: list[str] = field(default_factory=list)
    preserved_resources: list[str] = field(default_factory=list)
    bundled_resources: list[dict[str, Any]] = field(default_factory=list)
    walkmesh_transition_repairs: list[dict[str, Any]] = field(default_factory=list)
    pathing_metadata: dict[str, Any] = field(default_factory=dict)
    module_identity: dict[str, Any] = field(default_factory=dict)
    engine_contract: dict[str, Any] = field(default_factory=dict)
    readback_contract: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    code: str = "not_run"
    message: str = ""
    game_tested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_resref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "." in text:
        text = text.rsplit(".", 1)[0]
    return text[:16]


def _normalise_game(value: Any) -> str:
    game = str(value or "").strip().upper()
    if game not in _SUPPORTED_GAMES:
        raise ValueError(f"Unsupported target game {game or '(missing)'!r}; use K1 or K2.")
    return game


def remap_walkmesh_transition_destinations(
    wok: Any,
    *,
    source_room_resrefs: Iterable[str],
    target_room_resrefs: Iterable[str],
) -> list[dict[str, Any]]:
    """Remap WOK edge transitions from one LYT room ordering to another.

    Odyssey serializes a transition destination as a zero-based LYT room
    index, not a room resref.  A filtered recovery therefore cannot copy those
    integers blindly.  Existing destinations retained by the target layout are
    translated to the target index; transitions to omitted rooms are cleared.
    Invalid source indices are rejected because guessing would create a portal
    into an unrelated room.
    """

    source_rooms = tuple(_normalise_resref(room) for room in source_room_resrefs)
    target_rooms = tuple(_normalise_resref(room) for room in target_room_resrefs)
    if not source_rooms or any(not room for room in source_rooms):
        raise ValueError("Source transition room ordering contains an empty room resref.")
    if not target_rooms or any(not room for room in target_rooms):
        raise ValueError("Target transition room ordering contains an empty room resref.")
    if len(set(source_rooms)) != len(source_rooms):
        raise ValueError("Source transition room ordering contains duplicate room resrefs.")
    if len(set(target_rooms)) != len(target_rooms):
        raise ValueError("Target transition room ordering contains duplicate room resrefs.")

    target_indices = {room: index for index, room in enumerate(target_rooms)}
    rows: list[dict[str, Any]] = []
    for face_index, face in enumerate(tuple(getattr(wok, "faces", ()) or ())):
        for local_edge in range(3):
            attribute = f"trans{local_edge + 1}"
            source_index = int(getattr(face, attribute, -1))
            if source_index < 0:
                continue
            if source_index >= len(source_rooms):
                raise ValueError(
                    f"WOK face {face_index} edge {local_edge} transition index {source_index} "
                    f"is outside the {len(source_rooms)}-room source LYT ordering."
                )
            source_target = source_rooms[source_index]
            target_index = target_indices.get(source_target, -1)
            action = "preserved" if target_index == source_index else ("remapped" if target_index >= 0 else "dropped")
            if target_index != source_index:
                setattr(face, attribute, target_index)
            rows.append(
                {
                    "face_index": face_index,
                    "local_edge": local_edge,
                    "directed_edge": face_index * 3 + local_edge,
                    "source_index": source_index,
                    "source_target": source_target,
                    "target_index": target_index,
                    "action": action,
                }
            )
    return rows


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_binary_mdl(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(4) == b"\x00\x00\x00\x00"


def _validation_rows(report: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in tuple(getattr(report, "issues", ()) or ()):
        severity = getattr(getattr(issue, "severity", None), "value", getattr(issue, "severity", ""))
        rows.append(
            {
                "severity": str(severity or "").lower(),
                "code": str(getattr(issue, "code", "") or ""),
                "message": str(getattr(issue, "message", issue) or ""),
                "details": dict(getattr(issue, "details", {}) or {}),
            }
        )
    return rows


def _blocking_rows(rows: Iterable[dict[str, Any]]) -> list[str]:
    return [
        f"{row.get('code')}: {row.get('message')}".strip(": ")
        for row in rows
        if str(row.get("severity") or "").lower() == "blocking"
    ]


def _inspect_room(
    room_resref: str,
    mdl_path: Path,
    mdx_path: Path,
    wok_path: Path | None,
    *,
    game: str,
) -> tuple[dict[str, Any], list[str]]:
    # Deferred imports keep the Workflow package importable without forcing the
    # full PyKotor/validation payload into lightweight product surfaces.
    from src.core.validation.kotor_module_engine_contract import (
        inspect_raw_mdl_structure,
        inspect_raw_wok_structure,
    )

    mdl_fingerprint, mdl_report = inspect_raw_mdl_structure(
        room_resref,
        mdl_path.read_bytes(),
        mdx_path.read_bytes(),
        game=game,
    )
    mdl_rows = _validation_rows(mdl_report)
    result: dict[str, Any] = {
        "mdl": asdict(mdl_fingerprint),
        "mdl_issues": mdl_rows,
    }
    blocking = _blocking_rows(mdl_rows)
    if wok_path is not None and wok_path.is_file():
        wok_fingerprint, wok_report = inspect_raw_wok_structure(room_resref, wok_path.read_bytes())
        wok_rows = _validation_rows(wok_report)
        result["wok"] = asdict(wok_fingerprint)
        result["wok_issues"] = wok_rows
        blocking.extend(_blocking_rows(wok_rows))
    return result, blocking


def _run_mdlops(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "command": list(command),
        "cwd": str(cwd),
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
    }


def _single_generated(directory: Path, pattern: str, *, label: str) -> Path:
    matches = sorted(directory.glob(pattern), key=lambda item: item.name.lower())
    if len(matches) != 1:
        names = ", ".join(item.name for item in matches) or "none"
        raise RuntimeError(f"MDLOps generated {len(matches)} {label} candidate(s): {names}.")
    return matches[0]


def _inject_embedded_aabb_from_wok(ascii_mdl: Path, source_wok: Path, room_resref: str) -> bool:
    """Add a controller-free AABB mesh when a legacy room omitted one.

    MDLOps faithfully preserves a missing embedded room walkmesh, but KOTOR's
    area loader requires an AABB node in every playable room MDL.  Build the
    node from the same WOK that MDLOps is recompiling, then let MDLOps generate
    the binary AABB tree during its normal target-game compile pass.
    """

    from src.core.modules.module_format import WOKData

    model_text = ascii_mdl.read_text(encoding="latin-1", errors="replace")
    model_lines = model_text.splitlines()
    for line in model_lines:
        parts = line.strip().lower().split()
        if len(parts) >= 2 and parts[0] == "node" and parts[1] == "aabb":
            return False

    insert_at = next(
        (index for index, line in enumerate(model_lines) if line.strip().lower().startswith("endmodelgeom")),
        None,
    )
    if insert_at is None:
        raise ValueError(f"MDLOps ASCII model has no endmodelgeom marker: {ascii_mdl}")

    wok = WOKData.from_bytes(source_wok.read_bytes())
    vertices = tuple(getattr(wok, "verts", ()) or ())
    faces = tuple(getattr(wok, "faces", ()) or ())
    if not vertices or not faces:
        raise ValueError(f"Cannot embed an AABB node from empty room WOK: {source_wok}")

    room = _normalise_resref(room_resref)
    node_lines = [
        f"node aabb {room}_wg",
        f"  parent {room}",
        "  render 0",
        "  shadow 0",
        "  bitmap NULL",
        f"  verts {len(vertices)}",
    ]
    node_lines.extend(
        f"    {float(vertex[0]):.9g} {float(vertex[1]):.9g} {float(vertex[2]):.9g}"
        for vertex in vertices
    )
    node_lines.append(f"  faces {len(faces)}")
    node_lines.extend(
        "    "
        f"{int(face.v1)} {int(face.v2)} {int(face.v3)} 1 0 0 0 {int(getattr(face, 'surface', 1))}"
        for face in faces
    )
    node_lines.append("endnode")
    model_lines[insert_at:insert_at] = [*node_lines, ""]
    ascii_mdl.write_text("\n".join(model_lines) + "\n", encoding="latin-1")
    return True


def _parity_issues(source: dict[str, Any], output: dict[str, Any], *, has_source_wok: bool) -> list[str]:
    issues: list[str] = []
    source_mdl = dict(source.get("mdl") or {})
    output_mdl = dict(output.get("mdl") or {})
    source_aabb_count = int(source_mdl.get("aabb_node_count", 0) or 0)
    output_aabb_count = int(output_mdl.get("aabb_node_count", 0) or 0)
    repaired_missing_aabb = source_aabb_count == 0 and output_aabb_count == 1
    for field_name in ("declared_node_count", "visited_node_count"):
        source_value = source_mdl.get(field_name)
        output_value = output_mdl.get(field_name)
        expected = int(source_value) + (1 if repaired_missing_aabb else 0) if source_value is not None else None
        if expected is not None and output_value is not None and expected != int(output_value):
            issues.append(
                f"MDLOps changed room {field_name} from {source_value} to {output_value}; donor/manual review is required."
            )
    if not repaired_missing_aabb and source_aabb_count != output_aabb_count:
        issues.append(
            "MDLOps changed room aabb_node_count "
            f"from {source_aabb_count} to {output_aabb_count}; donor/manual review is required."
        )
    source_controllers = source_mdl.get("controller_count")
    output_controllers = output_mdl.get("controller_count")
    if (
        source_controllers is not None
        and output_controllers is not None
        and int(source_controllers) != int(output_controllers)
    ):
        issues.append(
            "MDLOps changed room controller_count "
            f"from {source_controllers} to {output_controllers}; donor/manual review is required."
        )
    if int(output_mdl.get("nonzero_node_plus_8", 0) or 0) != 0:
        issues.append("The compiled room contains nonzero node-header +8 runtime pointers.")
    if int(output_mdl.get("aabb_node_count", 0) or 0) < 1:
        issues.append("The compiled room has no embedded AABB walkmesh node.")

    if has_source_wok:
        source_wok = dict(source.get("wok") or {})
        output_wok = dict(output.get("wok") or {})
        for field_name in ("vertex_count", "face_count", "walkable_face_count"):
            source_value = source_wok.get(field_name)
            output_value = output_wok.get(field_name)
            if source_value is not None and output_value is not None and int(source_value) != int(output_value):
                issues.append(
                    f"MDLOps changed WOK {field_name} from {source_value} to {output_value}; containment review is required."
                )
        if source_wok.get("material_histogram") and source_wok.get("material_histogram") != output_wok.get("material_histogram"):
            issues.append("MDLOps changed the WOK material histogram; walkable/non-walk surfaces require review.")
    return issues


def _write_manifest(path: Path, result: LegacyRoomRepairResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_result(path: Path, result: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repair_legacy_room_with_mdlops(request: LegacyRoomRepairRequest) -> LegacyRoomRepairResult:
    """Create one target-game room candidate without mutating its sources."""

    raw_room = str(request.room_resref or Path(request.source_mdl).stem).strip()
    if "." in raw_room:
        raw_room = raw_room.rsplit(".", 1)[0]
    room = _normalise_resref(raw_room)
    result = LegacyRoomRepairResult(room_resref=room)
    try:
        game = _normalise_game(request.target_game)
    except ValueError as exc:
        result.blocking_issues.append(str(exc))
        result.code = "invalid_request"
        result.message = str(exc)
        return result
    result.target_game = game

    source_mdl = Path(request.source_mdl).expanduser().resolve()
    source_mdx = Path(request.source_mdx).expanduser().resolve() if request.source_mdx else source_mdl.with_suffix(".mdx")
    source_wok = Path(request.source_wok).expanduser().resolve() if request.source_wok else source_mdl.with_suffix(".wok")
    mdlops = Path(request.mdlops_executable).expanduser().resolve()
    output_dir = Path(request.output_dir).expanduser().resolve()
    manifest_path = output_dir / f"{room}.{game.lower()}.mdlops-repair.json"
    result.manifest_path = str(manifest_path)

    required_paths = (("source MDL", source_mdl), ("source MDX", source_mdx), ("MDLOps executable", mdlops))
    for label, path in required_paths:
        if not path.is_file():
            result.blocking_issues.append(f"{label} does not exist: {path}")
    if not room:
        result.blocking_issues.append("Room resref is empty.")
    if len(raw_room) > 16:
        result.blocking_issues.append(f"Room resref {raw_room!r} exceeds the 16-character Odyssey limit.")
    if result.blocking_issues:
        result.code = "input_missing"
        result.message = "Legacy room repair input is incomplete."
        _write_manifest(manifest_path, result)
        return result

    output_mdl = output_dir / f"{room}.mdl"
    output_mdx = output_dir / f"{room}.mdx"
    output_wok = output_dir / f"{room}.wok"
    result.output_mdl = str(output_mdl)
    result.output_mdx = str(output_mdx)
    result.output_wok = str(output_wok) if source_wok.is_file() else ""
    for path in (output_mdl, output_mdx, output_wok if source_wok.is_file() else None):
        if path is not None and path.exists() and not request.overwrite:
            result.blocking_issues.append(f"Output exists and overwrite is disabled: {path}")
    if result.blocking_issues:
        result.code = "output_exists"
        result.message = "Legacy room repair would overwrite an existing candidate."
        _write_manifest(manifest_path, result)
        return result

    source_paths = {"mdl": source_mdl, "mdx": source_mdx}
    if source_wok.is_file():
        source_paths["wok"] = source_wok
    result.source_hashes = {kind: _hash_file(path) for kind, path in source_paths.items()}

    source_binary = _is_binary_mdl(source_mdl)
    source_game = game
    if source_binary:
        header = source_mdl.read_bytes()[:20]
        if len(header) >= 16:
            pointer = int.from_bytes(header[12:16], "little")
            source_game = "K1" if pointer == 4_273_776 else "K2" if pointer == 4_285_200 else game
        try:
            result.source_fingerprints, _source_blocking = _inspect_room(
                room,
                source_mdl,
                source_mdx,
                source_wok if source_wok.is_file() else None,
                game=source_game,
            )
        except Exception as exc:
            result.warnings.append(f"Source structural inspection could not complete: {exc}")

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=f"ghoststudio-{room}-{game.lower()}-") as temp_text:
            scratch = Path(temp_text)
            scratch_mdl = scratch / source_mdl.name
            scratch_mdx = scratch / source_mdx.name
            shutil.copy2(source_mdl, scratch_mdl)
            shutil.copy2(source_mdx, scratch_mdx)
            if source_wok.is_file():
                shutil.copy2(source_wok, scratch / source_wok.name)

            ascii_mdl = scratch_mdl
            if source_binary:
                # MDLOps 1.0.2 processes a same-stem WOK automatically.  Its
                # help text advertises --walkmesh, but the packaged Perl option
                # parser does not register that switch consistently.  The
                # smooth-group pass is deterministic and matches the modern
                # compatibility workflow used for these recovered binaries.
                command = [str(mdlops), "--smoothgroups", scratch_mdl.name]
                result.commands.append(command)
                log = _run_mdlops(command, cwd=scratch)
                result.command_logs.append(log)
                if int(log["returncode"]) != 0:
                    raise RuntimeError(
                        f"MDLOps decompile failed with exit code {log['returncode']}: "
                        f"{str(log['stderr'] or log['stdout']).strip()}"
                    )
                ascii_mdl = _single_generated(scratch, f"{scratch_mdl.stem}-ascii.mdl", label="ASCII MDL")
                if source_wok.is_file():
                    _single_generated(scratch, f"{scratch_mdl.stem}-ascii.wok", label="ASCII WOK")
                    if _inject_embedded_aabb_from_wok(ascii_mdl, source_wok, room):
                        result.warnings.append(
                            "The legacy room MDL omitted its required embedded AABB node; "
                            "the candidate embeds the source WOK as a controller-free AABB mesh."
                        )

            target_flag = "-k1" if game == "K1" else "-k2"
            command = [str(mdlops), target_flag, "--weight", "area", ascii_mdl.name]
            result.commands.append(command)
            log = _run_mdlops(command, cwd=scratch)
            result.command_logs.append(log)
            if int(log["returncode"]) != 0:
                raise RuntimeError(
                    f"MDLOps {game} compile failed with exit code {log['returncode']}: "
                    f"{str(log['stderr'] or log['stdout']).strip()}"
                )

            compiled_mdl = _single_generated(scratch, f"{ascii_mdl.stem}-{game.lower()}-bin.mdl", label=f"{game} MDL")
            compiled_mdx = _single_generated(scratch, f"{ascii_mdl.stem}-{game.lower()}-bin.mdx", label=f"{game} MDX")
            compiled_wok: Path | None = None
            if source_wok.is_file():
                compiled_wok = _single_generated(scratch, f"{ascii_mdl.stem}-bin.wok", label="binary WOK")

            candidate_fingerprints, candidate_blocking = _inspect_room(
                room,
                compiled_mdl,
                compiled_mdx,
                compiled_wok,
                game=game,
            )
            result.output_fingerprints = candidate_fingerprints
            result.blocking_issues.extend(candidate_blocking)
            if result.source_fingerprints:
                result.blocking_issues.extend(
                    _parity_issues(
                        result.source_fingerprints,
                        candidate_fingerprints,
                        has_source_wok=source_wok.is_file(),
                    )
                )
            if result.blocking_issues:
                raise RuntimeError("; ".join(result.blocking_issues))

            shutil.copy2(compiled_mdl, output_mdl)
            shutil.copy2(compiled_mdx, output_mdx)
            if compiled_wok is not None:
                shutil.copy2(compiled_wok, output_wok)

        # Prove the immutable input files did not change while MDLOps worked.
        current_source_hashes = {kind: _hash_file(path) for kind, path in source_paths.items()}
        if current_source_hashes != result.source_hashes:
            result.blocking_issues.append("A source room file changed during the isolated MDLOps transaction.")
            raise RuntimeError(result.blocking_issues[-1])
        output_paths = {"mdl": output_mdl, "mdx": output_mdx}
        if source_wok.is_file():
            output_paths["wok"] = output_wok
        result.output_hashes = {kind: _hash_file(path) for kind, path in output_paths.items()}
        result.ok = True
        result.code = "structural_candidate_ready"
        result.message = (
            f"MDLOps produced a structurally accepted {game} candidate for {room}; "
            "a retail install/warp proof is still required."
        )
    except Exception as exc:
        if not result.blocking_issues:
            result.blocking_issues.append(str(exc))
        result.ok = False
        result.code = "mdlops_or_validation_failed"
        result.message = f"Legacy room repair failed for {room}: {exc}"
        for path in (output_mdl, output_mdx, output_wok):
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                pass
    finally:
        _write_manifest(manifest_path, result)
    return result


def _capsule_resources(path: Path) -> dict[tuple[str, str], bytes]:
    from pykotor.extract.capsule import LazyCapsule

    resources: dict[tuple[str, str], bytes] = {}
    capsule = LazyCapsule(path)
    for item in capsule:
        restype = item.restype()
        extension = str(getattr(restype, "extension", "") or "").lower()
        resref = _normalise_resref(item.resname())
        if not resref or not extension:
            continue
        data = capsule.resource(item.resname(), restype)
        if data is not None:
            resources[(resref, extension)] = bytes(data)
    return resources


def _first_resource(resources: dict[tuple[str, str], bytes], restype: str) -> bytes | None:
    matches = [data for (resref, extension), data in sorted(resources.items()) if extension == restype]
    return matches[0] if matches else None


def _module_resource(
    resources: dict[tuple[str, str], bytes],
    module_resref: str,
    restype: str,
    *,
    fallback_resref: str = "",
) -> tuple[bytes | None, str, bool]:
    """Resolve one capsule resource without silently choosing an ambiguity.

    The requested module resref is authoritative.  A single differently named
    resource is recoverable (several old releases contain a corrupt IFO/ARE
    name), but multiple candidates require a human donor decision.
    """

    wanted = _normalise_resref(fallback_resref or module_resref)
    direct = resources.get((wanted, restype))
    if direct is not None:
        return direct, wanted, False
    matches = [
        (resref, data)
        for (resref, extension), data in sorted(resources.items())
        if extension == restype
    ]
    if not matches:
        return None, "", False
    if len(matches) > 1:
        names = ", ".join(f"{resref}.{restype}" for resref, _data in matches)
        raise ValueError(
            f"Source MOD contains multiple {restype.upper()} candidates but no "
            f"{wanted}.{restype}: {names}. Select an explicit source file."
        )
    return matches[0][1], matches[0][0], True


def _explicit_resource(path_text: str, *, label: str) -> tuple[bytes | None, Path | None]:
    if not str(path_text or "").strip():
        return None, None
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Explicit {label} source does not exist: {path}")
    return path.read_bytes(), path


def _iter_extra_resource_paths(paths: Iterable[str], directories: Iterable[str]) -> Iterable[Path]:
    for raw_path in paths:
        yield Path(raw_path).expanduser().resolve()
    for raw_directory in directories:
        directory = Path(raw_directory).expanduser().resolve()
        if not directory.is_dir():
            raise FileNotFoundError(f"Extra module resource directory does not exist: {directory}")
        yield from sorted(
            (path for path in directory.rglob("*") if path.is_file()),
            key=lambda path: str(path).lower(),
        )


def _normalised_vis_bytes(source: bytes | None, rooms: tuple[str, ...]) -> tuple[bytes, bool]:
    from src.core.modules.module_format import VISData

    source_text = bytes(source or b"").decode("latin-1", errors="replace")
    vis = VISData.from_text(source_text) if source_text.strip() else VISData()
    room_set = set(rooms)
    normalised: dict[str, list[str]] = {
        room: sorted(
            {
                _normalise_resref(target)
                for target in tuple(vis.visibility.get(room, ()) or ())
                if _normalise_resref(target) in room_set and _normalise_resref(target) != room
            }
        )
        for room in rooms
    }
    for room, targets in tuple(normalised.items()):
        for target in tuple(targets):
            if room not in normalised[target]:
                normalised[target].append(room)
                normalised[target].sort()
    if len(rooms) > 1 and not any(normalised.values()):
        normalised = {room: [target for target in rooms if target != room] for room in rooms}
    vis.visibility = normalised
    output = vis.to_text().encode("latin-1")
    return output, output != bytes(source or b"")


def _room_wok_module_offset(room: Any, coordinate_space: str) -> tuple[float, float, float]:
    """Return the one allowed WOK-to-module translation for a LYT room row."""

    module_space_names = {
        "module",
        "module_space",
        "area",
        "area_space",
        "world",
        "world_space",
    }
    if str(coordinate_space or "room_local").strip().lower() in module_space_names:
        return (0.0, 0.0, 0.0)
    return (
        float(getattr(room, "x", 0.0)),
        float(getattr(room, "y", 0.0)),
        float(getattr(room, "z", 0.0)),
    )


def _combined_room_wok(
    rooms: tuple[Any, ...],
    room_woks: dict[str, Any],
    *,
    coordinate_space: str,
) -> Any:
    from src.core.modules.module_format import WOKData, WOKFace

    combined = WOKData(name="legacy_module_combined")
    for room in rooms:
        room_name = _normalise_resref(getattr(room, "model", ""))
        source = room_woks[room_name]
        vertex_offset = len(combined.verts)
        offset = _room_wok_module_offset(room, coordinate_space)
        combined.verts.extend(
            (
                float(vertex[0]) + offset[0],
                float(vertex[1]) + offset[1],
                float(vertex[2]) + offset[2],
            )
            for vertex in tuple(source.verts or ())
        )
        for face in tuple(source.faces or ()):
            combined.faces.append(
                WOKFace(
                    int(face.v1) + vertex_offset,
                    int(face.v2) + vertex_offset,
                    int(face.v3) + vertex_offset,
                    int(face.surface),
                    -1,
                    -1,
                    -1,
                    int(getattr(face, "trans1", -1)),
                    int(getattr(face, "trans2", -1)),
                    int(getattr(face, "trans3", -1)),
                )
            )
    combined.rebuild_adjacencies()
    return combined


def _fallback_entry_point(combined_wok: Any, module_resref: str) -> Any:
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.module_format import WALKABLE_IDS

    for face in tuple(getattr(combined_wok, "faces", ()) or ()):
        if int(getattr(face, "surface", -1)) not in WALKABLE_IDS:
            continue
        vertices = tuple(getattr(combined_wok, "verts", ()) or ())
        indices = (int(face.v1), int(face.v2), int(face.v3))
        if any(index < 0 or index >= len(vertices) for index in indices):
            continue
        point = tuple(sum(float(vertices[index][axis]) for index in indices) / 3.0 for axis in range(3))
        return ModuleEntryPoint(area_resref=module_resref, position=point, facing=0.0)
    return ModuleEntryPoint(area_resref=module_resref, position=(0.0, 0.0, 0.0), facing=0.0)


def _source_entry_point(source_ifo: bytes | None, fallback: Any, module_resref: str) -> Any:
    from src.core.modules.authored_module_objects import ModuleEntryPoint

    if not source_ifo:
        return fallback
    from pykotor.resource.formats.gff import read_gff

    root = read_gff(source_ifo).root
    direction_x = float(root.acquire("Mod_Entry_Dir_X", 1.0) or 0.0)
    direction_y = float(root.acquire("Mod_Entry_Dir_Y", 0.0) or 0.0)
    facing = 0.0 if abs(direction_x) + abs(direction_y) <= 1.0e-12 else math.atan2(direction_y, direction_x)
    return ModuleEntryPoint(
        area_resref=module_resref,
        position=(
            float(root.acquire("Mod_Entry_X", fallback.position[0]) or 0.0),
            float(root.acquire("Mod_Entry_Y", fallback.position[1]) or 0.0),
            float(root.acquire("Mod_Entry_Z", fallback.position[2]) or 0.0),
        ),
        facing=facing,
    )


def _patch_legacy_ifo_module_id(
    data: bytes,
    module_resref: str,
    *,
    regenerate: bool,
) -> tuple[bytes, dict[str, Any]]:
    """Apply the explicit legacy-candidate module identity policy.

    Entry routing and script hooks are handled separately.  This helper
    changes only ``Mod_ID`` when regeneration is requested, which prevents a
    recovered/renamed module from retaining a stock donor's runtime identity.
    """

    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from src.core.modules.authored_module_metadata import authored_module_id_bytes

    raw = bytes(data or b"")
    if not raw:
        raise ValueError("A serialized IFO is required before applying module identity policy.")
    gff = read_gff(raw)
    current = bytes(gff.root.get("Mod_ID") or b"")
    expected = authored_module_id_bytes(module_resref)
    changed = bool(regenerate and current != expected)
    if changed:
        gff.root.set_binary("Mod_ID", expected)
        raw = bytes_gff(gff)
    final = expected if regenerate else current
    if len(final) != 16:
        raise ValueError(
            f"module.ifo Mod_ID must be 16 bytes after identity policy; found {len(final)}."
        )
    return raw, {
        "policy": "regenerate_for_module_resref" if regenerate else "preserve_source",
        "module_resref": _normalise_resref(module_resref),
        "source_mod_id_hex": current.hex(),
        "expected_authored_mod_id_hex": expected.hex(),
        "final_mod_id_hex": final.hex(),
        "changed": changed,
    }


def _stage_resource_bytes(resources_dir: Path, resources: dict[tuple[str, str], bytes]) -> None:
    resources_dir.mkdir(parents=True, exist_ok=True)
    for (resref, restype), data in sorted(resources.items()):
        (resources_dir / f"{resref}.{restype}").write_bytes(data)


def build_legacy_module_candidate(request: LegacyModuleCandidateRequest) -> LegacyModuleCandidateResult:
    """Build a self-contained structural candidate from repaired legacy assets."""

    raw_module_resref = str(request.module_resref or "").strip()
    if "." in raw_module_resref:
        raw_module_resref = raw_module_resref.rsplit(".", 1)[0]
    module_resref = _normalise_resref(raw_module_resref)
    result = LegacyModuleCandidateResult(module_resref=module_resref)
    try:
        game = _normalise_game(request.target_game)
    except ValueError as exc:
        result.blocking_issues.append(str(exc))
        result.code = "invalid_request"
        result.message = str(exc)
        return result
    result.target_game = game
    output_root = Path(request.output_dir).expanduser().resolve()
    modules_dir = output_root / "Modules"
    resources_dir = output_root / "Resources"
    module_path = modules_dir / f"{module_resref}.mod"
    manifest_path = output_root / f"{module_resref}.{game.lower()}.module-repair.json"
    result.module_path = str(module_path)
    result.resources_dir = str(resources_dir)
    result.manifest_path = str(manifest_path)

    if not module_resref:
        result.blocking_issues.append("Module resref is empty.")
    if len(raw_module_resref) > 16:
        result.blocking_issues.append(
            f"Module resref {raw_module_resref!r} exceeds the 16-character Odyssey limit."
        )
    if module_path.exists() and not request.overwrite:
        result.blocking_issues.append(f"Output exists and overwrite is disabled: {module_path}")
    room_dir = Path(request.repaired_rooms_dir).expanduser().resolve()
    if not room_dir.is_dir():
        result.blocking_issues.append(f"Repaired room directory does not exist: {room_dir}")
    if result.blocking_issues:
        result.code = "input_missing"
        result.message = "Legacy module candidate input is incomplete."
        _write_json_result(manifest_path, result)
        return result

    try:
        from pykotor.resource.formats.erf import ERF, ERFType, write_erf
        from pykotor.resource.type import ResourceType
        from src.core.modules.authored_module_metadata import (
            AuthoredAreaMetadata,
            build_authored_are_bytes,
            build_authored_ifo_bytes,
            patch_preserved_stock_are_bytes,
            patch_preserved_stock_ifo_bytes,
        )
        from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, build_git_bytes
        from src.core.modules.authored_module_pathing import (
            AuthoredPathingRoom,
            compile_authored_pathing_for_rooms,
        )
        from src.core.modules.authored_module_project import AuthoredModuleMetadata
        from src.core.modules.module_format import LYTLayout, LYTRoom, WOKData
        from src.core.validation.kotor_module_engine_contract import (
            KotorModuleEngineContractRequest,
            validate_kotor_module_engine_contract,
        )

        source_resources: dict[tuple[str, str], bytes] = {}
        source_mod = Path(request.source_mod).expanduser().resolve() if request.source_mod else None
        if source_mod is not None and source_mod.is_file():
            source_resources = _capsule_resources(source_mod)
        elif source_mod is not None:
            result.warnings.append(f"Source MOD is absent; core metadata will be generated: {source_mod}")

        explicit_lyt, source_lyt = _explicit_resource(request.source_lyt, label="LYT")
        capsule_lyt, capsule_lyt_resref, capsule_lyt_fallback = _module_resource(
            source_resources,
            module_resref,
            "lyt",
        )
        if explicit_lyt is not None:
            lyt_bytes = explicit_lyt
            layout = LYTLayout.from_text(lyt_bytes.decode("latin-1", errors="replace"))
            result.preserved_resources.append(source_lyt.name if source_lyt is not None else f"{module_resref}.lyt")
        elif capsule_lyt is not None:
            lyt_bytes = capsule_lyt
            layout = LYTLayout.from_text(lyt_bytes.decode("latin-1", errors="replace"))
            result.preserved_resources.append(f"{capsule_lyt_resref}.lyt")
            if capsule_lyt_fallback:
                result.warnings.append(
                    f"Source MOD LYT is named {capsule_lyt_resref}.lyt instead of {module_resref}.lyt; "
                    "the candidate normalizes it to the module resref."
                )
        else:
            room_names = sorted(
                path.stem.lower()
                for path in room_dir.glob("*.mdl")
                if path.with_suffix(".mdx").is_file() and path.with_suffix(".wok").is_file()
            )
            layout = LYTLayout(rooms=[LYTRoom(name, 0.0, 0.0, 0.0) for name in room_names])
            lyt_bytes = layout.to_text().encode("latin-1")
            result.generated_resources.append(f"{module_resref}.lyt")
            result.warnings.append(
                "LYT was missing and was reconstructed with zero room offsets; visually audit room placement in Map Studio."
            )
        rooms = tuple(layout.rooms)
        overlong_rooms = [str(room.model) for room in rooms if len(str(room.model or "").strip()) > 16]
        if overlong_rooms:
            raise ValueError(
                "LYT room resrefs exceed the 16-character Odyssey limit: " + ", ".join(overlong_rooms)
            )
        room_resrefs = tuple(_normalise_resref(room.model) for room in rooms if _normalise_resref(room.model))
        result.room_resrefs = list(room_resrefs)
        if not room_resrefs:
            raise ValueError("The recovered layout contains no room rows.")
        if len(set(room_resrefs)) != len(room_resrefs):
            raise ValueError("The recovered LYT contains duplicate room resrefs.")
        visual_only_room_resrefs = tuple(
            dict.fromkeys(
                _normalise_resref(room)
                for room in request.visual_only_room_resrefs
                if _normalise_resref(room)
            )
        )
        unknown_visual_only_rooms = sorted(set(visual_only_room_resrefs) - set(room_resrefs))
        if unknown_visual_only_rooms:
            raise ValueError(
                "Visual-only room exceptions are absent from the recovered LYT: "
                + ", ".join(unknown_visual_only_rooms)
            )

        room_woks: dict[str, Any] = {}
        final_resources: dict[tuple[str, str], bytes] = {
            key: data
            for key, data in source_resources.items()
            if key[1] not in {"are", "git", "ifo", "pth", "lyt", "vis", "mdl", "mdx", "wok"}
        }
        for room in room_resrefs:
            for restype in ("mdl", "mdx", "wok"):
                path = room_dir / f"{room}.{restype}"
                if not path.is_file():
                    raise FileNotFoundError(f"Room {room} is missing repaired {restype.upper()}: {path}")
                final_resources[(room, restype)] = path.read_bytes()
            room_woks[room] = WOKData.from_bytes(final_resources[(room, "wok")])

        transition_source_rooms = tuple(
            _normalise_resref(room)
            for room in request.source_transition_room_resrefs
            if _normalise_resref(room)
        )
        result.source_transition_room_resrefs = list(transition_source_rooms)
        if transition_source_rooms:
            for room in room_resrefs:
                wok = room_woks[room]
                transition_rows = remap_walkmesh_transition_destinations(
                    wok,
                    source_room_resrefs=transition_source_rooms,
                    target_room_resrefs=room_resrefs,
                )
                for row in transition_rows:
                    result.walkmesh_transition_repairs.append({"room_resref": room, **row})
                changed_rows = [row for row in transition_rows if row["action"] != "preserved"]
                if not changed_rows:
                    continue
                remapped_wok_bytes = wok.to_bytes()
                remapped_wok = WOKData.from_bytes(remapped_wok_bytes)
                invalid_targets = [
                    int(transition)
                    for face in tuple(remapped_wok.faces or ())
                    for transition in (face.trans1, face.trans2, face.trans3)
                    if int(transition) >= len(room_resrefs)
                ]
                if invalid_targets:
                    raise ValueError(
                        f"Room {room} still contains out-of-range transition destinations after remap: "
                        f"{sorted(set(invalid_targets))}."
                    )
                final_resources[(room, "wok")] = remapped_wok_bytes
                room_woks[room] = remapped_wok
                result.generated_resources.append(f"{room}.wok transition destination repair")

            remapped_count = sum(
                row["action"] == "remapped" for row in result.walkmesh_transition_repairs
            )
            dropped_count = sum(
                row["action"] == "dropped" for row in result.walkmesh_transition_repairs
            )
            if remapped_count or dropped_count:
                result.warnings.append(
                    f"Walkmesh transition repair remapped {remapped_count} retained destination(s) "
                    f"and removed {dropped_count} destination(s) for rooms omitted from the recovered LYT."
                )

        combined_wok = _combined_room_wok(
            rooms,
            room_woks,
            coordinate_space=request.wok_coordinate_space,
        )
        fallback_entry = _fallback_entry_point(combined_wok, module_resref)
        explicit_are, explicit_are_path = _explicit_resource(request.source_are, label="ARE")
        explicit_git, explicit_git_path = _explicit_resource(request.source_git, label="GIT")
        explicit_ifo, explicit_ifo_path = _explicit_resource(request.source_ifo, label="IFO")
        capsule_are, capsule_are_resref, capsule_are_fallback = _module_resource(
            source_resources,
            module_resref,
            "are",
        )
        capsule_git, capsule_git_resref, capsule_git_fallback = _module_resource(
            source_resources,
            module_resref,
            "git",
        )
        capsule_ifo, capsule_ifo_resref, capsule_ifo_fallback = _module_resource(
            source_resources,
            module_resref,
            "ifo",
            fallback_resref="module",
        )
        source_are = explicit_are if explicit_are is not None else capsule_are
        source_git = explicit_git if explicit_git is not None else capsule_git
        source_ifo = explicit_ifo if explicit_ifo is not None else capsule_ifo
        for restype, explicit_path, capsule_resref, used_fallback in (
            ("ARE", explicit_are_path, capsule_are_resref, capsule_are_fallback),
            ("GIT", explicit_git_path, capsule_git_resref, capsule_git_fallback),
            ("IFO", explicit_ifo_path, capsule_ifo_resref, capsule_ifo_fallback),
        ):
            if explicit_path is not None:
                result.preserved_resources.append(explicit_path.name)
            elif used_fallback:
                expected = "module" if restype == "IFO" else module_resref
                result.warnings.append(
                    f"Source MOD {restype} is named {capsule_resref}.{restype.lower()} instead of "
                    f"{expected}.{restype.lower()}; the candidate normalizes its routing."
                )
        entry_point = _source_entry_point(source_ifo, fallback_entry, module_resref)
        metadata = AuthoredModuleMetadata(
            module_root=module_resref,
            game=game,
            display_name=f"{module_resref} (repaired legacy module)",
            tag=module_resref,
            description="Recovered by GhostStudio's non-destructive legacy module workflow.",
            capability_stage="repair_candidate",
        )
        area = AuthoredAreaMetadata(name=metadata.display_name, tag=module_resref)
        if source_are:
            are_bytes = patch_preserved_stock_are_bytes(
                source_are,
                metadata,
                area,
                room_resrefs=room_resrefs,
            )
            if explicit_are_path is None:
                result.preserved_resources.append(f"{module_resref}.are")
        else:
            are_bytes = build_authored_are_bytes(metadata, area, room_resrefs=room_resrefs)
            result.generated_resources.append(f"{module_resref}.are")
        if source_git:
            git_bytes = source_git
            if explicit_git_path is None:
                result.preserved_resources.append(f"{module_resref}.git")
        else:
            git_bytes = build_git_bytes(
                AuthoredGameplayPlacement(entry_point=entry_point),
                game=game,
            )
            result.generated_resources.append(f"{module_resref}.git")
        if source_ifo:
            ifo_bytes = patch_preserved_stock_ifo_bytes(source_ifo, entry_point, area_resrefs=(module_resref,))
            if explicit_ifo_path is None:
                result.preserved_resources.append("module.ifo")
            if ifo_bytes != source_ifo:
                result.generated_resources.append("module.ifo entry/area routing patch")
        else:
            ifo_bytes = build_authored_ifo_bytes(metadata, entry_point, area_resrefs=(module_resref,))
            result.generated_resources.append("module.ifo")
        ifo_bytes, result.module_identity = _patch_legacy_ifo_module_id(
            ifo_bytes,
            module_resref,
            regenerate=bool(request.regenerate_module_id),
        )
        if result.module_identity.get("changed"):
            result.generated_resources.append("module.ifo module identity regeneration")

        explicit_vis, source_vis = _explicit_resource(request.source_vis, label="VIS")
        capsule_vis, capsule_vis_resref, capsule_vis_fallback = _module_resource(
            source_resources,
            module_resref,
            "vis",
        )
        raw_vis = explicit_vis if explicit_vis is not None else capsule_vis
        vis_bytes, vis_changed = _normalised_vis_bytes(raw_vis, room_resrefs)
        if raw_vis is None:
            result.generated_resources.append(f"{module_resref}.vis")
        elif vis_changed:
            result.generated_resources.append(f"{module_resref}.vis symmetry repair")
        else:
            result.preserved_resources.append(
                source_vis.name if source_vis is not None else f"{capsule_vis_resref}.vis"
            )
        if explicit_vis is None and capsule_vis_fallback:
            result.warnings.append(
                f"Source MOD VIS is named {capsule_vis_resref}.vis instead of {module_resref}.vis; "
                "the candidate normalizes it to the module resref."
            )

        explicit_pth, source_pth = _explicit_resource(request.source_pth, label="PTH")
        capsule_pth, capsule_pth_resref, capsule_pth_fallback = _module_resource(
            source_resources,
            module_resref,
            "pth",
        )
        if not request.regenerate_pth and (explicit_pth is not None or capsule_pth is not None):
            pth_bytes = explicit_pth if explicit_pth is not None else capsule_pth
            result.preserved_resources.append(
                source_pth.name if source_pth is not None else f"{capsule_pth_resref}.pth"
            )
            if explicit_pth is None and capsule_pth_fallback:
                result.warnings.append(
                    f"Source MOD PTH is named {capsule_pth_resref}.pth instead of {module_resref}.pth; "
                    "the candidate normalizes it to the module resref."
                )
        else:
            pathing_rooms = tuple(
                AuthoredPathingRoom(
                    room_resref=_normalise_resref(getattr(room, "model", "")),
                    wok=room_woks[_normalise_resref(getattr(room, "model", ""))],
                    position=_room_wok_module_offset(room, request.wok_coordinate_space),
                )
                for room in rooms
            )
            pathing = compile_authored_pathing_for_rooms(pathing_rooms)
            result.pathing_metadata = dict(pathing.metadata)
            missing_portal_pairs = [
                pair
                for pair in pathing.metadata.get("reciprocal_transition_pairs", ())
                if int(pair.get("bidirectional_bridge_count", 0) or 0) < 1
            ]
            if missing_portal_pairs:
                labels = ", ".join(
                    f"{pair.get('room_a_resref', pair.get('room_a'))}<->"
                    f"{pair.get('room_b_resref', pair.get('room_b'))}"
                    for pair in missing_portal_pairs
                )
                raise ValueError(
                    "Generated PTH is missing bidirectional bridges for reciprocal WOK transitions: " + labels
                )
            pth_bytes = pathing.pth_bytes
            result.generated_resources.append(f"{module_resref}.pth")
            if request.regenerate_pth and (explicit_pth is not None or capsule_pth is not None):
                result.warnings.append(
                    "Source PTH was deliberately replaced because the recovered room/walkmesh set changed."
                )
            if int(pathing.metadata.get("path_graph_component_count", 0) or 0) > 1:
                result.warnings.append(
                    f"Generated PTH preserves {pathing.metadata['path_graph_component_count']} disconnected walkable "
                    "network(s) after reciprocal room transitions were linked."
                )

        final_resources[(module_resref, "are")] = are_bytes
        final_resources[(module_resref, "git")] = git_bytes
        final_resources[("module", "ifo")] = ifo_bytes
        final_resources[(module_resref, "lyt")] = lyt_bytes
        final_resources[(module_resref, "vis")] = vis_bytes
        final_resources[(module_resref, "pth")] = pth_bytes

        explicit_extra_paths = {
            str(Path(item).expanduser().resolve())
            for item in request.extra_resource_paths
        }
        documentation_stems = {
            "readme",
            "read_me",
            "license",
            "licence",
            "changelog",
            "changes",
            "credits",
        }
        non_deployable_extensions = {
            "csv",
            "json",
            "log",
            "md",
            "max",
            "pdf",
            "psb",
            "psd",
            "rtf",
            "zip",
        }
        for path in _iter_extra_resource_paths(request.extra_resource_paths, request.extra_resource_dirs):
            if not path.is_file():
                raise FileNotFoundError(f"Extra module resource does not exist: {path}")
            is_explicit = str(path) in explicit_extra_paths
            if not is_explicit and path.stem.strip().lower() in documentation_stems:
                continue
            restype = path.suffix.lower().lstrip(".")
            if not is_explicit and restype in non_deployable_extensions:
                continue
            resource_type = ResourceType.from_extension(restype)
            if resource_type is ResourceType.INVALID:
                # Texture/source packs often contain README, MAX, PSD, or
                # backup files beside deployable assets.  Explicit file paths
                # remain strict; recursive directories skip non-game files.
                if is_explicit:
                    raise ValueError(f"Unsupported extra module resource extension: {path.name}")
                continue
            if len(path.stem.strip()) > 16:
                raise ValueError(
                    f"Extra module resource resref exceeds the 16-character Odyssey limit: {path.name}"
                )
            key = (_normalise_resref(path.stem), restype)
            data = path.read_bytes()
            existing = final_resources.get(key)
            if existing is not None and existing != data:
                raise ValueError(f"Conflicting resource bytes for {key[0]}.{key[1]}.")
            final_resources[key] = data

        contract = validate_kotor_module_engine_contract(
            KotorModuleEngineContractRequest(
                game=game,
                module_resref=module_resref,
                resources=final_resources,
                expected_room_resrefs=room_resrefs,
                visual_only_room_resrefs=visual_only_room_resrefs,
            )
        )
        result.engine_contract = contract.to_dict()
        result.warnings.extend(contract.warnings)
        result.blocking_issues.extend(contract.blocking_issues)
        if result.blocking_issues:
            raise ValueError("Final serialized engine contract rejected the candidate.")

        capsule = ERF(ERFType.MOD)
        for (resref, restype), data in sorted(final_resources.items()):
            capsule.set_data(resref, ResourceType.from_extension(restype), data)
        modules_dir.mkdir(parents=True, exist_ok=True)
        temporary_module = modules_dir / f".{module_resref}.{game.lower()}.tmp.mod"
        write_erf(capsule, temporary_module)
        readback_resources = _capsule_resources(temporary_module)
        readback = validate_kotor_module_engine_contract(
            KotorModuleEngineContractRequest(
                game=game,
                module_resref=module_resref,
                resources=readback_resources,
                expected_room_resrefs=room_resrefs,
                visual_only_room_resrefs=visual_only_room_resrefs,
            )
        )
        result.readback_contract = readback.to_dict()
        if not readback.export_ready:
            result.blocking_issues.extend(readback.blocking_issues)
            raise ValueError("Packaged MOD readback failed the engine contract.")
        if module_path.exists():
            module_path.unlink()
        temporary_module.replace(module_path)
        _stage_resource_bytes(resources_dir, final_resources)
        result.bundled_resources = [
            {
                "resref": resref,
                "restype": restype,
                "size": len(data),
                "sha256": sha256(data).hexdigest(),
            }
            for (resref, restype), data in sorted(final_resources.items())
        ]
        result.ok = True
        result.code = "structural_candidate_ready"
        result.message = (
            f"Built {game} {module_resref}.mod with {len(room_resrefs)} repaired room(s); "
            "retail install/warp and movement proof is still required."
        )
    except Exception as exc:
        if not result.blocking_issues:
            result.blocking_issues.append(str(exc))
        result.ok = False
        result.code = "candidate_build_failed"
        result.message = f"Legacy module candidate failed: {exc}"
        temporary = modules_dir / f".{module_resref}.{game.lower()}.tmp.mod"
        try:
            if temporary.is_file():
                temporary.unlink()
        except OSError:
            pass
    finally:
        _write_json_result(manifest_path, result)
    return result


__all__ = [
    "LegacyRoomRepairRequest",
    "LegacyRoomRepairResult",
    "LegacyModuleCandidateRequest",
    "LegacyModuleCandidateResult",
    "remap_walkmesh_transition_destinations",
    "build_legacy_module_candidate",
    "repair_legacy_room_with_mdlops",
]
