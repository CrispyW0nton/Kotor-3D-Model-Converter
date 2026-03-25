"""Editor UI pipelines: exclusive checkbox selection and module-root combobox population."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QPixmap

if TYPE_CHECKING:
    from qtpy.QtGui import QImage
    from qtpy.QtWidgets import QCheckBox, QComboBox, QLabel

    from pykotor.common.modulekit import ModuleKitManager


def set_exclusive_checkbox_selection(active_checkbox: QCheckBox, checkboxes: Sequence[QCheckBox]) -> None:
    """Check only *active_checkbox* and uncheck all others in *checkboxes*."""
    for checkbox in checkboxes:
        checkbox.setChecked(checkbox is active_checkbox)


def populate_module_root_combobox(
    combo_box: QComboBox,
    module_kit_manager: ModuleKitManager | None,
) -> None:
    """Populate a combobox with module roots from *module_kit_manager*."""
    combo_box.clear()
    if module_kit_manager is None:
        return

    module_roots: list[str] = module_kit_manager.get_module_roots()
    for module_root in module_roots:
        display_name: str = module_kit_manager.get_module_display_name(module_root)
        combo_box.addItem(display_name, module_root)


def set_preview_source_image(
    label: QLabel,
    image: QImage | None,
) -> QImage | None:
    """Set preview source image and render to *label* at current size."""
    if image is None:
        label.clear()
        return None

    update_preview_image_size(label, image)
    return image


def update_preview_image_size(
    label: QLabel,
    source_image: QImage | None,
) -> None:
    """Render *source_image* into *label* using smooth KeepAspectRatio scaling."""
    if source_image is None:
        return

    label_size: QSize = label.size()
    if label_size.width() <= 0 or label_size.height() <= 0:
        label_size = label.sizeHint()
    if label_size.width() <= 0 or label_size.height() <= 0:
        label_size = QSize(128, 128)

    pixmap: QPixmap = QPixmap.fromImage(source_image)
    scaled: QPixmap = pixmap.scaled(
        label_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    label.setPixmap(scaled)
