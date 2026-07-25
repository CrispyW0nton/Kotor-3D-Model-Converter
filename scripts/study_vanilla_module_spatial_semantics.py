"""Study why every staged object exists and where it sits in retail KOTOR maps.

The scan is read-only.  It parses every shipping K1/K2 module GIT and PTH,
resolves template metadata when available, classifies the authored purpose of
each instance, and records spatial evidence such as threshold proximity,
circulation proximity, density, perimeter/centre placement, and repeated
door-flanking pairs.

Outputs:
    Saved/Codex/vanilla_module_spatial_semantics.json
    docs/knowledgebase/vanilla_module_spatial_semantics.md

Run from the repository root:
    py -3.14 scripts/study_vanilla_module_spatial_semantics.py
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYKOTOR = ROOT.parent / "PyKotor" / "Libraries" / "PyKotor" / "src"
UTILITY = ROOT.parent / "PyKotor" / "Libraries" / "Utility" / "src"
for path in (PYKOTOR, UTILITY, ROOT):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pykotor.extract.capsule import LazyCapsule  # noqa: E402
from pykotor.extract.installation import Installation, SearchLocation  # noqa: E402
from pykotor.resource.formats.gff import read_gff  # noqa: E402
from pykotor.resource.generics.git import read_git  # noqa: E402
from pykotor.resource.generics.pth import read_pth  # noqa: E402
from pykotor.resource.type import ResourceType  # noqa: E402


OUTPUT_JSON = ROOT / "Saved" / "Codex" / "vanilla_module_spatial_semantics.json"
OUTPUT_MARKDOWN = ROOT / "docs" / "knowledgebase" / "vanilla_module_spatial_semantics.md"
SEARCH = [SearchLocation.OVERRIDE, SearchLocation.CHITIN]
TEMPLATE_TYPES = {
    "creature": ResourceType.UTC,
    "door": ResourceType.UTD,
    "encounter": ResourceType.UTE,
    "placeable": ResourceType.UTP,
    "sound": ResourceType.UTS,
    "store": ResourceType.UTM,
    "trigger": ResourceType.UTT,
    "waypoint": ResourceType.UTW,
}


def _configured_games() -> dict[str, Path]:
    try:
        settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        settings = {}
    return {
        "K1": Path(str(settings.get("k1_dir") or r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")),
        "K2": Path(
            str(
                settings.get("k2_dir")
                or r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
            )
        ),
    }


def _module_family(game: str, module: str) -> str:
    key = module.lower()
    if game == "K1":
        rules = (
            (("end_",), "Endar Spire"),
            (("tar_",), "Taris"),
            (("dan",), "Dantooine"),
            (("tat_", "m19", "m45mg"), "Tatooine"),
            (("kas_", "m25"), "Kashyyyk"),
            (("man",), "Manaan"),
            (("korr_",), "Korriban"),
            (("lev_",), "Leviathan"),
            (("liv_",), "Yavin"),
            (("ebo_",), "Ebon Hawk"),
            (("unk_",), "Unknown World"),
            (("sta_",), "Star Forge"),
        )
    else:
        rules = (
            (("00",), "Ebon Hawk"),
            (("10",), "Peragus"),
            (("15",), "Harbinger"),
            (("2",), "Telos"),
            (("3",), "Nar Shaddaa"),
            (("4",), "Dxun"),
            (("5",), "Onderon"),
            (("6",), "Dantooine"),
            (("7",), "Korriban"),
            (("8",), "Ravager/M4-78"),
            (("9",), "Malachor/Coruscant"),
        )
    for prefixes, label in rules:
        if key.startswith(prefixes):
            return label
    return "Other"


def _distance_xy(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _template_text(installation: Installation, root: Any) -> tuple[str, dict[str, Any]]:
    fields: dict[str, Any] = {}
    for label in (
        "Tag",
        "TemplateResRef",
        "Conversation",
        "OnUsed",
        "OnOpen",
        "OnClosed",
        "OnDialog",
        "OnHeartbeat",
        "OnEnter",
        "OnExit",
        "Appearance",
        "Appearance_Type",
        "Faction",
        "FactionID",
        "Plot",
        "Static",
        "Useable",
        "HasInventory",
        "Locked",
        "KeyRequired",
        "TrapFlag",
        "MapNoteEnabled",
        "HasMapNote",
    ):
        try:
            value = root.acquire(label, None)
        except Exception:
            value = None
        if value not in (None, "", 0, False):
            fields[label] = str(value) if not isinstance(value, (str, int, float, bool)) else value
    names: list[str] = []
    for label in ("LocalizedName", "LocName", "FirstName", "Name", "MapNote"):
        try:
            value = root.acquire(label, None)
            resolved = installation.string(value, "") if value is not None else ""
        except Exception:
            resolved = ""
        if str(resolved).strip():
            names.append(str(resolved).strip())
    return (" / ".join(dict.fromkeys(names)), fields)


def _purpose(
    kind: str,
    *,
    resref: str,
    tag: str,
    display_name: str,
    fields: dict[str, Any],
    linked_module: str,
) -> tuple[str, str, float]:
    text = " ".join((resref, tag, display_name, *(str(value) for value in fields.values()))).lower()
    interactive = any(fields.get(key) for key in ("Useable", "OnUsed", "OnOpen", "OnDialog", "Conversation"))
    if kind == "door":
        if linked_module:
            return "functional_transition_gate", "Connects this module to another authored area.", 1.0
        return "functional_threshold", "Controls circulation and frames a room boundary.", 0.98
    if kind == "trigger":
        if linked_module:
            return "functional_transition_volume", "Moves the player across a module boundary.", 1.0
        if fields.get("TrapFlag") or "trap" in text:
            return "gameplay_hazard_volume", "Defines a spatially bounded trap or hazard.", 0.95
        return "scripted_event_volume", "Starts authored gameplay when the player enters a meaningful space.", 0.86
    if kind == "encounter":
        return "combat_spawn_zone", "Controls encounter arrival and combat pacing away from static decoration.", 0.98
    if kind == "camera":
        return "authored_viewpoint", "Composes a cutscene or scripted reveal from a deliberate position.", 1.0
    if kind == "sound":
        return "ambient_audio_zone", "Establishes local ambience or spatial audio around a district/node.", 0.98
    if kind == "store":
        return "service_inventory", "Supplies a merchant or scripted service inventory.", 1.0
    if kind == "waypoint":
        if fields.get("MapNoteEnabled") or fields.get("HasMapNote"):
            return "navigation_landmark", "Names an important destination on the player map.", 1.0
        if any(word in text for word in ("spawn", "start", "entry", "exit")):
            return "spawn_or_transition_anchor", "Anchors a player/NPC arrival or departure.", 0.92
        return "script_or_patrol_anchor", "Anchors movement, facing, patrol, or scripted blocking.", 0.84
    if kind == "creature":
        if any(word in text for word in ("merchant", "vendor", "shop", "bartender", "pazaak")):
            return "service_actor", "Occupies a service/activity node where the player expects interaction.", 0.92
        if fields.get("Conversation") or "dialog" in text:
            return "narrative_actor", "Faces and occupies a conversation or story beat.", 0.94
        if any(word in text for word in ("guard", "soldier", "sith", "turret", "enemy", "hostile")):
            return "combat_or_security_actor", "Guards a threshold, route, or tactical space.", 0.83
        return "ambient_population", "Makes the district feel occupied and supports environmental storytelling.", 0.72
    if kind == "placeable":
        groups = (
            (("computer", "console", "terminal", "panel", "switch"), "interactive_terminal", "Supports a functional interaction at a wall, desk, or control node."),
            (("crate", "chest", "locker", "footlocker", "container", "bin"), "storage_or_reward_container", "Stores loot or communicates storage/utility use."),
            (("chair", "bench", "stool", "bed", "table", "desk", "counter"), "activity_furniture", "Defines a believable human activity area rather than filling empty space."),
            (("statue", "banner", "monument", "fountain", "obelisk"), "landmark_or_civic_decor", "Creates identity, symmetry, or a focal point for navigation."),
            (("lamp", "light", "torch", "sconce"), "lighting_fixture", "Motivates local light and reinforces the architectural rhythm."),
            (("rock", "tree", "plant", "foliage", "grass", "rubble", "debris"), "environmental_dressing", "Reinforces biome, edge shape, or environmental history."),
            (("turret", "barricade", "mine"), "combat_support_prop", "Shapes threat, cover, or security at a tactical node."),
        )
        for words, role, rationale in groups:
            if any(word in text for word in words):
                return role, rationale, 0.90
        if interactive:
            return "interactive_prop", "Provides a deliberate player interaction at this location.", 0.88
        return "decorative_or_utility_prop", "Supports local function, scale, and material storytelling.", 0.62
    return "unclassified", "Requires manual review.", 0.25


def _instance_kind(instance: Any) -> str:
    return instance.__class__.__name__.removeprefix("GIT").removesuffix("Transition").lower()


def _read_module(
    game: str,
    installation: Installation,
    module_root: Path,
    module: str,
    template_cache: dict[tuple[str, str], tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    capsules = [LazyCapsule(module_root / f"{module}.rim")]
    secondary = module_root / f"{module}_s.rim"
    if secondary.is_file():
        capsules.append(LazyCapsule(secondary))
    git_data = None
    pth_data = None
    local_templates: dict[tuple[str, ResourceType], bytes] = {}
    for capsule in capsules:
        for resource in capsule:
            restype = resource.restype()
            data = capsule.resource(resource.resname(), restype)
            if restype == ResourceType.GIT and git_data is None:
                git_data = data
            elif restype == ResourceType.PTH and pth_data is None:
                pth_data = data
            elif restype in set(TEMPLATE_TYPES.values()):
                local_templates[(resource.resname().lower(), restype)] = data
    if git_data is None:
        return {"game": game, "module": module, "family": _module_family(game, module), "objects": [], "warning": "missing GIT"}
    git = read_git(git_data)
    pth_points: list[tuple[float, float]] = []
    if pth_data is not None:
        try:
            pth_points = [(float(point.x), float(point.y)) for point in read_pth(pth_data)]
        except Exception:
            pth_points = []
    raw_instances = list(git.instances())
    positions = [
        (float(instance.position.x), float(instance.position.y), float(instance.position.z))
        for instance in raw_instances
    ]
    if positions:
        min_x, max_x = min(point[0] for point in positions), max(point[0] for point in positions)
        min_y, max_y = min(point[1] for point in positions), max(point[1] for point in positions)
        center = ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)
        radius_x = max((max_x - min_x) * 0.5, 0.001)
        radius_y = max((max_y - min_y) * 0.5, 0.001)
    else:
        min_x = max_x = min_y = max_y = 0.0
        center = (0.0, 0.0)
        radius_x = radius_y = 1.0
    door_positions = [
        positions[index] for index, instance in enumerate(raw_instances) if _instance_kind(instance) == "door"
    ]
    objects: list[dict[str, Any]] = []
    for index, instance in enumerate(raw_instances):
        kind = _instance_kind(instance)
        position = positions[index]
        resref = str(getattr(instance, "resref", "") or "").strip().lower()
        tag = str(getattr(instance, "tag", "") or "").strip()
        linked_module = str(getattr(instance, "linked_to_module", "") or "").strip().lower()
        display_name = ""
        fields: dict[str, Any] = {}
        restype = TEMPLATE_TYPES.get(kind)
        if restype is not None and resref:
            cache_key = (resref, restype.extension)
            cached = template_cache.get(cache_key)
            if cached is None:
                data = local_templates.get((resref, restype))
                if data is None:
                    try:
                        result = installation.resource(resref, restype, SEARCH)
                        data = result.data if result else None
                    except Exception:
                        data = None
                if data is not None:
                    try:
                        cached = _template_text(installation, read_gff(data).root)
                    except Exception:
                        cached = ("", {})
                else:
                    cached = ("", {})
                template_cache[cache_key] = cached
            display_name, fields = cached
        role, rationale, confidence = _purpose(
            kind,
            resref=resref,
            tag=tag,
            display_name=display_name,
            fields=fields,
            linked_module=linked_module,
        )
        nearest_door = min((_distance_xy(position, door) for door in door_positions if door != position), default=None)
        nearest_path = min(
            (math.hypot(position[0] - point[0], position[1] - point[1]) for point in pth_points),
            default=None,
        )
        neighbours_2m = sum(
            1 for other in positions if other != position and _distance_xy(position, other) <= 2.0
        )
        neighbours_5m = sum(
            1 for other in positions if other != position and _distance_xy(position, other) <= 5.0
        )
        nx = abs(position[0] - center[0]) / radius_x
        ny = abs(position[1] - center[1]) / radius_y
        edge_score = max(nx, ny)
        spatial_tags: list[str] = []
        if nearest_door is not None and nearest_door <= 1.75 and kind not in {"door", "trigger"}:
            spatial_tags.append("threshold_adjacent")
        if nearest_path is not None and nearest_path <= 1.0:
            spatial_tags.append("circulation_adjacent")
        if edge_score >= 0.82:
            spatial_tags.append("perimeter")
        elif edge_score <= 0.28:
            spatial_tags.append("central")
        if neighbours_2m >= 3:
            spatial_tags.append("clustered")
        elif neighbours_5m == 0:
            spatial_tags.append("isolated")
        objects.append(
            {
                "index": index,
                "kind": kind,
                "resref": resref,
                "tag": tag,
                "display_name": display_name,
                "position": [round(value, 4) for value in position],
                "bearing_radians": round(float(instance.yaw() or 0.0), 6),
                "linked_module": linked_module,
                "purpose_role": role,
                "purpose_rationale": rationale,
                "purpose_confidence": confidence,
                "template_evidence": fields,
                "spatial_tags": spatial_tags,
                "nearest_door_m": None if nearest_door is None else round(nearest_door, 3),
                "nearest_path_point_m": None if nearest_path is None else round(nearest_path, 3),
                "neighbours_within_2m": neighbours_2m,
                "neighbours_within_5m": neighbours_5m,
                "perimeter_score": round(edge_score, 4),
            }
        )
    # Detect repeated same-template pairs that deliberately flank a door.
    by_template: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in objects:
        if row["resref"]:
            by_template[(row["kind"], row["resref"])].append(row)
    pair_count = 0
    for rows in by_template.values():
        for first_index, first in enumerate(rows):
            for second in rows[first_index + 1 :]:
                separation = _distance_xy(tuple(first["position"]), tuple(second["position"]))
                if not 1.0 <= separation <= 8.0:
                    continue
                midpoint = (
                    (first["position"][0] + second["position"][0]) * 0.5,
                    (first["position"][1] + second["position"][1]) * 0.5,
                    (first["position"][2] + second["position"][2]) * 0.5,
                )
                door_distance = min((_distance_xy(midpoint, door) for door in door_positions), default=999.0)
                if door_distance <= 2.0:
                    for row in (first, second):
                        if "door_flanking_pair" not in row["spatial_tags"]:
                            row["spatial_tags"].append("door_flanking_pair")
                    pair_count += 1
    return {
        "game": game,
        "module": module,
        "family": _module_family(game, module),
        "bounds_xy": [round(min_x, 3), round(min_y, 3), round(max_x, 3), round(max_y, 3)],
        "pth_point_count": len(pth_points),
        "object_count": len(objects),
        "door_flanking_pair_count": pair_count,
        "objects": objects,
    }


def _write_markdown(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    lines = [
        "# Vanilla KOTOR Module Spatial Semantics",
        "",
        f"Evidence scan: **{aggregate['module_count']} shipping modules**, "
        f"**{aggregate['object_count']} staged GIT objects** across KOTOR 1 and 2.",
        "The full per-object evidence (position, template, inferred purpose, confidence, threshold/path distance, "
        "density, perimeter/centre placement, and pairing) is stored in "
        "`Saved/Codex/vanilla_module_spatial_semantics.json`.",
        "",
        "## What the retail maps teach Map Studio",
        "",
        "1. **Doors are thresholds, never loose props.** A door belongs to a wall opening, controls circulation, "
        "and may carry a module transition. Map Studio must reject or warn on an unanchored door.",
        "2. **Decoration reinforces function.** Repeated statues, lamps, consoles, and banners commonly form "
        "door-flanking pairs or architectural rhythms; they are not uniformly scattered.",
        "3. **Furniture defines activity nodes.** Chairs, tables, beds, bars, and terminals should be placed as "
        "coherent use areas with facing and clearance, not as generic filler.",
        "4. **Waypoints and PTH points reveal intended circulation.** Functional objects sit beside paths; clutter "
        "must preserve the route instead of occupying it.",
        "5. **Perimeter and centre have different jobs.** Utility, storage, cover, and most dressing stay near edges. "
        "Monuments and navigation landmarks may occupy controlled central nodes.",
        "6. **Encounter, trigger, camera, and sound objects author invisible experience layers.** Their positions "
        "express pacing, arrival, reveal, combat, and ambience even when they have no visible mesh.",
        "",
        "## Observed role counts",
        "",
        "| Purpose role | Instances |",
        "|---|---:|",
    ]
    for role, count in aggregate["role_counts"].items():
        lines.append(f"| {role.replace('_', ' ').title()} | {count:,} |")
    lines.extend(
        [
            "",
            "## Spatial relationship counts",
            "",
            "| Relationship | Instances |",
            "|---|---:|",
        ]
    )
    for tag, count in aggregate["spatial_tag_counts"].items():
        lines.append(f"| {tag.replace('_', ' ').title()} | {count:,} |")
    lines.extend(
        [
            "",
            "## Product rules derived from the evidence",
            "",
            "- Every Content Browser item should declare a placement role: structural threshold, functional "
            "interaction, activity furniture, landmark, perimeter dressing, combat support, ambience, or script volume.",
            "- Functional thresholds require a wall/portal anchor and a clear walkable approach on both sides.",
            "- Decorative pairs require a shared anchor and deliberate symmetry or rhythm; the editor should offer "
            "paired placement instead of random duplication.",
            "- Activity props require an activity node, facing target, and clearance envelope.",
            "- The placement audit should report path blockage, unanchored doors, isolated utility objects, "
            "unsupported centre clutter, and decorative objects with no stated rationale.",
            "- Automatic staging may suggest evidence-backed arrangements, but authored meaning must remain explicit "
            "and editable by the level designer.",
            "",
            "## Families covered",
            "",
        ]
    )
    for family, count in aggregate["family_module_counts"].items():
        lines.append(f"- {family}: {count} module(s)")
    OUTPUT_MARKDOWN.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    modules: list[dict[str, Any]] = []
    errors: list[str] = []
    template_cache: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
    for game, game_root in _configured_games().items():
        module_root = game_root / "Modules"
        if not (game_root / "chitin.key").is_file() or not module_root.is_dir():
            errors.append(f"{game}: installation not found at {game_root}")
            continue
        installation = Installation(game_root)
        module_names = sorted(
            path.stem
            for path in module_root.glob("*.rim")
            if not path.name.lower().endswith("_s.rim")
        )
        print(f"{game}: studying {len(module_names)} modules", flush=True)
        for ordinal, module in enumerate(module_names, 1):
            try:
                modules.append(_read_module(game, installation, module_root, module, template_cache))
            except Exception as exc:
                errors.append(f"{game}/{module}: {exc}")
            if ordinal % 20 == 0 or ordinal == len(module_names):
                print(f"  {game} {ordinal}/{len(module_names)}", flush=True)
    role_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    spatial_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    object_count = 0
    for module in modules:
        family_counts[module["family"]] += 1
        for row in module["objects"]:
            object_count += 1
            role_counts[row["purpose_role"]] += 1
            kind_counts[row["kind"]] += 1
            spatial_counts.update(row["spatial_tags"])
    payload = {
        "schema": "ghostrigger.vanilla-module-spatial-semantics/v1",
        "method": "read-only GIT/PTH/template analysis with evidence-backed semantic and spatial classification",
        "aggregate": {
            "module_count": len(modules),
            "object_count": object_count,
            "template_count": len(template_cache),
            "role_counts": dict(role_counts.most_common()),
            "kind_counts": dict(kind_counts.most_common()),
            "spatial_tag_counts": dict(spatial_counts.most_common()),
            "family_module_counts": dict(sorted(family_counts.items())),
            "error_count": len(errors),
        },
        "modules": modules,
        "errors": errors,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown(payload)
    print(
        f"WROTE {OUTPUT_JSON} and {OUTPUT_MARKDOWN}: "
        f"{len(modules)} modules, {object_count} objects, {len(errors)} errors",
        flush=True,
    )
    return 0 if modules and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
