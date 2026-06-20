"""Compare a grdev01 diagnostic MOD against stock KOTOR module metadata.

This is a crash-investigation helper for the Map Studio `grdev01` smoke test.
It compares the module shell resources that most often cause load failures:

* module.ifo
* ARE
* GIT root/list shape
* LYT/VIS text resources
* PTH point/connection counts

The script is diagnostic-only.  It does not modify files and does not mark a
package game-tested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATHS = (
    "native/GhostRigger.Domain.Core.Modules/Python",
    "native/GhostRigger.Domain.Core.Game/Python",
    "native/GhostRigger.Domain.Core.Geometry/Python",
    "native/GhostRigger.Domain.Core.Math/Python",
    ".",
)

DEFAULT_INSTALLED_MODULE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor\Modules\grdev01.mod")
DEFAULT_GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
STOCK_MODULE_ROOT = "m02aa"
STOCK_RIM = "tar_m02aa.rim"
ROOM_NAME_RE = re.compile(rb"\b(?:m02aa|grdev01)_[A-Za-z0-9_]+\b", re.IGNORECASE)

EXPECTED_IFO_LABELS = {
    "Expansion_Pack",
    "Mod_Area_list",
    "Mod_Creator_ID",
    "Mod_Description",
    "Mod_Entry_Area",
    "Mod_Entry_Dir_X",
    "Mod_Entry_Dir_Y",
    "Mod_Entry_X",
    "Mod_Entry_Y",
    "Mod_Entry_Z",
    "Mod_Hak",
    "Mod_ID",
    "Mod_IsSaveGame",
    "Mod_MinPerHour",
    "Mod_Name",
    "Mod_Tag",
    "Mod_VO_ID",
    "Mod_Version",
    "Mod_XPScale",
}
EXPECTED_ARE_LABELS = {
    "CameraStyle",
    "Comments",
    "Creator_ID",
    "Flags",
    "ID",
    "Name",
    "NoRest",
    "PlayerVsPlayer",
    "Rooms",
    "Tag",
    "Unescapable",
    "Version",
}
EXPECTED_GIT_LABELS = {
    "AreaProperties",
    "CameraList",
    "Creature List",
    "Door List",
    "Encounter List",
    "List",
    "Placeable List",
    "SoundList",
    "StoreList",
    "TriggerList",
    "UseTemplates",
    "WaypointList",
}


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-path", type=Path, default=DEFAULT_INSTALLED_MODULE, help="Diagnostic MOD to compare.")
    parser.add_argument("--game-root-dir", type=Path, default=DEFAULT_GAME_ROOT, help="KOTOR install root for stock resources.")
    parser.add_argument("--stock-module-root", default=STOCK_MODULE_ROOT, help="Stock module root to compare against.")
    parser.add_argument("--stock-rim", default=STOCK_RIM, help="Stock RIM containing ARE/GIT/IFO.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path. Defaults to <module package directory>/grdev01_stock_metadata_compare.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print the report JSON.")
    return parser


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resource_bytes(result: Any, label: str) -> bytes:
    data = getattr(result, "data", result)
    if callable(data):
        data = data()
    data = bytes(data or b"")
    if not data:
        raise ValueError(f"{label} has no bytes.")
    return data


def _archive_get_any(archive: Any, restype: Any, preferred_resrefs: tuple[str, ...] = ()) -> tuple[str, bytes]:
    for resref in preferred_resrefs:
        data = archive.get(resref, restype)
        if data:
            return resref, bytes(data)
    for item in archive:
        if item.restype == restype:
            data = archive.get(item.resref, item.restype)
            if data:
                return item.resref, bytes(data)
    raise FileNotFoundError(f"No {restype.extension.upper()} resource found.")


def _stock_resource(installation: Any, resref: str, restype: Any) -> bytes:
    result = installation.resource(resref, restype)
    if result is None:
        raise FileNotFoundError(f"Stock resource {resref}.{restype.extension} not found.")
    return _resource_bytes(result, f"{resref}.{restype.extension}")


def _field_summary(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return {"kind": "bytes", "size": len(value), "sha256": _sha256(value)}
    try:
        from pykotor.resource.formats.gff.gff_data import GFFList, GFFStruct
    except Exception:
        GFFList = ()  # type: ignore[assignment]
        GFFStruct = ()  # type: ignore[assignment]
    if isinstance(value, GFFStruct):
        return {"kind": "struct", "field_count": len(_gff_fields(value))}
    if isinstance(value, GFFList):
        child_types: list[int] = []
        for index in range(len(value)):
            try:
                child_types.append(int(value.at(index).struct_id))
            except Exception:
                child_types.append(-1)
        return {"kind": "list", "length": len(value), "struct_ids": child_types[:32]}
    if hasattr(value, "stringref"):
        return {
            "kind": "locstring",
            "stringref": int(getattr(value, "stringref", -1)),
            "substring_count": len(getattr(value, "_substrings", {}) or {}),
        }
    return {"kind": type(value).__name__, "repr": repr(value)[:200]}


def _gff_fields(struct: Any) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    for item in struct:
        if not isinstance(item, tuple) or len(item) < 3:
            continue
        label, field_type, value = item[0], item[1], item[2]
        fields[str(label)] = {
            "type": str(getattr(field_type, "name", field_type)),
            "value": _field_summary(value),
        }
    return fields


def _diff_fields(left: dict[str, dict[str, Any]], right: dict[str, dict[str, Any]]) -> dict[str, Any]:
    left_keys = set(left)
    right_keys = set(right)
    shared = sorted(left_keys & right_keys)
    type_mismatches = [
        {"field": key, "left_type": left[key]["type"], "right_type": right[key]["type"]}
        for key in shared
        if left[key]["type"] != right[key]["type"]
    ]
    value_differences = [
        {"field": key, "left": left[key]["value"], "right": right[key]["value"]}
        for key in shared
        if left[key]["type"] == right[key]["type"] and left[key]["value"] != right[key]["value"]
    ]
    return {
        "left_field_count": len(left),
        "right_field_count": len(right),
        "missing_from_left": sorted(right_keys - left_keys),
        "extra_in_left": sorted(left_keys - right_keys),
        "type_mismatches": type_mismatches,
        "value_differences": value_differences,
    }


def _root_report(name: str, left_data: bytes, right_data: bytes) -> dict[str, Any]:
    from pykotor.resource.formats.gff import read_gff

    left = read_gff(left_data).root
    right = read_gff(right_data).root
    left_fields = _gff_fields(left)
    right_fields = _gff_fields(right)
    expected = EXPECTED_IFO_LABELS if name == "ifo" else EXPECTED_ARE_LABELS if name == "are" else EXPECTED_GIT_LABELS
    return {
        "left_size": len(left_data),
        "right_size": len(right_data),
        "left_sha256": _sha256(left_data),
        "right_sha256": _sha256(right_data),
        "left_fields": left_fields,
        "right_fields": right_fields,
        "diff": _diff_fields(left_fields, right_fields),
        "engine_shape": {
            "expected_labels": sorted(expected),
            "missing_expected_labels": sorted(expected - set(left_fields)),
            "extra_expected_reference_labels": sorted(expected - set(right_fields)),
        },
    }


def _text_report(left_data: bytes, right_data: bytes) -> dict[str, Any]:
    left = left_data.decode("latin-1", errors="replace").splitlines()
    right = right_data.decode("latin-1", errors="replace").splitlines()
    return {
        "left_size": len(left_data),
        "right_size": len(right_data),
        "left_sha256": _sha256(left_data),
        "right_sha256": _sha256(right_data),
        "left_line_count": len(left),
        "right_line_count": len(right),
        "same_text": left == right,
        "left_preview": left[:20],
        "right_preview": right[:20],
    }


def _pth_report(left_data: bytes, right_data: bytes) -> dict[str, Any]:
    from pykotor.resource.generics.pth import read_pth

    def counts(data: bytes) -> dict[str, int]:
        pth = read_pth(data)
        point_count = len(pth)
        connection_count = sum(len(pth.outgoing(index)) for index in range(point_count))
        return {"point_count": point_count, "connection_count": connection_count}

    return {
        "left_size": len(left_data),
        "right_size": len(right_data),
        "left_sha256": _sha256(left_data),
        "right_sha256": _sha256(right_data),
        "left_counts": counts(left_data),
        "right_counts": counts(right_data),
    }


def _resource_index(archive: Any) -> list[dict[str, Any]]:
    resources = []
    for item in archive:
        data = archive.get(item.resref, item.restype) or b""
        resources.append({"resref": item.resref, "restype": item.restype.extension, "type_id": item.restype.type_id, "size": len(data)})
    return sorted(resources, key=lambda item: (item["resref"], item["restype"]))


def _normal_room(value: Any) -> str:
    return str(value or "").strip().lower()


def _stock_rooms_from_lyt(lyt_data: bytes) -> list[str]:
    rooms: list[str] = []
    remaining = 0
    for line in lyt_data.decode("latin-1", errors="replace").splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        if tokens[0].lower() == "roomcount":
            remaining = int(tokens[1]) if len(tokens) > 1 and tokens[1].isdigit() else 0
            continue
        if remaining > 0 and len(tokens) >= 4:
            rooms.append(_normal_room(tokens[0]))
            remaining -= 1
    return rooms


def _vis_room_refs(vis_data: bytes) -> list[str]:
    rooms: list[str] = []
    for line in vis_data.decode("latin-1", errors="replace").splitlines():
        tokens = line.strip().split()
        if tokens:
            rooms.append(_normal_room(tokens[0]))
    return sorted(set(rooms))


def _are_room_names(are_data: bytes) -> list[str]:
    from pykotor.resource.formats.gff import read_gff

    root = read_gff(are_data).root
    rooms = root.get("Rooms")
    if not rooms:
        return []
    return [_normal_room(rooms.at(index).get("RoomName")) for index in range(len(rooms))]


def _room_resource_sets(archive: Any) -> dict[str, list[str]]:
    by_room: dict[str, set[str]] = {}
    for item in archive:
        restype = str(item.restype.extension).lower()
        if restype not in {"mdl", "mdx", "wok"}:
            continue
        resref = _normal_room(item.resref)
        by_room.setdefault(resref, set()).add(restype)
    return {room: sorted(types) for room, types in sorted(by_room.items())}


def _mdl_internal_room_refs(archive: Any) -> dict[str, list[str]]:
    from pykotor.resource.type import ResourceType

    internals: dict[str, list[str]] = {}
    for item in archive:
        if item.restype != ResourceType.MDL:
            continue
        resref = _normal_room(item.resref)
        data = archive.get(item.resref, item.restype) or b""
        strings = sorted(set(match.decode("ascii", errors="ignore").lower() for match in ROOM_NAME_RE.findall(data)))
        internals[resref] = strings
    return internals


def _room_identity_report(archive: Any, *, are_data: bytes, lyt_data: bytes, vis_data: bytes) -> dict[str, Any]:
    are_rooms = _are_room_names(are_data)
    lyt_rooms = _stock_rooms_from_lyt(lyt_data)
    vis_rooms = _vis_room_refs(vis_data)
    resources = _room_resource_sets(archive)
    mdl_internals = _mdl_internal_room_refs(archive)
    room_set = sorted(set(are_rooms) | set(lyt_rooms) | set(vis_rooms) | set(resources))
    blocking: list[str] = []
    warnings: list[str] = []
    missing_resource_types = {
        room: sorted({"mdl", "mdx", "wok"} - set(resources.get(room, [])))
        for room in room_set
        if sorted({"mdl", "mdx", "wok"} - set(resources.get(room, [])))
    }
    if missing_resource_types:
        blocking.append(f"Room resource sets are incomplete for {len(missing_resource_types)} room(s).")
    if sorted(set(are_rooms)) != sorted(set(lyt_rooms)):
        blocking.append("ARE room list does not match LYT room list.")
    if not set(vis_rooms).issubset(set(lyt_rooms)):
        blocking.append("VIS references room names that are not present in LYT.")
    for room, strings in mdl_internals.items():
        if room not in strings:
            internal_rooms = [value for value in strings if value.endswith(room[-4:]) or value.startswith("m02aa_") or value.startswith("grdev01_")]
            if internal_rooms:
                warnings.append(f"MDL resource {room}.mdl contains internal room refs {internal_rooms[:5]} instead of {room}.")
    return {
        "are_rooms": are_rooms,
        "lyt_rooms": lyt_rooms,
        "vis_rooms": vis_rooms,
        "room_resource_sets": resources,
        "mdl_internal_room_refs": mdl_internals,
        "missing_resource_types": missing_resource_types,
        "blocking_issues": blocking,
        "warnings": warnings,
        "coherent": not blocking and not warnings,
    }


def build_report(module_path: Path, game_root_dir: Path, stock_module_root: str, stock_rim_name: str) -> dict[str, Any]:
    _install_payload_paths()
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.erf.erf_auto import read_erf
    from pykotor.resource.formats.rim.rim_auto import read_rim
    from pykotor.resource.type import ResourceType

    diagnostic = read_erf(module_path)
    stock_rim = read_rim(game_root_dir / "Modules" / stock_rim_name)
    installation = Installation(str(game_root_dir))

    left_ifo_resref, left_ifo = _archive_get_any(diagnostic, ResourceType.IFO, ("module",))
    left_are_resref, left_are = _archive_get_any(diagnostic, ResourceType.ARE, ("grdev01", stock_module_root))
    left_git_resref, left_git = _archive_get_any(diagnostic, ResourceType.GIT, ("grdev01", stock_module_root))
    left_lyt_resref, left_lyt = _archive_get_any(diagnostic, ResourceType.LYT, ("grdev01", stock_module_root))
    left_vis_resref, left_vis = _archive_get_any(diagnostic, ResourceType.VIS, ("grdev01", stock_module_root))
    left_pth_resref, left_pth = _archive_get_any(diagnostic, ResourceType.PTH, ("grdev01", stock_module_root))

    right_ifo = _archive_get_any(stock_rim, ResourceType.IFO, ("module",))[1]
    right_are = _archive_get_any(stock_rim, ResourceType.ARE, (stock_module_root,))[1]
    right_git = _archive_get_any(stock_rim, ResourceType.GIT, (stock_module_root,))[1]
    right_lyt = _stock_resource(installation, stock_module_root, ResourceType.LYT)
    right_vis = _stock_resource(installation, stock_module_root, ResourceType.VIS)
    right_pth = _stock_resource(installation, stock_module_root, ResourceType.PTH)

    reports = {
        "ifo": _root_report("ifo", left_ifo, right_ifo),
        "are": _root_report("are", left_are, right_are),
        "git": _root_report("git", left_git, right_git),
        "lyt": _text_report(left_lyt, right_lyt),
        "vis": _text_report(left_vis, right_vis),
        "pth": _pth_report(left_pth, right_pth),
        "room_identity": _room_identity_report(diagnostic, are_data=left_are, lyt_data=left_lyt, vis_data=left_vis),
    }
    blocking = []
    for key in ("ifo", "are", "git"):
        missing = reports[key]["engine_shape"]["missing_expected_labels"]
        if missing:
            blocking.append(f"{key.upper()} missing expected engine labels: {', '.join(missing)}")
        mismatches = reports[key]["diff"]["type_mismatches"]
        if mismatches:
            blocking.append(f"{key.upper()} has {len(mismatches)} field type mismatch(es) versus stock {stock_module_root}.")
    blocking.extend(reports["room_identity"]["blocking_issues"])
    return {
        "ok": not blocking,
        "capability_stage": "diagnostic_metadata_comparison",
        "module_path": str(module_path),
        "game_root_dir": str(game_root_dir),
        "stock_module_root": stock_module_root,
        "stock_rim": stock_rim_name,
        "diagnostic_resource_roots": {
            "ifo": left_ifo_resref,
            "are": left_are_resref,
            "git": left_git_resref,
            "lyt": left_lyt_resref,
            "vis": left_vis_resref,
            "pth": left_pth_resref,
        },
        "resource_index": _resource_index(diagnostic),
        "reports": reports,
        "blocking_issues": blocking,
    }


def _print_human(report: dict[str, Any], output: Path) -> None:
    status = "OK" if report["ok"] else "WARN"
    print(f"grdev01 stock metadata comparison: {status}")
    print(f"Module: {report['module_path']}")
    print(f"Stock: {report['stock_module_root']} from {report['stock_rim']}")
    print(f"Report: {output}")
    roots = report.get("diagnostic_resource_roots", {})
    if roots:
        print("Diagnostic roots: " + ", ".join(f"{key}={value}" for key, value in roots.items()))
    if "reports" not in report:
        if report.get("blocking_issues"):
            print("")
            print("Blocking/shape issues:")
            for issue in report["blocking_issues"]:
                print(f"- {issue}")
        return
    for key in ("ifo", "are", "git"):
        item = report["reports"][key]
        diff = item["diff"]
        shape = item["engine_shape"]
        print(
            f"{key.upper()}: fields {diff['left_field_count']}/{diff['right_field_count']}, "
            f"missing expected {len(shape['missing_expected_labels'])}, "
            f"type mismatches {len(diff['type_mismatches'])}, "
            f"value diffs {len(diff['value_differences'])}"
        )
    for key in ("lyt", "vis"):
        item = report["reports"][key]
        print(f"{key.upper()}: same_text={item['same_text']} lines {item['left_line_count']}/{item['right_line_count']}")
    identity = report["reports"].get("room_identity", {})
    if identity:
        print(
            "Room identity: "
            f"coherent={identity.get('coherent')} "
            f"ARE={len(identity.get('are_rooms', []))} "
            f"LYT={len(identity.get('lyt_rooms', []))} "
            f"VIS={len(identity.get('vis_rooms', []))} "
            f"resources={len(identity.get('room_resource_sets', {}))} "
            f"warnings={len(identity.get('warnings', []))}"
        )
    pth = report["reports"]["pth"]
    print(f"PTH: points {pth['left_counts']['point_count']}/{pth['right_counts']['point_count']}, connections {pth['left_counts']['connection_count']}/{pth['right_counts']['connection_count']}")
    if report["blocking_issues"]:
        print("")
        print("Blocking/shape issues:")
        for issue in report["blocking_issues"]:
            print(f"- {issue}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    output = args.output or args.module_path.with_name("grdev01_stock_metadata_compare.json")
    try:
        report = build_report(args.module_path, args.game_root_dir, args.stock_module_root, args.stock_rim)
    except Exception as exc:
        report = {
            "ok": False,
            "capability_stage": "diagnostic_metadata_comparison",
            "module_path": str(args.module_path),
            "game_root_dir": str(args.game_root_dir),
            "stock_module_root": args.stock_module_root,
            "stock_rim": args.stock_rim,
            "blocking_issues": [f"Comparison failed: {exc}"],
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report, output)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
