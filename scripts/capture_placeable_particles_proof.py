"""Visible proof: game particle assets attached to a placeable in the
Placeable Builder — the K2 Ebon Hawk planet hologram (plc_holopera) grafted
onto a plain placeable model, simulating live in the builder preview.

Run: py -3.14 scripts/capture_placeable_particles_proof.py
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


def main() -> int:
    from PySide6 import QtWidgets

    from src.core.assets.resource_manager import ResourceManager
    from src.gui.qt_lib.windows.qt_placeable_builder import QtPlaceableBuilderWindow
    from src.gui.qt_lib.windows.qt_placeable_builder_controller import QtPlaceableBuilderController

    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    manager = ResourceManager()
    manager.set_k1_dir(settings.get("k1_dir", ""))
    manager.set_k2_dir(settings.get("k2_dir", ""))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtPlaceableBuilderWindow(None)
    controller = QtPlaceableBuilderController(
        window,
        library_root=ROOT / "Saved" / "PlaceableLibrary",
        resource_manager=manager,
        parent=window,
    )
    window.resize(1500, 900)
    window.show()
    _process_events(app, 1.5)

    report: dict = {"proof": "placeable builder particle assets"}

    # 1. Point the placeable's custom visual at a plain model (K2 footlocker).
    window.game_combo.setCurrentText("K2")
    window.mdl_resref_edit.setText("plc_footlker")
    window.mdl_resref_edit.textEdited.emit("plc_footlker")
    window._document_edited()
    _process_events(app, 4.0)

    # 2. Attach the ENTIRE Ebon Hawk planet hologram effect from the library
    #    (the same records the picker dialog produces via Add Entire Effect).
    from src.core.particles.emitter_library import build_effect_records

    source = manager.load_model("plc_holopera", "K2")
    assert source is not None, "plc_holopera did not load"
    records = build_effect_records(source, "K2", "plc_holopera")
    report["effect_emitters"] = len(records)
    for record in records:
        record["offset"] = [0.0, 0.0, 0.6]  # hover the hologram above the box
    window._particle_effects.extend(records)
    window._refresh_particle_effects_table()
    window._document_edited()
    _process_events(app, 6.0)

    # 3. The document must carry the effects; the preview must simulate them.
    document = window.current_document()
    stored = document.get("metadata", {}).get("particle_effects", [])
    report["stored_effects"] = len(stored)

    viewport = window.preview_viewport
    # Frame generously: the hologram hovers ~2.3 units above the crate, well
    # outside the base model's own bounds.
    frame_bounds = getattr(getattr(viewport, "camera", None), "frame_bounds", None)
    if callable(frame_bounds):
        frame_bounds((-2.5, -2.5, 0.0), (2.5, 2.5, 4.5))
        request = getattr(viewport, "_request_render", None)
        if callable(request):
            request(reason="proof framing", camera=True, scene=True)
    _process_events(app, 6.0)
    renderer = getattr(viewport, "_gpu_renderer", None)
    particles = int(getattr(renderer, "perf", {}).get("particles", 0) or 0)
    draw_calls = int(getattr(renderer, "perf", {}).get("particle_draw_calls", 0) or 0)
    report["preview_particles"] = particles
    report["preview_draw_calls"] = draw_calls
    report["preview_status"] = window.preview_status_label.text()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pixmap = window.grab()
    shot = OUT_DIR / "placeable_holo_particles.png"
    pixmap.save(str(shot), "PNG")
    report["screenshot"] = str(shot)

    ok = len(stored) == len(records) and particles > 0
    report["result"] = "PASS" if ok else "FAIL"
    (OUT_DIR / "placeable_particles_proof.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))

    window.close()
    _process_events(app, 0.3)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
