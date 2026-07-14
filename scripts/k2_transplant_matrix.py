"""Transplant bisection: isolate the bad plcaa resource inside a proven module.

tst_light.mod loads in K2. Build variants of it renamed to plcaa, swapping in
our generated room resources one at a time:

  t2  control: tst_light guts, module identity renamed to plcaa
  t3  our room: plcaa.mdl/.mdx/.wok + LYT/ARE room entry (rest tst_light)
  t4  our WOK only (tst_light room model, our walkmesh, room name r00_test)
  t5  our MDL/MDX only (our room model, tst_light walkmesh)

Usage: py -3.14 scripts/k2_transplant_matrix.py t2|t3|t4|t5
Writes artifacts/map_studio/k2_transplants/plcaa.mod
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

from pykotor.extract.capsule import LazyCapsule
from pykotor.resource.formats.erf import ERF, ERFType, write_erf
from pykotor.resource.formats.gff import bytes_gff, read_gff
from pykotor.resource.type import ResourceType as RT

K2M = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II\Modules")
OUT = ROOT / "artifacts" / "map_studio" / "k2_transplants"
OUT.mkdir(parents=True, exist_ok=True)

variant = (sys.argv[1] if len(sys.argv) > 1 else "t2").lower()

tst = LazyCapsule(K2M / "tst_light.mod")
resources = {(i.resref().lower(), i.restype()): bytes(i.data()) for i in tst}

ours_path = ROOT / "artifacts" / "map_studio" / "k2_plcaa_test_map" / "install" / "Modules" / "plcaa.mod"
ours = LazyCapsule(ours_path)
our_res = {(i.resref().lower(), i.restype()): bytes(i.data()) for i in ours}

# --- module identity rename: tst_light -> plcaa -------------------------
out: dict[tuple[str, RT], bytes] = {}
for (resref, rtype), data in resources.items():
    new_ref = "plcaa" if resref == "tst_light" else resref
    out[(new_ref, rtype)] = data

# IFO: entry area + area list must say plcaa
ifo = read_gff(out[("module", RT.IFO)])
ifo.root.set_resref("Mod_Entry_Area", "plcaa")
areas = ifo.root.acquire("Mod_Area_list", None)
if areas is not None:
    for entry in areas:
        entry.set_resref("Area_Name", "plcaa")
out[("module", RT.IFO)] = bytes_gff(ifo)

ROOM = "r00_test"
if variant in ("t3", "t5"):
    ROOM = "plcaa"

if variant == "t3":
    # our full room: mdl/mdx/wok swap + drop tst_light room files
    for rtype in (RT.MDL, RT.MDX, RT.WOK):
        out.pop(("r00_test", rtype), None)
        out[("plcaa", rtype)] = our_res[("plcaa", rtype)]
elif variant == "t4":
    # our WOK under the tst_light room name (walkmesh-only swap)
    out[("r00_test", RT.WOK)] = our_res[("plcaa", RT.WOK)]
elif variant == "t5":
    # our MDL/MDX, tst_light WOK renamed to match our room name
    for rtype in (RT.MDL, RT.MDX):
        out.pop(("r00_test", rtype), None)
        out[("plcaa", rtype)] = our_res[("plcaa", rtype)]
    wok = out.pop(("r00_test", RT.WOK))
    out[("plcaa", RT.WOK)] = wok

if ROOM == "plcaa":
    # LYT + VIS + ARE Rooms follow the room rename
    lyt = out[("plcaa", RT.LYT)].decode("latin-1").replace("r00_test", "plcaa")
    out[("plcaa", RT.LYT)] = lyt.encode("latin-1")
    vis = out[("plcaa", RT.VIS)].decode("latin-1").replace("r00_test", "plcaa")
    out[("plcaa", RT.VIS)] = vis.encode("latin-1")
    are = read_gff(out[("plcaa", RT.ARE)])
    rooms = are.root.acquire("Rooms", None)
    if rooms is not None:
        for entry in rooms:
            entry.set_string("RoomName", "plcaa")
    out[("plcaa", RT.ARE)] = bytes_gff(are)

erf = ERF(ERFType.MOD)
for (resref, rtype), data in sorted(out.items(), key=lambda kv: (kv[0][0], kv[0][1].extension)):
    erf.set_data(resref, rtype, data)
target = OUT / "plcaa.mod"
write_erf(erf, target)
print(f"variant {variant}: wrote {target} with {len(out)} resources; room={ROOM}")
for (resref, rtype) in sorted(out, key=lambda k: (k[0], k[1].extension)):
    print(f"  {resref}.{rtype.extension}")
