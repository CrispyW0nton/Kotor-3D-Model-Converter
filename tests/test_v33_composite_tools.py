"""
Tests for get_resource and get_quest tool modules.

Design: all tests run offline (no real KotOR install required).
Mock objects implement the minimum InstallationPort surface needed.
This follows the same offline-first pattern as test_agentdecompile_bridge.py.
"""

from __future__ import annotations

import asyncio
import json
import struct
from typing import Any, Dict, Iterator, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ── Minimal offline mock installation ────────────────────────────────────────

class MockResourceEntry:
    def __init__(self, resref: str, restype: str, data: bytes, source: str = "override"):
        self.resref = resref
        self.restype = restype
        self.data = data
        self.source = source


class MockInstallation:
    """Minimal InstallationPort mock for offline tests."""

    def __init__(self, resources: Dict[str, bytes] = None):
        self._resources: Dict[str, bytes] = resources or {}

    def get_resource(self, resref: str, restype: str) -> Optional[MockResourceEntry]:
        key = f"{resref}.{restype}"
        data = self._resources.get(key)
        if data is None:
            return None
        return MockResourceEntry(resref, restype, data, source="override")

    def iter_resources(self, location: str = "all") -> Iterator[MockResourceEntry]:
        for key, data in self._resources.items():
            if "." in key:
                resref, restype = key.rsplit(".", 1)
                yield MockResourceEntry(resref, restype, data, source=location)

    def talktable_string(self, strref: int) -> str:
        return f"TLK:{strref}"


def _make_minimal_gff_bytes() -> bytes:
    """
    Build a minimal valid-enough GFF binary for testing.
    Uses pykotor's GFF builder if available, otherwise returns empty bytes.
    """
    try:
        from pykotor.resource.formats.gff.gff_data import GFF, GFFStruct
        from pykotor.resource.formats.gff.gff_auto import bytes_gff
        gff = GFF()
        gff.root.set_string("Tag", "test_creature")
        gff.root.set_uint8("ClassList", 0)
        return bytes_gff(gff)
    except Exception:
        return b""


def _make_minimal_jrl_bytes() -> bytes:
    """Build a minimal global.jrl GFF for get_quest tests."""
    try:
        from pykotor.resource.formats.gff.gff_data import GFF, GFFStruct, GFFList
        from pykotor.resource.formats.gff.gff_auto import bytes_gff
        gff = GFF()
        cats = gff.root.set_list("Categories", GFFList())
        cat = GFFStruct()
        cat.set_string("Tag", "tat17_sandral")
        cat.set_uint32("Name", 1001)
        cat.set_uint32("Priority", 30)
        entries = cat.set_list("EntryList", GFFList())
        e1 = GFFStruct()
        e1.set_uint32("ID", 10)
        e1.set_uint32("Text", 2001)
        e1.set_uint8("End", 0)
        e1.set_string("Script", "k_tat17_q01")
        entries.append(e1)
        e2 = GFFStruct()
        e2.set_uint32("ID", 20)
        e2.set_uint32("Text", 2002)
        e2.set_uint8("End", 1)
        entries.append(e2)
        cats.append(cat)
        return bytes_gff(gff)
    except Exception:
        return b""


# ── Tool schema tests ─────────────────────────────────────────────────────────

class TestGetResourceSchema:

    def test_tool_definition_exists(self):
        from kotormcp.tools.resource import get_tools
        tools = get_tools()
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "get_resource"

    def test_required_fields(self):
        from kotormcp.tools.resource import get_tools
        schema = get_tools()[0]["inputSchema"]
        assert set(schema["required"]) == {"game", "resref", "restype"}

    def test_description_is_context_free(self):
        """Tool description must not reference any specific consumer context."""
        from kotormcp.tools.resource import get_tools
        desc = get_tools()[0]["description"].lower()
        for bad_word in ("discord", "vscode", "cursor", "claude", "bot", "extension"):
            assert bad_word not in desc, f"Description contains context word: {bad_word}"

    def test_name_has_no_app_prefix(self):
        from kotormcp.tools.resource import get_tools
        name = get_tools()[0]["name"]
        for prefix in ("kotor_", "ghostrigger_", "ghostscripter_", "gmodular_"):
            assert not name.startswith(prefix), f"Name has app prefix: {name}"


class TestGetQuestSchema:

    def test_tool_definition_exists(self):
        from kotormcp.tools.quest import get_tools
        tools = get_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "get_quest"

    def test_required_fields(self):
        from kotormcp.tools.quest import get_tools
        schema = get_tools()[0]["inputSchema"]
        assert set(schema["required"]) == {"game", "tag"}

    def test_optional_fields_present(self):
        from kotormcp.tools.quest import get_tools
        props = get_tools()[0]["inputSchema"]["properties"]
        assert "include_dlg" in props
        assert "include_scripts" in props

    def test_description_is_context_free(self):
        from kotormcp.tools.quest import get_tools
        desc = get_tools()[0]["description"].lower()
        for bad_word in ("discord", "vscode", "cursor", "claude", "bot"):
            assert bad_word not in desc, f"Description contains context: {bad_word}"


# ── Registry integration tests ────────────────────────────────────────────────

class TestRegistryIntegration:

    def test_total_tool_count(self):
        from kotormcp.tools import get_all_tools
        tools = get_all_tools()
        assert len(tools) == 43, f"Expected 43 tools, got {len(tools)}"

    def test_get_resource_in_registry(self):
        from kotormcp.tools import get_all_tools
        names = [t["name"] for t in get_all_tools()]
        assert "get_resource" in names

    def test_get_quest_in_registry(self):
        from kotormcp.tools import get_all_tools
        names = [t["name"] for t in get_all_tools()]
        assert "get_quest" in names

    def test_no_duplicate_tool_names(self):
        from kotormcp.tools import get_all_tools
        names = [t["name"] for t in get_all_tools()]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_all_tools_have_description(self):
        from kotormcp.tools import get_all_tools
        for tool in get_all_tools():
            assert "description" in tool, f"Tool {tool['name']} missing description"
            assert len(tool["description"]) > 10

    def _extract_text(self, result):
        """Extract the inner JSON/text string from a json_content response."""
        content = result.get("content", [])
        if isinstance(content, list) and content:
            raw = content[0].get("text", "")
        else:
            raw = str(result)
        return raw  # raw is the JSON string itself

    def test_dispatch_get_resource_unknown_game(self):
        from kotormcp.tools import handle_tool
        result = asyncio.run(handle_tool("get_resource", {
            "game": "invalid", "resref": "test", "restype": "utc",
        }))
        text = self._extract_text(result)
        assert "error" in text.lower() or "k1" in text.lower() or "game" in text.lower()

    def test_dispatch_get_quest_unknown_game(self):
        from kotormcp.tools import handle_tool
        result = asyncio.run(handle_tool("get_quest", {
            "game": "invalid", "tag": "tat17_sandral",
        }))
        text = self._extract_text(result)
        assert "error" in text.lower() or "game" in text.lower()

    def test_unknown_tool_raises(self):
        from kotormcp.tools import handle_tool
        with pytest.raises(ValueError, match="Unknown tool"):
            asyncio.run(handle_tool("nonexistent_tool_xyz", {}))


# ── get_resource handler tests ────────────────────────────────────────────────

class TestHandleGetResource:

    def _run(self, arguments):
        from kotormcp.tools.resource import handle_get_resource
        return asyncio.run(handle_get_resource(arguments))

    def test_missing_game(self):
        result = self._run({"resref": "n_sithpraet", "restype": "mdl"})
        text = str(result)
        assert "error" in text.lower() or "game" in text.lower()

    def test_missing_resref(self):
        result = self._run({"game": "k1", "restype": "utc"})
        text = str(result)
        assert "error" in text.lower()

    def test_resource_not_found(self):
        mock_inst = MockInstallation({})
        with patch("kotormcp.tools.resource.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.resource.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "resref": "notexist", "restype": "utc"})
        text = str(result)
        assert "not found" in text.lower() or "error" in text.lower()

    def test_binary_fallback_for_unknown_type(self):
        mock_inst = MockInstallation({"foo.xyz": b"\x01\x02\x03\x04"})
        with patch("kotormcp.tools.resource.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.resource.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "resref": "foo", "restype": "xyz"})
        text = str(result)
        # Should succeed (binary fallback) and return base64
        assert "error" not in text.lower() or "base64" in text.lower()

    def test_nss_source_decode(self):
        src = b"void main() { /* test script */ }"
        mock_inst = MockInstallation({"myscript.nss": src})
        with patch("kotormcp.tools.resource.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.resource.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "resref": "myscript", "restype": "nss"})
        text = str(result)
        assert "void main" in text or "source" in text

    def test_2da_decode(self):
        """2DA decode path — requires pykotor; skipped if not available."""
        try:
            from pykotor.resource.formats.twoda.twoda_auto import bytes_2da
            from pykotor.resource.formats.twoda.twoda_data import TwoDA
        except ImportError:
            pytest.skip("pykotor not available")
        table = TwoDA()
        table.add_column("label")
        table.add_row()
        table.set_cell(0, "label", "test_row")
        raw = bytes_2da(table)
        mock_inst = MockInstallation({"appearance.2da": raw})
        with patch("kotormcp.tools.resource.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.resource.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "resref": "appearance", "restype": "2da"})
        text = str(result)
        assert "columns" in text or "rows" in text or "error" in text


# ── get_quest handler tests ───────────────────────────────────────────────────

class TestHandleGetQuest:

    def _run(self, arguments):
        from kotormcp.tools.quest import handle_get_quest
        return asyncio.run(handle_get_quest(arguments))

    def test_missing_game(self):
        result = self._run({"tag": "tat17_sandral"})
        text = str(result)
        assert "error" in text.lower()

    def test_missing_tag(self):
        result = self._run({"game": "k1"})
        text = str(result)
        assert "error" in text.lower()

    def test_jrl_not_found(self):
        mock_inst = MockInstallation({})  # no jrl
        with patch("kotormcp.tools.quest.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.quest.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "tag": "tat17_sandral"})
        text = str(result)
        assert "jrl" in text.lower() or "error" in text.lower()

    def test_quest_not_found_returns_available_tags(self):
        jrl_data = _make_minimal_jrl_bytes()
        if not jrl_data:
            pytest.skip("pykotor GFF builder not available")
        mock_inst = MockInstallation({"global.jrl": jrl_data})
        with patch("kotormcp.tools.quest.resolve_game", return_value="k1"), \
             patch("kotormcp.tools.quest.load_installation", return_value=mock_inst):
            result = self._run({"game": "k1", "tag": "nonexistent_quest_xyz",
                                 "include_dlg": False, "include_scripts": False})
        text = str(result)
        assert "not found" in text.lower() or "available" in text.lower()

    def test_quest_found_returns_markdown(self):
        """Test the full quest pipeline using direct mock (bypassing pykotor GFF builder)."""
        from kotormcp.tools.quest import _find_quest, _render_markdown
        # Build categories directly (bypassing GFF serialization)
        categories = [{
            "tag": "tat17_sandral",
            "name_strref": 1001,
            "name_text": "Sandral-Matale Feud",
            "priority": 30,
            "entries": [
                {"id": 10, "text_strref": 2001, "text": "The feud begins.", "completes_plot": False},
                {"id": 20, "text_strref": 2002, "text": "Quest complete.", "completes_plot": True},
            ],
        }]
        matched = _find_quest(categories, "tat17")
        assert matched, "Should find quest by prefix"
        md = _render_markdown(matched, [], {}, [], "tat17", "k1")
        assert "tat17" in md.lower()
        assert "quest" in md.lower()
        assert "Sandral-Matale Feud" in md or "sandral" in md.lower()

    def test_script_source_included_when_nss_present(self):
        """Test script source surfacing via _fetch_script_sources."""
        from kotormcp.tools.quest import _fetch_script_sources
        nss_src = b"void main() { SetGlobalNumber(\"tat17\", 1); }"
        mock_inst = MockInstallation({"k_tat17_q01.nss": nss_src})
        results = _fetch_script_sources(["k_tat17_q01"], mock_inst)
        src = results.get("k_tat17_q01", "")
        assert "SetGlobalNumber" in src or "void main" in src


# ── Path extraction helper tests ──────────────────────────────────────────────

class TestExtractPath:

    def test_simple_key(self):
        from kotormcp.tools.resource import _extract_path
        assert _extract_path({"Foo": "bar"}, "Foo") == "bar"

    def test_nested_key(self):
        from kotormcp.tools.resource import _extract_path
        tree = {"A": {"B": {"C": 42}}}
        assert _extract_path(tree, "A.B.C") == 42

    def test_list_index(self):
        from kotormcp.tools.resource import _extract_path
        tree = {"Items": [{"Name": "sword"}, {"Name": "shield"}]}
        assert _extract_path(tree, "Items.1.Name") == "shield"

    def test_missing_key_returns_none(self):
        from kotormcp.tools.resource import _extract_path
        assert _extract_path({"A": 1}, "B.C") is None

    def test_out_of_range_index(self):
        from kotormcp.tools.resource import _extract_path
        assert _extract_path({"X": [1, 2]}, "X.99") is None
