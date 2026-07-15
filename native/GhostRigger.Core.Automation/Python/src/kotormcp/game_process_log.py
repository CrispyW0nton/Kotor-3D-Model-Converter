"""Live KOTOR process logging for in-game mod proof runs.

The logger attaches to the running game with the Windows debug API.  It does
not patch game code; it records the same exception/module events a debugger
would see, then pairs them with Override file fingerprints so each crash has a
reproducible mod context.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from ctypes import wintypes


KOTOR_EXE_BY_GAME = {
    "k1": "swkotor.exe",
    "swkotor": "swkotor.exe",
    "kotor1": "swkotor.exe",
    "k2": "swkotor2.exe",
    "tsl": "swkotor2.exe",
    "kotor2": "swkotor2.exe",
}

KOTOR_STATIC_IMAGE_BASE = 0x00400000
DEFAULT_SESSION_SECONDS = 900


TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
PROCESS_VM_READ = 0x0010
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
WOW64_CONTEXT_i386 = 0x00010000
WOW64_CONTEXT_CONTROL = WOW64_CONTEXT_i386 | 0x00000001
WOW64_CONTEXT_INTEGER = WOW64_CONTEXT_i386 | 0x00000002
WOW64_CONTEXT_SEGMENTS = WOW64_CONTEXT_i386 | 0x00000004
WOW64_CONTEXT_FULL = WOW64_CONTEXT_CONTROL | WOW64_CONTEXT_INTEGER | WOW64_CONTEXT_SEGMENTS
WOW64_MAXIMUM_SUPPORTED_EXTENSION = 512

EXCEPTION_DEBUG_EVENT = 1
CREATE_THREAD_DEBUG_EVENT = 2
CREATE_PROCESS_DEBUG_EVENT = 3
EXIT_THREAD_DEBUG_EVENT = 4
EXIT_PROCESS_DEBUG_EVENT = 5
LOAD_DLL_DEBUG_EVENT = 6
UNLOAD_DLL_DEBUG_EVENT = 7
OUTPUT_DEBUG_STRING_EVENT = 8
RIP_EVENT = 9

DBG_CONTINUE = 0x00010002
DBG_EXCEPTION_NOT_HANDLED = 0x80010001

EXCEPTION_ACCESS_VIOLATION = 0xC0000005
EXCEPTION_BREAKPOINT = 0x80000003
EXCEPTION_SINGLE_STEP = 0x80000004
MS_VC_THREAD_NAME_EXCEPTION = 0x406D1388
HANDLED_DEBUGGER_EXCEPTIONS = {
    EXCEPTION_BREAKPOINT,
    EXCEPTION_SINGLE_STEP,
    MS_VC_THREAD_NAME_EXCEPTION,
}


ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


class EXCEPTION_RECORD(ctypes.Structure):
    _fields_ = [
        ("ExceptionCode", wintypes.DWORD),
        ("ExceptionFlags", wintypes.DWORD),
        ("ExceptionRecord", ULONG_PTR),
        ("ExceptionAddress", ULONG_PTR),
        ("NumberParameters", wintypes.DWORD),
        ("ExceptionInformation", ULONG_PTR * 15),
    ]


class EXCEPTION_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("ExceptionRecord", EXCEPTION_RECORD),
        ("dwFirstChance", wintypes.DWORD),
    ]


class CREATE_THREAD_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hThread", wintypes.HANDLE),
        ("lpThreadLocalBase", ULONG_PTR),
        ("lpStartAddress", ULONG_PTR),
    ]


class CREATE_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("lpBaseOfImage", ULONG_PTR),
        ("dwDebugInfoFileOffset", wintypes.DWORD),
        ("nDebugInfoSize", wintypes.DWORD),
        ("lpThreadLocalBase", ULONG_PTR),
        ("lpStartAddress", ULONG_PTR),
        ("lpImageName", ULONG_PTR),
        ("fUnicode", wintypes.WORD),
    ]


class EXIT_THREAD_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("dwExitCode", wintypes.DWORD)]


class EXIT_PROCESS_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("dwExitCode", wintypes.DWORD)]


class LOAD_DLL_DEBUG_INFO(ctypes.Structure):
    _fields_ = [
        ("hFile", wintypes.HANDLE),
        ("lpBaseOfDll", ULONG_PTR),
        ("dwDebugInfoFileOffset", wintypes.DWORD),
        ("nDebugInfoSize", wintypes.DWORD),
        ("lpImageName", ULONG_PTR),
        ("fUnicode", wintypes.WORD),
    ]


class UNLOAD_DLL_DEBUG_INFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ULONG_PTR)]


class OUTPUT_DEBUG_STRING_INFO(ctypes.Structure):
    _fields_ = [
        ("lpDebugStringData", ULONG_PTR),
        ("fUnicode", wintypes.WORD),
        ("nDebugStringLength", wintypes.WORD),
    ]


class RIP_INFO(ctypes.Structure):
    _fields_ = [
        ("dwError", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
    ]


class DEBUG_EVENT_UNION(ctypes.Union):
    _fields_ = [
        ("Exception", EXCEPTION_DEBUG_INFO),
        ("CreateThread", CREATE_THREAD_DEBUG_INFO),
        ("CreateProcessInfo", CREATE_PROCESS_DEBUG_INFO),
        ("ExitThread", EXIT_THREAD_DEBUG_INFO),
        ("ExitProcess", EXIT_PROCESS_DEBUG_INFO),
        ("LoadDll", LOAD_DLL_DEBUG_INFO),
        ("UnloadDll", UNLOAD_DLL_DEBUG_INFO),
        ("DebugString", OUTPUT_DEBUG_STRING_INFO),
        ("RipInfo", RIP_INFO),
    ]


class DEBUG_EVENT(ctypes.Structure):
    _fields_ = [
        ("dwDebugEventCode", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
        ("u", DEBUG_EVENT_UNION),
    ]


class WOW64_FLOATING_SAVE_AREA(ctypes.Structure):
    _fields_ = [
        ("ControlWord", wintypes.DWORD),
        ("StatusWord", wintypes.DWORD),
        ("TagWord", wintypes.DWORD),
        ("ErrorOffset", wintypes.DWORD),
        ("ErrorSelector", wintypes.DWORD),
        ("DataOffset", wintypes.DWORD),
        ("DataSelector", wintypes.DWORD),
        ("RegisterArea", ctypes.c_ubyte * 80),
        ("Cr0NpxState", wintypes.DWORD),
    ]


class WOW64_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("ContextFlags", wintypes.DWORD),
        ("Dr0", wintypes.DWORD),
        ("Dr1", wintypes.DWORD),
        ("Dr2", wintypes.DWORD),
        ("Dr3", wintypes.DWORD),
        ("Dr6", wintypes.DWORD),
        ("Dr7", wintypes.DWORD),
        ("FloatSave", WOW64_FLOATING_SAVE_AREA),
        ("SegGs", wintypes.DWORD),
        ("SegFs", wintypes.DWORD),
        ("SegEs", wintypes.DWORD),
        ("SegDs", wintypes.DWORD),
        ("Edi", wintypes.DWORD),
        ("Esi", wintypes.DWORD),
        ("Ebx", wintypes.DWORD),
        ("Edx", wintypes.DWORD),
        ("Ecx", wintypes.DWORD),
        ("Eax", wintypes.DWORD),
        ("Ebp", wintypes.DWORD),
        ("Eip", wintypes.DWORD),
        ("SegCs", wintypes.DWORD),
        ("EFlags", wintypes.DWORD),
        ("Esp", wintypes.DWORD),
        ("SegSs", wintypes.DWORD),
        ("ExtendedRegisters", ctypes.c_ubyte * WOW64_MAXIMUM_SUPPORTED_EXTENSION),
    ]


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    parent_pid: int
    exe: str
    threads: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "parent_pid": self.parent_pid,
            "exe": self.exe,
            "threads": self.threads,
        }


class Win32ProcessProbe:
    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure()

    def _configure(self) -> None:
        k = self.kernel32
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32FirstW.restype = wintypes.BOOL
        k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.Process32NextW.restype = wintypes.BOOL
        k.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
        k.Module32FirstW.restype = wintypes.BOOL
        k.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
        k.Module32NextW.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.CloseHandle.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenThread.restype = wintypes.HANDLE
        k.ReadProcessMemory.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.LPVOID,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        k.ReadProcessMemory.restype = wintypes.BOOL
        if hasattr(k, "Wow64GetThreadContext"):
            k.Wow64GetThreadContext.argtypes = [wintypes.HANDLE, ctypes.POINTER(WOW64_CONTEXT)]
            k.Wow64GetThreadContext.restype = wintypes.BOOL
        k.DebugActiveProcess.argtypes = [wintypes.DWORD]
        k.DebugActiveProcess.restype = wintypes.BOOL
        k.DebugActiveProcessStop.argtypes = [wintypes.DWORD]
        k.DebugActiveProcessStop.restype = wintypes.BOOL
        k.DebugSetProcessKillOnExit.argtypes = [wintypes.BOOL]
        k.DebugSetProcessKillOnExit.restype = wintypes.BOOL
        k.WaitForDebugEvent.argtypes = [ctypes.POINTER(DEBUG_EVENT), wintypes.DWORD]
        k.WaitForDebugEvent.restype = wintypes.BOOL
        k.ContinueDebugEvent.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        k.ContinueDebugEvent.restype = wintypes.BOOL

    def processes(self) -> list[ProcessInfo]:
        handle = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if int(handle) == INVALID_HANDLE_VALUE:
            return []
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            rows: list[ProcessInfo] = []
            ok = bool(self.kernel32.Process32FirstW(handle, ctypes.byref(entry)))
            while ok:
                rows.append(
                    ProcessInfo(
                        pid=int(entry.th32ProcessID),
                        parent_pid=int(entry.th32ParentProcessID),
                        exe=str(entry.szExeFile),
                        threads=int(entry.cntThreads),
                    )
                )
                ok = bool(self.kernel32.Process32NextW(handle, ctypes.byref(entry)))
            return rows
        finally:
            self.kernel32.CloseHandle(handle)

    def find_process(self, names: Iterable[str]) -> Optional[ProcessInfo]:
        wanted = {name.lower() for name in names if name}
        candidates = [proc for proc in self.processes() if proc.exe.lower() in wanted]
        if not candidates:
            return None
        return sorted(candidates, key=lambda proc: proc.pid)[-1]

    def process_exists(self, pid: int) -> bool:
        handle = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD(0)
            return bool(
                self.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                and int(exit_code.value) == STILL_ACTIVE
            )
        finally:
            self.kernel32.CloseHandle(handle)

    def modules(self, pid: int) -> list[dict[str, Any]]:
        flags = TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
        handle = self.kernel32.CreateToolhelp32Snapshot(flags, int(pid))
        if int(handle) == INVALID_HANDLE_VALUE:
            return []
        try:
            entry = MODULEENTRY32W()
            entry.dwSize = ctypes.sizeof(MODULEENTRY32W)
            rows: list[dict[str, Any]] = []
            ok = bool(self.kernel32.Module32FirstW(handle, ctypes.byref(entry)))
            while ok:
                base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value or 0
                size = int(entry.modBaseSize)
                rows.append(
                    {
                        "name": str(entry.szModule),
                        "path": str(entry.szExePath),
                        "base": base,
                        "base_hex": f"0x{base:08x}",
                        "size": size,
                        "end": base + size,
                        "end_hex": f"0x{base + size:08x}",
                    }
                )
                ok = bool(self.kernel32.Module32NextW(handle, ctypes.byref(entry)))
            return rows
        finally:
            self.kernel32.CloseHandle(handle)

    def wow64_thread_context(self, thread_id: int) -> dict[str, Any]:
        if not hasattr(self.kernel32, "Wow64GetThreadContext"):
            return {"available": False, "error": "Wow64GetThreadContext unavailable"}
        handle = self.kernel32.OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, False, int(thread_id))
        if not handle:
            return {"available": False, "error": f"OpenThread failed: {int(ctypes.get_last_error())}"}
        try:
            context = WOW64_CONTEXT()
            context.ContextFlags = WOW64_CONTEXT_FULL
            if not self.kernel32.Wow64GetThreadContext(handle, ctypes.byref(context)):
                return {
                    "available": False,
                    "error": f"Wow64GetThreadContext failed: {int(ctypes.get_last_error())}",
                }
            registers = {
                "eax": int(context.Eax),
                "ebx": int(context.Ebx),
                "ecx": int(context.Ecx),
                "edx": int(context.Edx),
                "esi": int(context.Esi),
                "edi": int(context.Edi),
                "ebp": int(context.Ebp),
                "esp": int(context.Esp),
                "eip": int(context.Eip),
                "eflags": int(context.EFlags),
            }
            return {
                "available": True,
                **registers,
                **{f"{key}_hex": f"0x{value:08x}" for key, value in registers.items()},
            }
        finally:
            self.kernel32.CloseHandle(handle)

    def read_memory(self, pid: int, address: int, length: int) -> bytes:
        if address <= 0 or length <= 0:
            return b""
        handle = self.kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
            False,
            int(pid),
        )
        if not handle:
            return b""
        try:
            buf = (ctypes.c_ubyte * int(length))()
            read = ctypes.c_size_t(0)
            ok = self.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(int(address)),
                ctypes.byref(buf),
                int(length),
                ctypes.byref(read),
            )
            if not ok or read.value <= 0:
                return b""
            return bytes(buf[: read.value])
        finally:
            self.kernel32.CloseHandle(handle)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch() -> float:
    return time.time()


def _repo_root() -> Path:
    env_root = os.environ.get("GHOSTRIGGER_ROOT")
    if env_root:
        return Path(env_root).resolve()
    path = Path(__file__).resolve()
    for parent in [path, *path.parents]:
        if (parent / ".git").exists() or (parent / "CHANGES.md").exists():
            return parent
    return Path.cwd().resolve()


def _clean_session_label(label: Optional[str]) -> str:
    raw = str(label or "kotor-live").strip().lower()
    cleaned = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip(".-")
    return cleaned[:48] or "kotor-live"


def _game_key(game: str) -> str:
    text = str(game or "k2").strip().lower()
    return text if text in KOTOR_EXE_BY_GAME else "k2"


def default_session_root() -> Path:
    return _repo_root() / "Saved" / "KotorLiveLogs"


def make_session_id(label: Optional[str]) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{_clean_session_label(label)}"


def start_log_session(
    *,
    game: str = "k2",
    game_root: Optional[str] = None,
    session_label: Optional[str] = None,
    pid: Optional[int] = None,
    wait_for_process: bool = True,
    duration_seconds: int = DEFAULT_SESSION_SECONDS,
    asset_resrefs: Optional[list[str]] = None,
    session_root: Optional[str] = None,
) -> dict[str, Any]:
    root = Path(session_root).resolve() if session_root else default_session_root()
    session_id = make_session_id(session_label)
    session_dir = root / session_id
    session_dir.mkdir(parents=True, exist_ok=False)

    args = [
        sys.executable,
        "-m",
        "kotormcp.game_process_log",
        "monitor",
        "--game",
        _game_key(game),
        "--session-dir",
        str(session_dir),
        "--duration-seconds",
        str(max(5, int(duration_seconds or DEFAULT_SESSION_SECONDS))),
    ]
    if game_root:
        args.extend(["--game-root", str(Path(game_root))])
    if pid:
        args.extend(["--pid", str(int(pid))])
    if wait_for_process:
        args.append("--wait-for-process")
    for resref in asset_resrefs or ["c_drexlf", "appearance"]:
        if resref:
            args.extend(["--asset-resref", str(resref)])

    creationflags = 0x08000000 if os.name == "nt" else 0
    env = os.environ.copy()
    pythonpath_parts = [str(path) for path in sys.path if path]
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in pythonpath_parts + ([existing_pythonpath] if existing_pythonpath else []) if item
    )
    env.setdefault("GHOSTRIGGER_ROOT", str(_repo_root()))
    proc = subprocess.Popen(  # noqa: S603
        args,
        cwd=str(_repo_root()),
        env=env,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    metadata = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "helper_pid": int(proc.pid),
        "game": _game_key(game),
        "game_root": str(game_root or ""),
        "target_pid": int(pid) if pid else None,
        "duration_seconds": max(5, int(duration_seconds or DEFAULT_SESSION_SECONDS)),
        "asset_resrefs": asset_resrefs or ["c_drexlf", "appearance"],
        "started_at": _utc_now(),
        "events_path": str(session_dir / "events.jsonl"),
        "summary_path": str(session_dir / "summary.json"),
    }
    _write_json(session_dir / "session.json", metadata)
    return metadata


def request_stop(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir)
    path.mkdir(parents=True, exist_ok=True)
    marker = path / "stop.request"
    marker.write_text(_utc_now(), encoding="utf-8")
    return {"ok": True, "session_dir": str(path), "stop_request": str(marker)}


def read_session_status(session_dir: str | Path) -> dict[str, Any]:
    path = Path(session_dir)
    session = _read_json(path / "session.json")
    summary = _read_json(path / "summary.json")
    helper_pid = int(session.get("helper_pid") or 0)
    probe = Win32ProcessProbe()
    return {
        "session_dir": str(path),
        "session": session,
        "summary": summary,
        "helper_running": bool(helper_pid and probe.process_exists(helper_pid)),
        "events_path": str(path / "events.jsonl"),
        "events_count": _jsonl_count(path / "events.jsonl"),
        "stop_requested": (path / "stop.request").is_file(),
    }


def find_latest_session(session_root: Optional[str] = None) -> Optional[Path]:
    root = Path(session_root).resolve() if session_root else default_session_root()
    if not root.is_dir():
        return None
    sessions = [path for path in root.iterdir() if path.is_dir()]
    return sorted(sessions, key=lambda item: item.stat().st_mtime)[-1] if sessions else None


def analyze_session(
    session_dir: str | Path,
    *,
    annotate_with_ghidra: bool = True,
    game: str = "k2",
    ghidra_program: Optional[str] = None,
) -> dict[str, Any]:
    path = Path(session_dir)
    events = list(_read_jsonl(path / "events.jsonl"))
    exceptions = [event for event in events if event.get("event") == "exception"]
    crashes = [
        event
        for event in exceptions
        if _is_crash_exception(event)
    ]

    annotations: list[dict[str, Any]] = []
    if annotate_with_ghidra:
        for event in crashes[:5]:
            annotation = annotate_exception_with_ghidra(event, game=game, ghidra_program=ghidra_program)
            if annotation:
                annotations.append(annotation)

    summary = _read_json(path / "summary.json")
    summary.update(
        {
            "analysis_generated_at": _utc_now(),
            "exception_count": len(exceptions),
            "crash_count": len(crashes),
            "crashes": crashes,
            "ghidra_annotations": annotations,
        }
    )
    _write_json(path / "analysis.json", summary)
    _write_text_summary(path / "analysis.txt", summary)
    return summary


def annotate_exception_with_ghidra(
    event: dict[str, Any],
    *,
    game: str = "k2",
    ghidra_program: Optional[str] = None,
) -> dict[str, Any]:
    address_hex = event.get("ghidra_address") or event.get("address_hex")
    if not address_hex:
        return {}
    game_key = _game_key(game)
    try:
        from kotormcp.adapters_decompile import get_client  # noqa: PLC0415
    except Exception as exc:
        return {"address": address_hex, "error": f"Could not import AgentDecompile client: {exc}"}

    try:
        client = get_client()
        program_candidates = _ghidra_program_candidates(client, game_key, ghidra_program)
        result: dict[str, Any] = {}
        program_path = program_candidates[0]
        for candidate in program_candidates:
            program_path = candidate
            result = client.decompile_function(candidate, str(address_hex), limit=80, include_comments=True)
            if "error" not in result:
                break
    except Exception as exc:
        return {"address": address_hex, "error": f"Ghidra annotation failed: {exc}"}

    if "error" in result:
        return {"address": address_hex, "program_path": program_path, "error": result.get("error")}

    instruction = _instruction_at(result, str(address_hex))
    return {
        "address": address_hex,
        "program_path": program_path,
        "function": result.get("name") or result.get("function"),
        "function_address": result.get("address"),
        "signature": result.get("signature"),
        "decompilation": result.get("decompilation"),
        "instruction": instruction,
        "metadata": result.get("metadata", {}),
    }


def _ghidra_program_candidates(client: Any, game_key: str, explicit_program: Optional[str]) -> list[str]:
    if explicit_program:
        return [explicit_program]
    candidates = [client.resolve_program_path(game_key)]
    if game_key in {"k2", "tsl", "kotor2"}:
        steam = client.resolve_program_path("k2_steam")
        if steam not in candidates:
            candidates.append(steam)
    return candidates


def _instruction_at(result: dict[str, Any], address_hex: str) -> dict[str, Any]:
    needle = address_hex.lower().replace("0x", "").rjust(8, "0")
    for item in result.get("disassembly", {}).get("instructions", []) or []:
        address = str(item.get("address", "")).lower().replace("0x", "").rjust(8, "0")
        if address == needle:
            return item
    return {}


def run_monitor(
    *,
    game: str,
    session_dir: str,
    game_root: Optional[str],
    pid: Optional[int],
    wait_for_process: bool,
    duration_seconds: int,
    asset_resrefs: list[str],
) -> int:
    session_path = Path(session_dir)
    session_path.mkdir(parents=True, exist_ok=True)
    writer = EventWriter(session_path)
    game_key = _game_key(game)
    exe_name = KOTOR_EXE_BY_GAME[game_key]
    started_epoch = _epoch()
    context = {
        "event": "session_start",
        "timestamp": _utc_now(),
        "epoch": started_epoch,
        "game": game_key,
        "exe_name": exe_name,
        "game_root": str(game_root or ""),
        "asset_resrefs": asset_resrefs,
        "override_assets": summarize_override_assets(game_root, asset_resrefs),
        "runtime_files": summarize_runtime_files(game_root),
        "game_logs": summarize_game_logs(game_root),
    }
    writer.write(context)

    probe = Win32ProcessProbe()
    target = None
    if pid:
        target = ProcessInfo(pid=int(pid), parent_pid=0, exe=exe_name, threads=0)
    elif wait_for_process:
        deadline = time.time() + max(5, duration_seconds)
        while time.time() < deadline and not _stop_requested(session_path):
            target = probe.find_process([exe_name])
            if target:
                break
            time.sleep(0.5)
    else:
        target = probe.find_process([exe_name])

    if not target:
        writer.write({"event": "process_not_found", "timestamp": _utc_now(), "exe_name": exe_name})
        _finalize_summary(session_path, writer, probe, started_epoch, game_root, asset_resrefs)
        return 2

    writer.write({"event": "process_selected", "timestamp": _utc_now(), "process": target.as_dict()})
    modules = probe.modules(target.pid)
    module_inventory = summarize_module_inventory(modules, game_root=game_root)
    _write_json(session_path / "module_inventory.json", {"pid": target.pid, "modules": module_inventory})
    attached = bool(probe.kernel32.DebugActiveProcess(int(target.pid)))
    if not attached:
        error = int(ctypes.get_last_error())
        writer.write({"event": "debug_attach_failed", "timestamp": _utc_now(), "pid": target.pid, "last_error": error})
        writer.write(
            {
                "event": "monitor_fallback",
                "timestamp": _utc_now(),
                "pid": target.pid,
                "mode": "process_liveness",
                "reason": "debug_attach_denied" if error == 5 else "debug_attach_failed",
                "last_error": error,
                "modules": module_inventory,
            }
        )
        _poll_until_exit(session_path, writer, probe, target.pid, started_epoch, duration_seconds)
        _finalize_summary(session_path, writer, probe, started_epoch, game_root, asset_resrefs)
        return 0

    probe.kernel32.DebugSetProcessKillOnExit(False)
    writer.write(
        {
            "event": "debug_attached",
            "timestamp": _utc_now(),
            "pid": target.pid,
            "modules": module_inventory,
        }
    )

    exit_code = 0
    try:
        deadline = time.time() + max(5, duration_seconds)
        while time.time() < deadline and not _stop_requested(session_path):
            debug_event = DEBUG_EVENT()
            if not probe.kernel32.WaitForDebugEvent(ctypes.byref(debug_event), 500):
                if not probe.process_exists(target.pid):
                    writer.write({"event": "process_missing", "timestamp": _utc_now(), "pid": target.pid})
                    break
                continue
            event_dict, continue_status = _debug_event_to_dict(debug_event, probe, target.pid)
            writer.write(event_dict)
            probe.kernel32.ContinueDebugEvent(
                int(debug_event.dwProcessId),
                int(debug_event.dwThreadId),
                continue_status,
            )
            if event_dict.get("event") == "process_exit":
                exit_code = int(event_dict.get("exit_code") or 0)
                break
    finally:
        probe.kernel32.DebugActiveProcessStop(int(target.pid))
    _finalize_summary(session_path, writer, probe, started_epoch, game_root, asset_resrefs, exit_code=exit_code)
    return exit_code


class EventWriter:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.events_path = session_dir / "events.jsonl"

    def write(self, event: dict[str, Any]) -> None:
        event.setdefault("timestamp", _utc_now())
        event.setdefault("epoch", _epoch())
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def _walk_ebp_frames(probe: "Win32ProcessProbe", pid: int, context: dict, modules) -> list[dict[str, Any]]:
    """Walk the EBP chain at exception time, previewing string arguments.

    For crashes inside name-lookup loops this recovers the name the engine
    was searching for (e.g. FUN_0046e9b0's char* param at [caller_ebp+0xC]).
    """

    import struct as _struct

    frames: list[dict[str, Any]] = []
    ebp = int(context.get("ebp") or 0)
    for _ in range(6):
        if ebp <= 0x1000:
            break
        raw = probe.read_memory(pid, ebp, 8 + 4 * 4)
        if len(raw) < 8:
            break
        next_ebp, ret = _struct.unpack_from("<II", raw, 0)
        args = list(_struct.unpack_from("<IIII", raw, 8)) if len(raw) >= 24 else []
        frame: dict[str, Any] = {
            "return_hex": f"0x{ret:08x}",
            "module": module_for_address(modules, ret),
            "args_hex": [f"0x{a:08x}" for a in args],
        }
        previews = []
        for arg in args:
            if 0x10000 < arg < 0x7FFF0000:
                blob = probe.read_memory(pid, arg, 48)
                if blob:
                    text = blob.split(b"\x00", 1)[0]
                    if 1 <= len(text) <= 47 and all(32 <= b < 127 for b in text):
                        previews.append(text.decode("ascii", errors="replace"))
                    else:
                        previews.append("")
                else:
                    previews.append("")
            else:
                previews.append("")
        frame["arg_strings"] = previews
        frames.append(frame)
        if next_ebp <= ebp:
            break
        ebp = next_ebp
    return frames


def _debug_event_to_dict(event: DEBUG_EVENT, probe: Win32ProcessProbe, pid: int) -> tuple[dict[str, Any], int]:
    code = int(event.dwDebugEventCode)
    base = {
        "debug_event_code": code,
        "process_id": int(event.dwProcessId),
        "thread_id": int(event.dwThreadId),
    }
    if code == EXCEPTION_DEBUG_EVENT:
        info = event.u.Exception
        record = info.ExceptionRecord
        address = int(record.ExceptionAddress or 0)
        modules = probe.modules(pid)
        module = module_for_address(modules, address)
        detail = {
            **base,
            "event": "exception",
            "exception_code": int(record.ExceptionCode),
            "exception_code_hex": f"0x{int(record.ExceptionCode):08x}",
            "exception_name": exception_name(int(record.ExceptionCode)),
            "exception_flags": int(record.ExceptionFlags),
            "address": address,
            "address_hex": f"0x{address:08x}",
            "first_chance": bool(info.dwFirstChance),
            "module": module,
            "exception_parameters": [int(record.ExceptionInformation[i]) for i in range(int(record.NumberParameters))],
        }
        context = probe.wow64_thread_context(int(event.dwThreadId))
        detail["thread_context"] = context
        if context.get("available"):
            esp = int(context.get("esp") or 0)
            stack_bytes = probe.read_memory(pid, esp, 16 * 4)
            detail["stack"] = _stack_sample(stack_bytes, esp, modules)
            detail["frames"] = _walk_ebp_frames(probe, pid, context, modules)
        detail.update(ghidra_address_fields(detail))
        if int(record.ExceptionCode) in HANDLED_DEBUGGER_EXCEPTIONS:
            continue_status = DBG_CONTINUE
        else:
            continue_status = DBG_EXCEPTION_NOT_HANDLED if int(record.ExceptionCode) else DBG_CONTINUE
        return detail, continue_status
    if code == CREATE_PROCESS_DEBUG_EVENT:
        info = event.u.CreateProcessInfo
        return (
            {
                **base,
                "event": "process_create",
                "image_base": int(info.lpBaseOfImage or 0),
                "image_base_hex": f"0x{int(info.lpBaseOfImage or 0):08x}",
                "start_address": int(info.lpStartAddress or 0),
                "start_address_hex": f"0x{int(info.lpStartAddress or 0):08x}",
            },
            DBG_CONTINUE,
        )
    if code == EXIT_PROCESS_DEBUG_EVENT:
        return ({**base, "event": "process_exit", "exit_code": int(event.u.ExitProcess.dwExitCode)}, DBG_CONTINUE)
    if code == LOAD_DLL_DEBUG_EVENT:
        info = event.u.LoadDll
        address = int(info.lpBaseOfDll or 0)
        return (
            {
                **base,
                "event": "dll_load",
                "base": address,
                "base_hex": f"0x{address:08x}",
                "modules": probe.modules(pid),
            },
            DBG_CONTINUE,
        )
    if code == UNLOAD_DLL_DEBUG_EVENT:
        address = int(event.u.UnloadDll.lpBaseOfDll or 0)
        return ({**base, "event": "dll_unload", "base": address, "base_hex": f"0x{address:08x}"}, DBG_CONTINUE)
    if code == CREATE_THREAD_DEBUG_EVENT:
        info = event.u.CreateThread
        return (
            {
                **base,
                "event": "thread_create",
                "start_address": int(info.lpStartAddress or 0),
                "start_address_hex": f"0x{int(info.lpStartAddress or 0):08x}",
            },
            DBG_CONTINUE,
        )
    if code == EXIT_THREAD_DEBUG_EVENT:
        return ({**base, "event": "thread_exit", "exit_code": int(event.u.ExitThread.dwExitCode)}, DBG_CONTINUE)
    if code == OUTPUT_DEBUG_STRING_EVENT:
        info = event.u.DebugString
        length = int(info.nDebugStringLength)
        is_unicode = bool(info.fUnicode)
        # Read the actual string from the debugee — the game logs its
        # resource-load progress/errors here (CRes/CModule/CArea messages),
        # which name exactly what fails during a crash.
        text = ""
        addr = int(info.lpDebugStringData or 0)
        if addr and 0 < length <= 4096:
            raw = probe.read_memory(pid, addr, length * (2 if is_unicode else 1))
            if raw:
                try:
                    text = raw.decode("utf-16-le" if is_unicode else "latin-1", errors="replace")
                except Exception:
                    text = ""
                text = text.split("\x00", 1)[0].rstrip("\r\n")
        return (
            {
                **base,
                "event": "debug_string",
                "length": length,
                "unicode": is_unicode,
                "text": text,
            },
            DBG_CONTINUE,
        )
    if code == RIP_EVENT:
        info = event.u.RipInfo
        return ({**base, "event": "rip", "error": int(info.dwError), "type": int(info.dwType)}, DBG_CONTINUE)
    return ({**base, "event": "debug_event"}, DBG_CONTINUE)


def exception_name(code: int) -> str:
    if code == EXCEPTION_ACCESS_VIOLATION:
        return "EXCEPTION_ACCESS_VIOLATION"
    if code == EXCEPTION_BREAKPOINT:
        return "EXCEPTION_BREAKPOINT"
    if code == EXCEPTION_SINGLE_STEP:
        return "EXCEPTION_SINGLE_STEP"
    if code == MS_VC_THREAD_NAME_EXCEPTION:
        return "MS_VC_THREAD_NAME_EXCEPTION"
    return "UNKNOWN"


def _is_crash_exception(event: dict[str, Any]) -> bool:
    code = int(event.get("exception_code") or 0)
    if code in HANDLED_DEBUGGER_EXCEPTIONS:
        return False
    if code == EXCEPTION_ACCESS_VIOLATION:
        return True
    return not bool(event.get("first_chance", True))


def module_for_address(modules: list[dict[str, Any]], address: int) -> dict[str, Any]:
    for module in modules:
        base = int(module.get("base") or 0)
        end = int(module.get("end") or 0)
        if base <= address < end:
            offset = address - base
            return {
                **module,
                "offset": offset,
                "offset_hex": f"0x{offset:08x}",
            }
    return {}


def _stack_sample(data: bytes, base_address: int, modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    count = len(data) // 4
    for index in range(count):
        value = int.from_bytes(data[index * 4:index * 4 + 4], "little", signed=False)
        module = module_for_address(modules, value)
        row = {
            "index": index,
            "address": base_address + index * 4,
            "address_hex": f"0x{base_address + index * 4:08x}",
            "value": value,
            "value_hex": f"0x{value:08x}",
        }
        if module:
            row["module"] = {
                "name": module.get("name"),
                "offset": module.get("offset"),
                "offset_hex": module.get("offset_hex"),
            }
        rows.append(row)
    return rows


def ghidra_address_fields(event: dict[str, Any]) -> dict[str, Any]:
    module = event.get("module") or {}
    offset = module.get("offset")
    if offset is None:
        return {}
    name = str(module.get("name") or "").lower()
    if name not in {"swkotor.exe", "swkotor2.exe"}:
        return {}
    ghidra_address = KOTOR_STATIC_IMAGE_BASE + int(offset)
    return {
        "module_offset": int(offset),
        "module_offset_hex": f"0x{int(offset):08x}",
        "ghidra_address": f"0x{ghidra_address:08x}",
    }


def summarize_override_assets(game_root: Optional[str], resrefs: list[str]) -> list[dict[str, Any]]:
    if not game_root:
        return []
    override = Path(game_root) / "Override"
    if not override.is_dir():
        return []
    wanted = {str(resref).lower() for resref in resrefs if resref}
    rows: list[dict[str, Any]] = []
    for path in sorted(override.iterdir()):
        if not path.is_file():
            continue
        stem = path.stem.lower()
        suffix = path.suffix.lower().lstrip(".")
        if stem not in wanted and path.name.lower() not in {f"{resref}.2da" for resref in wanted}:
            continue
        if suffix not in {"mdl", "mdx", "tga", "txi", "2da", "uti", "utc", "mod"}:
            continue
        rows.append(summarize_file(path))
    return rows


def summarize_game_logs(game_root: Optional[str]) -> list[dict[str, Any]]:
    if not game_root:
        return []
    root = Path(game_root)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.log")):
        if path.is_file():
            rows.append(summarize_file(path, include_tail=True))
    return rows


def summarize_runtime_files(game_root: Optional[str]) -> list[dict[str, Any]]:
    """Hash game-root runtime files without modifying the installed mod stack."""

    if not game_root:
        return []
    root = Path(game_root)
    if not root.is_dir():
        return []

    candidates = [
        *root.glob("*.exe"),
        *root.glob("*.dll"),
        root / "patch_config.toml",
        root / "addresses.db",
    ]
    patches = root / "patches"
    if patches.is_dir():
        candidates.extend(patches.glob("*.dll"))

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(candidates, key=lambda item: str(item).lower()):
        key = str(path.resolve()).lower()
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        row = summarize_file(path)
        try:
            row["relative_path"] = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            row["relative_path"] = path.name
        rows.append(row)
    return rows


def summarize_module_inventory(
    modules: list[dict[str, Any]],
    *,
    game_root: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Enrich the debugger's loaded-module list with stable file hashes."""

    root = Path(game_root).resolve() if game_root else None
    rows: list[dict[str, Any]] = []
    for module in modules:
        row = dict(module)
        path = Path(str(module.get("path") or ""))
        if path.is_file():
            summary = summarize_file(path)
            row.update(
                {
                    "file_size": summary.get("size"),
                    "file_mtime": summary.get("mtime"),
                    "sha256": summary.get("sha256"),
                }
            )
            if root is not None:
                try:
                    row["game_relative_path"] = str(path.resolve().relative_to(root))
                    row["game_local"] = True
                except ValueError:
                    row["game_local"] = False
        rows.append(row)
    return rows


def summarize_file(path: Path, *, include_tail: bool = False) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}
    row = {
        "path": str(path),
        "name": path.name,
        "size": int(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": _sha256(path),
    }
    if include_tail:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            row["tail"] = text[-4000:]
        except OSError as exc:
            row["tail_error"] = str(exc)
    if path.suffix.lower() == ".mdl":
        row["mdl_header_probe"] = probe_mdl_header(path)
    return row


def probe_mdl_header(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()[:2048]
    except OSError as exc:
        return {"error": str(exc)}
    ascii_runs = re.findall(rb"[A-Za-z0-9_]{4,32}", data)
    return {
        "first_strings": [item.decode("ascii", errors="ignore") for item in ascii_runs[:12]],
        "first_bytes": data[:32].hex(" "),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _poll_until_exit(
    session_path: Path,
    writer: EventWriter,
    probe: Win32ProcessProbe,
    pid: int,
    started_epoch: float,
    duration_seconds: int,
) -> None:
    deadline = time.time() + max(5, duration_seconds)
    while time.time() < deadline and not _stop_requested(session_path):
        if not probe.process_exists(pid):
            writer.write({"event": "process_exit_observed", "pid": pid})
            break
        time.sleep(0.5)


def _finalize_summary(
    session_path: Path,
    writer: EventWriter,
    probe: Win32ProcessProbe,
    started_epoch: float,
    game_root: Optional[str],
    asset_resrefs: list[str],
    *,
    exit_code: int = 0,
) -> None:
    events = list(_read_jsonl(writer.events_path))
    exceptions = [event for event in events if event.get("event") == "exception"]
    summary = {
        "session_dir": str(session_path),
        "finished_at": _utc_now(),
        "duration_seconds": round(_epoch() - started_epoch, 3),
        "exit_code": int(exit_code),
        "event_count": len(events),
        "exception_count": len(exceptions),
        "last_exception": exceptions[-1] if exceptions else None,
        "override_assets": summarize_override_assets(game_root, asset_resrefs),
        "runtime_files": summarize_runtime_files(game_root),
        "game_logs": summarize_game_logs(game_root),
        "windows_events": collect_windows_events(started_epoch),
    }
    _write_json(session_path / "summary.json", summary)
    _write_text_summary(session_path / "summary.txt", summary)


def collect_windows_events(started_epoch: float) -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    start = datetime.fromtimestamp(started_epoch, timezone.utc).astimezone().isoformat()
    ps_script = (
        "$start=[datetime]::Parse('" + start.replace("'", "''") + "');"
        "Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=$start} "
        "| Where-Object { $_.Message -match 'swkotor|KOTOR|Knights of the Old Republic|nvoglv32' } "
        "| Select-Object TimeCreated,Id,ProviderName,Message "
        "| ConvertTo-Json -Depth 3"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = [parsed]
    return parsed if isinstance(parsed, list) else []


def _write_text_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "KOTOR Live Log Summary",
        f"Finished: {summary.get('finished_at') or summary.get('analysis_generated_at')}",
        f"Events: {summary.get('event_count')}",
        f"Exceptions: {summary.get('exception_count')}",
    ]
    last = summary.get("last_exception") or (summary.get("crashes") or [None])[-1]
    if last:
        lines.extend(
            [
                "",
                "Last exception:",
                f"  Code: {last.get('exception_code_hex')} {last.get('exception_name')}",
                f"  Address: {last.get('address_hex')}",
                f"  Module offset: {last.get('module_offset_hex')}",
                f"  Ghidra address: {last.get('ghidra_address')}",
                f"  First chance: {last.get('first_chance')}",
            ]
        )
        module = last.get("module") or {}
        if module:
            lines.append(f"  Module: {module.get('name')} ({module.get('path')})")
    annotations = summary.get("ghidra_annotations") or []
    if annotations:
        lines.extend(["", "Ghidra:"])
        for item in annotations:
            lines.append(f"  {item.get('address')}: {item.get('function')} {item.get('signature')}")
            instruction = item.get("instruction") or {}
            if instruction:
                lines.append(f"    {instruction.get('address')} {instruction.get('mnemonic')} {instruction.get('operands')}")
    path.write_text("\n".join(str(line) for line in lines) + "\n", encoding="utf-8")


def _stop_requested(session_path: Path) -> bool:
    return (session_path / "stop.request").is_file()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


def _jsonl_count(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _line in handle)
    except OSError:
        return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attach a live KOTOR debug-event logger.")
    sub = parser.add_subparsers(dest="command", required=True)
    monitor = sub.add_parser("monitor")
    monitor.add_argument("--game", default="k2")
    monitor.add_argument("--session-dir", required=True)
    monitor.add_argument("--game-root")
    monitor.add_argument("--pid", type=int)
    monitor.add_argument("--wait-for-process", action="store_true")
    monitor.add_argument("--duration-seconds", type=int, default=DEFAULT_SESSION_SECONDS)
    monitor.add_argument("--asset-resref", action="append", default=[])
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.command == "monitor":
        return run_monitor(
            game=args.game,
            session_dir=args.session_dir,
            game_root=args.game_root,
            pid=args.pid,
            wait_for_process=bool(args.wait_for_process),
            duration_seconds=int(args.duration_seconds),
            asset_resrefs=list(args.asset_resref or []),
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
