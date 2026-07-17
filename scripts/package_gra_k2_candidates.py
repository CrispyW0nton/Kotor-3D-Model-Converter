"""Build end-to-end KOTOR 2 candidates for the recovered Gra room sets.

The source bundles split each area into one collision-owning ``01a`` room and
several overlapping visual partitions.  This command:

* decompiles every surviving binary room with MDLOps in isolated scratch space;
* rewrites the reviewed ASCII through Ghost Studio's controller-free K2 writer;
* keeps the repaired, centralized ``01a`` WOK and assigns canonical empty WOKs
  only to explicitly validated visual-only partitions;
* trims LYT to surviving art, writes a symmetric collision-room-star VIS, and
  regenerates PTH from the final centralized walkmesh;
* preserves the recovered ARE/GIT/IFO, bundles required custom textures, builds
  the MOD, imports it through Map Studio, saves/reopens an editable KMAP, and
  runs raw/round-trip walkmesh audits.

Outputs are structural candidates.  The command never installs them into the
game and never claims retail proof.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from scripts.generate_legacy_room_walkmesh_candidates import (  # noqa: E402
    _candidate_proofs,
    _compile_static_ascii_room,
    _compile_static_binary_room,
    _filtered_lyt,
)
from src.core.assets.resource_manager import (  # noqa: E402
    RES_TGA,
    RES_TPC,
    ResourceManager,
    _identify_texture_source,
)
from src.core.modules.module_format import LYTLayout, VISData  # noqa: E402
from src.core.validation.kotor_module_engine_contract import (  # noqa: E402
    inspect_raw_mdl_structure,
)
from src.core.workflow.legacy_module_repair import (  # noqa: E402
    LegacyModuleCandidateRequest,
    build_legacy_module_candidate,
)


DEFAULT_MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
DEFAULT_SOURCE = (
    DEFAULT_MODULE_ROOT
    / "Q_SellOut"
    / "Extracted"
    / "Models_Yavin"
    / "Models_Yavin"
)
DEFAULT_SOURCE_MODS = (
    DEFAULT_MODULE_ROOT
    / "Q_SellOut"
    / "Extracted"
    / "Modules_Yavin"
    / "Modules_Yavin"
)
DEFAULT_COLLISION = (
    DEFAULT_MODULE_ROOT
    / "Converted"
    / "WalkmeshAudit"
    / "GeneratedCandidates"
    / "GraCentralCollision"
)
DEFAULT_OUTPUT = DEFAULT_COLLISION / "EndToEndK2"
DEFAULT_MDLOPS = ROOT / "Saved" / "ExternalTools" / "mdlops" / "mdlops.exe"
DEFAULT_K2_ROOT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)

AREA_ROOMS: dict[str, tuple[str, ...]] = {
    "gra801": tuple(f"gra801_01{suffix}" for suffix in ("a", "b", "c", "d", "e", "f", "h")),
    "gra802": tuple(f"gra802_01{suffix}" for suffix in ("a", "b", "d")),
    "gra803": tuple(f"gra803_01{suffix}" for suffix in ("a", "b", "c", "d")),
}
DOCUMENTED_SOURCE_LYT_ROOMS: dict[str, tuple[str, ...]] = {
    area: tuple(f"{area}_01{suffix}" for suffix in ("a", "b", "c", "d", "e", "f", "h"))
    for area in AREA_ROOMS
}


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _validation_rows(report: Any) -> list[dict[str, Any]]:
    rows = []
    for issue in tuple(getattr(report, "issues", ()) or ()):
        severity = getattr(
            getattr(issue, "severity", None),
            "value",
            getattr(issue, "severity", ""),
        )
        rows.append(
            {
                "severity": str(severity or "").lower(),
                "code": str(getattr(issue, "code", "") or ""),
                "message": str(getattr(issue, "message", issue) or ""),
                "details": dict(getattr(issue, "details", {}) or {}),
            }
        )
    return rows


def _source_path(source: Path, room: str, suffix: str) -> Path:
    matches = sorted(source.glob(f"{room}.{suffix}"), key=lambda item: item.name.casefold())
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected one {room}.{suffix} under {source}; found {len(matches)}."
        )
    return matches[0]


def _decompile_room(
    room: str,
    source: Path,
    mdlops: Path,
    output: Path,
) -> dict[str, Any]:
    source_mdl = _source_path(source, room, "mdl")
    source_mdx = _source_path(source, room, "mdx")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"ghoststudio-{room}-ascii-") as temporary:
        scratch = Path(temporary)
        local_mdl = scratch / source_mdl.name
        local_mdx = scratch / source_mdx.name
        shutil.copy2(source_mdl, local_mdl)
        shutil.copy2(source_mdx, local_mdx)
        command = [
            str(mdlops),
            "-a",
            "--smoothgroups",
            "--use-ascii-extension",
            str(local_mdl),
        ]
        completed = subprocess.run(
            command,
            cwd=str(scratch),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        candidates = sorted(scratch.glob("*.mdl.ascii"), key=lambda item: item.name.casefold())
        if completed.returncode != 0 or len(candidates) != 1:
            raise RuntimeError(
                f"MDLOps failed to decompile {room}: return={completed.returncode}, "
                f"ascii_candidates={len(candidates)}, stderr={completed.stderr.strip()}"
            )
        output.write_bytes(candidates[0].read_bytes())
    return {
        "source_mdl": _artifact(source_mdl),
        "source_mdx": _artifact(source_mdx),
        "output_ascii": _artifact(output),
        "command": command,
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or ""),
        "stderr": str(completed.stderr or ""),
    }


def _source_mdl_audit(room: str, source: Path, *, visual_only: bool) -> dict[str, Any]:
    mdl_path = _source_path(source, room, "mdl")
    mdx_path = _source_path(source, room, "mdx")
    fingerprint, report = inspect_raw_mdl_structure(
        room,
        mdl_path.read_bytes(),
        mdx_path.read_bytes(),
        game="K2",
        allow_missing_aabb=visual_only,
    )
    rows = _validation_rows(report)
    return {
        "fingerprint": asdict(fingerprint),
        "validation": rows,
        "blocking": any(
            str(row.get("severity") or "").lower() in {"error", "blocking"}
            for row in rows
        ),
        "note": (
            "The source raw audit is provenance evidence only. Promotion uses the controller-free "
            "Ghost Studio rewrite and its independent raw/semantic readback gates."
        ),
    }


def _write_collision_star_vis(
    rooms: Iterable[str],
    collision_room: str,
    destination: Path,
) -> dict[str, Any]:
    wanted = tuple(str(room).casefold() for room in rooms)
    collision = collision_room.casefold()
    if collision not in wanted:
        raise ValueError(f"Collision room {collision} is absent from the retained room set.")
    vis = VISData()
    vis.visibility = {
        room: (
            [target for target in wanted if target != room]
            if room == collision
            else [collision]
        )
        for room in wanted
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(vis.to_text().encode("latin-1"))
    return {
        "output": _artifact(destination),
        "policy": "symmetric_central_collision_room_star",
        "visibility": vis.visibility,
        "rationale": (
            "The collision-owning room sees every overlapping visual partition; each visual-only "
            "partition links back to the collision room. No unsupported visual-to-visual portal "
            "relationship is invented."
        ),
    }


def _missing_source_art(source: Path, area: str, retained: Iterable[str]) -> list[dict[str, Any]]:
    retained_set = {str(room).casefold() for room in retained}
    rows = []
    for room in DOCUMENTED_SOURCE_LYT_ROOMS[area]:
        presence = {
            extension: bool(list(source.glob(f"{room}.{extension}")))
            for extension in ("mdl", "mdx", "wok")
        }
        rows.append(
            {
                "room": room,
                "retained": room in retained_set,
                "source_presence": presence,
                "missing_source_files": [
                    f"{room}.{extension}" for extension, exists in presence.items() if not exists
                ],
                "treatment": (
                    "playable centralized collision owner"
                    if room == f"{area}_01a"
                    else (
                        "retained visual-only MDL/MDX; canonical empty WOK generated"
                        if room in retained_set
                        else "excluded from trimmed LYT because no surviving MDL/MDX pair exists"
                    )
                ),
            }
        )
    return rows


def _texture_dependencies(
    room_compiles: Iterable[dict[str, Any]],
    source: Path,
    manager: ResourceManager,
    extra_texture_dirs: tuple[Path, ...] = (),
) -> dict[str, Any]:
    referenced = sorted(
        {
            str(texture).casefold()
            for result in room_compiles
            for texture in tuple(result["binary_geometry"].get("visual_textures", ()) or ())
            if str(texture).strip().casefold() not in {"", "null", "none"}
        }
    )
    # The primary model directory wins; the extra directories cover recovered
    # collection textures that ship in sibling override folders of the same
    # bundle (Gra802 qxn_flr07 lives in Q_SellOut NarShadda/Beach_Villa
    # Q_Textures, byte-identical in each copy).
    source_tga: dict[str, Path] = {}
    source_txi: dict[str, Path] = {}
    for directory in (*reversed(extra_texture_dirs), source):
        source_tga.update({path.stem.casefold(): path for path in directory.glob("*.tga")})
        source_txi.update({path.stem.casefold(): path for path in directory.glob("*.txi")})
    bundled: list[Path] = []
    resolved = []
    missing = []
    unsafe_external = []

    def stock_texture(texture: str) -> tuple[bytes | None, str | None]:
        """Resolve a stock texture below Override/module precedence.

        ResourceManager.get_texture intentionally returns the user's active
        Override first.  That is correct for preview, but it is not a safe
        provenance test: a texture can be shadowed by Override while still
        existing in K2's stock texture packs.  Candidate packaging therefore
        asks the indexed installation for TexturePack/BIF bytes directly.
        """

        install = manager._k2
        if install is None:
            return None, None
        for archive in install._tex_erfs:
            for resource_type in (RES_TPC, RES_TGA):
                data = archive.read(texture, resource_type)
                if data is not None:
                    return data, f"TexturePack ({Path(archive.path).name})"
        for resource_type in (RES_TPC, RES_TGA):
            data = install.get_bif(texture, resource_type)
            if data is not None:
                return data, "stock KEY/BIF"
        return None, None

    for texture in referenced:
        if texture in source_tga:
            tga = source_tga[texture]
            if len(tga.stem) > 16:
                missing.append(
                    {
                        "texture": texture,
                        "reason": "Recovered TGA resref exceeds Odyssey's 16-character limit.",
                        "source": _artifact(tga),
                    }
                )
                continue
            bundled.append(tga)
            if texture in source_txi:
                bundled.append(source_txi[texture])
            resolved.append({"texture": texture, "source": "bundled recovered TGA/TXI"})
            continue
        stock_data, stock_location = stock_texture(texture)
        if stock_data is not None:
            resolved.append(
                {
                    "texture": texture,
                    "source": stock_location,
                    "byte_size": len(stock_data),
                    "note": "Stock K2 source verified below any active Override shadow.",
                }
            )
            if texture in source_txi:
                bundled.append(source_txi[texture])
            continue
        data = manager.get_texture(texture, "K2")
        if data is None:
            missing.append({"texture": texture, "reason": "Absent from recovered bundle and KOTOR 2 resources."})
            continue
        location = _identify_texture_source(texture, manager, "K2")
        entry = {"texture": texture, "source": location, "byte_size": len(data)}
        if location == "Override/" or location.startswith("module ERF"):
            unsafe_external.append(entry)
        else:
            resolved.append(entry)
        if texture in source_txi:
            bundled.append(source_txi[texture])
    unique_bundled = sorted({path.resolve() for path in bundled}, key=lambda item: item.name.casefold())
    return {
        "referenced": referenced,
        "resolved": resolved,
        "missing": missing,
        "unsafe_external_only": unsafe_external,
        "bundled_resources": [_artifact(path) for path in unique_bundled],
        "extra_resource_paths": [str(path) for path in unique_bundled],
        "ready": not missing and not unsafe_external,
    }


def _compile_area(
    area: str,
    rooms: tuple[str, ...],
    *,
    source: Path,
    source_mods: Path,
    collision_root: Path,
    output_root: Path,
    mdlops: Path,
    manager: ResourceManager,
    compile_route: str = "binary",
    extra_texture_dirs: tuple[Path, ...] = (),
) -> dict[str, Any]:
    destination = output_root / area / "K2"
    room_dir = destination / "Rooms"
    ascii_dir = destination / "SourceAscii"
    core_dir = destination / "CoreInputs"
    room_dir.mkdir(parents=True, exist_ok=True)
    collision_room = f"{area}_01a"
    collision_wok = collision_root / area / "K2" / f"{collision_room}.wok"
    if not collision_wok.is_file():
        raise FileNotFoundError(
            f"Repaired centralized collision WOK is absent: {collision_wok}. "
            "Run generate_gra_central_walkmesh_candidates.py first."
        )

    source_audits: dict[str, Any] = {}
    decompiles: dict[str, Any] = {}
    room_compiles = []
    for room in rooms:
        visual_only = room != collision_room
        source_audit = _source_mdl_audit(room, source, visual_only=visual_only)
        source_audits[room] = source_audit
        if compile_route == "binary":
            # MDLOps ASCII decompilation drops real visual nodes when a room
            # reuses node names in different subtrees (Gra802 Cylinder01,
            # 176 faces, LKO_dor01).  The binary route parses the raw source
            # MDL/MDX directly and enforces exact source node parity.
            room_compiles.append(
                _compile_static_binary_room(
                    room=room,
                    source_mdl_path=_source_path(source, room, "mdl"),
                    source_mdx_path=_source_path(source, room, "mdx"),
                    output_dir=room_dir,
                    visual_only=visual_only,
                    external_wok_path=collision_wok if not visual_only else None,
                )
            )
            continue
        ascii_path = ascii_dir / f"{room}.mdl.ascii"
        decompiles[room] = _decompile_room(room, source, mdlops, ascii_path)
        room_compiles.append(
            _compile_static_ascii_room(
                room=room,
                ascii_path=ascii_path,
                output_dir=room_dir,
                visual_only=visual_only,
                external_wok_path=collision_wok if not visual_only else None,
                # A malformed legacy file is not a trustworthy binary parity
                # oracle. The MDLOps ASCII fingerprint remains authoritative.
                legacy_binary_root=None if source_audit["blocking"] else source,
            )
        )

    textures = _texture_dependencies(room_compiles, source, manager, extra_texture_dirs)
    if not textures["ready"]:
        raise RuntimeError(
            f"{area} has unresolved texture dependencies: "
            f"missing={textures['missing']}, unsafe_external={textures['unsafe_external_only']}"
        )

    source_lyt = _source_path(source, area, "lyt")
    lyt = _filtered_lyt(source_lyt, rooms, core_dir / f"{area}.lyt")
    vis = _write_collision_star_vis(rooms, collision_room, core_dir / f"{area}.vis")
    source_mod = _source_path(source_mods, area, "mod")
    visual_only_rooms = tuple(room for room in rooms if room != collision_room)
    build = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref=area,
            target_game="K2",
            repaired_rooms_dir=str(room_dir),
            output_dir=str(destination),
            source_mod=str(source_mod),
            source_lyt=str(core_dir / f"{area}.lyt"),
            source_vis=str(core_dir / f"{area}.vis"),
            extra_resource_paths=tuple(textures["extra_resource_paths"]),
            visual_only_room_resrefs=visual_only_rooms,
            regenerate_pth=True,
            wok_coordinate_space="module",
            overwrite=True,
        )
    )
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module=area, candidate_root=destination)
    module_path = destination / "Modules" / f"{area}.mod"
    kmap_path = destination / "MapStudioProof" / f"{area}.kmap"
    return {
        "module": area,
        "candidate_root": str(destination),
        "compile_route": compile_route,
        "rooms": rooms,
        "collision_room": collision_room,
        "visual_only_rooms": visual_only_rooms,
        "source_mod": _artifact(source_mod),
        "source_mdl_audits": source_audits,
        "decompiles": decompiles,
        "room_compiles": room_compiles,
        "texture_dependencies": textures,
        "lyt": lyt,
        "vis": vis,
        "source_art_inventory": _missing_source_art(source, area, rooms),
        "module_build": build.to_dict(),
        "proofs": proofs,
        "mod": _artifact(module_path) if module_path.is_file() else None,
        "kmap": _artifact(kmap_path) if kmap_path.is_file() else None,
        "ready_for_manual_k2_test": bool(build.ok and proofs.get("ready_for_manual_k2_test")),
        "retail_game_tested": False,
    }


def _write_readme(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Gra KOTOR 2 end-to-end candidates",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        "Each candidate contains every surviving visual MDL/MDX partition, one repaired centralized "
        "`01a` collision WOK, canonical empty WOKs for validated visual-only partitions, trimmed LYT, "
        "a symmetric central-room-star VIS, regenerated PTH, recovered ARE/GIT/IFO, required custom "
        "textures, a MOD, and an editable Map Studio KMAP.",
        "",
        "| Module | Rooms | Visual-only | MOD SHA-256 | KMAP SHA-256 | Structural ready |",
        "|---|---:|---:|---|---|---|",
    ]
    for area in report["areas"]:
        mod_hash = str((area.get("mod") or {}).get("sha256") or "-")
        kmap_hash = str((area.get("kmap") or {}).get("sha256") or "-")
        lines.append(
            f"| {area['module']} | {len(area['rooms'])} | {len(area['visual_only_rooms'])} | "
            f"`{mod_hash}` | `{kmap_hash}` | {area['ready_for_manual_k2_test']} |"
        )
    lines.extend(["", "## Missing source art", ""])
    for area in report["areas"]:
        excluded = [row for row in area["source_art_inventory"] if not row["retained"]]
        lines.append(f"- `{area['module']}`: " + (
            "; ".join(
                f"{row['room']} ({', '.join(row['missing_source_files'])})" for row in excluded
            )
            if excluded
            else "none; all seven source LYT rooms have surviving MDL/MDX pairs"
        ))
    lines.extend(
        [
            "",
            "## Proof boundary",
            "",
            "The MOD and KMAP audits are structural and editor round-trip proofs only. These files have "
            "not been installed. Manual KOTOR 2 warps must still verify spawn, movement over every floor "
            "region, camera containment, AI pathing, visibility, textures, and save/reload.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--source-mod-dir", type=Path, default=DEFAULT_SOURCE_MODS)
    parser.add_argument("--collision-dir", type=Path, default=DEFAULT_COLLISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mdlops", type=Path, default=DEFAULT_MDLOPS)
    parser.add_argument("--k2-root", type=Path, default=DEFAULT_K2_ROOT)
    parser.add_argument(
        "--area",
        action="append",
        choices=sorted(AREA_ROOMS),
        default=[],
        help="Area to build; repeatable. Defaults to every registered Gra area.",
    )
    parser.add_argument(
        "--extra-texture-dir",
        action="append",
        type=Path,
        default=[],
        help=(
            "Additional recovered texture directory searched for referenced "
            "TGA/TXI resources after the primary model directory; repeatable."
        ),
    )
    parser.add_argument(
        "--compile-route",
        choices=("binary", "mdlops"),
        default="binary",
        help=(
            "Room compile route. 'binary' (default) parses the raw source MDL/MDX "
            "with Ghost Studio's parser and enforces exact source node parity; "
            "'mdlops' keeps the legacy ASCII decompile route, which drops "
            "duplicate-named visual nodes such as Gra802 Cylinder01."
        ),
    )
    args = parser.parse_args()
    source = args.source_dir.expanduser().resolve()
    source_mods = args.source_mod_dir.expanduser().resolve()
    collision = args.collision_dir.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    mdlops = args.mdlops.expanduser().resolve()
    k2_root = args.k2_root.expanduser().resolve()
    checks = [
        ("Gra source", source, True),
        ("Gra source MOD", source_mods, True),
        ("central collision", collision, True),
        ("KOTOR 2", k2_root / "chitin.key", False),
    ]
    if args.compile_route == "mdlops":
        checks.append(("MDLOps", mdlops, False))
    for label, path, expect_dir in checks:
        exists = path.is_dir() if expect_dir else path.is_file()
        if not exists:
            raise FileNotFoundError(f"{label} input does not exist: {path}")
    output.mkdir(parents=True, exist_ok=True)
    manager = ResourceManager()
    if not manager.set_k2_dir(str(k2_root)):
        raise RuntimeError(f"ResourceManager could not index KOTOR 2 at {k2_root}.")
    extra_texture_dirs = tuple(path.expanduser().resolve() for path in args.extra_texture_dir)
    for directory in extra_texture_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"Extra texture directory does not exist: {directory}")
    selected_areas = tuple(dict.fromkeys(args.area)) or tuple(AREA_ROOMS)
    areas = [
        _compile_area(
            area,
            AREA_ROOMS[area],
            source=source,
            source_mods=source_mods,
            collision_root=collision,
            output_root=output,
            mdlops=mdlops,
            manager=manager,
            compile_route=args.compile_route,
            extra_texture_dirs=extra_texture_dirs,
        )
        for area in selected_areas
    ]
    report = {
        "schema": "ghoststudio.gra-k2-end-to-end-candidates.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(source),
        "source_mod_directory": str(source_mods),
        "collision_directory": str(collision),
        "output_directory": str(output),
        "k2_root": str(k2_root),
        "compile_route": args.compile_route,
        "selected_areas": list(selected_areas),
        "mdlops": _artifact(mdlops) if args.compile_route == "mdlops" else None,
        "installed_into_game": False,
        "retail_game_tested": False,
        "areas": areas,
        "all_ready_for_manual_k2_test": all(area["ready_for_manual_k2_test"] for area in areas),
    }
    subset = "" if set(selected_areas) == set(AREA_ROOMS) else "." + "-".join(selected_areas)
    manifest = output / f"gra-k2-end-to-end-candidates{subset}.json"
    readme = output / ("README.md" if not subset else f"README{subset}.md")
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_readme(report, readme)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "readme": str(readme),
                "modules": {
                    area["module"]: {
                        "mod": (area.get("mod") or {}).get("path"),
                        "kmap": (area.get("kmap") or {}).get("path"),
                        "ready_for_manual_k2_test": area["ready_for_manual_k2_test"],
                    }
                    for area in areas
                },
                "retail_game_tested": False,
            },
            indent=2,
        )
    )
    return 0 if report["all_ready_for_manual_k2_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
