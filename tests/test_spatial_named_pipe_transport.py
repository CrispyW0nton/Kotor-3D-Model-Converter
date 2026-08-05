"""Focused contracts for the Windows Ghost Studio spatial named pipe."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
PIPE_MODULE = (
    ROOT
    / "native"
    / "GhostRigger.Core.Automation"
    / "Python"
    / "src"
    / "ipc"
    / "spatial_pipe.py"
)
AUTH_MODULE = PIPE_MODULE.with_name("spatial_auth.py")
PACKAGE_SID = (
    "S-1-15-2-1229027098-1376173174-3902671414-3221589281-"
    "1354859120-752965424-969501979"
)


def _pipe_module():
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_pipe_test_module",
        PIPE_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _auth_module():
    spec = importlib.util.spec_from_file_location(
        "ghoststudio_spatial_pipe_auth_test_module",
        AUTH_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _route_full_trust_test_client_to_server_namespace(
    module,
    monkeypatch: pytest.MonkeyPatch,
    *,
    pipe_alias: str,
) -> str:
    """Let full-trust transport tests reach the AppContainer-owned pipe path."""

    server_name = module._windows_app_container_server_pipe_name(
        pipe_alias,
        PACKAGE_SID,
        session_id=module._current_windows_session_id(),
    )
    validate_alias = module.validate_windows_spatial_pipe_name

    def _resolve_test_client_name(value: object) -> str:
        assert validate_alias(value) == pipe_alias
        return server_name

    monkeypatch.setattr(
        module,
        "validate_windows_spatial_pipe_name",
        _resolve_test_client_name,
    )
    return server_name


def test_pipe_name_is_unpredictable_session_local_and_strict() -> None:
    module = _pipe_module()

    first = module.create_windows_spatial_pipe_name()
    second = module.create_windows_spatial_pipe_name()

    assert first.startswith(r"\\.\pipe\LOCAL\GhostStudioSpatial-")
    assert second.startswith(r"\\.\pipe\LOCAL\GhostStudioSpatial-")
    assert first != second
    assert module.validate_windows_spatial_pipe_name(first) == first
    for invalid in (
        r"\\.\pipe\GhostStudioSpatial-token",
        r"\\server\pipe\LOCAL\GhostStudioSpatial-token",
        r"\\.\pipe\LOCAL\GhostStudioSpatial-..\escape",
    ):
        with pytest.raises(module.SpatialPipeError):
            module.validate_windows_spatial_pipe_name(invalid)


def test_server_creation_name_targets_the_exact_appcontainer_namespace() -> None:
    module = _pipe_module()
    alias = (
        r"\\.\pipe\LOCAL\GhostStudioSpatial-"
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFG"
    )

    server_name = module._windows_app_container_server_pipe_name(
        alias,
        PACKAGE_SID,
        session_id=42,
    )

    assert server_name == (
        rf"\\.\pipe\Sessions\42\AppContainerNamedObjects\{PACKAGE_SID}"
        r"\GhostStudioSpatial-0123456789abcdefghijklmnopqrstuvwxyzABCDEFG"
    )
    assert module.validate_windows_spatial_pipe_name(alias) == alias


def test_pipe_request_frame_round_trip_is_strict_and_bounded() -> None:
    module = _pipe_module()
    headers = {
        "X-GhostStudio-Session": "session_0123456789abcdef",
        "X-GhostStudio-Timestamp": "1000",
        "X-GhostStudio-Nonce": "nonce_0123456789abcdef",
        "X-GhostStudio-Signature": "a" * 64,
    }

    encoded = module.encode_spatial_pipe_request(
        method="POST",
        path="/api/mcpstudio/spatial-snapshot",
        headers=headers,
        body=b'{"includeSelection":false}',
    )
    decoded = module.decode_spatial_pipe_request(encoded)

    assert decoded.method == "POST"
    assert decoded.path == "/api/mcpstudio/spatial-snapshot"
    assert decoded.headers == headers
    assert decoded.body == b'{"includeSelection":false}'

    payload = json.loads(encoded.decode("utf-8"))
    payload["unexpected"] = True
    with pytest.raises(module.SpatialPipeError):
        module.decode_spatial_pipe_request(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
    with pytest.raises(module.SpatialPipeError):
        module.encode_spatial_pipe_request(
            method="POST",
            path="/api/mcpstudio/spatial-snapshot",
            headers=headers,
            body=b"x" * (module.MAX_REQUEST_BODY_BYTES + 1),
        )


def test_pipe_length_prefix_is_unsigned_big_endian_and_rejects_bad_lengths() -> None:
    module = _pipe_module()
    framed = module.pack_spatial_pipe_frame(b"abc", limit=8)

    assert framed == b"\x00\x00\x00\x03abc"
    assert module.unpack_spatial_pipe_frame(framed, limit=8) == b"abc"
    for invalid in (
        b"\x00\x00\x00\x03ab",
        b"\x00\x00\x00\x02abc",
        b"\x00\x00\x00\x09" + (b"x" * 9),
        b"\x00\x00\x00\x00",
    ):
        with pytest.raises(module.SpatialPipeError):
            module.unpack_spatial_pipe_frame(invalid, limit=8)


def test_pipe_response_hmac_binds_request_status_and_body() -> None:
    module = _pipe_module()
    request = module.decode_spatial_pipe_request(
        module.encode_spatial_pipe_request(
            method="GET",
            path="/api/mcpstudio/health",
            headers={
                "X-GhostStudio-Session": "session_0123456789abcdef",
                "X-GhostStudio-Timestamp": "1000",
                "X-GhostStudio-Nonce": "nonce_0123456789abcdef",
                "X-GhostStudio-Signature": "a" * 64,
            },
            body=b"",
        )
    )
    response = module.SpatialPipeResponse(
        status=200,
        content_type="application/json",
        body=b'{"status":"ok"}',
    )
    encoded = module.encode_spatial_pipe_response(
        response,
        request=request,
        secret=b"s" * 32,
    )

    assert (
        module.decode_spatial_pipe_response(
            encoded,
            request=request,
            secret=b"s" * 32,
        )
        == response
    )
    payload = json.loads(encoded.decode("utf-8"))
    payload["bodyBase64"] = "eyJzdGF0dXMiOiJub3Qtb2sifQ=="
    with pytest.raises(module.SpatialPipeError):
        module.decode_spatial_pipe_response(
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            request=request,
            secret=b"s" * 32,
        )


def test_named_pipe_descriptor_v2_round_trip_is_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe_module = _pipe_module()
    auth = _auth_module()
    descriptor_path = tmp_path / "private" / "ghoststudio-session.json"
    pipe_name = pipe_module.create_windows_spatial_pipe_name()
    monkeypatch.setenv(
        auth.SPATIAL_TRANSPORT_ENV,
        auth.WINDOWS_SPATIAL_TRANSPORT,
    )
    monkeypatch.setenv(auth.SPATIAL_APP_CONTAINER_SID_ENV, PACKAGE_SID)
    no_security = lambda _path, _is_directory: None

    published = auth.publish_spatial_session_descriptor(
        descriptor_path,
        pipe_name=pipe_name,
        transport=auth.WINDOWS_SPATIAL_TRANSPORT,
        now=lambda: 1_000,
        ttl_seconds=3_600,
        security_hook=no_security,
    )
    loaded = auth.load_spatial_session_descriptor(
        descriptor_path,
        now=lambda: 1_001,
        security_audit=no_security,
    )

    assert loaded == published
    assert loaded.schema == "ghoststudio-spatial-session/v2"
    assert loaded.transport == "windows-named-pipe-v1"
    assert loaded.pipe_name == pipe_name
    assert loaded.port is None
    payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema",
        "transport",
        "pipeName",
        "sessionId",
        "secret",
        "createdAt",
        "expiresAt",
        "pid",
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")
def test_real_named_pipe_round_trip_uses_local_reject_remote_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _pipe_module()
    observed: dict[str, object] = {}

    def _handle(request):
        observed["request"] = request
        return module.SpatialPipeResponse(
            status=200,
            content_type="application/json",
            body=b'{"status":"ok","schema":"test-response/v1"}',
        )

    server = module.WindowsSpatialNamedPipeServer(
        package_sid=PACKAGE_SID,
        request_handler=_handle,
        response_secret=b"s" * 32,
        client_identity_verifier=lambda _handle: None,
        io_timeout_seconds=2.0,
    )
    server.start()
    try:
        _route_full_trust_test_client_to_server_namespace(
            module,
            monkeypatch,
            pipe_alias=server.pipe_name,
        )
        response = module.call_windows_spatial_pipe(
            server.pipe_name,
            method="GET",
            path="/api/mcpstudio/health",
            headers={
                "X-GhostStudio-Session": "session_0123456789abcdef",
                "X-GhostStudio-Timestamp": "1000",
                "X-GhostStudio-Nonce": "nonce_0123456789abcdef",
                "X-GhostStudio-Signature": "b" * 64,
            },
            body=b"",
            timeout_seconds=2.0,
            expected_server_pid=os.getpid(),
            response_secret=b"s" * 32,
        )
    finally:
        server.stop()

    assert response.status == 200
    assert response.content_type == "application/json"
    assert json.loads(response.body)["status"] == "ok"
    request = observed["request"]
    assert request.method == "GET"
    assert request.path == "/api/mcpstudio/health"
    assert request.body == b""
    assert server.security_contract == {
        "pipePrefix": "\\\\.\\pipe\\LOCAL\\",
        "rejectRemoteClients": True,
        "daclPrincipals": ("current-user", "SYSTEM", PACKAGE_SID),
        "sessionScoped": True,
    }


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")
def test_named_pipe_accept_remains_available_after_several_idle_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _pipe_module()
    contacted: list[object] = []

    def _handle(request):
        contacted.append(request)
        return module.SpatialPipeResponse(
            status=200,
            content_type="application/json",
            body=b'{"status":"ok"}',
        )

    server = module.WindowsSpatialNamedPipeServer(
        package_sid=PACKAGE_SID,
        request_handler=_handle,
        response_secret=b"s" * 32,
        client_identity_verifier=lambda _handle: None,
        io_timeout_seconds=2.0,
    )
    server.start()
    try:
        time.sleep(3.0)
        assert server.is_running
        _route_full_trust_test_client_to_server_namespace(
            module,
            monkeypatch,
            pipe_alias=server.pipe_name,
        )
        response = module.call_windows_spatial_pipe(
            server.pipe_name,
            method="GET",
            path="/api/mcpstudio/health",
            headers={
                "X-GhostStudio-Session": "session_0123456789abcdef",
                "X-GhostStudio-Timestamp": "1000",
                "X-GhostStudio-Nonce": "nonce_idle_0123456789abc",
                "X-GhostStudio-Signature": "b" * 64,
            },
            body=b"",
            timeout_seconds=2.0,
            expected_server_pid=os.getpid(),
            response_secret=b"s" * 32,
        )
    finally:
        server.stop()

    assert response.status == 200
    assert len(contacted) == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")
def test_named_pipe_rejects_a_full_trust_client_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _pipe_module()
    contacted: list[object] = []
    server = module.WindowsSpatialNamedPipeServer(
        package_sid=PACKAGE_SID,
        request_handler=lambda request: contacted.append(request),
        response_secret=b"s" * 32,
        io_timeout_seconds=1.0,
    )
    server.start()
    try:
        _route_full_trust_test_client_to_server_namespace(
            module,
            monkeypatch,
            pipe_alias=server.pipe_name,
        )
        with pytest.raises(module.SpatialPipeError):
            module.call_windows_spatial_pipe(
                server.pipe_name,
                method="GET",
                path="/api/mcpstudio/health",
                headers={
                    "X-GhostStudio-Session": "session_0123456789abcdef",
                    "X-GhostStudio-Timestamp": "1000",
                    "X-GhostStudio-Nonce": "nonce_0123456789abcdef",
                    "X-GhostStudio-Signature": "b" * 64,
                },
                body=b"",
                timeout_seconds=1.0,
                expected_server_pid=os.getpid(),
                response_secret=b"s" * 32,
            )
    finally:
        server.stop()

    assert contacted == []


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")
def test_named_pipe_fatal_identity_failure_terminates_server_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _pipe_module()
    contacted: list[object] = []
    fatal_errors: list[BaseException] = []

    def _fatal_identity(_handle) -> None:
        raise module.SpatialPipeFatalError("pipe-security-failed")

    server = module.WindowsSpatialNamedPipeServer(
        package_sid=PACKAGE_SID,
        request_handler=lambda request: contacted.append(request),
        response_secret=b"s" * 32,
        client_identity_verifier=_fatal_identity,
        fatal_error_handler=fatal_errors.append,
        io_timeout_seconds=1.0,
    )
    server.start()
    try:
        _route_full_trust_test_client_to_server_namespace(
            module,
            monkeypatch,
            pipe_alias=server.pipe_name,
        )
        with pytest.raises(module.SpatialPipeError):
            module.call_windows_spatial_pipe(
                server.pipe_name,
                method="GET",
                path="/api/mcpstudio/health",
                headers={
                    "X-GhostStudio-Session": "session_0123456789abcdef",
                    "X-GhostStudio-Timestamp": "1000",
                    "X-GhostStudio-Nonce": "nonce_fatal_0123456789ab",
                    "X-GhostStudio-Signature": "b" * 64,
                },
                body=b"",
                timeout_seconds=1.0,
                expected_server_pid=os.getpid(),
                response_secret=b"s" * 32,
            )
        deadline = time.monotonic() + 2.0
        while server.is_running and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        server.stop()

    assert not server.is_running
    assert isinstance(server._startup_error, module.SpatialPipeFatalError)
    assert fatal_errors == [server._startup_error]
    assert contacted == []


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe integration")
def test_named_pipe_client_rejects_unexpected_server_pid_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _pipe_module()
    contacted: list[object] = []
    server = module.WindowsSpatialNamedPipeServer(
        package_sid=PACKAGE_SID,
        request_handler=lambda request: contacted.append(request),
        response_secret=b"s" * 32,
        client_identity_verifier=lambda _handle: None,
        io_timeout_seconds=1.0,
    )
    server.start()
    try:
        _route_full_trust_test_client_to_server_namespace(
            module,
            monkeypatch,
            pipe_alias=server.pipe_name,
        )
        with pytest.raises(module.SpatialPipeError):
            module.call_windows_spatial_pipe(
                server.pipe_name,
                method="GET",
                path="/api/mcpstudio/health",
                headers={
                    "X-GhostStudio-Session": "session_0123456789abcdef",
                    "X-GhostStudio-Timestamp": "1000",
                    "X-GhostStudio-Nonce": "nonce_0123456789abcdef",
                    "X-GhostStudio-Signature": "b" * 64,
                },
                body=b"",
                timeout_seconds=1.0,
                expected_server_pid=os.getpid() + 1,
                response_secret=b"s" * 32,
            )
    finally:
        server.stop()

    assert contacted == []
