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
) -> dict[str, Any]:
    if not mod.is_file():
        raise FileNotFoundError(f"{module} final MOD does not exist: {mod}")
    if kmap is not None and not kmap.is_file():
        raise FileNotFoundError(f"{module} final KMAP does not exist: {kmap}")
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
        "structural_candidate_ready": True,
        "retail_game_proven": False,
    }


def build_overlay() -> dict[str, Any]:
    gra = GENERATED / "GraCentralCollisionVerified" / "EndToEndK2Verified"
    lrfs = GENERATED / "LegacyRoomFloorSelection"
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
            mod=lrfs / "koq202" / "K2" / "FiveRoomCandidate" / "Modules" / "koq202.mod",
            kmap=lrfs / "koq202" / "K2" / "FiveRoomCandidate" / "MapStudioProof" / "koq202.kmap",
            classification="recovered_playable_rooms",
            compile_route="ascii",
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
            "rnvcanyon",
            mod=GENERATED / "rnvcanyon" / "K2" / "HonestCandidate" / "Modules" / "rnvcanyon.mod",
            kmap=GENERATED
            / "rnvcanyon"
            / "K2"
            / "HonestCandidate"
            / "MapStudioProof"
            / "rnvcanyon.kmap",
            classification="honest_partial",
            visual_only_rooms=("koq200_02", "valsky"),
            notes=(
                "Omits koq200_01l/01m/01n (LYT-only rooms with no surviving art).",
                "Generated PTH spans disconnected per-room walkmesh components; cross-room "
                "pathing needs explicit retail verification.",
            ),
            compile_route="ghoststudio_binary_mdl",
        ),
        _entry(
            "rnvcity",
            mod=GENERATED / "rnvcity" / "K2" / "HonestCandidate" / "Modules" / "rnvcity.mod",
            kmap=GENERATED
            / "rnvcity"
            / "K2"
            / "HonestCandidate"
            / "MapStudioProof"
            / "rnvcity.kmap",
            classification="full_k2_room_rebuild",
            notes=(
                "All nine koq201 rooms rewritten for K2: K1 function pointers replaced, "
                "embedded AABBs derived from repaired WOKs, symmetric VIS, regenerated PTH.",
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
            "gra801",
            "505qgm",
            "koq202",
            "vul803",
            "vul801",
            "undclb",
            "gra802",
            "gra803",
            "rnvcanyon",
            "rnvcity",
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
