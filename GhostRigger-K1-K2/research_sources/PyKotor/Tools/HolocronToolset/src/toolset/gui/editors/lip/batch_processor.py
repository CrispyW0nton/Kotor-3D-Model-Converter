"""Batch processor for LIP files."""

from __future__ import annotations

import wave

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
)

from pykotor.resource.formats.lip import LIP, LIPShape, bytes_lip

if TYPE_CHECKING:
    from qtpy.QtWidgets import (
        QWidget,
    )

    from toolset.data.installation import HTInstallation


class BatchLIPProcessor(QDialog):
    """Dialog for batch processing LIP files."""

    def __init__(self, parent: QWidget | None = None, installation: HTInstallation | None = None):
        """Initialize the batch processor."""
        super().__init__(parent)
        from toolset.uic.qtpy.dialogs.batch_processor import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.installation = installation

        # Connect signals
        self.ui.addAudioBtn.clicked.connect(self.add_audio_files)
        self.ui.removeAudioBtn.clicked.connect(self.remove_audio_file)
        self.ui.clearAudioBtn.clicked.connect(self.clear_audio_files)
        self.ui.browseBtn.clicked.connect(self.browse_output_dir)
        self.ui.processBtn.clicked.connect(self.process_files)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        # Keep track of files
        self.audio_files: list[Path] = []
        self.output_dir: Optional[Path] = None

    def add_audio_files(self):
        """Add WAV files to process."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Audio Files", "", "Audio Files (*.wav)")
        for file in files:
            path = Path(file)
            if path not in self.audio_files:
                self.audio_files.append(path)
                self.ui.audioList.addItem(path.name)

    def remove_audio_file(self):
        """Remove selected audio file."""
        selected = self.ui.audioList.selectedItems()
        if not selected:
            return

        for item in selected:
            idx = self.ui.audioList.row(item)
            self.audio_files.pop(idx)
            self.ui.audioList.takeItem(idx)

    def clear_audio_files(self):
        """Clear all audio files."""
        self.audio_files.clear()
        self.ui.audioList.clear()

    def browse_output_dir(self):
        """Select output directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir = Path(dir_path)
            self.ui.outputPath.setText(str(self.output_dir))

    def process_files(self):
        """Process all audio files."""
        if not self.audio_files:
            QMessageBox.warning(self, "Error", "No audio files selected")
            return

        if not self.output_dir:
            QMessageBox.warning(self, "Error", "No output directory selected")
            return

        errors = []
        for audio_file in self.audio_files:
            try:
                # Create LIP file
                lip = LIP()

                # Get audio duration
                with wave.open(str(audio_file), "rb") as wav:
                    frames = wav.getnframes()
                    rate = wav.getframerate()
                    duration = frames / float(rate)
                    lip.length = duration

                # Add some basic lip sync - this could be enhanced
                # Currently just adds a few basic shapes evenly spaced
                shapes = [
                    LIPShape.MPB,  # Start with closed mouth
                    LIPShape.AH,  # Open for vowel sound
                    LIPShape.OH,  # Round for O sound
                    LIPShape.MPB,  # Close mouth again
                ]

                interval = duration / (len(shapes) + 1)
                for i, shape in enumerate(shapes, 1):
                    lip.add(interval * i, shape)

                # Save LIP file
                output_path = self.output_dir / f"{audio_file.stem}.lip"
                with open(output_path, "wb") as f:
                    f.write(bytes_lip(lip))

            except Exception as e:
                errors.append(f"{audio_file.name}: {str(e)}")

        if errors:
            QMessageBox.warning(self, "Errors Occurred", "The following errors occurred:\n\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Success", f"Successfully processed {len(self.audio_files)} files")
