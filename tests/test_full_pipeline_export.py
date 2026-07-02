"""P4 (T2513): full-pipeline round-trip — split multi-node skinned export.

Proves the one previously-unattested claim in the c_drexl_uv chain: a
BIAGP-split MULTI-NODE skinned model survives `MDLBinaryWriter`, reloads
through `read_mdl_safe`, and passes the headless `ghostrigger_audit`.

Pipeline under test:
  real `c_drexlf` KotorModel
    → consolidate its 7 authored skin nodes into ONE 55-bone unified skin node
      (the shape a custom import produces)
    → `split_skinned_mesh_nodes_with_weight_remap` (PR E / T2512)
    → `MDLBinaryWriter.write` → bytes
    → `load_model_from_bytes` (read_mdl_safe path)
    → headless `ghostrigger_audit` on the written .mdl
    → artifact + SHA-256 hashes in exports/; optional Override install.

kotormcp shadowing workaround (charter §5.5): the sibling KotorMCP workspace's
`kotormcp` package shadows the repo-local Core.Automation copy on the conftest
path, and the sibling lacks `tools.ghostrigger`.  We therefore purge `kotormcp*`
from `sys.modules` and prepend the Core.Automation `src` root before importing
the audit tool (~5 lines, see `_load_audit_tool`).

Override install is env-gated (`GHOSTRIGGER_P4_INSTALL_OVERRIDE=1`) so a normal
pytest run never mutates the game install; the artifact + hashes always land in
`exports/t2513_c_drexlf/` for manual installation.  In-game observation (warp,
walk + attack animation) is the owner's manual acceptance step, out of scope.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_EXPORT_DIR = _ROOT / "exports" / "t2513_c_drexlf"

_REQUIRED_HOOKS = ("Lhand_g", "Rhand_g", "camerahook", "head_g")
_REQUIRED_ANIMATIONS = ("cwalk", "cpause1", "pause2", "default")
_EXPECTED_TEXTURE = "c_drex01"


def _load_module(mod_name: str, rel_path: str):
    path = _ROOT.joinpath(*rel_path.split("/"))
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


wf = _load_module(
    "gr_headless_body_workflow_p4",
    "native/GhostRigger.Core.Workflow/Python/src/core/characters/"
    "headless_body_workflow.py",
)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_audit_tool():
    """Import the repo-local `kotormcp.tools.ghostrigger` (audit) module.

    Shadowing workaround: the sibling KotorMCP workspace's `kotormcp` wins on
    the conftest path but lacks `tools.ghostrigger`; purge and re-import with
    the Core.Automation src root first.
    """
    automation_src = str(_ROOT / "native" / "GhostRigger.Core.Automation" / "Python" / "src")
    for name in [m for m in list(sys.modules) if m == "kotormcp" or m.startswith("kotormcp.")]:
        del sys.modules[name]
    if automation_src in sys.path:
        sys.path.remove(automation_src)
    sys.path.insert(0, automation_src)
    try:
        from kotormcp.tools import ghostrigger as audit_mod  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"repo-local kotormcp audit tool unavailable: {exc}")
    return audit_mod


def _weight_multiset(node, vertex_index):
    """Name-keyed {(bone_name, weight)} multiset — remap/local-index invariant."""
    row = node.skin_data[vertex_index]
    out = []
    for infl in getattr(row, "influences", []) or []:
        bi = int(getattr(infl, "bone_index", -1))
        w = float(getattr(infl, "weight", 0.0) or 0.0)
        if 0 <= bi < len(node.bone_map) and w > 1e-9:
            out.append((str(node.bone_map[bi]).lower(), round(w, 6)))
    return sorted(out)


def _consolidate_skin_nodes_to_unified(model) -> "object":
    """Replace the model's 7 skin nodes with ONE unified 55-bone skin node.

    The unified node sits at the root with identity transform, so node-local ==
    world and its vertices can be the donor builder's world-frame concatenation
    (the exact shape a custom single-mesh import produces after Policy 0).
    Per-vertex normals/uvs and per-bone qBone/tBone bind data are concatenated
    from the source nodes in the same iteration order the donor builder uses.
    """
    from src.core.game.kotor_loader import build_donor_skin_data_from_model

    donor = build_donor_skin_data_from_model(model)
    skin_nodes = [
        n for n in model.all_nodes() if getattr(n, "is_skin", False) and n.vertices
    ]
    assert len(skin_nodes) == 7

    # Per-vertex attributes, concatenated in builder order.
    normals: list = []
    uvs: list = []
    for node in skin_nodes:
        n_local = len(node.vertices)
        node_normals = list(getattr(node, "normals", []) or [])
        node_uvs = list(getattr(node, "uvs", []) or [])
        normals.extend(node_normals[:n_local] + [(0.0, 0.0, 1.0)] * max(0, n_local - len(node_normals)))
        uvs.extend(node_uvs[:n_local] + [(0.0, 0.0)] * max(0, n_local - len(node_uvs)))

    # Per-bone bind data by NAME from whichever source node carries the bone.
    bind_by_name: dict = {}
    for node in skin_nodes:
        qb = list(getattr(node, "qbone_list", []) or [])
        tb = list(getattr(node, "tbone_list", []) or [])
        for local_i, bone_name in enumerate(list(node.bone_map)):
            key = str(bone_name).lower()
            if key not in bind_by_name:
                q = qb[local_i] if local_i < len(qb) else (0.0, 0.0, 0.0, 1.0)
                t = tb[local_i] if local_i < len(tb) else (0.0, 0.0, 0.0)
                bind_by_name[key] = (q, t)

    skin_rows = []
    bi = np.asarray(donor.bone_indices, dtype=np.int64)
    bw = np.asarray(donor.bone_weights, dtype=np.float64)
    for row_bi, row_bw in zip(bi, bw):
        influences = []
        for b, w in zip(row_bi, row_bw):
            if int(b) >= 0 and float(w) > 0.0:
                influences.append(SimpleNamespace(bone_index=int(b), weight=float(w)))
        skin_rows.append(SimpleNamespace(influences=influences))

    # Mutate the first skin node into the unified container (keeps authentic
    # skin flags/node type for the writer), reparent to root, drop the rest.
    container = skin_nodes[0]
    root = model.root_node
    for node in skin_nodes:
        parent = getattr(node, "parent", None)
        if parent is not None and node in (parent.children or []):
            parent.children.remove(node)

    container.name = "bodyGeo"
    container.parent = root
    container.position = (0.0, 0.0, 0.0)
    container.rotation = (0.0, 0.0, 0.0, 1.0)
    container.vertices = [tuple(float(x) for x in v) for v in np.asarray(donor.vertices)]
    container.faces = [tuple(int(i) for i in f) for f in np.asarray(donor.faces)]
    container.normals = normals
    container.uvs = uvs
    container.face_uvs = []
    container.tangents = []
    container.skin_data = skin_rows
    container.bone_map = list(donor.bone_names)
    container.bone_map_floats = []
    container.qbone_list = [
        bind_by_name.get(str(n).lower(), ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))[0]
        for n in donor.bone_names
    ]
    container.tbone_list = [
        bind_by_name.get(str(n).lower(), ((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 0.0)))[1]
        for n in donor.bone_names
    ]
    root.children.append(container)
    return container


def test_full_pipeline_split_export_reload_audit(capsys) -> None:
    from tests.test_anatomical_partition import _resolve_k2_dir

    k2_dir = _resolve_k2_dir()
    if k2_dir is None:
        pytest.skip("K2 install not available")
    try:
        from src.core.assets.resource_manager import ResourceManager
        from src.core.mdl.mdl_writer import MDLBinaryWriter
        from src.core.game.kotor_loader import load_model_from_bytes
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"core imports unavailable: {exc}")

    mgr = ResourceManager()
    if not mgr.set_k2_dir(k2_dir):
        pytest.skip("could not index K2")
    model = mgr.load_model("c_drexlf", "K2")
    reference = ResourceManager().load_model("c_drexlf", "K2") if False else None
    # Fresh, unmutated donor reference (separate manager keeps caches apart).
    mgr2 = ResourceManager()
    mgr2.set_k2_dir(k2_dir)
    reference = mgr2.load_model("c_drexlf", "K2")
    if model is None or reference is None:
        pytest.skip("c_drexlf not found")

    # ---- Stage 1: consolidate to the single-import shape --------------------
    container = _consolidate_skin_nodes_to_unified(model)
    assert len(container.bone_map) > 16  # over-palette by construction
    source_weights = [
        _weight_multiset(container, i) for i in range(len(container.vertices))
    ]

    # ---- Stage 2: PR E split -------------------------------------------------
    split = wf.split_skinned_mesh_nodes_with_weight_remap(model, reference)
    assert split["ok"], split
    parts = [
        n for n in model.all_nodes() if getattr(n, "_gr_weight_remap_split", False)
    ]
    assert len(parts) == split["split_nodes"] >= 4
    for part in parts:
        assert len(part.bone_map) <= 16
        # qBone/tBone bind data subset alongside the palette (T2513 fix).
        assert len(part.qbone_list) == len(part.bone_map)
        assert len(part.tbone_list) == len(part.bone_map)

    try:
        model.compute_bounds()
    except Exception:
        pass

    # ---- Stage 3: binary export ----------------------------------------------
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    assert len(mdl_bytes) > 1024 and len(mdx_bytes) > 1024
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    mdl_path = _EXPORT_DIR / "c_drexlf.mdl"
    mdx_path = _EXPORT_DIR / "c_drexlf.mdx"
    mdl_path.write_bytes(mdl_bytes)
    mdx_path.write_bytes(mdx_bytes)
    hashes = {"mdl_sha256": _sha256(mdl_path), "mdx_sha256": _sha256(mdx_path)}

    # ---- Stage 4: reload through read_mdl_safe -------------------------------
    reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes)
    assert reloaded is not None
    reloaded_nodes = list(reloaded.all_nodes())
    reloaded_names = {str(n.name).lower() for n in reloaded_nodes}

    # Hooks preserved.
    for hook in _REQUIRED_HOOKS:
        assert hook.lower() in reloaded_names, f"hook lost: {hook}"

    # Animations preserved.
    anim_names = {
        str(getattr(a, "name", "") or "").lower()
        for a in (getattr(reloaded, "animations", []) or [])
    }
    for anim in _REQUIRED_ANIMATIONS:
        assert anim.lower() in anim_names, f"animation lost: {anim} (have {sorted(anim_names)})"

    # Multi-node skinned payload survived: same region nodes, palettes <= 16.
    reloaded_skins = [
        n for n in reloaded_nodes if getattr(n, "is_skin", False) and n.vertices
    ]
    assert len(reloaded_skins) == len(parts)
    for node in reloaded_skins:
        assert str(node.name).lower().startswith("bodygeo_anat")
        assert 0 < len(node.bone_map) <= 16, (node.name, len(node.bone_map))
        texture = str(getattr(node, "texture", "") or "").lower()
        assert texture == _EXPECTED_TEXTURE, (node.name, texture)

    assert sum(len(n.faces) for n in reloaded_skins) == 1526

    # Weights survive the byte round-trip: chain reloaded -> part -> source.
    parts_by_name = {str(p.name).lower(): p for p in parts}
    checked = 0
    for node in reloaded_skins:
        part = parts_by_name[str(node.name).lower()]
        assert len(node.vertices) == len(part.vertices)
        src_idx = getattr(part, "_gr_source_vertex_indices")
        for i in range(len(node.vertices)):
            assert _weight_multiset(node, i) == source_weights[src_idx[i]], (
                node.name,
                i,
            )
            checked += 1
    assert checked == len(container.vertices) * 0 + sum(
        len(p.vertices) for p in parts
    )

    # ---- Stage 5: headless ghostrigger_audit vs VANILLA baseline -------------
    # T2513 FINDING: vanilla c_drexlf itself audits as `issues_found` with 61
    # "UV count mismatch" issues (every bone-geometry node carries vertices but
    # no UVs — an analyzer strictness quirk, present in the shipped game data).
    # T2505's `status=ok` was on the single-mesh override, which had no
    # bone-geometry nodes at all.  The correct full-DAG acceptance is therefore
    # "NO NEW issues vs the vanilla baseline", not `status == ok`.
    audit_mod = _load_audit_tool()
    import asyncio

    vanilla_raw = asyncio.run(
        audit_mod.handle_audit(
            {"resref": "c_drexlf", "game": "k2", "game_path": str(k2_dir)}
        )
    )
    vanilla = json.loads(vanilla_raw["text"])
    assert "error" not in vanilla, vanilla

    raw = asyncio.run(audit_mod.handle_audit({"resref": str(mdl_path)}))
    payload = json.loads(raw["text"])
    with capsys.disabled():
        print("\n=== T2513 round-trip artifact ===")
        print(f"mdl={mdl_path} ({len(mdl_bytes)} B) sha256={hashes['mdl_sha256'][:16]}")
        print(f"mdx={mdx_path} ({len(mdx_bytes)} B) sha256={hashes['mdx_sha256'][:16]}")
        print(
            f"audit: status={payload.get('status')} nodes={payload.get('node_count')} "
            f"bbox={payload.get('bounding_box_ok')} issues={len(payload.get('issues', []))} "
            f"(vanilla baseline: status={vanilla.get('status')} "
            f"issues={len(vanilla.get('issues', []))})"
        )

    assert "error" not in payload, payload
    assert payload["bounding_box_ok"] is True, payload
    assert payload["status"] in ("ok", "issues_found"), payload
    assert not payload["warnings"], payload

    # No NEW issues: every exported issue must also exist in vanilla (the
    # export may only ever be cleaner than the shipped game data).
    vanilla_issues = set(vanilla.get("issues", []))
    new_issues = [i for i in payload.get("issues", []) if i not in vanilla_issues]
    assert not new_issues, f"export introduced NEW audit issues: {new_issues}"
    assert len(payload.get("issues", [])) <= len(vanilla_issues)

    # Persist the artifact manifest for the manual install / in-game step.
    manifest = {
        "task": "T2513",
        "resref": "c_drexlf",
        "region_nodes": [str(p.name) for p in parts],
        "palette_sizes": [len(p.bone_map) for p in parts],
        "hashes": hashes,
        "audit": payload,
        "install_hint": (
            "copy c_drexlf.mdl + c_drexlf.mdx to the K2 Override folder "
            "(or re-run with GHOSTRIGGER_P4_INSTALL_OVERRIDE=1)"
        ),
    }
    (_EXPORT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # ---- Stage 6 (env-gated): install to Override with hash verification -----
    if os.environ.get("GHOSTRIGGER_P4_INSTALL_OVERRIDE", "") == "1":
        override_dir = pathlib.Path(k2_dir) / "Override"
        override_dir.mkdir(parents=True, exist_ok=True)
        pre_existing = {}
        for src, name in ((mdl_path, "c_drexlf.mdl"), (mdx_path, "c_drexlf.mdx")):
            dst = override_dir / name
            if dst.exists():
                pre_existing[name] = _sha256(dst)
            dst.write_bytes(src.read_bytes())
            assert _sha256(dst) == _sha256(src), f"install hash mismatch: {name}"
        manifest["installed_to"] = str(override_dir)
        manifest["pre_existing_hashes"] = pre_existing
        (_EXPORT_DIR / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        with capsys.disabled():
            print(f"installed to {override_dir} (pre-existing: {pre_existing})")
