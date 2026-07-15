"""Focused proof: PIE start reuses cached walkmesh and player-actor work.

On large converted modules (koq201: 9 imported rooms, ~48k triangles) every
Play press measured ~62 s: ~49 s reloading the player body/head and their
supermodel animation chains, and ~9 s recombining the module walkmesh. Both
are pure projections of unchanged state, so they are now cached — the
combined WOK per authored revision, and the composed player actor per
(manager, game, body, head).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_session_build_accepts_precombined_walkmesh(monkeypatch) -> None:
    _configure_native_python_roots()
    from src.core.modules import map_studio_pie as pie
    from src.core.modules.module_editor_controller import ModuleEditorController

    controller = ModuleEditorController()
    controller.new_project(name="grpieperf", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grpieperf")

    calls = {"combine": 0}
    original = pie.combine_authored_module_walkmesh

    def counting_combine(project):
        calls["combine"] += 1
        return original(project)

    monkeypatch.setattr(pie, "combine_authored_module_walkmesh", counting_combine)

    first = controller.create_map_studio_pie_session()
    assert first.session is not None
    combines_after_first = calls["combine"]
    second = controller.create_map_studio_pie_session()
    assert second.session is not None
    # The controller's authored-revision cache supplies the combined WOK, so
    # the session builder itself never recombines.
    assert calls["combine"] == combines_after_first == 0


def test_player_actor_model_is_cached_across_play_presses() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpieactor", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        loads: list[str] = []

        class _Manager:
            def load_model_strict(self, resref, game):
                loads.append(str(resref))
                return _stub_model(str(resref))

            def load_model(self, resref, game):
                return _stub_model(str(resref))

        window.resource_manager = _Manager()
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))

        window._create_map_studio_pie_player_actor(session, preview, "K1")
        first_loads = list(loads)
        assert "pmbam" in first_loads
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        # The composed actor is reused: no further strict loads on replay.
        assert loads == first_loads
        cache = window._map_studio_pie_player_model_cache
        assert len(cache) == 1
        # A different player body is a different cache entry.
        window._map_studio_pie_player_settings = lambda: ("pfbam", "pfhc01")
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert "pfbam" in loads
        assert len(cache) == 2
    finally:
        window.deleteLater()


def test_prewarm_is_deferred_and_guarded() -> None:
    _configure_native_python_roots()
    source = (ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py").read_text(encoding="utf-8")
    assert "_prewarm_map_studio_pie_player_model" in source
    # Deferred off the refresh hot path: the MDL parse contends for the GIL.
    assert "QtCore.QTimer.singleShot(1500, self._prewarm_map_studio_pie_player_model)" in source
    mirror = (ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie.py").read_text(encoding="utf-8")
    assert "combined_walkmesh" in mirror
