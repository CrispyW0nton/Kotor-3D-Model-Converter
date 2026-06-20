"""Strip PLCaa to a quiet static floor/walls lab module.

PLCaa is useful as a dev-test space because its visible room geometry lives in
the base game resources, while the installed PLCaa.mod overlay carries the
runtime module metadata and busy GIT/script behavior.  This helper preserves the
module shell but removes dynamic gameplay lists and event scripts so the module
can be used as a calm level-design fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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

DEFAULT_GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
DEFAULT_PACKAGE_MODULE_ROOT = "ShaolinTestsMap"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "map_studio" / "shaolintestsmap_static_lab"
SOURCE_AREA_ROOT = "plcaa"
STATIC_LAB_ROOM_MODEL_ROOT = "plcaa"
STATIC_LAB_ROOM_REMOVE_PREFIXES = (
    "BoxSpin",
    "Box",
    "GeoSphere",
    "ScriptLoop",
    "ConeRef",
)

GIT_DYNAMIC_LISTS = (
    "CameraList",
    "Creature List",
    "Door List",
    "TriggerList",
    "Encounter List",
    "SoundList",
    "StoreList",
    "List",
    "Placeable List",
    "WaypointList",
)

IFO_EVENT_FIELDS = (
    "Mod_OnHeartbeat",
    "Mod_OnModLoad",
    "Mod_OnModStart",
    "Mod_OnClientEntr",
    "Mod_OnClientLeav",
    "Mod_OnActvtItem",
    "Mod_OnAcquirItem",
    "Mod_OnUsrDefined",
    "Mod_OnUnAqreItem",
    "Mod_OnPlrDeath",
    "Mod_OnPlrDying",
    "Mod_OnPlrLvlUp",
    "Mod_OnSpawnBtnDn",
    "Mod_OnPlrRest",
    "Mod_StartMovie",
)

ARE_EVENT_FIELDS = (
    "OnEnter",
    "OnExit",
    "OnHeartbeat",
    "OnUserDefined",
)


@dataclass(frozen=True)
class ResourceBytes:
    resref: str
    restype: str
    data: bytes
    source: str


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-module",
        type=Path,
        default=DEFAULT_GAME_ROOT / "Modules" / "PLCaa.mod",
        help="PLCaa.mod overlay to strip.",
    )
    parser.add_argument(
        "--game-root",
        type=Path,
        default=DEFAULT_GAME_ROOT,
        help="KOTOR install root used to resolve the baked PLCaa room MDL/MDX from models.bif.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for staged resources, package, and manifest.",
    )
    parser.add_argument(
        "--module-root",
        default=DEFAULT_PACKAGE_MODULE_ROOT,
        help="Warpable module filename/root to write. The source room area remains PLCaa unless renamed by a later slice.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder to install the stripped PLCaa.mod.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Back up and replace PLCaa.mod in --game-modules-dir.",
    )
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Allow replacing an existing installed PLCaa.mod when --install is used.",
    )
    parser.add_argument(
        "--include-risky-pruned-room-model",
        action="store_true",
        help=(
            "Experimental: embed a binary-patched PLCaa room MDL/MDX with demo nodes hidden. "
            "This is not enabled by default because it has crashed KOTOR in live tests."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _normalise_resref(value: Any, *, default: str = DEFAULT_PACKAGE_MODULE_ROOT) -> str:
    text = "".join(ch for ch in str(value or default).strip() if ch.isalnum() or ch == "_")
    return (text or default)[:16]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_data(resource: Any) -> bytes:
    data = getattr(resource, "data", b"")
    if callable(data):
        data = data()
    return bytes(data or b"")


def _next_backup_path(path: Path) -> Path:
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _gff_list_count(root: Any, label: str) -> int:
    try:
        values = root.acquire(label, None)
        return len(values) if values is not None else 0
    except Exception:
        return 0


def _resref_text(root: Any, label: str) -> str:
    try:
        value = root.acquire(label, "")
        return "" if value is None else str(value)
    except Exception:
        return ""


def _resource_map(source_module: Path) -> dict[tuple[str, str], ResourceBytes]:
    from pykotor.extract.capsule import LazyCapsule

    capsule = LazyCapsule(source_module)
    resources: dict[tuple[str, str], ResourceBytes] = {}
    for item in capsule:
        restype = item.restype().extension.lower()
        resref = item.resref().lower()
        resources[(resref, restype)] = ResourceBytes(
            resref=resref,
            restype=restype,
            data=bytes(item.data() or b""),
            source=str(source_module),
        )
    return resources


def _strip_git(data: bytes) -> tuple[bytes, dict[str, Any]]:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFFList

    gff = read_gff(data)
    before = {label: _gff_list_count(gff.root, label) for label in GIT_DYNAMIC_LISTS}
    for label in GIT_DYNAMIC_LISTS:
        gff.root.set_list(label, GFFList())
    after = {label: _gff_list_count(gff.root, label) for label in GIT_DYNAMIC_LISTS}
    return bytes_gff(gff), {"dynamic_lists_before": before, "dynamic_lists_after": after}


def _clear_script_fields(
    data: bytes,
    fields: tuple[str, ...],
    *,
    locstring_updates: dict[str, str] | None = None,
    string_updates: dict[str, str] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.common.language import LocalizedString

    gff = read_gff(data)
    before = {label: _resref_text(gff.root, label) for label in fields}
    for label in fields:
        gff.root.set_resref(label, "")
    for label, text in (locstring_updates or {}).items():
        gff.root.set_locstring(label, LocalizedString.from_english(text))
    for label, text in (string_updates or {}).items():
        gff.root.set_string(label, text)
    after = {label: _resref_text(gff.root, label) for label in fields}
    return bytes_gff(gff), {
        "scripts_before": before,
        "scripts_after": after,
        "locstring_updates": dict(locstring_updates or {}),
        "string_updates": dict(string_updates or {}),
    }


def _is_static_lab_demo_visual_node(node_name: str) -> bool:
    return any(node_name.startswith(prefix) for prefix in STATIC_LAB_ROOM_REMOVE_PREFIXES)


def _prune_static_lab_demo_visual_nodes(node: Any) -> list[str]:
    removed: list[str] = []
    kept: list[Any] = []
    for child in list(getattr(node, "children", []) or []):
        name = str(getattr(child, "name", "") or "")
        if _is_static_lab_demo_visual_node(name):
            removed.append(name)
            continue
        removed.extend(_prune_static_lab_demo_visual_nodes(child))
        kept.append(child)
    node.children = kept
    return removed


def _strip_room_model_to_static_lab(game_root: Path) -> tuple[ResourceBytes, ResourceBytes, dict[str, Any]]:
    from pykotor.extract.installation import Installation, SearchLocation
    from pykotor.resource.type import ResourceType

    from src.core.mdl.mdl_reader_wrapper import read_mdl_safe

    install = Installation(game_root)
    mdl_resource = install.resource(STATIC_LAB_ROOM_MODEL_ROOT, ResourceType.MDL, order=[SearchLocation.CHITIN])
    mdx_resource = install.resource(STATIC_LAB_ROOM_MODEL_ROOT, ResourceType.MDX, order=[SearchLocation.CHITIN])
    if mdl_resource is None or mdx_resource is None:
        raise RuntimeError(
            f"Could not resolve {STATIC_LAB_ROOM_MODEL_ROOT}.mdl/mdx from {game_root}. "
            "The stripped PLCaa lab needs the stock room model as a pruning source."
        )

    source_mdl = _resource_data(mdl_resource)
    source_mdx = _resource_data(mdx_resource)
    model = read_mdl_safe(
        source_mdl,
        source_ext=source_mdx,
        size_ext=len(source_mdx),
        file_format=ResourceType.MDL,
    )
    nodes_before = [str(getattr(node, "name", "") or "") for node in model.all_nodes()]
    animations_before = [str(getattr(anim, "name", "") or "") for anim in getattr(model, "animations", []) or []]
    root_children = list(getattr(getattr(model, "root", None), "children", []) or [])
    root_child_names = [str(getattr(child, "name", "") or "") for child in root_children]
    keep_root_child_count = 0
    for child in root_children:
        child_name = str(getattr(child, "name", "") or "")
        descendants = [str(getattr(node, "name", "") or "") for node in [child, *list(getattr(child, "descendants", lambda: [])())]]
        if child_name == "PLCaaa" or any(_is_static_lab_demo_visual_node(name) for name in descendants):
            break
        keep_root_child_count += 1
    if keep_root_child_count <= 0:
        raise RuntimeError("Could not identify a safe static PLCaa room child prefix to keep.")

    # Keep BioWare's original room-model binary layout.  Re-serialising PLCaa
    # through general-purpose writers changes node classes/controller blocks
    # enough to crash the game.  For this fixture we only shorten the root child
    # pointer count to the static room prefix and disable local room animations.
    mdl_out = bytearray(source_mdl)
    base = 12
    root_offset = struct.unpack_from("<I", mdl_out, base + 40)[0]
    root_abs = base + root_offset
    original_root_child_count = struct.unpack_from("<I", mdl_out, root_abs + 48)[0]
    if keep_root_child_count > original_root_child_count:
        raise RuntimeError("Static PLCaa room keep-count exceeds the stock root child count.")
    struct.pack_into("<II", mdl_out, root_abs + 48, keep_root_child_count, keep_root_child_count)
    original_animation_count = struct.unpack_from("<I", mdl_out, base + 92)[0]
    original_animation_count2 = struct.unpack_from("<I", mdl_out, base + 96)[0]
    struct.pack_into("<II", mdl_out, base + 92, 0, 0)
    mdx_out = bytes(source_mdx)

    readback = read_mdl_safe(
        bytes(mdl_out),
        source_ext=bytes(mdx_out),
        size_ext=len(mdx_out),
        file_format=ResourceType.MDL,
    )
    nodes_after = [str(getattr(node, "name", "") or "") for node in readback.all_nodes()]
    leaked = [name for name in nodes_after if _is_static_lab_demo_visual_node(name)]
    if leaked:
        raise RuntimeError(f"Cleaned PLCaa room model still contains demo visual nodes: {', '.join(leaked)}")

    return (
        ResourceBytes(
            STATIC_LAB_ROOM_MODEL_ROOT,
            "mdl",
            bytes(mdl_out),
            "plcaa_static_lab:pruned_room_model",
        ),
        ResourceBytes(
            STATIC_LAB_ROOM_MODEL_ROOT,
            "mdx",
            bytes(mdx_out),
            "plcaa_static_lab:pruned_room_model",
        ),
        {
            "source_mdl_size": len(source_mdl),
            "source_mdx_size": len(source_mdx),
            "cleaned_mdl_size": len(mdl_out),
            "cleaned_mdx_size": len(mdx_out),
            "nodes_before": nodes_before,
            "nodes_after_readback": nodes_after,
            "root_child_names_before": root_child_names,
            "root_child_count_before": original_root_child_count,
            "root_child_count_after": keep_root_child_count,
            "removed_visual_nodes": [name for name in nodes_before if _is_static_lab_demo_visual_node(name)],
            "stripped_controller_nodes": [],
            "animations_before": animations_before,
            "animation_count_before": original_animation_count,
            "animation_count2_before": original_animation_count2,
            "animations_after": [],
            "patch_strategy": "binary_root_child_filter",
            "source_mdl": str(getattr(mdl_resource, "filepath", "")),
            "source_mdx": str(getattr(mdx_resource, "filepath", "")),
        },
    )


def _stage_resource(resource: ResourceBytes, output_dir: Path) -> dict[str, Any]:
    path = output_dir / "source" / "resources" / f"{resource.resref}.{resource.restype}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resource.data)
    return {
        "resref": resource.resref,
        "restype": resource.restype,
        "path": str(path),
        "size": len(resource.data),
        "sha256": _sha256(resource.data),
        "source": resource.source,
    }


def _install_module(
    module_path: Path,
    modules_dir: Path,
    *,
    module_root: str,
    overwrite: bool,
) -> tuple[str, str, str, str, list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []
    modules_dir.mkdir(parents=True, exist_ok=True)
    destination = modules_dir / f"{module_root}.mod"
    backup_path = ""
    currentgame_path = ""
    currentgame_backup_path = ""
    if destination.exists():
        if not overwrite:
            blocking.append(f"{destination} already exists. Re-run with --overwrite-module to replace it.")
            return "", "", "", "", warnings, blocking
        backup = _next_backup_path(destination)
        shutil.copy2(destination, backup)
        backup_path = str(backup)
        warnings.append(f"Backed up existing {destination.name} to {backup}.")
    shutil.copy2(module_path, destination)
    currentgame_destination = modules_dir.parent / "currentgame" / f"{module_root}.mod"
    if currentgame_destination.exists():
        currentgame_backup = _next_backup_path(currentgame_destination)
        shutil.copy2(currentgame_destination, currentgame_backup)
        shutil.copy2(destination, currentgame_destination)
        currentgame_path = str(currentgame_destination)
        currentgame_backup_path = str(currentgame_backup)
        warnings.append(
            f"Refreshed stale currentgame cache copy {currentgame_destination.name}; "
            f"backup written to {currentgame_backup}."
        )
    return str(destination), backup_path, currentgame_path, currentgame_backup_path, warnings, blocking


def _build_static_plcaa(
    source_module: Path,
    output_dir: Path,
    *,
    module_root: str,
    game_root: Path,
    include_pruned_room_model: bool = False,
) -> dict[str, Any]:
    from src.core.modules.module_save_pipeline import (
        ModuleReplacementResource,
        ModuleSaveRequest,
        save_module_package,
    )

    resources = _resource_map(source_module)
    blocking: list[str] = []
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {}
    replacements: list[Any] = []
    required = ((SOURCE_AREA_ROOT, "git"), (SOURCE_AREA_ROOT, "are"), ("module", "ifo"))
    for key in required:
        if key not in resources:
            blocking.append(f"PLCaa overlay is missing required resource {key[0]}.{key[1]}.")
    if blocking:
        return {
            "ok": False,
            "code": "missing_required_resources",
            "warnings": warnings,
            "blocking_issues": blocking,
        }

    git_data, git_diag = _strip_git(resources[(SOURCE_AREA_ROOT, "git")].data)
    are_data, are_diag = _clear_script_fields(
        resources[(SOURCE_AREA_ROOT, "are")].data,
        ARE_EVENT_FIELDS,
        locstring_updates={"Name": module_root},
        string_updates={"Tag": module_root},
    )
    ifo_data, ifo_diag = _clear_script_fields(
        resources[("module", "ifo")].data,
        IFO_EVENT_FIELDS,
        locstring_updates={
            "Mod_Name": module_root,
            "Mod_Description": f"{module_root}: GhostRigger stripped PLCaa static level-design test map.",
        },
        string_updates={"Mod_Tag": module_root},
    )
    diagnostics["git"] = git_diag
    diagnostics["are"] = are_diag
    diagnostics["ifo"] = ifo_diag
    stripped = {
        (SOURCE_AREA_ROOT, "git"): ResourceBytes(SOURCE_AREA_ROOT, "git", git_data, "plcaa_static_lab:stripped_git"),
        (SOURCE_AREA_ROOT, "are"): ResourceBytes(SOURCE_AREA_ROOT, "are", are_data, "plcaa_static_lab:scriptless_are"),
        ("module", "ifo"): ResourceBytes("module", "ifo", ifo_data, "plcaa_static_lab:scriptless_ifo"),
    }
    if include_pruned_room_model:
        room_mdl, room_mdx, room_diag = _strip_room_model_to_static_lab(game_root)
        diagnostics["room_model"] = room_diag
        stripped[(room_mdl.resref, room_mdl.restype)] = room_mdl
        stripped[(room_mdx.resref, room_mdx.restype)] = room_mdx
    else:
        diagnostics["room_model"] = {
            "patch_strategy": "disabled_by_default",
            "reason": (
                "PLCaa demo shapes are baked into the stock room model. "
                "The prior binary child-filter package passed readback but crashed KOTOR, "
                "so this strip helper now leaves room-model resources out by default."
            ),
        }
        warnings.append(
            "PLCaa baked demo shapes are not removed by this safe strip path; use an authored static-lab module "
            "for a clean floor/walls test map."
        )
    for resource in stripped.values():
        replacements.append(ModuleReplacementResource(resource.resref, resource.restype, resource.data, source=resource.source))

    save_result = save_module_package(
        object(),
        ModuleSaveRequest(
            module_root=module_root,
            game="K1",
            output_dir=str(output_dir / "install" / "Modules"),
            archive_mode="mod",
            create_backups=True,
            write_manifest=True,
        ),
        replacements=replacements,
    )
    staged_resources = [_stage_resource(resource, output_dir) for resource in stripped.values()]
    blocking.extend(list(save_result.blocking_issues))
    warnings.extend(list(save_result.warnings))
    module_path = ""
    if save_result.archives:
        module_path = save_result.archives[0].path
    return {
        "ok": bool(save_result.ok) and not blocking,
        "code": "staged" if save_result.ok and not blocking else "blocked",
        "module_path": module_path,
        "module_root": module_root,
        "source_area_root": SOURCE_AREA_ROOT,
        "source_room_model_root": STATIC_LAB_ROOM_MODEL_ROOT,
        "save_manifest_path": save_result.manifest_path,
        "staged_resources": staged_resources,
        "diagnostics": diagnostics,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _summary(
    *,
    source_module: Path,
    game_root: Path,
    output_dir: Path,
    module_root: str,
    build: dict[str, Any],
    installed_module_path: str,
    backup_module_path: str,
    currentgame_module_path: str,
    currentgame_backup_module_path: str,
    install_warnings: list[str],
    install_blocking: list[str],
) -> dict[str, Any]:
    blocking = list(build.get("blocking_issues", [])) + list(install_blocking)
    warnings = list(build.get("warnings", [])) + list(install_warnings)
    module_path = str(build.get("module_path") or "")
    installed_hash = _file_sha256(Path(installed_module_path)) if installed_module_path else ""
    currentgame_hash = _file_sha256(Path(currentgame_module_path)) if currentgame_module_path else ""
    staged_hash = _file_sha256(Path(module_path)) if module_path else ""
    ok = (
        bool(build.get("ok"))
        and not blocking
        and (not installed_module_path or installed_hash == staged_hash)
        and (not currentgame_module_path or currentgame_hash == staged_hash)
    )
    return {
        "kind": "plcaa_static_lab_strip",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": ok,
        "code": "installed" if ok and installed_module_path else "staged" if ok else "blocked",
        "message": (
            "Installed stripped PLCaa static lab module."
            if ok and installed_module_path
            else "Staged stripped PLCaa static lab module."
            if ok
            else "PLCaa static lab strip is blocked."
        ),
        "source_module": str(source_module),
        "game_root": str(game_root),
        "source_sha256": _file_sha256(source_module) if source_module.exists() else "",
        "module_root": module_root,
        "source_area_root": SOURCE_AREA_ROOT,
        "source_room_model_root": STATIC_LAB_ROOM_MODEL_ROOT,
        "warp_command": f"warp {module_root}",
        "output_dir": str(output_dir),
        "module_path": module_path,
        "module_sha256": staged_hash,
        "save_manifest_path": str(build.get("save_manifest_path") or ""),
        "installed_module_path": installed_module_path,
        "installed_sha256": installed_hash,
        "backup_module_path": backup_module_path,
        "currentgame_module_path": currentgame_module_path,
        "currentgame_sha256": currentgame_hash,
        "currentgame_backup_module_path": currentgame_backup_module_path,
        "staged_resources": list(build.get("staged_resources", [])),
        "diagnostics": dict(build.get("diagnostics", {})),
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": [
            f"Launch KOTOR and run `warp {module_root}`.",
            "Confirm the PLCaa floor/walls load with no spawned creatures, placeables, moving scripts, area triggers, sounds, or cameras.",
            "If the room still has moving behavior, inspect global scripts or baked room model animation rather than the PLCaa overlay GIT.",
        ],
    }


def _print_human(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"PLCaa static lab strip: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Module root: {summary.get('module_root', '')}")
    print(f"Warp command: {summary.get('warp_command', '')}")
    print(f"Source: {summary['source_module']}")
    print(f"Package: {summary['module_path'] or '(not written)'}")
    if summary.get("installed_module_path"):
        print(f"Installed: {summary['installed_module_path']}")
    if summary.get("backup_module_path"):
        print(f"Backup: {summary['backup_module_path']}")
    if summary["warnings"]:
        print("\nWarnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")
    if summary["blocking_issues"]:
        print("\nBlocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")
    print("\nNext actions:")
    for action in summary["next_actions"]:
        print(f"- {action}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _install_payload_paths()
    output_dir = args.output_dir
    source_module = args.source_module
    module_root = _normalise_resref(args.module_root)
    installed = ""
    backup = ""
    currentgame_installed = ""
    currentgame_backup = ""
    install_warnings: list[str] = []
    install_blocking: list[str] = []
    if not source_module.exists():
        summary = {
            "ok": False,
            "code": "missing_source",
            "message": f"Source PLCaa.mod does not exist: {source_module}",
            "source_module": str(source_module),
            "output_dir": str(output_dir),
            "module_path": "",
            "installed_module_path": "",
            "backup_module_path": "",
            "warnings": [],
            "blocking_issues": [f"Source PLCaa.mod does not exist: {source_module}"],
            "next_actions": [],
        }
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human(summary)
        return 1

    build = _build_static_plcaa(
        source_module,
        output_dir,
        module_root=module_root,
        game_root=args.game_root,
        include_pruned_room_model=bool(args.include_risky_pruned_room_model),
    )
    module_path = Path(str(build.get("module_path") or ""))
    if args.install and not build.get("blocking_issues"):
        if not args.game_modules_dir:
            install_blocking.append("--install requires --game-modules-dir.")
        elif module_path.exists():
            installed, backup, currentgame_installed, currentgame_backup, install_warnings, install_blocking = _install_module(
                module_path,
                args.game_modules_dir,
                module_root=module_root,
                overwrite=bool(args.overwrite_module),
            )
    summary = _summary(
        source_module=source_module,
        game_root=args.game_root,
        output_dir=output_dir,
        module_root=module_root,
        build=build,
        installed_module_path=installed,
        backup_module_path=backup,
        currentgame_module_path=currentgame_installed,
        currentgame_backup_module_path=currentgame_backup,
        install_warnings=install_warnings,
        install_blocking=install_blocking,
    )
    manifest_path = output_dir / "plcaa_static_lab_manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary["manifest_path"] = str(manifest_path)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
