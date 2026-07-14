from __future__ import annotations

import inspect
from pathlib import Path

from PySide6 import QtGui, QtWidgets

from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin


ROOT = Path(__file__).resolve().parents[1]


def test_main_header_uses_ghoststudio_name_and_real_brand_icon_path() -> None:
    source = inspect.getsource(WindowChromeMixin._make_header)
    assert 'QtMatrixLabel("GHOST STUDIO")' in source
    assert 'QtMatrixLabel("GHOSTRIGGER")' not in source
    assert "_ghost_studio_brand_icon(36)" in source
    assert 'logo.setText("GS")' in source
    assert 'logo.setText("LO")' not in source


def test_brand_icon_loads_actual_ghoststudio_artwork() -> None:
    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class BrandHost:
        app_root = ROOT

        @staticmethod
        def _icon(_name: str, _size: int) -> QtGui.QIcon:
            return QtGui.QIcon()

    icon = WindowChromeMixin._ghost_studio_brand_icon(BrandHost(), 36)
    assert not icon.isNull()
    assert not icon.pixmap(36, 36).isNull()
