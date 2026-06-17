"""Qt application runner helper for the main GhostRigger window."""

from __future__ import annotations

import logging
import os
from queue import Empty, SimpleQueue
import sys
import time
from pathlib import Path
import threading
from typing import Callable, Optional, TextIO

try:
    from PySide6 import QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme import ThemeManager
from src.gui.windows.application_core.application_core_lib.functions.native_prelaunch import start_prelaunch_tasks

log = logging.getLogger(__name__)


class _SplashLogHandler(logging.Handler):
    def __init__(self, emit_line: Callable[[str], None]) -> None:
        super().__init__(logging.INFO)
        self._emit_line = emit_line
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)-34.34s  %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit_line(self.format(record))
        except Exception:
            self.handleError(record)


class _SplashStream:
    def __init__(self, wrapped: TextIO | None, emit_line: Callable[[str], None], label: str) -> None:
        self._wrapped = wrapped
        self._emit_line = emit_line
        self._label = label
        self._buffer = ""
        self._lock = threading.RLock()
        self.encoding = getattr(wrapped, "encoding", "utf-8") if wrapped is not None else "utf-8"
        self.errors = getattr(wrapped, "errors", "replace") if wrapped is not None else "replace"

    def write(self, text: str) -> int:
        value = str(text)
        with self._lock:
            written = None
            if self._wrapped is not None:
                written = self._wrapped.write(value)
                self._wrapped.flush()
            self._buffer += value
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    self._emit_line(f"{self._label}  {line}")
            return written if isinstance(written, int) else len(value)

    def flush(self) -> None:
        with self._lock:
            if self._buffer.strip():
                self._emit_line(f"{self._label}  {self._buffer.strip()}")
            self._buffer = ""
            if self._wrapped is not None:
                self._wrapped.flush()

    def isatty(self) -> bool:
        if self._wrapped is None:
            return False
        return bool(getattr(self._wrapped, "isatty", lambda: False)())

    def fileno(self) -> int:
        if self._wrapped is None:
            raise OSError("No wrapped stream is available.")
        return self._wrapped.fileno()

    def __getattr__(self, name: str):
        if self._wrapped is None:
            raise AttributeError(name)
        return getattr(self._wrapped, name)


def _read_existing_launch_log_lines() -> list[str]:
    lines: list[str] = []
    native_audit = os.environ.get("GHOSTRIGGER_NATIVE_PREPYTHON_AUDIT", "").strip()
    if native_audit:
        lines.extend(native_audit.splitlines())
    logfile = os.environ.get("GHOSTRIGGER_CURRENT_LOGFILE", "").strip()
    if logfile:
        try:
            lines.extend(Path(logfile).read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass
    return [line for line in lines if line.strip()]


def _install_splash_log_capture(emit_line: Callable[[str], None]) -> Callable[[], None]:
    root_logger = logging.getLogger()
    handler = _SplashLogHandler(emit_line)
    root_logger.addHandler(handler)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = _SplashStream(original_stdout, emit_line, "STDOUT")  # type: ignore[assignment]
    sys.stderr = _SplashStream(original_stderr, emit_line, "STDERR")  # type: ignore[assignment]

    def cleanup() -> None:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            root_logger.removeHandler(handler)
            handler.close()

    return cleanup


def _splash_hold_seconds_from_env() -> float:
    try:
        hold_ms = int(os.environ.get("GHOSTRIGGER_SPLASH_HOLD_MS", "0") or 0)
    except ValueError:
        return 0.0
    return max(0.0, min(float(hold_ms) / 1000.0, 15.0))


def run_qt_application(
    app_root: Optional[str],
    startup_input: Optional[dict],
    *,
    window_cls,
    splash_cls,
    read_settings: Callable[[Path], dict],
    collect_startup_diagnostics: Callable[[dict, object], dict],
    build_prelaunch_library_input: Callable[[Path, Optional[dict], object], dict],
) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GhostRigger")
    app.setStyle("Fusion")
    for family in ("Consolas", "Lucida Console", "Courier New"):
        if family in QtGui.QFontDatabase.families():
            app.setFont(QtGui.QFont(family, 9))
            break
    root = Path(app_root) if app_root else Path(__file__).resolve().parents[4]
    settings_data = read_settings(root / "settings.json")
    startup_theme_manager = ThemeManager(root, settings_data)
    splash = splash_cls(root, theme_manager=startup_theme_manager)
    splash.show()
    log_queue: SimpleQueue[str] = SimpleQueue()

    def queue_splash_log_line(line: str) -> None:
        log_queue.put(str(line))

    cleanup_splash_log_capture = _install_splash_log_capture(queue_splash_log_line)

    def update_prelaunch_status(title: str, detail: str) -> None:
        finished = title.lower().endswith("ready")
        splash.set_status(title, detail, finished=finished)
        splash.show()
        splash.raise_()
        app.processEvents()

    status_queue: SimpleQueue[tuple[str, str]] = SimpleQueue()

    def queue_prelaunch_status(title: str, detail: str) -> None:
        status_queue.put((str(title), str(detail)))

    def drain_splash_log() -> bool:
        updated = False
        while True:
            try:
                line = log_queue.get_nowait()
            except Empty:
                return updated
            splash.append_log_line(line)
            updated = True

    def drain_prelaunch_status() -> bool:
        updated = False
        while True:
            try:
                title, detail = status_queue.get_nowait()
            except Empty:
                return updated
            update_prelaunch_status(title, detail)
            updated = True

    for line in _read_existing_launch_log_lines():
        splash.append_log_line(line)
    update_prelaunch_status("Preparing startup", "Starting diagnostics and library indexing...")
    prelaunch_run = start_prelaunch_tasks(
        (
            lambda: collect_startup_diagnostics(settings_data, queue_prelaunch_status),
            lambda: build_prelaunch_library_input(root, startup_input, queue_prelaunch_status),
        ),
        status_callback=queue_prelaunch_status,
    )
    while not prelaunch_run.done():
        had_status = drain_prelaunch_status()
        had_log = drain_splash_log()
        if not had_status and not had_log:
            update_prelaunch_status("Preparing startup", "Indexing game libraries and checking renderer hardware...")
        time.sleep(0.025)
        app.processEvents()
    drain_prelaunch_status()
    drain_splash_log()
    try:
        startup_diagnostics = prelaunch_run.result(0)
    except Exception:
        log.warning("Pre-window startup diagnostics failed.", exc_info=True)
        startup_diagnostics = {"renderer_capabilities": [], "hardware_diagnostics": {}}
    try:
        prepared_input = prelaunch_run.result(1)
    except Exception:
        log.warning("Pre-window library preparation failed.", exc_info=True)
        prepared_input = dict(startup_input or {})
        prepared_input["preloaded_library"] = {
            "rows": [],
            "error": "Startup library preparation failed.",
            "detection_attempted": True,
        }
    finally:
        prelaunch_run.shutdown()
    prepared_input.update(startup_diagnostics)
    update_prelaunch_status("Opening workspace", "Starting the main window.")
    drain_splash_log()
    hold_seconds = _splash_hold_seconds_from_env()
    if hold_seconds > 0:
        deadline = time.monotonic() + hold_seconds
        while time.monotonic() < deadline:
            drain_splash_log()
            app.processEvents()
            time.sleep(0.025)
    app.processEvents()
    win = window_cls(root, startup_input=prepared_input)
    drain_splash_log()
    app.processEvents()
    win.show()
    splash.close()
    cleanup_splash_log_capture()
    return app.exec()
