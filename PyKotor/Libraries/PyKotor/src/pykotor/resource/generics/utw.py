"""UTW (waypoint) generic: GFF-based waypoint definitions and map notes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff, read_gff, write_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.formats.gff import GFFStruct
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class UTW:
    """Stores waypoint data.

    UTW files are GFF-based format files that store waypoint definitions including
    map notes, appearance, and location data.

    References:
    ----------
        Based on unified K1 (swkotor.exe) and TSL (swkotor2.exe) UTW implementation.
        Addresses: (K1: swkotor.exe, TSL: swkotor2.exe). TSL addresses: resolve in REVA when
        PyKotorGhidraProject.gpr is open (project may be locked by another process).

        - CSWSWaypoint::LoadWaypoint (main UTW GFF parser)
            K1: 0x005c7f30, TSL: TODO
            Loads all waypoint fields from GFF structure.
            Signature: LoadWaypoint(CSWSWaypoint* this, CResGFF* param_2, CResStruct* param_3).
            Called from LoadWaypoints and LoadFromTemplate.

        - CSWSArea::LoadWaypoints (load waypoints from area GIT)
            K1: 0x00505360, TSL: TODO

        - CSWSWaypoint::LoadFromTemplate (load waypoint template from ResRef)
            K1: 0x005c83b0, TSL: TODO
            Loads GFF then calls LoadWaypoint.

        GFF Field Structure (from LoadWaypoint analysis):
            - Root struct fields:
                - "Tag" (CExoString) - Waypoint tag identifier
                - "LocalizedName" (CExoLocString) - Localized waypoint name
                - "XPosition" (FLOAT) - X coordinate position
                - "YPosition" (FLOAT) - Y coordinate position
                - "ZPosition" (FLOAT) - Z coordinate position
                - "XOrientation" (FLOAT) - X orientation vector component
                - "YOrientation" (FLOAT) - Y orientation vector component
                - "ZOrientation" (FLOAT) - Z orientation vector component
                - "HasMapNote" (BYTE) - Whether waypoint has a map note
                - "MapNoteEnabled" (BYTE) - Whether map note is enabled (only read if HasMapNote is true)
                - "MapNote" (CExoLocString) - Localized map note text (only read if HasMapNote is true)

        Note: UTW files are GFF format files with specific structure definitions (GFFContent.UTW)

    Attributes:
    ----------
        resref: "TemplateResRef" field. The resource reference for this waypoint template.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:15 (TemplateResRef property)

        tag: "Tag" field. Tag identifier for this waypoint.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:16 (Tag property)

        name: "LocalizedName" field. Localized name of the waypoint.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:17 (LocalizedName property)

        has_map_note: "HasMapNote" field. Whether waypoint has a map note.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:19 (HasMapNote property)

        map_note: "MapNote" field. Localized map note text.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:20 (MapNote property)

        map_note_enabled: "MapNoteEnabled" field. Whether map note is enabled.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:21 (MapNoteEnabled property)

        appearance_id: "Appearance" field. Appearance type identifier. Used in toolset only.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:13 (Appearance property)

        palette_id: "PaletteID" field. Palette identifier. Used in toolset only.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:22 (PaletteID property)

        comment: "Comment" field. Developer comment. Used in toolset only.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:23 (Comment property)

        linked_to: "LinkedTo" field. Linked waypoint tag. Not used by the game engine.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:14 (LinkedTo property)

        description: "Description" field. Localized description. Not used by the game engine.
            Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/UTW.cs:18 (Description property)
    """

    BINARY_TYPE = ResourceType.UTW

    def __init__(self):
        self.resref: ResRef = ResRef.from_blank()
        self.comment: str = ""
        self.tag: str = ""

        self.name: LocalizedString = LocalizedString.from_invalid()

        self.has_map_note: bool = False
        self.map_note_enabled: bool = False
        self.map_note: LocalizedString = LocalizedString.from_invalid()

        self.appearance_id: int = 0
        self.palette_id: int = 0

        # Deprecated:
        self.linked_to: str = ""
        self.description: LocalizedString = LocalizedString.from_invalid()


def construct_utw(
    gff: GFF,
) -> UTW:
    """Constructs a UTW object from a GFF structure.

    Defaults when field missing (from engine): K1 CSWSWaypoint::LoadWaypoint (K1: 0x005c7f30, TSL: TODO).
    Tag "", TemplateResRef "", LocalizedName empty; HasMapNote/MapNoteEnabled 0, MapNote empty.
    Position/orient come from GIT (not in UTW root). Optional when missing.

    Reference functions: (1) LoadWaypoint root UTW parser, (2) LoadWaypoints area waypoints,
    (3) LoadFromTemplate, (4) CResGFF::ReadField* for Tag, LocalizedName, HasMapNote, MapNote,
    MapNoteEnabled. TSL same semantics; addresses in UTW class References.
    """
    utw = UTW()

    root: GFFStruct = gff.root
    # Identity/toolset: Appearance, LinkedTo, TemplateResRef, Tag, LocalizedName, Description. K1 LoadWaypoint 0x005c7f30 (Tag/LocalizedName); Appearance/LinkedTo/Description toolset-only. TSL same (addresses in UTW References). Optional.
    utw.appearance_id = root.acquire("Appearance", 0)
    utw.linked_to = root.acquire("LinkedTo", "")
    utw.resref = root.acquire("TemplateResRef", ResRef.from_blank())
    utw.tag = root.acquire("Tag", "")
    utw.name = root.acquire("LocalizedName", LocalizedString.from_invalid())
    utw.description = root.acquire("Description", LocalizedString.from_invalid())
    # Map note: HasMapNote 0, MapNote empty, MapNoteEnabled 0. K1/TSL LoadWaypoint. Optional.
    utw.has_map_note = bool(root.acquire("HasMapNote", 0))
    utw.map_note = root.acquire("MapNote", LocalizedString.from_invalid())
    utw.map_note_enabled = bool(root.acquire("MapNoteEnabled", 0))
    utw.palette_id = root.acquire("PaletteID", 0)
    utw.comment = root.acquire("Comment", "")

    return utw


def dismantle_utw(
    utw: UTW,
    game: Game = Game.K2,  # noqa: ARG001
    *,
    use_deprecated: bool = True,  # noqa: ARG001
) -> GFF:
    """Dismantles a UTW object into a GFF structure. Write same defaults as engine read. K1 LoadWaypoint 0x005c7f30; TSL same (addresses in UTW References)."""
    gff = GFF(GFFContent.UTW)

    root: GFFStruct = gff.root
    root.set_uint8("Appearance", utw.appearance_id)
    # LinkedTo: CExoString; toolset-only. Default "". Omit OK for engine.
    root.set_string("LinkedTo", utw.linked_to)
    # TemplateResRef: CResRef; template ref. Default blank. Omit OK.
    root.set_resref("TemplateResRef", utw.resref)
    # Tag: CExoString; engine default "". K1 LoadWaypoint 0x005c7f30 ReadFieldCExoString default "".
    root.set_string("Tag", utw.tag)
    # LocalizedName: CExoLocString; engine default empty. K1 LoadWaypoint 0x005c7f30 ReadFieldCExoLocString.
    root.set_locstring("LocalizedName", utw.name)
    # Description: CExoLocString; toolset-only. Default empty. Omit OK.
    root.set_locstring("Description", utw.description)
    # HasMapNote: BYTE; engine default 0. K1 LoadWaypoint 0x005c7f30 ReadFieldBYTE(..., 0).
    root.set_uint8("HasMapNote", utw.has_map_note)
    # MapNote: CExoLocString; read only when HasMapNote. Default empty. K1 LoadWaypoint 0x005c7f30.
    root.set_locstring("MapNote", utw.map_note)
    # MapNoteEnabled: BYTE; engine default 0. K1 LoadWaypoint 0x005c7f30 ReadFieldBYTE(..., 0).
    root.set_uint8("MapNoteEnabled", utw.map_note_enabled)
    # PaletteID: BYTE; toolset-only. Default 0. Omit OK.
    root.set_uint8("PaletteID", utw.palette_id)
    # Comment: CExoString; toolset-only. Default "". Omit OK.
    root.set_string("Comment", utw.comment)

    return gff


def read_utw(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> UTW:
    gff: GFF = read_gff(source, offset, size)
    return construct_utw(gff)


def write_utw(
    utw: UTW,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff: GFF = dismantle_utw(utw, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_utw(
    utw: UTW,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff: GFF = dismantle_utw(utw, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
