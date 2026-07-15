"""Deploy the Sith Ithorian package to K1 and place both NPCs in ShaolinTestsMap.

1. Copies the built package (models, textures, appearance.2da, UTCs) into the
   K1 Override, backing up anything it would replace.
2. Adds two GIT creature instances to ShaolinTestsMap.mod — 'Sith Lord'
   (sithlord01) and 'Sith Scholar' (sithschol01) — cloned from a vanilla K1
   GIT creature struct (danm13's m13aa, so the field set is K1-exact:
   TemplateResRef + X/Y/ZPosition + X/YOrientation, no K2 Bearing).
   Positions sit inside the room walkmesh (X/Y -5..5, entry (0,-3)), facing
   the entry point.  Idempotent: prior sith placements are stripped first.
3. Clears the stale currentgame/ShaolinTestsMap.mod cache copy.
4. Verifies: reparsed GIT, Override-resolved appearance rows, and model load.
"""
from __future__ import annotations

import copy
import datetime
import pathlib
import shutil
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Math/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

from src.core.assets.resource_manager import ResourceManager, _ErfIndex, RES_2DA  # noqa: E402
from src.core.modules import module_save_pipeline as msp  # noqa: E402
from src.core.templates.twoda import TwoDA  # noqa: E402
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402

K1 = pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
PKG = pathlib.Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
MOD = K1 / "modules" / "ShaolinTestsMap.mod"
GIT_AREA = "shaolintestsmap"
RES_GIT = 2023
ID_TO_EXT = {v: k for k, v in msp.RESTYPE_IDS.items()}

DEPLOY_FILES = [
    "c_ithlord.mdl", "c_ithlord.mdx", "c_ithlord_t00.tga",
    "c_ithschol.mdl", "c_ithschol.mdx", "c_ithschol_t00.tga",
    "appearance.2da", "sithlord01.utc", "sithschol01.utc",
]

PLACEMENTS = [
    # (utc resref, x, y, z, x_orient, y_orient) — facing -Y toward entry (0,-3)
    ("sithlord01", -1.8, 2.2, 0.0, 0.0, -1.0),
    ("sithschol01", 1.8, 2.2, 0.0, 0.0, -1.0),
]


def vanilla_k1_git_creature_struct():
    """Clone donor: first creature struct of danm13's m13aa GIT."""
    rim = (K1 / "modules" / "danm13.rim").read_bytes()
    assert rim[:8] == b"RIM V1.0", rim[:8]
    cnt, off = struct.unpack_from("<II", rim, 0x0C)
    for i in range(cnt):
        e = off + i * 32
        rt, _idx, roff, rsize = struct.unpack_from("<IIII", rim, e + 16)
        if rt == RES_GIT:
            git = read_gff(rim[roff:roff + rsize])
            return copy.deepcopy(git.root.fields["Creature List"].value[0])
    raise AssertionError("no GIT in danm13.rim")


def main() -> int:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # ---- 1. Override deploy -------------------------------------------------
    override = K1 / "Override"
    for name in DEPLOY_FILES:
        src = PKG / name
        assert src.is_file(), f"package file missing: {src}"
        dst = override / name
        if dst.exists():
            backup = override / f"{name}.pre_sith_{stamp}.bak"
            shutil.copy2(dst, backup)
            print(f"backup: {backup.name}")
        shutil.copy2(src, dst)
        print(f"override: {name} ({src.stat().st_size} B)")

    # ---- 2. GIT placement ---------------------------------------------------
    assert MOD.is_file(), MOD
    idx = _ErfIndex(str(MOD))
    keys = list(idx._index.keys())
    git = read_gff(idx.read(GIT_AREA, RES_GIT))
    creature_list = git.root.fields["Creature List"].value
    placed_refs = {p[0] for p in PLACEMENTS}
    creature_list[:] = [
        c for c in creature_list
        if str(c.fields.get("TemplateResRef").value) not in placed_refs
    ]
    donor = vanilla_k1_git_creature_struct()
    for ref, x, y, z, xo, yo in PLACEMENTS:
        inst = copy.deepcopy(donor)
        f = inst.fields
        f["TemplateResRef"].value = type(f["TemplateResRef"].value)(ref)
        f["XPosition"].value = float(x)
        f["YPosition"].value = float(y)
        f["ZPosition"].value = float(z)
        f["XOrientation"].value = float(xo)
        f["YOrientation"].value = float(yo)
        creature_list.append(inst)
        print(f"placed {ref} at ({x:.1f}, {y:.1f}, {z:.1f}) facing "
              f"({xo:.0f},{yo:.0f})")
    new_git = write_gff(git)

    entries = []
    for k in keys:
        resref, _, rt_str = k.rpartition(":")
        rt_id = int(rt_str)
        data = new_git if (rt_id == RES_GIT and resref == GIT_AREA) else idx.read(resref, rt_id)
        assert data, (resref, rt_id)
        ext = ID_TO_EXT.get(rt_id)
        assert ext is not None, f"unknown restype {rt_id} for {resref}"
        entries.append(msp.ModuleArchiveEntry(
            resref=resref, restype=ext, data=data,
            archive_role=msp._archive_role(ext) if hasattr(msp, "_archive_role") else "module",
            source="ShaolinTestsMap.mod", changed=(rt_id == RES_GIT),
            serializer="sith_ithorian_placement", warning=None,
        ))
    blob = msp.build_erf_v1_archive(entries, archive_type="MOD")
    backup = MOD.with_name(f"ShaolinTestsMap.mod.pre_sith_{stamp}.bak")
    shutil.copy2(MOD, backup)
    MOD.write_bytes(blob)
    print(f"module backup: {backup.name}")
    print(f"module written: {MOD.name} ({len(blob)} B, {len(entries)} resources)")

    # ---- 3. clear currentgame cache -----------------------------------------
    for cached in (K1 / "currentgame").glob("ShaolinTestsMap.mod"):
        cached.unlink()
        print(f"cleared cache: {cached}")

    # ---- 4. verify -----------------------------------------------------------
    idx2 = _ErfIndex(str(MOD))
    git2 = read_gff(idx2.read(GIT_AREA, RES_GIT))
    refs = [str(c.fields["TemplateResRef"].value)
            for c in git2.root.fields["Creature List"].value]
    print(f"verify GIT: creatures = {refs}")
    assert all(p[0] in refs for p in PLACEMENTS)
    assert set(idx2._index.keys()) == set(keys)

    mgr = ResourceManager()
    assert mgr.set_k1_dir(str(K1))
    t = TwoDA.from_bytes(mgr.get("appearance", RES_2DA, "K1"))
    rows = {
        (t.get(i, "race") or "").lower(): i
        for i in range(len(t))
        if (t.get(i, "race") or "").lower() in ("c_ithlord", "c_ithschol")
    }
    print(f"verify appearance (Override-resolved): {rows}, total rows {len(t)}")
    assert rows == {"c_ithlord": 509, "c_ithschol": 510}, rows
    for resref in ("c_ithlord", "c_ithschol"):
        m = mgr.load_model(resref, "K1")
        assert m is not None and len(m.animations) >= 280, resref
        clips = {str(a.name or "").lower() for a in m.animations}
        # T2565: full N_DarkJediM inventory + creature contract + natives.
        for needed in ("g0a1", "g0a2", "creadyr", "castout1", "castoutlp1",
                       "horror", "choke", "sleep", "paralyzed",
                       "c2a1", "c2d1", "g2a1", "walk", "pause1",
                       "cdamages", "cwalk", "tlknorm"):
            assert needed in clips, (resref, needed)
        hooks = {str(n.name or "").lower() for n in m.all_nodes()}
        assert "rhand" in hooks and "lhand" in hooks, "saber hand hooks missing"
        print(f"verify model: {resref} loads, {len(m.animations)} anims "
              f"(saber attacks, cast, victim clips, rhand/lhand hooks present)")
    # Engine-side assignment: animations.2da rows 276/277 must still name the
    # creature attack clips the resolver returns (base+0x114/0x115).
    anim2da = TwoDA.from_bytes(mgr.get("animations", RES_2DA, "K1"))
    assert (anim2da.get(276, "name") or "").lower() == "g0a1", anim2da.get(276, "name")
    assert (anim2da.get(277, "name") or "").lower() == "g0a2", anim2da.get(277, "name")
    print("verify animations.2da: row 276=g0a1, row 277=g0a2 (creature attack contract)")
    print("\nOK — warp ShaolinTestsMap: Sith Lord (left) and Sith Scholar "
          "(right) stand across from the entry point.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
