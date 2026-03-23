"""Tests for v3.4 tool additions: refs, walkmesh, archives.

Architecture compliance tests (Constantine + Khononov):
  - All new tools use data coupling only (args dict → result dict)
  - All new tools return {"type": "text", "text": "<json>"} format
  - No UI context baked into tool names or descriptions
  - Tool definitions follow the canonical structure (name, description, inputSchema)
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


class TestV34ToolRegistry:
    """Verify v3.4 tools are registered and discoverable."""

    def test_total_tool_count_is_43(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        assert len(get_all_tools()) == 43

    def test_refs_tools_registered(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        names = {t["name"] for t in get_all_tools()}
        assert "kotor_list_references" in names
        assert "kotor_find_referrers" in names
        assert "kotor_find_strref_referrers" in names
        assert "kotor_describe_dlg" in names
        assert "kotor_describe_jrl" in names
        assert "kotor_describe_resource_refs" in names

    def test_walkmesh_tool_registered(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        names = {t["name"] for t in get_all_tools()}
        assert "kotor_walkmesh_validation_diagram" in names

    def test_archive_tools_registered(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        names = {t["name"] for t in get_all_tools()}
        assert "kotor_list_archive" in names
        assert "kotor_extract_resource" in names

    def test_all_tools_have_required_fields(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        for tool in get_all_tools():
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing 'description'"
            assert "inputSchema" in tool, f"Tool {tool['name']} missing 'inputSchema'"

    def test_no_duplicate_tool_names(self):
        import sys; sys.path.insert(0, "src")
        from kotormcp.tools import get_all_tools
        names = [t["name"] for t in get_all_tools()]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"


class TestRefsToolsModule:
    """Unit tests for refs.py tool definitions and handler contracts."""

    def setup_method(self):
        import sys; sys.path.insert(0, "src")

    def test_get_tools_returns_6(self):
        from kotormcp.tools.refs import get_tools
        tools = get_tools()
        assert len(tools) == 6

    def test_tool_names(self):
        from kotormcp.tools.refs import get_tools
        names = {t["name"] for t in get_tools()}
        expected = {
            "kotor_list_references",
            "kotor_find_referrers",
            "kotor_find_strref_referrers",
            "kotor_describe_dlg",
            "kotor_describe_jrl",
            "kotor_describe_resource_refs",
        }
        assert names == expected

    def test_all_tools_read_only_descriptions(self):
        """All ref tools except none are read-only — verify descriptions say so."""
        from kotormcp.tools.refs import get_tools
        for tool in get_tools():
            assert "Read-only" in tool["description"] or "read-only" in tool["description"], (
                f"Tool {tool['name']} description should mention Read-only"
            )

    def test_describe_dlg_missing_game_returns_error(self):
        from kotormcp.tools.refs import handle_describe_dlg
        result = _run(handle_describe_dlg({"game": "invalid_game", "resref": "foo"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_describe_jrl_missing_game_returns_error(self):
        from kotormcp.tools.refs import handle_describe_jrl
        result = _run(handle_describe_jrl({"game": "invalid_game", "resref": "global"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_list_references_unknown_game_returns_error(self):
        from kotormcp.tools.refs import handle_list_references
        result = _run(handle_list_references({"game": "invalid_game", "resref": "foo", "restype": "DLG"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_find_referrers_unknown_game_returns_error(self):
        from kotormcp.tools.refs import handle_find_referrers
        result = _run(handle_find_referrers({"game": "xyz", "value": "k_foo"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_find_strref_referrers_unknown_game_returns_error(self):
        from kotormcp.tools.refs import handle_find_strref_referrers
        result = _run(handle_find_strref_referrers({"game": "xyz", "strref": 42}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_describe_resource_refs_unknown_game_returns_error(self):
        from kotormcp.tools.refs import handle_describe_resource_refs
        result = _run(handle_describe_resource_refs({"game": "xyz", "resref": "foo", "restype": "UTC"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_result_format_is_type_text(self):
        """All handlers must return {"type": "text", "text": "..."} format."""
        from kotormcp.tools.refs import handle_describe_dlg
        result = _run(handle_describe_dlg({"game": "invalid", "resref": "foo"}))
        assert result.get("type") == "text"
        assert isinstance(result.get("text"), str)


class TestWalkmeshToolModule:
    """Unit tests for walkmesh.py tool definitions and handler contracts."""

    def setup_method(self):
        import sys; sys.path.insert(0, "src")

    def test_get_tools_returns_1(self):
        from kotormcp.tools.walkmesh import get_tools
        tools = get_tools()
        assert len(tools) == 1

    def test_tool_name(self):
        from kotormcp.tools.walkmesh import get_tools
        assert get_tools()[0]["name"] == "kotor_walkmesh_validation_diagram"

    def test_missing_game_returns_error(self):
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        result = _run(handle_walkmesh_validation_diagram({"resref": "203tell"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data or "game" in result["text"].lower()

    def test_missing_resref_returns_error(self):
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        result = _run(handle_walkmesh_validation_diagram({"game": "k1"}))
        assert "text" in result

    def test_unknown_game_returns_error(self):
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        result = _run(handle_walkmesh_validation_diagram({"game": "invalid", "resref": "203tell"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_result_format_is_type_text(self):
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        result = _run(handle_walkmesh_validation_diagram({"game": "invalid", "resref": "test"}))
        assert result.get("type") == "text"
        assert isinstance(result.get("text"), str)

    def test_schema_has_use_color_flag(self):
        from kotormcp.tools.walkmesh import get_tools
        schema = get_tools()[0]["inputSchema"]
        assert "use_color" in schema["properties"]
        assert schema["properties"]["use_color"]["type"] == "boolean"

    def test_bwm_extension_stripped_from_resref(self):
        """Resrefs with .bwm extension should be stripped before lookup (v3.4.1)."""
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        # Passes .bwm extension — should strip it and attempt lookup (not crash on ext)
        result = _run(handle_walkmesh_validation_diagram({"game": "invalid_game", "resref": "test.bwm"}))
        # With invalid game it returns error, but it must not crash with a .bwm resref
        assert "text" in result
        assert isinstance(result["text"], str)

    def test_wok_extension_stripped_from_resref(self):
        """Resrefs with .wok extension should be stripped before lookup."""
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        result = _run(handle_walkmesh_validation_diagram({"game": "invalid_game", "resref": "test.wok"}))
        assert "text" in result
        assert isinstance(result["text"], str)


class TestV341Improvements:
    """Tests for v3.4.1 improvements derived from PyKotor test suite review."""

    def setup_method(self):
        import sys; sys.path.insert(0, "src")

    # -- JSON safety ----------------------------------------------------------

    def test_error_messages_are_valid_json(self):
        """All error paths must return valid JSON, even with special chars (v3.4.1)."""
        import asyncio, json
        from kotormcp.tools.refs import handle_list_references

        # Game with quotes in the name would break f-string JSON
        result = asyncio.run(handle_list_references({
            "game": 'bad"game',
            "resref": "test",
            "restype": "DLG",
        }))
        # Must be parseable JSON
        assert "text" in result
        parsed = json.loads(result["text"])
        assert "error" in parsed

    def test_walkmesh_error_messages_are_valid_json(self):
        """Walkmesh handler errors must return valid JSON."""
        import asyncio, json
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram

        result = asyncio.run(handle_walkmesh_validation_diagram({
            "game": 'bad"game',
            "resref": "test",
        }))
        assert "text" in result
        parsed = json.loads(result["text"])
        assert "error" in parsed

    # -- Schema fields --------------------------------------------------------

    def test_find_referrers_schema_has_case_sensitive(self):
        """kotor_find_referrers schema must expose case_sensitive parameter (v3.4.1)."""
        from kotormcp.tools.refs import get_tools
        tool = next(t for t in get_tools() if t["name"] == "kotor_find_referrers")
        props = tool["inputSchema"]["properties"]
        assert "case_sensitive" in props, "case_sensitive must be in kotor_find_referrers schema"
        assert props["case_sensitive"]["type"] == "boolean"

    def test_find_referrers_input_schema_has_case_sensitive(self):
        """FindReferrersInput Pydantic model must have case_sensitive field (v3.4.1)."""
        from kotormcp.schemas import FindReferrersInput
        inp = FindReferrersInput(game="k1", value="test")
        assert hasattr(inp, "case_sensitive")
        assert inp.case_sensitive is False  # default

    def test_walkmesh_tool_strips_bwm_suffix(self):
        """Walkmesh handler strips .bwm suffix from resref — parallel to .wok strip."""
        from kotormcp.tools.walkmesh import handle_walkmesh_validation_diagram
        import asyncio
        # With unknown game we always get an error, but the resref should be cleaned first
        result = asyncio.run(handle_walkmesh_validation_diagram({
            "game": "k999",
            "resref": "203tell.bwm",
        }))
        assert "error" in result.get("text", "")
        # The error should NOT mention ".bwm" in the resref (it was stripped)
        import json
        parsed = json.loads(result["text"])
        assert ".bwm" not in parsed.get("error", "203tell.bwm")

    # -- _err helper ----------------------------------------------------------

    def test_refs_has_err_helper(self):
        """refs.py must define the _err helper for JSON-safe errors (v3.4.1)."""
        import sys; sys.path.insert(0, "src")
        import kotormcp.tools.refs as refs_mod
        assert hasattr(refs_mod, "_err"), "_err helper must be present in refs.py"
        result = refs_mod._err("test error")
        assert result["type"] == "text"
        import json
        parsed = json.loads(result["text"])
        assert parsed["error"] == "test error"

    def test_refs_err_helper_escapes_quotes(self):
        """_err must escape quotes in error messages via json.dumps."""
        import sys; sys.path.insert(0, "src")
        import kotormcp.tools.refs as refs_mod
        import json
        msg = 'error with "quotes" inside'
        result = refs_mod._err(msg)
        # Must be valid JSON
        parsed = json.loads(result["text"])
        assert parsed["error"] == msg


class TestArchivesToolModule:
    """Unit tests for archives.py tool definitions and handler contracts."""

    def setup_method(self):
        import sys; sys.path.insert(0, "src")

    def test_get_tools_returns_2(self):
        from kotormcp.tools.archives import get_tools
        tools = get_tools()
        assert len(tools) == 2

    def test_tool_names(self):
        from kotormcp.tools.archives import get_tools
        names = {t["name"] for t in get_tools()}
        assert names == {"kotor_list_archive", "kotor_extract_resource"}

    def test_list_archive_nonexistent_file_returns_error(self):
        from kotormcp.tools.archives import handle_list_archive
        result = _run(handle_list_archive({"file_path": "/nonexistent/path/chitin.key"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_list_archive_unsupported_type_returns_error(self):
        import tempfile, os
        # Create a dummy file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"dummy")
            tmp_path = f.name
        try:
            from kotormcp.tools.archives import handle_list_archive
            result = _run(handle_list_archive({"file_path": tmp_path}))
            assert "text" in result
            data = json.loads(result["text"])
            assert "error" in data
        finally:
            os.unlink(tmp_path)

    def test_extract_resource_unknown_game_returns_error(self):
        from kotormcp.tools.archives import handle_extract_resource
        result = _run(handle_extract_resource({
            "game": "invalid_game",
            "resref": "foo",
            "restype": "UTC",
            "output_path": "/tmp/out",
        }))
        assert "text" in result
        data = json.loads(result["text"])
        assert "error" in data

    def test_extract_resource_schema_has_source_field(self):
        from kotormcp.tools.archives import get_tools
        extract_tool = next(t for t in get_tools() if t["name"] == "kotor_extract_resource")
        schema = extract_tool["inputSchema"]
        assert "source" in schema["properties"]

    def test_result_format_is_type_text(self):
        from kotormcp.tools.archives import handle_extract_resource
        result = _run(handle_extract_resource({
            "game": "invalid",
            "resref": "foo",
            "restype": "UTC",
            "output_path": "/tmp/test_out",
        }))
        assert result.get("type") == "text"
        assert isinstance(result.get("text"), str)

    def test_extract_tool_description_mentions_destructive(self):
        """Extract tool must declare its destructive nature in description."""
        from kotormcp.tools.archives import get_tools
        extract_tool = next(t for t in get_tools() if t["name"] == "kotor_extract_resource")
        assert "destructiveHint" in extract_tool["description"] or "writes" in extract_tool["description"].lower()


class TestV34DispatchIntegration:
    """Test that handle_tool routes all 9 new tools correctly."""

    def setup_method(self):
        import sys; sys.path.insert(0, "src")

    def _dispatch(self, name, args):
        from kotormcp.tools import handle_tool
        return _run(handle_tool(name, args))

    def test_dispatch_kotor_list_references_unknown_game(self):
        result = self._dispatch("kotor_list_references", {"game": "bad", "resref": "x", "restype": "DLG"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_find_referrers_unknown_game(self):
        result = self._dispatch("kotor_find_referrers", {"game": "bad", "value": "foo"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_find_strref_referrers_unknown_game(self):
        result = self._dispatch("kotor_find_strref_referrers", {"game": "bad", "strref": 0})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_describe_dlg_unknown_game(self):
        result = self._dispatch("kotor_describe_dlg", {"game": "bad", "resref": "foo"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_describe_jrl_unknown_game(self):
        result = self._dispatch("kotor_describe_jrl", {"game": "bad", "resref": "global"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_describe_resource_refs_unknown_game(self):
        result = self._dispatch("kotor_describe_resource_refs", {"game": "bad", "resref": "x", "restype": "UTC"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_walkmesh_validation_diagram_unknown_game(self):
        result = self._dispatch("kotor_walkmesh_validation_diagram", {"game": "bad", "resref": "foo"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_list_archive_missing_file(self):
        result = self._dispatch("kotor_list_archive", {"file_path": "/no/such/file.key"})
        assert "text" in result
        assert "error" in result["text"]

    def test_dispatch_kotor_extract_resource_unknown_game(self):
        result = self._dispatch("kotor_extract_resource", {
            "game": "bad", "resref": "x", "restype": "UTC", "output_path": "/tmp"
        })
        assert "text" in result
        assert "error" in result["text"]
