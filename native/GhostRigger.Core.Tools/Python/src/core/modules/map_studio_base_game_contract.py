"""Base-game module contract gates for Map Studio export validation.

Encodes the invariants observed across all 199 shipping KOTOR 1/2 modules
(evidence: Saved/Codex/base_module_scan.json, 2026-07-04 scan; distilled in
docs/knowledgebase/basegamemodulecontract.md) plus the WOK serialization
contract confirmed from the Kotor.NET reverse study.

Headless and read-only: callers hand in a lightweight description of the
export candidate and receive gate results.  Owning layer: Core validation.
Severity levels:
- "blocker": violated by zero base-game modules; export should stop.
- "warning": rare-but-legal in the base games; surface loudly, allow override.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: WOK surface ids observed walkable in every base-game module.
BASE_GAME_WALKABLE_SURFACES: frozenset[int] = frozenset(
    {1, 3, 4, 5, 6, 9, 10, 11, 13, 14, 16, 17, 18, 19}
)
#: WOK surface ids observed non-walkable in every base-game module.
BASE_GAME_NONWALKABLE_SURFACES: frozenset[int] = frozenset({0, 2, 7, 8, 15})
#: Every surface id that appears anywhere in shipping K1/K2 walkmeshes.
BASE_GAME_OBSERVED_SURFACES: frozenset[int] = frozenset(
    {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 16, 17, 19}
)
#: The universal blocker surface used for ~half of all base-game WOK faces.
SURFACE_NONWALK = 7
#: Door-threshold surface; correlates with transition edges in base modules.
SURFACE_DOOR = 19

# ── surfacemat.2da bit-field structure (RE from Odyssey engine) ─────────
# Source: KotorModdingKnowledgeBase/docs/engine/walkmesh-system.md
# The engine caches walk_check_material_mask from surfacemat.2da and uses
# bitwise AND for per-face filtering — no 2DA lookup at runtime.
SURFMAT_BIT_LINE_OF_SIGHT = 1  # bit 0: ray can pass for LOS checks
SURFMAT_BIT_WALK = 2           # bit 1: character can walk on this surface
SURFMAT_BIT_WALK_CHECK = 4     # bit 2: checked during walkmesh ray queries
#: Surface 7 (NonWalk) has ONLY the WalkCheck bit in some game versions,
#: meaning the engine never tests it — it is invisible to pathfinding.
#: Source: CSWCollisionMesh::NoNonWalkPolys material filter logic.

#: surfacemat.2da bit-field for the 15 observed base-game surface ids.
#: Derived from the RE analysis + base-game scan cross-reference.
#: {(surface_id, bitfield_flags)} — flags use the SURFMAT_BIT_* constants.
SURFACE_BITFIELDS: dict[int, int] = {
    0: 0,                       # Undefined — no flags
    1: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK | SURFMAT_BIT_LINE_OF_SIGHT,  # Dirt
    2: 0,                       # Obscuring — blocks LOS, not walkable
    3: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK | SURFMAT_BIT_LINE_OF_SIGHT,  # Grass
    4: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK | SURFMAT_BIT_LINE_OF_SIGHT,  # Stone
    5: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                              # Wood
    6: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                              # Water (walkable)
    7: 0,                       # NonWalk — engine never tests this surface
    8: 0,                       # Transparent — not walkable, not LOS-tested
    9: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                              # Carpet
    10: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK | SURFMAT_BIT_LINE_OF_SIGHT, # Metal
    11: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                             # Puddles
    13: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                             # Swamp
    14: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                             # Door transition
    16: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                             # Mud
    17: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK,                             # Leaves
    19: SURFMAT_BIT_WALK | SURFMAT_BIT_WALK_CHECK | SURFMAT_BIT_LINE_OF_SIGHT, # Door threshold
}


def is_walkable_surface(surface_id: int) -> bool:
    """Return True if the surface has the Walk bit set in surfacemat.2da."""

    return bool(SURFACE_BITFIELDS.get(int(surface_id), 0) & SURFMAT_BIT_WALK)


def is_los_blocking_surface(surface_id: int) -> bool:
    """Return True if the surface blocks line-of-sight (no LOS bit)."""

    return not bool(SURFACE_BITFIELDS.get(int(surface_id), 0) & SURFMAT_BIT_LINE_OF_SIGHT)


def is_walkcheck_surface(surface_id: int) -> bool:
    """Return True if the engine tests this surface during walkmesh ray queries."""

    return bool(SURFACE_BITFIELDS.get(int(surface_id), 0) & SURFMAT_BIT_WALK_CHECK)

#: Resref length limit enforced by the engine (confirmed in Kotor.NET ResRef).
MAX_RESREF_LENGTH = 16


@dataclass(frozen=True)
class ModuleContractIssue:
    """One gate result from the base-game contract check."""

    gate: str
    severity: str  # "blocker" | "warning"
    message: str


@dataclass(frozen=True)
class ModuleContractReport:
    """Aggregated gate results for one export candidate."""

    issues: tuple[ModuleContractIssue, ...] = field(default_factory=tuple)

    @property
    def blockers(self) -> tuple[ModuleContractIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "blocker")

    @property
    def warnings(self) -> tuple[ModuleContractIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def export_ready(self) -> bool:
        return not self.blockers


def _norm_names(values) -> set[str]:
    return {str(v or "").strip().lower() for v in tuple(values or ()) if str(v or "").strip()}


def check_module_against_base_game_contract(
    *,
    module_resref: str = "",
    are_room_names=(),
    lyt_room_names=(),
    vis_pairs=(),
    rooms_with_wok=(),
    ifo_area_names=(),
    entry_area: str = "",
    has_pth: bool = False,
    pth_point_count: int = 0,
    surface_id_histogram=None,
    sun_shadows: bool | None = None,
    creature_count: int | None = None,
    waypoint_count: int | None = None,
    room_positions=None,
) -> ModuleContractReport:
    """Run the base-game invariants against an export candidate description.

    ``vis_pairs`` is an iterable of (room_a, room_b) visibility edges.
    ``surface_id_histogram`` maps surface id -> face count for the module's
    combined walkmeshes.  All name comparisons are case-insensitive.
    """

    issues: list[ModuleContractIssue] = []

    resref = str(module_resref or "").strip()
    if resref and len(resref) > MAX_RESREF_LENGTH:
        issues.append(ModuleContractIssue(
            "resref_length", "blocker",
            f"Module resref '{resref}' exceeds {MAX_RESREF_LENGTH} chars; the engine truncates or rejects it.",
        ))

    are_rooms = _norm_names(are_room_names)
    lyt_rooms = _norm_names(lyt_room_names)
    if "****" in lyt_rooms:
        issues.append(ModuleContractIssue(
            "lyt_placeholder_room", "blocker",
            "LYT contains '****' placeholder rooms; only K1 stunt cutscene modules ship those.",
        ))
        lyt_rooms.discard("****")
    only_in_are = sorted(are_rooms - lyt_rooms)
    only_in_lyt = sorted(lyt_rooms - are_rooms)
    if only_in_are:
        issues.append(ModuleContractIssue(
            "are_rooms_match_lyt", "blocker",
            f"ARE Rooms not present in LYT: {only_in_are[:6]}. All 199 base modules match exactly.",
        ))
    if only_in_lyt:
        issues.append(ModuleContractIssue(
            "are_rooms_match_lyt", "blocker",
            f"LYT rooms missing from ARE Rooms list: {only_in_lyt[:6]}. All 199 base modules match exactly.",
        ))

    pairs = {(str(a or "").strip().lower(), str(b or "").strip().lower()) for a, b in tuple(vis_pairs or ())}
    asymmetric = sorted({(a, b) for (a, b) in pairs if (b, a) not in pairs})
    if asymmetric:
        issues.append(ModuleContractIssue(
            "vis_symmetry", "blocker",
            f"VIS asymmetric pairs (A sees B without B seeing A): {asymmetric[:6]}. Base-game VIS is always symmetric.",
        ))
    if lyt_rooms and not pairs and len(lyt_rooms) > 1:
        issues.append(ModuleContractIssue(
            "vis_present", "warning",
            "Multi-room module without VIS visibility pairs; base games ship VIS in 196/199 modules.",
        ))
    vis_rooms = {name for pair in pairs for name in pair}
    unknown_vis_rooms = sorted(vis_rooms - lyt_rooms) if lyt_rooms else []
    if unknown_vis_rooms:
        issues.append(ModuleContractIssue(
            "vis_rooms_in_lyt", "blocker",
            f"VIS references rooms not in LYT: {unknown_vis_rooms[:6]}.",
        ))

    wok_rooms = _norm_names(rooms_with_wok)
    rooms_without_wok = sorted(lyt_rooms - wok_rooms) if lyt_rooms else []
    if rooms_without_wok:
        issues.append(ModuleContractIssue(
            "room_wok_coverage", "blocker",
            f"LYT rooms without a WOK: {rooms_without_wok[:6]}. Every real base-game room ships one.",
        ))

    areas = [str(a or "").strip() for a in tuple(ifo_area_names or ()) if str(a or "").strip()]
    if len(areas) != 1:
        issues.append(ModuleContractIssue(
            "ifo_single_area", "blocker",
            f"IFO Mod_Area_list has {len(areas)} entries; every base module has exactly 1.",
        ))
    entry = str(entry_area or "").strip().lower()
    if areas and entry and entry not in {a.lower() for a in areas}:
        issues.append(ModuleContractIssue(
            "ifo_entry_area", "blocker",
            f"Mod_Entry_Area '{entry_area}' is not in Mod_Area_list.",
        ))

    if not has_pth:
        issues.append(ModuleContractIssue(
            "pth_present", "blocker",
            "Module has no PTH resource; all 199 base modules include one (even when empty).",
        ))
    elif int(pth_point_count or 0) == 0 and (creature_count or 0) > 0:
        issues.append(ModuleContractIssue(
            "pth_points_for_creatures", "warning",
            "PTH has zero points but GIT places creatures; NPC movement will be degraded.",
        ))

    histogram = {int(k): int(v) for k, v in dict(surface_id_histogram or {}).items()}
    if histogram:
        exotic = sorted(set(histogram) - BASE_GAME_OBSERVED_SURFACES)
        if exotic:
            issues.append(ModuleContractIssue(
                "wok_surface_vocabulary", "warning",
                f"WOK uses surface ids never seen in base games: {exotic[:8]}.",
            ))
        walkable_faces = sum(v for k, v in histogram.items() if k in BASE_GAME_WALKABLE_SURFACES)
        if walkable_faces == 0:
            issues.append(ModuleContractIssue(
                "wok_walkable_faces", "blocker",
                "Module walkmeshes contain zero walkable faces; the player cannot stand anywhere.",
            ))

    if sun_shadows:
        issues.append(ModuleContractIssue(
            "are_sun_shadows", "warning",
            "ARE SunShadows enabled; 198/199 base modules ship with shadows off.",
        ))
    if creature_count == 0 and waypoint_count == 0 and (creature_count is not None or waypoint_count is not None):
        issues.append(ModuleContractIssue(
            "git_population", "warning",
            "GIT has no creatures and no waypoints; legal but unusual for a playable area.",
        ))

    # Multi-level walkmesh overlap check.
    # RE finding: engine GetRoom() uses ±1000-unit vertical scan returning
    # the FIRST room in array order, not the nearest Z.  Two rooms with
    # overlapping XY AABBs at different Z heights will cause the engine to
    # always navigate on the first room's walkmesh, ignoring upper floors.
    # Source: KotorModdingKnowledgeBase/docs/engine/walkmesh-system.md
    room_pos_list = tuple(room_positions or ())
    if len(room_pos_list) >= 2:
        overlaps = _detect_multi_level_overlaps(room_pos_list)
        if overlaps:
            pairs_text = ", ".join(f"{a}/{b}" for a, b in overlaps[:4])
            issues.append(ModuleContractIssue(
                "multi_level_walkmesh", "warning",
                f"Rooms with overlapping XY footprints at different Z heights: {pairs_text}. "
                "Engine GetRoom() returns the first room in array order, not nearest Z — "
                "upper-floor navigation will be unreliable.",
            ))

    return ModuleContractReport(issues=tuple(issues))


def _detect_multi_level_overlaps(
    room_positions,
    *,
    overlap_threshold: float = 1.0,
    z_separation_threshold: float = 1.5,
) -> list[tuple[str, str]]:
    """Detect room pairs with overlapping XY AABBs at different Z levels.

    ``room_positions`` is an iterable of ``(room_name, (min_x, min_y, min_z),
    (max_x, max_y, max_z))`` tuples.  Returns a list of ``(room_a, room_b)``
    pairs that have meaningful XY overlap and Z separation exceeding the
    threshold, indicating a multi-level walkmesh situation the engine
    handles incorrectly.
    """

    rooms: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = []
    for entry in room_positions:
        try:
            name = str(entry[0] or "")
            bmin = tuple(float(v) for v in entry[1][:3])
            bmax = tuple(float(v) for v in entry[2][:3])
            if len(bmin) == 3 and len(bmax) == 3:
                rooms.append((name, bmin, bmax))
        except Exception:
            continue

    overlaps: list[tuple[str, str]] = []
    for i, (name_a, amin, amax) in enumerate(rooms):
        for j in range(i + 1, len(rooms)):
            name_b, bmin, bmax = rooms[j]
            # XY AABB intersection test
            overlap_x = max(0.0, min(amax[0], bmax[0]) - max(amin[0], bmin[0]))
            overlap_y = max(0.0, min(amax[1], bmax[1]) - max(amin[1], bmin[1]))
            if overlap_x < overlap_threshold or overlap_y < overlap_threshold:
                continue
            # Z separation test — rooms must be at clearly different heights
            z_center_a = (amin[2] + amax[2]) / 2.0
            z_center_b = (bmin[2] + bmax[2]) / 2.0
            if abs(z_center_a - z_center_b) < z_separation_threshold:
                continue
            overlaps.append((name_a, name_b))
    return overlaps
