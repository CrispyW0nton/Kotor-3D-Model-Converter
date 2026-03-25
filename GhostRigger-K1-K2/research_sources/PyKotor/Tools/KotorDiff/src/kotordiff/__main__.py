#!/usr/bin/env python3
"""KotorDiff entry point - handles GUI vs CLI mode selection."""

from __future__ import annotations

import atexit
import sys
import tempfile

from contextlib import suppress
from pathlib import Path
from types import TracebackType

# Add the PyKotor source directory to the Python path
script_dir = Path(__file__).resolve().parent  # kotordiff
src_dir = script_dir.parent  # src
kotordiff_dir = src_dir.parent  # KotorDiff
tools_dir = kotordiff_dir.parent  # Tools
pykotor_dir = tools_dir.parent  # PyKotor root
pykotor_src = pykotor_dir / "Libraries" / "PyKotor" / "src"
if str(pykotor_src) not in sys.path:
    sys.path.insert(0, str(pykotor_src))

# sys.path modifications removed - pykotor is now a proper package
from kotordiff.gui import KotorDiffApp
from loggerplus import RobustLogger  # type: ignore[import-untyped]
from pykotor.diff_tool.cli import execute_cli, has_cli_paths, parse_args
from utility.system.app_process.shutdown import terminate_main_process


def is_frozen() -> bool:
    """Check if running as a frozen executable."""
    return getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", False) or tempfile.gettempdir() in sys.executable


CURRENT_VERSION = "1.0.0"


def on_app_crash(
    etype: type[BaseException],
    exc: BaseException,
    tback: TracebackType | None,
):
    """Handle uncaught exceptions."""
    title, short_msg = (exc.__class__.__name__, str(exc))
    if tback is None:
        with suppress(Exception):
            import inspect

            current_stack = inspect.stack()
            if current_stack:
                current_stack = current_stack[1:][::-1]
                fake_traceback = None
                for frame_info in current_stack:
                    frame = frame_info.frame
                    fake_traceback = TracebackType(fake_traceback, frame, frame.f_lasti, frame.f_lineno)
                exc = exc.with_traceback(fake_traceback)
                tback = exc.__traceback__
    RobustLogger().error("Unhandled exception caught.", exc_info=(etype, exc, tback))

    with suppress(Exception):
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror(title, short_msg)
        root.destroy()

    print(f"[CRASH] {title}: {short_msg}", file=sys.stderr)
    sys.exit(1)


sys.excepthook = on_app_crash


def kotordiff_cleanup_func(app: KotorDiffApp):
    """Prevents the app from running in the background after sys.exit is called."""
    print("Fully shutting down KotorDiff...")
    terminate_main_process()
    app.root.destroy()


def main():
    """Main entry point."""
    cmdline_args = parse_args()

    # Determine if we should run in CLI mode
    force_cli = has_cli_paths(cmdline_args) and not getattr(cmdline_args, "gui", False) and app_class is None

    if force_cli:
        # CLI mode - paths were provided
        execute_cli(cmdline_args)
    else:
        # GUI mode - check if we can run GUI
        try:
            import os

            # Check if display is available
            display = os.environ.get("DISPLAY", "")
            if not display and os.name != "nt":  # Not Windows and no DISPLAY
                raise RuntimeError("No display available")
            app = KotorDiffApp()
            atexit.register(lambda: kotordiff_cleanup_func(app))
            app.root.mainloop()
        except Exception:  # noqa: BLE001
            if has_cli_paths(cmdline_args):
                # If we have paths but GUI failed, fall back to CLI
                execute_cli(cmdline_args)
            else:
                RobustLogger().exception("GUI not available")
                RobustLogger().warning("[Warning] Display driver not available, cannot run in GUI mode without command-line arguments.")
                RobustLogger().info("[Info] Use --help to see CLI options")
                sys.exit(0)


if __name__ == "__main__":
    main()
