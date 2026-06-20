"""Qt Character Builder window counterpart.

The implementation lives in ``qt_character_builder_panel.py`` alongside the
embedded panel.  This module preserves the one-to-one migration filename for
``character_builder_window.py``.
"""

from __future__ import annotations

from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderPanel, QtCharacterBuilderWindow

__all__ = ["QtCharacterBuilderPanel", "QtCharacterBuilderWindow"]

