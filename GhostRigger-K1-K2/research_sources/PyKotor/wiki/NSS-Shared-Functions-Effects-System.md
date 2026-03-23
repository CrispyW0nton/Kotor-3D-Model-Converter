# Effects System

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for the NWScript effects system. Effects are modifiers that can be applied to objects (typically creatures) to change their properties, deal damage, heal, apply status conditions, and more.

---

## Effects System Fundamentals

### Understanding Effects

Effects are temporary or permanent modifications to objects. They are **created** using effect functions (like `EffectDamage()`, `EffectHeal()`), but must be **applied** using `ApplyEffectToObject()` before they take effect.

### Effect Lifecycle

1. **Create**: Use an effect function to create an effect (e.g., `effect eDamage = EffectDamage(10, DAMAGE_TYPE_FIRE);`)
2. **Apply**: Use `ApplyEffectToObject()` to apply the effect with a duration type
3. **Active**: The effect modifies the object while active
4. **Expire**: Temporary effects expire after their duration; permanent effects persist until removed

### Key Concepts

- **Effect Creation**: Effects are objects that can be stored in variables and reused
- **Duration Types**: Effects have three duration types (Instant, Temporary, Permanent)
- **Instant Effects**: Applied immediately and removed (e.g., damage, healing)
- **Temporary Effects**: Active for a specified duration (e.g., buffs, debuffs)
- **Permanent Effects**: Last until explicitly removed (e.g., ability increases from items)
- **Effect Stacking**: Multiple effects of the same type can stack (implementation dependent)

---

## Applying Effects

### ApplyEffectToObject

**Routine:** 220

#### Function Signature

```nss
void ApplyEffectToObject(int nDurationType, effect eEffect, object oTarget, float fDuration = 0.0);
```

#### Description

Applies an effect to a target object with the specified duration type. This is the **primary way** to make effects take effect. Effects created with effect functions (e.g., `EffectDamage()`) do nothing until applied.

#### Parameters

- `nDurationType`: Duration type constant:
  - `DURATION_TYPE_INSTANT` (0) - Effect applies immediately and is removed
  - `DURATION_TYPE_TEMPORARY` (1) - Effect lasts for `fDuration` seconds
  - `DURATION_TYPE_PERMANENT` (2) - Effect persists until explicitly removed
- `eEffect`: The effect to apply (created with effect functions)
- `oTarget`: Target object to apply the effect to
- `fDuration`: Duration in seconds (required for `DURATION_TYPE_TEMPORARY`, ignored for others)

#### Duration Types Explained

**DURATION_TYPE_INSTANT (0)**

- Effect applies immediately and is removed
- Used for: Damage, healing, resurrection
- `fDuration` parameter is ignored

**DURATION_TYPE_TEMPORARY (1)**

- Effect lasts for `fDuration` seconds
- Used for: Temporary buffs/debuffs, status effects with duration
- Effect is automatically removed when duration expires
- `fDuration` must be specified (> 0.0)

**DURATION_TYPE_PERMANENT (2)**

- Effect persists until explicitly removed with `RemoveEffect()` or `ClearAllEffects()`
- Used for: Permanent ability increases, item-based effects
- `fDuration` parameter is ignored

#### Usage Examples

```nss
// Instant damage effect
effect eDamage = EffectDamage(25, DAMAGE_TYPE_FIRE);
ApplyEffectToObject(DURATION_TYPE_INSTANT, eDamage, oTarget, 0.0);
```

```nss
// Temporary speed increase (30 seconds)
effect eSpeed = EffectMovementSpeedIncrease(50); // +50% speed
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, eSpeed, oTarget, 30.0);
```

```nss
// Permanent ability increase
effect eStr = EffectAbilityIncrease(ABILITY_STRENGTH, 2);
ApplyEffectToObject(DURATION_TYPE_PERMANENT, eStr, oTarget, 0.0);
```

**Pattern: Conditional Duration**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Data/Scripts/a_speed_set.nss
effect eEffect;
if(nChange < 0)
    eEffect = EffectMovementSpeedDecrease(-nChange);
else 
    eEffect = EffectMovementSpeedIncrease(nChange);

if(nDuration != 0) 
    ApplyEffectToObject(DURATION_TYPE_TEMPORARY, eEffect, oObject, fDuration);
else 
    ApplyEffectToObject(DURATION_TYPE_PERMANENT, eEffect, oObject, 0.0);
```

#### Implementation Reference

- [`vendor/KotOR.js/src/nwscript/NWScriptDefK1.ts:2735-2759`](https://github.com/th3w1zard1/KotOR.js/blob/master/src/nwscript/NWScriptDefK1.ts#L2735-L2759)
- [`vendor/reone/src/libs/game/object.cpp:257-271`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/object.cpp#L257-L271)

---

## Damage and Healing Effects

### EffectDamage

**Routine:** 79

#### Function Signature

```nss
effect EffectDamage(int nDamageAmount, int nDamageType = DAMAGE_TYPE_UNIVERSAL, int nDamagePower = DAMAGE_POWER_NORMAL);
```

#### Description

Creates a damage effect that deals damage to a target when applied. The damage is applied immediately when used with `DURATION_TYPE_INSTANT`.

**⚠️ IMPORTANT:** Damage effects must be applied as `DURATION_TYPE_INSTANT` to deal damage. Temporary/permanent damage effects don't work as expected.

#### Parameters

- `nDamageAmount`: Amount of damage to deal (minimum 1, maximum 10000)
- `nDamageType`: Damage type constant (default: `DAMAGE_TYPE_UNIVERSAL`):
  - `DAMAGE_TYPE_BLUDGEONING` (1) - Physical bludgeoning damage
  - `DAMAGE_TYPE_PIERCING` (2) - Physical piercing damage
  - `DAMAGE_TYPE_SLASHING` (4) - Physical slashing damage
  - `DAMAGE_TYPE_PHYSICAL` (7) - All physical damage types
  - `DAMAGE_TYPE_UNIVERSAL` (8) - Universal damage (bypasses most resistances)
  - `DAMAGE_TYPE_ACID` (16) - Acid damage
  - `DAMAGE_TYPE_COLD` (32) - Cold damage
  - `DAMAGE_TYPE_LIGHTSIDE` (64) - Lightside force damage
  - `DAMAGE_TYPE_ELECTRICAL` (128) - Electrical damage
  - `DAMAGE_TYPE_FIRE` (256) - Fire damage
  - `DAMAGE_TYPE_DARKSIDE` (512) - Darkside force damage
  - `DAMAGE_TYPE_SONIC` (1024) - Sonic damage
  - `DAMAGE_TYPE_ION` (2048) - Ion damage
  - `DAMAGE_TYPE_BLASTER` (4096) - Blaster damage
- `nDamagePower`: Damage power level (default: `DAMAGE_POWER_NORMAL`):
  - `DAMAGE_POWER_NORMAL` (0)
  - `DAMAGE_POWER_PLUS_ONE` (1)
  - `DAMAGE_POWER_PLUS_TWO` (2)
  - `DAMAGE_POWER_PLUS_THREE` (3)
  - `DAMAGE_POWER_PLUS_FOUR` (4)
  - `DAMAGE_POWER_PLUS_FIVE` (5)

#### Usage Examples

```nss
// Basic fire damage
effect eDamage = EffectDamage(25, DAMAGE_TYPE_FIRE);
ApplyEffectToObject(DURATION_TYPE_INSTANT, eDamage, oTarget, 0.0);
```

```nss
// Physical slashing damage with save
if (!ReflexSave(oTarget, nDC, SAVE_TYPE_REFLEX, oCaster)) {
    ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectDamage(50, DAMAGE_TYPE_SLASHING), oTarget, 0.0);
} else {
    ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectDamage(25, DAMAGE_TYPE_SLASHING), oTarget, 0.0); // Half on save
}
```

**Pattern: Area Damage with Save**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/411DXN_Dxun_Sith_Tomb/k_def_user_heal.nss
object oShapeObject = GetFirstObjectInShape(4, 4.0, location1, 0, 65, [0.0,0.0,0.0]);
while (GetIsObjectValid(oShapeObject) && (int4 > 0)) {
    if (oShapeObject != OBJECT_SELF) {
        int nDC = 15;
        nDC = (nDC - GetAbilityModifier(ABILITY_DEXTERITY, oShapeObject));
        if (!ReflexSave(oShapeObject, nDC, 0, OBJECT_SELF)) {
            ApplyEffectToObject(DURATION_TYPE_INSTANT, 
                EffectDamage(50, DAMAGE_TYPE_SLASHING, 0), oShapeObject, 0.0);
        } else {
            int nHalfDamage = (GetHasFeat(125, oShapeObject)) ? 0 : (50 / 2);
            ApplyEffectToObject(DURATION_TYPE_INSTANT, 
                EffectDamage(nHalfDamage, DAMAGE_TYPE_SLASHING, 0), oShapeObject, 0.0);
        }
    }
    oShapeObject = GetNextObjectInShape(4, 4.0, location1, 0, 65, [0.0,0.0,0.0]);
}
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/script/routine/impl/effect.cpp:149-162`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/script/routine/impl/effect.cpp#L149-L162)
- [`vendor/KotOR.js/src/effects/EffectDamage.ts`](https://github.com/th3w1zard1/KotOR.js/blob/master/src/effects/EffectDamage.ts)

---

### EffectHeal

**Routine:** 78

#### Function Signature

```nss
effect EffectHeal(int nDamageToHeal);
```

#### Description

Creates a healing effect that restores hit points to a target. Must be applied as `DURATION_TYPE_INSTANT` to take effect.

**Returns:** `EFFECT_TYPE_INVALIDEFFECT` if `nDamageToHeal < 0`.

#### Parameters

- `nDamageToHeal`: Amount of hit points to restore (cannot be negative)

#### Usage Examples

```nss
// Simple healing
effect eHeal = EffectHeal(50);
ApplyEffectToObject(DURATION_TYPE_INSTANT, eHeal, oTarget, 0.0);
```

```nss
// Full healing (heal to max HP)
int nHealAmount = GetMaxHitPoints(OBJECT_SELF) - GetCurrentHitPoints(OBJECT_SELF);
if (nHealAmount > 0) {
    DelayCommand(1.0, ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectHeal(nHealAmount), OBJECT_SELF, 0.0));
}
```

**Pattern: Full Healing**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/403DXN_Dxun_Mandalorian_Ruins/k_circle_damage.nss
DelayCommand(1.0, ApplyEffectToObject(DURATION_TYPE_INSTANT, 
    EffectHeal((GetMaxHitPoints(OBJECT_SELF) - GetCurrentHitPoints(OBJECT_SELF))), 
    OBJECT_SELF, 0.0));
```

#### Implementation Reference

- [`vendor/reone/src/libs/game/script/routine/impl/effect.cpp:138-147`](https://github.com/th3w1zard1/reone/blob/master/src/libs/game/script/routine/impl/effect.cpp#L138-L147)

---

## Status Condition Effects

### EffectKnockdown

**Routine:** 134

#### Function Signature

```nss
effect EffectKnockdown();
```

#### Description

Creates a knockdown effect that knocks the target prone. Typically used with `DURATION_TYPE_TEMPORARY` for timed knockdowns.

#### Usage Examples

```nss
// Temporary knockdown (5 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, EffectKnockdown(), oTarget, 5.0);
```

```nss
// Knockdown after failed save
if (!FortitudeSave(oTarget, nDC, SAVE_TYPE_FORTITUDE, oCaster)) {
    ApplyEffectToObject(DURATION_TYPE_TEMPORARY, EffectKnockdown(), oTarget, 3.0);
}
```

---

### EffectParalyze

**Routine:** 148

#### Function Signature

```nss
effect EffectParalyze();
```

#### Description

Creates a paralyze effect that immobilizes the target. Target cannot move or take actions.

#### Usage Examples

```nss
// Temporary paralyze (10 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, EffectParalyze(), oTarget, 10.0);
```

```nss
// Permanent paralyze (until removed)
ApplyEffectToObject(DURATION_TYPE_PERMANENT, EffectParalyze(), oTarget, 0.0);
```

---

### EffectDeath

**Routine:** 133

#### Function Signature

```nss
effect EffectDeath(int nSpectacularDeath = 0, int nDisplayFeedback = 1);
```

#### Description

Creates a death effect that kills the target. Must be applied as `DURATION_TYPE_INSTANT`.

#### Parameters

- `nSpectacularDeath`: If non-zero, uses spectacular death animation
- `nDisplayFeedback`: If non-zero, displays death feedback message

#### Usage Examples

```nss
// Standard death
ApplyEffectToObject(DURATION_TYPE_INSTANT, EffectDeath(0, 1), oTarget, 0.0);
```

```nss
// Spectacular death
ApplyEffectToObject(DURATION_TYPE_INSTANT, EffectDeath(1, 1), oTarget, 0.0);
```

---

### EffectResurrection

**Routine:** 82

#### Function Signature

```nss
effect EffectResurrection(int nHitPointPercent = 100);
```

#### Description

Creates a resurrection effect that revives a dead creature. Must be applied as `DURATION_TYPE_INSTANT`.

#### Parameters

- `nHitPointPercent`: Percentage of maximum hit points to restore (0-100, default 100)

#### Usage Examples

```nss
// Full resurrection (100% HP)
ApplyEffectToObject(DURATION_TYPE_INSTANT, EffectResurrection(100), oTarget, 0.0);
```

```nss
// Resurrection at 50% HP
ApplyEffectToObject(DURATION_TYPE_INSTANT, EffectResurrection(50), oTarget, 0.0);
```

---

## Ability and Stat Effects

### EffectAbilityIncrease

**Routine:** 80

#### Function Signature

```nss
effect EffectAbilityIncrease(int nAbilityToIncrease, int nModifyBy);
```

#### Description

Creates an effect that increases an ability score. Commonly used with `DURATION_TYPE_PERMANENT` for item-based stat boosts.

#### Parameters

- `nAbilityToIncrease`: Ability constant:
  - `ABILITY_STRENGTH` (0)
  - `ABILITY_DEXTERITY` (1)
  - `ABILITY_CONSTITUTION` (2)
  - `ABILITY_INTELLIGENCE` (3)
  - `ABILITY_WISDOM` (4)
  - `ABILITY_CHARISMA` (5)
- `nModifyBy`: Amount to increase the ability by

#### Usage Examples

```nss
// Permanent +2 Strength (item effect)
ApplyEffectToObject(DURATION_TYPE_PERMANENT, 
    EffectAbilityIncrease(ABILITY_STRENGTH, 2), oTarget, 0.0);
```

```nss
// Temporary +4 Dexterity (spell/buff, 60 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, 
    EffectAbilityIncrease(ABILITY_DEXTERITY, 4), oTarget, 60.0);
```

---

### EffectAbilityDecrease

**Routine:** 446

#### Function Signature

```nss
effect EffectAbilityDecrease(int nAbility, int nModifyBy);
```

#### Description

Creates an effect that decreases an ability score. Typically used with `DURATION_TYPE_TEMPORARY` for debuffs.

#### Parameters

- `nAbility`: Ability constant (same as EffectAbilityIncrease)
- `nModifyBy`: Amount to decrease the ability by

#### Usage Examples

```nss
// Temporary -2 Strength debuff (30 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, 
    EffectAbilityDecrease(ABILITY_STRENGTH, 2), oTarget, 30.0);
```

---

## Movement Speed Effects

### EffectMovementSpeedIncrease

**Routine:** 165

#### Function Signature

```nss
effect EffectMovementSpeedIncrease(int nNewSpeedPercent);
```

#### Description

Creates an effect that increases movement speed. `nNewSpeedPercent` is the new speed as a percentage of base speed (e.g., 150 = 150% speed = 1.5x).

**Note:** There is typically a cap around 200% speed. Values above the cap may be ignored.

#### Parameters

- `nNewSpeedPercent`: New movement speed as percentage (100 = normal speed, 150 = 50% faster, 200 = double speed)

#### Usage Examples

```nss
// Temporary +50% speed (30 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, 
    EffectMovementSpeedIncrease(150), oTarget, 30.0);
```

```nss
// Permanent speed boost (item/feat)
ApplyEffectToObject(DURATION_TYPE_PERMANENT, 
    EffectMovementSpeedIncrease(125), oTarget, 0.0);
```

---

### EffectMovementSpeedDecrease

**Routine:** 451

#### Function Signature

```nss
effect EffectMovementSpeedDecrease(int nPercentChange);
```

#### Description

Creates an effect that decreases movement speed. `nPercentChange` is the amount to reduce speed by (e.g., 50 = reduce speed by 50%).

#### Parameters

- `nPercentChange`: Percentage to reduce speed by (50 = 50% slower)

#### Usage Examples

```nss
// Temporary -50% speed (10 seconds)
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, 
    EffectMovementSpeedDecrease(50), oTarget, 10.0);
```

---

## Utility Functions

### ClearAllEffects

**Routine:** 271 (TSL only)

#### Function Signature

```nss
void ClearAllEffects(object oTarget = OBJECT_SELF);
```

#### Description

Removes all effects from the target object. Useful for resetting state or removing unwanted effects.

#### Usage Examples

```nss
// Remove all effects from self
ClearAllEffects();

// Remove all effects from another object
ClearAllEffects(oTarget);
```

---

### RemoveEffect

**Routine:** 272

#### Function Signature

```nss
void RemoveEffect(object oTarget, effect eEffect);
```

#### Description

Removes a specific effect from the target. Requires the effect to have been previously stored.

#### Usage Examples

```nss
// Store effect and remove it later
effect eBuff = EffectAbilityIncrease(ABILITY_STRENGTH, 2);
ApplyEffectToObject(DURATION_TYPE_PERMANENT, eBuff, oTarget, 0.0);
// ... later ...
RemoveEffect(oTarget, eBuff);
```

---

## Common Patterns and Best Practices

### Pattern: Damage with Save

```nss
int nDC = 15; // Difficulty class
int nDamage = 50;
int nHalfDamage = 25;

if (!ReflexSave(oTarget, nDC, SAVE_TYPE_REFLEX, oCaster)) {
    ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectDamage(nDamage, DAMAGE_TYPE_FIRE), oTarget, 0.0);
} else {
    ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectDamage(nHalfDamage, DAMAGE_TYPE_FIRE), oTarget, 0.0);
}
```

### Pattern: Temporary Buff/Debuff

```nss
// Apply temporary effect
effect eBuff = EffectAbilityIncrease(ABILITY_STRENGTH, 4);
ApplyEffectToObject(DURATION_TYPE_TEMPORARY, eBuff, oTarget, 60.0);
```

### Pattern: Permanent Item Effect

```nss
// Item applies permanent stat boost
effect eStat = EffectAbilityIncrease(ABILITY_CONSTITUTION, 2);
ApplyEffectToObject(DURATION_TYPE_PERMANENT, eStat, oTarget, 0.0);
```

### Pattern: Healing to Full HP

```nss
int nHealAmount = GetMaxHitPoints(oTarget) - GetCurrentHitPoints(oTarget);
if (nHealAmount > 0) {
    ApplyEffectToObject(DURATION_TYPE_INSTANT, 
        EffectHeal(nHealAmount), oTarget, 0.0);
}
```

### Best Practices

1. **Always Use DURATION_TYPE_INSTANT for Damage/Healing**: Damage and healing effects should always be instant
2. **Use DURATION_TYPE_TEMPORARY for Buffs/Debuffs**: Status effects with duration should be temporary
3. **Use DURATION_TYPE_PERMANENT for Item Effects**: Effects from items should be permanent
4. **Store Effects When Needed**: If you need to remove effects later, store them in variables
5. **Clear Effects When Resetting**: Use `ClearAllEffects()` when resetting object state

---

## Related Functions

- `GetFirstEffect()` - Get first effect on an object
- `GetNextEffect()` - Get next effect on an object
- `GetEffectType()` - Get the type of an effect
- `GetEffectSpellId()` - Get spell ID associated with an effect (if any)
- `ApplyEffectAtLocation()` - Apply effect at a location (for area effects)

---

## Additional Effect Functions

The effects system includes many more effect types. Common additional effects include:

- `EffectACIncrease` / `EffectACDecrease` - Armor class modifiers
- `EffectAttackIncrease` / `EffectAttackDecrease` - Attack bonus modifiers
- `EffectDamageResistance` - Damage resistance
- `EffectDamageImmunityIncrease` / `EffectDamageImmunityDecrease` - Damage immunity
- `EffectHaste` / `EffectSlow` - Action speed modifiers
- `EffectInvisibility` - Invisibility effects
- `EffectRegenerate` - Regeneration over time
- `EffectSavingThrowIncrease` / `EffectSavingThrowDecrease` - Save modifiers
- `EffectSkillIncrease` / `EffectSkillDecrease` - Skill modifiers
- `EffectVisualEffect` - Visual effects only (no gameplay impact)

Each follows the same pattern: create with an effect function, then apply with `ApplyEffectToObject()`.
