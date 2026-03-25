"""UTC (creature) editor: stats, inventory, scripts, and portrait for creature blueprints."""

from __future__ import annotations

import os

from copy import deepcopy
from typing import TYPE_CHECKING, Sequence

from qtpy.QtCore import QSettings, Qt
from qtpy.QtGui import QImage, QPixmap, QTransform
from qtpy.QtWidgets import QApplication, QListWidgetItem, QMenu, QMessageBox

from loggerplus import RobustLogger
from pykotor.common.language import Gender, Language
from pykotor.common.misc import Game, ResRef
from pykotor.common.module import Module
from pykotor.extract.capsule import Capsule
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.ltr import read_ltr
from pykotor.resource.formats.twoda.twoda_data import TwoDA
from pykotor.resource.generics.dlg import DLG, bytes_dlg
from pykotor.resource.generics.utc import UTC, UTCClass, read_utc, write_utc
from pykotor.resource.type import ResourceType
from pykotor.tools import creature
from pykotor.tools.misc import is_capsule_file, is_sav_file
from toolset.data.installation import HTInstallation
from toolset.gui.common.localization import translate as tr
from toolset.gui.common.tooltip_utils import append_reference_search_tooltip
from toolset.gui.dialogs.inventory import InventoryEditor
from toolset.gui.dialogs.load_from_location_result import FileSelectionWindow, ResourceItems
from toolset.gui.editor import Editor
from toolset.gui.widgets.settings.installations import GlobalSettings
from toolset.utils.misc import get_qsettings_organization
from toolset.utils.window import add_window, open_resource_editor

if TYPE_CHECKING:
    from pathlib import Path

    from qtpy.QtCore import QPoint
    from qtpy.QtGui import QClipboard
    from qtpy.QtWidgets import QListWidget, QWidget
    from typing_extensions import Literal  # pyright: ignore[reportMissingModuleSource]

    from pykotor.common.language import LocalizedString
    from pykotor.extract.capsule import LazyCapsule
    from pykotor.extract.file import FileResource, LocationResult, ResourceResult
    from pykotor.resource.formats.ltr.ltr_data import LTR
    from pykotor.resource.formats.tpc.tpc_data import TPC, TPCMipmap
    from pykotor.resource.formats.twoda.twoda_data import TwoDA
    from pykotor.tools.path import CaseAwarePath


class UTCEditor(Editor):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation = None,
    ):
        """Initializes the Creature Editor window.

        Args:
        ----
            parent: QWidget: The parent widget
            installation: HTInstallation: The installation object

        Processing Logic:
        ----------------
            - Sets up supported resource types
            - Initializes superclass with parameters
            - Initializes settings objects
            - Initializes UTC object
            - Sets up UI from designer file
            - Sets up installation
            - Sets up signals
            - Sets initial option states
            - Updates 3D preview
            - Creates new empty creature.
        """
        supported: list[ResourceType] = [ResourceType.UTC, ResourceType.BTC, ResourceType.BIC]
        super().__init__(parent, "Creature Editor", "creature", supported, supported, installation)

        self.settings: UTCSettings = UTCSettings()
        self.global_settings: GlobalSettings = GlobalSettings()
        self._utc: UTC = UTC()
        self.setMinimumSize(0, 0)

        from toolset.uic.qtpy.editors.utc import Ui_MainWindow  # pyright: ignore[reportImportType]

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.resize(798, 553)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self._setup_menus()
        self._add_help_action()
        self._setup_installation(installation)
        self._setup_signals()
        self._installation: HTInstallation

        self.ui.actionSaveUnusedFields.setChecked(self.settings.saveUnusedFields)
        self.ui.actionAlwaysSaveK2Fields.setChecked(self.settings.alwaysSaveK2Fields)

        # Initialize model info widget state (collapsed by default)
        self.ui.modelInfoLabel.setVisible(False)
        self.ui.modelInfoSummaryLabel.setVisible(True)

        self.update3dPreview()

        self.new()

        # Connect the new context menu and tooltip actions
        self.ui.portraitPicture.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore[arg-type]
        self.ui.portraitPicture.customContextMenuRequested.connect(self._portrait_context_menu)
        self.ui.portraitPicture.setToolTip(self._generate_portrait_tooltip(as_html=True))

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        if installation is None:
            return
        self._setup_installation(installation)
        self.update3dPreview()

    def _generate_portrait_tooltip(self, *, as_html: bool = False) -> str:
        # sourcery skip: lift-return-into-if
        """Generates a detailed tooltip for the portrait picture."""
        portrait = self._get_portrait_resref()
        if as_html:
            tooltip = f"<b>Portrait:</b> {portrait}<br><br><i>Right-click for more options.</i>"
        else:
            tooltip = f"Portrait: {portrait}\n\nRight-click for more options."
        return tooltip

    def _portrait_context_menu(self, position: QPoint):
        context_menu = QMenu(self)

        portrait = self._get_portrait_resref()
        file_menu = context_menu.addMenu("File...")
        assert file_menu is not None, f"`file_menu = context_menu.addMenu('File...')` {file_menu.__class__.__name__}: {file_menu}"
        locations: dict[str, list[LocationResult]] = self._installation.locations(
            ([portrait], [ResourceType.TGA, ResourceType.TPC]),
            order=[SearchLocation.OVERRIDE, SearchLocation.TEXTURES_GUI, SearchLocation.TEXTURES_TPA, SearchLocation.TEXTURES_TPB, SearchLocation.TEXTURES_TPC, SearchLocation.CHITIN],
        )
        flat_locations: list[LocationResult] = [item for sublist in locations.values() for item in sublist]
        if flat_locations:
            for location in flat_locations:
                display_path_str: str = str(location.filepath.relative_to(self._installation.path()))
                loc_menu = file_menu.addMenu(display_path_str)
                resource_menu_builder = ResourceItems(resources=[location])
                resource_menu_builder.build_menu(loc_menu)

            action = file_menu.addAction("Details...")
            assert action is not None, f"`action = file_menu.addAction('Details...')` {action.__class__.__name__}: {action}"
            action.triggered.connect(lambda: self._open_details(flat_locations))

        context_menu.exec(self.ui.portraitPicture.mapToGlobal(position))  # pyright: ignore[reportCallIssue, reportArgumentType]  # type: ignore[call-overload]

    def _get_portrait_resref(self) -> str:
        index: int = self.ui.portraitSelect.currentIndex()
        alignment: int = self.ui.alignmentSlider.value()
        portraits: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_PORTRAITS)
        assert portraits is not None, f"portraits = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_PORTRAITS) {portraits}: {portraits}"
        result: str = portraits.get_cell(index, "baseresref")
        portrait_variants: tuple[tuple[bool, str], ...] = (
            (40 >= alignment > 30, "baseresrefe"),
            (30 >= alignment > 20, "baseresrefve"),
            (20 >= alignment > 10, "baseresrefvve"),
            (alignment <= 10, "baseresrefvvve"),
        )
        for condition, cell_name in portrait_variants:
            if not condition:
                continue
            variant_resref = portraits.get_cell(index, cell_name)
            if variant_resref:
                return variant_resref
            break
        return result

    def _open_details(
        self,
        locations: list[LocationResult],
    ):
        """Opens a details window for the given resource locations."""
        selection_window: FileSelectionWindow = FileSelectionWindow(locations, self._installation)
        selection_window.show()
        selection_window.activateWindow()
        add_window(selection_window)

    def _copy_portrait_tooltip(self):
        self._copy_to_clipboard(self._generate_portrait_tooltip(as_html=False))

    def _copy_to_clipboard(
        self,
        text: str,
    ):
        clipboard: QClipboard | None = QApplication.clipboard()
        assert clipboard is not None, f"`clipboard = QApplication.clipboard()` {clipboard.__class__.__name__}: {clipboard}"
        clipboard.setText(text)

    def _script_combo_boxes(self) -> list:
        return [widget for widget, _utc_attr in self._script_widget_attr_pairs()]

    def _script_widget_attr_pairs(self) -> list[tuple[object, str]]:
        return [
            (self.ui.onBlockedEdit, "on_blocked"),
            (self.ui.onAttackedEdit, "on_attacked"),
            (self.ui.onNoticeEdit, "on_notice"),
            (self.ui.onConversationEdit, "on_dialog"),
            (self.ui.onDamagedEdit, "on_damaged"),
            (self.ui.onDeathEdit, "on_death"),
            (self.ui.onEndRoundEdit, "on_end_round"),
            (self.ui.onEndConversationEdit, "on_end_dialog"),
            (self.ui.onDisturbedEdit, "on_disturbed"),
            (self.ui.onHeartbeatSelect, "on_heartbeat"),
            (self.ui.onSpawnEdit, "on_spawn"),
            (self.ui.onSpellCastEdit, "on_spell"),
            (self.ui.onUserDefinedSelect, "on_user_defined"),
        ]

    def _script_widget_values(self, utc: UTC) -> list[tuple[object, str]]:
        return [(widget, str(getattr(utc, utc_attr))) for widget, utc_attr in self._script_widget_attr_pairs()]

    def _set_combo_box_max_lengths(self, combo_boxes: Sequence[object], length: int):
        for combo_box in combo_boxes:
            line_edit = combo_box.lineEdit()
            if line_edit is not None:
                line_edit.setMaxLength(length)

    def _setup_signals(self):
        """Connect signals to slots.

        Processing Logic:
        ----------------
            - Connects button and widget signals to appropriate slot methods
            - Connects value changed signals from slider and dropdowns
            - Connects menu action triggers to toggle settings.
        """
        signal_connections = [
            (self.ui.firstnameRandomButton.clicked, self.randomize_first_name),
            (self.ui.lastnameRandomButton.clicked, self.randomize_last_name),
            (self.ui.tagGenerateButton.clicked, self.generate_tag),
            (self.ui.portraitSelect.currentIndexChanged, self.portrait_changed),
            (self.ui.conversationModifyButton.clicked, self.edit_conversation),
            (self.ui.inventoryButton.clicked, self.open_inventory),
            (self.ui.featList.itemChanged, self.update_feat_summary),
            (self.ui.powerList.itemChanged, self.update_power_summary),
            (self.ui.appearanceSelect.currentIndexChanged, self.update3dPreview),
            (self.ui.actionShowPreview.triggered, self.toggle_preview),
            (self.ui.modelInfoGroupBox.toggled, self._on_model_info_toggled),
            (self.ui.previewRenderer.resourcesLoaded, self._on_textures_loaded),
        ]
        for signal, handler in signal_connections:
            signal.connect(handler)

        self.ui.alignmentSlider.valueChanged.connect(lambda: self.portrait_changed(self.ui.portraitSelect.currentIndex()))
        self.ui.alignmentSlider.valueChanged.connect(self.update3dPreview)

        # Class level tooltips are set in utc.ui with full GFF/modder description

        for action, setting_name in (
            (self.ui.actionSaveUnusedFields, "saveUnusedFields"),
            (self.ui.actionAlwaysSaveK2Fields, "alwaysSaveK2Fields"),
        ):
            action.triggered.connect(lambda _checked=False, a=action, name=setting_name: setattr(self.settings, name, a.isChecked()))

    def _setup_installation(  # noqa: C901, PLR0912, PLR0915
        self,
        installation: HTInstallation,
    ):
        """Sets up the installation for character creation.

        Args:
        ----
            installation: {HTInstallation}: The installation to load data from

        Processing Logic:
        ----------------
            - Loads required 2da files if not already loaded
            - Sets items for dropdown menus from loaded 2da files
            - Clears and populates feat and power lists from loaded 2da files
            - Sets visibility of some checkboxes based on installation type.
        """
        self._installation = installation

        self.ui.previewRenderer.installation = installation
        self.ui.firstnameEdit.set_installation(installation)
        self.ui.lastnameEdit.set_installation(installation)

        # Load required 2da files if they have not been loaded already
        required: list[str] = [
            HTInstallation.TwoDA_APPEARANCES,
            HTInstallation.TwoDA_BASEITEMS,
            "heads",
            HTInstallation.TwoDA_SOUNDSETS,
            HTInstallation.TwoDA_PORTRAITS,
            HTInstallation.TwoDA_SUBRACES,
            HTInstallation.TwoDA_SPEEDS,
            HTInstallation.TwoDA_FACTIONS,
            HTInstallation.TwoDA_GENDERS,
            HTInstallation.TwoDA_PERCEPTIONS,
            HTInstallation.TwoDA_CLASSES,
            HTInstallation.TwoDA_FEATS,
            HTInstallation.TwoDA_POWERS,
        ]
        installation.ht_batch_cache_2da(required)

        appearances: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_APPEARANCES)
        soundsets: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_SOUNDSETS)
        portraits: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_PORTRAITS)
        subraces: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_SUBRACES)
        speeds: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_SPEEDS)
        factions: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_FACTIONS)
        genders: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_GENDERS)
        perceptions: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_PERCEPTIONS)
        classes: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_CLASSES)
        races: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_RACES)

        def _setup_select_from_2da(widget, twoda: TwoDA | None, twoda_name: str, column_name: str, transform=None) -> None:
            if twoda is None:
                return
            widget.set_context(twoda, self._installation, twoda_name)
            values = twoda.get_column(column_name)
            widget.set_items([transform(value) for value in values] if transform is not None else values)

        def _populate_checkable_list_from_2da(list_widget, twoda: TwoDA, name_column: str, text_transform=None) -> None:
            """Populate a QListWidget with checkable items from a TwoDA.

            Args:
            ----
                list_widget: The QListWidget to populate
                twoda: The TwoDA data source
                name_column: Column name for the text
                text_transform: Optional function to transform the text
            """
            list_widget.clear()
            for item in twoda:
                stringref: int = item.get_integer("name", 0)
                text: str = installation.talktable().string(stringref) if stringref else item.get_string(name_column)
                if text_transform:
                    text = text_transform(text)
                text = text or f"[Unused {name_column.title()} ID: {item.label()}]"
                qitem = QListWidgetItem(text)
                qitem.setData(Qt.ItemDataRole.UserRole, int(item.label()))
                qitem.setFlags(qitem.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                qitem.setCheckState(Qt.CheckState.Unchecked)
                list_widget.addItem(qitem)  # pyright: ignore[reportArgumentType, reportCallIssue]
            list_widget.setSortingEnabled(True)
            list_widget.sortItems(Qt.SortOrder.AscendingOrder)  # pyright: ignore[reportArgumentType]

        _setup_select_from_2da(self.ui.appearanceSelect, appearances, HTInstallation.TwoDA_APPEARANCES, "label")
        _setup_select_from_2da(self.ui.soundsetSelect, soundsets, HTInstallation.TwoDA_SOUNDSETS, "label")
        _setup_select_from_2da(self.ui.portraitSelect, portraits, HTInstallation.TwoDA_PORTRAITS, "baseresref")
        _setup_select_from_2da(self.ui.subraceSelect, subraces, HTInstallation.TwoDA_SUBRACES, "label")
        _setup_select_from_2da(self.ui.speedSelect, speeds, HTInstallation.TwoDA_SPEEDS, "label")
        _setup_select_from_2da(self.ui.factionSelect, factions, HTInstallation.TwoDA_FACTIONS, "label")
        _setup_select_from_2da(
            self.ui.genderSelect,
            genders,
            HTInstallation.TwoDA_GENDERS,
            "constant",
            transform=lambda label: label.replace("_", " ").title().replace("Gender ", ""),
        )
        _setup_select_from_2da(self.ui.perceptionSelect, perceptions, HTInstallation.TwoDA_PERCEPTIONS, "label")

        if classes is not None:  # sourcery skip: extract-method
            self.ui.class1Select.set_context(classes, self._installation, HTInstallation.TwoDA_CLASSES)
            self.ui.class1Select.set_items(classes.get_column("label"))

            self.ui.class2Select.set_context(classes, self._installation, HTInstallation.TwoDA_CLASSES)
            self.ui.class2Select.clear()
            self.ui.class2Select.setPlaceholderText(tr("[Unset]"))
            for label in classes.get_column("label"):  # pyright: ignore[reportArgumentType]
                self.ui.class2Select.addItem(label)
        self.ui.raceSelect.set_context(races, self._installation, HTInstallation.TwoDA_RACES)

        self.ui.raceSelect.clear()
        self.ui.raceSelect.addItem("Droid", 5)
        self.ui.raceSelect.addItem("Creature", 6)

        feats: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_FEATS)
        if feats is not None:
            _populate_checkable_list_from_2da(self.ui.featList, feats, "label")

        powers: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_POWERS)
        if powers is not None:
            _populate_checkable_list_from_2da(
                self.ui.powerList,
                powers,
                "label",
                text_transform=lambda t: t.replace("_", " ").replace("XXX", "").replace("\n", "").title(),
            )

        self.ui.noBlockCheckbox.setVisible(installation.tsl)
        self.ui.hologramCheckbox.setVisible(installation.tsl)
        self.ui.k2onlyBox.setVisible(installation.tsl)

        # Setup context menus for script fields with reference search enabled
        for field in self._script_combo_boxes():
            self._installation.setup_file_context_menu(field, [ResourceType.NSS, ResourceType.NCS], enable_reference_search=True, reference_search_type="script")
            append_reference_search_tooltip(field, "script")

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes,
    ):
        """Load UTC from bytes. Defaults when missing: see construct_utc. K1 LoadCreature @ 0x00500350 (LoadCreatures @ 0x00504a70), TSL LoadCreature @ 0x0068ccb0 (LoadCreatures @ 0x0071b140); ReadStatsFromGff @ (K1: 0x00560e60, TSL: 0x006ec350)."""
        super().load(filepath, resref, restype, data)
        self._load_utc(read_utc(data))
        self.update_item_count()

    def _load_utc(
        self,
        utc: UTC,
    ):
        """Loads UTC data into the UI.

        Args:
        ----
            utc (UTC): UTC object to load data from

        Loads UTC data (defaults from construct_utc; K1 LoadCreature 0x00500350, ReadStatsFromGff 0x00560e60; TSL LoadCreature 0x0068ccb0):
            - Sets UTC object reference and preview renderer creature
            - Loads basic data (name, tag, resref, appearance, soundset, conversation, portrait)
            - Loads advanced data (flags, stats, classes, feats, powers, scripts, comments)
        """
        self._utc = utc
        self.ui.previewRenderer.set_creature(utc)

        # Basic
        self.ui.firstnameEdit.set_locstring(utc.first_name)
        self.ui.lastnameEdit.set_locstring(utc.last_name)
        self.ui.tagEdit.setText(utc.tag)
        self.ui.resrefEdit.setText(str(utc.resref))
        self.ui.appearanceSelect.setCurrentIndex(utc.appearance_id)
        self.ui.soundsetSelect.setCurrentIndex(utc.soundset_id)
        self.ui.conversationEdit.set_combo_box_text(str(utc.conversation))
        self.ui.portraitSelect.setCurrentIndex(utc.portrait_id)

        # Advanced
        self.ui.disarmableCheckbox.setChecked(utc.disarmable)
        self.ui.noPermDeathCheckbox.setChecked(utc.no_perm_death)
        self.ui.min1HpCheckbox.setChecked(utc.min1_hp)
        self.ui.plotCheckbox.setChecked(utc.plot)
        self.ui.isPcCheckbox.setChecked(utc.is_pc)
        self.ui.noReorientateCheckbox.setChecked(utc.not_reorienting)
        self.ui.noBlockCheckbox.setChecked(utc.ignore_cre_path)
        self.ui.hologramCheckbox.setChecked(utc.hologram)
        # raceSelect is a ComboBox2DA which overrides setCurrentIndex() to expect the row index (5 or 6)
        # So we can use setCurrentIndex() directly with the race_id
        self.ui.raceSelect.setCurrentIndex(utc.race_id)
        self.ui.subraceSelect.setCurrentIndex(utc.subrace_id)
        self.ui.speedSelect.setCurrentIndex(utc.walkrate_id)
        self.ui.factionSelect.setCurrentIndex(utc.faction_id)
        self.ui.genderSelect.setCurrentIndex(utc.gender_id)
        self.ui.perceptionSelect.setCurrentIndex(utc.perception_id)
        self.ui.challengeRatingSpin.setValue(utc.challenge_rating)
        self.ui.blindSpotSpin.setValue(utc.blindspot)
        self.ui.multiplierSetSpin.setValue(utc.multiplier_set)

        # Stats
        self.ui.computerUseSpin.setValue(utc.computer_use)
        self.ui.demolitionsSpin.setValue(utc.demolitions)
        self.ui.stealthSpin.setValue(utc.stealth)
        self.ui.awarenessSpin.setValue(utc.awareness)
        self.ui.persuadeSpin.setValue(utc.persuade)
        self.ui.repairSpin.setValue(utc.repair)
        self.ui.securitySpin.setValue(utc.security)
        self.ui.treatInjurySpin.setValue(utc.treat_injury)
        self.ui.fortitudeSpin.setValue(utc.fortitude_bonus)
        self.ui.reflexSpin.setValue(utc.reflex_bonus)
        self.ui.willSpin.setValue(utc.willpower_bonus)
        self.ui.armorClassSpin.setValue(utc.natural_ac)
        self.ui.strengthSpin.setValue(utc.strength)
        self.ui.dexteritySpin.setValue(utc.dexterity)
        self.ui.constitutionSpin.setValue(utc.constitution)
        self.ui.intelligenceSpin.setValue(utc.intelligence)
        self.ui.wisdomSpin.setValue(utc.wisdom)
        self.ui.charismaSpin.setValue(utc.charisma)

        # TODO(th3w1zard1): Fix the maximum. Use max() due to uncertainty
        self.ui.baseHpSpin.setMaximum(max(self.ui.baseHpSpin.maximum(), utc.hp))
        self.ui.currentHpSpin.setMaximum(max(self.ui.currentHpSpin.maximum(), utc.current_hp))
        self.ui.maxHpSpin.setMaximum(max(self.ui.maxHpSpin.maximum(), utc.max_hp))
        self.ui.currentFpSpin.setMaximum(max(self.ui.currentFpSpin.maximum(), utc.fp))
        self.ui.maxFpSpin.setMaximum(max(self.ui.maxFpSpin.maximum(), utc.max_fp))
        self.ui.baseHpSpin.setValue(utc.hp)
        self.ui.currentHpSpin.setValue(utc.current_hp)
        self.ui.maxHpSpin.setValue(utc.max_hp)
        self.ui.currentFpSpin.setValue(utc.fp)
        self.ui.maxFpSpin.setValue(utc.max_fp)

        # Classes
        if len(utc.classes) >= 1:
            self.ui.class1Select.setCurrentIndex(utc.classes[0].class_id)
            self.ui.class1LevelSpin.setValue(utc.classes[0].class_level)
        if len(utc.classes) >= 2:  # noqa: PLR2004
            self.ui.class2Select.setCurrentIndex(utc.classes[1].class_id + 1)
            self.ui.class2LevelSpin.setValue(utc.classes[1].class_level)
        self.ui.alignmentSlider.setValue(utc.alignment)

        # Feats
        self._apply_checked_ids_to_list(
            self.ui.featList,
            utc.feats,
            self.get_feat_item,
            "featList",
            "[Modded Feat ID: {id_value}]",
        )

        # Powers
        power_ids: list[int] = [power for utc_class in utc.classes for power in utc_class.powers]
        self._apply_checked_ids_to_list(
            self.ui.powerList,
            power_ids,
            self.get_power_item,
            "powerList",
            "[Modded Power ID: {id_value}]",
        )
        self.relevant_script_resnames: list[str] = sorted(iter({res.resname().lower() for res in self._installation.get_relevant_resources(ResourceType.NCS, self._filepath)}))

        dlg_resources: list[FileResource] = self._installation.get_relevant_resources(ResourceType.DLG, self._filepath)
        dlg_resnames_set: set[str] = {res.resname().lower() for res in dlg_resources}
        dlg_resnames_sorted: list[str] = sorted(dlg_resnames_set)
        self.ui.conversationEdit.populate_combo_box(dlg_resnames_sorted)

        reference_fields = [
            (self.ui.conversationEdit, [ResourceType.DLG], "conversation"),
            (self.ui.tagEdit, [], "tag"),
            (self.ui.resrefEdit, [], "template_resref"),
        ]
        for widget, resource_types, reference_type in reference_fields:
            self._setup_reference_field(widget, resource_types, reference_type)

        # Set maxLength for FilterComboBox script fields (ResRefs are max 16 characters)
        script_combo_boxes = [*self._script_combo_boxes(), self.ui.conversationEdit]
        self._set_combo_box_max_lengths(script_combo_boxes, 16)

        for script_combo_box in self._script_combo_boxes():
            script_combo_box.populate_combo_box(self.relevant_script_resnames)

        # Scripts
        for script_widget, script_value in self._script_widget_values(utc):
            script_widget.set_combo_box_text(script_value)

        # Comments
        self.ui.comments.setPlainText(utc.comment)
        self._update_comments_tab_title()

    def _update_comments_tab_title(self):
        """Updates the Comments tab title with a notification badge if comments are not blank."""
        comments = self.ui.comments.toPlainText()
        if comments:
            self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.commentsTab), "Comments *")  # pyright: ignore[reportArgumentType]
        else:
            self.ui.tabWidget.setTabText(self.ui.tabWidget.indexOf(self.ui.commentsTab), "Comments")  # pyright: ignore[reportArgumentType]

    def _setup_reference_field(
        self,
        widget,
        resource_types: list[ResourceType],
        reference_type: str,
    ) -> None:
        """Configure context menu and tooltip for a reference-search enabled widget."""
        self._installation.setup_file_context_menu(
            widget,
            resource_types,
            enable_reference_search=True,
            reference_search_type=reference_type,
        )
        append_reference_search_tooltip(widget, reference_type)

    def _uncheck_all_list_items(self, list_widget: QListWidget, list_name: str) -> None:
        """Set all checkable items in a list widget to unchecked state."""
        for i in range(list_widget.count()):
            item: QListWidgetItem | None = list_widget.item(i)
            assert item is not None, f"{self.__class__.__name__}.ui.{list_name}.item({i}) {item.__class__.__name__}: {item}"
            item.setCheckState(Qt.CheckState.Unchecked)  # pyright: ignore[reportArgumentType]

    def _apply_checked_ids_to_list(
        self,
        list_widget: QListWidget,
        ids: list[int],
        get_item,
        list_name: str,
        modded_label_template: str,
    ) -> None:
        """Apply checked state for id-backed list items, creating missing modded entries."""
        self._uncheck_all_list_items(list_widget, list_name)
        for id_value in ids:
            item = get_item(id_value)
            if item is None:
                item = QListWidgetItem(modded_label_template.format(id_value=id_value))
                item.setData(Qt.ItemDataRole.UserRole, id_value)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                list_widget.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]
            item.setCheckState(Qt.CheckState.Checked)

    def build(self) -> tuple[bytes | bytearray, bytes]:
        """Build UTC bytes from editor state. Write values match engine. K1 LoadCreature @ 0x00500350, TSL @ 0x0068ccb0; ReadStatsFromGff @ (K1: 0x00560e60, TSL: 0x006ec350)."""
        utc: UTC = deepcopy(self._utc)

        utc.first_name = self.ui.firstnameEdit.locstring()
        utc.last_name = self.ui.lastnameEdit.locstring()
        utc.tag = self.ui.tagEdit.text()
        utc.resref = ResRef(self.ui.resrefEdit.text())
        utc.appearance_id = self.ui.appearanceSelect.currentIndex()
        utc.soundset_id = self.ui.soundsetSelect.currentIndex()
        utc.conversation = ResRef(self.ui.conversationEdit.currentText())
        utc.portrait_id = self.ui.portraitSelect.currentIndex()
        utc.disarmable = self.ui.disarmableCheckbox.isChecked()
        utc.no_perm_death = self.ui.noPermDeathCheckbox.isChecked()
        utc.min1_hp = self.ui.min1HpCheckbox.isChecked()
        utc.plot = self.ui.plotCheckbox.isChecked()
        utc.is_pc = self.ui.isPcCheckbox.isChecked()
        utc.not_reorienting = self.ui.noReorientateCheckbox.isChecked()
        utc.ignore_cre_path = self.ui.noBlockCheckbox.isChecked()
        utc.hologram = self.ui.hologramCheckbox.isChecked()
        # raceSelect is a ComboBox2DA which overrides currentIndex() to return the row index (5 or 6)
        # So we can use currentIndex() directly to get the race_id
        race_id = self.ui.raceSelect.currentIndex()
        utc.race_id = max(race_id, 0)
        utc.subrace_id = self.ui.subraceSelect.currentIndex()
        utc.walkrate_id = self.ui.speedSelect.currentIndex()
        utc.faction_id = self.ui.factionSelect.currentIndex()
        utc.gender_id = self.ui.genderSelect.currentIndex()
        utc.perception_id = self.ui.perceptionSelect.currentIndex()
        utc.challenge_rating = self.ui.challengeRatingSpin.value()
        utc.blindspot = self.ui.blindSpotSpin.value()
        utc.multiplier_set = self.ui.multiplierSetSpin.value()
        utc.computer_use = self.ui.computerUseSpin.value()
        utc.demolitions = self.ui.demolitionsSpin.value()
        utc.stealth = self.ui.stealthSpin.value()
        utc.awareness = self.ui.awarenessSpin.value()
        utc.persuade = self.ui.persuadeSpin.value()
        utc.repair = self.ui.repairSpin.value()
        utc.security = self.ui.securitySpin.value()
        utc.treat_injury = self.ui.treatInjurySpin.value()
        utc.fortitude_bonus = self.ui.fortitudeSpin.value()
        utc.reflex_bonus = self.ui.reflexSpin.value()
        utc.willpower_bonus = self.ui.willSpin.value()
        utc.natural_ac = self.ui.armorClassSpin.value()
        utc.strength = self.ui.strengthSpin.value()
        utc.dexterity = self.ui.dexteritySpin.value()
        utc.constitution = self.ui.constitutionSpin.value()
        utc.intelligence = self.ui.intelligenceSpin.value()
        utc.wisdom = self.ui.wisdomSpin.value()
        utc.charisma = self.ui.charismaSpin.value()
        utc.hp = self.ui.baseHpSpin.value()
        utc.current_hp = self.ui.currentHpSpin.value()
        utc.max_hp = self.ui.maxHpSpin.value()
        utc.fp = self.ui.currentFpSpin.value()
        utc.max_fp = self.ui.maxFpSpin.value()
        utc.alignment = self.ui.alignmentSlider.value()
        utc.on_blocked = ResRef(self.ui.onBlockedEdit.currentText())
        utc.on_attacked = ResRef(self.ui.onAttackedEdit.currentText())
        utc.on_notice = ResRef(self.ui.onNoticeEdit.currentText())
        utc.on_dialog = ResRef(self.ui.onConversationEdit.currentText())
        utc.on_damaged = ResRef(self.ui.onDamagedEdit.currentText())
        utc.on_disturbed = ResRef(self.ui.onDisturbedEdit.currentText())
        utc.on_death = ResRef(self.ui.onDeathEdit.currentText())
        utc.on_end_round = ResRef(self.ui.onEndRoundEdit.currentText())
        utc.on_end_dialog = ResRef(self.ui.onEndConversationEdit.currentText())
        utc.on_heartbeat = ResRef(self.ui.onHeartbeatSelect.currentText())
        utc.on_spawn = ResRef(self.ui.onSpawnEdit.currentText())
        utc.on_spell = ResRef(self.ui.onSpellCastEdit.currentText())
        utc.on_user_defined = ResRef(self.ui.onUserDefinedSelect.currentText())
        utc.comment = self.ui.comments.toPlainText()

        utc.classes = []
        if self.ui.class1Select.currentIndex() != -1:
            class_id: int = self.ui.class1Select.currentIndex()
            class_level: int = self.ui.class1LevelSpin.value()
            utc.classes.append(UTCClass(class_id, class_level))
        if self.ui.class2Select.currentIndex() != 0:
            # class2Select index 0 is "[Unset]", index 1 = class_id 0, index 2 = class_id 1, etc.
            class_id = self.ui.class2Select.currentIndex() - 1
            class_level = self.ui.class2LevelSpin.value()
            utc.classes.append(UTCClass(class_id, class_level))

        item: QListWidgetItem | None
        utc.feats = []
        for i in range(self.ui.featList.count()):
            item = self.ui.featList.item(i)  # pyright: ignore[reportAssignmentType]
            assert item is not None, f"{self.__class__.__name__}.ui.featList.item({i}) {item.__class__.__name__}: {item}"
            if item.checkState() == Qt.CheckState.Checked:
                utc.feats.append(item.data(Qt.ItemDataRole.UserRole))

        powers: list[int] = utc.classes[-1].powers
        for i in range(self.ui.powerList.count()):
            item = self.ui.powerList.item(i)  # pyright: ignore[reportAssignmentType]
            assert item is not None, f"{self.__class__.__name__}.ui.powerList.item({i}) {item.__class__.__name__}: {item}"
            if item.checkState() == Qt.CheckState.Checked:
                powers.append(item.data(Qt.ItemDataRole.UserRole))

        use_tsl: Literal[Game.K2, Game.K1] = Game.K2 if self.settings.alwaysSaveK2Fields or self._installation.tsl else Game.K1
        data = bytearray()
        write_utc(
            utc,
            data,
            game=use_tsl,
            use_deprecated=self.settings.saveUnusedFields,
        )

        return data, b""

    def new(self):
        super().new()
        self._load_utc(UTC())
        self.update_item_count()

    def randomize_first_name(self):
        ltr_resname: Literal["humanf", "humanm"] = "humanf" if self.ui.genderSelect.currentIndex() == 1 else "humanm"
        locstring: LocalizedString = self.ui.firstnameEdit.locstring()
        ltr: LTR = read_ltr(self._installation.resource(ltr_resname, ResourceType.LTR).data)
        locstring.stringref = -1
        locstring.set_data(Language.ENGLISH, Gender.MALE, ltr.generate())
        self.ui.firstnameEdit.set_locstring(locstring)

    def randomize_last_name(self):
        locstring: LocalizedString = self.ui.lastnameEdit.locstring()
        ltr: LTR = read_ltr(self._installation.resource("humanl", ResourceType.LTR).data)
        locstring.stringref = -1
        locstring.set_data(Language.ENGLISH, Gender.MALE, ltr.generate())
        self.ui.lastnameEdit.set_locstring(locstring)

    def generate_tag(self):
        self.ui.tagEdit.setText(self.ui.resrefEdit.text())

    def portrait_changed(
        self,
        _actual_combo_index: int,
    ):
        """Updates the portrait picture based on the selected index.

        Args:
        ----
            index (int): The selected index

        Updates the portrait pixmap:
            - Checks if index is 0, creates blank image
            - Else builds pixmap from index
            - Sets pixmap to portrait picture widget.
        """
        index: int = self.ui.portraitSelect.currentIndex()
        if index == 0:
            image = QImage(bytes(0 for _ in range(64 * 64 * 3)), 64, 64, QImage.Format.Format_RGB888)
            pixmap: QPixmap = QPixmap.fromImage(image)
        else:
            pixmap = self._build_pixmap(index)
        self.ui.portraitPicture.setPixmap(pixmap)
        self.ui.portraitPicture.setToolTip(self._generate_portrait_tooltip(as_html=True))

    def _build_pixmap(
        self,
        index: int,
    ) -> QPixmap:
        """Builds a portrait pixmap based on character alignment.

        Args:
        ----
            index: The character index to build a portrait for.

        Returns:
        -------
            pixmap: A QPixmap of the character portrait

        Builds the portrait pixmap by:
            1. Getting the character's alignment value
            2. Looking up the character's portrait reference in the portraits 2DA based on alignment
            3. Loading the texture for the portrait reference
            4. Converting the texture to a QPixmap.
        """
        alignment: int = self.ui.alignmentSlider.value()
        portraits: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_PORTRAITS)
        assert portraits is not None, f"portraits = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_PORTRAITS) {portraits.__class__.__name__}: {portraits}"
        portrait: str = portraits.get_cell(index, "baseresref")

        if 40 >= alignment > 30 and portraits.get_cell(index, "baseresrefe"):  # TODO(th3w1zard1): document these magic numbers  # noqa: FIX002, PLR2004, TD003
            portrait = portraits.get_cell(index, "baseresrefe")
        elif 30 >= alignment > 20 and portraits.get_cell(index, "baseresrefve"):  # noqa: PLR2004
            portrait = portraits.get_cell(index, "baseresrefve")
        elif 20 >= alignment > 10 and portraits.get_cell(index, "baseresrefvve"):  # noqa: PLR2004
            portrait = portraits.get_cell(index, "baseresrefvve")
        elif alignment <= 10 and portraits.get_cell(index, "baseresrefvvve"):  # noqa: PLR2004
            portrait = portraits.get_cell(index, "baseresrefvvve")

        texture: TPC | None = self._installation.texture(portrait, [SearchLocation.TEXTURES_GUI])

        if texture is not None:
            if texture.format().is_dxt():
                texture.decode()
            mipmap: TPCMipmap = texture.get(0, 0)
            image = QImage(bytes(mipmap.data), mipmap.width, mipmap.height, texture.format().to_qimage_format())
            return QPixmap.fromImage(image).transformed(QTransform().scale(1, -1))

        image = QImage(bytes(0 for _ in range(64 * 64 * 3)), 64, 64, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(image)

    def edit_conversation(self):
        """Edits a conversation.

        Processing Logic:
        ----------------
            1. Gets the conversation name from the UI text field
            2. Searches the installation for the conversation resource
            3. If not found, prompts to create a new file in the override folder
            4. Opens the resource editor with the conversation data.
        """
        resname: str = self.ui.conversationEdit.currentText()

        restype: ResourceType | None = None
        filepath: Path | CaseAwarePath | None = None
        data: bytes | None = None

        if not resname:
            QMessageBox(QMessageBox.Icon.Critical, "Invalid Dialog Reference", "Conversation field cannot be blank.").exec()
            return

        search: ResourceResult | None = self._installation.resource(resname, ResourceType.DLG)
        if search is None:
            if (
                QMessageBox(
                    QMessageBox.Icon.Information,
                    "DLG file not found",
                    "Do you wish to create a new dialog in the 'Override' folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ).exec()
                == QMessageBox.StandardButton.Yes
            ):
                filepath = self._installation.override_path() / f"{resname}.dlg"
                blank_dlg: bytes = bytes_dlg(DLG(), self._installation.game())
                filepath.write_bytes(blank_dlg)
        else:
            resname, restype, filepath, data = search  # pyright: ignore[reportAssignmentType]

        if data is None or filepath is None:
            print(f"Data/filepath cannot be None in self.edit_conversation() relevance: (resname={resname}, restype={restype!r}, filepath={filepath!r})")
            return

        open_resource_editor(filepath, resname, ResourceType.DLG, data, self._installation, self)

    def open_inventory(self):
        """Opens the inventory editor.

        Processing Logic:
        ----------------
            - Loads installed capsules from the root module folder
            - Initializes InventoryEditor with loaded capsules and current inventory/equipment
            - If InventoryEditor is closed successfully, updates internal inventory/equipment
            - Refreshes item count and 3D preview.
        """
        droid: bool = self.ui.raceSelect.currentIndex() == 0
        capsules_to_search: Sequence[LazyCapsule] = []
        if self._filepath is None:
            ...
        elif is_sav_file(self._filepath):
            # search the capsules inside the .sav outer capsule.
            # self._filepath represents the outer capsule
            # res.filepath() is potentially a nested capsule.
            capsules_to_search = [Capsule(res.filepath()) for res in Capsule(self._filepath) if is_capsule_file(res.filename()) and res.inside_capsule]
        elif is_capsule_file(self._filepath):
            capsules_to_search = Module.get_capsules_tuple_matching(self._installation, self._filepath.name)
        inventory_editor = InventoryEditor(
            self,
            self._installation,
            capsules_to_search,
            [],
            self._utc.inventory,
            self._utc.equipment,
            droid=droid,
        )
        if inventory_editor.exec():
            self._utc.inventory = inventory_editor.inventory
            self._utc.equipment = inventory_editor.equipment
            self.update_item_count()
            self.update3dPreview()

    def update_item_count(self):
        self.ui.inventoryCountLabel.setText(f"Total Items: {len(self._utc.inventory)}")

    def _find_list_item_by_user_role(
        self,
        list_widget: QListWidget,
        role_value: int,
        list_name: str,
    ) -> QListWidgetItem | None:
        """Find a QListWidget item by UserRole value."""
        for i in range(list_widget.count()):
            item: QListWidgetItem | None = list_widget.item(i)  # pyright: ignore[reportAssignmentType]
            if item is None:
                RobustLogger().warning(
                    "self.ui.%s.item(i=%s) returned None. Relevance: %r",
                    list_name,
                    i,
                    self,
                )
                continue
            if item.data(Qt.ItemDataRole.UserRole) == role_value:
                return item
        return None

    def _checked_list_summary(
        self,
        list_widget: QListWidget,
        list_name: str,
    ) -> str:
        """Build newline-separated summary of checked item texts."""
        checked_texts: list[str] = []
        for i in range(list_widget.count()):
            item: QListWidgetItem | None = list_widget.item(i)  # pyright: ignore[reportAssignmentType]
            if item is None:
                RobustLogger().warning(
                    "self.ui.%s.item(i=%s) returned None. Relevance: %r",
                    list_name,
                    i,
                    self,
                )
                continue

            if item.checkState() == Qt.CheckState.Checked:
                checked_texts.append(item.text())
        return "\n".join(checked_texts)

    def get_feat_item(
        self,
        feat_id: int,
    ) -> QListWidgetItem | None:
        return self._find_list_item_by_user_role(self.ui.featList, feat_id, "featList")

    def get_power_item(
        self,
        power_id: int,
    ) -> QListWidgetItem | None:
        return self._find_list_item_by_user_role(self.ui.powerList, power_id, "powerList")

    def toggle_preview(self):
        self.global_settings.showPreviewUTC = not self.global_settings.showPreviewUTC
        self.update3dPreview()

    def update_feat_summary(self):
        self.ui.featSummaryEdit.setPlainText(self._checked_list_summary(self.ui.featList, "featList"))

    def update_power_summary(self):
        self.ui.powerSummaryEdit.setPlainText(self._checked_list_summary(self.ui.powerList, "powerList"))

    def update3dPreview(self):
        """Updates the 3D preview and model info.

        Hides BOTH the preview renderer AND the model info groupbox when preview is hidden.
        """
        show_preview = self.global_settings.showPreviewUTC
        self.ui.actionShowPreview.setChecked(show_preview)
        self.ui.previewRenderer.setVisible(show_preview)
        self.ui.modelInfoGroupBox.setVisible(show_preview)

        if show_preview:
            self.resize(max(798, self.sizeHint().width()), max(553, self.sizeHint().height()))

            if self._installation is not None:
                data, _ = self.build()
                utc: UTC = read_utc(data)
                self.ui.previewRenderer.set_creature(utc)
                self._update_model_info(utc)
        else:
            self.resize(max(798 - 350, self.sizeHint().width()), max(553, self.sizeHint().height()))

    def _update_model_info(self, utc: UTC):
        """Updates the model information label with creature model details.

        Args:
        ----
            utc: The UTC object to analyze
        """
        if self._installation is None:
            return

        info_lines: list[str] = []

        try:

            def _append_renderer_texture_details(tex_name: str, *, indent: str = "    ") -> None:
                """Append texture resolution details from the renderer's existing lookup info.

                IMPORTANT: This MUST NOT perform any new Installation lookups. It only reads
                the cached metadata produced by the existing async resolver/worker pipeline.
                """
                scene = getattr(self.ui.previewRenderer, "_scene", None)
                if scene is None:
                    info_lines.append(f"{indent}Renderer: (scene not initialized)")
                    return
                lookup = getattr(scene, "texture_lookup_info", {}) or {}
                tex_info = lookup.get(tex_name)
                if not tex_info:
                    info_lines.append(f"{indent}Renderer: (not yet requested)")
                    return

                if tex_info.get("found"):
                    filepath = tex_info.get("filepath")
                    restype = tex_info.get("restype")
                    source_location = tex_info.get("source_location")

                    if filepath:
                        try:
                            rel_path = os.path.relpath(filepath, self._installation.path())
                        except Exception:  # noqa: BLE001
                            rel_path = str(filepath)
                        if restype:
                            info_lines.append(f"{indent}Renderer: {rel_path} ({restype})")
                        else:
                            info_lines.append(f"{indent}Renderer: {rel_path}")
                    else:
                        info_lines.append(f"{indent}Renderer: ✓ Loaded")

                    if source_location is not None:
                        # source_location is a SearchLocation (or None) recorded by SceneBase
                        try:
                            info_lines.append(f"{indent}  └─ SearchLocation: {self._format_search_order([source_location])}")
                        except Exception:  # noqa: BLE001
                            info_lines.append(f"{indent}  └─ SearchLocation: {source_location}")
                else:
                    search_order = tex_info.get("search_order", [])
                    search_str = self._format_search_order(search_order) if search_order else "Unknown"
                    info_lines.append(f"{indent}Renderer: ❌ Not found")
                    info_lines.append(f"{indent}  └─ Searched: {search_str}")

            # Get body model and texture
            appearance_2da: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_APPEARANCES)
            baseitems_2da: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_BASEITEMS)
            heads_2da: TwoDA | None = self._installation.ht_get_cache_2da("heads")

            body_model, body_texture = creature.get_body_model(
                utc,
                self._installation,
                appearance=appearance_2da,
                baseitems=baseitems_2da,
            )
            if body_model:
                info_lines.append(f"Body Model: '{body_model}'")
                body_mdl: ResourceResult | None = self._installation.resource(body_model, ResourceType.MDL)
                if body_mdl:
                    try:
                        mdl_path = body_mdl.filepath.relative_to(self._installation.path())
                        info_lines.append(f"  MDL: {mdl_path}")
                        source = self._get_source_location_type(body_mdl.filepath)
                        if source:
                            info_lines.append(f"    └─ Source: {source}")
                    except ValueError:
                        info_lines.append(f"  MDL: {body_mdl.filepath}")

                if body_texture:
                    info_lines.append(f"  Body Texture: '{body_texture}'")
                    # NOTE: Do not call Installation.texture()/location() here.
                    # Use renderer-produced lookup info instead (async-safe, no extra lookups).
                    _append_renderer_texture_details(body_texture, indent="    ")

            # Get head model and texture
            head_model, head_texture = creature.get_head_model(
                utc,
                self._installation,
                appearance=appearance_2da,
                heads=heads_2da,
            )
            if head_model:
                info_lines.append(f"Head Model: '{head_model}'")
                head_mdl: ResourceResult | None = self._installation.resource(head_model, ResourceType.MDL)
                if head_mdl:
                    try:
                        mdl_path = head_mdl.filepath.relative_to(self._installation.path())
                        info_lines.append(f"  MDL: {mdl_path}")
                    except ValueError:
                        info_lines.append(f"  MDL: {head_mdl.filepath}")

                if head_texture:
                    info_lines.append(f"  Head Texture: '{head_texture}'")
                    _append_renderer_texture_details(head_texture, indent="    ")

            # Get weapon models
            right_weapon, left_weapon = creature.get_weapon_models(
                utc,
                self._installation,
                appearance=appearance_2da,
                baseitems=baseitems_2da,
            )
            if right_weapon:
                info_lines.append(f"Right Weapon: '{right_weapon}'")
                weapon_mdl = self._installation.resource(right_weapon, ResourceType.MDL)
                if weapon_mdl:
                    try:
                        mdl_path = weapon_mdl.filepath.relative_to(self._installation.path())
                        info_lines.append(f"  MDL: {mdl_path}")
                    except ValueError:
                        info_lines.append(f"  MDL: {weapon_mdl.filepath}")
            if left_weapon:
                info_lines.append(f"Left Weapon: '{left_weapon}'")
                weapon_mdl = self._installation.resource(left_weapon, ResourceType.MDL)
                if weapon_mdl:
                    try:
                        mdl_path = weapon_mdl.filepath.relative_to(self._installation.path())
                        info_lines.append(f"  MDL: {mdl_path}")
                    except ValueError:
                        info_lines.append(f"  MDL: {weapon_mdl.filepath}")

            # Get mask model if equipped
            mask_model = creature.get_mask_model(utc, self._installation)
            if mask_model:
                info_lines.append(f"Mask Model: '{mask_model}'")
                mask_mdl = self._installation.resource(mask_model, ResourceType.MDL)
                if mask_mdl:
                    try:
                        mdl_path = mask_mdl.filepath.relative_to(self._installation.path())
                        info_lines.append(f"  MDL: {mdl_path}")
                    except ValueError:
                        info_lines.append(f"  MDL: {mask_mdl.filepath}")

            if not info_lines:
                info_lines.append("No model information available")

            # Add placeholder for textures - actual renderer textures will be populated when they finish loading
            info_lines.append("")
            info_lines.append("Renderer Textures: Loading...")

        except Exception as e:  # noqa: BLE001
            info_lines.append(f"Error gathering model info: {e}")

        full_text = "\n".join(info_lines)
        self.ui.modelInfoLabel.setText(full_text)

        # Update summary (first line or key info)
        summary = info_lines[0] if info_lines else "No model information"
        if body_model:
            summary = f"Body: {body_model}"
            if body_texture:
                summary += f" | Texture: {body_texture}"
        self.ui.modelInfoSummaryLabel.setText(summary)

    def _on_model_info_toggled(self, checked: bool):
        """Handle model info groupbox toggle."""
        self.ui.modelInfoLabel.setVisible(checked)
        if not checked:
            # When collapsed, ensure summary is visible
            self.ui.modelInfoSummaryLabel.setVisible(True)

    def _format_search_order(self, search_order: list[SearchLocation]) -> str:
        """Format search order list into human-readable string."""
        location_names = {
            SearchLocation.OVERRIDE: "Override",
            SearchLocation.CUSTOM_MODULES: "Custom Modules",
            SearchLocation.MODULES: "Modules",
            SearchLocation.CHITIN: "Chitin BIFs",
            SearchLocation.TEXTURES_TPA: "Texture Pack A",
            SearchLocation.TEXTURES_TPB: "Texture Pack B",
            SearchLocation.TEXTURES_TPC: "Texture Pack C",
            SearchLocation.TEXTURES_GUI: "GUI Textures",
        }
        return " → ".join(location_names.get(loc, str(loc)) for loc in search_order)

    def _on_textures_loaded(self):
        """Called when renderer signals that textures have finished loading.

        Reads the EXACT lookup info from scene.texture_lookup_info - this is the
        SAME info that the renderer used when loading textures. No additional lookups.
        """
        import os

        scene = self.ui.previewRenderer._scene
        if scene is None:
            return

        # Get the EXACT lookup info stored by the renderer when it loaded textures
        texture_lookup_info = getattr(scene, "texture_lookup_info", {})

        if not texture_lookup_info:
            RobustLogger().debug("_on_textures_loaded: No texture_lookup_info available yet")
            return

        RobustLogger().debug(f"_on_textures_loaded: Found {len(texture_lookup_info)} textures with lookup info")

        # Get current model info text and update the texture section
        current_text = self.ui.modelInfoLabel.text()

        # Find and replace the "Renderer Textures: Loading..." line
        lines = current_text.split("\n")
        new_lines: list[str] = []
        skip_old_texture_section = False

        for line in lines:
            if "Renderer Textures:" in line:
                skip_old_texture_section = True
                # Add new texture section
                new_lines.append("")
                new_lines.append(f"Renderer Textures ({len(texture_lookup_info)} loaded):")

                for tex_name, lookup_info in sorted(texture_lookup_info.items()):
                    restype = lookup_info.get("restype") or ""
                    if lookup_info.get("found"):
                        filepath = lookup_info.get("filepath")
                        source_location = lookup_info.get("source_location")
                        if filepath:
                            try:
                                if self._installation:
                                    rel_path = os.path.relpath(filepath, self._installation.path())
                                else:
                                    rel_path = str(filepath)
                                if restype:
                                    new_lines.append(f"  {tex_name} ({restype}): {rel_path}")
                                else:
                                    new_lines.append(f"  {tex_name}: {rel_path}")
                            except (ValueError, AttributeError):
                                if restype:
                                    new_lines.append(f"  {tex_name} ({restype}): {filepath}")
                                else:
                                    new_lines.append(f"  {tex_name}: {filepath}")

                            # Prefer the exact SearchLocation recorded by the renderer (no extra lookups).
                            if source_location is not None:
                                try:
                                    new_lines.append(f"    └─ SearchLocation: {self._format_search_order([source_location])}")
                                except Exception:  # noqa: BLE001
                                    new_lines.append(f"    └─ SearchLocation: {source_location}")
                            else:
                                source = self._get_source_location_type(filepath)
                                if source:
                                    new_lines.append(f"    └─ Source: {source}")
                        else:
                            if restype:
                                new_lines.append(f"  {tex_name} ({restype}): ✓ Loaded")
                            else:
                                new_lines.append(f"  {tex_name}: ✓ Loaded")
                    else:
                        search_order = lookup_info.get("search_order", [])
                        search_str = self._format_search_order(search_order) if search_order else "Unknown"
                        if restype:
                            new_lines.append(f"  {tex_name} ({restype}): ❌ Not found")
                        else:
                            new_lines.append(f"  {tex_name}: ❌ Not found")
                        new_lines.append(f"    └─ Searched: {search_str}")
            elif skip_old_texture_section and line.startswith("  "):
                # Skip old texture lines (indented)
                continue
            elif skip_old_texture_section and not line.startswith("  ") and line.strip():
                # End of old texture section
                skip_old_texture_section = False
                new_lines.append(line)
            elif not skip_old_texture_section:
                new_lines.append(line)

        self.ui.modelInfoLabel.setText("\n".join(new_lines))

    def _get_source_location_type(self, filepath: os.PathLike | str) -> str | None:
        """Determines the source location type for a given filepath.

        Args:
        ----
            filepath: The filepath to analyze

        Returns:
        -------
            A string describing the source location type, or None if unknown
        """
        if self._installation is None:
            return None

        try:
            from pathlib import Path

            path = self._installation.path()
            filepath_obj = Path(filepath) if not isinstance(filepath, Path) else filepath
            rel_path = filepath_obj.relative_to(path)
            path_str = str(rel_path).lower().replace("\\", "/")
            if "override" in path_str:
                return "Override folder"
            if path_str.startswith("modules/"):
                if path_str.endswith(".mod"):
                    return "Module (.mod)"
                if path_str.endswith(".rim"):
                    return "Module (.rim)"
                return "Module"
            if "chitin.key" in path_str or "data" in path_str:
                return "Chitin BIFs"
            if "textures" in path_str:
                return "Texture pack"
        except (ValueError, AttributeError):
            pass
        return None


class UTCSettings:
    def __init__(self):
        self.settings = QSettings(get_qsettings_organization("HolocronToolsetV4"), "UTCEditor")

    @property
    def saveUnusedFields(self) -> bool:
        return self.settings.value("saveUnusedFields", True, bool)

    @saveUnusedFields.setter
    def saveUnusedFields(self, value: bool):
        self.settings.setValue("saveUnusedFields", value)

    @property
    def alwaysSaveK2Fields(self) -> bool:
        return self.settings.value("alwaysSaveK2Fields", False, bool)

    @alwaysSaveK2Fields.setter
    def alwaysSaveK2Fields(self, value: bool):
        self.settings.setValue("alwaysSaveK2Fields", value)

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("utc"))
