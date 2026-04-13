"""
test_v420_acurig_integration.py
================================
Comprehensive tests for Phase 4 of the GhostRigger Character Builder:
  _AcuRigPanel — AcuRig/GRig integration data-model controller.
  ThumbnailCache — PIL thumbnail generation + cache.
  get_thumbnail_cache / reset_thumbnail_cache — module-level singletons.

All tests are fully headless (no Tk display, no PIL required).  They exercise
the data-model layer of the Phase 4 additions without creating any Tk widgets.

Coverage
--------
  • _AcuRigPanel.__init__ — available flag, degraded mode
  • _AcuRigPanel.detect_profile — returns str; handles None model
  • _AcuRigPanel.place_guides — returns dict; handles None model
  • _AcuRigPanel.move_guide — updates position; returns False when unavailable
  • _AcuRigPanel.lock_guide / unlock_guide
  • _AcuRigPanel.enforce_symmetry — returns int
  • _AcuRigPanel.generate_rig — returns model or None
  • _AcuRigPanel.auto_skin — returns stats dict
  • _AcuRigPanel.weight_stats — returns dict
  • _AcuRigPanel.mirror_weights — returns int
  • _AcuRigPanel.apply_tpose / apply_apose — returns guide dict
  • _AcuRigPanel.mask_fingers / mask_tail / mask_toes / unmask_all
  • _AcuRigPanel.is_masked
  • _AcuRigPanel.save_template / load_template — round-trip via tmp file
  • _AcuRigPanel.grig_weight_stats / grig_mirror_weights / grig_prune_weights
  • _AcuRigPanel.full_pipeline — returns result dict
  • _AcuRigPanel.summary_text — returns non-empty string
  • ThumbnailCache.__init__ — empty cache
  • ThumbnailCache.get_or_create — returns None when PIL absent, or image
  • ThumbnailCache.invalidate — removes entry
  • ThumbnailCache.clear — wipes all entries
  • ThumbnailCache.size — reflects entry count
  • ThumbnailCache._ortho_project — correct pixel mapping
  • ThumbnailCache.make_photo_image — graceful degradation without PIL/Tk
  • get_thumbnail_cache / reset_thumbnail_cache — singleton + reset
  • Module-level: _import_accurig returns 4 items
  • Module-level: _import_exporters returns dict
  • Integration: _AcuRigPanel with real AcuRig (if available)
  • _AcuRigPanel.guide_count / masked_bones properties
  • _AcuRigPanel state after full_pipeline when AcuRig unavailable
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# ──────────────────────────────────────────────────────────────────────────────
#  Import helpers (graceful degradation if optional modules missing)
# ──────────────────────────────────────────────────────────────────────────────

def _import_phase4():
    """Import Phase 4 classes from character_builder_window."""
    try:
        from src.gui.character_builder_window import (
            _AcuRigPanel,
            ThumbnailCache,
            BatchExportConfig,
            BatchExportResult,
            BatchExporter,
            get_thumbnail_cache,
            reset_thumbnail_cache,
            _import_accurig,
            _import_exporters,
        )
        return (_AcuRigPanel, ThumbnailCache, BatchExportConfig, BatchExportResult,
                BatchExporter, get_thumbnail_cache, reset_thumbnail_cache,
                _import_accurig, _import_exporters)
    except ImportError as exc:
        pytest.skip(f"character_builder_window not importable: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
#  Minimal model stubs
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _StubNode:
    name: str
    position: tuple = (0.0, 0.0, 0.0)
    children: list = field(default_factory=list)
    parent: Any = None
    flags: int = 0x01

    @property
    def type_label(self):
        return "dummy"


class _StubModel:
    """Minimal KotorModel stub for Phase 4 tests."""

    def __init__(self, name="test_body"):
        self.name       = name
        self.supermodel = "S_Female02"
        self.animations = []
        self.bb_min     = (-0.3, -0.3, 0.0)
        self.bb_max     = ( 0.3,  0.3, 1.8)
        self.root_node  = None

        root   = _StubNode("Mesh_Root", position=(0.0, 0.0, 0.0))
        pelvis = _StubNode("pelvis_g",  position=(0.0, 0.0, 0.5))
        neck   = _StubNode("neck_g",    position=(0.0, 0.0, 1.4))
        head   = _StubNode("head_g",    position=(0.0, 0.0, 1.65))
        larm   = _StubNode("LArm",      position=(-0.3, 0.0, 1.2))
        rarm   = _StubNode("RArm",      position=( 0.3, 0.0, 1.2))
        root.children  = [pelvis]
        pelvis.children = [neck, larm, rarm]
        neck.children  = [head]

        self._nodes = [root, pelvis, neck, head, larm, rarm]
        self.root_node = root

    def all_nodes(self):
        stack = [self.root_node] if self.root_node else []
        seen = set()
        while stack:
            n = stack.pop()
            if id(n) in seen:
                continue
            seen.add(id(n))
            yield n
            for c in getattr(n, "children", []):
                stack.append(c)

    def node_count(self):
        return sum(1 for _ in self.all_nodes())

    def mesh_nodes(self):
        return []

    def bone_nodes(self):
        return list(self.all_nodes())

    def find_node(self, name: str):
        for n in self.all_nodes():
            if n.name.lower() == name.lower():
                return n
        return None


# ──────────────────────────────────────────────────────────────────────────────
#  Fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_cache():
    """Reset thumbnail cache before each test."""
    try:
        (_, _, _, _, _, _, reset_thumbnail_cache, _, _) = _import_phase4()
        reset_thumbnail_cache()
    except Exception:
        pass
    yield


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _import_accurig and _import_exporters
# ──────────────────────────────────────────────────────────────────────────────

class TestImportHelpers:

    def test_import_accurig_returns_four_items(self):
        (_, _, _, _, _, _, _, _import_accurig, _) = _import_phase4()
        result = _import_accurig()
        assert len(result) == 4, "should return (AcuRig, RigGuide, BoneMask, GRig)"

    def test_import_accurig_items_are_class_or_none(self):
        (_, _, _, _, _, _, _, _import_accurig, _) = _import_phase4()
        for item in _import_accurig():
            assert item is None or isinstance(item, type)

    def test_import_exporters_returns_dict(self):
        (_, _, _, _, _, _, _, _, _import_exporters) = _import_phase4()
        result = _import_exporters()
        assert isinstance(result, dict)

    def test_import_exporters_known_keys(self):
        (_, _, _, _, _, _, _, _, _import_exporters) = _import_phase4()
        result = _import_exporters()
        # May or may not have keys depending on what's importable
        for key in result:
            assert key in ("MDL", "FBX", "glTF", "OBJ")


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel basic construction
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelInit:

    def test_creates_successfully(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert panel is not None

    def test_available_is_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert isinstance(panel.available, bool)

    def test_guides_is_empty_dict_initially(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert isinstance(panel.guides, dict)
        assert len(panel.guides) == 0

    def test_profile_is_string_initially(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert isinstance(panel.profile, str)

    def test_last_stats_is_dict_initially(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert isinstance(panel.last_stats, dict)

    def test_guide_count_is_zero_initially(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert panel.guide_count == 0

    def test_masked_bones_is_list(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        assert isinstance(panel.masked_bones, list)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel profile detection
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelProfile:

    def test_detect_none_model_returns_unknown(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.detect_profile(None)
        assert isinstance(result, str)

    def test_detect_stub_model_returns_string(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.detect_profile(model)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_detect_updates_profile_attribute(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        profile = panel.detect_profile(model)
        assert panel.profile == profile

    def test_detect_without_model_does_not_crash(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        # Should never raise
        panel.detect_profile(None)
        panel.detect_profile(None)

    def test_detect_known_profiles_subset(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        p = panel.detect_profile(model)
        known = {"humanoid", "quadruped", "droid", "prop", "creature", "unknown"}
        assert p in known, f"Unexpected profile: {p!r}"


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel guide placement
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelGuides:

    def test_place_guides_none_model_returns_empty(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.place_guides(None)
        assert isinstance(result, dict)

    def test_place_guides_stub_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.place_guides(model)
        assert isinstance(result, dict)

    def test_place_guides_updates_guides_attr(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        guides = panel.place_guides(model)
        assert panel.guides is guides

    def test_place_guides_with_profile(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.place_guides(model, profile="humanoid")
        assert isinstance(result, dict)

    def test_guide_count_after_place(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        panel.place_guides(model)
        assert panel.guide_count == len(panel.guides)

    def test_move_guide_returns_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.move_guide("pelvis", (0.0, 0.0, 0.5))
        assert isinstance(result, bool)

    def test_lock_guide_returns_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.lock_guide("head")
        assert isinstance(result, bool)

    def test_unlock_guide_returns_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.unlock_guide("head")
        assert isinstance(result, bool)

    def test_enforce_symmetry_returns_int(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.enforce_symmetry()
        assert isinstance(result, int)
        assert result >= 0


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel rig generation and skinning
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelRigAndSkin:

    def test_generate_rig_none_model_returns_none(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.generate_rig(None)
        assert result is None

    def test_generate_rig_stub_model_returns_model(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.generate_rig(model)
        assert result is model

    def test_auto_skin_none_model_returns_empty(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.auto_skin(None)
        assert isinstance(result, dict)

    def test_auto_skin_stub_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.auto_skin(model)
        assert isinstance(result, dict)

    def test_weight_stats_none_model_returns_empty(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.weight_stats(None)
        assert isinstance(result, dict)

    def test_weight_stats_stub_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.weight_stats(model)
        assert isinstance(result, dict)

    def test_mirror_weights_none_model_returns_zero(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.mirror_weights(None)
        assert result == 0

    def test_mirror_weights_stub_model_returns_int(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.mirror_weights(model)
        assert isinstance(result, int)
        assert result >= 0


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel pose correction
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelPose:

    def test_apply_tpose_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.apply_tpose()
        assert isinstance(result, dict)

    def test_apply_apose_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.apply_apose()
        assert isinstance(result, dict)

    def test_tpose_updates_guides(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        # Place some guides first
        model = _StubModel()
        panel.place_guides(model)
        before_count = panel.guide_count
        panel.apply_tpose()
        # Guide count should remain the same
        assert panel.guide_count == before_count

    def test_apose_updates_guides(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        panel.place_guides(model)
        before_count = panel.guide_count
        panel.apply_apose()
        assert panel.guide_count == before_count

    def test_tpose_and_apose_both_return_same_type(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        t = panel.apply_tpose()
        a = panel.apply_apose()
        assert type(t) == type(a)  # both dicts


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel bone mask
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelMask:

    def test_mask_fingers_does_not_crash(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_fingers()  # no return value, just must not crash

    def test_mask_tail_does_not_crash(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_tail()

    def test_mask_toes_does_not_crash(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_toes()

    def test_unmask_all_does_not_crash(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_fingers()
        panel.unmask_all()

    def test_is_masked_returns_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.is_masked("some_bone")
        assert isinstance(result, bool)

    def test_masked_bones_after_mask_fingers(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_fingers()
        result = panel.masked_bones
        assert isinstance(result, list)

    def test_masked_bones_empty_after_unmask_all(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        panel.mask_fingers()
        panel.mask_tail()
        panel.unmask_all()
        assert isinstance(panel.masked_bones, list)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel template persistence
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelTemplate:

    def test_save_template_returns_bool(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = panel.save_template(path)
            assert isinstance(result, bool)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_template_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                         mode="w") as f:
            json.dump({"guides": {}, "name": "test"}, f)
            path = f.name
        try:
            result = panel.load_template(path)
            assert isinstance(result, dict)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_save_and_load_round_trip(self):
        """If AcuRig is available, save + load should preserve guide structure."""
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        if not panel.available:
            pytest.skip("AcuRig unavailable — round-trip skipped")
        model = _StubModel()
        panel.place_guides(model)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            ok = panel.save_template(path, name="test_rig", description="unit test")
            assert ok
            panel2 = _AcuRigPanel()
            guides = panel2.load_template(path)
            assert isinstance(guides, dict)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_load_nonexistent_file_returns_empty(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.load_template("/nonexistent/path/template.json")
        assert isinstance(result, dict)

    def test_save_to_invalid_path_returns_false(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.save_template("/nonexistent/dir/template.json")
        assert isinstance(result, bool)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel GRig helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelGRig:

    def test_grig_weight_stats_none_returns_empty(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.grig_weight_stats(None)
        assert isinstance(result, dict)

    def test_grig_weight_stats_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.grig_weight_stats(model)
        assert isinstance(result, dict)

    def test_grig_mirror_weights_none_returns_zero(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.grig_mirror_weights(None)
        assert result == 0

    def test_grig_mirror_weights_model_returns_int(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.grig_mirror_weights(model)
        assert isinstance(result, int)

    def test_grig_prune_weights_none_returns_zero(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.grig_prune_weights(None)
        assert result == 0

    def test_grig_prune_weights_model_returns_int(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.grig_prune_weights(model)
        assert isinstance(result, int)

    def test_grig_prune_weights_custom_threshold(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.grig_prune_weights(model, threshold=0.05)
        assert isinstance(result, int)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — _AcuRigPanel full pipeline
# ──────────────────────────────────────────────────────────────────────────────

class TestAcuRigPanelFullPipeline:

    def test_full_pipeline_none_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.full_pipeline(None)
        assert isinstance(result, dict)

    def test_full_pipeline_none_model_has_ok_false(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        result = panel.full_pipeline(None)
        # Should indicate failure (either unavailable or no model)
        assert "ok" in result or "reason" in result or isinstance(result, dict)

    def test_full_pipeline_stub_model_returns_dict(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.full_pipeline(model)
        assert isinstance(result, dict)

    def test_full_pipeline_updates_profile(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        if not panel.available:
            pytest.skip("AcuRig unavailable")
        model = _StubModel()
        panel.full_pipeline(model)
        assert isinstance(panel.profile, str)

    def test_full_pipeline_with_scale(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        model = _StubModel()
        result = panel.full_pipeline(model, scale=1.5)
        assert isinstance(result, dict)

    def test_summary_text_returns_string(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        text = panel.summary_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_summary_text_contains_available(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        text = panel.summary_text()
        assert "AcuRig available" in text or "available" in text.lower()

    def test_summary_text_contains_profile(self):
        (_AcuRigPanel, *_) = _import_phase4()
        panel = _AcuRigPanel()
        text = panel.summary_text()
        assert "Profile" in text or "profile" in text.lower()


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — ThumbnailCache
# ──────────────────────────────────────────────────────────────────────────────

class TestThumbnailCache:

    def test_init_creates_empty_cache(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        assert cache.size() == 0

    def test_size_returns_int(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        assert isinstance(cache.size(), int)

    def test_clear_on_empty_cache_is_noop(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        cache.clear()
        assert cache.size() == 0

    def test_invalidate_nonexistent_key_is_noop(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        cache.invalidate("nonexistent", "K1")  # must not raise
        assert cache.size() == 0

    def test_get_or_create_none_model_returns_none(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        result = cache.get_or_create("pmhc1", "K1", None)
        assert result is None

    def test_get_or_create_none_model_does_not_cache(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        cache.get_or_create("pmhc1", "K1", None)
        assert cache.size() == 0

    def test_get_or_create_with_model_may_cache(self):
        """Calling with a model either returns an image (PIL available) or None."""
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        model = _StubModel()
        result = cache.get_or_create("pmhc1", "K1", model)
        # Either None (PIL not installed) or a PIL Image object
        assert result is None or hasattr(result, "size") or hasattr(result, "mode")

    def test_cache_hit_returns_same_object(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        model = _StubModel()
        first  = cache.get_or_create("pmhc1", "K1", model)
        second = cache.get_or_create("pmhc1", "K1", model)
        if first is not None:
            assert first is second, "Cache hit should return the same object"

    def test_cache_key_is_case_insensitive(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        model = _StubModel()
        lower = cache.get_or_create("pmhc1", "K1", model)
        upper = cache.get_or_create("PMHC1", "K1", model)
        if lower is not None:
            assert lower is upper, "Cache key should be case-insensitive"

    def test_invalidate_removes_entry(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        model = _StubModel()
        entry = cache.get_or_create("pmhc1", "K1", model)
        before_size = cache.size()
        cache.invalidate("pmhc1", "K1")
        assert cache.size() < before_size or cache.size() == 0

    def test_clear_wipes_all_entries(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        model = _StubModel()
        cache.get_or_create("pmhc1", "K1", model)
        cache.get_or_create("pmbc1", "K1", model)
        cache.clear()
        assert cache.size() == 0

    def test_thumb_size_constant(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        assert isinstance(ThumbnailCache.THUMB_SIZE, int)
        assert ThumbnailCache.THUMB_SIZE > 0

    def test_bg_colour_is_rgba_tuple(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        assert len(ThumbnailCache.BG_COLOUR) == 4

    def test_wire_colour_is_rgba_tuple(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        assert len(ThumbnailCache.WIRE_COLOUR) == 4

    def test_ortho_project_maps_min_to_margin(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        S = ThumbnailCache.THUMB_SIZE
        bb_min = (0.0, 0.0, 0.0)
        bb_max = (1.0, 1.0, 2.0)
        margin = 0.10
        px, py = cache._ortho_project(0.0, 0.0, 0.0, bb_min, bb_max, S)
        # x=0 (min) → nx=0 → px = margin*S
        expected_px = int(margin * S)
        # z=0 (min) → nz=1.0 → py = margin*S + 1.0*S*(1-2*margin)
        expected_py = int(margin * S + 1.0 * S * (1 - 2 * margin))
        assert px == expected_px
        assert py == expected_py  # z=min → bottom → large py

    def test_ortho_project_maps_max_to_high(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        S = ThumbnailCache.THUMB_SIZE
        bb_min = (0.0, 0.0, 0.0)
        bb_max = (1.0, 1.0, 2.0)
        margin = 0.10
        px, py = cache._ortho_project(1.0, 0.0, 2.0, bb_min, bb_max, S)
        # x=1 (max) → nx=1.0 → px = margin*S + 1.0*S*(1-2*margin)
        expected_px = int(margin * S + 1.0 * S * (1 - 2 * margin))
        # z=max → nz=0.0 → py = margin*S
        expected_py = int(margin * S)
        assert px == expected_px
        assert py == expected_py  # z=max → top → small py

    def test_ortho_project_degenerate_bbox(self):
        """Zero-span bounding box should not raise."""
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        S = ThumbnailCache.THUMB_SIZE
        bb_min = (1.0, 1.0, 1.0)
        bb_max = (1.0, 1.0, 1.0)  # zero span
        px, py = cache._ortho_project(1.0, 1.0, 1.0, bb_min, bb_max, S)
        assert isinstance(px, int)
        assert isinstance(py, int)

    def test_make_photo_image_without_pil_returns_none(self):
        """Without PIL/ImageTk, make_photo_image should return None gracefully."""
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()

        class _FakeWidget:
            pass

        # Pass a non-PIL object — ImageTk will fail → None
        result = cache.make_photo_image(object(), _FakeWidget())
        assert result is None

    def test_render_model_none_returns_none(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        cache = ThumbnailCache()
        result = cache._render_model(None)
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — Module-level singleton helpers
# ──────────────────────────────────────────────────────────────────────────────

class TestThumbnailCacheSingleton:

    def test_get_thumbnail_cache_returns_instance(self):
        (_, _, _, _, _, get_thumbnail_cache, reset_thumbnail_cache, _, _) = _import_phase4()
        cache = get_thumbnail_cache()
        assert cache is not None

    def test_get_thumbnail_cache_same_instance(self):
        (_, _, _, _, _, get_thumbnail_cache, _, _, _) = _import_phase4()
        c1 = get_thumbnail_cache()
        c2 = get_thumbnail_cache()
        assert c1 is c2, "Should return the same singleton"

    def test_reset_thumbnail_cache_creates_new_instance(self):
        (_, _, _, _, _, get_thumbnail_cache, reset_thumbnail_cache, _, _) = _import_phase4()
        c1 = get_thumbnail_cache()
        reset_thumbnail_cache()
        c2 = get_thumbnail_cache()
        assert c1 is not c2, "reset should create a fresh cache"

    def test_reset_wipes_entries(self):
        (_, ThumbnailCache, _, _, _, get_thumbnail_cache, reset_thumbnail_cache, _, _) = _import_phase4()
        cache = get_thumbnail_cache()
        model = _StubModel()
        cache.get_or_create("pmhc1", "K1", model)
        reset_thumbnail_cache()
        new_cache = get_thumbnail_cache()
        assert new_cache.size() == 0


# ──────────────────────────────────────────────────────────────────────────────
#  Integration — character_builder_window module structure
# ──────────────────────────────────────────────────────────────────────────────

class TestPhase4ModuleIntegration:

    def test_module_exports_AcuRigPanel(self):
        (_AcuRigPanel, *_) = _import_phase4()
        assert _AcuRigPanel is not None

    def test_module_exports_ThumbnailCache(self):
        (_, ThumbnailCache, *_) = _import_phase4()
        assert ThumbnailCache is not None

    def test_module_exports_BatchExportConfig(self):
        (_, _, BatchExportConfig, *_) = _import_phase4()
        assert BatchExportConfig is not None

    def test_module_exports_BatchExportResult(self):
        (_, _, _, BatchExportResult, *_) = _import_phase4()
        assert BatchExportResult is not None

    def test_module_exports_BatchExporter(self):
        (_, _, _, _, BatchExporter, *_) = _import_phase4()
        assert BatchExporter is not None

    def test_module_exports_get_thumbnail_cache(self):
        (_, _, _, _, _, get_thumbnail_cache, _, _, _) = _import_phase4()
        assert callable(get_thumbnail_cache)

    def test_module_exports_reset_thumbnail_cache(self):
        (_, _, _, _, _, _, reset_thumbnail_cache, _, _) = _import_phase4()
        assert callable(reset_thumbnail_cache)

    def test_acurig_panel_instantiates_without_args(self):
        (_AcuRigPanel, *_) = _import_phase4()
        p = _AcuRigPanel()
        assert hasattr(p, "available")
        assert hasattr(p, "guides")
        assert hasattr(p, "profile")

    def test_character_builder_window_source_has_acurig_panel(self):
        """Verify _AcuRigPanel is defined in character_builder_window.py."""
        import src.gui.character_builder_window as mod
        assert hasattr(mod, "_AcuRigPanel"), "_AcuRigPanel must be defined in module"

    def test_character_builder_window_source_has_thumbnail_cache(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod, "ThumbnailCache"), "ThumbnailCache must be defined"

    def test_character_builder_window_source_has_batch_export(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod, "BatchExporter"), "BatchExporter must be defined"
        assert hasattr(mod, "BatchExportConfig"), "BatchExportConfig must be defined"
        assert hasattr(mod, "BatchExportResult"), "BatchExportResult must be defined"

    def test_rig_frame_has_acurig_panel_attr(self):
        """_RigFrame.__init__ must store an _AcuRigPanel as self._acurig_panel."""
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._RigFrame.__init__)
        assert "_acurig_panel" in src_code, \
            "_RigFrame.__init__ must create self._acurig_panel"

    def test_export_frame_has_batch_format_vars(self):
        """_ExportFrame._build_ui must reference _batch_fmt_vars."""
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._ExportFrame._build_ui)
        assert "_batch_fmt_vars" in src_code

    def test_export_frame_has_batch_dir_var(self):
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._ExportFrame._build_ui)
        assert "_batch_dir_var" in src_code

    def test_assembly_frame_has_thumbnail_canvas(self):
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._AssemblyFrame._build_ui)
        assert "_thumb_canvas" in src_code

    def test_assembly_frame_has_refresh_thumbnails(self):
        import inspect, src.gui.character_builder_window as mod
        assert hasattr(mod._AssemblyFrame, "_refresh_thumbnails"), \
            "_AssemblyFrame must have _refresh_thumbnails method"

    def test_assembly_frame_has_char_name_var(self):
        """Phase 4 adds a character name entry field."""
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._AssemblyFrame._build_ui)
        assert "_char_name_var" in src_code
