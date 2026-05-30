"""Ghost Rigger viewport validation harness.

This module wraps the same model loading and headless rendering primitives used by
the Qt viewport. It is the canonical visual gate for final MDL outputs; Blender
remains an authoring-integrity gate for FBX intermediates.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.validation.capture_specs import (
    BonePosition,
    CameraPreset,
    FrameCapture,
    TrustLevel,
    ViewportCaptureSpec,
    ViewportValidationResult,
)

logger = logging.getLogger(__name__)


_CAMERA_ANGLES: Dict[CameraPreset, Tuple[float, float]] = {
    CameraPreset.FRONT_ORTHO: (90.0, 8.0),
    CameraPreset.THREE_QUARTER: (45.0, 18.0),
    CameraPreset.SIDE_LEFT: (180.0, 8.0),
    CameraPreset.SIDE_RIGHT: (0.0, 8.0),
    CameraPreset.TOP_DOWN: (90.0, 82.0),
    CameraPreset.BACK: (270.0, 8.0),
}


class ViewportValidator:
    """Programmatic interface to Ghost Rigger viewport validation."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._renderer = None
        self._animation_engine = None

    def _compute_sha256(self, mdl_path: Path) -> str:
        """Compute SHA-256 for provenance."""

        sha = hashlib.sha256()
        with open(mdl_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _looks_like_ascii_mdl(raw: bytes) -> bool:
        first16 = raw[:16]
        printable_count = sum(
            1
            for byte in first16
            if 0x20 <= byte <= 0x7E or byte in (0x09, 0x0A, 0x0D)
        )
        return (
            printable_count >= 10
            or raw[:8].lstrip(b"\x00").startswith(b"newmodel")
            or raw[:2] in (b"# ", b"#\t")
        )

    @staticmethod
    def _game_version(game: str):
        from src.core.geometry.model_data import GameVersion

        return GameVersion.K2 if str(game or "").upper() == "K2" else GameVersion.K1

    def _load_mdl(
        self,
        mdl_path: Path,
        *,
        mdx_path: Optional[Path] = None,
        game: str = "K1",
    ):
        """Load a binary or ASCII MDL through Ghost Rigger's model parsers."""

        raw = mdl_path.read_bytes()
        if self._looks_like_ascii_mdl(raw):
            from src.core.mdl.mdl_parser import MDLAsciiParser

            lines = raw.decode("utf-8", errors="replace").splitlines()
            model = MDLAsciiParser().parse(lines)
            model.mdl_path = str(mdl_path)
            model.mdx_path = ""
            model.game_version = self._game_version(game)
            return model

        from src.core.game.kotor_loader import load_model_from_bytes

        resolved_mdx = Path(mdx_path) if mdx_path else mdl_path.with_suffix(".mdx")
        mdx_bytes = resolved_mdx.read_bytes() if resolved_mdx.exists() else b""
        model = load_model_from_bytes(
            raw,
            mdx_bytes,
            game_version=self._game_version(game),
        )
        if model is None:
            raise RuntimeError(f"Could not parse MDL: {mdl_path}")
        model.mdl_path = str(mdl_path)
        model.mdx_path = str(resolved_mdx) if mdx_bytes else ""
        return model

    def _configure_fixture_supermodels(self, mdl_path: Path) -> None:
        """Enable inherited animation lookup for the isolated stock corpus."""

        try:
            from src.core.animation.animation_engine import SuperModelResolver
            from src.core.retargeting.sampler import (
                DEFAULT_CORPUS_ROOT,
                StockCorpusResourceManager,
            )
        except Exception:
            return

        try:
            corpus_root = Path(DEFAULT_CORPUS_ROOT).resolve()
            resolved = mdl_path.resolve()
            if corpus_root in resolved.parents:
                SuperModelResolver.configure(StockCorpusResourceManager(corpus_root))
                SuperModelResolver.clear_cache()
        except Exception:
            logger.debug("Could not configure fixture supermodel resolver", exc_info=True)

    def _init_renderer(self, model):
        from src.gui.qt_lib.viewports.frame_renderer import ArcBallCamera, FrameRenderer

        renderer = FrameRenderer(ArcBallCamera())
        renderer.show_texture = False
        renderer.show_bones = False
        renderer.show_grid = False
        renderer.show_light_gizmos = False
        renderer.set_model(model)
        self._renderer = renderer
        return renderer

    def _init_animation_engine(self, model):
        from src.core.animation.animation_engine import AnimationEngine

        self._animation_engine = AnimationEngine(model)
        return self._animation_engine

    def _available_animation_names(self, model) -> List[str]:
        try:
            engine = self._init_animation_engine(model)
            return sorted({str(entry["name"]) for entry in engine.list_all_animations()})
        except Exception:
            return sorted({str(anim.name) for anim in getattr(model, "animations", [])})

    def _set_animation_pose(
        self,
        model,
        animation_name: Optional[str],
        frame_index: int,
        fps: float,
    ) -> None:
        if self._renderer is None:
            return
        if not animation_name:
            self._renderer.set_animation_pose(None)
            return

        if self._animation_engine is None:
            self._init_animation_engine(model)
        engine = self._animation_engine
        if engine.current_animation is None or engine.current_animation.name.lower() != animation_name.lower():
            ok = engine.play(animation_name, loop=False, blend=False)
            if not ok:
                raise ValueError(f"Animation '{animation_name}' not found")
            base_pose = engine.evaluate(0.0)
            self._renderer.set_anim_base_pose(base_pose)

        seconds = frame_index / fps
        engine.seek(seconds)
        pose = engine.evaluate(seconds)
        length = getattr(engine.current_animation, "length", 0.0) if engine.current_animation else 0.0
        self._renderer.set_animation_pose(
            pose,
            name=animation_name,
            time=seconds,
            length=length,
        )

    def _camera_angles(self, preset: CameraPreset) -> Tuple[float, float]:
        return _CAMERA_ANGLES.get(preset, _CAMERA_ANGLES[CameraPreset.FRONT_ORTHO])

    def _capture_filename(
        self,
        mdl_path: Path,
        frame_index: int,
        animation_name: Optional[str],
    ) -> str:
        if animation_name:
            return f"{mdl_path.stem}_{animation_name}_frame_{frame_index:04d}.png"
        return f"{mdl_path.stem}_frame_{frame_index:04d}.png"

    def _capture_frame(
        self,
        *,
        mdl_path: Path,
        model,
        capture_spec: ViewportCaptureSpec,
        frame_index: int,
    ) -> FrameCapture:
        if self._renderer is None:
            raise RuntimeError("Renderer has not been initialized")

        start = time.perf_counter()
        self._set_animation_pose(
            model,
            capture_spec.animation_name,
            frame_index,
            capture_spec.fps,
        )

        png_path = self.output_dir / self._capture_filename(
            mdl_path,
            frame_index,
            capture_spec.animation_name,
        )
        azimuth, elevation = self._camera_angles(capture_spec.camera_preset)
        image = self._renderer.render_still(
            capture_spec.resolution[0],
            capture_spec.resolution[1],
            az_deg=azimuth,
            el_deg=elevation,
        )
        if image is None:
            raise RuntimeError(f"FrameRenderer returned no image for frame {frame_index}")
        image.save(png_path)

        bone_positions = self._extract_bone_positions(model)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return FrameCapture(
            frame_index=frame_index,
            png_path=png_path,
            bone_positions=bone_positions,
            render_time_ms=elapsed_ms,
        )

    @staticmethod
    def _to_wxyz(rotation_xyzw: Iterable[float]) -> Tuple[float, float, float, float]:
        vals = list(rotation_xyzw)
        if len(vals) != 4:
            return (1.0, 0.0, 0.0, 0.0)
        x, y, z, w = (float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))
        mag = math.sqrt(w * w + x * x + y * y + z * z)
        if mag <= 1e-9:
            return (1.0, 0.0, 0.0, 0.0)
        return (w / mag, x / mag, y / mag, z / mag)

    def _extract_bone_positions(self, model) -> List[BonePosition]:
        """Extract world transforms for all model nodes after current pose evaluation."""

        if self._renderer is None:
            return []
        positions: List[BonePosition] = []
        for node in getattr(model, "all_nodes", lambda: [])():
            try:
                world_pos, world_rot, _is_identity = self._renderer._node_world_transform(node)
            except Exception:
                try:
                    world_pos, world_rot = node.world_transform()
                except Exception:
                    continue
            positions.append(
                BonePosition(
                    name=str(getattr(node, "name", "")),
                    world_position=(
                        float(world_pos[0]),
                        float(world_pos[1]),
                        float(world_pos[2]),
                    ),
                    world_rotation_quat=self._to_wxyz(world_rot),
                )
            )
        return positions

    @staticmethod
    def _read_grayscale(path: Path):
        from PIL import Image

        img = Image.open(path).convert("L")
        try:
            import numpy as np

            return np.asarray(img, dtype="float64")
        finally:
            img.close()

    def _compute_ssim(self, image_a: Path, image_b: Path) -> float:
        """Compute SSIM, using scikit-image when present and a small fallback otherwise."""

        arr_a = self._read_grayscale(image_a)
        arr_b = self._read_grayscale(image_b)
        if arr_a.shape != arr_b.shape:
            raise ValueError(f"Image dimensions do not match: {arr_a.shape} vs {arr_b.shape}")

        try:
            from skimage.metrics import structural_similarity as ssim

            return float(ssim(arr_a, arr_b, data_range=255))
        except Exception:
            mean_a = float(arr_a.mean())
            mean_b = float(arr_b.mean())
            var_a = float(arr_a.var())
            var_b = float(arr_b.var())
            cov = float(((arr_a - mean_a) * (arr_b - mean_b)).mean())
            c1 = (0.01 * 255.0) ** 2
            c2 = (0.03 * 255.0) ** 2
            denom = (mean_a * mean_a + mean_b * mean_b + c1) * (var_a + var_b + c2)
            if denom <= 1e-12:
                return 1.0 if image_a.read_bytes() == image_b.read_bytes() else 0.0
            score = ((2 * mean_a * mean_b + c1) * (2 * cov + c2)) / denom
            return max(0.0, min(1.0, float(score)))

    def _reference_path(
        self,
        reference_captures_dir: Path,
        mdl_path: Path,
        frame_index: int,
        animation_name: Optional[str],
    ) -> Optional[Path]:
        expected = reference_captures_dir / self._capture_filename(
            mdl_path,
            frame_index,
            animation_name,
        )
        if expected.exists():
            return expected
        matches = sorted(reference_captures_dir.glob(f"*_frame_{frame_index:04d}.png"))
        return matches[0] if matches else None

    def validate_mdl(
        self,
        mdl_path: Path,
        capture_spec: ViewportCaptureSpec,
        reference_captures_dir: Optional[Path] = None,
        ssim_threshold: float = 0.85,
        *,
        mdx_path: Optional[Path] = None,
        game: str = "K1",
    ) -> ViewportValidationResult:
        """Load an MDL, render specified frames, and optionally compare captures."""

        mdl_path = Path(mdl_path)
        result = ViewportValidationResult(
            success=False,
            mdl_path=mdl_path,
            mdl_sha256="",
            node_count=0,
            mesh_count=0,
            animation_count=0,
        )
        start = time.perf_counter()

        try:
            if not mdl_path.exists():
                result.errors.append(f"MDL file not found: {mdl_path}")
                return result

            result.mdl_sha256 = self._compute_sha256(mdl_path)
            self._configure_fixture_supermodels(mdl_path)
            model = self._load_mdl(mdl_path, mdx_path=mdx_path, game=game)

            result.node_count = len(model.all_nodes())
            result.mesh_count = len(model.mesh_nodes())
            result.animation_names = self._available_animation_names(model)
            result.animation_count = len(result.animation_names)

            if capture_spec.animation_name:
                available = {name.lower() for name in result.animation_names}
                if capture_spec.animation_name.lower() not in available:
                    result.errors.append(
                        f"Animation '{capture_spec.animation_name}' not found. "
                        f"Available: {result.animation_names}"
                    )
                    return result

            self._init_renderer(model)
            if capture_spec.animation_name:
                self._init_animation_engine(model)

            ref_dir = Path(reference_captures_dir) if reference_captures_dir else None
            for frame_index in capture_spec.frames:
                capture = self._capture_frame(
                    mdl_path=mdl_path,
                    model=model,
                    capture_spec=capture_spec,
                    frame_index=frame_index,
                )
                result.captures.append(capture)

                if ref_dir:
                    ref_png = self._reference_path(
                        ref_dir,
                        mdl_path,
                        frame_index,
                        capture_spec.animation_name,
                    )
                    if ref_png is None:
                        result.warnings.append(
                            f"Reference not found for frame {frame_index} in {ref_dir}"
                        )
                    else:
                        score = self._compute_ssim(capture.png_path, ref_png)
                        result.ssim_scores[frame_index] = score
                        if score < ssim_threshold:
                            result.warnings.append(
                                f"Frame {frame_index}: SSIM {score:.3f} below "
                                f"threshold {ssim_threshold:.3f}"
                            )

            if result.ssim_scores:
                min_ssim = min(result.ssim_scores.values())
                if min_ssim >= 0.85:
                    result.trust_level = TrustLevel.CANONICAL
                elif min_ssim >= 0.70:
                    result.trust_level = TrustLevel.APPROXIMATE
                else:
                    result.trust_level = TrustLevel.INDICATIVE

            result.success = not result.errors
        except Exception as exc:
            logger.exception("Viewport validation failed")
            result.errors.append(f"Exception: {type(exc).__name__}: {exc}")
        finally:
            result.total_render_time_ms = (time.perf_counter() - start) * 1000.0

        return result

    def calibrate_against_ingame(
        self,
        viewport_render: Path,
        ingame_screenshot: Path,
    ) -> dict:
        """Compute viewport-to-in-game SSIM and classify trust level."""

        score = self._compute_ssim(Path(viewport_render), Path(ingame_screenshot))
        if score >= 0.85:
            trust = TrustLevel.CANONICAL
            recommendation = "Viewport is canonical for visual validation."
        elif score >= 0.70:
            trust = TrustLevel.APPROXIMATE
            recommendation = "Viewport is approximate; keep in-game spot checks."
        else:
            trust = TrustLevel.INDICATIVE
            recommendation = "Viewport is indicative; require in-game validation."

        return {
            "ssim": score,
            "trust_level": trust.value,
            "recommendation": recommendation,
            "viewport_render": str(viewport_render),
            "ingame_screenshot": str(ingame_screenshot),
        }
