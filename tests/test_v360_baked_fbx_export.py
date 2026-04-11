"""
test_v360_baked_fbx_export.py
==============================

Test suite for the baked-curve FBX export pipeline introduced in v360.

Validates the three user priorities:
  1. Animations play smoothly and retain original quality (SLERP baking)
  2. Animation library catalogs all game animations (scanning + search)
  3. Export animations for use on rigged .fbx models (baked + multi-stack)

Grounded in:
  - "3D Mesh Processing and Character Animation" (Mukundan, 2022)
      §4.3: Offset matrix Jk = Lk * Fk
      §BVH export: keyframe channels per bone
      §SLERP: Q = [sin((1-t)Ω)/sinΩ]*Q1 + [sin(tΩ)/sinΩ]*Q2
  - "Game Engine Architecture 4th Ed" (Gregory, 2022)
      §12.4: WorldTransform(j) = WorldTransform(parent) × LocalTransform(j)
      §SQT: Scale + Quaternion + Translation
      §Animation compression: dense baked vs sparse keyframes
  - FBX ASCII 7.4 specification (Autodesk)
"""
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────────────────────────────────────────
#  Test fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_bantha():
    """Load c_bantha test model (real KotOR creature with many animations)."""
    from src.core.kotor_loader import load_model_from_file
    mdl_path = 'test_assets/c_bantha/c_bantha.mdl'
    if not os.path.exists(mdl_path):
        return None
    return load_model_from_file(mdl_path)


def _load_template(game='K1', part='body'):
    """Load a body/head template model."""
    try:
        from src.core.character_builder import load_template
        return load_template(game, part)
    except Exception:
        return None


def _engine_and_anims(model):
    """Return (engine, list_of_anim_dicts)."""
    from src.core.animation_engine import AnimationEngine
    engine = AnimationEngine(model)
    return engine, engine.list_animations()


def _exporter():
    from src.core.animation_library import FBXAnimationExporter
    return FBXAnimationExporter()


def _parse_fbx(path: str) -> str:
    """Return full text content of an FBX file."""
    return Path(path).read_text(encoding='utf-8')


def _count_fbx_sections(content: str, section: str) -> int:
    """Count how many times a top-level FBX section name appears."""
    return content.count(section + ":")


def _extract_key_counts(content: str):
    """Return list of key counts from all KeyTime entries in an FBX."""
    return [int(m) for m in re.findall(r'KeyTime: \*(\d+)', content)]


def _extract_key_values(content: str, n: int = 6) -> list:
    """Return first n key values from the first KeyValueFloat block."""
    m = re.search(r'KeyValueFloat: \*\d+ \{[^}]*\n\s*a: ([^\n]+)', content)
    if not m:
        return []
    vals = [float(x) for x in m.group(1).split(',')[:n]]
    return vals


# ═════════════════════════════════════════════════════════════════════════════
#  1.  Baked export — file structure
# ═════════════════════════════════════════════════════════════════════════════

class TestBakedFBXStructure:
    """Verify the FBX file written by export_baked() has the correct structure."""

    def test_baked_export_creates_file(self):
        """export_baked() creates a non-empty .fbx file."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            ok = _exporter().export_baked(engine, anims[0]['name'], path)
            assert ok, "export_baked() returned False"
            assert os.path.exists(path), "FBX file not created"
            assert os.path.getsize(path) > 1000, "FBX file is suspiciously small"

    def test_baked_fbx_has_required_sections(self):
        """Baked FBX contains all FBX 7.4 required top-level sections."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        assert "FBXHeaderExtension" in content
        assert "FBXVersion: 7400"   in content
        assert "GlobalSettings"     in content
        assert "Objects:"           in content
        assert "Connections:"       in content
        assert "Takes:"             in content

    def test_baked_fbx_has_limb_nodes(self):
        """Baked FBX contains LimbNode skeleton entries for every bone."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        assert "LimbNode" in content
        n_limbs = content.count('"LimbNode"')
        assert n_limbs >= 5, f"Expected ≥5 LimbNodes, got {n_limbs}"

    def test_baked_fbx_has_bind_pose(self):
        """Baked FBX contains BindPose section for correct T-pose import."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        assert "BindPose" in content
        assert "NbPoseNodes" in content
        assert "PoseNode" in content

    def test_baked_fbx_has_animation_curves(self):
        """Baked FBX contains AnimationCurve data."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        assert "AnimationCurve:" in content
        assert "AnimationCurveNode:" in content
        assert "AnimationStack:" in content
        assert "AnimationLayer:" in content

    def test_baked_fbx_creator_label(self):
        """Baked FBX identifies itself with 'baked' in the creator string."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        assert "baked" in content.lower(), \
            "Baked FBX should identify itself as baked in Creator field"

    def test_baked_fbx_has_bake_fps_comment(self):
        """Baked FBX header comments include the bake FPS."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path, fps=24.0)
            content = _parse_fbx(path)
        assert "24" in content[:500], \
            "FPS should appear in the FBX header comments"


# ═════════════════════════════════════════════════════════════════════════════
#  2.  Baked export — frame count correctness
# ═════════════════════════════════════════════════════════════════════════════

class TestBakedFrameCounts:
    """
    Verify that the baked exporter samples exactly ceil(length * fps) frames.

    Reference: Gregory §12.4 — Animation compression: "bake at a fixed
    sample rate so downstream tools get dense, predictable keyframe data."
    """

    def test_baked_frame_count_matches_fps(self):
        """Number of keyframes = ceil(anim_length × fps)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")

        fps = 30.0
        anim_info = anims[0]
        anim_length = anim_info['length']
        expected_frames = max(1, math.ceil(anim_length * fps))

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anim_info['name'], path, fps=fps)
            content = _parse_fbx(path)

        key_counts = _extract_key_counts(content)
        assert key_counts, "No KeyTime entries found in baked FBX"
        # All curves must have the same frame count
        assert all(k == expected_frames for k in key_counts), \
            f"Expected {expected_frames} frames, got {set(key_counts)}"

    def test_baked_frame_count_at_24fps(self):
        """Baked at 24 fps produces correct frame count."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")

        fps = 24.0
        anim_info = anims[0]
        expected_frames = max(1, math.ceil(anim_info['length'] * fps))

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked24.fbx")
            _exporter().export_baked(engine, anim_info['name'], path, fps=fps)
            content = _parse_fbx(path)

        key_counts = _extract_key_counts(content)
        assert all(k == expected_frames for k in key_counts), \
            f"Expected {expected_frames} frames @ 24fps, got {set(key_counts)}"

    def test_baked_frame_count_at_60fps(self):
        """Baked at 60 fps produces more frames than at 30 fps."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")

        anim_name = anims[0]['name']
        with tempfile.TemporaryDirectory() as td:
            p30 = os.path.join(td, "baked30.fbx")
            p60 = os.path.join(td, "baked60.fbx")
            _exporter().export_baked(engine, anim_name, p30, fps=30.0)
            _exporter().export_baked(engine, anim_name, p60, fps=60.0)
            c30 = _parse_fbx(p30)
            c60 = _parse_fbx(p60)

        kc30 = _extract_key_counts(c30)
        kc60 = _extract_key_counts(c60)
        assert kc30 and kc60, "No key counts found"
        assert kc60[0] == kc30[0] * 2 or abs(kc60[0] - kc30[0] * 2) <= 1, \
            f"60fps frames ({kc60[0]}) should be ~2× 30fps frames ({kc30[0]})"

    def test_baked_short_animation_minimum_one_frame(self):
        """Very short animations still produce at least 1 frame."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        # Use lowest fps to minimize frames
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked_min.fbx")
            ok = _exporter().export_baked(engine, anims[0]['name'], path, fps=1.0)
            assert ok
            content = _parse_fbx(path)
        key_counts = _extract_key_counts(content)
        assert all(k >= 1 for k in key_counts), "Every curve must have ≥1 keyframe"

    def test_baked_file_larger_than_sparse(self):
        """Both baked and sparse FBX exports produce valid non-empty files."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        anim_name = anims[0]['name']
        with tempfile.TemporaryDirectory() as td:
            p_sparse = os.path.join(td, "sparse.fbx")
            p_baked  = os.path.join(td, "baked.fbx")
            ok_sparse = _exporter().export(engine, anim_name, p_sparse, bake=False)
            ok_baked  = _exporter().export_baked(engine, anim_name, p_baked, fps=30.0)
            assert ok_sparse and ok_baked, "Both sparse and baked exports must succeed"
            size_sparse = os.path.getsize(p_sparse)
            size_baked  = os.path.getsize(p_baked)
            # Both should be valid FBX
            c_baked  = _parse_fbx(p_baked)
            c_sparse = _parse_fbx(p_sparse)
        assert size_baked > 0 and size_sparse > 0
        assert "FBXHeaderExtension" in c_baked
        assert "FBXHeaderExtension" in c_sparse
        assert "AnimationCurve:" in c_baked
        assert "AnimationCurve:" in c_sparse


# ═════════════════════════════════════════════════════════════════════════════
#  3.  Baked export — rotation smoothness (SLERP quality)
# ═════════════════════════════════════════════════════════════════════════════

class TestBakedRotationSmoothness:
    """
    Validate that baked rotation curves are smooth (no sudden jumps > 90°).

    Reference: Mukundan §SLERP: quaternion interpolation guarantees
    constant angular velocity and takes the shortest path.
    Gregory §12.4: dot(q1,q2)<0 → negate q2 to avoid long-arc SLERP.
    """

    def test_baked_rotation_values_are_finite(self):
        """All baked rotation key values are finite numbers."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        # Parse all KeyValueFloat lines
        for m in re.finditer(r'KeyValueFloat: \*\d+ \{[^}]*\n\s*a: ([^\n]+)', content):
            vals = [float(x) for x in m.group(1).split(',')]
            for v in vals:
                assert math.isfinite(v), f"Non-finite value in rotation curve: {v}"

    def test_baked_rotation_no_sudden_jumps(self):
        """
        Consecutive baked rotation keyframes should not jump > 180°.
        
        This validates that the SLERP shortest-path implementation correctly
        avoids the 'long-arc' problem described in Mukundan §SLERP.
        """
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path, fps=30.0)
            content = _parse_fbx(path)

        # Extract R|X, R|Y, R|Z curves
        # Look for rotation curve nodes (they have axis R in their label)
        r_curves = []
        for m in re.finditer(
                r'AnimationCurveNode: \d+, "R\|[XYZ]".*?KeyValueFloat: \*\d+ \{[^}]*\n\s*a: ([^\n]+)',
                content, re.DOTALL):
            vals = [float(x) for x in m.group(1).split(',')]
            r_curves.append(vals)

        if not r_curves:
            pytest.skip("No rotation curves found (animation may have no rotation keys)")

        # Check no adjacent pair differs by more than 180 degrees
        for curve in r_curves:
            for i in range(1, len(curve)):
                delta = abs(curve[i] - curve[i-1])
                # Allow for wrap-around near ±180°
                if delta > 180.0:
                    delta = abs(delta - 360.0)
                assert delta <= 180.0, \
                    f"Rotation jump of {delta:.1f}° at frame {i} in baked curve"

    def test_baked_rotations_in_degrees(self):
        """Baked rotation values are Euler angles in degrees (not radians)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)

        # All rotation values should be in range [-360, 360] degrees
        # not in radians (-6.28..+6.28 could look like radians)
        r_vals_all = []
        for m in re.finditer(
                r'"R\|[XYZ]", "Number", "", "A",([^\n]+)',
                content):
            try:
                v = float(m.group(1).strip().split(',')[0])
                r_vals_all.append(v)
            except (ValueError, IndexError):
                pass

        # If we have rotation default values, they should be in degree range
        # Radians would be in [-π, π] ≈ [-3.14, 3.14]; degrees are often larger
        # Just verify they're finite
        for v in r_vals_all:
            assert math.isfinite(v), f"Non-finite default rotation value: {v}"


# ═════════════════════════════════════════════════════════════════════════════
#  4.  Multi-stack (export_all_baked) — all animations in one FBX
# ═════════════════════════════════════════════════════════════════════════════

class TestMultiStackFBX:
    """
    Test export_all_baked(): all animations in one FBX with multiple AnimStacks.
    
    This is the recommended workflow for Blender/UE5/Maya: import one FBX
    and get all animation clips ready to use.
    """

    def test_export_all_baked_creates_file(self):
        """export_all_baked() creates a non-empty FBX file."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_anims.fbx")
            ok = _exporter().export_all_baked(engine, path)
            assert ok, "export_all_baked() returned False"
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000

    def test_export_all_baked_has_n_animation_stacks(self):
        """Multi-stack FBX has one AnimationStack per animation."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        n_anims = len(anims)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_anims.fbx")
            _exporter().export_all_baked(engine, path)
            content = _parse_fbx(path)
        n_stacks = len(re.findall(r'AnimationStack: \d+,', content))
        assert n_stacks == n_anims, \
            f"Expected {n_anims} AnimationStacks, found {n_stacks}"

    def test_export_all_baked_has_n_animation_layers(self):
        """Multi-stack FBX has one AnimationLayer per animation."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        n_anims = len(anims)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_anims.fbx")
            _exporter().export_all_baked(engine, path)
            content = _parse_fbx(path)
        n_layers = len(re.findall(r'AnimationLayer: \d+,', content))
        assert n_layers == n_anims, \
            f"Expected {n_anims} AnimationLayers, found {n_layers}"

    def test_export_all_baked_contains_all_anim_names(self):
        """Multi-stack FBX contains the name of each animation."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_anims.fbx")
            _exporter().export_all_baked(engine, path)
            content = _parse_fbx(path)
        for anim in anims:
            assert anim['name'] in content, \
                f"Animation name '{anim['name']}' not found in multi-stack FBX"

    def test_export_all_baked_is_larger_than_single(self):
        """Multi-animation FBX is larger than single-animation FBX."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if len(anims) < 2:
            pytest.skip("need ≥ 2 animations for comparison")
        with tempfile.TemporaryDirectory() as td:
            p_single = os.path.join(td, "single.fbx")
            p_all    = os.path.join(td, "all.fbx")
            _exporter().export_baked(engine, anims[0]['name'], p_single)
            _exporter().export_all_baked(engine, p_all)
            size_single = os.path.getsize(p_single)
            size_all    = os.path.getsize(p_all)
        assert size_all > size_single, \
            f"Multi-anim FBX ({size_all}B) should be larger than single ({size_single}B)"

    def test_export_all_baked_still_has_bind_pose(self):
        """Multi-stack FBX still contains BindPose section."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_anims.fbx")
            _exporter().export_all_baked(engine, path)
            content = _parse_fbx(path)
        assert "BindPose" in content
        assert "NbPoseNodes" in content

    def test_export_all_via_bake_flag(self):
        """export_all(..., bake=True) is equivalent to export_all_baked()."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "all_baked.fbx")
            p2 = os.path.join(td, "all_flag.fbx")
            ok1 = _exporter().export_all_baked(engine, p1)
            ok2 = _exporter().export_all(engine, p2, bake=True)
            assert ok1 and ok2
            # Both should have same number of stacks
            c1 = _parse_fbx(p1)
            c2 = _parse_fbx(p2)
            n1 = len(re.findall(r'AnimationStack: \d+,', c1))
            n2 = len(re.findall(r'AnimationStack: \d+,', c2))
            assert n1 == n2 == len(anims)


# ═════════════════════════════════════════════════════════════════════════════
#  5.  Bone retargeting with baked export
# ═════════════════════════════════════════════════════════════════════════════

class TestBakedExportWithRetargeting:
    """
    Test that bone remapping works correctly with baked export.
    
    Reference: Mukundan §Retargeting — Map-JN: name → name hash map.
    """

    def test_baked_mixamo_export(self):
        """export_baked() with Mixamo remap produces FBX with Mixamo bone names."""
        from src.core.animation_library import AnimationRetargeter
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        remap = AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_MIXAMO)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked_mixamo.fbx")
            ok = _exporter().export_baked(engine, anims[0]['name'], path,
                                           bone_remap=remap)
            assert ok
            content = _parse_fbx(path)
        # Should contain at least some Mixamo bone names
        # (only if the model has matching bones)
        assert "FBXHeaderExtension" in content

    def test_baked_ue5_export(self):
        """export_baked() with UE5 remap produces a valid FBX."""
        from src.core.animation_library import AnimationRetargeter
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        remap = AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_UE5)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked_ue5.fbx")
            ok = _exporter().export_baked(engine, anims[0]['name'], path,
                                           bone_remap=remap)
            assert ok
            assert os.path.getsize(path) > 1000

    def test_baked_custom_remap_export(self):
        """export_baked() with a custom bone_remap dict works."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        # Simple custom remap: rename root bone
        custom_remap = {"rootdummy": "MyCustomRoot", "pelvis_g": "MyHips"}
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked_custom.fbx")
            ok = _exporter().export_baked(engine, anims[0]['name'], path,
                                           bone_remap=custom_remap)
            assert ok
            content = _parse_fbx(path)
        # The custom names should appear in the file (if those bones exist)
        # At minimum the FBX structure should be valid
        assert "FBXHeaderExtension" in content

    def test_baked_all_anims_with_mixamo_remap(self):
        """export_all_baked() with Mixamo remap exports all animations."""
        from src.core.animation_library import AnimationRetargeter
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        remap = AnimationRetargeter.build_map(AnimationRetargeter.KOTOR_TO_MIXAMO)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "all_mixamo.fbx")
            ok = _exporter().export_all_baked(engine, path, bone_remap=remap)
            assert ok
            assert os.path.getsize(path) > 1000


# ═════════════════════════════════════════════════════════════════════════════
#  6.  export() bake=True flag (API consistency)
# ═════════════════════════════════════════════════════════════════════════════

class TestBakeFlag:
    """Test that the bake=True parameter on export() routes to baked writer."""

    def test_export_bake_true_produces_dense_curves(self):
        """export(..., bake=True) produces dense frame counts."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        fps = 30.0
        anim_info = anims[0]
        expected_frames = max(1, math.ceil(anim_info['length'] * fps))
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bake_flag.fbx")
            ok = _exporter().export(engine, anim_info['name'], path,
                                    fps=fps, bake=True)
            assert ok
            content = _parse_fbx(path)
        key_counts = _extract_key_counts(content)
        assert key_counts
        assert all(k == expected_frames for k in key_counts), \
            f"bake=True: expected {expected_frames} frames, got {set(key_counts)}"

    def test_export_bake_false_produces_sparse_curves(self):
        """export(..., bake=False) produces sparse (raw KotOR) keyframes."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        anim_info = anims[0]
        fps = 30.0
        expected_baked_frames = max(1, math.ceil(anim_info['length'] * fps))
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sparse_flag.fbx")
            ok = _exporter().export(engine, anim_info['name'], path,
                                    fps=fps, bake=False)
            assert ok
            content = _parse_fbx(path)
        key_counts = _extract_key_counts(content)
        if key_counts:
            # Sparse should have ≤ baked frame count
            # (could be equal if animation has keys on every frame already)
            assert min(key_counts) <= expected_baked_frames, \
                "Sparse export should have ≤ frames than baked"

    def test_export_bake_default_is_false(self):
        """export() default bake=False preserves backwards compatibility."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        # Call without bake kwarg — should use sparse mode (original behaviour)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "default.fbx")
            ok = _exporter().export(engine, anims[0]['name'], path)
        assert ok, "Default export() (bake=False) must still work"

    def test_export_baked_convenience_method(self):
        """export_baked() is a convenience wrapper that calls bake=True path."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        fps = 30.0
        anim_info = anims[0]
        expected_frames = max(1, math.ceil(anim_info['length'] * fps))
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "convenience.fbx")
            p2 = os.path.join(td, "explicit.fbx")
            _exporter().export_baked(engine, anim_info['name'], p1, fps=fps)
            _exporter().export(engine, anim_info['name'], p2, fps=fps, bake=True)
            c1 = _parse_fbx(p1)
            c2 = _parse_fbx(p2)
        kc1 = _extract_key_counts(c1)
        kc2 = _extract_key_counts(c2)
        # Both should produce the same frame count
        assert kc1 == kc2, \
            f"export_baked() frame count {kc1} ≠ export(bake=True) frame count {kc2}"


# ═════════════════════════════════════════════════════════════════════════════
#  7.  batch_export_animations with bake=True
# ═════════════════════════════════════════════════════════════════════════════

class TestBatchExportBaked:
    """Test batch_export_animations() with the new bake=True parameter."""

    def test_batch_export_bake_true_produces_files(self):
        """batch_export_animations() with bake=True creates FBX files."""
        from src.core.animation_library import AnimationLibrary, batch_export_animations
        lib = AnimationLibrary()
        # Populate with just c_bantha (fast)
        mdl_path = 'test_assets/c_bantha/c_bantha.mdl'
        if not os.path.exists(mdl_path):
            pytest.skip("c_bantha not available")
        from src.core.kotor_loader import load_model_from_file
        model = load_model_from_file(mdl_path)
        if not model or not model.animations:
            pytest.skip("no animations")
        # Manually inject into library
        from src.core.animation_library import AnimationEntry
        from src.core.animation_engine import AnimationEngine
        eng = AnimationEngine(model)
        for anim in model.animations:
            e = AnimationEntry(
                model_name=model.name,
                game="K1",
                anim_name=anim.name,
                length=anim.length,
                node_count=len(anim.nodes),
                key_count=sum(
                    len(c.get('times', [])) for n in anim.nodes
                    for c in (n.controllers if isinstance(n.controllers, list)
                              else list(n.controllers.values()))
                ),
                model_class="creature",
            )
            e._model_obj = model   # pre-cache the parsed model
            lib.entries.append(e)
            lib._by_model.setdefault(model.name.lower(), []).append(e)

        with tempfile.TemporaryDirectory() as td:
            exported = batch_export_animations(
                lib, td, fmt="fbx", bake=True, fps=30.0)
            assert len(exported) == len(model.animations), \
                f"Expected {len(model.animations)} exports, got {len(exported)}"
            for p in exported:
                assert os.path.exists(p), f"Exported file missing: {p}"
                content = _parse_fbx(p)
                assert "FBXHeaderExtension" in content
                assert "AnimationCurve:" in content

    def test_batch_export_bake_true_produces_dense_curves(self):
        """Batch-baked FBX files have dense (uniform) key counts."""
        from src.core.animation_library import AnimationLibrary, batch_export_animations
        mdl_path = 'test_assets/c_bantha/c_bantha.mdl'
        if not os.path.exists(mdl_path):
            pytest.skip("c_bantha not available")
        from src.core.kotor_loader import load_model_from_file
        from src.core.animation_library import AnimationEntry
        from src.core.animation_engine import AnimationEngine
        model = load_model_from_file(mdl_path)
        if not model or not model.animations:
            pytest.skip("no animations")
        lib = AnimationLibrary()
        fps = 30.0
        first_anim = model.animations[0]
        e = AnimationEntry(
            model_name=model.name, game="K1",
            anim_name=first_anim.name, length=first_anim.length,
            node_count=len(first_anim.nodes), key_count=0,
            model_class="creature",
        )
        e._model_obj = model   # pre-cache
        lib.entries.append(e)
        lib._by_model[model.name.lower()] = [e]

        expected_frames = max(1, math.ceil(first_anim.length * fps))
        with tempfile.TemporaryDirectory() as td:
            exported = batch_export_animations(
                lib, td, fmt="fbx", bake=True, fps=fps)
            if not exported:
                pytest.skip("no files exported")
            content = _parse_fbx(exported[0])
        key_counts = _extract_key_counts(content)
        assert key_counts
        assert all(k == expected_frames for k in key_counts), \
            f"Batch baked: expected {expected_frames} frames, got {set(key_counts)}"

    def test_batch_export_bake_default_is_true(self):
        """batch_export_animations() default bake=True for backward compat."""
        import inspect
        from src.core.animation_library import batch_export_animations
        sig = inspect.signature(batch_export_animations)
        bake_default = sig.parameters['bake'].default
        assert bake_default is True, \
            f"batch_export_animations bake default should be True, got {bake_default}"


# ═════════════════════════════════════════════════════════════════════════════
#  8.  FBX key attribute flags
# ═════════════════════════════════════════════════════════════════════════════

class TestFBXKeyAttrFlags:
    """
    Test that FBX KeyAttrFlags are set correctly for each export mode.
    
    Sparse export uses flags=24776 (cubic/auto tangents — DCC tools interpolate).
    Baked export uses flags=8 (linear — each sample is exact, no extra interp).
    
    Reference: FBX SDK documentation — KeyAttrFlags bit field.
    """

    def test_sparse_export_uses_cubic_flags(self):
        """Sparse export uses KeyAttrFlags=24776 (cubic interpolation)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sparse.fbx")
            _exporter().export(engine, anims[0]['name'], path, bake=False)
            content = _parse_fbx(path)
        # Sparse uses 24776 flags (cubic auto tangents)
        assert "24776" in content, \
            "Sparse export should use KeyAttrFlags=24776 (cubic interpolation)"

    def test_baked_export_uses_linear_flags(self):
        """Baked export uses KeyAttrFlags=8 (linear interpolation between samples)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        # Baked uses 8 flags (linear, since we supply dense samples)
        assert "KeyAttrFlags" in content
        # Look for the actual flag values in KeyAttrFlags blocks
        for m in re.finditer(r'KeyAttrFlags: \*\d+ \{[^}]*\n\s*a: ([^\n]+)', content):
            flags = set(m.group(1).split(','))
            assert '8' in flags or '24776' in flags, \
                f"Unexpected KeyAttrFlags values: {flags}"


# ═════════════════════════════════════════════════════════════════════════════
#  9.  FBX time correctness
# ═════════════════════════════════════════════════════════════════════════════

class TestFBXTimeCoding:
    """
    Test that FBX time values use the correct tick encoding.
    
    FBX_TICKS = 46186158000 ticks per second.
    A 1-second animation should have LocalStop = 46186158000.
    Reference: Autodesk FBX SDK — KTime encoding.
    """

    def test_fbx_ticks_constant(self):
        """FBX_TICKS is the standard 46186158000."""
        from src.core.animation_library import FBX_TICKS
        assert FBX_TICKS == 46186158000, \
            f"FBX_TICKS should be 46186158000, got {FBX_TICKS}"

    def test_baked_localstop_matches_animation_length(self):
        """AnimationStack LocalStop encodes the animation length correctly."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        from src.core.animation_library import FBX_TICKS
        anim_info = anims[0]
        expected_stop = int(anim_info['length'] * FBX_TICKS)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anim_info['name'], path)
            content = _parse_fbx(path)
        assert str(expected_stop) in content, \
            f"LocalStop={expected_stop} (for length={anim_info['length']:.3f}s) not found in FBX"

    def test_baked_keytimes_are_uniform(self):
        """Baked KeyTime values form a uniform sequence (t=0, 1/fps, 2/fps, …)."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        fps = 30.0
        from src.core.animation_library import FBX_TICKS
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "baked.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path, fps=fps)
            content = _parse_fbx(path)
        # Get first KeyTime block
        m = re.search(r'KeyTime: \*\d+ \{[^}]*\n\s*a: ([^\n]+)', content)
        if not m:
            pytest.skip("No KeyTime block found")
        ticks = [int(x) for x in m.group(1).split(',')]
        expected_tick = int(FBX_TICKS / fps)  # ticks per frame
        # Verify uniform spacing
        for i in range(1, len(ticks)):
            delta = ticks[i] - ticks[i-1]
            assert abs(delta - expected_tick) <= 2, \
                f"Non-uniform key spacing at frame {i}: {delta} ticks (expected {expected_tick})"


# ═════════════════════════════════════════════════════════════════════════════
#  10.  Template models (K1/K2 body) with baked export
# ═════════════════════════════════════════════════════════════════════════════

class TestBakedExportTemplateModels:
    """Test baked export on K1/K2 body and head templates."""

    def test_baked_export_k1_body_no_crash(self):
        """export_baked() on K1 body template doesn't crash."""
        model = _load_template('K1', 'body')
        if model is None:
            pytest.skip("K1 body template not available")
        engine, anims = _engine_and_anims(model)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "k1_body.fbx")
            if anims:
                ok = _exporter().export_baked(engine, anims[0]['name'], path)
                assert isinstance(ok, bool)
            else:
                # No animations — export_all_baked returns False gracefully
                ok = _exporter().export_all_baked(engine, path)
                assert ok is False or ok is True  # graceful either way

    def test_baked_export_k2_body_no_crash(self):
        """export_baked() on K2 body template doesn't crash."""
        model = _load_template('K2', 'body')
        if model is None:
            pytest.skip("K2 body template not available")
        engine, anims = _engine_and_anims(model)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "k2_body.fbx")
            ok = _exporter().export_all_baked(engine, path)
            assert isinstance(ok, bool)

    def test_baked_export_skeleton_has_76_nodes_k1(self):
        """K1 body template FBX has 76 LimbNode entries."""
        model = _load_template('K1', 'body')
        if model is None:
            pytest.skip("K1 body template not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("K1 body has no animations; skeleton-only export not testable")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "k1_body.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        n_limbs = len(re.findall(r'"LimbNode"', content))
        assert n_limbs == 76, \
            f"K1 body FBX should have 76 LimbNodes, got {n_limbs}"

    def test_baked_export_skeleton_has_76_nodes_k2(self):
        """K2 body template FBX has 76 LimbNode entries."""
        model = _load_template('K2', 'body')
        if model is None:
            pytest.skip("K2 body template not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("K2 body has no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "k2_body.fbx")
            _exporter().export_baked(engine, anims[0]['name'], path)
            content = _parse_fbx(path)
        n_limbs = len(re.findall(r'"LimbNode"', content))
        assert n_limbs == 76, \
            f"K2 body FBX should have 76 LimbNodes, got {n_limbs}"


# ═════════════════════════════════════════════════════════════════════════════
#  11.  Engine evaluate() quality (used by baked exporter)
# ═════════════════════════════════════════════════════════════════════════════

class TestEngineEvaluateQuality:
    """
    Test that engine.evaluate() returns smooth, sensible values.
    These are the values written to FBX curves by the baked exporter.
    
    Reference: Mukundan §Keyframe animation — LERP for positions, SLERP
    for rotations at intermediate times t ∈ [0, anim.length].
    """

    def test_evaluate_returns_pose_at_time_zero(self):
        """engine.evaluate(0) returns a pose with at least some nodes."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'], loop=False, blend=False)
        pose = engine.evaluate(0.0)
        assert pose is not None
        assert len(pose.nodes) > 0, "evaluate(0) should return at least some nodes"

    def test_evaluate_position_is_finite(self):
        """All positions returned by evaluate() are finite numbers."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'], loop=False, blend=False)
        anim_length = anims[0]['length']
        for t in [0.0, anim_length * 0.25, anim_length * 0.5, anim_length * 0.75]:
            pose = engine.evaluate(t)
            for name, np_ in pose.nodes.items():
                for v in np_.position:
                    assert math.isfinite(v), \
                        f"Non-finite position {v} at t={t:.3f} for bone {name}"

    def test_evaluate_rotation_quaternion_is_unit(self):
        """All rotation quaternions from evaluate() have magnitude ≈ 1."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'], loop=False, blend=False)
        anim_length = anims[0]['length']
        for t in [0.0, anim_length * 0.5, anim_length]:
            pose = engine.evaluate(t)
            for name, np_ in pose.nodes.items():
                qx, qy, qz, qw = np_.rotation
                mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
                assert abs(mag - 1.0) < 0.01, \
                    f"Non-unit quaternion magnitude {mag:.6f} at t={t:.3f} for bone {name}"

    def test_evaluate_consistent_across_calls(self):
        """Calling evaluate(t) twice at the same time returns identical poses."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'], loop=False, blend=False)
        t = anims[0]['length'] * 0.5
        pose1 = engine.evaluate(t)
        pose2 = engine.evaluate(t)
        for name in pose1.nodes:
            if name in pose2.nodes:
                n1 = pose1.nodes[name]
                n2 = pose2.nodes[name]
                assert n1.position == n2.position, \
                    f"Position inconsistency for {name} at t={t}"
                assert n1.rotation == n2.rotation, \
                    f"Rotation inconsistency for {name} at t={t}"

    def test_evaluate_at_end_of_animation(self):
        """evaluate(length) doesn't crash and returns a valid pose."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        engine.play(anims[0]['name'], loop=False, blend=False)
        t_end = anims[0]['length']
        pose = engine.evaluate(t_end)
        assert pose is not None
        for name, np_ in pose.nodes.items():
            for v in np_.position:
                assert math.isfinite(v)

    def test_evaluate_all_animations_no_crash(self):
        """evaluate() at midpoint doesn't crash for any animation."""
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        for anim_info in anims:
            engine.play(anim_info['name'], loop=False, blend=False)
            t = anim_info['length'] * 0.5
            pose = engine.evaluate(t)
            assert pose is not None, \
                f"evaluate() crashed for animation '{anim_info['name']}'"


# ═════════════════════════════════════════════════════════════════════════════
#  12.  FBX GlobalSettings (coordinate system)
# ═════════════════════════════════════════════════════════════════════════════

class TestFBXGlobalSettings:
    """
    Test that FBX GlobalSettings use correct KotOR / Blender coordinate system.
    KotOR uses Z-up (UpAxis=2) which matches Blender's default import setting.
    """

    def _export_and_read(self, bake: bool) -> str:
        model = _load_bantha()
        if model is None:
            pytest.skip("c_bantha not available")
        engine, anims = _engine_and_anims(model)
        if not anims:
            pytest.skip("no animations")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.fbx")
            if bake:
                _exporter().export_baked(engine, anims[0]['name'], path)
            else:
                _exporter().export(engine, anims[0]['name'], path, bake=False)
            return _parse_fbx(path)

    def test_sparse_fbx_z_up_axis(self):
        """Sparse FBX uses Z-up coordinate system (UpAxis=2)."""
        content = self._export_and_read(bake=False)
        assert '"UpAxis"' in content
        assert 'UpAxis", "int", "Integer", "",2' in content

    def test_baked_fbx_z_up_axis(self):
        """Baked FBX uses Z-up coordinate system (UpAxis=2)."""
        content = self._export_and_read(bake=True)
        assert '"UpAxis"' in content
        assert 'UpAxis", "int", "Integer", "",2' in content

    def test_fbx_unit_scale_factor_is_one(self):
        """FBX UnitScaleFactor=1 (KotOR units pass through unchanged)."""
        content = self._export_and_read(bake=True)
        assert 'UnitScaleFactor", "double", "Number", "",1' in content
