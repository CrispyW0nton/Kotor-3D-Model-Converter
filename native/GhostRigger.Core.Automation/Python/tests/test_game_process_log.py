from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


PYTHON_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_SRC = PYTHON_ROOT / "src"
if str(AUTOMATION_SRC) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_SRC))


def test_debug_attach_retries_transient_invalid_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    from kotormcp import game_process_log

    class Probe:
        def __init__(self) -> None:
            self.results = iter(((False, game_process_log.ERROR_INVALID_PARAMETER), (True, 0)))
            self.attach_calls = 0

        def debug_attach(self, _pid: int) -> tuple[bool, int]:
            self.attach_calls += 1
            return next(self.results)

        @staticmethod
        def process_exists(_pid: int) -> bool:
            return True

    class Writer:
        def __init__(self) -> None:
            self.events: list[dict] = []

        def write(self, event: dict) -> None:
            self.events.append(dict(event))

    probe = Probe()
    writer = Writer()
    monkeypatch.setattr(game_process_log.time, "sleep", lambda _seconds: None)

    attached, error = game_process_log._attach_debugger_with_retry(probe, writer, 103132)

    assert attached is True
    assert error == 0
    assert probe.attach_calls == 2
    assert [event["last_error"] for event in writer.events] == [87, 0]


def test_fallback_monitor_retains_real_target_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from kotormcp import game_process_log

    class Probe:
        def __init__(self) -> None:
            self.statuses = iter(
                (
                    {"available": True, "running": True, "exit_code": None, "last_error": 0},
                    {
                        "available": True,
                        "running": False,
                        "exit_code": game_process_log.EXCEPTION_ACCESS_VIOLATION,
                        "last_error": 0,
                    },
                )
            )

        def monitor_status(self, _handle) -> dict:
            return next(self.statuses)

        @staticmethod
        def process_exists(_pid: int) -> bool:
            return True

    writer = game_process_log.EventWriter(tmp_path)
    monitor_handle = game_process_log.ProcessMonitorHandle(raw=123, can_wait=True)
    monkeypatch.setattr(game_process_log.time, "sleep", lambda _seconds: None)

    exit_code = game_process_log._poll_until_exit(
        tmp_path,
        writer,
        Probe(),
        103132,
        0.0,
        5,
        monitor_handle=monitor_handle,
    )
    events = list(game_process_log._read_jsonl(writer.events_path))

    assert exit_code == game_process_log.EXCEPTION_ACCESS_VIOLATION
    assert events[-1]["event"] == "process_exit_observed"
    assert events[-1]["exit_code_hex"] == "0xc0000005"
    assert events[-1]["exit_code_name"] == "EXCEPTION_ACCESS_VIOLATION"
    assert events[-1]["exit_code_source"] == "persistent_process_handle"


def test_fallback_ignores_enumeration_miss_until_persistent_handle_signals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from kotormcp import game_process_log

    class Probe:
        def __init__(self) -> None:
            self.statuses = iter(
                (
                    {"available": True, "running": True, "exit_code": None, "last_error": 0},
                    {
                        "available": True,
                        "running": False,
                        "exit_code": game_process_log.EXCEPTION_ACCESS_VIOLATION,
                        "last_error": 0,
                    },
                )
            )

        def monitor_status(self, _handle) -> dict:
            return next(self.statuses)

        @staticmethod
        def process_exists(_pid: int) -> bool:
            # Reproduces the KOQ200 run where Toolhelp stopped listing the PID
            # before the retained process handle signaled termination.
            return False

    writer = game_process_log.EventWriter(tmp_path)
    monitor_handle = game_process_log.ProcessMonitorHandle(raw=123, can_wait=True)
    monkeypatch.setattr(game_process_log.time, "sleep", lambda _seconds: None)

    exit_code = game_process_log._poll_until_exit(
        tmp_path,
        writer,
        Probe(),
        103132,
        0.0,
        5,
        monitor_handle=monitor_handle,
    )
    events = list(game_process_log._read_jsonl(writer.events_path))

    assert exit_code == game_process_log.EXCEPTION_ACCESS_VIOLATION
    assert [event["event"] for event in events] == [
        "process_enumeration_miss",
        "process_exit_observed",
    ]
    assert events[0]["persistent_handle_authoritative"] is True
    assert events[0]["monitor_status"]["running"] is True
    assert events[1]["exit_code_hex"] == "0xc0000005"


def test_unknown_target_exit_is_never_reported_as_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from kotormcp import game_process_log

    writer = game_process_log.EventWriter(tmp_path)
    writer.write(
        {
            "event": "process_exit_observed",
            "pid": 103132,
            "exit_code": None,
            "exit_code_source": None,
        }
    )
    monkeypatch.setattr(game_process_log, "summarize_override_assets", lambda *_args: [])
    monkeypatch.setattr(game_process_log, "summarize_runtime_files", lambda *_args: [])
    monkeypatch.setattr(game_process_log, "summarize_game_logs", lambda *_args: [])
    monkeypatch.setattr(game_process_log, "collect_windows_events", lambda *_args: [])

    game_process_log._finalize_summary(
        tmp_path,
        writer,
        object(),
        game_process_log._epoch(),
        None,
        [],
        exit_code=None,
        debugger_attached=False,
        debug_attach_error=87,
    )
    summary = game_process_log._read_json(tmp_path / "summary.json")

    assert summary["exit_code"] is None
    assert summary["exit_code_hex"] is None
    assert summary["exit_code_available"] is False
    assert summary["process_exit_observed"] is True
    assert summary["debug_attach_error"] == 87
    assert "Target exit: unknown" in (tmp_path / "summary.txt").read_text(encoding="utf-8")


def test_access_violation_records_fault_address_instruction_and_stack() -> None:
    from kotormcp import game_process_log

    class Probe:
        @staticmethod
        def modules(_pid: int) -> list[dict]:
            return [
                {
                    "name": "swkotor2.exe",
                    "path": r"C:\Games\KOTOR2\swkotor2.exe",
                    "base": 0x00400000,
                    "end": 0x00C00000,
                }
            ]

        @staticmethod
        def wow64_thread_context(_thread_id: int) -> dict:
            return {"available": True, "esp": 0x0012F000, "ebp": 0, "eip": 0x0044B3A8}

        @staticmethod
        def read_memory(_pid: int, address: int, length: int) -> bytes:
            if address == 0x0044B3A8:
                return bytes.fromhex("8b 90 84 00 00 00 c3")[:length]
            if address == 0x0012F000:
                return b"\x00" * length
            return b""

    event = game_process_log.DEBUG_EVENT()
    event.dwDebugEventCode = game_process_log.EXCEPTION_DEBUG_EVENT
    event.dwProcessId = 103132
    event.dwThreadId = 77
    event.u.Exception.dwFirstChance = 0
    record = event.u.Exception.ExceptionRecord
    record.ExceptionCode = game_process_log.EXCEPTION_ACCESS_VIOLATION
    record.ExceptionAddress = 0x0044B3A8
    record.NumberParameters = 2
    record.ExceptionInformation[0] = 0
    record.ExceptionInformation[1] = 0x84

    detail, continue_status = game_process_log._debug_event_to_dict(event, Probe(), 103132)

    assert continue_status == game_process_log.DBG_EXCEPTION_NOT_HANDLED
    assert detail["fault_operation_name"] == "read"
    assert detail["fault_address_hex"] == "0x00000084"
    assert detail["instruction_bytes_hex"] == "8b 90 84 00 00 00 c3"
    assert detail["module_offset_hex"] == "0x0004b3a8"
    assert detail["ghidra_address"] == "0x0044b3a8"
    assert len(detail["stack"]) == 32


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 process-handle contract")
def test_persistent_monitor_handle_observes_exit_after_process_disappears() -> None:
    from kotormcp.game_process_log import Win32ProcessProbe

    process = subprocess.Popen([sys.executable, "-c", "raise SystemExit(7)"])
    probe = Win32ProcessProbe()
    monitor_handle = probe.open_monitor_handle(process.pid)
    try:
        assert monitor_handle is not None
        process.wait(timeout=10)
        status = probe.monitor_status(monitor_handle)
    finally:
        probe.close_monitor_handle(monitor_handle)

    assert status == {
        "available": True,
        "running": False,
        "exit_code": 7,
        "last_error": 0,
    }
