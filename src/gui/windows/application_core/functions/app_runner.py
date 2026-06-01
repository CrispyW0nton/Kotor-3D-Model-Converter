"""Qt application runner helper for the main GhostRigger window."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Optional

try:
    from PySide6 import QtGui, QtWidgets
except ImportError as exc:  # pragma: no cover - import gate for Qt runtime
    raise RuntimeError("PySide6 is required for the Qt shell") from exc

from src.gui.libtheme import ThemeManager


def run_qt_application(
    app_root: Optional[str],
    startup_input: Optional[dict],
    *,
    window_cls,
    splash_cls,
    read_settings: Callable[[Path], dict],
    collect_startup_diagnostics: Callable[[dict], dict],
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
    startup_diagnostics = collect_startup_diagnostics(settings_data)
    startup_theme_manager = ThemeManager(root, settings_data)
    splash = splash_cls(root, theme_manager=startup_theme_manager)
    splash.show()

    def update_prelaunch_status(title: str, detail: str) -> None:
        finished = title.lower().endswith("ready")
        splash.set_status(title, detail, finished=finished)
        splash.show()
        splash.raise_()
        app.processEvents()

    update_prelaunch_status("Preparing startup", "Checking saved game-library settings...")
    prepared_input = build_prelaunch_library_input(root, startup_input, update_prelaunch_status)
    prepared_input.update(startup_diagnostics)
    update_prelaunch_status("Opening workspace", "Starting the main window.")
    app.processEvents()
    win = window_cls(root, startup_input=prepared_input)
    win.show()
    splash.close()
    return app.exec()
