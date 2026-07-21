"""Visible proof: plc_starmap emitter particles in the real main window.

Loads K1 ``plc_starmap`` through the normal game-resource load path, plays the
looped ``on`` animation, lets the viewport's live particle scheduling run, and
captures window screenshots plus renderer particle counters.

Run: py -3.14 scripts/capture_starmap_particle_proof.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

OUT_DIR = ROOT / "artifacts" / "particle_proof"


def _process_events(app, seconds: float) -> None:
    deadline = time.perf_counter() + max(0.0, float(seconds))
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _screen_grab(app, window, path: Path) -> dict:
    window.raise_()
    window.activateWindow()
    _process_events(app, 0.15)
    screen = app.primaryScreen()
    pixmap = screen.grabWindow(int(window.winId())) if screen is not None else window.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = bool(pixmap.save(str(path), "PNG"))
    return {"path": str(path), "saved": saved, "width": pixmap.width(), "height": pixmap.height()}


def main() -> int:
    from PySide6 import QtWidgets

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtGhostRiggerMainWindow()
    window.resize(1600, 950)
    window.show()
    _process_events(app, 1.5)

    # A fresh proof profile may not carry the user's game paths; seed them from
    # the repository settings.json so the game-resource load route works.
    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    if not window.k1_dir_edit.text().strip():
        window.k1_dir_edit.setText(str(settings.get("k1_dir", "") or ""))
    if not window.k2_dir_edit.text().strip():
        window.k2_dir_edit.setText(str(settings.get("k2_dir", "") or ""))

    report: dict = {"proof": "starmap emitter particles", "steps": []}

    # 1. Load K1 plc_starmap via the standard game-resource route.
    window._start_resource_load("plc_starmap", "K1", import_action="clear")
    for _ in range(200):
        _process_events(app, 0.1)
        model = getattr(window, "_current_model", None)
        if model is not None and "starmap" in str(getattr(model, "name", "")).lower():
            break
    model = getattr(window, "_current_model", None)
    assert model is not None, "plc_starmap did not load"
    emitter_count = sum(1 for node in model.all_nodes() if getattr(node, "is_emitter", False))
    report["model"] = str(getattr(model, "name", ""))
    report["emitter_nodes"] = emitter_count
    _process_events(app, 3.0)  # texture prewarm

    viewport = window.viewport

    def _renderer_particles() -> tuple[int, bool]:
        renderer = getattr(viewport, "_gpu_renderer", None)
        perf = getattr(renderer, "perf", {}) if renderer is not None else {}
        return int(perf.get("particles", 0) or 0), bool(getattr(renderer, "particles_active", False))

    # 2. Bind pose: let particle frames run on their own scheduling.
    _process_events(app, 2.0)
    bind_particles, bind_active = _renderer_particles()
    report["bind_pose"] = {"particles": bind_particles, "active": bind_active}
    report["screenshot_bind"] = _screen_grab(app, window, OUT_DIR / "starmap_bind.png")

    # 3. Play the looped "on" animation and let the effect develop.
    played = window._terminal_play_animation("on", loop=True)
    report["played_animation"] = played
    _process_events(app, 5.0)
    on_particles, on_active = _renderer_particles()
    report["on_animation"] = {"particles": on_particles, "active": on_active}
    report["screenshot_on"] = _screen_grab(app, window, OUT_DIR / "starmap_on.png")

    # 4. Stop playback; bind-pose emitters (sun gas) must keep simulating.
    window._terminal_stop_animation()
    _process_events(app, 2.0)
    stop_particles, stop_active = _renderer_particles()
    report["after_stop"] = {"particles": stop_particles, "active": stop_active}
    report["screenshot_stopped"] = _screen_grab(app, window, OUT_DIR / "starmap_stopped.png")

    ok = on_particles > 0 and bool(report["screenshot_on"]["saved"])
    report["result"] = "PASS" if ok else "FAIL"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "starmap_particle_proof.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    window.close()
    _process_events(app, 0.3)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
