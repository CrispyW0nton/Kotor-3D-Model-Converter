"""Scan all base-game KOTOR 1/2 modules and distill a 'polished module' contract.

For every module RIM pair in both games: parse ARE/GIT/IFO/PTH from the RIMs,
resolve the area's LYT/VIS from chitin, then resolve each LYT room's WOK.
Aggregates walkmesh surface usage, VIS symmetry, room/LYT/VIS consistency,
lighting fields, and gameplay-resource counts into a JSON report.

Run with: py -3.14 scripts/scan_base_game_modules.py
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from collections import Counter
from pathlib import Path

logging.disable(logging.CRITICAL)

from pykotor.extract.capsule import LazyCapsule
from pykotor.extract.installation import Installation, SearchLocation
from pykotor.resource.formats.gff import read_gff
from pykotor.resource.formats.lyt import read_lyt
from pykotor.resource.formats.vis import read_vis
from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.type import ResourceType

GAMES = {
    "K1": Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
    "K2": Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"),
}
OUT = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Kotor-3D-Model-Converter-qt\Saved\Codex\base_module_scan.json")
SEARCH = [SearchLocation.CHITIN, SearchLocation.OVERRIDE]


def scan_module(game: str, inst: Installation, base: Path, stem: str) -> dict:
    row: dict = {"game": game, "module": stem}
    main = base / f"{stem}.rim"
    srim = base / f"{stem}_s.rim"
    caps = [LazyCapsule(main)]
    if srim.exists():
        caps.append(LazyCapsule(srim))

    are = git = ifo = pth = None
    resource_counts: Counter = Counter()
    for cap in caps:
        for res in cap:
            rt = res.restype()
            resource_counts[rt.extension] += 1
            try:
                if rt == ResourceType.ARE and are is None:
                    are = read_gff(cap.resource(res.resname(), rt)).root
                elif rt == ResourceType.GIT and git is None:
                    git = read_gff(cap.resource(res.resname(), rt)).root
                elif rt == ResourceType.IFO and ifo is None:
                    ifo = read_gff(cap.resource(res.resname(), rt)).root
                elif rt == ResourceType.PTH and pth is None:
                    pth = read_gff(cap.resource(res.resname(), rt)).root
            except Exception:
                row.setdefault("parse_errors", []).append(f"{res.resname()}.{rt.extension}")
    row["resources"] = dict(resource_counts)

    area_name = ""
    if ifo is not None:
        area_name = str(ifo.acquire("Mod_Entry_Area", ""))
        row["ifo"] = {
            "entry_area": area_name,
            "entry_xyz": [
                round(float(ifo.acquire("Mod_Entry_X", 0.0)), 3),
                round(float(ifo.acquire("Mod_Entry_Y", 0.0)), 3),
                round(float(ifo.acquire("Mod_Entry_Z", 0.0)), 3),
            ],
            "area_count": len(ifo.acquire("Mod_Area_list", None) or []),
        }
    row["has"] = {"are": are is not None, "git": git is not None,
                  "ifo": ifo is not None, "pth": pth is not None}

    if are is not None:
        rooms_list = are.acquire("Rooms", None)
        row["are"] = {
            "rooms_listed": len(rooms_list) if rooms_list is not None else 0,
            "sun_ambient": are.acquire("SunAmbientColor", None),
            "sun_diffuse": are.acquire("SunDiffuseColor", None),
            "dynamic_ambient": are.acquire("DynAmbientColor", None),
            "fog_on": are.acquire("SunFogOn", None),
            "shadows": are.acquire("SunShadows", None),
        }
    if git is not None:
        git_counts = {}
        for label, key in (
            ("creatures", "Creature List"), ("placeables", "Placeable List"),
            ("doors", "Door List"), ("triggers", "TriggerList"),
            ("waypoints", "WaypointList"), ("sounds", "SoundList"),
            ("encounters", "Encounter List"), ("cameras", "CameraList"),
            ("stores", "StoreList"),
        ):
            lst = git.acquire(key, None)
            git_counts[label] = len(lst) if lst is not None else 0
        row["git"] = git_counts
    if pth is not None:
        points = pth.acquire("Path_Points", None)
        conns = pth.acquire("Path_Conections", None)
        row["pth"] = {
            "points": len(points) if points is not None else 0,
            "connections": len(conns) if conns is not None else 0,
        }

    if not area_name:
        return row

    lyt = vis = None
    try:
        r = inst.resource(area_name, ResourceType.LYT, SEARCH)
        if r:
            lyt = read_lyt(r.data)
    except Exception:
        row.setdefault("parse_errors", []).append(f"{area_name}.lyt")
    try:
        r = inst.resource(area_name, ResourceType.VIS, SEARCH)
        if r:
            vis = read_vis(r.data)
    except Exception:
        row.setdefault("parse_errors", []).append(f"{area_name}.vis")
    row["has"]["lyt"] = lyt is not None
    row["has"]["vis"] = vis is not None

    room_models: list[str] = []
    if lyt is not None:
        room_models = [str(r.model).strip().lower() for r in lyt.rooms]
        row["lyt"] = {"rooms": len(room_models), "doorhooks": len(lyt.doorhooks),
                      "tracks": len(lyt.tracks), "obstacles": len(lyt.obstacles)}
        if are is not None:
            are_rooms = set()
            rooms_list = are.acquire("Rooms", None)
            if rooms_list is not None:
                for s in rooms_list:
                    are_rooms.add(str(s.acquire("RoomName", "")).strip().lower())
            row["are_rooms_match_lyt"] = are_rooms == set(room_models)
            row["are_rooms_missing_from_lyt"] = sorted(are_rooms - set(room_models))[:5]
            row["lyt_rooms_missing_from_are"] = sorted(set(room_models) - are_rooms)[:5]
    if vis is not None:
        vis_rooms = {str(r).strip().lower() for r in vis.all_rooms()}
        row["vis"] = {"rooms": len(vis_rooms)}
        if room_models:
            row["vis_rooms_not_in_lyt"] = sorted(vis_rooms - set(room_models))[:5]
            row["lyt_rooms_not_in_vis"] = sorted(set(room_models) - vis_rooms)[:5]
        asym = 0
        pairs = 0
        for a in vis_rooms:
            try:
                for b in vis.get_visible(a):
                    pairs += 1
                    bl = str(b).strip().lower()
                    try:
                        if not vis.get_visibility(bl, a):
                            asym += 1
                    except Exception:
                        asym += 1
            except Exception:
                pass
        row["vis_pairs"] = pairs
        row["vis_asymmetric"] = asym

    walkable = nonwalk = trans_edges = wok_found = 0
    surface_ids: Counter = Counter()
    per_room_missing_wok: list[str] = []
    for model in room_models:
        try:
            r = inst.resource(model, ResourceType.WOK, SEARCH)
        except Exception:
            r = None
        if not r:
            per_room_missing_wok.append(model)
            continue
        wok_found += 1
        try:
            bwm = read_bwm(r.data)
            for face in bwm.faces:
                mat = int(getattr(face.material, "value", face.material))
                surface_ids[mat] += 1
                is_walk = face.material.walkable() if hasattr(face.material, "walkable") else False
                if is_walk:
                    walkable += 1
                else:
                    nonwalk += 1
                for t in (face.trans1, face.trans2, face.trans3):
                    if t is not None and int(t) >= 0:
                        trans_edges += 1
        except Exception:
            row.setdefault("wok_errors", []).append(model)
    row["wok"] = {
        "rooms_with_wok": wok_found,
        "rooms_missing_wok": per_room_missing_wok[:8],
        "walkable_faces": walkable,
        "nonwalk_faces": nonwalk,
        "transition_edge_refs": trans_edges,
        "surface_ids": {str(k): v for k, v in sorted(surface_ids.items())},
    }
    return row


def main() -> None:
    rows = []
    errors = []
    for game, root in GAMES.items():
        base = root / "Modules"
        if not base.exists():
            errors.append(f"{game}: missing {base}")
            continue
        inst = Installation(root)
        stems = sorted({p.name[:-4] for p in base.glob("*.rim") if not p.name.endswith("_s.rim")})
        print(f"{game}: {len(stems)} modules", flush=True)
        for i, stem in enumerate(stems):
            try:
                rows.append(scan_module(game, inst, base, stem))
            except Exception as exc:
                errors.append(f"{game}/{stem}: {exc}")
                traceback.print_exc()
            if (i + 1) % 20 == 0:
                print(f"  {game} {i+1}/{len(stems)}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"modules": rows, "errors": errors}, indent=1), encoding="utf-8")
    print(f"WROTE {OUT} modules={len(rows)} errors={len(errors)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
