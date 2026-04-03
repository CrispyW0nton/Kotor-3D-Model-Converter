from __future__ import annotations

from utility.gui.qt.kernel.qplatformdialoghelper.qplatformdialoghelper import QFileDialogPlatformHelper


class MacFileDialogHelper(QFileDialogPlatformHelper):
    def show_dialog(self) -> bool:
        try:
            from AppKit import NSURL, NSModalResponseOK, NSOpenPanel, NSSavePanel
        except ImportError:
            print("AppKit is not available. Make sure you're running on macOS.")
            return False

        from utility.gui.qt.adapters.filesystem.qfiledialog.qfiledialog import QFileDialog

        if self._options.acceptMode() == QFileDialog.AcceptMode.AcceptOpen:
            panel = NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(self._options.fileMode() != QFileDialog.FileMode.Directory)
            panel.setCanChooseDirectories_(self._options.fileMode() in [QFileDialog.FileMode.Directory, QFileDialog.FileMode.ExistingFiles])
            panel.setAllowsMultipleSelection_(self._options.fileMode() == QFileDialog.FileMode.ExistingFiles)
        else:
            panel = NSSavePanel.savePanel()

        panel.setDirectoryURL_(NSURL.fileURLWithPath_(self._current_directory))

        if panel.runModal() == NSModalResponseOK:
            if isinstance(panel, NSOpenPanel):
                self._selected_files = [url.path() for url in panel.URLs()]
            else:
                self._selected_files = [panel.URL().path()]
            return True
        return False
