# UTC Editor: Field Types and Ranges

This document records GFF field types and valid ranges for the Creature (UTC) format as verified against the game executables. Use these ranges when setting spinbox min/max in the Holocron Toolset UTC editor and when validating mod files.

**Verification:** The reader function `CSWSCreatureStats::ReadStatsFromGff` in KotOR and TSL was analyzed in reva (Ghidra) to confirm which GFF field names are read and with which type (BYTE, SHORT, WORD, INT, FLOAT, etc.). K1: ReadStatsFromGff @ 0x005afce0 (LoadCreatureData @ 0x00560e60 calls it). TSL: ReadStatsFromGff @ 0x006ec350.

## Hit Points and Force Points (SHORT)

All of the following are read with `CResGFF::ReadFieldSHORT(param_2, "FieldName", …)` in `ReadStatsFromGff` (K1 @ 0x005afce0). Signed 16-bit range is -32768–32767; the engine uses non-negative values only, so UI min/max 0–32767.

| GFF Field          | UI Control    | Type  | Min  | Max   | Reva (line) |
|--------------------|---------------|-------|------|------|--------------|
| HitPoints          | Base HP       | SHORT | 0    | 32767| ReadFieldSHORT param_2 "HitPoints" (~795) |
| CurrentHitPoints   | Current HP    | SHORT | 0    | 32767| ReadFieldSHORT param_2 "CurrentHitPoints" (~806) |
| ForcePoints        | Max FP        | SHORT | 0    | 32767| ReadFieldSHORT param_2 "ForcePoints" (~801) |
| CurrentForce       | Current FP    | SHORT | 0    | 32767| ReadFieldSHORT param_2 "CurrentForce" (~810) |

**Note:** MaxHitPoints is not read as a separate root field in ReadStatsFromGff; the engine uses HitPoints as max and CurrentHitPoints as current. The toolset may expose "Max HP" as an alias for HitPoints.

**In-game:** For NPCs (is_pc==0), the engine may recompute current HP/FP from level and Con/Wis/Cha modifiers after loading. Current HP can temporarily exceed max from buffs.

## Ability Scores (BYTE)

Str, Dex, Con, Int, Wis, Cha are read with `CResGFF::ReadFieldBYTE` (0–255). Modifiers are derived as (ability - 10) / 2.

| GFF Field | UI Control  | Type | Min | Max | Default |
|-----------|-------------|------|-----|-----|--------|
| Str       | Strength    | BYTE | 0   | 255 | 0      |
| Dex       | Dexterity   | BYTE | 0   | 255 | 0      |
| Con       | Constitution| BYTE | 0   | 255 | 0      |
| Int       | Intelligence| BYTE | 0   | 255 | 0      |
| Wis       | Wisdom      | BYTE | 0   | 255 | 0      |
| Cha       | Charisma    | BYTE | 0   | 255 | 0      |

**Typical modder range:** 8–20 for normal creatures.

## Save bonuses (SHORT, used as signed byte)

Read in K1 `ReadStatsFromGff` with `CResGFF::ReadFieldSHORT(param_2, "willbonus", …)`, `"fortbonus"`, `"refbonus"`; default is `(short)(char)this->will_bonus` (etc.), so the engine treats the value as signed-byte range. Written with `WriteFieldSHORT` with `(short)(char)value` in SaveStats. Effective range -128–127.

| GFF Field   | UI Control   | Type  | Min  | Max |
|------------|--------------|-------|-----|-----|
| fortbonus  | Fortitude    | SHORT | -128| 127 |
| refbonus   | Reflex       | SHORT | -128| 127 |
| willbonus  | Will         | SHORT | -128| 127 |

## Natural AC and Challenge Rating

| GFF Field        | UI Control       | Type  | Min | Max  |
|------------------|------------------|-------|-----|------|
| NaturalAC        | Armor Class      | BYTE  | 0   | 255  |
| ChallengeRating  | Challenge Rating | FLOAT | 0   | 100  |

## Skill ranks (SkillList Rank)

Each skill in the SkillList list has a `Rank` field written with `WriteFieldBYTE`. Range 0–255. (Engine may clamp to -127–127 when saving; editor uses 0–255.)

| UI Control       | GFF              |
|------------------|------------------|
| Computer Use     | SkillList Rank   |
| Demolitions      | SkillList Rank   |
| Stealth          | SkillList Rank   |
| Awareness        | SkillList Rank   |
| Persuade         | SkillList Rank   |
| Repair           | SkillList Rank   |
| Security         | SkillList Rank   |
| Treat Injury     | SkillList Rank   |

## Class levels (SHORT)

| GFF Field   | UI Control  | Type  | Min | Max   |
|-------------|-------------|-------|-----|-------|
| ClassLevel  | Class 1 / 2 | SHORT | 0   | 32767 |

Read with `ReadFieldSHORT` in ClassList element. KotOR cap is 20 per class; 50 allows modded games; editor allows full SHORT range.

## Identity and appearance (engine clamping)

| GFF Field   | UI Control | Type  | Min | Max | Notes |
|-------------|------------|-------|-----|-----|-------|
| GoodEvil    | Alignment  | BYTE  | 0   | 100 | Clamped: if (value > 100) value = 100 |
| Gender      | Gender     | BYTE  | 0   | 4   | Clamped: if (value > 4) value = 4. Index into gender.2da (e.g. 0=Male, 1=Female) |
| Race        | Race       | BYTE  | 0   | 255 | Index into racialtypes.2da. **Validation:** if value >= race_row_count (race.2da row count), creature load **fails** (engine returns error). Use only valid row indices. |
| SubraceIndex| Subrace    | BYTE  | 0   | 255 | Index into subrace.2da; refines race (e.g. subspecies). No engine clamp; invalid index can cause odd behavior. |
| FactionID   | Faction    | WORD  | 0   | 65535 | Index into repute.2da / faction table |
| PortraitId  | Portrait   | WORD  | 0   | 65533 | In K1: if (value < 0xfffe) use as portrait.2da row; else use Portrait ResRef. So 0–65533 = row, 65534/65535 = ResRef. |

## Perception

| GFF Field        | UI Control | Type | Min | Max | Notes |
|------------------|------------|------|-----|-----|-------|
| PerceptionRange  | Perception | BYTE | 0   | 255 | Row index into ranges.2da (primary/secondary detection range). Default 11 when missing. Value 12 (0xC) = use appearance PERCEPTIONDIST from appearance.2da. Invalid row can cause creature load failure (0x5f5). Used only for NPCs; PCs use fixed range. |

## Movement

| GFF Field   | UI Control | Type | Min | Max | Notes |
|-------------|------------|------|-----|-----|-------|
| WalkRate    | Speed      | INT  | 0   | (creaturespeed.2da rows - 1) | Row index into creaturespeed.2da (WALKRATE column). Used for walk/run speed in pathfinding and animation. Invalid index can yield default or broken movement. |

## KotOR 2 only

| GFF Field      | UI Control    | Type  | Min | Max | Notes |
|----------------|---------------|-------|-----|-----|-------|
| BlindSpot      | Blindspot     | FLOAT | 0   | 360 | Angle in degrees (AI perception blind spot). |
| MultiplierSet  | Multiplier Set| BYTE  | 0   | 255 | Encounter scaling index; written with WriteFieldBYTE in SaveStats. 0 = typical default. |

## ResRef and TemplateResRef

All ResRef fields (TemplateResRef, Conversation, Portrait, script ResRefs, etc.) use the engine's CResRef type, which stores at most **16 characters**. Longer strings are truncated when the game loads the GFF. The UTC editor enforces max length 16 on Template ResRef and other ResRef inputs.

## Methodology

Field types and ranges were determined by inspecting the creature-stats reader in the game executables: locating the GFF field name and the corresponding `ReadField*` call (ReadFieldBYTE, ReadFieldSHORT, ReadFieldWORD, ReadFieldINT, ReadFieldCResRef, etc.) and applying type-appropriate min/max (e.g. BYTE → 0–255; SHORT → 0–32767 for non-negative; WORD → 0–65535).

## Verification (Reva)

Verified against K1 `k1_win_gog_swkotor.exe` (and TSL where applicable) via PyKotor-reva MCP. Function: `CSWSCreatureStats::ReadStatsFromGff` — K1 @ 0x005afce0, TSL @ 0x006ec350.

**K1 (swkotor.exe) confirmations:**

- **Gender:** `ReadFieldBYTE(…, "Gender", …)` then `if (4 < bVar7) bVar7 = 4` → effective 0–4.
- **GoodEvil:** `ReadFieldBYTE(…, "GoodEvil", …)` then `if (100 < uVar12) uVar12 = 100` → effective 0–100.
- **Race:** `ReadFieldBYTE(…, "Race", …)`; if `(Rules->internal).race_row_count <= bVar7` then return 0x5f4 (load fails).
- **Str, Dex, Con, Int, Wis, Cha:** `ReadFieldBYTE` with no clamp → 0–255.
- **NaturalAC:** `ReadFieldBYTE(…, "NaturalAC", …)` → 0–255.
- **PortraitId:** `ReadFieldWORD(…, "PortraitId", …, 0xffff)`; if `uVar12 < 0xfffe` use as 2DA row, else use Portrait ResRef.
- **FactionID:** `ReadFieldWORD(…, "FactionID", …)` → 0–65535.
- **ChallengeRating:** `ReadFieldFLOAT(…, "ChallengeRating", …)`; no clamp in reader.
- **fortbonus, refbonus, willbonus:** `ReadFieldSHORT(param_2, "willbonus", …, (short)(char)this->will_bonus)` (and same for fortbonus, refbonus); result stored in byte → effective -128–127.
- **ClassLevel:** `ReadFieldSHORT` in ClassList element.
- **PerceptionRange:** `ReadFieldBYTE(…, "PerceptionRange", …, 0xb)`; invalid index can return 0x5f5.

TSL ReadStatsFromGff (0x006ec350) contains the same field names; BlindSpot and MultiplierSet strings exist in TSL executable. Editor min/max and tooltips match the above.

## FeatList and ClassList (Powers)

| GFF Structure | UI Control | Element Field | Type | Min | Max | Notes |
|---------------|------------|---------------|------|-----|-----|-------|
| FeatList | featList | Feat | BYTE | 0 | 255 | Index into feats.2da. Each list element stores one feat ID. ReadStatsFromGff @ 0x005afce0; SaveClassInfo writes. |
| ClassList | powerList | Class, ClassLevel; KnownList0/1/2 Spell | INT, SHORT; WORD | - | - | ClassList holds classes and levels; KnownList entries contain Spell IDs (WORD) referencing spells.2da. Powers are aggregated from all classes for display. |
