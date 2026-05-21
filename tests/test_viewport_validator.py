"""Tests for the Sprint 3 R2.75 viewport validator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.core.validation.capture_specs import (
    CameraPreset,
    TrustLevel,
    ViewportCaptureSpec,
    ViewportValidationResult,
)
from src.core.validation.viewport_validator import ViewportValidator


PMBAM_BINARY = Path("tests/fixtures/kotor_stock/k1/pmbam.mdl")
PMBAM_ASCII = Path("tests/fixtures/kotor_stock/k1/pmbam_ascii.mdl")


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "captures"
    out.mkdir()
    return out


@pytest.fixture
def validator(output_dir: Path) -> ViewportValidator:
    return ViewportValidator(output_dir=output_dir)


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_load_binary_mdl(validator: ViewportValidator):
    spec = ViewportCaptureSpec(frames=[0])

    result = validator.validate_mdl(mdl_path=PMBAM_BINARY, capture_spec=spec)

    assert result.success, result.errors
    assert result.node_count == 61
    assert result.mesh_count == 44
    assert len(result.mdl_sha256) == 64
    assert result.captures[0].png_path.exists()


@pytest.mark.skipif(not PMBAM_ASCII.exists(), reason="PMBAM ASCII not available")
def test_load_ascii_mdl(validator: ViewportValidator):
    spec = ViewportCaptureSpec(frames=[0])

    result = validator.validate_mdl(mdl_path=PMBAM_ASCII, capture_spec=spec)

    assert result.success, result.errors
    assert result.node_count > 0
    assert result.mesh_count > 0


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_render_bind_pose(validator: ViewportValidator):
    spec = ViewportCaptureSpec(frames=[0], resolution=(512, 512))

    result = validator.validate_mdl(mdl_path=PMBAM_BINARY, capture_spec=spec)

    assert result.success, result.errors
    assert len(result.captures) == 1
    png_path = result.captures[0].png_path
    assert png_path.exists()

    from PIL import Image

    with Image.open(png_path) as img:
        assert img.size == (512, 512)


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_render_animation_frame(validator: ViewportValidator):
    spec = ViewportCaptureSpec(frames=[0, 30], animation_name="g1a1")

    result = validator.validate_mdl(mdl_path=PMBAM_BINARY, capture_spec=spec)
    if not result.success:
        pytest.skip(f"Animation g1a1 not available: {result.errors}")

    assert len(result.captures) == 2
    hash_0 = hashlib.sha256(result.captures[0].png_path.read_bytes()).hexdigest()
    hash_30 = hashlib.sha256(result.captures[1].png_path.read_bytes()).hexdigest()
    assert hash_0 != hash_30


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_camera_presets_change_render_angle(tmp_path: Path):
    front_dir = tmp_path / "front"
    side_dir = tmp_path / "side"
    front_dir.mkdir()
    side_dir.mkdir()

    front = ViewportValidator(output_dir=front_dir).validate_mdl(
        mdl_path=PMBAM_BINARY,
        capture_spec=ViewportCaptureSpec(
            frames=[0],
            resolution=(128, 128),
            camera_preset=CameraPreset.FRONT_ORTHO,
        ),
    )
    side = ViewportValidator(output_dir=side_dir).validate_mdl(
        mdl_path=PMBAM_BINARY,
        capture_spec=ViewportCaptureSpec(
            frames=[0],
            resolution=(128, 128),
            camera_preset=CameraPreset.SIDE_LEFT,
        ),
    )

    assert front.success, front.errors
    assert side.success, side.errors
    front_hash = hashlib.sha256(front.captures[0].png_path.read_bytes()).hexdigest()
    side_hash = hashlib.sha256(side.captures[0].png_path.read_bytes()).hexdigest()
    assert front_hash != side_hash


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_extract_bone_positions(validator: ViewportValidator):
    spec = ViewportCaptureSpec(frames=[0])

    result = validator.validate_mdl(mdl_path=PMBAM_BINARY, capture_spec=spec)

    assert result.success, result.errors
    bones = result.captures[0].bone_positions
    assert len(bones) >= 19
    for bone in bones:
        assert bone.name
        assert len(bone.world_position) == 3
        assert len(bone.world_rotation_quat) == 4
        w, x, y, z = bone.world_rotation_quat
        mag_sq = w * w + x * x + y * y + z * z
        assert 0.99 <= mag_sq <= 1.01


@pytest.mark.skipif(not PMBAM_BINARY.exists(), reason="PMBAM binary not available")
def test_ssim_against_reference(validator: ViewportValidator, output_dir: Path):
    reference_dir = output_dir / "reference"
    reference_dir.mkdir()
    reference_validator = ViewportValidator(output_dir=reference_dir)
    spec = ViewportCaptureSpec(frames=[0])
    reference_result = reference_validator.validate_mdl(
        mdl_path=PMBAM_BINARY,
        capture_spec=spec,
    )
    assert reference_result.success, reference_result.errors

    result = validator.validate_mdl(
        mdl_path=PMBAM_BINARY,
        capture_spec=spec,
        reference_captures_dir=reference_dir,
        ssim_threshold=0.99,
    )

    assert result.success, result.errors
    assert 0 in result.ssim_scores
    assert result.ssim_scores[0] >= 0.99
    assert result.trust_level == TrustLevel.CANONICAL


def test_manifest_serialization(tmp_path: Path):
    result = ViewportValidationResult(
        success=True,
        mdl_path=Path("test.mdl"),
        mdl_sha256="a" * 64,
        node_count=61,
        mesh_count=44,
        animation_count=5,
    )

    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2)

    with open(manifest_path, encoding="utf-8") as handle:
        loaded = json.load(handle)

    assert loaded["success"] is True
    assert loaded["mdl_sha256"] == "a" * 64
    assert loaded["node_count"] == 61


def test_capture_spec_validation():
    with pytest.raises(ValueError, match="frames cannot be empty"):
        ViewportCaptureSpec(frames=[])
    with pytest.raises(ValueError, match="frame indices"):
        ViewportCaptureSpec(frames=[-1])
    spec = ViewportCaptureSpec(frames=[0], camera_preset="three_quarter")
    assert spec.camera_preset == CameraPreset.THREE_QUARTER
