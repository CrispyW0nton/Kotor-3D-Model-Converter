"""Visible proof: Particle Editor opens from the main-window toolbar action,
lists both game emitter libraries, live-edits plc_starmap emitters, and
applies a retail template.

Run: py -3.14 scripts/capture_particle_editor_proof.py
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


def _grab(app, widget, path: Path) -> dict:
    widget.raise_()
    widget.activateWindow()
    _process_events(app, 0.15)
    pixmap = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    return {"path": str(path), "saved": bool(pixmap.save(str(path), "PNG"))}


def main() -> int:
    from PySide6 import QtWidgets

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = QtGhostRiggerMainWindow()
    window.resize(1600, 950)
    window.show()
    _process_events(app, 1.5)

    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    if not window.k1_dir_edit.text().strip():
        window.k1_dir_edit.setText(str(settings.get("k1_dir", "") or ""))
    if not window.k2_dir_edit.text().strip():
        window.k2_dir_edit.setText(str(settings.get("k2_dir", "") or ""))

    report: dict = {"proof": "particle editor workspace"}

    # 1. The toolbar action must exist and open the editor window.
    action = getattr(window, "particle_editor_action", None)
    assert action is not None, "particle_editor_action missing from main window chrome"
    report["toolbar_action"] = action.text()
    action.trigger()
    _process_events(app, 1.0)
    editor = getattr(window, "particle_editor_window", None)
    assert editor is not None and editor.isVisible(), "Particle Editor window did not open"

    # 2. Cached K1/K2 emitter libraries populate in the background.
    for _ in range(600):
        _process_events(app, 0.1)
        if editor.k1_group.childCount() > 0 and editor.k2_group.childCount() > 0:
            break
    k1_templates = len(editor._templates.get("K1", []))
    k2_templates = len(editor._templates.get("K2", []))
    report["k1_templates"] = k1_templates
    report["k2_templates"] = k2_templates

    # 3. Load plc_starmap into the editor preview and select an emitter.
    editor.game_combo.setCurrentText("K1")
    editor.resref_edit.setText("plc_starmap")
    editor._load_requested_model()
    _process_events(app, 4.0)
    assert editor.model_group.childCount() == 76, "starmap emitters not listed"
    target = None
    for index in range(editor.model_group.childCount()):
        child = editor.model_group.child(index)
        if child.text(0) == "Sun_gas":
            target = child
            break
    editor.tree.setCurrentItem(target)
    _process_events(app, 2.0)
    report["selected"] = editor.selected_label.text()

    # 4. Live-edit a parameter; the simulation must keep producing particles.
    editor._scalar_widgets["birthrate"].setValue(150.0)
    _process_events(app, 2.5)
    renderer = getattr(editor.viewport, "_gpu_renderer", None)
    particles = int(getattr(renderer, "perf", {}).get("particles", 0) or 0)
    report["particles_after_edit"] = particles

    # 5. Apply a K2 retail template to the selected emitter (cross-game reuse).
    template = None
    for candidate in editor._templates.get("K2", []):
        defn = candidate.definition
        if str(defn.get("update", "")) == "Fountain" and defn.get("texture"):
            template = candidate
            break
    assert template is not None, "no K2 fountain template available"
    editor._apply_template(template)
    _process_events(app, 2.0)
    report["applied_template"] = template.key
    report["texture_after_template"] = editor.texture_edit.text()

    report["screenshot"] = _grab(app, editor, OUT_DIR / "particle_editor.png")

    ok = (
        k1_templates > 1000
        and k2_templates > 1000
        and particles > 50
        and report["screenshot"]["saved"]
    )
    report["result"] = "PASS" if ok else "FAIL"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "particle_editor_proof.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    editor.close()
    window.close()
    _process_events(app, 0.3)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
