"""Backward compatibility: utility.ui_libraries mirrors utility.gui so legacy imports resolve.

Legacy: from utility.ui_libraries.qt.widgets.theme.theme_dialog import ThemeDialog
Resolves to: utility.gui.qt.widgets.theme.theme_dialog (same namespace).
"""
from utility import gui
import sys

# Replace this package with gui so utility.ui_libraries.qt.widgets... resolves to gui.qt.widgets...
sys.modules["utility.ui_libraries"] = gui
