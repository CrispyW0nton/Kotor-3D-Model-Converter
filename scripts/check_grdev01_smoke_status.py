"""Audit the current grdev01 Map Studio smoke-test status.

This command reads the proof manifest, checks the pack manifest, re-verifies
the staged `grdev01.mod` package, and optionally compares an installed module
copy in a KOTOR `Modules` folder.  It does not mark anything game-tested; it
only reports which proof gates are satisfied and which still need evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RUNTIME_RESOURCE_KEYS = (
    "grdev01.are",
    "grdev01.git",
    "module.ifo",
    "grdev01.pth",
    "grdev01.lyt",
    "grdev01.vis",
    "grdev01_room01.mdl",
    "grdev01_room01.mdx",
    "grdev01_room01.wok",
)
ROOT_RUNTIME_RESOURCE_KEYS = (
    "{root}.are",
    "{root}.git",
    "module.ifo",
    "{root}.pth",
    "{root}.lyt",
    "{root}.vis",
)
PROOF_EVIDENCE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}
PAYLOAD_PATHS = (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Rendering/Python",
    "native/GhostRigger.Core.Automation/Python/src",
    ".",
)
KOTORMCP_REQUIRED_RESOURCE_TYPES = ("ARE", "GIT", "IFO", "LYT", "PTH", "VIS", "MDL", "WOK")


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        required=True,
        help="Path to the grdev01 proof manifest written by install/staging.",
    )
    parser.add_argument(
        "--module-path",
        type=Path,
        default=None,
        help="Optional explicit grdev01.mod package path. Defaults to the proof manifest package path.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder used to check the installed grdev01.mod copy.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable status payload instead of a human summary.",
    )
    parser.add_argument(
        "--kotormcp",
        action="store_true",
        help="Also query KotorMCP against the installed game to confirm grdev01 is visible as a module.",
    )
    parser.add_argument(
        "--write-report",
        type=Path,
        default=None,
        help="Optional Markdown status report path for a modder-readable smoke-test handoff.",
    )
    return parser


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, f"{path} could not be read as JSON: {exc}"


def _resolve_local_path(path_text: str) -> Path:
    path = Path(str(path_text or ""))
    return path if path.is_absolute() else ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generic_archive_verification(module_path: Path) -> dict[str, Any]:
    _install_payload_paths()
    from pykotor.resource.formats.erf.erf_auto import read_erf  # noqa: WPS433

    archive = read_erf(module_path)
    resources: list[dict[str, Any]] = []
    model_roots: dict[str, set[str]] = {}
    parsed_gff: list[str] = []
    parsed_wok: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    for item in archive:
        extension = str(getattr(item.restype, "extension", "") or "").lower()
        key = f"{str(item.resref).lower()}.{extension}"
        data = bytes(archive.get(item.resref, item.restype) or b"")
        resources.append(
            {
                "resref": str(item.resref).lower(),
                "restype": extension,
                "key": key,
                "size": len(data),
                "offset": int(getattr(item, "offset", 0) or 0),
            }
        )
        if extension in {"mdl", "mdx"}:
            model_roots.setdefault(str(item.resref).lower(), set()).add(extension)
        if extension in {"are", "git", "ifo"}:
            try:
                _gff_root(data)
                parsed_gff.append(key)
            except Exception as exc:
                blocking.append(f"{key} could not be parsed as GFF: {exc}")
        if extension == "wok":
            try:
                _wok_summary(data)
                parsed_wok.append(key)
            except Exception as exc:
                warnings.append(f"{key} could not be parsed as WOK: {exc}")
    model_pairs = sorted(root for root, types in model_roots.items() if {"mdl", "mdx"}.issubset(types))
    return {
        "ok": not blocking,
        "code": "verified" if not blocking else "verification_failed",
        "message": (
            f"{module_path.name} package readback passed generic diagnostic checks."
            if not blocking
            else f"{module_path.name} package readback found {len(blocking)} blocking issue(s)."
        ),
        "module_path": str(module_path),
        "module_sha256": _sha256(module_path),
        "resources": resources,
        "resource_keys": sorted(resource["key"] for resource in resources),
        "parsed_gff": parsed_gff,
        "parsed_wok": parsed_wok,
        "model_pairs": model_pairs,
        "path_point_count": 0,
        "path_connection_count": 0,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _verification_summary(module_path: Path, proof: dict[str, Any] | None = None) -> dict[str, Any]:
    if not module_path.is_file():
        return {
            "ok": False,
            "code": "module_missing",
            "module_path": str(module_path),
            "blocking_issues": [f"Module package does not exist: {module_path}"],
        }
    if _room_profile(proof or {}) == "stock_rooms":
        return _generic_archive_verification(module_path)
    _install_payload_paths()
    from src.core.modules.dev_module_smoke import verify_dev_test_module_package  # noqa: WPS433

    result = verify_dev_test_module_package(module_path)
    resources = [
        {
            "resref": resource.resref,
            "restype": resource.restype,
            "key": f"{resource.resref}.{resource.restype}",
            "size": resource.size,
            "offset": resource.offset,
        }
        for resource in result.resources
    ]
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "module_path": result.module_path,
        "module_sha256": _sha256(module_path),
        "resources": resources,
        "resource_keys": sorted(resource["key"] for resource in resources),
        "parsed_gff": list(result.parsed_gff),
        "parsed_wok": list(result.parsed_wok),
        "model_pairs": list(result.model_pairs),
        "path_point_count": result.path_point_count,
        "path_connection_count": result.path_connection_count,
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
    }


def _room_profile(proof: dict[str, Any]) -> str:
    if str(proof.get("kind") or "") == "grdev01_renamed_stock_area_clone":
        return "stock_rooms"
    if str(proof.get("room_resref_mode") or "") == "stock_m02aa_rooms":
        return "stock_rooms"
    return "authored_room"


def _infer_module_path(proof: dict[str, Any]) -> Path | None:
    package = proof.get("package") if isinstance(proof.get("package"), dict) else {}
    summary = proof.get("summary") if isinstance(proof.get("summary"), dict) else {}
    for value in (
        package.get("module_path"),
        summary.get("module_path"),
        summary.get("installed_module_path"),
    ):
        if value:
            return Path(str(value))
    return None


def _room_names_from_payloads(*, payloads: dict[str, bytes], module_root: str, proof: dict[str, Any]) -> list[str]:
    root = str(module_root or "grdev01").lower()
    if _room_profile(proof) != "stock_rooms":
        return [f"{root}_room01"]
    rooms = _lyt_rooms(payloads.get(f"{root}.lyt", b""))
    if rooms:
        return rooms
    resource_rooms: set[str] = set()
    for key in payloads:
        if key.endswith((".mdl", ".mdx", ".wok")):
            resource_rooms.add(key.rsplit(".", 1)[0].lower())
    return sorted(resource_rooms)


def _required_runtime_keys(*, module_root: str, room_names: list[str]) -> list[str]:
    root = str(module_root or "grdev01").lower()
    keys = [key.format(root=root) for key in ROOT_RUNTIME_RESOURCE_KEYS]
    for room in room_names:
        room_root = str(room).lower()
        keys.extend([f"{room_root}.mdl", f"{room_root}.mdx", f"{room_root}.wok"])
    return keys


def _runtime_archive_summary(verification: dict[str, Any], *, module_path: Path, module_root: str, proof: dict[str, Any]) -> dict[str, Any]:
    resource_keys = set(verification.get("resource_keys") or [])
    payloads = _archive_payloads(module_path)
    room_names = _room_names_from_payloads(payloads=payloads, module_root=module_root, proof=proof)
    required_keys = _required_runtime_keys(module_root=module_root, room_names=room_names)
    missing = [key for key in required_keys if key not in resource_keys]
    return {
        "profile": _room_profile(proof),
        "required_resource_keys": required_keys,
        "missing_required_resource_keys": missing,
        "engine_ifo_key_ok": "module.ifo" in resource_keys,
        "room_names": room_names,
        "room_model_pair_ok": all(f"{room}.mdl" in resource_keys and f"{room}.mdx" in resource_keys for room in room_names),
        "walkmesh_key_ok": all(f"{room}.wok" in resource_keys for room in room_names),
        "layout_keys_ok": f"{str(module_root or 'grdev01').lower()}.lyt" in resource_keys and f"{str(module_root or 'grdev01').lower()}.vis" in resource_keys,
        "path_key_ok": f"{str(module_root or 'grdev01').lower()}.pth" in resource_keys,
    }


def _pack_manifest_template_dependencies(*, pack_manifest_path: str) -> list[dict[str, Any]]:
    if not pack_manifest_path:
        return []
    path = _resolve_local_path(pack_manifest_path)
    if not path.is_file():
        return []
    data, error = _load_json(path)
    if error:
        return []
    authored = data.get("map_studio_authored_module")
    if not isinstance(authored, dict):
        authored = data.get("map_studio_smoke_test")
    if not isinstance(authored, dict):
        return []
    dependencies = authored.get("gameplay_template_dependencies")
    if not isinstance(dependencies, list):
        return []
    result: list[dict[str, Any]] = []
    for item in dependencies:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "kind": str(item.get("kind") or ""),
                "index": int(item.get("index") or 0),
                "template_resref": str(item.get("template_resref") or "").lower(),
                "restype": str(item.get("restype") or "").lower(),
                "tag": str(item.get("tag") or ""),
                "packaged": bool(item.get("packaged")),
                "required": bool(item.get("required", True)),
                "status": str(item.get("status") or ""),
                "message": str(item.get("message") or ""),
            }
        )
    return result


def _resolve_game_template_dependencies(
    *,
    dependencies: list[dict[str, Any]],
    game_root_dir: str,
) -> dict[str, Any]:
    warnings: list[str] = []
    blocking: list[str] = []
    if not dependencies:
        return {
            "checked": False,
            "game_root_dir": str(game_root_dir or ""),
            "dependencies": [],
            "all_required_resolved": True,
            "warnings": [],
            "blocking_issues": [],
        }
    root = Path(str(game_root_dir or ""))
    can_check = bool(root and (root / "chitin.key").is_file())
    resolved_dependencies = [dict(item) for item in dependencies]
    if not can_check:
        warnings.append("Gameplay template dependencies were not resolved because no valid KOTOR game root was available.")
        for item in resolved_dependencies:
            item["resolved"] = None
            item["source_path"] = ""
            item["resolution_message"] = "Not checked; no valid KOTOR game root was available."
        return {
            "checked": False,
            "game_root_dir": str(game_root_dir or ""),
            "dependencies": resolved_dependencies,
            "all_required_resolved": False,
            "warnings": warnings,
            "blocking_issues": [],
        }
    try:
        _install_payload_paths()
        from pykotor.extract.file import ResourceQuery  # noqa: WPS433
        from pykotor.extract.installation import Installation  # noqa: WPS433
        from pykotor.resource.type import ResourceType  # noqa: WPS433

        installation = Installation(root)
        for item in resolved_dependencies:
            resref = str(item.get("template_resref") or "").lower()
            restype = str(item.get("restype") or "").upper()
            try:
                resource_type = getattr(ResourceType, restype)
                found = installation.find_one(ResourceQuery(resref, resource_type))
            except Exception as exc:
                found = None
                item["resolution_error"] = str(exc)
            ok = found is not None
            item["resolved"] = ok
            item["source_path"] = str(getattr(found, "filepath", "") or "") if found is not None else ""
            if ok:
                item["resolution_message"] = f"{resref}.{restype.lower()} resolves from the selected KOTOR install."
            else:
                item["resolution_message"] = f"{resref}.{restype.lower()} was not found in the selected KOTOR install."
                if bool(item.get("required", True)):
                    blocking.append(item["resolution_message"])
    except Exception as exc:
        warnings.append(f"Gameplay template dependency resolution failed for {root}: {exc}")
        for item in resolved_dependencies:
            item["resolved"] = None
            item["source_path"] = ""
            item["resolution_message"] = "Not checked; template dependency resolver failed."
        return {
            "checked": False,
            "game_root_dir": str(root),
            "dependencies": resolved_dependencies,
            "all_required_resolved": False,
            "warnings": warnings,
            "blocking_issues": blocking,
        }
    return {
        "checked": True,
        "game_root_dir": str(root),
        "dependencies": resolved_dependencies,
        "all_required_resolved": not blocking,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _archive_payloads(module_path: Path) -> dict[str, bytes]:
    if not module_path.is_file():
        return {}
    _install_payload_paths()
    from pykotor.resource.formats.erf.erf_auto import read_erf  # noqa: WPS433

    archive = read_erf(module_path)
    payloads: dict[str, bytes] = {}
    for item in archive:
        extension = str(getattr(item.restype, "extension", "") or "").lower()
        key = f"{str(item.resref).lower()}.{extension}"
        payloads[key] = bytes(archive.get(item.resref, item.restype) or b"")
    return payloads


def _gff_root(data: bytes) -> Any:
    from pykotor.resource.formats.gff import read_gff  # noqa: WPS433

    return read_gff(data).root


def _gff_string(root: Any, label: str) -> str:
    try:
        value = root.get(label)
    except Exception:
        return ""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _gff_float(root: Any, label: str) -> float | None:
    try:
        value = root.get(label)
    except Exception:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _gff_list_labels(root: Any, label: str, field: str) -> list[str]:
    try:
        values = root.get(label)
    except Exception:
        return []
    if not values:
        return []
    labels: list[str] = []
    try:
        count = len(values)
    except Exception:
        return []
    for index in range(count):
        try:
            labels.append(str(values.at(index).get(field)))
        except Exception:
            labels.append("")
    return labels


def _gff_list_count(root: Any, label: str) -> int:
    try:
        values = root.get(label)
    except Exception:
        return 0
    if not values:
        return 0
    try:
        return int(len(values))
    except Exception:
        return 0


def _lyt_rooms(data: bytes) -> list[str]:
    rooms: list[str] = []
    remaining = 0
    for line in data.decode("latin-1", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        tokens = text.split()
        if not tokens:
            continue
        keyword = tokens[0].lower()
        if keyword == "roomcount":
            remaining = int(tokens[1]) if len(tokens) > 1 else 0
            continue
        if keyword in {"beginlayout", "donelayout", "filedependancy", "trackcount", "obstaclecount", "doorhookcount"}:
            continue
        if remaining > 0 and len(tokens) >= 4:
            rooms.append(tokens[0].lower())
            remaining -= 1
    return rooms


def _wok_summary(data: bytes) -> dict[str, Any]:
    _install_payload_paths()
    from src.core.modules.module_format import WOKData  # noqa: WPS433

    wok = WOKData.from_bytes(data)
    faces = list(getattr(wok, "faces", ()) or ())
    surfaces: dict[str, int] = {}
    for face in faces:
        surface = str(getattr(face, "surface", ""))
        surfaces[surface] = surfaces.get(surface, 0) + 1
    return {
        "vertex_count": len(getattr(wok, "verts", ()) or ()),
        "face_count": len(faces),
        "walkable_face_count": int(wok.walkable_face_count()) if hasattr(wok, "walkable_face_count") else 0,
        "non_walk_face_count": int(wok.non_walk_face_count()) if hasattr(wok, "non_walk_face_count") else 0,
        "surface_counts": surfaces,
    }


def _module_contract_summary(*, module_path: Path, module_root: str, proof: dict[str, Any] | None = None) -> dict[str, Any]:
    proof = proof or {}
    payloads = _archive_payloads(module_path)
    blocking: list[str] = []
    warnings: list[str] = []
    root = str(module_root or "grdev01").lower()
    profile = _room_profile(proof)
    required_checks = {str(check) for check in (proof.get("acceptance_checks") or []) if str(check)}
    contract = proof.get("t2601_smoke_contract") if isinstance(proof.get("t2601_smoke_contract"), dict) else {}
    expected_placeables = contract.get("expected_placeables") if isinstance(contract, dict) else ()
    expects_placeable = "test_placeable_visible" in required_checks or bool(expected_placeables)
    expected_rooms = _room_names_from_payloads(payloads=payloads, module_root=root, proof=proof)
    expected_room = expected_rooms[0] if expected_rooms else f"{root}_room01"
    ifo: dict[str, Any] = {}
    are: dict[str, Any] = {}
    git: dict[str, Any] = {}
    layout: dict[str, Any] = {}
    walkmesh: dict[str, Any] = {}

    try:
        ifo_root = _gff_root(payloads.get("module.ifo", b""))
        area_names = [value.lower() for value in _gff_list_labels(ifo_root, "Mod_Area_list", "Area_Name")]
        ifo = {
            "entry_area": _gff_string(ifo_root, "Mod_Entry_Area").lower(),
            "area_list": area_names,
            "entry_position": {
                "x": _gff_float(ifo_root, "Mod_Entry_X"),
                "y": _gff_float(ifo_root, "Mod_Entry_Y"),
                "z": _gff_float(ifo_root, "Mod_Entry_Z"),
            },
            "module_id_hex": str(_gff_string(ifo_root, "Mod_ID")),
        }
        if ifo["entry_area"] != root:
            blocking.append(f"module.ifo Mod_Entry_Area is {ifo['entry_area']!r}; expected {root!r}.")
        if root not in area_names:
            blocking.append(f"module.ifo Mod_Area_list does not include {root!r}.")
    except Exception as exc:
        blocking.append(f"module.ifo contract summary failed: {exc}")

    try:
        are_root = _gff_root(payloads.get(f"{root}.are", b""))
        rooms = [value.lower() for value in _gff_list_labels(are_root, "Rooms", "RoomName")]
        are = {
            "tag": _gff_string(are_root, "Tag"),
            "name": _gff_string(are_root, "Name"),
            "rooms": rooms,
        }
        missing_are_rooms = [room for room in expected_rooms if room not in rooms]
        if missing_are_rooms:
            blocking.append(f"{root}.are Rooms does not include expected room(s): {', '.join(missing_are_rooms)}.")
    except Exception as exc:
        blocking.append(f"{root}.are contract summary failed: {exc}")

    try:
        git_root = _gff_root(payloads.get(f"{root}.git", b""))
        git = {
            "creatures": _gff_list_count(git_root, "Creature List"),
            "doors": _gff_list_count(git_root, "Door List"),
            "placeables": _gff_list_count(git_root, "Placeable List"),
            "waypoints": _gff_list_count(git_root, "WaypointList"),
            "triggers": _gff_list_count(git_root, "TriggerList"),
        }
        if profile != "stock_rooms" and expects_placeable and git["placeables"] < 1:
            warnings.append(f"{root}.git has no placeables; the authored smoke proof expects a visible test placeable.")
    except Exception as exc:
        blocking.append(f"{root}.git contract summary failed: {exc}")

    try:
        rooms = _lyt_rooms(payloads.get(f"{root}.lyt", b""))
        layout = {"rooms": rooms}
        missing_layout_rooms = [room for room in expected_rooms if room not in rooms]
        if missing_layout_rooms:
            blocking.append(f"{root}.lyt does not include expected room(s): {', '.join(missing_layout_rooms)}.")
    except Exception as exc:
        blocking.append(f"{root}.lyt contract summary failed: {exc}")

    try:
        per_room_walkmesh: dict[str, Any] = {}
        total_walkable = 0
        total_non_walk = 0
        total_faces = 0
        total_vertices = 0
        for room in expected_rooms:
            summary = _wok_summary(payloads.get(f"{room}.wok", b""))
            per_room_walkmesh[room] = summary
            total_walkable += int(summary.get("walkable_face_count") or 0)
            total_non_walk += int(summary.get("non_walk_face_count") or 0)
            total_faces += int(summary.get("face_count") or 0)
            total_vertices += int(summary.get("vertex_count") or 0)
            if profile != "stock_rooms" and int(summary.get("walkable_face_count") or 0) < 1:
                blocking.append(f"{room}.wok has no walkable faces.")
        walkmesh = {
            "rooms": per_room_walkmesh,
            "vertex_count": total_vertices,
            "face_count": total_faces,
            "walkable_face_count": total_walkable,
            "non_walk_face_count": total_non_walk,
        }
        if total_walkable < 1:
            blocking.append("No expected room WOK has walkable faces.")
    except Exception as exc:
        blocking.append(f"{expected_room}.wok contract summary failed: {exc}")

    return {
        "module_root": root,
        "profile": profile,
        "expected_room": expected_room,
        "expected_rooms": expected_rooms,
        "ifo": ifo,
        "are": are,
        "git": git,
        "layout": layout,
        "walkmesh": walkmesh,
        "warnings": warnings,
        "blocking_issues": blocking,
        "ok": not blocking,
    }


def _parse_kotormcp_payload(result: dict[str, Any]) -> dict[str, Any]:
    text = result.get("text") if isinstance(result, dict) else ""
    if not isinstance(text, str) or not text:
        return {"error": f"Unexpected KotorMCP response: {result!r}"}
    try:
        payload = json.loads(text)
    except Exception as exc:
        return {"error": f"KotorMCP response was not JSON: {exc}"}
    return payload if isinstance(payload, dict) else {"error": f"Unexpected KotorMCP payload: {payload!r}"}


def _run_kotormcp_module_tool(name: str, arguments: dict[str, Any], *, game_root_dir: str = "") -> dict[str, Any]:
    _install_payload_paths()
    import asyncio  # noqa: WPS433
    import os  # noqa: WPS433

    from kotormcp.tools import handle_tool  # noqa: WPS433

    game = str(arguments.get("game") or "").lower()
    env_name = "K2_PATH" if game == "k2" else "K1_PATH"
    previous_env = os.environ.get(env_name)
    if game_root_dir:
        os.environ[env_name] = game_root_dir
    try:
        result = asyncio.run(handle_tool(name, arguments))
    finally:
        if game_root_dir:
            if previous_env is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = previous_env
    return _parse_kotormcp_payload(result)


def _kotormcp_summary(*, enabled: bool, module_root: str, game: str, game_root_dir: str = "") -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "ok": False,
            "available": False,
            "module_root": module_root,
            "game": game,
            "resource_count": 0,
            "resources": [],
            "missing_required_types": [],
            "warnings": [],
            "blocking_issues": [],
        }

    game_arg = "k2" if str(game).upper() == "K2" else "k1"
    warnings: list[str] = []
    blocking: list[str] = []
    try:
        resources = _run_kotormcp_module_tool(
            "kotor_module_resources",
            {"game": game_arg, "module_root": module_root, "limit": 500, "offset": 0},
            game_root_dir=game_root_dir,
        )
        describe = _run_kotormcp_module_tool(
            "kotor_describe_module",
            {"game": game_arg, "module_root": module_root},
            game_root_dir=game_root_dir,
        )
    except Exception as exc:
        return {
            "checked": True,
            "ok": False,
            "available": False,
            "module_root": module_root,
            "game": game_arg.upper(),
            "resource_count": 0,
            "resources": [],
            "missing_required_types": list(KOTORMCP_REQUIRED_RESOURCE_TYPES),
            "warnings": [],
            "blocking_issues": [f"KotorMCP could not run: {exc}"],
        }

    if resources.get("error"):
        blocking.append(str(resources["error"]))
    if describe.get("error"):
        blocking.append(str(describe["error"]))

    items = resources.get("items") if isinstance(resources.get("items"), list) else []
    seen_types = {str(item.get("type") or "").upper() for item in items if isinstance(item, dict)}
    missing_types = [restype for restype in KOTORMCP_REQUIRED_RESOURCE_TYPES if restype not in seen_types]
    if missing_types:
        blocking.append("KotorMCP did not see required resource types: " + ", ".join(missing_types))

    area_info = describe.get("area_info") if isinstance(describe.get("area_info"), dict) else {}
    if area_info.get("error"):
        warnings.append(f"KotorMCP area summary warning: {area_info['error']}")

    model_buffer_alias = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("resref") or "").lower() == "grdev01_room01" and str(item.get("type") or "").upper() in {"MDX", "THG"}:
            model_buffer_alias = str(item.get("type") or "").upper()
            break

    return {
        "checked": True,
        "ok": not blocking,
        "available": True,
        "module_root": str(resources.get("module_root") or module_root),
        "game": game_arg.upper(),
        "resource_count": int(resources.get("total") or resources.get("count") or len(items)),
        "resources": items,
        "type_breakdown": describe.get("type_breakdown") if isinstance(describe.get("type_breakdown"), dict) else {},
        "missing_required_types": missing_types,
        "model_buffer_entry_type": model_buffer_alias,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _installed_summary(*, module_path: Path, proof: dict[str, Any], game_modules_dir: Path | None) -> dict[str, Any]:
    install = proof.get("install") if isinstance(proof.get("install"), dict) else {}
    installed_path_text = str(install.get("installed_module_path") or "")
    backup_path_text = str(install.get("backup_module_path") or "")
    if game_modules_dir is not None:
        installed_path_text = str(game_modules_dir / "grdev01.mod")
    if not installed_path_text:
        return {
            "checked": False,
            "exists": False,
            "matches_package": False,
            "installed_module_path": "",
            "backup_module_path": backup_path_text,
            "package_sha256": _sha256(module_path) if module_path.is_file() else "",
            "installed_sha256": "",
        }
    installed_path = Path(installed_path_text)
    exists = installed_path.is_file()
    matches = False
    package_sha = _sha256(module_path) if module_path.is_file() else ""
    installed_sha = _sha256(installed_path) if exists else ""
    if exists and module_path.is_file():
        matches = installed_sha == package_sha
    return {
        "checked": True,
        "exists": exists,
        "matches_package": matches,
        "installed_module_path": str(installed_path),
        "backup_module_path": backup_path_text,
        "package_sha256": package_sha,
        "installed_sha256": installed_sha,
    }


def _currentgame_cache_summary(
    *,
    module_root: str,
    module_path: Path,
    launch_handoff: dict[str, Any],
    game_modules_dir: Path | None,
) -> dict[str, Any]:
    game_root_text = str(launch_handoff.get("resolved_game_root_dir") or "")
    if not game_root_text and game_modules_dir is not None:
        game_root_text = str(game_modules_dir.parent)
    if not game_root_text:
        return {
            "checked": False,
            "exists": False,
            "matches_package": False,
            "path": "",
            "package_sha256": _sha256(module_path) if module_path.is_file() else "",
            "cache_sha256": "",
        }
    cache_path = Path(game_root_text) / "currentgame" / f"{module_root}.mod"
    exists = cache_path.is_file()
    package_sha = _sha256(module_path) if module_path.is_file() else ""
    cache_sha = _sha256(cache_path) if exists else ""
    return {
        "checked": True,
        "exists": exists,
        "matches_package": bool(exists and package_sha and cache_sha == package_sha),
        "path": str(cache_path),
        "package_sha256": package_sha,
        "cache_sha256": cache_sha,
    }


def _proof_summary(proof: dict[str, Any]) -> dict[str, Any]:
    required = list(proof.get("acceptance_checks") or [])
    game_test = proof.get("game_test") if isinstance(proof.get("game_test"), dict) else {}
    checks = game_test.get("checks") if isinstance(game_test.get("checks"), dict) else {}
    missing = list(game_test.get("missing_checks") or [name for name in required if not checks.get(name, False)])
    evidence_path = str(game_test.get("evidence_path") or "")
    evidence = Path(evidence_path) if evidence_path else None
    evidence_exists = bool(evidence is not None and evidence.is_file())
    evidence_accepted = bool(evidence_exists and evidence.stat().st_size > 0 and evidence.suffix.lower() in PROOF_EVIDENCE_EXTENSIONS)
    return {
        "game_tested": bool(proof.get("game_tested")),
        "manual_proof_required": bool(proof.get("manual_proof_required", True)),
        "required_checks": required,
        "checks": checks,
        "missing_checks": missing,
        "evidence_path": evidence_path,
        "evidence_exists": evidence_exists,
        "evidence_accepted": evidence_accepted,
    }


def _proof_command_flags(required_checks: list[str]) -> str:
    flag_by_check = {
        "module_loads_in_game": "--module-loads-in-game",
        "module_identity_matches_authored_resref": "--module-identity-matches-authored-resref",
        "player_spawns_on_floor": "--player-spawns-on-floor",
        "test_placeable_visible": "--test-placeable-visible",
        "player_can_walk_on_floor": "--player-can-walk-on-floor",
        "transition_pathing_sanity_confirmed": "--transition-pathing-sanity-confirmed",
        "no_inherited_base_game_geometry_or_scripted_movers": "--no-inherited-base-game-geometry-or-scripted-movers",
    }
    return " ".join(flag_by_check[name] for name in required_checks if name in flag_by_check)


def _runtime_verification_label(required_checks: list[str]) -> str:
    suffix = "/pathing" if "transition_pathing_sanity_confirmed" in required_checks else ""
    return (
        f"floor/placeable/walkability{suffix}"
        if "test_placeable_visible" in required_checks
        else f"floor/walkability{suffix}"
    )


def _diagnostic_variant_id(proof: dict[str, Any]) -> str:
    if _room_profile(proof) != "stock_rooms":
        return ""
    root_mode = str(proof.get("root_resource_mode") or "")
    dual_root = root_mode == "dual_grdev01_and_m02aa_roots"
    if str(proof.get("root_script_mode") or "") == "scriptless":
        if str(proof.get("git_mode") or "") == "minimal_with_test_placeable":
            if dual_root:
                return "renamed_root_scriptless_dual_minimal_git_placeable"
            return "renamed_root_scriptless_minimal_git_placeable"
        if dual_root:
            return "renamed_root_scriptless_dual_minimal_git"
        return "renamed_root_scriptless_minimal_git"
    if str(proof.get("git_mode") or "") == "minimal_with_test_placeable":
        return "renamed_root_minimal_git_placeable"
    return "renamed_root_minimal_git"


def _launch_handoff_summary(*, proof: dict[str, Any], proof_manifest: Path) -> dict[str, Any]:
    handoff = proof.get("launch_handoff") if isinstance(proof.get("launch_handoff"), dict) else {}
    warp_command = str(handoff.get("warp_command") or proof.get("warp_command") or "warp grdev01")
    game = str(handoff.get("game") or proof.get("game") or "K1").upper()
    proof_path = str(proof_manifest)
    task = str(proof.get("task") or "").strip().upper()
    recorder_script = str(handoff.get("proof_recording_script_path") or "")
    if task == "T2601":
        recorder_command_script = "scripts/record_grdev01_smoke_proof.py"
    else:
        recorder_command_script = "scripts/record_authored_module_game_proof.py"
    required_checks = [str(check) for check in list(proof.get("acceptance_checks") or []) if str(check)]
    proof_flags = _proof_command_flags(required_checks)
    diagnostic_variant = _diagnostic_variant_id(proof)
    if diagnostic_variant:
        recorder_command = (
            f'python "scripts/record_grdev01_runtime_diagnostic_outcome.py" '
            f"--variant {diagnostic_variant} --outcome <loaded|crashed|infinite_load> "
            f'--notes "<what happened in game>" --json'
        )
    else:
        recorder_command = (
            f'python "{recorder_command_script}" --proof-manifest "{proof_path}" '
            f"--evidence <screenshot-or-video> {proof_flags}"
        )
    return {
        "game": "K2" if game == "K2" else "K1",
        "warp_command": warp_command,
        "resolved_modules_dir": str(handoff.get("resolved_modules_dir") or ""),
        "resolved_game_root_dir": str(handoff.get("resolved_game_root_dir") or ""),
        "expected_executable_path": str(handoff.get("expected_executable_path") or ""),
        "launch_helper_command": str(handoff.get("launch_helper_command") or ""),
        "elevated_launch_script_path": str(handoff.get("elevated_launch_script_path") or ""),
        "evidence_capture_command": str(handoff.get("evidence_capture_command") or ""),
        "proof_recording_script_path": recorder_script,
        "proof_recording_command_template": recorder_command,
        "runtime_verification_label": _runtime_verification_label(required_checks),
        "diagnostic_variant_id": diagnostic_variant,
    }


def _derive_status(*, verification: dict[str, Any], proof: dict[str, Any], installed: dict[str, Any]) -> tuple[str, bool]:
    if not verification.get("ok"):
        return "package_blocked", False
    if proof.get("game_tested") and proof.get("evidence_accepted") and not proof.get("missing_checks"):
        return "game_tested", True
    if installed.get("checked") and installed.get("exists") and not installed.get("matches_package"):
        return "installed_copy_mismatch", False
    if installed.get("checked") and installed.get("exists"):
        return "installed_ready_for_game_test", False
    return "ready_for_manual_install", False


def build_status(
    *,
    proof_manifest: Path,
    module_path: Path | None = None,
    game_modules_dir: Path | None = None,
    use_kotormcp: bool = False,
) -> dict[str, Any]:
    blocking: list[str] = []
    warnings: list[str] = []
    proof: dict[str, Any] = {}
    proof_error = ""
    if proof_manifest.is_file():
        proof, proof_error = _load_json(proof_manifest)
    else:
        proof_error = f"Proof manifest does not exist: {proof_manifest}"
    if proof_error:
        blocking.append(proof_error)
    package = proof.get("package") if isinstance(proof.get("package"), dict) else {}
    inferred_module = _infer_module_path(proof)
    checked_module_path = module_path or inferred_module
    if checked_module_path is None:
        checked_module_path = Path("grdev01.mod")
        blocking.append("No module package path was supplied and the proof manifest did not name one.")
    verification = _verification_summary(checked_module_path, proof=proof)
    blocking.extend(verification.get("blocking_issues", []))
    module_root = str(proof.get("module_root") or proof.get("package_module_root") or package.get("module_root") or "grdev01")
    runtime_archive = _runtime_archive_summary(
        verification,
        module_path=checked_module_path,
        module_root=module_root,
        proof=proof,
    )
    if runtime_archive["missing_required_resource_keys"]:
        blocking.append(
            "Module package is missing KOTOR runtime resources: "
            + ", ".join(runtime_archive["missing_required_resource_keys"])
        )
    module_contract = _module_contract_summary(module_path=checked_module_path, module_root=module_root, proof=proof)
    blocking.extend(module_contract.get("blocking_issues", []))
    warnings.extend(module_contract.get("warnings", []))
    proof_state = _proof_summary(proof)
    launch_handoff = _launch_handoff_summary(proof=proof, proof_manifest=proof_manifest)
    template_dependencies = _resolve_game_template_dependencies(
        dependencies=_pack_manifest_template_dependencies(pack_manifest_path=str(package.get("pack_manifest_path") or "")),
        game_root_dir=str(launch_handoff.get("resolved_game_root_dir") or (game_modules_dir.parent if game_modules_dir else "")),
    )
    warnings.extend(template_dependencies.get("warnings", []))
    blocking.extend(template_dependencies.get("blocking_issues", []))
    installed = _installed_summary(module_path=checked_module_path, proof=proof, game_modules_dir=game_modules_dir)
    currentgame_cache = _currentgame_cache_summary(
        module_root=module_root,
        module_path=checked_module_path,
        launch_handoff=launch_handoff,
        game_modules_dir=game_modules_dir,
    )
    kotormcp = _kotormcp_summary(
        enabled=use_kotormcp,
        module_root=module_root,
        game=launch_handoff.get("game") or proof.get("game") or "K1",
        game_root_dir=launch_handoff.get("resolved_game_root_dir") or "",
    )
    if use_kotormcp and not kotormcp.get("ok"):
        blocking.extend(kotormcp.get("blocking_issues", []))
    if installed.get("checked") and not installed.get("exists"):
        warnings.append(f"Installed module copy was not found: {installed['installed_module_path']}")
    if installed.get("checked") and installed.get("exists") and not installed.get("matches_package"):
        blocking.append("Installed grdev01.mod does not match the staged package bytes.")
    if currentgame_cache.get("exists") and not currentgame_cache.get("matches_package"):
        blocking.append(
            "KOTOR currentgame cache contains a stale grdev01.mod. Quit KOTOR and move or delete "
            f"{currentgame_cache['path']} before retesting warp grdev01."
        )
    elif currentgame_cache.get("exists"):
        warnings.append(
            "KOTOR currentgame cache already contains grdev01.mod. Restart from a clean save if warp testing behaves strangely."
        )
    status, complete = _derive_status(verification=verification, proof=proof_state, installed=installed)
    if blocking and status != "package_blocked":
        complete = False
    ready_for_game_launch = (
        status == "installed_ready_for_game_test"
        and not blocking
        and verification.get("ok")
        and installed.get("matches_package")
        and not proof_state.get("game_tested")
    )
    next_action = "No action required; this package is recorded as game-tested."
    if not verification.get("ok") or blocking:
        next_action = "Fix blocking package/install issues before launching KOTOR."
    elif proof_state.get("game_tested") and not proof_state.get("missing_checks"):
        next_action = "No action required; this package is recorded as game-tested."
    elif ready_for_game_launch:
        game_label = "KOTOR II" if launch_handoff.get("game") == "K2" else "KOTOR"
        runtime_label = str(launch_handoff.get("runtime_verification_label") or "floor/walkability")
        if launch_handoff.get("diagnostic_variant_id"):
            next_action = (
                f"Launch {game_label}, run `{launch_handoff['warp_command']}`, then record whether the "
                "diagnostic loaded, crashed, or reached an infinite loading screen."
            )
        else:
            next_action = (
                f"Launch {game_label}, run `{launch_handoff['warp_command']}`, verify {runtime_label}, "
                "then capture evidence and run the proof recording command."
            )
            if launch_handoff.get("evidence_capture_command"):
                next_action = (
                    f"Launch {game_label}, run `{launch_handoff['warp_command']}`, verify {runtime_label}, "
                    "then run the evidence capture command."
                )
    elif not installed.get("checked") or not installed.get("exists"):
        next_action = "Install/copy grdev01.mod into a KOTOR Modules folder before the game test."
    elif installed.get("checked") and not installed.get("matches_package"):
        next_action = "Reinstall the staged grdev01.mod so the live Modules copy matches the verified package."
    return {
        "ok": complete,
        "status": status if not blocking else ("game_tested" if complete else status),
        "proof_manifest_path": str(proof_manifest),
        "module_path": str(checked_module_path),
        "pack_manifest_path": str(package.get("pack_manifest_path") or ""),
        "package_verification": verification,
        "runtime_archive": runtime_archive,
        "module_contract": module_contract,
        "template_dependencies": template_dependencies,
        "proof": proof_state,
        "installed": installed,
        "currentgame_cache": currentgame_cache,
        "kotormcp": kotormcp,
        "launch_handoff": launch_handoff,
        "ready_for_game_launch": ready_for_game_launch,
        "next_action": next_action,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _print_human_summary(status: dict[str, Any]) -> None:
    print(f"grdev01 smoke status: {status['status']}")
    print(f"Module package: {status['module_path']}")
    print(f"Proof manifest: {status['proof_manifest_path']}")
    if status["pack_manifest_path"]:
        print(f"Pack manifest: {status['pack_manifest_path']}")
    print(f"Package readback: {status['package_verification']['code']}")
    print(f"Engine module IFO key: {status['runtime_archive']['engine_ifo_key_ok']}")
    contract = status.get("module_contract") or {}
    if contract:
        ifo = contract.get("ifo") or {}
        git = contract.get("git") or {}
        walkmesh = contract.get("walkmesh") or {}
        print(f"Module contract: {contract.get('ok')}")
        print(f"Entry area: {ifo.get('entry_area') or '(unknown)'}")
        print(f"Area list: {', '.join(ifo.get('area_list') or []) or '(empty)'}")
        print(f"Expected room: {contract.get('expected_room') or '(unknown)'}")
        print(f"GIT placeables: {git.get('placeables', 0)}")
        print(f"WOK walkable faces: {walkmesh.get('walkable_face_count', 0)}")
    installed = status["installed"]
    if installed["checked"]:
        print(f"Installed copy: {installed['installed_module_path']}")
        print(f"Installed copy matches package: {installed['matches_package']}")
        if installed["backup_module_path"]:
            print(f"Previous module backup: {installed['backup_module_path']}")
    currentgame_cache = status.get("currentgame_cache") or {}
    if currentgame_cache.get("checked"):
        print(f"Currentgame cache: {currentgame_cache.get('path') or '(not resolved)'}")
        print(f"Currentgame cache exists: {currentgame_cache.get('exists')}")
        if currentgame_cache.get("exists"):
            print(f"Currentgame cache matches package: {currentgame_cache.get('matches_package')}")
    kotormcp = status.get("kotormcp") or {}
    if kotormcp.get("checked"):
        print(f"KotorMCP module check: {kotormcp['ok']} ({kotormcp['resource_count']} resource(s))")
        if kotormcp.get("model_buffer_entry_type"):
            print(f"KotorMCP model buffer entry type: {kotormcp['model_buffer_entry_type']}")
    templates = status.get("template_dependencies") or {}
    if templates.get("dependencies"):
        print(f"Gameplay template check: {templates.get('checked')} ({len(templates.get('dependencies') or [])} dependency/dependencies)")
        print(f"Required templates resolved: {templates.get('all_required_resolved')}")
        for dependency in templates.get("dependencies") or []:
            label = f"{dependency.get('template_resref')}.{dependency.get('restype')}"
            print(f"- {label}: {dependency.get('resolution_message') or dependency.get('message')}")
    print(f"Ready for game launch: {status['ready_for_game_launch']}")
    handoff = status.get("launch_handoff") or {}
    if handoff.get("game"):
        print(f"Game: {handoff['game']}")
    if handoff.get("launch_helper_command"):
        print(f"Launch helper: {handoff['launch_helper_command']}")
    if handoff.get("elevated_launch_script_path"):
        print(f"Elevated launch script: {handoff['elevated_launch_script_path']}")
    if handoff.get("evidence_capture_command"):
        print(f"Evidence capture command: {handoff['evidence_capture_command']}")
    if handoff.get("proof_recording_script_path"):
        print(f"Proof recorder script: {handoff['proof_recording_script_path']}")
    if handoff.get("proof_recording_command_template"):
        print(f"Proof recorder command: {handoff['proof_recording_command_template']}")
    print(f"Next action: {status['next_action']}")
    proof = status["proof"]
    print(f"Game-tested: {proof['game_tested']}")
    print(f"Manual proof required: {proof['manual_proof_required']}")
    if proof["evidence_path"]:
        print(f"Evidence: {proof['evidence_path']} (exists: {proof['evidence_exists']})")
    if proof["missing_checks"]:
        print("")
        print("Missing proof checks:")
        for check in proof["missing_checks"]:
            print(f"- {check}")
    if status["warnings"]:
        print("")
        print("Warnings:")
        for warning in status["warnings"]:
            print(f"- {warning}")
    if kotormcp.get("warnings"):
        print("")
        print("KotorMCP warnings:")
        for warning in kotormcp["warnings"]:
            print(f"- {warning}")
    if templates.get("warnings"):
        print("")
        print("Template dependency warnings:")
        for warning in templates["warnings"]:
            print(f"- {warning}")
    if status["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in status["blocking_issues"]:
            print(f"- {issue}")


def _bool_mark(value: bool) -> str:
    return "OK" if value else "NO"


def _write_markdown_report(status: dict[str, Any], output_path: Path) -> None:
    contract = status.get("module_contract") or {}
    ifo = contract.get("ifo") or {}
    are = contract.get("are") or {}
    git = contract.get("git") or {}
    layout = contract.get("layout") or {}
    walkmesh = contract.get("walkmesh") or {}
    runtime = status.get("runtime_archive") or {}
    proof = status.get("proof") or {}
    installed = status.get("installed") or {}
    handoff = status.get("launch_handoff") or {}
    currentgame = status.get("currentgame_cache") or {}
    templates = status.get("template_dependencies") or {}
    lines = [
        "# grdev01 Smoke Status",
        "",
        "This report is a Map Studio smoke-test handoff. It is not proof that the module is game-tested; that requires a real KOTOR run.",
        "",
        "## Package",
        "",
        f"- Status: `{status.get('status', '')}`",
        f"- Module package: `{status.get('module_path', '')}`",
        f"- Package SHA256: `{status.get('package_verification', {}).get('module_sha256', '')}`",
        f"- Installed copy: `{installed.get('installed_module_path') or '(not installed)'}`",
        f"- Installed matches package: {_bool_mark(bool(installed.get('matches_package')))}",
        f"- Currentgame cache: `{currentgame.get('path') or '(not resolved)'}`",
        f"- Currentgame cache exists: {_bool_mark(bool(currentgame.get('exists')))}",
        "",
        "## Engine Handoff Contract",
        "",
        f"- Module root: `{contract.get('module_root', '')}`",
        f"- IFO entry area: `{ifo.get('entry_area', '')}`",
        f"- IFO area list: `{', '.join(ifo.get('area_list') or [])}`",
        f"- Entry position: `{ifo.get('entry_position', {})}`",
        f"- Mod_ID: `{ifo.get('module_id_hex', '')}`",
        f"- ARE rooms: `{', '.join(are.get('rooms') or [])}`",
        f"- LYT rooms: `{', '.join(layout.get('rooms') or [])}`",
        f"- Expected room: `{contract.get('expected_room', '')}`",
        f"- GIT placeables: `{git.get('placeables', 0)}`",
        f"- GIT waypoints: `{git.get('waypoints', 0)}`",
        f"- WOK vertices/faces: `{walkmesh.get('vertex_count', 0)} / {walkmesh.get('face_count', 0)}`",
        f"- WOK walkable/non-walk: `{walkmesh.get('walkable_face_count', 0)} / {walkmesh.get('non_walk_face_count', 0)}`",
        f"- Contract OK: {_bool_mark(bool(contract.get('ok')))}",
        "",
        "## Runtime Resources",
        "",
    ]
    missing = list(runtime.get("missing_required_resource_keys") or [])
    for key in runtime.get("required_resource_keys") or []:
        lines.append(f"- [{' ' if key in missing else 'x'}] `{key}`")
    if templates.get("dependencies"):
        lines.extend(
            [
                "",
                "## Gameplay Template Dependencies",
                "",
                f"- Checked against game root: {_bool_mark(bool(templates.get('checked')))}",
                f"- Required templates resolved: {_bool_mark(bool(templates.get('all_required_resolved')))}",
                f"- Game root: `{templates.get('game_root_dir') or '(not resolved)'}`",
                "",
            ]
        )
        for dependency in templates.get("dependencies") or []:
            label = f"{dependency.get('template_resref')}.{dependency.get('restype')}"
            resolved = dependency.get("resolved")
            mark = "?" if resolved is None else ("x" if resolved else " ")
            message = dependency.get("resolution_message") or dependency.get("message") or ""
            lines.append(f"- [{mark}] `{label}` - {message}")
    lines.extend(
        [
            "",
            "## In-Game Proof Required",
            "",
            f"- Warp command: `{handoff.get('warp_command') or 'warp grdev01'}`",
            f"- Ready for launch: {_bool_mark(bool(status.get('ready_for_game_launch'))) }",
            f"- Game-tested: {_bool_mark(bool(proof.get('game_tested'))) }",
            f"- Evidence accepted: {_bool_mark(bool(proof.get('evidence_accepted'))) }",
            "",
        ]
    )
    missing_checks = list(proof.get("missing_checks") or [])
    if missing_checks:
        lines.append("Missing proof checks:")
        for check in missing_checks:
            lines.append(f"- [ ] {check}")
        lines.append("")
    lines.extend(
        [
            "## Next Action",
            "",
            str(status.get("next_action") or ""),
        ]
    )
    if status.get("blocking_issues"):
        lines.extend(["", "## Blocking Issues", ""])
        for issue in status["blocking_issues"]:
            lines.append(f"- {issue}")
    if status.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in status["warnings"]:
            lines.append(f"- {warning}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    status = build_status(
        proof_manifest=args.proof_manifest,
        module_path=args.module_path,
        game_modules_dir=args.game_modules_dir,
        use_kotormcp=args.kotormcp,
    )
    if args.write_report is not None:
        _write_markdown_report(status, args.write_report)
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        _print_human_summary(status)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
