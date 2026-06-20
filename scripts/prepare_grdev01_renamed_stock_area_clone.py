"""Install a grdev01 diagnostic package with stock rooms and renamed root.

This crash-isolation fixture sits between the full stock-area clone and the
fully authored Map Studio room:

* room MDL/MDX/WOK assets stay stock `m02aa_*` resources;
* LYT/VIS/PTH text/path resources are stock `m02aa` bytes but packaged as
  `grdev01`;
* ARE/GIT are stock module bytes packaged as `grdev01`;
* module.ifo entry handoff is renamed to `grdev01`.

If this package loads, KOTOR accepts a renamed module root with stock rooms and
the next suspect is authored room geometry/metadata. If it crashes, investigate
module-root/package handoff before editing generated MDL/WOK again.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATHS = (
    "native/GhostRigger.Domain.Core.Modules/Python",
    "native/GhostRigger.Domain.Core.Level/Python",
    "native/GhostRigger.Domain.Core.Game/Python",
    "native/GhostRigger.Domain.Core.Scene/Python",
    "native/GhostRigger.Domain.Core.Walkmesh/Python",
    "native/GhostRigger.Domain.Core.Geometry/Python",
    "native/GhostRigger.Domain.Core.Camera/Python",
    "native/GhostRigger.Domain.Core.Math/Python",
    ".",
)

PACKAGE_MODULE_ROOT = "grdev01"
STOCK_MODULE_ROOT = "m02aa"
STOCK_RIM = "tar_m02aa.rim"
DIAGNOSTIC_MODULE_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "ghostrigger.k1.module.grdev01").bytes
TEST_PLACEABLE_TEMPLATE = "plc_bench"
TEST_PLACEABLE_TAG = "grdev01_test_bench"
TEST_PLACEABLE_POSITION = (94.95486450195312, 132.73565673828125, 0.0)


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "map_studio" / "grdev01_renamed_stock_area_clone",
        help="Directory that receives the renamed stock-area clone package.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        help="KOTOR install root used to read stock tar_m02aa resources.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder. Omit this to only stage the diagnostic package.",
    )
    parser.add_argument("--install", action="store_true", help="Copy the staged package to <Modules>/grdev01.mod.")
    parser.add_argument(
        "--rename-room-resrefs",
        action="store_true",
        help=(
            "Also rename stock room resource refs and LYT/VIS room text from m02aa_* "
            "to grdev01_* while keeping stock room bytes."
        ),
    )
    parser.add_argument(
        "--include-stock-roots",
        action="store_true",
        help=(
            "Also package exact stock m02aa ARE/GIT/LYT/VIS/PTH root resources next to the "
            "renamed grdev01 roots. This isolates mixed module-root/resource lookup behavior."
        ),
    )
    parser.add_argument(
        "--unique-module-id",
        action="store_true",
        help=(
            "Replace stock m02aa Mod_ID with a deterministic GhostRigger grdev01 UUID. "
            "Use this when isolating autosave/load identity collisions."
        ),
    )
    parser.add_argument(
        "--minimal-git",
        action="store_true",
        help=(
            "Keep stock ARE/LYT/VIS/PTH/room geometry, but strip dynamic GIT object lists "
            "so warp testing isolates module bootstrap and room loading from stock scripts, "
            "doors, creatures, triggers, cameras, stores, sounds, placeables, and waypoints."
        ),
    )
    parser.add_argument(
        "--minimal-git-test-placeable",
        action="store_true",
        help=(
            "When used with --minimal-git, add one known-safe plc_bench test placeable near the stock entry point. "
            "This keeps the diagnostic small while checking the visible-object requirement."
        ),
    )
    parser.add_argument(
        "--scriptless-root",
        action="store_true",
        help=(
            "Clear stock module/area event scripts and rename neutral root labels. "
            "Use this after a stripped-GIT package crashes to isolate Taris script handoff from module loading."
        ),
    )
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Back up and replace an existing grdev01.mod when --install is used.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _resource_bytes(result: Any, label: str) -> bytes:
    data = getattr(result, "data", result)
    if callable(data):
        data = data()
    data = bytes(data or b"")
    if not data:
        raise ValueError(f"Stock resource {label} has no bytes.")
    return data


def _installation_resource(installation: Any, resref: str, restype: Any) -> bytes:
    result = installation.resource(resref, restype)
    if result is None:
        raise FileNotFoundError(f"Could not find stock resource {resref}.{restype.extension}.")
    return _resource_bytes(result, f"{resref}.{restype.extension}")


def _rim_resource(rim: Any, resref: str, restype: Any) -> bytes:
    data = rim.get(resref, restype)
    if not data:
        raise FileNotFoundError(f"Could not find stock RIM resource {resref}.{restype.extension}.")
    return bytes(data)


def _stock_rooms_from_lyt(lyt_bytes: bytes) -> list[str]:
    rooms: list[str] = []
    remaining = 0
    for line in lyt_bytes.decode("latin-1", errors="replace").splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        keyword = tokens[0].lower()
        if keyword == "roomcount":
            remaining = int(tokens[1]) if len(tokens) > 1 else 0
            continue
        if remaining > 0 and len(tokens) >= 4:
            rooms.append(tokens[0].lower())
            remaining -= 1
    return rooms


_MODULE_EVENT_SCRIPT_FIELDS = (
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
)

_AREA_EVENT_SCRIPT_FIELDS = (
    "OnEnter",
    "OnExit",
    "OnHeartbeat",
    "OnUserDefined",
)


def _rename_stock_ifo(data: bytes, *, unique_module_id: bool = False, scriptless_root: bool = False) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    gff = read_gff(data)
    root = gff.root
    if unique_module_id:
        root.set_binary("Mod_ID", DIAGNOSTIC_MODULE_ID)
    root.set_resref("Mod_Entry_Area", PACKAGE_MODULE_ROOT)
    root.set_string("Mod_VO_ID", PACKAGE_MODULE_ROOT)
    root.set_string("Mod_Tag", PACKAGE_MODULE_ROOT)
    if scriptless_root:
        for field in _MODULE_EVENT_SCRIPT_FIELDS:
            if root.exists(field):
                root.set_resref(field, "")
    try:
        area_list = root.get("Mod_Area_list")
        if len(area_list) > 0:
            area_list.at(0).set_resref("Area_Name", PACKAGE_MODULE_ROOT)
    except Exception:
        pass
    return bytes_gff(gff)


def _rename_stock_are(data: bytes, *, scriptless_root: bool = False) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    gff = read_gff(data)
    root = gff.root
    root.set_string("Tag", PACKAGE_MODULE_ROOT)
    if scriptless_root:
        for field in _AREA_EVENT_SCRIPT_FIELDS:
            if root.exists(field):
                root.set_resref(field, "")
    return bytes_gff(gff)


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


def _minimal_stock_git(data: bytes, *, add_test_placeable: bool = False) -> bytes:
    """Strip runtime object lists from a stock GIT while preserving root shape."""

    from pykotor.resource.formats.gff import bytes_gff, read_gff
    from pykotor.resource.formats.gff.gff_data import GFFList

    gff = read_gff(data)
    root = gff.root
    for field in _RUNTIME_GIT_LIST_FIELDS:
        if root.exists(field):
            root.set_list(field, GFFList())
    if not root.exists("UseTemplates"):
        root.set_uint8("UseTemplates", 1)
    if add_test_placeable:
        placeables = root.get("Placeable List")
        if placeables is None:
            placeables = GFFList()
            root.set_list("Placeable List", placeables)
        item = placeables.add(9)
        item.set_resref("TemplateResRef", TEST_PLACEABLE_TEMPLATE)
        item.set_string("Tag", TEST_PLACEABLE_TAG)
        item.set_single("X", float(TEST_PLACEABLE_POSITION[0]))
        item.set_single("Y", float(TEST_PLACEABLE_POSITION[1]))
        item.set_single("Z", float(TEST_PLACEABLE_POSITION[2]))
        item.set_single("Bearing", 0.0)
    return bytes_gff(gff)


def _renamed_room_name(stock_room: str) -> str:
    return re.sub(re.escape(STOCK_MODULE_ROOT), PACKAGE_MODULE_ROOT, stock_room, flags=re.IGNORECASE).lower()


def _rewrite_stock_room_text(data: bytes) -> bytes:
    text = data.decode("latin-1", errors="replace")
    text = re.sub(re.escape(STOCK_MODULE_ROOT), PACKAGE_MODULE_ROOT, text, flags=re.IGNORECASE)
    return text.encode("latin-1")


def _rename_stock_are_rooms(data: bytes, *, scriptless_root: bool = False) -> bytes:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    gff = read_gff(data)
    root = gff.root
    root.set_string("Tag", PACKAGE_MODULE_ROOT)
    if scriptless_root:
        for field in _AREA_EVENT_SCRIPT_FIELDS:
            if root.exists(field):
                root.set_resref(field, "")
    rooms = root.get("Rooms")
    if rooms:
        for index in range(len(rooms)):
            room = rooms.at(index)
            room_name = str(room.get("RoomName") or "")
            if room_name:
                room.set_resref("RoomName", _renamed_room_name(room_name))
    return bytes_gff(gff)


def _load_renamed_stock_module_resources(
    game_root_dir: Path,
    *,
    rename_room_resrefs: bool = False,
    include_stock_roots: bool = False,
    unique_module_id: bool = False,
    minimal_git: bool = False,
    minimal_git_test_placeable: bool = False,
    scriptless_root: bool = False,
) -> tuple[list[Any], list[str]]:
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.rim.rim_auto import read_rim
    from pykotor.resource.type import ResourceType
    from src.core.modules.custom_module_packager import PackagedModuleResource

    installation = Installation(str(game_root_dir))
    rim = read_rim(game_root_dir / "Modules" / STOCK_RIM)
    if minimal_git_test_placeable:
        _installation_resource(installation, TEST_PLACEABLE_TEMPLATE, ResourceType.UTP)
    lyt = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.LYT)
    vis = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.VIS)
    pth = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.PTH)
    rooms = _stock_rooms_from_lyt(lyt)
    package_rooms = [_renamed_room_name(room) for room in rooms] if rename_room_resrefs else list(rooms)
    package_are = (
        _rename_stock_are_rooms(
            _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.ARE),
            scriptless_root=scriptless_root,
        )
        if rename_room_resrefs
        else _rename_stock_are(_rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.ARE), scriptless_root=scriptless_root)
    )
    package_git = _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.GIT)
    if minimal_git:
        package_git = _minimal_stock_git(package_git, add_test_placeable=minimal_git_test_placeable)
    package_lyt = _rewrite_stock_room_text(lyt) if rename_room_resrefs else lyt
    package_vis = _rewrite_stock_room_text(vis) if rename_room_resrefs else vis
    resources = [
        PackagedModuleResource(
            PACKAGE_MODULE_ROOT,
            "are",
            package_are,
            source=f"stock-renamed:{STOCK_RIM}",
        ),
        PackagedModuleResource(
            PACKAGE_MODULE_ROOT,
            "git",
            package_git,
            source=f"stock-minimal-git:{STOCK_RIM}" if minimal_git else f"stock-renamed:{STOCK_RIM}",
        ),
        PackagedModuleResource(
            "module",
            "ifo",
            _rename_stock_ifo(
                _rim_resource(rim, "module", ResourceType.IFO),
                unique_module_id=unique_module_id,
                scriptless_root=scriptless_root,
            ),
            source=f"stock-renamed:{STOCK_RIM}",
        ),
        PackagedModuleResource(PACKAGE_MODULE_ROOT, "lyt", package_lyt, source="stock-renamed:bif"),
        PackagedModuleResource(PACKAGE_MODULE_ROOT, "vis", package_vis, source="stock-renamed:bif"),
        PackagedModuleResource(PACKAGE_MODULE_ROOT, "pth", pth, source="stock-renamed:bif"),
    ]
    if include_stock_roots:
        resources.extend(
            [
                PackagedModuleResource(
                    STOCK_MODULE_ROOT,
                    "are",
                    _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.ARE),
                    source=f"stock-dual-root:{STOCK_RIM}",
                ),
                PackagedModuleResource(
                    STOCK_MODULE_ROOT,
                    "git",
                    _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.GIT),
                    source=f"stock-dual-root:{STOCK_RIM}",
                ),
                PackagedModuleResource(STOCK_MODULE_ROOT, "lyt", lyt, source="stock-dual-root:bif"),
                PackagedModuleResource(STOCK_MODULE_ROOT, "vis", vis, source="stock-dual-root:bif"),
                PackagedModuleResource(STOCK_MODULE_ROOT, "pth", pth, source="stock-dual-root:bif"),
            ]
        )
    for stock_room, package_room in zip(rooms, package_rooms):
        resources.extend(
            [
                PackagedModuleResource(package_room, "mdl", _installation_resource(installation, stock_room, ResourceType.MDL), source="stock:bif"),
                PackagedModuleResource(package_room, "mdx", _installation_resource(installation, stock_room, ResourceType.MDX), source="stock:bif"),
                PackagedModuleResource(package_room, "wok", _installation_resource(installation, stock_room, ResourceType.WOK), source="stock:bif"),
            ]
        )
    return resources, package_rooms


def _next_backup_path(path: Path) -> Path:
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _install_module(module_path: Path, modules_dir: Path, *, overwrite: bool) -> tuple[str, str, list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []
    modules_dir.mkdir(parents=True, exist_ok=True)
    destination = modules_dir / "grdev01.mod"
    backup_path = ""
    if destination.exists():
        if not overwrite:
            blocking.append(f"{destination} already exists. Re-run with --overwrite-module to replace it.")
            return "", "", warnings, blocking
        backup = _next_backup_path(destination)
        shutil.copy2(destination, backup)
        backup_path = str(backup)
        warnings.append(f"Backed up existing {destination.name} to {backup}.")
    shutil.copy2(module_path, destination)
    return str(destination), backup_path, warnings, blocking


def _readback(module_path: str) -> dict[str, Any]:
    from pykotor.resource.formats.erf.erf_auto import read_erf

    path = Path(module_path)
    erf = read_erf(path)
    resources = []
    for item in erf:
        data = erf.get(item.resref, item.restype) or b""
        resources.append(
            {
                "resref": str(item.resref),
                "restype": item.restype.extension,
                "type_id": item.restype.type_id,
                "size": len(data),
            }
        )
    return {
        "path": str(path),
        "size": path.stat().st_size if path.exists() else 0,
        "resource_count": len(resources),
        "resources": sorted(resources, key=lambda item: (item["resref"], item["restype"])),
    }


def _manifest(
    summary: dict[str, Any],
    rooms: list[str],
    readback: dict[str, Any],
    *,
    rename_room_resrefs: bool,
    include_stock_roots: bool,
    unique_module_id: bool,
    minimal_git: bool,
    minimal_git_test_placeable: bool,
    scriptless_root: bool,
) -> dict[str, Any]:
    git_mode = (
        "minimal_with_test_placeable"
        if minimal_git and minimal_git_test_placeable
        else "minimal_no_runtime_objects"
        if minimal_git
        else "stock_runtime_objects"
    )
    diagnostic_question = (
        "If this loads and the test bench is visible, KOTOR accepts the renamed module handoff, stock room geometry, and a single safe authored placement. "
        "If the no-placeable minimal-GIT diagnostic loads but this crashes, investigate authored GIT placement/template handling."
        if minimal_git and minimal_git_test_placeable
        else (
        "If this loads, KOTOR accepts the renamed module handoff and stock room geometry when dynamic GIT objects are stripped. "
        "If the full stock-GIT clone crashes but this loads, investigate object/template/script/transition references before generated room geometry."
        if minimal_git
        else (
            "If this loads, KOTOR accepts the renamed module handoff when both grdev01 and stock m02aa root resources are present. "
            "If it crashes, investigate the complete room rename contract or custom module bootstrap path before generated MDL/WOK."
        )
        )
    )
    return {
        "kind": "grdev01_renamed_stock_area_clone",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "package_module_root": PACKAGE_MODULE_ROOT,
        "stock_module_root": STOCK_MODULE_ROOT,
        "source_module": STOCK_RIM,
        "room_resref_mode": "renamed_grdev01_rooms" if rename_room_resrefs else "stock_m02aa_rooms",
        "root_resource_mode": "dual_grdev01_and_m02aa_roots" if include_stock_roots else "grdev01_roots_only",
        "module_id_mode": "unique_grdev01_uuid" if unique_module_id else "stock_m02aa_mod_id",
        "git_mode": git_mode,
        "root_script_mode": "scriptless" if scriptless_root else "stock_event_scripts",
        "test_placeable": (
            {
                "template": TEST_PLACEABLE_TEMPLATE,
                "tag": TEST_PLACEABLE_TAG,
                "position": list(TEST_PLACEABLE_POSITION),
            }
            if minimal_git and minimal_git_test_placeable
            else None
        ),
        "diagnostic_module_id_hex": DIAGNOSTIC_MODULE_ID.hex() if unique_module_id else "",
        "packaged_rooms": rooms,
        "diagnostic_question": diagnostic_question,
        "summary": summary,
        "readback": readback,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 renamed stock-area clone: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Package: {summary['module_path'] or '(not written)'}")
    print(f"Manifest: {summary['manifest_path'] or '(not written)'}")
    if summary["installed_module_path"]:
        print(f"Installed module: {summary['installed_module_path']}")
    if summary["backup_module_path"]:
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

    from src.core.modules.custom_module_packager import CustomModulePackRequest, package_custom_module

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    blocking: list[str] = []
    rooms: list[str] = []
    readback: dict[str, Any] = {}
    installed_path = ""
    backup_path = ""
    module_path = ""
    try:
        if args.rename_room_resrefs:
            warnings.append(
                "Room resource names and LYT/VIS room text are renamed, but stock MDL internals still reference m02aa_* names; "
                "use this mode only as an experimental resource-graph diagnostic."
            )
        if args.include_stock_roots:
            warnings.append(
                "Dual-root mode packages both grdev01 and m02aa root resources; this is a crash-isolation fixture, "
                "not a final authored-module layout."
            )
        if args.unique_module_id:
            warnings.append(
                "Mod_ID was changed from the stock m02aa value to a deterministic GhostRigger grdev01 UUID "
                "to isolate autosave/load identity collisions."
            )
        if args.minimal_git:
            warnings.append(
                "Dynamic stock GIT object lists were stripped. This diagnostic tests room/module load safety, "
                "not stock gameplay object, trigger, door, creature, camera, or waypoint behavior."
            )
        if args.minimal_git_test_placeable and not args.minimal_git:
            blocking.append("--minimal-git-test-placeable requires --minimal-git.")
        if args.minimal_git and args.minimal_git_test_placeable:
            warnings.append(
                f"A single {TEST_PLACEABLE_TEMPLATE} test placeable was added near the stock entry point to test visible authored placement."
            )
        if args.scriptless_root:
            warnings.append(
                "Stock module and area event scripts were cleared, including the Taris OnEnter script, "
                "to isolate module loading from stock runtime script assumptions."
            )
        if not blocking:
            resources, rooms = _load_renamed_stock_module_resources(
                args.game_root_dir,
                rename_room_resrefs=bool(args.rename_room_resrefs),
                include_stock_roots=bool(args.include_stock_roots),
                unique_module_id=bool(args.unique_module_id),
                minimal_git=bool(args.minimal_git),
                minimal_git_test_placeable=bool(args.minimal_git_test_placeable),
                scriptless_root=bool(args.scriptless_root),
            )
            package_result = package_custom_module(
                SimpleNamespace(resources={}),
                CustomModulePackRequest(
                    module_root=PACKAGE_MODULE_ROOT,
                    game="K1",
                    output_dir=str(output_dir),
                    archive_mode="mod",
                    create_backups=True,
                    write_loose_resources=True,
                    include_reference_check=False,
                    include_wok_check=False,
                    strict=True,
                ),
                resources=resources,
            )
            warnings.extend(package_result.warnings)
            blocking.extend(package_result.blocking_issues)
            module_path = package_result.module_path
            if module_path:
                readback = _readback(module_path)
            if package_result.ok and not blocking and args.install:
                if not args.game_modules_dir:
                    blocking.append("--install requires --game-modules-dir.")
                else:
                    installed_path, backup_path, install_warnings, install_blocking = _install_module(
                        Path(module_path),
                        args.game_modules_dir,
                        overwrite=bool(args.overwrite_module),
                    )
                    warnings.extend(install_warnings)
                    blocking.extend(install_blocking)
            ok = bool(package_result.ok) and not blocking
        else:
            ok = False
    except Exception as exc:
        ok = False
        blocking.append(f"Renamed stock-area clone package failed: {exc}")

    if installed_path:
        next_actions = [
            "Launch KOTOR and run `warp grdev01` with this renamed-root stock-area clone.",
            "If it loads, reinstall the corrected generated Map Studio room package next.",
            "If it crashes, investigate module-root/package handoff before generated room geometry.",
        ]
    else:
        next_actions = [
            "Install this package as `Modules/grdev01.mod` when ready to test the renamed-root diagnostic.",
            "Run `warp grdev01` and use the result to isolate module-root handoff vs generated geometry.",
        ]
    summary = {
        "ok": ok,
        "code": "prepared" if ok else "blocked",
        "message": (
            "Renamed stock-area clone diagnostic package is installed for in-game warp testing."
            if ok and installed_path
            else "Renamed stock-area clone diagnostic package is staged."
            if ok
            else "Renamed stock-area clone diagnostic package is not ready; resolve blocking issues first."
        ),
        "output_dir": str(output_dir),
        "game_root_dir": str(args.game_root_dir),
        "module_path": module_path,
        "installed_module_path": installed_path,
        "backup_module_path": backup_path,
        "manifest_path": str(output_dir / "grdev01_renamed_stock_area_clone_manifest.json"),
        "room_resref_mode": "renamed_grdev01_rooms" if args.rename_room_resrefs else "stock_m02aa_rooms",
        "root_resource_mode": "dual_grdev01_and_m02aa_roots" if args.include_stock_roots else "grdev01_roots_only",
        "module_id_mode": "unique_grdev01_uuid" if args.unique_module_id else "stock_m02aa_mod_id",
        "root_script_mode": "scriptless" if args.scriptless_root else "stock_event_scripts",
        "git_mode": (
            "minimal_with_test_placeable"
            if args.minimal_git and args.minimal_git_test_placeable
            else "minimal_no_runtime_objects"
            if args.minimal_git
            else "stock_runtime_objects"
        ),
        "diagnostic_module_id_hex": DIAGNOSTIC_MODULE_ID.hex() if args.unique_module_id else "",
        "stock_room_count": len(rooms),
        "resource_count": int(readback.get("resource_count") or 0),
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": next_actions,
    }
    manifest_path = output_dir / "grdev01_renamed_stock_area_clone_manifest.json"
    manifest_path.write_text(
        json.dumps(
            _manifest(
                summary,
                rooms,
                readback,
                rename_room_resrefs=bool(args.rename_room_resrefs),
                include_stock_roots=bool(args.include_stock_roots),
                unique_module_id=bool(args.unique_module_id),
                minimal_git=bool(args.minimal_git),
                minimal_git_test_placeable=bool(args.minimal_git_test_placeable),
                scriptless_root=bool(args.scriptless_root),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
