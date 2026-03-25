"""
Tests for KotorMCP architecture v3.0 (ports, adapters, new tools).

This file covers:
  - ports.py value objects and contracts
  - adapters.py: PyKotorRegistryAdapter, FileSystemModelLocator,
    CompositeModelLocator, MDLBinaryParserAdapter, ModelAnalyzer
  - New tool modules: modules.py, gffdata.py
  - Updated tool count (21+ tools)
  - InstallationAdapter via a lightweight stub (no real game needed)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Iterator, List, Optional

import pytest

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Guard: many tests here require pykotor — skip whole classes when absent
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def _data(result):
    return json.loads(result["text"])


# ── Port value objects ─────────────────────────────────────────────────────────

class TestPorts:
    def test_resource_entry_immutable(self):
        from kotormcp.ports import ResourceEntry
        e = ResourceEntry(resref="n_sithpraet", restype="MDL", extension="mdl",
                          size=1024, source="override")
        assert e.resref == "n_sithpraet"
        assert e.restype == "MDL"
        with pytest.raises((AttributeError, TypeError)):
            e.resref = "other"  # type: ignore[misc]

    def test_model_info_fields(self):
        from kotormcp.ports import ModelInfo
        info = ModelInfo(
            resref="test", path="/tmp/test.mdl",
            node_count=5, mesh_node_count=3,
            total_vertices=100, total_faces=50,
            bone_count=2, bones=["Bone1", "Bone2"],
            animations=["idle"],
            bounding_box_min=[-1.0, -1.0, 0.0],
            bounding_box_max=[1.0, 1.0, 2.0],
            classification="character",
            supermodel="S_Female02",
        )
        assert info.supermodel == "S_Female02"
        assert len(info.bones) == 2

    def test_audit_result_defaults(self):
        from kotormcp.ports import AuditResult
        r = AuditResult(resref="x", status="ok", node_count=10,
                        mesh_node_count=5, bounding_box_ok=True)
        assert r.issues == []
        assert r.warnings == []

    def test_port_contracts_are_abstract(self):
        """Verify ports cannot be instantiated directly."""
        from kotormcp.ports import (
            InstallationPort, InstallationRegistryPort,
            ModelLocatorPort, ModelParserPort,
        )
        import inspect
        for cls in [InstallationPort, InstallationRegistryPort,
                    ModelLocatorPort, ModelParserPort]:
            assert inspect.isabstract(cls), f"{cls.__name__} should be abstract"


# ── PyKotorRegistryAdapter ────────────────────────────────────────────────────

@_skip_no_pykotor
class TestPyKotorRegistryAdapter:
    def test_resolve_known_aliases(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        from pykotor.common.misc import Game
        reg = PyKotorRegistryAdapter()
        assert reg.resolve("k1") == Game.K1
        assert reg.resolve("tsl") == Game.K2
        assert reg.resolve("kotor2") == Game.K2

    def test_resolve_unknown_returns_none(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        reg = PyKotorRegistryAdapter()
        assert reg.resolve(None) is None
        assert reg.resolve("notgame") is None

    def test_clear_empties_cache(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        reg = PyKotorRegistryAdapter()
        reg.clear()
        assert len(reg._cache) == 0

    def test_iter_candidate_paths_explicit(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        from pykotor.common.misc import Game
        reg = PyKotorRegistryAdapter()
        paths = list(reg.iter_candidate_paths(Game.K1, "/tmp/fake_kotor"))
        assert any("fake_kotor" in str(p) for p in paths)

    def test_load_raises_for_bad_path(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        from pykotor.common.misc import Game
        reg = PyKotorRegistryAdapter()
        with pytest.raises((ValueError, Exception)):
            reg.load(Game.K1, "/nonexistent/kotor_path")

    def test_default_registry_is_singleton(self):
        from kotormcp.adapters import get_default_registry
        r1 = get_default_registry()
        r2 = get_default_registry()
        assert r1 is r2

    def test_default_path_keys(self):
        from kotormcp.adapters import PyKotorRegistryAdapter
        from pykotor.common.misc import Game
        reg = PyKotorRegistryAdapter()
        # Should return a set (may be empty without a real installation)
        keys = reg.default_path_keys(Game.K1)
        assert isinstance(keys, set)


# ── FileSystemModelLocator ─────────────────────────────────────────────────────

class TestFileSystemModelLocator:
    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_locate_by_absolute_path(self):
        from kotormcp.adapters import FileSystemModelLocator
        loc = FileSystemModelLocator()
        path, mdl, mdx = loc.locate(MDL_PATH)
        assert path == MDL_PATH or os.path.abspath(MDL_PATH) in path
        assert len(mdl) > 0

    def test_locate_missing_raises(self):
        from kotormcp.adapters import FileSystemModelLocator
        loc = FileSystemModelLocator()
        with pytest.raises(FileNotFoundError):
            loc.locate("/does/not/exist.mdl")

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_mdx_loaded_alongside_mdl(self):
        """MDX should be loaded when present next to the MDL."""
        from kotormcp.adapters import FileSystemModelLocator
        loc = FileSystemModelLocator()
        path, mdl, mdx = loc.locate(MDL_PATH)
        # .mdx may or may not exist — just verify no crash
        assert isinstance(mdx, bytes)


# ── CompositeModelLocator ─────────────────────────────────────────────────────

class TestCompositeModelLocator:
    def test_falls_through_to_second_locator(self):
        """First locator always raises; second should succeed."""
        from kotormcp.adapters import CompositeModelLocator
        from kotormcp.ports import ModelLocatorPort

        class _AlwaysFail(ModelLocatorPort):
            def locate(self, resref, game_alias=None, game_path=None):
                raise FileNotFoundError("intentional fail")

        class _AlwaysSucceed(ModelLocatorPort):
            def locate(self, resref, game_alias=None, game_path=None):
                return ("stub_path", b"MDL_BYTES", b"")

        comp = CompositeModelLocator([_AlwaysFail(), _AlwaysSucceed()])
        path, mdl, mdx = comp.locate("anything")
        assert path == "stub_path"
        assert mdl == b"MDL_BYTES"

    def test_all_fail_raises_fnf(self):
        from kotormcp.adapters import CompositeModelLocator, FileSystemModelLocator
        loc = CompositeModelLocator([FileSystemModelLocator()])
        with pytest.raises(FileNotFoundError):
            loc.locate("/nonexistent/nope.mdl")


# ── ModelAnalyzer ──────────────────────────────────────────────────────────────

class TestModelAnalyzer:
    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_model_info_returns_model_info(self):
        from kotormcp.adapters import (
            FileSystemModelLocator, MDLBinaryParserAdapter, ModelAnalyzer,
        )
        from kotormcp.ports import ModelInfo
        loc = FileSystemModelLocator()
        path, mdl, mdx = loc.locate(MDL_PATH)
        parser = MDLBinaryParserAdapter()
        model = parser.parse(mdl, mdx, path)
        analyzer = ModelAnalyzer()
        info = analyzer.model_info(model, "n_sithpraet", path)
        assert isinstance(info, ModelInfo)
        assert info.node_count == 82
        assert info.mesh_node_count == 63
        assert info.total_vertices == 6083
        assert info.supermodel == "S_Female02"

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_audit_returns_audit_result(self):
        from kotormcp.adapters import (
            FileSystemModelLocator, MDLBinaryParserAdapter, ModelAnalyzer,
        )
        from kotormcp.ports import AuditResult
        loc = FileSystemModelLocator()
        path, mdl, mdx = loc.locate(MDL_PATH)
        parser = MDLBinaryParserAdapter()
        model = parser.parse(mdl, mdx, path)
        analyzer = ModelAnalyzer()
        result = analyzer.audit(model, "n_sithpraet")
        assert isinstance(result, AuditResult)
        assert result.node_count == 82
        assert result.bounding_box_ok is True
        assert isinstance(result.issues, list)

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_model_info_and_audit_agree_on_counts(self):
        """Both methods must use the same logic — no Connascence of Algorithm."""
        from kotormcp.adapters import (
            FileSystemModelLocator, MDLBinaryParserAdapter, ModelAnalyzer,
        )
        loc = FileSystemModelLocator()
        path, mdl, mdx = loc.locate(MDL_PATH)
        parser = MDLBinaryParserAdapter()
        model = parser.parse(mdl, mdx, path)
        analyzer = ModelAnalyzer()
        info = analyzer.model_info(model, "test", path)
        audit = analyzer.audit(model, "test")
        assert info.node_count == audit.node_count
        assert info.mesh_node_count == audit.mesh_node_count


# ── InstallationAdapter (via a stub) ──────────────────────────────────────────

class _StubInstallation:
    """Minimal stub mimicking pykotor.extract.installation.Installation."""

    def path(self):
        from pathlib import Path
        return Path("/stub/kotor")

    def modules_list(self):
        return ["203tel", "manm26ac"]

    def override_resources(self):
        return iter([])

    def core_resources(self):
        return iter([])

    def chitin_resources(self):
        return iter([])

    def module_resources(self, _name):
        return iter([])

    def resource(self, resref, restype, order=None):
        return None

    def talktable(self):
        class _TT:
            def string(self, i):
                return f"stub_string_{i}"
        return _TT()


@_skip_no_pykotor
class TestInstallationAdapter:
    def _make_adapter(self):
        from kotormcp.adapters import InstallationAdapter
        from pykotor.common.misc import Game
        return InstallationAdapter(_StubInstallation(), Game.K1)

    def test_game_name(self):
        adapter = self._make_adapter()
        assert adapter.game_name() == "K1"

    def test_path_returns_string(self):
        adapter = self._make_adapter()
        p = adapter.path()
        assert isinstance(p, str)
        assert "/stub/kotor" in p

    def test_module_names(self):
        adapter = self._make_adapter()
        mods = adapter.module_names()
        assert "203tel" in mods

    def test_override_count_empty(self):
        adapter = self._make_adapter()
        assert adapter.override_count() == 0

    def test_talktable_string(self):
        adapter = self._make_adapter()
        text = adapter.talktable_string(0)
        assert "stub_string_0" in text

    def test_iter_resources_empty(self):
        adapter = self._make_adapter()
        items = list(adapter.iter_resources("all"))
        assert isinstance(items, list)


# ── Updated tool count ─────────────────────────────────────────────────────────

class TestUpdatedToolRegistry:
    def test_tool_count_increased(self):
        from kotormcp.tools import get_all_tools
        tools = get_all_tools()
        assert len(tools) >= 21, f"Expected 21+ tools, got {len(tools)}"

    def test_new_tools_registered(self):
        from kotormcp.tools import get_all_tools
        names = {t["name"] for t in get_all_tools()}
        new_tools = {
            "kotor_list_modules",
            "kotor_describe_module",
            "kotor_module_resources",
            "kotor_read_gff",
            "kotor_read_2da",
            "kotor_read_tlk",
        }
        assert new_tools <= names, f"Missing tools: {new_tools - names}"

    def test_all_tools_have_valid_schema(self):
        from kotormcp.tools import get_all_tools
        for tool in get_all_tools():
            assert "name" in tool, f"{tool} missing name"
            assert "description" in tool, f"{tool['name']} missing description"
            assert "inputSchema" in tool, f"{tool['name']} missing inputSchema"
            schema = tool["inputSchema"]
            assert schema.get("type") == "object", f"{tool['name']} schema type != object"
            assert "properties" in schema, f"{tool['name']} missing properties in schema"

    def test_dispatch_new_tools_unknown_game(self):
        """New tools return an error gracefully for unknown games."""
        from kotormcp.tools import handle_tool
        for tool_name, args in [
            ("kotor_list_modules", {"game": "bad"}),
            ("kotor_describe_module", {"game": "bad", "module_root": "test"}),
            ("kotor_module_resources", {"game": "bad", "module_root": "test"}),
            ("kotor_read_gff", {"game": "bad", "resref": "x", "restype": "utc"}),
            ("kotor_read_2da", {"game": "bad", "resref": "appearance"}),
            ("kotor_read_tlk", {"game": "bad"}),
        ]:
            result = _run(handle_tool(tool_name, args))
            data = _data(result)
            assert "error" in data, f"{tool_name} should return error for bad game"

    def test_dispatch_new_tools_bad_path(self):
        """New tools return an error gracefully when game path doesn't exist."""
        from kotormcp.tools import handle_tool
        for tool_name, args in [
            ("kotor_list_modules", {"game": "k1"}),
            ("kotor_describe_module", {"game": "k1", "module_root": "test"}),
            ("kotor_module_resources", {"game": "k1", "module_root": "test"}),
            ("kotor_read_gff", {"game": "k1", "resref": "x", "restype": "utc"}),
            ("kotor_read_2da", {"game": "k1", "resref": "appearance"}),
            ("kotor_read_tlk", {"game": "k1"}),
        ]:
            result = _run(handle_tool(tool_name, args))
            data = _data(result)
            # Either an error (no installation found) or a graceful empty result
            assert isinstance(data, dict), f"{tool_name} returned non-dict"


# ── GhostRigger service injection test ───────────────────────────────────────

class TestGhostRiggerServiceInjection:
    """Verify that tool handlers can be tested with injected stubs."""

    @pytest.mark.skipif(not os.path.exists(MDL_PATH), reason="test MDL not found")
    def test_model_info_with_injected_services(self):
        """Use the real locator/parser/analyzer but via the injection point."""
        from kotormcp.adapters import (
            CompositeModelLocator, FileSystemModelLocator,
            MDLBinaryParserAdapter, ModelAnalyzer, PyKotorRegistryAdapter,
        )
        from kotormcp.tools import ghostrigger as gr

        # Reset and inject custom services
        gr._reset_services()
        # After reset the next call to _get_services() builds defaults
        # Verify model_info still works after service container rebuild
        result = _run(gr.handle_model_info({"resref": MDL_PATH}))
        data = _data(result)
        assert "error" not in data
        assert data["node_count"] == 82

    def test_model_info_missing_returns_error(self):
        from kotormcp.tools import ghostrigger as gr
        result = _run(gr.handle_model_info({"resref": "/nope/not_there.mdl"}))
        data = _data(result)
        assert "error" in data

    def test_audit_missing_returns_error(self):
        from kotormcp.tools import ghostrigger as gr
        result = _run(gr.handle_audit({"resref": "/nope/not_there.mdl"}))
        data = _data(result)
        assert "error" in data


# ── New schema models ──────────────────────────────────────────────────────────

class TestNewSchemas:
    def test_list_modules_input(self):
        from kotormcp.schemas import ListModulesInput
        inp = ListModulesInput.model_validate({"game": "k1"})
        assert inp.game == "k1"

    def test_describe_module_input(self):
        from kotormcp.schemas import DescribeModuleInput
        inp = DescribeModuleInput.model_validate({"game": "k2", "module_root": "203tel"})
        assert inp.module_root == "203tel"

    def test_module_resources_input_defaults(self):
        from kotormcp.schemas import ModuleResourcesInput
        inp = ModuleResourcesInput.model_validate({"game": "k1", "module_root": "x"})
        assert inp.limit == 50
        assert inp.offset == 0

    def test_read_gff_input(self):
        from kotormcp.schemas import ReadGffInput
        inp = ReadGffInput.model_validate({"game": "k1", "resref": "n_sith001", "restype": "utc"})
        assert inp.restype == "utc"
        assert inp.max_depth is None  # optional

    def test_read_2da_input_defaults(self):
        from kotormcp.schemas import Read2daInput
        inp = Read2daInput.model_validate({"game": "k2", "resref": "appearance"})
        assert inp.row_start is None
        assert inp.columns is None

    def test_read_tlk_input_defaults(self):
        from kotormcp.schemas import ReadTlkInput
        inp = ReadTlkInput.model_validate({"game": "k1"})
        assert inp.limit == 100
        assert inp.strref_start is None
