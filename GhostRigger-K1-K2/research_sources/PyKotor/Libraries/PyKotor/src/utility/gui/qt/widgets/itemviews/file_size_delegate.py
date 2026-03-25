"""File size-aware item delegate for QFileSystemModel views.

Provides Windows 11-style rendering with WinDirStat-inspired size coloring:
- Large files (> 100MB) highlighted in red tones
- Medium files (> 10MB) highlighted in orange tones
- Small files in normal text color
- Human-readable size formatting

Also provides enhanced rendering for file items with proper icon sizing,
text truncation with ellipsis, and hover/selection highlighting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from qtpy.QtCore import QAbstractProxyModel, QRect, Qt
from qtpy.QtGui import QColor, QPainter, QPalette, QPen
from qtpy.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QAbstractItemModel, QModelIndex, QSize
    from qtpy.QtGui import QFontMetrics
    from qtpy.QtWidgets import QWidget


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format like Windows Explorer."""
    if size_bytes < 0:
        return ""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_size_color(size_bytes: int, is_dark_mode: bool = False) -> QColor | None:
    """Get a color for the file size based on magnitude.

    Inspired by WinDirStat's visual size awareness.

    Args:
        size_bytes: File size in bytes
        is_dark_mode: Whether the app is in dark mode

    Returns:
        QColor for the size text, or None for default color
    """
    if size_bytes < 0:
        return None

    # Define thresholds
    HUGE_THRESHOLD = 1024 * 1024 * 1024  # 1 GB
    VERY_LARGE_THRESHOLD = 100 * 1024 * 1024  # 100 MB
    LARGE_THRESHOLD = 10 * 1024 * 1024  # 10 MB
    MEDIUM_THRESHOLD = 1024 * 1024  # 1 MB

    if is_dark_mode:
        if size_bytes >= HUGE_THRESHOLD:
            return QColor("#FF6B6B")  # Bright red
        elif size_bytes >= VERY_LARGE_THRESHOLD:
            return QColor("#FF8E72")  # Red-orange
        elif size_bytes >= LARGE_THRESHOLD:
            return QColor("#FFA94D")  # Orange
        elif size_bytes >= MEDIUM_THRESHOLD:
            return QColor("#FFD43B")  # Yellow-orange
        return None  # Default color for small files
    else:
        if size_bytes >= HUGE_THRESHOLD:
            return QColor("#C92A2A")  # Dark red
        elif size_bytes >= VERY_LARGE_THRESHOLD:
            return QColor("#E03131")  # Red
        elif size_bytes >= LARGE_THRESHOLD:
            return QColor("#F76707")  # Orange
        elif size_bytes >= MEDIUM_THRESHOLD:
            return QColor("#E67700")  # Dark orange
        return None  # Default color for small files


def highlight_text_matches(
    painter: QPainter,
    text: str,
    search_text: str,
    rect: QRect,
    font_metrics: QFontMetrics,
    text_color: QColor,
    highlight_bg: QColor,
    highlight_fg: QColor,
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
) -> None:
    """Draw text with highlighted search matches.

    Args:
        painter: QPainter to draw with
        text: The full text to draw
        search_text: Text to highlight (case-insensitive)
        rect: Rectangle to draw in
        font_metrics: Font metrics for text measurement
        text_color: Normal text color
        highlight_bg: Background color for highlighted text
        highlight_fg: Foreground color for highlighted text
        alignment: Text alignment flags
    """
    if not search_text or search_text.lower() not in text.lower():
        # No match, draw normally
        painter.setPen(QPen(text_color))
        painter.drawText(rect, alignment, text)
        return

    # Find all matches (case-insensitive)
    text_lower = text.lower()
    search_lower = search_text.lower()
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        pos = text_lower.find(search_lower, start)
        if pos == -1:
            break
        matches.append((pos, pos + len(search_text)))
        start = pos + 1

    if not matches:
        painter.setPen(QPen(text_color))
        painter.drawText(rect, alignment, text)
        return

    # Calculate starting x position based on alignment
    total_width = font_metrics.horizontalAdvance(text)
    if alignment & Qt.AlignmentFlag.AlignHCenter:
        x = rect.x() + (rect.width() - total_width) // 2
    elif alignment & Qt.AlignmentFlag.AlignRight:
        x = rect.right() - total_width
    else:
        x = rect.x()

    # Calculate y position
    if alignment & Qt.AlignmentFlag.AlignVCenter:
        y = rect.y() + (rect.height() + font_metrics.ascent() - font_metrics.descent()) // 2
    elif alignment & Qt.AlignmentFlag.AlignBottom:
        y = rect.bottom() - font_metrics.descent()
    else:
        y = rect.y() + font_metrics.ascent()

    # Draw text segment by segment
    current_pos = 0
    for match_start, match_end in matches:
        # Draw text before match
        if current_pos < match_start:
            before_text = text[current_pos:match_start]
            painter.setPen(QPen(text_color))
            painter.drawText(x, y, before_text)
            x += font_metrics.horizontalAdvance(before_text)

        # Draw highlighted match
        match_text = text[match_start:match_end]
        match_width = font_metrics.horizontalAdvance(match_text)

        # Draw highlight background
        highlight_rect = QRect(
            x - 1,
            y - font_metrics.ascent(),
            match_width + 2,
            font_metrics.height(),
        )
        painter.fillRect(highlight_rect, highlight_bg)

        # Draw highlighted text
        painter.setPen(QPen(highlight_fg))
        painter.drawText(x, y, match_text)
        x += match_width

        current_pos = match_end

    # Draw remaining text after last match
    if current_pos < len(text):
        after_text = text[current_pos:]
        painter.setPen(QPen(text_color))
        painter.drawText(x, y, after_text)


class FileSizeAwareDelegate(QStyledItemDelegate):
    """A styled item delegate that provides enhanced rendering for file system views.

    Features:
    - WinDirStat-inspired size coloring (large files highlighted)
    - Human-readable size formatting
    - Proper text truncation with ellipsis
    - Windows 11-style hover and selection effects
    - Search text highlighting
    """

    # Column indices in QFileSystemModel
    NAME_COLUMN: ClassVar[int] = 0
    SIZE_COLUMN: ClassVar[int] = 1
    TYPE_COLUMN: ClassVar[int] = 2
    DATE_COLUMN: ClassVar[int] = 3

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._is_dark_mode = self._detect_dark_mode()
        self._search_text: str = ""

    @property
    def search_text(self) -> str:
        """Get the current search text for highlighting."""
        return self._search_text

    @search_text.setter
    def search_text(self, text: str) -> None:
        """Set the search text for highlighting."""
        self._search_text = text

    def _detect_dark_mode(self) -> bool:
        """Detect if the application is using dark mode."""
        qapp = QApplication.instance()
        if not isinstance(qapp, QApplication):
            return False
        palette = qapp.palette()
        window_color = palette.color(
            QPalette.ColorGroup.Active,  # pyright: ignore[reportArgumentType]
            QPalette.ColorRole.Window,  # pyright: ignore[reportArgumentType]
        )
        return window_color.lightness() < 128

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Paint the item with enhanced styling."""
        if not index.isValid():
            super().paint(painter, option, index)
            return

        # Get the model and check if it's a QFileSystemModel
        qmodel: QAbstractItemModel | None = index.model()
        source_model = qmodel

        # Handle proxy models
        while isinstance(source_model, QAbstractProxyModel):
            source_model = source_model.sourceModel()

        if not isinstance(source_model, QFileSystemModel):
            super().paint(painter, option, index)
            return

        column = index.column()

        # Special handling for size column
        if column == self.SIZE_COLUMN:
            self._paint_size_column(painter, option, index, source_model)
            return

        # Default painting for other columns
        super().paint(painter, option, index)

    def _paint_size_column(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
        model: QFileSystemModel,
    ) -> None:
        """Paint the size column with colored text based on file size."""
        painter.save()

        # Get the style
        style = option.widget.style() if option.widget else QApplication.style()

        # Draw background (selection/hover)
        assert style is not None, "Style should not be None"
        style.drawPrimitive(
            QStyle.PrimitiveElement.PE_PanelItemViewItem,
            option,
            painter,
            option.widget,
        )

        # Get size information
        # Map proxy index to source if needed
        source_index: QModelIndex = index
        current_model: QAbstractItemModel | None = index.model()
        while isinstance(current_model, QAbstractProxyModel):
            source_index = current_model.mapToSource(source_index)
            current_model = current_model.sourceModel()

        # Get file info from source model
        file_path = model.filePath(source_index.sibling(source_index.row(), 0))
        file_info = model.fileInfo(source_index.sibling(source_index.row(), 0))

        if file_info.isDir():
            # For directories, show empty or item count
            text = ""
        else:
            size = file_info.size()
            text = format_file_size(size)

            # Get color based on size
            size_color = get_size_color(size, self._is_dark_mode)
            if size_color is not None:
                painter.setPen(QPen(size_color))
            elif option.state & QStyle.StateFlag.State_Selected:
                painter.setPen(
                    option.palette.color(
                        QPalette.ColorGroup.Active,  # pyright: ignore[reportArgumentType]
                        QPalette.ColorRole.HighlightedText,  # pyright: ignore[reportArgumentType]
                    )
                )
            else:
                painter.setPen(
                    option.palette.color(
                        QPalette.ColorGroup.Active,  # pyright: ignore[reportArgumentType]
                        QPalette.ColorRole.Text,  # pyright: ignore[reportArgumentType]
                    )
                )

        # Draw text
        text_rect = option.rect.adjusted(4, 0, -4, 0)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            text,
        )

        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        """Return the size hint for the item."""
        size = super().sizeHint(option, index)
        # Ensure minimum row height for comfortable clicking
        size.setHeight(max(size.height(), 24))
        return size


class Windows11ItemDelegate(QStyledItemDelegate):
    """Item delegate that provides Windows 11 File Explorer-style rendering.

    Features:
    - Rounded selection rectangles
    - Subtle hover effects
    - Smooth transitions (via stylesheet)
    - Proper icon/text spacing
    - File size coloring
    - Search text highlighting
    """

    # Column indices in QFileSystemModel
    NAME_COLUMN: ClassVar[int] = 0
    SIZE_COLUMN: ClassVar[int] = 1
    TYPE_COLUMN: ClassVar[int] = 2
    DATE_COLUMN: ClassVar[int] = 3

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._is_dark_mode = self._detect_dark_mode()
        self._size_delegate = FileSizeAwareDelegate(parent)
        self._search_text: str = ""

    @property
    def search_text(self) -> str:
        """Get the current search text for highlighting."""
        return self._search_text

    @search_text.setter
    def search_text(self, text: str) -> None:
        """Set the search text for highlighting."""
        self._search_text = text
        self._size_delegate.search_text = text

    def _detect_dark_mode(self) -> bool:
        """Detect if the application is using dark mode."""
        qapp = QApplication.instance()
        if not isinstance(qapp, QApplication):
            return False
        palette = qapp.palette()
        window_color = palette.color(
            QPalette.ColorGroup.Active,  # pyright: ignore[reportArgumentType]
            QPalette.ColorRole.Window,  # pyright: ignore[reportArgumentType]
        )
        return window_color.lightness() < 128

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Paint the item with Windows 11-style effects."""
        if not index.isValid():
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Define colors based on theme
        if self._is_dark_mode:
            hover_color = QColor(255, 255, 255, 20)
            selection_color = QColor(0, 102, 204, 180)
            border_color = QColor(0, 102, 204)
        else:
            hover_color = QColor(0, 0, 0, 15)
            selection_color = QColor(0, 102, 204, 40)
            border_color = QColor(0, 102, 204, 100)

        # Draw custom background for hover/selection
        rect = option.rect
        is_selected = option.state & QStyle.StateFlag.State_Selected
        is_hover = option.state & QStyle.StateFlag.State_MouseOver

        if is_selected:
            painter.fillRect(rect, selection_color)
            # Draw subtle border for selection
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 4, 4)
        elif is_hover:
            painter.fillRect(rect, hover_color)

        painter.restore()

        # Delegate to size-aware painting for size column
        column = index.column()
        if column == self.SIZE_COLUMN:
            self._size_delegate._paint_size_column(painter, option, index, self._get_source_model(index))
            return

        # Use default painting for other columns but without the default selection
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.StateFlag.State_Selected  # Remove selection flag to prevent double-drawing
        opt.state &= ~QStyle.StateFlag.State_MouseOver  # Remove hover flag
        super().paint(painter, opt, index)

    def _get_source_model(self, index: QModelIndex) -> QFileSystemModel | None:
        """Get the source QFileSystemModel from potentially proxied index."""
        smodel = index.model()
        while isinstance(smodel, QAbstractProxyModel):
            smodel = smodel.sourceModel()
        return smodel if isinstance(smodel, QFileSystemModel) else None

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        """Return the size hint for the item."""
        size = super().sizeHint(option, index)
        # Ensure minimum row height for comfortable clicking
        size.setHeight(max(size.height(), 26))
        return size


if __name__ == "__main__":
    import sys

    from pathlib import Path

    from qtpy.QtWidgets import QApplication, QMainWindow, QTreeView

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("File Size Delegate Test")
    window.resize(800, 600)

    tree_view = QTreeView()
    model = QFileSystemModel()
    model.setRootPath(str(Path.home()))
    tree_view.setModel(model)
    tree_view.setRootIndex(model.index(str(Path.home())))

    # Apply the delegate
    delegate = Windows11ItemDelegate(tree_view)
    tree_view.setItemDelegate(delegate)

    window.setCentralWidget(tree_view)
    window.show()

    sys.exit(app.exec())
