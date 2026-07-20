"""KOTOR live process-log MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from kotormcp.game_process_log import (
    analyze_session,
    find_latest_session,
    read_session_status,
    request_stop,
    start_log_session,
)
from kotormcp.schemas import (
    KotorLogAnalyzeInput,
    KotorLogStartInput,
    KotorLogStatusInput,
    KotorLogStopInput,
)
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "kotor_log_start",
            "description": (
                "Start a live KOTOR debug-event log session. The helper waits for or attaches to "
                "swkotor/swkotor2, records Windows debug events, fingerprints Override assets, "
                "and writes JSONL evidence under Saved/KotorLiveLogs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "default": "k2"},
                    "path": {"type": "string", "description": "Optional absolute installation path"},
                    "session_label": {"type": "string", "default": "kotor-live"},
                    "pid": {"type": "integer", "description": "Optional already-running swkotor/swkotor2 process id"},
                    "wait_for_process": {"type": "boolean", "default": True},
                    "duration_seconds": {"type": "integer", "default": 900},
                    "asset_resrefs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["c_drexlf", "appearance"],
                    },
                    "session_root": {"type": "string", "description": "Optional output root for log sessions"},
                    "expected_warp_target": {
                        "type": "string",
                        "description": "Optional module resref expected in the warp command",
                    },
                    "expected_module_sha256": {
                        "type": "string",
                        "description": "Optional required SHA-256 for Modules/<expected_warp_target>.mod",
                    },
                },
            },
        },
        {
            "name": "kotor_log_status",
            "description": "Read status for a KOTOR live log session, or the latest session if no path is provided.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_dir": {"type": "string"},
                    "session_root": {"type": "string"},
                },
            },
        },
        {
            "name": "kotor_log_stop",
            "description": "Ask a KOTOR live log helper to detach and finalize its summary.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_dir": {"type": "string"},
                    "session_root": {"type": "string"},
                },
            },
        },
        {
            "name": "kotor_log_analyze",
            "description": (
                "Analyze a completed KOTOR live log session and annotate crash addresses "
                "with AgentDecompile/Ghidra when the backend is configured."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "default": "k2"},
                    "session_dir": {"type": "string"},
                    "session_root": {"type": "string"},
                    "annotate_with_ghidra": {"type": "boolean", "default": True},
                    "ghidra_program": {
                        "type": "string",
                        "description": "Optional exact AgentDecompile/Ghidra program path for the launched exe.",
                    },
                },
            },
        },
    ]


async def handle_start(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorLogStartInput.model_validate(arguments)
    game = resolve_game(inp.game)
    game_root = _game_root(game, inp.path)
    try:
        result = start_log_session(
            game=inp.game or "k2",
            game_root=game_root,
            session_label=inp.session_label,
            pid=inp.pid,
            wait_for_process=bool(inp.wait_for_process if inp.wait_for_process is not None else True),
            duration_seconds=int(inp.duration_seconds or 900),
            asset_resrefs=list(inp.asset_resrefs or ["c_drexlf", "appearance"]),
            session_root=inp.session_root,
            expected_warp_target=inp.expected_warp_target,
            expected_module_sha256=inp.expected_module_sha256,
        )
        return json_content({"ok": True, **result})
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc)})


async def handle_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorLogStatusInput.model_validate(arguments)
    session = _session_dir(inp.session_dir, inp.session_root)
    if session is None:
        return json_content({"ok": False, "error": "No KOTOR live log session was found."})
    try:
        return json_content({"ok": True, **read_session_status(session)})
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc), "session_dir": str(session)})


async def handle_stop(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorLogStopInput.model_validate(arguments)
    session = _session_dir(inp.session_dir, inp.session_root)
    if session is None:
        return json_content({"ok": False, "error": "No KOTOR live log session was found."})
    try:
        return json_content(request_stop(session))
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc), "session_dir": str(session)})


async def handle_analyze(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorLogAnalyzeInput.model_validate(arguments)
    session = _session_dir(inp.session_dir, inp.session_root)
    if session is None:
        return json_content({"ok": False, "error": "No KOTOR live log session was found."})
    try:
        result = analyze_session(
            session,
            annotate_with_ghidra=bool(inp.annotate_with_ghidra if inp.annotate_with_ghidra is not None else True),
            game=inp.game or "k2",
            ghidra_program=inp.ghidra_program,
        )
        return json_content({"ok": True, "session_dir": str(session), **result}, max_chars=250_000)
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc), "session_dir": str(session)})


def _game_root(game: Optional[Any], explicit_path: Optional[str]) -> Optional[str]:
    if explicit_path:
        return str(Path(explicit_path))
    if game is None:
        return None
    try:
        installation = load_installation(game, None)
    except Exception:
        return None
    return str(installation.path())


def _session_dir(explicit: Optional[str], root: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit)
    return find_latest_session(root)
