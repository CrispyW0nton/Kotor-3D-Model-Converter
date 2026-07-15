"""Full per-animation deformation audit for the custom Rancor (c_rancorS).

Runs fit -> rig -> bind on the real RancorTamedConceptFinal.fbx fixture, then
skins every split mesh against sampled poses of EVERY inherited animation and
scores:

- per-vertex displacement: max, p99, p95, mean
- per-edge stretch ratio: max, p99, p95, min (collapse)
- stretched/collapsed edge fractions
- failing edge -> bone-region grouping (arms / hands / legs / torso / neck / head)
- top offending edge IDs (vertex index pairs) by stretch and displacement
- base-frame (t=0, bind) anomaly separation

Outputs under Saved/:
- rancor_deformation_audit.json   (full detail, every sample)
- rancor_deformation_audit.csv    (one row per animation, worst-case rollup)
- rancor_deformation_audit.md     (human-readable summary)

Reuses the validator's LBS internals so the skinning path matches the game.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import math

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
    _edges_from_faces,
    _skin_vertices_with_palette,
    _palette_pose_from_evaluated_pose,
    _resolve_pose_transform,
    _model_height,
    _model_diagonal,
    EDGE_STRETCH_SPIKE_RATIO,
    EDGE_COLLAPSE_RATIO,
    MAX_FAILED_EDGE_FRACTION,
)
from src.core.animation.animation_engine import evaluate_aurora_animation_pose  # noqa: E402
from src.core.animation.gpu_skinning import MAX_BONES, MatrixPaletteUploader  # noqa: E402
from src.core.geometry import model_data as md  # noqa: E402

# ---------------------------------------------------------------------------
# Rancor bone -> body-region classification
# ---------------------------------------------------------------------------
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
    return "torso"  # default unknown deform bones to torso


def classify_bones(bone_names):
    return {i: classify_bone(n) for i, n in enumerate(bone_names)}


def _sample_times(length, samples_per_animation):
    """Spread sample times, always including a near-base (t≈0) frame."""
    if length <= 0.0:
        return [0.0]
    count = max(1, int(samples_per_animation))
    inner = [length * (step + 1) / float(count + 1) for step in range(count)]
    # Always probe a small base-offset frame to catch bind anomalies.
    base_t = min(0.033, length * 0.05)
    if not any(abs(t - base_t) < 1e-4 for t in inner):
        inner = [base_t] + inner
    return inner


def _top_edges(edges, ratios, weights_uv, region_of_slot, k=8):
    """Return the k worst-stretched edges with their region + ratio."""
    import numpy as np

    if edges.shape[0] == 0:
        return []
    order = np.argsort(ratios)[::-1][:k]
    out = []
    for idx in order:
        u, v = int(edges[idx, 0]), int(edges[idx, 1])
        regions = set()
        for vert in (u, v):
            for slot, w in weights_uv.get(vert, []):
                if w > 0.15:
                    regions.add(region_of_slot.get(slot, "torso"))
        out.append({
            "edge": [u, v],
            "ratio": round(float(ratios[idx]), 3),
            "regions": sorted(regions) or ["unknown"],
        })
    return out


def audit_model(model, *, samples_per_animation=5, use_base_bind=True,
                force_base_bind=False):
    import numpy as np

    height = _model_height(model)
    diagonal = _model_diagonal(model)
    model_scale = max(height, diagonal * 0.6)
    displacement_bound = max(1.0, model_scale * 1.5)
    edge_stretch_absolute = max(0.25, model_scale * 0.25)

    name_lookup = {
        str(getattr(n, "name", "") or "").strip().lower():
            str(getattr(n, "name", "") or "")
        for n in model.all_nodes()
    }

    # Collect skinned split meshes.
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

    mesh_data = []
    for mesh in skinned:
        verts = np.asarray(
            [tuple(float(c) for c in vx[:3]) for vx in mesh.vertices],
            dtype=np.float64,
        )
        slot_names = [str(n or "").strip() for n in list(mesh.bone_map)]
        slot_count = len(slot_names)
        region_of_slot = classify_bones(slot_names)
        weights, indices = _skin_rows_to_arrays(
            list(mesh.skin_data), verts.shape[0], slot_count,
        )
        uploader = MatrixPaletteUploader(max_bones=max(int(MAX_BONES), slot_count))
        uploader.build_inverse_bind_pose(model)
        edges = _edges_from_faces(list(getattr(mesh, "faces", []) or []), verts.shape[0])
        bind_edge_len = (
            np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]], axis=1)
            if edges.shape[0] else np.zeros(0)
        )
        # vertex -> [(slot_index, weight)] for region attribution
        weights_uv = {}
        for vi in range(min(weights.shape[0], verts.shape[0])):
            pairs = []
            for slot in range(weights.shape[1]):
                w = float(weights[vi, slot])
                if w > 1e-6:
                    pairs.append((int(indices[vi, slot]), w))
            weights_uv[vi] = pairs
        mesh_data.append({
            "mesh": mesh,
            "verts": verts,
            "slot_names": slot_names,
            "region_of_slot": region_of_slot,
            "weights": weights,
            "indices": indices,
            "weights_uv": weights_uv,
            "edges": edges,
            "bind_edge_len": bind_edge_len,
            "uploader": uploader,
        })

    anim_blocks = list(getattr(model, "animations", []) or [])
    samples = []
    for block in anim_blocks:
        anim_name = str(getattr(block, "name", "") or "?")
        length = float(getattr(block, "length", 0.0) or 0.0)
        times = _sample_times(length, samples_per_animation)
        base_palette_pose = None
        if use_base_bind:
            try:
                base_pose = evaluate_aurora_animation_pose(model, block, 0.0)
                base_palette_pose = _palette_pose_from_evaluated_pose(base_pose)
            except Exception:
                base_palette_pose = None
        for t in times:
            rec = {
                "animation": anim_name, "time": round(float(t), 4),
                "length": round(length, 4),
            }
            try:
                pose = evaluate_aurora_animation_pose(model, block, float(t))
            except Exception as exc:
                rec["failures"] = ["pose_evaluation_failed"]
                rec["error"] = str(exc)[:200]
                samples.append(rec)
                continue
            palette_pose = _palette_pose_from_evaluated_pose(pose)

            all_disp = []
            all_ratios = []
            top_edges_sample = []
            region_fail_counts = {r: 0 for r, _ in _REGION_RULES}
            region_fail_counts["unknown"] = 0
            total_fail_edges = 0
            total_edges = 0
            missing = set()

            for data in mesh_data:
                slot_names = data["slot_names"]
                for bone_name in slot_names:
                    if _resolve_pose_transform(pose, bone_name, name_lookup) is None:
                        missing.add(bone_name)
                try:
                    deformed = _skin_vertices_with_palette(
                        uploader=data["uploader"], mesh=data["mesh"],
                        pose=palette_pose,
                        anim_base_pose=(
                            base_palette_pose
                            if (use_base_bind and (force_base_bind or bool(getattr(
                                data["mesh"],
                                "_gr_use_animation_base_bind_for_preview",
                                False,
                            ))))
                            else None
                        ),
                        verts=data["verts"], weights=data["weights"],
                        indices=data["indices"],
                    )
                except Exception:
                    deformed = data["verts"]
                finite = np.isfinite(deformed).all(axis=1)
                non_finite = int((~finite).sum())
                safe = np.where(finite[:, None], deformed, data["verts"])
                disp = np.linalg.norm(safe - data["verts"], axis=1)
                all_disp.append(disp)
                edges = data["edges"]
                if edges.shape[0]:
                    dlen = np.linalg.norm(safe[edges[:, 0]] - safe[edges[:, 1]], axis=1)
                    blen = data["bind_edge_len"]
                    valid = blen > 1e-9
                    ratio = np.ones_like(dlen)
                    ratio[valid] = dlen[valid] / blen[valid]
                    all_ratios.append(ratio)
                    total_edges += edges.shape[0]
                    stretch_delta = dlen - blen
                    fail_mask = (ratio > EDGE_STRETCH_SPIKE_RATIO) & (stretch_delta > edge_stretch_absolute)
                    collapse_mask = ratio < EDGE_COLLAPSE_RATIO
                    bad = fail_mask | collapse_mask
                    total_fail_edges += int(bad.sum())
                    for ei in np.where(bad)[0]:
                        u, v = int(edges[ei, 0]), int(edges[ei, 1])
                        regs = set()
                        for vert in (u, v):
                            for slot, w in data["weights_uv"].get(vert, []):
                                if w > 0.15:
                                    regs.add(data["region_of_slot"].get(slot, "torso"))
                        for r in (regs or {"unknown"}):
                            region_fail_counts[r] = region_fail_counts.get(r, 0) + 1
                    mesh_top = _top_edges(
                        edges, ratio, data["weights_uv"],
                        data["region_of_slot"], k=5,
                    )
                    mesh_name = str(getattr(data["mesh"], "name", "") or "?")
                    for te in mesh_top:
                        te["mesh"] = mesh_name
                    top_edges_sample.extend(mesh_top)
                rec["non_finite"] = rec.get("non_finite", 0) + non_finite

            disp_arr = np.concatenate(all_disp) if all_disp else np.zeros(0)
            ratio_arr = np.concatenate(all_ratios) if all_ratios else np.zeros(0)
            rec.update({
                "max_disp": round(float(disp_arr.max()), 4) if disp_arr.size else 0.0,
                "p99_disp": round(float(np.percentile(disp_arr, 99)), 4) if disp_arr.size else 0.0,
                "p95_disp": round(float(np.percentile(disp_arr, 95)), 4) if disp_arr.size else 0.0,
                "mean_disp": round(float(disp_arr.mean()), 4) if disp_arr.size else 0.0,
                "displacement_bound": round(displacement_bound, 4),
                "max_edge_stretch": round(float(ratio_arr.max()), 3) if ratio_arr.size else 1.0,
                "p99_edge_stretch": round(float(np.percentile(ratio_arr, 99)), 3) if ratio_arr.size else 1.0,
                "p95_edge_stretch": round(float(np.percentile(ratio_arr, 95)), 3) if ratio_arr.size else 1.0,
                "min_edge_ratio": round(float(ratio_arr.min()), 3) if ratio_arr.size else 1.0,
                "failed_edge_count": total_fail_edges,
                "total_edge_count": total_edges,
                "failed_edge_fraction": round(total_fail_edges / max(1, total_edges), 5),
                "region_fail_counts": region_fail_counts,
                "missing_bones": sorted(missing),
                "top_edges": sorted(
                    top_edges_sample, key=lambda e: e["ratio"], reverse=True,
                )[:8],
            })
            failures = []
            if rec.get("non_finite"):
                failures.append("non_finite_vertices")
            if missing:
                failures.append("missing_bone_transforms")
            if rec["max_disp"] > displacement_bound:
                failures.append("exploded_vertices")
            if rec["failed_edge_fraction"] > MAX_FAILED_EDGE_FRACTION:
                failures.append("edge_stretch_spike")
            rec["failures"] = failures
            samples.append(rec)
    return {
        "model_name": str(getattr(model, "name", "") or ""),
        "model_height": round(height, 4),
        "model_diagonal": round(diagonal, 4),
        "displacement_bound": round(displacement_bound, 4),
        "samples": samples,
    }


def main() -> int:
    vanilla_mode = "--vanilla" in sys.argv
    engine_truth = "--engine-truth" in sys.argv or vanilla_mode
    if not vanilla_mode and not FBX.exists():
        print(f"MISSING FBX: {FBX}")
        return 2
    mgr = ResourceManager()
    assert mgr.set_k2_dir(K2), "K2 index failed"
    reference = mgr.load_model("c_rancors", "K2") or mgr.load_model("c_rancor", "K2")
    assert reference is not None, "could not load c_rancorS reference"

    if vanilla_mode:
        # Ground-truth control: audit the VANILLA donor model unchanged.
        model = reference
        print("VANILLA CONTROL MODE: auditing stock c_rancorS")
    else:
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
        # The game runs the SPLIT model (Character Builder Node Splitter),
        # so the audit must include it; the pre-T2526 audits measured the
        # unsplit mesh and missed every split-seam failure. --no-split keeps
        # the old behavior for comparison.
        if "--no-split" not in sys.argv:
            split_result = wf.split_skinned_mesh_nodes_with_weight_remap(
                model, reference
            )
            if not split_result.get("ok"):
                print("SPLIT FAILED:", split_result.get("code"),
                      split_result.get("message"))
                return 1
            print(f"split: {split_result.get('code')} -> "
                  f"{split_result.get('split_nodes')} region nodes; "
                  f"seam_weld={split_result.get('seam_weld')}")
    print(f"rigged model: {getattr(model, 'name', '?')}, "
          f"animations={len(list(getattr(model, 'animations', []) or []))}")

    # --- Merge supermodel-inherited animations (c_rancors -> c_rancor ...) ---
    # The rigged model only carries the donor's OWN animations; the game
    # resolves the rest through the supermodel chain. Walk the chain and
    # append any animation name not already present (closer model wins).
    present = {
        str(getattr(a, "name", "") or "").strip().lower()
        for a in list(getattr(model, "animations", []) or [])
    }
    chain_resref = str(getattr(reference, "supermodel", None) or "").strip()
    merged_from = []
    depth = 0
    while chain_resref and chain_resref.lower() != "null" and depth < 8:
        super_model = mgr.load_model(chain_resref, "K2")
        if super_model is None:
            print(f"WARNING: supermodel '{chain_resref}' not found; chain stops")
            break
        added = 0
        for anim in list(getattr(super_model, "animations", []) or []):
            key = str(getattr(anim, "name", "") or "").strip().lower()
            if key and key not in present:
                model.animations.append(anim)
                present.add(key)
                added += 1
        merged_from.append((chain_resref, added))
        chain_resref = str(getattr(super_model, "supermodel", None) or "").strip()
        depth += 1
    for resref, added in merged_from:
        print(f"merged {added} inherited animations from supermodel '{resref}'")
    print(f"total animations for audit: "
          f"{len(list(getattr(model, 'animations', []) or []))}")

    if "--no-base-bind" in sys.argv:
        # T2532 probe: audit with the animation-base-bind preview path OFF
        # (hierarchy bind fallback), regardless of per-mesh flags.
        for node in model.all_nodes():
            if getattr(node, "_gr_use_animation_base_bind_for_preview", False):
                setattr(node, "_gr_use_animation_base_bind_for_preview", False)
        print("BASE-BIND DISABLED for all meshes (--no-base-bind)")

    result = audit_model(
        model, samples_per_animation=5,
        force_base_bind=("--force-base-bind" in sys.argv),
    )

    # Roll up per-animation worst case.
    by_anim = {}
    for s in result["samples"]:
        a = s["animation"]
        cur = by_anim.get(a)
        if cur is None or s.get("max_edge_stretch", 0) > cur.get("max_edge_stretch", 0):
            by_anim[a] = s
    per_anim = sorted(by_anim.values(), key=lambda r: r.get("max_edge_stretch", 0), reverse=True)

    out_dir = ROOT / "Saved"
    out_dir.mkdir(exist_ok=True)
    suffix = "_vanilla" if vanilla_mode else ""
    json_path = out_dir / f"rancor_deformation_audit{suffix}.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    csv_path = out_dir / f"rancor_deformation_audit{suffix}.csv"
    fields = ["animation", "frames", "max_edge_stretch", "p95_edge_stretch",
              "p99_edge_stretch", "min_edge_ratio", "max_disp", "p95_disp", "p99_disp",
              "failed_edge_fraction", "arms", "hands", "legs", "torso", "neck", "head",
              "failures"]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in per_anim:
            rc = r.get("region_fail_counts", {})
            w.writerow({
                "animation": r["animation"],
                "frames": r.get("length", 0),
                "max_edge_stretch": r.get("max_edge_stretch", 0),
                "p95_edge_stretch": r.get("p95_edge_stretch", 0),
                "p99_edge_stretch": r.get("p99_edge_stretch", 0),
                "min_edge_ratio": r.get("min_edge_ratio", 1),
                "max_disp": r.get("max_disp", 0),
                "p95_disp": r.get("p95_disp", 0),
                "p99_disp": r.get("p99_disp", 0),
                "failed_edge_fraction": r.get("failed_edge_fraction", 0),
                "arms": rc.get("arms", 0), "hands": rc.get("hands", 0),
                "legs": rc.get("legs", 0), "torso": rc.get("torso", 0),
                "neck": rc.get("neck", 0), "head": rc.get("head", 0),
                "failures": ";".join(r.get("failures", [])),
            })

    # Markdown summary
    md_lines = [
        "# Rancor (c_rancorS) Full Animation Deformation Audit",
        "",
        f"Model: `{result['model_name']}`  height={result['model_height']}  "
        f"diagonal={result['model_diagonal']}  disp_bound={result['displacement_bound']}",
        "",
        "Worst-case rollup per animation (sorted by max edge stretch):",
        "",
        "| Animation | Frames | MaxStretch | p95 | p99 | MinRatio | MaxDisp | "
        "p95 Disp | %Fail | Arms | Hands | Legs | Torso | Neck | Head | Fail |",
        "|-----------|--------|-----------|-----|-----|---------|---------|"
        "---------|-------|------|-------|------|-------|------|------|------|",
    ]
    for r in per_anim:
        rc = r.get("region_fail_counts", {})
        md_lines.append(
            f"| {r['animation']} | {r.get('length',0)} | {r.get('max_edge_stretch',0)} | "
            f"{r.get('p95_edge_stretch',0)} | {r.get('p99_edge_stretch',0)} | "
            f"{r.get('min_edge_ratio',1)} | {r.get('max_disp',0)} | "
            f"{r.get('p95_disp',0)} | {r.get('failed_edge_fraction',0)} | "
            f"{rc.get('arms',0)} | {rc.get('hands',0)} | {rc.get('legs',0)} | "
            f"{rc.get('torso',0)} | {rc.get('neck',0)} | {rc.get('head',0)} | "
            f"{';'.join(r.get('failures',[]))} |"
        )
    md_lines.append("")
    out_dir.joinpath(f"rancor_deformation_audit{suffix}.md").write_text(
        "\n".join(md_lines), encoding="utf-8")

    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")
    n_fail = sum(1 for s in result["samples"] if s.get("failures"))
    print(f"\nSamples: {len(result['samples'])}, failing: {n_fail}")
    print("\n=== worst animations by max edge stretch ===")
    for r in per_anim[:12]:
        rc = r.get("region_fail_counts", {})
        print(f"  {r['animation']:14s} stretch={r.get('max_edge_stretch',0):6.2f} "
              f"p95={r.get('p95_edge_stretch',0):5.2f} disp={r.get('max_disp',0):6.2f} "
              f"%fail={r.get('failed_edge_fraction',0):.4f} "
              f"arms={rc.get('arms',0)} hands={rc.get('hands',0)} legs={rc.get('legs',0)} "
              f"torso={rc.get('torso',0)} [{';'.join(r.get('failures',[]))}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
