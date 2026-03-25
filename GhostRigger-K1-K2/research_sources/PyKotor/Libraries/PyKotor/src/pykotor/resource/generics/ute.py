"""UTE (encounter) generic: GFF-based encounter definitions and spawn lists."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, read_gff, write_gff
from pykotor.resource.formats.gff.gff_auto import bytes_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class UTE:
    """Stores encounter data.

    UTE files are GFF-based format files that store encounter definitions including
    creature spawn lists, difficulty, respawn settings, and script hooks.

    References:
    ----------
        KotOR I (swkotor.exe):
            - 0x00593830 - CSWSEncounter::LoadEncounter (593 bytes, 102 lines)
                - Main UTE GFF parser entry point
                - Loads encounter from GFF structure
                - Function signature: LoadEncounter(CSWSEncounter* this, CResGFF* param_1, CResStruct* param_2)
                - Called from LoadEncounters (0x00505060)
            - 0x00505060 - CSWSArea::LoadEncounters
                - Loads encounters from area GIT file
            - 0x00590820 - CSWSEncounter::ReadEncounterScriptsFromGff
                - Reads encounter scripts from GFF
            - 0x00590410 - CSWSEncounter::LoadEncounterSpawnPoints
                - Loads encounter spawn point geometry
            - 0x00590580 - CSWSEncounter::LoadEncounterGeometry
                - Loads encounter geometry data

        KotOR II / TSL (swkotor2.exe):
            - ReadEncounterFromGff equivalent: FUN_007eb810 (CreatureList: ResRef, CR, SingleSpawn, GuaranteedCount)
            - SaveEncounter equivalent: FUN_007ed770

        GFF Field Structure (from LoadEncounter analysis):
            - Root struct fields:
                - "CreatureList" (GFFList) - List of creature spawn entries
                - Script fields (from ReadEncounterScriptsFromGff):
                    - "OnEntered" (CResRef) - Script executed when encounter is entered
                    - "OnExhausted" (CResRef) - Script executed when encounter is exhausted
                    - "OnExit" (CResRef) - Script executed when encounter is exited
                    - "OnHeartbeat" (CResRef) - Script executed on heartbeat
                    - "OnSpawn" (CResRef) - Script executed when creatures spawn
                    - "OnUserDefined" (CResRef) - User defined script
            - CreatureList element struct fields:
                - "ResRef" (CResRef) - Creature template ResRef
                - "CR" (FLOAT) - Challenge rating
                - "SingleSpawn" (BYTE) - Whether creature spawns only once
                - Additional spawn-related fields

        Note: UTE files are GFF format files with specific structure definitions (GFFContent.UTE)

    Attributes:
    ----------
        resref: "TemplateResRef" field. The resource reference for this encounter template.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:15 (TemplateResRef property)

        tag: "Tag" field. Tag identifier for this encounter.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:13 (Tag property)

        comment: "Comment" field. Developer comment.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:33 (Comment property)

        active: "Active" field. Whether encounter is active.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:16 (Active property)

        difficulty_id: "DifficultyIndex" field. Difficulty index identifier.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:18 (DifficultyIndex property)

        faction_id: "Faction" field. Faction identifier.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:19 (Faction property)

        max_creatures: "MaxCreatures" field. Maximum number of creatures to spawn.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:20 (MaxCreatures property)

        player_only: "PlayerOnly" field. Whether encounter only triggers for player.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:21 (PlayerOnly property)

        rec_creatures: "RecCreatures" field. Recommended number of creatures.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:22 (RecCreatures property)

        reset: "Reset" field. Whether encounter resets after completion.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:23 (Reset property)

        reset_time: "ResetTime" field. Time in seconds before reset.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:24 (ResetTime property)

        respawns: "Respawns" field. Number of times encounter can respawn.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:25 (Respawns property)

        single_shot: "SpawnOption" field. Whether encounter spawns only once.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:26 (SpawnOption property)

        on_entered: "OnEntered" field. Script to run when encounter area is entered.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:27 (OnEntered property)

        on_exit: "OnExit" field. Script to run when leaving encounter area.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:28 (OnExit property)

        on_exhausted: "OnExhausted" field. Script to run when encounter is exhausted.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:29 (OnExhausted property)

        on_heartbeat: "OnHeartbeat" field. Script to run on heartbeat.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:30 (OnHeartbeat property)

        on_user_defined: "OnUserDefined" field. Script to run on user-defined event.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:31 (OnUserDefined property)

        creatures: List of UTECreature objects representing spawnable creatures.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:34 (Creatures property)

        palette_id: "PaletteID" field. Palette identifier. Used in toolset only.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:32 (PaletteID property)

        name: "LocalizedName" field. Localized name. Not used by the game engine.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:14 (LocalizedName property)

        unused_difficulty: "Difficulty" field. Difficulty value. Not used by the game engine.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:17 (Difficulty property)
    """

    BINARY_TYPE = ResourceType.UTE

    def __init__(self):
        self.resref: ResRef = ResRef.from_blank()
        self.tag: str = ""
        self.comment: str = ""

        self.active: bool = False
        self.player_only: bool = False
        self.reset: bool = False
        self.single_shot: bool = False

        self.difficulty_id: int = 0
        self.faction_id: int = 0

        self.max_creatures: int = 0
        self.rec_creatures: int = 0
        self.reset_time: int = 0
        self.respawns: int = 0

        self.on_exit: ResRef = ResRef.from_blank()
        self.on_exhausted: ResRef = ResRef.from_blank()
        self.on_heartbeat: ResRef = ResRef.from_blank()
        self.on_entered: ResRef = ResRef.from_blank()
        self.on_user_defined: ResRef = ResRef.from_blank()

        self.creatures: list[UTECreature] = []

        # Deprecated:
        self.name: LocalizedString = LocalizedString.from_invalid()
        self.palette_id: int = 0
        self.unused_difficulty: int = 0


class UTECreature:
    """Stores data for a creature that can be spawned by an encounter.

    References:
    ----------
        KotOR I (swkotor.exe):
            - 0x00592430 - CSWSEncounter::ReadEncounterFromGff (3445 bytes, 434 lines)
                - Loads CreatureList from UTE GFF structure
                - Function signature: ReadEncounterFromGff(CSWSEncounter* this, CResGFF* param_2, CResStruct* param_3, int param_4, Vector* param_5)
                - Called from LoadEncounter (0x00593830) and LoadFromTemplate (0x00593ba5)
            - Reads CreatureList (GFFList) at line 189:
                - ResRef (CResRef) - creature template resource reference
                - CR (FLOAT) - challenge rating
                - SingleSpawn (BYTE) - single spawn flag
        KotOR II / TSL (swkotor2.exe):
            - Functionally identical to K1 implementation
            - Same GFF structure and parsing logic


    Attributes:
    ----------
        appearance_id: "Appearance" field. Appearance type identifier for this creature.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:39 (Appearance property)

        challenge_rating: "CR" field. Challenge rating value.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:40 (CR property)

        resref: "ResRef" field. Resource reference to creature template (UTC file).
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:41 (ResRef property)

        single_spawn: "SingleSpawn" field. Whether this creature spawns only once.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:42 (SingleSpawn property)

        guaranteed_count: "GuaranteedCount" field. Guaranteed spawn count. KotOR 2 only.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTE.cs:43 (GuaranteedCount property)
    """

    def __init__(self):
        self.appearance_id: int = 0
        self.challenge_rating: float = 0.0
        self.resref: ResRef = ResRef.from_blank()
        self.single_spawn: bool = False
        self.guaranteed_count: int = 0


def utd_version(gff: GFF) -> Game:
    """Infer game version from UTE GFF. GuaranteedCount is TSL-only (K2)."""
    creature_list = gff.root.acquire("CreatureList", GFFList())
    for creature_struct in creature_list:
        if creature_struct.exists("GuaranteedCount"):
            return Game.K2
    return Game.K1


def construct_ute(gff: GFF) -> UTE:
    """Constructs a UTE object from a GFF structure.

    Defaults when field missing (REVA): K1 CSWSEncounter::LoadEncounter @ 0x00593830,
    ReadEncounterFromGff @ 0x00592430; TSL ReadEncounterFromGff @ 0x007eb810. Tag/TemplateResRef "";
    Active/PlayerOnly/Reset/SpawnOption 0; DifficultyIndex/Faction/MaxCreatures/RecCreatures/ResetTime/Respawns 0;
    scripts ResRef "". Optional when missing.

    Ten reference functions (5 K1, 5 TSL): K1 (1) LoadEncounter @ 0x00593830 (root UTE parser),
    (2) LoadEncounters @ 0x00505060 (area encounters), (3) ReadEncounterFromGff @ 0x00592430 (CreatureList),
    (4) ReadEncounterScriptsFromGff @ 0x00590820, (5) LoadEncounterSpawnPoints @ 0x00590410 / LoadEncounterGeometry @ 0x00590580.
    TSL (1) ReadEncounterFromGff @ 0x007eb810, (2) SaveEncounter @ 0x007ed770, (3)-(5) same semantics.
    """
    ute = UTE()

    root = gff.root
    # Identity: Tag "", TemplateResRef "". K1 LoadEncounter 0x00593830, TSL 0x007eb810. Optional.
    ute.tag = root.acquire("Tag", "")
    ute.resref = root.acquire("TemplateResRef", ResRef.from_blank())
    # Spawn/reset: Active, DifficultyIndex, Faction, MaxCreatures, RecCreatures, Reset, ResetTime, Respawns, SpawnOption. Default 0. K1/TSL LoadEncounter. Optional.
    ute.active = bool(root.acquire("Active", 0))
    ute.difficulty_id = root.acquire("DifficultyIndex", 0)
    ute.unused_difficulty = root.acquire("Difficulty", 0)
    ute.faction_id = root.acquire("Faction", 0)
    ute.max_creatures = root.acquire("MaxCreatures", 0)
    ute.player_only = bool(root.acquire("PlayerOnly", 0))
    ute.rec_creatures = root.acquire("RecCreatures", 0)
    ute.reset = bool(root.acquire("Reset", 0))
    ute.reset_time = root.acquire("ResetTime", 0)
    ute.respawns = root.acquire("Respawns", 0)
    ute.single_shot = bool(root.acquire("SpawnOption", 0))
    # Scripts: OnEntered/OnExit/OnExhausted/OnHeartbeat/OnUserDefined. ResRef "". K1 ReadEncounterScriptsFromGff 0x00590820; TSL same. Optional.
    ute.on_entered = root.acquire("OnEntered", ResRef.from_blank())
    ute.on_exit = root.acquire("OnExit", ResRef.from_blank())
    ute.on_exhausted = root.acquire("OnExhausted", ResRef.from_blank())
    ute.on_heartbeat = root.acquire("OnHeartbeat", ResRef.from_blank())
    ute.on_user_defined = root.acquire("OnUserDefined", ResRef.from_blank())
    ute.comment = root.acquire("Comment", "")
    ute.name = root.acquire("LocalizedName", LocalizedString.from_invalid())
    ute.palette_id = root.acquire("PaletteID", 0)

    # CreatureList: ResRef "", CR 0.0, SingleSpawn 0; TSL GuaranteedCount 0. K1 ReadEncounterFromGff 0x00592430, TSL 0x007eb810. Optional.
    creature_list = root.get_list("CreatureList")
    if creature_list is not None:
        for creature_struct in creature_list:
            creature = UTECreature()
            ute.creatures.append(creature)
            # K1 ReadEncounterFromGff @ 0x00592430: ResRef (CResRef ""), CR (FLOAT 0.0), SingleSpawn (BYTE 0).
            #   K1 does NOT read Appearance or GuaranteedCount; field3_0x18 hardcoded 0.
            # TSL FUN_007eb810 (ReadEncounterFromGff): same + GuaranteedCount (ReadFieldINT default 0).
            # Appearance is toolset-only; engine does not read it.
            creature.appearance_id = creature_struct.acquire("Appearance", 0)
            creature.challenge_rating = creature_struct.acquire("CR", 0.0)
            creature.single_spawn = bool(creature_struct.acquire("SingleSpawn", 0))
            creature.resref = creature_struct.acquire("ResRef", ResRef.from_blank())
            creature.guaranteed_count = creature_struct.acquire("GuaranteedCount", 0)

    return ute


def dismantle_ute(
    ute: UTE,
    game: Game = Game.K2,
    *,
    use_deprecated: bool = True,
) -> GFF:
    gff = GFF(GFFContent.UTE)

    root = gff.root
    # Write same defaults as engine read. K1 LoadEncounter 0x00593830, SaveEncounter 0x00591350; TSL 0x007eb810, 0x007ed770. Tag "", ResRef "", INT32/BYTE 0.
    root.set_string("Tag", ute.tag)
    root.set_resref("TemplateResRef", ute.resref)
    root.set_uint8("Active", ute.active)
    root.set_int32("DifficultyIndex", ute.difficulty_id)
    root.set_uint32("Faction", ute.faction_id)
    root.set_int32("MaxCreatures", ute.max_creatures)
    root.set_uint8("PlayerOnly", ute.player_only)
    root.set_int32("RecCreatures", ute.rec_creatures)
    root.set_uint8("Reset", ute.reset)
    root.set_int32("ResetTime", ute.reset_time)
    root.set_int32("Respawns", ute.respawns)
    root.set_int32("SpawnOption", ute.single_shot)
    root.set_resref("OnEntered", ute.on_entered)
    root.set_resref("OnExit", ute.on_exit)
    root.set_resref("OnExhausted", ute.on_exhausted)
    root.set_resref("OnHeartbeat", ute.on_heartbeat)
    root.set_resref("OnUserDefined", ute.on_user_defined)
    root.set_string("Comment", ute.comment)

    root.set_uint8("PaletteID", ute.palette_id)

    # K1 SaveEncounter @ 0x00591350: CreatureList writes ResRef, CR, SingleSpawn only.
    # TSL FUN_007ed770: CreatureList writes ResRef, CR, SingleSpawn, GuaranteedCount.
    creature_list = root.set_list("CreatureList", GFFList())
    for creature in ute.creatures:
        creature_struct = creature_list.add(0)
        creature_struct.set_int32("Appearance", creature.appearance_id)
        creature_struct.set_single("CR", creature.challenge_rating)
        creature_struct.set_uint8("SingleSpawn", creature.single_spawn)
        creature_struct.set_resref("ResRef", creature.resref)
        if game.is_k2():
            creature_struct.set_int32("GuaranteedCount", creature.guaranteed_count)

    if use_deprecated:
        root.set_locstring("LocalizedName", ute.name)
        root.set_int32("Difficulty", ute.unused_difficulty)

    return gff


def read_ute(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> UTE:
    gff = read_gff(source, offset, size)
    return construct_ute(gff)


def write_ute(
    ute: UTE,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff = dismantle_ute(ute, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_ute(
    ute: UTE,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff = dismantle_ute(ute, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
