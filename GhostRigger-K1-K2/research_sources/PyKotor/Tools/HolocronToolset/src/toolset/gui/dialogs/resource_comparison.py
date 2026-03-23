"""Dialog for quick side-by-side resource comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QDialog

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from pykotor.extract.file import FileResource

# Constants for hex display
ASCII_MIN_PRINTABLE = 32
ASCII_MAX_PRINTABLE = 127


class ResourceComparisonDialog(QDialog):
    """Quick side-by-side comparison dialog for resources."""

    def __init__(
        self,
        parent: QWidget | None,
        resource1: FileResource,
        resource2: FileResource | None = None,
    ):
        super().__init__(parent)
        from toolset.gui.common.localization import trf

        self.setWindowTitle(trf("Compare: {name}.{ext}", name=resource1.resname(), ext=resource1.restype().extension))

        self.resource1 = resource1
        self.resource2 = resource2

        from toolset.uic.qtpy.dialogs.resource_comparison import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Update localized labels
        from toolset.gui.common.localization import translate as tr

        self.ui.leftLabel.setText(tr("<b>Left:</b>"))
        self.ui.rightLabel.setText(tr("<b>Right:</b>"))
        self.ui.closeButton.setText(tr("Close"))

        # Sync scrollbars
        left_vscroll = self.ui.leftText.verticalScrollBar()
        right_vscroll = self.ui.rightText.verticalScrollBar()
        left_hscroll = self.ui.leftText.horizontalScrollBar()
        right_hscroll = self.ui.rightText.horizontalScrollBar()

        if left_vscroll and right_vscroll:
            left_vscroll.valueChanged.connect(right_vscroll.setValue)
            right_vscroll.valueChanged.connect(left_vscroll.setValue)

        if left_hscroll and right_hscroll:
            left_hscroll.valueChanged.connect(right_hscroll.setValue)
            right_hscroll.valueChanged.connect(left_hscroll.setValue)

        # Connect button
        self.ui.closeButton.clicked.connect(lambda: self.accept())

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self._load_resources()

    def _load_resources(self):
        """Load and display resource contents."""
        # Set paths
        self.ui.leftPathLabel.setText(str(self.resource1.filepath()))
        if self.resource2:
            self.ui.rightPathLabel.setText(str(self.resource2.filepath()))
        else:
            from toolset.gui.common.localization import translate as tr

            self.ui.rightPathLabel.setText(tr("[Not selected]"))

        # Load left resource
        try:
            data = self.resource1.data()
            self.ui.leftText.setPlainText(self._format_data(data))
        except Exception as e:  # noqa: BLE001
            self.ui.leftText.setPlainText(f"Error loading resource:\n{e}")

        # Load right resource
        if self.resource2:
            try:
                data = self.resource2.data()
                self.ui.rightText.setPlainText(self._format_data(data))
            except Exception as e:  # noqa: BLE001
                self.ui.rightText.setPlainText(f"Error loading resource:\n{e}")
        else:
            self.ui.rightText.setPlainText("[No resource selected for comparison]")

    def _format_data(self, data: bytes) -> str:
        """Format resource data for display."""
        # Try to decode as text
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:  # noqa: S110
            pass

        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:  # noqa: S110
            pass

        # Fall back to hex view
        hex_lines = []
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if ASCII_MIN_PRINTABLE <= b < ASCII_MAX_PRINTABLE else "." for b in chunk)
            hex_lines.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")

        return "\n".join(hex_lines)
