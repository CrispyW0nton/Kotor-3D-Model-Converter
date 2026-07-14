"""DirectInput proxy deployment and command helpers for KOTOR live proofs."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


HOOK_DLL_NAME = "dinput8.dll"
HOOK_COMMAND_FILE = "kotor_dinput_proxy_commands.txt"
HOOK_LOG_FILE = "kotor_dinput_proxy.log"
DEFAULT_KEY_POLLS = 12
DEFAULT_MOUSE_POLLS = 24

SCAN_ENTER = 0x1C
SCAN_GRAVE = 0x29
SCAN_SHIFT = 0x2A

CHAR_SCANCODES: dict[str, tuple[int, bool]] = {
    "a": (0x1E, False),
    "b": (0x30, False),
    "c": (0x2E, False),
    "d": (0x20, False),
    "e": (0x12, False),
    "f": (0x21, False),
    "g": (0x22, False),
    "h": (0x23, False),
    "i": (0x17, False),
    "j": (0x24, False),
    "k": (0x25, False),
    "l": (0x26, False),
    "m": (0x32, False),
    "n": (0x31, False),
    "o": (0x18, False),
    "p": (0x19, False),
    "q": (0x10, False),
    "r": (0x13, False),
    "s": (0x1F, False),
    "t": (0x14, False),
    "u": (0x16, False),
    "v": (0x2F, False),
    "w": (0x11, False),
    "x": (0x2D, False),
    "y": (0x15, False),
    "z": (0x2C, False),
    "1": (0x02, False),
    "2": (0x03, False),
    "3": (0x04, False),
    "4": (0x05, False),
    "5": (0x06, False),
    "6": (0x07, False),
    "7": (0x08, False),
    "8": (0x09, False),
    "9": (0x0A, False),
    "0": (0x0B, False),
    " ": (0x39, False),
    "-": (0x0C, False),
    "_": (0x0C, True),
    ".": (0x34, False),
    "/": (0x35, False),
    "\\": (0x2B, False),
    "`": (SCAN_GRAVE, False),
}


@dataclass(frozen=True)
class DInputHookPaths:
    game_root: Path
    proxy_path: Path
    target_dll: Path
    command_path: Path
    log_path: Path


def repo_root() -> Path:
    env_root = os.environ.get("GHOSTRIGGER_ROOT")
    if env_root:
        return Path(env_root).resolve()
    path = Path(__file__).resolve()
    for parent in [path, *path.parents]:
        if (parent / "CHANGES.md").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd().resolve()


def default_proxy_path() -> Path:
    return repo_root() / "Saved" / "KotorDInputProxy" / HOOK_DLL_NAME


def hook_paths(game_root: str | Path, proxy_path: Optional[str] = None) -> DInputHookPaths:
    root = Path(game_root).resolve()
    proxy = Path(proxy_path).resolve() if proxy_path else default_proxy_path()
    return DInputHookPaths(
        game_root=root,
        proxy_path=proxy,
        target_dll=root / HOOK_DLL_NAME,
        command_path=root / HOOK_COMMAND_FILE,
        log_path=root / HOOK_LOG_FILE,
    )


def describe_hook(game_root: str | Path, *, proxy_path: Optional[str] = None) -> dict[str, Any]:
    paths = hook_paths(game_root, proxy_path)
    proxy_hash = _sha256(paths.proxy_path) if paths.proxy_path.is_file() else ""
    target_hash = _sha256(paths.target_dll) if paths.target_dll.is_file() else ""
    return {
        "game_root": str(paths.game_root),
        "proxy_path": str(paths.proxy_path),
        "proxy_exists": paths.proxy_path.is_file(),
        "proxy_sha256": proxy_hash,
        "target_dll": str(paths.target_dll),
        "target_exists": paths.target_dll.is_file(),
        "target_sha256": target_hash,
        "installed": bool(proxy_hash and target_hash and proxy_hash == target_hash),
        "command_path": str(paths.command_path),
        "command_pending": paths.command_path.is_file(),
        "log_path": str(paths.log_path),
        "log_exists": paths.log_path.is_file(),
        "log_tail": _tail(paths.log_path),
    }


def install_hook(
    game_root: str | Path,
    *,
    game: str = "k2",
    proxy_path: Optional[str] = None,
    backup_root: Optional[str] = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    paths = hook_paths(game_root, proxy_path)
    if not paths.game_root.is_dir():
        return {"ok": False, "error": f"Game root does not exist: {paths.game_root}"}
    if not paths.proxy_path.is_file():
        return {"ok": False, "error": f"Built proxy DLL does not exist: {paths.proxy_path}"}

    before = describe_hook(paths.game_root, proxy_path=str(paths.proxy_path))
    if before["installed"]:
        return {"ok": True, "already_installed": True, "dry_run": bool(dry_run), "hook": before}

    backup_path = ""
    if paths.target_dll.exists():
        if not force:
            return {
                "ok": False,
                "error": f"Existing {HOOK_DLL_NAME} is not the GhostRigger proxy; pass force=True to back it up and replace it.",
                "hook": before,
            }
        backup_dir = _backup_dir(backup_root, game)
        backup_path = str(backup_dir / HOOK_DLL_NAME)

    if not dry_run:
        if backup_path:
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.target_dll, backup_path)
        shutil.copy2(paths.proxy_path, paths.target_dll)

    after = describe_hook(paths.game_root, proxy_path=str(paths.proxy_path))
    return {
        "ok": bool(dry_run or after["installed"]),
        "already_installed": False,
        "dry_run": bool(dry_run),
        "backup_path": backup_path,
        "hook": after,
    }


def queue_commands(
    game_root: str | Path,
    commands: Iterable[str],
    *,
    proxy_path: Optional[str] = None,
    reset_first: bool = False,
) -> dict[str, Any]:
    paths = hook_paths(game_root, proxy_path)
    clean = [_clean_command(command) for command in commands]
    clean = [command for command in clean if command]
    if reset_first:
        clean.insert(0, "reset")
    if not clean:
        return {"ok": False, "error": "No DirectInput proxy commands were provided."}
    if not paths.game_root.is_dir():
        return {"ok": False, "error": f"Game root does not exist: {paths.game_root}"}
    with paths.command_path.open("a", encoding="ascii", newline="\n") as handle:
        for command in clean:
            handle.write(command + "\n")
    return {
        "ok": True,
        "command_path": str(paths.command_path),
        "queued_count": len(clean),
        "commands": clean,
    }


def queue_text(
    game_root: str | Path,
    text: str,
    *,
    proxy_path: Optional[str] = None,
    open_console: bool = False,
    press_enter: bool = False,
    key_polls: int = DEFAULT_KEY_POLLS,
    reset_first: bool = False,
) -> dict[str, Any]:
    commands: list[str] = []
    if open_console:
        commands.append(_key_tap(SCAN_GRAVE, key_polls))
    for char in str(text or ""):
        if char == "\n":
            commands.append(_key_tap(SCAN_ENTER, key_polls))
            continue
        scan, shifted = _scan_for_char(char)
        if shifted:
            commands.append(f"key_combo 0x{SCAN_SHIFT:02x} 0x{scan:02x} {int(key_polls)}")
        else:
            commands.append(_key_tap(scan, key_polls))
    if press_enter:
        commands.append(_key_tap(SCAN_ENTER, key_polls))
    return queue_commands(game_root, commands, proxy_path=proxy_path, reset_first=reset_first)


def queue_mouse_click(
    game_root: str | Path,
    *,
    proxy_path: Optional[str] = None,
    mouse_polls: int = DEFAULT_MOUSE_POLLS,
    reset_first: bool = False,
) -> dict[str, Any]:
    return queue_commands(
        game_root,
        [f"mouse_click {int(mouse_polls or DEFAULT_MOUSE_POLLS)}"],
        proxy_path=proxy_path,
        reset_first=reset_first,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tail(path: Path, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:]


def _backup_dir(backup_root: Optional[str], game: str) -> Path:
    root = Path(backup_root).resolve() if backup_root else repo_root() / "Saved" / "KotorDInputProxyBackups"
    label = re.sub(r"[^a-z0-9_.-]+", "-", str(game or "kotor").lower()).strip(".-") or "kotor"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return root / f"{stamp}-{label}"


def _clean_command(command: str) -> str:
    text = str(command or "").strip()
    if not text or text.startswith("#"):
        return ""
    if "\r" in text or "\n" in text:
        raise ValueError("DirectInput proxy commands must be one line each.")
    command_name = text.split(maxsplit=1)[0].lower()
    if command_name not in {"reset", "mouse_click", "key_tap", "key_combo"}:
        raise ValueError(f"Unsupported DirectInput proxy command: {command_name}")
    return text


def _scan_for_char(char: str) -> tuple[int, bool]:
    if char.isalpha():
        scan, _shifted = CHAR_SCANCODES[char.lower()]
        return scan, char.isupper()
    if char in CHAR_SCANCODES:
        return CHAR_SCANCODES[char]
    raise ValueError(f"Unsupported text character for DirectInput proxy typing: {char!r}")


def _key_tap(scan: int, polls: int) -> str:
    return f"key_tap 0x{int(scan):02x} {int(polls or DEFAULT_KEY_POLLS)}"
