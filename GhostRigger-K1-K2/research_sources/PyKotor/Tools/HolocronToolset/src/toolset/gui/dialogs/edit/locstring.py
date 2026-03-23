"""Localized string editor dialog: edit StrRef, gender/variant, and TLK integration."""

from __future__ import annotations

import os

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout

from pykotor.common.language import Gender, Language, LocalizedString
from pykotor.extract.file import FileResource
from pykotor.resource.formats.tlk import read_tlk, write_tlk
from pykotor.resource.type import ResourceType
from pykotor.tools.path import CaseAwarePath
from toolset.data.installation import HTInstallation
from toolset.gui.common.localization import translate as tr, trf
from toolset.utils.window import open_resource_editor

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from pykotor.resource.resource_auto import TLK
    from toolset.data.installation import HTInstallation


class _TLKSearchDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        installation: HTInstallation,
        current_stringref: int,
    ):
        super().__init__(parent)
        from toolset.gui.common.localization import translate as tr

        self._installation: HTInstallation = installation
        self.selected_stringref: int | None = None

        self.setWindowTitle(tr("Search TLK Strings"))
        self.setModal(True)
        self.resize(480, 360)

        layout = QVBoxLayout(self)

        controls_layout = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(tr("Search for text in TLK strings (min 2 characters)..."))
        controls_layout.addWidget(self.search_edit)

        self.search_button = QPushButton(tr("Search"), self)
        controls_layout.addWidget(self.search_button)

        layout.addLayout(controls_layout)

        self.results_list = QListWidget(self)
        layout.addWidget(self.results_list)

        self.info_label = QLabel(self)
        self.info_label.setWordWrap(True)
        if current_stringref >= 0:
            current_text = installation.talktable().string(current_stringref)
            self.info_label.setText(tr(f"Current selection: [{current_stringref}] {current_text}"))
        else:
            self.info_label.setText(tr("No current StringRef selected."))
        layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.search_button.clicked.connect(self.perform_search)
        self.search_edit.returnPressed.connect(self.perform_search)
        self.results_list.itemClicked.connect(self._select_item)

    def perform_search(self):
        from toolset.gui.common.localization import translate as tr

        query = self.search_edit.text().strip()
        if len(query) < 2:
            self.info_label.setText(tr("Enter at least 2 characters to search."))
            self.results_list.clear()
            return

        query_lower = query.lower()
        talktable = self._installation.talktable()
        max_results = 100
        result_count = 0

        self.results_list.clear()
        for stringref in range(talktable.size()):
            text = talktable.string(stringref)
            if query_lower not in text.lower():
                continue
            item = QListWidgetItem(f"[{stringref}] {text}")
            item.setData(Qt.ItemDataRole.UserRole, stringref)
            self.results_list.addItem(item)
            result_count += 1
            if result_count >= max_results:
                break

        if result_count == 0:
            self.info_label.setText(tr(f"No results found for '{query}'."))
        elif result_count == max_results:
            self.info_label.setText(tr(f"Found {result_count} results (showing first {max_results})."))
        else:
            self.info_label.setText(tr(f"Found {result_count} results."))

    def _select_item(self, item: QListWidgetItem):
        self.selected_stringref = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class LocalizedStringDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        installation: HTInstallation,
        locstring: LocalizedString,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog  # pyright: ignore[reportArgumentType]
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint & ~Qt.WindowType.WindowContextHelpButtonHint & ~Qt.WindowType.WindowMinMaxButtonsHint
        )

        from toolset.uic.qtpy.dialogs.locstring import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        from toolset.gui.common.localization import translate as trf

        self.setWindowTitle(trf("{language} - {name} - Localized String Editor", language=installation.talktable().language().name.title(), name=installation.name))

        self.ui.stringrefSpin.valueChanged.connect(self.stringref_changed)
        self.ui.stringrefNewButton.clicked.connect(self.new_tlk_string)
        self.ui.stringrefNoneButton.clicked.connect(self.no_tlk_string)
        self.ui.stringrefSearchButton.clicked.connect(self.open_search_dialog)
        self.ui.stringrefOpenTLKButton.clicked.connect(self.open_in_tlk_editor)
        self.ui.maleRadio.clicked.connect(self.substring_changed)
        self.ui.femaleRadio.clicked.connect(self.substring_changed)
        self.ui.languageSelect.currentIndexChanged.connect(self.substring_changed)
        self.ui.stringEdit.textChanged.connect(self.string_edited)

        self._installation: HTInstallation = installation
        self.locstring: LocalizedString = LocalizedString.from_dict(locstring.to_dict())  # Deepcopy the object, we don't trust the `deepcopy` function though.
        self.ui.stringrefSpin.setValue(locstring.stringref)

    def accept(self):
        if self.locstring.stringref != -1:
            tlk_path: CaseAwarePath = CaseAwarePath(self._installation.path(), "dialog.tlk")
            tlk: TLK = read_tlk(tlk_path)
            if len(tlk) <= self.locstring.stringref:
                tlk.resize(self.locstring.stringref + 1)
            tlk[self.locstring.stringref].text = self.ui.stringEdit.toPlainText()
            write_tlk(tlk, tlk_path)
        super().accept()

    def reject(self):
        super().reject()

    def stringref_changed(
        self,
        stringref: int,
    ):
        self.ui.substringFrame.setVisible(stringref == -1)
        self.ui.stringrefOpenTLKButton.setEnabled(stringref >= 0)
        self.locstring.stringref = stringref

        if stringref == -1:
            self._update_text()
        else:
            self.ui.stringEdit.setPlainText(self._installation.talktable().string(stringref))

    def new_tlk_string(self):
        self.ui.stringrefSpin.setValue(self._installation.talktable().size())

    def no_tlk_string(self):
        self.ui.stringrefSpin.setValue(-1)

    def open_search_dialog(self):
        dialog = _TLKSearchDialog(self, self._installation, self.ui.stringrefSpin.value())
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted and dialog.selected_stringref is not None:
            self.ui.stringrefSpin.setValue(dialog.selected_stringref)

    def open_in_tlk_editor(self):
        stringref: int = self.ui.stringrefSpin.value()
        if stringref < 0:
            return

        tlk_path = self._installation.path() / "dialog.tlk"
        if not tlk_path.exists() or not tlk_path.is_file():
            QMessageBox(
                QMessageBox.Icon.Information,
                tr("dialog.tlk not found"),
                trf("Could not open the TLK editor because '{path}' was not found.", path=str(tlk_path)),
                QMessageBox.StandardButton.Ok,
                self,
            ).exec()
            return

        resource = FileResource("dialog", ResourceType.TLK, os.path.getsize(tlk_path), 0x0, tlk_path)  # noqa: PTH202
        _filepath, editor = open_resource_editor(resource, self._installation, self)
        from toolset.gui.editors.tlk import TLKEditor

        if editor is not None and isinstance(editor, TLKEditor):
            editor.goto_strref(stringref)

    def substring_changed(self):
        self._update_text()

    def _update_text(self):
        language: Language = Language(self.ui.languageSelect.currentIndex())
        gender: Gender = Gender(int(self.ui.femaleRadio.isChecked()))
        text: str = self.locstring.get(language, gender) or ""
        self.ui.stringEdit.setPlainText(text)

    def string_edited(self):
        if self.locstring.stringref == -1:
            language: Language = Language(self.ui.languageSelect.currentIndex())
            gender: Gender = Gender(int(self.ui.femaleRadio.isChecked()))
            self.locstring.set_data(language, gender, self.ui.stringEdit.toPlainText())
