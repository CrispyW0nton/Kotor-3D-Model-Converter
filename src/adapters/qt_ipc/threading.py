"""Qt callback dispatch adapter for IPC services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def marshal_to_gui_thread(cb: Callable[..., Any], *args: Any) -> bool:
    """Return True when ``cb`` was scheduled on a running Qt event loop."""
    try:
        from PySide6.QtCore import QCoreApplication, QTimer  # noqa: PLC0415

        app = QCoreApplication.instance()
        if app is None:
            return False
        QTimer.singleShot(0, lambda: cb(*args))
        return True
    except Exception:
        return False

