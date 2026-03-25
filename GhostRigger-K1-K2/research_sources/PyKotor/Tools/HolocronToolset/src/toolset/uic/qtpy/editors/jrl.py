# Form implementation generated from reading ui file '..\ui\editors\jrl.ui'
# Manually maintained to stay in sync with the .ui file.
# Re-run convertui.py (or pyuic6) to regenerate from scratch if needed.

from qtpy import QtCore, QtGui, QtWidgets

_PALETTE_STYLESHEET = """
QTreeView {
    background-color: palette(base);
    alternate-background-color: palette(alternate-base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
    show-decoration-selected: 1;
}
QTreeView::item {
    padding: 3px 4px;
    border-radius: 2px;
}
QTreeView::item:hover {
    background-color: palette(midlight);
}
QTreeView::branch {
    background: palette(base);
}
QSplitter::handle {
    background-color: palette(mid);
}
QSplitter::handle:vertical {
    height: 4px;
}
QGroupBox {
    border: 1px solid palette(mid);
    border-radius: 4px;
    margin-top: 8px;
    padding: 4px 2px 2px 2px;
    font-weight: bold;
    color: palette(window-text);
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    left: 8px;
}
QLineEdit {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 2px 4px;
}
QLineEdit:focus {
    border: 1px solid palette(highlight);
}
QSpinBox, QDoubleSpinBox {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 1px 3px;
}
QComboBox {
    background-color: palette(button);
    color: palette(button-text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 1px 6px;
}
QComboBox:hover {
    border: 1px solid palette(highlight);
}
QComboBox::drop-down {
    border: none;
}
QCheckBox {
    color: palette(window-text);
    spacing: 5px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid palette(mid);
    border-radius: 2px;
    background-color: palette(base);
}
QCheckBox::indicator:checked {
    background-color: palette(highlight);
    border-color: palette(highlight);
}
QLabel {
    color: palette(window-text);
}
QPlainTextEdit {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 2px;
}
QPlainTextEdit:focus {
    border: 1px solid palette(highlight);
}
QPushButton {
    background-color: palette(button);
    color: palette(button-text);
    border: 1px solid palette(mid);
    border-radius: 3px;
    padding: 2px 8px;
}
QPushButton:hover {
    background-color: palette(midlight);
}
QPushButton:pressed {
    background-color: palette(dark);
}
"""


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 570)
        MainWindow.setMinimumSize(QtCore.QSize(600, 450))
        MainWindow.setStyleSheet(_PALETTE_STYLESHEET)

        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # Main vertical layout
        self.verticalLayout_main = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout_main.setSpacing(4)
        self.verticalLayout_main.setContentsMargins(4, 4, 4, 4)
        self.verticalLayout_main.setObjectName("verticalLayout_main")

        # ── Filter bar ────────────────────────────────────────────
        self.filterBarLayout = QtWidgets.QHBoxLayout()
        self.filterBarLayout.setSpacing(4)
        self.filterBarLayout.setObjectName("filterBarLayout")

        self.filterLabel = QtWidgets.QLabel(parent=self.centralwidget)
        self.filterLabel.setText("Filter:")
        self.filterLabel.setObjectName("filterLabel")
        self.filterBarLayout.addWidget(self.filterLabel)

        self.filterEdit = QtWidgets.QLineEdit(parent=self.centralwidget)
        self.filterEdit.setPlaceholderText("Search quests and entries...")
        self.filterEdit.setClearButtonEnabled(True)
        self.filterEdit.setToolTip("Type to filter quests and entries. Right-click for filter options.")
        self.filterEdit.setObjectName("filterEdit")
        self.filterBarLayout.addWidget(self.filterEdit)

        self.filterClearBtn = QtWidgets.QPushButton(parent=self.centralwidget)
        self.filterClearBtn.setText("X")
        self.filterClearBtn.setToolTip("Clear filter")
        self.filterClearBtn.setMaximumWidth(28)
        self.filterClearBtn.setFlat(True)
        self.filterClearBtn.setObjectName("filterClearBtn")
        self.filterBarLayout.addWidget(self.filterClearBtn)

        self.verticalLayout_main.addLayout(self.filterBarLayout)

        # ── Splitter ──────────────────────────────────────────────
        self.splitter = QtWidgets.QSplitter(parent=self.centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Orientation.Vertical)
        self.splitter.setObjectName("splitter")

        # Journal tree
        self.journalTree = RobustTreeView(parent=self.splitter)
        self.journalTree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.journalTree.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.journalTree.setAlternatingRowColors(True)
        self.journalTree.setHeaderHidden(True)
        self.journalTree.setObjectName("journalTree")

        # Stacked pages
        self.questPages = QtWidgets.QStackedWidget(parent=self.splitter)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Minimum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.questPages.sizePolicy().hasHeightForWidth())
        self.questPages.setSizePolicy(sizePolicy)
        self.questPages.setObjectName("questPages")

        # ── Category page ─────────────────────────────────────────
        self.categoryPage = QtWidgets.QWidget()
        self.categoryPage.setObjectName("categoryPage")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.categoryPage)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")

        # Quest Properties group box
        self.categoryPropsGroup = QtWidgets.QGroupBox(parent=self.categoryPage)
        self.categoryPropsGroup.setTitle("Quest Properties")
        self.categoryPropsGroup.setObjectName("categoryPropsGroup")
        self.formLayout = QtWidgets.QFormLayout(self.categoryPropsGroup)
        self.formLayout.setObjectName("formLayout")

        self.label = QtWidgets.QLabel(parent=self.categoryPropsGroup)
        self.label.setObjectName("label")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label)

        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.categoryNameEdit = LocalizedStringLineEdit(parent=self.categoryPropsGroup)
        self.categoryNameEdit.setMinimumSize(QtCore.QSize(0, 23))
        self.categoryNameEdit.setObjectName("categoryNameEdit")
        self.horizontalLayout.addWidget(self.categoryNameEdit)
        self.formLayout.setLayout(0, QtWidgets.QFormLayout.ItemRole.FieldRole, self.horizontalLayout)

        self.label_5 = QtWidgets.QLabel(parent=self.categoryPropsGroup)
        self.label_5.setObjectName("label_5")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_5)

        self.categoryTag = QtWidgets.QLineEdit(parent=self.categoryPropsGroup)
        self.categoryTag.setObjectName("categoryTag")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.ItemRole.FieldRole, self.categoryTag)

        self.label_3 = QtWidgets.QLabel(parent=self.categoryPropsGroup)
        self.label_3.setObjectName("label_3")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_3)

        self.categoryPlotSelect = ComboBox2DA(parent=self.categoryPropsGroup)
        self.categoryPlotSelect.setObjectName("categoryPlotSelect")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.ItemRole.FieldRole, self.categoryPlotSelect)

        self.label_2 = QtWidgets.QLabel(parent=self.categoryPropsGroup)
        self.label_2.setObjectName("label_2")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_2)

        self.categoryPlanetSelect = ComboBox2DA(parent=self.categoryPropsGroup)
        self.categoryPlanetSelect.setObjectName("categoryPlanetSelect")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.ItemRole.FieldRole, self.categoryPlanetSelect)

        self.label_4 = QtWidgets.QLabel(parent=self.categoryPropsGroup)
        self.label_4.setObjectName("label_4")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_4)

        self.categoryPrioritySelect = QtWidgets.QComboBox(parent=self.categoryPropsGroup)
        self.categoryPrioritySelect.setObjectName("categoryPrioritySelect")
        self.categoryPrioritySelect.addItem("")
        self.categoryPrioritySelect.addItem("")
        self.categoryPrioritySelect.addItem("")
        self.categoryPrioritySelect.addItem("")
        self.categoryPrioritySelect.addItem("")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.ItemRole.FieldRole, self.categoryPrioritySelect)

        self.horizontalLayout_2.addWidget(self.categoryPropsGroup)

        # Notes group box
        self.categoryNotesGroup = QtWidgets.QGroupBox(parent=self.categoryPage)
        self.categoryNotesGroup.setTitle("Notes")
        self.categoryNotesGroup.setObjectName("categoryNotesGroup")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.categoryNotesGroup)
        self.verticalLayout_2.setObjectName("verticalLayout_2")

        self.categoryCommentEdit = HTPlainTextEdit(parent=self.categoryNotesGroup)
        self.categoryCommentEdit.setObjectName("categoryCommentEdit")
        self.verticalLayout_2.addWidget(self.categoryCommentEdit)

        self.horizontalLayout_2.addWidget(self.categoryNotesGroup)
        self.horizontalLayout_2.setStretch(0, 1)
        self.horizontalLayout_2.setStretch(1, 2)

        self.questPages.addWidget(self.categoryPage)

        # ── Entry page ────────────────────────────────────────────
        self.entryPage = QtWidgets.QWidget()
        self.entryPage.setObjectName("entryPage")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout(self.entryPage)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")

        # Entry Properties group box
        self.entryPropsGroup = QtWidgets.QGroupBox(parent=self.entryPage)
        self.entryPropsGroup.setTitle("Entry Properties")
        self.entryPropsGroup.setObjectName("entryPropsGroup")
        self.formLayout_2 = QtWidgets.QFormLayout(self.entryPropsGroup)
        self.formLayout_2.setObjectName("formLayout_2")

        self.label_8 = QtWidgets.QLabel(parent=self.entryPropsGroup)
        self.label_8.setObjectName("label_8")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_8)

        self.entryIdSpin = QtWidgets.QSpinBox(parent=self.entryPropsGroup)
        self.entryIdSpin.setMinimumSize(QtCore.QSize(80, 0))
        self.entryIdSpin.setMinimum(0)
        self.entryIdSpin.setMaximum(2147483647)
        self.entryIdSpin.setObjectName("entryIdSpin")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.ItemRole.FieldRole, self.entryIdSpin)

        self.label_9 = QtWidgets.QLabel(parent=self.entryPropsGroup)
        self.label_9.setObjectName("label_9")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_9)

        self.entryXpSpin = QtWidgets.QDoubleSpinBox(parent=self.entryPropsGroup)
        self.entryXpSpin.setMinimum(0.0)
        self.entryXpSpin.setMaximum(1000.0)
        self.entryXpSpin.setObjectName("entryXpSpin")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.ItemRole.FieldRole, self.entryXpSpin)

        self.label_7 = QtWidgets.QLabel(parent=self.entryPropsGroup)
        self.label_7.setObjectName("label_7")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.ItemRole.LabelRole, self.label_7)

        self.entryEndCheck = QtWidgets.QCheckBox(parent=self.entryPropsGroup)
        self.entryEndCheck.setText("")
        self.entryEndCheck.setObjectName("entryEndCheck")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.ItemRole.FieldRole, self.entryEndCheck)

        self.horizontalLayout_3.addWidget(self.entryPropsGroup)

        # Entry Text group box
        self.entryTextGroup = QtWidgets.QGroupBox(parent=self.entryPage)
        self.entryTextGroup.setTitle("Entry Text")
        self.entryTextGroup.setObjectName("entryTextGroup")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.entryTextGroup)
        self.verticalLayout.setObjectName("verticalLayout")

        self.entryTextEdit = HTPlainTextEdit(parent=self.entryTextGroup)
        self.entryTextEdit.setReadOnly(True)
        self.entryTextEdit.setObjectName("entryTextEdit")
        self.verticalLayout.addWidget(self.entryTextEdit)

        self.horizontalLayout_3.addWidget(self.entryTextGroup)

        self.questPages.addWidget(self.entryPage)

        self.verticalLayout_main.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.centralwidget)

        # ── Menu bar ──────────────────────────────────────────────
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 22))
        self.menubar.setObjectName("menubar")
        self.menuNew = QtWidgets.QMenu(parent=self.menubar)
        self.menuNew.setObjectName("menuNew")
        MainWindow.setMenuBar(self.menubar)

        self.actionOpen = QtGui.QAction(parent=MainWindow)
        self.actionOpen.setObjectName("actionOpen")
        self.actionSave = QtGui.QAction(parent=MainWindow)
        self.actionSave.setObjectName("actionSave")
        self.actionSave_As = QtGui.QAction(parent=MainWindow)
        self.actionSave_As.setObjectName("actionSave_As")
        self.actionNew = QtGui.QAction(parent=MainWindow)
        self.actionNew.setObjectName("actionNew")
        self.actionRevert = QtGui.QAction(parent=MainWindow)
        self.actionRevert.setObjectName("actionRevert")
        self.actionExit = QtGui.QAction(parent=MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.actionSettings = QtGui.QAction(parent=MainWindow)
        self.actionSettings.setObjectName("actionSettings")

        self.menuNew.addAction(self.actionNew)
        self.menuNew.addAction(self.actionOpen)
        self.menuNew.addAction(self.actionSave)
        self.menuNew.addAction(self.actionSave_As)
        self.menuNew.addAction(self.actionRevert)
        self.menuNew.addSeparator()
        self.menuNew.addAction(self.actionSettings)
        self.menuNew.addSeparator()
        self.menuNew.addAction(self.actionExit)
        self.menubar.addAction(self.menuNew.menuAction())

        self.retranslateUi(MainWindow)
        self.questPages.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Journal Editor"))
        self.filterLabel.setText(_translate("MainWindow", "Filter:"))
        self.filterEdit.setPlaceholderText(_translate("MainWindow", "Search quests and entries..."))
        self.filterClearBtn.setText(_translate("MainWindow", "X"))
        self.label.setText(_translate("MainWindow", "Name:"))
        self.categoryPropsGroup.setTitle(_translate("MainWindow", "Quest Properties"))
        self.categoryNotesGroup.setTitle(_translate("MainWindow", "Notes"))
        self.categoryNameEdit.setToolTip(_translate("MainWindow", "Name (GFF: Name): Display title of the quest. Localized string."))
        self.label_5.setText(_translate("MainWindow", "Tag:"))
        self.categoryTag.setToolTip(_translate("MainWindow", "Tag (GFF: Tag): Unique identifier. Scripts use AddJournalQuestEntry(\"Tag\", ID). Right-click to find all references."))
        self.label_3.setText(_translate("MainWindow", "Plot Index:"))
        self.categoryPlotSelect.setToolTip(_translate("MainWindow", "PlotIndex (GFF: PlotIndex): Row index into plot.2da. INT32."))
        self.label_2.setText(_translate("MainWindow", "Planet ID:"))
        self.categoryPlanetSelect.setToolTip(_translate("MainWindow", "PlanetID (GFF: PlanetID): Row index into planet 2DA. Toolset metadata. INT32."))
        self.label_4.setText(_translate("MainWindow", "Priority:"))
        self.categoryPrioritySelect.setToolTip(_translate("MainWindow", "Priority (GFF: Priority): Quest sort order. 0=Highest, 4=Lowest. UINT32."))
        self.categoryPrioritySelect.setItemText(0, _translate("MainWindow", "Highest"))
        self.categoryPrioritySelect.setItemText(1, _translate("MainWindow", "High"))
        self.categoryPrioritySelect.setItemText(2, _translate("MainWindow", "Medium"))
        self.categoryPrioritySelect.setItemText(3, _translate("MainWindow", "Low"))
        self.categoryPrioritySelect.setItemText(4, _translate("MainWindow", "Lowest"))
        self.categoryCommentEdit.setToolTip(_translate("MainWindow", "Comment (GFF: Comment): Developer notes only. The game ignores this."))
        self.entryPropsGroup.setTitle(_translate("MainWindow", "Entry Properties"))
        self.entryTextGroup.setTitle(_translate("MainWindow", "Entry Text"))
        self.label_8.setText(_translate("MainWindow", "ID:"))
        self.entryIdSpin.setToolTip(_translate("MainWindow", "ID (GFF: ID): State identifier. AddJournalQuestEntry(\"Tag\", ID). UINT32."))
        self.label_9.setText(_translate("MainWindow", "XP Percentage:"))
        self.entryXpSpin.setToolTip(_translate("MainWindow", "XP_Percentage (GFF: XP_Percentage): XP reward multiplier. Float."))
        self.label_7.setText(_translate("MainWindow", "End:"))
        self.entryEndCheck.setToolTip(_translate("MainWindow", "End (GFF: End): Completes the quest when reached. BYTE 0/1."))
        self.label_10 = QtWidgets.QLabel()  # kept for compat; title now in group box
        self.entryTextEdit.setToolTip(_translate("MainWindow", "Text (GFF: Text): Journal text for this entry. Localized string. Double-click to edit."))
        self.menuNew.setTitle(_translate("MainWindow", "File"))
        self.actionOpen.setText(_translate("MainWindow", "Open"))
        self.actionSave.setText(_translate("MainWindow", "Save"))
        self.actionSave_As.setText(_translate("MainWindow", "Save As"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionRevert.setText(_translate("MainWindow", "Revert"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))
        self.actionSettings.setText(_translate("MainWindow", "Settings..."))
        self.actionSettings.setToolTip(_translate("MainWindow", "Configure Journal Editor filter and jump-to-resource behaviour"))


from toolset.gui.widgets.edit.combobox_2da import ComboBox2DA
from toolset.gui.widgets.edit.locstring import LocalizedStringLineEdit
from toolset.gui.widgets.edit.plaintext import HTPlainTextEdit
from utility.gui.qt.widgets.itemviews.treeview import RobustTreeView
