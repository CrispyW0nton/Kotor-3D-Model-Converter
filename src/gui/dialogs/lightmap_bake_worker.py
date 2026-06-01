"""Qt worker wrapper for background lightmap bakes."""

from __future__ import annotations

try:
    from PySide6 import QtCore
except Exception:  # pragma: no cover
    QtCore = None

from src.adapters.gpu.lightmap_baker import LightmapBaker
from src.core.lighting.lightmap_bake_job import LightmapBakeJob


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


    class LightmapPreviewBakeWorker(QtCore.QObject):
        finished = QtCore.Signal(object)

        def __init__(self, mesh: object, lights: list[object], settings, baker: LightmapBaker | None = None):
            super().__init__()
            self.mesh = mesh
            self.lights = list(lights)
            self.settings = settings
            self.baker = baker or LightmapBaker()
            self._cancelled = False

        @QtCore.Slot()
        def run(self) -> None:
            self.finished.emit(
                self.baker.bake_preview(
                    self.mesh,
                    self.lights,
                    self.settings,
                    should_cancel=lambda: self._cancelled,
                )
            )

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


    class LightmapPreviewBakeWorker:  # type: ignore[no-redef]
        def __init__(self, mesh: object, lights: list[object], settings, baker: LightmapBaker | None = None):
            self.mesh = mesh
            self.lights = list(lights)
            self.settings = settings
            self.baker = baker or LightmapBaker()
            self._cancelled = False

        def run(self):
            return self.baker.bake_preview(self.mesh, self.lights, self.settings, should_cancel=lambda: self._cancelled)

        def cancel(self) -> None:
            self._cancelled = True
