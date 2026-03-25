# Abilities and Stats

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript ability and stat functions. These functions allow scripts to check ability scores, modifiers, hit points, and other character statistics.

---

## Abilities and Stats Fundamentals

### Understanding Ability Scores

KotOR uses the D&D d20 system with six ability scores:

- **Strength (STR)** - Physical power, melee damage
- **Dexterity (DEX)** - Agility, ranged accuracy, defense
- **Constitution (CON)** - Health, hit points
- **Intelligence (INT)** - Learning, technical skills
- **Wisdom (WIS)** - Perception, Force sensitivity
- **Charisma (CHA)** - Personality, persuasion

Ability scores typically range from 3 to 18 (though can be modified by effects). The modifier is calculated as `(Score - 10) / 2`, rounded down.

### Understanding Hit Points

Hit Points (HP) represent a creature's health:

- **Current HP** - Current health value
- **Max HP** - Maximum possible health
- When Current HP reaches 0, the creature is unconscious or dead

---

## Ability Score Functions

### GetAbilityScore

**Routine:** 288

#### Function Signature

```nss
int GetAbilityScore(int nAbility, object oCreature = OBJECT_SELF);
```

#### Description

Gets the base ability score of a creature. Returns the actual ability score value (typically 3-18+).

#### Parameters

- `nAbility`: Ability constant:
  - `ABILITY_STRENGTH` (0) - Strength
  - `ABILITY_DEXTERITY` (1) - Dexterity
  - `ABILITY_CONSTITUTION` (2) - Constitution
  - `ABILITY_INTELLIGENCE` (3) - Intelligence
  - `ABILITY_WISDOM` (4) - Wisdom
  - `ABILITY_CHARISMA` (5) - Charisma
- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Ability score value (typically 3-18, can be higher with effects)
- Default score if ability is invalid

#### Usage Examples

```nss
// Get PC's Strength
int nSTR = GetAbilityScore(ABILITY_STRENGTH, GetFirstPC());
if (nSTR >= 16) {
    // High strength character
}
```

```nss
// Check multiple abilities
int nINT = GetAbilityScore(ABILITY_INTELLIGENCE, GetFirstPC());
int nWIS = GetAbilityScore(ABILITY_WISDOM, GetFirstPC());

if (nINT >= 14 || nWIS >= 14) {
    // High mental stats
}
```

**Pattern: Ability-Based Dialogue**

```nss
// Use ability scores for dialogue options
int nCHA = GetAbilityScore(ABILITY_CHARISMA, GetFirstPC());
if (nCHA >= 15) {
    // High charisma option available
}
```

#### Notes

- Returns base ability score, not modified by temporary effects
- Ability scores can be modified by permanent effects (items, level-ups)
- Typical range is 3-18, but can be higher with effects

---

### GetAbilityModifier

**Routine:** 331

#### Function Signature

```nss
int GetAbilityModifier(int nAbility, object oCreature = OBJECT_SELF);
```

#### Description

Gets the ability modifier for a creature. The modifier is calculated as `(Ability Score - 10) / 2`, rounded down. Modifiers affect skills, combat, and other derived statistics.

#### Parameters

- `nAbility`: Ability constant (see `GetAbilityScore`)
- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Ability modifier (e.g., -4 to +4 for scores 3-18)
- Negative values for scores below 10, positive for scores above 10

#### Modifier Calculation

| Ability Score | Modifier |
|--------------|----------|
| 1 | -5 |
| 2-3 | -4 |
| 4-5 | -3 |
| 6-7 | -2 |
| 8-9 | -1 |
| 10-11 | 0 |
| 12-13 | +1 |
| 14-15 | +2 |
| 16-17 | +3 |
| 18-19 | +4 |
| 20+ | +5+ |

#### Usage Examples

```nss
// Get Strength modifier (affects melee damage)
int nSTRMod = GetAbilityModifier(ABILITY_STRENGTH, GetFirstPC());
```

```nss
// Calculate expected damage with modifier
int nBaseDamage = 10;
int nSTRMod = GetAbilityModifier(ABILITY_STRENGTH, GetFirstPC());
int nTotalDamage = nBaseDamage + nSTRMod;
```

**Pattern: Skill Check with Modifier**

```nss
// Calculate effective skill rank (base + modifier)
int nBaseSkill = GetSkillRank(SKILL_REPAIR, GetFirstPC());
int nINTMod = GetAbilityModifier(ABILITY_INTELLIGENCE, GetFirstPC());
int nEffectiveSkill = nBaseSkill + nINTMod;
```

#### Notes

- Modifier affects skills (Intelligence for Repair, Dexterity for Stealth, etc.)
- Modifier affects combat (Strength for melee, Dexterity for ranged)
- Formula: `(Score - 10) / 2`, rounded down

---

## Hit Point Functions

### GetCurrentHitPoints

**Routine:** 49

#### Function Signature

```nss
int GetCurrentHitPoints(object oObject = OBJECT_SELF);
```

#### Description

Gets the current hit points (health) of a creature or object. When HP reaches 0, the creature is unconscious or dead.

#### Parameters

- `oObject`: Creature or object to check (default: `OBJECT_SELF`)

#### Returns

- Current hit points (0 or higher)
- `0` if object is invalid or dead

#### Usage Examples

```nss
// Check PC's current HP
int nHP = GetCurrentHitPoints(GetFirstPC());
if (nHP < 50) {
    // Low on health - heal or warn player
}
```

```nss
// Check if creature is alive
int nHP = GetCurrentHitPoints(OBJECT_SELF);
if (nHP <= 0) {
    // Creature is dead/unconscious
}
```

**Pattern: Health Percentage Check**

```nss
// Check health as percentage
int nCurrentHP = GetCurrentHitPoints(GetFirstPC());
int nMaxHP = GetMaxHitPoints(GetFirstPC());
float fPercent = (IntToFloat(nCurrentHP) / IntToFloat(nMaxHP)) * 100.0;

if (fPercent < 25.0) {
    // Critical health - less than 25%
}
```

**Pattern: Combat Health Monitoring**

```nss
// Check health during combat
int nHP = GetCurrentHitPoints(OBJECT_SELF);
int nMaxHP = GetMaxHitPoints(OBJECT_SELF);

if (nHP < (nMaxHP / 2)) {
    // Below 50% health - use defensive tactics
}
```

#### Notes

- Returns 0 for dead creatures
- Works on creatures, doors, and placeables
- Use with `GetMaxHitPoints()` to calculate health percentage

---

### GetMaxHitPoints

**Routine:** 50

#### Function Signature

```nss
int GetMaxHitPoints(object oObject = OBJECT_SELF);
```

#### Description

Gets the maximum hit points (health capacity) of a creature or object. This is the highest HP value the creature can have.

#### Parameters

- `oObject`: Creature or object to check (default: `OBJECT_SELF`)

#### Returns

- Maximum hit points
- `0` if object is invalid

#### Usage Examples

```nss
// Get max HP
int nMaxHP = GetMaxHitPoints(GetFirstPC());
```

**Pattern: Full Heal**

```nss
// Heal to full HP
object oTarget = GetFirstPC();
int nCurrentHP = GetCurrentHitPoints(oTarget);
int nMaxHP = GetMaxHitPoints(oTarget);
int nHealAmount = nMaxHP - nCurrentHP;

if (nHealAmount > 0) {
    effect eHeal = EffectHeal(nHealAmount);
    ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oTarget);
}
```

**Pattern: Health Percentage**

```nss
// Calculate health percentage
int nCurrent = GetCurrentHitPoints(GetFirstPC());
int nMax = GetMaxHitPoints(GetFirstPC());
float fPercent = (IntToFloat(nCurrent) / IntToFloat(nMax)) * 100.0;

if (fPercent >= 75.0) {
    // Healthy
} else if (fPercent >= 50.0) {
    // Wounded
} else if (fPercent >= 25.0) {
    // Injured
} else {
    // Critical
}
```

#### Notes

- Max HP is determined by Constitution, class, and level
- Can be modified by temporary or permanent effects
- Use with `GetCurrentHitPoints()` for health calculations

---

## Force Points Functions (Jedi/KotOR Specific)

### GetCurrentForcePoints

**Routine:** 55

#### Function Signature

```nss
int GetCurrentForcePoints(object oObject = OBJECT_SELF);
```

#### Description

Gets the current Force Points (FP) of a creature. Force Points are used to cast Force powers.

#### Parameters

- `oObject`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Current Force Points (0 or higher)
- `0` if creature is invalid or has no Force Points

#### Usage Examples

```nss
// Check Force Points
int nFP = GetCurrentForcePoints(GetFirstPC());
if (nFP < 10) {
    // Low on Force Points
}
```

---

### GetMaxForcePoints

**Routine:** 56

#### Function Signature

```nss
int GetMaxForcePoints(object oObject = OBJECT_SELF);
```

#### Description

Gets the maximum Force Points (FP) of a creature. Max FP is determined by Wisdom modifier and class levels.

#### Parameters

- `oObject`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Maximum Force Points
- `0` if creature is invalid or has no Force abilities

#### Usage Examples

```nss
// Check max Force Points
int nMaxFP = GetMaxForcePoints(GetFirstPC());
```

---

## Ability Constants

### Standard Abilities

- `ABILITY_STRENGTH` (0) - Physical power
- `ABILITY_DEXTERITY` (1) - Agility and accuracy
- `ABILITY_CONSTITUTION` (2) - Health and endurance
- `ABILITY_INTELLIGENCE` (3) - Learning and technical ability
- `ABILITY_WISDOM` (4) - Perception and Force sensitivity
- `ABILITY_CHARISMA` (5) - Personality and social ability

---

## Common Patterns and Best Practices

### Pattern: Ability Check for Dialogue

```nss
// Use ability scores to unlock dialogue options
int nINT = GetAbilityScore(ABILITY_INTELLIGENCE, GetFirstPC());
int nWIS = GetAbilityScore(ABILITY_WISDOM, GetFirstPC());

if (nINT >= 14 || nWIS >= 14) {
    // High mental stats - show intelligent dialogue option
}
```

### Pattern: Health-Based Behavior

```nss
// Change behavior based on health percentage
int nCurrent = GetCurrentHitPoints(OBJECT_SELF);
int nMax = GetMaxHitPoints(OBJECT_SELF);
float fPercent = (IntToFloat(nCurrent) / IntToFloat(nMax)) * 100.0;

if (fPercent < 25.0) {
    // Critical health - flee or use emergency ability
} else if (fPercent < 50.0) {
    // Low health - use defensive stance
}
```

### Pattern: Heal to Full

```nss
// Heal creature to maximum HP
object oTarget = GetFirstPC();
int nCurrent = GetCurrentHitPoints(oTarget);
int nMax = GetMaxHitPoints(oTarget);
int nHeal = nMax - nCurrent;

if (nHeal > 0) {
    effect eHeal = EffectHeal(nHeal);
    ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oTarget);
}
```

### Pattern: Calculate Derived Stats

```nss
// Calculate effective defense (base + modifier)
int nBaseDefense = 10;
int nDEXMod = GetAbilityModifier(ABILITY_DEXTERITY, GetFirstPC());
int nTotalDefense = nBaseDefense + nDEXMod;
```

### Best Practices

1. **Check HP Before Actions**: Verify HP > 0 before performing actions on creatures
2. **Use Modifiers for Calculations**: Use `GetAbilityModifier()` for derived statistics
3. **Calculate Percentages**: Compare current to max HP for health percentage checks
4. **Validate Objects**: Always ensure objects are valid before checking stats
5. **Use Constants**: Always use ability constants instead of magic numbers
6. **Consider Temporary Effects**: Ability scores may be modified by effects

---

## Related Functions

- `GetSkillRank()` - Skill ranks (affected by ability modifiers) - see [Skills & Feats](NSS-Shared-Functions-Skills-and-Feats)
- `GetHitDice()` - Character level (affects max HP) - see [Skills & Feats](NSS-Shared-Functions-Skills-and-Feats)
- `EffectHeal()` - Restore HP - see [Effects System](NSS-Shared-Functions-Effects-System)
- `EffectDamage()` - Reduce HP - see [Effects System](NSS-Shared-Functions-Effects-System)

---

## Additional Notes

### Ability Score Modifiers

Ability modifiers are automatically calculated and affect:

- **Skills**: Intelligence affects Repair, Wisdom affects Awareness, etc.
- **Combat**: Strength affects melee damage, Dexterity affects ranged accuracy
- **Defense**: Dexterity modifier adds to defense (AC)
- **Hit Points**: Constitution modifier affects HP per level

### Hit Point Calculation

Max HP is calculated from:

- Base HP from class and level
- Constitution modifier per level
- Temporary or permanent effects

Current HP can be:

- Reduced by damage (combat, effects)
- Restored by healing (effects, items)
- Cannot exceed Max HP

### Force Points (KotOR Specific)

Force Points are used for Force powers:

- Max FP is determined by Wisdom modifier and Jedi class levels
- FP regenerate over time (implementation dependent)
- Non-Jedi characters typically have 0 FP

### Temporary vs. Permanent Stats

- **Permanent**: Base ability scores, level, class
- **Temporary**: Effects, equipment bonuses, temporary modifiers

`GetAbilityScore()` returns the base score. The effective score includes all modifiers but is not directly queryable through standard NWScript functions.
