"""Startup, settings, and game-library helper functions for application-core windows."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import traceback
from pathlib import Path
from typing import Optional

from src.gui.qt_lib.dialogs.qt_settings_dialog import save_settings
from src.gui.qt_lib.panels.qt_library_panel import enrich_library_rows, enrich_library_rows_with_resource_metadata
from src.core.rendering.hardware_info import collect_hardware_diagnostics
from src.adapters.rendering.renderer_factory import renderer_capabilities_snapshot
from src.core.rendering.renderer_settings import RendererSettings

log = logging.getLogger(__name__)

def _index_game_libraries_sync(k1_dir: str = "", k2_dir: str = "") -> tuple[object, list[dict]]:
    from src.core.assets.resource_manager import ResourceManager

    mgr = ResourceManager()
    rows = []
    if k1_dir:
        ok = mgr.set_k1_dir(k1_dir)
        if ok:
            for resref, _restype in mgr.list_models("K1"):
                rows.append({"game": "K1", "resref": resref, "source": k1_dir})
    if k2_dir:
        ok = mgr.set_k2_dir(k2_dir)
        if ok:
            for resref, _restype in mgr.list_models("K2"):
                rows.append({"game": "K2", "resref": resref, "source": k2_dir})
    rows = enrich_library_rows(enrich_library_rows_with_resource_metadata(rows, mgr))
    rows.sort(key=lambda item: (item["game"], item["resref"]))
    return mgr, rows
def _scan_library_rows_sync(k1_dir: str = "", k2_dir: str = "") -> list[dict]:
    _mgr, rows = _index_game_libraries_sync(k1_dir, k2_dir)
    return rows
def _read_settings_file(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.warning("Could not read settings from %s", path, exc_info=True)
    return {}
def _write_settings_file(path: Path, values: dict) -> None:
    try:
        save_settings(path, values)
    except Exception:
        log.warning("Could not save settings to %s", path, exc_info=True)
def _build_prelaunch_library_input(
    app_root: Path,
    startup_input: Optional[dict] = None,
    status_callback=None,
    *,
    indexer=None,
    read_settings=None,
    write_settings=None,
) -> dict:
    payload = dict(startup_input or {})
    settings_path = app_root / "settings.json"
    indexer = indexer or _index_game_libraries_sync
    read_settings = read_settings or _read_settings_file
    write_settings = write_settings or _write_settings_file
    settings = read_settings(settings_path)
    autoscan = bool(settings.get("autoscan", True))
    k1_dir = str(settings.get("k1_dir") or "").strip()
    k2_dir = str(settings.get("k2_dir") or "").strip()
    detected = False

    def status(title: str, detail: str) -> None:
        if status_callback is not None:
            status_callback(title, detail)

    status("Detecting game installs", "Checking saved paths and installed KotOR directories...")
    if not (k1_dir and k2_dir):
        from src.resources.game_detector import detect_kotor_dirs, save_config

        found_k1, found_k2 = detect_kotor_dirs()
        if found_k1 and not k1_dir:
            k1_dir = found_k1
            settings["k1_dir"] = found_k1
            detected = True
        if found_k2 and not k2_dir:
            k2_dir = found_k2
            settings["k2_dir"] = found_k2
            detected = True
        if detected:
            save_config(k1_dir or None, k2_dir or None)
            write_settings(settings_path, settings)

    preloaded = {
        "k1_dir": k1_dir,
        "k2_dir": k2_dir,
        "rows": [],
        "error": "",
        "autoscan": autoscan,
        "detection_attempted": True,
        "detected": detected,
    }
    payload["preloaded_library"] = preloaded
    if not (k1_dir or k2_dir):
        preloaded["error"] = "No KotOR game directories were detected."
        status("No game installs found", "GhostRigger will open with an empty Content Browser.")
        return payload
    if not autoscan:
        status("Game installs ready", "Startup library scan is disabled in Settings.")
        return payload

    try:
        status("Indexing game libraries", "Scanning model resources before the main window opens...")
        resource_manager, rows = indexer(k1_dir, k2_dir)
        preloaded["_resource_manager"] = resource_manager
        preloaded["rows"] = rows
        status("Library ready", f"{len(preloaded['rows'])} model resources indexed.")
    except Exception:
        preloaded["error"] = traceback.format_exc()
        status("Library scan failed", "GhostRigger will open; see the output log for details.")
    return payload
def _collect_prewindow_startup_diagnostics(settings_data: dict, status_callback=None) -> dict:
    """Collect renderer/hardware diagnostics before the main window exists."""

    payload = {"renderer_capabilities": [], "hardware_diagnostics": {}}
    renderer_settings = RendererSettings.from_settings(settings_data)

    def status(title: str, detail: str) -> None:
        if status_callback is not None:
            status_callback(title, detail)

    def scan_renderer_capabilities() -> list[dict]:
        status("Checking renderer backends", "Scanning native renderer capability exports...")
        log.info("Startup renderer scan beginning before Qt main-window initialization.")
        try:
            caps = renderer_capabilities_snapshot()
            for entry in caps:
                state = "available" if entry.available else f"unavailable: {entry.reason or 'no reason reported'}"
                log.info("Startup renderer scan: %s is %s.", entry.name, state)
            status("Renderer backends ready", f"{len(caps)} renderer capability records collected.")
            return [entry.to_dict() for entry in caps]
        except Exception as exc:
            log.warning("Startup renderer scan failed before main-window initialization: %s", exc, exc_info=True)
            status("Renderer scan failed", "GhostRigger will open with fallback renderer capability data.")
            return []

    def scan_hardware_diagnostics() -> dict:
        status("Checking graphics hardware", "Collecting GPU and viewport timing diagnostics...")
        log.info("Startup hardware scan beginning before Qt main-window initialization.")
        try:
            hardware = collect_hardware_diagnostics(
                renderer_diagnostics={
                    "backend_id": renderer_settings.backend.value,
                    "name": renderer_settings.backend.value,
                },
                target_fps=renderer_settings.target_fps,
            )
            for line in hardware.lines():
                log.info("Startup hardware scan: %s", line)
            status("Graphics hardware ready", "Startup hardware diagnostics collected.")
            return hardware.to_dict()
        except Exception as exc:
            log.warning("Startup hardware scan failed before main-window initialization: %s", exc, exc_info=True)
            status("Graphics hardware scan failed", "GhostRigger will open with hardware diagnostics marked unavailable.")
            return {"unavailable_reason": str(exc)}

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="GRStartupDiagnostics") as executor:
        renderer_future = executor.submit(scan_renderer_capabilities)
        hardware_future = executor.submit(scan_hardware_diagnostics)
        payload["renderer_capabilities"] = renderer_future.result()
        payload["hardware_diagnostics"] = hardware_future.result()
    return payload
