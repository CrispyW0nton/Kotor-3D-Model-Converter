#!/usr/bin/env python3
"""
Deep Model Audit v6.1 — GhostRigger-K1-K2
==========================================
Exhaustive per-model check with correct data structure access:
  - skin_data = List[VertexSkinData], each has .influences=[BoneWeight(bone_index,weight)]
  - animations[i].nodes = List[ModelNode], controllers = List[dict(type,name,times,values)]
  - model.all_nodes() / n.is_mesh / n.is_skin
"""

import sys, os, math, json, struct, logging, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)

from src.core.mdl_parser  import MDLBinaryParser, NodeFlags
from src.core.model_data  import KotorModel, ModelNode, VertexSkinData, BoneWeight
from src.autorig.accurig  import AcuRig, ProfileDetector
from src.autorig.grig     import GRig, BonePin
from src.converters.mesh_converter import OBJExporter, OBJImporter

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MDL_DIR  = os.path.join(REPO, "test_assets", "k1_extracted", "models")
TEX_DIR  = os.path.join(REPO, "test_assets", "k1_extracted", "textures")
SITH_MDL = os.path.join(REPO, "test_assets", "N_sithpraet.mdl")
SITH_TEX = os.path.join(REPO, "test_assets")
OUT_DIR  = os.path.join(REPO, "audit_output")
os.makedirs(OUT_DIR, exist_ok=True)

MODEL_FILES = sorted([
    os.path.join(MDL_DIR, f) for f in os.listdir(MDL_DIR) if f.endswith('.mdl')
])
if os.path.exists(SITH_MDL):
    MODEL_FILES.append(SITH_MDL)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _mesh_nodes(model: KotorModel):
    return model.mesh_nodes()


def _uv_coverage(node: ModelNode) -> float:
    """
    Compute UV utilization: fraction of vertices that have non-degenerate
    (u,v) coordinates in [0,1] range.  KotOR UVs are typically in 0..1
    but may tile; we check that UVs are present and non-zero.
    Returns a value in [0, 1] where 1.0 = all vertices have UVs.
    """
    if not node.uvs or not node.vertices:
        return 0.0
    # Count UVs that are non-zero (i.e. actually assigned)
    non_zero = sum(1 for (u, v) in node.uvs if abs(u) > 1e-9 or abs(v) > 1e-9)
    return non_zero / max(len(node.vertices), 1)


def _try_load_texture(name: str, search_dirs):
    """Load texture by name; falls back TGA→TPC and TPC-in-TGA."""
    if not HAS_PIL:
        return None, "no_pil"
    name = name.strip()
    if not name:
        return None, "no_name"
    for d in search_dirs:
        for ext in ('.tga', '.TGA', '.tpc', '.TPC', '.png', '.PNG', '.dds'):
            fp = os.path.join(d, name + ext)
            if not os.path.exists(fp):
                continue
            # 1) Try PIL
            try:
                img = Image.open(fp)
                img.load()
                return img, "pil_ok"
            except Exception:
                pass
            # 2) TPC-in-TGA
            try:
                with open(fp, 'rb') as fh:
                    raw = fh.read()
                from src.gui.viewport import _is_tpc_data, _load_tpc_bytes
                if _is_tpc_data(raw):
                    img2 = _load_tpc_bytes(raw)
                    if img2:
                        return img2, "tpc_in_tga"
            except Exception:
                pass
            # 3) Sibling .tpc file
            sibling = os.path.splitext(fp)[0] + '.tpc'
            if os.path.exists(sibling) and sibling != fp:
                try:
                    with open(sibling, 'rb') as fh:
                        raw = fh.read()
                    from src.gui.viewport import _load_tpc_bytes
                    img3 = _load_tpc_bytes(raw)
                    if img3:
                        return img3, "tpc_fallback"
                except Exception:
                    pass
            return None, f"load_fail:{os.path.basename(fp)}"
    return None, "not_found"


def _validate_weights(node: ModelNode):
    """
    Returns (issues_list, weighted_vert_count, total_vert_count).
    skin_data is List[VertexSkinData]; each has .influences=[BoneWeight(bone_index,weight)].
    """
    issues = []
    if not node.skin_data:
        return issues, 0, len(node.vertices) if node.vertices else 0

    total = len(node.vertices) if node.vertices else 0
    weighted = 0

    for vi, vsd in enumerate(node.skin_data):
        if not isinstance(vsd, VertexSkinData):
            continue
        active = [bw for bw in vsd.influences if bw.weight > 1e-6]
        if not active:
            continue
        weighted += 1
        s = sum(bw.weight for bw in active)
        if abs(s - 1.0) > 0.02:
            issues.append(f"v{vi}: sum={s:.3f}")
        if len(active) > 4:
            issues.append(f"v{vi}: {len(active)} influences")
        for bw in active:
            if math.isnan(bw.weight):
                issues.append(f"v{vi}: NaN weight bone={bw.bone_index}")

    return issues, weighted, total


def _validate_animations(model: KotorModel):
    """
    Returns (issues_list, total_keys_checked).
    animations[i].nodes is List[ModelNode];
    each node.controllers is List[dict] with 'times' and 'values'.
    """
    issues = []
    total_keys = 0
    for anim in model.animations:
        for nd in (anim.nodes or []):
            for ctrl in (nd.controllers or []):
                if not isinstance(ctrl, dict):
                    continue
                values = ctrl.get('values', [])
                for row in values:
                    row_iter = row if hasattr(row, '__iter__') else [row]
                    for val in row_iter:
                        try:
                            fv = float(val)
                            total_keys += 1
                            if math.isnan(fv) or math.isinf(fv):
                                issues.append(
                                    f"anim={anim.name} node={nd.name} "
                                    f"ctrl={ctrl.get('name','')} NaN/Inf"
                                )
                        except (TypeError, ValueError):
                            pass
    return issues, total_keys


def _model_bounds(model: KotorModel, skin_only: bool = True):
    """
    Compute model bounding box.
    skin_only=True: use only skin-mesh vertices (rendered geometry).
    """
    all_v = []
    for n in _mesh_nodes(model):
        if not n.vertices:
            continue
        if skin_only and not n.is_skin:
            # Skip bone-proxy nodes (no UVs, not skinned)
            if not (n.uvs and len(n.uvs) > 0):
                continue
        all_v.extend(n.vertices)
    if not all_v:
        # Fallback: all mesh nodes
        for n in _mesh_nodes(model):
            if n.vertices:
                all_v.extend(n.vertices)
    if not all_v:
        return None
    xs = [v[0] for v in all_v]
    ys = [v[1] for v in all_v]
    zs = [v[2] for v in all_v]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _check_and_fix_grig_pins(grig: GRig, model: KotorModel):
    """
    Check all GRig bone pins are within model bounds (+tolerance).
    Uses skin-mesh bounds (rendered geometry only) to avoid bone-proxy inflation.
    Auto-fix out-of-bounds pins by snapping to nearest mesh vertex.
    Returns (out_of_bounds_names, fixed_count, total_pin_count).
    """
    bounds = _model_bounds(model, skin_only=True)
    if bounds is None:
        return [], 0, len(grig._pins)

    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    tol = 0.35  # 35 cm tolerance
    cx, dx = (xmin+xmax)/2, (xmax-xmin)/2 + tol
    cy, dy = (ymin+ymax)/2, (ymax-ymin)/2 + tol
    cz, dz = (zmin+zmax)/2, (zmax-zmin)/2 + tol

    # Collect mesh vertices for snapping
    all_v = []
    for n in _mesh_nodes(model):
        if n.vertices:
            all_v.extend(n.vertices)

    oob = []
    fixed = 0
    for pin in list(grig._pins.values()):
        px, py, pz = pin.position
        if abs(px-cx) > dx or abs(py-cy) > dy or abs(pz-cz) > dz:
            oob.append(pin.name)
            if all_v and not pin.locked:
                # Snap to nearest vertex
                best_d = float('inf')
                best_v = pin.position
                for v in all_v:
                    d = (v[0]-px)**2 + (v[1]-py)**2 + (v[2]-pz)**2
                    if d < best_d:
                        best_d = d
                        best_v = v
                pin.position = best_v  # direct set (bypass lock check)
                fixed += 1

    return oob, fixed, len(grig._pins)


def _obj_roundtrip(model: KotorModel, name: str):
    """OBJ export → re-import; returns list of issue strings."""
    out_path = os.path.join(OUT_DIR, f"{name}_rt.obj")
    issues = []
    try:
        exp = OBJExporter()
        exp.export(model, out_path)
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 20:
            return ["obj_empty"]
        imp = OBJImporter()
        m2 = imp.import_file(out_path)
        orig_v = sum(len(n.vertices) for n in _mesh_nodes(model) if n.vertices)
        rt_v   = sum(len(n.vertices) for n in _mesh_nodes(m2)    if n.vertices)
        if orig_v == 0:
            return ["no_orig_verts"]
        ratio = rt_v / orig_v
        if ratio < 0.80:
            issues.append(f"verts_ratio={ratio:.0%} ({rt_v}/{orig_v})")
    except Exception as e:
        issues.append(f"exception: {e}")
    return issues


# ─── Checklist items ─────────────────────────────────────────────────────────

CHECKLIST = [
    "parse_ok",           # 1 MDL parsed without exception
    "mesh_complete",      # 2 has vertices and faces
    "normals_ok",         # 3 mesh nodes have normals
    "uvs_adequate",       # 4 average UV coverage ≥ 20%
    "textures_loaded",    # 5 all referenced textures can load
    "textures_pow2",      # 6 all textures are power-of-two
    "weights_valid",      # 7 per-vertex weights sum to 1 ± 2%, ≤4 influences
    "weights_full",       # 8 ≥95% of skinnable verts are weighted
    "anims_valid",        # 9 no NaN/Inf in animation keys
    "grig_ok",            #10 GRig pipeline runs without exception
    "grig_bounds_ok",     #11 all bone pins inside mesh bounds
    "obj_roundtrip_ok",   #12 OBJ export+import preserves ≥80% verts
]

# ─── Per-model audit ──────────────────────────────────────────────────────────

def audit_model(mdl_path: str) -> dict:
    name = os.path.splitext(os.path.basename(mdl_path))[0]
    tex_dirs = [TEX_DIR]
    # For sith praetorian (lives outside k1_extracted)
    mdl_dir = os.path.dirname(mdl_path)
    if mdl_dir not in tex_dirs:
        tex_dirs.append(mdl_dir)

    r = {
        "name":     name,
        "checks":   {k: None for k in CHECKLIST},
        "metrics":  {},
        "issues":   [],
        "warnings": [],
        "score":    0.0,
        "status":   "UNKNOWN",
    }

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    try:
        model = MDLBinaryParser.parse_files(mdl_path)
        r["checks"]["parse_ok"] = True
        r["metrics"]["classification"] = model.classification
    except Exception as e:
        r["checks"]["parse_ok"] = False
        r["issues"].append(f"parse: {e}")
        _set_score(r)
        return r

    # ── 2. Mesh completeness ──────────────────────────────────────────────────
    meshes = _mesh_nodes(model)
    total_v = sum(len(n.vertices) for n in meshes if n.vertices)
    total_f = sum(len(n.faces) for n in meshes if hasattr(n,'faces') and n.faces)
    r["metrics"]["mesh_nodes"]  = len(meshes)
    r["metrics"]["total_verts"] = total_v
    r["metrics"]["total_faces"] = total_f
    r["checks"]["mesh_complete"] = (total_v > 0 and total_f > 0)
    if not r["checks"]["mesh_complete"]:
        r["issues"].append(f"mesh: {total_v}v {total_f}f")

    # ── 3. Normals ────────────────────────────────────────────────────────────
    # Only check normals on *rendered* mesh nodes (those with UVs/texture).
    # Bone-proxy nodes (MESH, no UV, no SKIN) are internal helpers – KotOR
    # never renders them so missing normals on those is expected/OK.
    rendered_nodes_missing_normals = [
        n.name for n in meshes
        if n.vertices
        and (n.is_skin or (n.uvs and len(n.uvs) > 0))  # rendered node
        and (not n.normals or len(n.normals) != len(n.vertices))
    ]
    all_nodes_missing = [
        n.name for n in meshes
        if n.vertices and (not n.normals or len(n.normals) != len(n.vertices))
    ]
    r["metrics"]["nodes_missing_normals"] = all_nodes_missing
    r["metrics"]["rendered_missing_normals"] = rendered_nodes_missing_normals
    r["checks"]["normals_ok"] = (len(rendered_nodes_missing_normals) == 0)
    if rendered_nodes_missing_normals:
        r["warnings"].append(f"rendered_missing_normals: {rendered_nodes_missing_normals[:4]}")
    elif all_nodes_missing:
        r["warnings"].append(f"bone_proxy_missing_normals(ok): {all_nodes_missing[:3]}")

    # ── 4. UV coverage ────────────────────────────────────────────────────────
    uv_covs = []
    uv_low  = []
    # Only include rendered nodes (skin or has UVs) for UV metric
    uv_nodes = [n for n in meshes if n.is_skin or (n.uvs and len(n.uvs) > 0)]
    for n in uv_nodes:
        cov = _uv_coverage(n)
        uv_covs.append(cov)
        if cov < 0.30 and n.vertices and len(n.vertices) > 20:
            uv_low.append(f"{n.name}:{cov:.1%}")
    avg_uv = sum(uv_covs) / max(len(uv_covs), 1)
    r["metrics"]["uv_avg"]       = round(avg_uv, 4)
    r["metrics"]["uv_low"]       = uv_low
    r["metrics"]["uv_node_count"] = len(uv_nodes)
    # KotOR: rendered mesh nodes should have ≥90% of vertices UV-mapped
    r["checks"]["uvs_adequate"] = (avg_uv >= 0.90 or len(uv_nodes) == 0)
    if uv_low:
        r["warnings"].extend(uv_low[:4])

    # ── 5+6. Textures ─────────────────────────────────────────────────────────
    tex_names = set()
    for n in meshes:
        for attr in ("texture", "texture2", "lightmap"):
            t = (getattr(n, attr, "") or "").strip().lower()
            if t and not t.startswith("null"):
                tex_names.add(t)

    tex_ok_count = 0
    pow2_ok      = True
    for tn in tex_names:
        img, status = _try_load_texture(tn, tex_dirs)
        if img is None:
            r["warnings"].append(f"tex_missing:{tn} ({status})")
        else:
            tex_ok_count += 1
            w, h = img.size
            if not (_is_pow2(w) and _is_pow2(h)):
                pow2_ok = False
                r["warnings"].append(f"tex_npot:{tn} {w}x{h}")

    r["metrics"]["textures_total"]  = len(tex_names)
    r["metrics"]["textures_loaded"] = tex_ok_count
    r["checks"]["textures_loaded"]  = (tex_ok_count == len(tex_names)) or (not tex_names)
    r["checks"]["textures_pow2"]    = pow2_ok

    # ── 7+8. Skin weights ─────────────────────────────────────────────────────
    skin_nodes = [n for n in meshes if n.is_skin and n.skin_data]
    all_w_issues  = []
    total_weighted = 0
    total_skinnable = 0

    for sn in skin_nodes:
        wi, wv, tv = _validate_weights(sn)
        all_w_issues.extend(wi[:5])
        total_weighted  += wv
        total_skinnable += tv

    wt_pct = total_weighted / max(total_skinnable, 1)
    r["metrics"]["skin_nodes"]       = len(skin_nodes)
    r["metrics"]["weighted_verts"]   = total_weighted
    r["metrics"]["skinnable_verts"]  = total_skinnable
    r["metrics"]["weight_coverage"]  = round(wt_pct, 4)
    r["checks"]["weights_valid"] = (len(all_w_issues) == 0)
    r["checks"]["weights_full"]  = (wt_pct >= 0.95 or total_skinnable == 0)
    if all_w_issues:
        r["warnings"].extend(all_w_issues[:5])

    # ── 9. Animations ─────────────────────────────────────────────────────────
    anim_issues, anim_keys = _validate_animations(model)
    r["metrics"]["anim_count"] = len(model.animations)
    r["metrics"]["anim_keys"]  = anim_keys
    r["checks"]["anims_valid"] = (len(anim_issues) == 0)
    if anim_issues:
        r["warnings"].extend(anim_issues[:4])

    # ── 10+11. GRig ───────────────────────────────────────────────────────────
    try:
        gr = GRig()
        gr.rig_model_full(model)
        oob, fixed, total_pins = _check_and_fix_grig_pins(gr, model)

        r["metrics"]["grig_pins_total"] = total_pins
        r["metrics"]["grig_pins_oob"]   = len(oob)
        r["metrics"]["grig_pins_fixed"] = fixed
        r["checks"]["grig_ok"]          = True
        r["checks"]["grig_bounds_ok"]   = (len(oob) == 0)

        if oob:
            r["warnings"].append(f"pins_oob:{oob[:5]} fixed={fixed}")
            if fixed > 0:
                # Re-apply weights with corrected pins
                gr.apply_weights(model, smooth_iterations=1)
    except Exception as e:
        r["checks"]["grig_ok"]        = False
        r["checks"]["grig_bounds_ok"] = False
        r["issues"].append(f"grig: {e}")

    # ── 12. OBJ round-trip ────────────────────────────────────────────────────
    rt_issues = _obj_roundtrip(model, name)
    r["metrics"]["obj_rt"] = rt_issues
    r["checks"]["obj_roundtrip_ok"] = (len(rt_issues) == 0)
    if rt_issues:
        r["warnings"].extend(rt_issues)

    _set_score(r)
    return r


def _set_score(r: dict):
    checks = r["checks"]
    n_checks = len(CHECKLIST)
    passed = sum(1 for v in checks.values() if v is True)
    r["score"]  = round(passed / n_checks * 100.0, 1)
    if r["score"] == 100.0:
        r["status"] = "PASS"
    elif r["score"] >= 75.0:
        r["status"] = "WARN"
    else:
        r["status"] = "FAIL"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 76)
    print("  GhostRigger-K1-K2  Deep Model Audit v6.1  —  2026-03-06")
    print(f"  {len(MODEL_FILES)} models  |  12 checks per model")
    print("=" * 76)

    results = []
    t0 = time.time()

    for i, mdl_path in enumerate(MODEL_FILES):
        name = os.path.splitext(os.path.basename(mdl_path))[0]
        print(f"\n[{i+1:02d}/{len(MODEL_FILES)}] {name}", flush=True)
        try:
            r = audit_model(mdl_path)
        except Exception as e:
            r = {
                "name": name, "checks": {k: False for k in CHECKLIST},
                "metrics": {}, "issues": [str(e)],
                "warnings": [], "score": 0.0, "status": "FAIL",
            }
            traceback.print_exc()
        results.append(r)

        m = r["metrics"]
        sym = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[r["status"]]
        print(f"  {sym} {r['status']:4s}  score={r['score']:.1f}%  "
              f"v={m.get('total_verts',0)}  f={m.get('total_faces',0)}  "
              f"uv={m.get('uv_avg',0):.1%}  "
              f"wt={m.get('weight_coverage',0):.1%}  "
              f"anims={m.get('anim_count',0)}")

        fail_checks = [k for k, v in r["checks"].items() if v is False]
        if fail_checks:
            print(f"  ✗ {', '.join(fail_checks)}")
        for iss in r["issues"][:3]:
            print(f"  !! {iss}")
        for w in r["warnings"][:3]:
            print(f"  ~  {w}")

    elapsed = time.time() - t0

    # ── Summary table ─────────────────────────────────────────────────────────
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_warn = sum(1 for r in results if r["status"] == "WARN")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    avg    = sum(r["score"] for r in results) / len(results)

    print("\n" + "=" * 76)
    print("  SUMMARY")
    print("=" * 76)
    print(f"  {'MODEL':<22} {'ST':4}  {'SCORE':>6}  {'VERTS':>7}  {'UV%':>5}  {'WT%':>5}  {'ANM':>3}")
    print(f"  {'-'*22} {'-'*4}  {'-'*6}  {'-'*7}  {'-'*5}  {'-'*5}  {'-'*3}")
    for r in results:
        m = r["metrics"]
        sym = {"PASS":"✅","WARN":"⚠️","FAIL":"❌"}[r["status"]]
        print(f"  {r['name']:<22} {r['status']:4}  {r['score']:>6.1f}  "
              f"{m.get('total_verts',0):>7}  "
              f"{m.get('uv_avg',0):>5.1%}  "
              f"{m.get('weight_coverage',0):>5.1%}  "
              f"{m.get('anim_count',0):>3}")
    print(f"  {'-'*22} {'-'*4}  {'-'*6}")
    print(f"  {'AVERAGE':<22} {'':4}  {avg:>6.1f}")
    print(f"\n  PASS:{n_pass}  WARN:{n_warn}  FAIL:{n_fail}  Total:{len(results)}")

    # ── Check breakdown ───────────────────────────────────────────────────────
    print("\n  CHECK-LEVEL PASS RATES:")
    for ck in CHECKLIST:
        n_p = sum(1 for r in results if r["checks"].get(ck) is True)
        pct = n_p / len(results) * 100
        bar = "█" * int(pct/5) + "░" * (20 - int(pct/5))
        print(f"  {ck:<22} {bar}  {n_p:>2}/{len(results)}  {pct:>5.1f}%")

    # ── Per-model checklist ───────────────────────────────────────────────────
    print("\n  PER-MODEL CHECKLIST:")
    abbr = [c[:5] for c in CHECKLIST]
    hdr  = f"  {'MODEL':<22} " + "  ".join(f"{a:>5}" for a in abbr)
    print(hdr)
    for r in results:
        row = f"  {r['name']:<22} "
        row += "  ".join(
            f"{'✓':>5}" if r["checks"].get(c) is True
            else (f"{'✗':>5}" if r["checks"].get(c) is False else f"{'?':>5}")
            for c in CHECKLIST
        )
        row += f"   {r['score']:>5.1f}%"
        print(row)

    # ── Overall ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 76)
    print(f"  OVERALL COMPLETION: {avg:.1f}%")
    print(f"  Models at 100%: {n_pass}/{len(results)}")
    print(f"  Models 75-99%:  {n_warn}/{len(results)}")
    print(f"  Models <75%:    {n_fail}/{len(results)}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print("=" * 76)

    # ── Save report ───────────────────────────────────────────────────────────
    report = {
        "version": "6.1", "date": "2026-03-06",
        "models": len(results), "overall_score": round(avg, 2),
        "passed": n_pass, "warned": n_warn, "failed": n_fail,
        "results": results,
    }
    rpath = os.path.join(OUT_DIR, "deep_audit_v6.1.json")
    with open(rpath, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\n  JSON report → {rpath}")

    return results


if __name__ == "__main__":
    main()
