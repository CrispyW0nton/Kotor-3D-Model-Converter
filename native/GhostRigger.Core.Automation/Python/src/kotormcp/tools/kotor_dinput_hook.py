"""KOTOR DirectInput proxy hook MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from kotormcp.game_dinput_hook import (
    describe_hook,
    install_hook,
    queue_commands,
    queue_mouse_click,
    queue_text,
)
from kotormcp.schemas import (
    KotorDInputHookInstallInput,
    KotorDInputHookSendInput,
    KotorDInputHookStatusInput,
)
from kotormcp.state import load_installation, resolve_game
from kotormcp.utils import json_content


def get_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "kotor_dinput_hook_status",
            "description": (
                "Check whether the GhostRigger DirectInput proxy hook is installed beside "
                "swkotor/swkotor2 and return its command/log file paths."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "default": "k2"},
                    "path": {"type": "string", "description": "Optional absolute installation path"},
                    "proxy_path": {"type": "string", "description": "Optional built dinput8.dll path"},
                },
            },
        },
        {
            "name": "kotor_dinput_hook_install",
            "description": (
                "Install the built GhostRigger dinput8.dll proxy into a KOTOR 1 or KOTOR 2 "
                "game folder. Existing non-GhostRigger dinput8.dll files require force=True "
                "and are backed up before replacement."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "default": "k2"},
                    "path": {"type": "string", "description": "Optional absolute installation path"},
                    "proxy_path": {"type": "string", "description": "Optional built dinput8.dll path"},
                    "backup_root": {"type": "string", "description": "Optional backup output root"},
                    "force": {"type": "boolean", "default": False},
                    "dry_run": {"type": "boolean", "default": False},
                },
            },
        },
        {
            "name": "kotor_dinput_hook_send",
            "description": (
                "Queue command-file input for the installed KOTOR DirectInput proxy. This can "
                "tap keys, click the mouse, or type console text such as warp tst_light."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "default": "k2"},
                    "path": {"type": "string", "description": "Optional absolute installation path"},
                    "proxy_path": {"type": "string", "description": "Optional built dinput8.dll path"},
                    "commands": {"type": "array", "items": {"type": "string"}},
                    "text": {"type": "string"},
                    "open_console": {"type": "boolean", "default": False},
                    "press_enter": {"type": "boolean", "default": False},
                    "mouse_click": {"type": "boolean", "default": False},
                    "reset_first": {"type": "boolean", "default": False},
                    "key_polls": {"type": "integer", "default": 12},
                    "mouse_polls": {"type": "integer", "default": 24},
                },
            },
        },
    ]


async def handle_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorDInputHookStatusInput.model_validate(arguments)
    game_root = _game_root(inp.game, inp.path)
    if game_root is None:
        return json_content({"ok": False, "error": "Specify a known game (k1/k2) or an installation path."})
    try:
        return json_content({"ok": True, **describe_hook(game_root, proxy_path=inp.proxy_path)})
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc)})


async def handle_install(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorDInputHookInstallInput.model_validate(arguments)
    game = resolve_game(inp.game)
    game_root = _game_root(inp.game, inp.path)
    if game_root is None:
        return json_content({"ok": False, "error": "Specify a known game (k1/k2) or an installation path."})
    try:
        return json_content(
            install_hook(
                game_root,
                game=str(inp.game or game or "kotor"),
                proxy_path=inp.proxy_path,
                backup_root=inp.backup_root,
                force=bool(inp.force),
                dry_run=bool(inp.dry_run),
            )
        )
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc)})


async def handle_send(arguments: Dict[str, Any]) -> Dict[str, Any]:
    inp = KotorDInputHookSendInput.model_validate(arguments)
    game_root = _game_root(inp.game, inp.path)
    if game_root is None:
        return json_content({"ok": False, "error": "Specify a known game (k1/k2) or an installation path."})
    try:
        results: list[dict[str, Any]] = []
        if inp.commands:
            results.append(
                queue_commands(
                    game_root,
                    list(inp.commands or []),
                    proxy_path=inp.proxy_path,
                    reset_first=bool(inp.reset_first),
                )
            )
        if inp.text:
            results.append(
                queue_text(
                    game_root,
                    str(inp.text),
                    proxy_path=inp.proxy_path,
                    open_console=bool(inp.open_console),
                    press_enter=bool(inp.press_enter),
                    key_polls=int(inp.key_polls or 12),
                    reset_first=bool(inp.reset_first and not results),
                )
            )
        if bool(inp.mouse_click):
            results.append(
                queue_mouse_click(
                    game_root,
                    proxy_path=inp.proxy_path,
                    mouse_polls=int(inp.mouse_polls or 24),
                    reset_first=bool(inp.reset_first and not results),
                )
            )
        if not results:
            return json_content({"ok": False, "error": "Provide commands, text, or mouse_click=True."})
        return json_content(
            {
                "ok": all(bool(result.get("ok")) for result in results),
                "game_root": str(game_root),
                "results": results,
            }
        )
    except Exception as exc:
        return json_content({"ok": False, "error": str(exc)})


def _game_root(game: Optional[str], explicit_path: Optional[str]) -> Optional[Path]:
    if explicit_path:
        return Path(explicit_path)
    resolved = resolve_game(game or "k2")
    if resolved is None:
        return None
    try:
        installation = load_installation(resolved, None)
    except Exception:
        return None
    return Path(installation.path())
