from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Mapping

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import QListWidgetItem

from utility.common.geometry import SurfaceMaterial

if TYPE_CHECKING:
    from qtpy.QtWidgets import QComboBox, QListWidget


@lru_cache(maxsize=128)
def _cached_material_pixmap(rgba: int, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor.fromRgba(rgba))
    return pixmap


def material_display_name(material: SurfaceMaterial) -> str:
    return material.name.replace("_", " ").title()


def material_icon(color: QColor, *, size: int = 16) -> QIcon:
    return QIcon(_cached_material_pixmap(color.rgba(), size))


def get_walkmesh_material_colors() -> dict[SurfaceMaterial, QColor]:
    """Returns a dict mapping SurfaceMaterial to configured UI colors."""
    from pykotor.common.misc import Color
    from toolset.gui.widgets.settings.widgets.module_designer import ModuleDesignerSettings

    settings = ModuleDesignerSettings()

    def int_to_qcolor(intvalue: int) -> QColor:
        color = Color.from_rgba_integer(intvalue)
        return QColor(int(color.r * 255), int(color.g * 255), int(color.b * 255), int(color.a * 255))

    return {
        SurfaceMaterial.UNDEFINED: int_to_qcolor(settings.undefinedMaterialColour),
        SurfaceMaterial.OBSCURING: int_to_qcolor(settings.obscuringMaterialColour),
        SurfaceMaterial.DIRT: int_to_qcolor(settings.dirtMaterialColour),
        SurfaceMaterial.GRASS: int_to_qcolor(settings.grassMaterialColour),
        SurfaceMaterial.STONE: int_to_qcolor(settings.stoneMaterialColour),
        SurfaceMaterial.WOOD: int_to_qcolor(settings.woodMaterialColour),
        SurfaceMaterial.WATER: int_to_qcolor(settings.waterMaterialColour),
        SurfaceMaterial.NON_WALK: int_to_qcolor(settings.nonWalkMaterialColour),
        SurfaceMaterial.TRANSPARENT: int_to_qcolor(settings.transparentMaterialColour),
        SurfaceMaterial.CARPET: int_to_qcolor(settings.carpetMaterialColour),
        SurfaceMaterial.METAL: int_to_qcolor(settings.metalMaterialColour),
        SurfaceMaterial.PUDDLES: int_to_qcolor(settings.puddlesMaterialColour),
        SurfaceMaterial.SWAMP: int_to_qcolor(settings.swampMaterialColour),
        SurfaceMaterial.MUD: int_to_qcolor(settings.mudMaterialColour),
        SurfaceMaterial.LEAVES: int_to_qcolor(settings.leavesMaterialColour),
        SurfaceMaterial.LAVA: int_to_qcolor(settings.lavaMaterialColour),
        SurfaceMaterial.BOTTOMLESS_PIT: int_to_qcolor(settings.bottomlessPitMaterialColour),
        SurfaceMaterial.DEEP_WATER: int_to_qcolor(settings.deepWaterMaterialColour),
        SurfaceMaterial.DOOR: int_to_qcolor(settings.doorMaterialColour),
        SurfaceMaterial.NON_WALK_GRASS: int_to_qcolor(settings.nonWalkGrassMaterialColour),
        SurfaceMaterial.TRIGGER: int_to_qcolor(settings.nonWalkGrassMaterialColour),
    }


def populate_material_list_widget(
    widget: QListWidget,
    material_colors: Mapping[SurfaceMaterial, QColor],
    *,
    icon_size: int = 16,
) -> None:
    widget.clear()
    for material, color in material_colors.items():
        item = QListWidgetItem(material_icon(color, size=icon_size), material_display_name(material))
        item.setData(Qt.ItemDataRole.UserRole, material)
        widget.addItem(item)


def populate_material_combo_box(widget: QComboBox) -> None:
    widget.clear()
    for material in SurfaceMaterial:
        widget.addItem(material_display_name(material), material)
