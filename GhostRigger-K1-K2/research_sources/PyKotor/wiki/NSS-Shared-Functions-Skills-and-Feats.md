# Skills and Feats

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript skill and feat functions. These functions allow scripts to check skill ranks, verify feat acquisition, manage character levels, and award experience points.

---

## Skills and Feats Fundamentals

### Understanding Skills

Skills represent a creature's proficiency in various abilities. KotOR has 8 skills:

- **Computer Use** - Hacking terminals, using computer systems
- **Demolitions** - Disarming and setting explosives
- **Stealth** - Moving silently and hiding
- **Awareness** - Detecting hidden creatures and objects
- **Persuade** - Influencing others in conversations
- **Repair** - Fixing equipment and droids
- **Security** - Picking locks
- **Treat Injury** - Healing wounds

Skills are ranked from 0 (untrained) up to a maximum determined by level and class.

### Understanding Feats

Feats are special abilities and proficiencies that characters can acquire. They include:

- **Combat Feats** - Weapon proficiencies, combat techniques
- **Jedi Feats** - Force powers and lightsaber techniques
- **General Feats** - Various abilities and bonuses

Feats are typically acquired at level-up or through special events.

---

## Skill Functions

### GetSkillRank

**Routine:** 315

#### Function Signature

```nss
int GetSkillRank(int nSkill, object oTarget = OBJECT_SELF);
```

#### Description

Gets the skill rank (proficiency level) of a creature in a specific skill. Returns the total effective skill rank, including bonuses from ability modifiers, feats, and equipment.

#### Parameters

- `nSkill`: Skill constant to check:
  - `SKILL_COMPUTER_USE` (0) - Computer Use skill
  - `SKILL_DEMOLITIONS` (1) - Demolitions skill
  - `SKILL_STEALTH` (2) - Stealth skill
  - `SKILL_AWARENESS` (3) - Awareness skill
  - `SKILL_PERSUADE` (4) - Persuade skill
  - `SKILL_REPAIR` (5) - Repair skill
  - `SKILL_SECURITY` (6) - Security skill
  - `SKILL_TREAT_INJURY` (7) - Treat Injury skill
- `oTarget`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Skill rank (0 or higher) if skill is valid and creature has the skill
- `-1` if the creature doesn't have the skill or skill is invalid
- `0` if skill is untrained

#### Usage Examples

```nss
// Check PC's Persuade skill
int nPersuade = GetSkillRank(SKILL_PERSUADE, GetFirstPC());
if (nPersuade >= 10) {
    // High persuasion - unlock special dialogue option
}
```

```nss
// Check Repair skill
int nRepair = GetSkillRank(SKILL_REPAIR, OBJECT_SELF);
if (nRepair >= 5) {
    // Can repair items
}
```

**Pattern: Skill Check for Dialogue**

```nss
// Use skill rank to determine dialogue options
int nPersuade = GetSkillRank(SKILL_PERSUADE, GetFirstPC());
int nAwareness = GetSkillRank(SKILL_AWARENESS, GetFirstPC());

if (nPersuade >= 15) {
    // High persuade option
} else if (nAwareness >= 10) {
    // Alternative option based on awareness
}
```

#### Notes

- Skill rank includes all bonuses (ability modifiers, equipment, feats)
- Returns `-1` for skills the creature cannot use (class restrictions)
- Use skill ranks for skill checks and conditional dialogue

---

## Feat Functions

### GetHasFeat

**Routine:** 336

#### Function Signature

```nss
int GetHasFeat(int nFeat, object oCreature = OBJECT_SELF);
```

#### Description

Checks if a creature has a specific feat. Feats represent special abilities, proficiencies, and combat techniques.

#### Parameters

- `nFeat`: Feat constant to check (see Common Feats below)
- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- `TRUE` (1) if the creature has the feat
- `FALSE` (0) if the creature doesn't have the feat

#### Usage Examples

```nss
// Check if creature has lightsaber proficiency
if (GetHasFeat(FEAT_WEAPON_PROF_LIGHTSABER, GetFirstPC())) {
    // Can use lightsabers
}
```

```nss
// Check combat feat
if (GetHasFeat(FEAT_FLURRY, OBJECT_SELF)) {
    // Has Flurry feat - can use special attack
}
```

**Pattern: Conditional Based on Feats**

```nss
// Check multiple feats for class detection
if (GetHasFeat(FEAT_WEAPON_PROF_LIGHTSABER, GetFirstPC())) {
    // Jedi character
} else if (GetHasFeat(FEAT_ARMOUR_PROF_HEAVY, GetFirstPC())) {
    // Soldier/combat character
}
```

#### Common Feats (Examples)

**Combat Feats:**

- `FEAT_FLURRY` - Flurry attack mode
- `FEAT_CRITICAL_STRIKE` - Critical Strike attack mode
- `FEAT_POWER_ATTACK` - Power Attack attack mode
- `FEAT_AMBIDEXTERITY` - Dual-wield proficiency

**Armor Feats:**

- `FEAT_ARMOUR_PROF_LIGHT` - Light armor proficiency
- `FEAT_ARMOUR_PROF_MEDIUM` - Medium armor proficiency
- `FEAT_ARMOUR_PROF_HEAVY` - Heavy armor proficiency

**Jedi Feats:**

- `FEAT_WEAPON_PROF_LIGHTSABER` - Lightsaber proficiency
- `FEAT_ADVANCED_JEDI_DEFENSE` - Advanced Jedi defense
- `FEAT_MASTER_JEDI_DEFENSE` - Master Jedi defense

**Note:** Feat constants vary between K1 and TSL. Consult `nwscript.nss` for the full list of available feats in your game.

---

## Level and Experience Functions

### GetHitDice

**Routine:** 331

#### Function Signature

```nss
int GetHitDice(object oCreature = OBJECT_SELF);
```

#### Description

Gets the total character level (hit dice) of a creature. This is the sum of all class levels. In KotOR, this effectively represents the character's overall level.

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Total character level (sum of all class levels)
- `0` if creature is invalid

#### Usage Examples

```nss
// Check PC's level
int nLevel = GetHitDice(GetFirstPC());
if (nLevel >= 15) {
    // High level character
}
```

**Pattern: Level-Based Conditional**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/c_pc_level.nss
int nCompareAmount = GetScriptParameter(1);
int nLevel = GetHitDice(GetFirstPC());

if (nLevel >= nCompareAmount) {
    return TRUE;
} else {
    return FALSE;
}
```

**Pattern: Level-Based XP Rewards**

```nss
// Award XP based on level
int nLevel = GetHitDice(GetFirstPC());
int nXPAmount = nLevel * 15; // 15 XP per level
GiveXPToCreature(GetFirstPC(), nXPAmount);
```

#### Notes

- `GetHitDice()` returns the total level across all classes
- For multi-class characters, this is the sum of all class levels
- Use this for general level checks, not class-specific checks

---

### GiveXPToCreature

**Routine:** 332

#### Function Signature

```nss
void GiveXPToCreature(object oCreature, int nXPAward);
```

#### Description

Awards experience points (XP) to a creature. The creature may level up if they have enough XP.

#### Parameters

- `oCreature`: Creature to award XP to
- `nXPAward`: Amount of XP to award (must be positive)

#### Usage Examples

```nss
// Award fixed XP amount
GiveXPToCreature(GetFirstPC(), 500);
```

**Pattern: Level-Based XP Rewards**

```nss
// Award XP based on level
int nLevel = GetHitDice(GetFirstPC());
int nXPAmount = nLevel * 15;
GiveXPToCreature(GetFirstPC(), nXPAmount);
```

**Pattern: Quest Completion Reward**

```nss
// Award XP for completing a quest
object oPC = GetFirstPC();
int nBaseXP = 1000;
int nBonusXP = GetSkillRank(SKILL_PERSUADE, oPC) * 10; // Bonus based on skill
GiveXPToCreature(oPC, nBaseXP + nBonusXP);
```

#### Notes

- XP is automatically added to the creature's total
- Leveling up happens automatically if the creature has enough XP
- Cannot remove XP (use `SetXP` if available)

---

## Skill Constants

### Standard Skills (K1 & TSL)

- `SKILL_COMPUTER_USE` (0) - Computer Use skill
- `SKILL_DEMOLITIONS` (1) - Demolitions skill
- `SKILL_STEALTH` (2) - Stealth skill
- `SKILL_AWARENESS` (3) - Awareness skill
- `SKILL_PERSUADE` (4) - Persuade skill
- `SKILL_REPAIR` (5) - Repair skill
- `SKILL_SECURITY` (6) - Security skill
- `SKILL_TREAT_INJURY` (7) - Treat Injury skill
- `SKILL_MAX_SKILLS` (8) - Maximum number of skills (not a valid skill ID)

### Subskills

- `SUBSKILL_FLAGTRAP` (100) - Flag trap subskill
- `SUBSKILL_RECOVERTRAP` (101) - Recover trap subskill
- `SUBSKILL_EXAMINETRAP` (102) - Examine trap subskill

---

## Common Patterns and Best Practices

### Pattern: Skill Check for Dialogue Options

```nss
// Use multiple skill checks for dialogue branching
int nPersuade = GetSkillRank(SKILL_PERSUADE, GetFirstPC());
int nIntimidate = GetSkillRank(SKILL_AWARENESS, GetFirstPC()); // Awareness used for Intimidate in KotOR

if (nPersuade >= 15) {
    // High persuade option
} else if (nIntimidate >= 10) {
    // Intimidate option
} else {
    // Default option
}
```

### Pattern: Feat-Based Equipment Restrictions

```nss
// Check feats before allowing equipment
object oItem = CreateItemOnObject("heavy_armor", GetFirstPC());
if (GetHasFeat(FEAT_ARMOUR_PROF_HEAVY, GetFirstPC())) {
    ActionEquipItem(oItem, INVENTORY_SLOT_BODY);
} else {
    // Character cannot equip heavy armor
    DestroyObject(oItem);
}
```

### Pattern: Level-Based Scaling

```nss
// Scale rewards or difficulty based on level
int nLevel = GetHitDice(GetFirstPC());
int nReward = 100 * nLevel; // Reward scales with level
GiveXPToCreature(GetFirstPC(), nReward);
```

### Pattern: Skill-Based Success Chance

```nss
// Determine success based on skill rank
int nRepair = GetSkillRank(SKILL_REPAIR, GetFirstPC());
int nDC = 15; // Difficulty class

if (nRepair >= nDC) {
    // Automatic success
    // Repair item
} else if (nRepair >= nDC - 5) {
    // Partial success
    // Partial repair
} else {
    // Failure
    // Cannot repair
}
```

### Best Practices

1. **Check Skills Before Actions**: Verify skill ranks before attempting skill-based actions
2. **Use Feats for Class Detection**: Check feats to determine character class/build
3. **Level-Based Scaling**: Use `GetHitDice()` to scale rewards or difficulty
4. **Combine Skill Checks**: Use multiple skills for complex conditional logic
5. **Validate Creatures**: Always ensure creatures are valid before checking skills/feats
6. **Use Constants**: Always use skill/feat constants instead of magic numbers

---

## Related Functions

- `GetAbilityModifier()` - Get ability score modifier (affects skill ranks)
- `GetLevelByClass()` - Get level in a specific class (if available)
- `SetXP()` - Set experience points directly (if available)

---

## Additional Notes

### Skill Ranks vs. Ability Modifiers

Skill ranks are the base ranks, but the effective skill rank includes:

- Base skill ranks
- Ability modifier (Intelligence, Dexterity, etc. depending on skill)
- Equipment bonuses
- Feat bonuses
- Temporary bonuses from effects

`GetSkillRank()` returns the total effective rank, including all bonuses.

### Feat Acquisition

Feats are typically:

- Acquired at level-up
- Granted by class or race
- Granted through special events or scripts (if supported)

In most cases, scripts cannot grant feats directly - they are managed by the character advancement system.

### Level and Experience

Character levels are determined by total XP. The XP required for each level is defined in `exptable.2da`. When a character gains enough XP, they automatically level up.

### Multi-Class Characters

For multi-class characters:

- `GetHitDice()` returns the total level (sum of all class levels)
- `GetLevelByClass()` (if available) returns the level in a specific class
- Skills and feats can vary by class

---

## Skill and Feat Usage in Dialogues

Skills and feats are commonly used in dialogue conditional scripts:

```nss
// Dialogue conditional script example
int StartingConditional() {
    object oPC = GetFirstPC();
    
    // Check for skill requirement
    if (GetSkillRank(SKILL_PERSUADE, oPC) >= 15) {
        return TRUE; // Show this dialogue option
    }
    
    // Check for feat requirement
    if (GetHasFeat(FEAT_WEAPON_PROF_LIGHTSABER, oPC)) {
        return TRUE; // Show Jedi-specific option
    }
    
    return FALSE; // Don't show this option
}
```

This allows dialogue trees to adapt based on the player's character build and skills.
