"""Tests for anatomical_partition.partition_mesh_anatomically (PR C) in
native/GhostRigger.Core.Math/Python/src/math/anatomical_partition.py.

PR C decomposes a unified imported mesh into ≤16-bone anatomical regions using a
donor's skin weights (BIAGP on the donor) and transfers those regions to the
imported mesh by nearest-donor-face correspondence.

The module is loaded by file path and registered in ``sys.modules`` (the PR B
pattern) so that (a) it does not shadow the stdlib ``math`` package and (b) its
frozen dataclasses resolve their own module namespace.

Tests 5–7 exercise the real Drexl donor (K2 ``c_drexlf``) + the re-UV'd import
``C_DrexlF_UV.obj``; they ``skip`` when the K2 install or the OBJ is unavailable.
Test 7 is the load-bearing falsifier for the whole containment+splitter thesis;
see its docstring.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
from typing import List, Optional, Tuple

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
pytest.importorskip("scipy")

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(mod_name: str, rel_path: str):
    path = _ROOT.joinpath(*rel_path.split("/"))
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module  # register before exec so dataclasses resolve
    spec.loader.exec_module(module)
    return module


ap = _load_module(
    "gr_anatomical_partition",
    "native/GhostRigger.Core.Math/Python/src/math/anatomical_partition.py",
)
cf = _load_module(
    "gr_containment_fit_prc",
    "native/GhostRigger.Core.Math/Python/src/math/containment_fit.py",
)


# ---------------------------------------------------------------------------
# Synthetic mesh + skin builders
# ---------------------------------------------------------------------------


def _grid(nx: int, ny: int, spacing: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    """A flat triangulated grid: ``nx*ny`` vertices, ``2*(nx-1)*(ny-1)`` faces."""
    xs, ys = np.meshgrid(np.arange(nx) * spacing, np.arange(ny) * spacing)
    verts = np.stack([xs.ravel(), ys.ravel(), np.zeros(nx * ny)], axis=1).astype(np.float64)
    faces: List[Tuple[int, int, int]] = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            b = a + 1
            c = a + nx
            d = c + 1
            faces.append((a, b, c))
            faces.append((b, d, c))
    return verts, np.asarray(faces, dtype=np.int64)


def _limb_strip(
    n_zones: int, cols_per_zone: int = 4, ny: int = 5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``n_zones`` side-by-side grids sharing coincident seam columns.

    Each zone is its own vertex block (so every face is pure single-zone), but
    zone ``z``'s right column coincides in space with zone ``z+1``'s left column,
    so seam-welding makes the zones topologically adjacent — a chain of limbs
    "joined at a hub" with disjoint per-limb bone palettes.  Returns
    ``(vertices, faces, per_vertex_zone)``.
    """
    all_v, all_f, zone = [], [], []
    voff = 0
    for z in range(n_zones):
        v, f = _grid(cols_per_zone, ny)
        v = v.copy()
        v[:, 0] += z * (cols_per_zone - 1)  # seam columns coincide
        all_v.append(v)
        all_f.append(f + voff)
        zone.append(np.full(v.shape[0], z, dtype=np.int64))
        voff += v.shape[0]
    return np.vstack(all_v), np.vstack(all_f), np.concatenate(zone)


def _single_influence(primary: np.ndarray, k: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    """Skin arrays where each vertex is fully weighted to one ``primary`` bone."""
    v = primary.shape[0]
    bone_indices = np.full((v, k), -1, dtype=np.int64)
    bone_weights = np.zeros((v, k), dtype=np.float64)
    bone_indices[:, 0] = primary
    bone_weights[:, 0] = 1.0
    return bone_indices, bone_weights


def _donor(
    verts: np.ndarray,
    faces: np.ndarray,
    bone_indices: np.ndarray,
    bone_weights: np.ndarray,
    n_bones: int,
) -> "ap.DonorSkinData":
    names = [f"bone_{i}" for i in range(n_bones)]
    # Bone positions: centroid of the vertices most influenced by each bone.
    positions = np.zeros((n_bones, 3), dtype=np.float64)
    for b in range(n_bones):
        mask = np.any((bone_indices == b) & (bone_weights > 0), axis=1)
        positions[b] = verts[mask].mean(axis=0) if np.any(mask) else np.zeros(3)
    return ap.DonorSkinData(
        vertices=verts,
        faces=faces,
        bone_indices=bone_indices,
        bone_weights=bone_weights,
        bone_names=names,
        bone_positions=positions,
    )


# ---------------------------------------------------------------------------
# 1. Missing / malformed donor hard-fails
# ---------------------------------------------------------------------------


def test_missing_donor_raises() -> None:
    verts, faces = _grid(4, 4)

    # None donor.
    with pytest.raises(ap.MissingDonorError, match="Donor is None"):
        ap.partition_mesh_anatomically(verts, faces, None)

    # Too few vertices.
    tiny = ap.DonorSkinData(
        vertices=np.zeros((3, 3)),
        faces=np.array([[0, 1, 2]]),
        bone_indices=np.zeros((3, 4), dtype=np.int64),
        bone_weights=np.zeros((3, 4)),
        bone_names=["b0"],
        bone_positions=np.zeros((1, 3)),
    )
    with pytest.raises(ap.MissingDonorError, match="fewer than 4"):
        ap.partition_mesh_anatomically(verts, faces, tiny)

    # Weight/vertex-count mismatch.
    gverts, gfaces = _grid(4, 4)
    mismatch = ap.DonorSkinData(
        vertices=gverts,
        faces=gfaces,
        bone_indices=np.zeros((gverts.shape[0] - 2, 4), dtype=np.int64),
        bone_weights=np.zeros((gverts.shape[0] - 2, 4)),
        bone_names=["b0"],
        bone_positions=np.zeros((1, 3)),
    )
    with pytest.raises(ap.MissingDonorError, match="weight-vertex mismatch"):
        ap.partition_mesh_anatomically(verts, faces, mismatch)

    # Non-finite weights.
    bi, bw = _single_influence(np.zeros(gverts.shape[0], dtype=np.int64))
    bw[0, 0] = np.nan
    nonfinite = _donor(gverts, gfaces, bi, bw, 1)
    with pytest.raises(ap.MissingDonorError, match="non-finite"):
        ap.partition_mesh_anatomically(verts, faces, nonfinite)


# ---------------------------------------------------------------------------
# 2. Two disjoint-bone limbs → two regions
# ---------------------------------------------------------------------------


def test_synthetic_two_limb_creature_produces_two_regions() -> None:
    # Two limbs joined at a hub: each limb is a separate grid fully weighted to
    # its own bone (disjoint palettes), welded together at a shared seam column.
    verts, faces, zone = _limb_strip(2)
    bi, bw = _single_influence(zone.astype(np.int64))
    donor = _donor(verts, faces, bi, bw, 2)

    result = ap.partition_mesh_anatomically(verts, faces, donor, min_faces_per_region=2)

    assert result.diagnostics["final_region_count"] == 2
    doms = sorted(r.dominant_bone_index for r in result.regions)
    assert doms == [0, 1]


# ---------------------------------------------------------------------------
# 3. A 20-bone region is palette-split into ≤16-bone sub-regions
# ---------------------------------------------------------------------------


def test_synthetic_20_bone_region_splits_via_palette() -> None:
    # One connected patch whose faces are ALL dominated by bone 0 (weight 0.55
    # everywhere) but which collectively carries 20 distinct influence bones.
    nx, ny = 11, 6
    verts, faces = _grid(nx, ny)
    v = verts.shape[0]
    n_bones = 20
    bone_indices = np.full((v, 4), -1, dtype=np.int64)
    bone_weights = np.zeros((v, 4), dtype=np.float64)
    bone_indices[:, 0] = 0
    bone_weights[:, 0] = 0.55
    # Spread bones 1..19 across the patch as weak secondary influences.
    for idx in range(v):
        secondary = 1 + (idx % (n_bones - 1))
        bone_indices[idx, 1] = secondary
        bone_weights[idx, 1] = 0.45
    donor = _donor(verts, faces, bone_indices, bone_weights, n_bones)

    result = ap.partition_mesh_anatomically(verts, faces, donor)

    assert result.diagnostics["palette_splits_triggered"] >= 1
    assert result.diagnostics["final_region_count"] >= 2
    assert result.diagnostics["max_bones_in_any_region"] <= 16
    covered = set()
    for region in result.regions:
        assert region.bone_indices_in_region.size <= 16
        covered |= set(region.bone_indices_in_region.tolist())
    # Every one of the 20 bones is accounted for across the sub-regions.
    assert covered == set(range(n_bones))


# ---------------------------------------------------------------------------
# 4. Dust islands are merged away
# ---------------------------------------------------------------------------


def test_dust_islands_merged() -> None:
    # Three disjoint-bone zones (bones 0/1/2) welded into a chain, plus a tiny
    # bone-3 island (one face's vertices retagged) inside zone 0.  The island is
    # smaller than min_faces so it dissolves; the three real zones have disjoint
    # palettes so they never agglomerate → exactly 3 regions.
    verts, faces, zone = _limb_strip(3, cols_per_zone=5, ny=5)
    primary = zone.astype(np.int64)
    bi, bw = _single_influence(primary)
    # Retag the 3 vertices of one interior face of zone 0 to bone 3.
    zone0_faces = np.where(np.all(zone[faces] == 0, axis=1))[0]
    island_face = faces[zone0_faces[len(zone0_faces) // 2]]
    bi[island_face, 0] = 3
    donor = _donor(verts, faces, bi, bw, 4)

    result = ap.partition_mesh_anatomically(verts, faces, donor, min_faces_per_region=8)

    assert result.diagnostics["final_region_count"] == 3
    assert result.diagnostics["donor_regions_dust_merged"] >= 1


# ---------------------------------------------------------------------------
# Real Drexl donor + import fixtures (tests 5–7)
# ---------------------------------------------------------------------------


def _find_drexl_obj() -> Optional[pathlib.Path]:
    candidates = [
        os.environ.get("GHOSTRIGGER_DREXL_OBJ"),
        os.environ.get("DREXL_PATH"),
        r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\Drexl\C_DrexlF_UV.obj",
        str(_ROOT / ".hermes" / "desktop-attachments" / "C_DrexlF_UV.obj"),
    ]
    for c in candidates:
        if c and pathlib.Path(c).is_file():
            return pathlib.Path(c)
    return None


def _resolve_k2_dir() -> Optional[str]:
    candidates = [
        os.environ.get("K2_PATH"),
        r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
        r"h:\steam\steamapps\common\Knights of the Old Republic II",
    ]
    for c in candidates:
        if c and pathlib.Path(c).is_dir():
            return c
    return None


_DREXL_DONOR_CACHE: Optional["ap.DonorSkinData"] = None


def _load_drexl_model():
    """Load K2 ``c_drexlf``, skipping cleanly when the install is unavailable."""
    k2_dir = _resolve_k2_dir()
    if k2_dir is None:
        pytest.skip("K2 install not available (set K2_PATH)")
    try:
        from src.core.assets.resource_manager import ResourceManager
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"GhostRigger core imports unavailable: {exc}")
    mgr = ResourceManager()
    if not mgr.set_k2_dir(k2_dir):
        pytest.skip(f"Could not index K2 install at {k2_dir}")
    model = mgr.load_model("c_drexlf", "K2")
    if model is None:
        pytest.skip("c_drexlf not found in K2 install (cut content / needs Override)")
    return model


def _build_drexl_donor() -> "ap.DonorSkinData":
    """Load K2 ``c_drexlf`` and assemble a unified, world-frame DonorSkinData.

    Delegates to the production builder
    ``src.core.game.kotor_loader.build_donor_skin_data_from_model`` (PR C.1) so
    the tests exercise the real code path.  Drexl ships as 7 separate skin nodes
    (head/chest/each arm/each wing/tail); the builder concatenates them into one
    world-frame donor mesh, remaps each node's local bone indices to a global
    bone list, and reads rest-pose pivots via ``node.bone_world_position()``.
    """
    global _DREXL_DONOR_CACHE
    if _DREXL_DONOR_CACHE is not None:
        return _DREXL_DONOR_CACHE
    try:
        from src.core.game.kotor_loader import build_donor_skin_data_from_model
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"donor builder unavailable: {exc}")
    model = _load_drexl_model()
    _DREXL_DONOR_CACHE = build_donor_skin_data_from_model(model)
    return _DREXL_DONOR_CACHE


def _load_imported_drexl() -> Tuple[np.ndarray, np.ndarray]:
    obj = _find_drexl_obj()
    if obj is None:
        pytest.skip("Drexl import OBJ not available (set GHOSTRIGGER_DREXL_OBJ)")
    mesh = trimesh.load(str(obj), process=False, force="mesh")
    return (
        np.asarray(mesh.vertices, dtype=np.float64),
        np.asarray(mesh.faces, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# 5. Drexl donor partition shape
# ---------------------------------------------------------------------------


def test_drexl_donor_partition_shape() -> None:
    donor = _build_drexl_donor()
    imported_v, imported_f = _load_imported_drexl()

    result = ap.partition_mesh_anatomically(imported_v, imported_f, donor)
    diag = result.diagnostics

    # Corrected world-frame baseline (PR C.1).  Drexl's 7 authored skin nodes are
    # recovered exactly; the donor is a self-fit of C_DrexlF_UV.obj so transfer
    # confidence is ~1.0.  Tighten, never loosen: if these move, halt and report.
    assert diag["final_region_count"] == 7            # halt & report if different
    assert diag["max_bones_in_any_region"] <= 16      # hard invariant
    assert diag["max_bones_in_any_region"] == 16      # observed world-frame baseline
    assert diag["mean_transfer_confidence"] >= 0.99   # was 0.846 pre-PR-C.1

    # Every donor deformation bone (any nonzero weight) appears in some region.
    total_weight = np.zeros(len(donor.bone_names))
    for k in range(donor.bone_indices.shape[1]):
        valid = donor.bone_indices[:, k] >= 0
        np.add.at(total_weight, donor.bone_indices[valid, k], donor.bone_weights[valid, k])
    deformation_bones = set(np.where(total_weight > 1e-6)[0].tolist())

    covered = set()
    for region in result.regions:
        covered |= set(region.bone_indices_in_region.tolist())
    assert deformation_bones <= covered, (
        f"deformation bones missing from all regions: "
        f"{sorted(deformation_bones - covered)}"
    )
    # Bones may be shared across regions, so the sum can exceed the bone count.
    assert sum(r.bone_indices_in_region.size for r in result.regions) >= 54


# ---------------------------------------------------------------------------
# 6. Drexl region transfer to the imported OBJ
# ---------------------------------------------------------------------------


def test_drexl_region_transfer_to_imported_obj() -> None:
    donor = _build_drexl_donor()
    imported_v, imported_f = _load_imported_drexl()

    result = ap.partition_mesh_anatomically(imported_v, imported_f, donor)

    # Every imported face has a region assignment.
    assert result.imported_face_to_region.shape[0] == imported_f.shape[0]
    assert np.all(result.imported_face_to_region >= 0)

    # Self-fit under the corrected world frame (PR C.1): confidence ~1.0.
    assert result.diagnostics["mean_transfer_confidence"] >= 0.99
    assert isinstance(result.diagnostics["regions_with_low_transfer_confidence"], list)


# ---------------------------------------------------------------------------
# 6b. Donor builder applies the world-frame transform (PR C.1 / T2508)
# ---------------------------------------------------------------------------


def test_donor_builder_applies_world_frame() -> None:
    """The production donor-builder must place vertices in world space.

    Proves the PR C.1 fix: donor vertices are transformed by each skin node's
    parent-chain world transform, not concatenated node-local.  We compare the
    built donor against the raw node-local concatenation (the pre-PR-C.1
    behaviour) and require a meaningful shift plus the ``frame`` marker.
    """
    from src.core.game.kotor_loader import build_donor_skin_data_from_model

    model = _load_drexl_model()
    donor = build_donor_skin_data_from_model(model)

    assert donor.frame == "world_space_v1"

    # Raw node-local concatenation (same node filter/order the builder uses).
    skin = [n for n in model.all_nodes() if getattr(n, "is_skin", False) and n.vertices]
    raw = np.vstack([np.asarray(n.vertices, dtype=np.float64) for n in skin])
    assert raw.shape == donor.vertices.shape, (
        f"raw {raw.shape} vs built {donor.vertices.shape} — node set/order mismatch"
    )

    max_shift = float(np.max(np.linalg.norm(donor.vertices - raw, axis=1)))
    assert max_shift > 0.5, (
        f"world-frame transform barely moved vertices (max shift {max_shift:.3f}); "
        "builder may not be applying node transforms"
    )


def test_donor_builder_matches_canonical_world_transform() -> None:
    """Builder vertex placement == canonical `ModelNode.world_transform()` (PR C.1a).

    Locks the migration: the donor builder must produce the same bind-world
    vertices as `OBJExporter._node_bind_world_verts` (the shared export-path
    consumer of `world_transform()`), which — unlike a raw parent-chain walk —
    collapses parent 180° bind-flips.  Cross-module comparison, not a self-check.
    """
    from src.core.game.kotor_loader import build_donor_skin_data_from_model

    try:
        from src.converters.mesh_converter import OBJExporter
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"mesh_converter unavailable: {exc}")

    model = _load_drexl_model()
    donor = build_donor_skin_data_from_model(model)

    skin = [n for n in model.all_nodes() if getattr(n, "is_skin", False) and n.vertices]
    expected = np.vstack(
        [np.asarray(OBJExporter._node_bind_world_verts(n), dtype=np.float64) for n in skin]
    )
    assert expected.shape == donor.vertices.shape, (
        f"canonical {expected.shape} vs builder {donor.vertices.shape} — node mismatch"
    )
    assert np.allclose(donor.vertices, expected, atol=1e-9, rtol=0), (
        "builder vertices diverge from canonical world_transform placement; "
        f"max diff {float(np.max(np.abs(donor.vertices - expected)))}"
    )


# ---------------------------------------------------------------------------
# 7. FALSIFIER: per-region v2 containment on Drexl
# ---------------------------------------------------------------------------


def _region_v2_table(
    result: "ap.PartitionResult", imported_v: np.ndarray, imported_f: np.ndarray
) -> List[dict]:
    """Run v2 on every ≥3-bone region and return the per-region convergence row set."""
    rows: List[dict] = []
    for region in result.regions:
        bones = region.bone_positions
        if bones.shape[0] < 3:
            continue  # containment on 1–2 bones is degenerate
        face_ids = region.imported_face_indices
        if face_ids.size < 4:
            continue
        sub_faces = imported_f[face_ids]
        uniq, inverse = np.unique(sub_faces.reshape(-1), return_inverse=True)
        sub_v = imported_v[uniq]
        sub_f = inverse.reshape(-1, 3)

        bone_diag = float(np.linalg.norm(bones.max(axis=0) - bones.min(axis=0)))
        mesh_diag = float(np.linalg.norm(sub_v.max(axis=0) - sub_v.min(axis=0)))
        init_est = max(bone_diag / max(mesh_diag, 1e-9) * 1.2, 1e-9)

        fit = cf.fit_skeleton_inside_mesh_v2(
            sub_v,
            sub_f,
            bones,
            use_v2=True,
            target_margin=0.3,
            margin_relative_to="shell_diagonal",
        )
        scale = float(fit["scale"])
        ratio = scale / init_est if np.isfinite(scale) else float("inf")
        rows.append(
            {
                "region_id": region.region_id,
                "dominant_bone": region.dominant_bone_name,
                "n_bones": int(bones.shape[0]),
                "init_scale_estimate": init_est,
                "v2_scale": scale,
                "ratio": ratio,
                "all_bones_margin_met": bool(
                    all(fit.get("containment_fit", {}).get("v2_bone_margin_met", [False]))
                ),
                "status": fit.get("containment_fit", {}).get("v2_status", "unknown"),
            }
        )
    return rows


@pytest.mark.xfail(
    reason=(
        "Containment objective spec-level rework in flight — shell-containment of "
        "joint pivots is incoherent for open-shell region sub-meshes (proximal "
        "joints sit on the region rim, not its interior). See "
        "docs/knowledgebase/learned/pr_c_anatomical_partition_report.md"
    ),
    strict=True,
)
def test_drexl_per_region_v2_converges_at_natural_scale(capsys) -> None:
    """Load-bearing acceptance test: anatomical splitting must yield per-region
    containment at a *natural* scale.

    The thesis this whole PR series tests: a single rigid containment fit
    balloons on Drexl (PR B: scale ~87, ~10x baseline) because tail/hands/torso
    cannot sit inside one silhouette; splitting into anatomical regions should let
    each region's local sub-mesh contain its own bones at ≤1.5x the region's
    natural ``initial_scale_estimate``.  This test asserts that design goal for
    every ≥3-bone region.

    It is currently ``xfail(strict=True)`` — a hard-red gate, not a
    green-documenting waypoint.  PR C's partitioner is correct (test 5/6: 7
    authored regions recovered from weights, transfer confidence 0.846), but v2
    still balloons every region except the near-closed head (head_g ~3.2x; the
    rest hit the 20x cap).  Diagnostic ablations (full palette / dominant-only /
    weighted-influence-centroid) all balloon, and the ideal 7-skin-node partition
    balloons too, so this is NOT a segmentation or transfer bug: it is a
    specification finding that shell-containing joint pivots is incoherent for
    open-shell region sub-meshes (proximal joints sit on the region's rim).

    ``strict=True`` means an unexpected pass fails the suite — which is exactly
    right: if this test passes, someone changed the containment objective and must
    remove the xfail marker deliberately.  Do NOT tune the partitioner to flip
    it; the fix is a containment-objective redesign (see the report).
    """
    donor = _build_drexl_donor()
    imported_v, imported_f = _load_imported_drexl()
    result = ap.partition_mesh_anatomically(imported_v, imported_f, donor)

    rows = _region_v2_table(result, imported_v, imported_f)
    assert rows, "expected at least one ≥3-bone region to fit"

    header = (
        f"{'R':>3} {'dominant_bone':<14} {'nb':>3} {'init_est':>9} "
        f"{'v2_scale':>11} {'ratio':>9} {'margin':>6} {'status':>12}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row['region_id']:>3} {row['dominant_bone']:<14} {row['n_bones']:>3} "
            f"{row['init_scale_estimate']:>9.3f} {row['v2_scale']:>11.3f} "
            f"{row['ratio']:>9.2f} {str(row['all_bones_margin_met']):>6} "
            f"{row['status']:>12}"
        )
    ballooned = [r for r in rows if not (r["ratio"] <= 1.5)]
    converged = [r for r in rows if r["ratio"] <= 1.5]
    table = "\n".join(lines)
    with capsys.disabled():
        print("\n=== PR C test 7: per-region v2 convergence on Drexl ===")
        print(table)
        print(
            f"converged (<=1.5x): {len(converged)}/{len(rows)}  "
            f"ballooned (>1.5x): {len(ballooned)}/{len(rows)}"
        )

    # DESIGN GOAL: every region's local sub-mesh contains its bones at a natural
    # scale.  Currently xfail — the containment objective needs redesign (see the
    # report).  Do not tune the partitioner to make this pass.
    assert not ballooned, (
        f"{len(ballooned)}/{len(rows)} regions balloon >1.5x their natural scale "
        "estimate — shell-containment objective needs redesign.\n" + table
    )


# ---------------------------------------------------------------------------
# 8. Diagnostics schema is stable
# ---------------------------------------------------------------------------


def test_diagnostics_schema_stable() -> None:
    nx, ny = 9, 5
    verts, faces = _grid(nx, ny)
    xcol = (verts[:, 0]).round().astype(int)
    primary = np.where(xcol < nx // 2, 0, 1).astype(np.int64)
    bi, bw = _single_influence(primary)
    donor = _donor(verts, faces, bi, bw, 2)

    result = ap.partition_mesh_anatomically(verts, faces, donor, min_faces_per_region=2)
    diag = result.diagnostics

    assert diag["trace_version"] == "ghostrigger.partition/v1"
    expected_types = {
        "trace_version": str,
        "donor_face_count": int,
        "imported_face_count": int,
        "donor_regions_before_palette": int,
        "donor_regions_after_palette": int,
        "donor_regions_dust_merged": int,
        "final_region_count": int,
        "ambiguous_faces_deferred": int,
        "palette_splits_triggered": int,
        "max_bones_in_any_region": int,
        "min_bones_in_any_region": int,
        "regions_with_low_transfer_confidence": list,
        "empty_transfer_regions": list,
        "mean_transfer_confidence": float,
        "algorithm_seed": int,
    }
    for key, typ in expected_types.items():
        assert key in diag, f"missing diagnostics key: {key!r}"
        assert isinstance(diag[key], typ), (
            f"diagnostics[{key!r}] is {type(diag[key])}, expected {typ}"
        )
