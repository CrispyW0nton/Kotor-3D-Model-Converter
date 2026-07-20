"""Write the derived KOTOR 2 candidate status overlay.

The base ``Converted/CONVERSION_STATUS.json`` records the original conversion
pipeline outputs and is never rewritten by this command.  This overlay names
the *final* K2 candidate artifact per module — the exact MOD/KMAP pair that
should be staged for a manual retail warp test — plus each module's honest
classification and visual-only room exceptions.

Every entry carries ``retail_game_proven: false`` until the user's manual
KOTOR 2 warp, traversal, camera, and save/reload test has actually happened.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
CONVERTED = MODULE_ROOT / "Converted"
CANDIDATES = CONVERTED / "Candidates"
GENERATED = CONVERTED / "WalkmeshAudit" / "GeneratedCandidates"
BASE_STATUS = CONVERTED / "CONVERSION_STATUS.json"
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

KOQ202_QUARANTINED_CONTROLLER_FREE_SHA256 = (
    "7ecb30e28c3d5c68b64f230216653765b2cfcfe10a4c586be4db8797cf1f771b"
)
KOQ202_EXPECTED_CONTROLLER_COUNTS = {
    "koq202_01a": 618,
    "koq202_01b": 970,
    "koq202_01c": 174,
    "koq202_01d": 0,
    "koq202_01g": 272,
}
KOQ202_EXPECTED_TRANSITION_REPAIRS = {
    ("koq202_01a", 4, 0, "preserved", 2, 2),
    ("koq202_01a", 46, 0, "preserved", 1, 1),
    ("koq202_01b", 99, 0, "preserved", 0, 0),
    ("koq202_01c", 10, 0, "remapped", 6, 4),
    ("koq202_01c", 19, 0, "preserved", 0, 0),
    ("koq202_01g", 15, 1, "preserved", 2, 2),
    ("koq202_01g", 17, 0, "dropped", 7, -1),
}
KOQ202_CONTROLLER_PRESERVED_EVIDENCE = (
    WORKSPACE_ROOT / "artifacts" / "map_studio" / "koq202_k2_controller_preserved_20260718"
)
KOQ202_CONTROLLER_PRESERVED_ROOT = (
    KOQ202_CONTROLLER_PRESERVED_EVIDENCE / "koq202" / "K2" / "FiveRoomCandidate"
)
KOQ202_CONTROLLER_PRESERVED_MANIFEST = (
    KOQ202_CONTROLLER_PRESERVED_EVIDENCE / "koq202-k2-controller-preserved-candidate.json"
)

_STAGE = "py -3.14 scripts/stage_k2_manual_warp_candidate.py --module-root {root} --candidate \"{mod}\""


def _artifact(path: Path) -> dict[str, Any]:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "byte_size": path.stat().st_size, "sha256": digest.hexdigest()}


def _entry(
    module: str,
    *,
    mod: Path,
    kmap: Path | None,
    classification: str,
    visual_only_rooms: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
    compile_route: str = "",
    structural_candidate_ready: bool = True,
    readiness_evidence: dict[str, Any] | None = None,
    readiness_blockers: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not mod.is_file():
        raise FileNotFoundError(f"{module} final MOD does not exist: {mod}")
    if kmap is not None and not kmap.is_file():
        raise FileNotFoundError(f"{module} final KMAP does not exist: {kmap}")
    stage_command = ""
    if structural_candidate_ready:
        stage_command = _STAGE.format(root=module, mod=mod)
        for room in visual_only_rooms:
            stage_command += f" --visual-only-room {room}"
    return {
        "module": module,
        "classification": classification,
        "compile_route": compile_route,
        "mod": _artifact(mod),
        "kmap": _artifact(kmap) if kmap is not None else None,
        "visual_only_rooms": list(visual_only_rooms),
        "notes": list(notes),
        "stage_command": stage_command,
        "structural_candidate_ready": bool(structural_candidate_ready),
        "readiness_evidence": dict(readiness_evidence or {}),
        "readiness_blockers": list(readiness_blockers),
        "retail_game_proven": False,
    }


def _validate_koq202_controller_preserved_candidate(
    *,
    manifest_path: Path,
    mod_path: Path,
    kmap_path: Path,
) -> dict[str, Any]:
    """Fail closed unless KOQ202 matches the current controller/pathing proof.

    The former ``7ecb30...`` package passed older structural checks only because
    its five functional static controller banks had been stripped.  An overlay
    is a staging index, so it must independently bind the selected MOD/KMAP
    bytes to the current raw-engine, controller-parity, transition-remap, PTH,
    and Map Studio reopen evidence before it exposes a stage command.
    """

    errors: list[str] = []
    if not manifest_path.is_file():
        errors.append(f"missing controller-preserved manifest: {manifest_path}")
        payload: dict[str, Any] = {}
    else:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"invalid controller-preserved manifest: {exc}")
            payload = {}
    if not isinstance(payload, dict):
        errors.append("controller-preserved manifest root is not a JSON object")
        payload = {}

    def _integer(value: Any, default: int = -1) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    if not mod_path.is_file():
        errors.append(f"missing KOQ202 MOD: {mod_path}")
    if not kmap_path.is_file():
        errors.append(f"missing KOQ202 KMAP: {kmap_path}")
    mod_artifact = _artifact(mod_path) if mod_path.is_file() else None
    kmap_artifact = _artifact(kmap_path) if kmap_path.is_file() else None
    if mod_artifact and mod_artifact["sha256"] == KOQ202_QUARANTINED_CONTROLLER_FREE_SHA256:
        errors.append("selected MOD is the quarantined 7ecb30 controller-free artifact")

    candidate = payload.get("koq202_five_room_candidate", {})
    if not isinstance(candidate, dict):
        errors.append("KOQ202 candidate evidence is not a JSON object")
        candidate = {}
    if payload.get("schema") != "ghoststudio.koq202-k2-controller-preserved-candidate.v1":
        errors.append("manifest schema is not the controller-preserved KOQ202 schema")
    if candidate.get("ready_for_manual_k2_test") is not True:
        errors.append("candidate did not pass its current structural/manual-test readiness gate")
    if candidate.get("retail_game_tested") is not False:
        errors.append("candidate retail-test state is not explicitly false")
    if payload.get("installed_into_game") is not False:
        errors.append("evidence does not explicitly record that the candidate was not installed")
    expected_root = str(mod_path.parent.parent.resolve()) if mod_path.is_file() else ""
    if str(candidate.get("candidate_root", "")) != expected_root:
        errors.append("manifest candidate root does not identify the selected MOD/KMAP root")

    room_compiles = candidate.get("room_compiles", {})
    actual_controller_counts: dict[str, int] = {}
    embedded_aabb_face_count = 0
    for room, expected_count in KOQ202_EXPECTED_CONTROLLER_COUNTS.items():
        compile_row = room_compiles.get(room, {}) if isinstance(room_compiles, dict) else {}
        fingerprint = compile_row.get("mdl_audit", {}).get("fingerprint", {})
        actual_count = _integer(fingerprint.get("controller_count", -1))
        actual_controller_counts[room] = actual_count
        if actual_count != expected_count:
            errors.append(f"{room} has {actual_count} controllers; expected {expected_count}")
        if compile_row.get("controller_parity", {}).get(
            "exact_entry_order_metadata_times_values"
        ) is not True:
            errors.append(f"{room} did not prove exact controller entry/order/payload parity")
        if compile_row.get("source_node_parity", {}).get(
            "exact_visual_geometry_material_texture_parity"
        ) is not True:
            errors.append(f"{room} did not prove exact visual/material/texture parity")
        if compile_row.get("mdl_audit", {}).get("blocking") is not False:
            errors.append(f"{room} failed the raw K2 MDL structural contract")
        if compile_row.get("wok_audit", {}).get("blocking") is not False:
            errors.append(f"{room} failed the raw WOK structural contract")
        aabb_parity = compile_row.get("embedded_aabb_parity", {})
        if aabb_parity.get("face_index_topology_matches") is not True:
            errors.append(f"{room} embedded AABB does not match its final WOK topology")
        embedded_aabb_face_count += _integer(aabb_parity.get("face_count", 0), 0)
    if embedded_aabb_face_count != 190:
        errors.append(
            f"embedded AABB negative-dot plane contract covered {embedded_aabb_face_count} faces; expected 190"
        )

    module_build = candidate.get("module_build", {})
    if module_build.get("ok") is not True:
        errors.append("legacy-module workflow did not finish successfully")
    for contract_name in ("engine_contract", "readback_contract"):
        contract = module_build.get(contract_name, {})
        if contract.get("export_ready") is not True or contract.get("blocking_issues"):
            errors.append(f"{contract_name} did not pass without blocking issues")

    pathing = module_build.get("pathing_metadata", {})
    expected_pathing = {
        "point_count": 12,
        "connection_count": 20,
        "generated_portal_link_count": 3,
        "reciprocal_transition_pair_count": 3,
        "one_way_transition_count": 0,
    }
    actual_pathing = {field: _integer(pathing.get(field, -1)) for field in expected_pathing}
    if actual_pathing != expected_pathing:
        errors.append(f"PTH/portal metrics changed: {actual_pathing} != {expected_pathing}")

    actual_repairs = {
        (
            str(row.get("room_resref", "")),
            _integer(row.get("face_index", -1)),
            _integer(row.get("local_edge", -1)),
            str(row.get("action", "")),
            _integer(row.get("source_index", -1)),
            _integer(row.get("target_index", -1)),
        )
        for raw_row in module_build.get("walkmesh_transition_repairs", [])
        for row in (raw_row if isinstance(raw_row, dict) else {},)
    }
    if actual_repairs != KOQ202_EXPECTED_TRANSITION_REPAIRS:
        errors.append("WOK transition preservation/remap/drop table changed")

    proofs = candidate.get("proofs", {})
    roundtrip = proofs.get("map_studio_roundtrip", {})
    if roundtrip.get("ok") is not True:
        errors.append("MOD to editable KMAP to reopen proof failed")
    if proofs.get("mod_walkmesh_audit", {}).get("audit_pass") is not True:
        errors.append("final MOD walkmesh audit failed")
    if proofs.get("kmap_walkmesh_audit", {}).get("audit_pass") is not True:
        errors.append("reopened KMAP walkmesh audit failed")
    if proofs.get("walkmesh_parity", {}).get("all_match") is not True:
        errors.append("MOD/KMAP/reopened walkmesh parity failed")
    if mod_artifact and roundtrip.get("module_sha256") != mod_artifact["sha256"]:
        errors.append("manifest MOD hash does not match the selected MOD")
    if kmap_artifact and roundtrip.get("kmap_sha256") != kmap_artifact["sha256"]:
        errors.append("manifest KMAP hash does not match the selected KMAP")

    return {
        "passed": not errors,
        "errors": errors,
        "manifest": _artifact(manifest_path) if manifest_path.is_file() else None,
        "controller_counts": actual_controller_counts,
        "embedded_aabb_negative_dot_plane_face_count": embedded_aabb_face_count,
        "pathing": actual_pathing,
        "transition_repairs_match": actual_repairs == KOQ202_EXPECTED_TRANSITION_REPAIRS,
        "quarantined_sha256": KOQ202_QUARANTINED_CONTROLLER_FREE_SHA256,
    }


def build_overlay() -> dict[str, Any]:
    gra = GENERATED / "GraCentralCollisionVerified" / "EndToEndK2Verified"
    lrfs = GENERATED / "LegacyRoomFloorSelection"
    fresh_koq202_mod = KOQ202_CONTROLLER_PRESERVED_ROOT / "Modules" / "koq202.mod"
    fresh_koq202_kmap = KOQ202_CONTROLLER_PRESERVED_ROOT / "MapStudioProof" / "koq202.kmap"
    legacy_koq202_root = lrfs / "koq202" / "K2" / "FiveRoomCandidate"
    if fresh_koq202_mod.is_file() and fresh_koq202_kmap.is_file():
        koq202_mod = fresh_koq202_mod
        koq202_kmap = fresh_koq202_kmap
    else:
        # Preserve discoverability of the old evidence while making it
        # impossible for its quarantined hash to expose a staging command.
        koq202_mod = legacy_koq202_root / "Modules" / "koq202.mod"
        koq202_kmap = legacy_koq202_root / "MapStudioProof" / "koq202.kmap"
    koq202_readiness = _validate_koq202_controller_preserved_candidate(
        manifest_path=KOQ202_CONTROLLER_PRESERVED_MANIFEST,
        mod_path=koq202_mod,
        kmap_path=koq202_kmap,
    )
    entries = [
        _entry(
            "505qgm",
            mod=lrfs / "505qgm" / "K2" / "EightRoomCandidate" / "Modules" / "505qgm.mod",
            kmap=lrfs / "505qgm" / "K2" / "EightRoomCandidate" / "MapStudioProof" / "505qgm.kmap",
            classification="recovered_centralized_collision",
            visual_only_rooms=tuple(
                f"505qgm_01{suffix}" for suffix in ("b", "c", "d", "e", "f", "h", "l")
            ),
            notes=("505qgm_01a owns the map-wide playable WOK; seven partitions are visual-only.",),
            compile_route="ascii",
        ),
        _entry(
            "koq202",
            mod=koq202_mod,
            kmap=koq202_kmap,
            classification="recovered_playable_rooms",
            notes=(
                "All five retained rooms use the controller-preserving K2 writer with exact "
                "618/970/174/0/272 controller-bank and visual/material/texture parity.",
                "All 190 embedded AABB faces pass the negative-dot plane equation and match "
                "their final external WOK topology.",
                "Transition-aware PTH links all three reciprocal room seams; recovered room "
                "koq202_01d remains an evidence-honest isolated floor candidate.",
            ),
            compile_route="ghoststudio_binary_mdl",
            structural_candidate_ready=bool(koq202_readiness["passed"]),
            readiness_evidence=koq202_readiness,
            readiness_blockers=tuple(koq202_readiness["errors"]),
        ),
        _entry(
            "gra801",
            mod=gra / "gra801" / "K2" / "Modules" / "gra801.mod",
            kmap=gra / "gra801" / "K2" / "MapStudioProof" / "gra801.kmap",
            classification="recovered_centralized_collision",
            visual_only_rooms=tuple(
                f"gra801_01{suffix}" for suffix in ("b", "c", "d", "e", "f", "h")
            ),
            notes=(
                "Rebuilt 2026-07-16 through the binary MDL route; recovers 4 visual nodes/833 "
                "faces the earlier MDLOps ASCII route silently dropped.",
            ),
            compile_route="ghoststudio_binary_mdl",
        ),
        _entry(
            "gra802",
            mod=gra / "gra802" / "K2" / "Modules" / "gra802.mod",
            kmap=gra / "gra802" / "K2" / "MapStudioProof" / "gra802.kmap",
            classification="recovered_centralized_collision",
            visual_only_rooms=("gra802_01b", "gra802_01d"),
            notes=(
                "Binary MDL route preserves both duplicate-named Cylinder01 visual nodes "
                "(176 faces, LKO_dor01) that MDLOps dropped.",
            ),
            compile_route="ghoststudio_binary_mdl",
        ),
        _entry(
            "gra803",
            mod=gra / "gra803" / "K2" / "Modules" / "gra803.mod",
            kmap=gra / "gra803" / "K2" / "MapStudioProof" / "gra803.kmap",
            classification="recovered_centralized_collision",
            visual_only_rooms=("gra803_01b", "gra803_01c", "gra803_01d"),
            compile_route="ghoststudio_binary_mdl",
        ),
        _entry(
            "vul801",
            mod=CANDIDATES / "vul801" / "Max2019NWMaxMergedHardened" / "K2" / "Modules" / "vul801.mod",
            kmap=CANDIDATES / "vul801" / "Max2019NWMaxMergedHardened" / "K2" / "MapStudio" / "vul801.k2.kmap",
            classification="max2019_nwmax_recovered",
            notes=(
                "Three closed WOK components remain a required retail movement/pathing "
                "inspection point.",
            ),
            compile_route="max2019_nwmax",
        ),
        _entry(
            "vul803",
            mod=CANDIDATES
            / "vul803"
            / "Max2019NWMaxMergedHardened"
            / "a8ebb3e913f6"
            / "K2"
            / "Modules"
            / "vul803.mod",
            kmap=CANDIDATES
            / "vul803"
            / "Max2019NWMaxMergedHardened"
            / "a8ebb3e913f6"
            / "K2"
            / "MapStudio"
            / "vul803.k2.kmap",
            classification="max2019_nwmax_recovered",
            compile_route="max2019_nwmax",
        ),
        _entry(
            "undclb",
            mod=GENERATED / "undclb" / "K2" / "undclb.entry-repaired.mod",
            kmap=GENERATED / "undclb" / "K2" / "undclb.entry-repaired.kmap",
            classification="entry_repaired_candidate",
            notes=("Supersedes the stale base-status path whose entry point audit fails.",),
            compile_route="entry_repair",
        ),
        _entry(
            "koq200",
            mod=GENERATED / "koq200" / "K2" / "HonestCandidate" / "Modules" / "koq200.mod",
            kmap=GENERATED
            / "koq200"
            / "K2"
            / "HonestCandidate"
            / "MapStudioProof"
            / "koq200.kmap",
            classification="honest_partial",
            visual_only_rooms=("koq200_02", "valsky"),
            notes=(
                "Omits koq200_01l/01m/01n (LYT-only rooms with no surviving art).",
                "Transition-aware PTH contains six proven reciprocal portal bridges; four "
                "intentional networks still require explicit retail traversal.",
                "Canonical KOQ200 archive/resource/IFO/KMAP identity; supersedes the "
                "provenance-named rnvcanyon candidate for manual K2 staging.",
            ),
            compile_route="ghoststudio_binary_mdl",
        ),
        _entry(
            "koq201",
            mod=GENERATED / "koq201" / "K2" / "HonestCandidate" / "Modules" / "koq201.mod",
            kmap=GENERATED
            / "koq201"
            / "K2"
            / "HonestCandidate"
            / "MapStudioProof"
            / "koq201.kmap",
            classification="full_k2_room_rebuild",
            notes=(
                "All nine koq201 rooms rewritten for K2: K1 function pointers replaced, "
                "embedded AABBs derived from repaired WOKs, symmetric VIS, and a "
                "transition-aware PTH with four reciprocal bridges.",
                "Canonical KOQ201 archive/resource/IFO/KMAP identity; supersedes the "
                "provenance-named rnvcity candidate for manual K2 staging.",
            ),
            compile_route="ghoststudio_binary_mdl",
        ),
    ]
    classification_warnings = {
        "771qgm": "reconstruction_scaffold — not a recovered original",
        "yav501": "reconstruction_scaffold — not a recovered original",
        "773qgm": "wok_derived_proxy — visuals synthesized from collision data",
        "775qgm": "wok_derived_proxy — visuals synthesized from collision data",
        "901mal": "retail_donor_overlay — geometry borrows retail donor rooms",
        "921srt": "retail_donor_overlay — geometry borrows retail donor rooms",
    }
    return {
        "schema": "ghoststudio.k2-candidate-overlay.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "base_status": _artifact(BASE_STATUS),
        "policy": (
            "This overlay supersedes the base status paths for K2 manual-warp staging. "
            "The base status file is preserved unmodified. No module may be called "
            "retail-proven until the user's manual KOTOR 2 warp test passes."
        ),
        "modules": {row["module"]: row for row in entries},
        "classification_warnings": classification_warnings,
        "suggested_first_proof_wave": [
            "koq200",
            "koq201",
            "koq202",
            "gra801",
            "505qgm",
            "vul803",
            "vul801",
            "undclb",
            "gra802",
            "gra803",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=CONVERTED / "K2_CANDIDATE_OVERLAY.json",
    )
    args = parser.parse_args()
    overlay = build_overlay()
    output = args.output.expanduser().resolve()
    output.write_text(json.dumps(overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Overlay written: {output}")
    print(json.dumps({m: r["mod"]["sha256"][:12] for m, r in overlay["modules"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
