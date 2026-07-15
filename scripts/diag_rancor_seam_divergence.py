"""Cross-node seam divergence diagnostic for the SPLIT custom Rancor.

The full animation audit (diag_rancor_full_animation_audit.py) measures edge
stretch WITHIN each skinned node — but the in-game model is the anatomically
SPLIT model (split_skinned_mesh_nodes_with_weight_remap), and cracks open at
the boundaries BETWEEN split nodes, where no edge exists.  This script makes
that failure mode measurable:

1. fit -> rig -> SPLIT (mirrors the Character Builder Node Splitter path)
2. static check: group vertices that are coincident at bind (within and
   across split nodes) and compare each member's skin weights resolved into
   bone-NAME space — both the full influence list and the effective
   4-influence truncation the skinner actually uses.  Any delta here is a
   guaranteed animated crack, and fingerprints the pipeline pass that
   diverged the twins.
3. dynamic check: skin every node under sampled poses of EVERY inherited
   animation (same LBS path as the audit/renderer) and measure the world gap
   of each coincident group -> per-animation, per node-pair crack magnitude.

Outputs under Saved/:
- rancor_seam_divergence.json / .md   (custom split model)
- rancor_seam_divergence_vanilla.json / .md  (--vanilla control on c_rancorS)
"""
from __future__ import annotations

import json
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
from src.core.characters.animation_deformation_validator import (  # noqa: E402
    _skin_rows_to_arrays,
    _skin_vertices_with_palette,
    _palette_pose_from_evaluated_pose,
)
from src.core.animation.animation_engine import evaluate_aurora_animation_pose  # noqa: E402
from src.core.animation.gpu_skinning import MAX_BONES, MatrixPaletteUploader  # noqa: E402
from src.core.geometry import model_data as md  # noqa: E402

COINCIDENT_RADIUS = 5.0e-4       # world units: vertices closer than this at bind are "the same point"
WEIGHT_DELTA_EPS = 1.0e-4        # bone-name weight deltas above this count as divergent
GAP_REPORT_EPS = 1.0e-3          # animated seam gaps above this are reported

_REGION_RULES = [
    ("arms", ("bicep", "forearm", "shoulder", "clavic")),
    ("hands", ("hand", "index", "mid_", "pink", "thumb", "finger")),
    ("legs", ("thigh", "shin", "foot", "knee", "calf", "toe", "ankle")),
    ("torso", ("chest", "pelvis", "torso", "rib", "tail", "spine", "hip")),
    ("neck", ("neck",)),
    ("head", ("head", "jaw", "mouth", "tongue")),
]


def classify_bone(name: str) -> str:
    n = name.strip().lower().replace("ran_", "")
    for region, prefixes in _REGION_RULES:
        for p in prefixes:
            if n.startswith(p):
                return region
    return "torso"


def _sample_times(length, samples_per_animation=5):
    if length <= 0.0:
        return [0.0]
    count = max(1, int(samples_per_animation))
    inner = [length * (step + 1) / float(count + 1) for step in range(count)]
    base_t = min(0.033, length * 0.05)
    if not any(abs(t - base_t) < 1e-4 for t in inner):
        inner = [base_t] + inner
    return inner


def resolve_weights_by_name(row, bone_map):
    """influences -> {bone_name_lower: weight}; full list, unnormalized."""
    out = {}
    for influence in list(getattr(row, "influences", []) or []):
        try:
            bone_index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0) or 0.0)
        except Exception:
            continue
        if bone_index < 0 or bone_index >= len(bone_map) or weight <= 1e-9:
            continue
        name = str(bone_map[bone_index] or "").strip().lower()
        if not name:
            continue
        out[name] = out.get(name, 0.0) + weight
    return out


def effective_weights_by_name(row, bone_map):
    """What the skinner actually uses: first 4 influences, renormalized."""
    out = {}
    for influence in list(getattr(row, "influences", []) or [])[:4]:
        try:
            bone_index = int(getattr(influence, "bone_index", -1))
            weight = float(getattr(influence, "weight", 0.0) or 0.0)
        except Exception:
            continue
        if bone_index < 0 or bone_index >= len(bone_map) or weight <= 1e-9:
            continue
        name = str(bone_map[bone_index] or "").strip().lower()
        if not name:
            continue
        out[name] = out.get(name, 0.0) + weight
    total = sum(out.values())
    if total > 1e-9:
        out = {k: v / total for k, v in out.items()}
    return out


def weight_delta(a, b):
    keys = set(a) | set(b)
    return max((abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys), default=0.0)


def weight_delta_bones(a, b, top=3):
    keys = set(a) | set(b)
    deltas = sorted(
        ((abs(a.get(k, 0.0) - b.get(k, 0.0)), k) for k in keys), reverse=True
    )
    return [(k, round(d, 4)) for d, k in deltas[:top] if d > WEIGHT_DELTA_EPS]


def main() -> int:
    import numpy as np
    from scipy.spatial import cKDTree

    vanilla_mode = "--vanilla" in sys.argv
    mgr = ResourceManager()
    assert mgr.set_k2_dir(K2), "K2 index failed"
    reference = mgr.load_model("c_rancors", "K2") or mgr.load_model("c_rancor", "K2")
    assert reference is not None, "could not load c_rancorS reference"

    split_report = None
    if vanilla_mode:
        model = reference
        print("VANILLA CONTROL MODE: seam audit across stock c_rancorS skin nodes")
    else:
        if not FBX.exists():
            print(f"MISSING FBX: {FBX}")
            return 2
        scene = md.CharacterScene(game_version="K2")
        scene.mode = md.CharacterMode.CREATURE
        load = wf.load_body(
            str(FBX), scene, game_version="K2",
            fit_reference_model=reference,
            fit_reference_label=getattr(reference, "name", "c_rancorS"),
            expected_mode=md.CharacterMode.CREATURE,
            allow_mode_correction=True,
        )
        if not load.ok:
            print("load failed:", load.code, load.message)
            return 1
        rig = cb.apply_template_rig(load.model, reference, game="K2")
        if not rig.get("ok"):
            print("rig failed:", rig.get("message"))
            return 1
        model = rig["model"]
        if "--no-split" in sys.argv:
            print("NO-SPLIT MODE: auditing the rigged model before the Node Splitter")
        else:
            # --- the step the old audit skipped: the GUI Node Splitter path ---
            split_result = wf.split_skinned_mesh_nodes_with_weight_remap(model, reference)
            if not split_result.get("ok"):
                print("SPLIT FAILED:", split_result.get("code"), split_result.get("message"))
                return 1
            split_report = {
                "code": split_result.get("code"),
                "split_nodes": split_result.get("split_nodes"),
                "per_node": split_result.get("per_node"),
                "seam_weld": split_result.get("seam_weld"),
            }
            if split_result.get("seam_weld") is not None:
                print(f"  seam_weld: {split_result.get('seam_weld')}")
            print(f"split: {split_result.get('code')} -> "
                  f"{split_result.get('split_nodes')} region nodes")
            for entry in list(split_result.get("per_node") or []):
                print(f"  source={entry.get('source_node')} regions={entry.get('regions')} "
                      f"palettes={entry.get('palette_sizes')} method={entry.get('method')}")
                for sm in entry.get("weight_smoothing") or []:
                    print(f"    smoothing: {sm}")
                for hs in entry.get("rancor_hand_stabilization") or []:
                    print(f"    hand_stab: {hs}")

    # ---- collect skinned nodes -------------------------------------------
    skinned = []
    for node in model.all_nodes():
        if not bool(getattr(node, "is_skin", False)):
            continue
        if not list(getattr(node, "vertices", []) or []):
            continue
        if not list(getattr(node, "skin_data", []) or []):
            continue
        if not list(getattr(node, "bone_map", []) or []):
            continue
        skinned.append(node)
    print(f"skinned nodes ({len(skinned)}): "
          f"{[str(getattr(n, 'name', '?')) for n in skinned]}")
    if len(skinned) == 0:
        print("no skinned nodes; nothing to do")
        return 1

    name_lookup = {
        str(getattr(n, "name", "") or "").strip().lower():
            str(getattr(n, "name", "") or "")
        for n in model.all_nodes()
    }

    mesh_data = []
    for mesh in skinned:
        verts = np.asarray(
            [tuple(float(c) for c in vx[:3]) for vx in mesh.vertices],
            dtype=np.float64,
        )
        world = wf._node_world_vertices_for_split(mesh, np)
        slot_names = [str(n or "").strip() for n in list(mesh.bone_map)]
        weights, indices = _skin_rows_to_arrays(
            list(mesh.skin_data), verts.shape[0], len(slot_names),
        )
        uploader = MatrixPaletteUploader(max_bones=max(int(MAX_BONES), len(slot_names)))
        uploader.build_inverse_bind_pose(model)
        mesh_data.append({
            "mesh": mesh,
            "name": str(getattr(mesh, "name", "") or "?"),
            "verts": verts,
            "world": np.asarray(world, dtype=np.float64),
            "slot_names": slot_names,
            "rows": list(mesh.skin_data),
            "weights": weights,
            "indices": indices,
            "uploader": uploader,
            "base_bind_flag": bool(getattr(
                mesh, "_gr_use_animation_base_bind_for_preview", False)),
        })

    # ---- coincident groups at bind (union-find over close world pairs) ---
    all_points = np.concatenate([d["world"] for d in mesh_data], axis=0)
    owner = []          # global vertex -> (mesh_index, local_index)
    for mi, d in enumerate(mesh_data):
        owner.extend((mi, vi) for vi in range(d["world"].shape[0]))
    tree = cKDTree(all_points)
    pairs = tree.query_pairs(r=COINCIDENT_RADIUS, output_type="ndarray")

    parent = list(range(all_points.shape[0]))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[rb] = ra

    groups = {}
    for gv in range(all_points.shape[0]):
        groups.setdefault(find(gv), []).append(gv)
    # keep only true seam groups: >1 member, at least 2 distinct rows
    seam_groups = [g for g in groups.values() if len(g) > 1]
    cross_groups = [
        g for g in seam_groups if len({owner[v][0] for v in g}) > 1
    ]
    print(f"coincident groups: {len(seam_groups)} total, "
          f"{len(cross_groups)} span multiple nodes")

    # ---- static weight comparison ----------------------------------------
    def node_pair_key(g):
        names = sorted({mesh_data[owner[v][0]]["name"] for v in g})
        return " <-> ".join(names) if len(names) > 1 else f"{names[0]} (in-node)"

    static_by_pair = {}
    divergent_groups = []
    for g in seam_groups:
        members = [(owner[v][0], owner[v][1]) for v in g]
        full = [
            resolve_weights_by_name(
                mesh_data[mi]["rows"][vi], mesh_data[mi]["slot_names"])
            for mi, vi in members
        ]
        eff = [
            effective_weights_by_name(
                mesh_data[mi]["rows"][vi], mesh_data[mi]["slot_names"])
            for mi, vi in members
        ]
        max_full = 0.0
        max_eff = 0.0
        worst_bones = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                df = weight_delta(full[i], full[j])
                de = weight_delta(eff[i], eff[j])
                if de > max_eff:
                    max_eff = de
                    worst_bones = weight_delta_bones(eff[i], eff[j])
                max_full = max(max_full, df)
        key = node_pair_key(g)
        stat = static_by_pair.setdefault(key, {
            "groups": 0, "divergent_full": 0, "divergent_effective": 0,
            "max_full_delta": 0.0, "max_effective_delta": 0.0,
            "worst_bones": [],
        })
        stat["groups"] += 1
        if max_full > WEIGHT_DELTA_EPS:
            stat["divergent_full"] += 1
        if max_eff > WEIGHT_DELTA_EPS:
            stat["divergent_effective"] += 1
            regions = sorted({classify_bone(b) for b, _ in worst_bones}) or ["?"]
            divergent_groups.append({
                "nodes": key,
                "position": [round(float(c), 4) for c in all_points[g[0]]],
                "effective_delta": round(max_eff, 4),
                "full_delta": round(max_full, 4),
                "bones": worst_bones,
                "regions": regions,
            })
        if max_full > stat["max_full_delta"]:
            stat["max_full_delta"] = round(max_full, 4)
        if max_eff > stat["max_effective_delta"]:
            stat["max_effective_delta"] = round(max_eff, 4)
            stat["worst_bones"] = worst_bones

    print("\n=== STATIC seam-weight divergence by node pair ===")
    for key, stat in sorted(static_by_pair.items()):
        flag = "  <-- DIVERGENT" if stat["divergent_effective"] else ""
        print(f"  {key}: groups={stat['groups']} "
              f"divergent_eff={stat['divergent_effective']} "
              f"max_eff_delta={stat['max_effective_delta']} "
              f"bones={stat['worst_bones']}{flag}")

    if "--static-only" in sys.argv:
        print("\nSTATIC-ONLY MODE: skipping animation pass")
        return 0

    # ---- dynamic seam gap under every animation ---------------------------
    # merge supermodel-inherited animations exactly like the full audit
    present = {
        str(getattr(a, "name", "") or "").strip().lower()
        for a in list(getattr(model, "animations", []) or [])
    }
    chain_resref = str(getattr(reference, "supermodel", None) or "").strip()
    depth = 0
    while chain_resref and chain_resref.lower() != "null" and depth < 8:
        super_model = mgr.load_model(chain_resref, "K2")
        if super_model is None:
            break
        for anim in list(getattr(super_model, "animations", []) or []):
            key = str(getattr(anim, "name", "") or "").strip().lower()
            if key and key not in present:
                model.animations.append(anim)
                present.add(key)
        chain_resref = str(getattr(super_model, "supermodel", None) or "").strip()
        depth += 1

    # flatten groups into index arrays for fast gap evaluation
    group_members = [
        [(owner[v][0], owner[v][1]) for v in g] for g in seam_groups
    ]
    group_pair_names = [node_pair_key(g) for g in seam_groups]

    force_base_bind = "--force-base-bind" in sys.argv
    anims = list(getattr(model, "animations", []) or [])
    print(f"\ndynamic check across {len(anims)} animations...")
    per_anim = []
    for block in anims:
        anim_name = str(getattr(block, "name", "") or "?")
        length = float(getattr(block, "length", 0.0) or 0.0)
        base_palette_pose = None
        try:
            base_pose = evaluate_aurora_animation_pose(model, block, 0.0)
            base_palette_pose = _palette_pose_from_evaluated_pose(base_pose)
        except Exception:
            base_palette_pose = None
        worst = {"max_gap": 0.0, "time": 0.0, "pair": "", "p95_gap": 0.0,
                 "base_gap": 0.0, "gap_groups": 0}
        for t in _sample_times(length):
            try:
                pose = evaluate_aurora_animation_pose(model, block, float(t))
            except Exception:
                continue
            palette_pose = _palette_pose_from_evaluated_pose(pose)
            skinned_per_mesh = []
            for d in mesh_data:
                try:
                    out = _skin_vertices_with_palette(
                        uploader=d["uploader"], mesh=d["mesh"],
                        pose=palette_pose,
                        anim_base_pose=(
                            base_palette_pose
                            if (force_base_bind or d["base_bind_flag"])
                            else None
                        ),
                        verts=d["verts"], weights=d["weights"],
                        indices=d["indices"],
                    )
                except Exception:
                    out = d["verts"]
                skinned_per_mesh.append(np.asarray(out, dtype=np.float64))
            gaps = np.zeros(len(group_members))
            for gi, members in enumerate(group_members):
                pts = np.asarray([
                    skinned_per_mesh[mi][vi] for mi, vi in members
                ])
                if pts.shape[0] < 2 or not np.isfinite(pts).all():
                    continue
                gaps[gi] = float(
                    np.linalg.norm(pts - pts.mean(axis=0), axis=1).max() * 2.0
                )
            max_gap = float(gaps.max()) if gaps.size else 0.0
            is_base = t <= 0.034
            if is_base:
                worst["base_gap"] = max(worst["base_gap"], round(max_gap, 4))
            if max_gap > worst["max_gap"]:
                gi = int(gaps.argmax())
                worst.update({
                    "max_gap": round(max_gap, 4),
                    "time": round(float(t), 3),
                    "pair": group_pair_names[gi],
                    "p95_gap": round(float(np.percentile(gaps, 95)), 4) if gaps.size else 0.0,
                    "gap_groups": int((gaps > GAP_REPORT_EPS).sum()),
                })
        worst["animation"] = anim_name
        per_anim.append(worst)

    per_anim.sort(key=lambda r: r["max_gap"], reverse=True)

    # ---- outputs -----------------------------------------------------------
    suffix = "_vanilla" if vanilla_mode else ""
    out = {
        "model_name": str(getattr(model, "name", "") or ""),
        "mode": "vanilla" if vanilla_mode else "custom_split",
        "split_report": split_report,
        "skinned_nodes": [d["name"] for d in mesh_data],
        "base_bind_flags": {d["name"]: d["base_bind_flag"] for d in mesh_data},
        "coincident_groups": len(seam_groups),
        "cross_node_groups": len(cross_groups),
        "static_by_node_pair": static_by_pair,
        "divergent_groups": sorted(
            divergent_groups, key=lambda g: g["effective_delta"], reverse=True
        )[:200],
        "per_animation": per_anim,
    }
    out_dir = ROOT / "Saved"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / f"rancor_seam_divergence{suffix}.json"
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    md_lines = [
        f"# Rancor seam divergence — {'vanilla control' if vanilla_mode else 'custom split model'}",
        "",
        f"Model: `{out['model_name']}`  nodes: {', '.join(out['skinned_nodes'])}",
        f"Coincident bind groups: {len(seam_groups)} ({len(cross_groups)} cross-node)",
        "",
        "## Static weight divergence by node pair",
        "",
        "| Node pair | Groups | Divergent (effective) | Max eff Δw | Worst bones |",
        "|-----------|--------|----------------------|-----------|-------------|",
    ]
    for key, stat in sorted(static_by_pair.items()):
        md_lines.append(
            f"| {key} | {stat['groups']} | {stat['divergent_effective']} | "
            f"{stat['max_effective_delta']} | {stat['worst_bones']} |"
        )
    md_lines += [
        "",
        "## Animated seam gap per animation (worst sample)",
        "",
        "| Animation | MaxGap | p95Gap | BaseGap | Groups>1mm | Worst pair | t |",
        "|-----------|--------|--------|---------|-----------|------------|---|",
    ]
    for r in per_anim:
        md_lines.append(
            f"| {r['animation']} | {r['max_gap']} | {r['p95_gap']} | "
            f"{r['base_gap']} | {r['gap_groups']} | {r['pair']} | {r['time']} |"
        )
    md_lines.append("")
    md_path = out_dir / f"rancor_seam_divergence{suffix}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    print("\n=== worst animations by seam gap ===")
    for r in per_anim[:12]:
        print(f"  {r['animation']:14s} max_gap={r['max_gap']:8.4f} "
              f"p95={r['p95_gap']:8.4f} base={r['base_gap']:8.4f} "
              f"groups>{GAP_REPORT_EPS}={r['gap_groups']:5d} pair=[{r['pair']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
