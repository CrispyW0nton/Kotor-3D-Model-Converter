"""Optional watchdog-based hot reload for theme and layout XML."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6 import QtCore

log = logging.getLogger(__name__)


class ThemeLayoutWatcher(QtCore.QObject):
    changed = QtCore.Signal(str, str)

    def __init__(self, paths: list[Path], parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.paths = [Path(path) for path in paths]
        self._observer = None

    def start(self) -> bool:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except Exception as exc:
            log.debug("watchdog unavailable: %s", exc)
            return False

        owner = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):  # type: ignore[no-untyped-def]
                if not event.is_directory and str(event.src_path).lower().endswith(".xml"):
                    owner.changed.emit("modified", str(event.src_path))

            def on_created(self, event):  # type: ignore[no-untyped-def]
                if not event.is_directory and str(event.src_path).lower().endswith(".xml"):
                    owner.changed.emit("created", str(event.src_path))

        observer = Observer()
        for path in self.paths:
            if path.exists():
                observer.schedule(Handler(), str(path), recursive=False)
        observer.daemon = True
        observer.start()
        self._observer = observer
        return True

    def stop(self) -> None:
        observer = self._observer
        if observer is None:
            return
        observer.stop()
        observer.join(timeout=1.0)
        self._observer = None
