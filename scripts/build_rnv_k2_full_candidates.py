"""Build honest K2 candidates for the recovered RNV modules.

``RNVcanyon`` (area ``koq200``) becomes an honest partial: the seven surviving
playable rooms keep their authoritative WOKs, the two evidence-verified
visual-only rooms (``koq200_02``, ``valsky``) receive the retail no-AABB MDL
plus canonical empty WOKs, and the three LYT-only rooms with no surviving art
(``koq200_01l``/``01m``/``01n``) are omitted rather than fabricated.

``RNVcity`` (area ``koq201``) receives the full K2 room rebuild its audit
demanded: every room MDL/MDX is rewritten from the raw source binary through
Ghost Studio's K2 writer (K1 function pointers replaced, node ``+8`` zeroed,
static controllers removed), the missing embedded AABB nodes are derived from
each room's repaired external WOK, invalid WOK AABB tables are rebuilt without
semantic drift, VIS becomes symmetric over the full room set, and PTH is
regenerated from the final combined walkmesh.

Both candidates bundle the referenced K1 stock textures that KOTOR 2 does not
ship, produce a MOD plus editable Map Studio KMAP, and run the full
MOD<->KMAP walkmesh parity audit.  The outputs are structural candidates only;
manual retail KOTOR 2 warp/traversal proof is still required.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from pykotor.extract.capsule import Capsule  # noqa: E402
from pykotor.resource.formats.erf import ERF, ERFType, write_erf  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

from src.core.assets.resource_manager import RES_TGA, RES_TPC, ResourceManager  # noqa: E402
from src.core.geometry.model_data import NodeFlags  # noqa: E402
from src.core.mdl.mdl_parser import MDLBinaryParser  # noqa: E402
from src.core.modules.module_format import VISData, WALKABLE_IDS, WOKData  # noqa: E402
from src.core.workflow.legacy_module_repair import (  # noqa: E402
    LegacyModuleCandidateRequest,
    build_legacy_module_candidate,
)

from scripts.generate_legacy_room_walkmesh_candidates import (  # noqa: E402
    _artifact,
    _candidate_proofs,
    _compile_static_binary_room,
    _filtered_lyt,
)
from scripts.generate_rnv_walkmesh_candidates import (  # noqa: E402
    _reserialize_wok_derived_tables,
)

DEFAULT_MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
DEFAULT_CANDIDATES = DEFAULT_MODULE_ROOT / "Converted" / "WalkmeshAudit" / "GeneratedCandidates"
DEFAULT_K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
DEFAULT_K2_ROOT = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)

MODULE_PLANS: dict[str, dict[str, Any]] = {
    "rnvcanyon": {
        "source_mod": DEFAULT_CANDIDATES / "RNVcanyon" / "K2" / "RNVcanyon.ascii-wok-cleaned.mod",
        "area_resref": "koq200",
        "playable_rooms": tuple(f"koq200_01{suffix}" for suffix in "abcdefg"),
        # Verified 2026-07-16: both models survive with no embedded AABB node
        # and no WOK resource, matching the retail visual-partition pattern.
        "visual_only_rooms": ("koq200_02", "valsky"),
        # LYT-only rooms whose MDL/MDX no longer exist anywhere in the bundle.
        # An honest partial omits them instead of inventing geometry.
        "omitted_lyt_rooms": ("koq200_01l", "koq200_01m", "koq200_01n"),
        # MDLOps byproducts packaged as resources plus an off-LYT duplicate
        # sky model; they are not module data.
        "junk_resref_substrings": ("-ascii", "-textu"),
        "junk_resrefs": ("val_sky",),
    },
    "rnvcity": {
        "source_mod": DEFAULT_CANDIDATES / "RNVcity" / "K2" / "RNVcity.perimeter-repaired.mod",
        "area_resref": "koq201",
        "playable_rooms": tuple(f"koq201_01{suffix}" for suffix in "abcdefghj"),
        "visual_only_rooms": (),
        "omitted_lyt_rooms": (),
        "junk_resref_substrings": ("-ascii", "-textu"),
        "junk_resrefs": (),
        # Korriban City custom textures ship in the Marius bundle's Override
        # folder, not inside the recovered module capsule.
        "recovered_texture_dirs": (
            DEFAULT_MODULE_ROOT
            / "Marius_Things"
            / "Extracted"
            / "KorribanCity"
            / "KorribanCity"
            / "Override",
        ),
    },
}


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _capsule_resources(path: Path) -> dict[tuple[str, str], bytes]:
    resources: dict[tuple[str, str], bytes] = {}
    for resource in Capsule(path):
        key = (str(resource.resname()).strip().lower(), resource.restype().extension.lower())
        resources[key] = bytes(resource.data())
    return resources


def _is_junk(resref: str, plan: dict[str, Any]) -> bool:
    lowered = resref.casefold()
    if lowered in {name.casefold() for name in plan["junk_resrefs"]}:
        return True
    return any(marker in lowered for marker in plan["junk_resref_substrings"])


def _write_filtered_source_mod(
    resources: dict[tuple[str, str], bytes],
    plan: dict[str, Any],
    destination: Path,
) -> dict[str, Any]:
    erf = ERF(ERFType.MOD)
    kept: list[str] = []
    dropped: list[str] = []
    for (resref, extension), data in sorted(resources.items()):
        label = f"{resref}.{extension}"
        if extension == "txt" or _is_junk(resref, plan):
            dropped.append(label)
            continue
        erf.set_data(resref, ResourceType.from_extension(extension), data)
        kept.append(label)
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_erf(erf, destination)
    return {
        "output": _artifact(destination),
        "kept_resource_count": len(kept),
        "dropped_resources": dropped,
    }


def _entry_point_on_combined_walkmesh(
    resources: dict[tuple[str, str], bytes],
    playable_rooms: tuple[str, ...],
    authoritative_woks: dict[str, bytes],
) -> dict[str, Any]:
    """Check whether the source IFO entry lands on a walkable face.

    Recovered RNV IFOs carry a literal (0, 0, 0) entry.  The legacy packager
    preserves a present source entry verbatim, so a bogus one must be
    detected here and the IFO withheld, letting the packager derive the entry
    from the final combined walkmesh instead.
    """

    from pykotor.resource.formats.gff import read_gff

    ifo = resources.get(("module", "ifo"))
    if ifo is None:
        return {"present": False, "keep_source_ifo": False}
    root = read_gff(ifo).root
    entry = (
        float(root.acquire("Mod_Entry_X", 0.0) or 0.0),
        float(root.acquire("Mod_Entry_Y", 0.0) or 0.0),
        float(root.acquire("Mod_Entry_Z", 0.0) or 0.0),
    )
    on_walkable = False
    for room in playable_rooms:
        wok = WOKData.from_bytes(authoritative_woks[room])
        for face in wok.faces:
            if int(face.surface) not in WALKABLE_IDS:
                continue
            a, b, c = (wok.verts[int(face.v1)], wok.verts[int(face.v2)], wok.verts[int(face.v3)])
            # 2D barycentric containment in XY, tolerant of shared edges.
            d = (float(b[1]) - float(c[1])) * (float(a[0]) - float(c[0])) + (
                float(c[0]) - float(b[0])
            ) * (float(a[1]) - float(c[1]))
            if abs(d) < 1.0e-12:
                continue
            l1 = (
                (float(b[1]) - float(c[1])) * (entry[0] - float(c[0]))
                + (float(c[0]) - float(b[0])) * (entry[1] - float(c[1]))
            ) / d
            l2 = (
                (float(c[1]) - float(a[1])) * (entry[0] - float(c[0]))
                + (float(a[0]) - float(c[0])) * (entry[1] - float(c[1]))
            ) / d
            l3 = 1.0 - l1 - l2
            if min(l1, l2, l3) >= -1.0e-6:
                on_walkable = True
                break
        if on_walkable:
            break
    return {"present": True, "entry": entry, "keep_source_ifo": on_walkable}


def _referenced_textures(room_dir: Path, rooms: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    referenced: dict[str, list[dict[str, Any]]] = {}
    for room in rooms:
        model = MDLBinaryParser(
            (room_dir / f"{room}.mdl").read_bytes(),
            (room_dir / f"{room}.mdx").read_bytes(),
        ).parse()
        for node in model.all_nodes():
            for attribute in ("texture", "lightmap"):
                texture = str(getattr(node, attribute, "") or "").strip().casefold()
                if texture in {"", "null", "none"}:
                    continue
                referenced.setdefault(texture, []).append(
                    {
                        "room": room,
                        "node": str(getattr(node, "name", "") or ""),
                        "channel": attribute,
                        "render": bool(getattr(node, "render", True)),
                        "faces": len(getattr(node, "faces", []) or []),
                    }
                )
    return referenced


def _resolve_textures(
    referenced: dict[str, list[dict[str, Any]]],
    bundled: set[str],
    manager: ResourceManager,
    port_dir: Path,
    recovered_texture_dirs: tuple[Path, ...] = (),
) -> dict[str, Any]:
    recovered_tga: dict[str, Path] = {}
    recovered_txi: dict[str, Path] = {}
    for directory in reversed(recovered_texture_dirs):
        recovered_tga.update({path.stem.casefold(): path for path in directory.glob("*.tga")})
        recovered_tga.update({path.stem.casefold(): path for path in directory.glob("*.tpc")})
        recovered_txi.update({path.stem.casefold(): path for path in directory.glob("*.txi")})

    def stock_bytes(install: Any, texture: str) -> tuple[bytes, str, str] | None:
        for archive in install._tex_erfs:
            for restype, extension in ((RES_TPC, "tpc"), (RES_TGA, "tga")):
                data = archive.read(texture, restype)
                if data is not None:
                    return bytes(data), extension, f"TexturePack ({Path(archive.path).name})"
        for restype, extension in ((RES_TPC, "tpc"), (RES_TGA, "tga")):
            data = install.get_bif(texture, restype)
            if data is not None:
                return bytes(data), extension, "stock KEY/BIF"
        return None

    resolved: list[dict[str, Any]] = []
    ported: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    extra_resource_paths: list[str] = []
    for texture in sorted(referenced):
        if texture in bundled:
            resolved.append({"texture": texture, "source": "bundled in source MOD"})
            continue
        if texture in recovered_tga:
            source_path = recovered_tga[texture]
            port_dir.mkdir(parents=True, exist_ok=True)
            destination = port_dir / f"{texture}{source_path.suffix.lower()}"
            destination.write_bytes(source_path.read_bytes())
            extra_resource_paths.append(str(destination))
            if texture in recovered_txi:
                txi_destination = port_dir / f"{texture}.txi"
                txi_destination.write_bytes(recovered_txi[texture].read_bytes())
                extra_resource_paths.append(str(txi_destination))
            ported.append(
                {
                    "texture": texture,
                    "source": f"recovered bundle ({source_path})",
                    "output": _artifact(destination),
                    "note": "Custom texture recovered from the same download collection.",
                }
            )
            continue
        k2 = stock_bytes(manager._k2, texture)
        if k2 is not None:
            resolved.append({"texture": texture, "source": f"K2 {k2[2]}"})
            continue
        k1 = stock_bytes(manager._k1, texture)
        if k1 is not None:
            data, extension, location = k1
            port_dir.mkdir(parents=True, exist_ok=True)
            destination = port_dir / f"{texture}.{extension}"
            destination.write_bytes(data)
            extra_resource_paths.append(str(destination))
            ported.append(
                {
                    "texture": texture,
                    "source": f"K1 {location}",
                    "output": _artifact(destination),
                    "note": "K1 stock texture bundled because KOTOR 2 does not ship it.",
                }
            )
            continue
        missing.append(
            {
                "texture": texture,
                "referencing_nodes": referenced[texture][:6],
                "note": "Absent from the recovered bundle, KOTOR 2, and KOTOR 1; "
                "the surface renders untextured. Reported honestly, not fabricated.",
            }
        )
    return {
        "resolved": resolved,
        "ported_from_k1": ported,
        "missing": missing,
        "extra_resource_paths": extra_resource_paths,
    }


def _build_module(module: str, output_root: Path, manager: ResourceManager) -> dict[str, Any]:
    plan = MODULE_PLANS[module]
    source_mod = Path(plan["source_mod"])
    if not source_mod.is_file():
        raise FileNotFoundError(f"{module} source MOD does not exist: {source_mod}")
    resources = _capsule_resources(source_mod)
    playable_rooms: tuple[str, ...] = plan["playable_rooms"]
    visual_only_rooms: tuple[str, ...] = plan["visual_only_rooms"]
    retained_rooms = playable_rooms + visual_only_rooms
    area = plan["area_resref"]

    destination = output_root / module / "K2" / "HonestCandidate"
    source_rooms_dir = destination / "SourceRooms"
    wok_dir = destination / "CoreInputs" / "AuthoritativeWoks"
    room_dir = destination / "Rooms"
    core_dir = destination / "CoreInputs"
    port_dir = destination / "Resources" / "K1StockPorts"
    for directory in (source_rooms_dir, wok_dir, room_dir, core_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # 1. Extract room sources.
    for room in retained_rooms:
        for extension in ("mdl", "mdx"):
            data = resources.get((room, extension))
            if data is None:
                raise FileNotFoundError(f"{module} source is missing {room}.{extension}")
            (source_rooms_dir / f"{room}.{extension}").write_bytes(data)

    # 2. Authoritative WOKs: preserve surviving bytes; rebuild only the
    #    derived tables that fail the raw structural contract, proving zero
    #    semantic/indexed drift.
    wok_repairs: list[dict[str, Any]] = []
    authoritative_woks: dict[str, bytes] = {}
    for room in playable_rooms:
        data = resources.get((room, "wok"))
        if data is None:
            raise FileNotFoundError(f"{module} playable room {room} has no source WOK.")
        from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

        _fingerprint, report = inspect_raw_wok_structure(room, data)
        blocking = [
            issue
            for issue in tuple(getattr(report, "issues", ()) or ())
            if str(getattr(getattr(issue, "severity", None), "value", "")).lower()
            in {"error", "blocking"}
        ]
        if blocking:
            repaired, evidence = _reserialize_wok_derived_tables(data, resref=room)
            wok_repairs.append(
                {
                    "room": room,
                    "repair": "derived_tables_rebuilt_without_semantic_drift",
                    "blocking_codes": [str(getattr(issue, "code", "")) for issue in blocking],
                    "evidence": evidence,
                }
            )
            data = repaired
        authoritative_woks[room] = data
        (wok_dir / f"{room}.wok").write_bytes(data)

    # 3. Compile every retained room through the binary route.
    room_compiles: list[dict[str, Any]] = []
    for room in retained_rooms:
        room_compiles.append(
            _compile_static_binary_room(
                room=room,
                source_mdl_path=source_rooms_dir / f"{room}.mdl",
                source_mdx_path=source_rooms_dir / f"{room}.mdx",
                output_dir=room_dir,
                visual_only=room in visual_only_rooms,
                external_wok_path=(wok_dir / f"{room}.wok") if room in playable_rooms else None,
            )
        )

    # 4. Trimmed LYT (positions preserved) and symmetric VIS.
    source_lyt_path = core_dir / f"{area}.source.lyt"
    source_lyt_path.write_bytes(resources[(area, "lyt")])
    lyt = _filtered_lyt(source_lyt_path, retained_rooms, core_dir / f"{module}.lyt")
    vis = VISData()
    lowered_rooms = tuple(room.casefold() for room in retained_rooms)
    vis.visibility = {
        room: [target for target in lowered_rooms if target != room] for room in lowered_rooms
    }
    vis_path = core_dir / f"{module}.vis"
    vis_path.write_bytes(vis.to_text().encode("latin-1"))

    # 5. Texture dependencies: recovered bundle folders, then K1 stock ports.
    referenced = _referenced_textures(room_dir, retained_rooms)
    bundled = {name for (name, extension) in resources if extension in ("tga", "tpc")}
    textures = _resolve_textures(
        referenced,
        bundled,
        manager,
        port_dir,
        recovered_texture_dirs=tuple(plan.get("recovered_texture_dirs", ())),
    )

    # 6. Filtered source MOD (junk byproducts removed) plus IFO entry policy.
    entry_policy = _entry_point_on_combined_walkmesh(resources, playable_rooms, authoritative_woks)
    filtered_resources = dict(resources)
    if not entry_policy["keep_source_ifo"]:
        filtered_resources.pop(("module", "ifo"), None)
    filtered = _write_filtered_source_mod(
        filtered_resources,
        plan,
        core_dir / f"{module}.source-filtered.mod",
    )

    # 7. Package and prove.
    build = build_legacy_module_candidate(
        LegacyModuleCandidateRequest(
            module_resref=module,
            target_game="K2",
            repaired_rooms_dir=str(room_dir),
            output_dir=str(destination),
            source_mod=str(core_dir / f"{module}.source-filtered.mod"),
            source_lyt=str(core_dir / f"{module}.lyt"),
            source_vis=str(vis_path),
            extra_resource_paths=tuple(textures["extra_resource_paths"]),
            visual_only_room_resrefs=visual_only_rooms,
            regenerate_pth=True,
            wok_coordinate_space="module",
            overwrite=True,
        )
    )
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module=module, candidate_root=destination)

    module_path = destination / "Modules" / f"{module}.mod"
    kmap_path = destination / "MapStudioProof" / f"{module}.kmap"
    return {
        "module": module,
        "area_resref": area,
        "candidate_root": str(destination),
        "compile_route": "ghoststudio_binary_mdl",
        "source_mod": _artifact(source_mod),
        "playable_rooms": playable_rooms,
        "visual_only_rooms": visual_only_rooms,
        "omitted_lyt_rooms": plan["omitted_lyt_rooms"],
        "wok_repairs": wok_repairs,
        "room_compiles": room_compiles,
        "lyt": lyt,
        "vis": {"output": _artifact(vis_path), "policy": "symmetric_all_pairs"},
        "textures": textures,
        "entry_point_policy": entry_policy,
        "filtered_source_mod": filtered,
        "module_build": build.to_dict(),
        "proofs": proofs,
        "mod": _artifact(module_path) if module_path.is_file() else None,
        "kmap": _artifact(kmap_path) if kmap_path.is_file() else None,
        "ready_for_manual_k2_test": bool(build.ok and proofs.get("ready_for_manual_k2_test")),
        "retail_game_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        action="append",
        choices=sorted(MODULE_PLANS),
        default=[],
        help="Module to build; repeatable. Defaults to both RNV modules.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--k1-root", type=Path, default=DEFAULT_K1_ROOT)
    parser.add_argument("--k2-root", type=Path, default=DEFAULT_K2_ROOT)
    args = parser.parse_args()
    output_root = args.output_dir.expanduser().resolve()
    manager = ResourceManager()
    if not manager.set_k2_dir(str(args.k2_root.expanduser().resolve())):
        raise RuntimeError(f"ResourceManager could not index KOTOR 2 at {args.k2_root}.")
    if not manager.set_k1_dir(str(args.k1_root.expanduser().resolve())):
        raise RuntimeError(f"ResourceManager could not index KOTOR 1 at {args.k1_root}.")
    modules = tuple(dict.fromkeys(args.module)) or tuple(sorted(MODULE_PLANS))
    reports = [_build_module(module, output_root, manager) for module in modules]
    manifest = {
        "schema": "ghoststudio.rnv-k2-honest-candidates.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "modules": reports,
        "all_ready_for_manual_k2_test": all(row["ready_for_manual_k2_test"] for row in reports),
        "retail_game_tested": False,
    }
    manifest_path = output_root / ("rnv-k2-honest-candidates." + "-".join(modules) + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "modules": {
                    row["module"]: {
                        "mod": (row.get("mod") or {}).get("path"),
                        "kmap": (row.get("kmap") or {}).get("path"),
                        "ready_for_manual_k2_test": row["ready_for_manual_k2_test"],
                        "missing_textures": [item["texture"] for item in row["textures"]["missing"]],
                    }
                    for row in reports
                },
                "retail_game_tested": False,
            },
            indent=2,
        )
    )
    return 0 if manifest["all_ready_for_manual_k2_test"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
