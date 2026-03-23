"""Dialog for configuring reference search options.

This dialog allows users to configure search parameters for finding references
to scripts, tags, resrefs, conversations, and other values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import qtpy

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QCheckBox, QDialog

from toolset.utils.reference_search_config import get_all_searchable_file_types

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class ReferenceSearchOptions(QDialog):
    """Dialog for configuring reference search options."""

    def __init__(
        self,
        parent: QWidget | None,
        default_partial_match: bool = False,
        default_case_sensitive: bool = False,
        default_file_pattern: str = "",
        default_file_types: set[str] | None = None,
    ):
        """Initialize the reference search options dialog.

        Args:
        ----
            parent: Parent widget
            default_partial_match: Default value for partial match checkbox
            default_case_sensitive: Default value for case sensitive checkbox
            default_file_pattern: Default file pattern text
            default_file_types: Default set of file types to search
        """
        super().__init__(parent)
        if qtpy.QT5:
            win_type = Qt.WindowType(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.WindowContextHelpButtonHint)
        else:
            win_type = Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.WindowContextHelpButtonHint

        self.setWindowFlags(win_type)

        from toolset.uic.qtpy.dialogs.reference_search_options import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Set default values
        self.ui.partialMatchCheck.setChecked(default_partial_match)
        self.ui.caseSensitiveCheck.setChecked(default_case_sensitive)
        self.ui.filePatternEdit.setText(default_file_pattern)

        # Create checkboxes for each searchable file type
        self.file_type_checks: dict[str, QCheckBox] = {}
        all_types = sorted(get_all_searchable_file_types())
        for file_type in all_types:
            check = QCheckBox(file_type)
            if default_file_types is None or file_type in default_file_types:
                check.setChecked(True)
            self.file_type_checks[file_type] = check
            self.ui.fileTypesContainerLayout.addWidget(check)

        # Connect button box signals
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)

    def get_partial_match(self) -> bool:
        """Get the partial match setting."""
        return self.ui.partialMatchCheck.isChecked()

    def get_case_sensitive(self) -> bool:
        """Get the case sensitive setting."""
        return self.ui.caseSensitiveCheck.isChecked()

    def get_file_pattern(self) -> str | None:
        """Get the file pattern, or None if empty."""
        pattern = self.ui.filePatternEdit.text().strip()
        return pattern if pattern else None

    def get_file_types(self) -> set[str] | None:
        """Get the selected file types, or None if all are selected."""
        selected_types = {ftype for ftype, check in self.file_type_checks.items() if check.isChecked()}
        all_types = set(self.file_type_checks.keys())
        # Return None if all types are selected (means "search all")
        return None if selected_types == all_types else selected_types
