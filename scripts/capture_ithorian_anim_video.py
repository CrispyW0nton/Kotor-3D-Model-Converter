"""Render the custom Sith Ithorian animating through the real Character Builder
viewport (QtViewportWidget + pygfx/wgpu), capturing 30fps frames for a video.

Proof harness for T2559: builds the c_ithlord rig exactly as the Character
Builder shows it (load_body -> apply_template_rig -> anatomical split, with the
T2555/T2557/T2558 skinning fixes), plays ONE animation, and grabs the viewport
each frame.  Supports the Ithorian's own clips and S_Female02 supermodel clips.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from scripts.mcp.start_kotormcp_stdio import _python_roots
    for item in reversed(list(_python_roots(ROOT))):
        text = str(item)
        if Path(text).exists() and text not in sys.path:
            sys.path.insert(0, text)
except Exception as _exc:  # pragma: no cover
    for rel in (
        "native/GhostRigger.Core.Workflow/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Resources/Python",
        "native/GhostRigger.Core.IO/Python",
        "native/GhostRigger.Core.Rendering/Python",
        "native/GhostRigger.Core.GUI.Display/Python",
        "native/GhostRigger.Core.Scene/Python",
        "",
    ):
        p = str(ROOT / rel) if rel else str(ROOT)
        if p not in sys.path:
            sys.path.insert(0, p)

K1 = os.environ.get("K1_PATH", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
SRC = Path(r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\SithIthorianScholar")
OBJ = str(SRC / "IthorianSithLord.obj")


def build_rig(mgr):
    from src.core.characters import headless_body_workflow as wf
    from src.core.characters import character_builder as cb
    from src.core.geometry import model_data as md
    donor = lambda: mgr.load_model("c_ithorian", "K1", prefer_base_archive=True)
    scene = md.CharacterScene(game_version="K1")
    scene.mode = md.CharacterMode.CREATURE
    load = wf.load_body(OBJ, scene, game_version="K1", fit_reference_model=donor(),
                        fit_reference_label="c_ithorian",
                        expected_mode=md.CharacterMode.CREATURE, allow_mode_correction=True)
    assert load.ok, (load.code, load.message)
    rig = cb.apply_template_rig(load.model, donor(), game="K1")
    assert rig.get("ok"), rig.get("message")
    rigged = rig["model"]
    scene.assign(md.PartSlot.HEADLESS_BODY, rigged, resref="c_ithlord",
                 game_version="K1", source_path=OBJ)
    wf.split_imported_mesh_nodes(scene, respect_skinned="split_with_weight_remap",
                                 reference_model=donor())
    return rigged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anim", default="cwalk")
    ap.add_argument("--supermodel", default="", help="if set, inherit anim from this supermodel (e.g. S_Female02)")
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--start", type=float, default=0.0, help="first clip time in seconds")
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "ithorian_anim"))
    ap.add_argument("--resref", default="c_ithlord", help="load the deployed MDL by resref (proper textures)")
    ap.add_argument("--rebuild", action="store_true", help="build the rig from OBJ instead of loading the deployed MDL")
    ap.add_argument("--right-weapon", default="", help="BAS-attach a weapon model, e.g. w_lghtsbr_002")
    ap.add_argument("--mode", default="realistic", choices=["realistic", "shaded", "flat"])
    ap.add_argument("--bones", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.frames = 4

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from PySide6 import QtWidgets
    from src.core.assets.resource_manager import ResourceManager
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.rendering.renderer_backend import RendererBackend
    from src.core.rendering.renderer_settings import RendererSettings
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from scripts.visual_harness_pygfx_flat_animation import (
        _process_events, _force_render, _focus_camera_on_node, _best_sample_time,
    )

    mgr = ResourceManager()
    mgr.set_k1_dir(K1)
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(mgr)

    if args.rebuild:
        print("building c_ithlord rig from OBJ ...")
        rigged = build_rig(mgr)
    else:
        print(f"loading deployed MDL {args.resref!r} from override ...")
        rigged = mgr.load_model(args.resref, "K1")
        assert rigged is not None, f"could not load {args.resref}"

    source_model = rigged
    anim = args.anim
    if args.supermodel:
        rigged.supermodel = args.supermodel
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(mgr)
        # evaluate the clip through the supermodel chain against the Ithorian bones
        source_model = rigged

    if args.right_weapon:
        from src.systems.bas.preview_composer import build_bas_preview_model
        weapon = mgr.load_model(args.right_weapon, "K1")
        assert weapon is not None, f"could not load right-hand weapon {args.right_weapon}"
        rigged = build_bas_preview_model(
            body_model=rigged,
            attachment_models={"right_weapon": weapon},
            name=f"{args.resref}_{args.right_weapon}_proof",
        )
        source_model = rigged

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    viewport.resize(1280, 820)
    viewport.set_renderer_settings(RendererSettings(
        backend=RendererBackend.PYGFX_WGPU,
        preferred_windows_backend=RendererBackend.WGPU_D3D12,
        allow_fallback=True, target_fps=60,
        idle_render_mode="continuous", show_renderer_diagnostics=False,
    ))
    viewport.set_resource_manager(mgr, "K1")
    viewport.load_model(rigged)
    viewport.set_render_mode(args.mode)
    viewport.toggle_texture(True)
    viewport.toggle_bones(bool(args.bones))
    viewport.toggle_grid(True)
    viewport.show()
    _process_events(app, 0.6)

    engine = AnimationEngine(source_model)
    if not engine.play(anim, loop=True, blend=False):
        print(f"FAILED to play animation {anim!r} (supermodel={args.supermodel!r})")
        clips = sorted(a.name for a in source_model.animations)
        print("available local clips:", clips)
        return 2
    length = float(getattr(engine.current_animation, "length", 0.0) or 0.0) or 1.0
    pose0 = engine.evaluate(0.0)
    viewport.set_anim_base_pose(pose0)
    viewport.set_animation_playback_active(True, "ithorian proof")

    # frame the whole model
    _force_render(viewport, app, "load", scene=True, resources=True, style=True, overlay=True, hud=True)
    try:
        viewport.frame_all()
    except Exception as exc:
        print("frame_all failed:", exc)
    _process_events(app, 0.3)
    _force_render(viewport, app, "framed", camera=True, scene=True, style=True, overlay=True, hud=True)

    print(f"rendering {args.frames} frames of {anim!r} (len={length:.3f}s) ...")
    written = 0
    for i in range(args.frames):
        t = (float(args.start) + i / float(args.fps)) % length
        pose = engine.evaluate(t)
        viewport.set_animation_pose(pose, name=anim, time=t, length=length)
        _force_render(viewport, app, f"f{i}", animation=True, overlay=True, hud=True)
        pm = viewport.grab()
        fp = out / f"frame_{i:04d}.png"
        if pm.save(str(fp)):
            written += 1
        if i == 0 or (i + 1) % 30 == 0:
            print(f"  frame {i+1}/{args.frames} -> {fp.name} ({pm.width()}x{pm.height()})")
    viewport.set_animation_playback_active(False)
    print(f"DONE: {written}/{args.frames} frames in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
