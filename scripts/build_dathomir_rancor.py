"""Build the Dathomir BIG Rancor boss package (T2537).

Pipeline: fit the custom Rancor FBX against the BIG c_rancor donor (8.42
units tall, anim_scale 1.0, supermodel NULL -> the export is fully
self-contained with all 23 clips), split, seam-check, export as resref
``dat_rancor``, then generate:

- Override-ready appearance.2da (effective copy + new row cloned from the
  vanilla Creature_Rancor row 80, race=dat_rancor)
- dat_rancor01.utc (clone of g_rancor01 boss template, appearance -> new row)
- dat_rancor_t00.tga (body texture under the export's renamed resref)

Everything lands in the MDL export directory; staging to Override is a
separate, backed-up step.
"""
from __future__ import annotations

import json
import os
import pathlib
import struct
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
OUT = pathlib.Path(r"C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor\MDL")
RESREF = "dat_rancor"
UTC_RESREF = "dat_rancor01"
RES_UTC = 2027

from src.core.assets.resource_manager import ResourceManager, RES_2DA  # noqa: E402
from src.core.characters import headless_body_workflow as wf  # noqa: E402
from src.core.characters import character_builder as cb  # noqa: E402
from src.core.geometry import model_data as md  # noqa: E402
from src.core.templates.twoda import TwoDA  # noqa: E402
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from diag_rancor_seam_divergence import (  # noqa: E402
    effective_weights_by_name,
    weight_delta,
)

# T2544: cap the per-skin-node bone palette.  Our crashing rancor had 16-bone
# nodes; both working references stay lower (vanilla c_rancor max 15, our
# in-game-verified Drexl max 12).  KOTOR's skinmesh bonemap limit is the last
# untested difference from known-good models.
_BONE_LIMIT = int(os.environ.get("RANCOR_BONE_LIMIT", "16"))
if _BONE_LIMIT < 16:
    wf._SKIN_PALETTE_LIMIT = _BONE_LIMIT
    print(f"bone palette limit overridden to {_BONE_LIMIT}")


def twoda_to_binary_v2b(t: TwoDA) -> bytes:
    out = bytearray(b"2DA V2.b\n")
    for col in t.columns:
        out += col.encode("ascii") + b"\t"
    out += b"\0"
    rows = len(t)
    out += struct.pack("<I", rows)
    for i in range(rows):
        out += str(i).encode("ascii") + b"\t"
    data = bytearray()
    dedup: dict[str, int] = {}
    cell_offsets: list[int] = []
    for i in range(rows):
        for col in t.columns:
            value = t.get(i, col) or ""
            off = dedup.get(value)
            if off is None:
                off = len(data)
                dedup[value] = off
                data += value.encode("cp1252", "replace") + b"\0"
            cell_offsets.append(off)
    if len(data) >= 65536:
        raise ValueError(f"2DA data block too large: {len(data)}")
    for off in cell_offsets:
        out += struct.pack("<H", off)
    out += struct.pack("<H", len(data))
    out += data
    return bytes(out)


def main() -> int:
    mgr = ResourceManager()
    assert mgr.set_k2_dir(K2), "K2 index failed"

    def donor():
        return mgr.load_model("c_rancor", "K2", prefer_base_archive=True)

    # ---- 1. fit -> rig -> split against the BIG donor ---------------------
    scene = md.CharacterScene(game_version="K2")
    scene.mode = md.CharacterMode.CREATURE
    load = wf.load_body(
        str(FBX), scene, game_version="K2",
        fit_reference_model=donor(),
        fit_reference_label="c_rancor",
        expected_mode=md.CharacterMode.CREATURE,
        allow_mode_correction=True,
    )
    assert load.ok, (load.code, load.message)

    # ---- 1b. WELD the imported mesh ---------------------------------------
    # The source FBX is fully unwelded (3 unique verts per face -> 14349 verts
    # for 4783 faces).  KOTOR's per-skin-node vertex budget is ~1900 (vanilla
    # c_rancor max) and our split nodes blew past it (Body_Rancor 6477),
    # crashing the engine's mesh sizer at swkotor2+0x4962c (T2543).  Welding
    # coincident verts (same position + UV + normal) is LOSSLESS — it only
    # removes the redundant per-face duplication, halving the count to
    # vanilla-comparable density.  Done before rig/split so the whole pipeline
    # operates on welded geometry.
    def weld_mesh_node(node, pos_tol=1.0e-5, uv_tol=1.0e-4):
        verts = list(getattr(node, "vertices", []) or [])
        faces = list(getattr(node, "faces", []) or [])
        if not verts or not faces:
            return 0, 0
        uvs = list(getattr(node, "uvs", []) or [])
        normals = list(getattr(node, "normals", []) or [])
        has_uv = len(uvs) == len(verts)
        has_nrm = len(normals) == len(verts)

        def key(i):
            v = verts[i]
            k = (round(v[0] / pos_tol), round(v[1] / pos_tol), round(v[2] / pos_tol))
            if has_uv:
                u = uvs[i]
                k += (round(u[0] / uv_tol), round(u[1] / uv_tol))
            if has_nrm:
                n = normals[i]
                k += (round(n[0] / uv_tol), round(n[1] / uv_tol), round(n[2] / uv_tol))
            return k

        remap = {}
        new_v, new_uv, new_nrm = [], [], []
        old_to_new = [0] * len(verts)
        for i in range(len(verts)):
            k = key(i)
            j = remap.get(k)
            if j is None:
                j = len(new_v)
                remap[k] = j
                new_v.append(verts[i])
                if has_uv:
                    new_uv.append(uvs[i])
                if has_nrm:
                    new_nrm.append(normals[i])
            old_to_new[i] = j
        new_faces = []
        for f in faces:
            a, b, cc = old_to_new[int(f[0])], old_to_new[int(f[1])], old_to_new[int(f[2])]
            if a != b and b != cc and a != cc:
                new_faces.append((a, b, cc))
        before = len(verts)
        node.vertices = new_v
        node.faces = new_faces
        if has_uv:
            node.uvs = new_uv
        if has_nrm:
            node.normals = new_nrm
        for attr in ("tangents", "face_uvs", "skin_data", "bone_map_floats"):
            # per-vertex arrays that no longer align are cleared; the rig/bind
            # step regenerates skin data from the welded geometry.
            if attr in ("skin_data",) and getattr(node, attr, None):
                node.skin_data = []
        return before, len(new_v)

    if "--no-weld" not in sys.argv:
        for n in list(load.model.all_nodes()):
            if getattr(n, "vertices", None) and getattr(n, "faces", None):
                b, a = weld_mesh_node(n)
                if b != a:
                    print(f"weld: {getattr(n,'name','?')} {b} -> {a} verts "
                          f"({100*(b-a)/b:.0f}% reduction)")

    # ---- 1c. DECIMATE to KOTOR density ------------------------------------
    # Welding alone left Body_Rancor at 2435 verts (> vanilla's 1899 per-node
    # ceiling) and it STILL crashed at 0x4962c.  KOTOR skin nodes must stay
    # well under that; the proven-safe reference is our working Drexl (max
    # 1059/node).  Decimate the welded mesh (quadric collapse) to a target
    # keep-ratio, transferring UV/normal from the nearest pre-decimation
    # vertex, so every split region lands under ~1200 verts.
    decimate_keep = float(os.environ.get("RANCOR_DECIMATE_KEEP", "0.45"))
    if "--no-decimate" not in sys.argv and decimate_keep < 0.999:
        import numpy as np
        import fast_simplification
        from scipy.spatial import cKDTree
        for n in list(load.model.all_nodes()):
            verts = list(getattr(n, "vertices", []) or [])
            faces = list(getattr(n, "faces", []) or [])
            if len(verts) < 600 or len(faces) < 200:
                continue
            uvs = list(getattr(n, "uvs", []) or [])
            normals = list(getattr(n, "normals", []) or [])
            pts = np.asarray([(float(v[0]), float(v[1]), float(v[2])) for v in verts], dtype=np.float32)
            fac = np.asarray([(int(f[0]), int(f[1]), int(f[2])) for f in faces], dtype=np.int32)
            new_pts, new_fac = fast_simplification.simplify(
                pts, fac, target_reduction=1.0 - decimate_keep
            )
            tree = cKDTree(pts)
            _, nn = tree.query(new_pts, k=1)
            n.vertices = [tuple(float(c) for c in p) for p in new_pts]
            n.faces = [tuple(int(i) for i in f) for f in new_fac]
            if len(uvs) == len(verts):
                n.uvs = [uvs[int(j)] for j in nn]
            if len(normals) == len(verts):
                n.normals = [normals[int(j)] for j in nn]
            if getattr(n, "skin_data", None):
                n.skin_data = []
            print(f"decimate: {getattr(n,'name','?')} {len(verts)} -> {len(new_pts)} verts "
                  f"(keep {decimate_keep:.0%})")

    rig = cb.apply_template_rig(load.model, donor(), game="K2")
    assert rig.get("ok"), rig.get("message")
    rigged = rig["model"]
    zs = [v[2] for n in rigged.all_nodes() for v in (getattr(n, "vertices", []) or [])]
    print(f"rig: name={rigged.name} anim_scale={rigged.anim_scale} "
          f"supermodel={rigged.supermodel} anims={len(rigged.animations)} "
          f"height={max(zs)-min(zs):.3f}")

    scene.assign(
        md.PartSlot.HEADLESS_BODY, rigged,
        resref=RESREF, game_version="K2", source_path=str(FBX),
    )
    split = wf.split_imported_mesh_nodes(
        scene, respect_skinned="split_with_weight_remap",
        reference_model=donor(),
    )
    assert split.get("ok"), (split.get("code"), split.get("message"))
    print(f"split: {split.get('code')} nodes={split.get('split_nodes')}")

    # ---- 2. inline static seam check (same math as the diag) --------------
    import numpy as np
    from scipy.spatial import cKDTree

    parts = [
        n for n in rigged.all_nodes()
        if getattr(n, "is_skin", False) and getattr(n, "vertices", None)
        and getattr(n, "skin_data", None) and getattr(n, "bone_map", None)
    ]

    # T2550: qBone/tBone is an inverse-bind transform, not the bone's forward
    # world transform.  Keep this as a build-time engine contract so a parser-
    # clean but explosively deformed boss can never be staged again.
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.math.gpu_math import _matrix_from_pos_quat_np

    def assert_inverse_bind_contract(model, skin_nodes, *, node_indexed):
        nodes = list(model.all_nodes())
        by_name = {
            str(getattr(node, "name", "") or "").strip().lower(): node
            for node in nodes
            if str(getattr(node, "name", "") or "").strip()
        }
        max_error = 0.0
        checked = 0
        for skin_node in skin_nodes:
            skin_pos, skin_rot = wf._node_world_transform_or_local(skin_node)
            skin_world = _matrix_from_pos_quat_np(skin_pos, skin_rot)
            qbones = list(getattr(skin_node, "qbone_list", []) or [])
            tbones = list(getattr(skin_node, "tbone_list", []) or [])
            for slot, raw_name in enumerate(list(skin_node.bone_map or [])):
                name = str(raw_name or "").strip().lower()
                assert name in by_name, (skin_node.name, raw_name)
                bone = by_name[name]
                bind_index = nodes.index(bone) if node_indexed else slot
                assert 0 <= bind_index < len(qbones), (
                    skin_node.name, raw_name, bind_index, len(qbones)
                )
                assert 0 <= bind_index < len(tbones), (
                    skin_node.name, raw_name, bind_index, len(tbones)
                )
                bone_pos, bone_rot = wf._node_world_transform_or_local(bone)
                bone_world = _matrix_from_pos_quat_np(bone_pos, bone_rot)
                inverse_bind = np.asarray(
                    MatrixPaletteUploader.qbone_inverse_bind_matrix_g5(
                        qbones[bind_index], tbones[bind_index]
                    ),
                    dtype=np.float64,
                )
                error = float(np.max(np.abs((bone_world @ inverse_bind) - skin_world)))
                max_error = max(max_error, error)
                checked += 1
        tolerance = 1.0e-4 if node_indexed else 1.0e-6
        assert max_error <= tolerance, (max_error, tolerance, checked)
        return checked, max_error

    bind_checked, bind_error = assert_inverse_bind_contract(
        rigged, parts, node_indexed=False
    )
    donor_ambient = wf._reference_skin_ambient(donor())
    assert donor_ambient is not None
    assert all(
        tuple(float(value) for value in part.ambient[:3])
        == tuple(float(value) for value in donor_ambient)
        for part in parts
    )
    print(
        f"inverse-bind gate: {bind_checked} palette rows, "
        f"max_error={bind_error:.3g}; ambient={donor_ambient}"
    )

    points, owners = [], []
    for pi, part in enumerate(parts):
        world = wf._node_world_vertices_for_split(part, np)
        for vi in range(world.shape[0]):
            points.append(world[vi]); owners.append((pi, vi))
    tree = cKDTree(np.asarray(points))
    pairs = tree.query_pairs(r=5e-4, output_type="ndarray")
    worst = 0.0
    bad = 0
    for a, b in pairs:
        pa, va = owners[int(a)]; pb, vb = owners[int(b)]
        wa = effective_weights_by_name(parts[pa].skin_data[va], [str(x) for x in parts[pa].bone_map])
        wb = effective_weights_by_name(parts[pb].skin_data[vb], [str(x) for x in parts[pb].bone_map])
        d = weight_delta(wa, wb)
        worst = max(worst, d)
        if d > 1e-4:
            bad += 1
    print(f"seam check: {len(pairs)} coincident pairs, divergent={bad}, worst_delta={worst:.6f}")
    assert bad == 0, "seam weight divergence detected on big-donor build"

    # ---- 2b. resref rename (geometry-header name only) --------------------
    # KOTOR resolves a creature's model file from appearance.2da's race column
    # (== the .mdl filename); the model's geometry-header name (MDL +0x14,
    # written from model.name) should match it (T2538 — dat_rancor.mdl carried
    # the base name 'c_rancor').  ONLY model.name is renamed: the root NODE
    # name and every anim_root stay 'c_rancor' so (a) they remain mutually
    # consistent and animations still bind, and (b) the export transaction's
    # node-path + provenance checks — which key off the root node and the
    # native-base snapshot, NOT model.name — still pass.
    old_name = str(rigged.name)
    rigged.name = RESREF
    print(f"resref rename: geometry-header name '{old_name}' -> '{RESREF}' "
          f"(root node + anim_root stay '{old_name}')")

    mdl = OUT / f"{RESREF}.mdl"
    mdx = OUT / f"{RESREF}.mdx"

    # ---- 3. export ---------------------------------------------------------
    if "--no-anim" in sys.argv:
        # T2547 isolation probe: strip animations and write the MDL DIRECTLY
        # with the binary writer, bypassing the character export transaction
        # (which hard-requires the inherited animation set).  This produces a
        # loadable geometry-only model to bisect anim-data vs geometry/skin as
        # the plcaa area-load crash source.
        try:
            rigged.animations = []
        except Exception:
            pass
        if "--rigid" in sys.argv:
            # T2547b: strip skin to isolate skin-writer bugs vs base trimesh.
            try:
                from core.geometry.model_data import NodeFlags  # type: ignore
            except Exception:
                from src.core.geometry.model_data import NodeFlags  # type: ignore
            n_rigid = 0
            for nd in rigged.all_nodes():
                if getattr(nd, "is_skin", False):
                    try:
                        nd.flags = int(getattr(nd, "flags", 0)) & ~int(NodeFlags.SKIN)
                        nd.skin_data = []
                        nd.bone_map = []
                        nd.bone_map_floats = []
                        nd.qbone_list = []
                        nd.tbone_list = []
                        n_rigid += 1
                    except Exception:
                        pass
            print(f"RIGID PROBE: stripped skin from {n_rigid} nodes")
        from src.core.mdl.mdl_writer import MDLBinaryWriter
        mdl_bytes, mdx_bytes = MDLBinaryWriter().write(rigged)
        mdl.write_bytes(mdl_bytes)
        mdx.write_bytes(mdx_bytes)
        print(f"NO-ANIM PROBE: raw-wrote {mdl.name} ({len(mdl_bytes)} B) / "
              f"{mdx.name} ({len(mdx_bytes)} B), animations stripped")
    else:
        result = wf.export_scene(scene, formats=["kotor"], out_dir=str(OUT), write_sidecar=True)
        rows = list(getattr(result, "formats", []) or [])
        for row in rows:
            print(f"  [{row.key}] ok={row.ok} {row.message[:140]}")
        kotor_rows = [r for r in rows if r.key == "kotor"]
        assert kotor_rows and kotor_rows[0].ok, "kotor export failed"
    assert mdl.is_file() and mdx.is_file()

    from src.core.game.kotor_loader import load_model_from_bytes
    reloaded = load_model_from_bytes(mdl.read_bytes(), mdx.read_bytes())
    assert reloaded is not None
    # Geometry-header name (MDL +0x14) must equal the file resref (T2538);
    # root node + anim_root intentionally stay at the base name for internal
    # consistency / animation binding.
    internal_name = mdl.read_bytes()[20:52].split(b"\x00", 1)[0].decode("ascii", "replace")
    assert internal_name.lower() == RESREF, (
        f"geometry-header name {internal_name!r} != resref {RESREF!r} — "
        "engine may silently drop this creature"
    )
    assert str(reloaded.name).lower() == RESREF, reloaded.name
    root_name = str(reloaded.root_node.name)
    anim_roots = {str(getattr(a, "anim_root", "")) for a in reloaded.animations}
    print(f"internal names: header={internal_name} root_node={root_name} "
          f"anim_root={sorted(anim_roots)}")
    assert anim_roots <= {root_name}, (
        f"anim_root {anim_roots} inconsistent with root node {root_name!r}"
    )
    texs = sorted({
        str(getattr(n, "texture", "") or "") for n in reloaded.all_nodes()
        if getattr(n, "is_skin", False)
    })
    print(f"reload: internal_name={internal_name} anim_scale={reloaded.anim_scale} "
          f"supermodel={reloaded.supermodel} "
          f"anims={len(reloaded.animations)} skin_textures={texs}")
    reloaded_parts = [
        n for n in reloaded.all_nodes()
        if getattr(n, "is_skin", False) and getattr(n, "vertices", None)
        and getattr(n, "bone_map", None)
    ]
    reload_bind_checked, reload_bind_error = assert_inverse_bind_contract(
        reloaded, reloaded_parts, node_indexed=True
    )
    print(
        f"reload inverse-bind gate: {reload_bind_checked} palette rows, "
        f"max_error={reload_bind_error:.3g}"
    )
    body_tex = next((t for t in texs if t.lower().startswith(RESREF)), None)
    assert body_tex, f"no {RESREF}* texture reference found: {texs}"

    # ---- 4. texture under the renamed resref -------------------------------
    src_tga = OUT / "rancortamedc_t00.tga"   # same pixels from the first export
    dst_tga = OUT / f"{body_tex.lower()}.tga"
    # T2551: the Odyssey engine mis-samples textures above 2048 (working
    # Drexl ships 2048) — downscale to the KOTOR cap.
    # T2552: the engine also reads the TGA rows in the OPPOSITE vertical
    # order from what our texture pipeline emits for this source: with
    # face-level UV fidelity proven perfect, the unflipped 2048 atlas still
    # rendered as confetti; a vertical row flip snapped the wrapping correct
    # in the live game.  Bake the flip here.
    from PIL import Image, ImageOps
    KOTOR_MAX_TEX = int(os.environ.get("RANCOR_MAX_TEX", "2048"))
    img = Image.open(src_tga).convert("RGBA")
    if max(img.size) > KOTOR_MAX_TEX:
        img = img.resize((KOTOR_MAX_TEX, KOTOR_MAX_TEX), Image.LANCZOS)
    img = ImageOps.flip(img)   # vertical row flip — verified live (T2552)
    img.save(dst_tga)
    print(f"texture: {dst_tga.name} {img.size[0]}x{img.size[1]} V-flipped "
          f"({dst_tga.stat().st_size} B)")
    import struct as _struct
    _tw, _th = _struct.unpack_from("<HH", dst_tga.read_bytes(), 12)
    assert max(_tw, _th) <= KOTOR_MAX_TEX, f"texture still {_tw}x{_th}"

    # ---- 5. appearance.2da: effective copy + new row -----------------------
    # Read the VANILLA 2DA from the KEY/BIF archive, never Override — reading
    # our own previously-staged appearance.2da back would append a DUPLICATE
    # dat_rancor row each rebuild (T2541: row index drifted 671 -> 672).
    inst_k2 = mgr.get_k2()
    vanilla_2da = (
        inst_k2.get_bif("appearance", RES_2DA)
        if hasattr(inst_k2, "get_bif") else None
    ) or mgr.get("appearance", RES_2DA, "K2")
    t = TwoDA.from_bytes(vanilla_2da)
    # Idempotent: if a prior dat_rancor row leaked into the source, reuse it.
    race_col = t.col_index("race")
    label_col = t.col_index("label")
    existing = [i for i in range(len(t)) if (t.get(i, "race") or "").lower() == RESREF]
    assert not existing, f"vanilla 2DA already has {RESREF} rows {existing} — not vanilla"
    new_index = len(t)
    template_row = list(t._rows[80])
    t._rows.append(template_row[:])
    t._rows[new_index][race_col] = RESREF
    t._rows[new_index][label_col] = "Creature_Rancor_Dathomir"
    blob = twoda_to_binary_v2b(t)
    # round-trip verification: every cell of every row must survive
    t2 = TwoDA.from_bytes(blob)
    assert len(t2) == new_index + 1
    for i in (0, 80, 309, new_index):
        for col in t.columns:
            assert (t2.get(i, col) or "") == (t.get(i, col) or ""), (i, col)
    assert t2.get(new_index, "race") == RESREF
    (OUT / "appearance.2da").write_bytes(blob)
    print(f"appearance.2da: row {new_index} race={RESREF} "
          f"({len(blob)} B, round-trip verified)")

    # ---- 6. boss UTC --------------------------------------------------------
    gff = read_gff(mgr.get_k2().get("g_rancor01", RES_UTC))
    root = gff.root
    root["Appearance_Type"] = new_index
    root["Tag"] = UTC_RESREF
    tr = root.fields["TemplateResRef"]
    tr.value = type(tr.value)(UTC_RESREF)
    first_name = root.fields.get("FirstName")
    if first_name is not None and hasattr(first_name.value, "set_text"):
        first_name.value.set_text("Dathomir Rancor")
    # Playtest tuning (T2546): stock g_rancor01 is a CR-20 boss with Str 45
    # (+17 melee damage) — a one-hit kill on a low-level test character.
    # Drop it to a survivable-but-threatening profile.  Overridable via env.
    stat_overrides = {
        "Str": int(os.environ.get("RANCOR_STR", "16")),   # +3 dmg (was 45/+17)
        "HitPoints": int(os.environ.get("RANCOR_HP", "80")),
        "CurrentHitPoints": int(os.environ.get("RANCOR_HP", "80")),
        "MaxHitPoints": int(os.environ.get("RANCOR_HP", "80")),
        "ChallengeRating": float(os.environ.get("RANCOR_CR", "6")),
    }
    for field_name, value in stat_overrides.items():
        fld = root.fields.get(field_name)
        if fld is not None:
            fld.value = type(fld.value)(value)
    # T2553: stats alone don't govern damage — stock g_rancor01 dual-wields
    # g_w_crslash006 creature claws (monster damage 10d6 EACH, decoded via
    # iprp_monstcost row 17), which one-shots a test character regardless of
    # Str.  Swap to a survivable claw; the family is a clean damage dial:
    # crslash001=1d4, 002=1d6, 003=1d10, 005=3d6, 004=2d12, 006=10d6.
    claw = os.environ.get("RANCOR_CLAW", "g_w_crslash002")   # 1d6
    equip = root.fields.get("Equip_ItemList")
    swapped = 0
    if equip is not None:
        for slot_struct in equip.value:
            res_field = slot_struct.fields.get("EquippedRes")
            if res_field is not None:
                res_field.value = type(res_field.value)(claw)
                swapped += 1
    print(f"utc stats: Str={stat_overrides['Str']} HP={stat_overrides['HitPoints']} "
          f"CR={stat_overrides['ChallengeRating']} claws={swapped}x{claw} "
          f"(was Str 45 / HP 350 / CR 20 / 2x g_w_crslash006=10d6)")
    utc_bytes = write_gff(gff)
    check = read_gff(utc_bytes)
    assert check.root.fields["Appearance_Type"].value == new_index
    assert str(check.root.fields["TemplateResRef"].value) in (UTC_RESREF, f"ResRef('{UTC_RESREF}')")
    (OUT / f"{UTC_RESREF}.utc").write_bytes(utc_bytes)
    print(f"utc: {UTC_RESREF}.utc appearance={new_index} "
          f"({len(utc_bytes)} B, reparse verified)")

    manifest = {
        "resref": RESREF,
        "utc": UTC_RESREF,
        "appearance_row": new_index,
        "files": {
            f.name: f.stat().st_size
            for f in (mdl, mdx, dst_tga, OUT / "appearance.2da", OUT / f"{UTC_RESREF}.utc")
        },
    }
    (OUT / "dathomir_rancor_package.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print("package manifest written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
