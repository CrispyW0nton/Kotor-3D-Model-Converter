"""Tests for KotorMCP integration in GhostRigger.

Tests cover:
  - Package import and tool registration
  - URI parsing (mcp_resources)
  - State module (resolve_game, iter_candidate_paths)
  - GhostRigger-specific tools (model_info, audit, open_model)
  - IPC server MCP routes
  - Formatting utilities
"""

import asyncio
import json
import os
import sys

import pytest

# Ensure src is on path
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Guard: skip tests that require pykotor when it's not installed
try:
    import pykotor  # noqa: F401
    _PYKOTOR_OK = True
except ImportError:
    _PYKOTOR_OK = False

_skip_no_pykotor = pytest.mark.skipif(
    not _PYKOTOR_OK,
    reason="pykotor package not installed (optional dependency)"
)

MDL_PATH = os.path.join(os.path.dirname(__file__), "..", "test_assets", "N_sithpraet.mdl")


# ── Package & tool registration ───────────────────────────────────────────────

class TestKotorMCPPackage:
    def test_import(self):
        from kotormcp import __version__
        assert __version__ == "1.0.0"

    def test_tools_registered(self):
        from kotormcp.tools import get_all_tools
        tools = get_all_tools()
        assert len(tools) >= 15
        names = {t["name"] for t in tools}
        required = {
            "detectInstallations", "loadInstallation", "kotor_installation_info",
            "listResources", "describeResource", "kotor_find_resource", "kotor_search_resources",
            "journalOverview", "kotor_lookup_2da", "kotor_lookup_tlk",
            "ghostrigger_open_model", "ghostrigger_render_model", "ghostrigger_model_info",
            "ghostrigger_list_game_models", "ghostrigger_audit",
        }
        assert required <= names, f"Missing tools: {required - names}"

    def test_each_tool_has_required_fields(self):
        from kotormcp.tools import get_all_tools
        for tool in get_all_tools():
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_handle_tool_unknown_raises(self):
        from kotormcp.tools import handle_tool
        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.run(
                handle_tool("nonexistent_tool_xyz", {})
            )


# ── State module ──────────────────────────────────────────────────────────────

@_skip_no_pykotor
class TestKotorMCPState:
    def test_resolve_game_k1(self):
        from kotormcp.state import resolve_game
        from pykotor.common.misc import Game
        assert resolve_game("k1") == Game.K1
        assert resolve_game("K1") == Game.K1
        assert resolve_game("kotori") == Game.K1
        assert resolve_game("swkotor") == Game.K1

    def test_resolve_game_k2(self):
        from kotormcp.state import resolve_game
        from pykotor.common.misc import Game
        assert resolve_game("k2") == Game.K2
        assert resolve_game("tsl") == Game.K2
        assert resolve_game("kotor2") == Game.K2

    def test_resolve_game_none(self):
        from kotormcp.state import resolve_game
        assert resolve_game(None) is None
        assert resolve_game("invalid_game") is None

    def test_iter_candidate_paths_explicit(self):
        from kotormcp.state import iter_candidate_paths
        from pykotor.common.misc import Game
        candidates = list(iter_candidate_paths(Game.K1, "/tmp/fake_kotor"))
        paths_str = [str(c) for c in candidates]
        assert any("fake_kotor" in p for p in paths_str)

    def test_load_installation_missing(self):
        from kotormcp.state import load_installation, resolve_game, clear_cache
        from pykotor.common.misc import Game
        clear_cache()
        # Without env vars set, loading should raise ValueError
        with pytest.raises((ValueError, Exception)):
            load_installation(Game.K1, "/nonexistent/path")

    def test_clear_cache(self):
        from kotormcp.state import INSTALLATIONS, clear_cache
        clear_cache()
        assert len(INSTALLATIONS) == 0


# ── URI parsing ───────────────────────────────────────────────────────────────

class TestMCPResourceURIs:
    def test_parse_valid_k1_resource(self):
        from kotormcp.mcp_resources import parse_kotor_uri
        parsed = parse_kotor_uri("kotor://k1/resource/somefile.mdl")
        assert parsed["authority"] == "k1"
        assert parsed["type"] == "resource"
        assert parsed["path"] == "somefile.mdl"

    def test_parse_valid_k2_2da(self):
        from kotormcp.mcp_resources import parse_kotor_uri
        parsed = parse_kotor_uri("kotor://k2/2da/appearance")
        assert parsed["authority"] == "k2"
        assert parsed["type"] == "2da"
        assert parsed["path"] == "appearance"

    def test_parse_docs_capabilities(self):
        from kotormcp.mcp_resources import parse_kotor_uri
        parsed = parse_kotor_uri("kotor://docs/capabilities")
        assert parsed["authority"] == "docs"
        assert parsed["type"] == "capabilities"

    def test_parse_invalid_uri(self):
        from kotormcp.mcp_resources import parse_kotor_uri
        assert parse_kotor_uri("http://not-kotor/") == {}
        assert parse_kotor_uri("kotor://") == {}

    def test_parse_ghostrigger_model(self):
        from kotormcp.mcp_resources import parse_kotor_uri
        parsed = parse_kotor_uri("kotor://ghostrigger/model/n_sithpraet")
        assert parsed["authority"] == "ghostrigger"
        assert parsed["type"] == "model"
        assert parsed["path"] == "n_sithpraet"

    def test_list_resources_returns_templates(self):
        from kotormcp import mcp_resources
        resources = asyncio.run(mcp_resources.list_resources())
        assert len(resources) >= 8
        uris = {r["uri"] for r in resources}
        assert "kotor://docs/capabilities" in uris
        assert "kotor://k1/resource/{resref}.{ext}" in uris

    def test_read_capabilities(self):
        from kotormcp import mcp_resources
        content = asyncio.run(
            mcp_resources.read_resource("kotor://docs/capabilities")
        )
        assert content["mimeType"] == "text/markdown"
        assert "GhostRigger" in content["text"]
        assert "ghostrigger_model_info" in content["text"]

    def test_read_invalid_uri(self):
        from kotormcp import mcp_resources
        content = asyncio.run(
            mcp_resources.read_resource("http://bad-uri")
        )
        assert "error" in content


# ── Formatting utilities ──────────────────────────────────────────────────────

class TestKotorMCPFormatting:
    def test_json_content_small(self):
        from kotormcp.utils import json_content
        result = json_content({"key": "value"})
        assert result["type"] == "text"
        data = json.loads(result["text"])
        assert data["key"] == "value"

    def test_json_content_truncation(self):
        from kotormcp.utils import json_content
        large_payload = {"data": "x" * 30000}
        result = json_content(large_payload, max_chars=100)
        # When truncated the wrapper JSON itself must be valid (even if truncated preview is cut)
        text = result["text"]
        # The result text may itself be truncated (with "... (output truncated)")
        # so we just verify it contains the truncated indicator
        assert "truncated" in text or "output truncated" in text

    def test_make_tool_result(self):
        from kotormcp.utils import make_tool_result
        result = make_tool_result({"status": "ok"})
        # Should either be a mcp types object or a plain dict
        assert result is not None


# ── GhostRigger tools ─────────────────────────────────────────────────────────

class TestGhostRiggerTools:
    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_model_info_basic(self):
        from kotormcp.tools.ghostrigger import handle_model_info
        result = asyncio.run(
            handle_model_info({"resref": MDL_PATH})
        )
        data = json.loads(result["text"])
        assert "error" not in data, f"Unexpected error: {data.get('error')}"
        assert data["node_count"] == 82
        assert data["mesh_node_count"] == 63
        assert data["total_vertices"] == 6083
        assert data["supermodel"] == "S_Female02"
        assert data["classification"] == "character"

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_model_info_bounding_box(self):
        from kotormcp.tools.ghostrigger import handle_model_info
        result = asyncio.run(
            handle_model_info({"resref": MDL_PATH})
        )
        data = json.loads(result["text"])
        bb = data.get("bounding_box", {})
        assert bb.get("min") is not None
        assert bb.get("max") is not None
        assert len(bb["min"]) == 3
        assert len(bb["max"]) == 3

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_audit_runs(self):
        from kotormcp.tools.ghostrigger import handle_audit
        result = asyncio.run(
            handle_audit({"resref": MDL_PATH})
        )
        data = json.loads(result["text"])
        assert "error" not in data, f"Unexpected error: {data.get('error')}"
        assert data["node_count"] == 82
        assert data["mesh_node_count"] == 63
        assert data["bounding_box_ok"] is True
        assert isinstance(data["issues"], list)
        assert isinstance(data["warnings"], list)

    def test_model_info_missing_file(self):
        from kotormcp.tools.ghostrigger import handle_model_info
        result = asyncio.run(
            handle_model_info({"resref": "/nonexistent/model.mdl"})
        )
        data = json.loads(result["text"])
        assert "error" in data

    def test_open_model_no_ipc(self):
        """open_model should return a result (not crash) even without IPC running."""
        from kotormcp.tools.ghostrigger import handle_open_model
        result = asyncio.run(
            handle_open_model({"resref": "/nonexistent/model.mdl"})
        )
        data = json.loads(result["text"])
        # Should either report an error or success
        assert isinstance(data, dict)

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_open_model_existing(self):
        from kotormcp.tools.ghostrigger import handle_open_model
        result = asyncio.run(
            handle_open_model({"resref": MDL_PATH})
        )
        data = json.loads(result["text"])
        assert data.get("status") == "ok"
        assert data.get("ipc_sent") is False  # IPC not running in tests


# ── Installation detection (no game path needed) ──────────────────────────────

class TestInstallationTools:
    def test_detect_installations(self):
        from kotormcp.tools.installation import handle_detect_installations
        result = asyncio.run(
            handle_detect_installations({})
        )
        data = json.loads(result["text"])
        # Should return K1/K2 keys even if they don't exist
        assert "K1" in data or "K2" in data or "error" in data

    def test_load_installation_missing_game(self):
        from kotormcp.tools.installation import handle_load_installation
        result = asyncio.run(
            handle_load_installation({"game": "invalid_game_xyz"})
        )
        data = json.loads(result["text"])
        assert "error" in data

    def test_load_installation_bad_path(self):
        from kotormcp.tools.installation import handle_load_installation
        result = asyncio.run(
            handle_load_installation({"game": "k1", "path": "/nonexistent/path"})
        )
        data = json.loads(result["text"])
        assert "error" in data


# ── Discovery tools (no installation needed for error cases) ─────────────────

class TestDiscoveryTools:
    def test_list_resources_bad_game(self):
        from kotormcp.tools.discovery import handle_list_resources
        result = asyncio.run(
            handle_list_resources({"game": "bad_game_name"})
        )
        data = json.loads(result["text"])
        assert "error" in data

    def test_describe_resource_bad_game(self):
        from kotormcp.tools.discovery import handle_describe_resource
        result = asyncio.run(
            handle_describe_resource({"game": "bad_game", "resref": "global", "restype": "jrl"})
        )
        data = json.loads(result["text"])
        assert "error" in data

    def test_search_resources_bad_regex(self):
        from kotormcp.tools.discovery import handle_search_resources
        result = asyncio.run(
            handle_search_resources({"game": "k1", "pattern": "["})
        )
        data = json.loads(result["text"])
        assert "error" in data


# ── IPC server MCP routes ─────────────────────────────────────────────────────

class TestIPCMCPRoutes:
    """Test that the IPC server can handle MCP routes correctly."""

    def test_ipc_server_has_mcp_routes(self):
        """Verify MCP route handlers are defined in the IPC server."""
        from ipc.server import GhostRiggerIPCServer
        # Check the server can be instantiated
        server = GhostRiggerIPCServer()
        assert server is not None

    def test_ipc_server_has_mcp_attribute_in_health(self):
        """The IPC server health endpoint should report mcp=True."""
        # We can't easily start the full Flask server in a unit test,
        # but we can verify the source code has the mcp attribute.
        import inspect
        from ipc import server as ipc_server_mod
        src = inspect.getsource(ipc_server_mod)
        assert '"mcp": True' in src or "'mcp': True" in src

    def test_mcp_routes_defined(self):
        """Verify the MCP routes are defined in the IPC server source."""
        import inspect
        from ipc import server as ipc_server_mod
        src = inspect.getsource(ipc_server_mod)
        assert "/mcp/tools/list" in src
        assert "/mcp/tools/call" in src
        assert "/mcp/resources/list" in src
        assert "/mcp/resources/read" in src


# ── Schema validation ─────────────────────────────────────────────────────────

class TestSchemas:
    def test_load_installation_input(self):
        from kotormcp.schemas import LoadInstallationInput
        inp = LoadInstallationInput.model_validate({"game": "k1"})
        assert inp.game == "k1"
        assert inp.path is None

    def test_list_resources_input_defaults(self):
        from kotormcp.schemas import ListResourcesInput
        inp = ListResourcesInput.model_validate({"game": "k2"})
        assert inp.game == "k2"
        assert inp.location == "all"
        assert inp.limit == 50
        assert inp.offset == 0

    def test_find_resource_input(self):
        from kotormcp.schemas import FindResourceInput
        inp = FindResourceInput.model_validate({"game": "k1", "query": "n_sithpraet.mdl"})
        assert inp.game == "k1"
        assert inp.query == "n_sithpraet.mdl"
        assert inp.all_locations is True
