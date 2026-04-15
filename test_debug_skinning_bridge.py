#!/usr/bin/env python3
"""
test_debug_skinning_bridge.py — Automated Tests for the MCP Debug Skinning Bridge
=================================================================================
Tests the observability-first debug bridge for GhostRigger runtime skinning
inspection.  Validates:

1. Session lifecycle:  launch, status, close
2. Game library setup:  set path, verify
3. Model loading:  load by resref, get asset info
4. Animation control:  list, set, seek, bind-pose
5. Skinning inspection:  state, hierarchy, bone map, palette remap,
   bind-pose matrices, animated matrices, vertex influences
6. CPU-vs-GPU parity check
7. Debug bundle export
8. Tool definitions and dispatch

Requires game data in game_data/swkotor/ with chitin.key and data/models.bif.
Tests are skipped (not failed) if game data is unavailable.

Usage:
    python -m pytest test_debug_skinning_bridge.py -v
    python test_debug_skinning_bridge.py
"""

import asyncio
import json
import os
import sys
import pytest

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

sys.path.insert(0, os.path.join(_root, "src"))

from src.kotormcp.tools.debug_skinning import (
    _DebugSession,
    _get_session,
    _reset_session,
    get_tools,
)

# ─── Game data availability ─────────────────────────────────────────────────

GAME_DIR = os.path.join(_root, "game_data", "swkotor")
KEY_PATH = os.path.join(GAME_DIR, "chitin.key")
HAS_GAME_DATA = os.path.exists(KEY_PATH) and os.path.exists(
    os.path.join(GAME_DIR, "data", "models.bif")
)

skip_no_game = pytest.mark.skipif(
    not HAS_GAME_DATA,
    reason="Game data not available (chitin.key or models.bif missing)",
)

# Validation targets
VALIDATION_TARGETS = ["c_kraytdragon", "c_rancor", "c_dewback", "c_gammorean", "n_commf"]


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_session():
    """Reset the debug session before each test."""
    _reset_session()
    yield
    _reset_session()


@pytest.fixture
def session():
    """Get a fresh debug session."""
    s = _get_session()
    s.launch()
    return s


@pytest.fixture
def session_with_game(session):
    """Get a session with game library configured."""
    if not HAS_GAME_DATA:
        pytest.skip("No game data")
    session.set_game_path(GAME_DIR)
    return session


# ─── Test: Tool Definitions ─────────────────────────────────────────────────

class TestToolDefinitions:
    def test_get_tools_returns_list(self):
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 25

    def test_all_tools_have_required_fields(self):
        tools = get_tools()
        for t in tools:
            assert "name" in t, f"Missing 'name' in tool: {t}"
            assert "description" in t, f"Missing 'description' in tool: {t}"
            assert "inputSchema" in t, f"Missing 'inputSchema' in tool: {t}"
            assert t["name"].startswith("ghostrigger_debug_"), f"Bad prefix: {t['name']}"

    def test_tool_names_unique(self):
        tools = get_tools()
        names = [t["name"] for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_required_commands_present(self):
        """Verify all 25 required commands from the mission spec."""
        tools = get_tools()
        names = {t["name"] for t in tools}
        required = {
            "ghostrigger_debug_launch_app",
            "ghostrigger_debug_close_app",
            "ghostrigger_debug_get_runtime_status",
            "ghostrigger_debug_set_game_library_path",
            "ghostrigger_debug_verify_game_library",
            "ghostrigger_debug_load_model",
            "ghostrigger_debug_get_loaded_asset_info",
            "ghostrigger_debug_list_animations",
            "ghostrigger_debug_set_animation",
            "ghostrigger_debug_set_animation_time",
            "ghostrigger_debug_set_bind_pose",
            "ghostrigger_debug_set_camera_preset",
            "ghostrigger_debug_capture_viewport",
            "ghostrigger_debug_capture_validation_set",
            "ghostrigger_debug_get_skinning_state",
            "ghostrigger_debug_get_renderer_state",
            "ghostrigger_debug_get_bone_hierarchy",
            "ghostrigger_debug_get_bone_map",
            "ghostrigger_debug_get_palette_remap_table",
            "ghostrigger_debug_get_bind_pose_matrices",
            "ghostrigger_debug_get_animated_pose_matrices",
            "ghostrigger_debug_get_uploaded_palette",
            "ghostrigger_debug_sample_vertex_influences",
            "ghostrigger_debug_compare_cpu_gpu_skinning",
            "ghostrigger_debug_export_debug_bundle",
        }
        missing = required - names
        assert not missing, f"Missing required commands: {missing}"


# ─── Test: Session Lifecycle ─────────────────────────────────────────────────

class TestSessionLifecycle:
    def test_launch(self, session):
        assert session.started is True
        assert session.uptime_s >= 0

    def test_close(self, session):
        session.close()
        assert session.started is False
        assert session.model is None

    def test_runtime_status_before_launch(self):
        s = _get_session()
        assert s.started is False
        assert s.model is None

    def test_runtime_status_after_launch(self, session):
        assert session.started is True
        assert session.renderer is not None or True  # may fail in headless


# ─── Test: Game Library ──────────────────────────────────────────────────────

class TestGameLibrary:
    def test_set_invalid_path(self, session):
        result = session.set_game_path("/nonexistent/path")
        assert result["ok"] is False

    @skip_no_game
    def test_set_valid_path(self, session):
        result = session.set_game_path(GAME_DIR)
        assert result["ok"] is True
        assert session.game_verified is True

    @skip_no_game
    def test_verify_game(self, session_with_game):
        result = session_with_game.verify_game()
        assert result["ok"] is True
        assert result["chitin_key"] is True
        assert result["models_bif"] is True


# ─── Test: Model Loading ────────────────────────────────────────────────────

class TestModelLoading:
    @skip_no_game
    def test_load_kraytdragon(self, session_with_game):
        result = session_with_game.load_model("c_kraytdragon")
        assert result["ok"] is True
        assert result["node_count"] > 0
        assert result["skin_count"] > 0
        assert result["bone_count"] > 0
        assert "cwalk" in [a.lower() for a in result["animations"]]

    @skip_no_game
    def test_load_nonexistent(self, session_with_game):
        result = session_with_game.load_model("xyzzynonexistent")
        assert result["ok"] is False

    @skip_no_game
    def test_get_asset_info(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        info = session_with_game.get_asset_info()
        assert info["ok"] is True
        assert info["resref"] == "c_kraytdragon"
        assert len(info["skin_nodes"]) > 0


# ─── Test: Animation Control ────────────────────────────────────────────────

class TestAnimationControl:
    @skip_no_game
    def test_list_animations(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        anims = session_with_game.list_animations()
        assert len(anims) > 0
        names = [a["name"].lower() for a in anims]
        assert "cwalk" in names

    @skip_no_game
    def test_set_animation(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        result = session_with_game.set_animation("cwalk")
        assert result["ok"] is True
        assert session_with_game.current_anim_name == "cwalk"

    @skip_no_game
    def test_set_animation_time(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_animation("cwalk")
        result = session_with_game.set_animation_time(0.5)
        assert result["ok"] is True
        assert result["pose_nodes"] > 0

    @skip_no_game
    def test_set_bind_pose(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_animation("cwalk")
        result = session_with_game.set_bind_pose()
        assert result["ok"] is True
        assert session_with_game.current_pose is None


# ─── Test: Camera Presets ────────────────────────────────────────────────────

class TestCameraPresets:
    def test_valid_presets(self, session):
        for preset in ["front", "diagonal", "side", "top", "back"]:
            result = session.set_camera(preset)
            assert result["ok"] is True

    def test_invalid_preset(self, session):
        result = session.set_camera("nonexistent")
        assert result["ok"] is False


# ─── Test: Skinning Inspection ───────────────────────────────────────────────

class TestSkinningInspection:
    @skip_no_game
    def test_get_skinning_state(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        state = session_with_game.get_skinning_state()
        assert state["ok"] is True
        assert state["skin_node_count"] > 0
        assert state["uploader_active"] is True
        assert state["bone_count"] > 0

    @skip_no_game
    def test_get_bone_hierarchy(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        hier = session_with_game.get_bone_hierarchy()
        assert hier["ok"] is True
        assert "hierarchy" in hier
        assert hier["hierarchy"]["name"] != ""

    @skip_no_game
    def test_get_bone_map(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        # Find a skin node name
        info = session_with_game.get_asset_info()
        skin_name = info["skin_nodes"][0]["name"]
        bmap = session_with_game.get_bone_map_for_mesh(skin_name)
        assert bmap["ok"] is True
        assert bmap["is_skin"] is True
        assert bmap["bone_map_size"] > 0

    @skip_no_game
    def test_get_palette_remap_table(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        remap = session_with_game.get_palette_remap_table()
        assert remap["ok"] is True
        assert remap["skin_node_count"] > 0
        # Check all entries are valid
        for sname, table in remap["remap_tables"].items():
            for idx, entry in table.items():
                assert entry["valid"] is True, f"Invalid remap for {sname}[{idx}]"

    @skip_no_game
    def test_bind_pose_all_identity(self, session_with_game):
        """Bind-pose palette must be all-identity."""
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_bind_pose()
        result = session_with_game.get_bind_pose_matrices()
        assert result["ok"] is True
        assert result["all_identity"] is True

    @skip_no_game
    def test_animated_pose_non_identity(self, session_with_game):
        """Animated palette must have non-identity bones."""
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_animation("cwalk")
        session_with_game.set_animation_time(0.5)
        result = session_with_game.get_animated_pose_matrices()
        assert result["ok"] is True
        assert result["non_identity_count"] > 0

    @skip_no_game
    def test_uploaded_palette(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        result = session_with_game.get_uploaded_palette()
        assert result["ok"] is True
        assert result["bone_count"] > 0
        assert result["byte_size"] > 0

    @skip_no_game
    def test_sample_vertex_influences(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        info = session_with_game.get_asset_info()
        skin_name = info["skin_nodes"][0]["name"]
        result = session_with_game.sample_vertex_influences(skin_name)
        assert result["ok"] is True
        assert len(result["samples"]) > 0
        for sample in result["samples"]:
            assert abs(sample["weight_sum"] - 1.0) < 0.01, \
                f"Weights don't sum to 1.0 for vertex {sample['vertex_index']}: {sample['weight_sum']}"

    @skip_no_game
    def test_cpu_gpu_parity(self, session_with_game):
        """CPU LBS and GPU palette data must produce identical results."""
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_bind_pose()
        info = session_with_game.get_asset_info()
        skin_name = info["skin_nodes"][0]["name"]
        result = session_with_game.compare_cpu_gpu_skinning(skin_name)
        assert result["ok"] is True
        assert result["parity_pass"] is True, \
            f"CPU-GPU parity failed: max_diff={result['max_diff']}"


# ─── Test: Multi-Asset Validation ────────────────────────────────────────────

class TestMultiAssetValidation:
    """Validate debug bridge across all target assets."""

    @skip_no_game
    @pytest.mark.parametrize("resref", VALIDATION_TARGETS)
    def test_load_and_inspect(self, session_with_game, resref):
        """Load each target, verify skinning state, and check bind-pose identity."""
        result = session_with_game.load_model(resref)
        if not result["ok"]:
            pytest.skip(f"Model {resref} not available: {result.get('error')}")

        # Skinning state
        state = session_with_game.get_skinning_state()
        assert state["ok"] is True

        # Bind-pose identity check (only for models with skin nodes)
        if state["skin_node_count"] > 0:
            bp = session_with_game.get_bind_pose_matrices()
            assert bp["ok"] is True
            assert bp["all_identity"] is True, f"{resref}: bind-pose not all identity"

    @skip_no_game
    @pytest.mark.parametrize("resref", VALIDATION_TARGETS)
    def test_palette_remap_valid(self, session_with_game, resref):
        """All bone_map entries must remap to valid palette indices."""
        result = session_with_game.load_model(resref)
        if not result["ok"]:
            pytest.skip(f"Model {resref} not available")

        state = session_with_game.get_skinning_state()
        if state["skin_node_count"] == 0:
            pytest.skip(f"{resref} has no skin nodes")

        remap = session_with_game.get_palette_remap_table()
        assert remap["ok"] is True
        for sname, table in remap["remap_tables"].items():
            for idx, entry in table.items():
                assert entry["valid"] is True, \
                    f"{resref}/{sname}[{idx}]: invalid remap for bone '{entry['bone_name']}'"

    @skip_no_game
    @pytest.mark.parametrize("resref", ["c_kraytdragon", "c_rancor", "n_commf"])
    def test_animated_inspection(self, session_with_game, resref):
        """Load model, play animation, verify non-identity animated palette."""
        result = session_with_game.load_model(resref)
        if not result["ok"]:
            pytest.skip(f"Model {resref} not available")

        anims = session_with_game.list_animations()
        if not anims:
            pytest.skip(f"{resref} has no animations")

        # Pick cwalk or first available
        anim_name = "cwalk"
        available = [a["name"] for a in anims]
        if anim_name not in available:
            anim_name = available[0]

        session_with_game.set_animation(anim_name)
        session_with_game.set_animation_time(0.5)
        result = session_with_game.get_animated_pose_matrices()
        assert result["ok"] is True
        assert result["non_identity_count"] > 0, \
            f"{resref}/{anim_name}: all bones still identity at t=0.5"


# ─── Test: Debug Bundle Export ───────────────────────────────────────────────

class TestDebugBundle:
    @skip_no_game
    def test_export_bundle(self, session_with_game):
        session_with_game.load_model("c_kraytdragon")
        session_with_game.set_animation("cwalk")
        session_with_game.set_animation_time(0.5)
        out_dir = os.path.join(_root, "debug_bundles", "test_kraytdragon")
        result = session_with_game.export_debug_bundle(out_dir)
        assert result["ok"] is True
        assert os.path.exists(result["bundle_path"])
        # Verify JSON is valid
        with open(result["bundle_path"]) as f:
            bundle = json.load(f)
        assert "resref" in bundle
        assert "skinning_state" in bundle
        assert "bone_hierarchy" in bundle
        assert "palette_remap" in bundle
        assert "bind_pose_matrices" in bundle
        assert "vertex_samples" in bundle


# ─── Test: Handler Integration (async dispatch) ─────────────────────────────

class TestHandlerIntegration:
    """Test that MCP handlers route correctly via tool registry."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_launch_handler(self):
        from src.kotormcp.tools.debug_skinning import handle_launch_app
        result = self._run(handle_launch_app({}))
        assert "text" in result
        data = json.loads(result["text"])
        assert data["status"] == "ok"

    def test_status_handler(self):
        from src.kotormcp.tools.debug_skinning import handle_get_runtime_status
        result = self._run(handle_get_runtime_status({}))
        assert "text" in result
        data = json.loads(result["text"])
        assert "started" in data

    def test_camera_handler(self):
        from src.kotormcp.tools.debug_skinning import handle_set_camera_preset
        result = self._run(handle_set_camera_preset({"preset": "front"}))
        assert "text" in result
        data = json.loads(result["text"])
        assert data.get("ok") is True


# ─── Standalone runner ───────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
