"""Focused ownership and recovery contracts for the spatial GUI publisher."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

AUTOMATION_ROOT = Path(__file__).resolve().parents[1] / "src"
PACKAGE_SID = (
    "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)


def _modules():
    value = str(AUTOMATION_ROOT)
    if value not in sys.path:
        sys.path.insert(0, value)
    auth = importlib.import_module("ipc.spatial_auth")
    server = importlib.import_module("ipc.server")
    return auth, server


class _FakeLease:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        self._events.append("lease.close")
        self.closed = True


class _FakePipe:
    _counter = 0

    def __init__(self, events: list[object], lease: _FakeLease) -> None:
        type(self)._counter += 1
        token = chr(64 + min(type(self)._counter, 26)) * 43
        self.pipe_name = rf"\\.\pipe\LOCAL\GhostStudioSpatial-{token}"
        self._events = events
        self._lease = lease
        self.is_running = False

    def start(self) -> None:
        assert not self._lease.closed
        self._events.append("pipe.start")
        self.is_running = True

    def stop(self, *, drain_active: bool = False) -> None:
        self._events.append(("pipe.stop", drain_active, self._lease.closed))
        self.is_running = False


class _FakeStopEvent:
    def __init__(self, events: list[object]) -> None:
        self._events = events
        self._set = False

    def set(self) -> None:
        self._set = True

    def clear(self) -> None:
        self._set = False

    def is_set(self) -> bool:
        return self._set

    def wait(self, timeout: float) -> bool:
        self._events.append(("wait", timeout))
        return self._set


def _configured_server(server_module, tmp_path: Path):
    instance = server_module.GhostRiggerIPCServer({}, port=7001)
    profile_root = tmp_path / "profile"
    session_path = (
        profile_root
        / "MCPStudioState"
        / "GhostStudioSpatial"
        / "ghoststudio-session.json"
    )
    instance._spatial_bootstrap = object()
    instance._spatial_profile_root = profile_root
    instance._spatial_session_path = session_path
    instance._spatial_package_sid = PACKAGE_SID
    instance._spatial_transport = server_module.WINDOWS_SPATIAL_TRANSPORT
    return instance


def _descriptor(auth, credentials, pipe_name: str, *, pid: int | None = None):
    return auth.SpatialSessionDescriptor(
        credentials=credentials,
        port=None,
        created_at=1_000,
        pid=os.getpid() if pid is None else pid,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        pipe_name=pipe_name,
        schema="ghoststudio-spatial-session/v2",
    )


def _install_owner_fakes(
    monkeypatch: pytest.MonkeyPatch,
    auth,
    server_module,
    instance,
    events: list[object],
    acquisitions: list[_FakeLease | None],
):
    state: dict[str, object] = {"published": [], "current": None}
    pipes: list[_FakePipe] = []

    def prepare(path, **kwargs):
        events.append("prepare")
        assert Path(path) == instance._spatial_session_path.parent
        assert kwargs["package_sid"] == PACKAGE_SID
        assert kwargs["app_container_root"] == instance._spatial_profile_root
        return Path(path)

    def acquire(path, **kwargs):
        events.append("acquire")
        assert Path(path) == instance._spatial_session_path
        assert kwargs == {
            "package_sid": PACKAGE_SID,
            "app_container_root": instance._spatial_profile_root,
        }
        return acquisitions.pop(0)

    def build(_app, _credentials, _authenticator):
        events.append("pipe.build")
        lease = instance._spatial_session_lease
        assert lease is not None and not lease.closed
        pipe = _FakePipe(events, lease)
        pipes.append(pipe)
        return pipe

    def publish(path, **kwargs):
        events.append("publish")
        lease = instance._spatial_session_lease
        assert lease is not None and not lease.closed
        assert Path(path) == instance._spatial_session_path
        descriptor = _descriptor(
            auth,
            kwargs["credentials"],
            kwargs["pipe_name"],
        )
        state["current"] = descriptor
        state["published"].append(descriptor)
        return descriptor

    monkeypatch.setattr(
        server_module,
        "prepare_private_spatial_directory",
        prepare,
        raising=False,
    )
    monkeypatch.setattr(
        server_module,
        "acquire_windows_spatial_session_lease",
        acquire,
        raising=False,
    )
    monkeypatch.setattr(instance, "_build_windows_spatial_pipe", build)
    monkeypatch.setattr(
        server_module,
        "publish_spatial_session_descriptor",
        publish,
    )
    monkeypatch.setattr(
        server_module,
        "load_spatial_session_descriptor",
        lambda _path, **_kwargs: state["current"],
        raising=False,
    )
    return state, pipes


def test_first_owner_acquires_before_pipe_and_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    state, _pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )

    assert instance._try_acquire_windows_spatial_session_ownership(object())

    assert events == [
        "prepare",
        "acquire",
        "pipe.build",
        "pipe.start",
        "publish",
    ]
    assert instance._spatial_session_lease is lease
    assert len(state["published"]) == 1
    assert not lease.closed


def test_standby_does_not_publish_and_takes_over_on_a_later_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    state, _pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [None, lease],
    )

    assert not instance._maintain_windows_spatial_session(object())
    assert state["published"] == []
    assert events == ["prepare", "acquire"]

    assert instance._maintain_windows_spatial_session(object())
    assert len(state["published"]) == 1
    assert events.count("prepare") == 1
    assert events.count("acquire") == 2
    assert server_module._SPATIAL_SESSION_WATCH_SECONDS == pytest.approx(2.0)


def test_standby_watchdog_waits_between_ownership_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _auth, server_module = _modules()
    events: list[object] = []
    instance = _configured_server(server_module, tmp_path)

    class StopAfterProbe:
        def __init__(self) -> None:
            self.wait_count = 0

        def is_set(self) -> bool:
            return False

        def wait(self, timeout: float) -> bool:
            events.append(("wait", timeout))
            self.wait_count += 1
            return self.wait_count > 1

    instance._stop_requested = StopAfterProbe()
    monkeypatch.setattr(
        instance,
        "_maintain_windows_spatial_session",
        lambda _app: events.append("probe"),
    )

    instance._renew_spatial_sessions(object())

    assert events == [
        ("wait", server_module._SPATIAL_SESSION_WATCH_SECONDS),
        "probe",
        ("wait", server_module._SPATIAL_SESSION_WATCH_SECONDS),
    ]


def test_owner_rotates_when_the_scheduled_renewal_window_opens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    instance._stop_requested = _FakeStopEvent(events)
    state, pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )
    assert instance._try_acquire_windows_spatial_session_ownership(object())
    initial = state["published"][0]
    renew_at = (
        initial.credentials.expires_at
        - instance._spatial_session_renewal_margin_seconds
    )
    monkeypatch.setattr(
        server_module,
        "time",
        SimpleNamespace(time=lambda: renew_at),
    )

    assert instance._maintain_windows_spatial_session(object())

    replacement = state["published"][-1]
    assert replacement.credentials.session_id != initial.credentials.session_id
    assert replacement.pipe_name != initial.pipe_name
    assert len(pipes) == 2
    assert ("wait", server_module._SPATIAL_OLD_ENDPOINT_GRACE_SECONDS) in events
    assert ("pipe.stop", True, False) in events
    assert not lease.closed


@pytest.mark.parametrize(
    "replacement",
    ["missing", "malformed", "foreign"],
)
def test_owner_repairs_missing_malformed_or_foreign_descriptor_with_rotation(
    replacement: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    instance._stop_requested = _FakeStopEvent(events)
    state, pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )
    assert instance._try_acquire_windows_spatial_session_ownership(object())
    initial = state["published"][0]

    if replacement == "foreign":
        foreign_credentials = auth.SpatialSessionCredentials.create()
        observed = _descriptor(
            auth,
            foreign_credentials,
            rf"\\.\pipe\LOCAL\GhostStudioSpatial-{'Z' * 43}",
            pid=os.getpid() + 1,
        )

        def load(_path, **_kwargs):
            return observed

    else:
        code = (
            "session-descriptor-unavailable"
            if replacement == "missing"
            else "invalid-session-descriptor"
        )

        def load(_path, **_kwargs):
            raise auth.SpatialAuthenticationError(code)

    monkeypatch.setattr(
        server_module,
        "load_spatial_session_descriptor",
        load,
        raising=False,
    )

    assert instance._maintain_windows_spatial_session(object())

    repaired = state["published"][-1]
    assert repaired.credentials.session_id != initial.credentials.session_id
    assert repaired.pipe_name != initial.pipe_name
    assert len(pipes) == 2
    assert ("wait", server_module._SPATIAL_OLD_ENDPOINT_GRACE_SECONDS) in events
    assert ("pipe.stop", True, False) in events
    assert not lease.closed


def test_private_storage_drift_fails_closed_without_rotation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    state, _pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )
    assert instance._try_acquire_windows_spatial_session_ownership(object())

    def fail_audit(_path, **_kwargs):
        raise auth.SpatialAuthenticationError("private-session-required")

    monkeypatch.setattr(
        server_module,
        "load_spatial_session_descriptor",
        fail_audit,
        raising=False,
    )

    with pytest.raises(auth.SpatialAuthenticationError) as failure:
        instance._maintain_windows_spatial_session(object())

    assert failure.value.code == "private-session-required"
    assert len(state["published"]) == 1
    assert not lease.closed


def test_publish_failure_stops_replacement_and_releases_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    _state, pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )

    def fail_publish(*_args, **_kwargs):
        events.append("publish.fail")
        raise OSError("expected publication failure")

    monkeypatch.setattr(
        server_module,
        "publish_spatial_session_descriptor",
        fail_publish,
    )
    monkeypatch.setattr(
        server_module,
        "remove_spatial_session_descriptor",
        lambda *_args, **_kwargs: events.append(
            ("descriptor.remove-candidate", lease.closed)
        ),
    )

    with pytest.raises(OSError, match="expected publication failure"):
        instance._try_acquire_windows_spatial_session_ownership(object())

    assert len(pipes) == 1
    assert events[-4:] == [
        "publish.fail",
        ("descriptor.remove-candidate", False),
        ("pipe.stop", False, False),
        "lease.close",
    ]
    assert instance._spatial_session_lease is None
    assert lease.closed


def test_stop_joins_watchdog_then_removes_descriptor_and_releases_lease_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth, server_module = _modules()
    events: list[object] = []
    lease = _FakeLease(events)
    instance = _configured_server(server_module, tmp_path)
    _state, _pipes = _install_owner_fakes(
        monkeypatch,
        auth,
        server_module,
        instance,
        events,
        [lease],
    )
    assert instance._try_acquire_windows_spatial_session_ownership(object())

    def remove(_path, **_kwargs):
        events.append("descriptor.remove")
        assert not lease.closed
        return True

    monkeypatch.setattr(
        server_module,
        "remove_spatial_session_descriptor",
        remove,
    )

    class StoppedWatchdog:
        def join(self, *, timeout: float) -> None:
            assert timeout >= server_module._SPATIAL_SESSION_WATCH_SECONDS
            events.append("watchdog.join")

        def is_alive(self) -> bool:
            return False

    instance._spatial_renewal_thread = StoppedWatchdog()
    events.clear()

    instance.stop()

    assert events == [
        "watchdog.join",
        "descriptor.remove",
        ("pipe.stop", False, False),
        "lease.close",
    ]
    assert instance._spatial_pipe_server is None
    assert instance._spatial_session_lease is None
    assert lease.closed


@pytest.mark.parametrize("bind_failure", ["oserror", "system-exit"])
def test_spatial_bootstrap_port_conflict_uses_ephemeral_coordinator(
    bind_failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _auth, server_module = _modules()
    instance = _configured_server(server_module, tmp_path)
    calls: list[int] = []
    events: list[str] = []

    class FakeWerkzeugServer:
        server_port = 43123

        def serve_forever(self) -> None:
            events.append("serve")

        def shutdown(self) -> None:
            events.append("shutdown")

        def server_close(self) -> None:
            events.append("close")

    def make_server(host, port, _app, threaded=True):
        assert host == "127.0.0.1"
        assert threaded is True
        calls.append(port)
        if len(calls) == 1:
            if bind_failure == "system-exit":
                raise SystemExit(1)
            failure = OSError("10048 address already in use")
            failure.winerror = 10048
            raise failure
        return FakeWerkzeugServer()

    monkeypatch.setattr("werkzeug.serving.make_server", make_server)
    monkeypatch.setattr(
        instance,
        "_prepare_windows_spatial_session_lease_storage",
        lambda: events.append("prepare"),
        raising=False,
    )
    monkeypatch.setattr(
        instance,
        "_try_acquire_windows_spatial_session_ownership",
        lambda _app: False,
        raising=False,
    )
    monkeypatch.setattr(
        instance,
        "_start_spatial_renewal",
        lambda _app: events.append("watch"),
    )
    monkeypatch.setattr(
        server_module,
        "publish_spatial_session_descriptor",
        lambda *_args, **_kwargs: pytest.fail(
            "standby must not publish a loopback descriptor"
        ),
    )

    with caplog.at_level(logging.WARNING):
        instance._run_server()

    assert calls == [7001, 0]
    assert instance.port == 43123
    assert events[:3] == ["prepare", "watch", "serve"]
    assert "ephemeral" in caplog.text.lower()
    assert "7001" in caplog.text
