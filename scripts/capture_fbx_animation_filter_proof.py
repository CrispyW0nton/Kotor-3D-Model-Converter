"""Capture filter-aware FBX Select All in the real Ghost Studio main window."""

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
DEFAULT_OUTPUT = ROOT / "artifacts" / "qa" / "carth_bandon_facial_export"


def run(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, object]:
    from PySide6 import QtWidgets

    from src.gui.qt_lib.dialogs.qt_fbx_animation_selection_dialog import (
        QtFbxAnimationSelectionDialog,
    )
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    startup_input = {
        "preloaded_library": {
            "k1_dir": "",
            "k2_dir": "",
            "rows": [],
            "autoscan": False,
            "detection_attempted": True,
            "detected": False,
            "error": "",
        }
    }
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input=startup_input)
    window.resize(1440, 900)
    window.show()
    rows = (
        {"name": "tlknorm", "source_model_name": "S_Male02", "scope": "Inherited", "length": 1.6},
        {"name": "walk", "source_model_name": "S_Male02", "scope": "Inherited", "length": 1.2},
        {"name": "blink", "source_model_name": "P_CarthH", "scope": "Supplemental", "length": 0.8},
        {"name": "listen", "source_model_name": "P_CarthH", "scope": "Local", "length": 1.0},
    )
    dialog = QtFbxAnimationSelectionDialog(
        rows,
        parent=window,
        profile="unity",
        initial_selected_names=tuple(str(row["name"]) for row in rows),
    )
    dialog.resize(900, 520)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    for _ in range(12):
        app.processEvents()
        time.sleep(0.03)
    dialog._search_edit.setText("S_Male02")
    app.processEvents()
    dialog._select_all_button.click()
    for _ in range(8):
        app.processEvents()
        time.sleep(0.03)

    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "fbx_animation_filter_select_all_main_window.png"
    screen = app.primaryScreen()
    pixmap = screen.grabWindow(int(dialog.winId())) if screen is not None else dialog.grab()
    saved = bool(pixmap.save(str(screenshot_path), "PNG"))
    selected = dialog.selected_animation_names()
    visible = tuple(
        dialog._tree.topLevelItem(index).text(0)
        for index in range(dialog._tree.topLevelItemCount())
        if not dialog._tree.topLevelItem(index).isHidden()
    )
    hidden_checked = tuple(
        dialog._tree.topLevelItem(index).text(0)
        for index in range(dialog._tree.topLevelItemCount())
        if dialog._tree.topLevelItem(index).isHidden()
        and dialog._tree.topLevelItem(index).checkState(0).value == 2
    )
    expected = ("tlknorm", "walk")
    report = {
        "status": (
            "pass"
            if saved and selected == visible == expected and not hidden_checked
            else "fail"
        ),
        "filter": "S_Male02",
        "visible": list(visible),
        "selected": list(selected),
        "hidden_checked": list(hidden_checked),
        "screenshot": str(screenshot_path),
    }
    (output_dir / "fbx_animation_filter_select_all_proof.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    dialog.close()
    window.close()
    app.processEvents()
    if report["status"] != "pass":
        raise RuntimeError(f"Filter-aware Select All proof failed: {report}")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
