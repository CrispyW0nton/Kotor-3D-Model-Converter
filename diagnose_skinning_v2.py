#!/usr/bin/env python3
"""
Phase-2 Deep Skinning Diagnosis Script
=======================================
For each target asset:
  1. Load model from game BIF
  2. Inspect bone hierarchy, skin nodes, bone_map, animations
  3. Capture bind-pose screenshots (front + diagonal)
  4. Set failing animation at exact timestamps
  5. Capture animated screenshots
  6. Inspect animated pose matrices — check for anomalies
  7. Compare CPU vs GPU skinning
  8. Classify root cause
  9. Export full debug bundle

Target assets: c_kraytdragon, c_rancor, c_dewback, c_gammorean, n_commf (humanoid control)
PMHA01/PFHA01: BLOCKED — player.bif not on disk.
"""

import json
import math
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.kotormcp.tools.debug_skinning import _DebugSession, _get_anim_names, _get_anim_dict

OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnosis_v2")
GAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_data", "swkotor")

# Assets to diagnose and their expected failing animations
TARGETS = [
    {"resref": "c_kraytdragon", "anims": ["cwalk", "crun"], "timestamps": [0.3, 0.5, 0.7, 0.98]},
    {"resref": "c_rancor",      "anims": ["cwalk", "crun"], "timestamps": [0.3, 0.5, 0.7]},
    {"resref": "c_dewback",     "anims": ["cwalk", "crun"], "timestamps": [0.3, 0.5, 0.7]},
    {"resref": "c_gammorean",   "anims": ["cwalk", "crun"], "timestamps": [0.3, 0.5, 0.7]},
    {"resref": "n_commf",       "anims": [],                "timestamps": []},  # humanoid control (no own anims)
]


def diagnose_asset(target: dict) -> dict:
    """Run full diagnosis on one asset. Returns a diagnosis report dict."""
    resref = target["resref"]
    out_dir = os.path.join(OUTPUT_ROOT, resref)
    os.makedirs(out_dir, exist_ok=True)

    report = {
        "resref": resref,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "load": {},
        "hierarchy": {},
        "skin_nodes": [],
        "animations_available": [],
        "bind_pose": {},
        "animated_tests": [],
        "matrix_analysis": {},
        "cpu_gpu_parity": {},
        "root_cause_classification": "UNKNOWN",
        "visual_result": "NOT_ASSESSED",
        "screenshots": [],
        "errors": [],
    }

    session = _DebugSession()
    session.launch()
    gp = session.set_game_path(GAME_DIR)
    if not gp.get("ok"):
        report["errors"].append(f"Game path failed: {gp}")
        return report

    # ── 1. Load model ──────────────────────────────────────────────────
    load_result = session.load_model(resref)
    report["load"] = load_result
    if not load_result.get("ok"):
        report["errors"].append(f"Load failed: {load_result}")
        report["root_cause_classification"] = "LOAD_FAILURE"
        return report

    print(f"  Loaded {resref}: {load_result['node_count']} nodes, "
          f"{load_result['skin_count']} skins, {load_result['bone_count']} bones, "
          f"anims={load_result.get('animations', [])}")

    # ── 2. Bone hierarchy ──────────────────────────────────────────────
    hierarchy = session.get_bone_hierarchy()
    report["hierarchy"] = {
        "total_nodes": hierarchy.get("total_nodes", 0),
        "root_name": hierarchy.get("hierarchy", {}).get("name", "?"),
    }

    # ── 3. Skin node detail ────────────────────────────────────────────
    asset_info = session.get_asset_info()
    report["skin_nodes"] = asset_info.get("skin_nodes", [])

    # ── 4. Palette remap table ─────────────────────────────────────────
    remap = session.get_palette_remap_table()
    report["palette_remap"] = {}
    remap_issues = []
    if remap.get("ok"):
        for sname, table in remap.get("remap_tables", {}).items():
            invalid_count = sum(1 for v in table.values() if not v.get("valid", True))
            report["palette_remap"][sname] = {
                "size": len(table),
                "invalid_entries": invalid_count,
            }
            if invalid_count > 0:
                remap_issues.append(f"{sname}: {invalid_count} invalid remap entries")

    # ── 5. Bind-pose screenshots ───────────────────────────────────────
    session.set_bind_pose()
    bind_pose_mats = session.get_bind_pose_matrices()
    bp_all_identity = bind_pose_mats.get("all_identity", False)
    report["bind_pose"]["all_identity"] = bp_all_identity
    report["bind_pose"]["bone_count"] = bind_pose_mats.get("bone_count", 0)

    # Check for non-identity bind pose bones
    if not bp_all_identity:
        non_ident_bones = []
        for bname, bdata in bind_pose_mats.get("matrices", {}).items():
            if not bdata.get("is_identity", True):
                non_ident_bones.append(bname)
        report["bind_pose"]["non_identity_bones"] = non_ident_bones[:10]

    for preset in ["front", "diagonal"]:
        session.set_camera(preset)
        fname = f"bindpose_{preset}.png"
        fpath = os.path.join(out_dir, fname)
        r = session.capture_viewport(width=512, height=512, output_path=fpath)
        report["screenshots"].append({
            "file": fname, "mode": "bind_pose", "camera": preset,
            "ok": r.get("ok", False), "backend": r.get("backend", "?"),
            "error": r.get("error", ""),
        })
        if r.get("ok"):
            print(f"    Screenshot: {fname} ({r.get('backend', '?')})")
        else:
            print(f"    Screenshot FAILED: {fname} — {r.get('error', '?')}")

    # ── 6. Animated tests ──────────────────────────────────────────────
    available_anims = _get_anim_names(session.model)
    report["animations_available"] = available_anims
    anim_dict = _get_anim_dict(session.model)

    test_anims = target["anims"]
    if not test_anims and available_anims:
        test_anims = available_anims[:2]  # take first 2

    for anim_name in test_anims:
        if anim_name not in anim_dict:
            report["animated_tests"].append({
                "animation": anim_name,
                "status": "NOT_FOUND",
            })
            continue

        anim = anim_dict[anim_name]
        length = getattr(anim, "length", 1.0)

        timestamps = target["timestamps"]
        if not timestamps:
            timestamps = [length * 0.3, length * 0.7]

        session.set_animation(anim_name)

        for t in timestamps:
            t_actual = min(t, length - 0.001) if t <= length else t % length
            session.set_animation_time(t_actual)

            test_entry = {
                "animation": anim_name,
                "timestamp": round(t_actual, 4),
                "length": round(length, 4),
                "screenshots": [],
                "matrix_analysis": {},
                "vertex_analysis": {},
                "cpu_gpu_comparison": {},
            }

            # Capture animated screenshots
            for preset in ["front", "diagonal"]:
                session.set_camera(preset)
                fname = f"anim_{anim_name}_t{int(t_actual*1000)}ms_{preset}.png"
                fpath = os.path.join(out_dir, fname)
                r = session.capture_viewport(width=512, height=512, output_path=fpath)
                test_entry["screenshots"].append({
                    "file": fname, "camera": preset,
                    "ok": r.get("ok", False),
                    "backend": r.get("backend", "?"),
                    "error": r.get("error", ""),
                })
                report["screenshots"].append({
                    "file": fname, "mode": "animated", "animation": anim_name,
                    "time": round(t_actual, 4), "camera": preset,
                    "ok": r.get("ok", False),
                })

            # ── Animated pose matrix analysis ──────────────────────────────
            anim_matrices = session.get_animated_pose_matrices()
            if anim_matrices.get("ok"):
                non_ident = anim_matrices.get("non_identity_count", 0)
                total = anim_matrices.get("bone_count", 0)

                # Deep matrix analysis: check for exploded translations, bad determinants
                max_translation = 0.0
                bad_det_count = 0
                huge_translation_bones = []
                for bname, bdata in anim_matrices.get("matrices", {}).items():
                    tx, ty, tz = bdata.get("translation", [0, 0, 0])
                    t_mag = math.sqrt(tx*tx + ty*ty + tz*tz)
                    max_translation = max(max_translation, t_mag)
                    if t_mag > 50.0:
                        huge_translation_bones.append({
                            "bone": bname,
                            "translation": [tx, ty, tz],
                            "magnitude": round(t_mag, 2),
                        })
                    # Check determinant (column-major matrix)
                    m = bdata.get("matrix", [])
                    if len(m) == 16:
                        # 3x3 upper-left of column-major mat4
                        det = (m[0]*(m[5]*m[10] - m[6]*m[9])
                             - m[4]*(m[1]*m[10] - m[2]*m[9])
                             + m[8]*(m[1]*m[6] - m[2]*m[5]))
                        if abs(det) < 0.01 or abs(det) > 10.0:
                            bad_det_count += 1

                test_entry["matrix_analysis"] = {
                    "total_bones": total,
                    "non_identity": non_ident,
                    "max_translation": round(max_translation, 2),
                    "huge_translation_count": len(huge_translation_bones),
                    "huge_translation_bones": huge_translation_bones[:5],
                    "bad_determinant_count": bad_det_count,
                    "pct_animated": round(100 * non_ident / max(1, total), 1),
                }

            # ── Vertex influence sampling per skin node ────────────────────
            for sn_info in report["skin_nodes"]:
                sn_name = sn_info.get("name", "?")
                vi_result = session.sample_vertex_influences(sn_name, max_samples=5)
                if vi_result.get("ok"):
                    bad_weights = 0
                    for sample in vi_result.get("samples", []):
                        ws = sample.get("weight_sum", 0)
                        if abs(ws - 1.0) > 0.01:
                            bad_weights += 1
                    test_entry["vertex_analysis"][sn_name] = {
                        "total_verts": vi_result.get("total_vertices", 0),
                        "sampled": len(vi_result.get("samples", [])),
                        "bad_weight_sums": bad_weights,
                        "sample_preview": vi_result.get("samples", [])[:2],
                    }

            # ── CPU vs GPU parity ──────────────────────────────────────────
            for sn_info in report["skin_nodes"][:1]:  # first skin node
                sn_name = sn_info.get("name", "?")
                cmp = session.compare_cpu_gpu_skinning(sn_name, max_verts=20)
                if cmp.get("ok"):
                    test_entry["cpu_gpu_comparison"] = {
                        "mesh": sn_name,
                        "max_diff": cmp.get("max_diff", 0),
                        "parity_pass": cmp.get("parity_pass", False),
                        "vertex_count": cmp.get("vertex_count", 0),
                        # Show a few vertex comparisons
                        "sample_diffs": [
                            {
                                "vi": c["vertex_index"],
                                "bind": c["bind_pos"],
                                "cpu_skinned": c["cpu_skinned_pos"],
                                "diff": c["diff"],
                            }
                            for c in cmp.get("comparisons", [])[:5]
                        ],
                    }

            report["animated_tests"].append(test_entry)

    # ── 7. Overall matrix analysis (bind vs animated) ──────────────────
    # Check if animated matrices actually differ from bind pose meaningfully
    if report["animated_tests"]:
        first_anim_test = report["animated_tests"][0]
        ma = first_anim_test.get("matrix_analysis", {})
        report["matrix_analysis"] = {
            "bind_pose_all_identity": bp_all_identity,
            "animated_non_identity_pct": ma.get("pct_animated", 0),
            "animated_max_translation": ma.get("max_translation", 0),
            "animated_huge_translations": ma.get("huge_translation_count", 0),
            "animated_bad_determinants": ma.get("bad_determinant_count", 0),
        }

    # ── 8. Root cause classification ───────────────────────────────────
    report["root_cause_classification"] = _classify_root_cause(report, remap_issues)

    # ── 9. Export full debug bundle ────────────────────────────────────
    # Only if there are animations
    if test_anims and available_anims:
        # Set to first failing animation at mid-point for bundle export
        first_anim = test_anims[0] if test_anims[0] in anim_dict else available_anims[0]
        first_length = getattr(anim_dict.get(first_anim), "length", 1.0)
        session.set_animation(first_anim)
        session.set_animation_time(first_length * 0.5)

    bundle_result = session.export_debug_bundle(out_dir)
    report["debug_bundle"] = {
        "ok": bundle_result.get("ok", False),
        "path": bundle_result.get("bundle_path", ""),
        "sections": bundle_result.get("sections", []),
        "capture_count": bundle_result.get("capture_count", 0),
    }

    # Save diagnosis report
    report_path = os.path.join(out_dir, "diagnosis_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    session.close()
    return report


def _classify_root_cause(report: dict, remap_issues: list) -> str:
    """Classify the root cause of skinning failure based on collected evidence.

    Categories:
      a) WRONG_ANIMATION_DATA — animation keyframes are corrupt/missing
      b) WRONG_SUPERMODEL — animation inheritance from supermodel broken
      c) WRONG_BONE_MAP — bone_map contract mismatch (local→palette)
      d) WRONG_MATRIX_SPACE — matrix space composition error (local vs world)
      e) WRONG_SAMPLED_POSE — pose evaluated incorrectly at runtime
      f) CORRECT_MATH_INVALID_SOURCE — math is correct but source assumptions wrong
      g) OTHER — other proven cause
      h) VISUAL_PASS — appears correct
      i) NEEDS_VISUAL_REVIEW — cannot determine without human screenshot review
    """
    ma = report.get("matrix_analysis", {})
    skin_nodes = report.get("skin_nodes", [])
    anim_tests = report.get("animated_tests", [])
    available = report.get("animations_available", [])

    # If no animations available at all
    if not available:
        return "b) WRONG_SUPERMODEL — no animations found (may need supermodel loading)"

    # Check if remap has issues
    if remap_issues:
        return f"c) WRONG_BONE_MAP — {'; '.join(remap_issues)}"

    # Check bind pose
    if not ma.get("bind_pose_all_identity", True):
        return "d) WRONG_MATRIX_SPACE — bind-pose palette not all identity"

    # Check for huge translations (exploded skeleton)
    if ma.get("animated_huge_translations", 0) > 0:
        return "d) WRONG_MATRIX_SPACE — animated bones have huge translations (>50 units)"

    # Check for bad determinants
    if ma.get("animated_bad_determinants", 0) > 5:
        return "d) WRONG_MATRIX_SPACE — many bones have bad matrix determinants"

    # If animated but low non-identity count
    if ma.get("animated_non_identity_pct", 0) < 10 and available:
        return "e) WRONG_SAMPLED_POSE — very few bones animated (<10%), pose may not be evaluated"

    # Check CPU-GPU parity
    for at in anim_tests:
        cmp = at.get("cpu_gpu_comparison", {})
        if cmp.get("max_diff", 0) > 1.0:
            return "d) WRONG_MATRIX_SPACE — CPU/GPU skinning differ significantly"

    # Check vertex weight sums
    for at in anim_tests:
        for sn, va in at.get("vertex_analysis", {}).items():
            if va.get("bad_weight_sums", 0) > 0:
                return "f) CORRECT_MATH_INVALID_SOURCE — vertex weight sums != 1.0"

    # If we got here, the math looks OK — visual review needed
    if anim_tests:
        return "i) NEEDS_VISUAL_REVIEW — math checks pass, visual coherence requires screenshot review"

    return "UNKNOWN"


def main():
    print("=" * 80)
    print("  Phase-2 Deep Skinning Diagnosis")
    print(f"  Output: {OUTPUT_ROOT}")
    print("=" * 80)

    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    all_reports = {}
    summary_matrix = []

    for target in TARGETS:
        resref = target["resref"]
        print(f"\n{'─' * 60}")
        print(f"  Diagnosing: {resref}")
        print(f"{'─' * 60}")
        try:
            report = diagnose_asset(target)
            all_reports[resref] = report

            # Summary row
            ma = report.get("matrix_analysis", {})
            row = {
                "resref": resref,
                "nodes": report["load"].get("node_count", 0),
                "skins": report["load"].get("skin_count", 0),
                "bones": report["load"].get("bone_count", 0),
                "animations": len(report.get("animations_available", [])),
                "bind_all_identity": ma.get("bind_pose_all_identity", "?"),
                "anim_non_ident_pct": ma.get("animated_non_identity_pct", 0),
                "anim_max_trans": ma.get("animated_max_translation", 0),
                "anim_huge_trans": ma.get("animated_huge_translations", 0),
                "anim_bad_det": ma.get("animated_bad_determinants", 0),
                "screenshots_ok": sum(1 for s in report.get("screenshots", []) if s.get("ok")),
                "screenshots_total": len(report.get("screenshots", [])),
                "root_cause": report.get("root_cause_classification", "?"),
            }
            summary_matrix.append(row)

            print(f"\n  Result: {row['root_cause']}")
            print(f"  Screenshots: {row['screenshots_ok']}/{row['screenshots_total']}")

        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
            all_reports[resref] = {"error": str(e)}
            summary_matrix.append({
                "resref": resref,
                "root_cause": f"SCRIPT_ERROR: {e}",
            })

    # Save overall summary
    summary_path = os.path.join(OUTPUT_ROOT, "diagnosis_summary.json")
    with open(summary_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "targets": [t["resref"] for t in TARGETS],
            "pmha01_status": "BLOCKED — player.bif not on disk",
            "pfha01_status": "BLOCKED — player.bif not on disk",
            "summary_matrix": summary_matrix,
        }, f, indent=2, default=str)

    print(f"\n{'=' * 80}")
    print("  DIAGNOSIS SUMMARY")
    print(f"{'=' * 80}")
    for row in summary_matrix:
        print(f"  {row.get('resref', '?'):20s} | "
              f"nodes={row.get('nodes', '?'):4} | "
              f"skins={row.get('skins', '?'):2} | "
              f"bind_ident={str(row.get('bind_all_identity', '?')):5} | "
              f"anim%={row.get('anim_non_ident_pct', '?'):5} | "
              f"max_t={row.get('anim_max_trans', '?'):8} | "
              f"cause={row.get('root_cause', '?')}")

    print(f"\n  Saved to: {summary_path}")
    print(f"  Per-asset bundles in: {OUTPUT_ROOT}/<resref>/")
    return summary_matrix


if __name__ == "__main__":
    main()
