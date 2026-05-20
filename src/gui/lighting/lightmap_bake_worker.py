"""Qt worker wrapper for background lightmap bakes."""

from __future__ import annotations

try:
    from PySide6 import QtCore
except Exception:  # pragma: no cover
    QtCore = None

from .lightmap_bake_job import LightmapBakeJob
from .lightmap_baker import LightmapBaker


if QtCore is not None:

    class LightmapBakeWorker(QtCore.QObject):
        progress = QtCore.Signal(str, int, int, str)
        finished = QtCore.Signal(object)

        def __init__(self, job: LightmapBakeJob, baker: LightmapBaker | None = None):
            super().__init__()
            self.job = job
            self.baker = baker or LightmapBaker()
            self._cancelled = False
            self.job.progress = self.progress.emit
            self.job.should_cancel = lambda: self._cancelled

        @QtCore.Slot()
        def run(self) -> None:
            self.finished.emit(self.baker.bake(self.job))

        @QtCore.Slot()
        def cancel(self) -> None:
            self._cancelled = True

else:

    class LightmapBakeWorker:  # type: ignore[no-redef]
        def __init__(self, job: LightmapBakeJob, baker: LightmapBaker | None = None):
            self.job = job
            self.baker = baker or LightmapBaker()
            self._cancelled = False

        def run(self):
            return self.baker.bake(self.job)

        def cancel(self) -> None:
            self._cancelled = True
