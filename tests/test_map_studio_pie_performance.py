"""Focused proof: PIE start reuses cached walkmesh and player-actor work.

On large converted modules (koq201: 9 imported rooms, ~48k triangles) every
Play press measured ~62 s: ~49 s reloading the player body/head and their
supermodel animation chains, and ~9 s recombining the module walkmesh. Both
are pure projections of unchanged state, so they are now cached — the
combined WOK per authored revision, and the composed player actor per
(manager, resource revision, game, body, head).
"""

from __future__ import annotations

import os
import sys
import threading
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


def test_repeated_pie_requests_coalesce_without_restarting_scheduled_render() -> None:
    """A 16 ms simulation tick must not perpetually postpone one queued frame."""

    _configure_native_python_roots()
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import (
        ViewportRenderingPipelineMixin,
    )

    class _Timer:
        def __init__(self) -> None:
            self.active = True
            self.starts: list[int] = []

        def isActive(self) -> bool:  # noqa: N802 - Qt-shaped probe
            return self.active

        def start(self, delay: int) -> None:
            self.starts.append(int(delay))
            self.active = True

    class _Governor:
        def __init__(self) -> None:
            self.requests: list[tuple[str, dict[str, bool]]] = []

        def request_redraw(self, reason: str, **flags: bool) -> None:
            self.requests.append((reason, dict(flags)))

    timer = _Timer()
    governor = _Governor()
    harness = SimpleNamespace(
        _render_pending=False,
        _render_timer=timer,
        _frame_governor=governor,
        _renderer_settings=SimpleNamespace(target_fps=60),
        _dual_viewport_mode=False,
        _fast_frame_until=0.0,
        _last_render_wall=0.0,
    )

    request = ViewportRenderingPipelineMixin._request_render
    for _tick in range(20):
        request(harness, fast=True, reason="Map Studio PIE camera frame", camera=True)

    assert harness._render_pending is True
    assert len(governor.requests) == 20
    assert timer.starts == []

    timer.active = False
    request(harness, fast=True, reason="Map Studio PIE camera frame", camera=True)
    assert len(timer.starts) == 1
    assert timer.starts[0] >= 1


def test_controller_reuses_combined_walkmesh_until_authored_revision_changes(monkeypatch) -> None:
    _configure_native_python_roots()
    from src.core.modules import module_editor_controller as controller_module

    controller = controller_module.ModuleEditorController()
    controller.new_project(name="grpieperf", game="K1")
    controller.create_authored_room_preset_module(preset_id="rectangular_dev_room", module_root="grpieperf")

    calls = {"combine": 0}
    original = controller_module.combine_authored_module_walkmesh

    def counting_combine(project):
        calls["combine"] += 1
        return original(project)

    monkeypatch.setattr(controller_module, "combine_authored_module_walkmesh", counting_combine)

    first = controller.create_map_studio_pie_session()
    assert first.session is not None
    assert calls["combine"] == 1
    second = controller.create_map_studio_pie_session()
    assert second.session is not None
    assert calls["combine"] == 1

    controller.set_authored_module_entry_point(
        area_resref="grpieperf",
        position=(0.25, 0.25, 0.0),
        facing=0.0,
    )
    third = controller.create_map_studio_pie_session()
    assert third.session is not None
    # One authored mutation advances the revision and rebuilds exactly once.
    assert calls["combine"] == 2


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


def test_pie_runtime_player_replaces_and_restores_complete_player_start_preview() -> None:
    """PIE must never render its player over the editor Player Start character."""

    _configure_native_python_roots()
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    root = md.ModelNode(name="map_root", flags=int(md.NodeFlags.HEADER))
    room = md.ModelNode(name="room", flags=int(md.NodeFlags.HEADER))
    player_start = md.ModelNode(name="player_start", flags=int(md.NodeFlags.HEADER))
    body = md.ModelNode(name="player_body", flags=int(md.NodeFlags.HEADER))
    head = md.ModelNode(name="player_head", flags=int(md.NodeFlags.HEADER))
    body.parent = player_start
    head.parent = player_start
    player_start.children = [body, head]
    setattr(player_start, "_gr_map_studio_placement_id", "entry_point")
    setattr(player_start, "_gr_map_studio_placement_kind", "entry_point")
    room.parent = root
    player_start.parent = root
    root.children = [room, player_start]
    preview = md.KotorModel(name="map_preview", root_node=root)
    harness = SimpleNamespace(
        _map_studio_pie_actor=object(),
        _map_studio_pie_hidden_player_start_groups=[],
    )

    ModuleEditorWindow._hide_map_studio_pie_player_start_preview(harness, preview)

    assert root.children == [room]
    assert player_start.children == [body, head]
    assert harness._map_studio_pie_hidden_player_start_groups == [(1, player_start)]

    ModuleEditorWindow._restore_map_studio_pie_player_start_preview(harness, preview)

    assert root.children == [room, player_start]
    assert player_start.parent is root
    assert harness._map_studio_pie_hidden_player_start_groups == []


def test_prewarm_is_deferred_and_guarded() -> None:
    _configure_native_python_roots()
    source = (ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py").read_text(encoding="utf-8")
    assert "_prewarm_map_studio_pie_player_model" in source
    # Deferred off the refresh hot path: the MDL parse contends for the GIL.
    assert "QtCore.QTimer.singleShot(1500, self._prewarm_map_studio_pie_player_model)" in source
    mirror = (ROOT / "native/GhostRigger.Core.Scene/Python/src/core/modules/map_studio_pie.py").read_text(encoding="utf-8")
    assert "combined_walkmesh" in mirror


def test_prewarm_worker_does_not_touch_process_global_animation_state(monkeypatch) -> None:
    _configure_native_python_roots()
    import threading

    from PySide6 import QtWidgets
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpieprewarm", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            def load_model_strict(self, resref, game):
                return _stub_model(str(resref))

        class _ImmediateThread:
            def __init__(self, *, target, **_kwargs):
                self._target = target

            def start(self):
                self._target()

        configure_calls: list[object] = []
        play_calls: list[str] = []
        monkeypatch.setattr(threading, "Thread", _ImmediateThread)
        monkeypatch.setattr(
            SuperModelResolver,
            "configure",
            lambda manager: configure_calls.append(manager),
        )
        monkeypatch.setattr(
            AnimationEngine,
            "play",
            lambda _engine, name, **_kwargs: play_calls.append(str(name)) or True,
        )
        window.resource_manager = _Manager()
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")

        window._prewarm_map_studio_pie_player_model()

        assert len(window._map_studio_pie_player_model_cache) == 1
        assert configure_calls == []
        assert play_calls == []
    finally:
        window.deleteLater()


def test_player_actor_cache_invalidates_when_resource_revision_changes() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.controller.new_project(name="grpierevision", game="K1")

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def __init__(self) -> None:
                self.loads: list[tuple[int, str]] = []

            def load_model_strict(self, resref, _game):
                self.loads.append((self.revision, str(resref)))
                return _stub_model(f"{resref}_r{self.revision}")

            def load_model(self, resref, _game):
                return _stub_model(str(resref))

        manager = _Manager()
        window.resource_manager = manager
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))

        window._create_map_studio_pie_player_actor(session, preview, "K1")
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert manager.loads == [(0, "pmbam")]

        manager.revision = 1
        window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert manager.loads == [(0, "pmbam"), (1, "pmbam")]
        cache = window._map_studio_pie_player_model_cache
        assert len(cache) == 1
        cache_key = next(iter(cache))
        assert cache_key[0] is manager
        assert cache_key[1] == 1
    finally:
        window.deleteLater()


def test_play_does_not_duplicate_an_inflight_player_prewarm(monkeypatch) -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows import module_editor_window as window_module

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = window_module.ModuleEditorWindow()
    release_loader = threading.Event()
    try:
        window.controller.new_project(name="grpiepending", game="K1")
        load_started = threading.Event()
        loads: list[str] = []

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def load_model_strict(self, resref, _game):
                loads.append(str(resref))
                load_started.set()
                assert release_loader.wait(2.0)
                return _stub_model(str(resref))

            def load_model(self, resref, _game):
                return _stub_model(str(resref))

        window.resource_manager = _Manager()
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        preview = _stub_model("map_preview")
        session = SimpleNamespace(state=SimpleNamespace(position=(0.0, 0.0, 0.0), facing_radians=0.0))
        monkeypatch.setattr(window_module, "_MAP_STUDIO_PIE_PLAYER_PREWARM_WAIT_SECONDS", 0.01)

        window._prewarm_map_studio_pie_player_model()
        assert load_started.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            completion = next(iter(window._map_studio_pie_player_prewarm_pending.values()))

        warning = window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert "still preparing" in warning
        assert loads == ["pmbam"]

        release_loader.set()
        assert completion.wait(2.0)
        warning = window._create_map_studio_pie_player_actor(session, preview, "K1")
        assert warning == ""
        assert loads == ["pmbam"]
    finally:
        release_loader.set()
        window.deleteLater()


def test_prewarm_discards_model_when_resource_revision_changes() -> None:
    _configure_native_python_roots()
    from PySide6 import QtWidgets
    from src.core.geometry import model_data as md
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    release_loader = threading.Event()
    try:
        window.controller.new_project(name="grpieworkrev", game="K1")
        load_started = threading.Event()

        def _stub_model(name):
            root = md.ModelNode(name=f"{name}_root", flags=int(md.NodeFlags.HEADER))
            return md.KotorModel(name=name, root_node=root)

        class _Manager:
            revision = 0

            def load_model_strict(self, resref, _game):
                load_started.set()
                assert release_loader.wait(2.0)
                return _stub_model(str(resref))

        manager = _Manager()
        window.resource_manager = manager
        window._map_studio_pie_player_settings = lambda: ("pmbam", "")
        window._prewarm_map_studio_pie_player_model()
        assert load_started.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            old_key, completion = next(iter(window._map_studio_pie_player_prewarm_pending.items()))

        manager.revision = 1
        release_loader.set()
        assert completion.wait(2.0)
        with window._map_studio_pie_player_cache_lock:
            assert old_key not in window._map_studio_pie_player_model_cache
            assert old_key not in window._map_studio_pie_player_prewarm_pending
    finally:
        release_loader.set()
        window.deleteLater()
