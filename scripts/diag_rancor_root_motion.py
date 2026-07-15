"""Root-motion parity: rigged custom Rancor vs vanilla c_rancorS.

T2535: the Character Builder preview showed the custom Rancor's root drifting
per animation — cdie dropped the model through the floor.  Supermodel
(c_rancor) position tracks are multiplied by the REQUESTING model's
anim_scale (KotorBlender: p1 = restloc + animscale*val).  Vanilla c_rancorS
ships anim_scale=0.336; a rigged model that keeps the FBX default 1.0 plays
every inherited clip's translations ~3x too large.

This diagnostic drives BOTH models through the real playback path
(AnimationEngine.play/evaluate + SuperModelResolver, NOT the scale-blind
audit oracle) and compares per-animation world-space root-motion deltas
pos(t) - pos(0) of the pelvis.  Deltas cancel rest-pivot differences, so any
deviation is animation-track scaling, not skeleton fit.

Usage:
  python scripts/diag_rancor_root_motion.py            # rigged model as produced
  python scripts/diag_rancor_root_motion.py --force-anim-scale-1   # reproduce the bug
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Workflow/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Project/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Validation/Python",
    "native/GhostRigger.Core.Rendering/Python",
    "native/GhostRigger.Core.Unreal/Python",
    "native/GhostRigger.Core.Tools/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

FBX = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor"
    r"\Final\RancorTamedConceptFinal.fbx"
)
K2 = r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"

from src.core.assets.resource_manager import ResourceManager  # noqa: E402
from src.core.characters import headless_body_workflow as wf  # noqa: E402
from src.core.characters import character_builder as cb  # noqa: E402
from src.core.animation.animation_engine import (  # noqa: E402
    AnimationEngine,
    SuperModelResolver,
)
from src.core.geometry import model_data as md  # noqa: E402

TRACK_BONES = ("ran_pelvis", "rootdummy")
SAMPLES = 8


def _quat_rotate(q, v):
    qx, qy, qz, qw = q
    vx, vy, vz = v
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (
        vx + qw * tx + (qy * tz - qz * ty),
        vy + qw * ty + (qz * tx - qx * tz),
        vz + qw * tz + (qx * ty - qy * tx),
    )


def _quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def world_positions(model, pose):
    """FK: world position per node name (lower), pose-local overriding rest."""
    out = {}

    def walk(node, parent_pos, parent_rot):
        name = str(getattr(node, "name", "") or "").lower()
        node_pose = pose.nodes.get(name) if pose is not None else None
        local_pos = tuple(
            float(v) for v in (
                node_pose.position if node_pose is not None
                else (getattr(node, "position", (0, 0, 0)) or (0, 0, 0))
            )
        )
        local_rot = tuple(
            float(v) for v in (
                node_pose.rotation if node_pose is not None
                else (getattr(node, "rotation", (0, 0, 0, 1)) or (0, 0, 0, 1))
            )
        )
        wp = _quat_rotate(parent_rot, local_pos)
        world_pos = (parent_pos[0] + wp[0], parent_pos[1] + wp[1], parent_pos[2] + wp[2])
        world_rot = _quat_mul(parent_rot, local_rot)
        if name and name not in out:
            out[name] = world_pos
        for child in list(getattr(node, "children", []) or []):
            walk(child, world_pos, world_rot)

    root = getattr(model, "root_node", None)
    if root is not None:
        walk(root, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    return out


def trajectory(model, anim_name, length):
    """Per-sample world positions of tracked bones + global min bone Z."""
    engine = AnimationEngine(model)
    if not engine.play(anim_name, loop=False, blend=False):
        return None
    times = [length * i / float(SAMPLES - 1) for i in range(SAMPLES)]
    rows = []
    for t in times:
        pose = engine.evaluate(t)
        world = world_positions(model, pose)
        row = {"t": round(t, 4)}
        for bone in TRACK_BONES:
            if bone in world:
                row[bone] = world[bone]
        row["min_z"] = min((p[2] for p in world.values()), default=0.0)
        rows.append(row)
    return rows


def deltas(rows, bone):
    if not rows or bone not in rows[0]:
        return None
    base = rows[0][bone]
    return [
        (r[bone][0] - base[0], r[bone][1] - base[1], r[bone][2] - base[2])
        for r in rows if bone in r
    ]


def main() -> int:
    mgr = ResourceManager()
    assert mgr.set_k2_dir(K2), "K2 index failed"
    SuperModelResolver.configure(mgr)
    SuperModelResolver.clear_cache()

    vanilla = mgr.load_model("c_rancors", "K2", prefer_base_archive=True)
    assert vanilla is not None, "vanilla c_rancors missing"

    scene = md.CharacterScene(game_version="K2")
    scene.mode = md.CharacterMode.CREATURE
    load = wf.load_body(
        str(FBX), scene, game_version="K2",
        fit_reference_model=mgr.load_model("c_rancors", "K2", prefer_base_archive=True),
        fit_reference_label="c_rancorS",
        expected_mode=md.CharacterMode.CREATURE,
        allow_mode_correction=True,
    )
    assert load.ok, (load.code, load.message)
    rig = cb.apply_template_rig(
        load.model,
        mgr.load_model("c_rancors", "K2", prefer_base_archive=True),
        game="K2",
    )
    assert rig.get("ok"), rig.get("message")
    custom = rig["model"]
    if "--force-anim-scale-1" in sys.argv:
        custom.anim_scale = 1.0
        print("REPRODUCTION MODE: custom.anim_scale forced to 1.0")

    print(f"vanilla anim_scale={vanilla.anim_scale:.4f}  "
          f"custom anim_scale={float(getattr(custom, 'anim_scale', 1.0) or 1.0):.4f}")

    entries = SuperModelResolver.list_all_animations(vanilla, "K2")
    print(f"animations via chain: {len(entries)}")

    report = []
    for name, source, scale in entries:
        anim, _ = SuperModelResolver.resolve_animation(vanilla, name, "K2")
        length = float(getattr(anim, "length", 0.0) or 0.0) if anim is not None else 0.0
        rows_v = trajectory(vanilla, name, length)
        rows_c = trajectory(custom, name, length)
        if rows_v is None or rows_c is None:
            report.append({"animation": name, "source": source, "error": "play_failed"})
            continue
        rec = {
            "animation": name,
            "source": source,
            "inherited": source.lower() != str(vanilla.name).lower(),
            "length": round(length, 3),
            "vanilla_min_z": round(min(r["min_z"] for r in rows_v), 4),
            "custom_min_z": round(min(r["min_z"] for r in rows_c), 4),
        }
        for bone in TRACK_BONES:
            dv = deltas(rows_v, bone)
            dc = deltas(rows_c, bone)
            if dv is None or dc is None or len(dv) != len(dc):
                continue
            dev = max(
                math.dist(a, b) for a, b in zip(dv, dc)
            )
            mag_v = max((math.dist((0, 0, 0), d) for d in dv), default=0.0)
            mag_c = max((math.dist((0, 0, 0), d) for d in dc), default=0.0)
            rec[f"{bone}_max_deviation"] = round(dev, 4)
            rec[f"{bone}_vanilla_motion"] = round(mag_v, 4)
            rec[f"{bone}_custom_motion"] = round(mag_c, 4)
        report.append(rec)

    out = ROOT / "Saved" / "rancor_root_motion.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}\n")
    print(f"{'animation':14s} {'src':10s} {'vanilla':>8s} {'custom':>8s} "
          f"{'deviation':>9s}  {'v.minZ':>7s} {'c.minZ':>7s}")
    worst = 0.0
    for rec in sorted(
        report, key=lambda r: r.get("ran_pelvis_max_deviation", 0.0), reverse=True
    ):
        if "error" in rec:
            print(f"{rec['animation']:14s} PLAY FAILED")
            continue
        dev = rec.get("ran_pelvis_max_deviation", 0.0)
        worst = max(worst, dev)
        print(f"{rec['animation']:14s} {rec['source'][:10]:10s} "
              f"{rec.get('ran_pelvis_vanilla_motion', 0):8.3f} "
              f"{rec.get('ran_pelvis_custom_motion', 0):8.3f} "
              f"{dev:9.4f}  {rec['vanilla_min_z']:7.3f} {rec['custom_min_z']:7.3f}")
    print(f"\nWORST pelvis root-motion deviation vs vanilla: {worst:.4f} game units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
