"""Build evidence-backed RNV walkmesh cleanup candidates for KOTOR 2.

This command is intentionally narrower than a general module repair tool.  It
never modifies the source modules or a game install.  It performs only the two
repairs supported by the surviving data:

* ``RNVcity``: rebuild the derived BWM tables for the four WOKs whose serialized
  perimeter record is open while preserving indexed geometry, surfaces,
  adjacency, transition records, and all five header vectors.
* ``RNVcanyon``: remove seven ASCII ``node trimesh`` payloads that were packed
  with the WOK resource type.  The seven real binary BWM resources are retained
  byte-for-byte.  Missing rooms are classified from their surviving resources;
  no collision geometry is fabricated.

The results are structural candidates, not retail-game proof.  A manual KOTOR
2 warp and traversal is still required before either module can be called
working in game.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for _root in reversed(_python_roots(ROOT)):
    _text = str(_root)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from pykotor.extract.capsule import Capsule  # noqa: E402
from pykotor.resource.formats.erf import ERF, ERFType, write_erf  # noqa: E402
from pykotor.resource.formats.mdl import read_mdl  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

from core.modules.module_format import WOKData  # noqa: E402
from scripts.audit_walkmesh_library import audit_bwm_bytes, audit_mod  # noqa: E402


DEFAULT_MODULE_ROOT = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules")
DEFAULT_OUTPUT_ROOT = (
    DEFAULT_MODULE_ROOT / "Converted" / "WalkmeshAudit" / "GeneratedCandidates"
)
CITY_REPAIR_ROOMS = (
    "koq201_01f",
    "koq201_01g",
    "koq201_01h",
    "koq201_01j",
)
CANYON_PLAYABLE_ROOMS = tuple(f"koq200_01{suffix}" for suffix in "abcdefg")
CANYON_NO_SOURCE_ROOMS = ("koq200_01l", "koq200_01m", "koq200_01n")
CANYON_VISUAL_ONLY_ROOMS = ("koq200_02", "valsky")


ResourceKey = tuple[str, ResourceType]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _capsule_resources(path: Path) -> dict[ResourceKey, bytes]:
    resources: dict[ResourceKey, bytes] = {}
    for resource in Capsule(path):
        key = (str(resource.resname()).strip().lower(), resource.restype())
        if key in resources:
            raise ValueError(f"{path} contains a duplicate resource key: {key[0]}.{key[1].extension}")
        resources[key] = bytes(resource.data())
    return resources


def _write_mod(resources: dict[ResourceKey, bytes], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = ERF(ERFType.MOD)
    for (resref, restype), data in sorted(
        resources.items(), key=lambda item: (item[0][0], item[0][1].extension)
    ):
        archive.set_data(resref, restype, data)
    write_erf(archive, path)


def _resource_drift(
    before: dict[ResourceKey, bytes],
    after: dict[ResourceKey, bytes],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(before.keys() | after.keys(), key=lambda item: (item[0], item[1].extension)):
        old = before.get(key)
        new = after.get(key)
        if old == new:
            continue
        rows.append(
            {
                "resource": f"{key[0]}.{key[1].extension}",
                "change": "added" if old is None else "removed" if new is None else "content_changed",
                "source_byte_size": 0 if old is None else len(old),
                "candidate_byte_size": 0 if new is None else len(new),
                "source_sha256": "" if old is None else _sha256_bytes(old),
                "candidate_sha256": "" if new is None else _sha256_bytes(new),
            }
        )
    return rows


def _reserialize_wok_derived_tables(data: bytes, *, resref: str) -> tuple[bytes, dict[str, Any]]:
    """Rebuild BWM derived tables and prove that semantic/indexed data did not drift."""

    _source_parsed, source_audit = audit_bwm_bytes(data, source="source", resref=resref)
    if source_audit.get("signature") != "BWM " or source_audit.get("version") != "V1.0":
        raise ValueError(f"{resref}.wok is not a BWM V1.0 payload.")
    wok = WOKData.from_bytes(data)
    if not wok.faces:
        raise ValueError(f"{resref}.wok has no faces; refusing to synthesize collision geometry.")
    wok.raw = None
    candidate = wok.to_bytes()
    _candidate_parsed, candidate_audit = audit_bwm_bytes(
        candidate,
        source="derived-table repair",
        resref=resref,
    )

    fingerprint_keys = (
        "semantic",
        "face_indices",
        "material_order",
        "adjacency",
        "transition_records",
    )
    fingerprint_match = {
        key: source_audit.get("fingerprints", {}).get(key)
        == candidate_audit.get("fingerprints", {}).get(key)
        for key in fingerprint_keys
    }
    header_vectors_match = source_audit.get("header_vectors") == candidate_audit.get("header_vectors")
    if not all(fingerprint_match.values()) or not header_vectors_match:
        raise ValueError(f"{resref}.wok derived-table rebuild changed semantic/indexed data.")
    if not candidate_audit.get("raw_structure_valid"):
        raise ValueError(
            f"{resref}.wok remains structurally invalid after derived-table rebuild: "
            + "; ".join(candidate_audit.get("errors", []))
        )

    return candidate, {
        "resref": resref,
        "source_sha256": _sha256_bytes(data),
        "candidate_sha256": _sha256_bytes(candidate),
        "source_raw_structure_valid": bool(source_audit.get("raw_structure_valid")),
        "candidate_raw_structure_valid": bool(candidate_audit.get("raw_structure_valid")),
        "source_errors": list(source_audit.get("errors", [])),
        "source_perimeters": source_audit.get("perimeters", {}),
        "candidate_perimeters": candidate_audit.get("perimeters", {}),
        "source_aabb": source_audit.get("aabb", {}),
        "candidate_aabb": candidate_audit.get("aabb", {}),
        "fingerprint_match": fingerprint_match,
        "header_vectors_match": header_vectors_match,
    }


def _find_ascii_wok_keys(resources: dict[ResourceKey, bytes]) -> list[ResourceKey]:
    return sorted(
        (
            key
            for key, data in resources.items()
            if key[1] == ResourceType.WOK
            and key[0].endswith("-ascii")
            and not data.startswith(b"BWM ")
            and data.lstrip().lower().startswith(b"node ")
        ),
        key=lambda item: item[0],
    )


def _model_evidence(resources: dict[ResourceKey, bytes], resref: str) -> dict[str, Any]:
    mdl = resources.get((resref, ResourceType.MDL))
    mdx = resources.get((resref, ResourceType.MDX))
    evidence: dict[str, Any] = {
        "mdl_present": mdl is not None,
        "mdx_present": mdx is not None,
        "wok_present": (resref, ResourceType.WOK) in resources,
        "mdl_byte_size": len(mdl or b""),
        "mdx_byte_size": len(mdx or b""),
    }
    if mdl is None:
        return evidence
    try:
        model = read_mdl(mdl, source_ext=mdx or b"")
        nodes = list(model.all_nodes())
        evidence.update(
            {
                "internal_model_name": str(model.name),
                "node_count": len(nodes),
                "mesh_node_count": sum(getattr(node, "mesh", None) is not None for node in nodes),
                "light_node_count": sum(getattr(node, "light", None) is not None for node in nodes),
                "embedded_aabb_node_count": sum(getattr(node, "aabb", None) is not None for node in nodes),
            }
        )
    except Exception as exc:
        evidence["model_parse_error"] = f"{type(exc).__name__}: {exc}"
    return evidence


def _classify_canyon_rooms(resources: dict[ResourceKey, bytes]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resref in CANYON_PLAYABLE_ROOMS:
        data = resources.get((resref, ResourceType.WOK))
        wok_audit: dict[str, Any] = {}
        if data is not None:
            _parsed, wok_audit = audit_bwm_bytes(data, source="RNVcanyon", resref=resref)
        rows.append(
            {
                "resref": resref,
                "classification": "playable",
                "candidate_action": "retain_existing_binary_wok_byte_exact",
                "evidence": {
                    **_model_evidence(resources, resref),
                    "wok_raw_structure_valid": bool(wok_audit.get("raw_structure_valid")),
                    "wok_face_count": int(wok_audit.get("counts", {}).get("faces", 0)),
                    "wok_perimeter_loop_count": int(
                        wok_audit.get("perimeters", {}).get("perimeter_loop_count", 0)
                    ),
                },
            }
        )
    for resref in CANYON_NO_SOURCE_ROOMS:
        rows.append(
            {
                "resref": resref,
                "classification": "missing/invalid",
                "candidate_action": "blocked_no_collision_fabricated",
                "evidence": _model_evidence(resources, resref),
                "blocker": "LYT declares the room, but no MDL, MDX, or WOK resource survives.",
            }
        )
    for resref in CANYON_VISUAL_ONLY_ROOMS:
        evidence = _model_evidence(resources, resref)
        rows.append(
            {
                "resref": resref,
                "classification": "visual-only/backdrop",
                "candidate_action": "preserve_visual_model_without_fabricated_wok",
                "evidence": evidence,
                "classification_basis": (
                    "Surviving visual model has no embedded AABB walkmesh node and no external WOK; "
                    "the internal model identity/node mix is recorded for review."
                ),
            }
        )
    return rows


def _generate_city(source: Path, output_root: Path) -> dict[str, Any]:
    before = _capsule_resources(source)
    after = dict(before)
    repair_rows: list[dict[str, Any]] = []
    for resref in CITY_REPAIR_ROOMS:
        key = (resref, ResourceType.WOK)
        if key not in before:
            raise ValueError(f"RNVcity is missing expected repair target {resref}.wok.")
        repaired, repair = _reserialize_wok_derived_tables(before[key], resref=resref)
        source_perimeters = repair["source_perimeters"]
        if int(source_perimeters.get("open_loop_count", 0)) <= 0:
            raise ValueError(f"{resref}.wok is no longer an open-perimeter repair target.")
        after[key] = repaired
        repair_rows.append(repair)

    destination = output_root / "RNVcity" / "K2"
    target = destination / "RNVcity.perimeter-repaired.mod"
    _write_mod(after, target)
    reread = _capsule_resources(target)
    drift = _resource_drift(before, reread)
    expected = {f"{resref}.wok" for resref in CITY_REPAIR_ROOMS}
    actual = {row["resource"] for row in drift}
    if actual != expected or any(row["change"] != "content_changed" for row in drift):
        raise ValueError(f"RNVcity candidate resource drift escaped the repair scope: {drift}")
    audit = audit_mod(target, module="rnvcity", game="K2", roundtrip=True)
    return {
        "module": "RNVcity",
        "game": "K2",
        "source": _artifact_record(source),
        "candidate": _artifact_record(target),
        "repair": "rebuild_derived_bwm_tables_for_four_open_perimeters",
        "repair_rows": repair_rows,
        "resource_drift": drift,
        "mod_audit": audit,
        "candidate_pass": bool(audit.get("audit_pass")),
        "kmap_roundtrip": {
            "attempted": False,
            "reason": "No RNVcity KMAP source exists; generating one would exceed a derived-table-only repair.",
        },
        "retail_game_proven": False,
    }


def _generate_canyon(source: Path, output_root: Path) -> dict[str, Any]:
    before = _capsule_resources(source)
    after = dict(before)
    ascii_keys = _find_ascii_wok_keys(before)
    if len(ascii_keys) != 7:
        raise ValueError(f"Expected seven mislabeled ASCII WOK payloads, found {len(ascii_keys)}.")
    removed: list[dict[str, Any]] = []
    for key in ascii_keys:
        base = key[0][:-6]
        real_key = (base, ResourceType.WOK)
        if real_key not in before or not before[real_key].startswith(b"BWM "):
            raise ValueError(f"{key[0]}.wok has no corresponding binary {base}.wok to retain.")
        data = after.pop(key)
        removed.append(
            {
                "resource": f"{key[0]}.wok",
                "byte_size": len(data),
                "sha256": _sha256_bytes(data),
                "detected_prefix": data[:32].decode("ascii", "replace"),
                "reason": "ASCII node-trimesh text was packed with ResourceType.WOK.",
            }
        )

    destination = output_root / "RNVcanyon" / "K2"
    target = destination / "RNVcanyon.ascii-wok-cleaned.mod"
    _write_mod(after, target)
    reread = _capsule_resources(target)
    drift = _resource_drift(before, reread)
    expected_removed = {f"{key[0]}.wok" for key in ascii_keys}
    if {row["resource"] for row in drift} != expected_removed or any(
        row["change"] != "removed" for row in drift
    ):
        raise ValueError(f"RNVcanyon candidate resource drift escaped the cleanup scope: {drift}")

    retained_woks: list[dict[str, Any]] = []
    for resref in CANYON_PLAYABLE_ROOMS:
        key = (resref, ResourceType.WOK)
        if before.get(key) != reread.get(key):
            raise ValueError(f"{resref}.wok was not retained byte-for-byte.")
        data = reread[key]
        _parsed, wok_audit = audit_bwm_bytes(data, source=str(target), resref=resref)
        retained_woks.append(
            {
                "resource": f"{resref}.wok",
                "byte_size": len(data),
                "sha256": _sha256_bytes(data),
                "raw_structure_valid": bool(wok_audit.get("raw_structure_valid")),
                "face_count": int(wok_audit.get("counts", {}).get("faces", 0)),
                "perimeter_loop_count": int(
                    wok_audit.get("perimeters", {}).get("perimeter_loop_count", 0)
                ),
            }
        )

    classifications = _classify_canyon_rooms(reread)
    audit = audit_mod(target, module="rnvcanyon", game="K2", roundtrip=True)
    missing_invalid = [
        row["resref"] for row in classifications if row["classification"] == "missing/invalid"
    ]
    return {
        "module": "RNVcanyon",
        "game": "K2",
        "source": _artifact_record(source),
        "candidate": _artifact_record(target),
        "repair": "remove_seven_ascii_text_payloads_mislabeled_as_wok",
        "removed_mislabeled_resources": removed,
        "retained_binary_woks": retained_woks,
        "room_classification": classifications,
        "resource_drift": drift,
        "mod_audit": audit,
        "candidate_pass": False,
        "candidate_blockers": [
            f"No source art or WOK survives for: {', '.join(missing_invalid)}.",
            "Normal MOD audit remains blocked by LYT rooms without WOKs; visual-only rooms are documented rather than given fabricated collision.",
        ],
        "kmap_roundtrip": {
            "attempted": False,
            "reason": "No RNVcanyon KMAP source exists; its three no-source LYT rooms prevent a faithful KMAP conversion.",
        },
        "retail_game_proven": False,
    }


def _write_readme(report: dict[str, Any], path: Path) -> None:
    city, canyon = report["candidates"]
    city_changed = ", ".join(row["resource"] for row in city["resource_drift"])
    canyon_removed = ", ".join(row["resource"] for row in canyon["resource_drift"])
    lines = [
        "# RNV KOTOR 2 walkmesh cleanup candidates",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        "These files are isolated structural candidates. The source MODs and KOTOR 2 install were not modified.",
        "",
        "## RNVcity",
        "",
        f"Candidate: `{city['candidate']['path']}`",
        "",
        f"Changed resources: {city_changed}.",
        "",
        "The four source WOKs had complete geometry, adjacency, AABB coverage, and exact boundary-edge sets, but their serialized perimeter walk was open. The candidate rebuilds derived tables only. Semantic, face-index, surface-order, adjacency, transition, and header-vector fingerprints are unchanged.",
        "",
        f"Structural MOD audit: **{'pass' if city['mod_audit'].get('audit_pass') else 'FAIL'}**.",
        "",
        "## RNVcanyon",
        "",
        f"Candidate: `{canyon['candidate']['path']}`",
        "",
        f"Removed mislabeled resources: {canyon_removed}.",
        "",
        "The real binary WOKs for `koq200_01a` through `koq200_01g` remain byte-identical. `koq200_02` and `valsky` are classified as visual-only/backdrop resources from their surviving model structure and lack of embedded/external walkmesh. `koq200_01l`, `koq200_01m`, and `koq200_01n` remain blocked because no MDL, MDX, or WOK survives. No collision was invented.",
        "",
        f"Structural MOD audit: **{'pass' if canyon['mod_audit'].get('audit_pass') else 'blocked'}** (expected: unresolved no-source LYT rooms).",
        "",
        "## Proof boundary",
        "",
        "Neither candidate is retail-game proven. Test only after staging one candidate at a time for KOTOR 2, then manually warp, click-to-move across every room, cross transitions, test camera containment, save, reload, and capture the live log.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-root", type=Path, default=DEFAULT_MODULE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    module_root = args.module_root.expanduser().resolve()
    output_root = args.output_dir.expanduser().resolve()
    city_source = module_root / "RNVcity.mod"
    canyon_source = module_root / "RNVcanyon.mod"
    if not city_source.is_file() or not canyon_source.is_file():
        raise FileNotFoundError(f"Expected {city_source} and {canyon_source}.")

    candidates = [
        _generate_city(city_source, output_root),
        _generate_canyon(canyon_source, output_root),
    ]
    report = {
        "schema": "ghoststudio.rnv-walkmesh-candidates.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "module_root": str(module_root),
        "output_root": str(output_root),
        "source_files_modified": False,
        "game_install_modified": False,
        "proof_scope": "raw BWM, semantic fingerprint, resource-drift, MOD reopen, and WOK round-trip audit only",
        "retail_game_proven": False,
        "candidates": candidates,
    }
    manifest = output_root / "RNV_walkmesh_candidates_manifest.json"
    readme = output_root / "RNV_WALKMESH_CANDIDATES.md"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_readme(report, readme)
    print(
        json.dumps(
            {
                "manifest": str(manifest),
                "readme": str(readme),
                "rnvcity_candidate": candidates[0]["candidate"],
                "rnvcity_audit_pass": candidates[0]["mod_audit"].get("audit_pass"),
                "rnvcanyon_candidate": candidates[1]["candidate"],
                "rnvcanyon_audit_pass": candidates[1]["mod_audit"].get("audit_pass"),
                "rnvcanyon_blockers": candidates[1]["candidate_blockers"],
            },
            indent=2,
        )
    )
    return 0 if candidates[0]["candidate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
