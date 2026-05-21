"""3i Step 7 visual gate capture script.

Renders ``c_bomabeast`` (K1) and ``c_drexlf`` (K2) headlessly through the
``GpuRenderer`` GPU palette path under both:

    GHOSTRIGGER_SKIN_FORMULA unset                  -> F1 (production)
    GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_...  -> F11 wrapper

c_bomabeast is the falsification target chosen in 3i Step 7: its
``skin_bind`` rotation is non-identity so F11 must materially differ
from F1 (delta 0.6-3.6 units in palette space per the Step 7 reduction).

c_drexlf is the no-op control: Step 7 reduction proved F11 collapses to
F1 on 6 of 7 audited probes (only ``tailGeo`` shows a residual), so its
F1 vs F11 captures should be visually identical apart from at most a
sub-pixel residual on the tail.  This control is the infrastructure
sanity check.

Outputs:
    exports/skin_3i_step7_visual_gate/
        <game>_<resref>_cwalk_t000_<angle>_F1.png
        <game>_<resref>_cwalk_t000_<angle>_F11.png
        report.json   (per-pair pixel-diff + image metrics)

Usage::

    python scripts/skin_3i_step7_visual_gate.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K1_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"
K2_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

OUT_DIR = ROOT / "exports" / "skin_3i_step7_visual_gate"
REPORT_PATH = OUT_DIR / "report.json"

WIDTH = 512
HEIGHT = 512

# (resref, game, falsification_target?) — c_bomabeast is the gate; c_drexlf
# is the no-op infrastructure control.  c_brith is intentionally skipped
# per 3i Step 7 ("identity skin-bind => collapses to baseline").
TARGETS: Tuple[Tuple[str, str, bool], ...] = (
    ("c_bomabeast", "K1", True),
    ("c_drexlf",    "K2", False),
)

# (label, az_deg, el_deg) — three orthogonal-ish views to surface
# pelvis/upper-body coherence and limb folds rather than relying on
# a single diagonal angle.
ANGLES: Tuple[Tuple[str, float, float], ...] = (
    ("diagonal", -45.0, 20.0),
    ("front",     0.0,  10.0),
    ("side",     90.0,  10.0),
)

ANIM_NAME = "cwalk"
ANIM_TIME = 0.0


def _save_png(image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path))


def _image_metrics(path: Path) -> Dict[str, Any]:
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    mask = (arr.sum(axis=2) > 30.0)
    non_black = int(mask.sum())
    if non_black:
        ys, xs = np.where(mask)
        bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    else:
        bbox = (0, 0, 0, 0)
    return {
        "width": int(img.width),
        "height": int(img.height),
        "non_black_pixels": non_black,
        "bbox": list(bbox),
        "bbox_area": max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1]),
        "mean_brightness": float(arr.mean()),
    }


def _pixel_diff(path_a: Path, path_b: Path) -> Dict[str, float]:
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(path_a).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(path_b).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return {
            "pixel_diff_pct": 100.0,
            "max_channel_delta": 255.0,
            "mean_channel_delta": 255.0,
        }
    delta = np.abs(a - b)
    diff_mask = np.any(delta > 20, axis=2)
    return {
        "pixel_diff_pct": float(diff_mask.sum() * 100.0 / diff_mask.size),
        "max_channel_delta": float(delta.max()),
        "mean_channel_delta": float(delta.mean()),
    }


def _classify(diff_pct: float, falsification_target: bool) -> str:
    """Translate the pixel diff into the Step 7 binary decision label.

    The decision rule (from the user 3i Step 7 brief):
      - target (c_bomabeast): F11 must materially improve anatomy ->
        we cannot decide that from pixel deltas alone, but a non-trivial
        delta is the necessary precondition.  A "no movement" result
        on the falsification target collapses the B-translation line.
      - control (c_drexlf): F11 must be visually identical to F1.
        Any non-trivial delta means the env switch corrupted the
        no-op control and the gate cannot be trusted.
    """
    if falsification_target:
        if diff_pct < 0.05:
            return "TARGET_NO_MOVEMENT"
        if diff_pct < 1.0:
            return "TARGET_MARGINAL"
        return "TARGET_MATERIAL_DELTA"
    if diff_pct < 0.05:
        return "CONTROL_PASS"
    if diff_pct < 1.0:
        return "CONTROL_NEAR_PASS"
    return "CONTROL_FAIL"


def _setup_resource_manager():
    from src.core.qt_core.assets.resource_manager import ResourceManager
    from src.core.qt_core.animation.animation_engine import SuperModelResolver

    rm = ResourceManager()
    if not rm.set_k1_dir(K1_DIR):
        print(f"[step7_gate] WARN: K1 dir not found: {K1_DIR}", file=sys.stderr)
    if not rm.set_k2_dir(K2_DIR):
        print(f"[step7_gate] WARN: K2 dir not found: {K2_DIR}", file=sys.stderr)
    if not rm.is_ready():
        raise SystemExit("[step7_gate] FATAL: no game install indexed")
    SuperModelResolver._resource_manager = rm
    return rm


def _load_pose(model, name: str, time_s: float):
    """Evaluate ``name`` at ``time_s``; fall back to bind pose on failure."""
    from src.core.qt_core.animation.animation_engine import AnimationEngine

    engine = AnimationEngine(model)
    try:
        engine.play(name, loop=True, blend=False)
        pose = engine.evaluate(time_s)
        try:
            base_pose = engine.evaluate(0.0)
        except Exception:
            base_pose = None
        return pose, base_pose, engine
    except Exception as exc:
        print(f"[step7_gate] WARN: anim '{name}' missing -> bind pose ({exc!r})",
              file=sys.stderr)
        return None, None, None


def _render_under_formula(
    *,
    formula: str,
    rm,
    resref: str,
    game: str,
    angle_label: str,
    az_deg: float,
    el_deg: float,
    out_path: Path,
) -> Optional[Dict[str, Any]]:
    """Render one ``(resref, angle, formula)`` pair to PNG.

    Sets ``GHOSTRIGGER_SKIN_FORMULA`` for the duration of the call and
    restores its prior value on exit.  A fresh ``GpuRenderer`` is built
    per call so that no skin uploader state leaks between formulas.
    """
    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera
    from src.core.qt_core.assets.resource_manager import resolve_model_textures

    prior = os.environ.get("GHOSTRIGGER_SKIN_FORMULA")
    if formula == "F1":
        os.environ.pop("GHOSTRIGGER_SKIN_FORMULA", None)
    else:
        os.environ["GHOSTRIGGER_SKIN_FORMULA"] = formula

    renderer: Optional[GpuRenderer] = None
    try:
        model = rm.load_model(resref, game)
        if model is None:
            print(f"[step7_gate] ERR: failed to load {resref} from {game}",
                  file=sys.stderr)
            return None

        pose, base_pose, _engine = _load_pose(model, ANIM_NAME, ANIM_TIME)

        textures: Dict[str, Any] = {}
        try:
            textures = resolve_model_textures(model, rm, game=game)
        except Exception as exc:
            print(f"[step7_gate] WARN: texture load failed for {resref}: {exc!r}",
                  file=sys.stderr)

        camera = ArcBallCamera()
        try:
            bb_min, bb_max = model.bounding_box()
        except Exception:
            bb_min = getattr(model, "bb_min", None)
            bb_max = getattr(model, "bb_max", None)
        if bb_min is not None and bb_max is not None:
            camera.frame_bounds(bb_min, bb_max)
        camera.azimuth = az_deg
        camera.elevation = el_deg

        renderer = GpuRenderer()
        t0 = time.perf_counter()
        img = renderer.render(
            model, camera, WIDTH, HEIGHT,
            textures=textures,
            anim_pose=pose,
            anim_time=ANIM_TIME,
            anim_base_pose=base_pose,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if img is None:
            print(f"[step7_gate] ERR: renderer returned None for "
                  f"{resref}/{angle_label}/{formula}", file=sys.stderr)
            return None
        backend = renderer.perf.get("backend", "unknown")
        if backend != "gpu":
            print(f"[step7_gate] WARN: {resref}/{angle_label}/{formula} backend={backend} "
                  f"(visual gate is only meaningful on the GPU palette path)",
                  file=sys.stderr)

        _save_png(img, out_path)
        return {
            "path": str(out_path),
            "backend": backend,
            "frame_ms": elapsed_ms,
            "metrics": _image_metrics(out_path),
        }
    finally:
        if renderer is not None:
            try:
                renderer.release()
            except Exception:
                pass
        if prior is None:
            os.environ.pop("GHOSTRIGGER_SKIN_FORMULA", None)
        else:
            os.environ["GHOSTRIGGER_SKIN_FORMULA"] = prior


def main() -> int:
    rm = _setup_resource_manager()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "_generated_by": "scripts/skin_3i_step7_visual_gate.py",
        "_generated_at": time.time(),
        "anim": {"name": ANIM_NAME, "time": ANIM_TIME},
        "image_size": [WIDTH, HEIGHT],
        "decision_rule": (
            "Falsification target (c_bomabeast): F1 vs F11 must show "
            "TARGET_MATERIAL_DELTA AND visual review must improve "
            "upper/lower body coherence + pelvis continuity for B-translation "
            "to remain alive. Otherwise pivot to B-qbone-basis. Control "
            "(c_drexlf): F1 vs F11 must be CONTROL_PASS - any non-trivial "
            "delta means the env switch corrupted the no-op invariant and "
            "the gate cannot be trusted."
        ),
        "captures": [],
    }

    failures = 0
    for resref, game, is_target in TARGETS:
        for angle_label, az, el in ANGLES:
            base = f"{game.lower()}_{resref}_cwalk_t000_{angle_label}"
            out_f1 = OUT_DIR / f"{base}_F1.png"
            out_f11 = OUT_DIR / f"{base}_F11.png"

            f1_meta = _render_under_formula(
                formula="F1",
                rm=rm,
                resref=resref,
                game=game,
                angle_label=angle_label,
                az_deg=az,
                el_deg=el,
                out_path=out_f1,
            )
            f11_meta = _render_under_formula(
                formula="F11_rotation_only_skin_bind_wrapper",
                rm=rm,
                resref=resref,
                game=game,
                angle_label=angle_label,
                az_deg=az,
                el_deg=el,
                out_path=out_f11,
            )

            entry: Dict[str, Any] = {
                "resref": resref,
                "game": game,
                "is_falsification_target": is_target,
                "angle": angle_label,
                "az_deg": az,
                "el_deg": el,
                "f1": f1_meta,
                "f11": f11_meta,
            }
            if f1_meta is None or f11_meta is None:
                entry["status"] = "RENDER_FAILED"
                entry["classification"] = "ERROR"
                failures += 1
            else:
                diff = _pixel_diff(Path(f1_meta["path"]), Path(f11_meta["path"]))
                entry["pixel_diff"] = diff
                entry["classification"] = _classify(
                    diff["pixel_diff_pct"], is_target,
                )
                entry["status"] = "OK"
                print(
                    f"[step7_gate] {game}:{resref}:{angle_label} "
                    f"F1<->F11 diff={diff['pixel_diff_pct']:.3f}% "
                    f"max={diff['max_channel_delta']:.0f} -> {entry['classification']}"
                )
            report["captures"].append(entry)

    report["summary"] = {
        "captures_total": len(report["captures"]),
        "captures_failed": failures,
        "by_classification": {},
    }
    for cap in report["captures"]:
        cls = cap.get("classification", "ERROR")
        report["summary"]["by_classification"][cls] = (
            report["summary"]["by_classification"].get(cls, 0) + 1
        )

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[step7_gate] report -> {REPORT_PATH}")
    print(f"[step7_gate] summary: {report['summary']}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
