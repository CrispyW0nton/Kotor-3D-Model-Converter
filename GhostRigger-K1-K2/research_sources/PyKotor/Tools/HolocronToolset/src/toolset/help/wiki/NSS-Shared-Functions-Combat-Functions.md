# Combat Functions

Part of the [NSS File Format Documentation](NSS-File-Format).

**Category:** Shared Functions (K1 & TSL)

This document provides detailed documentation for NWScript combat-related functions. These functions allow scripts to check combat status, cancel combat, get combat information, and initiate attacks.

---

## Combat Status Functions

### GetIsInCombat

**Routine:** 320

#### Function Signature

```nss
int GetIsInCombat(object oCreature = OBJECT_SELF, int bOnlyCountReal = FALSE);
```

#### Description

Returns `TRUE` if the specified creature is currently in combat. Used to check combat status before performing combat-related actions.

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)
- `bOnlyCountReal`: If `TRUE`, only returns `TRUE` for "real" combat (TSL only, advanced usage - typically use `FALSE`)

#### Returns

- `TRUE` if the creature is in combat
- `FALSE` if not in combat or if the creature is invalid

#### Usage Examples

```nss
// Check if self is in combat
if (GetIsInCombat()) {
    // Do something during combat
}
```

```nss
// Check if specific creature is in combat
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsInCombat(oEnemy)) {
    // Enemy is already fighting
}
```

**Pattern: Check Combat Before Action**

```nss
// Only attack if not already in combat
if (!GetIsInCombat()) {
    object oTarget = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
    if (GetIsObjectValid(oTarget)) {
        ActionAttack(oTarget);
    }
}
```

---

### CancelCombat

**Routine:** 54

#### Function Signature

```nss
void CancelCombat(object oCreature = OBJECT_SELF);
```

#### Description

Cancels combat for the specified creature, ending their combat state. The creature will stop attacking and leave combat. Used in cutscenes, dialogue triggers, or scripted events that need to interrupt combat.

#### Parameters

- `oCreature`: Creature to cancel combat for (default: `OBJECT_SELF`)

#### Usage Examples

```nss
// Cancel own combat
CancelCombat();
```

```nss
// Cancel combat for specific creature (e.g., cutscene)
object oNPC = GetObjectByTag("boss");
CancelCombat(oNPC);
ClearAllActions(oNPC);
// Start cutscene...
```

**Pattern: End Combat for Cutscene**

```nss
// From vendor/Vanilla_KOTOR_Script_Source/TSL/Vanilla/Modules/904MAL_Malachor_V_Trayus_Core/k_def_death01_ls.nss
object oKreia = GetObjectByTag("kreia", 0);
AssignCommand(oKreia, ClearAllEffects());
AssignCommand(oKreia, ClearAllActions());
AssignCommand(oKreia, SurrenderToEnemies());
CancelCombat(oKreia);
AssignCommand(GetFirstPC(), ClearAllActions());
AssignCommand(GetFirstPC(), ClearAllEffects());
```

---

## Attack Target Functions

### GetAttackTarget

**Routine:** 316

#### Function Signature

```nss
object GetAttackTarget(object oCreature = OBJECT_SELF);
```

#### Description

Gets the current attack target of the specified creature. **Only works when the creature is in combat.**

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Target object if creature is in combat and has a target
- `OBJECT_INVALID` if not in combat or no target

#### Usage Examples

```nss
// Get current attack target
object oTarget = GetAttackTarget();
if (GetIsObjectValid(oTarget)) {
    // Do something with target
}
```

```nss
// Check if attacking specific target
object oEnemy = GetObjectByTag("boss");
if (GetAttackTarget() == oEnemy) {
    // Currently attacking the boss
}
```

**Pattern: Check Current Target**

```nss
if (GetIsInCombat()) {
    object oCurrentTarget = GetAttackTarget();
    if (GetIsObjectValid(oCurrentTarget)) {
        float fDistance = GetDistanceBetween(OBJECT_SELF, oCurrentTarget);
        if (fDistance > 10.0) {
            // Target too far, switch targets
            object oCloser = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
            if (GetIsObjectValid(oCloser)) {
                ClearAllActions();
                ActionAttack(oCloser);
            }
        }
    }
}
```

---

### GetLastAttacker

**Routine:** 36

#### Function Signature

```nss
object GetLastAttacker(object oAttackee = OBJECT_SELF);
```

#### Description

Gets the last creature that attacked the specified target. Useful for retaliation scripts or identifying threat sources.

#### Parameters

- `oAttackee`: Creature that was attacked (default: `OBJECT_SELF`)

#### Returns

- Object of the last attacker
- `OBJECT_INVALID` if no attacker or invalid object

#### Usage Examples

```nss
// Get last attacker
object oAttacker = GetLastAttacker();
if (GetIsObjectValid(oAttacker)) {
    // Retaliate against attacker
    ActionAttack(oAttacker);
}
```

```nss
// Check if attacked by specific creature
object oEnemy = GetObjectByTag("hated_enemy");
if (GetLastAttacker() == oEnemy) {
    // Attacked by specific enemy
    ApplyEffectToObject(DURATION_TYPE_TEMPORARY, EffectHaste(), OBJECT_SELF, 60.0);
}
```

---

### GetFirstAttacker

**Routine:** 727 (TSL only)

#### Function Signature

```nss
object GetFirstAttacker(object oCreature = OBJECT_SELF);
```

#### Description

Gets the first creature in the attacker list for the specified creature. Used to identify the primary threat.

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- First attacker object, or `OBJECT_INVALID` if none

---

## Attack Information Functions

### GetLastAttackType

**Routine:** 317

#### Function Signature

```nss
int GetLastAttackType(object oCreature = OBJECT_SELF);
```

#### Description

Gets the type of the creature's last attack. **Only works when the creature is in combat.**

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Attack type constant (`SPECIAL_ATTACK_*`), or invalid if not in combat

#### Attack Type Constants

- `SPECIAL_ATTACK_NONE` - No special attack
- `SPECIAL_ATTACK_CALLED_SHOT_LEG` - Called shot to leg
- `SPECIAL_ATTACK_CALLED_SHOT_ARM` - Called shot to arm
- `SPECIAL_ATTACK_SAP` - Sap attack
- `SPECIAL_ATTACK_DISARM` - Disarm attack
- `SPECIAL_ATTACK_IMPROVED_DISARM` - Improved disarm
- `SPECIAL_ATTACK_KNOCKDOWN` - Knockdown attack
- `SPECIAL_ATTACK_IMPROVED_KNOCKDOWN` - Improved knockdown
- `SPECIAL_ATTACK_STUN` - Stun attack
- `SPECIAL_ATTACK_DEATH_ATTACK` - Death attack
- `SPECIAL_ATTACK_CUTSCENE_INVISIBLE_ATTACK` - Cutscene attack

---

### GetLastAttackMode

**Routine:** 318

#### Function Signature

```nss
int GetLastAttackMode(object oCreature = OBJECT_SELF);
```

#### Description

Gets the combat mode of the creature's last attack. **Only works when the creature is in combat.**

#### Parameters

- `oCreature`: Creature to check (default: `OBJECT_SELF`)

#### Returns

- Combat mode constant (`COMBAT_MODE_*`)

#### Combat Mode Constants

- `COMBAT_MODE_RANGED` - Ranged attack
- `COMBAT_MODE_MELEE` - Melee attack

---

### GetLastAttackResult

**Routine:** 725 (TSL only)

#### Function Signature

```nss
int GetLastAttackResult(object oAttacker = OBJECT_SELF);
```

#### Description

Gets the result of the attacker's last attack attempt.

#### Parameters

- `oAttacker`: Attacker to check (default: `OBJECT_SELF`)

#### Returns

- Attack result constant (hit, miss, critical, etc.)

---

## Combat Actions

### ActionAttack

**Routine:** 37

#### Function Signature

```nss
void ActionAttack(object oAttackee, int bPassive = FALSE);
```

#### Description

Queues an attack action on the specified target. The creature will attempt to attack the target in combat. Attacks execute according to combat rules (attack rolls, damage, etc.).

#### Parameters

- `oAttackee`: Target to attack
- `bPassive`: If `TRUE`, uses passive attack mode (default: `FALSE`)

#### Usage Examples

```nss
// Basic attack
object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
if (GetIsObjectValid(oEnemy)) {
    ActionAttack(oEnemy);
}
```

**Pattern: AI Combat Routine**

```nss
// From vendor/K1_Community_Patch/Source/k_inc_generic.nss
if (GetIsObjectValid(oIntruder)) {
    ClearAllActions();
    ActionAttack(oIntruder);
    return;
} else {
    object oDefault = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
    if (GetIsObjectValid(oDefault)) {
        ClearAllActions();
        ActionAttack(oDefault);
        return;
    }
}
```

**Pattern: Attack Nearest Enemy**

```nss
if (!GetIsInCombat()) {
    object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
    if (GetIsObjectValid(oEnemy)) {
        ClearAllActions();
        ActionAttack(oEnemy);
    }
}
```

---

### SurrenderToEnemies

**Routine:** 379 (TSL only)

#### Function Signature

```nss
void SurrenderToEnemies(object oCreature = OBJECT_SELF);
```

#### Description

Makes the creature surrender to enemies, ending combat and making them non-hostile.

#### Parameters

- `oCreature`: Creature to surrender (default: `OBJECT_SELF`)

#### Usage Examples

```nss
// Surrender self
SurrenderToEnemies();

// Make NPC surrender
object oNPC = GetObjectByTag("defeated_enemy");
SurrenderToEnemies(oNPC);
CancelCombat(oNPC);
```

---

## Common Patterns and Best Practices

### Pattern: Combat Detection and Response

```nss
// Heartbeat script that responds to combat
void main() {
    if (GetIsInCombat()) {
        object oAttacker = GetLastAttacker();
        if (GetIsObjectValid(oAttacker)) {
            // Do something when attacked
        }
    }
}
```

### Pattern: End Combat for Cutscene

```nss
// Stop combat and prepare for cutscene
CancelCombat(OBJECT_SELF);
CancelCombat(oTarget);
ClearAllActions();
ClearAllEffects();
// Start cutscene...
```

### Pattern: Conditional Combat

```nss
// Only enter combat if certain conditions met
if (GetLocalInt(OBJECT_SELF, "CanFight") == 1 && !GetIsInCombat()) {
    object oEnemy = GetNearestCreature(CREATURE_TYPE_REPUTATION, REPUTATION_TYPE_ENEMY);
    if (GetIsObjectValid(oEnemy)) {
        ClearAllActions();
        ActionAttack(oEnemy);
    }
}
```

### Pattern: Retaliate on Attack

```nss
// Heartbeat script - attack whoever attacked you
void main() {
    object oAttacker = GetLastAttacker();
    if (GetIsObjectValid(oAttacker) && !GetIsInCombat()) {
        ClearAllActions();
        ActionAttack(oAttacker);
    }
}
```

### Best Practices

1. **Always Check Combat Status**: Use `GetIsInCombat()` before performing combat-related actions
2. **Clear Actions Before Attacking**: Use `ClearAllActions()` before `ActionAttack()` for reliable behavior
3. **Cancel Combat for Cutscenes**: Always cancel combat before starting cutscenes or dialogues
4. **Validate Attack Targets**: Check `GetIsObjectValid()` before using attack target functions
5. **Combat Functions Only Work in Combat**: Functions like `GetAttackTarget()` only work when creature is in combat

---

## Related Functions

- `GetNearestCreature()` - Find nearby creatures (used to find combat targets)
- `GetDistanceBetween()` - Get distance to target (for range checks)
- `ClearAllActions()` - Clear action queue (often needed before combat actions)
- `GetFaction()` / `GetReputation()` - Check faction/reputation (for determining enemies)

---

## Additional Combat Functions

Additional combat-related functions include:

- `GetAttemptedAttackTarget()` - Get attempted attack target (Routine 361, TSL)
- `GetGoingToBeAttackedBy()` - Get who will attack the target (Routine 211)
- `GetLastKiller()` - Get last creature that killed someone (Routine 437, TSL)
- `GetNextAttacker()` - Get next attacker in list (Routine 728, TSL)
- `CutsceneAttack()` - Perform a scripted attack for cutscenes (Routine 503, TSL)

Each follows similar patterns to the functions documented above.
