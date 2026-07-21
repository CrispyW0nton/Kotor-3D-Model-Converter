"""Focused UX contracts for the KOTOR Particle Editor."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore, QtWidgets


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_particle_editor_starts_safe_and_filters_lazy_library(tmp_path: Path) -> None:
    _qapp()
    from src.core.particles.emitter_library import EmitterTemplate
    from src.gui.qt_lib.windows.qt_particle_editor import QtParticleEditorWindow

    window = QtParticleEditorWindow(app_root=tmp_path)
    try:
        assert window.library_search_edit.isClearButtonEnabled()
        assert "not saved automatically" in window.session_notice_label.text()
        assert all(group.isEnabled() is False for group in window._parameter_groups)

        window._templates["K1"] = [
            EmitterTemplate(
                game="K1",
                model="plc_smoke",
                node="smoke_emitter",
                definition={"texture": "fx_smoke", "update": "Fountain", "blend": "Lighten"},
            ),
            EmitterTemplate(
                game="K1",
                model="plc_holo",
                node="ring_emitter",
                definition={"texture": "fx_holo", "update": "Fountain", "blend": "Lighten"},
            ),
        ]
        window._refresh_template_groups()
        assert window.k1_group.childCount() == 2
        assert window.k1_group.child(0).child(0).data(0, QtCore.Qt.UserRole) is None

        window.library_search_edit.setText("fx_holo")
        window._refresh_template_groups()
        assert window.k1_group.childCount() == 1
        assert window.k1_group.child(0).text(0) == "plc_holo"
        assert window.k1_group.child(0).child(0).text(0) == "ring_emitter"
    finally:
        window._session_modified = False
        window.close()
