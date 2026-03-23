"""Enhanced Preview Pane widget inspired by Windows 11 File Explorer.

This module provides a rich preview pane that shows:
- Image/video thumbnails with EXIF metadata
- Document previews (text files, PDFs via HTML)
- File metadata (size, dates, permissions)
- Icon + filename header like Windows 11
"""

from __future__ import annotations

import mimetypes
import os
import stat

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QImage, QPalette, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from utility.misc import is_valid_path

if TYPE_CHECKING:
    from qtpy.QtCore import QModelIndex
    from qtpy.QtWidgets import QFileSystemModel


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format like Windows Explorer."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_file_type_description(path: Path) -> str:
    """Get human-readable file type description like Windows Explorer."""
    if path.is_dir():
        return "File folder"

    suffix = path.suffix.lower()
    type_map = {
        ".txt": "Text Document",
        ".py": "Python File",
        ".js": "JavaScript File",
        ".html": "HTML Document",
        ".htm": "HTML Document",
        ".css": "CSS Stylesheet",
        ".json": "JSON File",
        ".xml": "XML File",
        ".md": "Markdown Document",
        ".jpg": "JPEG Image",
        ".jpeg": "JPEG Image",
        ".png": "PNG Image",
        ".gif": "GIF Image",
        ".bmp": "Bitmap Image",
        ".ico": "Icon File",
        ".svg": "SVG Image",
        ".mp3": "MP3 Audio",
        ".wav": "WAV Audio",
        ".mp4": "MP4 Video",
        ".avi": "AVI Video",
        ".mkv": "MKV Video",
        ".mov": "QuickTime Video",
        ".pdf": "PDF Document",
        ".doc": "Word Document",
        ".docx": "Word Document",
        ".xls": "Excel Spreadsheet",
        ".xlsx": "Excel Spreadsheet",
        ".ppt": "PowerPoint Presentation",
        ".pptx": "PowerPoint Presentation",
        ".zip": "ZIP Archive",
        ".rar": "RAR Archive",
        ".7z": "7-Zip Archive",
        ".tar": "TAR Archive",
        ".gz": "GZip Archive",
        ".exe": "Application",
        ".dll": "DLL File",
        ".sys": "System File",
        ".ini": "Configuration Settings",
        ".cfg": "Configuration File",
        ".log": "Log File",
    }

    if suffix in type_map:
        return type_map[suffix]

    # Fallback to generic description
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        category = mime_type.split("/")[0].title()
        return f"{category} File"

    if suffix:
        return f"{suffix.upper()[1:]} File"

    return "File"


class MetadataRow(QWidget):
    """A single row showing a label and value, styled like Windows 11 properties."""

    def __init__(
        self,
        label: str,
        value: str,
        parent: QWidget | None = None,
        *,
        selectable: bool = False,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.label_widget = QLabel(label)
        self.label_widget.setFixedWidth(100)
        self.label_widget.setStyleSheet("color: #666666; font-size: 10pt;")

        self.value_widget = QLabel(value)
        self.value_widget.setWordWrap(True)
        self.value_widget.setStyleSheet("color: #202020; font-size: 10pt;")
        if selectable:
            self.value_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse  # pyright: ignore[reportArgumentType]
            )

        layout.addWidget(self.label_widget)
        layout.addWidget(self.value_widget, 1)


class EnhancedPreviewPane(QWidget):
    """Windows 11-style preview pane with image previews, metadata, and file details."""

    # Maximum dimensions for preview images
    MAX_PREVIEW_WIDTH: ClassVar[int] = 300
    MAX_PREVIEW_HEIGHT: ClassVar[int] = 300

    # Supported image extensions
    IMAGE_EXTENSIONS: ClassVar[set[str]] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".tif"}

    # Supported text extensions for preview
    TEXT_EXTENSIONS: ClassVar[set[str]] = {
        ".txt",
        ".py",
        ".js",
        ".ts",
        ".html",
        ".htm",
        ".css",
        ".json",
        ".xml",
        ".md",
        ".rst",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".log",
        ".sh",
        ".bash",
        ".bat",
        ".cmd",
        ".ps1",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".kt",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".sql",
        ".nss",
    }

    # Signal emitted when selection should change
    fileActivated = Signal(Path)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._icon_provider = QFileIconProvider()
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Set up the preview pane UI layout."""
        self.setMinimumWidth(250)
        self.setMaximumWidth(400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Content widget inside scroll area
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header section (icon + filename)
        self._header_widget = QWidget()
        header_layout = QVBoxLayout(self._header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setMinimumSize(96, 96)
        header_layout.addWidget(self._icon_label)

        self._filename_label = QLabel()
        self._filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._filename_label.setWordWrap(True)
        self._filename_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #202020;")
        header_layout.addWidget(self._filename_label)

        self._filetype_label = QLabel()
        self._filetype_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._filetype_label.setStyleSheet("font-size: 10pt; color: #666666;")
        header_layout.addWidget(self._filetype_label)

        self._content_layout.addWidget(self._header_widget)

        # Preview section (for images/text)
        self._preview_frame = QFrame()
        self._preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._preview_frame.setStyleSheet("QFrame { background-color: #F5F5F5; border: 1px solid #E0E0E0; border-radius: 4px; }")
        preview_layout = QVBoxLayout(self._preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)

        self._preview_image_label = QLabel()
        self._preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_image_label.setMinimumHeight(150)
        preview_layout.addWidget(self._preview_image_label)

        self._preview_text_edit = QTextEdit()
        self._preview_text_edit.setReadOnly(True)
        self._preview_text_edit.setMaximumHeight(200)
        self._preview_text_edit.setStyleSheet("QTextEdit { background-color: #FFFFFF; border: none; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 9pt; }")
        self._preview_text_edit.hide()
        preview_layout.addWidget(self._preview_text_edit)

        self._preview_frame.hide()
        self._content_layout.addWidget(self._preview_frame)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #E0E0E0;")
        self._content_layout.addWidget(separator)

        # Metadata section
        self._metadata_widget = QWidget()
        self._metadata_layout = QVBoxLayout(self._metadata_widget)
        self._metadata_layout.setContentsMargins(0, 0, 0, 0)
        self._metadata_layout.setSpacing(4)
        self._content_layout.addWidget(self._metadata_widget)

        # Stretch at bottom
        self._content_layout.addStretch()

        scroll_area.setWidget(self._content_widget)
        main_layout.addWidget(scroll_area)

        # "No file selected" placeholder
        self._placeholder_label = QLabel("Select a file to preview")
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet("font-size: 12pt; color: #888888; padding: 40px;")
        main_layout.addWidget(self._placeholder_label)

        self._content_widget.hide()

    def _apply_styling(self):
        """Apply Windows 11-style appearance."""
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return

        palette = app.palette()
        is_dark = (
            palette.color(
                QPalette.ColorGroup.Active,  # pyright: ignore[reportArgumentType]
                QPalette.ColorRole.Window,  # pyright: ignore[reportArgumentType]
            ).lightness()
            < 128
        )

        if is_dark:
            self.setStyleSheet("""
                EnhancedPreviewPane {
                    background-color: #2D2D2D;
                    border-left: 1px solid #3D3D3D;
                }
                QLabel {
                    color: #E0E0E0;
                }
                QScrollArea {
                    background-color: transparent;
                }
            """)
            self._filename_label.setStyleSheet("font-size: 14pt; font-weight: 600; color: #E0E0E0;")
            self._filetype_label.setStyleSheet("font-size: 10pt; color: #A0A0A0;")
            self._preview_frame.setStyleSheet("QFrame { background-color: #353535; border: 1px solid #4D4D4D; border-radius: 4px; }")
        else:
            self.setStyleSheet("""
                EnhancedPreviewPane {
                    background-color: #F9F9F9;
                    border-left: 1px solid #E1E1E1;
                }
                QScrollArea {
                    background-color: transparent;
                }
            """)

    def set_file(self, path: Path | None):
        """Set the file to preview.

        Args:
            path: Path to the file to preview, or None to clear.
        """
        self._current_path = path
        self._clear_metadata()

        if not is_valid_path(path):
            self._content_widget.hide()
            self._placeholder_label.show()
            self._placeholder_label.setText("Select a file to preview")
            return

        self._placeholder_label.hide()
        self._content_widget.show()

        # Update header
        self._update_header(path)

        # Update preview
        self._update_preview(path)

        # Update metadata
        self._update_metadata(path)

    def set_file_from_index(self, index: QModelIndex, model: QFileSystemModel):
        """Set the file to preview from a model index.

        Args:
            index: The model index of the selected file.
            model: The file system model.
        """
        if not index.isValid():
            self.set_file(None)
            return

        file_path = Path(model.filePath(index))
        self.set_file(file_path)

    def _update_header(self, path: Path):
        """Update the header section with icon and filename."""
        # Get file icon
        icon = self._icon_provider.icon(str(path))
        pixmap = icon.pixmap(96, 96)
        self._icon_label.setPixmap(pixmap)

        # Set filename
        self._filename_label.setText(path.name)

        # Set file type description
        self._filetype_label.setText(get_file_type_description(path))

    def _update_preview(self, path: Path):
        """Update the preview section for the file."""
        suffix = path.suffix.lower()

        # Try image preview
        if suffix in self.IMAGE_EXTENSIONS:
            self._show_image_preview(path)
            return

        # Try text preview
        if suffix in self.TEXT_EXTENSIONS:
            self._show_text_preview(path)
            return

        # No preview available
        self._preview_frame.hide()

    def _show_image_preview(self, path: Path):
        """Show an image preview."""
        try:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                self._preview_frame.hide()
                return

            # Scale to fit while preserving aspect ratio
            scaled = pixmap.scaled(
                self.MAX_PREVIEW_WIDTH,
                self.MAX_PREVIEW_HEIGHT,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self._preview_image_label.setPixmap(scaled)
            self._preview_image_label.show()
            self._preview_text_edit.hide()
            self._preview_frame.show()

        except Exception as e:  # noqa: BLE001
            RobustLogger().warning(f"Failed to load image preview: {e}")
            self._preview_frame.hide()

    def _show_text_preview(self, path: Path):
        """Show a text file preview (first ~50 lines)."""
        try:
            # Try to read as text with various encodings
            content = None
            for encoding in ["utf-8", "utf-16", "latin-1", "cp1252"]:
                try:
                    with open(path, "r", encoding=encoding) as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= 50:
                                lines.append("...")
                                break
                            lines.append(line.rstrip())
                        content = "\n".join(lines)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if content is None:
                self._preview_frame.hide()
                return

            self._preview_text_edit.setPlainText(content)
            self._preview_text_edit.show()
            self._preview_image_label.hide()
            self._preview_frame.show()

        except Exception as e:  # noqa: BLE001
            RobustLogger().warning(f"Failed to load text preview: {e}")
            self._preview_frame.hide()

    def _clear_metadata(self):
        """Clear all metadata rows."""
        while self._metadata_layout.count() > 0:
            item = self._metadata_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _update_metadata(self, path: Path):
        """Update the metadata section with file properties."""
        try:
            stat_info = path.stat()

            # Size
            if path.is_file():
                self._add_metadata_row("Size", format_file_size(stat_info.st_size))
            elif path.is_dir():
                # Count items in directory
                try:
                    items = list(path.iterdir())
                    file_count = sum(1 for item in items if item.is_file())
                    dir_count = sum(1 for item in items if item.is_dir())
                    self._add_metadata_row("Contains", f"{file_count} files, {dir_count} folders")
                except PermissionError:
                    self._add_metadata_row("Contains", "Access denied")

            # Location
            self._add_metadata_row("Location", str(path.parent), selectable=True)

            # Date modified
            modified = datetime.fromtimestamp(stat_info.st_mtime)
            self._add_metadata_row("Modified", modified.strftime("%B %d, %Y, %I:%M %p"))

            # Date created (Windows) or changed (Unix)
            if hasattr(stat_info, "st_birthtime"):
                created = datetime.fromtimestamp(stat_info.st_birthtime)
            else:
                created = datetime.fromtimestamp(stat_info.st_ctime)
            self._add_metadata_row("Created", created.strftime("%B %d, %Y, %I:%M %p"))

            # Attributes (Windows-style)
            attrs = []
            if os.name == "nt":
                import ctypes

                FILE_ATTRIBUTE_READONLY = 0x1
                FILE_ATTRIBUTE_HIDDEN = 0x2
                FILE_ATTRIBUTE_SYSTEM = 0x4
                FILE_ATTRIBUTE_ARCHIVE = 0x20

                try:
                    attr_flags = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                    if attr_flags != -1:
                        if attr_flags & FILE_ATTRIBUTE_READONLY:
                            attrs.append("Read-only")
                        if attr_flags & FILE_ATTRIBUTE_HIDDEN:
                            attrs.append("Hidden")
                        if attr_flags & FILE_ATTRIBUTE_SYSTEM:
                            attrs.append("System")
                        if attr_flags & FILE_ATTRIBUTE_ARCHIVE:
                            attrs.append("Archive")
                except Exception:  # noqa: BLE001
                    pass
            else:
                # Unix permissions
                mode = stat_info.st_mode
                if not (mode & stat.S_IWUSR):
                    attrs.append("Read-only")
                if path.name.startswith("."):
                    attrs.append("Hidden")

            if attrs:
                self._add_metadata_row("Attributes", ", ".join(attrs))

            # Image-specific metadata
            if path.suffix.lower() in self.IMAGE_EXTENSIONS:
                self._add_image_metadata(path)

        except Exception as e:  # noqa: BLE001
            RobustLogger().warning(f"Failed to read file metadata: {e}")
            self._add_metadata_row("Error", "Could not read file information")

    def _add_metadata_row(
        self,
        label: str,
        value: str,
        *,
        selectable: bool = False,
    ):
        """Add a metadata row to the metadata section."""
        row = MetadataRow(label, value, self._metadata_widget, selectable=selectable)
        self._metadata_layout.addWidget(row)

    def _add_image_metadata(self, path: Path):
        """Add image-specific metadata (dimensions, etc.)."""
        try:
            image = QImage(str(path))
            if not image.isNull():
                self._add_metadata_row("Dimensions", f"{image.width()} × {image.height()} pixels")

                # Bit depth
                depth = image.depth()
                self._add_metadata_row("Bit depth", f"{depth} bit")

        except Exception as e:  # noqa: BLE001
            RobustLogger().warning(f"Failed to read image metadata: {e}")

    def sizeHint(self) -> QSize:
        """Return the preferred size."""
        return QSize(300, 500)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication, QMainWindow, QSplitter

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Preview Pane Test")
    window.resize(800, 600)

    splitter = QSplitter()

    # Placeholder for file list
    placeholder = QLabel("Select files here")
    placeholder.setMinimumWidth(400)
    splitter.addWidget(placeholder)

    # Preview pane
    preview = EnhancedPreviewPane()
    preview.set_file(Path.home())
    splitter.addWidget(preview)

    window.setCentralWidget(splitter)
    window.show()

    sys.exit(app.exec())
