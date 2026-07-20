"""Repack the retail-proven ``kq2all`` axis as canonical K2 ``koq200``.

The source archive is hash locked to the exact package that reached KOTOR 2's
``currentgame`` cache and was traversed successfully.  This builder changes
only module identity: five area-root resource keys are renamed, the IFO receives
the canonical deterministic Mod_ID/resrefs/tag, and the ARE tag becomes
``KOQ200``.  The eight MDL/MDX/WOK triplets, LYT/VIS/PTH payloads, empty runtime
GIT, textures, and all WOK transition rows remain byte-exact.

Nothing produced here is installed into KOTOR.  The canonical resref still
requires its own manual retail warp before promotion.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_koq200_k2_bisection_matrix as axis  # noqa: E402
from scripts.generate_legacy_room_walkmesh_candidates import _candidate_proofs  # noqa: E402
from pykotor.resource.formats.gff import bytes_gff, read_gff  # noqa: E402
from pykotor.resource.generics.pth import read_pth  # noqa: E402
from pykotor.resource.type import ResourceType as RT  # noqa: E402
from src.core.modules.authored_module_metadata import (  # noqa: E402
    MODULE_SCRIPT_FIELDS,
    authored_module_id_bytes,
)


SOURCE_MODULE_DEFAULT = (
    ROOT
    / "artifacts"
    / "map_studio"
    / "koq200_k2_bisection"
    / "07_kq2all_oracle_scriptless_candidate_all_rooms"
    / "Modules"
    / "kq2all.mod"
)
SOURCE_MODULE_SHA256 = "750d1c47a6454e00f33a53310781930db296bc8f22d51c439abaa45002b51ff7"
SOURCE_RETAIL_PROOF_SUMMARY = (
    ROOT
    / "Saved"
    / "KotorLiveLogs"
    / "20260718-170555-koq200-bisection-kq2all-hashlocked-r14"
    / "summary.txt"
)
OUTPUT_DEFAULT = ROOT / "artifacts" / "map_studio" / "koq200_k2_canonical_from_kq2all"

SOURCE_MODULE_RESREF = "kq2all"
TARGET_MODULE_RESREF = "koq200"
ROOM_RESREFS = axis.CANDIDATE_ROOM_RESREFS
ROOT_RESOURCE_TYPES = (RT.ARE, RT.GIT, RT.LYT, RT.PTH, RT.VIS)
EXPECTED_TRANSITION_COUNT = 34


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_label(key: tuple[str, Any]) -> str:
    return f"{key[0]}.{str(key[1].extension).lower()}"


def _byte_difference_count(before: bytes, after: bytes) -> int:
    shared = sum(left != right for left, right in zip(before, after))
    return shared + abs(len(before) - len(after))


def _validate_retail_source(source_module: Path, proof_summary: Path) -> dict[str, Any]:
    source_module = source_module.resolve()
    proof_summary = proof_summary.resolve()
    if not source_module.is_file():
        raise FileNotFoundError(f"Retail-proven kq2all source is missing: {source_module}")
    actual_hash = _sha256_path(source_module)
    if actual_hash != SOURCE_MODULE_SHA256:
        raise ValueError(
            f"kq2all source hash drifted: expected {SOURCE_MODULE_SHA256}, got {actual_hash}."
        )
    if not proof_summary.is_file():
        raise FileNotFoundError(f"kq2all retail proof summary is missing: {proof_summary}")
    proof_text = proof_summary.read_text(encoding="utf-8", errors="replace")
    required_fragments = (
        "Expected command: warp kq2all",
        "Crashes: 0",
        f"End currentgame: exists=True size={source_module.stat().st_size} sha256={actual_hash}",
    )
    missing = [fragment for fragment in required_fragments if fragment not in proof_text]
    if missing:
        raise ValueError("kq2all retail proof summary is incomplete: " + "; ".join(missing))
    return {
        "source_module": str(source_module),
        "source_sha256": actual_hash,
        "source_size": source_module.stat().st_size,
        "live_log_summary": str(proof_summary),
        "warp_route_reached_currentgame_byte_exact": True,
        "crashes": 0,
        "user_traversal_report": "User traversed the entire kq2all map and reported it good to go.",
        "source_axis_retail_proven": True,
    }


def _assert_scriptless_ifo(data: bytes) -> None:
    root = read_gff(data).root
    populated = {
        field: str(root.get(field) or "").strip()
        for field in MODULE_SCRIPT_FIELDS
        if str(root.get(field) or "").strip()
    }
    if populated:
        raise ValueError(f"kq2all oracle IFO is no longer scriptless: {populated}")


def _assert_empty_runtime_git(data: bytes) -> None:
    root = read_gff(data).root
    populated = {
        field: len(root.get(field))
        for field in axis._RUNTIME_GIT_LIST_FIELDS
        if root.exists(field) and len(root.get(field))
    }
    if populated:
        raise ValueError(f"kq2all oracle GIT is no longer runtime-empty: {populated}")


def _patch_canonical_ifo(data: bytes) -> bytes:
    _assert_scriptless_ifo(data)
    gff = read_gff(data)
    root = gff.root
    root.set_binary("Mod_ID", authored_module_id_bytes(TARGET_MODULE_RESREF))
    root.set_resref("Mod_Entry_Area", TARGET_MODULE_RESREF)
    root.set_string("Mod_Tag", TARGET_MODULE_RESREF.upper())
    areas = root.get("Mod_Area_list")
    if areas is None or len(areas) != 1:
        raise ValueError("Retail-proven kq2all IFO must contain exactly one area-list row.")
    for area in areas:
        area.set_resref("Area_Name", TARGET_MODULE_RESREF)
    output = bytes_gff(gff)
    _assert_scriptless_ifo(output)
    return output


def _patch_canonical_are(data: bytes) -> bytes:
    gff = read_gff(data)
    root = gff.root
    rooms = root.get("Rooms")
    actual_rooms = tuple(str(row.get("RoomName") or "").strip().lower() for row in rooms or ())
    if actual_rooms != ROOM_RESREFS:
        raise ValueError(
            f"Retail-proven kq2all ARE room order drifted: expected {ROOM_RESREFS}, got {actual_rooms}."
        )
    root.set_string("Tag", TARGET_MODULE_RESREF.upper())
    return bytes_gff(gff)


def _assert_source_axis(resources: Mapping[tuple[str, Any], bytes]) -> dict[str, Any]:
    _assert_scriptless_ifo(axis._resource(resources, "module", RT.IFO))
    _assert_empty_runtime_git(axis._resource(resources, SOURCE_MODULE_RESREF, RT.GIT))

    lyt = axis._resource(resources, SOURCE_MODULE_RESREF, RT.LYT)
    vis = axis._resource(resources, SOURCE_MODULE_RESREF, RT.VIS)
    for label, payload in (("LYT", lyt), ("VIS", vis)):
        if not payload.endswith(b"\r\n") or b"\n" in payload.replace(b"\r\n", b""):
            raise ValueError(f"Retail-proven kq2all {label} is no longer CRLF-normalized.")
    lyt_rooms = tuple(
        line.split()[0].lower()
        for line in lyt.decode("ascii").split("\r\n")
        if line.startswith("      koq200_")
    )
    vis_rooms = tuple(
        line.split()[0].lower()
        for line in vis.decode("ascii").split("\r\n")
        if line and not line.startswith(" ")
    )
    if lyt_rooms != ROOM_RESREFS or vis_rooms != ROOM_RESREFS:
        raise ValueError("Retail-proven kq2all LYT/VIS room order no longer matches all eight rooms.")

    entry = axis._ifo_entry(axis._resource(resources, "module", RT.IFO))
    expected_entry = axis._walkable_entry_from_wok(
        axis._resource(resources, ROOM_RESREFS[0], RT.WOK)
    )
    if any(abs(actual - expected) > 1.0e-5 for actual, expected in zip(entry, expected_entry)):
        raise ValueError(f"kq2all IFO entry {entry} is no longer on the expected 01a walkable face.")
    path = read_pth(axis._resource(resources, SOURCE_MODULE_RESREF, RT.PTH))
    point = path.get(0)
    if point is None or len(getattr(path, "_points", ())) != 1:
        raise ValueError("Retail-proven kq2all PTH must contain exactly its one isolated entry point.")
    if abs(float(point.x) - entry[0]) > 1.0e-5 or abs(float(point.y) - entry[1]) > 1.0e-5:
        raise ValueError("Retail-proven kq2all PTH point no longer matches the IFO entry.")

    rooms: list[dict[str, Any]] = []
    transition_count = 0
    for room in ROOM_RESREFS:
        hashes: dict[str, str] = {}
        transitions: tuple[tuple[int, int], ...] = ()
        for restype in (RT.MDL, RT.MDX, RT.WOK):
            payload = axis._resource(resources, room, restype)
            hashes[str(restype.extension).lower()] = _sha256_bytes(payload)
            if restype == RT.WOK:
                transitions = axis._wok_transition_rows(payload)
                if any(destination < 0 or destination >= len(ROOM_RESREFS) for _, destination in transitions):
                    raise ValueError(f"{room}.wok contains a transition outside the eight-room LYT.")
        transition_count += len(transitions)
        rooms.append(
            {
                "room": room,
                "triplet_sha256": hashes,
                "transition_count": len(transitions),
                "transition_destinations": sorted({destination for _, destination in transitions}),
            }
        )
    if transition_count != EXPECTED_TRANSITION_COUNT:
        raise ValueError(
            f"Retail-proven room set transition count drifted: expected {EXPECTED_TRANSITION_COUNT}, "
            f"got {transition_count}."
        )
    return {
        "rooms": rooms,
        "room_count": len(rooms),
        "transition_count": transition_count,
        "entry": list(entry),
        "lyt_room_order": list(lyt_rooms),
        "vis_room_order": list(vis_rooms),
        "scriptless_ifo": True,
        "runtime_git_empty": True,
    }


def _canonical_resources(
    source: Mapping[tuple[str, Any], bytes],
) -> dict[tuple[str, Any], bytes]:
    output = {(str(resref).lower(), restype): bytes(data) for (resref, restype), data in source.items()}
    for restype in ROOT_RESOURCE_TYPES:
        source_key = (SOURCE_MODULE_RESREF, restype)
        target_key = (TARGET_MODULE_RESREF, restype)
        if target_key in output:
            raise ValueError(f"kq2all unexpectedly already contains {_resource_label(target_key)}.")
        payload = axis._resource(output, SOURCE_MODULE_RESREF, restype)
        del output[source_key]
        output[target_key] = _patch_canonical_are(payload) if restype == RT.ARE else payload
    output[("module", RT.IFO)] = _patch_canonical_ifo(axis._resource(output, "module", RT.IFO))
    return output


def _resource_delta(
    source: Mapping[tuple[str, Any], bytes],
    output: Mapping[tuple[str, Any], bytes],
) -> dict[str, Any]:
    source_keys = set(source)
    output_keys = set(output)
    source_only = source_keys - output_keys
    output_only = output_keys - source_keys
    changed_common = {key for key in source_keys & output_keys if source[key] != output[key]}
    expected_source_only = {(SOURCE_MODULE_RESREF, restype) for restype in ROOT_RESOURCE_TYPES}
    expected_output_only = {(TARGET_MODULE_RESREF, restype) for restype in ROOT_RESOURCE_TYPES}
    if source_only != expected_source_only or output_only != expected_output_only:
        raise ValueError("Canonical repack changed resource keys outside the five area-root renames.")
    if changed_common != {("module", RT.IFO)}:
        raise ValueError(
            "Canonical repack changed same-key payloads outside module.ifo: "
            + ", ".join(sorted(_resource_label(key) for key in changed_common))
        )

    renamed: list[dict[str, Any]] = []
    for restype in ROOT_RESOURCE_TYPES:
        source_data = source[(SOURCE_MODULE_RESREF, restype)]
        output_data = output[(TARGET_MODULE_RESREF, restype)]
        renamed.append(
            {
                "source": _resource_label((SOURCE_MODULE_RESREF, restype)),
                "target": _resource_label((TARGET_MODULE_RESREF, restype)),
                "source_sha256": _sha256_bytes(source_data),
                "target_sha256": _sha256_bytes(output_data),
                "byte_identical": source_data == output_data,
                "byte_difference_count": _byte_difference_count(source_data, output_data),
            }
        )
    ifo_before = source[("module", RT.IFO)]
    ifo_after = output[("module", RT.IFO)]
    unchanged = (source_keys & output_keys) - changed_common
    return {
        "source_resource_count": len(source),
        "target_resource_count": len(output),
        "renamed_resource_count": len(renamed),
        "renamed_resources": renamed,
        "changed_same_key_resources": ["module.ifo"],
        "unchanged_same_key_resource_count": len(unchanged),
        "unchanged_same_key_resources": sorted(_resource_label(key) for key in unchanged),
        "module_ifo": {
            "source_sha256": _sha256_bytes(ifo_before),
            "target_sha256": _sha256_bytes(ifo_after),
            "byte_difference_count": _byte_difference_count(ifo_before, ifo_after),
        },
        "allowed_changes_only": True,
    }


def _assert_canonical_identity(resources: Mapping[tuple[str, Any], bytes]) -> dict[str, Any]:
    if any(resref == SOURCE_MODULE_RESREF for resref, _restype in resources):
        raise ValueError("Canonical archive still contains kq2all resource keys.")
    raw_hits = [
        _resource_label(key)
        for key, data in resources.items()
        if SOURCE_MODULE_RESREF.encode("ascii") in bytes(data).lower()
    ]
    if raw_hits:
        raise ValueError(f"Canonical archive still embeds kq2all identity in: {raw_hits}")

    ifo = read_gff(axis._resource(resources, "module", RT.IFO)).root
    area_list = ifo.get("Mod_Area_list")
    area_names = tuple(str(row.get("Area_Name") or "").lower() for row in area_list or ())
    expected_id = authored_module_id_bytes(TARGET_MODULE_RESREF)
    if ifo.get("Mod_ID") != expected_id:
        raise ValueError("Canonical IFO Mod_ID is not the deterministic authored-module identity.")
    if str(ifo.get("Mod_Entry_Area") or "").lower() != TARGET_MODULE_RESREF:
        raise ValueError("Canonical IFO entry area was not retargeted to koq200.")
    if str(ifo.get("Mod_Tag") or "") != TARGET_MODULE_RESREF.upper():
        raise ValueError("Canonical IFO tag was not retargeted to KOQ200.")
    if area_names != (TARGET_MODULE_RESREF,):
        raise ValueError("Canonical IFO area list was not retargeted to koq200.")
    _assert_scriptless_ifo(axis._resource(resources, "module", RT.IFO))

    are = read_gff(axis._resource(resources, TARGET_MODULE_RESREF, RT.ARE)).root
    rooms = tuple(str(row.get("RoomName") or "").lower() for row in are.get("Rooms") or ())
    if str(are.get("Tag") or "") != TARGET_MODULE_RESREF.upper() or rooms != ROOM_RESREFS:
        raise ValueError("Canonical ARE identity or room order is inconsistent.")
    _assert_empty_runtime_git(axis._resource(resources, TARGET_MODULE_RESREF, RT.GIT))
    return {
        "module_resref": TARGET_MODULE_RESREF,
        "mod_id_hex": expected_id.hex(),
        "ifo_entry_area": TARGET_MODULE_RESREF,
        "ifo_tag": TARGET_MODULE_RESREF.upper(),
        "ifo_area_list": list(area_names),
        "are_tag": TARGET_MODULE_RESREF.upper(),
        "are_rooms": list(rooms),
        "scriptless_ifo": True,
        "runtime_git_empty": True,
        "embedded_source_identity_hits": [],
    }


def _assert_proof_gates(engine_contract: dict[str, Any], proofs: dict[str, Any]) -> dict[str, Any]:
    roundtrip = dict(proofs.get("map_studio_roundtrip", {}) or {})
    checks = {
        "engine_contract_export_ready": bool(engine_contract.get("export_ready")),
        "map_studio_roundtrip_ok": bool(roundtrip.get("ok")),
        "reopened_room_count_matches": int(roundtrip.get("reopened_room_count", -1))
        == int(roundtrip.get("room_count", -2)),
        "reopened_wok_parity_complete": int(roundtrip.get("wok_parity_match_count", -1))
        == int(roundtrip.get("wok_parity_room_count", -2)),
        "mod_walkmesh_audit_pass": bool(
            dict(proofs.get("mod_walkmesh_audit", {}) or {}).get("audit_pass")
        ),
        "kmap_walkmesh_audit_pass": bool(
            dict(proofs.get("kmap_walkmesh_audit", {}) or {}).get("audit_pass")
        ),
        "mod_kmap_walkmesh_parity": bool(
            dict(proofs.get("walkmesh_parity", {}) or {}).get("all_match")
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Canonical KOQ200 proof gates failed: " + ", ".join(failed))
    return {"checks": checks, "passed": True}


def build_canonical(
    source_module: Path,
    output_dir: Path,
    *,
    proof_summary: Path = SOURCE_RETAIL_PROOF_SUMMARY,
) -> dict[str, Any]:
    source_module = source_module.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    module_path = output_dir / "Modules" / f"{TARGET_MODULE_RESREF}.mod"
    report_path = output_dir / f"{TARGET_MODULE_RESREF}.canonical-from-kq2all.json"
    if module_path.exists() or report_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing canonical artifact under {output_dir}.")

    retail_lineage = _validate_retail_source(source_module, proof_summary)
    source_resources = axis._archive_resources(source_module)
    source_axis = _assert_source_axis(source_resources)
    canonical_resources = _canonical_resources(source_resources)
    delta = _resource_delta(source_resources, canonical_resources)
    identity = _assert_canonical_identity(canonical_resources)

    module_path.parent.mkdir(parents=True, exist_ok=True)
    axis._write_module(canonical_resources, module_path)
    readback = axis._archive_resources(module_path)
    if readback != canonical_resources:
        raise ValueError("Canonical koq200 MOD readback differs from its exact build inputs.")
    readback_identity = _assert_canonical_identity(readback)
    readback_delta = _resource_delta(source_resources, readback)
    engine_contract = axis._engine_contract(TARGET_MODULE_RESREF, readback)
    if not bool(engine_contract.get("export_ready")):
        raise ValueError(
            "Canonical koq200 engine contract failed: "
            + "; ".join(str(value) for value in engine_contract.get("blocking_issues", []))
        )

    proofs = _candidate_proofs(module=TARGET_MODULE_RESREF, candidate_root=output_dir)
    proof_gates = _assert_proof_gates(engine_contract, proofs)
    kmap_path = output_dir / "MapStudioProof" / f"{TARGET_MODULE_RESREF}.kmap"
    if not kmap_path.is_file():
        raise FileNotFoundError("Map Studio proof did not emit koq200.kmap.")

    # The source and target room triplets must remain exact after archive readback.
    room_parity: list[dict[str, Any]] = []
    for room in ROOM_RESREFS:
        for restype in (RT.MDL, RT.MDX, RT.WOK):
            source_data = source_resources[(room, restype)]
            target_data = readback[(room, restype)]
            if source_data != target_data:
                raise ValueError(f"Canonical repack changed {_resource_label((room, restype))}.")
            room_parity.append(
                {
                    "resource": _resource_label((room, restype)),
                    "sha256": _sha256_bytes(target_data),
                    "byte_identical_to_retail_kq2all": True,
                }
            )

    report = {
        "schema": "ghoststudio.koq200-k2-canonical-from-retail-kq2all.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_retail_lineage": retail_lineage,
        "canonical_module": {
            "path": str(module_path),
            "sha256": _sha256_path(module_path),
            "size": module_path.stat().st_size,
            "resource_count": len(readback),
        },
        "map_studio_kmap": {
            "path": str(kmap_path),
            "sha256": _sha256_path(kmap_path),
            "size": kmap_path.stat().st_size,
        },
        "source_axis": source_axis,
        "canonical_identity": identity,
        "readback_identity": readback_identity,
        "resource_delta_vs_kq2all": delta,
        "readback_resource_delta_vs_kq2all": readback_delta,
        "room_triplet_parity": room_parity,
        "room_triplet_parity_count": len(room_parity),
        "engine_contract": engine_contract,
        "map_studio_proofs": proofs,
        "proof_gates": proof_gates,
        "installation_performed": False,
        "source_axis_retail_proven": True,
        "canonical_retail_game_tested": False,
        "ready_for_canonical_manual_k2_warp": True,
        "next_gate": "Stage only after explicit approval, then manually warp koq200 and traverse it in retail KOTOR 2.",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-module", type=Path, default=SOURCE_MODULE_DEFAULT)
    parser.add_argument("--retail-proof-summary", type=Path, default=SOURCE_RETAIL_PROOF_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_canonical(
        args.source_module,
        args.output_dir,
        proof_summary=args.retail_proof_summary,
    )
    print(
        json.dumps(
            {
                "mod": report["canonical_module"],
                "kmap": report["map_studio_kmap"],
                "report": report["report_path"],
                "room_triplets_byte_exact": report["room_triplet_parity_count"] == 24,
                "proof_gates_passed": report["proof_gates"]["passed"],
                "installation_performed": False,
                "canonical_retail_game_tested": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
