"""Focused contracts for the focus-safe Map Studio skybox visual proof route."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def _server_module():
    _configure_native_python_roots()
    return importlib.import_module("src.ipc.server")


def _resource_panels_module():
    _configure_native_python_roots()
    return importlib.import_module("src.gui.windows.application_core.shared.resource_panels")


def _app_runner_module():
    _configure_native_python_roots()
    return importlib.import_module("src.gui.windows.application_core.functions.app_runner")


def test_splash_stream_tolerates_closed_native_console_handle() -> None:
    module = _app_runner_module()
    emitted: list[str] = []

    class ClosedConsole:
        encoding = "utf-8"
        errors = "replace"

        def write(self, _text: str) -> int:
            raise OSError(22, "Invalid argument")

        def flush(self) -> None:
            raise OSError(22, "Invalid argument")

    stream = module._SplashStream(ClosedConsole(), emitted.append, "STDERR")

    assert stream.write("native startup continued\n") == len("native startup continued\n")
    stream.flush()
    assert emitted == ["STDERR  native startup continued"]


def _test_client(monkeypatch: pytest.MonkeyPatch, callbacks: dict):
    pytest.importorskip("flask")
    module = _server_module()
    captured: dict[str, object] = {}

    class _FakeWerkzeugServer:
        def __init__(self, app) -> None:
            captured["app"] = app
            self.server_port = 0

        def serve_forever(self) -> None:
            return None

    monkeypatch.setattr(
        "werkzeug.serving.make_server",
        lambda _host, _port, app, threaded=True: _FakeWerkzeugServer(app),
    )
    server = module.GhostRiggerIPCServer(callbacks, port=0)
    server._run_server()
    return server, captured["app"].test_client()


def _valid_route_payload(tmp_path: Path) -> dict:
    modules_dir = tmp_path / "Modules"
    modules_dir.mkdir()
    return {
        "game": "k2",
        "module_resref": "231TEL",
        "modules_dir": str(modules_dir.resolve()),
        "before_path": str((tmp_path / "before.png").resolve()),
        "after_path": str((tmp_path / "after.png").resolve()),
        "activate": False,
        "settle_ms": 0,
        "expected_room_resref": "231telSB",
        "expected_backdrop_surface_count": 22,
        "expected_textures": {"tel_sb01": [2048, 2048]},
    }


def _valid_pie_route_payload(tmp_path: Path) -> dict:
    kmap = tmp_path / "plcaa_pie.kmap"
    kmap.write_text("{}", encoding="utf-8")
    return {
        "kmap_path": str(kmap.resolve()),
        "capture_dir": str((tmp_path / "captures").resolve()),
        "activate": False,
        "settle_ms": 0,
        "movement_ms": 250,
        "sample_count": 3,
        "forward": 1.0,
        "strafe": 0.0,
        "run": False,
        "expected_min_distance": 0.05,
    }


def test_ghostrigger_ipc_port_can_be_overridden_per_process_without_changing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    monkeypatch.delenv("GHOSTRIGGER_IPC_PORT", raising=False)
    assert module.resolve_ghostrigger_ipc_port() == 7001
    monkeypatch.setenv("GHOSTRIGGER_IPC_PORT", "7011")
    assert module.resolve_ghostrigger_ipc_port() == 7011
    assert module.GhostRiggerIPCServer({}).port == 7011
    assert module.GhostRiggerIPCServer({}, port=0).port == 0
    for value in ("invalid", "0", "65536", ""):
        assert module.resolve_ghostrigger_ipc_port(value) == 7001


def test_focus_safe_validation_process_start_is_explicit_and_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _app_runner_module()
    monkeypatch.delenv("GHOSTRIGGER_START_WITHOUT_ACTIVATING", raising=False)
    assert module._start_without_activation_from_env() is False
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("GHOSTRIGGER_START_WITHOUT_ACTIVATING", value)
        assert module._start_without_activation_from_env() is True
    monkeypatch.setenv("GHOSTRIGGER_START_WITHOUT_ACTIVATING", "0")
    assert module._start_without_activation_from_env() is False


def test_pie_focus_audit_distinguishes_user_activity_from_proof_window_activation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    owners = {100: 10, 200: 20, 300: 99}
    monkeypatch.setattr(module, "_window_process_id", lambda handle: owners.get(handle))

    user_changed_apps = module._map_studio_focus_audit(100, 200, proof_process_id=99)
    assert user_changed_apps["foreground_unchanged"] is False
    assert user_changed_apps["proof_became_foreground"] is False

    proof_stole_focus = module._map_studio_focus_audit(100, 300, proof_process_id=99)
    assert proof_stole_focus["foreground_unchanged"] is False
    assert proof_stole_focus["proof_became_foreground"] is True


def test_pie_clean_presentation_accepts_only_transient_runtime_marker_geometry() -> None:
    module = _resource_panels_module()
    runtime = SimpleNamespace(
        footprints=(SimpleNamespace(role="pie_focus", kind="pie_focus", placement_id="authored:creature:1"),),
        lines=(SimpleNamespace(role="pie_path", kind="pie_path", placement_id="__map_studio_pie_path_0__"),),
        icons=(),
    )
    authored = SimpleNamespace(
        footprints=(SimpleNamespace(role="creature", kind="creature", placement_id="authored:creature:1"),),
        lines=(),
        icons=(),
    )

    assert module._map_studio_pie_marker_geometry_is_runtime_only(None) is True
    assert module._map_studio_pie_marker_geometry_is_runtime_only(runtime) is True
    assert module._map_studio_pie_marker_geometry_is_runtime_only(authored) is False


def test_map_studio_visual_proof_route_is_synchronous_validated_and_uses_180_second_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[dict] = []
    timeout_values: list[float] = []

    def callback(payload: dict) -> dict:
        received.append(payload)
        return {"status": "blocked", "blockers": ["fixture response"]}

    server, client = _test_client(monkeypatch, {"map_studio_visual_proof": callback})

    def invoke(cb, payload, *, timeout=2.0):
        timeout_values.append(float(timeout))
        return True, cb(payload)

    monkeypatch.setattr(server, "_invoke_callback_sync", invoke)
    response = client.post("/api/map_studio_visual_proof", json={"payload": _valid_route_payload(tmp_path)})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["proof"]["status"] == "blocked"
    assert timeout_values == [180.0]
    assert received[0]["game"] == "K2"
    assert received[0]["module_resref"] == "231tel"
    assert Path(received[0]["before_path"]).is_absolute()
    assert received[0]["activate"] is False


def test_map_studio_visual_proof_positive_settle_uses_full_renderer_residency_window(tmp_path: Path) -> None:
    module = _server_module()
    base_payload = _valid_route_payload(tmp_path)
    for requested in (None, 1, 750, 1000, 4999, 5000):
        payload = dict(base_payload)
        if requested is None:
            payload.pop("settle_ms")
        else:
            payload["settle_ms"] = requested
        normalised, error = module._validate_map_studio_visual_proof_payload(payload)
        assert error == ""
        assert normalised is not None
        assert normalised["settle_ms"] == 5000

    payload = dict(base_payload)
    normalised, error = module._validate_map_studio_visual_proof_payload(payload)
    assert error == ""
    assert normalised is not None
    assert normalised["settle_ms"] == 0


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"game": "k3"}, "game must be"),
        ({"module_resref": "not-a-resref"}, "module_resref"),
        ({"modules_dir": "relative/Modules"}, "modules_dir must be an absolute path"),
        ({"before_path": "relative.png"}, "before_path must be an absolute path"),
        ({"activate": True}, "activate must be false"),
        ({"settle_ms": 5001}, "settle_ms"),
        ({"expected_textures": {"bad-texture": [4, 4]}}, "invalid expected texture resref"),
        ({"expected_textures": {"skytex": [4]}}, "must be [width, height]"),
    ],
)
def test_map_studio_visual_proof_route_rejects_unsafe_or_malformed_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    updates: dict,
    message: str,
) -> None:
    callbacks: list[dict] = []
    _server, client = _test_client(
        monkeypatch,
        {"map_studio_visual_proof": lambda payload: callbacks.append(payload)},
    )
    payload = _valid_route_payload(tmp_path)
    payload.update(updates)
    response = client.post("/api/map_studio_visual_proof", json=payload)
    assert response.status_code == 400
    assert message in response.get_json()["message"]
    assert callbacks == []


def test_map_studio_visual_proof_route_reports_missing_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _server, client = _test_client(monkeypatch, {})
    response = client.post("/api/map_studio_visual_proof", json=_valid_route_payload(tmp_path))
    assert response.status_code == 503
    assert "callback unavailable" in response.get_json()["message"]


def test_map_studio_pie_visual_proof_route_is_focus_safe_validated_and_synchronous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[dict] = []
    timeout_values: list[float] = []
    server, client = _test_client(
        monkeypatch,
        {"map_studio_pie_visual_proof": lambda payload: received.append(payload) or {"status": "passed"}},
    )

    def invoke(cb, payload, *, timeout=2.0):
        timeout_values.append(float(timeout))
        return True, cb(payload)

    monkeypatch.setattr(server, "_invoke_callback_sync", invoke)
    response = client.post("/api/map_studio_pie_visual_proof", json={"payload": _valid_pie_route_payload(tmp_path)})
    assert response.status_code == 200
    assert response.get_json()["proof"]["status"] == "passed"
    assert timeout_values == [180.0]
    assert received[0]["activate"] is False
    assert Path(received[0]["kmap_path"]).is_absolute()


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"kmap_path": "relative.kmap"}, "kmap_path must be an absolute path"),
        ({"capture_dir": "relative"}, "capture_dir must be an absolute path"),
        ({"activate": True}, "activate must be false"),
        ({"movement_ms": 99}, "movement_ms"),
        ({"sample_count": 13}, "sample_count"),
        ({"forward": 1.1}, "forward"),
        ({"run": "yes"}, "run must be a boolean"),
    ],
)
def test_map_studio_pie_visual_proof_route_rejects_unsafe_or_unbounded_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    updates: dict,
    message: str,
) -> None:
    callbacks: list[dict] = []
    _server, client = _test_client(
        monkeypatch,
        {"map_studio_pie_visual_proof": lambda payload: callbacks.append(payload)},
    )
    payload = _valid_pie_route_payload(tmp_path)
    payload.update(updates)
    response = client.post("/api/map_studio_pie_visual_proof", json=payload)
    assert response.status_code == 400
    assert message in response.get_json()["message"]
    assert callbacks == []


def test_map_studio_visual_proof_refuses_dirty_or_nonempty_existing_singleton(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    monkeypatch.setattr(module, "_qt_object_alive", lambda _value: True)
    monkeypatch.setattr(module, "_foreground_window_handle", lambda: 77)

    for project in (
        SimpleNamespace(dirty=True, rooms=[], extra_sections={}),
        SimpleNamespace(dirty=False, rooms=[object()], extra_sections={}),
        SimpleNamespace(dirty=False, rooms=[], extra_sections={"authored_module": {"rooms": [1]}}),
    ):
        class _Host(module.ResourcePanelsMixin):
            module_editor_window = SimpleNamespace(project=project)

            def _open_module_editor_window(self, activate: bool = True):  # pragma: no cover - must never run
                raise AssertionError("proof route replaced an existing project")

        result = _Host()._map_studio_visual_proof_from_ipc(
            {"game": "K2", "module_resref": "231tel", "modules_dir": str(tmp_path)}
        )
        assert result["status"] == "blocked"
        assert result["foreground_unchanged"] is True
        assert result["project_guard"]["refused_existing_project"] is True
        assert any("refused to replace" in blocker for blocker in result["blockers"])


def test_map_studio_visual_proof_blocks_when_known_foreground_handle_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    handles = iter((1001, 2002))
    monkeypatch.setattr(module, "_foreground_window_handle", lambda: next(handles))
    monkeypatch.setattr(module, "_qt_object_alive", lambda _value: True)

    class _Host(module.ResourcePanelsMixin):
        module_editor_window = SimpleNamespace(
            project=SimpleNamespace(dirty=True, rooms=[], extra_sections={})
        )

        def _open_module_editor_window(self, activate: bool = True):  # pragma: no cover - must never run
            raise AssertionError("proof route replaced an existing project")

    result = _Host()._map_studio_visual_proof_from_ipc(
        {"game": "K2", "module_resref": "231tel", "modules_dir": str(tmp_path)}
    )
    assert result["status"] == "blocked"
    assert result["foreground_unchanged"] is False
    assert result["focus_audit"] == {
        "foreground_before": 1001,
        "foreground_after": 2002,
        "foreground_unchanged": False,
    }
    assert any("Foreground window changed" in blocker for blocker in result["blockers"])


def test_pie_renderer_readiness_records_zero_draw_polls_before_capturing_real_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    perf = {
        "last_frame_ms": 0.0,
        "draw_calls": 0,
        "tri_count": 0,
        "visible_meshes": 0,
        "culled_meshes": 0,
    }
    paint_requests: list[dict] = []
    settled: list[int] = []
    captured: list[Path] = []
    canvas_updates: list[str] = []

    class _Surface:
        def update(self) -> None:
            canvas_updates.append("surface")

    class _Canvas:
        def update(self) -> None:
            canvas_updates.append("canvas")

        def current_surface(self):
            return _Surface()

    def request_render(*, fast: bool, reason: str, **dirty_flags: bool) -> None:
        assert fast is True
        assert reason == "PIE visual proof renderer readiness"
        assert dirty_flags == {"scene": True}
        paint_requests.append(dict(dirty_flags))

    viewport = SimpleNamespace(
        _gpu_renderer=SimpleNamespace(perf=perf),
        _last_render_ms=0.0,
        _request_render=request_render,
    )

    def settle(milliseconds: int) -> None:
        # Renderer counters may transition only after this attempt has actively
        # requested a frame and the queued host/native-surface paints exist.
        assert len(paint_requests) == len(settled) + 1
        assert canvas_updates[-2:] == ["canvas", "surface"]
        settled.append(milliseconds)
        if len(settled) == 3:
            perf.update(
                {
                    "last_frame_ms": 18.0,
                    "draw_calls": 443,
                    "tri_count": 20000,
                    "visible_meshes": 50,
                }
            )

    def capture(_canvas: object, target: Path):
        captured.append(target)
        target.write_bytes(b"PNG")
        return {
            "path": str(target),
            "width": 2,
            "height": 1,
            "bytes_per_line": 8,
            "sha256": "ready",
            "saved": True,
        }, bytes((10, 20, 30, 255, 200, 210, 220, 255))

    monkeypatch.setattr(module, "_settle_map_studio_visual_proof", settle)
    monkeypatch.setattr(module, "_capture_map_studio_canvas", capture)
    monkeypatch.setattr(
        module,
        "_map_studio_capture_content_metrics",
        lambda _capture, _rgba: {"sample_count": 2, "content_present": True},
    )

    ready_frame: dict = {}
    result = module._wait_for_map_studio_renderer_readiness(
        _Canvas(),
        viewport,
        tmp_path,
        max_attempts=5,
        interval_ms=25,
        ready_frame=ready_frame,
    )

    assert result["ready"] is True
    assert result["attempt_count"] == 3
    assert result["blank_attempt_count"] == 2
    assert result["zero_draw_call_attempt_count"] == 2
    assert result["varied_content_missing_attempt_count"] == 0
    assert result["ready_attempt"] == 3
    assert result["ready_after_wait_ms"] == 75
    assert result["maximum_wait_ms"] == 125
    assert settled == [25, 25, 25]
    assert len(paint_requests) == 3
    assert canvas_updates == ["canvas", "surface"] * 3
    assert [path.name for path in captured] == ["pie_renderer_readiness_02.png"]
    assert all(row["capture_attempted"] is False for row in result["attempts"][:2])
    assert all(row["paint_drive"]["render_request_succeeded"] for row in result["attempts"])
    assert all(row["paint_drive"]["canvas_update_requested"] for row in result["attempts"])
    assert all(row["paint_drive"]["surface_update_requested"] for row in result["attempts"])
    assert result["attempts"][2]["performance"]["draw_calls"] == 443
    assert ready_frame["capture"]["sha256"] == "ready"
    assert Path(ready_frame["capture"]["path"]).name == "pie_frame_00.png"
    assert Path(ready_frame["capture"]["path"]).read_bytes() == b"PNG"
    assert ready_frame["rgba"]


def test_pie_renderer_readiness_caps_native_grab_when_drawn_surface_is_still_blank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    captures: list[Path] = []
    paint_requests: list[str] = []

    def capture(_canvas: object, target: Path):
        captures.append(target)
        target.write_bytes(b"PNG")
        return {
            "path": str(target),
            "width": 2,
            "height": 1,
            "bytes_per_line": 8,
            "sha256": "blank",
            "saved": True,
        }, bytes((20, 20, 20, 255) * 2)

    viewport = SimpleNamespace(
        _gpu_renderer=SimpleNamespace(perf={"draw_calls": 7}),
        _last_render_ms=1.0,
        _request_render=lambda **_kwargs: paint_requests.append("requested"),
    )
    monkeypatch.setattr(module, "_settle_map_studio_visual_proof", lambda _milliseconds: None)
    monkeypatch.setattr(module, "_capture_map_studio_canvas", capture)
    monkeypatch.setattr(
        module,
        "_map_studio_capture_content_metrics",
        lambda _capture, _rgba: {"sample_count": 2, "content_present": False},
    )

    result = module._wait_for_map_studio_renderer_readiness(
        object(),
        viewport,
        tmp_path,
        max_attempts=12,
        interval_ms=100,
        ready_frame={},
    )

    assert result["ready"] is False
    assert result["attempt_count"] == 1
    assert result["varied_content_missing_attempt_count"] == 1
    assert paint_requests == ["requested"]
    assert len(captures) == 1


def test_pie_visual_proof_blocks_before_requested_sequence_when_renderer_never_becomes_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    monkeypatch.setattr(module, "_foreground_window_handle", lambda: 7007)
    monkeypatch.setattr(module, "_settle_map_studio_visual_proof", lambda _milliseconds: None)
    monkeypatch.setattr(
        module,
        "_capture_map_studio_canvas",
        lambda _canvas, _target: (_ for _ in ()).throw(AssertionError("zero-draw readiness must not grab")),
    )

    session = SimpleNamespace(state=SimpleNamespace(position=[0.0, 0.0, 0.0], simulation_time=0.0))
    viewport = SimpleNamespace(
        canvas=object(),
        model=object(),
        camera=SimpleNamespace(target=[0.0, 0.0, 1.6]),
        frame_all=lambda: None,
        _gpu_renderer=SimpleNamespace(perf={"draw_calls": 0}),
        _last_render_ms=0.0,
    )
    panel = SimpleNamespace(
        viewport=viewport,
        _room_preview_model=object(),
        set_view_mode=lambda _mode: None,
    )

    class _Controller:
        def open_project(self, _path: Path, *, resource_manager=None) -> None:
            return None

        def create_map_studio_pie_session(self, *, preview_model=None):
            return SimpleNamespace(
                session=session,
                validation=SimpleNamespace(ok=True, blocking_issues=(), warnings=()),
                walkable_face_count=2,
                collision_triangle_count=4,
            )

    class _Window:
        project = SimpleNamespace(dirty=False, rooms=[], extra_sections={})
        controller = _Controller()
        resource_manager = object()
        viewport_panel = panel
        _map_studio_pie_session = None
        stopped = False

        def _reset_map_studio_texture_paint_session(self) -> None:
            return None

        def _refresh_all(self, _message: str) -> None:
            return None

        def _start_map_studio_pie(self, *, focus_viewport: bool = True) -> None:
            assert focus_viewport is False
            self._map_studio_pie_session = session

        def _stop_map_studio_pie(self) -> None:
            self.stopped = True
            self._map_studio_pie_session = None

    window = _Window()

    class _Host(module.ResourcePanelsMixin):
        module_editor_window = None

        def _open_module_editor_window(self, activate: bool = True):
            assert activate is False
            return window

    result = _Host()._map_studio_pie_visual_proof_from_ipc(_valid_pie_route_payload(tmp_path))

    assert result["status"] == "blocked"
    assert result["renderer_readiness"]["ready"] is False
    assert result["renderer_readiness"]["attempt_count"] == 12
    assert result["renderer_readiness"]["zero_draw_call_attempt_count"] == 12
    assert result["captures"]["sequence_started"] is False
    assert result["captures"]["completed"] == 0
    assert window.stopped is True
    assert any("requested continuous sample sequence was not started" in blocker for blocker in result["blockers"])


def test_map_studio_visual_proof_callback_imports_toggles_captures_and_audits_without_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _resource_panels_module()
    state = {"skybox": False, "activate_values": []}
    monkeypatch.setattr(module, "_foreground_window_handle", lambda: 5150)

    class _Image:
        size = (4, 4)

    class _Manager:
        def game_dir(self, game: str) -> str:
            assert game == "K2"
            return r"C:\Fixture\K2"

        def get_texture(self, name: str, game: str) -> bytes:
            assert (name, game) == ("skytex", "K2")
            return b"fixture texture"

        def load_texture_image(self, name: str, game: str, max_size: int = 512):
            assert (name, game, max_size) == ("skytex", "K2", 0)
            return _Image()

    backdrop_surface = SimpleNamespace(name="Sky", texture="skytex", backdrop=True)
    ground_surface = SimpleNamespace(name="Ground", texture="ground", backdrop=False)
    room = SimpleNamespace(
        normalised_resref=lambda: "skyroom",
        primitive=SimpleNamespace(surfaces=(backdrop_surface, ground_surface)),
    )

    class _Controller:
        def import_stock_module_from_rim(self, **kwargs):
            assert kwargs["module_resref"] == "fixture"
            assert kwargs["game"] == "K2"
            return True, "imported"

        def convert_all_stock_rooms_to_imported_mesh(self, **_kwargs):
            return True, "converted"

        def _load_authored_project_or_raise(self):
            return SimpleNamespace(rooms=(room,))

    class _Preview:
        def all_nodes(self):
            if not state["skybox"]:
                return []
            return [
                SimpleNamespace(
                    name="Sky",
                    _gr_map_studio_backdrop=True,
                    texture="skytex",
                    texture_names=["skytex"],
                )
            ]

    class _Canvas:
        pass

    canvas = _Canvas()
    viewport = SimpleNamespace(
        canvas=canvas,
        _renderer=SimpleNamespace(tex_cache=SimpleNamespace(get=lambda name: _Image() if name == "skytex" else None)),
        frame_all=lambda: None,
        _request_render=lambda **_kwargs: None,
    )
    panel = SimpleNamespace(
        viewport=viewport,
        _room_preview_model=_Preview(),
        set_view_mode=lambda mode: state.setdefault("view_mode", mode),
    )

    class _Window:
        project = SimpleNamespace(dirty=False, rooms=[], extra_sections={})
        resource_manager = _Manager()
        controller = _Controller()
        viewport_panel = panel
        _map_studio_show_skybox = False

        def _refresh_all(self, _message: str) -> None:
            return None

        def _set_map_studio_skybox_visible(self, visible: bool) -> None:
            self._map_studio_show_skybox = bool(visible)
            state["skybox"] = bool(visible)

    window = _Window()

    class _Host(module.ResourcePanelsMixin):
        module_editor_window = None

        def _open_module_editor_window(self, activate: bool = True):
            state["activate_values"].append(bool(activate))
            return window

    def fake_capture(_canvas, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"PNG")
        rgba = bytes((40, 80, 120, 255) if state["skybox"] else (0, 0, 0, 255))
        return {
            "path": str(target),
            "width": 1,
            "height": 1,
            "bytes_per_line": 4,
            "sha256": "after" if state["skybox"] else "before",
            "saved": True,
        }, rgba

    monkeypatch.setattr(module, "_capture_map_studio_canvas", fake_capture)
    monkeypatch.setattr(module, "_settle_map_studio_visual_proof", lambda _milliseconds: None)

    payload = {
        "game": "K2",
        "module_resref": "fixture",
        "modules_dir": str(tmp_path.resolve()),
        "before_path": str((tmp_path / "before.png").resolve()),
        "after_path": str((tmp_path / "after.png").resolve()),
        "settle_ms": 0,
        "expected_room_resref": "skyroom",
        "expected_backdrop_surface_count": 1,
        "expected_textures": {"skytex": [4, 4]},
    }
    result = _Host()._map_studio_visual_proof_from_ipc(payload)

    assert result["status"] == "ok"
    assert state["activate_values"] == [False]
    assert result["captures"]["delta"]["changed_pixels"] == 1
    assert result["surface_audit"]["backdrop_surface_count"] == 1
    assert result["texture_audit"]["resource_decode_verified"] is True
    assert result["texture_audit"]["renderer_cache_verified"] is True
    assert result["texture_audit"]["renderer_material_binding_verified"] is True
    assert result["preview_audit"]["visible_backdrop_node_count"] == 1
    assert result["preview_audit"]["visible_backdrop_texture_resrefs"] == ["skytex"]
    assert result["window_activated"] is False
    assert result["foreground_unchanged"] is True


@pytest.mark.parametrize(
    (
        "motion_updates",
        "expected_animation_required",
        "expected_animation_observed",
        "minimum_distance",
        "expected_native_grabs",
    ),
    [
        ({}, True, True, 0.2, 4),
        (
            {"forward": 0.0, "strafe": 0.0, "expected_min_distance": 0.0},
            False,
            False,
            0.0,
            3,
        ),
    ],
    ids=("locomotion", "stationary-capture"),
)
def test_map_studio_pie_visual_proof_applies_motion_contract_and_captures_continuous_frames_without_activation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    motion_updates: dict,
    expected_animation_required: bool,
    expected_animation_observed: bool,
    minimum_distance: float,
    expected_native_grabs: int,
) -> None:
    module = _resource_panels_module()
    state = {
        "activate_values": [],
        "focus_viewport_values": [],
        "moving": False,
        "stopped": False,
        "captures": 0,
    }
    monkeypatch.setattr(module, "_foreground_window_handle", lambda: 6006)

    session = SimpleNamespace(
        state=SimpleNamespace(position=[0.0, 0.0, 0.0], simulation_time=0.0),
    )
    camera = SimpleNamespace(target=[0.0, 0.0, 1.6])
    canvas = object()
    viewport_properties = {"_gr_map_studio_pie_clean_runtime": False}
    gpu_renderer = SimpleNamespace(
        show_light_gizmos=True,
        show_light_radius_volumes=True,
        show_dummy_helpers=True,
        selected_node=object(),
        selected_nodes=[object()],
        perf={
            "last_frame_ms": 20.0,
            "gpu_upload_ms": 1.0,
            "draw_ms": 16.0,
            "readback_ms": 3.0,
            "draw_calls": 42,
            "tri_count": 207,
            "visible_meshes": 40,
            "culled_meshes": 12,
        },
    )
    viewport = SimpleNamespace(
        canvas=canvas,
        model=object(),
        camera=camera,
        frame_all=lambda: None,
        property=lambda name: viewport_properties.get(name),
        _gpu_renderer=gpu_renderer,
        _map_studio_marker_geometry=object(),
        _last_render_ms=22.0,
    )
    panel = SimpleNamespace(viewport=viewport, _room_preview_model=object(), set_view_mode=lambda _mode: None)

    class _Controller:
        def open_project(self, path: Path, *, resource_manager=None) -> None:
            state["opened"] = str(path)
            state["open_resource_manager"] = resource_manager

        def create_map_studio_pie_session(self, *, preview_model=None):
            assert preview_model is panel._room_preview_model
            return SimpleNamespace(
                session=session,
                validation=SimpleNamespace(ok=True, blocking_issues=(), warnings=()),
                walkable_face_count=2,
                collision_triangle_count=4,
            )

    class _Window:
        project = SimpleNamespace(dirty=False, rooms=[], extra_sections={})
        controller = _Controller()
        resource_manager = object()
        viewport_panel = panel
        _map_studio_pie_session = None
        _map_studio_pie_actor = None
        _map_studio_pie_actor_warning = ""
        _map_studio_pie_animation_name = "pause1"

        def _reset_map_studio_texture_paint_session(self) -> None:
            return None

        def _refresh_all(self, _message: str) -> None:
            return None

        def _start_map_studio_pie(self, *, focus_viewport: bool = True) -> None:
            state["focus_viewport_values"].append(bool(focus_viewport))
            self._map_studio_pie_session = session
            self._map_studio_pie_actor = object()
            viewport_properties["_gr_map_studio_pie_clean_runtime"] = True
            viewport._map_studio_marker_geometry = None
            gpu_renderer.show_light_gizmos = False
            gpu_renderer.show_light_radius_volumes = False
            gpu_renderer.show_dummy_helpers = False
            gpu_renderer.selected_node = None
            gpu_renderer.selected_nodes = []

        def _stop_map_studio_pie(self) -> None:
            state["stopped"] = True
            self._map_studio_pie_session = None

        def _handle_map_studio_pie_move_input(self, payload: dict) -> None:
            state["moving"] = bool(payload.get("forward") or payload.get("strafe"))

    window = _Window()

    class _Host(module.ResourcePanelsMixin):
        module_editor_window = None

        def _open_module_editor_window(self, activate: bool = True):
            state["activate_values"].append(bool(activate))
            return window

    def settle(_milliseconds: int) -> None:
        if state["moving"]:
            session.state.position[0] += 0.2
            session.state.simulation_time += 0.1
            camera.target[0] = session.state.position[0]
            window._map_studio_pie_animation_name = "walk"

    def capture(_canvas: object, target: Path):
        state["captures"] += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"PNG")
        shade = min(250, 20 + state["captures"])
        rgba = bytes((shade, 40, 80, 255, 120, 180, 220, 255))
        return {
            "path": str(target),
            "width": 2,
            "height": 1,
            "bytes_per_line": 8,
            "sha256": str(state["captures"]),
            "saved": True,
        }, rgba

    monkeypatch.setattr(module, "_settle_map_studio_visual_proof", settle)
    monkeypatch.setattr(module, "_capture_map_studio_canvas", capture)
    monkeypatch.setattr(
        module,
        "_map_studio_capture_content_metrics",
        lambda _capture, _rgba: {"content_present": True, "sample_count": 2},
    )
    payload = _valid_pie_route_payload(tmp_path)
    payload.update(motion_updates)
    result = _Host()._map_studio_pie_visual_proof_from_ipc(payload)

    assert result["status"] == "passed"
    assert state["activate_values"] == [False]
    assert state["focus_viewport_values"] == [False]
    assert state["open_resource_manager"] is window.resource_manager
    assert state["stopped"] is True
    assert result["runtime"]["movement_distance"] >= minimum_distance
    assert result["runtime"]["actor_attached"] is True
    assert result["runtime"]["moving_animation_required"] is expected_animation_required
    assert result["runtime"]["moving_animation_observed"] is expected_animation_observed
    assert result["runtime"]["clean_runtime_presentation"]["ok"] is True
    assert result["runtime"]["performance"] == {
        "viewport_frame_median_ms": 22.0,
        "gpu_frame_median_ms": 20.0,
        "viewport_estimated_fps": 45.45,
        "gpu_estimated_fps": 50.0,
        "gpu_upload_median_ms": 1.0,
        "gpu_draw_median_ms": 16.0,
        "gpu_readback_median_ms": 3.0,
    }
    assert result["captures"]["frames"][0]["performance"]["visible_meshes"] == 40
    assert result["captures"]["frames"][0]["performance"]["culled_meshes"] == 12
    assert result["renderer_readiness"]["ready"] is True
    assert result["renderer_readiness"]["ready_attempt"] == 1
    assert result["captures"]["sequence_started"] is True
    assert result["captures"]["continuous_content"] is True
    assert result["captures"]["completed"] == 3
    assert state["captures"] == expected_native_grabs
    assert (result["captures"]["motion_frame"] is not None) is (expected_native_grabs == 4)
    assert result["foreground_unchanged"] is True


def test_map_studio_visual_proof_source_and_mirror_contracts() -> None:
    server = ROOT / "native/GhostRigger.Core.Automation/Python/src/ipc/server.py"
    main_window = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py"
    display = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/resource_panels.py"
    tools = ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/application_core/shared/resource_panels.py"
    module_editor = ROOT / "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    app_runner = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/functions/app_runner.py"
    rendering_pipeline = ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/viewport_core/widgets/rendering_pipeline.py"

    server_source = server.read_text(encoding="utf-8")
    main_source = main_window.read_text(encoding="utf-8")
    resource_source = display.read_text(encoding="utf-8")
    module_editor_source = module_editor.read_text(encoding="utf-8")
    app_runner_source = app_runner.read_text(encoding="utf-8")
    rendering_pipeline_source = rendering_pipeline.read_text(encoding="utf-8")
    assert '@app.route("/api/map_studio_visual_proof", methods=["POST"])' in server_source
    assert '@app.route("/api/map_studio_pie_visual_proof", methods=["POST"])' in server_source
    assert server_source.count("timeout=180.0") == 2
    assert "timeout=90.0" not in server_source
    assert '"map_studio_pie_visual_proof": map_studio_pie_visual_proof' in main_source
    assert "self._ipc_server.port" in main_source
    assert '"map_studio_visual_proof": map_studio_visual_proof' in main_source
    assert "return self._map_studio_visual_proof_from_ipc(data)" in main_source
    assert "def _open_module_editor_window(self, activate: bool = True)" in resource_source
    assert "window.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, not bool(activate))" in resource_source
    assert "window = self._open_module_editor_window(activate=False)" in resource_source
    assert "_map_studio_project_content_reasons" in resource_source
    assert "foreground_before = _foreground_window_handle()" in resource_source
    assert 'result["foreground_unchanged"] = foreground_unchanged' in resource_source
    assert "def _map_studio_pie_visual_proof_from_ipc" in resource_source
    assert "window._start_map_studio_pie(focus_viewport=False)" in resource_source
    assert "def _start_map_studio_pie(self, *, focus_viewport: bool = True)" in module_editor_source
    assert "if focus_viewport:" in module_editor_source
    assert "self._start_map_studio_pie()" in module_editor_source
    assert 'resource_manager=getattr(window, "resource_manager", None)' in resource_source
    assert "self.controller.open_project(path, resource_manager=self.resource_manager)" in module_editor_source
    assert "_map_studio_capture_content_metrics" in resource_source
    assert "_wait_for_map_studio_renderer_readiness" in resource_source
    assert "_MAP_STUDIO_PIE_RENDERER_READINESS_MAX_ATTEMPTS = 12" in resource_source
    assert '"sequence_started": False' in resource_source
    assert "GHOSTRIGGER_START_WITHOUT_ACTIVATING" in app_runner_source
    assert "WA_ShowWithoutActivating" in app_runner_source
    assert 'clean_runtime = bool(self.property("_gr_map_studio_pie_clean_runtime"))' in rendering_pipeline_source
    assert "or clean_runtime" in rendering_pipeline_source
    assert display.read_bytes() == tools.read_bytes()
