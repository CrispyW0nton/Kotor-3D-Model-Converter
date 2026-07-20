"""Live in-game proof: warp into the custom K2 plcaa test map via KotorMCP.

Evidence-first flow (calls the kotormcp tool handlers directly):
  1. Verify/install the DirectInput proxy hook.
  2. Preflight the save+warp route (module installed, cheats, windowed, save).
  3. Start a crash-log session (debugger attach, events.jsonl).
  4. Launch TSL, drive the Load Game menu via SendInput, warp via the hook.
  5. Capture window screenshots before/after the warp.
  6. Stop + analyze the session (Ghidra-annotated if it crashed).

Run: py -3.14 -u scripts/kotor_live_warp_plcaa.py [--skip-launch]
"""
from __future__ import annotations

import asyncio
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

os.environ.setdefault("GHOSTRIGGER_ROOT", str(ROOT))
os.environ.setdefault("AGENTDECOMPILE_MCP_SERVER_URL", "http://170.9.241.140:8080/mcp/")
os.environ.setdefault("AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST", "170.9.241.140")
os.environ.setdefault("AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT", "13100")
os.environ.setdefault("AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY", "Odyssey")
os.environ.setdefault("AGENTDECOMPILE_GHIDRA_USERNAME", "OpenKotOR")
_ghidra_password = os.environ.get("AGENTDECOMPILE_GHIDRA_PASSWORD", "").strip()
if _ghidra_password and not os.environ.get("AGENTDECOMPILE_MCP_HEADERS_JSON"):
    os.environ["AGENTDECOMPILE_MCP_HEADERS_JSON"] = json.dumps(
        {
            "User-Agent": "PyKotorAgent/1.0",
            "X-Agent-Version": "1.0",
            "X-Agent-Server-Username": os.environ["AGENTDECOMPILE_GHIDRA_USERNAME"],
            "X-Agent-Server-Password": _ghidra_password,
            "X-Ghidra-Repository": "Odyssey",
            "X-Agent-Server-Repository": "Odyssey",
        }
    )
os.environ.setdefault("AGENTDECOMPILE_K2_STEAM_PROGRAM_PATH", "/TSL/k2_win_steam_aspyr_swkotor2.exe")

from kotormcp.tools import game_test as tool_game_test
from kotormcp.tools import kotor_dinput_hook as tool_hook
from kotormcp.tools import kotor_input as tool_input
from kotormcp.tools import kotor_live_log as tool_log

TARGET_MODULE = os.environ.get("GR_WARP_TARGET", "plcaa")
SESSION_LABEL = os.environ.get("GR_SESSION_LABEL", f"runtime-test-{TARGET_MODULE}-k2-warp")
ASSET_RESREFS = ["plcaa", "gr_puzzle", "gr_pzdoor", "gr_store", "gr_shopterm", "gr_ped1", "ruler01", "appearance"]
K2_GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def clean_slate() -> None:
    """Stale proxy commands replay into the next launch; a crashed session's
    currentgame cache can auto-resume — both contaminate the test."""

    queue = K2_GAME_ROOT / "kotor_dinput_proxy_commands.txt"
    if queue.exists():
        queue.write_text("", encoding="ascii")
        print("cleared stale dinput proxy queue")
    currentgame = K2_GAME_ROOT / "currentgame"
    if currentgame.exists():
        shutil.rmtree(currentgame, ignore_errors=True)
        print("cleared currentgame cache")


def result_of(raw) -> dict:
    """Unwrap the kotormcp json_content envelope."""

    if isinstance(raw, dict) and "text" in raw:
        try:
            return json.loads(raw["text"])
        except Exception:
            return {"raw": raw["text"]}
    return raw if isinstance(raw, dict) else {"raw": raw}


def step(name: str, payload: dict, keys: tuple[str, ...] = ()) -> dict:
    summary = {k: payload.get(k) for k in keys if k in payload} if keys else payload
    print(f"\n== {name} ==")
    print(json.dumps(summary, indent=2, default=str)[:1600], flush=True)
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-launch",
        action="store_true",
        help="Use an already-running KOTOR 2 process instead of launching the game.",
    )
    return parser.parse_args()


async def main(*, skip_launch: bool = False) -> int:
    clean_slate()

    # 1. Hook status / install.
    hook = result_of(await tool_hook.handle_status({"game": "k2"}))
    step("dinput hook status", hook, ("installed", "proxy_sha256", "log_path"))
    if not hook.get("installed"):
        installed = result_of(await tool_hook.handle_install({"game": "k2"}))
        step("dinput hook install", installed)
        if not installed.get("ok", installed.get("installed")):
            print("BLOCKED: hook install failed")
            return 1

    # 2. Preflight (no launch yet).
    prepare = result_of(
        await tool_game_test.handle_prepare_save_warp_test(
            {
                "game": "k2",
                "target_module": TARGET_MODULE,
                "require_loaded_save_before_warp": True,
                "require_dinput_hook": True,
            }
        )
    )
    step(
        "prepare save+warp preflight",
        prepare,
        ("ready", "target_module", "selected_save", "module", "console", "windowed", "blocking_issues", "warnings"),
    )
    if not prepare.get("ready"):
        if os.environ.get("GR_SKIP_PREFLIGHT"):
            print("preflight not ready — continuing anyway (GR_SKIP_PREFLIGHT set)")
        else:
            print("BLOCKED: preflight not ready")
            return 1

    # 3. Start crash-log session BEFORE launch.
    log = result_of(
        await tool_log.handle_start(
            {
                "game": "k2",
                "session_label": SESSION_LABEL,
                "wait_for_process": True,
                "duration_seconds": 300,
                "asset_resrefs": ASSET_RESREFS,
            }
        )
    )
    step("log session start", log, ("ok", "session_dir", "session_id", "error"))
    session_dir = log.get("session_dir", "")

    # 4. Launch the game via the preflight's launcher.
    if not skip_launch:
        launched = result_of(
            await tool_game_test.handle_prepare_save_warp_test(
                {
                    "game": "k2",
                    "target_module": TARGET_MODULE,
                    "require_loaded_save_before_warp": True,
                    "require_dinput_hook": True,
                    "launch_game": True,
                }
            )
        )
        step("game launch", launched.get("launch") or launched, ())
        print("waiting for the main menu...", flush=True)
        time.sleep(35.0)

    shots_dir = ROOT / "Saved" / "GameTestStaging"
    shots_dir.mkdir(parents=True, exist_ok=True)
    shot = result_of(
        await tool_input.handle_capture_window(
            {"game": "k2", "output_path": str(shots_dir / "plcaa_k2_main_menu.png")}
        )
    )
    step("main menu screenshot", shot, ("ok", "output_path", "window", "error"))

    # 5. Drive Load Game -> newest save -> warp plcaa (hook console).
    route = result_of(
        await tool_input.handle_run_save_warp_route(
            {
                "game": "k2",
                "target_module": TARGET_MODULE,
                "start_screen": "main_menu",
                "save_row_index": 0,
                "use_dinput_hook": True,
                "after_menu_seconds": 3.0,
                "after_load_seconds": 25.0,
                "after_warp_seconds": 25.0,
            }
        )
    )
    step("save->warp route", route, ("ok", "target_module", "actions", "error"))

    shot2 = result_of(
        await tool_input.handle_capture_window(
            {"game": "k2", "output_path": str(shots_dir / "plcaa_k2_after_warp.png")}
        )
    )
    step("after-warp screenshot", shot2, ("ok", "output_path", "window", "error"))

    # Give the module a moment to settle, then wrap up the session.
    time.sleep(10.0)
    status = result_of(await tool_log.handle_status({}))
    step("log status", status, ("running", "session_dir", "event_count", "exception_count"))
    stopped = result_of(await tool_log.handle_stop({"session_dir": session_dir} if session_dir else {}))
    step("log stop", stopped, ("ok", "session_dir", "summary_path", "error"))
    session_dir = stopped.get("session_dir", session_dir)

    analysis = result_of(
        await tool_log.handle_analyze(
            {
                "session_dir": session_dir,
                "annotate_with_ghidra": True,
                "ghidra_program": "/TSL/k2_win_steam_aspyr_swkotor2.exe",
                "game": "k2",
            }
        )
    )
    step("log analyze", analysis, ("ok", "verdict", "exception_count", "analysis_path", "crash", "error"))

    print("\n== evidence ==")
    print("session:", session_dir)
    for name in ("events.jsonl", "summary.json", "analysis.json", "analysis.txt"):
        candidate = Path(str(session_dir)) / name
        print(f"  {name}: {'present' if candidate.exists() else 'MISSING'}")
    return 0


if __name__ == "__main__":
    _args = _parse_args()
    raise SystemExit(asyncio.run(main(skip_launch=_args.skip_launch)))
