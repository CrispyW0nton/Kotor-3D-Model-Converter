from __future__ import annotations

import sys

from qtpy.QtCore import QThread
from qtpy.QtWidgets import QApplication

from holopazaak.config import CURRENT_VERSION
from holopazaak.main_settings import setup_holopazaak_default_env, setup_post_init_settings, setup_pre_init_settings
from holopazaak.ui.mainwindow import PazaakWindow


def qt_cleanup():
    """Cleanup so we can exit."""
    print("Closing HoloPazaak...")


def main():
    """Main entry point for HoloPazaak.

    This block is ran when users run __main__.py directly.
    """
    setup_pre_init_settings()

    app = QApplication(sys.argv)
    app.setApplicationName("HoloPazaak")
    app.setOrganizationName("PyKotor")
    app.setOrganizationDomain("github.com/th3w1zard1/PyKotor")
    app.setApplicationVersion(CURRENT_VERSION)
    app.setDesktopFileName("com.pykotor.holopazaak")
    app.setApplicationDisplayName("HoloPazaak")

    # Application icon will be set by the window if needed
    # For now, we rely on system defaults rather than requiring Qt resource files

    main_gui_thread: QThread | None = app.thread()
    assert main_gui_thread is not None, "Main GUI thread should not be None"
    main_gui_thread.setPriority(QThread.Priority.HighestPriority)
    app.aboutToQuit.connect(qt_cleanup)

    setup_post_init_settings()
    setup_holopazaak_default_env()

    window = PazaakWindow()
    window.show()
    sys.exit(app.exec())
