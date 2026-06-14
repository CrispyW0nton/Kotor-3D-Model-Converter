#!/usr/bin/env python3
"""Native Visual Studio entrypoint for GhostRigger.

This file is owned by `GhostRigger.Native.Core.Host` and is copied beside
`GhostRigger.exe` during the Visual Studio build. It intentionally does not
import or execute the repository-root `main.py`.
"""

from __future__ import annotations

import argparse
import atexit
import datetime
import logging
import os
from pathlib import Path
import sys
import traceback


_HOST_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(os.environ.get("GHOSTRIGGER_NATIVE_REPO_ROOT", "") or _HOST_DIR).resolve()


def _extract_native_python_payloads() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        import json
    except Exception:
        return None

    build_dir = Path(os.environ.get("GHOSTRIGGER_NATIVE_BUILD_OUTPUT_DIR", "") or _HOST_DIR)
    payload_root = Path(os.environ.get("GHOSTRIGGER_NATIVE_PAYLOAD_ROOT", "") or (build_dir / "GhostRiggerPythonPayload"))
    if (payload_root / "src").is_dir():
        return payload_root

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.FindResourceA.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    kernel32.FindResourceA.restype = ctypes.c_void_p
    kernel32.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.LoadResource.restype = ctypes.c_void_p
    kernel32.LockResource.argtypes = [ctypes.c_void_p]
    kernel32.LockResource.restype = ctypes.c_void_p
    kernel32.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.SizeofResource.restype = ctypes.c_uint32

    extracted = 0
    skipped = 0
    for dll_path in build_dir.glob("*.dll"):
        try:
            dll = ctypes.CDLL(str(dll_path), winmode=8)
            manifest_fn = dll.gr_python_payload_manifest_json
            manifest_fn.restype = ctypes.c_char_p
            manifest = json.loads((manifest_fn() or b"{}").decode("utf-8-sig"))
        except Exception:
            continue

        for row in manifest.get("files", []):
            resource_name = str(row.get("resource_name") or "").encode("ascii", errors="ignore")
            packaged_path = str(row.get("packaged_path") or "").replace("\\", "/")
            if not resource_name or not packaged_path:
                continue
            if packaged_path.startswith("Python/"):
                packaged_path = packaged_path[len("Python/"):]
            parts = [part for part in packaged_path.split("/") if part]
            if not parts or ".." in parts:
                continue

            resource = kernel32.FindResourceA(dll._handle, resource_name, ctypes.c_void_p(10))
            if not resource:
                continue
            handle = kernel32.LoadResource(dll._handle, resource)
            data_ptr = kernel32.LockResource(handle) if handle else None
            size = int(kernel32.SizeofResource(dll._handle, resource))
            if not data_ptr or size <= 0:
                continue

            target = payload_root.joinpath(*parts)
            if target.exists():
                skipped += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(ctypes.string_at(data_ptr, size))
            extracted += 1

    if (extracted or skipped) and (payload_root / "src").is_dir():
        os.environ["GHOSTRIGGER_NATIVE_PAYLOAD_ROOT"] = str(payload_root)
        return payload_root
    return None


_NATIVE_PAYLOAD_ROOT = Path(os.environ.get("GHOSTRIGGER_NATIVE_PAYLOAD_ROOT", "") or "")
if not (_NATIVE_PAYLOAD_ROOT and (_NATIVE_PAYLOAD_ROOT / "src").is_dir()):
    _NATIVE_PAYLOAD_ROOT = _extract_native_python_payloads()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if _NATIVE_PAYLOAD_ROOT and (_NATIVE_PAYLOAD_ROOT / "src").is_dir():
    sys.path.insert(0, str(_NATIVE_PAYLOAD_ROOT))

_LOG_DIR = _REPO_ROOT / "Logs"
_CURRENT_LOGFILE: str | None = None


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "debug"}


def _setup_logging() -> str | None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    for entry in _LOG_DIR.glob("*.log"):
        try:
            entry.unlink()
        except OSError:
            pass

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    logfile = _LOG_DIR / f"ghostrigger_{stamp}.log"
    level = logging.DEBUG if _env_enabled("GHOSTRIGGER_DEBUG_LOG") else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    try:
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", datefmt="%H:%M:%S"))
        root_logger.addHandler(file_handler)
    except OSError:
        logfile = None

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)-34.34s  %(message)s", datefmt="%H:%M:%S"))
    root_logger.addHandler(stream_handler)

    global _CURRENT_LOGFILE
    _CURRENT_LOGFILE = str(logfile) if logfile is not None else None
    return _CURRENT_LOGFILE


def _flush_all_handlers() -> None:
    for handler in list(logging.getLogger().handlers):
        try:
            handler.flush()
        except Exception:
            pass


def _install_exception_hooks(logfile: str | None) -> None:
    crash_log = logging.getLogger("ghostrigger.crash")

    def _handle_uncaught(exc_type, exc_value, exc_tb) -> None:
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        crash_log.critical("UNHANDLED EXCEPTION:\n%s", message)
        _flush_all_handlers()
        print(f"\n{'=' * 60}\nGhostRigger CRASH - see Logs/ for full trace\n{'=' * 60}\n{message}", file=sys.stderr)

    sys.excepthook = _handle_uncaught


def _install_atexit_flush() -> None:
    shutdown_log = logging.getLogger("ghostrigger.shutdown")

    def _atexit_flush() -> None:
        shutdown_log.info("GhostRigger native-host atexit flush.")
        _flush_all_handlers()

    atexit.register(_atexit_flush)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GhostRigger native host")
    parser.add_argument("--gui", default="qt")
    parser.add_argument("model", nargs="?", help="Optional startup model path.")
    parser.add_argument("--tga", action="append", default=[])
    parser.add_argument("--texture", dest="tga", action="append")
    parser.add_argument("--texture-dir")
    parser.add_argument("--game", choices=("K1", "K2", "k1", "k2"))
    return parser.parse_args(argv)


def _precache_themes(app_dir: Path, log: logging.Logger) -> None:
    from src.gui.libtheme.theme_applier import ThemeApplier
    from src.gui.libtheme.theme_loader import ThemeLoader
    from src.gui.libtheme.theme_settings import user_config_root

    loader = ThemeLoader()
    themes = dict(loader.load_dir(app_dir / "config" / "themes" / "themes"))
    themes.update(loader.load_dir(user_config_root() / "themes"))
    if not themes:
        log.warning("Theme precache skipped; no theme XML files found.")
        return
    result = ThemeApplier.precache_stylesheets(sorted(themes.values(), key=lambda theme: (theme.id != "default", theme.name.lower(), theme.id)))
    log.info(
        "Theme precache complete: %d built, %d cached, %d failed in %.1f ms.",
        int(result["built"]),
        int(result["cached"]),
        int(result["failed"]),
        float(result["total_ms"]),
    )


def main(argv: list[str] | None = None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    logfile = _setup_logging()
    log = logging.getLogger("ghostrigger.native_main")

    log.info("=" * 60)
    log.info("GhostRigger Native Host starting - Python %s", sys.version.split()[0])
    log.info("Native host entrypoint: %s", Path(__file__).resolve())
    log.info("Visual Studio build output: %s", os.environ.get("GHOSTRIGGER_NATIVE_BUILD_OUTPUT_DIR", ""))
    log.info("Repository root: %s", _REPO_ROOT)
    log.info("Session log: %s", logfile or "DISABLED")
    log.info("=" * 60)

    if (args.gui or "qt").strip().lower() != "qt":
        log.warning("Only Qt is supported by the native host; continuing with Qt.")

    _install_exception_hooks(logfile)
    _install_atexit_flush()

    try:
        from src.core.qt_core.diagnostics.diagnostics import log_session_start
        log_session_start(str(_REPO_ROOT), logfile or "(no log file)")
    except Exception as exc:
        log.debug("diagnostics.log_session_start failed: %s", exc)

    try:
        try:
            _precache_themes(_REPO_ROOT, log)
        except Exception as exc:
            log.warning("Theme precache skipped after an unexpected error: %s", exc, exc_info=True)

        from src.gui.qt_lib.windows.qt_main_window import run as run_qt

        log.info("Qt launcher starting from native host entrypoint.")
        rc = run_qt(str(_REPO_ROOT), startup_input=vars(args))
        log.info("Qt main window exited cleanly.")
        _flush_all_handlers()
        return rc
    except Exception:
        log.critical("Fatal error during Qt startup:\n%s", traceback.format_exc())
        _flush_all_handlers()
        raise


if __name__ == "__main__":
    main()
