"""K2 PLCaa gameplay milestone: shell port + staging + scripted puzzle.

Builds the user's test map headlessly, end to end:
  Stage 1  K1 plcaa geometry -> strip demo objects/scripts -> retarget to K2,
           bundling the K1 textures/lightmaps the shell needs.
  Stage 2  Stage gameplay in cordoned zones: assassin-droid enemies, a
           merchant (store + shop terminal), placeable containers; cordon
           pillars raised with GModeler extrudes.
  Stage 3  Naga Sadow-style puzzle: three pedestals used in order unlock a
           door — custom UTP/UTD templates + NSS compiled to NCS, all
           bundled into the module.
Everything is verified by reading the packaged .mod back with PyKotor.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import replace as dc_replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots

for item in reversed(_python_roots(ROOT)):
    text = str(item)
    if text not in sys.path:
        sys.path.insert(0, text)

logging.disable(logging.CRITICAL)

from pykotor.extract.capsule import LazyCapsule
from pykotor.resource.formats.gff import bytes_gff, read_gff
from pykotor.resource.formats.ncs import compile_nss, bytes_ncs
from pykotor.common.misc import Game
from pykotor.resource.type import ResourceType as RT

from src.core.assets.resource_manager import ResourceManager, RES_TPC
from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive, imported_mesh_surface_role
from src.core.modules.authored_module_kmap_bridge import (
    authored_project_from_kmap_payload,
    authored_project_to_kmap_payload,
)
from src.core.modules.authored_module_objects import (
    AuthoredCreatureInstance,
    AuthoredDoorInstance,
    AuthoredGameplayPlacement,
    AuthoredPlaceableInstance,
    AuthoredStoreInstance,
    ModuleEntryPoint,
)
from src.core.modules.module_editor_controller import ModuleEditorController

K1_ROOT = Path(os.environ.get("GHOSTRIGGER_K1_ROOT", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"))
K2_ROOT = Path(os.environ.get("GHOSTRIGGER_K2_ROOT", r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"))
K2_MODULES = K2_ROOT / "Modules"
DEMO_PREFIXES = ("boxspin", "box", "geosphere", "scriptloop", "coneref")
OUT_DIR = ROOT / "artifacts" / "map_studio" / "k2_plcaa_test_map"

RESULTS: list[tuple[str, str, str]] = []
#: Bisection mode (--no-door / --no-store / --no-creatures / --no-placeables):
#: builds a reduced module for in-game crash isolation; strict content
#: assertions relax since counts intentionally differ.
VARIANT = any(arg.startswith("--no-") for arg in sys.argv)


def record(name, ok, detail=""):
    RESULTS.append((name, "PASS" if ok else "FAIL", str(detail)[:120]))
    print(f"{name:56} {'PASS' if ok else 'FAIL':6} {str(detail)[:120]}", flush=True)


def finish() -> int:
    fails = sum(1 for _n, s, _d in RESULTS if s == "FAIL")
    print()
    print(f"{'K2 PLCAA GAMEPLAY MILESTONE':56} {'RESULT':6} DETAIL")
    print("-" * 130)
    for name, status, detail in RESULTS:
        print(f"{name:56} {status:6} {detail}")
    print("-" * 130)
    print(f"{len(RESULTS) - fails}/{len(RESULTS)} PASS")
    return 1 if fails else 0


def capsule_resource(rim_path: Path, resref: str, restype) -> bytes:
    data = LazyCapsule(rim_path).resource(resref, restype)
    if not data:
        raise AssertionError(f"{resref}.{restype} not found in {rim_path.name}")
    return bytes(data)


def retag_template(data: bytes, *, tag: str, resref: str, extra_fields=None) -> bytes:
    gff = read_gff(data)
    gff.root.set_string("Tag", tag)
    gff.root.set_resref("TemplateResRef", resref)
    for setter, label, value in extra_fields or ():
        getattr(gff.root, setter)(label, value)
    return bytes_gff(gff)


def is_demo_surface(name: str) -> bool:
    clean = str(name or "").strip().lower()
    return any(clean.startswith(prefix) for prefix in DEMO_PREFIXES)


# ================= Stage 1: shell port =================
if not (K1_ROOT.exists() and K2_ROOT.exists()):
    record("S01 both game installs found", False, f"K1={K1_ROOT.exists()} K2={K2_ROOT.exists()}")
    sys.exit(finish())
record("S01 both game installs found", True, "")

rm = ResourceManager()
rm.set_k1_dir(str(K1_ROOT))
rm.set_k2_dir(str(K2_ROOT))

c = ModuleEditorController()
c.new_project(name="plcaa", game="K1")
ok, message = c.import_stock_module_from_rim(
    module_resref="plcaa", modules_dir=str(K1_ROOT / "modules"), game="K1", resource_manager=rm
)
record("S02 import K1 plcaa", ok, message[:100])
ok, message = c.convert_all_stock_rooms_to_imported_mesh(resource_manager=rm)
record("S03 convert to editable mesh", ok, message[:100])
ok, message = c.prepare_imported_room_for_static_runtime_rebuild(
    room_resref="plcaa",
    reason=(
        "Golden K2 plcaa gameplay fixture intentionally strips the K1 demo runtime graph "
        "and rebuilds the edited shell as a new static room."
    ),
)
record("S03b acknowledge static runtime rebuild", ok, message[:100])
if not ok:
    sys.exit(finish())


def authored_of(c):
    return authored_project_from_kmap_payload(
        c.project.extra_sections["authored_module"], fallback_name="plcaa", fallback_game="K2"
    )


def store_authored(c, authored):
    c.project.extra_sections["authored_module"] = authored_project_to_kmap_payload(authored)
    c.project.dirty = True


# Strip demo objects: only floor/ceiling/walls remain.
deleted = 0
while True:
    prim = authored_of(c).rooms[0].primitive
    target = next(((i, s) for i, s in enumerate(prim.surfaces) if is_demo_surface(s.name)), None)
    if target is None:
        break
    index, surface = target
    ok, message = c.delete_imported_mesh_room_faces(
        room_resref="plcaa", mesh_role=imported_mesh_surface_role(index), face_indices=list(range(len(surface.faces)))
    )
    if not ok:
        record("S04 strip demo objects", False, message)
        sys.exit(finish())
    deleted += len(surface.faces)
prim = authored_of(c).rooms[0].primitive
record("S04 strip demo objects (shell only)", deleted > 0 and len(prim.surfaces) == 3, f"{deleted} faces removed, {len(prim.surfaces)} shell surfaces")

# ================= Stage 2: cordon pillars via GModeler =================
ZONES = {
    "enemies": (15.0, 15.0),
    "merchant": (45.0, 15.0),
    "containers": (15.0, 45.0),
    "puzzle": (45.0, 45.0),
}


def floor_face_near(prim, x, y):
    """(surface_index, face_index) of the floor face nearest (x, y)."""

    best = None
    for surface_index, surface in enumerate(prim.surfaces):
        for face_index, face in enumerate(surface.faces):
            pts = [surface.vertices[v] for v in face]
            nz = 1.0
            ax, ay, az = pts[0]
            bx, by, bz = pts[1]
            cx, cy, cz = pts[2]
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nxv = (uy * vz) - (uz * vy)
            nyv = (uz * vx) - (ux * vz)
            nzv = (ux * vy) - (uy * vx)
            length = (nxv * nxv + nyv * nyv + nzv * nzv) ** 0.5 or 1.0
            if nzv / length < 0.9:  # floor faces point up
                continue
            czm = (az + bz + cz) / 3.0
            if czm > 1.0:  # ceiling
                continue
            cxm = (ax + bx + cx) / 3.0
            cym = (ay + by + cy) / 3.0
            d = (cxm - x) ** 2 + (cym - y) ** 2
            if best is None or d < best[0]:
                best = (d, surface_index, face_index)
    return (best[1], best[2]) if best else (-1, -1)


pillars = 0
for zone, (zx, zy) in ZONES.items():
    prim = authored_of(c).rooms[0].primitive
    surface_index, face_index = floor_face_near(prim, zx + 6.0, zy + 6.0)
    if face_index < 0:
        continue
    ok, message = c.extrude_imported_mesh_room_faces(
        room_resref="plcaa",
        mesh_role=imported_mesh_surface_role(surface_index),
        face_indices=[face_index],
        distance=1.5,
    )
    if ok:
        pillars += 1
record("S05 cordon pillars extruded (GModeler)", pillars == 4, f"{pillars}/4 zone markers raised")

# Optional bisect variant: strip lightmaps (tst_light, which loads fine in
# K2, is fullbright with tex_count=1; plcaa carries a second UV set).
if "--no-lightmaps" in sys.argv:
    authored = authored_of(c)
    room = authored.rooms[0]
    surfaces = tuple(
        dc_replace(s, lightmap="", uvs_lm=(), tex_count=1, texture_names=(s.texture,) if s.texture else ())
        for s in room.primitive.surfaces
    )
    room = dc_replace(room, primitive=dc_replace(room.primitive, surfaces=surfaces))
    authored = dc_replace(authored, rooms=(room,))
    store_authored(c, authored)
    record("S05a lightmaps stripped (bisect)", True, f"{len(surfaces)} surfaces fullbright")

# Optional bisect variant: K2 vanilla modules never name a room the same as
# the area/module ("101perz" in area "101per"); K1's plcaa does. Rename the
# room to test the K2 name-collision hypothesis.
ROOM_RESREF = "plcaa"
if "--rename-room" in sys.argv:
    ROOM_RESREF = "plcaa_r00"
    authored = authored_of(c)
    room = authored.rooms[0]
    prim = dc_replace(room.primitive, room_resref=ROOM_RESREF)
    room = dc_replace(room, room_resref=ROOM_RESREF, primitive=prim, visible_rooms=())
    authored = dc_replace(authored, rooms=(room,))
    store_authored(c, authored)
    record("S05b room renamed for K2 (bisect)", authored_of(c).rooms[0].room_resref == ROOM_RESREF, ROOM_RESREF)

# ================= Stage 3: templates, scripts, textures =================
PER = K2_MODULES / "101PER_s.rim"
TEL = K2_MODULES / "202TEL_s.rim"

extra: list[tuple[str, str, bytes]] = []

# Enemies: Peragus assassin droids (kept verbatim; GIT refers to them).
for resref in ("g_assassindrd002", "g_assassindrd003"):
    extra.append((resref, "utc", capsule_resource(PER, resref, RT.UTC)))
# Merchant NPC body + store, retagged for this map.
extra.append(("gr_merchant", "utc", retag_template(capsule_resource(PER, "n_commf001", RT.UTC), tag="gr_merchant", resref="gr_merchant")))
extra.append(("gr_store", "utm", retag_template(capsule_resource(TEL, "m_202_001", RT.UTM), tag="gr_store", resref="gr_store")))
# Containers.
for resref in ("cont_med012", "ebstrg001"):
    extra.append((resref, "utp", capsule_resource(PER, resref, RT.UTP)))

# Puzzle: three pedestals (computer panel base) + locked reward door.
panel_bytes = capsule_resource(PER, "comppnl001", RT.UTP)
for index in (1, 2, 3):
    extra.append(
        (
            f"gr_ped{index}",
            "utp",
            retag_template(
                panel_bytes,
                tag=f"gr_ped{index}",
                resref=f"gr_ped{index}",
                extra_fields=(
                    ("set_resref", "OnUsed", "gr_puzzle"),
                    ("set_uint8", "Useable", 1),
                    ("set_uint8", "Static", 0),
                    ("set_uint8", "Plot", 1),
                ),
            ),
        )
    )
extra.append(
    (
        "gr_pzdoor",
        "utd",
        retag_template(
            capsule_resource(PER, "sw_door_per001", RT.UTD),
            tag="gr_pzdoor",
            resref="gr_pzdoor",
            extra_fields=(
                ("set_uint8", "Locked", 1),
                ("set_uint8", "KeyRequired", 0),
                ("set_uint8", "Plot", 1),
                ("set_uint8", "Static", 0),
                ("set_resref", "OnUsed", ""),
            ),
        ),
    )
)
# Shop terminal: using it opens the merchant's store.
extra.append(
    (
        "gr_shopterm",
        "utp",
        retag_template(
            panel_bytes,
            tag="gr_shopterm",
            resref="gr_shopterm",
            extra_fields=(
                ("set_resref", "OnUsed", "gr_shop"),
                ("set_uint8", "Useable", 1),
                ("set_uint8", "Static", 0),
                ("set_uint8", "Plot", 1),
            ),
        ),
    )
)
# Dathomir Rancor boss (custom): bundle the pre-built UTC (appearance row
# 671 -> dat_rancor model, which loads from Override).  Built by
# scripts/build_dathomir_rancor.py; global assets (mdl/mdx/tga + appearance
# .2da) must be staged to the K2 Override folder separately.
# RANCOR_TEST_RESREF isolation knob (T2538 crash bisection):
#   dat_rancor01 (default) -> custom UTC bundled + custom Override assets
#   g_rancor01             -> stock BIF template + vanilla model (no bundle),
#                             to test whether a plain big rancor crashes plcaa.
RANCOR_RESREF = os.environ.get("RANCOR_TEST_RESREF", "dat_rancor01")
DAT_RANCOR_UTC = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\Dathomir\Characters\Rancor\MDL\dat_rancor01.utc"
)
_bundled_rancor = RANCOR_RESREF == "dat_rancor01" and DAT_RANCOR_UTC.is_file()
if _bundled_rancor:
    extra.append(("dat_rancor01", "utc", DAT_RANCOR_UTC.read_bytes()))

# 2 droids + merchant + store + 2 containers + 3 pedestals + door + shop
# terminal (+ custom Rancor boss UTC when bundled)
_expected_extra = 12 if _bundled_rancor else 11
record("S06 templates extracted + retagged", len(extra) == _expected_extra,
       f"{len(extra)} templates (rancor={RANCOR_RESREF})")

# Scripts: Naga Sadow-style ordered pedestal puzzle + shop opener.
PUZZLE_NSS = """
// gr_puzzle: use the three pedestals in order (1 -> 2 -> 3) to unlock the
// reward door; a wrong step resets progress (Naga Sadow tomb style).
void main() {
    object oSelf = OBJECT_SELF;
    string sTag = GetTag(oSelf);
    object oPed1 = GetObjectByTag("gr_ped1", 0);
    object oPed2 = GetObjectByTag("gr_ped2", 0);
    object oDoor = GetObjectByTag("gr_pzdoor", 0);
    if (sTag == "gr_ped1") {
        SetLocalBoolean(oPed1, 40, TRUE);
    } else if (sTag == "gr_ped2") {
        if (GetLocalBoolean(oPed1, 40) == TRUE) {
            SetLocalBoolean(oPed2, 40, TRUE);
        } else {
            SetLocalBoolean(oPed1, 40, FALSE);
            SetLocalBoolean(oPed2, 40, FALSE);
        }
    } else if (sTag == "gr_ped3") {
        if (GetLocalBoolean(oPed2, 40) == TRUE) {
            SetLocked(oDoor, FALSE);
            AssignCommand(oDoor, ActionOpenDoor(oDoor));
        } else {
            SetLocalBoolean(oPed1, 40, FALSE);
            SetLocalBoolean(oPed2, 40, FALSE);
        }
    }
}
"""
SHOP_NSS = """
// gr_shop: shop terminal opens the test merchant's store for the player.
void main() {
    object oStore = GetObjectByTag("gr_store", 0);
    if (GetIsObjectValid(oStore)) {
        OpenStore(oStore, GetFirstPC());
    }
}
"""
try:
    puzzle_ncs = bytes_ncs(compile_nss(PUZZLE_NSS, Game.K2))
    shop_ncs = bytes_ncs(compile_nss(SHOP_NSS, Game.K2))
    extra.append(("gr_puzzle", "ncs", puzzle_ncs))
    extra.append(("gr_shop", "ncs", shop_ncs))
    record("S07 puzzle + shop scripts compile (K2 NCS)", len(puzzle_ncs) > 32 and len(shop_ncs) > 16, f"{len(puzzle_ncs)}B / {len(shop_ncs)}B")
except Exception as exc:
    record("S07 puzzle + shop scripts compile (K2 NCS)", False, f"{type(exc).__name__}: {exc}")
    sys.exit(finish())

# Textures the shell references, ported from K1 for the Override folder.
prim = authored_of(c).rooms[0].primitive
texture_names = sorted(
    {
        str(t).strip().lower()
        for s in prim.surfaces
        for t in (s.texture, s.lightmap, *s.texture_names)
        if str(t).strip()
    }
)
override_dir = OUT_DIR / "install" / "Override"
shutil.rmtree(OUT_DIR, ignore_errors=True)
override_dir.mkdir(parents=True, exist_ok=True)
ported = 0
for name in texture_names:
    data = rm.get(name, RES_TPC, "K1")
    if data:
        (override_dir / f"{name}.tpc").write_bytes(bytes(data))
        # No vanilla/community precedent for TPCs inside .mod archives; the
        # Override copies are the real delivery. --no-tpc drops the bundled
        # copies to test whether they poison the module resource index.
        if "--no-tpc" not in sys.argv:
            extra.append((name, "tpc", bytes(data)))
        ported += 1
record("S08 K1 shell textures ported for Override", ported == len(texture_names), f"{ported}/{len(texture_names)}: {', '.join(texture_names)}")

# ================= Stage 4: placements =================
def z_at(x, y, prim):
    return 0.0  # plcaa floor is flat at z=0


prim = authored_of(c).rooms[0].primitive
placements = AuthoredGameplayPlacement(
    entry_point=ModuleEntryPoint(area_resref="plcaa", position=(30.0, 30.0, 0.0), facing=0.0),
    creatures=(
        AuthoredCreatureInstance(template_resref="g_assassindrd002", tag="gr_enemy1", position=(ZONES["enemies"][0], ZONES["enemies"][1], 0.0), bearing=0.0),
        AuthoredCreatureInstance(template_resref="g_assassindrd003", tag="gr_enemy2", position=(ZONES["enemies"][0] + 3.0, ZONES["enemies"][1], 0.0), bearing=0.0),
        AuthoredCreatureInstance(template_resref="gr_merchant", tag="gr_merchant", position=(ZONES["merchant"][0], ZONES["merchant"][1], 0.0), bearing=3.14),
        # Dathomir Rancor boss — walkmesh-validated (plcaa floor X -1..59,
        # Y -0.6..58.5); faces -Y back toward the (30,30) entry point.
        AuthoredCreatureInstance(template_resref=RANCOR_RESREF, tag="test_rancor", position=(30.0, 48.0, 0.0), bearing=3.14159),
    ),
    placeables=(
        AuthoredPlaceableInstance(template_resref="cont_med012", tag="gr_cont1", position=(ZONES["containers"][0], ZONES["containers"][1], 0.0)),
        AuthoredPlaceableInstance(template_resref="ebstrg001", tag="gr_cont2", position=(ZONES["containers"][0] + 2.0, ZONES["containers"][1], 0.0)),
        AuthoredPlaceableInstance(template_resref="gr_shopterm", tag="gr_shopterm", position=(ZONES["merchant"][0] + 2.0, ZONES["merchant"][1], 0.0)),
        AuthoredPlaceableInstance(template_resref="gr_ped1", tag="gr_ped1", position=(ZONES["puzzle"][0], ZONES["puzzle"][1], 0.0)),
        AuthoredPlaceableInstance(template_resref="gr_ped2", tag="gr_ped2", position=(ZONES["puzzle"][0] + 2.5, ZONES["puzzle"][1], 0.0)),
        AuthoredPlaceableInstance(template_resref="gr_ped3", tag="gr_ped3", position=(ZONES["puzzle"][0] + 5.0, ZONES["puzzle"][1], 0.0)),
    ),
    doors=()
    if "--no-door" in sys.argv
    else (
        AuthoredDoorInstance(template_resref="gr_pzdoor", tag="gr_pzdoor", position=(ZONES["puzzle"][0] + 2.5, ZONES["puzzle"][1] + 6.0, 0.0), bearing=0.0),
    ),
    stores=()
    if "--no-store" in sys.argv
    else (
        AuthoredStoreInstance(template_resref="gr_store", tag="gr_store", position=(ZONES["merchant"][0], ZONES["merchant"][1] + 1.0, 0.0)),
    ),
)
if "--no-creatures" in sys.argv:
    placements = dc_replace(placements, creatures=())
if "--no-placeables" in sys.argv:
    placements = dc_replace(placements, placeables=())
authored = authored_of(c)
authored = dc_replace(authored, placements=placements, metadata=dc_replace(authored.metadata, game="K2", module_root="plcaa"))
store_authored(c, authored)
record(
    "S09 fresh K2 placements staged (old scripts dropped)",
    VARIANT or (len(authored.placements.creatures) == 4 and len(authored.placements.placeables) == 6),
    f"{len(authored.placements.creatures)} creatures, {len(authored.placements.placeables)} placeables, "
    f"{len(authored.placements.doors)} door(s), {len(authored.placements.stores)} store(s)",
)

# ================= Stage 5: export as K2 module =================
from src.core.modules.authored_module_export import AuthoredModuleExportRequest, export_authored_module_project

authored = authored_of(c)
result = export_authored_module_project(
    AuthoredModuleExportRequest(
        project=authored,
        output_dir=str(OUT_DIR),
        game_root_dir=str(K2_ROOT),
        extra_resources=tuple(extra),
    )
)
kinds = {entry.restype for entry in result.resources}
required_kinds = {"mdl", "wok", "lyt", "are", "git", "ifo", "utc", "utp", "utm", "utd", "ncs"}
if "--no-tpc" not in sys.argv:
    required_kinds.add("tpc")
record(
    "S10 export K2 plcaa.mod",
    result.ok and not result.blocking_issues and required_kinds <= kinds,
    f"kinds={sorted(kinds)} blocking={result.blocking_issues[:1]}",
)
verification = result.package_verification
record("S11 package verification", verification is not None and verification.ok, getattr(verification, "message", "none")[:100])
engine_contract = dict(result.metadata.get("engine_contract", {}) or {})
record(
    "S11b vanilla-derived raw engine contract",
    bool(engine_contract.get("export_ready")),
    f"rooms={len(engine_contract.get('rooms', []) or [])} blocking={list(engine_contract.get('blocking_issues', []) or [])[:1]}",
)

# ================= Stage 6: read the .mod back and verify everything =================
mod_path = Path(str(result.module_path or ""))
if not mod_path.exists():
    record("S12 module readback", False, "no module written")
    sys.exit(finish())

cap = LazyCapsule(mod_path)
have = {(item.resref().lower(), item.restype().extension.lower()) for item in cap}
wanted = {
    ("g_assassindrd002", "utc"), ("g_assassindrd003", "utc"), ("gr_merchant", "utc"),
    ("gr_store", "utm"), ("cont_med012", "utp"), ("ebstrg001", "utp"),
    ("gr_ped1", "utp"), ("gr_ped2", "utp"), ("gr_ped3", "utp"), ("gr_shopterm", "utp"),
    ("gr_pzdoor", "utd"), ("gr_puzzle", "ncs"), ("gr_shop", "ncs"), ("ruler01", "tpc"),
}
if _bundled_rancor:
    wanted.add(("dat_rancor01", "utc"))
missing = wanted - have
record(
    "S12 all templates/scripts/textures in .mod",
    VARIANT or not missing,
    f"missing={sorted(missing)[:4]}" if missing else f"{len(wanted)} bundled resources present",
)

git = read_gff(cap.resource("plcaa", RT.GIT))
creatures = git.root.acquire("Creature List", [])
creature_count = len(creatures)
creature_refs = {str(c.acquire("TemplateResRef", "")).lower() for c in creatures}
placeable_count = len(git.root.acquire("Placeable List", []))
door_count = len(git.root.acquire("Door List", []))
stores = git.root.acquire("StoreList", [])
store_ok = False
if len(stores) == 1:
    entry = stores[0]
    resref = str(entry.acquire("ResRef", ""))
    x = float(entry.acquire("XPosition", 0.0))
    store_ok = resref == "gr_store" and abs(x - ZONES["merchant"][0]) < 0.01
record(
    "S13 GIT round-trip (engine field contract)",
    VARIANT or (creature_count == 4 and RANCOR_RESREF.lower() in creature_refs
                and placeable_count == 6 and door_count == 1 and store_ok),
    f"{creature_count} creatures ({'rancor OK' if RANCOR_RESREF.lower() in creature_refs else 'RANCOR MISSING'}), "
    f"{placeable_count} placeables, {door_count} door, store ResRef+pos ok={store_ok}",
)

pedestal = read_gff(cap.resource("gr_ped1", RT.UTP))
door = read_gff(cap.resource("gr_pzdoor", RT.UTD))
record(
    "S14 puzzle wiring in templates",
    str(pedestal.root.acquire("OnUsed", "")) == "gr_puzzle"
    and int(pedestal.root.acquire("Useable", 0)) == 1
    and int(door.root.acquire("Locked", 0)) == 1,
    f"ped OnUsed={pedestal.root.acquire('OnUsed', '')} useable={pedestal.root.acquire('Useable', 0)} door locked={door.root.acquire('Locked', 0)}",
)

ncs_bytes = bytes(cap.resource("gr_puzzle", RT.NCS))
record("S15 compiled puzzle NCS bundled byte-exact", ncs_bytes == puzzle_ncs, f"{len(ncs_bytes)} bytes")

import struct

mdl = bytes(cap.resource(ROOM_RESREF, RT.MDL))
fp1 = struct.unpack_from("<I", mdl, 12)[0]
record("S16 room MDL uses K2 function pointers", fp1 == 4285200, f"fp1={fp1}")

record("S17 module + Override staged", mod_path.exists() and any(override_dir.glob("*.tpc")), str(mod_path))

sys.exit(finish())
