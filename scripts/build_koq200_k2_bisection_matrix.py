"""Build a fail-closed K2 KOQ200 metadata/room transplant matrix.

The retail engine is the oracle.  These packages are deliberately *not*
release candidates: each one changes a single resource axis relative to the
known-loadable ``tst_light`` shell so a manual warp can identify whether the
KOQ200 transition stops in module metadata or in a particular room triplet.

Nothing produced by this script is installed into KOTOR.  Every output uses a
unique module resref and deterministic Mod_ID so the variants can be staged
side-by-side after the game has closed.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import uuid
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for _path in reversed(_python_roots(ROOT)):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)


FAILED_MODULE_DEFAULT = (
    ROOT
    / "Saved"
    / "KotorManualWarpEvidence"
    / "20260718T144644223_koq200_k2_crash_safe_6395"
    / "koq200.mod"
)
ORACLE_MODULE_DEFAULT = (
    ROOT
    / "exports"
    / "SAO_Drexl_Working_K2_Package_20260703"
    / "Test_Map"
    / "tst_light.mod"
)
OUTPUT_DEFAULT = ROOT / "artifacts" / "map_studio" / "koq200_k2_bisection"

FAILED_MODULE_SHA256 = "6395c56e2ee6184a29e505206e90fec0019306f169c51766ea6fcfd978667a78"
ORACLE_MODULE_SHA256 = "d5162ac70ab512dea4fc9c66227b4eaae244860cb00539276c67daa4ceb4d0c1"

FAILED_AREA_RESREF = "koq200"
ORACLE_AREA_RESREF = "tst_light"
ORACLE_ROOM_RESREF = "r00_test"
CANDIDATE_ROOM_RESREFS = tuple(f"koq200_01{suffix}" for suffix in "abcdefgh")
WALKABLE_SURFACE_IDS = frozenset({1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 30})
MODULE_ID_NAMESPACE = uuid.UUID("39b4f4af-8fb6-5f39-a51f-50dcfe574b62")

_RUNTIME_GIT_LIST_FIELDS = (
    "CameraList",
    "Creature List",
    "Door List",
    "Encounter List",
    "List",
    "Placeable List",
    "SoundList",
    "StoreList",
    "TriggerList",
    "WaypointList",
)


@dataclass(frozen=True)
class VariantSpec:
    module_resref: str
    label: str
    purpose: str
    metadata_source: str
    room_source: str
    candidate_room: str = ""
    strip_runtime_git: bool = False
    strip_module_event_scripts: bool = False


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        module_resref="kq2ctl",
        label="renamed_oracle_control",
        purpose="Prove the renamed tst_light shell and the current K2 patch environment still load.",
        metadata_source="oracle",
        room_source="oracle",
    ),
    VariantSpec(
        module_resref="kq2min",
        label="oracle_minimal_git_control",
        purpose="Prove the empty-runtime-GIT control used by the room transplants.",
        metadata_source="oracle",
        room_source="oracle",
        strip_runtime_git=True,
    ),
    VariantSpec(
        module_resref="kq2r0h",
        label="oracle_metadata_candidate_01h",
        purpose="Test the smallest KOQ200 room triplet under proven metadata and an empty runtime GIT.",
        metadata_source="oracle",
        room_source="candidate",
        candidate_room="koq200_01h",
        strip_runtime_git=True,
    ),
    VariantSpec(
        module_resref="kq2r0a",
        label="oracle_metadata_candidate_01a",
        purpose="Test KOQ200's entry/main room triplet under proven metadata and an empty runtime GIT.",
        metadata_source="oracle",
        room_source="candidate",
        candidate_room="koq200_01a",
        strip_runtime_git=True,
    ),
    VariantSpec(
        module_resref="kq2met",
        label="candidate_metadata_oracle_room",
        purpose="Test KOQ200 IFO/ARE/GIT semantics while retaining the proven r00_test room/layout.",
        metadata_source="candidate",
        room_source="oracle",
    ),
    VariantSpec(
        module_resref="kq2scr",
        label="candidate_metadata_scriptless_oracle_room",
        purpose=(
            "Retest KOQ200 metadata under the proven r00_test room after clearing only inherited "
            "module event hooks whose NCS resources are absent from the candidate and clean K2 libraries."
        ),
        metadata_source="candidate",
        room_source="oracle",
        strip_module_event_scripts=True,
    ),
    VariantSpec(
        module_resref="kq2all",
        label="oracle_scriptless_candidate_all_rooms",
        purpose=(
            "Test the complete KOQ200 eight-room layout under the proven oracle shell with empty "
            "runtime GIT and module event hooks, preserving every candidate room triplet and its "
            "original in-range WOK transitions byte-for-byte."
        ),
        metadata_source="oracle",
        room_source="candidate_all",
        strip_runtime_git=True,
        strip_module_event_scripts=True,
    ),
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_resources(path: Path) -> dict[tuple[str, Any], bytes]:
    from pykotor.resource.formats.erf import read_erf

    archive = read_erf(path)
    resources: dict[tuple[str, Any], bytes] = {}
    for item in archive:
        resref = str(item.resref).strip().lower()
        resources[(resref, item.restype)] = bytes(archive.get(item.resref, item.restype) or b"")
    return resources


def _resource(resources: Mapping[tuple[str, Any], bytes], resref: str, restype: Any) -> bytes:
    key = (resref.lower(), restype)
    try:
        return bytes(resources[key])
    except KeyError as exc:
        raise KeyError(f"Missing required source resource {resref}.{restype.extension}") from exc


def _single_room_lyt(room_resref: str) -> bytes:
    room = room_resref.lower()
    return (
        "beginlayout\r\n"
        "   roomcount 1\r\n"
        f"      {room} 0.0 0.0 0.0\r\n"
        "   trackcount 0\r\n"
        "   obstaclecount 0\r\n"
        "   doorhookcount 0\r\n"
        "donelayout\r\n"
    ).encode("ascii")


def _single_room_vis(room_resref: str) -> bytes:
    return f"{room_resref.lower()} 0\r\n".encode("ascii")


def _multi_room_lyt(room_resrefs: tuple[str, ...]) -> bytes:
    rooms = tuple(str(room).strip().lower() for room in room_resrefs)
    if not rooms or any(not room for room in rooms) or len(set(rooms)) != len(rooms):
        raise ValueError("Multi-room LYT requires a non-empty ordered set of unique room resrefs.")
    lines = ["beginlayout", f"   roomcount {len(rooms)}"]
    lines.extend(f"      {room} 0.0 0.0 0.0" for room in rooms)
    lines.extend(("   trackcount 0", "   obstaclecount 0", "   doorhookcount 0", "donelayout"))
    return ("\r\n".join(lines) + "\r\n").encode("ascii")


def _normalize_ascii_crlf(data: bytes) -> bytes:
    text = bytes(data).decode("ascii")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return (normalized.replace("\n", "\r\n") + "\r\n").encode("ascii")


def _walkable_entry_from_wok(data: bytes) -> tuple[float, float, float]:
    """Return a point just above the first indexed walkable triangle.

    KOQ200's recovered WOK vertices are already in module coordinates.  The
    header ``position`` row is retained as source metadata and is intentionally
    not added a second time here.
    """

    if len(data) < 136 or data[:8] != b"BWM V1.0":
        raise ValueError("Candidate room WOK does not contain a complete BWM V1.0 header.")
    vertex_count, vertex_offset, face_count, face_offset, material_offset = struct.unpack_from(
        "<5I", data, 72
    )
    if vertex_count < 3 or face_count < 1:
        raise ValueError("Candidate room WOK has no triangle suitable for an entry point.")
    if vertex_offset + vertex_count * 12 > len(data):
        raise ValueError("Candidate room WOK vertex table is out of bounds.")
    if face_offset + face_count * 12 > len(data) or material_offset + face_count * 4 > len(data):
        raise ValueError("Candidate room WOK face/material table is out of bounds.")

    vertices = [struct.unpack_from("<3f", data, vertex_offset + index * 12) for index in range(vertex_count)]
    for face_index in range(face_count):
        material = struct.unpack_from("<I", data, material_offset + face_index * 4)[0]
        if int(material) not in WALKABLE_SURFACE_IDS:
            continue
        indices = struct.unpack_from("<3I", data, face_offset + face_index * 12)
        if any(index >= vertex_count for index in indices):
            raise ValueError(f"Candidate room WOK face {face_index} has an invalid vertex index.")
        points = [vertices[index] for index in indices]
        return (
            sum(point[0] for point in points) / 3.0,
            sum(point[1] for point in points) / 3.0,
            (sum(point[2] for point in points) / 3.0) + 0.05,
        )
    raise ValueError("Candidate room WOK contains no walkable material face.")


def _neutralize_wok_transitions(data: bytes) -> tuple[bytes, int]:
    """Clear cross-room transition destinations without rewriting BWM tables.

    A single-room bisection LYT cannot safely retain destinations into the
    original eight-room layout.  Only the transition uint32 in each existing
    edge row changes; indexed geometry, adjacency, AABB, edge IDs, and perimeter
    records remain byte-identical.
    """

    if len(data) < 136 or data[:8] != b"BWM V1.0":
        raise ValueError("Candidate room WOK does not contain a complete BWM V1.0 header.")
    fields = struct.unpack_from("<16I", data, 72)
    edge_count, edge_offset = int(fields[12]), int(fields[13])
    if edge_offset + edge_count * 8 > len(data):
        raise ValueError("Candidate room WOK edge table is out of bounds.")
    output = bytearray(data)
    changed = 0
    for index in range(edge_count):
        transition_offset = edge_offset + index * 8 + 4
        transition = struct.unpack_from("<I", output, transition_offset)[0]
        if transition == 0xFFFFFFFF:
            continue
        struct.pack_into("<I", output, transition_offset, 0xFFFFFFFF)
        changed += 1
    return bytes(output), changed


def _wok_transition_rows(data: bytes) -> tuple[tuple[int, int], ...]:
    """Read non-sentinel directed-edge transitions without rewriting the WOK."""

    if len(data) < 136 or data[:8] != b"BWM V1.0":
        raise ValueError("Candidate room WOK does not contain a complete BWM V1.0 header.")
    fields = struct.unpack_from("<16I", data, 72)
    face_count = int(fields[2])
    edge_count, edge_offset = int(fields[12]), int(fields[13])
    if edge_offset + edge_count * 8 > len(data):
        raise ValueError("Candidate room WOK edge table is out of bounds.")
    rows: list[tuple[int, int]] = []
    for index in range(edge_count):
        directed_edge, transition = struct.unpack_from("<ii", data, edge_offset + index * 8)
        if transition < 0:
            continue
        if directed_edge < 0 or directed_edge >= face_count * 3:
            raise ValueError(f"Candidate room WOK transition references invalid directed edge {directed_edge}.")
        rows.append((int(directed_edge), int(transition)))
    return tuple(rows)


def _ifo_entry(data: bytes) -> tuple[float, float, float]:
    from pykotor.resource.formats.gff import read_gff

    root = read_gff(data).root
    return (
        float(root.get("Mod_Entry_X", 0.0) or 0.0),
        float(root.get("Mod_Entry_Y", 0.0) or 0.0),
        float(root.get("Mod_Entry_Z", 0.0) or 0.0),
    )


def _single_point_pth(entry: tuple[float, float, float]) -> bytes:
    from pykotor.resource.generics.pth import PTH, bytes_pth

    graph = PTH()
    graph.add(float(entry[0]), float(entry[1]))
    return bytes_pth(graph)


def _patch_ifo_identity(
    data: bytes,
    *,
    module_resref: str,
    entry: tuple[float, float, float] | None = None,
) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    gff = read_gff(data)
    root = gff.root
    module = module_resref.lower()
    root.set_binary("Mod_ID", uuid.uuid5(MODULE_ID_NAMESPACE, module).bytes)
    root.set_resref("Mod_Entry_Area", module)
    root.set_string("Mod_Tag", module.upper())
    area_list = root.get("Mod_Area_list")
    if area_list is None or len(area_list) < 1:
        raise ValueError("Source IFO has no Mod_Area_list row to retarget.")
    for area in area_list:
        area.set_resref("Area_Name", module)
    if entry is not None:
        root.set_single("Mod_Entry_X", float(entry[0]))
        root.set_single("Mod_Entry_Y", float(entry[1]))
        root.set_single("Mod_Entry_Z", float(entry[2]))
    return bytes_gff(gff)


def _patch_are_rooms(data: bytes, *, module_resref: str, room_resrefs: tuple[str, ...]) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFFFieldType, GFFList

    requested = tuple(str(room).strip().lower() for room in room_resrefs)
    if not requested or any(not room for room in requested) or len(set(requested)) != len(requested):
        raise ValueError("ARE room patch requires a non-empty ordered set of unique room resrefs.")
    gff = read_gff(data)
    root = gff.root
    root.set_string("Tag", module_resref.upper())
    rooms = root.get("Rooms")
    if rooms is None or len(rooms) < 1:
        raise ValueError("Source ARE has no Rooms row to retarget.")
    replacement = GFFList()
    for room_resref in requested:
        row = copy.deepcopy(rooms.at(0))
        if row.what_type("RoomName") == GFFFieldType.ResRef:
            row.set_resref("RoomName", room_resref)
        else:
            row.set_string("RoomName", room_resref)
        replacement.append(row)
    root.set_list("Rooms", replacement)
    return bytes_gff(gff)


def _patch_are_single_room(data: bytes, *, module_resref: str, room_resref: str) -> bytes:
    return _patch_are_rooms(
        data,
        module_resref=module_resref,
        room_resrefs=(room_resref,),
    )


def _strip_runtime_git(data: bytes) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFFList

    gff = read_gff(data)
    for field in _RUNTIME_GIT_LIST_FIELDS:
        if gff.root.exists(field):
            gff.root.set_list(field, GFFList())
    if not gff.root.exists("UseTemplates"):
        gff.root.set_uint8("UseTemplates", 1)
    return bytes_gff(gff)


def _strip_ifo_module_event_scripts(data: bytes) -> tuple[bytes, list[dict[str, str]]]:
    """Clear preserved IFO event hooks for the explicit scriptless bisection.

    The failed KOQ200 IFO inherited ``001EBO`` hooks without carrying their
    module-local NCS payloads.  This helper uses Map Studio's canonical module
    hook list and records every non-empty field it clears; no unrelated IFO
    metadata is rebuilt or discarded.
    """

    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from src.core.modules.authored_module_metadata import MODULE_SCRIPT_FIELDS

    gff = read_gff(data)
    cleared: list[dict[str, str]] = []
    for label in MODULE_SCRIPT_FIELDS:
        if not gff.root.exists(label):
            continue
        value = str(gff.root.get(label) or "").strip()
        if not value:
            continue
        cleared.append({"field": label, "resref": value.lower()})
        gff.root.set_resref(label, "")
    return bytes_gff(gff), cleared


def _candidate_texture_payload(resources: Mapping[tuple[str, Any], bytes]) -> dict[tuple[str, Any], bytes]:
    wanted = {"tga", "tpc", "txi"}
    return {
        key: bytes(data)
        for key, data in resources.items()
        if str(key[1].extension).lower() in wanted
    }


def _oracle_base(
    oracle: Mapping[tuple[str, Any], bytes],
    *,
    module_resref: str,
) -> dict[tuple[str, Any], bytes]:
    """Copy the oracle archive and rename only its area-root resources."""

    from pykotor.resource.type import ResourceType as RT

    output: dict[tuple[str, Any], bytes] = {}
    for (resref, restype), data in oracle.items():
        target_resref = module_resref if resref == ORACLE_AREA_RESREF else resref
        output[(target_resref, restype)] = bytes(data)
    output[("module", RT.IFO)] = _patch_ifo_identity(
        _resource(output, "module", RT.IFO), module_resref=module_resref
    )
    output[(module_resref, RT.ARE)] = _patch_are_single_room(
        _resource(output, module_resref, RT.ARE),
        module_resref=module_resref,
        room_resref=ORACLE_ROOM_RESREF,
    )
    # The known-loadable tst_light fixture omits PTH entirely.  The strict Map
    # Studio engine contract requires one path point, so add a deterministic
    # isolated point at the unchanged oracle entry position.
    if (module_resref, RT.PTH) not in output:
        output[(module_resref, RT.PTH)] = _single_point_pth(
            _ifo_entry(output[("module", RT.IFO)])
        )
    return output


def _build_variant_resources(
    spec: VariantSpec,
    *,
    failed: Mapping[tuple[str, Any], bytes],
    oracle: Mapping[tuple[str, Any], bytes],
) -> tuple[dict[tuple[str, Any], bytes], dict[str, Any]]:
    from pykotor.resource.type import ResourceType as RT

    output = _oracle_base(oracle, module_resref=spec.module_resref)
    entry: tuple[float, float, float] | None = None
    injected: list[str] = []
    transition_note: dict[str, Any] | None = None
    transition_preservation_note: dict[str, Any] | None = None
    script_note: dict[str, Any] | None = None

    if spec.metadata_source == "candidate":
        oracle_entry = _ifo_entry(_resource(oracle, "module", RT.IFO))
        output[("module", RT.IFO)] = _patch_ifo_identity(
            _resource(failed, "module", RT.IFO),
            module_resref=spec.module_resref,
            entry=oracle_entry,
        )
        output[(spec.module_resref, RT.ARE)] = _patch_are_single_room(
            _resource(failed, FAILED_AREA_RESREF, RT.ARE),
            module_resref=spec.module_resref,
            room_resref=ORACLE_ROOM_RESREF,
        )
        output[(spec.module_resref, RT.GIT)] = _resource(failed, FAILED_AREA_RESREF, RT.GIT)
        injected.extend(["module.ifo", f"{FAILED_AREA_RESREF}.are", f"{FAILED_AREA_RESREF}.git"])

    if spec.room_source == "candidate_all":
        for restype in (RT.MDL, RT.MDX, RT.WOK):
            output.pop((ORACLE_ROOM_RESREF, restype), None)
        preserved_rooms: list[dict[str, Any]] = []
        for room in CANDIDATE_ROOM_RESREFS:
            room_transitions: tuple[tuple[int, int], ...] = ()
            triplet_hashes: dict[str, str] = {}
            for restype in (RT.MDL, RT.MDX, RT.WOK):
                source_data = _resource(failed, room, restype)
                output[(room, restype)] = source_data
                injected.append(f"{room}.{restype.extension}")
                triplet_hashes[str(restype.extension).lower()] = _sha256_bytes(source_data)
                if restype == RT.WOK:
                    room_transitions = _wok_transition_rows(source_data)
                    invalid_destinations = sorted(
                        {destination for _edge, destination in room_transitions if destination >= len(CANDIDATE_ROOM_RESREFS)}
                    )
                    if invalid_destinations:
                        raise ValueError(
                            f"{room}.wok has transition destination(s) outside the eight-room LYT: "
                            f"{invalid_destinations}"
                        )
            preserved_rooms.append(
                {
                    "room_resref": room,
                    "triplet_sha256": triplet_hashes,
                    "transition_count": len(room_transitions),
                    "transition_destinations": sorted({destination for _edge, destination in room_transitions}),
                }
            )
        output.update(_candidate_texture_payload(failed))
        entry_room = CANDIDATE_ROOM_RESREFS[0]
        entry = _walkable_entry_from_wok(output[(entry_room, RT.WOK)])
        output[(spec.module_resref, RT.LYT)] = _multi_room_lyt(CANDIDATE_ROOM_RESREFS)
        output[(spec.module_resref, RT.VIS)] = _normalize_ascii_crlf(
            _resource(failed, FAILED_AREA_RESREF, RT.VIS)
        )
        output[(spec.module_resref, RT.PTH)] = _single_point_pth(entry)
        output[(spec.module_resref, RT.ARE)] = _patch_are_rooms(
            output[(spec.module_resref, RT.ARE)],
            module_resref=spec.module_resref,
            room_resrefs=CANDIDATE_ROOM_RESREFS,
        )
        output[("module", RT.IFO)] = _patch_ifo_identity(
            output[("module", RT.IFO)],
            module_resref=spec.module_resref,
            entry=entry,
        )
        transition_preservation_note = {
            "mode": "preserved_exactly",
            "lyt_room_order": list(CANDIDATE_ROOM_RESREFS),
            "rooms": preserved_rooms,
        }

    elif spec.room_source == "candidate":
        room = spec.candidate_room.lower()
        if not room:
            raise ValueError(f"{spec.module_resref} does not name its candidate room.")
        for restype in (RT.MDL, RT.MDX, RT.WOK):
            output.pop((ORACLE_ROOM_RESREF, restype), None)
            source_data = _resource(failed, room, restype)
            if restype == RT.WOK:
                source_data, neutralized = _neutralize_wok_transitions(source_data)
                transition_note = {
                    "source_wok_sha256": _sha256_bytes(_resource(failed, room, RT.WOK)),
                    "bisection_wok_sha256": _sha256_bytes(source_data),
                    "neutralized_transition_count": neutralized,
                    "unchanged_tables": ["vertices", "faces", "materials", "normals", "planes", "aabb", "adjacency", "edge_ids", "perimeters"],
                }
            output[(room, restype)] = source_data
            injected.append(f"{room}.{restype.extension}")
        output.update(_candidate_texture_payload(failed))
        entry = _walkable_entry_from_wok(output[(room, RT.WOK)])
        output[(spec.module_resref, RT.LYT)] = _single_room_lyt(room)
        output[(spec.module_resref, RT.VIS)] = _single_room_vis(room)
        output[(spec.module_resref, RT.PTH)] = _single_point_pth(entry)
        output[(spec.module_resref, RT.ARE)] = _patch_are_single_room(
            output[(spec.module_resref, RT.ARE)],
            module_resref=spec.module_resref,
            room_resref=room,
        )
        output[("module", RT.IFO)] = _patch_ifo_identity(
            output[("module", RT.IFO)],
            module_resref=spec.module_resref,
            entry=entry,
        )

    if spec.strip_runtime_git:
        output[(spec.module_resref, RT.GIT)] = _strip_runtime_git(
            output[(spec.module_resref, RT.GIT)]
        )

    if spec.strip_module_event_scripts:
        source_ifo = output[("module", RT.IFO)]
        stripped_ifo, cleared = _strip_ifo_module_event_scripts(source_ifo)
        if not cleared:
            raise ValueError(
                f"{spec.module_resref} requested a scriptless metadata bisection, but no event hooks were present."
            )
        output[("module", RT.IFO)] = stripped_ifo
        script_note = {
            "source_ifo_sha256": _sha256_bytes(source_ifo),
            "bisection_ifo_sha256": _sha256_bytes(stripped_ifo),
            "cleared_module_event_hooks": cleared,
            "other_ifo_fields_preserved_semantically": True,
        }

    return output, {
        "entry_point": list(entry) if entry is not None else None,
        "injected": injected,
        "synthetic_single_point_pth": True,
        "transition_neutralization": transition_note,
        "transition_preservation": transition_preservation_note,
        "module_event_script_neutralization": script_note,
    }


def _write_module(resources: Mapping[tuple[str, Any], bytes], target: Path) -> None:
    from pykotor.resource.formats.erf import ERF, ERFType, write_erf

    archive = ERF(ERFType.MOD)
    for (resref, restype), data in sorted(
        resources.items(), key=lambda row: (row[0][0], str(row[0][1].extension))
    ):
        archive.set_data(resref, restype, bytes(data))
    target.parent.mkdir(parents=True, exist_ok=True)
    write_erf(archive, target)


def _engine_contract(module_resref: str, resources: Mapping[tuple[str, Any], bytes]) -> dict[str, Any]:
    from src.core.validation.kotor_module_engine_contract import (
        KotorModuleEngineContractRequest,
        validate_kotor_module_engine_contract,
    )

    normalized = {
        (resref.lower(), str(restype.extension).lower()): bytes(data)
        for (resref, restype), data in resources.items()
    }
    report = validate_kotor_module_engine_contract(
        KotorModuleEngineContractRequest(
            game="K2",
            module_resref=module_resref,
            resources=normalized,
        )
    )
    return report.to_dict()


def build_matrix(
    failed_module: Path,
    oracle_module: Path,
    output_dir: Path,
    *,
    selected: set[str] | None = None,
) -> dict[str, Any]:
    failed_module = failed_module.resolve()
    oracle_module = oracle_module.resolve()
    output_dir = output_dir.resolve()
    if not failed_module.is_file():
        raise FileNotFoundError(f"Failed KOQ200 evidence module not found: {failed_module}")
    if not oracle_module.is_file():
        raise FileNotFoundError(f"Known-loadable tst_light module not found: {oracle_module}")

    failed_sha = _sha256_path(failed_module)
    oracle_sha = _sha256_path(oracle_module)
    if failed_sha != FAILED_MODULE_SHA256:
        raise ValueError(
            f"KOQ200 source hash is {failed_sha}; expected exact failed artifact {FAILED_MODULE_SHA256}."
        )
    if oracle_sha != ORACLE_MODULE_SHA256:
        raise ValueError(
            f"Oracle source hash is {oracle_sha}; expected known-loadable artifact {ORACLE_MODULE_SHA256}."
        )

    failed = _archive_resources(failed_module)
    oracle = _archive_resources(oracle_module)
    rows: list[dict[str, Any]] = []
    wanted = {value.lower() for value in selected} if selected else None
    for order, spec in enumerate(VARIANTS, start=1):
        if wanted is not None and spec.module_resref not in wanted and spec.label not in wanted:
            continue
        resources, build_notes = _build_variant_resources(spec, failed=failed, oracle=oracle)
        variant_dir = output_dir / f"{order:02d}_{spec.module_resref}_{spec.label}"
        target = variant_dir / "Modules" / f"{spec.module_resref}.mod"
        _write_module(resources, target)
        readback = _archive_resources(target)
        if readback != resources:
            raise ValueError(f"{spec.module_resref} archive readback does not match its build inputs.")
        contract = _engine_contract(spec.module_resref, readback)
        resource_rows = [
            {
                "resref": resref,
                "restype": str(restype.extension).lower(),
                "size": len(data),
                "sha256": _sha256_bytes(data),
            }
            for (resref, restype), data in sorted(
                readback.items(), key=lambda row: (row[0][0], str(row[0][1].extension))
            )
        ]
        row = {
            **asdict(spec),
            "order": order,
            "module_path": str(target),
            "module_sha256": _sha256_path(target),
            "resource_count": len(readback),
            "resources": resource_rows,
            "build_notes": build_notes,
            "structural_contract_export_ready": bool(contract.get("export_ready")),
            "structural_contract": contract,
            "bisection_only": True,
            "ready_for_manual_k2_test": False,
            "manual_test_status": "unverified",
            "retail_engine_status": "unknown",
        }
        variant_dir.mkdir(parents=True, exist_ok=True)
        (variant_dir / f"{spec.module_resref}.bisection.json").write_text(
            json.dumps(row, indent=2), encoding="utf-8"
        )
        rows.append(row)

    if wanted is not None:
        matched = {row["module_resref"] for row in rows}
        unresolved = wanted - matched - {row["label"] for row in rows}
        if unresolved:
            raise ValueError(f"Unknown bisection variant(s): {sorted(unresolved)}")
    matrix = {
        "schema": "ghostrigger.koq200_k2_bisection.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "failed_source": str(failed_module),
        "failed_source_sha256": failed_sha,
        "oracle_source": str(oracle_module),
        "oracle_source_sha256": oracle_sha,
        "installation_performed": False,
        "ready_for_manual_k2_test": False,
        "retail_engine_status": "unknown",
        "instructions": (
            "Do not promote any variant. After KOTOR closes, stage all variants side-by-side and "
            "manually warp in listed order with a fresh live-log session. Stop at the first failure."
        ),
        "variants": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "koq200-k2-bisection-matrix.json").write_text(
        json.dumps(matrix, indent=2), encoding="utf-8"
    )
    return matrix


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failed-module", type=Path, default=FAILED_MODULE_DEFAULT)
    parser.add_argument("--oracle-module", type=Path, default=ORACLE_MODULE_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Optional module resref or label to build; repeat for more than one. Defaults to all.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    matrix = build_matrix(
        args.failed_module,
        args.oracle_module,
        args.output_dir,
        selected=set(args.variant) or None,
    )
    print(f"Built {len(matrix['variants'])} bisection-only KOQ200 K2 modules under {args.output_dir.resolve()}")
    for row in matrix["variants"]:
        print(
            f"  {row['order']:02d} warp {row['module_resref']}  "
            f"sha256={row['module_sha256']}  structural={row['structural_contract_export_ready']}"
        )
    print("No KOTOR installation files were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
