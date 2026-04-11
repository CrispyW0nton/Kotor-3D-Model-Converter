"""
test_v345_animation_library_export.py
======================================

Tests for the AnimationLibrary, FBXAnimationExporter, and
AnimationRetargeter pipeline introduced in v3.4.5.

Priority requirements tested:
  1. Animations play smoothly and retain original quality
     → FBX export includes all keyframes, no anim_scale distortion
  2. Animation Library catalogs all game animations
     → AnimationLibrary.scan() populates entries correctly
  3. Export animations to rigged FBX models
     → FBXAnimationExporter produces valid FBX ASCII 7.4 output
     → Bone remap (Mixamo / UE5 / custom) works correctly
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import List

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────
BANTHA_MDL = Path("test_assets/c_bantha/c_bantha.mdl")
BANTHA_MDX = Path("test_assets/c_bantha/c_bantha.mdx")

pytestmark = pytest.mark.skipif(
    not BANTHA_MDL.exists(),
    reason="test_assets/c_bantha not available"
)


def _load_bantha():
    from src.core.kotor_loader import load_model_from_file
    return load_model_from_file(str(BANTHA_MDL), str(BANTHA_MDX))


def _bantha_engine():
    from src.core.animation_engine import AnimationEngine
    return AnimationEngine(_load_bantha())


# ═══════════════════════════════════════════════════════════════════════
#  1. AnimationEntry data class
# ═══════════════════════════════════════════════════════════════════════

class TestAnimationEntry:

    def test_import(self):
        from src.core.animation_library import AnimationEntry
        ae = AnimationEntry(
            model_name="c_bantha", game="K1", anim_name="cwalk",
            length=1.47, node_count=34, key_count=1000, model_class="creature"
        )
        assert ae.display_name == "c_bantha::cwalk"

    def test_fps_estimate_30(self):
        from src.core.animation_library import AnimationEntry
        ae = AnimationEntry(
            model_name="x", game="K1", anim_name="walk",
            length=1.0, node_count=10, key_count=300, model_class="c"
        )
        assert ae.fps_estimate == 30.0

    def test_fps_estimate_clamped(self):
        from src.core.animation_library import AnimationEntry
        ae = AnimationEntry(
            model_name="x", game="K1", anim_name="walk",
            length=1.0, node_count=1, key_count=9999, model_class="c"
        )
        assert ae.fps_estimate <= 120.0

    def test_fps_estimate_zero_length(self):
        from src.core.animation_library import AnimationEntry
        ae = AnimationEntry(
            model_name="x", game="K1", anim_name="walk",
            length=0.0, node_count=10, key_count=300, model_class="c"
        )
        # Should not raise — defaults to 30
        assert ae.fps_estimate == 30.0


# ═══════════════════════════════════════════════════════════════════════
#  2. AnimationLibrary (unit, no game files)
# ═══════════════════════════════════════════════════════════════════════

class TestAnimationLibraryBasic:

    def test_import(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        assert lib.entries == []
        assert lib.is_scanning is False

    def test_stats_empty(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        s = lib.stats
        assert s['total_animations'] == 0
        assert s['total_models'] == 0

    def test_search_empty(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        results = lib.search("walk")
        assert results == []

    def test_get_all_model_names_empty(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        assert lib.get_all_model_names() == []

    def test_get_all_anim_names_empty(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        assert lib.get_all_anim_names() == []

    def test_double_scan_guard(self):
        """Second scan while first is running should be a no-op."""
        from src.core.animation_library import AnimationLibrary

        class FakeLib:
            models = []
            def get_model_data(self, entry):
                return None, None

        lib = AnimationLibrary()
        lib.is_scanning = True   # pretend already scanning
        lib.scan(FakeLib(), background=True)  # should NOT start a thread
        assert lib._scan_thread is None


# ═══════════════════════════════════════════════════════════════════════
#  3. AnimationLibrary with real bantha model
# ═══════════════════════════════════════════════════════════════════════

class TestAnimationLibraryWithModel:

    def _make_fake_game_lib(self):
        """Return a minimal fake GameLibrary that exposes c_bantha."""
        class FakeEntry:
            resref = 'c_bantha'
            game = 'K1'
            classification = 'creature'

        class FakeGameLib:
            models = [FakeEntry()]
            def get_model_data(self, entry):
                if entry.resref == 'c_bantha':
                    mdl = BANTHA_MDL.read_bytes()
                    mdx = BANTHA_MDX.read_bytes() if BANTHA_MDX.exists() else b''
                    return mdl, mdx
                return None, None

        return FakeGameLib()

    def test_scan_populates_entries(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        fake = self._make_fake_game_lib()
        lib.scan(fake, background=False)
        assert len(lib.entries) > 0, "Scan should produce entries for c_bantha"

    def test_scan_finds_walk_animation(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        names = {e.anim_name for e in lib.entries}
        assert 'cwalk' in names or any('walk' in n for n in names)

    def test_stats_populated_after_scan(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        s = lib.stats
        assert s['total_animations'] > 0
        assert s['total_models'] >= 1

    def test_search_by_name(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        results = lib.search(query='walk')
        assert len(results) > 0

    def test_search_by_game(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        k1 = lib.search(game='K1')
        k2 = lib.search(game='K2')
        assert len(k1) > 0
        assert len(k2) == 0   # fake lib is K1 only

    def test_get_model_animations(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        anims = lib.get_model_animations('c_bantha')
        assert len(anims) > 0

    def test_get_engine_lazy_loads_model(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        lib.scan(self._make_fake_game_lib(), background=False)
        entry = lib.entries[0]
        engine = lib.get_engine(entry)
        assert engine is not None
        assert engine.model.name is not None

    def test_background_scan_completes(self):
        from src.core.animation_library import AnimationLibrary
        lib = AnimationLibrary()
        done_event = threading.Event()
        result = [0]

        def _complete(n):
            result[0] = n
            done_event.set()

        lib.scan(self._make_fake_game_lib(),
                 on_complete=_complete, background=True)
        done_event.wait(timeout=10)
        assert result[0] > 0


# ═══════════════════════════════════════════════════════════════════════
#  4. AnimationRetargeter
# ═══════════════════════════════════════════════════════════════════════

class TestAnimationRetargeter:

    def test_import(self):
        from src.core.animation_library import AnimationRetargeter
        assert AnimationRetargeter.KOTOR_TO_MIXAMO
        assert AnimationRetargeter.KOTOR_TO_UE5

    def test_mixamo_map_contains_key_bones(self):
        from src.core.animation_library import AnimationRetargeter
        m = AnimationRetargeter.KOTOR_TO_MIXAMO
        assert 'pelvis_g' in m
        assert 'rhand' in m
        assert 'lhand' in m
        assert 'headhook' in m or 'camerahook' in m

    def test_ue5_map_contains_key_bones(self):
        from src.core.animation_library import AnimationRetargeter
        m = AnimationRetargeter.KOTOR_TO_UE5
        assert 'pelvis_g' in m
        assert m['pelvis_g'] == 'pelvis'
        assert m['rhand'] == 'hand_r'

    def test_build_map_case_insensitive(self):
        from src.core.animation_library import AnimationRetargeter
        remap = AnimationRetargeter.build_map({'Pelvis_G': 'hips', 'RHand': 'rh'})
        assert remap.get('pelvis_g') == 'hips'
        assert remap.get('rhand') == 'rh'

    def test_build_map_case_sensitive(self):
        from src.core.animation_library import AnimationRetargeter
        remap = AnimationRetargeter.build_map(
            {'Pelvis_G': 'hips'}, case_insensitive=False)
        assert 'Pelvis_G' in remap
        assert 'pelvis_g' not in remap

    def test_save_and_load_json(self):
        from src.core.animation_library import AnimationRetargeter
        remap = {'pelvis_g': 'hips', 'rhand': 'rh'}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'remap.json')
            AnimationRetargeter.save_json(remap, path)
            loaded = AnimationRetargeter.from_json(path)
        assert loaded['pelvis_g'] == 'hips'
        assert loaded['rhand'] == 'rh'

    def test_kotor_bones_list_nonempty(self):
        from src.core.animation_library import AnimationRetargeter
        assert len(AnimationRetargeter.KOTOR_BONES) > 10


# ═══════════════════════════════════════════════════════════════════════
#  5. FBXAnimationExporter — structure tests (no game files needed)
# ═══════════════════════════════════════════════════════════════════════

class TestFBXAnimationExporterStructure:

    def test_import(self):
        from src.core.animation_library import FBXAnimationExporter
        exp = FBXAnimationExporter()
        assert exp is not None

    def test_export_no_anim_returns_false(self):
        from src.core.animation_library import FBXAnimationExporter
        from src.core.animation_engine import AnimationEngine

        model = _load_bantha()
        engine = AnimationEngine(model)
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            ok = exp.export(engine, "__nonexistent_anim__",
                            os.path.join(d, "out.fbx"))
        assert ok is False

    def test_export_all_no_anims_model(self):
        """export_all on a model without animations returns False."""
        from src.core.animation_library import FBXAnimationExporter
        from src.core.animation_engine import AnimationEngine
        from src.core.model_data import KotorModel

        # Build a model with no animations
        empty_model = KotorModel()
        empty_model.name = "empty"
        empty_model.animations = []
        engine = AnimationEngine(empty_model)
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            ok = exp.export_all(engine, os.path.join(d, "out.fbx"))
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════
#  6. FBXAnimationExporter — integration tests (bantha model)
# ═══════════════════════════════════════════════════════════════════════

class TestFBXAnimationExporterIntegration:

    def test_export_single_animation(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        assert engine.model.animations, "c_bantha must have animations"
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, f"{anim.name}.fbx")
            ok = exp.export(engine, anim.name, path)
            assert ok is True
            assert os.path.exists(path)
            size = os.path.getsize(path)
            assert size > 1000, f"FBX file too small: {size} bytes"

    def test_fbx_header_is_valid(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert "; FBX 7.4.0" in content
        assert "FBXHeaderExtension:" in content
        assert "FBXVersion: 7400" in content
        assert "Objects:" in content
        assert "Connections:" in content

    def test_fbx_contains_skeleton_nodes(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert "LimbNode" in content, "FBX must contain skeleton LimbNode entries"
        assert "Skeleton" in content, "FBX must contain Skeleton attribute nodes"

    def test_fbx_contains_animation_stack(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert "AnimationStack:" in content
        assert "AnimationLayer:" in content
        assert "AnimationCurve:" in content

    def test_fbx_contains_takes_block(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        # Takes block for Blender/UE4 compat
        assert "Takes:" in content

    def test_fbx_anim_name_in_file(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert anim.name in content, f"Anim name '{anim.name}' missing from FBX"

    def test_export_all_animations(self):
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "all.fbx")
            ok = exp.export_all(engine, path)
            assert ok is True
            size = os.path.getsize(path)
            assert size > 10000, f"All-anim FBX too small: {size}"
            # All animation names should appear
            content = open(path).read()
            for a in engine.model.animations:
                assert a.name in content, f"Anim '{a.name}' missing from all-anims FBX"

    def test_export_with_mixamo_remap(self):
        from src.core.animation_library import FBXAnimationExporter, AnimationRetargeter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        remap = AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_MIXAMO)
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mixamo.fbx")
            ok = exp.export(engine, anim.name, path, bone_remap=remap)
            assert ok is True

    def test_export_with_ue5_remap(self):
        from src.core.animation_library import FBXAnimationExporter, AnimationRetargeter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        remap = AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_UE5)
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ue5.fbx")
            ok = exp.export(engine, anim.name, path, bone_remap=remap)
            assert ok is True

    def test_export_no_scale_distortion(self):
        """Verify anim_scale=1.0 is preserved (no position inflation)."""
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        # anim_scale on bantha should be 1.0
        anim_scale = getattr(engine.model, 'anim_scale', 1.0) or 1.0
        assert anim_scale == 1.0, (
            "c_bantha anim_scale must be 1.0 for original-quality animation")
        # Verify FBX export succeeds with that scale
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "scale_test.fbx")
            ok = exp.export(engine, anim.name, path)
            assert ok is True


# ═══════════════════════════════════════════════════════════════════════
#  7. FBX keyframe quality tests
# ═══════════════════════════════════════════════════════════════════════

class TestFBXKeyframeQuality:

    def test_position_keyframes_present(self):
        """FBX must contain T|X/T|Y/T|Z curve data."""
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kf_test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert '"T|X"' in content or '"T|Y"' in content or '"T|Z"' in content

    def test_rotation_keyframes_present(self):
        """FBX must contain R|X/R|Y/R|Z curve data."""
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "kf_test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        assert '"R|X"' in content or '"R|Y"' in content or '"R|Z"' in content

    def test_keyframe_times_nonzero(self):
        """Animation should have real time span (not all zeros)."""
        from src.core.animation_library import FBXAnimationExporter
        engine = _bantha_engine()
        anim = engine.model.animations[0]
        assert anim.length > 0, "Animation must have positive length"
        exp = FBXAnimationExporter()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "time_test.fbx")
            exp.export(engine, anim.name, path)
            content = open(path).read()
        # LocalStop should be non-zero
        FBX_TICKS = 46186158000
        expected_ticks = int(anim.length * FBX_TICKS)
        assert str(expected_ticks) in content, (
            f"Expected tick count {expected_ticks} for length {anim.length}s not found")


# ═══════════════════════════════════════════════════════════════════════
#  8. Batch export helper
# ═══════════════════════════════════════════════════════════════════════

class TestBatchExport:

    def _make_lib_with_bantha(self):
        from src.core.animation_library import AnimationLibrary
        class FakeEntry:
            resref = 'c_bantha'
            game = 'K1'
            classification = 'creature'

        class FakeGameLib:
            models = [FakeEntry()]
            def get_model_data(self, entry):
                if entry.resref == 'c_bantha':
                    mdl = BANTHA_MDL.read_bytes()
                    mdx = BANTHA_MDX.read_bytes() if BANTHA_MDX.exists() else b''
                    return mdl, mdx
                return None, None

        lib = AnimationLibrary()
        lib.scan(FakeGameLib(), background=False)
        return lib

    def test_batch_export_fbx(self):
        from src.core.animation_library import batch_export_animations
        alib = self._make_lib_with_bantha()
        with tempfile.TemporaryDirectory() as d:
            exported = batch_export_animations(alib, d, fmt="fbx")
            assert len(exported) > 0
            for path in exported:
                assert os.path.exists(path)
                assert path.endswith('.fbx')

    def test_batch_export_bvh(self):
        from src.core.animation_library import batch_export_animations
        alib = self._make_lib_with_bantha()
        with tempfile.TemporaryDirectory() as d:
            exported = batch_export_animations(alib, d, fmt="bvh")
            assert len(exported) > 0
            for path in exported:
                assert path.endswith('.bvh')

    def test_batch_export_json(self):
        from src.core.animation_library import batch_export_animations
        alib = self._make_lib_with_bantha()
        with tempfile.TemporaryDirectory() as d:
            exported = batch_export_animations(alib, d, fmt="json")
            assert len(exported) > 0
            for path in exported:
                assert path.endswith('.json')
                # Validate JSON is parseable
                with open(path) as f:
                    data = json.load(f)
                assert 'anim_name' in data or 'name' in data or 'animation' in data

    def test_batch_progress_callback(self):
        from src.core.animation_library import batch_export_animations
        alib = self._make_lib_with_bantha()
        progress_calls = []

        def _prog(done, total, path):
            progress_calls.append((done, total, path))

        with tempfile.TemporaryDirectory() as d:
            batch_export_animations(alib, d, fmt="fbx", on_progress=_prog)

        assert len(progress_calls) > 0
        # Final call should have done == total
        last = progress_calls[-1]
        assert last[0] == last[1]


# ═══════════════════════════════════════════════════════════════════════
#  9. AnimationLibraryPanel wiring in main_window.py
# ═══════════════════════════════════════════════════════════════════════

class TestAnimationLibraryPanelWiring:

    @classmethod
    def setup_class(cls):
        cls.MW_SRC = open("src/gui/main_window.py").read()

    def test_panel_class_defined(self):
        assert "class AnimationLibraryPanel" in self.MW_SRC

    def test_panel_instantiated_in_main_window(self):
        assert "self.anim_lib_panel = AnimationLibraryPanel(" in self.MW_SRC

    def test_panel_added_to_notebook(self):
        assert "right_nb.add(self.anim_lib_panel" in self.MW_SRC

    def test_animlib_tab_name_registered(self):
        assert "'animlib'" in self.MW_SRC

    def test_panel_receives_library_callback(self):
        assert "get_library" in self.MW_SRC

    def test_panel_receives_viewport_callback(self):
        assert "get_viewport" in self.MW_SRC

    def test_panel_receives_set_model_callback(self):
        assert "set_model" in self.MW_SRC

    def test_panel_has_scan_button(self):
        assert "Scan Game Library" in self.MW_SRC

    def test_panel_has_export_menu(self):
        assert "Export FBX (KotOR skeleton)" in self.MW_SRC
        assert "Export FBX (Mixamo skeleton)" in self.MW_SRC
        assert "Export FBX (UE5 Mannequin)" in self.MW_SRC

    def test_panel_has_remap_selector(self):
        assert "KotOR Native" in self.MW_SRC
        assert "Mixamo" in self.MW_SRC
        assert "UE5 Mannequin" in self.MW_SRC


# ═══════════════════════════════════════════════════════════════════════
#  10. Math helpers
# ═══════════════════════════════════════════════════════════════════════

class TestMathHelpers:

    def test_quat_to_euler_identity(self):
        from src.core.animation_library import _quat_to_euler_xyz
        rx, ry, rz = _quat_to_euler_xyz(0.0, 0.0, 0.0, 1.0)
        assert abs(rx) < 0.001
        assert abs(ry) < 0.001
        assert abs(rz) < 0.001

    def test_quat_to_euler_90_z(self):
        from src.core.animation_library import _quat_to_euler_xyz
        # 90° around Z: quat = (0, 0, sin45, cos45)
        s = math.sqrt(2) / 2
        rx, ry, rz = _quat_to_euler_xyz(0.0, 0.0, s, s)
        assert abs(rz - 90.0) < 1.0

    def test_quat_to_euler_normalization(self):
        """Non-unit quaternion should be normalized."""
        from src.core.animation_library import _quat_to_euler_xyz
        # Scale by 2 — should give same result as unit quat
        rx1, ry1, rz1 = _quat_to_euler_xyz(0.0, 0.0, 0.0, 1.0)
        rx2, ry2, rz2 = _quat_to_euler_xyz(0.0, 0.0, 0.0, 2.0)
        assert abs(rx1 - rx2) < 0.001
        assert abs(ry1 - ry2) < 0.001
        assert abs(rz1 - rz2) < 0.001

    def test_safe_filename(self):
        from src.core.animation_library import _safe_filename
        assert _safe_filename("c_bantha") == "c_bantha"
        assert "/" not in _safe_filename("walk/run")
        assert len(_safe_filename("a" * 200)) <= 64
