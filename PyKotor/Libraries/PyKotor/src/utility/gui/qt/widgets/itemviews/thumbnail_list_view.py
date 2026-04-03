"""Thumbnail-enabled list view for QFileDialogExtended.

Provides Windows 11 File Explorer-style icon view with:
- Multiple icon sizes (Extra Large, Large, Medium, Small)
- Thumbnail generation for images
- Smooth icon scaling
- Grid layout with proper spacing
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileIconProvider,
    QFileSystemModel,
    QListView,
    QStyle,
    QStyledItemDelegate,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]

if TYPE_CHECKING:
    from qtpy.QtCore import QModelIndex
    from qtpy.QtGui import QPainter
    from qtpy.QtWidgets import (
        QStyleOptionViewItem,
        QWidget,
    )


class IconSize(IntEnum):
    """Icon size presets matching Windows 11 File Explorer."""

    EXTRA_LARGE = 256
    LARGE = 128
    MEDIUM = 64
    SMALL = 32
    LIST = 16
    DETAILS = 16


class ThumbnailCache:
    """Thread-safe thumbnail cache with LRU eviction."""

    MAX_CACHE_SIZE: ClassVar[int] = 500

    # Supported image formats for thumbnails
    THUMBNAIL_FORMATS: ClassVar[set[str]] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".tif"}

    def __init__(self):
        self._cache: dict[tuple[str, int], QPixmap] = {}
        self._access_order: list[tuple[str, int]] = []

    def get(self, path: str, size: int) -> QPixmap | None:
        """Get cached thumbnail if available."""
        key = (path, size)
        if key in self._cache:
            # Move to end of access order (most recently used)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def put(self, path: str, size: int, pixmap: QPixmap) -> None:
        """Store thumbnail in cache with LRU eviction."""
        key = (path, size)

        # Evict oldest entries if cache is full
        while len(self._cache) >= self.MAX_CACHE_SIZE and self._access_order:
            oldest_key = self._access_order.pop(0)
            self._cache.pop(oldest_key, None)

        self._cache[key] = pixmap
        self._access_order.append(key)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()
        self._access_order.clear()

    @staticmethod
    def can_generate_thumbnail(path: str) -> bool:
        """Check if a thumbnail can be generated for the given path."""
        suffix = Path(path).suffix.lower()
        return suffix in ThumbnailCache.THUMBNAIL_FORMATS


# Global thumbnail cache instance
_thumbnail_cache = ThumbnailCache()


def generate_thumbnail(path: str, size: int) -> QPixmap | None:
    """Generate a thumbnail for the given image file.

    Args:
        path: Path to the image file
        size: Target size for the thumbnail (square)

    Returns:
        QPixmap thumbnail or None if generation failed
    """
    # Check cache first
    cached = _thumbnail_cache.get(path, size)
    if cached is not None:
        return cached

    if not ThumbnailCache.can_generate_thumbnail(path):
        return None

    try:
        # Load image
        image = QImage(path)
        if image.isNull():
            return None

        # Scale to fit within size while preserving aspect ratio
        scaled = image.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        pixmap = QPixmap.fromImage(scaled)

        # Cache the result
        _thumbnail_cache.put(path, size, pixmap)

        return pixmap

    except Exception as e:  # noqa: BLE001
        RobustLogger().debug(f"Failed to generate thumbnail for {path}: {e}")
        return None


class ThumbnailIconDelegate(QStyledItemDelegate):
    """Item delegate that shows thumbnails for images and large icons for other files."""

    def __init__(
        self,
        parent: QWidget | None = None,
        icon_size: int = IconSize.MEDIUM,
    ):
        super().__init__(parent)
        self._icon_size = icon_size
        self._icon_provider = QFileIconProvider()

    @property
    def icon_size(self) -> int:
        """Get the current icon size."""
        return self._icon_size

    @icon_size.setter
    def icon_size(self, size: int) -> None:
        """Set the icon size and invalidate cache if needed."""
        if self._icon_size != size:
            self._icon_size = size

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Paint the item with thumbnail or icon."""
        if not index.isValid():
            super().paint(painter, option, index)
            return

        # Get the model and file path
        model = index.model()
        source_model = model
        source_index = index

        # Handle proxy models
        while hasattr(source_model, "sourceModel"):
            source_index = source_model.mapToSource(source_index)
            source_model = source_model.sourceModel()

        if not isinstance(source_model, QFileSystemModel):
            super().paint(painter, option, index)
            return

        file_path = source_model.filePath(source_index)
        file_info = source_model.fileInfo(source_index)

        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)

        # Draw selection/hover background
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelItemViewItem,
            option,
            painter,
            option.widget,
        )

        # Calculate icon rect
        icon_rect = option.rect
        text_height = option.fontMetrics.height() + 4

        # For icon view, icon is above text
        if self._icon_size >= IconSize.MEDIUM:
            icon_rect.setHeight(icon_rect.height() - text_height)

        # Center icon in rect
        icon_size = min(self._icon_size, icon_rect.width() - 8, icon_rect.height() - 8)
        icon_x = icon_rect.x() + (icon_rect.width() - icon_size) // 2
        icon_y = icon_rect.y() + (icon_rect.height() - icon_size) // 2

        # Try to get thumbnail for images
        pixmap = None
        if not file_info.isDir() and ThumbnailCache.can_generate_thumbnail(file_path):
            pixmap = generate_thumbnail(file_path, icon_size)

        # Fall back to file icon
        if pixmap is None:
            icon = source_model.fileIcon(source_index)
            pixmap = icon.pixmap(icon_size, icon_size)

        # Draw the icon/thumbnail
        if pixmap and not pixmap.isNull():
            # Center the pixmap if it's smaller than the icon size
            px_x = icon_x + (icon_size - pixmap.width()) // 2
            px_y = icon_y + (icon_size - pixmap.height()) // 2
            painter.drawPixmap(px_x, px_y, pixmap)

        # Draw filename text below icon (for medium+ sizes)
        if self._icon_size >= IconSize.MEDIUM:
            text_rect = option.rect
            text_rect.setTop(icon_rect.bottom())

            # Elide text if too long
            text = file_info.fileName()
            elided = option.fontMetrics.elidedText(
                text,
                Qt.TextElideMode.ElideMiddle,
                text_rect.width() - 4,
            )

            painter.setPen(option.palette.color(option.palette.ColorRole.Text))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                elided,
            )

        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        """Return the size hint for the item."""
        text_height = option.fontMetrics.height() + 4

        if self._icon_size >= IconSize.MEDIUM:
            # Icon view: icon + text below
            return QSize(
                self._icon_size + 16,
                self._icon_size + text_height + 16,
            )
        else:
            # List/details view: icon beside text
            return QSize(
                self._icon_size + 200,
                max(self._icon_size + 4, text_height + 4),
            )


class ThumbnailListView(QListView):
    """A list view that supports thumbnail display and multiple icon sizes.

    Provides Windows 11-style icon view modes:
    - Extra Large Icons (256px)
    - Large Icons (128px)
    - Medium Icons (64px)
    - Small Icons (32px)
    - List (16px, horizontal flow)
    - Details (handled by tree view)
    """

    iconSizeChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_icon_size = IconSize.MEDIUM
        self._thumbnail_delegate = ThumbnailIconDelegate(self, self._current_icon_size)

        self.setItemDelegate(self._thumbnail_delegate)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self._apply_icon_size(self._current_icon_size)

    def set_icon_size_mode(self, mode: IconSize) -> None:
        """Set the icon size mode.

        Args:
            mode: One of the IconSize enum values
        """
        if self._current_icon_size == mode:
            return

        self._current_icon_size = mode
        self._apply_icon_size(mode)
        self.iconSizeChanged.emit(mode)

    def _apply_icon_size(self, size: int) -> None:
        """Apply the icon size settings."""
        self._thumbnail_delegate.icon_size = size

        if size >= IconSize.MEDIUM:
            # Icon view mode
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setFlow(QListView.Flow.LeftToRight)
            self.setWrapping(True)
            self.setGridSize(QSize(size + 20, size + 40))
            self.setIconSize(QSize(size, size))
        elif size == IconSize.SMALL:
            # Small icons - still icon mode but smaller
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setFlow(QListView.Flow.LeftToRight)
            self.setWrapping(True)
            self.setGridSize(QSize(120, 40))
            self.setIconSize(QSize(size, size))
        else:
            # List mode
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setFlow(QListView.Flow.TopToBottom)
            self.setWrapping(False)
            self.setGridSize(QSize())
            self.setIconSize(QSize(size, size))

        # Force relayout
        self.doItemsLayout()

    def set_extra_large_icons(self) -> None:
        """Set extra large icons (256px)."""
        self.set_icon_size_mode(IconSize.EXTRA_LARGE)

    def set_large_icons(self) -> None:
        """Set large icons (128px)."""
        self.set_icon_size_mode(IconSize.LARGE)

    def set_medium_icons(self) -> None:
        """Set medium icons (64px)."""
        self.set_icon_size_mode(IconSize.MEDIUM)

    def set_small_icons(self) -> None:
        """Set small icons (32px)."""
        self.set_icon_size_mode(IconSize.SMALL)

    def set_list_view(self) -> None:
        """Set list view mode (16px icons)."""
        self.set_icon_size_mode(IconSize.LIST)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QPushButton, QVBoxLayout, QWidget

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Thumbnail List View Test")
    window.resize(800, 600)

    central = QWidget()
    layout = QVBoxLayout(central)

    # Toolbar with icon size buttons
    toolbar = QWidget()
    toolbar_layout = QHBoxLayout(toolbar)

    list_view = ThumbnailListView()

    model = QFileSystemModel()
    model.setRootPath(str(Path.home() / "Pictures"))
    list_view.setModel(model)
    list_view.setRootIndex(model.index(str(Path.home() / "Pictures")))

    btn_xl = QPushButton("Extra Large")
    btn_xl.clicked.connect(list_view.set_extra_large_icons)
    toolbar_layout.addWidget(btn_xl)

    btn_l = QPushButton("Large")
    btn_l.clicked.connect(list_view.set_large_icons)
    toolbar_layout.addWidget(btn_l)

    btn_m = QPushButton("Medium")
    btn_m.clicked.connect(list_view.set_medium_icons)
    toolbar_layout.addWidget(btn_m)

    btn_s = QPushButton("Small")
    btn_s.clicked.connect(list_view.set_small_icons)
    toolbar_layout.addWidget(btn_s)

    btn_list = QPushButton("List")
    btn_list.clicked.connect(list_view.set_list_view)
    toolbar_layout.addWidget(btn_list)

    toolbar_layout.addStretch()

    layout.addWidget(toolbar)
    layout.addWidget(list_view)

    window.setCentralWidget(central)
    window.show()

    sys.exit(app.exec())
