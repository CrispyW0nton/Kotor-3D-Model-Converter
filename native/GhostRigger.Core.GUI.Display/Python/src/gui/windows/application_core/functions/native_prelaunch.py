"""Native pre-launch worker bridge for the Qt shell."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import ctypes
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Sequence

PrelaunchJob = Callable[[], object]
PrelaunchStatusCallback = Callable[[str, str], None]

_TASK_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)
_STATUS_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_char_p)
_SHELL_DLL = "GhostRigger.Core.GUI.Display.dll"


def _candidate_shell_dll_paths() -> list[Path]:
    candidates: list[Path] = []
    build_output = os.environ.get("GHOSTRIGGER_NATIVE_BUILD_OUTPUT_DIR", "").strip()
    if build_output:
        candidates.append(Path(build_output) / _SHELL_DLL)
    payload_root = os.environ.get("GHOSTRIGGER_NATIVE_PAYLOAD_ROOT", "").strip()
    if payload_root:
        candidates.append(Path(payload_root).parent / _SHELL_DLL)
    candidates.append(Path(sys.executable).resolve().parent / _SHELL_DLL)
    return candidates


def _load_native_shell_library() -> ctypes.CDLL | None:
    for dll_path in _candidate_shell_dll_paths():
        if not dll_path.exists():
            continue
        try:
            if hasattr(os, "add_dll_directory"):
                with os.add_dll_directory(str(dll_path.parent)):
                    library = ctypes.CDLL(str(dll_path))
            else:
                library = ctypes.CDLL(str(dll_path))
            run_tasks = library.gr_windows_main_window_run_prelaunch_tasks
            run_tasks.argtypes = [ctypes.c_int, _TASK_CALLBACK, _STATUS_CALLBACK]
            run_tasks.restype = ctypes.c_int
            return library
        except (AttributeError, OSError):
            continue
    return None


class _PythonPrelaunchRun:
    def __init__(self, jobs: Sequence[PrelaunchJob]) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max(1, len(jobs)), thread_name_prefix="GRStartup")
        self._futures: list[Future[object]] = [self._executor.submit(job) for job in jobs]

    def done(self) -> bool:
        return all(future.done() for future in self._futures)

    def task_done(self, index: int) -> bool:
        return self._futures[index].done()

    def result(self, index: int, timeout: float | None = None) -> object:
        return self._futures[index].result(timeout=timeout)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)


class _NativePrelaunchRun:
    def __init__(
        self,
        library: ctypes.CDLL,
        jobs: Sequence[PrelaunchJob],
        status_callback: PrelaunchStatusCallback | None,
    ) -> None:
        self._library = library
        self._jobs = list(jobs)
        self._status_callback = status_callback
        self._results: list[object | None] = [None] * len(self._jobs)
        self._errors: list[BaseException | None] = [None] * len(self._jobs)
        self._task_done_events: list[threading.Event] = [threading.Event() for _ in self._jobs]
        self._native_result = 0
        self._done = threading.Event()
        self._task_callback = _TASK_CALLBACK(self._run_task)
        self._native_status_callback = _STATUS_CALLBACK(self._emit_status)
        self._coordinator = threading.Thread(
            target=self._run_native,
            name="GRNativePrelaunchCoordinator",
            daemon=True,
        )
        self._coordinator.start()

    def _emit_status(self, title: bytes | None, detail: bytes | None) -> None:
        if self._status_callback is None:
            return
        decoded_title = (title or b"").decode("utf-8", errors="replace")
        decoded_detail = (detail or b"").decode("utf-8", errors="replace")
        self._status_callback(decoded_title, decoded_detail)

    def _run_task(self, index: int) -> None:
        if index < 0 or index >= len(self._jobs):
            return
        try:
            self._results[index] = self._jobs[index]()
        except BaseException as exc:
            self._errors[index] = exc
        finally:
            self._task_done_events[index].set()

    def _run_native(self) -> None:
        try:
            self._native_result = self._library.gr_windows_main_window_run_prelaunch_tasks(
                len(self._jobs),
                self._task_callback,
                self._native_status_callback,
            )
        except BaseException as exc:
            if self._errors:
                self._errors[0] = exc
            self._native_result = 1
        finally:
            self._done.set()

    def done(self) -> bool:
        return self._done.is_set()

    def task_done(self, index: int) -> bool:
        return self._task_done_events[index].is_set()

    def result(self, index: int, timeout: float | None = None) -> object:
        if not self._task_done_events[index].wait(timeout):
            raise TimeoutError(f"Pre-launch task {index} has not completed.")
        error = self._errors[index]
        if error is not None:
            raise error
        if self._done.is_set() and self._native_result != 0:
            raise RuntimeError(f"Native pre-launch worker bridge failed with code {self._native_result}.")
        return self._results[index]

    def shutdown(self) -> None:
        self._coordinator.join()


def start_prelaunch_tasks(
    jobs: Sequence[PrelaunchJob],
    *,
    status_callback: PrelaunchStatusCallback | None = None,
) -> _NativePrelaunchRun | _PythonPrelaunchRun:
    library = _load_native_shell_library()
    if library is None:
        if status_callback is not None:
            status_callback("Python startup threading", "Native Shell Main worker bridge unavailable; using Python workers.")
        return _PythonPrelaunchRun(jobs)
    return _NativePrelaunchRun(library, jobs, status_callback)
