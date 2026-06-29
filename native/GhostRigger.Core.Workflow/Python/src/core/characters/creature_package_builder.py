"""
Creature Package Builder — generates the full set of files needed to install a
custom creature (like c_drexlf) into KOTOR 1 or 2 as a spawned enemy.

This module orchestrates the existing MDL/MDX export pipeline, GFF writer, and
2DA writer into a single "creature package" that drops straight into the game's
Override folder.

Outputs for a creature named "c_drexlf":
    <output_dir>/c_drexlf.mdl                 — model (from existing export)
    <output_dir>/c_drexlf.mdx                 — animation data
    <output_dir>/c_drexlf.tga                 — diffuse texture (if provided)
    <output_dir>/appearance.2da               — appearance row for the creature
    <output_dir>/c_drexlf.utc                 — creature template (GFF binary)
    <output_dir>/spawn_c_drexlf.nss           — NWScript spawn script (source)
    <output_dir>/INSTALL_README.txt           — installation instructions

The spawn script source (.nss) must be compiled to bytecode (.ncs) using an
external compiler (nwnnsscomp or the community's KOTOR toolchain). The UTC
references the compiled script name. For quick testing without compilation,
the UTC's OnSpawn references KOTOR's built-in `k_def_spawn01` script.
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ─── KOTOR faction IDs (from faction.2da) ────────────────────────────────────
# These are the standard hostile/hostile-to-player factions.
FACTION_HOSTILE = 1     # 1 = hostile to player (standard enemy)
FACTION_FRIENDLY = 2    # 2 = friendly to player
FACTION_NEUTRAL = 5     # 5 = neutral

# ─── KOTOR 2 standard creature appearance type codes ────────────────────────
APPTYPE_S = "S"  # Simple creature (creature-only animations: crun, cwalk)
APPTYPE_F = "F"  # Full animation (humanoid: run, walk, combat — uses supermodel)
APPTYPE_B = "B"  # Body + head (split model)

# ─── Standard KOTOR 2 built-in script ResRefs ───────────────────────────────
# These exist in the stock game and provide basic creature AI behavior.
STANDARD_SCRIPTS = {
    "OnSpawn":         "k_def_spawn01",
    "OnDeath":         "k_def_death01",
    "OnDamaged":       "k_def_damage01",
    "OnAttacked":      "k_def_combat01",
    "OnHeartbeat":     "",
    "OnBlocked":       "",
    "OnConversation":  "",
    "OnDisturbance":   "",
    "OnEndConversation": "",
    "OnUserDefined":   "",
}


@dataclass
class CreatureSpec:
    """Specification for a creature to be generated."""
    resref: str                          # e.g. "c_drexlf"
    display_name: str                    # e.g. "Drexl"
    appearance_type: int = 0             # appearance.2da row (0 = auto-assign)
    model_resref: str = ""               # model name (defaults to resref)
    texture_resref: str = ""             # texture name (defaults to model_resref)
    app_type: str = APPTYPE_S            # S/F/B
    supermodel: str = ""                 # supermodel chain (empty for standalone creatures)
    model_type_col: str = "modela"       # appearance.2da model column (modela for simple)
    texture_col: str = "texa"            # appearance.2da texture column

    # Combat stats
    faction_id: int = FACTION_HOSTILE
    level: int = 5
    max_hp: int = 45
    str_stat: int = 14
    dex_stat: int = 10
    con_stat: int = 12
    int_stat: int = 6
    wis_stat: int = 8
    cha_stat: int = 6

    # Class (0=Soldier, 1=Scout, 2=Scoundrel, etc.)
    class1: int = 0
    race: int = 6  # 6 = Humanoid (default for creatures)

    # Scripts — defaults to standard KOTOR 2 built-in scripts
    scripts: Dict[str, str] = field(default_factory=lambda: dict(STANDARD_SCRIPTS))

    # Scale and movement (appearance.2da columns)
    walk_rate: float = 3.0
    run_rate: float = 6.0
    scale: float = 1.0

    # Texture path (optional — copied into package)
    texture_path: Optional[str] = None

    # Game version
    game_version: str = "K2"  # "K1" or "K2"


@dataclass
class CreaturePackageResult:
    """Result of building a creature package."""
    output_dir: Path
    files_written: List[str] = field(default_factory=list)
    appearance_row: int = -1
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def build_creature_package(
    spec: CreatureSpec,
    output_dir: str | Path,
    *,
    mdl_path: Optional[str | Path] = None,
    existing_appearance_2da: Optional[bytes] = None,
    donor_appearance_row: int = -1,
) -> CreaturePackageResult:
    """Build a complete creature installation package.

    Parameters
    ----------
    spec : CreatureSpec
        Creature specification (name, stats, faction, model reference).
    output_dir : str or Path
        Directory to write all package files into.
    mdl_path : str or Path, optional
        Path to the already-exported MDL file. If provided, it and its MDX
        are copied into the package.
    existing_appearance_2da : bytes, optional
        Raw bytes of the game's existing appearance.2da. If provided, a new row
        is appended. If not, a minimal appearance.2da is generated from scratch.
    donor_appearance_row : int, optional
        If > 0, the new row clones this row from the existing appearance.2da
        and overrides only the model/texture columns. Useful for creatures.

    Returns
    -------
    CreaturePackageResult
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result = CreaturePackageResult(output_dir=out)

    model_resref = spec.model_resref or spec.resref
    tex_resref = spec.texture_resref or model_resref

    # ── 1. Copy model files ──────────────────────────────────────────────
    if mdl_path:
        mdl_p = Path(mdl_path)
        mdx_p = mdl_p.with_suffix(".mdx")
        dest_mdl = out / f"{model_resref}.mdl"
        dest_mdx = out / f"{model_resref}.mdx"
        dest_mdl.write_bytes(mdl_p.read_bytes())
        if mdx_p.exists():
            dest_mdx.write_bytes(mdx_p.read_bytes())
            result.files_written.append(str(dest_mdx))
        result.files_written.append(str(dest_mdl))
        log.info("Creature package: copied %s + %s", dest_mdl.name, dest_mdx.name)

    # ── 2. Copy texture (if provided) ────────────────────────────────────
    if spec.texture_path:
        tex_src = Path(spec.texture_path)
        tex_dest = out / f"{tex_resref}.tga"
        tex_dest.write_bytes(tex_src.read_bytes())
        result.files_written.append(str(tex_dest))
        log.info("Creature package: copied texture %s", tex_dest.name)

    # ── 3. Generate appearance.2da ───────────────────────────────────────
    appearance_row = _generate_appearance_2da(
        out, spec, model_resref, tex_resref,
        existing_appearance_2da, donor_appearance_row,
    )
    result.appearance_row = appearance_row

    # ── 4. Generate UTC creature template ────────────────────────────────
    utc_path = _generate_utc(out, spec, appearance_row)
    result.files_written.append(str(utc_path))

    # ── 5. Generate spawn script source ──────────────────────────────────
    nss_path = _generate_spawn_script(out, spec)
    result.files_written.append(str(nss_path))

    # ── 6. Generate installation readme ──────────────────────────────────
    readme_path = _generate_readme(out, spec, appearance_row)
    result.files_written.append(str(readme_path))

    # Notes for the user
    result.notes.append(
        f"Appearance_Type {appearance_row} assigned to {spec.resref}. "
        f"The UTC template references this row."
    )
    result.notes.append(
        f"Spawn script '{Path(nss_path).stem}' must be compiled to .ncs "
        f"using nwnnsscomp or the KOTOR toolchain. Place the .ncs in Override."
    )
    result.notes.append(
        f"UTC OnSpawn uses built-in '{STANDARD_SCRIPTS['OnSpawn']}' for basic AI. "
        f"For custom spawn behavior, compile and reference the generated .nss."
    )

    return result


# ─── appearance.2da generation ──────────────────────────────────────────────


def _generate_appearance_2da(
    out_dir: Path,
    spec: CreatureSpec,
    model_resref: str,
    tex_resref: str,
    existing_data: Optional[bytes],
    donor_row: int,
) -> int:
    """Generate or append to appearance.2da. Returns the row index assigned."""
    app_path = out_dir / "appearance.2da"

    if existing_data:
        # Parse existing, append row
        try:
            from src.core.templates.twoda import TwoDA
        except ImportError:
            from core.templates.twoda import TwoDA  # type: ignore

        twoda = TwoDA.from_bytes(existing_data, "appearance")

        # Determine new row index
        new_row_idx = len(twoda)

        # If donor row specified, clone it; otherwise use defaults
        donor_cells: Dict[str, str] = {}
        if donor_row >= 0 and donor_row < len(twoda):
            donor = twoda[donor_row]
            for col in twoda.columns:
                donor_cells[col] = donor[col]

        # Override with our creature's values
        col_updates = {
            spec.model_type_col: model_resref,
            spec.texture_col: tex_resref,
            "label": spec.resref,
            "race": spec.resref,
        }

        # Build the new row
        row_data = []
        for col in twoda.columns:
            col_l = col.lower()
            if col_l in {c.lower() for c in col_updates}:
                for k, v in col_updates.items():
                    if k.lower() == col_l:
                        row_data.append(v)
                        break
            elif col.lower() in {k.lower() for k in donor_cells}:
                row_data.append(donor_cells.get(col, twoda.BLANK))
            else:
                row_data.append(twoda.BLANK)

        # Ensure we have exactly the right number of columns
        while len(row_data) < len(twoda.columns):
            row_data.append(twoda.BLANK)
        row_data = row_data[: len(twoda.columns)]

        twoda._rows.append(row_data)
        twoda._labels.append(spec.resref)

        ascii_text = twoda.to_ascii_2da()
        app_path.write_text(ascii_text, encoding="utf-8")
        log.info("appearance.2da: appended row %d for %s", new_row_idx, spec.resref)
        return new_row_idx

    else:
        # Generate a minimal appearance.2da from scratch
        # This handles the case where we can't read the game's existing 2DA.
        # The user should merge this with their game's appearance.2da.
        columns = [
            "label", "racetex", "race",
            spec.model_type_col, spec.texture_col,
            "appearance", "walkdist", "rundist", "size",
            "perspace", "perception", "faction",
        ]
        row_data = [
            spec.resref, tex_resref, spec.resref,
            model_resref, tex_resref,
            spec.app_type,
            str(spec.walk_rate), str(spec.run_rate),
            "SMALL" if spec.app_type == APPTYPE_S else "MEDIUM",
            "0.3", "5.0", str(spec.faction_id),
        ]

        lines = ["2DA V2.0", ""]
        header = "          " + "  ".join(c.ljust(16) for c in columns)
        lines.append(header)
        # Row 0 is a header row in vanilla; put our creature at row 0 in the
        # minimal file — user merges into their game's appearance.2da
        row_str = f"{spec.resref:<10}" + "  ".join(
            (c if c else "****").ljust(16) for c in row_data
        )
        lines.append(row_str)
        app_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.warning(
            "appearance.2da: generated MINIMAL file (no game 2DA provided). "
            "User must merge row 0 into their game's appearance.2da."
        )
        return 0


# ─── UTC creature template generation ───────────────────────────────────────


def _generate_utc(out_dir: Path, spec: CreatureSpec, appearance_row: int) -> Path:
    """Generate a binary UTC creature template file."""
    try:
        from src.formats.gff_types import GffFile, GffFieldType, GffStruct
        from src.formats.gff_writer import GffWriter
    except ImportError:
        from formats.gff_types import GffFile, GffFieldType, GffStruct  # type: ignore
        from formats.gff_writer import GffWriter  # type: ignore

    utc = GffFile()
    utc.file_type = "UTC "
    utc.file_version = "V3.2"

    # CExoLocString for FirstName (StringRef=0, count=1, language=0, value=name)
    # We store it as a GffStruct with the right field type
    root = utc.root

    # Basic identity
    root.set("Tag", GffFieldType.CEXOSTRING, spec.resref)
    root.set("TemplateResRef", GffFieldType.RESREF, spec.resref)

    # FirstName as CExoLocString — we build the raw field
    # CExoLocString: {StringRef: INT32, SubStringCount: UINT32,
    #   [LanguageID: UINT32, StringLength: UINT32, String: chars]*}
    # GffField with type CEXOLOCSTRING stores this as a dict:
    #   {str_ref: int, strings: {lang_id: "text"}}
    first_name_field = GffField(
        type=GffFieldType.CEXOLOCSTRING,
        value={"str_ref": -1, "strings": {0: spec.display_name}},
    )
    root.fields["FirstName"] = first_name_field

    root.set("Appearance_Type", GffFieldType.UINT16, appearance_row)
    root.set("Gender", GffFieldType.BYTE, 0)  # 0 = male, 1 = female, 2 = none
    root.set("Race", GffFieldType.BYTE, spec.race)

    # Class and level
    root.set("Class1", GffFieldType.BYTE, spec.class1)
    root.set("ClassList", GffFieldType.LIST, [_make_class_struct(spec.class1, spec.level)])

    root.set("Level", GffFieldType.BYTE, spec.level)

    # Stats
    root.set("Str", GffFieldType.BYTE, spec.str_stat)
    root.set("Dex", GffFieldType.BYTE, spec.dex_stat)
    root.set("Con", GffFieldType.BYTE, spec.con_stat)
    root.set("Int", GffFieldType.BYTE, spec.int_stat)
    root.set("Wis", GffFieldType.BYTE, spec.wis_stat)
    root.set("Cha", GffFieldType.BYTE, spec.cha_stat)

    # HP
    root.set("MaxHitPoints", GffFieldType.INT16, spec.max_hp)
    root.set("CurrentHitPoints", GffFieldType.INT16, spec.max_hp)
    root.set("MaxFP", GffFieldType.INT16, 0)
    root.set("CurrentFP", GffFieldType.INT16, 0)

    # Faction — hostile for enemies
    root.set("FactionID", GffFieldType.UINT32, spec.faction_id)

    # Scripts — reference KOTOR's built-in default scripts
    for event_name, script_ref in spec.scripts.items():
        if script_ref:
            root.set(event_name, GffFieldType.RESREF, script_ref)

    # Other flags
    root.set("NoPermDeath", GffFieldType.BYTE, 0)
    root.set("WillNotRender", GffFieldType.BYTE, 0)
    root.set("Disarmable", GffFieldType.BYTE, 1)
    root.set("BodyBag", GffFieldType.BYTE, 0)
    root.set("MultiplierSet", GffFieldType.BYTE, 0)
    root.set("BlindSpot", GffFieldType.FLOAT, 0.0)
    root.set("NotReorienting", GffFieldType.BYTE, 0)
    root.set("SoundSetFile", GffFieldType.UINT16, 0)

    # Serialize
    writer = GffWriter(utc)
    utc_bytes = writer.serialize()

    utc_path = out_dir / f"{spec.resref}.utc"
    utc_path.write_bytes(utc_bytes)
    log.info("UTC: wrote %s (%d bytes, appearance=%d)",
             utc_path.name, len(utc_bytes), appearance_row)
    return utc_path


def _make_class_struct(class_id: int, level: int):
    """Build a Class struct for the ClassList."""
    from src.formats.gff_types import GffStruct, GffFieldType

    cls = GffStruct()
    cls.set("Class", GffFieldType.BYTE, class_id)
    cls.set("ClassLevel", GffFieldType.BYTE, level)
    return cls


# ─── Spawn script generation ────────────────────────────────────────────────


def _generate_spawn_script(out_dir: Path, spec: CreatureSpec) -> Path:
    """Generate an NWScript .nss source file for spawning the creature.

    This script can be attached to a placeable's OnUsed event, an area's
    OnEnter event, or called from a dialogue. It spawns the creature at a
    specified location.
    """
    nss_path = out_dir / f"spawn_{spec.resref}.nss"

    script = f'''// ═══════════════════════════════════════════════════════════════
// Spawn script: {spec.display_name} ({spec.resref})
// Generated by GhostRigger Character Builder
//
// This script spawns the {spec.display_name} creature at the location of
// the calling object (or a waypoint if specified).
//
// Usage options:
//   1. Attach to a Placeable's OnUsed event (creature spawns when used)
//   2. Attach to an Area's OnEnter event (spawns when player enters)
//   3. Call from dialogue: ExecuteScript("spawn_{spec.resref}", ...)
//
// COMPILE: Use nwnnsscomp or the KOTOR Toolchain to compile this .nss
//          to a .ncs bytecode file. Place the .ncs in the Override folder.
//
//   nwnnsscomp -c -g k2 spawn_{spec.resref}.nss
// ═══════════════════════════════════════════════════════════════

#include "k_inc_generic"

void main()
{{
    // ── Spawn location ──────────────────────────────────────────────
    // Spawn at the caller's position (Placeable/Waypoint).
    // Change OBJECT_SELF to a specific waypoint ResRef for fixed spawns.
    location spawnLoc = GetLocation(OBJECT_SELF);

    // Offset slightly to avoid spawning inside the caller
    vector vPos = GetPositionFromLocation(spawnLoc);
    vPos.x += 1.0f;  // 1 meter to the right
    spawnLoc = Location(GetAreaFromLocation(spawnLoc), vPos,
                        GetFacingFromLocation(spawnLoc));

    // ── Spawn the creature ──────────────────────────────────────────
    // OBJECT_TYPE_CREATURE, template ResRef, location, use appearance
    object oCreature = CreateObject(OBJECT_TYPE_CREATURE,
                                     "{spec.resref}",
                                     spawnLoc);

    // ── Make it hostile (if it isn't already via UTC FactionID) ─────
    // ChangeShintoHostile is not available; use standard faction change:
    // ChangeToStandardFaction(oCreature, STANDARD_FACTION_HOSTILE_1);

    // ── Visual effect (optional) ────────────────────────────────────
    // Apply a spawn-in visual effect
    ApplyEffectAtLocation(DURATION_TYPE_INSTANT,
                          EffectVisualEffect(VFX_FNF_SUMMON_MONSTER_1),
                          spawnLoc);

    // ── Debug message ───────────────────────────────────────────────
    // SendMessageToPC(GetFirstPC(), "{spec.display_name} spawned!");
}}
'''

    nss_path.write_text(script, encoding="utf-8")
    log.info("NSS: wrote %s (compile with nwnnsscomp)", nss_path.name)
    return nss_path


# ─── Installation readme ────────────────────────────────────────────────────


def _generate_readme(out_dir: Path, spec: CreatureSpec, appearance_row: int) -> Path:
    """Generate a human-readable installation guide."""
    readme_path = out_dir / "INSTALL_README.txt"

    game_name = "Knights of the Old Republic II: The Sith Lords" if spec.game_version == "K2" \
        else "Knights of the Old Republic"

    files_list = f"  {spec.resref}.mdl         — 3D model\n"
    files_list += f"  {spec.resref}.mdx         — Animation data\n"
    if spec.texture_path:
        files_list += f"  {spec.texture_resref or spec.resref}.tga         — Diffuse texture\n"
    files_list += f"  appearance.2da    — Character appearance table (row {appearance_row})\n"
    files_list += f"  {spec.resref}.utc         — Creature template\n"
    files_list += f"  spawn_{spec.resref}.nss   — Spawn script SOURCE (needs compilation)\n"

    readme = f'''╔══════════════════════════════════════════════════════════════╗
║       GhostRigger Character Builder — Creature Package       ║
╚══════════════════════════════════════════════════════════════╝

  Creature:   {spec.display_name} ({spec.resref})
  Game:       {game_name}
  Appearance: Row {appearance_row} in appearance.2da
  Faction:    {"Hostile (enemy)" if spec.faction_id == FACTION_HOSTILE else str(spec.faction_id)}
  Level:      {spec.level} (HP: {spec.max_hp})

═══════════════════════════════════════════════════════════════
  FILES IN THIS PACKAGE
═══════════════════════════════════════════════════════════════

{files_list}

═══════════════════════════════════════════════════════════════
  INSTALLATION (QUICK — MODEL OVERRIDE ONLY)
═══════════════════════════════════════════════════════════════

If you just want to replace the model (existing c_drexlf spawns):

  1. Copy {spec.resref}.mdl and {spec.resref}.mdx to:
     <game>/Override/

  2. Copy the texture ({spec.texture_resref or spec.resref}.tga) to:
     <game>/Override/

  3. Launch the game. The model will replace the stock c_drexlf.

═══════════════════════════════════════════════════════════════
  INSTALLATION (FULL — SPAWN AS NEW ENEMY)
═══════════════════════════════════════════════════════════════

To spawn {spec.display_name} as a test enemy anywhere in the game:

  1. Copy ALL files to <game>/Override/

  2. If you already have an appearance.2da in Override, you must MERGE:
     - Open your existing appearance.2da in a text editor
     - Add the row from THIS package's appearance.2da at the end
     - Note the row number (0-indexed)
     - Edit {spec.resref}.utc and update Appearance_Type to match

  3. COMPILE the spawn script:
     - Use nwnnsscomp:  nwnnsscomp -c -g k2 spawn_{spec.resref}.nss
     - This produces spawn_{spec.resref}.ncs
     - Copy spawn_{spec.resref}.ncs to Override/

  4. IN-GAME TESTING via console:
     - Enable cheats: add "EnableCheats=1" to swkotor2.ini under [Game Options]
     - Press ~ to open console (type invisible)
     - Type: spawn {spec.resref}
     - The creature should spawn at your position

  5. AMBIENT SPAWN via script:
     - Attach spawn_{spec.resref} to a Placeable's OnUsed event
     - Or attach it to an Area's OnEnter event
     - Or call ExecuteScript("spawn_{spec.resref}", OBJECT_SELF)

═══════════════════════════════════════════════════════════════
  TROUBLESHOOTING
═══════════════════════════════════════════════════════════════

  PROBLEM: Creature is invisible
  CAUSE:   Missing texture in Override, or texture name mismatch
  FIX:     Ensure {spec.texture_resref or spec.resref}.tga is in Override

  PROBLEM: Creature T-pose / no animations
  CAUSE:   Supermodel reference wrong, or bone names don't match
  FIX:     Check the MDL's supermodel field matches the game's chain.
           For K2 creatures with NULL supermodel, animations are self-contained.

  PROBLEM: Game crashes on spawn
  CAUSE:   appearance.2da row corrupted or texture name mismatch
  FIX:     Verify appearance.2da row {appearance_row} has valid model/texture refs

  PROBLEM: spawn command not recognized
  CAUSE:   EnableCheats not set, or using wrong console key
  FIX:     Add EnableCheats=1 to swkotor2.ini [Game Options] section

═══════════════════════════════════════════════════════════════
  CREDITS
═══════════════════════════════════════════════════════════════

  Model exported by GhostRigger Character Builder
  {spec.display_name} — restored cut content
  Generated for {game_name}
'''

    readme_path.write_text(readme, encoding="utf-8")
    return readme_path
