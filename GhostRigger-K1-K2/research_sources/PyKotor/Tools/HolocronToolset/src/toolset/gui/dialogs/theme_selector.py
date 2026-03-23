"""Toolset compatibility wrapper: delegates to utility ThemeSelectorDialog with Toolset tr and theme manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from toolset.gui.common.localization import translate as tr
from utility.gui.qt.widgets.theme import ThemeSelectorDialog as UtilityThemeSelectorDialog

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget


class ThemeSelectorDialog(UtilityThemeSelectorDialog):
    """
    Toolset theme selector: utility dialog with Toolset localization and optional theme manager.
    Prefer importing from utility.gui.qt.widgets.theme for new code.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        available_themes: list[str] | None = None,
        available_styles: list[str] | None = None,
        current_theme: str | None = None,
        current_style: str | None = None,
    ):
        super().__init__(
            parent=parent,
            theme_manager=None,
            available_themes=available_themes,
            available_styles=available_styles,
            current_theme=current_theme,
            current_style=current_style,
            tr=tr,
            install_no_scroll_filter=True,
        )
