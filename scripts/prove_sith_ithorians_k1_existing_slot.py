"""Capture an actual KOTOR 1 proof for Lorum Ipsat on the clean PLCaa map.

The installed UTC is a hostile modeltype-F creature, matching K1's external
right-hand weapon attachment path.  Lorum's Set-2-shaped weapon slots and
creature fallback slots carry N_DarthMalak's combat choreography.
The proof combines that exact static asset/module chain with a same-process,
crash-monitored capture of Lorum entering combat in the real game.

Run this only after the Debug-app visual acceptance review.  KOTOR must be
closed before the script starts.  The script leaves KOTOR open by default and
never terminates it on an error; `--close-game` is the explicit opt-in shutdown.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import sys
import time
import atexit
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

os.environ.setdefault("GHOSTRIGGER_ROOT", str(ROOT))

from kotormcp.game_dinput_hook import describe_hook, hook_paths
from kotormcp.game_input import KotorWindowInput
from kotormcp.game_process_log import (
    analyze_session,
    read_session_status,
    request_stop,
    start_log_session,
)
from kotormcp.tools import game_test as tool_game_test
from src.core.assets.resource_manager import RES_2DA, ResourceManager, _ErfIndex
from src.core.modules.module_format import LYTLayout
from src.core.templates.twoda import TwoDA
from src.formats.gff_reader import read_gff


K1 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PACKAGE = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
OUTPUT = ROOT / "artifacts" / "lorum_ipsat_k1_plcaa_game_proof_20260713"
DEPLOYMENT_MANIFEST = ROOT / "artifacts" / "lorum_ipsat_plcaa" / "deployment_manifest.json"
STAGED_MODULE = ROOT / "artifacts" / "lorum_ipsat_plcaa" / "plcaa.mod"
INSTALLED_MODULE = K1 / "modules" / "PLCaa.mod"
DEPLOYED_FILES = (
    "c_ithlord.mdl",
    "c_ithlord.mdx",
    "c_ithlord_t00.tga",
    "appearance.2da",
    "sithlord01.utc",
)
RES_GIT = 2023
RES_LYT = 3000
DYNAMIC_GIT_LISTS = (
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
EXPECTED_FEATS = (
    1, 4, 5, 6, 8, 11, 54, 21, 55, 28,
    93, 36, 39, 40, 41, 42, 43, 44, 45, 50,
)
EXPECTED_POWERS = (
    4, 8, 9, 13, 12, 15, 16, 23, 30, 43, 45, 49, 50,
)
NATIVE_ITHORIAN_ANIMATIONS = (
    "crun", "cwalk", "cwalkinj", "cdodgeg", "cdamages", "cdie",
    "chturnl", "chturnr", "cpause1", "cpause2", "tlknorm", "cgustandb",
    "ctaunt", "cvictory", "cdead", "listen",
)
DIALOGUE_ANIMATIONS = ("cpause1", "cpause2", "tlknorm", "listen")
MALAK_COMBAT_SLOTS = {
    *(f"c2a{i}" for i in range(1, 7)),
    *(f"c2p{i}" for i in range(1, 6)),
    *(f"c2d{i}" for i in range(1, 6)),
    *(f"c2n{i}" for i in range(1, 3)),
    *(f"f2a{i}" for i in range(1, 5)),
    *(f"f2d{i}" for i in range(1, 4)),
    *(f"f2p{i}" for i in range(1, 4)),
    "g2r1", "g2w1", "tlkforce",
    "castout1", "castout2", "castout3",
    "castoutlp1", "castoutlp2", "castoutlp3",
    "choke", "fear", "horror", "sleep", "whirlwind",
    "throwsab", "throwsablp", "catchsab",
    "g1x1", "g1y1", "g1z1", "taunt", "kd",
    "g0a1", "g0a2", "creadyr",
}
MODELTYPE_F_NATIVE_STATE_ALIASES = {
    "pause1": "cpause1",
    "pause2": "cpause2",
    "die": "cdie",
    "dead": "cdead",
}
MAX_VISIBLE_SAVE_ROW = 4


def _tool_result(raw) -> dict:
    """Unwrap KotorMCP's json_content response envelope."""

    if isinstance(raw, dict) and "text" in raw:
        try:
            value = json.loads(raw["text"])
        except Exception as exc:
            raise RuntimeError(f"invalid KotorMCP response: {raw!r}") from exc
        return value if isinstance(value, dict) else {"value": value}
    return raw if isinstance(raw, dict) else {"raw": raw}


async def _preflight_save_warp_route() -> dict:
    prepare = _tool_result(
        await tool_game_test.handle_prepare_save_warp_test(
            {
                "game": "k1",
                "path": str(K1),
                "target_module": "plcaa",
                "require_loaded_save_before_warp": True,
                "require_dinput_hook": True,
                "launch_game": False,
            }
        )
    )
    saves = _tool_result(
        await tool_game_test.handle_list_saves(
            {
                "game": "k1",
                "path": str(K1),
                "offset": 0,
                "limit": 200,
            }
        )
    )
    if (
        prepare.get("error")
        or saves.get("error")
        or prepare.get("truncated")
        or saves.get("truncated")
    ):
        raise RuntimeError(f"KOTOR proof preflight failed: prepare={prepare}, saves={saves}")

    def same_path(left, right) -> bool:
        return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(
            str(Path(right).resolve())
        )

    selected = prepare.get("selected_save") or {}
    blocking = list(prepare.get("blocking_issues") or [])
    currentgame = prepare.get("currentgame_cache") or {}
    required = {
        "ready": bool(prepare.get("ready")),
        "path": same_path(prepare.get("path", ""), K1),
        "target_module": str(prepare.get("target_module") or "").lower()
        == "plcaa",
        "selected_save": bool(selected),
        "loaded_save_before_warp": bool(prepare.get("loaded_save_before_warp")),
        "module": bool((prepare.get("module") or {}).get("exists")),
        "console": bool((prepare.get("console") or {}).get("ready")),
        "windowed": bool((prepare.get("windowed") or {}).get("ready")),
        "hook": bool((prepare.get("dinput_hook") or {}).get("installed")),
        "currentgame_absent": not bool(currentgame.get("exists")),
        "no_blocking_issues": not blocking,
        "complete_save_listing": not bool(saves.get("has_more")),
    }
    if not all(required.values()):
        raise RuntimeError(
            "KOTOR proof preflight is not safe: "
            + json.dumps({"required": required, "prepare": prepare}, default=str)
        )

    selected_folder = str(selected.get("folder") or "")
    if not selected_folder.strip():
        raise RuntimeError("KOTOR proof preflight selected save has no folder")
    parsed_matches = [
        index
        for index, item in enumerate(saves.get("items") or [])
        if same_path(item.get("folder", ""), selected_folder)
    ]
    if len(parsed_matches) != 1:
        raise RuntimeError(
            "selected save did not map exactly once in the parsed save list: "
            f"{parsed_matches}"
        )
    # KOTOR also displays legacy rows that the strict save parser can omit.
    # Derive the click row from the actual numbered save directories so the
    # fixed UI coordinate matches what the player sees without deleting data.
    ui_save_rows = sorted(
        (path for path in (K1 / "saves").iterdir() if path.is_dir()),
        key=lambda path: path.name.lower(),
    )
    ui_matches = [
        index for index, path in enumerate(ui_save_rows)
        if same_path(path, selected_folder)
    ]
    if len(ui_matches) != 1:
        raise RuntimeError(
            f"selected save did not map exactly once to visible save rows: {ui_matches}"
        )
    save_row_index = int(ui_matches[0])
    # The route has no scrolling contract, but the first five fixed-height
    # rows are visible and have an established coordinate step.  A failed
    # PLCaa warp can create a target-module autosave in row 0, so permit the
    # next verified visible save instead of deleting or mutating user saves.
    if not 0 <= save_row_index <= MAX_VISIBLE_SAVE_ROW:
        raise RuntimeError(
            f"selected proof save is row {save_row_index}; only visible rows "
            f"0-{MAX_VISIBLE_SAVE_ROW} are safe without scrolling"
        )
    return {
        "prepare": prepare,
        "saves": saves,
        "required": required,
        "selected_save": selected,
        "save_row_index": save_row_index,
        "visible_save_rows": [path.name for path in ui_save_rows],
        "list_count": int(saves.get("count") or 0),
        "exact_folder_match": True,
    }


def _process_is_running(pid: int) -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    error_invalid_parameter = 87
    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(synchronize, False, int(pid))
    if not handle:
        error = int(ctypes.get_last_error())
        if error == error_invalid_parameter:
            return False
        raise RuntimeError(f"OpenProcess({pid}) failed while checking shutdown: {error}")
    try:
        result = int(kernel32.WaitForSingleObject(handle, 0))
        if result == wait_object_0:
            return False
        if result == wait_timeout:
            return True
        raise RuntimeError(
            f"WaitForSingleObject({pid}) returned unexpected status 0x{result:08X}"
        )
    finally:
        kernel32.CloseHandle(handle)


def _terminate_exact_process(pid: int, *, timeout_seconds: float = 8.0) -> dict:
    """Terminate only the supplied PID and wait for that exact handle to exit."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    process_terminate = 0x0001
    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(process_terminate | synchronize, False, int(pid))
    if not handle:
        error = int(ctypes.get_last_error())
        return {
            "ok": False,
            "pid": int(pid),
            "opened": False,
            "open_error": error,
            "process_running": _process_is_running(pid),
        }
    try:
        ctypes.set_last_error(0)
        terminated = bool(kernel32.TerminateProcess(handle, 0))
        terminate_error = int(ctypes.get_last_error()) if not terminated else 0
        wait_ms = max(0, int(round(float(timeout_seconds) * 1000.0)))
        wait_result = int(kernel32.WaitForSingleObject(handle, wait_ms)) if terminated else wait_timeout
        exited = wait_result == wait_object_0
        return {
            "ok": bool(terminated and exited),
            "pid": int(pid),
            "opened": True,
            "terminated": terminated,
            "terminate_error": terminate_error,
            "wait_result": f"0x{wait_result:08X}",
            "process_running": not exited and _process_is_running(pid),
        }
    finally:
        kernel32.CloseHandle(handle)


def _graceful_close_exact_game(
    controller: KotorWindowInput,
    expected_pid: int,
    *,
    timeout_seconds: float = 20.0,
) -> dict:
    """Post WM_CLOSE only to the exact game process launched by this proof."""

    status = controller.status()
    if not status.get("window_found"):
        running = _process_is_running(expected_pid)
        forced = _terminate_exact_process(expected_pid) if running else None
        return {
            "ok": bool(not running or (forced and forced.get("ok"))),
            "already_closed": not running,
            "expected_pid": int(expected_pid),
            "posted": False,
            "process_running": bool(running and not (forced and forced.get("ok"))),
            "close_method": "already_closed" if not running else "terminate_exact_pid",
            "forced": forced,
        }
    live_pid = int(status.get("process_id") or 0)
    if live_pid != int(expected_pid):
        return {
            "ok": False,
            "refused_pid_mismatch": True,
            "expected_pid": int(expected_pid),
            "live_pid": live_pid,
            "posted": False,
        }

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.PostMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.PostMessageW.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    posted = bool(user32.PostMessageW(int(status["hwnd"]), 0x0010, 0, 0))
    post_error = int(ctypes.get_last_error()) if not posted else 0
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    final_status = status
    while posted and time.monotonic() < deadline:
        final_status = controller.status()
        running = _process_is_running(expected_pid)
        if not final_status.get("window_found") and not running:
            return {
                "ok": True,
                "already_closed": False,
                "expected_pid": int(expected_pid),
                "posted": True,
                "process_running": False,
                "close_method": "wm_close",
                "final_status": final_status,
            }
        if (
            final_status.get("window_found")
            and int(final_status.get("process_id") or 0) != int(expected_pid)
        ):
            break
        time.sleep(0.25)
    running = _process_is_running(expected_pid)
    forced = _terminate_exact_process(expected_pid) if running else None
    return {
        "ok": bool(not running or (forced and forced.get("ok"))),
        "already_closed": False,
        "expected_pid": int(expected_pid),
        "posted": posted,
        "post_error": post_error,
        "process_running": bool(running and not (forced and forced.get("ok"))),
        "close_method": "process_exited" if not running else "terminate_exact_pid",
        "forced": forced,
        "final_status": final_status,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wait_for_window(controller: KotorWindowInput, timeout_seconds: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = controller.status()
        if status.get("window_found"):
            return status
        time.sleep(1.0)
    raise RuntimeError("KOTOR 1 window did not appear before the proof timeout")


def _visible_image_metrics(path: Path) -> dict:
    from PIL import Image

    with Image.open(path) as source:
        rgb = source.convert("RGB")
        gray = rgb.convert("L")
        histogram = gray.histogram()
        total = max(1, gray.width * gray.height)
        nonblack = sum(histogram[9:])
        mean_luma = sum(index * count for index, count in enumerate(histogram)) / total
        extrema = gray.getextrema()
        menu_crop = rgb.crop(
            (
                int(round(rgb.width * 0.41)),
                int(round(rgb.height * 0.43)),
                int(round(rgb.width * 0.79)),
                int(round(rgb.height * 0.71)),
            )
        )
        menu_yellow = 0
        menu_cyan = 0
        for red, green, blue in menu_crop.getdata():
            if red >= 160 and green >= 140 and blue <= 80 and red - green <= 100:
                menu_yellow += 1
            if red <= 80 and green >= 80 and blue >= 100:
                menu_cyan += 1
        menu_ready = menu_yellow >= 150 and menu_cyan >= 500
    return {
        "width": int(gray.width),
        "height": int(gray.height),
        "nonblack_fraction": float(nonblack / total),
        "mean_luma": float(mean_luma),
        "minimum_luma": int(extrema[0]),
        "maximum_luma": int(extrema[1]),
        "menu_yellow_pixels": int(menu_yellow),
        "menu_cyan_pixels": int(menu_cyan),
        "ready": bool(
            (nonblack / total) >= 0.05
            and mean_luma >= 2.0
            and extrema[1] >= 16
            and menu_ready
        ),
    }


def _main_menu_selection_metrics(path: Path) -> dict:
    """Identify KOTOR's highlighted main-menu row from the captured pixels."""

    from PIL import Image

    rows = {
        "new_game": (0.47, 0.51),
        "load_game": (0.51, 0.55),
        "movies": (0.55, 0.59),
        "options": (0.59, 0.63),
        "quit": (0.63, 0.67),
    }
    with Image.open(path) as source:
        rgb = source.convert("RGB")
        width, height = rgb.size
        yellow_by_row: dict[str, int] = {}
        for name, (top_ratio, bottom_ratio) in rows.items():
            crop = rgb.crop(
                (
                    int(round(width * 0.47)),
                    int(round(height * top_ratio)),
                    int(round(width * 0.72)),
                    int(round(height * bottom_ratio)),
                )
            )
            yellow_by_row[name] = sum(
                1
                for red, green, blue in crop.getdata()
                if red >= 140
                and green >= 120
                and blue <= 90
                and red - green <= 100
            )
    selected = max(yellow_by_row, key=yellow_by_row.get)
    if yellow_by_row[selected] < 80:
        selected = "unknown"
    return {
        "selected": selected,
        "yellow_by_row": yellow_by_row,
        "load_game_selected": selected == "load_game",
    }


def _wait_for_rendered_menu(
    controller: KotorWindowInput,
    expected_pid: int,
    output_path: Path,
    *,
    timeout_seconds: float = 45.0,
) -> dict:
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    attempts: list[dict] = []
    while time.monotonic() < deadline:
        status = controller.status()
        live_pid = int(status.get("process_id") or 0)
        if not status.get("window_found") or live_pid != int(expected_pid):
            raise RuntimeError(
                f"KOTOR process changed while waiting for its rendered menu: {status}"
            )
        capture = controller.capture_window(
            str(output_path),
            region="client",
            activate=True,
            clip_to_work_area=True,
            settle_seconds=0.2,
        )
        metrics = _visible_image_metrics(output_path)
        attempts.append({"status": status, "metrics": metrics})
        if metrics["ready"]:
            return {
                "ok": True,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "capture": capture,
                "metrics": metrics,
            }
        time.sleep(1.0)
    raise RuntimeError(f"KOTOR main menu stayed visually blank: {attempts}")


def _load_screen_metrics(path: Path) -> dict:
    from PIL import Image

    with Image.open(path) as source:
        rgb = source.convert("RGB")
        width, height = rgb.size

        def counts(box: tuple[float, float, float, float]) -> dict[str, int]:
            crop = rgb.crop(
                (
                    int(round(width * box[0])),
                    int(round(height * box[1])),
                    int(round(width * box[2])),
                    int(round(height * box[3])),
                )
            )
            yellow = 0
            cyan = 0
            for red, green, blue in crop.getdata():
                if red >= 160 and green >= 140 and blue <= 80 and red - green <= 100:
                    yellow += 1
                if red <= 80 and green >= 80 and blue >= 100:
                    cyan += 1
            return {"yellow": yellow, "cyan": cyan}

        save_row = counts((0.21, 0.23, 0.53, 0.41))
        load_button = counts((0.40, 0.67, 0.62, 0.83))
    return {
        "save_row": save_row,
        "load_button": load_button,
        "ready": bool(
            save_row["yellow"] >= 200
            and save_row["cyan"] >= 500
            and load_button["cyan"] >= 100
        ),
    }


def _wait_for_load_screen(
    controller: KotorWindowInput,
    expected_pid: int,
    output_path: Path,
    *,
    timeout_seconds: float = 5.0,
) -> dict:
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    attempts: list[dict] = []
    while time.monotonic() < deadline:
        status = controller.status()
        if (
            not status.get("window_found")
            or int(status.get("process_id") or 0) != int(expected_pid)
        ):
            raise RuntimeError(f"KOTOR process changed before the Load Game screen: {status}")
        capture = controller.capture_window(
            str(output_path), region="client", activate=False, settle_seconds=0.0
        )
        metrics = _load_screen_metrics(output_path)
        attempts.append({"status": status, "metrics": metrics})
        if metrics["ready"]:
            return {
                "ok": True,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "capture": capture,
                "metrics": metrics,
            }
        time.sleep(0.5)
    raise RuntimeError(f"KOTOR did not reach its Load Game screen: {attempts}")


def _gameplay_screen_metrics(path: Path) -> dict:
    visible = _visible_image_metrics(path)
    load = _load_screen_metrics(path)
    return {
        "visible": visible,
        "load": load,
        "ready": bool(
            visible["nonblack_fraction"] >= 0.05
            and not visible["ready"]
            and not load["ready"]
        ),
    }


def _classify_initial_screen(path: Path) -> dict:
    """Classify only screens that are safe for automated menu input.

    The KOTOR equipment and combat HUDs share enough cyan/yellow pixels with
    the main menu to satisfy the older broad menu gate.  Fail closed here: a
    screen is considered the main menu only when its menu-row signature is
    present *and* its overall luminance/coverage still looks like the sparse
    menu background.  Gameplay-like and unknown screens are never routed into
    keyboard or mouse actions.
    """

    visible = _visible_image_metrics(path)
    load = _load_screen_metrics(path)
    menu_selection = _main_menu_selection_metrics(path)
    main_menu_ready = bool(
        not load["ready"]
        and visible["ready"]
        and menu_selection["selected"] != "unknown"
        and visible["nonblack_fraction"] <= 0.82
        and visible["mean_luma"] <= 40.0
        and load["save_row"]["cyan"] < 500
    )
    if load["ready"]:
        screen = "load_screen"
    elif main_menu_ready:
        screen = "main_menu"
    elif visible["nonblack_fraction"] >= 0.05:
        screen = "gameplay_or_other"
    else:
        screen = "unknown"
    return {
        "screen": screen,
        "visible": visible,
        "load": load,
        "menu_selection": menu_selection,
        "main_menu_ready": main_menu_ready,
    }


def _wait_for_gameplay_screen(
    controller: KotorWindowInput,
    expected_pid: int,
    output_path: Path,
    *,
    timeout_seconds: float = 25.0,
) -> dict:
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    attempts: list[dict] = []
    while time.monotonic() < deadline:
        status = controller.status()
        if (
            not status.get("window_found")
            or int(status.get("process_id") or 0) != int(expected_pid)
        ):
            raise RuntimeError(f"KOTOR process changed while loading the save: {status}")
        capture = controller.capture_window(
            str(output_path), region="client", activate=False, settle_seconds=0.0
        )
        metrics = _gameplay_screen_metrics(output_path)
        attempts.append({"status": status, "metrics": metrics})
        if metrics["ready"]:
            return {
                "ok": True,
                "attempt_count": len(attempts),
                "attempts": attempts,
                "capture": capture,
                "metrics": metrics,
            }
        time.sleep(0.75)
    raise RuntimeError(f"KOTOR did not leave its menu/load screens: {attempts}")


def _wait_for_log_target(
    session_dir: Path, expected_pid: int, timeout_seconds: float = 12.0
) -> dict:
    deadline = time.monotonic() + max(1.0, float(timeout_seconds))
    last_events: list[dict] = []
    events_path = session_dir / "events.jsonl"
    while time.monotonic() < deadline:
        if events_path.is_file():
            lines = [
                line
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            parsed_events: list[dict] = []
            for index, line in enumerate(lines):
                try:
                    parsed_events.append(json.loads(line))
                except json.JSONDecodeError:
                    if index != len(lines) - 1:
                        raise
            last_events = parsed_events
            selected = [event for event in last_events if event.get("event") == "process_selected"]
            if selected:
                selected_pid = int((selected[-1].get("process") or {}).get("pid") or 0)
                if selected_pid != int(expected_pid):
                    raise RuntimeError(
                        f"live logger selected PID {selected_pid}, expected {expected_pid}"
                    )
                attached = [
                    event for event in last_events if event.get("event") == "debug_attached"
                ]
                if attached:
                    attachment = attached[-1]
                    attached_pid = int(attachment.get("pid") or 0)
                    if attached_pid != int(expected_pid):
                        raise RuntimeError(
                            f"live logger attached to PID {attached_pid}, expected {expected_pid}"
                        )
                    return {
                        "ok": True,
                        "expected_pid": int(expected_pid),
                        "selected": selected[-1],
                        "attachment": attachment,
                        "monitoring": attachment,
                        "monitoring_mode": "debug_events",
                    }
                failures = [
                    event
                    for event in last_events
                    if event.get("event") == "debug_attach_failed"
                ]
                fallbacks = [
                    event for event in last_events if event.get("event") == "monitor_fallback"
                ]
                if failures and fallbacks:
                    failure = failures[-1]
                    fallback = fallbacks[-1]
                    fallback_pid = int(fallback.get("pid") or 0)
                    if (
                        int(failure.get("last_error") or 0) != 5
                        or fallback_pid != int(expected_pid)
                        or fallback.get("mode") != "process_liveness"
                    ):
                        raise RuntimeError(
                            f"live logger fallback is not the expected elevated-game path: "
                            f"{failure}, {fallback}"
                        )
                    return {
                        "ok": True,
                        "expected_pid": int(expected_pid),
                        "selected": selected[-1],
                        "attachment": failure,
                        "monitoring": fallback,
                        "monitoring_mode": "process_liveness",
                        "limitation": (
                            "KOTOR is configured RUNASADMIN; this medium-integrity proof "
                            "process cannot receive debugger events from it."
                        ),
                    }
        time.sleep(0.25)
    raise RuntimeError(f"live logger did not select exact PID {expected_pid}: {last_events}")


def _run_verified_save_warp_route(
    controller: KotorWindowInput,
    expected_pid: int,
    shots: Path,
    *,
    target_module: str,
    save_row_index: int,
    expected_loaded_module: str,
    start_screen: str,
) -> dict:
    if not 0 <= int(save_row_index) <= MAX_VISIBLE_SAVE_ROW:
        raise RuntimeError(
            f"the Lorum proof only permits visible save rows 0-{MAX_VISIBLE_SAVE_ROW}"
        )
    actions: list[dict] = []
    load_screen = None
    if start_screen == "load_screen":
        initial_metrics = _load_screen_metrics(shots / "00_main_menu.png")
        if not initial_metrics["ready"]:
            raise RuntimeError(
                f"declared initial Load Game screen failed pixel gate: {initial_metrics}"
            )
        load_screen = {
            "ok": True,
            "already_open": True,
            "metrics": initial_metrics,
        }
        actions.append({"action": "reuse_open_load_screen", **load_screen})
    elif start_screen == "main_menu":
        keyboard_attempt: dict = {
            "route": "same_integrity_win32_scan",
            "sequence": ["down", "enter"],
        }
        controller.tap_scan(0xD0)
        time.sleep(0.35)
        selection_capture = controller.capture_window(
            str(shots / "00_menu_load_selected.png"),
            region="client",
            activate=False,
            settle_seconds=0.0,
        )
        selection = _main_menu_selection_metrics(shots / "00_menu_load_selected.png")
        keyboard_attempt["selection_capture"] = selection_capture
        keyboard_attempt["selection"] = selection
        if selection["load_game_selected"]:
            controller.tap_scan(0x1C)
            try:
                load_screen = _wait_for_load_screen(
                    controller,
                    expected_pid,
                    shots / "00a_load_screen.png",
                    timeout_seconds=7.0,
                )
                keyboard_attempt["transition_ok"] = True
            except RuntimeError as exc:
                keyboard_attempt["transition_ok"] = False
                keyboard_attempt["transition_error"] = str(exc)
        actions.append({"action": "keyboard_load_game", **keyboard_attempt})
    else:
        raise RuntimeError(f"unsupported initial KOTOR screen: {start_screen}")

    main_click_attempts: list[dict] = []
    if load_screen is None:
        for attempt in range(1, 4):
            action = controller.click(0.604, 0.547, coordinate_space="ratio")
            main_click_attempts.append({"attempt": attempt, "action": action})
            try:
                load_screen = _wait_for_load_screen(
                    controller,
                    expected_pid,
                    shots / "00a_load_screen.png",
                    timeout_seconds=5.0,
                )
                break
            except RuntimeError as exc:
                main_click_attempts[-1]["transition_error"] = str(exc)
    if load_screen is None:
        raise RuntimeError(
            f"Load Game input failed: keyboard={keyboard_attempt}, "
            f"mouse={main_click_attempts}"
        )
    if main_click_attempts:
        actions.append({"action": "click_load_game", "attempts": main_click_attempts})
    controller.reset_dinput_cursor_tracking()

    row_y = 0.356 + int(save_row_index) * 0.066
    row_action = controller.click(0.377, row_y, coordinate_space="ratio")
    actions.append(
        {
            "action": "click_save_row",
            "save_row_index": int(save_row_index),
            **row_action,
        }
    )
    time.sleep(0.75)

    loaded_save = None
    load_click_attempts: list[dict] = []
    for attempt in range(1, 3):
        action = controller.click(0.499, 0.742, coordinate_space="ratio")
        load_click_attempts.append({"attempt": attempt, "action": action})
        time.sleep(12.0)
        try:
            loaded_save = _wait_for_gameplay_screen(
                controller,
                expected_pid,
                shots / "00b_loaded_save.png",
                timeout_seconds=25.0,
            )
            break
        except RuntimeError as exc:
            load_click_attempts[-1]["transition_error"] = str(exc)
    if loaded_save is None:
        raise RuntimeError(f"verified save did not load: {load_click_attempts}")
    actions.append({"action": "click_load_save", "attempts": load_click_attempts})

    loaded_save_modules: list[str] = []
    save_module_deadline = time.monotonic() + 15.0
    while time.monotonic() < save_module_deadline:
        loaded_save_modules = [str(path) for path in (K1 / "currentgame").glob("*.mod")]
        if loaded_save_modules:
            break
        time.sleep(0.5)
    if not loaded_save_modules:
        raise RuntimeError("the selected save never materialized a currentgame module")
    loaded_stems = {Path(path).stem.lower() for path in loaded_save_modules}
    expected_stem = str(expected_loaded_module or "").strip().lower()
    if not expected_stem or expected_stem not in loaded_stems:
        raise RuntimeError(
            f"selected row did not load verified module {expected_stem!r}: "
            f"{sorted(loaded_stems)}"
        )
    if str(target_module).lower() in loaded_stems:
        raise RuntimeError(
            f"selected save was already in warp target {target_module}: "
            f"{sorted(loaded_stems)}"
        )

    command = f"warp {target_module}"
    actions.append(
        {"action": "console_command", "command": command, **controller.console_command(command)}
    )
    currentgame: list[str] = []
    warp_deadline = time.monotonic() + 35.0
    while time.monotonic() < warp_deadline:
        currentgame = [
            str(path)
            for path in (K1 / "currentgame").glob("*.mod")
            if path.stem.lower() == str(target_module).lower()
        ]
        if currentgame:
            break
        time.sleep(0.5)
    if not currentgame:
        raise RuntimeError(f"KOTOR did not materialize currentgame/{target_module}.mod")
    target_screen = _wait_for_gameplay_screen(
        controller,
        expected_pid,
        shots / "00c_plcaa_gameplay.png",
        timeout_seconds=25.0,
    )
    return {
        "ok": True,
        "start_screen": start_screen,
        "target_module": target_module,
        "save_row_index": int(save_row_index),
        "verified_loaded_module": expected_stem,
        "load_screen": load_screen,
        "loaded_save": loaded_save,
        "loaded_save_modules": loaded_save_modules,
        "currentgame_modules": currentgame,
        "target_screen": target_screen,
        "actions": actions,
        "final_status": controller.status(),
    }


def _wait_for_log_summary(session_dir: Path, timeout_seconds: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last = {}
    while time.monotonic() < deadline:
        last = read_session_status(session_dir)
        if last.get("summary") and not last.get("helper_running"):
            return last
        time.sleep(0.5)
    raise RuntimeError(f"live-log helper did not finalize: {last}")


def _frame_delta(first: Path, second: Path) -> int:
    from PIL import Image, ImageChops

    left = Image.open(first).convert("RGB")
    right = Image.open(second).convert("RGB")
    if left.size != right.size:
        return left.width * left.height
    diff = ImageChops.difference(left, right)
    return sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0))


def _write_contact_sheet(paths: list[Path], output: Path) -> Path:
    from PIL import Image, ImageDraw

    cell_width, cell_height, label_height, columns = 320, 240, 22, 4
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_width * columns, (cell_height + label_height) * rows), "#111111")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_width, cell_height))
        column = index % columns
        row = index // columns
        x = column * cell_width + (cell_width - image.width) // 2
        y = row * (cell_height + label_height)
        sheet.paste(image, (x, y))
        draw.text((column * cell_width + 5, y + cell_height + 3), path.stem, fill="#ffffff")
        image.close()
    sheet.save(output, "JPEG", quality=92)
    sheet.close()
    return output


def _write_animation(paths: list[Path], output: Path) -> Path:
    """Write the captured real-game frame sequence as a reviewable GIF."""

    from PIL import Image

    frames = [Image.open(path).convert("RGB") for path in paths]
    if not frames:
        raise AssertionError("cannot record an empty KOTOR proof sequence")
    try:
        frames[0].save(
            output,
            save_all=True,
            append_images=frames[1:],
            duration=250,
            loop=0,
            optimize=False,
        )
    finally:
        for frame in frames:
            frame.close()
    return output


def _event_signature(animation) -> tuple[tuple[float, str], ...]:
    return tuple(
        (float(event.time), str(event.name))
        for event in (animation.events or [])
    )


def _node_signature(node) -> tuple:
    parent = getattr(node, "parent", None)
    return (
        str(getattr(node, "name", "") or ""),
        str(getattr(parent, "name", "") or "") if parent is not None else "",
        int(getattr(node, "flags", 0) or 0),
        tuple(float(value) for value in (getattr(node, "position", ()) or ())),
        tuple(float(value) for value in (getattr(node, "rotation", ()) or ())),
        tuple(getattr(node, "controllers", ()) or ()),
    )


def _animation_signature(
    animation,
    *,
    include_name: bool = True,
    include_events: bool = True,
) -> tuple:
    return (
        str(getattr(animation, "name", "") or "").lower() if include_name else "",
        float(getattr(animation, "length", 0.0) or 0.0),
        float(getattr(animation, "transition_time", 0.0) or 0.0),
        str(getattr(animation, "anim_root", "") or ""),
        _event_signature(animation) if include_events else (),
        tuple(_node_signature(node) for node in (animation.nodes or [])),
    )


def _verify_installed_plcaa(
    package_hashes: dict[str, str],
    override_hashes: dict[str, str],
) -> dict:
    """Prove this run targets the exact staged clean PLCaa deployment."""

    assert DEPLOYMENT_MANIFEST.is_file(), DEPLOYMENT_MANIFEST
    assert STAGED_MODULE.is_file(), STAGED_MODULE
    assert INSTALLED_MODULE.is_file(), INSTALLED_MODULE
    deployment = json.loads(DEPLOYMENT_MANIFEST.read_text(encoding="utf-8"))
    assert deployment.get("schema") == "lorum_ipsat_plcaa_deployment_v1", deployment
    assert deployment.get("installed") is True, deployment
    assert deployment.get("hash_identical_module") is True, deployment
    assert deployment.get("hash_identical_override") is True, deployment
    manifest_package_hashes = {
        str(name): str(digest).lower()
        for name, digest in (deployment.get("package_hashes") or {}).items()
    }
    assert manifest_package_hashes == package_hashes == override_hashes

    staged_hash = _sha256(STAGED_MODULE)
    installed_hash = _sha256(INSTALLED_MODULE)
    assert staged_hash == installed_hash
    assert staged_hash == str(
        (deployment.get("staged_module_validation") or {}).get("sha256") or ""
    ).lower()
    assert installed_hash == str(
        ((deployment.get("install") or {}).get("module") or {}).get("sha256") or ""
    ).lower()

    index = _ErfIndex(str(INSTALLED_MODULE))
    lyt_bytes = index.read("plcaa", RES_LYT)
    assert lyt_bytes, f"PLCaa LYT missing from {INSTALLED_MODULE}"
    layout = LYTLayout.from_text(lyt_bytes.decode("latin-1", errors="strict"))
    assert [room.model for room in layout.rooms] == ["plcaa"], layout.rooms
    assert not layout.doorhooks, layout.doorhooks
    assert b"doorhookcount 0\r\n" in lyt_bytes.lower(), lyt_bytes
    git_bytes = index.read("plcaa", RES_GIT)
    assert git_bytes, f"PLCaa GIT missing from {INSTALLED_MODULE}"
    git = read_gff(git_bytes)
    counts = {
        label: len(git.root.fields[label].value)
        if label in git.root.fields else 0
        for label in DYNAMIC_GIT_LISTS
    }
    assert counts["Creature List"] == 1, counts
    assert all(
        count == 0
        for label, count in counts.items()
        if label != "Creature List"
    ), counts
    creatures = git.root.fields["Creature List"].value
    creature = creatures[0]
    assert str(creature.fields["TemplateResRef"].value).lower() == "sithlord01"
    placement = {
        "position": [
            float(creature.fields[label].value)
            for label in ("XPosition", "YPosition", "ZPosition")
        ],
        "facing": [
            float(creature.fields[label].value)
            for label in ("XOrientation", "YOrientation")
        ],
    }
    assert placement["position"] == [29.0, 32.0, 0.0], placement
    assert placement["facing"] == [0.0, -1.0], placement
    assert (deployment.get("staged_module_validation") or {}).get(
        "creature_refs"
    ) == ["sithlord01"]
    assert ((deployment.get("install") or {}).get("module") or {}).get(
        "creature_refs"
    ) == ["sithlord01"]
    return {
        "deployment_manifest": str(DEPLOYMENT_MANIFEST),
        "staged_module": str(STAGED_MODULE),
        "installed_module": str(INSTALLED_MODULE),
        "staged_sha256": staged_hash,
        "installed_sha256": installed_hash,
        "hash_identical": True,
        "resource_count": len(index._index),
        "layout_rooms": [room.model for room in layout.rooms],
        "layout_doorhook_count": len(layout.doorhooks),
        "dynamic_git_counts": counts,
        "creature_refs": ["sithlord01"],
        "lorum_placement": placement,
    }


def _verify_static_slot_chain() -> dict:
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    appearance = TwoDA.from_bytes(manager.get("appearance", RES_2DA, "K1"))
    animations = TwoDA.from_bytes(manager.get("animations", RES_2DA, "K1"))
    model = manager.load_model("c_ithlord", "K1")
    stock_ithorian = manager.load_model(
        "c_ithorian", "K1", prefer_base_archive=True
    )
    assert model is not None
    assert stock_ithorian is not None
    final_animations = list(model.animations or [])
    final_names = [str(animation.name or "").strip().lower() for animation in final_animations]
    assert len(final_names) == len(set(final_names))
    assert len(final_names) >= 284
    assert tuple(final_names[:len(NATIVE_ITHORIAN_ANIMATIONS)]) == NATIVE_ITHORIAN_ANIMATIONS
    assert set(DIALOGUE_ANIMATIONS) <= set(final_names)
    by_name = {
        str(animation.name or "").strip().lower(): animation
        for animation in final_animations
    }
    stock_by_name = {
        str(animation.name or "").strip().lower(): animation
        for animation in (stock_ithorian.animations or [])
    }
    for index, name in enumerate(NATIVE_ITHORIAN_ANIMATIONS):
        assert _animation_signature(final_animations[index]) == _animation_signature(
            stock_by_name[name]
        ), name

    assert MALAK_COMBAT_SLOTS <= set(final_names)
    for target, source in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
        assert _animation_signature(
            by_name[target], include_name=False
        ) == _animation_signature(
            by_name[source], include_name=False
        ), (target, source)
    for target, source in (("g0a1", "c2a1"), ("g0a2", "c2a2")):
        assert _animation_signature(
            by_name[target], include_name=False, include_events=False
        ) == _animation_signature(
            by_name[source], include_name=False, include_events=False
        ), (target, source)
        event_names = {
            str(event.name or "").lower()
            for event in (by_name[target].events or [])
        }
        assert "hit" in event_names
        assert not ({"clash", "contact", "hitparry"} & event_names)
    assert _animation_signature(
        by_name["creadyr"], include_name=False
    ) == _animation_signature(by_name["g2r1"], include_name=False)
    assert _animation_signature(
        by_name["c2a6"], include_name=False
    ) == _animation_signature(by_name["c2a5"], include_name=False)

    utc_name = "sithlord01.utc"
    utc = read_gff((K1 / "Override" / utc_name).read_bytes())
    first_name = utc.root.fields["FirstName"].value
    assert first_name.strref == -1 and first_name.english == "Lorum Ipsat"
    assert str(utc.root.fields["Tag"].value) == "sithlord01"
    assert str(utc.root.fields["TemplateResRef"].value) == "sithlord01"
    assert int(utc.root.fields["Appearance_Type"].value) == 509
    assert int(utc.root.fields["FactionID"].value) == 1
    assert int(utc.root.fields["SoundSetFile"].value) == 48
    assert int(utc.root.fields["GoodEvil"].value) == 10
    assert str(utc.root.fields["ScriptSpawn"].value) == "k_pkor_spn_buff"
    assert float(utc.root.fields["ChallengeRating"].value) == 8.0
    assert int(utc.root.fields["CurrentHitPoints"].value) == 60
    assert int(utc.root.fields["MaxHitPoints"].value) == 68
    assert int(utc.root.fields["ForcePoints"].value) == 64
    assert int(utc.root.fields["CurrentForce"].value) == 64
    classes = utc.root.fields["ClassList"].value
    assert len(classes) == 1
    assert int(classes[0].fields["Class"].value) == 3
    assert int(classes[0].fields["ClassLevel"].value) == 8
    powers = tuple(
        int(spell.fields["Spell"].value)
        for spell in classes[0].fields["KnownList0"].value
    )
    feats = tuple(
        int(feat.fields["Feat"].value)
        for feat in utc.root.fields["FeatList"].value
    )
    assert powers == EXPECTED_POWERS
    assert feats == EXPECTED_FEATS
    equipment = [
        str(item.fields["EquippedRes"].value)
        for item in utc.root.fields["Equip_ItemList"].value
        if "EquippedRes" in item.fields
    ]
    assert any(item.lower() == "g_w_lghtsbr06" for item in equipment)

    row = {
        "appearance_row": 509,
        "race": appearance.get(509, "race"),
        "modeltype": appearance.get(509, "modeltype"),
        "local_animation_count": len(final_animations),
        "engine_requested_slots": ["g0a1", "g0a2", "creadyr"],
        "malak_aliases": {
            "g0a1": "c2a1",
            "g0a2": "c2a2",
            "creadyr": "g2r1",
            "c2a6": "c2a5",
        },
        "malak_combat_slot_count": len(MALAK_COMBAT_SLOTS),
        "modeltype_f_native_state_aliases": dict(
            MODELTYPE_F_NATIVE_STATE_ALIASES),
        "native_ithorian_animation_count": len(NATIVE_ITHORIAN_ANIMATIONS),
        "native_dialogue_animations": list(DIALOGUE_ANIMATIONS),
        "utc": utc_name,
        "name": first_name.english,
        "class": 3,
        "level": 8,
        "challenge_rating": 8.0,
        "faction_id": int(utc.root.fields["FactionID"].value),
        "force_power_count": len(powers),
        "equipment": equipment,
    }
    assert str(row["race"] or "").lower() == "c_ithlord"
    assert str(row["modeltype"] or "").upper() == "F"
    slot_rows = {
        "276": animations.get(276, "name"),
        "277": animations.get(277, "name"),
        "278": animations.get(278, "name"),
    }
    assert [
        str(slot_rows[key] or "").lower() for key in ("276", "277", "278")
    ] == ["g0a1", "g0a2", "creadyr"]
    return {"appearance": {"c_ithlord": row}, "animations_2da_rows": slot_rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--close-game",
        action="store_true",
        help=(
            "Explicitly close the exact proof process after a successful "
            "capture. By default KOTOR is always left open, including on errors."
        ),
    )
    args = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "proof_report.json"
    report_path.unlink(missing_ok=True)
    shots = OUTPUT / "frames"
    shots.mkdir(parents=True, exist_ok=True)
    for stale_frame in shots.glob("*.png"):
        stale_frame.unlink()
    (OUTPUT / "combat_contact_sheet.jpg").unlink(missing_ok=True)
    (OUTPUT / "combat_recording.gif").unlink(missing_ok=True)

    package_hashes = {name: _sha256(PACKAGE / name) for name in DEPLOYED_FILES}
    override_hashes = {name: _sha256(K1 / "Override" / name) for name in DEPLOYED_FILES}
    assert package_hashes == override_hashes, "Override does not match the current built package"
    installed_plcaa = _verify_installed_plcaa(package_hashes, override_hashes)
    static_slot_chain = _verify_static_slot_chain()

    # Keep key delivery inside KOTOR's buffered DirectInput stream.  The input
    # helper explicitly restores foreground ownership before every queued key.
    controller = KotorWindowInput(game="k1", dinput_hook_root=K1)
    assert not controller.status().get("window_found"), (
        "start with KOTOR 1 closed for an uncontaminated proof"
    )
    preflight = asyncio.run(_preflight_save_warp_route())
    hook = describe_hook(K1)
    assert hook.get("installed"), hook
    command_file = hook_paths(K1).command_path
    command_file.write_text("", encoding="ascii")

    proof_pid = 0
    log: dict | None = None
    session_dir: Path | None = None
    log_target: dict | None = None
    log_finalized = False

    def stop_log_on_exit() -> None:
        if log_finalized or session_dir is None:
            return
        request_stop(session_dir)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if not read_session_status(session_dir).get("helper_running"):
                break
            time.sleep(0.25)

    atexit.register(stop_log_on_exit)

    os.startfile("steam://run/32370")  # noqa: S606 - intentional installed-game launch
    startup = _wait_for_window(controller)
    proof_pid = int(startup.get("process_id") or 0)
    assert proof_pid > 0, startup
    time.sleep(20.0)
    menu_ready = _wait_for_rendered_menu(
        controller,
        proof_pid,
        shots / "00_main_menu.png",
    )
    menu_capture = menu_ready["capture"]
    initial_screen_metrics = _classify_initial_screen(
        shots / "00_main_menu.png"
    )
    initial_screen = str(initial_screen_metrics["screen"])
    if initial_screen not in {"load_screen", "main_menu"}:
        raise RuntimeError(
            "KOTOR is not on a verified main-menu or Load Game screen; "
            "the proof sent no navigation input and will leave the game open. "
            f"Screen classification: {initial_screen_metrics}"
        )

    log = start_log_session(
        game="k1",
        game_root=str(K1),
        session_label="t2572-lorum-ipsat-malak-plcaa-k1",
        pid=proof_pid,
        wait_for_process=False,
        duration_seconds=900,
        asset_resrefs=[
            "c_ithlord",
            "appearance",
            "animations",
            "sithlord01",
        ],
        session_root=str(OUTPUT / "live_logs"),
    )
    assert int(log.get("target_pid") or 0) == proof_pid, log
    session_dir = Path(log["session_dir"])
    log_target = _wait_for_log_target(session_dir, proof_pid)
    logger_pid = int((log_target.get("selected") or {}).get("process", {}).get("pid") or 0)
    assert logger_pid == proof_pid, log_target

    route = _run_verified_save_warp_route(
        controller,
        proof_pid,
        shots,
        target_module="plcaa",
        save_row_index=int(preflight["save_row_index"]),
        expected_loaded_module=str(
            preflight["selected_save"].get("last_module") or ""
        ),
        start_screen=initial_screen,
    )
    route_status = controller.status()
    route_final_status = route.get("final_status") or {}
    assert (
        route_status.get("window_found")
        and int(route_status.get("process_id") or 0) == proof_pid
        and route_final_status.get("window_found")
        and int(route_final_status.get("process_id") or 0) == proof_pid
    ), {
        "startup": startup,
        "route_status": route_status,
        "route_final_status": route_final_status,
    }

    # KOTOR pauses the first hostile encounter behind an "Enemy Sighted"
    # message. Space dismisses it and lets ordinary AI combat request the stock
    # g0a1/g0a2 slots whose local payloads are Malak's choreography.
    controller.tap_scan(0x39)
    time.sleep(0.5)

    capture_frame_count = 150
    capture_interval_seconds = 0.1
    frame_paths: list[Path] = []
    for index in range(capture_frame_count):
        path = shots / f"{index + 1:03d}_combat.png"
        controller.capture_window(
            str(path),
            region="client",
            activate=False,
            clip_to_work_area=True,
            settle_seconds=0.0,
        )
        frame_paths.append(path)
        time.sleep(capture_interval_seconds)

    live_status = controller.status()
    assert live_status.get("window_found"), "KOTOR exited during the custom-model proof"
    assert int(live_status.get("process_id") or 0) == proof_pid, {
        "startup": startup,
        "route_status": route_status,
        "live_status": live_status,
    }
    request_stop(session_dir)
    final_log_status = _wait_for_log_summary(session_dir)
    log_finalized = True
    analysis = analyze_session(session_dir, annotate_with_ghidra=False, game="k1")

    events = [
        json.loads(line)
        for line in (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    event_names = [str(event.get("event") or "") for event in events]
    attached = [event for event in events if event.get("event") == "debug_attached"]
    fallbacks = [event for event in events if event.get("event") == "monitor_fallback"]
    monitoring = (attached or fallbacks)[-1]
    monitored_pid = int(monitoring.get("pid") or 0)
    assert (
        monitored_pid == proof_pid
        and int(live_status["process_id"]) == proof_pid
    ), monitoring
    assert not (
        {"process_not_found", "process_missing", "process_exit_observed"}
        & set(event_names)
    ), event_names
    if not attached:
        failures = [event for event in events if event.get("event") == "debug_attach_failed"]
        assert failures and int(failures[-1].get("last_error") or 0) == 5, failures
        assert fallbacks and fallbacks[-1].get("mode") == "process_liveness", fallbacks

    frame_hashes = [_sha256(path) for path in frame_paths]
    changed_pixels = [_frame_delta(frame_paths[0], path) for path in frame_paths[1:]]
    contact_sheet = _write_contact_sheet(frame_paths, OUTPUT / "combat_contact_sheet.jpg")
    recording = _write_animation(frame_paths, OUTPUT / "combat_recording.gif")
    report = {
        "schema": "lorum_ipsat_malak_plcaa_k1_proof_v3",
        "actual_game": "KOTOR 1",
        "target_module": "plcaa",
        "creature": "Lorum Ipsat",
        "model": "c_ithlord",
        "existing_slots": ["g0a1", "g0a2", "creadyr"],
        "combat_choreography": "N_DarthMalak",
        "preflight": preflight,
        "installed_plcaa": installed_plcaa,
        "static_slot_chain": static_slot_chain,
        "package_hashes": package_hashes,
        "override_hashes": override_hashes,
        "hash_identical": package_hashes == override_hashes,
        "hook": hook,
        "launch_context": {
            "runasadmin_compatibility_suspended_for_proof": (
                os.environ.get("LORUM_K1_PROOF_SUSPENDED_RUNASADMIN") == "1"
            ),
            "purpose": "same-integrity deterministic input and full debug-event monitoring",
        },
        "startup": startup,
        "menu_ready": menu_ready,
        "menu_capture": menu_capture,
        "initial_screen_metrics": initial_screen_metrics,
        "route": route,
        "route_status": route_status,
        "route_final_status": route_final_status,
        "live_status_after_capture": live_status,
        "frames": [str(path) for path in frame_paths],
        "capture_frame_count": capture_frame_count,
        "capture_interval_seconds": capture_interval_seconds,
        "contact_sheet": str(contact_sheet),
        "recording": str(recording),
        "unique_frame_hashes": len(set(frame_hashes)),
        "changed_pixels_from_first": changed_pixels,
        "log_session": log,
        "log_target": log_target,
        "log_status": final_log_status,
        "analysis": analysis,
        "debug_events": {
            "event_names": event_names,
            "attached": attached,
            "fallbacks": fallbacks,
            "monitoring_mode": log_target.get("monitoring_mode"),
            "monitoring_limitation": log_target.get("limitation"),
            "proof_pid": proof_pid,
            "same_pid_from_start_through_capture": (
                int(startup["process_id"])
                == logger_pid
                == int(route_final_status["process_id"])
                == int(route_status["process_id"])
                == int(live_status["process_id"])
                == monitored_pid
                == proof_pid
            ),
        },
        "visual_acceptance": {
            "automated_skeletal_animation_verdict": "not_evaluated",
            "required": "manual body-local articulation review of captured frames",
            "reason": (
                "whole-screen motion can come from the camera, player, HUD, "
                "effects, or rigid root motion"
            ),
        },
        "game_shutdown": {
            "requested": bool(args.close_game),
            "attempted": False,
            "ok": None,
            "reason": "KOTOR is left open by default",
        },
    }
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    assert len(set(frame_hashes)) >= 3, "capture remained visually unchanged"
    assert max(changed_pixels, default=0) >= 5000, "capture has no usable pixel variation"
    assert int(analysis.get("crash_count", 0) or 0) == 0, analysis

    game_shutdown = dict(report["game_shutdown"])
    if args.close_game:
        try:
            game_shutdown = _graceful_close_exact_game(controller, proof_pid)
            game_shutdown["requested"] = True
            game_shutdown["attempted"] = True
        except Exception as exc:
            game_shutdown = {
                "requested": True,
                "attempted": True,
                "ok": False,
                "expected_pid": proof_pid,
                "error": f"{type(exc).__name__}: {exc}",
            }
        assert game_shutdown.get("ok"), game_shutdown
    report["game_shutdown"] = game_shutdown
    report_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({
        "proof_report": str(report_path),
        "frames": len(frame_paths),
        "recording": str(recording),
        "unique_frame_hashes": len(set(frame_hashes)),
        "max_changed_pixels": max(changed_pixels, default=0),
        "crash_count": analysis.get("crash_count", 0),
        "exception_count": analysis.get("exception_count", 0),
        "monitoring_mode": log_target.get("monitoring_mode"),
        "skeletal_animation_verdict": "manual_review_required",
        "game_shutdown": game_shutdown,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
