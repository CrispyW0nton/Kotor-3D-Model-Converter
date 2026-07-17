"""Create isolated walkmesh-repair candidates from the converted-module audit.

This command never overwrites an indexed Converted artifact or a game install.
It writes only beneath ``Converted/WalkmeshAudit/GeneratedCandidates`` and
records source/candidate hashes plus focused structural audits.

The current deterministic repairs are intentionally narrow:

* ``undclb``: move the stale entry point from the missing second room to the
  centroid of the nearest non-boundary walkable face in the surviving room.
* ``vul803``: reserialize its surviving WOK with Ghost Studio's index-topology
  writer so the AABB split-plane table uses the vanilla-supported bitmasks.

No geometry is fabricated for structural-only ``vul801``.  Imported zero-area
faces and unused legacy vertices are reported but preserved because retail
libraries contain the same classes of anomaly and blind deletion can change
collision seams or perimeter ownership.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
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
from pykotor.resource.formats.gff import bytes_gff, read_gff  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402

from core.modules.module_format import WOKData  # noqa: E402
from scripts.audit_walkmesh_library import audit_kmap, audit_mod  # noqa: E402
from src.core.level.kmap_serializer import KMapSerializer  # noqa: E402
from src.core.modules.authored_module_kmap_bridge import (  # noqa: E402
    authored_project_from_kmap_payload,
)
from src.core.modules.authored_module_walkmesh import (  # noqa: E402
    combine_authored_module_walkmesh,
)
from src.core.modules.authored_walkmesh_surfaces import (  # noqa: E402
    is_walkable_walkmesh_surface,
)


DEFAULT_STATUS = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\CONVERSION_STATUS.json"
)
DEFAULT_OUTPUT = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\WalkmeshAudit\GeneratedCandidates"
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _indexed_output(status: dict[str, Any], module: str, game: str) -> dict[str, Any]:
    for candidate in status.get("candidates", []):
        if str(candidate.get("module", "")).strip().lower() != module.lower():
            continue
        output = dict(candidate.get("outputs", {}).get(game, {}) or {})
        if output:
            return output
    raise KeyError(f"CONVERSION_STATUS has no {game} output row for {module}.")


def _capsule_resources(path: Path) -> dict[tuple[str, ResourceType], bytes]:
    return {
        (str(resource.resname()).strip().lower(), resource.restype()): bytes(resource.data())
        for resource in Capsule(path)
    }


def _write_mod(resources: dict[tuple[str, ResourceType], bytes], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = ERF(ERFType.MOD)
    for (resref, restype), data in sorted(
        resources.items(), key=lambda item: (item[0][0], item[0][1].extension)
    ):
        archive.set_data(resref, restype, data)
    write_erf(archive, path)


def _triangle_area_xy(vertices: list[tuple[float, float, float]]) -> float:
    a, b, c = vertices
    return abs(
        ((b[0] - a[0]) * (c[1] - a[1]))
        - ((b[1] - a[1]) * (c[0] - a[0]))
    ) * 0.5


def _safe_entry_from_kmap(path: Path) -> dict[str, Any]:
    project_file = KMapSerializer.load(path)
    payload = project_file.extra_sections.get("authored_module")
    if not isinstance(payload, dict):
        raise ValueError(f"{path} has no authored_module payload.")
    project = authored_project_from_kmap_payload(payload)
    old = tuple(float(value) for value in project.placements.entry_point.position)
    combined = combine_authored_module_walkmesh(project)
    if combined.blocking_issues:
        raise ValueError("; ".join(combined.blocking_issues))

    rows: list[dict[str, Any]] = []
    for face_index, face in enumerate(combined.wok.faces):
        if not is_walkable_walkmesh_surface(int(face.surface)):
            continue
        indices = (int(face.v1), int(face.v2), int(face.v3))
        if any(index < 0 or index >= len(combined.wok.verts) for index in indices):
            continue
        vertices = [tuple(float(value) for value in combined.wok.verts[index]) for index in indices]
        area = _triangle_area_xy(vertices)
        if area <= 1.0e-9:
            continue
        centroid = tuple(sum(vertex[axis] for vertex in vertices) / 3.0 for axis in range(3))
        rows.append(
            {
                "face_index": face_index,
                "surface": int(face.surface),
                "centroid": centroid,
                "area_xy": area,
                "horizontal_distance": math.hypot(centroid[0] - old[0], centroid[1] - old[1]),
                "non_boundary": min(int(face.adj1), int(face.adj2), int(face.adj3)) >= 0,
            }
        )
    if not rows:
        raise ValueError(f"{path} has no nondegenerate walkable WOK face.")

    # Prefer a face that does not directly touch the perimeter so the player is
    # not spawned on a collision edge.  Among safe faces, preserve the original
    # design intent by choosing the closest centroid; area and face index make
    # ties deterministic.
    interior = [row for row in rows if row["non_boundary"]]
    pool = interior or rows
    chosen = min(
        pool,
        key=lambda row: (
            float(row["horizontal_distance"]),
            -float(row["area_xy"]),
            int(row["face_index"]),
        ),
    )
    return {
        "old_position": old,
        "new_position": tuple(float(value) for value in chosen["centroid"]),
        "face_index": int(chosen["face_index"]),
        "surface": int(chosen["surface"]),
        "face_area_xy": float(chosen["area_xy"]),
        "horizontal_move": float(chosen["horizontal_distance"]),
        "non_boundary_face": bool(chosen["non_boundary"]),
    }


def _write_entry_repaired_kmap(source: Path, target: Path, position: tuple[float, float, float]) -> None:
    project = KMapSerializer.load(source)
    payload = project.extra_sections.get("authored_module")
    if not isinstance(payload, dict):
        raise ValueError(f"{source} has no authored_module payload.")
    patched = copy.deepcopy(payload)
    patched.setdefault("placements", {}).setdefault("entry_point", {})["position"] = list(position)
    project.extra_sections["authored_module"] = patched
    target.parent.mkdir(parents=True, exist_ok=True)
    KMapSerializer.save(project, target)


def _patch_mod_entry(
    resources: dict[tuple[str, ResourceType], bytes],
    position: tuple[float, float, float],
) -> tuple[str, ResourceType]:
    key = next((key for key in resources if key[1] == ResourceType.IFO), None)
    if key is None:
        raise ValueError("MOD has no IFO resource to receive the repaired entry point.")
    ifo = read_gff(resources[key])
    ifo.root.set_single("Mod_Entry_X", float(position[0]))
    ifo.root.set_single("Mod_Entry_Y", float(position[1]))
    ifo.root.set_single("Mod_Entry_Z", float(position[2]))
    resources[key] = bytes(bytes_gff(ifo))
    return key


def _repair_wok_aabb(
    resources: dict[tuple[str, ResourceType], bytes],
    *,
    resref: str,
) -> tuple[str, ResourceType]:
    key = (resref.lower(), ResourceType.WOK)
    if key not in resources:
        raise ValueError(f"MOD has no {resref}.wok resource.")
    parsed = WOKData.from_bytes(resources[key])
    if not parsed.faces:
        raise ValueError(f"{resref}.wok has no faces; refusing to synthesize collision geometry.")
    # This operation explicitly repairs derived tables, so bypass the normal
    # exact-byte preservation path used for unchanged imported WOKs.
    parsed.raw = None
    resources[key] = parsed.to_bytes()
    return key


def _resource_drift(
    before: dict[tuple[str, ResourceType], bytes],
    after: dict[tuple[str, ResourceType], bytes],
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
                "source_sha256": "" if old is None else _sha256_bytes(old),
                "candidate_sha256": "" if new is None else _sha256_bytes(new),
            }
        )
    return rows


def _artifact_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _generate_undclb(
    status: dict[str, Any], game: str, output_root: Path
) -> dict[str, Any]:
    indexed = _indexed_output(status, "undclb", game)
    source_mod = Path(str(indexed["mod"]))
    source_kmap = Path(str(indexed["kmap"]))
    destination = output_root / "undclb" / game
    target_mod = destination / "undclb.entry-repaired.mod"
    target_kmap = destination / "undclb.entry-repaired.kmap"

    choice = _safe_entry_from_kmap(source_kmap)
    new_position = tuple(choice["new_position"])
    before = _capsule_resources(source_mod)
    after = dict(before)
    _patch_mod_entry(after, new_position)
    _write_mod(after, target_mod)
    _write_entry_repaired_kmap(source_kmap, target_kmap, new_position)

    mod_audit = audit_mod(target_mod, module="undclb", game=game, roundtrip=True)
    kmap_audit = audit_kmap(target_kmap, module="undclb", game=game, roundtrip=True)
    return {
        "module": "undclb",
        "game": game,
        "repair": "entry_point_to_nearest_non_boundary_walkable_face_centroid",
        "entry_choice": choice,
        "source_mod": _artifact_record(source_mod),
        "source_kmap": _artifact_record(source_kmap),
        "candidate_mod": _artifact_record(target_mod),
        "candidate_kmap": _artifact_record(target_kmap),
        "mod_resource_drift": _resource_drift(before, _capsule_resources(target_mod)),
        "mod_audit": mod_audit,
        "kmap_audit": kmap_audit,
        "candidate_pass": bool(mod_audit.get("audit_pass") and kmap_audit.get("audit_pass")),
        "retail_game_proven": False,
    }


def _generate_vul803(
    status: dict[str, Any], game: str, output_root: Path
) -> dict[str, Any]:
    indexed = _indexed_output(status, "vul803", game)
    source_mod = Path(str(indexed["mod"]))
    source_kmap = Path(str(indexed["kmap"]))
    destination = output_root / "vul803" / game
    target_mod = destination / "vul803.aabb-repaired.mod"
    target_kmap = destination / "vul803.aabb-repaired.kmap"

    before = _capsule_resources(source_mod)
    after = dict(before)
    _repair_wok_aabb(after, resref="vul803_01a")
    _write_mod(after, target_mod)
    target_kmap.parent.mkdir(parents=True, exist_ok=True)
    target_kmap.write_bytes(source_kmap.read_bytes())

    mod_audit = audit_mod(target_mod, module="vul803", game=game, roundtrip=True)
    kmap_audit = audit_kmap(target_kmap, module="vul803", game=game, roundtrip=True)
    return {
        "module": "vul803",
        "game": game,
        "repair": "rebuild_wok_aabb_adjacency_and_perimeter_tables_without_new_geometry",
        "source_mod": _artifact_record(source_mod),
        "source_kmap": _artifact_record(source_kmap),
        "candidate_mod": _artifact_record(target_mod),
        "candidate_kmap": _artifact_record(target_kmap),
        "mod_resource_drift": _resource_drift(before, _capsule_resources(target_mod)),
        "mod_audit": mod_audit,
        "kmap_audit": kmap_audit,
        "candidate_pass": bool(mod_audit.get("audit_pass") and kmap_audit.get("audit_pass")),
        "retail_game_proven": False,
    }


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Converted walkmesh generated candidates",
        "",
        f"Generated: `{report['generated_utc']}`",
        "",
        report["proof_scope"],
        "",
        "## Candidate results",
        "",
        "| Module | Game | Repair | MOD audit | KMAP audit | Changed MOD resources |",
        "|---|---|---|---:|---:|---|",
    ]
    entry_details: list[str] = []
    for row in report["candidates"]:
        lines.append(
            f"| {row['module']} | {row['game']} | {row['repair']} | "
            f"{'pass' if row['mod_audit'].get('audit_pass') else 'FAIL'} | "
            f"{'pass' if row['kmap_audit'].get('audit_pass') else 'FAIL'} | "
            f"{', '.join(item['resource'] for item in row['mod_resource_drift']) or 'none'} |"
        )
        if row.get("entry_choice"):
            choice = row["entry_choice"]
            entry_details.append(
                f"- `{row['module']}` {row['game']} entry: "
                f"`{tuple(round(v, 6) for v in choice['old_position'])}` → "
                f"`{tuple(round(v, 6) for v in choice['new_position'])}` "
                f"on face {choice['face_index']} (surface {choice['surface']}, "
                f"non-boundary={choice['non_boundary_face']})."
            )

    lines.extend(["", "## Entry relocation details", "", *entry_details])

    lines.extend(
        [
            "",
            "## Deliberate non-repairs",
            "",
            "- `vul801`: no candidate was generated. Its indexed outputs are structural-only, "
            "the LYT is deliberately empty, and the surviving room has no visible geometry. "
            "Inventing a floor would misrepresent missing source art as recovery.",
            "- Imported zero-area faces were preserved. Vanilla libraries contain legacy "
            "degeneracies; removing one without authoring context can change collision seams.",
            "- Unreferenced legacy vertices were preserved in canonical files. Their loss on "
            "an in-memory round trip does not alter referenced triangles, but is not a reason "
            "to rewrite an otherwise valid imported WOK.",
            "",
            "## Proof boundary",
            "",
            "These candidates pass raw BWM table checks, Ghost Studio serialization, KMAP "
            "reopen/compile, and entry-on-walkmesh checks. They are not KOTOR retail proof. "
            "Manual warp, movement across every accessible region, transition, and camera-"
            "containment testing is still required in each target game.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    status_path = args.status.expanduser().resolve()
    output_root = args.output_dir.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    status = json.loads(status_path.read_text(encoding="utf-8"))

    candidates: list[dict[str, Any]] = []
    for game in ("K1", "K2"):
        candidates.append(_generate_undclb(status, game, output_root))
        candidates.append(_generate_vul803(status, game, output_root))
    report = {
        "schema": "ghoststudio.converted-walkmesh-generated-candidates.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status_path": str(status_path),
        "status_sha256": _sha256_file(status_path),
        "output_root": str(output_root),
        "proof_scope": (
            "Non-destructive candidate generation plus raw/round-trip BWM and KMAP structural audit; "
            "not retail KOTOR proof."
        ),
        "canonical_artifacts_modified": False,
        "candidate_count": len(candidates),
        "candidate_pass_count": sum(bool(row["candidate_pass"]) for row in candidates),
        "candidates": candidates,
        "excluded": [
            {
                "module": "vul801",
                "reason": "structural-only/reference-only; visible geometry and authoritative WOKs are missing",
                "candidate_generated": False,
            }
        ],
    }
    json_path = output_root / "generated_candidates_manifest.json"
    markdown_path = output_root / "README.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(report, markdown_path)
    print(
        json.dumps(
            {
                "candidate_count": report["candidate_count"],
                "candidate_pass_count": report["candidate_pass_count"],
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            indent=2,
        )
    )
    return 0 if report["candidate_pass_count"] == report["candidate_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
