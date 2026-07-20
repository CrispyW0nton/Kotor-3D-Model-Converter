"""Build honest K2 candidates for the recovered RNV modules.

``RNVcanyon`` (area ``koq200``) remains the provenance-preserving seven-room
partial.  The canonical ``--module koq200`` route is a separate hybrid: it
uses the byte-audited complete K2 MDL/MDX/WOK triplets for ``koq200_01a``
through ``koq200_01h`` and adds the two evidence-verified RNV visual-only
partitions (``koq200_02`` and ``valsky``).  Missing LYT-only rooms
(``koq200_01l``/``01m``/``01n``) are still omitted rather than fabricated.

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
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
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

from src.core.assets.resource_manager import RES_NCS, RES_TGA, RES_TPC, ResourceManager  # noqa: E402
from src.core.geometry.model_data import NodeFlags  # noqa: E402
from src.core.mdl.mdl_parser import MDLBinaryParser  # noqa: E402
from src.core.modules.module_format import (  # noqa: E402
    LYTLayout,
    LYTRoom,
    VISData,
    WALKABLE_IDS,
    WOKData,
)
from src.core.workflow.legacy_module_repair import (  # noqa: E402
    LegacyModuleCandidateRequest,
    build_legacy_module_candidate,
)

from scripts.generate_legacy_room_walkmesh_candidates import (  # noqa: E402
    _artifact,
    _candidate_proofs,
    _compile_static_binary_room,
    _filtered_lyt,
    _parse_lyt_rooms,
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
KOQ200_AUDITED_COMPLETE_RESOURCES = (
    DEFAULT_MODULE_ROOT / "Converted" / "Candidates" / "koq200" / "K2" / "Candidate" / "Resources"
)
KOQ200_COMPLETE_PLAYABLE_ROOMS = tuple(f"koq200_01{suffix}" for suffix in "abcdefgh")
KOQ200_RNV_VISUAL_ONLY_ROOMS = ("koq200_02", "valsky")
KOQ200_HYBRID_ROOM_ORDER = KOQ200_COMPLETE_PLAYABLE_ROOMS + KOQ200_RNV_VISUAL_ONLY_ROOMS
KOQ201_LOCAL_01A_WOK = (
    DEFAULT_MODULE_ROOT
    / "Converted"
    / "Candidates"
    / "koq201"
    / "K2"
    / "Resources"
    / "koq201_01a.wok"
)
KOQ201_LOCAL_01A_WOK_SHA256 = (
    "836ef5d11505b5e6e64a4a038552cd57c8494078e5cf22eb8406c3642c4a42b4"
)
KOQ201_PLAYABLE_ROOMS = tuple(f"koq201_01{suffix}" for suffix in "abcdefghj")
KOQ201_EXPECTED_RECIPROCAL_TRANSITION_PAIRS = 5
KOQ201_EXPECTED_PATH_COMPONENTS = 4
KOQ200_FAILED_CONSERVATIVE_BASELINE = {
    "mod_sha256": "6395c56e2ee6184a29e505206e90fec0019306f169c51766ea6fcfd978667a78",
    "manual_k2_warp_result": "failed_crash_before_currentgame_cache",
    "proof_source": "user-reported manual KOTOR 2 warp on 2026-07-18",
    "consequence": (
        "Structural acceptance did not predict retail loadability. New KOQ200 artifacts remain "
        "bisection inputs until a room/metadata transplant isolates the crash."
    ),
}

# These hashes are the byte-structurally audited room triplets.  The canonical
# hybrid route fails closed if its input directory drifts, rather than silently
# compiling a different room set under the same KOQ200 label.
KOQ200_AUDITED_ROOM_HASHES: dict[str, dict[str, str]] = {
    "koq200_01a": {
        "mdl": "1035a17522f17ae62bbf5851d3832754a56dbcd1b2cc479aac73ada2656f33f8",
        "mdx": "62ef380d25573e0b6324d5ef7e8782a49977b999e44d5f4816276da6fc7aecf4",
        "wok": "e6843e1588d1d96884cbb2ec6d797c824656446585ed61d9ba4cfa8fdac83638",
    },
    "koq200_01b": {
        "mdl": "67c09da27497ba79da0812992f1f45e259b1da69f6e06493d2f732b3c7507cb1",
        "mdx": "e54611658eff60015af8e7a49e03c7eafa749b6375c30167c1747af3ca3e2400",
        "wok": "fe39afd8ce70cf2655e3c21441574c62e1c8bbed25b08f908191f77d1c41b6cf",
    },
    "koq200_01c": {
        "mdl": "44babe8929f1aa7e292d1aaa81b652ccdd67ab3023b9a0f545d48b7dd910f964",
        "mdx": "35517d55791a35eadf19c2af783d0408c036c136c100d72fd472bc2450b8b8a8",
        "wok": "b3457be8fb957bd059bed59b663a5a1af06089084d18e392ed33cd87c9f95c9c",
    },
    "koq200_01d": {
        "mdl": "d370220388c7159ebf58fdf1a194ff0f85e9c407254f708569e109494bf13c02",
        "mdx": "21ce74d18aee0fca9175cbf56265e2548b59304f136e370f584e92e236898943",
        "wok": "53e714b8fcfb2573ff4234acad21d1d80b00c8414fd71b432a877faefa8f9e09",
    },
    "koq200_01e": {
        "mdl": "855238177e121773ba7d80c32a6d2c602922c0dd01851119dbce34dd99c7b6ba",
        "mdx": "30f0e0bcb8c47ed56e7740e3d9c784b2fb8376d739c2b53175a41132f6a5de06",
        "wok": "80c9c789db60e53cc1e906e2533bb9f51d6b3554b1c7f4969682b3885507b2ec",
    },
    "koq200_01f": {
        "mdl": "b2ff7bc19227176b2c654cc951d4e110b12503ef16a4f4b34fcecb6e1888fed3",
        "mdx": "01e44fb7c4b0cb85ee171ad21e671b60e41b2ec1aa3b0891b1ffcce50d9bea9d",
        "wok": "eabaeed2b308b108b95e5693a4556e5766da8b64c9973a61ab25d529c0b0dd06",
    },
    "koq200_01g": {
        "mdl": "25ff58fa9a99d99b09e2143c76ad17dc94fd28af52e980d6aac646b9d995e221",
        "mdx": "2720cd3c9b43bba8b231c33e5c534f68e2d197fe543c11218bb9221e643f6a81",
        "wok": "d56a3d929e3e623ae157628bdcc387757d79c5deabdb7c51ec5624d288464dcb",
    },
    "koq200_01h": {
        "mdl": "11f83220459eb4f4e1ccf40f7944ab8b7f7e291dee02cc7aa55fd42cdd4eebee",
        "mdx": "312aa40991957f20a439205fa401e73cd690b2ad69aaf1a8dfc9832f57067e4f",
        "wok": "dff488e33cf37c5a79c737311caccdc21f7ba9ae8f2ca5096acf986b06f33be7",
    },
}

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

# The recovered downloads use community-facing archive names, while their
# actual Odyssey area identities are KOQ200 and KOQ201.  Keep the historical
# RNV outputs available for provenance, but allow a canonical build whose MOD
# filename, module resources, IFO routing, KMAP name, and warp resref all agree.
MODULE_ALIASES: dict[str, str] = {
    "koq200": "rnvcanyon",
    "koq201": "rnvcity",
}
DEFAULT_MODULES: tuple[str, ...] = ("rnvcanyon", "rnvcity")

CANONICAL_MODULE_PLANS: dict[str, dict[str, Any]] = {
    "koq200": {
        **MODULE_PLANS["rnvcanyon"],
        "source_module": "rnvcanyon",
        "playable_rooms": KOQ200_COMPLETE_PLAYABLE_ROOMS,
        "visual_only_rooms": KOQ200_RNV_VISUAL_ONLY_ROOMS,
        "combined_room_order": KOQ200_HYBRID_ROOM_ORDER,
        "source_transition_room_resrefs": KOQ200_COMPLETE_PLAYABLE_ROOMS,
        "audited_candidate_resources_dir": KOQ200_AUDITED_COMPLETE_RESOURCES,
        "audited_room_hashes": KOQ200_AUDITED_ROOM_HASHES,
        "use_audited_candidate_metadata": True,
        "preserve_audited_room_bytes": True,
        "keep_unresolved_module_scripts_explicit": False,
        "neutralize_unresolved_module_scripts": True,
        "known_failed_baseline": KOQ200_FAILED_CONSERVATIVE_BASELINE,
        "requires_room_metadata_transplant_bisection": True,
    },
    "koq201": {
        **MODULE_PLANS["rnvcity"],
        "source_module": "rnvcity",
        "playable_rooms": KOQ201_PLAYABLE_ROOMS,
        # The recovered 76-face 01a AABB is the centralized union of local
        # partitions 01a..01f.  Promoting it as 01a's external WOK duplicates
        # collision from five other rooms and erases the 01a -> 01b portal.
        # Use the already-derived-table-repaired six-face local partition.
        "authoritative_wok_overrides": {
            "koq201_01a": KOQ201_LOCAL_01A_WOK,
        },
        "authoritative_wok_hashes": {
            "koq201_01a": KOQ201_LOCAL_01A_WOK_SHA256,
        },
        "reject_cross_room_wok_face_duplicates": True,
        "expected_reciprocal_transition_pair_count": (
            KOQ201_EXPECTED_RECIPROCAL_TRANSITION_PAIRS
        ),
        "expected_path_graph_component_count": KOQ201_EXPECTED_PATH_COMPONENTS,
        "neutralize_unresolved_module_scripts": True,
        "keep_unresolved_module_scripts_explicit": False,
        "require_engine_readback_and_kmap_parity": True,
    },
}

# The source KOQ200 WOKs contain several steep faces, but slope alone is not a
# valid Odyssey wall classifier.  Known-loadable K1/K2 exterior WOKs retain
# isolated 46-90 degree walkable faces, including fully-adjacent rough-terrain
# connectors and narrow boundary strips.  These ten source-indexed faces were
# reviewed separately: each is part of a paired boundary wall strip, spans at
# least six world units vertically, carries no transition record, and is not a
# floor-region margin.  Keep the policy canonical-KOQ200-only and fail closed if
# the recovered source topology ever changes under these indices.
KOQ200_REVIEWED_WALL_FACE_INDICES: dict[str, tuple[int, ...]] = {
    "koq200_01d": (174, 175),
    "koq200_01e": (71, 72, 73, 74, 75, 76, 77, 78),
}
KOQ200_REVIEWED_WALL_MIN_SLOPE_DEGREES = 70.0
KOQ200_REVIEWED_WALL_MIN_Z_SPAN = 6.0


def _resolve_module_plan(module: str) -> tuple[str, dict[str, Any]]:
    canonical = CANONICAL_MODULE_PLANS.get(module)
    if canonical is not None:
        return str(canonical["source_module"]), canonical
    source_module = MODULE_ALIASES.get(module, module)
    try:
        return source_module, MODULE_PLANS[source_module]
    except KeyError as exc:
        choices = ", ".join(sorted(set(MODULE_PLANS) | set(MODULE_ALIASES)))
        raise ValueError(f"Unknown RNV/KOQ module {module!r}; choose one of: {choices}.") from exc


def _wok_face_geometry(wok: WOKData, face_index: int) -> dict[str, Any]:
    """Measure one source-indexed WOK face without changing its topology."""

    face = wok.faces[face_index]
    indices = (int(face.v1), int(face.v2), int(face.v3))
    points = tuple(wok.verts[index] for index in indices)
    a, b, c = points
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = (
        (uy * vz) - (uz * vy),
        (uz * vx) - (ux * vz),
        (ux * vy) - (uy * vx),
    )
    normal_length = math.sqrt((nx * nx) + (ny * ny) + (nz * nz))
    slope = (
        math.degrees(math.acos(max(0.0, min(1.0, abs(nz) / normal_length))))
        if normal_length > 1.0e-12
        else 0.0
    )
    adjacencies = (int(face.adj1), int(face.adj2), int(face.adj3))
    transitions = (int(face.trans1), int(face.trans2), int(face.trans3))
    return {
        "source_face_index": int(face_index),
        "vertex_indices": list(indices),
        "surface_before": int(face.surface),
        "surface_after": None,
        "decision": "removed_from_floor_wok",
        "slope_degrees": round(slope, 6),
        "area_3d": round(normal_length * 0.5, 6),
        "area_xy": round(abs(nz) * 0.5, 6),
        "x_span": round(max(point[0] for point in points) - min(point[0] for point in points), 6),
        "y_span": round(max(point[1] for point in points) - min(point[1] for point in points), 6),
        "z_span": round(max(point[2] for point in points) - min(point[2] for point in points), 6),
        "adjacencies": list(adjacencies),
        "boundary_edge_count": sum(value < 0 for value in adjacencies),
        "transitions": list(transitions),
        "transition_edge_count": sum(value >= 0 for value in transitions),
    }


def _transition_semantics(
    wok: WOKData,
    *,
    excluded_face_indices: frozenset[int] = frozenset(),
) -> list[tuple[tuple[int, int, int], int, int]]:
    """Describe transition edges independently of renumbered face rows."""

    rows: list[tuple[tuple[int, int, int], int, int]] = []
    for face_index, face in enumerate(wok.faces):
        if face_index in excluded_face_indices:
            continue
        triangle = (int(face.v1), int(face.v2), int(face.v3))
        for edge_index, transition in enumerate((face.trans1, face.trans2, face.trans3)):
            if int(transition) >= 0:
                rows.append((triangle, edge_index, int(transition)))
    return rows


def _preserved_steep_face_rows(
    wok: WOKData,
    *,
    threshold_degrees: float = 45.0,
) -> list[dict[str, Any]]:
    """Enumerate steep walkable faces left for retail traversal proof."""

    rows: list[dict[str, Any]] = []
    for face_index, face in enumerate(wok.faces):
        if int(face.surface) not in WALKABLE_IDS:
            continue
        row = _wok_face_geometry(wok, face_index)
        if float(row["slope_degrees"]) <= float(threshold_degrees):
            continue
        row["surface_after"] = int(face.surface)
        row["decision"] = "preserved_for_manual_traversal"
        row["reason"] = (
            "Slope alone is not an Odyssey wall classifier; comparable known-loadable exterior "
            "WOKs retain steep rough-terrain and connector faces."
        )
        rows.append(row)
    return rows


def _remove_reviewed_floor_wall_faces(
    data: bytes,
    *,
    room: str,
    face_indices: tuple[int, ...],
    min_slope_degrees: float = KOQ200_REVIEWED_WALL_MIN_SLOPE_DEGREES,
    min_z_span: float = KOQ200_REVIEWED_WALL_MIN_Z_SPAN,
) -> tuple[bytes, dict[str, Any]]:
    """Remove an explicit, evidence-reviewed wall strip from one floor WOK.

    The caller supplies source face indices; this function deliberately does
    not discover faces from slope alone.  Geometry and topology guards make a
    changed source fail rather than applying an obsolete review decision.
    """

    from src.core.validation.kotor_module_engine_contract import inspect_raw_wok_structure

    source = WOKData.from_bytes(data)
    if not source.faces or source.adjacency_domain_count is None:
        raise ValueError(f"{room}.wok has no parsed adjacency-domain topology.")
    selected = tuple(sorted({int(index) for index in face_indices}))
    selected_set = frozenset(selected)
    if not selected or selected[-1] >= len(source.faces) or selected[0] < 0:
        raise ValueError(f"{room}.wok reviewed wall indices are outside the source face table.")
    adjacency_domain_before = int(source.adjacency_domain_count)
    if any(index >= adjacency_domain_before for index in selected):
        raise ValueError(f"{room}.wok reviewed wall face is outside its walkable adjacency domain.")

    removed = [_wok_face_geometry(source, index) for index in selected]
    for row in removed:
        index = int(row["source_face_index"])
        if int(row["surface_before"]) not in WALKABLE_IDS:
            raise ValueError(f"{room}.wok face {index} is no longer a walkable source face.")
        if float(row["slope_degrees"]) < float(min_slope_degrees):
            raise ValueError(
                f"{room}.wok face {index} no longer meets the reviewed wall slope gate."
            )
        if float(row["z_span"]) < float(min_z_span):
            raise ValueError(
                f"{room}.wok face {index} no longer meets the reviewed wall height gate."
            )
        if int(row["boundary_edge_count"]) < 1:
            raise ValueError(f"{room}.wok face {index} is no longer a boundary wall-strip face.")
        if int(row["transition_edge_count"]) != 0:
            raise ValueError(f"{room}.wok face {index} now owns a transition edge and cannot be removed.")
        if not any(int(neighbour) in selected_set for neighbour in row["adjacencies"]):
            raise ValueError(f"{room}.wok face {index} is no longer paired with the reviewed wall strip.")

    before_transition_semantics = _transition_semantics(
        source,
        excluded_face_indices=selected_set,
    )
    retained_faces = [face for index, face in enumerate(source.faces) if index not in selected_set]
    source.faces = retained_faces
    source.adjacency_domain_count = adjacency_domain_before - len(selected)
    candidate = source.to_bytes()
    reopened = WOKData.from_bytes(candidate)
    after_transition_semantics = _transition_semantics(reopened)
    if before_transition_semantics != after_transition_semantics:
        raise ValueError(f"{room}.wok transition semantics changed while removing reviewed walls.")

    expected_topology = [
        (
            int(face.v1),
            int(face.v2),
            int(face.v3),
            int(face.surface),
            int(face.trans1),
            int(face.trans2),
            int(face.trans3),
        )
        for face in retained_faces
    ]
    reopened_topology = [
        (
            int(face.v1),
            int(face.v2),
            int(face.v3),
            int(face.surface),
            int(face.trans1),
            int(face.trans2),
            int(face.trans3),
        )
        for face in reopened.faces
    ]
    if expected_topology != reopened_topology or source.verts != reopened.verts:
        raise ValueError(f"{room}.wok retained indexed topology changed during wall removal.")

    fingerprint, validation = inspect_raw_wok_structure(room, candidate)
    validation_rows = [
        {
            "severity": str(getattr(issue.severity, "value", issue.severity)).lower(),
            "code": str(issue.code),
            "message": str(issue.message),
        }
        for issue in tuple(getattr(validation, "issues", ()) or ())
    ]
    blocking = [
        row for row in validation_rows if row["severity"] in {"error", "blocking"}
    ]
    if blocking:
        raise ValueError(f"{room}.wok reviewed wall removal failed raw engine validation: {blocking}")
    if (
        int(fingerprint.aabb_missing_face_count) != 0
        or int(fingerprint.aabb_covered_face_count) != len(reopened.faces)
        or int(fingerprint.closed_perimeter_count) != int(fingerprint.perimeter_count)
    ):
        raise ValueError(f"{room}.wok reviewed wall removal left incomplete AABB/perimeter data.")

    ambiguous = _preserved_steep_face_rows(reopened)

    return candidate, {
        "room": room,
        "repair": "reviewed_vertical_wall_faces_removed_from_floor_wok",
        "policy_scope": "canonical_koq200_only",
        "source_sha256": _sha256_bytes(data),
        "candidate_sha256": _sha256_bytes(candidate),
        "review_thresholds": {
            "minimum_slope_degrees": float(min_slope_degrees),
            "minimum_z_span": float(min_z_span),
            "requires_boundary_edge": True,
            "requires_reviewed_pair": True,
            "requires_no_transition_edges": True,
            "note": "Thresholds are guards on explicit reviewed indices, not an automatic classifier.",
        },
        "before": {
            "vertex_count": len(source.verts),
            "face_count": len(reopened.faces) + len(selected),
            "adjacency_domain_count": adjacency_domain_before,
            "transition_record_count": len(before_transition_semantics),
        },
        "after": {
            "vertex_count": len(reopened.verts),
            "face_count": len(reopened.faces),
            "adjacency_domain_count": int(reopened.adjacency_domain_count or 0),
            "transition_record_count": len(after_transition_semantics),
            "engine_fingerprint": asdict(fingerprint),
            "validation": validation_rows,
        },
        "removed_faces": removed,
        "removed_face_count": len(removed),
        "ambiguous_steep_faces_preserved": ambiguous,
        "ambiguous_steep_face_count": len(ambiguous),
        "retained_face_order_preserved": True,
        "retained_vertex_indices_preserved": True,
        "transition_semantics_preserved": True,
    }


def _apply_koq200_floor_wok_repair(
    data: bytes,
    *,
    module: str,
    room: str,
) -> tuple[bytes, dict[str, Any] | None]:
    """Apply only canonical KOQ200's explicit reviewed wall removals."""

    if str(module).casefold() != "koq200":
        return data, None
    indices = KOQ200_REVIEWED_WALL_FACE_INDICES.get(str(room).casefold())
    if indices:
        repaired, report = _remove_reviewed_floor_wall_faces(
            data,
            room=str(room).casefold(),
            face_indices=indices,
        )
        return repaired, report

    source = WOKData.from_bytes(data)
    ambiguous = _preserved_steep_face_rows(source)
    transition_count = len(_transition_semantics(source))
    return data, {
        "room": str(room).casefold(),
        "repair": "steep_walkable_faces_reviewed_no_automatic_change",
        "policy_scope": "canonical_koq200_only",
        "source_sha256": _sha256_bytes(data),
        "candidate_sha256": _sha256_bytes(data),
        "before": {
            "vertex_count": len(source.verts),
            "face_count": len(source.faces),
            "adjacency_domain_count": int(source.adjacency_domain_count or 0),
            "transition_record_count": transition_count,
        },
        "after": {
            "vertex_count": len(source.verts),
            "face_count": len(source.faces),
            "adjacency_domain_count": int(source.adjacency_domain_count or 0),
            "transition_record_count": transition_count,
        },
        "removed_faces": [],
        "removed_face_count": 0,
        "ambiguous_steep_faces_preserved": ambiguous,
        "ambiguous_steep_face_count": len(ambiguous),
        "retained_face_order_preserved": True,
        "retained_vertex_indices_preserved": True,
        "transition_semantics_preserved": True,
    }


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _authoritative_wok_bytes(
    *,
    room: str,
    plan: dict[str, Any],
    source_resources: dict[tuple[str, str], bytes],
) -> tuple[bytes, dict[str, Any]]:
    """Resolve one room WOK through a hash-pinned canonical override.

    A canonical repair may replace a proven-bad recovered resource, but it may
    not silently consume whichever similarly named file happens to exist.  The
    override and its expected SHA-256 are therefore one fail-closed contract.
    """

    room = str(room).strip().casefold()
    overrides = {
        str(key).strip().casefold(): Path(value)
        for key, value in dict(plan.get("authoritative_wok_overrides", {}) or {}).items()
    }
    expected_hashes = {
        str(key).strip().casefold(): str(value).strip().casefold()
        for key, value in dict(plan.get("authoritative_wok_hashes", {}) or {}).items()
    }
    override = overrides.get(room)
    if override is None:
        data = source_resources.get((room, "wok"))
        if data is None:
            raise FileNotFoundError(f"Playable room {room} has no source WOK.")
        source = "recovered source MOD"
        source_path: str | None = None
    else:
        override = override.expanduser().resolve()
        if not override.is_file():
            raise FileNotFoundError(f"Canonical WOK override does not exist: {override}")
        data = override.read_bytes()
        source = "hash-pinned canonical WOK override"
        source_path = str(override)

    actual_hash = _sha256_bytes(data)
    expected_hash = expected_hashes.get(room)
    if override is not None and not expected_hash:
        raise ValueError(f"Canonical WOK override {room} has no expected SHA-256 contract.")
    if expected_hash and actual_hash != expected_hash:
        raise ValueError(
            f"Canonical WOK input drift for {room}: expected {expected_hash}, got {actual_hash}."
        )
    return data, {
        "room": room,
        "source": source,
        "path": source_path,
        "sha256": actual_hash,
        "expected_sha256": expected_hash,
        "override_applied": override is not None,
    }


def _world_wok_triangle_signature(
    wok: WOKData,
    face_index: int,
    position: tuple[float, float, float],
    *,
    decimals: int = 5,
) -> tuple[tuple[float, float, float], ...]:
    face = wok.faces[face_index]
    return tuple(
        sorted(
            tuple(
                round(float(wok.verts[vertex_index][axis]) + float(position[axis]), decimals)
                for axis in range(3)
            )
            for vertex_index in (int(face.v1), int(face.v2), int(face.v3))
        )
    )


def _audit_cross_room_wok_face_duplicates(
    *,
    room_order: tuple[str, ...],
    authoritative_woks: dict[str, bytes],
    room_positions: dict[str, tuple[float, float, float]],
) -> dict[str, Any]:
    """Find exact world-space collision triangles owned by multiple rooms."""

    owner_by_triangle: dict[tuple[tuple[float, float, float], ...], tuple[str, int]] = {}
    duplicates: list[dict[str, Any]] = []
    face_counts: dict[str, int] = {}
    for room in room_order:
        room_key = str(room).strip().casefold()
        data = authoritative_woks.get(room_key)
        if data is None:
            raise ValueError(f"Cross-room WOK audit is missing {room_key}.")
        wok = WOKData.from_bytes(data)
        face_counts[room_key] = len(wok.faces)
        position = tuple(float(value) for value in room_positions.get(room_key, (0.0, 0.0, 0.0)))
        for face_index in range(len(wok.faces)):
            signature = _world_wok_triangle_signature(wok, face_index, position)
            previous = owner_by_triangle.get(signature)
            if previous is None:
                owner_by_triangle[signature] = (room_key, face_index)
                continue
            previous_room, previous_face = previous
            if previous_room == room_key:
                continue
            duplicates.append(
                {
                    "room_a": previous_room,
                    "face_a": previous_face,
                    "room_b": room_key,
                    "face_b": face_index,
                    "triangle": [list(point) for point in signature],
                }
            )
    return {
        "policy": "exact_world_space_triangle_identity_at_0.00001",
        "room_order": [str(room).casefold() for room in room_order],
        "face_counts": face_counts,
        "duplicate_face_count": len(duplicates),
        "duplicates": duplicates,
        "passed": not duplicates,
    }


def _audit_reciprocal_wok_transitions(
    *,
    room_order: tuple[str, ...],
    authoritative_woks: dict[str, bytes],
) -> dict[str, Any]:
    """Audit room-index transition records before PTH generation."""

    rooms = tuple(str(room).strip().casefold() for room in room_order)
    directed: dict[tuple[int, int], int] = {}
    invalid: list[dict[str, Any]] = []
    for source_index, room in enumerate(rooms):
        data = authoritative_woks.get(room)
        if data is None:
            raise ValueError(f"Transition audit is missing {room}.")
        wok = WOKData.from_bytes(data)
        for face_index, face in enumerate(wok.faces):
            for local_edge, target_index in enumerate((face.trans1, face.trans2, face.trans3)):
                target_index = int(target_index)
                if target_index < 0:
                    continue
                if target_index >= len(rooms) or target_index == source_index:
                    invalid.append(
                        {
                            "room": room,
                            "face": face_index,
                            "local_edge": local_edge,
                            "target_index": target_index,
                        }
                    )
                    continue
                key = (source_index, target_index)
                directed[key] = directed.get(key, 0) + 1

    reciprocal: list[dict[str, Any]] = []
    one_way: list[dict[str, Any]] = []
    for source_index, target_index in sorted(directed):
        if source_index < target_index and (target_index, source_index) in directed:
            reciprocal.append(
                {
                    "room_a": rooms[source_index],
                    "room_b": rooms[target_index],
                    "a_to_b_edge_count": directed[(source_index, target_index)],
                    "b_to_a_edge_count": directed[(target_index, source_index)],
                }
            )
        elif (target_index, source_index) not in directed:
            one_way.append(
                {
                    "source": rooms[source_index],
                    "target": rooms[target_index],
                    "edge_count": directed[(source_index, target_index)],
                }
            )
    return {
        "room_order": list(rooms),
        "directed_transition_edge_count": sum(directed.values()),
        "reciprocal_transition_pair_count": len(reciprocal),
        "reciprocal_transition_pairs": reciprocal,
        "one_way_transition_count": len(one_way),
        "one_way_transitions": one_way,
        "invalid_transition_count": len(invalid),
        "invalid_transitions": invalid,
    }


def _assert_candidate_proof_gates(build: Any, proofs: dict[str, Any]) -> dict[str, Any]:
    """Fail when serialization/readback or Map Studio parity is incomplete."""

    build_data = build.to_dict() if hasattr(build, "to_dict") else dict(build)
    engine_ready = bool(dict(build_data.get("engine_contract", {}) or {}).get("export_ready"))
    readback_ready = bool(dict(build_data.get("readback_contract", {}) or {}).get("export_ready"))
    roundtrip = dict(proofs.get("map_studio_roundtrip", {}) or {})
    mod_audit = dict(proofs.get("mod_walkmesh_audit", {}) or {})
    kmap_audit = dict(proofs.get("kmap_walkmesh_audit", {}) or {})
    parity = dict(proofs.get("walkmesh_parity", {}) or {})
    checks = {
        "build_ok": bool(build_data.get("ok")),
        "engine_contract_export_ready": engine_ready,
        "packaged_readback_export_ready": readback_ready,
        "map_studio_roundtrip_ok": bool(roundtrip.get("ok")),
        "mod_walkmesh_audit_pass": bool(mod_audit.get("audit_pass")),
        "kmap_walkmesh_audit_pass": bool(kmap_audit.get("audit_pass")),
        "mod_kmap_walkmesh_parity": bool(parity.get("all_match")),
        "reopened_room_count_matches": int(roundtrip.get("reopened_room_count", -1))
        == int(roundtrip.get("room_count", -2)),
        "reopened_wok_parity_complete": int(roundtrip.get("wok_parity_match_count", -1))
        == int(roundtrip.get("wok_parity_room_count", -2)),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Candidate proof gates failed: " + ", ".join(failed))
    return {"checks": checks, "passed": True, "retail_game_tested": False}


def _capsule_resources(path: Path) -> dict[tuple[str, str], bytes]:
    resources: dict[tuple[str, str], bytes] = {}
    for resource in Capsule(path):
        key = (str(resource.resname()).strip().lower(), resource.restype().extension.lower())
        resources[key] = bytes(resource.data())
    return resources


def _directory_resources(path: Path) -> dict[tuple[str, str], bytes]:
    """Load one flat, staged resource directory without consulting the game."""

    if not path.is_dir():
        raise FileNotFoundError(f"Audited resource directory does not exist: {path}")
    resources: dict[tuple[str, str], bytes] = {}
    for resource_path in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
        if not resource_path.is_file() or not resource_path.suffix:
            continue
        key = (resource_path.stem.strip().casefold(), resource_path.suffix[1:].strip().casefold())
        if key in resources:
            raise ValueError(f"Duplicate staged resource identity: {key[0]}.{key[1]}")
        resources[key] = resource_path.read_bytes()
    return resources


def _validation_issue_rows(report: Any) -> list[dict[str, Any]]:
    return [
        {
            "severity": str(getattr(issue.severity, "value", issue.severity)).lower(),
            "code": str(issue.code),
            "message": str(issue.message),
        }
        for issue in tuple(getattr(report, "issues", ()) or ())
    ]


def _stage_audited_room_triplet(
    *,
    room: str,
    resources: dict[tuple[str, str], bytes],
    expected_hashes: dict[str, str],
    source_resources_dir: Path,
    source_rooms_dir: Path,
    wok_dir: Path,
    room_dir: Path,
) -> dict[str, Any]:
    """Stage an already-audited K2 room byte-for-byte and recheck raw gates."""

    from src.core.validation.kotor_module_engine_contract import (
        inspect_raw_mdl_structure,
        inspect_raw_wok_structure,
    )

    triplet: dict[str, bytes] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    for extension in ("mdl", "mdx", "wok"):
        data = resources.get((room, extension))
        if data is None:
            raise FileNotFoundError(
                f"Audited KOQ200 resource directory is missing {room}.{extension}: "
                f"{source_resources_dir}"
            )
        expected = str(expected_hashes.get(extension, "")).casefold()
        actual = _sha256_bytes(data)
        if not expected or actual != expected:
            raise ValueError(
                f"Audited KOQ200 input drift for {room}.{extension}: expected {expected or '<unset>'}, "
                f"got {actual}."
            )
        triplet[extension] = data

    mdl_fingerprint, mdl_report = inspect_raw_mdl_structure(
        room,
        triplet["mdl"],
        triplet["mdx"],
        game="K2",
    )
    wok_fingerprint, wok_report = inspect_raw_wok_structure(room, triplet["wok"])
    mdl_issues = _validation_issue_rows(mdl_report)
    wok_issues = _validation_issue_rows(wok_report)
    blocking = [
        row
        for row in mdl_issues + wok_issues
        if row["severity"] in {"error", "blocking"}
    ]
    if blocking:
        raise ValueError(f"Audited KOQ200 room {room} no longer passes raw engine gates: {blocking}")

    parsed = MDLBinaryParser(triplet["mdl"], triplet["mdx"]).parse()
    if parsed is None:
        raise ValueError(f"Ghost Studio could not parse audited room {room} after raw validation.")
    nodes = tuple(parsed.all_nodes())
    controller_count = sum(len(getattr(node, "controllers", ()) or ()) for node in nodes)
    emitter_nodes = [node for node in nodes if int(getattr(node, "flags", 0)) & int(NodeFlags.EMITTER)]
    light_nodes = [node for node in nodes if int(getattr(node, "flags", 0)) & int(NodeFlags.LIGHT)]

    for extension, destination_dir in (
        ("mdl", source_rooms_dir),
        ("mdx", source_rooms_dir),
        ("mdl", room_dir),
        ("mdx", room_dir),
        ("wok", wok_dir),
        ("wok", room_dir),
    ):
        destination = destination_dir / f"{room}.{extension}"
        destination.write_bytes(triplet[extension])
        artifacts[f"{destination_dir.name}/{extension}"] = _artifact(destination)

    return {
        "room": room,
        "route": "audited_complete_mdlops_k2_triplet_passthrough",
        "source_resource_dir": str(source_resources_dir),
        "byte_exact_input_hashes": dict(expected_hashes),
        "raw_mdl_fingerprint": asdict(mdl_fingerprint),
        "raw_wok_fingerprint": asdict(wok_fingerprint),
        "raw_mdl_issues": mdl_issues,
        "raw_wok_issues": wok_issues,
        "node_count": len(nodes),
        "controller_count": controller_count,
        "emitter_node_count": len(emitter_nodes),
        "emitter_controller_count": sum(
            len(getattr(node, "controllers", ()) or ()) for node in emitter_nodes
        ),
        "light_node_count": len(light_nodes),
        "light_controller_count": sum(
            len(getattr(node, "controllers", ()) or ()) for node in light_nodes
        ),
        "writer_reentry": False,
        "writer_reentry_reason": (
            "The triplet is already the audited K2 writer/MDLOps output; another serialization would "
            "replace byte evidence without adding an engine guarantee."
        ),
        "artifacts": artifacts,
    }


def _overlay_audited_candidate_resources(
    source_resources: dict[tuple[str, str], bytes],
    audited_resources: dict[tuple[str, str], bytes],
    *,
    area_resref: str,
) -> tuple[dict[tuple[str, str], bytes], list[dict[str, Any]], dict[str, str]]:
    """Overlay audited metadata and textures while retaining RNV-only assets."""

    core_keys = {
        (area_resref.casefold(), "are"),
        (area_resref.casefold(), "git"),
        ("module", "ifo"),
    }
    missing_core = [f"{name}.{extension}" for name, extension in sorted(core_keys - audited_resources.keys())]
    if missing_core:
        raise FileNotFoundError(
            "Audited KOQ200 resource directory is missing core metadata: " + ", ".join(missing_core)
        )

    merged = dict(source_resources)
    rows: list[dict[str, Any]] = []
    candidate_texture_names: set[str] = set()
    for key, data in sorted(audited_resources.items()):
        resref, extension = key
        if key not in core_keys and extension not in {"tga", "tpc", "txi"}:
            continue
        before = merged.get(key)
        merged[key] = data
        if extension in {"tga", "tpc"}:
            candidate_texture_names.add(resref)
        rows.append(
            {
                "resource": f"{resref}.{extension}",
                "role": "core_metadata" if key in core_keys else "texture_dependency",
                "action": "added" if before is None else ("preserved" if before == data else "replaced"),
                "source_sha256": _sha256_bytes(data),
                "replaced_sha256": _sha256_bytes(before) if before is not None and before != data else None,
                "source": "audited complete KOQ200 candidate resource directory",
            }
        )

    bundled_provenance = {
        resref: (
            "audited complete KOQ200 candidate resource directory"
            if resref in candidate_texture_names
            else "recovered RNV source MOD"
        )
        for resref, extension in merged
        if extension in {"tga", "tpc"}
    }
    return merged, rows, bundled_provenance


def _layout_positions(data: bytes) -> dict[str, tuple[float, float, float]]:
    layout = LYTLayout.from_text(data.decode("latin-1", errors="replace"))
    return {
        str(room.model).strip().casefold(): (float(room.x), float(room.y), float(room.z))
        for room in layout.rooms
    }


def _write_evidence_backed_zero_layout(
    *,
    destination: Path,
    room_order: tuple[str, ...],
    playable_rooms: tuple[str, ...],
    visual_only_rooms: tuple[str, ...],
    audited_lyt: bytes,
    rnv_source_lyt: bytes,
    audited_lyt_source: Path,
    rnv_lyt_source: Path,
) -> dict[str, Any]:
    """Build the canonical hybrid LYT only after both zero-origin claims pass."""

    audited_positions = _layout_positions(audited_lyt)
    rnv_positions = _layout_positions(rnv_source_lyt)
    evidence: list[dict[str, Any]] = []
    for room in playable_rooms:
        position = audited_positions.get(room.casefold())
        if position is None:
            raise ValueError(f"Audited KOQ200 LYT does not contain required room {room}.")
        if any(abs(value) > 1.0e-9 for value in position):
            raise ValueError(f"Audited KOQ200 LYT places {room} at non-zero position {position}.")
        evidence.append({"room": room, "position": list(position), "source": str(audited_lyt_source)})
    for room in visual_only_rooms:
        position = rnv_positions.get(room.casefold())
        if position is None:
            raise ValueError(f"Recovered RNV LYT does not contain visual-only room {room}.")
        if any(abs(value) > 1.0e-9 for value in position):
            raise ValueError(f"Recovered RNV LYT places {room} at non-zero position {position}.")
        evidence.append({"room": room, "position": list(position), "source": str(rnv_lyt_source)})

    expected_order = tuple(room.casefold() for room in playable_rooms + visual_only_rooms)
    if tuple(room.casefold() for room in room_order) != expected_order:
        raise ValueError(
            "Canonical KOQ200 room order must be playable a..h followed by koq200_02 and valsky."
        )
    layout = LYTLayout(rooms=[LYTRoom(room, 0.0, 0.0, 0.0) for room in room_order])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(layout.to_text().encode("latin-1"))
    reopened = LYTLayout.from_text(destination.read_text(encoding="latin-1"))
    reopened_order = tuple(str(room.model).strip().casefold() for room in reopened.rooms)
    if reopened_order != tuple(room.casefold() for room in room_order):
        raise ValueError("Combined KOQ200 LYT changed room ordering during write/readback.")
    if any(abs(value) > 1.0e-9 for room in reopened.rooms for value in (room.x, room.y, room.z)):
        raise ValueError("Combined KOQ200 LYT did not round-trip with zero room origins.")
    return {
        "output": _artifact(destination),
        "policy": "evidence_backed_zero_origins_a_to_h_then_visual_partitions",
        "room_order": list(room_order),
        "positions": {room: [0.0, 0.0, 0.0] for room in room_order},
        "evidence": evidence,
        "audited_lyt_sha256": _sha256_bytes(audited_lyt),
        "rnv_source_lyt_sha256": _sha256_bytes(rnv_source_lyt),
    }


def _audit_module_scripts(
    resources: dict[tuple[str, str], bytes],
    manager: ResourceManager,
    *,
    target_game: str,
) -> dict[str, Any]:
    """Report preserved module-event scripts without hiding external gaps."""

    from pykotor.resource.formats.gff import read_gff

    ifo = resources.get(("module", "ifo"))
    if ifo is None:
        return {"ifo_present": False, "references": [], "unresolved": [], "unresolved_count": 0}
    root = read_gff(ifo).root
    install = manager.get_k2() if target_game.upper() == "K2" else manager.get_k1()
    rows: list[dict[str, Any]] = []
    for field_name in sorted(str(name) for name in root.keys() if str(name).startswith("Mod_On")):
        resref = str(root.get(field_name) or "").strip().casefold()
        if not resref:
            continue
        bundled = (resref, "ncs") in resources
        clean_base = bool(install is not None and install.get_bif(resref, RES_NCS) is not None)
        rows.append(
            {
                "field": field_name,
                "resref": resref,
                "bundled_ncs": bundled,
                "clean_target_game_key_bif": clean_base,
                "status": "bundled" if bundled else ("clean_target_game" if clean_base else "unresolved_external"),
                "preserved_in_ifo": True,
            }
        )
    unresolved = [row for row in rows if row["status"] == "unresolved_external"]
    return {
        "ifo_present": True,
        "ifo_sha256": _sha256_bytes(ifo),
        "references": rows,
        "unresolved": unresolved,
        "unresolved_count": len(unresolved),
        "policy": "preserve_and_report; do_not_silently_clear_or_fabricate",
        "target_game_lookup": f"clean {target_game.upper()} KEY/BIF only",
    }


def _neutralize_unresolved_module_scripts(
    resources: dict[tuple[str, str], bytes],
    audit: dict[str, Any],
) -> tuple[dict[tuple[str, str], bytes], dict[str, Any]]:
    """Clear only module hooks proven unresolved for the target build.

    This is deliberately driven by the clean target-game script audit.  It
    does not bundle donor scripts from another module and does not touch hooks
    that resolve from the candidate or clean KEY/BIF libraries.
    """

    unresolved = list(audit.get("unresolved", ()) or ())
    if not unresolved:
        return dict(resources), {
            "applied": False,
            "cleared_hooks": [],
            "reason": "No unresolved module event hooks were present.",
        }
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    ifo = resources.get(("module", "ifo"))
    if ifo is None:
        raise ValueError("Cannot neutralize unresolved module hooks without module.ifo.")
    gff = read_gff(ifo)
    cleared: list[dict[str, Any]] = []
    for row in unresolved:
        field = str(row.get("field") or "").strip()
        resref = str(row.get("resref") or "").strip().casefold()
        if not field or not resref:
            raise ValueError(f"Malformed unresolved module-script audit row: {row!r}")
        current = str(gff.root.get(field) or "").strip().casefold()
        if current != resref:
            raise ValueError(
                f"module.ifo {field} changed after script audit: expected {resref}, found {current or '(empty)'}."
            )
        gff.root.set_resref(field, "")
        cleared.append({"field": field, "resref": resref, "action": "cleared_unresolved_hook"})
    output = dict(resources)
    output[("module", "ifo")] = bytes_gff(gff)
    return output, {
        "applied": True,
        "source_ifo_sha256": _sha256_bytes(ifo),
        "candidate_ifo_sha256": _sha256_bytes(output[("module", "ifo")]),
        "cleared_hooks": cleared,
        "reason": (
            "The hooks do not resolve from the candidate or clean target-game KEY/BIF. "
            "Donor module-local NCS resources are not safe to transplant."
        ),
    }


def _verify_audited_room_output_hashes(
    resources_dir: Path,
    expected: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Prove the final MOD staging directory kept all audited triplet bytes."""

    rows: list[dict[str, Any]] = []
    for room, hashes in expected.items():
        for extension, expected_hash in hashes.items():
            path = resources_dir / f"{room}.{extension}"
            if not path.is_file():
                raise FileNotFoundError(f"Final hybrid output is missing audited resource {path.name}.")
            actual_hash = _sha256_bytes(path.read_bytes())
            if actual_hash != expected_hash:
                raise ValueError(
                    f"Final hybrid output changed {path.name}: expected {expected_hash}, got {actual_hash}."
                )
            rows.append(
                {
                    "resource": path.name,
                    "sha256": actual_hash,
                    "byte_exact": True,
                    "output": _artifact(path),
                }
            )
    return rows


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
    bundled: set[str] | dict[str, str],
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
    non_rendering_only: list[dict[str, Any]] = []
    extra_resource_paths: list[str] = []
    for texture in sorted(referenced):
        if texture in bundled:
            source = (
                str(bundled.get(texture) or "bundled in source MOD")
                if isinstance(bundled, dict)
                else "bundled in source MOD"
            )
            resolved.append({"texture": texture, "source": source})
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
        reference_rows = referenced[texture]
        visible_references = [
            row for row in reference_rows if bool(row.get("render")) and int(row.get("faces", 0) or 0) > 0
        ]
        row = {
            "texture": texture,
            "referencing_nodes": reference_rows[:6],
        }
        if visible_references:
            row["note"] = (
                "Absent from the recovered bundle, KOTOR 2, and KOTOR 1; the visible surface renders "
                "untextured. Reported honestly, not fabricated."
            )
            missing.append(row)
        else:
            row["note"] = (
                "Referenced only by non-rendering MDL nodes (for KOQ200, the embedded AABB walkmesh). "
                "No deployable texture is required; the byte-exact model label is preserved."
            )
            non_rendering_only.append(row)
    return {
        "resolved": resolved,
        "ported_from_k1": ported,
        "missing": missing,
        "non_rendering_only": non_rendering_only,
        "extra_resource_paths": extra_resource_paths,
    }


def _build_module(module: str, output_root: Path, manager: ResourceManager) -> dict[str, Any]:
    source_module, plan = _resolve_module_plan(module)
    source_mod = Path(plan["source_mod"])
    if not source_mod.is_file():
        raise FileNotFoundError(f"{module} source MOD does not exist: {source_mod}")
    source_resources = _capsule_resources(source_mod)
    playable_rooms: tuple[str, ...] = plan["playable_rooms"]
    visual_only_rooms: tuple[str, ...] = plan["visual_only_rooms"]
    retained_rooms = tuple(plan.get("combined_room_order", playable_rooms + visual_only_rooms))
    if retained_rooms != playable_rooms + visual_only_rooms:
        raise ValueError(
            f"{module} combined room order must list all playable rooms first, then visual-only rooms."
        )
    area = plan["area_resref"]

    audited_resources_dir_text = str(plan.get("audited_candidate_resources_dir", "") or "").strip()
    audited_resources_dir = Path(audited_resources_dir_text) if audited_resources_dir_text else None
    audited_resources: dict[tuple[str, str], bytes] = {}
    audited_resource_overlay: list[dict[str, Any]] = []
    if audited_resources_dir is not None:
        audited_resources = _directory_resources(audited_resources_dir)
        module_resources, audited_resource_overlay, bundled_provenance = (
            _overlay_audited_candidate_resources(
                source_resources,
                audited_resources,
                area_resref=area,
            )
        )
    else:
        module_resources = dict(source_resources)
        bundled_provenance = {
            name: "recovered source MOD"
            for name, extension in module_resources
            if extension in {"tga", "tpc"}
        }

    destination = output_root / module / "K2" / "HonestCandidate"
    source_rooms_dir = destination / "SourceRooms"
    wok_dir = destination / "CoreInputs" / "AuthoritativeWoks"
    room_dir = destination / "Rooms"
    core_dir = destination / "CoreInputs"
    port_dir = destination / "Resources" / "K1StockPorts"
    for directory in (source_rooms_dir, wok_dir, room_dir, core_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # 1. Extract only the RNV rooms that still need the repaired writer.  The
    # canonical KOQ200 playable rooms are staged byte-for-byte below.
    source_compile_rooms = (
        visual_only_rooms
        if bool(plan.get("preserve_audited_room_bytes"))
        else retained_rooms
    )
    for room in source_compile_rooms:
        for extension in ("mdl", "mdx"):
            data = source_resources.get((room, extension))
            if data is None:
                raise FileNotFoundError(f"{module} source is missing {room}.{extension}")
            (source_rooms_dir / f"{room}.{extension}").write_bytes(data)

    # 2. Authoritative WOKs.  Canonical KOQ200 consumes the exact audited
    # triplets; provenance-named RNV builds retain their existing repair path.
    wok_repairs: list[dict[str, Any]] = []
    wok_floor_reviews: list[dict[str, Any]] = []
    authoritative_wok_inputs: list[dict[str, Any]] = []
    authoritative_woks: dict[str, bytes] = {}
    room_compiles: list[dict[str, Any]] = []
    if bool(plan.get("preserve_audited_room_bytes")):
        if audited_resources_dir is None:
            raise ValueError(f"{module} requests audited room passthrough without a resource directory.")
        expected_room_hashes = dict(plan.get("audited_room_hashes", {}))
        for room in playable_rooms:
            expected = expected_room_hashes.get(room)
            if expected is None:
                raise ValueError(f"{module} has no audited hash contract for {room}.")
            room_compiles.append(
                _stage_audited_room_triplet(
                    room=room,
                    resources=audited_resources,
                    expected_hashes=expected,
                    source_resources_dir=audited_resources_dir,
                    source_rooms_dir=source_rooms_dir,
                    wok_dir=wok_dir,
                    room_dir=room_dir,
                )
            )
            data = audited_resources[(room, "wok")]
            authoritative_woks[room] = data
            authoritative_wok_inputs.append(
                {
                    "room": room,
                    "source": "byte-audited complete candidate resource directory",
                    "path": str(audited_resources_dir / f"{room}.wok"),
                    "sha256": _sha256_bytes(data),
                    "expected_sha256": str(expected["wok"]),
                    "override_applied": True,
                    "candidate_sha256": _sha256_bytes(data),
                    "derived_table_repair_applied": False,
                }
            )
            parsed_wok = WOKData.from_bytes(data)
            ambiguous = _preserved_steep_face_rows(parsed_wok)
            wok_floor_reviews.append(
                {
                    "room": room,
                    "repair": "audited_complete_wok_preserved_byte_exact",
                    "policy_scope": "canonical_koq200_hybrid",
                    "source_sha256": _sha256_bytes(data),
                    "candidate_sha256": _sha256_bytes(data),
                    "removed_faces": [],
                    "removed_face_count": 0,
                    "ambiguous_steep_faces_preserved": ambiguous,
                    "ambiguous_steep_face_count": len(ambiguous),
                    "retained_face_order_preserved": True,
                    "retained_vertex_indices_preserved": True,
                    "transition_semantics_preserved": True,
                    "reason": (
                        "This is the byte-audited K2 WOK. The hybrid builder does not apply slope-only "
                        "or source-index wall edits to an already validated triplet."
                    ),
                }
            )
    else:
        for room in playable_rooms:
            data, input_evidence = _authoritative_wok_bytes(
                room=room,
                plan=plan,
                source_resources=source_resources,
            )
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
                input_evidence["derived_table_repair_applied"] = True
            else:
                input_evidence["derived_table_repair_applied"] = False
            data, reviewed_wall_repair = _apply_koq200_floor_wok_repair(
                data,
                module=module,
                room=room,
            )
            if reviewed_wall_repair is not None:
                wok_floor_reviews.append(reviewed_wall_repair)
                if int(reviewed_wall_repair.get("removed_face_count", 0)):
                    wok_repairs.append(reviewed_wall_repair)
            input_evidence["candidate_sha256"] = _sha256_bytes(data)
            authoritative_wok_inputs.append(input_evidence)
            authoritative_woks[room] = data
            (wok_dir / f"{room}.wok").write_bytes(data)

    # 3. Compile source-backed rooms through the repaired writer.  Its parity
    # report is the controller/emitter/light preservation gate for 02/valsky.
    for room in source_compile_rooms:
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

    # 4. Evidence-backed combined LYT and symmetric VIS.
    source_lyt_path = core_dir / f"{area}.source.lyt"
    source_lyt_bytes = source_resources[(area, "lyt")]
    source_lyt_path.write_bytes(source_lyt_bytes)
    lyt_path = core_dir / f"{module}.lyt"
    if audited_resources_dir is not None:
        audited_lyt = audited_resources.get((area, "lyt"))
        if audited_lyt is None:
            raise FileNotFoundError(f"Audited resource directory is missing {area}.lyt.")
        lyt = _write_evidence_backed_zero_layout(
            destination=lyt_path,
            room_order=retained_rooms,
            playable_rooms=playable_rooms,
            visual_only_rooms=visual_only_rooms,
            audited_lyt=audited_lyt,
            rnv_source_lyt=source_lyt_bytes,
            audited_lyt_source=audited_resources_dir / f"{area}.lyt",
            rnv_lyt_source=source_mod,
        )
        source_transition_rooms = tuple(plan["source_transition_room_resrefs"])
    else:
        source_transition_rooms = tuple(_parse_lyt_rooms(source_lyt_path))
        lyt = _filtered_lyt(source_lyt_path, retained_rooms, lyt_path)

    room_positions = _layout_positions(lyt_path.read_bytes())
    cross_room_wok_audit = _audit_cross_room_wok_face_duplicates(
        room_order=playable_rooms,
        authoritative_woks=authoritative_woks,
        room_positions=room_positions,
    )
    if bool(plan.get("reject_cross_room_wok_face_duplicates")) and not bool(
        cross_room_wok_audit["passed"]
    ):
        raise ValueError(
            f"{module} duplicates {cross_room_wok_audit['duplicate_face_count']} exact "
            "world-space collision triangle(s) across room WOKs."
        )

    expected_transition_pairs = plan.get("expected_reciprocal_transition_pair_count")
    missing_transition_audit_rooms = [
        room for room in source_transition_rooms if room.casefold() not in authoritative_woks
    ]
    if missing_transition_audit_rooms and expected_transition_pairs is not None:
        raise ValueError(
            f"{module} cannot prove reciprocal WOK transitions; missing authoritative WOKs for: "
            + ", ".join(missing_transition_audit_rooms)
        )
    if missing_transition_audit_rooms:
        source_transition_audit = {
            "skipped": True,
            "reason": "The provenance build retains LYT-only rooms without surviving WOKs.",
            "missing_rooms": missing_transition_audit_rooms,
        }
    else:
        source_transition_audit = _audit_reciprocal_wok_transitions(
            room_order=source_transition_rooms,
            authoritative_woks=authoritative_woks,
        )
    if expected_transition_pairs is not None:
        actual_transition_pairs = int(source_transition_audit["reciprocal_transition_pair_count"])
        if actual_transition_pairs != int(expected_transition_pairs):
            raise ValueError(
                f"{module} expected {expected_transition_pairs} reciprocal WOK transition pair(s), "
                f"found {actual_transition_pairs}."
            )
        if int(source_transition_audit["one_way_transition_count"]):
            raise ValueError(f"{module} has one-way WOK transition records.")
        if int(source_transition_audit["invalid_transition_count"]):
            raise ValueError(f"{module} has invalid WOK transition target indices.")
    vis = VISData()
    lowered_rooms = tuple(room.casefold() for room in retained_rooms)
    vis.visibility = {
        room: [target for target in lowered_rooms if target != room] for room in lowered_rooms
    }
    vis_path = core_dir / f"{module}.vis"
    vis_path.write_bytes(vis.to_text().encode("latin-1"))

    # 5. Texture dependencies: the audited KOQ200 directory wins over older
    # RNV duplicates; remaining source/stock dependencies stay explicit.
    referenced = _referenced_textures(room_dir, retained_rooms)
    textures = _resolve_textures(
        referenced,
        bundled_provenance,
        manager,
        port_dir,
        recovered_texture_dirs=tuple(plan.get("recovered_texture_dirs", ())),
    )

    # 6. Filtered source MOD plus explicit inherited-script evidence.
    entry_policy = _entry_point_on_combined_walkmesh(
        module_resources,
        playable_rooms,
        authoritative_woks,
    )
    filtered_resources = dict(module_resources)
    if not entry_policy["keep_source_ifo"]:
        if bool(plan.get("keep_unresolved_module_scripts_explicit")):
            raise ValueError(
                f"{module} audited IFO entry is no longer on the combined walkmesh; refusing "
                "to silently replace it and erase inherited module-script evidence."
            )
        filtered_resources.pop(("module", "ifo"), None)
    source_script_audit = _audit_module_scripts(filtered_resources, manager, target_game="K2")
    script_neutralization: dict[str, Any] = {
        "applied": False,
        "cleared_hooks": [],
        "reason": "The module plan preserves source event hooks.",
    }
    if bool(plan.get("neutralize_unresolved_module_scripts")):
        filtered_resources, script_neutralization = _neutralize_unresolved_module_scripts(
            filtered_resources,
            source_script_audit,
        )
    script_audit = _audit_module_scripts(filtered_resources, manager, target_game="K2")
    if bool(plan.get("neutralize_unresolved_module_scripts")) and script_audit.get("unresolved_count"):
        raise ValueError(f"{module} still has unresolved module event hooks after neutralization.")
    script_audit_path = destination / f"{module}.k2.module-script-audit.json"
    script_audit_path.write_text(
        json.dumps(script_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
            source_lyt=str(lyt_path),
            source_vis=str(vis_path),
            extra_resource_paths=tuple(textures["extra_resource_paths"]),
            visual_only_room_resrefs=visual_only_rooms,
            regenerate_pth=True,
            wok_coordinate_space="module",
            source_transition_room_resrefs=source_transition_rooms,
            regenerate_module_id=True,
            overwrite=True,
        )
    )
    proofs: dict[str, Any] = {"ready_for_manual_k2_test": False}
    if build.ok:
        proofs = _candidate_proofs(module=module, candidate_root=destination)

    module_path = destination / "Modules" / f"{module}.mod"
    kmap_path = destination / "MapStudioProof" / f"{module}.kmap"
    audited_output_hashes: list[dict[str, Any]] = []
    output_script_audit: dict[str, Any] = {}
    if build.ok and bool(plan.get("preserve_audited_room_bytes")):
        audited_output_hashes = _verify_audited_room_output_hashes(
            destination / "Resources",
            dict(plan["audited_room_hashes"]),
        )
    if build.ok and module_path.is_file():
        output_script_audit = _audit_module_scripts(
            _capsule_resources(module_path),
            manager,
            target_game="K2",
        )
        if output_script_audit.get("references") != script_audit.get("references"):
            raise ValueError(f"Final {module} MOD changed inherited IFO module-script references.")
        if bool(plan.get("neutralize_unresolved_module_scripts")) and int(
            output_script_audit.get("unresolved_count", 0) or 0
        ):
            raise ValueError(f"Final {module} MOD still contains unresolved module event hooks.")

    candidate_proof_gates: dict[str, Any] = {
        "passed": not bool(plan.get("require_engine_readback_and_kmap_parity")),
        "skipped": not bool(plan.get("require_engine_readback_and_kmap_parity")),
        "retail_game_tested": False,
    }
    if bool(plan.get("require_engine_readback_and_kmap_parity")):
        candidate_proof_gates = _assert_candidate_proof_gates(build, proofs)

    pathing_metadata = dict(build.pathing_metadata or {})
    reciprocal_pairs = list(pathing_metadata.get("reciprocal_transition_pairs", []) or [])
    missing_transition_bridges = [
        pair
        for pair in reciprocal_pairs
        if int(pair.get("bidirectional_bridge_count", 0) or 0) < 1
    ]
    expected_path_components = plan.get("expected_path_graph_component_count")
    actual_path_components = int(pathing_metadata.get("path_graph_component_count", 0) or 0)
    if expected_transition_pairs is not None:
        if len(reciprocal_pairs) != int(expected_transition_pairs):
            raise ValueError(
                f"{module} PTH metadata expected {expected_transition_pairs} reciprocal transition "
                f"pair(s), found {len(reciprocal_pairs)}."
            )
        if missing_transition_bridges:
            raise ValueError(f"{module} PTH generation omitted reciprocal transition bridges.")
    if expected_path_components is not None and actual_path_components != int(expected_path_components):
        raise ValueError(
            f"{module} PTH graph expected {expected_path_components} connected component(s), "
            f"found {actual_path_components}."
        )
    transition_pathing = {
        "source_transition_room_order": list(source_transition_rooms),
        "final_lyt_room_order": list(retained_rooms),
        "point_count": int(pathing_metadata.get("point_count", 0) or 0),
        "connection_count": int(pathing_metadata.get("connection_count", 0) or 0),
        "path_graph_component_count": actual_path_components,
        "expected_path_graph_component_count": expected_path_components,
        "reciprocal_transition_pair_count": len(reciprocal_pairs),
        "expected_reciprocal_transition_pair_count": expected_transition_pairs,
        "generated_portal_link_count": int(pathing_metadata.get("generated_portal_link_count", 0) or 0),
        "missing_transition_bridges": missing_transition_bridges,
        "transition_network_connected": bool(
            int(pathing_metadata.get("connection_count", 0) or 0) > 0
            and reciprocal_pairs
            and not missing_transition_bridges
        ),
        "fully_single_component": int(pathing_metadata.get("path_graph_component_count", 0) or 0) <= 1,
        "caveat": (
            "koq201_01g/01h/01j have no source-authored WOK transitions and remain isolated components."
            if module == "koq201"
            else (
                "koq200_01h has no source-authored WOK transition; its path component is preserved rather "
                "than inventing a nearly-kilometre portal."
            )
        ),
    }
    transition_contract_passed = bool(
        expected_transition_pairs is None
        or (
            int(source_transition_audit.get("reciprocal_transition_pair_count", -1))
            == int(expected_transition_pairs)
            and int(source_transition_audit.get("one_way_transition_count", -1)) == 0
            and int(source_transition_audit.get("invalid_transition_count", -1)) == 0
            and len(reciprocal_pairs) == int(expected_transition_pairs)
            and not missing_transition_bridges
        )
    )
    path_component_contract_passed = bool(
        expected_path_components is None or actual_path_components == int(expected_path_components)
    )
    script_contract_passed = bool(
        not plan.get("neutralize_unresolved_module_scripts")
        or (
            int(script_audit.get("unresolved_count", 0) or 0) == 0
            and int(output_script_audit.get("unresolved_count", 0) or 0) == 0
        )
    )
    structural_gates_passed = bool(
        build.ok
        and proofs.get("ready_for_manual_k2_test")
        and transition_pathing["transition_network_connected"]
        and bool(cross_room_wok_audit["passed"])
        and transition_contract_passed
        and path_component_contract_passed
        and script_contract_passed
        and bool(candidate_proof_gates.get("passed"))
        and (not plan.get("preserve_audited_room_bytes") or len(audited_output_hashes) == 24)
    )
    requires_transplant_bisection = bool(plan.get("requires_room_metadata_transplant_bisection"))
    known_failed_baseline = dict(plan.get("known_failed_baseline", {}) or {})
    manual_test_disposition = {
        "status": (
            "blocked_pending_room_metadata_transplant_bisection"
            if requires_transplant_bisection
            else ("structural_candidate_eligible_for_manual_test" if structural_gates_passed else "blocked")
        ),
        "known_failed_baseline": known_failed_baseline or None,
        "structural_gates_passed": structural_gates_passed,
        "requires_room_metadata_transplant_bisection": requires_transplant_bisection,
        "safe_or_installable_claim": False,
        "next_gate": (
            "Build isolated room/metadata transplant variants, identify the crashing partition or metadata "
            "family with live debugger evidence, then rebuild a new candidate."
            if requires_transplant_bisection
            else "Manual retail load and traversal proof."
        ),
    }
    if requires_transplant_bisection:
        proofs = dict(proofs)
        proofs["structural_gates_passed"] = structural_gates_passed
        proofs["ready_for_manual_k2_test"] = False
        proofs["manual_gate_reason"] = manual_test_disposition["status"]
    ready_for_manual_test = bool(structural_gates_passed and not requires_transplant_bisection)
    return {
        "module": module,
        "source_module": source_module,
        "area_resref": area,
        "candidate_root": str(destination),
        "compile_route": (
            "audited_complete_mdlops_k2_plus_ghoststudio_visual_partition_writer"
            if audited_resources_dir is not None
            else "ghoststudio_binary_mdl"
        ),
        "source_mod": _artifact(source_mod),
        "audited_candidate_resources_dir": str(audited_resources_dir) if audited_resources_dir else None,
        "audited_resource_overlay": audited_resource_overlay,
        "playable_rooms": playable_rooms,
        "visual_only_rooms": visual_only_rooms,
        "omitted_lyt_rooms": plan["omitted_lyt_rooms"],
        "source_transition_room_resrefs": source_transition_rooms,
        "authoritative_wok_inputs": authoritative_wok_inputs,
        "wok_repairs": wok_repairs,
        "wok_floor_reviews": wok_floor_reviews,
        "wok_floor_review_summary": {
            "reviewed_room_count": len(wok_floor_reviews),
            "removed_wall_face_count": sum(
                int(row.get("removed_face_count", 0)) for row in wok_floor_reviews
            ),
            "ambiguous_steep_face_count": sum(
                int(row.get("ambiguous_steep_face_count", 0)) for row in wok_floor_reviews
            ),
            "retail_traversal_required": any(
                int(row.get("ambiguous_steep_face_count", 0)) for row in wok_floor_reviews
            ),
        },
        "room_compiles": room_compiles,
        "audited_output_room_hashes": audited_output_hashes,
        "lyt": lyt,
        "vis": {"output": _artifact(vis_path), "policy": "symmetric_all_pairs"},
        "textures": textures,
        "entry_point_policy": entry_policy,
        "module_script_audit": script_audit,
        "source_module_script_audit": source_script_audit,
        "module_script_neutralization": script_neutralization,
        "module_script_audit_report": _artifact(script_audit_path),
        "output_module_script_audit": output_script_audit,
        "cross_room_wok_audit": cross_room_wok_audit,
        "source_transition_audit": source_transition_audit,
        "transition_aware_pathing": transition_pathing,
        "candidate_proof_gates": candidate_proof_gates,
        "known_failed_baseline": known_failed_baseline or None,
        "manual_test_disposition": manual_test_disposition,
        "structurally_ready_for_bisection": structural_gates_passed,
        "filtered_source_mod": filtered,
        "module_build": build.to_dict(),
        "proofs": proofs,
        "mod": _artifact(module_path) if module_path.is_file() else None,
        "kmap": _artifact(kmap_path) if kmap_path.is_file() else None,
        "ready_for_manual_k2_test": ready_for_manual_test,
        "retail_game_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        action="append",
        choices=sorted(set(MODULE_PLANS) | set(MODULE_ALIASES)),
        default=[],
        help=(
            "Module to build; repeatable. Use koq200/koq201 for canonical identities. "
            "Runtime-failed modules remain bisection-only even when structural gates pass. "
            "Defaults to both provenance-named RNV modules."
        ),
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
    modules = tuple(dict.fromkeys(args.module)) or DEFAULT_MODULES
    reports = [_build_module(module, output_root, manager) for module in modules]
    manifest = {
        "schema": "ghoststudio.rnv-k2-honest-candidates.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "modules": reports,
        "all_ready_for_manual_k2_test": all(row["ready_for_manual_k2_test"] for row in reports),
        "all_structurally_ready_for_bisection": all(
            bool(row.get("structurally_ready_for_bisection", row["ready_for_manual_k2_test"]))
            for row in reports
        ),
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
                        "structurally_ready_for_bisection": row.get("structurally_ready_for_bisection"),
                        "manual_test_disposition": row.get("manual_test_disposition", {}).get("status"),
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
