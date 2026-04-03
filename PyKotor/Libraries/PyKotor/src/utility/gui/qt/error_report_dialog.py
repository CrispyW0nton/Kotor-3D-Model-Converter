from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog

from utility.gui.common.error_report_dialog import ErrorReportDialogBase
from utility.gui.qt.error_report_dialog_ui import Ui_Dialog

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent
    from qtpy.QtWidgets import QWidget

    from utility.gui.common.error_report_dialog import ErrorReportData


class QtErrorReportDialog(QDialog, ErrorReportDialogBase):
    def __init__(
        self,
        parent: QWidget | None = None,
        on_submit: Callable[[ErrorReportData], None] | None = None,
    ):
        super().__init__(parent)
        self._on_submit: Callable[[ErrorReportData], None] | None = on_submit
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint)
        self.ui.sendButton.clicked.connect(self._handle_submit)

    def _handle_submit(self):
        if self._on_submit is not None:
            self._on_submit(self.get_report_data())
        self.accept()

    def closeEvent(self, event: QCloseEvent):  # noqa: N802
        event.accept()

    def get_additional_information(self) -> str:
        return self.ui.additionalText.toPlainText().strip()

    def set_additional_information(self, text: str) -> None:
        self.ui.additionalText.setPlainText(text)

    def get_include_logs(self) -> bool:
        return self.ui.includeLogsCheckbox.isChecked()

    def set_include_logs(self, include: bool) -> None:
        self.ui.includeLogsCheckbox.setChecked(include)

    def get_contact_info(self) -> str:
        return self.ui.contactInput.text().strip()

    def set_contact_info(self, text: str) -> None:
        self.ui.contactInput.setText(text)
