#!/usr/bin/env python3
"""
GhostRigger-K1-K2 – Entry Point

Logging policy
--------------
Every session writes a rotating log to  <app_dir>/Logs/ghostrigger_<date>.log
All logging.* output (DEBUG and above) is captured, plus:
  - Unhandled Python exceptions   (sys.excepthook)
  - Tkinter internal errors       (Tk.report_callback_exception)
  - Graceful on-exit flush        (atexit + WM_DELETE_WINDOW)

The Logs/ folder is created automatically if it does not exist.
Old log files beyond LOG_KEEP_FILES are auto-rotated (newest kept).
"""
import sys, os, logging, atexit, traceback, datetime, argparse

# ── Path setup ────────────────────────────────────────────────────────────
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _APP_DIR)

# ── Logs folder ───────────────────────────────────────────────────────────
_LOG_DIR        = os.path.join(_APP_DIR, "Logs")
_LOG_KEEP_FILES = 20          # keep the 20 most-recent session logs
_LOG_MAX_BYTES  = 10_000_000  # 10 MB per file before rotation


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on", "debug")


def _log_level() -> int:
    """Use quiet production logging unless detailed diagnostics are requested."""
    return logging.DEBUG if _env_enabled("GHOSTRIGGER_DEBUG_LOG") else logging.INFO


def _make_log_dir():
    """Create Logs/ folder if it does not exist."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except OSError as e:
        print(f"[GhostRigger] WARNING: could not create Logs/ folder: {e}",
              file=sys.stderr)


def _rotate_old_logs():
    """Delete oldest log files when more than _LOG_KEEP_FILES exist."""
    try:
        files = sorted(
            [f for f in os.listdir(_LOG_DIR) if f.startswith("ghostrigger_") and f.endswith(".log")],
            key=lambda f: os.path.getmtime(os.path.join(_LOG_DIR, f))
        )
        while len(files) >= _LOG_KEEP_FILES:
            oldest = files.pop(0)
            try:
                os.remove(os.path.join(_LOG_DIR, oldest))
            except OSError:
                pass
    except Exception:
        pass


def _setup_logging():
    """
    Configure the root logger with:
      1. A file handler → Logs/ghostrigger_YYYY-MM-DD_HHMMSS.log
      2. A stderr stream handler (INFO+)
    Returns the path of the current session log file.
    """
    _make_log_dir()
    _rotate_old_logs()

    stamp   = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    logfile = os.path.join(_LOG_DIR, f"ghostrigger_{stamp}.log")

    root_logger = logging.getLogger()
    level = _log_level()
    root_logger.setLevel(level)

    # ── File handler: DEBUG+ (captures everything) ────────────────────────
    try:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%H:%M:%S"
        ))
        root_logger.addHandler(fh)
    except OSError as e:
        print(f"[GhostRigger] WARNING: cannot open log file {logfile}: {e}",
              file=sys.stderr)
        logfile = None

    # ── Console handler: INFO+ ────────────────────────────────────────────
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter(
        "%(levelname)-8s %(name)s  %(message)s"
    ))
    root_logger.addHandler(sh)

    return logfile


def _flush_all_handlers():
    """Flush and close all file-based log handlers."""
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            h.flush()
        except Exception:
            pass


def _install_exception_hooks(logfile: str, install_tk_hook: bool = True):
    """
    Install global exception handlers so crashes are always logged to file.

    1. sys.excepthook  – catches unhandled exceptions in the main thread.
    2. Tk.report_callback_exception – catches errors in Tkinter callbacks.
    """
    _log = logging.getLogger("ghostrigger.crash")

    def _handle_uncaught(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _log.critical(f"UNHANDLED EXCEPTION:\n{msg}")
        _flush_all_handlers()
        # Also print to stderr so the user sees it in the console
        print(f"\n{'='*60}\nGhostRigger CRASH — see Logs/ for full trace\n{'='*60}\n{msg}",
              file=sys.stderr)

    sys.excepthook = _handle_uncaught

    if not install_tk_hook:
        return

    # Tkinter swallows callback errors by default; redirect to our logger
    try:
        import tkinter as tk
        _orig_report = tk.Tk.report_callback_exception

        def _tk_exception_handler(self, exc, val, tb):
            msg = "".join(traceback.format_exception(exc, val, tb))
            _log.error(f"Tkinter callback exception:\n{msg}")
            _flush_all_handlers()
            # Fall back to the original handler (shows error in console)
            try:
                _orig_report(self, exc, val, tb)
            except Exception:
                pass

        tk.Tk.report_callback_exception = _tk_exception_handler
    except Exception as e:
        _log.warning(f"Could not install Tkinter exception hook: {e}")


def _install_close_hook(app, logfile: str):
    """
    Wire up WM_DELETE_WINDOW so the log is flushed before Tk exits.
    Also registers atexit as a fallback.
    """
    _log = logging.getLogger("ghostrigger.shutdown")

    def _on_close():
        _log.info("=" * 60)
        _log.info("GhostRigger session ended (window closed by user).")
        _log.info("=" * 60)
        _flush_all_handlers()
        try:
            app.destroy()
        except Exception:
            pass

    try:
        app.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception as e:
        _log.warning(f"Could not register WM_DELETE_WINDOW hook: {e}")

    def _atexit_flush():
        _log.info("GhostRigger atexit flush.")
        _flush_all_handlers()

    atexit.register(_atexit_flush)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch GhostRigger and optionally open a KotOR model.",
    )
    parser.add_argument("--gui", choices=("qt", "tk", "tkinter"),
                        default=None,
                        help="GUI backend to launch (default: qt). "
                             "Use --gui=tk only for the legacy Tkinter shell "
                             "(scheduled for removal in M3). "
                             "Overrides GHOSTRIGGER_GUI.")
    parser.add_argument("--mdl", help="Path to a .mdl file to open after startup.")
    parser.add_argument("--mdx", help="Path to the matching .mdx file.")
    parser.add_argument(
        "--tga",
        action="append",
        default=[],
        help="Path to a texture file to make available to the viewport. May be repeated.",
    )
    parser.add_argument("--texture", dest="tga", action="append",
                        help="Alias for --tga.")
    parser.add_argument("--texture-dir",
                        help="Texture search directory to use for the startup model.")
    parser.add_argument("--game", choices=("K1", "K2", "k1", "k2"),
                        help="Preferred game version for the startup model.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # ── Logging setup (must happen before any imports that use logging) ───
    logfile = _setup_logging()
    log = logging.getLogger("ghostrigger.main")

    log.info("=" * 60)
    log.info(f"GhostRigger-K1-K2 starting — Python {sys.version.split()[0]}")
    log.info(f"Session log: {logfile or 'DISABLED (could not open log file)'}")
    log.info(f"App directory: {_APP_DIR}")
    log.info("=" * 60)

    # T003 — Qt is the default GUI. Tk remains as an explicit opt-in until
    # M3/T303 deletes it. There is NO auto-fallback: if --gui=qt fails the
    # process dies with the Qt traceback so the user sees the real error
    # instead of silently dropping into the legacy Tk shell.
    gui_mode = (args.gui or os.environ.get("GHOSTRIGGER_GUI", "qt")).strip().lower()
    if gui_mode in ("tkinter",):
        gui_mode = "tk"
    if gui_mode not in ("qt", "tk"):
        log.warning("Unknown GUI mode %r; defaulting to qt.", gui_mode)
        gui_mode = "qt"

    # Install exception hooks before anything else can raise.  The Tk callback
    # hook is only installed when the Tk app owns the process.
    _install_exception_hooks(logfile, install_tk_hook=(gui_mode == "tk"))

    # Log detailed session-start diagnostics (PIL, NumPy, platform)
    try:
        from src.core.diagnostics import log_session_start
        log_session_start(_APP_DIR, logfile or "(no log file)")
    except Exception as _diag_err:
        log.debug(f"diagnostics.log_session_start failed: {_diag_err}")

    if gui_mode == "qt":
        try:
            from src.gui.qt_main_window import run as _run_qt

            log.info("Qt main window starting.")
            rc = _run_qt(_APP_DIR, startup_input=vars(args))
            log.info("Qt main window exited cleanly.")
            _flush_all_handlers()
            return rc
        except Exception:
            log.critical("Fatal error during Qt startup:\n" + traceback.format_exc())
            _flush_all_handlers()
            raise

    # gui_mode == "tk" — legacy path (frozen, slated for deletion in M3/T303).
    log.warning("Launching legacy Tkinter shell (--gui=tk). "
                "This path is frozen and will be removed in M3.")
    try:
        from src.gui.main_window import run as _run_gui, KotorModToolsApp

        # Patch run() to install the close hook
        def run():
            app = KotorModToolsApp()
            _install_close_hook(app, logfile)
            if args.texture_dir:
                app._texture_dir = args.texture_dir
            elif args.tga:
                app._texture_dir = os.path.dirname(os.path.abspath(args.tga[0]))
            if args.mdl:
                app.after(0, lambda: app.open_startup_model(
                    args.mdl,
                    mdx_path=args.mdx or "",
                    texture_dir=getattr(app, "_texture_dir", ""),
                    game=(args.game or "").upper(),
                ) if hasattr(app, "open_startup_model") else None)
            log.info("Tkinter mainloop starting.")
            app.mainloop()
            log.info("Tkinter mainloop exited cleanly.")
            _flush_all_handlers()

        run()

    except Exception:
        log.critical("Fatal error during startup:\n" + traceback.format_exc())
        _flush_all_handlers()
        raise


if __name__ == "__main__":
    main()
