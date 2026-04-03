"""JRL (journal) generic: GFF-based quest and save-game journal data."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, read_gff, write_gff
from pykotor.resource.formats.gff.gff_auto import bytes_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class JRL:
    """Stores journal (quest) data.

    JRL files are GFF-based. Module JRL uses Categories/EntryList (quest/entry definitions).
    Save-game journal uses JNL_SortOrder and JNL_Entries (JNL_PlotID, JNL_State, JNL_Date, JNL_Time).

    References (REVA):
    ------------------
        LoadJournal (save format) @ (K1: 0x004f17d0, TSL: 0x006fd830). K1: CSWSCreature::LoadJournal;
        reads JNL_Entries, JNL_SortOrder (INT), JNL_PlotID (""), JNL_State/JNL_Date/JNL_Time (0).
        Caller: K1 LoadCharacterFromIFO @ 0x00561e30; TSL caller FUN_00701d10 @ 0x00701d10.
        Module format (Categories/EntryList) is toolset-defined; same defaults in both games.
    """

    BINARY_TYPE = ResourceType.JRL

    def __init__(self):
        self.quests: list[JRLQuest] = []


class JRLQuest:
    """Stores data of an individual quest.

    Attributes:
    ----------
        name: "Name" field.
        planet_id: "PlanetID" field.
        plot_index: "PlotIndex" field.
        priority: "Priority" field.
        tag: "Tag" field.

        comment: "Comment" field. Used in toolset only.
    """

    def __init__(
        self,
        name: LocalizedString | None = None,
        planet_id: int | None = None,
        plot_index: int | None = None,
        priority: JRLQuestPriority | None = None,
        tag: str | None = None,
        entries: list[JRLEntry] | None = None,
        comment: str | None = None,
    ):
        self.comment: str = "" if comment is None else comment
        self.name: LocalizedString = LocalizedString.from_invalid() if name is None else name
        self.planet_id: int = 0 if planet_id is None else planet_id
        self.plot_index: int = 0  # plot.2da
        self.priority: JRLQuestPriority = JRLQuestPriority.LOWEST if priority is None else priority
        self.tag: str = "" if tag is None else tag
        self.entries: list[JRLEntry] = [] if entries is None else entries


class JRLEntry:
    """Stores the data for an entry in a quest.

    Attributes:
    ----------
        end: "End" field.
        entry_id: "ID" field.
        text: "Text" field.
        xp_percentage: "XP_Percentage" field.
    """

    def __init__(
        self,
        end: bool | None = None,
        entry_id: int | None = None,
        text: LocalizedString | None = None,
        xp_percentage: float | None = None,
    ):
        self.end: bool = False if end is None else end
        self.entry_id: int = 0 if entry_id is None else entry_id
        self.text: LocalizedString = LocalizedString.from_invalid() if text is None else text
        self.xp_percentage: float = 0.0 if xp_percentage is None else xp_percentage


class JRLQuestPriority(IntEnum):
    HIGHEST = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    LOWEST = 4


def construct_jrl(gff: GFF) -> JRL:
    """Construct JRL from GFF (module format: Categories/EntryList).

    Defaults when field missing: Categories optional (empty list); per-category Comment "",
    Name empty, PlanetID/PlotIndex/Priority 0, Tag ""; per-entry End 0, ID 0, Text empty,
    XP_Percentage 0.0. Omit OK. Save format JNL_* (LoadJournal): JNL_PlotID "", JNL_State/JNL_Date/JNL_Time 0.

    Reference functions (5 K1, 5 TSL):
    K1: (1) CSWSCreature::LoadJournal @ 0x004f17d0 (JNL_Entries, JNL_SortOrder, JNL_PlotID/State/Date/Time),
    (2) LoadCharacterFromIFO @ 0x00561e30 (caller), (3) CResGFF::GetList JNL_Entries,
    (4) ReadFieldINT JNL_SortOrder, (5) ReadFieldCExoString JNL_PlotID default "".
    TSL: (1) FUN_006fd830 @ 0x006fd830 (same JNL_* read), (2) FUN_00701d10 @ 0x00701d10 (caller),
    (3)-(5) same semantics. Module Categories/EntryList not parsed by engine; defaults from toolset.
    """
    jrl = JRL()

    # Categories list (module format). Empty if missing. K1 LoadJournal @ 0x004f17d0, TSL @ 0x006fd830 read JNL_* (save); Categories toolset-defined. Omit OK.
    # Comment "", Name empty, PlanetID/PlotIndex 0, Priority 0 (HIGHEST in enum), Tag "". K1/TSL convention. Omit OK.
    for category_struct in gff.root.acquire("Categories", GFFList()):
        quest = JRLQuest()
        jrl.quests.append(quest)
        quest.comment = category_struct.acquire("Comment", "")
        quest.name = category_struct.acquire("Name", LocalizedString.from_invalid())
        quest.planet_id = category_struct.acquire("PlanetID", 0)
        quest.plot_index = category_struct.acquire("PlotIndex", 0)
        quest.priority = JRLQuestPriority(category_struct.acquire("Priority", 0))
        quest.tag = category_struct.acquire("Tag", "")

        # EntryList: End BYTE 0, ID 0, Text empty, XP_Percentage 0.0. K1 LoadJournal @ 0x004f17d0, TSL @ 0x006fd830 JNL_State/JNL_Date/JNL_Time default 0. Omit OK.
        for entry_struct in category_struct.acquire("EntryList", GFFList()):
            entry = JRLEntry()
            quest.entries.append(entry)
            entry.end = bool(entry_struct.acquire("End", 0))
            entry.entry_id = entry_struct.acquire("ID", 0)
            entry.text = entry_struct.acquire("Text", LocalizedString.from_invalid())
            entry.xp_percentage = entry_struct.acquire("XP_Percentage", 0.0)

    return jrl


def dismantle_jrl(  # TODO: store original list indices and sort.
    jrl: JRL,
    game: Game = Game.K2,
    *,
    use_deprecated: bool = True,
) -> GFF:
    gff = GFF(GFFContent.JRL)

    # Write same defaults as construct_jrl. Categories/EntryList; Comment "", PlanetID/PlotIndex/Priority 0, End/ID 0, XP_Percentage 0.0. K1 LoadJournal @ 0x004f17d0 (JNL_* save); TSL: same journal path. Omit OK.
    category_list: GFFList = gff.root.set_list("Categories", GFFList())
    for i, quest in enumerate(jrl.quests):
        category_struct = category_list.add(i)
        category_struct.set_string("Comment", quest.comment)
        category_struct.set_locstring("Name", quest.name)
        category_struct.set_int32("PlanetID", quest.planet_id)
        category_struct.set_int32("PlotIndex", quest.plot_index)
        category_struct.set_uint32("Priority", quest.priority.value)
        category_struct.set_string("Tag", quest.tag)

        entry_list: GFFList = category_struct.set_list("EntryList", GFFList())
        for j, entry in enumerate(quest.entries):
            entry_struct = entry_list.add(j)
            entry_struct.set_uint16("End", entry.end)
            entry_struct.set_uint32("ID", entry.entry_id)
            entry_struct.set_locstring("Text", entry.text)
            entry_struct.set_single("XP_Percentage", entry.xp_percentage)

    return gff


def read_jrl(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> JRL:
    gff: GFF = read_gff(source, offset, size)
    return construct_jrl(gff)


def write_jrl(
    jrl: JRL,
    target: TARGET_TYPES,
    file_format: ResourceType = ResourceType.GFF,
    game: Game = Game.K2,
):
    gff: GFF = dismantle_jrl(jrl, game)
    write_gff(gff, target, file_format)


def bytes_jrl(
    jrl: JRL,
    file_format: ResourceType = ResourceType.GFF,
) -> bytes:
    gff: GFF = dismantle_jrl(jrl)
    return bytes_gff(gff, file_format)
