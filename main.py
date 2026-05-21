#!/usr/bin/env python3
"""
GhostRigger-K1-K2 – Entry Point

Logging policy
--------------
Every session writes a rotating log to  <app_dir>/Logs/ghostrigger_<date>.log
All logging.* output (DEBUG and above) is captured, plus:
  - Unhandled Python exceptions   (sys.excepthook)
  - Graceful on-exit flush        (atexit)

The Logs/ folder is created automatically if it does not exist.
Old log files beyond LOG_KEEP_FILES are auto-rotated (newest kept).

History
-------
Pre-M3/T303 this entry point also supported a ``--gui=tk`` legacy
shell launched from ``src/gui/main_window.py``. Both the flag and the
Tk shell were removed in milestone M3 (T302 deleted the modules,
T303 trimmed the launcher). Qt is now the only supported front-end.
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


def _install_exception_hooks(logfile: str):
    """
    Install the global exception handler so crashes are always logged.

    Qt callbacks raise into ``sys.excepthook`` already (QCoreApplication
    re-raises into Python), so a single hook is enough. The pre-M3
    Tk-specific ``Tk.report_callback_exception`` patch was removed in
    M3/T303 along with the Tk launcher.
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


def _install_atexit_flush():
    """Register an atexit hook that flushes log handlers on shutdown.

    Replaces the pre-M3 ``_install_close_hook`` which wired into Tk's
    ``WM_DELETE_WINDOW`` protocol. Under Qt the application closes
    through ``QCoreApplication.quit()`` which already triggers normal
    interpreter shutdown, so a plain ``atexit`` is sufficient.
    """
    _log = logging.getLogger("ghostrigger.shutdown")

    def _atexit_flush():
        _log.info("GhostRigger atexit flush.")
        _flush_all_handlers()

    atexit.register(_atexit_flush)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch GhostRigger and optionally open a KotOR model.",
    )
    # M3/T303 — Qt is the only supported GUI. The ``--gui`` flag is kept
    # purely so historical scripts that pass ``--gui=qt`` still work; any
    # other value is silently coerced to ``qt`` with a warning.
    parser.add_argument("--gui", choices=("qt",),
                        default="qt",
                        help="GUI backend to launch. Qt is the only supported "
                             "value; the legacy ``tk`` option was removed in "
                             "M3/T303 together with src/gui/main_window.py.")
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


def _precache_themes(app_dir: str, log: logging.Logger) -> None:
    """Warm stylesheet cache before the Qt main window starts."""
    from pathlib import Path

    from src.gui.libtheme.theme_applier import ThemeApplier
    from src.gui.libtheme.theme_loader import ThemeLoader
    from src.gui.libtheme.theme_settings import user_config_root

    loader = ThemeLoader()
    packaged_dir = Path(app_dir) / "config" / "themes" / "themes"
    packaged_themes = loader.load_dir(packaged_dir)
    user_themes = loader.load_dir(user_config_root() / "themes")
    themes = dict(packaged_themes)
    themes.update(user_themes)
    ordered = sorted(themes.values(), key=lambda theme: (theme.id != "default", theme.name.lower(), theme.id))
    if not ordered:
        print("[GhostRigger] Theme precache: no theme XML files found.", flush=True)
        log.warning("Theme precache skipped; no theme XML files found in %s", packaged_dir)
        return

    print(f"[GhostRigger] Precaching {len(ordered)} theme stylesheet(s)...", flush=True)
    if user_themes:
        print(f"[GhostRigger] Theme precache includes {len(user_themes)} user theme(s).", flush=True)
    log.info("Theme precache starting for %d theme(s).", len(ordered))
    result = ThemeApplier.precache_stylesheets(ordered)
    for entry in result["results"]:
        theme = entry["theme"]
        status = str(entry["status"])
        elapsed_ms = float(entry["elapsed_ms"])
        message = str(entry["message"])
        if status == "failed":
            print(f"[GhostRigger] Theme precache FAILED {theme.id}: {message}", flush=True)
        elif status == "cached":
            print(f"[GhostRigger] Theme precache cached {theme.id}", flush=True)
        else:
            print(f"[GhostRigger] Theme precache built {theme.id} in {elapsed_ms:.1f} ms", flush=True)
    built = int(result["built"])
    cached = int(result["cached"])
    failed = int(result["failed"])
    total_ms = float(result["total_ms"])
    print(
        f"[GhostRigger] Theme precache complete: {built} built, {cached} cached, "
        f"{failed} failed in {total_ms:.1f} ms.",
        flush=True,
    )
    log.info(
        "Theme precache complete: %d built, %d cached, %d failed in %.1f ms.",
        built,
        cached,
        failed,
        total_ms,
    )


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

    # M3/T303 — Qt is the only supported GUI. ``--gui=qt`` is accepted for
    # backward compatibility; ``GHOSTRIGGER_GUI`` is still consulted so
    # existing launch scripts keep working, but any non-``qt`` value is
    # coerced to ``qt`` with a warning rather than entering a dead Tk path.
    gui_mode = (args.gui or os.environ.get("GHOSTRIGGER_GUI", "qt")).strip().lower()
    if gui_mode not in ("qt",):
        log.warning(
            "Unsupported GUI mode %r requested; Qt is the only supported "
            "front-end after M3/T303. Continuing with --gui=qt.",
            gui_mode,
        )
        gui_mode = "qt"

    # Install the unified exception hook + atexit log flush. No Tk-specific
    # hooks any more — they were deleted alongside the Tk launcher in
    # M3/T303.
    _install_exception_hooks(logfile)
    _install_atexit_flush()

    # Log detailed session-start diagnostics (PIL, NumPy, platform)
    try:
        from src.core.qt_core.diagnostics.diagnostics import log_session_start
        log_session_start(_APP_DIR, logfile or "(no log file)")
    except Exception as _diag_err:
        log.debug(f"diagnostics.log_session_start failed: {_diag_err}")

    try:
        try:
            _precache_themes(_APP_DIR, log)
        except Exception as _theme_err:
            print(f"[GhostRigger] Theme precache skipped: {_theme_err}", flush=True)
            log.warning("Theme precache skipped after an unexpected error: %s", _theme_err, exc_info=True)

        from src.gui.qt_lib.windows.qt_main_window import run as _run_qt

        log.info("Qt main window starting.")
        rc = _run_qt(_APP_DIR, startup_input=vars(args))
        log.info("Qt main window exited cleanly.")
        _flush_all_handlers()
        return rc
    except Exception:
        log.critical("Fatal error during Qt startup:\n" + traceback.format_exc())
        _flush_all_handlers()
        raise


if __name__ == "__main__":
    main()
