from __future__ import annotations

import os

from qtpy.QtWidgets import QApplication


def running_under_pytest() -> bool:
    # pytest always sets this while executing tests.
    return "PYTEST_CURRENT_TEST" in os.environ


def process_events_if_safe() -> None:
    """Process Qt events only when it is safe.

    pytest-qt runs its own event processing loop and can deadlock if production
    code calls QApplication.processEvents() re-entrantly during those waits.

    This helper intentionally becomes a no-op under pytest.
    """

    if running_under_pytest():
        return

    if os.environ.get("PYKOTOR_QT_SKIP_PROCESS_EVENTS") == "1":
        return

    app = QApplication.instance()
    if app is None:
        return

    QApplication.processEvents()
