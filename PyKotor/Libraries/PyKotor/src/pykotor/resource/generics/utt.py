"""UTT (trigger) generic: GFF-based trigger definitions, scripts, and trap settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pykotor.common.language import LocalizedString
from pykotor.common.misc import Game, ResRef
from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff, read_gff, write_gff
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.formats.gff import GFFStruct
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class UTT:
    """Stores trigger data.

    UTT files are GFF-based format files that store trigger definitions including
    trap mechanics, script hooks, and activation settings.

    References:
    ----------
        Based on unified K1 (swkotor.exe) and TSL (swkotor2.exe) UTT implementation.
        Addresses: (K1: swkotor.exe, TSL: swkotor2.exe). TSL addresses: resolve in REVA when
        PyKotorGhidraProject.gpr is open (project may be locked by another process).

        - CSWSTrigger::LoadTrigger (main UTT GFF parser)
            K1: 0x0058da80, TSL: TODO
            Loads all trigger fields from GFF structure.
            Signature: LoadTrigger(CSWSTrigger* this, CResGFF* param_2, CResStruct* param_3).
            Called from LoadTriggers and LoadFromTemplate.

        - CSWSArea::LoadTriggers (load triggers from area GIT)
            K1: 0x0050a350, TSL: TODO

        - CSWSTrigger::LoadFromTemplate (load trigger template from ResRef)
            K1: 0x0058ed70, TSL: TODO
            Loads GFF then calls LoadTrigger.

        - CSWSTrigger::LoadTriggerGeometry (trigger geometry)
            K1: 0x0058d060, TSL: TODO

        GFF Field Structure (from LoadTrigger analysis):
            - Root struct fields:
                - "PortraitId" (WORD) - Portrait ID (0xffff = use Portrait ResRef)
                - "Portrait" (CResRef) - Portrait resource reference (if PortraitId == 0xffff)
                - "CreatorId" (DWORD) - Creator object ID (default 0x7f000000)
                - Script fields:
                    - "ScriptHeartbeat" (CResRef) - Heartbeat script
                    - "ScriptOnEnter" (CResRef) - On enter script
                    - "ScriptOnExit" (CResRef) - On exit script
                    - "ScriptUserDefine" (CResRef) - User defined script
                    - "OnTrapTriggered" (CResRef) - Trap triggered script
                    - "OnDisarm" (CResRef) - Disarm script
                    - "OnClick" (CResRef) - Click script
                - "TrapType" (BYTE) - Trap type identifier
                - "TrapOneShot" (BYTE) - Whether trap fires only once
                - "LinkedTo" (CExoString) - Linked object tag
                - "LinkedToFlags" (BYTE) - Linked object flags
                - "LinkedToModule" (CResRef) - Linked module ResRef
                - "AutoRemoveKey" (BYTE) - Whether key is auto-removed
                - "Tag" (CExoString) - Trigger tag identifier
                - "LocalizedName" (CExoLocString) - Localized trigger name
                - "Faction" (DWORD) - Faction identifier
                - "KeyName" (CExoString) - Key name/ResRef
                - "TrapDisarmable" (BYTE) - Whether trap is disarmable
                - "TrapDetectable" (BYTE) - Whether trap is detectable
                - "Cursor" (BYTE) - Cursor type identifier
                - "TransitionDestination" (CExoLocString) - Transition destination text
                - Additional fields for highlight, geometry, etc.

        Note: UTT files are GFF format files with specific structure definitions (GFFContent.UTT)

    Attributes:
    ----------
        resref: "TemplateResRef" field. The resource reference for this trigger template.
        tag: "Tag" field. Tag identifier for this trigger.
        auto_remove_key: "AutoRemoveKey" field. Whether key is removed after use.
        faction_id: "Faction" field. Faction identifier.
        cursor_id: "Cursor" field. Cursor type identifier.
        highlight_height: "HighlightHeight" field. Height of highlight area.
        key_name: "KeyName" field. Tag of the key item required.
        type_id: "Type" field. Trigger type identifier.
        is_trap: "TrapFlag" field. Whether trigger has a trap.
        trap_type: "TrapType" field. Type of trap.
        trap_once: "TrapOneShot" field. Whether trap fires only once.
        trap_detectable: "TrapDetectable" field. Whether trap is detectable.
        trap_detect_dc: "TrapDetectDC" field. Difficulty class to detect trap.
        trap_disarmable: "TrapDisarmable" field. Whether trap is disarmable.
        trap_disarm_dc: "DisarmDC" field. Difficulty class to disarm trap.
        on_disarm: "OnDisarm" field. Script to run when trap is disarmed.
        on_trap_triggered: "OnTrapTriggered" field. Script to run when trap triggers.
        on_click: "OnClick" field. Script to run when trigger is clicked.
        on_heartbeat: "ScriptHeartbeat" field. Script to run on heartbeat.
        on_enter: "ScriptOnEnter" field. Script to run when area is entered.
        on_exit: "ScriptOnExit" field. Script to run when area is exited.
        on_user_defined: "ScriptUserDefine" field. Script to run on user-defined event.
        comment: "Comment" field. Developer comment.
        palette_id: "PaletteID" field. Palette identifier. Used in toolset only.
        name: "LocalizedName" field. Localized name. Not used by the game engine.
        loadscreen_id: "LoadScreenID" field. Load screen identifier. Not used by the game engine.
        portrait_id: "PortraitId" field. Portrait identifier. Not used by the game engine.
    """

    BINARY_TYPE = ResourceType.UTT

    def __init__(self):
        self.resref: ResRef = ResRef.from_blank()
        self.comment: str = ""
        self.tag: str = ""

        self.name: LocalizedString = LocalizedString.from_invalid()

        self.faction_id: int = 0
        self.cursor_id: int = 0
        self.type_id: int = 0

        self.auto_remove_key: bool = True
        self.key_name: str = ""

        self.highlight_height: float = 0.0

        self.is_trap: bool = False
        self.trap_type: int = 0
        self.trap_once: bool = False
        self.trap_detectable: bool = False
        self.trap_detect_dc: int = 0
        self.trap_disarmable: bool = False
        self.trap_disarm_dc: int = 0

        self.on_disarm: ResRef = ResRef.from_blank()
        self.on_click: ResRef = ResRef.from_blank()
        self.on_trap_triggered: ResRef = ResRef.from_blank()
        self.on_heartbeat: ResRef = ResRef.from_blank()
        self.on_enter: ResRef = ResRef.from_blank()
        self.on_exit: ResRef = ResRef.from_blank()
        self.on_user_defined: ResRef = ResRef.from_blank()

        # Deprecated:
        self.portrait_id: int = 0
        self.loadscreen_id: int = 0
        self.palette_id: int = 0
        self.name = LocalizedString.from_invalid()


def construct_utt(
    gff: GFF,
) -> UTT:
    """Constructs a UTT object from a GFF structure.

    Defaults when field missing (from engine): K1 CSWSTrigger::LoadTrigger (K1: 0x0058da80, TSL: TODO).
    Tag "", TemplateResRef "", CreatorId 0x7f000000; scripts ResRef ""; TrapFlag/TrapType/TrapOneShot etc. 0.
    Optional when missing.

    Reference functions: (1) LoadTrigger root UTT parser, (2) LoadTriggers area triggers,
    (3) LoadFromTemplate, (4) LoadTriggerGeometry, (5) CResGFF::ReadField* for Tag, TemplateResRef,
    scripts, trap fields. TSL same semantics; addresses in UTT class References.
    """
    utt = UTT()

    root: GFFStruct = gff.root
    # Identity: Tag "", TemplateResRef "". K1 LoadTrigger 0x0058da80; TSL same (addresses in UTT References). Optional.
    utt.tag = root.acquire("Tag", "")
    utt.resref = root.acquire("TemplateResRef", ResRef.from_blank())
    # Key/faction/cursor: AutoRemoveKey 0, Faction 0, Cursor 0, KeyName "", HighlightHeight 0.0, Type 0. K1/TSL LoadTrigger. Optional.
    utt.auto_remove_key = bool(root.acquire("AutoRemoveKey", 0))
    utt.faction_id = root.acquire("Faction", 0)
    # Cursor: BYTE default 0. Omit OK.
    utt.cursor_id = root.acquire("Cursor", 0)
    # HighlightHeight: FLOAT default 0.0. Omit OK.
    utt.highlight_height = root.acquire("HighlightHeight", 0.0)
    # KeyName: CExoString "". Omit OK.
    utt.key_name = root.acquire("KeyName", "")
    # Type: INT32 default 0. Omit OK.
    utt.type_id = root.acquire("Type", 0)
    # Trap: TrapDetectable, TrapDetectDC, TrapDisarmable, DisarmDC, TrapFlag, TrapOneShot, TrapType. Default 0. K1/TSL LoadTrigger. Optional.
    utt.trap_detectable = bool(root.acquire("TrapDetectable", 0))
    utt.trap_detect_dc = root.acquire("TrapDetectDC", 0)
    utt.trap_disarmable = bool(root.acquire("TrapDisarmable", 0))
    utt.trap_disarm_dc = root.acquire("DisarmDC", 0)
    utt.is_trap = bool(root.acquire("TrapFlag", 0))
    utt.trap_once = bool(root.acquire("TrapOneShot", 0))
    utt.trap_type = root.acquire("TrapType", 0)
    # Scripts: OnDisarm, OnTrapTriggered, OnClick, ScriptHeartbeat, ScriptOnEnter, ScriptOnExit, ScriptUserDefine. ResRef "". K1/TSL LoadTrigger. Optional.
    utt.on_disarm = root.acquire("OnDisarm", ResRef.from_blank())
    utt.on_trap_triggered = root.acquire("OnTrapTriggered", ResRef.from_blank())
    utt.on_click = root.acquire("OnClick", ResRef.from_blank())
    utt.on_heartbeat = root.acquire("ScriptHeartbeat", ResRef.from_blank())
    utt.on_enter = root.acquire("ScriptOnEnter", ResRef.from_blank())
    utt.on_exit = root.acquire("ScriptOnExit", ResRef.from_blank())
    utt.on_user_defined = root.acquire("ScriptUserDefine", ResRef.from_blank())
    # Comment/LocalizedName/LoadScreenID/PortraitId/PaletteID: toolset/display; defaults "", from_invalid(), 0.
    utt.comment = root.acquire("Comment", "")
    utt.name = root.acquire("LocalizedName", LocalizedString.from_invalid())
    utt.loadscreen_id = root.acquire("LoadScreenID", 0)
    utt.portrait_id = root.acquire("PortraitId", 0)
    utt.palette_id = root.acquire("PaletteID", 0)

    return utt


def dismantle_utt(
    utt: UTT,
    game: Game = Game.K2,
    *,
    use_deprecated: bool = True,
) -> GFF:
    """Dismantles a UTT object into a GFF structure.

    Args:
    ----
        utt: UTT - The UTT object to dismantle
        game: Game - The game the UTT is for (default K2)
        use_deprecated: bool - Whether to include deprecated fields (default True)

    Returns:
    -------
        GFF - The dismantled UTT as a GFF structure

    Write same defaults as engine read. K1 LoadTrigger 0x0058da80; TSL same (addresses in UTT References).
    """
    gff = GFF(GFFContent.UTT)

    root = gff.root
    # Tag: CExoString; engine default "". K1 LoadTrigger 0x0058da80.
    root.set_string("Tag", utt.tag)
    root.set_resref("TemplateResRef", utt.resref)
    # AutoRemoveKey/Faction/Cursor/HighlightHeight/KeyName/Type: defaults 0 or 0.0 or "". K1 0x0058da80.
    root.set_uint8("AutoRemoveKey", utt.auto_remove_key)
    root.set_uint32("Faction", utt.faction_id)
    root.set_uint8("Cursor", utt.cursor_id)
    root.set_single("HighlightHeight", utt.highlight_height)
    root.set_string("KeyName", utt.key_name)
    root.set_int32("Type", utt.type_id)
    # Trap fields: BYTE/INT defaults 0. K1 LoadTrigger ReadFieldBYTE.
    root.set_uint8("TrapDetectable", utt.trap_detectable)
    root.set_uint8("TrapDetectDC", utt.trap_detect_dc)
    root.set_uint8("TrapDisarmable", utt.trap_disarmable)
    root.set_uint8("DisarmDC", utt.trap_disarm_dc)
    root.set_uint8("TrapFlag", utt.is_trap)
    root.set_uint8("TrapOneShot", utt.trap_once)
    root.set_uint8("TrapType", utt.trap_type)
    # Scripts: CResRef; engine default "". K1 LoadTrigger 0x0058da80 ReadFieldCResRef.
    root.set_resref("OnDisarm", utt.on_disarm)
    root.set_resref("OnTrapTriggered", utt.on_trap_triggered)
    root.set_resref("OnClick", utt.on_click)
    root.set_resref("ScriptHeartbeat", utt.on_heartbeat)
    root.set_resref("ScriptOnEnter", utt.on_enter)
    root.set_resref("ScriptOnExit", utt.on_exit)
    root.set_resref("ScriptUserDefine", utt.on_user_defined)
    root.set_string("Comment", utt.comment)

    root.set_uint8("PaletteID", utt.palette_id)

    if use_deprecated:
        root.set_locstring("LocalizedName", utt.name)
        root.set_uint16("LoadScreenID", utt.loadscreen_id)
        root.set_uint16("PortraitId", utt.portrait_id)

    return gff


def read_utt(
    source: SOURCE_TYPES,
    offset: int = 0,
    size: int | None = None,
) -> UTT:
    gff = read_gff(source, offset, size)
    return construct_utt(gff)


def write_utt(
    utt: UTT,
    target: TARGET_TYPES,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
):
    gff = dismantle_utt(utt, game, use_deprecated=use_deprecated)
    write_gff(gff, target, file_format)


def bytes_utt(
    utt: UTT,
    game: Game = Game.K2,
    file_format: ResourceType = ResourceType.GFF,
    *,
    use_deprecated: bool = True,
) -> bytes:
    gff = dismantle_utt(utt, game, use_deprecated=use_deprecated)
    return bytes_gff(gff, file_format)
