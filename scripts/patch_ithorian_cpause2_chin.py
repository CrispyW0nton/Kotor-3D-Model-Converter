"""T2575: raise the cpause2 thinking hand to the custom Ithorian's chin.

The cpause2 payload is byte-identical to the stock Ithorian clip, but the
custom model's arm/neck proportions leave the left hand ~6cm below the chin
during the hold (vanilla min hand-to-head 0.436m vs ours 0.500m).  This
patch transfers the VANILLA hand position expressed in the animated
``head_g`` frame (the chin rides the head) onto the custom skeleton with
the analytic two-bone solver, keeping the authored hand orientation, and
blends the correction by the vanilla hand-to-head distance so the rise and
lower phases stay authored.  Only the left-arm chain of ``cpause2`` changes;
the ``pause2`` modeltype-F alias is refreshed from the corrected clip.

Run:  python scripts/patch_ithorian_cpause2_chin.py
"""
from __future__ import annotations

import datetime
import hashlib
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(_python_roots(ROOT)):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
K1 = pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PATCH_TAG = "t2575"
# The golden bytes this patch expects to start from (T2574 output).
PRE_MDL_SHA256 = (
    "ea790a88df8b51b95fb259566eeacd4cdf53a8c9e8dccb881cb22583678721d8"
)
PRE_MDX_SHA256 = (
    "be156cc8ccd0f2e225d66f385ae37713f52874f957cfeb3e74c5f981ec4677b1"
)
# Blend by the vanilla hand-to-head distance: fully corrected during the
# chin hold, untouched while the arm is down.
FULL_WEIGHT_DISTANCE = 0.55
ZERO_WEIGHT_DISTANCE = 0.85
CHANGED_CLIPS = {"cpause2", "pause2"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clip(model, name: str):
    return next(
        a for a in model.animations
        if str(a.name or "").strip().lower() == name
    )


def _chin_scan(model, anim) -> tuple[float, float]:
    from src.core.animation.animation_engine import (
        evaluate_aurora_animation_pose,
    )

    from build_sith_ithorians import _pose_world_by_name

    length = float(anim.length)
    best = (float("inf"), 0.0)
    for index in range(int(length * 30.0) + 1):
        t = index / 30.0
        pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(model, anim, t))
        d = math.dist(pose["lhand_g"].position, pose["head_g"].position)
        if d < best[0]:
            best = (d, t)
    return best


def correct_chin_arm(model, vanilla) -> dict:
    from src.core.animation.animation_engine import (
        evaluate_aurora_animation_pose,
    )
    from src.math.limb_ik import solve_two_bone_positions

    from build_sith_ithorians import (
        _clean_animation_times,
        _ensure_arm_orientation_track,
        _point_from_frame,
        _point_in_frame,
        _pose_world_by_name,
        _quat_between_vecs,
        _quat_inv_xyzw,
        _quat_mul_xyzw,
        _quat_norm_xyzw,
    )

    anim = _clip(model, "cpause2")
    source_clip = _clip(vanilla, "cpause2")
    length = float(anim.length)

    relevant = {"head_g", "lbicep_g", "lforearm_g", "lhand_g", "torsoupr_g"}
    times = [0.0, length]
    for block in (anim, source_clip):
        for node in block.nodes or []:
            if str(node.name or "").strip().lower() not in relevant:
                continue
            for ctrl in node.controllers or []:
                times.extend(float(t) for t in (ctrl.get("times") or []))
    for index in range(int(length * 30.0) + 1):
        times.append(index / 30.0)
    solve_times = _clean_animation_times(times, length)

    rig_by_name = {
        str(node.name or "").strip().lower(): node
        for node in model.all_nodes()
    }
    tracks = {
        name: _ensure_arm_orientation_track(anim, model, name, solve_times)
        for name in ("lbicep_g", "lforearm_g", "lhand_g")
    }

    solved = 0
    max_weight = 0.0
    max_landing = 0.0
    for key_index, t in enumerate(solve_times):
        vanilla_pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(vanilla, source_clip, t))
        vanilla_head = vanilla_pose["head_g"]
        vanilla_hand = vanilla_pose["lhand_g"]
        d_vanilla = math.dist(vanilla_hand.position, vanilla_head.position)
        weight = (ZERO_WEIGHT_DISTANCE - d_vanilla) / (
            ZERO_WEIGHT_DISTANCE - FULL_WEIGHT_DISTANCE)
        weight = max(0.0, min(1.0, weight))
        if weight <= 0.0:
            continue
        max_weight = max(max_weight, weight)

        target_pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(model, anim, t))
        head = target_pose["head_g"]
        shoulder = target_pose["lbicep_g"]
        elbow = target_pose["lforearm_g"]
        hand = target_pose["lhand_g"]
        original_hand_world_q = tuple(float(c) for c in hand.rotation[:4])

        offset_vanilla = _point_in_frame(vanilla_hand.position, vanilla_head)
        offset_current = _point_in_frame(hand.position, head)
        goal_local = tuple(
            current + weight * (target - current)
            for current, target in zip(offset_current, offset_vanilla)
        )
        goal_world = _point_from_frame(goal_local, head)

        solution = solve_two_bone_positions(
            shoulder.position,
            elbow.position,
            hand.position,
            goal_world,
            elbow.position,
        )

        shoulder_delta = _quat_between_vecs(
            tuple(float(a) - float(b)
                  for a, b in zip(elbow.position, shoulder.position)),
            tuple(float(a) - float(b)
                  for a, b in zip(
                      solution.elbow_position, shoulder.position)),
        )
        new_shoulder_world = _quat_norm_xyzw(_quat_mul_xyzw(
            shoulder_delta, tuple(float(c) for c in shoulder.rotation[:4])))
        parent = rig_by_name["lbicep_g"].parent
        parent_world = target_pose[str(parent.name).strip().lower()]
        tracks["lbicep_g"]["values"][key_index] = list(
            _quat_norm_xyzw(_quat_mul_xyzw(
                _quat_inv_xyzw(
                    tuple(float(c) for c in parent_world.rotation[:4])),
                new_shoulder_world,
            )))

        target_pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(model, anim, t))
        elbow = target_pose["lforearm_g"]
        hand = target_pose["lhand_g"]
        elbow_delta = _quat_between_vecs(
            tuple(float(a) - float(b)
                  for a, b in zip(hand.position, elbow.position)),
            tuple(float(a) - float(b)
                  for a, b in zip(
                      solution.target_position, elbow.position)),
        )
        new_elbow_world = _quat_norm_xyzw(_quat_mul_xyzw(
            elbow_delta, tuple(float(c) for c in elbow.rotation[:4])))
        parent = rig_by_name["lforearm_g"].parent
        parent_world = target_pose[str(parent.name).strip().lower()]
        tracks["lforearm_g"]["values"][key_index] = list(
            _quat_norm_xyzw(_quat_mul_xyzw(
                _quat_inv_xyzw(
                    tuple(float(c) for c in parent_world.rotation[:4])),
                new_elbow_world,
            )))

        target_pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(model, anim, t))
        parent = rig_by_name["lhand_g"].parent
        parent_world = target_pose[str(parent.name).strip().lower()]
        tracks["lhand_g"]["values"][key_index] = list(
            _quat_norm_xyzw(_quat_mul_xyzw(
                _quat_inv_xyzw(
                    tuple(float(c) for c in parent_world.rotation[:4])),
                original_hand_world_q,
            )))

        target_pose = _pose_world_by_name(
            evaluate_aurora_animation_pose(model, anim, t))
        landing = math.dist(
            target_pose["lhand_g"].position, solution.target_position)
        max_landing = max(max_landing, landing)
        assert landing <= 1.0e-3, (
            f"cpause2 lhand IK miss at {t:.4f}: {landing:.6f}m")
        solved += 1

    return {
        "solve_times": len(solve_times),
        "solved_keys": solved,
        "max_weight": max_weight,
        "max_landing_error": max_landing,
    }


def main() -> None:
    from src.core.assets.resource_manager import ResourceManager
    from src.core.game.kotor_loader import load_model_from_bytes
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    from build_sith_ithorians import (
        MODELTYPE_F_NATIVE_STATE_ALIASES,
        _animation_payload_signature,
        assert_hand_attachment_hook_contract,
        install_modeltype_f_native_state_aliases,
    )

    mdl_path = PACKAGE / "c_ithlord.mdl"
    mdx_path = PACKAGE / "c_ithlord.mdx"
    old_mdl = mdl_path.read_bytes()
    old_mdx = mdx_path.read_bytes()
    assert _sha256(old_mdl) == PRE_MDL_SHA256, (
        "golden MDL does not match the build this patch was written against"
    )
    assert _sha256(old_mdx) == PRE_MDX_SHA256, "golden MDX drifted"

    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    vanilla = manager.load_model("c_ithorian", "K1", prefer_base_archive=True)
    assert vanilla is not None

    model = load_model_from_bytes(old_mdl, old_mdx)
    assert model is not None
    before = {
        str(anim.name or "").lower(): _animation_payload_signature(anim)
        for anim in model.animations
    }
    animation_count = len(model.animations)

    baseline = _chin_scan(model, _clip(model, "cpause2"))
    vanilla_best = _chin_scan(vanilla, _clip(vanilla, "cpause2"))
    print(f"vanilla chin hold: min lhand-head {vanilla_best[0]:.4f} "
          f"@ t={vanilla_best[1]:.3f}")
    print(f"custom before    : min lhand-head {baseline[0]:.4f} "
          f"@ t={baseline[1]:.3f}")

    report = correct_chin_arm(model, vanilla)
    print(f"IK pass: {report['solved_keys']}/{report['solve_times']} keys, "
          f"max landing {report['max_landing_error']:.6f}m")

    alias_report = install_modeltype_f_native_state_aliases(model)
    print("aliases refreshed: "
          + ", ".join(f"{t}<-{d['source']}" for t, d in alias_report.items()))

    raw_mdl, raw_mdx = MDLBinaryWriter().write(model)
    reloaded = load_model_from_bytes(raw_mdl, raw_mdx)
    assert reloaded is not None
    assert_hand_attachment_hook_contract(reloaded)
    assert len(reloaded.animations) == animation_count
    internal = raw_mdl[20:52].split(b"\x00", 1)[0].decode("ascii", "replace")
    assert internal == "c_ithlord", internal

    after = {
        str(anim.name or "").lower(): _animation_payload_signature(anim)
        for anim in reloaded.animations
    }
    changed = [
        name
        for name, signature in before.items()
        if name not in CHANGED_CLIPS and after[name] != signature
    ]
    assert not changed, f"unexpected clips changed: {changed}"
    assert after["pause2"] == after["cpause2"], (
        "pause2 alias no longer mirrors the corrected cpause2"
    )
    stock_by_name = {
        str(anim.name or "").lower(): anim for anim in vanilla.animations
    }
    for target, source in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
        if target in CHANGED_CLIPS:
            continue
        assert after[target] == _animation_payload_signature(
            stock_by_name[source]
        ), f"{target} drifted from vanilla {source}"

    # The true acceptance gate runs on the SERIALIZED bytes.
    corrected = _chin_scan(reloaded, _clip(reloaded, "cpause2"))
    print(f"custom after     : min lhand-head {corrected[0]:.4f} "
          f"@ t={corrected[1]:.3f}")
    assert corrected[0] <= vanilla_best[0] + 0.02, (
        "serialized chin hold still short of the vanilla contact distance"
    )

    assert raw_mdl.count(b"c_ithlord") == 9, raw_mdl.count(b"c_ithlord")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for path, data in ((mdl_path, old_mdl), (mdx_path, old_mdx)):
        backup = path.with_suffix(
            path.suffix + f".pre_{PATCH_TAG}_{stamp}.bak")
        backup.write_bytes(data)
        print(f"backup: {backup.name}")
    mdl_path.write_bytes(raw_mdl)
    mdx_path.write_bytes(raw_mdx)

    purple = raw_mdl.replace(b"c_ithlord", b"c_ithpurp")
    print(f"new GOLDEN_MDL_SHA256 = {_sha256(raw_mdl)}")
    print(f"new GOLDEN_MDX_SHA256 = {_sha256(raw_mdx)}")
    print(f"new PURPLE_MDL_SHA256 = {_sha256(purple)}")
    print("patched golden package model in place; update the pinned hashes, "
          "rerun the demo package builder, then install to the live "
          "Override.")


if __name__ == "__main__":
    main()
