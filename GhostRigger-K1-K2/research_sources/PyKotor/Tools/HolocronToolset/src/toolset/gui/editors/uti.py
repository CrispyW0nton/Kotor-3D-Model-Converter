"""UTI (item) editor: properties, portrait/icon picker, and load-from-location."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Sequence

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAction,  # pyright: ignore[reportPrivateImportUsage]
    QApplication,
    QDialog,
    QListWidgetItem,
    QMenu,
    QShortcut,  # pyright: ignore[reportPrivateImportUsage]
    QTreeWidgetItem,
)

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs]
from pykotor.common.misc import ResRef
from pykotor.extract.file import LocationResult
from pykotor.extract.installation import SearchLocation
from pykotor.resource.formats.gff import write_gff
from pykotor.resource.formats.twoda.twoda_data import TwoDA
from pykotor.resource.generics.uti import UTI, UTIProperty, dismantle_uti, read_uti
from pykotor.resource.type import ResourceType
from toolset.data.installation import HTInstallation
from toolset.gui.common.localization import translate as tr, translate_with_format as trf
from toolset.gui.dialogs.edit.locstring import LocalizedStringDialog
from toolset.gui.dialogs.load_from_location_result import FileSelectionWindow, ResourceItems
from toolset.gui.editor import Editor
from toolset.gui.widgets.settings.installations import GlobalSettings
from toolset.utils.window import add_window

if TYPE_CHECKING:
    import os

    from qtpy.QtCore import QModelIndex, QPoint
    from qtpy.QtGui import QClipboard, QPixmap
    from qtpy.QtWidgets import QWidget
    from typing_extensions import Literal  # pyright: ignore[reportMissingModuleSource]

    from pykotor.common.module import GFF
    from pykotor.extract.file import FileResource, LocationResult, ResourceIdentifier, ResourceResult
    from pykotor.extract.twoda import TwoDARow
    from pykotor.resource.formats.twoda.twoda_data import TwoDA


class UTIEditor(Editor):
    def __init__(
        self,
        parent: QWidget | None,
        installation: HTInstallation | None = None,
    ):
        """Initializes the Item Editor window.

        Args:
        ----
            parent: {QWidget}: The parent widget
            installation: {HTInstallation}: The KOTOR installation.
        """
        supported: list[ResourceType] = [ResourceType.UTI]
        super().__init__(parent, "Item Editor", "item", supported, supported, installation)

        self._uti = UTI()
        self.globalSettings: GlobalSettings = GlobalSettings()

        from toolset.uic.qtpy.editors.uti import Ui_MainWindow

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setup_menus()
        self._add_help_action()
        self._setup_signals()
        self._installation: HTInstallation

        self._setup_installation(installation)
        self.ui.descEdit.set_installation(installation)

        self.setMinimumSize(700, 350)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        QShortcut("Del", self).activated.connect(self.on_del_shortcut)

        self.ui.iconLabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # pyright: ignore[reportArgumentType]
        self.ui.iconLabel.customContextMenuRequested.connect(self._icon_label_context_menu)

        # Initialize model info widget state (collapsed by default)
        self.ui.itemModelInfoLabel.setVisible(False)
        self.ui.itemModelInfoSummaryLabel.setVisible(True)

        # Setup reference search for Tag field (append to .ui tooltip)
        if installation is not None:
            for widget, resource_types, reference_type, tooltip_suffix in self._reference_field_specs():
                self._setup_reference_field(widget, resource_types, reference_type, tooltip_suffix)

        self.update3dPreview()
        self.new()

    def _on_installation_changed(self, installation: HTInstallation | None) -> None:
        if installation is None:
            return
        self._setup_installation(installation)
        self.update3dPreview()

    def _setup_reference_field(
        self,
        widget,
        resource_types: list[ResourceType],
        reference_type: str,
        tooltip_suffix: str,
    ) -> None:
        """Configure context-menu reference search and append helper tooltip text."""
        assert self._installation is not None
        self._installation.setup_file_context_menu(
            widget,
            resource_types,
            enable_reference_search=True,
            reference_search_type=reference_type,
        )
        tooltip = widget.toolTip() or ""
        widget.setToolTip(f"{tooltip} {tooltip_suffix}".strip())

    def _reference_field_specs(self) -> list[tuple[object, list[ResourceType], str, str]]:
        """Return common reference-search field configuration for this editor."""
        return [
            (
                self.ui.tagEdit,
                [],
                "tag",
                tr("Right-click to find references to this tag in the installation."),
            ),
            (
                self.ui.resrefEdit,
                [],
                "template_resref",
                tr("Right-click to find references to this template resref in the installation."),
            ),
        ]

    @staticmethod
    def _connect_signals(signals: Sequence[object], *handlers: object) -> None:
        """Connect each signal in `signals` to each handler in `handlers`."""
        for signal in signals:
            for handler in handlers:
                signal.connect(handler)

    def _setup_signals(self):
        """Set up signal connections for UI elements."""
        signal_connections = [
            (self.ui.tagGenerateButton.clicked, self.generate_tag),
            (self.ui.resrefGenerateButton.clicked, self.generate_resref),
            (self.ui.editPropertyButton.clicked, self.edit_selected_property),
            (self.ui.removePropertyButton.clicked, self.remove_selected_property),
            (self.ui.addPropertyButton.clicked, self.add_selected_property),
            (self.ui.availablePropertyList.doubleClicked, self.on_available_property_list_double_clicked),
            (self.ui.assignedPropertiesList.doubleClicked, self.on_assigned_property_list_double_clicked),
            (self.ui.previewRenderer.resourcesLoaded, self._on_textures_loaded),
        ]
        for signal, handler in signal_connections:
            signal.connect(handler)

        update_signals = (
            self.ui.modelVarSpin.valueChanged,
            self.ui.bodyVarSpin.valueChanged,
            self.ui.textureVarSpin.valueChanged,
            self.ui.baseSelect.currentIndexChanged,
        )
        self._connect_signals(update_signals, self.on_update_icon, self.update3dPreview)

    def _load_basic_fields(self, uti: UTI):
        self.ui.nameEdit.set_locstring(uti.name)
        self.ui.descEdit.set_locstring(uti.description)
        self.ui.tagEdit.setText(uti.tag)
        self.ui.resrefEdit.setText(str(uti.resref))
        self.ui.baseSelect.setCurrentIndex(uti.base_item)
        self.ui.costSpin.setValue(uti.cost)
        self.ui.additionalCostSpin.setValue(uti.add_cost)
        self.ui.upgradeSpin.setValue(uti.upgrade_level)
        self.ui.plotCheckbox.setChecked(bool(uti.plot))
        self.ui.chargesSpin.setValue(uti.charges)
        self.ui.stackSpin.setValue(uti.stack_size)
        self.ui.modelVarSpin.setValue(uti.model_variation)
        self.ui.bodyVarSpin.setValue(uti.body_variation)
        self.ui.textureVarSpin.setValue(uti.texture_variation)

    def _save_basic_fields(self, uti: UTI):
        uti.name = self.ui.nameEdit.locstring()
        uti.description = self.ui.descEdit.locstring()
        uti.tag = self.ui.tagEdit.text()
        uti.resref = ResRef(self.ui.resrefEdit.text())
        uti.base_item = self.ui.baseSelect.currentIndex()
        uti.cost = self.ui.costSpin.value()
        uti.add_cost = self.ui.additionalCostSpin.value()
        uti.upgrade_level = self.ui.upgradeSpin.value()
        uti.plot = self.ui.plotCheckbox.isChecked()
        uti.charges = self.ui.chargesSpin.value()
        uti.stack_size = self.ui.stackSpin.value()
        uti.model_variation = self.ui.modelVarSpin.value()
        uti.body_variation = self.ui.bodyVarSpin.value()
        uti.texture_variation = self.ui.textureVarSpin.value()

    def _load_assigned_properties(self, uti: UTI):
        self.ui.assignedPropertiesList.clear()
        for uti_property in uti.properties:
            text = self.property_summary(uti_property)
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, uti_property)
            self.ui.assignedPropertiesList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

    def _save_assigned_properties(self, uti: UTI):
        uti.properties.clear()
        for i in range(self.ui.assignedPropertiesList.count()):
            item: QListWidgetItem | None = self.ui.assignedPropertiesList.item(i)
            if item is None:
                RobustLogger().warning(f"Failed to retrieve property item at index {i} from assigned properties list. Skipping...")
                continue
            uti.properties.append(item.data(Qt.ItemDataRole.UserRole))

    def _setup_installation(
        self,
        installation: HTInstallation,
    ):
        self._installation = installation  # pyright: ignore[reportIncompatibleVariableOverride]
        self.ui.nameEdit.set_installation(installation)
        self.ui.descEdit.set_installation(installation)

        required: list[str] = [HTInstallation.TwoDA_BASEITEMS, HTInstallation.TwoDA_ITEM_PROPERTIES]
        installation.ht_batch_cache_2da(required)

        baseitems: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_BASEITEMS)
        item_properties: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_ITEM_PROPERTIES)
        self.ui.baseSelect.clear()
        if baseitems is None:
            RobustLogger().error("Failed to retrieve BASEITEMS 2DA.")
        else:
            self.ui.baseSelect.set_items(baseitems.get_column("label"))
            self.ui.baseSelect.set_context(baseitems, installation, HTInstallation.TwoDA_BASEITEMS)

        self.ui.availablePropertyList.clear()
        if item_properties is not None:
            for i in range(item_properties.get_height()):
                prop_name: str = UTIEditor.property_name(installation, i)
                item = QTreeWidgetItem([prop_name])
                self.ui.availablePropertyList.addTopLevelItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

                subtype_resname: str = item_properties.get_cell(i, "subtyperesref")
                if not subtype_resname:
                    item.setData(0, Qt.ItemDataRole.UserRole, i)
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, i)
                    continue

                subtype: TwoDA | None = installation.ht_get_cache_2da(subtype_resname)
                if subtype is None:
                    RobustLogger().warning(f"Failed to retrieve subtype '{subtype_resname}' for property name '{prop_name}' at index {i}. Skipping...")
                    continue

                for j in range(subtype.get_height()):
                    if subtype_resname == "spells":
                        print("   ", j)
                    name: None | str = UTIEditor.subproperty_name(installation, i, j)
                    if not name or not name.strip():  # possible HACK: this fixes a bug where there'd be a bunch of blank entries.
                        continue
                    child = QTreeWidgetItem([name])
                    child.setData(0, Qt.ItemDataRole.UserRole, i)
                    child.setData(0, Qt.ItemDataRole.UserRole + 1, j)
                    item.addChild(child)

    def load(
        self,
        filepath: os.PathLike | str,
        resref: str,
        restype: ResourceType,
        data: bytes | bytearray,
    ):
        """Load resource and populate UI from UTI. Defaults from construct_uti (K1 LoadDataFromGff 0x0055fcd0, LoadItem 0x00560970; TSL TODO)."""
        super().load(filepath, resref, restype, data)

        uti = read_uti(data)
        self._loadUTI(uti)

    def _loadUTI(self, uti: UTI):
        """Loads UTI data into UI. Defaults from construct_uti; K1 LoadDataFromGff 0x0055fcd0, LoadItem 0x00560970; TSL same (addresses TODO)."""
        self._uti: UTI = uti

        # Basic
        self._load_basic_fields(uti)

        # Properties
        self._load_assigned_properties(uti)

        # Comments
        self.ui.commentsEdit.setPlainText(uti.comment)

    def build(self) -> tuple[bytes, bytes]:
        """Builds UTI from UI. Populates from UI then dismantle_uti (K1 LoadDataFromGff 0x0055fcd0, LoadItem 0x00560970; TSL TODO). Returns GFF bytes and log."""
        uti: UTI = deepcopy(self._uti)

        # Basic
        self._save_basic_fields(uti)
        self._save_assigned_properties(uti)

        # Comments
        uti.comment = self.ui.commentsEdit.toPlainText()

        data = bytearray()
        gff: GFF = dismantle_uti(uti)
        write_gff(gff, data)

        return data, b""

    def new(self):
        super().new()
        self._loadUTI(UTI())

    def change_name(self):
        dialog = LocalizedStringDialog(self, self._installation, self.ui.nameEdit.locstring())
        if not dialog.exec():
            return
        self._load_locstring(self.ui.nameEdit.ui.locstringText, dialog.locstring)  # pyright: ignore[reportArgumentType]

    def change_desc(self):
        dialog = LocalizedStringDialog(self, self._installation, self.ui.descEdit.locstring())
        if not dialog.exec():
            return
        self._load_locstring(self.ui.descEdit.ui.locstringText, dialog.locstring)  # pyright: ignore[reportArgumentType]

    def generate_tag(self):
        resref_text = self.ui.resrefEdit.text()
        if not resref_text or not resref_text.strip():
            self.generate_resref()
        self.ui.tagEdit.setText(self.ui.resrefEdit.text())

    def generate_resref(self):
        if self._resname and self._resname.strip():
            self.ui.resrefEdit.setText(self._resname)
        else:
            self.ui.resrefEdit.setText("m00xx_itm_000")

    def edit_selected_property(self):
        if not self.ui.assignedPropertiesList.selectedItems():
            return
        uti_property: UTIProperty = self.ui.assignedPropertiesList.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        dialog = PropertyEditor(self._installation, uti_property)
        if not dialog.exec():
            return
        self.ui.assignedPropertiesList.selectedItems()[0].setData(Qt.ItemDataRole.UserRole, dialog.uti_property())
        self.ui.assignedPropertiesList.selectedItems()[0].setText(self.property_summary(dialog.uti_property()))

    def add_selected_property(self):
        if not self.ui.availablePropertyList.selectedItems():
            return
        item: QTreeWidgetItem = self.ui.availablePropertyList.selectedItems()[0]
        property_id: int = item.data(0, Qt.ItemDataRole.UserRole)
        if property_id is None:
            return
        subtype_id: int = item.data(0, Qt.ItemDataRole.UserRole + 1)
        self._add_property_main(property_id, subtype_id)

    def _add_property_main(
        self,
        property_id: int,
        subtype_id: int,
    ):
        itemprops: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_ITEM_PROPERTIES)
        if itemprops is None:
            return

        uti_property = UTIProperty()
        uti_property.property_name = property_id
        uti_property.subtype = subtype_id
        uti_property.cost_table = itemprops.get_row(property_id).get_integer("costtableresref", 255)
        uti_property.cost_value = 0
        uti_property.param1 = itemprops.get_row(property_id).get_integer("param1resref", 255)
        uti_property.param1_value = 0
        uti_property.chance_appear = 100

        text: str = self.property_summary(uti_property)
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, uti_property)
        self.ui.assignedPropertiesList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

    def remove_selected_property(self):
        if not self.ui.assignedPropertiesList.selectedItems():
            return
        index: QModelIndex = self.ui.assignedPropertiesList.selectedIndexes()[0]
        self.ui.assignedPropertiesList.takeItem(index.row())

    def property_summary(
        self,
        uti_property: UTIProperty,
    ) -> str:  # sourcery skip: assign-if-exp, reintroduce-else
        """Retrieve the property, subproperty and cost names from the UTIEditor.

        Processing Logic:
        ----------------
            - It returns a formatted string combining the retrieved names.
            - If a cost or subproperty is not present, it is omitted from the returned string.
        """
        prop_name: str = UTIEditor.property_name(self._installation, uti_property.property_name)
        subprop_name: str | None = UTIEditor.subproperty_name(self._installation, uti_property.property_name, uti_property.subtype)
        cost_name: str | None = UTIEditor.cost_name(self._installation, uti_property.cost_table, uti_property.cost_value)

        if cost_name and subprop_name:
            return f"{prop_name}: {subprop_name} [{cost_name}]"
        if subprop_name:
            return f"{prop_name}: {subprop_name}"
        if cost_name:
            return f"{prop_name}: [{cost_name}]"
        return f"{prop_name}"

    def _generate_icon_tooltip(
        self,
        *,
        as_html: bool = False,
    ) -> str:  # sourcery skip: lift-return-into-if
        """Generates a detailed tooltip for the iconLabel."""
        base_item: int = self.ui.baseSelect.currentIndex()
        model_variation: int = self.ui.modelVarSpin.value()
        texture_variation: int = self.ui.textureVarSpin.value()

        assert self._installation is not None
        base_item_name: str = self._installation.get_item_base_name(base_item)
        model_var_name: str = self._installation.get_model_var_name(model_variation)
        texture_var_name: str = self._installation.get_texture_var_name(texture_variation)
        icon_path: str = self._installation.get_item_icon_path(base_item, model_variation, texture_variation)

        if as_html:
            tooltip = (
                f"<b>Base Item:</b> {base_item_name} (ID: {base_item})<br>"
                f"<b>Model Variation:</b> {model_var_name} (ID: {model_variation})<br>"
                f"<b>Texture Variation:</b> {texture_var_name} (ID: {texture_variation})<br>"
                f"<b>Icon Name:</b> {icon_path}"
            )
        else:
            tooltip = (
                f"Base Item: {base_item_name} (ID: {base_item})\n"
                f"Model Variation: {model_var_name} (ID: {model_variation})\n"
                f"Texture Variation: {texture_var_name} (ID: {texture_variation})\n"
                f"Icon Name: {icon_path}"
            )
        return tooltip

    def _icon_label_context_menu(
        self,
        position: QPoint,
    ):
        context_menu = QMenu(self)
        copy_menu = QMenu("Copy..")

        base_item: int = self.ui.baseSelect.currentIndex()
        model_variation: int = self.ui.modelVarSpin.value()
        texture_variation: int = self.ui.textureVarSpin.value()
        icon_path: str = self._installation.get_item_icon_path(base_item, model_variation, texture_variation)

        summary_item_icon_action = QAction(tr("Icon Summary"), self)
        summary_item_icon_action.triggered.connect(self._copy_icon_tooltip)
        copy_menu.addAction(summary_item_icon_action)
        copy_menu.addSeparator()

        copy_actions: list[tuple[str, str]] = [
            (trf("Base Item: {base_item}", base_item=base_item), f"{base_item}"),
            (trf("Model Variation: {model_variation}", model_variation=model_variation), f"{model_variation}"),
            (trf("Texture Variation: {texture_variation}", texture_variation=texture_variation), f"{texture_variation}"),
            (trf("Icon Name: '{icon_path}'", icon_path=icon_path), f"{icon_path}"),
        ]
        for action_text, clipboard_value in copy_actions:
            action = QAction(action_text, self)
            action.triggered.connect(lambda _checked=False, value=clipboard_value: self._copy_to_clipboard(value))
            copy_menu.addAction(action)

        file_menu = context_menu.addMenu("File...")
        assert file_menu is not None
        locations: dict[ResourceIdentifier, list[LocationResult]] = self._installation.locations(
            ([icon_path], [ResourceType.TGA, ResourceType.TPC]),
            order=[SearchLocation.OVERRIDE, SearchLocation.TEXTURES_GUI, SearchLocation.TEXTURES_TPA, SearchLocation.TEXTURES_TPB, SearchLocation.TEXTURES_TPC, SearchLocation.CHITIN],
        )
        flat_locations: list[LocationResult] = [item for sublist in locations.values() for item in sublist]
        if flat_locations:
            for location in flat_locations:
                display_path_str = str(location.filepath.relative_to(self._installation.path()))
                loc_menu = file_menu.addMenu(display_path_str)
                resource_menu_builder = ResourceItems(resources=[location])
                resource_menu_builder.build_menu(loc_menu)

            file_menu.addAction("Details...").triggered.connect(lambda: self._open_details(flat_locations))

        context_menu.addMenu(copy_menu)
        icon_label = self.ui.iconLabel
        target = icon_label if icon_label is not None else self
        context_menu.exec(target.mapToGlobal(position))  # pyright: ignore[reportArgumentType]

    def _open_details(
        self,
        locations: Sequence[FileResource | ResourceResult | LocationResult],
    ):
        selection_window: FileSelectionWindow = FileSelectionWindow(locations, self._installation)
        selection_window.show()
        selection_window.activateWindow()
        add_window(selection_window)

    def _copy_icon_tooltip(self):
        tooltip_text: str = self._generate_icon_tooltip(as_html=False)
        self._copy_to_clipboard(tooltip_text)

    def _copy_to_clipboard(
        self,
        text: str,
    ):
        clipboard: QClipboard | None = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def on_update_icon(self, *args, **kwargs):
        base_item: int = self.ui.baseSelect.currentIndex()
        model_variation: int = self.ui.modelVarSpin.value()
        texture_variation: int = self.ui.textureVarSpin.value()
        pixmap: QPixmap | None = self._installation.get_item_icon(base_item, model_variation, texture_variation)
        icon_label = self.ui.iconLabel
        if pixmap is not None:
            icon_label.setPixmap(pixmap)  # pyright: ignore[reportArgumentType]
            # Update the tooltip whenever the icon changes
            icon_label.setToolTip(self._generate_icon_tooltip(as_html=True))

    def update3dPreview(self):
        """Updates the 3D preview and model info.

        Hides BOTH the preview renderer AND the model info groupbox when preview is hidden.
        """
        show_preview = self.globalSettings.showPreviewUTI
        self.ui.previewRenderer.setVisible(show_preview)
        self.ui.itemModelInfoGroupBox.setVisible(show_preview)

        if show_preview:
            self.resize(max(800, self.sizeHint().width()), max(400, self.sizeHint().height()))

            if self._installation is not None:
                # Build item data and set it on the renderer (if it supports set_item, e.g. ItemRenderer)
                data, _ = self.build()
                uti: UTI = read_uti(data)
                self.ui.previewRenderer.set_item(uti)
                self._update_model_info(uti)
        else:
            self.resize(max(800 - 200, self.sizeHint().width()), max(400, self.sizeHint().height()))

    def _update_model_info(self, uti: UTI):
        """Updates the model information label with item model details.

        Args:
        ----
            uti: The UTI object to analyze
        """
        if self._installation is None:
            return

        info_lines: list[str] = []

        try:
            # Get the base item data to find the model path
            baseitems: TwoDA | None = self._installation.ht_get_cache_2da(HTInstallation.TwoDA_BASEITEMS)
            if baseitems is None or uti.base_item >= baseitems.get_height():
                info_lines.append("Model: Unknown (invalid base item)")
            else:
                model_type: int = baseitems.get_row(uti.base_item).get_integer("ModelType") or 0
                model_name: str = baseitems.get_row(uti.base_item).get_string("ModelName") or "Unknown"
                info_lines.append(f"Model: {model_name} (type {model_type})")
                info_lines.append(f"Variation: {uti.model_variation}")

            # Basic summary
            summary = " | ".join(info_lines[:2]) if info_lines else "No model info available"
            self.ui.itemModelInfoSummaryLabel.setText(summary)

            # Detailed info
            detail = "\n".join(info_lines)
            self.ui.itemModelInfoLabel.setText(detail)
        except Exception as e:
            RobustLogger().error(f"Error updating item model info: {e}")
            self.ui.itemModelInfoSummaryLabel.setText("Error loading model info")
            self.ui.itemModelInfoLabel.setText(str(e))

    def toggle_preview(self):
        """Toggle the 3D preview visibility."""
        self.globalSettings.showPreviewUTI = not self.globalSettings.showPreviewUTI
        self.update3dPreview()

    def _on_textures_loaded(self):
        """Called when textures finish loading in the preview renderer."""
        # Optional: update model info with texture details if renderer has that info
        # For now, just log that textures loaded
        pass

    def on_available_property_list_double_clicked(self):
        for item in self.ui.availablePropertyList.selectedItems():
            if item.childCount() != 0:
                continue
            self.add_selected_property()

    def on_assigned_property_list_double_clicked(self):
        self.edit_selected_property()

    def on_del_shortcut(self):
        if not self.ui.assignedPropertiesList.hasFocus():
            return
        self.remove_selected_property()

    @staticmethod
    def property_name(
        installation: HTInstallation,
        prop: int,
    ) -> str:
        properties: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_ITEM_PROPERTIES)
        if properties is None:
            RobustLogger().error("Failed to retrieve ITEM_PROPERTIES 2DA.")
            return "Unknown"
        stringref: int | None = properties.get_row(prop).get_integer("name")
        if stringref is None:
            RobustLogger().error(f"Failed to retrieve name stringref for property {prop}.")
            return "Unknown"
        return installation.talktable().string(stringref)

    @staticmethod
    def subproperty_name(
        installation: HTInstallation,
        prop: int,
        subprop: int,
    ) -> None | str:
        properties: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_ITEM_PROPERTIES)
        if properties is None:
            RobustLogger().error("Failed to retrieve ITEM_PROPERTIES 2DA.")
            return None
        subtype_resname: str | None = properties.get_cell(prop, "subtyperesref")
        if not subtype_resname:
            RobustLogger().error(f"Failed to retrieve subtype_resname for property {prop}.")
            return None
        subproperties: TwoDA | None = installation.ht_get_cache_2da(subtype_resname)
        if subproperties is None:
            return None
        header_strref: Literal["name", "string_ref"] = "name" if "name" in subproperties.get_headers() else "string_ref"
        name_strref: int | None = subproperties.get_row(subprop).get_integer(header_strref)
        return subproperties.get_cell(subprop, "label") if name_strref is None else installation.talktable().string(name_strref)

    @staticmethod
    def cost_name(
        installation: HTInstallation,
        cost: int,
        value: int,
    ) -> str | None:
        cost_table_list: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_IPRP_COSTTABLE)
        if cost_table_list is None:
            RobustLogger().error("Failed to retrieve IPRP_COSTTABLE 2DA.")
            return None

        costtable_name: str | None = cost_table_list.get_cell(cost, "name")
        if costtable_name is None:
            RobustLogger().error(f"Failed to retrieve costtable 'name' for cost '{cost}'.")
            return None

        costtable: TwoDA | None = installation.ht_get_cache_2da(costtable_name)
        if costtable is None:
            RobustLogger().error(f"Failed to retrieve '{costtable_name}' 2DA.")
            return None

        try:
            stringref: int | None = costtable.get_row(value).get_integer("name")
            if stringref is not None:
                return installation.talktable().string(stringref)
        except (IndexError, Exception):  # noqa: BLE001
            RobustLogger().warning("Could not get the costtable 2DA row/value", exc_info=True)
        return None

    @staticmethod
    def param_name(
        installation: HTInstallation,
        paramtable: int,
        param: int,
    ) -> str | None:
        RobustLogger().info(f"Attempting to get param name for paramtable: {paramtable}, param: {param}")

        # Get the IPRP_PARAMTABLE 2DA
        paramtable_list: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_IPRP_PARAMTABLE)
        paramtable_2da: TwoDA | None = None
        if paramtable_list is None:
            RobustLogger().error("Failed to retrieve IPRP_PARAMTABLE 2DA.")
            return None

        try:
            # Get the specific parameter table 2DA
            table_resref: str | None = paramtable_list.get_cell(paramtable, "tableresref")
            if table_resref is None:
                RobustLogger().error(f"Failed to retrieve table_resref for paramtable: '{paramtable}'.")
                return None
            RobustLogger().info(f"Retrieved table_resref: '{table_resref}' for paramtable: '{paramtable}'")

            paramtable_2da = installation.ht_get_cache_2da(table_resref)
            if paramtable_2da is None:
                RobustLogger().error(f"Failed to retrieve 2DA file: {table_resref}.")
                return None

            # Get the string reference for the parameter name
            param_row: TwoDARow = paramtable_2da.get_row(param)
            stringref: int | None = param_row.get_integer("name")
            if stringref is None:
                RobustLogger().warning(f"Failed to get 'name' value for param '{param}' in '{table_resref}'")
                RobustLogger().info(f"Available columns in '{table_resref}': '{paramtable_2da.get_headers()}'")
                RobustLogger().info(f"Row data for param '{param}': '{param_row._data}'")  # noqa: SLF001
                return None

            # Get the actual string from the talk table
            result: str = installation.talktable().string(stringref)
            RobustLogger().info(f"Retrieved param name: {result} for stringref: {stringref}")
            return result  # noqa: TRY300

        except IndexError:
            RobustLogger().exception(f"paramtable: {paramtable}, param: {param}")
            RobustLogger().info(f"IPRP_PARAMTABLE height: {paramtable_list.get_height()}, width: {paramtable_list.get_width()}")
            RobustLogger().info(f"Available rows in IPRP_PARAMTABLE: {paramtable_list.get_labels()}")
        except KeyError:
            RobustLogger().exception("Likely missing column in 2DA.")
            if "paramtable_2da" in locals() and paramtable_2da is not None:
                RobustLogger().info(f"Available columns in '{table_resref}': {paramtable_2da.get_headers()}")
        except Exception:  # noqa: BLE001
            RobustLogger().exception("Unexpected error in param_name", exc_info=True)

        return None


class PropertyEditor(QDialog):
    def __init__(
        self,
        installation: HTInstallation,
        uti_property: UTIProperty,
    ):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint & ~Qt.WindowType.WindowContextHelpButtonHint & ~Qt.WindowType.WindowMinimizeButtonHint
        )

        from toolset.uic.qtpy.dialogs.property import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

        self.ui.costSelectButton.clicked.connect(self.select_cost)
        self.ui.parameterSelectButton.clicked.connect(self.select_param)
        self.ui.costList.doubleClicked.connect(self.select_cost)
        self.ui.parameterList.doubleClicked.connect(self.select_param)

        self._installation: HTInstallation = installation
        self._uti_property: UTIProperty = uti_property

        cost_table_list: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_IPRP_COSTTABLE)  # noqa: F841
        if cost_table_list is None:
            RobustLogger().warning("Failed to get IPRP_COSTTABLE")
            return
        if uti_property.cost_table != 0xFF:  # noqa: PLR2004
            costtable_resref: str | None = cost_table_list.get_cell(uti_property.cost_table, "name")
            if costtable_resref is None:
                RobustLogger().warning(f"Failed to get costtable for name: {costtable_resref}")
                return
            costtable: TwoDA | None = installation.ht_get_cache_2da(costtable_resref)
            if costtable is None:
                RobustLogger().warning(f"Failed to get costtable for resref: {costtable_resref}")
                return
            for i in range(costtable.get_height()):
                cost_name: str | None = UTIEditor.cost_name(installation, uti_property.cost_table, i)
                if cost_name is None:
                    RobustLogger().warning(f"No cost_name at index {i}")
                item = QListWidgetItem(cost_name)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.ui.costList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

        if uti_property.param1 != 0xFF:  # noqa: PLR2004
            param_list: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_IPRP_PARAMTABLE)
            if param_list is None:
                RobustLogger().warning("Failed to get IPRP_PARAMTABLE")
                return

            paramtable_resref: str | None = param_list.get_cell(uti_property.param1, "tableresref")
            if paramtable_resref is None:
                RobustLogger().warning(f"No tableresref found for param1: {uti_property.param1}")
                return

            paramtable: TwoDA | None = installation.ht_get_cache_2da(paramtable_resref)
            if paramtable is None:
                RobustLogger().warning(f"Failed to get paramtable for resref: {paramtable_resref}")
                return

            for i in range(paramtable.get_height()):
                param_name: str | None = UTIEditor.param_name(installation, uti_property.param1, i)
                if param_name is None:
                    RobustLogger().warning(f"No param_name at index {i}")
                item = QListWidgetItem(param_name)
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.ui.parameterList.addItem(item)  # pyright: ignore[reportArgumentType, reportCallIssue]

        upgrades: TwoDA | None = installation.ht_get_cache_2da(HTInstallation.TwoDA_UPGRADES)
        if upgrades is not None:
            upgrade_items: list[str] = [upgrades.get_cell(i, "label").replace("_", " ").title() for i in range(upgrades.get_height())]
        else:
            upgrade_items = []

        self.ui.upgradeSelect.set_items(upgrade_items, cleanup_strings=False)
        self.ui.upgradeSelect.set_context(upgrades, installation, HTInstallation.TwoDA_UPGRADES)
        if uti_property.upgrade_type is not None:
            self.ui.upgradeSelect.setCurrentIndex(uti_property.upgrade_type + 1)

        self.reload_textboxes()

    def reload_textboxes(self):
        """Reloads textboxes with property names."""
        property_name: str = UTIEditor.property_name(self._installation, self._uti_property.property_name)
        self.ui.propertyEdit.setText(property_name or "")

        subproperty_name: str | None = UTIEditor.subproperty_name(self._installation, self._uti_property.property_name, self._uti_property.subtype)
        self.ui.subpropertyEdit.setText(subproperty_name or "")

        cost_name: str | None = UTIEditor.cost_name(self._installation, self._uti_property.cost_table, self._uti_property.cost_value)
        self.ui.costEdit.setText(cost_name or "")

        param_name: str | None = UTIEditor.param_name(self._installation, self._uti_property.param1, self._uti_property.param1_value)
        self.ui.parameterEdit.setText(param_name or "")

    def select_cost(self):
        cur_item: QListWidgetItem | None = self.ui.costList.currentItem()  # pyright: ignore[reportAssignmentType]
        if not cur_item:
            return

        self._uti_property.cost_value = cur_item.data(Qt.ItemDataRole.UserRole)
        self.reload_textboxes()

    def select_param(self):
        cur_item: QListWidgetItem | None = self.ui.parameterList.currentItem()  # pyright: ignore[reportAssignmentType]
        if not cur_item:
            return

        self._uti_property.param1_value = cur_item.data(Qt.ItemDataRole.UserRole)
        self.reload_textboxes()

    def uti_property(self) -> UTIProperty:
        self._uti_property.upgrade_type = self.ui.upgradeSelect.currentIndex() - 1
        if self.ui.upgradeSelect.currentIndex() == 0:
            self._uti_property.upgrade_type = None
        return self._uti_property

if __name__ == "__main__":
    import sys

    from toolset.gui.editors.standalone import launch_editor_cli

    sys.exit(launch_editor_cli("uti"))
