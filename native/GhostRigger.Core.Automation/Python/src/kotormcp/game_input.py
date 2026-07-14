"""Win32 input helpers for driving KOTOR's game window during proof runs."""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from ctypes import wintypes
from kotormcp.game_dinput_hook import queue_commands, queue_mouse_click, queue_text


K2_WINDOW_TITLE = "Star Wars: Knights of the Old Republic II: The Sith Lords"
K1_WINDOW_TITLE = "Star Wars: Knights of the Old Republic"


class KotorInputError(RuntimeError):
    """Raised when Windows rejects or cannot route a game input event."""


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    def as_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height,
        }


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUTUNION),
    ]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _POINT(ctypes.Structure):
    _fields_ = [
        ("x", wintypes.LONG),
        ("y", wintypes.LONG),
    ]


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SW_RESTORE = 9
SPI_GETWORKAREA = 0x0030


SCAN_ENTER = 0x1C
SCAN_GRAVE = 0x29
SCAN_SHIFT = 0x2A
SCAN_ESCAPE = 0x01


CHAR_SCANCODES: dict[str, Tuple[int, bool]] = {
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
}


def default_window_title(game: Optional[str]) -> str:
    text = str(game or "k2").strip().lower()
    if text in {"k1", "swkotor", "kotor1"}:
        return K1_WINDOW_TITLE
    return K2_WINDOW_TITLE


class KotorWindowInput:
    """Route real Win32 input to the KOTOR foreground window.

    KOTOR ignores normal synthetic input unless its UI thread is attached to the
    caller before focus is restored. This helper keeps that focus dance in one
    place so MCP proof runs can load saves and type hidden console commands.
    """

    def __init__(
        self,
        window_title: Optional[str] = None,
        *,
        game: Optional[str] = "k2",
        dinput_hook_root: Optional[str | Path] = None,
    ) -> None:
        self.window_title = window_title or default_window_title(game)
        self.dinput_hook_root = Path(dinput_hook_root) if dinput_hook_root else None
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        self._user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        self._user32.FindWindowW.restype = wintypes.HWND
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self._user32.IsWindowVisible.restype = wintypes.BOOL
        self._user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
        self._user32.EnumWindows.restype = wintypes.BOOL
        self._user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
        self._user32.GetWindowRect.restype = wintypes.BOOL
        self._user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
        self._user32.GetClientRect.restype = wintypes.BOOL
        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self._user32.AttachThreadInput.restype = wintypes.BOOL
        self._user32.SwitchToThisWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
        self._user32.SwitchToThisWindow.restype = None
        self._user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.ShowWindow.restype = wintypes.BOOL
        self._user32.BringWindowToTop.argtypes = [wintypes.HWND]
        self._user32.BringWindowToTop.restype = wintypes.BOOL
        self._user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self._user32.SetForegroundWindow.restype = wintypes.BOOL
        self._user32.SetActiveWindow.argtypes = [wintypes.HWND]
        self._user32.SetActiveWindow.restype = wintypes.HWND
        self._user32.SetFocus.argtypes = [wintypes.HWND]
        self._user32.SetFocus.restype = wintypes.HWND
        self._user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self._user32.SetCursorPos.restype = wintypes.BOOL
        self._user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(_POINT)]
        self._user32.ClientToScreen.restype = wintypes.BOOL
        self._user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
        self._user32.SendInput.restype = wintypes.UINT
        self._user32.SystemParametersInfoW.argtypes = [
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.UINT,
        ]
        self._user32.SystemParametersInfoW.restype = wintypes.BOOL
        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    def find_window(self) -> Optional[int]:
        hwnd = int(self._user32.FindWindowW(None, self.window_title) or 0)
        if hwnd:
            return hwnd
        needle = self.window_title.lower()
        found: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(candidate: int, _lparam: int) -> bool:
            if not self._user32.IsWindowVisible(candidate):
                return True
            length = int(self._user32.GetWindowTextLengthW(candidate))
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(candidate, buffer, length + 1)
            title = buffer.value.lower()
            if needle in title or title in needle:
                found.append(int(candidate))
                return False
            return True

        self._user32.EnumWindows(callback, 0)
        return found[0] if found else None

    def require_window(self) -> int:
        hwnd = self.find_window()
        if not hwnd:
            raise KotorInputError(f"KOTOR window was not found: {self.window_title}")
        return hwnd

    def window_title_text(self, hwnd: Optional[int] = None) -> str:
        target = hwnd or self.require_window()
        length = int(self._user32.GetWindowTextLengthW(target))
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(target, buffer, length + 1)
        return buffer.value

    def rect(self, hwnd: Optional[int] = None) -> WindowRect:
        target = hwnd or self.require_window()
        rect = _RECT()
        if not self._user32.GetWindowRect(target, ctypes.byref(rect)):
            raise KotorInputError(f"GetWindowRect failed: {ctypes.get_last_error()}")
        return WindowRect(rect.left, rect.top, rect.right, rect.bottom)

    def status(self) -> dict[str, Any]:
        hwnd = self.find_window()
        if not hwnd:
            return {
                "window_found": False,
                "window_title": self.window_title,
                "hwnd": 0,
            }
        pid = wintypes.DWORD(0)
        thread_id = int(self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))
        foreground = int(self._user32.GetForegroundWindow() or 0)
        return {
            "window_found": True,
            "window_title": self.window_title_text(hwnd),
            "hwnd": hwnd,
            "process_id": int(pid.value),
            "thread_id": thread_id,
            "foreground_hwnd": foreground,
            "is_foreground": foreground == hwnd,
            "rect": self.rect(hwnd).as_dict(),
        }

    def activate(self) -> dict[str, Any]:
        hwnd = self.require_window()
        pid = wintypes.DWORD(0)
        target_tid = int(self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))
        current_tid = int(self._kernel32.GetCurrentThreadId())
        foreground_hwnd = int(self._user32.GetForegroundWindow() or 0)
        foreground_pid = wintypes.DWORD(0)
        foreground_tid = (
            int(self._user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(foreground_pid)))
            if foreground_hwnd
            else 0
        )
        attached_pairs: list[tuple[int, int]] = []
        attach_error = 0
        try:
            seen_pairs: set[tuple[int, int]] = set()
            for first, second in (
                (current_tid, target_tid),
                (current_tid, foreground_tid),
                (target_tid, foreground_tid),
            ):
                if first and second and first != second:
                    pair = (first, second)
                    if pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    if bool(self._user32.AttachThreadInput(first, second, True)):
                        attached_pairs.append(pair)
                    else:
                        attach_error = int(ctypes.get_last_error())
            self._user32.ShowWindow(hwnd, SW_RESTORE)
            self._user32.BringWindowToTop(hwnd)
            self._user32.SwitchToThisWindow(hwnd, True)
            foreground_ok = bool(self._user32.SetForegroundWindow(hwnd))
            self._user32.SetActiveWindow(hwnd)
            self._user32.SetFocus(hwnd)
            time.sleep(0.12)
            if int(self._user32.GetForegroundWindow() or 0) != hwnd:
                self._user32.BringWindowToTop(hwnd)
                foreground_ok = bool(self._user32.SetForegroundWindow(hwnd)) or foreground_ok
                time.sleep(0.12)
            return {
                "hwnd": hwnd,
                "process_id": int(pid.value),
                "target_thread_id": target_tid,
                "current_thread_id": current_tid,
                "foreground_thread_id": foreground_tid,
                "attached_thread_input": bool(attached_pairs),
                "attached_thread_pairs": attached_pairs,
                "attach_error": attach_error,
                "foreground_ok": foreground_ok,
                "is_foreground": int(self._user32.GetForegroundWindow() or 0) == hwnd,
                "rect": self.rect(hwnd).as_dict(),
            }
        finally:
            for first, second in reversed(attached_pairs):
                self._user32.AttachThreadInput(first, second, False)

    def click(
        self,
        x: float,
        y: float,
        *,
        coordinate_space: str = "ratio",
        clicks: int = 1,
        delay_seconds: float = 0.5,
    ) -> dict[str, Any]:
        hwnd = self.require_window()
        focus = self.activate()
        sx, sy = self._screen_point(hwnd, x, y, coordinate_space)
        if not self._user32.SetCursorPos(int(round(sx)), int(round(sy))):
            raise KotorInputError(f"SetCursorPos failed: {ctypes.get_last_error()}")
        hook_results: list[dict[str, Any]] = []
        for _ in range(max(1, int(clicks or 1))):
            if self.dinput_hook_root:
                hook_results.append(queue_mouse_click(self.dinput_hook_root))
            else:
                self._send_mouse(MOUSEEVENTF_LEFTDOWN)
                time.sleep(max(0.01, delay_seconds))
                self._send_mouse(MOUSEEVENTF_LEFTUP)
            time.sleep(max(0.01, delay_seconds))
        return {
            "ok": True,
            "screen_x": int(round(sx)),
            "screen_y": int(round(sy)),
            "coordinate_space": coordinate_space,
            "clicks": max(1, int(clicks or 1)),
            "dinput_hook": bool(self.dinput_hook_root),
            "hook_results": hook_results,
            "focus": focus,
        }

    def type_text(
        self,
        text: str,
        *,
        open_console: bool = False,
        press_enter: bool = False,
        key_delay_seconds: float = 0.035,
    ) -> dict[str, Any]:
        focus = self.activate()
        if self.dinput_hook_root:
            hook = queue_text(
                self.dinput_hook_root,
                text,
                open_console=open_console,
                press_enter=press_enter,
                key_polls=12,
            )
            return {
                "ok": bool(hook.get("ok")),
                "characters": len(text),
                "open_console": open_console,
                "press_enter": press_enter,
                "dinput_hook": True,
                "hook_result": hook,
                "focus": focus,
            }
        if open_console:
            self.tap_scan(SCAN_GRAVE, key_delay_seconds=key_delay_seconds)
            time.sleep(0.25)
        for char in text:
            if char == "\n":
                self.tap_scan(SCAN_ENTER, key_delay_seconds=key_delay_seconds)
                continue
            scan, shifted = self._scan_for_char(char)
            if shifted:
                self._send_key(SCAN_SHIFT, key_up=False)
            self.tap_scan(scan, key_delay_seconds=key_delay_seconds)
            if shifted:
                self._send_key(SCAN_SHIFT, key_up=True)
            time.sleep(max(0.0, key_delay_seconds))
        if press_enter:
            self.tap_scan(SCAN_ENTER, key_delay_seconds=key_delay_seconds)
        return {
            "ok": True,
            "characters": len(text),
            "open_console": open_console,
            "press_enter": press_enter,
            "focus": focus,
        }

    def capture_window(
        self,
        output_path: str,
        *,
        region: str = "client",
        activate: bool = True,
        clip_to_work_area: bool = True,
        settle_seconds: float = 0.25,
    ) -> dict[str, Any]:
        hwnd = self.require_window()
        focus = self.activate() if activate else self.status()
        time.sleep(max(0.0, float(settle_seconds or 0.0)))
        rect = self._capture_rect(hwnd, region)
        if clip_to_work_area:
            rect = self._intersect_rect(rect, self._work_area_rect())
        if rect.width <= 0 or rect.height <= 0:
            raise KotorInputError(f"KOTOR capture rectangle is empty: {rect.as_dict()}")
        try:
            from PIL import ImageGrab  # noqa: PLC0415
        except Exception as exc:  # pragma: no cover - runtime dependency in supported builds
            raise KotorInputError(f"Pillow ImageGrab is unavailable: {exc}") from exc
        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        image.save(path)
        return {
            "ok": True,
            "output_path": str(path.resolve()),
            "region": str(region or "client"),
            "clip_to_work_area": bool(clip_to_work_area),
            "rect": rect.as_dict(),
            "focus": focus,
        }

    def console_command(self, command: str, *, key_delay_seconds: float = 0.035) -> dict[str, Any]:
        return self.type_text(command, open_console=True, press_enter=True, key_delay_seconds=key_delay_seconds)

    def tap_scan(self, scan: int, *, key_delay_seconds: float = 0.035) -> None:
        if self.dinput_hook_root:
            queue_commands(self.dinput_hook_root, [f"key_tap 0x{int(scan):02x} 12"])
            time.sleep(max(0.01, key_delay_seconds))
            return
        self._send_key(scan, key_up=False)
        time.sleep(max(0.01, key_delay_seconds))
        self._send_key(scan, key_up=True)

    def _screen_point(self, hwnd: int, x: float, y: float, coordinate_space: str) -> tuple[float, float]:
        space = str(coordinate_space or "ratio").lower()
        if space == "screen":
            return float(x), float(y)
        if space == "client":
            point = _POINT(int(round(x)), int(round(y)))
            if not self._user32.ClientToScreen(hwnd, ctypes.byref(point)):
                raise KotorInputError(f"ClientToScreen failed: {ctypes.get_last_error()}")
            return float(point.x), float(point.y)
        rect = self.rect(hwnd)
        if space == "window":
            return rect.left + float(x), rect.top + float(y)
        if space == "ratio":
            return rect.left + (rect.width * float(x)), rect.top + (rect.height * float(y))
        raise KotorInputError(f"Unsupported coordinate space: {coordinate_space}")

    def _capture_rect(self, hwnd: int, region: str) -> WindowRect:
        mode = str(region or "client").strip().lower()
        if mode == "window":
            return self.rect(hwnd)
        if mode != "client":
            raise KotorInputError(f"Unsupported capture region: {region}")
        client = _RECT()
        if not self._user32.GetClientRect(hwnd, ctypes.byref(client)):
            raise KotorInputError(f"GetClientRect failed: {ctypes.get_last_error()}")
        top_left = _POINT(client.left, client.top)
        bottom_right = _POINT(client.right, client.bottom)
        if not self._user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
            raise KotorInputError(f"ClientToScreen failed: {ctypes.get_last_error()}")
        if not self._user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
            raise KotorInputError(f"ClientToScreen failed: {ctypes.get_last_error()}")
        return WindowRect(top_left.x, top_left.y, bottom_right.x, bottom_right.y)

    def _work_area_rect(self) -> WindowRect:
        rect = _RECT()
        if not self._user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            raise KotorInputError(f"SystemParametersInfoW(SPI_GETWORKAREA) failed: {ctypes.get_last_error()}")
        return WindowRect(rect.left, rect.top, rect.right, rect.bottom)

    def _intersect_rect(self, first: WindowRect, second: WindowRect) -> WindowRect:
        return WindowRect(
            max(first.left, second.left),
            max(first.top, second.top),
            min(first.right, second.right),
            min(first.bottom, second.bottom),
        )

    def _scan_for_char(self, char: str) -> Tuple[int, bool]:
        if char.isalpha():
            scan, _shifted = CHAR_SCANCODES[char.lower()]
            return scan, char.isupper()
        if char in CHAR_SCANCODES:
            return CHAR_SCANCODES[char]
        raise KotorInputError(f"Unsupported text character for scancode input: {char!r}")

    def _send_mouse(self, flags: int) -> None:
        item = _INPUT()
        item.type = INPUT_MOUSE
        item.u.mi = _MOUSEINPUT(0, 0, 0, flags, 0, None)
        self._send_input(item)

    def _send_key(self, scan: int, *, key_up: bool) -> None:
        item = _INPUT()
        item.type = INPUT_KEYBOARD
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
        item.u.ki = _KEYBDINPUT(0, int(scan), flags, 0, None)
        self._send_input(item)

    def _send_input(self, item: _INPUT) -> None:
        array = (_INPUT * 1)()
        array[0] = item
        sent = int(self._user32.SendInput(1, array, ctypes.sizeof(_INPUT)))
        if sent != 1:
            raise KotorInputError(f"SendInput failed: {ctypes.get_last_error()}")


def run_save_warp_route(
    controller: KotorWindowInput,
    *,
    target_module: str,
    start_screen: str = "main_menu",
    save_row_index: int = 1,
    main_menu_load_ratio: tuple[float, float] = (0.604, 0.547),
    save_row_ratio: tuple[float, float] = (0.302, 0.266),
    save_row_step_ratio: float = 0.039,
    load_button_ratio: tuple[float, float] = (0.334, 0.882),
    after_menu_seconds: float = 2.0,
    after_load_seconds: float = 12.0,
    after_warp_seconds: float = 15.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    screen = str(start_screen or "main_menu").lower()
    if screen == "main_menu":
        actions.append({"action": "click_load_game", **controller.click(*main_menu_load_ratio, coordinate_space="ratio")})
        sleep_fn(max(0.1, after_menu_seconds))
    elif screen not in {"load_screen", "in_game"}:
        raise KotorInputError("start_screen must be one of: main_menu, load_screen, in_game")

    if screen in {"main_menu", "load_screen"}:
        row_x, row_y = save_row_ratio
        target_y = row_y + (max(0, int(save_row_index)) * float(save_row_step_ratio))
        actions.append(
            {
                "action": "click_save_row",
                "save_row_index": int(save_row_index),
                **controller.click(row_x, target_y, coordinate_space="ratio"),
            }
        )
        sleep_fn(0.5)
        actions.append({"action": "click_load_save", **controller.click(*load_button_ratio, coordinate_space="ratio")})
        sleep_fn(max(1.0, after_load_seconds))

    command = f"warp {target_module}"
    actions.append({"action": "console_command", "command": command, **controller.console_command(command)})
    sleep_fn(max(1.0, after_warp_seconds))
    return {
        "ok": True,
        "target_module": target_module,
        "start_screen": start_screen,
        "save_row_index": int(save_row_index),
        "actions": actions,
        "final_status": controller.status(),
    }
