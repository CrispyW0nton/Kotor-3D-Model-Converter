"""Place the Dathomir Rancor boss into tst_light via a GIT creature instance.

Mirrors the existing Drexl setup: tst_light.mod's GIT carries one creature
(g_drexl_amb01) whose model is overridden from Override.  This adds a second
creature instance pointing at our boss UTC dat_rancor01 (appearance row 671
-> dat_rancor model, already staged in Override), then repackages the .mod
with the stock ERF/MOD builder.  No console command needed — warp to
tst_light and the boss is standing there.

Backs up the original tst_light.mod first and verifies the repackaged GIT
reparses with both creatures.
"""
from __future__ import annotations

import copy
import datetime
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "",
):
    p = str(ROOT / rel) if rel else str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

K2 = pathlib.Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")
MOD = K2 / "Modules" / "tst_light.mod"
STAGE = ROOT / "Saved" / "GameTestStaging"
# Default: the VANILLA big-rancor template (appearance row 80 -> model
# c_rancor, which our Override shadows).  This keeps the live test down to a
# single variable — the custom model.  Pass --utc <resref> to place a custom
# template instead (e.g. dat_rancor01 once the resref-rename export exists).
UTC_RESREF = "g_rancor01"
if "--utc" in sys.argv:
    UTC_RESREF = sys.argv[sys.argv.index("--utc") + 1]

from src.core.assets.resource_manager import _ErfIndex, _key  # noqa: E402
from src.core.modules import module_save_pipeline as msp  # noqa: E402
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402

RES_GIT = 2023
ID_TO_EXT = {v: k for k, v in msp.RESTYPE_IDS.items()}


def main() -> int:
    assert MOD.is_file(), f"missing {MOD}"
    idx = _ErfIndex(str(MOD))
    keys = list(idx._index.keys())  # "resref:restype_id"
    print(f"tst_light.mod resources: {len(keys)}")

    # --- read + modify the GIT ---------------------------------------------
    git_bytes = idx.read("tst_light", RES_GIT)
    assert git_bytes, "no GIT in tst_light.mod"
    git = read_gff(git_bytes)
    creature_list = git.root.fields["Creature List"].value
    assert creature_list, "GIT has no creatures to clone"
    donor = creature_list[0]
    donor_ref = str(donor.fields["TemplateResRef"].value)
    print(f"donor creature: {donor_ref} at "
          f"({donor.fields['XPosition'].value:.2f}, {donor.fields['YPosition'].value:.2f})")

    # Remove any prior rancor placements (idempotent re-runs, any variant).
    creature_list[:] = [
        c for c in creature_list
        if str(c.fields.get("TemplateResRef").value) not in
        (UTC_RESREF, "dat_rancor01", "g_rancor01", "g_rancor02")
    ]

    boss = copy.deepcopy(donor)
    boss.fields["TemplateResRef"].value = type(donor.fields["TemplateResRef"].value)(UTC_RESREF)
    boss.fields["Tag"].value = UTC_RESREF
    # Position must be INSIDE the r00_test walkmesh (X -8.17..9.10,
    # Y -23.08..8.25 — parsed from the module's WOK); the first attempt at
    # Y=10.0 was out of bounds and the engine silently dropped the spawn.
    # The room opens toward -Y, so the big boss gets floor space there,
    # facing +Y back toward the entrance and the Drexl.
    boss.fields["XPosition"].value = 0.0
    boss.fields["YPosition"].value = -8.0
    boss.fields["ZPosition"].value = float(donor.fields["ZPosition"].value)
    boss.fields["XOrientation"].value = 0.0
    boss.fields["YOrientation"].value = 1.0
    boss.fields["Bearing"].value = 0.0
    creature_list.append(boss)
    print(f"placed {UTC_RESREF} at (0.00, -8.00) facing +Y; creatures now: {len(creature_list)}")

    new_git = write_gff(git)

    # --- repackage every resource, GIT swapped ------------------------------
    entries = []
    for k in keys:
        resref, _, rt_str = k.rpartition(":")
        rt_id = int(rt_str)
        data = new_git if rt_id == RES_GIT else idx.read(resref, rt_id)
        if not data:
            continue
        ext = ID_TO_EXT.get(rt_id)
        if ext is None:
            print(f"WARNING: unknown restype id {rt_id} for {resref}; skipped")
            continue
        entries.append(msp.ModuleArchiveEntry(
            resref=resref, restype=ext, data=data,
            archive_role=msp._archive_role(ext) if hasattr(msp, "_archive_role") else "module",
            source="tst_light.mod", changed=(rt_id == RES_GIT),
            serializer="rancor_placement", warning=None,
        ))
    blob = msp.build_erf_v1_archive(entries, archive_type="MOD")
    print(f"repackaged .mod: {len(entries)} resources, {len(blob)} B")

    # --- backup + write -----------------------------------------------------
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    STAGE.mkdir(parents=True, exist_ok=True)
    backup = STAGE / f"tst_light_mod_backup_{stamp}.mod"
    shutil.copy2(MOD, backup)
    MOD.write_bytes(blob)
    print(f"backup: {backup}")
    print(f"wrote:  {MOD}")

    # Drop any stale currentgame copy so the edited module is the one loaded.
    cg = K2 / "currentgame" / "tst_light.mod"
    if cg.exists():
        cg.unlink()
        print(f"removed stale {cg}")

    # --- verify -------------------------------------------------------------
    idx2 = _ErfIndex(str(MOD))
    git2 = read_gff(idx2.read("tst_light", RES_GIT))
    refs = [str(c.fields["TemplateResRef"].value) for c in git2.root.fields["Creature List"].value]
    print(f"verify: reparsed creature list = {refs}")
    assert UTC_RESREF in refs, "boss not present after repackage"
    assert donor_ref in refs, "donor creature lost"
    assert set(idx2._index.keys()) == set(keys), "resource set changed"
    print("OK: tst_light now contains the Drexl reference + the Rancor boss.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
