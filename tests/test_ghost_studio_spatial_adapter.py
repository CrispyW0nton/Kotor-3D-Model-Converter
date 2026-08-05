"""Focused contracts for the private Ghost Studio spatial adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
AUTH_MODULE = (
    ROOT
    / "native"
    / "GhostRigger.Core.Automation"
    / "Python"
    / "src"
    / "ipc"
    / "spatial_auth.py"
)
SNAPSHOT_MODULE = (
    ROOT
    / "native"
    / "GhostRigger.Core.Scene"
    / "Python"
    / "src"
    / "core"
    / "scene"
    / "spatial_snapshot.py"
)
SPATIAL_MCP_MODULE = (
    ROOT
    / "native"
    / "GhostRigger.Core.Automation"
    / "Python"
    / "src"
    / "ghoststudio_spatial_mcp"
    / "server.py"
)


def _auth_module():
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_auth_test_module",
        AUTH_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _snapshot_module():
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_snapshot_test_module",
        SNAPSHOT_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _spatial_mcp_module():
    automation_src = SPATIAL_MCP_MODULE.parents[1]
    text = str(automation_src)
    if text not in sys.path:
        sys.path.insert(0, text)
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_mcp_test_module",
        SPATIAL_MCP_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def _server_module():
    _configure_native_python_roots()
    import importlib

    return importlib.import_module("src.ipc.server")


def _viewport_tools_module():
    _configure_native_python_roots()
    import importlib

    return importlib.import_module(
        "src.gui.windows.application_core.shared.viewport_tools"
    )


def _test_client(
    monkeypatch: pytest.MonkeyPatch,
    callbacks: dict,
    *,
    authenticator=None,
):
    pytest.importorskip("flask")
    module = _server_module()
    captured: dict[str, object] = {}

    def _marshal_inline_for_test(callback, *args) -> bool:
        callback(*args)
        return True

    monkeypatch.setattr(
        module,
        "marshal_to_gui_thread",
        _marshal_inline_for_test,
    )

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
    server = module.GhostRiggerIPCServer(
        callbacks,
        port=0,
        spatial_authenticator=authenticator,
    )
    server._run_server()
    return module, server, captured["app"].test_client()


def _credentials(module, *, expires_at: int = 2_000):
    return module.SpatialSessionCredentials(
        session_id="session_0123456789abcdef",
        secret=b"s" * 32,
        expires_at=expires_at,
    )


def _valid_gui_readiness(*, ready: bool = True) -> dict:
    return {
        "ready": ready,
        "mainThreadObserved": ready,
        "windowVisible": ready,
        "windowMinimized": False,
        "viewport": {
            "stateAvailable": ready,
            "visible": ready,
            "width": 1280 if ready else 0,
            "height": 720 if ready else 0,
        },
        "grid": {
            "stateAvailable": ready,
            "visible": ready,
        },
        "reason": None if ready else "viewport-state-unavailable",
    }


def _valid_viewport() -> dict:
    identity = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return {
        "id": "ghoststudio-main-viewport",
        "rectangle": {
            "x": 0.0,
            "y": 0.0,
            "width": 1280.0,
            "height": 720.0,
        },
        "pixelOrigin": "top-left",
        "devicePixelRatio": 1.0,
        "cameraStableId": None,
        "projection": "perspective",
        "viewMatrix": identity,
        "projectionMatrix": identity,
        "nearClip": 0.01,
        "farClip": 1000.0,
    }


def _valid_spatial_snapshot(
    *,
    include_bounds: bool = True,
    include_hierarchy: bool = True,
    include_selection: bool = True,
) -> dict:
    snapshot = _snapshot_module().build_scene_spatial_snapshot(
        _scene(_scene_object("object_a", selected=True)),
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
        viewport=_valid_viewport(),
        grid={
            "origin": [0.0, 0.0, 0.0],
            "spacing": [10.0, 10.0, 10.0],
            "subdivisions": 10,
            "visible": True,
            "snapEnabled": False,
        },
        include_bounds=include_bounds,
        include_hierarchy=include_hierarchy,
        include_selection=include_selection,
    )
    snapshot["guiReadiness"] = _valid_gui_readiness()
    return snapshot


def test_spatial_hmac_round_trip_binds_method_path_and_body() -> None:
    module = _auth_module()
    credentials = _credentials(module)
    signer = module.SpatialRequestSigner(credentials)
    verifier = module.SpatialRequestAuthenticator(
        credentials,
        now=lambda: 1_000,
    )
    body = b'{"includeCapture":false}'
    headers = signer.sign(
        method="POST",
        path="/api/mcpstudio/spatial-snapshot",
        body=body,
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )

    verified = verifier.verify(
        headers=headers,
        method="POST",
        path="/api/mcpstudio/spatial-snapshot",
        body=body,
    )

    assert verified.session_id == credentials.session_id
    assert verified.timestamp == 1_000
    assert verified.nonce == "nonce_0123456789abcdef"
    assert verified.body_sha256 == module.sha256_hex(body)
    for changed in (
        {"method": "GET"},
        {"path": "/api/mcpstudio/health"},
        {"body": b'{"includeCapture":true}'},
    ):
        with pytest.raises(module.SpatialAuthenticationError) as error:
            module.SpatialRequestAuthenticator(
                credentials,
                now=lambda: 1_000,
            ).verify(
                headers=headers,
                method=changed.get("method", "POST"),
                path=changed.get(
                    "path",
                    "/api/mcpstudio/spatial-snapshot",
                ),
                body=changed.get("body", body),
            )
        assert error.value.code == "invalid-signature"


@pytest.mark.parametrize(
    ("headers_update", "expected_code"),
    [
        ({"X-GhostStudio-Session": ""}, "missing-credentials"),
        ({"X-GhostStudio-Session": "another_session_012345"}, "invalid-session"),
        ({"X-GhostStudio-Timestamp": "not-a-number"}, "invalid-timestamp"),
        ({"X-GhostStudio-Nonce": "short"}, "invalid-nonce"),
        ({"X-GhostStudio-Signature": "not-a-signature"}, "invalid-signature"),
    ],
)
def test_spatial_hmac_rejects_malformed_credentials(
    headers_update: dict[str, str],
    expected_code: str,
) -> None:
    module = _auth_module()
    credentials = _credentials(module)
    signer = module.SpatialRequestSigner(credentials)
    headers = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )
    headers.update(headers_update)

    with pytest.raises(module.SpatialAuthenticationError) as error:
        module.SpatialRequestAuthenticator(
            credentials,
            now=lambda: 1_000,
        ).verify(
            headers=headers,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )

    assert error.value.code == expected_code
    assert credentials.secret.hex() not in str(error.value)


def test_spatial_hmac_rejects_expired_and_replayed_requests() -> None:
    module = _auth_module()
    credentials = _credentials(module)
    signer = module.SpatialRequestSigner(credentials)
    headers = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )
    verifier = module.SpatialRequestAuthenticator(
        credentials,
        max_clock_skew_seconds=30,
        now=lambda: 1_000,
    )

    verifier.verify(
        headers=headers,
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )
    with pytest.raises(module.SpatialAuthenticationError) as replay:
        verifier.verify(
            headers=headers,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )
    assert replay.value.code == "replayed-request"

    with pytest.raises(module.SpatialAuthenticationError) as stale:
        module.SpatialRequestAuthenticator(
            credentials,
            max_clock_skew_seconds=30,
            now=lambda: 1_031,
        ).verify(
            headers=headers,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )
    assert stale.value.code == "expired-request"


def test_spatial_hmac_replay_cache_fails_closed_at_capacity() -> None:
    module = _auth_module()
    credentials = _credentials(module, expires_at=2_000)
    signer = module.SpatialRequestSigner(credentials)
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        replay_capacity=1,
        now=lambda: 1_000,
    )
    first = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )
    second = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_000,
        nonce="nonce_fedcba9876543210",
    )

    authenticator.verify(
        headers=first,
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )
    with pytest.raises(module.SpatialAuthenticationError) as capacity:
        authenticator.verify(
            headers=second,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )
    assert capacity.value.code == "replay-capacity-exhausted"
    with pytest.raises(module.SpatialAuthenticationError) as replay:
        authenticator.verify(
            headers=first,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )
    assert replay.value.code == "replayed-request"


def test_spatial_hmac_replay_cache_purges_out_of_order_expired_timestamps() -> None:
    module = _auth_module()
    credentials = _credentials(module, expires_at=2_000)
    signer = module.SpatialRequestSigner(credentials)
    current_time = [1_000]
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        max_clock_skew_seconds=60,
        replay_capacity=2,
        now=lambda: current_time[0],
    )
    future_first = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_050,
        nonce="nonce_future_0123456789",
    )
    older_second = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=950,
        nonce="nonce_older_01234567890",
    )

    authenticator.verify(
        headers=future_first,
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )
    authenticator.verify(
        headers=older_second,
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )

    current_time[0] = 1_011
    replacement = signer.sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_011,
        nonce="nonce_fresh_0123456789",
    )
    authenticator.verify(
        headers=replacement,
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )

    with pytest.raises(module.SpatialAuthenticationError) as replay:
        authenticator.verify(
            headers=future_first,
            method="GET",
            path="/api/mcpstudio/health",
            body=b"",
        )
    assert replay.value.code == "replayed-request"


def test_spatial_credentials_do_not_expose_secret_in_repr() -> None:
    module = _auth_module()
    credentials = _credentials(module)

    assert "ssss" not in repr(credentials)
    assert credentials.secret.hex() not in repr(credentials)


def test_spatial_session_descriptor_round_trip_is_bounded_and_private(
    tmp_path: Path,
) -> None:
    module = _auth_module()
    descriptor_path = tmp_path / "private" / "ghoststudio-session.json"
    secured: list[tuple[Path, bool]] = []

    published = module.publish_spatial_session_descriptor(
        descriptor_path,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=3_600,
        security_hook=lambda path, is_directory: secured.append(
            (Path(path), is_directory)
        ),
    )
    loaded = module.load_spatial_session_descriptor(
        descriptor_path,
        now=lambda: 1_001,
        security_audit=lambda path, is_directory: secured.append(
            (Path(path), is_directory)
        ),
    )

    assert loaded.schema == "ghoststudio-spatial-session/v1"
    assert loaded.port == 7017
    assert loaded.created_at == 1_000
    assert loaded.credentials == published.credentials
    assert loaded.credentials.expires_at == 4_600
    assert descriptor_path.stat().st_size < 4096
    assert (descriptor_path.parent, True) in secured
    assert (descriptor_path, False) in secured
    assert loaded.credentials.secret.hex() not in repr(loaded)


def test_spatial_session_descriptor_rejects_expiry_and_unknown_fields(
    tmp_path: Path,
) -> None:
    module = _auth_module()
    descriptor_path = tmp_path / "private" / "ghoststudio-session.json"
    no_security = lambda _path, _is_directory: None
    module.publish_spatial_session_descriptor(
        descriptor_path,
        port=7017,
        now=lambda: 1_000,
        ttl_seconds=60,
        security_hook=no_security,
    )

    with pytest.raises(module.SpatialAuthenticationError) as expired:
        module.load_spatial_session_descriptor(
            descriptor_path,
            now=lambda: 1_061,
            security_audit=no_security,
        )
    assert expired.value.code == "expired-session"

    payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    descriptor_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.SpatialAuthenticationError) as invalid:
        module.load_spatial_session_descriptor(
            descriptor_path,
            now=lambda: 1_001,
            security_audit=no_security,
        )
    assert invalid.value.code == "invalid-session-descriptor"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows production transport")
def test_spatial_gui_server_requires_sealed_transport_and_package_sid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    auth = _auth_module()
    monkeypatch.delenv(auth.SPATIAL_TRANSPORT_ENV, raising=False)
    monkeypatch.delenv(auth.SPATIAL_APP_CONTAINER_SID_ENV, raising=False)

    with pytest.raises(module.SpatialAuthenticationError) as missing_transport:
        module.GhostRiggerIPCServer(
            {},
            port=0,
            spatial_session_path=tmp_path / "session.json",
        )
    assert missing_transport.value.code == "invalid-spatial-transport"

    monkeypatch.setenv(
        auth.SPATIAL_TRANSPORT_ENV,
        auth.WINDOWS_SPATIAL_TRANSPORT,
    )
    with pytest.raises(module.SpatialAuthenticationError) as missing_sid:
        module.GhostRiggerIPCServer(
            {},
            port=0,
            spatial_session_path=tmp_path / "session.json",
        )
    assert missing_sid.value.code == "invalid-app-container-sid"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows production transport")
def test_spatial_gui_server_uses_explicit_bootstrap_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    import importlib

    auth = importlib.import_module("src.ipc.spatial_auth")
    for key in (
        auth.SPATIAL_TRANSPORT_ENV,
        auth.SPATIAL_APP_CONTAINER_SID_ENV,
        auth.SPATIAL_SESSION_PATH_ENV,
        "GHOSTSTUDIO_SPATIAL_BASE_URL",
        "GHOSTSTUDIO_SPATIAL_HOST",
        "GHOSTSTUDIO_SPATIAL_PORT",
        "GHOSTSTUDIO_SPATIAL_SESSION_URL",
        "GHOSTSTUDIO_SPATIAL_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    anchor = auth.SpatialProfileAnchor(
        schema=auth.SPATIAL_PROFILE_ANCHOR_SCHEMA,
        adapter_id=auth.SPATIAL_PROFILE_ADAPTER_ID,
        approval_id="ab" * 32,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        identity_derivation=auth.SPATIAL_PROFILE_IDENTITY_DERIVATION,
    )
    moniker = auth.derive_windows_spatial_profile_moniker(
        anchor.approval_id
    )
    profile_root = tmp_path / "Local" / "Packages" / moniker
    profile_root.mkdir(parents=True)
    package_sid = (
        "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
        "1354859120-752965424-969501979"
    )
    session_path = auth.spatial_session_path_for_profile(profile_root)
    bootstrap = auth.SpatialServerBootstrap(
        anchor=anchor,
        identity=auth.WindowsSpatialProfileIdentity(
            moniker=moniker,
            package_sid=package_sid,
            profile_root=profile_root,
        ),
        session_path=session_path,
    )

    server = module.GhostRiggerIPCServer(
        {},
        port=0,
        spatial_bootstrap=bootstrap,
    )

    assert server._spatial_package_sid == package_sid
    assert server._spatial_profile_root == profile_root
    assert server._spatial_session_path == session_path
    assert server._spatial_transport == auth.WINDOWS_SPATIAL_TRANSPORT

    with pytest.raises(ValueError, match="mutually exclusive"):
        module.GhostRiggerIPCServer(
            {},
            port=0,
            spatial_bootstrap=bootstrap,
            spatial_session_path=session_path,
        )

    monkeypatch.setenv(
        "GHOSTSTUDIO_SPATIAL_URL",
        "http://127.0.0.1:7001",
    )
    with pytest.raises(auth.SpatialAuthenticationError) as conflict:
        module.GhostRiggerIPCServer(
            {},
            port=0,
            spatial_bootstrap=bootstrap,
        )
    assert conflict.value.code == "conflicting-spatial-environment"


def test_spatial_ipc_routes_fail_closed_without_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _module, _server, client = _test_client(
        monkeypatch,
        {"get_spatial_snapshot": lambda _payload: {"sceneRevision": "scene:1"}},
    )

    response = client.post(
        "/api/mcpstudio/spatial-snapshot",
        data=b"{}",
        content_type="application/json",
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "error",
        "code": "spatial-auth-unconfigured",
    }


def test_windows_named_pipe_mode_has_no_loopback_spatial_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = _auth_module()
    credentials = _credentials(auth)
    module, server, client = _test_client(
        monkeypatch,
        {"get_spatial_health": lambda: _valid_gui_readiness()},
        authenticator=auth.SpatialRequestAuthenticator(
            credentials,
            now=lambda: 1_000,
        ),
    )
    server._spatial_transport = module.WINDOWS_SPATIAL_TRANSPORT
    headers = auth.SpatialRequestSigner(credentials).sign(
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )

    response = client.get(
        "/api/mcpstudio/health",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.get_json() == {
        "status": "error",
        "code": "spatial-transport-unavailable",
    }


def test_spatial_ipc_rejects_missing_invalid_and_replayed_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    credentials = _credentials(module)
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        now=lambda: 1_000,
    )
    _module, _server, client = _test_client(
        monkeypatch,
        {"get_spatial_snapshot": lambda _payload: _valid_spatial_snapshot()},
        authenticator=authenticator,
    )
    path = "/api/mcpstudio/spatial-snapshot"
    body = b'{"includeSelection":true}'

    missing = client.post(path, data=body, content_type="application/json")
    assert missing.status_code == 401
    assert missing.get_json()["code"] == "missing-credentials"

    headers = module.SpatialRequestSigner(credentials).sign(
        method="POST",
        path=path,
        body=body,
        timestamp=1_000,
        nonce="nonce_0123456789abcdef",
    )
    invalid_headers = {**headers, module.HEADER_SIGNATURE: "0" * 64}
    invalid = client.post(
        path,
        data=body,
        content_type="application/json",
        headers=invalid_headers,
    )
    assert invalid.status_code == 401
    assert invalid.get_json()["code"] == "invalid-signature"

    first = client.post(
        path,
        data=body,
        content_type="application/json",
        headers=headers,
    )
    replay = client.post(
        path,
        data=body,
        content_type="application/json",
        headers=headers,
    )
    assert first.status_code == 200
    assert replay.status_code == 401
    assert replay.get_json()["code"] == "replayed-request"
    combined = json.dumps(
        [missing.get_json(), invalid.get_json(), replay.get_json()],
        sort_keys=True,
    )
    assert credentials.secret.hex() not in combined


def test_spatial_ipc_exposes_only_narrow_authenticated_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    credentials = _credentials(module)
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        now=lambda: 1_000,
    )
    observed: list[dict] = []

    def snapshot(payload: dict) -> dict:
        observed.append(payload)
        return _valid_spatial_snapshot()

    _module, _server, client = _test_client(
        monkeypatch,
        {
            "get_spatial_health": lambda: _valid_gui_readiness(),
            "get_spatial_snapshot": snapshot,
            "capture_spatial_evidence": lambda payload: {
                "captureId": payload["captureId"],
                "sha256": "a" * 64,
            },
            "get_spatial_evidence_gaps": lambda _payload: {
                "gaps": ["camera-projection-unavailable"],
            },
        },
        authenticator=authenticator,
    )

    def request(method: str, path: str, body: bytes, nonce: str):
        headers = module.SpatialRequestSigner(credentials).sign(
            method=method,
            path=path,
            body=body,
            timestamp=1_000,
            nonce=nonce,
        )
        return client.open(
            path,
            method=method,
            data=body,
            content_type="application/json",
            headers=headers,
        )

    health = request(
        "GET",
        "/api/mcpstudio/health",
        b"",
        "nonce_health_0123456789",
    )
    snapshot_response = request(
        "POST",
        "/api/mcpstudio/spatial-snapshot",
        b'{"includeSelection":true}',
        "nonce_snapshot_01234567",
    )
    capture_response = request(
        "POST",
        "/api/mcpstudio/capture",
        b'{"captureId":"capture_0123456789abcdef"}',
        "nonce_capture_012345678",
    )
    gaps_response = request(
        "POST",
        "/api/mcpstudio/evidence-gaps",
        b"{}",
        "nonce_gaps_012345678901",
    )

    assert health.status_code == 200
    assert health.get_json()["endpoint"] == {
        "authenticated": True,
        "transport": "loopback-http",
    }
    assert health.get_json()["gui"] == _valid_gui_readiness()
    assert health.get_json()["capabilities"] == [
        "health",
        "spatial-snapshot",
        "capture",
        "evidence-gaps",
    ]
    assert snapshot_response.get_json()["snapshot"]["sceneRevision"].startswith(
        "sha256:"
    )
    assert capture_response.get_json()["capture"]["sha256"] == "a" * 64
    assert gaps_response.get_json()["evidence"]["gaps"] == [
        "camera-projection-unavailable"
    ]
    assert observed == [{"includeSelection": True}]


def test_spatial_health_distinguishes_endpoint_liveness_from_gui_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    credentials = _credentials(module)
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        now=lambda: 1_000,
    )
    _module, _server, client = _test_client(
        monkeypatch,
        {"get_spatial_health": lambda: _valid_gui_readiness(ready=False)},
        authenticator=authenticator,
    )
    path = "/api/mcpstudio/health"
    headers = module.SpatialRequestSigner(credentials).sign(
        method="GET",
        path=path,
        body=b"",
        timestamp=1_000,
        nonce="nonce_health_unready_0123",
    )

    response = client.get(path, headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["endpoint"]["authenticated"] is True
    assert payload["gui"]["ready"] is False
    assert payload["gui"]["viewport"]["stateAvailable"] is False
    assert payload["gui"]["grid"]["stateAvailable"] is False


def test_spatial_callbacks_fail_closed_when_gui_marshalling_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _server_module()
    credentials = _credentials(module)
    authenticator = module.SpatialRequestAuthenticator(
        credentials,
        now=lambda: 1_000,
    )
    callbacks_observed: list[str] = []

    def health() -> dict:
        callbacks_observed.append("health")
        return _valid_gui_readiness()

    def snapshot(_payload: dict) -> dict:
        callbacks_observed.append("snapshot")
        return _valid_spatial_snapshot()

    _module, _server, client = _test_client(
        monkeypatch,
        {
            "get_spatial_health": health,
            "get_spatial_snapshot": snapshot,
        },
        authenticator=authenticator,
    )
    monkeypatch.setattr(
        module,
        "marshal_to_gui_thread",
        lambda _callback, *_args: False,
    )
    signer = module.SpatialRequestSigner(credentials)
    health_path = "/api/mcpstudio/health"
    health_headers = signer.sign(
        method="GET",
        path=health_path,
        body=b"",
        timestamp=1_000,
        nonce="nonce_health_no_gui_0123",
    )
    snapshot_path = "/api/mcpstudio/spatial-snapshot"
    snapshot_body = b"{}"
    snapshot_headers = signer.sign(
        method="POST",
        path=snapshot_path,
        body=snapshot_body,
        timestamp=1_000,
        nonce="nonce_snapshot_no_gui_01",
    )

    health_response = client.get(health_path, headers=health_headers)
    snapshot_response = client.post(
        snapshot_path,
        data=snapshot_body,
        content_type="application/json",
        headers=snapshot_headers,
    )

    assert health_response.status_code == 200
    assert health_response.get_json()["gui"]["reason"] == (
        "gui-readiness-check-failed"
    )
    assert snapshot_response.status_code == 504
    assert snapshot_response.get_json()["code"] == "spatial-snapshot-failed"
    assert callbacks_observed == []


def test_live_gui_health_callback_requires_viewport_and_grid_markers() -> None:
    module = _viewport_tools_module()
    current_thread = module.QtCore.QThread.currentThread()
    canvas = SimpleNamespace(
        width=lambda: 1280,
        height=lambda: 720,
        isVisible=lambda: True,
    )
    viewport = SimpleNamespace(
        canvas=canvas,
        camera=object(),
        measurement_settings=SimpleNamespace(
            minor_grid_spacing=10.0,
            major_grid_spacing=100.0,
        ),
        display_options=SimpleNamespace(show_grid=False),
    )
    window = SimpleNamespace(
        thread=lambda: current_thread,
        isVisible=lambda: True,
        isMinimized=lambda: False,
        viewport=viewport,
    )

    ready = module.ViewportToolsMixin._ipc_spatial_health(window)
    viewport.measurement_settings = None
    missing_grid = module.ViewportToolsMixin._ipc_spatial_health(window)

    assert ready == {
        "ready": True,
        "mainThreadObserved": True,
        "windowVisible": True,
        "windowMinimized": False,
        "viewport": {
            "stateAvailable": True,
            "visible": True,
            "width": 1280,
            "height": 720,
        },
        "grid": {
            "stateAvailable": True,
            "visible": False,
        },
        "reason": None,
    }
    assert missing_grid["ready"] is False
    assert missing_grid["reason"] == "grid-state-unavailable"


def test_live_gui_observation_does_not_read_widgets_off_the_gui_thread() -> None:
    module = _viewport_tools_module()

    class _OffThreadWindow:
        def thread(self):
            return object()

        def isVisible(self) -> bool:
            raise AssertionError("off-thread QWidget visibility read")

        def isMinimized(self) -> bool:
            raise AssertionError("off-thread QWidget window-state read")

        @property
        def viewport(self):
            raise AssertionError("off-thread QWidget child read")

    readiness = module._observe_spatial_gui(
        _OffThreadWindow()
    ).readiness_payload()

    assert readiness == {
        "ready": False,
        "mainThreadObserved": False,
        "windowVisible": False,
        "windowMinimized": False,
        "viewport": {
            "stateAvailable": False,
            "visible": False,
            "width": 0,
            "height": 0,
        },
        "grid": {
            "stateAvailable": False,
            "visible": False,
        },
        "reason": "gui-main-thread-unobserved",
    }


def _scene_object(
    stable_id: str,
    *,
    position=(0.0, 0.0, 0.0),
    rotation=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    selected=False,
    group_id="",
):
    return SimpleNamespace(
        id=stable_id,
        name=f"Object {stable_id}",
        object_type="model",
        visible=True,
        locked=False,
        selected=selected,
        group_id=group_id,
        transform=SimpleNamespace(
            position=position,
            rotation=rotation,
            scale=scale,
        ),
        pivot=SimpleNamespace(
            position_local=(10.0, 0.0, 0.0),
            rotation_local=(0.0, 0.0, 0.0),
            enabled=True,
        ),
        material_overrides={"body": "body_material"},
        metadata={
            "bounds": {
                "minimum": [-1.0, -2.0, -3.0],
                "maximum": [1.0, 2.0, 3.0],
            }
        },
    )


def _scene(*objects):
    return SimpleNamespace(
        id="scene_0123456789abcdef",
        units={"system_unit": "cm", "display_unit": "cm"},
        objects=list(objects),
        all_objects=lambda: list(objects),
    )


def test_scene_snapshot_is_revisioned_and_declares_coordinate_semantics() -> None:
    module = _snapshot_module()
    first = _scene_object(
        "object_b",
        position=(100.0, 200.0, 300.0),
        rotation=(0.0, 0.0, 90.0),
        scale=(1.0, 2.0, 1.0),
        selected=True,
        group_id="not-a-parent-contract",
    )
    second = _scene_object("object_a")

    snapshot = module.build_scene_spatial_snapshot(
        _scene(first, second),
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
    )

    assert snapshot["schemaVersion"] == "1.0"
    assert snapshot["application"] == {
        "id": "ghoststudio",
        "version": "2.8",
        "apiVersion": "ghoststudio-spatial/v1",
    }
    assert snapshot["sceneRevision"].startswith("sha256:")
    assert snapshot["coordinateFrames"] == [
        {
            "id": "ghoststudio-world",
            "semanticSpace": "world",
            "handedness": "right",
            "metersPerUnit": 0.01,
            "originMeters": [0.0, 0.0, 0.0],
            "basis": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "upAxis": "+Z",
            "forwardAxis": "+Y",
        }
    ]
    assert [row["stableId"] for row in snapshot["entities"]] == [
        "object_a",
        "object_b",
    ]
    entity = snapshot["entities"][1]
    assert "parentStableId" not in entity
    assert snapshot["hierarchy"]["status"] == "unavailable"
    assert entity["localMatrix"][0][3] == 100.0
    assert entity["localMatrix"][1][3] == 200.0
    assert entity["localMatrix"][2][3] == 300.0
    assert entity["bounds"] == first.metadata["bounds"]
    assert snapshot["selection"] == {
        "mode": "object",
        "stableIds": ["object_b"],
    }
    assert any(
        row["kind"] == "semantic-api"
        and row["epistemicStatus"] == "observed"
        for row in snapshot["evidence"]
    )
    assert any(
        row["kind"] == "derived-calculation"
        and row["epistemicStatus"] == "inferred"
        for row in snapshot["evidence"]
    )


def test_scene_revision_is_order_independent_and_changes_with_transform() -> None:
    module = _snapshot_module()
    first = _scene_object("object_a")
    second = _scene_object("object_b")

    forward = module.build_scene_spatial_snapshot(
        _scene(first, second),
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
    )
    reverse = module.build_scene_spatial_snapshot(
        _scene(second, first),
        application_version="2.8",
        captured_at="2026-07-25T21:30:01Z",
    )
    changed = module.build_scene_spatial_snapshot(
        _scene(
            _scene_object("object_a", position=(1.0, 0.0, 0.0)),
            second,
        ),
        application_version="2.8",
        captured_at="2026-07-25T21:30:02Z",
    )

    assert forward["sceneRevision"] == reverse["sceneRevision"]
    assert forward["sceneRevision"] != changed["sceneRevision"]


def test_scene_snapshot_selection_redaction_and_hierarchy_are_truthful() -> None:
    module = _snapshot_module()
    scene = _scene(_scene_object("object_a", selected=True))

    redacted = module.build_scene_spatial_snapshot(
        scene,
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
        include_selection=False,
        include_hierarchy=False,
    )
    requested = module.build_scene_spatial_snapshot(
        scene,
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
        include_selection=True,
        include_hierarchy=True,
    )

    assert "selection" not in redacted
    assert "selected" not in redacted["entities"][0]
    assert "hierarchy" not in redacted
    assert "parentStableId" not in redacted["entities"][0]
    assert requested["selection"]["stableIds"] == ["object_a"]
    assert requested["entities"][0]["selected"] is True
    assert requested["hierarchy"] == {
        "status": "unavailable",
        "reason": "scene-parent-hierarchy-unavailable",
    }
    assert "parentStableId" not in requested["entities"][0]
    assert redacted["sceneRevision"] == requested["sceneRevision"]


def test_scene_snapshot_rejects_source_collections_above_the_work_bound() -> None:
    module = _snapshot_module()
    calls: list[bool] = []

    class _OversizedScene:
        id = "oversized_scene"
        units = {"system_unit": "cm", "display_unit": "cm"}
        objects = [object()] * (module.MAX_SPATIAL_ENTITIES + 1)
        model_instances = []

        def all_objects(self):
            calls.append(True)
            return self.objects

    with pytest.raises(ValueError, match="entity work bound"):
        module.build_scene_spatial_snapshot(
            _OversizedScene(),
            application_version="2.8",
        )

    assert calls == []


def test_spatial_evidence_gaps_are_explicit_not_inferred_from_a_screenshot() -> None:
    module = _snapshot_module()
    snapshot = module.build_scene_spatial_snapshot(
        _scene(_scene_object("object_a")),
        application_version="2.8",
        captured_at="2026-07-25T21:30:00Z",
    )

    gaps = module.spatial_evidence_gaps(snapshot)

    assert gaps["schema"] == "ghoststudio-spatial-evidence-gaps/v1"
    assert "viewport-camera-matrices-unavailable" in gaps["gaps"]
    assert "capture-unavailable" in gaps["gaps"]
    assert "scene-parent-hierarchy-unavailable" in gaps["gaps"]
    assert gaps["screenshotProvesGuiAction"] is False


def test_live_evidence_gaps_survive_unavailable_grid_state() -> None:
    module = _viewport_tools_module()
    current_thread = module.QtCore.QThread.currentThread()

    class _Window(module.ViewportToolsMixin):
        pass

    window = _Window()
    window.thread = lambda: current_thread
    window.isVisible = lambda: True
    window.isMinimized = lambda: False
    window.scene_manager = SimpleNamespace(
        active_scene=_scene(_scene_object("object_a"))
    )
    window.viewport = SimpleNamespace(
        canvas=SimpleNamespace(
            width=lambda: 1280,
            height=lambda: 720,
            isVisible=lambda: True,
        ),
        camera=object(),
        measurement_settings=None,
        display_options=SimpleNamespace(show_grid=True),
    )

    with pytest.raises(RuntimeError, match="grid-state-unavailable"):
        window._ipc_spatial_snapshot({})

    gaps = window._ipc_spatial_evidence_gaps({})

    assert gaps["sceneRevision"].startswith("sha256:")
    assert "grid-state-unavailable" in gaps["gaps"]
    assert "capture-unavailable" in gaps["gaps"]
    assert len(gaps["gaps"]) == len(set(gaps["gaps"]))
    assert len(gaps["gaps"]) <= 8
    assert gaps["screenshotProvesGuiAction"] is False


def test_narrow_mcp_catalog_has_exactly_four_spatial_tools() -> None:
    module = _spatial_mcp_module()
    server = module.GhostStudioSpatialMcpServer()

    initialized = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
    )
    catalog = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
    )

    assert initialized["result"]["protocolVersion"] == "2025-11-25"
    assert initialized["result"]["capabilities"] == {
        "tools": {"listChanged": False}
    }
    tools = catalog["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "ghoststudio_health",
        "ghoststudio_spatial_snapshot",
        "ghoststudio_capture",
        "ghoststudio_evidence_gaps",
    ]
    assert all(
        tool["inputSchema"]["additionalProperties"] is False
        for tool in tools
    )
    health, snapshot, _capture, _gaps = tools
    assert health["outputSchema"]["additionalProperties"] is False
    assert snapshot["outputSchema"]["additionalProperties"] is False
    assert snapshot["outputSchema"]["properties"]["snapshot"][
        "additionalProperties"
    ] is False
    hierarchy = snapshot["inputSchema"]["properties"]["includeHierarchy"]
    assert "unavailable" in hierarchy["description"].casefold()


def test_narrow_mcp_validates_arguments_before_contacting_gui() -> None:
    module = _spatial_mcp_module()
    contacted: list[bool] = []

    class _Client:
        def call(self, _name, _arguments):
            contacted.append(True)
            return {"status": "ok"}

    server = module.GhostStudioSpatialMcpServer(client_factory=_Client)
    response = server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_capture",
                "arguments": {"captureId": "../outside"},
            },
        }
    )

    assert response["result"]["isError"] is True
    assert "invalid-arguments" in response["result"]["content"][0]["text"]
    assert contacted == []


def test_narrow_client_signs_exact_bounded_named_pipe_request() -> None:
    module = _spatial_mcp_module()
    auth = _auth_module()
    credentials = _credentials(auth, expires_at=4_000_000_000)
    descriptor = auth.SpatialSessionDescriptor(
        credentials=credentials,
        port=None,
        created_at=1_000,
        pid=1234,
        transport="windows-named-pipe-v1",
        pipe_name=(
            r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
        ),
        schema="ghoststudio-spatial-session/v2",
    )
    observed: dict[str, object] = {}

    def _pipe_caller(pipe_name, **kwargs):
        observed["pipe_name"] = pipe_name
        observed.update(kwargs)
        return module._SPATIAL_PIPE.SpatialPipeResponse(
            status=200,
            content_type="application/json",
            body=(
                b'{"status":"ok","snapshot":'
                b'{"sceneRevision":"scene:1"}}'
            ),
        )

    client = module.GhostStudioSpatialClient(
        session_path=Path("C:/private/ghoststudio-session.json"),
        descriptor_loader=lambda _path: descriptor,
        pipe_caller=_pipe_caller,
        environ={
            auth.SPATIAL_TRANSPORT_ENV: auth.WINDOWS_SPATIAL_TRANSPORT
        },
    )
    result = client.call(
        "ghoststudio_spatial_snapshot",
        {"includeSelection": True},
    )

    assert result["snapshot"]["sceneRevision"] == "scene:1"
    assert observed["pipe_name"] == descriptor.pipe_name
    assert observed["path"] == "/api/mcpstudio/spatial-snapshot"
    assert observed["method"] == "POST"
    assert observed["expected_server_pid"] == 1234
    assert observed["response_secret"] == credentials.secret
    body = observed["body"]
    assert body == b'{"includeSelection":true}'
    headers = observed["headers"]
    auth.SpatialRequestAuthenticator(
        credentials,
        now=lambda: int(headers["X-GhostStudio-Timestamp"]),
    ).verify(
        headers=headers,
        method="POST",
        path="/api/mcpstudio/spatial-snapshot",
        body=body,
    )


def test_narrow_client_reloads_changed_descriptor_and_retries_pipe_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _spatial_mcp_module()
    auth = _auth_module()
    initial_credentials = auth.SpatialSessionCredentials(
        session_id="session_initial_0123456789",
        secret=b"i" * 32,
        expires_at=4_000_000_000,
    )
    replacement_credentials = auth.SpatialSessionCredentials(
        session_id="session_replaced_01234567",
        secret=b"r" * 32,
        expires_at=4_000_000_000,
    )
    initial = auth.SpatialSessionDescriptor(
        credentials=initial_credentials,
        port=None,
        created_at=1_000,
        pid=1111,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        pipe_name=(
            r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
        ),
        schema="ghoststudio-spatial-session/v2",
    )
    replacement = auth.SpatialSessionDescriptor(
        credentials=replacement_credentials,
        port=None,
        created_at=1_001,
        pid=2222,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        pipe_name=(
            r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            "0123456789abcdefghijklmnopqrstuvwxyzABCDEFG"
        ),
        schema="ghoststudio-spatial-session/v2",
    )
    descriptors = iter((initial, replacement))
    loader_calls: list[Path] = []
    pipe_calls: list[tuple[str, dict[str, object]]] = []
    clock = iter((100.0, 100.0, 102.0))
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
        raising=False,
    )

    def _load(path):
        loader_calls.append(path)
        return next(descriptors)

    def _pipe_caller(pipe_name, **kwargs):
        pipe_calls.append((pipe_name, kwargs))
        if len(pipe_calls) == 1:
            raise module.SpatialPipeError("pipe-unavailable")
        return module._SPATIAL_PIPE.SpatialPipeResponse(
            status=200,
            content_type="application/json",
            body=b'{"status":"ok"}',
        )

    client = module.GhostStudioSpatialClient(
        session_path=Path("C:/private/ghoststudio-session.json"),
        descriptor_loader=_load,
        pipe_caller=_pipe_caller,
        environ={
            auth.SPATIAL_TRANSPORT_ENV: auth.WINDOWS_SPATIAL_TRANSPORT
        },
        timeout_seconds=5.0,
    )

    assert client.call("ghoststudio_health", {})["status"] == "ok"
    assert len(loader_calls) == 2
    assert [call[0] for call in pipe_calls] == [
        initial.pipe_name,
        replacement.pipe_name,
    ]
    assert [call[1]["timeout_seconds"] for call in pipe_calls] == [5.0, 3.0]
    assert pipe_calls[1][1]["expected_server_pid"] == replacement.pid
    assert (
        pipe_calls[1][1]["response_secret"]
        == replacement_credentials.secret
    )
    auth.SpatialRequestAuthenticator(
        replacement_credentials,
        now=lambda: int(
            pipe_calls[1][1]["headers"]["X-GhostStudio-Timestamp"]
        ),
    ).verify(
        headers=pipe_calls[1][1]["headers"],
        method="GET",
        path="/api/mcpstudio/health",
        body=b"",
    )


def test_narrow_client_does_not_retry_failed_unchanged_pipe_descriptor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _spatial_mcp_module()
    auth = _auth_module()
    descriptor = auth.SpatialSessionDescriptor(
        credentials=_credentials(auth, expires_at=4_000_000_000),
        port=None,
        created_at=1_000,
        pid=1234,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        pipe_name=(
            r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
        ),
        schema="ghoststudio-spatial-session/v2",
    )
    loader_calls: list[Path] = []
    pipe_calls: list[str] = []
    clock = iter((100.0, 100.0))
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock)),
        raising=False,
    )

    def _load(path):
        loader_calls.append(path)
        return descriptor

    def _pipe_caller(pipe_name, **_kwargs):
        pipe_calls.append(pipe_name)
        raise module.SpatialPipeError("pipe-unavailable")

    client = module.GhostStudioSpatialClient(
        session_path=Path("C:/private/ghoststudio-session.json"),
        descriptor_loader=_load,
        pipe_caller=_pipe_caller,
        environ={
            auth.SPATIAL_TRANSPORT_ENV: auth.WINDOWS_SPATIAL_TRANSPORT
        },
        timeout_seconds=5.0,
    )

    with pytest.raises(module.SpatialAdapterError) as failure:
        client.call("ghoststudio_health", {})

    assert failure.value.code == "spatial-request-failed"
    assert len(loader_calls) == 2
    assert pipe_calls == [descriptor.pipe_name]
    assert descriptor.credentials.secret.hex() not in str(failure.value)


def test_narrow_client_fails_closed_without_sealed_pipe_transport_marker() -> None:
    module = _spatial_mcp_module()
    auth = _auth_module()
    descriptor = auth.SpatialSessionDescriptor(
        credentials=_credentials(auth, expires_at=4_000_000_000),
        port=None,
        created_at=1_000,
        pid=1234,
        transport="windows-named-pipe-v1",
        pipe_name=(
            r"\\.\pipe\LOCAL\GhostStudioSpatial-"
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ"
        ),
        schema="ghoststudio-spatial-session/v2",
    )
    contacted: list[object] = []
    client = module.GhostStudioSpatialClient(
        session_path=Path("C:/private/ghoststudio-session.json"),
        descriptor_loader=lambda _path: descriptor,
        pipe_caller=lambda *_args, **_kwargs: contacted.append(True),
        environ={},
    )

    with pytest.raises(module.SpatialAdapterError) as unavailable:
        client.call("ghoststudio_health", {})

    assert unavailable.value.code == "ghoststudio-unavailable"
    assert contacted == []


def test_narrow_mcp_returns_safe_error_when_session_is_unavailable() -> None:
    module = _spatial_mcp_module()

    class _UnavailableClient:
        def call(self, _name, _arguments):
            raise module.SpatialAdapterError("ghoststudio-unavailable")

    response = module.GhostStudioSpatialMcpServer(
        client_factory=_UnavailableClient
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_health",
                "arguments": {},
            },
        }
    )

    assert response["result"]["isError"] is True
    text = response["result"]["content"][0]["text"]
    assert "ghoststudio-unavailable" in text
    assert "secret" not in text.lower()


def test_narrow_mcp_rejects_snapshot_without_live_gui_markers() -> None:
    module = _spatial_mcp_module()

    class _InvalidClient:
        def call(self, _name, _arguments):
            return {
                "status": "ok",
                "schema": "ghoststudio-spatial-response/v1",
                "snapshot": {
                    "schemaVersion": "1.0",
                    "sceneRevision": "sha256:" + ("a" * 64),
                    "entities": [],
                },
            }

    response = module.GhostStudioSpatialMcpServer(
        client_factory=_InvalidClient
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_spatial_snapshot",
                "arguments": {},
            },
        }
    )

    assert response["result"]["isError"] is True
    assert "invalid-response" in response["result"]["content"][0]["text"]


def test_narrow_mcp_health_preserves_truthful_unready_gui_state() -> None:
    module = _spatial_mcp_module()

    class _HealthClient:
        def call(self, _name, _arguments):
            return {
                "status": "ok",
                "schema": "ghoststudio-spatial-health/v2",
                "program": "GhostStudio",
                "endpoint": {
                    "authenticated": True,
                    "transport": "loopback-http",
                },
                "gui": _valid_gui_readiness(ready=False),
                "capabilities": [
                    "health",
                    "spatial-snapshot",
                    "capture",
                    "evidence-gaps",
                ],
            }

    response = module.GhostStudioSpatialMcpServer(
        client_factory=_HealthClient
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_health",
                "arguments": {},
            },
        }
    )

    result = response["result"]
    assert result.get("isError") is not True
    assert result["structuredContent"]["endpoint"]["authenticated"] is True
    assert result["structuredContent"]["gui"]["ready"] is False


def test_narrow_mcp_accepts_gui_ready_snapshot_with_full_redaction() -> None:
    module = _spatial_mcp_module()

    class _ValidClient:
        def call(self, _name, _arguments):
            return {
                "status": "ok",
                "schema": "ghoststudio-spatial-response/v1",
                "snapshot": _valid_spatial_snapshot(
                    include_bounds=False,
                    include_hierarchy=False,
                    include_selection=False,
                ),
            }

    response = module.GhostStudioSpatialMcpServer(
        client_factory=_ValidClient
    ).dispatch(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "ghoststudio_spatial_snapshot",
                "arguments": {
                    "includeBounds": False,
                    "includeHierarchy": False,
                    "includeSelection": False,
                },
            },
        }
    )

    result = response["result"]
    assert result.get("isError") is not True
    snapshot = result["structuredContent"]["snapshot"]
    assert "selection" not in snapshot
    assert "hierarchy" not in snapshot
    assert "selected" not in snapshot["entities"][0]
    assert "bounds" not in snapshot["entities"][0]
    assert snapshot["guiReadiness"]["ready"] is True
